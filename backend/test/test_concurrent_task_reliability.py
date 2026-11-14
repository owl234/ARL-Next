import ast
import itertools
import os
import sys
import tempfile
import threading
import time
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import dns.exception
import dns.resolver
from bson import ObjectId

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)


class InMemoryLeaseCollection:
    """线程安全的轻量内存 Mongo 集合桩，模拟 condition-based update_one / update_many 原子语义。"""

    def __init__(self):
        self._lock = threading.Lock()
        self.docs = {}
        self.indexes = []

    def _matches(self, doc, query):
        if not query:
            return True
        for key, cond in query.items():
            if key == "$or":
                if not any(self._matches(doc, branch) for branch in cond):
                    return False
                continue
            val = doc.get(key)
            if isinstance(cond, dict):
                if "$exists" in cond:
                    exists = key in doc
                    if exists != bool(cond["$exists"]):
                        return False
                if "$lt" in cond:
                    if not isinstance(val, (int, float)) or not (val < cond["$lt"]):
                        return False
                if "$nin" in cond:
                    if val in cond["$nin"]:
                        return False
            else:
                if val != cond:
                    return False
        return True

    def find_one(self, query):
        with self._lock:
            for doc in self.docs.values():
                if self._matches(doc, query):
                    return dict(doc)
        return None

    def find(self, query=None):
        with self._lock:
            return [dict(doc) for doc in self.docs.values() if self._matches(doc, query or {})]

    def update_one(self, query, update, upsert=False):
        with self._lock:
            for key, doc in self.docs.items():
                if self._matches(doc, query):
                    if "$set" in update:
                        doc.update(update["$set"])
                    return SimpleNamespace(matched_count=1, modified_count=1)
            if upsert:
                new_doc = {}
                if "_id" in query and not isinstance(query["_id"], dict):
                    new_doc["_id"] = query["_id"]
                else:
                    new_doc["_id"] = ObjectId()
                if "$setOnInsert" in update:
                    new_doc.update(update["$setOnInsert"])
                if "$set" in update:
                    new_doc.update(update["$set"])
                self.docs[new_doc["_id"]] = new_doc
                return SimpleNamespace(matched_count=0, modified_count=1)
            return SimpleNamespace(matched_count=0, modified_count=0)

    def update_many(self, query, update):
        with self._lock:
            modified = 0
            for doc in self.docs.values():
                if self._matches(doc, query):
                    if "$set" in update:
                        doc.update(update["$set"])
                    modified += 1
            return SimpleNamespace(matched_count=modified, modified_count=modified)

    def create_index(self, keys, **kwargs):
        self.indexes.append((keys, kwargs))


def _load_performance_resource():
    source_path = os.path.join(BACKEND_ROOT, "app", "routes", "system_config.py")
    with open(source_path, "r", encoding="utf-8") as handle:
        tree = ast.parse(handle.read(), filename=source_path)

    selected = []
    for node in tree.body:
        if isinstance(node, ast.Assign):
            names = [t.id for t in node.targets if isinstance(t, ast.Name)]
            if any(name.startswith("_POOL_SETTLE") for name in names):
                selected.append(node)
        elif isinstance(node, ast.FunctionDef):
            if node.name.startswith("_runtime_") or node.name == "_wait_pool_size":
                selected.append(node)
        elif isinstance(node, ast.ClassDef) and node.name == "Performance":
            selected.append(node)

    get_perf = MagicMock()
    update_perf = MagicMock()

    env = {
        "ARLResource": object,
        "ns": SimpleNamespace(route=lambda *a, **kw: (lambda cls: cls), expect=lambda *a, **kw: (lambda fn: fn)),
        "auth": lambda fn: fn,
        "get_performance_config": get_perf,
        "update_performance_config": update_perf,
        "performance_model": object(),
    }
    module = ast.Module(body=selected, type_ignores=[])
    ast.fix_missing_locations(module)
    exec(compile(module, source_path, "exec"), env)
    return env["Performance"], get_perf, update_perf


