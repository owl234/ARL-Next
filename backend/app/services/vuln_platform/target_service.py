# backend/app/services/vuln_platform/target_service.py
"""目标范围业务服务"""

import hashlib
from urllib.parse import urlparse

from app import utils
from app.utils import db as db_utils
from app.utils.time import utcnow
from app.models import TargetModel

logger = utils.get_logger()


class TargetService(object):
    """目标范围业务服务"""

    COLLECTION = TargetModel.COLLECTION

    def __init__(self, db=None):
        self.db = db or utils.conn_db(self.COLLECTION)
        db_utils.ensure_indexes(
            self.COLLECTION, TargetModel.get_indexes(), db=self.db)

    def upsert_from_project(self, project_fingerprint, platform,
                             scope_list):
        """从项目范围导入目标"""
        new_count = 0
        now = utcnow()

        for raw in scope_list:
            target, target_type = self._normalize(raw)
            if not target:
                continue

            fingerprint = hashlib.sha256(
                "{}:{}".format(platform, target).encode()
            ).hexdigest()

            insert_doc = {
                "target": target,
                "target_type": target_type,
                "project_fingerprint": project_fingerprint,
                "platform": platform,
                "source_raw": raw,
                "status": "active",
                "scanned": False,
                "last_scan_at": None,
                "fingerprint": fingerprint,
                "created_at": now,
                "updated_at": now,
            }
            update_doc = {
                "status": "active",
                "updated_at": now,
            }

            is_new, _ = db_utils.upsert_one(
                self.COLLECTION,
                query={"fingerprint": fingerprint},
                insert_doc=insert_doc,
                update_doc=update_doc,
                db=self.db)
            if is_new:
                new_count += 1

        return new_count

    def mark_scanned(self, fingerprint):
        """标记目标已扫描"""
        db_utils.update_one(
            self.COLLECTION,
            {"fingerprint": fingerprint},
            {"scanned": True,
             "last_scan_at": utcnow(),
             "updated_at": utcnow()},
            db=self.db)

    def list_pending(self, project_fingerprint=None, limit=0):
        """查询待扫描目标"""
        query = {"status": "active", "scanned": False}
        if project_fingerprint:
            query["project_fingerprint"] = project_fingerprint
        return db_utils.find_many(
            self.COLLECTION, query, limit=limit, db=self.db)

    def list_by_project(self, project_fingerprint):
        """查询项目下所有目标"""
        return db_utils.find_many(
            self.COLLECTION,
            {"project_fingerprint": project_fingerprint},
            db=self.db)

    def list_paged(self, page=1, page_size=20, **filters):
        query = {k: v for k, v in filters.items() if v}
        return db_utils.find_paged(
            self.COLLECTION,
            query=query,
            sort=[("_id", -1)],
            page=page, page_size=page_size,
            db=self.db)

    @staticmethod
    def _normalize(raw):
        """标准化目标字符串"""
        raw = raw.strip().lower()
        if not raw:
            return None, None
        if raw.startswith(("http://", "https://")):
            return urlparse(raw).netloc, "url"
        if "/" in raw:
            return raw, "cidr"
        if raw.replace(".", "").isdigit():
            return raw, "ip"
        return raw, "domain"