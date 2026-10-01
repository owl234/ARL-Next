# backend/app/celerytask.py
import signal
import time
from bson import ObjectId
from app.config import Config
from celery import Celery, platforms, current_task
from celery.schedules import crontab
from app import utils
from app import tasks as wrap_tasks
from app.modules import (
    CeleryAction, TaskSyncStatus, TaskStatus, CeleryRoutingKey,
)

logger = utils.get_logger()

celery = Celery('task', broker=Config.CELERY_BROKER_URL)

# ═══════════════════════════════════════════════════════════
# Celery 配置
# ═══════════════════════════════════════════════════════════

celery.conf.update(
    task_acks_late=True,
    worker_max_tasks_per_child=50,
    broker_connection_retry_on_startup=True,
    task_soft_time_limit=2592000,
    task_time_limit=2592300,
    worker_prefetch_multiplier=1,
    broker_transport_options={
        "max_retries": 3,
        "interval_start": 0,
        "interval_step": 0.2,
        "interval_max": 0.5,
    },

    # ★ 漏洞平台聚合：任务路由
    task_routes={
        # 抓取类任务
        "app.celerytask.vuln_platform_fetch_all": {
            "queue": "platform_fetch",
        },
        "app.celerytask.vuln_platform_fetch_one": {
            "queue": "platform_fetch",
        },
        # 扫描类任务
        "app.celerytask.vuln_platform_execute_scan": {
            "queue": "scan",
        },
        # 提交类任务
        "app.celerytask.vuln_platform_auto_submit": {
            "queue": "platform_fetch",
        },
        # 检查类任务
        "app.celerytask.vuln_platform_check_scope": {
            "queue": "platform_fetch",
        },
        "app.celerytask.vuln_platform_cookie_check": {
            "queue": "platform_fetch",
        },
        # 复扫类任务
        "app.celerytask.vuln_platform_weekly_rescan": {
            "queue": "platform_fetch",
        },
        "app.celerytask.vuln_platform_daily_rescan": {
            "queue": "platform_fetch",
        },
    },

    # ★ 漏洞平台聚合：Beat 定时调度
    beat_schedule={
        # 每天凌晨 2 点抓取所有已启用平台
        "vuln-platform-fetch-daily": {
            "task": "app.celerytask.vuln_platform_fetch_all",
            "schedule": crontab(hour=2, minute=0),
        },
        # 每 6 小时检查项目范围变化
        "vuln-platform-check-scope": {
            "task": "app.celerytask.vuln_platform_check_scope",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        # 每 6 小时检查 Cookie 有效性
        "vuln-platform-cookie-check": {
            "task": "app.celerytask.vuln_platform_cookie_check",
            "schedule": crontab(minute=30, hour="*/6"),
        },
        # 每周一早上 8 点全量复扫
        "vuln-platform-weekly-rescan": {
            "task": "app.celerytask.vuln_platform_weekly_rescan",
            "schedule": crontab(day_of_week=1, hour=8, minute=0),
        },
        # 每天中午 12 点增量复扫
        "vuln-platform-daily-rescan": {
            "task": "app.celerytask.vuln_platform_daily_rescan",
            "schedule": crontab(hour=12, minute=0),
        },
    },
)

platforms.C_FORCE_ROOT = True

from celery.signals import task_prerun, task_postrun, worker_process_init, task_failure
try:
    from celery.exceptions import WorkerLostError
except ImportError:
    try:
        from billiard.exceptions import WorkerLostError
    except ImportError:
        WorkerLostError = None

from app.utils import arl_task_id_var, MongoSyslogHandler
import threading
_token_local = threading.local()


# ═══════════════════════════════════════════════════════════
# Worker / Task 信号钩子
# ═══════════════════════════════════════════════════════════

@worker_process_init.connect
def setup_worker_process(**kw):
    try:
        MongoSyslogHandler._ensure_worker()
    except Exception:
        pass


@task_prerun.connect
def setup_task_context(task_id, task, args, kwargs, **kw):
    try:
        options = None
        if args and len(args) > 0:
            options = args[0]
        elif kwargs and 'options' in kwargs:
            options = kwargs.get('options')

        business_task_id = "global"
        if isinstance(options, dict):
            if "data" in options and isinstance(options["data"], dict):
                business_task_id = (
                    options["data"].get("task_id")
                    or options["data"].get("scheduler_id")
                    or options["data"].get("_id")
                    or "global"
                )
            elif "task_id" in options:
                business_task_id = options.get("task_id") or "global"
            elif "scheduler_id" in options:
                business_task_id = options.get("scheduler_id") or "global"
            elif "_id" in options:
                business_task_id = options.get("_id") or "global"

        token = arl_task_id_var.set(str(business_task_id))
        _token_local.token = token
    except Exception:
        pass


@task_postrun.connect
def teardown_task_context(**kw):
    token = getattr(_token_local, 'token', None)
    if token:
        try:
            arl_task_id_var.reset(token)
        except ValueError:
            pass
        _token_local.token = None

@task_failure.connect
def handle_task_failure(sender=None, task_id=None, exception=None, args=None, kwargs=None, traceback=None, einfo=None, **kw):
    """
    捕获 Celery Worker 执行失败，特别针对 Linux 内核 OOM Killer (SIGKILL / Signal 9 / WorkerLostError)
    实现秒级熔断收敛，在 MongoDB 任务记录与对应 task_id 的 syslog 中抛出完整诊断卡片，
    防止 RabbitMQ 重复投递导致无限 OOM 崩溃循环，让后续排队任务正常拉起。
    """
    try:
        exc_str = str(exception)
        is_worker_lost = False
        if WorkerLostError and isinstance(exception, WorkerLostError):
            is_worker_lost = True
        elif "signal 9" in exc_str or "SIGKILL" in exc_str or "exitcode 137" in exc_str or "WorkerLostError" in exc_str:
            is_worker_lost = True

        # 提取业务任务编号 (business_task_id)
        options = None
        if args and len(args) > 0:
            options = args[0]
        elif kwargs and 'options' in kwargs:
            options = kwargs.get('options')

        business_task_id = None
        if isinstance(options, dict):
            if "data" in options and isinstance(options["data"], dict):
                business_task_id = options["data"].get("task_id") or options["data"].get("scheduler_id") or options["data"].get("_id")
            elif "task_id" in options:
                business_task_id = options.get("task_id")
            elif "scheduler_id" in options:
                business_task_id = options.get("scheduler_id")
            elif "_id" in options:
                business_task_id = options.get("_id")

        target_collection = 'task'
        task_data = None
        if business_task_id and business_task_id != "global":
            try:
                b_task_id_str = str(business_task_id)
                if ObjectId.is_valid(b_task_id_str):
                    task_data = utils.conn_db('task').find_one({"_id": ObjectId(b_task_id_str)})
                    if not task_data:
                        task_data = utils.conn_db('github_task').find_one({"_id": ObjectId(b_task_id_str)})
                        if task_data:
                            target_collection = 'github_task'
            except Exception:
                pass

        if not task_data and task_id:
            task_data = utils.conn_db('task').find_one({"celery_id": str(task_id)})
            if not task_data:
                task_data = utils.conn_db('github_task').find_one({"celery_id": str(task_id)})
                if task_data:
                    target_collection = 'github_task'

        if not task_data:
            logger.warning(f"Task failure handler: could not locate task for celery_id={task_id}, exc={exc_str}")
            return

        db_id = task_data["_id"]
        current_status = task_data.get("status", "")
        # 如果任务已经被标记为结束或手动停止，不重复覆盖
        if current_status in [TaskStatus.DONE, TaskStatus.STOP]:
            return

        curr_d = utils.curr_date()
        if is_worker_lost:
            last_phase = current_status or "未知阶段"
            log_msg = (
                f"【🚨 CRITICAL 异常抛出】【OOM-KILLER】检测到 Worker 扫描子进程异常终止 (WorkerLostError: signal 9 SIGKILL)！\n"
                f"• 根因推断: Linux 内核物理内存耗尽 (OOM Killer) 强行杀死扫描子进程 (或宿主机外部强制 SIGKILL)\n"
                f"• 中断阶段: 任务在【{last_phase}】阶段失联\n"
                f"• 原始异常: {exc_str}\n"
                f"• 排查指引: \n"
                f"   1. 登录宿主机执行: dmesg -T | grep -i oom 确认内核 OOM 强杀记录\n"
                f"   2. 检查宿主机内存与 Swap 分区（建议配置 2GB~4GB Swap 规避突发峰值）\n"
                f"   3. 避免在较小内存机器上配置超大域名/目录爆破字典或超高扫描并发\n"
                f"• 熔断保护: 当前任务已标记为 ERROR 终止态，Worker 槽位已释放，排队任务正常继续执行"
            )
            logger.critical(f"Task {db_id} terminated prematurely by OOM/SIGKILL in phase [{last_phase}]")
            end_reason = "系统内存耗尽 (OOM Killer 强杀)"
        else:
            log_msg = f"【❌ 任务执行异常】Celery Worker 报告未捕获错误: {exc_str}"
            logger.error(f"Task {db_id} failed with error: {exc_str}")
            end_reason = f"任务执行异常: {exc_str[:100]}"

        # 写入该任务的专属 syslog 日志集合 (整型时间戳统一模型)
        try:
            utils.conn_db('syslog').insert_one({
                "task_id": str(db_id),
                "message": log_msg,
                "level": "CRITICAL" if is_worker_lost else "ERROR",
                "time": curr_d,
                "timestamp": int(time.time())
            })
        except Exception as log_err:
            logger.error(f"Failed to insert failure syslog for task {db_id}: {log_err}")

        # 数据库原子级更新为 ERROR，同时防范与用户在 Web 端手动点击 STOP 的时序竞态
        try:
            update_ret = utils.conn_db(target_collection).update_one(
                {"_id": db_id, "status": {"$nin": [TaskStatus.DONE, TaskStatus.STOP]}},
                {"$set": {
                    "status": TaskStatus.ERROR,
                    "end_reason": end_reason,
                    "error_msg": exc_str,
                    "end_time": curr_d
                }}
            )
            if update_ret.matched_count == 0:
                logger.info(f"Task {db_id} was already finalized or stopped, skipping failure overwrite.")
        except Exception as db_err:
            logger.error(f"Failed to update task {db_id} status on failure: {db_err}")

        # 异步线程清理临时文件，规避 Celery 主进程同步 I/O 阻塞导致 RabbitMQ 心跳超时
        try:
            threading.Thread(
                target=utils.clean_task_tmp_files,
                args=(str(db_id),),
                daemon=True,
                name=f"CleanTmpFiles-{db_id}"
            ).start()
        except Exception as clean_err:
            logger.warning(f"Failed to spawn clean_task_tmp_files thread for task {db_id}: {clean_err}")

    except Exception as e:
        logger.exception(f"Unexpected error in handle_task_failure: {e}")



# ═══════════════════════════════════════════════════════════
# 主任务入口（复用现有 arl_task）
# ═══════════════════════════════════════════════════════════

@celery.task(queue=CeleryRoutingKey.ASSET_TASK)
def arl_task(options):
    # 这里不检验 celery_action， 调用的时候区分
    run_task(options)


@celery.task(name='app.celerytask.dict_import_celery_task',
             queue=CeleryRoutingKey.ASSET_TASK_LIGHT)
def dict_import_celery_task(task_id, temp_file_path, target_dict_path):
    """
    异步超大字典流式导入与去重写入
    """
    from app.services.dict_upload import background_process_dict
    background_process_dict(task_id, temp_file_path, target_dict_path)


def sigterm_handler(signum, frame):
    if not current_task:
        return
    celery_id = current_task.request.id
    routing_key = current_task.request.delivery_info['routing_key']
    logger.info(
        f"Caught signal {signum}, celery_id:{celery_id} "
        f"terminating {routing_key}..."
    )

    logger.info(f"{current_task.request}")
    utils.exit_gracefully(signum, frame)


def run_task(options):
    signal.signal(signal.SIGTERM, sigterm_handler)
    action = options.get("celery_action")
    data = options.get("data")

    action_map = {
        CeleryAction.DOMAIN_TASK_SYNC_TASK: domain_task_sync,
        CeleryAction.DOMAIN_EXEC_TASK: domain_exec,
        CeleryAction.IP_EXEC_TASK: ip_exec,
        CeleryAction.DOMAIN_TASK: domain_task,
        CeleryAction.IP_TASK: ip_task,
        CeleryAction.RUN_RISK_CRUISING: run_risk_cruising_task,
        CeleryAction.FOFA_TASK: fofa_task,
        CeleryAction.GITHUB_TASK_TASK: github_task_task,
        CeleryAction.GITHUB_TASK_MONITOR: github_task_monitor,
        CeleryAction.ASSET_SITE_UPDATE: asset_site_update,
        CeleryAction.ADD_ASSET_SITE_TASK: asset_site_add_task,
        CeleryAction.ASSET_WIH_UPDATE: asset_wih_update_task,
        CeleryAction.ONESHOT_DOMAIN_EXEC_TASK: oneshot_domain_exec,
        CeleryAction.ONESHOT_IP_EXEC_TASK: oneshot_ip_exec,
        CeleryAction.GITHUB_THREAT_CVE: github_threat_cve_task,
        CeleryAction.GITHUB_THREAT_TOOLS: github_threat_tools_task,
        CeleryAction.GITHUB_THREAT_HACKERS: github_threat_hackers_task,
    }

    start_time = time.time()
    logger.info("run_task action:{} time: {}".format(action, start_time))
    logger.info("name:{}, target:{}, task_id:{}".format(
        data.get("name"), data.get("target"), data.get("task_id")))

    task_options = data.get("options", {})
    if task_options:
        active_opts = []
        for k, v in task_options.items():
            if v is True:
                active_opts.append(f"已开启 {k}")
            elif isinstance(v, str) and v:
                active_opts.append(f"{k}: {v}")
        if active_opts:
            logger.info(f"任务配置: {', '.join(active_opts)}")

    task_id = data.get("task_id")
    if task_id:
        try:
            item = utils.conn_db('task').find_one(
                {"_id": ObjectId(task_id)})
            if not item:
                item = utils.conn_db('github_task').find_one(
                    {"_id": ObjectId(task_id)})

            if item and item.get("status") in [
                TaskStatus.STOP, TaskStatus.ERROR, TaskStatus.DONE
            ]:
                allow_after_done = [
                    CeleryAction.DOMAIN_TASK_SYNC_TASK,
                    CeleryAction.ASSET_SITE_UPDATE,
                    CeleryAction.ASSET_WIH_UPDATE,
                    CeleryAction.ADD_ASSET_SITE_TASK,
                ]
                if action not in allow_after_done:
                    logger.info(
                        f"Task {task_id} has been stopped or ended "
                        f"manually, skip execution"
                    )
                    return

            if action in [
                CeleryAction.DOMAIN_TASK,
                CeleryAction.IP_TASK,
                CeleryAction.RUN_RISK_CRUISING,
                CeleryAction.FOFA_TASK,
            ]:
                utils.clean_task_data(task_id)
        except Exception as e:
            logger.error(
                f"Error checking or cleaning task {task_id}: {e}")

    try:
        fun = action_map.get(action)
        if fun:
            fun(data)
        else:
            logger.warning("not found {} action".format(action))
    except Exception as e:
        logger.exception(e)

    elapsed = time.time() - start_time
    logger.info("end {} elapsed: {}".format(action, elapsed))


@celery.task(queue=CeleryRoutingKey.GITHUB_TASK)
def arl_github(options):
    # 这里不检验 celery_action， 调用的时候区分
    run_task(options)


# ═══════════════════════════════════════════════════════════
# 原有任务处理函数（保持不变）
# ═══════════════════════════════════════════════════════════

def domain_exec(options):
    """域名监测任务"""
    scope_id = options.get("scope_id")
    domain = options.get("domain")
    scheduler_id = options.get("scheduler_id")
    monitor_options = options.get("monitor_options")
    name = options.get("name")
    wrap_tasks.domain_executors(
        base_domain=domain, scheduler_id=scheduler_id,
        scope_id=scope_id, options=monitor_options, name=name)


def oneshot_domain_exec(options):
    """一次性域名监测任务"""
    scope_id = options.get("scope_id")
    domain = options.get("domain")
    monitor_options = options.get("monitor_options")
    name = options.get("name")
    task_id = options.get("task_id")
    wrap_tasks.oneshot_domain_executors(
        base_domain=domain, scope_id=scope_id,
        options=monitor_options, name=name, task_id=task_id)


def domain_task_sync(options):
    """域名同步任务"""
    from app.services.syncAsset import sync_asset
    scope_id = options.get("scope_id")
    task_id = options.get("task_id")
    query = {"_id": ObjectId(task_id)}
    try:
        update = {"$set": {"sync_status": TaskSyncStatus.RUNNING}}
        utils.conn_db('task').update_one(query, update)

        sync_asset(task_id, scope_id, update_flag=False)

        update = {"$set": {"sync_status": TaskSyncStatus.DEFAULT}}
        utils.conn_db('task').update_one(query, update)
    except Exception as e:
        update = {"$set": {"sync_status": TaskSyncStatus.ERROR}}
        utils.conn_db('task').update_one(query, update)
        logger.exception(e)


def domain_task(options):
    """常规域名任务"""
    target = options["target"]
    task_options = options["options"]
    task_id = options["task_id"]
    item = utils.conn_db('task').find_one({"_id": ObjectId(task_id)})
    if not item:
        logger.info("domain_task not found {} {}".format(target, item))
        return
    wrap_tasks.domain_task(target, task_id, task_options)


def ip_task(options):
    """常规IP任务"""
    target = options["target"]
    task_options = options["options"]
    task_id = options["task_id"]
    wrap_tasks.ip_task(target, task_id, task_options)


def run_risk_cruising_task(options):
    task_id = options["task_id"]
    wrap_tasks.run_risk_cruising_task(task_id)


def fofa_task(options):
    task_id = options["task_id"]
    task_options = options["options"]
    target = " ".join(options["fofa_ip"])
    wrap_tasks.ip_task(target, task_id, task_options)


def ip_exec(options):
    """IP 监测任务"""
    scope_id = options.get("scope_id")
    target = options.get("domain")
    scheduler_id = options.get("scheduler_id")
    monitor_options = options.get("monitor_options")
    name = options.get("name")
    wrap_tasks.ip_executor(
        target=target, scope_id=scope_id, task_name=name,
        scheduler_id=scheduler_id, options=monitor_options)


def oneshot_ip_exec(options):
    """一次性 IP 监测任务"""
    scope_id = options.get("scope_id")
    target = options.get("domain")
    monitor_options = options.get("monitor_options")
    name = options.get("name")
    task_id = options.get("task_id")
    wrap_tasks.oneshot_ip_executors(
        target=target, scope_id=scope_id, task_name=name,
        options=monitor_options, task_id=task_id)


def github_task_task(options):
    task_id = options["task_id"]
    keyword = options["keyword"]
    wrap_tasks.github_task_task(task_id=task_id, keyword=keyword)


def github_task_monitor(options):
    task_id = options["task_id"]
    keyword = options["keyword"]
    scheduler_id = options["github_scheduler_id"]
    wrap_tasks.github_task_monitor(
        task_id=task_id, keyword=keyword, scheduler_id=scheduler_id)


def asset_site_update(options):
    task_id = options["task_id"]
    task_options = options["options"]
    scope_id = task_options["scope_id"]
    scheduler_id = task_options["scheduler_id"]
    wrap_tasks.asset_site_update_task(
        task_id=task_id, scope_id=scope_id, scheduler_id=scheduler_id)


def asset_wih_update_task(options):
    task_id = options["task_id"]
    task_options = options["options"]
    scope_id = task_options["scope_id"]
    scheduler_id = task_options["scheduler_id"]
    wrap_tasks.asset_wih_update_task(
        task_id=task_id, scope_id=scope_id, scheduler_id=scheduler_id)


def asset_site_add_task(options):
    task_id = options["task_id"]
    wrap_tasks.run_add_asset_site_task(task_id)


# ═══════════════════════════════════════════════════════════
# ★ 漏洞平台聚合：Celery 任务
# ═══════════════════════════════════════════════════════════

@celery.task(name='app.celerytask.vuln_platform_fetch_all',
             queue='platform_fetch')
def vuln_platform_fetch_all():
    """抓取所有已启用平台"""
    from app.services.vuln_platform import ProjectService

    try:
        service = ProjectService()
        result = service.fetch_all_platforms()
        logger.info("全平台抓取完成: {}".format(result))
        return {"platforms": result}
    except Exception as e:
        logger.exception(e)
        return {"error": str(e)}


@celery.task(name='app.celerytask.vuln_platform_fetch_one',
             queue='platform_fetch')
def vuln_platform_fetch_one(platform_name):
    """抓取单个平台"""
    from app.services.vuln_platform import ProjectService

    try:
        service = ProjectService()
        result = service.fetch_and_sync(platform_name)
        logger.info("[{}] 抓取完成: {}".format(platform_name, result))
        return result
    except Exception as e:
        logger.exception(e)
        return {"error": str(e)}


@celery.task(name='app.celerytask.vuln_platform_execute_scan',
             queue='scan')
def vuln_platform_execute_scan(scan_request):
    """执行扫描任务（由 ScanOrchestrator 下发）"""
    from app.services.vuln_platform import (
        ProjectService, TargetService, VulnService,
    )
    from app.services.vuln_platform.scan_thread import (
        nuclei_scan_thread,
    )

    project_fp = scan_request["project_fingerprint"]
    source_platform = scan_request.get("source_platform")
    scope = scan_request["scope"]
    scan_config = scan_request["scan_config"]

    logger.info("执行扫描: project={}, targets={}".format(
        project_fp, len(scope)))

    project_service = ProjectService()
    target_service = TargetService()
    vuln_service = VulnService()

    try:
        findings = nuclei_scan_thread(
            targets=scope,
            scan_config=scan_config,
            project_fingerprint=project_fp,
            source_platform=source_platform,
            concurrency=scan_config.get("max_workers", 10))
    except Exception as e:
        logger.error("扫描失败: project={}, error={}".format(
            project_fp, e))
        raise

    # 漏洞落库
    new_count = 0
    for f in findings:
        is_new, _ = vuln_service.insert_or_update_finding(
            f, project_fp, source_platform)
        if is_new:
            new_count += 1

    # 更新项目状态
    project_service.update_scan_state(
        project_fp, status="completed",
        vuln_count=len(findings))

    # 标记目标已扫描
    for t in scope:
        pending = target_service.list_pending()
        for p in pending:
            if p.get("target") == t:
                target_service.mark_scanned(p["fingerprint"])
                break

    logger.info("扫描完成: project={}, findings={}, new={}".format(
        project_fp, len(findings), new_count))

    return {"project": project_fp, "findings": len(findings),
            "new": new_count}


@celery.task(name='app.celerytask.vuln_platform_auto_submit',
             queue='platform_fetch')
def vuln_platform_auto_submit(project_fingerprint):
    """扫描完成后自动提交项目漏洞"""
    from app.services.vuln_platform import VulnSubmitter

    try:
        result = VulnSubmitter().submit_project_vulns(
            project_fingerprint)
        logger.info("项目 {} 自动提交结果: {}".format(
            project_fingerprint, result))
        return result
    except Exception as e:
        logger.exception(e)
        return {"error": str(e)}


@celery.task(name='app.celerytask.vuln_platform_check_scope',
             queue='platform_fetch')
def vuln_platform_check_scope():
    """检查所有活跃项目的范围变化"""
    from app.services.vuln_platform import (
        ProjectService, ScanOrchestrator,
    )

    try:
        project_service = ProjectService()
        orchestrator = ScanOrchestrator()
        projects = project_service.list_active()

        changes = []
        for p in projects:
            r = orchestrator.dispatch_scan(p["fingerprint"])
            if r.get("dispatched"):
                changes.append({
                    "project": p["fingerprint"],
                    "target_count": r.get("target_count", 0),
                })

        logger.info("范围检查完成: {} 个项目有变化".format(
            len(changes)))
        return {"projects_with_changes": len(changes),
                "details": changes}
    except Exception as e:
        logger.exception(e)
        return {"error": str(e)}


@celery.task(name='app.celerytask.vuln_platform_cookie_check',
             queue='platform_fetch')
def vuln_platform_cookie_check():
    """检查所有需要登录的平台 Cookie 有效性"""
    from app.adapters.vuln_platform import get_all_adapters

    try:
        adapters = get_all_adapters()
        invalid = []
        for name, adapter in adapters.items():
            if not adapter.cookie_mgr:
                continue
            test_url = adapter.config.get("test_url", "")
            if not adapter.cookie_mgr.is_cookie_valid(test_url):
                invalid.append(name)
                logger.warning("[{}] Cookie 已失效".format(name))

        return {"invalid_cookies": invalid}
    except Exception as e:
        logger.exception(e)
        return {"error": str(e)}


@celery.task(name='app.celerytask.vuln_platform_weekly_rescan',
             queue='platform_fetch')
def vuln_platform_weekly_rescan():
    """每周全量复扫"""
    from app.services.vuln_platform import (
        ProjectService, ScanOrchestrator,
    )

    try:
        project_service = ProjectService()
        orchestrator = ScanOrchestrator()
        count = 0
        for p in project_service.list_active():
            r = orchestrator.full_scan(p["fingerprint"])
            if r.get("dispatched"):
                count += 1

        logger.info("每周全量复扫下发: {} 个项目".format(count))
        return {"dispatched": count}
    except Exception as e:
        logger.exception(e)
        return {"error": str(e)}


@celery.task(name='app.celerytask.vuln_platform_daily_rescan',
             queue='platform_fetch')
def vuln_platform_daily_rescan():
    """每日增量复扫"""
    from app.services.vuln_platform import (
        ProjectService, ScanOrchestrator,
    )

    try:
        project_service = ProjectService()
        orchestrator = ScanOrchestrator()
        count = 0
        for p in project_service.list_active():
            r = orchestrator.incremental_rescan(p["fingerprint"])
            if r.get("dispatched"):
                count += 1

        logger.info("每日增量复扫下发: {} 个项目".format(count))
        return {"dispatched": count}
    except Exception as e:
        logger.exception(e)
        return {"error": str(e)}


def github_threat_cve_task(options):
    from app.tasks.github_threat_monitor import run_threat_task_worker
    run_threat_task_worker("cve")


def github_threat_tools_task(options):
    from app.tasks.github_threat_monitor import run_threat_task_worker
    run_threat_task_worker("tools")


def github_threat_hackers_task(options):
    from app.tasks.github_threat_monitor import run_threat_task_worker
    run_threat_task_worker("hackers")
