import sys
import threading
from . import conn_db


def update_task_tag():
    """更新task任务tag信息"""
    table = "task"
    items = conn_db(table).find({})
    for item in items:
        task_tag = item.get("task_tag")
        query = {"_id": item["_id"]}
        if not task_tag:
            item["task_tag"] = "task"
            conn_db(table).find_one_and_replace(query, item)


def create_index():
    index_map = {
        "cert": "task_id",
        "domain": ["task_id", "domain"],
        "fileleak": "task_id",
        "ip": "task_id",
        "npoc_service": "task_id",
        "site": ["task_id", "status", "title", "hostname", "site", "http_server"],
        "service": "task_id",
        "url": "task_id",
        "task": ["status", "start_time"],
        "icp_task": ["status", "start_time", "end_time"],
        "vuln": ["task_id", "save_date"],
        "nuclei_result": ["task_id", "vuln_severity", "save_date"],
        "asset_ip": "scope_id",
        "asset_site": "scope_id",
        "asset_domain": ["scope_id", "domain"],
        "github_result": "github_task_id",
        "github_monitor_result": "github_scheduler_id",
        "wih": ["task_id", "record_type", "fnv_hash"],
        "asset_cert": ["scope_id", "ip"],
        "asset_service": "scope_id",
        "asset_fileleak": "scope_id",
        "asset_url": "scope_id",
        "asset_vuln": ["scope_id", "vul_name"],
        "asset_npoc_service": "scope_id",
        "asset_cip": "scope_id",
        "asset_nuclei_result": "scope_id",
        "asset_stat_finger": "scope_id",
        "asset_wih": ["scope_id", "record_type", "fnv_hash"],
        "dict_upload_task": "task_id",
    }
    for table in index_map:
        if isinstance(index_map[table], list):
            for index in index_map[table]:
                conn_db(table).create_index(index, background=True)
        else:
            conn_db(table).create_index(index_map[table], background=True)

    # Scheduler 核心轮询复合索引
    conn_db('scheduler').create_index([("status", 1), ("next_run_time", 1)], background=True)

    # icp_asset 核心多维查询与排序复合索引（解决 COLLSCAN 与 32MB 内存排序超限）
    # 逐个兜底：索引属增益型优化，任一构建异常都不得阻断后续增量迁移步骤
    for icp_keys in ([("task_id", 1), ("query_type", 1), ("updateRecordTime", -1)],
                     [("task_id", 1), ("query_type", 1), ("examineDate", -1)]):
        try:
            conn_db('icp_asset').create_index(icp_keys, background=True)
        except Exception as ex:
            import logging
            logging.getLogger().warning(f"Failed to create icp_asset index {icp_keys}: {ex}")

    # 兜底：创建联合唯一索引，彻底解决极端并发下的重复写入问题
    unique_indexes = {
        "site": [("task_id", 1), ("site", 1)],
        "domain": [("task_id", 1), ("domain", 1)],
        "ip": [("task_id", 1), ("ip", 1)],
        "cert": [("task_id", 1), ("ip", 1), ("port", 1)],
        "service": [("task_id", 1), ("service_name", 1)],
        "url": [("task_id", 1), ("url", 1)],
        "fileleak": [("task_id", 1), ("site", 1), ("url", 1)],
        "npoc_service": [("task_id", 1), ("target", 1)],
        "vuln": [("task_id", 1), ("vuln_url", 1), ("plugin_name", 1)],
        "nuclei_result": [("task_id", 1), ("template_id", 1), ("host", 1)],
        "stat_finger": [("task_id", 1), ("name", 1)],
        "cip": [("task_id", 1), ("cidr_ip", 1)],
        "wih": [("task_id", 1), ("site", 1), ("fnv_hash", 1)],
        "asset_wih": [("scope_id", 1), ("site", 1), ("fnv_hash", 1)],
        "poc": [("plugin_name", 1)],
        "fingerprint_deleted": [("name", 1)],
    }

    def _deduplicate_and_create_unique(col, keys, drop_idx=None):
        import logging
        # 🛡️【无损兼容】在去重前，为存量数据自动平滑生成新标准 Hash 补齐，避免 null 误聚合
        if col in ["wih", "asset_wih"]:
            try:
                from app.services.wih.fnv1a import fnv1a_64
                cursor = conn_db(col).find(
                    {"$or": [{"fnv_hash": {"$exists": False}}, {"fnv_hash": None}, {"fnv_hash": ""}]},
                    batch_size=500
                )
                for doc in cursor:
                    content = doc.get("content", "")
                    new_hash = fnv1a_64(content) if content else f"fallback_{doc['_id']}"
                    conn_db(col).update_one({"_id": doc["_id"]}, {"$set": {"fnv_hash": new_hash}})
            except Exception as inner_ex:
                logging.getLogger().error(f"Failed to migrate missing fnv_hash for {col}: {inner_ex}")

        try:
            group_id = {k[0]: f"${k[0]}" for k in keys}
            pipeline = [
                {"$group": {"_id": group_id, "dups": {"$push": "$_id"}, "count": {"$sum": 1}}},
                {"$match": {"count": {"$gt": 1}}}
            ]
            for doc in conn_db(col).aggregate(pipeline, allowDiskUse=True):
                dups = doc['dups'][1:]
                if dups:
                    conn_db(col).delete_many({"_id": {"$in": dups}})

            if drop_idx:
                try:
                    conn_db(col).drop_index(drop_idx)
                except Exception as drop_e:
                    logging.getLogger().warning(f"Failed to drop old index {drop_idx} on {col}: {drop_e}")
            else:
                # 兜底：若未指定 drop_idx，清理同字段的旧非唯一索引
                try:
                    target_keys = [(k, int(d)) for k, d in keys]
                    for name, info in conn_db(col).index_information().items():
                        if [(k, int(d)) for k, d in info.get("key", [])] == target_keys and not info.get("unique", False):
                            conn_db(col).drop_index(name)
                except Exception:
                    pass

            conn_db(col).create_index(keys, unique=True, background=True)
            logging.getLogger().info(f"Successfully deduplicated and created unique index on {col}")
        except Exception as de:
            logging.getLogger().error(f"Failed to deduplicate or create unique index on {col}: {de}")

    for col, keys in unique_indexes.items():
        try:
            # 🛡️【平滑演进】主动探测：若存量库已存在同字段非唯一索引（如老版 poc.plugin_name），先去重并平滑置换为唯一索引
            target_keys = [(k, int(d)) for k, d in keys]
            existing_indexes = conn_db(col).index_information()
            conflict_idx_name = None
            for idx_name, info in existing_indexes.items():
                if [(k, int(d)) for k, d in info.get("key", [])] == target_keys and not info.get("unique", False):
                    conflict_idx_name = idx_name
                    break

            if conflict_idx_name:
                import logging
                logging.getLogger().info(f"Detected legacy non-unique index {conflict_idx_name} on {col}, upgrading to unique...")
                _deduplicate_and_create_unique(col, keys, drop_idx=conflict_idx_name)
            else:
                conn_db(col).create_index(keys, unique=True, background=True)
        except Exception as e:
            import logging
            err_msg = str(e).lower()
            if "e11000" in err_msg or "duplicate key error" in err_msg or "different options" in err_msg or "conflict" in err_msg:
                logging.getLogger().warning(f"Index conflict or duplicate key on {col} ({e}), attempting to deduplicate and migrate...")
                _deduplicate_and_create_unique(col, keys)
            else:
                logging.getLogger().warning(f"Failed to create unique index on {col}: {e}")

    # 专门处理特殊的系统日志与临时任务索引
    def _create_syslog_indexes():
        import time
        import logging
        max_retries = 30
        retries = 0
        while retries < max_retries:
            try:
                # 2592000 秒 = 30天
                conn_db('syslog').create_index([("create_time", 1)], expireAfterSeconds=2592000, background=True)
                # 为 task_id 建立索引，防止前端查看任务日志时触发全表扫描（COLLSCAN）拖垮系统
                conn_db('syslog').create_index([("task_id", 1)], background=True)
                # 字典异步上传任务记录 7 天自动过期清理 (604800 秒)
                conn_db('dict_upload_task').create_index([("create_time", 1)], expireAfterSeconds=604800, background=True)
                logging.getLogger().info("Syslog & dict upload indexes created successfully.")
                return
            except Exception as e:
                retries += 1
                wait_time = min(2 ** retries, 300)
                logging.getLogger().warning(f"Failed to create syslog indexes (Attempt {retries}/{max_retries}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        logging.getLogger().error("CRITICAL: Failed to create syslog indexes after maximum retries. Please check MongoDB status!")

    threading.Thread(target=_create_syslog_indexes, daemon=True).start()


def migrate_asset_scope_domain_status():
    """
    后台静默补齐存量 asset_scope 分组的 domain_status 探测状态与覆盖度
    彻底消除前端访问存量资产分组时的延迟
    """
    def _worker():
        import logging
        logger = logging.getLogger()
        try:
            scopes = list(conn_db("asset_scope").find({"domain_status": {"$exists": False}}))
            if not scopes:
                return
            logger.info(f"Start migrating domain_status for {len(scopes)} asset scopes...")
            from app.helpers.scope import get_scope_domain_stat
            for sc in scopes:
                try:
                    get_scope_domain_stat(sc, auto_persist=True)
                except Exception as ex:
                    logger.warning(f"Error migrating scope {sc.get('_id')}: {ex}")
            logger.info("Successfully finished migrating asset scope domain_status.")
        except Exception as e:
            logger.error(f"migrate_asset_scope_domain_status error: {e}")

    threading.Thread(target=_worker, daemon=True).start()


def cleanup_asset_scope_dead_fields():
    """
    🧹【平滑演进】下线资产黑名单功能后，清理存量 asset_scope 文档中的死字段 black_scope / black_scope_array
    该字段自引入起仅存储、从未被扫描/监控链路读取，$unset 无任何行为影响；重复执行幂等
    """
    import logging
    logger = logging.getLogger()
    try:
        result = conn_db('asset_scope').update_many(
            {"$or": [{"black_scope": {"$exists": True}}, {"black_scope_array": {"$exists": True}}]},
            {"$unset": {"black_scope": "", "black_scope_array": ""}}
        )
        if result.modified_count:
            logger.info(f"Cleaned up dead black_scope fields from {result.modified_count} asset_scope documents.")
    except Exception as e:
        logger.error(f"Failed to cleanup asset_scope dead black_scope fields: {e}")


def migrate_asset_site_pending_test_tag():
    """
    全量为存量资产组站点幂等补齐 '待测试' 标签（单次迁移，后续重启不再复活已删除标签）
    使用原生 $addToSet 原子批量更新，毫秒级完成且保留所有既有自定义标签
    """
    import logging
    import time
    logger = logging.getLogger()
    sys_db = conn_db("system_config")

    # 🛡️【迁移哨兵】：若存量迁移已完成，直接跳过，防止系统重启时复活用户已测试并手动移除的标签
    migration_record = sys_db.find_one({"_id": "migration_asset_site_pending_test_tag"})
    if migration_record and migration_record.get("status") == "completed":
        return

    try:
        # 🛡️【扁平化自愈】：若存在历史嵌套数组 tag（如 [['入口'], '待测试']），原子展平并去重
        try:
            conn_db("asset_site").update_many(
                {"tag.0": {"$type": 4}},
                [{
                    "$set": {
                        "tag": {
                            "$reduce": {
                                "input": "$tag",
                                "initialValue": [],
                                "in": {
                                    "$setUnion": [
                                        "$$value",
                                        {"$cond": [{"$isArray": "$$this"}, "$$this", ["$$this"]]}
                                    ]
                                }
                            }
                        }
                    }
                }]
            )
        except Exception as e:
            logger.warning(f"Flattening nested tags failed: {e}")

        # 🛡️【类型防御】若 tag 本身为纯字符串（非数组），转为单元素数组
        try:
            conn_db("asset_site").update_many(
                {"$expr": {"$eq": [{"$type": "$tag"}, "string"]}},
                [{"$set": {"tag": ["$tag"]}}]
            )
        except Exception as e:
            logger.warning(f"Pipeline update for string tags failed, falling back to cursor update: {e}")
            cursor = conn_db("asset_site").find({"$expr": {"$eq": [{"$type": "$tag"}, "string"]}}, {"_id": 1, "tag": 1}, batch_size=500)
            from pymongo import UpdateOne
            bulk_ops = []
            for doc in cursor:
                val = doc.get("tag")
                tag_list = [val] if val else []
                bulk_ops.append(UpdateOne({"_id": doc["_id"]}, {"$set": {"tag": tag_list}}))
                if len(bulk_ops) >= 500:
                    conn_db("asset_site").bulk_write(bulk_ops, ordered=False)
                    bulk_ops = []
            if bulk_ops:
                conn_db("asset_site").bulk_write(bulk_ops, ordered=False)

        query = {"$or": [{"tag": {"$exists": False}}, {"tag": {"$ne": "待测试"}}]}
        res = conn_db("asset_site").update_many(query, {"$addToSet": {"tag": "待测试"}})
        modified_count = res.modified_count if res else 0
        if modified_count:
            logger.info(f"migrate_asset_site_pending_test_tag: successfully updated {modified_count} asset sites with '待测试' tag.")

        # 标记全量迁移完成
        sys_db.update_one(
            {"_id": "migration_asset_site_pending_test_tag"},
            {"$set": {"status": "completed", "completed_at": time.time(), "modified_count": modified_count}},
            upsert=True
        )
    except Exception as e:
        logger.error(f"migrate_asset_site_pending_test_tag error: {e}")


def ensure_builtin_dicts():
    """确保核心内置字典文件存在（防止升级后因持久化数据卷隔离缺失新增的内置字典）"""
    import os
    import logging
    from app.config import Config
    dict_dir = os.path.join(Config.basedir if hasattr(Config, 'basedir') else os.path.dirname(os.path.dirname(__file__)), 'dicts')
    top300_path = os.path.join(dict_dir, 'domain_top300.txt')
    if not os.path.exists(top300_path):
        try:
            from app.tasks.domain import _load_recursive_dict
            words = _load_recursive_dict()
            with open(top300_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(words) + '\n')
            logging.getLogger().info("Successfully auto-seeded missing domain_top300.txt into dicts volume.")
        except Exception as e:
            logging.getLogger().warning(f"Failed to auto-seed domain_top300.txt: {e}")


def fingerprint_info_update():
    """
    增量平滑同步内置 webapp.json 指纹到 MongoDB fingerprint 集合
    确保存量升级的老用户自动获得新增与加固的指纹，同时完全保留用户在 UI 中添加的自定义指纹
    """
    import os
    import json
    import logging
    from app.config import Config
    from app.services.fingerprint_cache import finger_db_cache
    from pymongo import UpdateOne
    from app.utils import curr_date_obj

    logger = logging.getLogger()
    webapp_file = Config.web_app_rule
    if not os.path.exists(webapp_file):
        return

    try:
        with open(webapp_file, 'r', encoding='utf-8') as f:
            web_app_rules = json.load(f)
    except Exception as e:
        logger.error(f"Failed to load webapp.json in fingerprint_info_update: {e}")
        return

    db = conn_db('fingerprint')
    try:
        db.create_index("name", unique=True, background=True)
    except Exception:
        pass

    # 1. 若表完全为空，直接触发底层 auto_seed 初始全量灌入
    if db.count_documents({}) == 0:
        finger_db_cache._auto_seed_if_empty()
        return

    # 2. 存量环境执行增量自动补齐与核心系统指纹加固
    try:
        # 清理已废弃/合并的存量冗余规则（如 etcd-io 归并至 etcd）
        db.delete_one({"name": "etcd-io"})

        # 用户在 UI 主动删除的内置指纹黑名单：删除后不因增量同步自动复活
        # （由 /fingerprint/delete/ 写入，重新添加/全量重灌时清除）
        deleted_names = set(conn_db('fingerprint_deleted').distinct('name'))

        # 核心加固指纹白名单：代码加固更新后强制同步最新规则
        # 键名必须与 webapp.json 实际键名严格一致（如 Consul by HashiCorp / alibaba-nacos），
        # 并尊重用户删除标记，避免强制复活已删除的核心指纹
        core_system_rules = [
            "etcd", "Kubelet", "Consul by HashiCorp", "alibaba-nacos", "Kubernetes",
            "Nginx", "Byte-nginx", "ByteDance-TLB"
        ]
        updated_core_rules = {}
        for rule_name in core_system_rules:
            if (rule_name in web_app_rules and rule_name not in deleted_names
                    and web_app_rules[rule_name].get("fofa_rule")):
                updated_core_rules[rule_name] = web_app_rules[rule_name]["fofa_rule"]

        existing_names = set(db.distinct('name'))
        # 增量补齐缺失的内置指纹（排除已删除黑名单与待加固核心规则，确保 bulk_write 中每条规则指令严格唯一）
        missing_rules = {
            name: detail for name, detail in web_app_rules.items()
            if name not in existing_names and name not in deleted_names
            and name not in updated_core_rules and detail.get("fofa_rule")
        }

        operations = []
        now_date = curr_date_obj()

        # 增量补齐缺失的内置指纹
        for name, detail in missing_rules.items():
            operations.append(UpdateOne(
                {"name": name},
                {"$setOnInsert": {"name": name, "human_rule": detail["fofa_rule"], "update_date": now_date}},
                upsert=True
            ))

        # 平滑同步核心加固指纹
        for name, rule_str in updated_core_rules.items():
            operations.append(UpdateOne(
                {"name": name},
                {"$set": {"human_rule": rule_str, "update_date": now_date}},
                upsert=True
            ))

        if operations:
            db.bulk_write(operations, ordered=False)
            logger.info(f"Smoothly synced {len(operations)} fingerprint rules (new: {len(missing_rules)}) to MongoDB.")
            finger_db_cache.update_cache(force=True)
    except Exception as e:
        logger.error(f"Failed to smoothly sync fingerprints: {e}")


def cleanup_zombie_tasks():
    """
    🛡️【系统韧性】启动与更新时自动收敛因系统重启或更新中断的僵尸/孤儿任务
    将非终态任务优雅收敛为 TaskStatus.ERROR，并记录明确的终止原因与时间戳
    """
    import logging
    import time
    from app.modules import TaskStatus
    logger = logging.getLogger()
    try:
        non_running = [TaskStatus.DONE, TaskStatus.WAITING, TaskStatus.ERROR, TaskStatus.STOP]
        zombie_tasks = list(conn_db('task').find({"status": {"$nin": non_running}}))
        if zombie_tasks:
            logger.warning(f"Detected {len(zombie_tasks)} interrupted tasks during startup, converging status...")
            curr_date = time.strftime("%Y-%m-%d %H:%M:%S")
            for task in zombie_tasks:
                if task.get("task_tag") == "monitor":
                    conn_db('task').delete_one({"_id": task["_id"]})
                    options = task.get("options", {})
                    scheduler_id = options.get("scheduler_id")
                    if scheduler_id:
                        try:
                            from bson import ObjectId
                            conn_db('scheduler').update_one(
                                {"_id": ObjectId(scheduler_id)},
                                {"$set": {"next_run_time": int(time.time())}}
                            )
                        except Exception:
                            pass
                else:
                    conn_db('task').update_one(
                        {"_id": task["_id"]},
                        {"$set": {
                            "status": TaskStatus.ERROR,
                            "end_time": curr_date,
                            "end_reason": "系统重启/升级中断 (Interrupted by system restart/update)"
                        }}
                    )
            logger.info("Successfully converged interrupted tasks to ERROR.")
    except Exception as e:
        logger.error(f"Failed to cleanup zombie tasks: {e}")


def migrate_asset_cip_merge():
    """
    🛡️【第一性原理：资产组 C 段存量聚合与并集自愈】
    修复历史版本中跨任务资产同步时 ReplaceOne 覆盖导致的 C 段 IP/域名丢失问题。
    从 asset_ip 溯源，按 (scope_id, c_segment) 聚合完整的 IP 集合与关联域名集合，并补全回 asset_cip。
    """
    import logging
    from app import utils
    logger = logging.getLogger()
    try:
        pipeline = [
            {"$match": {"c_segment": {"$exists": True, "$ne": ""}, "scope_id": {"$exists": True, "$ne": ""}}},
            {
                "$group": {
                    "_id": {
                        "scope_id": "$scope_id",
                        "cidr_ip": "$c_segment"
                    },
                    "all_ips": {"$addToSet": "$ip"},
                    "all_domains": {"$push": "$domain"}
                }
            }
        ]

        cursor = conn_db('asset_ip').aggregate(pipeline, allowDiskUse=True)
        updated_count = 0
        for doc in cursor:
            group = doc.get("_id", {})
            scope_id = group.get("scope_id")
            cidr_ip = group.get("cidr_ip")
            if not scope_id or not cidr_ip:
                continue

            all_ips = [ip for ip in doc.get("all_ips", []) if ip]

            domain_set = set()
            for dom_entry in doc.get("all_domains", []):
                if isinstance(dom_entry, list):
                    for d in dom_entry:
                        if d and isinstance(d, str):
                            domain_set.add(d.strip())
                elif isinstance(dom_entry, str) and dom_entry.strip():
                    domain_set.add(dom_entry.strip())

            existing_cip = conn_db('asset_cip').find_one({"scope_id": scope_id, "cidr_ip": cidr_ip})
            if existing_cip:
                curr_ips = existing_cip.get("ip_list") or []
                curr_domains = existing_cip.get("domain_list") or []

                merged_ips = list(dict.fromkeys(curr_ips + all_ips))
                merged_domains = list(dict.fromkeys(curr_domains + list(domain_set)))

                if set(merged_ips) != set(curr_ips) or set(merged_domains) != set(curr_domains):
                    conn_db('asset_cip').update_one(
                        {"_id": existing_cip["_id"]},
                        {
                            "$set": {
                                "ip_list": merged_ips,
                                "ip_count": len(merged_ips),
                                "domain_list": merged_domains,
                                "domain_count": len(merged_domains),
                                "update_date": utils.curr_date_obj()
                            }
                        }
                    )
                    updated_count += 1
            else:
                now = utils.curr_date_obj()
                new_cip = {
                    "scope_id": scope_id,
                    "cidr_ip": cidr_ip,
                    "ip_list": all_ips,
                    "ip_count": len(all_ips),
                    "domain_list": list(domain_set),
                    "domain_count": len(domain_set),
                    "save_date": now,
                    "update_date": now
                }
                conn_db('asset_cip').insert_one(new_cip)
                updated_count += 1

        if updated_count > 0:
            logger.info(f"Successfully migrated/repaired {updated_count} asset_cip records.")
    except Exception as e:
        logger.error(f"migrate_asset_cip_merge failed: {e}", exc_info=True)


def migrate_geo_ip_data():
    """
    🛡️【第一性原理：全量存量 IP 资产高精度 Geo 数据后台异步平滑自愈】
    基于 ip2region + GeoLite2 双轨高精引擎，在后台异步守护线程中执行。
    增加 system_config 全局状态位幂等控制，彻底杜绝服务每次重启时的重复无意义扫描。
    增加 no_cursor_timeout 防中断保护，采用 bulk_write 批量写入（每批 1000 条），
    彻底杜绝主启动流程超时（60s 锁抢占）与阻塞。
    """
    import logging
    import time
    import threading
    from pymongo import UpdateOne
    from .ip import get_ip_city, get_ip_asn

    logger = logging.getLogger()
    sys_coll = conn_db('system_config')
    mig_record = sys_coll.find_one({"_id": "geo_ip2region_migrated_v1"})
    if mig_record and mig_record.get("status") == "completed":
        return

    def _worker():
        try:
            sys_coll.update_one(
                {"_id": "geo_ip2region_migrated_v1"},
                {"$set": {"status": "processing", "start_time": time.time()}},
                upsert=True
            )
            missing_geo_query = {
                "ip_type": "PUBLIC",
                "$or": [
                    {"geo_city.city": None},
                    {"geo_city.city": "null"},
                    {"geo_city": {}},
                    {"geo_city": {"$exists": False}}
                ]
            }

            total_migrated = 0
            for coll_name in ("ip", "asset_ip"):
                cursor = None
                try:
                    coll = conn_db(coll_name)
                    total_need = coll.count_documents(missing_geo_query)
                    if total_need == 0:
                        continue

                    logger.info(f"Start background migrating geo data for {total_need} documents in '{coll_name}'...")
                    cursor = coll.find(missing_geo_query, {"_id": 1, "ip": 1}, no_cursor_timeout=True)
                    operations = []
                    migrated_count = 0

                    for doc in cursor:
                        curr_ip = doc.get("ip")
                        if not curr_ip:
                            continue

                        new_geo = get_ip_city(curr_ip)
                        new_asn = get_ip_asn(curr_ip)

                        update_fields = {}
                        if new_geo:
                            update_fields["geo_city"] = new_geo
                        if new_asn:
                            update_fields["geo_asn"] = new_asn
                            if new_asn.get("organization"):
                                update_fields["as_organization"] = new_asn["organization"]
                            if new_asn.get("number"):
                                update_fields["asn"] = new_asn["number"]

                        if update_fields:
                            operations.append(UpdateOne({"_id": doc["_id"]}, {"$set": update_fields}))

                        if len(operations) >= 1000:
                            coll.bulk_write(operations, ordered=False)
                            migrated_count += len(operations)
                            operations = []

                    if operations:
                        coll.bulk_write(operations, ordered=False)
                        migrated_count += len(operations)

                    total_migrated += migrated_count
                    logger.info(f"Successfully migrated geo data for {migrated_count} documents in '{coll_name}'.")
                except Exception as e:
                    logger.error(f"migrate_geo_ip_data failed for collection '{coll_name}': {e}", exc_info=True)
                finally:
                    if cursor is not None:
                        try:
                            cursor.close()
                        except Exception:
                            pass

            sys_coll.update_one(
                {"_id": "geo_ip2region_migrated_v1"},
                {"$set": {"status": "completed", "completed_at": time.time(), "total_migrated": total_migrated}},
                upsert=True
            )
            logger.info("migrate_geo_ip_data fully completed and marked in system_config.")
        except Exception as e:
            logger.error(f"migrate_geo_ip_data background worker error: {e}", exc_info=True)

    t = threading.Thread(target=_worker, name="arl-geo-migration", daemon=True)
    t.start()


def arl_update():
    if is_run_flask_routes():
        return

    import time
    db = conn_db('system_config')
    now = time.time()
    
    # 尝试初始化锁记录，使用 upsert 和 $setOnInsert 避免 DuplicateKeyError
    db.update_one(
        {"_id": "init_lock"},
        {"$setOnInsert": {"status": "idle", "locked_at": 0, "last_completed_at": 0}},
        upsert=True
    )

    # 兼容 v1.2.1 及更早版本的锁状态："completed" 迁移为 "idle"，
    # 否则存量 init_lock 停留在旧版完成态，新版抢占条件永不命中导致迁移逻辑（索引/补齐/收敛）永久跳过
    db.update_one(
        {"_id": "init_lock", "status": "completed"},
        {"$set": {"status": "idle", "last_completed_at": 0}}
    )

    # 检查并释放过期的死锁（超过60秒未完成）
    stale_time = now - 60
    db.update_one(
        {"_id": "init_lock", "status": "processing", "locked_at": {"$lt": stale_time}},
        {"$set": {"status": "idle"}}
    )
    
    # 尝试抢占初始化锁：允许在 idle 或初次 pending 时抢占，且距离上次完成时间至少大于 15 秒（避免同一次启动中多 Worker 重复执行）
    result = db.update_one(
        {
            "_id": "init_lock",
            "$or": [
                {"status": {"$in": ["pending", "idle"]}, "last_completed_at": {"$lt": now - 15}},
                {"status": {"$in": ["pending", "idle"]}, "last_completed_at": {"$exists": False}}
            ]
        },
        {"$set": {"status": "processing", "locked_at": now}}
    )
    
    # 如果没拿到锁，说明已有其他进程正在处理或刚刚处理完毕
    if result.modified_count == 0:
        return

    def _run_step(name, func):
        """单步兜底：任一增量步骤异常都不得连带跳过其后的迁移/清理，且必须留痕便于定位毒插件"""
        try:
            func()
        except Exception as e:
            import logging
            logging.getLogger().error(f"arl_update step '{name}' failed: {e}", exc_info=True)

    try:
        _run_step("ensure_builtin_dicts", ensure_builtin_dicts)
        _run_step("fingerprint_info_update", fingerprint_info_update)
        _run_step("update_task_tag", update_task_tag)
        _run_step("create_index", create_index)
        _run_step("npoc_info_update", npoc_info_update)
        _run_step("cleanup_asset_scope_dead_fields", cleanup_asset_scope_dead_fields)
        _run_step("migrate_asset_scope_domain_status", migrate_asset_scope_domain_status)
        _run_step("migrate_asset_site_pending_test_tag", migrate_asset_site_pending_test_tag)
        _run_step("migrate_asset_cip_merge", migrate_asset_cip_merge)
        _run_step("migrate_geo_ip_data", migrate_geo_ip_data)
        _run_step("cleanup_zombie_tasks", cleanup_zombie_tasks)
        db.update_one({"_id": "init_lock"}, {"$set": {"status": "idle", "last_completed_at": time.time()}})
    except Exception as e:
        import logging
        logging.getLogger().error(f"Failed to complete arl_update: {e}")
        db.update_one({"_id": "init_lock"}, {"$set": {"status": "idle", "locked_at": 0}}, upsert=True)


# 创建锁，防止多线程同时更新
lock = threading.Lock()


def npoc_info_update():
    from app.services.npoc import NPoC
    with lock:
        n = NPoC()
        db = conn_db('poc')
        existing_names = set(db.distinct('plugin_name'))
        missing_names = set(n.plugin_name_list) - existing_names
        if missing_names:
            # 仅增量同步新增插件，避免全量 sync_to_db 覆盖既有插件元数据与 update_date
            # 已通过 POST /poc/delete/ 删除的插件会同时移除磁盘脚本，重启后不再加载，天然不复活
            n.sync_to_db(names=missing_names)


# 判断是否是-m flask routes 模式运行
def is_run_flask_routes():
    if len(sys.argv) == 2:
        if "flask/__main__.py" in sys.argv[0]:
            if sys.argv[1] == "routes":
                return True

    return False
