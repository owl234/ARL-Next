from contextlib import contextmanager
import contextvars
import ipaddress
import os
import re
import shutil
import sys
import threading
from concurrent.futures import as_completed
from urllib.parse import urlparse

from bson import ObjectId
from pymongo import UpdateOne

from app import utils
from app.modules import AssetScopeType, ErrorMsg, SchedulerStatus, TaskStatus
from app.utils import ContextAwareThreadPoolExecutor, get_logger
from app.utils.IPy import IP
from app.utils.domain import is_in_scopes, is_valid_domain
from app.utils.ip import ip_in_scope

logger = get_logger()

_DB_GETTER_VAR = contextvars.ContextVar("_cascade_db_getter", default=None)


def _db(collection):
    getter = _DB_GETTER_VAR.get()
    if getter is not None:
        return getter(collection)
    return utils.conn_db(collection)


@contextmanager
def _use_db_getter(db_getter):
    if db_getter is None:
        yield
        return
    token = _DB_GETTER_VAR.set(db_getter)
    try:
        yield
    finally:
        _DB_GETTER_VAR.reset(token)

UNPREFIXED_COLLECTIONS = (
    "site",
    "domain",
    "ip",
    "cert",
    "service",
    "fileleak",
    "url",
    "vuln",
    "npoc_service",
    "cip",
    "nuclei_result",
    "stat_finger",
    "wih",
)

ASSET_COLLECTIONS = tuple(f"asset_{c}" for c in UNPREFIXED_COLLECTIONS)

MAX_BATCH_DELETE_SIZE = 500
CHUNK_SIZE = 1000

_DASHBOARD_CACHE_VERSION_ID = "_dashboard_cache_version"
_TASK_SCOPE_CACHE_VERSION_ID = "_task_scope_cache_version"

_EXECUTOR_LOCK = threading.Lock()
_SHARED_EXECUTOR = None
_SHARED_EXECUTOR_PID = None
_SHARED_EXECUTOR_MAX_WORKERS = 12


def get_shared_executor():
    """
    PID 感知的进程级共享有界线程池。
    兼容 gunicorn --preload 的 fork() 模型：若子进程 PID 变化则懒加载重建线程池，规避 fork 锁死锁。
    """
    global _SHARED_EXECUTOR, _SHARED_EXECUTOR_PID
    pid = os.getpid()
    if _SHARED_EXECUTOR is not None and _SHARED_EXECUTOR_PID == pid:
        return _SHARED_EXECUTOR
    with _EXECUTOR_LOCK:
        if _SHARED_EXECUTOR is None or _SHARED_EXECUTOR_PID != pid:
            _SHARED_EXECUTOR = ContextAwareThreadPoolExecutor(max_workers=_SHARED_EXECUTOR_MAX_WORKERS)
            _SHARED_EXECUTOR_PID = pid
        return _SHARED_EXECUTOR


def bump_asset_cache_versions():
    """
    原子递增跨进程缓存版本号（仪表盘缓存 + 监控对比任务归属缓存），
    同时清空当前进程本地缓存，保障多 Worker 下立即可见。
    """
    for doc_id in (_DASHBOARD_CACHE_VERSION_ID, _TASK_SCOPE_CACHE_VERSION_ID):
        try:
            _db("system_config").update_one(
                {"_id": doc_id},
                {"$inc": {"version": 1}},
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"Failed to bump cache version {doc_id}: {e}")

    dashboard_mod = sys.modules.get("app.routes.dashboard")
    if dashboard_mod and hasattr(dashboard_mod, "clear_local_dashboard_cache"):
        try:
            dashboard_mod.clear_local_dashboard_cache()
        except Exception:
            pass

    monitor_diff_mod = sys.modules.get("app.utils.monitor_diff")
    if monitor_diff_mod and hasattr(monitor_diff_mod, "clear_task_scope_cache"):
        try:
            monitor_diff_mod.clear_task_scope_cache()
        except Exception:
            pass


def _chunked(seq, size=CHUNK_SIZE):
    items = list(seq)
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _extract_host_from_target(value):
    if not value or not isinstance(value, str):
        return ""
    raw = value.strip()
    if not raw:
        return ""
    if "://" in raw:
        try:
            parsed = urlparse(raw)
            if parsed.hostname:
                return parsed.hostname.lower().strip(".")
        except Exception:
            pass
    # 无 scheme 的 host:port 或 [ipv6]:port
    if raw.startswith("["):
        end = raw.find("]")
        if end != -1:
            return raw[1:end].lower()
    if "/" in raw:
        raw = raw.split("/", 1)[0]
    if "?" in raw:
        raw = raw.split("?", 1)[0]
    if raw.count(":") == 1:
        host_part, port_part = raw.rsplit(":", 1)
        if port_part.isdigit():
            raw = host_part
    return raw.lower().strip(".")


def _normalize_scope_arrays(scope_doc):
    if not scope_doc:
        return [], [], []
    scope_array = list(scope_doc.get("scope_array") or [])
    domain_array = scope_doc.get("domain_array")
    ip_array = scope_doc.get("ip_array")
    if domain_array is None or ip_array is None:
        st = scope_doc.get("scope_type")
        d_arr, i_arr = [], []
        for x in scope_array:
            if utils.is_vaild_ip_target(x):
                i_arr.append(x)
            elif is_valid_domain(x):
                d_arr.append(x)
            elif st == AssetScopeType.IP:
                i_arr.append(x)
            else:
                d_arr.append(x)
        if domain_array is None:
            domain_array = d_arr
        if ip_array is None:
            ip_array = i_arr
    return scope_array, list(domain_array), list(ip_array)


def is_scope_target_alive(scope_id, target=None, strict_ip=False):
    """
    全链路存活栅栏（Pre-Commit Guard）：
    核验指定资产组是否依然存活；若传入 target（根域名/子域名/IP/CIDR/站点URL），
    进一步核验该目标是否仍落入资产组最新范围，阻断已删资产组或已剔除根目标的在途任务脏写。
    """
    if not scope_id or not ObjectId.is_valid(str(scope_id)):
        return False
    try:
        scope_doc = _db("asset_scope").find_one(
            {"_id": ObjectId(str(scope_id))},
            {"scope_array": 1, "domain_array": 1, "ip_array": 1, "scope_type": 1},
        )
    except Exception as e:
        logger.warning(f"is_scope_target_alive DB check failed for scope {scope_id}: {e}")
        return False

    if not scope_doc:
        return False

    if target is None:
        return True

    scope_array, domain_array, ip_array = _normalize_scope_arrays(scope_doc)
    raw = str(target).strip()
    if not raw:
        return True

    # 支持空格分隔的多目标字符串（如复合 IP 监控）
    tokens = raw.split() if (" " in raw and "://" not in raw) else [raw]
    for tok in tokens:
        tok_lower = tok.strip().lower()
        if not tok_lower:
            continue
        if tok_lower in scope_array:
            return True

        host = _extract_host_from_target(tok_lower)
        if not host:
            continue

        if host in scope_array:
            return True

        if utils.is_vaild_ip_target(host):
            if ip_array and ip_in_scope(host, ip_array):
                return True
            if not strict_ip and domain_array:
                # 域名型资产组中，若该 IP 仍被组内存活子域名解析引用，则允许其直连站点/WIH 写入
                try:
                    ref_dom = _db("asset_domain").find_one(
                        {"scope_id": str(scope_id), "ips": host},
                        {"domain": 1, "_id": 0},
                    )
                    if ref_dom and is_in_scopes(ref_dom.get("domain", ""), domain_array):
                        return True
                except Exception:
                    pass
            continue

        if is_valid_domain(host) and domain_array and is_in_scopes(host, domain_array):
            return True

    return False


def _get_scope_scheduler_ids(scope_ids):
    sids = [str(s) for s in scope_ids if s]
    if not sids:
        return []
    result = []
    for chunk in _chunked(sids):
        for doc in _db("scheduler").find({"scope_id": {"$in": chunk}}, {"_id": 1}):
            result.append(str(doc["_id"]))
    return result


def get_bound_task_ids(scope_ids, extra_scheduler_ids=None):
    """
    严格依据显式绑定字段检索归属指定资产组的任务 ID 集合。
    绝不通过 target 文本模糊匹配未绑定独立扫描任务。
    """
    sids = list(dict.fromkeys(str(s) for s in scope_ids if s))
    if not sids and not extra_scheduler_ids:
        return []

    sch_ids = set(_get_scope_scheduler_ids(sids)) if sids else set()
    if extra_scheduler_ids:
        sch_ids.update(str(x) for x in extra_scheduler_ids if x)

    task_ids = set()
    or_clauses = []
    if sids:
        for chunk in _chunked(sids):
            or_clauses.extend([
                {"scope_id": {"$in": chunk}},
                {"sync_scope_id": {"$in": chunk}},
                {"synced_scope_id": {"$in": chunk}},
                {"options.scope_id": {"$in": chunk}},
                {"options.related_scope_id": {"$in": chunk}},
            ])
    if sch_ids:
        for chunk in _chunked(list(sch_ids)):
            or_clauses.append({"options.scheduler_id": {"$in": chunk}})

    if not or_clauses:
        return []

    for doc in _db("task").find({"$or": or_clauses}, {"_id": 1}):
        task_ids.add(str(doc["_id"]))
    return list(task_ids)


def get_task_bound_scope_ids(task_ids):
    """查询指定任务列表显式绑定的存活资产组 ID 集合。"""
    tids = list(dict.fromkeys(str(t) for t in task_ids if t and ObjectId.is_valid(str(t))))
    if not tids:
        return []

    candidate_scope_ids = set()
    scheduler_ids = set()
    for chunk in _chunked(tids):
        obj_ids = [ObjectId(t) for t in chunk]
        for doc in _db("task").find(
            {"_id": {"$in": obj_ids}},
            {
                "scope_id": 1,
                "sync_scope_id": 1,
                "synced_scope_id": 1,
                "options.scope_id": 1,
                "options.related_scope_id": 1,
                "options.scheduler_id": 1,
            },
        ):
            opts = doc.get("options") if isinstance(doc.get("options"), dict) else {}
            for cand in (
                doc.get("scope_id"),
                doc.get("sync_scope_id"),
                doc.get("synced_scope_id"),
                opts.get("scope_id"),
                opts.get("related_scope_id"),
            ):
                if cand and ObjectId.is_valid(str(cand)):
                    candidate_scope_ids.add(str(cand))
            sch_id = opts.get("scheduler_id")
            if sch_id and ObjectId.is_valid(str(sch_id)):
                scheduler_ids.add(str(sch_id))

    if scheduler_ids:
        for chunk in _chunked(list(scheduler_ids)):
            for doc in _db("scheduler").find(
                {"_id": {"$in": [ObjectId(s) for s in chunk]}},
                {"scope_id": 1},
            ):
                sid = doc.get("scope_id")
                if sid and ObjectId.is_valid(str(sid)):
                    candidate_scope_ids.add(str(sid))

    if not candidate_scope_ids:
        return []

    alive_scope_ids = []
    for chunk in _chunked(list(candidate_scope_ids)):
        for doc in _db("asset_scope").find(
            {"_id": {"$in": [ObjectId(s) for s in chunk]}},
            {"_id": 1},
        ):
            alive_scope_ids.append(str(doc["_id"]))
    return alive_scope_ids


def _revoke_celery_tasks(celery_ids):
    valid_ids = list(dict.fromkeys(
        str(cid).strip()
        for cid in (celery_ids or [])
        if cid and str(cid).strip() and str(cid).strip() != "celery_id_placeholder"
    ))
    if not valid_ids:
        return
    try:
        from app import celerytask
        control = celerytask.celery.control
    except Exception as e:
        logger.warning(f"Failed to acquire Celery control for revoke: {e}")
        return

    for cid in valid_ids:
        try:
            control.revoke(cid, terminate=True, signal="SIGTERM", reply=False)
        except Exception as e:
            logger.warning(f"Failed to revoke celery task {cid}: {e}")


