# backend/app/adapters/vuln_platform/cookie_thread.py
"""Cookie 健康检查多线程任务"""

import time

from app import utils
from app.services.baseThread import BaseThread
from app.adapters.vuln_platform import get_adapter
from app.adapters.vuln_platform.config import PLATFORM_CONFIG

logger = utils.get_logger()


class CookieHealthThread(BaseThread):
    """多平台并发检查 Cookie 有效性"""

    def __init__(self, db, platforms=None, concurrency=5):
        if platforms is None:
            platforms = [
                name for name, cfg in PLATFORM_CONFIG.items()
                if cfg.get("requires_login") and cfg.get("enabled")
            ]
        super().__init__(targets=platforms, concurrency=concurrency)
        self.db = db
        self.invalid_platforms = []

    def work(self, platform_name):
        """检查单个平台的 Cookie"""
        try:
            adapter = get_adapter(platform_name, db=self.db)
            if not adapter.cookie_mgr:
                return

            test_url = PLATFORM_CONFIG[platform_name].get(
                "test_url", "")
            if not adapter.cookie_mgr.is_cookie_valid(test_url):
                self.invalid_platforms.append(platform_name)
                logger.warning("[CookieCheck] {} Cookie 已失效"
                               .format(platform_name))
            else:
                logger.debug("[CookieCheck] {} Cookie 有效"
                             .format(platform_name))
        except Exception as e:
            logger.warning("[CookieCheck] {} 检查异常: {}".format(
                platform_name, e))

    def run(self):
        t1 = time.time()
        logger.info("start cookie health check, platforms:{}"
                    .format(len(self.targets)))
        self._run()
        elapse = time.time() - t1
        logger.info("end cookie health check ({:.2f}s), invalid:{}"
                    .format(elapse, self.invalid_platforms))
        return self.invalid_platforms


def cookie_health_thread(db, platforms=None, concurrency=5):
    """Cookie 健康检查并发入口"""
    t = CookieHealthThread(db, platforms=platforms,
                            concurrency=concurrency)
    return t.run()