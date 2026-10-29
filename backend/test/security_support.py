"""Isolated real-route fixtures: MongoDB and deployment are never contacted."""

import ast
import hashlib
import importlib.util
import logging
from pathlib import Path
import sys
import types
from unittest.mock import Mock, MagicMock

from flask import Flask
from flask_restx import Api
import mongomock
import pytest


ROOT = Path(__file__).resolve().parents[1]


def load_source(monkeypatch, name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    parent, _, child = name.rpartition('.')
    if parent in sys.modules:
        monkeypatch.setattr(sys.modules[parent], child, module, raising=False)
    return module


@pytest.fixture
def app_env(monkeypatch, tmp_path):
    for name in ('app', 'app.utils', 'app.services', 'app.routes'):
        module = types.ModuleType(name)
        module.__path__ = []
        monkeypatch.setitem(sys.modules, name, module)
    utils = sys.modules['app.utils']
    sys.modules['app'].utils = utils
    cfg = types.ModuleType('app.config')
    cfg.Config = types.SimpleNamespace(AUTH=True, API_KEY='fixture-api-key', PROXY_URL='',
                                      MONGO_URL='mongodb://unused.invalid', MONGO_DB='arl',
                                      SCREENSHOT_DIR=str(tmp_path / 'screenshots'),
                                      SCREENSHOT_FAIL_IMG=str(tmp_path / 'fallback.jpg'))
    cfg.basedir = str(tmp_path / 'app')
    Path(cfg.basedir).mkdir()
    cfg.clear_system_config_cache = Mock()
    cfg.bump_system_config_version = Mock()
    monkeypatch.setitem(sys.modules, 'app.config', cfg)
    db = mongomock.MongoClient().arl
    conn = types.ModuleType('app.utils.conn')
    conn.conn_db = lambda name: db[name]
    conn.ConnMongo = Mock(side_effect=AssertionError('Real DB access forbidden'))
    monkeypatch.setitem(sys.modules, conn.__name__, conn)
    utils.conn_db = conn.conn_db
    utils.gen_md5 = lambda value: hashlib.md5(value.encode()).hexdigest()
    utils.get_logger = lambda *a: logging.getLogger('security-test')
    utils.curr_date = lambda: '2026-10-28 12:00:00'
    credentials = load_source(monkeypatch, 'app.utils.credentials', 'app/utils/credentials.py')
    user = load_source(monkeypatch, 'app.utils.user', 'app/utils/user.py')
    for name in ('auth', 'user_login', 'user_login_header', 'user_logout', 'user_refresh_token', 'change_pass'):
        setattr(utils, name, getattr(user, name))
    load_source(monkeypatch, 'app.utils.download_ticket', 'app/utils/download_ticket.py')
    load_source(monkeypatch, 'app.mcp_asset', 'app/mcp_asset.py')
    load_source(monkeypatch, 'app.mcp_security', 'app/mcp_security.py')
    arlupdate = types.ModuleType('app.utils.arlupdate')
    arlupdate.create_index = Mock()
    monkeypatch.setitem(sys.modules, arlupdate.__name__, arlupdate)
    exporter = types.ModuleType('app.utils.wih_export')
    exporter.format_wih_export = Mock()
    monkeypatch.setitem(sys.modules, exporter.__name__, exporter)
    routes = sys.modules['app.routes']
    nodes = []
    for node in ast.parse((ROOT / 'app/routes/__init__.py').read_text()).body:
        if isinstance(node, ast.ImportFrom) and node.level == 1:
            break
        nodes.append(node)
    exec(compile(ast.Module(body=nodes, type_ignores=[]), 'route-base', 'exec'), routes.__dict__)
    return types.SimpleNamespace(cfg=cfg, user=user, utils=utils, db=db,
                                 credentials=credentials, tmp=tmp_path, monkeypatch=monkeypatch)


def make_client(env, *namespaces):
    web = Flask('security-tests')
    web.config['TESTING'] = True
    api = Api(web, prefix='/api', doc=False)
    for ns in namespaces:
        api.add_namespace(ns)

    @web.get('/protected')
    @env.user.auth
    def protected():
        return {'code': 200}

    return web.test_client()


def load_backup(env):
    load_source(env.monkeypatch, 'app.services.backup_archive', 'app/services/backup_archive.py')
    load_source(env.monkeypatch, 'app.services.backup_workers', 'app/services/backup_workers.py')
    module = load_source(env.monkeypatch, 'app.services.backup_service', 'app/services/backup_service.py')
    module.STATUS_FILE = str(env.tmp / 'backup-status.json')
    module.progress_tracker = module.BackupProgressTracker()
    backup_dir = env.tmp / 'backups'
    backup_dir.mkdir()
    module.get_backup_dir = lambda: str(backup_dir)
    module.get_running_task_count = lambda: 0
    module.RestoreWorkers = MagicMock()
    module.find_tool = Mock(return_value='/not-executed/mongorestore')
    module.run_command_streaming = Mock()
    module.get_all_collection_counts = lambda: {'collections': {}, 'summary': {}, 'total_documents': 0, 'total_collections': 0}
    return module, backup_dir
