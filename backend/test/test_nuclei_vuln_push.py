"""Nuclei 漏洞推送全链路单元测试（离线隔离，不依赖外部网络或真实 MongoDB）。"""
import ast
import copy
from contextlib import contextmanager
from datetime import datetime
import importlib.util
import json
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from bson import ObjectId
import mongomock
from pymongo import UpdateOne

ROOT = Path(__file__).resolve().parents[1]


def _load_nodes(path, env, names):
    tree = ast.parse((ROOT / path).read_text())
    nodes = [
        copy.deepcopy(n)
        for n in tree.body
        if getattr(n, "name", None) in names
        or (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets))
    ]
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(path), "exec"), env)


def _load_push_module(fake_config, fake_db, webhook_calls):
    """隔离加载 app/utils/push.py，并在返回前绑定可清理的 sys.modules 补丁。"""
    app_pkg = types.ModuleType("app")
    app_pkg.__path__ = []
    utils_pkg = types.ModuleType("app.utils")
    utils_pkg.__path__ = []
    conn_mod = types.ModuleType("app.utils.conn")
    conn_mod.conn_db = fake_db.__getitem__
    config_mod = types.ModuleType("app.config")
    config_mod.Config = fake_config
    services_pkg = types.ModuleType("app.services")
    services_pkg.__path__ = []
    webhook_mod = types.ModuleType("app.services.webhook")

    def _fake_nuclei_webhook(**kwargs):
        webhook_calls.append(kwargs)

    webhook_mod.nuclei_vuln_web_hook = _fake_nuclei_webhook
    services_pkg.webhook = webhook_mod

    logger = MagicMock()
    utils_pkg.get_logger = lambda: logger
    utils_pkg.http_req = MagicMock()
    utils_pkg.conn = conn_mod
    app_pkg.utils = utils_pkg
    app_pkg.config = config_mod
    app_pkg.services = services_pkg

    patcher = patch.dict(
        sys.modules,
        {
            "app": app_pkg,
            "app.utils": utils_pkg,
            "app.utils.conn": conn_mod,
            "app.config": config_mod,
            "app.services": services_pkg,
            "app.services.webhook": webhook_mod,
        },
    )
    patcher.start()
    spec = importlib.util.spec_from_file_location("test_isolated_push_module", ROOT / "app/utils/push.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    sys.modules["app.utils.push"] = mod
    utils_pkg.push = mod
    return mod, patcher


class NucleiPushCoreTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().arl
        self.webhook_calls = []
        self.config = types.SimpleNamespace(
            PUSH_OPTIONS=["task_complete", "nuclei_vuln"],
            NUCLEI_PUSH_SEVERITIES=["critical", "high", "medium", "low"],
            DINGDING_ACCESS_TOKEN="dd-token",
            DINGDING_SECRET="dd-secret",
            FEISHU_WEBHOOK="https://open.feishu.cn/open-apis/bot/v2/hook/test",
            FEISHU_SECRET="fs-secret",
            WX_WORK_WEBHOOK="https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test",
            TG_BOT_TOKEN="tg-token",
            TG_CHAT_ID="tg-chat",
            EMAIL_HOST="smtp.example.com",
            EMAIL_PORT=465,
            EMAIL_USERNAME="bot@example.com",
            EMAIL_PASSWORD="pwd",
            EMAIL_TO="sec@example.com",
        )
        self.push_mod, self._patcher = _load_push_module(self.config, self.db, self.webhook_calls)
        self.addCleanup(self._patcher.stop)

    def test_push_summary_handles_update_only_vulns_without_zero_count(self):
        p = self.push_mod.Push(
            asset_map={"task_name": "monitor_job"},
            asset_counter={"nuclei_result": 0},
            update_counter={"nuclei_result": 3},
        )
        plain = p._generate_plain_text_payload()
        html_out = p._generate_html_payload()
        self.assertIn("监测到 3 项存量漏洞变动", plain)
        self.assertNotIn("检出 0 项漏洞风险", plain)
        self.assertIn("监测到 <strong>3</strong> 项存量漏洞变动", html_out)

    def test_severity_normalization_filtering_and_sorting(self):
        norm = self.push_mod.normalize_nuclei_push_severities(["LOW", "critical", "invalid", "high", "low"])
        self.assertEqual(norm, ["critical", "high", "low"])
        self.assertEqual(self.push_mod.normalize_nuclei_push_severities([]), [])

        findings = [
            {"template_id": "t-info", "vuln_severity": "info", "vuln_name": "Info"},
            {"template_id": "t-low", "vuln_severity": "low", "vuln_name": "Low"},
            {"template_id": "t-crit", "vuln_severity": "critical", "vuln_name": "Crit"},
            {"template_id": "t-high", "vuln_severity": "HIGH", "vuln_name": "High"},
        ]
        default_filtered = self.push_mod.filter_and_sort_nuclei_results(findings)
        self.assertEqual([x["template_id"] for x in default_filtered], ["t-crit", "t-high", "t-low"])

        high_only = self.push_mod.filter_and_sort_nuclei_results(findings, ["critical", "high"])
        self.assertEqual([x["template_id"] for x in high_only], ["t-crit", "t-high"])

        self.config.NUCLEI_PUSH_SEVERITIES = []
        self.assertEqual(self.push_mod.filter_and_sort_nuclei_results(findings), [])

    def test_build_report_truncates_and_escapes_html(self):
        findings = [
            {
                "template_id": f"cve-2026-{i:04d}",
                "vuln_name": f"<script>alert({i})</script>",
                "vuln_severity": "high" if i % 2 == 0 else "critical",
                "vuln_url": f"https://app.example.com/path?x={i}&q=<a>",
            }
            for i in range(25)
        ]
        ordered = self.push_mod.filter_and_sort_nuclei_results(findings)
        title, plain, html_out, counts = self.push_mod.build_nuclei_vuln_report(
            task_name="scan-<prod>",
            task_target="app.example.com",
            results=ordered,
            scope_name="核心资产组",
            max_items=20,
        )
        self.assertIn("检出 25 项漏洞", title)
        self.assertEqual(counts["critical"], 12)
        self.assertEqual(counts["high"], 13)
        self.assertIn("所属资产组：核心资产组", plain)
        self.assertIn("其余 5 项请登录 ARL-Next 控制台查看", plain)
        self.assertNotIn("<script>", html_out)
        self.assertIn("&lt;script&gt;alert(", html_out)

    def test_nuclei_vuln_push_dispatches_all_6_channels_and_respects_gates(self):
        tid = self.db.task.insert_one({"name": "prod-scan", "target": "example.com", "status": "done", "end_time": "2026-11-18 21:00:00"}).inserted_id
        sid = self.db.asset_scope.insert_one({"name": "生产资产组"}).inserted_id
        findings = [
            {"template_id": "cve-1", "vuln_name": "RCE", "vuln_severity": "critical", "vuln_url": "https://a.example.com/rce"},
            {"template_id": "info-1", "vuln_name": "Banner", "vuln_severity": "info", "vuln_url": "https://a.example.com/"},
        ]

        with patch.object(self.push_mod, "dingding_send", return_value={"errcode": 0}) as m_dd, \
             patch.object(self.push_mod, "feishu_send", return_value={"code": 0}) as m_fs, \
             patch.object(self.push_mod, "wx_work_send", return_value={"errcode": 0}) as m_wx, \
             patch.object(self.push_mod, "telegram_send", return_value={"ok": True}) as m_tg, \
             patch.object(self.push_mod, "send_email") as m_em:
            sent = self.push_mod.nuclei_vuln_push(str(tid), findings, scope_id=str(sid))

        self.assertTrue(sent)
        m_dd.assert_called_once()
        m_fs.assert_called_once()
        m_wx.assert_called_once()
        m_tg.assert_called_once()
        m_em.assert_called_once()
        self.assertEqual(len(self.webhook_calls), 1)
        self.assertEqual(self.webhook_calls[0]["task_id"], str(tid))
        self.assertEqual(self.webhook_calls[0]["scope_id"], str(sid))
        self.assertEqual([x["template_id"] for x in self.webhook_calls[0]["nuclei_results"]], ["cve-1"])
        # Email 应接收完整 HTML 表格
        self.assertIn("<table", m_em.call_args.args[6])

        # 未订阅 nuclei_vuln 时不触发任何通道
        self.webhook_calls.clear()
        self.config.PUSH_OPTIONS = ["task_complete"]
        with patch.object(self.push_mod, "dingding_send") as m_dd2:
            self.assertFalse(self.push_mod.nuclei_vuln_push(str(tid), findings, scope_id=str(sid)))
            m_dd2.assert_not_called()
        self.assertEqual(self.webhook_calls, [])

        # 仅有 info 级别（不在白名单）时不推送
        self.config.PUSH_OPTIONS = ["nuclei_vuln"]
        self.assertFalse(self.push_mod.nuclei_vuln_push(str(tid), [findings[1]], scope_id=str(sid)))
        self.assertEqual(self.webhook_calls, [])

    def test_wecom_message_truncated_within_byte_limit(self):
        long_text = "\n".join([f"{i}. [高危] 测试漏洞标题用于校验企业微信字节截断边界 {i}" for i in range(60)])
        with patch.object(self.push_mod, "dingding_send", return_value={"errcode": 0}), \
             patch.object(self.push_mod, "feishu_send", return_value={"code": 0}), \
             patch.object(self.push_mod, "wx_work_send", return_value={"errcode": 0}) as m_wx, \
             patch.object(self.push_mod, "telegram_send", return_value={"ok": True}), \
             patch.object(self.push_mod, "send_email"):
            self.push_mod.unified_push("nuclei_vuln", "超长漏洞告警", long_text)
        sent_msg = m_wx.call_args.args[0]
        self.assertLessEqual(len(sent_msg.encode("utf-8")), 2000)


class NucleiWebhookTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().arl
        self.config = types.SimpleNamespace(
            WEB_HOOK_URL="https://webhook.example.com/arl",
            WEB_HOOK_TOKEN="hook-secret",
        )
        self.http_calls = []
        app_pkg = types.ModuleType("app")
        app_pkg.__path__ = []
        utils_pkg = types.ModuleType("app.utils")
        utils_pkg.__path__ = []
        helpers_pkg = types.ModuleType("app.helpers")
        helpers_pkg.__path__ = []
        asset_site_mod = types.ModuleType("app.helpers.asset_site")
        asset_site_mod.build_show_filed_map = lambda fields: {f: 1 for f in fields}
        config_mod = types.ModuleType("app.config")
        config_mod.Config = self.config
        push_mod = types.ModuleType("app.utils.push")
        push_mod.count_nuclei_severities = lambda items: {
            sev: sum(1 for i in items if i.get("vuln_severity") == sev)
            for sev in ("critical", "high", "medium", "low", "info")
        }

        def _fake_http_req(url, method="get", json=None, headers=None, timeout=10, proxy_domain=None):
            self.http_calls.append({"url": url, "method": method, "json": json, "headers": headers, "timeout": timeout, "proxy_domain": proxy_domain})
            return types.SimpleNamespace(status_code=200)

        utils_pkg.conn_db = self.db.__getitem__
        utils_pkg.get_logger = lambda: MagicMock()
        utils_pkg.http_req = _fake_http_req
        utils_pkg.push = push_mod
        app_pkg.utils = utils_pkg
        app_pkg.config = config_mod
        app_pkg.helpers = helpers_pkg

        self._patcher = patch.dict(
            sys.modules,
            {
                "app": app_pkg,
                "app.utils": utils_pkg,
                "app.utils.push": push_mod,
                "app.config": config_mod,
                "app.helpers": helpers_pkg,
                "app.helpers.asset_site": asset_site_mod,
            },
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

        spec = importlib.util.spec_from_file_location("test_isolated_webhook", ROOT / "app/services/webhook.py")
        self.webhook_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.webhook_mod)

    def test_nuclei_vuln_webhook_payload_and_unscoped_safety(self):
        tid = self.db.task.insert_one({
            "name": "unscoped-task",
            "target": "https://demo.example.com",
            "type": "domain",
            "task_tag": "task",
            "start_time": "2026-11-18 20:00:00",
            "status": "done",
            "end_time": "2026-11-18 20:05:00",
            "options": {"nuclei_scan": True},
        }).inserted_id
        results = [
            {
                "template_id": "cve-2026-1",
                "vuln_name": "Test Vuln",
                "vuln_severity": "critical",
                "vuln_url": "https://demo.example.com/api",
                "target": "https://demo.example.com",
                "host": "https://demo.example.com",
                "extracted_results": ["uid=0(root)"],
                "save_date": "2026-11-18 20:04:00",
            }
        ]
        self.webhook_mod.nuclei_vuln_web_hook(task_id=str(tid), scope_id="", nuclei_results=results)
        self.assertEqual(len(self.http_calls), 1)
        call = self.http_calls[0]
        self.assertEqual(call["url"], "https://webhook.example.com/arl")
        self.assertEqual(call["headers"], {"Token": "hook-secret"})
        self.assertEqual(call["proxy_domain"], "intel")
        payload = call["json"]
        self.assertEqual(payload["type"], "nuclei_vuln")
        self.assertEqual(payload["task_id"], str(tid))
        self.assertEqual(payload["scope_id"], "")
        self.assertIsNone(payload["scope_data"])
        self.assertEqual(payload["task_data"]["status"], "done")
        self.assertEqual(payload["task_data"]["end_time"], "2026-11-18 20:05:00")
        self.assertEqual(payload["summary"]["total"], 1)
        self.assertEqual(payload["summary"]["severity_counts"]["critical"], 1)
        self.assertEqual(payload["nuclei_results"][0]["template_id"], "cve-2026-1")


class SyncDeduplicationAndLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().arl
        self.logger = MagicMock()
        self.summary_pushes = []
        self.nuclei_pushes = []

        app_pkg = types.ModuleType("app")
        app_pkg.__path__ = []
        utils_pkg = types.ModuleType("app.utils")
        utils_pkg.__path__ = []
        push_mod = types.ModuleType("app.utils.push")
        push_mod.nuclei_vuln_push = lambda **kwargs: self.nuclei_pushes.append(kwargs) or True
        monitor_diff_mod = types.ModuleType("app.utils.monitor_diff")
        monitor_diff_mod.log_monitor_diff_summary = lambda task_id: None
        helpers_pkg = types.ModuleType("app.helpers")
        helpers_pkg.__path__ = []
        helpers_pkg.get_ip_domain_list = lambda t: ([], [])
        helpers_pkg.update_scope_domain_status = lambda *a, **kw: None
        scope_mod = types.ModuleType("app.helpers.scope")
        scope_mod.validate_task_scope = lambda target, scope_id: self.db.asset_scope.find_one({"_id": ObjectId(scope_id)})
        modules_mod = types.ModuleType("app.modules")
        modules_mod.ScopeValidationError = RuntimeError
        modules_mod.TaskSyncStatus = types.SimpleNamespace(RUNNING="running", DEFAULT="default", ERROR="error")
        services_pkg = types.ModuleType("app.services")
        services_pkg.__path__ = []
        sync_mod = types.ModuleType("app.services.syncAsset")
        task_scope_sync_mod = types.ModuleType("app.services.task_scope_sync")

        utils_pkg.conn_db = self.db.__getitem__
        utils_pkg.get_logger = lambda: self.logger
        utils_pkg.curr_date = lambda: "2026-11-18 21:00:00"
        utils_pkg.curr_date_obj = lambda: datetime(2026, 11, 18, 21, 0)
        utils_pkg.to_datetime_obj = lambda val, fallback_oid=None: val if isinstance(val, datetime) else datetime(2026, 11, 18, 21, 0)
        utils_pkg.message_push = lambda **kwargs: self.summary_pushes.append(kwargs)
        utils_pkg.push = push_mod
        utils_pkg.monitor_diff = monitor_diff_mod
        app_pkg.utils = utils_pkg
        app_pkg.helpers = helpers_pkg
        app_pkg.services = services_pkg
        app_pkg.modules = modules_mod

        service_fusion_mod = types.ModuleType("app.services.service_fusion")
        self._patcher = patch.dict(
            sys.modules,
            {
                "app": app_pkg,
                "app.utils": utils_pkg,
                "app.utils.push": push_mod,
                "app.utils.monitor_diff": monitor_diff_mod,
                "app.helpers": helpers_pkg,
                "app.helpers.scope": scope_mod,
                "app.modules": modules_mod,
                "app.services": services_pkg,
                "app.services.service_fusion": service_fusion_mod,
                "app.services.syncAsset": sync_mod,
                "app.services.task_scope_sync": task_scope_sync_mod,
            },
        )
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

        sf_spec = importlib.util.spec_from_file_location("app.services.service_fusion", ROOT / "app/services/service_fusion.py")
        sf_loaded = importlib.util.module_from_spec(sf_spec)
        sf_spec.loader.exec_module(sf_loaded)
        sys.modules["app.services.service_fusion"] = sf_loaded
        services_pkg.service_fusion = sf_loaded

        sync_env = sync_mod.__dict__
        sync_env.update(copy=copy, re=re, ObjectId=ObjectId, utils=utils_pkg, conn=self.db.__getitem__, logger=self.logger)
        _load_nodes("app/services/syncAsset.py", sync_env, ["SyncAsset", "sync_asset"])
        services_pkg.sync_asset = sync_env["sync_asset"]
        self.sync_asset = sync_env["sync_asset"]

        guarded_env = task_scope_sync_mod.__dict__
        guarded_env.update(
            ObjectId=ObjectId,
            utils=utils_pkg,
            ScopeValidationError=modules_mod.ScopeValidationError,
            TaskSyncStatus=modules_mod.TaskSyncStatus,
            validate_task_scope=scope_mod.validate_task_scope,
        )
        _load_nodes("app/services/task_scope_sync.py", guarded_env, ["sync_task_to_scope"])
        self.sync_task_to_scope = guarded_env["sync_task_to_scope"]

        common_env = dict(utils=utils_pkg, services=services_pkg, ObjectId=ObjectId, logger=self.logger, contextmanager=contextmanager)
        _load_nodes("app/services/commonTask.py", common_env, ["CommonTask"])
        self.common_cls = common_env["CommonTask"]

    def test_sync_asset_pushes_only_newly_discovered_nuclei_results(self):
        scope_id = str(self.db.asset_scope.insert_one({"name": "监控组"}).inserted_id)
        t1 = str(self.db.task.insert_one({"name": "mon-1", "status": "done"}).inserted_id)
        t2 = str(self.db.task.insert_one({"name": "mon-2", "status": "done"}).inserted_id)

        # 第一次扫描：发现 12 条漏洞（超过 max_record_asset_count=10，验证不被截断）
        for i in range(12):
            self.db.nuclei_result.insert_one({
                "task_id": t1,
                "template_id": f"cve-{i}",
                "target": f"https://a.example.com:{8000 + i}",
                "vuln_severity": "low" if i < 11 else "critical",
            })

        self.sync_asset(t1, scope_id, update_flag=True, push_flag=True, task_name="mon-1")
        self.assertEqual(len(self.summary_pushes), 1)
        self.assertEqual(len(self.nuclei_pushes), 1)
        self.assertEqual(len(self.nuclei_pushes[0]["results"]), 12)
        self.assertEqual(self.db.asset_nuclei_result.count_documents({"scope_id": scope_id}), 12)

        # 第二次监控重扫：1 条存量重复 + 1 条全新漏洞
        self.summary_pushes.clear()
        self.nuclei_pushes.clear()
        self.db.nuclei_result.insert_many([
            {"task_id": t2, "template_id": "cve-0", "target": "https://a.example.com:8000", "vuln_severity": "low"},
            {"task_id": t2, "template_id": "cve-new", "target": "https://a.example.com:9000", "vuln_severity": "high"},
        ])
        self.sync_asset(t2, scope_id, update_flag=True, push_flag=True, task_name="mon-2")
        self.assertEqual(len(self.nuclei_pushes), 1)
        self.assertEqual([x["template_id"] for x in self.nuclei_pushes[0]["results"]], ["cve-new"])

        # 第三次监控重扫：全部为存量漏洞 -> 不再推送 nuclei_vuln
        self.nuclei_pushes.clear()
        t3 = str(self.db.task.insert_one({"name": "mon-3", "status": "done"}).inserted_id)
        self.db.nuclei_result.insert_one(
            {"task_id": t3, "template_id": "cve-new", "target": "https://a.example.com:9000", "vuln_severity": "high"}
        )
        self.sync_asset(t3, scope_id, update_flag=True, push_flag=True, task_name="mon-3")
        self.assertEqual(self.nuclei_pushes, [])

    def test_unscoped_task_deferred_push_includes_all_nuclei_results_and_runs_after_done(self):
        tid = str(self.db.task.insert_one({"name": "unscoped", "target": "example.com", "status": "running", "end_time": "-"}).inserted_id)
        for i in range(15):
            self.db.nuclei_result.insert_one({
                "task_id": tid,
                "template_id": f"tmpl-{i}",
                "target": "https://example.com",
                "vuln_severity": "high",
            })
        self.db.vuln.insert_one({"task_id": tid, "target": "https://example.com", "vul_name": "weak-pass"})

        common = self.common_cls(tid)
        common.options = {"nuclei_scan": True}
        common.sync_asset(push_flag=False)
        # 尚未落库 DONE 前不得提前推送
        self.assertEqual(self.summary_pushes, [])
        self.assertEqual(self.nuclei_pushes, [])

        self.db.task.update_one({"_id": ObjectId(tid)}, {"$set": {"status": "done", "end_time": "2026-11-18 21:00:00"}})
        common.dispatch_completion_notifications()

        self.assertEqual(len(self.summary_pushes), 1)
        self.assertEqual(self.summary_pushes[0]["asset_counter"]["nuclei_result"], 15)
        self.assertEqual(self.summary_pushes[0]["asset_counter"]["vuln"], 1)
        self.assertEqual(self.summary_pushes[0]["update_counter"], {})
        self.assertEqual(len(self.nuclei_pushes), 1)
        self.assertEqual(len(self.nuclei_pushes[0]["results"]), 15)
        self.assertEqual(self.nuclei_pushes[0]["scope_id"], "")

    def test_manual_sync_remains_silent(self):
        scope_id = str(self.db.asset_scope.insert_one({"name": "组1", "domain_array": ["example.com"]}).inserted_id)
        tid = str(self.db.task.insert_one({"name": "manual", "target": "www.example.com", "status": "done"}).inserted_id)
        self.db.nuclei_result.insert_one({"task_id": tid, "template_id": "cve-x", "target": "https://www.example.com", "vuln_severity": "critical"})

        self.assertTrue(self.sync_task_to_scope(tid, scope_id))
        self.assertEqual(self.summary_pushes, [])
        self.assertEqual(self.nuclei_pushes, [])
        self.assertEqual(self.db.asset_nuclei_result.count_documents({"scope_id": scope_id}), 1)

    def test_risk_cruising_executes_nuclei_before_common_run_and_pushes_after_done(self):
        # 通过 AST 验证 RiskCruising.work 与 RiskCruising.run 调用顺序
        tree = ast.parse((ROOT / "app/tasks/poc.py").read_text())
        cls_node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "RiskCruising")
        work_node = next(n for n in cls_node.body if isinstance(n, ast.FunctionDef) and n.name == "work")
        run_node = next(n for n in cls_node.body if isinstance(n, ast.FunctionDef) and n.name == "run")

        work_calls = [ast.unparse(n) for n in ast.walk(work_node) if isinstance(n, ast.Call)]
        nuclei_idx = next(i for i, s in enumerate(work_calls) if "nuclei_scan" in s)
        common_idx = next(i for i, s in enumerate(work_calls) if "common_run" in s)
        self.assertLess(nuclei_idx, common_idx)
        self.assertTrue(any("common_run(push_flag=False)" in s for s in work_calls))

        run_calls = [ast.unparse(n) for n in ast.walk(run_node) if isinstance(n, ast.Call)]
        done_idx = next(i for i, s in enumerate(run_calls) if "TaskStatus.DONE" in s)
        end_idx = next(i for i, s in enumerate(run_calls) if "'end_time'" in s or '"end_time"' in s)
        push_idx = next(i for i, s in enumerate(run_calls) if "dispatch_completion_notifications" in s)
        self.assertLess(done_idx, push_idx)
        self.assertLess(end_idx, push_idx)

    def test_domain_ip_and_add_site_tasks_defer_push_until_done(self):
        for rel_path, cls_name, meth_name in [
            ("app/tasks/domain.py", "DomainTask", "_run_phases"),
            ("app/tasks/ip.py", "IPTask", "_run_phases"),
            ("app/tasks/asset_site.py", "AddAssetSiteTask", "work"),
        ]:
            tree = ast.parse((ROOT / rel_path).read_text())
            cls_node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == cls_name)
            fn_node = next(n for n in cls_node.body if isinstance(n, ast.FunctionDef) and n.name == meth_name)
            calls = [ast.unparse(n) for n in ast.walk(fn_node) if isinstance(n, ast.Call)]
            self.assertTrue(
                any("push_flag=False" in c for c in calls),
                f"{cls_name}.{meth_name} 应先以 push_flag=False 完成同步",
            )
            if rel_path != "app/tasks/asset_site.py":
                done_idx = next(i for i, c in enumerate(calls) if "TaskStatus.DONE" in c)
                push_idx = next(i for i, c in enumerate(calls) if "dispatch_completion_notifications" in c)
                self.assertLess(done_idx, push_idx)

    def test_notification_exception_does_not_fail_completed_task(self):
        tid = str(self.db.task.insert_one({"name": "err-notify", "target": "example.com", "status": "done"}).inserted_id)
        common = self.common_cls(tid)
        common.options = {"nuclei_scan": True}
        common.sync_asset(push_flag=False)
        with patch.object(common, "_push_task_result_only", side_effect=RuntimeError("smtp down")):
            common.dispatch_completion_notifications()  # 不得向上抛出


class MigrationAndConfigTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().arl
        app_pkg = types.ModuleType("app")
        app_pkg.__path__ = []
        config_mod = types.ModuleType("app.config")
        config_mod.clear_calls = 0
        config_mod.bump_calls = 0
        config_mod.clear_system_config_cache = lambda: setattr(config_mod, "clear_calls", config_mod.clear_calls + 1)
        config_mod.bump_system_config_version = lambda: setattr(config_mod, "bump_calls", config_mod.bump_calls + 1)
        app_pkg.config = config_mod

        self._patcher = patch.dict(sys.modules, {"app": app_pkg, "app.config": config_mod})
        self._patcher.start()
        self.addCleanup(self._patcher.stop)

        self.config_mod = config_mod
        self.env = {"conn_db": self.db.__getitem__}
        _load_nodes("app/utils/arlupdate.py", self.env, ["migrate_nuclei_push_options"])

    def test_migrate_nuclei_push_options_is_one_shot_and_respects_manual_opt_out(self):
        self.db.system_config.insert_one({
            "_id": "general_config",
            "push_options": ["task_complete", "asset_site"],
        })
        self.env["migrate_nuclei_push_options"]()

        cfg = self.db.system_config.find_one({"_id": "general_config"})
        self.assertIn("nuclei_vuln", cfg["push_options"])
        self.assertEqual(cfg["nuclei_push_severities"], ["critical", "high", "medium", "low"])
        self.assertEqual(self.config_mod.clear_calls, 1)
        self.assertEqual(self.config_mod.bump_calls, 1)

        # 管理员手动取消勾选 nuclei_vuln 后，再次重启迁移不得强行复活
        self.db.system_config.update_one(
            {"_id": "general_config"},
            {"$set": {"push_options": ["task_complete"]}},
        )
        self.env["migrate_nuclei_push_options"]()
        cfg_after = self.db.system_config.find_one({"_id": "general_config"})
        self.assertEqual(cfg_after["push_options"], ["task_complete"])

    def test_system_config_general_get_and_post_nuclei_push_fields(self):
        from flask import Flask
        from flask_restx import Resource

        cfg_ns = types.SimpleNamespace(
            NUCLEI_PUSH_SEVERITIES=["critical", "high", "medium", "low"],
            PUSH_OPTIONS=["task_complete", "nuclei_vuln"],
            CELERY_BROKER_URL="", MONGO_URL="", MONGO_DB="", GEOIP_CITY="", GEOIP_ASN="",
            FOFA_KEY="", FOFA_URL="", FOFA_MAX_PAGE=5, FOFA_PAGE_SIZE=2000,
            SO_SEARCH_COOKIE="", BING_SEARCH_COOKIE="", GITHUB_TOKEN="",
            TYC_ID="", TYC_TOKEN="", PROXY_URL="",
            DOMAIN_BRUTE_CONCURRENT=300, ALT_DNS_CONCURRENT=1500,
            FILE_LEAK_TOP_2k="", DOMAIN_DICT_2W="", AUTH=False, API_KEY="",
            WEB_HOOK_URL="", WEB_HOOK_TOKEN="", DINGDING_SECRET="", DINGDING_ACCESS_TOKEN="",
            FEISHU_WEBHOOK="", FEISHU_SECRET="", WX_WORK_WEBHOOK="", TG_BOT_TOKEN="", TG_CHAT_ID="",
            EMAIL_HOST="", EMAIL_PORT=465, EMAIL_USERNAME="", EMAIL_PASSWORD="", EMAIL_TO="",
            QUERY_PLUGIN_CONFIG={},
        )
        config_mod = sys.modules["app.config"]
        config_mod.Config = cfg_ns
        push_mod = types.ModuleType("app.utils.push")
        push_mod.normalize_nuclei_push_severities = lambda v: [
            s for s in ("critical", "high", "medium", "low", "info") if s in {str(x).lower() for x in (v or [])}
        ]
        utils_pkg = types.ModuleType("app.utils")
        utils_pkg.__path__ = []
        conn_mod = types.ModuleType("app.utils.conn")
        conn_mod.conn_db = self.db.__getitem__
        utils_pkg.conn = conn_mod
        utils_pkg.push = push_mod
        app_pkg = sys.modules["app"]
        app_pkg.utils = utils_pkg

        with patch.dict(
            sys.modules,
            {
                "app.utils": utils_pkg,
                "app.utils.conn": conn_mod,
                "app.utils.push": push_mod,
            },
        ):
            route_env = {
                "ARLResource": Resource,
                "auth": lambda fn: fn,
            }
            tree = ast.parse((ROOT / "app/routes/system_config.py").read_text())
            cls_node = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "GeneralConfig")
            cls_copy = copy.deepcopy(cls_node)
            cls_copy.decorator_list = []
            for m in cls_copy.body:
                if isinstance(m, ast.FunctionDef):
                    m.decorator_list = []
            exec(compile(ast.fix_missing_locations(ast.Module(body=[cls_copy], type_ignores=[])), "system_config", "exec"), route_env)
            res_obj = route_env["GeneralConfig"]()
            got = res_obj.get()
            self.assertEqual(got["code"], 200)
            self.assertEqual(got["data"]["nuclei_push_severities"], ["critical", "high", "medium", "low"])

            app = Flask(__name__)
            with app.test_request_context(
                "/api/system_config/general",
                method="POST",
                json={"push_options": ["nuclei_vuln"], "nuclei_push_severities": ["HIGH", "critical", "bogus"]},
            ):
                posted = res_obj.post()
            self.assertEqual(posted["code"], 200)
            saved = self.db.system_config.find_one({"_id": "general_config"})
            self.assertEqual(saved["push_options"], ["nuclei_vuln"])
            self.assertEqual(saved["nuclei_push_severities"], ["critical", "high"])


if __name__ == "__main__":
    unittest.main()
