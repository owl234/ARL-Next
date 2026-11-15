# -*- coding: utf-8 -*-
"""
统一系统代理节点池、三域分流策略、旁路白名单与运行时态服务。

单一事实源 (MongoDB `system_config`):
  - `_id: "proxy_config"`: 权威配置文档（nodes / policies / bypass / schema_version）
  - `_id: "proxy_runtime_status"`: OSINT 出口切换与 300s WAF 冷却运行时状态
  - `_id: "general_config"`: 仅保留 `proxy_url` 向下兼容镜像（不作为主配置源）
"""

from __future__ import annotations

import ipaddress
import itertools
import logging
import os
import re
import threading
import time
import uuid
from copy import deepcopy
from urllib.parse import quote, unquote, urlsplit

import requests

logger = logging.getLogger("arlv2.proxy")

PROXY_CONFIG_DOC_ID = "proxy_config"
PROXY_RUNTIME_DOC_ID = "proxy_runtime_status"
PROXY_SCHEMA_VERSION = 1

SUPPORTED_PROTOCOLS = ("http", "https", "socks5", "socks5h")
SUPPORTED_MODES = ("direct_only", "failover", "round_robin", "fixed_proxy")
TRAFFIC_DOMAINS = ("osint", "scan", "intel")

DOMESTIC_WEBHOOK_HOSTS = frozenset({
    "oapi.dingtalk.com",
    "open.feishu.cn",
    "open.larksuite.com",
    "qyapi.weixin.qq.com",
})

INTERNAL_SERVICE_HOSTS = frozenset({
    "localhost",
    "127.0.0.1",
    "::1",
    "osint-service",
    "arl-osint-service-prod",
    "arl-puppeteer",
    "arl-puppeteer-prod",
    "mongodb",
    "arl-mongodb-prod",
    "rabbitmq",
    "arl-rabbitmq-prod",
    "arl-web",
    "arl-web-prod",
    "arl-worker",
    "arl-worker-prod",
    "arl-mcp",
    "arl-mcp-prod",
    "arl-frontend",
    "arl-frontend-prod",
    "web",
    "worker",
    "worker-light",
    "worker-github",
    "nginx",
    "host.docker.internal",
})

INTEL_HINT_HOSTS = frozenset({
    "api.github.com",
    "github.com",
    "raw.githubusercontent.com",
    "codeload.github.com",
    "objects.githubusercontent.com",
    "api.telegram.org",
    "fofa.info",
    "api.fofa.info",
    "hunter.qianxin.com",
    "api.hunter.how",
    "quake.360.net",
    "api.zoomeye.org",
    "api.securitytrails.com",
    "www.virustotal.com",
    "crt.sh",
    "otx.alienvault.com",
    "web.archive.org",
    "jldc.me",
    "dns.projectdiscovery.io",
    "api.certspotter.com",
    "api.hackertarget.com",
    "rapiddns.io",
    "ghfast.top",
    "ghproxy.net",
})

OSINT_HINT_HOSTS = frozenset({
    "beian.miit.gov.cn",
    "hlwicpfwc.miit.gov.cn",
    "capi.tianyancha.com",
    "www.tianyancha.com",
})

PROBE_PRESETS = {
    "egress_ip": {
        "label": "常规出口连通性与公网 IP 探测",
        "urls": [
            "https://myip.ipip.net",
            "https://api.ipify.org?format=json",
            "https://ifconfig.me/ip",
        ],
    },
    "miit": {
        "label": "工信部 ICP 备案接口连通性探测",
        "urls": ["https://beian.miit.gov.cn/"],
    },
    "tianyancha": {
        "label": "天眼查接口连通性与地域围栏探测",
        "urls": ["https://capi.tianyancha.com/"],
    },
    "github": {
        "label": "GitHub API 连通性探测",
        "urls": ["https://api.github.com/zen"],
    },
}

_LOCAL_CACHE_LOCK = threading.Lock()
_LOCAL_CACHE = {
    "doc": None,
    "loaded_at": 0.0,
    "version": None,
    "has_db_doc": False,
}
_LOCAL_CACHE_TTL = 15.0

_RR_LOCK = threading.Lock()
_RR_COUNTERS = {
    "osint": itertools.count(),
    "scan": itertools.count(),
    "intel": itertools.count(),
}


def default_proxy_config():
    """返回标准初始系统代理配置结构。"""
    return {
        "_id": PROXY_CONFIG_DOC_ID,
        "schema_version": PROXY_SCHEMA_VERSION,
        "nodes": [],
        "policies": {
            "osint": {
                "mode": "direct_only",
                "node_ids": [],
                "cooldown_sec": 300,
                "include_direct": False,
            },
            "scan": {
                "mode": "direct_only",
                "node_ids": [],
                "apply_to_nuclei": True,
                "apply_to_npoc": True,
                "apply_to_puppeteer": False,
                "include_direct": False,
            },
            "intel": {
                "mode": "direct_only",
                "node_ids": [],
                "include_direct": False,
            },
        },
        "bypass": {
            "bypass_private_cidr": True,
            "bypass_domestic_webhooks": True,
            "custom_no_proxy": [],
        },
        "updated_at": 0,
    }


def parse_proxy_url_string(raw_url, default_name="legacy-default", default_id="legacy-default"):
    """将传统单串 PROXY_URL 解析为结构化节点对象；无效串返回 None。"""
    text = str(raw_url or "").strip()
    if not text:
        return None
    if "://" not in text:
        text = f"http://{text}"
    parsed = urlsplit(text)
    scheme = (parsed.scheme or "http").lower()
    if scheme not in SUPPORTED_PROTOCOLS:
        scheme = "http"
    host = (parsed.hostname or "").strip()
    try:
        port = parsed.port
    except ValueError:
        port = None
    if not host or not port or not (1 <= int(port) <= 65535):
        return None
    username = unquote(parsed.username) if parsed.username else ""
    password = unquote(parsed.password) if parsed.password else ""
    now_ts = int(time.time())
    return {
        "id": default_id,
        "name": default_name,
        "protocol": scheme,
        "host": host,
        "port": int(port),
        "username": username,
        "password": password,
        "region_hint": "legacy",
        "remark": "由旧版 PROXY_URL 自动迁移",
        "enabled": True,
        "created_at": now_ts,
        "updated_at": now_ts,
        "last_probe": None,
    }


