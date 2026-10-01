# backend/app/utils/http_client.py
"""
ARL-Next 统一 HTTP 请求工具

特性：
- 从线程本地缓存获取代理（按目标站点）
- 自动随机 User-Agent + 完整浏览器头
- 单次请求，无重试
- 失败代理自动清理
"""

import os
import time
import random
from contextlib import contextmanager
from typing import Optional, Dict
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter

from app import utils
from app.utils.proxy_client import proxy_client
from app.utils.proxy_cache import proxy_cache

logger = utils.get_logger()


# ═══════════════════════════════════════════════════════════
# User-Agent 池
# ═══════════════════════════════════════════════════════════

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:122.0) Gecko/20100101 Firefox/122.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36 Edg/122.0.0.0",
]


def random_ua():
    return random.choice(USER_AGENTS)


# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

DEFAULT_TIMEOUT = 15
PROXY_FAIL_STATUS = (403, 407, 429, 502, 503, 504)

NO_PROXY_HOSTS = (
    "127.0.0.1", "localhost", "0.0.0.0",
    "10.", "172.16.", "172.17.", "172.18.", "172.19.",
    "172.20.", "172.21.", "172.22.", "172.23.", "172.24.",
    "172.25.", "172.26.", "172.27.", "172.28.", "172.29.",
    "172.30.", "172.31.", "192.168.",
)


def _is_internal_url(url):
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    for prefix in NO_PROXY_HOSTS:
        if host.startswith(prefix) or host == prefix:
            return True
    return False


# ═══════════════════════════════════════════════════════════
# 默认请求头
# ═══════════════════════════════════════════════════════════

def build_headers(ua=None):
    ua = ua or random_ua()
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,"
                  "application/xml;q=0.9,image/avif,"
                  "image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "Cache-Control": "max-age=0",
    }

    is_mac = "Macintosh" in ua or "Mac OS X" in ua
    is_win = "Windows" in ua
    is_linux = "Linux" in ua and "Android" not in ua
    is_mobile = "Mobile" in ua or "iPhone" in ua or "Android" in ua
    is_chrome = "Chrome" in ua and "Edg" not in ua and "OPR" not in ua
    is_edge = "Edg/" in ua
    is_firefox = "Firefox" in ua

    headers["Sec-Fetch-Site"] = "none"
    headers["Sec-Fetch-Mode"] = "navigate"
    headers["Sec-Fetch-User"] = "?1"
    headers["Sec-Fetch-Dest"] = "document"

    if is_chrome or is_edge:
        version = "122"
        for v in ("122", "121", "120", "119", "118"):
            if "Chrome/{}".format(v) in ua:
                version = v
                break
        platform = "Unknown"
        if is_mac:
            platform = "macOS"
        elif is_win:
            platform = "Windows"
        elif is_linux:
            platform = "Linux"
        headers["sec-ch-ua"] = (
            '"Chromium";v="{v}", "Not(A:Brand";v="24", '
            '"Google Chrome";v="{v}"'.format(v=version))
        headers["sec-ch-ua-mobile"] = "?1" if is_mobile else "?0"
        headers["sec-ch-ua-platform"] = '"{}"'.format(platform)

    if is_firefox:
        headers["Accept-Language"] = (
            "zh-CN,zh;q=0.8,zh-TW;q=0.7,"
            "zh-HK;q=0.5,en-US;q=0.3,en;q=0.2")
        headers["DNT"] = "1"
        headers["Sec-GPC"] = "1"

    if is_mobile:
        headers["Accept"] = (
            "text/html,application/xhtml+xml,"
            "application/xml;q=0.9,*/*;q=0.8")

    return headers


# ═══════════════════════════════════════════════════════════
# 响应对象
# ═══════════════════════════════════════════════════════════

class HttpResponse(object):
    def __init__(self, resp, proxy=None, elapsed=0.0):
        self._resp = resp
        self.proxy = proxy
        self.elapsed = elapsed

    @property
    def status_code(self):
        return self._resp.status_code

    @property
    def text(self):
        return self._resp.text

    @property
    def content(self):
        return self._resp.content

    @property
    def headers(self):
        return self._resp.headers

    @property
    def url(self):
        return self._resp.url

    @property
    def encoding(self):
        return self._resp.encoding

    @encoding.setter
    def encoding(self, value):
        self._resp.encoding = value

    def json(self, **kwargs):
        return self._resp.json(**kwargs)

    def iter_content(self, chunk_size=8192):
        return self._resp.iter_content(chunk_size)

    def iter_lines(self, **kwargs):
        return self._resp.iter_lines(**kwargs)

    def raise_for_status(self):
        return self._resp.raise_for_status()

    def close(self):
        self._resp.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()

    def __repr__(self):
        return "<HttpResponse [{}] proxy={} elapsed={:.2f}s>".format(
            self.status_code, self.proxy, self.elapsed)


class _EmptyResponse(object):
    status_code = 0
    text = ""
    content = b""
    headers = {}
    url = ""

    def json(self, **kwargs):
        return {}

    def raise_for_status(self):
        raise RuntimeError("请求未成功（空响应）")

    def iter_content(self, chunk_size=8192):
        return iter([])

    def close(self):
        pass


# ═══════════════════════════════════════════════════════════
# HttpClient
# ═══════════════════════════════════════════════════════════

