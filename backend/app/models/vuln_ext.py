# ARL-Next/app/models/vuln_ext.py
"""漏洞扩展模型 —— 集合名：vuln_platform_vulns"""

from datetime import datetime
from typing import Optional, Dict, Any
from pymongo import IndexModel, ASCENDING

from app.models.base import BaseModel


class VulnExtModel(BaseModel):
    """漏洞平台聚合的漏洞模型"""

    COLLECTION = "vuln_platform_vulns"

    FIELDS = {
        "template_id": str,
        "target_url": str,
        "project_fingerprint": str,
        "platform": str,
        "severity": str,
        "submit_status": str,
        "submit_platform": Optional[str],
        "submit_time": Optional[datetime],
        "platform_vuln_id": Optional[str],
        "submit_message": Optional[str],
        "raw_info": Optional[Dict[str, Any]],
    }

    INDEXES = [
        IndexModel([("template_id", ASCENDING),
                    ("target_url", ASCENDING),
                    ("project_fingerprint", ASCENDING)],
                   unique=True, name="idx_template_target_project_unique"),
        IndexModel([("project_fingerprint", ASCENDING)],
                   name="idx_project_fp"),
        IndexModel([("submit_status", ASCENDING)],
                   name="idx_submit_status"),
    ]

    ENABLE_CREATED_AT = True
    ENABLE_UPDATED_AT = True

    SUBMIT_STATUS_PENDING = "pending"
    SUBMIT_STATUS_SUBMITTED = "submitted"
    SUBMIT_STATUS_FAILED = "failed"

    @classmethod
    def default_order(cls):
        return "-_id"