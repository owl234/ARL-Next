import os
import sys
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import dns.exception
import dns.resolver

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


class TestDnsServerHealthCircuitBreaker(unittest.TestCase):
    """验证上游 DNS 节点动态熔断冷却、局部超时剔除与全冷却兜底。"""

    def setUp(self):
        from app.utils import dns_client
        dns_client.reset_dns_server_health()

    def tearDown(self):
        from app.utils import dns_client
        dns_client.reset_dns_server_health()

    def test_dead_server_quarantined_after_threshold_failures(self):
        from app.utils import dns_client

        servers = ("192.0.2.10", "192.0.2.20", "192.0.2.30")
        seen_batches = []

        class FakeAnswer(list):
            def __init__(self, ips, nameserver):
                super().__init__(ips)
                self.nameserver = nameserver

        class FakeRData:
            def __init__(self, address):
                self.address = address

        def fake_build_resolver(nameservers=None, timeout=2.5, lifetime=5.0):
            seen_batches.append(list(nameservers or []))
            resolver = MagicMock()
            if nameservers and nameservers[0] == "192.0.2.10":
                # 模拟首节点超时后由第二个健康节点应答
                ans = FakeAnswer([FakeRData("203.0.113.5")], nameserver=nameservers[1])
                resolver.resolve.return_value = ans
            else:
                ans = FakeAnswer([FakeRData("203.0.113.5")], nameserver=nameservers[0])
                resolver.resolve.return_value = ans
            return resolver

        with patch.object(dns_client, "_load_dns_servers", return_value=servers), \
             patch.object(dns_client, "_build_resolver", side_effect=fake_build_resolver), \
             patch.object(dns_client, "_get_logger", return_value=MagicMock()):
            # 连续触发两次 192.0.2.10 首节点失败后进入冷却
            dns_client._record_server_failure("192.0.2.10")
            with patch.object(dns_client, "_next_cursor", return_value=0):
                ips, transient = dns_client.resolve_records("ok.example.com", rdtype="A", retries=0, backoff_base=0)
            self.assertFalse(transient)
            self.assertEqual(ips, ["203.0.113.5"])

            # 此后选择批次应跳过处于冷却期的 192.0.2.10
            next_batch = dns_client._select_nameservers(servers, attempt=0, batch_size=4)
            self.assertNotIn("192.0.2.10", next_batch)
            self.assertEqual(set(next_batch), {"192.0.2.20", "192.0.2.30"})

    def test_lifetime_timeout_only_penalizes_failing_servers_in_errors(self):
        from app.utils import dns_client

        servers = ("192.0.2.1", "192.0.2.2", "192.0.2.3", "192.0.2.4")

        def fake_build_resolver(nameservers=None, timeout=2.5, lifetime=5.0):
            resolver = MagicMock()
            exc = dns.resolver.LifetimeTimeout(
                timeout=5.0,
                errors=[
                    ("192.0.2.1", False, 53, dns.exception.Timeout("timed out"), None),
                    ("192.0.2.2", False, 53, dns.exception.Timeout("timed out"), None),
                ],
            )
            resolver.resolve.side_effect = exc
            return resolver

        with patch.object(dns_client, "_load_dns_servers", return_value=servers), \
             patch.object(dns_client, "_build_resolver", side_effect=fake_build_resolver), \
             patch.object(dns_client, "_next_cursor", return_value=0), \
             patch.object(dns_client, "_get_logger", return_value=MagicMock()):
            ips, transient = dns_client.resolve_records("timeout.example.com", rdtype="A", retries=1, backoff_base=0)

        self.assertTrue(transient)
        self.assertEqual(ips, [])
        # 仅 192.0.2.1 / 192.0.2.2 被记录失败并隔离，未尝试的 192.0.2.3 / 192.0.2.4 保持健康
        healthy = dns_client._filter_healthy_servers(servers)
        self.assertEqual(set(healthy), {"192.0.2.3", "192.0.2.4"})

    def test_all_servers_cooled_down_still_falls_back_gracefully(self):
        from app.utils import dns_client

        servers = ("192.0.2.1", "192.0.2.2")
        base_now = 1000.0
        dns_client._record_server_failure("192.0.2.1", now=base_now)
        dns_client._record_server_failure("192.0.2.1", now=base_now)
        dns_client._record_server_failure("192.0.2.2", now=base_now + 10.0)
        dns_client._record_server_failure("192.0.2.2", now=base_now + 10.0)

        fallback = dns_client._filter_healthy_servers(servers, now=base_now + 20.0)
        self.assertEqual(fallback, ("192.0.2.1", "192.0.2.2"))

    def test_dnsserver_dict_excludes_known_dead_resolvers(self):
        dict_path = os.path.join(BACKEND_DIR, "app", "dicts", "dnsserver.txt")
        with open(dict_path, "r", encoding="utf-8") as f:
            entries = {line.strip() for line in f if line.strip() and not line.startswith("#")}
        for dead_ip in ("182.254.116.116", "182.254.118.118", "117.85.70.226"):
            self.assertNotIn(dead_ip, entries)
        self.assertGreaterEqual(len(entries), 10)


