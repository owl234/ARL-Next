from bson import ObjectId
import os
from flask import request
from xing.conf import Conf as npoc_conf
from flask_restx import Resource, Api, reqparse, fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.services.npoc import NPoC
from app import utils, celerytask
from app.modules import ErrorMsg, TaskStatus, CeleryAction
import copy

ns = Namespace('poc', description="PoC信息")

logger = get_logger()

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
        更新 PoC 信息
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

        return utils.build_ret(ErrorMsg.Success, {"delete_cnt": delete_cnt})



@ns.route('/import/')
class ARLPoCImport(ARLResource):

    @auth
    def post(self):
        """
        导入 PoC 文件 (支持单文件和多文件)
        """
        if 'file' not in request.files:
            return utils.build_ret(ErrorMsg.ParamError, {'error': 'No file part'})

        files = request.files.getlist('file')
        if not files or len(files) == 0:
            return utils.build_ret(ErrorMsg.ParamError, {'error': 'No selected file'})

        plugins_dir = npoc_conf.SYSTEM_PLUGINS_DIR
        
        success_count = 0
        fail_count = 0
        fail_details = []
        
        for file in files:
            if file.filename == '':
                continue
                
            # 只支持 .py, .yml, .yaml
            ext = os.path.splitext(file.filename)[1].lower()
            if ext not in ['.py', '.yml', '.yaml']:
                fail_count += 1
                fail_details.append({"filename": file.filename, "reason": "不支持的文件格式，仅支持 .py, .yml, .yaml"})
                continue
                
            try:
                # 简单防止路径穿越
                safe_filename = os.path.basename(file.filename)
                save_path = os.path.join(plugins_dir, safe_filename)
                file.save(save_path)
                success_count += 1
            except Exception as e:
                fail_count += 1
                fail_details.append({"filename": file.filename, "reason": str(e)})

        # 文件保存后，触发一次同步操作
        n = NPoC()
        plugin_cnt_before = len(n.plugin_name_list)
        
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