def _cleanup_unreferenced_screenshots(task_ids=None, screenshot_paths=None):
    """回收不再被 site 或 asset_site 引用的物理截图目录或单张截图文件。"""
    from app.config import Config
    screenshot_root = os.path.realpath(Config.SCREENSHOT_DIR)

    for tid in list(dict.fromkeys(str(t) for t in (task_ids or []) if t)):
        try:
            ref_query = {
                "$or": [
                    {"task_id": tid},
                    {"screenshot": {"$gte": f"/image/{tid}/", "$lt": f"/image/{tid}0"}},
                ]
            }
            if _db("asset_site").find_one(ref_query, {"_id": 1}):
                continue
            if _db("site").find_one(ref_query, {"_id": 1}):
                continue
            target_dir = os.path.realpath(os.path.join(screenshot_root, tid))
            if target_dir.startswith(screenshot_root + os.sep) and os.path.exists(target_dir):
                shutil.rmtree(target_dir, ignore_errors=True)
        except Exception as e:
            logger.warning(f"Failed to clean screenshot dir for task {tid}: {e}")

    for rel_path in list(dict.fromkeys(str(p).strip() for p in (screenshot_paths or []) if p and isinstance(p, str))):
        if not rel_path.startswith("/image/"):
            continue
        try:
            if _db("asset_site").find_one({"screenshot": rel_path}, {"_id": 1}):
                continue
            if _db("site").find_one({"screenshot": rel_path}, {"_id": 1}):
                continue
            sub_path = rel_path[len("/image/"):].lstrip("/")
            full_path = os.path.realpath(os.path.join(screenshot_root, sub_path))
            if full_path.startswith(screenshot_root + os.sep) and os.path.isfile(full_path):
                os.unlink(full_path)
        except Exception as e:
            logger.warning(f"Failed to clean screenshot file {rel_path}: {e}")


def recalculate_tasks_statistics(task_ids):
    """
    恒定 O(13) 聚合批处理重算多任务 task.statistic。
    使用进程级共享线程池在 13 张无前缀表并发分组计数，合并后单次 bulk_write 回写（包含计数归零）。
    """
    valid_tids = list(dict.fromkeys(str(t) for t in (task_ids or []) if t and ObjectId.is_valid(str(t))))
    if not valid_tids:
        return {}

    stats_by_tid = {
        tid: {f"{col}_cnt": 0 for col in UNPREFIXED_COLLECTIONS}
        for tid in valid_tids
    }

    def _agg_collection(col_name):
        counts = {}
        for chunk in _chunked(valid_tids):
            pipeline = [
                {"$match": {"task_id": {"$in": chunk}}},
                {"$group": {"_id": "$task_id", "cnt": {"$sum": 1}}},
            ]
            for doc in _db(col_name).aggregate(pipeline):
                tid = doc.get("_id")
                if tid is not None:
                    counts[str(tid)] = counts.get(str(tid), 0) + int(doc.get("cnt", 0))
        return col_name, counts

    executor = get_shared_executor()
    futures = [executor.submit(_agg_collection, col) for col in UNPREFIXED_COLLECTIONS]
    for fut in as_completed(futures):
        try:
            col_name, col_counts = fut.result()
            stat_key = f"{col_name}_cnt"
            for tid, cnt in col_counts.items():
                if tid in stats_by_tid:
                    stats_by_tid[tid][stat_key] = cnt
        except Exception as e:
            logger.error(f"Failed to aggregate task statistic: {e}")

    ops = [
        UpdateOne({"_id": ObjectId(tid)}, {"$set": {"statistic": stat}})
        for tid, stat in stats_by_tid.items()
    ]
    for chunk in _chunked(ops):
        try:
            _db("task").bulk_write(chunk, ordered=False)
        except Exception as e:
            logger.error(f"Failed to bulk write recalculated task statistics: {e}")

    return stats_by_tid


def _rebuild_derived_for_owner(
    owner_field,
    owner_id,
    is_asset,
    targets=("cip", "stat_finger", "service"),
    preserve_existing_npoc=True,
):
    """
    基于存活宿主表全量重算单个作用域（资产组或任务）的三大派生集合：
      - cip / asset_cip：双向归并 ip + domain 生成 /24 C 段统计
      - stat_finger / asset_stat_finger：从 site.finger 聚合真实指纹计数（兼容 dict 与 str）
      - service / asset_service：从 ip.port_info 聚合去重 (ip, port_id) 端点列表
    """
    prefix = "asset_" if is_asset else ""
    target_set = set(targets)
    now = utils.curr_date_obj()

    # 若需重算 cip 或 service，仅读取一次 ip 宿主表减少 I/O
    ip_docs = None
    if "cip" in target_set or "service" in target_set:
        proj = {"ip": 1, "save_date": 1, "update_date": 1, "_id": 0}
        if "cip" in target_set:
            proj["domain"] = 1
        if "service" in target_set:
            proj["port_info"] = 1
        ip_docs = list(_db(f"{prefix}ip").find({owner_field: owner_id}, proj))

    def _pick_min_dt(a, b):
        da = utils.to_datetime_obj(a)
        db = utils.to_datetime_obj(b)
        if da and db:
            return min(da, db)
        return da or db

    def _pick_max_dt(a, b):
        da = utils.to_datetime_obj(a)
        db = utils.to_datetime_obj(b)
        if da and db:
            return max(da, db)
        return da or db

    # 1. 重算 cip / asset_cip
    if "cip" in target_set:
        ip_domains_map = {}
        ip_time_map = {}
        for doc in ip_docs:
            ip_val = doc.get("ip")
            if not ip_val or ":" in str(ip_val):
                continue
            ip_str = str(ip_val).strip()
            dom_set = ip_domains_map.setdefault(ip_str, set())
            raw_doms = doc.get("domain")
            if isinstance(raw_doms, list):
                dom_set.update(d for d in raw_doms if isinstance(d, str) and d)
            elif isinstance(raw_doms, str) and raw_doms:
                dom_set.add(raw_doms)
            ts_entry = ip_time_map.setdefault(ip_str, {"save": None, "upd": None})
            ts_entry["save"] = _pick_min_dt(ts_entry["save"], doc.get("save_date"))
            ts_entry["upd"] = _pick_max_dt(ts_entry["upd"], doc.get("update_date") or doc.get("save_date"))

        if ip_domains_map:
            for d_doc in _db(f"{prefix}domain").find(
                {owner_field: owner_id},
                {"domain": 1, "ips": 1, "_id": 0},
            ):
                d_name = d_doc.get("domain")
                d_ips = d_doc.get("ips")
                if not d_name or not isinstance(d_ips, list):
                    continue
                for d_ip in d_ips:
                    if d_ip in ip_domains_map:
                        ip_domains_map[d_ip].add(d_name)

        cip_map = {}
        for ip_str, dom_set in ip_domains_map.items():
            try:
                cidr = IP(f"{ip_str}/24", make_net=True).strNormal(1)
            except Exception:
                continue
            entry = cip_map.setdefault(cidr, {"ip_set": set(), "domain_set": set(), "save": None, "upd": None})
            entry["ip_set"].add(ip_str)
            entry["domain_set"].update(dom_set)
            ip_ts = ip_time_map.get(ip_str) or {}
            entry["save"] = _pick_min_dt(entry["save"], ip_ts.get("save"))
            entry["upd"] = _pick_max_dt(entry["upd"], ip_ts.get("upd"))

        cip_col = _db(f"{prefix}cip")
        desired_cidrs = set(cip_map.keys())
        existing_cip_map = {
            doc.get("cidr_ip"): doc
            for doc in cip_col.find({owner_field: owner_id}, {"cidr_ip": 1, "save_date": 1, "update_date": 1, "_id": 0})
            if doc.get("cidr_ip")
        }
        stale_cidrs = list(set(existing_cip_map.keys()) - desired_cidrs)
        if stale_cidrs:
            for chunk in _chunked(stale_cidrs):
                cip_col.delete_many({owner_field: owner_id, "cidr_ip": {"$in": chunk}})

        ops = []
        for cidr, info in cip_map.items():
            ip_list = sorted(info["ip_set"])
            domain_list = sorted(info["domain_set"])
            ex_doc = existing_cip_map.get(cidr) or {}
            min_save = _pick_min_dt(ex_doc.get("save_date"), info["save"]) or now
            max_upd = _pick_max_dt(ex_doc.get("update_date"), info["upd"]) or min_save
            set_doc = {
                owner_field: owner_id,
                "cidr_ip": cidr,
                "ip_list": ip_list,
                "ip_count": len(ip_list),
                "domain_list": domain_list,
                "domain_count": len(domain_list),
            }
            update_spec = {"$set": set_doc, "$setOnInsert": {"save_date": min_save}}
            if is_asset:
                set_doc["update_date"] = max_upd
            ops.append(UpdateOne({owner_field: owner_id, "cidr_ip": cidr}, update_spec, upsert=True))
        for chunk in _chunked(ops):
            cip_col.bulk_write(chunk, ordered=False)

    # 2. 重算 stat_finger / asset_stat_finger
    if "stat_finger" in target_set:
        finger_map = {}
        for s_doc in _db(f"{prefix}site").find({owner_field: owner_id}, {"finger": 1, "save_date": 1, "update_date": 1, "_id": 0}):
            fingers = s_doc.get("finger")
            if not isinstance(fingers, list):
                continue
            s_save = s_doc.get("save_date")
            s_upd = s_doc.get("update_date") or s_save
            seen_in_site = set()
            for item in fingers:
                if isinstance(item, dict):
                    fname = item.get("name")
                elif isinstance(item, str):
                    fname = item
                else:
                    fname = None
                if not fname or not isinstance(fname, str):
                    continue
                key = fname.lower()
                if key in seen_in_site:
                    continue
                seen_in_site.add(key)
                if key not in finger_map:
                    finger_map[key] = {"name": fname, "cnt": 1, "save": utils.to_datetime_obj(s_save), "upd": utils.to_datetime_obj(s_upd)}
                else:
                    finger_map[key]["cnt"] += 1
                    finger_map[key]["save"] = _pick_min_dt(finger_map[key]["save"], s_save)
                    finger_map[key]["upd"] = _pick_max_dt(finger_map[key]["upd"], s_upd)

        sf_col = _db(f"{prefix}stat_finger")
        desired_info = {v["name"]: v for v in finger_map.values()}
        existing_sf_map = {
            doc.get("name"): doc
            for doc in sf_col.find({owner_field: owner_id}, {"name": 1, "save_date": 1, "update_date": 1, "_id": 0})
            if doc.get("name")
        }
        stale_names = list(set(existing_sf_map.keys()) - set(desired_info.keys()))
        if stale_names:
            for chunk in _chunked(stale_names):
                sf_col.delete_many({owner_field: owner_id, "name": {"$in": chunk}})

        ops = []
        for fname, info in desired_info.items():
            ex_doc = existing_sf_map.get(fname) or {}
            min_save = _pick_min_dt(ex_doc.get("save_date"), info["save"]) or now
            max_upd = _pick_max_dt(ex_doc.get("update_date"), info["upd"]) or min_save
            set_doc = {
                owner_field: owner_id,
                "name": fname,
                "cnt": info["cnt"],
            }
            update_spec = {"$set": set_doc, "$setOnInsert": {"save_date": min_save}}
            if is_asset:
                set_doc["update_date"] = max_upd
            ops.append(UpdateOne({owner_field: owner_id, "name": fname}, update_spec, upsert=True))
        for chunk in _chunked(ops):
            sf_col.bulk_write(chunk, ordered=False)

    # 3. 重算 service / asset_service（单端点模型：融合 ip.port_info 与 npoc_service）
    if "service" in target_set:
        from app.services.service_fusion import (
            build_service_endpoint_doc,
            expand_service_doc_to_endpoints,
            merge_endpoint_records,
            normalize_host,
            normalize_port,
        )

        endpoint_map = {}
        for doc in (ip_docs or []):
            ip_val = normalize_host(doc.get("ip"))
            port_info_list = doc.get("port_info")
            if not ip_val or not isinstance(port_info_list, list):
                continue
            doc_save = utils.to_datetime_obj(doc.get("save_date"))
            doc_upd = utils.to_datetime_obj(doc.get("update_date")) or doc_save
            for p in port_info_list:
                if not isinstance(p, dict):
                    continue
                svc_name = p.get("service_name")
                port_id = normalize_port(p.get("port_id"))
                if not svc_name or port_id is None:
                    continue
                ep_key = (ip_val, port_id)
                raw_port_sources = p.get("sources") or ["nmap"]
                if not preserve_existing_npoc:
                    raw_port_sources = [s for s in raw_port_sources if s != "npoc"] or ["nmap"]
                ep_doc = build_service_endpoint_doc(
                    owner_field=owner_field,
                    owner_id=owner_id,
                    ip=ip_val,
                    port_id=port_id,
                    service_name=svc_name,
                    product=p.get("product") or "",
                    version=p.get("version") or "",
                    target=p.get("target") or "",
                    sources=raw_port_sources,
                    save_date=doc_save,
                    update_date=doc_upd,
                )
                endpoint_map[ep_key] = merge_endpoint_records(endpoint_map.get(ep_key), ep_doc)

        for npoc_doc in _db(f"{prefix}npoc_service").find({owner_field: owner_id}):
            for npoc_ep in expand_service_doc_to_endpoints(npoc_doc, default_source="npoc"):
                ep_key = (npoc_ep["ip"], npoc_ep["port_id"])
                endpoint_map[ep_key] = merge_endpoint_records(
                    endpoint_map.get(ep_key),
                    npoc_ep,
                    prefer_incoming_service=True,
                )

        svc_col = _db(f"{prefix}service")
        stale_doc_ids = []
        for ex_doc in svc_col.find({owner_field: owner_id}):
            ex_ip = normalize_host(ex_doc.get("ip"))
            ex_port = normalize_port(ex_doc.get("port_id"))
            ex_infos = ex_doc.get("service_info")
            is_legacy_grouped = not ex_ip or ex_port is None or (isinstance(ex_infos, list) and len(ex_infos) > 1)
            if is_legacy_grouped:
                stale_doc_ids.append(ex_doc["_id"])
                continue
            ep_key = (ex_ip, ex_port)
            if ep_key not in endpoint_map:
                stale_doc_ids.append(ex_doc["_id"])
            else:
                # 保留存量端点的最早 save_date、最新 update_date 及已归并的 npoc 来源（npoc_service 显式删除重算时除外）
                cur = endpoint_map[ep_key]
                cur["save_date"] = _pick_min_dt(ex_doc.get("save_date"), cur.get("save_date"))
                cur["update_date"] = _pick_max_dt(ex_doc.get("update_date"), cur.get("update_date"))
                if preserve_existing_npoc and "npoc" in (ex_doc.get("sources") or []):
                    endpoint_map[ep_key] = merge_endpoint_records(ex_doc, cur)

        if stale_doc_ids:
            for chunk in _chunked(stale_doc_ids):
                svc_col.delete_many({"_id": {"$in": chunk}})

        ops = []
        for (ip_val, port_id), ep_doc in endpoint_map.items():
            set_doc = dict(ep_doc)
            set_doc.pop("_id", None)
            set_doc[owner_field] = owner_id
            saved_ts = utils.to_datetime_obj(set_doc.pop("save_date", None)) or now
            upd_ts = utils.to_datetime_obj(set_doc.pop("update_date", None)) or saved_ts
            if is_asset:
                set_doc["update_date"] = upd_ts
                update_spec = {
                    "$set": set_doc,
                    "$setOnInsert": {"save_date": saved_ts},
                }
            else:
                update_spec = {
                    "$set": set_doc,
                    "$setOnInsert": {"save_date": saved_ts},
                }
            ops.append(
                UpdateOne(
                    {owner_field: owner_id, "ip": ip_val, "port_id": port_id},
                    update_spec,
                    upsert=True,
                )
            )
        for chunk in _chunked(ops):
            svc_col.bulk_write(chunk, ordered=False)


