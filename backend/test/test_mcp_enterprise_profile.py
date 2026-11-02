#coding: utf-8
"""
单元测试：ARL-Next 企业生态资产画像聚合核心 (app.mcp_asset.build_enterprise_profile)
与 MCP REST 端点 (/api/mcp/enterprise_profile)
"""

import sys
import os
import unittest
from bson import ObjectId
from unittest.mock import Mock, patch

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(TEST_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.mcp_asset import build_enterprise_profile


class FakeCollection:
    def __init__(self, docs=None):
        self.docs = docs or []

    def find_one(self, filter_dict=None, sort=None):
        items = self._filter(filter_dict)
        if sort and items:
            for field, order in sort:
                items.sort(key=lambda x: x.get(field, ""), reverse=(order == -1))
        return items[0] if items else None

    def find(self, filter_dict=None, projection=None):
        items = self._filter(filter_dict)
        return FakeCursor(items)

    def count_documents(self, filter_dict=None):
        return len(self._filter(filter_dict))

    def _filter(self, f):
        if not f:
            return list(self.docs)
        res = []
        for d in self.docs:
            if self._matches(d, f):
                res.append(d)
        return res

    def _matches(self, doc, cond):
        if not isinstance(cond, dict):
            return True
        for k, v in cond.items():
            if k == "$or":
                sub_matched = any(self._matches(doc, sub_c) for sub_c in v)
                if not sub_matched:
                    return False
                continue
            doc_val = doc.get(k)
            if isinstance(v, dict) and "$regex" in v:
                import re
                pat = v["$regex"]
                flags = re.IGNORECASE if v.get("$options") == "i" else 0
                if not (isinstance(doc_val, str) and re.search(pat, doc_val, flags)):
                    return False
            elif doc_val != v:
                return False
        return True


class FakeCursor:
    def __init__(self, items):
        self.items = list(items)

    def sort(self, field, order=-1):
        return self

    def skip(self, n):
        self.items = self.items[n:]
        return self

    def limit(self, n):
        self.items = self.items[:n]
        return self

    def __iter__(self):
        return iter(self.items)


class TestMCPEnterpriseProfile(unittest.TestCase):
    def setUp(self):
        self.task_id = "670000000000000000000001"
        self.scope_id = "670000000000000000000002"

        self.mock_task = {
            "_id": ObjectId(self.task_id),
            "name": "深圳市腾讯计算机系统有限公司全景测绘",
            "company_name": "深圳市腾讯计算机系统有限公司",
            "target": "深圳市腾讯计算机系统有限公司",
            "status": "done",
            "task_type": "tyc",
            "gid": "123456",
            "synced_scope_id": self.scope_id
        }

        self.mock_scope = {
            "_id": ObjectId(self.scope_id),
            "name": "腾讯集团",
            "enterprise_name": "深圳市腾讯计算机系统有限公司",
            "domain_array": ["qq.com", "tencent.com", "wechat.com"],
            "scope_array": ["qq.com", "tencent.com", "wechat.com"]
        }

        self.mock_assets = [
            {"task_id": self.task_id, "query_type": "web", "domain": "qq.com", "serviceName": "腾讯网", "serviceLicence": "粤B2-20090059-1"},
            {"task_id": self.task_id, "query_type": "web", "domain": "tencent.com", "serviceName": "腾讯官方网站", "serviceLicence": "粤B2-20090059-5"},
            {"task_id": self.task_id, "query_type": "web", "domain": "wechat.com", "serviceName": "微信官网", "serviceLicence": "粤B2-20090059-18"},
            {"task_id": self.task_id, "query_type": "app", "name": "腾讯会议", "category": "办公商务", "serviceLicence": "粤B2-20090059-App1"},
            {"task_id": self.task_id, "query_type": "app", "name": "企业微信", "category": "商务沟通", "serviceLicence": "粤B2-20090059-App2"},
            {"task_id": self.task_id, "query_type": "mapp", "name": "腾讯乘车码", "unitName": "深圳市腾讯计算机系统有限公司"},
            {"task_id": self.task_id, "query_type": "wechat", "name": "腾讯科技", "wechatId": "qqtech"},
            {"task_id": self.task_id, "query_type": "weibo", "name": "腾讯官方微博", "homeUrl": "https://weibo.com/tencent"},
            {"task_id": self.task_id, "query_type": "kapp", "name": "腾讯新闻快应用", "unitName": "深圳市腾讯计算机系统有限公司"},
            {"task_id": self.task_id, "query_type": "invest", "name": "腾讯云计算（北京）有限责任公司", "percent": "100%", "legalPerson": "邱跃鹏"}
        ]

        self.collections = {
            "icp_task": FakeCollection([self.mock_task]),
            "asset_scope": FakeCollection([self.mock_scope]),
            "icp_asset": FakeCollection(self.mock_assets),
            "asset_site": FakeCollection([{"scope_id": self.scope_id, "site": "https://qq.com"}]),
            "asset_vuln": FakeCollection([{"scope_id": self.scope_id, "vuln_name": "Test CVE"}]),
            "asset_nuclei_result": FakeCollection([])
        }

        self.patcher = patch("app.utils.conn_db", side_effect=lambda name: self.collections.get(name, FakeCollection()))
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_overview_mode_success(self):
        """测试概览模式 (category='all')：返回统计、样本与绑定的资产组态势"""
        res = build_enterprise_profile(target="深圳市腾讯计算机系统有限公司")
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res["enterprise_info"]["name"], "深圳市腾讯计算机系统有限公司")
        self.assertEqual(res["enterprise_info"]["task_status"], "done")
        self.assertEqual(res["asset_counts"]["web"], 3)
        self.assertEqual(res["asset_counts"]["app"], 2)
        self.assertEqual(res["asset_counts"]["total"], 10)

        # 验证 Top 采样
        self.assertEqual(len(res["samples"]["web_top"]), 3)
        self.assertEqual(res["samples"]["web_top"][0]["domain"], "qq.com")
        self.assertEqual(res["samples"]["app_top"][0]["name"], "腾讯会议")
        self.assertEqual(res["samples"]["invest_top"][0]["company_name"], "腾讯云计算（北京）有限责任公司")

        # 验证关联资产组态势透出
        bound_scope = res["enterprise_info"]["bound_scope"]
        self.assertIsNotNone(bound_scope)
        self.assertEqual(bound_scope["scope_name"], "腾讯集团")
        self.assertEqual(bound_scope["managed_domains"], 3)
        self.assertEqual(bound_scope["live_sites"], 1)
        self.assertEqual(bound_scope["unresolved_risks"], 1)

        # 验证下钻指引
        self.assertIn("category='web'", res["drilldown_guidance"]["tip"])
        self.assertIn("get_asset_profile", res["drilldown_guidance"]["tip"])

    def test_domain_reverse_lookup(self):
        """测试输入根域名时，通过 icp_asset 反查归属企业主体并返回画像"""
        res = build_enterprise_profile(target="qq.com")
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res["enterprise_info"]["name"], "深圳市腾讯计算机系统有限公司")

    def test_fuzzy_name_match(self):
        """测试企业简称模糊匹配"""
        res = build_enterprise_profile(target="腾讯计算机")
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res["enterprise_info"]["name"], "深圳市腾讯计算机系统有限公司")

    def test_category_drilldown_web(self):
        """测试分维度下钻模式 (category='web')"""
        res = build_enterprise_profile(target="腾讯", category="web", page=1, size=2)
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res["category"], "web")
        self.assertEqual(res["pagination"]["total"], 3)
        self.assertEqual(len(res["items"]), 2)
        self.assertTrue(res["pagination"]["has_more"])
        self.assertEqual(res["items"][0]["domain"], "qq.com")

    def test_category_drilldown_invest(self):
        """测试分维度下钻模式 (category='invest')"""
        res = build_enterprise_profile(target="腾讯", category="invest")
        self.assertEqual(res.get("status"), "success")
        self.assertEqual(res["category"], "invest")
        self.assertEqual(len(res["items"]), 1)
        self.assertEqual(res["items"][0]["company_name"], "腾讯云计算（北京）有限责任公司")
        self.assertEqual(res["items"][0]["ratio"], "100%")

    def test_multiple_candidates_disambiguation(self):
        """测试简称命中多家不同企业时返回候选清单"""
        multi_tasks = [
            {"_id": ObjectId("670000000000000000000010"), "company_name": "阿里巴巴网络技术有限公司", "name": "阿里任务1", "status": "done"},
            {"_id": ObjectId("670000000000000000000011"), "company_name": "阿里云计算有限公司", "name": "阿里任务2", "status": "done"}
        ]
        self.collections["icp_task"] = FakeCollection(multi_tasks)
        res = build_enterprise_profile(target="阿里")
        self.assertEqual(res.get("status"), "multiple_candidates")
        self.assertEqual(len(res.get("candidates", [])), 2)
        names = [c["name"] for c in res["candidates"]]
        self.assertIn("阿里巴巴网络技术有限公司", names)
        self.assertIn("阿里云计算有限公司", names)

    def test_not_found_handling(self):
        """测试完全未检索到企业时的安全只读提示"""
        res = build_enterprise_profile(target="未知神秘企业xxxx")
        self.assertEqual(res.get("status"), "not_found")
        self.assertIn("未在 ARL 资产库中检索到", res["message"])
        self.assertIn("企业全景测绘建组", res["suggestion"])

    def test_unsupported_category(self):
        """测试传入不支持的 category"""
        res = build_enterprise_profile(target="腾讯", category="invalid_cat")
        self.assertEqual(res.get("status"), "error")
        self.assertIn("Unsupported category", res.get("message", ""))


if __name__ == "__main__":
    unittest.main()
