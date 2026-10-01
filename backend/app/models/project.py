
# ARL-Next/app/models/project.py
"""项目模型 —— 集合名：vuln_platform_projects"""

from datetime import datetime
from typing import List, Optional
from pymongo import IndexModel, ASCENDING

from app.models.base import BaseModel


class ProjectModel(BaseModel):
    """众测项目模型"""

    COLLECTION = "vuln_platform_projects"

    FIELDS = {
        "fingerprint": str,
        "platform": str,
        "project_id": str,
        "project_name": str,
        "scope": List[str],
        "scope_fingerprint": str,
        "status": str,
        "fetched_at": datetime,
        "last_scan_at": Optional[datetime],
        "scan_phase": Optional[str],
        "scan_status": Optional[str],
        "asset_count": int,
        "vuln_count": int,
        "asset_fingerprints": List[str],
    }

    # 只保留必要索引
    INDEXES = [
        IndexModel([("fingerprint", ASCENDING)],
                   unique=True, name="idx_fp_unique"),
        IndexModel([("platform", ASCENDING),
                    ("project_id", ASCENDING)],
                   unique=True, name="idx_platform_project_unique"),
        IndexModel([("status", ASCENDING)],
                   name="idx_status"),
    ]

    ENABLE_CREATED_AT = True
    ENABLE_UPDATED_AT = True

    STATUS_ACTIVE = "active"
    STATUS_EXPIRED = "expired"

    PHASE_QUICK = "quick"
    PHASE_FULL = "full"
    PHASE_INCREMENTAL = "incremental"

    @classmethod
    def default_order(cls):
        # ObjectId 含时间戳，按 _id 倒序 = 按时间倒序
        return "-_id"