"""Keep Celery consumers paused while a database backup is restored."""

import fcntl
import os
import time

from app import utils

RESTORE_LOCK = '/tmp/arl_restore.lock'
SCAN_QUEUES = frozenset(('arltask', 'arltask_heavy', 'arltask_light', 'arlgithub'))
TERMINAL = ('done', 'error', 'stop')


class BackupOperationLock:
    """One backup or restore across threads, web workers and CLI processes."""
    def __init__(self, path: str):
        self.path = path
        self.fd: int | None = None

    def acquire(self):
        if self.fd is not None:
            return self
        fd = os.open(self.path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            raise RuntimeError('已有备份或恢复正在执行') from None
        except BaseException:
            os.close(fd)
            raise
        self.fd = fd
        return self

    def release(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def __enter__(self):
        return self.acquire()

    def __exit__(self, *exc):
        self.release()


class RestoreWorkers:
    def __init__(self, force=False, timeout=30):
        from app.celerytask import celery
        self.app = celery
        self.control = celery.control
        self.force = force
        self.timeout = timeout
        self.paused: list[tuple[str, str]] = []
        self.workers: list[str] = []
        self.lock_fd: int | None = None
        self.restore_started = False

    def _acknowledged(self, replies, workers):
        acknowledged = {worker for reply in (replies or []) for worker, result in reply.items()
                        if isinstance(result, dict) and 'ok' in result and 'error' not in result}
        if not set(workers).issubset(acknowledged):
            raise RuntimeError('未收到全部 Worker 的确认，已阻止数据库恢复')

    def _responses(self, method):
        replies = getattr(self.control.inspect(destination=self.workers, timeout=3), method)()
        if not isinstance(replies, dict) or not set(self.workers).issubset(replies):
            raise RuntimeError('无法确认全部 Worker 的运行状态，已阻止数据库恢复')
        return replies

    def _snapshot(self, method):
        replies = self._responses(method)
        return [task for worker in self.workers for task in replies[worker]]

    def _queue_operation(self, purge=False):
        count, consumers = 0, 0
        # Probe every ARL queue, including consumers that did not answer inspect.
        for queue in sorted(SCAN_QUEUES):
            with self.app.connection_for_write() as connection:
                channel = connection.default_channel
                try:
                    _, ready, consuming = channel.queue_declare(queue=queue, passive=True)
                except Exception as exc:
                    if getattr(exc, 'reply_code', None) == 404 and queue not in {q for _, q in self.paused}:
                        continue  # A disabled queue may never have been declared.
                    raise
                if not isinstance(ready, int) or not isinstance(consuming, int):
                    raise RuntimeError('无法确认消息队列状态，已阻止恢复')  # noqa: TRY004 -- malformed broker reply, not caller input
                count += ready
                consumers += consuming
                if purge:
                    if consuming:
                        raise RuntimeError('扫描队列仍有消费者，禁止清理消息或恢复')
                    channel.queue_purge(queue=queue)
        return count, consumers

    def _pool_processes(self):
        stats = self._responses('stats')
        result = {}
        for worker in self.workers:
            processes = stats[worker].get('pool', {}).get('processes')
            if not isinstance(processes, list) or any(type(pid) is not int for pid in processes):
                raise RuntimeError('恢复需要可确认子进程退出的 prefork Worker')
            result[worker] = set(processes)
        return result

    def _unfinished(self):
        for name in ('task', 'github_task'):
            yield from utils.conn_db(name).find({'status': {'$nin': list(TERMINAL)}}, {'celery_id': 1})

    def _mark_stopped(self):
        for name in ('task', 'github_task'):
            utils.conn_db(name).update_many(
                {'status': {'$nin': list(TERMINAL)}},
                {'$set': {'status': 'stop', 'end_time': utils.curr_date()}},
            )

    def _resume(self):
        failures = []
        for worker, queue in reversed(self.paused):
            try:
                self._acknowledged(self.control.add_consumer(
                    queue, destination=[worker], reply=True, timeout=3), [worker])
            except Exception as exc:  # noqa: BLE001 -- attempt to resume every paused queue
                failures.append(exc)
        self.paused.clear()
        if failures:
            raise RuntimeError('数据库操作已结束，但部分 Worker 队列恢复失败，请重启 Worker') from failures[0]

    def _unlock(self):
        if self.lock_fd is not None:
            os.close(self.lock_fd)
            self.lock_fd = None

    def __enter__(self):
        self.lock_fd = os.open(RESTORE_LOCK, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if utils.conn_db('icp_task').count_documents({'status': {'$nin': list(TERMINAL)}}):
                raise RuntimeError('企业测绘任务未完成；请先等待 OSINT 任务结束，不能强制覆盖恢复')
            deadline = time.monotonic() + self.timeout
            fcntl.flock(self.lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self._unlock()
            raise RuntimeError('已有数据库恢复正在执行')
        try:
            queues = self.control.inspect(timeout=3).active_queues()
            if not isinstance(queues, dict) or not queues:
                raise RuntimeError('无法确认 Worker 状态，已阻止数据库恢复；请检查 Worker 和消息队列')
            for worker, entries in queues.items():
                for entry in entries:
                    queue = entry.get('name')
                    if queue not in SCAN_QUEUES:
                        continue
                    # Record before sending, so an uncertain reply also gets a
                    # compensating resume if preflight fails.
                    self.paused.append((worker, queue))
                    self._acknowledged(self.control.cancel_consumer(
                        queue, destination=[worker], reply=True, timeout=3), [worker])
            self.workers = sorted({worker for worker, _ in self.paused})
            if not self.workers:
                raise RuntimeError('未找到可确认状态的扫描 Worker，已阻止数据库恢复')

            queued, consumers = self._queue_operation()
            while consumers:
                if time.monotonic() >= deadline:
                    raise RuntimeError('队列消费未完全暂停或存在未响应的 Worker，已阻止恢复')
                time.sleep(0.2)
                queued, consumers = self._queue_operation()

            active = self._snapshot('active')
            reserved = self._snapshot('reserved')
            scheduled = self._snapshot('scheduled')
            unfinished = list(self._unfinished())
            if (active or reserved or scheduled or unfinished or queued) and not self.force:
                raise RuntimeError('存在运行中或排队中的任务，请等待完成或确认强制恢复')

            # A prefetched request can still enter a pool child. Let these
            # settle before identifying the processes that must actually exit.
            while reserved:
                if time.monotonic() >= deadline:
                    raise RuntimeError('预取任务尚未进入可确认状态，已阻止恢复')
                time.sleep(0.2)
                reserved = self._snapshot('reserved')
            active_by_worker = self._responses('active')
            active = [task for worker in self.workers for task in active_by_worker[worker]]
            old_processes = self._pool_processes() if active else {}
            active_pids = {worker: {task.get('worker_pid') for task in active_by_worker[worker]}
                           for worker in self.workers}
            for worker, pids in active_pids.items():
                if pids and (any(type(pid) is not int for pid in pids)
                             or not pids.issubset(old_processes.get(worker, set()))):
                    raise RuntimeError('无法确认运行任务所属子进程，已阻止恢复')

            task_ids = {task['id'] for task in active + reserved if task.get('id')}
            task_ids.update(task['request']['id'] for task in scheduled if task.get('request', {}).get('id'))
            task_ids.update(str(task['celery_id']) for task in unfinished if task.get('celery_id'))
            if task_ids:
                self._acknowledged(self.control.revoke(
                    sorted(task_ids), terminate=True, signal='SIGTERM',
                    destination=self.workers, reply=True, timeout=3), self.workers)
            while True:
                remaining = self._snapshot('active')
                current = self._pool_processes() if active else {}
                # revoke removes requests from inspect.active before SIGTERM
                # has finished. Require the original pool children to be reaped.
                alive = any(active_pids[worker] & pids for worker, pids in current.items())
                if not remaining and not alive:
                    break
                if time.monotonic() >= deadline:
                    raise RuntimeError('等待 Worker 子进程退出超时，已阻止数据库恢复')
                time.sleep(0.2)
            if self.force:
                self._queue_operation(purge=True)
                self._mark_stopped()
            return self
        except Exception:
            try:
                self._resume()
            finally:
                self._unlock()
            raise

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type and self.restore_started:
                raise RuntimeError('恢复未完成，扫描队列保持暂停；修复并确认数据后再重启 Worker') from exc
            if not exc_type:
                # Discard jobs published against the old database while the
                # consumers were paused; their task records have been replaced.
                self._queue_operation(purge=True)
                self._mark_stopped()
            self._resume()
        finally:
            self._unlock()