class Branch1DnsClientTests(unittest.TestCase):
    """验证分支 1：独立 DNS 客户端重试、公共 DNS 池与 MassDNS 解析复用。"""

    def test_extract_massdns_records_separates_cname_and_chases_a_chain(self):
        from app.utils.dns_client import extract_massdns_records

        raw = [
            {"domain": "www.example.com.", "type": "CNAME", "record": "cdn.example.com."},
            {"domain": "cdn.example.com.", "type": "A", "record": "93.184.216.34"},
            {"domain": "api.example.com.", "type": "A", "record": "93.184.216.35"},
            {"domain": "bad.example.com.", "type": "A", "record": "0.0.0.1"},
        ]
        extracted = extract_massdns_records(raw)

        self.assertEqual(extracted["www.example.com"]["cnames"], ["cdn.example.com"])
        self.assertEqual(extracted["www.example.com"]["ips"], ["93.184.216.34"])
        self.assertEqual(extracted["api.example.com"]["ips"], ["93.184.216.35"])
        self.assertEqual(extracted["bad.example.com"]["ips"], [])

    def test_resolve_records_retries_transient_timeout_and_distinguishes_nxdomain(self):
        from app.utils import dns_client

        call_nameservers = []

        class FakeRData:
            def __init__(self, address):
                self.address = address

        def fake_build_resolver(nameservers=None, timeout=2.5, lifetime=5.0):
            call_nameservers.append(nameservers)
            resolver = MagicMock()
            if len(call_nameservers) == 1:
                resolver.resolve.side_effect = dns.exception.Timeout("timed out")
            else:
                resolver.resolve.return_value = [FakeRData("203.0.113.10")]
            return resolver

        with patch.object(dns_client, "_load_dns_servers", return_value=("223.5.5.5", "119.29.29.29", "8.8.8.8", "1.1.1.1")), \
             patch.object(dns_client, "_build_resolver", side_effect=fake_build_resolver), \
             patch.object(dns_client, "_get_logger", return_value=MagicMock()):
            ips, transient = dns_client.resolve_records("retry.example.com", rdtype="A", retries=2, backoff_base=0)

        self.assertFalse(transient)
        self.assertEqual(ips, ["203.0.113.10"])
        self.assertEqual(len(call_nameservers), 2)
        self.assertNotEqual(call_nameservers[0], None)

        nx_attempts = []

        def fake_nx_resolver(nameservers=None, timeout=2.5, lifetime=5.0):
            nx_attempts.append(nameservers)
            resolver = MagicMock()
            resolver.resolve.side_effect = dns.resolver.NXDOMAIN()
            return resolver

        with patch.object(dns_client, "_load_dns_servers", return_value=("223.5.5.5",)), \
             patch.object(dns_client, "_build_resolver", side_effect=fake_nx_resolver), \
             patch.object(dns_client, "_get_logger", return_value=MagicMock()):
            ips, transient = dns_client.resolve_records("missing.example.com", rdtype="A", retries=2, backoff_base=0)

        self.assertFalse(transient)
        self.assertEqual(ips, [])
        self.assertEqual(len(nx_attempts), 1, "NXDOMAIN 属于确定性否定，不应触发额外重试")

    def test_resolver_domain_and_build_domain_info_reuse_pre_resolved_and_track_transient(self):
        from app.services.resolverDomain import resolver_domain
        from app.services.buildDomainInfo import build_domain_info

        with patch("app.utils.get_ip_with_status") as mock_get_ip:
            mock_get_ip.return_value = ([], True)
            res = resolver_domain(
                ["cached.example.com", "timeout.example.com"],
                concurrency=2,
                pre_resolved={"cached.example.com": ["192.0.2.1"]},
            )
            self.assertEqual(res["cached.example.com"], ["192.0.2.1"])
            self.assertEqual(res["timeout.example.com"], [])
            mock_get_ip.assert_called_once_with("timeout.example.com")

        with patch("app.utils.get_ip_with_status") as mock_ip, \
             patch("app.utils.get_cname") as mock_cname, \
             patch("app.utils.is_dynamic_ip_edge_domain", return_value=False):
            info_list = build_domain_info(
                ["cached.example.com"],
                concurrency=1,
                pre_resolved={"cached.example.com": {"ips": ["192.0.2.2"], "cnames": ["alias.example.net"]}},
            )
            self.assertEqual(len(info_list), 1)
            self.assertEqual(info_list[0].type, "CNAME")
            self.assertEqual(info_list[0].record_list, ["alias.example.net"])
            self.assertEqual(info_list[0].ip_list, ["192.0.2.2"])
            mock_ip.assert_not_called()
            mock_cname.assert_not_called()


