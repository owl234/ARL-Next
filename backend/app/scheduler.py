import sys
from bson import ObjectId
from pymongo import UpdateOne
from app.utils import conn_db as conn
from app import utils
from app import celerytask
import time
from app.modules import CeleryAction, SchedulerStatus, AssetScopeType, TaskStatus, CeleryRoutingKey
from app.helpers import task_schedule, asset_site_monitor, asset_wih_monitor

logger = utils.get_logger()

domain_monitor_options = {
    'domain_brute': True,
    'domain_brute_type': 'big',
    'alt_dns': False,
    'arl_search': True,
    'port_scan_type': 'test',
    'port_scan': True,
    'dns_query_plugin': True,
    'site_identify': False
}

ip_monitor_options = {
    'port_scan_type': 'test',
    'port_scan': True,
    'site_identify': False
}


def create_scheduler_job(domain, scope_id, interval, scope_type, name="", custom_options=None):
    logger.info("add {} job {} {} {}".format(scope_type, interval, domain, scope_id))
    current_time = int(time.time()) + 30
    
    if custom_options is None:
        if scope_type == AssetScopeType.DOMAIN:
            custom_options = domain_monitor_options.copy()
        elif scope_type == AssetScopeType.IP:
            custom_options = ip_monitor_options.copy()
        else:
            custom_options = {}

    if scope_type == AssetScopeType.IP:
        custom_options.update({
            "domain_brute": False,
            "alt_dns": False,
            "dns_query_plugin": False,
            "arl_search": False
        })

    item = {
        "domain": domain,
        "scope_id": scope_id,
        "interval": interval,
        "next_run_time": current_time,
        "next_run_date": utils.time2date(current_time),
        "last_run_time": 0,
        "last_run_date": "-",
        "run_number": 0,
        "status": SchedulerStatus.RUNNING,
        "monitor_options": custom_options,
        "name": name,
        "scope_type": scope_type
    }
    conn('scheduler').insert_one(item)
    return str(item["_id"])

def add_scheduler(domain, scope_id, options=None, interval=60 * 1, name="", scope_type=AssetScopeType.DOMAIN):
    return create_scheduler_job(domain, scope_id, interval, scope_type, name, options)

def add_asset_site_monitor_job(scope_id, name, interval=60 * 1):
    return create_scheduler_job("资产站点更新", scope_id, interval, "site_update_monitor", name)

def add_asset_wih_monitor_job(scope_id, name, interval=60 * 1):
    return create_scheduler_job("资产分组 WIH 更新", scope_id, interval, "wih_update_monitor", name)


def delete_scheduler(scheduler_id):
    ret = conn("scheduler").delete_one({"_id": ObjectId(scheduler_id)})
    return ret


def stop_scheduler(scheduler_id):
    item = find_scheduler(scheduler_id)
    item["next_run_date"] = "-"
    item["next_run_time"] = sys.maxsize
    item["status"] = SchedulerStatus.STOP
    query = {"_id": ObjectId(scheduler_id)}
    ret = conn('scheduler').find_one_and_replace(query, item)
    return ret


def recover_scheduler(scheduler_id):
    current_time = int(time.time()) + 30
    item = find_scheduler(scheduler_id)

    next_run_time = current_time + item["interval"]
    item["next_run_date"] = utils.time2date(next_run_time)
    item["next_run_time"] = next_run_time
    item["status"] = SchedulerStatus.RUNNING
    query = {"_id": ObjectId(scheduler_id)}
    ret = conn('scheduler').find_one_and_replace(query, item)
    return ret


def run_scheduler(scheduler_id):
    item = find_scheduler(scheduler_id)
    if not item:
        return False

    if item.get("status") == SchedulerStatus.STOP:
        recover_scheduler(scheduler_id)
        item = find_scheduler(scheduler_id)

    domain = item["domain"]
    scope_id = item["scope_id"]
    options = item["monitor_options"]
    name = item["name"]
    scope_type = item.get("scope_type")

    if not scope_type:
        scope_type = AssetScopeType.DOMAIN

    if scope_type == "site_update_monitor":
        asset_site_monitor.submit_asset_site_monitor_job(scope_id=scope_id,
                                                         name=name,
                                                         scheduler_id=str(item["_id"]))

    elif scope_type == "wih_update_monitor":
        asset_wih_monitor.submit_asset_wih_monitor_job(scope_id=scope_id,
                                                       name=name,
                                                       scheduler_id=str(item["_id"]))

    else:
        submit_scheduler(domain=domain, scheduler_id=str(item["_id"]),
                   scope_id=scope_id, options=options,
                   name=name, scope_type=scope_type)

    return True


def find_scheduler(scheduler_id):
    query = {"_id": ObjectId(scheduler_id)}
    item = conn('scheduler').find_one(query)
    return item


