import fcntl
import os
import socket
import threading
import time
import uuid
from contextlib import contextmanager

from app.utils.conn import conn_db


_LOCAL_LOCKS_GUARD = threading.Lock()
_LOCAL_THREAD_SEMAPHORES = {}


def get_packet_slot_limit():
    """
    获取高发包重阶段（MassDNS / AltDNS / PortScan）全局并发槽位上限。

    读取优先级：环境变量 ARL_PACKET_PHASE_SLOTS > MongoDB system_config(packet_lease).max_slots > 默认值 1。
    默认 1 个槽位可使重发包阶段与单任务模式保持一致的抗丢包稳定性，同时不阻塞非发包阶段并发。
    """
    env_val = os.environ.get("ARL_PACKET_PHASE_SLOTS")
    if env_val is not None:
        try:
            return max(1, min(16, int(env_val)))
        except (TypeError, ValueError):
            pass

    try:
        col = conn_db("system_config")
        if hasattr(col, "find_one"):
            doc = col.find_one({"_id": "packet_lease"})
            if isinstance(doc, dict) and doc.get("max_slots") is not None:
                return max(1, min(16, int(doc["max_slots"])))
    except Exception:
        pass
    return 1


def _get_current_task_id():
    try:
        from app.utils import arl_task_id_var
        val = arl_task_id_var.get()
        if val and val != "global":
            return str(val)
    except Exception:
        pass
    return ""


def _get_thread_semaphore(max_slots):
    key = int(max_slots)
    with _LOCAL_LOCKS_GUARD:
        sem = _LOCAL_THREAD_SEMAPHORES.get(key)
        if sem is None:
            sem = threading.Semaphore(key)
            _LOCAL_THREAD_SEMAPHORES[key] = sem
        return sem


def _mongo_lease_available():
    """校验当前运行环境中的 packet_phase_lease 集合是否具备真实整型计数语义（排除纯 Mock 桩对象）。"""
    try:
        col = conn_db("packet_phase_lease")
        if not col or not hasattr(col, "update_one"):
            return None
        probe_id = "_probe_noop"
        if hasattr(col, "find_one"):
            col.find_one({"_id": probe_id})
        res = col.update_one({"_id": "__never_match_slot__"}, {"$set": {"_noop": 1}}, upsert=False)
        if not isinstance(getattr(res, "modified_count", None), int):
            return None
        return col
    except Exception:
        return None


