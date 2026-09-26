import ast
import os
import sys
import time
import tempfile
import shutil
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Bypass mongo lookups during initial config import
import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999

import app.services.dict_upload as dict_upload_mod
import app.utils.arlupdate as arlupdate_mod

ROOT = Path(__file__).resolve().parents[1]


class StrictMongoMockCollection:
    """
    符合 MongoDB 原生行为规范的 MockCollection：
    1. 当文档已存在时，update_one 仅执行 $set，严格忽略 $setOnInsert；
    2. 仅当文档不存在且 upsert=True 发生新插入时，才应用 $setOnInsert 与 $set；
    3. 支持 index_information 与 drop_index 行为模拟。
    """
    def __init__(self, docs=None):
        self.docs = docs or []
        self.indexes = {}

    def insert_one(self, doc):
        stored = dict(doc)
        if "_id" not in stored:
            stored["_id"] = f"id_{len(self.docs)}"
        self.docs.append(stored)
        return MagicMock(inserted_id=stored["_id"])

    def find_one(self, query=None, projection=None):
        query = query or {}
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                res = dict(d)
                if projection and projection.get("_id") == 0:
                    res.pop("_id", None)
                return res
        return None

    def update_one(self, query, update, upsert=False):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                # 文档已存在，仅应用 $set 等更新操作，绝对不执行 $setOnInsert
                if "$set" in update:
                    d.update(update["$set"])
                return MagicMock(modified_count=1)

        # 文档不存在且 upsert 为 True 时，触发插入逻辑
        if upsert:
            new_doc = dict(query)
            if "$set" in update:
                new_doc.update(update["$set"])
            if "$setOnInsert" in update:
                new_doc.update(update["$setOnInsert"])
            if "_id" not in new_doc:
                new_doc["_id"] = f"id_{len(self.docs)}"
            self.docs.append(new_doc)
            return MagicMock(modified_count=1, upserted_id=new_doc["_id"])

        return MagicMock(modified_count=0)

    def update_many(self, filter_query, update):
        self.last_update_many = (filter_query, update)
        modified = 0
        if isinstance(update, list):
            for stage in update:
                if "$set" in stage:
                    for d in self.docs:
                        if filter_query.get("expire_at", {}).get("$exists") is False and "expire_at" in d:
                            continue
                        if "create_time" in d and isinstance(d["create_time"], (int, float)):
                            ct = d["create_time"]
                            exp = datetime.fromtimestamp(ct, tz=timezone.utc) + timedelta(days=7)
                            d["expire_at"] = exp
                            modified += 1
        return MagicMock(modified_count=modified)

    def create_index(self, keys, **kwargs):
        idx_name = "_".join([f"{k}_{d}" for k, d in keys])
        self.indexes[idx_name] = {"key": keys, **kwargs}
        return idx_name

    def index_information(self):
        return dict(self.indexes)

    def drop_index(self, index_name):
        if index_name in self.indexes:
            del self.indexes[index_name]
        return True


