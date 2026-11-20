from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg
from app import utils

ns = Namespace('service', description="系统服务信息")

logger = get_logger()

base_search_fields = {
    'service_name': fields.String(description="系统服务名称"),
    'service_info.ip': fields.String(required=False, description="IP"),
    'service_info.port_id': fields.Integer(description="端口号"),
    'service_info.version': fields.String(description="系统服务版本"),
    'service_info.product': fields.String(description="产品"),
    "task_id": fields.String(description="任务ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLService(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        服务信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='service')

        return data


delete_service_fields = ns.model('deleteService', {
    '_id': fields.List(fields.String(required=True, description="数据_id")),
    'task_id': fields.String(required=False, description="可选任务 ID"),
    'source_type': fields.String(required=False, description="可选删除作用域：task | global")
})


@ns.route('/delete/')
class DeleteARLService(ARLResource):
    @auth
    @ns.expect(delete_service_fields)
    def post(self):
        """
        删除系统服务信息（按端点级精确剥离端口）
        """
        args = self.parse_args(delete_service_fields)
        from app.services.asset_cascade_service import handle_dimension_delete
        return handle_dimension_delete(
            "service", False, args,
            build_ret_fn=utils.build_ret, success_msg=ErrorMsg.Success, db_getter=utils.conn_db,
        )

