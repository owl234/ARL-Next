import unittest
from unittest.mock import MagicMock, patch
import os
import sys
import time
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError
from celery.exceptions import MaxRetriesExceededError, Retry

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)


# Bypass mongo lookups during initial config import
import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999

# Prevent pymongo connection attempt during utils import
import pymongo
pymongo.MongoClient = MagicMock()

from app.modules import TaskStatus, SchedulerStatus, AssetScopeType
from app import utils
from app import scheduler
from app.tasks import scheduler as task_scheduler


class MockCollection:
    def __init__(self, docs=None):
        self.docs = docs or []
        self.update_calls = []
        self.delete_calls = []

    def find(self, query=None):
        query = query or {}
        return [doc for doc in self.docs if self._matches(doc, query)]

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

    def delete_many(self, query):
        self.delete_calls.append(query)
        initial_len = len(self.docs)
        self.docs = [doc for doc in self.docs if not self._matches(doc, query)]
        return MagicMock(deleted_count=initial_len - len(self.docs))

    def count_documents(self, query):
        return len(self.find(query))

    def bulk_write(self, requests):
        return MagicMock(modified_count=len(requests))

    def _matches(self, doc, query):
        for k, v in query.items():
            if k == "_id":
                if str(doc.get("_id")) != str(v):
                    return False
            elif k == "status" and isinstance(v, dict) and "$nin" in v:
                if doc.get("status") in v["$nin"]:
                    return False
            elif k == "next_run_time" and isinstance(v, dict) and "$lte" in v:
                if doc.get("next_run_time", 0) > v["$lte"]:
                    return False
            elif k.startswith("options."):
                sub_key = k.split(".", 1)[1]
                if doc.get("options", {}).get(sub_key) != v:
                    return False
            else:
                if doc.get(k) != v:
                    return False
        return True


