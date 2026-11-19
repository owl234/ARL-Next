"""Nuclei 自建模板参与 ASM 任务全链路回归测试（含真实 Nuclei v3 Loopback HTTP/TCP 端到端验证）。"""

import ast
import copy
import io
import json
import shlex
import shutil
import socket
import subprocess
import sys
import threading
import types
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import Mock

from bson import ObjectId
import pytest

from security_support import ROOT, app_env, load_source, make_client


def _load_nuclei_stack(env):
    env.cfg.Config.TMP_PATH = str(env.tmp)
    counter = iter(range(1000))
    env.utils.random_choices = lambda length=8: f"fix{next(counter):04d}"
    env.utils.build_ret = lambda error, data: (
        {**({"message": error, "code": 999} if isinstance(error, str) else error), "data": data}
    )
    env.utils.exec_system = Mock()

    modules_mod = types.ModuleType("app.modules")
    modules_mod.ErrorMsg = types.SimpleNamespace(
        Success={"code": 200, "message": "success"},
        Error={"code": 500, "message": "系统异常"},
        NotFoundScopeID={"code": 801, "message": "资产组不存在"},
        PolicyIDNotFound={"code": 901, "message": "策略不存在"},
        TaskTargetIsEmpty={"code": 201, "message": "任务目标为空"},
        ResultSetIDNotFound={"code": 902, "message": "结果集不存在"},
        ResultSetIsEmpty={"code": 903, "message": "结果集为空"},
    )
    modules_mod.TaskTag = types.SimpleNamespace(TASK="task", RISK_CRUISING="risk_cruising", MONITOR="monitor")
    env.monkeypatch.setitem(sys.modules, "app.modules", modules_mod)

    proxy_mod = types.ModuleType("app.services.proxy_service")
    proxy_mod.load_proxy_config = lambda: {"policies": {"scan": {"apply_to_nuclei": True}}, "bypass": []}
    proxy_mod.mask_proxy_url_secret = lambda url: url
    proxy_mod.resolve_proxy_url = lambda domain="scan", target_url=None: ""
    proxy_mod.should_bypass_url = lambda url, bypass=None, domain=None: False
    env.monkeypatch.setitem(sys.modules, "app.services.proxy_service", proxy_mod)

    svc = load_source(env.monkeypatch, "app.services.nuclei_template_service", "app/services/nuclei_template_service.py")
    scan_mod = load_source(env.monkeypatch, "app.services.nuclei_scan", "app/services/nuclei_scan.py")
    route_mod = load_source(env.monkeypatch, "app.routes.nuclei", "app/routes/nuclei.py")

    env.db.user.insert_one({"username": "tester", "password": env.credentials.hash_password("pw")})
    client = make_client(env, route_mod.ns)
    headers = {"Token": "fixture-api-key"}
    return svc, scan_mod, route_mod, client, headers


