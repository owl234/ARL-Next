# backend/app/services/vuln_platform/schedule_service.py
"""扫描调度业务服务"""

from app import utils
from app.utils import db as db_utils
from app.utils.time import utcnow
from app.models import ScanScheduleModel

logger = utils.get_logger()


class ScheduleService(object):
    """扫描调度业务服务"""

    COLLECTION = ScanScheduleModel.COLLECTION

    def __init__(self, db=None):
        self.db = db or utils.conn_db(self.COLLECTION)
        db_utils.ensure_indexes(
            self.COLLECTION,
            ScanScheduleModel.get_indexes(), db=self.db)

    def upsert(self, data):
        """创建/更新调度"""
        key = {
            "project_fingerprint": data["project_fingerprint"],
            "profile": data["profile"],
        }
        now = utcnow()
        insert_doc = {
            **data,
            "enabled": data.get("enabled", True),
            "last_run": None,
            "next_run": None,
            "created_at": now,
            "updated_at": now,
        }
        update_doc = {
            **data,
            "updated_at": now,
        }

        is_new, _ = db_utils.upsert_one(
            self.COLLECTION,
            query=key,
            insert_doc=insert_doc,
            update_doc=update_doc,
            db=self.db)
        return {"created": is_new}

    def toggle(self, schedule_id, enabled):
        """启用/禁用"""
        db_utils.update_one(
            self.COLLECTION,
            {"_id": db_utils._to_object_id(schedule_id)
             if hasattr(db_utils, "_to_object_id")
             else schedule_id},
            {"enabled": enabled, "updated_at": utcnow()},
            db=self.db)

    def remove(self, schedule_id):
        """删除"""
        from bson import ObjectId
        try:
            oid = ObjectId(schedule_id)
        except Exception:
            return 0
        return db_utils.delete_one(
            self.COLLECTION, {"_id": oid}, db=self.db)

    def list_enabled(self):
        """查询所有启用的调度"""
        return db_utils.find_many(
            self.COLLECTION,
            {"enabled": True},
            db=self.db)

    def list_paged(self, page=1, page_size=20, **filters):
        query = {k: v for k, v in filters.items() if v}
        return db_utils.find_paged(
            self.COLLECTION,
            query=query,
            sort=[("_id", -1)],
            page=page, page_size=page_size,
            db=self.db)