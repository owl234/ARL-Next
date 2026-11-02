import os
import sys
import unittest
from unittest.mock import MagicMock, patch
try:
    import mongomock
except ImportError:
    mongomock = None
import requests
import ssl

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
npoc_dir = os.path.join(backend_dir, 'ARL-NPoC')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if npoc_dir not in sys.path:
    sys.path.insert(0, npoc_dir)

import app.config
app.config.get_system_config_value = lambda k, d: d

from app.modules import IPInfo, PortInfo
from app.tasks.domain import FindSite
from app.utils.conn import (
    create_resilient_ssl_context,
    ResilientSSLAdapter,
    _resilient_ssl_adapter,
    http_req
)
from app.services.checkHTTP import CheckHTTP, check_http, GATEWAY_PORTS, GATEWAY_PATHS
from app.services.commonTask import sync_service_from_site, WebSiteFetch
from app.services.fetchSite import FetchSite
from app.tasks.ip import IPTask
from app.services.domainSiteUpdate import DomainSiteUpdate
from app import utils


class TestFindSiteBuild(unittest.TestCase):
    """
    第一性原理测试：验证 FindSite._build 在生成域名候选的同时，
    必须追加物理 IP 候选 {ip}:{port}，确保无 SNI / 虚拟主机的网关设备不被丢弃。
    """

    def test_build_with_domains_and_ips(self):
        port_80 = PortInfo(port_id=80, service_name="http", version="", product="")
        port_443 = PortInfo(port_id=443, service_name="https", version="", product="")
        port_8443 = PortInfo(port_id=8443, service_name="unknown", version="", product="")
        info = IPInfo(
            ip="192.168.1.1",
            port_info=[port_80, port_443, port_8443],
            os_info={},
            domain=["gateway.local"],
            cdn_name=""
        )

        finder = FindSite([info])
        urls = finder._build()

        # 域名候选
        self.assertIn("http://gateway.local", urls)
        self.assertIn("https://gateway.local", urls)
        self.assertIn("http://gateway.local:8443", urls)
        self.assertIn("https://gateway.local:8443", urls)

        # 物理 IP 候选 (P0 核心需求)
        self.assertIn("http://192.168.1.1", urls)
        self.assertIn("https://192.168.1.1", urls)
        self.assertIn("http://192.168.1.1:8443", urls)
        self.assertIn("https://192.168.1.1:8443", urls)

    def test_build_ip_only_without_domains(self):
        """当 IP 无关联域名时，仍能正确构建物理 IP 候选"""
        port_8080 = PortInfo(port_id=8080, service_name="http", version="", product="")
        info = IPInfo(
            ip="10.0.0.1",
            port_info=[port_8080],
            os_info={},
            domain=[],
            cdn_name=""
        )

        finder = FindSite([info])
        urls = finder._build()

        self.assertIn("http://10.0.0.1:8080", urls)
        self.assertIn("https://10.0.0.1:8080", urls)
        self.assertEqual(len(urls), 2)

    def test_build_with_dict_structures(self):
        """兼容字典格式输入的 ip_info_list"""
        dict_info = {
            "ip": "172.16.0.1",
            "domain": ["internal.corp"],
            "port_info": [
                {"port_id": 80},
                {"port_id": 443}
            ]
        }
        finder = FindSite([dict_info])
        urls = finder._build()

        self.assertIn("http://internal.corp", urls)
        self.assertIn("https://internal.corp", urls)
        self.assertIn("http://172.16.0.1", urls)
        self.assertIn("https://172.16.0.1", urls)

    def test_build_ipv6_formatting(self):
        """IPv6 地址以中括号包裹"""
        port_80 = PortInfo(port_id=80, service_name="http", version="", product="")
        info = IPInfo(
            ip="2001:db8::1",
            port_info=[port_80],
            os_info={},
            domain=[],
            cdn_name=""
        )
        finder = FindSite([info])
        urls = finder._build()
        self.assertIn("http://[2001:db8::1]", urls)

    def test_build_handles_string_ports_and_bracketed_ipv6(self):
        """字符串 port_id 也能正确识别 80/443，已有中括号的 IPv6 不会出现双括号"""
        dict_info = {
            "ip": "[2001:db8::2]",
            "domain": ["v6.example.com"],
            "port_info": [
                {"port_id": "80"},
                {"port_id": "443"},
                {"port_id": "8443"}
            ]
        }
        finder = FindSite([dict_info])
        urls = finder._build()

        self.assertIn("http://v6.example.com", urls)
        self.assertIn("https://v6.example.com", urls)
        self.assertIn("http://v6.example.com:8443", urls)
        self.assertIn("https://v6.example.com:8443", urls)
        # 验证 IPv6 无双中括号
        self.assertIn("http://[2001:db8::2]", urls)
        self.assertIn("https://[2001:db8::2]", urls)
        self.assertIn("http://[2001:db8::2]:8443", urls)
        self.assertIn("https://[2001:db8::2]:8443", urls)
        # 确保无多余的带 :80 或 :443
        self.assertNotIn("http://[2001:db8::2]:80", urls)
        self.assertNotIn("https://[2001:db8::2]:443", urls)

    def test_build_ignores_empty_and_none_domain_and_ip(self):
        """当 domain 或 ip 包含 None 或空字符串时，不应产生畸形 URL (如 http:// 或 http://None)"""
        info = {
            "ip": None,
            "domain": ["", None, "   "],
            "port_info": [{"port_id": 80}, {"port_id": 443}]
        }
        finder = FindSite([info])
        urls = finder._build()
        self.assertEqual(urls, [])



