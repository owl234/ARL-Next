# -*- coding: utf-8 -*-
"""
OSINT 长耗时任务韧性与设计闭环回归测试：
1. Branch A：TYC JWT 预检、鉴权拦截快速短路、静默截断提示与告警落库
2. Branch B/C：多出口令牌/Cookie/会话隔离、指数退避、粘性切换与公司边界回切、验证码跨出口故障转移、source_synced 归属修正、原位详情补全
3. Branch D1/D2/Pipeline：重启字段白名单、孤儿任务资产组指针清理、MIIT 维度按 query_type 过滤、深度遍历总量封顶、TYC->Queue->MIIT 流水线、断点续跑与 HTTP 路由
"""

import ast
import asyncio
import base64
import importlib.util
import json
import os
import sys
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase
from bson import ObjectId

_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)
_OSINT_DIR = os.path.join(_BACKEND_DIR, "osint_service")
for _p in (_OSINT_DIR, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ymicp  # noqa: E402
from proxy_router import DIRECT_EXIT_ID, ExitCandidate, OsintProxyRouter  # noqa: E402
from clients import tyc_async, job_runner  # noqa: E402
from routes.recon_routes import setup_recon_routes, reconcile_orphan_tasks  # noqa: E402
from task_manager import TaskManager  # noqa: E402


async def _no_sleep(*_args, **_kwargs):
    return None


def _make_jwt(exp_ts):
    header = base64.urlsafe_b64encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode()).decode().rstrip("=")
    payload = base64.urlsafe_b64encode(json.dumps({"exp": exp_ts, "sub": "test"}).encode()).decode().rstrip("=")
    return f"{header}.{payload}.sig"


class _FakeDb:
    def __init__(self, cols):
        self._cols = cols

    def __getitem__(self, name):
        return self._cols[name]


class _FakeInsertResult:
    def __init__(self, inserted_id=None):
        self.inserted_id = inserted_id


class _FakeUpdateResult:
    def __init__(self, matched_count=1, modified_count=1):
        self.matched_count = matched_count
        self.modified_count = modified_count


class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def sort(self, field, direction=1):
        reverse = direction < 0
        self._docs.sort(key=lambda d: str(d.get(field) or ""), reverse=reverse)
        return self

    async def to_list(self, length=None):
        if length is None:
            return list(self._docs)
        return list(self._docs[:length])

    def __aiter__(self):
        self._iter = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._iter)
        except StopIteration:
            raise StopAsyncIteration


class _FakeAsyncCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])

    @staticmethod
    def _matches(doc, filt):
        for k, v in (filt or {}).items():
            if isinstance(v, dict):
                if "$in" in v and doc.get(k) not in v["$in"]:
                    return False
                if "$nin" in v and doc.get(k) in v["$nin"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    def find(self, filt=None, projection=None):
        matched = []
        for d in self.docs:
            if self._matches(d, filt):
                if projection:
                    item = {"_id": d.get("_id")}
                    for k, keep in projection.items():
                        if keep and k in d:
                            item[k] = d[k]
                    matched.append(item)
                else:
                    matched.append(dict(d))
        return _FakeCursor(matched)

    async def find_one(self, filt=None, projection=None):
        for d in self.docs:
            if self._matches(d, filt):
                if projection:
                    item = {"_id": d.get("_id")}
                    for k, keep in projection.items():
                        if keep and k in d:
                            item[k] = d[k]
                    return item
                return dict(d)
        return None

    async def insert_one(self, doc):
        copy_doc = dict(doc)
        copy_doc.setdefault("_id", ObjectId())
        self.docs.append(copy_doc)
        return _FakeInsertResult(copy_doc["_id"])

    async def insert_many(self, docs, ordered=True):
        ids = []
        for d in docs:
            res = await self.insert_one(d)
            ids.append(res.inserted_id)
        return SimpleNamespace(inserted_ids=ids)

    async def update_one(self, filt, update, upsert=False):
        for d in self.docs:
            if self._matches(d, filt):
                for k, v in (update.get("$set") or {}).items():
                    d[k] = v
                for k in (update.get("$unset") or {}).keys():
                    d.pop(k, None)
                return _FakeUpdateResult(1, 1)
        if upsert:
            doc = dict(filt or {})
            for k, v in (update.get("$set") or {}).items():
                doc[k] = v
            doc.setdefault("_id", ObjectId())
            self.docs.append(doc)
            return _FakeUpdateResult(1, 1)
        return _FakeUpdateResult(0, 0)

    async def delete_many(self, filt):
        kept = [d for d in self.docs if not self._matches(d, filt)]
        deleted = len(self.docs) - len(kept)
        self.docs = kept
        return SimpleNamespace(deleted_count=deleted)

    async def count_documents(self, filt):
        return sum(1 for d in self.docs if self._matches(d, filt))


class _FakeSyncCollection:
    def __init__(self, docs=None):
        self.docs = [dict(d) for d in (docs or [])]

    @staticmethod
    def _matches(doc, filt):
        for k, v in (filt or {}).items():
            if isinstance(v, dict):
                if "$in" in v and doc.get(k) not in v["$in"]:
                    return False
                if "$nin" in v and doc.get(k) in v["$nin"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    def find_one(self, filt=None, projection=None):
        for d in self.docs:
            if self._matches(d, filt):
                return dict(d)
        return None

    def insert_one(self, doc):
        copy_doc = dict(doc)
        copy_doc.setdefault("_id", ObjectId())
        self.docs.append(copy_doc)
        return _FakeInsertResult(copy_doc["_id"])

    def update_one(self, filt, update, upsert=False):
        for d in self.docs:
            if self._matches(d, filt):
                for k, v in (update.get("$set") or {}).items():
                    d[k] = v
                for k in (update.get("$unset") or {}).keys():
                    d.pop(k, None)
                return _FakeUpdateResult(1, 1)
        if upsert:
            doc = dict(filt or {})
            for k, v in (update.get("$set") or {}).items():
                doc[k] = v
            doc.setdefault("_id", ObjectId())
            self.docs.append(doc)
            return _FakeUpdateResult(1, 1)
        return _FakeUpdateResult(0, 0)

    def update_many(self, filt, update):
        matched = 0
        for d in self.docs:
            if self._matches(d, filt):
                matched += 1
                for k, v in (update.get("$set") or {}).items():
                    d[k] = v
                for k in (update.get("$unset") or {}).keys():
                    d.pop(k, None)
        return _FakeUpdateResult(matched, matched)


def _extract_icp_symbols(names, env_overrides=None):
    icp_path = Path(_BACKEND_DIR) / "app" / "routes" / "icp.py"
    src = icp_path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=str(icp_path))
    wanted = set(names)
    selected = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in wanted
    ]
    mod = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(mod)

    class _NS:
        @staticmethod
        def route(*_args, **_kwargs):
            return lambda cls: cls

    class _ARLResource:
        pass

    class _TaskStatus:
        WAITING = "waiting"
        RUNNING = "running"
        DONE = "done"
        STOP = "stop"
        ERROR = "error"

    class _ErrorMsg:
        Success = {"code": 200, "message": "success"}
        NotFoundTask = {"code": 404, "message": "task not found"}
        TaskIsRunning = {"code": 409, "message": "task is running"}
        Error = {"code": 500, "message": "error"}

    def _build_ret(err, data=None):
        ret = dict(err)
        if data is not None:
            ret["data"] = data
        return ret

    env = {
        "bson": SimpleNamespace(ObjectId=ObjectId),
        "ns": _NS(),
        "ARLResource": _ARLResource,
        "auth": lambda fn: fn,
        "TaskStatus": _TaskStatus,
        "ErrorMsg": _ErrorMsg,
        "build_ret": _build_ret,
        "curr_date": lambda: "2026-11-16 10:30:00",
        "logger": SimpleNamespace(info=lambda *a, **k: None, warning=lambda *a, **k: None, error=lambda *a, **k: None),
        "conn_db": lambda _name: _FakeSyncCollection(),
        "_request_recon": lambda *_a, **_k: {"code": 200},
    }
    if env_overrides:
        env.update(env_overrides)
    exec(compile(mod, str(icp_path), "exec"), env)
    return env


