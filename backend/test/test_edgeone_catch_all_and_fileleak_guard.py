import os
import sys
import unittest
from unittest.mock import MagicMock, patch

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
npoc_dir = os.path.join(backend_dir, 'ARL-NPoC')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if npoc_dir not in sys.path:
    sys.path.insert(0, npoc_dir)

import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999

import pymongo
pymongo.MongoClient = MagicMock()

from app.modules import DomainInfo, IPInfo, PortInfo, SiteAutoTag
from app.services.autoTag import auto_tag, is_infra_fingerprint
from app.services.checkHTTP import CheckHTTP
from app.services.commonTask import WebSiteFetch
from app.services.fetchSite import FetchSite
from app.services.fileLeak import FileLeak, URL
from app.tasks.domain import FindSite, ScanPort
from app.utils.cdn import (
    get_cdn_name_by_cname,
    get_cdn_name_by_domain_strict,
    get_cdn_name_by_headers,
)


def _mock_response(status_code, content=b"", headers=None, text=None):
    resp = MagicMock()
    resp.status_code = status_code
    resp.content = content
    resp.headers = dict(headers or {})
    resp.text = text if text is not None else content.decode("utf-8", errors="ignore")
    resp.iter_content = MagicMock(return_value=[content] if content else [])
    resp.close = MagicMock()
    return resp


class TestCheckHTTPAndFetchSiteGatewayReject(unittest.TestCase):
    """验证 418 / 421 边缘网关拒收响应的分层准入与跳过 6 路径回退探测"""

    def test_empty_418_and_421_dropped_without_gateway_fallback(self):
        for code in (418, 421):
            checker = CheckHTTP(["https://demo.pages.dnsoe7.com/"])
            called_urls = []

            def fake_http_req(url, **kwargs):
                called_urls.append(url)
                return _mock_response(
                    code,
                    content=b"",
                    headers={"Server": "TencentEdgeOne", "EO-LOG-UUID": "12345"},
                )

            with patch("app.utils.http_req", side_effect=fake_http_req):
                checker.work("https://demo.pages.dnsoe7.com/")

            self.assertEqual(called_urls, ["https://demo.pages.dnsoe7.com/"])
            self.assertNotIn("https://demo.pages.dnsoe7.com/", checker.checkout_map)

    def test_non_empty_418_and_421_passed_without_gateway_fallback(self):
        for code in (418, 421):
            checker = CheckHTTP(["https://demo.pages.dnsoe7.com/"])
            called_urls = []

            def fake_http_req(url, **kwargs):
                called_urls.append(url)
                return _mock_response(
                    code,
                    content=b"<html><title>EdgeOne Reject</title></html>",
                    headers={"Server": "TencentEdgeOne", "Content-Type": "text/html"},
                )

            with patch("app.utils.http_req", side_effect=fake_http_req):
                checker.work("https://demo.pages.dnsoe7.com/")

            self.assertEqual(called_urls, ["https://demo.pages.dnsoe7.com/"])
            self.assertIn("https://demo.pages.dnsoe7.com/", checker.checkout_map)
            self.assertEqual(checker.checkout_map["https://demo.pages.dnsoe7.com/"]["status"], code)

    def test_fetch_site_skips_gateway_fallback_and_favicon_on_empty_418(self):
        fetcher = FetchSite(["https://demo.pages.dnsoe7.com"])
        called_urls = []

        def fake_http_req(url, **kwargs):
            called_urls.append(url)
            return _mock_response(
                418,
                content=b"",
                headers={"Server": "TencentEdgeOne", "EO-LOG-UUID": "99999"},
            )

        with patch("app.utils.http_req", side_effect=fake_http_req), \
             patch("app.services.fetchSite.fetch_favicon") as mock_fav, \
             patch("app.services.fetchSite.finger_identify", return_value=["EdgeOne"]), \
             patch("app.utils.get_ip", return_value=["198.51.100.10"]):
            fetcher.work("https://demo.pages.dnsoe7.com")

        self.assertEqual(called_urls, ["https://demo.pages.dnsoe7.com"])
        mock_fav.assert_not_called()
        self.assertEqual(len(fetcher.site_info_list), 1)
        self.assertEqual(fetcher.site_info_list[0]["status"], 418)


