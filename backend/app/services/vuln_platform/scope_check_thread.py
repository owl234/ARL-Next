# backend/app/services/vuln_platform/scope_check_thread.py
"""项目范围变化检查多线程任务"""

import time

from app import utils
from app.services.baseThread import BaseThread

logger = utils.get_logger()


class ScopeCheckThread(BaseThread):
    """多项目并发检查范围变化"""

    def __init__(self, projects, orchestrator, concurrency=5):
        super().__init__(targets=projects, concurrency=concurrency)
        self.orchestrator = orchestrator
        self.changes = []

    def work(self, project):
        try:
            project_fp = project.get("fingerprint")
            r = self.orchestrator.check_and_rescan(project_fp)
            if r.get("dispatched"):
                self.changes.append({
                    "project": project_fp,
                    "platform": project.get("platform"),
                    "new_assets": r.get("target_count", 0),
                })
                logger.info("[ScopeCheck] {} 有 {} 个新增资产"
                            .format(project_fp,
                                    r.get("target_count", 0)))
        except Exception as e:
            logger.warning("[ScopeCheck] {} 检查失败: {}".format(
                project.get("fingerprint"), e))

    def run(self):
        t1 = time.time()
        logger.info("start scope check, projects:{}".format(
            len(self.targets)))
        self._run()
        elapse = time.time() - t1
        logger.info("end scope check ({:.2f}s), changes:{}"
                    .format(elapse, len(self.changes)))
        return self.changes


def scope_check_thread(projects, orchestrator, concurrency=5):
    t = ScopeCheckThread(projects, orchestrator,
                          concurrency=concurrency)
    return t.run()