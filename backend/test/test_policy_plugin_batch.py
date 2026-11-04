import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure backend and xing paths
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
xing_dir = os.path.abspath(os.path.join(backend_dir, 'ARL-NPoC'))
if xing_dir not in sys.path:
    sys.path.insert(0, xing_dir)
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Bypass mongo lookups during config initialization
import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999
app.config._config_cache["version"] = 1
app.config._read_config_version = lambda: 1

from app.routes.policy import _update_plugin_config
from app import utils


class TestPolicyPluginBatch(unittest.TestCase):
    def setUp(self):
        self.mock_db = MagicMock()
        self.mock_poc_col = MagicMock()
        self.mock_db.side_effect = lambda col: self.mock_poc_col if col == 'poc' else MagicMock()

    def test_tc01_empty_and_invalid_inputs(self):
        """TC-01: 空输入与非列表数据安全降级为 []"""
        with patch.object(utils, 'conn_db', self.mock_db):
            self.assertEqual(_update_plugin_config([]), [])
            self.assertEqual(_update_plugin_config(None), [])
            self.assertEqual(_update_plugin_config("invalid"), [])
            self.assertEqual(_update_plugin_config({}), [])
            # 无数据库调用
            self.mock_poc_col.find.assert_not_called()

    def test_tc02_normal_plugins_batch_query(self):
        """TC-02: 正常插件列表通过单个 $in 批量查询组装结果"""
        mock_docs = [
            {"plugin_name": "poc_apache_struts2", "vul_name": "Apache Struts2 S2-045 RCE"},
            {"plugin_name": "poc_log4j2_rce", "vul_name": "Apache Log4j2 JNDI RCE"}
        ]
        self.mock_poc_col.find.return_value = mock_docs

        input_config = [
            {"plugin_name": "poc_apache_struts2", "enable": True},
            {"plugin_name": "poc_log4j2_rce", "enable": False}
        ]

        with patch.object(utils, 'conn_db', self.mock_db):
            result = _update_plugin_config(input_config)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0], {
            "plugin_name": "poc_apache_struts2",
            "vul_name": "Apache Struts2 S2-045 RCE",
            "enable": True
        })
        self.assertEqual(result[1], {
            "plugin_name": "poc_log4j2_rce",
            "vul_name": "Apache Log4j2 JNDI RCE",
            "enable": False
        })

        # 验证仅调用一次 find，使用了 $in 与投影
        self.mock_poc_col.find.assert_called_once_with(
            {"plugin_name": {"$in": ["poc_apache_struts2", "poc_log4j2_rce"]}},
            {"plugin_name": 1, "vul_name": 1}
        )

    def test_tc03_deduplication_keeps_first_occurrence(self):
        """TC-03: 重复插件去重，严格保留首个配置与原始顺序"""
        mock_docs = [
            {"plugin_name": "poc_shiro", "vul_name": "Shiro RememberMe RCE"},
            {"plugin_name": "poc_fastjson", "vul_name": "Fastjson Deserialization"}
        ]
        self.mock_poc_col.find.return_value = mock_docs

        input_config = [
            {"plugin_name": "poc_shiro", "enable": True},
            {"plugin_name": "poc_fastjson", "enable": True},
            {"plugin_name": "poc_shiro", "enable": False},  # 重复项被去重
            {"plugin_name": "poc_fastjson", "enable": False}  # 重复项被去重
        ]

        with patch.object(utils, 'conn_db', self.mock_db):
            result = _update_plugin_config(input_config)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["plugin_name"], "poc_shiro")
        self.assertEqual(result[0]["enable"], True)
        self.assertEqual(result[1]["plugin_name"], "poc_fastjson")
        self.assertEqual(result[1]["enable"], True)

        # 批量查询中只包含 2 个唯一名字
        call_args = self.mock_poc_col.find.call_args[0]
        self.assertEqual(call_args[0]["plugin_name"]["$in"], ["poc_shiro", "poc_fastjson"])

    def test_tc04_missing_plugin_error_message(self):
        """TC-04: 遇到库中不存在的插件，精准返回首个缺失插件的错误提示"""
        mock_docs = [
            {"plugin_name": "poc_exist_1", "vul_name": "Existing Vul 1"}
        ]
        self.mock_poc_col.find.return_value = mock_docs

        input_config = [
            {"plugin_name": "poc_exist_1", "enable": True},
            {"plugin_name": "poc_not_found_xyz", "enable": True},
            {"plugin_name": "poc_not_found_abc", "enable": True}
        ]

        with patch.object(utils, 'conn_db', self.mock_db):
            result = _update_plugin_config(input_config)

        # 匹配首个未找到插件的错误提示字符串
        self.assertIsInstance(result, str)
        self.assertEqual(result, "没有找到 poc_not_found_xyz 插件")

    def test_tc05_corrupt_items_tolerance(self):
        """TC-05: 容忍脏数据（如非字典、None、缺失 plugin_name、空白名称、缺失 enable 等）"""
        mock_docs = [
            {"plugin_name": "poc_valid", "vul_name": "Valid Vul"}
        ]
        self.mock_poc_col.find.return_value = mock_docs

        input_config = [
            None,
            "corrupt string",
            {"enable": True},  # 缺少 plugin_name 应忽略
            {"plugin_name": None, "enable": True},  # plugin_name 为 None 应忽略
            {"plugin_name": "   ", "enable": True},  # 纯空白 plugin_name 应忽略
            {"plugin_name": "poc_valid"},  # 缺少 enable 应忽略
            {"plugin_name": "poc_valid", "enable": None},  # enable 为 None 应忽略
            {"plugin_name": "poc_valid", "enable": True}
        ]

        with patch.object(utils, 'conn_db', self.mock_db):
            result = _update_plugin_config(input_config)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["plugin_name"], "poc_valid")
        self.assertEqual(result[0]["enable"], True)

    def test_tc07_duplicate_db_records_preserve_first(self):
        """TC-07: 当 DB 中存在同名重复插件时，保持与 find_one 一致的保首策略"""
        mock_docs = [
            {"plugin_name": "poc_dup", "vul_name": "First Vul Definition"},
            {"plugin_name": "poc_dup", "vul_name": "Overwriting Vul Definition"}
        ]
        self.mock_poc_col.find.return_value = mock_docs

        input_config = [
            {"plugin_name": "poc_dup", "enable": True}
        ]

        with patch.object(utils, 'conn_db', self.mock_db):
            result = _update_plugin_config(input_config)

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["plugin_name"], "poc_dup")
        self.assertEqual(result[0]["vul_name"], "First Vul Definition")

    def test_tc06_high_concurrency_scale_simulation(self):
        """TC-06: 12,000 个海量 PoC 配置批量聚合验证与耗时断言"""
        import time

        total_pocs = 12000
        input_config = [
            {"plugin_name": f"poc_scale_{i:05d}", "enable": (i % 2 == 0)}
            for i in range(total_pocs)
        ]

        # 模拟分块查询返回生成器
        def mock_find(query, projection):
            names = query.get("plugin_name", {}).get("$in", [])
            return [{"plugin_name": n, "vul_name": f"Vul {n}"} for n in names]

        self.mock_poc_col.find.side_effect = mock_find

        start_time = time.perf_counter()
        with patch.object(utils, 'conn_db', self.mock_db):
            result = _update_plugin_config(input_config)
        duration = time.perf_counter() - start_time

        # 验证结果完整性
        self.assertEqual(len(result), total_pocs)
        self.assertEqual(result[0]["plugin_name"], "poc_scale_00000")
        self.assertEqual(result[0]["vul_name"], "Vul poc_scale_00000")
        self.assertEqual(result[0]["enable"], True)
        self.assertEqual(result[1]["enable"], False)

        # 验证分块批次：12000 个按照 chunk_size=5000 分为 3 批 (5000 + 5000 + 2000)
        self.assertEqual(self.mock_poc_col.find.call_count, 3)

        # 验证性能耗时远小于 1 秒（完全消灭 120s 超时风险）
        self.assertLess(duration, 0.5, f"12,000 PoC processing took {duration:.4f}s, exceeded 0.5s limit")


if __name__ == '__main__':
    unittest.main()
