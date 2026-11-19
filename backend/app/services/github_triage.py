import csv
import io
import json
import re
from typing import Any, Dict, List, Optional

from app import utils

TRIAGE_PENDING = "pending"
TRIAGE_CONFIRMED = "confirmed"
TRIAGE_FALSE_POSITIVE = "false_positive"
VALID_TRIAGE_STATUSES = {TRIAGE_PENDING, TRIAGE_CONFIRMED, TRIAGE_FALSE_POSITIVE}


def csv_literal(value: Any) -> Any:
    """Neutralize leading formula prefixes when serializing cells to CSV."""
    if isinstance(value, str) and value.lstrip(" \t\r\n").startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def normalize_repo_full_name(raw_repo: str) -> str:
    """Normalize a GitHub repo reference or URL into canonical `owner/repo` form."""
    text = (raw_repo or "").strip()
    if not text:
        return ""
    for prefix in (
        "https://github.com/",
        "http://github.com/",
        "https://api.github.com/repos/",
        "http://api.github.com/repos/",
    ):
        if text.lower().startswith(prefix):
            text = text[len(prefix):]
            break
    text = text.strip("/")
    if text.endswith(".git"):
        text = text[:-4]
    parts = [p for p in text.split("/") if p]
    if len(parts) >= 2:
        return f"{parts[0]}/{parts[1]}"
    return text


def get_triage_status_map(hash_list: List[str]) -> Dict[str, Dict[str, str]]:
    """Batch-fetch persisted triage metadata keyed by finding `hash_md5`."""
    clean_hashes = [h for h in dict.fromkeys(hash_list or []) if h]
    if not clean_hashes:
        return {}
    result: Dict[str, Dict[str, str]] = {}
    cursor = utils.conn_db("github_triage").find(
        {"hash_md5": {"$in": clean_hashes}},
        {"_id": 0, "hash_md5": 1, "triage_status": 1, "note": 1, "updated_at": 1},
    )
    for doc in cursor:
        h = doc.get("hash_md5")
        if h:
            result[h] = {
                "triage_status": doc.get("triage_status") or TRIAGE_PENDING,
                "note": doc.get("note") or "",
                "updated_at": doc.get("updated_at") or "",
            }
    return result


def set_triage_status(
    hash_md5_list: List[str],
    triage_status: str,
    note: Optional[str] = None,
) -> Dict[str, Any]:
    """Persist triage status by `hash_md5` and propagate across result collections."""
    if triage_status not in VALID_TRIAGE_STATUSES:
        raise ValueError(f"Invalid triage_status: {triage_status}")

    clean_hashes = [str(h).strip() for h in (hash_md5_list or []) if str(h).strip()]
    clean_hashes = list(dict.fromkeys(clean_hashes))
    if not clean_hashes:
        return {"updated_hashes": 0, "triage_status": triage_status}

    now_str = utils.curr_date()
    triage_col = utils.conn_db("github_triage")
    note_val = note.strip() if isinstance(note, str) else None

    for h in clean_hashes:
        update_doc: Dict[str, Any] = {
            "hash_md5": h,
            "triage_status": triage_status,
            "updated_at": now_str,
        }
        if note_val is not None:
            update_doc["note"] = note_val
        try:
            triage_col.update_one(
                {"hash_md5": h},
                {"$set": update_doc},
                upsert=True,
            )
        except Exception as exc:
            if getattr(exc, "code", None) == 11000 or exc.__class__.__name__ == "DuplicateKeyError":
                triage_col.update_one({"hash_md5": h}, {"$set": update_doc})
            else:
                raise

    sync_fields: Dict[str, Any] = {
        "triage_status": triage_status,
        "triage_updated_at": now_str,
    }
    if note_val is not None:
        sync_fields["triage_note"] = note_val

    query = {"hash_md5": {"$in": clean_hashes}}
    utils.conn_db("github_result").update_many(query, {"$set": sync_fields})
    utils.conn_db("github_monitor_result").update_many(query, {"$set": sync_fields})

    return {
        "updated_hashes": len(clean_hashes),
        "triage_status": triage_status,
        "updated_at": now_str,
    }


