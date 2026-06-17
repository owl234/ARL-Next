import os
import pytest
import requests

# ============================================================
# 测试环境基础配置
# 支持通过环境变量 ARL_BASE_URL / ARL_USERNAME / ARL_PASSWORD 动态替换
# 默认指向本地 Docker 启动的后端服务
# ============================================================
BASE_URL = os.environ.get("ARL_BASE_URL", "http://localhost:5003/api")
USERNAME = os.environ.get("ARL_USERNAME", "admin")
PASSWORD = os.environ.get("ARL_PASSWORD", "waifyy@0608")


# ============================================================
# 全局 HTTP 客户端 fixture（session 级别，整个测试套件只登录一次）
# ============================================================
@pytest.fixture(scope="session")
def api_client():
    """
    全局 HTTP 客户端 fixture。
    - 在所有测试开始前自动登录并获取 Token
    - 将带有 Token 的 session 交给后续测试用例使用
    - 测试结束后自动退出登录并关闭 session
    """
    session = requests.Session()
    login_url = f"{BASE_URL}/user/login"

    res = session.post(login_url, json={"username": USERNAME, "password": PASSWORD})
    assert res.status_code == 200, f"全局前置条件失败：无法连接后端 ({BASE_URL}) 或登录失败"

    token = res.json().get("data", {}).get("token")
    assert token is not None, "全局前置条件失败：未获取到 Token"

    # 将 Token 注入全局 Session Header
    session.headers.update({"Token": token})
    # 挂载 base_url 方便子用例调用
    session.base_url = BASE_URL

    yield session

    # 测试结束后退出登录
    try:
        session.get(f"{BASE_URL}/user/logout")
    except Exception:
        pass
    session.close()


# ============================================================
# 资产组（scope）fixture：创建一个测试用 Domain 类型资产组
# ============================================================
@pytest.fixture(scope="session")
def test_scope(api_client):
    """
    创建一个供测试使用的资产组，测试结束后自动删除。
    """
    payload = {
        "name": "pytest-test-scope",
        "scope": "pytest-test.example.com",
        "black_scope": "",
        "scope_type": "domain"
    }
    # 尝试先删除同名数据，避免冲突
    try:
        res = api_client.get(f"{api_client.base_url}/asset_scope/", params={"name": "pytest-test-scope"})
        existing_id = res.json().get("items", [{}])[0].get("_id")
        if existing_id:
            api_client.post(f"{api_client.base_url}/asset_scope/delete/", json={"_id": [existing_id]})
    except Exception:
        pass
        
    res = api_client.post(f"{api_client.base_url}/asset_scope/", json=payload)
    assert res.status_code == 200, f"创建测试资产组失败: {res.text}"
    data = res.json()
    # 提取 scope_id
    scope_id = data.get("data", {}).get("scope_id") or data.get("data", {}).get("_id") or data.get("_id")
    assert scope_id, f"未获取到资产组 ID, 响应: {data}"

    yield scope_id

    # 测试结束后删除资产组
    try:
        api_client.post(f"{api_client.base_url}/asset_scope/delete/", json={"_id": [scope_id]})
    except Exception:
        pass


# ============================================================
# 策略（policy）fixture：创建一个测试用扫描策略
# ============================================================
@pytest.fixture(scope="session")
def test_policy(api_client):
    """
    创建一个供测试使用的扫描策略，测试结束后自动删除。
    """
    payload = {
        "name": "pytest-test-policy",
        "desc": "由 pytest 自动创建的测试策略",
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
    # 尝试先删除同名数据
    try:
        res = api_client.get(f"{api_client.base_url}/policy/", params={"name": "pytest-test-policy"})
        existing_id = res.json().get("items", [{}])[0].get("_id")
        if existing_id:
            api_client.post(f"{api_client.base_url}/policy/delete/", json={"_id": [existing_id]})
    except Exception:
        pass
        
    res = api_client.post(f"{api_client.base_url}/policy/add/", json=payload)
    assert res.status_code == 200, f"创建测试策略失败: {res.text}"
    data = res.json()
    policy_id = data.get("data", {}).get("_id") or data.get("_id")
    assert policy_id, f"未获取到策略 ID, 响应: {data}"

    yield policy_id

    # 测试结束后删除策略
    try:
        api_client.post(f"{api_client.base_url}/policy/delete/", json={"_id": [policy_id]})
    except Exception:
        pass