class Branch2PacketLeaseTests(unittest.TestCase):
    """验证分支 2：Mongo 原子槽位互斥、崩溃租约接管、flock 降级与启动迁移。"""

    def test_mongo_lease_enforces_slot_limit_and_reclaims_expired_slot(self):
        from app.utils.packet_lease import acquire_packet_slot, release_task_packet_slots

        col = InMemoryLeaseCollection()
        # 模拟曾崩溃遗留的过期占锁记录（ttl 已过期）
        col.docs["packet_slot_0"] = {
            "_id": "packet_slot_0",
            "state": "busy",
            "owner_id": "dead-worker:1",
            "task_id": "dead-task",
            "expires_at": time.time() - 5,
        }

        active = 0
        peak = 0
        lock = threading.Lock()

        def worker(idx):
            nonlocal active, peak
            with acquire_packet_slot(
                phase="massdns",
                task_id=f"t-{idx}",
                max_slots=1,
                lease_ttl=30,
                wait_timeout=5,
                poll_interval=0.05,
                collection=col,
            ):
                with lock:
                    active += 1
                    peak = max(peak, active)
                time.sleep(0.08)
                with lock:
                    active -= 1

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10)

        self.assertEqual(peak, 1)
        self.assertEqual(col.docs["packet_slot_0"]["state"], "free")

        # 验证 release_task_packet_slots 立即清除指定任务的占锁槽位
        col.docs["packet_slot_0"] = {"_id": "packet_slot_0", "state": "busy", "task_id": "crashed-123"}
        freed = release_task_packet_slots("crashed-123", collection=col)
        self.assertEqual(freed, 1)
        self.assertEqual(col.docs["packet_slot_0"]["state"], "free")

    def test_local_flock_fallback_serializes_when_mongo_unavailable(self):
        from app.utils import packet_lease

        active = 0
        peak = 0
        lock = threading.Lock()

        def worker(idx):
            nonlocal active, peak
            with packet_lease.acquire_packet_slot(
                phase="port_scan",
                task_id=f"offline-{idx}",
                max_slots=1,
                wait_timeout=5,
                poll_interval=0.05,
            ):
                with lock:
                    active += 1
                    peak = max(peak, active)
                time.sleep(0.06)
                with lock:
                    active -= 1

        with tempfile.TemporaryDirectory() as tmpdir, \
             patch("app.config.Config.TMP_PATH", tmpdir), \
             patch.object(packet_lease, "_mongo_lease_available", return_value=None):
            threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10)

        self.assertEqual(peak, 1)

    def test_ensure_packet_lease_schema_backfills_and_cleans_stale_slots(self):
        from app.utils import arlupdate

        sys_col = InMemoryLeaseCollection()
        lease_col = InMemoryLeaseCollection()
        lease_col.docs["packet_slot_0"] = {
            "_id": "packet_slot_0",
            "state": "busy",
            "task_id": "stale-task",
            "expires_at": time.time() - 60,
        }

        with patch.object(arlupdate, "conn_db", side_effect=lambda name: sys_col if name == "system_config" else lease_col):
            arlupdate.ensure_packet_lease_schema()

        self.assertEqual(sys_col.docs["packet_lease"]["max_slots"], 1)
        self.assertEqual(lease_col.docs["packet_slot_0"]["state"], "free")
        self.assertEqual(len(lease_col.indexes), 1)

        # MockCollection 缺 create_index / update_many 时也不应崩溃
        minimal_col = SimpleNamespace(update_one=MagicMock())
        with patch.object(arlupdate, "conn_db", return_value=minimal_col):
            arlupdate.ensure_packet_lease_schema()
        minimal_col.update_one.assert_called_once()

    def test_massdns_and_portscan_wrap_execution_with_packet_slot(self):
        from app.services.massdns import MassDNS
        from app.services.portScan import PortScan

        entered = []

        class RecorderCM:
            def __init__(self, phase):
                self.phase = phase

            def __enter__(self):
                entered.append(("enter", self.phase))
                return {"mode": "test"}

            def __exit__(self, exc_type, exc_val, exc_tb):
                entered.append(("exit", self.phase))
                return False

        with tempfile.TemporaryDirectory() as tmpdir, \
             patch("app.config.Config.MASSDNS_BIN", "/usr/bin/massdns"), \
             patch("app.config.Config.DNS_SERVER", "/tmp/dns.txt"), \
             patch("app.services.massdns.acquire_packet_slot", side_effect=lambda **kw: RecorderCM(kw["phase"])), \
             patch("app.services.massdns.utils.exec_system", return_value=SimpleNamespace(returncode=1)):
            md = MassDNS(["a.example.com"], mass_dns_bin="/usr/bin/massdns", dns_server="/tmp/dns.txt", tmp_dir=tmpdir)
            with self.assertRaises(RuntimeError):
                md.mass_dns()
            self.assertEqual(entered, [("enter", "massdns"), ("exit", "massdns")])
            self.assertEqual(os.listdir(tmpdir), [], "异常退出后也必须清理临时域名字典与输出文件")

        entered.clear()
        with patch("app.services.portScan.acquire_packet_slot", side_effect=lambda **kw: RecorderCM(kw["phase"])), \
             patch("app.services.portScan.nmap.PortScanner") as mock_scanner:
            ps = PortScan(targets=[], ports="80")
            self.assertEqual(ps.run(), [])
            mock_scanner.assert_not_called()

            scanner_inst = mock_scanner.return_value
            scanner_inst.all_hosts.return_value = []
            ps2 = PortScan(targets=["192.0.2.10"], ports="80")
            self.assertEqual(ps2.run(), [])
            self.assertEqual(entered, [("enter", "port_scan"), ("exit", "port_scan")])