def list_ignored_repos() -> List[Dict[str, str]]:
    """Return all ignored repositories ordered newest first."""
    cursor = utils.conn_db("github_ignored_repo").find({}, {"_id": 0}).sort("created_at", -1)
    items = []
    for doc in cursor:
        items.append({
            "repo_full_name": doc.get("repo_full_name", ""),
            "reason": doc.get("reason", ""),
            "created_at": doc.get("created_at", ""),
        })
    return items


def get_ignored_repo_names() -> List[str]:
    """Return canonical names of all ignored repositories."""
    return [
        doc["repo_full_name"]
        for doc in utils.conn_db("github_ignored_repo").find({}, {"_id": 0, "repo_full_name": 1})
        if doc.get("repo_full_name")
    ]


def manage_ignored_repos(action: str, repo_full_names: List[str], reason: str = "") -> Dict[str, Any]:
    """Add or remove repositories from the noisy-repo ignore list."""
    normalized = [
        normalize_repo_full_name(r)
        for r in (repo_full_names or [])
    ]
    clean_repos = [r for r in dict.fromkeys(normalized) if r]
    if not clean_repos:
        return {"action": action, "count": 0, "repos": []}

    col = utils.conn_db("github_ignored_repo")
    now_str = utils.curr_date()
    if action == "add":
        for repo in clean_repos:
            repo_doc = {
                "repo_full_name": repo,
                "reason": (reason or "").strip(),
                "created_at": now_str,
            }
            try:
                col.update_one(
                    {"repo_full_name": repo},
                    {"$set": repo_doc},
                    upsert=True,
                )
            except Exception as exc:
                if getattr(exc, "code", None) == 11000 or exc.__class__.__name__ == "DuplicateKeyError":
                    col.update_one({"repo_full_name": repo}, {"$set": repo_doc})
                else:
                    raise
    elif action == "remove":
        col.delete_many({"repo_full_name": {"$in": clean_repos}})
    else:
        raise ValueError(f"Unsupported action: {action}")

    return {"action": action, "count": len(clean_repos), "repos": clean_repos}


def _load_source_metadata():
    """Load task and scheduler id->metadata maps for finding attribution."""
    task_map: Dict[str, Dict[str, str]] = {}
    scheduler_task_ids: List[str] = []
    for doc in utils.conn_db("github_task").find({}, {"name": 1, "github_scheduler_id": 1}):
        tid = str(doc.get("_id", ""))
        if not tid:
            continue
        sid = str(doc.get("github_scheduler_id") or "")
        task_map[tid] = {"name": doc.get("name", ""), "github_scheduler_id": sid}
        if sid:
            scheduler_task_ids.append(tid)

    scheduler_map: Dict[str, Dict[str, str]] = {}
    for doc in utils.conn_db("github_scheduler").find({}, {"name": 1, "keyword": 1}):
        sid = str(doc.get("_id", ""))
        if sid:
            scheduler_map[sid] = {"name": doc.get("name", ""), "keyword": doc.get("keyword", "")}

    return task_map, scheduler_map, scheduler_task_ids


