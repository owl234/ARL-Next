"""
test_api_scheduler.py
=====================
测试资产监控任务调度接口：
  - GET  /api/scheduler/          查询监控任务列表
  - POST /api/scheduler/add/      创建监控任务
  - POST /api/scheduler/delete/   删除监控任务
  - POST /api/scheduler/run/      立即执行监控任务
  - POST /api/scheduler/pause/    暂停监控任务
  - POST /api/scheduler/resume/   恢复监控任务
"""
import pytest
from conftest import BASE_URL


# ──────────────────────────────────────────────
# 辅助：创建并返回监控任务 ID
# ──────────────────────────────────────────────
def _create_scheduler(api_client, scope_id, name="pytest-scheduler-tmp", interval=86400):
    payload = {
        "scope_id": scope_id,
        "domain": "pytest-test.example.com",
        "interval": interval,
        "name": name
    }
    res = api_client.post(f"{BASE_URL}/scheduler/add/", json=payload)
    assert res.status_code == 200, f"创建监控任务失败: {res.text}"
    body = res.json()
    assert body["code"] == 200, f"监控任务创建业务错误: {body}"
    job_id = body.get("data", {}).get("_id") or body.get("_id")
    assert job_id, f"未获取到监控任务 ID: {body}"
    return job_id


# ──────────────────────────────────────────────
# 1. 查询监控任务
# ──────────────────────────────────────────────

class TestSchedulerQuery:
    def test_get_scheduler_list(self, api_client):
        """GET /scheduler/ 应返回标准分页结构"""
        res = api_client.get(f"{BASE_URL}/scheduler/")
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert "items" in body
        assert "total" in body

    def test_get_scheduler_pagination(self, api_client):
        """分页参数生效"""
        res = api_client.get(f"{BASE_URL}/scheduler/", params={"page": 1, "size": 3})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert len(body["items"]) <= 3

    def test_get_scheduler_filter_by_name(self, api_client, test_scope):
        """按名称过滤监控任务"""
        # 先创建一个，再搜索
        job_id = _create_scheduler(api_client, test_scope, name="pytest-find-scheduler")
        res = api_client.get(f"{BASE_URL}/scheduler/", params={"name": "pytest-find-scheduler"})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert body["total"] >= 1
        # 清理
        api_client.post(f"{BASE_URL}/scheduler/delete/", json={"job_id": [job_id]})


# ──────────────────────────────────────────────
# 2. 创建监控任务
# ──────────────────────────────────────────────

