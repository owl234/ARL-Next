# ARL-Next/app/models/scan_schedule.py
"""扫描调度模型 —— 集合名：vuln_platform_scan_schedules"""

from datetime import datetime
from typing import Optional
from pymongo import IndexModel, ASCENDING

from app.models.base import BaseModel


class ScanScheduleModel(BaseModel):
    """扫描调度模型"""

    COLLECTION = "vuln_platform_scan_schedules"

    FIELDS = {
        "project_fingerprint": str,
        "profile": str,
        "cron_expression": str,
        "enabled": bool,
        "last_run": Optional[datetime],
        "next_run": Optional[datetime],
    }

    INDEXES = [
        IndexModel([("project_fingerprint", ASCENDING),
                    ("profile", ASCENDING)],
                   unique=True, name="idx_project_profile_unique"),
        IndexModel([("enabled", ASCENDING)],
                   name="idx_enabled"),
    ]

    ENABLE_CREATED_AT = True
    ENABLE_UPDATED_AT = True

    @classmethod
    def default_order(cls):
        return "-_id"