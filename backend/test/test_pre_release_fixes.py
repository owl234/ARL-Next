"""本次发版前评审 P0/P1 修复项的离线回归测试（基于 mongomock + Flask test_client）。"""
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from bson import ObjectId
from flask import Flask
from flask_restx import Api
import mongomock

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
xing_dir = os.path.abspath(os.path.join(backend_dir, 'ARL-NPoC'))
if xing_dir not in sys.path:
    sys.path.insert(0, xing_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999
app.config._config_cache["version"] = 1
app.config._read_config_version = lambda: 1

from app import utils
from app.routes import ARLResource
from app.routes import site as site_route
from app.routes import assetSite as asset_site_route
from app.routes import task_schedule as task_schedule_route
from app.routes import service as service_route
from app.routes import cip as cip_route
from app.helpers import task_schedule as task_schedule_helper
from app.services import asset_cascade_service
from app.utils import arlupdate


class TestPreReleaseFixes(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().arl_pre_release_test
        self.app = Flask(__name__)
        api = Api(self.app, prefix="/api")
        api.add_namespace(site_route.ns, path="/site")
        api.add_namespace(asset_site_route.ns, path="/asset_site")
        api.add_namespace(task_schedule_route.ns, path="/task_schedule")
        api.add_namespace(service_route.ns, path="/service")
        api.add_namespace(cip_route.ns, path="/cip")
        self.client = self.app.test_client()

    # ------------------------------------------------------------------
    # 1. P0-1: 风险巡航 POST save_result_set 严格校验与 Fail-Closed
    # ------------------------------------------------------------------
    def test_post_site_save_result_set_strict_id_selection_and_fail_closed(self):
        id1, id2, id3 = ObjectId(), ObjectId(), ObjectId()
        self.db.site.insert_many([
            {"_id": id1, "task_id": "t1", "site": "https://a.example.com/login"},
            {"_id": id2, "task_id": "t1", "site": "https://b.example.com/app"},
            {"_id": id3, "task_id": "t2", "site": "https://c.example.com/other"},
        ])

        with patch("app.utils.user.user_login_header", return_value={"username": "admin"}), \
             patch.object(utils, "conn_db", side_effect=self.db.__getitem__), \
             patch.object(service_route, "conn", side_effect=self.db.__getitem__), \
             patch.object(cip_route, "conn", side_effect=self.db.__getitem__):
            # 正常勾选：仅写入选中的两条，不会退化为全库
            resp = self.client.post("/api/site/save_result_set/", json={"_id": [str(id1), str(id2)]})
            body = resp.get_json()
            self.assertEqual(body["code"], 200)
            self.assertEqual(body["data"]["result_total"], 2)
            rs_doc = self.db.result_set.find_one({"_id": ObjectId(body["data"]["result_set_id"])})
            self.assertEqual(set(rs_doc["items"]), {"https://a.example.com", "https://b.example.com"})

            # 带 task_id 作用域约束：排除非该任务的 ID
            resp_scoped = self.client.post(
                "/api/site/save_result_set/",
                json={"_id": [str(id1), str(id3)], "task_id": "t1"},
            )
            body_scoped = resp_scoped.get_json()
            self.assertEqual(body_scoped["code"], 200)
            self.assertEqual(body_scoped["data"]["result_total"], 1)

            # Fail-Closed：空数组、非法 ObjectId、超限 (>500) 一律返回 code=400 且不新建结果集
            before_cnt = self.db.result_set.count_documents({})
            for bad_payload in (
                {"_id": []},
                {"_id": ["not-an-oid"]},
                {"_id": [str(id1), "bad-oid"]},
                {"_id": [str(ObjectId()) for _ in range(501)]},
            ):
                bad_resp = self.client.post("/api/site/save_result_set/", json=bad_payload).get_json()
                self.assertEqual(bad_resp["code"], 400, f"payload={bad_payload}")
            self.assertEqual(self.db.result_set.count_documents({}), before_cnt)

    def test_post_asset_site_save_result_set_strict_id_selection_and_fail_closed(self):
        id1, id2, id3 = ObjectId(), ObjectId(), ObjectId()
        self.db.asset_site.insert_many([
            {"_id": id1, "scope_id": "s1", "site": "https://s1-a.example.com/path"},
            {"_id": id2, "scope_id": "s1", "site": "https://s1-b.example.com"},
            {"_id": id3, "scope_id": "s2", "site": "https://s2-c.example.com"},
        ])

        with patch("app.utils.user.user_login_header", return_value={"username": "admin"}), \
             patch.object(utils, "conn_db", side_effect=self.db.__getitem__), \
             patch.object(service_route, "conn", side_effect=self.db.__getitem__), \
             patch.object(cip_route, "conn", side_effect=self.db.__getitem__):
            resp = self.client.post(
                "/api/asset_site/save_result_set/",
                json={"_id": [str(id1), str(id3)], "scope_id": "s1"},
            )
            body = resp.get_json()
            self.assertEqual(body["code"], 200)
            self.assertEqual(body["data"]["result_total"], 1)
            rs_doc = self.db.result_set.find_one({"_id": ObjectId(body["data"]["result_set_id"])})
            self.assertEqual(rs_doc["items"], ["https://s1-a.example.com"])

            before_cnt = self.db.result_set.count_documents({})
            for bad_payload in (
                {"_id": []},
                {"_id": ["invalid"]},
                {"_id": [str(ObjectId()) for _ in range(501)]},
            ):
                bad_resp = self.client.post("/api/asset_site/save_result_set/", json=bad_payload).get_json()
                self.assertEqual(bad_resp["code"], 400)
            self.assertEqual(self.db.result_set.count_documents({}), before_cnt)

    # ------------------------------------------------------------------
    # 2. P1: POST /api/task_schedule/run/ 校验、任意状态立即运行、失败不虚增
    # ------------------------------------------------------------------
    def test_task_schedule_run_validates_ids_and_only_increments_after_dispatch(self):
        sid_stop = ObjectId()
        sid_done = ObjectId()
        self.db.task_schedule.insert_many([
            {
                "_id": sid_stop,
                "name": "stopped-plan",
                "target": "example.com",
                "status": "stop",
                "schedule_type": "recurrent_scan",
                "run_number": 2,
                "policy_id": str(ObjectId()),
            },
            {
                "_id": sid_done,
                "name": "done-plan",
                "target": "example.org",
                "status": "done",
                "schedule_type": "future_scan",
                "run_number": 1,
                "policy_id": str(ObjectId()),
            },
        ])

        with patch("app.utils.user.user_login_header", return_value={"username": "admin"}), \
             patch.object(utils, "conn_db", side_effect=self.db.__getitem__), \
             patch.object(service_route, "conn", side_effect=self.db.__getitem__), \
             patch.object(cip_route, "conn", side_effect=self.db.__getitem__):
            # 空数组返回 code=400，非法/不存在 ObjectId 返回 TaskScheduleNotFound（绝不抛 HTTP 500）
            r_empty = self.client.post("/api/task_schedule/run/", json={"_id": []})
            self.assertEqual(r_empty.status_code, 200)
            self.assertEqual(r_empty.get_json()["code"], 400)
            for bad_ids in (["invalid-oid"], [str(sid_stop), "bad"]):
                r = self.client.post("/api/task_schedule/run/", json={"_id": bad_ids})
                self.assertEqual(r.status_code, 200)
                self.assertNotEqual(r.get_json()["code"], 200)

            # 派发失败时返回非 200 错误码且 run_number 不得虚增
            with patch.object(task_schedule_helper, "submit_task_schedule", side_effect=RuntimeError("broker down")):
                r_fail = self.client.post("/api/task_schedule/run/", json={"_id": [str(sid_stop)]})
                self.assertEqual(r_fail.status_code, 200)
                self.assertNotEqual(r_fail.get_json()["code"], 200)
            self.assertEqual(self.db.task_schedule.find_one({"_id": sid_stop})["run_number"], 2)

            # stop / done 状态手动立即执行成功时，均能派发且 run_number 原子 +1
            dispatched = []
            with patch.object(
                task_schedule_helper,
                "submit_task_schedule",
                side_effect=lambda item: dispatched.append(item["name"]),
            ):
                r_ok = self.client.post(
                    "/api/task_schedule/run/",
                    json={"_id": [str(sid_stop), str(sid_done)]},
                )
                self.assertEqual(r_ok.get_json()["code"], 200)

            self.assertEqual(dispatched, ["stopped-plan", "done-plan"])
            self.assertEqual(self.db.task_schedule.find_one({"_id": sid_stop})["run_number"], 3)
            self.assertEqual(self.db.task_schedule.find_one({"_id": sid_done})["run_number"], 2)
            # 停止态手动单次触发保持 stop，不偷偷改回 scheduled
            self.assertEqual(self.db.task_schedule.find_one({"_id": sid_stop})["status"], "stop")

    # ------------------------------------------------------------------
    # 3. P0/P1: 统一服务表两阶段安全迁移、保留 _id 时间戳、失败跳过唯一索引
    # ------------------------------------------------------------------
    def test_unified_service_migration_two_phase_preserves_oid_save_date_and_index_guard(self):
        # 校验 create_index 正常执行时不对 service/asset_service 下发冲突的非唯一复合索引
        ok_created_by_table = {}

        def _ok_conn(table_name):
            return ok_created_by_table.setdefault(table_name, MagicMock())

        with patch.object(arlupdate, "conn_db", side_effect=_ok_conn), \
             patch.object(arlupdate, "migrate_unified_service_assets", return_value=True):
            arlupdate.create_index()

        non_unique_asset_svc = [
            c.args[0] for c in ok_created_by_table["asset_service"].create_index.call_args_list
            if not c.kwargs.get("unique")
        ]
        non_unique_svc = [
            c.args[0] for c in ok_created_by_table["service"].create_index.call_args_list
            if not c.kwargs.get("unique")
        ]
        self.assertNotIn([("scope_id", 1), ("ip", 1), ("port_id", 1)], non_unique_asset_svc)
        self.assertNotIn([("task_id", 1), ("ip", 1), ("port_id", 1)], non_unique_svc)

        # 构造缺少 save_date 的旧版分组 service 文档，验证继承 _id.generation_time
        legacy_dt = datetime(2025, 5, 1, 8, 30, 0, tzinfo=timezone.utc)
        legacy_oid = ObjectId.from_datetime(legacy_dt)
        expected_local_naive = utils.to_datetime_obj(None, fallback_oid=legacy_oid)

        self.db.service.insert_one({
            "_id": legacy_oid,
            "task_id": "t_mig",
            "service_name": "ssh",
            "service_info": [{"ip": "192.0.2.10", "port_id": 22, "product": "OpenSSH", "version": "9.0"}],
        })

        with patch.object(arlupdate, "conn_db", side_effect=self.db.__getitem__), \
             patch.object(utils, "conn_db", side_effect=self.db.__getitem__):
            ok = arlupdate.migrate_unified_service_assets()
            self.assertTrue(ok)
            docs = list(self.db.service.find({"task_id": "t_mig"}))
            self.assertEqual(len(docs), 1)
            self.assertEqual(docs[0]["ip"], "192.0.2.10")
            self.assertEqual(docs[0]["port_id"], 22)
            self.assertEqual(docs[0]["save_date"], expected_local_naive)
            # 再次执行应命中 sentinel 幂等返回 True
            self.assertTrue(arlupdate.migrate_unified_service_assets())

        # 当 migrate_unified_service_assets 返回 False 时，create_index 不得为 service/asset_service 建唯一索引
        created_by_table = {}

        def _fake_conn(table_name):
            return created_by_table.setdefault(table_name, MagicMock())

        with patch.object(arlupdate, "conn_db", side_effect=_fake_conn), \
             patch.object(arlupdate, "migrate_unified_service_assets", return_value=False):
            arlupdate.create_index()

        for col_name in ("service", "asset_service"):
            unique_calls = [
                c for c in created_by_table.get(col_name, MagicMock()).create_index.call_args_list
                if c.kwargs.get("unique") is True
            ]
            self.assertEqual(unique_calls, [], f"{col_name} must skip unique index when migration failed")

    # ------------------------------------------------------------------
    # 4. P1: 级联删除畸形 IP 防护、npoc_service 删除重算 service、stat_finger 大小写无关剥离
    # ------------------------------------------------------------------
    def test_cascade_cip_malformed_ip_npoc_rebuild_and_case_insensitive_stat_finger(self):
        task_id = str(ObjectId())
        # 4a. C 段删除包含非法 IP 字符串不崩，且仍删除合法同段 IP
        cip_id = ObjectId()
        self.db.cip.insert_one({"_id": cip_id, "task_id": task_id, "cidr_ip": "192.0.2.0/24"})
        self.db.ip.insert_many([
            {"_id": ObjectId(), "task_id": task_id, "ip": "not-an-ip"},
            {"_id": ObjectId(), "task_id": task_id, "ip": "192.0.2.55", "port_info": []},
        ])

        # 4b. npoc_service 删除重算统一 service 集合
        npoc_only_id = ObjectId()
        npoc_fused_id = ObjectId()
        self.db.ip.insert_one({
            "_id": ObjectId(),
            "task_id": task_id,
            "ip": "198.51.100.20",
            "port_info": [{"port_id": 6379, "service_name": "redis", "product": "Redis", "version": ""}],
        })
        self.db.npoc_service.insert_many([
            {"_id": npoc_only_id, "task_id": task_id, "host": "198.51.100.99", "port": "9200", "scheme": "elasticsearch"},
            {"_id": npoc_fused_id, "task_id": task_id, "host": "198.51.100.20", "port": "6379", "scheme": "redis"},
        ])
        self.db.service.insert_many([
            {"task_id": task_id, "ip": "198.51.100.99", "port_id": 9200, "service_name": "elasticsearch", "sources": ["npoc"]},
            {"task_id": task_id, "ip": "198.51.100.20", "port_id": 6379, "service_name": "redis", "sources": ["nmap", "npoc"]},
        ])

        # 4c. stat_finger 大小写无关剥离
        site_id = ObjectId()
        self.db.site.insert_one({
            "_id": site_id,
            "task_id": task_id,
            "site": "https://web.example.com",
            "finger": [{"name": "Nginx", "confidence": "100"}, "NGINX", {"name": "Vue"}],
        })
        self.db.stat_finger.insert_one({"_id": ObjectId(), "task_id": task_id, "name": "Nginx", "cnt": 1})

        with patch.object(utils, "conn_db", side_effect=self.db.__getitem__):
            res_cip = asset_cascade_service.cascade_delete_dimension_records(
                "cip", [str(cip_id)], task_id=task_id, source_type="task"
            )
            self.assertEqual(res_cip["deleted_count"], 1)
            self.assertEqual(self.db.ip.count_documents({"task_id": task_id, "ip": "192.0.2.55"}), 0)
            self.assertEqual(self.db.ip.count_documents({"task_id": task_id, "ip": "not-an-ip"}), 1)

            res_npoc = asset_cascade_service.cascade_delete_dimension_records(
                "npoc_service", [str(npoc_only_id), str(npoc_fused_id)], task_id=task_id, source_type="task"
            )
            self.assertEqual(res_npoc["deleted_count"], 2)
            self.assertIsNone(self.db.service.find_one({"task_id": task_id, "ip": "198.51.100.99", "port_id": 9200}))
            fused_doc = self.db.service.find_one({"task_id": task_id, "ip": "198.51.100.20", "port_id": 6379})
            self.assertIsNotNone(fused_doc)
            self.assertEqual(fused_doc["sources"], ["nmap"])

            res_sf = asset_cascade_service.cascade_delete_dimension_records(
                "stat_finger", ["nginx"], task_id=task_id, source_type="task"
            )
            self.assertEqual(res_sf["deleted_count"], 1)
            remaining_sf = [d["name"] for d in self.db.stat_finger.find({"task_id": task_id})]
            self.assertEqual(remaining_sf, ["Vue"])
            site_after = self.db.site.find_one({"_id": site_id})
            self.assertIsNotNone(site_after)
            self.assertEqual(site_after["finger"], [{"name": "Vue"}])

    # ------------------------------------------------------------------
    # 5. P1: 全局 service/cip 导出 save_date 按 $min(save_date) 口径与 ISO 时区归一
    # ------------------------------------------------------------------
    def test_parse_date_boundary_iso_tz_and_global_service_cip_export_parity(self):
        # ISO 8601 带 Z 与时区偏移均归一为本地 naive datetime
        dt_z = ARLResource._parse_date_boundary("2026-11-20T00:00:00Z")
        dt_off = ARLResource._parse_date_boundary("2026-11-20T08:00:00+08:00")
        self.assertIsNotNone(dt_z)
        self.assertIsNone(dt_z.tzinfo)
        self.assertIsNotNone(dt_off)
        self.assertIsNone(dt_off.tzinfo)
        self.assertEqual(dt_z, dt_off)

        # 旧端点首次发现于 11-01，11-15 被新任务复扫；按 11-10 后筛选首次发现时间，全局列表与导出均应排除旧端点
        self.db.service.insert_many([
            {
                "task_id": "t_old", "ip": "192.0.2.1", "port_id": 80, "service_name": "http",
                "save_date": datetime(2026, 11, 1, 10, 0, 0),
            },
            {
                "task_id": "t_new", "ip": "192.0.2.1", "port_id": 80, "service_name": "http",
                "save_date": datetime(2026, 11, 15, 10, 0, 0),
            },
            {
                "task_id": "t_new", "ip": "192.0.2.2", "port_id": 443, "service_name": "https",
                "save_date": datetime(2026, 11, 15, 10, 0, 0),
            },
        ])
        self.db.cip.insert_many([
            {"task_id": "t_old", "cidr_ip": "192.0.2.0/24", "save_date": datetime(2026, 11, 1, 10, 0, 0)},
            {"task_id": "t_new", "cidr_ip": "192.0.2.0/24", "save_date": datetime(2026, 11, 15, 10, 0, 0)},
            {"task_id": "t_new", "cidr_ip": "198.51.100.0/24", "save_date": datetime(2026, 11, 15, 10, 0, 0)},
        ])

        with patch("app.utils.user.user_login_header", return_value={"username": "admin"}), \
             patch.object(utils, "conn_db", side_effect=self.db.__getitem__), \
             patch.object(service_route, "conn", side_effect=self.db.__getitem__), \
             patch.object(cip_route, "conn", side_effect=self.db.__getitem__):
            q = {"save_date__dgt": "2026-11-10 00:00:00"}
            svc_list = self.client.get("/api/service/", query_string=q).get_json()["items"]
            svc_export = self.client.get("/api/service/export/", query_string=q).get_data(as_text=True).splitlines()
            self.assertEqual(len(svc_list), 1)
            self.assertEqual(svc_list[0]["ip"], "192.0.2.2")
            self.assertEqual(svc_export, ["https://192.0.2.2:443"])

            # 全局 C 段导出同样基于分组后 $min(save_date) 过滤（排除 11-01 首次发现的 192.0.2.0/24）
            cip_export = self.client.get("/api/cip/export/", query_string=q).get_data(as_text=True).splitlines()
            self.assertEqual(cip_export, ["198.51.100.0/24"])


if __name__ == "__main__":
    unittest.main()
