import os
import ast
import re
from flask import request
from xing.conf import Conf as npoc_conf
from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.services.npoc import NPoC
from app import utils
from app.modules import ErrorMsg

ns = Namespace('poc', description="PoC信息")

logger = get_logger()


def _plugin_type_of(type_nodes: list):
    """从 self.plugin_type = PluginType.X / 'x' 赋值中解析插件类型（取首个可识别值）"""
    for node in type_nodes or []:
        if isinstance(node, ast.Attribute):
            return node.attr.upper()
        if isinstance(node, ast.Name):
            return node.id.upper()
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value.upper()
    return ""


def _collect_plugin_contract(classdef: ast.ClassDef):
    """
    收集 Plugin 类的静态契约信息：self.<attr> 的全部赋值节点与已实现的方法名
    只做 AST 取值，不导入不执行，规避任意代码求值风险
    """
    assigned = {}
    methods = set()
    for item in classdef.body:
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            methods.add(item.name)
    for node in ast.walk(classdef):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Attribute) and isinstance(target.value, ast.Name) \
                        and target.value.id == 'self':
                    assigned.setdefault(target.attr, []).append(node.value)
    return assigned, methods


def validate_poc_script(content: str):
    """
    静态校验 PoC Python 脚本的语法正确性与 Plugin 类契约结构。
    契约基准取自引擎硬依赖（xing/core/BasePlugin.do_map 与 NPoC.gen_poc_info），
    已对全量存量出厂插件做过 AST 审计，确保零误杀：
      - plugin_type 缺失 -> do_map KeyError
      - scheme 缺失(非 SNIFFER) -> gen_poc_info `",".join(p.scheme)` TypeError，
        会使每次 /poc/sync 与启动期 arl_update 增量链整体抛错
      - 类型方法缺失 -> 插件可加载但运行期必然 NotImplementedError
    :param content: 源码字符串
    :return: (is_valid: bool, error_msg: str)
    """
    if not content or not content.strip():
        return False, "PoC 脚本内容不能为空"

    try:
        tree = ast.parse(content)
    except SyntaxError as e:
        return False, f"Python 语法错误 (第 {e.lineno} 行): {e.msg}"
    except Exception as e:
        return False, f"代码解析异常: {e}"

    plugin_cls = next(
        (n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'Plugin'), None
    )
    if plugin_cls is None:
        return False, "缺少核心 'Plugin' 类定义（必须定义名为 Plugin 的类）"

    assigned, methods = _collect_plugin_contract(plugin_cls)
    business_methods = methods - {'__init__'}
    if not business_methods:
        return False, "Plugin 类中缺少有效的方法实现（需实现 verify、login 等业务逻辑，不能仅有 __init__）"

    plugin_type = _plugin_type_of(assigned.get('plugin_type'))
    if not plugin_type:
        return False, ("未声明插件类型（需在 __init__ 中设置 self.plugin_type = PluginType.POC"
                       " / BRUTE / SNIFFER）")

    # scheme 的硬依赖仅对进入 gen_poc_info 的 POC/BRUTE 成立；
    # SNIFFER 在 gen_poc_info 中被 continue 跳过，LISTENER 等类型不进插件库，均不强制
    if plugin_type in ('POC', 'BRUTE'):
        scheme_nodes = assigned.get('scheme') or []
        has_valid_scheme = any(
            not (isinstance(n, ast.Constant) and n.value is None) for n in scheme_nodes
        )
        if not has_valid_scheme:
            return False, ("缺少有效的 self.scheme（须为 [SchemeType.HTTP, SchemeType.HTTPS] 这类列表，"
                           "不可缺失或为 None），否则插件库同步与启动增量迁移会整体报错")

    if plugin_type == 'POC' and 'verify' not in methods:
        return False, "POC 插件必须实现 verify(self, target) 方法"

    if plugin_type == 'SNIFFER' and 'sniffer' not in methods:
        return False, "协议识别(SNIFFER)插件必须实现 sniffer(self, host, port) 方法"

    if plugin_type == 'BRUTE' and 'service_brute' not in methods:
        if not {'check_app', 'login'} <= methods:
            return False, ("爆破插件需实现 check_app(self, target) + login(self, target, user, passwd)，"
                           "或自行实现 service_brute(self)")

        # 静态校验字典配置契约：未自定义 service_brute 时，BasePlugin.load_dict 强依赖 username_file 与 password_file
        dicts_dir = os.path.join(npoc_conf.PROJECT_DIRECTORY, "dicts")
        u_nodes = assigned.get('username_file') or []
        p_nodes = assigned.get('password_file') or []
        u_file = next((n.value for n in u_nodes if isinstance(n, ast.Constant) and isinstance(n.value, str)), None)
        p_file = next((n.value for n in p_nodes if isinstance(n, ast.Constant) and isinstance(n.value, str)), None)

        if not u_file:
            return False, "爆破插件须在 __init__ 中声明 self.username_file = 'username_xxx.txt' 字典文件名"
        if not p_file:
            return False, "爆破插件须在 __init__ 中声明 self.password_file = 'password_xxx.txt' 字典文件名"

        if os.path.exists(dicts_dir):
            if not os.path.exists(os.path.join(dicts_dir, u_file)):
                return False, f"声明的用户名字典 '{u_file}' 在 xing/dicts/ 目录下不存在，请核对字典名称"
            if not os.path.exists(os.path.join(dicts_dir, p_file)):
                return False, f"声明的密码字典 '{p_file}' 在 xing/dicts/ 目录下不存在，请核对字典名称"

    return True, ""


