"""Nuclei 模板创建、校验、Dry Run 即时调试与自建模板扫描通道回归测试。"""

import ast
import importlib.util
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import types
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import Mock, patch

import mongomock
import pytest

from security_support import ROOT, app_env, load_source, make_client


def _load_nuclei_env(env):
    """在隔离环境中加载 nuclei_template_service、nuclei_scan 与 nuclei 路由。"""
    env.cfg.Config.TMP_PATH = str(env.tmp)
    env.utils.random_choices = lambda length=8: f"fix{length}"
    env.utils.build_ret = lambda error, data: (
        {**({"message": error, "code": 999} if isinstance(error, str) else error), "data": data}
    )
    env.utils.exec_system = Mock()

    # 避免导入真实 proxy_service 时连库或读生产配置；默认直连无代理
    modules_mod = types.ModuleType("app.modules")
    modules_mod.ErrorMsg = types.SimpleNamespace(
        Success={"code": 200, "message": "success"},
        Error={"code": 500, "message": "系统异常"},
    )
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


def test_static_validation_requires_author_severity_and_protocol(app_env):
    svc, _, _, _, _ = _load_nuclei_env(app_env)

    # 1. 缺 author
    ok, err = svc.parse_and_validate_nuclei_yaml(
        "id: no-author\ninfo:\n  name: Test\n  severity: high\nhttp:\n  - method: GET\n    path: ['{{BaseURL}}/']\n"
    )
    assert not ok
    assert "author" in err

    # 2. author 支持字符串列表
    ok_list, meta_list = svc.parse_and_validate_nuclei_yaml(
        "id: list-author\ninfo:\n  name: Test\n  author:\n    - alice\n    - bob\n  severity: high\n"
        "http:\n  - method: GET\n    path: ['{{BaseURL}}/']\n"
    )
    assert ok_list
    assert meta_list["author"] == "alice, bob"

    # 3. 无效 severity 不再静默降级为 info
    ok_sev, err_sev = svc.parse_and_validate_nuclei_yaml(
        "id: bad-sev\ninfo:\n  name: Test\n  author: a\n  severity: urgent\nhttp:\n  - method: GET\n"
    )
    assert not ok_sev
    assert "severity" in err_sev

    # 4. 缺少协议块或空协议块
    ok_proto, err_proto = svc.parse_and_validate_nuclei_yaml(
        "id: no-proto\ninfo:\n  name: Test\n  author: a\n  severity: info\n"
    )
    assert not ok_proto
    assert "协议" in err_proto

    ok_empty, err_empty = svc.parse_and_validate_nuclei_yaml(
        "id: empty-proto\ninfo:\n  name: Test\n  author: a\n  severity: info\nhttp: []\n"
    )
    assert not ok_empty
    assert "不能为空" in err_empty


def test_protocol_aware_target_normalization(app_env):
    svc, _, _, _, _ = _load_nuclei_env(app_env)

    assert svc.normalize_dry_run_target("example.com:8080", "http") == (True, "http://example.com:8080")
    assert svc.normalize_dry_run_target("https://example.com/a", "http") == (True, "https://example.com/a")
    assert svc.normalize_dry_run_target("example.com", "dns") == (True, "example.com")
    assert svc.normalize_dry_run_target("https://example.com/foo", "dns") == (True, "example.com")
    assert svc.normalize_dry_run_target("http://192.0.2.10:6379/ping", "tcp") == (True, "192.0.2.10:6379")

    ok_space, _ = svc.normalize_dry_run_target("example.com -t evil.yaml", "http")
    assert not ok_space
    ok_flag, _ = svc.normalize_dry_run_target("-t", "http")
    assert not ok_flag


