import os
import sys
import unittest
from unittest.mock import MagicMock, patch
from bson import ObjectId

# Ensure backend and ARL-NPoC are in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
npoc_dir = os.path.join(backend_dir, 'ARL-NPoC')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if npoc_dir not in sys.path:
    sys.path.insert(0, npoc_dir)

# Bypass MongoDB connection and syslog flush timeouts during unit tests
import pymongo
pymongo.MongoClient = MagicMock()

import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999
app.config.get_system_config_value = lambda k, d: d
app.config.Config.AUTH = False

import app.utils
import app.utils.conn
_mock_conn_db = lambda *a, **k: MagicMock()
app.utils.conn.conn_db = _mock_conn_db
app.utils.conn_db = _mock_conn_db

from app.modules import (
    DEFAULT_ALIVE_PORTS,
    get_alive_ports,
    get_scan_ports,
    sanitize_ports,
    ScanPortType
)
from app.utils.dict_utils import is_builtin_dict, BUILTIN_ASSET_DICTS
from app.routes.dictionary import get_category
from app.routes.policy import AddARLPolicy, EditPolicy, ip_config_fields
from app.routes.task import ARLTask, add_task_fields, base_search_task_fields
from app.services.portScan import PortScan, normalize_host_discovery_mode, port_scan
from app.tasks.domain import DomainTask, ScanPort
from app.tasks.ip import IPTask


