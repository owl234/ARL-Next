# backend/app/services/vuln_platform/recon_thread.py
"""资产侦察多线程任务"""

import time

from app import utils
from app.services.baseThread import BaseThread

logger = utils.get_logger()


class AssetReconThread(BaseThread):
    """多域名并发资产侦察"""

    def __init__(self, domains, recon_config,
                 source_platform=None, project_fingerprint=None,
                 concurrency=10):
        super().__init__(targets=domains, concurrency=concurrency)
        self.recon_config = recon_config or {}
        self.source_platform = source_platform
        self.project_fingerprint = project_fingerprint
        self.assets = []

    def work(self, domain):
        from app.services.npoc import run_risk_cruising
        try:
            logger.debug("[Recon] 侦察: {}".format(domain))
            results = run_risk_cruising(
                targets=[domain],
                config=self.recon_config,
                context={
                    "project_fingerprint":
                        self.project_fingerprint,
                    "source_platform": self.source_platform,
                })
            if results:
                self.assets.extend(results)
                logger.info("[Recon] {} 发现 {} 个资产".format(
                    domain, len(results)))
        except Exception as e:
            logger.warning("[Recon] {} 侦察失败: {}".format(
                domain, e))

    def run(self):
        t1 = time.time()
        logger.info("start asset recon, project:{}, domains:{}"
                    .format(self.project_fingerprint,
                            len(self.targets)))
        self._run()
        elapse = time.time() - t1
        logger.info("end asset recon ({:.2f}s), assets:{}"
                    .format(elapse, len(self.assets)))
        return self.assets


def asset_recon_thread(domains, recon_config, source_platform=None,
                        project_fingerprint=None, concurrency=10):
    t = AssetReconThread(
        domains=domains,
        recon_config=recon_config,
        source_platform=source_platform,
        project_fingerprint=project_fingerprint,
        concurrency=concurrency)
    return t.run()