def _clean_host(raw_host):
    host = str(raw_host or "").strip()
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1].strip()
    if not host or any(ch in host for ch in (" ", "\t", "\r", "\n", "/", "\\", "@", "?")):
        raise ValueError("代理主机地址格式无效")
    return host


def validate_node_payload(payload, existing_node=None):
    """校验并规范化单个代理节点载荷。"""
    if not isinstance(payload, dict):
        raise ValueError("节点配置格式错误")

    name = str(payload.get("name") if "name" in payload else (existing_node or {}).get("name") or "").strip()
    if not name or len(name) > 64:
        raise ValueError("节点名称不能为空且长度不能超过 64 个字符")

    protocol = str(payload.get("protocol") if "protocol" in payload else (existing_node or {}).get("protocol") or "socks5").strip().lower()
    if protocol not in SUPPORTED_PROTOCOLS:
        raise ValueError(f"不支持的代理协议: {protocol}")

    host = _clean_host(payload.get("host") if "host" in payload else (existing_node or {}).get("host"))

    raw_port = payload.get("port") if "port" in payload else (existing_node or {}).get("port")
    try:
        port = int(raw_port)
    except (TypeError, ValueError):
        raise ValueError("代理端口必须为 1-65535 的整数")
    if not (1 <= port <= 65535):
        raise ValueError("代理端口必须在 1-65535 之间")

    username = str(payload.get("username") if "username" in payload else (existing_node or {}).get("username") or "").strip()
    clear_password = bool(payload.get("clear_password", False))
    if clear_password:
        password = ""
    elif "password" in payload and payload.get("password") not in (None, ""):
        password = str(payload.get("password"))
    else:
        password = str((existing_node or {}).get("password") or "")

    region_hint = str(payload.get("region_hint") if "region_hint" in payload else (existing_node or {}).get("region_hint") or "").strip()[:32]
    remark = str(payload.get("remark") if "remark" in payload else (existing_node or {}).get("remark") or "").strip()[:200]
    enabled = bool(payload.get("enabled")) if "enabled" in payload else bool((existing_node or {}).get("enabled", True))

    now_ts = int(time.time())
    node_id = str((existing_node or {}).get("id") or payload.get("id") or f"node_{uuid.uuid4().hex[:8]}").strip()
    if not re.match(r"^[a-zA-Z0-9_-]{2,48}$", node_id):
        node_id = f"node_{uuid.uuid4().hex[:8]}"

    return {
        "id": node_id,
        "name": name,
        "protocol": protocol,
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "region_hint": region_hint,
        "remark": remark,
        "enabled": enabled,
        "created_at": int((existing_node or {}).get("created_at") or now_ts),
        "updated_at": now_ts,
        "last_probe": (existing_node or {}).get("last_probe"),
    }


def _normalize_no_proxy_entries(raw_entries):
    if raw_entries is None:
        return []
    if isinstance(raw_entries, str):
        items = re.split(r"[\s,;]+", raw_entries)
    elif isinstance(raw_entries, list):
        items = raw_entries
    else:
        raise ValueError("custom_no_proxy 必须为数组或分隔字符串")
    cleaned = []
    seen = set()
    for item in items:
        s = str(item or "").strip().lower()
        if not s or len(s) > 255:
            continue
        if s not in seen:
            seen.add(s)
            cleaned.append(s)
    return cleaned


def normalize_proxy_config(raw_doc):
    """将数据库/用户输入收敛为完整规范化配置。"""
    base = default_proxy_config()
    if not isinstance(raw_doc, dict):
        return base

    nodes = []
    node_ids_seen = set()
    for n in raw_doc.get("nodes") or []:
        if not isinstance(n, dict):
            continue
        try:
            norm_n = validate_node_payload(n, existing_node=n)
        except ValueError:
            continue
        if norm_n["id"] in node_ids_seen:
            continue
        node_ids_seen.add(norm_n["id"])
        nodes.append(norm_n)
    base["nodes"] = nodes

    raw_policies = raw_doc.get("policies") if isinstance(raw_doc.get("policies"), dict) else {}
    for dom in TRAFFIC_DOMAINS:
        src = raw_policies.get(dom) if isinstance(raw_policies.get(dom), dict) else {}
        dst = base["policies"][dom]
        mode = str(src.get("mode") or dst["mode"]).strip()
        if mode in SUPPORTED_MODES:
            dst["mode"] = mode
        raw_nids = src.get("node_ids") if isinstance(src.get("node_ids"), list) else []
        dst["node_ids"] = [str(nid) for nid in raw_nids if str(nid) in node_ids_seen]
        if "include_direct" in src:
            dst["include_direct"] = bool(src["include_direct"])
        if dom == "osint":
            try:
                cd = int(src.get("cooldown_sec", 300) or 300)
            except (TypeError, ValueError):
                cd = 300
            dst["cooldown_sec"] = max(30, min(3600, cd))
        elif dom == "scan":
            if "apply_to_nuclei" in src:
                dst["apply_to_nuclei"] = bool(src["apply_to_nuclei"])
            if "apply_to_npoc" in src:
                dst["apply_to_npoc"] = bool(src["apply_to_npoc"])
            if "apply_to_puppeteer" in src:
                dst["apply_to_puppeteer"] = bool(src["apply_to_puppeteer"])

    raw_bypass = raw_doc.get("bypass") if isinstance(raw_doc.get("bypass"), dict) else {}
    if "bypass_private_cidr" in raw_bypass:
        base["bypass"]["bypass_private_cidr"] = bool(raw_bypass["bypass_private_cidr"])
    if "bypass_domestic_webhooks" in raw_bypass:
        base["bypass"]["bypass_domestic_webhooks"] = bool(raw_bypass["bypass_domestic_webhooks"])
    if "custom_no_proxy" in raw_bypass:
        try:
            base["bypass"]["custom_no_proxy"] = _normalize_no_proxy_entries(raw_bypass["custom_no_proxy"])
        except ValueError:
            pass
    base["updated_at"] = int(raw_doc.get("updated_at") or 0)
    return base


