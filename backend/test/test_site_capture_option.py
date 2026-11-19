import copy
import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from bson import ObjectId
from flask import Flask
from flask_restx import Api

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

from app import services, utils
from app.config import Config
from app.helpers.policy import get_options_by_policy_id, normalize_site_capture
from app.modules import TaskTag, WebSiteFetchStatus
from app.routes import policy as policy_route
from app.routes import task as task_route
from app.routes import taskFofa as fofa_route
from app.scheduler import domain_monitor_options, ip_monitor_options
from app.services.commonTask import WebSiteFetch
from app.services.syncAsset import SyncAsset
from app.utils.arlupdate import create_index, update_policy_schema
from app.utils import monitor_diff


class _FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.bulk_ops = []
        self.last_find_one_query = None

    def find(self, query=None, projection=None):
        return [copy.deepcopy(d) for d in self.docs]

    def find_one(self, query=None, projection=None):
        self.last_find_one_query = query
        for doc in self.docs:
            if _match_simple_query(doc, query or {}):
                return copy.deepcopy(doc)
        return None

    def insert_one(self, doc):
        if "_id" not in doc:
            doc["_id"] = ObjectId()
        self.docs.append(copy.deepcopy(doc))
        res = MagicMock()
        res.inserted_id = doc["_id"]
        return res

    def update_one(self, query, update, upsert=False):
        return MagicMock(modified_count=1)

    def find_one_and_replace(self, query, replacement):
        for idx, doc in enumerate(self.docs):
            if _match_simple_query(doc, query):
                self.docs[idx] = copy.deepcopy(replacement)
                return copy.deepcopy(replacement)
        return None

    def bulk_write(self, operations, ordered=True):
        self.bulk_ops.extend(operations)
        return MagicMock()

    def delete_many(self, query):
        return MagicMock(deleted_count=0)

    def delete_one(self, query):
        return MagicMock(deleted_count=1)


def _match_simple_query(doc, query):
    import re
    for k, v in query.items():
        if k == "$or":
            if not any(_match_simple_query(doc, sub) for sub in v):
                return False
            continue
        actual = doc.get(k)
        if isinstance(v, dict):
            if "$regex" in v:
                if not isinstance(actual, str) or not re.search(v["$regex"], actual):
                    return False
            elif "$in" in v:
                if actual not in v["$in"]:
                    return False
            else:
                return False
        elif actual != v:
            return False
    return True