class TestCdnCnameRoutingFilter(unittest.TestCase):
    """验证第三方多租户 CDN CNAME 边缘路由子域精准过滤且不误伤根域与常规子域。"""

    def test_matches_third_party_routing_subdomains_and_preserves_legitimate_hosts(self):
        from app.utils.cdn import is_cdn_cname_routing_subdomain

        # 应拦截：明确路由前缀下的第三方客户子域
        for dom in (
            "api.customer.example.com.eo.dnse5.com",
            "tenant.example.org.eo.dnse4.com",
            "web.example.net.eo.dnse3.com",
            "docs.example.com.pages.dnsoe5.com",
            "foo.eo.dnsoe7.net",
            "img.customer.example.com.cdn.dnsv1.com",
            "app.customer.example.com.cdns.edgeone.site",
            "site.customer.example.com.pages.edgeone.ai",
            "static.customer.example.com.tc.cdntip.com",
            "shop.customer.example.com.w.kunlunsl.com",
            "dl.customer.example.com.alikunlun.com",
        ):
            self.assertTrue(is_cdn_cname_routing_subdomain(dom, base_domain="dnse5.com"), f"应过滤 {dom}")

        # 应保留：根域、常规设施子域、非路由前缀子域、普通公司业务域
        for dom in (
            "dnse5.com",
            "ns1.dnse5.com",
            "www.dnse5.com",
            "eo.dnse5.com",
            "pages.dnsoe5.com",
            "dnsoe5.com",
            "ad1.dnsv1.net",
            "dnssec1.dnsv1.net",
            "hy.dnsv20.com",
            "eo.corp.example.com",
            "cdn.corp.example.com",
            "api.example.com",
        ):
            self.assertFalse(is_cdn_cname_routing_subdomain(dom, base_domain="dnse5.com"), f"不应误杀 {dom}")

        # 显式定向扫描该路由子域本身时豁免
        self.assertFalse(
            is_cdn_cname_routing_subdomain(
                "api.customer.example.com.eo.dnse5.com",
                base_domain="api.customer.example.com.eo.dnse5.com",
            )
        )

    def test_dns_query_base_filters_cdn_routing_subdomains(self):
        from app.services.dns_query import DNSQueryBase

        class DummyPlugin(DNSQueryBase):
            def __init__(self):
                super().__init__()
                self.source_name = "dummy"

            def sub_domains(self, target):
                return [
                    "ns1.dnse5.com",
                    "www.dnse5.com",
                    "eo.dnse5.com",
                    "tenant-a.example.com.eo.dnse5.com",
                    "api.tenant-a.example.com.eo.dnse5.com",
                    "tenant-b.example.org.eo.dnse5.com",
                ]

        plugin = DummyPlugin()
        with patch("app.utils.check_domain_black", return_value=False):
            results = plugin.query("dnse5.com")

        self.assertEqual(set(results), {"ns1.dnse5.com", "www.dnse5.com", "eo.dnse5.com"})


