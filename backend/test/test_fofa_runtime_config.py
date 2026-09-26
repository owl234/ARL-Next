import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import dns_query
from app.services import fofaClient


class _FakeFofaClient:
    page_sizes = []

    def __init__(self, key, page_size, max_page, fields):
        self.page_sizes.append((page_size, max_page, fields))

    def search(self, query):
        yield []


class TestFofaRuntimeConfig(unittest.TestCase):
    def test_query_uses_dynamic_pagination_values_at_call_time(self):
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

        self.assertEqual(_FakeFofaClient.page_sizes[-2:], [(37, 2, "host,ip,port"), (11, 1, "host,ip,port")])

    def test_plugin_config_is_not_mutated_when_reading_enable(self):
        config = {"fofa": {"enable": False}}
        plugin = SimpleNamespace(source_name="fofa", query=lambda target: [target])
        with patch.object(dns_query.Config, "QUERY_PLUGIN_CONFIG", config, create=True):
            source, result = dns_query.run_plugin(plugin, "example.com")

        self.assertEqual((source, result), ("fofa", []))
        self.assertEqual(config, {"fofa": {"enable": False}})


if __name__ == "__main__":
    unittest.main()
