import os
import sys
import unittest
from unittest.mock import MagicMock, patch

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Bypass mongo lookups during initial config import
import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999

# Prevent pymongo connection attempt during utils import
import pymongo
pymongo.MongoClient = MagicMock()

from app.config import Config
Config.AUTH = False

import openpyxl
import openpyxl.writer.excel
openpyxl.writer.excel.save_virtual_workbook = MagicMock()
import types
import importlib.machinery

class AutoModule(types.ModuleType):
    def __getattr__(self, name):
        return MagicMock()

xing_pkg = AutoModule('xing')
xing_pkg.__path__ = []
xing_pkg.__spec__ = importlib.machinery.ModuleSpec('xing', None, is_package=True)
sys.modules['xing'] = xing_pkg

for sub in ['conf', 'core', 'utils', 'plugins']:
    sm = AutoModule(f'xing.{sub}')
    sm.__path__ = []
    sm.__spec__ = importlib.machinery.ModuleSpec(f'xing.{sub}', None, is_package=True)
    sys.modules[f'xing.{sub}'] = sm
    setattr(xing_pkg, sub, sm)

import bson
from bson import ObjectId

# 模拟数据库集合
class MockCollection:
    def __init__(self, data=None):
        self.data = data if data is not None else []
        self.updated = []

    def _matches(self, item, filter_query):
        if not filter_query:
            return True
        for k, v in filter_query.items():
            if k == "$or":
                if not any(self._matches(item, sub_q) for sub_q in v):
                    return False
                continue
            val = item.get(k)
            if isinstance(v, dict):
                if "$in" in v and val not in v["$in"]:
                    return False
                if "$ne" in v and val == v["$ne"]:
                    return False
                if "$exists" in v:
                    exists = k in item and item[k] is not None
                    if bool(v["$exists"]) != exists:
                        return False
                if "$gt" in v and not (val is not None and val > v["$gt"]):
                    return False
            elif val != v:
                return False
        return True

    def find_one(self, filter_query, *args, **kwargs):
        for item in self.data:
            if self._matches(item, filter_query):
                return dict(item)
        return None

    def find(self, filter_query=None, *args, **kwargs):
        return [dict(item) for item in self.data if self._matches(item, filter_query)]

    def insert_one(self, doc):
        d = dict(doc)
        if '_id' not in d:
            d['_id'] = ObjectId()
        self.data.append(d)
        res = MagicMock()
        res.inserted_id = d['_id']
        return res

    def _apply_update(self, item, update_doc):
        if "$set" in update_doc:
            for sk, sv in update_doc["$set"].items():
                item[sk] = sv
        if "$unset" in update_doc:
            for uk in update_doc["$unset"].keys():
                item.pop(uk, None)

    def update_one(self, filter_query, update_doc):
        self.updated.append((filter_query, update_doc))
        for item in self.data:
            if self._matches(item, filter_query):
                self._apply_update(item, update_doc)
                return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)

    def update_many(self, filter_query, update_doc):
        self.updated.append((filter_query, update_doc))
        modified = 0
        for item in self.data:
            if self._matches(item, filter_query):
                self._apply_update(item, update_doc)
                modified += 1
        return MagicMock(modified_count=modified)

    def delete_one(self, filter_query):
        for idx, item in enumerate(self.data):
            if self._matches(item, filter_query):
                self.data.pop(idx)
                return MagicMock(deleted_count=1)
        return MagicMock(deleted_count=0)

    def delete_many(self, filter_query):
        before = len(self.data)
        self.data = [item for item in self.data if not self._matches(item, filter_query)]
        return MagicMock(deleted_count=before - len(self.data))


