# -*- coding: utf-8 -*-
"""
OSINT 微服务多出口代理调度与自动切备路由器。

职责：
1. 读取主服务传入的 proxy_bundle 或直接从共享 MongoDB `system_config` 同步策略与节点池。
2. 支持 http / https / socks5 / socks5h 协议，自动为 aiohttp 构建 TCPConnector 或 aiohttp_socks.ProxyConnector。
3. 维护按物理出口 IP 隔离的限流时间槽（直连与单个备机均严格遵守 2.6s~3.2s 安全间隔，防止备机过快烧毁）。
4. 维护主/备出口冷却状态与 300s 自动回切（failover / round_robin / fixed_proxy / direct_only），支持管理员一键重置。
"""

import asyncio
import logging
import random
import re
import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

from aiohttp import TCPConnector

logger = logging.getLogger(__name__)

DIRECT_EXIT_ID = "__direct__"
PROXY_CONFIG_DOC_ID = "proxy_config"
PROXY_RUNTIME_DOC_ID = "proxy_runtime_status"
DEFAULT_COOLDOWN_SEC = 300
TRANSPORT_COOLDOWN_SEC = 60

_GLOBAL_STATE_LOCK = threading.Lock()
_GLOBAL_RESET_EPOCH = 0
_PROCESS_RATE_LOCK_GUARD = threading.Lock()
_PROCESS_RATE_LOCKS = {}
_PROCESS_LAST_REQ_TS = {}


def bump_global_reset_epoch():
    """供 POST /api/v1/recon/proxy_reset_cooldown 触发，通知所有运行中路由器同步解除冷却。"""
    global _GLOBAL_RESET_EPOCH
    with _GLOBAL_STATE_LOCK:
        _GLOBAL_RESET_EPOCH += 1
        return _GLOBAL_RESET_EPOCH


def get_global_reset_epoch():
    with _GLOBAL_STATE_LOCK:
        return _GLOBAL_RESET_EPOCH


def normalize_proxy_url(raw):
    if not raw or not isinstance(raw, str):
        return None
    p = raw.strip()
    if not p:
        return None
    if "://" not in p:
        p = f"http://{p}"
    return p


def mask_proxy_url_secret(proxy_url):
    if not proxy_url:
        return ""
    text = str(proxy_url).strip()
    if not text:
        return ""
    has_scheme = "://" in text
    try:
        parsed = urlsplit(text if has_scheme else f"http://{text}")
        if not parsed.hostname:
            return "***" if "@" in text else text
        if parsed.username or parsed.password or "@" in text:
            host = parsed.hostname or ""
            if ":" in host and not host.startswith("["):
                host = f"[{host}]"
            port = f":{parsed.port}" if parsed.port else ""
            user_label = parsed.username or "***"
            if has_scheme:
                return f"{parsed.scheme}://{user_label}:******@{host}{port}"
            return f"{user_label}:******@{host}{port}"
        return text
    except Exception:
        return "***"


def _safe_exit_id_key(raw_id):
    return re.sub(r"[.$]+", "_", str(raw_id or DIRECT_EXIT_ID))


def extract_proxy_ip(proxy_url):
    if not proxy_url or not isinstance(proxy_url, str):
        return None
    m = re.search(r"@?(\d{1,3}(?:\.\d{1,3}){3})", proxy_url)
    if m:
        return m.group(1)
    try:
        host = urlsplit(normalize_proxy_url(proxy_url) or "").hostname
        if host:
            return host
    except Exception:
        pass
    m_dom = re.search(r"://([^:/]+)", proxy_url)
    if m_dom:
        return m_dom.group(1)
    return proxy_url.strip() or None


