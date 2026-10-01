# backend/app/services/vuln_platform/project_service.py
"""项目业务服务"""

from app import utils
from app.utils import db as db_utils
from app.utils.time import utcnow
from app.models import ProjectModel

logger = utils.get_logger()


class ProjectService(object):
    """项目业务服务"""

    COLLECTION = ProjectModel.COLLECTION

    def __init__(self, db=None):
        self.db = db or utils.conn_db(self.COLLECTION)
        db_utils.ensure_indexes(
            self.COLLECTION, ProjectModel.get_indexes(), db=self.db)

    # ═══════════════════════════════════════════════
    # 写入
    # ═══════════════════════════════════════════════

    def upsert(self, project_data):
        """按 fingerprint upsert，返回 (is_new, fingerprint)"""
        fingerprint = project_data.get("fingerprint")
        if not fingerprint:
            raise ValueError("缺少 fingerprint")

        now = utcnow()
        insert_doc = {
            **project_data,
            "status": project_data.get("status",
                                        ProjectModel.STATUS_ACTIVE),
            "created_at": now,
            "updated_at": now,
            "fetched_at": now,
            "last_scan_at": None,
            "scan_phase": None,
            "scan_status": None,
            "asset_count": 0,
            "vuln_count": 0,
            "asset_fingerprints": [],
        }
        update_doc = {
            "project_name": project_data.get("project_name"),
            "scope": project_data.get("scope"),
            "scope_fingerprint":
                project_data.get("scope_fingerprint"),
            "fetched_at": now,
            "updated_at": now,
        }

        is_new, _ = db_utils.upsert_one(
            self.COLLECTION,
            query={"fingerprint": fingerprint},
            insert_doc=insert_doc,
            update_doc=update_doc,
            db=self.db)
        return is_new, fingerprint

    def update_scan_state(self, fingerprint, phase=None,
                          status=None, asset_count=None,
                          vuln_count=None):
        """更新扫描状态"""
        update = {
            "last_scan_at": utcnow(),
            "updated_at": utcnow(),
        }
        if phase is not None:
            update["scan_phase"] = phase
        if status is not None:
            update["scan_status"] = status
        if asset_count is not None:
            update["asset_count"] = asset_count
        if vuln_count is not None:
            update["vuln_count"] = vuln_count

        db_utils.update_one(
            self.COLLECTION,
            {"fingerprint": fingerprint},
            update,
            db=self.db)

    def expire(self, fingerprint):
        """标记过期"""
        db_utils.update_one(
            self.COLLECTION,
            {"fingerprint": fingerprint},
            {"status": ProjectModel.STATUS_EXPIRED,
             "updated_at": utcnow()},
            db=self.db)

    # ═══════════════════════════════════════════════
    # 读取
    # ═══════════════════════════════════════════════

    def get(self, fingerprint):
        return db_utils.find_one(
            self.COLLECTION,
            {"fingerprint": fingerprint},
            db=self.db)

    def get_by_id(self, _id):
        return db_utils.find_by_id(
            self.COLLECTION, _id, db=self.db)

    def list_active(self):
        return db_utils.find_many(
            self.COLLECTION,
            {"status": ProjectModel.STATUS_ACTIVE},
            db=self.db)

    def list_paged(self, platform=None, status=None,
                   keyword=None, page=1, page_size=20):
        query = {}
        if platform:
            query["platform"] = platform
        if status:
            query["status"] = status
        if keyword:
            query["project_name"] = {
                "$regex": keyword, "$options": "i"}

        return db_utils.find_paged(
            self.COLLECTION,
            query=query,
            sort=[("_id", -1)],
            page=page, page_size=page_size,
            db=self.db)

    # ═══════════════════════════════════════════════
    # 业务逻辑
    # ═══════════════════════════════════════════════

    def get_new_assets(self, fingerprint, current_fingerprints):
        """获取新增资产指纹"""
        record = db_utils.find_one(
            self.COLLECTION,
            {"fingerprint": fingerprint},
            projection={"asset_fingerprints": 1},
            db=self.db)
        if not record:
            return list(current_fingerprints)

        previous = set(record.get("asset_fingerprints", []))
        current = set(current_fingerprints)
        new_fps = list(current - previous)

        db_utils.update_one(
            self.COLLECTION,
            {"fingerprint": fingerprint},
            {"asset_fingerprints": list(current),
             "updated_at": utcnow()},
            db=self.db)
        return new_fps

    def fetch_and_sync(self, platform_name):
        """从平台抓取项目并同步"""
        from app.adapters.vuln_platform import get_adapter
        from app.adapters.vuln_platform.dedup import (
            IncrementalDeduplicator)

        adapter = get_adapter(platform_name, db=self.db)
        try:
            remote_projects = adapter.fetch_projects()
        except Exception as e:
            logger.error("[{}] 远程获取失败: {}".format(
                platform_name, e))
            return {"new": 0, "updated": 0, "error": str(e)}

        new_count = 0
        updated_count = 0

        for project in remote_projects:
            scope = project.get("scope", [])
            scope_fp = \
                IncrementalDeduplicator.compute_scope_fingerprint(
                    scope)
            project_fp = \
                IncrementalDeduplicator.compute_project_fingerprint(
                    platform_name,
                    project.get("project_id", ""), scope_fp)

            project["platform"] = platform_name
            project["fingerprint"] = project_fp
            project["scope_fingerprint"] = scope_fp

            is_new, _ = self.upsert(project)
            if is_new:
                new_count += 1
            else:
                updated_count += 1

        logger.info("[{}] 同步: 新增 {}, 更新 {}".format(
            platform_name, new_count, updated_count))
        return {"new": new_count, "updated": updated_count,
                "total": len(remote_projects)}

    def fetch_all_platforms(self):
        """抓取所有已启用平台"""
        from app.adapters.vuln_platform.platform_thread import (
            platform_fetch_thread)
        result = platform_fetch_thread(self.db, concurrency=4)
        sync_results = {}
        for name in result.get("projects", {}):
            sync_results[name] = self.fetch_and_sync(name)
        for name, err in result.get("errors", {}).items():
            sync_results[name] = {"error": err}
        return sync_results