class TestInfraFingerprintAndAutoTag(unittest.TestCase):
    """验证基础设施指纹判定单一事实源与 AutoTag 协同"""

    def test_infra_fingerprints_recognized_and_business_fingerprints_preserved(self):
        infra_names = [
            "EdgeOne",
            "TencentEdgeOne",
            "Alibaba Cloud CDN",
            "Alibaba Cloud (Block Page)",
            "Amazon CloudFront",
            "Amazon ALB",
            "Azure Edge Network",
            "ByteDance-CDN",
            "Cloudflare",
            "Akamai",
            "Fastly",
            "CDN77",
            "ArvanCloud",
            "Nginx",
            "OpenResty",
        ]
        for name in infra_names:
            self.assertTrue(is_infra_fingerprint(name), f"{name} 应被识别为基础设施指纹")
            self.assertTrue(WebSiteFetch._is_infra_fingerprint(name))

        business_names = [
            "Nacos",
            "Grafana",
            "Spring Boot",
            "Spring Cloud Gateway",
            "Citrix Access Gateway",
            "WordPress",
            "Apache Shiro",
            "GitLab",
        ]
        for name in business_names:
            self.assertFalse(is_infra_fingerprint(name), f"{name} 不应误判为基础设施指纹")
            self.assertFalse(WebSiteFetch._is_infra_fingerprint(name))

    def test_auto_tag_marks_empty_418_edgeone_invalid_but_protects_business_finger(self):
        edgeone_site = {
            "site": "https://a.pages.dnsoe7.com",
            "hostname": "a.pages.dnsoe7.com",
            "status": 418,
            "title": "",
            "body_length": 0,
            "headers": "HTTP/1.1 418 I'm a Teapot\nServer: TencentEdgeOne\nEO-LOG-UUID: 123",
            "finger": [{"name": "EdgeOne"}],
        }
        auto_tag(edgeone_site)
        self.assertIn(SiteAutoTag.INVALID, edgeone_site.get("tag", []))

        nacos_site = {
            "site": "https://nacos.example.com",
            "hostname": "nacos.example.com",
            "status": 404,
            "title": "",
            "body_length": 0,
            "headers": "HTTP/1.1 404 Not Found\nServer: nginx",
            "finger": [{"name": "EdgeOne"}, {"name": "Nacos"}],
        }
        auto_tag(nacos_site)
        self.assertNotIn(SiteAutoTag.INVALID, nacos_site.get("tag", []))