class TestWebSiteFetchSiteCapture(unittest.TestCase):
    def _build_fetcher(self, options, sites=None, catch_all=None):
        task_id = str(ObjectId())
        fetcher = WebSiteFetch(
            task_id=task_id,
            sites=sites or ["https://app.example.com"],
            options=options,
        )
        fetcher.available_sites = list(sites or ["https://app.example.com"])
        fetcher.site_info_list = [
            {"site": s, "hostname": "app.example.com", "ip": "192.0.2.10", "status": 200, "title": "OK", "finger": []}
            for s in fetcher.available_sites
        ]
        if catch_all:
            fetcher.catch_all_sites.update(catch_all)
        return fetcher

    def test_site_capture_disabled_skips_screenshot_and_writes_empty_string(self):
        fetcher = self._build_fetcher(options={"site_capture": False})
        self.assertFalse(fetcher.site_capture_enabled)

        site_col = _FakeCollection()
        with patch.object(utils, "conn_db", side_effect=lambda name: site_col if name == "site" else _FakeCollection()), \
             patch("app.utils.monitor_diff.tag_monitor_diff", side_effect=lambda *a, **k: None), \
             patch("app.services.commonTask.sync_service_from_site"), \
             patch.object(fetcher, "fetch_site"), \
             patch.object(fetcher, "run_func", side_effect=lambda status, fn: fn()) as mock_run_func, \
             patch.object(services, "site_screenshot") as mock_screenshot:
            fetcher.run()

        mock_screenshot.assert_not_called()
        statuses = [call.args[0] for call in mock_run_func.call_args_list]
        self.assertNotIn(WebSiteFetchStatus.SITE_CAPTURE, statuses)
        self.assertEqual(len(site_col.bulk_ops), 1)
        written_doc = site_col.bulk_ops[0]._doc["$set"]
        self.assertEqual(written_doc["screenshot"], "")

    def test_site_capture_default_missing_or_none_is_enabled(self):
        for opts in ({}, {"site_capture": None}, {"site_capture": True}):
            fetcher = self._build_fetcher(options=opts)
            self.assertTrue(fetcher.site_capture_enabled)

            site_col = _FakeCollection()
            with patch.object(utils, "conn_db", side_effect=lambda name: site_col if name == "site" else _FakeCollection()), \
                 patch("app.utils.monitor_diff.tag_monitor_diff", side_effect=lambda *a, **k: None), \
                 patch("app.services.commonTask.sync_service_from_site"), \
                 patch.object(fetcher, "fetch_site"), \
                 patch.object(fetcher, "run_func", side_effect=lambda status, fn: fn()) as mock_run_func, \
                 patch.object(services, "site_screenshot") as mock_screenshot:
                fetcher.run()

            mock_screenshot.assert_called_once()
            self.assertEqual(mock_screenshot.call_args.args[0], ["https://app.example.com"])
            statuses = [call.args[0] for call in mock_run_func.call_args_list]
            self.assertIn(WebSiteFetchStatus.SITE_CAPTURE, statuses)
            written_doc = site_col.bulk_ops[0]._doc["$set"]
            self.assertTrue(written_doc["screenshot"].startswith(f"/image/{fetcher.task_id}/"))

    def test_catch_all_sites_excluded_from_screenshot_even_when_enabled(self):
        sites = ["https://real.example.com", "https://default.example.com"]
        fetcher = self._build_fetcher(
            options={"site_capture": True},
            sites=sites,
            catch_all={"https://default.example.com"},
        )
        site_col = _FakeCollection()
        with patch.object(utils, "conn_db", side_effect=lambda name: site_col if name == "site" else _FakeCollection()), \
             patch("app.utils.monitor_diff.tag_monitor_diff", side_effect=lambda *a, **k: None), \
             patch("app.services.commonTask.sync_service_from_site"), \
             patch.object(fetcher, "fetch_site"), \
             patch.object(fetcher, "run_func", side_effect=lambda status, fn: fn()), \
             patch.object(services, "site_screenshot") as mock_screenshot:
            fetcher.run()

        mock_screenshot.assert_called_once()
        self.assertEqual(mock_screenshot.call_args.args[0], ["https://real.example.com"])
        by_site = {op._doc["$set"]["site"]: op._doc["$set"]["screenshot"] for op in site_col.bulk_ops}
        self.assertTrue(by_site["https://real.example.com"].startswith(f"/image/{fetcher.task_id}/"))
        self.assertEqual(by_site["https://default.example.com"], "")

    def test_all_catch_all_sites_does_not_invoke_screenshot_service(self):
        sites = ["https://default.example.com"]
        fetcher = self._build_fetcher(
            options={"site_capture": True},
            sites=sites,
            catch_all={"https://default.example.com"},
        )
        with patch.object(services, "site_screenshot") as mock_screenshot:
            fetcher.site_screenshot()
        mock_screenshot.assert_not_called()


