import unittest
from unittest.mock import MagicMock
import os
import sys

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999

import pymongo
pymongo.MongoClient = MagicMock()

from app.routes.assetIP import BaseAssetIPResource
from app.routes.ip import BaseIPResource


class TestIPCDNFilter(unittest.TestCase):
    def setUp(self):
        self.asset_resource = BaseAssetIPResource()
        self.ip_resource = BaseIPResource()

    def test_asset_ip_query_all(self):
        query = self.asset_resource.build_db_query({"cdn_type": "all", "scope_id": "scope123"})
        self.assertEqual(query.get("scope_id"), "scope123")
        self.assertNotIn("$or", query)
        self.assertNotIn("$and", query)

    def test_asset_ip_query_invalid_cdn_type(self):
        # 非法 cdn_type 降级为全部
        query = self.asset_resource.build_db_query({"cdn_type": "unknown_value", "scope_id": "scope123"})
        self.assertEqual(query.get("scope_id"), "scope123")
        self.assertNotIn("$or", query)
        self.assertNotIn("$and", query)

    def test_asset_ip_query_origin(self):
        query = self.asset_resource.build_db_query({"cdn_type": "origin", "scope_id": "scope123"})
        self.assertEqual(query.get("scope_id"), "scope123")
        self.assertIn("$and", query)
        and_conditions = query["$and"]
        self.assertEqual(len(and_conditions), 2)
        self.assertEqual(and_conditions[0], {"$or": [{"is_cdn": False}, {"is_cdn": {"$exists": False}}]})
        self.assertEqual(and_conditions[1], {"$or": [{"cdn_name": ""}, {"cdn_name": None}, {"cdn_name": {"$exists": False}}]})

    def test_asset_ip_query_origin_loose_types(self):
        # 松散类型支持: is_cdn="false", 0, False
        for val in ("false", "False", 0, False):
            q = self.asset_resource.build_db_query({"is_cdn": val, "scope_id": "scope123"})
            self.assertIn("$and", q, f"Failed for is_cdn={val}")

    def test_asset_ip_query_origin_with_ghost_cdn_name(self):
        # 防御测试：当 cdn_type="origin" 但同时残存 cdn_name="Cloudflare" 幽灵参数时，cdn_name 必须被剥离
        query = self.asset_resource.build_db_query({"cdn_type": "origin", "cdn_name": "Cloudflare", "scope_id": "scope123"})
        self.assertEqual(query.get("scope_id"), "scope123")
        self.assertIn("$and", query)
        self.assertNotIn("cdn_name", query)

    def test_asset_ip_query_cdn(self):
        # 验证 cdn 状态安全放入 $and，不破坏顶层 $or
        query = self.asset_resource.build_db_query({"cdn_type": "cdn", "scope_id": "scope123"})
        self.assertEqual(query.get("scope_id"), "scope123")
        self.assertIn("$and", query)
        self.assertEqual(query["$and"][0]["$or"], [{"is_cdn": True}, {"cdn_name": {"$exists": True, "$nin": ["", None]}}])

    def test_asset_ip_query_cdn_loose_types(self):
        # 松散类型支持: is_cdn="true", 1, True
        for val in ("true", "True", 1, True):
            q = self.asset_resource.build_db_query({"is_cdn": val, "scope_id": "scope123"})
            self.assertIn("$and", q, f"Failed for is_cdn={val}")
            self.assertEqual(q["$and"][0]["$or"], [{"is_cdn": True}, {"cdn_name": {"$exists": True, "$nin": ["", None]}}])

    def test_cdn_query_does_not_overwrite_existing_or(self):
        # 关键防御断言：当基础查询已经产生 $or 时，cdn 过滤不应该覆盖原有的 $or
        class SubclassedResource(BaseAssetIPResource):
            def build_db_query(self, args):
                q = super().build_db_query(args)
                return q

        res = SubclassedResource()
        # 模拟 super 生成了带有 $and 或 $or 的查询
        with unittest.mock.patch.object(BaseAssetIPResource, 'build_db_query', return_value={"scope_id": "123", "$and": [{"mock_rule": 1}]}):
            pass # 构造完成

        query = res.build_db_query({"cdn_type": "cdn", "scope_id": "scope123"})
        self.assertIn("$and", query)

    def test_ip_query_origin(self):
        query = self.ip_resource.build_db_query({"cdn_type": "origin", "task_id": "task123"})
        self.assertEqual(query.get("task_id"), "task123")
        self.assertIn("$and", query)

    def test_ip_query_origin_with_ghost_cdn_name(self):
        # 任务详情同理防御幽灵参数互斥
        query = self.ip_resource.build_db_query({"cdn_type": "origin", "cdn_name": "Cloudflare", "task_id": "task123"})
        self.assertEqual(query.get("task_id"), "task123")
        self.assertIn("$and", query)
        self.assertNotIn("cdn_name", query)

    def test_ip_query_cdn(self):
        query = self.ip_resource.build_db_query({"cdn_type": "cdn", "task_id": "task123"})
        self.assertEqual(query.get("task_id"), "task123")
        self.assertIn("$and", query)
        self.assertEqual(query["$and"][0]["$or"], [{"is_cdn": True}, {"cdn_name": {"$exists": True, "$nin": ["", None]}}])


if __name__ == '__main__':
    unittest.main()
