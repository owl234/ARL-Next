# backend/app/services/vuln_platform/nuclei_filter.py
"""Nuclei 扫描结果误报过滤"""

import subprocess
import json
from pathlib import Path
from datetime import datetime

from app import utils

logger = utils.get_logger()


class NucleiFalsePositiveFilter(object):
    """Nuclei 误报过滤"""

    HIGH_FP_TAGS = ["exposure", "tech", "favicon"]
    KNOWN_FP_TEMPLATE_IDS = [
        "path-traversal-detection",
        "directory-listing",
    ]

    def __init__(self, templates_dir="/opt/nuclei-templates"):
        self.templates_dir = templates_dir
        self.ignore_file = Path("/tmp/nuclei-ignore.txt")

    def build_ignore_list(self):
        with open(self.ignore_file, "w") as f:
            for tid in self.KNOWN_FP_TEMPLATE_IDS:
                f.write("{}.yaml\n".format(tid))

    def scan_with_filters(self, targets_file, output_file,
                          severity="critical,high", rate_limit=150):
        self.build_ignore_list()
        cmd = [
            "nuclei", "-l", targets_file,
            "-t", self.templates_dir,
            "-severity", severity,
            "-exclude-tags", ",".join(self.HIGH_FP_TAGS),
            "-exclude", str(self.ignore_file),
            "-rate-limit", str(rate_limit),
            "-timeout", "10", "-retries", "1",
            "-o", output_file, "-jsonl",
        ]
        logger.info("执行 Nuclei 扫描: {}".format(" ".join(cmd)))
        try:
            subprocess.run(cmd, capture_output=True, text=True,
                            timeout=3600)
        except subprocess.TimeoutExpired:
            logger.error("Nuclei 扫描超时")
        return self._parse_results(output_file)

    def _parse_results(self, output_file):
        results = []
        try:
            with open(output_file) as f:
                for line in f:
                    if line.strip():
                        results.append(json.loads(line))
        except FileNotFoundError:
            logger.warning("结果文件不存在: {}".format(output_file))
        return results

    def secondary_validation(self, finding):
        vuln_type = finding.get("template-id", "")
        if vuln_type in self.KNOWN_FP_TEMPLATE_IDS:
            return {"valid": False, "reason": "已知高误报模板"}
        severity = finding.get("info", {}).get("severity", "")
        if severity in ["critical", "high"]:
            return {
                "valid": None,
                "reason": "高危漏洞需人工复核",
                "requires_review": True,
            }
        return {"valid": True, "reason": "自动通过"}


class FalsePositiveFeedback(object):
    """误报反馈收集"""

    def __init__(self, db):
        self.collection = db.false_positive_feedback

    def record_false_positive(self, template_id, target_url,
                               notes=""):
        self.collection.insert_one({
            "template_id": template_id,
            "target_url": target_url,
            "notes": notes,
            "created_at": datetime.utcnow(),
        })

    def get_high_fp_templates(self, threshold=5):
        pipeline = [
            {"$group": {"_id": "$template_id",
                        "count": {"$sum": 1}}},
            {"$match": {"count": {"$gte": threshold}}},
            {"$sort": {"count": -1}},
        ]
        return list(self.collection.aggregate(pipeline))