class TestSyncAssetScreenshotPreservation(unittest.TestCase):
    def test_sync_preserves_existing_screenshot_when_new_scan_has_empty_screenshot(self):
        old_doc = {
            "_id": ObjectId(),
            "scope_id": "scope1",
            "site": "https://app.example.com",
            "task_id": "old_task_111",
            "title": "Portal",
            "status": 200,
            "finger": [],
            "tag": ["待测试"],
            "screenshot": "/image/old_task_111/https_app.example.com.jpg",
        }
        new_doc = {
            "_id": ObjectId(),
            "task_id": "new_task_222",
            "site": "https://app.example.com",
            "title": "Portal",
            "status": 200,
            "finger": [],
            "tag": [],
            "screenshot": "",
        }
        asset_site_col = _FakeCollection(docs=[old_doc])
        syncer = SyncAsset(task_id="new_task_222", scope_id="scope1", update_flag=True)

        with patch("app.services.syncAsset.conn", side_effect=lambda name: asset_site_col if name == "asset_site" else _FakeCollection()):
            syncer._process_sync_chunk("site", "asset_site", [new_doc])

        self.assertEqual(len(asset_site_col.bulk_ops), 1)
        replaced = asset_site_col.bulk_ops[0]._doc
        self.assertEqual(replaced["screenshot"], "/image/old_task_111/https_app.example.com.jpg")
        self.assertEqual(replaced["task_id"], "new_task_222")

    def test_sync_overwrites_screenshot_when_new_scan_captures_fresh_screenshot(self):
        old_doc = {
            "_id": ObjectId(),
            "scope_id": "scope1",
            "site": "https://app.example.com",
            "task_id": "old_task_111",
            "title": "Portal",
            "status": 200,
            "finger": [],
            "tag": [],
            "screenshot": "/image/old_task_111/https_app.example.com.jpg",
        }
        new_doc = {
            "_id": ObjectId(),
            "task_id": "new_task_222",
            "site": "https://app.example.com",
            "title": "Portal",
            "status": 200,
            "finger": [],
            "tag": [],
            "screenshot": "/image/new_task_222/https_app.example.com.jpg",
        }
        asset_site_col = _FakeCollection(docs=[old_doc])
        syncer = SyncAsset(task_id="new_task_222", scope_id="scope1", update_flag=True)

        with patch("app.services.syncAsset.conn", side_effect=lambda name: asset_site_col if name == "asset_site" else _FakeCollection()):
            syncer._process_sync_chunk("site", "asset_site", [new_doc])

        replaced = asset_site_col.bulk_ops[0]._doc
        self.assertEqual(replaced["screenshot"], "/image/new_task_222/https_app.example.com.jpg")


