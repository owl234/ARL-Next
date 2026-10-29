import os
import threading
import tempfile
from flask import request, send_file
from flask_restx import Namespace, fields, reqparse
from . import ARLResource
from app.utils import auth
from app.config import Config
from app.utils.user import user_login_header
from app.utils.download_ticket import issue_download_ticket, consume_download_ticket
from app.services.backup_service import (
    create_backup_archive,
    restore_backup_archive,
    list_all_backups,
    delete_backup_file,
    read_archive_manifest,
    get_backup_dir,
    get_running_task_count,
    progress_tracker,
    reserve_backup_operation,
)

ns = Namespace("backup", description="系统全量数据备份与恢复 API")

create_backup_model = ns.model('CreateBackup', {
    'include_screenshots': fields.Boolean(default=True, description='是否包含站点资产截图文件'),
    'note': fields.String(default='', description='备份备注说明')
})

restore_model = ns.model('RestoreBackup', {
    'filename': fields.String(required=True, description='备份归档文件名'),
    'force': fields.Boolean(default=False, description='是否终止运行中及排队中的任务并继续恢复')
})


def start_backup_job(func, **kwargs):
    try:
        operation_lock = reserve_backup_operation()
    except RuntimeError:
        return {'code': 409, 'message': '已有备份或恢复正在执行'}, 409

    def run():
        try:
            func(**kwargs, _operation_lock=operation_lock)
        except Exception:
            pass  # The service records the operation's error for /status.
        finally:
            operation_lock.release()

    try:
        threading.Thread(target=run, daemon=True).start()
    except BaseException:
        operation_lock.release()
        raise
    return None


def backup_request_data():
    data = request.get_json(silent=True)
    if data is None and not request.content_length:
        return {}
    return data if isinstance(data, dict) else None


@ns.route('/create')
class CreateBackup(ARLResource):
    @auth
    @ns.expect(create_backup_model)
    def post(self):
        """
        异步触发一键全量备份
        """
        data = backup_request_data()
        if data is None:
            return {'code': 400, 'message': '请求体必须为 JSON 对象'}, 400
        include_screenshots = data.get('include_screenshots', True)
        note = data.get('note', '')
        if type(include_screenshots) is not bool or not isinstance(note, str) or len(note) > 80:
            return {'code': 400, 'message': 'include_screenshots 必须为布尔值，note 必须为不超过 80 字的字符串'}, 400

        # 启动后台异步线程执行备份，避免超大备份包耗时过长导致网关 HTTP 504 超时
        conflict = start_backup_job(create_backup_archive, include_screenshots=include_screenshots, note=note)
        if conflict:
            return conflict

        return {
            "code": 200,
            "message": "备份任务已成功在后台启动",
            "data": {
                "include_screenshots": include_screenshots,
                "note": note
            }
        }


@ns.route('/status')
class BackupStatus(ARLResource):
    @auth
    def get(self):
        """
        获取当前备份或恢复任务的实时进度与状态
        """
        state = progress_tracker.get_state()
        return {
            "code": 200,
            "message": "success",
            "data": state
        }


@ns.route('/list')
class BackupList(ARLResource):
    @auth
    def get(self):
        """
        获取服务器上现存的所有备份文件列表与元数据
        """
        backups = list_all_backups()
        running_tasks = get_running_task_count()
        return {
            "code": 200,
            "message": "success",
            "data": {
                "items": backups,
                "running_tasks": running_tasks
            }
        }


@ns.route('/download/<string:filename>')
class DownloadBackup(ARLResource):
    def get(self, filename):
        """
        下载指定的备份归档文件
        """
        safe_name = os.path.basename(filename)
        if not (safe_name.startswith("arl_backup_") and safe_name.endswith(".tar.gz")):
            return {"code": 400, "message": "非法的备份文件名"}, 400

        if Config.AUTH and not user_login_header() and not consume_download_ticket(request.args.get('ticket'), safe_name):
            return {'code': 401, 'message': 'not login', 'data': {}}, 401

        backup_dir = get_backup_dir()
        file_path = os.path.join(backup_dir, safe_name)
        if not os.path.isfile(file_path) or os.path.islink(file_path):
            return {"code": 404, "message": "备份文件不存在"}, 404

        response = send_file(file_path, as_attachment=True, download_name=safe_name,
                             mimetype='application/gzip')
        response.headers['Cache-Control'] = 'private, no-store'
        response.headers['Referrer-Policy'] = 'no-referrer'
        return response


@ns.route('/download_ticket')
class BackupDownloadTicket(ARLResource):
    @auth
    def post(self):
        filename = (request.get_json(silent=True) or {}).get('filename')
        if (not isinstance(filename, str) or filename != os.path.basename(filename)
                or not filename.startswith('arl_backup_') or not filename.endswith('.tar.gz')):
            return {'code': 400, 'message': '非法的备份文件名'}, 400
        path = os.path.join(get_backup_dir(), filename)
        if not os.path.isfile(path) or os.path.islink(path):
            return {'code': 404, 'message': '备份文件不存在'}, 404
        return {'code': 200, 'message': 'success', 'data': {'ticket': issue_download_ticket(filename), 'expires_in': 60}}


