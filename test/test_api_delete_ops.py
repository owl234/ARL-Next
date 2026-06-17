import pytest
from conftest import BASE_URL

class TestDeleteOps:
    """覆盖各模块的 DELETE 操作"""

class TestDeleteOps:
    """覆盖各模块的基础 DELETE 操作"""

    def test_delete_asset_domain(self, api_client):
        res = api_client.post(f"{BASE_URL}/asset_domain/delete/", json={"_id": ["0"*24]})
        assert res.status_code == 200

    def test_delete_asset_ip(self, api_client):
        res = api_client.post(f"{BASE_URL}/asset_ip/delete/", json={"_id": ["0"*24]})
        assert res.status_code == 200

    def test_delete_asset_site(self, api_client):
        res = api_client.post(f"{BASE_URL}/asset_site/delete/", json={"_id": ["0"*24]})
        assert res.status_code == 200

    def test_delete_asset_wih(self, api_client):
        res = api_client.post(f"{BASE_URL}/asset_wih/delete/", json={"_id": ["0"*24]})
        assert res.status_code == 200

    def test_delete_cert(self, api_client):
        res = api_client.post(f"{BASE_URL}/cert/delete/", json={"_id": ["0"*24]})
        assert res.status_code == 200

    def test_delete_domain(self, api_client):
        res = api_client.post(f"{BASE_URL}/domain/delete/", json={"_id": ["0"*24]})
        assert res.status_code == 200

    def test_delete_site(self, api_client):
        res = api_client.post(f"{BASE_URL}/site/delete/", json={"_id": ["0"*24]})
        assert res.status_code == 200

    def test_delete_ip(self, api_client):
        res = api_client.post(f"{BASE_URL}/ip/delete/", json={"_id": ["0"*24]})
        assert res.status_code == 200

    def test_delete_fileleak(self, api_client):
        res = api_client.post(f"{BASE_URL}/fileleak/delete/", json={"_id": ["0"*24]})
        assert res.status_code == 200

    def test_delete_nuclei_result(self, api_client):
        res = api_client.post(f"{BASE_URL}/nuclei_result/delete/", json={"_id": ["0"*24]})
        assert res.status_code == 200

    def test_delete_vuln(self, api_client):
        res = api_client.post(f"{BASE_URL}/vuln/delete/", json={"_id": ["0"*24]})
        assert res.status_code == 200

    def test_delete_wih(self, api_client):
        res = api_client.post(f"{BASE_URL}/wih/delete/", json={"_id": ["0"*24]})
        assert res.status_code == 200

    def test_delete_fingerprint(self, api_client):
        res = api_client.post(f"{BASE_URL}/fingerprint/delete/", json={"_id": ["0"*24]})
        assert res.status_code == 200