def _load_sync_tyc_client_cls():
    tyc_path = Path(_BACKEND_DIR) / "app" / "services" / "tycClient.py"
    fake_app = types.ModuleType("app")
    fake_cfg_mod = types.ModuleType("app.config")
    fake_cfg_mod.Config = SimpleNamespace(TYC_ID="gid-1", TYC_TOKEN="tok-1", PROXY_URL="")
    fake_services = types.ModuleType("app.services")
    fake_proxy = types.ModuleType("app.services.proxy_service")
    fake_proxy.resolve_requests_proxies = lambda **_k: None
    fake_proxy.mask_proxy_url_secret = lambda u: str(u)
    fake_proxy.record_osint_exit_event = lambda *a, **k: None
    fake_proxy.resolve_proxy_candidates = lambda **_k: [None]

    spec = importlib.util.spec_from_file_location("app.services.tycClient_under_test", tyc_path)
    mod = importlib.util.module_from_spec(spec)
    sys_stubs = {
        "app": fake_app,
        "app.config": fake_cfg_mod,
        "app.services": fake_services,
        "app.services.proxy_service": fake_proxy,
    }
    with patch.dict(sys.modules, sys_stubs):
        spec.loader.exec_module(mod)
    return mod.TycClient, mod, sys_stubs


class TestTycAuthAndTruncation(unittest.TestCase):
    def test_inspect_tyc_token_expired_and_valid(self):
        now = time.time()
        expired_info = tyc_async.inspect_tyc_token(_make_jwt(now - 3600))
        self.assertTrue(expired_info["is_jwt"])
        self.assertTrue(expired_info["expired"])
        self.assertFalse(expired_info["valid"])
        self.assertTrue(expired_info["expired_at"])

        valid_info = tyc_async.inspect_tyc_token(_make_jwt(now + 3600))
        self.assertTrue(valid_info["is_jwt"])
        self.assertFalse(valid_info["expired"])
        self.assertTrue(valid_info["valid"])

        non_jwt = tyc_async.inspect_tyc_token("opaque-token")
        self.assertFalse(non_jwt["is_jwt"])
        self.assertFalse(non_jwt["expired"])

    def test_auth_required_short_circuits_without_sleep_and_records_truncation(self):
        async def run():
            client = tyc_async.AsyncTycClient("gid-1", "tok-expired")
            recorded_issues = []

            async def _on_issue(label, issue):
                recorded_issues.append((label, issue))

            client.attach_task_hooks(issue_cb=_on_issue)

            sleep_calls = []

            async def _track_sleep(sec, *args, **kwargs):
                sleep_calls.append(sec)

            class _FakeResCtx:
                def __init__(self, status, payload):
                    self.status = status
                    self.headers = {"Content-Type": "application/json"}
                    self._payload = payload

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    return False

                async def text(self):
                    return json.dumps(self._payload)

                async def json(self):
                    return self._payload

            class _FakeSession:
                def __init__(self, *args, **kwargs):
                    pass

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    return False

                def get(self, url, **kwargs):
                    params = kwargs.get("params") or {}
                    p = params.get("pageNum", 1)
                    if p == 1:
                        return _FakeResCtx(200, {
                            "state": "ok",
                            "data": {"itemTotal": 250, "item": [{"domain": "a.qq.com"}, {"domain": "b.qq.com"}]},
                        })
                    return _FakeResCtx(200, {"state": "warn", "message": "请登录以使用完整功能"})

            with patch.object(tyc_async.asyncio, "sleep", side_effect=_track_sleep), \
                 patch.object(tyc_async.aiohttp, "ClientSession", _FakeSession):
                rows = await client.get_icp_record_list("gid-1")

            self.assertEqual([r["domain"] for r in rows], ["a.qq.com", "b.qq.com"])
            # 仅含基础请求/翻页间隔，绝对未触发 15s/30s/45s 无意义重试睡眠
            self.assertIn(1.5, sleep_calls)
            self.assertTrue(all(s < 15 for s in sleep_calls))
            self.assertEqual(len(recorded_issues), 1)
            self.assertTrue(recorded_issues[0][1]["auth_required"])
            self.assertEqual(recorded_issues[0][1]["expected_total"], 250)
            self.assertEqual(recorded_issues[0][1]["fetched"], 2)
            self.assertEqual(len(client.consume_fetch_issues()), 1)
            self.assertEqual(client.consume_fetch_issues(), [])

        asyncio.run(run())

    def test_sync_tyc_client_check_token_detail_rejects_expired_jwt_and_login_state(self):
        TycClient, tyc_mod, sys_stubs = _load_sync_tyc_client_cls()
        c = TycClient()
        c.gid = "gid-1"
        c.token = _make_jwt(time.time() - 120)

        with patch.dict(sys.modules, sys_stubs), patch.object(tyc_mod.requests, "get") as mock_get:
            ok, msg, etype = c.check_token_detail()
        self.assertFalse(ok)
        self.assertEqual(etype, "token_expired")
        self.assertIn("过期", msg)
        mock_get.assert_not_called()

        c.token = _make_jwt(time.time() + 3600)

        class _MockResp:
            status_code = 200
            text = '{"state":"warn","message":"请登录以使用完整功能"}'

            def json(self):
                return {"state": "warn", "message": "请登录以使用完整功能"}

        with patch.dict(sys.modules, sys_stubs), patch.object(tyc_mod.requests, "get", return_value=_MockResp()):
            ok2, _msg2, etype2 = c.check_token_detail()
        self.assertFalse(ok2)
        self.assertEqual(etype2, "token_expired")


