#coding: utf-8
"""
单元测试：ARL-Next 原生异步 MCP SSE 服务 (app/mcp_server.py)
验证 SSE 长连接、双通道鉴权、JSON-RPC 2.0 报文分发与渐进式工具集控制。
"""

import asyncio
import json
import os
import sys
import unittest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch

# 注入 backend 路径
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
BACKEND_DIR = os.path.dirname(TEST_DIR)
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from app.mcp_server import MCPServer, MCPSession, PROTOCOL_VERSION


class TestMCPServerSSE(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.server = MCPServer(host="127.0.0.1", port=0)
        self.mock_user = {"username": "admin", "token": "test-token-123"}
        self.patcher_conn = patch("app.mcp_server.utils.conn_db")
        self.mock_conn = self.patcher_conn.start()
        self.mock_conn.return_value = Mock()
        self.mock_conn.return_value.find_one.return_value = {}
        self.mock_conn.return_value.find_one_and_update.return_value = {'count': 1}
        self.addCleanup(self.patcher_conn.stop)

    def test_supported_tools_default_readonly(self):
        """测试默认只读模式下的工具列表"""
        with patch.dict(os.environ, {"ARL_MCP_ENABLE_DISPATCH": "false"}):
            srv = MCPServer()
            tools = srv.get_supported_tools()
            tool_names = [t["name"] for t in tools]
            self.assertIn("get_asset_profile", tool_names)
            self.assertIn("get_enterprise_profile", tool_names)
            self.assertIn("search_assets", tool_names)
            self.assertIn("get_task_status", tool_names)
            self.assertNotIn("create_scan_task", tool_names)
            self.assertNotIn("stop_scan_task", tool_names)

    def test_supported_tools_with_dispatch_enabled(self):
        """测试开启调度时的工具列表"""
        with patch.dict(os.environ, {"ARL_MCP_ENABLE_DISPATCH": "true"}):
            srv = MCPServer()
            tools = srv.get_supported_tools()
            tool_names = [t["name"] for t in tools]
            self.assertIn("get_asset_profile", tool_names)
            self.assertIn("get_enterprise_profile", tool_names)
            self.assertIn("create_scan_task", tool_names)
            self.assertIn("stop_scan_task", tool_names)

    def test_authenticate_token_api_key(self):
        """测试通过系统 API_KEY 鉴权"""
        with patch("app.mcp_server.Config") as mock_cfg:
            mock_cfg.AUTH = True
            mock_cfg.API_KEY = "global-secret-api-key"
            res = self.server.authenticate_token("global-secret-api-key")
            self.assertIsNotNone(res)
            self.assertEqual(res["type"], "api")
            self.assertEqual(res["username"], "ARL-API")

            # 带 Bearer 前缀鉴权
            res_bearer = self.server.authenticate_token("Bearer global-secret-api-key")
            self.assertIsNotNone(res_bearer)
            self.assertEqual(res_bearer["type"], "api")

    def test_authenticate_token_db_user(self):
        """测试通过 MongoDB user 表活跃 Token 鉴权"""
        with patch("app.mcp_server.Config") as mock_cfg, patch("app.mcp_server.utils.conn_db") as mock_conn:
            mock_cfg.AUTH = True
            mock_cfg.API_KEY = ""
            mock_coll = Mock()
            mock_coll.find_one.return_value = {
                "username": "sec_auditor",
                "token": "valid-session-token",
                "token_expire_at": datetime.now(timezone.utc) + timedelta(hours=2)
            }
            mock_conn.return_value = mock_coll

            res = self.server.authenticate_token("valid-session-token")
            self.assertIsNotNone(res)
            self.assertEqual(res["username"], "sec_auditor")
            self.assertEqual(res["type"], "user")

    def test_authenticate_token_invalid(self):
        """测试无效 Token 鉴权失败"""
        with patch("app.mcp_server.Config") as mock_cfg, patch("app.mcp_server.utils.conn_db") as mock_conn:
            mock_cfg.AUTH = True
            mock_cfg.API_KEY = "correct-key"
            mock_coll = Mock()
            mock_coll.find_one.return_value = None
            mock_conn.return_value = mock_coll

            res = self.server.authenticate_token("wrong-token")
            self.assertIsNone(res)

    def test_extract_token_dual_channel(self):
        """测试双通道提取 Token (Header 优先，Query 兜底)"""
        # 1. 只有 Header
        t1 = self.server._extract_token_from_request({"authorization": "Bearer header-token"}, {})
        self.assertEqual(t1, "header-token")

        # 2. 只有 Query
        t2 = self.server._extract_token_from_request({}, {"token": ["query-token"]})
        self.assertEqual(t2, "query-token")

        # 3. Header 优先于 Query
        t3 = self.server._extract_token_from_request({"token": "prioritized-header"}, {"token": ["fallback-query"]})
        self.assertEqual(t3, "prioritized-header")

    async def test_jsonrpc_initialize(self):
        """测试 JSON-RPC initialize 握手报文"""
        session = MCPSession("sess-001", self.mock_user)
        req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": PROTOCOL_VERSION}
        }
        res = await self.server.handle_jsonrpc(req, session)
        self.assertIsNotNone(res)
        self.assertEqual(res["id"], 1)
        self.assertEqual(res["result"]["protocolVersion"], PROTOCOL_VERSION)
        self.assertEqual(res["result"]["serverInfo"]["name"], "arl-next-remote")

    async def test_jsonrpc_tools_list(self):
        """测试 JSON-RPC tools/list 工具清单返回"""
        session = MCPSession("sess-002", self.mock_user)
        req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list",
            "params": {}
        }
        res = await self.server.handle_jsonrpc(req, session)
        self.assertEqual(res["id"], 2)
        tools = res["result"]["tools"]
        self.assertTrue(any(t["name"] == "get_asset_profile" for t in tools))

    async def test_jsonrpc_tool_call_get_asset_profile(self):
        """测试 JSON-RPC tools/call 调用资产画像"""
        session = MCPSession("sess-003", self.mock_user)
        mock_profile = {
            "target": "demo.example.com",
            "resolved_ips": ["1.1.1.1"],
            "web": {"url": "https://demo.example.com", "title": "Test Title"}
        }
        with patch("app.mcp_server.build_asset_profile", return_value=mock_profile):
            req = {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_asset_profile",
                    "arguments": {"target": "demo.example.com"}
                }
            }
            res = await self.server.handle_jsonrpc(req, session)
            self.assertEqual(res["id"], 3)
            self.assertFalse(res["result"]["isError"])
            content = json.loads(res["result"]["content"][0]["text"])
            self.assertEqual(content["target"], "demo.example.com")
            self.assertEqual(content["resolved_ips"], ["1.1.1.1"])

    async def test_full_sse_handshake_and_message_delivery(self):
        """端到端集成模拟：启动服务监听，测试 HTTP GET /sse 建立长连接 + POST /message 消息下行"""
        with patch.object(self.server, "authenticate_token", return_value=self.mock_user), \
             patch("app.mcp_server.build_asset_profile", return_value={"target": "baidu.com", "resolved_ips": ["180.101.50.242"]}):

            # 启动实际的 TCP Server
            tcp_server = await asyncio.start_server(self.server.handle_client, "127.0.0.1", 0)
            host, port = tcp_server.sockets[0].getsockname()

            # 客户端 1：发起 GET /sse 握手
            r_sse, w_sse = await asyncio.open_connection(host, port)
            w_sse.write(f"GET /mcp/sse HTTP/1.1\r\nHost: {host}:{port}\r\nAuthorization: Bearer valid-token\r\n\r\n".encode("utf-8"))
            await w_sse.drain()

            # 读取 HTTP 响应头
            status_line = await r_sse.readline()
            self.assertIn(b"200 OK", status_line)

            # 跳过响应 Headers
            headers_done = False
            while not headers_done:
                line = await r_sse.readline()
                if line in (b"\r\n", b"\n", b""):
                    headers_done = True

            # 读取 endpoint event
            event_line = await r_sse.readline()
            self.assertEqual(event_line.strip(), b"event: endpoint")
            data_line = await r_sse.readline()
            self.assertTrue(data_line.startswith(b"data: /mcp/message?sessionId="))
            endpoint_url = data_line.decode().split("data: ")[1].strip()
            session_id = endpoint_url.split("sessionId=")[1]
            await r_sse.readline() # 空行

            self.assertIn(session_id, self.server.sessions)

            # 客户端 2：发起 POST /mcp/message 上行请求
            r_post, w_post = await asyncio.open_connection(host, port)
            req_body = json.dumps({
                "jsonrpc": "2.0",
                "id": 101,
                "method": "initialize",
                "params": {"protocolVersion": PROTOCOL_VERSION}
            })
            post_req = (
                f"POST /mcp/message?sessionId={session_id} HTTP/1.1\r\n"
                f"Host: {host}:{port}\r\n"
                f"Authorization: Bearer valid-token\r\n"
                f"Content-Type: application/json\r\n"
                f"Content-Length: {len(req_body)}\r\n\r\n"
                f"{req_body}"
            )
            w_post.write(post_req.encode("utf-8"))
            await w_post.drain()

            post_status = await r_post.readline()
            self.assertIn(b"202 Accepted", post_status)
            w_post.close()
            await w_post.wait_closed()

            # 在 SSE 客户端中读取返回的 JSON-RPC 消息
            sse_ev = await r_sse.readline()
            self.assertEqual(sse_ev.strip(), b"event: message")
            sse_data = await r_sse.readline()
            msg = json.loads(sse_data.decode().split("data: ")[1].strip())
            self.assertEqual(msg["id"], 101)
            self.assertEqual(msg["result"]["protocolVersion"], PROTOCOL_VERSION)

            # 清理长连接
            w_sse.close()
            await w_sse.wait_closed()
            tcp_server.close()
            await tcp_server.wait_closed()


    def test_authenticate_token_mcp_key_active(self):
        """测试通过独立 MCP API Key 鉴权成功"""
        import hashlib
        raw_key = "arl_mcp_test_token_1234567890"
        key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

        mock_key_doc = {
            "_id": "507f1f77bcf86cd799439011",
            "name": "Cursor Agent",
            "key_hash": key_hash,
            "status": "active",
            "scopes": ["asset:read"],
            "created_by": "sec_user",
            "expire_at": datetime.now(timezone.utc) + timedelta(days=30)
        }
        with patch("app.mcp_server.Config") as mock_cfg:
            mock_cfg.AUTH = True
            mock_cfg.API_KEY = ""
            self.mock_conn.return_value.find_one.return_value = mock_key_doc

            res = self.server.authenticate_token(raw_key)
            self.assertIsNotNone(res)
            self.assertEqual(res["type"], "mcp_key")
            self.assertEqual(res["key_name"], "Cursor Agent")
            self.assertEqual(res["scopes"], ["asset:read"])

    def test_authenticate_token_mcp_key_revoked(self):
        """测试已吊销的 MCP API Key 鉴权失败"""
        import hashlib
        raw_key = "arl_mcp_revoked_key_123"
        key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

        mock_key_doc = {
            "_id": "507f1f77bcf86cd799439012",
            "name": "Old Key",
            "key_hash": key_hash,
            "status": "revoked",
            "scopes": ["asset:read"]
        }
        with patch("app.mcp_server.Config") as mock_cfg:
            mock_cfg.AUTH = True
            mock_cfg.API_KEY = ""
            self.mock_conn.return_value.find_one.return_value = mock_key_doc

            res = self.server.authenticate_token(raw_key)
            self.assertIsNone(res)

    def test_authenticate_token_mcp_key_expired(self):
        """测试已过期的 MCP API Key 鉴权失败"""
        import hashlib
        raw_key = "arl_mcp_expired_key_123"
        key_hash = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

        mock_key_doc = {
            "_id": "507f1f77bcf86cd799439013",
            "name": "Expired Key",
            "key_hash": key_hash,
            "status": "active",
            "expire_at": datetime.now(timezone.utc) - timedelta(days=1)
        }
        with patch("app.mcp_server.Config") as mock_cfg:
            mock_cfg.AUTH = True
            mock_cfg.API_KEY = ""
            self.mock_conn.return_value.find_one.return_value = mock_key_doc

            res = self.server.authenticate_token(raw_key)
            self.assertIsNone(res)

    async def test_tool_call_permission_denied_for_readonly_scope(self):
        """测试只读权限 Key 尝试调用调度任务被拦截"""
        readonly_user = {
            "username": "auditor",
            "type": "mcp_key",
            "scopes": ["asset:read"],
            "key_id": "507f1f77bcf86cd799439011",
            "key_name": "Readonly Key"
        }
        res, is_err = await self.server.handle_tool_call("create_scan_task", {"name": "test", "target": "example.com"}, readonly_user)
        self.assertTrue(is_err)
        self.assertEqual(res.get("status"), "denied")
        self.assertIn("Permission denied", res.get("message", ""))

    async def test_tool_call_get_enterprise_profile(self):
        """测试通过 SSE MCP 服务分流调用 get_enterprise_profile 工具"""
        readonly_user = {
            "username": "auditor",
            "type": "mcp_key",
            "scopes": ["asset:read"],
            "key_id": "507f1f77bcf86cd799439011",
            "key_name": "Readonly Key"
        }
        with patch("app.mcp_server.build_enterprise_profile") as mock_build:
            mock_build.return_value = {
                "status": "success",
                "enterprise_info": {"name": "腾讯计算机", "task_id": "670000000000000000000001"},
                "asset_counts": {"web": 100, "total": 100}
            }
            res, is_err = await self.server.handle_tool_call("get_enterprise_profile", {"target": "腾讯"}, readonly_user)
            self.assertFalse(is_err)
            self.assertEqual(res.get("status"), "success")
            self.assertEqual(res["enterprise_info"]["name"], "腾讯计算机")
            mock_build.assert_called_with("腾讯", "all", 1, 20, "")


if __name__ == "__main__":
    unittest.main()
