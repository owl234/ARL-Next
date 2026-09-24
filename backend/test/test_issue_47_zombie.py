import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import time
from bson import ObjectId

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Bypass mongo lookups during initial config import
import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999

from app.modules import TaskStatus
from app import utils
from app import scheduler
from app.utils import arlupdate


class MockCollection:
    def __init__(self, docs=None):
        self.docs = docs or []
        self.update_calls = []
        self.delete_calls = []

    def find(self, query=None):
        query = query or {}
        results = []
        for doc in self.docs:
            if self._matches(doc, query):
                results.append(doc)
        return results

    def find_one(self, query=None):
        query = query or {}
        for doc in self.docs:
            if self._matches(doc, query):
                return doc
        return None

    def update_one(self, query, update, upsert=False):
        self.update_calls.append((query, update))
        for doc in self.docs:
            if self._matches(doc, query):
                if "$set" in update:
                    doc.update(update["$set"])
                return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)

    def delete_one(self, query):
        self.delete_calls.append(query)
        for i, doc in enumerate(self.docs):
            if self._matches(doc, query):
                self.docs.pop(i)
                return MagicMock(deleted_count=1)
        return MagicMock(deleted_count=0)

    def _matches(self, doc, query):
        for k, v in query.items():
            if k == "_id":
                if doc.get("_id") != v:
                    return False
            elif isinstance(v, dict):
                if "$nin" in v:
                    if doc.get(k) in v["$nin"]:
                        return False
                if "$in" in v:
                    if doc.get(k) not in v["$in"]:
                        return False
            else:
                if doc.get(k) != v:
                    return False
        return True


