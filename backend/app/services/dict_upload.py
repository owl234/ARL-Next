import os
import time
import threading
import uuid
from datetime import datetime, timedelta, timezone
from app.utils import get_logger
from app.utils import conn_db as conn
from app.utils.dict_utils import file_lock, count_file_lines, hash_dict_entry, dict_lock

logger = get_logger()

def background_process_dict(task_id, temp_file_path, target_dict_path):
    """
    后台处理字典：分块统计、64位紧凑哈希去重并追加到目标字典中（具备独立排他文件锁与心跳进度上报）
    """
    try:
        # 平滑过渡为 processing 状态
        now = int(time.time())
        conn('dict_upload_task').update_one(
            {"task_id": task_id},
            {"$set": {
                "status": "processing",
                "message": "正在分析文件与现有字典...",
                "update_time": now
            },
            "$setOnInsert": {
                "progress": 0,
                "total_lines": 0,
                "inserted_lines": 0,
                "ignored_lines": 0,
                "create_time": now,
                # TTL indexes require a BSON date. Keep create_time as the
                # existing integer field used by the UI, and use a dedicated
                # absolute expiry field for automatic cleanup.
                "expire_at": datetime.now(timezone.utc) + timedelta(days=7)
            }},
            upsert=True
        )

        # 确保目标目录存在
        os.makedirs(os.path.dirname(target_dict_path), exist_ok=True)

        existing_hashes = set()
        inserted_lines = 0
        ignored_lines = 0
        processed_lines = 0

        # 2. 极速获取上传文件的总行数（用于进度计算）
        total_lines = count_file_lines(temp_file_path)
        if total_lines == 0:
            # 兜底逐行读取（按物理行计数，与处理进度计数口径一致）
            with open(temp_file_path, 'r', encoding='utf-8', errors='ignore') as f:
                for _line in f:
                    total_lines += 1

        conn('dict_upload_task').update_one(
            {"task_id": task_id},
            {"$set": {"total_lines": total_lines, "message": "正在流式导入与去重...", "update_time": int(time.time())}}
        )

        # 3. 合并预加载与写入为单一独立排他锁段，消除并发空窗（TOCTOU）
        with dict_lock(target_dict_path, exclusive=True):
            with open(target_dict_path, 'a+', encoding='utf-8', errors='ignore') as fout:
                # 3a. 在排他锁内以 64 位紧凑哈希预加载现有字典用于去重（单条仅 8 字节）
                fout.seek(0)
                for line in fout:
                    line = line.strip().lstrip('\ufeff')
                    if line:
                        existing_hashes.add(hash_dict_entry(line))

                # 确保已有非空文件末尾具备换行符，避免首个新增条目与历史尾行拼接
                fout.flush()
                try:
                    fout.buffer.seek(0, os.SEEK_END)
                    pos = fout.buffer.tell()
                    if pos > 0:
                        fout.buffer.seek(pos - 1)
                        if fout.buffer.read(1) != b'\n':
                            fout.write('\n')
                except Exception:
                    pass
                fout.seek(0, os.SEEK_END)

                # 3b. 在排他锁内流式写入
                with open(temp_file_path, 'r', encoding='utf-8-sig', errors='ignore') as fin:
                    for line in fin:
                        line = line.strip().lstrip('\ufeff')
                        processed_lines += 1

                        if line:
                            h = hash_dict_entry(line)
                            if h not in existing_hashes:
                                fout.write(line + "\n")
                                existing_hashes.add(h)
                                inserted_lines += 1
                            else:
                                ignored_lines += 1

                        # 每处理 10000 行或在末尾更新一次进度
                        if processed_lines % 10000 == 0 or processed_lines == total_lines:
                            progress = int((processed_lines / total_lines) * 100) if total_lines > 0 else 100
                            conn('dict_upload_task').update_one(
                                {"task_id": task_id},
                                {"$set": {
                                    "progress": min(progress, 99),
                                    "inserted_lines": inserted_lines,
                                    "ignored_lines": ignored_lines,
                                    "message": f"正在处理... ({processed_lines}/{total_lines})",
                                    "update_time": int(time.time())
                                }}
                            )
                fout.flush()

        # 4. 处理完成
        conn('dict_upload_task').update_one(
            {"task_id": task_id},
            {"$set": {
                "status": "completed",
                "progress": 100,
                "inserted_lines": inserted_lines,
                "ignored_lines": ignored_lines,
                "message": "导入完成",
                "update_time": int(time.time())
            }}
        )
        logger.info(f"Dict upload task {task_id} completed. Inserted: {inserted_lines}, Ignored: {ignored_lines}")

    except Exception as e:
        logger.error(f"Error in dict upload task {task_id}: {e}")
        conn('dict_upload_task').update_one(
            {"task_id": task_id},
            {"$set": {
                "status": "error",
                "message": f"处理出错: {str(e)}",
                "update_time": int(time.time())
            }}
        )
    finally:
        # 清理临时文件
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as e:
                logger.error(f"Failed to remove temp file {temp_file_path}: {e}")


def trigger_dict_upload_task(temp_file_path, target_dict_path):
    """
    生成任务 ID 并优先派发至 Celery 异步队列（由 arl-worker 容器独立运行，规避 Gunicorn worker 生命周期回收）；
    在 Celery 未启动或连接异常时平滑降级为守护线程。
    """
    task_id = str(uuid.uuid4())
    now = int(time.time())

    # 1. 原子前置写入 pending 状态文档，彻底消除 Worker 消费空窗期导致的 404 与前端轮询假死
    try:
        conn('dict_upload_task').insert_one({
            "task_id": task_id,
            "status": "pending",
            "progress": 0,
            "total_lines": 0,
            "inserted_lines": 0,
            "ignored_lines": 0,
            "message": "任务已提交，正在等待队列调度...",
            "create_time": now,
            "update_time": now
        })
    except Exception as e:
        logger.error(f"Failed to pre-insert pending status for dict upload task {task_id}: {e}")

    dispatched = False
    try:
        from app.celerytask import dict_import_celery_task
        from app.modules import CeleryRoutingKey
        dict_import_celery_task.apply_async(
            args=[task_id, temp_file_path, target_dict_path],
            queue=CeleryRoutingKey.ASSET_TASK_LIGHT
        )
        dispatched = True
        logger.info(f"Dispatched dict upload task {task_id} to Celery queue {CeleryRoutingKey.ASSET_TASK_LIGHT}")
    except Exception as e:
        logger.warning(f"Failed to dispatch dict upload task to Celery ({e}), falling back to background thread")

    if not dispatched:
        try:
            t = threading.Thread(target=background_process_dict, args=(task_id, temp_file_path, target_dict_path))
            t.daemon = True
            t.start()
            logger.info(f"Started dict upload task {task_id} in background daemon thread")
        except Exception as e:
            logger.error(f"Failed to start fallback thread for dict upload task {task_id}: {e}")
            conn('dict_upload_task').update_one(
                {"task_id": task_id},
                {"$set": {"status": "error", "message": f"任务派发失败: {e}", "update_time": int(time.time())}}
            )

    return task_id
