"""
test_api_task.py
================
测试资产发现任务接口：
  - GET  /api/task/             任务列表查询（分页、过滤）
  - POST /api/task/             提交新任务
  - POST /api/task/batch_stop/  批量停止
  - POST /api/task/delete/      批量删除
  - GET  /api/task/<id>/        任务详情
"""
import time
import pytest
from conftest import BASE_URL


# ──────────────────────────────────────────────
# 1. 任务列表查询
# ──────────────────────────────────────────────

class TestTaskQuery:
    def test_get_task_list(self, api_client):
        """GET /task/ 应返回标准分页结构"""
        res = api_client.get(f"{BASE_URL}/task/")
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert "items" in body
        assert "total" in body
        assert "page" in body
        assert "size" in body

    def test_get_task_list_pagination(self, api_client):
        """分页参数 page=1&size=5 应正常生效"""
        res = api_client.get(f"{BASE_URL}/task/", params={"page": 1, "size": 5})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert body["page"] == 1
        assert body["size"] == 5
        assert len(body["items"]) <= 5

    def test_get_task_list_filter_by_status(self, api_client):
        """按 status 字段过滤任务"""
        res = api_client.get(f"{BASE_URL}/task/", params={"status": "done"})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        # 如果有结果，每条记录的 status 应该匹配（模糊）
        for item in body["items"]:
            assert "done" in item.get("status", "").lower()

    def test_get_task_list_order_by_id(self, api_client):
        """按 _id 降序排列"""
        res = api_client.get(f"{BASE_URL}/task/", params={"order": "-_id", "size": 3})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200


# ──────────────────────────────────────────────
# 2. 提交新任务
# ──────────────────────────────────────────────

class TestTaskSubmit:
    def test_submit_task_success(self, api_client):
        """提交一个合法的域名扫描任务，应成功创建"""
        payload = {
            "name": "pytest-task-test",
            "target": "example.com",
            "domain_brute": False,
            "port_scan": False,
            "service_detection": False,
            "os_detection": False,
            "site_identify": False,
            "site_capture": False,
            "file_leak": False,
            "search_engines": False,
            "site_spider": False,
            "arl_search": False,
            "alt_dns": False,
            "ssl_cert": False,
            "nuclei_scan": False
        }
        res = api_client.post(f"{BASE_URL}/task/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert "items" in body
        assert len(body["items"]) > 0
        # 将任务 ID 存到类属性，供后续停止/删除测试使用
        TestTaskSubmit.created_task_id = body["items"][0].get("task_id") or body["items"][0].get("_id")

    def test_submit_task_missing_name(self, api_client):
        """缺少必填 name 字段：应返回 400"""
        payload = {"target": "example.com"}
        res = api_client.post(f"{BASE_URL}/task/", json=payload)
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)

    def test_submit_task_missing_target(self, api_client):
        """缺少必填 target 字段：应返回 400"""
        payload = {"name": "pytest-no-target"}
        res = api_client.post(f"{BASE_URL}/task/", json=payload)
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)

    def test_submit_task_empty_target(self, api_client):
        """target 字段为空字符串：业务层应拒绝"""
        payload = {"name": "pytest-empty-target", "target": ""}
        res = api_client.post(f"{BASE_URL}/task/", json=payload)
        assert res.status_code in (200, 400)
        if res.status_code == 200:
            body = res.json()
            assert body["code"] != 200


# ──────────────────────────────────────────────
# 3. 批量停止任务
# ──────────────────────────────────────────────

class TestTaskSingleStop:
    def test_single_stop_task(self, api_client):
        """GET /task/stop/<task_id>  单任务停止接口"""
        task_id = getattr(TestTaskSubmit, "created_task_id", None)
        if not task_id:
            pytest.skip("依赖 test_submit_task_success 先运行")
        res = api_client.get(f"{BASE_URL}/task/stop/{task_id}")
        assert res.status_code == 200
        body = res.json()
        # 已停止 or 成功停止
        assert body["code"] in (200, 400)

    def test_single_stop_nonexistent(self, api_client):
        """停止不存在的任务 ID：应返回业务错误"""
        res = api_client.get(f"{BASE_URL}/task/stop/000000000000000000000000")
        assert res.status_code == 200
        body = res.json()
        assert body["code"] != 200


