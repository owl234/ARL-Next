"""方案 A：任务资产产出筛选、高级数值比较修复、终态统计补写与存量后台回填回归测试。"""
import copy
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from bson import ObjectId
import mongomock

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.routes import ARLResource
from app.routes.task import ARLTask, base_search_task_fields, stop_task
from app.utils.task_statistics import flush_task_statistic_safely


class TaskAssetYieldQueryTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().arl
        self.resource = ARLTask()
        self.tasks = {
            "done_site": {
                "_id": ObjectId(), "name": "done_site", "status": "done",
                "statistic": {"site_cnt": 3, "domain_cnt": 0, "ip_cnt": 0, "wih_cnt": 0, "vuln_cnt": 0, "nuclei_result_cnt": 0},
            },
            "done_domain_ip": {
                "_id": ObjectId(), "name": "done_domain_ip", "status": "done",
                "statistic": {"site_cnt": 0, "domain_cnt": 5, "ip_cnt": 2, "wih_cnt": 0, "vuln_cnt": 0, "nuclei_result_cnt": 0},
            },
            "done_vuln_only": {
                "_id": ObjectId(), "name": "done_vuln_only", "status": "done",
                "statistic": {"site_cnt": 0, "domain_cnt": 0, "ip_cnt": 0, "wih_cnt": 0, "vuln_cnt": 1, "nuclei_result_cnt": 0},
            },
            "done_nuclei_only": {
                "_id": ObjectId(), "name": "done_nuclei_only", "status": "done",
                "statistic": {"site_cnt": 0, "domain_cnt": 0, "ip_cnt": 0, "wih_cnt": 0, "vuln_cnt": 0, "nuclei_result_cnt": 4},
            },
            "done_wih_only": {
                "_id": ObjectId(), "name": "done_wih_only", "status": "done",
                "statistic": {"site_cnt": 0, "domain_cnt": 0, "ip_cnt": 0, "wih_cnt": 2, "vuln_cnt": 0, "nuclei_result_cnt": 0},
            },
            "done_empty": {
                "_id": ObjectId(), "name": "done_empty", "status": "done",
                "statistic": {"site_cnt": 0, "domain_cnt": 0, "ip_cnt": 0, "wih_cnt": 0, "vuln_cnt": 0, "nuclei_result_cnt": 0},
            },
            "stop_with_ip": {
                "_id": ObjectId(), "name": "stop_with_ip", "status": "stop",
                "statistic": {"site_cnt": 0, "domain_cnt": 0, "ip_cnt": 7, "wih_cnt": 0, "vuln_cnt": 0, "nuclei_result_cnt": 0},
            },
            "error_missing_stat": {
                "_id": ObjectId(), "name": "error_missing_stat", "status": "error",
            },
            "waiting_new": {
                "_id": ObjectId(), "name": "waiting_new", "status": "waiting",
            },
            "running_stage": {
                "_id": ObjectId(), "name": "running_stage", "status": "port_scan",
                "statistic": {"site_cnt": 0, "domain_cnt": 0, "ip_cnt": 0, "wih_cnt": 0, "vuln_cnt": 0, "nuclei_result_cnt": 0},
            },
        }
        self.db.task.insert_many(copy.deepcopy(list(self.tasks.values())))

    def _query_names(self, args):
        q = self.resource.build_db_query(args)
        return {doc["name"] for doc in self.db.task.find(q)}

    def test_search_fields_register_yield_and_all_six_numeric_filters(self):
        for key in (
            "asset_yield", "asset_types",
            "statistic.ip_cnt", "statistic.ip_cnt__gt", "statistic.ip_cnt__lt",
            "statistic.vuln_cnt", "statistic.vuln_cnt__gt", "statistic.vuln_cnt__lt",
            "statistic.nuclei_result_cnt", "statistic.nuclei_result_cnt__gt", "statistic.nuclei_result_cnt__lt",
        ):
            self.assertIn(key, base_search_task_fields)

    def test_has_asset_matches_any_of_six_core_dimensions_regardless_of_status(self):
        matched = self._query_names({"asset_yield": "has_asset"})
        self.assertEqual(matched, {
            "done_site", "done_domain_ip", "done_vuln_only",
            "done_nuclei_only", "done_wih_only", "stop_with_ip",
        })

    def test_no_asset_restricts_to_terminal_statuses_and_excludes_waiting_or_running(self):
        matched = self._query_names({"asset_yield": "no_asset"})
        self.assertEqual(matched, {"done_empty", "error_missing_stat"})
        self.assertNotIn("waiting_new", matched)
        self.assertNotIn("running_stage", matched)

    def test_no_asset_combined_with_status_intersects_without_overwriting(self):
        self.assertEqual(self._query_names({"asset_yield": "no_asset", "status": "done"}), {"done_empty"})
        self.assertEqual(self._query_names({"asset_yield": "no_asset", "status": "abnormal"}), {"error_missing_stat"})
        # 进行中/排队与无产出（已结束）互斥，交集应严格为空集
        self.assertEqual(self._query_names({"asset_yield": "no_asset", "status": "active"}), set())
        self.assertEqual(self._query_names({"asset_yield": "no_asset", "status": "waiting"}), set())

    def test_asset_types_multi_select_uses_or_semantics_and_supports_alias(self):
        self.assertEqual(
            self._query_names({"asset_types": "site,nuclei_result"}),
            {"done_site", "done_nuclei_only"},
        )
        self.assertEqual(
            self._query_names({"asset_types": "ip,vuln", "status": "done"}),
            {"done_domain_ip", "done_vuln_only"},
        )

    def test_asset_types_composes_with_numeric_range_filters_without_clobbering(self):
        # 同时要求有 IP (>0) 且 IP 数量 < 5，应仅命中 ip_cnt=2 而非 ip_cnt=7
        self.assertEqual(
            self._query_names({"asset_types": "ip", "statistic.ip_cnt__lt": 5}),
            {"done_domain_ip"},
        )
        self.assertEqual(
            self._query_names({"statistic.ip_cnt__gt": 3}),
            {"stop_with_ip"},
        )

    def test_invalid_yield_or_asset_types_fails_closed(self):
        self.assertEqual(self._query_names({"asset_yield": "invalid_mode"}), set())
        self.assertEqual(self._query_names({"asset_types": "unknown_dim"}), set())