class TestResilientSSL(unittest.TestCase):
    """
    第一性原理测试：验证 ResilientSSLAdapter 与 resilient_ssl=True 在 http_req 中的支持
    """

    def test_create_resilient_ssl_context(self):
        ctx = create_resilient_ssl_context()
        self.assertFalse(ctx.check_hostname)
        self.assertEqual(ctx.verify_mode, ssl.CERT_NONE)

        if hasattr(ssl, 'TLSVersion') and hasattr(ssl.TLSVersion, 'TLSv1_2'):
            self.assertEqual(ctx.maximum_version, ssl.TLSVersion.TLSv1_2)

        if hasattr(ssl, 'OP_IGNORE_UNEXPECTED_EOF'):
            self.assertTrue(ctx.options & ssl.OP_IGNORE_UNEXPECTED_EOF)

        legacy_connect = getattr(ssl, 'OP_LEGACY_SERVER_CONNECT', 0x4)
        self.assertTrue(ctx.options & legacy_connect)

    def test_resilient_ssl_adapter_initialization(self):
        adapter = ResilientSSLAdapter()
        self.assertIsNotNone(adapter.ssl_context)
        self.assertFalse(adapter.ssl_context.check_hostname)

    @patch.object(requests.adapters.HTTPAdapter, 'send')
    def test_http_req_with_resilient_ssl(self, mock_send):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.url = "https://127.0.0.1:8443"
        mock_response.is_redirect = False
        mock_response.headers = {}
        mock_response._content = b"OK"
        mock_response._content_consumed = False
        mock_response.raw = None
        mock_send.return_value = mock_response

        # resilient_ssl=True 正常调度而不抛出任何 unexpected keyword argument 异常
        resp = http_req("https://127.0.0.1:8443", resilient_ssl=True, timeout=2)
        self.assertEqual(resp.status_code, 200)


