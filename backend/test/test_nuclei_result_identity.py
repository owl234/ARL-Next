"""真实解析/批量入库/资产同步方法配合 mongomock；实际引擎仅访问本地 HTTP。"""
import ast
import copy
from datetime import datetime
import itertools
import json
import logging
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from bson import ObjectId
import mongomock
from pymongo import UpdateOne


ROOT = Path(__file__).resolve().parents[1]
SCANNER = ROOT / 'app/services/nuclei_scan.py'
LOG = logging.getLogger(__name__)


def execute(nodes, env):
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), 'nuclei-result-fixture', 'exec'), env)


def load_nodes(path, names, env):
    execute([copy.deepcopy(n) for n in ast.parse((ROOT / path).read_text()).body
             if getattr(n, 'name', None) in names], env)


def raw_result(url='http://127.0.0.1:8080', **extra):
    return {'template-id': 'fixture-template', 'host': '127.0.0.1', 'url': url,
            'matched-at': url + '/probe', 'info': {'name': 'Fixture', 'severity': 'high'}, **extra}


class ResultFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name)
        self.db = mongomock.MongoClient().arl
        count = itertools.count()
        self.utils = types.SimpleNamespace(
            get_logger=lambda: LOG, random_choices=lambda *args: str(next(count)),
            conn_db=self.db.__getitem__, curr_date=lambda: '2026-10-15 12:00:00',
            curr_date_obj=lambda: datetime(2026, 10, 15, 12))
        env = dict(Config=types.SimpleNamespace(TMP_PATH=str(self.directory)), utils=self.utils)
        tree = ast.parse(SCANNER.read_text())
        execute([n for n in tree.body if not (
            isinstance(n, ast.ImportFrom) and n.module in ('app', 'app.config'))], env)
        self.scanner = env['NucleiScan']([])

        monitor = types.ModuleType('app.utils.monitor_diff')
        monitor.__dict__.update(conn_db=self.db.__getitem__, _get_task_scope_id=lambda _: None)
        load_nodes('app/utils/monitor_diff.py', ['_get_baseline_query', '_compute_update_diff', 'tag_monitor_diff'], monitor.__dict__)
        modules = patch.dict(sys.modules, {'app.utils.monitor_diff': monitor})
        modules.start()
        self.addCleanup(modules.stop)
        self.baseline_query = monitor._get_baseline_query
        persistence = dict(UpdateOne=UpdateOne, conn_db=self.db.__getitem__)
        load_nodes('app/utils/__init__.py', ['safe_insert_asset_many'], persistence)
        self.utils.safe_insert_asset_many = persistence['safe_insert_asset_many']

        # 使用生产定义的唯一索引，不另写测试专用去重规则。
        tree = ast.parse((ROOT / 'app/utils/arlupdate.py').read_text())
        indexes = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign) and
                       any(isinstance(t, ast.Name) and t.id == 'unique_indexes' for t in n.targets))
        index_env = {}
        execute([copy.deepcopy(indexes)], index_env)
        self.db.nuclei_result.create_index(index_env['unique_indexes']['nuclei_result'], unique=True)

        # 只加载原任务的 Nuclei 入库方法，隔离其他扫描阶段。
        tree = ast.parse((ROOT / 'app/services/commonTask.py').read_text())
        method = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'nuclei_scan')
        method = copy.deepcopy(method)
        method.name = 'save_scan_results'
        self.common_env = dict(utils=self.utils, logger=LOG)
        execute([method], self.common_env)
        sync_env = dict(copy=copy, re=re, ObjectId=ObjectId, utils=self.utils, conn=self.db.__getitem__, logger=LOG)
        load_nodes('app/services/syncAsset.py', ['SyncAsset'], sync_env)
        self.sync_class = sync_env['SyncAsset']

    def parse(self, records):
        Path(self.scanner.nuclei_result_path).write_text(''.join(json.dumps(r) + '\n' for r in records))
        return self.scanner.dump_result()

    def scan_and_save(self, records, task='task-a'):
        self.common_env['nuclei_scan'] = lambda *args, **kwargs: self.parse(records)
        self.common_env['save_scan_results'](types.SimpleNamespace(task_id=task, poc_sites={'fixture'}, options={}))

    def sync(self, task='task-a', scope='scope-a', update=True):
        sync = self.sync_class(task, scope, update_flag=update, category=['nuclei_result'])
        sync.sync_by_category('nuclei_result')