class TestIssue48ScopeScheduler(unittest.TestCase):
    def setUp(self):
        from app.config import Config
        Config.AUTH = False
        self.scope_id = ObjectId("6ab083824b32130de93a9438")
        self.scope_id_str = str(self.scope_id)

        self.mock_asset_scope = MockCollection([
            {
                "_id": self.scope_id,
                "name": "test_scope",
                "scope_array": ["alpha.example.com", "beta.example.com"],
                "domain_array": ["alpha.example.com", "beta.example.com"],
                "ip_array": [],
                "domain_status": {"alpha.example.com": {}, "beta.example.com": {}}
            }
        ])

        self.mock_scheduler = MockCollection([
            {
                "_id": ObjectId("6ab083827f11ac36493a9436"),
                "scope_id": self.scope_id_str,
                "domain": "alpha.example.com",
                "scope_type": AssetScopeType.DOMAIN,
                "status": SchedulerStatus.RUNNING,
                "next_run_time": int(time.time()) - 100,
                "interval": 3600
            }
        ])

        self.mock_task = MockCollection([])

        self.db_collections = {
            "asset_scope": self.mock_asset_scope,
            "scheduler": self.mock_scheduler,
            "task": self.mock_task,
            "asset_domain": MockCollection([]),
            "asset_ip": MockCollection([]),
            "asset_site": MockCollection([]),
            "asset_wih": MockCollection([])
        }

    def mock_conn(self, table_name):
        if table_name not in self.db_collections:
            self.db_collections[table_name] = MockCollection([])
        return self.db_collections[table_name]

    @patch("app.utils.conn_db")
    def test_single_scope_delete_cascades_scheduler(self, mock_conn_db):
        mock_conn_db.side_effect = self.mock_conn
        from app.routes.assetScope import DeleteARLAssetScope

        resource = DeleteARLAssetScope()
        resource.parser = MagicMock()
        resource.parser.parse_args.return_value = {
            "scope_id": self.scope_id_str,
            "scope": "alpha.example.com"
        }

        with patch.object(DeleteARLAssetScope, "get_scope_data", return_value=self.mock_asset_scope.find_one({"_id": self.scope_id})):
            resp = resource.get()

        self.assertEqual(resp["code"], 200)
        # Check that alpha.example.com was removed from scope_array
        scope_doc = self.mock_asset_scope.find_one({"_id": self.scope_id})
        self.assertNotIn("alpha.example.com", scope_doc["scope_array"])

        # Check that scheduler collection was queried to delete alpha.example.com
        sched_doc = self.mock_scheduler.find_one({"domain": "alpha.example.com"})
        self.assertIsNone(sched_doc, "scheduler document should be cascade deleted")

    @patch("app.utils.conn_db")
    def test_update_scope_diff_cascades_scheduler(self, mock_conn_db):
        mock_conn_db.side_effect = self.mock_conn
        from app.routes.assetScope import UpdateARLAssetScope

        resource = UpdateARLAssetScope()
        resource.parse_args = MagicMock(return_value={
            "_id": self.scope_id_str,
            "scope": "beta.example.com",  # alpha removed
            "name": "test_scope"
        })

        resp = resource.post()
        self.assertEqual(resp["code"], 200)

        # Scheduler for alpha should be deleted
        sched_doc = self.mock_scheduler.find_one({"domain": "alpha.example.com"})
        self.assertIsNone(sched_doc, "scheduler document should be cascade deleted on scope update diff")

    @patch("app.scheduler.conn")
    @patch("app.celerytask.arl_task.apply_async")
    def test_scheduler_detects_orphan_and_auto_deletes(self, mock_apply_async, mock_conn):
        mock_conn.side_effect = self.mock_conn

        # Case 1: Scope does not exist
        orphan_sched_1 = {
            "_id": ObjectId("6ab083827f11ac36493a9499"),
            "scope_id": str(ObjectId("6ab083827f11ac36493a9488")), # nonexistent
            "domain": "orphan.com",
            "scope_type": AssetScopeType.DOMAIN,
            "status": SchedulerStatus.RUNNING,
            "next_run_time": int(time.time()) - 50,
            "interval": 3600
        }
        # Case 2: Target not in scope_array
        orphan_sched_2 = {
            "_id": ObjectId("6ab083827f11ac36493a9498"),
            "scope_id": self.scope_id_str,
            "domain": "deleted.example.com", # not in scope_array
            "scope_type": AssetScopeType.DOMAIN,
            "status": SchedulerStatus.RUNNING,
            "next_run_time": int(time.time()) - 50,
            "interval": 3600
        }
        self.mock_scheduler.docs = [orphan_sched_1, orphan_sched_2]

        scheduler.asset_monitor_scheduler()

        # Both orphan schedulers should be auto-deleted
        self.assertEqual(len(self.mock_scheduler.docs), 0)
        # Celery apply_async should NEVER be called for orphans
        mock_apply_async.assert_not_called()

    @patch("app.utils.conn_db")
    def test_worker_domain_executors_drops_invalid_scope_target(self, mock_conn_db):
        mock_conn_db.side_effect = self.mock_conn

        with patch("app.tasks.scheduler.wrap_domain_executors") as mock_wrap:
            # Call domain_executors with a target that is NOT in scope_array
            task_scheduler.domain_executors(
                base_domain="not_in_scope.com",
                scheduler_id=str(self.mock_scheduler.docs[0]["_id"]),
                scope_id=self.scope_id_str
            )
            # wrap_domain_executors must NOT be called
            mock_wrap.assert_not_called()

            # Call domain_executors with a VALID target
            task_scheduler.domain_executors(
                base_domain="alpha.example.com",
                scheduler_id=str(self.mock_scheduler.docs[0]["_id"]),
                scope_id=self.scope_id_str
            )
            # wrap_domain_executors MUST be called
            mock_wrap.assert_called_once()

    @patch("app.utils.conn_db")
    @patch("app.tasks.scheduler.conn")
    def test_worker_ip_executor_drops_invalid_and_prunes_composite(self, mock_conn_scheduler, mock_conn_db):
        mock_conn_db.side_effect = self.mock_conn
        mock_conn_scheduler.side_effect = self.mock_conn

        # Set up an IP scope
        ip_scope_id = ObjectId("6ab083824b32130de93a9439")
        ip_scope_id_str = str(ip_scope_id)
        self.mock_asset_scope.docs.append({
            "_id": ip_scope_id,
            "name": "ip_scope",
            "scope_array": ["192.168.1.1", "192.168.1.2"],
            "ip_array": ["192.168.1.1", "192.168.1.2"]
        })

        ip_sched_id = ObjectId("6ab083827f11ac36493a9437")
        self.mock_scheduler.docs.append({
            "_id": ip_sched_id,
            "scope_id": ip_scope_id_str,
            "domain": "192.168.1.1 192.168.1.99",
            "scope_type": AssetScopeType.IP,
            "status": SchedulerStatus.RUNNING
        })

        with patch("app.tasks.scheduler.IPExecutor") as MockIPExecutor, \
             patch("app.tasks.scheduler.update_scheduler_run"):
            mock_instance = MagicMock()
            MockIPExecutor.return_value = mock_instance

            # Case 1: Target completely invalid
            task_scheduler.ip_executor(
                target="10.0.0.1",
                scope_id=ip_scope_id_str,
                task_name="test",
                scheduler_id=str(ip_sched_id),
                options={}
            )
            mock_instance.run.assert_not_called()

            # Case 2: Composite target contains 1 valid (192.168.1.1) and 1 removed (192.168.1.99)
            task_scheduler.ip_executor(
                target="192.168.1.1 192.168.1.99",
                scope_id=ip_scope_id_str,
                task_name="test",
                scheduler_id=str(ip_sched_id),
                options={}
            )
            # Should run with pruned target "192.168.1.1"
            MockIPExecutor.assert_called_with("192.168.1.1", ip_scope_id_str, "test", str(ip_sched_id), {})
            mock_instance.run.assert_called_once()

    @patch("app.utils.conn_db")
    def test_worker_domain_executors_drops_on_invalid_id(self, mock_conn_db):
        mock_conn_db.side_effect = self.mock_conn

        with patch("app.tasks.scheduler.wrap_domain_executors") as mock_wrap:
            task_scheduler.domain_executors(
                base_domain="alpha.example.com",
                scheduler_id=str(self.mock_scheduler.docs[0]["_id"]),
                scope_id="invalid-not-hex-id"
            )
            mock_wrap.assert_not_called()

    @patch("app.utils.conn_db")
    def test_worker_domain_executors_retries_on_pymongo_error(self, mock_conn_db):
        mock_conn_db.side_effect = self.mock_conn

        with patch("app.tasks.scheduler.wrap_domain_executors") as mock_wrap, \
             patch("app.tasks.scheduler.current_task") as mock_celery_task, \
             patch.object(self.mock_asset_scope, "find_one", side_effect=PyMongoError("DB connection error")):

            mock_task_obj = MagicMock()
            mock_task_obj.retry.side_effect = Retry("Simulated Celery Retry")
            mock_celery_task._get_current_object.return_value = mock_task_obj

            with self.assertRaises(Retry):
                task_scheduler.domain_executors(
                    base_domain="alpha.example.com",
                    scheduler_id=str(self.mock_scheduler.docs[0]["_id"]),
                    scope_id=self.scope_id_str
                )
            mock_task_obj.retry.assert_called_once()
            self.assertEqual(mock_task_obj.retry.call_args[1].get("countdown"), 30)
            self.assertEqual(mock_task_obj.retry.call_args[1].get("max_retries"), 3)
            mock_wrap.assert_not_called()

    @patch("app.utils.conn_db")
    def test_worker_domain_executors_drops_on_max_retries_exceeded(self, mock_conn_db):
        mock_conn_db.side_effect = self.mock_conn

        with patch("app.tasks.scheduler.wrap_domain_executors") as mock_wrap, \
             patch("app.tasks.scheduler.current_task") as mock_celery_task, \
             patch.object(self.mock_asset_scope, "find_one", side_effect=PyMongoError("DB connection error")):

            mock_task_obj = MagicMock()
            mock_task_obj.retry.side_effect = MaxRetriesExceededError()
            mock_celery_task._get_current_object.return_value = mock_task_obj

            task_scheduler.domain_executors(
                base_domain="alpha.example.com",
                scheduler_id=str(self.mock_scheduler.docs[0]["_id"]),
                scope_id=self.scope_id_str
            )
            mock_wrap.assert_not_called()

    @patch("app.utils.conn_db")
    @patch("app.tasks.scheduler.conn")
    def test_worker_ip_executor_drops_on_invalid_id(self, mock_conn_scheduler, mock_conn_db):
        mock_conn_db.side_effect = self.mock_conn
        mock_conn_scheduler.side_effect = self.mock_conn

        with patch("app.tasks.scheduler.IPExecutor") as MockIPExecutor, \
             patch("app.tasks.scheduler.update_scheduler_run"):
            mock_instance = MagicMock()
            MockIPExecutor.return_value = mock_instance

            task_scheduler.ip_executor(
                target="1.1.1.1",
                scope_id="invalid-not-hex-id",
                task_name="test",
                scheduler_id=str(self.mock_scheduler.docs[0]["_id"]),
                options={}
            )
            mock_instance.run.assert_not_called()

    @patch("app.utils.conn_db")
    @patch("app.tasks.scheduler.conn")
    def test_worker_ip_executor_retries_on_pymongo_error(self, mock_conn_scheduler, mock_conn_db):
        mock_conn_db.side_effect = self.mock_conn
        mock_conn_scheduler.side_effect = self.mock_conn

        with patch("app.tasks.scheduler.IPExecutor") as MockIPExecutor, \
             patch("app.tasks.scheduler.update_scheduler_run"), \
             patch("app.tasks.scheduler.current_task") as mock_celery_task, \
             patch.object(self.mock_asset_scope, "find_one", side_effect=PyMongoError("DB lost")):

            mock_instance = MagicMock()
            MockIPExecutor.return_value = mock_instance
            mock_task_obj = MagicMock()
            mock_task_obj.retry.side_effect = Retry("Simulated Celery Retry")
            mock_celery_task._get_current_object.return_value = mock_task_obj

            with self.assertRaises(Retry):
                task_scheduler.ip_executor(
                    target="1.1.1.1",
                    scope_id=self.scope_id_str,
                    task_name="test",
                    scheduler_id=str(self.mock_scheduler.docs[0]["_id"]),
                    options={}
                )
            mock_task_obj.retry.assert_called_once()
            self.assertEqual(mock_task_obj.retry.call_args[1].get("countdown"), 30)
            self.assertEqual(mock_task_obj.retry.call_args[1].get("max_retries"), 3)
            mock_instance.run.assert_not_called()

    @patch("app.utils.conn_db")
    @patch("app.scheduler.conn")
    def test_scheduler_gate2_preserves_on_pymongo_error_and_deletes_on_invalid_id(self, mock_conn_scheduler, mock_conn_db):
        mock_conn_db.side_effect = self.mock_conn
        mock_conn_scheduler.side_effect = self.mock_conn

        sched_doc = {
            "_id": ObjectId("6ab083827f11ac36493a9499"),
            "scope_id": self.scope_id_str,
            "domain": "alpha.example.com",
            "scope_type": AssetScopeType.DOMAIN,
            "status": SchedulerStatus.RUNNING,
            "next_run_time": int(time.time()) - 50,
            "interval": 3600
        }
        self.mock_scheduler.docs = [sched_doc]

        # Case 1: PyMongoError during scheduler check -> should NOT delete scheduler
        with patch.object(self.mock_asset_scope, "find_one", side_effect=PyMongoError("DB network error")):
            scheduler.asset_monitor_scheduler()
            self.assertEqual(len(self.mock_scheduler.docs), 1)

        # Case 2: InvalidId -> should delete orphan scheduler
        self.mock_scheduler.docs[0]["scope_id"] = "invalid-not-hex-id"
        with patch.object(self.mock_asset_scope, "find_one", side_effect=InvalidId("Bad ObjectId")):
            scheduler.asset_monitor_scheduler()
            self.assertEqual(len(self.mock_scheduler.docs), 0)


if __name__ == "__main__":
    unittest.main()