class TestCheckHTTP(unittest.TestCase):
    """
    第一性原理测试：验证 checkHTTP 的超时配置、放宽 400 校验、SSL 重试及网关回退探测
    """

    def setUp(self):
        self.checker = CheckHTTP(["https://192.168.1.1:8443"])

    def test_default_timeout_is_6_6(self):
        """超时必须为 (6, 6)"""
        self.assertEqual(self.checker.timeout, (6, 6))

    def test_relaxed_400_validation_with_server_header(self):
        """400 响应若带 Server 头，应视为存活站点"""
        mock_conn = MagicMock()
        mock_conn.status_code = 400
        mock_conn.headers = {"Server": "Apache/2.4.41", "Content-Type": "text/plain"}
        mock_conn.content = b"Bad Request"

        with patch('app.utils.http_req', return_value=mock_conn):
            result = self.checker.check("http://192.168.1.1:8080")
            self.assertIsNotNone(result)
            self.assertEqual(result["status"], 400)

    def test_relaxed_400_validation_with_html_structure(self):
        """400 响应若带 HTML 结构，应视为存活站点"""
        mock_conn = MagicMock()
        mock_conn.status_code = 400
        mock_conn.headers = {"Content-Type": "text/html; charset=utf-8"}
        mock_conn.content = b"<html><head><title>Bad Request</title></head><body>Error 400</body></html>"

        with patch('app.utils.http_req', return_value=mock_conn):
            result = self.checker.check("http://192.168.1.1:8080")
            self.assertIsNotNone(result)
            self.assertEqual(result["status"], 400)

    def test_barren_400_validation_rejected(self):
        """400 响应若既无 Server 头又无 HTML 结构和 ETag/Date，则过滤抛弃"""
        mock_conn = MagicMock()
        mock_conn.status_code = 400
        mock_conn.headers = {}
        mock_conn.content = b""

        with patch('app.utils.http_req', return_value=mock_conn):
            result = self.checker.check("http://192.168.1.1:8080")
            self.assertIsNone(result)

    def test_filtered_status_codes_410_422_5xx(self):
        for code in (410, 422, 502, 503):
            mock_conn = MagicMock()
            mock_conn.status_code = code
            mock_conn.headers = {"Server": "nginx"}
            mock_conn.content = b"Error"

            with patch('app.utils.http_req', return_value=mock_conn):
                result = self.checker.check("http://192.168.1.1:8080")
                self.assertIsNone(result, f"Status code {code} must return None")

    def test_auto_retry_with_resilient_ssl_on_ssl_error(self):
        """捕获 SSLError 时自动使用 resilient_ssl=True 重试"""
        calls = []

        def side_effect(url, **kwargs):
            calls.append(kwargs.get("resilient_ssl", False))
            if not kwargs.get("resilient_ssl", False):
                raise requests.exceptions.SSLError("SSL Handshake Failure")
            mock_res = MagicMock()
            mock_res.status_code = 200
            mock_res.headers = {"Server": "Embedded-Gateway"}
            mock_res.content = b"OK"
            return mock_res

        with patch('app.utils.http_req', side_effect=side_effect):
            res = self.checker.check("https://192.168.1.1:8443")
            self.assertIsNotNone(res)
            self.assertEqual(res["status"], 200)
            self.assertEqual(calls, [False, True])

    def test_gateway_fallback_probing_on_root_failure(self):
        """当高危网关端口根路径失败或返回错误时，自动探测备用网关路径"""
        checker = CheckHTTP(["https://192.168.1.1:8443/"])

        def side_effect(url, **kwargs):
            if url == "https://192.168.1.1:8443/":
                # 根路径返回 404
                mock_404 = MagicMock()
                mock_404.status_code = 404
                mock_404.headers = {}
                mock_404.content = b"Not Found"
                return mock_404
            elif url == "https://192.168.1.1:8443/login.html":
                # 网关登录路径返回 200
                mock_200 = MagicMock()
                mock_200.status_code = 200
                mock_200.headers = {"Content-Type": "text/html"}
                mock_200.content = b"<html><title>Gateway Login</title></html>"
                return mock_200
            else:
                raise requests.exceptions.ConnectionError("Connection Refused")

        with patch('app.utils.http_req', side_effect=side_effect):
            checker.work("https://192.168.1.1:8443/")
            self.assertIn("https://192.168.1.1:8443/", checker.checkout_map)
            self.assertEqual(checker.checkout_map["https://192.168.1.1:8443/"]["status"], 200)

    def test_no_gateway_fallback_when_root_succeeds(self):
        """当根路径返回 200 OK 时，不触发网关回退探测"""
        checker = CheckHTTP(["http://192.168.1.1:80/"])
        called_urls = []

        def side_effect(url, **kwargs):
            called_urls.append(url)
            mock_200 = MagicMock()
            mock_200.status_code = 200
            mock_200.headers = {"Server": "nginx"}
            mock_200.content = b"Welcome"
            return mock_200

        with patch('app.utils.http_req', side_effect=side_effect):
            checker.work("http://192.168.1.1:80/")
            self.assertEqual(called_urls, ["http://192.168.1.1:80/"])
            self.assertEqual(checker.checkout_map["http://192.168.1.1:80/"]["status"], 200)

    def test_http_url_with_https_in_domain_does_not_retry_ssl(self):
        """当 HTTP 目标的域名包含 https 关键字（如 http://https-service.internal）发生错误时，不应误判为 HTTPS 触发弹性重试"""
        checker = CheckHTTP(["http://https-service.internal:8080/"])
        call_kwargs = []

        def side_effect(url, **kwargs):
            call_kwargs.append(kwargs)
            raise requests.exceptions.ConnectionError("Connection refused")

        with patch('app.utils.http_req', side_effect=side_effect):
            with self.assertRaises(requests.exceptions.ConnectionError):
                checker.check("http://https-service.internal:8080/")

        # 仅调用一次，没有弹性 SSL 重试
        self.assertEqual(len(call_kwargs), 1)
        self.assertFalse(call_kwargs[0].get("resilient_ssl", False))

    def test_plain_http_sent_to_https_port_is_rejected(self):
        """当 HTTP 探测命中 HTTPS 端口并返回 400 'The plain HTTP request was sent to HTTPS port' 时，应被判定为无效站点"""
        checker = CheckHTTP(["http://192.168.1.1:443/"])
        mock_resp = MagicMock()
        mock_resp.status_code = 400
        mock_resp.headers = {"Server": "nginx", "Content-Type": "text/html"}
        mock_resp.content = b"<html><head><title>400 The plain HTTP request was sent to HTTPS port</title></head></html>"

        with patch('app.utils.http_req', return_value=mock_resp):
            res = checker.check("http://192.168.1.1:443/")
            self.assertIsNone(res)

    def test_gateway_fallback_accepts_401_and_403(self):
        """当网关路径返回 401 Unauthorized 或 403 Forbidden 时，应被判定为有效存活网关"""
        for code in (401, 403):
            checker = CheckHTTP(["https://192.168.1.1:8443/"])

            def side_effect(url, **kwargs):
                if url == "https://192.168.1.1:8443/":
                    mock_fail = MagicMock()
                    mock_fail.status_code = 404
                    mock_fail.headers = {}
                    mock_fail.content = b"Not Found"
                    return mock_fail
                elif url == "https://192.168.1.1:8443/admin/":
                    mock_auth = MagicMock()
                    mock_auth.status_code = code
                    mock_auth.headers = {"Server": "Gateway-Admin", "WWW-Authenticate": "Basic realm=login"}
                    mock_auth.content = b"Auth Required"
                    return mock_auth
                else:
                    raise requests.exceptions.ConnectionError("Refused")

            with patch('app.utils.http_req', side_effect=side_effect):
                checker.work("https://192.168.1.1:8443/")
                self.assertIn("https://192.168.1.1:8443/", checker.checkout_map)
                self.assertEqual(checker.checkout_map["https://192.168.1.1:8443/"]["status"], code)
                self.assertEqual(checker.checkout_map["https://192.168.1.1:8443/"]["url"], "https://192.168.1.1:8443/")


