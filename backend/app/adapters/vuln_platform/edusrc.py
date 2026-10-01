# backend/app/adapters/vuln_platform/edusrc.py
"""EduSRC适配器"""

import re

from app import utils
from .base import BasePlatformAdapter

logger = utils.get_logger()


class EduSrcAdapter(BasePlatformAdapter):
    """EduSRC平台适配器"""

    def __init__(self, platform_name="edusrc", db=None):
        super().__init__(platform_name, db=db)

    def fetch_projects(self):
        if self.cookie_mgr:
            if not self.cookie_mgr.ensure_valid(
                    self.config["test_url"], self._login):
                raise RuntimeError("EduSRC Cookie 维护失败")

        url = "{}/list/".format(self.config["base_url"])
        try:
            resp = self._safe_request(url)
        except PermissionError:
            logger.warning("robots.txt 禁止，跳过: {}".format(url))
            return []

        projects = self._parse_projects(resp.text)
        logger.info("EduSRC获取 {} 个项目".format(len(projects)))
        return projects

    def fetch_scope(self, project_id):
        url = "{}/list/{}".format(
            self.config["base_url"], project_id)
        try:
            resp = self._safe_request(url)
            return self._extract_scope(resp.text)
        except Exception as e:
            logger.error("获取EduSRC项目范围失败: {}".format(e))
            return []

    def submit_vulnerability(self, vuln_data):
        logger.info("EduSRC提交漏洞: {}".format(
            vuln_data.get("title", "N/A")))
        return {
            "success": False,
            "platform_vuln_id": None,
            "message": "EduSRC提交需登录态，请配置 Cookie",
        }

    def _login(self):
        logger.info("执行EduSRC登录...")
        return {}

    def _parse_projects(self, html):
        projects = []
        pattern = re.compile(
            r'<a[^>]*href="/list/(\d+)"[^>]*>([^<]+)</a>')
        for match in pattern.finditer(html):
            projects.append({
                "project_id": match.group(1),
                "project_name": match.group(2).strip(),
                "scope": [],
                "platform": "edusrc",
            })
        return projects

    def _extract_scope(self, html):
        scope = []
        domain_pattern = re.compile(
            r'([a-zA-Z0-9.-]+\.(?:edu\.cn|ac\.cn|edu\.[a-z]{2,}))')
        for match in domain_pattern.finditer(html):
            scope.append(match.group(1))
        return scope