import os
import sys

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Bypass mongo lookups during unit tests
import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999

import unittest
from types import SimpleNamespace
from unittest.mock import patch
import concurrent.futures

from app.services import dns_query
from app.services import fofaClient


class _FakeFofaClient:
    calls = []

    def __init__(self, key, page_size, max_page, fields):
        self.calls.append((key, page_size, max_page, fields))

    def search(self, query):
        yield []


class TestFofaRuntimeConfig(unittest.TestCase):
    def setUp(self):
        _FakeFofaClient.calls.clear()
        app.config._config_cache["data"] = {}
        app.config._config_cache["last_update"] = 9999999999

    def test_tc01_query_uses_dynamic_pagination_values_at_call_time(self):
        """TC-01: FOFA 分页配置运行时动态生效，不受导入期冻结影响"""
        config = SimpleNamespace(
            FOFA_KEY="fixture-key",
            FOFA_URL="https://fofa.example",
            FOFA_PAGE_SIZE=37,
            FOFA_MAX_PAGE=2,
        )
        with patch.object(fofaClient, "Config", config), patch.object(
            fofaClient, "FofaClient", _FakeFofaClient
        ):
            fofaClient.fofa_query('domain="example.com"')
            config.FOFA_PAGE_SIZE = 11
            config.FOFA_MAX_PAGE = 1
            fofaClient.fofa_query('domain="example.com"')

        self.assertEqual(len(_FakeFofaClient.calls), 2)
        self.assertEqual(_FakeFofaClient.calls[0], ("fixture-key", 37, 2, "host,ip,port"))
        self.assertEqual(_FakeFofaClient.calls[1], ("fixture-key", 11, 1, "host,ip,port"))

    def test_tc02_query_explicit_parameters_take_precedence(self):
        """TC-02: 显式传参优先级高于 Config 动态配置默认值"""
        config = SimpleNamespace(
            FOFA_KEY="fixture-key",
            FOFA_URL="https://fofa.example",
            FOFA_PAGE_SIZE=999,
            FOFA_MAX_PAGE=50,
        )
        with patch.object(fofaClient, "Config", config), patch.object(
            fofaClient, "FofaClient", _FakeFofaClient
        ):
            # 显式传入 page_size 与 max_page
            fofaClient.fofa_query('domain="example.com"', page_size=25, max_page=3)

        self.assertEqual(len(_FakeFofaClient.calls), 1)
        self.assertEqual(_FakeFofaClient.calls[0], ("fixture-key", 25, 3, "host,ip,port"))

    def test_tc03_query_mock_and_unconfigured_branches(self):
        """TC-03: 特殊 Mock 查询分支与未配置 FOFA_KEY 分支正常兼容"""
        config = SimpleNamespace(
            FOFA_KEY="",
            FOFA_URL="https://fofa.example",
            FOFA_PAGE_SIZE=100,
            FOFA_MAX_PAGE=5,
        )
        with patch.object(fofaClient, "Config", config):
            # 未配置 KEY
            ret = fofaClient.fofa_query('domain="example.com"')
            self.assertIn("please set fofa key", ret)

            # test_mock 查询
            ret_mock_ip = fofaClient.fofa_query("test_mock", fields="ip")
            self.assertEqual(ret_mock_ip, ["127.0.0.1"])

            ret_mock_all = fofaClient.fofa_query("test_mock")
            self.assertEqual(ret_mock_all, [["localhost", "127.0.0.1", 80]])

            # FOFA_KEY == 'mock'
            config.FOFA_KEY = "mock"
            ret_key_mock = fofaClient.fofa_query('domain="test.com"')
            self.assertEqual(ret_key_mock, [["localhost", "127.0.0.1", 80]])

    def test_tc04_plugin_repeated_runs_with_enable_false_no_pollution(self):
        """TC-04: 插件配置为 enable=False 时，多轮连续调用始终生效且字典不被污染"""
        config = {"fofa": {"enable": False, "key": "test-key"}}
        plugin = SimpleNamespace(
            source_name="fofa",
            query=lambda target: [f"found.{target}"],
            init_key=lambda **kwargs: None
        )
        with patch.object(dns_query.Config, "QUERY_PLUGIN_CONFIG", config, create=True):
            for i in range(5):
                source, result = dns_query.run_plugin(plugin, f"target{i}.com")
                self.assertEqual((source, result), ("fofa", []))

        # 断言外部共享字典依然完整保留 enable=False 与 key
        self.assertEqual(config, {"fofa": {"enable": False, "key": "test-key"}})

    def test_tc05_plugin_repeated_runs_with_credentials_preserve_all_keys(self):
        """TC-05: 插件配置包含凭据且 enable=True 时，多轮连续调用不丢失任何键值"""
        config = {"fofa": {"enable": True, "key": "secret_key_123", "email": "admin@arl.local"}}
        received_kwargs = []

        def fake_init_key(**kwargs):
            received_kwargs.append(kwargs)

        plugin = SimpleNamespace(
            source_name="fofa",
            query=lambda target: [f"sub.{target}"],
            init_key=fake_init_key
        )

        with patch.object(dns_query.Config, "QUERY_PLUGIN_CONFIG", config, create=True):
            for i in range(3):
                source, result = dns_query.run_plugin(plugin, "example.com")
                self.assertEqual(source, "fofa")
                self.assertEqual(result, ["sub.example.com"])

        # 每次 init_key 收到的参数都不应包含 enable（因为被 pop 消费），但必须包含 key 与 email
        self.assertEqual(len(received_kwargs), 3)
        for kw in received_kwargs:
            self.assertEqual(kw, {"key": "secret_key_123", "email": "admin@arl.local"})

        # 核心断言：原始共享 Config.QUERY_PLUGIN_CONFIG 中的 enable 与其他参数完全未被篡改
        self.assertEqual(config["fofa"], {"enable": True, "key": "secret_key_123", "email": "admin@arl.local"})

    def test_tc06_plugin_concurrent_runs_thread_safety(self):
        """TC-06: 多线程并发执行 run_plugin 时，共享配置对象无竞态污染与异常"""
        config = {"fofa": {"enable": True, "token": "thread-safe-token"}}
        plugin = SimpleNamespace(
            source_name="fofa",
            query=lambda target: [f"concurrent.{target}"],
            init_key=lambda **kwargs: None
        )

        def worker(idx):
            return dns_query.run_plugin(plugin, f"concurrent{idx}.com")

        with patch.object(dns_query.Config, "QUERY_PLUGIN_CONFIG", config, create=True):
            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = [executor.submit(worker, i) for i in range(20)]
                results = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(results), 20)
        for source, res in results:
            self.assertEqual(source, "fofa")
            self.assertTrue(res[0].startswith("concurrent."))

        # 原始配置依然完整无缺
        self.assertEqual(config["fofa"], {"enable": True, "token": "thread-safe-token"})

    def test_tc07_plugin_invalid_and_empty_config_handling(self):
        """TC-07: 插件配置异常结构（非字典、None、空字典）容错与防御降级"""
        plugin = SimpleNamespace(
            source_name="fofa",
            query=lambda target: [f"ok.{target}"],
            init_key=lambda **kwargs: None
        )

        # 1. 配置为非字典（如字符串）
        config_invalid_type = {"fofa": "invalid_string_config"}
        with patch.object(dns_query.Config, "QUERY_PLUGIN_CONFIG", config_invalid_type, create=True):
            source, result = dns_query.run_plugin(plugin, "example.com")
            self.assertEqual((source, result), ("fofa", []))

        # 2. 配置为空字典
        config_empty = {"fofa": {}}
        with patch.object(dns_query.Config, "QUERY_PLUGIN_CONFIG", config_empty, create=True):
            source, result = dns_query.run_plugin(plugin, "example.com")
            self.assertEqual((source, result), ("fofa", ["ok.example.com"]))

        # 3. 插件不在配置中
        config_missing = {}
        with patch.object(dns_query.Config, "QUERY_PLUGIN_CONFIG", config_missing, create=True):
            source, result = dns_query.run_plugin(plugin, "example.com")
            self.assertEqual((source, result), ("fofa", ["ok.example.com"]))


if __name__ == "__main__":
    unittest.main()
