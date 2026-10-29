import os
import json
import tarfile
import tempfile
import unittest
import hashlib
from unittest.mock import patch, MagicMock

from app.services.backup_service import (
    BackupProgressTracker,
    compute_sha256,
    read_archive_manifest,
    list_all_backups,
    delete_backup_file,
    get_running_task_count,
    create_backup_archive,
    restore_backup_archive
)


class TestBackupRestore(unittest.TestCase):
    def test_progress_tracker_lifecycle(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as tf:
            mock_status_file = tf.name
        try:
            with patch("app.services.backup_service.STATUS_FILE", mock_status_file):
                tracker = BackupProgressTracker()
                self.assertEqual(tracker.status, "idle")

                tracker.start("backup", "arl_backup_test.tar.gz")
                state = tracker.get_state()
                self.assertEqual(state["status"], "backing_up")
                self.assertEqual(state["action"], "backup")
                self.assertEqual(state["archive_name"], "arl_backup_test.tar.gz")

                tracker.update("正在导出数据...", 50, "导出步骤A完成")
                state = tracker.get_state()
                self.assertEqual(state["stage"], "正在导出数据...")
                self.assertEqual(state["percent"], 50)
                self.assertTrue(any("导出步骤A完成" in log for log in state["logs"]))

                tracker.finish({"archive_name": "arl_backup_test.tar.gz", "size": 1024})
                state = tracker.get_state()
                self.assertEqual(state["status"], "success")
                self.assertEqual(state["percent"], 100)
                self.assertEqual(state["result"]["size"], 1024)

                tracker.start("restore", "arl_backup_test.tar.gz")
                tracker.fail("模拟还原失败错误")
                state = tracker.get_state()
                self.assertEqual(state["status"], "error")
                self.assertEqual(state["error"], "模拟还原失败错误")
        finally:
            if os.path.exists(mock_status_file):
                os.remove(mock_status_file)

    def test_compute_sha256(self):
        with tempfile.NamedTemporaryFile("w+", delete=False) as f:
            f.write("Hello ARL-Next Backup Test!")
            f_path = f.name
        try:
            expected = hashlib.sha256("Hello ARL-Next Backup Test!".encode()).hexdigest()
            self.assertEqual(compute_sha256(f_path), expected)
        finally:
            if os.path.exists(f_path):
                os.remove(f_path)

    def test_manifest_reading_and_validation(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            archive_path = os.path.join(tmpdir, "arl_backup_sample.tar.gz")
            
            # 创建伪造的备份内容
            sub_file = os.path.join(tmpdir, "mongo_dump.archive.gz")
            with open(sub_file, "w") as f:
                f.write("dummy database dump")
            data_hash = compute_sha256(sub_file)

            manifest_data = {
                "format_version": "1.0",
                "created_at": "2026-10-21T22:00:00",
                "arl_version": "3.5.0",
                "include_screenshots": False,
                "note": "单元测试备份",
                "mongo_stats": {
                    "total_collections": 5,
                    "total_documents": 100,
                    "summary": {"task_assets": 50, "scope_assets": 20, "total_tasks": 5, "total_users": 2}
                },
                "files": {"mongo_dump": "mongo_dump.archive.gz"},
                "checksums": {"mongo_dump.archive.gz": data_hash}
            }
            manifest_file = os.path.join(tmpdir, "manifest.json")
            with open(manifest_file, "w", encoding="utf-8") as f:
                json.dump(manifest_data, f)

            with tarfile.open(archive_path, "w:gz") as tar:
                tar.add(manifest_file, arcname="manifest.json")
                tar.add(sub_file, arcname="mongo_dump.archive.gz")

            # 读取元数据
            read_manifest = read_archive_manifest(archive_path)
            self.assertEqual(read_manifest["arl_version"], "3.5.0")
            self.assertEqual(read_manifest["note"], "单元测试备份")
            self.assertEqual(read_manifest["mongo_stats"]["total_documents"], 100)

    def test_list_and_delete_backups(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("app.services.backup_service.get_backup_dir", return_value=tmpdir):
                # 创建合法备份文件
                valid_file = os.path.join(tmpdir, "arl_backup_20261021_120000_123456.tar.gz")
                manifest_data = {
                    "format_version": "1.0",
                    "created_at": "2026-10-21T12:00:00",
                    "arl_version": "3.5.0",
                    "include_screenshots": True,
                    "note": "测试列表",
                    "mongo_stats": {"summary": {"task_assets": 10}},
                    "files": {"mongo_dump": "mongo_dump.archive.gz"},
                    "checksums": {"mongo_dump.archive.gz": hashlib.sha256(b'dummy dump').hexdigest()}
                }
                manifest_file = os.path.join(tmpdir, "manifest.json")
                with open(manifest_file, "w") as f:
                    json.dump(manifest_data, f)

                with tarfile.open(valid_file, "w:gz") as tar:
                    tar.add(manifest_file, arcname="manifest.json")
                    import io
                    member = tarfile.TarInfo('mongo_dump.archive.gz')
                    member.size = len(b'dummy dump')
                    tar.addfile(member, io.BytesIO(b'dummy dump'))

                # 列出备份
                backups = list_all_backups()
                self.assertEqual(len(backups), 1)
                self.assertEqual(backups[0]["filename"], "arl_backup_20261021_120000_123456.tar.gz")
                self.assertTrue(backups[0]["include_screenshots"])

                # 删除备份
                deleted = delete_backup_file("arl_backup_20261021_120000_123456.tar.gz")
                self.assertTrue(deleted)
                self.assertFalse(os.path.exists(valid_file))
                self.assertEqual(len(list_all_backups()), 0)

    def test_restore_blocked_on_running_tasks(self):
        with tempfile.NamedTemporaryFile("w+", suffix=".tar.gz", delete=False) as f:
            archive_path = f.name
        try:
            with patch("app.services.backup_service.get_running_task_count", return_value=3):
                with self.assertRaises(RuntimeError) as cm:
                    restore_backup_archive(archive_path, force=False)
                self.assertIn("3 个运行中或排队中的任务", str(cm.exception))
        finally:
            if os.path.exists(archive_path):
                os.remove(archive_path)


if __name__ == "__main__":
    unittest.main()
