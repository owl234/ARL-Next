"""
test_api_data_query.py
======================
测试所有通用数据查询接口（只读，不修改数据）：
  - GET /api/site/
  - GET /api/domain/
  - GET /api/ip/
  - GET /api/url/
  - GET /api/cert/
  - GET /api/service/
  - GET /api/fileleak/
  - GET /api/vuln/
  - GET /api/nuclei_result/
  - GET /api/wih/
  - GET /api/asset_domain/
  - GET /api/asset_ip/
  - GET /api/asset_site/
  - GET /api/asset_wih/
  - GET /api/cip/
  - GET /api/fingerprint/
  - GET /api/npoc_service/
"""
import pytest
from conftest import BASE_URL


# ──────────────────────────────────────────────
# 辅助：通用分页结构断言
# ──────────────────────────────────────────────
def assert_paginated_response(body, expected_code=200):
    assert body.get("code") == expected_code, f"code 不匹配: {body}"
    assert "items" in body, f"缺少 items 字段: {body}"
    assert "total" in body, f"缺少 total 字段: {body}"
    assert "page" in body, f"缺少 page 字段: {body}"
    assert "size" in body, f"缺少 size 字段: {body}"
    assert isinstance(body["items"], list), "items 应为列表"
    assert isinstance(body["total"], int), "total 应为整数"


# ──────────────────────────────────────────────
# 1. 扫描结果数据查询
# ──────────────────────────────────────────────

class TestSiteQuery:
    def test_get_site_list(self, api_client):
        """GET /site/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/site/")
        assert res.status_code == 200
        assert_paginated_response(res.json())

    def test_get_site_pagination(self, api_client):
        """站点分页：size=5"""
        res = api_client.get(f"{BASE_URL}/site/", params={"page": 1, "size": 5})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert len(body["items"]) <= 5

    def test_get_site_filter_by_status(self, api_client):
        """按 status 过滤站点"""
        res = api_client.get(f"{BASE_URL}/site/", params={"status": "200"})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200


class TestDomainQuery:
    def test_get_domain_list(self, api_client):
        """GET /domain/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/domain/")
        assert res.status_code == 200
        assert_paginated_response(res.json())

    def test_get_domain_pagination(self, api_client):
        """域名分页：size=5"""
        res = api_client.get(f"{BASE_URL}/domain/", params={"page": 1, "size": 5})
        assert res.status_code == 200
        body = res.json()
        assert len(body["items"]) <= 5


class TestIPQuery:
    def test_get_ip_list(self, api_client):
        """GET /ip/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/ip/")
        assert res.status_code == 200
        assert_paginated_response(res.json())

    def test_get_ip_filter_by_type(self, api_client):
        """按 ip_type 过滤"""
        res = api_client.get(f"{BASE_URL}/ip/", params={"ip_type": "public"})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200


class TestURLQuery:
    def test_get_url_list(self, api_client):
        """GET /url/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/url/")
        assert res.status_code == 200
        assert_paginated_response(res.json())


class TestCertQuery:
    def test_get_cert_list(self, api_client):
        """GET /cert/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/cert/")
        assert res.status_code == 200
        assert_paginated_response(res.json())


class TestServiceQuery:
    def test_get_service_list(self, api_client):
        """GET /service/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/service/")
        assert res.status_code == 200
        assert_paginated_response(res.json())


class TestFileleakQuery:
    def test_get_fileleak_list(self, api_client):
        """GET /fileleak/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/fileleak/")
        assert res.status_code == 200
        assert_paginated_response(res.json())


class TestVulnQuery:
    def test_get_vuln_list(self, api_client):
        """GET /vuln/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/vuln/")
        assert res.status_code == 200
        assert_paginated_response(res.json())


class TestNucleiResultQuery:
    def test_get_nuclei_result_list(self, api_client):
        """GET /nuclei_result/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/nuclei_result/")
        assert res.status_code == 200
        assert_paginated_response(res.json())


class TestWihQuery:
    def test_get_wih_list(self, api_client):
        """GET /wih/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/wih/")
        assert res.status_code == 200
        assert_paginated_response(res.json())


# ──────────────────────────────────────────────
# 2. 资产库查询
# ──────────────────────────────────────────────

class TestAssetDomainQuery:
    def test_get_asset_domain_list(self, api_client):
        """GET /asset_domain/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/asset_domain/")
        assert res.status_code == 200
        assert_paginated_response(res.json())

    def test_filter_asset_domain_by_scope(self, api_client, test_scope):
        """按 scope_id 过滤资产域名"""
        res = api_client.get(f"{BASE_URL}/asset_domain/", params={"scope_id": test_scope})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200


class TestAssetIPQuery:
    def test_get_asset_ip_list(self, api_client):
        """GET /asset_ip/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/asset_ip/")
        assert res.status_code == 200
        assert_paginated_response(res.json())


class TestAssetSiteQuery:
    def test_get_asset_site_list(self, api_client):
        """GET /asset_site/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/asset_site/")
        assert res.status_code == 200
        assert_paginated_response(res.json())


class TestAssetWihQuery:
    def test_get_asset_wih_list(self, api_client):
        """GET /asset_wih/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/asset_wih/")
        assert res.status_code == 200
        assert_paginated_response(res.json())


# ──────────────────────────────────────────────
# 3. 其他数据查询
# ──────────────────────────────────────────────

class TestCipQuery:
    def test_get_cip_list(self, api_client):
        """GET /cip/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/cip/")
        assert res.status_code == 200
        assert_paginated_response(res.json())


class TestFingerprintQuery:
    def test_get_fingerprint_list(self, api_client):
        """GET /fingerprint/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/fingerprint/")
        assert res.status_code == 200
        assert_paginated_response(res.json())

    def test_get_fingerprint_filter_by_name(self, api_client):
        """按指纹名称模糊过滤"""
        res = api_client.get(f"{BASE_URL}/fingerprint/", params={"name": "nginx"})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200


class TestNpocServiceQuery:
    def test_get_npoc_service_list(self, api_client):
        """GET /npoc_service/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/npoc_service/")
        assert res.status_code == 200
        assert_paginated_response(res.json())


# ──────────────────────────────────────────────
# 4. 通用查询参数测试（以 site 为例）
# ──────────────────────────────────────────────

class TestCommonQueryParams:
    def test_order_asc(self, api_client):
        """升序排列：order=+_id"""
        res = api_client.get(f"{BASE_URL}/site/", params={"order": "+_id", "size": 5})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200

    def test_order_desc(self, api_client):
        """降序排列：order=-_id"""
        res = api_client.get(f"{BASE_URL}/site/", params={"order": "-_id", "size": 5})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200

    def test_page_out_of_range(self, api_client):
        """page 超出范围（超大页码）：应返回空 items 而非报错"""
        res = api_client.get(f"{BASE_URL}/site/", params={"page": 999999, "size": 10})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert body["items"] == []  # 越界页应为空列表

    def test_size_negative_fallback(self, api_client):
        """size 为负数时，应 fallback 为默认值 10"""
        res = api_client.get(f"{BASE_URL}/site/", params={"page": 1, "size": -1})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert body["size"] == 10  # 负数 size 应被修正为 10

    def test_size_max_cap(self, api_client):
        """size 超过 100000 时应被截断"""
        res = api_client.get(f"{BASE_URL}/site/", params={"page": 1, "size": 999999})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert body["size"] <= 100000