class TestPolicyAndTaskSiteCaptureContract(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        api = Api(self.app)
        api.add_namespace(policy_route.ns, path="/policy")
        api.add_namespace(task_route.ns, path="/task")
        self.client = self.app.test_client()

    def test_get_options_by_policy_id_preserves_false_and_defaults_missing_to_true(self):
        pid_false = ObjectId()
        pid_missing = ObjectId()
        policy_col = _FakeCollection(docs=[
            {
                "_id": pid_false,
                "name": "FastNoShot",
                "policy": {
                    "domain_config": {"domain_brute": True},
                    "ip_config": {"port_scan": True},
                    "site_config": {"site_identify": True, "site_capture": False},
                },
            },
            {
                "_id": pid_missing,
                "name": "LegacyPolicy",
                "policy": {
                    "domain_config": {"domain_brute": True},
                    "ip_config": {"port_scan": True},
                    "site_config": {"site_identify": True},
                },
            },
        ])
        with patch.object(utils, "conn_db", side_effect=lambda name: policy_col if name == "policy" else _FakeCollection()):
            opts_false_task = get_options_by_policy_id(str(pid_false), TaskTag.TASK)
            opts_false_risk = get_options_by_policy_id(str(pid_false), TaskTag.RISK_CRUISING)
            opts_legacy = get_options_by_policy_id(str(pid_missing), TaskTag.TASK)

        self.assertIs(opts_false_task["site_capture"], False)
        self.assertIs(opts_false_risk["site_capture"], False)
        self.assertIs(opts_legacy["site_capture"], True)

    def test_add_and_edit_policy_persist_site_capture(self):
        policy_col = _FakeCollection()
        with patch("app.utils.user.user_login_header", return_value={"username": "admin"}), \
             patch.object(utils, "conn_db", side_effect=lambda name: policy_col if name == "policy" else _FakeCollection()):
            # 1. Create with explicit False
            resp1 = self.client.post("/policy/add/", json={
                "name": "NoShotPolicy",
                "policy": {"site_config": {"site_capture": False}},
            })
            self.assertEqual(resp1.get_json()["code"], 200)
            pid1 = resp1.get_json()["data"]["policy_id"]
            doc1 = policy_col.find_one({"_id": ObjectId(pid1)})
            self.assertIs(doc1["policy"]["site_config"]["site_capture"], False)

            # 2. Create with omitted / null site_capture -> defaults to True without error
            resp2 = self.client.post("/policy/add/", json={
                "name": "DefaultShotPolicy",
                "policy": {"site_config": {"site_capture": None}},
            })
            self.assertEqual(resp2.get_json()["code"], 200)
            pid2 = resp2.get_json()["data"]["policy_id"]
            doc2 = policy_col.find_one({"_id": ObjectId(pid2)})
            self.assertIs(doc2["policy"]["site_config"]["site_capture"], True)

            # 3. Edit unrelated field preserves False
            resp3 = self.client.post("/policy/edit/", json={
                "policy_id": pid1,
                "policy_data": {"name": "NoShotPolicyRenamed"},
            })
            self.assertEqual(resp3.get_json()["code"], 200)
            doc1_after = policy_col.find_one({"_id": ObjectId(pid1)})
            self.assertIs(doc1_after["policy"]["site_config"]["site_capture"], False)

            # 4. Edit toggles False -> True
            resp4 = self.client.post("/policy/edit/", json={
                "policy_id": pid1,
                "policy_data": {"policy": {"site_config": {"site_capture": True}}},
            })
            self.assertEqual(resp4.get_json()["code"], 200)
            doc1_toggled = policy_col.find_one({"_id": ObjectId(pid1)})
            self.assertIs(doc1_toggled["policy"]["site_config"]["site_capture"], True)

    def test_post_task_normalizes_omitted_and_explicit_site_capture(self):
        captured_options = []

        def _fake_submit(target, name, options):
            captured_options.append(dict(options))
            return [{"task_id": str(ObjectId()), "target": target, "name": name}]

        with patch("app.utils.user.user_login_header", return_value={"username": "admin"}), \
             patch.object(task_route, "submit_task_task", side_effect=_fake_submit):
            r_default = self.client.post("/task/", json={"name": "t1", "target": "example.com"})
            r_false = self.client.post("/task/", json={"name": "t2", "target": "example.com", "site_capture": False})
            r_true = self.client.post("/task/", json={"name": "t3", "target": "example.com", "site_capture": True})

        self.assertEqual(r_default.get_json()["code"], 200)
        self.assertEqual(r_false.get_json()["code"], 200)
        self.assertEqual(r_true.get_json()["code"], 200)
        self.assertIs(captured_options[0]["site_capture"], True)
        self.assertIs(captured_options[1]["site_capture"], False)
        self.assertIs(captured_options[2]["site_capture"], True)

    def test_delete_task_preserves_screenshot_dir_referenced_by_asset_site_path(self):
        old_task_id = str(ObjectId())
        with tempfile.TemporaryDirectory() as tmpdir:
            shot_dir = os.path.join(tmpdir, old_task_id)
            os.makedirs(shot_dir, exist_ok=True)
            shot_file = os.path.join(shot_dir, "https_app.example.com.jpg")
            with open(shot_file, "wb") as f:
                f.write(b"jpeg")

            # asset_site now has newer task_id, but still points to old_task_id screenshot path
            asset_site_col = _FakeCollection(docs=[{
                "task_id": str(ObjectId()),
                "site": "https://app.example.com",
                "screenshot": f"/image/{old_task_id}/https_app.example.com.jpg",
            }])
            task_col = _FakeCollection(docs=[{
                "_id": ObjectId(old_task_id),
                "status": "done",
            }])

            def _conn(name):
                if name == "task":
                    return task_col
                if name == "asset_site":
                    return asset_site_col
                return _FakeCollection()

            with patch("app.utils.user.user_login_header", return_value={"username": "admin"}), \
                 patch.object(utils, "conn_db", side_effect=_conn), \
                 patch.object(Config, "SCREENSHOT_DIR", tmpdir):
                resp = self.client.post("/task/delete/", json={
                    "task_id": [old_task_id],
                    "del_task_data": True,
                })

            self.assertEqual(resp.get_json()["code"], 200)
            self.assertTrue(os.path.exists(shot_file), "Referenced screenshot directory must not be deleted")

    def test_update_policy_schema_backfills_missing_site_capture_without_overwriting_false(self):
        mock_col = MagicMock()
        mock_col.update_many.return_value = MagicMock(modified_count=1)
        with patch("app.utils.arlupdate.conn_db", return_value=mock_col):
            update_policy_schema()

        calls = mock_col.update_many.call_args_list
        # First call unsets only scope_config (NOT site_capture)
        unset_filter, unset_op = calls[0].args
        self.assertEqual(unset_filter, {"policy.scope_config": {"$exists": True}})
        self.assertNotIn("policy.site_config.site_capture", unset_op.get("$unset", {}))

        # Second call backfills only missing or None site_capture to True with object-parent guard
        backfill_filter, backfill_op = calls[1].args
        self.assertEqual(backfill_filter, {
            "policy": {"$type": "object"},
            "$and": [
                {"$or": [
                    {"policy.site_config": {"$exists": False}},
                    {"policy.site_config": {"$type": "object"}},
                ]},
                {"$or": [
                    {"policy.site_config.site_capture": {"$exists": False}},
                    {"policy.site_config.site_capture": None},
                ]},
            ],
        })
        self.assertEqual(backfill_op, {"$set": {"policy.site_config.site_capture": True}})

    def test_create_index_registers_asset_site_task_id_and_screenshot_indexes(self):
        created_by_table = {}

        def _fake_conn(table_name):
            col = created_by_table.setdefault(table_name, MagicMock())
            return col

        with patch("app.utils.arlupdate.conn_db", side_effect=_fake_conn):
            create_index()

        asset_site_calls = [c.args[0] for c in created_by_table["asset_site"].create_index.call_args_list]
        self.assertIn("task_id", asset_site_calls)
        self.assertIn("screenshot", asset_site_calls)

    def test_delete_task_removes_unreferenced_screenshot_dir(self):
        old_task_id = str(ObjectId())
        with tempfile.TemporaryDirectory() as tmpdir:
            shot_dir = os.path.join(tmpdir, old_task_id)
            os.makedirs(shot_dir, exist_ok=True)
            shot_file = os.path.join(shot_dir, "https_app.example.com.jpg")
            with open(shot_file, "wb") as f:
                f.write(b"jpeg")

            # asset_site has no reference to old_task_id (neither task_id nor screenshot prefix)
            asset_site_col = _FakeCollection(docs=[{
                "task_id": str(ObjectId()),
                "site": "https://other.example.com",
                "screenshot": f"/image/{str(ObjectId())}/https_other.example.com.jpg",
            }])
            task_col = _FakeCollection(docs=[{
                "_id": ObjectId(old_task_id),
                "status": "done",
            }])

            def _conn(name):
                if name == "task":
                    return task_col
                if name == "asset_site":
                    return asset_site_col
                return _FakeCollection()

            with patch("app.utils.user.user_login_header", return_value={"username": "admin"}), \
                 patch.object(utils, "conn_db", side_effect=_conn), \
                 patch.object(Config, "SCREENSHOT_DIR", tmpdir):
                resp = self.client.post("/task/delete/", json={
                    "task_id": [old_task_id],
                    "del_task_data": True,
                })

            self.assertEqual(resp.get_json()["code"], 200)
            self.assertFalse(os.path.exists(shot_dir), "Unreferenced screenshot directory should be deleted")

    def test_normalize_site_capture_and_string_boolean_edges(self):
        for truthy in (None, True, "true", "True", " 1 ", "yes", "on", 1):
            self.assertIs(normalize_site_capture(truthy), True, f"Expected True for {truthy!r}")
        for falsy in (False, "false", "False", " 0 ", "no", "off", "", 0):
            self.assertIs(normalize_site_capture(falsy), False, f"Expected False for {falsy!r}")

        fetcher = WebSiteFetch(task_id=str(ObjectId()), sites=[], options={"site_capture": "false"})
        self.assertFalse(fetcher.site_capture_enabled)

        policy_col = _FakeCollection()
        with patch("app.utils.user.user_login_header", return_value={"username": "admin"}), \
             patch.object(utils, "conn_db", side_effect=lambda name: policy_col if name == "policy" else _FakeCollection()):
            # AddARLPolicy with omitted site_config -> defaults to True
            r_bare = self.client.post("/policy/add/", json={"name": "BarePolicy", "policy": {}})
            self.assertEqual(r_bare.get_json()["code"], 200)
            pid = r_bare.get_json()["data"]["policy_id"]
            self.assertIs(policy_col.find_one({"_id": ObjectId(pid)})["policy"]["site_config"]["site_capture"], True)

            # EditPolicy with string "false" -> False (not bool("false") == True)
            r_str_false = self.client.post("/policy/edit/", json={
                "policy_id": pid,
                "policy_data": {"policy": {"site_config": {"site_capture": "false"}}},
            })
            self.assertEqual(r_str_false.get_json()["code"], 200)
            self.assertIs(policy_col.find_one({"_id": ObjectId(pid)})["policy"]["site_config"]["site_capture"], False)

            # EditPolicy with flattened policy_data (no outer "policy" key)
            r_flat_true = self.client.post("/policy/edit/", json={
                "policy_id": pid,
                "policy_data": {"site_config": {"site_capture": "1"}},
            })
            self.assertEqual(r_flat_true.get_json()["code"], 200)
            self.assertIs(policy_col.find_one({"_id": ObjectId(pid)})["policy"]["site_config"]["site_capture"], True)

            r_flat_false = self.client.post("/policy/edit/", json={
                "policy_id": pid,
                "policy_data": {"site_config": {"site_capture": "0"}},
            })
            self.assertEqual(r_flat_false.get_json()["code"], 200)
            self.assertIs(policy_col.find_one({"_id": ObjectId(pid)})["policy"]["site_config"]["site_capture"], False)

        # Legacy DB doc storing string "false" is respected by both policy readers
        str_pid = ObjectId()
        str_col = _FakeCollection(docs=[{
            "_id": str_pid,
            "name": "LegacyStringFalse",
            "policy": {
                "domain_config": {},
                "ip_config": {"port_scan": True},
                "site_config": {"site_capture": "false"},
            },
        }])
        with patch.object(utils, "conn_db", return_value=str_col), \
             patch.object(fofa_route, "conn_db", return_value=str_col):
            self.assertIs(get_options_by_policy_id(str(str_pid), TaskTag.TASK)["site_capture"], False)
            self.assertIs(fofa_route.policy_2_task_options(str(str_pid))["site_capture"], False)

    def test_policyless_defaults_enable_site_capture(self):
        self.assertIs(domain_monitor_options["site_capture"], True)
        self.assertIs(ip_monitor_options["site_capture"], True)

        legacy_policy_id = ObjectId()
        policy_col = _FakeCollection(docs=[{
            "_id": legacy_policy_id,
            "policy": {
                "domain_config": {},
                "ip_config": {"port_scan": True},
                "site_config": {"site_identify": True},
            },
        }])
        with patch.object(fofa_route, "conn_db", return_value=policy_col):
            opts = fofa_route.policy_2_task_options(str(legacy_policy_id))
        self.assertIs(opts["site_capture"], True)


class TestMonitorDiffScreenshotGuard(unittest.TestCase):
    def test_empty_screenshot_does_not_trigger_false_update(self):
        old_doc = {
            "scope_id": "scope1",
            "site": "https://app.example.com",
            "title": "Portal",
            "status": 200,
            "screenshot": "/image/old_task/https_app.example.com.jpg",
        }
        new_doc_unchanged = {
            "task_id": "new_task",
            "site": "https://app.example.com",
            "title": "Portal",
            "status": 200,
            "screenshot": "",
        }
        diff_unchanged = monitor_diff._compute_update_diff(old_doc, new_doc_unchanged)
        self.assertEqual(diff_unchanged, {})

        # Real field change still triggers update, without spurious screenshot diff
        new_doc_title_changed = dict(new_doc_unchanged, title="Portal v2")
        diff_title = monitor_diff._compute_update_diff(old_doc, new_doc_title_changed)
        self.assertEqual(diff_title, {"title": {"before": "Portal", "after": "Portal v2"}})

    def test_non_empty_screenshot_backfill_still_triggers_update(self):
        old_doc = {
            "scope_id": "scope1",
            "site": "https://app.example.com",
            "title": "Portal",
            "status": 200,
            "screenshot": "",
        }
        new_doc = {
            "task_id": "new_task",
            "site": "https://app.example.com",
            "title": "Portal",
            "status": 200,
            "screenshot": "/image/new_task/https_app.example.com.jpg",
        }
        diff = monitor_diff._compute_update_diff(old_doc, new_doc)
        self.assertIn("screenshot", diff)
        self.assertEqual(diff["screenshot"]["after"], "/image/new_task/https_app.example.com.jpg")


if __name__ == "__main__":
    unittest.main()