def _build_match_query(filters: Dict[str, Any], ignored_repos: List[str], scheduler_task_ids: List[str]) -> Dict[str, Any]:
    """Translate user filters into a MongoDB $match dictionary."""
    and_clauses: List[Dict[str, Any]] = []

    if filters.get("github_task_id"):
        and_clauses.append({"github_task_id": str(filters["github_task_id"]).strip()})
    if filters.get("github_scheduler_id"):
        and_clauses.append({"github_scheduler_id": str(filters["github_scheduler_id"]).strip()})

    source_type = filters.get("source_type") or "all"
    if source_type == "task" and not filters.get("github_task_id") and scheduler_task_ids:
        and_clauses.append({"github_task_id": {"$nin": scheduler_task_ids}})

    for field in ("repo_full_name", "path", "human_content", "keyword"):
        val = (filters.get(field) or "").strip()
        if val:
            and_clauses.append({field: {"$regex": re.escape(val), "$options": "i"}})

    triage_status = (filters.get("triage_status") or "").strip()
    if triage_status == TRIAGE_PENDING:
        and_clauses.append({
            "$or": [
                {"triage_status": TRIAGE_PENDING},
                {"triage_status": {"$exists": False}},
                {"triage_status": ""},
            ]
        })
    elif triage_status in (TRIAGE_CONFIRMED, TRIAGE_FALSE_POSITIVE):
        and_clauses.append({"triage_status": triage_status})

    only_ignored = bool(filters.get("only_ignored"))
    include_ignored = bool(filters.get("include_ignored"))
    if only_ignored:
        if ignored_repos:
            and_clauses.append({"repo_full_name": {"$in": ignored_repos}})
        else:
            # Force empty match when no repos are ignored
            and_clauses.append({"_id": {"$exists": False}, "repo_full_name": "__never_match__"})
    elif not include_ignored and ignored_repos:
        and_clauses.append({"repo_full_name": {"$nin": ignored_repos}})

    if not and_clauses:
        return {}
    if len(and_clauses) == 1:
        return and_clauses[0]
    return {"$and": and_clauses}


def _dedup_key_expr():
    return {
        "$ifNull": [
            "$hash_md5",
            {"$concat": [{"$ifNull": ["$repo_full_name", ""]}, "/", {"$ifNull": ["$path", ""]}]},
        ]
    }


def _enrich_finding_doc(
    raw_doc: Dict[str, Any],
    task_ids: List[str],
    scheduler_ids: List[str],
    task_map: Dict[str, Dict[str, str]],
    scheduler_map: Dict[str, Dict[str, str]],
    triage_map: Dict[str, Dict[str, str]],
    ignored_set: set,
) -> Dict[str, Any]:
    """Normalize a deduplicated finding document for API output."""
    item = dict(raw_doc)
    item["_id"] = str(item.get("_id", ""))
    if "update_date" in item:
        item["update_date"] = str(item["update_date"])

    clean_tids = [t for t in (task_ids or []) if t]
    clean_sids = [s for s in (scheduler_ids or []) if s]
    if item.get("github_task_id") and item["github_task_id"] not in clean_tids:
        clean_tids.append(item["github_task_id"])
    if item.get("github_scheduler_id") and item["github_scheduler_id"] not in clean_sids:
        clean_sids.append(item["github_scheduler_id"])

    # Infer scheduler attribution through parent github_task if needed
    for tid in clean_tids:
        meta = task_map.get(tid)
        if meta and meta.get("github_scheduler_id"):
            sid = meta["github_scheduler_id"]
            if sid not in clean_sids:
                clean_sids.append(sid)

    source_names: List[str] = []
    for sid in clean_sids:
        s_meta = scheduler_map.get(sid)
        if s_meta and s_meta.get("name"):
            source_names.append(s_meta["name"])
    for tid in clean_tids:
        t_meta = task_map.get(tid)
        if t_meta and t_meta.get("name") and not t_meta.get("github_scheduler_id"):
            source_names.append(t_meta["name"])

    if not source_names:
        for tid in clean_tids:
            t_meta = task_map.get(tid)
            if t_meta and t_meta.get("name"):
                source_names.append(t_meta["name"])

    hash_md5 = item.get("hash_md5") or f"{item.get('repo_full_name', '')}/{item.get('path', '')}"
    item["hash_md5"] = hash_md5

    persisted = triage_map.get(hash_md5)
    if persisted:
        item["triage_status"] = persisted["triage_status"]
        item["triage_note"] = persisted["note"]
        item["triage_updated_at"] = persisted["updated_at"]
    else:
        item["triage_status"] = item.get("triage_status") or TRIAGE_PENDING
        item["triage_note"] = item.get("triage_note") or ""
        item["triage_updated_at"] = item.get("triage_updated_at") or ""

    item["source_type"] = "scheduler" if clean_sids else "task"
    item["source_names"] = list(dict.fromkeys(source_names))
    item["task_ids"] = list(dict.fromkeys(clean_tids))
    item["scheduler_ids"] = list(dict.fromkeys(clean_sids))
    item["source_count"] = max(1, len(set(clean_sids) | {
        tid for tid in clean_tids if not (task_map.get(tid) or {}).get("github_scheduler_id")
    }))
    item["is_repo_ignored"] = item.get("repo_full_name", "") in ignored_set
    return item