def rebuild_scope_derived_collections(scope_ids, targets=("cip", "stat_finger", "service"), preserve_existing_npoc=True):
    """基于存活宿主表重算指定资产组的 asset_cip / asset_stat_finger / asset_service。"""
    unique_sids = list(dict.fromkeys(str(s) for s in (scope_ids or []) if s))
    for sid in unique_sids:
        try:
            _rebuild_derived_for_owner(
                "scope_id", sid, is_asset=True, targets=targets, preserve_existing_npoc=preserve_existing_npoc
            )
        except Exception as e:
            logger.error(f"rebuild_scope_derived_collections failed for scope {sid}: {e}")


def rebuild_task_derived_collections(task_ids, targets=("cip", "stat_finger", "service"), preserve_existing_npoc=True):
    """基于存活宿主表重算指定任务的 cip / stat_finger / service。"""
    unique_tids = list(dict.fromkeys(str(t) for t in (task_ids or []) if t))
    for tid in unique_tids:
        try:
            _rebuild_derived_for_owner(
                "task_id", tid, is_asset=False, targets=targets, preserve_existing_npoc=preserve_existing_npoc
            )
        except Exception as e:
            logger.error(f"rebuild_task_derived_collections failed for task {tid}: {e}")


def _refresh_scopes_domain_status(scope_ids):
    from app.helpers.scope import get_scope_domain_stat
    for sid in list(dict.fromkeys(str(s) for s in (scope_ids or []) if s and ObjectId.is_valid(str(s)))):
        try:
            scope_doc = _db("asset_scope").find_one({"_id": ObjectId(sid)})
            if scope_doc:
                get_scope_domain_stat(scope_doc, auto_persist=True)
        except Exception as e:
            logger.warning(f"Failed to refresh domain_status for scope {sid}: {e}")


def _build_url_prefix_clauses(field, base_urls, include_port_colon=False):
    """
    构建带严格定界符的 URL 前缀范围查询条件（B-tree 索引友好）：
      - 精确匹配 u 与 u + "/"
      - 路径子项：[u + "/", u + "0")  (ASCII '/'=47, '0'=48)
      - 查询子项：[u + "?", u + "@")  (ASCII '?'=63, '@'=64)
      - 锚点子项：[u + "#", u + "$")  (ASCII '#'=35, '$'=36)
      - 可选端口子项（仅 L1 域名/IP 级联使用）：[u + ":", u + ";") (ASCII ':'=58, ';'=59)
    杜绝 http://a.com 误匹配 http://a.com.evil.com 或 L2 删站误伤 http://a.com:8080。
    """
    exact_values = []
    clauses = []
    seen_bases = set()

    for raw in base_urls:
        if not raw or not isinstance(raw, str):
            continue
        u = raw.strip().rstrip("/")
        if not u or u in seen_bases:
            continue
        seen_bases.add(u)
        exact_values.append(u)
        exact_values.append(u + "/")
        clauses.append({field: {"$gte": u + "/", "$lt": u + "0"}})
        clauses.append({field: {"$gte": u + "?", "$lt": u + "@"}})
        clauses.append({field: {"$gte": u + "#", "$lt": u + "$"}})
        if include_port_colon:
            clauses.append({field: {"$gte": u + ":", "$lt": u + ";"}})

    if exact_values:
        clauses.insert(0, {field: {"$in": exact_values}})
    return clauses


def _build_host_exact_or_port_clauses(field, hosts):
    """构建 hostname/host/target 精确或 host:port 定界符范围条件（不匹配 host.evil.com）。"""
    exact_vals = []
    clauses = []
    seen = set()
    for raw in hosts:
        if not raw or not isinstance(raw, str):
            continue
        h = raw.strip().lower()
        if not h or h in seen:
            continue
        seen.add(h)
        host_fmt = f"[{h}]" if (":" in h and not h.startswith("[")) else h
        exact_vals.append(h)
        if host_fmt != h:
            exact_vals.append(host_fmt)
        clauses.append({field: {"$gte": f"{host_fmt}:", "$lt": f"{host_fmt};"}})
    if exact_vals:
        clauses.insert(0, {field: {"$in": exact_vals}})
    return clauses


def _build_host_url_bases(hosts):
    bases = []
    for raw in hosts:
        if not raw or not isinstance(raw, str):
            continue
        h = raw.strip().lower()
        if not h:
            continue
        host_fmt = f"[{h}]" if (":" in h and not h.startswith("[")) else h
        bases.append(f"http://{host_fmt}")
        bases.append(f"https://{host_fmt}")
    return bases


def _apply_scope_filter(base_query, owner_field=None, owner_ids=None):
    if not owner_field:
        return base_query
    if not owner_ids:
        return None
    if len(owner_ids) == 1:
        owner_cond = {owner_field: owner_ids[0]}
    else:
        owner_cond = {owner_field: {"$in": list(owner_ids)}}
    if not base_query:
        return owner_cond
    return {"$and": [owner_cond, base_query]}


def _delete_with_owner_tracking(col_name, match_query, owner_field=None, owner_ids=None, track_field=None, extra_proj=None):
    """
    在指定作用域内删除匹配文档，并在删除前以窄投影收集受影响的 owner ID 及附加字段（如 screenshot）。
    """
    affected_owners = set()
    collected_docs = []

    if owner_field and owner_ids is not None:
        if not owner_ids:
            return 0, affected_owners, collected_docs
        total_deleted = 0
        for chunk in _chunked(owner_ids):
            q = _apply_scope_filter(match_query, owner_field, chunk)
            if track_field or extra_proj:
                proj = {"_id": 0}
                if track_field:
                    proj[track_field] = 1
                if extra_proj:
                    for k in extra_proj:
                        proj[k] = 1
                for doc in _db(col_name).find(q, proj):
                    if track_field and doc.get(track_field):
                        affected_owners.add(str(doc[track_field]))
                    if extra_proj:
                        collected_docs.append(doc)
            res = _db(col_name).delete_many(q)
            total_deleted += getattr(res, "deleted_count", 0)
        return total_deleted, affected_owners, collected_docs

    # 全局模式（无 owner_field 限制）
    if track_field or extra_proj:
        proj = {"_id": 0}
        if track_field:
            proj[track_field] = 1
        if extra_proj:
            for k in extra_proj:
                proj[k] = 1
        for doc in _db(col_name).find(match_query, proj):
            if track_field and doc.get(track_field):
                affected_owners.add(str(doc[track_field]))
            if extra_proj:
                collected_docs.append(doc)
    res = _db(col_name).delete_many(match_query)
    return getattr(res, "deleted_count", 0), affected_owners, collected_docs


def _cascade_delete_l3_for_sites_and_hosts(
    site_urls,
    hosts,
    is_asset,
    owner_ids=None,
    global_mode=False,
    include_port_colon=False,
):
    """按精确 site URL 集合（以及可选的 L1 host 集合）向下清理 5 张 L3 表（url/fileleak/wih/vuln/nuclei_result）。"""
    prefix = "asset_" if is_asset else ""
    owner_field = None if global_mode else ("scope_id" if is_asset else "task_id")
    track_field = "scope_id" if is_asset else "task_id"
    affected_owners = set()

    clean_sites = list(dict.fromkeys(u.strip().rstrip("/") for u in (site_urls or []) if u and isinstance(u, str)))
    clean_hosts = list(dict.fromkeys(h.strip().lower() for h in (hosts or []) if h and isinstance(h, str)))
    host_url_bases = _build_host_url_bases(clean_hosts) if clean_hosts else []

    if not clean_sites and not clean_hosts:
        return affected_owners

    site_variants = []
    for u in clean_sites:
        site_variants.append(u)
        site_variants.append(u + "/")

    # 1. url & fileleak
    for col in ("url", "fileleak"):
        or_clauses = []
        if site_variants:
            or_clauses.append({"site": {"$in": site_variants}})
            or_clauses.extend(_build_url_prefix_clauses("url", clean_sites, include_port_colon=False))
        if host_url_bases:
            or_clauses.extend(_build_url_prefix_clauses("site", host_url_bases, include_port_colon=include_port_colon))
            or_clauses.extend(_build_url_prefix_clauses("url", host_url_bases, include_port_colon=include_port_colon))
        if or_clauses:
            _, owners, _ = _delete_with_owner_tracking(
                f"{prefix}{col}",
                {"$or": or_clauses},
                owner_field=owner_field,
                owner_ids=owner_ids,
                track_field=track_field,
            )
            affected_owners.update(owners)

    # 2. wih
    wih_or = []
    if site_variants:
        wih_or.append({"site": {"$in": site_variants}})
        wih_or.extend(_build_url_prefix_clauses("site", clean_sites, include_port_colon=False))
    if host_url_bases:
        wih_or.extend(_build_url_prefix_clauses("site", host_url_bases, include_port_colon=include_port_colon))
    if clean_hosts:
        # 同步清理 WIH 发现的子域名记录（record_type == "domain" 且 content == domain）
        wih_or.append({"record_type": "domain", "content": {"$in": clean_hosts}})
    if wih_or:
        _, owners, _ = _delete_with_owner_tracking(
            f"{prefix}wih",
            {"$or": wih_or},
            owner_field=owner_field,
            owner_ids=owner_ids,
            track_field=track_field,
        )
        affected_owners.update(owners)

    # 3. vuln & nuclei_result
    for col in ("vuln", "nuclei_result"):
        or_clauses = []
        if site_variants:
            or_clauses.extend(_build_url_prefix_clauses("target", clean_sites, include_port_colon=False))
            or_clauses.extend(_build_url_prefix_clauses("vuln_url", clean_sites, include_port_colon=False))
            or_clauses.extend(_build_url_prefix_clauses("host", clean_sites, include_port_colon=False))
        if host_url_bases:
            or_clauses.extend(_build_url_prefix_clauses("target", host_url_bases, include_port_colon=include_port_colon))
            or_clauses.extend(_build_url_prefix_clauses("vuln_url", host_url_bases, include_port_colon=include_port_colon))
            or_clauses.extend(_build_url_prefix_clauses("host", host_url_bases, include_port_colon=include_port_colon))
        if clean_hosts:
            or_clauses.extend(_build_host_exact_or_port_clauses("target", clean_hosts))
            or_clauses.extend(_build_host_exact_or_port_clauses("host", clean_hosts))
        if or_clauses:
            _, owners, _ = _delete_with_owner_tracking(
                f"{prefix}{col}",
                {"$or": or_clauses},
                owner_field=owner_field,
                owner_ids=owner_ids,
                track_field=track_field,
            )
            affected_owners.update(owners)

    return affected_owners


