# ARL-Next/app/models/submit_record.py
"""漏洞提交记录模型 —— 集合名：vuln_platform_submit_records"""

from datetime import datetime
from typing import Optional
from bson import ObjectId
from pymongo import IndexModel, ASCENDING

from app.models.base import BaseModel


class SubmitRecordModel(BaseModel):
    """提交记录模型"""

    COLLECTION = "vuln_platform_submit_records"

    FIELDS = {
        "vuln_id": ObjectId,
        "platform": str,
        "source_platform": str,
        "project_fingerprint": str,
        "success": bool,
        "platform_vuln_id": Optional[str],
        "message": Optional[str],
        "submit_time": datetime,
        "status": str,
    }

    INDEXES = [
        IndexModel([("vuln_id", ASCENDING),
                    ("platform", ASCENDING)],
                   unique=True, name="idx_vuln_platform_unique"),
        IndexModel([("project_fingerprint", ASCENDING)],
                   name="idx_project_fp"),
        IndexModel([("status", ASCENDING)],
                   name="idx_status"),
    ]

    ENABLE_CREATED_AT = True
    ENABLE_UPDATED_AT = True

    STATUS_SUBMITTED = "submitted"
    STATUS_FAILED = "failed"

    @classmethod
    def default_order(cls):
        return "-_id"