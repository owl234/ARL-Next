from functools import lru_cache
import threading
import time
from bson import ObjectId
from app.utils.conn import conn_db

_TASK_SCOPE_CACHE_VERSION_ID = "_task_scope_cache_version"
_TASK_SCOPE_VER_LOCK = threading.Lock()
_TASK_SCOPE_VER_STATE = {"ver": None, "checked_at": 0.0}
_TASK_SCOPE_VER_CHECK_INTERVAL = 2.0


def _read_task_scope_cache_version():
    try:
        doc = conn_db('system_config').find_one({"_id": _TASK_SCOPE_CACHE_VERSION_ID}, {"version": 1})
        if doc:
            return doc.get("version")
    except Exception:
        pass
    return None


def _sync_task_scope_cache_version(force=False):
    now = time.time()
    if not force and (now - _TASK_SCOPE_VER_STATE["checked_at"] < _TASK_SCOPE_VER_CHECK_INTERVAL):
        return
    with _TASK_SCOPE_VER_LOCK:
        now = time.time()
        if not force and (now - _TASK_SCOPE_VER_STATE["checked_at"] < _TASK_SCOPE_VER_CHECK_INTERVAL):
            return
        current_ver = _read_task_scope_cache_version()
        _TASK_SCOPE_VER_STATE["checked_at"] = now
        if current_ver is not None and _TASK_SCOPE_VER_STATE["ver"] != current_ver:
            _get_task_scope_id_cached.cache_clear()
            _TASK_SCOPE_VER_STATE["ver"] = current_ver


def clear_task_scope_cache():
    with _TASK_SCOPE_VER_LOCK:
        _get_task_scope_id_cached.cache_clear()
        _TASK_SCOPE_VER_STATE["checked_at"] = 0.0


@lru_cache(maxsize=1024)
def _get_task_scope_id_cached(task_id):
    if not task_id:
        return None
    try:
        item = conn_db('task').find_one({"_id": ObjectId(task_id)}, {"options.scope_id": 1, "scope_id": 1})
        if item:
            opts = item.get("options") if isinstance(item.get("options"), dict) else {}
            return opts.get("scope_id") or item.get("scope_id")
    except Exception:
        pass
    return None


def _get_task_scope_id(task_id):
    if not task_id:
        return None
    _sync_task_scope_cache_version()
    return _get_task_scope_id_cached(task_id)

def _get_baseline_query(category, item, scope_id):
    if category == "wih":
        return {"scope_id": scope_id, "site": item.get("site"), "fnv_hash": item.get("fnv_hash")}
    elif category == "cert":
        return {"scope_id": scope_id, "ip": item.get("ip"), "cert.fingerprint.sha256": item.get("cert", {}).get("fingerprint", {}).get("sha256")}
    elif category == "service":
        if item.get("ip") and item.get("port_id") is not None:
            return {"scope_id": scope_id, "ip": item.get("ip"), "port_id": item.get("port_id")}
        return {"scope_id": scope_id, "service_name": item.get("service_name")}
    elif category == "fileleak":
        return {"scope_id": scope_id, "url": item.get("url")}
    elif category == "url":
        return {"scope_id": scope_id, "url": item.get("url")}
    elif category == "vuln":
        return {"scope_id": scope_id, "target": item.get("target"), "vul_name": item.get("vul_name")}
    elif category == "npoc_service":
        return {"scope_id": scope_id, "host": item.get("host"), "port": item.get("port")}
    elif category == "cip":
        return {"scope_id": scope_id, "cidr_ip": item.get("cidr_ip")}
    elif category == "nuclei_result":
        return {"scope_id": scope_id, "target": item.get("target"), "template_id": item.get("template_id")}
    elif category == "stat_finger":
        return {"scope_id": scope_id, "name": item.get("name")}
    elif category in ["site", "domain", "ip"]:
        return {"scope_id": scope_id, category: item.get(category)}
    return None

def _compute_update_diff(old_item, new_item):
    diff = {}
    for k, v in new_item.items():
        if k in ["task_id", "_id", "scope_id", "save_date", "update_date", "change_status", "update_diff"]: continue
        # 无截图任务（site_capture=False 或 catch_all）写入空串时，SyncAsset 会保留存量截图，不应产生虚假变动
        if k == "screenshot" and not v:
            continue
        old_v = old_item.get(k)
        if old_v != v:
            diff[k] = {"before": old_v, "after": v}
    return diff

def tag_monitor_diff(collection_name, item):
    """
    Hook to dynamically tag real-time monitor diffs before insertion.
    """
    if not item or not isinstance(item, dict): return
    if collection_name.startswith("asset_"):
        category = collection_name[6:]
    else:
        category = collection_name
        
    task_id = item.get("task_id")
    # Only tag for newly scanned items belonging to a task (not sync operations)
    if not task_id or "scope_id" in item:
        return
        
    scope_id = _get_task_scope_id(task_id)
    if not scope_id:
        return
        
    query = _get_baseline_query(category, item, scope_id)
    if not query:
        return
        
    old_item = conn_db("asset_" + category).find_one(query)
    if not old_item:
        item["change_status"] = "new"
    else:
        diff = _compute_update_diff(old_item, item)
        if diff:
            item["change_status"] = "update"
            item["update_diff"] = diff
        else:
            item["change_status"] = "unchanged"

def log_monitor_diff_summary(task_id):
    """
    Summarize and write to the syslog table via logger.
    """
    if not task_id: return
    scope_id = _get_task_scope_id(task_id)
    if not scope_id:
        return # Not a monitor task
        
    import app.utils
    logger = app.utils.get_logger()
    
    categories = [
        "site", "domain", "ip", "wih", "cert", "service", 
        "fileleak", "url", "vuln", "npoc_service", "cip", 
        "nuclei_result", "stat_finger"
    ]
    
    summary = []
    total_new = 0
    total_update = 0
    
    for cat in categories:
        new_cnt = conn_db(cat).count_documents({"task_id": task_id, "change_status": "new"})
        upd_cnt = conn_db(cat).count_documents({"task_id": task_id, "change_status": "update"})
        
        if new_cnt > 0 or upd_cnt > 0:
            total_new += new_cnt
            total_update += upd_cnt
            parts = []
            if new_cnt > 0: parts.append(f"新增 {new_cnt} 个")
            if upd_cnt > 0: parts.append(f"变动 {upd_cnt} 个")
            summary.append(f"{cat}({', '.join(parts)})")
            
    if total_new == 0 and total_update == 0:
        logger.info("[监控对比] 本次任务未发现任何资产变动或新增。")
    else:
        logger.info(f"[监控对比] 本次任务共发现新增资产 {total_new} 项，变动 {total_update} 项。详情：{'；'.join(summary)}。")

