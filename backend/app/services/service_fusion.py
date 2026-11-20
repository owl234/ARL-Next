from urllib.parse import urlsplit
from pymongo import UpdateOne
from app import utils

WEAK_SERVICE_NAMES = frozenset({
    "",
    "unknown",
    "tcpwrapped",
    "none",
    "null",
    "service",
    "tcp",
})

CANONICAL_SOURCES = ("nmap", "npoc")


def _get_db(collection, db_getter=None):
    if callable(db_getter):
        return db_getter(collection)
    return utils.conn_db(collection)


def normalize_host(host_val) -> str:
    if host_val is None:
        return ""
    raw = str(host_val).strip()
    if not raw:
        return ""
    if "://" in raw:
        try:
            parsed = urlsplit(raw)
            if parsed.hostname:
                return parsed.hostname.strip("[] ").lower()
        except Exception:
            pass
    if raw.startswith("[") and "]" in raw:
        end = raw.find("]")
        return raw[1:end].strip().lower()
    if raw.count(":") == 1:
        host_part, port_part = raw.rsplit(":", 1)
        if port_part.isdigit():
            raw = host_part
    return raw.strip("[] ").lower()


def normalize_port(port_val):
    if port_val is None or isinstance(port_val, bool):
        return None
    if isinstance(port_val, int):
        return port_val if port_val > 0 else None
    raw = str(port_val).strip()
    if not raw:
        return None
    try:
        val = int(raw)
        return val if val > 0 else None
    except (ValueError, TypeError):
        return None


def is_weak_service_name(name) -> bool:
    if not name or not isinstance(name, str):
        return True
    cleaned = name.strip().lower()
    if cleaned in WEAK_SERVICE_NAMES:
        return True
    if cleaned.endswith("?"):
        return True
    return False


def choose_service_name(existing_name, new_name, prefer_new: bool = False) -> str:
    ex = str(existing_name or "").strip()
    nw = str(new_name or "").strip()
    ex_weak = is_weak_service_name(ex)
    nw_weak = is_weak_service_name(nw)

    if prefer_new:
        if not nw_weak:
            return nw
        if not ex_weak:
            return ex
        return nw.rstrip("?") or ex.rstrip("?") or "unknown"

    if not ex_weak:
        return ex
    if not nw_weak:
        return nw
    return ex.rstrip("?") or nw.rstrip("?") or "unknown"


def merge_sources(*source_items) -> list:
    found = []
    for item in source_items:
        if not item:
            continue
        if isinstance(item, str):
            tokens = [t.strip().lower() for t in item.split(",") if t.strip()]
        elif isinstance(item, (list, tuple, set)):
            tokens = []
            for sub in item:
                if isinstance(sub, str) and sub.strip():
                    tokens.append(sub.strip().lower())
                elif isinstance(sub, (list, tuple, set)):
                    for s2 in sub:
                        if isinstance(s2, str) and s2.strip():
                            tokens.append(s2.strip().lower())
        else:
            continue
        for tok in tokens:
            if tok == "python":
                tok = "npoc"
            if tok not in found:
                found.append(tok)

    ordered = [s for s in CANONICAL_SOURCES if s in found]
    for s in found:
        if s not in ordered:
            ordered.append(s)
    return ordered or ["nmap"]


def build_service_target(service_name, ip, port_id, existing_target: str = "") -> str:
    ip_str = normalize_host(ip)
    port_num = normalize_port(port_id)
    if not ip_str or port_num is None:
        return str(existing_target or "").strip()

    host_fmt = f"[{ip_str}]" if ":" in ip_str else ip_str
    svc = str(service_name or "").strip().lower().rstrip("?")
    scheme = svc if not is_weak_service_name(svc) else "tcp"

    ex_target = str(existing_target or "").strip()
    if ex_target and "://" in ex_target:
        ex_scheme = ex_target.split("://", 1)[0].strip().lower()
        if not is_weak_service_name(ex_scheme) and is_weak_service_name(svc):
            return ex_target
    return f"{scheme}://{host_fmt}:{port_num}"


