import os
import time
import threading
import uuid
from app.utils import get_logger
from app.utils import conn_db as conn
from app.utils.dict_utils import file_lock, count_file_lines

logger = get_logger()

def background_process_dict(task_id, temp_file_path, target_dict_path):
    """
    后台处理字典：分块统计、去重并追加到目标字典中（具备排他文件锁与进度上报）
    """
    try:
        # 初始化任务状态
        conn('dict_upload_task').insert_one({
            "task_id": task_id,
            "status": "processing",
            "progress": 0,
            "total_lines": 0,
            "inserted_lines": 0,
            "ignored_lines": 0,
            "message": "正在分析文件与现有字典...",
            "create_time": int(time.time()),
            "update_time": int(time.time())
        })

        # 确保目标目录存在
        os.makedirs(os.path.dirname(target_dict_path), exist_ok=True)

        existing_set = set()
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

        # 3. 合并预加载与写入为单一排他锁段，消除并发空窗（TOCTOU）
        with open(target_dict_path, 'a+', encoding='utf-8', errors='ignore') as fout:
            with file_lock(fout, exclusive=True):
                # 3a. 在排他锁内预加载现有字典用于去重
                fout.seek(0)
                for line in fout:
                    line = line.strip().lstrip('\ufeff')
                    if line:
                        existing_set.add(line)

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

                        if line and line not in existing_set:
                            fout.write(line + "\n")
                            existing_set.add(line)
                            inserted_lines += 1
                        elif line:
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
    生成任务 ID 并启动后台线程
    """
    task_id = str(uuid.uuid4())
    t = threading.Thread(target=background_process_dict, args=(task_id, temp_file_path, target_dict_path))
    t.daemon = True
    t.start()
    return task_id
