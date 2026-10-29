"""Restoration never runs real broker or database commands in these tests."""

import sys
import types
from unittest.mock import MagicMock, Mock

import pytest
from security_support import app_env as _app_env
from security_support import load_backup, load_source
from test_security_backup import make_backup

app_env = _app_env


@pytest.fixture
def workers(app_env):
    control = Mock()
    inspect = control.inspect.return_value
    inspect.active_queues.return_value = {'worker': [{'name': 'arltask_heavy'}]}
    inspect.stats.return_value = {'worker': {'pool': {'processes': [123]}}}
    for name in ('active', 'reserved', 'scheduled'):
        getattr(inspect, name).return_value = {'worker': []}
    replies = [{'worker': {'ok': 'confirmed'}}]
    for name in ('cancel_consumer', 'add_consumer', 'revoke'):
        getattr(control, name).return_value = replies
    celery = MagicMock(control=control)
    channel = celery.connection_for_write.return_value.__enter__.return_value.default_channel
    channel.queue_declare.return_value = ('arltask_heavy', 0, 0)
    module = types.ModuleType('app.celerytask')
    module.celery = celery
    app_env.monkeypatch.setitem(sys.modules, 'app.celerytask', module)
    safety = load_source(app_env.monkeypatch, 'app.services.backup_workers', 'app/services/backup_workers.py')
    safety.RESTORE_LOCK = str(app_env.tmp / 'restore.lock')
    app_env.monkeypatch.setattr(safety.time, 'sleep', lambda _: None)
    return types.SimpleNamespace(module=safety, control=control, inspect=inspect, channel=channel)


def test_force_waits_for_worker_exit_before_restore(app_env, workers):
    app_env.db.task.insert_one({'status': 'waiting', 'celery_id': 'queued-task'})
    workers.inspect.active.side_effect = [
        {'worker': [{'id': 'running-task', 'worker_pid': 123}]},
        {'worker': [{'id': 'running-task', 'worker_pid': 123}, {'id': 'reserved-task', 'worker_pid': 124}]}, {'worker': []}]
    workers.inspect.reserved.side_effect = [{'worker': [{'id': 'reserved-task'}]}, {'worker': []}]
    workers.inspect.stats.side_effect = [
        {'worker': {'pool': {'processes': [123, 124]}}}, {'worker': {'pool': {'processes': [125, 126]}}}]
    workers.inspect.scheduled.return_value = {'worker': [{'request': {'id': 'eta-task'}}]}
    with workers.module.RestoreWorkers(force=True) as guard:
        guard.restore_started = True
        assert workers.inspect.active.call_count == 3
        assert workers.control.cancel_consumer.called
        workers.control.add_consumer.assert_not_called()
        assert set(workers.control.revoke.call_args.args[0]) == {'queued-task', 'running-task', 'reserved-task', 'eta-task'}
        assert app_env.db.task.find_one()['status'] == 'stop'
    workers.control.add_consumer.assert_called_once()
    assert workers.channel.queue_purge.call_count == 2 * len(workers.module.SCAN_QUEUES)


@pytest.mark.parametrize('pending', ['database', 'broker', 'active', 'reserved', 'scheduled'])
def test_unforced_restore_rejects_pending_work(app_env, workers, pending):
    if pending == 'database':
        app_env.db.task.insert_one({'status': 'waiting', 'celery_id': 'queued-task'})
    elif pending == 'broker':
        workers.channel.queue_declare.return_value = ('arltask_heavy', 2, 0)
    else:
        getattr(workers.inspect, pending).return_value = {'worker': [{'id': 'fixture'}]}
    with pytest.raises(RuntimeError, match='排队'), workers.module.RestoreWorkers():
        pytest.fail('Restoration must not start')
    workers.control.revoke.assert_not_called()
    workers.channel.queue_purge.assert_not_called()
    workers.control.add_consumer.assert_called_once()


