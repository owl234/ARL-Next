import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure backend and ARL-NPoC are in sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
npoc_dir = os.path.join(backend_dir, 'ARL-NPoC')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if npoc_dir not in sys.path:
    sys.path.insert(0, npoc_dir)

# Bypass MongoDB connection during tests
import app.utils.conn
app.utils.conn.conn_db = lambda *a, **k: MagicMock()

import app.config
app.config.get_system_config_value = lambda k, d: d

from app.modules import (
    DEFAULT_ALIVE_PORTS,
    get_alive_ports,
    get_scan_ports,
    sanitize_ports,
    ScanPortType
)
from app.utils.dict_utils import is_builtin_dict, BUILTIN_ASSET_DICTS
from app.routes.dictionary import get_category
from app.services.portScan import PortScan, port_scan


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
        ps_default = PortScan(targets=["192.168.1.1"], ports="80,443")
        self.assertEqual(ps_default.alive_port, alive_val)
        self.assertIn("-Pn", ps_default.nmap_arguments)
        self.assertNotIn("-PE -PS", ps_default.nmap_arguments)

        # Top 100 端口（> 60 个端口）
        ports_top100 = get_scan_ports("top100")
        self.assertGreater(len(ports_top100.split(",")), 60)
        ps_top100 = PortScan(targets=["192.168.1.1"], ports=ports_top100)
        self.assertEqual(ps_top100.alive_port, alive_val)
        self.assertIn(f"-PE -PS{alive_val}", ps_top100.nmap_arguments)
        self.assertNotIn("-Pn", ps_top100.nmap_arguments)
        self.assertEqual(ps_top100.max_retries, 2)

        # Top 1000 端口（> 60 个端口）
        ports_top1000 = get_scan_ports("top1000")
        self.assertGreater(len(ports_top1000.split(",")), 60)
        ps_top1000 = PortScan(targets=["192.168.1.1"], ports=ports_top1000)
        self.assertIn(f"-PE -PS{alive_val}", ps_top1000.nmap_arguments)
        self.assertNotIn("-Pn", ps_top1000.nmap_arguments)

        # 全端口 1-65535
        ps_all = PortScan(targets=["192.168.1.1"], ports="1-65535")
        self.assertIn(f"-PE -PS{alive_val}", ps_all.nmap_arguments)
        self.assertNotIn("-Pn", ps_all.nmap_arguments)
        self.assertEqual(ps_all.max_host_group, 2)

        # 自定义 alive_port 字符串覆盖
        custom_alive = "80,443,8080"
        ps_custom = PortScan(targets=["192.168.1.1"], ports=ports_top100, alive_port=custom_alive)
        self.assertEqual(ps_custom.alive_port, custom_alive)
        self.assertIn(f"-PE -PS{custom_alive}", ps_custom.nmap_arguments)

        # 自定义 alive_port 列表覆盖
        custom_alive_list = [22, 80, 443]
        ps_custom_list = PortScan(targets=["192.168.1.1"], ports=ports_top100, alive_port=custom_alive_list)
        self.assertEqual(ps_custom_list.alive_port, "22,80,443")
        self.assertIn("-PE -PS22,80,443", ps_custom_list.nmap_arguments)

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