def validate_policies_and_bypass_update(current_cfg, payload):
    """校验前端提交的 policies / bypass 增量更新并合入配置。"""
    if not isinstance(payload, dict):
        raise ValueError("策略载荷格式错误")
    merged = deepcopy(normalize_proxy_config(current_cfg))
    valid_ids = {n["id"] for n in merged["nodes"]}

    if "policies" in payload:
        p_in = payload["policies"]
        if not isinstance(p_in, dict):
            raise ValueError("policies 必须为对象")
        for dom, dom_in in p_in.items():
            if dom not in TRAFFIC_DOMAINS:
                continue
            if not isinstance(dom_in, dict):
                raise ValueError(f"{dom} 策略格式错误")
            target = merged["policies"][dom]
            if "mode" in dom_in:
                mode = str(dom_in["mode"] or "").strip()
                if mode not in SUPPORTED_MODES:
                    raise ValueError(f"不支持的分流模式: {mode}")
                target["mode"] = mode
            if "node_ids" in dom_in:
                nids = dom_in["node_ids"]
                if not isinstance(nids, list):
                    raise ValueError(f"{dom}.node_ids 必须为数组")
                dedup = []
                for nid in nids:
                    nid_s = str(nid or "").strip()
                    if nid_s and nid_s in valid_ids and nid_s not in dedup:
                        dedup.append(nid_s)
                target["node_ids"] = dedup
            if target["mode"] in ("fixed_proxy", "round_robin") and not target["node_ids"]:
                if not (target["mode"] == "round_robin" and bool(dom_in.get("include_direct", target.get("include_direct")))):
                    raise ValueError(f"{dom} 域处于 {target['mode']} 模式时至少需要绑定 1 个代理节点")
            if target["mode"] == "failover" and not target["node_ids"]:
                raise ValueError(f"{dom} 域处于故障切备模式时至少需要绑定 1 个备用节点")
            if "include_direct" in dom_in:
                target["include_direct"] = bool(dom_in["include_direct"])
            if dom == "osint" and "cooldown_sec" in dom_in:
                try:
                    cd = int(dom_in["cooldown_sec"])
                except (TypeError, ValueError):
                    raise ValueError("cooldown_sec 必须为整数")
                if not (30 <= cd <= 3600):
                    raise ValueError("冷却时间必须在 30 到 3600 秒之间")
                target["cooldown_sec"] = cd
            if dom == "scan":
                for flag in ("apply_to_nuclei", "apply_to_npoc", "apply_to_puppeteer"):
                    if flag in dom_in:
                        target[flag] = bool(dom_in[flag])

    if "bypass" in payload:
        b_in = payload["bypass"]
        if not isinstance(b_in, dict):
            raise ValueError("bypass 必须为对象")
        if "bypass_private_cidr" in b_in:
            merged["bypass"]["bypass_private_cidr"] = bool(b_in["bypass_private_cidr"])
        if "bypass_domestic_webhooks" in b_in:
            merged["bypass"]["bypass_domestic_webhooks"] = bool(b_in["bypass_domestic_webhooks"])
        if "custom_no_proxy" in b_in:
            merged["bypass"]["custom_no_proxy"] = _normalize_no_proxy_entries(b_in["custom_no_proxy"])

    merged["updated_at"] = int(time.time())
    return merged


def build_node_proxy_url(node):
    """构造可供 requests / urllib3 / nuclei 使用的标准代理 URL。"""
    if not isinstance(node, dict):
        return ""
    proto = (node.get("protocol") or "http").lower()
    host = (node.get("host") or "").strip()
    port = node.get("port")
    if not host or not port:
        return ""
    host_fmt = f"[{host}]" if ":" in host and not host.startswith("[") else host
    user = node.get("username") or ""
    pwd = node.get("password") or ""
    if user:
        user_enc = quote(str(user), safe="")
        pwd_enc = quote(str(pwd), safe="") if pwd else ""
        auth = f"{user_enc}:{pwd_enc}@" if pwd else f"{user_enc}@"
    else:
        auth = ""
    return f"{proto}://{auth}{host_fmt}:{int(port)}"


def format_node_display_url(node):
    """构造脱敏展示串，不包含真实密码。"""
    if not isinstance(node, dict):
        return ""
    proto = (node.get("protocol") or "http").lower()
    host = (node.get("host") or "").strip()
    port = node.get("port")
    host_fmt = f"[{host}]" if ":" in host and not host.startswith("[") else host
    user = node.get("username") or ""
    has_pwd = bool(node.get("password"))
    if user and has_pwd:
        return f"{proto}://{user}:***@{host_fmt}:{int(port)}"
    if user:
        return f"{proto}://{user}@{host_fmt}:{int(port)}"
    return f"{proto}://{host_fmt}:{int(port)}"


def mask_proxy_url_secret(proxy_url):
    """隐藏 URL 中的账号密码用于日志安全记录。"""
    text = str(proxy_url or "").strip()
    if not text or "@" not in text:
        return text
    try:
        p = urlsplit(text)
        if not p.hostname:
            return text
        host_fmt = f"[{p.hostname}]" if ":" in p.hostname else p.hostname
        port_part = f":{p.port}" if p.port else ""
        return f"{p.scheme}://***@{host_fmt}{port_part}"
    except Exception:
        return "***"


def mask_proxy_config_for_api(cfg):
    """返回脱敏后的完整配置（password 置空，补 has_password 与 display_url）。"""
    norm = normalize_proxy_config(cfg)
    masked = deepcopy(norm)
    for node in masked["nodes"]:
        raw_pwd = node.get("password") or ""
        node["has_password"] = bool(raw_pwd)
        node["display_url"] = format_node_display_url(node)
        node["password"] = ""
    return masked


def _get_conn_db():
    from app.utils.conn import conn_db
    return conn_db


def _read_config_version_safe():
    try:
        from app.config import _read_config_version
        return _read_config_version()
    except Exception:
        return None


def clear_proxy_local_cache():
    with _LOCAL_CACHE_LOCK:
        _LOCAL_CACHE["doc"] = None
        _LOCAL_CACHE["loaded_at"] = 0.0
        _LOCAL_CACHE["version"] = None
        _LOCAL_CACHE["has_db_doc"] = False


