# backend/app/adapters/vuln_platform/generic.py
"""通用导入适配器"""

from app import utils
from .base import BasePlatformAdapter

logger = utils.get_logger()


class GenericAdapter(BasePlatformAdapter):
    """通用导入适配器"""

    def __init__(self, platform_name="generic", db=None):
        super().__init__(platform_name, db=db)

    def fetch_projects(self, **kwargs):
        return []

    def fetch_scope(self, project_id):
        return []

    def submit_vulnerability(self, vuln_data):
        logger.info("通用记录漏洞: {} @ {}".format(
            vuln_data.get("title", "N/A"),
            vuln_data.get("target_url", "N/A")))
        return {
            "success": True,
            "platform_vuln_id": "local-{}".format(
                vuln_data.get("_id", "na")),
            "message": "已记录到本地",
        }

    def import_scope(self, platform_name, project_name, scope):
        from .dedup import IncrementalDeduplicator

        scope_fp = IncrementalDeduplicator.compute_scope_fingerprint(
            scope)
        project_fp = \
            IncrementalDeduplicator.compute_project_fingerprint(
                platform_name, project_name, scope_fp)

        if self.dedup:
            self.dedup.record_project(project_fp, {
                "platform": platform_name,
                "project_id": project_name,
                "project_name": project_name,
                "scope": scope,
            })
            return {"success": True, "fingerprint": project_fp}

        return {"success": False, "message": "无数据库连接"}