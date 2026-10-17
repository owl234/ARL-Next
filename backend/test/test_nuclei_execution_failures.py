"""原扫描与子进程执行函数；模拟 CLI 及可选实际 Nuclei 本地失败验证。"""
import ast
import copy
from contextlib import contextmanager, nullcontext
import itertools
import json
import logging
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time
import traceback
import types
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / 'app/services/nuclei_scan.py'
LOG = logging.getLogger('nuclei-failure-fixture')


def execute(nodes, env):
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), 'nuclei-failure-fixture', 'exec'), env)


class FailureTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        counter = itertools.count()
        self.templates = [{'template_id': 'local-fixture', 'content': 'id: local-fixture\n'}]
        self.utils = types.SimpleNamespace(
            get_logger=lambda: LOG, random_choices=lambda *args: f'fixture{next(counter)}',
            conn_db=lambda name: types.SimpleNamespace(find=lambda *args, **kwargs:
                self.templates if name == 'nuclei_template' else [{'template_id': 'ignored-fixture'}]))
        utility = dict(subprocess=subprocess, shlex=shlex)
        fn = next(n for n in ast.parse((ROOT / 'app/utils/__init__.py').read_text()).body
                  if isinstance(n, ast.FunctionDef) and n.name == 'exec_system')
        execute([copy.deepcopy(fn)], utility)
        self.utils.exec_system = utility['exec_system']
        env = dict(Config=types.SimpleNamespace(TMP_PATH=str(self.root)), utils=self.utils)
        tree = ast.parse(SCANNER.read_text())
        execute([n for n in tree.body if not (
            isinstance(n, ast.ImportFrom) and n.module in ('app', 'app.config'))], env)
        self.module = types.SimpleNamespace(**env)
        self.scan = self.module.NucleiScan(['http://127.0.0.1:12345'])
        self.binary = self.root / 'nuclei-fixture'
        self.binary.write_text(f'#!{sys.executable}\n' + '''import json, sys
from pathlib import Path
if '-version' in sys.argv:
    sys.exit(0)
mode = json.loads(Path(__file__).with_suffix('.json').read_text())
if not mode.get('no_output'):
    path = Path(sys.argv[sys.argv.index('-o') + 1])
    path.write_text(''.join(json.dumps(r) + '\\n' for r in mode.get('results', [])))
sys.exit(mode.get('code', 0))
''')
        self.binary.chmod(0o755)
        self.scan.nuclei_bin_path = str(self.binary)
        self.set_mode()
        imported = patch.dict(sys.modules, {'app.routes.nuclei': types.SimpleNamespace(get_community_templates_dir=lambda: '')})
        imported.start()
        self.addCleanup(imported.stop)

    def set_mode(self, code=0, results=None, **extra):
        self.binary.with_suffix('.json').write_text(json.dumps({'code': code, 'results': results or [], **extra}))

    def finding(self):
        return {'template-id': 'fixture', 'host': 'http://127.0.0.1:12345',
                'matched-at': 'http://127.0.0.1:12345/probe',
                'info': {'name': 'Local finding', 'severity': 'high'}}

    def paths(self):
        return [self.scan.nuclei_target_path, self.scan.nuclei_result_path,
                self.scan.custom_templates_path, self.scan.nuclei_exclude_file]

    def assert_cleaned(self):
        for path in self.paths():
            if path:
                self.assertFalse(Path(path).exists(), path)

    def test_nonzero_exit_raises_and_cleans_every_artifact(self):
        for code in (1, 7):
            with self.subTest(code=code):
                self.set_mode(code=code)
                with self.assertRaises(subprocess.CalledProcessError) as error:
                    self.scan.run()
                self.assertEqual(error.exception.returncode, code)
                self.assertIsNotNone(self.scan.custom_templates_path)
                self.assertIsNotNone(self.scan.nuclei_exclude_file)
                self.assert_cleaned()

    def test_failed_process_partial_results_are_not_reported_as_success(self):
        self.set_mode(code=2, results=[self.finding()])
        with patch.object(self.scan, 'dump_result') as parse, self.assertRaises(subprocess.CalledProcessError):
            self.scan.run()
        parse.assert_not_called()
        self.assert_cleaned()

    def test_success_without_matches_is_still_an_empty_result(self):
        for no_output in (False, True):
            with self.subTest(no_output=no_output):
                self.set_mode(no_output=no_output)
                self.assertEqual(self.scan.run(), [])
                self.assert_cleaned()

    def test_successful_results_are_parsed_before_cleanup(self):
        self.set_mode(results=[self.finding()])
        results = self.scan.run()
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]['template_id'], 'fixture')
        self.assertEqual(results[0]['vuln_url'], self.finding()['matched-at'])
        self.assert_cleaned()

    def test_timeout_and_launch_error_propagate_after_cleanup(self):
        for failure in (subprocess.TimeoutExpired('fixture', 1), OSError('fixture launch failure')):
            with self.subTest(failure=type(failure).__name__):
                def fail(*args, **kwargs):
                    Path(self.scan.nuclei_result_path).write_text('partial')
                    raise failure
                with patch.object(self.utils, 'exec_system', side_effect=fail), self.assertRaises(type(failure)) as error:
                    self.scan.run()
                self.assertIs(error.exception, failure)
                self.assert_cleaned()

    def test_partial_template_preparation_is_cleaned(self):
        failure = OSError('fixture materialization failure')
        def prepare():
            self.scan.custom_templates_path = str(self.root / 'partial-template-dir')
            Path(self.scan.custom_templates_path).mkdir()
            (Path(self.scan.custom_templates_path) / 'partial.yaml').write_text('partial')
            raise failure
        with patch.object(self.scan, '_materialize_custom_templates', side_effect=prepare), self.assertRaises(OSError) as error:
            self.scan.run()
        self.assertIs(error.exception, failure)
        self.assert_cleaned()

    def test_result_read_failure_propagates_after_cleanup(self):
        self.set_mode(results=[self.finding()])
        with patch.object(self.scan, 'dump_result', side_effect=PermissionError('fixture read failure')), self.assertRaises(PermissionError):
            self.scan.run()
        self.assert_cleaned()

    def test_one_cleanup_failure_does_not_skip_others_or_mask_scan_error(self):
        self.set_mode(code=7, results=[self.finding()])
        original_unlink = os.unlink
        def unlink(path, *args, **kwargs):
            if str(path) == self.scan.nuclei_target_path:
                raise PermissionError('fixture cleanup failure')
            return original_unlink(path, *args, **kwargs)
        with patch.object(self.module.os, 'unlink', side_effect=unlink), self.assertLogs(LOG, level='WARNING') as logs:
            with self.assertRaises(subprocess.CalledProcessError) as error:
                self.scan.run()
        self.assertEqual(error.exception.returncode, 7)
        self.assertTrue(Path(self.scan.nuclei_target_path).exists())
        for path in self.paths()[1:]:
            self.assertFalse(Path(path).exists(), path)
        self.assertIn('fixture cleanup failure', '\n'.join(logs.output))

    def test_cleanup_failure_keeps_successful_scan_result(self):
        self.set_mode(results=[self.finding()])
        with patch.object(self.module.shutil, 'rmtree', side_effect=PermissionError('fixture directory failure')):
            with self.assertLogs(LOG, level='WARNING'):
                results = self.scan.run()
        self.assertEqual(len(results), 1)
        self.assertTrue(Path(self.scan.custom_templates_path).exists())
        self.assertFalse(Path(self.scan.nuclei_exclude_file).exists())

    def test_missing_engine_retains_skip_behavior(self):
        self.scan.nuclei_bin_path = str(self.root / 'missing')
        with patch.object(self.scan, 'exec_nuclei') as execute_scan:
            self.assertEqual(self.scan.run(), [])
        execute_scan.assert_not_called()

    def test_existing_phase_handler_records_execution_failure(self):
        self.set_mode(code=7)
        tree = ast.parse((ROOT / 'app/services/commonTask.py').read_text())
        phase = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'safe_phase')
        env = dict(contextmanager=contextmanager, time=time, traceback=traceback, logger=LOG,
                   TaskHeartbeat=lambda *args, **kwargs: nullcontext())
        execute([copy.deepcopy(phase)], env)
        update = Mock()
        with self.assertLogs(LOG, level='ERROR'):
            with env['safe_phase'](types.SimpleNamespace(task_id='fixture-task'), 'nuclei_scan', update):
                self.scan.run()
        update.update_services.assert_any_call('nuclei_scan_error', 0.0)
        self.assertTrue(any(call.args[0] == 'error_msg' and '7' in call.args[1]
                            for call in update.update_task_field.call_args_list))
        self.assert_cleaned()

    @unittest.skipUnless(os.environ.get('NUCLEI_TEST_BINARY'), 'Set NUCLEI_TEST_BINARY for actual engine failure')
    def test_real_nuclei_rejects_invalid_template_and_cleans_artifacts(self):
        config = self.root / 'config'
        templates = self.root / 'templates'
        config.mkdir()
        templates.mkdir()
        (config / 'config.yaml').write_text('{}\n')
        self.templates[0]['content'] = 'invalid: [yaml\n'
        self.scan.nuclei_bin_path = os.environ['NUCLEI_TEST_BINARY']
        isolated = dict(os.environ, NUCLEI_CONFIG_DIR=str(config), NUCLEI_TEMPLATES_DIR=str(templates),
                        DISABLE_NUCLEI_TEMPLATES_PUBLIC_DOWNLOAD='true', NO_PROXY='127.0.0.1,localhost')
        real_run = subprocess.run
        def run(command, **kwargs):
            if '-version' not in command:
                command = [*command, '-ni', '-nh', '-no-stdin']
            kwargs.update(env=isolated, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            kwargs['timeout'] = min(kwargs.get('timeout', 30), 30)
            return real_run(command, **kwargs)
        with patch.object(self.module.subprocess, 'run', side_effect=run), self.assertRaises(subprocess.CalledProcessError):
            self.scan.run()
        self.assert_cleaned()


if __name__ == '__main__':
    unittest.main()