def _cascade_delete_ips_in_side(target_ips, is_asset, owner_ids=None, global_mode=False):
    """在单侧（asset_* 或无前缀表）执行完整「删 IP」级联：删 IP -> 删站点/证书/npoc/L3 -> 解绑 domain.ips。"""
    ips = list(dict.fromkeys(str(ip).strip() for ip in (target_ips or []) if ip))
    if not ips:
        return set(), set()

    prefix = "asset_" if is_asset else ""
    owner_field = None if global_mode else ("scope_id" if is_asset else "task_id")
    track_field = "scope_id" if is_asset else "task_id"
    affected_owners = set()
    screenshots = set()

    # 1. 删除 ip / asset_ip
    _, owners, _ = _delete_with_owner_tracking(
        f"{prefix}ip",
        {"ip": {"$in": ips}},
        owner_field=owner_field,
        owner_ids=owner_ids,
        track_field=track_field,
    )
    affected_owners.update(owners)

    # 2. 查找并删除关联 site / asset_site（ip 字段匹配或 hostname/URL 为该 IP 直连）
    site_or = [{"ip": {"$in": ips}}]
    site_or.extend(_build_host_exact_or_port_clauses("hostname", ips))
    site_or.extend(_build_url_prefix_clauses("site", _build_host_url_bases(ips), include_port_colon=True))
    _, s_owners, s_docs = _delete_with_owner_tracking(
        f"{prefix}site",
        {"$or": site_or},
        owner_field=owner_field,
        owner_ids=owner_ids,
        track_field=track_field,
        extra_proj=("site", "screenshot"),
    )
    affected_owners.update(s_owners)
    deleted_sites = []
    for d in s_docs:
        if d.get("site"):
            deleted_sites.append(d["site"])
        if d.get("screenshot"):
            screenshots.add(d["screenshot"])

    # 3. 删除 cert / asset_cert
    _, c_owners, _ = _delete_with_owner_tracking(
        f"{prefix}cert",
        {"ip": {"$in": ips}},
        owner_field=owner_field,
        owner_ids=owner_ids,
        track_field=track_field,
    )
    affected_owners.update(c_owners)

    # 4. 删除 npoc_service / asset_npoc_service
    npoc_or = _build_host_exact_or_port_clauses("host", ips) + _build_host_exact_or_port_clauses("target", ips)
    if npoc_or:
        _, n_owners, _ = _delete_with_owner_tracking(
            f"{prefix}npoc_service",
            {"$or": npoc_or},
            owner_field=owner_field,
            owner_ids=owner_ids,
            track_field=track_field,
        )
        affected_owners.update(n_owners)

    # 5. 向下清理 L3
    l3_owners = _cascade_delete_l3_for_sites_and_hosts(
        site_urls=deleted_sites,
        hosts=ips,
        is_asset=is_asset,
        owner_ids=owner_ids,
        global_mode=global_mode,
        include_port_colon=True,
    )
    affected_owners.update(l3_owners)

    # 6. 向上解绑 domain.ips / asset_domain.ips（保留 domain 文档本身）
    dom_col = _db(f"{prefix}domain")
    if global_mode:
        for doc in dom_col.find({"ips": {"$in": ips}}, {track_field: 1, "_id": 0}):
            if doc.get(track_field):
                affected_owners.add(str(doc[track_field]))
        dom_col.update_many({"ips": {"$in": ips}}, {"$pull": {"ips": {"$in": ips}}})
    elif owner_ids:
        for chunk in _chunked(owner_ids):
            q = {owner_field: {"$in": chunk}, "ips": {"$in": ips}}
            for doc in dom_col.find(q, {track_field: 1, "_id": 0}):
                if doc.get(track_field):
                    affected_owners.add(str(doc[track_field]))
            dom_col.update_many(q, {"$pull": {"ips": {"$in": ips}}})

    return affected_owners, screenshots


def _cascade_delete_domains_in_side(target_domains, is_asset, owner_ids=None, global_mode=False):
    """
    在单侧（asset_* 或无前缀表）执行完整「删域名」级联：
      删 domain -> 删关联 site/npoc/L3(含 WIH domain 记录) -> 剥离 ip.domain 并回收孤儿 IP（完整复用删 IP 链路）。
    """
    domains = list(dict.fromkeys(str(d).strip().lower() for d in (target_domains or []) if d))
    if not domains:
        return set(), set()

    prefix = "asset_" if is_asset else ""
    owner_field = None if global_mode else ("scope_id" if is_asset else "task_id")
    track_field = "scope_id" if is_asset else "task_id"
    affected_owners = set()
    screenshots = set()

    # 1. 删除 domain / asset_domain（同时采集关联 ips 与归属 owner 用于孤儿 IP 判定）
    _, d_owners, d_docs = _delete_with_owner_tracking(
        f"{prefix}domain",
        {"domain": {"$in": domains}},
        owner_field=owner_field,
        owner_ids=owner_ids,
        track_field=track_field,
        extra_proj=("ips", track_field),
    )
    affected_owners.update(d_owners)

    candidate_ips_by_owner = {}
    for d in d_docs:
        oid = str(d.get(track_field) or "")
        ips = d.get("ips")
        if oid and isinstance(ips, list):
            candidate_ips_by_owner.setdefault(oid, set()).update(ip for ip in ips if isinstance(ip, str) and ip)

    # 2. 查找并删除 hostname 归属这些子域名的 site / asset_site
    site_or = _build_host_exact_or_port_clauses("hostname", domains)
    site_or.extend(_build_url_prefix_clauses("site", _build_host_url_bases(domains), include_port_colon=True))
    _, s_owners, s_docs = _delete_with_owner_tracking(
        f"{prefix}site",
        {"$or": site_or},
        owner_field=owner_field,
        owner_ids=owner_ids,
        track_field=track_field,
        extra_proj=("site", "screenshot"),
    )
    affected_owners.update(s_owners)
    deleted_sites = []
    for d in s_docs:
        if d.get("site"):
            deleted_sites.append(d["site"])
        if d.get("screenshot"):
            screenshots.add(d["screenshot"])

    # 3. 删除 npoc_service / asset_npoc_service
    npoc_or = _build_host_exact_or_port_clauses("host", domains) + _build_host_exact_or_port_clauses("target", domains)
    if npoc_or:
        _, n_owners, _ = _delete_with_owner_tracking(
            f"{prefix}npoc_service",
            {"$or": npoc_or},
            owner_field=owner_field,
            owner_ids=owner_ids,
            track_field=track_field,
        )
        affected_owners.update(n_owners)

    # 4. 向下清理 L3（含 WIH record_type='domain' 发现记录）
    l3_owners = _cascade_delete_l3_for_sites_and_hosts(
        site_urls=deleted_sites,
        hosts=domains,
        is_asset=is_asset,
        owner_ids=owner_ids,
        global_mode=global_mode,
        include_port_colon=True,
    )
    affected_owners.update(l3_owners)

    # 5. 从 ip.domain / asset_ip.domain 剥离被删域名，收集所有候选孤儿 IP
    ip_col = _db(f"{prefix}ip")
    if global_mode:
        ip_q = {"domain": {"$in": domains}}
        for doc in ip_col.find(ip_q, {"ip": 1, track_field: 1, "_id": 0}):
            oid = str(doc.get(track_field) or "")
            if oid and doc.get("ip"):
                candidate_ips_by_owner.setdefault(oid, set()).add(doc["ip"])
                affected_owners.add(oid)
        ip_col.update_many(ip_q, {"$pull": {"domain": {"$in": domains}}})
    elif owner_ids:
        for chunk in _chunked(owner_ids):
            ip_q = {owner_field: {"$in": chunk}, "domain": {"$in": domains}}
            for doc in ip_col.find(ip_q, {"ip": 1, track_field: 1, "_id": 0}):
                oid = str(doc.get(track_field) or "")
                if oid and doc.get("ip"):
                    candidate_ips_by_owner.setdefault(oid, set()).add(doc["ip"])
                    affected_owners.add(oid)
            ip_col.update_many(ip_q, {"$pull": {"domain": {"$in": domains}}})

    # 6. 精确判定孤儿 IP（逐个 owner 校验：① 无其他存活域名引用 ② 非直配 IP/纯 IP 任务）
    dom_col = _db(f"{prefix}domain")
    for oid, cand_ips in candidate_ips_by_owner.items():
        if not cand_ips:
            continue

        # 排除直配 IP 目标（资产组 CIDR 级 ip_in_scope / 任务 type == 'ip'）
        protected_ip_array = []
        if is_asset:
            if ObjectId.is_valid(oid):
                sc_doc = _db("asset_scope").find_one(
                    {"_id": ObjectId(oid)},
                    {"scope_array": 1, "domain_array": 1, "ip_array": 1, "scope_type": 1},
                )
                _, _, protected_ip_array = _normalize_scope_arrays(sc_doc)
        else:
            if ObjectId.is_valid(oid):
                t_doc = _db("task").find_one({"_id": ObjectId(oid)}, {"type": 1})
                if t_doc and t_doc.get("type") == "ip":
                    # 纯 IP 扫描任务中的 IP 绝不因删域名被当作孤儿回收
                    continue

        orphan_ips = []
        cand_list = list(cand_ips)
        for ip_doc in ip_col.find(
            {owner_field or track_field: oid, "ip": {"$in": cand_list}},
            {"ip": 1, "domain": 1, "_id": 0},
        ):
            ip_val = ip_doc.get("ip")
            if not ip_val:
                continue
            rem_domains = [x for x in (ip_doc.get("domain") or []) if x]
            if rem_domains:
                continue
            if is_asset and protected_ip_array and ip_in_scope(ip_val, protected_ip_array):
                continue
            # 二次核验：当前作用域内是否仍有其他存活域名解析到该 IP
            still_ref = dom_col.find_one({owner_field or track_field: oid, "ips": ip_val}, {"_id": 1})
            if still_ref:
                continue
            orphan_ips.append(ip_val)

        if orphan_ips:
            # 完整复用「删 IP」链路（同步清理该孤儿 IP 的直连站点及下级 L3、cert）
            o_owners, o_shots = _cascade_delete_ips_in_side(
                orphan_ips,
                is_asset=is_asset,
                owner_ids=[oid],
                global_mode=False,
            )
            affected_owners.update(o_owners)
            screenshots.update(o_shots)

    return affected_owners, screenshots


def _cascade_delete_sites_in_side(site_urls, is_asset, owner_ids=None, global_mode=False):
    """在单侧执行 L2「删站点」级联：删 site -> 向下按严格定界符清 L3，保留 L1 domain/ip。"""
    clean_sites = list(dict.fromkeys(u.strip().rstrip("/") for u in (site_urls or []) if u and isinstance(u, str)))
    if not clean_sites:
        return set(), set()

    prefix = "asset_" if is_asset else ""
    owner_field = None if global_mode else ("scope_id" if is_asset else "task_id")
    track_field = "scope_id" if is_asset else "task_id"
    affected_owners = set()
    screenshots = set()

    variants = []
    for u in clean_sites:
        variants.append(u)
        variants.append(u + "/")

    _, s_owners, s_docs = _delete_with_owner_tracking(
        f"{prefix}site",
        {"site": {"$in": variants}},
        owner_field=owner_field,
        owner_ids=owner_ids,
        track_field=track_field,
        extra_proj=("screenshot",),
    )
    affected_owners.update(s_owners)
    for d in s_docs:
        if d.get("screenshot"):
            screenshots.add(d["screenshot"])

    l3_owners = _cascade_delete_l3_for_sites_and_hosts(
        site_urls=clean_sites,
        hosts=[],
        is_asset=is_asset,
        owner_ids=owner_ids,
        global_mode=global_mode,
        include_port_colon=False,
    )
    affected_owners.update(l3_owners)
    return affected_owners, screenshots


