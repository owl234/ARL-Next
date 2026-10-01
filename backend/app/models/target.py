# ARL-Next/app/models/target.py
"""目标范围模型 —— 集合名：vuln_platform_targets"""

from datetime import datetime
from typing import Optional
from pymongo import IndexModel, ASCENDING

from app.models.base import BaseModel


class TargetModel(BaseModel):
    """标准化目标范围模型"""

    COLLECTION = "vuln_platform_targets"

    FIELDS = {
        "target": str,
        "target_type": str,
        "project_fingerprint": str,
        "platform": str,
        "scope_id": Optional[str],
        "source_raw": Optional[str],
        "status": str,
        "scanned": bool,
        "last_scan_at": Optional[datetime],
        "fingerprint": str,
    }

    INDEXES = [
        IndexModel([("fingerprint", ASCENDING)],
                   unique=True, name="idx_fp_unique"),
        IndexModel([("project_fingerprint", ASCENDING)],
                   name="idx_project_fp"),
        IndexModel([("scanned", ASCENDING)],
                   name="idx_scanned"),
    ]

    ENABLE_CREATED_AT = True
    ENABLE_UPDATED_AT = True

    TARGET_TYPE_DOMAIN = "domain"
    TARGET_TYPE_IP = "ip"
    TARGET_TYPE_CIDR = "cidr"
    TARGET_TYPE_URL = "url"
    TARGET_TYPE_APP = "app"

    @classmethod
    def default_order(cls):
        return "-_id"