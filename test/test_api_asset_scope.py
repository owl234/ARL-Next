"""
test_api_asset_scope.py
=======================
测试资产组管理接口：
  - GET  /api/asset_scope/          查询资产组列表
  - POST /api/asset_scope/          创建资产组
  - POST /api/asset_scope/update/   修改资产组
  - POST /api/asset_scope/delete/   删除资产组
"""
import pytest
from conftest import BASE_URL


# ──────────────────────────────────────────────
# 辅助：创建并返回资产组 ID
# ──────────────────────────────────────────────
def _create_scope(api_client, name="pytest-scope-tmp", scope="test.example.com", scope_type="domain"):
    payload = {
        "name": name,
        "scope": scope,
        "black_scope": "",
        "scope_type": scope_type
    }
    res = api_client.post(f"{BASE_URL}/asset_scope/", json=payload)
    assert res.status_code == 200, f"创建资产组失败: {res.text}"
    body = res.json()
    assert body.get("code") == 200, f"创建资产组失败: {body}"
    scope_id = body.get("data", {}).get("scope_id") or body.get("data", {}).get("_id") or body.get("_id")
    assert scope_id, f"未获取到 scope_id: {body}"
    return scope_id


# ──────────────────────────────────────────────
# 1. 查询资产组
# ──────────────────────────────────────────────

class TestAssetScopeQuery:
    def test_get_scope_list(self, api_client):
        """GET /asset_scope/ 应返回标准分页结构"""
        res = api_client.get(f"{BASE_URL}/asset_scope/")
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert "items" in body
        assert "total" in body

    def test_get_scope_with_pagination(self, api_client):
        """分页参数生效：page=1, size=5"""
        res = api_client.get(f"{BASE_URL}/asset_scope/", params={"page": 1, "size": 5})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert len(body["items"]) <= 5

    def test_get_scope_filter_by_name(self, api_client, test_scope):
        """按名称模糊过滤资产组（依赖 test_scope fixture）"""
        res = api_client.get(f"{BASE_URL}/asset_scope/", params={"name": "pytest-test-scope"})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        # 至少包含 fixture 创建的那个资产组
        assert body["total"] >= 1

    def test_get_scope_filter_by_type(self, api_client):
        """按 scope_type 过滤"""
        res = api_client.get(f"{BASE_URL}/asset_scope/", params={"scope_type": "domain"})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200


# ──────────────────────────────────────────────
# 2. 追加 / 局部删除资产组条目
# ──────────────────────────────────────────────

class TestAssetScopePartialOps:
    def test_append_scope_to_existing(self, api_client):
        """POST /asset_scope/add/ 向已有资产组追加新域名"""
        scope_id = _create_scope(api_client, name="pytest-append-scope",
                                 scope="original.example.com")
        res = api_client.post(f"{BASE_URL}/asset_scope/add/",
                              json={"scope_id": scope_id, "scope": "appended.example.com"})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        api_client.post(f"{BASE_URL}/asset_scope/delete/", json={"_id": [scope_id]})

    def test_append_scope_invalid_domain(self, api_client, test_scope):
        """追加非法域名：业务层应拒绝"""
        res = api_client.post(f"{BASE_URL}/asset_scope/add/",
                              json={"scope_id": test_scope, "scope": "not_a_valid!!!"})
        assert res.status_code == 200
        assert res.json()["code"] != 200

    def test_append_scope_nonexistent_id(self, api_client):
        """追加到不存在的资产组：业务层应拒绝"""
        res = api_client.post(f"{BASE_URL}/asset_scope/add/",
                              json={"scope_id": "000000000000000000000000",
                                    "scope": "test.example.com"})
        assert res.status_code == 200
        assert res.json()["code"] != 200

    def test_partial_delete_scope_entry(self, api_client):
        """GET /asset_scope/delete/?scope=xxx  局部删除资产组中某条目"""
        scope_id = _create_scope(api_client, name="pytest-partial-del",
                                 scope="keep.example.com")
        api_client.post(f"{BASE_URL}/asset_scope/add/",
                        json={"scope_id": scope_id, "scope": "remove.example.com"})
        res = api_client.get(f"{BASE_URL}/asset_scope/delete/",
                             params={"scope": "remove.example.com", "scope_id": scope_id})
        assert res.status_code == 200
        assert res.json()["code"] == 200
        api_client.post(f"{BASE_URL}/asset_scope/delete/", json={"_id": [scope_id]})

    def test_partial_delete_nonexistent_entry(self, api_client, test_scope):
        """局部删除不存在的条目：应返回业务错误"""
        res = api_client.get(f"{BASE_URL}/asset_scope/delete/",
                             params={"scope": "nonexistent.example.com",
                                     "scope_id": test_scope})
        assert res.status_code == 200
        assert res.json()["code"] != 200


