"""Boundary and failure regressions from the second review of PR 89."""

import asyncio
import json
import subprocess
import sys
from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from security_support import app_env as _app_env
from security_support import load_backup, load_source, make_client
from test_backup_worker_safety import workers as _workers
from test_mcp_governance_regressions import MemoryWriter, create_key, post_message
from test_mcp_governance_regressions import mcp as _mcp
from test_security_backup import make_backup

app_env = _app_env
workers = _workers
mcp = _mcp


def test_enterprise_profile_works_through_stdio_and_policy(app_env, mcp):
    _, server = mcp
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    token, _ = create_key(app_env)
    client = make_client(app_env, route.ns)
    build = Mock(return_value={'status': 'success', 'enterprise_name': 'fixture'})
    app_env.monkeypatch.setattr(route, 'build_enterprise_profile', build)
    bridge = load_source(app_env.monkeypatch, 'fixture_stdio_bridge', '../mcp-server/server.py')
    def request_api(endpoint, params):
        response = client.get('/api' + endpoint, query_string=params, headers={'Token': token})
        return response.status_code, response.get_json()
    app_env.monkeypatch.setattr(bridge, '_request_api', request_api)
    assert bridge._fetch_enterprise_profile('fixture', 'app', 2, 7)['status'] == 'success'
    build.assert_called_once_with(target='fixture', category='app', page='2', size='7', task_id='')
    assert app_env.db.mcp_log.find_one()['tool_name'] == 'get_enterprise_profile'
    app_env.db.mcp_config.insert_one({'_id': 'global', 'tool_switches': {'get_enterprise_profile': False}})
    assert 'get_enterprise_profile' not in {tool['name'] for tool in server.get_supported_tools(server.authenticate_token(token))}
    assert client.get('/api/mcp/enterprise_profile?target=fixture', headers={'Token': token}).status_code == 403
    assert build.call_count == 1


@pytest.mark.parametrize('task_id', ['invalid', '0' * 24])
def test_missing_enterprise_task_never_selects_unrelated_company(app_env, task_id):
    asset = sys.modules['app.mcp_asset']
    app_env.db.icp_task.insert_one({'name': 'Unrelated company', 'status': 'done'})
    result = asset.build_enterprise_profile('', task_id=task_id)
    assert result['status'] in ('error', 'not_found')
    assert 'enterprise_info' not in result and 'candidates' not in result


def test_enterprise_pagination_handles_infinity_and_large_values(app_env):
    asset = sys.modules['app.mcp_asset']
    task_id = str(app_env.db.icp_task.insert_one({'name': 'fixture', 'status': 'done'}).inserted_id)
    result = asset.build_enterprise_profile('', 'web', float('inf'), float('inf'), task_id)
    assert result['pagination']['page'] == 1 and result['pagination']['size'] == 20
    result = asset.build_enterprise_profile('', 'web', 10**50, 100, task_id)
    assert result['pagination']['page'] == 2_147_483_647


@pytest.mark.parametrize('raw_key', ['', ' ', None, [], 0])
def test_empty_explicit_key_cannot_export_administrator_credential(app_env, raw_key):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    response = make_client(app_env, route.ns).post('/api/mcp/export_server',
        headers={'Token': 'fixture-api-key'}, json={'raw_key': raw_key})
    assert response.status_code == 400
    assert 'fixture-api-key' not in response.get_data(as_text=True)


def test_active_list_empty_is_not_process_exit(app_env, workers):
    running = {'worker': [{'id': 'fixture', 'worker_pid': 123}]}
    workers.inspect.active.side_effect = [running, running, {'worker': []}]
    workers.inspect.stats.return_value = {'worker': {'pool': {'processes': [123]}}}
    with (
        pytest.raises(RuntimeError, match='子进程退出超时'),
        workers.module.RestoreWorkers(force=True, timeout=0),
    ):
        pytest.fail('A live pool process must block mongorestore')
    workers.channel.queue_purge.assert_not_called()


def test_broker_consumer_count_detects_nonresponding_worker(app_env, workers):
    workers.channel.queue_declare.return_value = ('arltask_heavy', 0, 1)
    with (
        pytest.raises(RuntimeError, match='消费未完全暂停'),
        workers.module.RestoreWorkers(force=True, timeout=0),
    ):
        pytest.fail('Control acknowledgement does not prove cancellation')
    workers.control.revoke.assert_not_called()