class TestWildcardProbeHardening(unittest.TestCase):
    """验证 DomainExecutor.set_wildcard_ip_set() 的并发探测、NXDOMAIN 早退、父域剪枝与耗时预算。"""

    def _make_executor(self, base_domain, domains):
        from app.tasks.scheduler import DomainExecutor

        with patch("app.tasks.domain.get_scan_ports", return_value="80,443"):
            executor = DomainExecutor(
                base_domain,
                "000000000000000000000001",
                {"scope_id": "000000000000000000000002"},
            )
        executor.new_domain_set = set(domains)
        return executor

    def test_prunes_single_child_parents_and_sorts_by_child_count(self):
        domains = {
            # 3 个子域聚集在 hot.example.com
            "a.hot.example.com",
            "b.hot.example.com",
            "c.hot.example.com",
            # 2 个子域聚集在 warm.example.com
            "x.warm.example.com",
            "y.warm.example.com",
            # 多个仅含 1 个子域的叶子父域应被裁剪
            "leaf.one1.example.com",
            "leaf.one2.example.com",
            "leaf.one3.example.com",
        }
        executor = self._make_executor("example.com", domains)
        executor.WILDCARD_MAX_PARENTS = 3
        executor.WILDCARD_MIN_CHILDREN = 2

        probe_parents, total_unique, eligible = executor._select_wildcard_probe_parents()
        self.assertEqual(probe_parents, ["example.com", "hot.example.com", "warm.example.com"])
        self.assertEqual(eligible, 2)
        self.assertGreaterEqual(total_unique, 6)

    def test_nxdomain_early_exit_skips_cname_and_remaining_rounds(self):
        domains = {"a.wild.example.com", "b.wild.example.com", "a.clean.example.com", "b.clean.example.com"}
        executor = self._make_executor("example.com", domains)

        ip_calls = []
        cname_calls = []

        def fake_get_ip_with_status(domain, log_flag=False, retries=1):
            ip_calls.append(domain)
            if domain.endswith(".wild.example.com"):
                return ["198.51.100.7"], False
            # 确定性 NXDOMAIN
            return [], False

        def fake_get_cname(domain, log_flag=False, retries=1):
            cname_calls.append(domain)
            if domain.endswith(".wild.example.com"):
                return ["wild-lb.example.com"]
            return []

        with patch("app.utils.get_ip_with_status", side_effect=fake_get_ip_with_status), \
             patch("app.utils.get_cname", side_effect=fake_get_cname):
            executor.set_wildcard_ip_set()

        # wild.example.com 应命中泛解析（3 轮 A + 3 轮 CNAME）
        self.assertIn("wild.example.com", executor.wildcard_map)
        self.assertEqual(executor.wildcard_map["wild.example.com"]["ips"], {"198.51.100.7"})
        self.assertEqual(executor.wildcard_map["wild.example.com"]["static_cnames"], {"wild-lb.example.com"})
        self.assertFalse(executor.wildcard_map["wild.example.com"]["is_rotating"])

        # 非泛解析父域（example.com / clean.example.com）确定性 NXDOMAIN 仅查 1 次 A 且 0 次 CNAME
        clean_ip_calls = [d for d in ip_calls if d.endswith(".clean.example.com")]
        base_ip_calls = [d for d in ip_calls if d.endswith(".example.com") and ".clean." not in d and ".wild." not in d]
        self.assertEqual(len(clean_ip_calls), 1)
        self.assertEqual(len(base_ip_calls), 1)
        self.assertEqual(len(cname_calls), 3)
        self.assertTrue(all(d.endswith(".wild.example.com") for d in cname_calls))

    def test_concurrent_execution_and_time_budget_enforcement(self):
        # 构造 20 个满足 >=2 子节点的父域，验证并发执行与耗时预算早停
        domains = set()
        for i in range(20):
            domains.add(f"a.p{i}.example.com")
            domains.add(f"b.p{i}.example.com")

        executor = self._make_executor("example.com", domains)
        executor.WILDCARD_PROBE_CONCURRENCY = 5
        executor.WILDCARD_PROBE_BUDGET_SECONDS = 0.15

        active_threads = 0
        peak_threads = 0
        lock = threading.Lock()
        probed = []

        def slow_get_ip(domain, log_flag=False, retries=1):
            nonlocal active_threads, peak_threads
            with lock:
                active_threads += 1
                peak_threads = max(peak_threads, active_threads)
                probed.append(domain)
            try:
                time.sleep(0.08)
                return [], False
            finally:
                with lock:
                    active_threads -= 1

        t0 = time.monotonic()
        with patch("app.utils.get_ip_with_status", side_effect=slow_get_ip), \
             patch("app.utils.get_cname", return_value=[]):
            executor.set_wildcard_ip_set()
        elapsed = time.monotonic() - t0

        self.assertGreaterEqual(peak_threads, 2, "泛解析探测应并发执行")
        self.assertLess(elapsed, 0.8, "耗时预算应阻断长尾父域无止境探测")
        self.assertLess(len(probed), 21, "预算耗尽后应跳过剩余父域")


