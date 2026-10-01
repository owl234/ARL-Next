# backend/app/services/vuln_platform/submit_service.py
"""提交记录业务服务"""

from app import utils
from app.utils import db as db_utils
from app.utils.time import utcnow
from app.models import SubmitRecordModel

logger = utils.get_logger()


class SubmitService(object):
    """提交记录业务服务"""

    COLLECTION = SubmitRecordModel.COLLECTION

    def __init__(self, db=None):
        self.db = db or utils.conn_db(self.COLLECTION)
        db_utils.ensure_indexes(
            self.COLLECTION,
            SubmitRecordModel.get_indexes(), db=self.db)

    def insert(self, record):
        """插入提交记录"""
        now = utcnow()
        doc = {
            **record,
            "created_at": now,
            "updated_at": now,
        }
        return db_utils.insert_one(
            self.COLLECTION, doc, db=self.db)

    def find_success_by_vuln(self, vuln_id):
        """查找漏洞已成功提交的记录"""
        return db_utils.find_one(
            self.COLLECTION,
            {"vuln_id": vuln_id,
             "status": SubmitRecordModel.STATUS_SUBMITTED},
            db=self.db)

    def list_paged(self, platform=None, status=None,
                   project_fingerprint=None,
                   page=1, page_size=20):
        query = {}
        if platform:
            query["platform"] = platform
        if status:
            query["status"] = status
        if project_fingerprint:
            query["project_fingerprint"] = project_fingerprint

        return db_utils.find_paged(
            self.COLLECTION,
            query=query,
            sort=[("_id", -1)],
            page=page, page_size=page_size,
            db=self.db)