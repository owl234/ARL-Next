"""Tests for GitHub monitor backend triage, threat radar, scheduler & dashboard fixes."""

import json
import sys
import types
from unittest.mock import Mock, patch

from bson import ObjectId

from security_support import ROOT, app_env, load_source, make_client


def _setup_github_env(app_env):
    """Load real modules needed for GitHub triage, routes, and dashboard tests."""
    app_env.cfg.Config.DOMAIN_DICT_2W = ""
    app_env.cfg.Config.GITHUB_TOKEN = ""
    utils = app_env.utils
    utils.http_req = Mock()
    utils.build_ret = lambda msg, data=None: {
        "code": msg["code"],
        "message": msg["message"],
        "data": {} if data is None else data,
    }
    utils.check_cron_interval = lambda cron: (True, "")
    utils.check_cron = lambda cron: (0, 1800, 0)
    utils.time2date = lambda ts: "2026-11-16 12:30:00"
    utils.curr_date_obj = lambda: "2026-11-16 12:00:00"

    # Load real ErrorMsg / TaskStatus / SchedulerStatus
    modules_mod = load_source(app_env.monkeypatch, "app.modules", "app/modules/__init__.py")
    app_env.monkeypatch.setitem(sys.modules, "app.modules", modules_mod)

    celery_mod = types.ModuleType("app.celerytask")
    celery_mod.CeleryAction = modules_mod.CeleryAction
    celery_mod.celery = types.SimpleNamespace(control=types.SimpleNamespace(revoke=Mock()))
    celery_mod.arl_github = types.SimpleNamespace(delay=Mock(return_value="celery-gh-1"))
    app_env.monkeypatch.setitem(sys.modules, "app.celerytask", celery_mod)

    triage_mod = load_source(app_env.monkeypatch, "app.services.github_triage", "app/services/github_triage.py")
    gh_task_util = load_source(app_env.monkeypatch, "app.utils.github_task", "app/utils/github_task.py")
    utils.github_task = gh_task_util

    gh_result_route = load_source(app_env.monkeypatch, "app.routes.github_result", "app/routes/github_result.py")
    gh_mon_result_route = load_source(
        app_env.monkeypatch, "app.routes.github_monitor_result", "app/routes/github_monitor_result.py"
    )
    gh_scheduler_route = load_source(
        app_env.monkeypatch, "app.routes.github_scheduler", "app/routes/github_scheduler.py"
    )
    gh_task_route = load_source(app_env.monkeypatch, "app.routes.github_task", "app/routes/github_task.py")
    gh_threat_route = load_source(app_env.monkeypatch, "app.routes.github_threat", "app/routes/github_threat.py")
    dash_route = load_source(app_env.monkeypatch, "app.routes.dashboard", "app/routes/dashboard.py")

    return types.SimpleNamespace(
        triage=triage_mod,
        gh_task_util=gh_task_util,
        gh_result_route=gh_result_route,
        gh_mon_result_route=gh_mon_result_route,
        gh_scheduler_route=gh_scheduler_route,
        gh_task_route=gh_task_route,
        gh_threat_route=gh_threat_route,
        dash_route=dash_route,
        celery_mod=celery_mod,
    )


def _auth_headers():
    return {"Token": "fixture-api-key"}


