# backend/app/adapters/vuln_platform/base.py
"""平台适配器抽象基类"""

from abc import ABC, abstractmethod

from app import utils
from app.utils.http_client import http
from app.utils.proxy_cache import proxy_cache
from .compliance import ComplianceChecker
from .cookie_manager import CookieManager
from .config import get_platform_config

logger = utils.get_logger()


class BasePlatformAdapter(ABC):

    def __init__(self, platform_name, db=None):
        self.platform_name = platform_name
        self.config = get_platform_config(platform_name)
        self.db = db

        self.compliance = ComplianceChecker(
            user_agent=self.config.get("user_agent",
                                        "ARL-Next-Bot/1.0"),
            default_delay=self.config.get("default_delay", 3.0))

        if self.config.get("requires_login"):
            self.cookie_mgr = CookieManager(platform_name)
        else:
            self.cookie_mgr = None

    @abstractmethod
    def fetch_projects(self, **kwargs):
        pass

    @abstractmethod
    def fetch_scope(self, project_id):
        pass

    @abstractmethod
    def submit_vulnerability(self, vuln_data):
        pass

    # ═══════════════════════════════════════════════
    # 预缓存代理（按实际目标站点验证）
    # ═══════════════════════════════════════════════

    def warmup_proxy(self, target_url: str, size: int = 5) -> int:
        """
        预缓存代理（针对实际目标站点验证）

        :param target_url: 实际要爬取的 URL
        :param size: 期望缓存数量
        :return: 实际缓存数量
        """
        logger.info(
            "[{}] 预热代理缓存: target={}, size={}".format(
                self.platform_name, target_url, size))

        count = proxy_cache.warmup(target_url=target_url, size=size)

        if count == 0:
            logger.warning(
                "[{}] 预热失败，将使用直连: {}".format(
                    self.platform_name, target_url))
        else:
            logger.info(
                "[{}] 预热完成: {} 个代理可访问 {}".format(
                    self.platform_name, count, target_url))

        return count

    # ═══════════════════════════════════════════════
    # 安全请求（合规 + 速率 + Cookie + 代理 + UA）
    # ═══════════════════════════════════════════════

    def _safe_request(self, url, method="GET", headers=None,
                       use_proxy=True, timeout=None, **kwargs):
        if not self.compliance.can_fetch(url):
            raise PermissionError(
                "robots.txt 禁止抓取: {}".format(url))

        self.compliance.wait_if_needed(url)

        req_headers = dict(headers or {})
        if self.cookie_mgr and self.cookie_mgr.cookie_string:
            req_headers["Cookie"] = self.cookie_mgr.cookie_string

        return http.request(
            method=method,
            url=url,
            headers=req_headers,
            use_proxy=use_proxy,
            timeout=timeout or 15,
            **kwargs)