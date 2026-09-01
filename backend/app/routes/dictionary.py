import os
from flask_restx import Resource, Namespace, fields
from flask import send_file
from werkzeug.datastructures import FileStorage
from app.utils import get_logger, auth
from app.utils.dict_utils import (
    is_builtin_dict,
    append_to_dict_file, delete_entries_from_dict_file, file_lock
)
from . import get_arl_parser
from app.config import Config

ns = Namespace('dictionary', description="字典管理")
logger = get_logger()

# 基础目录配置，使用 Config 中的 basedir
DICT_DIR = os.path.join(Config.basedir if hasattr(Config, 'basedir') else os.path.dirname(os.path.dirname(__file__)), 'dicts')

# /list 请求参数
list_parser = get_arl_parser({}, location='args')

# /preview 请求参数
preview_fields = {
    'name': fields.String(required=True, description="字典文件名"),
    'limit': fields.Integer(required=False, description="限制返回的行数", default=500)
}
preview_parser = get_arl_parser(preview_fields, location='args')

# /search 请求参数
search_fields = {
    'name': fields.String(required=True, description="字典文件名"),
    'keyword': fields.String(required=True, description="搜索关键词(精确匹配)")
}
search_parser = get_arl_parser(search_fields, location='args')

# /append 请求参数 (JSON body)
append_fields = {
    'name': fields.String(required=True, description="字典文件名"),
    'content': fields.String(required=True, description="要追加的条目，多行以换行符分隔")
}
append_parser = get_arl_parser(append_fields, location='json')

# /create 请求参数 (JSON body)
create_fields = {
    'name': fields.String(required=True, description="字典文件名"),
    'content': fields.String(required=False, description="初始条目内容（可选）")
}
create_parser = get_arl_parser(create_fields, location='json')

# /delete 请求参数 (JSON body)
delete_fields = {
    'name': fields.String(required=True, description="字典文件名"),
    'content': fields.String(required=True, description="要删除的条目，多行以换行符分隔")
}
delete_parser = get_arl_parser(delete_fields, location='json')

# /delete_file 请求参数
delete_file_fields = {
    'name': fields.String(required=True, description="字典文件名")
}
delete_file_parser = get_arl_parser(delete_file_fields, location='json')

# /download 请求参数
download_fields = {
    'name': fields.String(required=True, description="字典文件名")
}
download_parser = get_arl_parser(download_fields, location='args')


def get_safe_dict_path(name):
    """防止目录穿越、NUL 字节注入与 symlink 逃逸"""
    if not name or '..' in name or '/' in name or '\\' in name or '\x00' in name:
        return None
    if not name.endswith('.txt'):
        return None
    path = os.path.join(DICT_DIR, name)
    if not os.path.exists(path):
        return None
    # 拒绝 symlink 逃逸：文件真实路径必须落在 DICT_DIR 内
    dict_dir_real = os.path.realpath(DICT_DIR)
    if not os.path.realpath(path).startswith(dict_dir_real + os.sep):
        return None
    return path


def get_category(filename):
    if filename.startswith('domain_'):
        return '🌍 子域名爆破 (Subdomain Bruteforce)'
    elif filename == 'altdnsdict.txt' or filename.startswith('altdns_'):
        return '🧠 智能子域爆破 (AltDNS Dict)'
    elif filename == 'dnsserver.txt' or filename.startswith('dnsserver_'):
        return '🌐 DNS 解析配置 (DNS Config)'
    elif filename.startswith('file_'):
        return '📂 目录文件泄露 (File/Dir Leak)'
    elif filename.startswith('black'):
        return '🛡️ 全局黑名单拦截 (Blacklist)'
    elif filename.startswith('port_'):
        return '🔌 端口扫描策略 (Port Config)'
    else:
        return '其他 (Others)'


@ns.route('/list')
class DictionaryList(Resource):
    @auth
    @ns.expect(list_parser)
    def get(self):
        """
        获取 .txt 字典列表，并打上分类与内置保护标签
        """
        try:
            files = []
            if os.path.exists(DICT_DIR):
                for f in sorted(os.listdir(DICT_DIR)):
                    if f.endswith('.txt'):
                        size = os.path.getsize(os.path.join(DICT_DIR, f))
                        cat = get_category(f)
                        is_builtin = is_builtin_dict(f, is_brute=False)
                        files.append({
                            'name': f,
                            'size': size,
                            'category': cat,
                            'is_builtin': is_builtin
                        })
            return {'code': 200, 'message': 'success', 'data': files}
        except Exception as e:
            logger.error(f"Error listing dictionaries: {e}")
            return {'code': 500, 'message': str(e)}


