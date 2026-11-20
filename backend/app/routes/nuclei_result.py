from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app import utils
from app.modules import ErrorMsg

ns = Namespace('nuclei_result', description="nuclei 扫描结果")

logger = get_logger()

base_search_fields = {
    'template_url': fields.String(required=False, description="模版文件URL"),
    'template_id': fields.String(description="模版id"),
    'template_source': fields.String(description="模版来源 (custom|community)"),
    'vuln_name': fields.String(description="漏洞名称"),
    'vuln_severity': fields.String(description="漏洞等级"),
    'vuln_url': fields.String(description="漏洞URL"),
    'curl_command': fields.String(description="curl 命令"),
    'target': fields.String(description="目标"),
    'extracted_results': fields.String(description="提取内容"),
    "task_id": fields.String(description="任务ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLUrl(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    def build_db_query(self, args):
        args_copy = dict(args)
        source_val = args_copy.pop('template_source', None)
        q = super().build_db_query(args_copy)
        if source_val == 'community':
            q.setdefault('$and', []).append({
                '$or': [
                    {'template_source': 'community'},
                    {'template_source': {'$exists': False}},
                    {'template_source': None},
                    {'template_source': ''},
                ]
            })
        elif source_val:
            q['template_source'] = source_val
        return q

    @auth
    @ns.expect(parser)
    def get(self):
        """
        nuclei 扫描结果查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='nuclei_result')

        return data


delete_nuclei_result_fields = ns.model('deleteNucleiResultFields',  {
    '_id': fields.List(fields.String(required=True, description="nuclei 扫描结果 _id")),
    'task_id': fields.String(required=False, description="可选任务 ID"),
    'source_type': fields.String(required=False, description="可选删除作用域：task | global")
})


@ns.route('/delete/')
class DeleteNucleiResult(ARLResource):
    @auth
    @ns.expect(delete_nuclei_result_fields)
    def post(self):
        """
        删除 nuclei 扫描结果
        """
        args = self.parse_args(delete_nuclei_result_fields)
        from app.services.asset_cascade_service import handle_dimension_delete
        return handle_dimension_delete(
            "nuclei_result", False, args,
            build_ret_fn=utils.build_ret, success_msg=ErrorMsg.Success, db_getter=utils.conn_db,
        )