@ns.route('/delete/<string:filename>')
class DeleteBackup(ARLResource):
    @auth
    def delete(self, filename):
        """
        删除指定的备份文件
        """
        try:
            success = delete_backup_file(filename)
            if success:
                return {"code": 200, "message": "备份文件已成功删除"}
            return {"code": 404, "message": "备份文件不存在"}
        except ValueError as ve:
            return {"code": 400, "message": str(ve)}
        except Exception as e:
            return {"code": 500, "message": f"删除备份文件失败: {str(e)}"}


@ns.route('/upload')
class UploadBackup(ARLResource):
    @auth
    def post(self):
        """
        上传外部备份包至服务器
        """
        if 'file' not in request.files:
            return {"code": 400, "message": "未找到上传文件字段 'file'"}

        file_obj = request.files['file']
        orig_filename = os.path.basename(file_obj.filename or "")

        if not (orig_filename.startswith("arl_backup_") and orig_filename.endswith(".tar.gz")):
            return {"code": 400, "message": "文件名格式不正确，必须为 arl_backup_*.tar.gz 格式"}

        backup_dir = get_backup_dir()
        dest_path = os.path.join(backup_dir, orig_filename)

        # 先写入私有临时文件，校验成功后发布，不能截断已有备份。
        fd, temp_path = tempfile.mkstemp(prefix='.upload_', dir=backup_dir)
        os.close(fd)
        try:
            file_obj.save(temp_path)
            manifest = read_archive_manifest(temp_path)
            # link 原子地拒绝同名文件，防止并发上传互相覆盖。
            os.link(temp_path, dest_path)
            return {
                "code": 200,
                "message": "备份包上传并校验成功",
                "data": {
                    "filename": orig_filename,
                    "size": os.path.getsize(dest_path),
                    "created_at": manifest.get("created_at"),
                    "arl_version": manifest.get("arl_version"),
                    "include_screenshots": manifest.get("include_screenshots", True),
                    "summary": manifest.get("mongo_stats", {}).get("summary", {})
                }
            }
        except FileExistsError:
            return {"code": 409, "message": "同名备份已存在，请更换文件名"}, 409
        except Exception as e:
            return {"code": 400, "message": f"上传的备份包无效或已损坏: {str(e)}"}
        finally:
            os.unlink(temp_path)


@ns.route('/restore')
class RestoreBackup(ARLResource):
    @auth
    @ns.expect(restore_model)
    def post(self):
        """
        异步触发一键全量恢复
        """
        data = backup_request_data()
        if data is None:
            return {'code': 400, 'message': '请求体必须为 JSON 对象'}, 400
        filename = data.get('filename')
        force = data.get('force', False)
        if type(force) is not bool:
            return {'code': 400, 'message': 'force 必须为布尔值'}, 400

        if (not isinstance(filename, str) or filename != os.path.basename(filename)
                or not filename.startswith('arl_backup_') or not filename.endswith('.tar.gz')):
            return {"code": 400, "message": "非法的备份文件名"}, 400

        safe_name = os.path.basename(filename)
        backup_dir = get_backup_dir()
        archive_path = os.path.join(backup_dir, safe_name)

        if not os.path.isfile(archive_path):
            return {"code": 404, "message": "指定的备份归档文件不存在"}

        # 检查运行中的任务
        running_tasks = get_running_task_count()
        if running_tasks > 0 and not force:
            return {
                "code": 409,
                "message": f"系统当前有 {running_tasks} 个运行中或排队中的任务，执行覆盖恢复将终止这些任务。",
                "data": {
                    "running_tasks": running_tasks,
                    "require_force": True
                }
            }

        # 启动后台异步线程执行恢复
        conflict = start_backup_job(restore_backup_archive, archive_path=archive_path, force=force)
        if conflict:
            return conflict

        return {
            "code": 200,
            "message": "数据覆盖恢复任务已在后台启动",
            "data": {
                "filename": safe_name,
                "force": force
            }
        }


@ns.route('/info/<string:filename>')
class BackupInfo(ARLResource):
    @auth
    def get(self, filename):
        """
        读取并返回指定备份包的完整元数据与资产大盘统计
        """
        safe_name = os.path.basename(filename)
        backup_dir = get_backup_dir()
        file_path = os.path.join(backup_dir, safe_name)
        if not os.path.isfile(file_path):
            return {"code": 404, "message": "备份文件不存在"}, 404

        try:
            manifest = read_archive_manifest(file_path)
            return {
                "code": 200,
                "message": "success",
                "data": {
                    "filename": safe_name,
                    "size": os.path.getsize(file_path),
                    "manifest": manifest
                }
            }
        except Exception as e:
            return {"code": 500, "message": f"解析元数据失败: {str(e)}"}