def all_scheduler():
    items = []
    for item in conn('scheduler').find():
        items.append(item)
    return items


def submit_scheduler(domain, scheduler_id, scope_id, options=None, name="", scope_type=AssetScopeType.DOMAIN):
    monitor_options = domain_monitor_options.copy()
    if scope_type == AssetScopeType.IP:
        monitor_options = ip_monitor_options.copy()

    if options is None:
        options = {}

    monitor_options.update(options)

    task_data = {
        "domain": domain,
        "scope_id": scope_id,
        "scheduler_id": scheduler_id,
        "type": scope_type,
        "monitor_options": monitor_options,
        "name": name
    }

    if scope_type == AssetScopeType.DOMAIN:
        task_options = {
            "celery_action": CeleryAction.DOMAIN_EXEC_TASK,
            "data": task_data
        }
        celery_id = celerytask.arl_task.apply_async(kwargs={'options': task_options}, queue=CeleryRoutingKey.ASSET_TASK_HEAVY)
        logger.info("submit domain job {} {} {}".format(celery_id, domain, scope_id))

    if scope_type == AssetScopeType.IP:
        task_options = {
            "celery_action": CeleryAction.IP_EXEC_TASK,
            "data": task_data
        }
        celery_id = celerytask.arl_task.apply_async(kwargs={'options': task_options}, queue=CeleryRoutingKey.ASSET_TASK_HEAVY)
        logger.info("submit ip job {} {} {}".format(celery_id, domain, scope_id))


def update_scheduler_run(scheduler_id):
    curr_time = int(time.time())
    item = find_scheduler(scheduler_id)
    if not item:
        return
    item["next_run_time"] = curr_time + item["interval"]
    item["next_run_date"] = utils.time2date(item["next_run_time"])
    item["last_run_time"] = curr_time
    item["last_run_date"] = utils.time2date(curr_time)
    item["run_number"] += 1
    query = {"_id": item["_id"]}
    conn('scheduler').find_one_and_replace(query, item)


DISPATCH_MAP = {
    AssetScopeType.DOMAIN: {
        "action": CeleryAction.DOMAIN_EXEC_TASK,
        "queue": CeleryRoutingKey.ASSET_TASK_HEAVY
    },
    AssetScopeType.IP: {
        "action": CeleryAction.IP_EXEC_TASK,
        "queue": CeleryRoutingKey.ASSET_TASK_HEAVY
    },
    "site_update_monitor": {
        "func": asset_site_monitor.submit_asset_site_monitor_job
    },
    "wih_update_monitor": {
        "func": asset_wih_monitor.submit_asset_wih_monitor_job
    }
}

def asset_monitor_scheduler():
    curr_time = int(time.time())
    query = {
        "status": SchedulerStatus.RUNNING,
        "next_run_time": {"$lte": curr_time}
    }
    due_tasks = conn('scheduler').find(query)
    bulk_updates = []

    for item in due_tasks:
        try:
            scheduler_id_str = str(item["_id"])
            running_tasks = conn('task').count_documents({
                "options.scheduler_id": scheduler_id_str,
                "status": {"$nin": [TaskStatus.DONE, TaskStatus.ERROR, TaskStatus.STOP]}
            })

            if running_tasks > 0:
                logger.info(f"Task overlap prevented: scheduler {scheduler_id_str} is already running. Skipping this round.")
                next_time = curr_time + item.get("interval", 3600)
                bulk_updates.append(UpdateOne(
                    {"_id": item["_id"]},
                    {"$set": {"next_run_time": next_time, "next_run_date": utils.time2date(next_time)}}
                ))
                continue

            scope_type = item.get("scope_type") or AssetScopeType.DOMAIN
            strategy = DISPATCH_MAP.get(scope_type)

            if not strategy:
                logger.error(f"Unknown scope type: {scope_type}")
                continue

            if "func" in strategy:
                strategy["func"](scope_id=item["scope_id"], name=item.get("name", ""), scheduler_id=scheduler_id_str)
            else:
                task_data = {
                    "domain": item["domain"],
                    "scope_id": item["scope_id"],
                    "scheduler_id": scheduler_id_str,
                    "type": scope_type,
                    "monitor_options": item.get("monitor_options", {}),
                    "name": item.get("name", "")
                }
                task_options = {
                    "celery_action": strategy["action"],
                    "data": task_data
                }
                celery_id = celerytask.arl_task.apply_async(kwargs={'options': task_options}, queue=strategy["queue"])
                logger.info(f"submit {scope_type} job {celery_id} {item['domain']} {item['scope_id']}")

            next_time = curr_time + item.get("interval", 3600)
            bulk_updates.append(UpdateOne(
                {"_id": item["_id"]},
                {"$set": {
                    "next_run_time": next_time,
                    "next_run_date": utils.time2date(next_time),
                    "last_run_time": curr_time,
                    "last_run_date": utils.time2date(curr_time)
                }, "$inc": {"run_number": 1}}
            ))

        except Exception as e:
            logger.exception(f"Scheduler dispatch error for {item.get('_id')}: {str(e)}")

    if bulk_updates:
        try:
            conn('scheduler').bulk_write(bulk_updates, ordered=False)
        except Exception as e:
            logger.error(f"Bulk write error in scheduler: {str(e)}")