def test_create_and_update_routes_support_enable_and_semantic_validate(app_env, monkeypatch):
    svc, _, _, client, headers = _load_nuclei_env(app_env)

    # 无真实 nuclei 时降级静态校验，模拟有 nuclei 返回语义失败时必须拦截
    monkeypatch.setattr(svc.shutil, "which", lambda name: None)

    valid_yaml = (
        "id: custom-create-check\n"
        "info:\n"
        "  name: Create Check\n"
        "  author: sec-team\n"
        "  severity: high\n"
        "  tags: custom,rce\n"
        "http:\n"
        "  - method: GET\n"
        "    path:\n"
        "      - '{{BaseURL}}/health'\n"
        "    matchers:\n"
        "      - type: status\n"
        "        status: [200]\n"
    )

    # 支持 enable=False 创建
    res = client.post(
        "/api/nuclei/template/create/",
        headers=headers,
        json={"content": valid_yaml, "enable": False},
    )
    assert res.status_code == 200
    assert res.json["code"] == 200
    assert res.json["data"]["enable"] is False
    stored = app_env.db.nuclei_template.find_one({"template_id": "custom-create-check"})
    assert stored is not None and stored["enable"] is False

    # 重复 ID 拦截
    dup = client.post("/api/nuclei/template/create/", headers=headers, json={"content": valid_yaml})
    assert dup.json["code"] != 200
    assert "已存在" in dup.json["message"]

    # 字符串 "false" 正确解析为 False
    valid_yaml_2 = valid_yaml.replace("custom-create-check", "custom-create-check-2")
    res2 = client.post(
        "/api/nuclei/template/create/",
        headers=headers,
        json={"content": valid_yaml_2, "enable": "false"},
    )
    assert res2.json["code"] == 200
    assert app_env.db.nuclei_template.find_one({"template_id": "custom-create-check-2"})["enable"] is False

    # 更新重命名冲突应返回清晰业务提示而非 500 系统异常文案
    conflict_yaml = valid_yaml_2.replace("custom-create-check-2", "custom-create-check")
    upd_conflict = client.post(
        "/api/nuclei/template/update/",
        headers=headers,
        json={"template_id": "custom-create-check-2", "content": conflict_yaml},
    )
    assert upd_conflict.json["code"] == 999
    assert "已被占用" in upd_conflict.json["message"]
    assert "系统异常" not in upd_conflict.json["message"]

    # 模拟 nuclei -validate 拦截语义错误，且命令行带 -duc 和 -no-color
    seen_cmds = []

    def fake_run(cmd, **kwargs):
        seen_cmds.append(cmd)
        return types.SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="[ERR] Could not load template: invalid matcher DSL",
        )

    monkeypatch.setattr(svc.shutil, "which", lambda name: "/usr/bin/nuclei")
    monkeypatch.setattr(svc.subprocess, "run", fake_run)
    bad_sem = client.post(
        "/api/nuclei/template/create/",
        headers=headers,
        json={"content": valid_yaml.replace("custom-create-check", "custom-bad-sem")},
    )
    assert bad_sem.json["code"] != 200
    assert "Nuclei 语义验证不通过" in bad_sem.json["message"]
    assert "-duc" in seen_cmds[0] and "-no-color" in seen_cmds[0] and "-validate" in seen_cmds[0]