def build_aiohttp_connector(proxy_url=None, *, local_ipv6=None, connector_config=None):
    """
    依据代理协议返回 `(connector, request_proxy_arg)`。
    - 直连：`(TCPConnector(...), None)`
    - HTTP / HTTPS 代理：`(TCPConnector(...), proxy_url)`，交由 aiohttp session.request(proxy=...) 握手
    - SOCKS5 / SOCKS5H：`(aiohttp_socks.ProxyConnector.from_url(...), None)`，严禁同时传 session.post(proxy=...)
    """
    cfg = dict(connector_config or {})
    norm = normalize_proxy_url(proxy_url)
    if norm:
        scheme = (urlsplit(norm).scheme or "").lower()
        if scheme in ("socks5", "socks5h", "socks4", "socks4a"):
            try:
                from aiohttp_socks import ProxyConnector
            except ImportError as exc:
                raise RuntimeError("当前 osint-service 缺少 aiohttp-socks 依赖，无法启用 SOCKS5 代理") from exc
            socks_kwargs = {}
            for k in ("limit", "limit_per_host", "ttl_dns_cache", "use_dns_cache", "keepalive_timeout"):
                if k in cfg:
                    socks_kwargs[k] = cfg[k]
            if "ssl" in cfg:
                socks_kwargs["ssl"] = cfg["ssl"]
            # python_socks.parse_proxy_url 只接受 socks5/socks4 scheme，远端解析由 rdns=True 控制
            _, _, rest = norm.partition("://")
            connector_url = norm
            if scheme == "socks5h":
                connector_url = f"socks5://{rest}"
            elif scheme == "socks4a":
                connector_url = f"socks4://{rest}"
            connector = ProxyConnector.from_url(
                connector_url,
                rdns=(scheme in ("socks5h", "socks4a")),
                **socks_kwargs,
            )
            connector._arl_local_ip = extract_proxy_ip(norm)
            return connector, None
        connector = TCPConnector(**cfg)
        connector._arl_local_ip = extract_proxy_ip(norm)
        return connector, norm

    if local_ipv6:
        connector = TCPConnector(local_addr=(local_ipv6, 0), **cfg)
        connector._arl_local_ip = local_ipv6
    else:
        connector = TCPConnector(**cfg)
        connector._arl_local_ip = None
    return connector, None


@dataclass
class ExitCandidate:
    exit_id: str
    name: str
    proxy_url: str = None
    ip: str = ""