class TestProxyIsolationAndBeianFailover(unittest.TestCase):
    def test_exponential_backoff_and_sticky_failover_with_boundary_failback(self):
        router = OsintProxyRouter(bundle={
            "policy": {"mode": "failover", "cooldown_sec": 300, "max_failovers": 2},
            "nodes": [
                {"id": "ecs-1", "name": "Backup-1", "protocol": "http", "proxy_url": "http://192.0.2.10:8080"},
            ],
        })

        # 指数退避: 300 -> 600 -> 1200 -> 1800
        self.assertEqual(router.mark_exit_blocked(DIRECT_EXIT_ID, reason="403"), 300)
        self.assertEqual(router.mark_exit_blocked(DIRECT_EXIT_ID, reason="403"), 600)
        self.assertEqual(router.mark_exit_blocked(DIRECT_EXIT_ID, reason="403"), 1200)
        self.assertEqual(router.mark_exit_blocked(DIRECT_EXIT_ID, reason="403"), 1800)

        # 直连冷却期间切换至 ecs-1 并锁定粘性
        cands = router.get_candidates(sticky=True)
        self.assertEqual([c.exit_id for c in cands], ["ecs-1"])
        router.mark_exit_active("ecs-1")

        # 即使直连过期恢复，sticky=True 仍优先保持在 ecs-1（避免同主体中途回切重跑鉴权）
        router.blocked_exits[DIRECT_EXIT_ID]["until_ts"] = time.time() - 10
        self.assertEqual([c.exit_id for c in router.get_candidates(sticky=True)], ["ecs-1", DIRECT_EXIT_ID])
        # 非 sticky 调用默认仍优先主出口
        self.assertEqual([c.exit_id for c in router.get_candidates(sticky=False)], [DIRECT_EXIT_ID, "ecs-1"])

        # 主体切换边界调用 allow_primary_failback 后，允许重回主出口
        router.allow_primary_failback()
        self.assertEqual([c.exit_id for c in router.get_candidates(sticky=True)], [DIRECT_EXIT_ID, "ecs-1"])

    def test_per_exit_token_isolation_and_detail_captcha_failover(self):
        async def run():
            router = OsintProxyRouter(bundle={
                "policy": {"mode": "failover", "cooldown_sec": 300, "max_failovers": 2},
                "nodes": [
                    {"id": "ecs-1", "name": "Backup-1", "protocol": "http", "proxy_url": "http://192.0.2.11:8080"},
                ],
            })
            client = ymicp.beian()
            client.attach_proxy_router(router)
            client._get_exit_state(DIRECT_EXIT_ID).update({"token": "tok-direct", "token_expire": time.time() + 600, "jsluid": "jsl-direct"})
            client._get_exit_state("ecs-1").update({"token": "tok-ecs", "token_expire": time.time() + 600, "jsluid": "jsl-ecs"})

            self.assertEqual(client.token, "tok-direct")
            await client._handle_exit_failure(
                ExitCandidate(exit_id=DIRECT_EXIT_ID, name="主服务器直连", proxy_url=None),
                reason="触发WAF",
            )
            # 直连态被清空，ecs-1 的令牌与 jsluid 保持不受影响
            self.assertEqual(client.token, "")
            self.assertEqual(client._get_exit_state("ecs-1")["token"], "tok-ecs")
            self.assertEqual(client._get_exit_state("ecs-1")["jsluid"], "jsl-ecs")

            # 测试 getAppAndMiniDetail 在出口 A 403/521 时自动切换至备用出口 B 并续签验证码上下文
            router2 = OsintProxyRouter(bundle={
                "policy": {"mode": "failover", "cooldown_sec": 300, "max_failovers": 2},
                "nodes": [
                    {"id": "ecs-1", "name": "Backup-1", "protocol": "http", "proxy_url": "http://192.0.2.12:8080"},
                ],
            })
            client2 = ymicp.beian()
            client2.attach_proxy_router(router2)
            client2._get_exit_state(DIRECT_EXIT_ID).update({"token": "t-a", "token_expire": time.time() + 600})
            client2._get_exit_state("ecs-1").update({"token": "t-b", "token_expire": time.time() + 600})

            post_proxies = []

            async def fake_check_img(proxy="", **_kwargs):
                return True, f"uuid-{proxy or 'direct'}", "t-b", f"sign-{proxy or 'direct'}", {}

            class _DetailResp:
                def __init__(self, status, payload):
                    self.status = status
                    self._payload = payload

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    return False

                async def json(self):
                    return self._payload

                async def text(self):
                    return json.dumps(self._payload)

            class _FakeSession:
                def __init__(self, proxy=""):
                    self.proxy = proxy
                    self.closed = False
                    self.cookie_jar = SimpleNamespace(filter_cookies=lambda _u: {})

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    return False

                def post(self, url, **kwargs):
                    p = kwargs.get("proxy") or self.proxy
                    post_proxies.append(p)
                    if not p:
                        return _DetailResp(403, {"code": 403, "msg": "blocked"})
                    return _DetailResp(200, {"code": 200, "success": True, "params": {"serviceName": "微信", "dataId": "D1"}})

            with patch.object(client2, "check_img", side_effect=fake_check_img), \
                 patch.object(client2, "get_session", side_effect=lambda proxy="", direct_override=False: _FakeSession(proxy=proxy)), \
                 patch.object(ymicp.config, "captcha", SimpleNamespace(enable=True)), \
                 patch.object(ymicp.asyncio, "sleep", side_effect=_no_sleep):
                ok_d, res = await client2.getAppAndMiniDetail("D1", 6, "u-old", "t-a", "s-old", {})

            self.assertTrue(ok_d)
            self.assertTrue(res.get("success"))
            self.assertEqual(res["params"]["serviceName"], "微信")
            self.assertEqual(post_proxies, ["", "http://192.0.2.12:8080"])
            self.assertTrue(router2.is_exit_blocked(DIRECT_EXIT_ID))

        asyncio.run(run())