def test_dry_run_route_strips_ansi_detects_matches_passes_proxy_and_handles_nonzero(app_env, monkeypatch):
    _, _, route_mod, client, headers = _load_nuclei_env(app_env)

    # 1. 模拟带 ANSI 颜色、且 -jle 产出结构化结果的执行（验证 info 级别 & 代理注入 & 脱敏）
    seen_cmds = []

    def fake_resolve_proxy(targets):
        return "http://user:s3cr3t@192.0.2.1:8080", "http://user:***@192.0.2.1:8080"

    def fake_run_match(cmd, **kwargs):
        seen_cmds.append(list(cmd))
        jle_idx = cmd.index("-jle") + 1
        Path(cmd[jle_idx]).write_text(
            json.dumps({
                "template-id": "dryrun-demo",
                "info": {"name": "DryRun Demo", "severity": "info"},
                "matched-at": "http://192.0.2.10:8080/hit",
                "curl-command": "curl 'http://192.0.2.10:8080/hit'",
                "extracted-results": ["secret-token"],
            }) + "\n",
            encoding="utf-8",
        )
        return types.SimpleNamespace(
            returncode=0,
            stdout="[\x1b[92mdryrun-demo\x1b[0m] [\x1b[94mhttp\x1b[0m] [\x1b[34minfo\x1b[0m] http://192.0.2.10:8080/hit\n",
            stderr="[\x1b[34mINF\x1b[0m] Using proxy http://user:s3cr3t@192.0.2.1:8080\n",
        )

    monkeypatch.setattr(route_mod.shutil, "which", lambda name: "/usr/bin/nuclei")
    monkeypatch.setattr(route_mod, "resolve_nuclei_proxy", fake_resolve_proxy)
    monkeypatch.setattr(route_mod.subprocess, "run", fake_run_match)

    tpl = (
        "id: dryrun-demo\ninfo:\n  name: DryRun Demo\n  author: tester\n  severity: info\n"
        "http:\n  - method: GET\n    path: ['{{BaseURL}}/hit']\n    matchers:\n      - type: status\n        status: [200]\n"
    )
    res = client.post("/api/nuclei/template/test/", headers=headers, json={"content": tpl, "target": "192.0.2.10:8080"})
    assert res.status_code == 200
    assert res.json["code"] == 200
    data = res.json["data"]
    assert data["matched"] is True
    assert data["matched_count"] == 1
    assert data["findings"][0]["matched_at"] == "http://192.0.2.10:8080/hit"
    assert data["findings"][0]["extracted_results"] == ["secret-token"]
    assert "\x1b[" not in data["output"]
    assert "s3cr3t" not in data["output"]
    assert "***@192.0.2.1:8080" in data["output"]
    assert "-proxy" in seen_cmds[0] and "-nc" in seen_cmds[0]

    # 2. 非 0 退出码应明确报错而非返回 code=200 未命中，且不把完整 output 拼入 message
    def fake_run_fail(cmd, **kwargs):
        return types.SimpleNamespace(
            returncode=1,
            stdout="",
            stderr="[FTL] Could not run nuclei: no templates provided for scan\n",
        )

    monkeypatch.setattr(route_mod.subprocess, "run", fake_run_fail)
    res_fail = client.post("/api/nuclei/template/test/", headers=headers, json={"content": tpl, "target": "192.0.2.10:8080"})
    assert res_fail.json["code"] != 200
    assert "Nuclei 执行失败" in res_fail.json["message"]
    assert "output:" not in res_fail.json["message"]
    assert res_fail.json["data"]["returncode"] == 1
    assert "no templates provided" in res_fail.json["data"]["output"]

    # 3. 确认临时文件已清理
    assert not any(p.name.startswith("dryrun_") for p in Path(app_env.tmp).iterdir())


def test_real_nuclei_dry_run_against_loopback_http(app_env, monkeypatch):
    """当系统安装有 nuclei 时，对真实二进制执行端到端 Dry Run 验证（覆盖 high 与 info 级别命中）。"""
    nuclei_bin = shutil.which("nuclei")
    if not nuclei_bin:
        pytest.skip("nuclei binary not installed")

    svc, _, _, client, headers = _load_nuclei_env(app_env)
    # 生产环境默认禁止调试 127.0.0.1 回环地址，本用例专测真实 Nuclei 回环命中链路，显式放行测试回环目标
    monkeypatch.setattr(svc, "_validate_dry_run_target_safety", lambda target: (True, ""))

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            body = b"spring.cloud.ok" if self.path == "/actuator/env" else b"not-found"
            self.send_response(200 if self.path == "/actuator/env" else 404)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        for severity in ("high", "info"):
            tpl = (
                f"id: real-dryrun-{severity}\n"
                "info:\n"
                f"  name: Real DryRun {severity}\n"
                "  author: verifier\n"
                f"  severity: {severity}\n"
                "  tags: custom,demo\n"
                "http:\n"
                "  - method: GET\n"
                "    path:\n"
                "      - '{{BaseURL}}/actuator/env'\n"
                "    matchers:\n"
                "      - type: word\n"
                "        words:\n"
                "          - 'spring.cloud.ok'\n"
            )
            hit = client.post(
                "/api/nuclei/template/test/",
                headers=headers,
                json={"content": tpl, "target": f"127.0.0.1:{server.server_port}"},
            )
            assert hit.json["code"] == 200, hit.json
            assert hit.json["data"]["matched"] is True, hit.json
            assert hit.json["data"]["matched_count"] == 1
            assert "\x1b[" not in hit.json["data"]["output"]

        miss_tpl = (
            "id: real-dryrun-miss\n"
            "info:\n"
            "  name: Real DryRun Miss\n"
            "  author: verifier\n"
            "  severity: high\n"
            "http:\n"
            "  - method: GET\n"
            "    path:\n"
            "      - '{{BaseURL}}/missing'\n"
            "    matchers:\n"
            "      - type: status\n"
            "        status: [200]\n"
        )
        miss = client.post(
            "/api/nuclei/template/test/",
            headers=headers,
            json={"content": miss_tpl, "target": f"http://127.0.0.1:{server.server_port}"},
        )
        assert miss.json["code"] == 200
        assert miss.json["data"]["matched"] is False
        assert miss.json["data"]["matched_count"] == 0
    finally:
        server.shutdown()
        server.server_close()


