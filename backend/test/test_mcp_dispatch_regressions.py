"""Exercise MCP against the existing task builders and stop implementation."""

import asyncio
import sys
import types
from unittest.mock import AsyncMock, Mock

import pytest
from bson import ObjectId
from security_support import load_source
from test_task_scope import ScopeFixture, load_nodes


@pytest.fixture
def dispatch(monkeypatch):
    fixture = ScopeFixture()
    fixture.setUp()
    try:
        cfg = types.ModuleType('app.config')
        cfg.Config = types.SimpleNamespace(AUTH=True, API_KEY='fixture-api-key')
        monkeypatch.setitem(sys.modules, 'app.config', cfg)
        load_source(monkeypatch, 'app.helpers.policy', 'app/helpers/policy.py')
        load_source(monkeypatch, 'app.mcp_asset', 'app/mcp_asset.py')
        load_source(monkeypatch, 'app.mcp_security', 'app/mcp_security.py')
        mcp = load_source(monkeypatch, 'app.mcp_server', 'app/mcp_server.py')
        fixture.server = mcp.MCPServer()
        fixture.server._record_audit_log = AsyncMock()
        fixture.user = {'scopes': ['asset:read', 'task:dispatch'], 'token': 'fixture-token'}
        fixture.db.mcp_config.insert_one({'_id': 'global', 'tool_switches': {
            'create_scan_task': True, 'stop_scan_task': True}})
        fixture.policy_id = fixture.db.policy.insert_one({'name': 'fixture policy', 'is_default': True,
            'policy': {'related_scope_id': str(fixture.scope_id), 'port_scan': False}}).inserted_id
        routes = types.ModuleType('app.routes')
        routes.__path__ = []
        monkeypatch.setitem(sys.modules, 'app.routes', routes)
        task = types.ModuleType('app.routes.task')
        monkeypatch.setitem(sys.modules, 'app.routes.task', task)
        celerytask = sys.modules['app.celerytask']
        celerytask.celery = types.SimpleNamespace(control=types.SimpleNamespace(revoke=Mock()))
        fixture.revoke = celerytask.celery.control.revoke
        task.__dict__.update(utils=fixture.utils, ObjectId=ObjectId, logger=fixture.logger,
            TaskStatus=fixture.constants['TaskStatus'], celerytask=celerytask,
            ErrorMsg=types.SimpleNamespace(Success={'code': 200, 'message': 'success'},
                Error={'code': 500}, NotFoundTask={'code': 404}, TaskIsDone={'code': 400}))
        load_nodes('app/routes/task.py', task.__dict__, ['stop_task'])
        yield fixture
    finally:
        fixture.doCleanups()


def call(fixture, name, args):
    return asyncio.run(fixture.server.handle_tool_call(name, args, fixture.user))


def test_mixed_targets_use_standard_routing_and_payload(dispatch):
    result, error = call(dispatch, 'create_scan_task', {
        'name': 'fixture', 'target': 'www.example.com,192.0.2.1\napi.example.com'})
    assert not error
    assert len(result['task_ids']) == 3
    assert result['task_id'] == result['task_ids'][0]
    assert len(dispatch.queue.calls) == 3
    assert {item['kwargs']['options']['celery_action'] for item in dispatch.queue.calls} == {'domain_task', 'ip_task'}
    for item in dispatch.queue.calls:
        assert item['queue'] == 'arltask_heavy'
        task = item['kwargs']['options']['data']
        assert task['options']['related_scope_id'] == str(dispatch.scope_id)
        assert task['task_id'] in result['task_ids']
        assert dispatch.stored(task)['celery_id'] == 'queue-fixture-id'


def test_out_of_scope_batch_is_rejected_before_any_dispatch(dispatch):
    _, error = call(dispatch, 'create_scan_task', {
        'name': 'fixture', 'target': 'www.example.com outside.org'})
    assert error
    assert dispatch.queue.calls == []
    assert dispatch.db.task.count_documents({}) == 0


@pytest.mark.parametrize('policy_id', ['invalid', '0' * 24])
def test_missing_policy_does_not_create_waiting_task(dispatch, policy_id):
    result, error = call(dispatch, 'create_scan_task', {
        'name': 'fixture', 'target': 'www.example.com', 'policy_id': policy_id})
    assert error and result['status'] == 'error'
    assert dispatch.queue.calls == []
    assert dispatch.db.task.count_documents({}) == 0


def test_queue_failure_preserves_standard_cleanup(dispatch):
    dispatch.queue.error = RuntimeError('fixture broker unavailable')
    _, error = call(dispatch, 'create_scan_task', {'name': 'fixture', 'target': 'www.example.com'})
    assert error
    assert dispatch.db.task.count_documents({}) == 0


def test_stop_revokes_celery_task_and_records_end_time(dispatch):
    task = dispatch.create()[0]
    result, error = call(dispatch, 'stop_scan_task', {'task_id': task['task_id']})
    assert not error and result['status'] == 'success'
    dispatch.revoke.assert_called_once_with('queue-fixture-id', signal='SIGTERM', terminate=True)
    assert dispatch.stored(task)['status'] == 'stop'
    assert dispatch.stored(task)['end_time']


def test_stop_failure_is_not_reported_as_success(dispatch):
    task = dispatch.create()[0]
    dispatch.revoke.side_effect = RuntimeError('fixture broker unavailable')
    result, error = call(dispatch, 'stop_scan_task', {'task_id': task['task_id']})
    assert error and result['status'] == 'error'
    assert dispatch.stored(task)['status'] == 'waiting'


def test_stop_missing_task_is_error(dispatch):
    result, error = call(dispatch, 'stop_scan_task', {'task_id': str(ObjectId())})
    assert error and result['status'] == 'error'
    dispatch.revoke.assert_not_called()
