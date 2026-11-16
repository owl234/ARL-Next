# -*- coding: utf-8 -*-
import asyncio
import aiohttp
import time
import hashlib
import re
import base64
import os
import io
import inspect
import numpy as np
from PIL import Image
import ujson
import random
import uuid
from aiohttp import TCPConnector
from mlog import logger
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
import ssl
import subprocess
import locale
from contextlib import asynccontextmanager
import threading
from load_config import config
from cachetools import TTLCache
from proxy_router import (
    DIRECT_EXIT_ID,
    ExitCandidate,
    OsintProxyRouter,
    build_aiohttp_connector,
    mask_proxy_url_secret,
    normalize_proxy_url,
)



def is_public_ipv6(ipv6):
    return not (ipv6.startswith("fe80") or ipv6.startswith("fc00") or ipv6.startswith("fd00"))

# 获取本地IPv6地址
def _run_cmd_capture(cmd):
    """执行系统命令并自动多编码尝试解码，失败返回空字符串"""
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate(timeout=5)
    except Exception:
        return ""
    if not out:
        return ""
    enc_candidates = [
        "utf-8",
        locale.getpreferredencoding(False) or "",
        "gbk",
        "cp936",
        "latin-1",
    ]
    for enc in enc_candidates:
        if not enc:
            continue
        try:
            return out.decode(enc)
        except Exception:
            continue
    return out.decode("utf-8", errors="ignore")

def get_local_ipv6_addresses():
    """跨平台获取本机公网IPv6地址，自动处理编码/异常"""
    addresses = []
    try:
        if os.name == 'nt':  # Windows
            output = _run_cmd_capture(["netsh", "interface", "ipv6", "show", "addresses"])
            if not output:
                return []
            for line in output.splitlines():
                line_strip = line.strip()
                # 兼容中文(公用/手动)及可能的英文(Public/Manual)
                if any(k in line_strip for k in ("公用", "手动", "Public", "Manual")) and ":" in line_strip:
                    parts = line_strip.split()
                    candidate = parts[-1]
                    candidate = candidate.strip()
                    # 去除可能的/前缀长度
                    candidate = candidate.split("/")[0]
                    if ":" in candidate and is_public_ipv6(candidate):
                        addresses.append(candidate)
        else:  # Linux / mac
            output = _run_cmd_capture(["ip", "-6", "addr", "show"])
            if not output:
                return []
            for line in output.splitlines():
                line_strip = line.strip()
                if ("inet6" in line_strip) and ("scope global" in line_strip):
                    try:
                        candidate = line_strip.split()[1].split("/")[0]
                        if is_public_ipv6(candidate):
                            addresses.append(candidate)
                    except Exception:
                        continue
    except Exception:
        return []
    # 去重
    return list(dict.fromkeys(addresses))

class _ExitAttemptError(Exception):
    """内部控制流异常：标识单次请求出口命中 WAF/限流/网络故障，供上层按策略故障切换。"""
    def __init__(self, kind, reason, blocked_ip=None, cooldown_sec=None):
        super().__init__(reason)
        self.kind = kind
        self.reason = reason
        self.blocked_ip = blocked_ip
        self.cooldown_sec = cooldown_sec