class TestCrossIPCatchAllAndDownstreamBlocking(unittest.TestCase):
    """验证跨 IP CDN 去噪聚类、首道防线裸 IP 首项修复及全下游阻断"""

    def _make_fetcher(self, site_info_list, options=None):
        fetcher = WebSiteFetch.__new__(WebSiteFetch)
        fetcher.task_id = "task_edgeone_test"
        fetcher.sites = [s["site"] for s in site_info_list]
        fetcher.site_info_list = list(site_info_list)
        fetcher.available_sites = [s["site"] for s in site_info_list]
        fetcher.catch_all_sites = set()
        fetcher._poc_sites = None
        fetcher.options = options if options is not None else {}
        fetcher.search_engines_result = {}
        fetcher.page_url_set = set()
        fetcher.wih_record_set = set()
        fetcher.wih_domain_set = set()
        return fetcher

    def test_control_probe_backfills_domain_when_bare_ip_comes_first(self):
        sites = [
            {
                "site": "http://203.0.113.10:8080",
                "hostname": "203.0.113.10",
                "ip": "203.0.113.10",
                "status": 418,
                "title": "",
                "body_length": 0,
                "simhash": "0",
                "http_server": "TencentEdgeOne",
                "finger": [{"name": "EdgeOne"}],
            },
            {
                "site": "http://a.pages.dnsoe7.com:8080",
                "hostname": "a.pages.dnsoe7.com",
                "ip": "203.0.113.10",
                "status": 418,
                "title": "",
                "body_length": 0,
                "simhash": "0",
                "http_server": "TencentEdgeOne",
                "finger": [{"name": "EdgeOne"}],
            },
        ]
        fetcher = self._make_fetcher(sites)
        probed_hostnames = []

        def fake_fetch_ref(ip, scheme, port, hostname):
            probed_hostnames.append(hostname)
            return {"status": 418, "title": "", "body_length": 0, "simhash": "0"}

        with patch.object(WebSiteFetch, "_fetch_catch_all_reference", side_effect=fake_fetch_ref):
            fetcher.filter_catch_all_by_control_probe()

        self.assertEqual(probed_hostnames, ["a.pages.dnsoe7.com"])
        self.assertEqual(len(fetcher.site_info_list), 1)
        self.assertTrue(fetcher.site_info_list[0]["is_catch_all"])
        self.assertEqual(len(fetcher.poc_sites), 0)

    def test_cross_ip_cdn_clustering_converges_multi_ip_418_and_blocks_all_downstream(self):
        # 构造 50 个分布在 25 个不同 EdgeOne IP 上的同质非空 418 站点（每 IP 仅 2 条，单 IP 无法触发 >=10）
        sites = []
        for i in range(50):
            ip = f"198.51.100.{i // 2 + 1}"
            sites.append({
                "site": f"https://sub{i}.pages.dnsoe7.com",
                "hostname": f"sub{i}.pages.dnsoe7.com",
                "ip": ip,
                "status": 418,
                "title": "",
                "body_length": 128,
                "simhash": "1234567890",
                "http_server": "TencentEdgeOne",
                "finger": [{"name": "EdgeOne"}],
            })

        # 额外加入 1 个具备真实业务指纹的站点，确保绝对不被误杀
        sites.append({
            "site": "https://portal.example.com",
            "hostname": "portal.example.com",
            "ip": "198.51.100.200",
            "status": 403,
            "title": "控制台登录",
            "body_length": 128,
            "simhash": "1234567890",
            "http_server": "TencentEdgeOne",
            "finger": [{"name": "EdgeOne"}, {"name": "Nacos"}],
        })

        fetcher = self._make_fetcher(sites)
        with patch.object(WebSiteFetch, "_fetch_catch_all_reference", return_value=None):
            fetcher.filter_catch_all_by_control_probe()
            fetcher.filter_catch_all_vhost()

        # 50 个 EdgeOne 默认 418 站跨 25 IP 收敛为 1 条代表站点 + 1 条特赦业务站 = 2 条
        self.assertEqual(len(fetcher.site_info_list), 2)
        rep = next(s for s in fetcher.site_info_list if s["site"].startswith("https://sub"))
        self.assertTrue(rep.get("is_catch_all"))
        self.assertIn("catch_all_vhost", rep.get("tag", []))
        self.assertEqual(rep["catch_all_evidence"]["mode"], "cross_ip_cluster")
        self.assertEqual(rep["catch_all_evidence"]["cluster_size"], 50)
        self.assertEqual(rep["catch_all_evidence"]["distinct_ips"], 25)

        # 下游 poc_sites、site_spider、WIH 均只放行特赦业务站，阻断全部 50 个 catch-all 站点
        self.assertEqual(fetcher.poc_sites, {"https://portal.example.com"})

        with patch("app.services.site_spider_thread", return_value={}) as mock_spider:
            fetcher.site_spider()
            mock_spider.assert_called_once_with([["https://portal.example.com"]])

        with patch("app.services.run_wih", return_value=[]) as mock_wih:
            fetcher.run_web_info_hunter()
            mock_wih.assert_called_once_with(["https://portal.example.com"])

    def test_all_catch_all_skips_spider_and_wih_completely(self):
        sites = [
            {
                "site": f"https://edge{i}.pages.dnsoe7.com",
                "hostname": f"edge{i}.pages.dnsoe7.com",
                "ip": f"203.0.113.{i + 1}",
                "status": 418,
                "title": "",
                "body_length": 0,
                "simhash": "",
                "http_server": "TencentEdgeOne",
                "finger": [{"name": "EdgeOne"}],
            }
            for i in range(15)
        ]
        fetcher = self._make_fetcher(sites)
        with patch.object(WebSiteFetch, "_fetch_catch_all_reference", return_value=None):
            fetcher.filter_catch_all_by_control_probe()
            fetcher.filter_catch_all_vhost()

        self.assertEqual(len(fetcher.site_info_list), 1)
        self.assertEqual(len(fetcher.poc_sites), 0)

        with patch("app.services.site_spider_thread") as mock_spider, \
             patch("app.services.run_wih") as mock_wih:
            fetcher.site_spider()
            fetcher.run_web_info_hunter()
            mock_spider.assert_not_called()
            mock_wih.assert_not_called()


class TestFileLeakDualBaselineAbort(unittest.TestCase):
    """验证 FileLeak 双随机基线探针命中网关拒收/不可达码时的早退行为"""

    def test_early_aborts_on_consistent_unroutable_baseline_codes(self):
        for code in (400, 418, 421, 502, 503, 504):
            targets = [
                URL("https://demo.pages.dnsoe7.com/.env", ".env"),
                URL("https://demo.pages.dnsoe7.com/.git/config", ".git/config"),
            ]
            fl = FileLeak("https://demo.pages.dnsoe7.com", targets, concurrency=2)
            called_urls = []

            def fake_http_req(url, *args, **kwargs):
                called_urls.append(url)
                return _mock_response(code, content=b"", headers={"Server": "TencentEdgeOne"})

            with patch("app.utils.http_req", side_effect=fake_http_req):
                pages = fl.run()

            self.assertTrue(fl.abort_scan, f"状态码 {code} 双基线一致应触发早退")
            self.assertEqual(len(called_urls), 2, f"状态码 {code} 早退后仅允许发送 2 次基线探针")
            self.assertEqual(len(pages), 0)

    def test_does_not_abort_on_403_404_500_or_inconsistent_baseline(self):
        for code in (403, 404, 500):
            targets = [URL("https://app.example.com/.env", ".env")]
            fl = FileLeak("https://app.example.com", targets, concurrency=2)
            called_urls = []

            def fake_http_req(url, *args, **kwargs):
                called_urls.append(url)
                return _mock_response(code, content=b"denied", headers={"Server": "nginx"})

            with patch("app.utils.http_req", side_effect=fake_http_req):
                fl.run()

            self.assertFalse(fl.abort_scan, f"状态码 {code} 不应触发早退")
            self.assertGreaterEqual(len(called_urls), 3)

        # 不一致基线（502 vs 404）也不应触发早退
        targets = [URL("https://flaky.example.com/.env", ".env")]
        fl = FileLeak("https://flaky.example.com", targets, concurrency=2)
        seq = iter([
            _mock_response(502, content=b"bad gw"),
            _mock_response(404, content=b"not found"),
            _mock_response(404, content=b"not found"),
        ])
        with patch("app.utils.http_req", side_effect=lambda *a, **kw: next(seq)):
            fl.run()
        self.assertFalse(fl.abort_scan)


