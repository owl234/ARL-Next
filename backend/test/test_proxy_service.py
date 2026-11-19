# -*- coding: utf-8 -*-
"""
统一系统代理节点池、三域流量分流、旁路白名单、引擎注入与 REST API 单元测试
"""

import importlib.util
import logging
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask
from flask_restx import Api, Resource


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROXY_SERVICE_PATH = BACKEND_ROOT / "app" / "services" / "proxy_service.py"
CONN_PATH = BACKEND_ROOT / "app" / "utils" / "conn.py"
FAVICON_HTTP_PATH = BACKEND_ROOT / "app" / "utils" / "favicon_http.py"
TYC_CLIENT_PATH = BACKEND_ROOT / "app" / "services" / "tycClient.py"
NUCLEI_SCAN_PATH = BACKEND_ROOT / "app" / "services" / "nuclei_scan.py"
SYSTEM_CONFIG_ROUTE_PATH = BACKEND_ROOT / "app" / "routes" / "system_config.py"


class _FakeCollection:
    def __init__(self):
        self.docs = {}

    def find_one(self, query, projection=None):
        doc_id = (query or {}).get("_id")
        doc = self.docs.get(doc_id)
        if not isinstance(doc, dict):
            return None
        return dict(doc)

    def update_one(self, query, update, upsert=False):
        doc_id = (query or {}).get("_id")
        if doc_id not in self.docs and not upsert:
            return
        cur = dict(self.docs.get(doc_id) or {"_id": doc_id})
        if "$set" in update:
            for k, v in update["$set"].items():
                if "." in k:
                    parts = k.split(".")
                    node = cur
                    for p in parts[:-1]:
                        if not isinstance(node.get(p), dict):
                            node[p] = {}
                        else:
                            node[p] = dict(node[p])
                        node = node[p]
                    node[parts[-1]] = v
                else:
                    cur[k] = v
        if "$unset" in update:
            for k in update["$unset"].keys():
                if "." in k:
                    parts = k.split(".")
                    node = cur
                    for p in parts[:-1]:
                        if not isinstance(node.get(p), dict):
                            node = None
                            break
                        node[p] = dict(node[p])
                        node = node[p]
                    if isinstance(node, dict):
                        node.pop(parts[-1], None)
                else:
                    cur.pop(k, None)
        if "$inc" in update:
            for k, v in update["$inc"].items():
                cur[k] = cur.get(k, 0) + v
        self.docs[doc_id] = cur


class _FakeResponse:
    def __init__(self, status_code=200, text="", json_data=None):
        self.status_code = status_code
        self.text = text
        self._json = json_data

    def json(self):
        if self._json is None:
            raise ValueError("no json")
        return self._json


