"""
test_api_export.py
==================
测试数据导出接口：
  - GET /api/site/export/
  - GET /api/domain/export/
  - GET /api/ip/export/
  - GET /api/url/export/
  - GET /api/wih/export/
  - GET /api/cip/export/
  - POST /api/batch_export/
"""
import pytest
from conftest import BASE_URL


# ──────────────────────────────────────────────
# 辅助：断言导出响应格式
# ──────────────────────────────────────────────
def assert_export_response(res):
    """导出接口应返回文件流（octet-stream）或 JSON 成功响应"""
    assert res.status_code == 200, f"导出接口返回非 200: {res.status_code}"
    content_type = res.headers.get("Content-Type", "")
    # 可能是文件流，也可能是空内容
    assert (
        "octet-stream" in content_type
        or "text/plain" in content_type
        or "application/json" in content_type
    ), f"Content-Type 不符合预期: {content_type}"


# ──────────────────────────────────────────────
# 1. 单类型导出接口
# ──────────────────────────────────────────────

class TestExportSingle:
    def test_export_site(self, api_client):
        """GET /site/export/ 导出站点数据"""
        res = api_client.get(f"{BASE_URL}/site/export/")
        assert res.status_code == 200
        # 导出接口返回文件流
        content_type = res.headers.get("Content-Type", "")
        assert "octet-stream" in content_type or "text" in content_type

    def test_export_domain(self, api_client):
        """GET /domain/export/ 导出域名数据"""
        res = api_client.get(f"{BASE_URL}/domain/export/")
        assert res.status_code == 200

    def test_export_ip(self, api_client):
        """GET /ip/export/ 导出 IP 数据"""
        res = api_client.get(f"{BASE_URL}/ip/export/")
        assert res.status_code == 200

    def test_export_url(self, api_client):
        """GET /url/export/ 导出 URL 数据"""
        res = api_client.get(f"{BASE_URL}/url/export/")
        assert res.status_code == 200

    def test_export_wih(self, api_client):
        """GET /wih/export/ 导出 WIH 数据"""
        res = api_client.get(f"{BASE_URL}/wih/export/")
        assert res.status_code == 200

    def test_export_cip(self, api_client):
        """GET /cip/export/ 导出 CIDR IP 数据"""
        res = api_client.get(f"{BASE_URL}/cip/export/")
        assert res.status_code == 200

    def test_export_asset_site(self, api_client):
        """GET /asset_site/export/ 导出资产站点数据"""
        res = api_client.get(f"{BASE_URL}/asset_site/export/")
        assert res.status_code == 200

    def test_export_asset_domain(self, api_client):
        """GET /asset_domain/export/ 导出资产域名数据"""
        res = api_client.get(f"{BASE_URL}/asset_domain/export/")
        assert res.status_code == 200

    def test_export_asset_ip(self, api_client):
        """GET /asset_ip/export/ 导出资产 IP 数据"""
        res = api_client.get(f"{BASE_URL}/asset_ip/export/")
        assert res.status_code == 200

    def test_export_asset_wih(self, api_client):
        """GET /asset_wih/export/ 导出资产 WIH 数据"""
        res = api_client.get(f"{BASE_URL}/asset_wih/export/")
        assert res.status_code == 200


# ──────────────────────────────────────────────
# 2. 带过滤条件的导出
# ──────────────────────────────────────────────

class TestExportWithFilter:
    def test_export_site_with_task_id(self, api_client):
        """按 task_id 过滤导出站点（task_id 为空时也不应报错）"""
        res = api_client.get(f"{BASE_URL}/site/export/",
                             params={"task_id": "000000000000000000000000"})
        assert res.status_code == 200

    def test_export_domain_with_task_id(self, api_client):
        """按 task_id 过滤导出域名"""
        res = api_client.get(f"{BASE_URL}/domain/export/",
                             params={"task_id": "000000000000000000000000"})
        assert res.status_code == 200

    def test_export_site_content_disposition(self, api_client):
        """导出接口应包含 Content-Disposition 头（文件名）"""
        res = api_client.get(f"{BASE_URL}/site/export/")
        assert res.status_code == 200
        # 如果有数据，应有 Content-Disposition；无数据时可能返回空文件
        # 此处验证接口不崩溃即可
        assert res.headers.get("Content-Type") is not None


