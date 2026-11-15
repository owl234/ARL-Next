# -*- coding: utf-8 -*-
"""
工信部 ICP 限流熔断与规避体系单元测试集
验证：
1. 创宇盾 WAF HTML 真实报文 client_ip 正则提取
2. 出口代理自动解析、优先级继承与封禁 IP 自动剔除
3. 自适应物理流控消峰 (Rate Slot) 间隔保证
4. 详情级专属熔断与列表级熔断的分级隔离 (Detail WAF Isolation)
5. 全局熔断判定与健康代理自愈感知
"""
import time
import unittest
from unittest.mock import patch

import sys
import os
sys.path.append(os.path.abspath("backend/osint_service"))
from ymicp import beian


class TestIcpRateLimitMitigation(unittest.IsolatedAsyncioTestCase):

    def setUp(self):
        self.icp = beian()

    def test_extract_waf_blocked_ip_from_html(self):
        """测试从创宇盾真实拦截 HTML 报文中精确提取 client_ip"""
        sample_waf_html = """
        <!DOCTYPE html><html><body>
        <script>
        var data = {"client_ip":"198.51.100.158","time_error":"20/Oct/2026:21:42:28 +0800","error_403_type":"cli_ip","error_403":"您的IP最近有可疑的攻击行为，请稍后重试."};
        document.getElementById('error_403').innerText = data['error_403'];
        </script>
        </body></html>
        """
        ip = self.icp._extract_waf_blocked_ip(sample_waf_html)
        self.assertEqual(ip, "198.51.100.158")

        # 容错：空报文或非HTML
        self.assertIsNone(self.icp._extract_waf_blocked_ip(""))
        self.assertIsNone(self.icp._extract_waf_blocked_ip(None))
        self.assertIsNone(self.icp._extract_waf_blocked_ip("<html>normal content</html>"))

    def test_extract_proxy_ip(self):
        """测试从各种代理 URL 中提取 IP/主机名"""
        self.assertEqual(self.icp._extract_proxy_ip("http://192.168.1.100:8080"), "192.168.1.100")
        self.assertEqual(self.icp._extract_proxy_ip("http://user:pass@10.0.0.5:9999"), "10.0.0.5")
        self.assertEqual(self.icp._extract_proxy_ip("http://proxy.example.com:8080"), "proxy.example.com")
        self.assertIsNone(self.icp._extract_proxy_ip(None))

    def test_resolve_proxy_precedence(self):
        """测试出口代理的优先级解析链与黑名单剔除"""
        # 1. 显式代理优先
        explicit = "http://1.1.1.1:8080"
        self.assertEqual(self.icp._resolve_proxy(explicit), explicit)

        # 2. 显式代理若被拉黑，回退到下一个层级
        self.icp._add_blocked_ip("1.1.1.1")
        # 此时 tunnel 为空，代理池为空，回退到 None
        self.assertIsNone(self.icp._resolve_proxy(explicit))

        # 3. 隧道代理继承
        with patch("ymicp.config") as mock_cfg:
            mock_cfg.proxy.tunnel.url = "http://tunnel.example.com:8888"
            self.assertEqual(self.icp._resolve_proxy(None), "http://tunnel.example.com:8888")

            # 若隧道被拉黑，回退到代理池或 None
            self.icp._add_blocked_ip("tunnel.example.com")
            self.assertIsNone(self.icp._resolve_proxy(None))

    async def test_acquire_rate_slot_spacing(self):
        """测试物理流控消峰锁强制施加安全间隔"""
        # 模拟单 IP 模式，设定短安全间隔测试时间差
        with patch("random.uniform", return_value=0.15):
            t0 = time.time()
            await self.icp._acquire_rate_slot(is_proxied=False)
            t1 = time.time()
            await self.icp._acquire_rate_slot(is_proxied=False)
            t2 = time.time()

            # 第二次调用必须等待至少 0.15s
            self.assertGreaterEqual(t2 - t1, 0.14)

    def test_detail_waf_isolation(self):
        """测试详情级熔断与列表级熔断的严格分级隔离"""
        self.assertFalse(self.icp._waf_open())
        self.assertFalse(self.icp._detail_waf_open())

        # 触发详情熔断
        self.icp._detail_waf_trip("测试详情获取")

        # 详情熔断应开启，但全局列表熔断必须依然保持关闭（保护列表抓取不受殃及）
        self.assertTrue(self.icp._detail_waf_open())
        self.assertFalse(self.icp._waf_open())

    def test_is_global_waf_blocked_respects_proxies(self):
        """测试有健康代理时全局熔断不生效（保持不停机）"""
        # 触发列表熔断
        self.icp._waf_trip("测试列表查询")
        self.assertTrue(self.icp._waf_open())

        # 单 IP 模式（无健康代理可用）-> 全局熔断生效
        with patch.object(self.icp, "_has_healthy_proxy", return_value=False):
            self.assertTrue(self.icp._is_global_waf_blocked())

        # 多代理模式（有健康代理可用）-> 全局熔断不生效（自动由健康代理接管）
        with patch.object(self.icp, "_has_healthy_proxy", return_value=True):
            self.assertFalse(self.icp._is_global_waf_blocked())

    def test_is_rate_limited_hints(self):
        """测试 MIIT 业务层限流文案的精准识别"""
        self.assertTrue(self.icp._is_rate_limited("您目前访问频次过高[访问ip:1.2.3.4]，请稍后再试"))
        self.assertTrue(self.icp._is_rate_limited("操作频繁，请稍候再试"))
        self.assertTrue(self.icp._is_rate_limited("请求过快"))
        self.assertFalse(self.icp._is_rate_limited("查询成功"))
        self.assertFalse(self.icp._is_rate_limited(None))


