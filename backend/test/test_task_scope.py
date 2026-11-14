"""离线验证原路由、派发/重启、范围匹配和真实资产同步方法。

AST 加载原实现以隔离应用启动；配置、安全策略、消息队列和通知为 fixture，
数据库使用 mongomock，域名匹配使用 tld，IP 匹配使用项目内的 IPy。
"""
import ast
import copy
from contextlib import contextmanager
from datetime import datetime
import functools
import importlib.util
import logging
from pathlib import Path
import re
import sys
import types
import unittest
from unittest.mock import patch

import bson
from bson import ObjectId
from flask import Flask, request
from flask_restx import Api, Namespace, Resource, fields, reqparse
import mongomock
import tld

ROOT = Path(__file__).resolve().parents[1]


def load_nodes(path, env, names):
    tree = ast.parse((ROOT / path).read_text())
    nodes = [copy.deepcopy(n) for n in tree.body if getattr(n, 'name', None) in names or
             isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in n.targets)]
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(path), 'exec'), env)


def module(name):
    result = types.ModuleType(name)
    result.__path__ = []
    result.__package__ = name.rpartition('.')[0]
    return result


class Queue:
    def __init__(self):
        self.calls = []
        self.error = None
        self.worker = None
    def apply_async(self, **kwargs):
        self.calls.append(copy.deepcopy(kwargs))
        if self.worker:
            self.worker(kwargs['kwargs']['options']['data'])
        if self.error:
            raise self.error
        return 'queue-fixture-id'