class TestSyncServiceFromSite(unittest.TestCase):
    """
    第一性原理测试：验证 sync_service_from_site 的反哺校准机制
    """

    def setUp(self):
        if mongomock is not None:
            self.mock_client = mongomock.MongoClient()
            self.mock_db = self.mock_client.test_db
            self._is_mongomock = True
        else:
            import uuid
            self._is_mongomock = False
            self._prefix = f"test_tmp_{uuid.uuid4().hex[:8]}_"
            self.real_db = utils.conn_db("user").database

            class DbProxy:
                def __init__(self, real_db, prefix):
                    self.real_db = real_db
                    self.prefix = prefix
                    self.created_cols = []

                def __getitem__(self, item):
                    target = self.prefix + item
                    if target not in self.created_cols:
                        self.created_cols.append(target)
                    return self.real_db[target]

            self.mock_db = DbProxy(self.real_db, self._prefix)

        self.service_col = self.mock_db["service"]
        self.ip_col = self.mock_db["ip"]
        self.task_col = self.mock_db["task"]
        self.site_col = self.mock_db["site"]

        # 模拟预置存量数据：端口 8443 原本被 nmap 识别为 unknown
        self.task_id = "task_test_999"
        self.service_col.insert_one({
            "task_id": self.task_id,
            "service_name": "unknown",
            "service_info": [
                {"ip": "192.168.1.1", "port_id": 8443, "product": "", "version": ""}
            ]
        })
        self.ip_col.insert_one({
            "task_id": self.task_id,
            "ip": "192.168.1.1",
            "port_info": [
                {"port_id": 8443, "service_name": "unknown", "product": "", "version": ""}
            ]
        })

        self.patcher1 = patch('app.utils.conn.conn_db', side_effect=lambda col, **kw: self.mock_db[col])
        self.patcher2 = patch('app.utils.conn_db', side_effect=lambda col, **kw: self.mock_db[col])
        self.patcher1.start()
        self.patcher2.start()

    def tearDown(self):
        self.patcher1.stop()
        self.patcher2.stop()
        if not getattr(self, '_is_mongomock', True):
            for col_name in getattr(self.mock_db, 'created_cols', []):
                try:
                    self.real_db[col_name].drop()
                except Exception:
                    pass

    def test_sync_moves_unknown_to_https_and_deletes_empty_unknown_doc(self):
        """验证反哺后将 unknown 移入 https，且物理删除空 unknown 文档"""
        site_info_list = [{
            "task_id": self.task_id,
            "site": "https://192.168.1.1:8443",
            "ip": "192.168.1.1",
            "http_server": "OpenSSL-Gateway",
            "finger": [{"name": "Ruijie Gateway", "version": "v3.2"}]
        }]

        sync_service_from_site(self.task_id, site_info_list)

        # 1. 验证 unknown 分类已被彻底删除 (无残留空行)
        unknown_docs = list(self.service_col.find({"task_id": self.task_id, "service_name": "unknown"}))
        self.assertEqual(len(unknown_docs), 0, "Empty unknown document must be deleted!")

        # 2. 验证已正确归入 https 分类并附带指纹与版本
        https_doc = self.service_col.find_one({"task_id": self.task_id, "service_name": "https"})
        self.assertIsNotNone(https_doc, "https document must be created!")
        self.assertEqual(len(https_doc["service_info"]), 1)
        srv_item = https_doc["service_info"][0]
        self.assertEqual(srv_item["ip"], "192.168.1.1")
        self.assertEqual(srv_item["port_id"], 8443)
        self.assertEqual(srv_item["product"], "Ruijie Gateway")
        self.assertEqual(srv_item["version"], "v3.2")

        # 3. 验证 db.ip.port_info 的 service_name 和 product 同步更新
        ip_doc = self.ip_col.find_one({"task_id": self.task_id, "ip": "192.168.1.1"})
        self.assertIsNotNone(ip_doc)
        port_item = [p for p in ip_doc["port_info"] if p["port_id"] == 8443][0]
        self.assertEqual(port_item["service_name"], "https")
        self.assertEqual(port_item["product"], "Ruijie Gateway")
        self.assertEqual(port_item["version"], "v3.2")

    def test_sync_service_idempotence(self):
        """重复同步相同站点信息不应造成重复记录"""
        site_info_list = [{
            "task_id": self.task_id,
            "site": "https://192.168.1.1:8443",
            "ip": "192.168.1.1",
            "http_server": "OpenSSL-Gateway",
            "finger": [{"name": "Ruijie Gateway", "version": "v3.2"}]
        }]

        sync_service_from_site(self.task_id, site_info_list)
        sync_service_from_site(self.task_id, site_info_list)

        https_doc = self.service_col.find_one({"task_id": self.task_id, "service_name": "https"})
        self.assertEqual(len(https_doc["service_info"]), 1)

    def test_sync_handles_empty_and_none_gracefully(self):
        """空参数或异常数据静默退出，不抛出异常"""
        sync_service_from_site(None, [])
        sync_service_from_site(self.task_id, [])
        sync_service_from_site(self.task_id, [{"site": ""}])

    def test_websitefetch_save_site_info_triggers_sync(self):
        """验证 WebSiteFetch.save_site_info() 会正常拉起 sync_service_from_site"""
        fetcher = WebSiteFetch(task_id=self.task_id, sites=["https://192.168.1.1:8443"], options={})
        fetcher.site_info_list = [{
            "task_id": self.task_id,
            "site": "https://192.168.1.1:8443",
            "ip": "192.168.1.1",
            "finger": []
        }]

        with patch('app.services.commonTask.sync_service_from_site') as mock_sync:
            fetcher.save_site_info()
            mock_sync.assert_called_once()
            args, _ = mock_sync.call_args
            self.assertEqual(args[0], self.task_id)

    def test_sync_resolves_ip_when_ip_is_empty(self):
        """当 site_info 中的 ip 字段为空时，从 hostname 智能解析（支持 IP 与域名），且不抛出 AttributeError"""
        task_id = "task_empty_ip"
        self.service_col.insert_one({
            "task_id": task_id,
            "service_name": "unknown",
            "service_info": [{"ip": "10.10.10.10", "port_id": 8080, "product": "", "version": ""}]
        })
        self.ip_col.insert_one({
            "task_id": task_id,
            "ip": "10.10.10.10",
            "port_info": [{"port_id": 8080, "service_name": "unknown", "product": "", "version": ""}]
        })

        site_info_list = [{
            "task_id": task_id,
            "site": "http://10.10.10.10:8080",
            "ip": "",  # 空 IP
            "http_server": "Embedded-Gateway",
            "finger": [{"name": "Web Admin", "version": "1.0"}]
        }]

        sync_service_from_site(task_id, site_info_list)

        # unknown 文档被删除
        unknown_doc = self.service_col.find_one({"task_id": task_id, "service_name": "unknown"})
        self.assertIsNone(unknown_doc)

        # http 文档被创建
        http_doc = self.service_col.find_one({"task_id": task_id, "service_name": "http"})
        self.assertIsNotNone(http_doc)
        self.assertEqual(http_doc["service_info"][0]["ip"], "10.10.10.10")

    def test_sync_pushes_port_when_port_not_in_port_info(self):
        """当 db.ip 存在但 port_info 尚无此端口时，防御性推入该端口信息"""
        self.ip_col.insert_one({
            "task_id": self.task_id,
            "ip": "192.168.2.1",
            "port_info": [{"port_id": 22, "service_name": "ssh"}]
        })

        site_info_list = [{
            "task_id": self.task_id,
            "site": "https://192.168.2.1:443",
            "ip": "192.168.2.1",
            "http_server": "OpenResty",
            "finger": []
        }]

        sync_service_from_site(self.task_id, site_info_list)

        ip_doc = self.ip_col.find_one({"task_id": self.task_id, "ip": "192.168.2.1"})
        port_ids = [p["port_id"] for p in ip_doc["port_info"]]
        self.assertIn(443, port_ids)

    def test_sync_cleanup_on_item_error(self):
        """当单条数据处理异常时，finally 块仍能清理幽灵空文档"""
        task_id = "task_cleanup_err"
        self.service_col.insert_one({
            "task_id": task_id,
            "service_name": "unknown",
            "service_info": []  # 初始为空
        })

        # 传入一个导致单项解析异常的数据
        site_info_list = [{"site": None}]

        sync_service_from_site(task_id, site_info_list)

        # 空 unknown 必须被清理
        unknown_doc = self.service_col.find_one({"task_id": task_id, "service_name": "unknown"})
        self.assertIsNone(unknown_doc)

    def test_sync_with_objectid_task_id(self):
        """验证当 task_id 为 ObjectId 对象时，sync_service_from_site 正确转为字符串并完成匹配"""
        from bson import ObjectId
        obj_task_id = ObjectId("507f1f77bcf86cd799439011")
        str_task_id = str(obj_task_id)

        self.service_col.insert_one({
            "task_id": str_task_id,
            "service_name": "unknown",
            "service_info": [{"ip": "10.0.0.99", "port_id": 8080, "product": "", "version": ""}]
        })
        self.ip_col.insert_one({
            "task_id": str_task_id,
            "ip": "10.0.0.99",
            "port_info": [{"port_id": 8080, "service_name": "unknown", "product": "", "version": ""}]
        })

        site_info_list = [{
            "task_id": str_task_id,
            "site": "http://10.0.0.99:8080",
            "ip": "10.0.0.99",
            "http_server": "TestServer",
            "finger": []
        }]

        sync_service_from_site(obj_task_id, site_info_list)

        # unknown 文档被删除
        self.assertIsNone(self.service_col.find_one({"task_id": str_task_id, "service_name": "unknown"}))
        # http 文档被创建
        http_doc = self.service_col.find_one({"task_id": str_task_id, "service_name": "http"})
        self.assertIsNotNone(http_doc)
        self.assertEqual(http_doc["service_info"][0]["port_id"], 8080)

    def test_sync_creates_ip_document_when_absent(self):
        """当 db.ip 中完全不存在该 IP 的记录时，sync_service_from_site 自动创建新 IP 记录且 protocol 为 tcp"""
        new_ip = "192.168.100.50"
        site_info_list = [{
            "task_id": self.task_id,
            "site": "https://192.168.100.50:443",
            "ip": new_ip,
            "http_server": "Nginx/1.20",
            "finger": []
        }]

        sync_service_from_site(self.task_id, site_info_list)

        ip_doc = self.ip_col.find_one({"task_id": self.task_id, "ip": new_ip})
        self.assertIsNotNone(ip_doc, "IP document must be created if absent!")
        self.assertEqual(len(ip_doc["port_info"]), 1)
        port_entry = ip_doc["port_info"][0]
        self.assertEqual(port_entry["port_id"], 443)
        self.assertEqual(port_entry["service_name"], "https")
        self.assertEqual(port_entry["protocol"], "tcp")
        self.assertEqual(port_entry["product"], "Nginx/1.20")

    def test_sync_handles_none_http_server(self):
        """当 site_info 中 http_server 为 None 且无指纹时，product 存入空字符串而不是 None"""
        ip = "192.168.100.60"
        site_info_list = [{
            "task_id": self.task_id,
            "site": "https://192.168.100.60:8443",
            "ip": ip,
            "http_server": None,  # None 字段
            "finger": []
        }]

        sync_service_from_site(self.task_id, site_info_list)

        https_doc = self.service_col.find_one({"task_id": self.task_id, "service_name": "https"})
        self.assertIsNotNone(https_doc)
        matching = [s for s in https_doc["service_info"] if s["ip"] == ip]
        self.assertEqual(len(matching), 1)
        self.assertEqual(matching[0]["product"], "")
        self.assertIsNotNone(matching[0]["product"])



