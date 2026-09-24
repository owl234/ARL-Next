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
        "site": ["task_id", "status", "title", "hostname", "site", "http_server", "tag", "is_catch_all"],
        "service": "task_id",
        "url": "task_id",
        "task": ["status", "start_time"],
        "icp_task": ["status", "start_time", "end_time", "synced_scope_id"],
        "vuln": ["task_id", "save_date"],
        "nuclei_result": ["task_id", "vuln_severity", "save_date"],
        "asset_ip": "scope_id",
        "asset_site": ["scope_id", "tag", "is_catch_all"],
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
        "asset_scope": "group_id",
        "asset_group": "sort_order",
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
        "asset_group": [("name", 1)],
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
                # 兼容历史记录：旧版本 create_time 是 Unix 整数，先转换为
                # BSON Date 类型的绝对过期时间，再建立 TTL=0 索引。
                conn_db('dict_upload_task').update_many(
                    {
                        "expire_at": {"$exists": False},
                        "create_time": {"$type": ["int", "long", "double", "decimal"]}
                    },
                    [
                        {"$set": {
                            "expire_at": {
                                "$dateAdd": {
                                    "startDate": {"$toDate": {"$multiply": ["$create_time", 1000]}},
                                    "unit": "day",
                                    "amount": 7
                                }
                            }
                        }}
                    ]
                )
                conn_db('dict_upload_task').create_index(
                    [("expire_at", 1)], expireAfterSeconds=0, background=True
                )
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


