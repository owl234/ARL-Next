import datetime
import sys
from bson import ObjectId
from bson.errors import InvalidId
from pymongo import UpdateOne
from pymongo.errors import PyMongoError
from app.utils import conn_db as conn, curr_date
from app import utils
import time
from app.modules import CeleryAction, SchedulerStatus, AssetScopeType, TaskStatus, CeleryRoutingKey, TaskTag
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
    return create_scheduler_job("资产组 WIH 更新", scope_id, interval, "wih_update_monitor", name)


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

    # 预建 WAITING 任务工单，保证排队可见与全生命周期追踪
    merged_options = monitor_options.copy()
    merged_options.update({
        "scope_id": scope_id,
        "scheduler_id": scheduler_id
    })
    task_record = {
        "name": name,
        "target": domain,
        "start_time": "-",
        "status": TaskStatus.WAITING,
        "type": scope_type,
        "task_tag": TaskTag.MONITOR,
        "end_time": "-",
        "service": [],
        "options": merged_options,
        "scope_id": str(scope_id),
        "celery_id": ""
    }
    insert_res = conn('task').insert_one(task_record)
    task_id = str(insert_res.inserted_id)

    task_data = {
        "domain": domain,
        "scope_id": scope_id,
        "scheduler_id": scheduler_id,
        "type": scope_type,
        "monitor_options": monitor_options,
        "name": name,
        "task_id": task_id
    }

    try:
        if scope_type == AssetScopeType.DOMAIN:
            task_options = {
                "celery_action": CeleryAction.DOMAIN_EXEC_TASK,
                "data": task_data
            }
            celery_id = celerytask.arl_task.apply_async(kwargs={'options': task_options}, queue=CeleryRoutingKey.ASSET_TASK_HEAVY)
            conn('task').update_one({"_id": ObjectId(task_id)}, {"$set": {"celery_id": str(celery_id)}})
            logger.info("submit domain job {} {} {} task_id={}".format(celery_id, domain, scope_id, task_id))

        if scope_type == AssetScopeType.IP:
            task_options = {
                "celery_action": CeleryAction.IP_EXEC_TASK,
                "data": task_data
            }
            celery_id = celerytask.arl_task.apply_async(kwargs={'options': task_options}, queue=CeleryRoutingKey.ASSET_TASK_HEAVY)
            conn('task').update_one({"_id": ObjectId(task_id)}, {"$set": {"celery_id": str(celery_id)}})
            logger.info("submit ip job {} {} {} task_id={}".format(celery_id, domain, scope_id, task_id))
    except Exception:
        conn('task').delete_one({"_id": ObjectId(task_id)})
        raise


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