def test_triage_overview_dedup_repo_group_ignore_and_export(app_env):
    mods = _setup_github_env(app_env)
    client = make_client(
        app_env,
        mods.gh_result_route.ns,
        mods.gh_mon_result_route.ns,
    )

    sched_id = str(ObjectId())
    task_cron_id = str(ObjectId())
    task_manual_id = str(ObjectId())
    app_env.db.github_scheduler.insert_one({"_id": ObjectId(sched_id), "name": "核心域名监控", "keyword": "example.com"})
    app_env.db.github_task.insert_many([
        {"_id": ObjectId(task_cron_id), "name": "GitHub监控-核心域名监控", "github_scheduler_id": sched_id},
        {"_id": ObjectId(task_manual_id), "name": "单次泄露排查", "keyword": "example.com secret"},
    ])

    h_same = "hash-same-file"
    h_other = "hash-other-file"
    h_noisy = "hash-noisy-repo"

    # Same finding appears in both github_result (via cron task) and github_monitor_result
    app_env.db.github_result.insert_many([
        {
            "repo_full_name": "acme/backend-api",
            "path": "config/.env",
            "hash_md5": h_same,
            "human_content": "DB_PASS=supersecret123",
            "keyword": "example.com",
            "commit_date": "2026-11-16 10:00:00",
            "github_task_id": task_cron_id,
            "html_url": "https://github.com/acme/backend-api/blob/main/config/.env",
        },
        {
            "repo_full_name": "acme/backend-api",
            "path": "src/settings.py",
            "hash_md5": h_other,
            "human_content": "API_KEY = 'AKIA1234567890'",
            "keyword": "example.com secret",
            "commit_date": "2026-11-16 09:00:00",
            "github_task_id": task_manual_id,
            "html_url": "https://github.com/acme/backend-api/blob/main/src/settings.py",
        },
        {
            "repo_full_name": "=cmd|' /C calc'!A0/mirror",
            "path": "list.txt",
            "hash_md5": h_noisy,
            "human_content": "=1+1",
            "keyword": "example.com",
            "commit_date": "2026-11-15 08:00:00",
            "github_task_id": task_manual_id,
        },
    ])
    app_env.db.github_monitor_result.insert_one({
        "repo_full_name": "acme/backend-api",
        "path": "config/.env",
        "hash_md5": h_same,
        "human_content": "DB_PASS=supersecret123",
        "keyword": "example.com",
        "commit_date": "2026-11-16 10:00:00",
        "github_scheduler_id": sched_id,
        "html_url": "https://github.com/acme/backend-api/blob/main/config/.env",
    })

    # 1. Overview deduplicates h_same across both collections -> 3 unique files
    res = client.get("/api/github_result/overview/?page=1&size=10", headers=_auth_headers())
    assert res.status_code == 200
    data = res.json["data"]
    assert data["total"] == 3
    hashes = [item["hash_md5"] for item in data["items"]]
    assert len(set(hashes)) == 3

    # 2. Triage status propagation across both collections + persistence table
    triage_res = client.post(
        "/api/github_result/triage/",
        headers=_auth_headers(),
        json={"hash_md5s": [h_same], "triage_status": "confirmed", "note": "真实库密码"},
    )
    assert triage_res.status_code == 200
    assert triage_res.json["code"] == 200
    assert app_env.db.github_triage.find_one({"hash_md5": h_same})["triage_status"] == "confirmed"
    assert app_env.db.github_monitor_result.find_one({"hash_md5": h_same})["triage_status"] == "confirmed"

    # 3. Repo-grouped mode collapses acme/backend-api into 1 group with 2 files
    grp_res = client.get("/api/github_result/overview/?group_by=repo", headers=_auth_headers())
    assert grp_res.status_code == 200
    groups = grp_res.json["data"]["items"]
    acme_group = next(g for g in groups if g["repo_full_name"] == "acme/backend-api")
    assert acme_group["file_count"] == 2
    assert acme_group["confirmed_count"] == 1
    assert acme_group["pending_count"] == 1

    # 4. Ignore repo hides it from default view & stats, and surfaces in only_ignored=true
    ign_res = client.post(
        "/api/github_result/ignored_repos/",
        headers=_auth_headers(),
        json={"action": "add", "repo_full_names": ["https://github.com/acme/backend-api"]},
    )
    assert ign_res.status_code == 200
    assert ign_res.json["data"]["repos"] == ["acme/backend-api"]

    after_ign = client.get("/api/github_result/overview/", headers=_auth_headers()).json["data"]
    assert after_ign["total"] == 1
    assert after_ign["items"][0]["hash_md5"] == h_noisy

    only_ign = client.get("/api/github_result/overview/?only_ignored=true", headers=_auth_headers()).json["data"]
    assert only_ign["total"] == 2

    stats = client.get("/api/github_result/stats/", headers=_auth_headers()).json["data"]
    assert stats["ignored_repos"] == 1
    assert stats["pending"] == 1  # only h_noisy is non-ignored

    # 5. CSV export escapes formula prefixes safely
    csv_res = client.get("/api/github_result/export/?format=csv", headers=_auth_headers())
    assert csv_res.status_code == 200
    csv_text = csv_res.data.decode("utf-8")
    assert "'=cmd|" in csv_text
    assert "'=1+1" in csv_text

    # 6. JSON export returns structured JSON
    json_res = client.get("/api/github_result/export/?format=json", headers=_auth_headers())
    assert json_res.status_code == 200
    exported = json.loads(json_res.data.decode("utf-8"))
    assert len(exported) == 1
    assert exported[0]["hash_md5"] == h_noisy