def test_same_pid_in_another_worker_is_not_mistaken_for_active_child(app_env, workers):
    workers.inspect.active_queues.return_value = {
        'worker': [{'name': 'arltask_heavy'}], 'other': [{'name': 'arltask_light'}]}
    replies = [{'worker': {'ok': 'ok'}}, {'other': {'ok': 'ok'}}]
    for method in ('cancel_consumer', 'add_consumer', 'revoke'):
        getattr(workers.control, method).return_value = replies
    active = {'worker': [{'id': 'fixture', 'worker_pid': 123}], 'other': []}
    workers.inspect.active.side_effect = [active, active, {'worker': [], 'other': []}]
    workers.inspect.reserved.return_value = workers.inspect.scheduled.return_value = {'worker': [], 'other': []}
    workers.inspect.stats.side_effect = [
        {'worker': {'pool': {'processes': [123]}}, 'other': {'pool': {'processes': [123]}}},
        {'worker': {'pool': {'processes': [124]}}, 'other': {'pool': {'processes': [123]}}}]
    with workers.module.RestoreWorkers(force=True, timeout=0):
        pass


def test_osint_writers_cannot_be_terminated_by_celery_restore(app_env, workers):
    app_env.db.icp_task.insert_one({'status': 'running'})
    with (
        pytest.raises(RuntimeError, match='OSINT'),
        workers.module.RestoreWorkers(force=True),
    ):
        pytest.fail('An independent OSINT writer must block restore')
    workers.control.cancel_consumer.assert_not_called()