class ParserTests(ResultFixture):
    def test_modern_url_keeps_protocol_port_and_base_path(self):
        urls = ['http://127.0.0.1:8080/app-a', 'http://127.0.0.1:8443/app-a',
                'https://127.0.0.1:8443/app-a', 'https://127.0.0.1:8443/app-b']
        parsed = self.parse([raw_result(url) for url in urls])
        self.assertEqual([r['host'] for r in parsed], urls)
        self.assertEqual([r['target'] for r in parsed], urls)

    def test_legacy_host_and_matched_fallback_remain_supported(self):
        cases = [({'host': 'https://legacy.example:9443/base'}, 'https://legacy.example:9443/base'),
                 ({'host': 'legacy.example'}, 'legacy.example'),
                 ({'matched-at': 'https://fallback.example:8443/probe'}, 'https://fallback.example:8443/probe'),
                 ({'url': '', 'host': None, 'matched-at': 'dns.example'}, 'dns.example')]
        for record, expected in cases:
            with self.subTest(record=record):
                parsed = self.parse([record])[0]
                self.assertEqual(parsed['host'], expected)
                self.assertEqual(parsed['target'], expected)

    def test_separate_host_port_and_scheme_preserve_service_identity(self):
        cases = [('example.com', '80', 'http', 'http://example.com:80'),
                 ('example.com', 443, 'https', 'https://example.com:443'),
                 ('192.0.2.1', '6379', None, '192.0.2.1:6379'),
                 ('::1', '8080', 'http', 'http://[::1]:8080'),
                 ('[::1]', '8443', 'https', 'https://[::1]:8443'),
                 ('::1', None, 'http', 'http://[::1]')]
        for host, port, scheme, expected in cases:
            with self.subTest(host=host, port=port):
                parsed = self.parse([{'host': host, 'port': port, 'scheme': scheme}])[0]
                self.assertEqual(parsed['host'], expected)

    def test_legacy_host_with_port_is_not_appended_twice(self):
        for host in ('example.com:8080', '[::1]:8080', 'http://example.com:8080/base'):
            with self.subTest(host=host):
                self.assertEqual(self.parse([{'host': host, 'port': '8080'}])[0]['target'], host)

    def test_vulnerability_evidence_fields_remain_intact(self):
        record = raw_result(**{'template-url': 'https://templates.example/fixture',
                               'curl-command': 'curl http://127.0.0.1:8080/probe', 'extracted-results': ['fixture']})
        parsed = self.parse([record])[0]
        self.assertEqual(parsed['vuln_url'], record['matched-at'])
        self.assertEqual(parsed['template_id'], record['template-id'])
        self.assertEqual(parsed['vuln_name'], 'Fixture')
        self.assertEqual(parsed['vuln_severity'], 'high')
        self.assertEqual(parsed['extracted_results'], ['fixture'])
        self.assertEqual(parsed['curl_command'], record['curl-command'])


