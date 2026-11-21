from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg
from app import utils

ns = Namespace('asset_nuclei_result', description="资产组Nuclei漏洞信息")

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
    "save_date__dgt": fields.String(description="发现时间大于等于"),
    "save_date__dlt": fields.String(description="发现时间小于等于"),
    "update_date__dgt": fields.String(description="更新时间大于等于"),
    "update_date__dlt": fields.String(description="更新时间小于等于"),
    "scope_id": fields.String(description="资产范围ID")
}

base_search_fields.update(base_query_fields)


def _apply_template_source_query(resource, args):
    args_copy = dict(args)
    source_val = args_copy.pop('template_source', None)
    q = ARLResource.build_db_query(resource, args_copy)
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


@ns.route('/')
class ARLAssetNucleiResult(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    def build_db_query(self, args):
        return _apply_template_source_query(self, args)

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组Nuclei漏洞信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='asset_nuclei_result')
        return data


@ns.route('/export/')
class ARLAssetNucleiResultExport(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    def build_db_query(self, args):
        return _apply_template_source_query(self, args)

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组Nuclei漏洞信息导出
        """
        args = self.parser.parse_args()
        response = self.send_export_file(args=args, _type="asset_nuclei_result")
        return response


delete_nucleiresult_fields = ns.model('deleteAssetNucleiResult',  {
    '_id': fields.List(fields.String(required=True, description="数据_id")),
    'scope_id': fields.String(required=False, description="可选资产组 ID")
})


@ns.route('/delete/')
class DeleteARLAssetNucleiResult(ARLResource):
    @auth
    @ns.expect(delete_nucleiresult_fields)
    def post(self):
        """
        删除资产组Nuclei漏洞信息
        """
        args = self.parse_args(delete_nucleiresult_fields)
        from app.services.asset_cascade_service import handle_dimension_delete
        return handle_dimension_delete(
            "nuclei_result", True, args,
            build_ret_fn=utils.build_ret, success_msg=ErrorMsg.Success, db_getter=utils.conn_db,
        )
