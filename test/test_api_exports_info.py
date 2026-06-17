import pytest
from conftest import BASE_URL

class TestExportsAndInfo:
    """覆盖各个模块的 GET 导出和 Info 接口"""

    def test_export_asset_domain(self, api_client):
        res = api_client.get(f"{BASE_URL}/asset_domain/export/")
        assert res.status_code == 200

    def test_export_asset_ip(self, api_client):
        res = api_client.get(f"{BASE_URL}/asset_ip/export/")
        assert res.status_code == 200

    def test_export_asset_ip_ip(self, api_client):
        res = api_client.get(f"{BASE_URL}/asset_ip/export_ip/")
        assert res.status_code == 200

    def test_export_asset_ip_domain(self, api_client):
        res = api_client.get(f"{BASE_URL}/asset_ip/export_domain/")
        assert res.status_code == 200

    def test_export_asset_site(self, api_client):
        res = api_client.get(f"{BASE_URL}/asset_site/export/")
        assert res.status_code == 200

    def test_export_asset_wih(self, api_client):
        res = api_client.get(f"{BASE_URL}/asset_wih/export/")
        assert res.status_code == 200

    def test_export_cip(self, api_client):
        res = api_client.get(f"{BASE_URL}/cip/export/")
        assert res.status_code == 200

    def test_export_domain(self, api_client):
        res = api_client.get(f"{BASE_URL}/domain/export/")
        assert res.status_code == 200

    def test_export_fingerprint(self, api_client):
        res = api_client.get(f"{BASE_URL}/fingerprint/export/")
        assert res.status_code == 200

    def test_export_ip(self, api_client):
        res = api_client.get(f"{BASE_URL}/ip/export/")
        assert res.status_code == 200

    def test_export_ip_domain(self, api_client):
        res = api_client.get(f"{BASE_URL}/ip/export_domain/")
        assert res.status_code == 200

    def test_export_ip_ip(self, api_client):
        res = api_client.get(f"{BASE_URL}/ip/export_ip/")
        assert res.status_code == 200

    def test_export_site(self, api_client):
        res = api_client.get(f"{BASE_URL}/site/export/")
        assert res.status_code == 200

    def test_export_url(self, api_client):
        res = api_client.get(f"{BASE_URL}/url/export/")
        assert res.status_code == 200

    def test_export_wih(self, api_client):
        res = api_client.get(f"{BASE_URL}/wih/export/")
        assert res.status_code == 200

    def test_console_info(self, api_client):
        res = api_client.get(f"{BASE_URL}/console/info")
        assert res.status_code == 200

    def test_image_get(self, api_client):
        res = api_client.get(f"{BASE_URL}/image/000000000000000000000000/notfound.jpg")
        assert res.status_code in [200, 404]

