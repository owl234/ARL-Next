import os
import sys
import unittest
from unittest.mock import MagicMock

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999

import pymongo
pymongo.MongoClient = MagicMock()

from app.routes import ARLResource


class TestCDNSemanticQuery(unittest.TestCase):
    """
    第一性原理单元测试：验证 cdn_name 智能语义识别与 is_cdn 查询转换
    确保搜索“独立”、“独立源站”等关键词时能够正确匹配非 CDN 资产（包括缺失字段的历史数据）
    """

    def setUp(self):
        self.resource = ARLResource()

    def test_independent_origin_semantic_keywords(self):
        keywords = ["独立", "独立源站", "源站", "非cdn", "非 CDN", "false", "0", "否", "  独立源站  "]
        for kw in keywords:
            with self.subTest(keyword=kw):
                query = self.resource.build_db_query({"cdn_name": kw, "scope_id": "scope_123"})
                self.assertEqual(query.get("scope_id"), "scope_123")
                self.assertEqual(query.get("is_cdn"), {"$ne": True})
                self.assertEqual(query.get("cdn_name"), {"$in": ["", None]})

    def test_cdn_node_semantic_keywords(self):
        keywords = ["cdn节点", "cdn 节点", "CDN节点"]
        for kw in keywords:
            with self.subTest(keyword=kw):
                query = self.resource.build_db_query({"cdn_name": kw, "scope_id": "scope_123"})
                self.assertEqual(query.get("scope_id"), "scope_123")
                expected_or = [
                    {"is_cdn": True},
                    {"cdn_name": {"$nin": ["", None]}}
                ]
                self.assertEqual(query.get("$or"), expected_or)

    def test_vendor_name_regex_query(self):
        vendors = ["阿里云", "Cloudflare", "腾讯云 CDN", "华为云"]
        for vendor in vendors:
            with self.subTest(vendor=vendor):
                query = self.resource.build_db_query({"cdn_name": vendor})
                self.assertIn("cdn_name", query)
                import re
                self.assertTrue(bool(re.search(query["cdn_name"]["$regex"], vendor, re.I)))

    def test_is_cdn_explicit_query(self):
        # is_cdn = false / 0
        for val in ["false", "0", False, "否"]:
            with self.subTest(val=val):
                query = self.resource.build_db_query({"is_cdn": val})
                self.assertEqual(query.get("is_cdn"), {"$ne": True})
                self.assertEqual(query.get("cdn_name"), {"$in": ["", None]})

        # is_cdn = true / 1
        for val in ["true", "1", True, "是"]:
            with self.subTest(val=val):
                query = self.resource.build_db_query({"is_cdn": val})
                expected_or = [
                    {"is_cdn": True},
                    {"cdn_name": {"$nin": ["", None]}}
                ]
                self.assertEqual(query.get("$or"), expected_or)


if __name__ == '__main__':
    unittest.main()