def _cascade_delete_services_in_side(endpoint_tuples, empty_service_names, is_asset, owner_ids=None, global_mode=False):
    """
    精确端点级服务联动：
    按 (service_name, ip, port_id) 端点对从 ip.port_info / asset_ip.port_info 中 $pull 剥离端口项，
    同步删除 service / asset_service 单端点文档及 npoc_service / asset_npoc_service 对应记录；
    不误伤同 service_name 下其他 IP 的服务。
    """
    prefix = "asset_" if is_asset else ""
    owner_field = None if global_mode else ("scope_id" if is_asset else "task_id")
    track_field = "scope_id" if is_asset else "task_id"
    affected_owners = set()

    # 按 IP 分组待剥离的 (service_name, port_id)
    ports_by_ip = {}
    for svc_name, ip_val, port_id in (endpoint_tuples or []):
        if not ip_val or port_id is None:
            continue
        ports_by_ip.setdefault(str(ip_val), []).append((svc_name, port_id))

    ip_col = _db(f"{prefix}ip")
    svc_col = _db(f"{prefix}service")
    npoc_col = _db(f"{prefix}npoc_service")
    for ip_val, pairs in ports_by_ip.items():
        # 构建精确端口匹配条件（兼容 port_id 为 int 或 str）
        port_vals = set()
        for _, pid in pairs:
            port_vals.add(pid)
            try:
                port_vals.add(int(pid))
            except (ValueError, TypeError):
                pass
            port_vals.add(str(pid))

        port_vals_list = list(port_vals)
        base_q = {"ip": ip_val, "port_info.port_id": {"$in": port_vals_list}}
        svc_base_q = {"$or": [{"ip": ip_val, "port_id": {"$in": port_vals_list}}, {"service_info.ip": ip_val}]}
        npoc_base_q = {"host": ip_val, "port": {"$in": port_vals_list}}
        if global_mode:
            for doc in ip_col.find(base_q, {track_field: 1, "_id": 0}):
                if doc.get(track_field):
                    affected_owners.add(str(doc[track_field]))
            for doc in svc_col.find(svc_base_q, {track_field: 1, "_id": 0}):
                if doc.get(track_field):
                    affected_owners.add(str(doc[track_field]))
            for doc in npoc_col.find(npoc_base_q, {track_field: 1, "_id": 0}):
                if doc.get(track_field):
                    affected_owners.add(str(doc[track_field]))
            npoc_col.delete_many(npoc_base_q)
            svc_col.delete_many({"ip": ip_val, "port_id": {"$in": port_vals_list}})
            for svc_name, pid in pairs:
                pid_cands = [pid, str(pid)]
                try:
                    pid_int = int(pid)
                    if pid_int not in pid_cands:
                        pid_cands.append(pid_int)
                except (ValueError, TypeError):
                    pass
                pull_ip_elem = {"port_id": {"$in": pid_cands}}
                ip_col.update_many({"ip": ip_val}, {"$pull": {"port_info": pull_ip_elem}})

                svc_filter = {"ip": {"$exists": False}, "service_info.ip": ip_val}
                if svc_name:
                    svc_filter["service_name"] = svc_name
                svc_col.update_many(svc_filter, {"$pull": {"service_info": {"ip": ip_val, "port_id": {"$in": pid_cands}}}})
        elif owner_ids:
            for chunk in _chunked(owner_ids):
                q = {owner_field: {"$in": chunk}, "ip": ip_val}
                for doc in ip_col.find({**q, "port_info.port_id": {"$in": port_vals_list}}, {track_field: 1, "_id": 0}):
                    if doc.get(track_field):
                        affected_owners.add(str(doc[track_field]))
                sq = {owner_field: {"$in": chunk}, "$or": [{"ip": ip_val, "port_id": {"$in": port_vals_list}}, {"service_info.ip": ip_val}]}
                for doc in svc_col.find(sq, {track_field: 1, "_id": 0}):
                    if doc.get(track_field):
                        affected_owners.add(str(doc[track_field]))
                nq = {owner_field: {"$in": chunk}, "host": ip_val, "port": {"$in": port_vals_list}}
                for doc in npoc_col.find(nq, {track_field: 1, "_id": 0}):
                    if doc.get(track_field):
                        affected_owners.add(str(doc[track_field]))
                npoc_col.delete_many(nq)
                svc_col.delete_many({owner_field: {"$in": chunk}, "ip": ip_val, "port_id": {"$in": port_vals_list}})
                for svc_name, pid in pairs:
                    pid_cands = [pid, str(pid)]
                    try:
                        pid_int = int(pid)
                        if pid_int not in pid_cands:
                            pid_cands.append(pid_int)
                    except (ValueError, TypeError):
                        pass
                    pull_ip_elem = {"port_id": {"$in": pid_cands}}
                    ip_col.update_many(q, {"$pull": {"port_info": pull_ip_elem}})

                    svc_filter = {owner_field: {"$in": chunk}, "ip": {"$exists": False}, "service_info.ip": ip_val}
                    if svc_name:
                        svc_filter["service_name"] = svc_name
                    svc_col.update_many(svc_filter, {"$pull": {"service_info": {"ip": ip_val, "port_id": {"$in": pid_cands}}}})

    # 清理旧版 service_info 已变空的服务文档
    empty_q = {"ip": {"$exists": False}, "$or": [{"service_info": {"$exists": False}}, {"service_info": {"$size": 0}}]}
    if global_mode:
        svc_col.delete_many(empty_q)
    elif owner_ids:
        for chunk in _chunked(owner_ids):
            svc_col.delete_many({"$and": [{owner_field: {"$in": chunk}}, empty_q]})

    if empty_service_names:
        _, s_owners, _ = _delete_with_owner_tracking(
            f"{prefix}service",
            {
                "service_name": {"$in": list(empty_service_names)},
                "ip": {"$exists": False},
                "$or": [{"service_info": {"$exists": False}}, {"service_info": {"$size": 0}}],
            },
            owner_field=owner_field,
            owner_ids=owner_ids,
            track_field=track_field,
        )
        affected_owners.update(s_owners)

    return affected_owners


def _cascade_delete_stat_fingers_in_side(finger_names, is_asset, owner_ids=None, global_mode=False):
    """从 site.finger / asset_site.finger 剥离目标指纹（兼容 dict 与 str 双格式及大小写不敏感匹配，保留宿主站点）并删除 stat_finger。"""
    names = list(dict.fromkeys(str(n).strip() for n in (finger_names or []) if n and isinstance(n, str)))
    if not names:
        return set()

    prefix = "asset_" if is_asset else ""
    owner_field = None if global_mode else ("scope_id" if is_asset else "task_id")
    track_field = "scope_id" if is_asset else "task_id"
    affected_owners = set()

    # 聚合统计按 name.lower() 大小写不敏感归并，删除时同样使用全词大小写不敏感匹配，避免异大小写指纹删后复活
    ci_pattern = "^(?:" + "|".join(re.escape(n) for n in names) + ")$"
    ci_regex = {"$regex": ci_pattern, "$options": "i"}

    # 1. 删除 stat_finger / asset_stat_finger 中大小写不敏感匹配项
    _, sf_owners, _ = _delete_with_owner_tracking(
        f"{prefix}stat_finger",
        {"$or": [{"name": {"$in": names}}, {"name": ci_regex}]},
        owner_field=owner_field,
        owner_ids=owner_ids,
        track_field=track_field,
    )
    affected_owners.update(sf_owners)

    # 2. 从 site.finger / asset_site.finger 双格式 $pull（保留宿主站点）
    site_col = _db(f"{prefix}site")
    match_site_or = [
        {"finger.name": {"$in": names}},
        {"finger.name": ci_regex},
        {"finger": {"$in": names}},
        {"finger": ci_regex},
    ]
    if global_mode:
        q = {"$or": match_site_or}
        for doc in site_col.find(q, {track_field: 1, "_id": 0}):
            if doc.get(track_field):
                affected_owners.add(str(doc[track_field]))
        site_col.update_many(
            {"$or": [{"finger.name": {"$in": names}}, {"finger.name": ci_regex}]},
            {"$pull": {"finger": {"name": ci_regex}}},
        )
        site_col.update_many(
            {"$or": [{"finger": {"$in": names}}, {"finger": ci_regex}]},
            {"$pull": {"finger": ci_regex}},
        )
    elif owner_ids:
        for chunk in _chunked(owner_ids):
            q = {"$and": [{owner_field: {"$in": chunk}}, {"$or": match_site_or}]}
            for doc in site_col.find(q, {track_field: 1, "_id": 0}):
                if doc.get(track_field):
                    affected_owners.add(str(doc[track_field]))
            site_col.update_many(
                {owner_field: {"$in": chunk}, "$or": [{"finger.name": {"$in": names}}, {"finger.name": ci_regex}]},
                {"$pull": {"finger": {"name": ci_regex}}},
            )
            site_col.update_many(
                {owner_field: {"$in": chunk}, "$or": [{"finger": {"$in": names}}, {"finger": ci_regex}]},
                {"$pull": {"finger": ci_regex}},
            )

    return affected_owners


def _is_valid_cidr_key(val):
    if not isinstance(val, str) or "/" not in val:
        return False
    try:
        ipaddress.ip_network(val.strip(), strict=False)
        return True
    except ValueError:
        return False


def cascade_delete_scopes(scope_ids):
    """
    删除整个资产组（全索引同步强一致，严格按显式绑定关系隔离，绝不误伤独立扫描任务）：
      1. 校验全部 scope_id
      2. 快照 updating_icp_task_id / scheduler / bound_task_ids / active_celery_ids
      3. 同步删除 asset_scope 与关联 scheduler，终止 updating_icp_task_id 并解绑 icp_task（保留测绘数据），
         revoke 并删除显式绑定任务 task 文档
      4. 共享线程池并发对 13 张 asset_*（按 scope_id）与 13 张无前缀表（按 bound_task_ids）全索引清理
      5. 回收无引用物理截图 + 递增跨进程缓存版本号
    """
    unique_sids = list(dict.fromkeys(str(s).strip() for s in (scope_ids or []) if s))
    if not unique_sids:
        return {"ok": True, "scope_ids": [], "deleted_tasks": 0}

    scope_docs = []
    for sid in unique_sids:
        if not ObjectId.is_valid(sid):
            return {"ok": False, "error": ErrorMsg.NotFoundScopeID, "data": {"scope_id": sid}}
        doc = _db("asset_scope").find_one({"_id": ObjectId(sid)})
        if not doc:
            return {"ok": False, "error": ErrorMsg.NotFoundScopeID, "data": {"scope_id": sid}}
        scope_docs.append(doc)

    # 1. 快照关联资源
    updating_icp_ids = list(dict.fromkeys(
        str(doc["updating_icp_task_id"])
        for doc in scope_docs
        if doc.get("updating_icp_task_id")
    ))
    scheduler_ids = _get_scope_scheduler_ids(unique_sids)
    bound_task_ids = get_bound_task_ids(unique_sids, extra_scheduler_ids=scheduler_ids)

    terminal_statuses = [TaskStatus.DONE, TaskStatus.ERROR, TaskStatus.STOP]
    active_celery_ids = []
    if bound_task_ids:
        for chunk in _chunked(bound_task_ids):
            for tdoc in _db("task").find(
                {
                    "_id": {"$in": [ObjectId(t) for t in chunk if ObjectId.is_valid(t)]},
                    "status": {"$nin": terminal_statuses},
                },
                {"celery_id": 1},
            ):
                if tdoc.get("celery_id"):
                    active_celery_ids.append(tdoc["celery_id"])

    # 2. 前置防竞态：先摘除顶层 asset_scope 与 scheduler，使存活栅栏立即拦截在途监控写入
    scope_obj_ids = [ObjectId(sid) for sid in unique_sids]
    _db("asset_scope").delete_many({"_id": {"$in": scope_obj_ids}})
    _db("scheduler").delete_many({"scope_id": {"$in": unique_sids}})

    # 3. 企业测绘闭环：复用 _stop_single_icp_task 置停在途更新任务，并解绑 synced_scope_*（保留测绘成果）
    if updating_icp_ids:
        try:
            from app.routes.icp import _stop_single_icp_task
            for utid in updating_icp_ids:
                try:
                    _stop_single_icp_task(utid)
                except Exception as e:
                    logger.warning(f"Failed to stop updating icp_task {utid} while deleting scope: {e}")
        except Exception as e:
            logger.warning(f"Failed to import _stop_single_icp_task: {e}")

    try:
        _db("icp_task").update_many(
            {"synced_scope_id": {"$in": unique_sids}},
            {"$unset": {"synced_scope_id": "", "synced_scope_name": ""}},
        )
    except Exception as e:
        logger.warning(f"Failed to unbind icp_task for scopes {unique_sids}: {e}")

    # 4. 先发非阻塞 SIGTERM revoke 再删绑定任务文档
    _revoke_celery_tasks(active_celery_ids)
    if bound_task_ids:
        for chunk in _chunked(bound_task_ids):
            _db("task").delete_many({"_id": {"$in": [ObjectId(t) for t in chunk if ObjectId.is_valid(t)]}})

    # 5. 共享线程池并发清理 26 张表（全索引 $in 查询）
    executor = get_shared_executor()

    def _del_asset_col(col_name):
        for chunk in _chunked(unique_sids):
            _db(col_name).delete_many({"scope_id": {"$in": chunk}})

    def _del_task_col(col_name):
        for chunk in _chunked(bound_task_ids):
            _db(col_name).delete_many({"task_id": {"$in": chunk}})

    futures = [executor.submit(_del_asset_col, col) for col in ASSET_COLLECTIONS]
    if bound_task_ids:
        futures.extend(executor.submit(_del_task_col, col) for col in UNPREFIXED_COLLECTIONS)

    for fut in as_completed(futures):
        try:
            fut.result()
        except Exception as e:
            logger.error(f"cascade_delete_scopes collection cleanup error: {e}")

    # 6. 回收无引用物理截图 & 跨进程缓存失效
    if bound_task_ids:
        _cleanup_unreferenced_screenshots(task_ids=bound_task_ids)
    bump_asset_cache_versions()

    return {
        "ok": True,
        "scope_ids": unique_sids,
        "deleted_tasks": len(bound_task_ids),
        "deleted_schedulers": len(scheduler_ids),
    }


