# coding: utf-8
"""资产侦查任务批量/单任务多工作表 Excel 导出服务。"""

from collections import Counter, OrderedDict
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
import re

from bson import ObjectId
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Font, PatternFill

from app import utils
from app.services.service_fusion import expand_service_doc_to_endpoints, merge_sources
from app.utils.excel_export import append_literal_row
from app.utils.task_statistics import TASK_STATISTIC_TABLES

MAX_EXPORT_TASKS = 100
MAX_ROWS_PER_SHEET = 50000
MAX_CELL_TEXT_LEN = 32767

SHEET_ORDER = (
    "overview",
    "site",
    "domain",
    "ip",
    "service",
    "vuln",
    "nuclei_result",
    "wih",
    "fileleak",
    "cert",
    "url",
    "cip",
    "statist",
)

DEFAULT_SHEETS = (
    "overview",
    "site",
    "domain",
    "ip",
    "service",
    "vuln",
    "nuclei_result",
    "statist",
)

SHEET_TITLES = {
    "overview": "任务概览",
    "site": "站点",
    "domain": "域名",
    "ip": "IP",
    "service": "系统服务",
    "vuln": "风险漏洞",
    "nuclei_result": "Nuclei漏洞",
    "wih": "WIH",
    "fileleak": "文件泄露",
    "cert": "SSL证书",
    "url": "URL",
    "cip": "C段",
    "statist": "资产统计",
}

# 状态文案字典与阶段名称字典严格分表维护（唯一事实源，与前端 constants/taskStatus.js 一致）
TASK_STATUS_LABEL = {
    "running": "进行中",
    "waiting": "排队中",
    "done": "已完成",
    "stop": "已停止",
    "error": "异常失败",
}

PLUGIN_STAGE_LABEL = {
    "domain_brute": "域名爆破",
    "dns_query_plugin": "域名查询插件",
    "arl_search": "ARL 历史查询",
    "alt_dns": "DNS 字典生成",
    "recursive_domain_brute": "递归域名爆破",
    "port_scan": "端口扫描",
    "ssl_cert": "SSL 证书获取",
    "service_detection": "服务识别",
    "os_detection": "操作系统识别",
    "find_site": "站点发现",
    "fetch_site": "站点探测",
    "site_identify": "站点识别",
    "site_capture": "站点截图",
    "search_engines": "搜索引擎",
    "site_spider": "站点爬虫",
    "file_leak": "文件泄露",
    "find_vhost": "Host 碰撞",
    "findvhost": "Host 碰撞",
    "npoc_service_detection": "Python 服务识别",
    "poc_run": "风险巡航",
    "nuclei_scan": "Nuclei 扫描",
    "weak_brute": "弱口令爆破",
    "wih_domain_update": "WIH 域名更新",
    "web_info_hunter": "WIH 信息收集",
}

TERMINAL_STATUSES = frozenset({"done", "stop", "error"})
ILLEGAL_XML_CHARS_RE = re.compile(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]")
SAFE_FILENAME_RE = re.compile(r'[\\/:*?"<>|\r\n\t]+')

HEADER_FONT = Font(name="Calibri", size=11, bold=True, color="1F2937")
HEADER_FILL = PatternFill(fill_type="solid", start_color="F3F4F6", end_color="F3F4F6")
SECTION_FONT = Font(name="Calibri", size=11, bold=True, color="111827")


class TaskExcelExportError(ValueError):
    """参数校验或任务查询失败时抛出的业务异常。"""

    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


@dataclass
class TaskExcelExportResult:
    content: bytes
    filename: str
    task_count: int
    deduplicate: bool
    has_active_tasks: bool
    included_sheets: list = field(default_factory=list)
    empty_sheets: list = field(default_factory=list)
    truncated_sheets: list = field(default_factory=list)
    sheet_row_counts: dict = field(default_factory=dict)


def format_task_status_label(status) -> str:
    raw = str(status or "").strip()
    if not raw:
        return TASK_STATUS_LABEL["running"]
    if raw in TASK_STATUS_LABEL:
        return TASK_STATUS_LABEL[raw]
    stage_name = PLUGIN_STAGE_LABEL.get(raw, raw)
    return f"进行中 · {stage_name}"


def is_active_task_status(status) -> bool:
    return str(status or "").strip() not in TERMINAL_STATUSES


def _clean_text(value) -> str:
    if value is None:
        return ""
    text = str(value)
    text = ILLEGAL_XML_CHARS_RE.sub("", text)
    if len(text) > MAX_CELL_TEXT_LEN:
        text = text[: MAX_CELL_TEXT_LEN - 3] + "..."
    return text


def _sanitize_row(values) -> list:
    sanitized = []
    for val in values:
        if val is None or isinstance(val, (int, float)) and not isinstance(val, bool):
            sanitized.append(val)
        elif isinstance(val, bool):
            sanitized.append("是" if val else "否")
        else:
            sanitized.append(_clean_text(val))
    return sanitized


def _append_styled_row(ws, values, font=None, fill=None):
    cells = []
    for raw in _sanitize_row(values):
        cell = WriteOnlyCell(ws, value=raw)
        if isinstance(raw, str):
            cell.data_type = "s"
        if font is not None:
            cell.font = font
        if fill is not None:
            cell.fill = fill
        cells.append(cell)
    ws.append(cells)


def _append_data_row(ws, values):
    append_literal_row(ws, _sanitize_row(values))


def _set_col_widths(ws, widths):
    for idx, width in enumerate(widths, start=1):
        col_letter = _col_index_to_letter(idx)
        ws.column_dimensions[col_letter].width = float(width)


def _col_index_to_letter(index: int) -> str:
    letters = []
    n = index
    while n > 0:
        n, rem = divmod(n - 1, 26)
        letters.append(chr(65 + rem))
    return "".join(reversed(letters))


