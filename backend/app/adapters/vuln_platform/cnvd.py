# backend/app/adapters/vuln_platform/cnvd.py
"""CNVD众测适配器"""

import re

from app import utils
from .base import BasePlatformAdapter

logger = utils.get_logger()


class CnvdAdapter(BasePlatformAdapter):
    """CNVD众测平台适配器"""

    def __init__(self, platform_name="cnvd", db=None):
        super().__init__(platform_name, db=db)

    def fetch_projects(self):
        url = "{}/news/list".format(self.config["base_url"])
        try:
            resp = self._safe_request(url)
        except PermissionError:
            logger.warning("robots.txt 禁止，跳过: {}".format(url))
            return []

        activities = self._parse_activities(resp.text)
        logger.info("CNVD获取 {} 个众测活动".format(len(activities)))
        return activities

    def fetch_scope(self, project_id):
        url = "{}/news/{}".format(
            self.config["base_url"], project_id)
        try:
            resp = self._safe_request(url)
            return self._extract_scope(resp.text)
        except Exception as e:
            logger.error("获取CNVD活动范围失败: {}".format(e))
            return []

    def submit_vulnerability(self, vuln_data):
        logger.info("CNVD提交漏洞: {}".format(
            vuln_data.get("title", "N/A")))
        return {
            "success": False,
            "platform_vuln_id": None,
            "message": "CNVD提交需人工确认完整证明材料",
        }

    def _parse_activities(self, html):
        activities = []
        pattern = re.compile(
            r'<a[^>]*href="/news/(\d+)"[^>]*>([^<]+)</a>')
        for match in pattern.finditer(html):
            activities.append({
                "project_id": match.group(1),
                "project_name": match.group(2).strip(),
                "scope": [],
                "platform": "cnvd",
            })
        return activities

    def _extract_scope(self, html):
        scope = []
        domain_pattern = re.compile(
            r'(?:域名|目标|范围|资产)[：:]\s*'
            r'([a-zA-Z0-9.-]+\.[a-zA-Z]{2,})')
        for match in domain_pattern.finditer(html):
            scope.append(match.group(1))
        return scope