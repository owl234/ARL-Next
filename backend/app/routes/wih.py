from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg
from app import utils

ns = Namespace('wih', description="WEB Info Hunter 信息")

logger = get_logger()

base_search_fields = {
    'record_type': fields.String(required=False, description="记录类型"),
    'record_type__eq': fields.String(required=False, description="记录类型精确匹配"),
    'record_type__neq': fields.String(required=False, description="记录类型不等于（全匹配）"),
    'record_type__not': fields.String(required=False, description="记录类型不包含"),
    'content': fields.String(description="内容"),
    'source': fields.String(description="来源 JS URL"),
    'site': fields.String(description="站点URL"),
    "save_date__dgt": fields.String(description="发现时间大于等于"),
    "save_date__dlt": fields.String(description="发现时间小于等于"),
    'task_id': fields.String(description="任务ID"),
}


base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLWebInfoHunter(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        WEB Info Hunter 信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='wih')

        return data


@ns.route('/export/')
class ARLWihExport(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        WIH 导出
        """
        args = self.parser.parse_args()
        response = self.send_export_file(args=args, _type="wih")

        return response


delete_wih_fields = ns.model('deleteWih',  {
    '_id': fields.List(fields.String(required=True, description="数据_id")),
    'task_id': fields.String(required=False, description="可选任务 ID"),
    'source_type': fields.String(required=False, description="可选删除作用域：task | global")
})


@ns.route('/delete/')
class DeleteARLWIH(ARLResource):
    @auth
    @ns.expect(delete_wih_fields)
    def post(self):
        """
        删除任务中的 wih 数据
        """
        args = self.parse_args(delete_wih_fields)
        from app.services.asset_cascade_service import handle_dimension_delete
        return handle_dimension_delete(
            "wih", False, args,
            build_ret_fn=utils.build_ret, success_msg=ErrorMsg.Success, db_getter=utils.conn_db,
        )