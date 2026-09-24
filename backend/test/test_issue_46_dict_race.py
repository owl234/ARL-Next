import os
import sys
import time
import shutil
import tempfile
import threading
import unittest
from unittest.mock import MagicMock, patch

# Ensure backend root is on sys.path
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Bypass mongo lookups during initial config import
import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999

from app.utils.dict_utils import (
    dict_lock,
    get_dict_lock_path,
    create_dict_file,
    append_to_dict_file,
    delete_entries_from_dict_file,
    hash_dict_entry
)
from app.services.dict_upload import trigger_dict_upload_task


class MockCollection:
    def __init__(self, docs=None):
        self.docs = docs or []
        self.inserted = []
        self.updated = []

    def insert_one(self, doc):
        self.docs.append(doc)
        self.inserted.append(doc)
        return MagicMock(inserted_id=doc.get("_id"))

    def find_one(self, query=None):
        query = query or {}
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                return d
        return None

    def update_one(self, query, update, upsert=False):
        self.updated.append((query, update))
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                if "$set" in update:
                    d.update(update["$set"])
                return MagicMock(modified_count=1)
        if upsert:
            new_doc = dict(query)
            if "$set" in update:
                new_doc.update(update["$set"])
            self.docs.append(new_doc)
            return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)


class TestDictConcurrencyAndRace(unittest.TestCase):
    """
    第一性原理单元测试：验证字典高并发读写竞态与锁文件 Inode 不变性 (Issue #46)
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_arl_dict_")
        self.dict_path = os.path.join(self.test_dir, "test_dict.txt")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_dict_lock_inode_invariance(self):
        """
        验证锁文件独立性：当 os.replace 替换字典文件时，.lock 文件的 Inode 保持不变，
        杜绝因替换原文件导致等待进程持有的 fd 指向已 unlink 的旧 Inode。
        """
        # 初始创建
        create_dict_file(self.dict_path, "item1\nitem2\nitem3\n")
        lock_path = get_dict_lock_path(self.dict_path)
        self.assertEqual(lock_path, self.dict_path + ".lock")

        # 确保 lock 文件已生成
        with dict_lock(self.dict_path):
            pass

        orig_lock_ino = os.stat(lock_path).st_ino
        orig_dict_ino = os.stat(self.dict_path).st_ino

        # 执行删除操作（内部会触发临时文件写入与 os.replace 原字典文件）
        deleted = delete_entries_from_dict_file(self.dict_path, {"item2"})
        self.assertEqual(deleted, 1)

        new_dict_ino = os.stat(self.dict_path).st_ino
        new_lock_ino = os.stat(lock_path).st_ino

        # 字典原文件的 Inode 应当改变（原子替换），而锁文件的 Inode 必须绝对保持不变
        self.assertNotEqual(orig_dict_ino, new_dict_ino)
        self.assertEqual(orig_lock_ino, new_lock_ino)

    def test_concurrent_delete_and_append_no_data_loss(self):
        """
        重现并验证 Issue #46 核心竞态：
        并发执行 delete 与 append 操作，验证追加的新条目 100% 被保留，绝对不被 delete 的原子替换覆盖丢失。
        """
        # 1. 初始化包含 100 条待删除项的字典
        initial_items = [f"old_entry_{i}" for i in range(100)]
        create_dict_file(self.dict_path, "\n".join(initial_items))

        # 待追加的 100 个新条目
        appended_items = [f"new_entry_{i}" for i in range(100)]
        errors = []

        def run_delete():
            try:
                # 模拟分批删除老数据
                for chunk_idx in range(5):
                    targets = {f"old_entry_{chunk_idx * 20 + j}" for j in range(20)}
                    delete_entries_from_dict_file(self.dict_path, targets)
                    time.sleep(0.005)
            except Exception as e:
                errors.append(f"Delete error: {e}")

        def run_append():
            try:
                # 模拟并发追加新数据
                for chunk_idx in range(5):
                    lines = "\n".join(appended_items[chunk_idx * 20:(chunk_idx + 1) * 20])
                    append_to_dict_file(self.dict_path, lines)
                    time.sleep(0.005)
            except Exception as e:
                errors.append(f"Append error: {e}")

        t_del = threading.Thread(target=run_delete)
        t_app = threading.Thread(target=run_append)

        t_del.start()
        t_app.start()

        t_del.join()
        t_app.join()

        self.assertEqual(len(errors), 0, f"Thread errors occurred: {errors}")

        # 读取最终文件内容
        with open(self.dict_path, 'r', encoding='utf-8') as f:
            final_content = set(line.strip() for line in f if line.strip())

        # 校验：所有 100 个新追加的条目必须全部存在，零丢失
        for item in appended_items:
            self.assertIn(item, final_content, f"Data loss detected! {item} was overwritten!")

        # 校验：所有 100 个老条目必须已被彻底清除
        for item in initial_items:
            self.assertNotIn(item, final_content, f"Old entry {item} should have been deleted!")


class TestDictUploadTaskPendingState(unittest.TestCase):
    """
    第一性原理单元测试：验证 trigger_dict_upload_task 原子前置写入 pending 状态 (Issue #46)
    确保前端在请求派发完成的瞬间立刻轮询时，绝对不会出现 404 导致任务假死中断。
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_arl_upload_")
        self.temp_file = os.path.join(self.test_dir, "temp.txt")
        self.target_file = os.path.join(self.test_dir, "target.txt")
        with open(self.temp_file, "w") as f:
            f.write("a\nb\nc\n")

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("app.services.dict_upload.conn")
    @patch("app.celerytask.dict_import_celery_task.apply_async")
    def test_pre_inserted_pending_status_on_dispatch(self, mock_apply_async, mock_conn):
        mock_collection = MockCollection()
        mock_conn.return_value = mock_collection

        # 调用派发函数
        task_id = trigger_dict_upload_task(self.temp_file, self.target_file)

        # 校验：任务派发时已在集合中插入 pending 记录
        self.assertEqual(len(mock_collection.inserted), 1)
        doc = mock_collection.inserted[0]
        self.assertEqual(doc["task_id"], task_id)
        self.assertEqual(doc["status"], "pending")
        self.assertEqual(doc["progress"], 0)
        self.assertIn("等待队列调度", doc["message"])

        # 模拟前端第一次轮询查询状态（在 Worker 尚未消费任何数据前）
        polled = mock_collection.find_one({"task_id": task_id})
        self.assertIsNotNone(polled)
        self.assertEqual(polled["status"], "pending")


class TestDictSyncAppend10MBLimit(unittest.TestCase):
    """
    第一性原理单元测试：验证同步追加接口 10MB 物理截断与引导提示 (Issue #46)
    """

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_arl_append_")
        self.dict_name = "test_limit.txt"

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir, ignore_errors=True)

    @patch("app.routes.dictionary.get_safe_dict_path")
    @patch("app.routes.dictionary.append_parser.parse_args")
    def test_dictionary_append_10mb_limit(self, mock_args, mock_path):
        from app.routes.dictionary import DictionaryAppend

        mock_path.return_value = os.path.join(self.test_dir, self.dict_name)

        # 构造超过 10MB 的超大 payload
        large_content = "x" * (10 * 1024 * 1024 + 1024)
        mock_args.return_value = {
            "name": self.dict_name,
            "content": large_content
        }

        # 调用接口（绕过 auth 装饰器或直接调用未装饰函数）
        # 由于 @auth 装饰，我们直接调用 DictionaryAppend 的 post 实现逻辑
        handler = DictionaryAppend()
        res = handler.post.__wrapped__(handler) if hasattr(handler.post, '__wrapped__') else handler.post()

        self.assertEqual(res["code"], 400)
        self.assertIn("10MB", res["message"])
        self.assertIn("文件上传", res["message"])


if __name__ == '__main__':
    unittest.main()