def cleanup_zombie_tasks():
    non_running_statuses = [TaskStatus.DONE, TaskStatus.WAITING, TaskStatus.ERROR, TaskStatus.STOP]
    zombie_tasks = conn('task').find({"status": {"$nin": non_running_statuses}})
    count = 0
    
    for task in zombie_tasks:
        task_id = str(task["_id"])
        logger.info(f"Cleanup zombie task: {task_id}, status: {task.get('status')}")
        
        # 清理残余数据
        utils.clean_task_data(task_id)
        
        if task.get("task_tag") == "monitor":
            # 对于监控任务，删除残余记录
            conn('task').delete_one({"_id": task["_id"]})
            
            # 找到对应的 scheduler_id，将其 next_run_time 设置为当前时间
            options = task.get("options", {})
            scheduler_id = options.get("scheduler_id")
            if scheduler_id:
                logger.info(f"Re-scheduling monitor job: {scheduler_id}")
                conn('scheduler').update_one(
                    {"_id": ObjectId(scheduler_id)},
                    {"$set": {"next_run_time": int(time.time())}}
                )
        else:
            # 普通任务直接报错
            conn('task').update_one(
                {"_id": task["_id"]},
                {"$set": {
                    "status": TaskStatus.ERROR,
                    "end_time": utils.curr_date(),
                    "end_reason": "系统重启/升级中断 (Interrupted by system restart/update)"
                }}
            )
            
        count += 1
        
def cleanup_orphan_tmp_files(max_age_seconds=86400):
    """
    清理 TMP_PATH 目录下的孤儿临时文件（如强行终止任务遗留的 wih、nuclei、massdns 等中间文件）
    默认清理修改时间超过 24 小时 (86400秒) 的临时文件，白名单排除系统配置文件
    """
    import os
    import shutil
    from app.config import Config

    tmp_dir = Config.TMP_PATH
    if not os.path.exists(tmp_dir):
        return

    now = time.time()
    clean_count = 0
    preserved_files = {'github.hash', '.gitkeep', '.gitignore'}

    try:
        for fname in os.listdir(tmp_dir):
            if fname in preserved_files or fname.startswith('.'):
                continue

            fpath = os.path.join(tmp_dir, fname)
            try:
                if os.path.isfile(fpath) or os.path.islink(fpath):
                    mtime = os.path.getmtime(fpath)
                    if (now - mtime) > max_age_seconds:
                        os.unlink(fpath)
                        clean_count += 1
                elif os.path.isdir(fpath):
                    mtime = os.path.getmtime(fpath)
                    if (now - mtime) > max_age_seconds:
                        shutil.rmtree(fpath, ignore_errors=True)
                        clean_count += 1
            except Exception as fe:
                logger.warning(f"Failed to clean tmp file {fpath}: {fe}")
    except Exception as e:
        logger.error(f"Error scanning tmp_dir {tmp_dir}: {e}")

    if clean_count > 0:
        logger.info(f"Cleaned up {clean_count} orphan tmp files older than {max_age_seconds}s from {tmp_dir}.")


def run_forever():
    from app.utils.github_task import github_task_scheduler
    logger.info("start scheduler server ")
    
    # 启动时先清理僵尸任务并恢复
    cleanup_zombie_tasks()
    # 启动时清理孤儿临时文件
    cleanup_orphan_tmp_files()
    
    last_tmp_clean = time.time()

    while True:
        # Threat Intelligence (CVE/Tools/Hackers) 独立任务调度
        from app.tasks.github_threat_monitor import threat_intelligence_scheduler
        threat_intelligence_scheduler()

        # 资产监控任务调度
        asset_monitor_scheduler()

        # Github 监控任务调度
        github_task_scheduler()

        # 计划任务调度
        task_schedule.task_scheduler()

        # 每小时自动巡检并清理一次孤儿临时文件
        curr_time = time.time()
        if curr_time - last_tmp_clean > 3600:
            cleanup_orphan_tmp_files()
            last_tmp_clean = curr_time

        # logger.debug(time.time())
        # sleep 时间不能超过60S，Github 里的任务可能运行不了。
        time.sleep(58)


if __name__ == '__main__':
    run_forever()