def cascade_delete_schedulers(scheduler_ids, stop_only=False):
    """
    删除或停止资产持续监控计划（含单条与批量）：
      1. 删除或置停 scheduler
      2. 查找所有 options.scheduler_id 命中的非终态派生 task，先将 DB 状态置为 stop + end_time，再 revoke
      3. 保留历史已完成任务与已入库 asset_*，刷新关联资产组 domain_status 并递增跨进程缓存版本号
    """
    unique_ids = list(dict.fromkeys(str(s).strip() for s in (scheduler_ids or []) if s))
    if not unique_ids:
        return {"scheduler_ids": [], "stopped_tasks": 0}

    sch_obj_ids = [ObjectId(s) for s in unique_ids if ObjectId.is_valid(s)]
    sch_docs = list(_db("scheduler").find({"_id": {"$in": sch_obj_ids}}, {"_id": 1, "scope_id": 1}))
    affected_scope_ids = list(dict.fromkeys(str(d.get("scope_id")) for d in sch_docs if d.get("scope_id")))

    if stop_only:
        _db("scheduler").update_many(
            {"_id": {"$in": sch_obj_ids}},
            {"$set": {
                "status": SchedulerStatus.STOP,
                "next_run_date": "-",
                "next_run_time": sys.maxsize,
            }},
        )
    else:
        _db("scheduler").delete_many({"_id": {"$in": sch_obj_ids}})

    # 查找并终止所有非终态派生监控任务（先置 DB stop + end_time 再发 revoke）
    terminal_statuses = [TaskStatus.DONE, TaskStatus.ERROR, TaskStatus.STOP]
    active_tasks = list(_db("task").find(
        {
            "options.scheduler_id": {"$in": unique_ids},
            "status": {"$nin": terminal_statuses},
        },
        {"_id": 1, "celery_id": 1},
    ))
    stopped_task_ids = [t["_id"] for t in active_tasks]
    celery_ids = [t.get("celery_id") for t in active_tasks if t.get("celery_id")]

    if stopped_task_ids:
        _db("task").update_many(
            {"_id": {"$in": stopped_task_ids}, "status": {"$nin": terminal_statuses}},
            {"$set": {"status": TaskStatus.STOP, "end_time": utils.curr_date()}},
        )
        _revoke_celery_tasks(celery_ids)

    if affected_scope_ids:
        _refresh_scopes_domain_status(affected_scope_ids)

    bump_asset_cache_versions()
    return {
        "scheduler_ids": unique_ids,
        "stopped_tasks": len(stopped_task_ids),
        "affected_scope_ids": affected_scope_ids,
    }


def _target_token_matches_removed(token, removed_domains, removed_ips):
    tok = (token or "").strip().lower()
    if not tok:
        return False
    if tok in removed_domains or tok in removed_ips:
        return True
    if removed_domains and is_valid_domain(tok) and is_in_scopes(tok, removed_domains):
        return True
    if removed_ips and utils.is_vaild_ip_target(tok) and ip_in_scope(tok, removed_ips):
        return True
    return False


def cascade_remove_scope_targets(scope_id, removed_targets):
    """
    资产组剔除根目标后的深度级联清理（必须在 asset_scope 更新落库后调用）：
      - 联动删除/收缩对应 domain/ip 监控计划（保留组级站点/WIH 监控计划）
      - 仅在 scope_id 及其显式绑定任务 bound_task_ids 内操作，绝不误伤独立任务或他组资产
      - 全部 target 落入被删范围的绑定任务直接终止并删除；混合绑定任务与 asset_* 按 L1->L2->L3 剥离后重算派生表与统计
    """
    sid = str(scope_id)
    removed = list(dict.fromkeys(str(t).strip().lower() for t in (removed_targets or []) if t and str(t).strip()))
    if not removed or not ObjectId.is_valid(sid):
        return {"removed_targets": []}

    removed_domains = [t for t in removed if is_valid_domain(t)]
    removed_ips = [t for t in removed if not is_valid_domain(t)]

    scope_doc = _db("asset_scope").find_one({"_id": ObjectId(sid)})
    _, remaining_domain_array, remaining_ip_array = _normalize_scope_arrays(scope_doc)

    # 1. 监控计划联动（先于子资产清理，防止继续派发）
    sch_to_delete = []
    for sch in _db("scheduler").find({"scope_id": sid}):
        st = sch.get("scope_type") or AssetScopeType.DOMAIN
        dom_str = (sch.get("domain") or "").strip()
        if st == AssetScopeType.DOMAIN:
            if dom_str.lower() in removed_domains:
                sch_to_delete.append(str(sch["_id"]))
        elif st == AssetScopeType.IP:
            tokens = dom_str.split()
            kept = [tok for tok in tokens if tok.lower() not in removed_ips]
            if not kept:
                sch_to_delete.append(str(sch["_id"]))
            elif len(kept) != len(tokens):
                _db("scheduler").update_one({"_id": sch["_id"]}, {"$set": {"domain": " ".join(kept)}})
    if sch_to_delete:
        cascade_delete_schedulers(sch_to_delete, stop_only=False)

    # 2. 分类显式绑定任务：整任务删除 vs 局部剥离
    bound_tids = get_bound_task_ids([sid])
    full_delete_tids = []
    partial_tids = []
    active_celery_ids = []
    terminal_statuses = [TaskStatus.DONE, TaskStatus.ERROR, TaskStatus.STOP]

    if bound_tids:
        for chunk in _chunked(bound_tids):
            for tdoc in _db("task").find(
                {"_id": {"$in": [ObjectId(t) for t in chunk if ObjectId.is_valid(t)]}},
                {"_id": 1, "target": 1, "type": 1, "status": 1, "celery_id": 1},
            ):
                tid = str(tdoc["_id"])
                ttype = tdoc.get("type")
                raw_target = str(tdoc.get("target") or "").strip()
                tokens = [x for x in re.split(r"[,\s]+", raw_target) if x]
                if ttype in ("domain", "ip") and tokens and all(
                    _target_token_matches_removed(tok, removed_domains, removed_ips)
                    for tok in tokens
                ):
                    full_delete_tids.append(tid)
                    if tdoc.get("status") not in terminal_statuses and tdoc.get("celery_id"):
                        active_celery_ids.append(tdoc["celery_id"])
                else:
                    partial_tids.append(tid)

    if full_delete_tids:
        _revoke_celery_tasks(active_celery_ids)
        for chunk in _chunked(full_delete_tids):
            _db("task").delete_many({"_id": {"$in": [ObjectId(t) for t in chunk if ObjectId.is_valid(t)]}})
        executor = get_shared_executor()

        def _del_t_col(col_name):
            for chunk in _chunked(full_delete_tids):
                _db(col_name).delete_many({"task_id": {"$in": chunk}})

        futs = [executor.submit(_del_t_col, col) for col in UNPREFIXED_COLLECTIONS]
        for f in as_completed(futs):
            try:
                f.result()
            except Exception as e:
                logger.error(f"cascade_remove_scope_targets full task cleanup error: {e}")

    screenshots = set()
    affected_partial_tids = set()

    # 3. 收集并清理被移除根域名覆盖的全部子域名（L1 -> L2 -> L3）
    if removed_domains:
        matched_asset_domains = []
        for doc in _db("asset_domain").find({"scope_id": sid}, {"domain": 1, "_id": 0}):
            d = doc.get("domain")
            if d and is_in_scopes(d, removed_domains):
                matched_asset_domains.append(d)
        target_domains_asset = list(dict.fromkeys(removed_domains + matched_asset_domains))
        _, shots = _cascade_delete_domains_in_side(target_domains_asset, is_asset=True, owner_ids=[sid], global_mode=False)
        screenshots.update(shots)

        if partial_tids:
            matched_task_domains = []
            for chunk in _chunked(partial_tids):
                for doc in _db("domain").find({"task_id": {"$in": chunk}}, {"domain": 1, "_id": 0}):
                    d = doc.get("domain")
                    if d and is_in_scopes(d, removed_domains):
                        matched_task_domains.append(d)
            target_domains_task = list(dict.fromkeys(removed_domains + matched_task_domains))
            t_owners, t_shots = _cascade_delete_domains_in_side(
                target_domains_task, is_asset=False, owner_ids=partial_tids, global_mode=False
            )
            affected_partial_tids.update(t_owners)
            screenshots.update(t_shots)

    # 4. 收集并清理落入被移除 IP/CIDR 范围的 IP（排除仍被剩余 ip_array 或存活子域名覆盖的 IP）
    if removed_ips:
        surviving_domain_ips_asset = set()
        for doc in _db("asset_domain").find({"scope_id": sid}, {"ips": 1, "_id": 0}):
            for ip_v in (doc.get("ips") or []):
                surviving_domain_ips_asset.add(ip_v)

        matched_asset_ips = []
        for doc in _db("asset_ip").find({"scope_id": sid}, {"ip": 1, "_id": 0}):
            ip_v = doc.get("ip")
            if not ip_v:
                continue
            if ip_in_scope(ip_v, removed_ips):
                if remaining_ip_array and ip_in_scope(ip_v, remaining_ip_array):
                    continue
                if ip_v in surviving_domain_ips_asset:
                    continue
                matched_asset_ips.append(ip_v)
        if matched_asset_ips:
            _, shots = _cascade_delete_ips_in_side(matched_asset_ips, is_asset=True, owner_ids=[sid], global_mode=False)
            screenshots.update(shots)

        if partial_tids:
            matched_task_ips = []
            for chunk in _chunked(partial_tids):
                for doc in _db("ip").find({"task_id": {"$in": chunk}}, {"ip": 1, "_id": 0}):
                    ip_v = doc.get("ip")
                    if not ip_v:
                        continue
                    if ip_in_scope(ip_v, removed_ips):
                        if remaining_ip_array and ip_in_scope(ip_v, remaining_ip_array):
                            continue
                        matched_task_ips.append(ip_v)
            if matched_task_ips:
                t_owners, t_shots = _cascade_delete_ips_in_side(
                    matched_task_ips, is_asset=False, owner_ids=partial_tids, global_mode=False
                )
                affected_partial_tids.update(t_owners)
                screenshots.update(t_shots)

    # 5. 重算派生表、任务统计、回收截图、刷新 domain_status 与跨进程缓存失效
    rebuild_scope_derived_collections([sid])
    if affected_partial_tids:
        rebuild_task_derived_collections(list(affected_partial_tids))
        recalculate_tasks_statistics(list(affected_partial_tids))
    if full_delete_tids or screenshots:
        _cleanup_unreferenced_screenshots(task_ids=full_delete_tids, screenshot_paths=list(screenshots))
    _refresh_scopes_domain_status([sid])
    bump_asset_cache_versions()

    return {
        "removed_targets": removed,
        "deleted_tasks": len(full_delete_tids),
        "updated_tasks": len(affected_partial_tids),
    }


def _sync_scope_rename_references(scope_id, old_name, new_name):
    """资产组改名时同步默认命名规则的 scheduler.name、绑定 icp_task.synced_scope_name 与绑定 task 组名冗余字段。"""
    sid = str(scope_id)
    if not old_name or not new_name or old_name == new_name:
        return

    # 1. 更新默认命名规则的 scheduler.name
    old_prefix = f"监控-{old_name}-"
    old_site = f"站点监控-{old_name}"
    old_wih = f"WIH 监控-{old_name}"
    old_wih_nospace = f"WIH监控-{old_name}"

    for sch in _db("scheduler").find({"scope_id": sid}, {"_id": 1, "name": 1}):
        sname = sch.get("name") or ""
        updated_name = None
        if sname.startswith(old_prefix):
            updated_name = f"监控-{new_name}-" + sname[len(old_prefix):]
        elif sname == old_site:
            updated_name = f"站点监控-{new_name}"
        elif sname == old_wih:
            updated_name = f"WIH 监控-{new_name}"
        elif sname == old_wih_nospace:
            updated_name = f"WIH监控-{new_name}"
        if updated_name:
            _db("scheduler").update_one({"_id": sch["_id"]}, {"$set": {"name": updated_name}})

    # 2. 更新关联 icp_task.synced_scope_name
    try:
        _db("icp_task").update_many(
            {"synced_scope_id": sid},
            {"$set": {"synced_scope_name": new_name}},
        )
    except Exception as e:
        logger.warning(f"Failed to sync icp_task.synced_scope_name for scope {sid}: {e}")

    # 3. 更新关联 task 的组名展示字段
    try:
        _db("task").update_many(
            {"options.related_scope_id": sid},
            {"$set": {"related_scope_name": new_name}},
        )
        _db("task").update_many(
            {"sync_scope_id": sid},
            {"$set": {"sync_scope_name": new_name}},
        )
        _db("task").update_many(
            {"synced_scope_id": sid},
            {"$set": {"synced_scope_name": new_name}},
        )
    except Exception as e:
        logger.warning(f"Failed to sync task scope name fields for scope {sid}: {e}")


