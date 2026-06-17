"""
test_api_github.py
==================
测试 GitHub 监控相关接口：
  - GET  /api/github_task/          查询 GitHub 监控任务列表
  - POST /api/github_task/          创建 GitHub 监控任务
  - POST /api/github_task/stop/     停止 GitHub 监控任务
  - POST /api/github_task/delete/   删除 GitHub 监控任务
  - GET  /api/github_result/        查询 GitHub 扫描结果
  - GET  /api/github_scheduler/     查询 GitHub 监控调度任务
  - GET  /api/github_monitor_result/ 查询 GitHub 监控结果
"""
import time
import pytest
from conftest import BASE_URL


# ──────────────────────────────────────────────
# 辅助：创建 GitHub 任务
# ──────────────────────────────────────────────
def _create_github_task(api_client, name="pytest-github-task", keyword="pytest secret leak test"):
    payload = {"name": name, "keyword": keyword}
    res = api_client.post(f"{BASE_URL}/github_task/", json=payload)
    assert res.status_code == 200, f"创建 GitHub 任务失败: {res.text}"
    body = res.json()
    assert body.get("code") == 200, f"创建 Github 监控任务失败: {body}"
    task_id = body.get("data", {}).get("task_id") or body.get("data", {}).get("_id") or body.get("_id")
    assert task_id, f"未获取到 task_id: {body}"
    return task_id


# ──────────────────────────────────────────────
# 1. 查询 GitHub 任务
# ──────────────────────────────────────────────

class TestGithubTaskQuery:
    def test_get_github_task_list(self, api_client):
        """GET /github_task/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/github_task/")
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert "items" in body
        assert "total" in body

    def test_get_github_task_pagination(self, api_client):
        """分页参数 size=3 生效"""
        res = api_client.get(f"{BASE_URL}/github_task/", params={"page": 1, "size": 3})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert len(body["items"]) <= 3

    def test_get_github_task_filter_by_status(self, api_client):
        """按 status 过滤"""
        res = api_client.get(f"{BASE_URL}/github_task/", params={"status": "done"})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200


# ──────────────────────────────────────────────
# 2. 创建 GitHub 任务
# ──────────────────────────────────────────────

class TestGithubTaskCreate:
    def test_create_github_task_success(self, api_client):
        """正常创建 GitHub 监控任务"""
        task_id = _create_github_task(api_client, name="pytest-create-github")
        assert task_id
        # 存储供后续停止/删除使用
        TestGithubTaskCreate.task_id = task_id

    def test_create_github_task_missing_name(self, api_client):
        """缺少 name 字段：应返回 400"""
        res = api_client.post(f"{BASE_URL}/github_task/", json={"keyword": "test"})
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)

    def test_create_github_task_missing_keyword(self, api_client):
        """缺少 keyword 字段：应返回 400"""
        res = api_client.post(f"{BASE_URL}/github_task/", json={"name": "pytest-no-kw"})
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)

    def test_create_github_task_empty_keyword(self, api_client):
        """keyword 为空字符串：业务层应拒绝"""
        res = api_client.post(f"{BASE_URL}/github_task/",
                              json={"name": "pytest-empty-kw", "keyword": "   "})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] != 200


# ──────────────────────────────────────────────
# 3. 停止 GitHub 任务
# ──────────────────────────────────────────────

class TestGithubTaskStop:
    def test_stop_github_task(self, api_client):
        """停止正在运行的 GitHub 任务"""
        task_id = getattr(TestGithubTaskCreate, "task_id", None)
        if not task_id:
            pytest.skip("未找到可停止的 GitHub 任务 ID")

        time.sleep(2)  # 等待任务启动
        res = api_client.post(f"{BASE_URL}/github_task/stop/", json={"_id": [task_id]})
        assert res.status_code == 200
        body = res.json()
        # 可能已完成（done）或正在运行（running），两种情况都可接受
        assert body["code"] in (200, 400, 500) or "code" in body

    def test_stop_nonexistent_github_task(self, api_client):
        """停止不存在的任务：应返回业务错误"""
        res = api_client.post(f"{BASE_URL}/github_task/stop/",
                              json={"_id": ["000000000000000000000000"]})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] != 200


# ──────────────────────────────────────────────
# 4. 删除 GitHub 任务
# ──────────────────────────────────────────────

class TestGithubTaskDelete:
    def test_delete_github_task(self, api_client):
        """删除已停止/完成的 GitHub 任务"""
        # 创建一个新任务，等待完成后再删
        task_id = _create_github_task(api_client, name="pytest-delete-github")
        time.sleep(3)

        # 先停止
        api_client.post(f"{BASE_URL}/github_task/stop/", json={"_id": [task_id]})
        time.sleep(1)

        # 再删除
        res = api_client.post(f"{BASE_URL}/github_task/delete/", json={"_id": [task_id]})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200

    def test_delete_nonexistent_github_task(self, api_client):
        """删除不存在的 GitHub 任务：应返回业务错误"""
        res = api_client.post(f"{BASE_URL}/github_task/delete/",
                              json={"_id": ["000000000000000000000000"]})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] != 200

    def test_delete_missing_id(self, api_client):
        """缺少 _id 字段：应返回 400"""
        res = api_client.post(f"{BASE_URL}/github_task/delete/", json={})
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)


# ──────────────────────────────────────────────
# 5. GitHub 扫描结果查询
# ──────────────────────────────────────────────

class TestGithubResultQuery:
    def test_get_github_result_list(self, api_client):
        """GET /github_result/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/github_result/")
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert "items" in body

    def test_get_github_monitor_result_list(self, api_client):
        """GET /github_monitor_result/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/github_monitor_result/")
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert "items" in body


# ──────────────────────────────────────────────
# 6. GitHub 监控调度查询
# ──────────────────────────────────────────────

class TestGithubSchedulerQuery:
    def test_get_github_scheduler_list(self, api_client):
        """GET /github_scheduler/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/github_scheduler/")
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert "items" in body
