import os
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from bson import ObjectId

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
npoc_dir = os.path.join(backend_dir, 'ARL-NPoC')
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)
if npoc_dir not in sys.path:
    sys.path.insert(0, npoc_dir)

import pymongo
pymongo.MongoClient = MagicMock()

import app.config
app.config._config_cache["data"] = {}
app.config._config_cache["last_update"] = 9999999999
app.config.get_system_config_value = lambda k, d: d
app.config.Config.AUTH = False

import app.utils
import app.utils.conn
_mock_conn_db = lambda *a, **k: MagicMock()
app.utils.conn.conn_db = _mock_conn_db
app.utils.conn_db = _mock_conn_db

from app.routes.policy import AddARLPolicy, EditPolicy
from app.modules import get_scan_ports
from app.tasks.domain import DomainTask
from app.tasks.ip import IPTask


class TestPolicyCustomPortLinkage(unittest.TestCase):

    def test_add_policy_system_dict_and_empty_custom_no_hardcoded_fallback(self):
        policy_col = MagicMock()
        policy_col.insert_one.side_effect = lambda doc: doc.__setitem__("_id", ObjectId())
        add_res = AddARLPolicy()

        with patch("app.routes.policy.utils.conn_db", return_value=policy_col):
            # 1. 新建策略选择系统字典 port_custom.txt：port_custom 置空，不注入 80,443
            with patch.object(add_res, "parse_args", return_value={
                "name": "p_dict_custom",
                "desc": "",
                "policy": {"ip_config": {"port_scan": True, "port_scan_type": "port_custom.txt"}},
            }):
                resp = add_res.post()
                self.assertEqual(resp.get("code"), 200)
                inserted = policy_col.insert_one.call_args[0][0]
                self.assertEqual(inserted["policy"]["ip_config"]["port_scan_type"], "port_custom.txt")
                self.assertEqual(inserted["policy"]["ip_config"]["port_custom"], "")

            # 2. API 传 port_scan_type="custom" 但未传 port_custom：port_custom 留空（执行期实时读取 port_custom.txt）
            with patch.object(add_res, "parse_args", return_value={
                "name": "p_api_custom_live",
                "desc": "",
                "policy": {"ip_config": {"port_scan": True, "port_scan_type": "custom"}},
            }):
                resp = add_res.post()
                self.assertEqual(resp.get("code"), 200)
                inserted = policy_col.insert_one.call_args[0][0]
                self.assertEqual(inserted["policy"]["ip_config"]["port_scan_type"], "custom")
                self.assertEqual(inserted["policy"]["ip_config"]["port_custom"], "")

            # 3. API 显式传 port_scan_type="custom" + 合法 port_custom：兼容保留
            with patch.object(add_res, "parse_args", return_value={
                "name": "p_api_custom_inline",
                "desc": "",
                "policy": {"ip_config": {"port_scan": True, "port_scan_type": "custom", "port_custom": "80, 443, 8000-8010"}},
            }):
                resp = add_res.post()
                self.assertEqual(resp.get("code"), 200)
                inserted = policy_col.insert_one.call_args[0][0]
                self.assertEqual(inserted["policy"]["ip_config"]["port_custom"], "80,443,8000-8010")

            # 4. API 传非法 port_custom 仍拦截报错
            policy_col.insert_one.reset_mock()
            with patch.object(add_res, "parse_args", return_value={
                "name": "p_api_custom_bad",
                "desc": "",
                "policy": {"ip_config": {"port_scan": True, "port_scan_type": "custom", "port_custom": "80,abc"}},
            }):
                resp = add_res.post()
                self.assertNotEqual(resp.get("code"), 200)
                policy_col.insert_one.assert_not_called()

            # 5. 非 custom 类型即便附带历史 port_custom 也清空，避免脏数据残留
            with patch.object(add_res, "parse_args", return_value={
                "name": "p_top100",
                "desc": "",
                "policy": {"ip_config": {"port_scan": True, "port_scan_type": "port_top100.txt", "port_custom": "80,443"}},
            }):
                resp = add_res.post()
                self.assertEqual(resp.get("code"), 200)
                inserted = policy_col.insert_one.call_args[0][0]
                self.assertEqual(inserted["policy"]["ip_config"]["port_custom"], "")

    def test_edit_policy_legacy_compatibility_and_switch_to_system_dict(self):
        oid = ObjectId()
        policy_col = MagicMock()
        edit_res = EditPolicy()

        def make_legacy_custom_doc():
            return {
                "_id": oid,
                "name": "legacy_custom",
                "desc": "",
                "policy": {
                    "domain_config": {},
                    "ip_config": {"port_scan": True, "port_scan_type": "custom", "port_custom": "22,3306"},
                    "site_config": {},
                    "poc_config": [],
                    "brute_config": [],
                },
            }

        with patch("app.routes.policy.utils.conn_db", return_value=policy_col):
            # 1. 仅修改名称时，存量 custom 策略的手填端口原样保留
            policy_col.find_one.return_value = make_legacy_custom_doc()
            with patch.object(edit_res, "parse_args", return_value={
                "policy_id": str(oid),
                "policy_data": {"name": "legacy_renamed"},
            }):
                resp = edit_res.post()
                self.assertEqual(resp.get("code"), 200)
                replaced = policy_col.find_one_and_replace.call_args[0][1]
                self.assertEqual(replaced["policy"]["ip_config"]["port_scan_type"], "custom")
                self.assertEqual(replaced["policy"]["ip_config"]["port_custom"], "22,3306")

            # 2. 编辑页保存切换为系统字典 port_custom.txt 时，清理历史 port_custom
            policy_col.find_one.return_value = make_legacy_custom_doc()
            with patch.object(edit_res, "parse_args", return_value={
                "policy_id": str(oid),
                "policy_data": {"policy": {"ip_config": {"port_scan_type": "port_custom.txt"}}},
            }):
                resp = edit_res.post()
                self.assertEqual(resp.get("code"), 200)
                replaced = policy_col.find_one_and_replace.call_args[0][1]
                self.assertEqual(replaced["policy"]["ip_config"]["port_scan_type"], "port_custom.txt")
                self.assertEqual(replaced["policy"]["ip_config"]["port_custom"], "")

            # 3. API 显式将 port_custom 置空，不再回退硬编码 80,443
            policy_col.find_one.return_value = make_legacy_custom_doc()
            with patch.object(edit_res, "parse_args", return_value={
                "policy_id": str(oid),
                "policy_data": {"policy": {"ip_config": {"port_scan_type": "custom", "port_custom": ""}}},
            }):
                resp = edit_res.post()
                self.assertEqual(resp.get("code"), 200)
                replaced = policy_col.find_one_and_replace.call_args[0][1]
                self.assertEqual(replaced["policy"]["ip_config"]["port_scan_type"], "custom")
                self.assertEqual(replaced["policy"]["ip_config"]["port_custom"], "")

            # 4. 仅更新 port_custom 但不重传 port_scan_type 时依然触发非法格式拦截
            policy_col.find_one.return_value = make_legacy_custom_doc()
            policy_col.find_one_and_replace.reset_mock()
            with patch.object(edit_res, "parse_args", return_value={
                "policy_id": str(oid),
                "policy_data": {"policy": {"ip_config": {"port_custom": "not_a_port"}}},
            }):
                resp = edit_res.post()
                self.assertNotEqual(resp.get("code"), 200)
                policy_col.find_one_and_replace.assert_not_called()

            # 5. 原为 top100（带历史默认 port_custom="80,443"）切到 custom 且不传 port_custom：不继承旧默认值
            policy_col.find_one.return_value = {
                "_id": oid,
                "name": "legacy_top100",
                "desc": "",
                "policy": {
                    "domain_config": {},
                    "ip_config": {"port_scan": True, "port_scan_type": "top100", "port_custom": "80,443"},
                    "site_config": {},
                    "poc_config": [],
                    "brute_config": [],
                },
            }
            with patch.object(edit_res, "parse_args", return_value={
                "policy_id": str(oid),
                "policy_data": {"policy": {"ip_config": {"port_scan_type": "custom"}}},
            }):
                resp = edit_res.post()
                self.assertEqual(resp.get("code"), 200)
                replaced = policy_col.find_one_and_replace.call_args[0][1]
                self.assertEqual(replaced["policy"]["ip_config"]["port_scan_type"], "custom")
                self.assertEqual(replaced["policy"]["ip_config"]["port_custom"], "")

    def test_runtime_domain_and_ip_tasks_live_read_port_custom_dict_and_keep_legacy_inline(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            dicts_dir = os.path.join(tmpdir, "dicts")
            os.makedirs(dicts_dir, exist_ok=True)
            custom_path = os.path.join(dicts_dir, "port_custom.txt")
            with open(custom_path, "w", encoding="utf-8") as f:
                f.write("8081\n9000-9002\n")

            with patch("app.config.Config.basedir", tmpdir):
                # 1. DomainTask 使用 port_custom.txt 实时读取系统字典
                dt1 = DomainTask(
                    base_domain="example.com",
                    task_id="t1",
                    options={"port_scan_type": "port_custom.txt", "port_custom": ""},
                )
                self.assertEqual(dt1.scan_port_option["ports"], "8081,9000-9002")

                # 2. 更新系统设置 port_custom.txt 后，后续任务无需修改策略即实时生效
                with open(custom_path, "w", encoding="utf-8") as f:
                    f.write("8443\n10443\n")
                dt2 = DomainTask(
                    base_domain="example.com",
                    task_id="t2",
                    options={"port_scan_type": "port_custom.txt", "port_custom": ""},
                )
                self.assertEqual(dt2.scan_port_option["ports"], "8443,10443")

                # 3. API 传 port_scan_type="custom" 且 port_custom="" 同样实时读取 port_custom.txt
                dt3 = DomainTask(
                    base_domain="example.com",
                    task_id="t3",
                    options={"port_scan_type": "custom", "port_custom": ""},
                )
                self.assertEqual(dt3.scan_port_option["ports"], "8443,10443")
                self.assertEqual(get_scan_ports("custom"), "8443,10443")

                # 4. 存量未重新编辑的 custom + 非空 port_custom 策略平滑兼容按原手填端口执行
                dt4 = DomainTask(
                    base_domain="example.com",
                    task_id="t4",
                    options={"port_scan_type": "custom", "port_custom": "22,3389"},
                )
                self.assertEqual(dt4.scan_port_option["ports"], "22,3389")

                # 5. IPTask 同样实时联动 port_custom.txt 并兼容存量手填端口
                ip_task = IPTask.__new__(IPTask)
                ip_task.ip_target = "192.0.2.10"
                ip_task.task_id = "ip1"
                ip_task.task_tag = "task"
                ip_task.ip_info_list = []
                ip_task.ip_set = set()
                ip_task.options = {"port_scan_type": "port_custom.txt", "port_custom": ""}
                with patch("app.tasks.ip.services.port_scan", return_value=[]) as mock_scan:
                    ip_task.port_scan()
                    self.assertEqual(mock_scan.call_args.kwargs["ports"], "8443,10443")

                ip_task.options = {"port_scan_type": "custom", "port_custom": "22,3389"}
                with patch("app.tasks.ip.services.port_scan", return_value=[]) as mock_scan:
                    ip_task.port_scan()
                    self.assertEqual(mock_scan.call_args.kwargs["ports"], "22,3389")


if __name__ == "__main__":
    unittest.main()
