import sys
import os
import threading
from . import conn_db
from app.config import Config


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
        "vuln": "task_id",
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
    }
    for table in index_map:
        if isinstance(index_map[table], list):
            for index in index_map[table]:
                conn_db(table).create_index(index, background=True)
        else:
            conn_db(table).create_index(index_map[table], background=True)

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

    # 专门处理特殊的系统日志索引
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
                logging.getLogger().info("Syslog indexes created successfully.")
                return
            except Exception as e:
                retries += 1
                wait_time = min(2 ** retries, 300)
                logging.getLogger().warning(f"Failed to create syslog indexes (Attempt {retries}/{max_retries}): {e}. Retrying in {wait_time}s...")
                time.sleep(wait_time)
        logging.getLogger().error("CRITICAL: Failed to create syslog indexes after maximum retries. Please check MongoDB status!")

    threading.Thread(target=_create_syslog_indexes, daemon=True).start()


def arl_update():
    if is_run_flask_routes():
        return

    npoc_info_update()
    
    from app.services.fingerprint_cache import finger_db_cache
    finger_db_cache._auto_seed_if_empty()
    import time
    db = conn_db('system_config')
    
    # 尝试初始化锁记录
    try:
        db.insert_one({"_id": "init_lock", "status": "pending", "locked_at": 0})
    except Exception:
        pass 
    
    # 检查并释放过期的死锁（超过60分钟未完成）
    stale_time = time.time() - 3600
    db.update_one(
        {"_id": "init_lock", "status": "processing", "locked_at": {"$lt": stale_time}},
        {"$set": {"status": "pending"}}
    )
    
    # 尝试抢占初始化锁
    result = db.update_one(
        {"_id": "init_lock", "status": "pending"},
        {"$set": {"status": "processing", "locked_at": time.time()}}
    )
    
    # 如果没拿到锁，说明已有其他进程正在处理或已经处理完毕
    if result.modified_count == 0:
        return

    try:
        update_task_tag()
        create_index()
        db.update_one({"_id": "init_lock"}, {"$set": {"status": "completed"}})
    except Exception as e:
        import logging
        logging.getLogger().error(f"Failed to complete arl_update: {e}")
        db.update_one({"_id": "init_lock"}, {"$set": {"status": "pending"}}, upsert=True)


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