class TestAlivePortExternalization(unittest.TestCase):
    """
    第一性原理单元测试：验证存活探测端口字典外部化 (port_alive.txt)
    """

    def setUp(self):
        self.dicts_dir = os.path.join(backend_dir, 'app', 'dicts')
        self.alive_dict_path = os.path.join(self.dicts_dir, 'port_alive.txt')

    def test_alive_port_loads_and_sanitizes_correctly(self):
        """验证 port_alive.txt 正常存在时 get_alive_ports() 能正确加载并清洗"""
        self.assertTrue(os.path.exists(self.alive_dict_path), "port_alive.txt must exist")
        ports = get_alive_ports()
        self.assertIsInstance(ports, str)
        port_list = ports.split(',')
        self.assertEqual(len(port_list), 28)

        # 验证 47 个端口展开总数
        total_discrete_ports = sum(
            int(p.split('-')[1]) - int(p.split('-')[0]) + 1 if '-' in p else 1
            for p in port_list
        )
        self.assertEqual(total_discrete_ports, 47)

        # 验证 843 已被剔除
        self.assertNotIn("843", port_list)

        # 验证保留的基础端口
        for expected in ["21", "22", "25", "80", "443", "1433", "2222", "3306", "3389", "5000-5004", "8007-8011", "8080-8091", "8093", "8099", "8443", "9090"]:
            self.assertIn(expected, port_list)

        # 验证新增的 12 个现代高频端口
        for new_port in ["8000", "8001", "8888", "9000", "7001", "6443", "2375", "6379", "5432", "9200", "27017", "1521"]:
            self.assertIn(new_port, port_list)

    def test_ensure_builtin_dicts_evolution(self):
        """验证 ensure_builtin_dicts() 智能增量演进：剔除 843、补全新增 12 端口、保留用户个性化端口并按数值升序排序"""
        import tempfile
        from app.utils.arlupdate import ensure_builtin_dicts
        from app.config import Config

        with tempfile.TemporaryDirectory() as tmp_dir:
            dicts_dir = os.path.join(tmp_dir, 'dicts')
            os.makedirs(dicts_dir, exist_ok=True)
            alive_path = os.path.join(dicts_dir, 'port_alive.txt')
            # 存量文件：包含 843、缺少现代端口（如 8000、6443），包含用户自定义端口 10000 和 3000
            legacy_content = "80\n443\n843\n3000\n10000\n"
            with open(alive_path, 'w', encoding='utf-8') as f:
                f.write(legacy_content)

            with patch.object(Config, 'basedir', tmp_dir):
                ensure_builtin_dicts()

            with open(alive_path, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f if l.strip()]

            # 1. 验证 843 已被剔除
            self.assertNotIn("843", lines)
            # 2. 验证用户个性化端口被完整保留
            self.assertIn("3000", lines)
            self.assertIn("10000", lines)
            # 3. 验证 12 个新增现代基准端口全部被补齐
            for p in ['8000', '8001', '8888', '9000', '7001', '6443', '2375', '6379', '5432', '9200', '27017', '1521']:
                self.assertIn(p, lines)
            # 4. 验证严格按数值升序排序
            import re
            extracted_ports = [int(re.match(r'^(\d+)', l).group(1)) for l in lines]
            self.assertEqual(extracted_ports, sorted(extracted_ports))

    def test_ensure_builtin_dicts_empty_or_invalid_file_reseeding(self):
        """验证当 port_alive.txt 为 0 字节空文件或仅含注释时，自动补齐写入完整 47 个基准端口（而非仅新增的 12 个）"""
        import tempfile
        from app.utils.arlupdate import ensure_builtin_dicts
        from app.config import Config

        with tempfile.TemporaryDirectory() as tmp_dir:
            dicts_dir = os.path.join(tmp_dir, 'dicts')
            os.makedirs(dicts_dir, exist_ok=True)
            alive_path = os.path.join(dicts_dir, 'port_alive.txt')
            # 模拟 0 字节空文件
            with open(alive_path, 'w', encoding='utf-8') as f:
                f.write("")

            with patch.object(Config, 'basedir', tmp_dir):
                ensure_builtin_dicts()

            with open(alive_path, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f if l.strip()]

            # 必须补全为完整 28 行（47 个离散端口）
            self.assertEqual(len(lines), 28)
            self.assertNotIn("843", lines)
            for foundational in ["21", "22", "80", "443", "5000-5004", "8000"]:
                self.assertIn(foundational, lines)

    def test_ensure_builtin_dicts_inline_comments_and_ranges(self):
        """验证包含注释、/tcp 协议后缀、多端口单行及覆盖范围时的健壮处理"""
        import tempfile
        from app.utils.arlupdate import ensure_builtin_dicts
        from app.config import Config

        with tempfile.TemporaryDirectory() as tmp_dir:
            dicts_dir = os.path.join(tmp_dir, 'dicts')
            os.makedirs(dicts_dir, exist_ok=True)
            alive_path = os.path.join(dicts_dir, 'port_alive.txt')
            # 843 带注释与 /tcp 后缀；已存在 8000-8010 范围覆盖 8000 与 8001
            raw_content = (
                "# Custom Config\n"
                "80/tcp\n"
                "443, 843 # Flash socket\n"
                "8000-8010 # covers 8000 and 8001\n"
                "9999\n"
            )
            with open(alive_path, 'w', encoding='utf-8') as f:
                f.write(raw_content)

            with patch.object(Config, 'basedir', tmp_dir):
                ensure_builtin_dicts()

            with open(alive_path, 'r', encoding='utf-8') as f:
                lines = [l.strip() for l in f if l.strip()]

            # 843 必须被彻底剥离
            self.assertNotIn("843", lines)
            self.assertNotIn("843/tcp", lines)
            # 8000-8010 已覆盖 8000 与 8001，不得重复插入单独的 8000 或 8001
            self.assertIn("8000-8010", lines)
            self.assertNotIn("8000", lines)
            self.assertNotIn("8001", lines)
            # 自定义端口 9999 被保留
            self.assertIn("9999", lines)
            # 未覆盖的其余 10 个新增基准端口被补齐
            for p in ['8888', '9000', '7001', '6443', '2375', '6379', '5432', '9200', '27017', '1521']:
                self.assertIn(p, lines)

    def test_fallback_when_file_missing_or_empty(self):
        """验证临时改名模拟文件丢失或空内容时，get_alive_ports() 能够平滑回退到 DEFAULT_ALIVE_PORTS"""
        backup_path = self.alive_dict_path + ".bak_test"
        try:
            if os.path.exists(self.alive_dict_path):
                os.rename(self.alive_dict_path, backup_path)
            
            result = get_alive_ports()
            self.assertEqual(result, DEFAULT_ALIVE_PORTS)
        finally:
            if os.path.exists(backup_path):
                os.rename(backup_path, self.alive_dict_path)

        with patch("builtins.open", unittest.mock.mock_open(read_data="")):
            with patch("os.path.exists", return_value=True):
                self.assertEqual(get_alive_ports(), DEFAULT_ALIVE_PORTS)

        with patch("builtins.open", unittest.mock.mock_open(read_data="# only comments\n// nothing else\ninvalid_port\n")):
            with patch("os.path.exists", return_value=True):
                self.assertEqual(get_alive_ports(), DEFAULT_ALIVE_PORTS)

    def test_safety_clamp_when_exceeding_max_ports(self):
        """验证当端口数 > 60 时，防呆截断机制正常生效"""
        mock_data = "\n".join(str(1000 + i) for i in range(70))
        with patch("builtins.open", unittest.mock.mock_open(read_data=mock_data)):
            with patch("os.path.exists", return_value=True):
                res_60 = get_alive_ports(max_ports=60)
                ports_60 = res_60.split(",")
                self.assertEqual(len(ports_60), 60)
                self.assertEqual(ports_60[0], "1000")
                self.assertEqual(ports_60[-1], "1059")

                res_10 = get_alive_ports(max_ports=10)
                ports_10 = res_10.split(",")
                self.assertEqual(len(ports_10), 10)
                self.assertEqual(ports_10[-1], "1009")

    def test_portscan_alive_port_and_nmap_arguments(self):
        """验证 PortScan() 实例化的 self.alive_port 正确赋值，且大端口扫描（Top 100/Top 1000/All）下拼装的 nmap_arguments 包含正确的 -PE -PS 参数"""
        alive_val = get_alive_ports()

        # 默认初始化（端口 <= 60 且 != 1-65535 应走 -Pn）
        ps_default = PortScan(targets=["192.0.2.1"], ports="80,443")
        self.assertEqual(ps_default.alive_port, alive_val)
        self.assertIn("-Pn", ps_default.nmap_arguments)
        self.assertNotIn("-PE -PS", ps_default.nmap_arguments)

        # Top 100 端口（61..2000 展开端口）：单 IP 和 <=16 IP 在 auto 模式下走 -Pn；>16 IP 走 -PE -PS
        ports_top100 = get_scan_ports("top100")
        self.assertGreater(len(ports_top100.split(",")), 60)
        ps_top100_single = PortScan(targets=["192.0.2.1"], ports=ports_top100)
        self.assertEqual(ps_top100_single.alive_port, alive_val)
        self.assertIn("-Pn", ps_top100_single.nmap_arguments)
        self.assertNotIn("-PE -PS", ps_top100_single.nmap_arguments)
        self.assertEqual(ps_top100_single.max_retries, 2)

        ps_top100_16 = PortScan(targets=["192.0.2.0/28"], ports=ports_top100)
        self.assertEqual(ps_top100_16.target_ip_count, 16)
        self.assertIn("-Pn", ps_top100_16.nmap_arguments)

        ps_top100_17 = PortScan(targets=[f"192.0.2.{i}" for i in range(1, 18)], ports=ports_top100)
        self.assertIn(f"-PE -PS{alive_val}", ps_top100_17.nmap_arguments)
        self.assertNotIn("-Pn", ps_top100_17.nmap_arguments)
        self.assertEqual(ps_top100_17.max_retries, 2)

        # Top 1000 端口（61..2000 展开端口）
        ports_top1000 = get_scan_ports("top1000")
        self.assertGreater(len(ports_top1000.split(",")), 60)
        ps_top1000_single = PortScan(targets=["192.0.2.1"], ports=ports_top1000)
        self.assertIn("-Pn", ps_top1000_single.nmap_arguments)
        self.assertEqual(ps_top1000_single.max_retries, 2)

        ps_top1000_256 = PortScan(targets=["192.0.2.0/24"], ports=ports_top1000)
        self.assertIn(f"-PE -PS{alive_val}", ps_top1000_256.nmap_arguments)
        self.assertNotIn("-Pn", ps_top1000_256.nmap_arguments)

        # 全端口 1-65535：<=2 IP 在 auto 模式下走 -Pn；>2 IP 走 -PE -PS，且保留高并发防护参数
        ps_all_2 = PortScan(targets=["192.0.2.1", "192.0.2.2"], ports="1-65535")
        self.assertIn("-Pn", ps_all_2.nmap_arguments)
        self.assertNotIn("-PE -PS", ps_all_2.nmap_arguments)
        self.assertEqual(ps_all_2.max_host_group, 2)

        ps_all_3 = PortScan(targets=["192.0.2.1", "192.0.2.2", "192.0.2.3"], ports="1-65535")
        self.assertIn(f"-PE -PS{alive_val}", ps_all_3.nmap_arguments)
        self.assertNotIn("-Pn", ps_all_3.nmap_arguments)
        self.assertEqual(ps_all_3.max_host_group, 2)

        # 自定义 alive_port 字符串覆盖（超过阈值触发 -PE -PS 时生效）
        custom_alive = "80,443,8080"
        ps_custom = PortScan(targets=["192.0.2.0/24"], ports=ports_top100, alive_port=custom_alive)
        self.assertEqual(ps_custom.alive_port, custom_alive)
        self.assertIn(f"-PE -PS{custom_alive}", ps_custom.nmap_arguments)

        # 自定义 alive_port 列表覆盖
        custom_alive_list = [22, 80, 443]
        ps_custom_list = PortScan(targets=["192.0.2.0/24"], ports=ports_top100, alive_port=custom_alive_list)
        self.assertEqual(ps_custom_list.alive_port, "22,80,443")
        self.assertIn("-PE -PS22,80,443", ps_custom_list.nmap_arguments)

    def test_portscan_expanded_ranges_and_ip_formats(self):
        """验证区间端口展开计数与 CIDR/短横线 IP 范围扩展计数"""
        # 8000-8099 = 100 端口，1 个逗号项但展开后 > 60
        ps_range_1 = PortScan(targets=["192.0.2.1"], ports="8000-8099")
        self.assertEqual(ps_range_1.expanded_port_count, 100)
        self.assertIn("-Pn", ps_range_1.nmap_arguments)

        ps_range_dash = PortScan(targets=["192.0.2.1-20"], ports="8000-8099")
        self.assertEqual(ps_range_dash.target_ip_count, 20)
        self.assertIn("-PE -PS", ps_range_dash.nmap_arguments)

        # >2000 端口区间：2 IP 用 -Pn，3 IP 用 -PE -PS
        ps_large_2 = PortScan(targets=["192.0.2.1", "192.0.2.2"], ports="1-2500")
        self.assertIn("-Pn", ps_large_2.nmap_arguments)
        ps_large_3 = PortScan(targets=["192.0.2.1", "192.0.2.2", "192.0.2.3"], ports="1-2500")
        self.assertIn("-PE -PS", ps_large_3.nmap_arguments)

        # <=60 展开端口即使 /24 (256 IP) 也始终用 -Pn
        ps_small_cidr = PortScan(targets=["192.0.2.0/24"], ports="80,443,8000-8019")
        self.assertEqual(ps_small_cidr.expanded_port_count, 22)
        self.assertIn("-Pn", ps_small_cidr.nmap_arguments)
        self.assertNotIn("-PE -PS", ps_small_cidr.nmap_arguments)

    def test_portscan_host_discovery_mode_override_and_validation(self):
        """验证 skip/probe 手动覆盖与合法性校验"""
        ps_skip = PortScan(
            targets=["192.0.2.0/24"],
            ports="1-65535",
            host_discovery_mode="skip",
        )
        self.assertIn("-Pn", ps_skip.nmap_arguments)
        self.assertNotIn("-PE -PS", ps_skip.nmap_arguments)
        self.assertEqual(ps_skip.max_host_group, 2)

        ps_probe = PortScan(
            targets=["192.0.2.1"],
            ports="80,443",
            host_discovery_mode="probe",
        )
        self.assertIn("-PE -PS", ps_probe.nmap_arguments)
        self.assertNotIn("-Pn", ps_probe.nmap_arguments)

        self.assertEqual(normalize_host_discovery_mode(None), "auto")
        self.assertEqual(normalize_host_discovery_mode(""), "auto")
        self.assertEqual(normalize_host_discovery_mode("PROBE"), "probe")
        with self.assertRaises(ValueError):
            normalize_host_discovery_mode("invalid_mode", strict=True)

    def test_portscan_exclude_ports_subtracted_from_alive_ports(self):
        """验证启用 -PE -PS 时 exclude_ports 会从探活端口列表中剔除，全部排除时回退为 -PE"""
        ps_split = PortScan(
            targets=["192.0.2.1"],
            ports="80,443",
            alive_port="22,5000-5004,8080",
            exclude_ports="22,5002",
            host_discovery_mode="probe",
        )
        self.assertEqual(ps_split.effective_alive_port, "5000-5001,5003-5004,8080")
        self.assertIn("-PE -PS5000-5001,5003-5004,8080", ps_split.nmap_arguments)
        self.assertIn("--exclude-ports 22,5002", ps_split.nmap_arguments)

        ps_all_excluded = PortScan(
            targets=["192.0.2.1"],
            ports="80,443",
            alive_port="80,443",
            exclude_ports="80,443",
            host_discovery_mode="probe",
        )
        self.assertEqual(ps_all_excluded.effective_alive_port, "")
        self.assertIn(" -PE ", f" {ps_all_excluded.nmap_arguments} ")
        self.assertNotIn("-PS", ps_all_excluded.nmap_arguments)

    def test_portscan_run_logs_and_forwards_strategy(self):
        """验证 PortScan.run 记录 IP/端口计数与探测策略，以及任务/路由字段暴露"""
        self.assertIn("host_discovery_mode", ip_config_fields)
        self.assertIn("host_discovery_mode", add_task_fields)
        self.assertIn("options.host_discovery_mode", base_search_task_fields)

        fake_scanner = MagicMock()
        fake_scanner.all_hosts.return_value = []
        with patch("app.services.portScan.utils.not_in_black_ips", return_value=True), \
             patch("app.services.portScan.nmap.PortScanner", return_value=fake_scanner), \
             patch("app.services.portScan.acquire_packet_slot"), \
             patch("app.services.portScan.logger") as mock_logger:
            port_scan(targets=["192.0.2.1"], ports="80,443", host_discovery_mode="probe")
            mock_logger.info.assert_called()
            logged_msg = mock_logger.info.call_args[0][0]
            self.assertIn("ips=1", logged_msg)
            self.assertIn("expanded_ports=2", logged_msg)
            self.assertIn("discovery_mode=probe", logged_msg)
            self.assertIn("strategy=-PE -PS", logged_msg)

    def test_domain_and_ip_tasks_forward_host_discovery_mode(self):
        """验证 DomainTask / ScanPort / IPTask 正确透传和兜底 host_discovery_mode"""
        sp_default = ScanPort(domain_info_list=[], option=None)
        self.assertEqual(sp_default.option["host_discovery_mode"], "auto")

        with patch("app.tasks.domain.get_scan_ports", return_value="80,443"):
            dt_probe = DomainTask(
                base_domain="example.com",
                task_id="650000000000000000000010",
                options={"host_discovery_mode": "probe"},
            )
            self.assertEqual(dt_probe.scan_port_option["host_discovery_mode"], "probe")

            dt_none = DomainTask(
                base_domain="example.com",
                task_id="650000000000000000000011",
                options={"host_discovery_mode": None},
            )
            self.assertEqual(dt_none.scan_port_option["host_discovery_mode"], "auto")

        ip_task = IPTask.__new__(IPTask)
        ip_task.ip_target = "192.0.2.1"
        ip_task.task_id = "650000000000000000000012"
        ip_task.task_tag = "task"
        ip_task.ip_info_list = []
        ip_task.ip_set = set()
        ip_task.options = {"port_scan_type": "test", "host_discovery_mode": "skip"}
        with patch("app.tasks.ip.get_scan_ports", return_value="80,443"), \
             patch("app.tasks.ip.services.port_scan", return_value=[]) as mock_port_scan:
            ip_task.port_scan()
            mock_port_scan.assert_called_once()
            self.assertEqual(mock_port_scan.call_args.kwargs["host_discovery_mode"], "skip")

    def test_routes_validate_and_normalize_host_discovery_mode(self):
        """验证 Task 与 Policy 接口的 host_discovery_mode 校验与默认值归一化"""
        task_res = ARLTask()
        with patch.object(task_res, "parse_args", return_value={
            "name": "t1", "target": "192.0.2.1", "host_discovery_mode": "bad"
        }), patch("app.routes.task.submit_task_task") as mock_submit:
            resp = task_res.post()
            self.assertNotEqual(resp.get("code"), 200)
            mock_submit.assert_not_called()

        with patch.object(task_res, "parse_args", return_value={
            "name": "t2", "target": "192.0.2.1", "host_discovery_mode": None
        }), patch("app.routes.task.submit_task_task", return_value=[{"task_id": "1"}]) as mock_submit:
            resp = task_res.post()
            self.assertEqual(resp.get("code"), 200)
            self.assertEqual(mock_submit.call_args.kwargs["options"]["host_discovery_mode"], "auto")

        policy_col = MagicMock()
        policy_col.insert_one.side_effect = lambda doc: doc.__setitem__("_id", ObjectId())
        add_res = AddARLPolicy()
        with patch("app.routes.policy.utils.conn_db", return_value=policy_col):
            with patch.object(add_res, "parse_args", return_value={
                "name": "p_bad",
                "desc": "",
                "policy": {"ip_config": {"port_scan_type": "test", "host_discovery_mode": "invalid"}},
            }):
                resp = add_res.post()
                self.assertNotEqual(resp.get("code"), 200)
                policy_col.insert_one.assert_not_called()

            with patch.object(add_res, "parse_args", return_value={
                "name": "p_ok",
                "desc": "",
                "policy": {"ip_config": {"port_scan_type": "test"}},
            }):
                resp = add_res.post()
                self.assertEqual(resp.get("code"), 200)
                inserted = policy_col.insert_one.call_args[0][0]
                self.assertEqual(inserted["policy"]["ip_config"]["host_discovery_mode"], "auto")

        oid = ObjectId()
        legacy_doc = {
            "_id": oid,
            "name": "legacy",
            "desc": "",
            "policy": {
                "domain_config": {},
                "ip_config": {"port_scan": True, "port_scan_type": "top100"},
                "site_config": {},
                "poc_config": [],
                "brute_config": [],
            },
        }
        edit_res = EditPolicy()
        policy_col.find_one.return_value = legacy_doc
        with patch("app.routes.policy.utils.conn_db", return_value=policy_col):
            with patch.object(edit_res, "parse_args", return_value={
                "policy_id": str(oid),
                "policy_data": {"policy": {"ip_config": {"host_discovery_mode": "wrong"}}},
            }):
                resp = edit_res.post()
                self.assertNotEqual(resp.get("code"), 200)
                policy_col.find_one_and_replace.assert_not_called()

            policy_col.find_one.return_value = {
                **legacy_doc,
                "policy": {**legacy_doc["policy"], "ip_config": {"port_scan": True, "port_scan_type": "top100"}},
            }
            with patch.object(edit_res, "parse_args", return_value={
                "policy_id": str(oid),
                "policy_data": {"policy": {"ip_config": {"host_discovery_mode": "skip"}}},
            }):
                resp = edit_res.post()
                self.assertEqual(resp.get("code"), 200)
                replaced = policy_col.find_one_and_replace.call_args[0][1]
                self.assertEqual(replaced["policy"]["ip_config"]["host_discovery_mode"], "skip")

    def test_builtin_dict_and_category(self):
        """验证 /api/dictionary/list 与 dict_utils 中的 is_builtin_dict('port_alive.txt') 返回 True 且分类为 '🔌 端口扫描策略'"""
        self.assertIn('port_alive.txt', BUILTIN_ASSET_DICTS)
        self.assertTrue(is_builtin_dict('port_alive.txt', is_brute=False))
        self.assertFalse(is_builtin_dict('port_alive.txt', is_brute=True))
        
        category = get_category('port_alive.txt')
        self.assertEqual(category, '🔌 端口扫描策略 (Port Config)')

        alive_via_scan = get_scan_ports("port_alive.txt")
        self.assertTrue(bool(alive_via_scan))
        self.assertEqual(alive_via_scan, get_alive_ports())


if __name__ == '__main__':
    unittest.main()