def build_service_endpoint_doc(
    owner_field,
    owner_id,
    ip,
    port_id,
    service_name="",
    product="",
    version="",
    target="",
    sources=None,
    save_date=None,
    update_date=None,
    extra_fields=None,
) -> dict:
    clean_ip = normalize_host(ip)
    clean_port = normalize_port(port_id)
    clean_svc = choose_service_name("", service_name, prefer_new=True)
    clean_prod = str(product or "").strip()
    clean_ver = str(version or "").strip()
    clean_sources = merge_sources(sources)
    clean_target = build_service_target(clean_svc, clean_ip, clean_port, existing_target=target)

    doc = {
        "ip": clean_ip,
        "port_id": clean_port,
        "service_name": clean_svc,
        "product": clean_prod,
        "version": clean_ver,
        "target": clean_target,
        "sources": clean_sources,
        "service_info": [
            {
                "ip": clean_ip,
                "port_id": clean_port,
                "product": clean_prod,
                "version": clean_ver,
            }
        ],
    }
    if owner_field and owner_id is not None:
        doc[owner_field] = str(owner_id)
    if save_date is not None:
        doc["save_date"] = save_date
    if update_date is not None:
        doc["update_date"] = update_date
    if isinstance(extra_fields, dict):
        for k, v in extra_fields.items():
            if k not in doc and v is not None:
                doc[k] = v
    return doc


def expand_service_doc_to_endpoints(doc: dict, default_source: str = "nmap") -> list:
    """
    将单条服务文档（新版单端点 service、旧版含 service_info 数组的 service、或 npoc_service 文档）
    统一展开为标准单端点字典列表。
    """
    if not isinstance(doc, dict):
        return []

    owner_field = "scope_id" if "scope_id" in doc else ("task_id" if "task_id" in doc else None)
    owner_id = doc.get(owner_field) if owner_field else None
    save_date = doc.get("save_date")
    update_date = doc.get("update_date")
    extra = {}
    if "change_status" in doc:
        extra["change_status"] = doc["change_status"]
    if "update_diff" in doc and isinstance(doc["update_diff"], dict) and "service_info" not in doc["update_diff"]:
        extra["update_diff"] = doc["update_diff"]

    # 1. npoc_service / asset_npoc_service 格式: {scheme, host, port, target}
    if ("scheme" in doc or "host" in doc) and "service_name" not in doc:
        host = normalize_host(doc.get("host"))
        port = normalize_port(doc.get("port"))
        target = str(doc.get("target") or "").strip()
        scheme = str(doc.get("scheme") or "").strip()
        if (not host or port is None) and target:
            raw_t = target if "://" in target else f"tcp://{target}"
            try:
                parsed = urlsplit(raw_t)
                if not host and parsed.hostname:
                    host = parsed.hostname.strip("[] ").lower()
                if port is None and parsed.port:
                    port = normalize_port(parsed.port)
                if not scheme and parsed.scheme and parsed.scheme != "tcp":
                    scheme = parsed.scheme
            except Exception:
                pass
        if not host or port is None:
            return []
        return [
            build_service_endpoint_doc(
                owner_field=owner_field,
                owner_id=owner_id,
                ip=host,
                port_id=port,
                service_name=scheme or "unknown",
                product=doc.get("product") or "",
                version=doc.get("version") or "",
                target=target,
                sources=doc.get("sources") or ["npoc"],
                save_date=save_date,
                update_date=update_date,
                extra_fields=extra,
            )
        ]

    # 2. 新版单端点 service / asset_service 格式: 顶层含 ip 与 port_id
    top_ip = normalize_host(doc.get("ip"))
    top_port = normalize_port(doc.get("port_id"))
    svc_infos = doc.get("service_info")
    if top_ip and top_port is not None and (not isinstance(svc_infos, list) or len(svc_infos) <= 1):
        info0 = svc_infos[0] if (isinstance(svc_infos, list) and svc_infos and isinstance(svc_infos[0], dict)) else {}
        prod = doc.get("product") if doc.get("product") is not None else info0.get("product", "")
        ver = doc.get("version") if doc.get("version") is not None else info0.get("version", "")
        return [
            build_service_endpoint_doc(
                owner_field=owner_field,
                owner_id=owner_id,
                ip=top_ip,
                port_id=top_port,
                service_name=doc.get("service_name") or "",
                product=prod,
                version=ver,
                target=doc.get("target") or "",
                sources=doc.get("sources") or [default_source],
                save_date=save_date,
                update_date=update_date,
                extra_fields=extra,
            )
        ]

    # 3. 旧版按 service_name 聚合的嵌套 service_info 数组格式
    endpoints = []
    if isinstance(svc_infos, list):
        svc_name = doc.get("service_name") or ""
        sources = doc.get("sources") or [default_source]
        for info in svc_infos:
            if not isinstance(info, dict):
                continue
            ip_val = normalize_host(info.get("ip"))
            port_val = normalize_port(info.get("port_id"))
            if not ip_val or port_val is None:
                continue
            endpoints.append(
                build_service_endpoint_doc(
                    owner_field=owner_field,
                    owner_id=owner_id,
                    ip=ip_val,
                    port_id=port_val,
                    service_name=info.get("service_name") or svc_name,
                    product=info.get("product") or "",
                    version=info.get("version") or "",
                    target=info.get("target") or "",
                    sources=info.get("sources") or sources,
                    save_date=save_date,
                    update_date=update_date,
                    extra_fields=extra,
                )
            )
    return endpoints