def test_backup_lock_is_shared_with_another_process(app_env):
    service, directory = load_backup(app_env)
    script = "import fcntl,sys; f=open(sys.argv[1],'w'); fcntl.flock(f,fcntl.LOCK_EX); print('locked',flush=True); sys.stdin.readline()"
    child = subprocess.Popen([sys.executable, '-c', script, str(directory / '.operation.lock')],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    try:
        assert child.stdout.readline().strip() == 'locked'
        with pytest.raises(RuntimeError, match='已有备份或恢复'):
            service.create_backup_archive()
        assert service.progress_tracker.get_state()['status'] == 'idle'
        service.run_command_streaming.assert_not_called()
    finally:
        child.communicate('\n', timeout=5)


@pytest.mark.parametrize('force', ['false', 'true', 0, 1, None, []])
def test_restore_requires_boolean_force_before_starting_job(app_env, force):
    _, directory = load_backup(app_env)
    archive = make_backup(directory)
    route = load_source(app_env.monkeypatch, 'app.routes.backup', 'app/routes/backup.py')
    start = Mock(side_effect=AssertionError('Invalid input must not start a restore'))
    app_env.monkeypatch.setattr(route, 'start_backup_job', start)
    response = make_client(app_env, route.ns).post('/api/backup/restore', headers={'Token': 'fixture-api-key'},
        json={'filename': archive.name, 'force': force})
    assert response.status_code == 400
    start.assert_not_called()


def test_backup_api_reserves_lock_before_acknowledging(app_env):
    service, _ = load_backup(app_env)
    route = load_source(app_env.monkeypatch, 'app.routes.backup', 'app/routes/backup.py')
    with service.reserve_backup_operation():
        response = make_client(app_env, route.ns).post('/api/backup/create', headers={'Token': 'fixture-api-key'}, json={})
        assert response.status_code == 409


def test_streaming_command_drains_stdout_and_redacts_connection_uri(app_env, caplog):
    service, _ = load_backup(app_env)
    # Load a fresh service: load_backup intentionally mocks subprocess execution.
    service = load_source(app_env.monkeypatch, 'app.services.backup_service', 'app/services/backup_service.py')
    service.STATUS_FILE = str(app_env.tmp / 'progress.json')
    service.progress_tracker = service.BackupProgressTracker()
    script = "import sys; sys.stdout.write(('x'*2000+'\\n')*100); print('mongodb://fixture:fixture-secret@example.test/db',file=sys.stderr)"
    service.run_command_streaming([sys.executable, '-c', script], 'fixture', 0, 90)
    state = service.progress_tracker.get_state()
    assert 'fixture-secret' not in repr(state) + caplog.text
    assert len(service.progress_tracker.logs) <= 50


def test_rpc_capacity_reserves_before_database_awaits(app_env, mcp):
    module, server = mcp
    token, _ = create_key(app_env)
    session = module.MCPSession('fixture', server.authenticate_token(token))
    server.sessions['fixture'] = session
    app_env.monkeypatch.setattr(module, 'MAX_SESSION_RPC', 1)
    async def scenario():
        gate = asyncio.Event()
        async def processing(*args, **kwargs):
            await gate.wait()
            return {'jsonrpc': '2.0', 'id': 1, 'result': {}}
        app_env.monkeypatch.setattr(server, 'handle_jsonrpc', processing)
        try:
            responses = await asyncio.gather(*(post_message(server, 'fixture') for _ in range(8)))
            assert sum(b'202 Accepted' in reply for reply in responses) == 1
            assert sum(b'429 Too Many Requests' in reply for reply in responses) == 7
            session.close()
            assert server.pending_count == 1
        finally:
            gate.set()
            await asyncio.gather(*list(server.pending))
            await asyncio.sleep(0)
        assert server.pending_count == session.pending_count == 0
    asyncio.run(scenario())


def test_full_response_queue_does_not_leak_rpc_tasks(app_env, mcp):
    module, server = mcp
    token, _ = create_key(app_env)
    session = module.MCPSession('fixture', server.authenticate_token(token))
    server.sessions['fixture'] = session
    app_env.monkeypatch.setattr(module, 'REPLY_QUEUE_TIMEOUT', 0.01)
    app_env.monkeypatch.setattr(module, 'build_asset_profile', Mock(return_value={'target': 'fixture'}))
    async def scenario():
        session.queue = asyncio.Queue(maxsize=1)
        await session.queue.put({'old': 'unread'})
        assert b'202 Accepted' in await post_message(server, 'fixture')
        await asyncio.wait_for(asyncio.gather(*list(server.pending)), timeout=1)
        await asyncio.sleep(0)
        assert session.is_closed and server.pending_count == 0
    asyncio.run(scenario())


@pytest.mark.parametrize('length', ['-1', 'bad', str(17 * 1024 * 1024)])
def test_invalid_message_length_is_rejected_without_reading_body(app_env, mcp, length):
    module, server = mcp
    token, _ = create_key(app_env)
    server.sessions['fixture'] = module.MCPSession('fixture', server.authenticate_token(token))
    async def scenario():
        reader, writer = asyncio.StreamReader(), MemoryWriter()
        reader.feed_data(f'POST /mcp/message?sessionId=fixture HTTP/1.1\r\nContent-Length: {length}\r\n\r\n'.encode())
        await asyncio.wait_for(server.handle_client(reader, writer), timeout=1)
        assert b'400 Bad Request' in writer.output
    asyncio.run(scenario())


def test_mongo_datetime_result_is_valid_mcp_json(app_env, mcp):
    module, server = mcp
    token, _ = create_key(app_env)
    session = module.MCPSession('fixture', server.authenticate_token(token))
    app_env.db.site.insert_one({'site': 'https://fixture.test', 'updated_at': datetime(2026, 1, 1, tzinfo=UTC)})
    request = {'id': 1, 'method': 'tools/call', 'params': {'name': 'search_assets', 'arguments': {'query': 'fixture'}}}
    result = asyncio.run(server.handle_jsonrpc(request, session))
    assert not result['result']['isError']
    assert json.loads(result['result']['content'][0]['text'])['items'][0]['updated_at'].startswith('2026-01-01')


@pytest.mark.parametrize('payload', [
    {'tool_switches': {'create_scan_task': 'false'}},
    {'tool_switches': {'unknown': True}}, {'tool_switches': None},
    {'rate_limit_per_min': 0}, {'rate_limit_per_min': True},
    {'max_search_limit': 201}, {'max_search_limit': '10'},
])
def test_invalid_policy_is_rejected_without_partial_write(app_env, payload):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    app_env.db.mcp_config.insert_one({'_id': 'global', 'tool_switches': {'create_scan_task': False}})
    before = app_env.db.mcp_config.find_one()
    response = make_client(app_env, route.ns).post('/api/mcp/config', headers={'Token': 'fixture-api-key'}, json=payload)
    assert response.status_code == 400
    assert app_env.db.mcp_config.find_one() == before


def test_partial_policy_save_keeps_other_disabled_tools(app_env, mcp):
    _, server = mcp
    server._dispatch_enabled = True
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    app_env.db.mcp_config.insert_one({'_id': 'global', 'tool_switches': {'create_scan_task': False}})
    response = make_client(app_env, route.ns).post('/api/mcp/config', headers={'Token': 'fixture-api-key'},
        json={'tool_switches': {'search_assets': False}})
    assert response.status_code == 200
    assert app_env.db.mcp_config.find_one()['tool_switches']['create_scan_task'] is False
    assert 'create_scan_task' not in {tool['name'] for tool in server.get_supported_tools()}


@pytest.mark.parametrize('field,value', [
    ('scopes', []), ('scopes', ['unknown']), ('scopes', 'asset:read'),
    ('expire_days', -1), ('expire_days', '7'), ('expire_days', True),
    ('expire_days', float('inf')), ('expire_days', 10**50),
])
def test_invalid_key_options_cannot_silently_grant_access(app_env, field, value):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    response = make_client(app_env, route.ns).post('/api/mcp/keys', headers={'Token': 'fixture-api-key'},
        json={'name': 'fixture', field: value})
    assert response.status_code == 400
    assert app_env.db.mcp_key.count_documents({}) == 0


def test_literal_search_and_zero_page_size_are_bounded(app_env):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    app_env.db.mcp_key.insert_many([{'name': '[fixture]'}, {'name': 'unrelated'}])
    response = make_client(app_env, route.ns).get('/api/mcp/keys', headers={'Token': 'fixture-api-key'},
        query_string={'keyword': '[fixture]', 'page': 0, 'size': 0})
    assert response.status_code == 200
    data = response.get_json()['data']
    assert data['total'] == 1 and data['size'] == data['page'] == 1


def test_denied_calls_consume_quota_and_cannot_flood_audit_log(app_env, mcp):
    route = load_source(app_env.monkeypatch, 'app.routes.mcp', 'app/routes/mcp.py')
    token, _ = create_key(app_env, scopes=['task:dispatch'])
    app_env.db.mcp_config.insert_one({'_id': 'global', 'rate_limit_per_min': 10})
    security = sys.modules['app.mcp_security']
    app_env.monkeypatch.setattr(security.time, 'time', lambda: 1200.0)
    client = make_client(app_env, route.ns)
    responses = [client.get('/api/mcp/asset_profile?target=fixture', headers={'Token': token}) for _ in range(40)]
    assert [response.status_code for response in responses[:10]] == [403] * 10
    assert [response.status_code for response in responses[10:]] == [429] * 30
    assert app_env.db.mcp_log.count_documents({}) == 11


def test_accepted_rpc_survives_post_connection_close_failure(app_env, mcp):
    module, server = mcp
    token, _ = create_key(app_env)
    session = module.MCPSession('fixture', server.authenticate_token(token))
    server.sessions['fixture'] = session
    profile = Mock(return_value={'target': 'fixture'})
    app_env.monkeypatch.setattr(module, 'build_asset_profile', profile)
    class ClosingWriter(MemoryWriter):
        async def wait_closed(self):
            raise ConnectionResetError('fixture peer closed after acknowledgment')
    async def scenario():
        body = json.dumps({'id': 1, 'method': 'tools/call', 'params': {
            'name': 'get_asset_profile', 'arguments': {'target': 'fixture'}}}).encode()
        reader, writer = asyncio.StreamReader(), ClosingWriter()
        reader.feed_data(f'POST /mcp/message?sessionId=fixture HTTP/1.1\r\nContent-Length: {len(body)}\r\n\r\n'.encode() + body)
        reader.feed_eof()
        await server.handle_client(reader, writer)
        assert b'202 Accepted' in writer.output
        response = await asyncio.wait_for(session.queue.get(), 2)
        assert not response['result']['isError']
        await asyncio.gather(*list(server.pending))
    asyncio.run(scenario())
    profile.assert_called_once()


def test_missing_session_retains_404_for_valid_credential(app_env, mcp):
    _, server = mcp
    token, _ = create_key(app_env)
    assert b'404 Not Found' in asyncio.run(post_message(server, 'missing', token))
    assert b'401 Unauthorized' in asyncio.run(post_message(server, 'missing', 'invalid'))
