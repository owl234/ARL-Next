"""MCP regressions using real handlers, an in-memory DB and no scan traffic."""

import ast
import asyncio
import hashlib
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, Mock

import pytest
from security_support import app_env as _app_env
from security_support import load_source, make_client

app_env = _app_env


@pytest.fixture
def mcp(app_env):
    module = load_source(app_env.monkeypatch, 'app.mcp_server', 'app/mcp_server.py')
    server = module.MCPServer()
    server._record_audit_log = AsyncMock()
    return module, server


def create_key(env, *, scopes=None, expires=None, suffix='a'):
    token = 'arl_mcp_' + suffix * 32
    key_id = env.db.mcp_key.insert_one({
        'name': 'fixture', 'key_hash': hashlib.sha256(token.encode()).hexdigest(),
        'status': 'active', 'scopes': scopes if scopes is not None else ['asset:read'],
        'expire_at': expires,
    }).inserted_id
    return token, key_id


class MemoryWriter:
    def __init__(self):
        self.output = bytearray()
    def get_extra_info(self, name):
        return ('127.0.0.1', 12345)
    def write(self, data):
        self.output.extend(data)
    async def drain(self):
        pass
    def close(self):
        pass
    async def wait_closed(self):
        pass


async def post_message(server, session_id, token=None, method='tools/call'):
    body = json.dumps({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': {
        'name': 'get_asset_profile', 'arguments': {'target': 'example.test'}}}).encode()
    header = f'Token: {token}\r\n' if token is not None else ''
    reader = asyncio.StreamReader()
    reader.feed_data((f'POST /mcp/message?sessionId={session_id} HTTP/1.1\r\n'
                     f'Host: fixture\r\n{header}Content-Length: {len(body)}\r\n\r\n').encode() + body)
    reader.feed_eof()
    writer = MemoryWriter()
    await server.handle_client(reader, writer)
    return bytes(writer.output)


@pytest.mark.parametrize('change', ['revoke', 'delete', 'expire'])
@pytest.mark.parametrize('include_token', [False, True])
def test_existing_sessions_recheck_credentials(app_env, mcp, change, include_token):
    module, server = mcp
    token, key_id = create_key(app_env)
    session = module.MCPSession('fixture', server.authenticate_token(token))
    server.sessions['fixture'] = session
    if change == 'delete':
        app_env.db.mcp_key.delete_one({'_id': key_id})
    else:
        values = {'status': 'revoked'} if change == 'revoke' else {'expire_at': datetime.now(UTC) - timedelta(seconds=1)}
        app_env.db.mcp_key.update_one({'_id': key_id}, {'$set': values})
    profile = Mock(side_effect=AssertionError('Revoked credentials must not read assets'))
    app_env.monkeypatch.setattr(module, 'build_asset_profile', profile)
    response = asyncio.run(post_message(server, 'fixture', token if include_token else None))
    assert b'401 Unauthorized' in response
    assert session.is_closed
    profile.assert_not_called()


def test_explicit_other_credential_cannot_borrow_session(app_env, mcp):
    module, server = mcp
    token, _ = create_key(app_env)
    other, _ = create_key(app_env, suffix='b')
    session = module.MCPSession('fixture', server.authenticate_token(token))
    server.sessions['fixture'] = session
    response = asyncio.run(post_message(server, 'fixture', other))
    assert b'401 Unauthorized' in response
    assert not session.is_closed


def test_naive_utc_expiry_is_independent_of_container_timezone(app_env, mcp):
    _, server = mcp
    token, key_id = create_key(app_env, expires=datetime.now(UTC) + timedelta(hours=1))
    assert app_env.db.mcp_key.find_one({'_id': key_id})['expire_at'].tzinfo is None
    original = os.environ.get('TZ')
    try:
        for zone in ('Asia/Shanghai', 'UTC', 'America/Los_Angeles'):
            os.environ['TZ'] = zone
            time.tzset()
            assert server.authenticate_token(token)
        app_env.db.mcp_key.update_one({'_id': key_id}, {'$set': {'expire_at': datetime.now(UTC) - timedelta(seconds=1)}})
        assert server.authenticate_token(token) is None
    finally:
        if original is None:
            os.environ.pop('TZ', None)
        else:
            os.environ['TZ'] = original
        time.tzset()


def test_discovery_and_execution_share_policy_and_scopes(app_env, mcp):
    _, server = mcp
    server._dispatch_enabled = False
    app_env.db.mcp_config.insert_one({'_id': 'global', 'tool_switches': {
        'create_scan_task': True, 'stop_scan_task': True, 'search_assets': False}})
    readonly = {'scopes': ['asset:read']}
    operator = {'scopes': ['asset:read', 'task:dispatch']}
    assert {t['name'] for t in server.get_supported_tools(readonly)} == {'get_asset_profile', 'get_enterprise_profile', 'get_task_status'}
    assert {t['name'] for t in server.get_supported_tools(operator)} == {
        'get_asset_profile', 'get_enterprise_profile', 'get_task_status', 'create_scan_task', 'stop_scan_task'}
    result, error = asyncio.run(server.handle_tool_call('search_assets', {'query': 'fixture'}, operator))
    assert error and result['code'] == 403
    app_env.db.mcp_config.update_one({'_id': 'global'}, {'$set': {'tool_switches.create_scan_task': False}})
    assert 'create_scan_task' not in {t['name'] for t in server.get_supported_tools(operator)}


