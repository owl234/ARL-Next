import sys
import types
import unittest
from unittest.mock import patch
from bson import ObjectId
import mongomock


class _FakeDatabase:
    def __init__(self):
        self.client = mongomock.MongoClient()
        self.db = self.client["arl_test_cascade"]

    def conn(self, collection_name):
        return self.db[collection_name]


class TestAssetCascadeAndDerived(unittest.TestCase):
    def setUp(self):
        self.fake = _FakeDatabase()
        self.conn = self.fake.conn

        # Ensure app.utils.conn_db points to our isolated mongomock DB for every test
        import app.utils as utils_mod
        import app.utils.conn as conn_mod
        import app.services.asset_cascade_service as cascade_mod

        self.utils_mod = utils_mod
        self.cascade_mod = cascade_mod

        class _FakeConnMongo:
            def __init__(self, conn_fn):
                self._conn_fn = conn_fn

            def get_collection_proxy(self, collection, db_name=None):
                return self._conn_fn(collection)

        fake_mongo = _FakeConnMongo(self.conn)
        self.patchers = [
            patch.object(utils_mod, "conn_db", side_effect=self.conn),
            patch.object(conn_mod, "conn_db", side_effect=self.conn),
            patch.object(conn_mod, "ConnMongo", return_value=fake_mongo),
            patch.object(cascade_mod, "_revoke_celery_tasks", return_value=[]),
            patch.object(cascade_mod, "_cleanup_unreferenced_screenshots", return_value=0),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()

    # ------------------------------------------------------------------
    # 1. Scope isolation & explicit task binding
    # ------------------------------------------------------------------

    def test_scope_deletion_isolates_unbound_tasks_and_other_scopes(self):
        scope_a = ObjectId()
        scope_b = ObjectId()
        scope_a_str = str(scope_a)
        scope_b_str = str(scope_b)

        sched_a = ObjectId()
        sched_b = ObjectId()

        t_bound_direct = ObjectId()
        t_bound_synced = ObjectId()
        t_bound_opts = ObjectId()
        t_bound_sched = ObjectId()
        t_unbound_ind = ObjectId()
        t_scope_b = ObjectId()

        self.conn("asset_scope").insert_many([
            {"_id": scope_a, "name": "ScopeA", "scope": "a.example.com", "scope_array": ["a.example.com"], "scope_type": "domain"},
            {"_id": scope_b, "name": "ScopeB", "scope": "a.example.com", "scope_array": ["a.example.com"], "scope_type": "domain"},
        ])
        self.conn("scheduler").insert_many([
            {"_id": sched_a, "scope_id": scope_a_str, "domain": "a.example.com", "name": "资产分组监控-ScopeA"},
            {"_id": sched_b, "scope_id": scope_b_str, "domain": "a.example.com", "name": "资产分组监控-ScopeB"},
        ])
        self.conn("task").insert_many([
            {"_id": t_bound_direct, "name": "direct", "target": "a.example.com", "status": "done", "scope_id": scope_a_str},
            {"_id": t_bound_synced, "name": "synced", "target": "a.example.com", "status": "done", "synced_scope_id": scope_a_str},
            {"_id": t_bound_opts, "name": "opts", "target": "a.example.com", "status": "done", "options": {"related_scope_id": scope_a_str}},
            {"_id": t_bound_sched, "name": "sched", "target": "a.example.com", "status": "done", "options": {"scheduler_id": str(sched_a)}},
            {"_id": t_unbound_ind, "name": "independent", "target": "a.example.com", "status": "done"},
            {"_id": t_scope_b, "name": "scope_b_task", "target": "a.example.com", "status": "done", "scope_id": scope_b_str},
        ])

        for tid in [t_bound_direct, t_bound_synced, t_bound_opts, t_bound_sched, t_unbound_ind, t_scope_b]:
            self.conn("domain").insert_one({"domain": "sub.a.example.com", "ips": ["192.0.2.1"], "task_id": str(tid)})
            self.conn("site").insert_one({"site": "http://sub.a.example.com", "hostname": "sub.a.example.com", "ip": "192.0.2.1", "task_id": str(tid)})

        for sid in [scope_a_str, scope_b_str]:
            self.conn("asset_domain").insert_one({"domain": "sub.a.example.com", "ips": ["192.0.2.1"], "scope_id": sid})
            self.conn("asset_site").insert_one({"site": "http://sub.a.example.com", "hostname": "sub.a.example.com", "ip": "192.0.2.1", "scope_id": sid})

        # Delete scope_a via cascade_delete_scopes (which atomically deletes asset_scope itself)
        res = self.cascade_mod.cascade_delete_scopes([scope_a_str])
        self.assertTrue(res["ok"])
        self.assertIsNone(self.conn("asset_scope").find_one({"_id": scope_a}))

        # Scope A and all 4 bound tasks + their unprefixed assets must be gone
        self.assertEqual(self.conn("asset_domain").count_documents({"scope_id": scope_a_str}), 0)
        self.assertEqual(self.conn("asset_site").count_documents({"scope_id": scope_a_str}), 0)
        self.assertEqual(self.conn("scheduler").count_documents({"scope_id": scope_a_str}), 0)
        for tid in [t_bound_direct, t_bound_synced, t_bound_opts, t_bound_sched]:
            self.assertIsNone(self.conn("task").find_one({"_id": tid}))
            self.assertEqual(self.conn("domain").count_documents({"task_id": str(tid)}), 0)
            self.assertEqual(self.conn("site").count_documents({"task_id": str(tid)}), 0)

        # Scope B, Scope B's task, and Unbound Independent Task must survive untouched
        self.assertEqual(self.conn("asset_domain").count_documents({"scope_id": scope_b_str}), 1)
        self.assertEqual(self.conn("asset_site").count_documents({"scope_id": scope_b_str}), 1)
        self.assertEqual(self.conn("scheduler").count_documents({"scope_id": scope_b_str}), 1)
        self.assertIsNotNone(self.conn("task").find_one({"_id": t_unbound_ind}))
        self.assertEqual(self.conn("domain").count_documents({"task_id": str(t_unbound_ind)}), 1)
        self.assertEqual(self.conn("site").count_documents({"task_id": str(t_unbound_ind)}), 1)
        self.assertIsNotNone(self.conn("task").find_one({"_id": t_scope_b}))
        self.assertEqual(self.conn("domain").count_documents({"task_id": str(t_scope_b)}), 1)

    def test_scope_target_removal_isolates_unbound_tasks_and_rebuilds_derived(self):
        scope_a = ObjectId()
        scope_b = ObjectId()
        scope_a_str = str(scope_a)
        scope_b_str = str(scope_b)
        t_bound = ObjectId()
        t_ind = ObjectId()

        self.conn("asset_scope").insert_many([
            {"_id": scope_a, "name": "ScopeA", "scope": "keep.example.com", "scope_array": ["keep.example.com"], "scope_type": "domain"},
            {"_id": scope_b, "name": "ScopeB", "scope": "drop.example.com", "scope_array": ["drop.example.com"], "scope_type": "domain"},
        ])
        self.conn("task").insert_many([
            {"_id": t_bound, "name": "bound", "target": "drop.example.com keep.example.com", "status": "done", "scope_id": scope_a_str},
            {"_id": t_ind, "name": "ind", "target": "drop.example.com", "status": "done"},
        ])

        # Asset tables for Scope A: drop.example.com + keep.example.com
        self.conn("asset_domain").insert_many([
            {"domain": "www.drop.example.com", "ips": ["192.0.2.10"], "scope_id": scope_a_str},
            {"domain": "www.keep.example.com", "ips": ["192.0.2.20"], "scope_id": scope_a_str},
            {"domain": "www.drop.example.com", "ips": ["192.0.2.10"], "scope_id": scope_b_str},
        ])
        self.conn("asset_ip").insert_many([
            {"ip": "192.0.2.10", "domain": ["www.drop.example.com"], "port_info": [{"port_id": 80, "service_name": "http"}], "scope_id": scope_a_str},
            {"ip": "192.0.2.20", "domain": ["www.keep.example.com"], "port_info": [{"port_id": 443, "service_name": "https"}], "scope_id": scope_a_str},
            {"ip": "192.0.2.10", "domain": ["www.drop.example.com"], "port_info": [{"port_id": 80, "service_name": "http"}], "scope_id": scope_b_str},
        ])
        self.conn("asset_site").insert_many([
            {"site": "http://www.drop.example.com", "hostname": "www.drop.example.com", "ip": "192.0.2.10", "finger": [{"name": "DropCMS"}], "scope_id": scope_a_str},
            {"site": "https://www.keep.example.com", "hostname": "www.keep.example.com", "ip": "192.0.2.20", "finger": [{"name": "KeepCMS"}], "scope_id": scope_a_str},
        ])

        # Task tables for bound task & independent task
        for tid in [str(t_bound), str(t_ind)]:
            self.conn("domain").insert_one({"domain": "www.drop.example.com", "ips": ["192.0.2.10"], "task_id": tid})
            self.conn("ip").insert_one({"ip": "192.0.2.10", "domain": ["www.drop.example.com"], "port_info": [{"port_id": 80, "service_name": "http"}], "task_id": tid})
            self.conn("site").insert_one({"site": "http://www.drop.example.com", "hostname": "www.drop.example.com", "ip": "192.0.2.10", "finger": [{"name": "DropCMS"}], "task_id": tid})
        self.conn("domain").insert_one({"domain": "www.keep.example.com", "ips": ["192.0.2.20"], "task_id": str(t_bound)})

        self.cascade_mod.cascade_remove_scope_targets(scope_a_str, ["drop.example.com"])

        # Scope A cleaned & derived rebuilt
        self.assertEqual([d["domain"] for d in self.conn("asset_domain").find({"scope_id": scope_a_str})], ["www.keep.example.com"])
        self.assertEqual([d["ip"] for d in self.conn("asset_ip").find({"scope_id": scope_a_str})], ["192.0.2.20"])
        self.assertEqual([d["name"] for d in self.conn("asset_stat_finger").find({"scope_id": scope_a_str})], ["KeepCMS"])
        self.assertEqual([d["service_name"] for d in self.conn("asset_service").find({"scope_id": scope_a_str})], ["https"])
        cips_a = list(self.conn("asset_cip").find({"scope_id": scope_a_str}))
        self.assertEqual(len(cips_a), 1)
        self.assertEqual(cips_a[0]["ip_list"], ["192.0.2.20"])

        # Bound task cleaned & statistic recalculated
        self.assertEqual([d["domain"] for d in self.conn("domain").find({"task_id": str(t_bound)})], ["www.keep.example.com"])
        bound_doc = self.conn("task").find_one({"_id": t_bound})
        self.assertEqual(bound_doc["statistic"]["domain_cnt"], 1)
        self.assertEqual(bound_doc["statistic"]["site_cnt"], 0)

        # Scope B & independent task untouched
        self.assertEqual(self.conn("asset_domain").count_documents({"scope_id": scope_b_str}), 1)
        self.assertEqual(self.conn("domain").count_documents({"task_id": str(t_ind)}), 1)
        self.assertEqual(self.conn("site").count_documents({"task_id": str(t_ind)}), 1)

    def test_scoped_dimension_delete_only_touches_scope_and_bound_tasks(self):
        scope_a = str(ObjectId())
        scope_b = str(ObjectId())
        t_bound = ObjectId()
        t_ind = ObjectId()

        self.conn("asset_scope").insert_many([
            {"_id": ObjectId(scope_a), "name": "A", "scope_array": ["example.com"], "scope_type": "domain"},
            {"_id": ObjectId(scope_b), "name": "B", "scope_array": ["example.com"], "scope_type": "domain"},
        ])
        self.conn("task").insert_many([
            {"_id": t_bound, "name": "bound", "status": "done", "synced_scope_id": scope_a},
            {"_id": t_ind, "name": "ind", "status": "done"},
        ])

        ad_a = self.conn("asset_domain").insert_one({"domain": "api.example.com", "ips": ["192.0.2.5"], "scope_id": scope_a}).inserted_id
        self.conn("asset_domain").insert_one({"domain": "api.example.com", "ips": ["192.0.2.5"], "scope_id": scope_b})
        self.conn("domain").insert_one({"domain": "api.example.com", "ips": ["192.0.2.5"], "task_id": str(t_bound)})
        self.conn("domain").insert_one({"domain": "api.example.com", "ips": ["192.0.2.5"], "task_id": str(t_ind)})

        res = self.cascade_mod.handle_dimension_delete(
            "domain", is_asset_route=True, args={"_id": [str(ad_a)], "scope_id": scope_a}
        )
        self.assertEqual(res["code"], 200)
        self.assertEqual(self.conn("asset_domain").count_documents({"scope_id": scope_a}), 0)
        self.assertEqual(self.conn("domain").count_documents({"task_id": str(t_bound)}), 0)
        # Scope B & unbound task untouched
        self.assertEqual(self.conn("asset_domain").count_documents({"scope_id": scope_b}), 1)
        self.assertEqual(self.conn("domain").count_documents({"task_id": str(t_ind)}), 1)

    def test_global_vs_default_task_dimension_delete_and_batch_limit(self):
        scope_a = str(ObjectId())
        t_a = ObjectId()
        t_b = ObjectId()
        self.conn("asset_scope").insert_one({"_id": ObjectId(scope_a), "name": "A", "scope_array": ["example.com"], "scope_type": "domain"})
        self.conn("task").insert_many([
            {"_id": t_a, "name": "TA", "status": "done"},
            {"_id": t_b, "name": "TB", "status": "done"},
        ])
        s_a = self.conn("site").insert_one({"site": "https://x.example.com", "hostname": "x.example.com", "task_id": str(t_a)}).inserted_id
        s_b = self.conn("site").insert_one({"site": "https://x.example.com", "hostname": "x.example.com", "task_id": str(t_b)}).inserted_id
        self.conn("asset_site").insert_one({"site": "https://x.example.com", "hostname": "x.example.com", "scope_id": scope_a})

        # Default (no source_type) on unprefixed route must isolate to task_a ONLY
        res_task = self.cascade_mod.handle_dimension_delete("site", is_asset_route=False, args={"_id": [str(s_a)]})
        self.assertEqual(res_task["code"], 200)
        self.assertEqual(self.conn("site").count_documents({"task_id": str(t_a)}), 0)
        self.assertEqual(self.conn("site").count_documents({"task_id": str(t_b)}), 1)
        self.assertEqual(self.conn("asset_site").count_documents({"scope_id": scope_a}), 1)

        # Explicit source_type="global" must delete across remaining tasks AND asset_site
        res_global = self.cascade_mod.handle_dimension_delete(
            "site", is_asset_route=False, args={"_id": [str(s_b)], "source_type": "global"}
        )
        self.assertEqual(res_global["code"], 200)
        self.assertEqual(self.conn("site").count_documents({}), 0)
        self.assertEqual(self.conn("asset_site").count_documents({}), 0)

        # Batch > 500 must fail fast with code 400 (matching dimension /delete/ validation contract)
        too_many = [str(ObjectId()) for _ in range(501)]
        res_limit = self.cascade_mod.handle_dimension_delete("site", is_asset_route=False, args={"_id": too_many})
        self.assertEqual(res_limit["code"], 400)

    # ------------------------------------------------------------------
    # 2. Enterprise recon closure & scope rename synchronization
    # ------------------------------------------------------------------

    def test_scope_delete_stops_icp_update_and_unbinds_preserving_icp_data(self):
        scope_id = ObjectId()
        icp_updating_id = ObjectId()
        icp_bound_id = ObjectId()

        self.conn("asset_scope").insert_one({
            "_id": scope_id,
            "name": "EntScope",
            "scope_array": ["ent.example.com"],
            "scope_type": "domain",
            "updating_icp_task_id": str(icp_updating_id),
        })
        self.conn("icp_task").insert_many([
            {"_id": icp_updating_id, "status": "running", "synced_scope_id": str(scope_id), "synced_scope_name": "EntScope"},
            {"_id": icp_bound_id, "status": "done", "synced_scope_id": str(scope_id), "synced_scope_name": "EntScope"},
        ])
        self.conn("icp_asset").insert_one({"task_id": str(icp_bound_id), "domain": "ent.example.com"})

        stop_calls = []
        fake_icp_route = types.ModuleType("app.routes.icp")

        def fake_stop_single_icp_task(tid):
            stop_calls.append(tid)
            self.conn("icp_task").update_one({"_id": ObjectId(tid)}, {"$set": {"status": "stop"}})
            return {"stopped": True}

        fake_icp_route._stop_single_icp_task = fake_stop_single_icp_task

        with patch.dict(sys.modules, {"app.routes.icp": fake_icp_route}):
            self.cascade_mod.cascade_delete_scopes([str(scope_id)])

        self.assertEqual(stop_calls, [str(icp_updating_id)])
        # Both icp_task records & icp_asset MUST be preserved, with synced_scope_* unset
        t1 = self.conn("icp_task").find_one({"_id": icp_updating_id})
        t2 = self.conn("icp_task").find_one({"_id": icp_bound_id})
        self.assertIsNotNone(t1)
        self.assertEqual(t1["status"], "stop")
        self.assertNotIn("synced_scope_id", t1)
        self.assertNotIn("synced_scope_name", t1)
        self.assertIsNotNone(t2)
        self.assertNotIn("synced_scope_id", t2)
        self.assertEqual(self.conn("icp_asset").count_documents({"task_id": str(icp_bound_id)}), 1)

    def test_scope_rename_syncs_scheduler_icp_and_bound_tasks(self):
        scope_id = str(ObjectId())
        s_dom = ObjectId()
        s_site = ObjectId()
        s_wih = ObjectId()
        s_custom = ObjectId()
        icp_id = ObjectId()
        t_id = ObjectId()

        self.conn("scheduler").insert_many([
            {"_id": s_dom, "scope_id": scope_id, "name": "监控-OldName-a.example.com"},
            {"_id": s_site, "scope_id": scope_id, "name": "站点监控-OldName"},
            {"_id": s_wih, "scope_id": scope_id, "name": "WIH 监控-OldName"},
            {"_id": s_custom, "scope_id": scope_id, "name": "自定义监控名称"},
        ])
        self.conn("icp_task").insert_one({"_id": icp_id, "synced_scope_id": scope_id, "synced_scope_name": "OldName"})
        self.conn("task").insert_one({
            "_id": t_id,
            "scope_id": scope_id,
            "sync_scope_id": scope_id,
            "synced_scope_id": scope_id,
            "related_scope_name": "OldName",
            "sync_scope_name": "OldName",
            "synced_scope_name": "OldName",
            "options": {"related_scope_id": scope_id},
        })

        self.cascade_mod._sync_scope_rename_references(scope_id, "OldName", "NewName")

        self.assertEqual(self.conn("scheduler").find_one({"_id": s_dom})["name"], "监控-NewName-a.example.com")
        self.assertEqual(self.conn("scheduler").find_one({"_id": s_site})["name"], "站点监控-NewName")
        self.assertEqual(self.conn("scheduler").find_one({"_id": s_wih})["name"], "WIH 监控-NewName")
        self.assertEqual(self.conn("scheduler").find_one({"_id": s_custom})["name"], "自定义监控名称")
        self.assertEqual(self.conn("icp_task").find_one({"_id": icp_id})["synced_scope_name"], "NewName")
        t_doc = self.conn("task").find_one({"_id": t_id})
        self.assertEqual(t_doc["related_scope_name"], "NewName")
        self.assertEqual(t_doc["sync_scope_name"], "NewName")
        self.assertEqual(t_doc["synced_scope_name"], "NewName")

    # ------------------------------------------------------------------
    # 3. L1/L2/L3 cascade boundaries & precision
    # ------------------------------------------------------------------

    def test_domain_delete_orphan_ip_reclaim_vs_cidr_protection_and_wih(self):
        scope_id = ObjectId()
        scope_str = str(scope_id)
        self.conn("asset_scope").insert_one({
            "_id": scope_id,
            "name": "MixedScope",
            "scope_array": ["example.com", "192.0.2.128/25"],
            "scope_type": "domain",
        })

        d_del = self.conn("asset_domain").insert_one({
            "domain": "dead.example.com",
            "ips": ["192.0.2.10", "192.0.2.20", "192.0.2.130"],
            "scope_id": scope_str,
        }).inserted_id
        self.conn("asset_domain").insert_one({
            "domain": "alive.example.com",
            "ips": ["192.0.2.20"],
            "scope_id": scope_str,
        })

        # 192.0.2.10: orphan -> MUST be reclaimed along with direct-IP site
        # 192.0.2.20: shared with alive.example.com -> MUST survive (with dead.example.com pulled)
        # 192.0.2.130: covered by scope CIDR 192.0.2.128/25 -> MUST survive
        self.conn("asset_ip").insert_many([
            {"ip": "192.0.2.10", "domain": ["dead.example.com"], "port_info": [{"port_id": 80, "service_name": "http"}], "scope_id": scope_str},
            {"ip": "192.0.2.20", "domain": ["dead.example.com", "alive.example.com"], "port_info": [{"port_id": 443, "service_name": "https"}], "scope_id": scope_str},
            {"ip": "192.0.2.130", "domain": ["dead.example.com"], "port_info": [{"port_id": 22, "service_name": "ssh"}], "scope_id": scope_str},
        ])
        self.conn("asset_site").insert_many([
            {"site": "http://dead.example.com", "hostname": "dead.example.com", "ip": "192.0.2.10", "scope_id": scope_str},
            {"site": "http://192.0.2.10", "hostname": "192.0.2.10", "ip": "192.0.2.10", "scope_id": scope_str},
            {"site": "https://alive.example.com", "hostname": "alive.example.com", "ip": "192.0.2.20", "scope_id": scope_str},
        ])
        self.conn("asset_wih").insert_many([
            {"record_type": "domain", "content": "dead.example.com", "site": "https://alive.example.com", "scope_id": scope_str},
            {"record_type": "api_endpoint", "content": "GET /secret", "site": "http://dead.example.com", "scope_id": scope_str},
            {"record_type": "domain", "content": "alive.example.com", "site": "https://alive.example.com", "scope_id": scope_str},
        ])

        res = self.cascade_mod.handle_dimension_delete(
            "domain", is_asset_route=True, args={"_id": [str(d_del)], "scope_id": scope_str}
        )
        self.assertEqual(res["code"], 200)

        remaining_ips = {d["ip"]: d for d in self.conn("asset_ip").find({"scope_id": scope_str})}
        self.assertNotIn("192.0.2.10", remaining_ips)
        self.assertIn("192.0.2.20", remaining_ips)
        self.assertEqual(remaining_ips["192.0.2.20"]["domain"], ["alive.example.com"])
        self.assertIn("192.0.2.130", remaining_ips)
        self.assertEqual(remaining_ips["192.0.2.130"]["domain"], [])

        remaining_sites = {d["site"] for d in self.conn("asset_site").find({"scope_id": scope_str})}
        self.assertEqual(remaining_sites, {"https://alive.example.com"})

        remaining_wih = [d["content"] for d in self.conn("asset_wih").find({"scope_id": scope_str})]
        self.assertEqual(remaining_wih, ["alive.example.com"])

    def test_ip_delete_unbinds_domain_ips_preserving_domain(self):
        tid = str(ObjectId())
        self.conn("task").insert_one({"_id": ObjectId(tid), "name": "ip_del_task", "status": "done", "type": "domain"})
        self.conn("domain").insert_one({"domain": "app.example.com", "ips": ["192.0.2.50", "192.0.2.51"], "task_id": tid})
        ip_id = self.conn("ip").insert_one({
            "ip": "192.0.2.50",
            "domain": ["app.example.com"],
            "port_info": [{"port_id": 80, "service_name": "http"}],
            "task_id": tid,
        }).inserted_id
        self.conn("ip").insert_one({
            "ip": "192.0.2.51",
            "domain": ["app.example.com"],
            "port_info": [{"port_id": 443, "service_name": "https"}],
            "task_id": tid,
        })
        self.conn("site").insert_many([
            {"site": "http://192.0.2.50", "hostname": "192.0.2.50", "ip": "192.0.2.50", "task_id": tid},
            {"site": "https://app.example.com", "hostname": "app.example.com", "ip": "192.0.2.51", "task_id": tid},
        ])

        res = self.cascade_mod.handle_dimension_delete("ip", is_asset_route=False, args={"_id": [str(ip_id)], "task_id": tid})
        self.assertEqual(res["code"], 200)

        dom = self.conn("domain").find_one({"task_id": tid, "domain": "app.example.com"})
        self.assertIsNotNone(dom)
        self.assertEqual(dom["ips"], ["192.0.2.51"])
        self.assertEqual([s["site"] for s in self.conn("site").find({"task_id": tid})], ["https://app.example.com"])
        cips = list(self.conn("cip").find({"task_id": tid}))
        self.assertEqual(len(cips), 1)
        self.assertEqual(cips[0]["ip_list"], ["192.0.2.51"])

    def test_service_delete_endpoint_precision_and_derived_rebuild(self):
        scope_id = str(ObjectId())
        t_id = ObjectId()
        self.conn("asset_scope").insert_one({"_id": ObjectId(scope_id), "name": "SvcScope", "scope_array": ["192.0.2.0/24"], "scope_type": "ip"})
        self.conn("task").insert_one({"_id": t_id, "name": "svc_task", "status": "done", "scope_id": scope_id})

        # Two IPs both run http; 192.0.2.1 also runs https
        self.conn("asset_ip").insert_many([
            {
                "ip": "192.0.2.1",
                "scope_id": scope_id,
                "port_info": [
                    {"port_id": 80, "service_name": "http", "product": "nginx"},
                    {"port_id": 443, "service_name": "https", "product": "nginx"},
                ],
            },
            {
                "ip": "192.0.2.2",
                "scope_id": scope_id,
                "port_info": [
                    {"port_id": 80, "service_name": "http", "product": "apache"},
                ],
            },
        ])
        svc_del_id = self.conn("asset_service").insert_one({
            "service_name": "http",
            "service_info": [{"ip": "192.0.2.1", "port_id": 80, "product": "nginx"}],
            "scope_id": scope_id,
        }).inserted_id
        self.conn("asset_service").insert_one({
            "service_name": "http",
            "service_info": [{"ip": "192.0.2.2", "port_id": 80, "product": "apache"}],
            "scope_id": scope_id,
        })

        res = self.cascade_mod.handle_dimension_delete(
            "service", is_asset_route=True, args={"_id": [str(svc_del_id)], "scope_id": scope_id}
        )
        self.assertEqual(res["code"], 200)

        ip1 = self.conn("asset_ip").find_one({"scope_id": scope_id, "ip": "192.0.2.1"})
        ip2 = self.conn("asset_ip").find_one({"scope_id": scope_id, "ip": "192.0.2.2"})
        self.assertEqual([p["port_id"] for p in ip1["port_info"]], [443])
        self.assertEqual([p["port_id"] for p in ip2["port_info"]], [80])

        # Rebuilt asset_service must retain http for 192.0.2.2:80 and https for 192.0.2.1:443
        svc_map = {d["service_name"]: d["service_info"] for d in self.conn("asset_service").find({"scope_id": scope_id})}
        self.assertIn("http", svc_map)
        self.assertEqual([(e["ip"], e["port_id"]) for e in svc_map["http"]], [("192.0.2.2", 80)])
        self.assertIn("https", svc_map)
        self.assertEqual([(e["ip"], e["port_id"]) for e in svc_map["https"]], [("192.0.2.1", 443)])

    def test_stat_finger_delete_pulls_dict_and_string_fingers_keeping_site(self):
        tid = str(ObjectId())
        self.conn("task").insert_one({"_id": ObjectId(tid), "name": "f_task", "status": "done"})
        self.conn("site").insert_many([
            {"site": "http://s1.example.com", "finger": [{"name": "Nginx"}, {"name": "Vue"}], "task_id": tid},
            {"site": "http://s2.example.com", "finger": ["Nginx", "React"], "task_id": tid},
        ])
        self.conn("stat_finger").insert_many([
            {"name": "Nginx", "cnt": 2, "task_id": tid},
            {"name": "Vue", "cnt": 1, "task_id": tid},
            {"name": "React", "cnt": 1, "task_id": tid},
        ])

        res = self.cascade_mod.handle_dimension_delete(
            "stat_finger", is_asset_route=False, args={"name": ["Nginx"], "task_id": tid, "source_type": "task"}
        )
        self.assertEqual(res["code"], 200)

        # Both sites survive; Nginx removed from both dict & string finger formats
        self.assertEqual(self.conn("site").count_documents({"task_id": tid}), 2)
        s1 = self.conn("site").find_one({"site": "http://s1.example.com"})
        s2 = self.conn("site").find_one({"site": "http://s2.example.com"})
        self.assertEqual(s1["finger"], [{"name": "Vue"}])
        self.assertEqual(s2["finger"], ["React"])

        fingers = {d["name"]: d["cnt"] for d in self.conn("stat_finger").find({"task_id": tid})}
        self.assertEqual(fingers, {"Vue": 1, "React": 1})

    def test_url_prefix_boundary_no_false_positive(self):
        tid = str(ObjectId())
        self.conn("task").insert_one({"_id": ObjectId(tid), "name": "url_bound", "status": "done"})
        site_id = self.conn("site").insert_one({
            "site": "http://a.example.com",
            "hostname": "a.example.com",
            "task_id": tid,
        }).inserted_id
        self.conn("url").insert_many([
            {"url": "http://a.example.com", "task_id": tid},
            {"url": "http://a.example.com/admin", "task_id": tid},
            {"url": "http://a.example.com?id=1", "task_id": tid},
            {"url": "http://a.example.com:8080/login", "task_id": tid},
            {"url": "http://a.example.com.evil.com/path", "task_id": tid},
        ])

        res = self.cascade_mod.handle_dimension_delete("site", is_asset_route=False, args={"_id": [str(site_id)], "task_id": tid})
        self.assertEqual(res["code"], 200)

        remaining_urls = {d["url"] for d in self.conn("url").find({"task_id": tid})}
        self.assertEqual(
            remaining_urls,
            {"http://a.example.com:8080/login", "http://a.example.com.evil.com/path"},
        )

    def test_cip_delete_by_cidr_and_objectid(self):
        scope_id = str(ObjectId())
        self.conn("asset_scope").insert_one({"_id": ObjectId(scope_id), "name": "CipScope", "scope_array": ["192.0.2.0/24", "198.51.100.0/24"], "scope_type": "ip"})
        self.conn("asset_ip").insert_many([
            {"ip": "192.0.2.10", "scope_id": scope_id, "port_info": [{"port_id": 80, "service_name": "http"}]},
            {"ip": "198.51.100.20", "scope_id": scope_id, "port_info": [{"port_id": 443, "service_name": "https"}]},
        ])
        self.cascade_mod.rebuild_scope_derived_collections([scope_id])

        # Delete first CIDR by CIDR string
        res1 = self.cascade_mod.handle_dimension_delete(
            "cip", is_asset_route=True, args={"_id": ["192.0.2.0/24"], "scope_id": scope_id}
        )
        self.assertEqual(res1["code"], 200)
        self.assertEqual([d["ip"] for d in self.conn("asset_ip").find({"scope_id": scope_id})], ["198.51.100.20"])

        # Delete remaining CIDR by ObjectId
        cip_doc = self.conn("asset_cip").find_one({"scope_id": scope_id})
        self.assertIsNotNone(cip_doc)
        res2 = self.cascade_mod.handle_dimension_delete(
            "cip", is_asset_route=True, args={"_id": [str(cip_doc["_id"])], "scope_id": scope_id}
        )
        self.assertEqual(res2["code"], 200)
        self.assertEqual(self.conn("asset_ip").count_documents({"scope_id": scope_id}), 0)
        self.assertEqual(self.conn("asset_cip").count_documents({"scope_id": scope_id}), 0)

    # ------------------------------------------------------------------
    # 4. Derived rebuilds, gen_cip_map regression, SyncAsset & count parity
    # ------------------------------------------------------------------

    def test_gen_cip_map_per_record_have_domain_flag_and_ipv6_guard(self):
        import app.utils.arl as arl_mod
        tid = str(ObjectId())
        self.conn("ip").insert_many([
            {"ip": "192.0.2.1", "domain": ["a.example.com"], "task_id": tid},
            {"ip": "192.0.2.2", "domain": [], "task_id": tid},
            {"ip": "198.51.100.1", "domain": [], "task_id": tid},
            {"ip": "2001:db8::1", "domain": ["v6.example.com"], "task_id": tid},
        ])
        self.conn("domain").insert_many([
            {"domain": "a.example.com", "ips": ["192.0.2.1"], "task_id": tid},
            {"domain": "b.example.com", "ips": ["203.0.113.5"], "task_id": tid},
        ])

        with patch.object(arl_mod, "conn_db", side_effect=self.conn):
            cip_map = arl_mod.gen_cip_map(tid)
        self.assertIn("192.0.2.0/24", cip_map)
        self.assertEqual(cip_map["192.0.2.0/24"]["ip_set"], {"192.0.2.1", "192.0.2.2"})
        self.assertEqual(cip_map["192.0.2.0/24"]["domain_set"], {"a.example.com"})
        # 198.51.100.1 had empty domain AFTER 192.0.2.1 had domain -> must NOT inherit have_domain_flag pollution
        self.assertIn("198.51.100.0/24", cip_map)
        self.assertEqual(cip_map["198.51.100.0/24"]["ip_set"], {"198.51.100.1"})
        self.assertEqual(cip_map["198.51.100.0/24"]["domain_set"], set())
        # IPv6 gracefully ignored without crashing
        self.assertEqual(len(cip_map), 2)

        # rebuild_task_derived_collections cross-references domain.ips to enrich surviving ip records
        # without inventing ghost C-blocks for IPs absent from the ip host table
        self.conn("domain").insert_one({"domain": "enriched.example.com", "ips": ["198.51.100.1"], "task_id": tid})
        self.cascade_mod.rebuild_task_derived_collections([tid], targets=("cip",))
        rebuilt = {d["cidr_ip"]: d for d in self.conn("cip").find({"task_id": tid})}
        self.assertEqual(rebuilt["198.51.100.0/24"]["domain_list"], ["enriched.example.com"])
        self.assertNotIn("203.0.113.0/24", rebuilt)

    def test_sync_asset_update_flag_false_rebuilds_new_service_endpoints_and_alive_guard(self):
        from app.services.syncAsset import SyncAsset
        import app.services.syncAsset as sync_mod

        scope_id = ObjectId()
        scope_str = str(scope_id)
        t_id = ObjectId()
        t_str = str(t_id)

        self.conn("asset_scope").insert_one({"_id": scope_id, "name": "SyncScope", "scope_array": ["192.0.2.0/24"], "scope_type": "ip"})
        self.conn("task").insert_one({"_id": t_id, "name": "t_sync", "status": "done", "scope_id": scope_str})

        # Existing scope already has http on 192.0.2.1:80
        self.conn("asset_ip").insert_one({
            "ip": "192.0.2.1",
            "scope_id": scope_str,
            "port_info": [{"port_id": 80, "service_name": "http", "product": "nginx"}],
        })
        self.conn("asset_service").insert_one({
            "service_name": "http",
            "service_info": [{"ip": "192.0.2.1", "port_id": 80, "product": "nginx"}],
            "scope_id": scope_str,
        })

        # New task discovers http on 192.0.2.2:8080
        self.conn("ip").insert_one({
            "ip": "192.0.2.2",
            "task_id": t_str,
            "port_info": [{"port_id": 8080, "service_name": "http", "product": "tomcat"}],
        })
        self.conn("service").insert_one({
            "service_name": "http",
            "service_info": [{"ip": "192.0.2.2", "port_id": 8080, "product": "tomcat"}],
            "task_id": t_str,
        })

        with patch.object(sync_mod, "conn", side_effect=self.conn):
            SyncAsset(t_str, scope_str, update_flag=False).run()

        # Rebuilt asset_service must now include BOTH 192.0.2.1:80 and 192.0.2.2:8080 as per-endpoint records
        http_docs = list(self.conn("asset_service").find({"scope_id": scope_str, "service_name": "http"}))
        self.assertEqual(len(http_docs), 2)
        endpoints = {(d["ip"], d["port_id"]) for d in http_docs}
        self.assertEqual(endpoints, {("192.0.2.1", 80), ("192.0.2.2", 8080)})

        # Survival guard: if scope is deleted before SyncAsset.run(), nothing should be written
        deleted_scope = str(ObjectId())
        with patch.object(sync_mod, "conn", side_effect=self.conn):
            SyncAsset(t_str, deleted_scope, update_flag=False).run()
        self.assertEqual(self.conn("asset_ip").count_documents({"scope_id": deleted_scope}), 0)

    def test_asset_overview_count_parity_global_and_scoped(self):
        import app.routes.assetOverview as overview_mod

        scope_a = str(ObjectId())
        scope_b = str(ObjectId())

        # Populate global unprefixed collections (including duplicate cidr_ip and stat_finger across tasks)
        self.conn("site").insert_many([{"site": "http://1.example.com"}, {"site": "http://2.example.com"}])
        self.conn("domain").insert_one({"domain": "1.example.com"})
        self.conn("cip").insert_many([
            {"cidr_ip": "192.0.2.0/24", "task_id": "t1"},
            {"cidr_ip": "192.0.2.0/24", "task_id": "t2"},
            {"cidr_ip": "198.51.100.0/24", "task_id": "t1"},
        ])
        self.conn("stat_finger").insert_many([
            {"name": "Nginx", "cnt": 3, "task_id": "t1"},
            {"name": "Nginx", "cnt": 2, "task_id": "t2"},
            {"name": "Apache", "cnt": 1, "task_id": "t1"},
        ])

        # Populate scoped collections
        self.conn("asset_site").insert_many([
            {"site": "http://a.example.com", "scope_id": scope_a},
            {"site": "http://b.example.com", "scope_id": scope_b},
        ])
        self.conn("asset_stat_finger").insert_many([
            {"name": "Nginx", "cnt": 1, "scope_id": scope_a},
            {"name": "Nginx", "cnt": 2, "scope_id": scope_a},
            {"name": "Vue", "cnt": 1, "scope_id": scope_a},
            {"name": "Other", "cnt": 1, "scope_id": scope_b},
        ])

        with patch.object(overview_mod, "conn", side_effect=self.conn):
            self.assertEqual(overview_mod._count_collection("site", None), 2)
            self.assertEqual(overview_mod._count_collection("domain", None), 1)
            self.assertEqual(overview_mod._count_collection("cip", None), 2)  # distinct cidr_ip
            self.assertEqual(overview_mod._count_collection("stat_finger", None), 2)  # distinct name
            self.assertEqual(overview_mod._count_collection("site", scope_a), 1)
            self.assertEqual(overview_mod._count_collection("stat_finger", scope_a), 2)

    # ------------------------------------------------------------------
    # 5. Task deletion, scheduler guards, cache version & migration
    # ------------------------------------------------------------------

    def test_task_delete_del_synced_asset_false_vs_true(self):
        scope_id = str(ObjectId())
        t1 = ObjectId()
        t2 = ObjectId()
        t1_str, t2_str = str(t1), str(t2)

        self.conn("asset_scope").insert_one({"_id": ObjectId(scope_id), "name": "S", "scope_array": ["example.com"], "scope_type": "domain"})
        self.conn("task").insert_many([
            {"_id": t1, "name": "T1", "status": "done", "synced_scope_id": scope_id},
            {"_id": t2, "name": "T2", "status": "done", "synced_scope_id": scope_id},
        ])
        self.conn("domain").insert_many([
            {"domain": "only-t1.example.com", "task_id": t1_str},
            {"domain": "shared.example.com", "task_id": t1_str},
            {"domain": "shared.example.com", "task_id": t2_str},
        ])
        self.conn("asset_domain").insert_many([
            {"domain": "only-t1.example.com", "scope_id": scope_id, "task_id": t1_str},
            {"domain": "shared.example.com", "scope_id": scope_id, "task_id": t1_str},
        ])

        # Case 1: del_task_data=True, del_synced_asset=False -> preserves ALL asset_domain records
        t3 = ObjectId()
        self.conn("task").insert_one({"_id": t3, "name": "T3", "status": "done", "synced_scope_id": scope_id})
        self.conn("domain").insert_one({"domain": "t3.example.com", "task_id": str(t3)})
        self.conn("asset_domain").insert_one({"domain": "t3.example.com", "scope_id": scope_id, "task_id": str(t3)})

        self.cascade_mod.cascade_delete_tasks([str(t3)], del_task_data=True, del_synced_asset=False)
        self.assertIsNone(self.conn("task").find_one({"_id": t3}))
        self.assertEqual(self.conn("domain").count_documents({"task_id": str(t3)}), 0)
        self.assertEqual(self.conn("asset_domain").count_documents({"domain": "t3.example.com", "scope_id": scope_id}), 1)

        # Case 2: del_task_data=True, del_synced_asset=True -> deletes exclusive only-t1, preserves shared (exists in t2)
        self.cascade_mod.cascade_delete_tasks([t1_str], del_task_data=True, del_synced_asset=True)
        self.assertIsNone(self.conn("task").find_one({"_id": t1}))
        self.assertEqual(self.conn("domain").count_documents({"task_id": t1_str}), 0)
        self.assertEqual(self.conn("asset_domain").count_documents({"domain": "only-t1.example.com", "scope_id": scope_id}), 0)
        self.assertEqual(self.conn("asset_domain").count_documents({"domain": "shared.example.com", "scope_id": scope_id}), 1)

    def test_scheduler_orphan_cleanup_preserves_site_and_wih_monitors(self):
        import app.scheduler as sched_mod
        from app.modules import AssetScopeType

        scope_id = ObjectId()
        scope_str = str(scope_id)
        self.conn("asset_scope").insert_one({
            "_id": scope_id,
            "name": "S",
            "scope_array": ["live.example.com"],
            "scope_type": AssetScopeType.DOMAIN,
        })

        site_mon_id = self.conn("scheduler").insert_one({
            "scope_id": scope_str,
            "name": "站点监控-S",
            "domain": "站点监控",
            "scope_type": "site_update_monitor",
            "status": "running",
            "next_run_time": 1,
            "interval": 3600,
        }).inserted_id
        wih_mon_id = self.conn("scheduler").insert_one({
            "scope_id": scope_str,
            "name": "WIH 监控-S",
            "domain": "WIH监控",
            "scope_type": "wih_update_monitor",
            "status": "running",
            "next_run_time": 1,
            "interval": 3600,
        }).inserted_id
        orphan_dom_id = self.conn("scheduler").insert_one({
            "scope_id": scope_str,
            "name": "监控-S-removed.example.com",
            "domain": "removed.example.com",
            "scope_type": AssetScopeType.DOMAIN,
            "status": "running",
            "next_run_time": 1,
            "interval": 3600,
        }).inserted_id

        dispatched = []
        fake_dispatch = {
            "site_update_monitor": {"func": lambda **kw: dispatched.append(("site", kw["scope_id"]))},
            "wih_update_monitor": {"func": lambda **kw: dispatched.append(("wih", kw["scope_id"]))},
        }
        with patch.object(sched_mod, "conn", side_effect=self.conn), \
             patch.dict(sched_mod.DISPATCH_MAP, fake_dispatch):
            sched_mod.asset_monitor_scheduler()

        self.assertIsNotNone(self.conn("scheduler").find_one({"_id": site_mon_id}))
        self.assertIsNotNone(self.conn("scheduler").find_one({"_id": wih_mon_id}))
        self.assertIsNone(self.conn("scheduler").find_one({"_id": orphan_dom_id}))
        self.assertEqual(set(dispatched), {("site", scope_str), ("wih", scope_str)})

    def test_cascade_delete_schedulers_stop_only_and_is_scope_target_alive(self):
        scope_id = ObjectId()
        scope_str = str(scope_id)
        sched_id = ObjectId()
        t_running = ObjectId()
        t_done = ObjectId()

        self.conn("asset_scope").insert_one({
            "_id": scope_id,
            "name": "MonScope",
            "scope_array": ["mon.example.com", "192.0.2.0/24"],
            "scope_type": "domain",
        })
        self.conn("scheduler").insert_one({
            "_id": sched_id,
            "scope_id": scope_str,
            "domain": "mon.example.com",
            "status": "running",
        })
        self.conn("task").insert_many([
            {"_id": t_running, "status": "running", "celery_id": "cid-1", "options": {"scheduler_id": str(sched_id)}},
            {"_id": t_done, "status": "done", "celery_id": "cid-2", "options": {"scheduler_id": str(sched_id)}},
        ])

        self.cascade_mod.cascade_delete_schedulers([str(sched_id)], stop_only=True)

        # Running task stopped, done task & scheduler doc preserved
        self.assertEqual(self.conn("task").find_one({"_id": t_running})["status"], "stop")
        self.assertEqual(self.conn("task").find_one({"_id": t_done})["status"], "done")
        self.assertIsNotNone(self.conn("scheduler").find_one({"_id": sched_id}))

        # Survival guard checks
        self.assertTrue(self.cascade_mod.is_scope_target_alive(scope_str))
        self.assertTrue(self.cascade_mod.is_scope_target_alive(scope_str, target="sub.mon.example.com"))
        self.assertTrue(self.cascade_mod.is_scope_target_alive(scope_str, target="192.0.2.42", strict_ip=True))
        self.assertFalse(self.cascade_mod.is_scope_target_alive(scope_str, target="other.example.com"))
        self.assertFalse(self.cascade_mod.is_scope_target_alive(scope_str, target="198.51.100.1", strict_ip=True))
        self.assertFalse(self.cascade_mod.is_scope_target_alive(str(ObjectId())))

    def test_cross_process_cache_version_invalidation(self):
        import app.routes.dashboard as dash_mod
        import app.utils.monitor_diff as mdiff_mod

        t1 = ObjectId()
        self.conn("task").insert_one({"_id": t1, "scope_id": "scope-old"})

        with patch.object(dash_mod, "conn", side_effect=self.conn), \
             patch.object(mdiff_mod, "conn_db", side_effect=self.conn):
            dash_mod.clear_local_dashboard_cache()
            mdiff_mod.clear_task_scope_cache()

            # Prime caches in worker A at version 0
            dash_mod._set_cached_dashboard_entry("stats", {"stale": True}, 0)
            self.assertEqual(mdiff_mod._get_task_scope_id(str(t1)), "scope-old")

            # Mutate DB and bump cross-process versions (simulating worker B)
            self.conn("task").update_one({"_id": t1}, {"$set": {"scope_id": "scope-new"}})
            self.cascade_mod.bump_asset_cache_versions()

            dash_doc = self.conn("system_config").find_one({"_id": dash_mod._DASHBOARD_CACHE_VERSION_ID})
            ts_doc = self.conn("system_config").find_one({"_id": mdiff_mod._TASK_SCOPE_CACHE_VERSION_ID})
            self.assertIsNotNone(dash_doc)
            self.assertGreaterEqual(dash_doc["version"], 1)
            self.assertIsNotNone(ts_doc)
            self.assertGreaterEqual(ts_doc["version"], 1)

            # Simulate another Gunicorn worker still holding stale entry at old ver=0
            dash_mod._set_cached_dashboard_entry("stats", {"stale": True}, 0)
            cached, ver = dash_mod._get_cached_dashboard_entry("stats", 60)
            self.assertIsNone(cached)
            self.assertEqual(ver, dash_doc["version"])

            # Simulate another worker checking task_scope cache version after throttle window
            mdiff_mod._TASK_SCOPE_VER_STATE["ver"] = 0
            mdiff_mod._TASK_SCOPE_VER_STATE["checked_at"] = 0.0
            self.assertEqual(mdiff_mod._get_task_scope_id(str(t1)), "scope-new")

    def test_migrate_heal_cascade_and_derived_assets_idempotent(self):
        import app.utils.arlupdate as arlupdate_mod

        live_scope = ObjectId()
        live_str = str(live_scope)
        ghost_scope_str = str(ObjectId())
        t_broken_cip = ObjectId()
        t_broken_str = str(t_broken_cip)

        self.conn("asset_scope").insert_one(
            {"_id": live_scope, "name": "Live", "scope_array": ["live.example.com"], "scope_type": "domain"}
        )
        # Orphan asset_domain & scheduler pointing to ghost scope
        self.conn("asset_domain").insert_one({"domain": "ghost.example.com", "scope_id": ghost_scope_str})
        self.conn("scheduler").insert_one({"scope_id": ghost_scope_str, "domain": "ghost.example.com"})

        # Live scope with stale stat_finger/service/cip vs real host tables
        self.conn("asset_site").insert_one({
            "site": "https://live.example.com",
            "hostname": "live.example.com",
            "finger": [{"name": "RealFinger"}],
            "scope_id": live_str,
        })
        self.conn("asset_stat_finger").insert_one({"name": "GhostFinger", "cnt": 99, "scope_id": live_str})
        self.conn("asset_ip").insert_one({
            "ip": "192.0.2.88",
            "scope_id": live_str,
            "port_info": [{"port_id": 8080, "service_name": "http-proxy"}],
        })
        self.conn("asset_service").insert_one({
            "service_name": "stale-svc",
            "service_info": [{"ip": "192.0.2.99", "port_id": 9999}],
            "scope_id": live_str,
        })

        # Historical task cip missing domain_list due to old gen_cip_map bug
        self.conn("ip").insert_one({"ip": "192.0.2.77", "domain": ["fix.example.com"], "task_id": t_broken_str})
        self.conn("cip").insert_one({
            "cidr_ip": "192.0.2.0/24",
            "ip_list": ["192.0.2.77"],
            "ip_count": 1,
            "domain_list": [],
            "domain_count": 0,
            "task_id": t_broken_str,
        })

        with patch.object(arlupdate_mod, "conn_db", side_effect=self.conn):
            arlupdate_mod.migrate_heal_cascade_and_derived_assets(run_in_thread=False)

        # Ghost scope data purged, live scope derived tables rebuilt from host tables, broken task cip repaired
        self.assertEqual(self.conn("asset_domain").count_documents({"scope_id": ghost_scope_str}), 0)
        self.assertEqual(self.conn("scheduler").count_documents({"scope_id": ghost_scope_str}), 0)
        self.assertEqual([d["name"] for d in self.conn("asset_stat_finger").find({"scope_id": live_str})], ["RealFinger"])
        self.assertEqual([d["service_name"] for d in self.conn("asset_service").find({"scope_id": live_str})], ["http-proxy"])
        self.assertEqual([d["cidr_ip"] for d in self.conn("asset_cip").find({"scope_id": live_str})], ["192.0.2.0/24"])
        repaired_cip = self.conn("cip").find_one({"task_id": t_broken_str})
        self.assertEqual(repaired_cip["domain_list"], ["fix.example.com"])
        self.assertEqual(repaired_cip["domain_count"], 1)

        sentinel = self.conn("system_config").find_one({"_id": "migration_cascade_heal_v1"})
        self.assertIsNotNone(sentinel)
        self.assertEqual(sentinel["status"], "completed")

        # Second run is a no-op (insert synthetic ghost record and confirm it is NOT touched)
        self.conn("asset_domain").insert_one({"domain": "after-sentinel.example.com", "scope_id": ghost_scope_str})
        with patch.object(arlupdate_mod, "conn_db", side_effect=self.conn):
            arlupdate_mod.migrate_heal_cascade_and_derived_assets(run_in_thread=False)
        self.assertEqual(self.conn("asset_domain").count_documents({"domain": "after-sentinel.example.com"}), 1)

    def test_unified_service_fusion_dedup_calibration_and_migration(self):
        import app.utils.arlupdate as arlupdate_mod
        import app.routes.service as svc_route_mod
        import app.routes.assetOverview as overview_mod
        from app.services.service_fusion import sync_npoc_items_to_service_and_ip

        t1 = str(ObjectId())
        t2 = str(ObjectId())
        scope_id = str(ObjectId())

        # 1. Legacy grouped service doc in t1 + npoc_service doc on same (ip, port)
        self.conn("ip").insert_one({
            "task_id": t1,
            "ip": "192.0.2.10",
            "port_info": [
                {"port_id": 6379, "service_name": "unknown", "product": "Redis key-value store", "version": "7.0.5"},
                {"port_id": 22, "service_name": "ssh", "product": "OpenSSH", "version": "8.9"},
            ],
        })
        self.conn("service").insert_many([
            {
                "task_id": t1,
                "service_name": "unknown",
                "service_info": [{"ip": "192.0.2.10", "port_id": 6379, "product": "Redis key-value store", "version": "7.0.5"}],
            },
            {
                "task_id": t1,
                "service_name": "ssh",
                "service_info": [{"ip": "192.0.2.10", "port_id": 22, "product": "OpenSSH", "version": "8.9"}],
            },
        ])

        # Real-time Python sniffer detection calibrates 192.0.2.10:6379 from 'unknown' to 'redis'
        npoc_results = [
            {"scheme": "redis", "host": "192.0.2.10", "port": "6379", "target": "redis://192.0.2.10:6379", "task_id": t1}
        ]
        self.conn("npoc_service").insert_many(npoc_results)
        sync_npoc_items_to_service_and_ip(t1, npoc_results, db_getter=self.conn)

        # Migrate remaining legacy grouped docs (like ssh:22) via migrate_unified_service_assets
        with patch.object(arlupdate_mod, "conn_db", side_effect=self.conn):
            arlupdate_mod.migrate_unified_service_assets()

        t1_svcs = {d["port_id"]: d for d in self.conn("service").find({"task_id": t1})}
        self.assertEqual(set(t1_svcs.keys()), {22, 6379})
        self.assertEqual(t1_svcs[6379]["service_name"], "redis")
        self.assertEqual(t1_svcs[6379]["product"], "Redis key-value store")
        self.assertEqual(t1_svcs[6379]["version"], "7.0.5")
        self.assertEqual(t1_svcs[6379]["sources"], ["nmap", "npoc"])
        self.assertEqual(t1_svcs[22]["service_name"], "ssh")
        self.assertEqual(t1_svcs[22]["sources"], ["nmap"])

        # 2. Task t2 scans the same 192.0.2.10:6379 with only Nmap 'unknown'; global query must deduplicate to 2 endpoints
        self.conn("service").insert_one({
            "task_id": t2,
            "ip": "192.0.2.10",
            "port_id": 6379,
            "service_name": "unknown",
            "product": "",
            "version": "",
            "sources": ["nmap"],
        })

        svc_res = svc_route_mod.ServiceResource()
        with patch.object(svc_route_mod, "conn", side_effect=self.conn), \
             patch.object(overview_mod, "conn", side_effect=self.conn):
            global_data = svc_res.build_data(args={"page": 1, "size": 10}, collection="service")
            self.assertEqual(global_data["total"], 2)
            self.assertEqual(overview_mod._count_collection("service", None), 2)
            by_port = {item["port_id"]: item for item in global_data["items"]}
            self.assertEqual(by_port[6379]["service_name"], "redis")
            self.assertEqual(by_port[6379]["product"], "Redis key-value store")
            self.assertEqual(by_port[6379]["sources"], ["nmap", "npoc"])

            # Filter by source='npoc' in global mode
            npoc_only = svc_res.build_data(args={"page": 1, "size": 10, "sources": "npoc"}, collection="service")
            self.assertEqual(npoc_only["total"], 1)
            self.assertEqual(npoc_only["items"][0]["port_id"], 6379)

        # 3. Asset scope rebuild merges asset_ip + asset_npoc_service into asset_service
        self.conn("asset_ip").insert_one({
            "scope_id": scope_id,
            "ip": "192.0.2.10",
            "port_info": [{"port_id": 6379, "service_name": "unknown", "product": "Redis", "version": "7.0"}],
        })
        self.conn("asset_npoc_service").insert_one({
            "scope_id": scope_id,
            "host": "192.0.2.10",
            "port": "6379",
            "scheme": "redis",
            "target": "redis://192.0.2.10:6379",
        })
        self.cascade_mod.rebuild_scope_derived_collections([scope_id], targets=("service",))
        scoped_svcs = list(self.conn("asset_service").find({"scope_id": scope_id}))
        self.assertEqual(len(scoped_svcs), 1)
        self.assertEqual(scoped_svcs[0]["service_name"], "redis")
        self.assertEqual(scoped_svcs[0]["product"], "Redis")
        self.assertEqual(scoped_svcs[0]["sources"], ["nmap", "npoc"])


if __name__ == "__main__":
    unittest.main()