from app import celerytask

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
            scope_id_str = str(item.get("scope_id", ""))

            # 关口 2：查验关联资产组有效性与监控目标包含关系 (自愈与盲派发阻断 - Issue #48 加固)
            try:
                scope_obj = conn('asset_scope').find_one({"_id": ObjectId(scope_id_str)})
            except InvalidId:
                logger.warning(f"Invalid scope_id '{scope_id_str}' in scheduler {scheduler_id_str}. Auto-deleting orphan scheduler.")
                conn('scheduler').delete_one({"_id": item["_id"]})
                continue
            except PyMongoError as ex:
                logger.error(f"MongoDB error checking scope {scope_id_str} for scheduler {scheduler_id_str}: {ex}. Skipping this run.")
                continue
            except Exception as ex:
                logger.error(f"Unexpected error checking scope {scope_id_str} for scheduler {scheduler_id_str}: {ex}. Skipping this run.")
                continue

            if not scope_obj:
                logger.warning(f"Orphan scheduler detected: scope_id '{scope_id_str}' not found in asset_scope. Auto-deleting scheduler {scheduler_id_str}.")
                conn('scheduler').delete_one({"_id": item["_id"]})
                continue

            scope_type = item.get("scope_type") or AssetScopeType.DOMAIN
            valid_scopes = set(scope_obj.get("scope_array", []))
            target_str = item.get("domain", "")

            if scope_type == AssetScopeType.IP and " " in target_str:
                valid_targets = [t for t in target_str.split() if t in valid_scopes]
                if not valid_targets:
                    logger.warning(f"Orphan composite IP scheduler: all targets in '{target_str}' removed from scope {scope_id_str}. Auto-deleting scheduler {scheduler_id_str}.")
                    conn('scheduler').delete_one({"_id": item["_id"]})
                    continue
                item["domain"] = " ".join(valid_targets)
            elif target_str:
                if target_str not in valid_scopes:
                    logger.warning(f"Orphan scheduler detected: target '{target_str}' no longer in scope {scope_id_str}. Auto-deleting scheduler {scheduler_id_str}.")
                    conn('scheduler').delete_one({"_id": item["_id"]})
                    continue

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

            strategy = DISPATCH_MAP.get(scope_type)

            if not strategy:
                logger.error(f"Unknown scope type: {scope_type}")
                continue

            if "func" in strategy:
                strategy["func"](scope_id=item["scope_id"], name=item.get("name", ""), scheduler_id=scheduler_id_str)
            else:
                # 预建 WAITING 任务工单，保证排队可见与全生命周期追踪
                merged_options = (item.get("monitor_options") or {}).copy()
                merged_options.update({
                    "scope_id": item["scope_id"],
                    "scheduler_id": scheduler_id_str
                })
                task_record = {
                    "name": item.get("name", ""),
                    "target": item["domain"],
                    "start_time": "-",
                    "status": TaskStatus.WAITING,
                    "type": scope_type,
                    "task_tag": TaskTag.MONITOR,
                    "end_time": "-",
                    "service": [],
                    "options": merged_options,
                    "scope_id": scope_id_str,
                    "celery_id": ""
                }
                insert_res = conn('task').insert_one(task_record)
                task_id = str(insert_res.inserted_id)

                task_data = {
                    "domain": item["domain"],
                    "scope_id": item["scope_id"],
                    "scheduler_id": scheduler_id_str,
                    "type": scope_type,
                    "monitor_options": item.get("monitor_options", {}),
                    "name": item.get("name", ""),
                    "task_id": task_id
                }
                task_options = {
                    "celery_action": strategy["action"],
                    "data": task_data
                }
                try:
                    celery_id = celerytask.arl_task.apply_async(kwargs={'options': task_options}, queue=strategy["queue"])
                    conn('task').update_one({"_id": ObjectId(task_id)}, {"$set": {"celery_id": str(celery_id)}})
                    logger.info(f"submit {scope_type} job {celery_id} {item['domain']} {item['scope_id']} task_id={task_id}")
                except Exception:
                    conn('task').delete_one({"_id": ObjectId(task_id)})
                    raise

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


def _parse_task_timestamp(val):
    if not val or val == "-":
        return None
    if isinstance(val, (int, float)):
        return float(val)
    if isinstance(val, datetime.datetime):
        if val.tzinfo is not None:
            return val.timestamp()
        return val.timestamp()
    if isinstance(val, str):
        try:
            struct = time.strptime(val, "%Y-%m-%d %H:%M:%S")
            return time.mktime(struct)
        except Exception:
            pass
        try:
            from app.utils.time import date2time
            return date2time(val)
        except Exception:
            pass
        try:
            return utils.parse_datetime(val).timestamp()
        except Exception:
            pass
    return None


def _get_task_latest_activity(task):
    """
    获取任务最近活跃时间戳，按 update_date、update_time、last_updated、start_time 及 _id 生成时间依次探测
    """
    ts_candidates = []
    for field in ["update_date", "update_time", "last_updated", "start_time"]:
        val = task.get(field)
        ts = _parse_task_timestamp(val)
        if ts is not None:
            ts_candidates.append(ts)

    # 兜底：若以上字段均无有效时间，检查 ObjectId 自带的生成时间
    obj_id = task.get("_id")
    if hasattr(obj_id, "generation_time"):
        try:
            ts_candidates.append(obj_id.generation_time.timestamp())
        except Exception:
            pass

    if ts_candidates:
        return max(ts_candidates)
    return None