class Branch3ConcurrencyDualStateTests(unittest.TestCase):
    """验证分支 3：Performance 接口返回 pending_convergence，以及 scheduler 空闲自收敛。"""

    def test_performance_post_and_get_expose_pending_convergence_fields(self):
        Performance, get_perf, update_perf = _load_performance_resource()
        get_perf.return_value = {
            "celery_heavy_concurrency": 4,
            "celery_light_concurrency": 2,
            "osint_concurrency": 2,
            "github_concurrency": 1,
        }

        inspector = MagicMock()
        # post 时重任务仍停留在 4，请求缩容到 2，模拟忙时缩容暂缓
        inspector.stats.return_value = {
            "arltask_heavy@n1": {"pool": {"processes": [1, 2, 3, 4]}},
            "arltask_light@n1": {"pool": {"processes": [1, 2]}},
            "arlgithub@n1": {"pool": {"processes": [1]}},
        }
        control = MagicMock()
        control.inspect.return_value = inspector
        control.pool_shrink.return_value = [{"arltask_heavy@n1": {"ok": "pool shrink started"}}]
        fake_celery = SimpleNamespace(control=control)

        res = Performance()
        res.get_parser = MagicMock(return_value=SimpleNamespace(parse_args=lambda: {
            "celery_heavy_concurrency": 2,
            "celery_light_concurrency": 2,
            "osint_concurrency": 2,
            "github_concurrency": 1,
        }))

        fake_mod = SimpleNamespace(celery=fake_celery)
        clock = itertools.count(0.0, 10.0)
        with patch.dict(sys.modules, {"app.celerytask": fake_mod}), \
             patch("time.monotonic", side_effect=lambda: next(clock)), \
             patch("time.sleep"):
            post_resp = res.post()

        self.assertEqual(post_resp["code"], 200)
        self.assertTrue(post_resp["pending_convergence"])
        self.assertEqual(len(post_resp["pending_nodes"]), 1)
        self.assertEqual(post_resp["pending_nodes"][0]["queue"], "arltask_heavy")
        self.assertEqual(post_resp["pending_nodes"][0]["reason"], "busy_deferred")

        get_perf.return_value = {
            "celery_heavy_concurrency": 2,
            "celery_light_concurrency": 2,
            "osint_concurrency": 2,
            "github_concurrency": 1,
        }
        with patch.dict(sys.modules, {"app.celerytask": fake_mod}):
            get_resp = res.get()
        self.assertTrue(get_resp["data"]["pending_convergence"])
        self.assertEqual(get_resp["data"]["pending_nodes"][0]["runtime"], 4)
        self.assertEqual(get_resp["data"]["pending_nodes"][0]["target"], 2)

    def test_reconcile_worker_concurrency_grows_always_and_shrinks_only_when_idle(self):
        from app import scheduler

        inspector = MagicMock()
        inspector.stats.return_value = {
            "arltask_heavy@n1": {"pool": {"processes": [1, 2, 3, 4]}},  # target=2, busy -> defer shrink
            "arltask_light@n1": {"pool": {"processes": [1, 2, 3, 4]}},  # target=2, idle -> shrink
            "arlgithub@n1": {"pool": {"processes": [1]}},              # target=3 -> grow even if active
        }
        inspector.active.return_value = {
            "arltask_heavy@n1": [{"id": "running-job"}],
            "arltask_light@n1": [],
            "arlgithub@n1": [{"id": "gh-job"}],
        }
        fake_control = MagicMock()
        fake_control.inspect.return_value = inspector
        fake_celery_mod = SimpleNamespace(celery=SimpleNamespace(control=fake_control))

        cfg = {
            "celery_heavy_concurrency": 2,
            "celery_light_concurrency": 2,
            "osint_concurrency": 1,
            "github_concurrency": 3,
        }
        with patch.dict(sys.modules, {"app.celerytask": fake_celery_mod}), \
             patch("app.utils.performance_config.get_performance_config", return_value=cfg):
            adjusted = scheduler.reconcile_worker_concurrency()

        self.assertEqual(adjusted, 2)
        fake_control.pool_grow.assert_called_once_with(
            n=2, destination=["arlgithub@n1"], reply=True, timeout=1.5
        )
        fake_control.pool_shrink.assert_called_once_with(
            n=2, destination=["arltask_light@n1"], reply=True, timeout=1.5
        )