def merge_endpoint_records(existing_ep: dict, incoming_ep: dict, prefer_incoming_service: bool = False) -> dict:
    if not existing_ep:
        return dict(incoming_ep)
    if not incoming_ep:
        return dict(existing_ep)

    owner_field = "scope_id" if ("scope_id" in existing_ep or "scope_id" in incoming_ep) else (
        "task_id" if ("task_id" in existing_ep or "task_id" in incoming_ep) else None
    )
    owner_id = (incoming_ep.get(owner_field) or existing_ep.get(owner_field)) if owner_field else None

    ip_val = normalize_host(incoming_ep.get("ip") or existing_ep.get("ip"))
    port_val = normalize_port(incoming_ep.get("port_id") if incoming_ep.get("port_id") is not None else existing_ep.get("port_id"))

    in_sources = incoming_ep.get("sources") or []
    ex_sources = existing_ep.get("sources") or []
    prefer_new = prefer_incoming_service or ("npoc" in in_sources and "npoc" not in ex_sources)

    merged_svc = choose_service_name(
        existing_ep.get("service_name"),
        incoming_ep.get("service_name"),
        prefer_new=prefer_new,
    )
    merged_prod = str(incoming_ep.get("product") or existing_ep.get("product") or "").strip()
    merged_ver = str(incoming_ep.get("version") or existing_ep.get("version") or "").strip()
    merged_sources = merge_sources(ex_sources, in_sources)

    raw_target = (
        incoming_ep.get("target")
        if (prefer_new and incoming_ep.get("target"))
        else (existing_ep.get("target") or incoming_ep.get("target") or "")
    )
    merged_target = build_service_target(merged_svc, ip_val, port_val, existing_target=raw_target)

    save_date = existing_ep.get("save_date") or incoming_ep.get("save_date")
    update_date = incoming_ep.get("update_date") or existing_ep.get("update_date") or save_date

    extra = {}
    for k in ("change_status", "update_diff", "_id"):
        if k in existing_ep:
            extra[k] = existing_ep[k]
        elif k in incoming_ep:
            extra[k] = incoming_ep[k]

    return build_service_endpoint_doc(
        owner_field=owner_field,
        owner_id=owner_id,
        ip=ip_val,
        port_id=port_val,
        service_name=merged_svc,
        product=merged_prod,
        version=merged_ver,
        target=merged_target,
        sources=merged_sources,
        save_date=save_date,
        update_date=update_date,
        extra_fields=extra,
    )


def format_service_endpoint_for_return(doc: dict) -> dict:
    """确保接口返回的每条服务记录具备完整的单端点字段（兼容旧版嵌套记录）。"""
    if not isinstance(doc, dict):
        return doc
    eps = expand_service_doc_to_endpoints(doc)
    if eps:
        ep = eps[0]
        for k in ("_id", "task_id", "scope_id", "save_date", "update_date", "change_status", "update_diff"):
            if k in doc and doc[k] is not None:
                ep[k] = doc[k]
        return ep
    return doc