class TestFrontendAssetSearchVue(unittest.TestCase):
    """
    验证前端 AssetSearch.vue 中 site.searchFields 已成功注册 IP 检索字段
    """

    def test_ip_field_present_in_site_search_fields(self):
        frontend_file = os.path.abspath(
            os.path.join(backend_dir, '..', 'frontend', 'src', 'views', 'AssetSearch.vue')
        )
        self.assertTrue(os.path.exists(frontend_file))
        with open(frontend_file, 'r', encoding='utf-8') as f:
            content = f.read()

        # 检查 site.searchFields 区域
        site_block_start = content.find("site: {")
        self.assertNotEqual(site_block_start, -1)
        domain_block_start = content.find("domain: {", site_block_start)
        self.assertNotEqual(domain_block_start, -1)

        site_content = content[site_block_start:domain_block_start]
        self.assertIn("{ label: 'IP', key: 'ip', operator: '=' }", site_content)


class TestFetchSiteResilience(unittest.TestCase):
    """
    验证 FetchSite 在遇到 SSL 异常时自动触发弹性重试，
    以及在根路径异常时自动回退网关路径提取真实登录页指纹。
    """

    def test_fetch_site_retries_resilient_ssl_on_ssl_error(self):
        fetcher = FetchSite(["https://192.168.1.1:8443"])
        fetcher.fetch_fingerprint = MagicMock()
        calls = []

        def mock_http_req(url, **kwargs):
            calls.append(kwargs)
            if not kwargs.get("resilient_ssl", False):
                raise requests.exceptions.SSLError("SSL unexpected EOF")
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.content = b"<html><head><title>Secure Gateway</title></head></html>"
            mock_resp.text = "<html><head><title>Secure Gateway</title></head></html>"
            mock_resp.headers = {"Server": "SecureOS/1.0"}
            return mock_resp

        with patch('app.utils.http_req', side_effect=mock_http_req), \
             patch('app.services.fetchSite.fetch_favicon', return_value={}):
            fetcher.work("https://192.168.1.1:8443")

        self.assertEqual(len(fetcher.site_info_list), 1)
        self.assertEqual(fetcher.site_info_list[0]["title"], "Secure Gateway")
        self.assertTrue(any(c.get("resilient_ssl") for c in calls))

    def test_fetch_site_fallback_to_gateway_paths(self):
        """当根路径 404 时，FetchSite 自动探测网关备选路径并捕获真实指纹"""
        fetcher = FetchSite(["https://192.168.1.1:8443"])
        fetcher.fetch_fingerprint = MagicMock()

        def mock_http_req(url, **kwargs):
            mock_resp = MagicMock()
            if url.endswith("/web/frame/login.html"):
                mock_resp.status_code = 200
                mock_resp.content = b"<html><head><title>Router Web Login</title></head></html>"
                mock_resp.text = "<html><head><title>Router Web Login</title></head></html>"
                mock_resp.headers = {"Server": "EmbeddedWeb"}
            else:
                mock_resp.status_code = 404
                mock_resp.content = b"404 Not Found"
                mock_resp.text = "404 Not Found"
                mock_resp.headers = {}
            return mock_resp

        with patch('app.utils.http_req', side_effect=mock_http_req), \
             patch('app.services.fetchSite.fetch_favicon', return_value={}):
            fetcher.work("https://192.168.1.1:8443")

        self.assertEqual(len(fetcher.site_info_list), 1)
        self.assertEqual(fetcher.site_info_list[0]["title"], "Router Web Login")

    def test_fetch_site_fallback_accepts_401_and_403(self):
        """当网关备选路径返回 401 时，FetchSite 依然捕获该站点并提取认证挑战指纹"""
        fetcher = FetchSite(["https://192.168.1.1:8443"])
        fetcher.fetch_fingerprint = MagicMock()

        def mock_http_req(url, **kwargs):
            mock_resp = MagicMock()
            if url.endswith("/admin/"):
                mock_resp.status_code = 401
                mock_resp.content = b"<html><head><title>Admin Auth Required</title></head></html>"
                mock_resp.text = "<html><head><title>Admin Auth Required</title></head></html>"
                mock_resp.headers = {"Server": "Gateway-Security", "WWW-Authenticate": "Basic realm=Admin"}
            else:
                mock_resp.status_code = 404
                mock_resp.content = b"Not Found"
                mock_resp.text = "Not Found"
                mock_resp.headers = {}
            return mock_resp

        with patch('app.utils.http_req', side_effect=mock_http_req), \
             patch('app.services.fetchSite.fetch_favicon', return_value={}):
            fetcher.work("https://192.168.1.1:8443")

        self.assertEqual(len(fetcher.site_info_list), 1)
        self.assertEqual(fetcher.site_info_list[0]["status"], 401)
        self.assertEqual(fetcher.site_info_list[0]["title"], "Admin Auth Required")

    def test_fetch_favicon_with_binascii_encode(self):
        """验证 fetch_favicon 正常调用 binascii.b2a_base64 编码并计算 mmh3 哈希，不抛出 NameError"""
        from app.services.fetchSite import fetch_favicon, FetchFavicon
        favicon_content = b"\x89PNG\r\n\x1a\n" + b"A" * 150  # 超过 80 字节的假图片数据

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.content = favicon_content
        mock_resp.headers = {"Content-Type": "image/png"}

        with patch('app.services.fetchSite.fetch_favicon_response', return_value=mock_resp):
            fav = fetch_favicon("https://example.com/")
            self.assertIn("hash", fav)
            self.assertNotEqual(fav["hash"], 0)
            self.assertIn("data", fav)