def _load_proxy_config_with_meta(use_cache=True):
    """读取系统代理配置（带跨进程版本号校验微缓存），同时返回数据库是否存在独立文档。"""
    now = time.monotonic()
    if use_cache:
        with _LOCAL_CACHE_LOCK:
            cached_doc = _LOCAL_CACHE["doc"]
            cached_has_db_doc = bool(_LOCAL_CACHE.get("has_db_doc"))
            fresh = cached_doc is not None and (now - _LOCAL_CACHE["loaded_at"] < _LOCAL_CACHE_TTL)
            if fresh and cached_has_db_doc:
                seen = _LOCAL_CACHE.get("version")
                cur_ver = _read_config_version_safe()
                if cur_ver is not None and seen != cur_ver:
                    fresh = False
            if fresh:
                return deepcopy(cached_doc), cached_has_db_doc

    doc = None
    db_failed = False
    try:
        doc = _get_conn_db()("system_config").find_one({"_id": PROXY_CONFIG_DOC_ID})
    except Exception as e:
        db_failed = True
        logger.debug(f"load_proxy_config db skipped: {e}")

    if not doc:
        # 兼容未执行 arlupdate 或单测中仅设置 Config.PROXY_URL 的场景；
        # 若 DB 不可达，短缓存空默认结构避免重复阻塞。
        if db_failed:
            cfg = default_proxy_config()
            mem_proxy = _explicit_in_memory_proxy_override()
            node = parse_proxy_url_string(mem_proxy) if mem_proxy else None
            if node:
                cfg["nodes"] = [node]
                for dom in TRAFFIC_DOMAINS:
                    cfg["policies"][dom]["mode"] = "fixed_proxy"
                    cfg["policies"][dom]["node_ids"] = [node["id"]]
            if use_cache:
                with _LOCAL_CACHE_LOCK:
                    _LOCAL_CACHE["doc"] = deepcopy(cfg)
                    _LOCAL_CACHE["loaded_at"] = now
                    _LOCAL_CACHE["version"] = None
                    _LOCAL_CACHE["has_db_doc"] = False
            return cfg, False
        return _fallback_config_from_legacy(), False

    norm = normalize_proxy_config(doc)
    if use_cache:
        with _LOCAL_CACHE_LOCK:
            _LOCAL_CACHE["doc"] = deepcopy(norm)
            _LOCAL_CACHE["loaded_at"] = now
            _LOCAL_CACHE["version"] = _read_config_version_safe()
            _LOCAL_CACHE["has_db_doc"] = True
    return norm, True


def load_proxy_config(use_cache=True):
    """读取系统代理配置（带跨进程版本号校验微缓存）。"""
    cfg, _ = _load_proxy_config_with_meta(use_cache=use_cache)
    return cfg


def _fallback_config_from_legacy():
    """在数据库尚无 proxy_config 文档时，平滑兼容 general_config.proxy_url 或 Config.PROXY_URL。"""
    cfg = default_proxy_config()
    legacy_raw = ""
    try:
        gen = _get_conn_db()("system_config").find_one({"_id": "general_config"}, {"proxy_url": 1})
        if gen and gen.get("proxy_url"):
            legacy_raw = str(gen.get("proxy_url") or "").strip()
    except Exception:
        pass
    if not legacy_raw:
        try:
            from app.config import Config
            legacy_raw = str(getattr(Config, "_PROXY_URL", "") or getattr(Config, "PROXY_URL", "") or "").strip()
        except Exception:
            legacy_raw = ""
    if legacy_raw:
        node = parse_proxy_url_string(legacy_raw)
        if node:
            cfg["nodes"] = [node]
            for dom in TRAFFIC_DOMAINS:
                cfg["policies"][dom]["mode"] = "fixed_proxy"
                cfg["policies"][dom]["node_ids"] = [node["id"]]
    return cfg


def _compute_legacy_proxy_summary(cfg):
    """计算供 legacy Config.PROXY_URL 兼容字段同步的摘要代理串。"""
    nodes_by_id = {n["id"]: n for n in cfg.get("nodes", []) if n.get("enabled", True)}
    for dom in ("scan", "osint", "intel"):
        pol = (cfg.get("policies") or {}).get(dom) or {}
        mode = pol.get("mode", "direct_only")
        if mode == "direct_only":
            continue
        for nid in pol.get("node_ids") or []:
            node = nodes_by_id.get(nid)
            if node:
                return build_node_proxy_url(node)
    return ""


def save_proxy_config(cfg):
    """持久化 proxy_config 并同步兼容字段及跨进程缓存版本号。"""
    norm = normalize_proxy_config(cfg)
    norm["updated_at"] = int(time.time())
    col = _get_conn_db()("system_config")
    col.update_one(
        {"_id": PROXY_CONFIG_DOC_ID},
        {"$set": {k: v for k, v in norm.items() if k != "_id"}},
        upsert=True,
    )
    # 同步写入 general_config.proxy_url 兼容镜像（不覆盖其它字段）
    col.update_one(
        {"_id": "general_config"},
        {"$set": {"proxy_url": _compute_legacy_proxy_summary(norm)}},
        upsert=True,
    )
    clear_proxy_local_cache()
    try:
        from app.config import bump_system_config_version, clear_system_config_cache
        clear_system_config_cache()
        bump_system_config_version()
    except Exception:
        pass
    return norm


def ensure_proxy_config_schema():
    """供 arlupdate 启动迁移：幂等初始化或由旧 PROXY_URL 平滑升级至 proxy_config。"""
    col = _get_conn_db()("system_config")
    existing = col.find_one({"_id": PROXY_CONFIG_DOC_ID})
    if existing:
        norm = normalize_proxy_config(existing)
        # 仅在缺关键结构时补齐，不覆盖用户已配置项
        needs_patch = any(
            k not in existing for k in ("schema_version", "nodes", "policies", "bypass")
        ) or any(dom not in (existing.get("policies") or {}) for dom in TRAFFIC_DOMAINS)
        if needs_patch:
            save_proxy_config(norm)
        return False

    cfg = _fallback_config_from_legacy()
    save_proxy_config(cfg)
    return True