class TestPipelineResumeBackfillAndLifecycle(unittest.TestCase):
    def test_upsert_source_synced_not_mislabeled_for_icp_only_merge(self):
        async def run():
            task_obj_id = ObjectId()
            task_id = str(task_obj_id)
            tasks_col = _FakeAsyncCollection([{"_id": task_obj_id, "status": "running"}])
            assets_col = _FakeAsyncCollection()
            fake_db = _FakeDb({"icp_task": tasks_col, "icp_asset": assets_col})
            idx = {}
            doc_sources = {}
            with patch.object(job_runner, "db", fake_db):
                is_new_1 = await job_runner._upsert_task_asset(
                    task_id, "app",
                    {"dataId": "1001", "serviceName": "示例APP", "serviceLicence": "粤B2-1"},
                    "示例科技", idx, source="icp", doc_sources=doc_sources,
                )
                is_new_2 = await job_runner._upsert_task_asset(
                    task_id, "app",
                    {"dataId": "1001", "serviceName": "示例APP", "serviceLicence": "粤B2-1", "version": "2.0"},
                    "示例科技", idx, source="icp", doc_sources=doc_sources,
                )
                self.assertTrue(is_new_1)
                self.assertFalse(is_new_2)
                self.assertEqual(len(assets_col.docs), 1)
                # 同一 ICP 维度的重复更新绝不能误标为 tyc+icp
                self.assertEqual(assets_col.docs[0]["source"], "icp")
                self.assertNotEqual(assets_col.docs[0].get("source_synced"), "tyc+icp")

                # 跨数据源（既有 tyc 资产 + icp 补充）才标记为 tyc+icp
                is_new_3 = await job_runner._upsert_task_asset(
                    task_id, "app",
                    {"dataId": "1002", "appName": "交叉APP", "serviceLicence": "粤B2-2"},
                    "示例科技", idx, source="tyc", doc_sources=doc_sources,
                )
                is_new_4 = await job_runner._upsert_task_asset(
                    task_id, "app",
                    {"dataId": "1002", "serviceName": "交叉APP", "serviceLicence": "粤B2-2"},
                    "示例科技", idx, source="icp", doc_sources=doc_sources,
                )
                self.assertTrue(is_new_3)
                self.assertFalse(is_new_4)
                self.assertEqual(assets_col.docs[1]["source_synced"], "tyc+icp")

        asyncio.run(run())

    def test_tyc_pipeline_filters_miit_caps_companies_and_resumes_from_checkpoint(self):
        async def run():
            task_id = ObjectId()
            task_id_str = str(task_id)
            tasks_col = _FakeAsyncCollection([
                {"_id": task_id, "status": "waiting", "name": "pipeline-test", "query_type": ["invest", "web", "app"]}
            ])
            assets_col = _FakeAsyncCollection()
            syslog_col = _FakeAsyncCollection()
            scope_col = _FakeAsyncCollection()
            cfg_col = _FakeAsyncCollection([
                {"_id": "general_config", "max_traverse_companies": 2, "detail_max_items": 50}
            ])
            collections = {
                "icp_task": tasks_col,
                "icp_asset": assets_col,
                "syslog": syslog_col,
                "asset_scope": scope_col,
                "system_config": cfg_col,
            }
            fake_db = _FakeDb(collections)
            sp_queried = []
            company_calls = []

            client_icp = ymicp.beian()

            async def fake_query(name, sp, page_num, page_size, proxy=""):
                sp_queried.append((name, sp))
                if sp == 1:
                    return True, {"code": 200, "success": True, "params": {"total": 1, "pages": 1, "list": [
                        {"dataId": f"did-{name}", "serviceLicence": "粤B2-APP-1"}
                    ]}}, {"p_uuid": "", "token": "t", "sign": "s", "base_header": {}}
                return True, {"code": 200, "success": True, "params": {"total": 0, "pages": 0, "list": []}}, None

            async def fake_detail(did, sp_type, *_a, **_k):
                return True, {"success": True, "code": 200, "params": {"dataId": did, "serviceName": f"Detail-{did}"}}

            async def fake_invest(gid):
                company_calls.append(("invest", gid))
                if gid == "G0":
                    return [
                        {"id": "G1", "name": "子公司一有限公司", "percent": "100%"},
                        {"id": "G2", "name": "子公司二有限公司", "percent": "100%"},
                    ]
                return []

            async def fake_web(gid):
                company_calls.append(("web", gid))
                return [{"domain": f"{gid.lower()}.example.com", "ym": f"{gid.lower()}.example.com"}]

            async def fake_app(gid):
                return []

            async def fake_app_icp(gid):
                return []

            with patch.object(job_runner, "db", fake_db), \
                 patch.object(job_runner.asyncio, "sleep", side_effect=_no_sleep), \
                 patch.object(ymicp.asyncio, "sleep", side_effect=_no_sleep), \
                 patch.object(ymicp, "beian", return_value=client_icp), \
                 patch.object(client_icp, "_query_beian_page", side_effect=fake_query), \
                 patch.object(client_icp, "getAppAndMiniDetail", side_effect=fake_detail), \
                 patch.object(tyc_async.AsyncTycClient, "get_invest_list", side_effect=fake_invest), \
                 patch.object(tyc_async.AsyncTycClient, "get_icp_record_list", side_effect=fake_web), \
                 patch.object(tyc_async.AsyncTycClient, "get_app_list", side_effect=fake_app), \
                 patch.object(tyc_async.AsyncTycClient, "get_app_icp_record_list", side_effect=fake_app_icp):
                await job_runner.run_tyc_job({
                    "task_id": task_id_str,
                    "gid": "G0",
                    "depth": 2,
                    "query_type": ["invest", "web", "app"],
                    "enable_icp": True,
                    "max_companies": 2,
                    "tyc_id": "id",
                    "tyc_token": _make_jwt(time.time() - 600),  # 过期 JWT -> 产生 warning 日志
                    "company_name": "母公司有限公司",
                })

            task_doc = tasks_col.docs[0]
            self.assertEqual(task_doc["status"], "done")
            # query_type 不含 mapp/kapp，故 MIIT 仅应查 web(0) 和 app(1)，严禁查 mapp(2)/kapp(3)
            queried_sps = {sp for _, sp in sp_queried}
            self.assertTrue(queried_sps <= {0, 1})
            self.assertNotIn(2, queried_sps)
            self.assertNotIn(3, queried_sps)

            # max_traverse_companies=2：G0 + G1，G2 应被上限截断
            invest_gids = [gid for kind, gid in company_calls if kind == "invest"]
            self.assertEqual(invest_gids, ["G0", "G1"])
            self.assertTrue(task_doc["recon_checkpoint"]["completed"])
            self.assertTrue(any("过期" in log["message"] for log in syslog_col.docs))

            # 现在模拟断点续跑 (resume=True)：G0 已完成且在 tyc_done_gids & miit_done_gids，仅 G1 未做
            task_id2 = ObjectId()
            tasks_col2 = _FakeAsyncCollection([
                {
                    "_id": task_id2,
                    "status": "waiting",
                    "name": "resume-test",
                    "is_resumed": True,
                    "recon_checkpoint": {
                        "current_level": 0,
                        "level_gids": ["G0"],
                        "next_gids": ["G1"],
                        "visited_gids": ["G0", "G1"],
                        "gid_to_name": {"G0": "母公司有限公司", "G1": "子公司一有限公司"},
                        "tyc_done_gids": ["G0"],
                        "miit_done_gids": ["G0"],
                        "max_companies_reached": False,
                        "completed": False,
                    },
                }
            ])
            assets_col2 = _FakeAsyncCollection([
                {"_id": ObjectId(), "task_id": str(task_id2), "query_type": "web", "domain": "g0.example.com", "source_synced": "tyc"}
            ])
            collections2 = {
                "icp_task": tasks_col2,
                "icp_asset": assets_col2,
                "syslog": _FakeAsyncCollection(),
                "asset_scope": _FakeAsyncCollection(),
                "system_config": cfg_col,
            }
            fake_db2 = _FakeDb(collections2)
            resumed_gids = []

            async def fake_web2(gid):
                resumed_gids.append(gid)
                return [{"domain": f"{gid.lower()}.example.com", "ym": f"{gid.lower()}.example.com"}]

            with patch.object(job_runner, "db", fake_db2), \
                 patch.object(job_runner.asyncio, "sleep", side_effect=_no_sleep), \
                 patch.object(ymicp.asyncio, "sleep", side_effect=_no_sleep), \
                 patch.object(ymicp, "beian", return_value=client_icp), \
                 patch.object(client_icp, "_query_beian_page", side_effect=fake_query), \
                 patch.object(client_icp, "getAppAndMiniDetail", side_effect=fake_detail), \
                 patch.object(tyc_async.AsyncTycClient, "get_icp_record_list", side_effect=fake_web2):
                await job_runner.run_tyc_job({
                    "task_id": str(task_id2),
                    "gid": "G0",
                    "depth": 2,
                    "query_type": ["web"],
                    "enable_icp": True,
                    "max_companies": 2,
                    "tyc_id": "id",
                    "tyc_token": _make_jwt(time.time() + 3600),
                    "company_name": "母公司有限公司",
                    "resume": True,
                })

            # G0 已在 checkpoint tyc_done_gids 中，不应被重复拉取；仅 G1 被续跑查询
            self.assertEqual(resumed_gids, ["G1"])
            self.assertEqual(tasks_col2.docs[0]["status"], "done")
            self.assertEqual(tasks_col2.docs[0]["statistic"]["web_cnt"], 2)

        asyncio.run(run())

    def test_backfill_details_job_fills_missing_names_and_restores_status(self):
        async def run():
            task_id = ObjectId()
            asset_missing_id = ObjectId()
            asset_filled_id = ObjectId()
            tasks_col = _FakeAsyncCollection([
                {"_id": task_id, "status": "done", "name": "bf-test", "company_name": "测试有限公司"}
            ])
            assets_col = _FakeAsyncCollection([
                {"_id": asset_missing_id, "task_id": str(task_id), "query_type": "app", "dataId": "D-MISS", "serviceName": ""},
                {"_id": asset_filled_id, "task_id": str(task_id), "query_type": "app", "dataId": "D-OK", "serviceName": "已有名称"},
            ])
            syslog_col = _FakeAsyncCollection()
            cfg_col = _FakeAsyncCollection([{"_id": "general_config", "detail_max_items": 100}])
            collections = {
                "icp_task": tasks_col,
                "icp_asset": assets_col,
                "syslog": syslog_col,
                "system_config": cfg_col,
                "asset_scope": _FakeAsyncCollection(),
            }
            fake_db = _FakeDb(collections)
            client_icp = ymicp.beian()
            detail_dids = []

            async def fake_detail(did, sp_type, *_a, **_k):
                detail_dids.append(did)
                return True, {"success": True, "code": 200, "params": {"dataId": did, "serviceName": "补全后的APP", "version": "3.1.0"}}

            with patch.object(job_runner, "db", fake_db), \
                 patch.object(job_runner.asyncio, "sleep", side_effect=_no_sleep), \
                 patch.object(ymicp.asyncio, "sleep", side_effect=_no_sleep), \
                 patch.object(ymicp, "beian", return_value=client_icp), \
                 patch.object(client_icp, "check_img", return_value=(True, "u1", "tok-bf", "s1", {})), \
                 patch.object(client_icp, "getAppAndMiniDetail", side_effect=fake_detail):
                client_icp._get_exit_state(DIRECT_EXIT_ID).update({"token": "tok-bf", "token_expire": time.time() + 600})
                await job_runner.run_backfill_details_job({"task_id": str(task_id), "query_types": ["app"]})

            self.assertEqual(detail_dids, ["D-MISS"])
            self.assertEqual(assets_col.docs[0]["serviceName"], "补全后的APP")
            self.assertEqual(assets_col.docs[0]["appName"], "补全后的APP")
            self.assertEqual(tasks_col.docs[0]["status"], "done")
            self.assertNotIn("detail_backfill_running", tasks_col.docs[0])

        asyncio.run(run())

    def test_restart_whitelist_and_reconcile_clears_scope_updating_pointer(self):
        old_id = ObjectId()
        scope_id = ObjectId()
        cols = {
            "icp_task": _FakeSyncCollection([{
                "_id": old_id,
                "name": "orig",
                "target": "TYC_100",
                "task_type": "tyc",
                "gid": "100",
                "depth": 2,
                "invest_ratio": 51,
                "query_type": ["web"],
                "enable_icp": True,
                "company_name": "测试公司",
                "status": "stop",
                "synced_scope_id": str(scope_id),
                "auto_group_status": "done",
                "auto_group_claim_time": "2026-11-15 00:00:00",
                "auto_group_msg": "legacy",
                "synced_at": "2026-11-15 01:00:00",
                "recon_checkpoint": {"current_level": 1},
                "is_resumed": True,
                "detail_backfill_last_time": "2026-11-15 02:00:00",
            }]),
            "asset_scope": _FakeSyncCollection([{
                "_id": scope_id,
                "synced_icp_task_id": str(old_id),
            }]),
        }
        fake_tyc_mod = types.SimpleNamespace(TycClient=lambda: SimpleNamespace(gid="g", token="t"))
        fake_sys_stubs = {
            "app": types.ModuleType("app"),
            "app.services": types.ModuleType("app.services"),
            "app.services.tycClient": fake_tyc_mod,
        }
        env = _extract_icp_symbols(
            ["_restart_single_icp_task"],
            {"conn_db": lambda n: cols[n], "_request_recon": lambda *_a, **_k: {"code": 200}},
        )
        with patch.dict(sys.modules, fake_sys_stubs):
            ok, reason, _data = env["_restart_single_icp_task"](str(old_id))
        self.assertTrue(ok, reason)
        self.assertEqual(len(cols["icp_task"].docs), 2)
        new_doc = cols["icp_task"].docs[1]
        for forbidden in ("auto_group_status", "auto_group_claim_time", "auto_group_msg", "synced_at", "recon_checkpoint", "is_resumed", "detail_backfill_last_time"):
            self.assertNotIn(forbidden, new_doc)
        self.assertEqual(new_doc["prev_task_id"], str(old_id))

        # Test Flask IcpTaskResume & IcpTaskBackfillDetails
        resumable_id = ObjectId()
        cols2 = {
            "icp_task": _FakeSyncCollection([
                {
                    "_id": resumable_id,
                    "status": "stop",
                    "name": "resumable",
                    "task_type": "tyc",
                    "gid": "200",
                    "query_type": ["web"],
                    "recon_checkpoint": {"completed": False, "tyc_done_gids": ["200"]},
                }
            ]),
            "asset_scope": _FakeSyncCollection(),
        }
        dispatched = []
        fake_flask = types.SimpleNamespace(request=SimpleNamespace(get_json=lambda silent=True: {"query_types": ["app"]}))
        env2 = _extract_icp_symbols(
            ["_build_task_recon_options", "IcpTaskResume", "IcpTaskBackfillDetails"],
            {
                "conn_db": lambda n: cols2[n],
                "_request_recon": lambda act, opt: dispatched.append((act, opt)) or {"code": 200},
            },
        )
        with patch.dict(sys.modules, {"flask": fake_flask, **fake_sys_stubs}):
            r_res = env2["IcpTaskResume"]().post(str(resumable_id))
        self.assertEqual(r_res["code"], 200)
        self.assertEqual(dispatched[0][0], "resume")
        self.assertTrue(dispatched[0][1]["resume"])
        self.assertEqual(cols2["icp_task"].docs[0]["status"], "waiting")

        # 置回 stop 后测试原位详情补全入口
        cols2["icp_task"].docs[0]["status"] = "stop"
        with patch.dict(sys.modules, {"flask": fake_flask}):
            b_res = env2["IcpTaskBackfillDetails"]().post(str(resumable_id))
        self.assertEqual(b_res["code"], 200)
        self.assertEqual(dispatched[1][0], "backfill_details")
        self.assertEqual(dispatched[1][1]["query_types"], ["app"])

    def test_reconcile_calls_scope_sync_and_preserves_resume_flag(self):
        async def run():
            it_id = str(ObjectId())
            wt_id = str(ObjectId())
            tasks_col = _FakeAsyncCollection([
                {"_id": it_id, "status": "running"},
                {"_id": wt_id, "status": "waiting", "name": "resumed-w", "task_type": "icp", "target": "qq.com", "query_type": ["web"], "is_resumed": True, "recon_checkpoint": {"completed": False}},
            ])
            sync_calls = []

            async def fake_sync(tid, st):
                sync_calls.append((tid, st))

            mock_jr = MagicMock()
            mock_jr.db = {"icp_task": tasks_col, "system_config": _FakeAsyncCollection()}
            mock_jr.curr_date = lambda: "2026-11-16 10:30:00"
            mock_jr._sync_scope_after_task_completion = fake_sync
            submitted = []

            with patch.dict(sys.modules, {"clients.job_runner": mock_jr}), \
                 patch("routes.recon_routes.submit_recon_job", side_effect=lambda _tm, opt: submitted.append(opt)), \
                 patch("routes.recon_routes.asyncio.sleep", side_effect=_no_sleep):
                await reconcile_orphan_tasks({"task_manager": TaskManager()})

            self.assertEqual(sync_calls, [(it_id, "stop")])
            self.assertEqual(len(submitted), 1)
            self.assertTrue(submitted[0]["resume"])

        asyncio.run(run())