def icp_auto_group_scheduler():
    """
    企业全景测绘「自动纳管建组」后台消费器

    背景：该流程原先由前端浏览器页面轮询驱动，关闭或离开页面即暂停追踪，
    导致主成功路径与前台进程强绑定。此处改为后端统一消费，页面仅负责展示。

    消费条件：icp_task 中 status=done 且 auto_group=true 且尚未被消费的任务。
    通过 auto_group_claimed 标记做原子领取，规避多实例并发重复建组。
    """
    query = {
        "status": TaskStatus.DONE,
        "auto_group": True,
        "$or": [
            {"auto_group_claimed": {"$exists": False}},
            {"auto_group_claimed": False}
        ]
    }

    claimed = []
    for item in conn('icp_task').find(query).limit(20):
        # 原子领取：仅当仍未领取时才置位，避免并发重复消费
        res = conn('icp_task').update_one(
            {"_id": item["_id"],
             "$or": [{"auto_group_claimed": {"$exists": False}},
                     {"auto_group_claimed": False}]},
            {"$set": {"auto_group_claimed": True, "auto_group_claim_time": utils.curr_date()}}
        )
        if res.modified_count == 1:
            claimed.append(item)

    for item in claimed:
        task_id = str(item["_id"])
        try:
            process_icp_auto_group(item, task_id)
        except Exception as e:
            logger.exception(f"Failed to auto-group icp task {task_id}: {e}")
            conn('icp_task').update_one(
                {"_id": item["_id"]},
                {"$set": {"auto_group_result": "error", "auto_group_msg": str(e)[:500]}}
            )

    return len(claimed)


def process_icp_auto_group(task, task_id):
    """对单个已完成的企业测绘任务执行自动建组与资产入库"""
    from app.routes.icp import build_auto_group_payload, perform_icp_sync

    domains = []
    for asset in conn('icp_asset').find({"task_id": task_id, "query_type": "web"}):
        d = asset.get('domain') or asset.get('ym')
        if d and isinstance(d, str):
            domains.append(d.strip().lower())
    domains = sorted(set(domains))

    if not domains:
        logger.info(f"Auto-group skipped for {task_id}: no web domains found")
        conn('icp_task').update_one(
            {"_id": task["_id"]},
            {"$set": {"auto_group_result": "no_domain",
                      "auto_group_msg": "未发现可纳管的网站域名"}}
        )
        return

    payload = build_auto_group_payload(task, domains)
    ok, err_code, result = perform_icp_sync(task_id, payload)

    conn('icp_task').update_one(
        {"_id": task["_id"]},
        {"$set": {
            "auto_group_result": "success" if ok else "error",
            "auto_group_msg": result.get("msg") or result.get("error", ""),
            "auto_group_domain_count": len(domains),
            "auto_group_scope_id": result.get("scope_id") or "",
            "auto_group_time": utils.curr_date()
        }}
    )
    logger.info(f"Auto-group finished for {task_id}: {len(domains)} domains, ok={ok}")


