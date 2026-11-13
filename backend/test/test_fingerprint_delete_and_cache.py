import io
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask
import mongomock
from pymongo.errors import BulkWriteError
from werkzeug.datastructures import FileStorage

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
XING_DIR = os.path.join(BACKEND_DIR, 'ARL-NPoC')
for p in (BACKEND_DIR, XING_DIR):
    if os.path.isdir(p) and p not in sys.path:
        sys.path.insert(0, p)

# 单元测试导入期绕过全局配置与异步日志线程对远端 Mongo 的连接探测
import app.config as app_config
app_config._config_cache["data"] = {}
app_config._config_cache["last_update"] = 9999999999
app_config._read_config_version = lambda: None

from app import utils
utils.MongoSyslogHandler.emit = lambda self, record: None
utils.MongoSyslogHandler._flush_on_exit = classmethod(lambda cls: None)

from app import routes as routes_init
from app.config import Config
from app.routes import fingerprint as fingerprint_route
from app.services import fingerprint_cache
from app.services.fingerprint_cache import FingerPrintCache
from app.utils import arlupdate
from app.utils.conn import SafeCollectionProxy


class _UnackedResult:
    acknowledged = False


class _UnackedWriteWrapper:
    """模拟 SafeCollectionProxy 在吞掉 BulkWriteError 时返回 acknowledged=False。"""

    def __init__(self, real_coll):
        self._real = real_coll

    def bulk_write(self, *args, **kwargs):
        return _UnackedResult()

    def __getattr__(self, name):
        return getattr(self._real, name)


