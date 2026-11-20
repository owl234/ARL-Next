"""Issue #97：关闭域名爆破后，启动日志不应输出爆破字典，根域名来源不应标记为 domain_brute。"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)


ISSUE_97_OPTIONS = {
    "policy_name": "Web子域名信息收集",
    "domain_brute": False,
    "domain_brute_type": "domain_2w.txt",
    "alt_dns": False,
    "alt_dns_dict": "altdnsdict.txt",
    "dns_query_plugin": True,
    "port_scan": False,
    "port_scan_type": "port_all.txt",
    "port_custom": "80,443",
    "host_timeout_type": "default",
    "host_discovery_mode": "auto",
    "exclude_ports": "8080",
    "file_leak": False,
    "file_leak_dict": "file_top_200.txt",
    "skip_scan_cdn_ip": True,
}


class OptionSummaryTests(unittest.TestCase):
    def test_disabled_parent_switch_hides_dependent_options(self):
        from app.celerytask import build_task_options_summary

        summary = build_task_options_summary(ISSUE_97_OPTIONS)
        joined = ", ".join(summary)
        for hidden in ("domain_brute_type", "alt_dns_dict", "port_scan_type", "port_custom",
                       "host_timeout_type", "host_discovery_mode", "exclude_ports", "file_leak_dict"):
            self.assertNotIn(hidden, joined)
        self.assertIn("policy_name: Web子域名信息收集", summary)
        self.assertIn("已开启 dns_query_plugin", summary)
        self.assertIn("已开启 skip_scan_cdn_ip", summary)

    def test_enabled_parent_switch_keeps_dependent_options(self):
        from app.celerytask import build_task_options_summary

        opts = dict(ISSUE_97_OPTIONS, domain_brute=True, alt_dns=True, port_scan=True, file_leak=True)
        summary = build_task_options_summary(opts)
        for expected in ("domain_brute_type: domain_2w.txt", "alt_dns_dict: altdnsdict.txt",
                         "port_scan_type: port_all.txt", "host_discovery_mode: auto",
                         "file_leak_dict: file_top_200.txt"):
            self.assertIn(expected, summary)

    def test_non_dict_options_return_empty(self):
        from app.celerytask import build_task_options_summary

        self.assertEqual(build_task_options_summary(None), [])
        self.assertEqual(build_task_options_summary({}), [])


class RootDomainSourceTests(unittest.TestCase):
    def _make_task(self, options):
        from app.tasks.domain import DomainTask

        with patch("app.tasks.domain.get_scan_ports", return_value="80,443"):
            dt = DomainTask(base_domain="example.com", task_id="650000000000000000000097", options=options)
        dt.base_update_task = MagicMock()
        dt.update_task_field = MagicMock()
        return dt

    def test_root_domain_saved_as_target_when_domain_brute_disabled(self):
        from app import modules
        from app.modules import CollectSource

        dt = self._make_task({"domain_brute": False, "dns_query_plugin": False, "arl_search": False, "alt_dns": False})
        info = modules.DomainInfo(domain="example.com", type="A", record=["192.0.2.1"], ips=["192.0.2.1"])
        with patch.object(dt, "build_single_domain_info", return_value=info), \
             patch.object(dt, "save_domain_info_list") as save_mock, \
             patch.object(dt, "domain_brute") as brute_mock, \
             patch.object(dt, "recursive_domain_brute") as recursive_mock:
            dt.domain_fetch()

        brute_mock.assert_not_called()
        recursive_mock.assert_not_called()
        save_mock.assert_called_once()
        self.assertEqual(save_mock.call_args.kwargs.get("source"), CollectSource.TARGET)
        self.assertEqual(CollectSource.TARGET, "target")


if __name__ == "__main__":
    unittest.main()