def cleanup_zombie_tasks(window_seconds=1800):
    """
    🛡️【系统韧性与活性双重探测】清理因系统异常重启或中断的真正僵尸任务
    1. Celery 活性探测：活跃任务绝对不收敛；
    2. 实例代际与确定失联快收敛：若记录的 Worker 实例已重启更换 boot_id，或目标节点存活响应 Inspect 但未持有该 celery_id，无需等待 30 分钟直接收敛；
    3. 心跳安全时间窗：当 Worker 失联/无响应 Inspect 时，若在 window_seconds (默认30分钟) 内有活跃心跳/启动时间，防御误杀；
    4. 监控任务保留审计：严禁物理删除，标记为 TaskStatus.ERROR 并保留 end_reason，平滑延后调度。
    """
    non_running_statuses = [TaskStatus.DONE, TaskStatus.WAITING, TaskStatus.ERROR, TaskStatus.STOP]
    zombie_tasks = list(conn('task').find({"status": {"$nin": non_running_statuses}}))
    if not zombie_tasks:
        return 0

    # 1. Celery 活性双重探测：获取存活 Worker 与正在执行的任务集合
    active_celery_ids = set()
    responding_workers = set()
    try:
        from app.celerytask import celery as celery_app
        inspector = celery_app.control.inspect(timeout=5.0)
        active_map = inspector.active() if inspector else None
        if isinstance(active_map, dict):
            for worker_name, tasks in active_map.items():
                if isinstance(tasks, list):
                    responding_workers.add(str(worker_name))
                    for t in tasks:
                        if isinstance(t, dict) and t.get("id"):
                            active_celery_ids.add(str(t["id"]))
        logger.info(
            f"Celery inspect found {len(active_celery_ids)} active tasks across {len(responding_workers)} responding workers"
        )
    except Exception as e:
        logger.warning(f"Failed to inspect celery active tasks: {e}")

    # 2. 读取各 Worker 实例最新启动代际 (boot_id)，实现重启快速感知
    worker_boot_map = {}
    try:
        wi_col = conn('worker_instances')
        if wi_col and hasattr(wi_col, 'find'):
            for wdoc in wi_col.find({}):
                if isinstance(wdoc, dict) and wdoc.get("worker_node") and wdoc.get("boot_id"):
                    worker_boot_map[str(wdoc["worker_node"])] = str(wdoc["boot_id"])
    except Exception as we:
        logger.debug(f"Failed to query worker_instances: {we}")

    now = time.time()
    converged_count = 0

    for task in zombie_tasks:
        task_id = str(task["_id"])
        celery_id = str(task.get("celery_id", ""))

        # a. 若任务的 celery_id 仍处于活跃任务队列中，严禁收敛，直接跳过并打 info 日志
        if celery_id and celery_id in active_celery_ids:
            logger.info(f"Task {task_id} (celery_id: {celery_id}) is actively executing in Celery, skipping convergence.")
            continue

        latest_act = _get_task_latest_activity(task)
        worker_node = str(task.get("worker_node", "") or "")
        task_boot_id = str(task.get("worker_boot_id", "") or "")

        worker_rebooted = bool(
            worker_node
            and task_boot_id
            and worker_node in worker_boot_map
            and worker_boot_map[worker_node] != task_boot_id
        )
        worker_confirmed_absent = bool(
            worker_node
            and worker_node in responding_workers
            and celery_id
            and celery_id != "celery_id_placeholder"
        )

        # b. 未确认节点重启且未收到该节点在线确认时，保留 30 分钟心跳安全时间窗，防御 Inspect 瞬时超时
        if not (worker_rebooted or worker_confirmed_absent):
            if latest_act is not None and (now - latest_act) < window_seconds:
                logger.info(
                    f"Task {task_id} (celery_id: {celery_id}) was active {now - latest_act:.1f}s ago "
                    f"(within {window_seconds}s heartbeat window), skipping convergence."
                )
                continue

        # 收敛前二次回查数据库，防止在 Inspect 期间任务刚好正常完成引起的竞态覆写
        try:
            fresh_doc = conn('task').find_one({"_id": task["_id"]})
            if isinstance(fresh_doc, dict) and fresh_doc.get("status") in non_running_statuses:
                logger.info(
                    f"Task {task_id} already transitioned to {fresh_doc.get('status')} before convergence, skipping."
                )
                continue
        except Exception:
            pass

        if worker_rebooted:
            fast_tag = "worker_rebooted"
            converge_error_msg = f"检测到执行节点 {worker_node} 已重启（代际变更），原任务进程丢失，已快速收敛"
        elif worker_confirmed_absent:
            fast_tag = "worker_confirmed_absent"
            converge_error_msg = f"执行节点 {worker_node} 在线核验未持有该任务进程 (celery_id={celery_id})，已快速收敛"
        else:
            fast_tag = "heartbeat_timeout"
            converge_error_msg = f"任务心跳超时失联且 Inspect 未检测到活跃执行，已由看门狗自动收敛"

        # 确认为真正失活的僵尸任务，执行收敛
        logger.warning(
            f"Converging confirmed zombie task ({fast_tag}): {task_id}, status: {task.get('status')}, "
            f"celery_id: {celery_id}, elapsed since activity: {now - (latest_act or 0):.1f}s"
        )

        # 仅物理清理该任务在磁盘上的临时文件与截图，严禁删除 MongoDB 13 维已入库资产
        try:
            utils.clean_task_tmp_files(task_id)
        except Exception as e:
            logger.warning(f"Failed to clean temporary disk files for zombie task {task_id}: {e}")

        # 立即释放该任务可能残留占用的高发包互斥槽位
        try:
            from app.utils.packet_lease import release_task_packet_slots
            release_task_packet_slots(task_id, collection=conn('packet_phase_lease'))
        except Exception:
            pass

        curr_date = utils.curr_date()
        is_monitor = (task.get("task_tag") == "monitor")

        # c. 监控任务与普通任务安全收敛与保留审计：严禁调用 conn('task').delete_one！
        conn('task').update_one(
            {"_id": task["_id"]},
            {"$set": {
                "status": TaskStatus.ERROR,
                "end_time": curr_date,
                "end_reason": "服务重启/异常中断",
                "error_msg": converge_error_msg
            }}
        )

        try:
            syslog_col = conn('syslog')
            if hasattr(syslog_col, 'insert_one'):
                syslog_col.insert_one({
                    "task_id": task_id,
                    "message": (
                        f"【⚠️ 异常收敛 ({fast_tag})】{converge_error_msg}（最后记录阶段: {task.get('status')}），"
                        f"已由系统看门狗自动收敛为 ERROR 终止态。"
                    ),
                    "level": "ERROR",
                    "time": curr_date,
                    "timestamp": int(time.time())
                })
        except Exception as log_ex:
            logger.warning(f"Failed to write zombie convergence syslog for task {task_id}: {log_ex}")

        if is_monitor:
            options = task.get("options", {})
            scheduler_id = options.get("scheduler_id")
            if scheduler_id:
                logger.info(f"Re-scheduling monitor job: {scheduler_id} next_run_time in 60s")
                try:
                    conn('scheduler').update_one(
                        {"_id": ObjectId(scheduler_id)},
                        {"$set": {"next_run_time": int(time.time()) + 60}}
                    )
                except Exception as e:
                    logger.error(f"Failed to reschedule monitor job {scheduler_id}: {e}")

        converged_count += 1

    if converged_count > 0:
        logger.info(f"Successfully converged {converged_count} zombie tasks to ERROR.")

    return converged_count
        
