"""真实路由、解析器和查询方法配合 Flask 客户端及内存 MongoDB。

通过 AST 加载原方法，避免导入完整应用时连接配置库和扫描组件。
没有替代请求解析、查询转换、列表、导出或结果集实现。
"""
import ast
import copy
from datetime import datetime
import functools
from pathlib import Path
import re
import time
import types
import unittest
from urllib.parse import quote, urlsplit, urlunsplit

from bson import ObjectId
from flask import Flask, has_request_context, make_response, request
from flask_restx import Api, Namespace, Resource, fields, reqparse
import mongomock

ROOT = Path(__file__).resolve().parents[1]
ROUTES = [
    ('site.py', 'site', 'status', ['ARLSite', 'ARLSiteExport', 'ARLSaveResultSet']),
    ('assetSite.py', 'asset_site', 'status', ['ARLAssetSite', 'ARLSiteExport', 'ARLSaveResultSet']),
    ('url.py', 'url', 'status_code', ['ARLUrl', 'ARLUrlExport']),
    ('assetUrl.py', 'asset_url', 'status_code', ['ARLAssetUrl', 'ARLAssetUrlExport']),
    ('fileleak.py', 'fileleak', 'status_code', ['ARLFileLeak']),
    ('assetFileleak.py', 'asset_fileleak', 'status_code', ['ARLAssetFileleak', 'ARLAssetFileleakExport']),
]


def execute_nodes(path, env, select):
    nodes = [copy.deepcopy(n) for n in ast.parse(path.read_text()).body if select(n)]
    exec(compile(ast.fix_missing_locations(ast.Module(body=nodes, type_ignores=[])), str(path), 'exec'), env)


def assigned(node, names):
    return isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id in names for t in node.targets)


def load_base(conn):
    env = dict(Resource=Resource, fields=fields, reqparse=reqparse, re=re, json=__import__('json'),
               ObjectId=ObjectId, copy=copy, datetime=datetime, quote=quote, time=time, make_response=make_response, conn=conn)
    execute_nodes(ROOT / 'app/utils/wih_export.py', env, lambda n: isinstance(n, ast.FunctionDef))
    execute_nodes(ROOT / 'app/routes/__init__.py', env,
                  lambda n: assigned(n, ('base_query_fields', 'EQUAL_FIELDS')) or
                  isinstance(n, ast.ClassDef) and n.name == 'ARLResource' or
                  isinstance(n, ast.FunctionDef) and n.name == 'get_arl_parser')
    execute_nodes(ROOT / 'app/routes/http_status.py', env,
                  lambda n: isinstance(n, (ast.ClassDef, ast.FunctionDef)))
    env.update(request=request, has_request_context=has_request_context)
    return env


class StatusQueryTests(unittest.TestCase):
    def setUp(self):
        self.env = load_base(lambda name: None)
        self.resource = self.env['HttpStatusResource']()

    def test_codes_are_deduplicated_and_sorted(self):
        self.assertEqual(self.env['parse_http_status_codes']('403, 200,200,599,100'), [100, 200, 403, 599])

    def test_invalid_codes_are_rejected(self):
        for value in ('', ' ', '200,', ',200', '99', '600', '200.0', '2e2', '２００', '{"$ne":200}', '200,abc', None, ['200']):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.env['parse_http_status_codes'](value)

    def test_request_size_is_bounded(self):
        for value in ('200,' * 501, ' ' * 2001):
            with self.assertRaises(ValueError):
                self.env['parse_http_status_codes'](value)
        self.assertEqual(len(self.env['parse_http_status_codes'](','.join(map(str, range(100, 600))))), 500)

    def test_status_membership_keeps_other_filters(self):
        query = self.resource.build_db_query({'status__in': [200, 403], 'task_id': 'task-a', 'title': 'admin'})
        self.assertEqual(query['status'], {'$in': [200, 403]})
        self.assertEqual(query['task_id'], 'task-a')
        self.assertEqual(query['title'], {'$regex': 'admin', '$options': 'i'})
        self.assertNotIn('status__in', query)

    def test_legacy_single_value_and_task_status_are_unchanged(self):
        self.assertEqual(self.resource.build_db_query({'status': 200}), {'status': 200})
        self.assertEqual(self.env['ARLResource']().build_db_query({'status': 'running'}), {'status': 'running'})

    def test_legacy_and_multiple_conditions_intersect_in_any_order(self):
        for args in ({'status': 404, 'status__in': [200, 403]}, {'status__in': [200, 403], 'status': 404}):
            self.assertEqual(self.resource.build_db_query(args), {'status': {'$eq': 404, '$in': [200, 403]}})


class HTTPStatusTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().arl
        self.app = Flask(__name__)
        api = Api(self.app, prefix='/api')
        self.env = load_base(self.db.__getitem__)
        auth_env = dict(functools=functools, Config=types.SimpleNamespace(AUTH=True),
                        user_login_header=lambda: request.headers.get('Token') == 'fixture-token')
        execute_nodes(ROOT / 'app/utils/user.py', auth_env,
                      lambda n: isinstance(n, ast.FunctionDef) and n.name == 'auth')
        # 这些无关组件只用于包装返回值和裁剪结果集路径。
        def cut_filename(url):
            parsed = urlsplit(url)
            return urlunsplit((parsed.scheme, parsed.netloc, '', '', ''))
        utils = types.SimpleNamespace(conn_db=self.db.__getitem__, url=types.SimpleNamespace(cut_filename=cut_filename),
                                     build_ret=lambda error, data: dict(error, data=data))
        for filename, namespace, status_field, class_names in ROUTES:
            self.db[namespace].insert_many([
                dict(site=f'https://{i}.fixture.test', url=f'https://{i}.fixture.test/path',
                     title='admin' if i < 4 else 'other', task_id='task-a' if i != 3 else 'task-b',
                     scope_id='scope-a' if i != 3 else 'scope-b', update_date=datetime(2026, 10, i + 1), **{status_field: code})
                for i, code in enumerate([200, 403, 404, 200, 403])
            ])
            env = dict(self.env, ns=Namespace(namespace), auth=auth_env['auth'], utils=utils,
                       ErrorMsg=types.SimpleNamespace(Success={'code': 200}, QueryResultIsEmpty={'code': 400}))
            path = ROOT / 'app/routes' / filename
            execute_nodes(path, env, lambda n: assigned(n, ('base_search_fields', 'site_search_fields')) or
                          isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and
                          isinstance(n.value.func, ast.Attribute) and
                          isinstance(n.value.func.value, ast.Name) and n.value.func.value.id == 'base_search_fields')
            for node in ast.parse(path.read_text()).body:
                if isinstance(node, ast.ClassDef) and node.name in class_names:
                    node = copy.deepcopy(node)
                    node.body = [n for n in node.body if not isinstance(n, ast.FunctionDef) or n.name == 'get' or n.name.startswith('_')]
                    exec(compile(ast.fix_missing_locations(ast.Module(body=[node], type_ignores=[])), str(path), 'exec'), env)
            api.add_namespace(env['ns'])
        self.client = self.app.test_client()
        self.headers = {'Token': 'fixture-token'}

    def get(self, path, params):
        return self.client.get('/api/' + path, query_string=params, headers=self.headers)

    def test_every_http_asset_list_accepts_multiselect_and_keeps_scope(self):
        for _, namespace, key, _ in ROUTES:
            with self.subTest(namespace=namespace):
                params = {key + '__in': '200,403', 'title': 'admin', 'task_id': 'task-a'}
                if namespace.startswith('asset_'):
                    params['scope_id'] = 'scope-a'
                response = self.get(namespace + '/', params)
                self.assertEqual(response.status_code, 200)
                body = response.get_json()
                self.assertEqual(body['total'], 2)
                self.assertEqual({item[key] for item in body['items']}, {200, 403})

    def test_site_list_export_and_result_set_have_identical_targets(self):
        for namespace in ('site', 'asset_site'):
            params = {'status__in': '403,200', 'title': 'admin', 'task_id': 'task-a'}
            if namespace == 'asset_site':
                params['scope_id'] = 'scope-a'
            listed = self.get(namespace + '/', params).get_json()['items']
            expected = {item['site'] for item in listed}
            exported = self.get(namespace + '/export/', params)
            self.assertEqual(exported.status_code, 200)
            self.assertEqual(set(exported.get_data(as_text=True).splitlines()), expected)
            saved = self.get(namespace + '/save_result_set/', params).get_json()
            result = self.db.result_set.find_one({'_id': ObjectId(saved['data']['result_set_id'])})
            self.assertEqual(set(result['items']), expected)
            self.assertEqual(result['total'], 2)

    def test_url_and_asset_fileleak_exports_use_status_filter(self):
        for namespace in ('url', 'asset_url', 'asset_fileleak'):
            params = {'status_code__in': '200,403', 'task_id': 'task-a', 'title': 'admin'}
            if namespace.startswith('asset_'):
                params['scope_id'] = 'scope-a'
            listed = self.get(namespace + '/', params).get_json()['items']
            exported = self.get(namespace + '/export/', params)
            self.assertEqual(set(exported.get_data(as_text=True).splitlines()), {item['url'] for item in listed})

    def test_invalid_filters_reject_all_operations_without_saving(self):
        for value in ('', '200,', '600', '{"$ne":200}', '200,garbage'):
            for namespace in ('site', 'asset_site'):
                for suffix in ('/', '/export/', '/save_result_set/'):
                    with self.subTest(value=value, path=namespace + suffix):
                        self.assertEqual(self.get(namespace + suffix, {'status__in': value}).status_code, 400)
        self.assertEqual(self.db.result_set.count_documents({}), 0)

    def test_repeated_status_parameter_is_rejected(self):
        response = self.get('site/', [('status__in', '200'), ('status__in', '403')])
        self.assertEqual(response.status_code, 400)

    def test_single_status_and_absent_filter_remain_compatible(self):
        self.assertEqual(self.get('site/', {'status': 404}).get_json()['total'], 1)
        self.assertEqual(self.get('site/', {}).get_json()['total'], 5)
        self.assertEqual(self.get('site/', {'status': 404, 'status__in': '200,403'}).get_json()['total'], 0)

    def test_asset_dates_and_statuses_match_for_list_export_and_result_set(self):
        params = {'scope_id': 'scope-a', 'status__in': '200,403',
                  'update_date__dgt': '2026-10-01 12:00:00', 'update_date__dlt': '2026-10-03 00:00:00'}
        expected = {'https://1.fixture.test'}
        listed = self.get('asset_site/', params).get_json()['items']
        self.assertEqual({item['site'] for item in listed}, expected)
        self.assertEqual(set(self.get('asset_site/export/', params).get_data(as_text=True).splitlines()), expected)
        saved = self.get('asset_site/save_result_set/', params).get_json()
        result = self.db.result_set.find_one({'_id': ObjectId(saved['data']['result_set_id'])})
        self.assertEqual(set(result['items']), expected)

    def test_new_query_routes_remain_authenticated(self):
        for path in ('site/', 'site/export/', 'site/save_result_set/', 'asset_site/', 'url/', 'fileleak/'):
            self.assertEqual(self.client.get('/api/' + path).get_json()['code'], 401)


if __name__ == '__main__':
    unittest.main()
