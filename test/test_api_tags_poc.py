import pytest
from conftest import BASE_URL

class TestTagsAndResultSet:
    """站点和资产站点的标签管理与结果集保存操作"""

    def test_site_add_delete_tag(self, api_client):
        """测试普通的非法ID添加/删除标签"""
        # 测试 POST /site/add_tag/
        res = api_client.post(f"{BASE_URL}/site/add_tag/", json={"_id": "0"*24, "tag": "test_tag"})
        assert res.status_code == 200

        # 测试 POST /site/delete_tag/
        res = api_client.post(f"{BASE_URL}/site/delete_tag/", json={"_id": "0"*24, "tag": "test_tag"})
        assert res.status_code == 200

    def test_asset_site_add_delete_tag(self, api_client):
        """测试资产站点的非法ID添加/删除标签"""
        # 测试 POST /asset_site/add_tag/
        res = api_client.post(f"{BASE_URL}/asset_site/add_tag/", json={"_id": "0"*24, "tag": "test_tag"})
        assert res.status_code == 200

        # 测试 POST /asset_site/delete_tag/
        res = api_client.post(f"{BASE_URL}/asset_site/delete_tag/", json={"_id": "0"*24, "tag": "test_tag"})
        assert res.status_code == 200

    def test_site_save_result_set(self, api_client):
        """测试保存站点结果集 (GET /site/save_result_set/)"""
        res = api_client.get(f"{BASE_URL}/site/save_result_set/")
        assert res.status_code == 200
        body = res.json()
        assert "code" in body

    def test_asset_site_save_result_set(self, api_client):
        """测试保存资产站点结果集 (GET /asset_site/save_result_set/)"""
        res = api_client.get(f"{BASE_URL}/asset_site/save_result_set/")
        assert res.status_code == 200
        body = res.json()
        assert "code" in body


class TestPocOps:
    """POC 库的同步与清空操作"""

    def test_poc_sync(self, api_client):
        """测试同步 POC 信息 (GET /poc/sync/)"""
        res = api_client.get(f"{BASE_URL}/poc/sync/")
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200

    def test_poc_delete(self, api_client):
        """测试清空 POC 信息 (GET /poc/delete/)"""
        res = api_client.get(f"{BASE_URL}/poc/delete/")
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
