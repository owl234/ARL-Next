import bson
from app import utils
from app.utils.ip import ip_in_scope
from app.utils.domain import is_in_scopes


def check_target_in_scope(target, scope_data):
    from .task import get_ip_domain_list
    ip_list, domain_list = get_ip_domain_list(target)

    domain_array = scope_data.get("domain_array")
    ip_array = scope_data.get("ip_array")
    
    if domain_array is None or ip_array is None:
        st = scope_data.get("scope_type", "domain")
        sa = scope_data.get("scope_array", [])
        domain_array = sa if st == "domain" else []
        ip_array = sa if st == "ip" else []

    for ip in ip_list:
        if not ip_in_scope(ip, ip_array):
            raise Exception("{}不在范围{}中".format(ip, ",".join(ip_array)))

    for domain in domain_list:
        if not is_in_scopes(domain, domain_array):
            raise Exception("{}不在范围{}中".format(domain, ",".join(domain_array)))

    return ip_list, domain_list


def get_scope_by_scope_id(scope_id):
    query = {
        "_id": bson.ObjectId(scope_id)
    }
    data = utils.conn_db("asset_scope").find_one(query)
    return data


def update_scope_domain_status(scope_id, domain, status, task_id=None):
    """
    更新资产分组中指定主域名的探测状态
    status: 'unprobed' | 'scanning' | 'probed' | 'error'
    """
    if not scope_id or not domain:
        return
    try:
        scope = utils.conn_db("asset_scope").find_one({"_id": bson.ObjectId(str(scope_id))})
        if not scope:
            return

        domain_status = scope.get("domain_status", {})
        if not isinstance(domain_status, dict):
            domain_status = {}

        target_info = domain_status.get(domain, {})
        if not isinstance(target_info, dict):
            target_info = {}

        target_info["status"] = status
        target_info["last_probe_time"] = utils.curr_date()
        if task_id:
            target_info["last_task_id"] = str(task_id)

        domain_status[domain] = target_info

        # 清理由于 MongoDB 点号路径误解析可能残留的嵌套脏 key (如 c4games -> com)
        if "." in domain:
            first_part = domain.split(".")[0]
            if first_part in domain_status and isinstance(domain_status[first_part], dict):
                domain_status.pop(first_part, None)

        utils.conn_db("asset_scope").update_one(
            {"_id": bson.ObjectId(str(scope_id))},
            {"$set": {"domain_status": domain_status}}
        )
    except Exception as e:
        utils.get_logger().error(f"update_scope_domain_status error: {e}")