def upsert_proxy_node(payload, node_id=None):
    """新增或更新单个代理节点，返回 (updated_config, node)。"""
    cfg = load_proxy_config(use_cache=False)
    nodes = cfg["nodes"]
    existing = None
    existing_idx = None
    if node_id:
        for idx, item in enumerate(nodes):
            if item["id"] == node_id:
                existing = item
                existing_idx = idx
                break
        if existing is None:
            raise KeyError(f"节点不存在: {node_id}")

    norm_node = validate_node_payload(payload, existing_node=existing)
    if existing_idx is not None:
        nodes[existing_idx] = norm_node
    else:
        while any(n["id"] == norm_node["id"] for n in nodes):
            norm_node["id"] = f"node_{uuid.uuid4().hex[:8]}"
        nodes.append(norm_node)

    saved = save_proxy_config(cfg)
    return saved, norm_node


def delete_proxy_node(node_id):
    """删除代理节点并从各域绑定引用中平滑摘除，返回 (updated_config, removed_node)。"""
    cfg = load_proxy_config(use_cache=False)
    removed = None
    remaining = []
    for item in cfg["nodes"]:
        if item["id"] == node_id:
            removed = item
        else:
            remaining.append(item)
    if removed is None:
        raise KeyError(f"节点不存在: {node_id}")

    cfg["nodes"] = remaining
    for dom in TRAFFIC_DOMAINS:
        pol = cfg["policies"][dom]
        pol["node_ids"] = [nid for nid in (pol.get("node_ids") or []) if nid != node_id]
        # 若固定/切备策略绑定的节点已被全部删空，平滑回退为 direct_only，防止业务静默报错
        if pol.get("mode") in ("fixed_proxy", "failover", "round_robin") and not pol["node_ids"]:
            if not (pol.get("mode") == "round_robin" and pol.get("include_direct")):
                pol["mode"] = "direct_only"

    saved = save_proxy_config(cfg)
    return saved, removed


def update_proxy_policies(payload):
    """更新三域策略与旁路白名单。"""
    cfg = load_proxy_config(use_cache=False)
    merged = validate_policies_and_bypass_update(cfg, payload)
    return save_proxy_config(merged)


def sync_legacy_proxy_url(raw_url):
    """兼容旧版 POST /general 提交 proxy_url 时同步刷新 proxy_config。"""
    raw = str(raw_url or "").strip()
    cfg = load_proxy_config(use_cache=False)
    if raw:
        node = parse_proxy_url_string(raw, default_name="legacy-default", default_id="legacy-default")
        if node is None:
            raise ValueError("proxy_url 格式无效")
        nodes = [n for n in cfg.get("nodes", []) if n.get("id") != "legacy-default"]
        nodes.insert(0, node)
        cfg["nodes"] = nodes
        for dom in TRAFFIC_DOMAINS:
            pol = cfg["policies"][dom]
            if pol.get("mode") == "direct_only" or not pol.get("node_ids"):
                pol["mode"] = "fixed_proxy"
                pol["node_ids"] = ["legacy-default"]
    else:
        cfg["nodes"] = [n for n in cfg.get("nodes", []) if n.get("id") != "legacy-default"]
        for dom in TRAFFIC_DOMAINS:
            pol = cfg["policies"][dom]
            pol["node_ids"] = [nid for nid in (pol.get("node_ids") or []) if nid != "legacy-default"]
            if pol.get("mode") in ("fixed_proxy", "failover", "round_robin") and not pol["node_ids"]:
                if not (pol.get("mode") == "round_robin" and pol.get("include_direct")):
                    pol["mode"] = "direct_only"
    return save_proxy_config(cfg)


def infer_domain_for_url(url):
    """为未显式指定 proxy_domain 的 http_req 调用推断所属流量域。"""
    try:
        host = (urlsplit(str(url or "")).hostname or "").lower()
    except Exception:
        host = ""
    if not host:
        return "scan"
    if host in OSINT_HINT_HOSTS or host.endswith(".miit.gov.cn") or host.endswith(".tianyancha.com"):
        return "osint"
    if host in INTEL_HINT_HOSTS or host.endswith(".github.com") or host.endswith(".githubusercontent.com"):
        return "intel"
    return "scan"


def _match_host_pattern(host, pattern):
    host = host.lower().strip(".")
    pat = pattern.lower().strip()
    if not host or not pat:
        return False
    if pat.startswith("*."):
        suffix = pat[2:]
        return host == suffix or host.endswith("." + suffix)
    if pat.startswith("."):
        suffix = pat[1:]
        return host == suffix or host.endswith("." + suffix)
    return host == pat


def should_bypass_url(url, bypass_cfg=None, *, domain=None):
    """判断目标 URL 是否应当命中旁路直连规则。"""
    if domain == "bypass":
        return True
    if not url:
        return False
    text = str(url).strip()
    try:
        parsed = urlsplit(text)
    except Exception:
        return False
    host = (parsed.hostname or "").strip().lower()
    if not host:
        return False

    if host in INTERNAL_SERVICE_HOSTS or host.endswith(".local") or host.endswith(".internal"):
        return True

    env_no_proxy = os.environ.get("NO_PROXY") or os.environ.get("no_proxy") or ""
    if env_no_proxy:
        for pat in _normalize_no_proxy_entries(env_no_proxy):
            if _match_host_pattern(host, pat):
                return True

    cfg = bypass_cfg if isinstance(bypass_cfg, dict) else (load_proxy_config().get("bypass") or {})
    if cfg.get("bypass_domestic_webhooks", True) and host in DOMESTIC_WEBHOOK_HOSTS:
        return True

    ip_obj = None
    try:
        ip_obj = ipaddress.ip_address(host)
    except ValueError:
        ip_obj = None

    if cfg.get("bypass_private_cidr", True):
        if ip_obj is not None:
            if ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_link_local or ip_obj.is_reserved:
                return True
        elif "." not in host and ":" not in host:
            # 单标签主机名（如容器服务名 arl-test-target / 内部短名）无法被公网代理解析，开启内网旁路时自动直连
            return True

    for pat in cfg.get("custom_no_proxy") or []:
        if ip_obj is not None and "/" in pat:
            try:
                if ip_obj in ipaddress.ip_network(pat, strict=False):
                    return True
            except ValueError:
                pass
        if _match_host_pattern(host, pat):
            return True

    return False


def _read_runtime_status_doc():
    try:
        return _get_conn_db()("system_config").find_one({"_id": PROXY_RUNTIME_DOC_ID}) or {}
    except Exception:
        return {}