def find_existing_plugin_file(plugin_name: str) -> str:
    """在所有插件子目录下查找指定名称的插件文件路径"""
    plugins_dir = npoc_conf.SYSTEM_PLUGINS_DIR
    for root, dirs, files in os.walk(plugins_dir):
        for ext in ['.py', '.yml', '.yaml']:
            target_file = f"{plugin_name}{ext}"
            if target_file in files:
                return os.path.join(root, target_file)
    return ""


def detect_plugin_dir(content: str, plugin_type: str = "") -> str:
    """
    根据插件代码内容或指定类型，智能匹配目标存储子目录 (brute / poc / sniffer)
    """
    plugins_dir = npoc_conf.SYSTEM_PLUGINS_DIR
    p_type = (plugin_type or "").lower()

    if p_type == 'brute' or 'PluginType.BRUTE' in content or 'plugin_type = "brute"' in content or "plugin_type = 'brute'" in content:
        target_dir = os.path.join(plugins_dir, 'brute')
    elif p_type == 'sniffer' or 'PluginType.SNIFFER' in content or 'plugin_type = "sniffer"' in content or "plugin_type = 'sniffer'" in content:
        target_dir = os.path.join(plugins_dir, 'sniffer')
    else:
        target_dir = os.path.join(plugins_dir, 'poc')

    os.makedirs(target_dir, exist_ok=True)
    return target_dir