def test_scheduler_run_now_counts_and_task_source_type(app_env):
    mods = _setup_github_env(app_env)
    client = make_client(app_env, mods.gh_scheduler_route.ns, mods.gh_task_route.ns)

    sid = str(ObjectId())
    app_env.db.github_scheduler.insert_one({
        "_id": ObjectId(sid),
        "name": "域名周期监控",
        "keyword": "corp.example",
        "cron": "*/30 * * * *",
        "run_number": 0,
        "last_run_date": "-",
        "last_run_time": 0,
        "next_run_date": "2026-11-16 12:30:00",
        "status": "running",
    })
    app_env.db.github_monitor_result.insert_one({"github_scheduler_id": sid, "hash_md5": "h1"})

    # Trigger immediate run
    run_res = client.post("/api/github_scheduler/run/", headers=_auth_headers(), json={"_id": [sid]})
    assert run_res.status_code == 200
    assert run_res.json["code"] == 200
    assert len(run_res.json["data"]["task_id_list"]) == 1
    assert app_env.db.github_scheduler.find_one({"_id": ObjectId(sid)})["run_number"] == 1

    # Scheduler GET includes result_count
    sched_list = client.get("/api/github_scheduler/", headers=_auth_headers()).json["items"]
    assert sched_list[0]["result_count"] == 1

    # Insert one manual task and test source_type filtering
    app_env.db.github_task.insert_one({
        "name": "手动单次任务",
        "keyword": "manual.example",
        "status": "done",
        "start_time": "2026-11-16 11:00:00",
        "end_time": "2026-11-16 11:05:00",
    })
    all_tasks = client.get("/api/github_task/", headers=_auth_headers()).json["items"]
    assert len(all_tasks) == 2
    assert {t["source_type"] for t in all_tasks} == {"task", "scheduler"}

    manual_only = client.get("/api/github_task/?source_type=task", headers=_auth_headers()).json["items"]
    assert len(manual_only) == 1
    assert manual_only[0]["source_type"] == "task"

    sched_only = client.get("/api/github_task/?source_type=scheduler", headers=_auth_headers()).json["items"]
    assert len(sched_only) == 1
    assert sched_only[0]["source_type"] == "scheduler"


def test_github_threat_routes_proxy_quota_batch_and_filtering(app_env):
    mods = _setup_github_env(app_env)
    from flask import Flask
    web = Flask("threat-test")
    web.config["TESTING"] = True
    web.register_blueprint(mods.gh_threat_route.github_threat_bp, url_prefix="/api/github_threat")
    client = web.test_client()

    # 1. Token status uses intel proxy and returns both core and search quotas
    app_env.cfg.Config.GITHUB_TOKEN = "ghp_fixture"
    mods.gh_threat_route.utils.http_req.return_value = types.SimpleNamespace(
        status_code=200,
        json=lambda: {
            "resources": {
                "core": {"remaining": 4800, "limit": 5000, "reset": 1700000000},
                "search": {"remaining": 0, "limit": 30, "reset": 1700000060},
            }
        },
    )
    tok_res = client.get("/api/github_threat/token_status", headers=_auth_headers())
    assert tok_res.status_code == 200
    tok_data = tok_res.json["data"]
    assert tok_data["status"] == "rate_limited"
    assert tok_data["core"]["remaining"] == 4800
    assert tok_data["search"]["remaining"] == 0
    assert mods.gh_threat_route.utils.http_req.call_args.kwargs["proxy_domain"] == "intel"

    # 2. Batch add tools with flexible normalization
    tools_res = client.post(
        "/api/github_threat/tools_target",
        headers=_auth_headers(),
        json={"repo_urls": [
            "https://github.com/chaitin/xray/releases",
            "projectdiscovery/nuclei",
            "https://github.com/chaitin/xray.git",
            "invalid-input",
        ]},
    )
    assert tools_res.status_code == 200
    assert tools_res.json["data"]["added"] == 2
    assert tools_res.json["data"]["skipped"] == 1
    assert tools_res.json["data"]["invalid"] == 1

    # 3. Hackers batch add + history filtering by github_id and q
    hackers_res = client.post(
        "/api/github_threat/hackers_target",
        headers=_auth_headers(),
        json={"github_ids": ["https://github.com/knownsec", "@projectdiscovery"]},
    )
    assert hackers_res.json["data"]["added"] == 2

    app_env.db.github_hackers_history.insert_many([
        {"full_name": "knownsec/pocsuite3", "description": "PoC framework", "language": "Python", "insert_time": "2026-11-16 10:00:00"},
        {"full_name": "projectdiscovery/nuclei", "description": "YAML scanner", "language": "Go", "insert_time": "2026-11-16 11:00:00"},
    ])
    filtered = client.get("/api/github_threat/hackers_history?github_id=knownsec", headers=_auth_headers()).json["data"]
    assert len(filtered) == 1
    assert filtered[0]["full_name"] == "knownsec/pocsuite3"

    q_filtered = client.get("/api/github_threat/hackers_history?q=YAML", headers=_auth_headers()).json["data"]
    assert len(q_filtered) == 1
    assert q_filtered[0]["full_name"] == "projectdiscovery/nuclei"