def reconcile_worker_concurrency():
    """
    巡检并自动对齐 Celery Worker 运行时进程池与数据库中保存的目标并发配置：
    - 当运行进程数低于目标配置时，执行 pool_grow 扩容；
    - 当运行进程数高于目标配置（例如用户保存缩容时有任务占用导致暂缓），仅在该节点当前无活跃任务时执行 pool_shrink 空闲缩容。
    """
    try:
        from app.utils.performance_config import get_performance_config
        from app.celerytask import celery as celery_app
    except Exception:
        return 0

    try:
        cfg = get_performance_config()
    except Exception as e:
        logger.debug(f"reconcile_worker_concurrency failed to read config: {e}")
        return 0

    try:
        inspector = celery_app.control.inspect(timeout=1.5)
        stats = inspector.stats() if inspector else None
        if not isinstance(stats, dict) or not stats:
            return 0
        active_map = inspector.active() or {}
    except Exception as e:
        logger.debug(f"reconcile_worker_concurrency inspect failed: {e}")
        return 0

    queue_targets = [
        ("arltask_heavy", max(1, int(cfg.get("celery_heavy_concurrency", 1)))),
        ("arltask_light", max(1, int(cfg.get("celery_light_concurrency", 1)))),
        ("arlgithub", max(1, int(cfg.get("github_concurrency", 1)))),
    ]

    adjusted = 0
    for node, node_stats in stats.items():
        if not isinstance(node_stats, dict):
            continue
        pool = node_stats.get("pool")
        processes = pool.get("processes") if isinstance(pool, dict) else None
        if not isinstance(processes, list):
            continue
        current = len(processes)

        desired = None
        for key, val in queue_targets:
            if key in str(node):
                desired = val
                break
        if desired is None or current == desired:
            continue

        diff = desired - current
        if diff > 0:
            try:
                celery_app.control.pool_grow(n=diff, destination=[node], reply=True, timeout=1.5)
                logger.info(f"reconcile_worker_concurrency: grew {node} from {current} to {desired}")
                adjusted += 1
            except Exception as e:
                logger.warning(f"reconcile_worker_concurrency: pool_grow failed on {node}: {e}")
        else:
            node_active = active_map.get(node) if isinstance(active_map, dict) else None
            if isinstance(node_active, list) and len(node_active) == 0:
                try:
                    celery_app.control.pool_shrink(n=abs(diff), destination=[node], reply=True, timeout=1.5)
                    logger.info(f"reconcile_worker_concurrency: shrank idle {node} from {current} toward {desired}")
                    adjusted += 1
                except Exception as e:
                    logger.warning(f"reconcile_worker_concurrency: pool_shrink failed on {node}: {e}")
            else:
                logger.debug(
                    f"reconcile_worker_concurrency: deferring shrink on busy node {node} "
                    f"(runtime={current}, target={desired})"
                )

    return adjusted


