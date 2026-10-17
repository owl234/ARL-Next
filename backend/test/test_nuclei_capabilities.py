"""启动能力检测与扫描兼容性；数据库和外部引擎以隔离夹具代替。"""
import ast
import itertools
import json
import logging
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import types
import unittest
from unittest.mock import Mock, patch


SOURCE = Path(__file__).resolve().parents[1] / 'app/services/nuclei_scan.py'


def load_scanner(tmp_dir):
    # 执行真实模块，替换会初始化完整应用的两个导入。
    tree = ast.parse(SOURCE.read_text())
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.ImportFrom) and node.module in ('app', 'app.config'))]
    counter = itertools.count()
    utils = types.SimpleNamespace(get_logger=lambda: logging.getLogger('nuclei-fixture'),
        random_choices=lambda *args: 'fixture{}'.format(next(counter)),
        conn_db=lambda name: types.SimpleNamespace(find=lambda *args, **kwargs: []))
    env = {'Config': types.SimpleNamespace(TMP_PATH=tmp_dir), 'utils': utils}
    exec(compile(tree, str(SOURCE), 'exec'), env)
    return types.SimpleNamespace(**env)


class NucleiCapabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.module = load_scanner(self.tmp.name)
        self.binary = self.write_binary('nuclei')

    def write_binary(self, name):
        path = Path(self.tmp.name) / name
        path.write_bytes(b'fixture executable\n')
        path.chmod(0o755)
        return path.resolve()

    def scanner(self, binary=None, options=None):
        scan = self.module.NucleiScan(['http://127.0.0.1:12345'], options)
        scan.nuclei_bin_path = str(binary or self.binary)
        return scan

    @staticmethod
    def success(*args, **kwargs):
        return types.SimpleNamespace(returncode=0)

    def test_modern_cli_one_probe_and_cache_across_scan_instances(self):
        with patch.object(self.module.subprocess, 'run', side_effect=self.success) as probe:
            first, second = self.scanner(), self.scanner()
            self.assertTrue(first.check_have_nuclei())
            self.assertTrue(second.check_have_nuclei())
            self.assertEqual(first.nuclei_json_flag, '-jsonl')
            self.assertEqual(second.nuclei_json_flag, '-jsonl')
            self.assertEqual(first.nuclei_bin_path, str(self.binary.resolve()))
            self.assertEqual(probe.call_count, 1)
            self.assertEqual(probe.call_args.args[0], [str(self.binary), '-duc', '-jsonl', '-version'])
            self.assertEqual(probe.call_args.kwargs['timeout'], 5)

    def test_legacy_cli_fallback_and_success_cache(self):
        def legacy(args, **kwargs):
            return types.SimpleNamespace(returncode=0 if '-json' in args else 2)
        with patch.object(self.module.subprocess, 'run', side_effect=legacy) as probe:
            for _ in range(2):
                scan = self.scanner()
                self.assertTrue(scan.check_have_nuclei())
                self.assertEqual(scan.nuclei_json_flag, '-json')
            self.assertEqual(probe.call_count, 2)

    def test_missing_binary_not_cached_and_later_install_recovers(self):
        missing = Path(self.tmp.name) / 'later-installed'
        with patch.object(self.module.subprocess, 'run', side_effect=self.success) as probe:
            self.assertEqual(self.scanner(missing).run(), [])
            probe.assert_not_called()
            self.write_binary(missing.name)
            self.assertTrue(self.scanner(missing).check_have_nuclei())
            self.assertEqual(probe.call_count, 1)

    def test_nonzero_version_skips_scan_and_failure_is_not_cached(self):
        with patch.object(self.module.subprocess, 'run', return_value=types.SimpleNamespace(returncode=1)) as probe:
            scan = self.scanner()
            scan.exec_nuclei = Mock()
            self.assertEqual(scan.run(), [])
            scan.exec_nuclei.assert_not_called()
            self.assertEqual(probe.call_count, 3)
        with patch.object(self.module.subprocess, 'run', side_effect=self.success) as probe:
            self.assertTrue(self.scanner().check_have_nuclei())
            self.assertEqual(probe.call_count, 1)

    def test_unsupported_json_reports_error_without_caching(self):
        def unsupported(args, **kwargs):
            return types.SimpleNamespace(returncode=0 if args == [str(self.binary), '-version'] else 2)
        with patch.object(self.module.subprocess, 'run', side_effect=unsupported) as probe:
            for _ in range(2):
                with self.assertRaisesRegex(RuntimeError, 'does not support'):
                    self.scanner().run()
            self.assertEqual(probe.call_count, 6)
            self.assertEqual(self.module._detect_json_flag.cache_info().currsize, 0)

    def test_launch_error_not_cached(self):
        with patch.object(self.module.subprocess, 'run', side_effect=OSError('fixture launch error')):
            self.assertFalse(self.scanner().check_have_nuclei())
        with patch.object(self.module.subprocess, 'run', side_effect=self.success) as probe:
            self.assertTrue(self.scanner().check_have_nuclei())
            self.assertEqual(probe.call_count, 1)

    def test_timeout_not_cached_and_scan_does_not_start(self):
        with patch.object(self.module.subprocess, 'run', side_effect=subprocess.TimeoutExpired('fixture', 5)):
            scan = self.scanner()
            scan.exec_nuclei = Mock()
            self.assertEqual(scan.run(), [])
            scan.exec_nuclei.assert_not_called()
        with patch.object(self.module.subprocess, 'run', side_effect=self.success) as probe:
            self.assertTrue(self.scanner().check_have_nuclei())
            self.assertEqual(probe.call_count, 1)

    def test_atomic_replacement_invalidates_same_size_and_mtime(self):
        original = self.binary.stat()
        with patch.object(self.module.subprocess, 'run', side_effect=self.success) as probe:
            self.scanner()._check_json_flag()
            replacement = self.write_binary('replacement')
            os.utime(replacement, ns=(original.st_atime_ns, original.st_mtime_ns))
            os.replace(replacement, self.binary)
            self.assertEqual(original.st_size, self.binary.stat().st_size)
            self.assertEqual(original.st_mtime_ns, self.binary.stat().st_mtime_ns)
            self.scanner()._check_json_flag()
            self.assertEqual(probe.call_count, 2)

    def test_in_place_replacement_updates_capability(self):
        def supports(args, **kwargs):
            wanted = '-json' if self.binary.read_bytes().startswith(b'legacy') else '-jsonl'
            return types.SimpleNamespace(returncode=0 if wanted in args else 2)
        with patch.object(self.module.subprocess, 'run', side_effect=supports) as probe:
            modern = self.scanner()
            modern._check_json_flag()
            self.binary.write_bytes(b'legacy executable changed\n')
            legacy = self.scanner()
            legacy._check_json_flag()
            self.assertEqual(modern.nuclei_json_flag, '-jsonl')
            self.assertEqual(legacy.nuclei_json_flag, '-json')
            self.assertEqual(probe.call_count, 3)

    def test_symlink_switch_invalidates_cache(self):
        link = Path(self.tmp.name) / 'nuclei-link'
        second = self.write_binary('nuclei-second')
        link.symlink_to(self.binary)
        with patch.object(self.module.subprocess, 'run', side_effect=self.success) as probe:
            self.scanner(link)._check_json_flag()
            link.unlink()
            link.symlink_to(second)
            scan = self.scanner(link)
            scan._check_json_flag()
            self.assertEqual(probe.call_count, 2)
            self.assertEqual(scan.nuclei_bin_path, str(second))

    def test_path_change_uses_new_binary(self):
        second_dir = Path(self.tmp.name) / 'second'
        second_dir.mkdir()
        second = self.write_binary('second/nuclei')
        with patch.object(self.module.subprocess, 'run', side_effect=self.success) as probe:
            for directory in (self.tmp.name, str(second_dir)):
                with patch.dict(os.environ, {'PATH': directory}):
                    scan = self.scanner()
                    scan.nuclei_bin_path = 'nuclei'
                    scan._check_json_flag()
            self.assertEqual(probe.call_count, 2)
            self.assertEqual(scan.nuclei_bin_path, str(second))

    def test_cached_binary_permission_removal_is_detected(self):
        with patch.object(self.module.subprocess, 'run', side_effect=self.success) as probe:
            self.scanner()._check_json_flag()
            self.binary.chmod(0o644)
            self.assertFalse(self.scanner().check_have_nuclei())
            self.assertEqual(probe.call_count, 1)
            self.binary.chmod(0o755)
            self.scanner()._check_json_flag()
            self.assertEqual(probe.call_count, 2)

    def test_worker_process_identity_does_not_reuse_parent_cache(self):
        with patch.object(self.module.subprocess, 'run', side_effect=self.success) as probe:
            for pid in (100, 100, 200, 200):
                with patch.object(self.module.os, 'getpid', return_value=pid):
                    self.scanner()._check_json_flag()
            self.assertEqual(probe.call_count, 2)

    def test_success_cache_is_bounded(self):
        with patch.object(self.module.subprocess, 'run', side_effect=self.success):
            for index in range(12):
                self.scanner(self.write_binary('version-{}'.format(index)))._check_json_flag()
        self.assertEqual(self.module._detect_json_flag.cache_info().currsize, 8)

    def test_scan_flags_results_and_cleanup_for_modern_and_legacy_cli(self):
        for flag in ('-jsonl', '-json'):
            with self.subTest(flag=flag):
                binary = self.write_binary(flag[1:] + ' with spaces')
                scan = self.scanner(binary, {'nuclei_config': {
                    'severity': ['critical', 'high'], 'exclude_blacklist': False,
                    'extra_exclude_ids': ['ignore-fixture']}})
                commands = []

                def execute(command, **kwargs):
                    args = shlex.split(' '.join(command))
                    commands.append(args)
                    self.assertEqual(Path(scan.nuclei_target_path).read_text(), 'http://127.0.0.1:12345\n')
                    Path(scan.nuclei_result_path).write_text(json.dumps({
                        'template-id': 'fixture-template', 'host': 'http://127.0.0.1:12345',
                        'matched-at': 'http://127.0.0.1:12345/probe',
                        'info': {'name': 'fixture finding', 'severity': 'high'}}) + '\n')
                    return types.SimpleNamespace(returncode=0)

                def probe(args, **kwargs):
                    return types.SimpleNamespace(returncode=0 if flag in args else 2)

                self.module.utils.exec_system = execute
                with patch.object(self.module.subprocess, 'run', side_effect=probe) as cli:
                    results = scan.run()
                self.assertEqual(cli.call_count, 1 if flag == '-jsonl' else 2)
                self.assertEqual(len(commands), 1)
                args = commands[0]
                self.assertEqual(args[0], str(binary))
                self.assertEqual(args[args.index('-tags') + 1], 'cve,http')
                self.assertEqual(args[args.index('-severity') + 1], 'critical,high')
                self.assertIn(flag, args)
                self.assertIn('-eid', args)
                self.assertEqual(results[0]['template_id'], 'fixture-template')
                self.assertEqual(results[0]['vuln_url'], 'http://127.0.0.1:12345/probe')
                self.assertFalse(Path(scan.nuclei_target_path).exists())
                self.assertFalse(Path(scan.nuclei_result_path).exists())
                self.assertFalse(Path(scan.nuclei_exclude_file).exists())