class OsintProxyRouter:
    """支持多节点故障切换、回切、轮询以及每出口物理速率槽的 OSINT 路由器。"""

    def __init__(self, bundle=None, *, db=None, legacy_proxy=None, syslog_cb=None, service_scope=""):
        self.db = db
        self.syslog_cb = syslog_cb
        self.service_scope = str(service_scope or "").strip().lower()
        self.policy = {}
        self.nodes = []
        self.has_structured_policy = False
        self.legacy_proxy = normalize_proxy_url(legacy_proxy)
        self.blocked_exits = {}
        self.active_exit_id = DIRECT_EXIT_ID
        self.last_switch_reason = ""
        self.last_switch_at = 0
        self._rr_index = 0
        self._fail_streak = {}
        self._sticky_backup_exit_id = None
        self._seen_reset_epoch = get_global_reset_epoch()
        self._lock = threading.Lock()
        self._rate_locks = _PROCESS_RATE_LOCKS
        self._last_req_ts_by_exit = _PROCESS_LAST_REQ_TS
        self._dirty_blocked_keys = set()
        self._dirty_cleared_keys = set()
        self._full_reset_pending = False
        if bundle:
            self.load_bundle(bundle)

    def load_bundle(self, bundle):
        if not isinstance(bundle, dict):
            return
        policy = bundle.get("policy") or {}
        raw_nodes = bundle.get("nodes") or []
        norm_nodes = []
        for item in raw_nodes:
            if not isinstance(item, dict):
                continue
            p_url = normalize_proxy_url(item.get("proxy_url"))
            if not p_url:
                continue
            norm_nodes.append({
                "id": str(item.get("id") or ""),
                "name": str(item.get("name") or item.get("id") or "proxy"),
                "protocol": str(item.get("protocol") or "http"),
                "proxy_url": p_url,
                "ip": str(item.get("host") or extract_proxy_ip(p_url) or ""),
            })
        with self._lock:
            self.policy = dict(policy)
            self.nodes = norm_nodes
            self.has_structured_policy = True
            if bundle.get("legacy_proxy_url"):
                self.legacy_proxy = normalize_proxy_url(bundle.get("legacy_proxy_url"))

    async def sync_from_db(self, db=None):
        target_db = db if db is not None else self.db
        if target_db is None:
            return
        self.db = target_db
        try:
            proxy_doc = await target_db["system_config"].find_one({"_id": PROXY_CONFIG_DOC_ID})
            rt_doc = await target_db["system_config"].find_one({"_id": PROXY_RUNTIME_DOC_ID})
            if proxy_doc:
                nodes_by_id = {}
                for n in proxy_doc.get("nodes") or []:
                    if not isinstance(n, dict) or not n.get("enabled", True):
                        continue
                    nid = str(n.get("id") or "")
                    if not nid:
                        continue
                    proto = str(n.get("protocol") or "http").lower()
                    host = str(n.get("host") or "").strip()
                    port = n.get("port")
                    if not host or not port:
                        continue
                    auth = ""
                    user = str(n.get("username") or "").strip()
                    pwd = str(n.get("password") or "").strip()
                    if user and pwd:
                        from urllib.parse import quote
                        auth = f"{quote(user, safe='')}:{quote(pwd, safe='')}@"
                    elif user:
                        from urllib.parse import quote
                        auth = f"{quote(user, safe='')}@"
                    p_host = f"[{host}]" if (":" in host and not host.startswith("[")) else host
                    p_url = f"{proto}://{auth}{p_host}:{int(port)}"
                    nodes_by_id[nid] = {
                        "id": nid,
                        "name": str(n.get("name") or nid),
                        "protocol": proto,
                        "proxy_url": p_url,
                        "host": host,
                    }
                osint_pol = (proxy_doc.get("policies") or {}).get("osint") or {}
                resolved_nodes = [nodes_by_id[nid] for nid in (osint_pol.get("node_ids") or []) if nid in nodes_by_id]
                self.load_bundle({
                    "policy": osint_pol,
                    "nodes": resolved_nodes,
                })
            elif not self.has_structured_policy and not self.legacy_proxy:
                gen = await target_db["system_config"].find_one({"_id": "general_config"}, {"proxy_url": 1})
                if gen and gen.get("proxy_url"):
                    self.legacy_proxy = normalize_proxy_url(gen.get("proxy_url"))

            if rt_doc:
                self._sync_blocked_from_doc(rt_doc)
        except Exception as exc:
            logger.debug(f"OsintProxyRouter sync_from_db warning: {exc}")

    def _sync_blocked_from_doc(self, rt_doc):
        now = time.time()
        raw_blocked = rt_doc.get("blocked_exits") if isinstance(rt_doc.get("blocked_exits"), dict) else {}
        with self._lock:
            cleaned = {}
            for eid, info in raw_blocked.items():
                if not isinstance(info, dict):
                    continue
                entry_scope = str(info.get("service_scope") or "").strip().lower()
                if self.service_scope and entry_scope and entry_scope != self.service_scope:
                    continue
                try:
                    until_ts = float(info.get("until_ts") or 0)
                except (TypeError, ValueError):
                    until_ts = 0
                if until_ts > now:
                    entry = {
                        "until_ts": until_ts,
                        "reason": str(info.get("reason") or ""),
                        "ip": str(info.get("ip") or ""),
                    }
                    if entry_scope:
                        entry["service_scope"] = entry_scope
                    if info.get("streak"):
                        entry["streak"] = int(info.get("streak") or 1)
                    cleaned[str(eid)] = entry
            self.blocked_exits = cleaned
            if rt_doc.get("active_exit_id"):
                self.active_exit_id = str(rt_doc.get("active_exit_id"))

    def _check_reset_epoch(self):
        cur = get_global_reset_epoch()
        if cur != self._seen_reset_epoch:
            with self._lock:
                if cur != self._seen_reset_epoch:
                    self.blocked_exits.clear()
                    self._fail_streak.clear()
                    self._sticky_backup_exit_id = None
                    self.active_exit_id = DIRECT_EXIT_ID
                    self.last_switch_reason = "管理员手动重置冷却"
                    self.last_switch_at = int(time.time())
                    self._seen_reset_epoch = cur

    def _prune_expired_locked(self):
        now = time.time()
        expired = [k for k, v in self.blocked_exits.items() if float(v.get("until_ts") or 0) <= now]
        for k in expired:
            self.blocked_exits.pop(k, None)

    def is_exit_blocked(self, exit_id):
        self._check_reset_epoch()
        with self._lock:
            self._prune_expired_locked()
            return exit_id in self.blocked_exits

    def clear_all_cooldowns(self):
        with self._lock:
            self.blocked_exits.clear()
            self._fail_streak.clear()
            self._dirty_blocked_keys.clear()
            self._dirty_cleared_keys.clear()
            self._full_reset_pending = True
            self._sticky_backup_exit_id = None
            self.active_exit_id = DIRECT_EXIT_ID
            self.last_switch_reason = "管理员手动重置冷却"
            self.last_switch_at = int(time.time())

    def allow_primary_failback(self):
        """在主体或阶段切换边界解除备机粘性锁定，允许主出口冷却恢复后平滑探测回切。"""
        with self._lock:
            self._sticky_backup_exit_id = None

    def get_mode(self):
        return str(self.policy.get("mode") or "direct_only")

    def get_cooldown_sec(self):
        try:
            return max(30, int(self.policy.get("cooldown_sec") or DEFAULT_COOLDOWN_SEC))
        except (TypeError, ValueError):
            return DEFAULT_COOLDOWN_SEC

    def get_max_failovers(self):
        try:
            return max(0, int(self.policy.get("max_failovers") if self.policy.get("max_failovers") is not None else 2))
        except (TypeError, ValueError):
            return 2

    def _all_allowed_exits(self):
        mode = self.get_mode()
        direct = ExitCandidate(exit_id=DIRECT_EXIT_ID, name="主服务器直连", proxy_url=None, ip="")
        node_cands = [
            ExitCandidate(exit_id=n["id"], name=n["name"], proxy_url=n["proxy_url"], ip=n.get("ip", ""))
            for n in self.nodes
        ]
        if mode == "direct_only":
            return [direct]
        if mode == "failover":
            return [direct] + node_cands
        if mode == "round_robin":
            pool = ([direct] if self.policy.get("include_direct") else []) + node_cands
            return pool
        if mode == "fixed_proxy":
            # OSINT 域固定代理无可用启用节点时严格 Fail-Closed，严禁静默回退主服务器直连
            return node_cands
        return [direct]

    def get_candidates(self, explicit_proxy=None, sticky=False):
        """
        返回当前可尝试的有序候选出口列表。
        - failover：主直连健康时排首位（到点自动回切）；主直连处于冷却时跳过直连并优先返回健康备机。
          当 sticky=True 且当前已切至健康备机时，在本阶段内保持粘性不中途强切回直连。
        - round_robin：在所有健康可用出口间轮转，且其余健康出口跟在后面供单次异常兜底。
        - fixed_proxy：仅返回健康的绑定代理节点。
        - direct_only：仅返回直连（若处于冷却则返回空，由上游等待单次冷却）。
        """
        self._check_reset_epoch()
        explicit = normalize_proxy_url(explicit_proxy)
        if not self.has_structured_policy and explicit:
            ip_or_masked = extract_proxy_ip(explicit) or mask_proxy_url_secret(explicit)
            eid = f"explicit:{_safe_exit_id_key(ip_or_masked)}"
            if self.is_exit_blocked(eid):
                return []
            return [ExitCandidate(exit_id=eid, name=mask_proxy_url_secret(explicit), proxy_url=explicit, ip=extract_proxy_ip(explicit) or "")]

        allowed = self._all_allowed_exits()
        with self._lock:
            self._prune_expired_locked()
            healthy = [c for c in allowed if c.exit_id not in self.blocked_exits]
            mode = self.get_mode()
            if sticky and mode == "failover" and self._sticky_backup_exit_id:
                sticky_cand = next((c for c in healthy if c.exit_id == self._sticky_backup_exit_id), None)
                if sticky_cand is not None:
                    healthy = [sticky_cand] + [c for c in healthy if c.exit_id != self._sticky_backup_exit_id]
            elif mode == "round_robin" and len(healthy) > 1:
                idx = self._rr_index % len(healthy)
                self._rr_index += 1
                healthy = healthy[idx:] + healthy[:idx]
            max_attempts = 1 + self.get_max_failovers()
            return healthy[:max_attempts]

    def has_healthy_exit(self, explicit_proxy=None):
        return bool(self.get_candidates(explicit_proxy=explicit_proxy))

    def has_healthy_backup_proxy(self):
        self._check_reset_epoch()
        with self._lock:
            self._prune_expired_locked()
            for n in self.nodes:
                if n["id"] not in self.blocked_exits:
                    return True
        return False

    def is_all_exits_blocked(self):
        return not self.get_candidates()

    def earliest_unblock_delay(self):
        """当所有允许出口均处于冷却时，返回最近恢复出口还需等待的秒数。"""
        self._check_reset_epoch()
        allowed_ids = {c.exit_id for c in self._all_allowed_exits()}
        now = time.time()
        with self._lock:
            self._prune_expired_locked()
            if any(eid not in self.blocked_exits for eid in allowed_ids):
                return 0.0
            remaining = [
                max(0.0, float(self.blocked_exits[eid]["until_ts"]) - now)
                for eid in allowed_ids if eid in self.blocked_exits
            ]
            return min(remaining) if remaining else 0.0

    def mark_exit_blocked(self, exit_id, *, reason="", ip="", cooldown_sec=None):
        now = time.time()
        with self._lock:
            streak = self._fail_streak.get(exit_id, 0) + 1
            self._fail_streak[exit_id] = streak
            if cooldown_sec is None:
                base_cd = max(10, int(self.get_cooldown_sec()))
                cd = min(1800, base_cd * (2 ** min(streak - 1, 3)))
            else:
                cd = max(10, int(cooldown_sec))
            if self._sticky_backup_exit_id == exit_id:
                self._sticky_backup_exit_id = None
            entry = {
                "until_ts": now + cd,
                "reason": str(reason or "触发风控限制")[:200],
                "ip": str(ip or ""),
                "streak": streak,
            }
            if self.service_scope:
                entry["service_scope"] = self.service_scope
            self.blocked_exits[exit_id] = entry
            self._dirty_blocked_keys.add(exit_id)
            self._dirty_cleared_keys.discard(exit_id)
            self.last_switch_at = int(now)
            self.last_switch_reason = f"{exit_id} 冷却 {cd}s: {str(reason or '风控限制')[:120]}"
        return cd

    def mark_exit_active(self, exit_id, reason=""):
        with self._lock:
            prev = self.active_exit_id
            self.active_exit_id = exit_id
            was_blocked = exit_id in self.blocked_exits
            self.blocked_exits.pop(exit_id, None)
            self._fail_streak.pop(exit_id, None)
            if was_blocked:
                self._dirty_cleared_keys.add(exit_id)
                self._dirty_blocked_keys.discard(exit_id)
            if self.get_mode() == "failover":
                self._sticky_backup_exit_id = exit_id if exit_id != DIRECT_EXIT_ID else None
            if prev != exit_id:
                self.last_switch_at = int(time.time())
                self.last_switch_reason = reason or f"切换至出口 {exit_id}"

    async def persist_runtime_status(self):
        if self.db is None:
            return
        with self._lock:
            now_int = int(time.time())
            now_flt = time.time()
            expired = [k for k, v in self.blocked_exits.items() if float(v.get("until_ts") or 0) <= now_flt]
            for k in expired:
                self.blocked_exits.pop(k, None)
                self._dirty_cleared_keys.add(k)
                self._dirty_blocked_keys.discard(k)

            full_reset = self._full_reset_pending
            self._full_reset_pending = False
            dirty_blocked = {k: dict(self.blocked_exits[k]) for k in list(self._dirty_blocked_keys) if k in self.blocked_exits}
            dirty_cleared = list(self._dirty_cleared_keys)
            self._dirty_blocked_keys.clear()
            self._dirty_cleared_keys.clear()

            set_ops = {
                "active_exit_id": self.active_exit_id,
                "last_switch_at": self.last_switch_at,
                "last_switch_reason": self.last_switch_reason,
                "updated_at": now_int,
            }
            unset_ops = {}
            if full_reset or (not dirty_blocked and not dirty_cleared and not self.blocked_exits):
                set_ops["blocked_exits"] = dict(self.blocked_exits)
            else:
                for k, v in dirty_blocked.items():
                    set_ops[f"blocked_exits.{_safe_exit_id_key(k)}"] = v
                for k in dirty_cleared:
                    if k not in dirty_blocked:
                        unset_ops[f"blocked_exits.{_safe_exit_id_key(k)}"] = ""

        update_doc = {"$set": set_ops}
        if unset_ops:
            update_doc["$unset"] = unset_ops
        try:
            await self.db["system_config"].update_one(
                {"_id": PROXY_RUNTIME_DOC_ID},
                update_doc,
                upsert=True,
            )
        except Exception as exc:
            logger.debug(f"persist_runtime_status warning: {exc}")

    async def emit_syslog(self, level, title, message):
        if not callable(self.syslog_cb):
            return
        try:
            res = self.syslog_cb(level, title, message)
            if asyncio.iscoroutine(res):
                await res
        except Exception:
            pass

    def _get_exit_rate_lock(self, exit_id):
        key = str(exit_id or DIRECT_EXIT_ID)
        try:
            loop_id = id(asyncio.get_running_loop())
        except RuntimeError:
            loop_id = 0
        lock_key = (loop_id, key)
        with _PROCESS_RATE_LOCK_GUARD:
            lock = self._rate_locks.get(lock_key)
            if lock is None:
                lock = asyncio.Lock()
                self._rate_locks[lock_key] = lock
            return lock

    async def acquire_rate_slot(self, exit_id=DIRECT_EXIT_ID, interval_range=(2.6, 3.2)):
        """按物理出口 ID 隔离控频：每个独立出口（直连或单台备机）均严格保持 2.6s~3.2s 安全间隔。"""
        key = str(exit_id or DIRECT_EXIT_ID)
        lock = self._get_exit_rate_lock(key)
        async with lock:
            now = time.time()
            last_ts = self._last_req_ts_by_exit.get(key, 0.0)
            min_interval = random.uniform(interval_range[0], interval_range[1])
            elapsed = now - last_ts
            if elapsed < min_interval:
                await asyncio.sleep(min_interval - elapsed)
            self._last_req_ts_by_exit[key] = time.time()