class TestFingerprintDeleteAndCache(unittest.TestCase):
    def setUp(self):
        self.flask_app = Flask(__name__)
        self.client = mongomock.MongoClient()
        self.db = self.client['arl_test']

        self._tmp_dir = tempfile.TemporaryDirectory()
        self.webapp_path = os.path.join(self._tmp_dir.name, 'webapp.json')
        self._write_webapp({
            "Nginx": {"fofa_rule": 'header="nginx"'},
            "Redis": {"fofa_rule": 'body="redis"'},
        })

        self.cache = FingerPrintCache()
        self.patchers = [
            patch.object(Config, 'AUTH', False),
            patch.object(Config, 'web_app_rule', self.webapp_path),
            patch.object(utils, 'conn_db', side_effect=self._conn_db),
            patch.object(routes_init, 'conn', side_effect=self._conn_db),
            patch.object(fingerprint_cache, 'conn_db', side_effect=self._conn_db),
            patch.object(arlupdate, 'conn_db', side_effect=self._conn_db),
            patch.object(fingerprint_cache, 'finger_db_cache', self.cache),
            patch.object(arlupdate, 'finger_db_cache', self.cache, create=True),
        ]
        for p in self.patchers:
            p.start()

    def tearDown(self):
        for p in reversed(self.patchers):
            p.stop()
        self._tmp_dir.cleanup()

    def _conn_db(self, collection, db_name=None):
        return self.db[collection]

    def _write_webapp(self, rules_dict):
        with open(self.webapp_path, 'w', encoding='utf-8') as f:
            json.dump(rules_dict, f, ensure_ascii=False)

    def _delete_ids(self, ids):
        res_cls = fingerprint_route.DeleteARLFinger()
        with self.flask_app.test_request_context(
            '/api/fingerprint/delete/', method='POST', json={'_id': ids}
        ):
            return res_cls.post()

    def test_delete_all_fingerprints_never_reseeds_on_cache_or_restart(self):
        arlupdate.fingerprint_info_update()
        self.assertEqual(self.db['fingerprint'].count_documents({}), 2)

        all_ids = [str(doc['_id']) for doc in self.db['fingerprint'].find({}, {'_id': 1})]
        # 分批删除直至清空
        r1 = self._delete_ids(all_ids[:1])
        self.assertEqual(r1['code'], 200)
        self.assertEqual(self.db['fingerprint'].count_documents({}), 1)

        r2 = self._delete_ids(all_ids[1:])
        self.assertEqual(r2['code'], 200)
        self.assertEqual(self.db['fingerprint'].count_documents({}), 0)
        self.assertEqual(set(self.db['fingerprint_deleted'].distinct('name')), {'Nginx', 'Redis'})

        # 删除后缓存刷新、扫描识别、服务重启增量同步均不得恢复已删指纹
        self.cache.update_cache(force=True)
        self.assertEqual(self.cache.get_data(), [])
        self.assertEqual(fingerprint_cache.finger_db_identify({'header': 'nginx', 'body': 'redis'}), [])
        self.assertEqual(self.db['fingerprint'].count_documents({}), 0)

        arlupdate.fingerprint_info_update()
        self.assertEqual(self.db['fingerprint'].count_documents({}), 0)

    def test_partial_delete_respects_blacklist_while_new_rule_syncs(self):
        arlupdate.fingerprint_info_update()
        nginx_doc = self.db['fingerprint'].find_one({'name': 'Nginx'})
        res = self._delete_ids([str(nginx_doc['_id'])])
        self.assertEqual(res['code'], 200)

        # 模拟版本升级新增内置规则，同时包含已删除的 Nginx
        self._write_webapp({
            "Nginx": {"fofa_rule": 'header="nginx"'},
            "Redis": {"fofa_rule": 'body="redis"'},
            "NewCloudApp": {"fofa_rule": 'title="NewCloudApp"'},
        })
        arlupdate.fingerprint_info_update()

        names = set(self.db['fingerprint'].distinct('name'))
        self.assertEqual(names, {'Redis', 'NewCloudApp'})

    def test_legacy_emptied_db_with_blacklist_does_not_reseed(self):
        # 模拟旧版本：fingerprint 已被删空、无初始化 sentinel，但 fingerprint_deleted 有记录
        self.db['fingerprint_deleted'].insert_many([{'name': 'Nginx'}, {'name': 'Redis'}])

        arlupdate.fingerprint_info_update()
        self.assertEqual(self.db['fingerprint'].count_documents({}), 0)
        sentinel = self.db['system_config'].find_one({'_id': 'fingerprint_initialized_v1'})
        self.assertTrue(sentinel and sentinel.get('initialized'))

        self.cache.update_cache(force=True)
        self.assertEqual(self.db['fingerprint'].count_documents({}), 0)

    def test_fresh_empty_db_auto_seeds_once(self):
        arlupdate.fingerprint_info_update()
        self.assertEqual(set(self.db['fingerprint'].distinct('name')), {'Nginx', 'Redis'})
        sentinel = self.db['system_config'].find_one({'_id': 'fingerprint_initialized_v1'})
        self.assertTrue(sentinel and sentinel.get('initialized'))

    def test_delete_fail_closed_when_blacklist_write_unacknowledged(self):
        arlupdate.fingerprint_info_update()
        nginx_doc = self.db['fingerprint'].find_one({'name': 'Nginx'})

        def _failing_conn(col, db_name=None):
            if col == 'fingerprint_deleted':
                return _UnackedWriteWrapper(self.db[col])
            return self.db[col]

        with patch.object(utils, 'conn_db', side_effect=_failing_conn):
            res = self._delete_ids([str(nginx_doc['_id'])])

        self.assertNotEqual(res['code'], 200)
        self.assertIsNotNone(self.db['fingerprint'].find_one({'_id': nginx_doc['_id']}))

    def test_delete_succeeds_when_unacked_but_already_in_blacklist(self):
        arlupdate.fingerprint_info_update()
        nginx_doc = self.db['fingerprint'].find_one({'name': 'Nginx'})
        self.db['fingerprint_deleted'].insert_one({'name': 'Nginx'})

        def _unacked_conn(col, db_name=None):
            if col == 'fingerprint_deleted':
                return _UnackedWriteWrapper(self.db[col])
            return self.db[col]

        with patch.object(utils, 'conn_db', side_effect=_unacked_conn):
            res = self._delete_ids([str(nginx_doc['_id'])])

        self.assertEqual(res['code'], 200)
        self.assertIsNone(self.db['fingerprint'].find_one({'_id': nginx_doc['_id']}))

    def test_cross_worker_cache_invalidation_on_delete_and_add(self):
        arlupdate.fingerprint_info_update()
        worker2_cache = FingerPrintCache()
        self.assertEqual({f.app_name for f in worker2_cache.get_data()}, {'Nginx', 'Redis'})

        # Worker1 删除 Redis
        redis_doc = self.db['fingerprint'].find_one({'name': 'Redis'})
        self.assertEqual(self._delete_ids([str(redis_doc['_id'])])['code'], 200)

        # Worker2 无需等待 TTL 即可感知版本号变更并刷新
        self.assertEqual({f.app_name for f in worker2_cache.get_data()}, {'Nginx'})

        # Worker1 新增指纹后，Worker2 也应自动感知
        add_cls = fingerprint_route.ARLFingerprint()
        with self.flask_app.test_request_context(
            '/api/fingerprint/',
            method='POST',
            json={'name': 'CustomApp', 'human_rule': 'body="custom_app_marker"'},
        ):
            add_res = add_cls.post()
        self.assertEqual(add_res['code'], 200)
        self.assertEqual({f.app_name for f in worker2_cache.get_data()}, {'Nginx', 'CustomApp'})

    def test_rule_search_and_alias_filter_human_rule(self):
        arlupdate.fingerprint_info_update()
        get_cls = fingerprint_route.ARLFingerprint()

        with self.flask_app.test_request_context('/api/fingerprint/?human_rule=redis', method='GET'):
            res1 = get_cls.get()
        self.assertEqual(res1['code'], 200)
        self.assertEqual([item['name'] for item in res1['items']], ['Redis'])

        with self.flask_app.test_request_context('/api/fingerprint/?rule=nginx', method='GET'):
            res2 = get_cls.get()
        self.assertEqual(res2['code'], 200)
        self.assertEqual([item['name'] for item in res2['items']], ['Nginx'])

    def test_arlupdate_create_index_deduplicates_fingerprint_collection(self):
        self.db['fingerprint'].insert_many([
            {'name': 'DupApp', 'human_rule': 'body="a"'},
            {'name': 'DupApp', 'human_rule': 'body="b"'},
        ])
        with patch('threading.Thread'):
            arlupdate.create_index()

        self.assertEqual(self.db['fingerprint'].count_documents({'name': 'DupApp'}), 1)
        idx_info = self.db['fingerprint'].index_information()
        self.assertTrue(any(info.get('unique') and info.get('key') == [('name', 1)] for info in idx_info.values()))

    def test_safe_collection_proxy_swallowed_bulk_write_error_still_fails_closed(self):
        arlupdate.fingerprint_info_update()
        nginx_doc = self.db['fingerprint'].find_one({'name': 'Nginx'})

        class _BrokenBulkColl:
            def __init__(self, real):
                self._real = real
                self.name = 'fingerprint_deleted'

            def bulk_write(self, *args, **kwargs):
                raise BulkWriteError({'writeErrors': [{'code': 43, 'errmsg': 'write failure'}], 'writeConcernErrors': []})

            def __getattr__(self, item):
                return getattr(self._real, item)

        def _proxy_conn(col, db_name=None):
            if col == 'fingerprint_deleted':
                return SafeCollectionProxy(_BrokenBulkColl(self.db[col]))
            return self.db[col]

        with patch.object(utils, 'conn_db', side_effect=_proxy_conn):
            res = self._delete_ids([str(nginx_doc['_id'])])

        self.assertNotEqual(res['code'], 200)
        self.assertIsNotNone(self.db['fingerprint'].find_one({'_id': nginx_doc['_id']}))

    def test_upload_and_sync_from_json_invalidate_cross_worker_cache(self):
        arlupdate.fingerprint_info_update()
        worker2_cache = FingerPrintCache()
        self.assertEqual({f.app_name for f in worker2_cache.get_data()}, {'Nginx', 'Redis'})

        # 上传新 YAML 指纹后，其他 Worker 应感知版本变更
        yaml_bytes = b'- name: UploadedApp\n  rule: title="UploadedApp"\n'
        storage = FileStorage(stream=io.BytesIO(yaml_bytes), filename='finger.yml')
        upload_cls = fingerprint_route.UploadARLFinger()
        with patch.object(fingerprint_route.file_upload, 'parse_args', return_value={'file': storage}):
            up_res = upload_cls.post()
        self.assertEqual(up_res['code'], 200)
        self.assertEqual(up_res['data']['success_cnt'], 1)
        self.assertEqual({f.app_name for f in worker2_cache.get_data()}, {'Nginx', 'Redis', 'UploadedApp'})

        # 全量同步回 webapp.json 后，其他 Worker 也应感知并恢复
        sync_cls = fingerprint_route.SyncFromJSON()
        sync_res = sync_cls.post()
        self.assertEqual(sync_res['code'], 200)
        self.assertEqual({f.app_name for f in worker2_cache.get_data()}, {'Nginx', 'Redis'})


if __name__ == '__main__':
    unittest.main()
