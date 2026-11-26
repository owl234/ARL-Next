import datetime
import json
import unittest
from unittest.mock import patch

from bson import ObjectId
import mongomock


class _FakeDB:
    def __init__(self):
        self.client = mongomock.MongoClient()
        self.db = self.client["arl_test_discovery_time"]

    def conn(self, name):
        return self.db[name]


class TestAssetDiscoveryTime(unittest.TestCase):
    def setUp(self):
        self.fake = _FakeDB()
        self.conn = self.fake.conn

        import app.utils as utils_mod
        import app.utils.conn as conn_mod
        import app.utils.arlupdate as arlupdate_mod
        import app.routes as routes_mod
        import app.routes.service as service_route_mod
        import app.routes.cip as cip_route_mod
        import app.routes.assetCip as asset_cip_route_mod
        import app.routes.stat_finger as stat_finger_route_mod
        import app.routes.assetStatFinger as asset_stat_finger_route_mod
        import app.services.syncAsset as sync_asset_mod

        self.utils_mod = utils_mod
        self.arlupdate_mod = arlupdate_mod
        self.routes_mod = routes_mod
        self.service_route_mod = service_route_mod
        self.cip_route_mod = cip_route_mod
        self.asset_cip_route_mod = asset_cip_route_mod
        self.stat_finger_route_mod = stat_finger_route_mod
        self.asset_stat_finger_route_mod = asset_stat_finger_route_mod
        self.sync_asset_mod = sync_asset_mod

        class _FakeConnMongo:
            def __init__(self, fn):
                self._fn = fn

            def get_collection_proxy(self, collection, db_name=None):
                return self._fn(collection)

        self.patchers = [
            patch.object(utils_mod, "conn_db", side_effect=self.conn),
            patch.object(conn_mod, "conn_db", side_effect=self.conn),
            patch.object(conn_mod, "ConnMongo", return_value=_FakeConnMongo(self.conn)),
            patch.object(arlupdate_mod, "conn_db", side_effect=self.conn),
            patch.object(routes_mod, "conn", side_effect=self.conn),
            patch.object(service_route_mod, "conn", side_effect=self.conn),
            patch.object(cip_route_mod, "conn", side_effect=self.conn),
            patch.object(sync_asset_mod, "conn", side_effect=self.conn),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()

    def test_time_helpers_normalize_strings_datetimes_and_objectids(self):
        dt = self.utils_mod.to_datetime_obj("2026-11-10 08:09:10")
        self.assertEqual(dt, datetime.datetime(2026, 11, 10, 8, 9, 10))
        self.assertEqual(self.utils_mod.format_datetime_str(dt), "2026-11-10 08:09:10")

        oid = ObjectId.from_datetime(datetime.datetime(2026, 5, 1, 0, 0, 0, tzinfo=datetime.timezone.utc))
        derived = self.utils_mod.to_datetime_obj(None, fallback_oid=oid)
        self.assertIsInstance(derived, datetime.datetime)
        self.assertIsNone(derived.tzinfo)
        expected_local = oid.generation_time.astimezone().replace(tzinfo=None).replace(microsecond=0)
        self.assertEqual(derived, expected_local)

    def test_safe_insert_asset_persists_bson_datetime_and_preserves_first_seen(self):
        first_dt = datetime.datetime(2026, 11, 1, 10, 0, 0)
        later_dt = datetime.datetime(2026, 11, 5, 12, 0, 0)

        self.utils_mod.safe_insert_asset(
            "domain",
            ["task_id", "domain"],
            {"task_id": "t1", "domain": "a.example.test", "save_date": first_dt},
        )
        # Re-upserting the same record must keep original save_date ($setOnInsert)
        self.utils_mod.safe_insert_asset(
            "domain",
            ["task_id", "domain"],
            {"task_id": "t1", "domain": "a.example.test", "source": "brute", "save_date": later_dt},
        )
        doc = self.conn("domain").find_one({"task_id": "t1", "domain": "a.example.test"})
        self.assertEqual(doc["save_date"], first_dt)
        self.assertEqual(doc["source"], "brute")

        # safe_insert_asset_many converts string save_date to BSON datetime and fills missing save_date
        self.utils_mod.safe_insert_asset_many(
            "fileleak",
            ["task_id", "site", "url"],
            [
                {"task_id": "t1", "site": "https://a.example.test", "url": "https://a.example.test/.env", "save_date": "2026-11-02 09:30:00"},
                {"task_id": "t1", "site": "https://a.example.test", "url": "https://a.example.test/robots.txt"},
            ],
        )
        d1 = self.conn("fileleak").find_one({"url": "https://a.example.test/.env"})
        d2 = self.conn("fileleak").find_one({"url": "https://a.example.test/robots.txt"})
        self.assertEqual(d1["save_date"], datetime.datetime(2026, 11, 2, 9, 30, 0))
        self.assertIsInstance(d2["save_date"], datetime.datetime)

    def test_sync_asset_inherits_original_save_date_and_only_advances_update_date_on_rescan(self):
        t1_dt = datetime.datetime(2026, 11, 1, 9, 0, 0)
        t2_dt = datetime.datetime(2026, 11, 10, 14, 0, 0)
        scope_oid = ObjectId()
        scope_id = str(scope_oid)
        self.conn("asset_scope").insert_one({
            "_id": scope_oid,
            "name": "TestScope",
            "scope": "example.test",
            "scope_array": ["example.test"],
            "scope_type": "domain",
        })

        self.conn("domain").insert_one({
            "task_id": "task-1",
            "domain": "api.example.test",
            "record": ["192.0.2.10"],
            "save_date": t1_dt,
        })
        sync1 = self.sync_asset_mod.SyncAsset(task_id="task-1", scope_id=scope_id, update_flag=True, category=["domain"])
        sync1.sync_by_category("domain")

        first_doc = self.conn("asset_domain").find_one({"scope_id": scope_id, "domain": "api.example.test"})
        self.assertEqual(first_doc["save_date"], t1_dt)
        # First insert aligns update_date with original discovery time (no spurious two-line delta)
        self.assertEqual(first_doc["update_date"], t1_dt)

        # Second scan refreshes the record: save_date stays t1_dt, update_date advances to now
        self.conn("domain").insert_one({
            "task_id": "task-2",
            "domain": "api.example.test",
            "record": ["192.0.2.11"],
            "save_date": t2_dt,
        })
        sync2 = self.sync_asset_mod.SyncAsset(task_id="task-2", scope_id=scope_id, update_flag=True, category=["domain"])
        sync2.sync_by_category("domain")

        updated_doc = self.conn("asset_domain").find_one({"scope_id": scope_id, "domain": "api.example.test"})
        self.assertEqual(updated_doc["save_date"], t1_dt)
        self.assertGreater(updated_doc["update_date"], t1_dt)

    def test_migrate_asset_discovery_timestamps_backfills_and_is_idempotent(self):
        legacy_oid = ObjectId.from_datetime(datetime.datetime(2026, 4, 15, 4, 0, 0, tzinfo=datetime.timezone.utc))
        expected_oid_local = legacy_oid.generation_time.astimezone().replace(tzinfo=None).replace(microsecond=0)

        # Missing save_date on task collection
        self.conn("site").insert_one({"_id": legacy_oid, "task_id": "t1", "site": "https://legacy.example.test"})
        # String save_date on vuln & nuclei_result
        self.conn("vuln").insert_one({"task_id": "t1", "target": "https://legacy.example.test", "save_date": "2026-10-05 11:22:33"})
        self.conn("nuclei_result").insert_one({"task_id": "t1", "target": "https://legacy.example.test", "save_date": "2026-10-06 07:08:09"})
        # Asset collection with update_date only (missing save_date)
        asset_upd = datetime.datetime(2026, 3, 1, 8, 0, 0)
        self.conn("asset_site").insert_one({
            "_id": legacy_oid,
            "scope_id": "s1",
            "site": "https://legacy.example.test",
            "update_date": asset_upd,
        })
        # Asset collection with string save_date and missing update_date
        self.conn("asset_vuln").insert_one({
            "scope_id": "s1",
            "target": "https://legacy.example.test",
            "save_date": "2026-09-20 15:00:00",
        })

        self.arlupdate_mod.migrate_asset_discovery_timestamps()
        # Second run should be a clean no-op
        self.arlupdate_mod.migrate_asset_discovery_timestamps()

        site_doc = self.conn("site").find_one({"_id": legacy_oid})
        self.assertEqual(site_doc["save_date"], expected_oid_local)

        vuln_doc = self.conn("vuln").find_one({"task_id": "t1"})
        self.assertEqual(vuln_doc["save_date"], datetime.datetime(2026, 10, 5, 11, 22, 33))

        nuc_doc = self.conn("nuclei_result").find_one({"task_id": "t1"})
        self.assertEqual(nuc_doc["save_date"], datetime.datetime(2026, 10, 6, 7, 8, 9))

        asset_site_doc = self.conn("asset_site").find_one({"_id": legacy_oid})
        self.assertEqual(asset_site_doc["save_date"], asset_upd)
        self.assertEqual(asset_site_doc["update_date"], asset_upd)

        asset_vuln_doc = self.conn("asset_vuln").find_one({"scope_id": "s1"})
        self.assertEqual(asset_vuln_doc["save_date"], datetime.datetime(2026, 9, 20, 15, 0, 0))
        self.assertEqual(asset_vuln_doc["update_date"], datetime.datetime(2026, 9, 20, 15, 0, 0))

    def test_all_26_routes_expose_save_date_filters_and_asset_routes_expose_update_date(self):
        task_modules = [
            "site", "domain", "ip", "cert", "service", "fileleak", "url",
            "cip", "stat_finger", "wih", "vuln", "nuclei_result", "npoc_service",
        ]
        asset_modules = [
            "assetSite", "assetDomain", "assetIP", "assetCert", "assetService",
            "assetFileleak", "assetUrl", "assetCip", "assetStatFinger",
            "assetWih", "assetVuln", "assetNucleiResult", "assetNpocService",
        ]
        for mod_name in task_modules:
            mod = __import__(f"app.routes.{mod_name}", fromlist=["base_search_fields"])
            self.assertIn("save_date__dgt", mod.base_search_fields, mod_name)
            self.assertIn("save_date__dlt", mod.base_search_fields, mod_name)

        for mod_name in asset_modules:
            mod = __import__(f"app.routes.{mod_name}", fromlist=["base_search_fields"])
            self.assertIn("save_date__dgt", mod.base_search_fields, mod_name)
            self.assertIn("save_date__dlt", mod.base_search_fields, mod_name)
            self.assertIn("update_date__dgt", mod.base_search_fields, mod_name)
            self.assertIn("update_date__dlt", mod.base_search_fields, mod_name)

    def test_inclusive_date_range_query_and_cert_json_export(self):
        res = self.routes_mod.ARLResource()
        q = res.build_db_query({
            "save_date__dgt": "2026-11-10",
            "save_date__dlt": "2026-11-10",
        })
        self.assertEqual(q["save_date"]["$gte"], datetime.datetime(2026, 11, 10, 0, 0, 0))
        self.assertEqual(q["save_date"]["$lte"], datetime.datetime(2026, 11, 10, 23, 59, 59))

        self.conn("asset_cert").insert_one({
            "scope_id": "s1",
            "ip": "192.0.2.10",
            "port": 443,
            "cert": {"subject_dn": "CN=example.test"},
            "save_date": datetime.datetime(2026, 11, 10, 0, 0, 0),
            "update_date": datetime.datetime(2026, 11, 12, 12, 30, 0),
        })
        from flask import Flask
        app = Flask(__name__)
        with app.test_request_context():
            resp = res.send_export_cert_json({"scope_id": "s1", "save_date__dgt": "2026-11-10 00:00:00", "save_date__dlt": "2026-11-10 23:59:59"}, "asset_cert")
            payload = json.loads(resp.get_data(as_text=True))
            self.assertEqual(len(payload), 1)
            self.assertEqual(payload[0]["save_date"], "2026-11-10 00:00:00")
            self.assertEqual(payload[0]["update_date"], "2026-11-12 12:30:00")

    def test_global_aggregated_service_cip_and_stat_finger_min_max_filter_and_sort(self):
        d1 = datetime.datetime(2026, 11, 1, 10, 0, 0)
        d2 = datetime.datetime(2026, 11, 15, 16, 0, 0)
        d3 = datetime.datetime(2026, 11, 20, 9, 0, 0)

        # 1. Global service aggregation: same endpoint seen on d1 and d3; another seen only on d2
        self.conn("service").insert_many([
            {"task_id": "t1", "ip": "192.0.2.1", "port_id": 443, "service_name": "https", "sources": ["nmap"], "save_date": d1},
            {"task_id": "t3", "ip": "192.0.2.1", "port_id": 443, "service_name": "https", "sources": ["npoc"], "save_date": d3},
            {"task_id": "t2", "ip": "192.0.2.2", "port_id": 22, "service_name": "ssh", "sources": ["nmap"], "save_date": d2},
        ])
        svc_res = self.service_route_mod.ServiceResource()
        all_svc = svc_res.build_data({"page": 1, "size": 10, "order": "+save_date"}, collection="service")
        self.assertEqual(all_svc["total"], 2)
        self.assertEqual([i["ip"] for i in all_svc["items"]], ["192.0.2.1", "192.0.2.2"])
        self.assertEqual(all_svc["items"][0]["save_date"], "2026-11-01 10:00:00")
        self.assertEqual(all_svc["items"][0]["update_date"], "2026-11-20 09:00:00")
        self.assertEqual(all_svc["items"][1]["save_date"], "2026-11-15 16:00:00")
        self.assertEqual(all_svc["items"][1]["update_date"], "2026-11-15 16:00:00")

        # Post-group save_date filter >= Nov 10 MUST exclude 192.0.2.1 (first seen Nov 1 even though re-seen Nov 20!)
        filtered_svc = svc_res.build_data(
            {"page": 1, "size": 10, "save_date__dgt": "2026-11-10 00:00:00", "save_date__dlt": "2026-11-21 23:59:59"},
            collection="service",
        )
        self.assertEqual(filtered_svc["total"], 1)
        self.assertEqual(filtered_svc["items"][0]["ip"], "192.0.2.2")

        # 2. CIP: verify task-level sorting & date filter via mongomock AND verify global pipeline stages ($min/$max + post-group $match + $sort)
        self.conn("cip").insert_many([
            {"task_id": "t1", "cidr_ip": "192.0.2.0/24", "ip_list": ["192.0.2.1"], "ip_count": 5, "domain_count": 5, "domain_list": [], "save_date": d1},
            {"task_id": "t1", "cidr_ip": "198.51.100.0/24", "ip_list": ["198.51.100.1"], "ip_count": 1, "domain_count": 0, "domain_list": [], "save_date": d2},
            {"task_id": "t3", "cidr_ip": "192.0.2.0/24", "ip_list": ["192.0.2.2"], "ip_count": 1, "domain_count": 0, "domain_list": [], "save_date": d3},
        ])
        cip_res = self.cip_route_mod.CIPResource()
        cip_task_desc = cip_res.build_data({"task_id": "t1", "page": 1, "size": 10, "order": "-save_date"}, collection="cip")
        self.assertEqual(cip_task_desc["total"], 2)
        self.assertEqual([i["cidr_ip"] for i in cip_task_desc["items"]], ["198.51.100.0/24", "192.0.2.0/24"])

        captured_pipelines = []
        orig_cip_col = self.conn("cip")

        class _CipSpy:
            def aggregate(self, pipeline):
                captured_pipelines.append(pipeline)
                # Strip $reduce stage that mongomock lacks; run count pipelines verbatim
                if any("$reduce" in str(st) for st in pipeline):
                    return [
                        {"_id": "198.51.100.0/24", "cidr_ip": "198.51.100.0/24", "ip_count": 1, "domain_count": 0, "save_date": d2, "update_date": d2}
                    ]
                return orig_cip_col.aggregate(pipeline)

            def distinct(self, *a, **kw):
                return orig_cip_col.distinct(*a, **kw)

        with patch.object(self.cip_route_mod, "conn", return_value=_CipSpy()):
            cip_filtered = cip_res.build_data(
                {"page": 1, "size": 10, "order": "-save_date", "save_date__dgt": "2026-11-10 00:00:00", "save_date__dlt": "2026-11-21 23:59:59"},
                collection="cip",
            )
            self.assertEqual(cip_filtered["total"], 1)
            main_pipe = captured_pipelines[0]
            group_stage = next(st["$group"] for st in main_pipe if "$group" in st)
            self.assertEqual(group_stage["save_date"], {"$min": "$save_date"})
            self.assertEqual(group_stage["latest_save_date"], {"$max": "$save_date"})
            # Pre-group $match must NOT contain save_date; post-group $match MUST filter save_date
            self.assertNotIn("save_date", main_pipe[0]["$match"])
            post_matches = [st["$match"] for st in main_pipe[1:] if "$match" in st]
            self.assertTrue(any("save_date" in m for m in post_matches))
            sort_stage = next(st["$sort"] for st in main_pipe if "$sort" in st)
            self.assertEqual(sort_stage["save_date"], -1)

        # 3. stat_finger & asset_stat_finger return save_date/update_date and support filter & sort
        self.conn("stat_finger").insert_many([
            {"task_id": "t1", "name": "Nginx", "cnt": 5, "save_date": d1},
            {"task_id": "t3", "name": "Nginx", "cnt": 3, "save_date": d3},
            {"task_id": "t2", "name": "Vue", "cnt": 2, "save_date": d2},
        ])
        self.conn("asset_stat_finger").insert_many([
            {"scope_id": "s1", "name": "Nginx", "cnt": 8, "save_date": d1, "update_date": d3},
            {"scope_id": "s1", "name": "Vue", "cnt": 2, "save_date": d2, "update_date": d2},
        ])
        self.conn("asset_cip").insert_many([
            {"scope_id": "s1", "cidr_ip": "192.0.2.0/24", "ip_count": 5, "domain_count": 5, "save_date": d1, "update_date": d3},
            {"scope_id": "s1", "cidr_ip": "198.51.100.0/24", "ip_count": 1, "domain_count": 0, "save_date": d2, "update_date": d2},
        ])

        from flask import Flask
        from flask_restx import Api
        app = Flask(__name__)
        api = Api(app, prefix="/api")
        api.add_namespace(self.stat_finger_route_mod.ns)
        api.add_namespace(self.asset_stat_finger_route_mod.ns)
        api.add_namespace(self.asset_cip_route_mod.ns)
        client = app.test_client()

        with patch("app.utils.user.Config.AUTH", False):
            sf_resp = client.get("/api/stat_finger/?order=-save_date").get_json()
            self.assertEqual(sf_resp["total"], 2)
            self.assertEqual([i["name"] for i in sf_resp["items"]], ["Vue", "Nginx"])
            self.assertEqual(sf_resp["items"][1]["save_date"], "2026-11-01 10:00:00")
            self.assertEqual(sf_resp["items"][1]["update_date"], "2026-11-20 09:00:00")

            asf_resp = client.get("/api/asset_stat_finger/?scope_id=s1&order=-save_date").get_json()
            self.assertEqual(asf_resp["total"], 2)
            self.assertEqual([i["name"] for i in asf_resp["items"]], ["Vue", "Nginx"])
            self.assertEqual(asf_resp["items"][1]["save_date"], "2026-11-01 10:00:00")
            self.assertEqual(asf_resp["items"][1]["update_date"], "2026-11-20 09:00:00")

            asf_filtered = client.get("/api/asset_stat_finger/?scope_id=s1&save_date__dgt=2026-11-10&save_date__dlt=2026-11-21").get_json()
            self.assertEqual(asf_filtered["total"], 1)
            self.assertEqual(asf_filtered["items"][0]["name"], "Vue")

            acip_resp = client.get("/api/asset_cip/?scope_id=s1&order=-save_date").get_json()
            self.assertEqual(acip_resp["total"], 2)
            self.assertEqual([i["cidr_ip"] for i in acip_resp["items"]], ["198.51.100.0/24", "192.0.2.0/24"])

    def test_nuclei_webhook_serializes_datetime_save_date_to_json(self):
        from app.services.webhook import NucleiVulnWebHook
        wh = NucleiVulnWebHook(
            task_id="t1",
            scope_id="s1",
            web_hook_url="https://hook.example.test",
            web_hook_token="tok",
            nuclei_results=[{
                "template_id": "cve-test",
                "vuln_name": "Test",
                "vuln_severity": "high",
                "save_date": datetime.datetime(2026, 11, 20, 12, 0, 0),
            }],
        )
        serialized = wh._serialize_results()
        dumped = json.dumps(serialized)
        self.assertIn("2026-11-20 12:00:00", dumped)

    def test_mcp_search_assets_serializes_datetime_save_date_to_json(self):
        from app.mcp_asset import search_mcp_assets
        self.conn("site").insert_one({
            "task_id": "t1",
            "site": "https://mcp.example.test",
            "title": "MCP Test",
            "save_date": datetime.datetime(2026, 11, 20, 15, 30, 45),
        })
        res, is_err = search_mcp_assets("mcp.example.test", asset_type="site", limit=5)
        self.assertFalse(is_err)
        dumped = json.dumps(res)
        self.assertIn("2026-11-20 15:30:45", dumped)


if __name__ == "__main__":
    unittest.main()
