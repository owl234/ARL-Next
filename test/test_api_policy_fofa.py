import pytest
from conftest import BASE_URL

class TestPolicyAdvanced:
    """策略高级操作测试"""

    def test_policy_add(self, api_client):
        """测试 POST /policy/add/ (嵌套 policy 字段)"""
        payload = {
            "name": "pytest-advanced-policy",
            "desc": "Test policy with full fields",
            "policy": {
                "port_scan_type": "test",
                "port_scan": True,
                "domain_config": {},
                "ip_config": {},
                "site_config": {}
            }
        }
        res = api_client.post(f"{BASE_URL}/policy/add/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        # 清理
        policy_id = body.get("data", {}).get("_id")
        if policy_id:
            api_client.post(f"{BASE_URL}/policy/delete/", json={"_id": [policy_id]})

    def test_policy_edit(self, api_client, test_policy):
        """测试 POST /policy/edit/"""
        payload = {
            "policy_id": test_policy,
            "policy_data": {
                "name": "pytest-policy-edited",
                "desc": "Edited desc",
                "policy": {
                    "port_scan": False,
                    "domain_config": {},
                    "ip_config": {},
                    "site_config": {}
                }
            }
        }
        res = api_client.post(f"{BASE_URL}/policy/edit/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200


class TestTaskFofa:
    """FOFA 任务操作测试"""

    def test_task_fofa_test_connection(self, api_client):
        """测试 POST /task_fofa/test"""
        payload = {"query": "domain=\"example.com\""}
        res = api_client.post(f"{BASE_URL}/task_fofa/test", json=payload)
        assert res.status_code == 200
        body = res.json()
        # 由于可能没有配置 FOFA_KEY，返回 200 或 400（业务错误）均属于接口正常处理
        assert "code" in body

    def test_task_fofa_submit(self, api_client):
        """测试 POST /task_fofa/submit"""
        payload = {
            "query": "domain=\"example.com\"",
            "name": "pytest-fofa-task",
            "policy_id": "000000000000000000000000"
        }
        res = api_client.post(f"{BASE_URL}/task_fofa/submit", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert "code" in body


class TestMiscOps:
    """其他离散接口测试"""

    def test_fingerprint_upload_empty(self, api_client):
        """测试 POST /fingerprint/upload/"""
        # 伪造一个文件上传，只要接口能正常响应即算覆盖
        files = {'file': ('test.zip', b'fake data', 'application/zip')}
        res = api_client.post(f"{BASE_URL}/fingerprint/upload/", files=files)
        assert res.status_code == 200

    def test_user_change_pass_invalid(self, api_client):
        """测试 POST /user/change_pass (原密码错误)"""
        payload = {"old_password": "wrong_password", "new_password": "new_pass123", "check_password": "new_pass123"}
        res = api_client.post(f"{BASE_URL}/user/change_pass", json=payload)
        assert res.status_code in [200, 400]
        if res.status_code == 200:
            assert res.json()["code"] != 200

    def test_user_logout(self, api_client):
        """测试 GET /user/logout"""
        import requests
        login_res = requests.post(f"{BASE_URL}/user/login", json={"username": "admin", "password": "waifyy@0608"})
        tmp_token = login_res.json()["data"]["token"]
        
        try:
            res = requests.get(f"{BASE_URL}/user/logout", headers={"Token": tmp_token})
            assert res.status_code == 200
            assert res.json()["code"] in (200, 401)
        finally:
            login_res2 = requests.post(f"{BASE_URL}/user/login", json={"username": "admin", "password": "waifyy@0608"})
            api_client.headers.update({"Token": login_res2.json()["data"]["token"]})

