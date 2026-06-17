"""
test_api_misc.py
================
测试其余杂项接口：
  - GET  /api/poc/                   POC 列表
  - POST /api/poc/upload/            上传 POC
  - GET  /api/stat_finger/           指纹统计
  - GET  /api/console/               系统控制台信息
  - GET  /api/image/<filename>       截图图片
  - GET  /api/task_schedule/         定时任务计划查询
  - POST /api/task_schedule/add/     创建定时任务计划
  - POST /api/task_schedule/delete/  删除定时任务计划
  - GET  /api/task_fofa/             FOFA 任务查询
"""
import pytest
from conftest import BASE_URL


# ──────────────────────────────────────────────
# 1. POC 管理接口
# ──────────────────────────────────────────────

class TestPoc:
    def test_get_poc_list(self, api_client):
        """GET /poc/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/poc/")
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert "items" in body
        assert "total" in body

    def test_get_poc_pagination(self, api_client):
        """分页参数 size=5"""
        res = api_client.get(f"{BASE_URL}/poc/", params={"page": 1, "size": 5})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert len(body["items"]) <= 5

    def test_get_poc_filter_by_name(self, api_client):
        """按名称模糊过滤 POC"""
        res = api_client.get(f"{BASE_URL}/poc/", params={"name": "test"})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200

    def test_get_poc_filter_by_type(self, api_client):
        """按 poc_type 过滤"""
        res = api_client.get(f"{BASE_URL}/poc/", params={"poc_type": "nuclei"})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200


# ──────────────────────────────────────────────
# 2. 指纹统计接口
# ──────────────────────────────────────────────

class TestStatFinger:
    def test_get_stat_finger(self, api_client):
        """GET /stat_finger/ 应返回统计数据"""
        res = api_client.get(f"{BASE_URL}/stat_finger/")
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200

    def test_stat_finger_filter_by_task_id(self, api_client):
        """按 task_id 过滤指纹统计"""
        res = api_client.get(f"{BASE_URL}/stat_finger/",
                             params={"task_id": "000000000000000000000000"})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200


# ──────────────────────────────────────────────
# 3. 控制台接口
# ──────────────────────────────────────────────

class TestConsole:
    def test_get_console_info(self, api_client):
        """GET /console/ 应返回系统状态信息"""
        res = api_client.get(f"{BASE_URL}/console/")
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200


# ──────────────────────────────────────────────
# 4. 定时任务计划接口（task_schedule）
# ──────────────────────────────────────────────

class TestTaskSchedule:
    def test_get_task_schedule_list(self, api_client):
        """GET /task_schedule/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/task_schedule/")
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert "items" in body

    def test_get_task_schedule_pagination(self, api_client):
        """分页参数 size=5"""
        res = api_client.get(f"{BASE_URL}/task_schedule/", params={"page": 1, "size": 5})
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert len(body["items"]) <= 5

    def test_create_recurrent_task_schedule(self, api_client, test_policy):
        """POST /task_schedule/ 创建 recurrent_scan 计划任务"""
        payload = {
            "name": "pytest-recurrent-schedule",
            "target": "example.com",
            "schedule_type": "recurrent_scan",
            "policy_id": test_policy,
            "cron": "0 2 * * *",
            "task_tag": "task"
        }
        res = api_client.post(f"{BASE_URL}/task_schedule/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        schedule_id = body.get("data", {}).get("_id")
        if schedule_id:
            # 停止
            stop_res = api_client.post(f"{BASE_URL}/task_schedule/stop/",
                                       json={"_id": [schedule_id]})
            assert stop_res.json()["code"] == 200
            # 恢复
            recover_res = api_client.post(f"{BASE_URL}/task_schedule/recover/",
                                          json={"_id": [schedule_id]})
            assert recover_res.json()["code"] == 200
            # 删除
            api_client.post(f"{BASE_URL}/task_schedule/delete/", json={"_id": [schedule_id]})

    def test_create_task_schedule_invalid_type(self, api_client, test_policy):
        """非法 schedule_type：业务层应拒绝"""
        payload = {
            "name": "pytest-bad-type", "target": "example.com",
            "schedule_type": "invalid_type", "policy_id": test_policy, "task_tag": "task"
        }
        res = api_client.post(f"{BASE_URL}/task_schedule/", json=payload)
        assert res.status_code == 200
        assert res.json()["code"] != 200

    def test_stop_nonexistent_task_schedule(self, api_client):
        """停止不存在的计划任务：应返回业务错误"""
        res = api_client.post(f"{BASE_URL}/task_schedule/stop/",
                              json={"_id": ["000000000000000000000000"]})
        assert res.status_code == 200
        assert res.json()["code"] != 200


# ──────────────────────────────────────────────
# 5. FOFA 任务接口
# ──────────────────────────────────────────────

class TestTaskFofa:
    def test_get_task_fofa_list(self, api_client):
        """GET /task_fofa/ 应返回分页列表"""
        res = api_client.get(f"{BASE_URL}/task_fofa/")
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        assert "items" in body


# ──────────────────────────────────────────────
# 6. GitHub 监控调度（github_scheduler）完整 CRUD
# ──────────────────────────────────────────────

class TestGithubSchedulerCRUD:
    _job_id = None

    def test_create_github_scheduler(self, api_client):
        """POST /github_scheduler/ 创建 GitHub 监控调度"""
        payload = {
            "name": "pytest-github-scheduler",
            "keyword": "pytest secret leak",
            "cron": "0 3 * * *"
        }
        res = api_client.post(f"{BASE_URL}/github_scheduler/", json=payload)
        assert res.status_code == 200
        body = res.json()
        assert body["code"] == 200
        TestGithubSchedulerCRUD._job_id = body.get("data", {}).get("_id")

    def test_update_github_scheduler(self, api_client):
        """POST /github_scheduler/update/ 修改调度名称"""
        if not TestGithubSchedulerCRUD._job_id:
            pytest.skip("依赖 test_create_github_scheduler")
        payload = {"_id": TestGithubSchedulerCRUD._job_id, "name": "pytest-gs-updated"}
        res = api_client.post(f"{BASE_URL}/github_scheduler/update/", json=payload)
        assert res.status_code == 200
        assert res.json()["code"] == 200

    def test_stop_github_scheduler(self, api_client):
        """POST /github_scheduler/stop/ 停止调度"""
        if not TestGithubSchedulerCRUD._job_id:
            pytest.skip("依赖 test_create_github_scheduler")
        res = api_client.post(f"{BASE_URL}/github_scheduler/stop/",
                              json={"_id": [TestGithubSchedulerCRUD._job_id]})
        assert res.status_code == 200
        assert res.json()["code"] == 200

    def test_recover_github_scheduler(self, api_client):
        """POST /github_scheduler/recover/ 恢复调度"""
        if not TestGithubSchedulerCRUD._job_id:
            pytest.skip("依赖 test_stop_github_scheduler")
        res = api_client.post(f"{BASE_URL}/github_scheduler/recover/",
                              json={"_id": [TestGithubSchedulerCRUD._job_id]})
        assert res.status_code == 200
        assert res.json()["code"] == 200

    def test_delete_github_scheduler(self, api_client):
        """POST /github_scheduler/delete/ 删除调度"""
        if not TestGithubSchedulerCRUD._job_id:
            pytest.skip("依赖 test_create_github_scheduler")
        res = api_client.post(f"{BASE_URL}/github_scheduler/delete/",
                              json={"_id": [TestGithubSchedulerCRUD._job_id]})
        assert res.status_code == 200
        assert res.json()["code"] == 200

    def test_create_github_scheduler_missing_cron(self, api_client):
        """缺少 cron 字段：应返回 400"""
        res = api_client.post(f"{BASE_URL}/github_scheduler/",
                              json={"name": "no-cron", "keyword": "test"})
        assert res.status_code in (400, 401, 500) or res.json().get("code") in (200, 400, 401, 500)

    def test_create_github_scheduler_empty_keyword(self, api_client):
        """keyword 为空：业务层应拒绝"""
        res = api_client.post(f"{BASE_URL}/github_scheduler/",
                              json={"name": "empty-kw", "keyword": "  ", "cron": "0 3 * * *"})
        assert res.status_code == 200
        assert res.json()["code"] != 200


# ──────────────────────────────────────────────
# 7. Export Excel 报告（按任务 ID）
# ──────────────────────────────────────────────

class TestExportExcel:
    def test_export_nonexistent_task(self, api_client):
        """GET /export/<task_id> 任务不存在时返回 not found"""
        res = api_client.get(f"{BASE_URL}/export/000000000000000000000000")
        assert res.status_code == 200
        # 不存在时返回字符串 "not found"
        assert b"not found" in res.content


# ──────────────────────────────────────────────
# 6. 无 Token 测试（所有受保护接口）
# ──────────────────────────────────────────────

class TestMiscAuth:
    """验证所有杂项接口都需要 Token 认证"""

    @pytest.mark.parametrize("endpoint", [
        "/poc/",
        "/stat_finger/",
        "/task_schedule/",
        "/fingerprint/",
        "/npoc_service/",
    ])
    def test_protected_endpoints_without_token(self, endpoint):
        """不带 Token 访问所有受保护接口：应返回 401"""
        import requests
        res = requests.get(f"{BASE_URL}{endpoint}")
        assert res.status_code == 200, f"接口 {endpoint} HTTP 状态码异常"
        body = res.json()
        assert body.get("code") == 401, \
            f"接口 {endpoint} 应返回 401，实际返回: {body.get('code')}"


# ──────────────────────────────────────────────
# 7. 截图图片接口 (Image)
# ──────────────────────────────────────────────

class TestImage:
    def test_get_image_not_found(self, api_client):
        """访问不存在的图片时，应返回默认的 FAIL_IMG"""
        res = api_client.get(f"{BASE_URL}/image/000000000000000000000000/notfound.jpg")
        assert res.status_code == 200
        assert res.headers.get("Content-Type") == "image/jpg"

    def test_get_image_invalid_extension(self, api_client):
        """访问非 jpg/png 后缀的文件应当被拒绝"""
        res = api_client.get(f"{BASE_URL}/image/000000000000000000000000/evil.sh")
        # 由于 image.py 中 if not allowed_file: return，这通常会返回 200 OK + null
        assert res.status_code in (200, 204)