class TestCDNEdgeOneDetectionAndFindSite(unittest.TestCase):
    """验证 EdgeOne CDN 特征识别与域名任务中跳过 CDN 裸 IP 探测"""

    def test_edgeone_headers_and_strict_domain_rules(self):
        self.assertEqual(
            get_cdn_name_by_headers({"Server": "TencentEdgeOne", "EO-LOG-UUID": "111"}),
            "腾讯云 CDN/EdgeOne",
        )
        self.assertEqual(
            get_cdn_name_by_headers({"EO-Cache-Status": "MISS"}),
            "腾讯云 CDN/EdgeOne",
        )
        self.assertEqual(
            get_cdn_name_by_domain_strict("tenant.example.pages.dnsoe7.com"),
            "腾讯云 CDN/EdgeOne",
        )
        self.assertEqual(get_cdn_name_by_domain_strict("dnsoe9.com"), "腾讯云 CDN/EdgeOne")
        self.assertEqual(get_cdn_name_by_domain_strict("dnsv2.com"), "腾讯云 CDN/EdgeOne")
        self.assertEqual(get_cdn_name_by_domain_strict("a.edgeone.site"), "腾讯云 CDN/EdgeOne")
        self.assertEqual(get_cdn_name_by_cname("sample.example.cdns.edgeone.site"), "腾讯云 CDN/EdgeOne")

        # 严格域名规则不得误伤普通公司含 dns/edge/cdn 的业务域
        self.assertEqual(get_cdn_name_by_domain_strict("dns.corp.com"), "")
        self.assertEqual(get_cdn_name_by_domain_strict("edge-api.corp.com"), "")
        self.assertEqual(get_cdn_name_by_domain_strict("cdn-admin.corp.com"), "")

    def test_scan_port_recognizes_a_record_edgeone_domain_as_cdn(self):
        dom = DomainInfo(
            domain="tenant.example.pages.dnsoe7.com",
            type="A",
            record=["198.51.100.10"],
            ips=["198.51.100.10"],
        )
        scanner = ScanPort([dom], option={"ports": "80,443", "skip_scan_cdn_ip": True})
        with patch("app.utils.get_ip_asn", return_value={}):
            cdn_name = scanner.get_cdn_name("198.51.100.10", dom)
        self.assertEqual(cdn_name, "腾讯云 CDN/EdgeOne")

    def test_find_site_skips_bare_ip_for_cdn_with_domains_but_keeps_non_cdn_and_ip_only(self):
        port_80 = PortInfo(port_id=80, service_name="http", version="", product="")
        port_443 = PortInfo(port_id=443, service_name="https", version="", product="")

        cdn_with_domain = IPInfo(
            ip="198.51.100.10",
            port_info=[port_80, port_443],
            os_info={},
            domain=["a.pages.dnsoe7.com"],
            cdn_name="腾讯云 CDN/EdgeOne",
        )
        cdn_ip_only = IPInfo(
            ip="198.51.100.11",
            port_info=[port_443],
            os_info={},
            domain=[],
            cdn_name="腾讯云 CDN/EdgeOne",
        )
        normal_with_domain = IPInfo(
            ip="192.0.2.10",
            port_info=[port_80],
            os_info={},
            domain=["app.example.com"],
            cdn_name="",
        )

        urls = FindSite([cdn_with_domain, cdn_ip_only, normal_with_domain])._build()

        # CDN + 域名：保留域名探测，跳过裸 IP
        self.assertIn("http://a.pages.dnsoe7.com", urls)
        self.assertIn("https://a.pages.dnsoe7.com", urls)
        self.assertNotIn("http://198.51.100.10", urls)
        self.assertNotIn("https://198.51.100.10", urls)

        # 纯 IP 目标（无域名）：仍保留 IP 探测
        self.assertIn("https://198.51.100.11", urls)

        # 非 CDN + 域名：同时保留域名与裸 IP 探测
        self.assertIn("http://app.example.com", urls)
        self.assertIn("http://192.0.2.10", urls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
