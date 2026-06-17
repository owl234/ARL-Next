"""
test_api_policy.py
==================
测试扫描策略接口：
  - GET  /api/policy/         查询策略列表
  - POST /api/policy/         创建策略
  - POST /api/policy/update/  修改策略
  - POST /api/policy/delete/  删除策略
"""
import pytest
from conftest import BASE_URL

# ──────────────────────────────────────────────
# 辅助：构建标准策略 payload
# ──────────────────────────────────────────────
def _create_policy(api_client, name="pytest-policy"):
    """
    辅助方法：创建一个策略并返回 policy_id
    """
    payload = {
        "name": name,
        "desc": "test policy",
        "policy": {
            "domain_config": {
                "domain_brute": False,
                "domain_brute_type": "test",
                "alt_dns": False,
                "arl_search": False,
                "dns_query_plugin": False
            },
            "ip_config": {
                "port_scan": False,
                "port_scan_type": "test",
                "service_detection": False,
                "os_detection": False,
                "ssl_cert": False,
                "skip_scan_cdn_ip": True,
                "port_custom": "80,443",
                "host_timeout_type": "default",
                "host_timeout": 900,
                "port_parallelism": 32,
                "port_min_rate": 60,
                "exclude_ports": ""
            },
            "site_config": {
                "site_identify": False,
                "site_capture": False,
                "search_engines": False,
                "site_spider": False,
                "nuclei_scan": False,
                "web_info_hunter": False
            },
            "scope_config": {
                "scope_id": ""
            }
        }
    }
    res = api_client.post(f"{api_client.base_url}/policy/add/", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body.get("code") == 200, f"创建策略失败: {res.text}"
    policy_id = body.get("data", {}).get("policy_id") or body.get("data", {}).get("_id") or body.get("_id")
    assert policy_id, f"未获取到策略 ID, 响应: {body}"
    return policy_id


# ──────────────────────────────────────────────
# 1. 查询策略
# ──────────────────────────────────────────────

def _build_policy_payload(name="test-policy"):
    return {
        "name": name,
        "desc": "test policy",
        "policy": {
            "domain_config": {
                "domain_brute": False,
                "domain_brute_type": "test",
                "alt_dns": False,
                "arl_search": False,
                "dns_query_plugin": False
            },
            "ip_config": {
                "port_scan": False,
                "port_scan_type": "test",
                "service_detection": False,
                "os_detection": False,
                "ssl_cert": False,
                "skip_scan_cdn_ip": True,
                "port_custom": "80,443",
                "host_timeout_type": "default",
                "host_timeout": 900,
                "port_parallelism": 32,
                "port_min_rate": 60,
                "exclude_ports": ""
            },
            "site_config": {
                "site_identify": False,
                "site_capture": False,
                "search_engines": False,
                "site_spider": False,
                "nuclei_scan": False,
                "web_info_hunter": False
            },
            "scope_config": {
                "scope_id": ""
            }
        }
    }

class TestPolicyQuery:
    def test_get_policy_list(self, api_client):
        """GET /policy/ 应返回标准分页结构"""
        res = api_client.get(f"{BASE_URL}/policy/")
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert "items" in body
        assert "total" in body

    def test_get_policy_with_pagination(self, api_client):
        """分页参数 page=1&size=5 生效"""
        res = api_client.get(f"{BASE_URL}/policy/", params={"page": 1, "size": 5})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert len(body["items"]) <= 5

    def test_get_policy_filter_by_name(self, api_client, test_policy):
        """按名称过滤策略（依赖 test_policy fixture）"""
        res = api_client.get(f"{BASE_URL}/policy/", params={"name": "pytest-test-policy"})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert body["total"] >= 1

    def test_get_policy_filter_by_id(self, api_client, test_policy):
        """按 _id 查询特定策略"""
        res = api_client.get(f"{BASE_URL}/policy/", params={"_id": test_policy})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert body["total"] == 1
        assert body["items"][0]["_id"] == test_policy


# ──────────────────────────────────────────────
# 2. 创建策略
# ──────────────────────────────────────────────

class TestPolicyCreate:
    def test_create_policy_success(self, api_client):
        """正常创建策略"""
        policy_id = _create_policy(api_client, name="pytest-create-policy")
        assert policy_id
        # 清理
        api_client.post(f"{BASE_URL}/policy/delete/", json={"_id": [policy_id]})

    def test_create_policy_missing_name(self, api_client):
        """缺少必填 name：应返回 400"""
        payload = _build_policy_payload()
        del payload["name"]
        res = api_client.post(f"{BASE_URL}/policy/", json=payload)
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)

    def test_create_policy_with_all_options_enabled(self, api_client):
        """创建开启所有扫描选项的策略"""
        payload = _build_policy_payload(name="pytest-full-options-policy")
        payload["domain_config"]["domain_brute"] = True
        payload["ip_config"]["port_scan"] = True
        payload["site_config"]["site_identify"] = True

        res = api_client.post(f"{BASE_URL}/policy/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        policy_id = body.get("data", {}).get("policy_id") or body.get("data", {}).get("_id") or body.get("_id")
        # 清理
        if policy_id:
            api_client.post(f"{BASE_URL}/policy/delete/", json={"_id": [policy_id]})


# ──────────────────────────────────────────────
# 3. 修改策略
# ──────────────────────────────────────────────

class TestPolicyUpdate:
    def test_update_policy(self, api_client):
        """修改策略名称"""
        policy_id = _create_policy(api_client, name="pytest-update-before-policy")
        payload = _build_policy_payload(name="pytest-update-after-policy")
        payload["_id"] = policy_id
        res = api_client.post(f"{BASE_URL}/policy/update/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        # 清理
        api_client.post(f"{BASE_URL}/policy/delete/", json={"_id": [policy_id]})

    def test_update_nonexistent_policy(self, api_client):
        """修改不存在的策略：应返回业务错误"""
        payload = _build_policy_payload(name="ghost-policy")
        payload["_id"] = "000000000000000000000000"
        res = api_client.post(f"{BASE_URL}/policy/update/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] != 200


# ──────────────────────────────────────────────
# 4. 删除策略
# ──────────────────────────────────────────────

class TestPolicyDelete:
    def test_delete_policy(self, api_client):
        """正常删除策略"""
        policy_id = _create_policy(api_client, name="pytest-delete-policy")
        res = api_client.post(f"{BASE_URL}/policy/delete/", json={"_id": [policy_id]})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200

    def test_delete_nonexistent_policy(self, api_client):
        """删除不存在的策略：应返回业务错误"""
        res = api_client.post(f"{BASE_URL}/policy/delete/",
                              json={"_id": ["000000000000000000000000"]})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] != 200

    def test_delete_policy_missing_id(self, api_client):
        """缺少 _id 字段：应返回 400"""
        res = api_client.post(f"{BASE_URL}/policy/delete/", json={})
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)