class TaskTerminalStatisticFlushTests(unittest.TestCase):
    def test_flush_task_statistic_safely_persists_counts_and_swallows_errors(self):
        db = mongomock.MongoClient().arl
        tid = ObjectId()
        db.task.insert_one({"_id": tid, "status": "stop"})
        fake_stat = {"site_cnt": 2, "domain_cnt": 1, "ip_cnt": 3, "wih_cnt": 0, "vuln_cnt": 0, "nuclei_result_cnt": 0}
        fake_utils = types.SimpleNamespace(
            arl=types.SimpleNamespace(task_statistic=lambda _tid: fake_stat),
            conn_db=lambda name: db[name],
        )
        with patch.dict(sys.modules, {"app": types.SimpleNamespace(utils=fake_utils)}):
            result = flush_task_statistic_safely(str(tid))
        self.assertEqual(result, fake_stat)
        self.assertEqual(db.task.find_one({"_id": tid})["statistic"], fake_stat)
        self.assertIsNone(flush_task_statistic_safely("not-an-object-id"))

    def test_stop_task_flushes_statistic_for_zombie_and_revoked_tasks(self):
        db = mongomock.MongoClient().arl
        zombie_id = ObjectId()
        active_id = ObjectId()
        db.task.insert_many([
            {"_id": zombie_id, "status": "running", "celery_id": ""},
            {"_id": active_id, "status": "port_scan", "celery_id": "celery-123"},
        ])
        flushed = []
        fake_control = types.SimpleNamespace(revoke=lambda *a, **kw: None)
        with patch("app.routes.task.utils.conn_db", side_effect=lambda name: db[name]), \
             patch("app.routes.task.utils.curr_date", return_value="2026-11-23 15:50:00"), \
             patch("app.routes.task.celerytask.celery", types.SimpleNamespace(control=fake_control)), \
             patch("app.routes.task.flush_task_statistic_safely", side_effect=lambda tid, _log=None: flushed.append(tid)):
            res1 = stop_task(str(zombie_id))
            res2 = stop_task(str(active_id))
        self.assertEqual(res1["code"], 200)
        self.assertEqual(res2["code"], 200)
        self.assertEqual(flushed, [str(zombie_id), str(active_id)])
        self.assertEqual(db.task.find_one({"_id": zombie_id})["status"], "stop")
        self.assertEqual(db.task.find_one({"_id": active_id})["status"], "stop")

    def test_backfill_terminal_task_statistics_only_targets_missing_terminal_tasks_and_sets_sentinel(self):
        from app.utils import arlupdate
        db = mongomock.MongoClient().arl
        t_missing_stop = ObjectId()
        t_partial_done = ObjectId()
        t_complete_done = ObjectId()
        t_waiting = ObjectId()
        db.task.insert_many([
            {"_id": t_missing_stop, "status": "stop"},
            {"_id": t_partial_done, "status": "done", "statistic": {"site_cnt": 1}},
            {
                "_id": t_complete_done, "status": "done",
                "statistic": {"site_cnt": 1, "domain_cnt": 0, "ip_cnt": 0, "wih_cnt": 0, "vuln_cnt": 0, "nuclei_result_cnt": 0},
            },
            {"_id": t_waiting, "status": "waiting"},
        ])
        called_batches = []
        with patch.object(arlupdate, "conn_db", side_effect=lambda name: db[name]), \
             patch("app.services.asset_cascade_service.recalculate_tasks_statistics", side_effect=lambda batch: called_batches.append(list(batch))):
            first_count = arlupdate.backfill_terminal_task_statistics(run_async=False)
            second_count = arlupdate.backfill_terminal_task_statistics(run_async=False)
        self.assertEqual(first_count, 2)
        self.assertEqual(second_count, 0)
        self.assertEqual(set(called_batches[0]), {str(t_missing_stop), str(t_partial_done)})
        sentinel = db.system_config.find_one({"_id": "migration_backfill_terminal_task_statistics_v1"})
        self.assertEqual(sentinel["status"], "completed")
        self.assertEqual(sentinel["backfilled_count"], 2)


if __name__ == "__main__":
    unittest.main()