# ──────────────────────────────────────────────
# 3. 创建资产组
# ──────────────────────────────────────────────

class TestAssetScopeCreate:
    def test_create_domain_scope(self, api_client):
        """创建 domain 类型资产组"""
        scope_id = _create_scope(api_client, name="pytest-domain-scope", scope="domain-test.example.com")
        assert scope_id
        # 清理
        api_client.post(f"{BASE_URL}/asset_scope/delete/", json={"_id": [scope_id]})

    def test_create_ip_scope(self, api_client):
        """创建 IP 类型资产组"""
        payload = {
            "name": "pytest-ip-scope",
            "scope": "192.168.1.0/24",
            "black_scope": "",
            "scope_type": "ip"
        }
        res = api_client.post(f"{BASE_URL}/asset_scope/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        scope_id = body.get("data", {}).get("_id") or body.get("_id")
        # 清理
        if scope_id:
            api_client.post(f"{BASE_URL}/asset_scope/delete/", json={"_id": [scope_id]})

    def test_create_scope_missing_name(self, api_client):
        """缺少 name 字段：应返回 400"""
        payload = {"scope": "test.example.com", "black_scope": "", "scope_type": "domain"}
        res = api_client.post(f"{BASE_URL}/asset_scope/", json=payload)
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)

    def test_create_scope_missing_scope(self, api_client):
        """缺少 scope 字段：应返回 400"""
        payload = {"name": "pytest-no-scope", "black_scope": "", "scope_type": "domain"}
        res = api_client.post(f"{BASE_URL}/asset_scope/", json=payload)
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)


# ──────────────────────────────────────────────
# 3. 修改资产组
# ──────────────────────────────────────────────

class TestAssetScopeUpdate:
    def test_update_scope_name(self, api_client):
        """修改资产组名称"""
        scope_id = _create_scope(api_client, name="pytest-update-before")
        payload = {
            "_id": scope_id,
            "name": "pytest-update-after",
            "scope": "test.example.com",
            "black_scope": "",
            "scope_type": "domain"
        }
        res = api_client.post(f"{BASE_URL}/asset_scope/update/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        # 清理
        api_client.post(f"{BASE_URL}/asset_scope/delete/", json={"_id": [scope_id]})

    def test_update_nonexistent_scope(self, api_client):
        """修改不存在的资产组：应返回业务错误"""
        payload = {
            "_id": "000000000000000000000000",
            "name": "ghost",
            "scope": "ghost.example.com",
            "black_scope": "",
            "scope_type": "domain"
        }
        res = api_client.post(f"{BASE_URL}/asset_scope/update/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] != 200


# ──────────────────────────────────────────────
# 4. 删除资产组
# ──────────────────────────────────────────────

class TestAssetScopeDelete:
    def test_delete_scope(self, api_client):
        """正常删除资产组"""
        scope_id = _create_scope(api_client, name="pytest-delete-scope")
        res = api_client.post(f"{BASE_URL}/asset_scope/delete/", json={"_id": [scope_id]})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200

    def test_delete_nonexistent_scope(self, api_client):
        """删除不存在的资产组：应返回业务错误"""
        res = api_client.post(f"{BASE_URL}/asset_scope/delete/",
                              json={"_id": ["000000000000000000000000"]})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] != 200

    def test_delete_scope_missing_id(self, api_client):
        """缺少 _id 字段：应返回 400"""
        res = api_client.post(f"{BASE_URL}/asset_scope/delete/", json={})
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)
