# backend/app/adapters/vuln_platform/cookie_manager.py
"""
Cookie 自动维护管理器（仅内存）
- Cookie 从 PLATFORM_CONFIG 读取
- 不持久化到文件
- refresh 只更新内存
"""

import time

from app import utils
from app.utils.time import utcnow
from .config import get_cookie_string, get_cookie_ttl

logger = utils.get_logger()


class CookieManager(object):
    """Cookie 自动维护管理器（仅内存）"""

    def __init__(self, platform_name,
                 cookie_file=None,        # 保留参数（兼容旧签名，忽略）
                 cookie_ttl_hours=None):  # 保留参数（兼容旧签名）
        """
        :param platform_name: 平台名称
        :param cookie_file: 已废弃（保留兼容）
        :param cookie_ttl_hours: 覆盖默认 TTL（可选）
        """
        self.platform_name = platform_name

        # TTL：显式传入优先，否则从 config 读取
        self.cookie_ttl_hours = (
            cookie_ttl_hours or get_cookie_ttl(platform_name))

        # ★ Cookie 直接从 PLATFORM_CONFIG 读取（仅内存）
        self.cookie_string = get_cookie_string(platform_name)
        self.last_login_time = None

        if self.cookie_string:
            logger.info("[{}] 已加载 Cookie ({} 字符)".format(
                platform_name, len(self.cookie_string)))
        else:
            logger.warning("[{}] 未配置 Cookie".format(
                platform_name))

    @property
    def cookies(self):
        """
        兼容旧代码：返回 cookie 的 dict 形式
        :return: {"key1": "val1", "key2": "val2"}
        """
        if not self.cookie_string:
            return {}
        result = {}
        for part in self.cookie_string.split(";"):
            part = part.strip()
            if not part or "=" not in part:
                continue
            key, _, value = part.partition("=")
            result[key.strip()] = value.strip()
        return result

    @property
    def cookie_header(self):
        """返回 Cookie 请求头字符串"""
        return self.cookie_string or ""

    # ═══════════════════════════════════════════════
    # Cookie 有效性检测
    # ═══════════════════════════════════════════════

    def is_cookie_valid(self, test_url, expected_status=200):
        """检测 Cookie 是否有效"""
        import requests

        if not self.cookie_string:
            logger.warning("[{}] Cookie 为空".format(
                self.platform_name))
            return False

        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Macintosh; "
                              "Intel Mac OS X 10_15_7)",
                "Cookie": self.cookie_string,
            }
            resp = requests.get(
                test_url, headers=headers,
                timeout=10, allow_redirects=False)

            if resp.status_code in (301, 302):
                location = resp.headers.get("Location", "").lower()
                if "login" in location:
                    logger.warning("[{}] Cookie 已过期"
                                    "（重定向到登录页）".format(
                                        self.platform_name))
                    return False

            return resp.status_code == expected_status

        except Exception as e:
            logger.error("[{}] Cookie 检测失败: {}".format(
                self.platform_name, e))
            return False

    # ═══════════════════════════════════════════════
    # Cookie 刷新
    # ═══════════════════════════════════════════════

    def refresh_cookie(self, login_func, *args, **kwargs):
        """
        刷新 Cookie（仅更新内存，不持久化）
        :param login_func: 登录函数，返回新的 cookie 字符串
        """
        logger.info("[{}] 开始刷新 Cookie...".format(
            self.platform_name))
        try:
            new_cookie = login_func(*args, **kwargs)
            if new_cookie and isinstance(new_cookie, str):
                self.cookie_string = new_cookie.strip()
                self.last_login_time = utcnow()
                logger.info("[{}] Cookie 刷新成功（仅内存）".format(
                    self.platform_name))
                return True
            logger.error("[{}] Cookie 刷新失败：登录返回空".format(
                self.platform_name))
            return False
        except Exception as e:
            logger.error("[{}] Cookie 刷新异常: {}".format(
                self.platform_name, e))
            return False

    def ensure_valid(self, test_url, login_func, max_retries=3):
        """
        确保 Cookie 有效，失效时自动刷新
        :return: bool
        """
        for attempt in range(max_retries):
            if self.is_cookie_valid(test_url):
                return True

            logger.info("[{}] Cookie 失效，第 {}/{} 次刷新".format(
                self.platform_name, attempt + 1, max_retries))

            if self.refresh_cookie(login_func):
                return True

            time.sleep(5 * (attempt + 1))

        logger.warning("[ALERT][{}] Cookie 刷新失败，需人工介入".format(
            self.platform_name))
        return False

    # ═══════════════════════════════════════════════
    # 工具方法
    # ═══════════════════════════════════════════════

    def get_cookie_header(self):
        """返回 Cookie 请求头字符串"""
        return self.cookie_string or ""

    def update_cookie(self, cookie_string):
        """更新 Cookie 字符串（仅内存）"""
        self.cookie_string = cookie_string.strip()

    def clear(self):
        """清空 Cookie（仅内存）"""
        self.cookie_string = ""