def test_github_threat_monitors_persist_release_notes_and_repo_metadata(app_env):
    _setup_github_env(app_env)
    app_env.monkeypatch.setitem(sys.modules, "app.utils.push", types.SimpleNamespace(unified_push=Mock()))
    monitor_mod = load_source(app_env.monkeypatch, "app.tasks.github_threat_monitor", "app/tasks/github_threat_monitor.py")

    app_env.db.github_tools_target.insert_one({
        "repo_url": "https://api.github.com/repos/projectdiscovery/nuclei",
        "last_tag": "v3.3.0",
        "last_commit_time": "2026-11-01",
    })
    app_env.db.github_hackers_target.insert_one({"github_id": "knownsec"})

    from datetime import datetime, timezone
    recent_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    def fake_http_req(url, **kwargs):
        if url.endswith("/releases"):
            return types.SimpleNamespace(
                status_code=200,
                json=lambda: [{
                    "tag_name": "v3.3.0",
                    "published_at": "2026-11-01T00:00:00Z",
                    "html_url": "https://github.com/projectdiscovery/nuclei/releases/tag/v3.3.0",
                    "name": "Nuclei v3.3.0",
                    "body": "### What's Changed\n- Added templates",
                }],
            )
        if "/users/knownsec/repos" in url:
            return types.SimpleNamespace(
                status_code=200,
                json=lambda: [{
                    "full_name": "knownsec/new-tool",
                    "name": "new-tool",
                    "fork": False,
                    "created_at": recent_iso,
                    "html_url": "https://github.com/knownsec/new-tool",
                    "description": "Recon utility",
                    "language": "Python",
                    "stargazers_count": 42,
                }],
            )
        return None

    with patch.object(monitor_mod.utils, "http_req", side_effect=fake_http_req):
        monitor_mod.GithubToolsMonitorTask().run()
        monitor_mod.GithubHackersMonitorTask().run()

    tool_doc = app_env.db.github_tools_target.find_one({"repo_url": "https://api.github.com/repos/projectdiscovery/nuclei"})
    assert "Added templates" in tool_doc["release_notes"]
    assert tool_doc["release_url"].endswith("/v3.3.0")

    hist_doc = app_env.db.github_hackers_history.find_one({"full_name": "knownsec/new-tool"})
    assert hist_doc["description"] == "Recon utility"
    assert hist_doc["language"] == "Python"
    assert hist_doc["stargazers_count"] == 42


def test_dashboard_stats_counts_github_scheduler(app_env):
    mods = _setup_github_env(app_env)
    client = make_client(app_env, mods.dash_route.ns)
    app_env.db.github_scheduler.insert_many([{"name": "p1"}, {"name": "p2"}])

    res = client.get("/api/dashboard/stats", headers=_auth_headers())
    assert res.status_code == 200
    assert res.json["data"]["github_monitors"] == 2