class TestReconResumeAndBackfillRoutes(AioHTTPTestCase):
    async def get_application(self):
        app = web.Application()
        app["task_manager"] = TaskManager()
        setup_recon_routes(app)
        return app

    async def test_resume_and_backfill_http_endpoints(self):
        tid = str(ObjectId())
        with patch("routes.recon_routes.submit_recon_job") as mock_submit:
            resp = await self.client.post(
                "/api/v1/recon/resume",
                json={"task_id": tid, "type": "tyc", "gid": "9519792"},
            )
            self.assertEqual(resp.status, 200)
            body = await resp.json()
            self.assertEqual(body["code"], 200)
            self.assertTrue(mock_submit.call_args[0][1]["resume"])

            resp2 = await self.client.post(
                "/api/v1/recon/backfill_details",
                json={"task_id": tid, "query_types": ["app"]},
            )
            self.assertEqual(resp2.status, 200)
            body2 = await resp2.json()
            self.assertEqual(body2["code"], 200)
            self.assertEqual(mock_submit.call_args[0][1]["action"], "backfill_details")


class TestOsintBlankAndPendingFixes(unittest.TestCase):
    def test_detail_failover_writes_back_detail_context_and_per_exit_cooldown(self):
        async def run():
            router = OsintProxyRouter(bundle={
                "policy": {"mode": "failover", "cooldown_sec": 300, "max_failovers": 2},
                "nodes": [
                    {"id": "ecs-1", "name": "Backup-1", "protocol": "http", "proxy_url": "http://192.0.2.21:8080"},
                ],
            })
            client = ymicp.beian()
            client.attach_proxy_router(router)

            seen_auth = []

            class _Resp:
                def __init__(self, status, payload):
                    self.status = status
                    self._payload = payload

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    return False

                async def text(self):
                    return json.dumps(self._payload)

            class _Sess:
                def __init__(self, proxy=""):
                    self.proxy = proxy
                    self.closed = False

                async def __aenter__(self):
                    return self

                async def __aexit__(self, *args):
                    return False

                def post(self, _url, **kwargs):
                    p = kwargs.get("proxy") or self.proxy
                    hdrs = kwargs.get("headers") or {}
                    seen_auth.append((p, hdrs.get("uuid"), hdrs.get("sign"), hdrs.get("token")))
                    if not p:
                        return _Resp(403, {"code": 403, "msg": "blocked"})
                    return _Resp(200, {"code": 200, "success": True, "params": {"serviceName": "恢复应用"}})

            async def fake_check_img(proxy="", **_kwargs):
                return True, f"uuid-{proxy or 'direct'}", "tok-backup", f"sign-{proxy or 'direct'}", {}

            detail_ctx = {"p_uuid": "uuid-direct", "token": "tok-direct", "sign": "sign-direct", "base_header": {}, "exit_id": DIRECT_EXIT_ID}
            items_res = {"code": 200, "success": True, "params": {"list": [
                {"dataId": "D1", "serviceLicence": "L1"},
                {"dataId": "D2", "serviceLicence": "L2"},
            ]}}

            with patch.object(client, "check_img", side_effect=fake_check_img), \
                 patch.object(client, "get_session", side_effect=lambda proxy="", direct_override=False: _Sess(proxy=proxy)), \
                 patch.object(ymicp, "config", SimpleNamespace(system=SimpleNamespace(detail_concurrency=1, detail_max_items=20), captcha=SimpleNamespace(enable=True))), \
                 patch.object(ymicp.asyncio, "sleep", side_effect=_no_sleep):
                out = await client._enrich_app_details(items_res, 1, detail_ctx, "")

            # 第一条切至备份出口后，detail_context 被回写为备份出口上下文，第二条直接使用备份凭据一次成功
            self.assertEqual(detail_ctx["exit_id"], "ecs-1")
            self.assertEqual(detail_ctx["sign"], "sign-http://192.0.2.21:8080")
            self.assertEqual(len(seen_auth), 3)
            self.assertEqual(seen_auth[0][0], "")
            self.assertEqual(seen_auth[1], ("http://192.0.2.21:8080", "uuid-http://192.0.2.21:8080", "sign-http://192.0.2.21:8080", "tok-backup"))
            self.assertEqual(seen_auth[2], ("http://192.0.2.21:8080", "uuid-http://192.0.2.21:8080", "sign-http://192.0.2.21:8080", "tok-backup"))
            self.assertEqual([x["serviceName"] for x in out["params"]["list"]], ["恢复应用", "恢复应用"])
            # 仅主出口处于冷却，备用出口仍健康，故全局 _detail_waf_open 保持 False
            client._detail_waf_trip("直连详情限流", exit_id=DIRECT_EXIT_ID)
            self.assertFalse(client._detail_waf_open())

        asyncio.run(run())

    def test_slider_miss_does_not_lock_refresh_streak_into_circuit_break(self):
        async def run():
            client = ymicp.beian()
            refresh_attempts = {"cnt": 0}

            async def fake_check_img(*_args, **_kwargs):
                refresh_attempts["cnt"] += 1
                if refresh_attempts["cnt"] == 1:
                    return False, "滑块匹配失败", "", "", ""
                return True, "u-ok", "t-ok", "s-ok", {}

            async def fake_detail(_did, _st, _u, _t, sign, _hdr, _proxy=""):
                if sign != "s-ok":
                    return True, {"success": False, "code": 500, "msg": "sign expired"}
                return True, {"success": True, "params": {"serviceName": "正常应用"}}

            res = {"code": 200, "success": True, "params": {"list": [
                {"dataId": "d1", "serviceLicence": "L1"},
                {"dataId": "d2", "serviceLicence": "L2"},
                {"dataId": "d3", "serviceLicence": "L3"},
            ]}}

            with patch.object(ymicp, "config", SimpleNamespace(system=SimpleNamespace(detail_concurrency=1, detail_max_items=20), captcha=SimpleNamespace(enable=True))), \
                 patch.object(ymicp.asyncio, "sleep", side_effect=_no_sleep), \
                 patch.object(client, "check_img", side_effect=fake_check_img), \
                 patch.object(client, "getAppAndMiniDetail", side_effect=fake_detail):
                out = await client._enrich_app_details(res, 1, {"p_uuid": "u0", "token": "t0", "sign": "s-stale", "base_header": {}}, "")

            self.assertEqual(refresh_attempts["cnt"], 2)
            self.assertFalse(client._detail_waf_open())
            self.assertEqual(out["params"]["list"][1]["serviceName"], "正常应用")
            self.assertEqual(out["params"]["list"][2]["serviceName"], "正常应用")

        asyncio.run(run())

    def test_tyc_app_merges_app_icp_record_list_and_skips_miit_detail(self):
        async def run():
            task_id = ObjectId()
            tasks_col = _FakeAsyncCollection([
                {"_id": task_id, "status": "waiting", "name": "app-merge", "query_type": ["app"]}
            ])
            assets_col = _FakeAsyncCollection()
            syslog_col = _FakeAsyncCollection()
            cfg_col = _FakeAsyncCollection([{"_id": "general_config", "detail_max_items": 50}])
            fake_db = _FakeDb({
                "icp_task": tasks_col,
                "icp_asset": assets_col,
                "syslog": syslog_col,
                "asset_scope": _FakeAsyncCollection(),
                "system_config": cfg_col,
            })

            client_icp = ymicp.beian()
            detail_called = []

            async def fake_query(_name, sp, _pn, _ps, _proxy=""):
                if sp == 1:
                    return True, {
                        "code": 200, "success": True,
                        "params": {"total": 1, "pages": 1, "list": [
                            {"dataId": "did-wx", "serviceLicence": "粤ICP备09052002号-2A"}
                        ]}
                    }, {"p_uuid": "", "token": "t", "sign": "s", "base_header": {}}
                return True, {"code": 200, "success": True, "params": {"total": 0, "pages": 0, "list": []}}, None

            async def fake_app(_gid):
                return [{"name": "微信", "icon": "https://img.example/wx.png", "classes": "社交", "brief": "即时通讯"}]

            async def fake_app_icp(_gid):
                return [{
                    "serviceName": "微信",
                    "serviceFilingNumber": "粤ICP备09052002号-2A",
                    "examineDate": "2024-03-01",
                    "appIcpRecordDetail": {
                        "icpFilingSubjectInformation": {
                            "organizingName": "深圳市腾讯计算机系统有限公司",
                            "mainLicence": "粤ICP备09052002号",
                        },
                        "contentTypeName": "即时通信",
                    },
                }]

            with patch.object(job_runner, "db", fake_db), \
                 patch.object(job_runner.asyncio, "sleep", side_effect=_no_sleep), \
                 patch.object(ymicp.asyncio, "sleep", side_effect=_no_sleep), \
                 patch.object(ymicp, "beian", return_value=client_icp), \
                 patch.object(client_icp, "_query_beian_page", side_effect=fake_query), \
                 patch.object(client_icp, "getAppAndMiniDetail", side_effect=lambda did, *_: detail_called.append(did)), \
                 patch.object(tyc_async.AsyncTycClient, "get_app_list", side_effect=fake_app), \
                 patch.object(tyc_async.AsyncTycClient, "get_app_icp_record_list", side_effect=fake_app_icp):
                await job_runner.run_tyc_job({
                    "task_id": str(task_id),
                    "gid": "9519792",
                    "depth": 1,
                    "query_type": ["app"],
                    "enable_icp": True,
                    "tyc_id": "id",
                    "tyc_token": _make_jwt(time.time() + 3600),
                    "company_name": "深圳市腾讯计算机系统有限公司",
                })

            self.assertEqual(detail_called, [])
            self.assertEqual(len(assets_col.docs), 1)
            doc = assets_col.docs[0]
            self.assertEqual(doc["serviceName"], "微信")
            self.assertEqual(doc["icon"], "https://img.example/wx.png")
            self.assertEqual(doc["category"], "社交")
            self.assertEqual(doc["serviceLicence"], "粤ICP备09052002号-2A")
            self.assertEqual(doc["mainLicence"], "粤ICP备09052002号")
            self.assertEqual(doc["contentTypeName"], "即时通信")
            self.assertEqual(doc["updateRecordTime"], "2024-03-01")

        asyncio.run(run())

    def test_backfill_details_unlimited_and_deduplicates_against_tyc(self):
        async def run():
            task_id = ObjectId()
            tyc_doc_id = ObjectId()
            miit_dup_id = ObjectId()
            tasks_col = _FakeAsyncCollection([
                {"_id": task_id, "status": "done", "name": "bf-full", "company_name": "测试有限公司", "statistic": {"asset_cnt": 106, "app_cnt": 106}}
            ])
            unnamed_docs = [
                {"_id": miit_dup_id, "task_id": str(task_id), "query_type": "app", "dataId": "D-DUP", "serviceLicence": "LIC-DUP", "mainLicence": "MAIN-DUP", "contentTypeName": "社交", "serviceName": "", "source": "icp"}
            ] + [
                {"_id": ObjectId(), "task_id": str(task_id), "query_type": "app", "dataId": f"D-{i}", "serviceLicence": f"LIC-{i}", "serviceName": "", "source": "icp"}
                for i in range(104)
            ]
            assets_col = _FakeAsyncCollection([
                {"_id": tyc_doc_id, "task_id": str(task_id), "query_type": "app", "name": "重复APP", "serviceName": "重复APP", "icon": "https://ico.test/app.png", "brief": "TYC简介", "source": "tyc"},
                *unnamed_docs,
            ])
            syslog_col = _FakeAsyncCollection()
            cfg_col = _FakeAsyncCollection([{"_id": "general_config", "detail_max_items": 2}])
            fake_db = _FakeDb({
                "icp_task": tasks_col,
                "icp_asset": assets_col,
                "syslog": syslog_col,
                "system_config": cfg_col,
                "asset_scope": _FakeAsyncCollection(),
            })

            client_icp = ymicp.beian()
            queried_dids = []

            async def fake_detail(did, _st, *_a, **_k):
                queried_dids.append(did)
                if did == "D-DUP":
                    return True, {"success": True, "code": 200, "params": {"dataId": did, "serviceName": "重复APP", "mainLicence": "MAIN-DUP", "version": "2.0"}}
                return True, {"success": True, "code": 200, "params": {"dataId": did, "serviceName": f"App-{did}"}}

            with patch.object(job_runner, "db", fake_db), \
                 patch.object(job_runner.asyncio, "sleep", side_effect=_no_sleep), \
                 patch.object(ymicp.asyncio, "sleep", side_effect=_no_sleep), \
                 patch.object(ymicp, "config", SimpleNamespace(system=SimpleNamespace(detail_concurrency=2, detail_max_items=2, progress_log_interval_sec=30), captcha=SimpleNamespace(enable=False))), \
                 patch.object(ymicp, "beian", return_value=client_icp), \
                 patch.object(client_icp, "getAppAndMiniDetail", side_effect=fake_detail):
                client_icp._get_exit_state(DIRECT_EXIT_ID).update({"token": "tok-bf", "token_expire": time.time() * 1000 + 600000})
                await job_runner.run_backfill_details_job({"task_id": str(task_id), "query_types": ["app"]})

            # 1. 即使系统配置 detail_max_items=2，手动原位补全仍应全量处理 105 条待补全记录
            self.assertEqual(len(queried_dids), 105)
            # 2. 重复命名记录与既有 TYC 记录自动合并去重，最终应保留 105 条不重复 APP
            self.assertEqual(len(assets_col.docs), 105)
            merged_tyc = next(d for d in assets_col.docs if d["_id"] == tyc_doc_id)
            self.assertEqual(merged_tyc["icon"], "https://ico.test/app.png")
            self.assertEqual(merged_tyc["brief"], "TYC简介")
            self.assertEqual(merged_tyc["serviceLicence"], "LIC-DUP")
            self.assertEqual(merged_tyc["mainLicence"], "MAIN-DUP")
            self.assertEqual(merged_tyc["contentTypeName"], "社交")
            self.assertEqual(merged_tyc["version"], "2.0")
            self.assertEqual(merged_tyc["source_synced"], "tyc+icp")
            # 3. 统计计数应重算为 105
            self.assertEqual(tasks_col.docs[0]["status"], "done")
            self.assertEqual(tasks_col.docs[0]["statistic"]["app_cnt"], 105)
            self.assertEqual(tasks_col.docs[0]["statistic"]["asset_cnt"], 105)

        asyncio.run(run())

    def test_normalize_icp_asset_item_extracts_nested_tyc_details(self):
        src = Path(_BACKEND_DIR, "app", "routes", "icp.py").read_text(encoding="utf-8")
        tree = ast.parse(src)
        fn_node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "normalize_icp_asset_item")
        env = {}
        exec(compile(ast.fix_missing_locations(ast.Module(body=[fn_node], type_ignores=[])), "icp.py", "exec"), env)
        normalize_fn = env["normalize_icp_asset_item"]

        out = normalize_fn({
            "query_type": "app",
            "appName": "示例应用",
            "appLogo": "https://img.example/logo.png",
            "appIcpRecordDetail": {
                "icpFilingSubjectInformation": {
                    "organizingName": "示例科技有限公司",
                    "mainLicence": "京ICP备20240001号",
                    "natureName": "企业",
                },
                "icpFilingServiceInformation": {
                    "serviceLicence": "京ICP备20240001号-1A",
                    "contentTypeName": "工具",
                },
            },
        })
        self.assertEqual(out["serviceName"], "示例应用")
        self.assertEqual(out["unitName"], "示例科技有限公司")
        self.assertEqual(out["mainLicence"], "京ICP备20240001号")
        self.assertEqual(out["serviceLicence"], "京ICP备20240001号-1A")
        self.assertEqual(out["contentTypeName"], "工具")
        self.assertEqual(out["companyType"], "企业")
        self.assertEqual(out["icon"], "https://img.example/logo.png")

    def test_sentinel_empty_detail_does_not_overwrite_dataid_or_break(self):
        async def run():
            client = ymicp.beian()
            client._get_exit_state(DIRECT_EXIT_ID).update({"token": "tok-s", "token_expire": time.time() * 1000 + 600000})
            items_res = {
                "code": 200,
                "success": True,
                "params": {
                    "list": [
                        {"dataId": 10001 + i, "serviceType": 6, "serviceLicence": f"LIC-{i}", "serviceName": ""}
                        for i in range(6)
                    ]
                },
            }

            async def fake_sentinel_detail(*_a, **_k):
                return True, {
                    "code": 200,
                    "success": True,
                    "msg": "操作成功",
                    "params": {
                        "contentTypeName": "",
                        "dataId": 0,
                        "mainLicence": "",
                        "natureName": "企业",
                        "serviceLicence": "",
                        "serviceName": "",
                        "serviceType": 0,
                        "unitName": "",
                        "updateRecordTime": None,
                    },
                }

            progress_msgs = []

            async def fake_prog(_sp, _stage, msg):
                progress_msgs.append(msg)

            client.attach_task_hooks(progress_cb=fake_prog)
            try:
                with patch.object(ymicp.asyncio, "sleep", side_effect=_no_sleep), \
                     patch.object(ymicp, "config", SimpleNamespace(system=SimpleNamespace(detail_concurrency=2, detail_max_items=0, progress_log_interval_sec=30), captcha=SimpleNamespace(enable=False))), \
                     patch.object(client, "getAppAndMiniDetail", side_effect=fake_sentinel_detail):
                    out = await client._enrich_app_details(items_res, 1, {"p_uuid": "", "token": "tok-s", "sign": "s", "base_header": {}}, "", max_items=0)
            finally:
                client.attach_task_hooks()

            prm = out["params"]
            self.assertFalse(bool(prm.get("_detail_circuit_break")))
            self.assertEqual(prm["_detail_missing"], 6)
            for idx, item in enumerate(prm["list"]):
                self.assertEqual(item["dataId"], 10001 + idx)
                self.assertEqual(item["serviceType"], 6)
            self.assertTrue(any("成功 0 条" in m for m in progress_msgs), msg=progress_msgs)

        asyncio.run(run())

    def test_backfill_refreshes_stale_and_zero_dataid_by_licence(self):
        async def run():
            task_id = ObjectId()
            id_zero = ObjectId()
            id_stale = ObjectId()
            tasks_col = _FakeAsyncCollection([
                {"_id": task_id, "status": "done", "name": "bf-refresh", "company_name": "腾讯测绘主体", "statistic": {"asset_cnt": 2, "app_cnt": 2}}
            ])
            assets_col = _FakeAsyncCollection([
                {"_id": id_zero, "task_id": str(task_id), "query_type": "app", "dataId": 0, "serviceType": 0, "serviceLicence": "粤B2-TEST-1A", "unitName": "腾讯测绘主体", "serviceName": "", "source": "icp"},
                {"_id": id_stale, "task_id": str(task_id), "query_type": "app", "dataId": 700001, "serviceType": 6, "serviceLicence": "粤B2-TEST-2A", "unitName": "腾讯测绘主体", "serviceName": "", "source": "icp"},
            ])
            syslog_col = _FakeAsyncCollection()
            cfg_col = _FakeAsyncCollection([{"_id": "general_config"}])
            fake_db = _FakeDb({
                "icp_task": tasks_col,
                "icp_asset": assets_col,
                "syslog": syslog_col,
                "system_config": cfg_col,
                "asset_scope": _FakeAsyncCollection(),
            })

            client_icp = ymicp.beian()
            client_icp._get_exit_state(DIRECT_EXIT_ID).update({"token": "tok-rf", "token_expire": time.time() * 1000 + 600000})

            async def fake_query_page(keyword, sp, page_num, page_size, proxy=""):
                mapping = {
                    "粤B2-TEST-1A": {"dataId": 880001, "serviceType": 6, "serviceLicence": "粤B2-TEST-1A", "serviceName": "", "unitName": "腾讯测绘主体"},
                    "粤B2-TEST-2A": {"dataId": 880002, "serviceType": 6, "serviceLicence": "粤B2-TEST-2A", "serviceName": "", "unitName": "腾讯测绘主体"},
                }
                item = mapping.get(keyword)
                return True, {"code": 200, "success": True, "params": {"total": 1 if item else 0, "list": [item] if item else []}}, {}

            async def fake_detail(did, _st, *_a, **_k):
                if did == 700001:
                    return True, {"code": 200, "success": True, "params": {"dataId": 0, "serviceType": 0, "serviceName": ""}}
                if did == 880001:
                    return True, {"code": 200, "success": True, "params": {"dataId": 880001, "serviceType": 6, "serviceName": "刷新后App1", "mainLicence": "粤B2-TEST"}}
                if did == 880002:
                    return True, {"code": 200, "success": True, "params": {"dataId": 880002, "serviceType": 6, "serviceName": "刷新后App2", "mainLicence": "粤B2-TEST"}}
                return False, {}

            with patch.object(job_runner, "db", fake_db), \
                 patch.object(job_runner.asyncio, "sleep", side_effect=_no_sleep), \
                 patch.object(ymicp.asyncio, "sleep", side_effect=_no_sleep), \
                 patch.object(ymicp, "config", SimpleNamespace(system=SimpleNamespace(detail_concurrency=2, detail_max_items=0, progress_log_interval_sec=30), captcha=SimpleNamespace(enable=False))), \
                 patch.object(ymicp, "beian", return_value=client_icp), \
                 patch.object(client_icp, "_query_beian_page", side_effect=fake_query_page), \
                 patch.object(client_icp, "getAppAndMiniDetail", side_effect=fake_detail):
                await job_runner.run_backfill_details_job({"task_id": str(task_id), "query_types": ["app"]})

            by_id = {d["_id"]: d for d in assets_col.docs}
            self.assertEqual(by_id[id_zero]["serviceName"], "刷新后App1")
            self.assertEqual(by_id[id_zero]["dataId"], 880001)
            self.assertEqual(by_id[id_stale]["serviceName"], "刷新后App2")
            self.assertEqual(by_id[id_stale]["dataId"], 880002)
            self.assertEqual(tasks_col.docs[0]["status"], "done")

        asyncio.run(run())


if __name__ == "__main__":
    unittest.main()