def heal_historical_invalid_sites():
    """
    🛡️【第一性原理：历史存量无效站点情报自愈与防误杀迁移】
    扫描存量被误打上 '无效' 标签的资产组站点：
    1. 若已有指纹（如 Volcengine-DCDN、Spring 等），直接剔除 '无效'；
    2. 若关联 asset_fileleak 存在 200 敏感端点（/pods, /metrics, /healthz 等）、
       或关联 asset_vuln 存在漏洞、或 asset_cert 存在 k8s 证书：
       自动反哺指纹并剔除 '无效'，补齐 '待测试' 标签。
    单次幂等迁移，通过 sentinel 记录完成态，不影响系统后续运行。
    """
    import logging
    import time
    from urllib.parse import urlparse
    from pymongo import UpdateOne
    logger = logging.getLogger()
    sys_db = conn_db("system_config")

    sentinel_id = "migration_heal_invalid_sites_v1"
    record = sys_db.find_one({"_id": sentinel_id})
    if record and record.get("status") == "completed":
        return

    try:
        coll = conn_db("asset_site")
        cursor = coll.find({"tag": "无效"}, batch_size=200)
        bulk_ops = []
        healed_count = 0

        fileleak_coll = conn_db("asset_fileleak")
        vuln_coll = conn_db("asset_vuln")
        cert_coll = conn_db("asset_cert")

        for doc in cursor:
            site_url = doc.get("site") or ""
            scope_id = doc.get("scope_id")
            ip = doc.get("ip") or ""

            try:
                parsed = urlparse(site_url)
                site_port = parsed.port or (443 if parsed.scheme == "https" else 80)
            except Exception:
                site_port = 80

            existing_fingers = doc.get("finger") or []
            if not isinstance(existing_fingers, list):
                existing_fingers = []

            current_names = set()
            for f in existing_fingers:
                if isinstance(f, dict) and f.get("name"):
                    current_names.add(f["name"])
                elif isinstance(f, str):
                    current_names.add(f)

            # 1. 检查 asset_fileleak
            if site_url:
                query_leak = {"site": site_url, "status_code": {"$in": [200, 301, 302]}}
                if scope_id:
                    query_leak["scope_id"] = scope_id
                leaks = list(fileleak_coll.find(query_leak))
                for lk in leaks:
                    u = lk.get("url", "")
                    st = lk.get("status_code")
                    if st == 200:
                        if u.endswith("/pods") or "/pods?" in u:
                            current_names.add("Kubernetes-Kubelet")
                        elif u.endswith("/healthz") or "/healthz?" in u:
                            if site_port == 10256:
                                current_names.add("Kubernetes-Kube-Proxy")
                            elif site_port in (10255, 10250):
                                current_names.add("Kubernetes-Kubelet")
                            elif site_port == 9091:
                                current_names.add("Milvus")
                            elif site_port == 8093:
                                current_names.add("Kubernetes-Edge")
                        elif u.endswith("/metrics") or "/metrics?" in u:
                            current_names.add("Prometheus-Metrics")
                        elif u.endswith("/readyz") or "/readyz?" in u or u.endswith("/livez") or "/livez?" in u:
                            current_names.add("Kubernetes-Probe")
                        elif "/actuator" in u:
                            current_names.add("Spring-Boot-Actuator")
                        elif "/swagger" in u or "/api-docs" in u or "/openapi.json" in u:
                            current_names.add("Swagger-UI")
                        elif "/api/v1/credential/users" in u or "/api/v1/collections" in u:
                            current_names.add("Milvus")
                    elif st in (301, 302):
                        if u.endswith("/pms") or "/pms/" in u:
                            current_names.add("HP-System-Management")

            # 2. 检查 asset_vuln
            if site_url:
                query_vuln = {"$or": [{"target": site_url}, {"vuln_url": site_url}]}
                if scope_id:
                    query_vuln["scope_id"] = scope_id
                vulns = list(vuln_coll.find(query_vuln))
                for v in vulns:
                    app_name = v.get("app_name") or v.get("plugin_name") or "Vulnerability"
                    current_names.add(f"Vuln:{app_name}")

            # 3. 检查 asset_cert
            if ip:
                query_cert = {"ip": ip, "port": site_port}
                if scope_id:
                    query_cert["scope_id"] = scope_id
                certs = list(cert_coll.find(query_cert))
                for c in certs:
                    cert_dict = c.get("cert") or {}
                    subject_dn = (cert_dict.get("subject_dn") or "").lower()
                    issuer_dn = (cert_dict.get("issuer_dn") or "").lower()
                    if "konnectivity" in subject_dn or "konnectivity" in issuer_dn:
                        current_names.add("Kubernetes-Konnectivity")
                    elif "kubernetes" in subject_dn or "k8s" in subject_dn or "kubernetes" in issuer_dn:
                        current_names.add("Kubernetes")

            # 若具备任何指纹（原有或新反哺），或者命中以上任何事实：必须移除 "无效"
            if current_names:
                raw_tags = doc.get("tag") or []
                if isinstance(raw_tags, str):
                    raw_tags = [raw_tags]
                elif not isinstance(raw_tags, list):
                    raw_tags = []

                clean_tags = [t for t in raw_tags if t != "无效"]
                if "待测试" not in clean_tags:
                    clean_tags.append("待测试")

                updated_finger_list = []
                seen = set()
                for f in existing_fingers:
                    name = f.get("name") if isinstance(f, dict) else f
                    if name and name not in seen:
                        updated_finger_list.append(f if isinstance(f, dict) else {
                            "icon": "default.png", "name": name, "confidence": "100", "version": "", "website": "", "categories": []
                        })
                        seen.add(name)
                for name in sorted(current_names):
                    if name not in seen:
                        updated_finger_list.append({
                            "icon": "default.png", "name": name, "confidence": "100", "version": "", "website": "", "categories": []
                        })
                        seen.add(name)

                bulk_ops.append(UpdateOne(
                    {"_id": doc["_id"]},
                    {"$set": {"finger": updated_finger_list, "tag": clean_tags}}
                ))
                healed_count += 1

                if len(bulk_ops) >= 200:
                    coll.bulk_write(bulk_ops, ordered=False)
                    bulk_ops = []

        if bulk_ops:
            coll.bulk_write(bulk_ops, ordered=False)

        sys_db.update_one(
            {"_id": sentinel_id},
            {"$set": {"status": "completed", "completed_at": time.time(), "healed_count": healed_count}},
            upsert=True
        )
        if healed_count:
            logger.info(f"heal_historical_invalid_sites: successfully healed {healed_count} invalid sites.")
    except Exception as e:
        logger.error(f"heal_historical_invalid_sites error: {e}", exc_info=True)


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
    [DEPRECATED / 防御注解] 僵尸任务收敛逻辑已解耦并移交调度器守护进程 (backend/app/scheduler.py)。
    严禁在 Web Worker 或 arl_update 数据迁移初始化流水线中执行，以杜绝 Web 服务多 Worker 启动/轮转时误杀运行中的扫描任务。
    为保持向后静态引用兼容，保留本函数声明为空操作（防御性跳过并记录告警）。
    """
    import logging
    logger = logging.getLogger()
    logger.warning(
        "[DEPRECATED] arlupdate.cleanup_zombie_tasks is deprecated and disabled in Web context. "
        "Zombie task lifecycle cleanup is exclusively handled by app.scheduler.cleanup_zombie_tasks."
    )
    return


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


def heal_polluted_site_fingers():
    """
    🛡️【第一性原理：存量站点指纹雪崩异常数据平滑重估自愈】
    针对历史早期缺陷（如正则入参反转）导致指纹数组膨胀（> 30个）的脏数据，
    基于持久化的 headers、title、favicon 及加固后的指纹引擎在后台异步平滑自愈清洗。
    自动剔除上千条虚假 Body 正则指纹，保留合法的 Server/Title/Favicon 组件特征。
    """
    import logging
    import time
    import threading
    from pymongo import UpdateOne
    from app.services.fetchSite import finger_identify
    from app.services import finger_db_cache

    logger = logging.getLogger()
    sys_coll = conn_db('system_config')
    mig_record = sys_coll.find_one({"_id": "finger_heal_migrated_v1"})
    if mig_record and mig_record.get("status") == "completed":
        return

    def _worker():
        try:
            sys_coll.update_one(
                {"_id": "finger_heal_migrated_v1"},
                {"$set": {"status": "processing", "start_time": time.time()}},
                upsert=True
            )
            # 确保规则库缓存为最新
            finger_db_cache.update_cache()

            polluted_query = {
                "$expr": {"$gt": [{"$size": {"$ifNull": ["$finger", []]}}, 30]}
            }

            total_healed = 0
            for coll_name in ("asset_site", "site"):
                coll = conn_db(coll_name)
                total_need = coll.count_documents(polluted_query)
                if total_need == 0:
                    continue

                logger.info(f"Start background healing {total_need} polluted finger records in '{coll_name}'...")
                cursor = coll.find(polluted_query, {
                    "_id": 1, "site": 1, "headers": 1, "title": 1, "favicon": 1, "finger": 1
                }, batch_size=200, no_cursor_timeout=True)

                operations = []
                healed_count = 0

                try:
                    for doc in cursor:
                        headers = doc.get("headers") or ""
                        title = doc.get("title") or ""
                        favicon_hash = str(doc.get("favicon", {}).get("hash", 0)) if isinstance(doc.get("favicon"), dict) else "0"

                        try:
                            matched_names = finger_identify(content=b"", header=headers, title=title, favicon_hash=favicon_hash)
                        except Exception as e:
                            logger.warning(f"Failed to re-identify finger for {doc.get('site')}: {e}")
                            matched_names = []

                        cleaned_fingers = []
                        for name in set(matched_names):
                            cleaned_fingers.append({
                                "icon": "default.png",
                                "name": name,
                                "confidence": "80",
                                "version": "",
                                "website": "https://www.riskivy.com",
                                "categories": []
                            })

                        operations.append(UpdateOne(
                            {"_id": doc["_id"]},
                            {"$set": {"finger": cleaned_fingers}}
                        ))

                        if len(operations) >= 200:
                            coll.bulk_write(operations, ordered=False)
                            healed_count += len(operations)
                            operations = []

                    if operations:
                        coll.bulk_write(operations, ordered=False)
                        healed_count += len(operations)
                finally:
                    if cursor is not None:
                        try:
                            cursor.close()
                        except Exception:
                            pass

                total_healed += healed_count
                logger.info(f"Successfully healed {healed_count} polluted records in '{coll_name}'.")

            sys_coll.update_one(
                {"_id": "finger_heal_migrated_v1"},
                {"$set": {"status": "completed", "completed_at": time.time(), "total_healed": total_healed}},
                upsert=True
            )
            logger.info("heal_polluted_site_fingers fully completed and marked in system_config.")
        except Exception as e:
            logger.error(f"heal_polluted_site_fingers background worker error: {e}", exc_info=True)

    t = threading.Thread(target=_worker, name="arl-finger-heal", daemon=True)
    t.start()


def backfill_icp_task_synced_scopes():
    """
    自动对齐并自愈历史存量已同步 ICP 任务：
    若历史任务存在同名 asset_scope，自动补齐 synced_scope_id 与 synced_scope_name，
    并补全 asset_scope.domain_status 中对应域名的 task_id 与 task_name 溯源信息。
    """
    try:
        icp_task_col = conn_db('icp_task')
        scope_col = conn_db('asset_scope')

        tasks = list(icp_task_col.find({
            "$or": [
                {"synced_scope_id": {"$in": [None, ""]}},
                {"synced_scope_id": {"$exists": False}}
            ]
        }))
        if not tasks:
            return

        scopes = list(scope_col.find({}, {"_id": 1, "name": 1, "group_name": 1, "domain_status": 1}))
        scope_by_name = {s["name"].strip(): s for s in scopes if s.get("name")}

        for task in tasks:
            task_name = (task.get("name") or "").strip()
            matched_scope = scope_by_name.get(task_name)
            if matched_scope:
                scope_id_str = str(matched_scope["_id"])
                scope_name = matched_scope.get("name", "")
                group_name = matched_scope.get("group_name", "")

                # 回写 icp_task 关联
                icp_task_col.update_one(
                    {"_id": task["_id"]},
                    {"$set": {
                        "synced_scope_id": scope_id_str,
                        "synced_scope_name": scope_name,
                        "synced_group_name": group_name
                    }}
                )

                # 补全 matched_scope 中遗漏 task_id 的 icp 域名溯源信息
                domain_status = matched_scope.get("domain_status", {})
                updated_ds = False
                if isinstance(domain_status, dict):
                    for d, meta in domain_status.items():
                        if isinstance(meta, dict) and meta.get("sync_source") == "icp" and not meta.get("task_id"):
                            meta["task_id"] = str(task["_id"])
                            meta["task_name"] = task_name
                            updated_ds = True
                if updated_ds:
                    scope_col.update_one(
                        {"_id": matched_scope["_id"]},
                        {"$set": {"domain_status": domain_status}}
                    )
    except Exception as e:
        import logging
        logging.getLogger().error(f"backfill_icp_task_synced_scopes failed: {e}")


def migrate_asset_group_sort_order():
    """
    平滑补齐 asset_group 存量数据的 sort_order 字段，确保向下兼容与排序稳定性
    """
    try:
        col = conn_db('asset_group')
        missing_docs = list(col.find({'sort_order': {'$exists': False}}).sort('_id', 1))
        if missing_docs:
            max_doc = col.find_one({'sort_order': {'$exists': True}}, sort=[('sort_order', -1)])
            current_max = (max_doc.get('sort_order', -1) if max_doc else -1) + 1
            for idx, doc in enumerate(missing_docs):
                col.update_one({'_id': doc['_id']}, {'$set': {'sort_order': current_max + idx}})
    except Exception as e:
        import logging
        logging.getLogger().error(f"migrate_asset_group_sort_order failed: {e}")


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
        _run_step("heal_historical_invalid_sites", heal_historical_invalid_sites)
        _run_step("migrate_asset_cip_merge", migrate_asset_cip_merge)
        _run_step("migrate_geo_ip_data", migrate_geo_ip_data)
        _run_step("heal_polluted_site_fingers", heal_polluted_site_fingers)
        _run_step("backfill_icp_task_synced_scopes", backfill_icp_task_synced_scopes)
        _run_step("migrate_asset_group_sort_order", migrate_asset_group_sort_order)
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
