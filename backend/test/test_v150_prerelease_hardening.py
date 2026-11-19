# -*- coding: utf-8 -*-
"""v1.5.0 发版前安全加固与状态机回归测试套件（覆盖 P0-1~P0-4 与 P1 关键修复）。"""

import asyncio
import importlib.util
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from bson import ObjectId

from security_support import ROOT, app_env, load_source


BACKEND_ROOT = ROOT
OSINT_ROOT = BACKEND_ROOT / "osint_service"


def _load_module(mod_name, path):
    spec = importlib.util.spec_from_file_location(mod_name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _prepare_app_env(env):
    env.cfg.Config.TMP_PATH = str(env.tmp)
    env.cfg.Config.basedir = str(env.tmp)
    env.utils.random_choices = lambda length=8: f"fix{length}"
    env.utils.build_ret = lambda error, data: (
        {**({"message": error, "code": 999} if isinstance(error, str) else error), "data": data}
    )
    modules_mod = types.ModuleType("app.modules")
    modules_mod.ErrorMsg = types.SimpleNamespace(
        Success={"code": 200, "message": "success"},
        Error={"code": 500, "message": "系统异常"},
    )
    modules_mod.TaskTag = types.SimpleNamespace(TASK="task", MONITOR="monitor")
    env.monkeypatch.setitem(sys.modules, "app.modules", modules_mod)


def test_p0_1_nuclei_severity_cli_injection_blocked(app_env):
    """P0-1: 校验 normalize_nuclei_config 与 NucleiScan 均拦截恶意 severity CLI 参数注入。"""
    _prepare_app_env(app_env)
    pol_helper = load_source(app_env.monkeypatch, "app.helpers.policy", "app/helpers/policy.py")

    norm, err = pol_helper.normalize_nuclei_config(
        {"include_community": True, "severity": ["low -code", "high"]},
        nuclei_scan_enabled=True,
        strict_severity=True,
    )
    assert norm is None and err is not None

    norm_ok, err_ok = pol_helper.normalize_nuclei_config(
        {"include_community": True, "severity": ["Critical", "HIGH"]},
        nuclei_scan_enabled=True,
        strict_severity=True,
    )
    assert err_ok is None
    assert norm_ok["severity"] == ["critical", "high"]

    # 直接绕过路由传入 NucleiScan 时，白名单仍彻底剥离注入串
    proxy_mod = types.ModuleType("app.services.proxy_service")
    proxy_mod.load_proxy_config = lambda: {"policies": {"scan": {"apply_to_nuclei": False}}, "bypass": {}}
    proxy_mod.mask_proxy_url_secret = lambda u: u
    proxy_mod.resolve_proxy_url = lambda domain="scan", target_url=None: ""
    proxy_mod.should_bypass_url = lambda url, bypass=None, domain=None: False
    app_env.monkeypatch.setitem(sys.modules, "app.services.proxy_service", proxy_mod)

    svc = load_source(app_env.monkeypatch, "app.services.nuclei_template_service", "app/services/nuclei_template_service.py")
    app_env.monkeypatch.setattr(svc, "get_community_templates_dir", lambda: "")
    scan_mod = load_source(app_env.monkeypatch, "app.services.nuclei_scan", "app/services/nuclei_scan.py")

    seen_cmds = []
    app_env.utils.exec_system = lambda cmd, timeout=None: (seen_cmds.append(list(cmd)), types.SimpleNamespace(returncode=0))[1]
    scanner = scan_mod.NucleiScan(
        targets=["https://example.com"],
        options={"nuclei_config": {"include_community": True, "severity": ["low -code -file", "high"]}},
    )
    scanner.nuclei_bin_path = "/usr/bin/nuclei"
    scanner.nuclei_json_flag = "-jsonl"
    try:
        scanner.exec_nuclei()
    finally:
        scanner._delete_file()

    assert len(seen_cmds) == 1
    cmd_str = " ".join(seen_cmds[0])
    assert "-code" not in cmd_str
    assert "-file" not in cmd_str
    assert "-severity high" in cmd_str


def test_p1_nuclei_multiprotocol_bypass_and_dryrun_ssrf_blocked(app_env):
    """P1: 多协议模板（http + code/workflows）不得伪装绕过，在线调试阻断回环/云元数据/内部服务但放行常规私网。"""
    _prepare_app_env(app_env)
    svc = load_source(app_env.monkeypatch, "app.services.nuclei_template_service", "app/services/nuclei_template_service.py")

    hybrid_yaml = (
        "id: hybrid-code-bypass\n"
        "info:\n"
        "  name: Hybrid Bypass\n"
        "  author: sec\n"
        "  severity: high\n"
        "http:\n"
        "  - method: GET\n"
        "    path: ['{{BaseURL}}/']\n"
        "code:\n"
        "  - engine:\n"
        "      - sh\n"
        "    source: id\n"
    )
    ok, meta = svc.parse_and_validate_nuclei_yaml(hybrid_yaml, run_nuclei_validate=False)
    assert ok is True
    assert meta["protocol"] == "code"
    assert "code" in meta["protocols"]
    assert svc.classify_asm_protocol(meta) == "unsupported"
    assert svc.is_asm_supported_protocol(meta) is False

    # 在线调试目标安全校验
    for blocked in ("127.0.0.1:8080", "http://localhost:5000", "169.254.169.254", "http://mongodb:27017", "http://osint-service:16181"):
        safe_ok, err_msg = svc.normalize_dry_run_target(blocked, "http")
        assert safe_ok is False, f"Expected {blocked} to be blocked"
        assert err_msg

    # 常规 RFC1918 私网在未命中 BLACK_IPS 时允许调试（契合内网部署需求）
    ok_priv, norm_priv = svc.normalize_dry_run_target("10.10.20.30:8080", "http")
    assert ok_priv is True
    assert norm_priv == "http://10.10.20.30:8080"


def test_p1_nuclei_mixed_target_proxy_split_and_masked_error(app_env):
    """P1: 混合私网与公网目标拆分走直连/代理，且失败异常不泄漏明文代理密码。"""
    _prepare_app_env(app_env)
    ps = load_source(app_env.monkeypatch, "app.services.proxy_service", "app/services/proxy_service.py")
    assert ps.should_bypass_url("192.168.1.10:6379", {"bypass_private_cidr": True}, domain="scan") is True
    assert ps.should_bypass_url("internal.local", {"bypass_private_cidr": True}, domain="scan") is True
    assert ps.should_bypass_url("93.184.216.34:6379", {"bypass_private_cidr": True}, domain="scan") is False
    assert "SecretPass" not in ps.mask_proxy_url_secret("user:SecretPass@192.0.2.1:1080")

    _, node = ps.upsert_proxy_node({
        "name": "ScanProxy",
        "protocol": "socks5h",
        "host": "192.0.2.88",
        "port": 1080,
        "username": "u1",
        "password": "TopSecretPassword",
    })
    ps.update_proxy_policies({"policies": {"scan": {"mode": "fixed_proxy", "node_ids": [node["id"]], "apply_to_nuclei": True}}})

    svc = load_source(app_env.monkeypatch, "app.services.nuclei_template_service", "app/services/nuclei_template_service.py")
    app_env.monkeypatch.setattr(svc, "get_community_templates_dir", lambda: "")
    scan_mod = load_source(app_env.monkeypatch, "app.services.nuclei_scan", "app/services/nuclei_scan.py")

    recorded = []

    def fake_exec(cmd, timeout=None):
        recorded.append(" ".join(cmd))
        return types.SimpleNamespace(returncode=0)

    app_env.utils.exec_system = fake_exec
    scanner = scan_mod.NucleiScan(targets=["https://example.com", "http://192.168.1.20:8080"])
    scanner.nuclei_bin_path = "/usr/bin/nuclei"
    scanner.nuclei_json_flag = "-jsonl"
    try:
        scanner.exec_nuclei()
    finally:
        scanner._delete_file()

    assert len(recorded) == 2
    assert sum("-proxy" in c for c in recorded) == 1
    assert sum("-proxy" not in c for c in recorded) == 1
    assert all("TopSecretPassword" not in c for c in recorded)

    # 失败时抛出的 CalledProcessError 也不得包含明文密码
    app_env.utils.exec_system = lambda cmd, timeout=None: types.SimpleNamespace(returncode=2)
    fail_scanner = scan_mod.NucleiScan(targets=["https://example.com"])
    fail_scanner.nuclei_bin_path = "/usr/bin/nuclei"
    fail_scanner.nuclei_json_flag = "-jsonl"
    try:
        with pytest.raises(Exception) as exc_info:
            fail_scanner.exec_nuclei()
        assert "TopSecretPassword" not in str(exc_info.value)
    finally:
        fail_scanner._delete_file()


def test_branch1_tiered_fixed_proxy_and_favicon_socks_unquote(app_env):
    """分支 1: OSINT fixed_proxy 无启用节点时严格 Fail-Closed，scan/intel 记告警降级直连；favicon SOCKS 凭据正确 unquote。"""
    _prepare_app_env(app_env)
    ps = load_source(app_env.monkeypatch, "app.services.proxy_service", "app/services/proxy_service.py")
    _, node = ps.upsert_proxy_node({
        "name": "DisabledNode",
        "protocol": "http",
        "host": "192.0.2.99",
        "port": 8080,
        "enabled": True,
    })
    ps.update_proxy_policies({
        "policies": {
            "osint": {"mode": "fixed_proxy", "node_ids": [node["id"]]},
            "scan": {"mode": "fixed_proxy", "node_ids": [node["id"]]},
        }
    })
    ps.upsert_proxy_node({
        "name": "DisabledNode",
        "protocol": "http",
        "host": "192.0.2.99",
        "port": 8080,
        "enabled": False,
    }, node_id=node["id"])
    assert ps.resolve_proxy_candidates(domain="osint", target_url="https://capi.tianyancha.com/") == []
    assert ps.resolve_proxy_candidates(domain="scan", target_url="https://example.com/") == [None]

    fav_mod = _load_module("app.utils.favicon_http_test", BACKEND_ROOT / "app" / "utils" / "favicon_http.py")
    captured_socks = {}

    class _FakeResp:
        status = 200
        headers = {}
        def read(self, n):
            return b"ok"
        def close(self):
            pass

    class _FakeSocksMgr:
        def __init__(self, proxy_url, username=None, password=None, **kw):
            captured_socks["proxy_url"] = proxy_url
            captured_socks["username"] = username
            captured_socks["password"] = password
        def request(self, *args, **kwargs):
            return _FakeResp()
        def clear(self):
            pass

    fake_socks_mod = types.ModuleType("urllib3.contrib.socks")
    fake_socks_mod.SOCKSProxyManager = _FakeSocksMgr
    with patch.dict(sys.modules, {"urllib3.contrib.socks": fake_socks_mod}), \
         patch.object(fav_mod.socket, "getaddrinfo", return_value=[(2, 1, 6, "", ("93.184.216.34", 80))]):
        fav_mod.fetch_favicon_response(
            "http://example.com/favicon.ico",
            allowed_ip=lambda ip: True,
            forbidden_domain=lambda h: False,
            proxy_url="socks5h://user%40corp:p%3As%40word@192.0.2.10:1080",
        )
    assert captured_socks["proxy_url"] == "socks5h://192.0.2.10:1080"
    assert captured_socks["username"] == "user@corp"
    assert captured_socks["password"] == "p:s@word"


def test_p0_2_p0_3_p0_4_osint_sanitization_isolation_and_backfill_reconcile():
    """P0-2/P0-3/P0-4: 日志脱敏、TYC/MIIT 冷却隔离、原子点路径持久化、崩溃后释放 detail_backfill_running 锁。"""
    if str(OSINT_ROOT) not in sys.path:
        sys.path.insert(0, str(OSINT_ROOT))
    import proxy_router as pr
    import clients.job_runner as jr
    import routes.recon_routes as rr

    assert pr.mask_proxy_url_secret("http://u:Secret123@192.0.2.5:8080") == "http://u:******@192.0.2.5:8080"
    assert "Secret123" not in pr.mask_proxy_url_secret("u:Secret123@192.0.2.5:8080")

    # fixed_proxy 无节点时在 OSINT 严格 Fail-Closed
    r_fixed = pr.OsintProxyRouter(bundle={"policy": {"mode": "fixed_proxy", "node_ids": []}, "nodes": []})
    assert r_fixed._all_allowed_exits() == []
    assert r_fixed.get_candidates() == []

    # TYC vs MIIT service_scope 隔离 + 原子点路径持久化
    updates = []

    class _FakeAsyncCol:
        async def update_one(self, q, u, upsert=False):
            updates.append((q, u, upsert))

    fake_db = {"system_config": _FakeAsyncCol()}
    bundle = {
        "policy": {"mode": "failover", "node_ids": ["n1"], "cooldown_sec": 300},
        "nodes": [{"id": "n1", "name": "Backup1", "protocol": "http", "proxy_url": "http://192.0.2.11:8080", "host": "192.0.2.11"}],
    }
    r_tyc = pr.OsintProxyRouter(bundle=bundle, db=fake_db, service_scope="tyc")
    r_miit = pr.OsintProxyRouter(bundle=bundle, db=fake_db, service_scope="miit")

    r_tyc.mark_exit_blocked("__direct__", reason="419 bannedLocation", cooldown_sec=300)
    assert r_tyc.is_exit_blocked("__direct__") is True
    assert r_miit.is_exit_blocked("__direct__") is False

    r_miit._sync_blocked_from_doc({"blocked_exits": r_tyc.blocked_exits})
    assert r_miit.is_exit_blocked("__direct__") is False

    asyncio.run(r_tyc.persist_runtime_status())
    assert updates
    set_doc = updates[-1][1]["$set"]
    assert "blocked_exits.__direct__" in set_doc
    assert "blocked_exits" not in set_doc

    # 日志脱敏
    sanitized = jr._sanitize_options_for_log({
        "task_id": "abc",
        "tyc_id": "1234567890",
        "tyc_token": "SUPER_SECRET_JWT_TOKEN",
        "proxy_url": "http://proxyuser:ProxyPass99@192.0.2.5:8080",
        "proxy_bundle": {
            "policy": {"mode": "failover"},
            "nodes": [{"id": "n1", "proxy_url": "socks5h://u:HiddenPwd@192.0.2.6:1080"}],
        },
    })
    serialized = str(sanitized)
    assert "SUPER_SECRET_JWT_TOKEN" not in serialized
    assert "ProxyPass99" not in serialized
    assert "HiddenPwd" not in serialized
    assert sanitized["proxy_bundle"] == {"mode": "failover", "node_count": 1}

    # P0-3: reconcile_orphan_tasks 清理 detail_backfill_running 并恢复原终态
    bf_id = ObjectId()
    docs = [
        {"_id": bf_id, "status": "running", "detail_backfill_running": True, "detail_backfill_prev_status": "done"},
    ]

    class _FakeCursor:
        def __init__(self, items):
            self._items = items
        def sort(self, *a, **kw):
            return self
        async def to_list(self, length=None):
            return list(self._items)

    class _FakeTaskCol:
        def find(self, query, *a, **kw):
            out = []
            for d in docs:
                if all(d.get(k) == v for k, v in query.items()):
                    out.append(d)
            return _FakeCursor(out)
        async def update_one(self, q, u, upsert=False):
            for d in docs:
                if d["_id"] == q["_id"]:
                    for k, v in (u.get("$set") or {}).items():
                        d[k] = v
                    for k in (u.get("$unset") or {}).keys():
                        d.pop(k, None)

    mock_jr = MagicMock()
    mock_jr.db = {"icp_task": _FakeTaskCol(), "system_config": _FakeTaskCol()}
    mock_jr.curr_date = lambda: "2026-11-19 15:00:00"
    mock_jr._sync_scope_after_task_completion = None

    async def _no_sleep(_):
        return None

    with patch.dict(sys.modules, {"clients.job_runner": mock_jr}), \
         patch.object(rr.asyncio, "sleep", side_effect=_no_sleep), \
         patch.object(rr, "_schedule_syslog", lambda *a, **kw: None):
        asyncio.run(rr.reconcile_orphan_tasks({"task_manager": MagicMock()}))

    assert docs[0]["status"] == "done"
    assert "detail_backfill_running" not in docs[0]
    assert "detail_backfill_prev_status" not in docs[0]


def test_p1_github_threat_nosql_injection_and_interval_validation(app_env):
    """P1: GitHub 威胁雷达删除接口阻断 MongoDB 操作符注入，配置接口校验 interval 合法性。"""
    _prepare_app_env(app_env)
    from flask import Flask
    threat_mod = load_source(app_env.monkeypatch, "app.routes.github_threat", "app/routes/github_threat.py")
    app = Flask(__name__)
    app.register_blueprint(threat_mod.github_threat_bp, url_prefix="/api/github_threat")
    client = app.test_client()
    headers = {"Token": "fixture-api-key"}

    app_env.db.github_tools_target.insert_one({"repo_url": "owner/tool1"})
    app_env.db.github_hackers_target.insert_one({"github_id": "researcher1"})
    app_env.db.github_cve_history.insert_one({"cve_name": "CVE-2026-0001"})

    r1 = client.post("/api/github_threat/tools_target/delete", headers=headers, json={"repo_url": {"$ne": ""}})
    assert r1.json["code"] != 200
    assert app_env.db.github_tools_target.count_documents({}) == 1

    r2 = client.post("/api/github_threat/hackers_target/delete", headers=headers, json={"github_id": {"$ne": ""}})
    assert r2.json["code"] != 200
    assert app_env.db.github_hackers_target.count_documents({}) == 1

    r3 = client.post("/api/github_threat/cve_history/delete", headers=headers, json={"cve_name": {"$ne": ""}})
    assert r3.json["code"] != 200
    assert app_env.db.github_cve_history.count_documents({}) == 1

    for bad_interval in (0, -5, "abc", True, 9999):
        rc = client.post("/api/github_threat/cve_config", headers=headers, json={"enabled": True, "interval": bad_interval})
        assert rc.json["code"] != 200


def test_p1_mcp_bounds_ip_and_readonly_fallback(app_env):
    """P1: MCP SSE 采信 X-Real-IP、不让 Basic 遮蔽 Token，Stdio 拉取失败仅降级只读工具。"""
    _prepare_app_env(app_env)
    mcp_sec = load_source(app_env.monkeypatch, "app.mcp_security", "app/mcp_security.py")
    _ = mcp_sec
    mcp_asset = load_source(app_env.monkeypatch, "app.mcp_asset", "app/mcp_asset.py")
    _ = mcp_asset
    mcp_srv = load_source(app_env.monkeypatch, "app.mcp_server", "app/mcp_server.py")
    inst = mcp_srv.MCPServer()
    tok = inst._extract_token_from_request(
        headers={"authorization": "Basic YWRtaW46cGFzcw==", "token": "arl_mcp_real_token"},
        query_params={},
    )
    assert tok == "arl_mcp_real_token"

    bridge = _load_module("mcp_bridge_hardening_test", BACKEND_ROOT.parent / "mcp-server" / "server.py")
    with patch.object(bridge, "_get_auth", return_value=("https://arl.example", "readonly-token")), \
         patch.object(bridge, "_request_api", return_value=(503, {"message": "unavailable"})):
        tools = bridge._fetch_remote_tools()
    tool_names = [t["name"] for t in tools]
    assert "create_scan_task" not in tool_names
    assert "stop_scan_task" not in tool_names
    assert tool_names == ["get_asset_profile", "get_enterprise_profile"]