def _build_base_dedup_pipeline(
    filters: Dict[str, Any],
    match_query: Dict[str, Any],
) -> tuple:
    """Return `(root_collection, pipeline)` deduplicating across result collections."""
    source_type = filters.get("source_type") or "all"
    has_task_id = bool(filters.get("github_task_id"))
    has_scheduler_id = bool(filters.get("github_scheduler_id"))

    pipeline: List[Dict[str, Any]] = []
    if match_query:
        pipeline.append({"$match": match_query})

    if has_scheduler_id or (source_type == "scheduler" and not has_task_id):
        root_col = "github_monitor_result"
    elif has_task_id or source_type == "task":
        root_col = "github_result"
    else:
        root_col = "github_result"
        union_stage: Dict[str, Any] = {"coll": "github_monitor_result"}
        if match_query:
            union_stage["pipeline"] = [{"$match": match_query}]
        pipeline.append({"$unionWith": union_stage})

    pipeline.extend([
        {"$sort": {"_id": -1}},
        {
            "$group": {
                "_id": _dedup_key_expr(),
                "doc": {"$first": "$$ROOT"},
                "task_ids": {"$addToSet": "$github_task_id"},
                "scheduler_ids": {"$addToSet": "$github_scheduler_id"},
            }
        },
        {"$sort": {"doc._id": -1}},
    ])
    return root_col, pipeline


def _dedup_key_value(doc: Dict[str, Any]) -> str:
    return doc.get("hash_md5") or f"{doc.get('repo_full_name', '')}/{doc.get('path', '')}"