def get_scope_domain_stat(scope_data, auto_persist=True):
    """
    计算并规整资产分组的范围项（域名/IP/网段）探测状态和统计覆盖度
    使用高效批量聚合与持久化回写，彻底杜绝 N+1 跨表查询与全表正则扫描
    """
    # 优先取 scope_array（覆盖域名、IP、网段全量范围项）
    scope_items = scope_data.get("scope_array")
    if scope_items is None:
        sa = []
        if scope_data.get("domain_array"):
            sa.extend(scope_data["domain_array"])
        if scope_data.get("ip_array"):
            sa.extend(scope_data["ip_array"])
        scope_items = sa or []

    domain_status = scope_data.get("domain_status")
    if not isinstance(domain_status, dict):
        domain_status = {}

    scope_id_str = str(scope_data.get("_id", ""))

    # 1. 实时检索处于运行中（非终态）的任务集合，确保真实执行中的目标标记为 scanning
    active_scanning_set = set()
    try:
        terminal_statuses = ["done", "error", "stop"]
        for doc in utils.conn_db("task").find(
            {
                "status": {"$nin": terminal_statuses},
                "$or": [
                    {"target": {"$in": scope_items}},
                    {"domain": {"$in": scope_items}}
                ]
            },
            {"target": 1, "domain": 1}
        ):
            if doc.get("target"):
                for tok in str(doc["target"]).split():
                    active_scanning_set.add(tok.strip())
            if doc.get("domain"):
                active_scanning_set.add(str(doc["domain"]).strip())
    except Exception as e:
        utils.get_logger().error(f"check active scanning tasks error: {e}")

    # 所有非活跃扫描的目标纳入全量一致性核验（高性能批量 $in 索引查询）
    items_to_check = [d for d in scope_items if d not in active_scanning_set]

    # 如果存在待核验项，进行批量聚合检测（一次性查询，杜绝 for 循环单条查询与正则 COLLSCAN）
    need_persist = False
    if items_to_check and scope_id_str:
        # 2. 预加载当前 scope_id 关联的所有已完成历史任务中的 target tokens（覆盖空格拼接的多目标与单目标）
        found_in_scope_tasks = set()
        try:
            for tsk in utils.conn_db("task").find(
                {
                    "$or": [
                        {"scope_id": scope_id_str},
                        {"options.scope_id": scope_id_str},
                        {"options.related_scope_id": scope_id_str}
                    ],
                    "status": "done"
                },
                {"target": 1, "domain": 1}
            ):
                tgt = tsk.get("target")
                if tgt and isinstance(tgt, str):
                    for tok in tgt.split():
                        found_in_scope_tasks.add(tok.strip())
                dom = tsk.get("domain")
                if dom and isinstance(dom, str):
                    found_in_scope_tasks.add(dom.strip())
        except Exception as e:
            utils.get_logger().error(f"check scope tasks error: {e}")

        # 分批处理防止超大列表 (e.g. > 500) 导致 $in 超过 BSON 限制
        chunk_size = 500
        for i in range(0, len(items_to_check), chunk_size):
            chunk = items_to_check[i:i + chunk_size]

            # 3. 批量检查 asset_domain 表
            found_domains = set()
            try:
                for doc in utils.conn_db("asset_domain").find(
                    {"scope_id": scope_id_str, "domain": {"$in": chunk}},
                    {"domain": 1}
                ):
                    if doc.get("domain"):
                        found_domains.add(doc["domain"])
            except Exception as e:
                utils.get_logger().error(f"check asset_domain batch error: {e}")

            # 4. 批量检查 asset_ip 表
            found_ips = set()
            try:
                for doc in utils.conn_db("asset_ip").find(
                    {"scope_id": scope_id_str, "ip": {"$in": chunk}},
                    {"ip": 1}
                ):
                    if doc.get("ip"):
                        found_ips.add(doc["ip"])
            except Exception as e:
                utils.get_logger().error(f"check asset_ip batch error: {e}")

            # 5. 对于不在当前 scope 下已有沉淀资产/任务的剩余项，批量检查全局 task 表
            remaining_for_task = [
                x for x in chunk 
                if x not in found_domains and x not in found_ips and x not in found_in_scope_tasks
            ]
            found_tasks = set()
            if remaining_for_task:
                try:
                    for doc in utils.conn_db("task").find(
                        {
                            "$or": [
                                {"target": {"$in": remaining_for_task}},
                                {"domain": {"$in": remaining_for_task}}
                            ],
                            "status": "done"
                        },
                        {"target": 1, "domain": 1}
                    ):
                        if doc.get("target"):
                            for tok in str(doc["target"]).split():
                                found_tasks.add(tok.strip())
                        if doc.get("domain"):
                            found_tasks.add(doc["domain"])
                except Exception as e:
                    utils.get_logger().error(f"check task batch error: {e}")

            # 6. 批量检查 scheduler 表（精准 $in 匹配）
            remaining_for_sch = [
                x for x in remaining_for_task if x not in found_tasks
            ]
            found_sch = set()
            if remaining_for_sch:
                try:
                    for doc in utils.conn_db("scheduler").find(
                        {
                            "scope_id": scope_id_str,
                            "domain": {"$in": remaining_for_sch},
                            "$or": [{"run_number": {"$gt": 0}}, {"last_run_time": {"$gt": 0}}]
                        },
                        {"domain": 1}
                    ):
                        if doc.get("domain"):
                            found_sch.add(doc["domain"])
                except Exception as e:
                    utils.get_logger().error(f"check scheduler batch error: {e}")

            # 统一补齐与纠偏
            for d in chunk:
                is_probed = (
                    d in found_domains 
                    or d in found_ips 
                    or d in found_in_scope_tasks 
                    or d in found_tasks 
                    or d in found_sch
                )
                prev_status = domain_status.get(d, {}).get("status") if isinstance(domain_status.get(d), dict) else None
                new_status = "probed" if is_probed else "unprobed"
                if prev_status != new_status:
                    need_persist = True
                    target_meta = dict(domain_status.get(d, {})) if isinstance(domain_status.get(d), dict) else {}
                    target_meta["status"] = new_status
                    if is_probed and not target_meta.get("last_probe_time"):
                        target_meta["last_probe_time"] = utils.curr_date()
                    domain_status[d] = target_meta

    # 统计各状态计数
    updated_status = {}
    probed_cnt = 0
    unprobed_cnt = 0
    scanning_cnt = 0
    error_cnt = 0

    for d in scope_items:
        if d in active_scanning_set:
            st_obj = dict(domain_status.get(d, {})) if isinstance(domain_status.get(d), dict) else {}
            st_obj["status"] = "scanning"
            scanning_cnt += 1
            if domain_status.get(d, {}).get("status") != "scanning":
                need_persist = True
        else:
            st_obj = domain_status.get(d)
            if not isinstance(st_obj, dict):
                st_obj = {"status": "unprobed"}

            st_val = st_obj.get("status", "unprobed")
            if st_val == "probed":
                probed_cnt += 1
            elif st_val == "scanning":
                scanning_cnt += 1
            elif st_val == "error":
                error_cnt += 1
            else:
                unprobed_cnt += 1

        updated_status[d] = st_obj

    # 自动持久化回写至 MongoDB asset_scope，确保后续查询 0 额外 DB 聚合开销
    if need_persist and auto_persist and scope_id_str:
        try:
            utils.conn_db("asset_scope").update_one(
                {"_id": bson.ObjectId(scope_id_str)},
                {"$set": {"domain_status": updated_status}}
            )
        except Exception as e:
            utils.get_logger().error(f"auto_persist domain_status for scope {scope_id_str} error: {e}")

    return updated_status, {
        "total": len(scope_items),
        "probed": probed_cnt,
        "unprobed": unprobed_cnt,
        "scanning": scanning_cnt,
        "error": error_cnt
    }