def test_custom_channel_bypasses_severity_and_global_blacklist_and_supports_custom_only(app_env, monkeypatch):
    svc, scan_mod, _, _, _ = _load_nuclei_stack(app_env)

    # 社区目录存在 1 条演示模板
    comm_dir = app_env.tmp / "comm_dir"
    comm_dir.mkdir()
    (comm_dir / "comm.yaml").write_text("id: comm-cve\n", encoding="utf-8")
    monkeypatch.setattr(svc, "get_community_templates_dir", lambda: str(comm_dir))

    # 插入一条 info 级自建模板，且其 template_id 同时存在于全局误报黑名单
    app_env.db.nuclei_template.insert_one({
        "template_id": "custom-info-panel",
        "name": "Custom Info Panel",
        "protocol": "http",
        "severity": "info",
        "tags": ["custom", "panel"],
        "content": "id: custom-info-panel\ninfo:\n  name: Custom Info Panel\n  author: a\n  severity: info\nhttp:\n  - method: GET\n    path: ['{{BaseURL}}/']\n",
        "enable": True,
    })
    app_env.db.nuclei_blacklist.insert_one({"template_id": "custom-info-panel", "reason": "community fp"})

    commands = []

    def fake_exec(cmd_list, timeout=None):
        args = shlex.split(" ".join(cmd_list))
        commands.append(args)
        out_path = args[args.index("-o") + 1]
        if "-tags" in args:
            Path(out_path).write_text(json.dumps({
                "template-id": "comm-cve",
                "url": "https://example.com",
                "matched-at": "https://example.com/cve",
                "info": {"name": "Comm CVE", "severity": "high"},
            }) + "\n", encoding="utf-8")
        else:
            Path(out_path).write_text(json.dumps({
                "template-id": "custom-info-panel",
                "url": "https://example.com",
                "matched-at": "https://example.com/admin",
                "info": {"name": "Custom Info Panel", "severity": "info"},
            }) + "\n", encoding="utf-8")
        return types.SimpleNamespace(returncode=0)

    app_env.utils.exec_system = fake_exec

    # 1. 双通道：社区受 severity + -eid 约束；自建无 -severity / -eid / -tags，且结果准确标注 template_source
    scan = scan_mod.NucleiScan(
        targets=["https://example.com"],
        options={"nuclei_config": {"include_community": True, "severity": ["critical", "high"], "custom_template_mode": "all_enabled"}},
    )
    scan.nuclei_bin_path = "/usr/bin/nuclei"
    scan.nuclei_json_flag = "-jsonl"
    try:
        scan.exec_nuclei()
        results = scan.dump_result()
    finally:
        scan._delete_file()

    assert len(commands) == 2
    comm_cmd, custom_cmd = commands
    assert "-tags" in comm_cmd and "-severity" in comm_cmd and "-eid" in comm_cmd
    assert "-tags" not in custom_cmd and "-severity" not in custom_cmd and "-eid" not in custom_cmd
    by_id = {r["template_id"]: r for r in results}
    assert by_id["comm-cve"]["template_source"] == "community"
    assert by_id["custom-info-panel"]["template_source"] == "custom"

    # 2. 仅自建模式 (include_community=False)：不触发社区通道
    commands.clear()
    scan_custom_only = scan_mod.NucleiScan(
        targets=["https://example.com"],
        options={"nuclei_config": {"include_community": False, "custom_template_mode": "all_enabled"}},
    )
    scan_custom_only.nuclei_bin_path = "/usr/bin/nuclei"
    scan_custom_only.nuclei_json_flag = "-jsonl"
    try:
        scan_custom_only.exec_nuclei()
        only_results = scan_custom_only.dump_result()
    finally:
        scan_custom_only._delete_file()

    assert len(commands) == 1
    assert "-tags" not in commands[0] and "-eid" not in commands[0]
    assert len(only_results) == 1 and only_results[0]["template_source"] == "custom"

    # 3. 仅自建模式但无任何已启用模板 -> 安全跳过，0 调用不抛异常
    commands.clear()
    scan_empty = scan_mod.NucleiScan(
        targets=["https://example.com"],
        options={"nuclei_config": {"include_community": False, "custom_template_mode": "none"}},
    )
    scan_empty.nuclei_bin_path = "/usr/bin/nuclei"
    scan_empty.nuclei_json_flag = "-jsonl"
    try:
        scan_empty.exec_nuclei()
        assert scan_empty.dump_result() == []
    finally:
        scan_empty._delete_file()
    assert commands == []


