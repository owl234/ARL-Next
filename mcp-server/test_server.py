"""python3 -m unittest discover -s mcp-server -p 'test_*.py' -v"""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import ssl
import subprocess
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('arl_mcp_server', Path(__file__).with_name('server.py'))
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class MCPTests(unittest.TestCase):
    def setUp(self):
        self.auth = patch.object(server, '_get_auth', return_value=('https://arl.example', 'fixture-token'))
        self.auth.start()
        self.addCleanup(self.auth.stop)

    @classmethod
    def setUpClass(cls):
        """回环 HTTPS 服务 + 自签证书（CN=localhost，不带 SAN，复刻真实部署证书）。"""
        if not shutil.which('openssl'):
            raise unittest.SkipTest('openssl is required for the loopback TLS fixture')

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b'{"code":200,"items":[]}')

            def log_message(self, *args):
                pass

        cls._directory = tempfile.TemporaryDirectory()
        cls.directory = cls._directory.name
        cls.cert = str(Path(cls.directory) / 'cert.pem')
        key = str(Path(cls.directory) / 'key.pem')
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-subj', '/CN=localhost',
                        '-keyout', key, '-out', cls.cert],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        cls.httpd = HTTPServer(('127.0.0.1', 0), Handler)
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(cls.cert, key)
        cls.httpd.socket = context.wrap_socket(cls.httpd.socket, server_side=True)
        cls._thread = threading.Thread(target=cls.httpd.serve_forever, daemon=True)
        cls._thread.start()
        cls.loopback_host = 'https://127.0.0.1:{}'.format(cls.httpd.server_port)
        cls.loopback_alias = 'https://localhost:{}'.format(cls.httpd.server_port)

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls._thread.join(timeout=2)
        cls._directory.cleanup()

    def clean_tls_env(self, **overrides):
        """屏蔽外部环境残留的 TLS 变量，逐用例显式声明生效配置。"""
        env = {'ARL_CA_BUNDLE': '', 'ARL_TLS_VERIFY': '', 'ARL_STRICT_HOSTNAME': ''}
        env.update(overrides)
        return env

    def call_tool(self):
        return server.handle_request({'id': 1, 'method': 'tools/call', 'params': {
            'name': 'get_asset_profile', 'arguments': {'target': 'alpha.example'}}})['result']

    def fallback_api(self, status, data, failing_endpoint=None):
        def api(endpoint, params=None):
            if endpoint == '/mcp/asset_profile':
                return 404, {}
            if failing_endpoint is None or endpoint == failing_endpoint:
                return status, data
            return 200, {'code': 200, 'items': []}
        return api

    def test_body_auth_error_is_tool_error(self):
        for code in (401, 403, '401'):
            with self.subTest(code=code), patch.object(server, '_request_api', self.fallback_api(200, {'code': code})):
                result = self.call_tool()
                self.assertTrue(result['isError'])
                self.assertEqual(json.loads(result['content'][0]['text'])['status'], 'auth_error')

    def test_one_failed_dimension_does_not_look_empty(self):
        with patch.object(server, '_request_api', self.fallback_api(503, {}, '/vuln/')):
            result = self.call_tool()
        self.assertTrue(result['isError'])
        self.assertEqual(json.loads(result['content'][0]['text'])['status'], 'error')

    def test_successful_empty_queries_still_return_not_found(self):
        with patch.object(server, '_request_api', self.fallback_api(200, {'code': 200, 'items': []})):
            result = self.call_tool()
        self.assertFalse(result['isError'])
        self.assertEqual(json.loads(result['content'][0]['text'])['status'], 'not_found')

    def test_ip_detail_errors_are_checked(self):
        def api(endpoint, params=None):
            if endpoint == '/ip/':
                return 200, {'code': 401}
            return 200, {'items': []}
        with patch.object(server, '_request_api', api):
            self.assertEqual(server._fallback_aggregate_profile('192.0.2.1')['status'], 'auth_error')

    def test_malformed_success_response_is_error(self):
        for data in ({'code': 200}, {'items': None}, ['unexpected']):
            with self.subTest(data=data), patch.object(server, '_request_api', return_value=(200, data)):
                self.assertEqual(server._request_items('/site/', {})[0], 502)

    def test_invalid_ca_path_returns_error_without_request(self):
        with patch.dict(os.environ, {'ARL_CA_BUNDLE': '/nonexistent/fixture-ca.pem', 'ARL_TLS_VERIFY': 'true'}), \
                patch.object(server.urllib.request, 'urlopen') as request:
            self.assertEqual(server._request_api('/site/')[0], 500)
            request.assert_not_called()

    def test_tls_context_matrix(self):
        """链校验/主机名校验/显式关闭三档组合，逐项锁定预期上下文特征。"""
        cases = [
            ('default', {}, False, True, ssl.CERT_REQUIRED),
            ('explicit off', {'ARL_TLS_VERIFY': 'false'}, False, False, ssl.CERT_NONE),
            ('trusted ca (dns)', {'ARL_CA_BUNDLE': self.cert}, False, True, ssl.CERT_REQUIRED),
        ]
        for label, env, expect_pinned, expect_hostname_check, expect_verify in cases:
            with self.subTest(label=label), patch.dict(os.environ, self.clean_tls_env(**env)):
                context, peer_check, insecure = server._build_ssl_context('https://arl.example/api/site/')
                self.assertEqual(isinstance(context, server._PinnedCAContext), expect_pinned)
                self.assertEqual(context.check_hostname, expect_hostname_check)
                self.assertEqual(context.verify_mode, expect_verify)
                self.assertEqual(bool(peer_check), expect_pinned)
                self.assertEqual(insecure, expect_verify == ssl.CERT_NONE)

    def test_ip_literal_accepts_ca_verified_certificate_without_san(self):
        """证书无 SAN（CN=localhost）时，IP 字面量访问放行而非整链失败。"""
        with patch.object(server, '_get_auth', return_value=(self.loopback_host, 'fixture-token')), \
                patch.dict(os.environ, self.clean_tls_env(ARL_CA_BUNDLE=self.cert,
                                                          NO_PROXY='127.0.0.1', no_proxy='127.0.0.1')):
            self.assertEqual(server._request_api('/site/')[0], 200)

    def test_ip_literal_trusting_another_certificate_is_still_rejected(self):
        """可信 CA 与实际服务端证书不符时仍须拒绝——链校验不可被绕过。"""
        other = str(Path(self.directory) / 'other.pem')
        subprocess.run(['openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes', '-days', '1',
                        '-subj', '/CN=localhost', '-keyout', str(Path(self.directory) / 'other.key'),
                        '-out', other], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        with patch.object(server, '_get_auth', return_value=(self.loopback_host, 'fixture-token')), \
                patch.dict(os.environ, self.clean_tls_env(ARL_CA_BUNDLE=other,
                                                          NO_PROXY='127.0.0.1', no_proxy='127.0.0.1')):
            code, error = server._request_api('/site/')
            self.assertEqual(code, 500)
            self.assertIn('CERTIFICATE_VERIFY_FAILED', error['message'])

    def test_strict_hostname_env_keeps_hostname_check(self):
        with patch.dict(os.environ, self.clean_tls_env(ARL_CA_BUNDLE=self.cert, ARL_STRICT_HOSTNAME='true')):
            context, peer_check, insecure = server._build_ssl_context('https://192.0.2.10/api/site/')
        self.assertFalse(isinstance(context, server._PinnedCAContext))
        self.assertTrue(context.check_hostname)
        self.assertIsNone(peer_check)
        self.assertFalse(insecure)

    def test_dns_host_keeps_hostname_check_with_ca_bundle(self):
        with patch.dict(os.environ, self.clean_tls_env(ARL_CA_BUNDLE=self.cert)):
            context, peer_check, insecure = server._build_ssl_context('https://arl.example/api/site/')
        self.assertFalse(isinstance(context, server._PinnedCAContext))
        self.assertTrue(context.check_hostname)
        self.assertIsNone(peer_check)
        self.assertFalse(insecure)

    def test_local_self_signed_cert_is_not_trusted_for_remote_host(self):
        """本地自签证书只对本机回环地址自动生效，远程目标不得被本地文件静默放行。"""
        with patch.dict(os.environ, self.clean_tls_env()):
            self.assertEqual(server._resolve_ca_bundle('https://192.0.2.10:5173'), ('', False))
            self.assertEqual(server._resolve_ca_bundle('https://localhost:5173'), ('', False))
            self.assertEqual(server._resolve_ca_bundle('https://127.0.0.1:5173'), ('', False))

        # 无自动发现时，远程 IP 回到系统默认：严格校验且不使用任何本地 CA
        with patch.dict(os.environ, self.clean_tls_env()), \
                patch.object(server, '_resolve_ca_bundle', return_value=('', False)):
            remote, peer_check, insecure = server._build_ssl_context('https://192.0.2.10/api/site/')
        self.assertTrue(remote.check_hostname)
        self.assertEqual(remote.verify_mode, ssl.CERT_REQUIRED)
        self.assertIsNone(peer_check)
        self.assertFalse(insecure)

    def test_auto_discovery_reads_cert_path_from_auth_doc(self):
        """ARL_auth.md 中登记的 ARL_LOCAL_CERT 路径被自动识别为本地自签证书。"""
        doc = Path(self.directory) / 'ARL_doc' / 'ARL_auth.md'
        doc.parent.mkdir(parents=True, exist_ok=True)
        doc.write_text(f'ARL_LOCAL_CERT: {self.cert}\n', encoding='utf-8')
        with patch.object(server, '__file__', str(doc.parent / 'server.py')), \
                patch.dict(os.environ, self.clean_tls_env()):
            self.assertEqual(server._resolve_ca_bundle('https://127.0.0.1:5173'), (self.cert, True))
            # 非回环目标不得被本地文件自动放行
            self.assertEqual(server._resolve_ca_bundle('https://192.0.2.10:5173'), ('', False))

    def test_ca_bundle_auto_discovery_prefers_explicit_env(self):
        with patch.dict(os.environ, self.clean_tls_env(ARL_CA_BUNDLE='/tmp/explicit.pem')):
            path, is_local = server._resolve_ca_bundle('https://127.0.0.1:5173')
        self.assertEqual(path, '/tmp/explicit.pem')
        self.assertFalse(is_local)

    def test_ca_bundle_auto_discovery_skips_non_loopback(self):
        with patch.dict(os.environ, self.clean_tls_env()):
            self.assertEqual(server._resolve_ca_bundle('https://192.0.2.10:5173'), ('', False))

    def test_downloadable_client_matches_server(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual((root / 'mcp-server/server.py').read_bytes(),
                         (root / 'frontend/public/mcp/server.py').read_bytes())

    def test_tools_list_contains_both_tools(self):
        """tools/list 声明包含 get_asset_profile 与 get_enterprise_profile 工具"""
        resp = server.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        tools = resp.get("result", {}).get("tools", [])
        tool_names = [t["name"] for t in tools]
        self.assertIn("get_asset_profile", tool_names)
        self.assertIn("get_enterprise_profile", tool_names)

    def test_call_enterprise_profile_missing_target(self):
        """缺少必填 target 参数时返回工具调用错误"""
        resp = server.handle_request({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": "get_enterprise_profile", "arguments": {}}
        })
        self.assertTrue(resp.get("result", {}).get("isError"))
        content_text = resp["result"]["content"][0]["text"]
        self.assertIn("Missing required parameter: target", content_text)

    def test_call_enterprise_profile_primary_endpoint(self):
        """优先直接调用原生 /mcp/enterprise_profile 接口"""
        mock_profile = {
            "status": "success",
            "enterprise_info": {"name": "测试科技有限公司", "task_id": "670000000000000000000001"},
            "asset_counts": {"web": 10, "app": 2, "total": 12}
        }
        with patch.object(server, '_request_api', return_value=(200, mock_profile)) as mock_req:
            resp = server.handle_request({
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "get_enterprise_profile", "arguments": {"target": "测试科技", "category": "all"}}
            })
            self.assertFalse(resp.get("result", {}).get("isError"))
            self.assertIn("测试科技有限公司", resp["result"]["content"][0]["text"])
            mock_req.assert_called_with("/mcp/enterprise_profile", {"target": "测试科技", "category": "all", "page": 1, "size": 20})

    def test_call_enterprise_profile_fallback_when_404(self):
        """当原生 /mcp/enterprise_profile 返回 404 时，自动降级至标准 /icp/task 聚合"""
        def fake_request_api(endpoint, params):
            if endpoint == "/mcp/enterprise_profile":
                return 404, {"code": 404, "message": "Not Found"}
            elif endpoint == "/icp/task":
                return 200, {"code": 200, "items": [{"_id": "670000000000000000000001", "name": "测试企业全景测绘", "company_name": "测试企业", "status": "done"}]}
            elif endpoint == "/icp/asset":
                return 200, {"code": 200, "total": 5, "items": [{"domain": "test.com", "serviceName": "测试网站"}]}
            return 404, {}

        with patch.object(server, '_request_api', side_effect=fake_request_api):
            resp = server.handle_request({
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "get_enterprise_profile", "arguments": {"target": "测试企业", "category": "all"}}
            })
            self.assertFalse(resp.get("result", {}).get("isError"))
            content = json.loads(resp["result"]["content"][0]["text"])
            self.assertEqual(content.get("status"), "success")
            self.assertEqual(content["enterprise_info"]["name"], "测试企业")

    def test_loopback_tls_default_rejects_self_signed_and_explicit_ca_works(self):
        """默认拒绝自签；指定 CA 后按主机名口径放行 localhost、拒绝 IP 字面量。"""
        with patch.object(server, '_get_auth', return_value=(self.loopback_alias, 'fixture-token')), \
                patch.dict(os.environ, self.clean_tls_env(ARL_TLS_VERIFY='true',
                                                          NO_PROXY='localhost', no_proxy='localhost')):
            code, error = server._request_api('/site/')
            self.assertEqual(code, 500)
            self.assertIn('CERTIFICATE_VERIFY_FAILED', error['message'])
            with patch.dict(os.environ, {'ARL_CA_BUNDLE': self.cert}):
                self.assertEqual(server._request_api('/site/')[0], 200)
            # A trusted certificate must still match the requested hostname.
            with patch.object(server, '_get_auth', return_value=(self.loopback_host, 'fixture-token')), \
                    patch.dict(os.environ, {'ARL_CA_BUNDLE': self.cert, 'ARL_STRICT_HOSTNAME': 'true',
                                           'NO_PROXY': '127.0.0.1', 'no_proxy': '127.0.0.1'}):
                self.assertEqual(server._request_api('/site/')[0], 500)
            with patch.dict(os.environ, {'ARL_TLS_VERIFY': 'false'}):
                self.assertEqual(server._request_api('/site/')[0], 200)

    def test_tools_list_syncs_from_remote_and_falls_back_on_404(self):
        remote_tools = [server.TOOL_GET_ASSET_PROFILE, server.TOOL_SEARCH_ASSETS]
        with patch.object(server, '_request_api', return_value=(200, {'code': 200, 'tools': remote_tools})):
            resp = server.handle_request({'jsonrpc': '2.0', 'id': 11, 'method': 'tools/list'})
            self.assertEqual([t['name'] for t in resp['result']['tools']], ['get_asset_profile', 'search_assets'])

        with patch.object(server, '_request_api', return_value=(404, {})):
            resp = server.handle_request({'jsonrpc': '2.0', 'id': 12, 'method': 'tools/list'})
            self.assertEqual([t['name'] for t in resp['result']['tools']], ['get_asset_profile', 'get_enterprise_profile'])

    def test_stdio_supports_search_task_status_and_dispatch_tools(self):
        with patch.object(server, '_request_api', return_value=(200, {'items': [{'site': 'https://a.test'}], 'total': 1, 'type': 'site'})) as mock_get:
            res = server.handle_request({
                'jsonrpc': '2.0', 'id': 21, 'method': 'tools/call',
                'params': {'name': 'search_assets', 'arguments': {'query': 'a.test', 'asset_type': 'site', 'limit': 5}}
            })['result']
            self.assertFalse(res['isError'])
            mock_get.assert_called_with('/mcp/search_assets', {'query': 'a.test', 'asset_type': 'site', 'limit': 5})

        tid = '670000000000000000000001'
        with patch.object(server, '_request_api', return_value=(200, {'task_id': tid, 'status': 'done'})) as mock_get:
            res = server.handle_request({
                'jsonrpc': '2.0', 'id': 22, 'method': 'tools/call',
                'params': {'name': 'get_task_status', 'arguments': {'task_id': tid}}
            })['result']
            self.assertFalse(res['isError'])
            mock_get.assert_called_with('/mcp/task_status', {'task_id': tid})

        with patch.object(server, '_post_api', return_value=(200, {'status': 'success', 'task_id': tid})) as mock_post:
            res = server.handle_request({
                'jsonrpc': '2.0', 'id': 23, 'method': 'tools/call',
                'params': {'name': 'create_scan_task', 'arguments': {'name': 'recon', 'target': 'example.com'}}
            })['result']
            self.assertFalse(res['isError'])
            mock_post.assert_called_with('/mcp/create_scan_task', {'name': 'recon', 'target': 'example.com'})

        with patch.object(server, '_post_api', return_value=(403, {'code': 403, 'status': 'denied', 'message': 'Permission denied'})):
            res = server.handle_request({
                'jsonrpc': '2.0', 'id': 24, 'method': 'tools/call',
                'params': {'name': 'stop_scan_task', 'arguments': {'task_id': tid}}
            })['result']
            self.assertTrue(res['isError'])
            self.assertEqual(json.loads(res['content'][0]['text'])['status'], 'denied')


if __name__ == '__main__':
    unittest.main()