def cleanup_orphan_tmp_files(max_age_seconds=604800):
    """
    清理 TMP_PATH 目录下的孤儿临时文件（如强行终止任务遗留的 wih、nuclei、massdns 等中间文件）
    默认清理修改时间超过 7 天 (604800秒) 的临时文件，白名单排除系统配置文件，充分护航 2-3 天超长扫描任务
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
    from app.tasks.github_threat_monitor import threat_intelligence_scheduler
    logger.info("start scheduler server ")
    
    # 启动时先清理僵尸任务并恢复
    cleanup_zombie_tasks()
    # 启动时清理孤儿临时文件
    cleanup_orphan_tmp_files()
    
    last_tmp_clean = time.time()
    last_zombie_clean = time.time()

    while True:
        # Threat Intelligence (CVE/Tools/Hackers) 异步解耦任务调度
        threat_intelligence_scheduler()

        # 资产监控任务调度
        asset_monitor_scheduler()

        # Github 监控任务调度
        github_task_scheduler()

        # 计划任务调度
        task_schedule.task_scheduler()

        # 企业全景测绘自动纳管建组（原前端轮询职责下沉至后端）
        icp_auto_group_scheduler()

        # Worker 运行时并发与配置目标空闲对齐（弥补任务执行中缩容暂缓的场景）
        try:
            reconcile_worker_concurrency()
        except Exception as rec_err:
            logger.debug(f"reconcile_worker_concurrency tick error: {rec_err}")

        # 每小时自动巡检并清理一次孤儿临时文件
        curr_time = time.time()
        if curr_time - last_tmp_clean > 3600:
            cleanup_orphan_tmp_files()
            last_tmp_clean = curr_time

        # 每 10 分钟 (600秒) 周期性巡检并收敛因 Worker 异常崩溃遗留的僵尸任务
        if curr_time - last_zombie_clean > 600:
            cleanup_zombie_tasks(window_seconds=1800)
            last_zombie_clean = curr_time

        # logger.debug(time.time())
        # sleep 时间不能超过60S，Github 里的任务可能运行不了。
        time.sleep(58)



if __name__ == '__main__':
    run_forever()