class PersistenceTests(ResultFixture):
    def test_two_ports_survive_task_upsert_and_repeated_asset_sync(self):
        records = [raw_result('http://127.0.0.1:8080'), raw_result('http://127.0.0.1:8443')]
        for _ in range(2):
            self.scan_and_save(records)
            self.sync()
        self.assertEqual(self.db.nuclei_result.count_documents({}), 2)
        self.assertEqual(self.db.asset_nuclei_result.count_documents({}), 2)
        self.assertEqual({d['target'] for d in self.db.asset_nuclei_result.find()}, {r['url'] for r in records})

    def test_tasks_templates_and_scopes_keep_their_existing_boundaries(self):
        records = [raw_result(), raw_result(**{'template-id': 'second-template'})]
        for task in ('task-a', 'task-b'):
            self.scan_and_save(records, task)
            self.sync(task)
        self.sync(scope='scope-b')
        self.assertEqual(self.db.nuclei_result.count_documents({}), 4)
        self.assertEqual(self.db.asset_nuclei_result.count_documents({'scope_id': 'scope-a'}), 2)
        self.assertEqual(self.db.asset_nuclei_result.count_documents({'scope_id': 'scope-b'}), 2)

    def test_legacy_full_url_matches_new_result_without_archive_duplicates(self):
        legacy = raw_result()
        legacy.pop('url')
        legacy['host'] = 'http://127.0.0.1:8080'
        self.scan_and_save([legacy])
        self.sync()
        existing = self.db.asset_nuclei_result.find_one()
        self.scan_and_save([raw_result()])
        self.sync()
        self.assertEqual(self.db.nuclei_result.count_documents({}), 1)
        self.assertEqual(self.db.asset_nuclei_result.count_documents({}), 1)
        self.assertEqual(self.db.asset_nuclei_result.find_one()['_id'], existing['_id'])

    def test_ambiguous_legacy_record_is_retained_without_guessing_its_port(self):
        legacy = {'scope_id': 'scope-a', 'host': '127.0.0.1', 'target': '127.0.0.1', 'template_id': 'fixture-template'}
        old_id = self.db.asset_nuclei_result.insert_one(copy.deepcopy(legacy)).inserted_id
        self.scan_and_save([raw_result('http://127.0.0.1:8080'), raw_result('http://127.0.0.1:8443')])
        self.sync()
        self.assertEqual(self.db.asset_nuclei_result.count_documents({}), 3)
        self.assertEqual(self.db.asset_nuclei_result.find_one({'_id': old_id}), dict(legacy, _id=old_id))

    def test_monitor_baselines_distinguish_the_same_template_on_different_ports(self):
        parsed = self.parse([raw_result('http://127.0.0.1:8080'), raw_result('http://127.0.0.1:8443')])
        queries = [self.baseline_query('nuclei_result', item, 'scope-a') for item in parsed]
        self.assertNotEqual(queries[0], queries[1])


@unittest.skipUnless(os.environ.get('NUCLEI_TEST_BINARY'), 'Set NUCLEI_TEST_BINARY for real loopback scan')
class RealNucleiTests(ResultFixture):
    def test_two_real_http_ports_survive_parsing_storage_and_asset_sync(self):
        from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
        import threading

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                body = b'local-port-fixture'
                self.send_response(200)
                self.send_header('Content-Length', str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            def log_message(self, *args):
                pass

        targets = []
        for _ in range(2):
            server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
            thread = threading.Thread(target=lambda s=server: s.serve_forever(poll_interval=0.05), daemon=True)
            thread.start()
            self.addCleanup(thread.join)
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            targets.append(f'http://127.0.0.1:{server.server_port}')
        templates, config = self.directory / 'templates', self.directory / 'config'
        templates.mkdir()
        config.mkdir()
        (config / 'config.yaml').write_text('{}\n')
        (templates / 'fixture.yaml').write_text('''id: fixture-two-ports
info:
  name: Local port fixture
  author: local-test
  severity: high
  tags: cve,http
http:
  - method: GET
    path: ["{{BaseURL}}/probe"]
    matchers:
      - type: word
        words: ["local-port-fixture"]
''')
        target_file = self.directory / 'targets.txt'
        target_file.write_text('\n'.join(targets))
        env = dict(os.environ, NUCLEI_CONFIG_DIR=str(config), NUCLEI_TEMPLATES_DIR=str(templates),
                   DISABLE_NUCLEI_TEMPLATES_PUBLIC_DOWNLOAD='true', NO_PROXY='127.0.0.1,localhost')
        result = subprocess.run([os.environ['NUCLEI_TEST_BINARY'], '-duc', '-ni', '-nh', '-no-stdin',
                                 '-silent', '-jsonl', '-l', str(target_file), '-t', str(templates)],
                                env=env, capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        records = [json.loads(line) for line in result.stdout.splitlines()]
        self.assertEqual(len(records), 2)
        for _ in range(2):
            self.scan_and_save(records)
            self.sync()
        for collection in ('nuclei_result', 'asset_nuclei_result'):
            self.assertEqual(self.db[collection].count_documents({}), 2)
            self.assertEqual({d['target'] for d in self.db[collection].find()}, set(targets))


if __name__ == '__main__':
    unittest.main()