def _load_module(mod_name, path):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestUnifiedProxyService(unittest.TestCase):
    def setUp(self):
        self.coll = _FakeCollection()
        self.version_box = {"val": 1}
        self.tmp_dir = tempfile.mkdtemp(prefix="arl_proxy_test_")
        self.exec_calls = []
        self.log_records = []

        app_pkg = types.ModuleType("app")
        app_pkg.__path__ = [str(BACKEND_ROOT / "app")]

        config_mod = types.ModuleType("app.config")

        class _Config:
            PROXY_URL = ""
            _PROXY_URL = ""
            TYC_ID = "gid-fixture"
            TYC_TOKEN = "tok-fixture"
            TMP_PATH = self.tmp_dir

        config_mod.Config = _Config
        config_mod._read_config_version = lambda: self.version_box["val"]
        config_mod.clear_system_config_cache = lambda: None

        def _bump():
            self.version_box["val"] += 1

        config_mod.bump_system_config_version = _bump

        utils_pkg = types.ModuleType("app.utils")
        utils_pkg.__path__ = [str(BACKEND_ROOT / "app" / "utils")]
        utils_pkg.conn_db = lambda name: self.coll
        utils_pkg.auth = lambda fn: fn

        test_logger = logging.getLogger("arl.proxy.test")

        class _ListHandler(logging.Handler):
            def __init__(self, sink):
                super().__init__()
                self.sink = sink

            def emit(self, record):
                self.sink.append(record.getMessage())

        test_logger.handlers = [_ListHandler(self.log_records)]
        test_logger.setLevel(logging.INFO)
        utils_pkg.get_logger = lambda: test_logger
        utils_pkg.random_choices = lambda length=6: "abc123"

        class _Completed:
            def __init__(self, rc=0):
                self.returncode = rc

        def _fake_exec_system(cmd, timeout=None):
            self.exec_calls.append(cmd)
            return _Completed(0)

        utils_pkg.exec_system = _fake_exec_system

        conn_stub = types.ModuleType("app.utils.conn")
        conn_stub.conn_db = lambda name: self.coll

        sec_stub = types.ModuleType("app.utils.security_policy")
        sec_stub.get_security_policy = lambda: ([], [])
        sec_stub.update_security_policy = lambda a, b: None

        perf_stub = types.ModuleType("app.utils.performance_config")
        perf_stub.get_performance_config = lambda: {}
        perf_stub.update_performance_config = lambda **kw: None

        services_pkg = types.ModuleType("app.services")
        services_pkg.__path__ = [str(BACKEND_ROOT / "app" / "services")]

        routes_pkg = types.ModuleType("app.routes")
        routes_pkg.__path__ = [str(BACKEND_ROOT / "app" / "routes")]
        routes_pkg.ARLResource = Resource

        self.stubs = {
            "app": app_pkg,
            "app.config": config_mod,
            "app.utils": utils_pkg,
            "app.utils.conn": conn_stub,
            "app.utils.security_policy": sec_stub,
            "app.utils.performance_config": perf_stub,
            "app.services": services_pkg,
            "app.routes": routes_pkg,
        }
        _MISSING = object()
        saved_app_modules = {
            name: sys.modules.get(name, _MISSING)
            for name in list(sys.modules.keys())
            if name == "app" or name.startswith("app.")
        }

        def _restore_app_modules():
            for name in list(sys.modules.keys()):
                if name == "app" or name.startswith("app."):
                    if name not in saved_app_modules:
                        sys.modules.pop(name, None)
            for name, orig in saved_app_modules.items():
                if orig is _MISSING:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = orig

        self.addCleanup(_restore_app_modules)
        sys.modules.update(self.stubs)

        self.ps = _load_module("app.services.proxy_service", PROXY_SERVICE_PATH)
        sys.modules["app.services.proxy_service"] = self.ps
        self.ps.clear_proxy_local_cache()

    def tearDown(self):
        self.ps.clear_proxy_local_cache()

    def test_node_crud_masking_and_password_lifecycle(self):
        """节点增删改校验、密码留空保留/清空以及删除后自动回退策略"""
        with self.assertRaises(ValueError):
            self.ps.upsert_proxy_node({"name": "bad", "protocol": "ftp", "host": "192.0.2.1", "port": 21})
        with self.assertRaises(ValueError):
            self.ps.upsert_proxy_node({"name": "bad", "protocol": "http", "host": "192.0.2.1", "port": 99999})

        _, node = self.ps.upsert_proxy_node({
            "name": "ECS 备用1",
            "protocol": "socks5h",
            "host": "192.0.2.10",
            "port": 1080,
            "username": "alice",
            "password": "s3cr3t@value",
            "region_hint": "华南",
        })
        nid = node["id"]
        self.ps.update_proxy_policies({
            "policies": {"osint": {"mode": "failover", "node_ids": [nid], "cooldown_sec": 300}},
        })

        masked = self.ps.mask_proxy_config_for_api(self.ps.load_proxy_config(use_cache=False))
        self.assertEqual(masked["nodes"][0]["password"], "")
        self.assertTrue(masked["nodes"][0]["has_password"])
        self.assertEqual(masked["nodes"][0]["display_url"], "socks5h://alice:***@192.0.2.10:1080")

        # 更新名称且 password 留空时保留原密码
        _, updated = self.ps.upsert_proxy_node({
            "name": "ECS 备用1-改名",
            "protocol": "socks5h",
            "host": "192.0.2.10",
            "port": 1080,
            "username": "alice",
            "password": "",
        }, node_id=nid)
        self.assertEqual(updated["password"], "s3cr3t@value")

        # clear_password=True 清空原密码
        _, cleared = self.ps.upsert_proxy_node({
            "name": "ECS 备用1-无密",
            "protocol": "socks5h",
            "host": "192.0.2.10",
            "port": 1080,
            "username": "alice",
            "clear_password": True,
        }, node_id=nid)
        self.assertEqual(cleared["password"], "")

        # 删除节点后，绑定它的 failover 策略自动收敛回 direct_only
        after_del, _ = self.ps.delete_proxy_node(nid)
        self.assertEqual(after_del["nodes"], [])
        self.assertEqual(after_del["policies"]["osint"]["node_ids"], [])
        self.assertEqual(after_del["policies"]["osint"]["mode"], "direct_only")

    def test_legacy_proxy_url_migration_and_sync(self):
        """历史 general_config.proxy_url 平滑升级为 proxy_config 并双向兼容同步"""
        self.coll.docs["general_config"] = {
            "_id": "general_config",
            "proxy_url": "socks5://ops:pass123@192.0.2.20:1080",
        }
        migrated = self.ps.ensure_proxy_config_schema()
        self.assertTrue(migrated)
        # 幂等：再次执行不应重复写入
        self.assertFalse(self.ps.ensure_proxy_config_schema())

        cfg = self.ps.load_proxy_config(use_cache=False)
        self.assertEqual(len(cfg["nodes"]), 1)
        self.assertEqual(cfg["nodes"][0]["id"], "legacy-default")
        self.assertEqual(cfg["nodes"][0]["protocol"], "socks5")
        self.assertEqual(cfg["policies"]["scan"]["mode"], "fixed_proxy")
        self.assertEqual(cfg["policies"]["scan"]["node_ids"], ["legacy-default"])

        # 传统入口清空 proxy_url 同步摘除节点
        cleared_cfg = self.ps.sync_legacy_proxy_url("")
        self.assertEqual(cleared_cfg["nodes"], [])
        self.assertEqual(cleared_cfg["policies"]["scan"]["mode"], "direct_only")

    def test_bypass_private_cidr_internal_hosts_and_domestic_webhooks(self):
        """内网 CIDR、内部容器服务名、国内 Webhook 及自定义规则均准确旁路"""
        _, node = self.ps.upsert_proxy_node({
            "name": "Intel Proxy",
            "protocol": "http",
            "host": "192.0.2.30",
            "port": 8080,
        })
        self.ps.update_proxy_policies({
            "policies": {
                "scan": {"mode": "fixed_proxy", "node_ids": [node["id"]]},
                "intel": {"mode": "fixed_proxy", "node_ids": [node["id"]]},
            },
            "bypass": {
                "bypass_private_cidr": True,
                "bypass_domestic_webhooks": True,
                "custom_no_proxy": "*.internal.corp, 198.51.100.0/24",
            },
        })

        for bypass_target in (
            "http://osint-service:16181/api/v1/recon/start",
            "http://arl-puppeteer:3000/render",
            "http://arl-test-target:8088/",
            "http://127.0.0.1:8000/health",
            "https://10.2.3.4:8443/admin",
            "http://192.168.10.20/",
            "https://oapi.dingtalk.com/robot/send?access_token=abc",
            "https://open.feishu.cn/open-apis/bot/v2/hook/xyz",
            "https://qyapi.weixin.qq.com/cgi-bin/webhook/send",
            "https://git.internal.corp/org/repo",
            "https://198.51.100.42/v1",
        ):
            self.assertIsNone(
                self.ps.resolve_requests_proxies(bypass_target),
                f"Expected bypass for {bypass_target}",
            )

        with patch.dict(os.environ, {"NO_PROXY": "custom-env.example"}):
            self.assertIsNone(self.ps.resolve_requests_proxies("https://custom-env.example/ping", domain="intel"))

        self.assertEqual(
            self.ps.resolve_requests_proxies("https://api.github.com/zen", domain="intel"),
            {"http": "http://192.0.2.30:8080", "https": "http://192.0.2.30:8080"},
        )
        self.assertEqual(
            self.ps.resolve_requests_proxies("https://api.telegram.org/bot123/sendMessage", domain="intel"),
            {"http": "http://192.0.2.30:8080", "https": "http://192.0.2.30:8080"},
        )

    def test_osint_failover_round_robin_and_cooldown_reset(self):
        """OSINT 主备故障转移、全阻塞降级与手动冷却重置；Scan 轮询顺序切换"""
        _, n1 = self.ps.upsert_proxy_node({"name": "ECS-A", "protocol": "http", "host": "192.0.2.41", "port": 8080})
        _, n2 = self.ps.upsert_proxy_node({"name": "ECS-B", "protocol": "http", "host": "192.0.2.42", "port": 8080})
        self.ps.update_proxy_policies({
            "policies": {
                "osint": {"mode": "failover", "node_ids": [n1["id"], n2["id"]], "cooldown_sec": 300},
                "scan": {"mode": "round_robin", "node_ids": [n1["id"], n2["id"]], "include_direct": False},
            }
        })

        # 初始状态：主直连正常，failover 首选直连 (None)
        self.assertEqual(self.ps.get_proxy_runtime_summary("osint")["state"], "direct_ok")
        self.assertEqual(
            self.ps.resolve_proxy_candidates("osint"),
            [None, "http://192.0.2.41:8080", "http://192.0.2.42:8080"],
        )

        # 主直连触发 WAF 冷却后，runtime 状态进入 backup_active，候选跳过直连
        self.ps.record_osint_exit_event(None, blocked=True, cooldown_sec=300, reason="创宇盾 403")
        rt_backup = self.ps.get_proxy_runtime_summary("osint")
        self.assertEqual(rt_backup["state"], "backup_active")
        self.assertEqual(rt_backup["active_node_name"], "ECS-A")
        self.assertGreater(rt_backup["cooldown_remaining_sec"], 0)
        self.assertEqual(
            self.ps.resolve_proxy_candidates("osint"),
            ["http://192.0.2.41:8080", "http://192.0.2.42:8080"],
        )

        # 备机一并冷却 -> degraded_blocked
        self.ps.record_osint_exit_event("http://192.0.2.41:8080", blocked=True, cooldown_sec=200, reason="403")
        self.ps.record_osint_exit_event("http://192.0.2.42:8080", blocked=True, cooldown_sec=200, reason="403")
        self.assertEqual(self.ps.get_proxy_runtime_summary("osint")["state"], "degraded_blocked")

        # 管理员手动重置冷却，并通知 osint-service
        with patch.object(self.ps.requests, "post", return_value=_FakeResponse(200)) as mock_post:
            res = self.ps.reset_osint_cooldown()
        self.assertTrue(res["osint_notified"])
        self.assertEqual(res["runtime"]["state"], "direct_ok")
        mock_post.assert_called_once()

        # round_robin 依次轮换
        c1 = self.ps.resolve_proxy_candidates("scan")[0]
        c2 = self.ps.resolve_proxy_candidates("scan")[0]
        self.assertNotEqual(c1, c2)

    def test_puppeteer_auth_compat_and_ssrf_allowlisted_probe(self):
        """Puppeteer 鉴权降级提示，以及探针 SSRF 白名单拦截与 WAF 判定"""
        _, auth_node = self.ps.upsert_proxy_node({
            "name": "Auth Socks",
            "protocol": "socks5h",
            "host": "192.0.2.50",
            "port": 1080,
            "username": "u",
            "password": "p",
        })
        self.ps.update_proxy_policies({
            "policies": {
                "scan": {
                    "mode": "fixed_proxy",
                    "node_ids": [auth_node["id"]],
                    "apply_to_puppeteer": True,
                }
            }
        })
        p_url, warn = self.ps.resolve_puppeteer_proxy()
        self.assertIsNone(p_url)
        self.assertIn("Puppeteer 已自动降级直连", warn)

        # 非白名单预设直接拒绝（防 SSRF）
        with self.assertRaises(ValueError):
            self.ps.probe_proxy_node(node_id=auth_node["id"], preset="http://169.254.169.254/latest/meta-data")

        # 工信部 521 JS 前置挑战视作出口未封禁连通正常；403/创宇盾视作 waf_blocked
        with patch.object(self.ps.requests, "get", return_value=_FakeResponse(521, "<script>document.cookie</script>")):
            r_521 = self.ps.probe_proxy_node(node_id=auth_node["id"], preset="miit", save_result=False)
        self.assertTrue(r_521["ok"])
        self.assertFalse(r_521["waf_blocked"])
        with patch.object(self.ps.requests, "get", return_value=_FakeResponse(403, "创宇盾 error_403_type")):
            r_403 = self.ps.probe_proxy_node(node_id=auth_node["id"], preset="miit", save_result=False)
        self.assertFalse(r_403["ok"])
        self.assertTrue(r_403["waf_blocked"])

        # 天眼查 419 bannedLocation 探针结果保存
        with patch.object(
            self.ps.requests,
            "get",
            return_value=_FakeResponse(419, '{"message":"bannedLocation","errorCode":"301000"}'),
        ):
            probe = self.ps.probe_proxy_node(node_id=auth_node["id"], preset="tianyancha", save_result=True)
        self.assertFalse(probe["ok"])
        self.assertTrue(probe["waf_blocked"])
        self.assertEqual(probe["status_code"], 419)
        stored = self.ps.load_proxy_config(use_cache=False)["nodes"][0]["last_probe"]
        self.assertEqual(stored["preset"], "tianyancha")

    def test_http_req_proxy_domain_and_nuclei_proxy_masking(self):
        """conn.http_req 按 call 生成独立 proxies；Nuclei 转换 socks5h->socks5 并脱敏日志"""
        _, scan_node = self.ps.upsert_proxy_node({
            "name": "Scan Socks",
            "protocol": "socks5h",
            "host": "192.0.2.60",
            "port": 1080,
            "username": "scanuser",
            "password": "TopSecretPassword",
        })
        _, intel_node = self.ps.upsert_proxy_node({
            "name": "Intel Http",
            "protocol": "http",
            "host": "192.0.2.61",
            "port": 8080,
        })
        self.ps.update_proxy_policies({
            "policies": {
                "scan": {"mode": "fixed_proxy", "node_ids": [scan_node["id"]], "apply_to_nuclei": True},
                "intel": {"mode": "fixed_proxy", "node_ids": [intel_node["id"]]},
            }
        })

        # 1. conn.http_req 校验
        conn_mod = _load_module("app.utils.conn_under_test", CONN_PATH)
        recorded_proxies = []

        class _FakeSession:
            def __init__(self):
                self.adapters = {}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def mount(self, prefix, adapter):
                self.adapters[prefix] = adapter

            def get(self, url, **kwargs):
                recorded_proxies.append(kwargs.get("proxies"))
                resp = _FakeResponse(200, "ok")
                resp._content = b"ok"
                resp.raw = None
                return resp

        with patch.object(conn_mod, "StatelessSession", _FakeSession), patch.object(conn_mod, "patch_content", lambda *a: None):
            conn_mod.http_req("https://api.github.com/zen", proxy_domain="intel")
            conn_mod.http_req("https://api.github.com/zen", proxy_domain="bypass")
        self.assertEqual(recorded_proxies[0], {"http": "http://192.0.2.61:8080", "https": "http://192.0.2.61:8080"})
        self.assertIsNone(recorded_proxies[1])

        # 2. NucleiScan 注入 -proxy（socks5h -> socks5）：含认证代理通过 0o600 临时文件传递，CLI 与日志均不暴露明文密码
        nuclei_mod = _load_module("app.services.nuclei_scan_under_test", NUCLEI_SCAN_PATH)
        scanner = nuclei_mod.NucleiScan(targets=["https://example.com"])
        scanner.nuclei_json_flag = "-jsonl"
        scanner.exec_nuclei()
        cmd_str = " ".join(self.exec_calls[-1])
        self.assertIn("-proxy", cmd_str)
        self.assertNotIn("TopSecretPassword", cmd_str)
        proxy_files = [p for p, _ in scanner._extra_tmp_files if "nuclei_proxy_" in os.path.basename(p)]
        self.assertEqual(len(proxy_files), 1)
        with open(proxy_files[0], "r", encoding="utf-8") as pf:
            self.assertEqual(pf.read().strip(), "socks5://scanuser:TopSecretPassword@192.0.2.60:1080")
        self.assertEqual(os.stat(proxy_files[0]).st_mode & 0o777, 0o600)
        self.assertTrue(any("***@192.0.2.60:1080" in line for line in self.log_records))
        self.assertFalse(any("TopSecretPassword" in line for line in self.log_records))
        scanner._delete_file()
        self.assertFalse(os.path.exists(proxy_files[0]))

        # 全部为内网 CIDR 目标时自动跳过 -proxy
        self.exec_calls.clear()
        private_scanner = nuclei_mod.NucleiScan(targets=["http://192.168.1.10:8080"])
        private_scanner.nuclei_json_flag = "-jsonl"
        private_scanner.exec_nuclei()
        self.assertNotIn("-proxy", " ".join(self.exec_calls[-1]))

    def test_tyc_client_in_flight_failover_on_419(self):
        """同步 TycClient 遇 419 bannedLocation 时瞬时切备成功并冷却主直连"""
        _, backup = self.ps.upsert_proxy_node({
            "name": "CN-ECS",
            "protocol": "http",
            "host": "192.0.2.70",
            "port": 8080,
        })
        self.ps.update_proxy_policies({
            "policies": {"osint": {"mode": "failover", "node_ids": [backup["id"]], "cooldown_sec": 300}}
        })

        tyc_mod = _load_module("app.services.tyc_under_test", TYC_CLIENT_PATH)
        client = tyc_mod.TycClient()
        seen = []

        def _fake_get(url, **kwargs):
            px = kwargs.get("proxies")
            seen.append(px)
            if not px:
                return _FakeResponse(419, '{"message":"bannedLocation","errorCode":"301000"}')
            return _FakeResponse(200, '{"state":"ok"}', {"state": "ok", "data": {"companyName": "测试集团"}})

        with patch.object(tyc_mod.requests, "get", side_effect=_fake_get):
            data = client._request("GET", "/cloud-company-background/test")

        self.assertEqual(data, {"companyName": "测试集团"})
        self.assertEqual(seen, [None, {"http": "http://192.0.2.70:8080", "https": "http://192.0.2.70:8080"}])
        self.assertEqual(self.ps.get_proxy_runtime_summary("osint")["state"], "backup_active")

    def test_flask_system_config_proxy_routes_end_to_end(self):
        """挂载真实 Flask-RESTx system_config 路由测试全套 /proxy CRUD 与探测接口"""
        sc_mod = _load_module("app.routes.system_config_under_test", SYSTEM_CONFIG_ROUTE_PATH)
        flask_app = Flask(__name__)
        api = Api(flask_app)
        api.add_namespace(sc_mod.ns, path="/api/system_config")
        client = flask_app.test_client()

        # GET /proxy
        r0 = client.get("/api/system_config/proxy")
        self.assertEqual(r0.status_code, 200)
        d0 = r0.get_json()
        self.assertEqual(d0["code"], 200)
        self.assertIn("capabilities", d0["data"])

        # POST /proxy/nodes
        r1 = client.post("/api/system_config/proxy/nodes", json={
            "name": "RouteNode",
            "protocol": "socks5h",
            "host": "192.0.2.80",
            "port": 1080,
            "username": "u",
            "password": "secret",
        })
        self.assertEqual(r1.status_code, 200)
        nid = r1.get_json()["data"]["node"]["id"]
        self.assertEqual(r1.get_json()["data"]["node"]["password"], "")
        self.assertTrue(r1.get_json()["data"]["node"]["has_password"])

        # PUT /proxy/policies（invalid mode -> 400; valid failover -> 200）
        r_bad = client.put("/api/system_config/proxy/policies", json={
            "policies": {"osint": {"mode": "fixed_proxy", "node_ids": []}}
        })
        self.assertEqual(r_bad.status_code, 400)

        r2 = client.put("/api/system_config/proxy/policies", json={
            "policies": {"osint": {"mode": "failover", "node_ids": [nid], "cooldown_sec": 300}},
            "bypass": {"bypass_private_cidr": True, "bypass_domestic_webhooks": True, "custom_no_proxy": ["*.corp"]},
        })
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(r2.get_json()["data"]["config"]["policies"]["osint"]["mode"], "failover")

        # POST /proxy/probe (mock HTTP check)
        with patch.object(self.ps.requests, "get", return_value=_FakeResponse(200, "198.51.100.88")):
            r3 = client.post("/api/system_config/proxy/probe", json={"node_id": nid, "preset": "egress_ip"})
        self.assertEqual(r3.status_code, 200)
        self.assertTrue(r3.get_json()["data"]["result"]["ok"])
        self.assertEqual(r3.get_json()["data"]["result"]["egress_ip"], "198.51.100.88")

        # POST /proxy/cooldown/reset
        with patch.object(self.ps.requests, "post", return_value=_FakeResponse(200)):
            r4 = client.post("/api/system_config/proxy/cooldown/reset")
        self.assertEqual(r4.status_code, 200)
        self.assertTrue(r4.get_json()["data"]["osint_notified"])

        # DELETE /proxy/nodes/<id>
        r5 = client.delete(f"/api/system_config/proxy/nodes/{nid}")
        self.assertEqual(r5.status_code, 200)
        self.assertEqual(r5.get_json()["data"]["config"]["nodes"], [])
        self.assertEqual(r5.get_json()["data"]["config"]["policies"]["osint"]["mode"], "direct_only")

    def test_favicon_http_selects_socks_and_http_proxy_managers(self):
        """favicon_http 根据 proxy_url 协议区分 SOCKSProxyManager 与 urllib3.ProxyManager"""
        favicon_mod = _load_module("app.utils.favicon_http_under_test", FAVICON_HTTP_PATH)
        seen_calls = []

        class _FakeUrllibResp:
            def __init__(self, body=b"ICO"):
                self.status = 200
                self.headers = {"Content-Type": "image/x-icon"}
                self._body = body

            def read(self, n):
                return self._body[:n]

            def close(self):
                pass

        class _FakeManager:
            def __init__(self, kind, proxy_url, **kwargs):
                seen_calls.append((kind, proxy_url))

            def request(self, method, url, **kwargs):
                return _FakeUrllibResp()

            def clear(self):
                pass

        fake_socks_mod = types.ModuleType("urllib3.contrib.socks")
        fake_socks_mod.SOCKSProxyManager = lambda proxy_url, **kw: _FakeManager("socks", proxy_url, **kw)

        fake_addr = [(2, 1, 6, "", ("198.51.100.10", 80))]
        with (
            patch.object(favicon_mod.socket, "getaddrinfo", return_value=fake_addr),
            patch.object(favicon_mod.urllib3, "ProxyManager", side_effect=lambda u, **kw: _FakeManager("http", u, **kw)),
            patch.dict(sys.modules, {"urllib3.contrib.socks": fake_socks_mod}),
        ):
            r_socks = favicon_mod.fetch_favicon_response(
                "http://example.com/favicon.ico",
                allowed_ip=lambda ip: True,
                forbidden_domain=lambda h: False,
                proxy_url="socks5h://192.0.2.11:1080",
            )
            r_http = favicon_mod.fetch_favicon_response(
                "http://example.com/favicon.ico",
                allowed_ip=lambda ip: True,
                forbidden_domain=lambda h: False,
                proxy_url="http://192.0.2.10:8080",
            )

        self.assertEqual(r_socks.content, b"ICO")
        self.assertEqual(r_http.content, b"ICO")
        self.assertEqual(
            seen_calls,
            [("socks", "socks5h://192.0.2.11:1080"), ("http", "http://192.0.2.10:8080")],
        )


if __name__ == "__main__":
    unittest.main()
