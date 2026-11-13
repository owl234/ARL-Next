"""
backend/test/integration/conftest.py
====================================
在线 API 集成测试的最小公共夹具。

- 仅依赖 requests，不导入 app、不连 Mongo，采集阶段零副作用。
- 默认打本地直连后端；生产网关（Nginx 5173）或远端主机一律走环境变量覆盖。
- 后端服务不可达时整组用例自动 skip，保证默认 `pytest backend/test` 不变红。

环境变量：
  ARL_API_BASE  API 基址（含 /api 前缀），默认 http://127.0.0.1:5000/api
  ARL_USERNAME  登录账号，默认 admin
  ARL_PASSWORD  登录密码，默认 arlpass（新部署已改为首次启动随机生成，请从 /tmp/arl_initial_admin_password 或 ARL_ADMIN_PASSWORD 获取后传入）
"""
import os

import pytest
import requests

BASE_URL = os.environ.get("ARL_API_BASE", "http://127.0.0.1:5000/api").rstrip("/")
USERNAME = os.environ.get("ARL_USERNAME", "admin")
PASSWORD = os.environ.get("ARL_PASSWORD", "arlpass")


class APIClient(requests.Session):
    """带 base_url 属性的 Session，用例沿用 api_client.get/post 写法。"""

    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.headers.update({"Content-Type": "application/json"})


@pytest.fixture(scope="module")
def api_client():
    """登录一次并复用 Token；服务不可达则 skip 整个模块。"""
    client = APIClient(BASE_URL)
    try:
        res = client.post(
            f"{BASE_URL}/user/login",
            json={"username": USERNAME, "password": PASSWORD},
            timeout=10,
        )
    except requests.RequestException as e:
        pytest.skip(f"后端服务不可达 ({BASE_URL})，跳过在线集成测试: {e}")
    body = res.json()
    token = (body.get("data") or {}).get("token")
    if res.status_code != 200 or body.get("code") != 200 or not token:
        pytest.skip(f"登录失败 ({BASE_URL})，跳过在线集成测试: {body}")
    client.headers.update({"Token": token})
    yield client
    try:
        client.get(f"{BASE_URL}/user/logout", timeout=10)
    except requests.RequestException:
        pass


def _create_scope(client, name, scope):
    res = client.post(
        f"{BASE_URL}/asset_scope/",
        json={"name": name, "scope": scope, "scope_type": "domain"},
        timeout=15,
    )
    body = res.json()
    scope_id = (body.get("data") or {}).get("scope_id") or (body.get("data") or {}).get("_id")
    assert scope_id, f"创建资产组失败: {body}"
    return scope_id


def _create_policy(client, name):
    payload = {
        "name": name,
        "desc": "integration fixture policy",
        "policy": {
            "domain_config": {
                "domain_brute": False,
                "domain_brute_type": "test",
                "alt_dns": False,
                "arl_search": False,
                "dns_query_plugin": False,
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
                "exclude_ports": "",
            },
            "site_config": {
                "site_identify": False,
                "site_capture": False,
                "search_engines": False,
                "site_spider": False,
                "nuclei_scan": False,
                "web_info_hunter": False,
            },
            "scope_config": {"scope_id": ""},
        },
    }
    res = client.post(f"{BASE_URL}/policy/add/", json=payload, timeout=15)
    body = res.json()
    policy_id = (body.get("data") or {}).get("policy_id") or (body.get("data") or {}).get("_id")
    assert policy_id, f"创建策略失败: {body}"
    return policy_id


@pytest.fixture(scope="module")
def test_scope(api_client):
    """预置一个 pytest-test-scope 资产组，模块结束后级联删除。"""
    scope_id = _create_scope(api_client, "pytest-test-scope", "pytest-fixture.example.com")
    yield scope_id
    try:
        api_client.post(f"{BASE_URL}/asset_scope/delete/", json={"scope_id": [scope_id]}, timeout=15)
    except requests.RequestException:
        pass


@pytest.fixture(scope="module")
def test_policy(api_client):
    """预置一个 pytest-test-policy 策略，模块结束后删除。"""
    policy_id = _create_policy(api_client, "pytest-test-policy")
    yield policy_id
    try:
        api_client.post(f"{BASE_URL}/policy/delete/", json={"policy_id": [policy_id]}, timeout=15)
    except requests.RequestException:
        pass