class TestWafCooldownWaitOnce(unittest.IsolatedAsyncioTestCase):
    """熔断等待重试一次语义：命中即等（至多一次），而非永久跳过"""

    def _load_wait_fn(self):
        path = os.path.abspath(os.path.join(
            os.path.dirname(__file__), "..", "osint_service", "clients", "job_runner.py"))
        src = open(path, encoding="utf-8").read()
        ns = {"__name__": "job_runner_wait_test"}
        # 仅提取等待函数与其常量，避免拉起 motor/mongo 连接
        start = src.index("WAF_WAIT_MAX_SECONDS = 300")
        end = src.index("async def _claim_recon_task")
        chunk = "import asyncio\nimport logging\nimport time\nlogger = logging.getLogger(__name__)\n" + src[start:end]
        exec(compile(chunk, path, "exec"), ns)
        return ns["_wait_waf_cooldown_once"], ns["WAF_WAIT_MAX_SECONDS"]

    async def test_no_wait_when_cooldown_expired(self):
        fn, _ = self._load_wait_fn()
        fake = type("M", (), {"_waf_block_ts": time.time() - 400, "waf_cooldown": 300})()
        self.assertTrue(await fn(fake, "tid", "场景"))

    async def test_skip_when_wait_exceeds_cap(self):
        fn, cap = self._load_wait_fn()
        fake = type("M", (), {"_waf_block_ts": time.time(), "waf_cooldown": 9999})()
        self.assertFalse(await fn(fake, "tid", "场景"))
        self.assertEqual(cap, 300)

    async def test_wait_then_proceed_once(self):
        fn, _ = self._load_wait_fn()
        logged = []
        async def fake_log(level, title, msg):
            logged.append((level, title, msg))
        fake = type("M", (), {"_waf_block_ts": time.time() - 299, "waf_cooldown": 300})()
        t0 = time.time()
        self.assertTrue(await fn(fake, "tid", "场景", insert_syslog=fake_log))
        self.assertLess(time.time() - t0, 30)
        self.assertTrue(any("重试一次" in m for _, _, m in logged))


