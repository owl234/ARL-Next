"""系统更新检查与更新日志获取单元测试。

覆盖以下核心契约：
1. 代理复用：配置 Config.PROXY_URL 时，GitHub API 与 raw.githubusercontent.com 请求必须透传代理；
2. 远端回退：/releases/latest 失败或正文为空且 /tags 返回新版本时，依次回退到 /releases/tags/{tag} 与 raw CHANGELOG(_en).md，绝不拿旧版容器本地日志充数；
3. 离线/已最新：已最新或 GitHub 不可达时正确读取对应语言的本地 CHANGELOG；
4. 多语言拆分：GitHub Release 中英双语正文按 lang 参数精确拆分并兜底回退；
5. 跨 Worker 共享缓存：完整结果缓存 1 小时，降级/空日志仅短缓存 60 秒；本地升级版本大于缓存远端版本时自动穿透失效。
"""
import ast
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import patch

BACKEND_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = BACKEND_ROOT.parent
SERVICE_PATH = BACKEND_ROOT / "app" / "services" / "system_config_service.py"
ROUTE_PATH = BACKEND_ROOT / "app" / "routes" / "system_config.py"


def _load_service_module():
    spec = importlib.util.spec_from_file_location("test_system_config_service_mod", SERVICE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _FakeCollection:
    def __init__(self):
        self.docs = {}

    def find_one(self, query):
        doc = self.docs.get(query.get("_id"))
        return dict(doc) if isinstance(doc, dict) else None

    def update_one(self, query, update, upsert=False):
        doc_id = query.get("_id")
        if doc_id not in self.docs and not upsert:
            return
        cur = dict(self.docs.get(doc_id) or {"_id": doc_id})
        if "$set" in update:
            cur.update(update["$set"])
        self.docs[doc_id] = cur


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

    def json(self):
        return self._json_data


class SystemUpdateChangelogTests(unittest.TestCase):
    def setUp(self):
        self.svc = _load_service_module()
        self.svc._UPDATE_CACHE["timestamp"] = 0
        self.svc._UPDATE_CACHE["data"] = None
        self.fake_col = _FakeCollection()
        self.fake_proxy_url = ""

        app_pkg = types.ModuleType("app")
        app_cfg = types.ModuleType("app.config")
        app_utils = types.ModuleType("app.utils")
        app_conn = types.ModuleType("app.utils.conn")

        class _Config:
            PROXY_URL = ""

        self.ConfigStub = _Config
        app_cfg.Config = _Config
        app_conn.conn_db = lambda name: self.fake_col if name == "system_config" else _FakeCollection()
        app_utils.conn = app_conn
        app_pkg.config = app_cfg
        app_pkg.utils = app_utils
        self.module_stubs = {
            "app": app_pkg,
            "app.config": app_cfg,
            "app.utils": app_utils,
            "app.utils.conn": app_conn,
        }

    def test_extract_changelog_section_handles_prefixes_and_separators(self):
        sample = (
            "# Changelog\n\n---\n\n"
            "## [v1.4.6] - 2026-11-14\n\n"
            "### 🚀 新增功能\n- 特性 A\n\n---\n\n"
            "## [v1.4.0] - 2026-09-24\n\n"
            "### 🚀 新增功能\n- 老特性\n"
        )
        sec_146 = self.svc.extract_changelog_section(sample, "v1.4.6")
        self.assertIn("特性 A", sec_146)
        self.assertNotIn("老特性", sec_146)
        self.assertFalse(sec_146.endswith("---"))

        # 不应把 v1.4 误匹配到 v1.4.6
        self.assertEqual(self.svc.extract_changelog_section(sample, "v1.4"), "")
        # 支持不带 v 前缀匹配
        self.assertIn("特性 A", self.svc.extract_changelog_section(sample, "1.4.6"))

    def test_get_local_changelog_section_respects_locale_with_fallback(self):
        zh_notes = self.svc.get_local_changelog_section("v1.4.6", lang="zh-CN")
        en_notes = self.svc.get_local_changelog_section("v1.4.6", lang="en-US")
        ru_notes = self.svc.get_local_changelog_section("v1.4.6", lang="ru-RU")
        self.assertIn("新增功能", zh_notes)
        self.assertIn("New Features", en_notes)
        self.assertEqual(ru_notes, en_notes)

        # CHANGELOG_en.md 仅追溯到 v1.4.2；更早版本应自动回退到中文 CHANGELOG.md
        old_en_fallback = self.svc.get_local_changelog_section("v1.4.0", lang="en-US")
        self.assertTrue(old_en_fallback)

    def test_proxy_forwarded_when_configured_and_bilingual_body_split(self):
        self.ConfigStub.PROXY_URL = "http://127.0.0.1:7890"
        calls = []
        bilingual_body = (
            "### 🚀 新增功能\n- 中文更新点\n\n---\n\n"
            "### 🚀 New Features\n- English feature\n\n"
            "**Full Changelog**: https://github.com/owl234/ARL-Next/compare/v1.4.5...v1.4.6"
        )

        def fake_get(url, **kwargs):
            calls.append((url, kwargs))
            return _FakeResponse(
                200,
                json_data={
                    "tag_name": "v1.4.6",
                    "body": bilingual_body,
                    "html_url": "https://github.com/owl234/ARL-Next/releases/tag/v1.4.6",
                    "published_at": "2026-11-14T00:00:00Z",
                },
            )

        with patch.dict(sys.modules, self.module_stubs), \
                patch.object(self.svc, "get_local_version_str", return_value="v1.4.5"), \
                patch.object(self.svc.requests, "get", side_effect=fake_get):
            zh_res = self.svc.check_system_update_info(force_refresh=True, lang="zh-CN")
            en_res = self.svc.check_system_update_info(force_refresh=False, lang="en-US")

        self.assertEqual(len(calls), 1)  # 第二次切换语言直接命中共享缓存
        self.assertEqual(calls[0][1]["proxies"], {
            "http": "http://127.0.0.1:7890",
            "https": "http://127.0.0.1:7890",
        })
        self.assertTrue(zh_res["has_new_version"])
        self.assertIn("中文更新点", zh_res["release_notes"])
        self.assertNotIn("English feature", zh_res["release_notes"])
        self.assertTrue(en_res["is_cached"])
        self.assertIn("English feature", en_res["release_notes"])
        self.assertNotIn("中文更新点", en_res["release_notes"])

    def test_tags_fallback_uses_remote_changelog_instead_of_old_local_file(self):
        requested_urls = []

        def fake_get(url, **kwargs):
            requested_urls.append(url)
            if url.endswith("/releases/latest"):
                return _FakeResponse(404)
            if "/tags" in url and "releases/tags" not in url:
                return _FakeResponse(200, json_data=[{"name": "v1.4.6"}, {"name": "v1.4.5"}])
            if url.endswith("/releases/tags/v1.4.6"):
                return _FakeResponse(404)
            if url.endswith("/v1.4.6/CHANGELOG.md"):
                return _FakeResponse(200, text="## [v1.4.6] - 2026-11-14\n\n### 🚀 新增功能\n- 远端新版本特性\n")
            if url.endswith("/v1.4.6/CHANGELOG_en.md"):
                return _FakeResponse(200, text="## [v1.4.6] - 2026-11-14\n\n### 🚀 New Features\n- Remote new feature\n")
            return _FakeResponse(404)

        with patch.dict(sys.modules, self.module_stubs), \
                patch.object(self.svc, "get_local_version_str", return_value="v1.4.5"), \
                patch.object(self.svc.requests, "get", side_effect=fake_get):
            res = self.svc.check_system_update_info(force_refresh=True, lang="zh-CN")

        self.assertTrue(res["has_new_version"])
        self.assertEqual(res["remote_version"], "v1.4.6")
        self.assertFalse(res["notes_unavailable"])
        self.assertIn("远端新版本特性", res["release_notes"])
        self.assertTrue(any(u.endswith("/v1.4.6/CHANGELOG.md") for u in requested_urls))

    def test_empty_remote_notes_does_not_leak_old_local_changelog_and_uses_short_ttl(self):
        def fake_get(url, **kwargs):
            if url.endswith("/releases/latest"):
                return _FakeResponse(200, json_data={"tag_name": "v9.9.9", "body": None})
            return _FakeResponse(404)

        with patch.dict(sys.modules, self.module_stubs), \
                patch.object(self.svc, "get_local_version_str", return_value="v1.4.6"), \
                patch.object(self.svc.requests, "get", side_effect=fake_get), \
                patch.object(self.svc.time, "time", side_effect=[1000.0, 1020.0, 1070.0]):
            first = self.svc.check_system_update_info(force_refresh=False, lang="zh-CN")
            second_cached = self.svc.check_system_update_info(force_refresh=False, lang="zh-CN")
            third_expired = self.svc.check_system_update_info(force_refresh=False, lang="zh-CN")

        self.assertTrue(first["has_new_version"])
        self.assertEqual(first["release_notes"], "")
        self.assertTrue(first["notes_unavailable"])
        self.assertTrue(second_cached["is_cached"])
        # 超过 60s 降级缓存窗口后必须重新请求，而不是锁死 1 小时
        self.assertFalse(third_expired["is_cached"])

    def test_offline_fallback_returns_local_changelog_and_marks_offline(self):
        with patch.dict(sys.modules, self.module_stubs), \
                patch.object(self.svc, "get_local_version_str", return_value="v1.4.6"), \
                patch.object(self.svc.requests, "get", side_effect=TimeoutError("network unreachable")):
            res = self.svc.check_system_update_info(force_refresh=True, lang="zh-CN")

        self.assertTrue(res["is_offline"])
        self.assertFalse(res["has_new_version"])
        self.assertFalse(res["notes_unavailable"])
        self.assertEqual(res["remote_version"], "v1.4.6")
        self.assertIn("新增功能", res["release_notes"])

    def test_shared_mongodb_cache_visible_across_workers_and_invalidated_on_upgrade(self):
        # Worker 1 写入共享缓存
        with patch.dict(sys.modules, self.module_stubs), \
                patch.object(self.svc, "get_local_version_str", return_value="v1.4.5"), \
                patch.object(self.svc.requests, "get", return_value=_FakeResponse(
                    200, json_data={"tag_name": "v1.4.6", "body": "### 🚀 新增功能\n- 共享缓存日志"}
                )):
            w1 = self.svc.check_system_update_info(force_refresh=True, lang="zh-CN")

        self.assertFalse(w1["is_cached"])

        # Worker 2（全新模块实例，进程内存缓存为空）应直接命中 MongoDB 共享缓存
        worker2_svc = _load_service_module()
        with patch.dict(sys.modules, self.module_stubs), \
                patch.object(worker2_svc, "get_local_version_str", return_value="v1.4.5"), \
                patch.object(worker2_svc.requests, "get", side_effect=AssertionError("should hit shared cache")):
            w2 = worker2_svc.check_system_update_info(force_refresh=False, lang="zh-CN")

        self.assertTrue(w2["is_cached"])
        self.assertIn("共享缓存日志", w2["release_notes"])

        # 容器升级到高于缓存远端版本的 v1.4.7 后，应自动穿透旧缓存
        calls = []

        def fake_get_new(url, **kwargs):
            calls.append(url)
            return _FakeResponse(200, json_data={"tag_name": "v1.4.7", "body": "### 🚀 新增功能\n- v1.4.7 新版日志"})

        with patch.dict(sys.modules, self.module_stubs), \
                patch.object(worker2_svc, "get_local_version_str", return_value="v1.4.7"), \
                patch.object(worker2_svc.requests, "get", side_effect=fake_get_new):
            upgraded = worker2_svc.check_system_update_info(force_refresh=False, lang="zh-CN")

        self.assertFalse(upgraded["is_cached"])
        self.assertEqual(len(calls), 1)
        self.assertEqual(upgraded["remote_version"], "v1.4.7")

    def test_route_passes_lang_and_refresh_arguments(self):
        tree = ast.parse(ROUTE_PATH.read_text(encoding="utf-8"))
        cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "CheckUpdate")
        fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == "get")
        src = ast.get_source_segment(ROUTE_PATH.read_text(encoding="utf-8"), fn)
        self.assertIn("flask_req.args.get('lang'", src)
        self.assertIn("check_system_update_info(force_refresh=force_refresh, lang=lang)", src)


if __name__ == "__main__":
    unittest.main()
