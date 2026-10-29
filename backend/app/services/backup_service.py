import os
import sys
import re
import json
import time
import shutil
import tarfile
import hashlib
import logging
import threading
import subprocess
import tempfile
from collections import deque
from functools import wraps
from datetime import datetime
from typing import Dict, Any, List, Optional
from urllib.parse import urlparse

from app.config import Config, basedir, clear_system_config_cache, bump_system_config_version
from app.utils.conn import ConnMongo
from .backup_archive import read_manifest, stage_restore, install_staged, regular_backup_member
from .backup_workers import RestoreWorkers, BackupOperationLock

logger = logging.getLogger('arlv2')

STATUS_FILE = "/tmp/arl_backup_status.json"

class BackupProgressTracker:
    """
    跨 Gunicorn 多 Worker 进程持久化的进度管理器。
    将状态原子写入 /tmp/arl_backup_status.json，避免多进程内存隔离导致状态读取不一致。
    """
    start_time: Optional[float]
    end_time: Optional[float]
    logs: List[str]
    error: Optional[str]
    result: Optional[Dict[str, Any]]
    archive_name: Optional[str]

    def __init__(self):
        self._lock = threading.Lock()
        # 初始化时优先从磁盘读取现有状态，若有正在运行的任务则继承；终态则进入 idle
        disk_state = self._read_from_disk()
        if disk_state and disk_state.get("status") in ["backing_up", "restoring"]:
            self.status = disk_state.get("status", "idle")
            self.action = disk_state.get("action")
            self.stage = disk_state.get("stage", "")
            self.percent = disk_state.get("percent", 0)
            self.start_time = disk_state.get("start_time")
            self.end_time = disk_state.get("end_time")
            self.logs = disk_state.get("logs", [])
            self.error = disk_state.get("error")
            self.result = disk_state.get("result")
            self.archive_name = disk_state.get("archive_name")
        else:
            self.reset(save_disk=False)

    def _save_to_disk(self, state: Dict[str, Any]):
        try:
            tmp_path = f"{STATUS_FILE}.tmp.{os.getpid()}_{threading.get_ident()}"
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False)
            os.replace(tmp_path, STATUS_FILE)
        except Exception as e:
            logger.warning(f"保存备份进度至磁盘失败: {e}")

    def _read_from_disk(self) -> Optional[Dict[str, Any]]:
        try:
            if os.path.isfile(STATUS_FILE):
                with open(STATUS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception:
            pass
        return None

    def reset(self, save_disk: bool = True):
        with self._lock:
            self.status = "idle"  # idle | backing_up | restoring | success | error
            self.action = None    # backup | restore
            self.stage = ""
            self.percent = 0
            self.start_time = None
            self.end_time = None
            self.logs = []
            self.error = None
            self.result = None
            self.archive_name = None
            if save_disk:
                self._save_to_disk(self._build_dict())

    def _build_dict(self) -> Dict[str, Any]:
        elapsed = 0
        if self.start_time:
            end = self.end_time if self.end_time else time.time()
            elapsed = int(end - self.start_time)
        return {
            "status": self.status,
            "action": self.action,
            "stage": self.stage,
            "percent": self.percent,
            "elapsed": elapsed,
            "logs": self.logs[-50:],
            "error": self.error,
            "result": self.result,
            "archive_name": self.archive_name,
            "start_time": self.start_time,
            "end_time": self.end_time
        }

    def start(self, action: str, archive_name: Optional[str] = None):
        with self._lock:
            self.status = "backing_up" if action == "backup" else "restoring"
            self.action = action
            self.stage = "正在初始化工作区..."
            self.percent = 5
            self.start_time = time.time()
            self.end_time = None
            self.logs = [f"[{datetime.now().strftime('%H:%M:%S')}] 任务启动: {action}"]
            self.error = None
            self.result = None
            self.archive_name = archive_name
            self._save_to_disk(self._build_dict())

    def update(self, stage: str, percent: int, log_msg: Optional[str] = None):
        with self._lock:
            self.stage = stage
            self.percent = percent
            if log_msg:
                timestamp = datetime.now().strftime('%H:%M:%S')
                self.logs.append(f"[{timestamp}] {log_msg}")
                self.logs = self.logs[-50:]
                logger.info(f"[BackupService] {log_msg}")
            self._save_to_disk(self._build_dict())

    def finish(self, result: Dict[str, Any]):
        with self._lock:
            self.status = "success"
            self.percent = 100
            self.end_time = time.time()
            self.stage = "操作已成功完成"
            self.result = result
            timestamp = datetime.now().strftime('%H:%M:%S')
            self.logs.append(f"[{timestamp}] ✅ 操作成功完成")
            logger.info(f"[BackupService] Task finished successfully: {result}")
            self._save_to_disk(self._build_dict())

    def fail(self, error_msg: str):
        with self._lock:
            self.status = "error"
            self.end_time = time.time()
            self.error = error_msg
            self.stage = f"执行失败: {error_msg}"
            timestamp = datetime.now().strftime('%H:%M:%S')
            self.logs.append(f"[{timestamp}] ❌ 发生错误: {error_msg}")
            logger.error(f"[BackupService] Task failed: {error_msg}")
            self._save_to_disk(self._build_dict())

    def get_state(self) -> Dict[str, Any]:
        disk_state = self._read_from_disk()
        if disk_state:
            with self._lock:
                self.status = disk_state.get("status", self.status)
                self.percent = disk_state.get("percent", self.percent)
                self.stage = disk_state.get("stage", self.stage)
                self.action = disk_state.get("action", self.action)
                self.logs = disk_state.get("logs", self.logs)

            start_time = disk_state.get("start_time")
            end_time = disk_state.get("end_time")
            if start_time:
                end = end_time if end_time else time.time()
                disk_state["elapsed"] = int(end - start_time)
            return disk_state

        with self._lock:
            return self._build_dict()

progress_tracker = BackupProgressTracker()
_task_lock = threading.Lock()


def reserve_backup_operation():
    return BackupOperationLock(os.path.join(get_backup_dir(), '.operation.lock')).acquire()


def exclusive_backup_operation(func):
    @wraps(func)
    def wrapped(*args, **kwargs):
        operation_lock = kwargs.pop('_operation_lock', None) or reserve_backup_operation()
        with operation_lock:
            return func(*args, **kwargs)
    return wrapped


def get_backup_dir() -> str:
    """
    获取备份包持久化目录。优先使用已挂载的 Docker 卷目录 /code/backend/data/backups，
    本地开发时自动回退至工程内 backend/data/backups。
    """
    candidates = [
        "/code/backend/data/backups",
        os.path.abspath(os.path.join(basedir, "..", "data", "backups")),
        os.path.abspath(os.path.join(basedir, "data", "backups")),
        os.path.join(basedir, "tmp_backup")
    ]
    for path in candidates:
        try:
            os.makedirs(path, exist_ok=True)
            test_file = os.path.join(path, ".perm_test")
            with open(test_file, "w") as f:
                f.write("ok")
            os.remove(test_file)
            return path
        except Exception:
            continue
    raise RuntimeError("无法找到可写的备份存储目录")


def find_tool(tool_name: str) -> str:
    """
    查找 mongodump 或 mongorestore 二进制路径
    """
    search_paths = [
        f"/usr/local/bin/{tool_name}",
        f"/usr/bin/{tool_name}",
        shutil.which(tool_name) or ""
    ]
    for path in search_paths:
        if path and os.path.isfile(path) and os.access(path, os.X_OK):
            return path
    raise RuntimeError(
        f"未在系统中找到必要工具 {tool_name}！"
        f"请确保 Docker 容器内或宿主机安装了 mongodb-database-tools。"
    )


def compute_sha256(file_path: str) -> str:
    """计算单个文件的 SHA256 哈希值"""
    sha = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            sha.update(chunk)
    return sha.hexdigest()


def get_arl_version() -> str:
    """获取当前 ARL-Next 版本号"""
    version_paths = [
        "/code/version.txt",
        os.path.abspath(os.path.join(basedir, "..", "..", "version.txt")),
        os.path.abspath(os.path.join(basedir, "..", "version.txt"))
    ]
    for p in version_paths:
        if os.path.isfile(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    ver = f.read().strip()
                    if ver:
                        return ver
            except Exception:
                pass
    return "3.5.0"


def get_all_collection_counts() -> Dict[str, Any]:
    """
    统计 MongoDB 中所有非系统集合的文档数，以及测绘资产分类大盘数据
    """
    db_name = Config.MONGO_DB
    client = ConnMongo().conn
    db = client[db_name]
    
    collection_names = sorted(db.list_collection_names())
    counts = {}
    total_docs = 0
    
    for name in collection_names:
        if name.startswith("system."):
            continue
        try:
            cnt = db[name].count_documents({})
            counts[name] = cnt
            total_docs += cnt
        except Exception as e:
            counts[name] = 0
            logger.warning(f"统计集合 {name} 文档数失败: {e}")

    # 关键业务资产维度汇总
    asset_keys = [
        "site", "domain", "ip", "cert", "service", "url", "fileleak",
        "npoc_service", "vuln", "nuclei_result", "stat_finger", "cip", "wih", "icp_asset"
    ]
    scope_asset_keys = [
        "asset_site", "asset_domain", "asset_ip", "asset_cert", "asset_service",
        "asset_url", "asset_fileleak", "asset_vuln", "asset_nuclei_result",
        "asset_stat_finger", "asset_cip", "asset_wih"
    ]
    
    total_task_assets = sum(counts.get(k, 0) for k in asset_keys)
    total_scope_assets = sum(counts.get(k, 0) for k in scope_asset_keys)
    total_tasks = counts.get("task", 0)
    total_users = counts.get("user", 0)
    
    return {
        "collections": counts,
        "total_collections": len(counts),
        "total_documents": total_docs,
        "summary": {
            "task_assets": total_task_assets,
            "scope_assets": total_scope_assets,
            "total_tasks": total_tasks,
            "total_users": total_users
        }
    }


def get_running_task_count() -> int:
    """包括排队任务，避免旧队列在恢复期间或恢复后继续写入。"""
    from app.modules import TaskStatus
    from app.utils.conn import conn_db
    non_running = [TaskStatus.DONE, TaskStatus.ERROR, TaskStatus.STOP]
    return sum(conn_db(name).count_documents({"status": {"$nin": non_running}})
               for name in ('task', 'github_task'))


def run_command_streaming(cmd: List[str], stage_prefix: str, pct_start: int, pct_end: int, log_tag: str = "Engine"):
    """
    流式执行外部工具命令（如 mongodump / mongorestore），
    实时从 stderr/stdout 逐行读取输出，并平滑步进进度与控制台日志。
    """
    logger.info('Running backup command: %s', log_tag)
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        universal_newlines=True
    )
    
    lines_read = 0
    all_err_lines: deque[str] = deque(maxlen=10)
    assert proc.stdout is not None
    try:
        for line in proc.stdout:
            line_str = re.sub(r'mongodb(?:\+srv)?://\S+', '[redacted MongoDB URI]', line.strip())
            if not line_str:
                continue
            all_err_lines.append(line_str[:2000])
            lines_read += 1
            clean_line = re.sub(r'^\d{4}-\d{2}-\d{2}T[\d:\.\+\-]+[\t\s]*', '', line_str)[:2000]
            is_milestone = any(k in clean_line.lower() for k in ["done", "writing", "restoring", "finished", "%"])
            if is_milestone or lines_read % 3 == 0:
                curr_pct = min(pct_end - 1, pct_start + (lines_read // 2))
                progress_tracker.update(f"{stage_prefix}: {clean_line[:55]}", curr_pct, f"[{log_tag}] {clean_line}")
        proc.wait()
    except BaseException:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        raise
    finally:
        proc.stdout.close()
    if proc.returncode != 0:
        err_msg = "\n".join(all_err_lines) if all_err_lines else "外部命令异常退出"
        raise RuntimeError(f"{log_tag} 命令执行失败 (退出码 {proc.returncode}): {err_msg[:200]}")


@exclusive_backup_operation
def create_backup_archive(include_screenshots: bool = True, note: str = "") -> Dict[str, Any]:
    """
    执行全量一键备份的核心实现函数
    """
    if not _task_lock.acquire(blocking=False):
        raise RuntimeError("系统当前已有备份或恢复任务正在执行，请稍候再试。")
    
    work_dir = None
    backup_file_path = None
    try:
        timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        rand_suffix = hashlib.md5(f"{time.time()}_{os.getpid()}".encode()).hexdigest()[:6]
        archive_name = f"arl_backup_{timestamp_str}_{rand_suffix}.tar.gz"
        
        progress_tracker.start("backup", archive_name)
        progress_tracker.update("正在准备备份临时工作区...", 10, "创建临时工作目录")
        
        backup_dir = get_backup_dir()
        work_dir = os.path.join(backup_dir, f".work_{timestamp_str}_{rand_suffix}")
        os.makedirs(work_dir, exist_ok=True)
        
        # 1. 采集 MongoDB 集合文档元数据
        progress_tracker.update("正在提取数据库文档计数与元数据...", 15, "统计集合与资产总数")
        mongo_stats = get_all_collection_counts()
        
        # 2. 调用 mongodump 导出数据库完整归档
        progress_tracker.update("正在执行 mongodump 归档导出...", 25, "启动 mongodump 进程")
        dump_tool = find_tool("mongodump")
        mongo_archive_name = "mongo_dump.archive.gz"
        mongo_archive_path = os.path.join(work_dir, mongo_archive_name)
        
        # 解析 MONGO_URL 构建参数
        mongo_uri = Config.MONGO_URL
        db_name = Config.MONGO_DB
        
        dump_cmd = [
            dump_tool,
            f"--uri={mongo_uri}",
            f"--db={db_name}",
            f"--archive={mongo_archive_path}",
            "--gzip"
        ]
        
        run_command_streaming(dump_cmd, "MongoDB 归档导出", 20, 55, log_tag="mongodump")
        
        dump_size = os.path.getsize(mongo_archive_path)
        progress_tracker.update(
            "MongoDB 数据归档导出完成", 55,
            f"MongoDB 导出成功 (体积: {round(dump_size / 1024 / 1024, 2)} MB)"
        )
        
        file_map = {
            "mongo_dump": mongo_archive_name
        }
        
        # 3. 打包截图资源（如果选择包含且目录存在）
        if include_screenshots:
            progress_tracker.update("正在打包站点资产截图 (tmp_screenshot)...", 56, "检查资产截图目录")
            screenshot_dirs = [
                "/code/backend/app/tmp_screenshot",
                os.path.join(basedir, "tmp_screenshot")
            ]
            scr_dir = next((d for d in screenshot_dirs if os.path.isdir(d)), None)
            if scr_dir and os.path.isdir(scr_dir):
                files = [f for f in os.listdir(scr_dir) if not f.startswith('.')]
                total_files = len(files)
                if total_files > 0:
                    scr_tar_name = "screenshots.tar.gz"
                    scr_tar_path = os.path.join(work_dir, scr_tar_name)
                    progress_tracker.update("正在压缩资产截图文件...", 58, f"发现 {total_files} 张截图，启动多文件分批归档压缩")
                    with tarfile.open(scr_tar_path, "w:gz", dereference=False) as tar:
                        step = max(1, total_files // 10)
                        for idx, fname in enumerate(files, 1):
                            fpath = os.path.join(scr_dir, fname)
                            tar.add(fpath, arcname=os.path.join("tmp_screenshot", fname), filter=regular_backup_member)
                            if idx % step == 0 or idx == total_files:
                                sub_pct = min(74, 58 + int((idx / total_files) * 16))
                                progress_tracker.update(
                                    f"正在压缩截图 ({idx}/{total_files})...",
                                    sub_pct,
                                    f"已归档截图: {idx}/{total_files} ({round(idx * 100 / total_files)}%)"
                                )
                    file_map["screenshots"] = scr_tar_name
                    scr_size = os.path.getsize(scr_tar_path)
                    progress_tracker.update("资产截图打包完成", 75, f"截图打包成功 (体积: {round(scr_size / 1024 / 1024, 2)} MB)")
                else:
                    progress_tracker.update("跳过资产截图打包", 75, "未找到截图文件或目录为空，跳过")
            else:
                progress_tracker.update("跳过资产截图打包", 75, "未找到截图文件或目录为空，跳过")
        else:
            progress_tracker.update("用户配置为排除截图", 75, "按用户设置排除资产截图文件")

        # 4. 打包自定义字典与 PoC 插件
        progress_tracker.update("正在打包自定义字典与 PoC 插件库...", 80, "打包规则与扩展插件")
        dict_dirs = ["/code/backend/app/dicts", os.path.join(basedir, "dicts")]
        d_dir = next((d for d in dict_dirs if os.path.isdir(d)), None)
        if d_dir and os.listdir(d_dir):
            dict_tar_name = "dicts.tar.gz"
            with tarfile.open(os.path.join(work_dir, dict_tar_name), "w:gz") as tar:
                tar.add(d_dir, arcname="dicts", filter=regular_backup_member)
            file_map["dicts"] = dict_tar_name

        poc_dirs = ["/code/backend/ARL-NPoC/xing/plugins", os.path.abspath(os.path.join(basedir, "..", "ARL-NPoC", "xing", "plugins"))]
        p_dir = next((d for d in poc_dirs if os.path.isdir(d)), None)
        if p_dir and os.listdir(p_dir):
            poc_tar_name = "pocs.tar.gz"
            with tarfile.open(os.path.join(work_dir, poc_tar_name), "w:gz") as tar:
                tar.add(p_dir, arcname="plugins", filter=regular_backup_member)
            file_map["pocs"] = poc_tar_name

        # 5. 复制当前 config.yaml（如存在）
        config_files = ["/code/backend/config.yaml", os.path.abspath(os.path.join(basedir, "..", "config.yaml")), os.path.join(basedir, "config.yaml")]
        c_file = next((f for f in config_files if os.path.isfile(f)), None)
        if c_file:
            shutil.copyfile(c_file, os.path.join(work_dir, "config.yaml"))
            file_map["config"] = "config.yaml"

        # 6. 计算各构件 SHA256 哈希
        progress_tracker.update("正在计算构件 SHA256 校验和...", 85, "校验哈希生成")
        checksums = {}
        for key, fname in file_map.items():
            fpath = os.path.join(work_dir, fname)
            if os.path.isfile(fpath):
                checksums[fname] = compute_sha256(fpath)

        # 7. 生成 manifest.json
        manifest = {
            "format_version": "1.0",
            "created_at": datetime.now().isoformat(),
            "arl_version": get_arl_version(),
            "include_screenshots": include_screenshots,
            "note": note,
            "mongo_stats": mongo_stats,
            "files": file_map,
            "checksums": checksums
        }
        with open(os.path.join(work_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2, ensure_ascii=False)

        # 8. 打包最终发布归档包
        progress_tracker.update("正在整合并压缩生成最终备份归档包...", 90, f"创建归档文件: {archive_name}")
        backup_file_path = os.path.join(backup_dir, archive_name)
        
        with tarfile.open(backup_file_path, "w:gz") as final_tar:
            for item in os.listdir(work_dir):
                item_full_path = os.path.join(work_dir, item)
                final_tar.add(item_full_path, arcname=item)
                
        total_size = os.path.getsize(backup_file_path)
        progress_tracker.update("备份包整合封装完成", 98, f"备份文件生成完毕 (总大小: {round(total_size / 1024 / 1024, 2)} MB)")
        
        result_payload = {
            "archive_name": archive_name,
            "size": total_size,
            "created_at": manifest["created_at"],
            "arl_version": manifest["arl_version"],
            "include_screenshots": include_screenshots,
            "note": note,
            "mongo_stats": mongo_stats
        }
        progress_tracker.finish(result_payload)
        return result_payload

    except Exception as e:
        logger.exception(f"创建备份失败: {e}")
        progress_tracker.fail(str(e))
        if backup_file_path and os.path.isfile(backup_file_path):
            try:
                os.remove(backup_file_path)
            except Exception:
                pass
        raise
    finally:
        if work_dir and os.path.isdir(work_dir):
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass
        _task_lock.release()


def read_archive_manifest(archive_path: str) -> Dict[str, Any]:
    """
    轻量快速读取备份包中的 manifest.json，无需解包整个巨型文件
    """
    if not os.path.isfile(archive_path):
        raise FileNotFoundError(f"备份文件不存在: {archive_path}")
    
    return read_manifest(archive_path)


def list_all_backups() -> List[Dict[str, Any]]:
    """
    扫描备份目录，返回所有合法的备份归档清单及其元数据
    """
    backup_dir = get_backup_dir()
    backups: List[Dict[str, Any]] = []
    
    if not os.path.isdir(backup_dir):
        return backups

    for fname in os.listdir(backup_dir):
        if not (fname.startswith("arl_backup_") and fname.endswith(".tar.gz")):
            continue
        full_path = os.path.join(backup_dir, fname)
        if not os.path.isfile(full_path):
            continue
            
        file_size = os.path.getsize(full_path)
        try:
            manifest = read_archive_manifest(full_path)
            backups.append({
                "filename": fname,
                "size": file_size,
                "created_at": manifest.get("created_at"),
                "arl_version": manifest.get("arl_version", "unknown"),
                "include_screenshots": manifest.get("include_screenshots", True),
                "note": manifest.get("note", ""),
                "summary": manifest.get("mongo_stats", {}).get("summary", {}),
                "valid": True
            })
        except Exception as e:
            backups.append({
                "filename": fname,
                "size": file_size,
                "created_at": datetime.fromtimestamp(os.path.getctime(full_path)).isoformat(),
                "arl_version": "unknown",
                "include_screenshots": False,
                "note": f"无法解析元数据: {str(e)}",
                "summary": {},
                "valid": False
            })
            
    # 按创建时间倒序排列
    backups.sort(key=lambda x: x.get("created_at") or "", reverse=True)
    return backups


def delete_backup_file(filename: str) -> bool:
    """
    安全删除指定备份文件（防御路径穿越）
    """
    safe_name = os.path.basename(filename)
    if not (safe_name.startswith("arl_backup_") and safe_name.endswith(".tar.gz")):
        raise ValueError("无效的备份文件名")
        
    backup_dir = get_backup_dir()
    target_path = os.path.join(backup_dir, safe_name)
    if os.path.isfile(target_path):
        os.remove(target_path)
        return True
    return False


@exclusive_backup_operation
def restore_backup_archive(archive_path: str, force: bool = False) -> Dict[str, Any]:
    """
    执行数据恢复的核心实现函数（基于 --drop 完全覆盖模式）
    """
    if not os.path.isfile(archive_path):
        raise FileNotFoundError(f"备份文件不存在: {archive_path}")
        
    if not _task_lock.acquire(blocking=False):
        raise RuntimeError("系统当前已有备份或恢复任务正在执行，请稍候再试。")
        
    work_dir = None
    try:
        archive_name = os.path.basename(archive_path)
        progress_tracker.start("restore", archive_name)
        progress_tracker.update("正在进行前置运行状态预检...", 5, "校验当前扫描任务")
        
        # 1. 前置预检：扫描运行中任务
        running_count = get_running_task_count()
        if running_count > 0 and not force:
            raise RuntimeError(f"系统当前有 {running_count} 个运行中或排队中的任务！请等待完成后再恢复。")

        # 所有归档层级、哈希和目标目录均先校验；恶意包不得触发停任务或 --drop。
        progress_tracker.update("正在解包归档并校验完整性...", 15, "校验备份构件与恢复目录")
        work_dir = tempfile.mkdtemp(prefix='.restore_', dir=get_backup_dir())
        app_dir = '/code/backend/app' if os.path.isdir('/code/backend/app') else basedir
        poc_dir = '/code/backend/ARL-NPoC/xing' if os.path.isdir('/code/backend/ARL-NPoC/xing') else os.path.abspath(os.path.join(basedir, '..', 'ARL-NPoC', 'xing'))
        manifest, staged = stage_restore(archive_path, work_dir, {
            'screenshots': ('tmp_screenshot', os.path.join(app_dir, 'tmp_screenshot')),
            'dicts': ('dicts', os.path.join(app_dir, 'dicts')),
            'pocs': ('plugins', os.path.join(poc_dir, 'plugins')),
        })

        # Pause consumers and confirm termination before replacing any data.
        with RestoreWorkers(force=force) as workers:
            # 3. 执行 mongorestore 覆盖还原
            progress_tracker.update("正在恢复 MongoDB 数据库（--drop 完全覆盖恢复）...", 35, "调用 mongorestore 覆盖还原")
            restore_tool = find_tool("mongorestore")
            mongo_archive_name = manifest.get("files", {}).get("mongo_dump", "mongo_dump.archive.gz")
            mongo_archive_path = os.path.join(work_dir, mongo_archive_name)
        
            if not os.path.isfile(mongo_archive_path):
                raise FileNotFoundError("未在解包目录中找到 MongoDB 归档文件！")
            
            mongo_uri = Config.MONGO_URL
            db_name = Config.MONGO_DB
        
            # 使用 --nsInclude="db_name.*" 与 --drop 确保对当前数据库内各个集合执行安全清空覆盖
            restore_cmd = [
                restore_tool,
                f"--uri={mongo_uri}",
                f"--nsInclude={db_name}.*",
                "--drop",
                f"--archive={mongo_archive_path}",
                "--gzip"
            ]
        
            workers.restore_started = True
            run_command_streaming(restore_cmd, "MongoDB 覆盖恢复", 35, 70, log_tag="mongorestore")
            progress_tracker.update("MongoDB 数据覆盖还原成功", 70, "数据库集合已全部恢复")

            # 4. 还原静态资产与截图文件
            progress_tracker.update("正在还原已校验的数据文件...", 80, "恢复截图、字典与插件")
            for source, destination in staged:
                install_staged(source, destination)

            # 5. 执行索引重构与平滑兼容
            progress_tracker.update("正在重新构建数据库核心索引与同步缓存...", 90, "执行 arlupdate 索引维护")
            try:
                from app.utils.arlupdate import create_index
                create_index()
            except Exception as ie:
                logger.warning(f"索引重新构建告警: {ie}")
            
            clear_system_config_cache()
            bump_system_config_version()

            # 6. 比对校验恢复后的数据量
            progress_tracker.update("正在执行恢复后数据量交叉比对...", 95, "比对各集合文档计数")
            current_stats = get_all_collection_counts()
            expected_collections = manifest.get("mongo_stats", {}).get("collections", {})
        
            diff_report = {}
            for cname, expected_cnt in expected_collections.items():
                actual_cnt = current_stats.get("collections", {}).get(cname, 0)
                if actual_cnt != expected_cnt:
                    diff_report[cname] = {
                        "expected": expected_cnt,
                        "actual": actual_cnt
                    }
                
            if diff_report:
                logger.warning(f"恢复完成但部分集合数量有微小差异: {diff_report}")
            
            final_summary = {
                "restored_at": datetime.now().isoformat(),
                "manifest_created_at": manifest.get("created_at"),
                "arl_version": manifest.get("arl_version"),
                "total_documents_restored": current_stats["total_documents"],
                "total_collections_restored": current_stats["total_collections"],
                "summary": current_stats["summary"],
                "discrepancies": diff_report,
                "verified": len(diff_report) == 0
            }
        
        progress_tracker.finish(final_summary)
        return final_summary

    except Exception as e:
        logger.exception(f"恢复备份失败: {e}")
        progress_tracker.fail(str(e))
        raise
    finally:
        if work_dir and os.path.isdir(work_dir):
            try:
                shutil.rmtree(work_dir, ignore_errors=True)
            except Exception:
                pass
        _task_lock.release()