class TestOsintProxyRouterAndFailover(unittest.IsolatedAsyncioTestCase):
    """OSINT 多协议代理路由、按物理出口控频、故障瞬时转移与 300s 自动回切契约测试"""

    def setUp(self):
        from proxy_router import OsintProxyRouter, bump_global_reset_epoch
        bump_global_reset_epoch()
        self.OsintProxyRouter = OsintProxyRouter

    async def test_per_exit_rate_slot_isolated_and_floor_enforced(self):
        """直连与每个备用节点必须独立持有物理流控锁，且各自严守 interval_range 下限"""
        router = self.OsintProxyRouter({
            "policy": {"mode": "failover", "cooldown_sec": 300},
            "nodes": [{"id": "ecs-1", "name": "华为ECS", "protocol": "socks5h", "proxy_url": "socks5h://192.0.2.50:1080", "host": "192.0.2.50"}],
        })
        # 先验证同出口连续两次请求强制间隔 >=0.12s（以短窗口模拟 2.6s 物理间隔锁）
        with patch("proxy_router.random.uniform", return_value=0.12):
            await router.acquire_rate_slot(exit_id="ecs-1", interval_range=(0.12, 0.12))
            t1 = time.monotonic()
            await router.acquire_rate_slot(exit_id="ecs-1", interval_range=(0.12, 0.12))
            t2 = time.monotonic()
            self.assertGreaterEqual(t2 - t1, 0.10)

            # 不同物理出口 (__direct__ vs ecs-1) 互不阻塞，切换后首跳立即执行
            t3 = time.monotonic()
            await router.acquire_rate_slot(exit_id="__direct__", interval_range=(0.12, 0.12))
            t4 = time.monotonic()
            self.assertLess(t4 - t3, 0.08)

    async def test_failover_in_flight_direct_waf_to_backup_and_300s_auto_failback(self):
        """主出口创宇盾 403 -> 同请求瞬时切换备机成功 -> 300s 期满自动优先回切主直连"""
        from ymicp import _ExitAttemptError
        icp = beian()
        syslog_events = []

        async def _capture_log(level, title, msg):
            syslog_events.append((level, title, msg))

        router = self.OsintProxyRouter(
            {
                "policy": {"mode": "failover", "cooldown_sec": 300, "max_failovers": 2},
                "nodes": [
                    {
                        "id": "ecs-1",
                        "name": "备用ECS",
                        "protocol": "socks5h",
                        "proxy_url": "socks5h://user:pwd@192.0.2.51:1080",
                        "host": "192.0.2.51",
                    }
                ],
            },
            syslog_cb=_capture_log,
        )
        icp.attach_proxy_router(router)

        tried_exits = []

        async def _fake_attempt(name, sp, pageNum, pageSize, cand, force_token=False):
            tried_exits.append((cand.exit_id, force_token))
            if cand.exit_id == "__direct__":
                raise _ExitAttemptError("waf_blocked", "创宇盾拦截", blocked_ip="198.51.100.1", cooldown_sec=300)
            return True, {"success": True, "params": {"list": [{"domain": "example.com"}]}}, None

        with patch.object(icp, "_query_beian_page_once", side_effect=_fake_attempt):
            ok, payload, _ = await icp._query_beian_page("示例企业", 0, 1, 20)

        self.assertTrue(ok)
        self.assertEqual(payload["params"]["list"][0]["domain"], "example.com")
        self.assertEqual(tried_exits, [("__direct__", False), ("ecs-1", True)])
        self.assertTrue(router.is_exit_blocked("__direct__"))
        self.assertEqual(router.active_exit_id, "ecs-1")
        self.assertEqual(router.get_candidates()[0].exit_id, "ecs-1")
        self.assertTrue(any("切换至" in msg for _, _, msg in syslog_events))

        # 模拟 300s 冷却窗口期满：主直连自动恢复为第一候选出口
        router.blocked_exits["__direct__"]["until_ts"] = time.time() - 1
        self.assertFalse(router.is_exit_blocked("__direct__"))
        self.assertEqual(router.get_candidates()[0].exit_id, "__direct__")

    async def test_reset_cooldown_unblocks_immediately_and_earliest_delay_computed(self):
        """全部出口冷却时返回最短解封延迟；管理员重置冷却后立即解封"""
        from proxy_router import bump_global_reset_epoch
        router = self.OsintProxyRouter({
            "policy": {"mode": "failover", "cooldown_sec": 300},
            "nodes": [{"id": "ecs-1", "name": "ECS", "protocol": "http", "proxy_url": "http://192.0.2.60:8080", "host": "192.0.2.60"}],
        })
        router.mark_exit_blocked("__direct__", reason="WAF", cooldown_sec=300)
        router.mark_exit_blocked("ecs-1", reason="WAF", cooldown_sec=120)
        self.assertTrue(router.is_all_exits_blocked())
        delay = router.earliest_unblock_delay()
        self.assertGreater(delay, 90.0)
        self.assertLessEqual(delay, 121.0)

        bump_global_reset_epoch()
        self.assertFalse(router.is_all_exits_blocked())
        self.assertEqual(router.earliest_unblock_delay(), 0.0)
        self.assertEqual(router.get_candidates()[0].exit_id, "__direct__")

    async def test_build_aiohttp_connector_socks5_vs_http(self):
        """SOCKS5/SOCKS5H 返回 ProxyConnector 且 req_proxy=None，HTTP 返回 TCPConnector 与 proxy_url"""
        from proxy_router import build_aiohttp_connector
        import types

        conn_http, proxy_http = build_aiohttp_connector("http://192.0.2.10:8080")
        try:
            self.assertEqual(proxy_http, "http://192.0.2.10:8080")
        finally:
            await conn_http.close()

        captured = {}

        class _FakeProxyConnector:
            @classmethod
            def from_url(cls, url, rdns=False, **kwargs):
                # 模拟 python_socks.parse_proxy_url 仅接受 socks5 / socks4 scheme
                if url.startswith(("socks5h://", "socks4a://")):
                    raise ValueError(f"Invalid scheme component: {url.split('://', 1)[0]}")
                captured["url"] = url
                captured["rdns"] = rdns
                captured["kwargs"] = kwargs
                inst = cls()
                return inst

            async def close(self):
                pass

        fake_mod = types.ModuleType("aiohttp_socks")
        fake_mod.ProxyConnector = _FakeProxyConnector
        with patch.dict(sys.modules, {"aiohttp_socks": fake_mod}):
            conn_socks, proxy_socks = build_aiohttp_connector("socks5h://u:p@192.0.2.11:1080")
            await conn_socks.close()

        self.assertIsNone(proxy_socks)
        self.assertEqual(captured["url"], "socks5://u:p@192.0.2.11:1080")
        self.assertTrue(captured["rdns"])

    async def test_async_tyc_failover_on_419_banned_location(self):
        """AsyncTycClient 命中 419 bannedLocation 时瞬时切到备用代理完成查询"""
        from clients.tyc_async import AsyncTycClient
        router = self.OsintProxyRouter({
            "policy": {"mode": "failover", "cooldown_sec": 300},
            "nodes": [{"id": "ecs-cn", "name": "境内ECS", "protocol": "http", "proxy_url": "http://192.0.2.77:8080", "host": "192.0.2.77"}],
        })
        client = AsyncTycClient("gid", "tok", proxy_router=router)
        calls = []

        class _FakeResCtx:
            def __init__(self, status, payload):
                self.status = status
                self._payload = payload
                self.headers = {"Content-Type": "application/json"}

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            async def text(self):
                import json
                return json.dumps(self._payload)

            async def json(self):
                return self._payload

        class _FakeSession:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, *args):
                return False

            def get(self, url, **kwargs):
                proxy_arg = kwargs.get("proxy")
                calls.append(proxy_arg)
                if not proxy_arg:
                    return _FakeResCtx(419, {"message": "bannedLocation", "errorCode": "301000"})
                return _FakeResCtx(200, {"state": "ok", "data": {"companyName": "示例公司"}})

        with patch("asyncio.sleep", return_value=None), patch("clients.tyc_async.aiohttp.ClientSession", _FakeSession):
            data = await client._request("GET", "/cloud-company-background/test")

        self.assertEqual(data, {"companyName": "示例公司"})
        self.assertEqual(calls, [None, "http://192.0.2.77:8080"])
        self.assertTrue(router.is_exit_blocked("__direct__"))
        self.assertEqual(router.active_exit_id, "ecs-cn")

    async def test_sync_from_db_handles_motor_truth_value_forbidden(self):
        """Motor/PyMongo Database 禁止 bool(db) 时，sync_from_db 必须使用 `is not None` 避免抛出 NotImplementedError"""
        router = self.OsintProxyRouter()

        class _StrictCollection:
            async def find_one(self, query, projection=None):
                _id = query.get("_id")
                if _id == "proxy_config":
                    return {
                        "nodes": [
                            {
                                "id": "hw",
                                "name": "Huawei-ECS",
                                "protocol": "socks5h",
                                "host": "192.0.2.88",
                                "port": 80,
                                "enabled": True,
                            }
                        ],
                        "policies": {
                            "osint": {
                                "mode": "failover",
                                "node_ids": ["hw"],
                                "include_direct": False,
                                "cooldown_sec": 300,
                            }
                        },
                    }
                if _id == "proxy_runtime":
                    return {"blocked_exits": {}}
                return None

        class _StrictMotorDatabase:
            def __bool__(self):
                raise NotImplementedError(
                    "Database objects do not implement truth value testing or bool(). "
                    "Please compare with None instead: database is not None"
                )

            def __getitem__(self, name):
                return _StrictCollection()

        await router.sync_from_db(_StrictMotorDatabase())
        self.assertTrue(router.has_structured_policy)
        self.assertEqual(router.get_mode(), "failover")
        self.assertEqual(len(router.nodes), 1)
        self.assertEqual(router.nodes[0]["id"], "hw")


if __name__ == "__main__":
    unittest.main()
