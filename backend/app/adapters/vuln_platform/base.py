# backend/app/adapters/vuln_platform/base.py
"""平台适配器抽象基类"""

from abc import ABC, abstractmethod

from app import utils
from .compliance import ComplianceChecker
from .cookie_manager import CookieManager
from .config import get_platform_config

logger = utils.get_logger()


class BasePlatformAdapter(ABC):
    """所有平台适配器的抽象基类"""

    def __init__(self, platform_name, db=None):
        self.platform_name = platform_name
        self.config = get_platform_config(platform_name)
        self.db = db

        self.compliance = ComplianceChecker(
            user_agent=self.config.get("user_agent",
                                        "ARL-Next-Bot/1.0"),
            default_delay=self.config.get("default_delay", 3.0))

        # Cookie 管理
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

    def _safe_request(self, url, method="GET", headers=None, **kwargs):
        """安全请求：robots 检查 → 速率控制 → 附加 Cookie"""
        import requests

        if not self.compliance.can_fetch(url):
            raise PermissionError(
                "robots.txt 禁止抓取: {}".format(url))

        self.compliance.wait_if_needed(url)

        req_headers = {
            "User-Agent": self.config.get("user_agent",
                                           "ARL-Next-Bot/1.0"),
        }
        if headers:
            req_headers.update(headers)

        # ★ 修复：用 cookie_string 而不是 cookies
        if self.cookie_mgr and self.cookie_mgr.cookie_string:
            req_headers["Cookie"] = self.cookie_mgr.cookie_string

        return requests.request(
            method, url, headers=req_headers, timeout=15, **kwargs)