def test_stdio_key_is_readonly_and_can_be_revoked(app_env, mcp):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    token, key_id = create_key(app_env)
    profile = Mock(return_value={'target': 'example.test'})
    app_env.monkeypatch.setattr(route, 'build_asset_profile', profile)
    client = make_client(app_env, route.ns)
    headers = {'Token': token}
    assert client.get('/api/mcp/asset_profile?target=example.test', headers=headers).status_code == 200
    assert client.get('/api/mcp/keys', headers=headers).status_code == 401
    assert client.get('/protected', headers=headers).status_code == 401
    app_env.db.mcp_key.update_one({'_id': key_id}, {'$set': {'status': 'revoked'}})
    assert client.get('/api/mcp/asset_profile?target=example.test', headers=headers).status_code == 401
    assert profile.call_count == 1


def test_stdio_enforces_tool_switch_and_read_scope(app_env, mcp):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    token, key_id = create_key(app_env, scopes=['task:dispatch'])
    client = make_client(app_env, route.ns)
    assert client.get('/api/mcp/asset_profile?target=example.test', headers={'Token': token}).status_code == 403
    app_env.db.mcp_key.update_one({'_id': key_id}, {'$set': {'scopes': ['asset:read']}})
    app_env.db.mcp_config.insert_one({'_id': 'global', 'tool_switches': {'get_asset_profile': False}})
    assert client.get('/api/mcp/asset_profile?target=example.test', headers={'Token': token}).status_code == 403


def test_quota_shared_by_sse_and_stdio_returns_http_429(app_env, mcp):
    module, server = mcp
    security = __import__('app.mcp_security', fromlist=['consume_mcp_quota'])
    app_env.monkeypatch.setattr(security.time, 'time', lambda: 1200.0)
    app_env.db.mcp_config.insert_one({'_id': 'global', 'rate_limit_per_min': 10})
    token, _ = create_key(app_env)
    user = server.authenticate_token(token)
    server.sessions['fixture'] = module.MCPSession('fixture', user)
    app_env.monkeypatch.setattr(module, 'build_asset_profile', Mock(return_value={'target': 'fixture'}))
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    app_env.monkeypatch.setattr(route, 'build_asset_profile', Mock(return_value={'target': 'fixture'}))
    client = make_client(app_env, route.ns)

    async def call_sse():
        for _ in range(5):
            assert b'202 Accepted' in await post_message(server, 'fixture')
            result = await asyncio.wait_for(server.sessions['fixture'].queue.get(), 2)
            assert not result['result']['isError']
    asyncio.run(call_sse())
    for _ in range(5):
        assert client.get('/api/mcp/asset_profile?target=fixture', headers={'Token': token}).status_code == 200
    response = asyncio.run(post_message(server, 'fixture'))
    assert b'429 Too Many Requests' in response and b'Retry-After:' in response
    response = client.get('/api/mcp/asset_profile?target=fixture', headers={'Token': token})
    assert response.status_code == 429 and response.headers['Retry-After'] == '60'
    assert module.build_asset_profile.call_count == 5
    app_env.monkeypatch.setattr(security.time, 'time', lambda: 1260.0)
    assert client.get('/api/mcp/asset_profile?target=fixture', headers={'Token': token}).status_code == 200


def test_quota_atomic_across_workers_and_keys(app_env, mcp):
    security = __import__('app.mcp_security', fromlist=['consume_mcp_quota'])
    app_env.monkeypatch.setattr(security.time, 'time', lambda: 1200.0)
    policy = {'rate_limit_per_min': 10}
    def consume(_):
        try:
            security.consume_mcp_quota({'token': 'fixture-one'}, policy)
            return True
        except security.MCPRequestError as error:
            assert error.status == 429
            return False
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(consume, range(40))) == 10
    security.consume_mcp_quota({'token': 'fixture-two'}, policy)


def test_export_uses_complete_dedicated_key_in_post_body(app_env, mcp):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    token, _ = create_key(app_env)
    client = make_client(app_env, route.ns)
    headers = {'Token': 'fixture-api-key'}
    response = client.post('/api/mcp/export_server', headers=headers,
                           json={'host': 'https://example.test', 'raw_key': token})
    assert response.status_code == 200
    tree = ast.parse(response.get_data(as_text=True))
    constants = {n.targets[0].id: n.value.value for n in tree.body
                 if isinstance(n, ast.Assign) and isinstance(n.targets[0], ast.Name) and isinstance(n.value, ast.Constant)}
    assert constants['DEFAULT_TOKEN'] == token
    assert client.post('/api/mcp/export_server', headers=headers, json={'raw_key': token[:12] + '...'}).status_code == 400
    assert client.get('/api/mcp/export_server', headers=headers, query_string={'raw_key': token}).status_code == 400


def test_unavailable_quota_store_rejects_before_tool_execution(app_env, mcp):
    module, server = mcp
    token, _ = create_key(app_env)
    server.sessions['fixture'] = module.MCPSession('fixture', server.authenticate_token(token))
    broken = Mock()
    broken.find_one_and_update.side_effect = RuntimeError('fixture unavailable')
    app_env.monkeypatch.setattr(app_env.utils, 'conn_db',
        lambda name: broken if name == 'mcp_rate_limit' else app_env.db[name])
    profile = Mock()
    app_env.monkeypatch.setattr(module, 'build_asset_profile', profile)
    assert b'503 Service Unavailable' in asyncio.run(post_message(server, 'fixture'))
    profile.assert_not_called()


def test_stdio_audits_usage_without_recording_credentials(app_env, mcp):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    token, key_id = create_key(app_env)
    app_env.monkeypatch.setattr(route, 'build_asset_profile', Mock(return_value={'target': 'example.test'}))
    response = make_client(app_env, route.ns).get('/api/mcp/asset_profile?target=example.test', headers={'Token': token})
    assert response.status_code == 200
    entry = app_env.db.mcp_log.find_one()
    assert entry['key_id'] == str(key_id) and entry['status'] == 'success'
    assert token not in repr(entry)
    assert app_env.db.mcp_key.find_one({'_id': key_id})['last_used_at']
