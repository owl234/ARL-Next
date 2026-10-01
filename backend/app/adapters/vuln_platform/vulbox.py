# backend/app/adapters/vuln_platform/vulbox.py
"""漏洞盒子适配器"""

import re

from app import utils
from .base import BasePlatformAdapter

logger = utils.get_logger()


class VulboxAdapter(BasePlatformAdapter):
    """漏洞盒子平台适配器"""

    def __init__(self, platform_name="vulbox", db=None):
        super().__init__(platform_name, db=db)

    def fetch_projects(self, project_type="public", pages=10):
        if self.cookie_mgr:
            if not self.cookie_mgr.ensure_valid(
                    self.config["test_url"], self._login):
                raise RuntimeError("漏洞盒子 Cookie 维护失败")

        projects = []
        base = self.config["base_url"]
        for page in range(1, pages + 1):
            url = "{}/project?type={}&page={}".format(
                base, project_type, page)
            try:
                resp = self._safe_request(url)
            except PermissionError:
                logger.warning("robots.txt 禁止，跳过: {}".format(url))
                continue

            items = self._parse_projects(resp.text)
            if not items:
                break
            logger.info("第 {} 页解析到 {} 个项目".format(
                page, len(items)))
            projects.extend(items)

        logger.info("漏洞盒子共获取 {} 个项目".format(len(projects)))
        return projects

    def fetch_scope(self, project_id):
        url = "{}/project/{}".format(
            self.config["base_url"], project_id)
        try:
            resp = self._safe_request(url)
            return self._extract_scope(resp.text)
        except Exception as e:
            logger.error("获取漏洞盒子项目范围失败: {}".format(e))
            return []

    def submit_vulnerability(self, vuln_data):
        logger.info("漏洞盒子提交漏洞: {} @ {}".format(
            vuln_data.get("title", "N/A"),
            vuln_data.get("target_url", "N/A")))
        return {
            "success": False,
            "platform_vuln_id": None,
            "message": "漏洞盒子提交接口需抓包确认，请配置后启用",
        }

    def _login(self):
        logger.info("执行漏洞盒子登录...")
        return {}

    def _parse_projects(self, html):
        projects = []
        pattern = re.compile(
            r'<a[^>]*href="/project/(\d+)"[^>]*>([^<]+)</a>')
        for match in pattern.finditer(html):
            projects.append({
                "project_id": match.group(1),
                "project_name": match.group(2).strip(),
                "scope": [],
                "platform": "vulbox",
            })
        return projects

    def _extract_scope(self, html):
        scope = []
        domain_pattern = re.compile(
            r'(?:域名|目标|范围)[：:]\s*([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})')
        for match in domain_pattern.finditer(html):
            scope.append(match.group(1))
        return scope