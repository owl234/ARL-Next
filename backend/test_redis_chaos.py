import time
import sys
from app.celerytask import celery, arl_task
from celery.app.control import Control

def get_redis_client():
    return celery.connection().channel().client

def test_connection():
    try:
        r = get_redis_client()
        r.ping()
        print("[SUCCESS] Connected to Redis.")
    except Exception as e:
        print(f"[ERROR] Redis connection failed: {e}")
        sys.exit(1)

def inject_tasks(n):
    print(f"[*] Injecting {n} tasks into queue...")
    ids = []
    for i in range(n):
        res = arl_task.delay(options={"target": f"127.0.0.1", "port_scan_type": "top10", "task_tag": f"chaos_{i}"})
        ids.append(res.id)
    print(f"[SUCCESS] Injected {n} tasks.")
    return ids

def get_queue_len():
    r = get_redis_client()
    qlen = r.llen('arltask')
    print(f"[*] Current 'arltask' queue length: {qlen}")
    return qlen

def revoke_task(task_id):
    c = Control(celery)
    c.revoke(task_id, terminate=True)
    print(f"[*] Revoked task {task_id}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_redis_chaos.py [ping|inject N|qlen|revoke TID]")
        sys.exit(1)
    
    cmd = sys.argv[1]
    if cmd == "ping":
        test_connection()
    elif cmd == "inject":
        n = int(sys.argv[2]) if len(sys.argv) > 2 else 10
        inject_tasks(n)
    elif cmd == "qlen":
        get_queue_len()
    elif cmd == "revoke":
        tid = sys.argv[2]
        revoke_task(tid)