def _extract_natural_key_matcher(category, doc):
    """提取用于单条记录跨表匹配的对齐查询条件（处理无前缀表与 asset_* 字段差异）。"""
    if category in ("site", "domain", "ip"):
        val = doc.get(category)
        return {category: val} if val else None
    if category in ("url", "fileleak"):
        val = doc.get("url")
        return {"url": val} if val else None
    if category == "wih":
        site = doc.get("site")
        fnv = doc.get("fnv_hash")
        if site and fnv is not None:
            return {"site": site, "fnv_hash": fnv}
        return None
    if category == "cert":
        ip_v = doc.get("ip")
        port_v = doc.get("port")
        sha256 = (doc.get("cert") or {}).get("fingerprint", {}).get("sha256") if isinstance(doc.get("cert"), dict) else None
        if ip_v and port_v is not None:
            if sha256:
                return {"$or": [{"ip": ip_v, "port": port_v}, {"ip": ip_v, "cert.fingerprint.sha256": sha256}]}
            return {"ip": ip_v, "port": port_v}
        if ip_v and sha256:
            return {"ip": ip_v, "cert.fingerprint.sha256": sha256}
        return None
    if category == "npoc_service":
        host = doc.get("host")
        port = doc.get("port")
        target = doc.get("target")
        or_parts = []
        if host and port is not None:
            or_parts.append({"host": host, "port": port})
        if target:
            or_parts.append({"target": target})
        if not or_parts:
            return None
        return or_parts[0] if len(or_parts) == 1 else {"$or": or_parts}
    if category == "vuln":
        target = doc.get("target")
        vname = doc.get("vul_name") or doc.get("plugin_name")
        vurl = doc.get("vuln_url")
        if not target and not vurl:
            return None
        cond = {}
        if target:
            cond["target"] = target
        if vurl:
            cond["vuln_url"] = vurl
        if vname:
            cond["$or"] = [{"vul_name": vname}, {"plugin_name": vname}]
        return cond
    if category == "nuclei_result":
        tid = doc.get("template_id")
        target = doc.get("target") or doc.get("host")
        vurl = doc.get("vuln_url")
        if not tid:
            return None
        cond = {"template_id": tid}
        if target:
            cond["$or"] = [{"target": target}, {"host": target}]
        if vurl:
            cond["vuln_url"] = vurl
        return cond
    return None


def cascade_delete_dimension_records(category, ids_or_keys, source_type, scope_id=None, task_id=None, db_getter=None):
    """
    12 维资产（底层 13 对集合）统一级联删除引擎。
    遵循三端作用域契约：
      - source_type == 'asset'  : 仅清 scope_id 及显式绑定该组的 bound_task_ids
      - source_type == 'task'   : 清当前任务；若任务显式绑定了资产组 A，同步清 A 及 bound_task_ids(A)；独立任务绝不碰 asset_*
      - source_type == 'global' : 全库双表穿透删除（用于全局「资产搜索」入口）
    """
    with _use_db_getter(db_getter):
        return _cascade_delete_dimension_records_impl(
            category=category,
            ids_or_keys=ids_or_keys,
            source_type=source_type,
            scope_id=scope_id,
            task_id=task_id,
        )


def _cascade_delete_dimension_records_impl(category, ids_or_keys, source_type, scope_id=None, task_id=None):
    if category not in UNPREFIXED_COLLECTIONS:
        raise ValueError(f"Unsupported asset category: {category}")

    keys = [x for x in (ids_or_keys or []) if isinstance(x, str) and x.strip()]
    if not keys:
        return {"deleted_count": 0, "affected_scope_ids": [], "affected_task_ids": []}
    if len(keys) > MAX_BATCH_DELETE_SIZE:
        raise ValueError(f"单次删除最多支持 {MAX_BATCH_DELETE_SIZE} 条记录")

    if source_type not in ("asset", "task", "global"):
        raise ValueError(f"Unsupported source_type: {source_type}")

    is_primary_asset = source_type == "asset"
    primary_col = f"asset_{category}" if is_primary_asset else category
    global_mode = source_type == "global"

    # 1. 解析入参：ObjectId 文档 + 聚合维度字符串键（stat_finger name / cip cidr_ip）
    obj_ids = [ObjectId(k) for k in keys if ObjectId.is_valid(k)]
    str_keys = [k.strip() for k in keys if not ObjectId.is_valid(k)]

    matched_docs = []
    if obj_ids:
        for chunk in _chunked(obj_ids):
            matched_docs.extend(list(_db(primary_col).find({"_id": {"$in": chunk}})))

    if category == "cip" and str_keys:
        cidr_q = {"cidr_ip": {"$in": str_keys}}
        if source_type == "asset" and scope_id:
            cidr_q["scope_id"] = str(scope_id)
        elif source_type == "task" and task_id:
            cidr_q["task_id"] = str(task_id)
        matched_docs.extend(list(_db(primary_col).find(cidr_q)))
    elif category == "stat_finger" and str_keys:
        sf_q = {"name": {"$in": str_keys}}
        if source_type == "asset" and scope_id:
            sf_q["scope_id"] = str(scope_id)
        elif source_type == "task" and task_id:
            sf_q["task_id"] = str(task_id)
        matched_docs.extend(list(_db(primary_col).find(sf_q)))

    # 若没有任何匹配文档且非聚合键直传，直接幂等返回 0
    if not matched_docs and not (category in ("cip", "stat_finger") and str_keys):
        return {"deleted_count": 0, "affected_scope_ids": [], "affected_task_ids": []}

    # 2. 确定精确作用域上下文（asset_* 侧 scope_ids 与无前缀侧 task_ids）
    scope_ids = set()
    task_ids = set()
    if source_type == "asset":
        if scope_id:
            scope_ids.add(str(scope_id))
        for doc in matched_docs:
            if doc.get("scope_id"):
                scope_ids.add(str(doc["scope_id"]))
        if scope_ids:
            task_ids.update(get_bound_task_ids(list(scope_ids)))
    elif source_type == "task":
        if task_id:
            task_ids.add(str(task_id))
        for doc in matched_docs:
            if doc.get("task_id"):
                task_ids.add(str(doc["task_id"]))
        bound_sids = get_task_bound_scope_ids(list(task_ids))
        if bound_sids:
            scope_ids.update(bound_sids)
            task_ids.update(get_bound_task_ids(bound_sids))

    scope_id_list = list(scope_ids)
    task_id_list = list(task_ids)

    affected_scopes = set(scope_id_list)
    affected_tasks = set(task_id_list)
    screenshots = set()
    deleted_primary_count = len(matched_docs) if matched_docs else len(str_keys)

    # 3. 按维度执行对应级联动作
    if category == "domain":
        target_domains = list(dict.fromkeys(
            str(d.get("domain")).strip().lower() for d in matched_docs if d.get("domain")
        ))
        if global_mode or scope_id_list:
            s_aff, s_shots = _cascade_delete_domains_in_side(
                target_domains, is_asset=True, owner_ids=scope_id_list, global_mode=global_mode
            )
            affected_scopes.update(s_aff)
            screenshots.update(s_shots)
        if global_mode or task_id_list:
            t_aff, t_shots = _cascade_delete_domains_in_side(
                target_domains, is_asset=False, owner_ids=task_id_list, global_mode=global_mode
            )
            affected_tasks.update(t_aff)
            screenshots.update(t_shots)
        if affected_scopes:
            rebuild_scope_derived_collections(list(affected_scopes))
            _refresh_scopes_domain_status(list(affected_scopes))
        if affected_tasks:
            rebuild_task_derived_collections(list(affected_tasks))
            recalculate_tasks_statistics(list(affected_tasks))

    elif category in ("ip", "cip"):
        target_ips = set()
        target_cidrs = set()
        if category == "ip":
            for d in matched_docs:
                if d.get("ip"):
                    target_ips.add(str(d["ip"]).strip())
        else:
            for k in str_keys:
                if _is_valid_cidr_key(k):
                    target_cidrs.add(k)
            for d in matched_docs:
                if d.get("cidr_ip"):
                    target_cidrs.add(str(d["cidr_ip"]).strip())
                for ip_v in (d.get("ip_list") or []):
                    if isinstance(ip_v, str) and ip_v.strip():
                        target_ips.add(ip_v.strip())

            # 同时展开作用域内落入目标 /24 CIDR 的全部存活 IP（防止 cip 历史陈旧漏删 IP）
            cidr_nets = []
            for c in target_cidrs:
                try:
                    cidr_nets.append(ipaddress.ip_network(c, strict=False))
                except ValueError:
                    pass
            if cidr_nets:
                if global_mode or scope_id_list:
                    q_ip = {} if global_mode else {"scope_id": {"$in": scope_id_list}}
                    for doc in _db("asset_ip").find(q_ip, {"ip": 1, "_id": 0}):
                        ip_v = doc.get("ip")
                        if not ip_v or not isinstance(ip_v, str) or ":" in ip_v:
                            continue
                        try:
                            ip_obj = ipaddress.ip_address(ip_v.strip())
                        except ValueError:
                            continue
                        if any(ip_obj in net for net in cidr_nets):
                            target_ips.add(ip_v.strip())
                if global_mode or task_id_list:
                    q_ip = {} if global_mode else {"task_id": {"$in": task_id_list}}
                    for doc in _db("ip").find(q_ip, {"ip": 1, "_id": 0}):
                        ip_v = doc.get("ip")
                        if not ip_v or not isinstance(ip_v, str) or ":" in ip_v:
                            continue
                        try:
                            ip_obj = ipaddress.ip_address(ip_v.strip())
                        except ValueError:
                            continue
                        if any(ip_obj in net for net in cidr_nets):
                            target_ips.add(ip_v.strip())

            # 直接删除显式选中的 cip / asset_cip 文档（覆盖无关联 ip 文档的孤立 C 段）
            if obj_ids:
                _db(primary_col).delete_many({"_id": {"$in": obj_ids}})
            if target_cidrs:
                if global_mode or scope_id_list:
                    _, c_sc, _ = _delete_with_owner_tracking(
                        "asset_cip",
                        {"cidr_ip": {"$in": list(target_cidrs)}},
                        owner_field=None if global_mode else "scope_id",
                        owner_ids=scope_id_list,
                        track_field="scope_id",
                    )
                    affected_scopes.update(c_sc)
                if global_mode or task_id_list:
                    _, c_tk, _ = _delete_with_owner_tracking(
                        "cip",
                        {"cidr_ip": {"$in": list(target_cidrs)}},
                        owner_field=None if global_mode else "task_id",
                        owner_ids=task_id_list,
                        track_field="task_id",
                    )
                    affected_tasks.update(c_tk)

        if target_ips:
            if global_mode or scope_id_list:
                s_aff, s_shots = _cascade_delete_ips_in_side(
                    list(target_ips), is_asset=True, owner_ids=scope_id_list, global_mode=global_mode
                )
                affected_scopes.update(s_aff)
                screenshots.update(s_shots)
            if global_mode or task_id_list:
                t_aff, t_shots = _cascade_delete_ips_in_side(
                    list(target_ips), is_asset=False, owner_ids=task_id_list, global_mode=global_mode
                )
                affected_tasks.update(t_aff)
                screenshots.update(t_shots)

        if affected_scopes:
            rebuild_scope_derived_collections(list(affected_scopes))
            _refresh_scopes_domain_status(list(affected_scopes))
        if affected_tasks:
            rebuild_task_derived_collections(list(affected_tasks))
            recalculate_tasks_statistics(list(affected_tasks))

    elif category == "site":
        target_sites = list(dict.fromkeys(
            str(d.get("site")).strip() for d in matched_docs if d.get("site")
        ))
        if global_mode or scope_id_list:
            s_aff, s_shots = _cascade_delete_sites_in_side(
                target_sites, is_asset=True, owner_ids=scope_id_list, global_mode=global_mode
            )
            affected_scopes.update(s_aff)
            screenshots.update(s_shots)
        if global_mode or task_id_list:
            t_aff, t_shots = _cascade_delete_sites_in_side(
                target_sites, is_asset=False, owner_ids=task_id_list, global_mode=global_mode
            )
            affected_tasks.update(t_aff)
            screenshots.update(t_shots)
        if affected_scopes:
            rebuild_scope_derived_collections(list(affected_scopes), targets=("stat_finger",))
        if affected_tasks:
            rebuild_task_derived_collections(list(affected_tasks), targets=("stat_finger",))
            recalculate_tasks_statistics(list(affected_tasks))

    elif category == "service":
        # 精确端点级 (service_name, ip, port_id) 联动，杜绝按 service_name 全库误杀其他 IP 的服务
        endpoint_tuples = []
        empty_service_names = set()
        for d in matched_docs:
            sname = d.get("service_name")
            if d.get("ip") and d.get("port_id") is not None:
                endpoint_tuples.append((sname, d["ip"], d["port_id"]))
                continue
            sinfos = d.get("service_info") or []
            if isinstance(sinfos, list) and sinfos:
                for info in sinfos:
                    if isinstance(info, dict) and info.get("ip") and info.get("port_id") is not None:
                        endpoint_tuples.append((sname, info["ip"], info["port_id"]))
            elif sname:
                empty_service_names.add(sname)

        # 删除显式选中的服务文档
        if obj_ids:
            _db(primary_col).delete_many({"_id": {"$in": obj_ids}})

        if global_mode or scope_id_list:
            s_aff = _cascade_delete_services_in_side(
                endpoint_tuples, empty_service_names, is_asset=True, owner_ids=scope_id_list, global_mode=global_mode
            )
            affected_scopes.update(s_aff)
        if global_mode or task_id_list:
            t_aff = _cascade_delete_services_in_side(
                endpoint_tuples, empty_service_names, is_asset=False, owner_ids=task_id_list, global_mode=global_mode
            )
            affected_tasks.update(t_aff)

        if affected_scopes:
            sids_with_ip = [
                s for s in affected_scopes
                if _db("asset_ip").find_one({"scope_id": s}, {"_id": 1}) or _db("asset_npoc_service").find_one({"scope_id": s}, {"_id": 1})
            ]
            if sids_with_ip:
                rebuild_scope_derived_collections(sids_with_ip, targets=("service",))
        if affected_tasks:
            tids_with_ip = [
                t for t in affected_tasks
                if _db("ip").find_one({"task_id": t}, {"_id": 1}) or _db("npoc_service").find_one({"task_id": t}, {"_id": 1})
            ]
            if tids_with_ip:
                rebuild_task_derived_collections(tids_with_ip, targets=("service",))
            recalculate_tasks_statistics(list(affected_tasks))

    elif category == "stat_finger":
        finger_names = set(str_keys)
        for d in matched_docs:
            if d.get("name"):
                finger_names.add(str(d["name"]).strip())
        if obj_ids:
            _db(primary_col).delete_many({"_id": {"$in": obj_ids}})
        if global_mode or scope_id_list:
            s_aff = _cascade_delete_stat_fingers_in_side(
                list(finger_names), is_asset=True, owner_ids=scope_id_list, global_mode=global_mode
            )
            affected_scopes.update(s_aff)
        if global_mode or task_id_list:
            t_aff = _cascade_delete_stat_fingers_in_side(
                list(finger_names), is_asset=False, owner_ids=task_id_list, global_mode=global_mode
            )
            affected_tasks.update(t_aff)
        if affected_scopes:
            sids_with_site = [s for s in affected_scopes if _db("asset_site").find_one({"scope_id": s}, {"_id": 1})]
            if sids_with_site:
                rebuild_scope_derived_collections(sids_with_site, targets=("stat_finger",))
        if affected_tasks:
            tids_with_site = [t for t in affected_tasks if _db("site").find_one({"task_id": t}, {"_id": 1})]
            if tids_with_site:
                rebuild_task_derived_collections(tids_with_site, targets=("stat_finger",))
            recalculate_tasks_statistics(list(affected_tasks))

    else:
        # L2 独立项（cert / npoc_service）与 L3 叶节点（url / fileleak / wih / vuln / nuclei_result）
        matchers = []
        for d in matched_docs:
            m = _extract_natural_key_matcher(category, d)
            if m:
                matchers.append(m)

        # 确保显式传入的 _id 必删（兼容缺自然键的历史残缺数据）
        if obj_ids:
            _db(primary_col).delete_many({"_id": {"$in": obj_ids}})

        if matchers:
            match_q = matchers[0] if len(matchers) == 1 else {"$or": matchers}
            if global_mode or scope_id_list:
                _, s_aff, _ = _delete_with_owner_tracking(
                    f"asset_{category}",
                    match_q,
                    owner_field=None if global_mode else "scope_id",
                    owner_ids=scope_id_list,
                    track_field="scope_id",
                )
                affected_scopes.update(s_aff)
            if global_mode or task_id_list:
                _, t_aff, _ = _delete_with_owner_tracking(
                    category,
                    match_q,
                    owner_field=None if global_mode else "task_id",
                    owner_ids=task_id_list,
                    track_field="task_id",
                )
                affected_tasks.update(t_aff)

        if category == "npoc_service":
            if affected_scopes:
                rebuild_scope_derived_collections(
                    list(affected_scopes), targets=("service",), preserve_existing_npoc=False
                )
            if affected_tasks:
                rebuild_task_derived_collections(
                    list(affected_tasks), targets=("service",), preserve_existing_npoc=False
                )

        if affected_tasks:
            recalculate_tasks_statistics(list(affected_tasks))

    if screenshots:
        _cleanup_unreferenced_screenshots(screenshot_paths=list(screenshots))

    bump_asset_cache_versions()

    return {
        "deleted_count": deleted_primary_count,
        "affected_scope_ids": list(affected_scopes),
        "affected_task_ids": list(affected_tasks),
    }