def test_dual_channel_fault_isolation_preserves_succeeded_channel_findings(app_env, monkeypatch):
    svc, scan_mod, _, _, _ = _load_nuclei_stack(app_env)

    comm_dir = app_env.tmp / "comm_iso"
    comm_dir.mkdir()
    (comm_dir / "comm.yaml").write_text("id: comm-cve\n", encoding="utf-8")
    monkeypatch.setattr(svc, "get_community_templates_dir", lambda: str(comm_dir))

    app_env.db.nuclei_template.insert_one({
        "template_id": "custom-flaky",
        "protocol": "http",
        "content": "id: custom-flaky\ninfo:\n  name: Flaky\n  author: a\n  severity: high\nhttp:\n  - method: GET\n    path: ['{{BaseURL}}/']\n",
        "enable": True,
    })

    # 场景 A：社区通道成功产出结果，自建通道退出码 1 -> 必须保留社区结果不抛错
    def comm_ok_custom_fail(cmd_list, timeout=None):
        args = shlex.split(" ".join(cmd_list))
        out_path = args[args.index("-o") + 1]
        if "-tags" in args:
            Path(out_path).write_text(json.dumps({
                "template-id": "comm-cve-kept",
                "url": "https://example.com",
                "matched-at": "https://example.com/kept",
                "info": {"name": "Kept Finding", "severity": "critical"},
            }) + "\n", encoding="utf-8")
            return types.SimpleNamespace(returncode=0)
        return types.SimpleNamespace(returncode=1)

    app_env.utils.exec_system = comm_ok_custom_fail
    scan = scan_mod.NucleiScan(targets=["https://example.com"])
    scan.nuclei_bin_path = "/usr/bin/nuclei"
    scan.nuclei_json_flag = "-jsonl"
    try:
        scan.exec_nuclei()
        res = scan.dump_result()
    finally:
        scan._delete_file()
    assert len(res) == 1
    assert res[0]["template_id"] == "comm-cve-kept"
    assert res[0]["template_source"] == "community"

    # 场景 B：全部通道均失败 -> 仍向上抛出 CalledProcessError
    app_env.utils.exec_system = lambda cmd_list, timeout=None: types.SimpleNamespace(returncode=1)
    scan_all_fail = scan_mod.NucleiScan(targets=["https://example.com"])
    scan_all_fail.nuclei_bin_path = "/usr/bin/nuclei"
    scan_all_fail.nuclei_json_flag = "-jsonl"
    with pytest.raises(subprocess.CalledProcessError):
        try:
            scan_all_fail.exec_nuclei()
        finally:
            scan_all_fail._delete_file()


def test_protocol_routing_buckets_unsupported_skip_and_tags_case_normalization(app_env, monkeypatch):
    svc, scan_mod, _, _, _ = _load_nuclei_stack(app_env)
    monkeypatch.setattr(svc, "get_community_templates_dir", lambda: "")

    app_env.db.nuclei_template.insert_many([
        {
            "template_id": "tpl-http",
            "protocol": "http",
            "tags": ["rce"],
            "content": "id: tpl-http\ninfo:\n  name: H\n  author: a\n  severity: high\nhttp:\n  - method: GET\n    path: ['{{BaseURL}}/']\n",
            "enable": True,
        },
        {
            "template_id": "tpl-tcp",
            "protocol": "tcp",
            "tags": ["rce"],
            "content": "id: tpl-tcp\ninfo:\n  name: T\n  author: a\n  severity: high\ntcp:\n  - host: ['{{Hostname}}']\n",
            "enable": True,
        },
        {
            "template_id": "tpl-dns",
            "protocol": "dns",
            "tags": ["rce"],
            "content": "id: tpl-dns\ninfo:\n  name: D\n  author: a\n  severity: info\ndns:\n  - name: '{{FQDN}}'\n",
            "enable": True,
        },
        {
            "template_id": "tpl-headless-skip",
            "protocol": "headless",
            "tags": ["rce"],
            "content": "id: tpl-headless-skip\ninfo:\n  name: HL\n  author: a\n  severity: high\nheadless:\n  - steps: []\n",
            "enable": True,
        },
        {
            "template_id": "tpl-empty-content",
            "protocol": "http",
            "tags": ["rce"],
            "content": "   ",
            "enable": True,
        },
    ])

    recorded_runs = []

    def fake_exec(cmd_list, timeout=None):
        args = shlex.split(" ".join(cmd_list))
        t_dir = args[args.index("-t") + 1]
        l_file = args[args.index("-l") + 1]
        recorded_runs.append({
            "files": sorted(p.name for p in Path(t_dir).glob("*.yaml")),
            "targets": [line.strip() for line in Path(l_file).read_text(encoding="utf-8").splitlines() if line.strip()],
        })
        return types.SimpleNamespace(returncode=0)

    app_env.utils.exec_system = fake_exec

    # 故意传入大写 tag "RCE"，且 web_targets 为空（模拟无存活 Web 站点但有开放端口与子域名场景）
    scan = scan_mod.NucleiScan(
        targets=[],
        options={"nuclei_config": {"include_community": False, "custom_template_mode": "tags", "selected_tags": ["RCE"]}},
        extra_targets={"network": ["192.0.2.10:6379"], "dns": ["dangling.example.com"]},
    )
    scan.nuclei_bin_path = "/usr/bin/nuclei"
    scan.nuclei_json_flag = "-jsonl"
    try:
        scan.exec_nuclei()
        assert len(scan._custom_skipped_unsupported) == 1
        assert scan._custom_skipped_unsupported[0] == ("tpl-headless-skip", "headless")
    finally:
        scan._delete_file()

    # web 桶因为 web_targets=[] 被安全跳过，仅运行 network 和 dns 桶
    assert len(recorded_runs) == 2
    assert recorded_runs[0] == {"files": ["tpl-tcp.yaml"], "targets": ["192.0.2.10:6379"]}
    assert recorded_runs[1] == {"files": ["tpl-dns.yaml"], "targets": ["dangling.example.com"]}