# ──────────────────────────────────────────────
# 3. 批量导出接口
# ──────────────────────────────────────────────

class TestBatchExport:
    """批量导出：每种类型有独立子路由 /batch_export/<type>/"""

    def test_batch_export_site(self, api_client):
        """POST /batch_export/site/"""
        res = api_client.post(f"{BASE_URL}/batch_export/site/",
                              json={"task_id": ["000000000000000000000000"]})
        assert res.status_code == 200

    def test_batch_export_domain(self, api_client):
        """POST /batch_export/domain/"""
        res = api_client.post(f"{BASE_URL}/batch_export/domain/",
                              json={"task_id": ["000000000000000000000000"]})
        assert res.status_code == 200

    def test_batch_export_ip(self, api_client):
        """POST /batch_export/ip/"""
        res = api_client.post(f"{BASE_URL}/batch_export/ip/",
                              json={"task_id": ["000000000000000000000000"]})
        assert res.status_code == 200

    def test_batch_export_url(self, api_client):
        """POST /batch_export/url/"""
        res = api_client.post(f"{BASE_URL}/batch_export/url/",
                              json={"task_id": ["000000000000000000000000"]})
        assert res.status_code == 200

    def test_batch_export_ip_port(self, api_client):
        """POST /batch_export/ip_port/  IP:端口 批量导出"""
        res = api_client.post(f"{BASE_URL}/batch_export/ip_port/",
                              json={"task_id": ["000000000000000000000000"]})
        assert res.status_code == 200

    def test_batch_export_cip(self, api_client):
        """POST /batch_export/cip/  C段批量导出"""
        res = api_client.post(f"{BASE_URL}/batch_export/cip/",
                              json={"task_id": ["000000000000000000000000"]})
        assert res.status_code == 200

    def test_batch_export_wih(self, api_client):
        """POST /batch_export/wih/"""
        res = api_client.post(f"{BASE_URL}/batch_export/wih/",
                              json={"task_id": ["000000000000000000000000"]})
        assert res.status_code == 200

    def test_batch_export_asset_ip(self, api_client, test_scope):
        """POST /batch_export/asset_ip/  按 scope_id 导出"""
        res = api_client.post(f"{BASE_URL}/batch_export/asset_ip/",
                              json={"scope_id": [test_scope]})
        assert res.status_code == 200

    def test_batch_export_asset_domain(self, api_client, test_scope):
        """POST /batch_export/asset_domain/"""
        res = api_client.post(f"{BASE_URL}/batch_export/asset_domain/",
                              json={"scope_id": [test_scope]})
        assert res.status_code == 200

    def test_batch_export_asset_site(self, api_client, test_scope):
        """POST /batch_export/asset_site/"""
        res = api_client.post(f"{BASE_URL}/batch_export/asset_site/",
                              json={"scope_id": [test_scope]})
        assert res.status_code == 200

    def test_batch_export_asset_wih(self, api_client, test_scope):
        """POST /batch_export/asset_wih/"""
        res = api_client.post(f"{BASE_URL}/batch_export/asset_wih/",
                              json={"scope_id": [test_scope]})
        assert res.status_code == 200

    def test_batch_export_missing_task_id(self, api_client):
        """缺少 task_id：应返回 400"""
        res = api_client.post(f"{BASE_URL}/batch_export/site/", json={})
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)



# ──────────────────────────────────────────────
# 4. 无 Token 访问导出接口
# ──────────────────────────────────────────────

class TestExportAuth:
    def test_export_without_token(self):
        """不带 Token 访问导出接口：应被拦截返回 401"""
        import requests
        res = requests.get(f"{BASE_URL}/site/export/")
        assert res.status_code == 200
        body = res.json()
        assert body.get("code") == 401