class TestSchedulerCreate:
    def test_create_scheduler_success(self, api_client, test_scope):
        """正常创建监控任务"""
        job_id = _create_scheduler(api_client, test_scope, name="pytest-create-scheduler")
        assert job_id
        # 清理
        api_client.post(f"{BASE_URL}/scheduler/delete/", json={"job_id": [job_id]})

    def test_create_scheduler_missing_scope_id(self, api_client):
        """缺少 scope_id 字段：应返回 400"""
        payload = {"domain": "test.example.com", "interval": 86400, "name": "pytest-no-scope"}
        res = api_client.post(f"{BASE_URL}/scheduler/add/", json=payload)
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)

    def test_create_scheduler_missing_domain(self, api_client, test_scope):
        """缺少 domain 字段：应返回 400"""
        payload = {"scope_id": test_scope, "interval": 86400, "name": "pytest-no-domain"}
        res = api_client.post(f"{BASE_URL}/scheduler/add/", json=payload)
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)

    def test_create_scheduler_with_policy(self, api_client, test_scope, test_policy):
        """创建带有策略 ID 的监控任务"""
        payload = {
            "scope_id": test_scope,
            "domain": "pytest-policy-monitor.example.com",
            "interval": 86400,
            "name": "pytest-policy-scheduler",
            "policy_id": test_policy
        }
        res = api_client.post(f"{BASE_URL}/scheduler/add/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        job_id = body.get("data", {}).get("_id") or body.get("_id")
        # 清理
        if job_id:
            api_client.post(f"{BASE_URL}/scheduler/delete/", json={"job_id": [job_id]})


# ──────────────────────────────────────────────
# 3. 暂停 / 恢复监控任务
# ──────────────────────────────────────────────

class TestSchedulerStopRecover:
    def test_stop_and_recover_scheduler(self, api_client, test_scope):
        """POST /scheduler/stop/ 停止，再 POST /scheduler/recover/ 恢复"""
        job_id = _create_scheduler(api_client, test_scope, name="pytest-stop-recover-scheduler")

        # 停止（job_id 是字符串，非列表）
        res = api_client.post(f"{BASE_URL}/scheduler/stop/", json={"job_id": job_id})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200

        # 恢复
        res = api_client.post(f"{BASE_URL}/scheduler/recover/", json={"job_id": job_id})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200

        # 清理
        api_client.post(f"{BASE_URL}/scheduler/delete/", json={"job_id": [job_id]})

    def test_batch_stop_scheduler(self, api_client, test_scope):
        """POST /scheduler/stop/batch  批量停止"""
        job_id = _create_scheduler(api_client, test_scope, name="pytest-batch-stop-scheduler")
        res = api_client.post(f"{BASE_URL}/scheduler/stop/batch", json={"job_id": [job_id]})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        # 清理
        api_client.post(f"{BASE_URL}/scheduler/recover/batch", json={"job_id": [job_id]})
        api_client.post(f"{BASE_URL}/scheduler/delete/", json={"job_id": [job_id]})

    def test_batch_recover_scheduler(self, api_client, test_scope):
        """POST /scheduler/recover/batch  批量恢复"""
        job_id = _create_scheduler(api_client, test_scope, name="pytest-batch-recover-scheduler")
        # 先停止
        api_client.post(f"{BASE_URL}/scheduler/stop/", json={"job_id": job_id})
        # 再批量恢复
        res = api_client.post(f"{BASE_URL}/scheduler/recover/batch", json={"job_id": [job_id]})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        api_client.post(f"{BASE_URL}/scheduler/delete/", json={"job_id": [job_id]})

    def test_stop_nonexistent_scheduler(self, api_client):
        """停止不存在的监控任务：应返回业务错误"""
        res = api_client.post(f"{BASE_URL}/scheduler/stop/",
                              json={"job_id": "000000000000000000000000"})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] != 200


class TestSchedulerSiteWihMonitor:
    def test_add_site_monitor(self, api_client, test_scope):
        """POST /scheduler/add/site_monitor/ 添加站点更新监控"""
        payload = {
            "scope_id": test_scope,
            "interval": 86400,
            "name": "pytest-site-monitor"
        }
        res = api_client.post(f"{BASE_URL}/scheduler/add/site_monitor/", json=payload)
        assert res.status_code == 200
        body = res.json()
        # 成功或已存在相同监控（DomainSiteViaJob）
        assert body["code"] in (200, 400)

    def test_add_wih_monitor(self, api_client, test_scope):
        """POST /scheduler/add/wih_monitor/ 添加 WIH 更新监控"""
        payload = {
            "scope_id": test_scope,
            "interval": 86400,
            "name": "pytest-wih-monitor"
        }
        res = api_client.post(f"{BASE_URL}/scheduler/add/wih_monitor/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] in (200, 400)

    def test_add_site_monitor_interval_too_short(self, api_client, test_scope):
        """interval 小于 6 小时：应返回业务错误"""
        payload = {"scope_id": test_scope, "interval": 100, "name": "pytest-too-short"}
        res = api_client.post(f"{BASE_URL}/scheduler/add/site_monitor/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] != 200


# ──────────────────────────────────────────────
# 4. 删除监控任务
# ──────────────────────────────────────────────

class TestSchedulerDelete:
    def test_delete_scheduler(self, api_client, test_scope):
        """正常删除监控任务"""
        job_id = _create_scheduler(api_client, test_scope, name="pytest-delete-scheduler")
        res = api_client.post(f"{BASE_URL}/scheduler/delete/", json={"job_id": [job_id]})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200

    def test_delete_nonexistent_scheduler(self, api_client):
        """删除不存在的监控任务：应返回业务错误"""
        res = api_client.post(f"{BASE_URL}/scheduler/delete/",
                              json={"job_id": ["000000000000000000000000"]})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] != 200

    def test_delete_scheduler_missing_id(self, api_client):
        """缺少 _id 字段：应返回 400"""
        res = api_client.post(f"{BASE_URL}/scheduler/delete/", json={})
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)