class TestUtilsIP(unittest.TestCase):
    """验证 is_v4_ip 与 is_v6_ip 边界与合法性判定"""

    def test_is_v4_ip_and_is_v6_ip(self):
        self.assertTrue(utils.is_v4_ip("192.168.1.1"))
        self.assertTrue(utils.is_v4_ip("127.0.0.1"))
        self.assertFalse(utils.is_v4_ip("2001:db8::1"))
        self.assertFalse(utils.is_v4_ip("example.com"))
        self.assertFalse(utils.is_v4_ip(None))
        self.assertFalse(utils.is_v4_ip(""))

        self.assertTrue(utils.is_v6_ip("2001:db8::1"))
        self.assertTrue(utils.is_v6_ip("[2001:db8::1]"))
        self.assertFalse(utils.is_v6_ip("192.168.1.1"))
        self.assertFalse(utils.is_v6_ip("example.com"))
        self.assertFalse(utils.is_v6_ip(None))


class TestIPTaskFindSite(unittest.TestCase):
    """验证 tasks.ip.IPTask.find_site 对 IPv6 与字符串端口的鲁棒性"""

    def test_ip_task_find_site_ipv6_and_string_ports(self):
        task = IPTask.__new__(IPTask)
        task.ip_info_list = [
            {
                "ip": "2001:db8::1",
                "port_info": [
                    {"port_id": "80"},
                    {"port_id": "443"},
                    {"port_id": "8080"}
                ]
            }
        ]
        task.site_list = []

        mock_check_map = {
            "http://[2001:db8::1]": {"status": 200},
            "https://[2001:db8::1]": {"status": 200},
            "https://[2001:db8::1]:8080": {"status": 200}
        }

        with patch('app.services.check_http', return_value=mock_check_map) as mock_check:
            task.find_site()
            called_urls = mock_check.call_args[0][0]
            self.assertIn("http://[2001:db8::1]", called_urls)
            self.assertIn("https://[2001:db8::1]", called_urls)
            self.assertIn("http://[2001:db8::1]:8080", called_urls)
            self.assertIn("https://[2001:db8::1]:8080", called_urls)
            # 80/443 不应带 :80/:443
            self.assertNotIn("http://[2001:db8::1]:80", called_urls)
            self.assertNotIn("https://[2001:db8::1]:443", called_urls)

    def test_ip_task_find_site_ignores_empty_and_none_ip(self):
        """当 ip 字段为 None 或空字符串时，IPTask.find_site 安全跳过，不抛出异常也不生成畸形 URL"""
        task = IPTask.__new__(IPTask)
        task.ip_info_list = [
            {"ip": None, "port_info": [{"port_id": 80}]},
            {"ip": "   ", "port_info": [{"port_id": 443}]}
        ]
        task.site_list = []
        with patch('app.services.check_http', return_value={}) as mock_check:
            task.find_site()
            called_urls = mock_check.call_args[0][0]
            self.assertEqual(called_urls, [])



class TestDomainSiteUpdateSync(unittest.TestCase):
    """验证 DomainSiteUpdate.save_site_info 会拉起 sync_service_from_site"""

    def test_domain_site_update_save_site_info_triggers_sync(self):
        updater = DomainSiteUpdate.__new__(DomainSiteUpdate)
        updater.task_id = "test_task_update"
        updater.available_sites = ["https://10.0.0.1:8443"]

        mock_site_info = [{
            "task_id": "test_task_update",
            "site": "https://10.0.0.1:8443",
            "ip": "10.0.0.1",
            "finger": []
        }]

        with patch('app.services.domainSiteUpdate.fetch_site', return_value=mock_site_info), \
             patch('app.services.commonTask.sync_service_from_site') as mock_sync, \
             patch('app.utils.conn_db') as mock_conn:
            mock_col = MagicMock()
            mock_col.find.return_value = []
            mock_conn.return_value = mock_col
            updater.save_site_info()
            mock_sync.assert_called_once()


if __name__ == '__main__':
    unittest.main()