@unittest.skipUnless(os.environ.get('NUCLEI_TEST_BINARY'), 'Set NUCLEI_TEST_BINARY for loopback integration')
class RealNucleiCapabilityTests(unittest.TestCase):
    def test_real_cli_scan_and_warm_cache_match_direct_scan(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = b'local-fixture-match'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.05), daemon=True)
        thread.start()
        self.addCleanup(thread.join)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            template_dir = root / 'templates'
            template_dir.mkdir()
            for product in ('wordpress', 'jenkins'):
                (template_dir / (product + '.yaml')).write_text('''id: fixture-'''+product+'''
info:
  name: Loopback fixture
  author: local-test
  severity: high
  tags: cve,http,'''+product+'''
http:
  - method: GET
    path: ["{{BaseURL}}/probe"]
    matchers:
      - type: word
        words: ["local-fixture-match"]
''')
            config_dir = root / 'config'
            config_dir.mkdir()
            (config_dir / 'config.yaml').write_text('{}\n')
            binary = str(Path(os.environ['NUCLEI_TEST_BINARY']).resolve())
            target = 'http://127.0.0.1:{}'.format(server.server_port)
            env = dict(os.environ, NUCLEI_CONFIG_DIR=str(config_dir),
                NUCLEI_TEMPLATES_DIR=str(template_dir), DISABLE_NUCLEI_TEMPLATES_PUBLIC_DOWNLOAD='true',
                NO_PROXY='127.0.0.1,localhost')
            run_process = subprocess.run
            direct = run_process([binary, '-duc', '-ni', '-nh', '-no-stdin', '-silent', '-jsonl',
                '-tags', 'cve,http', '-severity', 'high', '-u', target],
                env=env, capture_output=True, text=True, timeout=30)
            self.assertEqual(direct.returncode, 0, direct.stderr)
            expected = {json.loads(line)['template-id'] for line in direct.stdout.splitlines()}
            self.assertEqual(expected, {'fixture-wordpress', 'fixture-jenkins'})
            module = load_scanner(tmp)
            probes, commands = [], []

            def probe(command, **kwargs):
                probes.append(command)
                return run_process(command, env=env, **kwargs)

            def execute(command, **kwargs):
                args = shlex.split(' '.join(command))
                commands.append(args)
                # 这些隔离测试参数不写入应用配置。
                completed = run_process(args + ['-ni', '-nh', '-no-stdin'], env=env,
                    capture_output=True, text=True, timeout=30)
                self.assertEqual(completed.returncode, 0, completed.stderr)
                return completed

            module.utils.exec_system = execute
            with patch.object(module.subprocess, 'run', side_effect=probe):
                for _ in range(2):
                    scan = module.NucleiScan([target], {'nuclei_config': {'severity': ['high']}})
                    scan.nuclei_bin_path = binary
                    results = scan.run()
                    self.assertEqual({item['template_id'] for item in results}, expected)
                    self.assertFalse(Path(scan.nuclei_result_path).exists())
            self.assertEqual(len(probes), 1)
            self.assertEqual(len(commands), 2)
            def comparable(command):
                args = list(command)
                for flag in ('-l', '-o'):
                    args[args.index(flag) + 1] = '<temporary-file>'
                return args
            self.assertEqual(comparable(commands[0]), comparable(commands[1]))


if __name__ == '__main__':
    unittest.main()