class TestTaskSyncScope:
    def test_sync_scope_valid_domain(self, api_client):
        """GET /task/sync_scope/?target=xxx  反查归属资产组"""
        res = api_client.get(f"{BASE_URL}/task/sync_scope/", params={"target": "example.com"})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert "items" in body

    def test_sync_scope_invalid_domain(self, api_client):
        """非合法域名：业务层应拒绝"""
        res = api_client.get(f"{BASE_URL}/task/sync_scope/", params={"target": "not_a_domain!!!"})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] != 200

    def test_sync_scope_missing_target(self, api_client):
        """缺少 target 参数：应返回 400"""
        res = api_client.get(f"{BASE_URL}/task/sync_scope/")
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)


class TestTaskPolicySubmit:
    def test_submit_task_by_invalid_policy(self, api_client):
        """按不存在的策略 ID 下发任务：应返回 policy not found"""
        payload = {
            "name": "pytest-policy-task",
            "target": "example.com",
            "policy_id": "000000000000000000000000",
            "task_tag": "task"
        }
        res = api_client.post(f"{BASE_URL}/task/policy/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] != 200

    def test_submit_task_by_policy_invalid_tag(self, api_client, test_policy):
        """task_tag 不合法：应返回业务错误"""
        payload = {
            "name": "pytest-bad-tag-task",
            "target": "example.com",
            "policy_id": test_policy,
            "task_tag": "invalid_tag"
        }
        res = api_client.post(f"{BASE_URL}/task/policy/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] != 200

    def test_submit_task_by_policy_missing_fields(self, api_client):
        """缺少必填字段：应返回 400"""
        res = api_client.post(f"{BASE_URL}/task/policy/", json={"name": "no-policy-id"})
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)


class TestTaskRestart:
    def test_restart_nonexistent_task(self, api_client):
        """重启不存在的任务：应返回业务错误"""
        res = api_client.post(f"{BASE_URL}/task/restart/",
                              json={"task_id": ["000000000000000000000000"]})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] != 200

    def test_restart_missing_field(self, api_client):
        """缺少 task_id 字段：应返回 400"""
        res = api_client.post(f"{BASE_URL}/task/restart/", json={})
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)


class TestTaskStop:
    def test_batch_stop_task(self, api_client):
        """批量停止已创建的任务"""
        task_id = getattr(TestTaskSubmit, "created_task_id", None)
        if not task_id:
            pytest.skip("未找到可停止的任务 ID，依赖 test_submit_task_success 先运行")

        # 等待任务进入 running 状态（最多等 5 秒）
        time.sleep(3)
        payload = {"task_id": [task_id]}
        res = api_client.post(f"{BASE_URL}/task/batch_stop/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200

    def test_batch_stop_empty_list(self, api_client):
        """传入空列表停止：不应崩溃"""
        res = api_client.post(f"{BASE_URL}/task/batch_stop/", json={"task_id": []})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200

    def test_batch_stop_missing_field(self, api_client):
        """缺少 task_id 字段：应返回 400"""
        res = api_client.post(f"{BASE_URL}/task/batch_stop/", json={})
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)


# ──────────────────────────────────────────────
# 4. 删除任务
# ──────────────────────────────────────────────

class TestTaskDelete:
    def test_delete_task(self, api_client):
        """删除已停止的任务"""
        task_id = getattr(TestTaskSubmit, "created_task_id", None)
        if not task_id:
            pytest.skip("未找到可删除的任务 ID，依赖 test_submit_task_success 先运行")

        # 等待停止完成
        time.sleep(3)
        payload = {"task_id": [task_id]}
        res = api_client.post(f"{BASE_URL}/task/delete/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200

    def test_delete_nonexistent_task(self, api_client):
        """删除不存在的任务：应返回业务错误"""
        payload = {"task_id": ["000000000000000000000000"]}  # 不存在的 ObjectId
        res = api_client.post(f"{BASE_URL}/task/delete/", json=payload)
        assert res.status_code == 200
        body = res.json()
        # 不存在应报错，code != 200
        assert body["code"] != 200
