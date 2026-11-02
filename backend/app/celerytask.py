import signal
import time
from bson import ObjectId
from app.config import Config
from celery import Celery, platforms, current_task
from app import utils
from app import tasks as wrap_tasks
from app.modules import CeleryAction, TaskStatus, CeleryRoutingKey

logger = utils.get_logger()

celery = Celery('task', broker=Config.CELERY_BROKER_URL)

celery.conf.update(
    task_acks_late=True,
    worker_max_tasks_per_child=50,
    broker_connection_retry_on_startup=True,
    task_soft_time_limit=2592000,
    task_time_limit=2592300,
    worker_prefetch_multiplier=1,
    broker_transport_options={"max_retries": 3, "interval_start": 0, "interval_step": 0.2, "interval_max": 0.5},
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
                business_task_id = options["data"].get("task_id") or options["data"].get("scheduler_id") or options["data"].get("_id") or "global"
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


@celery.task(queue=CeleryRoutingKey.ASSET_TASK)
def arl_task(options):
    # 这里不检验 celery_action， 调用的时候区分
    run_task(options)


@celery.task(name='app.celerytask.dict_import_celery_task', queue=CeleryRoutingKey.ASSET_TASK_LIGHT)
def dict_import_celery_task(task_id, temp_file_path, target_dict_path):
    """
    异步超大字典流式导入与去重写入（由 Celery Worker 容器独立调度执行，彻底规避 Web 容器 Worker 回收中断）
    """
    from app.services.dict_upload import background_process_dict
    background_process_dict(task_id, temp_file_path, target_dict_path)


@celery.task(name='app.celerytask.nuclei_template_sync_task', queue=CeleryRoutingKey.ASSET_TASK_LIGHT)
def nuclei_template_sync_task(zip_file_path=None, target_version=None):
    """
    Worker 节点协同更新官方社区模板（保持多容器环境模板版本与 Web 面板一致）
    """
    logger.info("Executing Worker nuclei_template_sync_task...")
    try:
        from app.routes.nuclei import get_community_templates_dir, extract_templates_zip_to_dir, update_templates_config_version, load_community_index
        import os
        import requests
        from app.config import Config

        target_dir = get_community_templates_dir() or "/root/nuclei-templates"
        if zip_file_path and os.path.isfile(zip_file_path):
            extract_templates_zip_to_dir(zip_file_path, target_dir)
            if target_version:
                update_templates_config_version(target_version)
        else:
            mirrors = ["https://ghfast.top/", "https://ghproxy.net/"]
            raw_url = "https://github.com/projectdiscovery/nuclei-templates/releases/latest/download/nuclei-templates.zip"
            tmp_zip = os.path.join(Config.TMP_PATH, "worker_nuclei_sync.zip")
            for m in mirrors:
                try:
                    resp = requests.get(f"{m}{raw_url}", stream=True, timeout=30, verify=False)
                    if resp.status_code == 200:
                        with open(tmp_zip, "wb") as f:
                            for chunk in resp.iter_content(chunk_size=128 * 1024):
                                if chunk:
                                    f.write(chunk)
                        extract_templates_zip_to_dir(tmp_zip, target_dir)
                        if target_version:
                            update_templates_config_version(target_version)
                        if os.path.exists(tmp_zip):
                            os.unlink(tmp_zip)
                        break
                except Exception as ex:
                    logger.warning(f"Worker mirror sync attempt {m} failed: {ex}")
        load_community_index(force_refresh=True)
        logger.info("Worker nuclei_template_sync_task completed successfully.")
    except Exception as e:
        logger.error(f"Worker nuclei_template_sync_task failed: {e}")


def sigterm_handler(signum, frame):
    if not current_task:
        return
    celery_id = current_task.request.id
    routing_key = current_task.request.delivery_info['routing_key']
    logger.info(f"Caught signal {signum}, celery_id:{celery_id} terminating {routing_key}...")

    logger.info(f"{current_task.request}")
    # Removed writing TaskStatus.STOP to database so that interrupted tasks remain RUNNING
    # and can be automatically resumed/re-executed when RabbitMQ requeues them.

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
    # 这里监控任务 task_id 和 target 是空的
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
            # 校验任务是否已被人工主动停止或已结束
            item = utils.conn_db('task').find_one({"_id": ObjectId(task_id)})
            if not item:
                item = utils.conn_db('github_task').find_one({"_id": ObjectId(task_id)})
                
            if item and item.get("status") in [TaskStatus.STOP, TaskStatus.ERROR, TaskStatus.DONE]:
                # 允许在任务完成后执行的后续操作（如同步资产、更新资产）
                allow_after_done = [
                    CeleryAction.DOMAIN_TASK_SYNC_TASK,
                    CeleryAction.ASSET_SITE_UPDATE,
                    CeleryAction.ASSET_WIH_UPDATE,
                    CeleryAction.ADD_ASSET_SITE_TASK
                ]
                if action not in allow_after_done:
                    logger.info(f"Task {task_id} has been stopped or ended manually, skip execution")
                    return
            # 如果任务被系统中断后重试，清除上次产生的残余数据
            if action in [CeleryAction.DOMAIN_TASK, CeleryAction.IP_TASK, CeleryAction.RUN_RISK_CRUISING, CeleryAction.FOFA_TASK]:
                utils.clean_task_data(task_id)
        except Exception as e:
            logger.error(f"Error checking or cleaning task {task_id}: {e}")

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




def domain_exec(options):
    """域名监测任务"""
    scope_id = options.get("scope_id")
    domain = options.get("domain")
    scheduler_id = options.get("scheduler_id")
    monitor_options = options.get("monitor_options")
    name = options.get("name")
    task_id = options.get("task_id")
    wrap_tasks.domain_executors(base_domain=domain, scheduler_id=scheduler_id,
                                scope_id=scope_id, options=monitor_options, name=name, task_id=task_id)


def oneshot_domain_exec(options):
    """一次性域名监测任务"""
    scope_id = options.get("scope_id")
    domain = options.get("domain")
    monitor_options = options.get("monitor_options")
    name = options.get("name")
    task_id = options.get("task_id")
    wrap_tasks.oneshot_domain_executors(base_domain=domain, scope_id=scope_id, options=monitor_options, name=name, task_id=task_id)


def domain_task_sync(options):
    """同步域名或 IP 任务的已有资产结果。"""
    from app.services.task_scope_sync import sync_task_to_scope
    sync_task_to_scope(options.get("task_id"), options.get("scope_id"))


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
    """
    IP 监测任务
    """
    scope_id = options.get("scope_id")
    target = options.get("domain")
    scheduler_id = options.get("scheduler_id")
    monitor_options = options.get("monitor_options")
    name = options.get("name")
    task_id = options.get("task_id")
    wrap_tasks.ip_executor(target=target, scope_id=scope_id,
                           task_name=name, scheduler_id=scheduler_id,
                           options=monitor_options, task_id=task_id)

def oneshot_ip_exec(options):
    """
    一次性 IP 监测任务
    """
    scope_id = options.get("scope_id")
    target = options.get("domain") # Payload uses 'domain' for IP target as well
    monitor_options = options.get("monitor_options")
    name = options.get("name")
    task_id = options.get("task_id")
    wrap_tasks.oneshot_ip_executors(target=target, scope_id=scope_id,
                                    task_name=name, options=monitor_options, task_id=task_id)


def github_task_task(options):
    task_id = options["task_id"]
    keyword = options["keyword"]
    wrap_tasks.github_task_task(task_id=task_id, keyword=keyword)


def github_task_monitor(options):
    task_id = options["task_id"]
    keyword = options["keyword"]
    scheduler_id = options["github_scheduler_id"]
    wrap_tasks.github_task_monitor(task_id=task_id, keyword=keyword, scheduler_id=scheduler_id)


def asset_site_update(options):
    task_id = options["task_id"]
    task_options = options["options"]
    scope_id = task_options["scope_id"]
    scheduler_id = task_options["scheduler_id"]
    wrap_tasks.asset_site_update_task(task_id=task_id,
                                      scope_id=scope_id, scheduler_id=scheduler_id)


def asset_wih_update_task(options):
    task_id = options["task_id"]
    task_options = options["options"]
    scope_id = task_options["scope_id"]
    scheduler_id = task_options["scheduler_id"]
    wrap_tasks.asset_wih_update_task(task_id=task_id,
                                     scope_id=scope_id, scheduler_id=scheduler_id)


def asset_site_add_task(options):
    task_id = options["task_id"]
    wrap_tasks.run_add_asset_site_task(task_id)


def github_threat_cve_task(options):
    from app.tasks.github_threat_monitor import run_threat_task_worker
    run_threat_task_worker("cve")


def github_threat_tools_task(options):
    from app.tasks.github_threat_monitor import run_threat_task_worker
    run_threat_task_worker("tools")


def github_threat_hackers_task(options):
    from app.tasks.github_threat_monitor import run_threat_task_worker
    run_threat_task_worker("hackers")
