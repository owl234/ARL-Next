# backend/app/services/vuln_platform/submit_thread.py
"""漏洞批量提交多线程任务"""

import time

from app import utils
from app.services.baseThread import BaseThread

logger = utils.get_logger()


class VulnSubmitThread(BaseThread):
    """多漏洞并发提交（每个按来源平台回传）"""

    def __init__(self, vuln_ids, submitter, concurrency=5):
        super().__init__(targets=vuln_ids, concurrency=concurrency)
        self.submitter = submitter
        self.records = []

    def work(self, vuln_id):
        try:
            record = self.submitter.submit(vuln_id)
            self.records.append(record)
            if record.get("success"):
                logger.info("[Submit] {} → {} 成功".format(
                    vuln_id, record.get("platform")))
            else:
                logger.warning("[Submit] {} → {} 失败: {}".format(
                    vuln_id, record.get("platform"),
                    record.get("message")))
        except Exception as e:
            logger.warning("[Submit] {} 提交异常: {}".format(
                vuln_id, e))
            self.records.append({
                "vuln_id": vuln_id,
                "success": False,
                "message": str(e),
            })

    def run(self):
        t1 = time.time()
        logger.info("start vuln submit, count:{}".format(
            len(self.targets)))
        self._run()
        elapse = time.time() - t1
        logger.info("end vuln submit ({:.2f}s), total:{}"
                    .format(elapse, len(self.records)))
        return self.records


def vuln_submit_thread(vuln_ids, submitter, concurrency=5):
    t = VulnSubmitThread(vuln_ids, submitter,
                          concurrency=concurrency)
    return t.run()