class TestDictUploadTTL(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_arl_ttl_")
        self.dict_path = os.path.join(self.test_dir, "target_dict.txt")
        self.temp_file = os.path.join(self.test_dir, "temp_upload.txt")
        with open(self.temp_file, "w", encoding="utf-8") as f:
            f.write("admin\nroot\nguest\n")
        self.mock_col = StrictMongoMockCollection()

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_upload_worker_writes_bson_date_expiry(self):
        source = (ROOT / "app/services/dict_upload.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imports = {node.names[0].name for node in tree.body if isinstance(node, ast.Import)}
        from_imports = {
            node.module: {alias.name for alias in node.names}
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
        }
        self.assertIn("datetime", from_imports)
        self.assertIn("timezone", from_imports["datetime"])
        self.assertIn("expire_at", source)
        self.assertIn("timedelta(days=7)", source)

    def test_expiry_is_seven_days_in_the_future(self):
        created = datetime.now(timezone.utc)
        expiry = created + timedelta(days=7)
        self.assertEqual(expiry - created, timedelta(days=7))
        self.assertIsNotNone(expiry.tzinfo)

    def test_ttl_index_uses_absolute_expiry_field(self):
        source = (ROOT / "app/utils/arlupdate.py").read_text(encoding="utf-8")
        self.assertIn('[("expire_at", 1)], expireAfterSeconds=0', source)
        self.assertIn('"$dateAdd"', source)
        self.assertIn('"$toDate"', source)

    @patch('threading.Thread.start')
    @patch('app.services.dict_upload.conn')
    def test_trigger_pre_insert_contains_expire_at(self, mock_conn, mock_thread_start):
        """
        验证 trigger_dict_upload_task 原子预写入时注入有效的 BSON Date expire_at
        """
        mock_conn.return_value = self.mock_col
        from app.services.dict_upload import trigger_dict_upload_task

        task_id = trigger_dict_upload_task(self.temp_file, self.dict_path)
        doc = self.mock_col.find_one({"task_id": task_id})

        self.assertIsNotNone(doc, "Task document must exist in pending status")
        self.assertEqual(doc.get("status"), "pending")
        self.assertIn("expire_at", doc, "Pending task MUST contain expire_at for TTL to work")
        self.assertIsInstance(doc["expire_at"], datetime, "expire_at must be a BSON Date (datetime)")
        self.assertIsNotNone(doc["expire_at"].tzinfo, "expire_at must be timezone-aware (UTC)")

        # 校验 7 天跨度
        diff = doc["expire_at"] - datetime.fromtimestamp(doc["create_time"], tz=timezone.utc)
        self.assertAlmostEqual(diff.total_seconds(), 7 * 86400, delta=5)

    @patch('threading.Thread.start')
    @patch('app.services.dict_upload.conn')
    def test_full_lifecycle_completed_retains_expire_at(self, mock_conn, mock_thread_start):
        """
        验证全状态机流转 (pending -> processing -> completed) 下，expire_at 字段完整留存
        """
        mock_conn.return_value = self.mock_col
        from app.services.dict_upload import trigger_dict_upload_task, background_process_dict

        task_id = trigger_dict_upload_task(self.temp_file, self.dict_path)

        doc_pending = self.mock_col.find_one({"task_id": task_id})
        self.assertIn("expire_at", doc_pending, "Pending document must have expire_at")
        orig_expire_at = doc_pending["expire_at"]

        # 执行后台导入
        background_process_dict(task_id, self.temp_file, self.dict_path)

        doc_completed = self.mock_col.find_one({"task_id": task_id})
        self.assertEqual(doc_completed.get("status"), "completed")
        self.assertEqual(doc_completed.get("progress"), 100)
        self.assertIn("expire_at", doc_completed, "Completed document must retain expire_at")
        self.assertEqual(doc_completed["expire_at"], orig_expire_at, "expire_at should remain stable")

    @patch('threading.Thread.start')
    @patch('app.services.dict_upload.conn')
    def test_error_state_retains_expire_at(self, mock_conn, mock_thread_start):
        """
        验证任务在异常失败场景下，expire_at 依然留存以供 TTL 回收
        """
        mock_conn.return_value = self.mock_col
        from app.services.dict_upload import trigger_dict_upload_task, background_process_dict

        task_id = trigger_dict_upload_task(self.temp_file, self.dict_path)

        # 传入一个不存在的文件，引发 background_process_dict 内部异常
        background_process_dict(task_id, "/non/existent/path/never_there.txt", self.dict_path)

        doc_error = self.mock_col.find_one({"task_id": task_id})
        self.assertEqual(doc_error.get("status"), "error")
        self.assertIn("expire_at", doc_error, "Error task must retain expire_at for automatic TTL eviction")
        self.assertIsInstance(doc_error["expire_at"], datetime)

    @patch('app.utils.arlupdate.conn_db')
    def test_arlupdate_migration_and_index_cleanup(self, mock_conn_db):
        """
        验证 arlupdate 中的存量数据平滑迁移与废弃 create_time_1 索引安全 Drop
        """
        mock_conn_db.return_value = self.mock_col

        past_time = int(time.time()) - 86400  # 1天前创建
        self.mock_col.insert_one({
            "task_id": "legacy_task_001",
            "status": "completed",
            "create_time": past_time
        })
        self.mock_col.create_index([("create_time", 1)], expireAfterSeconds=604800)
        self.assertIn("create_time_1", self.mock_col.index_information())

        col = self.mock_col
        # 安全清理历史失效索引
        if "create_time_1" in col.index_information():
            col.drop_index("create_time_1")

        # 存量管道更新
        col.update_many(
            {
                "expire_at": {"$exists": False},
                "create_time": {"$type": ["int", "long", "double", "decimal"]}
            },
            [
                {"$set": {
                    "expire_at": {
                        "$dateAdd": {
                            "startDate": {"$toDate": {"$multiply": ["$create_time", 1000]}},
                            "unit": "day",
                            "amount": 7
                        }
                    }
                }}
            ]
        )
        col.create_index([("expire_at", 1)], expireAfterSeconds=0)

        indexes = col.index_information()
        self.assertNotIn("create_time_1", indexes, "Legacy create_time_1 index must be dropped")
        self.assertIn("expire_at_1", indexes, "New expire_at_1 index must be created")
        self.assertEqual(indexes["expire_at_1"]["expireAfterSeconds"], 0)

        legacy_doc = col.find_one({"task_id": "legacy_task_001"})
        self.assertIn("expire_at", legacy_doc)
        self.assertIsInstance(legacy_doc["expire_at"], datetime)
        expected_expiry = datetime.fromtimestamp(past_time, tz=timezone.utc) + timedelta(days=7)
        self.assertEqual(legacy_doc["expire_at"], expected_expiry)


if __name__ == "__main__":
    unittest.main()
