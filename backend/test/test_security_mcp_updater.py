import ast
import csv
import importlib.util
import io
import json
from pathlib import Path
import threading
import time
import types
from unittest.mock import Mock
from http.server import ThreadingHTTPServer

import pytest
import requests

from security_support import ROOT, app_env, load_source, make_client


@pytest.mark.parametrize('value', ['=1+1', '+SUM(1,1)', '-1+1', '@SUM(1)', '\t=1+1', '\r=1+1', '\n=1+1', '  =1+1'])
def test_csv_formula_prefixes_are_literal(app_env, value):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    app_env.db.site.insert_one({'task_id': '0' * 24, 'title': value})
    client = make_client(app_env, route.ns)
    response = client.get('/api/mcp/task_detail_export', headers={'Token': 'fixture-api-key'},
                          query_string={'task_id': '0' * 24, 'tab': 'site', 'columns': 'title'})
    assert list(csv.reader(io.StringIO(response.get_data(as_text=True)))) == [['title'], ["'" + value]]


@pytest.mark.parametrize('host', ['https://example.test"; MARKER=True #', 'javascript:alert(1)',
                                 'https://user:pass@example.test', 'https://example.test/path',
                                 'https://example.test:0', 'https://example.test/?query=1'])
def test_mcp_unsafe_host_is_rejected(app_env, host):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    response = make_client(app_env, route.ns).get('/api/mcp/export_server',
                                                headers={'Token': 'fixture-api-key'}, query_string={'host': host})
    assert response.status_code == 400


def test_mcp_export_serializes_custom_api_key_as_data(app_env):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    token = 'fixture"; MARKER=True #\\tail'
    app_env.cfg.Config.API_KEY = token
    response = make_client(app_env, route.ns).get('/api/mcp/export_server', headers={'Token': token},
                                                query_string={'host': 'https://example.test:5173'})
    assert response.status_code == 200
    tree = ast.parse(response.get_data(as_text=True))
    constants = {n.targets[0].id: n.value.value for n in tree.body
                 if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name)
                 and isinstance(n.value, ast.Constant)}
    assert constants['DEFAULT_HOST'] == 'https://example.test:5173'
    assert constants['DEFAULT_TOKEN'] == token
    assert 'MARKER' not in constants


def test_csv_formula_headers_are_literal(app_env):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    app_env.db.site.insert_one({'task_id': '0' * 24, 'title': 'ordinary title'})
    response = make_client(app_env, route.ns).get('/api/mcp/task_detail_export',
        headers={'Token': 'fixture-api-key'}, query_string={'task_id': '0' * 24, 'columns': '=1+1,title'})
    rows = list(csv.reader(io.StringIO(response.get_data(as_text=True))))
    assert rows == [["'=1+1", 'title'], ['', 'ordinary title']]