def _load_active_osint_blocked_map():
    doc = _read_runtime_status_doc()
    now = time.time()
    raw = doc.get("blocked_exits") if isinstance(doc.get("blocked_exits"), dict) else {}
    active = {}
    for exit_id, info in raw.items():
        if not isinstance(info, dict):
            continue
        try:
            until_ts = float(info.get("until_ts") or 0)
        except (TypeError, ValueError):
            until_ts = 0
        if until_ts > now:
            active[exit_id] = {
                **info,
                "until_ts": until_ts,
                "remaining_sec": max(1, int(round(until_ts - now))),
            }
    return active, doc


def _explicit_in_memory_proxy_override():
    """仅兼容测试替身或进程内临时覆写 Config.PROXY_URL 且数据库未配置 proxy_config 的情况。"""
    try:
        from app.config import Config
        mem_val = str(getattr(Config, "PROXY_URL", "") or "").strip()
        if mem_val:
            return mem_val
    except Exception:
        pass
    return ""


def resolve_proxy_candidates(domain="scan", target_url=None):
    """
    解析指定域与目标 URL 的有序候选代理 URL 列表。
    列表中的 None 表示直连；非空字符串表示具体代理 URL。
    """
    if domain == "bypass":
        return [None]

    cfg, db_has_proxy_doc = _load_proxy_config_with_meta()
    if should_bypass_url(target_url, cfg.get("bypass"), domain=domain):
        return [None]

    if not db_has_proxy_doc and not cfg.get("nodes"):
        mem_proxy = _explicit_in_memory_proxy_override()
        if mem_proxy:
            return [mem_proxy]

    policies = cfg.get("policies") or {}
    pol = policies.get(domain) or {"mode": "direct_only", "node_ids": []}
    mode = pol.get("mode", "direct_only")
    nodes_by_id = {n["id"]: n for n in cfg.get("nodes", []) if n.get("enabled", True)}
    bound_nodes = [nodes_by_id[nid] for nid in (pol.get("node_ids") or []) if nid in nodes_by_id]

    if mode == "direct_only" or (not bound_nodes and not pol.get("include_direct")):
        return [None]

    blocked_exits = {}
    if domain == "osint":
        blocked_exits, _ = _load_active_osint_blocked_map()

    if mode == "fixed_proxy":
        urls = [build_node_proxy_url(n) for n in bound_nodes if build_node_proxy_url(n)]
        return urls or [None]

    if mode == "failover":
        ordered = []
        if "__direct__" not in blocked_exits:
            ordered.append(None)
        for n in bound_nodes:
            if n["id"] not in blocked_exits:
                u = build_node_proxy_url(n)
                if u:
                    ordered.append(u)
        if not ordered:
            # 均在冷却时，保留主直连+备机按常规回退序列返回
            ordered.append(None)
            for n in bound_nodes:
                u = build_node_proxy_url(n)
                if u:
                    ordered.append(u)
        return ordered

    if mode == "round_robin":
        pool = []
        if pol.get("include_direct") and "__direct__" not in blocked_exits:
            pool.append(None)
        for n in bound_nodes:
            if n["id"] not in blocked_exits:
                u = build_node_proxy_url(n)
                if u:
                    pool.append(u)
        if not pool:
            pool = [build_node_proxy_url(n) for n in bound_nodes if build_node_proxy_url(n)]
            if pol.get("include_direct"):
                pool.insert(0, None)
        if not pool:
            return [None]
        with _RR_LOCK:
            idx = next(_RR_COUNTERS.setdefault(domain, itertools.count())) % len(pool)
        return pool[idx:] + pool[:idx]

    return [None]


def resolve_proxy_url(domain="scan", target_url=None):
    """返回当前域与目标最优先的单个代理 URL，直连时返回 ''。"""
    candidates = resolve_proxy_candidates(domain=domain, target_url=target_url)
    first = candidates[0] if candidates else None
    return first or ""


def resolve_requests_proxies(target_url=None, domain=None):
    """为 requests 库生成独立的新字典（避免全局 dict 并发竞态），直连返回 None。"""
    eff_domain = domain or infer_domain_for_url(target_url)
    proxy_url = resolve_proxy_url(domain=eff_domain, target_url=target_url)
    if not proxy_url:
        return None
    return {"http": proxy_url, "https": proxy_url}


def resolve_puppeteer_proxy(target_url=None):
    """
    评估 scan 域的 Puppeteer 代理可用性，返回 `(proxy_url, compat_warning)`。
    Chromium `--proxy-server` 原生不支持带用户名密码的 SOCKS5/HTTP 代理，自动降级直连。
    """
    cfg = load_proxy_config()
    scan_pol = (cfg.get("policies") or {}).get("scan") or {}
    if not scan_pol.get("apply_to_puppeteer", False):
        return None, None
    proxy_url = resolve_proxy_url(domain="scan", target_url=target_url)
    if not proxy_url:
        return None, None
    parsed = urlsplit(proxy_url)
    if parsed.username or parsed.password:
        return None, "当前 scan 域绑定节点启用了账号密码认证，Chromium 原生暂不支持带鉴权代理，Puppeteer 已自动降级直连。"
    return proxy_url, None


def get_osint_proxy_bundle():
    """构建透传给 osint-service 的完整策略上下文。"""
    cfg = load_proxy_config()
    osint_pol = deepcopy((cfg.get("policies") or {}).get("osint") or {})
    nodes_by_id = {n["id"]: n for n in cfg.get("nodes", []) if n.get("enabled", True)}
    resolved_nodes = []
    for nid in osint_pol.get("node_ids") or []:
        node = nodes_by_id.get(nid)
        if node:
            resolved_nodes.append({
                "id": node["id"],
                "name": node["name"],
                "protocol": node["protocol"],
                "proxy_url": build_node_proxy_url(node),
                "host": node["host"],
                "port": node["port"],
            })
    first_proxy = resolved_nodes[0]["proxy_url"] if (resolved_nodes and osint_pol.get("mode") != "direct_only") else ""
    return {
        "policy": osint_pol,
        "nodes": resolved_nodes,
        "legacy_proxy_url": first_proxy,
    }