class TestDnsServerVolumeMigration(unittest.TestCase):
    """验证持久化卷 arl_app_dicts 中 dnsserver.txt 的补缺播种与一次性幂等清理。"""

    def _make_fake_sys_db(self):
        store = {}

        class FakeSysConfigCollection:
            def find_one(self, query):
                return store.get(query.get("_id"))

            def update_one(self, query, update, upsert=False):
                doc_id = query.get("_id")
                if doc_id not in store:
                    if not upsert:
                        return
                    store[doc_id] = {"_id": doc_id}
                for key, value in (update.get("$set") or {}).items():
                    store[doc_id][key] = value

        return store, FakeSysConfigCollection()

    def test_auto_seeds_missing_dnsserver_file(self):
        import tempfile
        from app.utils import arlupdate

        with tempfile.TemporaryDirectory() as tmpdir:
            res = arlupdate.ensure_dnsserver_dict(dict_dir=tmpdir)
            self.assertEqual(res["action"], "seeded")
            path = os.path.join(tmpdir, "dnsserver.txt")
            self.assertTrue(os.path.exists(path))
            with open(path, "r", encoding="utf-8") as f:
                entries = [line.strip() for line in f if line.strip() and not line.startswith("#")]
            self.assertEqual(tuple(entries), arlupdate.DEFAULT_DNS_SERVERS)
            for dead_ip in arlupdate.DEAD_DNS_SERVERS_V1:
                self.assertNotIn(dead_ip, entries)

    def test_prunes_dead_dns_servers_once_and_preserves_custom_entries(self):
        import tempfile
        from app.utils import arlupdate

        store, fake_sys_db = self._make_fake_sys_db()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "dnsserver.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    "# corp custom dns\n"
                    "223.5.5.5\n"
                    "182.254.116.116\n"
                    "10.0.0.53\n"
                    "182.254.118.118\n"
                    "117.85.70.226\n"
                    "1.1.1.1\n"
                )

            with patch.object(arlupdate, "conn_db", return_value=fake_sys_db):
                res1 = arlupdate.ensure_dnsserver_dict(dict_dir=tmpdir)
                self.assertEqual(res1["action"], "pruned")
                self.assertEqual(set(res1["removed"]), set(arlupdate.DEAD_DNS_SERVERS_V1))
                self.assertEqual(
                    store["migration_prune_dead_dnsservers_v1"]["status"],
                    "completed",
                )

                with open(path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
                self.assertEqual(lines, ["# corp custom dns", "223.5.5.5", "10.0.0.53", "1.1.1.1"])

                # 哨兵落盘后若管理员手工追加内容，再次启动不得覆盖
                with open(path, "a", encoding="utf-8") as f:
                    f.write("117.85.70.226\n")
                res2 = arlupdate.ensure_dnsserver_dict(dict_dir=tmpdir)
                self.assertEqual(res2["action"], "skipped")
                with open(path, "r", encoding="utf-8") as f:
                    lines_after = f.read().splitlines()
                self.assertIn("117.85.70.226", lines_after)

    def test_re_seeds_baseline_if_only_dead_dns_servers_existed(self):
        import tempfile
        from app.utils import arlupdate

        store, fake_sys_db = self._make_fake_sys_db()
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "dnsserver.txt")
            with open(path, "w", encoding="utf-8") as f:
                f.write("182.254.116.116\n117.85.70.226\n")

            with patch.object(arlupdate, "conn_db", return_value=fake_sys_db):
                res = arlupdate.ensure_dnsserver_dict(dict_dir=tmpdir)
            self.assertEqual(res["action"], "fallback_seeded")
            self.assertTrue(store["migration_prune_dead_dnsservers_v1"]["seeded_fallback"])
            with open(path, "r", encoding="utf-8") as f:
                entries = [line.strip() for line in f if line.strip()]
            self.assertEqual(tuple(entries), arlupdate.DEFAULT_DNS_SERVERS)


if __name__ == "__main__":
    unittest.main()
