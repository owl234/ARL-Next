import os
import sys
import time
import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999

from app.modules import TaskStatus
from app import scheduler
from app.services.commonTask import TaskHeartbeat
from app.tasks import asset_wih

# WIH 采集已运行的时长，超过 cleanup_zombie_tasks 默认的 30 分钟时间窗
ELAPSED_SECONDS = 31 * 60


class MockCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    def find(self, query=None):
        return [doc for doc in self.docs if self._matches(doc, query or {})]

    def find_one(self, query=None):
        for doc in self.docs:
            if self._matches(doc, query or {}):
                return doc
        return None

    def update_one(self, query, update, upsert=False):
        for doc in self.docs:
            if self._matches(doc, query):
                doc.update(update.get("$set", {}))
                return MagicMock(matched_count=1, modified_count=1)
        return MagicMock(matched_count=0, modified_count=0)

    def _matches(self, doc, query):
        for k, v in query.items():
            if isinstance(v, dict) and "$nin" in v:
                if doc.get(k) in v["$nin"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True


class TestAssetWihHeartbeat(unittest.TestCase):
    def setUp(self):
        self.task_id = ObjectId("507f1f77bcf86cd799439031")
        self.scheduler_id = ObjectId("507f1f77bcf86cd799439033")
        self.scope_id = "507f1f77bcf86cd799439032"
        self.task_doc = {
            "_id": self.task_id,
            "status": TaskStatus.WAITING,
            "task_tag": "monitor",
            "celery_id": "wih-celery-1",
            "options": {"scheduler_id": str(self.scheduler_id)},
        }
        self.scheduler_doc = {"_id": self.scheduler_id, "status": "running", "next_run_time": 0}
        self.task_col = MockCollection([self.task_doc])
        self.scheduler_col = MockCollection([self.scheduler_doc])

    def _conn(self, table_name, db_name=None):
        if table_name == 'task':
            return self.task_col
        if table_name == 'scheduler':
            return self.scheduler_col
        return MockCollection()

    def _run_task(self, run_wih):
        with patch('app.utils.conn_db', side_effect=self._conn), \
             patch('app.scheduler.conn', side_effect=self._conn), \
             patch('app.scheduler.update_scheduler_run'), \
             patch('app.utils.clean_task_tmp_files') as clean_tmp, \
             patch('app.services.asset_wih_monitor.get_scope_by_scope_id',
                   return_value={"name": "测试资产组", "domain_array": ["example.com"]}), \
             patch('app.services.asset_wih_monitor.asset_site.find_site_by_scope_id',
                   return_value=["https://www.example.com"]), \
             patch('app.services.asset_wih_monitor.run_wih', side_effect=run_wih), \
             patch.object(asset_wih.AssetWihUpdateTask, 'insert_stat'):
            asset_wih.asset_wih_update_task(str(self.task_id), self.scope_id, str(self.scheduler_id))
        return clean_tmp

    def test_wih_task_writes_heartbeat(self):
        """WIH 监控任务执行期间写入 last_updated 与 update_date"""
        heartbeat = {}

        def run_wih(sites):
            heartbeat["last_updated"] = self.task_doc.get("last_updated")
            heartbeat["update_date"] = self.task_doc.get("update_date")
            return []

        self._run_task(run_wih)

        self.assertIsNotNone(heartbeat["last_updated"])
        self.assertIsNotNone(heartbeat["update_date"])
        self.assertEqual(self.task_doc["status"], TaskStatus.DONE)

    def test_long_running_wih_task_survives_patrol_without_inspect_reply(self):
        """WIH 采集超过 30 分钟且 Celery inspect 无响应时，巡检不应把运行中的任务判为僵尸任务"""
        real_time = time.time
        shifted_time = MagicMock(wraps=time)
        shifted_time.time = lambda: real_time() + ELAPSED_SECONDS
        inspector = MagicMock()
        inspector.active.return_value = None  # 5 秒内没有 Worker 响应
        observed = {}

        def run_wih(sites):
            # 心跳线程与调度器使用同一个时钟：采集期间心跳持续刷新，随后 10 分钟巡检正好执行
            with patch('app.services.commonTask.time', shifted_time), \
                 patch('app.scheduler.time', shifted_time), \
                 patch('app.celerytask.celery.control.inspect', return_value=inspector):
                time.sleep(0.2)
                observed["converged"] = scheduler.cleanup_zombie_tasks(window_seconds=1800)
            observed["status"] = self.task_doc["status"]
            return []

        with patch('app.tasks.asset_wih.TaskHeartbeat',
                   side_effect=lambda task_id, interval: TaskHeartbeat(task_id, interval=0.05)):
            clean_tmp = self._run_task(run_wih)

        self.assertEqual(observed["converged"], 0)
        self.assertEqual(observed["status"], "wih_monitor")
        clean_tmp.assert_not_called()
        self.assertEqual(self.scheduler_doc["next_run_time"], 0)
        self.assertEqual(self.task_doc["status"], TaskStatus.DONE)
        self.assertNotIn("end_reason", self.task_doc)


if __name__ == '__main__':
    unittest.main()