def get_proxy_runtime_summary(domain="osint"):
    """生成前端 Dashboard / 测绘弹窗 / 代理页共享的运行态势单一事实源。"""
    cfg = load_proxy_config()
    nodes = cfg.get("nodes") or []
    enabled_nodes = [n for n in nodes if n.get("enabled", True)]
    nodes_by_id = {n["id"]: n for n in nodes}
    pol = (cfg.get("policies") or {}).get(domain) or {}
    mode = pol.get("mode", "direct_only")
    bound_enabled = [nodes_by_id[nid] for nid in (pol.get("node_ids") or []) if nid in nodes_by_id and nodes_by_id[nid].get("enabled", True)]
    _, puppet_warning = resolve_puppeteer_proxy()

    blocked_exits, rt_doc = _load_active_osint_blocked_map()
    direct_blocked = blocked_exits.get("__direct__")
    healthy_bound = [n for n in bound_enabled if n["id"] not in blocked_exits]

    state = "direct_ok"
    active_exit_id = "__direct__"
    active_node_name = ""
    cooldown_remaining_sec = 0

    if mode == "direct_only":
        if direct_blocked:
            state = "degraded_blocked"
            cooldown_remaining_sec = direct_blocked["remaining_sec"]
        else:
            state = "direct_ok"
    elif mode == "failover":
        if not direct_blocked:
            state = "direct_ok"
            active_exit_id = "__direct__"
        elif healthy_bound:
            state = "backup_active"
            active_exit_id = healthy_bound[0]["id"]
            active_node_name = healthy_bound[0]["name"]
            cooldown_remaining_sec = direct_blocked["remaining_sec"]
        elif bound_enabled:
            state = "degraded_blocked"
            all_rem = [direct_blocked["remaining_sec"]] + [
                blocked_exits[n["id"]]["remaining_sec"]
                for n in bound_enabled if n["id"] in blocked_exits
            ]
            cooldown_remaining_sec = min(all_rem) if all_rem else direct_blocked["remaining_sec"]
        else:
            state = "proxy_unavailable"
            cooldown_remaining_sec = direct_blocked["remaining_sec"]
    elif mode in ("fixed_proxy", "round_robin"):
        active_id = str(rt_doc.get("active_exit_id") or "")
        if healthy_bound:
            chosen = next((n for n in healthy_bound if n["id"] == active_id), healthy_bound[0])
            state = "proxy_active"
            active_exit_id = chosen["id"]
            active_node_name = chosen["name"]
        elif mode == "round_robin" and pol.get("include_direct") and not direct_blocked:
            state = "direct_ok"
            active_exit_id = "__direct__"
        elif bound_enabled:
            state = "degraded_blocked"
            rem_list = [blocked_exits[n["id"]]["remaining_sec"] for n in bound_enabled if n["id"] in blocked_exits]
            if mode == "round_robin" and pol.get("include_direct") and direct_blocked:
                rem_list.append(direct_blocked["remaining_sec"])
            cooldown_remaining_sec = min(rem_list) if rem_list else 0
        else:
            state = "proxy_unavailable"

    blocked_list = []
    for eid, info in blocked_exits.items():
        label = "主服务器直连" if eid == "__direct__" else (nodes_by_id.get(eid, {}).get("name") or eid)
        blocked_list.append({
            "exit_id": eid,
            "label": label,
            "reason": info.get("reason") or "触发风控/连接冷却",
            "ip": info.get("ip") or "",
            "remaining_sec": info.get("remaining_sec", 0),
            "until_ts": info.get("until_ts", 0),
        })

    return {
        "domain": domain,
        "mode": mode,
        "state": state,
        "active_exit_id": active_exit_id,
        "active_node_name": active_node_name,
        "cooldown_remaining_sec": cooldown_remaining_sec,
        "blocked_exits": blocked_list,
        "enabled_node_count": len(enabled_nodes),
        "total_node_count": len(nodes),
        "bound_node_count": len(bound_enabled),
        "last_switch_at": rt_doc.get("last_switch_at") or 0,
        "last_switch_reason": rt_doc.get("last_switch_reason") or "",
        "puppeteer_compat_warning": puppet_warning,
        "updated_at": rt_doc.get("updated_at") or 0,
    }


def record_osint_exit_event(
    proxy_url=None,
    *,
    blocked=False,
    cooldown_sec=300,
    reason="",
    exit_id=None,
):
    """记录 OSINT 单次请求的出口状态（成功切换或触发 403/419/网络故障冷却）。"""
    cfg = load_proxy_config()
    nodes = cfg.get("nodes") or []
    target_exit_id = exit_id
    node_name = ""
    if not target_exit_id:
        if not proxy_url:
            target_exit_id = "__direct__"
        else:
            for node in nodes:
                if build_node_proxy_url(node) == proxy_url:
                    target_exit_id = node["id"]
                    node_name = node["name"]
                    break
            if not target_exit_id:
                target_exit_id = f"ext:{mask_proxy_url_secret(proxy_url)}"

    if target_exit_id != "__direct__" and not node_name:
        for node in nodes:
            if node["id"] == target_exit_id:
                node_name = node["name"]
                break

    now = int(time.time())
    try:
        col = _get_conn_db()("system_config")
        rt_doc = col.find_one({"_id": PROXY_RUNTIME_DOC_ID}) or {}
        blocked_exits = dict(rt_doc.get("blocked_exits") or {})
        if blocked:
            blocked_exits[target_exit_id] = {
                "until_ts": now + max(10, int(cooldown_sec or 300)),
                "reason": str(reason or "触发风控冷却")[:200],
                "ip": "",
                "updated_at": now,
            }
            update_fields = {
                "blocked_exits": blocked_exits,
                "last_switch_at": now,
                "last_switch_reason": f"{'主服务器直连' if target_exit_id == '__direct__' else (node_name or target_exit_id)} 冷却 {int(cooldown_sec or 300)}s: {str(reason or '风控限制')[:120]}",
                "updated_at": now,
            }
        else:
            if target_exit_id in blocked_exits:
                blocked_exits.pop(target_exit_id, None)
            prev_active = rt_doc.get("active_exit_id")
            update_fields = {
                "blocked_exits": blocked_exits,
                "active_exit_id": target_exit_id,
                "updated_at": now,
            }
            if prev_active != target_exit_id:
                update_fields["last_switch_at"] = now
                update_fields["last_switch_reason"] = reason or (
                    "切换至主服务器直连" if target_exit_id == "__direct__" else f"切换至代理节点 {node_name or target_exit_id}"
                )
        col.update_one(
            {"_id": PROXY_RUNTIME_DOC_ID},
            {"$set": update_fields},
            upsert=True,
        )
    except Exception as e:
        logger.debug(f"record_osint_exit_event warning: {e}")


