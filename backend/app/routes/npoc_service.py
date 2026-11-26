from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg
from app import utils

ns = Namespace('npoc_service', description="系统服务(python)信息")

logger = get_logger()

base_search_fields = {
    'scheme': fields.String(description="系统服务名称"),
    'host': fields.String(required=False, description="host"),
    'port': fields.String(description="端口号"),
    'target': fields.String(description="目标"),
    "save_date__dgt": fields.String(description="发现时间大于等于"),
    "save_date__dlt": fields.String(description="发现时间小于等于"),
    "task_id": fields.String(description="任务ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class NpocService(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        服务信息(python)查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='npoc_service')

        return data


@ns.route('/export/')
class ARLNpocServiceExport(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        服务信息(python)导出
        """
        args = self.parser.parse_args()
        response = self.send_export_file(args=args, _type="npoc_service")
        return response


delete_npocservice_fields = ns.model('deleteNpocService', {
    '_id': fields.List(fields.String(required=True, description="数据_id")),
    'task_id': fields.String(required=False, description="可选任务 ID"),
    'source_type': fields.String(required=False, description="可选删除作用域：task | global")
})


@ns.route('/delete/')
class DeleteARLNpocService(ARLResource):
    @auth
    @ns.expect(delete_npocservice_fields)
    def post(self):
        """
        删除 Npoc 服务信息
        """
        args = self.parse_args(delete_npocservice_fields)
        from app.services.asset_cascade_service import handle_dimension_delete
        return handle_dimension_delete(
            "npoc_service", False, args,
            build_ret_fn=utils.build_ret, success_msg=ErrorMsg.Success, db_getter=utils.conn_db,
        )