class Branch4TieredFaultToleranceTests(unittest.TestCase):
    """验证分支 4：critical vs non-critical 阶段容错、sync_summary 写入。"""

    def test_safe_phase_differentiates_critical_and_auxiliary_failures(self):
        from app.services.commonTask import CommonTask

        task = CommonTask("650000000000000000000001")
        updates = {}
        base_update = MagicMock()
        base_update.update_task_field.side_effect = lambda field, val: updates.__setitem__(field, val)

        with patch("app.services.commonTask.TaskHeartbeat"):
            # 非关键阶段异常被吸收，错误写入 error_msg 和 phase_errors
            with task.safe_phase("alt_dns", base_update, critical=False):
                raise RuntimeError("alt_dns resolver timeout")
            self.assertIn("alt_dns", updates["phase_errors"])
            self.assertIn("alt_dns resolver timeout", updates["error_msg"])

            # 关键阶段异常必须向外抛出，由上层转为 ERROR 终态
            with self.assertRaises(RuntimeError):
                with task.safe_phase("find_site", base_update, critical=True):
                    raise RuntimeError("find_site probe crashed")
            self.assertIn("find_site", updates["phase_errors"])

    def test_sync_asset_persists_sync_summary_with_new_and_update_breakdown(self):
        from app.services import syncAsset

        oid = ObjectId()
        task_col = InMemoryLeaseCollection()
        task_col.docs[oid] = {"_id": oid, "status": "done"}

        mock_sync = MagicMock()
        mock_sync.run.return_value = (
            {"site": ["https://a.example.com"]},
            {"site": 1, "domain": 2},
            {"site": ["https://old.example.com"]},
            {"site": 3},
        )
        with patch.object(syncAsset, "SyncAsset", return_value=mock_sync), \
             patch.object(syncAsset, "conn", return_value=task_col):
            syncAsset.sync_asset(str(oid), "scope-1", push_flag=False)

        saved = task_col.docs[oid]["sync_summary"]
        self.assertEqual(saved["total_new"], 3)
        self.assertEqual(saved["total_update"], 3)
        self.assertEqual(saved["new"], {"site": 1, "domain": 2})
        self.assertEqual(saved["update"], {"site": 3})

    def test_domain_fetch_fails_when_domain_brute_fails_without_fallback_results(self):
        from app.tasks.domain import DomainTask

        with patch("app.tasks.domain.get_scan_ports", return_value="80,443"):
            dt = DomainTask(
                base_domain="example.com",
                task_id="650000000000000000000002",
                options={
                    "domain_brute": True,
                    "arl_search": True,
                    "dns_query_plugin": False,
                    "alt_dns": False,
                },
            )
        dt.base_update_task = MagicMock()

        # Case 1: domain_brute 崩溃且 Fallback 未产出任何域名 -> 必须抛错阻断而非伪装 DONE
        with patch("app.services.commonTask.TaskHeartbeat"), \
             patch.object(dt, "domain_brute", side_effect=RuntimeError("massdns crash")), \
             patch.object(dt, "arl_search", return_value=None):
            with self.assertRaises(RuntimeError):
                dt.domain_fetch()
        self.assertIn("domain_brute", dt._phase_errors)

        # Case 2: domain_brute 崩溃但 arl_search 产出了域名 -> 允许继续后续阶段
        with patch("app.tasks.domain.get_scan_ports", return_value="80,443"):
            dt2 = DomainTask(
                base_domain="example.com",
                task_id="650000000000000000000003",
                options={
                    "domain_brute": True,
                    "arl_search": True,
                    "dns_query_plugin": False,
                    "alt_dns": False,
                },
            )
        dt2.base_update_task = MagicMock()

        def fake_arl():
            dt2.domain_info_list.append(SimpleNamespace(domain="sub.example.com"))

        with patch("app.services.commonTask.TaskHeartbeat"), \
             patch.object(dt2, "domain_brute", side_effect=RuntimeError("massdns crash")), \
             patch.object(dt2, "arl_search", side_effect=fake_arl), \
             patch.object(dt2, "recursive_domain_brute"):
            dt2.domain_fetch()
        self.assertIn("domain_brute", dt2._phase_errors)
        self.assertEqual(len(dt2.domain_info_list), 1)