def test_nuclei_scan_custom_templates_bypass_cve_http_tag_filter_and_respect_none_mode(app_env, monkeypatch):
    svc, scan_mod, route_mod, _, _ = _load_nuclei_env(app_env)

    app_env.db.nuclei_template.insert_one({
        "template_id": "custom-rce-notag",
        "name": "Custom RCE",
        "content": "id: custom-rce-notag\ninfo:\n  name: Custom RCE\n  author: a\n  severity: high\n  tags: [custom, rce]\n",
        "tags": ["custom", "rce"],
        "enable": True,
    })

    # 1. mode=none 不应物化任何自建模板
    scan_none = scan_mod.NucleiScan(
        targets=["https://example.com"],
        options={"nuclei_config": {"custom_template_mode": "none"}},
    )
    scan_none._materialize_custom_templates()
    assert scan_none.custom_templates_path is None

    # 2. mode=all_enabled 且存在社区模板目录时：社区走 -tags cve,http，自建独立通道无 -tags/-severity/-eid 限制并合并结果
    comm_dir = app_env.tmp / "comm_templates"
    comm_dir.mkdir()
    (comm_dir / "demo.yaml").write_text("id: comm-demo\n", encoding="utf-8")
    monkeypatch.setattr(svc, "get_community_templates_dir", lambda: str(comm_dir))
    monkeypatch.setattr(route_mod, "get_community_templates_dir", lambda: str(comm_dir))

    commands = []

    def fake_exec(cmd_list, timeout=None):
        args = shlex.split(" ".join(cmd_list))
        commands.append(args)
        out_path = args[args.index("-o") + 1]
        if "-tags" in args:
            Path(out_path).write_text(
                json.dumps({
                    "template-id": "comm-cve",
                    "url": "https://example.com",
                    "matched-at": "https://example.com/cve",
                    "info": {"name": "Comm CVE", "severity": "high"},
                }) + "\n",
                encoding="utf-8",
            )
        else:
            Path(out_path).write_text(
                json.dumps({
                    "template-id": "custom-rce-notag",
                    "url": "https://example.com",
                    "matched-at": "https://example.com/custom",
                    "info": {"name": "Custom RCE", "severity": "critical"},
                }) + "\n",
                encoding="utf-8",
            )
        return types.SimpleNamespace(returncode=0)

    app_env.utils.exec_system = fake_exec
    scan = scan_mod.NucleiScan(targets=["https://example.com"], options={"nuclei_config": {"custom_template_mode": "all_enabled"}})
    scan.nuclei_bin_path = "/usr/bin/nuclei"
    scan.nuclei_json_flag = "-jsonl"
    try:
        scan.exec_nuclei()
        merged = scan.dump_result()
    finally:
        scan._delete_file()

    assert len(commands) == 2
    assert "-tags" in commands[0] and commands[0][commands[0].index("-tags") + 1] == "cve,http"
    assert "-tags" not in commands[1]
    assert commands[1][commands[1].index("-t") + 1] == scan.custom_templates_path
    assert {item["template_id"] for item in merged} == {"comm-cve", "custom-rce-notag"}
    assert not Path(scan.nuclei_result_path).exists()
    assert not Path(scan.nuclei_custom_result_path).exists()
