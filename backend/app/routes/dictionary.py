import os
from flask_restx import Resource, Namespace, fields
from app.utils import get_logger, auth
from . import ARLResource, get_arl_parser
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

# /delete 请求参数 (JSON body)
delete_fields = {
    'name': fields.String(required=True, description="字典文件名"),
    'content': fields.String(required=True, description="要删除的条目，多行以换行符分隔")
}
delete_parser = get_arl_parser(delete_fields, location='json')

def get_safe_dict_path(name):
    """防止目录穿越"""
    if '..' in name or '/' in name or '\\' in name:
        return None
    if not name.endswith('.txt'):
        return None
    path = os.path.join(DICT_DIR, name)
    if not os.path.exists(path):
        return None
    return path


@ns.route('/delete_entries')
class DictionaryDelete(Resource):
    @auth
    @ns.expect(delete_parser)
    def post(self):
        """
        从字典中批量删除条目
        """
        args = delete_parser.parse_args()
        name = args.get('name')
        content = args.get('content', '')
        
        path = get_safe_dict_path(name)
        if not path:
            return {'code': 404, 'message': '文件不合法或不存在'}
            
        entries_to_delete = set(line.strip() for line in content.split('\n') if line.strip())
        if not entries_to_delete:
            return {'code': 400, 'message': '要删除的内容不能为空'}
            
        try:
            # 1. 读出原文件内容并过滤
            retained_entries = []
            deleted_count = 0
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    clean_line = line.strip()
                    if clean_line in entries_to_delete:
                        deleted_count += 1
                    else:
                        if clean_line: # 顺便跳过空行
                            retained_entries.append(clean_line)
            
            # 2. 如果有被删除的数据，则覆写文件
            if deleted_count > 0:
                with open(path, 'w', encoding='utf-8') as f:
                    for i, entry in enumerate(retained_entries):
                        # 如果不是最后一行，或者文件不为空，加换行。这里最简单的方式是用 join
                        pass
                
                # 更简单的写回逻辑
                with open(path, 'w', encoding='utf-8') as f:
                    if retained_entries:
                        f.write('\n'.join(retained_entries) + '\n')
                        
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



def get_category(filename):
    if filename.startswith('domain_') or 'dns' in filename:
        return '子域名收集 (Subdomain Recon)'
    elif filename.startswith('file_'):
        return '目录与文件泄露 (File/Dir Leak)'
    elif filename.startswith('black'):
        return '黑名单配置 (Blacklist)'
    elif filename == 'dnsserver.txt':
        return '基础网络配置 (Network Config)'
    elif filename.startswith('port_'):
        return '端口扫描策略 (Port Config)'
    else:
        return '其他 (Others)'

@ns.route('/list')
class DictionaryList(Resource):
    @auth
    @ns.expect(list_parser)
    def get(self):
        """
        获取 .txt 字典列表，并打上分类标签
        """
        try:
            files = []
            if os.path.exists(DICT_DIR):
                for f in os.listdir(DICT_DIR):
                    if f.endswith('.txt'):
                        size = os.path.getsize(os.path.join(DICT_DIR, f))
                        cat = get_category(f)
                        files.append({'name': f, 'size': size, 'category': cat})
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
        预览字典内容（限制行数）
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
                for line in f:
                    stripped = line.strip()
                    if not stripped: continue
                    total += 1
                    if total <= limit:
                        lines.append(stripped)
            
            return {
                'code': 200, 
                'message': 'success', 
                'data': {
                    'lines': lines,
                    'total': total,
                    'limit': limit
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
        检查条目是否在字典中存在（精确匹配）
        """
        args = search_parser.parse_args()
        name = args.get('name')
        keyword = args.get('keyword', '').strip()
        
        path = get_safe_dict_path(name)
        if not path:
            return {'code': 404, 'message': '文件不合法或不存在'}
            
        if not keyword:
             return {'code': 400, 'message': '关键词不能为空'}
             
        try:
            matches = []
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                for line in f:
                    stripped = line.strip()
                    if not stripped: continue
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
        向字典追加条目（自动去重）
        """
        args = append_parser.parse_args()
        name = args.get('name')
        content = args.get('content', '')
        
        path = get_safe_dict_path(name)
        if not path:
            return {'code': 404, 'message': '文件不合法或不存在'}
            
        new_entries = [line.strip() for line in content.split('\n') if line.strip()]
        if not new_entries:
            return {'code': 400, 'message': '追加内容不能为空'}
            
        try:
            existing_entries_set = set()
            clean_lines = []
            
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                raw_lines = f.readlines()
                
            for line in raw_lines:
                stripped = line.strip()
                if stripped and stripped not in existing_entries_set:
                    existing_entries_set.add(stripped)
                    clean_lines.append(stripped)
            
            to_append = [entry for entry in new_entries if entry not in existing_entries_set]
            
            # 只要有新追加的条目，或者原始文件中有空行/重复行，就覆盖重写整个文件，顺便“洗白”空行
            if to_append or len(clean_lines) != len(raw_lines): 
                clean_lines.extend(to_append)
                with open(path, 'w', encoding='utf-8') as f:
                    for entry in clean_lines:
                        f.write(f"{entry}\n")
                        
            return {
                'code': 200, 
                'message': 'success', 
                'data': {
                    'total_submitted': len(new_entries),
                    'added': len(to_append)
                }
            }
        except Exception as e:
            logger.error(f"Error appending to dictionary {name}: {e}")
            return {'code': 500, 'message': str(e)}
