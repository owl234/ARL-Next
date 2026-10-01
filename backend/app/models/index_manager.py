# backend/app/models/index_manager.py
"""MongoDB 索引统一管理"""

from pymongo import IndexModel, ASCENDING, DESCENDING

from app import utils

logger = utils.get_logger()

_INDEX_FLAGS = set()


def _ensure(collection, name, indexes):
    flag = "{}.{}".format(collection.name, name)
    if flag in _INDEX_FLAGS:
        return
    try:
        collection.create_indexes(indexes)
        _INDEX_FLAGS.add(flag)
        logger.info("索引就绪: {} [{}]".format(collection.name, name))
    except Exception as e:
        logger.warning("索引创建异常 [{}]: {}".format(flag, e))


def ensure_project_indexes(collection):
    _ensure(collection, "project", [
        IndexModel([("fingerprint", ASCENDING)], unique=True,
                   name="idx_fingerprint_unique"),
        IndexModel([("platform", ASCENDING),
                    ("project_id", ASCENDING)],
                   name="idx_platform_project"),
        IndexModel([("status", ASCENDING)], name="idx_status"),
        IndexModel([("fetched_at", DESCENDING)], name="idx_fetched_at"),
    ])


def ensure_schedule_indexes(collection):
    _ensure(collection, "schedule", [
        IndexModel([("project_fingerprint", ASCENDING),
                    ("profile", ASCENDING)],
                   unique=True, name="idx_project_profile_unique"),
        IndexModel([("enabled", ASCENDING)], name="idx_enabled"),
    ])


def ensure_submit_record_indexes(collection):
    _ensure(collection, "submit_record", [
        IndexModel([("vuln_id", ASCENDING),
                    ("platform", ASCENDING)],
                   name="idx_vuln_platform"),
        IndexModel([("project_fingerprint", ASCENDING)],
                   name="idx_project_fp"),
        IndexModel([("submit_time", DESCENDING)],
                   name="idx_submit_time"),
        IndexModel([("status", ASCENDING)], name="idx_status"),
    ])


def ensure_vuln_indexes(collection):
    _ensure(collection, "vuln_ext", [
        IndexModel([("project_fingerprint", ASCENDING)],
                   name="idx_project_fp"),
        IndexModel([("template_id", ASCENDING),
                    ("target_url", ASCENDING),
                    ("project_fingerprint", ASCENDING)],
                   name="idx_template_target_project"),
        IndexModel([("submit_status", ASCENDING)],
                   name="idx_submit_status"),
    ])


def ensure_all_indexes(db):
    ensure_project_indexes(db.projects)
    ensure_schedule_indexes(db.scan_schedules)
    ensure_submit_record_indexes(db.submit_records)
    ensure_vuln_indexes(db.vuln)
    logger.info("所有 MongoDB 索引已就绪")