def sync_npoc_items_to_service_and_ip(task_id, npoc_items, db_getter=None):
    """
    将 Python 插件服务识别 (npoc_service_detection) 结果实时合流至 db.service 并反哺校准 db.ip.port_info。
    """
    if not task_id or not npoc_items:
        return
    tid = str(task_id)
    svc_col = _get_db("service", db_getter)
    ip_col = _get_db("ip", db_getter)
    now_str = utils.curr_date()

    for item in npoc_items:
        for incoming in expand_service_doc_to_endpoints({**item, "task_id": tid}, default_source="npoc"):
            ip_val = incoming["ip"]
            port_val = incoming["port_id"]
            if not ip_val or port_val is None:
                continue

            port_cands = [port_val, str(port_val)]

            # 1. 若存在旧版未设置顶层 ip 的聚合文档，先从中提取旧 product/version 并剥离该端点
            legacy_prod = ""
            legacy_ver = ""
            legacy_sources = []
            for leg in svc_col.find(
                {"task_id": tid, "ip": {"$exists": False}, "service_info.ip": ip_val},
                {"service_name": 1, "service_info": 1, "sources": 1},
            ):
                for s_info in (leg.get("service_info") or []):
                    if isinstance(s_info, dict) and normalize_host(s_info.get("ip")) == ip_val and normalize_port(s_info.get("port_id")) == port_val:
                        legacy_prod = legacy_prod or s_info.get("product") or ""
                        legacy_ver = legacy_ver or s_info.get("version") or ""
                        legacy_sources = merge_sources(legacy_sources, leg.get("sources") or ["nmap"])
                svc_col.update_one(
                    {"_id": leg["_id"]},
                    {"$pull": {"service_info": {"ip": ip_val, "port_id": {"$in": port_cands}}}},
                )

            # 2. 查找当前任务是否已有该 (ip, port_id) 的单端点记录
            existing = svc_col.find_one({"task_id": tid, "ip": ip_val, "port_id": {"$in": port_cands}})
            if not existing and (legacy_prod or legacy_ver or legacy_sources):
                existing = build_service_endpoint_doc(
                    owner_field="task_id",
                    owner_id=tid,
                    ip=ip_val,
                    port_id=port_val,
                    service_name="",
                    product=legacy_prod,
                    version=legacy_ver,
                    sources=legacy_sources or ["nmap"],
                    save_date=now_str,
                )

            # 同时若 db.ip 中有该端口的 product/version 而 service 尚未记录，从 db.ip 补齐
            ip_doc = ip_col.find_one({"task_id": tid, "ip": ip_val}, {"port_info": 1})
            if ip_doc and isinstance(ip_doc.get("port_info"), list):
                for p_entry in ip_doc["port_info"]:
                    if isinstance(p_entry, dict) and normalize_port(p_entry.get("port_id")) == port_val:
                        ip_prod = p_entry.get("product") or ""
                        ip_ver = p_entry.get("version") or ""
                        ip_svc = p_entry.get("service_name") or ""
                        ip_sources = p_entry.get("sources") or ["nmap"]
                        if existing:
                            if not existing.get("product") and ip_prod:
                                existing["product"] = ip_prod
                            if not existing.get("version") and ip_ver:
                                existing["version"] = ip_ver
                            existing["sources"] = merge_sources(existing.get("sources"), ip_sources)
                        else:
                            existing = build_service_endpoint_doc(
                                owner_field="task_id",
                                owner_id=tid,
                                ip=ip_val,
                                port_id=port_val,
                                service_name=ip_svc,
                                product=ip_prod,
                                version=ip_ver,
                                sources=ip_sources,
                                save_date=now_str,
                            )
                        break

            merged = merge_endpoint_records(existing, incoming, prefer_incoming_service=True)
            merged.pop("_id", None)
            if not merged.get("save_date"):
                merged["save_date"] = item.get("save_date") or now_str

            svc_col.update_one(
                {"task_id": tid, "ip": ip_val, "port_id": port_val},
                {"$set": merged},
                upsert=True,
            )

            # 3. 反哺修正 db.ip.port_info 中的 service_name、sources 与 target
            set_fields = {
                "port_info.$.service_name": merged["service_name"],
                "port_info.$.sources": merged["sources"],
                "port_info.$.target": merged["target"],
            }
            if merged.get("product"):
                set_fields["port_info.$.product"] = merged["product"]
            if merged.get("version"):
                set_fields["port_info.$.version"] = merged["version"]

            res = ip_col.update_many(
                {"task_id": tid, "ip": ip_val, "port_info.port_id": port_val},
                {"$set": set_fields},
            )
            if res.matched_count == 0:
                ip_col.update_many(
                    {"task_id": tid, "ip": ip_val, "port_info.port_id": str(port_val)},
                    {"$set": set_fields},
                )

    # 清理旧版 service_info 已被掏空的历史文档
    svc_col.delete_many({"task_id": tid, "ip": {"$exists": False}, "service_info": {"$size": 0}})