@ns.route('/preview')
class DictionaryPreview(Resource):
    @auth
    @ns.expect(preview_parser)
    def get(self):
        """
        预览字典内容（限制行数，共享锁内统计非空总行数）
        """
        args = preview_parser.parse_args()
        name = args.get('name')
        limit = args.get('limit') or 500

        path = get_safe_dict_path(name)
        if not path:
            return {'code': 404, 'message': '文件不合法或不存在'}

        try:
            lines = []
            total = 0
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                with file_lock(f, exclusive=False):
                    for line in f:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        total += 1
                        if len(lines) < limit:
                            lines.append(stripped)

            return {
                'code': 200,
                'message': 'success',
                'data': {
                    'lines': lines,
                    'total': total,
                    'limit': limit,
                    'is_builtin': is_builtin_dict(name, is_brute=False)
                }
            }
        except Exception as e:
            logger.error(f"Error reading dictionary {name}: {e}")
            return {'code': 500, 'message': str(e)}


@ns.route('/search')
class DictionarySearch(Resource):
    @auth
    @ns.expect(search_parser)
    def get(self):
        """
        检查条目是否在字典中存在（精确或包含匹配）
        """
        args = search_parser.parse_args()
        name = args.get('name')
        keyword = (args.get('keyword') or '').strip()

        path = get_safe_dict_path(name)
        if not path:
            return {'code': 404, 'message': '文件不合法或不存在'}

        if not keyword:
            return {'code': 400, 'message': '关键词不能为空'}

        try:
            matches = []
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                with file_lock(f, exclusive=False):
                    for line in f:
                        stripped = line.strip()
                        if not stripped:
                            continue
                        if keyword in stripped:
                            matches.append(stripped)
                            if len(matches) >= 100:
                                break

            return {
                'code': 200,
                'message': 'success',
                'data': {
                    'matches': matches,
                    'keyword': keyword
                }
            }
        except Exception as e:
            logger.error(f"Error searching dictionary {name}: {e}")
            return {'code': 500, 'message': str(e)}


@ns.route('/append')
class DictionaryAppend(Resource):
    @auth
    @ns.expect(append_parser)
    def post(self):
        """
        向字典追加条目（自动去重与并发安全文件锁）
        """
        args = append_parser.parse_args()
        name = args.get('name')
        content = args.get('content') or ''

        path = get_safe_dict_path(name)
        if not path:
            return {'code': 404, 'message': '文件不合法或不存在'}

        if not content.strip():
            return {'code': 400, 'message': '追加内容不能为空'}

        try:
            total_submitted, added = append_to_dict_file(path, content)
            return {
                'code': 200,
                'message': 'success',
                'data': {
                    'total_submitted': total_submitted,
                    'added': added
                }
            }
        except Exception as e:
            logger.error(f"Error appending to dictionary {name}: {e}")
            return {'code': 500, 'message': str(e)}


@ns.route('/delete_entries')
class DictionaryDelete(Resource):
    @auth
    @ns.expect(delete_parser)
    def post(self):
        """
        从字典中批量删除条目（并发文件锁保护）
        """
        args = delete_parser.parse_args()
        name = args.get('name')
        content = args.get('content') or ''

        path = get_safe_dict_path(name)
        if not path:
            return {'code': 404, 'message': '文件不合法或不存在'}

        entries_to_delete = set(line.strip() for line in content.split('\n') if line.strip())
        if not entries_to_delete:
            return {'code': 400, 'message': '要删除的内容不能为空'}

        try:
            deleted_count = delete_entries_from_dict_file(path, entries_to_delete)
            return {
                'code': 200,
                'message': 'success',
                'data': {
                    'total_submitted': len(entries_to_delete),
                    'deleted': deleted_count
                }
            }
        except Exception as e:
            logger.error(f"Error deleting from dictionary {name}: {e}")
            return {'code': 500, 'message': str(e)}


@ns.route('/delete_file')
class DictionaryDeleteFile(Resource):
    @auth
    @ns.expect(delete_file_parser)
    def post(self):
        """
        删除字典文件（内置核心字典拦截保护）
        """
        args = delete_file_parser.parse_args()
        name = args.get('name')

        if is_builtin_dict(name, is_brute=False):
            return {'code': 400, 'message': f'字典 {name} 为系统内置核心字典，受安全策略保护严禁删除！'}

        path = get_safe_dict_path(name)
        if not path:
            return {'code': 404, 'message': '文件不合法或不存在'}

        try:
            os.remove(path)
            return {'code': 200, 'message': 'success', 'data': {'name': name}}
        except Exception as e:
            logger.error(f"Error deleting dictionary file {name}: {e}")
            return {'code': 500, 'message': str(e)}


