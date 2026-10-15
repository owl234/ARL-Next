#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""离线验证 WIH 内置规则，不启动应用或访问网络。

运行：python3 -m unittest discover -s backend/test -p test_wih_builtin_rules.py -v
"""

import importlib.util
from pathlib import Path
import re
import tempfile
import unittest
from unittest import mock


BACKEND = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "wih_rule_engine_under_test", BACKEND / "app/services/wih/rule_engine.py"
)
rule_engine = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(rule_engine)
EXTRA_RULES = ("ip", "path", "domain_url", "ip_url")
SAMPLE = '''fetch("https://api.example.com/v1/users");
axios.get("/api/admin"); fetch("http://192.0.2.1:8080/api/status");'''
EXPECTED = {
    "ip": "192.0.2.1",
    "path": "/api/admin",
    "domain_url": "https://api.example.com/v1/users",
    "ip_url": "http://192.0.2.1:8080/api/status",
}


class TestWihBuiltinRules(unittest.TestCase):
    def make_engine(self, config):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "rules.yml"
        path.write_text(config, encoding="utf-8")
        return rule_engine.WihRuleEngine(str(path))

    def engine_for(self, *ids, enabled=True, extra=""):
        config = "rules:\n" + "".join(
            f"  - id: {rule_id}\n    enabled: {str(enabled).lower()}\n"
            for rule_id in ids
        )
        return self.make_engine(config + extra)

    def test_enabling_each_builtin_without_pattern_extracts_results(self):
        for rule_id, content in EXPECTED.items():
            with self.subTest(rule_id=rule_id):
                self.assertEqual(
                    self.engine_for(rule_id).extract_from_text(SAMPLE), [(rule_id, content)]
                )

    def test_disabled_rules_do_not_extract(self):
        engine = self.engine_for(*EXTRA_RULES, enabled=False)
        self.assertEqual(engine.extract_from_text(SAMPLE), [])

    def test_default_configuration_keeps_optional_rules_disabled(self):
        engine = rule_engine.WihRuleEngine(str(BACKEND / "app/dicts/wih_rules.yml"))
        self.assertFalse(set(EXTRA_RULES) & {rule["id"] for rule in engine.rules})
        matches = engine.extract_from_text(SAMPLE)
        self.assertIn(("domain", "api.example.com"), matches)
        self.assertFalse(set(EXTRA_RULES) & {kind for kind, _ in matches})

    def test_shipped_yaml_extracts_all_four_types_after_enabling(self):
        config = (BACKEND / "app/dicts/wih_rules.yml").read_text(encoding="utf-8")
        for rule_id in EXTRA_RULES:
            config, count = re.subn(
                rf'(- id: {rule_id}\n\s+enabled:) false', r'\1 true', config
            )
            self.assertEqual(count, 1)
        matches = self.make_engine(config).extract_from_text(SAMPLE)
        self.assertEqual({kind for kind, _ in matches}, {"domain", *EXTRA_RULES})
        self.assertEqual(len(matches), 5)

    def test_valid_ipv4_ipv6_and_ip_url_hosts(self):
        engine = self.engine_for("ip")
        text = '''"10.0.0.1" "192.0.2.1:8080" "2001:db8::1" "::1" "::"
                  "::ffff:192.0.2.2" "http://[2001:db8::2]:8080/status"
                  "::1:2:3:4:5:6:7" "1:2:3:4:5:6:7::"
                  IPs: 198.51.100.1. IPv6: 2001:db8::3.'''
        self.assertEqual(engine.extract_from_text(text), [
            ("ip", value) for value in (
                "10.0.0.1", "192.0.2.1", "2001:db8::1", "::1", "::",
                "::ffff:192.0.2.2", "2001:db8::2",
                "::1:2:3:4:5:6:7", "1:2:3:4:5:6:7::",
                "198.51.100.1", "2001:db8::3",
            )
        ])

    def test_invalid_and_embedded_ip_fragments_are_ignored(self):
        text = '''"999.0.0.1" "192.0.2.999" "192.000.2.1" "1.2.3.4.5"
                  "v1.2.3.4" "192.0.2.1suffix" "2001:db8::gg" "aa:bb:cc:dd:ee:ff"'''
        self.assertEqual(self.engine_for("ip").extract_from_text(text), [])

    def test_urls_are_classified_by_host_and_preserve_port_path_query_fragment(self):
        domain_urls = [
            "https://api.example.technology:8443/v1/users?q=test#details",
            "HTTP://API.EXAMPLE.COM/v1/users",
            "https://api.internal./health",
            "http://localhost:8000/status",
            "https://api.example.com/a_(b)?next=/login",
        ]
        ip_urls = [
            "http://192.0.2.1:8080/api/status?full=1#top",
            "https://[2001:db8::1]:9443/api/status",
            "http://[::1]",
        ]
        text = " ".join(f'"{url}"' for url in domain_urls + ip_urls)
        engine = self.engine_for("domain_url", "ip_url")
        self.assertEqual(engine.extract_from_text(text),
                         [("domain_url", url) for url in domain_urls]
                         + [("ip_url", url) for url in ip_urls])

    def test_invalid_urls_do_not_become_domain_results_or_abort_later_matches(self):
        text = '''"http://999.0.0.1/a" "http://192.0.2.1:99999/a"
                  "http://api.example.com:abc/a" "http:///a" "http://[bad]/a"
                  "http://[192.0.2.1]/a" "http://[::1]extra/a"
                  "http://-invalid.example/a" "ftp://api.example.com/a"
                  "https://api.example.com/valid"'''
        self.assertEqual(self.engine_for("domain_url", "ip_url").extract_from_text(text),
                         [("domain_url", "https://api.example.com/valid")])

    def test_urls_in_unquoted_text_exclude_surrounding_punctuation(self):
        text = "See (https://api.example.com/a_(b)); then http://[2001:db8::1]."
        self.assertEqual(self.engine_for("domain_url", "ip_url").extract_from_text(text), [
            ("domain_url", "https://api.example.com/a_(b)"),
            ("ip_url", "http://[2001:db8::1]"),
        ])

    def test_long_invalid_tokens_and_url_suffix_do_not_hide_valid_matches(self):
        text = ":" * 50000 + "g " + SAMPLE
        engine = self.engine_for(*EXTRA_RULES)
        self.assertEqual(engine.extract_from_text(text), list(EXPECTED.items()))
        url = "https://api.example.com/a_(b)"
        text = url + ")" * 50000 + "; " + url
        self.assertEqual(self.engine_for("domain_url").extract_from_text(text), [("domain_url", url)])

    def test_paths_in_html_and_javascript_keep_relative_form(self):
        text = '''<a href='/admin/login?next=/home'>login</a>
                  fetch("./api/users"); const endpoint = `../api/users`;
                  <script src="/assets/app.js"></script>
                  "//cdn.example.com/a" "https://api.example.com/v1"
                  "text/html" // comment\n /* comment */'''
        self.assertEqual(self.engine_for("path").extract_from_text(text), [
            ("path", "/admin/login?next=/home"),
            ("path", "./api/users"),
            ("path", "../api/users"),
            ("path", "/assets/app.js"),
        ])

    def test_escaped_slashes_are_supported_for_urls_and_paths(self):
        text = r'''{"url":"https:\/\/api.example.com\/v1", "path":"\/api\/users",
                    "ip":"http:\/\/192.0.2.1:8080\/status"}'''
        self.assertEqual(self.engine_for("path", "domain_url", "ip_url").extract_from_text(text), [
            ("path", "/api/users"),
            ("domain_url", "https://api.example.com/v1"),
            ("ip_url", "http://192.0.2.1:8080/status"),
        ])

    def test_custom_pattern_overrides_each_added_builtin(self):
        for rule_id in EXTRA_RULES:
            with self.subTest(rule_id=rule_id):
                engine = self.make_engine(
                    f"rules:\n  - id: {rule_id}\n    enabled: true\n"
                    "    pattern: 'marker:([A-Z]+)'\n"
                )
                self.assertEqual(engine.extract_from_text(SAMPLE + " marker:CUSTOM"),
                                 [(rule_id, "CUSTOM")])

    def test_deduplication_and_empty_input(self):
        engine = self.engine_for(*EXTRA_RULES)
        expected = engine.extract_from_text(SAMPLE)
        self.assertEqual(len(expected), 4)
        self.assertEqual(engine.extract_from_text(SAMPLE * 2), expected)
        self.assertEqual(engine.extract_from_text(SAMPLE), expected)
        self.assertEqual(engine.extract_from_text(""), [])

    def test_exclusions_apply_to_each_builtin_and_all_source_context_fields(self):
        for rule_id in EXTRA_RULES:
            with self.subTest(rule_id=rule_id):
                content = EXPECTED[rule_id]
                engine = self.engine_for(rule_id, extra=(
                    "exclude_rules:\n  - name: context-specific\n"
                    f"    id: {rule_id}\n    content: '{content}'\n"
                    "    target: example.com\n    source: 'regex:app\\.js$'\n"
                    "    source_tag: script\n    enabled: true\n"
                ))
                context = dict(target_site="https://example.com", source_url="https://example.com/app.js",
                               source_tag="script")
                self.assertEqual(engine.extract_from_text(SAMPLE, **context), [])
                for field in context:
                    changed = dict(context, **{field: "unmatched"})
                    self.assertEqual(engine.extract_from_text(SAMPLE, **changed), [(rule_id, content)])

    def test_exclusion_does_not_remove_other_rule_types(self):
        engine = self.engine_for("ip", "ip_url", extra=(
            "exclude_rules:\n  - id: ip\n    content: 192.0.2.1\n    enabled: true\n"
        ))
        self.assertEqual(engine.extract_from_text(SAMPLE),
                         [("ip_url", "http://192.0.2.1:8080/api/status")])

    def test_no_pyyaml_fallback_supports_builtins_and_exclusions(self):
        with mock.patch.object(rule_engine, "yaml", None):
            engine = self.engine_for(*EXTRA_RULES, extra=(
                "exclude_rules:\n  - id: path\n    content: /api/admin\n    enabled: true\n"
            ))
        self.assertEqual(engine.extract_from_text(SAMPLE), [
            ("ip", "192.0.2.1"),
            ("domain_url", "https://api.example.com/v1/users"),
            ("ip_url", "http://192.0.2.1:8080/api/status"),
        ])

    def test_existing_domain_secret_and_custom_rules_keep_their_behavior(self):
        engine = self.make_engine('''rules:
  - id: domain
    enabled: true
  - id: secret_key
    enabled: true
  - id: example_token
    enabled: true
    pattern: 'token:([A-Z]+)'
''')
        text = 'API.EXAMPLE.COM github.com api_secret="abcdefghijklmnopqrst" token:EXAMPLE'
        self.assertEqual(engine.extract_from_text(text), [
            ("domain", "api.example.com"),
            ("secret_key", "abcdefghijklmnopqrst"),
            ("example_token", "EXAMPLE"),
        ])


if __name__ == "__main__":
    unittest.main()