class ScopeFixture(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().arl
        self.queue = Queue()
        self.pushes = []
        self.logger = logging.getLogger('task_scope_fixture')
        self.logger.addHandler(logging.NullHandler())
        self.logger.propagate = False
        names = ['app', 'app.utils', 'app.utils.security_policy', 'app.helpers', 'app.helpers.task',
                 'app.helpers.scope', 'app.services', 'app.services.syncAsset', 'app.services.task_scope_sync',
                 'app.celerytask', 'app.modules', 'app.utils.monitor_diff']
        modules = {name: module(name) for name in names}
        self.patch = patch.dict(sys.modules, modules)
        self.patch.start()
        self.addCleanup(self.patch.stop)
        self.utils = modules['app.utils']
        self.utils.conn_db = self.db.__getitem__
        self.utils.get_logger = lambda: self.logger
        self.utils.curr_date = lambda: '2026-10-12 12:00:00'
        self.utils.curr_date_obj = lambda: datetime(2026, 10, 12, 12)
        self.utils.truncate_string = lambda value: value[:200]
        self.utils.message_push = lambda **kwargs: self.pushes.append(kwargs)
        self.utils.build_ret = lambda error, data: dict(error if isinstance(error, dict) else {'code': 400, 'message': error}, data=data)
        modules['app'].utils = self.utils
        modules['app'].services = modules['app.services']
        modules['app'].celerytask = modules['app.celerytask']
        modules['app.celerytask'].arl_task = self.queue
        modules['app.utils.monitor_diff'].log_monitor_diff_summary = lambda task_id: None
        modules['app.utils.security_policy'].get_security_policy = lambda: (['198.51.100.0/24'], ['gov.cn'])
        ip_spec = importlib.util.spec_from_file_location('fixture_ipy', ROOT / 'app/utils/IPy.py')
        ipy = importlib.util.module_from_spec(ip_spec)
        ip_spec.loader.exec_module(ipy)
        domain_env = dict(__name__='app.utils.domain', __package__='app.utils', re=re, tld=tld, blackdomain_list=['blocked.example.com'], blackhexie_list=[])
        ip_env = dict(__name__='app.utils.ip', __package__='app.utils', re=re, IP=ipy.IP)
        load_nodes('app/utils/domain.py', domain_env, ['is_valid_domain', 'is_valid_fuzz_domain', 'is_in_scope', 'is_in_scopes', 'check_domain_black', 'is_forbidden_domain'])
        load_nodes('app/utils/ip.py', ip_env, ['is_vaild_ip_target', 'ip_in_scope', 'not_in_black_ips'])
        parse_env = dict(get_tld=tld.get_tld)
        load_nodes('app/utils/__init__.py', parse_env, ['domain_parsed', 'get_fld'])
        self.utils.domain_parsed = parse_env['domain_parsed']
        self.utils.get_fld = parse_env['get_fld']
        self.utils.domain = types.SimpleNamespace(is_forbidden_domain=domain_env['is_forbidden_domain'])
        for name in ['is_valid_domain', 'is_valid_fuzz_domain', 'is_in_scopes', 'check_domain_black']:
            setattr(self.utils, name, domain_env[name])
        self.utils.is_vaild_ip_target = ip_env['is_vaild_ip_target']
        self.utils.not_in_black_ips = ip_env['not_in_black_ips']
        constants = modules['app.modules'].__dict__
        load_nodes('app/modules/__init__.py', constants, ['TaskStatus', 'TaskTag', 'TaskType', 'SchedulerStatus', 'TaskSyncStatus', 'ScopeValidationError', 'CeleryAction', 'CeleryRoutingKey'])
        constants = {key: value for key, value in constants.items() if not key.startswith('__')}
        # fixture 通过 AST 独立加载 app.modules，异常类对象与模块级 import 不同源；
        # 统一挂到实例上供断言取用，确保 assertRaises 捕获的是同源类型。
        self.ScopeValidationError = constants['ScopeValidationError']
        task_env = modules['app.helpers.task'].__dict__
        task_env.update(constants, utils=self.utils, bson=bson, re=re, logger=self.logger)
        load_nodes('app/helpers/task.py', task_env, ['target2list', 'get_ip_domain_list', 'build_task_data', 'submit_task', 'submit_task_task', 'get_task_data', 'restart_task'])
        scope_env = modules['app.helpers.scope'].__dict__
        scope_env.update(constants, bson=bson, utils=self.utils, ip_in_scope=ip_env['ip_in_scope'], is_in_scopes=domain_env['is_in_scopes'])
        load_nodes('app/helpers/scope.py', scope_env, ['check_target_in_scope', 'validate_task_scope', 'get_scope_by_scope_id', 'update_scope_domain_status'])
        helpers = modules['app.helpers']
        helpers.get_ip_domain_list = task_env['get_ip_domain_list']
        helpers.update_scope_domain_status = scope_env['update_scope_domain_status']
        sync_env = modules['app.services.syncAsset'].__dict__
        sync_env.update(copy=copy, re=re, ObjectId=ObjectId, utils=self.utils, conn=self.db.__getitem__, logger=self.logger)
        load_nodes('app/services/syncAsset.py', sync_env, ['SyncAsset', 'sync_asset'])
        modules['app.services'].sync_asset = sync_env['sync_asset']
        guarded_env = modules['app.services.task_scope_sync'].__dict__
        guarded_env.update(constants, ObjectId=ObjectId, utils=self.utils, validate_task_scope=scope_env['validate_task_scope'])
        load_nodes('app/services/task_scope_sync.py', guarded_env, ['sync_task_to_scope'])
        common_env = dict(utils=self.utils, services=modules['app.services'], ObjectId=ObjectId, logger=self.logger, contextmanager=contextmanager)
        load_nodes('app/services/commonTask.py', common_env, ['CommonTask'])
        self.common_cls = common_env['CommonTask']
        self.submit = task_env['submit_task_task']
        self.restart = task_env['restart_task']
        self.validate = scope_env['validate_task_scope']
        self.sync = guarded_env['sync_task_to_scope']
        self.core_sync_module = modules['app.services.syncAsset']
        load_nodes('app/celerytask.py', modules['app.celerytask'].__dict__, ['domain_task_sync'])
        self.run_sync_worker = modules['app.celerytask'].domain_task_sync
        self.constants = constants
        self.scope_id = self.db.asset_scope.insert_one({'name': 'fixture group', 'domain_array': ['example.com'], 'ip_array': ['192.0.2.0/24']}).inserted_id

    def create(self, target='www.example.com', linked=True):
        options = {'port_scan': False, 'nuclei_scan': False, 'file_leak_dict': 'fixture-dict'}
        if linked:
            options['related_scope_id'] = str(self.scope_id)
        return self.submit(target, 'fixture scan', options)

    def stored(self, data):
        return self.db.task.find_one({'_id': ObjectId(data['task_id'])})

    def add_results(self, task_id):
        self.db.domain.insert_one({'task_id': task_id, 'domain': 'www.example.com', 'source': 'fixture'})
        self.db.ip.insert_one({'task_id': task_id, 'ip': '192.0.2.1', 'port_info': []})
        self.db.site.insert_one({'task_id': task_id, 'site': 'https://www.example.com', 'status': 200, 'title': 'fixture'})
        self.db.url.insert_one({'task_id': task_id, 'url': 'https://www.example.com/path'})


class ScopeSubmissionTests(ScopeFixture):
    def test_linked_mixed_targets_use_regular_queue_and_preserve_options(self):
        items = self.create('www.example.com\n192.0.2.1')
        self.assertEqual({item['type'] for item in items}, {'domain', 'ip'})
        self.assertEqual(len(self.queue.calls), 2)
        for item in items:
            self.assertEqual(item['task_tag'], 'task')
            self.assertNotIn('scope_id', item['options'])
            self.assertEqual(item['options']['related_scope_id'], str(self.scope_id))
            self.assertEqual(item['options']['file_leak_dict'], 'fixture-dict')
            stored = self.stored(item)
            self.assertEqual(stored['sync_status'], 'default')
            self.assertNotIn('synced_scope_id', stored)
        actions = {call['kwargs']['options']['celery_action'] for call in self.queue.calls}
        self.assertEqual(actions, {'domain_task', 'ip_task'})

    def test_batch_has_no_side_effect_when_any_target_is_outside_group(self):
        for target in ('www.example.com evil-example.com', '192.0.2.1 192.0.3.1', 'www.example.com 192.0.3.0/24'):
            with self.subTest(target=target), self.assertRaises(Exception):
                self.create(target)
        self.assertEqual(self.db.task.count_documents({}), 0)
        self.assertEqual(self.queue.calls, [])

    def test_scope_id_missing_or_malformed_rejects_without_creating(self):
        for scope_id in ('bad', str(ObjectId()), ' '):
            with self.assertRaises(self.ScopeValidationError) as ctx:
                self.submit('www.example.com', 'fixture', {'related_scope_id': scope_id})
            self.assertEqual(ctx.exception.reason, 'invalid')
        self.assertEqual(self.db.task.count_documents({}), 0)
        self.assertEqual(self.queue.calls, [])

    def test_single_ip_and_subnet_must_be_fully_contained(self):
        self.validate('192.0.2.1 192.0.2.128/25', str(self.scope_id))
        for target in ('192.0.2.0/23', '192.0.3.1'):
            with self.assertRaises(self.ScopeValidationError) as ctx:
                self.validate(target, str(self.scope_id))
            self.assertEqual(ctx.exception.reason, 'out_of_scope')

    def test_legacy_domain_and_ip_scope_formats(self):
        for st, scopes, target in [('domain', ['example.com'], 'www.example.com'), ('ip', ['192.0.2.0/24'], '192.0.2.1')]:
            identifier = self.db.asset_scope.insert_one({'scope_type': st, 'scope_array': scopes}).inserted_id
            self.validate(target, str(identifier))

    def test_explicit_domain_array_is_kept_if_other_array_missing(self):
        identifier = self.db.asset_scope.insert_one({'domain_array': ['example.com']}).inserted_id
        self.validate('www.example.com', str(identifier))

    def test_blacklist_remains_effective(self):
        for target in ('blocked.example.com', '198.51.100.1', 'a.gov.cn'):
            with self.assertRaises(Exception):
                self.create(target)
        self.assertEqual(self.queue.calls, [])

    def test_empty_target_and_uppercase_id_handling(self):
        with self.assertRaises(self.ScopeValidationError) as ctx:
            self.validate('   ', str(self.scope_id))
        self.assertEqual(ctx.exception.reason, 'empty')
        item = self.submit('www.example.com', 'fixture', {'related_scope_id': str(self.scope_id).upper()})[0]
        self.assertEqual(item['options']['related_scope_id'], str(self.scope_id))

    def test_no_group_preserves_original_scan_submission(self):
        item = self.create('outside.org', linked=False)[0]
        self.assertNotIn('related_scope_name', self.stored(item))
        self.assertNotIn('sync_status', self.stored(item))

    def test_restart_keeps_group_but_clears_old_sync_outcome(self):
        item = self.create()[0]
        old_id = ObjectId(item['task_id'])
        self.db.task.update_one({'_id': old_id}, {'$set': {'status': 'done', 'sync_status': 'error', 'sync_error': 'old',
            'synced_scope_id': str(self.scope_id), 'sync_scope_id': str(self.scope_id),
            'sync_summary': {'total_new': 3, 'total_update': 1}, 'phase_errors': {'alt_dns': 'timeout'}}})
        restarted = self.restart(item['task_id'])
        self.assertNotEqual(restarted['task_id'], item['task_id'])
        fresh = self.stored(restarted)
        self.assertEqual(fresh['options']['related_scope_id'], str(self.scope_id))
        self.assertEqual(fresh['sync_status'], 'default')
        self.assertNotIn('sync_error', fresh)
        self.assertNotIn('synced_scope_id', fresh)
        self.assertNotIn('sync_summary', fresh)
        self.assertNotIn('phase_errors', fresh)
        self.assertEqual(self.db.task.find_one({'_id': old_id})['sync_error'], 'old')

    def test_restart_revalidates_deleted_or_changed_group_before_dispatch(self):
        item = self.create()[0]
        self.db.asset_scope.update_one({'_id': self.scope_id}, {'$set': {'domain_array': ['other.org']}})
        with self.assertRaises(Exception):
            self.restart(item['task_id'])
        self.db.asset_scope.delete_one({'_id': self.scope_id})
        with self.assertRaises(self.ScopeValidationError) as ctx:
            self.restart(item['task_id'])
        self.assertEqual(ctx.exception.reason, 'invalid')
        self.assertEqual(self.db.task.count_documents({}), 1)
        self.assertEqual(len(self.queue.calls), 1)


class ScopeSyncTests(ScopeFixture):
    def test_original_sync_pipeline_copies_assets_and_records_success(self):
        item = self.create()[0]
        self.add_results(item['task_id'])
        self.assertTrue(self.sync(item['task_id'], str(self.scope_id)))
        task = self.stored(item)
        self.assertEqual(task['sync_status'], 'default')
        self.assertEqual(task['synced_scope_id'], str(self.scope_id))
        for category in ('domain', 'ip', 'site', 'url'):
            self.assertEqual(self.db['asset_' + category].count_documents({'scope_id': str(self.scope_id)}), 1)
            self.assertEqual(self.db[category].count_documents({'task_id': item['task_id']}), 1)
        self.assertFalse(self.pushes)

    def test_repeated_sync_deduplicates_in_selected_group_and_preserves_other_group(self):
        item = self.create()[0]
        self.add_results(item['task_id'])
        self.db.asset_site.insert_one({'scope_id': 'other-group', 'site': 'https://www.example.com', 'title': 'other'})
        with patch.object(self.logger, 'error') as logged_errors:
            self.assertTrue(self.sync(item['task_id'], str(self.scope_id)))
            self.assertTrue(self.sync(item['task_id'], str(self.scope_id)))
            logged_errors.assert_not_called()
        self.assertEqual(self.db.asset_site.count_documents({'scope_id': str(self.scope_id)}), 1)
        self.assertEqual(self.db.asset_site.find_one({'scope_id': 'other-group'})['title'], 'other')

    def test_common_scan_completion_calls_guarded_sync(self):
        item = self.create()[0]
        self.add_results(item['task_id'])
        common = self.common_cls(item['task_id'])
        common.options = item['options']
        common.sync_asset()
        self.assertEqual(self.stored(item)['synced_scope_id'], str(self.scope_id))
        self.assertEqual(len(self.pushes), 1)

    def test_asset_site_monitor_and_risk_tasks_keep_existing_sync_hooks(self):
        for task_type, tag, target in [('asset_site_add', 'task', ['https://www.example.com']), ('domain', 'monitor', 'www.example.com'), ('risk_cruising', 'risk_cruising', '巡航结果')]:
            identifier = self.db.task.insert_one({'type': task_type, 'task_tag': tag, 'target': target}).inserted_id
            common = self.common_cls(str(identifier))
            common.options = {'related_scope_id': str(self.scope_id)}
            with patch.object(sys.modules['app.services'], 'sync_asset') as legacy, patch.object(sys.modules['app.services.task_scope_sync'], 'sync_task_to_scope') as guarded:
                common.sync_asset()
                legacy.assert_called_once_with(task_id=str(identifier), scope_id=str(self.scope_id), push_flag=True)
                guarded.assert_not_called()

    def test_unassociated_common_completion_only_pushes_original_results(self):
        item = self.create(linked=False)[0]
        self.add_results(item['task_id'])
        common = self.common_cls(item['task_id'])
        common.options = item['options']
        common.sync_asset()
        self.assertEqual(len(self.pushes), 1)
        self.assertNotIn('sync_status', self.stored(item))
        self.assertEqual(self.db.asset_site.count_documents({}), 0)

    def test_scope_validation_failure_is_reported_without_exception_stack(self):
        """范围校验失败属可控失败：如实记录原因，且不升级为框架级异常上报。"""
        item = self.create()[0]
        self.add_results(item['task_id'])
        self.db.task.update_one({'_id': ObjectId(item['task_id'])}, {'$set': {'status': 'done'}})
        self.db.asset_scope.delete_one({'_id': self.scope_id})
        with patch.object(self.logger, 'exception') as logged_exception, \
                patch.object(self.logger, 'warning') as logged_warning:
            self.assertFalse(self.sync(item['task_id'], str(self.scope_id)))
            logged_exception.assert_not_called()
            logged_warning.assert_called()
        task = self.stored(item)
        self.assertEqual(task['sync_status'], 'error')
        self.assertIn('不存在', task['sync_error'])
        self.assertEqual(self.db.asset_site.count_documents({}), 0)

    def test_out_of_scope_sync_failure_keeps_distinct_reason(self):
        """越界与「资产组不存在」须留下可区分的失败原因，便于用户判断处置方式。"""
        item = self.create()[0]
        self.add_results(item['task_id'])
        self.db.task.update_one({'_id': ObjectId(item['task_id'])}, {'$set': {'status': 'done'}})
        self.db.asset_scope.update_one({'_id': self.scope_id}, {'$set': {'domain_array': ['other.org']}})
        self.assertFalse(self.sync(item['task_id'], str(self.scope_id)))
        task = self.stored(item)
        self.assertEqual(task['sync_status'], 'error')
        self.assertIn('不在范围', task['sync_error'])
        self.assertNotIn('不存在', task['sync_error'])

    def test_group_deleted_before_sync_preserves_scan_results_and_status(self):
        item = self.create()[0]
        self.add_results(item['task_id'])
        self.db.task.update_one({'_id': ObjectId(item['task_id'])}, {'$set': {'status': 'done'}})
        self.db.asset_scope.delete_one({'_id': self.scope_id})
        self.assertFalse(self.sync(item['task_id'], str(self.scope_id)))
        task = self.stored(item)
        self.assertEqual(task['status'], 'done')
        self.assertEqual(task['sync_status'], 'error')
        self.assertIn('不存在', task['sync_error'])
        self.assertEqual(self.db.site.count_documents({}), 1)
        self.assertEqual(self.db.asset_site.count_documents({}), 0)

    def test_group_changed_before_sync_is_rejected(self):
        item = self.create()[0]
        self.add_results(item['task_id'])
        self.db.asset_scope.update_one({'_id': self.scope_id}, {'$set': {'domain_array': ['other.org']}})
        self.assertFalse(self.sync(item['task_id'], str(self.scope_id)))
        self.assertEqual(self.db.asset_site.count_documents({}), 0)

    def test_sync_failure_and_manual_retry_clear_error_after_success(self):
        item = self.create()[0]
        self.add_results(item['task_id'])
        self.db.task.update_one({'_id': ObjectId(item['task_id'])}, {'$set': {'sync_summary': {'total_new': 2, 'total_update': 1}}})
        with patch.object(self.core_sync_module, 'sync_asset', side_effect=RuntimeError('fixture database failure')):
            self.assertFalse(self.sync(item['task_id'], str(self.scope_id)))
        self.assertEqual(self.stored(item)['sync_error'], 'fixture database failure')
        self.assertNotIn('sync_summary', self.stored(item))
        self.assertTrue(self.sync(item['task_id'], str(self.scope_id)))
        self.assertNotIn('sync_error', self.stored(item))
        self.assertEqual(self.db.asset_site.count_documents({}), 1)

    def test_missing_task_does_not_create_assets(self):
        self.assertFalse(self.sync(str(ObjectId()), str(self.scope_id)))
        self.assertEqual(self.db.task.count_documents({}), 0)


class HTTPTests(ScopeFixture):
    def setUp(self):
        super().setUp()
        self.app = Flask(__name__)
        api = Api(self.app, prefix='/api')
        env = dict(Resource=Resource, reqparse=reqparse, fields=fields)
        load_nodes('app/routes/__init__.py', env, ['ARLResource'])
        auth_env = dict(functools=functools, Config=types.SimpleNamespace(AUTH=True), user_login_header=lambda: request.headers.get('Token') == 'fixture-token')
        load_nodes('app/utils/user.py', auth_env, ['auth'])
        errors = types.SimpleNamespace(**{name: {'code': code} for code, name in enumerate([
            'Success', 'Error', 'TaskTargetIsEmpty', 'NotFoundTask', 'TaskTargetNotInScope', 'TaskIsRunning', 'TaskSyncDealing',
            'NotFoundScopeID'], 200)})
        errors.Success = {'code': 200}
        env.update(ns=Namespace('task'), auth=auth_env['auth'], utils=self.utils, ObjectId=ObjectId,
                   conn=self.db.__getitem__, celerytask=types.SimpleNamespace(arl_task=self.queue), logger=self.logger,
                   ErrorMsg=errors, submit_task_task=self.submit, **self.constants)
        load_nodes('app/routes/task.py', env, ['add_task_fields', 'sync_task_fields'])
        tree = ast.parse((ROOT / 'app/routes/task.py').read_text())
        for cls in tree.body:
            if isinstance(cls, ast.ClassDef) and cls.name in ('ARLTask', 'SyncTask'):
                cls = copy.deepcopy(cls)
                cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == 'post']
                exec(compile(ast.fix_missing_locations(ast.Module(body=[cls], type_ignores=[])), 'app/routes/task.py', 'exec'), env)
        api.add_namespace(env['ns'])
        self.client = self.app.test_client()
        self.headers = {'Token': 'fixture-token'}

    def post(self, path, payload):
        return self.client.post('/api/task/' + path, json=payload, headers=self.headers).get_json()

    def test_create_endpoint_parses_optional_group_and_returns_regular_tasks(self):
        result = self.post('', {'name': 'fixture', 'target': 'www.example.com\n192.0.2.1', 'related_scope_id': str(self.scope_id)})
        self.assertEqual(result['code'], 200)
        self.assertEqual(len(result['items']), 2)
        self.assertTrue(all(item['options']['related_scope_id'] == str(self.scope_id) for item in result['items']))

    def test_invalid_batch_returns_specific_error_without_dispatch(self):
        result = self.post('', {'name': 'fixture', 'target': 'www.example.com\noutside.org', 'related_scope_id': str(self.scope_id)})
        self.assertNotEqual(result['code'], 200)
        self.assertIn('outside.org', result['data']['error'])
        self.assertFalse(self.queue.calls)

    def test_legacy_create_without_group_and_authentication(self):
        self.assertEqual(self.post('', {'name': 'fixture', 'target': 'outside.org'})['code'], 200)
        self.assertEqual(self.client.post('/api/task/', json={'name': 'fixture', 'target': 'outside.org'}).get_json()['code'], 401)

    def test_ip_manual_sync_and_fast_worker_keep_completed_state(self):
        item = self.create('192.0.2.1')[0]
        self.add_results(item['task_id'])
        self.db.task.update_one({'_id': ObjectId(item['task_id'])}, {'$set': {'status': 'done'}})
        self.queue.worker = self.run_sync_worker
        result = self.post('sync/', {'task_id': item['task_id'], 'scope_id': str(self.scope_id)})
        self.assertEqual(result['code'], 200)
        self.assertEqual(self.stored(item)['sync_status'], 'default')
        self.assertEqual(self.stored(item)['synced_scope_id'], str(self.scope_id))

    def test_busy_and_nonterminal_manual_sync_do_not_enqueue(self):
        item = self.create()[0]
        payload = {'task_id': item['task_id'], 'scope_id': str(self.scope_id)}
        self.assertNotEqual(self.post('sync/', payload)['code'], 200)
        self.db.task.update_one({'_id': ObjectId(item['task_id'])}, {'$set': {'status': 'done', 'sync_status': 'running'}})
        self.assertNotEqual(self.post('sync/', payload)['code'], 200)
        self.assertEqual(len(self.queue.calls), 1)

    def test_waiting_sync_is_claimed_only_once(self):
        item = self.create()[0]
        self.db.task.update_one({'_id': ObjectId(item['task_id'])}, {'$set': {'status': 'done'}})
        payload = {'task_id': item['task_id'], 'scope_id': str(self.scope_id)}
        self.assertEqual(self.post('sync/', payload)['code'], 200)
        self.assertNotEqual(self.post('sync/', payload)['code'], 200)
        self.assertEqual(len(self.queue.calls), 2)

    def test_invalid_sync_ids_do_not_dispatch(self):
        item = self.create()[0]
        self.db.task.update_one({'_id': ObjectId(item['task_id'])}, {'$set': {'status': 'done'}})
        for payload in ({'task_id': 'bad', 'scope_id': str(self.scope_id)}, {'task_id': item['task_id'], 'scope_id': 'bad'}):
            self.assertNotEqual(self.post('sync/', payload)['code'], 200)
        self.assertEqual(len(self.queue.calls), 1)

    def test_manual_sync_dispatch_failure_is_visible_without_losing_results(self):
        item = self.create()[0]
        self.add_results(item['task_id'])
        self.db.task.update_one({'_id': ObjectId(item['task_id'])}, {'$set': {'status': 'done'}})
        self.queue.error = RuntimeError('fixture queue unavailable')
        result = self.post('sync/', {'task_id': item['task_id'], 'scope_id': str(self.scope_id)})
        self.assertNotEqual(result['code'], 200)
        self.assertEqual(self.stored(item)['sync_status'], 'error')
        self.assertEqual(self.db.site.count_documents({}), 1)

    def test_resync_clears_stale_sync_summary_on_claim_and_dispatch_failure(self):
        item = self.create()[0]
        self.add_results(item['task_id'])
        self.db.task.update_one({'_id': ObjectId(item['task_id'])}, {'$set': {
            'status': 'done',
            'sync_status': 'default',
            'sync_summary': {'total_new': 5, 'total_update': 2},
        }})
        result = self.post('sync/', {'task_id': item['task_id'], 'scope_id': str(self.scope_id)})
        self.assertEqual(result['code'], 200)
        claimed = self.stored(item)
        self.assertEqual(claimed['sync_status'], 'waiting')
        self.assertNotIn('sync_summary', claimed)

        self.db.task.update_one({'_id': ObjectId(item['task_id'])}, {'$set': {
            'sync_status': 'default',
            'sync_summary': {'total_new': 4, 'total_update': 1},
        }})
        self.queue.error = RuntimeError('fixture queue unavailable')
        failed = self.post('sync/', {'task_id': item['task_id'], 'scope_id': str(self.scope_id)})
        self.assertNotEqual(failed['code'], 200)
        errored = self.stored(item)
        self.assertEqual(errored['sync_status'], 'error')
        self.assertNotIn('sync_summary', errored)


if __name__ == '__main__':
    unittest.main()