base_search_fields = {
    'plugin_name': fields.String(description="PoC 名称 ID"),
    'app_name': fields.String(description="应用名称"),
    'scheme': fields.String(description="支持的协议"),
    'vul_name': fields.String(description="漏洞名称"),
    'plugin_type': fields.String(description="插件类别", enum=['poc', 'brute']),
    'update_date': fields.String(description="更新时间"),
    'category': fields.String(description="PoC 分类")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLPoC(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        PoC 信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args,  collection='poc')

        return data


@ns.route('/sync/')
class ARLPoCSync(ARLResource):

    @auth
    def get(self):
        """
        同步本地 PoC 插件信息到数据库
        """
        n = NPoC()
        plugin_cnt = len(n.plugin_name_list)
        n.sync_to_db()
        n.delete_db()

        return utils.build_ret(ErrorMsg.Success, {"plugin_cnt": plugin_cnt})


@ns.route('/delete/')
class ARLPoCDelete(ARLResource):

    @auth
    def get(self):
        """
        清空 PoC 信息
        """
        result = utils.conn_db('poc').delete_many({})
        delete_cnt = result.deleted_count

        # 级联清空 policy 表中的所有相关引用
        utils.conn_db('policy').update_many(
            {},
            {
                "$set": {
                    "policy.poc_config": [],
                    "policy.brute_config": []
                }
            }
        )

        return utils.build_ret(ErrorMsg.Success, {"delete_cnt": delete_cnt})

    @auth
    def post(self):
        """
        批量删除 PoC 信息
        """
        args = request.json or {}
        plugin_names = args.get('plugin_names', [])
        
        if not plugin_names:
            return utils.build_ret(ErrorMsg.Error, {'error': '未提供要删除的 PoC plugin_names'})

        # 1. 从 DB 删除
        result = utils.conn_db('poc').delete_many({'plugin_name': {'$in': plugin_names}})
        delete_cnt = result.deleted_count
        
        # 2. 级联清空 policy 表中的相关引用
        utils.conn_db('policy').update_many(
            {},
            {
                "$pull": {
                    "policy.poc_config": {"plugin_name": {"$in": plugin_names}},
                    "policy.brute_config": {"plugin_name": {"$in": plugin_names}}
                }
            }
        )

        # 3. 从磁盘深度递归删除实际脚本文件，彻底防止新建或子目录中的插件删除失败
        plugins_dir = npoc_conf.SYSTEM_PLUGINS_DIR
        for root, dirs, files in os.walk(plugins_dir):
            for name in plugin_names:
                for ext in ['.py', '.yml', '.yaml']:
                    target_file = f"{name}{ext}"
                    if target_file in files:
                        file_path = os.path.join(root, target_file)
                        try:
                            os.remove(file_path)
                            logger.info(f"Successfully removed poc file: {file_path}")
                        except Exception as e:
                            logger.error(f"Failed to remove poc file: {file_path}, err: {e}")

        return utils.build_ret(ErrorMsg.Success, {"delete_cnt": delete_cnt})



@ns.route('/import/')
class ARLPoCImport(ARLResource):

    @auth
    def post(self):
        """
        导入 PoC 文件 (支持单文件和多文件，仅限 Python 脚本)
        """
        if 'file' not in request.files:
            return utils.build_ret(ErrorMsg.Error, {'error': 'No file part'})

        files = request.files.getlist('file')
        if not files or len(files) == 0:
            return utils.build_ret(ErrorMsg.Error, {'error': 'No selected file'})

        plugins_dir = npoc_conf.SYSTEM_PLUGINS_DIR
        poc_dir = os.path.join(plugins_dir, 'poc')
        if not os.path.exists(poc_dir):
            os.makedirs(poc_dir, exist_ok=True)

        success_count = 0
        fail_count = 0
        fail_details = []

        for file in files:
            if not file or file.filename == '':
                continue

            safe_filename = os.path.basename(file.filename)
            base_name, ext = os.path.splitext(safe_filename)
            ext = ext.lower()

            # 仅支持 .py 格式
            if ext != '.py':
                fail_count += 1
                fail_details.append({"filename": file.filename, "reason": "不支持的文件格式，仅支持 .py 脚本"})
                continue

            # 校验文件名格式：只允许英文字母、数字和下划线，且禁止以下划线开头（防 __init__.py 及中文绕过）
            if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_]*$', base_name):
                fail_count += 1
                fail_details.append({"filename": file.filename, "reason": "插件文件名不合法（仅允许英文字母、数字和下划线，且首字符必须为英文字母或数字）"})
                continue

            # 读取内容并校验
            try:
                raw_bytes = file.read()
                try:
                    content = raw_bytes.decode('utf-8-sig')
                except UnicodeDecodeError:
                    content = raw_bytes.decode('gbk')
            except Exception as e:
                fail_count += 1
                fail_details.append({"filename": file.filename, "reason": f"文件解码失败 (需为 UTF-8 或 GBK 格式): {e}"})
                continue

            # AST 语法与规范静态校验
            is_valid, err_msg = validate_poc_script(content)
            if not is_valid:
                fail_count += 1
                fail_details.append({"filename": file.filename, "reason": err_msg})
                continue

            # 智能匹配存放目录（已有同名文件则原位覆盖更新，否则根据代码特征自动归类至 brute/ 或 poc/）
            existing_path = find_existing_plugin_file(base_name)
            if existing_path:
                save_path = existing_path
            else:
                target_dir = detect_plugin_dir(content)
                save_path = os.path.join(target_dir, safe_filename)

            try:
                with open(save_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                success_count += 1
            except Exception as e:
                fail_count += 1
                fail_details.append({"filename": file.filename, "reason": f"保存文件失败: {e}"})

        # 文件成功保存后，触发一次同步操作
        if success_count > 0:
            n = NPoC()
            try:
                n.sync_to_db()
                n.delete_db()
            except Exception as e:
                logger.error(f"PoC 同步失败: {e}")
                return utils.build_ret(ErrorMsg.Error, {'error': f'PoC 保存成功，但同步到数据库时失败: {e}'})

        return utils.build_ret(ErrorMsg.Success, {
            "success_count": success_count,
            "fail_count": fail_count,
            "fail_details": fail_details
        })

@ns.route('/source/')
class ARLPoCSource(ARLResource):

    @auth
    def get(self):
        """
        获取 PoC 源码
        """
        plugin_name = request.args.get('plugin_name')
        if not plugin_name:
            return utils.build_ret(ErrorMsg.Error, {'error': '未提供 plugin_name'})

        file_path = find_existing_plugin_file(plugin_name)
        if not file_path:
            return utils.build_ret(ErrorMsg.Error, {'error': 'PoC 文件未找到'})

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except Exception as e:
            return utils.build_ret(ErrorMsg.Error, {'error': f'读取文件失败: {e}'})

        return utils.build_ret(ErrorMsg.Success, {'content': content})

    @auth
    def post(self):
        """
        更新 PoC 源码
        """
        args = request.json or {}
        plugin_name = args.get('plugin_name')
        content = args.get('content')

        if not plugin_name or content is None:
            return utils.build_ret(ErrorMsg.Error, {'error': '未提供 plugin_name 或 content'})

        file_path = find_existing_plugin_file(plugin_name)
        if not file_path:
            return utils.build_ret(ErrorMsg.Error, {'error': 'PoC 文件未找到'})

        # 仅对 Python 脚本进行 AST 语法与结构静态校验，避免影响存量 YAML 文件
        if file_path.endswith('.py'):
            is_valid, err_msg = validate_poc_script(content)
            if not is_valid:
                return utils.build_ret(ErrorMsg.Error, {'error': f'代码校验失败: {err_msg}'})

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            return utils.build_ret(ErrorMsg.Error, {'error': f'保存文件失败: {e}'})

        # 保存后同步更新到数据库
        n = NPoC()
        try:
            n.sync_to_db()
            n.delete_db()
        except Exception as e:
            logger.error(f"PoC 同步失败: {e}")
            return utils.build_ret(ErrorMsg.Error, {'error': f'PoC 保存成功，但同步到数据库时失败: {e}'})

        return utils.build_ret(ErrorMsg.Success, {'message': '保存成功'})


@ns.route('/create/')
class ARLPoCCreate(ARLResource):

    @auth
    def post(self):
        """
        新建 PoC 源码 (仅限 Python 脚本)
        """
        args = request.json or {}
        plugin_name = args.get('plugin_name')
        content = args.get('content')
        ext = args.get('ext', '.py')

        if ext.lower() != '.py':
            return utils.build_ret(ErrorMsg.Error, {'error': '仅支持新建 .py 插件'})

        if not plugin_name or content is None:
            return utils.build_ret(ErrorMsg.Error, {'error': '未提供 plugin_name 或 content'})

        # 校验文件名格式：只允许英文字母、数字和下划线，且禁止以下划线开头（防中文绕过与保留文件冲突）
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9_]*$', plugin_name):
            return utils.build_ret(ErrorMsg.Error, {'error': '插件名称只允许英文字母、数字和下划线，且首字符必须为英文字母或数字'})

        # AST 语法与结构静态校验
        is_valid, err_msg = validate_poc_script(content)
        if not is_valid:
            return utils.build_ret(ErrorMsg.Error, {'error': f'代码校验失败: {err_msg}'})

        # 全插件子目录防重名冲突检查（防遮蔽系统内置插件或跨目录同名）
        existing_path = find_existing_plugin_file(plugin_name)
        if existing_path:
            cat_dir = os.path.basename(os.path.dirname(existing_path))
            return utils.build_ret(ErrorMsg.Error, {'error': f'该插件名称已存在（位于 {cat_dir} 插件库中），请更换！'})

        # 智能匹配存放目录（弱口令归入 brute/，常规 PoC 归入 poc/）
        target_dir = detect_plugin_dir(content, args.get('plugin_type', ''))
        file_path = os.path.join(target_dir, f"{plugin_name}.py")

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            return utils.build_ret(ErrorMsg.Error, {'error': f'保存文件失败: {e}'})

        # 保存后同步更新到数据库
        n = NPoC()
        try:
            n.sync_to_db()
            n.delete_db()
        except Exception as e:
            logger.error(f"PoC 同步失败: {e}")
            return utils.build_ret(ErrorMsg.Error, {'error': f'PoC 保存成功，但同步到数据库时失败: {e}'})

        return utils.build_ret(ErrorMsg.Success, {'message': '新建成功'})