class HttpClient(object):

    def __init__(self, timeout=DEFAULT_TIMEOUT, use_proxy=True):
        self.timeout = timeout
        self.use_proxy = use_proxy
        self._session = self._build_session()

    def _build_session(self):
        session = requests.Session()
        adapter = HTTPAdapter(pool_connections=20, pool_maxsize=50)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    # ── 代理获取/释放 ─────────────────────────────
    def _acquire_proxy(self, url, use_proxy=None):
        """获取代理（从目标站点专属缓存）"""
        if use_proxy is False:
            return None
        if use_proxy is None and not self.use_proxy:
            return None
        if _is_internal_url(url):
            return None

        try:
            # ★ 传入目标 URL
            raw = proxy_cache.get(target_url=url)
            if raw:
                return {"http": raw, "https": raw}
        except Exception as e:
            logger.debug("[HTTP] 获取代理失败: {}".format(e))
        return None

    def _release_proxy(self, url, proxy, success=True):
        """释放代理（失败时从缓存和代理池中删除）"""
        if not proxy:
            return

        proxy_str = proxy.get("http") or proxy.get("https")
        if not proxy_str:
            return

        if success:
            return

        try:
            # ★ 传入目标 URL
            proxy_cache.mark_dead(target_url=url, proxy=proxy_str)
        except Exception:
            pass

        try:
            proxy_client.delete_proxy(proxy_str)
            logger.info("[HTTP] 代理失败，已删除: {}".format(proxy_str))
        except Exception as e:
            logger.debug("[HTTP] 删除代理失败: {}".format(e))

    # ═══════════════════════════════════════════════
    # 核心请求方法
    # ═══════════════════════════════════════════════

    def request(self, method, url,
                 use_proxy=None,
                 timeout=None,
                 headers=None,
                 ua=None,
                 browser_headers=True,
                 raise_on_fail=False,
                 **kwargs):
        timeout = timeout if timeout is not None else self.timeout

        if browser_headers:
            req_headers = build_headers(ua=ua)
        else:
            req_headers = {"User-Agent": ua or random_ua()}
        if headers:
            req_headers.update(headers)

        proxy = self._acquire_proxy(url, use_proxy)
        proxy_str = proxy.get("http") if proxy else "direct"

        start = time.time()
        err_msg = None

        try:
            logger.debug(
                "[HTTP] {} {} (proxy={})".format(
                    method, url, proxy_str))

            resp = self._session.request(
                method, url,
                headers=req_headers,
                proxies=proxy,
                timeout=timeout,
                **kwargs)

            elapsed = time.time() - start

            if resp.status_code in PROXY_FAIL_STATUS and proxy:
                self._release_proxy(url, proxy, success=False)
                logger.warning(
                    "[HTTP] 代理异常 {} ({})".format(
                        proxy_str, resp.status_code))
            else:
                self._release_proxy(url, proxy, success=True)

            logger.debug(
                "[HTTP] {} {} → {} ({:.2f}s)".format(
                    method, url, resp.status_code, elapsed))

            return HttpResponse(
                resp,
                proxy=proxy_str if proxy else None,
                elapsed=elapsed)

        except requests.exceptions.ProxyError as e:
            self._release_proxy(url, proxy, success=False)
            err_msg = "代理连接失败 {}: {}".format(proxy_str, e)
            logger.warning("[HTTP] {}".format(err_msg))

        except requests.exceptions.Timeout as e:
            self._release_proxy(url, proxy, success=False)
            err_msg = "请求超时 (proxy={}): {}".format(proxy_str, e)
            logger.warning("[HTTP] {}".format(err_msg))

        except requests.exceptions.ConnectionError as e:
            self._release_proxy(url, proxy, success=False)
            err_msg = "连接失败 (proxy={}): {}".format(proxy_str, e)
            logger.warning("[HTTP] {}".format(err_msg))

        except Exception as e:
            err_msg = "请求异常: {}".format(e)
            logger.error("[HTTP] {}".format(err_msg))

        elapsed = time.time() - start
        if raise_on_fail:
            raise RuntimeError(err_msg)

        return HttpResponse(_EmptyResponse(), proxy=None, elapsed=elapsed)

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)

    def head(self, url, **kwargs):
        return self.request("HEAD", url, **kwargs)

    def patch(self, url, **kwargs):
        return self.request("PATCH", url, **kwargs)

    @contextmanager
    def session(self, use_proxy=None):
        proxy = (self._acquire_proxy("", use_proxy)
                 if use_proxy is not False else None)
        sess = _SessionWrapper(self, proxy, use_proxy)
        try:
            yield sess
        finally:
            if proxy and sess.failed:
                self._release_proxy("", proxy, success=False)

    def close(self):
        try:
            self._session.close()
        except Exception:
            pass


class _SessionWrapper(object):
    def __init__(self, client, proxy, use_proxy):
        self.client = client
        self.proxy = proxy
        self.use_proxy = use_proxy
        self.failed = False

    def request(self, method, url, **kwargs):
        resp = self.client.request(
            method, url, use_proxy=self.use_proxy, **kwargs)
        if resp.status_code >= 500 or resp.status_code == 0:
            self.failed = True
        return resp

    def get(self, url, **kwargs):
        return self.request("GET", url, **kwargs)

    def post(self, url, **kwargs):
        return self.request("POST", url, **kwargs)

    def put(self, url, **kwargs):
        return self.request("PUT", url, **kwargs)

    def delete(self, url, **kwargs):
        return self.request("DELETE", url, **kwargs)


http = HttpClient()