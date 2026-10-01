# backend/app/adapters/vuln_platform/hackerone.py
"""HackerOne API 适配器"""

import os
import requests

from app import utils
from .base import BasePlatformAdapter

logger = utils.get_logger()


class HackerOneAdapter(BasePlatformAdapter):
    """HackerOne平台适配器（使用官方 API）"""

    def __init__(self, platform_name="hackerone", db=None):
        super().__init__(platform_name, db=db)
        self.api_base = self.config.get("api_base")
        self.username = os.environ.get("HACKERONE_USERNAME")
        self.api_token = os.environ.get("HACKERONE_TOKEN")
        if self.username and self.api_token:
            self.auth = (self.username, self.api_token)
        else:
            self.auth = None
            logger.warning("HackerOne API 凭据未配置")

    def fetch_projects(self):
        if not self.auth:
            return []

        url = "{}/hackers/programs".format(self.api_base)
        self.compliance.wait_if_needed(url)
        try:
            resp = requests.get(url, auth=self.auth, timeout=15)
            if resp.status_code != 200:
                logger.error("HackerOne API 返回: {}".format(
                    resp.status_code))
                return []
            data = resp.json().get("data", [])
            projects = []
            for item in data:
                projects.append({
                    "project_id": item["attributes"]["handle"],
                    "project_name": item["attributes"]["name"],
                    "scope": [],
                    "platform": "hackerone",
                })
            logger.info("HackerOne获取 {} 个项目".format(
                len(projects)))
            return projects
        except Exception as e:
            logger.error("HackerOne API 获取失败: {}".format(e))
            return []

    def fetch_scope(self, project_id):
        if not self.auth:
            return []

        url = "{}/hackers/programs/{}/structured_scopes".format(
            self.api_base, project_id)
        self.compliance.wait_if_needed(url)
        try:
            resp = requests.get(url, auth=self.auth, timeout=15)
            if resp.status_code != 200:
                return []
            scopes = resp.json().get("data", [])
            targets = []
            for s in scopes:
                attrs = s.get("attributes", {})
                asset_id = attrs.get("asset_identifier", "")
                if asset_id and attrs.get(
                        "eligible_for_submission", True):
                    targets.append(asset_id)
            return targets
        except Exception as e:
            logger.error("HackerOne scope 获取失败: {}".format(e))
            return []

    def submit_vulnerability(self, vuln_data):
        logger.info("HackerOne提交漏洞: {}".format(
            vuln_data.get("title", "N/A")))
        return {
            "success": False,
            "platform_vuln_id": None,
            "message": "HackerOne 提交需通过官方 API 报告接口",
        }