@ns.route('/download')
class DictionaryDownload(Resource):
    @auth
    @ns.expect(download_parser)
    def get(self):
        """
        一键下载/导出字典文件
        """
        args = download_parser.parse_args()
        name = args.get('name')

        path = get_safe_dict_path(name)
        if not path:
            return {'code': 404, 'message': '文件不合法或不存在'}, 404

        try:
            try:
                return send_file(path, as_attachment=True, download_name=name, mimetype='text/plain')
            except TypeError:
                return send_file(path, as_attachment=True, attachment_filename=name, mimetype='text/plain')
        except Exception as e:
            logger.error(f"Error downloading dictionary {name}: {e}")
            return {'code': 500, 'message': str(e)}, 500


@ns.route('/create')
class DictionaryCreate(Resource):
    @auth
    @ns.expect(create_parser)
    def post(self):
        """新建字典文件并写入初始内容"""
        args = create_parser.parse_args()
        name = (args.get('name') or '').strip()
        content = args.get('content') or ''

        # 路径与文件名安全校验
        if not name or '..' in name or '/' in name or '\\' in name or '\x00' in name:
            return {'code': 400, 'message': '文件名不合法'}
        if not name.endswith('.txt'):
            name += '.txt'

        path = os.path.join(DICT_DIR, name)
        if os.path.exists(path):
            return {'code': 400, 'message': '同名字典已存在'}

        try:
            entries = [line.strip() for line in content.split('\n') if line.strip()]
            seen = set()
            clean_entries = []
            for e in entries:
                if e not in seen:
                    seen.add(e)
                    clean_entries.append(e)

            with open(path, 'w', encoding='utf-8') as f:
                with file_lock(f, exclusive=True):
                    if clean_entries:
                        f.write('\n'.join(clean_entries) + '\n')

            return {'code': 200, 'message': 'success', 'data': {'name': name}}
        except Exception as e:
            logger.error(f"Error creating dictionary {name}: {e}")
            return {'code': 500, 'message': str(e)}


from app.services.dict_upload import trigger_dict_upload_task
from app.utils import conn_db as conn

upload_parser = ns.parser()
upload_parser.add_argument('file', location='files', type=FileStorage, required=True)
upload_parser.add_argument('name', location='form', type=str, required=True, help="字典文件名")

status_parser = ns.parser()
status_parser.add_argument('task_id', location='args', type=str, required=True, help="上传任务ID")


@ns.route('/upload_large')
class DictionaryUploadLarge(Resource):
    @auth
    @ns.expect(upload_parser)
    def post(self):
        """异步超大字典上传与流式去重写入"""
        args = upload_parser.parse_args()
        name = (args.get('name') or '').strip()
        file_obj = args.get('file')

        if not name or '..' in name or '/' in name or '\\' in name or '\x00' in name:
            return {"code": 400, "message": "字典名称非法"}

        if not name.endswith('.txt'):
            name += '.txt'

        path = os.path.join(DICT_DIR, name)
        # 拒绝 symlink 逃逸：写入目标真实路径必须落在 DICT_DIR 内（与读取路径 get_safe_dict_path 防护一致）
        if not os.path.realpath(path).startswith(os.path.realpath(DICT_DIR) + os.sep):
            return {"code": 400, "message": "字典名称非法"}

        if not file_obj or file_obj.filename == '':
            return {"code": 400, "message": "未上传文件"}

        if not file_obj.filename.endswith('.txt'):
            return {"code": 400, "message": "仅支持 .txt 格式文件"}

        # 保存到临时目录
        tmp_dir = os.path.join(Config.basedir if hasattr(Config, 'basedir') else os.path.dirname(os.path.dirname(__file__)), 'tmp_upload')
        os.makedirs(tmp_dir, exist_ok=True)

        import uuid
        tmp_filename = f"{uuid.uuid4().hex}.txt"
        tmp_path = os.path.join(tmp_dir, tmp_filename)

        file_obj.save(tmp_path)

        task_id = trigger_dict_upload_task(tmp_path, path)
        return {"code": 200, "message": "success", "task_id": task_id}


@ns.route('/upload_status')
class DictionaryUploadStatus(Resource):
    @auth
    @ns.expect(status_parser)
    def get(self):
        """查询字典上传任务状态"""
        args = status_parser.parse_args()
        task_id = args.get('task_id')

        task_info = conn('dict_upload_task').find_one({"task_id": task_id}, {"_id": 0})
        if not task_info:
            return {"code": 404, "message": "任务不存在"}

        return {"code": 200, "message": "success", "data": task_info}