def trigger_scope_domain_scan(scope_id, domains, policy_id, task_type='oneshot', interval=86400, task_name=""):
    """
    复用监控/扫描任务体系，对资产分组中的指定域名下发任务
    """
    from app.modules import TaskTag, CeleryAction, CeleryRoutingKey, AssetScopeType
    from app.helpers import get_options_by_policy_id
    from app import celerytask, scheduler as app_scheduler

    scope_data = get_scope_by_scope_id(scope_id)
    if not scope_data:
        raise Exception(f"未找到资产分组: {scope_id}")

    task_options = get_options_by_policy_id(policy_id, TaskTag.TASK) if policy_id else {}
    if task_options is None:
        task_options = {}

    triggered_count = 0
    for d in domains:
        d = d.strip()
        if not d:
            continue

        curr_name = task_name or f"{'一次性扫描' if task_type == 'oneshot' else '监控'}-{scope_data.get('name', '资产组')}-{d}"
        curr_name = utils.truncate_string(curr_name)

        if task_type == 'periodic':
            # 周期监控任务
            interval_sec = max(3600 * 6, int(interval))
            scheduler_id = app_scheduler.add_scheduler(
                domain=d,
                scope_id=str(scope_id),
                options=task_options,
                interval=interval_sec,
                name=curr_name,
                scope_type=AssetScopeType.DOMAIN
            )
            update_scope_domain_status(scope_id, d, "scanning", scheduler_id)
            triggered_count += 1
        else:
            # 一次性扫描任务
            task_data = {
                "domain": d,
                "scope_id": str(scope_id),
                "type": AssetScopeType.DOMAIN,
                "monitor_options": task_options,
                "name": curr_name
            }
            options = {
                "celery_action": CeleryAction.ONESHOT_DOMAIN_EXEC_TASK,
                "data": task_data
            }
            celery_id = celerytask.arl_task.apply_async(kwargs={'options': options}, queue=CeleryRoutingKey.ASSET_TASK_HEAVY)
            update_scope_domain_status(scope_id, d, "scanning", str(celery_id))
            triggered_count += 1

    return triggered_count



