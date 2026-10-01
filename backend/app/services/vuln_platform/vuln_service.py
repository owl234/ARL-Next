# backend/app/services/vuln_platform/vuln_service.py
"""漏洞业务服务"""

from app import utils
from app.utils import db as db_utils
from app.utils.time import utcnow
from app.models import VulnExtModel

logger = utils.get_logger()


class VulnService(object):
    """漏洞业务服务"""

    COLLECTION = VulnExtModel.COLLECTION

    def __init__(self, db=None):
        self.db = db or utils.conn_db(self.COLLECTION)
        db_utils.ensure_indexes(
            self.COLLECTION,
            VulnExtModel.get_indexes(), db=self.db)

    def insert_or_update_finding(self, finding, project_fingerprint,
                                  source_platform):
        """
        插入或更新漏洞
        :return: (is_new, vuln_id)
        """
        template_id = finding.get("template-id")
        target_url = finding.get("target_url")

        key = {
            "template_id": template_id,
            "target_url": target_url,
            "project_fingerprint": project_fingerprint,
        }

        now = utcnow()
        insert_doc = {
            **finding,
            "project_fingerprint": project_fingerprint,
            "platform": source_platform,
            "submit_status": VulnExtModel.SUBMIT_STATUS_PENDING,
            "submit_platform": None,
            "submit_time": None,
            "platform_vuln_id": None,
            "created_at": now,
            "updated_at": now,
        }
        update_doc = {
            **finding,
            "updated_at": now,
        }

        return db_utils.upsert_one(
            self.COLLECTION,
            query=key,
            insert_doc=insert_doc,
            update_doc=update_doc,
            db=self.db)

    def get(self, vuln_id):
        return db_utils.find_by_id(
            self.COLLECTION, vuln_id, db=self.db)

    def list_by_project(self, project_fingerprint,
                         submit_status=None):
        query = {"project_fingerprint": project_fingerprint}
        if submit_status:
            query["submit_status"] = submit_status
        return db_utils.find_many(
            self.COLLECTION, query, db=self.db)

    def list_pending_submit(self, project_fingerprint):
        """查询待提交的漏洞"""
        return db_utils.find_many(
            self.COLLECTION,
            {"project_fingerprint": project_fingerprint,
             "submit_status": {
                 "$ne": VulnExtModel.SUBMIT_STATUS_SUBMITTED}},
            db=self.db)

    def update_submit_state(self, vuln_id, platform, status,
                             platform_vuln_id=None, message=None):
        """更新提交状态"""
        update = {
            "submit_platform": platform,
            "submit_status": status,
            "submit_time": utcnow(),
            "updated_at": utcnow(),
        }
        if platform_vuln_id:
            update["platform_vuln_id"] = platform_vuln_id
        if message:
            update["submit_message"] = message

        from bson import ObjectId
        try:
            oid = ObjectId(vuln_id)
        except Exception:
            return 0
        db_utils.update_one(
            self.COLLECTION,
            {"_id": oid},
            update,
            db=self.db)