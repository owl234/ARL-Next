from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app import utils
from app.modules import ErrorMsg

ns = Namespace('vuln', description="漏洞信息")

logger = get_logger()

base_search_fields = {
    'plg_name': fields.String(required=False, description="plugin ID"),
    'plg_type': fields.String(description="类别"),
    'vul_category': fields.String(description="类别"),
    'vul_name': fields.String(description="漏洞名称"),
    'app_name': fields.String(description="应用名"),
    'target': fields.String(description="目标"),
    "save_date__dgt": fields.String(description="发现时间大于等于"),
    "save_date__dlt": fields.String(description="发现时间小于等于"),
    "task_id": fields.String(description="任务ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLUrl(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        漏洞 信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='vuln')

        return data


delete_vuln_fields = ns.model('deleteVulnFields',  {
    '_id': fields.List(fields.String(required=True, description="风险信息 _id")),
    'task_id': fields.String(required=False, description="可选任务 ID"),
    'source_type': fields.String(required=False, description="可选删除作用域：task | global")
})


@ns.route('/delete/')
class DeleteARLVuln(ARLResource):
    @auth
    @ns.expect(delete_vuln_fields)
    def post(self):
        """
        删除 风险信息
        """
        args = self.parse_args(delete_vuln_fields)
        from app.services.asset_cascade_service import handle_dimension_delete
        return handle_dimension_delete(
            "vuln", False, args,
            build_ret_fn=utils.build_ret, success_msg=ErrorMsg.Success, db_getter=utils.conn_db,
        )

