import asyncio
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from bson import ObjectId

# 确保可导入 backend/osint_service 模块
_TEST_DIR = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR = os.path.dirname(_TEST_DIR)
_OSINT_DIR = os.path.join(_BACKEND_DIR, "osint_service")
for _p in (_OSINT_DIR, _BACKEND_DIR):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import ymicp  # noqa: E402
from clients import tyc_async, job_runner  # noqa: E402


class _FakeInsertManyResult:
    def __init__(self, inserted_ids):
        self.inserted_ids = inserted_ids


class _FakeInsertOneResult:
    def __init__(self, inserted_id):
        self.inserted_id = inserted_id


class _FakeCollection:
    def __init__(self, docs=None):
        self.docs = list(docs or [])
        self.statistic_history = []

    @staticmethod
    def _matches(doc, filt):
        for k, v in (filt or {}).items():
            if isinstance(v, dict):
                if "$in" in v and doc.get(k) not in v["$in"]:
                    return False
            elif doc.get(k) != v:
                return False
        return True

    async def find_one(self, filt, projection=None):
        for d in self.docs:
            if self._matches(d, filt):
                if projection:
                    return {k: d[k] for k in projection if k in d}
                return dict(d)
        return None

    async def insert_one(self, doc):
        copy_doc = dict(doc)
        copy_doc.setdefault("_id", ObjectId())
        self.docs.append(copy_doc)
        return _FakeInsertOneResult(copy_doc["_id"])

    async def insert_many(self, docs, ordered=False):
        ids = []
        for d in docs:
            copy_doc = dict(d)
            copy_doc.setdefault("_id", ObjectId())
            self.docs.append(copy_doc)
            ids.append(copy_doc["_id"])
        return _FakeInsertManyResult(ids)

    async def update_one(self, filt, update):
        for d in self.docs:
            if self._matches(d, filt):
                if "$set" in update:
                    d.update(update["$set"])
                    if "statistic" in update["$set"]:
                        self.statistic_history.append(dict(update["$set"]["statistic"]))
                return SimpleNamespace(modified_count=1, matched_count=1)
        return SimpleNamespace(modified_count=0, matched_count=0)

    async def delete_one(self, filt):
        for idx, d in enumerate(self.docs):
            if self._matches(d, filt):
                self.docs.pop(idx)
                return SimpleNamespace(deleted_count=1)
        return SimpleNamespace(deleted_count=0)


class _FakeDB:
    def __init__(self, collections=None):
        self._cols = dict(collections or {})

    def __getitem__(self, name):
        return self._cols.setdefault(name, _FakeCollection())