def _format_datetime(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    return _clean_text(value)


def _earlier_date(left: str, right: str) -> str:
    if not left:
        return right
    if not right:
        return left
    return left if left <= right else right


def _unique_ordered_list(items) -> list:
    result = []
    seen = set()
    for item in items:
        text = str(item or "").strip()
        if text and text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _extend_unique(target: list, values):
    existing = set(target)
    for val in values:
        text = str(val or "").strip()
        if text and text not in existing:
            existing.add(text)
            target.append(text)


def _format_geo_city(raw_geo) -> str:
    geo_city = raw_geo if isinstance(raw_geo, dict) else {}
    parts = [
        str(c).strip()
        for c in (
            geo_city.get("country_name"),
            geo_city.get("region_name"),
            geo_city.get("city"),
        )
        if c and str(c).strip() not in ("None", "null", "0")
    ]
    deduped = []
    for part in parts:
        if not deduped or deduped[-1] != part:
            deduped.append(part)
    return "/".join(deduped)


def _format_geo_asn(raw_asn) -> str:
    if not isinstance(raw_asn, dict):
        return ""
    org = str(raw_asn.get("organization") or "").strip()
    num = raw_asn.get("number")
    if num and org:
        return f"AS{num} {org}"
    if org:
        return org
    if num:
        return f"AS{num}"
    return ""


def _derive_c_segment(ip_str: str, raw_c_segment) -> str:
    if raw_c_segment:
        return str(raw_c_segment).strip()
    parts = ip_str.split(".")
    if len(parts) == 4 and all(p.isdigit() for p in parts):
        return f"{parts[0]}.{parts[1]}.{parts[2]}.0/24"
    return ""


def _safe_filename_part(text: str, max_len: int = 36) -> str:
    cleaned = SAFE_FILENAME_RE.sub("_", str(text or "").strip())
    cleaned = re.sub(r"_+", "_", cleaned).strip("._ ")
    return cleaned[:max_len]


def _build_task_labels(tasks: list) -> dict:
    name_counts = Counter(str(t.get("name") or "").strip() for t in tasks)
    labels = {}
    for task in tasks:
        tid = str(task["_id"])
        name = str(task.get("name") or "").strip()
        target = str(task.get("target") or "").strip()
        if name and name_counts[name] == 1:
            labels[tid] = name
        elif name:
            short_target = target[:24] + ("..." if len(target) > 24 else "")
            suffix = short_target if short_target and short_target != name else tid[:8]
            labels[tid] = f"{name} ({suffix})"
        elif target:
            labels[tid] = target[:32] + ("..." if len(target) > 32 else "")
        else:
            labels[tid] = tid
    return labels


def _resolve_task_statistic(task: dict, db_getter) -> dict:
    tid = str(task["_id"])
    raw_stat = task.get("statistic") if isinstance(task.get("statistic"), dict) else {}
    stat = {}
    need_live = is_active_task_status(task.get("status"))
    for table in TASK_STATISTIC_TABLES:
        key = f"{table}_cnt"
        if not need_live and key in raw_stat and raw_stat[key] is not None:
            stat[key] = int(raw_stat[key])
        else:
            stat[key] = int(db_getter(table).count_documents({"task_id": tid}))
    return stat


def validate_export_params(task_id_list, sheets=None, deduplicate=True, max_tasks=MAX_EXPORT_TASKS):
    if not isinstance(task_id_list, list) or len(task_id_list) == 0:
        raise TaskExcelExportError("请至少选择一个任务进行导出", status_code=400)

    normalized_ids = []
    seen = set()
    for raw_id in task_id_list:
        if not isinstance(raw_id, str) or not ObjectId.is_valid(raw_id.strip()):
            raise TaskExcelExportError(f"包含无效的任务 ID: {raw_id}", status_code=400)
        tid = raw_id.strip()
        if tid not in seen:
            seen.add(tid)
            normalized_ids.append(tid)

    if len(normalized_ids) > max_tasks:
        raise TaskExcelExportError(f"单次最多支持导出 {max_tasks} 个任务", status_code=400)

    if sheets is None:
        selected_sheets = list(DEFAULT_SHEETS)
    else:
        if not isinstance(sheets, list) or len(sheets) == 0:
            raise TaskExcelExportError("请至少选择一个导出工作表维度", status_code=400)
        invalid = [s for s in sheets if not isinstance(s, str) or s.strip() not in SHEET_TITLES]
        if invalid:
            raise TaskExcelExportError(f"包含不支持的导出维度: {', '.join(map(str, invalid))}", status_code=400)
        requested_set = {s.strip() for s in sheets}
        selected_sheets = [key for key in SHEET_ORDER if key in requested_set]
        if not selected_sheets:
            raise TaskExcelExportError("请至少选择一个导出工作表维度", status_code=400)

    return normalized_ids, selected_sheets, bool(deduplicate)


def _iter_cursor_docs(collection, query, projection=None, limit=None):
    cursor = collection.find(query, projection)
    if limit is not None and hasattr(cursor, "limit"):
        cursor = cursor.limit(limit)
    return cursor


def _collect_site_rows(db_getter, task_ids, task_labels, deduplicate, max_rows):
    headers = ["站点", "标题", "状态码", "Web服务", "指纹", "Favicon Hash", "IP", "标签", "发现时间", "来源任务"]
    widths = [38, 36, 10, 22, 36, 18, 18, 22, 20, 28]
    projection = {
        "site": 1, "title": 1, "status": 1, "http_server": 1,
        "finger": 1, "favicon.hash": 1, "ip": 1, "tag": 1,
        "save_date": 1, "task_id": 1,
    }
    query = {"task_id": {"$in": task_ids}}

    if not deduplicate:
        rows = []
        truncated = False
        for doc in _iter_cursor_docs(db_getter("site"), query, projection, limit=max_rows + 1):
            if len(rows) >= max_rows:
                truncated = True
                break
            fingers = _unique_ordered_list(
                x.get("name") for x in (doc.get("finger") or []) if isinstance(x, dict)
            )
            raw_tag = doc.get("tag")
            tags = _unique_ordered_list(raw_tag if isinstance(raw_tag, list) else ([raw_tag] if raw_tag else []))
            favicon = doc.get("favicon") if isinstance(doc.get("favicon"), dict) else {}
            rows.append([
                doc.get("site") or "",
                doc.get("title") or "",
                doc.get("status"),
                doc.get("http_server") or "",
                ", ".join(fingers),
                favicon.get("hash") if favicon.get("hash") is not None else "",
                doc.get("ip") or "",
                ", ".join(tags),
                _format_datetime(doc.get("save_date")),
                task_labels.get(str(doc.get("task_id") or ""), ""),
            ])
        return headers, widths, rows, truncated

    merged = OrderedDict()
    truncated = False
    for doc in _iter_cursor_docs(db_getter("site"), query, projection):
        site_url = str(doc.get("site") or "").strip()
        key = site_url.lower() if site_url else str(doc.get("_id") or len(merged))
        fingers = _unique_ordered_list(
            x.get("name") for x in (doc.get("finger") or []) if isinstance(x, dict)
        )
        raw_tag = doc.get("tag")
        tags = _unique_ordered_list(raw_tag if isinstance(raw_tag, list) else ([raw_tag] if raw_tag else []))
        favicon = doc.get("favicon") if isinstance(doc.get("favicon"), dict) else {}
        fav_hash = favicon.get("hash") if favicon.get("hash") is not None else ""
        t_label = task_labels.get(str(doc.get("task_id") or ""), "")
        s_date = _format_datetime(doc.get("save_date"))

        if key in merged:
            rec = merged[key]
            if not rec["title"] and doc.get("title"):
                rec["title"] = doc.get("title")
            if rec["status"] is None and doc.get("status") is not None:
                rec["status"] = doc.get("status")
            if not rec["http_server"] and doc.get("http_server"):
                rec["http_server"] = doc.get("http_server")
            if rec["fav_hash"] == "" and fav_hash != "":
                rec["fav_hash"] = fav_hash
            if not rec["ip"] and doc.get("ip"):
                rec["ip"] = doc.get("ip")
            _extend_unique(rec["fingers"], fingers)
            _extend_unique(rec["tags"], tags)
            rec["save_date"] = _earlier_date(rec["save_date"], s_date)
            _extend_unique(rec["tasks"], [t_label])
        else:
            if len(merged) >= max_rows:
                truncated = True
                break
            merged[key] = {
                "site": site_url,
                "title": doc.get("title") or "",
                "status": doc.get("status"),
                "http_server": doc.get("http_server") or "",
                "fingers": fingers,
                "fav_hash": fav_hash,
                "ip": doc.get("ip") or "",
                "tags": tags,
                "save_date": s_date,
                "tasks": [t_label] if t_label else [],
            }

    rows = [
        [
            r["site"], r["title"], r["status"], r["http_server"],
            ", ".join(r["fingers"]), r["fav_hash"], r["ip"],
            ", ".join(r["tags"]), r["save_date"], ", ".join(r["tasks"]),
        ]
        for r in merged.values()
    ]
    return headers, widths, rows, truncated


def _collect_domain_rows(db_getter, task_ids, task_labels, deduplicate, max_rows):
    headers = ["域名", "解析类型", "记录值", "关联IP", "来源", "发现时间", "来源任务"]
    widths = [34, 12, 40, 32, 18, 20, 28]
    projection = {"domain": 1, "type": 1, "record": 1, "ips": 1, "source": 1, "save_date": 1, "task_id": 1}
    query = {"task_id": {"$in": task_ids}}

    if not deduplicate:
        rows = []
        truncated = False
        for doc in _iter_cursor_docs(db_getter("domain"), query, projection, limit=max_rows + 1):
            if len(rows) >= max_rows:
                truncated = True
                break
            records = _unique_ordered_list(doc.get("record") if isinstance(doc.get("record"), list) else [doc.get("record")])
            ips = _unique_ordered_list(doc.get("ips") if isinstance(doc.get("ips"), list) else [doc.get("ips")])
            rows.append([
                doc.get("domain") or "",
                doc.get("type") or "",
                "\n".join(records),
                "\n".join(ips),
                doc.get("source") or "",
                _format_datetime(doc.get("save_date")),
                task_labels.get(str(doc.get("task_id") or ""), ""),
            ])
        return headers, widths, rows, truncated

    merged = OrderedDict()
    truncated = False
    for doc in _iter_cursor_docs(db_getter("domain"), query, projection):
        dom = str(doc.get("domain") or "").strip()
        dtype = str(doc.get("type") or "").strip()
        key = (dom.lower(), dtype.upper()) if dom else (str(doc.get("_id") or len(merged)), dtype)
        records = _unique_ordered_list(doc.get("record") if isinstance(doc.get("record"), list) else [doc.get("record")])
        ips = _unique_ordered_list(doc.get("ips") if isinstance(doc.get("ips"), list) else [doc.get("ips")])
        src = str(doc.get("source") or "").strip()
        t_label = task_labels.get(str(doc.get("task_id") or ""), "")
        s_date = _format_datetime(doc.get("save_date"))

        if key in merged:
            rec = merged[key]
            _extend_unique(rec["record"], records)
            _extend_unique(rec["ips"], ips)
            _extend_unique(rec["source"], [src])
            rec["save_date"] = _earlier_date(rec["save_date"], s_date)
            _extend_unique(rec["tasks"], [t_label])
        else:
            if len(merged) >= max_rows:
                truncated = True
                break
            merged[key] = {
                "domain": dom,
                "type": dtype,
                "record": records,
                "ips": ips,
                "source": [src] if src else [],
                "save_date": s_date,
                "tasks": [t_label] if t_label else [],
            }

    rows = [
        [
            r["domain"], r["type"], "\n".join(r["record"]), "\n".join(r["ips"]),
            ", ".join(r["source"]), r["save_date"], ", ".join(r["tasks"]),
        ]
        for r in merged.values()
    ]
    return headers, widths, rows, truncated


def _sort_port_ids(port_ids) -> list:
    def _key(val):
        try:
            return (0, int(val))
        except (TypeError, ValueError):
            return (1, str(val))
    return sorted(port_ids, key=_key)


def _collect_ip_rows(db_getter, task_ids, task_labels, deduplicate, max_rows):
    headers = ["IP", "C段", "开放端口", "开放端口数", "操作系统", "关联域名", "地理位置", "AS信息", "CDN", "IP类型", "发现时间", "来源任务"]
    widths = [18, 18, 36, 12, 24, 38, 24, 34, 18, 12, 20, 28]
    projection = {
        "ip": 1, "c_segment": 1, "port_info": 1, "os_info": 1,
        "domain": 1, "geo_city": 1, "geo_asn": 1, "cdn_name": 1,
        "ip_type": 1, "save_date": 1, "task_id": 1,
    }
    query = {"task_id": {"$in": task_ids}}

    if not deduplicate:
        rows = []
        truncated = False
        for doc in _iter_cursor_docs(db_getter("ip"), query, projection, limit=max_rows + 1):
            if len(rows) >= max_rows:
                truncated = True
                break
            ip_str = str(doc.get("ip") or "").strip()
            ports = _sort_port_ids(_unique_ordered_list(
                p.get("port_id") for p in (doc.get("port_info") or []) if isinstance(p, dict) and p.get("port_id") is not None
            ))
            domains = _unique_ordered_list(doc.get("domain") if isinstance(doc.get("domain"), list) else [doc.get("domain")])
            os_info = doc.get("os_info") if isinstance(doc.get("os_info"), dict) else {}
            rows.append([
                ip_str,
                _derive_c_segment(ip_str, doc.get("c_segment")),
                ", ".join(ports),
                len(ports),
                os_info.get("name") or "",
                "\n".join(domains),
                _format_geo_city(doc.get("geo_city")),
                _format_geo_asn(doc.get("geo_asn")),
                doc.get("cdn_name") or "",
                doc.get("ip_type") or "",
                _format_datetime(doc.get("save_date")),
                task_labels.get(str(doc.get("task_id") or ""), ""),
            ])
        return headers, widths, rows, truncated

    merged = OrderedDict()
    truncated = False
    for doc in _iter_cursor_docs(db_getter("ip"), query, projection):
        ip_str = str(doc.get("ip") or "").strip()
        key = ip_str or str(doc.get("_id") or len(merged))
        ports = _unique_ordered_list(
            p.get("port_id") for p in (doc.get("port_info") or []) if isinstance(p, dict) and p.get("port_id") is not None
        )
        domains = _unique_ordered_list(doc.get("domain") if isinstance(doc.get("domain"), list) else [doc.get("domain")])
        os_info = doc.get("os_info") if isinstance(doc.get("os_info"), dict) else {}
        os_name = str(os_info.get("name") or "").strip()
        geo_str = _format_geo_city(doc.get("geo_city"))
        asn_str = _format_geo_asn(doc.get("geo_asn"))
        cdn = str(doc.get("cdn_name") or "").strip()
        ip_type = str(doc.get("ip_type") or "").strip()
        c_seg = _derive_c_segment(ip_str, doc.get("c_segment"))
        t_label = task_labels.get(str(doc.get("task_id") or ""), "")
        s_date = _format_datetime(doc.get("save_date"))

        if key in merged:
            rec = merged[key]
            _extend_unique(rec["ports"], ports)
            _extend_unique(rec["domains"], domains)
            if not rec["c_segment"] and c_seg:
                rec["c_segment"] = c_seg
            if not rec["os_name"] and os_name:
                rec["os_name"] = os_name
            if not rec["geo"] and geo_str:
                rec["geo"] = geo_str
            if not rec["asn"] and asn_str:
                rec["asn"] = asn_str
            if not rec["cdn"] and cdn:
                rec["cdn"] = cdn
            if not rec["ip_type"] and ip_type:
                rec["ip_type"] = ip_type
            rec["save_date"] = _earlier_date(rec["save_date"], s_date)
            _extend_unique(rec["tasks"], [t_label])
        else:
            if len(merged) >= max_rows:
                truncated = True
                break
            merged[key] = {
                "ip": ip_str,
                "c_segment": c_seg,
                "ports": ports,
                "os_name": os_name,
                "domains": domains,
                "geo": geo_str,
                "asn": asn_str,
                "cdn": cdn,
                "ip_type": ip_type,
                "save_date": s_date,
                "tasks": [t_label] if t_label else [],
            }

    rows = []
    for r in merged.values():
        sorted_ports = _sort_port_ids(r["ports"])
        rows.append([
            r["ip"], r["c_segment"], ", ".join(sorted_ports), len(sorted_ports),
            r["os_name"], "\n".join(r["domains"]), r["geo"], r["asn"],
            r["cdn"], r["ip_type"], r["save_date"], ", ".join(r["tasks"]),
        ])
    return headers, widths, rows, truncated


def _iter_service_endpoints(db_getter, task_ids):
    """读取融合后的 service 集合，并按 (task_id, ip, port_id) 补齐历史/未完整写入任务的 ip.port_info 端点。"""
    seen_task_endpoints = set()
    query = {"task_id": {"$in": task_ids}}
    for doc in _iter_cursor_docs(db_getter("service"), query):
        tid = str(doc.get("task_id") or "")
        for ep in expand_service_doc_to_endpoints(doc):
            ep_tid = str(ep.get("task_id") or tid)
            ep["task_id"] = ep_tid
            ep_ip = str(ep.get("ip") or "").strip()
            ep_port = ep.get("port_id")
            if ep_ip and ep_port is not None:
                seen_task_endpoints.add((ep_tid, ep_ip, str(ep_port)))
            yield ep

    ip_projection = {"ip": 1, "port_info": 1, "save_date": 1, "task_id": 1}
    for doc in _iter_cursor_docs(db_getter("ip"), query, ip_projection):
        ip_str = str(doc.get("ip") or "").strip()
        tid = str(doc.get("task_id") or "")
        s_date = doc.get("save_date")
        for p in (doc.get("port_info") or []):
            if not isinstance(p, dict) or p.get("port_id") is None:
                continue
            port_id = p.get("port_id")
            if ip_str and (tid, ip_str, str(port_id)) in seen_task_endpoints:
                continue
            svc_name = str(p.get("service_name") or "").strip() or "unknown"
            if ip_str:
                seen_task_endpoints.add((tid, ip_str, str(port_id)))
            yield {
                "ip": ip_str,
                "port_id": port_id,
                "service_name": svc_name,
                "product": str(p.get("product") or "").strip(),
                "version": str(p.get("version") or "").strip(),
                "sources": ["nmap"],
                "target": f"{svc_name}://{ip_str}:{port_id}" if ip_str else "",
                "save_date": s_date,
                "task_id": tid,
            }


def _collect_service_rows(db_getter, task_ids, task_labels, deduplicate, max_rows):
    headers = ["IP", "端口", "服务/协议", "产品", "版本", "识别来源", "目标", "发现时间", "来源任务"]
    widths = [18, 10, 16, 28, 18, 16, 30, 20, 28]

    if not deduplicate:
        rows = []
        truncated = False
        for ep in _iter_service_endpoints(db_getter, task_ids):
            if len(rows) >= max_rows:
                truncated = True
                break
            sources = merge_sources(ep.get("sources"))
            rows.append([
                ep.get("ip") or "",
                ep.get("port_id"),
                ep.get("service_name") or "",
                ep.get("product") or "",
                ep.get("version") or "",
                ", ".join(sources),
                ep.get("target") or "",
                _format_datetime(ep.get("save_date")),
                task_labels.get(str(ep.get("task_id") or ""), ""),
            ])
        return headers, widths, rows, truncated

    merged = OrderedDict()
    truncated = False
    for ep in _iter_service_endpoints(db_getter, task_ids):
        ip_str = str(ep.get("ip") or "").strip()
        port_id = ep.get("port_id")
        svc_name = str(ep.get("service_name") or "").strip()
        key = (ip_str, port_id, svc_name.lower())
        sources = merge_sources(ep.get("sources"))
        t_label = task_labels.get(str(ep.get("task_id") or ""), "")
        s_date = _format_datetime(ep.get("save_date"))

        if key in merged:
            rec = merged[key]
            if not rec["product"] and ep.get("product"):
                rec["product"] = ep.get("product")
            if not rec["version"] and ep.get("version"):
                rec["version"] = ep.get("version")
            if not rec["target"] and ep.get("target"):
                rec["target"] = ep.get("target")
            rec["sources"] = merge_sources(rec["sources"], sources)
            rec["save_date"] = _earlier_date(rec["save_date"], s_date)
            _extend_unique(rec["tasks"], [t_label])
        else:
            if len(merged) >= max_rows:
                truncated = True
                break
            merged[key] = {
                "ip": ip_str,
                "port_id": port_id,
                "service_name": svc_name,
                "product": ep.get("product") or "",
                "version": ep.get("version") or "",
                "sources": sources,
                "target": ep.get("target") or "",
                "save_date": s_date,
                "tasks": [t_label] if t_label else [],
            }

    rows = [
        [
            r["ip"], r["port_id"], r["service_name"], r["product"], r["version"],
            ", ".join(r["sources"]), r["target"], r["save_date"], ", ".join(r["tasks"]),
        ]
        for r in merged.values()
    ]
    return headers, widths, rows, truncated


def _collect_vuln_rows(db_getter, task_ids, task_labels, deduplicate, max_rows):
    headers = ["漏洞名称", "类别", "应用名", "目标", "验证信息", "发现时间", "来源任务"]
    widths = [32, 18, 20, 34, 48, 20, 28]
    projection = {
        "vul_name": 1, "vuln_name": 1, "vul_category": 1, "vuln_type": 1,
        "app_name": 1, "target": 1, "verify_data": 1, "proof": 1,
        "save_date": 1, "task_id": 1,
    }
    query = {"task_id": {"$in": task_ids}}

    if not deduplicate:
        rows = []
        truncated = False
        for doc in _iter_cursor_docs(db_getter("vuln"), query, projection, limit=max_rows + 1):
            if len(rows) >= max_rows:
                truncated = True
                break
            rows.append([
                doc.get("vul_name") or doc.get("vuln_name") or "",
                doc.get("vul_category") or doc.get("vuln_type") or "",
                doc.get("app_name") or "",
                doc.get("target") or "",
                doc.get("verify_data") or doc.get("proof") or "",
                _format_datetime(doc.get("save_date")),
                task_labels.get(str(doc.get("task_id") or ""), ""),
            ])
        return headers, widths, rows, truncated

    merged = OrderedDict()
    truncated = False
    for doc in _iter_cursor_docs(db_getter("vuln"), query, projection):
        v_name = str(doc.get("vul_name") or doc.get("vuln_name") or "").strip()
        v_cat = str(doc.get("vul_category") or doc.get("vuln_type") or "").strip()
        app_name = str(doc.get("app_name") or "").strip()
        target = str(doc.get("target") or "").strip()
        verify = str(doc.get("verify_data") or doc.get("proof") or "").strip()
        key = (v_name, target, app_name)
        t_label = task_labels.get(str(doc.get("task_id") or ""), "")
        s_date = _format_datetime(doc.get("save_date"))

        if key in merged:
            rec = merged[key]
            if not rec["vul_category"] and v_cat:
                rec["vul_category"] = v_cat
            if not rec["verify_data"] and verify:
                rec["verify_data"] = verify
            rec["save_date"] = _earlier_date(rec["save_date"], s_date)
            _extend_unique(rec["tasks"], [t_label])
        else:
            if len(merged) >= max_rows:
                truncated = True
                break
            merged[key] = {
                "vul_name": v_name,
                "vul_category": v_cat,
                "app_name": app_name,
                "target": target,
                "verify_data": verify,
                "save_date": s_date,
                "tasks": [t_label] if t_label else [],
            }

    rows = [
        [
            r["vul_name"], r["vul_category"], r["app_name"], r["target"],
            r["verify_data"], r["save_date"], ", ".join(r["tasks"]),
        ]
        for r in merged.values()
    ]
    return headers, widths, rows, truncated


def _format_nuclei_source(raw_source) -> str:
    val = str(raw_source or "").strip().lower()
    if val == "custom":
        return "自建"
    return "社区"


def _collect_nuclei_rows(db_getter, task_ids, task_labels, deduplicate, max_rows):
    headers = ["模板ID", "漏洞名称", "严重等级", "目标", "漏洞URL", "模板来源", "验证命令", "发现时间", "来源任务"]
    widths = [26, 32, 12, 30, 42, 12, 48, 20, 28]
    projection = {
        "template_id": 1, "vuln_name": 1, "vuln_severity": 1, "target": 1,
        "vuln_url": 1, "template_source": 1, "verify_command": 1, "curl_command": 1,
        "save_date": 1, "task_id": 1,
    }
    query = {"task_id": {"$in": task_ids}}

    if not deduplicate:
        rows = []
        truncated = False
        for doc in _iter_cursor_docs(db_getter("nuclei_result"), query, projection, limit=max_rows + 1):
            if len(rows) >= max_rows:
                truncated = True
                break
            rows.append([
                doc.get("template_id") or "",
                doc.get("vuln_name") or "",
                doc.get("vuln_severity") or "",
                doc.get("target") or "",
                doc.get("vuln_url") or "",
                _format_nuclei_source(doc.get("template_source")),
                doc.get("verify_command") or doc.get("curl_command") or "",
                _format_datetime(doc.get("save_date")),
                task_labels.get(str(doc.get("task_id") or ""), ""),
            ])
        return headers, widths, rows, truncated

    merged = OrderedDict()
    truncated = False
    for doc in _iter_cursor_docs(db_getter("nuclei_result"), query, projection):
        tpl_id = str(doc.get("template_id") or "").strip()
        vuln_url = str(doc.get("vuln_url") or "").strip()
        target = str(doc.get("target") or "").strip()
        key = (tpl_id, vuln_url or target)
        cmd = str(doc.get("verify_command") or doc.get("curl_command") or "").strip()
        t_label = task_labels.get(str(doc.get("task_id") or ""), "")
        s_date = _format_datetime(doc.get("save_date"))

        if key in merged:
            rec = merged[key]
            if not rec["vuln_name"] and doc.get("vuln_name"):
                rec["vuln_name"] = doc.get("vuln_name")
            if not rec["vuln_severity"] and doc.get("vuln_severity"):
                rec["vuln_severity"] = doc.get("vuln_severity")
            if not rec["verify_command"] and cmd:
                rec["verify_command"] = cmd
            rec["save_date"] = _earlier_date(rec["save_date"], s_date)
            _extend_unique(rec["tasks"], [t_label])
        else:
            if len(merged) >= max_rows:
                truncated = True
                break
            merged[key] = {
                "template_id": tpl_id,
                "vuln_name": doc.get("vuln_name") or "",
                "vuln_severity": doc.get("vuln_severity") or "",
                "target": target,
                "vuln_url": vuln_url,
                "template_source": _format_nuclei_source(doc.get("template_source")),
                "verify_command": cmd,
                "save_date": s_date,
                "tasks": [t_label] if t_label else [],
            }

    rows = [
        [
            r["template_id"], r["vuln_name"], r["vuln_severity"], r["target"],
            r["vuln_url"], r["template_source"], r["verify_command"],
            r["save_date"], ", ".join(r["tasks"]),
        ]
        for r in merged.values()
    ]
    return headers, widths, rows, truncated


def _collect_wih_rows(db_getter, task_ids, task_labels, deduplicate, max_rows):
    headers = ["记录类型", "内容", "来源JS", "所属站点", "发现时间", "来源任务"]
    widths = [18, 44, 44, 34, 20, 28]
    projection = {"record_type": 1, "content": 1, "source": 1, "site": 1, "save_date": 1, "task_id": 1}
    query = {"task_id": {"$in": task_ids}}

    if not deduplicate:
        rows = []
        truncated = False
        for doc in _iter_cursor_docs(db_getter("wih"), query, projection, limit=max_rows + 1):
            if len(rows) >= max_rows:
                truncated = True
                break
            rows.append([
                doc.get("record_type") or "",
                doc.get("content") or "",
                doc.get("source") or "",
                doc.get("site") or "",
                _format_datetime(doc.get("save_date")),
                task_labels.get(str(doc.get("task_id") or ""), ""),
            ])
        return headers, widths, rows, truncated

    merged = OrderedDict()
    truncated = False
    for doc in _iter_cursor_docs(db_getter("wih"), query, projection):
        rec_type = str(doc.get("record_type") or "").strip()
        content = str(doc.get("content") or "").strip()
        site = str(doc.get("site") or "").strip()
        source = str(doc.get("source") or "").strip()
        key = (rec_type, content, site)
        t_label = task_labels.get(str(doc.get("task_id") or ""), "")
        s_date = _format_datetime(doc.get("save_date"))

        if key in merged:
            rec = merged[key]
            _extend_unique(rec["sources"], [source])
            rec["save_date"] = _earlier_date(rec["save_date"], s_date)
            _extend_unique(rec["tasks"], [t_label])
        else:
            if len(merged) >= max_rows:
                truncated = True
                break
            merged[key] = {
                "record_type": rec_type,
                "content": content,
                "sources": [source] if source else [],
                "site": site,
                "save_date": s_date,
                "tasks": [t_label] if t_label else [],
            }

    rows = [
        [
            r["record_type"], r["content"], "\n".join(r["sources"]),
            r["site"], r["save_date"], ", ".join(r["tasks"]),
        ]
        for r in merged.values()
    ]
    return headers, widths, rows, truncated


def _collect_fileleak_rows(db_getter, task_ids, task_labels, deduplicate, max_rows):
    headers = ["URL", "标题", "状态码", "Body长度", "发现时间", "来源任务"]
    widths = [48, 32, 10, 12, 20, 28]
    projection = {"url": 1, "title": 1, "status_code": 1, "content_length": 1, "save_date": 1, "task_id": 1}
    query = {"task_id": {"$in": task_ids}}

    if not deduplicate:
        rows = []
        truncated = False
        for doc in _iter_cursor_docs(db_getter("fileleak"), query, projection, limit=max_rows + 1):
            if len(rows) >= max_rows:
                truncated = True
                break
            rows.append([
                doc.get("url") or "",
                doc.get("title") or "",
                doc.get("status_code"),
                doc.get("content_length"),
                _format_datetime(doc.get("save_date")),
                task_labels.get(str(doc.get("task_id") or ""), ""),
            ])
        return headers, widths, rows, truncated

    merged = OrderedDict()
    truncated = False
    for doc in _iter_cursor_docs(db_getter("fileleak"), query, projection):
        url_val = str(doc.get("url") or "").strip()
        key = url_val or str(doc.get("_id") or len(merged))
        t_label = task_labels.get(str(doc.get("task_id") or ""), "")
        s_date = _format_datetime(doc.get("save_date"))

        if key in merged:
            rec = merged[key]
            if not rec["title"] and doc.get("title"):
                rec["title"] = doc.get("title")
            if rec["status_code"] is None and doc.get("status_code") is not None:
                rec["status_code"] = doc.get("status_code")
            if rec["content_length"] is None and doc.get("content_length") is not None:
                rec["content_length"] = doc.get("content_length")
            rec["save_date"] = _earlier_date(rec["save_date"], s_date)
            _extend_unique(rec["tasks"], [t_label])
        else:
            if len(merged) >= max_rows:
                truncated = True
                break
            merged[key] = {
                "url": url_val,
                "title": doc.get("title") or "",
                "status_code": doc.get("status_code"),
                "content_length": doc.get("content_length"),
                "save_date": s_date,
                "tasks": [t_label] if t_label else [],
            }

    rows = [
        [r["url"], r["title"], r["status_code"], r["content_length"], r["save_date"], ", ".join(r["tasks"])]
        for r in merged.values()
    ]
    return headers, widths, rows, truncated


def _extract_cert_fields(doc: dict) -> dict:
    cert_obj = doc.get("cert") if isinstance(doc.get("cert"), dict) else {}
    ext = cert_obj.get("extensions") if isinstance(cert_obj.get("extensions"), dict) else {}
    validity = cert_obj.get("validity") if isinstance(cert_obj.get("validity"), dict) else {}
    fp = cert_obj.get("fingerprint") if isinstance(cert_obj.get("fingerprint"), dict) else {}
    san = ext.get("subjectAltName")
    if isinstance(san, list):
        san_text = ", ".join(str(x) for x in san if x)
    else:
        san_text = str(san or "")
    return {
        "ip": str(doc.get("ip") or "").strip(),
        "port": doc.get("port"),
        "subject": str(cert_obj.get("subject_dn") or cert_obj.get("subject") or ""),
        "issuer": str(cert_obj.get("issuer_dn") or cert_obj.get("issuer") or ""),
        "san": san_text,
        "start": str(validity.get("start") or ""),
        "end": str(validity.get("end") or ""),
        "sha1": str(fp.get("sha1") or ""),
        "save_date": _format_datetime(doc.get("save_date")),
    }


def _collect_cert_rows(db_getter, task_ids, task_labels, deduplicate, max_rows):
    headers = ["IP", "端口", "主题(Subject)", "签发者(Issuer)", "备用名称(SAN)", "生效时间", "过期时间", "SHA-1", "发现时间", "来源任务"]
    widths = [18, 10, 38, 38, 42, 22, 22, 44, 20, 28]
    projection = {"ip": 1, "port": 1, "cert": 1, "save_date": 1, "task_id": 1}
    query = {"task_id": {"$in": task_ids}}

    if not deduplicate:
        rows = []
        truncated = False
        for doc in _iter_cursor_docs(db_getter("cert"), query, projection, limit=max_rows + 1):
            if len(rows) >= max_rows:
                truncated = True
                break
            c = _extract_cert_fields(doc)
            rows.append([
                c["ip"], c["port"], c["subject"], c["issuer"], c["san"],
                c["start"], c["end"], c["sha1"], c["save_date"],
                task_labels.get(str(doc.get("task_id") or ""), ""),
            ])
        return headers, widths, rows, truncated

    merged = OrderedDict()
    truncated = False
    for doc in _iter_cursor_docs(db_getter("cert"), query, projection):
        c = _extract_cert_fields(doc)
        key = (c["ip"], c["port"], c["sha1"])
        t_label = task_labels.get(str(doc.get("task_id") or ""), "")
        if key in merged:
            rec = merged[key]
            for field_name in ("subject", "issuer", "san", "start", "end"):
                if not rec[field_name] and c[field_name]:
                    rec[field_name] = c[field_name]
            rec["save_date"] = _earlier_date(rec["save_date"], c["save_date"])
            _extend_unique(rec["tasks"], [t_label])
        else:
            if len(merged) >= max_rows:
                truncated = True
                break
            c["tasks"] = [t_label] if t_label else []
            merged[key] = c

    rows = [
        [
            r["ip"], r["port"], r["subject"], r["issuer"], r["san"],
            r["start"], r["end"], r["sha1"], r["save_date"], ", ".join(r["tasks"]),
        ]
        for r in merged.values()
    ]
    return headers, widths, rows, truncated


def _collect_url_rows(db_getter, task_ids, task_labels, deduplicate, max_rows):
    headers = ["URL", "标题", "状态码", "Body长度", "来源", "发现时间", "来源任务"]
    widths = [48, 32, 10, 12, 18, 20, 28]
    projection = {"url": 1, "title": 1, "status_code": 1, "content_length": 1, "source": 1, "save_date": 1, "task_id": 1}
    query = {"task_id": {"$in": task_ids}}

    if not deduplicate:
        rows = []
        truncated = False
        for doc in _iter_cursor_docs(db_getter("url"), query, projection, limit=max_rows + 1):
            if len(rows) >= max_rows:
                truncated = True
                break
            rows.append([
                doc.get("url") or "",
                doc.get("title") or "",
                doc.get("status_code"),
                doc.get("content_length"),
                doc.get("source") or "",
                _format_datetime(doc.get("save_date")),
                task_labels.get(str(doc.get("task_id") or ""), ""),
            ])
        return headers, widths, rows, truncated

    merged = OrderedDict()
    truncated = False
    for doc in _iter_cursor_docs(db_getter("url"), query, projection):
        url_val = str(doc.get("url") or "").strip()
        key = url_val or str(doc.get("_id") or len(merged))
        src = str(doc.get("source") or "").strip()
        t_label = task_labels.get(str(doc.get("task_id") or ""), "")
        s_date = _format_datetime(doc.get("save_date"))

        if key in merged:
            rec = merged[key]
            if not rec["title"] and doc.get("title"):
                rec["title"] = doc.get("title")
            if rec["status_code"] is None and doc.get("status_code") is not None:
                rec["status_code"] = doc.get("status_code")
            if rec["content_length"] is None and doc.get("content_length") is not None:
                rec["content_length"] = doc.get("content_length")
            _extend_unique(rec["sources"], [src])
            rec["save_date"] = _earlier_date(rec["save_date"], s_date)
            _extend_unique(rec["tasks"], [t_label])
        else:
            if len(merged) >= max_rows:
                truncated = True
                break
            merged[key] = {
                "url": url_val,
                "title": doc.get("title") or "",
                "status_code": doc.get("status_code"),
                "content_length": doc.get("content_length"),
                "sources": [src] if src else [],
                "save_date": s_date,
                "tasks": [t_label] if t_label else [],
            }

    rows = [
        [
            r["url"], r["title"], r["status_code"], r["content_length"],
            ", ".join(r["sources"]), r["save_date"], ", ".join(r["tasks"]),
        ]
        for r in merged.values()
    ]
    return headers, widths, rows, truncated


def _collect_cip_rows(db_getter, task_ids, task_labels, deduplicate, max_rows):
    headers = ["C段", "IP数量", "域名数量", "关联IP", "关联域名", "发现时间", "来源任务"]
    widths = [20, 12, 12, 40, 44, 20, 28]
    projection = {"cidr_ip": 1, "ip_list": 1, "domain_list": 1, "ip_count": 1, "domain_count": 1, "save_date": 1, "task_id": 1}
    query = {"task_id": {"$in": task_ids}}

    if not deduplicate:
        rows = []
        truncated = False
        for doc in _iter_cursor_docs(db_getter("cip"), query, projection, limit=max_rows + 1):
            if len(rows) >= max_rows:
                truncated = True
                break
            ips = _unique_ordered_list(doc.get("ip_list") or [])
            domains = _unique_ordered_list(doc.get("domain_list") or [])
            ip_cnt = doc.get("ip_count") if doc.get("ip_count") is not None else len(ips)
            dom_cnt = doc.get("domain_count") if doc.get("domain_count") is not None else len(domains)
            rows.append([
                doc.get("cidr_ip") or "",
                ip_cnt,
                dom_cnt,
                "\n".join(ips),
                "\n".join(domains),
                _format_datetime(doc.get("save_date")),
                task_labels.get(str(doc.get("task_id") or ""), ""),
            ])
        return headers, widths, rows, truncated

    merged = OrderedDict()
    truncated = False
    for doc in _iter_cursor_docs(db_getter("cip"), query, projection):
        cidr = str(doc.get("cidr_ip") or "").strip()
        key = cidr or str(doc.get("_id") or len(merged))
        ips = _unique_ordered_list(doc.get("ip_list") or [])
        domains = _unique_ordered_list(doc.get("domain_list") or [])
        t_label = task_labels.get(str(doc.get("task_id") or ""), "")
        s_date = _format_datetime(doc.get("save_date"))

        if key in merged:
            rec = merged[key]
            _extend_unique(rec["ips"], ips)
            _extend_unique(rec["domains"], domains)
            rec["save_date"] = _earlier_date(rec["save_date"], s_date)
            _extend_unique(rec["tasks"], [t_label])
        else:
            if len(merged) >= max_rows:
                truncated = True
                break
            merged[key] = {
                "cidr_ip": cidr,
                "ips": ips,
                "domains": domains,
                "save_date": s_date,
                "tasks": [t_label] if t_label else [],
            }

    rows = [
        [
            r["cidr_ip"], len(r["ips"]), len(r["domains"]),
            "\n".join(r["ips"]), "\n".join(r["domains"]),
            r["save_date"], ", ".join(r["tasks"]),
        ]
        for r in merged.values()
    ]
    return headers, widths, rows, truncated


ASSET_COLLECTORS = {
    "site": _collect_site_rows,
    "domain": _collect_domain_rows,
    "ip": _collect_ip_rows,
    "service": _collect_service_rows,
    "vuln": _collect_vuln_rows,
    "nuclei_result": _collect_nuclei_rows,
    "wih": _collect_wih_rows,
    "fileleak": _collect_fileleak_rows,
    "cert": _collect_cert_rows,
    "url": _collect_url_rows,
    "cip": _collect_cip_rows,
}


def _compute_asset_statistics(db_getter, task_ids, deduplicate):
    """按与导出一致的去重口径统计 Top 20 端口、系统服务与软件产品。"""
    port_counter = Counter()
    service_counter = Counter()
    product_counter = Counter()

    seen_ip_ports = set()
    ip_projection = {"ip": 1, "port_info": 1, "task_id": 1}
    for doc in _iter_cursor_docs(db_getter("ip"), {"task_id": {"$in": task_ids}}, ip_projection):
        ip_str = str(doc.get("ip") or "").strip()
        for p in (doc.get("port_info") or []):
            if not isinstance(p, dict) or p.get("port_id") is None:
                continue
            port_id = str(p.get("port_id"))
            if deduplicate:
                pair = (ip_str, port_id)
                if pair in seen_ip_ports:
                    continue
                seen_ip_ports.add(pair)
            port_counter[port_id] += 1

    seen_svc_keys = set()
    for ep in _iter_service_endpoints(db_getter, task_ids):
        ip_str = str(ep.get("ip") or "").strip()
        port_id = ep.get("port_id")
        svc_name = str(ep.get("service_name") or "").strip()
        if svc_name == "https-alt":
            svc_name = "https"
        product = str(ep.get("product") or "").strip()

        if deduplicate:
            if port_id is not None:
                pair = (ip_str, str(port_id))
                if pair not in seen_ip_ports:
                    seen_ip_ports.add(pair)
                    port_counter[str(port_id)] += 1
            s_key = (ip_str, port_id, svc_name.lower())
            if s_key in seen_svc_keys:
                continue
            seen_svc_keys.add(s_key)

        if svc_name and svc_name.lower() != "unknown":
            service_counter[svc_name] += 1
        if product and "**" not in product:
            product_counter[product] += 1

    port_total = sum(port_counter.values())
    service_total = sum(service_counter.values())
    product_total = sum(product_counter.values())

    def _top_rows(counter, total):
        if total <= 0:
            return []
        return [
            (name, cnt, f"{(cnt * 100.0) / total:.2f}%")
            for name, cnt in counter.most_common(20)
        ]

    return {
        "port_total": port_total,
        "port_top": _top_rows(port_counter, port_total),
        "service_total": service_total,
        "service_top": _top_rows(service_counter, service_total),
        "product_total": product_total,
        "product_top": _top_rows(product_counter, product_total),
    }


def _write_statist_sheet(wb, stats, deduplicate):
    if stats["port_total"] == 0 and stats["service_total"] == 0 and stats["product_total"] == 0:
        return 0

    ws = wb.create_sheet(title=SHEET_TITLES["statist"])
    _set_col_widths(ws, [28, 16, 14, 42])

    scope_note = (
        "跨任务去重统计（按唯一 IP:端口 / 服务端点归并）"
        if deduplicate
        else "跨任务累计统计（未去重，按所选任务原始记录汇总）"
    )
    _append_styled_row(ws, ["统计口径", scope_note], font=SECTION_FONT)
    _append_data_row(ws, [])

    row_count = 0
    sections = [
        ("端口开放 Top 20", "端口", stats["port_top"], "端口开放总数", stats["port_total"]),
        ("系统服务 Top 20", "系统服务", stats["service_top"], "系统服务总数", stats["service_total"]),
        ("软件产品 Top 20", "软件产品", stats["product_top"], "软件产品总数", stats["product_total"]),
    ]

    for title, item_col, top_items, total_label, total_val in sections:
        _append_styled_row(ws, [title, f"{total_label}: {total_val}"], font=SECTION_FONT)
        _append_styled_row(ws, [item_col, "数量", "占比"], font=HEADER_FONT, fill=HEADER_FILL)
        if top_items:
            for name, cnt, pct in top_items:
                _append_data_row(ws, [name, cnt, pct])
                row_count += 1
        else:
            _append_data_row(ws, ["无数据", 0, "0.00%"])
        _append_data_row(ws, [])

    return row_count


def _write_overview_sheet(
    wb,
    tasks,
    task_stats_map,
    selected_sheets,
    included_sheets,
    empty_sheets,
    truncated_sheets,
    sheet_row_counts,
    deduplicate,
    has_active_tasks,
    export_time_str,
    max_rows,
):
    ws = wb.create_sheet(title=SHEET_TITLES["overview"], index=0)
    _set_col_widths(ws, [26, 26, 30, 18, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 10, 20, 20])

    dedup_note = "跨任务去重合并（各资产表「来源任务」列汇总命中任务）" if deduplicate else "未去重明细（按所选任务完整保留原始记录）"
    trunc_note = (
        f"以下工作表达到单表 {max_rows} 行上限并已截断：" + "、".join(SHEET_TITLES[k] for k in truncated_sheets)
        if truncated_sheets
        else "无截断"
    )
    snapshot_note = (
        "包含进行中或排队中任务，导出内容为导出时刻已入库数据快照"
        if has_active_tasks
        else "全部所选任务均已结束"
    )

    _append_styled_row(ws, ["导出摘要", "说明"], font=HEADER_FONT, fill=HEADER_FILL)
    _append_data_row(ws, ["导出时间", export_time_str])
    _append_data_row(ws, ["所选任务数", len(tasks)])
    _append_data_row(ws, ["数据口径", dedup_note])
    _append_data_row(ws, ["任务状态说明", snapshot_note])
    _append_data_row(ws, ["单工作表上限", f"{max_rows} 行（{trunc_note}）"])
    _append_data_row(ws, [])

    # 维度导出状态明细
    _append_styled_row(ws, ["工作表维度汇总"], font=SECTION_FONT)
    _append_styled_row(ws, ["工作表名称", "维度标识", "导出条数", "导出状态"], font=HEADER_FONT, fill=HEADER_FILL)
    for key in selected_sheets:
        if key == "overview":
            _append_data_row(ws, [SHEET_TITLES[key], key, len(tasks), "已导出"])
            continue
        cnt = sheet_row_counts.get(key, 0)
        if key in truncated_sheets:
            status_desc = f"已导出（已达 {max_rows} 行上限截断）"
        elif key in included_sheets:
            status_desc = "已导出"
        else:
            status_desc = "无数据（已自动跳过）"
        _append_data_row(ws, [SHEET_TITLES[key], key, cnt, status_desc])
    _append_data_row(ws, [])

    # 所选任务逐条明细（各维计数口径与页面任务列表一致）
    _append_styled_row(ws, ["所选任务清单（各任务资产计数为单任务原始统计，未跨任务去重）"], font=SECTION_FONT)
    task_headers = [
        "任务名", "任务ID", "目标", "状态",
        "站点", "域名", "IP", "系统服务", "WIH", "风险漏洞", "Nuclei漏洞",
        "文件泄露", "URL", "SSL证书", "C段",
        "开始时间", "结束时间",
    ]
    _append_styled_row(ws, task_headers, font=HEADER_FONT, fill=HEADER_FILL)

    for task in tasks:
        tid = str(task["_id"])
        st = task_stats_map.get(tid, {})
        _append_data_row(ws, [
            task.get("name") or "",
            tid,
            task.get("target") or "",
            format_task_status_label(task.get("status")),
            st.get("site_cnt", 0),
            st.get("domain_cnt", 0),
            st.get("ip_cnt", 0),
            st.get("service_cnt", 0),
            st.get("wih_cnt", 0),
            st.get("vuln_cnt", 0),
            st.get("nuclei_result_cnt", 0),
            st.get("fileleak_cnt", 0),
            st.get("url_cnt", 0),
            st.get("cert_cnt", 0),
            st.get("cip_cnt", 0),
            _format_datetime(task.get("start_time")),
            _format_datetime(task.get("end_time")),
        ])


def build_tasks_excel_report(
    task_id_list,
    sheets=None,
    deduplicate=True,
    db_getter=None,
    max_tasks=MAX_EXPORT_TASKS,
    max_rows_per_sheet=MAX_ROWS_PER_SHEET,
) -> TaskExcelExportResult:
    """构建单任务或多任务合并 Excel 报告（write_only 流式写入）。"""
    conn_fn = db_getter or utils.conn_db
    task_ids, selected_sheets, dedup = validate_export_params(
        task_id_list,
        sheets=sheets,
        deduplicate=deduplicate,
        max_tasks=max_tasks,
    )

    object_ids = [ObjectId(tid) for tid in task_ids]
    found_docs = list(conn_fn("task").find({"_id": {"$in": object_ids}}))
    doc_by_id = {str(doc["_id"]): doc for doc in found_docs}
    tasks = [doc_by_id[tid] for tid in task_ids if tid in doc_by_id]

    if not tasks:
        raise TaskExcelExportError("未找到可导出的任务", status_code=404)

    resolved_task_ids = [str(t["_id"]) for t in tasks]
    task_labels = _build_task_labels(tasks)
    has_active_tasks = any(is_active_task_status(t.get("status")) for t in tasks)
    now = datetime.now()
    export_time_str = now.strftime("%Y-%m-%d %H:%M:%S")
    timestamp_tag = now.strftime("%Y%m%d_%H%M%S")

    wb = Workbook(write_only=True)
    included_sheets = []
    empty_sheets = []
    truncated_sheets = []
    sheet_row_counts = {}

    for key in selected_sheets:
        if key == "overview":
            continue
        if key == "statist":
            stats = _compute_asset_statistics(conn_fn, resolved_task_ids, dedup)
            written = _write_statist_sheet(wb, stats, dedup)
            sheet_row_counts[key] = written
            if written > 0:
                included_sheets.append(key)
            else:
                empty_sheets.append(key)
            continue

        collector = ASSET_COLLECTORS[key]
        headers, widths, rows, truncated = collector(
            conn_fn,
            resolved_task_ids,
            task_labels,
            dedup,
            max_rows_per_sheet,
        )
        sheet_row_counts[key] = len(rows)
        if not rows:
            empty_sheets.append(key)
            continue

        ws = wb.create_sheet(title=SHEET_TITLES[key])
        _set_col_widths(ws, widths)
        _append_styled_row(ws, headers, font=HEADER_FONT, fill=HEADER_FILL)
        for row in rows:
            _append_data_row(ws, row)
        included_sheets.append(key)
        if truncated:
            truncated_sheets.append(key)

    # 若用户勾选了「任务概览」，或所有选中的资产表均为空（兜底保证工作簿合法有效），则在首位写入「任务概览」
    need_overview = ("overview" in selected_sheets) or (len(included_sheets) == 0)
    if need_overview:
        task_stats_map = {str(t["_id"]): _resolve_task_statistic(t, conn_fn) for t in tasks}
        _write_overview_sheet(
            wb=wb,
            tasks=tasks,
            task_stats_map=task_stats_map,
            selected_sheets=selected_sheets,
            included_sheets=included_sheets,
            empty_sheets=empty_sheets,
            truncated_sheets=truncated_sheets,
            sheet_row_counts=sheet_row_counts,
            deduplicate=dedup,
            has_active_tasks=has_active_tasks,
            export_time_str=export_time_str,
            max_rows=max_rows_per_sheet,
        )
        included_sheets.insert(0, "overview")
        sheet_row_counts["overview"] = len(tasks)

    output = BytesIO()
    wb.save(output)
    content = output.getvalue()

    if len(tasks) == 1:
        name_part = _safe_filename_part(tasks[0].get("name") or tasks[0].get("target") or resolved_task_ids[0])
        filename = f"ARL_资产报告_{name_part or resolved_task_ids[0]}_{timestamp_tag}.xlsx"
    else:
        filename = f"ARL_批量资产报告_{len(tasks)}个任务_{timestamp_tag}.xlsx"

    return TaskExcelExportResult(
        content=content,
        filename=filename,
        task_count=len(tasks),
        deduplicate=dedup,
        has_active_tasks=has_active_tasks,
        included_sheets=included_sheets,
        empty_sheets=empty_sheets,
        truncated_sheets=truncated_sheets,
        sheet_row_counts=sheet_row_counts,
    )
