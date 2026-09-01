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
        "poc": "plugin_name",
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
        "asset_wih": [("scope_id", 1), ("site", 1), ("fnv_hash", 1)]
    }

    for col, keys in unique_indexes.items():
        try:
            conn_db(col).create_index(keys, unique=True, background=True)
        except Exception as e:
            import logging
            if "E11000" in str(e) or "duplicate key error" in str(e).lower():
                logging.getLogger().warning(f"Duplicate key error on {col}, attempting to deduplicate...")
                
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
                    conn_db(col).create_index(keys, unique=True, background=True)
                    logging.getLogger().info(f"Successfully deduplicated and created unique index on {col}")
                except Exception as de:
                    logging.getLogger().error(f"Failed to deduplicate {col}: {de}")
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


def arl_update():
    if is_run_flask_routes():
        return

    npoc_info_update()
    
    from app.services.fingerprint_cache import finger_db_cache
    finger_db_cache._auto_seed_if_empty()
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

    try:
        ensure_builtin_dicts()
        update_task_tag()
        create_index()
        migrate_asset_scope_domain_status()
        cleanup_zombie_tasks()
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
        if conn_db('poc').count_documents({}) > 0:
            return

        n = NPoC()
        n.sync_to_db()


# 判断是否是-m flask routes 模式运行
def is_run_flask_routes():
    if len(sys.argv) == 2:
        if "flask/__main__.py" in sys.argv[0]:
            if sys.argv[1] == "routes":
                return True

    return False
