import signal
import time
from bson import ObjectId
from app.config import Config
from celery import Celery, platforms, current_task
from app import utils
from app import tasks as wrap_tasks
from app.modules import CeleryAction, TaskSyncStatus, TaskStatus, CeleryRoutingKey

logger = utils.get_logger()

celery = Celery('task', broker=Config.CELERY_BROKER_URL)

celery.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_transport_options={"max_retries": 3, "interval_start": 0, "interval_step": 0.2, "interval_max": 0.5},
)
platforms.C_FORCE_ROOT = True


@celery.task(queue=CeleryRoutingKey.ASSET_TASK)
def arl_task(options):
    # 这里不检验 celery_action， 调用的时候区分
    run_task(options)


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
    }
    start_time = time.time()
    # 这里监控任务 task_id 和 target 是空的
    logger.info("run_task action:{} time: {}".format(action, start_time))
    logger.info("name:{}, target:{}, task_id:{}".format(
        data.get("name"), data.get("target"), data.get("task_id")))
        
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


@celery.task(queue=CeleryRoutingKey.ASSET_TASK)
def icp_query_task(options):
    from app.tasks.icp import run_icp_task
    run_icp_task(options)


@celery.task(queue=CeleryRoutingKey.ASSET_TASK)
def tyc_query_task(options):
    from app.tasks.tyc import run_tyc_task
    run_tyc_task(options)



def domain_exec(options):
    """域名监测任务"""
    scope_id = options.get("scope_id")
    domain = options.get("domain")
    job_id = options.get("job_id")
    monitor_options = options.get("monitor_options")
    name = options.get("name")
    wrap_tasks.domain_executors(base_domain=domain, job_id=job_id,
                                scope_id=scope_id, options=monitor_options, name=name)


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
    """
    IP 监测任务
    """
    scope_id = options.get("scope_id")
    target = options.get("domain")
    job_id = options.get("job_id")
    monitor_options = options.get("monitor_options")
    name = options.get("name")
    wrap_tasks.ip_executor(target=target, scope_id=scope_id,
                           task_name=name, job_id=job_id,
                           options=monitor_options)


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