class Branch5WorkerGenerationZombieTests(unittest.TestCase):
    """验证分支 5：Worker 启动代际登记与僵尸任务快速收敛（含完成竞态防护）。"""

    def test_worker_ready_and_task_prerun_record_boot_generation(self):
        from app import celerytask

        wi_col = InMemoryLeaseCollection()
        oid = ObjectId()
        task_col = InMemoryLeaseCollection()
        task_col.docs[oid] = {"_id": oid, "status": "running", "celery_id": "cid-1"}

        def fake_conn(name):
            if name == "worker_instances":
                return wi_col
            if name == "task":
                return task_col
            return InMemoryLeaseCollection()

        with patch.object(celerytask.utils, "conn_db", side_effect=fake_conn):
            celerytask.on_worker_ready(sender=SimpleNamespace(hostname="arltask_heavy@host1"))
            self.assertEqual(wi_col.docs["arltask_heavy@host1"]["boot_id"], celerytask.WORKER_BOOT_ID)

            fake_task = SimpleNamespace(request=SimpleNamespace(hostname="arltask_heavy@host1"))
            celerytask.setup_task_context(
                task_id="cid-1",
                task=fake_task,
                args=[{"data": {"task_id": str(oid)}}],
                kwargs={},
            )
            self.assertEqual(task_col.docs[oid]["worker_node"], "arltask_heavy@host1")
            self.assertEqual(task_col.docs[oid]["worker_boot_id"], celerytask.WORKER_BOOT_ID)

    def test_cleanup_zombie_tasks_fast_converges_rebooted_and_absent_workers_with_race_guard(self):
        from app import scheduler
        from app.modules import TaskStatus

        now = time.time()
        id_reboot = ObjectId()
        id_absent = ObjectId()
        id_raced_done = ObjectId()
        id_offline_fresh = ObjectId()

        task_col = InMemoryLeaseCollection()
        task_col.docs = {
            id_reboot: {
                "_id": id_reboot,
                "status": "domain_brute",
                "celery_id": "c-reboot",
                "worker_node": "arltask_heavy@h1",
                "worker_boot_id": "old-boot-id",
                "last_updated": int(now - 5),  # 心跳极新但节点已重启
            },
            id_absent: {
                "_id": id_absent,
                "status": "port_scan",
                "celery_id": "c-absent",
                "worker_node": "arltask_light@h1",
                "worker_boot_id": "same-boot-id",
                "last_updated": int(now - 30),  # 在线节点确认无此任务
            },
            id_raced_done: {
                "_id": id_raced_done,
                "status": "find_site",
                "celery_id": "c-done",
                "worker_node": "arltask_light@h1",
                "worker_boot_id": "same-boot-id",
                "last_updated": int(now - 30),
            },
            id_offline_fresh: {
                "_id": id_offline_fresh,
                "status": "domain_brute",
                "celery_id": "c-offline",
                "worker_node": "arltask_heavy@offline",
                "worker_boot_id": "offline-boot",
                "last_updated": int(now - 60),  # 节点失联但还在 30 分钟心跳窗内，应保留
            },
        }
        wi_col = InMemoryLeaseCollection()
        wi_col.docs = {
            "arltask_heavy@h1": {"_id": "arltask_heavy@h1", "worker_node": "arltask_heavy@h1", "boot_id": "new-boot-id"},
            "arltask_light@h1": {"_id": "arltask_light@h1", "worker_node": "arltask_light@h1", "boot_id": "same-boot-id"},
        }
        lease_col = InMemoryLeaseCollection()
        lease_col.docs = {
            "packet_slot_0": {"_id": "packet_slot_0", "state": "busy", "task_id": str(id_reboot)},
        }
        syslog_col = MagicMock()

        def fake_conn(name):
            if name == "task":
                return task_col
            if name == "worker_instances":
                return wi_col
            if name == "packet_phase_lease":
                return lease_col
            if name == "syslog":
                return syslog_col
            return InMemoryLeaseCollection()

        def fake_active():
            # 模拟 Inspect 期间 id_raced_done 刚好正常完成
            task_col.docs[id_raced_done]["status"] = TaskStatus.DONE
            return {
                "arltask_heavy@h1": [],
                "arltask_light@h1": [],
            }

        inspector = MagicMock()
        inspector.active.side_effect = fake_active
        fake_celery_mod = SimpleNamespace(celery=SimpleNamespace(control=MagicMock(inspect=lambda timeout=5.0: inspector)))

        with patch.object(scheduler, "conn", side_effect=fake_conn), \
             patch.dict(sys.modules, {"app.celerytask": fake_celery_mod}), \
             patch.object(scheduler.utils, "clean_task_tmp_files"):
            converged = scheduler.cleanup_zombie_tasks(window_seconds=1800)

        self.assertEqual(converged, 2)
        self.assertEqual(task_col.docs[id_reboot]["status"], TaskStatus.ERROR)
        self.assertEqual(task_col.docs[id_reboot]["end_reason"], "服务重启/异常中断")
        self.assertEqual(lease_col.docs["packet_slot_0"]["state"], "free")
        self.assertEqual(task_col.docs[id_absent]["status"], TaskStatus.ERROR)
        self.assertEqual(task_col.docs[id_raced_done]["status"], TaskStatus.DONE)
        self.assertEqual(task_col.docs[id_offline_fresh]["status"], "domain_brute")

    def test_run_task_restores_sigterm_handler_on_completion_and_early_skip(self):
        import signal
        from app import celerytask
        from app.modules import CeleryAction, TaskStatus

        sentinel = lambda signum, frame: None
        prev = signal.getsignal(signal.SIGTERM)
        signal.signal(signal.SIGTERM, sentinel)
        try:
            seen_inside_action = []
            oid_run = ObjectId()
            oid_stop = ObjectId()
            task_col = InMemoryLeaseCollection()
            task_col.docs[oid_run] = {"_id": oid_run, "status": "domain_brute"}
            task_col.docs[oid_stop] = {"_id": oid_stop, "status": TaskStatus.STOP}

            def fake_domain_exec(data):
                seen_inside_action.append(signal.getsignal(signal.SIGTERM))

            with patch.object(celerytask.utils, "conn_db", return_value=task_col), \
                 patch.object(celerytask, "domain_exec", side_effect=fake_domain_exec):
                celerytask.run_task({
                    "celery_action": CeleryAction.DOMAIN_EXEC_TASK,
                    "data": {"name": "t1", "target": "example.com", "task_id": str(oid_run)},
                })
                self.assertEqual(seen_inside_action, [celerytask.sigterm_handler])
                self.assertIs(signal.getsignal(signal.SIGTERM), sentinel)

                # Early return when task was already stopped must also restore SIGTERM
                celerytask.run_task({
                    "celery_action": CeleryAction.DOMAIN_EXEC_TASK,
                    "data": {"name": "t2", "target": "example.com", "task_id": str(oid_stop)},
                })
                self.assertIs(signal.getsignal(signal.SIGTERM), sentinel)
        finally:
            signal.signal(signal.SIGTERM, prev)


if __name__ == "__main__":
    unittest.main()