class beian:
    def __init__(self):
        self.typj = {
            0: ujson.dumps(
                {"pageNum": "", "pageSize": "", "unitName": "", "serviceType": 1}
            ),  # 网站
            1: ujson.dumps(
                {"pageNum": "", "pageSize": "", "unitName": "", "serviceType": 6}
            ),  # APP
            2: ujson.dumps(
                {"pageNum": "", "pageSize": "", "unitName": "", "serviceType": 7}
            ),  # 小程序
            3: ujson.dumps(
                {"pageNum": "", "pageSize": "", "unitName": "", "serviceType": 8}
            ),  # 快应用
        }
        self.btypj = {
            0: ujson.dumps({"domainName": ""}),
            1: ujson.dumps({"serviceName": "", "serviceType": 6}),
            2: ujson.dumps({"serviceName": "", "serviceType": 7}),
            3: ujson.dumps({"serviceName": "", "serviceType": 8}),
        }
        self.session = None
        self.cookie_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.41 Safari/537.36 Edg/101.0.1210.32"
        }
        self.home = "https://beian.miit.gov.cn/"
        self.url = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/auth"
        self.getCheckImage = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/image/getCheckImagePoint"
        self.checkImage = (
            "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/image/checkImage"
        )
        # 正常查询
        self.queryByCondition = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/icpAbbreviateInfo/queryByCondition"
        # 违法违规域名查询
        self.blackqueryByCondition = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/blackListDomain/queryByCondition"
        # 违法违规APP,小程序,快应用
        self.blackappAndMiniByCondition = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/blackListDomain/queryByCondition_appAndMini"
        # APP/小程序/快应用详情查询接口
        self.queryDetailByAppAndMiniId = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/icpAbbreviateInfo/queryDetailByAppAndMiniId"
        self.sign = "eyJ0eXBlIjozLCJleHREYXRhIjp7InZhZnljb2RlX2ltYWdlX2tleSI6IjUyZWI1ZTcyODViNzRmNWJhM2YwYzBkNTg0YTg3NmVmIn0sImUiOjE3NTY5NzAyNDg4MjN9.Ngpkwn4T7sQoQF9pCk_sQQpH61wQUEKnK2sQ8hDIq-Q"
        self.token = ""
        self.token_expire = 0
        self.timeout = aiohttp.ClientTimeout(total=getattr(getattr(config, 'system', object()), 'http_client_timeout', 30))
        self.local_ipv6_addresses = get_local_ipv6_addresses() if getattr(getattr(getattr(config, 'proxy', object()), 'local_ipv6_pool', object()), 'enable', False) else []
        self.ipv6_index = 0
        
        self._ipv6_lock = threading.Lock()  # IPv6轮询锁
        
        # 连接池配置
        self.connector_config = {
            'limit': 100,
            'limit_per_host': 30,
            'ttl_dns_cache': 300,
            'use_dns_cache': True,
            'ssl': False,
            'keepalive_timeout': 30
        }

        self._blocked_ip_cache = TTLCache(maxsize=1000, ttl=300)
        self._blocked_ip_lock = threading.Lock()

        # WAF 熔断状态挂在实例上：单 IP 冷却期对齐 IP 封禁 300s TTL
        self._waf_block_ts = 0.0
        self.waf_cooldown = 300
        # 详情专属熔断状态：避免详情限流殃及列表查询（冷却 180s）
        self._detail_waf_block_ts = 0.0
        self.detail_waf_cooldown = 180
        self._token_lock = None

        # 全局自适应流控锁与时间戳（单 IP 直连物理消峰）
        self._rate_lock = None
        self._last_req_ts = 0.0
        self._cached_jsluid = None
        self.proxy_router = OsintProxyRouter()
        self._progress_cb = None
        self._page_cb = None
        self._detail_cb = None
        self._should_stop_cb = None
        self._skip_detail_fn = None

    def attach_proxy_router(self, router):
        if router is not None:
            self.proxy_router = router

    def attach_task_hooks(
        self,
        *,
        progress_cb=None,
        page_cb=None,
        detail_cb=None,
        should_stop_cb=None,
        skip_detail_fn=None,
    ):
        """挂载任务级进度日志、增量落库、详情回写与协同终止回调"""
        self._progress_cb = progress_cb
        self._page_cb = page_cb
        self._detail_cb = detail_cb
        self._should_stop_cb = should_stop_cb
        self._skip_detail_fn = skip_detail_fn

    def _get_system_int_config(self, key, default):
        val = getattr(getattr(config, "system", object()), key, None)
        if val is None or val == "":
            return default
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    async def _emit_progress(self, sp, stage, message):
        if self._progress_cb is None:
            return
        try:
            res = self._progress_cb(sp, stage, message)
            if inspect.isawaitable(res):
                await res
        except Exception as e:
            logger.warning(f"进度回调执行异常: {e}")

    async def _emit_page(self, sp, items, page_num, total_pages):
        if self._page_cb is None or not items:
            return
        res = self._page_cb(sp, items, page_num, total_pages)
        if inspect.isawaitable(res):
            await res

    async def _emit_detail(self, sp, items):
        if self._detail_cb is None or not items:
            return
        res = self._detail_cb(sp, items)
        if inspect.isawaitable(res):
            await res

    async def _check_should_stop(self):
        if self._should_stop_cb is None:
            return False
        try:
            res = self._should_stop_cb()
            if inspect.isawaitable(res):
                return bool(await res)
            return bool(res)
        except Exception as e:
            logger.warning(f"停止检查回调异常: {e}")
            return False

    @property
    def rate_lock(self):
        """惰性绑定当前事件循环的异步锁，用于请求控频消峰"""
        if self._rate_lock is None:
            self._rate_lock = asyncio.Lock()
        return self._rate_lock

    async def _acquire_rate_slot(self, is_proxied=False, exit_id=None):
        """按物理出口 IP 隔离限流槽：无论直连还是单个备机，同一物理出口均强制 2.6s~3.2s 安全间隔。"""
        eff_exit = exit_id or ("__legacy_proxy__" if is_proxied else DIRECT_EXIT_ID)
        await self.proxy_router.acquire_rate_slot(eff_exit, interval_range=(2.6, 3.2))
        self._last_req_ts = time.time()

    def _detail_waf_open(self):
        """详情熔断是否处于开启态（冷却期内跳过详情补全）"""
        return (time.time() - self._detail_waf_block_ts) < self.detail_waf_cooldown

    def _detail_waf_trip(self, scene="详情获取"):
        first_trip = not self._detail_waf_open()
        self._detail_waf_block_ts = time.time()
        if first_trip:
            logger.warning(
                f"{scene}触发限流或创宇盾拦截，启动详情降级：跳过后续详情请求，冷却 {self.detail_waf_cooldown}s"
            )

    def _extract_proxy_ip(self, proxy):
        """从代理连接串中提取 IP 或主机名标识"""
        if not proxy or not isinstance(proxy, str):
            return None
        m = re.search(r'@?([0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)', proxy)
        if m:
            return m.group(1)
        m_domain = re.search(r'://([^:/]+)', proxy)
        if m_domain:
            return m_domain.group(1)
        return proxy.strip()

    def _extract_waf_blocked_ip(self, text):
        """从创宇盾/WAF拦截报文中提取真实被封禁的客户端IP"""
        if not text or not isinstance(text, str):
            return None
        match = re.search(r'["\']client_ip["\']\s*:\s*["\']([^"\']+)["\']', text)
        if match:
            return match.group(1).strip()
        return None

    def _resolve_proxy(self, proxy=None):
        """
        统一解析出口代理：
        1. 若挂接了多域结构化策略且开启代理模式，优先从健康候选中选取首个出口（直连时返回 None）；
        2. 显式指定的非空代理优先；
        3. 其次读取隧道代理配置 (config.proxy.tunnel.url)；
        4. 再次从 API 代理池缓存 (pool_cache) 中轮询未被拦截的可用代理；
        5. 兜底返回空（直连模式）。
        """
        if proxy and isinstance(proxy, str) and proxy.strip():
            p = normalize_proxy_url(proxy)
            pip = self._extract_proxy_ip(p)
            if not self._is_ip_blocked(pip):
                return p

        if getattr(self, "proxy_router", None) is not None and self.proxy_router.has_structured_policy:
            cands = self.proxy_router.get_candidates()
            if cands:
                return cands[0].proxy_url

        # 尝试隧道代理
        tunnel_url = getattr(getattr(getattr(config, "proxy", object()), "tunnel", object()), "url", None)
        if tunnel_url and isinstance(tunnel_url, str) and tunnel_url.strip():
            t_url = normalize_proxy_url(tunnel_url)
            tip = self._extract_proxy_ip(t_url)
            if not self._is_ip_blocked(tip):
                return t_url

        # 尝试 API 代理池
        try:
            from proxy_pool import pool_cache
            candidates = [p for p in pool_cache.keys() if not self._is_ip_blocked(self._extract_proxy_ip(p))]
            if candidates:
                chosen = normalize_proxy_url(random.choice(candidates))
                return chosen
        except Exception:
            pass

        return None

    def _has_healthy_proxy(self):
        """检查当前是否有健康的代理节点可用"""
        if getattr(self, "proxy_router", None) is not None and self.proxy_router.has_structured_policy:
            if self.proxy_router.has_healthy_backup_proxy():
                return True
        resolved = self._resolve_proxy(None)
        return bool(resolved)

    def _is_global_waf_blocked(self):
        """仅当发生 WAF 封禁且当前无任何健康出口可用时，判定为全局熔断"""
        if getattr(self, "proxy_router", None) is not None and self.proxy_router.has_structured_policy:
            if self.proxy_router.get_mode() != "direct_only":
                return self.proxy_router.is_all_exits_blocked()
            return self.proxy_router.is_exit_blocked(DIRECT_EXIT_ID) or (
                self._waf_open() and not self._has_healthy_proxy()
            )
        return self._waf_open() and not self._has_healthy_proxy()

    def get_earliest_unblock_delay(self):
        """计算全局冷却期下最近一个允许出口的剩余冷却秒数"""
        if getattr(self, "proxy_router", None) is not None and self.proxy_router.has_structured_policy:
            delay = self.proxy_router.earliest_unblock_delay()
            if delay > 0:
                return delay
        if self._waf_open() and not self._has_healthy_proxy():
            return max(0.0, float(self._waf_block_ts) + float(self.waf_cooldown) - time.time())
        return 0.0

    def _get_jsluid_cookie(self, proxy=None):
        """获取有效的加速乐/创宇盾 Cookie 标识"""
        if getattr(self, "_cached_jsluid", None):
            return self._cached_jsluid
        return uuid.uuid4().hex

    @property
    def token_lock(self):
        """惰性绑定当前事件循环的异步锁，用于 Token 续期 DCL"""
        if self._token_lock is None:
            self._token_lock = asyncio.Lock()
        return self._token_lock

    def _waf_open(self):
        """熔断是否处于开启态（冷却期内不再发起详情请求）"""
        return (time.time() - self._waf_block_ts) < self.waf_cooldown

    def _waf_trip(self, scene):
        """开启熔断，仅在首次触发时打印告警，避免批内刷屏"""
        first_trip = not self._waf_open()
        self._waf_block_ts = time.time()
        if first_trip:
            logger.warning(
                f"{scene}触发创宇盾拦截，启动熔断降级：跳过后续详情请求，冷却 {self.waf_cooldown}s"
            )

    # 业务层限流文案（非创宇盾 HTML 拦截页，而是 MIIT 接口返回的 JSON 业务码）：
    # 命中同样开启 WAF 熔断，避免深穿透下换主体继续撞限流
    RATE_LIMIT_HINTS = ("频次过高", "访问频繁", "稍后再试", "请求过快", "操作频繁")

    def _is_rate_limited(self, text):
        """判定响应是否为 MIIT 业务层限流"""
        if not text or not isinstance(text, str):
            return False
        return any(h in text for h in self.RATE_LIMIT_HINTS)

    def _session_local_ip(self, session):
        """
        取回本次会话实际绑定的出口地址。
        优先读 get_session 打上的 _arl_local_ip 标记，不依赖 aiohttp 私有属性；
        仅在标记缺失时按版本回退探测（3.9 的 _local_addr / 3.12+ 的 _local_addr_infos）。
        """
        connector = getattr(session, "_connector", None)
        if connector is None:
            return None
        ip = getattr(connector, "_arl_local_ip", None)
        if ip:
            return ip
        addr = getattr(connector, "_local_addr", None) or getattr(connector, "_local_addr_infos", None)
        try:
            if isinstance(addr, (list, tuple)) and addr:
                first = addr[0]
                if isinstance(first, (list, tuple)) and first:
                    return first[-1][0]
                if isinstance(first, str):
                    return first
        except (IndexError, KeyError, TypeError, AttributeError):
            return None
        return None


    def _add_blocked_ip(self, ip):
        """将IP添加到黑名单缓存"""
        if not ip:
            return
        with self._blocked_ip_lock:
            self._blocked_ip_cache[ip] = True
            logger.info(f"IP {ip} 被创宇盾拦截已添加到黑名单缓存，5分钟后恢复使用")

    def _is_ip_blocked(self, ip):
        """检查IP是否在黑名单缓存中"""
        if not ip:
            return False
        with self._blocked_ip_lock:
            return ip in self._blocked_ip_cache
        
    def _get_next_ipv6(self):
        """线程安全的IPv6轮询，跳过被拦截的IP"""
        if not self.local_ipv6_addresses:
            return None
        
        with self._ipv6_lock:
            attempts = 0
            max_attempts = len(self.local_ipv6_addresses) * 2  # 最多尝试两轮
            
            while attempts < max_attempts:
                if self.ipv6_index >= len(self.local_ipv6_addresses):
                    self.ipv6_index = 0
                
                ipv6 = self.local_ipv6_addresses[self.ipv6_index]
                self.ipv6_index += 1
                attempts += 1
                
                # 检查IP是否被拦截
                if not self._is_ip_blocked(ipv6):
                    return ipv6
                else:
                    logger.debug(f"跳过被拦截的IPv6地址: {ipv6}")
            
            logger.warning("所有IPv6地址都被拦截，暂无可用地址")
            return None

    async def _get_connector(self, local_ipv6=None):
        if local_ipv6:
            connector = TCPConnector(
                local_addr=(local_ipv6, 0),
                **self.connector_config
            )
        else:
            connector = TCPConnector(**self.connector_config)
        
        return connector

    @asynccontextmanager
    async def get_session(self, proxy="", direct_override=False):
        resolved_proxy = None if direct_override else self._resolve_proxy(proxy)
        local_ipv6 = None
        if not resolved_proxy and self.local_ipv6_addresses:
            local_ipv6 = self._get_next_ipv6()
            if local_ipv6:
                logger.info(f"使用本地IPv6地址: {local_ipv6}")

        connector, req_proxy = build_aiohttp_connector(
            resolved_proxy,
            local_ipv6=local_ipv6,
            connector_config=self.connector_config,
        )
        session = aiohttp.ClientSession(
            timeout=self.timeout,
            connector=connector,
            headers={'Connection': 'keep-alive'}
        )
        # aiohttp HTTP/HTTPS 代理通过 session.request(proxy=...) 走通道；SOCKS5 由 ProxyConnector 托管故置 None
        session._arl_proxy = req_proxy
        session._arl_proxy_url = resolved_proxy

        try:
            yield session
        finally:
            await session.close()
            await connector.close()

    def _iter_attempt_exits(self, explicit_proxy=""):
        """返回本次请求可按序尝试的出口候选列表。"""
        if getattr(self, "proxy_router", None) is not None and self.proxy_router.has_structured_policy:
            cands = self.proxy_router.get_candidates()
            if cands:
                return cands
            return []
        resolved = self._resolve_proxy(explicit_proxy)
        if resolved:
            ip_val = self._extract_proxy_ip(resolved) or resolved
            return [ExitCandidate(
                exit_id=f"explicit:{ip_val}",
                name=mask_proxy_url_secret(resolved),
                proxy_url=resolved,
                ip=ip_val,
            )]
        return [ExitCandidate(exit_id=DIRECT_EXIT_ID, name="主服务器直连", proxy_url=None, ip="")]

    async def _handle_exit_failure(self, cand, *, blocked_ip=None, reason="", cooldown_sec=None, next_cand=None, scene="MIIT查询"):
        eff_cd = cooldown_sec or (self.proxy_router.get_cooldown_sec() if getattr(self, "proxy_router", None) else self.waf_cooldown)
        if getattr(self, "proxy_router", None) is not None:
            self.proxy_router.mark_exit_blocked(
                cand.exit_id,
                reason=reason,
                ip=blocked_ip or cand.ip or "",
                cooldown_sec=eff_cd,
            )
            await self.proxy_router.persist_runtime_status()
        if cand.proxy_url:
            if blocked_ip:
                self._add_blocked_ip(blocked_ip)
            elif cand.ip:
                self._add_blocked_ip(cand.ip)
        elif blocked_ip:
            self._add_blocked_ip(blocked_ip)

        # 切换物理出口后需重置绑定 IP 的 Token / Cookie 上下文
        self.token = ""
        self.token_expire = 0
        self._cached_jsluid = None

        if next_cand is not None:
            msg = f"出口 [{cand.name}] 在{scene}时{reason}，已隔离 {eff_cd}s 并立即切换至 [{next_cand.name}] 重试"
            logger.warning(msg)
            await self.proxy_router.emit_syslog("warning", "出口故障切换", msg)
        else:
            msg = f"出口 [{cand.name}] 在{scene}时{reason}，已冷却 {eff_cd}s（当前暂无其他健康备用出口）"
            logger.warning(msg)
            await self.proxy_router.emit_syslog("warning", "出口熔断", msg)

    async def _handle_exit_success(self, cand, *, switched_from_primary=False):
        if getattr(self, "proxy_router", None) is None:
            return
        prev = self.proxy_router.active_exit_id
        recover_msg = (
            "主服务器直连冷却结束，自动回切主服务器直连"
            if (prev != DIRECT_EXIT_ID and cand.exit_id == DIRECT_EXIT_ID)
            else f"切换至出口 [{cand.name}]"
        )
        self.proxy_router.mark_exit_active(cand.exit_id, reason=recover_msg)
        if prev != cand.exit_id:
            await self.proxy_router.persist_runtime_status()
            if prev != DIRECT_EXIT_ID and cand.exit_id == DIRECT_EXIT_ID:
                await self.proxy_router.emit_syslog("info", "出口自动回切", "主服务器直连冷却恢复，已自动回切为主出口执行查询")
            elif switched_from_primary and cand.exit_id != DIRECT_EXIT_ID:
                await self.proxy_router.emit_syslog("info", "备用节点接管", f"已使用备用代理节点 [{cand.name}] 成功完成本轮请求")

    def _open_candidate_session(self, cand):
        return self.get_session(
            proxy=(cand.proxy_url or ""),
            direct_override=(cand.proxy_url is None),
        )

    async def get_token(self, proxy="", force=False, exit_candidate=None, _raise_on_exit_err=False):
        if exit_candidate is not None:
            cand = exit_candidate
        else:
            cands = self._iter_attempt_exits(proxy)
            cand = cands[0] if cands else ExitCandidate(exit_id=DIRECT_EXIT_ID, name="主服务器直连", proxy_url=None, ip="")

        base_header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Origin": "https://beian.miit.gov.cn",
            "Referer": "https://beian.miit.gov.cn/",
            "Sec-Ch-Ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Cookie": f"__jsluid_s={self._get_jsluid_cookie(cand.proxy_url)}",
        }

        now_ms = int(time.time() * 1000)
        if not force and (self.token_expire - now_ms > 60000):
            return True, self.token, base_header

        if not hasattr(self, '_token_async_lock'):
            self._token_async_lock = asyncio.Lock()

        async with self._token_async_lock:
            now_ms = int(time.time() * 1000)
            if not force and (self.token_expire - now_ms > 60000):
                return True, self.token, base_header

            timeStamp = round(time.time() * 1000)
            authSecret = "testtest" + str(timeStamp)
            authKey = hashlib.md5(authSecret.encode(encoding="UTF-8")).hexdigest()
            auth_data = {"authKey": authKey, "timeStamp": timeStamp}

            try:
                async with self._open_candidate_session(cand) as session:
                    actual_proxy = getattr(session, "_arl_proxy", None)
                    await self._acquire_rate_slot(is_proxied=bool(cand.proxy_url), exit_id=cand.exit_id)
                    current_ip = self._session_local_ip(session)
                    async with session.post(self.url, data=auth_data, headers=base_header, proxy=actual_proxy) as req:
                        req_text = await req.text()
                        req_status = req.status
            except Exception as e:
                logger.warning(f"get_token Faile : {e}")
                if _raise_on_exit_err:
                    raise _ExitAttemptError("transport_error", f"连接/网络异常 ({type(e).__name__})", cooldown_sec=60) from e
                return False, str(e), ""

            if "当前访问疑似黑客攻击" in req_text or "已被创宇盾拦截" in req_text or req_status == 403 or (isinstance(req_text, str) and "error_403_type" in req_text):
                blocked_ip = self._extract_waf_blocked_ip(req_text) or current_ip or self._extract_proxy_ip(cand.proxy_url)
                if _raise_on_exit_err:
                    raise _ExitAttemptError("waf_blocked", "触发创宇盾拦截 (HTTP 403)", blocked_ip=blocked_ip)
                if blocked_ip:
                    self._add_blocked_ip(blocked_ip)
                self._waf_trip("Token获取")
                return False, "当前访问已被创宇盾拦截", ""

            try:
                t = ujson.loads(req_text)
                token = t["params"]["bussiness"]
                expire = int(time.time() * 1000) + t["params"]["expire"]
                self.token = token
                self.token_expire = expire
                return True, token, base_header
            except Exception as e:
                logger.warning(f"get_token parse failed: {e}")
                return False, str(e), ""

    async def get_cookie(self, proxy=""):
        resolved_proxy = self._resolve_proxy(proxy)
        try:
            async with self.get_session(resolved_proxy) as session:
                actual_proxy = getattr(session, "_arl_proxy", resolved_proxy)
                await self._acquire_rate_slot(is_proxied=bool(actual_proxy))
                async with session.get(self.home, headers=self.cookie_headers, proxy=actual_proxy) as req:
                    await req.text()
                    matched = re.compile(r"[0-9a-z]{32}").search(str(req.cookies))
                    if matched:
                        c_val = matched[0]
                        self._cached_jsluid = c_val
                        return c_val
        except Exception as e:
            logger.debug(f"get_cookie failed: {e}")
        return uuid.uuid4().hex

    def get_clientUid(self):
        characters = "0123456789abcdef"
        unique_id = ["0"] * 36

        for i in range(36):
            unique_id[i] = random.choice(characters)

        unique_id[14] = "4"
        unique_id[19] = characters[(3 & int(unique_id[19], 16)) | 8]
        unique_id[8] = unique_id[13] = unique_id[18] = unique_id[23] = "-"

        point_id = "point-" + "".join(unique_id)

        return ujson.dumps({"clientUid": point_id})

    def match_slider_offset(self, small_image_b64, big_image_b64):
        """在大图上找与滑块同尺寸的纯色正方形缺口区域，返回其 x 偏移量"""
        big_img = np.array(Image.open(io.BytesIO(base64.b64decode(big_image_b64))).convert("RGB"))
        small_img = np.array(Image.open(io.BytesIO(base64.b64decode(small_image_b64))))
        sh, sw = small_img.shape[:2]

        # 缩小到一半
        resized = big_img[::2, ::2]
        h, w = resized.shape[:2]
        min_side = int(min(sw, sh) * 0.5 * 0.5)

        # 量化颜色，编码为单通道整数
        q = (resized.astype(np.int32) // 4) * 4
        color_id = q[:, :, 0] + q[:, :, 1] * 256 + q[:, :, 2] * 65536

        # 找出现次数最多的几个颜色（缺口灰色通常是高频色之一）
        flat_colors = color_id.ravel()
        unique, counts = np.unique(flat_colors, return_counts=True)
        # 只检查出现次数前 5 的颜色
        top_indices = np.argsort(counts)[-5:]

        best_area = 0
        best_x = 0

        for idx in top_indices:
            c = unique[idx]
            mask = color_id == c
            # 对每行求该颜色的连续像素数，利用列方向累积
            # 列投影：每列有多少连续行是该颜色
            col_run = np.zeros((h, w), dtype=np.int32)
            col_run[0] = mask[0].astype(np.int32)
            for y in range(1, h):
                col_run[y] = np.where(mask[y], col_run[y - 1] + 1, 0)

            # 对每行找符合高度条件的列段的最大宽度
            for y in range(min_side, h):
                row = col_run[y] >= min_side
                if not np.any(row):
                    continue
                # 找连续 True 段
                d = np.diff(row.astype(np.int8))
                starts = np.where(d == 1)[0] + 1
                ends = np.where(d == -1)[0] + 1
                if row[0]:
                    starts = np.concatenate([[0], starts])
                if row[-1]:
                    ends = np.concatenate([ends, [w]])
                for s, e in zip(starts, ends):
                    run_w = e - s
                    if s <= sw // 4:
                        continue
                    run_h = int(col_run[y, s])
                    ratio = run_w / run_h if run_h > 0 else 0
                    if 0.7 < ratio < 1.4 and run_w * run_h > best_area:
                        best_area = run_w * run_h
                        best_x = s

        if best_area == 0:
            return False, "未找到缺口"

        offset_x = best_x * 2
        logger.info(f"缺口定位: x={offset_x}, 滑块={sw}x{sh}")
        return True, offset_x

    async def check_img(self, proxy="", exit_candidate=None, force_token=False, _raise_on_exit_err=False):
        if exit_candidate is not None:
            cand = exit_candidate
        else:
            cands = self._iter_attempt_exits(proxy)
            cand = cands[0] if cands else ExitCandidate(exit_id=DIRECT_EXIT_ID, name="主服务器直连", proxy_url=None, ip="")

        success, token, base_header = await self.get_token(
            proxy,
            force=force_token,
            exit_candidate=cand,
            _raise_on_exit_err=_raise_on_exit_err,
        )
        if not success:
            logger.info(f"获取token失败：{token}")
            return False, token, '', '', ''
        try:
            data = self.get_clientUid()
            length = str(len(str(data).encode("utf-8")))
            base_header.update({"Content-Length": length, "token": token})
            base_header["Content-Type"] = "application/json"
            try:
                async with self._open_candidate_session(cand) as session:
                    actual_proxy = getattr(session, "_arl_proxy", None)
                    await self._acquire_rate_slot(is_proxied=bool(cand.proxy_url), exit_id=cand.exit_id)
                    current_ip = self._session_local_ip(session)
                    async with session.post(self.getCheckImage, data=data, headers=base_header, proxy=actual_proxy) as req:
                        res_text = await req.text()
                        if "当前访问疑似黑客攻击" in res_text or "已被创宇盾拦截" in res_text or req.status == 403 or (isinstance(res_text, str) and "error_403_type" in res_text):
                            blocked_ip = self._extract_waf_blocked_ip(res_text) or current_ip or self._extract_proxy_ip(cand.proxy_url)
                            if _raise_on_exit_err:
                                raise _ExitAttemptError("waf_blocked", "验证码获取触发创宇盾拦截 (HTTP 403)", blocked_ip=blocked_ip)
                            if blocked_ip:
                                self._add_blocked_ip(blocked_ip)
                            self._waf_trip("验证码获取")
                            return False, "当前访问已被创宇盾拦截", '', '', ''
                        res = ujson.loads(res_text)
            except _ExitAttemptError:
                raise
            except Exception as e:
                logger.info(f"请求验证码时失败：{e}")
                if _raise_on_exit_err:
                    raise _ExitAttemptError("transport_error", f"验证码连接异常 ({type(e).__name__})", cooldown_sec=60) from e
                return False, f"请求验证码时失败：{e}", '', '', ''

            p_uuid = res["params"]["uuid"]
            big_image = res["params"]["bigImage"]
            small_image = res["params"]["smallImage"]

            start = time.time()
            match_success, offset_x = self.match_slider_offset(small_image, big_image)
            if not match_success:
                logger.info(f"滑块匹配失败：{offset_x}")
                return False, "滑块匹配失败", '', '', ''
            logger.info(f"滑块匹配用时 {time.time() - start:.4f}s")

            check_data = ujson.dumps({"key": p_uuid, "value": str(offset_x)})
            logger.info(f"checkImage 请求体: {check_data}")
            length = str(len(check_data.encode("utf-8")))
            base_header.update({"Content-Length": length})
            try:
                async with self._open_candidate_session(cand) as session:
                    actual_proxy = getattr(session, "_arl_proxy", None)
                    await self._acquire_rate_slot(is_proxied=bool(cand.proxy_url), exit_id=cand.exit_id)
                    current_ip = self._session_local_ip(session)
                    async with session.post(self.checkImage, data=check_data, headers=base_header, proxy=actual_proxy) as req:
                        res = await req.text()
                        req_status = req.status
            except Exception as e:
                if _raise_on_exit_err:
                    raise _ExitAttemptError("transport_error", f"验证码校验网络异常 ({type(e).__name__})", cooldown_sec=60) from e
                raise

            if "当前访问疑似黑客攻击" in res or "已被创宇盾拦截" in res or req_status == 403 or (isinstance(res, str) and "error_403_type" in res):
                blocked_ip = self._extract_waf_blocked_ip(res) or current_ip or self._extract_proxy_ip(cand.proxy_url)
                if _raise_on_exit_err:
                    raise _ExitAttemptError("waf_blocked", "验证码提交触发创宇盾拦截 (HTTP 403)", blocked_ip=blocked_ip)
                if blocked_ip:
                    self._add_blocked_ip(blocked_ip)
                self._waf_trip("验证码提交")
                return False, "当前访问已被创宇盾拦截", '', '', ''

            data = ujson.loads(res)
            logger.info(f"checkImage 响应: code={data.get('code')}, msg={data.get('msg')}, success={data.get('success')}")
            if not data.get("success", False):
                captcha_config = getattr(config, 'captcha', object())
                if getattr(captcha_config, 'save_failed_img', False):
                    save_path = getattr(captcha_config, 'save_failed_img_path', './failed_captcha')
                    for folder in [f'{save_path}/ibig', f'{save_path}/isma']:
                        os.makedirs(folder, exist_ok=True)
                    filename = f"{uuid.uuid4()}.jpg"
                    with open(f"{save_path}/isma/{filename}", "wb") as f:
                        f.write(base64.b64decode(small_image))
                    with open(f"{save_path}/ibig/{filename}", "wb") as f:
                        f.write(base64.b64decode(big_image))
                    logger.info(f"失败验证码已保存: {filename}")
                return False, "验证码识别失败", '', '', ''
            else:
                sign = data["params"]
                return True, p_uuid, token, sign, base_header

        except _ExitAttemptError:
            raise
        except Exception as e:
            logger.warning(f"check_image Faile : {e}")
            return False, str(e), '', '', ''

    async def getAppAndMiniDetail(self, dataId, serviceType, p_uuid, token, sign, base_header, proxy="", session=None):
        """优化的详情获取，支持多协议代理、每出口控频与故障切换"""
        info = {"dataId": dataId, "serviceType": serviceType}
        length = str(len(str(ujson.dumps(info, ensure_ascii=False)).encode("utf-8")))
        captcha_enabled = bool(getattr(getattr(config, 'captcha', object()), 'enable', False))

        def _make_detail_headers(cur_token, cur_header):
            dh = dict(cur_header)
            dh.update({"Content-Length": length, "uuid": p_uuid, "token": cur_token, "sign": sign})
            if not captcha_enabled:
                dh.pop("uuid", None)
                dh.pop("Content-Length", None)
            return dh

        if session:
            detail_header = _make_detail_headers(token, base_header)
            current_ip = self._session_local_ip(session)
            actual_proxy = getattr(session, "_arl_proxy", None)
            proxy_url_used = getattr(session, "_arl_proxy_url", actual_proxy)
            await self._acquire_rate_slot(is_proxied=bool(proxy_url_used))
            if captcha_enabled:
                async with session.post(self.queryDetailByAppAndMiniId,
                                        data=ujson.dumps(info, ensure_ascii=False),
                                        headers=detail_header,
                                        proxy=actual_proxy) as req:
                    res = await req.text()
            else:
                async with session.post(f"{self.queryDetailByAppAndMiniId}",
                                        json=info,
                                        headers=detail_header,
                                        proxy=actual_proxy) as req:
                    res = await req.text()
            if "当前访问疑似黑客攻击" in res or "已被创宇盾拦截" in res or (isinstance(res, str) and "error_403_type" in res):
                blocked_ip = self._extract_waf_blocked_ip(res) or current_ip or self._extract_proxy_ip(proxy_url_used)
                if blocked_ip:
                    self._add_blocked_ip(blocked_ip)
                self._detail_waf_trip("详情获取")
                return False, {"code": 403, "msg": "当前访问已被创宇盾拦截", "success": False}
            try:
                parsed_res = ujson.loads(res)
                _msg = str(parsed_res.get("msg") or parsed_res.get("message") or "")
                if self._is_rate_limited(_msg):
                    self._detail_waf_trip("详情获取(业务限流)")
                    return False, {"code": 429, "msg": f"业务限流: {_msg}", "success": False}
                return True, parsed_res
            except Exception as e:
                return False, {"code": 500, "msg": f"解析异常: {e}", "success": False}

        candidates = self._iter_attempt_exits(proxy)
        if not candidates:
            self._detail_waf_trip("详情获取")
            return False, {"code": 403, "msg": "当前所有出口均处于冷却状态", "success": False}

        cur_token = token
        cur_header = base_header
        last_err = {"code": 500, "msg": "详情获取失败", "success": False}
        for idx, cand in enumerate(candidates):
            next_cand = candidates[idx + 1] if (idx + 1 < len(candidates)) else None
            if idx > 0 and not captcha_enabled:
                tok_ok, new_tok, new_hdr = await self.get_token(proxy, force=True, exit_candidate=cand)
                if tok_ok:
                    cur_token = new_tok
                    cur_header = new_hdr
            detail_header = _make_detail_headers(cur_token, cur_header)
            try:
                async with self._open_candidate_session(cand) as sess:
                    actual_proxy = getattr(sess, "_arl_proxy", None)
                    await self._acquire_rate_slot(is_proxied=bool(cand.proxy_url), exit_id=cand.exit_id)
                    current_ip = self._session_local_ip(sess)
                    if captcha_enabled:
                        async with sess.post(self.queryDetailByAppAndMiniId,
                                             data=ujson.dumps(info, ensure_ascii=False),
                                             headers=detail_header,
                                             proxy=actual_proxy) as req:
                            res = await req.text()
                            req_status = req.status
                    else:
                        async with sess.post(f"{self.queryDetailByAppAndMiniId}",
                                             json=info,
                                             headers=detail_header,
                                             proxy=actual_proxy) as req:
                            res = await req.text()
                            req_status = req.status
            except Exception as exc:
                await self._handle_exit_failure(
                    cand,
                    reason=f"详情网络异常 ({type(exc).__name__})",
                    cooldown_sec=60,
                    next_cand=next_cand,
                    scene="详情补全",
                )
                last_err = {"code": 500, "msg": f"详情请求异常: {exc}", "success": False}
                if next_cand is not None:
                    continue
                return False, last_err

            if "当前访问疑似黑客攻击" in res or "已被创宇盾拦截" in res or req_status == 403 or (isinstance(res, str) and "error_403_type" in res):
                blocked_ip = self._extract_waf_blocked_ip(res) or current_ip or self._extract_proxy_ip(cand.proxy_url)
                await self._handle_exit_failure(
                    cand,
                    blocked_ip=blocked_ip,
                    reason="触发创宇盾拦截 (HTTP 403)",
                    next_cand=next_cand,
                    scene="详情补全",
                )
                last_err = {"code": 403, "msg": "当前访问已被创宇盾拦截", "success": False}
                if next_cand is not None:
                    continue
                self._detail_waf_trip("详情获取")
                return False, last_err

            try:
                parsed_res = ujson.loads(res)
                _msg = str(parsed_res.get("msg") or parsed_res.get("message") or "")
                if self._is_rate_limited(_msg):
                    await self._handle_exit_failure(
                        cand,
                        reason=f"触发业务限流 ({_msg[:60]})",
                        next_cand=next_cand,
                        scene="详情补全",
                    )
                    last_err = {"code": 429, "msg": f"业务限流: {_msg}", "success": False}
                    if next_cand is not None:
                        continue
                    self._detail_waf_trip("详情获取(业务限流)")
                    return False, last_err
                await self._handle_exit_success(cand, switched_from_primary=(idx > 0))
                return True, parsed_res
            except Exception as e:
                logger.warning(f"解析详情响应失败: {e}, 响应文本截断: {res[:100]}")
                return False, {"code": 500, "msg": f"解析异常: {e}", "success": False}

        return False, last_err

    def _is_auto_pagination(self, pageNum, pageSize):
        """未显式传分页参数时，默认拉取全部页。"""
        return pageNum in (None, "") and pageSize in (None, "")

    def _get_total_pages(self, result, page_size):
        params = result.get("params", {}) if isinstance(result, dict) else {}
        pages = params.get("pages") or params.get("lastPage")
        if pages:
            try:
                return max(int(pages), 1)
            except (TypeError, ValueError):
                pass

        total = params.get("total")
        try:
            total = int(total)
            return max((total + page_size - 1) // page_size, 1)
        except (TypeError, ValueError):
            return 1

    async def _query_beian_page_once(self, name, sp, pageNum, pageSize, cand, force_token=False):
        info = ujson.loads(self.typj.get(sp))
        info["pageNum"] = pageNum
        info["pageSize"] = pageSize
        info["unitName"] = name
        current_ip = None

        if getattr(getattr(config, 'captcha', object()), 'enable', False):
            success, p_uuid, token, sign, base_header = await self.check_img(
                cand.proxy_url or "",
                exit_candidate=cand,
                force_token=force_token,
                _raise_on_exit_err=True,
            )
            if not success:
                logger.info(f"打码失败：{p_uuid}")
                return False, p_uuid, None

            length = str(len(str(ujson.dumps(info, ensure_ascii=False)).encode("utf-8")))
            base_header.update({"Content-Length": length, "uuid": p_uuid, "token": token, "sign": sign})

            try:
                async with self._open_candidate_session(cand) as session:
                    actual_proxy = getattr(session, "_arl_proxy", None)
                    await self._acquire_rate_slot(is_proxied=bool(cand.proxy_url), exit_id=cand.exit_id)
                    current_ip = self._session_local_ip(session)
                    async with session.post(self.queryByCondition,
                                            data=ujson.dumps(info, ensure_ascii=False),
                                            headers=base_header,
                                            proxy=actual_proxy) as req:
                        res = await req.text()
                        req_status = req.status
            except Exception as e:
                raise _ExitAttemptError("transport_error", f"列表连接异常 ({type(e).__name__})", cooldown_sec=60) from e
        else:
            success, token, base_header = await self.get_token(
                cand.proxy_url or "",
                force=force_token,
                exit_candidate=cand,
                _raise_on_exit_err=True,
            )
            sign = ""
            p_uuid = ""
            if not success:
                logger.info("获取token失败")
                return False, None, None
            base_header.update({"token": token, "sign": self.sign})

            try:
                async with self._open_candidate_session(cand) as session:
                    actual_proxy = getattr(session, "_arl_proxy", None)
                    await self._acquire_rate_slot(is_proxied=bool(cand.proxy_url), exit_id=cand.exit_id)
                    current_ip = self._session_local_ip(session)
                    async with session.post(f"{self.queryByCondition}/",
                                            json=info,
                                            headers=base_header,
                                            proxy=actual_proxy) as req:
                        res = await req.text()
                        req_status = req.status
            except Exception as e:
                raise _ExitAttemptError("transport_error", f"列表连接异常 ({type(e).__name__})", cooldown_sec=60) from e

        if "当前访问疑似黑客攻击" in res or "已被创宇盾拦截" in res or req_status == 403 or (isinstance(res, str) and "error_403_type" in res):
            blocked_ip = self._extract_waf_blocked_ip(res) or current_ip or self._extract_proxy_ip(cand.proxy_url)
            raise _ExitAttemptError("waf_blocked", "触发创宇盾拦截 (HTTP 403)", blocked_ip=blocked_ip)

        try:
            result = ujson.loads(res)
        except Exception as e:
            snippet = (res or "")[:120].replace("\n", " ")
            logger.warning(f"列表查询响应解析失败: {e}, 响应片段: {snippet}")
            return False, f"列表查询响应解析失败: {e}", None

        _msg = ""
        if isinstance(result, dict):
            _msg = str(result.get("msg") or result.get("message") or "")
        if self._is_rate_limited(_msg):
            raise _ExitAttemptError("rate_limited", f"MIIT业务限流 ({_msg[:80]})")

        detail_context = {
            "p_uuid": p_uuid,
            "token": token,
            "sign": sign if getattr(getattr(config, 'captcha', object()), 'enable', False) else self.sign,
            "base_header": base_header,
        }
        return True, result, detail_context

    async def _query_beian_page(self, name, sp, pageNum, pageSize, proxy=""):
        # 全局 WAF 熔断检查：当所有允许出口均处于冷却时直接短路返回，交由外层执行单次等待
        if self._is_global_waf_blocked():
            return False, "当前访问已被创宇盾拦截", None

        candidates = self._iter_attempt_exits(proxy)
        if not candidates:
            return False, "当前所有出口均处于冷却状态", None

        last_err = "当前访问已被创宇盾拦截"
        for idx, cand in enumerate(candidates):
            next_cand = candidates[idx + 1] if (idx + 1 < len(candidates)) else None
            try:
                ok, payload, detail_ctx = await self._query_beian_page_once(
                    name, sp, pageNum, pageSize, cand, force_token=(idx > 0)
                )
                if ok:
                    await self._handle_exit_success(cand, switched_from_primary=(idx > 0))
                    return True, payload, detail_ctx
                return False, payload, detail_ctx
            except _ExitAttemptError as err:
                await self._handle_exit_failure(
                    cand,
                    blocked_ip=err.blocked_ip,
                    reason=err.reason,
                    cooldown_sec=err.cooldown_sec,
                    next_cand=next_cand,
                    scene="列表查询",
                )
                last_err = "当前访问已被创宇盾拦截" if err.kind == "waf_blocked" else err.reason
                if next_cand is not None:
                    continue
                if err.kind in ("waf_blocked", "rate_limited") and self._is_global_waf_blocked():
                    self._waf_trip("列表查询")
                return False, last_err, None

        return False, last_err, None

    async def _enrich_app_details(self, result, sp, detail_context, proxy, target_name=""):
        """为APP/小程序/快应用结果补充详情（支持跳过已知、上限截断、令牌单次自愈与连续失败熔断）"""
        if (sp in (1, 2, 3)
            and result.get("success")
            and result.get("params", {}).get("list")):

            items = result["params"]["list"]
            if not items:
                return result

            detail_context = detail_context or {}

            # 先筛除无 dataId、已自带名称、或调用方判定已命中的条目
            candidate_indices = []
            skipped_known = 0
            for idx, item in enumerate(items):
                if not item.get("dataId"):
                    continue
                if str(item.get("serviceName") or "").strip():
                    skipped_known += 1
                    continue
                if self._skip_detail_fn is not None:
                    try:
                        if self._skip_detail_fn(sp, item):
                            skipped_known += 1
                            continue
                    except Exception as e:
                        logger.warning(f"跳过已知详情判定异常: {e}")
                candidate_indices.append(idx)

            max_items = self._get_system_int_config("detail_max_items", 100)
            if max_items > 0 and len(candidate_indices) > max_items:
                skipped_cap = len(candidate_indices) - max_items
                target_indices = candidate_indices[:max_items]
            else:
                skipped_cap = 0
                target_indices = candidate_indices

            result["params"]["_detail_skipped_known"] = skipped_known
            result["params"]["_detail_skipped_cap"] = skipped_cap
            result["params"]["_detail_target_count"] = len(target_indices)

            if not target_indices:
                if skipped_known or skipped_cap:
                    logger.info(
                        f"详情补全无需发起远程查询 (跳过已知: {skipped_known}, 上限截断: {skipped_cap})"
                    )
                return result

            # 详情熔断检查：若处于详情冷却中，直接返回基础列表资产，不阻塞整体流程
            if self._detail_waf_open():
                result["params"]["_detail_missing"] = len(candidate_indices)
                result["params"]["_detail_waf"] = True
                result["params"]["_detail_circuit_break"] = True
                logger.info(f"当前处于详情熔断冷却期，跳过 {len(target_indices)} 条条目详情补全，保留基础列表数据")
                return result

            max_concurrency = min(
                self._get_system_int_config("detail_concurrency", 2),
                len(target_indices),
                2,
            )
            max_concurrency = max(1, max_concurrency)
            sem = asyncio.Semaphore(max_concurrency)
            context_lock = asyncio.Lock()
            captcha_enabled = bool(getattr(getattr(config, 'captcha', object()), 'enable', False))
            stats = {"enriched": 0}
            state = {
                "consecutive_failures": 0,
                "refresh_used_in_streak": False,
                "circuit_broken": False,
            }

            async def ensure_token_valid():
                if captcha_enabled:
                    return
                now_ms = int(time.time() * 1000)
                if self.token_expire - now_ms >= 60000:
                    return
                async with self.token_lock:
                    now_ms = int(time.time() * 1000)
                    if self.token_expire - now_ms >= 60000:
                        detail_context["token"] = self.token
                        return
                    try:
                        logger.info("ICP Token 即将过期，正在自动刷新 Token...")
                        tok_ok, new_tok, _ = await self.get_token(proxy)
                        if tok_ok:
                            detail_context["token"] = new_tok
                            logger.info("ICP Token 自动刷新成功")
                    except Exception as e:
                        logger.warning(f"刷新 Token 异常: {e}")

            def _is_waf_failure(d_data):
                return self._detail_waf_open() or (
                    isinstance(d_data, dict)
                    and (d_data.get("code") in (403, 429) or "已被创宇盾拦截" in str(d_data))
                )

            def _is_detail_ok(d_success, d_data):
                return bool(
                    d_success
                    and isinstance(d_data, dict)
                    and d_data.get("success")
                    and d_data.get("params")
                )

            async def _request_detail_once(item, serviceType):
                async with sem:
                    if self._detail_waf_open() or state["circuit_broken"]:
                        return False, {"code": 403, "msg": "详情熔断中", "success": False}
                    await ensure_token_valid()
                    return await self.getAppAndMiniDetail(
                        item["dataId"],
                        serviceType,
                        detail_context.get("p_uuid", ""),
                        detail_context.get("token", ""),
                        detail_context.get("sign", ""),
                        detail_context.get("base_header", {}),
                        proxy,
                    )

            async def fetch_detail(item):
                if self._detail_waf_open() or self._waf_open() or state["circuit_broken"] or "dataId" not in item:
                    return item, False

                serviceType = 6 if sp == 1 else (7 if sp == 2 else 8)
                try:
                    used_p_uuid = detail_context.get("p_uuid", "")
                    used_sign = detail_context.get("sign", "")
                    d_success, d_data = await _request_detail_once(item, serviceType)

                    if _is_detail_ok(d_success, d_data):
                        async with context_lock:
                            state["consecutive_failures"] = 0
                            state["refresh_used_in_streak"] = False
                        merged_item = item.copy()
                        merged_item.update(d_data["params"])
                        stats["enriched"] += 1
                        return merged_item, True

                    if _is_waf_failure(d_data):
                        if not self._detail_waf_open():
                            self._detail_waf_trip("详情获取")
                        return item, False

                    # 非 WAF 业务失败：打码模式下至多单次锁定刷新 (p_uuid, sign) 并重试一次
                    should_retry = False
                    if captcha_enabled and not await self._check_should_stop():
                        async with context_lock:
                            if detail_context.get("p_uuid", "") != used_p_uuid or detail_context.get("sign", "") != used_sign:
                                should_retry = True
                            elif not state["refresh_used_in_streak"]:
                                state["refresh_used_in_streak"] = True
                                ok, new_uuid, new_tok, new_sign, new_hdr = await self.check_img(proxy, force_token=True)
                                if ok:
                                    detail_context["p_uuid"] = new_uuid
                                    detail_context["token"] = new_tok
                                    detail_context["sign"] = new_sign
                                    detail_context["base_header"] = new_hdr
                                    should_retry = True

                    if should_retry and not self._detail_waf_open() and not self._waf_open() and not state["circuit_broken"]:
                        d_success, d_data = await _request_detail_once(item, serviceType)
                        if _is_detail_ok(d_success, d_data):
                            async with context_lock:
                                state["consecutive_failures"] = 0
                                state["refresh_used_in_streak"] = False
                            merged_item = item.copy()
                            merged_item.update(d_data["params"])
                            stats["enriched"] += 1
                            return merged_item, True
                        if _is_waf_failure(d_data):
                            if not self._detail_waf_open():
                                self._detail_waf_trip("详情获取")
                            return item, False

                    async with context_lock:
                        if not self._detail_waf_open():
                            state["consecutive_failures"] += 1
                            if state["consecutive_failures"] >= 5:
                                state["circuit_broken"] = True
                                self._detail_waf_trip("详情连续失败")
                    return item, False
                except Exception as e:
                    logger.error(f"详情获取异常 dataId={item.get('dataId')} err={e}")
                    async with context_lock:
                        if not self._detail_waf_open():
                            state["consecutive_failures"] += 1
                            if state["consecutive_failures"] >= 5:
                                state["circuit_broken"] = True
                                self._detail_waf_trip("详情连续异常")
                    return item, False

            sp_labels = {1: "移动APP", 2: "小程序", 3: "快应用"}
            sp_label = sp_labels.get(sp, "备案资产")
            target_prefix = f"主体【{target_name}】" if target_name else ""
            interval_sec = max(1, self._get_system_int_config("progress_log_interval_sec", 30))

            if len(target_indices) > 5:
                skip_notes = []
                if skipped_known > 0:
                    skip_notes.append(f"跳过已知名称 {skipped_known} 条")
                if skipped_cap > 0:
                    skip_notes.append(f"受单批上限截断跳过 {skipped_cap} 条")
                note_suffix = f"（{'，'.join(skip_notes)}）" if skip_notes else ""
                await self._emit_progress(
                    sp,
                    "detail",
                    f"正在补全{target_prefix}{sp_label}详情：待查询 {len(target_indices)} 条{note_suffix}",
                )

            detailed_list = list(items)
            batch_size = max_concurrency
            last_log_ts = time.monotonic()
            processed = 0

            for i in range(0, len(target_indices), batch_size):
                if await self._check_should_stop():
                    result["params"]["_stopped"] = True
                    logger.info(f"任务已中止，停止{sp_label}详情补全（已处理 {processed}/{len(target_indices)} 条）")
                    break

                if self._detail_waf_open() or self._waf_open() or state["circuit_broken"]:
                    state["circuit_broken"] = True
                    break

                batch_indices = target_indices[i:i + batch_size]
                tasks = [fetch_detail(items[idx]) for idx in batch_indices]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                batch_enriched = []
                for j, res in enumerate(batch_results):
                    orig_idx = batch_indices[j]
                    if isinstance(res, Exception):
                        logger.error(f"批次任务异常: {res}")
                    else:
                        updated_item, enriched_ok = res
                        detailed_list[orig_idx] = updated_item
                        if enriched_ok:
                            batch_enriched.append(updated_item)

                if batch_enriched:
                    await self._emit_detail(sp, batch_enriched)

                processed += len(batch_indices)
                now_ts = time.monotonic()
                if (len(target_indices) > 5 and processed >= len(target_indices)) or (now_ts - last_log_ts >= interval_sec):
                    await self._emit_progress(
                        sp,
                        "detail",
                        f"正在补全{target_prefix}{sp_label}详情：已完成 {processed}/{len(target_indices)} 条（成功 {stats['enriched']} 条）",
                    )
                    last_log_ts = now_ts

                if i + batch_size < len(target_indices) and not (self._detail_waf_open() or self._waf_open() or state["circuit_broken"]):
                    if await self._check_should_stop():
                        result["params"]["_stopped"] = True
                        break
                    await asyncio.sleep(random.uniform(0.8, 1.6))

            result["params"]["list"] = detailed_list
            missing = max(len(candidate_indices) - stats["enriched"], 0)
            circuit_broken = bool(state["circuit_broken"] or self._detail_waf_open())
            if missing:
                result["params"]["_detail_missing"] = missing
                result["params"]["_detail_waf"] = self._detail_waf_open()
            if circuit_broken:
                result["params"]["_detail_circuit_break"] = True
                if len(target_indices) > 5 or processed < len(target_indices):
                    await self._emit_progress(
                        sp,
                        "detail",
                        f"{target_prefix}{sp_label}详情补全触发保护熔断：已完成 {processed}/{len(target_indices)} 条（成功 {stats['enriched']} 条），其余保留基础备案号入库",
                    )
            logger.info(
                f"并发详情获取完成，总计 {len(detailed_list)} 条 (目标 {len(target_indices)} 条, 跳过已知 {skipped_known} 条, 上限跳过 {skipped_cap} 条, 详情缺失 {missing} 条, 详情熔断 {circuit_broken})"
            )

        return result

    async def getbeian(self, name, sp, pageNum, pageSize, proxy=""):
        if await self._check_should_stop():
            return True, {"code": 200, "success": True, "params": {"list": [], "_stopped": True}}

        auto_pagination = self._is_auto_pagination(pageNum, pageSize)
        if auto_pagination:
            first_page = 1
            page_size = 26
        else:
            first_page = int(pageNum or 1)
            page_size = int(pageSize or 26)

        success, result, detail_context = await self._query_beian_page(
            name, sp, first_page, page_size, proxy
        )
        if not success:
            return False, result

        if not auto_pagination:
            result = await self._enrich_app_details(result, sp, detail_context, proxy, target_name=name)
            return True, result

        params = result.get("params", {})
        first_items = list(params.get("list") or [])
        all_items = list(first_items)
        total_pages = self._get_total_pages(result, page_size)
        total_records = int(params.get("total") or len(all_items) or 0)

        await self._emit_page(sp, first_items, first_page, total_pages)

        page_step = max(1, self._get_system_int_config("progress_log_page_step", 5))
        interval_sec = max(1, self._get_system_int_config("progress_log_interval_sec", 30))
        sp_labels = {0: "网站备案", 1: "移动APP", 2: "小程序", 3: "快应用"}
        sp_label = sp_labels.get(sp, "备案资产")

        last_log_ts = time.monotonic()
        if total_pages > page_step:
            await self._emit_progress(
                sp,
                "list",
                f"正在拉取主体【{name}】工信部 {sp_label} 列表：共 {total_records} 条（约 {total_pages} 页），第 1/{total_pages} 页，累计 {len(all_items)} 条",
            )

        stopped = False
        for current_page in range(2, total_pages + 1):
            if await self._check_should_stop():
                stopped = True
                logger.info(f"任务已中止，停止工信部 {sp_label} 后续分页抓取（已完成第 {current_page - 1}/{total_pages} 页）")
                break

            await asyncio.sleep(2.0)  # 防止请求过快触发 MIIT 403 防火墙
            if await self._check_should_stop():
                stopped = True
                logger.info(f"任务已中止，停止工信部 {sp_label} 后续分页抓取（已完成第 {current_page - 1}/{total_pages} 页）")
                break

            success, page_result, page_detail_context = await self._query_beian_page(
                name, sp, current_page, page_size, proxy
            )
            if not success:
                logger.warning(f"分页获取失败，已抓取至第 {current_page-1} 页，停止继续翻页")
                await self._emit_progress(
                    sp,
                    "list",
                    f"主体【{name}】工信部 {sp_label} 列表分页在第 {current_page}/{total_pages} 页提前停止（累计 {len(all_items)} 条，原因: {page_result}）",
                )
                break  # 不直接抛出错误，而是保留已获取的前几页数据

            page_params = page_result.get("params", {})
            page_items = list(page_params.get("list") or [])
            all_items.extend(page_items)
            detail_context = page_detail_context or detail_context

            await self._emit_page(sp, page_items, current_page, total_pages)

            now_ts = time.monotonic()
            need_heartbeat = (
                (total_pages > page_step and (current_page % page_step == 0 or current_page == total_pages))
                or (now_ts - last_log_ts >= interval_sec)
            )
            if need_heartbeat:
                await self._emit_progress(
                    sp,
                    "list",
                    f"正在拉取主体【{name}】工信部 {sp_label} 列表：第 {current_page}/{total_pages} 页，累计 {len(all_items)}/{total_records or len(all_items)} 条",
                )
                last_log_ts = now_ts

        params["list"] = all_items
        params["pageNum"] = 1
        params["pageSize"] = len(all_items)
        if stopped:
            params["_stopped"] = True
        result["params"] = params

        if stopped:
            return True, result

        result = await self._enrich_app_details(result, sp, detail_context, proxy, target_name=name)
        return True, result

    async def _getblackbeian_once(self, name, sp, cand, force_token=False):
        info = ujson.loads(self.btypj.get(sp))
        if sp == 0:
            info["domainName"] = name
        else:
            info["serviceName"] = name

        current_ip = None
        if getattr(getattr(config, 'captcha', object()), 'enable', False):
            success, p_uuid, token, sign, base_header = await self.check_img(
                cand.proxy_url or "",
                exit_candidate=cand,
                force_token=force_token,
                _raise_on_exit_err=True,
            )
            if not success:
                return False, p_uuid

            length = str(len(str(ujson.dumps(info, ensure_ascii=False)).encode("utf-8")))
            base_header.update(
                {"Content-Length": length, "uuid": p_uuid, "token": token, "sign": sign}
            )
            try:
                async with self._open_candidate_session(cand) as session:
                    actual_proxy = getattr(session, "_arl_proxy", None)
                    await self._acquire_rate_slot(is_proxied=bool(cand.proxy_url), exit_id=cand.exit_id)
                    current_ip = self._session_local_ip(session)
                    async with session.post((self.blackqueryByCondition if sp == 0 else self.blackappAndMiniByCondition),
                                            data=ujson.dumps(info, ensure_ascii=False),
                                            headers=base_header, proxy=actual_proxy) as req:
                        res = await req.text()
                        req_status = req.status
            except Exception as e:
                raise _ExitAttemptError("transport_error", f"黑名单查询网络异常 ({type(e).__name__})", cooldown_sec=60) from e

        else:
            success, token, base_header = await self.get_token(
                cand.proxy_url or "",
                force=force_token,
                exit_candidate=cand,
                _raise_on_exit_err=True,
            )
            if not success:
                logger.info("获取token失败")
                return False, None
            base_header.update({"token": token, "sign": self.sign})

            try:
                async with self._open_candidate_session(cand) as session:
                    actual_proxy = getattr(session, "_arl_proxy", None)
                    await self._acquire_rate_slot(is_proxied=bool(cand.proxy_url), exit_id=cand.exit_id)
                    current_ip = self._session_local_ip(session)
                    async with session.post((f"{self.blackqueryByCondition}/" if sp == 0 else f"{self.blackappAndMiniByCondition}/"),
                                            json=info,
                                            headers=base_header, proxy=actual_proxy) as req:
                        res = await req.text()
                        req_status = req.status
            except Exception as e:
                raise _ExitAttemptError("transport_error", f"黑名单查询网络异常 ({type(e).__name__})", cooldown_sec=60) from e

        if "当前访问疑似黑客攻击" in res or "已被创宇盾拦截" in res or req_status == 403 or (isinstance(res, str) and "error_403_type" in res):
            blocked_ip = self._extract_waf_blocked_ip(res) or current_ip or self._extract_proxy_ip(cand.proxy_url)
            raise _ExitAttemptError("waf_blocked", "触发创宇盾拦截 (HTTP 403)", blocked_ip=blocked_ip)

        return True, ujson.loads(res)

    async def getblackbeian(self, name, sp, proxy=""):
        if self._is_global_waf_blocked():
            return False, "当前访问已被创宇盾拦截"

        candidates = self._iter_attempt_exits(proxy)
        if not candidates:
            return False, "当前所有出口均处于冷却状态"

        last_err = "当前访问已被创宇盾拦截"
        for idx, cand in enumerate(candidates):
            next_cand = candidates[idx + 1] if (idx + 1 < len(candidates)) else None
            try:
                ok, data = await self._getblackbeian_once(name, sp, cand, force_token=(idx > 0))
                if ok:
                    await self._handle_exit_success(cand, switched_from_primary=(idx > 0))
                return ok, data
            except _ExitAttemptError as err:
                await self._handle_exit_failure(
                    cand,
                    blocked_ip=err.blocked_ip,
                    reason=err.reason,
                    cooldown_sec=err.cooldown_sec,
                    next_cand=next_cand,
                    scene="黑名单查询",
                )
                last_err = "当前访问已被创宇盾拦截" if err.kind == "waf_blocked" else err.reason
                if next_cand is not None:
                    continue
                if err.kind in ("waf_blocked", "rate_limited") and self._is_global_waf_blocked():
                    self._waf_trip("黑名单查询")
                return False, last_err

        return False, last_err

    async def autoget(self, name, sp, pageNum="", pageSize="", proxy="", b=1):
        try:
            if proxy != "":
                success,data = (
                    await self.getbeian(name, sp, pageNum, pageSize, proxy)
                    if b == 1
                    else await self.getblackbeian(name, sp, proxy)
                )
            else:
                success,data = (
                    await self.getbeian(name, sp, pageNum, pageSize)
                    if b == 1
                    else await self.getblackbeian(name, sp)
                )
            if not success:
                return {"code":500,"message":data}
            if data["code"] == 500 or not success:
                return {"code": 122, "message": "工信部服务器异常"}
        except Exception as e:
            return {"code": 122, "message": "查询失败","error":str(e)}
        
        return data

    # APP备案查询
    async def ymApp(self, name, pageNum="", pageSize="", proxy=""):
        return await self.autoget(name, 1, pageNum, pageSize, proxy)

    # 网站备案查询
    async def ymWeb(self, name, pageNum="", pageSize="", proxy=""):
        return await self.autoget(name, 0, pageNum, pageSize, proxy)

    # 小程序备案查询
    async def ymMiniApp(self, name, pageNum="", pageSize="", proxy=""):
        return await self.autoget(name, 2, pageNum, pageSize, proxy)

    # 快应用备案查询
    async def ymKuaiApp(self, name, pageNum="", pageSize="", proxy=""):
        return await self.autoget(name, 3, pageNum, pageSize, proxy)



    async def cleanup(self):
        """清理资源 - 移除连接器缓存相关代码"""
        logger.info("beian资源清理完成")

    def __del__(self):
        """析构函数，确保资源清理"""
        try:
            pass
        except:
            pass

if __name__ == "__main__":
    async def main():
        a = beian()
        try:
            # 官方单页查询pageSize最大支持26
            # 页面索引pageNum从1开始,第一页可以不写
            data = await a.ymWeb("深圳市腾讯计算机系统有限公司")
            print(f"查询结果：\n{data}")
            data = await a.ymApp("深圳市腾讯计算机系统有限公司")
            print(f"查询结果：\n{data}")
        finally:
            await a.cleanup()  # 确保资源清理

    asyncio.run(main())

    """
    在其他代码模块中调用（异步）

        from ymicp import beian

        icp = beian()
        try:
            data = await icp.ymApp("微信")
        finally:
            await icp.cleanup()  # 重要：确保资源清理
    
    """
