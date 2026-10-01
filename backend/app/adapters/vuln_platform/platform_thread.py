# backend/app/adapters/vuln_platform/platform_thread.py
"""
漏洞平台抓取多线程任务（继承 BaseThread）
- PlatformFetchThread: 多平台并发抓取
- ScopeFetchThread: 单平台内多项目范围并发抓取
"""

import time

from app import utils
from app.services.baseThread import BaseThread
from app.adapters.vuln_platform import get_adapter, \
    get_enabled_platforms

logger = utils.get_logger()


class PlatformFetchThread(BaseThread):
    """多平台并发抓取线程"""

    def __init__(self, db, platforms=None, concurrency=4):
        if platforms is None:
            platforms = get_enabled_platforms()
        super().__init__(targets=platforms, concurrency=concurrency)
        self.db = db
        self.platform_projects_map = {}
        self.platform_error_map = {}

    def work(self, platform_name):
        """抓取单个平台的项目列表"""
        logger.info("[Fetch] 开始抓取平台: {}".format(platform_name))
        try:
            adapter = get_adapter(platform_name, db=self.db)
            projects = adapter.fetch_projects() or []
            self.platform_projects_map[platform_name] = projects
            logger.info("[Fetch] {} 抓取完成: {} 个项目".format(
                platform_name, len(projects)))
        except Exception as e:
            self.platform_error_map[platform_name] = str(e)
            logger.warning("[Fetch] {} 抓取失败: {}".format(
                platform_name, e))

    def run(self):
        t1 = time.time()
        logger.info("start platform fetch, platforms:{}".format(
            len(self.targets)))
        self._run()
        elapse = time.time() - t1
        logger.info("end platform fetch ({:.2f}s)".format(elapse))
        return {
            "projects": self.platform_projects_map,
            "errors": self.platform_error_map,
        }


class ScopeFetchThread(BaseThread):
    """单平台内多项目范围并发抓取"""

    def __init__(self, adapter, project_ids, concurrency=4):
        super().__init__(targets=project_ids, concurrency=concurrency)
        self.adapter = adapter
        self.scope_map = {}

    def work(self, project_id):
        """抓取单个项目的测试范围"""
        try:
            scope = self.adapter.fetch_scope(project_id) or []
            self.scope_map[project_id] = scope
            logger.debug("[Scope] {}/{} 范围: {} 个目标".format(
                self.adapter.platform_name, project_id, len(scope)))
        except Exception as e:
            logger.warning("[Scope] {}/{} 抓取失败: {}".format(
                self.adapter.platform_name, project_id, e))
            self.scope_map[project_id] = []

    def run(self):
        t1 = time.time()
        logger.info("start scope fetch [{}], projects:{}".format(
            self.adapter.platform_name, len(self.targets)))
        self._run()
        elapse = time.time() - t1
        logger.info("end scope fetch [{}] ({:.2f}s)".format(
            self.adapter.platform_name, elapse))
        return self.scope_map


def platform_fetch_thread(db, platforms=None, concurrency=4):
    """多平台并发抓取入口"""
    t = PlatformFetchThread(db, platforms=platforms,
                             concurrency=concurrency)
    return t.run()


def scope_fetch_thread(adapter, project_ids, concurrency=4):
    """单平台多项目范围抓取入口"""
    t = ScopeFetchThread(adapter, project_ids,
                         concurrency=concurrency)
    return t.run()