def reset_osint_cooldown():
    """清空 OSINT 冷却表并同步通知 osint-service 立即解除内存态冷却。"""
    try:
        _get_conn_db()("system_config").update_one(
            {"_id": PROXY_RUNTIME_DOC_ID},
            {"$set": {
                "blocked_exits": {},
                "active_exit_id": "__direct__",
                "last_switch_reason": "管理员手动重置冷却状态",
                "last_switch_at": int(time.time()),
                "updated_at": int(time.time()),
            }},
            upsert=True,
        )
    except Exception as e:
        logger.warning(f"reset_osint_cooldown db update warning: {e}")

    osint_notified = False
    try:
        resp = requests.post("http://osint-service:16181/api/v1/recon/proxy_reset_cooldown", timeout=3)
        osint_notified = resp.status_code == 200
    except Exception:
        osint_notified = False

    return {
        "osint_notified": osint_notified,
        "runtime": get_proxy_runtime_summary("osint"),
    }


def _extract_egress_ip(text):
    if not text:
        return ""
    m = re.search(r"(\d{1,3}(?:\.\d{1,3}){3})", str(text))
    if m:
        return m.group(1)
    return ""


def probe_proxy_node(node_id=None, draft_payload=None, preset="egress_ip", save_result=True):
    """
    使用安全白名单探针对代理节点进行真实连通性与出口 IP 探测。
    禁止传入任意外部 URL，杜绝探测接口沦为 SSRF 入口。
    """
    if preset not in PROBE_PRESETS:
        raise ValueError(f"不支持的探针预设: {preset}")

    cfg = load_proxy_config(use_cache=False)
    target_node = None
    if node_id:
        for item in cfg["nodes"]:
            if item["id"] == node_id:
                target_node = deepcopy(item)
                break
        if target_node is None:
            raise KeyError(f"节点不存在: {node_id}")
        if isinstance(draft_payload, dict):
            target_node = validate_node_payload(draft_payload, existing_node=target_node)
    elif isinstance(draft_payload, dict):
        target_node = validate_node_payload(draft_payload, existing_node=None)
    else:
        raise ValueError("必须提供 node_id 或待测节点配置")

    proxy_url = build_node_proxy_url(target_node)
    proxies = {"http": proxy_url, "https": proxy_url}
    headers = {"User-Agent": "ARL-Next-Proxy-Probe/1.0"}
    preset_cfg = PROBE_PRESETS[preset]

    ok = False
    status_code = 0
    latency_ms = None
    egress_ip = ""
    waf_blocked = False
    detail = ""

    for probe_url in preset_cfg["urls"]:
        t0 = time.monotonic()
        try:
            resp = requests.get(
                probe_url,
                proxies=proxies,
                headers=headers,
                timeout=(6, 10),
                allow_redirects=False,
                verify=True,
            )
            latency_ms = int(round((time.monotonic() - t0) * 1000))
            status_code = resp.status_code
            body = resp.text or ""
            if preset == "egress_ip":
                ip = _extract_egress_ip(body)
                if resp.status_code < 400 and (ip or body.strip()):
                    ok = True
                    egress_ip = ip
                    detail = f"出口连通正常 (HTTP {status_code}" + (f", IP: {ip})" if ip else ")")
                    break
                detail = f"探针返回 HTTP {status_code}"
            elif preset == "miit":
                if "创宇盾" in body or "error_403_type" in body or status_code == 403:
                    waf_blocked = True
                    detail = "可连通工信部网站，但该出口 IP 当前被创宇盾拦截 (HTTP 403)"
                    ok = False
                elif status_code < 500 or status_code == 521:
                    ok = True
                    suffix = "（前置挑战，出口未被封禁）" if status_code == 521 else ""
                    detail = f"工信部出口握手正常 (HTTP {status_code}){suffix}"
                else:
                    detail = f"工信部返回异常状态 HTTP {status_code}"
                break
            elif preset == "tianyancha":
                if status_code == 419 or "bannedLocation" in body or "301000" in body:
                    waf_blocked = True
                    ok = False
                    detail = "该出口被天眼查地域围栏拦截 (HTTP 419 bannedLocation，可能为非中国大陆 IP)"
                elif status_code < 500:
                    ok = True
                    detail = f"天眼查出口连通正常，未触发地域围栏 (HTTP {status_code})"
                else:
                    detail = f"天眼查返回异常状态 HTTP {status_code}"
                break
            elif preset == "github":
                if status_code < 400:
                    ok = True
                    detail = f"GitHub API 连通正常 (HTTP {status_code})"
                else:
                    detail = f"GitHub API 返回 HTTP {status_code}"
                break
        except Exception as exc:
            latency_ms = int(round((time.monotonic() - t0) * 1000))
            err_str = str(exc)
            if "Missing dependencies for SOCKS support" in err_str:
                detail = "当前运行环境缺少 PySocks 依赖，请 rebuild 镜像以启用 SOCKS5 支持"
                break
            detail = f"连接失败: {err_str[:180]}"

    result = {
        "ok": ok,
        "preset": preset,
        "status_code": status_code,
        "latency_ms": latency_ms,
        "egress_ip": egress_ip,
        "waf_blocked": waf_blocked,
        "detail": detail,
        "checked_at": int(time.time()),
    }

    if save_result and node_id:
        for item in cfg["nodes"]:
            if item["id"] == node_id:
                item["last_probe"] = result
                break
        try:
            save_proxy_config(cfg)
        except Exception as e:
            logger.debug(f"save probe result failed: {e}")

    return result


def get_proxy_capabilities():
    """检查当前进程运行时的代理协议与引擎兼容能力。"""
    try:
        import socks  # noqa: F401
        pysocks_ok = True
    except ImportError:
        pysocks_ok = False
    return {
        "pysocks_installed": pysocks_ok,
        "protocols": list(SUPPORTED_PROTOCOLS),
        "presets": [
            {"key": k, "label": v["label"]} for k, v in PROBE_PRESETS.items()
        ],
    }