def _make_system_cfg(**kwargs):
    defaults = {
        "detail_concurrency": 1,
        "detail_max_items": 60,
        "progress_log_interval_sec": 30,
        "progress_log_page_step": 5,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


async def _no_sleep(_sec):
    return None


class YmicpProgressAndDetailTests(unittest.IsolatedAsyncioTestCase):
    async def test_getbeian_throttled_heartbeat_incremental_pages_and_short_task_quiet(self):
        client = ymicp.beian()
        sys_cfg = _make_system_cfg(progress_log_page_step=5, progress_log_interval_sec=30)
        fake_cfg = SimpleNamespace(system=sys_cfg, captcha=SimpleNamespace(enable=False))

        async def fast_sleep(_sec):
            return None

        # 场景1：12页长列表 -> 应按第1、5、10、12页节流播报，且每页立即触发 page_cb
        pages_persisted = []
        progress_logs = []

        async def fake_query_12(_name, _sp, page_num, _page_size, _proxy=""):
            return (
                True,
                {
                    "code": 200,
                    "success": True,
                    "params": {
                        "total": 12 * 26,
                        "pages": 12,
                        "list": [{"domain": f"p{page_num}.example.com"}],
                    },
                },
                {"p_uuid": "", "token": "t", "sign": "s", "base_header": {}},
            )

        async def on_page(sp, items, page_num, total_pages):
            pages_persisted.append((page_num, total_pages, items[0]["domain"]))

        async def on_progress(sp, stage, message):
            progress_logs.append((stage, message))

        client.attach_task_hooks(progress_cb=on_progress, page_cb=on_page)

        clock = {"t": 100.0}

        def mono():
            clock["t"] += 1.0
            return clock["t"]

        with patch.object(ymicp, "config", fake_cfg), \
             patch.object(ymicp.asyncio, "sleep", side_effect=fast_sleep), \
             patch.object(ymicp.time, "monotonic", side_effect=mono), \
             patch.object(client, "_query_beian_page", side_effect=fake_query_12):
            ok, res = await client.getbeian("腾讯", 0, "", "")

        self.assertTrue(ok)
        self.assertEqual(len(pages_persisted), 12)
        self.assertEqual(len(res["params"]["list"]), 12)
        # 仅第 1 / 5 / 10 / 12 页发出 4 条进度日志
        self.assertEqual(len(progress_logs), 4)
        self.assertIn("1/12", progress_logs[0][1])
        self.assertIn("5/12", progress_logs[1][1])
        self.assertIn("10/12", progress_logs[2][1])
        self.assertIn("12/12", progress_logs[3][1])

        # 场景2：3页短任务(<30s) -> 零中间进度刷屏
        pages_persisted.clear()
        progress_logs.clear()

        async def fake_query_3(_name, _sp, page_num, _page_size, _proxy=""):
            return (
                True,
                {
                    "code": 200,
                    "success": True,
                    "params": {
                        "total": 60,
                        "pages": 3,
                        "list": [{"domain": f"s{page_num}.example.com"}],
                    },
                },
                {"p_uuid": "", "token": "t", "sign": "s", "base_header": {}},
            )

        with patch.object(ymicp, "config", fake_cfg), \
             patch.object(ymicp.asyncio, "sleep", side_effect=fast_sleep), \
             patch.object(ymicp.time, "monotonic", side_effect=mono), \
             patch.object(client, "_query_beian_page", side_effect=fake_query_3):
            ok, _res = await client.getbeian("短任务公司", 0, "", "")

        self.assertTrue(ok)
        self.assertEqual(len(pages_persisted), 3)
        self.assertEqual(progress_logs, [])

    async def test_getbeian_time_heartbeat_and_cooperative_stop(self):
        client = ymicp.beian()
        sys_cfg = _make_system_cfg(progress_log_page_step=5, progress_log_interval_sec=30)
        fake_cfg = SimpleNamespace(system=sys_cfg, captcha=SimpleNamespace(enable=False))

        async def fast_sleep(_sec):
            return None

        progress_logs = []
        pages_seen = []

        async def fake_query(_name, _sp, page_num, _page_size, _proxy=""):
            return (
                True,
                {
                    "code": 200,
                    "success": True,
                    "params": {
                        "total": 100,
                        "pages": 4,
                        "list": [{"domain": f"t{page_num}.example.com"}],
                    },
                },
                {"p_uuid": "", "token": "t", "sign": "s", "base_header": {}},
            )

        clock = {"t": 10.0}

        def slow_mono():
            # 每次调用推进 35s，即使总页数 <= 5 也应触发按时间心跳
            clock["t"] += 35.0
            return clock["t"]

        client.attach_task_hooks(
            progress_cb=lambda sp, st, msg: progress_logs.append(msg),
            page_cb=lambda sp, items, pn, tp: pages_seen.append(pn),
        )
        with patch.object(ymicp, "config", fake_cfg), \
             patch.object(ymicp.asyncio, "sleep", side_effect=fast_sleep), \
             patch.object(ymicp.time, "monotonic", side_effect=slow_mono), \
             patch.object(client, "_query_beian_page", side_effect=fake_query):
            ok, _res = await client.getbeian("慢响应公司", 0, "", "")

        self.assertTrue(ok)
        self.assertEqual(pages_seen, [1, 2, 3, 4])
        self.assertGreaterEqual(len(progress_logs), 1)

        # 协同停止：第 2 页落库后停止 -> 不再请求第 3 页，也不进入详情阶段
        pages_seen.clear()
        enrich_called = {"cnt": 0}

        async def fake_enrich(*_args, **_kwargs):
            enrich_called["cnt"] += 1
            return _args[0]

        client.attach_task_hooks(
            page_cb=lambda sp, items, pn, tp: pages_seen.append(pn),
            should_stop_cb=lambda: len(pages_seen) >= 2,
        )
        with patch.object(ymicp, "config", fake_cfg), \
             patch.object(ymicp.asyncio, "sleep", side_effect=fast_sleep), \
             patch.object(client, "_query_beian_page", side_effect=fake_query), \
             patch.object(client, "_enrich_app_details", side_effect=fake_enrich):
            ok, res = await client.getbeian("停机公司", 1, "", "")

        self.assertTrue(ok)
        self.assertEqual(pages_seen, [1, 2])
        self.assertTrue(res["params"].get("_stopped"))
        self.assertEqual(enrich_called["cnt"], 0)

    async def test_enrich_skips_known_and_caps_details(self):
        client = ymicp.beian()
        sys_cfg = _make_system_cfg(detail_concurrency=1, detail_max_items=3)
        fake_cfg = SimpleNamespace(system=sys_cfg, captcha=SimpleNamespace(enable=False))

        async def fast_sleep(_sec):
            return None

        items = [
            {"dataId": "has_name_1", "serviceLicence": "L-HN1", "serviceName": "已有名称APP"},
            {"dataId": "known_1", "serviceLicence": "LIC-TYC-1", "serviceName": ""},
            {"dataId": "known_2", "serviceLicence": "LIC-TYC-2", "serviceName": ""},
        ] + [
            {"dataId": f"unk_{i}", "serviceLicence": f"LIC-UNK-{i}", "serviceName": ""}
            for i in range(6)
        ]
        result = {"code": 200, "success": True, "params": {"list": list(items)}}
        queried_ids = []
        detail_cb_items = []

        async def fake_detail(dataId, *_args, **_kwargs):
            queried_ids.append(dataId)
            return True, {"success": True, "params": {"serviceName": f"Name-{dataId}", "mainLicence": f"MAIN-{dataId}"}}

        client.token = "tok"
        client.token_expire = 9999999999999
        client.attach_task_hooks(
            skip_detail_fn=lambda sp, it: it.get("serviceLicence") in {"LIC-TYC-1", "LIC-TYC-2"},
            detail_cb=lambda sp, enriched: detail_cb_items.extend(enriched),
        )

        with patch.object(ymicp, "config", fake_cfg), \
             patch.object(ymicp.asyncio, "sleep", side_effect=fast_sleep), \
             patch.object(client, "getAppAndMiniDetail", side_effect=fake_detail):
            out = await client._enrich_app_details(result, 1, {"p_uuid": "", "token": "tok", "sign": "s", "base_header": {}}, "", target_name="测试")

        self.assertEqual(queried_ids, ["unk_0", "unk_1", "unk_2"])
        self.assertEqual(len(out["params"]["list"]), len(items))
        self.assertEqual(out["params"]["_detail_skipped_known"], 3)
        self.assertEqual(out["params"]["_detail_skipped_cap"], 3)
        self.assertEqual(out["params"]["_detail_target_count"], 3)
        self.assertEqual(out["params"]["_detail_missing"], 3)
        self.assertFalse(out["params"].get("_detail_circuit_break", False))
        self.assertEqual([x["dataId"] for x in detail_cb_items], ["unk_0", "unk_1", "unk_2"])

    async def test_enrich_single_check_img_refresh_and_5_failure_circuit_break(self):
        client = ymicp.beian()
        sys_cfg = _make_system_cfg(detail_concurrency=1, detail_max_items=20)
        fake_cfg = SimpleNamespace(system=sys_cfg, captcha=SimpleNamespace(enable=True))

        async def fast_sleep(_sec):
            return None

        # 场景1：sign 过期引发单次刷新 -> 刷新一次 check_img 后成功，第2条直接复用新 sign
        refresh_calls = {"cnt": 0}

        async def fake_check_img(*_args, **_kwargs):
            refresh_calls["cnt"] += 1
            return True, "fresh_uuid", "fresh_tok", "fresh_sign", {"User-Agent": "ua"}

        async def fake_detail_recover(dataId, serviceType, p_uuid, token, sign, base_header, proxy=""):
            if sign == "stale_sign":
                return True, {"success": False, "code": 500, "msg": "sign invalid"}
            return True, {"success": True, "params": {"serviceName": f"App-{dataId}"}}

        res1 = {"code": 200, "success": True, "params": {"list": [
            {"dataId": "d1", "serviceLicence": "L1"},
            {"dataId": "d2", "serviceLicence": "L2"},
        ]}}

        with patch.object(ymicp, "config", fake_cfg), \
             patch.object(ymicp.asyncio, "sleep", side_effect=fast_sleep), \
             patch.object(client, "check_img", side_effect=fake_check_img), \
             patch.object(client, "getAppAndMiniDetail", side_effect=fake_detail_recover):
            out1 = await client._enrich_app_details(
                res1, 1,
                {"p_uuid": "stale_u", "token": "t", "sign": "stale_sign", "base_header": {}},
                "",
            )

        self.assertEqual(refresh_calls["cnt"], 1)
        self.assertEqual(out1["params"]["list"][0]["serviceName"], "App-d1")
        self.assertEqual(out1["params"]["list"][1]["serviceName"], "App-d2")
        self.assertFalse(client._detail_waf_open())

        # 场景2：详情接口持续失败 -> 仅刷新 1 次 check_img，连续失败 5 次即熔断，绝不刷穿 12 条
        client2 = ymicp.beian()
        refresh_calls["cnt"] = 0
        detail_attempts = {"cnt": 0}

        async def fake_detail_always_fail(*_args, **_kwargs):
            detail_attempts["cnt"] += 1
            return True, {"success": False, "code": 500, "msg": "backend error"}

        items_12 = [{"dataId": f"f_{i}", "serviceLicence": f"FL-{i}"} for i in range(12)]
        res2 = {"code": 200, "success": True, "params": {"list": items_12}}

        with patch.object(ymicp, "config", fake_cfg), \
             patch.object(ymicp.asyncio, "sleep", side_effect=fast_sleep), \
             patch.object(client2, "check_img", side_effect=fake_check_img), \
             patch.object(client2, "getAppAndMiniDetail", side_effect=fake_detail_always_fail):
            out2 = await client2._enrich_app_details(
                res2, 1,
                {"p_uuid": "u0", "token": "t0", "sign": "s0", "base_header": {}},
                "",
            )

        self.assertEqual(refresh_calls["cnt"], 1)
        # 5次失败：第1条试1次+刷新后重试1次，其余4条各1次 -> 合计6次远小于12条
        self.assertLessEqual(detail_attempts["cnt"], 7)
        self.assertTrue(client2._detail_waf_open())
        self.assertTrue(out2["params"].get("_detail_circuit_break"))
        self.assertEqual(len(out2["params"]["list"]), 12)


class TycPaginationProgressTests(unittest.IsolatedAsyncioTestCase):
    async def test_fetch_all_pages_throttled_progress_and_stop(self):
        client = tyc_async.AsyncTycClient(gid="9519792", token="tok")
        client.page_size = 100
        sys_cfg = _make_system_cfg(progress_log_page_step=5, progress_log_interval_sec=30)
        fake_cfg = SimpleNamespace(system=sys_cfg)

        logs = []
        client.attach_task_hooks(progress_cb=lambda scene, msg: logs.append((scene, msg)))

        async def fake_req(_method, _path, json_data=None, params=None, max_retries=3):
            pn = (params or json_data)["pageNum"]
            return {"itemTotal": 700, "item": [{"id": f"{pn}_{i}"} for i in range(100)]}

        clock = {"t": 1.0}

        def fast_mono():
            clock["t"] += 1.0
            return clock["t"]

        with patch.object(tyc_async, "config", fake_cfg), \
             patch.object(tyc_async.asyncio, "sleep", side_effect=_no_sleep), \
             patch.object(tyc_async.time, "monotonic", side_effect=fast_mono), \
             patch.object(client, "_request", side_effect=fake_req):
            items = await client.get_icp_record_list("9519792")

        self.assertEqual(len(items), 700)
        # 第1、5、7页发出3条节流日志
        self.assertEqual(len(logs), 3)
        self.assertEqual(logs[0][0], "网站备案")
        self.assertIn("1/7", logs[0][1])
        self.assertIn("5/7", logs[1][1])
        self.assertIn("7/7", logs[2][1])

        # 短列表(2页)安静不刷屏
        logs.clear()

        async def fake_short(_method, _path, json_data=None, params=None, max_retries=3):
            pn = (params or json_data)["pageNum"]
            return {"count": 150, "items": [{"id": f"{pn}_{i}"} for i in range(100 if pn == 1 else 50)]}

        with patch.object(tyc_async, "config", fake_cfg), \
             patch.object(tyc_async.asyncio, "sleep", side_effect=_no_sleep), \
             patch.object(tyc_async.time, "monotonic", side_effect=fast_mono), \
             patch.object(client, "_request", side_effect=fake_short):
            short_items = await client.get_app_list("9519792")

        self.assertEqual(len(short_items), 150)
        self.assertEqual(logs, [])

        # should_stop_cb 在第 2 页后中断
        pages_seen = []

        async def fake_stop_req(_method, _path, json_data=None, params=None, max_retries=3):
            pn = (params or json_data)["pageNum"]
            pages_seen.append(pn)
            return {"itemTotal": 1000, "miniProgramIcpRecordList": [{"id": f"m_{pn}"}]}

        client.attach_task_hooks(should_stop_cb=lambda: len(pages_seen) >= 2)
        with patch.object(tyc_async, "config", fake_cfg), \
             patch.object(tyc_async.asyncio, "sleep", side_effect=_no_sleep), \
             patch.object(client, "_request", side_effect=fake_stop_req):
            partial = await client.get_mini_program_list("9519792")

        self.assertEqual(pages_seen, [1, 2])
        self.assertEqual(len(partial), 2)


class JobRunnerIncrementalAndDedupTests(unittest.IsolatedAsyncioTestCase):
    async def test_enrichment_incremental_page_persistence_cross_source_dedup_and_cap_syslog(self):
        task_id = str(ObjectId())
        tyc_named_doc_id = ObjectId()
        tyc_named_doc = {
            "_id": tyc_named_doc_id,
            "task_id": task_id,
            "query_type": "app",
            "appName": "王者助手",
            "serviceName": "王者助手",
            "unitName": "腾讯科技有限公司",
            "source": "tyc",
        }

        tasks_col = _FakeCollection([{"_id": ObjectId(task_id), "status": "running"}])
        assets_col = _FakeCollection([tyc_named_doc])
        syslog_col = _FakeCollection()
        fake_db = _FakeDB({
            "icp_task": tasks_col,
            "icp_asset": assets_col,
            "syslog": syslog_col,
        })

        task_assets_index = {
            "web": {},
            "app": {"王者助手": tyc_named_doc_id},
            "mapp": {},
            "wechat": {},
            "weibo": {},
            "kapp": {},
            "invest": {},
        }
        known_named_lics = {"app": {"粤b2-tyc-known"}, "mapp": set(), "kapp": set()}
        counts = {"web": 0, "app": 1, "mapp": 0, "kapp": 0, "wechat": 0, "weibo": 0, "invest": 0}
        total_assets_holder = [1]

        async def insert_syslog(level, title, message):
            await syslog_col.insert_one({"task_id": task_id, "level": level, "title": title, "message": message})

        async def update_stats():
            await tasks_col.update_one(
                {"_id": ObjectId(task_id)},
                {"$set": {"statistic": {"asset_cnt": total_assets_holder[0], **counts}}},
            )

        myicp = ymicp.beian()
        myicp.token = "tok"
        myicp.token_expire = 9999999999999

        # 配置上限为 2 条未知 APP 详情查询，心跳步长 2 页
        sys_cfg = _make_system_cfg(detail_concurrency=1, detail_max_items=2, progress_log_page_step=2)
        fake_cfg = SimpleNamespace(system=sys_cfg, captcha=SimpleNamespace(enable=False))

        # 跟踪在网站第 2 页拉取前数据库是否已经写入第 1 页网站资产（证明逐页增量落库）
        web_p1_persisted_before_p2 = {"ok": False}

        async def fake_query_beian_page(_name, sp, page_num, _page_size, _proxy=""):
            if sp == 0:  # web: 3页
                if page_num == 2:
                    web_docs = [d for d in assets_col.docs if d.get("query_type") == "web"]
                    web_p1_persisted_before_p2["ok"] = (
                        len(web_docs) == 1
                        and web_docs[0]["domain"] == "w1.qq.com"
                        and len(tasks_col.statistic_history) >= 1
                    )
                return (
                    True,
                    {"code": 200, "success": True, "params": {"total": 3 * 26, "pages": 3, "list": [{"domain": f"w{page_num}.qq.com"}]}},
                    {"p_uuid": "", "token": "tok", "sign": "s", "base_header": {}},
                )
            if sp == 1:  # app: 1条已在TYC命名(跳过详情), 1条将与无证TYC记录按名跨源去重合并, 1条新APP, 1条超上限跳过详情
                return (
                    True,
                    {
                        "code": 200,
                        "success": True,
                        "params": {
                            "total": 4,
                            "pages": 1,
                            "list": [
                                {"dataId": "d_skip", "serviceLicence": "粤B2-TYC-KNOWN"},
                                {"dataId": "d_merge", "serviceLicence": "粤B2-MERGE"},
                                {"dataId": "d_new", "serviceLicence": "粤B2-NEWAPP"},
                                {"dataId": "d_cap", "serviceLicence": "粤B2-CAPPED"},
                            ],
                        },
                    },
                    {"p_uuid": "", "token": "tok", "sign": "s", "base_header": {}},
                )
            # 小程序与快应用返回无记录
            return True, {"code": 200, "success": True, "params": {"total": 0, "pages": 0, "list": []}}, None

        detail_queried_ids = []

        async def fake_detail(dataId, *_args, **_kwargs):
            detail_queried_ids.append(dataId)
            if dataId == "d_merge":
                return True, {"success": True, "params": {"serviceName": "王者助手", "mainLicence": "粤ICP备100号"}}
            if dataId == "d_new":
                return True, {"success": True, "params": {"serviceName": "腾讯会议", "mainLicence": "粤ICP备200号"}}
            return True, {"success": False, "code": 500, "msg": "unexpected"}

        with patch.object(job_runner, "db", fake_db), \
             patch.object(job_runner.asyncio, "sleep", side_effect=_no_sleep), \
             patch.object(ymicp, "config", fake_cfg), \
             patch.object(ymicp.asyncio, "sleep", side_effect=_no_sleep), \
             patch.object(myicp, "_query_beian_page", side_effect=fake_query_beian_page), \
             patch.object(myicp, "getAppAndMiniDetail", side_effect=fake_detail):
            await job_runner._run_company_icp_enrichment(
                task_id=task_id,
                company_name="腾讯科技有限公司",
                myicp=myicp,
                task_assets_index=task_assets_index,
                counts=counts,
                total_assets_holder=total_assets_holder,
                insert_syslog=insert_syslog,
                update_stats=update_stats,
                proxy="",
                known_named_lics=known_named_lics,
            )

        # 1. 第 1 页在拉取第 2 页前已落库且刷新了 statistic
        self.assertTrue(web_p1_persisted_before_p2["ok"])
        # 2. 跳过 TYC 已知及超上限条目，仅查询 d_merge 与 d_new
        self.assertEqual(detail_queried_ids, ["d_merge", "d_new"])
        # 3. 跨源同名去重删除孤立记录，APP 最终共 4 条：王者助手(合并了粤B2-MERGE)、粤B2-TYC-KNOWN、腾讯会议、粤B2-CAPPED
        app_docs = [d for d in assets_col.docs if d.get("query_type") == "app"]
        self.assertEqual(len(app_docs), 4)
        self.assertEqual(counts["app"], 4)
        merged_tyc = next(d for d in app_docs if d["_id"] == tyc_named_doc_id)
        self.assertEqual(merged_tyc["serviceLicence"], "粤B2-MERGE")
        self.assertEqual(merged_tyc["mainLicence"], "粤ICP备100号")
        self.assertEqual(merged_tyc["source_synced"], "tyc+icp")
        new_app = next(d for d in app_docs if d.get("serviceLicence") == "粤B2-NEWAPP")
        self.assertEqual(new_app["serviceName"], "腾讯会议")
        # 4. 超上限截断说明出现在运行日志
        msgs = [d["message"] for d in syslog_col.docs]
        self.assertTrue(any("受单批详情上限控制跳过 1 条详情查询" in m for m in msgs))

    async def test_run_icp_job_incremental_page_and_detail_writeback(self):
        task_id = ObjectId()
        tasks_col = _FakeCollection([{
            "_id": task_id,
            "status": "waiting",
            "target": "测试公司",
            "query_type": ["app"],
        }])
        assets_col = _FakeCollection()
        syslog_col = _FakeCollection()
        fake_db = _FakeDB({
            "icp_task": tasks_col,
            "icp_asset": assets_col,
            "syslog": syslog_col,
            "system_config": _FakeCollection(),
            "task_scope": _FakeCollection(),
        })

        client = ymicp.beian()
        client.token = "tok"
        client.token_expire = 9999999999999
        sys_cfg = _make_system_cfg(detail_concurrency=1, detail_max_items=60)
        fake_cfg = SimpleNamespace(system=sys_cfg, captcha=SimpleNamespace(enable=False))

        page1_inserted_before_page2 = {"ok": False}

        async def fake_query(_name, _sp, page_num, _page_size, _proxy=""):
            if page_num == 2:
                page1_inserted_before_page2["ok"] = (
                    len(assets_col.docs) == 1
                    and assets_col.docs[0]["serviceLicence"] == "LIC-1"
                    and len(tasks_col.statistic_history) >= 1
                )
            return (
                True,
                {"code": 200, "success": True, "params": {"total": 52, "pages": 2, "list": [{"dataId": f"id-{page_num}", "serviceLicence": f"LIC-{page_num}"}]}},
                {"p_uuid": "", "token": "tok", "sign": "s", "base_header": {}},
            )

        async def fake_detail(dataId, *_args, **_kwargs):
            return True, {"success": True, "params": {"serviceName": f"App-{dataId}", "contentTypeName": "工具"}}

        with patch.object(ymicp, "config", fake_cfg), \
             patch.object(ymicp.asyncio, "sleep", side_effect=_no_sleep), \
             patch.object(client, "_query_beian_page", side_effect=fake_query), \
             patch.object(client, "getAppAndMiniDetail", side_effect=fake_detail), \
             patch.object(ymicp, "beian", return_value=client), \
             patch.object(job_runner, "db", fake_db), \
             patch.object(job_runner.asyncio, "sleep", side_effect=_no_sleep):
            await job_runner.run_icp_job({
                "task_id": str(task_id),
                "target": "测试公司",
                "query_type": ["app"],
            })

        self.assertTrue(page1_inserted_before_page2["ok"])
        self.assertEqual(len(assets_col.docs), 2)
        self.assertEqual(sorted(d["serviceName"] for d in assets_col.docs), ["App-id-1", "App-id-2"])
        self.assertEqual(tasks_col.docs[0]["status"], "done")
        self.assertEqual(tasks_col.docs[0]["statistic"]["app_cnt"], 2)

    async def test_run_icp_job_cooperative_stop_preserves_partial_and_keeps_stop_status(self):
        task_id = ObjectId()
        tasks_col = _FakeCollection([{
            "_id": task_id,
            "status": "waiting",
            "target": "停止测试公司",
            "query_type": ["web"],
        }])
        assets_col = _FakeCollection()
        fake_db = _FakeDB({
            "icp_task": tasks_col,
            "icp_asset": assets_col,
            "syslog": _FakeCollection(),
            "system_config": _FakeCollection(),
            "task_scope": _FakeCollection(),
        })

        client = ymicp.beian()
        sys_cfg = _make_system_cfg(detail_concurrency=1, detail_max_items=60)
        fake_cfg = SimpleNamespace(system=sys_cfg, captcha=SimpleNamespace(enable=False))
        pages_queried = []

        async def fake_query(_name, _sp, page_num, _page_size, _proxy=""):
            pages_queried.append(page_num)
            return (
                True,
                {
                    "code": 200,
                    "success": True,
                    "params": {"total": 100, "pages": 4, "list": [{"domain": f"s{page_num}.example.com"}]},
                },
                {"p_uuid": "", "token": "t", "sign": "s", "base_header": {}},
            )

        async def stop_after_page2_sleep(_sec):
            # 第2页已完成逐页落库，在页间休眠时模拟用户点击停止任务
            if len(pages_queried) >= 2:
                tasks_col.docs[0]["status"] = "stop"

        with patch.object(ymicp, "config", fake_cfg), \
             patch.object(asyncio, "sleep", side_effect=stop_after_page2_sleep), \
             patch.object(client, "_query_beian_page", side_effect=fake_query), \
             patch.object(ymicp, "beian", return_value=client), \
             patch.object(job_runner, "db", fake_db):
            await job_runner.run_icp_job({
                "task_id": str(task_id),
                "target": "停止测试公司",
                "query_type": ["web"],
            })

        self.assertEqual(pages_queried, [1, 2])
        self.assertEqual(len(assets_col.docs), 2)
        self.assertEqual(tasks_col.docs[0]["status"], "stop")

    async def test_run_tyc_job_wires_known_lics_and_exits_cleanly_on_stop(self):
        task_id = ObjectId()
        tasks_col = _FakeCollection([{
            "_id": task_id,
            "status": "waiting",
            "target": "TYC_9519792",
            "company_name": "腾讯科技有限公司",
        }])
        assets_col = _FakeCollection()
        fake_db = _FakeDB({
            "icp_task": tasks_col,
            "icp_asset": assets_col,
            "syslog": _FakeCollection(),
            "system_config": _FakeCollection(),
            "task_scope": _FakeCollection(),
        })

        client = ymicp.beian()
        client.token = "tok"
        client.token_expire = 9999999999999
        sys_cfg = _make_system_cfg(detail_concurrency=1, detail_max_items=60)
        fake_cfg = SimpleNamespace(system=sys_cfg, captcha=SimpleNamespace(enable=False))

        detail_calls = []
        app_pages_queried = []

        async def fake_query(_name, sp, page_num, _page_size, _proxy=""):
            if sp == 1:
                app_pages_queried.append(page_num)
                if page_num == 2:
                    tasks_col.docs[0]["status"] = "stop"
                return (
                    True,
                    {"code": 200, "success": True, "params": {"total": 100, "pages": 4, "list": [{"dataId": f"did-{page_num}", "serviceLicence": "粤B2-KNOWN-APP"}]}},
                    {"p_uuid": "", "token": "tok", "sign": "s", "base_header": {}},
                )
            return True, {"code": 200, "success": True, "params": {"total": 0, "pages": 0, "list": []}}, None

        async def fake_app_list(_gid):
            return [{"appName": "QQ", "serviceLicence": "粤B2-KNOWN-APP"}]

        with patch.object(ymicp, "config", fake_cfg), \
             patch.object(ymicp.asyncio, "sleep", side_effect=_no_sleep), \
             patch.object(client, "_query_beian_page", side_effect=fake_query), \
             patch.object(client, "getAppAndMiniDetail", side_effect=lambda did, *_: detail_calls.append(did)), \
             patch.object(ymicp, "beian", return_value=client), \
             patch.object(tyc_async.AsyncTycClient, "get_app_list", side_effect=fake_app_list), \
             patch.object(tyc_async.AsyncTycClient, "get_app_icp_record_list", return_value=[]), \
             patch.object(job_runner, "db", fake_db), \
             patch.object(job_runner.asyncio, "sleep", side_effect=_no_sleep):
            await job_runner.run_tyc_job({
                "task_id": str(task_id),
                "gid": "9519792",
                "depth": 1,
                "query_type": ["app"],
                "enable_icp": True,
                "tyc_id": "id",
                "tyc_token": "tok",
                "company_name": "腾讯科技有限公司",
            })

        self.assertEqual(app_pages_queried, [1, 2])
        self.assertEqual(detail_calls, [])
        # 中止后绝不能把 status 改回 done
        self.assertEqual(tasks_col.docs[0]["status"], "stop")

