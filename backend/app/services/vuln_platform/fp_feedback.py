# backend/app/services/vuln_platform/fp_feedback.py
"""误报反馈业务服务"""

from app import utils
from .nuclei_filter import FalsePositiveFeedback, \
    NucleiFalsePositiveFilter

logger = utils.get_logger()


class FpFeedbackService(object):
    """误报反馈业务服务"""

    def __init__(self, db):
        self.db = db
        self.feedback = FalsePositiveFeedback(db)
        self.filter = NucleiFalsePositiveFilter()

    def mark_false_positive(self, template_id, target_url, notes=""):
        self.feedback.record_false_positive(
            template_id, target_url, notes)

        high_fp = self.feedback.get_high_fp_templates(threshold=5)
        high_fp_ids = [item["_id"] for item in high_fp]

        if template_id in high_fp_ids:
            self._sync_ignore_list(high_fp_ids)
            logger.info("模板 {} 已加入忽略列表".format(template_id))

        return {
            "recorded": True,
            "template_id": template_id,
            "high_fp_templates": high_fp_ids,
        }

    def _sync_ignore_list(self, template_ids):
        ignore_file = self.filter.ignore_file
        with open(ignore_file, "w") as f:
            for tid in template_ids:
                f.write("{}.yaml\n".format(tid))

    def get_fp_statistics(self):
        high_fp = self.feedback.get_high_fp_templates(threshold=1)
        return {
            "total_fp_templates": len(high_fp),
            "high_fp_templates": high_fp[:20],
        }