@pytest.fixture
def updater(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location('security_updater', ROOT.parent / 'updater/updater.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.READ_TOKEN_FILE = str(tmp_path / 'state/read_token.json')
    module.LOG_FILE = str(tmp_path / 'update.log')
    Path(module.LOG_FILE).write_text('private log fixture\n')
    return module


def test_updater_read_token_expiry_rotation_and_persistence(updater):
    token = updater.issue_log_token()
    assert updater.verify_log_token(token)
    assert token not in Path(updater.READ_TOKEN_FILE).read_text()
    assert Path(updater.READ_TOKEN_FILE).stat().st_mode & 0o777 == 0o600
    newer = updater.issue_log_token()
    assert not updater.verify_log_token(token)
    assert updater.verify_log_token(newer)
    record = json.loads(Path(updater.READ_TOKEN_FILE).read_text())
    record['expires_at'] = time.time() - 1
    Path(updater.READ_TOKEN_FILE).write_text(json.dumps(record))
    assert not updater.verify_log_token(newer)


def test_updater_control_status_scopes_and_expiry(updater, monkeypatch):
    handler = object.__new__(updater.PollingHandler)
    token = 'fixture-' + 'x' * 40
    record = {'token': token, 'purpose': 'status', 'expires_at': time.time() + 300}
    runner = Mock(return_value=types.SimpleNamespace(returncode=0, stdout=json.dumps(record)))
    monkeypatch.setattr(updater.subprocess, 'run', runner)
    assert handler.verify_token(token, purpose='status')
    assert not handler.verify_token(token, purpose='control')
    record['expires_at'] = time.time() - 1
    runner.return_value.stdout = json.dumps(record)
    assert not handler.verify_token(token, purpose='status')
    assert not handler._authorize_token('')


def test_updater_public_log_and_get_mutations_are_denied(updater, monkeypatch):
    # Any unexpected Docker/host command fails the test.
    monkeypatch.setattr(updater.subprocess, 'run', Mock(side_effect=AssertionError('No host commands allowed')))
    server = ThreadingHTTPServer(('127.0.0.1', 0), updater.PollingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        base = f'http://127.0.0.1:{server.server_port}'
        assert requests.get(base + '/update/log?offset=0', timeout=3).status_code == 403
        assert requests.get(base + '/update/trigger?token=ignored', timeout=3).status_code == 405
        assert requests.get(base + '/update/auth_status', timeout=3).status_code == 403
        token = updater.issue_log_token()
        response = requests.get(base + '/update/log?offset=0', headers={'X-Update-Read-Token': token}, timeout=3)
        assert response.status_code == 200
        assert response.json()['chunk'] == 'private log fixture\n'
        assert 'Access-Control-Allow-Origin' not in response.headers
        assert requests.get(base + '/update/log?token=' + token, timeout=3).status_code == 403
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_bootstrap_password_random_private_and_existing_accounts_preserved(app_env, capsys):
    module = load_source(app_env.monkeypatch, 'security_bootstrap', 'inject_user.py')
    path = app_env.tmp / 'initial-password'
    module.ensure_admin(app_env.db.user, password_file=str(path))
    password = path.read_text().strip()
    assert len(password) >= 24
    assert password not in capsys.readouterr().out
    assert path.stat().st_mode & 0o777 == 0o600
    user = app_env.db.user.find_one({'username': 'admin'})
    assert app_env.credentials.verify_password(user['password'], password)
    module.ensure_admin(app_env.db.user, password='ignored-password', password_file=str(path))
    assert app_env.db.user.find_one()['password'] == user['password']
    app_env.db.user.update_one({'username': 'admin'}, {'$set': {'token': 'old-session'}})
    module.ensure_admin(app_env.db.user, reset=True, password='new-fixture-password', password_file=str(path))
    assert app_env.db.user.find_one()['token'] is None
    assert app_env.credentials.verify_password(app_env.db.user.find_one()['password'], 'new-fixture-password')
    assert not path.exists()


def test_mcp_governance_keys_crud(app_env):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    client = make_client(app_env, route.ns)

    # 1. 创建 Key
    res = client.post('/api/mcp/keys', headers={'Token': 'fixture-api-key'}, json={
        'name': 'Test Cursor Key',
        'scopes': ['asset:read'],
        'expire_days': 30
    })
    assert res.status_code == 200
    data = res.get_json()['data']
    key_id = data['id']
    raw_key = data['raw_key']
    assert raw_key.startswith('arl_mcp_')

    # 2. 查询 Key 列表
    res_list = client.get('/api/mcp/keys', headers={'Token': 'fixture-api-key'})
    assert res_list.status_code == 200
    items = res_list.get_json()['data']['items']
    assert len(items) == 1
    assert items[0]['name'] == 'Test Cursor Key'
    assert items[0]['status'] == 'active'

    # 3. 吊销 Key
    res_status = client.post(f'/api/mcp/keys/{key_id}/status', headers={'Token': 'fixture-api-key'}, json={'status': 'revoked'})
    assert res_status.status_code == 200

    # 验证状态变更为 revoked
    key_in_db = app_env.db.mcp_key.find_one({'name': 'Test Cursor Key'})
    assert key_in_db['status'] == 'revoked'

    # 4. 删除 Key
    res_del = client.delete(f'/api/mcp/keys/{key_id}', headers={'Token': 'fixture-api-key'})
    assert res_del.status_code == 200
    assert app_env.db.mcp_key.count_documents({}) == 0


def test_mcp_governance_logs_and_config(app_env):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    client = make_client(app_env, route.ns)

    # 插入模拟日志
    from datetime import datetime, timezone
    app_env.db.mcp_log.insert_one({
        'key_id': 'legacy',
        'key_name': '[Legacy Token]',
        'client_ip': '127.0.0.1',
        'tool_name': 'get_asset_profile',
        'target': 'example.com',
        'status': 'success',
        'duration_ms': 45,
        'summary': '命中资产',
        'error_message': '',
        'created_at': datetime.now(timezone.utc)
    })
    app_env.db.mcp_log.insert_one({
        'key_id': 'legacy',
        'key_name': '[Legacy Token]',
        'client_ip': '127.0.0.1',
        'tool_name': 'create_scan_task',
        'target': 'test.org',
        'status': 'denied',
        'duration_ms': 12,
        'summary': '未授权调用',
        'error_message': 'Scope task:dispatch required',
        'created_at': datetime.now(timezone.utc)
    })

    # 查询 Overview
    res_ov = client.get('/api/mcp/overview', headers={'Token': 'fixture-api-key'})
    assert res_ov.status_code == 200
    ov_data = res_ov.get_json()['data']
    assert ov_data['today_calls'] >= 2
    assert ov_data['error_calls_24h'] >= 1
    assert ov_data['service_status'] == 'running'

    # 查询 Logs 列表
    res_logs = client.get('/api/mcp/logs', headers={'Token': 'fixture-api-key'}, query_string={'tool_name': 'get_asset_profile'})
    assert res_logs.status_code == 200
    logs_data = res_logs.get_json()['data']
    assert logs_data['total'] == 1
    assert logs_data['items'][0]['target'] == 'example.com'

    # 联动聚合筛选: time_range=today & status=abnormal
    res_abnormal = client.get('/api/mcp/logs', headers={'Token': 'fixture-api-key'}, query_string={'time_range': 'today', 'status': 'abnormal'})
    assert res_abnormal.status_code == 200
    ab_data = res_abnormal.get_json()['data']
    assert ab_data['total'] == 1
    assert ab_data['items'][0]['status'] == 'denied'

    # 导出 Logs CSV
    res_export = client.get('/api/mcp/logs/export', headers={'Token': 'fixture-api-key'})
    assert res_export.status_code == 200
    assert 'text/csv' in res_export.headers['Content-Type']
    csv_content = res_export.get_data(as_text=True)
    assert 'example.com' in csv_content

    # 配置查询与修改
    res_cfg = client.get('/api/mcp/config', headers={'Token': 'fixture-api-key'})
    assert res_cfg.status_code == 200
    cfg_data = res_cfg.get_json()['data']
    assert 'tool_switches' in cfg_data

    # 修改配置
    res_save = client.post('/api/mcp/config', headers={'Token': 'fixture-api-key'}, json={
        'tool_switches': {'get_asset_profile': True, 'create_scan_task': True},
        'max_search_limit': 100,
        'rate_limit_per_min': 200
    })
    assert res_save.status_code == 200

    saved_cfg = app_env.db.mcp_config.find_one({'_id': 'global'})
    assert saved_cfg['max_search_limit'] == 100
    assert saved_cfg['tool_switches']['create_scan_task'] is True