class TestSmoothAssetUpdate(unittest.TestCase):
    """
    主体资产平滑更新与双指针机制单元测试
    """

    def test_heal_stale_updating_icp_tasks_done(self):
        """测试已完成任务自动晋升为 synced_icp_task_id"""
        from app.utils.arlupdate import heal_stale_updating_icp_tasks

        scope_id = ObjectId()
        task_done_id = ObjectId()

        mock_scope_col = MockCollection([
            {
                "_id": scope_id,
                "synced_icp_task_id": "old_task_id",
                "updating_icp_task_id": str(task_done_id)
            }
        ])
        mock_task_col = MockCollection([
            {
                "_id": task_done_id,
                "status": "done"
            }
        ])

        def fake_conn_db(table):
            if table == 'asset_scope':
                return mock_scope_col
            elif table == 'icp_task':
                return mock_task_col
            return MockCollection()

        with patch('app.utils.arlupdate.conn_db', side_effect=fake_conn_db):
            heal_stale_updating_icp_tasks()

            scope = mock_scope_col.find_one({"_id": scope_id})
            self.assertEqual(scope.get("synced_icp_task_id"), str(task_done_id))
            self.assertNotIn("updating_icp_task_id", scope)

    def test_heal_stale_updating_icp_tasks_error(self):
        """测试异常任务自动清理 updating_icp_task_id 并保留原主指针"""
        from app.utils.arlupdate import heal_stale_updating_icp_tasks

        scope_id = ObjectId()
        task_err_id = ObjectId()

        mock_scope_col = MockCollection([
            {
                "_id": scope_id,
                "synced_icp_task_id": "old_task_id",
                "updating_icp_task_id": str(task_err_id)
            }
        ])
        mock_task_col = MockCollection([
            {
                "_id": task_err_id,
                "status": "error",
                "error_msg": "API quota exceeded"
            }
        ])

        def fake_conn_db(table):
            if table == 'asset_scope':
                return mock_scope_col
            elif table == 'icp_task':
                return mock_task_col
            return MockCollection()

        with patch('app.utils.arlupdate.conn_db', side_effect=fake_conn_db):
            heal_stale_updating_icp_tasks()

            scope = mock_scope_col.find_one({"_id": scope_id})
            self.assertEqual(scope.get("synced_icp_task_id"), "old_task_id")
            self.assertNotIn("updating_icp_task_id", scope)

    def test_restart_single_icp_task_double_pointer(self):
        """测试重启任务时主指针不变，新任务被记录到 updating_icp_task_id"""
        from app.routes.icp import _restart_single_icp_task

        old_task_id = ObjectId()
        scope_id = ObjectId()

        mock_scope_col = MockCollection([
            {
                "_id": scope_id,
                "synced_icp_task_id": str(old_task_id)
            }
        ])
        mock_task_col = MockCollection([
            {
                "_id": old_task_id,
                "name": "测试企业主体",
                "target": "测试企业",
                "task_type": "icp",
                "query_type": ["web"],
                "status": "done",
                "synced_scope_id": str(scope_id)
            }
        ])

        def fake_conn_db(table):
            if table == 'asset_scope':
                return mock_scope_col
            elif table == 'icp_task':
                return mock_task_col
            return MockCollection()

        # 复刻微服务真实确认响应：_request_recon 会校验 code 与 task_id 必须回显一致。
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_response.json = lambda: {
            "code": 200, "msg": "Task accepted",
            "task_id": str(mock_task_col.data[-1]["_id"])
        }
        mock_requests_post = MagicMock(return_value=mock_response)

        with patch('app.routes.icp.conn_db', side_effect=fake_conn_db), \
             patch('requests.post', mock_requests_post):
            ok, reason, res = _restart_single_icp_task(str(old_task_id))

            self.assertTrue(ok)
            self.assertEqual(reason, "success")
            new_task_id = res.get("new_task_id")
            self.assertIsNotNone(new_task_id)
            self.assertNotEqual(str(old_task_id), new_task_id)

            # 验证资产组主指针未被篡改，依然指向旧任务
            scope = mock_scope_col.find_one({"_id": scope_id})
            self.assertEqual(scope.get("synced_icp_task_id"), str(old_task_id))
            # 验证 updating_icp_task_id 指向新任务
            self.assertEqual(scope.get("updating_icp_task_id"), new_task_id)

            # 验证新任务记录了 prev_task_id
            new_task = mock_task_col.find_one({"_id": ObjectId(new_task_id)})
            self.assertEqual(new_task.get("prev_task_id"), str(old_task_id))

    def test_asset_scope_enrich_running_and_done(self):
        """测试 AssetScope 列表与详情接口富化双指针：running保持展示旧任务，done原子晋升"""
        from app.routes.assetScope import ARLAssetScope

        old_task_id = ObjectId()
        new_running_id = ObjectId()
        scope_1_id = ObjectId()

        # 场景 A：任务正在运行中，AssetScope 保持指向旧任务，同时透传 updating_icp_task_id 与 updating_status
        items = [
            {
                "_id": scope_1_id,
                "name": "资产组A",
                "synced_icp_task_id": str(old_task_id),
                "updating_icp_task_id": str(new_running_id)
            }
        ]

        mock_scope_col = MockCollection(items)
        mock_task_col = MockCollection([
            {
                "_id": old_task_id,
                "name": "旧测绘任务",
                "target": "测试企业",
                "task_type": "icp",
                "status": "done"
            },
            {
                "_id": new_running_id,
                "name": "新测绘任务",
                "target": "测试企业",
                "task_type": "icp",
                "status": "running",
                "start_time": "2026-10-13 16:00:00"
            }
        ])

        def fake_conn_db(table):
            if table == 'asset_scope':
                return mock_scope_col
            elif table == 'icp_task':
                return mock_task_col
            return MockCollection()

        with patch('app.routes.assetScope.utils.conn_db', side_effect=fake_conn_db):
            resource = ARLAssetScope()
            # 模拟 resource.get() 中的 build_data 阶段
            data = {"items": items, "total": 1}
            with patch.object(resource, 'build_data', return_value=data), \
                 patch.object(resource.parser, 'parse_args', return_value={}):
                res = resource.get()
                item = res['items'][0]
                # 依然保持指向旧任务，存量资产视图正常
                self.assertEqual(item.get('synced_icp_task_id'), str(old_task_id))
                self.assertEqual(item.get('updating_icp_task_id'), str(new_running_id))
                self.assertEqual(item.get('updating_status'), 'running')

        # 场景 B：新测绘任务已完成，查询时自动原子晋升并清理 updating_icp_task_id
        done_task_id = ObjectId()
        scope_2_id = ObjectId()
        items_b = [
            {
                "_id": scope_2_id,
                "name": "资产组B",
                "synced_icp_task_id": str(old_task_id),
                "updating_icp_task_id": str(done_task_id)
            }
        ]
        mock_scope_col_b = MockCollection(items_b)
        mock_task_col_b = MockCollection([
            {
                "_id": old_task_id,
                "name": "旧测绘任务",
                "target": "测试企业",
                "task_type": "icp",
                "status": "done"
            },
            {
                "_id": done_task_id,
                "name": "新已完成任务",
                "target": "测试企业",
                "task_type": "icp",
                "status": "done"
            }
        ])

        def fake_conn_db_b(table):
            if table == 'asset_scope':
                return mock_scope_col_b
            elif table == 'icp_task':
                return mock_task_col_b
            return MockCollection()

        with patch('app.routes.assetScope.utils.conn_db', side_effect=fake_conn_db_b):
            resource = ARLAssetScope()
            data_b = {"items": items_b, "total": 1}
            with patch.object(resource, 'build_data', return_value=data_b), \
                 patch.object(resource.parser, 'parse_args', return_value={}):
                res_b = resource.get()
                item_b = res_b['items'][0]
                # 主指针原子晋升为新任务 ID，updating_icp_task_id 清除
                self.assertEqual(item_b.get('synced_icp_task_id'), str(done_task_id))
                self.assertNotIn('updating_icp_task_id', item_b)
                # 数据库中的持久化指针亦被同步更新
                db_scope = mock_scope_col_b.find_one({"_id": scope_2_id})
                self.assertEqual(db_scope.get("synced_icp_task_id"), str(done_task_id))
                self.assertNotIn("updating_icp_task_id", db_scope)

    def test_job_runner_scope_sync_helper(self):
        """测试 job_runner 中异步任务完成后的 _sync_scope_after_task_completion 协程"""
        import asyncio
        from osint_service.clients.job_runner import _sync_scope_after_task_completion, db

        scope_id = ObjectId()
        task_id = str(ObjectId())

        # 模拟 Motor / AsyncIOMotorClient collection
        class AsyncMockCollection:
            def __init__(self, data):
                self.data = data

            async def find_one(self, query):
                for item in self.data:
                    match = True
                    for k, v in query.items():
                        if item.get(k) != v:
                            match = False
                            break
                    if match:
                        return dict(item)
                return None

            async def update_one(self, query, update):
                for item in self.data:
                    match = True
                    for k, v in query.items():
                        if item.get(k) != v:
                            match = False
                            break
                    if match:
                        if "$set" in update:
                            for sk, sv in update["$set"].items():
                                item[sk] = sv
                        if "$unset" in update:
                            for uk in update["$unset"]:
                                item.pop(uk, None)
                        return MagicMock(modified_count=1)
                return MagicMock(modified_count=0)

        # 测试任务成功完成场景（同步晋升指针并清除遗留的 last_update_error）
        scope_data = [{
            "_id": scope_id,
            "synced_icp_task_id": "old_id",
            "updating_icp_task_id": task_id,
            "last_update_error": "旧失败提示",
            "last_update_error_task_id": "prev_err_task",
            "last_update_error_time": "2026-11-16 07:00:00"
        }]
        mock_col = AsyncMockCollection(scope_data)
        mock_db = MagicMock()
        mock_db.__getitem__.return_value = mock_col
        with patch('osint_service.clients.job_runner.db', mock_db):
            asyncio.run(_sync_scope_after_task_completion(task_id, "done"))
            self.assertEqual(scope_data[0].get("synced_icp_task_id"), task_id)
            self.assertNotIn("updating_icp_task_id", scope_data[0])
            self.assertNotIn("last_update_error", scope_data[0])

        # 测试任务失败熔断场景（保留旧主指针，持久化失败摘要以供列表返回后展示）
        task_fail_id = str(ObjectId())
        scope_data_fail = [{
            "_id": scope_id,
            "synced_icp_task_id": "old_id",
            "updating_icp_task_id": task_fail_id
        }]
        mock_col_fail = AsyncMockCollection(scope_data_fail)
        mock_db_fail = MagicMock()
        mock_db_fail.__getitem__.return_value = mock_col_fail
        with patch('osint_service.clients.job_runner.db', mock_db_fail):
            asyncio.run(_sync_scope_after_task_completion(task_fail_id, "error", "天眼查接口超时"))
            self.assertEqual(scope_data_fail[0].get("synced_icp_task_id"), "old_id")
            self.assertNotIn("updating_icp_task_id", scope_data_fail[0])
            self.assertEqual(scope_data_fail[0].get("last_update_error"), "天眼查接口超时")
            self.assertEqual(scope_data_fail[0].get("last_update_error_task_id"), task_fail_id)

        # 测试任务被手动停止场景（保留旧主指针，不写入失败摘要）
        task_stop_id = str(ObjectId())
        scope_data_stop = [{
            "_id": scope_id,
            "synced_icp_task_id": "old_id",
            "updating_icp_task_id": task_stop_id
        }]
        mock_col_stop = AsyncMockCollection(scope_data_stop)
        mock_db_stop = MagicMock()
        mock_db_stop.__getitem__.return_value = mock_col_stop
        with patch('osint_service.clients.job_runner.db', mock_db_stop):
            asyncio.run(_sync_scope_after_task_completion(task_stop_id, "stop"))
            self.assertEqual(scope_data_stop[0].get("synced_icp_task_id"), "old_id")
            self.assertNotIn("updating_icp_task_id", scope_data_stop[0])
            self.assertNotIn("last_update_error", scope_data_stop[0])

    def test_restart_rejects_concurrent_update_and_strips_auto_group(self):
        """测试并发重启拦截返回 existing updating_task_id，且新任务不继承 auto_group 标记"""
        from app.routes.icp import _restart_single_icp_task, IcpTaskRestart

        scope_id = ObjectId()
        old_task_id = ObjectId()
        active_utid = ObjectId()

        mock_task_col = MockCollection([
            {
                "_id": old_task_id,
                "name": "并发防重测试",
                "target": "测试集团",
                "task_type": "icp",
                "status": "done",
                "synced_scope_id": str(scope_id),
                "auto_group": True,
                "auto_group_scope_id": str(scope_id),
                "auto_group_claimed": True
            },
            {
                "_id": active_utid,
                "name": "进行中的更新任务",
                "target": "测试集团",
                "task_type": "icp",
                "status": "waiting"
            }
        ])
        mock_scope_col = MockCollection([
            {
                "_id": scope_id,
                "synced_icp_task_id": str(old_task_id),
                "updating_icp_task_id": str(active_utid)
            }
        ])
        tables = {'asset_scope': mock_scope_col, 'icp_task': mock_task_col}

        with patch('app.routes.icp.conn_db', side_effect=lambda t: tables.setdefault(t, MockCollection())):
            ok, reason, res = _restart_single_icp_task(str(old_task_id))
            self.assertFalse(ok)
            self.assertEqual(reason, "updating")
            self.assertEqual(res.get("updating_task_id"), str(active_utid))
            self.assertEqual(len(mock_task_col.data), 2)

            api_res = IcpTaskRestart().get(str(old_task_id))
            self.assertNotEqual(api_res.get("code"), 200)
            self.assertEqual(api_res.get("data", {}).get("updating_task_id"), str(active_utid))

            # 若旧更新已结束，重跑新任务不应继承 auto_group 字段
            mock_scope_col.update_one({"_id": scope_id}, {"$unset": {"updating_icp_task_id": ""}})
            mock_scope_col.update_one({"_id": scope_id}, {"$set": {"last_update_error": "old err"}})
            mock_resp = MagicMock(status_code=200)
            mock_resp.json = lambda: {"code": 200, "task_id": str(mock_task_col.data[-1]["_id"])}
            with patch('requests.post', MagicMock(return_value=mock_resp)):
                ok2, reason2, res2 = _restart_single_icp_task(str(old_task_id))
                self.assertTrue(ok2)
                self.assertEqual(reason2, "success")
                created = mock_task_col.find_one({"_id": ObjectId(res2["new_task_id"])})
                self.assertNotIn("auto_group", created)
                self.assertNotIn("auto_group_claimed", created)
                self.assertNotIn("auto_group_scope_id", created)
                self.assertNotIn("last_update_error", mock_scope_col.find_one({"_id": scope_id}))

    def test_bind_enterprise_clears_updating_pointer_and_stops_superseded_task(self):
        """测试更换绑定主体时清理 updating_icp_task_id、历史错误摘要并停止旧更新任务"""
        from app.routes.assetScope import BindEnterpriseScope

        scope_id = ObjectId()
        old_task_id = ObjectId()
        old_updating_id = ObjectId()
        new_task_id = ObjectId()

        mock_scope_col = MockCollection([
            {
                "_id": scope_id,
                "name": "资产组A",
                "synced_icp_task_id": str(old_task_id),
                "updating_icp_task_id": str(old_updating_id),
                "last_update_error": "前一次失败"
            }
        ])
        mock_task_col = MockCollection([
            {"_id": old_task_id, "name": "旧任务", "target": "旧公司", "task_type": "icp", "status": "done", "synced_scope_id": str(scope_id)},
            {"_id": old_updating_id, "name": "旧更新", "target": "旧公司", "task_type": "icp", "status": "running"},
            {"_id": new_task_id, "name": "新主体测绘", "target": "新公司", "task_type": "tyc", "status": "done"}
        ])
        tables = {'asset_scope': mock_scope_col, 'icp_task': mock_task_col}
        stop_calls = []

        resource = BindEnterpriseScope()
        with patch('app.routes.assetScope.utils.conn_db', side_effect=lambda t: tables.setdefault(t, MockCollection())), \
             patch('app.routes.icp._request_recon', side_effect=lambda ep, payload=None, **kw: stop_calls.append((ep, payload)) or {"code": 200}), \
             patch.object(resource, 'parse_args', return_value={"scope_id": str(scope_id), "task_id": str(new_task_id)}):
            res = resource.post()
            self.assertEqual(res.get("code"), 200)
            self.assertEqual(stop_calls, [("stop", {"task_id": str(old_updating_id)})])

            updated_scope = mock_scope_col.find_one({"_id": scope_id})
            self.assertEqual(updated_scope.get("synced_icp_task_id"), str(new_task_id))
            self.assertNotIn("updating_icp_task_id", updated_scope)
            self.assertNotIn("last_update_error", updated_scope)

            old_task = mock_task_col.find_one({"_id": old_task_id})
            self.assertNotIn("synced_scope_id", old_task)
            self.assertEqual(mock_task_col.find_one({"_id": new_task_id}).get("synced_scope_id"), str(scope_id))
            self.assertEqual(mock_task_col.find_one({"_id": old_updating_id}).get("status"), "stop")

    def test_asset_scope_persists_last_update_error_until_dismissed_and_heals_stop_missing(self):
        """测试 GET /asset_scope/ 多次轮询保留 last_update_error 直到手动清除，stop/missing 任务不写错误"""
        from app.routes.assetScope import ARLAssetScope, ClearScopeUpdateError

        scope_err_id = ObjectId()
        err_task_id = ObjectId()
        scope_stop_id = ObjectId()
        stop_task_id = ObjectId()
        scope_missing_id = ObjectId()
        missing_task_id = ObjectId()

        items = [
            {"_id": scope_err_id, "name": "组Err", "synced_icp_task_id": "base_err", "updating_icp_task_id": str(err_task_id)},
            {"_id": scope_stop_id, "name": "组Stop", "synced_icp_task_id": "base_stop", "updating_icp_task_id": str(stop_task_id)},
            {"_id": scope_missing_id, "name": "组Missing", "synced_icp_task_id": "base_miss", "updating_icp_task_id": str(missing_task_id)}
        ]
        mock_scope_col = MockCollection([dict(x) for x in items])
        mock_task_col = MockCollection([
            {"_id": err_task_id, "status": "error", "error_msg": "查询异常"},
            {"_id": stop_task_id, "status": "stop"}
        ])
        tables = {'asset_scope': mock_scope_col, 'icp_task': mock_task_col}

        resource = ARLAssetScope()
        clear_res = ClearScopeUpdateError()
        with patch('app.routes.assetScope.utils.conn_db', side_effect=lambda t: tables.setdefault(t, MockCollection())):
            first_items = [{**x, "_id": str(x["_id"])} for x in mock_scope_col.data]
            with patch.object(resource, 'build_data', return_value={"items": first_items, "total": 3}), \
                 patch.object(resource.parser, 'parse_args', return_value={}):
                out1 = resource.get()
                self.assertEqual(out1['items'][0].get('update_error_msg'), '查询异常')
                self.assertNotIn('updating_icp_task_id', out1['items'][0])
                self.assertNotIn('updating_icp_task_id', out1['items'][1])
                self.assertNotIn('update_error_msg', out1['items'][1])
                self.assertNotIn('updating_icp_task_id', out1['items'][2])
                self.assertNotIn('update_error_msg', out1['items'][2])

            # 列表二次轮询：错误仍保留给详情页
            second_items = [{**x, "_id": str(x["_id"])} for x in mock_scope_col.data]
            with patch.object(resource, 'build_data', return_value={"items": second_items, "total": 3}), \
                 patch.object(resource.parser, 'parse_args', return_value={}):
                out2 = resource.get()
                self.assertEqual(out2['items'][0].get('update_error_msg'), '查询异常')
                # 确认 _id 为字符串时也成功写回了真实 ObjectId 记录
                db_err_scope = mock_scope_col.find_one({"_id": scope_err_id})
                self.assertNotIn("updating_icp_task_id", db_err_scope)
                self.assertEqual(db_err_scope.get("last_update_error"), "查询异常")

            # 关闭错误提示后彻底清理
            with patch.object(clear_res, 'parse_args', return_value={"scope_id": str(scope_err_id)}):
                res_clr = clear_res.post()
                self.assertEqual(res_clr.get("code"), 200)
                self.assertNotIn("last_update_error", mock_scope_col.find_one({"_id": scope_err_id}))

    def test_icp_stop_and_delete_clear_scope_updating_pointer(self):
        """测试停止或删除更新任务时立即释放资产组 updating_icp_task_id"""
        from app.routes.icp import IcpTaskStop, IcpTaskDelete

        scope_id = ObjectId()
        utid_stop = ObjectId()
        utid_del = ObjectId()

        mock_scope_col = MockCollection([
            {"_id": scope_id, "synced_icp_task_id": "old_snap", "updating_icp_task_id": str(utid_stop)}
        ])
        mock_task_col = MockCollection([
            {"_id": utid_stop, "status": "running", "target": "测试"},
            {"_id": utid_del, "status": "stop", "target": "测试2"}
        ])
        tables = {'asset_scope': mock_scope_col, 'icp_task': mock_task_col}

        with patch('app.routes.icp.conn_db', side_effect=lambda t: tables.setdefault(t, MockCollection())), \
             patch('app.routes.icp._request_recon', return_value={"code": 200, "msg": "stopped"}):
            stop_res = IcpTaskStop().get(str(utid_stop))
            self.assertEqual(stop_res.get("code"), 200)
            self.assertNotIn("updating_icp_task_id", mock_scope_col.find_one({"_id": scope_id}))
            self.assertEqual(mock_scope_col.find_one({"_id": scope_id}).get("synced_icp_task_id"), "old_snap")

            mock_scope_col.update_one({"_id": scope_id}, {"$set": {"updating_icp_task_id": str(utid_del)}})
            del_res = IcpTaskDelete().get(str(utid_del))
            self.assertEqual(del_res.get("code"), 200)
            self.assertNotIn("updating_icp_task_id", mock_scope_col.find_one({"_id": scope_id}))
            self.assertIsNone(mock_task_col.find_one({"_id": utid_del}))


if __name__ == '__main__':
    unittest.main()