def test_real_nuclei_end_to_end_custom_info_http_and_tcp_against_loopback(app_env, monkeypatch):
    """使用真实 nuclei 二进制验证：1) info 级自建 HTTP 模板绕过社区 severity/黑名单命中；2) 空 Web 站点下自建 TCP 模板命中开放端口。"""
    nuclei_bin = shutil.which("nuclei")
    if not nuclei_bin:
        pytest.skip("nuclei binary not installed")

    svc, scan_mod, _, _, _ = _load_nuclei_stack(app_env)
    monkeypatch.setattr(svc, "get_community_templates_dir", lambda: "")

    def real_exec(cmd_list, timeout=None):
        args = shlex.split(" ".join(cmd_list))
        return subprocess.run(args + ["-ni", "-nh", "-no-stdin"], capture_output=True, text=True, timeout=30)

    app_env.utils.exec_system = real_exec

    # 1. 本地 HTTP 服务 + info 自建模板（并故意加入黑名单验证不被误屏蔽）
    class HttpHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"custom-admin-portal-v1"
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    http_srv = ThreadingHTTPServer(("127.0.0.1", 0), HttpHandler)
    http_thread = threading.Thread(target=http_srv.serve_forever, daemon=True)
    http_thread.start()

    # 2. 本地 TCP 服务 + tcp 自建模板
    tcp_srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_srv.bind(("127.0.0.1", 0))
    tcp_port = tcp_srv.getsockname()[1]
    tcp_srv.listen(5)
    stop_tcp = threading.Event()

    def serve_tcp():
        tcp_srv.settimeout(0.2)
        while not stop_tcp.is_set():
            try:
                conn, _ = tcp_srv.accept()
                conn.recv(1024)
                conn.sendall(b"+PONG\r\n")
                conn.close()
            except Exception:
                pass

    tcp_thread = threading.Thread(target=serve_tcp, daemon=True)
    tcp_thread.start()

    try:
        app_env.db.nuclei_template.insert_many([
            {
                "template_id": "real-asm-info-http",
                "protocol": "http",
                "severity": "info",
                "enable": True,
                "content": (
                    "id: real-asm-info-http\n"
                    "info:\n"
                    "  name: Real ASM Info HTTP\n"
                    "  author: verifier\n"
                    "  severity: info\n"
                    "http:\n"
                    "  - method: GET\n"
                    "    path:\n"
                    "      - '{{BaseURL}}/admin'\n"
                    "    matchers:\n"
                    "      - type: word\n"
                    "        words:\n"
                    "          - 'custom-admin-portal-v1'\n"
                ),
            },
            {
                "template_id": "real-asm-tcp-redis",
                "protocol": "tcp",
                "severity": "high",
                "enable": True,
                "content": (
                    "id: real-asm-tcp-redis\n"
                    "info:\n"
                    "  name: Real ASM TCP Pong\n"
                    "  author: verifier\n"
                    "  severity: high\n"
                    "tcp:\n"
                    "  - inputs:\n"
                    "      - data: \"PING\\r\\n\"\n"
                    "    host:\n"
                    "      - '{{Hostname}}'\n"
                    "    matchers:\n"
                    "      - type: word\n"
                    "        words:\n"
                    "          - '+PONG'\n"
                ),
            },
        ])
        app_env.db.nuclei_blacklist.insert_one({"template_id": "real-asm-info-http", "reason": "global fp"})

        # 默认 severity=[low,medium,high,critical]，但自建 info HTTP + TCP 均应正常命中
        results = scan_mod.nuclei_scan(
            targets=[f"http://127.0.0.1:{http_srv.server_port}"],
            options={"nuclei_config": {"include_community": False, "severity": ["critical", "high"], "custom_template_mode": "all_enabled"}},
            extra_targets={"network": [f"127.0.0.1:{tcp_port}"]},
        )
        by_id = {r["template_id"]: r for r in results}
        assert "real-asm-info-http" in by_id
        assert by_id["real-asm-info-http"]["template_source"] == "custom"
        assert by_id["real-asm-info-http"]["vuln_severity"] == "info"

        assert "real-asm-tcp-redis" in by_id
        assert by_id["real-asm-tcp-redis"]["template_source"] == "custom"
        assert by_id["real-asm-tcp-redis"]["target"] == f"127.0.0.1:{tcp_port}"
    finally:
        stop_tcp.set()
        tcp_srv.close()
        http_srv.shutdown()
        http_srv.server_close()