class TestIssue47ZombieTasks(unittest.TestCase):
    def setUp(self):
        self.mock_task_col = MockCollection()
        self.mock_scheduler_col = MockCollection()
        self.mock_init_lock_col = MockCollection([{"_id": "init_lock", "status": "idle", "last_completed_at": 0}])

    def _mock_conn(self, table_name, db_name=None):
        if table_name == 'task':
            return self.mock_task_col
        elif table_name == 'scheduler':
            return self.mock_scheduler_col
        elif table_name == 'init_lock':
            return self.mock_init_lock_col
        return MockCollection()

    def test_task2_gunicorn_preload_in_start_script(self):
        """验证 start_web_prod.sh 中已配置 gunicorn --preload"""
        script_path = os.path.join(backend_dir, 'start_web_prod.sh')
        self.assertTrue(os.path.exists(script_path), f"{script_path} must exist")
        with open(script_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查是否包含 gunicorn 且带 --preload 参数
        gunicorn_lines = [line for line in content.splitlines() if line.strip().startswith('gunicorn')]
        self.assertTrue(len(gunicorn_lines) > 0, "Must contain a gunicorn execution command")
        gunicorn_cmd = gunicorn_lines[0]
        self.assertIn('--preload', gunicorn_cmd, "Gunicorn command must include --preload")
        self.assertIn('app.main:arl_app', gunicorn_cmd, "Gunicorn must target app.main:arl_app")

    def test_task1_arlupdate_cleanup_zombie_tasks_is_deprecated_noop(self):
        """验证 arlupdate.cleanup_zombie_tasks 已完全弃用且为空操作"""
        with patch('app.utils.arlupdate.conn_db') as mock_conn:
            # 直接调用 arlupdate 中的函数
            arlupdate.cleanup_zombie_tasks()
            # 必须没有任何数据库交互
            mock_conn.assert_not_called()

    def test_task1_arl_update_does_not_modify_active_tasks(self):
        """验证 arl_update() 执行流水线不再篡改任何运行中的活跃任务"""
        active_task = {
            "_id": ObjectId("507f1f77bcf86cd799439011"),
            "name": "active_scan_1",
            "target": "example.com",
            "status": "domain_brute",
            "task_tag": "task",
            "start_time": utils.curr_date(),
            "celery_id": "active-celery-1"
        }
        self.mock_task_col.docs = [active_task]

        with patch('app.utils.conn_db', side_effect=self._mock_conn),              patch('app.utils.arlupdate.conn_db', side_effect=self._mock_conn),              patch('app.utils.arlupdate.ensure_builtin_dicts'),              patch('app.utils.arlupdate.fingerprint_info_update'),              patch('app.utils.arlupdate.create_index'),              patch('app.utils.arlupdate.npoc_info_update'),              patch('app.utils.arlupdate.cleanup_asset_scope_dead_fields'),              patch('app.utils.arlupdate.migrate_asset_scope_domain_status'),              patch('app.utils.arlupdate.migrate_asset_site_pending_test_tag'),              patch('app.utils.arlupdate.heal_historical_invalid_sites'),              patch('app.utils.arlupdate.migrate_asset_cip_merge'),              patch('app.utils.arlupdate.migrate_geo_ip_data'),              patch('app.utils.arlupdate.heal_polluted_site_fingers'),              patch('app.utils.arlupdate.backfill_icp_task_synced_scopes'),              patch('app.utils.arlupdate.migrate_asset_group_sort_order'):
            
            arlupdate.arl_update()

        # 验证 active_task 状态完好如初，依然是 domain_brute
        self.assertEqual(active_task["status"], "domain_brute")
        # 验证 task collection 绝对没有触发 delete_one
        self.assertEqual(len(self.mock_task_col.delete_calls), 0)
        # 验证没有把 active_task 改为 ERROR
        for query, update in self.mock_task_col.update_calls:
            if "$set" in update:
                self.assertNotEqual(update["$set"].get("status"), TaskStatus.ERROR)

    def test_task3_scheduler_skips_celery_active_task(self):
        """验证调度器探测到 Celery 活跃任务时，严格跳过收敛"""
        task_id = ObjectId("507f1f77bcf86cd799439012")
        celery_id = "live-celery-task-999"
        # 即使任务已经运行超过 30 分钟 (例如 2 小时前开始)
        old_time = utils.time2date(time.time() - 7200)
        task_doc = {
            "_id": task_id,
            "status": "port_scan",
            "task_tag": "task",
            "celery_id": celery_id,
            "start_time": old_time
        }
        self.mock_task_col.docs = [task_doc]

        mock_inspector = MagicMock()
        mock_inspector.active.return_value = {
            "worker1@host": [{"id": celery_id, "name": "arl_task"}]
        }

        with patch('app.scheduler.conn', side_effect=self._mock_conn), \
             patch('app.celerytask.celery.control.inspect', return_value=mock_inspector), \
             patch('app.utils.clean_task_tmp_files') as mock_clean:
            
            converged = scheduler.cleanup_zombie_tasks()

        self.assertEqual(converged, 0)
        self.assertEqual(task_doc["status"], "port_scan")
        self.assertEqual(len(self.mock_task_col.update_calls), 0)
        self.assertEqual(len(self.mock_task_col.delete_calls), 0)
        mock_clean.assert_not_called()

    def test_task3_scheduler_skips_heartbeat_window_task(self):
        """验证处于 30 分钟心跳时间窗内的任务，即使 Celery Inspect 超时/为空，也严禁误杀"""
        task_id = ObjectId("507f1f77bcf86cd799439013")
        recent_time = utils.time2date(time.time() - 300) # 5分钟前启动
        task_doc = {
            "_id": task_id,
            "status": "find_site",
            "task_tag": "task",
            "celery_id": "untracked-or-starting-celery-id",
            "start_time": recent_time
        }
        self.mock_task_col.docs = [task_doc]

        # 模拟 Celery inspect 超时或返回空（无法查到 worker）
        mock_inspector = MagicMock()
        mock_inspector.active.return_value = {}

        with patch('app.scheduler.conn', side_effect=self._mock_conn), \
             patch('app.celerytask.celery.control.inspect', return_value=mock_inspector), \
             patch('app.utils.clean_task_tmp_files') as mock_clean:
            
            converged = scheduler.cleanup_zombie_tasks(window_seconds=1800)

        self.assertEqual(converged, 0)
        self.assertEqual(task_doc["status"], "find_site")
        self.assertEqual(len(self.mock_task_col.update_calls), 0)
        mock_clean.assert_not_called()

    def test_task3_scheduler_converges_dead_regular_task(self):
        """验证真正超时的死亡普通任务被收敛为 ERROR，记录终止原因且不被物理删除"""
        task_id = ObjectId("507f1f77bcf86cd799439014")
        dead_time = utils.time2date(time.time() - 3600) # 1小时前
        task_doc = {
            "_id": task_id,
            "status": "port_scan",
            "task_tag": "task",
            "celery_id": "dead-celery-id-888",
            "start_time": dead_time
        }
        self.mock_task_col.docs = [task_doc]

        mock_inspector = MagicMock()
        mock_inspector.active.return_value = {}

        with patch('app.scheduler.conn', side_effect=self._mock_conn), \
             patch('app.celerytask.celery.control.inspect', return_value=mock_inspector), \
             patch('app.utils.clean_task_tmp_files') as mock_clean:
            
            converged = scheduler.cleanup_zombie_tasks(window_seconds=1800)

        self.assertEqual(converged, 1)
        self.assertEqual(task_doc["status"], TaskStatus.ERROR)
        self.assertEqual(task_doc["end_reason"], "服务重启/异常中断")
        self.assertTrue(task_doc.get("end_time"))
        # 绝不物理删除普通任务
        self.assertEqual(len(self.mock_task_col.delete_calls), 0)
        mock_clean.assert_called_once_with(str(task_id))

    def test_task3_scheduler_converges_dead_monitor_task_without_deletion(self):
        """验证失活监控任务被置为 ERROR 且文档保留审计（严禁 delete_one），平滑延后调度"""
        task_id = ObjectId("507f1f77bcf86cd799439015")
        scheduler_id = ObjectId("507f1f77bcf86cd799439099")
        dead_time = utils.time2date(time.time() - 3600)
        task_doc = {
            "_id": task_id,
            "status": "domain_brute",
            "task_tag": "monitor",
            "celery_id": "dead-monitor-celery-111",
            "start_time": dead_time,
            "options": {"scheduler_id": str(scheduler_id)}
        }
        scheduler_doc = {
            "_id": scheduler_id,
            "status": "running",
            "next_run_time": 1000
        }
        self.mock_task_col.docs = [task_doc]
        self.mock_scheduler_col.docs = [scheduler_doc]

        mock_inspector = MagicMock()
        mock_inspector.active.return_value = {}

        before_time = int(time.time())

        with patch('app.scheduler.conn', side_effect=self._mock_conn), \
             patch('app.celerytask.celery.control.inspect', return_value=mock_inspector), \
             patch('app.utils.clean_task_tmp_files') as mock_clean:
            
            converged = scheduler.cleanup_zombie_tasks(window_seconds=1800)

        after_time = int(time.time())

        self.assertEqual(converged, 1)
        # 1. 验证严禁调用 delete_one！任务文档依然保留
        self.assertEqual(len(self.mock_task_col.delete_calls), 0, "conn('task').delete_one must NEVER be called!")
        self.assertEqual(len(self.mock_task_col.docs), 1, "Monitor task document must be preserved!")
        
        # 2. 验证状态更新为 ERROR，并记录原因
        self.assertEqual(task_doc["status"], TaskStatus.ERROR)
        self.assertEqual(task_doc["end_reason"], "服务重启/异常中断")
        self.assertTrue(task_doc.get("end_time"))

        # 3. 验证 scheduler 的 next_run_time 延后到 60 秒后重新调度
        self.assertGreaterEqual(scheduler_doc["next_run_time"], before_time + 60)
        self.assertLessEqual(scheduler_doc["next_run_time"], after_time + 65)
        mock_clean.assert_called_once_with(str(task_id))

    def test_task3_scheduler_inspect_exception_tolerance(self):
        """验证 Celery Inspect 出现网络异常或超时异常时的容错韧性"""
        recent_id = ObjectId("507f1f77bcf86cd799439016")
        dead_id = ObjectId("507f1f77bcf86cd799439017")
        now = time.time()
        
        recent_task = {
            "_id": recent_id,
            "status": "port_scan",
            "celery_id": "recent-celery",
            "start_time": utils.time2date(now - 300)
        }
        dead_task = {
            "_id": dead_id,
            "status": "port_scan",
            "celery_id": "dead-celery",
            "start_time": utils.time2date(now - 3600)
        }
        self.mock_task_col.docs = [recent_task, dead_task]

        # 模拟 inspect 抛出网络/连接异常
        mock_inspect = MagicMock(side_effect=Exception("RabbitMQ Broker Unreachable"))

        with patch('app.scheduler.conn', side_effect=self._mock_conn), \
             patch('app.celerytask.celery.control.inspect', mock_inspect), \
             patch('app.utils.clean_task_tmp_files'):

            
            converged = scheduler.cleanup_zombie_tasks(window_seconds=1800)

        # 仅超时任务被收敛，心跳窗口内任务得以保护
        self.assertEqual(converged, 1)
        self.assertEqual(recent_task["status"], "port_scan")
        self.assertEqual(dead_task["status"], TaskStatus.ERROR)

    def test_task4_task_heartbeat_updates_mongo_timestamp(self):
        """验证 TaskHeartbeat 心跳守护线程在任务阶段执行中定时刷新 last_updated 与 update_date"""
        from app.services.commonTask import TaskHeartbeat
        task_id = ObjectId("507f1f77bcf86cd799439099")
        task_doc = {"_id": task_id, "status": "nuclei_scan"}
        self.mock_task_col.docs = [task_doc]

        with patch('app.utils.conn_db', side_effect=self._mock_conn):
            with TaskHeartbeat(str(task_id), interval=0.05):
                time.sleep(0.12)

        self.assertTrue(len(self.mock_task_col.update_calls) >= 1)
        self.assertTrue(task_doc.get("last_updated"))
        self.assertTrue(task_doc.get("update_date"))

    def test_task4_cleanup_orphan_tmp_files_default_7_days(self):
        """验证 cleanup_orphan_tmp_files 默认保护窗口已扩展为 7 天 (604800s)"""
        import inspect
        sig = inspect.signature(scheduler.cleanup_orphan_tmp_files)
        default_val = sig.parameters['max_age_seconds'].default
        self.assertEqual(default_val, 604800)

    def test_task5_task_heartbeat_zero_delay_flush_on_enter_and_exit(self):
        """验证 TaskHeartbeat 在进入(__enter__)与退出(__exit__)时立即落库，无60秒等待空白"""
        from app.services.commonTask import TaskHeartbeat
        task_id = ObjectId("507f1f77bcf86cd799439098")
        task_doc = {"_id": task_id, "status": "domain_brute"}
        self.mock_task_col.docs = [task_doc]

        with patch('app.utils.conn_db', side_effect=self._mock_conn):
            # interval 设为 3600 秒，但依靠 __enter__ 立即落库
            with TaskHeartbeat(str(task_id), interval=3600):
                self.assertIsNotNone(task_doc.get("last_updated"), "Must immediately flush on enter!")
                self.assertIsNotNone(task_doc.get("update_date"), "Must immediately flush on enter!")
                first_ts = task_doc["last_updated"]

        # 验证 __exit__ 也会补齐一次更新
        self.assertGreaterEqual(len(self.mock_task_col.update_calls), 2)
        self.assertGreaterEqual(task_doc["last_updated"], first_ts)

    def test_task5_clean_task_tmp_files_only_cleans_disk_not_db(self):
        """验证 clean_task_tmp_files 仅清理磁盘临时目录，严禁删除 MongoDB 资产数据"""
        from app import utils
        task_id = "507f1f77bcf86cd799439097"

        with patch('shutil.rmtree') as mock_rmtree, \
             patch('os.path.exists', return_value=True), \
             patch('os.listdir', return_value=[f"{task_id}.tmp", "other.txt"]), \
             patch('os.unlink') as mock_unlink, \
             patch('app.utils.conn_db', side_effect=self._mock_conn):

            utils.clean_task_tmp_files(task_id)

            # 验证磁盘清理调用
            self.assertTrue(mock_rmtree.called or mock_unlink.called)
            # 验证 MongoDB 绝对未被调用 delete
            self.assertEqual(len(self.mock_task_col.delete_calls), 0)

    def test_task5_cleanup_zombie_tasks_uses_timeout_5(self):
        """验证 Celery Inspect 探针超时设置为 5.0 秒"""
        task_id = ObjectId("507f1f77bcf86cd799439096")
        self.mock_task_col.docs = [{
            "_id": task_id,
            "status": "port_scan",
            "celery_id": "dummy-celery-1",
            "start_time": utils.time2date(time.time() - 3600)
        }]
        mock_inspect = MagicMock()
        mock_inspect.return_value.active.return_value = {}

        with patch('app.scheduler.conn', side_effect=self._mock_conn), \
             patch('app.celerytask.celery.control.inspect', mock_inspect), \
             patch('app.utils.clean_task_tmp_files'):
            scheduler.cleanup_zombie_tasks(window_seconds=1800)

        mock_inspect.assert_called_with(timeout=5.0)


    def test_task5_scheduler_run_forever_has_10min_periodic_clean(self):
        """验证 run_forever 包含每 10 分钟 (600秒) 周期性巡检收敛逻辑"""
        import inspect
        source = inspect.getsource(scheduler.run_forever)
        self.assertIn("last_zombie_clean", source)
        self.assertIn("600", source)
        self.assertIn("cleanup_zombie_tasks(window_seconds=1800)", source)


if __name__ == '__main__':
    unittest.main()