def cascade_delete_tasks(task_ids, del_task_data=False, del_synced_asset=False):
    """
    任务管理删除任务（默认隔离保护资产组 asset_* 台账）：
      - Fail-Fast 校验所有 task_id 存在且处于终态（done / stop / error）
      - 删除 task 记录；del_task_data=True 时并发清空 13 张无前缀表中 task_id 对应的全部记录
      - 默认 del_synced_asset=False 完整保留 asset_* 台账；
        仅在用户显式传 del_synced_asset=True 时，检查同资产组其他存活绑定任务支撑，清理独占 asset_* 并重算派生表
      - 回收无引用物理截图，刷新关联资产组 domain_status，递增跨进程缓存版本号
    """
    done_status = [TaskStatus.DONE, TaskStatus.STOP, TaskStatus.ERROR]
    unique_tids = list(dict.fromkeys(str(t).strip() for t in (task_ids or []) if t))
    if not unique_tids:
        return {"ok": True, "task_ids": []}

    # 1. Fail-Fast 校验
    for tid in unique_tids:
        if not ObjectId.is_valid(tid):
            return {"ok": False, "error": ErrorMsg.NotFoundTask, "data": {"task_id": tid}}
        tdoc = _db("task").find_one({"_id": ObjectId(tid)}, {"_id": 1, "status": 1})
        if not tdoc:
            return {"ok": False, "error": ErrorMsg.NotFoundTask, "data": {"task_id": tid}}
        if tdoc.get("status") not in done_status:
            return {"ok": False, "error": ErrorMsg.TaskIsRunning, "data": {"task_id": tid}}

    affected_scope_ids = get_task_bound_scope_ids(unique_tids)

    # 2. 删除 task 文档
    for chunk in _chunked(unique_tids):
        _db("task").delete_many({"_id": {"$in": [ObjectId(t) for t in chunk]}})

    # 3. 并发清理 13 张无前缀表
    if del_task_data:
        executor = get_shared_executor()

        def _del_col(col_name):
            for chunk in _chunked(unique_tids):
                _db(col_name).delete_many({"task_id": {"$in": chunk}})

        futs = [executor.submit(_del_col, col) for col in UNPREFIXED_COLLECTIONS]
        for fut in as_completed(futs):
            try:
                fut.result()
            except Exception as e:
                logger.error(f"cascade_delete_tasks failed cleaning unprefixed collection: {e}")

        # 4. 仅在用户显式勾选 del_synced_asset=True 时清理资产组独占资产
        if del_synced_asset and affected_scope_ids:
            non_derived = (
                "site", "domain", "ip", "cert", "npoc_service",
                "fileleak", "url", "vuln", "nuclei_result", "wih",
            )
            for sid in affected_scope_ids:
                surviving_bound_tids = get_bound_task_ids([sid])
                for cat in non_derived:
                    asset_col = _db(f"asset_{cat}")
                    task_col = _db(cat)
                    cand_docs = list(asset_col.find({"scope_id": sid, "task_id": {"$in": unique_tids}}))
                    if not cand_docs:
                        continue
                    ids_to_remove = []
                    for doc in cand_docs:
                        matcher = _extract_natural_key_matcher(cat, doc)
                        supported = False
                        if matcher and surviving_bound_tids:
                            check_q = _apply_scope_filter(matcher, "task_id", surviving_bound_tids)
                            if check_q and task_col.find_one(check_q, {"_id": 1}):
                                supported = True
                        if not supported:
                            ids_to_remove.append(doc["_id"])
                    if ids_to_remove:
                        for chunk in _chunked(ids_to_remove):
                            asset_col.delete_many({"_id": {"$in": chunk}})
                rebuild_scope_derived_collections([sid])

        _cleanup_unreferenced_screenshots(task_ids=unique_tids)

    if affected_scope_ids:
        _refresh_scopes_domain_status(affected_scope_ids)

    bump_asset_cache_versions()
    return {
        "ok": True,
        "task_ids": unique_tids,
        "affected_scope_ids": affected_scope_ids,
    }


def handle_dimension_delete(category, is_asset_route, args, build_ret_fn=None, success_msg=None, db_getter=None):
    """
    供 26 个资产维度路由 /delete/ 复用的统一入参校验、作用域收敛与级联调度入口。
    """
    ret_fn = build_ret_fn or utils.build_ret
    ok_msg = success_msg if success_msg is not None else ErrorMsg.Success

    args = args if isinstance(args, dict) else {}
    raw_ids = args.get("_id")
    raw_names = args.get("name")
    raw_cidrs = args.get("cidr_ip")
    scope_id = (args.get("scope_id") or "").strip() or None
    task_id = (args.get("task_id") or "").strip() or None
    req_source_type = (args.get("source_type") or "").strip().lower() or None

    if category == "cip":
        keys = []
        if isinstance(raw_ids, list):
            keys.extend(raw_ids)
        if isinstance(raw_cidrs, list):
            keys.extend(raw_cidrs)
        if not keys or any(
            not isinstance(v, str) or (not ObjectId.is_valid(v.strip()) and not _is_valid_cidr_key(v.strip()))
            for v in keys
        ):
            return ret_fn({"code": 400, "message": "请提供有效的记录 ID 列表"}, {"count": len(keys)})
        keys = [v.strip() for v in keys]
        if is_asset_route and any(not ObjectId.is_valid(v) for v in keys) and not scope_id:
            return ret_fn({"code": 400, "message": "按 C 段删除资产组记录必须提供 scope_id"}, {"count": len(keys)})
    elif category == "stat_finger":
        keys = []
        if isinstance(raw_ids, list):
            keys.extend(raw_ids)
        if isinstance(raw_names, list):
            keys.extend(raw_names)
        if not keys or any(not isinstance(v, str) or not v.strip() for v in keys):
            return ret_fn({"code": 400, "message": "请提供有效的指纹名称或记录 ID 列表"}, {"count": len(keys)})
        keys = [v.strip() for v in keys]
        if is_asset_route and any(not ObjectId.is_valid(v) for v in keys) and not scope_id:
            return ret_fn({"code": 400, "message": "按指纹名称删除资产组统计必须提供 scope_id"}, {"count": len(keys)})
    else:
        keys = raw_ids if isinstance(raw_ids, list) else []
        if not keys or any(not isinstance(v, str) or not ObjectId.is_valid(v.strip()) for v in keys):
            return ret_fn({"code": 400, "message": "请提供有效的记录 ID 列表"}, {"count": len(keys)})
        keys = [v.strip() for v in keys]

    if len(keys) > MAX_BATCH_DELETE_SIZE:
        return ret_fn(
            {"code": 400, "message": f"单次删除最多支持 {MAX_BATCH_DELETE_SIZE} 条记录"},
            {"count": len(keys)},
        )

    if is_asset_route:
        resolved_source = "asset"
    elif req_source_type == "global":
        resolved_source = "global"
    elif req_source_type == "task":
        resolved_source = "task"
    elif category == "cip" and not task_id and any(_is_valid_cidr_key(v) for v in keys):
        resolved_source = "global"
    elif category == "stat_finger" and not task_id and any(not ObjectId.is_valid(v) for v in keys):
        resolved_source = "global"
    else:
        resolved_source = "task"

    res = cascade_delete_dimension_records(
        category=category,
        ids_or_keys=keys,
        source_type=resolved_source,
        scope_id=scope_id,
        task_id=task_id,
        db_getter=db_getter,
    )
    return ret_fn(ok_msg, {"_id": keys, "deleted_count": res["deleted_count"]})
