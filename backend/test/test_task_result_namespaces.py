"""原路由、请求解析及查询/导出配合 Flask 客户端和 mongomock。

AST 加载隔离应用初始化，认证使用原装饰器及受控凭据，不连接真实服务。
"""
import ast
import functools
from pathlib import Path
import types
import unittest

from bson import ObjectId
from flask import Flask, request
from flask_restx import Api, Namespace
import mongomock

from test_http_status_filter import assigned, execute_nodes, load_base


ROOT = Path(__file__).resolve().parents[1]


class TaskResultTests(unittest.TestCase):
    def setUp(self):
        self.db = mongomock.MongoClient().arl
        self.app = Flask(__name__)
        api = Api(self.app, prefix='/api')
        env = load_base(self.db.__getitem__)
        auth_env = dict(functools=functools, Config=types.SimpleNamespace(AUTH=True),
                        user_login_header=lambda: request.headers.get('Token') == 'fixture-token')
        execute_nodes(ROOT / 'app/utils/user.py', auth_env,
                      lambda n: isinstance(n, ast.FunctionDef) and n.name == 'auth')
        env.update(auth=auth_env['auth'], utils=types.SimpleNamespace(
            conn_db=self.db.__getitem__, build_ret=lambda error, data: dict(error, data=data)),
            ErrorMsg=types.SimpleNamespace(Success={'code': 200}))
        for filename, namespace in [('url.py', 'url'), ('cip.py', 'cip'), ('stat_finger.py', 'stat_finger')]:
            env['ns'] = Namespace(namespace)
            execute_nodes(ROOT / 'app/routes' / filename, env, lambda n:
                          assigned(n, ('base_search_fields', 'delete_result_fields')) or
                          isinstance(n, ast.ClassDef) or
                          isinstance(n, ast.Expr) and isinstance(n.value, ast.Call) and
                          isinstance(n.value.func, ast.Attribute) and
                          isinstance(n.value.func.value, ast.Name) and n.value.func.value.id == 'base_search_fields')
            api.add_namespace(env['ns'])
        self.client = self.app.test_client()
        self.headers = {'Token': 'fixture-token'}
        self.ids = {}
        for collection, field in [('url', 'url'), ('cip', 'cidr_ip'), ('stat_finger', 'name')]:
            self.ids[collection] = []
            for task in ('task-a', 'task-b'):
                record_id = ObjectId()
                self.ids[collection].append(record_id)
                record = dict(_id=record_id, task_id=task, ip_count=1, domain_count=2, cnt=3,
                              **{field: f'https://{task}.example/path' if field == 'url' else f'{task}-value'})
                self.db[collection].insert_one(record)
                # 相同 ID 的资产组归档用于发现误删集合，站点同样保留。
                self.db['asset_' + collection].insert_one(dict(record, scope_id='group-a'))
                self.db.site.insert_one(dict(record, _id=ObjectId(), site=f'https://{task}.example'))

    def get(self, path, **params):
        return self.client.get('/api/' + path, query_string={'page': 1, 'size': 10, **params}, headers=self.headers)

    def delete(self, collection, ids, headers=None):
        return self.client.post('/api/' + collection + '/delete/', json={'_id': ids},
                                headers=self.headers if headers is None else headers)

    def test_each_list_remains_scoped_to_the_requested_task(self):
        for collection, field in [('url', 'url'), ('cip', 'cidr_ip'), ('stat_finger', 'name')]:
            with self.subTest(collection=collection):
                body = self.get(collection + '/', task_id='task-a').get_json()
                self.assertEqual(body['code'], 200)
                self.assertEqual(body['total'], 1)
                self.assertEqual(len(body['items']), 1)
                self.assertIn('task-a', body['items'][0][field])

    def test_url_and_cidr_list_export_share_task_and_filter(self):
        for collection, field in [('url', 'url'), ('cip', 'cidr_ip')]:
            with self.subTest(collection=collection):
                params = {'task_id': 'task-a', field: 'task-a'}
                listed = self.get(collection + '/', **params).get_json()['items']
                exported = self.get(collection + '/export/', **params)
                self.assertEqual(exported.status_code, 200)
                self.assertEqual(set(exported.get_data(as_text=True).splitlines()), {r[field] for r in listed})

    def test_url_multiselect_filter_matches_export(self):
        self.db.url.update_one({'_id': self.ids['url'][0]}, {'$set': {'status_code': 403}})
        self.db.url.insert_one({'task_id': 'task-a', 'url': 'https://excluded.example', 'status_code': 404})
        params = {'task_id': 'task-a', 'status_code__in': '200,403'}
        listed = self.get('url/', **params).get_json()['items']
        self.assertEqual(len(listed), 1)
        self.assertEqual(self.get('url/export/', **params).get_data(as_text=True).splitlines(), [listed[0]['url']])

    def test_global_url_list_uses_task_results_and_never_archived_only_records(self):
        self.db.asset_url.insert_one({'scope_id': 'group-b', 'url': 'https://archive-only.example'})
        body = self.get('url/').get_json()
        self.assertEqual(body['total'], 2)
        self.assertNotIn('https://archive-only.example', {r['url'] for r in body['items']})

    def test_delete_removes_selected_task_result_and_preserves_other_collections(self):
        for collection in ('url', 'cip'):
            with self.subTest(collection=collection):
                first, second = self.ids[collection]
                response = self.delete(collection, [str(first)]).get_json()
                self.assertEqual(response['code'], 200)
                self.assertEqual(response['data']['deleted_count'], 1)
                self.assertIsNone(self.db[collection].find_one({'_id': first}))
                self.assertIsNotNone(self.db[collection].find_one({'_id': second}))
                self.assertEqual(self.db['asset_' + collection].count_documents({}), 2)
                self.assertEqual(self.db.site.count_documents({}), 6)

    def test_delete_validates_entire_batch_before_any_mutation(self):
        for collection in ('url', 'cip'):
            first = str(self.ids[collection][0])
            for ids in ([], [first, 'invalid'], [first, ''], ['invalid', first]):
                with self.subTest(collection=collection, ids=ids):
                    response = self.delete(collection, ids).get_json()
                    self.assertEqual(response['code'], 999)
                    self.assertEqual(self.db[collection].count_documents({}), 2)

    def test_delete_requires_authentication_and_id_list(self):
        for collection in ('url', 'cip'):
            with self.subTest(collection=collection):
                ids = [str(self.ids[collection][0])]
                self.assertEqual(self.delete(collection, ids, headers={}).get_json()['code'], 401)
                self.assertEqual(self.client.post('/api/' + collection + '/delete/', json={},
                                                 headers=self.headers).status_code, 400)
                self.assertEqual(self.db[collection].count_documents({}), 2)

    def test_delete_is_idempotent_and_counts_unique_existing_ids(self):
        for collection in ('url', 'cip'):
            with self.subTest(collection=collection):
                existing = str(self.ids[collection][0])
                ids = [existing, existing, str(ObjectId())]
                self.assertEqual(self.delete(collection, ids).get_json()['data']['deleted_count'], 1)
                self.assertEqual(self.delete(collection, ids).get_json()['data']['deleted_count'], 0)

    def test_delete_rejects_non_array_or_non_string_ids_without_mutation(self):
        for collection in ('url', 'cip'):
            existing = str(self.ids[collection][0])
            for ids in (existing, {existing: True}, [123], [existing, None]):
                with self.subTest(collection=collection, ids=ids):
                    response = self.delete(collection, ids)
                    self.assertEqual(response.status_code, 400)
                    self.assertEqual(self.db[collection].count_documents({}), 2)

    def test_fingerprint_statistics_preserve_aggregation_and_exact_name_filter(self):
        self.db.stat_finger.insert_one({'task_id': 'task-a', 'name': 'task-a-value', 'cnt': 4})
        body = self.get('stat_finger/', task_id='task-a', name__eq='task-a-value').get_json()
        self.assertEqual(body['total'], 1)
        self.assertEqual(body['items'][0]['cnt'], 7)
        self.assertNotIn('_id', body['items'][0])
        self.assertEqual(self.client.post('/api/stat_finger/delete/', json={}, headers=self.headers).status_code, 404)


if __name__ == '__main__':
    unittest.main()
