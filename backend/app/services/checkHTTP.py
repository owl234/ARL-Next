import time
import urllib.parse
import ssl

from app import utils
from .baseThread import BaseThread

import requests.exceptions
logger = utils.get_logger()

GATEWAY_PORTS = {
    80, 443, 8080, 8443, 8000, 8001, 8081, 8088, 8089, 8888, 8848,
    9000, 9090, 7001, 10000, 10443, 9443, 4443, 4433, 4430, 8444,
    4848, 8161, 8880, 9999, 10001, 5000, 5001, 7443, 8082, 8083,
    8084, 8085, 9043, 9060, 9444, 2375, 2376, 6443
}

GATEWAY_PATHS = [
    "/web/frame/login.html",
    "/login.html",
    "/admin/",
    "/ui/",
    "/manage/",
    "/system/"
]


class CheckHTTP(BaseThread):
    def __init__(self, urls, concurrency=10):
        super().__init__(urls, concurrency=concurrency)
        self.timeout = (6, 6)
        self.checkout_map = {}

    def check(self, url, resilient=False):
        parsed = urllib.parse.urlsplit(url)
        is_https = (parsed.scheme.lower() == "https") or url.startswith("https://")
        try:
            conn = utils.http_req(url, method="get", timeout=self.timeout, verify=False, resilient_ssl=resilient)
        except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, ssl.SSLError) as e:
            if not resilient and is_https:
                return self.check(url, resilient=True)
            raise e

        if conn.status_code == 400:
            content_lower = (conn.content or b"").lower()
            if b"the plain http request was sent to https port" in content_lower:
                return None

            has_server = bool(conn.headers.get("Server"))
            content_type = conn.headers.get("Content-Type", "").lower()
            has_html = "text/html" in content_type or any(tag in content_lower for tag in (b"<html", b"<head", b"<body", b"<!doctype html"))
            has_legacy = bool(conn.headers.get("ETag") and conn.headers.get("Date"))
            if not (has_server or has_html or has_legacy):
                return None

        # *** 特殊情况过滤
        if conn.status_code == 422 or conn.status_code == 410:
            return None

        if (conn.status_code >= 501) and (conn.status_code < 600):
            return None

        if conn.status_code == 403:
            check_str = b'</title><style type="text/css">body{margin:5% auto 0 auto;padding:0 18px}'
            if check_str in conn.content:
                return None

        item = {
            "status": conn.status_code,
            "content-type": conn.headers.get("Content-Type", "")
        }

        return item

    def work(self, url):
        parsed = urllib.parse.urlsplit(url)
        path = parsed.path or "/"
        is_root = (path == "/" or path == "")
        scheme = parsed.scheme.lower() if parsed.scheme else "http"
        port = parsed.port or (443 if scheme == "https" else 80)
        is_candidate_for_fallback = (scheme == "https") or (port in GATEWAY_PORTS)

        out = None
        try:
            out = self.check(url)
        except requests.exceptions.RequestException:
            out = None
        except Exception as e:
            out = None
            logger.warning("error on url {}".format(url))
            logger.warning(e)

        # 检查是否需要回退探测网关路径
        # 条件：针对根路径、属于高危/网关端口或 https 协议，且根路径失败(out is None)或返回错误(status >= 400)
        is_error = (out is None) or (out.get("status", 0) >= 400)
        if is_root and is_candidate_for_fallback and is_error:
            base_url = f"{parsed.scheme}://{parsed.netloc}"
            for gpath in GATEWAY_PATHS:
                probe_url = base_url + gpath
                try:
                    fb_out = self.check(probe_url)
                    if fb_out is not None and (fb_out.get("status", 0) < 400 or fb_out.get("status", 0) in (401, 403)):
                        fb_out["url"] = url
                        out = fb_out
                        break
                except Exception:
                    continue

        if out is not None:
            self.checkout_map[url] = out

    def run(self):
        t1 = time.time()
        logger.info("start check http {}".format(len(self.targets)))
        self._run()
        time.time() - t1
        return self.checkout_map


def check_http(urls, concurrency=15):
    c = CheckHTTP(urls, concurrency)
    return c.run()