def test_batch_import_runs_semantic_validation_and_rejects_broken_template(app_env):
    if not shutil.which("nuclei"):
        pytest.skip("nuclei binary not installed")

    _, _, _, client, headers = _load_nuclei_stack(app_env)

    good_1 = (
        "id: import-good-1\ninfo:\n  name: Good 1\n  author: a\n  severity: high\n"
        "http:\n  - method: GET\n    path: ['{{BaseURL}}/a']\n    matchers:\n      - type: status\n        status: [200]\n"
    )
    good_2 = (
        "id: import-good-2\ninfo:\n  name: Good 2\n  author: a\n  severity: info\n"
        "http:\n  - method: GET\n    path: ['{{BaseURL}}/b']\n    matchers:\n      - type: status\n        status: [200]\n"
    )
    bad_dsl = (
        "id: import-bad-dsl\ninfo:\n  name: Bad DSL\n  author: a\n  severity: high\n"
        "http:\n  - method: GET\n    path: ['{{BaseURL}}/c']\n    matchers:\n      - type: dsl\n        dsl: ['unknown_fn(']\n"
    )

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("good1.yaml", good_1)
        zf.writestr("good2.yaml", good_2)
        zf.writestr("bad.yaml", bad_dsl)
    buf.seek(0)

    res = client.post(
        "/api/nuclei/template/import/",
        headers=headers,
        data={"file": (buf, "bundle.zip")},
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    assert res.json["code"] == 200
    data = res.json["data"]
    assert data["success_count"] == 2
    assert data["fail_count"] == 1
    assert data["fail_details"][0]["filename"] == "bad.yaml"
    assert "语义验证不通过" in data["fail_details"][0]["reason"]
    assert app_env.db.nuclei_template.find_one({"template_id": "import-good-1"}) is not None
    assert app_env.db.nuclei_template.find_one({"template_id": "import-good-2"}) is not None
    assert app_env.db.nuclei_template.find_one({"template_id": "import-bad-dsl"}) is None


def test_wih_discovered_sites_merged_into_available_sites_and_poc_sites():
    """验证 DomainTask.process_wih_domains 修复后将 WIH 增量站点合并至 available_sites 并刷新 poc_sites。"""
    source = (ROOT / "app/tasks/domain.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    cls_node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "DomainTask")
    method_node = next(n for n in cls_node.body if isinstance(n, ast.FunctionDef) and n.name == "process_wih_domains")

    class FakeWebSiteFetch:
        def __init__(self, task_id, sites, options, scope_domain=None):
            self.sites = list(sites)
            self.available_sites = list(sites)
            self.catch_all_sites = set()
            self.wih_domain_set = set()
            self._poc_sites = None

        @property
        def poc_sites(self):
            if self._poc_sites is None:
                self._poc_sites = {s for s in self.available_sites if s not in self.catch_all_sites}
            return self._poc_sites

        def run(self):
            pass

    helpers_mod = types.ModuleType("app.helpers")
    helpers_mod.find_domain_by_task_id = lambda tid: []
    services_stub = types.SimpleNamespace(probe_http=lambda doms, *args: [f"https://{d}" for d in doms])
    env = {
        "time": __import__("time"),
        "logger": Mock(),
        "services": services_stub,
        "WebSiteFetch": FakeWebSiteFetch,
    }
    exec(compile(ast.Module(body=[copy.deepcopy(method_node)], type_ignores=[]), "domain-wih", "exec"), env)

    orig_helpers = sys.modules.get("app.helpers")
    sys.modules["app.helpers"] = helpers_mod
    try:
        main_fetch = FakeWebSiteFetch("t1", ["https://www.example.com"], {})
        # 触发一次旧 poc_sites 缓存，验证后续必须失效刷新
        assert main_fetch.poc_sites == {"https://www.example.com"}

        task_stub = types.SimpleNamespace(
            task_id="t1",
            base_domain="example.com",
            options={},
            task_tag="task",
            site_list=["https://www.example.com"],
            domain_source_map={},
            wih_domain_set={"api-wih.example.com"},
            web_site_fetch=main_fetch,
            update_task_field=lambda *a, **k: None,
            update_services=lambda *a, **k: None,
            build_domain_info=lambda doms: [types.SimpleNamespace(domain=d) for d in doms],
            clear_domain_info_by_record=lambda x: x,
            save_domain_info_list=lambda *a, **k: None,
        )
        env["process_wih_domains"](task_stub)
        assert "https://api-wih.example.com" in main_fetch.available_sites
        assert "https://api-wih.example.com" in main_fetch.poc_sites
    finally:
        if orig_helpers is None:
            sys.modules.pop("app.helpers", None)
        else:
            sys.modules["app.helpers"] = orig_helpers


def test_policy_nuclei_config_normalization_and_push_custom_badge(app_env):
    """验证策略 nuclei_config 校验归一化、告警推送 [自建] 标注与 Webhook template_source 透传。"""
    # 1. _normalize_nuclei_config
    pol_tree = ast.parse((ROOT / "app/routes/policy.py").read_text(encoding="utf-8"))
    norm_fn = next(n for n in pol_tree.body if isinstance(n, ast.FunctionDef) and n.name == "_normalize_nuclei_config")
    pol_env = {}
    exec(compile(ast.Module(body=[copy.deepcopy(norm_fn)], type_ignores=[]), "pol-norm", "exec"), pol_env)
    normalize = pol_env["_normalize_nuclei_config"]

    _, err_both_off = normalize({"include_community": False, "custom_template_mode": "none"}, nuclei_scan_enabled=True)
    assert err_both_off and "不能同时关闭" in err_both_off

    _, err_sel_empty = normalize({"include_community": False, "custom_template_mode": "selected", "selected_custom_templates": []}, nuclei_scan_enabled=True)
    assert err_sel_empty and "至少选择 1 个自建模板" in err_sel_empty

    ok_cfg, ok_err = normalize({"include_community": False, "custom_template_mode": "tags", "selected_tags": [" RCE ", "rce"]}, nuclei_scan_enabled=True)
    assert ok_err is None
    assert ok_cfg["include_community"] is False
    assert ok_cfg["selected_tags"] == ["rce"]

    # 2. push.build_nuclei_vuln_report 自定义来源标注
    app_env.monkeypatch.setattr(sys.modules["app.utils"], "http_req", lambda *a, **kw: None, raising=False)
    push_mod = load_source(app_env.monkeypatch, "app.utils.push", "app/utils/push.py")
    title, plain, html_body, _ = push_mod.build_nuclei_vuln_report(
        task_name="ASM-Task",
        task_target="example.com",
        results=[
            {
                "template_id": "custom-rce-01",
                "template_source": "custom",
                "vuln_name": "Custom RCE",
                "vuln_severity": "critical",
                "vuln_url": "https://example.com/rce",
            },
            {
                "template_id": "CVE-2026-0001",
                "template_source": "community",
                "vuln_name": "Comm Vuln",
                "vuln_severity": "high",
                "vuln_url": "https://example.com/cve",
            },
        ],
    )
    assert "[严重][自建] Custom RCE (custom-rce-01)" in plain
    assert "[高危] Comm Vuln (CVE-2026-0001)" in plain
    assert "自建</span>" in html_body

    # 3. Webhook _RESULT_FIELDS 包含 template_source
    wh_tree = ast.parse((ROOT / "app/services/webhook.py").read_text(encoding="utf-8"))
    wh_cls = next(n for n in wh_tree.body if isinstance(n, ast.ClassDef) and n.name == "NucleiVulnWebHook")
    wh_fields = next(n for n in wh_cls.body if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "_RESULT_FIELDS" for t in n.targets))
    field_vals = ast.literal_eval(wh_fields.value)
    assert "template_source" in field_vals


def test_migrate_nuclei_result_template_source_backfills_legacy_docs(app_env):
    app_env.db.nuclei_template.insert_one({"template_id": "my-custom-rule", "enable": True})
    app_env.db.nuclei_result.insert_many([
        {"task_id": "t1", "template_id": "my-custom-rule", "template_url": ""},
        {"task_id": "t1", "template_id": "CVE-2025-0001", "template_url": "https://github.com/projectdiscovery/nuclei-templates/x.yaml"},
        {"task_id": "t1", "template_id": "legacy-unknown", "template_url": ""},
    ])
    app_env.db.asset_nuclei_result.insert_one({"scope_id": "s1", "template_id": "my-custom-rule", "template_url": ""})

    tree = ast.parse((ROOT / "app/utils/arlupdate.py").read_text(encoding="utf-8"))
    mig_fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "migrate_nuclei_result_template_source")
    mig_env = {"conn_db": app_env.db.__getitem__}
    exec(compile(ast.Module(body=[copy.deepcopy(mig_fn)], type_ignores=[]), "mig-ts", "exec"), mig_env)
    mig_env["migrate_nuclei_result_template_source"]()

    assert app_env.db.nuclei_result.find_one({"template_id": "my-custom-rule"})["template_source"] == "custom"
    assert app_env.db.nuclei_result.find_one({"template_id": "CVE-2025-0001"})["template_source"] == "community"
    assert app_env.db.nuclei_result.find_one({"template_id": "legacy-unknown"})["template_source"] == "community"
    assert app_env.db.asset_nuclei_result.find_one({"template_id": "my-custom-rule"})["template_source"] == "custom"
