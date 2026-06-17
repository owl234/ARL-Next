"""
test_api_auth.py
================
测试用户认证相关接口：
  - POST /api/user/login        登录
  - GET  /api/user/logout       退出
  - POST /api/user/change_pass  修改密码
  - 无 Token 访问受保护接口
"""
import requests
from conftest import BASE_URL, USERNAME, PASSWORD


# ──────────────────────────────────────────────
# 1. 登录测试
# ──────────────────────────────────────────────

def test_login_success(api_client):
    """正确账号密码可成功登录并获取 Token"""
    res = requests.post(f"{BASE_URL}/user/login",
                        json={"username": USERNAME, "password": PASSWORD})
    assert res.status_code == 200
    body = res.json()
    assert body.get("code") == 200
    assert body.get("message") == "success"
    data = body.get("data", {})
    assert "token" in data
    assert data["token"]  # Token 不为空
    # 登录成功会覆盖后端的 Token 记录，为了不影响后续全局 api_client 的使用，将新 Token 喂给它
    api_client.headers.update({"Token": data["token"]})


def test_login_wrong_password():
    """错误密码登录：HTTP 200 但业务 code=401"""
    res = requests.post(f"{BASE_URL}/user/login",
                        json={"username": USERNAME, "password": "totally_wrong_password_12345"})
    assert res.status_code == 200
    body = res.json()
    assert body.get("code") == 401


def test_login_empty_username():
    """空用户名登录：业务层拒绝"""
    res = requests.post(f"{BASE_URL}/user/login",
                        json={"username": "", "password": PASSWORD})
    assert res.status_code == 200
    body = res.json()
    # 业务层返回 401（找不到用户）
    assert body.get("code") in (400, 401)


def test_login_missing_fields():
    """缺少必填字段：flask-restx 返回 400"""
    res = requests.post(f"{BASE_URL}/user/login", json={})
    assert res.status_code in (400, 401) or res.json().get("code") in (400, 401)


# ──────────────────────────────────────────────
# 2. 无 Token 访问受保护接口
# ──────────────────────────────────────────────

def test_access_without_token():
    """不携带 Token 访问受保护接口，应被拦截返回 401"""
    session = requests.Session()  # 全新无 Token 的 session
    res = session.get(f"{BASE_URL}/task/")
    body = res.json()
    assert body.get("code") == 401


def test_access_with_invalid_token():
    """携带无效 Token 访问，应被拦截返回 401"""
    session = requests.Session()
    session.headers.update({"Token": "this_is_an_invalid_token_abc123"})
    res = session.get(f"{BASE_URL}/task/")
    body = res.json()
    assert body.get("code") == 401


# ──────────────────────────────────────────────
# 3. 携带 Token 访问
# ──────────────────────────────────────────────

def test_access_with_token(api_client):
    """携带有效 Token 访问受保护接口，应成功返回 200"""
    res = api_client.get(f"{api_client.base_url}/task/")
    assert res.status_code == 200
    body = res.json()
    assert body.get("code") == 200


# ──────────────────────────────────────────────
# 4. 修改密码测试
# ──────────────────────────────────────────────

def test_change_pass_mismatch(api_client):
    """新密码与确认密码不一致时应返回 301"""
    payload = {
        "old_password": PASSWORD,
        "new_password": "newpass123",
        "check_password": "differentpass456"
    }
    res = api_client.post(f"{api_client.base_url}/user/change_pass", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body.get("code") == 301


def test_change_pass_wrong_old(api_client):
    """旧密码错误时应返回 303"""
    payload = {
        "old_password": "completely_wrong_old_pass",
        "new_password": "newpass123",
        "check_password": "newpass123"
    }
    res = api_client.post(f"{api_client.base_url}/user/change_pass", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body.get("code") == 303


def test_change_pass_empty_new(api_client):
    """新密码为空时应返回 302"""
    payload = {
        "old_password": PASSWORD,
        "new_password": "",
        "check_password": ""
    }
    res = api_client.post(f"{api_client.base_url}/user/change_pass", json=payload)
    assert res.status_code == 200
    body = res.json()
    assert body.get("code") in (302, 400)


# ──────────────────────────────────────────────
# 5. 退出登录
# ──────────────────────────────────────────────

def test_logout(api_client):
    """退出登录接口应返回 200（api_client fixture 在 session 末尾会调用，此处仅验证接口可达）"""
    # 注意：此处不真正退出，仅验证接口返回格式正确
    # 如果退出，后续测试将失效；真正的退出在 conftest 的 yield 后执行
    res = requests.Session().get(f"{BASE_URL}/user/logout")
    # 未带 Token 退出也不应崩溃
    assert res.status_code == 200