@pytest.mark.parametrize('failure', ['offline', 'cancel_ack', 'inspect_reply', 'revoke_ack', 'timeout'])
def test_worker_uncertainty_prevents_restore(app_env, workers, failure):
    if failure == 'offline':
        workers.inspect.active_queues.return_value = None
    elif failure == 'cancel_ack':
        workers.control.cancel_consumer.return_value = []
    elif failure == 'inspect_reply':
        workers.inspect.active.return_value = {}
    else:
        workers.inspect.active.return_value = {'worker': [{'id': 'fixture', 'worker_pid': 123}]}
        if failure == 'revoke_ack':
            workers.control.revoke.return_value = []
    with (
        pytest.raises(RuntimeError),
        workers.module.RestoreWorkers(force=True, timeout=0),
    ):
        pytest.fail('Unconfirmed workers must not permit mongorestore')
    workers.channel.queue_purge.assert_not_called()


def test_failure_after_drop_keeps_consumers_paused(app_env, workers):
    with (
        pytest.raises(RuntimeError, match='保持暂停'),
        workers.module.RestoreWorkers(force=True) as guard,
    ):
        guard.restore_started = True
        raise RuntimeError('fixture mongorestore failed')
    workers.control.add_consumer.assert_not_called()


def test_preflight_failure_resumes_consumers(app_env, workers):
    with pytest.raises(ValueError), workers.module.RestoreWorkers(force=True):
        raise ValueError('fixture tool unavailable before restore')
    workers.control.add_consumer.assert_called_once()


def test_restore_lock_excludes_other_gunicorn_worker(app_env, workers):
    with (
        workers.module.RestoreWorkers(),
        pytest.raises(RuntimeError, match='已有数据库恢复'),
        workers.module.RestoreWorkers(),
    ):
        pytest.fail('Concurrent restoration must be rejected')
    workers.control.cancel_consumer.assert_called_once()


def test_restore_integration_only_runs_drop_after_confirmed_stop(app_env, workers):
    service, directory = load_backup(app_env)
    service.RestoreWorkers = workers.module.RestoreWorkers
    path = make_backup(directory)
    app_env.db.task.insert_one({'status': 'running', 'celery_id': 'fixture'})
    workers.inspect.active.side_effect = [{'worker': [{'id': 'fixture', 'worker_pid': 123}]},
        {'worker': [{'id': 'fixture', 'worker_pid': 123}]}, {'worker': []}]
    workers.inspect.stats.side_effect = [
        {'worker': {'pool': {'processes': [123]}}}, {'worker': {'pool': {'processes': [124]}}}]
    def restore(cmd, *args, **kwargs):
        assert '--drop' in cmd
        assert workers.control.revoke.called
        assert workers.inspect.active.call_count == 3
        workers.control.add_consumer.assert_not_called()
    service.run_command_streaming.side_effect = restore
    service.restore_backup_archive(str(path), force=True)
    service.run_command_streaming.assert_called_once()
    workers.control.add_consumer.assert_called_once()


def test_bad_archive_never_pauses_or_revokes_workers(app_env, workers):
    service, directory = load_backup(app_env)
    service.RestoreWorkers = workers.module.RestoreWorkers
    path = make_backup(directory, manifest_change=lambda m: m['checksums'].clear())
    with pytest.raises(ValueError):
        service.restore_backup_archive(str(path), force=True)
    workers.control.cancel_consumer.assert_not_called()
    workers.control.revoke.assert_not_called()
    service.run_command_streaming.assert_not_called()


def test_pending_count_includes_queued_and_github_tasks(app_env):
    from test_task_scope import load_nodes
    module = types.ModuleType('app.modules')
    module.TaskStatus = types.SimpleNamespace(DONE='done', ERROR='error', STOP='stop', WAITING='waiting')
    app_env.monkeypatch.setitem(sys.modules, 'app.modules', module)
    env = {}
    load_nodes('app/services/backup_service.py', env, ['get_running_task_count'])
    app_env.db.task.insert_many([{'status': 'waiting'}, {'status': 'running'}, {'status': 'done'}])
    app_env.db.github_task.insert_many([{'status': 'waiting'}, {'status': 'stop'}])
    assert env['get_running_task_count']() == 3