def _collect_dedup_rows_fallback(filters: Dict[str, Any], match_query: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Fallback deduplication when $unionWith is unavailable (e.g. mongomock in tests)."""
    source_type = filters.get("source_type") or "all"
    has_task_id = bool(filters.get("github_task_id"))
    has_scheduler_id = bool(filters.get("github_scheduler_id"))

    docs: List[Dict[str, Any]] = []
    if has_scheduler_id or (source_type == "scheduler" and not has_task_id):
        docs.extend(utils.conn_db("github_monitor_result").find(match_query))
    elif has_task_id or source_type == "task":
        docs.extend(utils.conn_db("github_result").find(match_query))
    else:
        docs.extend(utils.conn_db("github_result").find(match_query))
        docs.extend(utils.conn_db("github_monitor_result").find(match_query))

    docs.sort(key=lambda d: str(d.get("_id", "")), reverse=True)
    grouped: Dict[str, Dict[str, Any]] = {}
    for doc in docs:
        key = _dedup_key_value(doc)
        entry = grouped.get(key)
        if entry is None:
            grouped[key] = {
                "_id": key,
                "doc": doc,
                "task_ids": [doc["github_task_id"]] if doc.get("github_task_id") else [],
                "scheduler_ids": [doc["github_scheduler_id"]] if doc.get("github_scheduler_id") else [],
            }
        else:
            if doc.get("github_task_id") and doc["github_task_id"] not in entry["task_ids"]:
                entry["task_ids"].append(doc["github_task_id"])
            if doc.get("github_scheduler_id") and doc["github_scheduler_id"] not in entry["scheduler_ids"]:
                entry["scheduler_ids"].append(doc["github_scheduler_id"])
    return list(grouped.values())


def query_unified_findings(filters: Dict[str, Any]) -> Dict[str, Any]:
    """Query deduplicated code leak findings in flat or repo-grouped mode."""
    page = max(1, int(filters.get("page") or 1))
    size = max(1, min(200, int(filters.get("size") or 10)))
    group_by = (filters.get("group_by") or "flat").strip().lower()

    ignored_repos = get_ignored_repo_names()
    ignored_set = set(ignored_repos)
    task_map, scheduler_map, scheduler_task_ids = _load_source_metadata()
    match_query = _build_match_query(filters, ignored_repos, scheduler_task_ids)
    root_col, base_pipeline = _build_base_dedup_pipeline(filters, match_query)

    skip = (page - 1) * size
    if group_by == "repo":
        pipeline = base_pipeline + [
            {
                "$group": {
                    "_id": "$doc.repo_full_name",
                    "latest_id": {"$max": "$doc._id"},
                    "latest_commit_date": {"$max": "$doc.commit_date"},
                    "file_count": {"$sum": 1},
                    "pending_count": {
                        "$sum": {
                            "$cond": [
                                {"$in": [{"$ifNull": ["$doc.triage_status", TRIAGE_PENDING]}, [TRIAGE_PENDING, ""]]},
                                1,
                                0,
                            ]
                        }
                    },
                    "confirmed_count": {
                        "$sum": {
                            "$cond": [{"$eq": ["$doc.triage_status", TRIAGE_CONFIRMED]}, 1, 0]
                        }
                    },
                    "false_positive_count": {
                        "$sum": {
                            "$cond": [{"$eq": ["$doc.triage_status", TRIAGE_FALSE_POSITIVE]}, 1, 0]
                        }
                    },
                    "keywords": {"$addToSet": "$doc.keyword"},
                    "files": {
                        "$push": {
                            "doc": "$doc",
                            "task_ids": "$task_ids",
                            "scheduler_ids": "$scheduler_ids",
                        }
                    },
                }
            },
            {"$sort": {"latest_id": -1}},
            {
                "$facet": {
                    "metadata": [{"$count": "total"}],
                    "data": [{"$skip": skip}, {"$limit": size}],
                }
            },
        ]
        try:
            agg_res = list(utils.conn_db(root_col).aggregate(pipeline, allowDiskUse=True))
            facet_doc = agg_res[0] if agg_res else {}
            total = (facet_doc.get("metadata") or [{}])[0].get("total", 0)
            raw_groups = facet_doc.get("data") or []
        except NotImplementedError:
            dedup_rows = _collect_dedup_rows_fallback(filters, match_query)
            by_repo: Dict[str, Dict[str, Any]] = {}
            for row in dedup_rows:
                doc = row["doc"]
                repo = doc.get("repo_full_name") or ""
                g = by_repo.setdefault(repo, {
                    "_id": repo,
                    "latest_id": doc.get("_id"),
                    "latest_commit_date": doc.get("commit_date") or "",
                    "file_count": 0,
                    "keywords": [],
                    "files": [],
                })
                g["file_count"] += 1
                if str(doc.get("commit_date") or "") > str(g["latest_commit_date"] or ""):
                    g["latest_commit_date"] = doc.get("commit_date") or ""
                if doc.get("keyword") and doc["keyword"] not in g["keywords"]:
                    g["keywords"].append(doc["keyword"])
                g["files"].append(row)
            all_groups = list(by_repo.values())
            total = len(all_groups)
            raw_groups = all_groups[skip:skip + size]

        all_hashes = [
            f["doc"].get("hash_md5")
            for g in raw_groups
            for f in (g.get("files") or [])
            if f.get("doc", {}).get("hash_md5")
        ]
        triage_map = get_triage_status_map(all_hashes)

        items = []
        for g in raw_groups:
            repo_name = g.get("_id") or ""
            enriched_files = [
                _enrich_finding_doc(
                    f.get("doc") or {},
                    f.get("task_ids") or [],
                    f.get("scheduler_ids") or [],
                    task_map,
                    scheduler_map,
                    triage_map,
                    ignored_set,
                )
                for f in (g.get("files") or [])
            ]
            pending_cnt = sum(1 for f in enriched_files if f["triage_status"] == TRIAGE_PENDING)
            confirmed_cnt = sum(1 for f in enriched_files if f["triage_status"] == TRIAGE_CONFIRMED)
            fp_cnt = sum(1 for f in enriched_files if f["triage_status"] == TRIAGE_FALSE_POSITIVE)
            items.append({
                "repo_full_name": repo_name,
                "file_count": g.get("file_count", len(enriched_files)),
                "pending_count": pending_cnt,
                "confirmed_count": confirmed_cnt,
                "false_positive_count": fp_cnt,
                "latest_commit_date": g.get("latest_commit_date") or "",
                "keywords": [k for k in (g.get("keywords") or []) if k],
                "is_repo_ignored": repo_name in ignored_set,
                "files": enriched_files,
            })

        return {
            "page": page,
            "size": size,
            "total": total,
            "group_by": "repo",
            "items": items,
        }

    pipeline = base_pipeline + [
        {
            "$facet": {
                "metadata": [{"$count": "total"}],
                "data": [{"$skip": skip}, {"$limit": size}],
            }
        }
    ]
    try:
        agg_res = list(utils.conn_db(root_col).aggregate(pipeline, allowDiskUse=True))
        facet_doc = agg_res[0] if agg_res else {}
        total = (facet_doc.get("metadata") or [{}])[0].get("total", 0)
        raw_rows = facet_doc.get("data") or []
    except NotImplementedError:
        dedup_rows = _collect_dedup_rows_fallback(filters, match_query)
        total = len(dedup_rows)
        raw_rows = dedup_rows[skip:skip + size]

    all_hashes = [r["doc"].get("hash_md5") for r in raw_rows if r.get("doc", {}).get("hash_md5")]
    triage_map = get_triage_status_map(all_hashes)

    items = [
        _enrich_finding_doc(
            r.get("doc") or {},
            r.get("task_ids") or [],
            r.get("scheduler_ids") or [],
            task_map,
            scheduler_map,
            triage_map,
            ignored_set,
        )
        for r in raw_rows
    ]

    return {
        "page": page,
        "size": size,
        "total": total,
        "group_by": "flat",
        "items": items,
    }


def get_findings_stats() -> Dict[str, int]:
    """Compute deduplicated triage counts and active GitHub monitor/task counts."""
    ignored_repos = get_ignored_repo_names()
    match_non_ignored = {"repo_full_name": {"$nin": ignored_repos}} if ignored_repos else {}

    pipeline: List[Dict[str, Any]] = []
    if match_non_ignored:
        pipeline.append({"$match": match_non_ignored})
    pipeline.append({
        "$unionWith": {
            "coll": "github_monitor_result",
            **({"pipeline": [{"$match": match_non_ignored}]} if match_non_ignored else {}),
        }
    })
    pipeline.extend([
        {"$sort": {"_id": -1}},
        {
            "$group": {
                "_id": _dedup_key_expr(),
                "triage_status": {"$first": {"$ifNull": ["$triage_status", TRIAGE_PENDING]}},
            }
        },
        {
            "$group": {
                "_id": {
                    "$cond": [
                        {"$in": ["$triage_status", [TRIAGE_CONFIRMED, TRIAGE_FALSE_POSITIVE]]},
                        "$triage_status",
                        TRIAGE_PENDING,
                    ]
                },
                "count": {"$sum": 1},
            }
        },
    ])

    counts = {TRIAGE_PENDING: 0, TRIAGE_CONFIRMED: 0, TRIAGE_FALSE_POSITIVE: 0}
    try:
        for row in utils.conn_db("github_result").aggregate(pipeline, allowDiskUse=True):
            status_key = row.get("_id")
            if status_key in counts:
                counts[status_key] = row.get("count", 0)
    except NotImplementedError:
        dedup_rows = _collect_dedup_rows_fallback({"source_type": "all"}, match_non_ignored)
        triage_map = get_triage_status_map([r["doc"].get("hash_md5") for r in dedup_rows if r["doc"].get("hash_md5")])
        for r in dedup_rows:
            doc = r["doc"]
            h = doc.get("hash_md5")
            st = (triage_map.get(h) or {}).get("triage_status") or doc.get("triage_status") or TRIAGE_PENDING
            if st not in counts:
                st = TRIAGE_PENDING
            counts[st] += 1
    except Exception:
        pass

    running_tasks = utils.conn_db("github_task").count_documents(
        {"status": {"$nin": ["done", "stop", "error"]}}
    )
    running_schedulers = utils.conn_db("github_scheduler").count_documents({"status": "running"})

    return {
        "pending": counts[TRIAGE_PENDING],
        "confirmed": counts[TRIAGE_CONFIRMED],
        "false_positive": counts[TRIAGE_FALSE_POSITIVE],
        "total": counts[TRIAGE_PENDING] + counts[TRIAGE_CONFIRMED] + counts[TRIAGE_FALSE_POSITIVE],
        "ignored_repos": len(ignored_repos),
        "running_tasks": running_tasks,
        "running_schedulers": running_schedulers,
    }


def export_unified_findings(filters: Dict[str, Any], export_format: str = "csv"):
    """Export filtered deduplicated findings as CSV or JSON (capped at 50,000 rows)."""
    ignored_repos = get_ignored_repo_names()
    ignored_set = set(ignored_repos)
    task_map, scheduler_map, scheduler_task_ids = _load_source_metadata()
    match_query = _build_match_query(filters, ignored_repos, scheduler_task_ids)
    root_col, base_pipeline = _build_base_dedup_pipeline(filters, match_query)

    pipeline = base_pipeline + [{"$limit": 50000}]
    try:
        raw_rows = list(utils.conn_db(root_col).aggregate(pipeline, allowDiskUse=True))
    except NotImplementedError:
        raw_rows = _collect_dedup_rows_fallback(filters, match_query)[:50000]
    all_hashes = [r["doc"].get("hash_md5") for r in raw_rows if r.get("doc", {}).get("hash_md5")]
    triage_map = get_triage_status_map(all_hashes)

    items = [
        _enrich_finding_doc(
            r.get("doc") or {},
            r.get("task_ids") or [],
            r.get("scheduler_ids") or [],
            task_map,
            scheduler_map,
            triage_map,
            ignored_set,
        )
        for r in raw_rows
    ]

    if export_format == "json":
        payload = json.dumps(items, ensure_ascii=False, indent=2, default=str)
        return payload, "application/json; charset=utf-8", "github_leak_findings.json"

    output = io.StringIO()
    writer = csv.writer(output)
    headers = [
        "repo_full_name",
        "path",
        "triage_status",
        "keyword",
        "source_type",
        "source_names",
        "commit_date",
        "html_url",
        "human_content",
        "triage_note",
    ]
    writer.writerow(headers)
    for item in items:
        writer.writerow([
            csv_literal(item.get("repo_full_name", "")),
            csv_literal(item.get("path", "")),
            csv_literal(item.get("triage_status", TRIAGE_PENDING)),
            csv_literal(item.get("keyword", "")),
            csv_literal(item.get("source_type", "")),
            csv_literal(", ".join(item.get("source_names") or [])),
            csv_literal(item.get("commit_date", "")),
            csv_literal(item.get("html_url", "")),
            csv_literal(item.get("human_content", "")),
            csv_literal(item.get("triage_note", "")),
        ])
    # Prefix UTF-8 BOM for Excel Chinese character compatibility
    return "\ufeff" + output.getvalue(), "text/csv; charset=utf-8", "github_leak_findings.csv"