@contextmanager
def _local_flock_slot(phase, task_id, max_slots, wait_timeout=None, poll_interval=0.5):
    """当 MongoDB 不可用或处于离线单机上下文时，退化为进程/文件双层槽位互斥。"""
    from app.config import Config
    from app.utils import get_logger

    logger = get_logger()
    tmp_dir = getattr(Config, "TMP_PATH", "/tmp") or "/tmp"
    os.makedirs(tmp_dir, exist_ok=True)

    sem = _get_thread_semaphore(max_slots)
    deadline = (time.monotonic() + wait_timeout) if wait_timeout is not None else None
    sem_timeout = max(0.1, deadline - time.monotonic()) if deadline is not None else None
    acquired_sem = sem.acquire(timeout=sem_timeout) if sem_timeout is not None else sem.acquire()
    if not acquired_sem:
        raise TimeoutError(f"Timed out waiting for local packet phase semaphore ({phase})")

    fd = None
    last_log = 0.0
    try:
        while True:
            for idx in range(max_slots):
                lock_path = os.path.join(tmp_dir, f".arl_packet_slot_{idx}.lock")
                candidate_fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
                try:
                    fcntl.flock(candidate_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fd = candidate_fd
                    break
                except OSError:
                    os.close(candidate_fd)
            if fd is not None:
                break
            now_mono = time.monotonic()
            if deadline is not None and now_mono >= deadline:
                raise TimeoutError(f"Timed out waiting for local file lock in packet phase ({phase})")
            if now_mono - last_log >= 60.0:
                logger.info(
                    "Packet phase [%s] task=%s waiting for local slot (max_slots=%d)",
                    phase,
                    task_id or "-",
                    max_slots,
                )
                last_log = now_mono
            time.sleep(poll_interval)
        yield {"mode": "local_flock", "slot_id": f"local_{phase}"}
    finally:
        if fd is not None:
            try:
                fcntl.flock(fd, fcntl.LOCK_UN)
            except OSError:
                pass
            try:
                os.close(fd)
            except OSError:
                pass
        sem.release()


@contextmanager
def acquire_packet_slot(
    phase,
    task_id=None,
    max_slots=None,
    lease_ttl=120,
    wait_timeout=None,
    poll_interval=1.0,
    collection=None,
):
    """
    为高发包阶段（MassDNS / AltDNS / PortScan）申请有限并发租约槽位。

    特性：
    - 基于 MongoDB 文档级条件原子更新实现跨容器/跨 Worker 进程互斥；
    - 持有期间后台守护线程按 lease_ttl/3 自动续期；
    - 若持有者因 SIGKILL / OOM 崩溃，expires_at 到期后自动可被其他任务接管，无永久死锁；
    - 当数据库不可用或处于测试 Mock 环境时自动退化为本地线程+文件锁。
    """
    resolved_task_id = task_id or _get_current_task_id()
    slots = max(1, int(max_slots if max_slots is not None else get_packet_slot_limit()))

    col = collection if collection is not None else _mongo_lease_available()
    if col is None:
        with _local_flock_slot(
            phase,
            resolved_task_id,
            slots,
            wait_timeout=wait_timeout,
            poll_interval=min(0.5, float(poll_interval)),
        ) as info:
            yield info
        return

    from app.utils import get_logger
    logger = get_logger()
    owner_id = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"

    # 确保所有槽位基础文档存在
    for idx in range(slots):
        slot_id = f"packet_slot_{idx}"
        try:
            col.update_one(
                {"_id": slot_id},
                {"$setOnInsert": {"state": "free", "expires_at": 0.0, "owner_id": ""}},
                upsert=True,
            )
        except Exception:
            pass

    acquired_slot = None
    deadline = (time.monotonic() + wait_timeout) if wait_timeout is not None else None
    last_wait_log = 0.0

    while acquired_slot is None:
        now = time.time()
        for idx in range(slots):
            slot_id = f"packet_slot_{idx}"
            try:
                res = col.update_one(
                    {
                        "_id": slot_id,
                        "$or": [
                            {"state": "free"},
                            {"state": {"$exists": False}},
                            {"expires_at": {"$lt": now}},
                        ],
                    },
                    {
                        "$set": {
                            "state": "busy",
                            "owner_id": owner_id,
                            "task_id": resolved_task_id,
                            "phase": phase,
                            "acquired_at": now,
                            "heartbeat_at": now,
                            "expires_at": now + lease_ttl,
                        }
                    },
                )
                if getattr(res, "modified_count", 0) == 1:
                    acquired_slot = slot_id
                    break
            except Exception as exc:
                logger.warning("Packet lease claim error on %s, falling back to local lock: %s", slot_id, exc)
                with _local_flock_slot(
                    phase,
                    resolved_task_id,
                    slots,
                    wait_timeout=wait_timeout,
                    poll_interval=min(0.5, float(poll_interval)),
                ) as info:
                    yield info
                return

        if acquired_slot is not None:
            break

        now_mono = time.monotonic()
        if deadline is not None and now_mono >= deadline:
            raise TimeoutError(f"Timed out waiting for Mongo packet lease ({phase}, max_slots={slots})")

        if now_mono - last_wait_log >= 60.0:
            logger.info(
                "Packet phase [%s] task=%s queued for lease slot (max_slots=%d)",
                phase,
                resolved_task_id or "-",
                slots,
            )
            last_wait_log = now_mono

        sleep_sec = float(poll_interval)
        if deadline is not None:
            sleep_sec = min(sleep_sec, max(0.05, deadline - now_mono))
        time.sleep(sleep_sec)

    stop_event = threading.Event()
    renew_interval = max(1.0, float(lease_ttl) / 3.0)

    def _renew_loop():
        while not stop_event.wait(renew_interval):
            try:
                now_ts = time.time()
                col.update_one(
                    {"_id": acquired_slot, "owner_id": owner_id},
                    {"$set": {"heartbeat_at": now_ts, "expires_at": now_ts + lease_ttl}},
                )
            except Exception:
                pass

    renew_thread = threading.Thread(target=_renew_loop, daemon=True, name=f"PacketLease-{acquired_slot}")
    renew_thread.start()

    try:
        yield {"mode": "mongo_lease", "slot_id": acquired_slot, "owner_id": owner_id}
    finally:
        stop_event.set()
        try:
            col.update_one(
                {"_id": acquired_slot, "owner_id": owner_id},
                {
                    "$set": {
                        "state": "free",
                        "owner_id": "",
                        "task_id": "",
                        "phase": "",
                        "expires_at": 0.0,
                        "released_at": time.time(),
                    }
                },
            )
        except Exception as exc:
            logger.warning("Failed to release packet lease %s: %s", acquired_slot, exc)


def release_task_packet_slots(task_id, collection=None):
    """在任务异常终止或看门狗收敛时立即释放其残留占用的高发包槽位。"""
    if not task_id:
        return 0
    try:
        if collection is not None:
            col = collection
            if not hasattr(col, "update_many"):
                return 0
            # 当外部显式注入 MockCollection/Collection 时，检查 update_many 是否真实返回整型
        else:
            col = _mongo_lease_available()
            if col is None or not hasattr(col, "update_many"):
                return 0
        res = col.update_many(
            {"task_id": str(task_id), "state": "busy"},
            {
                "$set": {
                    "state": "free",
                    "owner_id": "",
                    "task_id": "",
                    "phase": "",
                    "expires_at": 0.0,
                    "released_at": time.time(),
                }
            },
        )
        cnt = getattr(res, "modified_count", 0)
        return int(cnt) if isinstance(cnt, int) else 0
    except Exception:
        return 0
