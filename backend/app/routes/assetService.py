from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from .service import ServiceResource
from app.modules import ErrorMsg
from app import utils

ns = Namespace('asset_service', description="资产组系统服务信息")

logger = get_logger()

base_search_fields = {
    'service_name': fields.String(description="系统服务/协议名称"),
    'scheme': fields.String(description="协议名称(兼容别名)"),
    'ip': fields.String(required=False, description="IP/主机"),
    'host': fields.String(required=False, description="主机(兼容别名)"),
    'port_id': fields.String(description="端口号"),
    'port': fields.String(description="端口号(兼容别名)"),
    'product': fields.String(description="服务产品"),
    'version': fields.String(description="服务版本"),
    'target': fields.String(description="目标URI"),
    'sources': fields.String(description="识别来源 (nmap | npoc)"),
    'source': fields.String(description="识别来源(兼容别名)"),
    'service_info.ip': fields.String(required=False, description="IP(兼容字段)"),
    'service_info.port_id': fields.String(description="端口号(兼容字段)"),
    'service_info.version': fields.String(description="系统服务版本(兼容字段)"),
    'service_info.product': fields.String(description="产品(兼容字段)"),
    "save_date__dgt": fields.String(description="发现时间大于等于"),
    "save_date__dlt": fields.String(description="发现时间小于等于"),
    "update_date__dgt": fields.String(description="更新时间大于等于"),
    "update_date__dlt": fields.String(description="更新时间小于等于"),
    "insert_time__dgt": fields.String(description="插入时间大于"),
    "insert_time__dlt": fields.String(description="插入时间小于"),
    "scope_id": fields.String(description="资产范围ID"),
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLAssetService(ServiceResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组系统服务信息查询（融合 Nmap 与 Python 插件识别结果）
        """
        args = self.parser.parse_args()
        return self.build_data(args=args, collection='asset_service')


@ns.route('/export/')
class ARLAssetServiceExport(ServiceResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组系统服务信息导出
        """
        args = self.parser.parse_args()
        return self.send_export_file(args=args, _type="asset_service")


delete_service_fields = ns.model('deleteAssetService', {
    '_id': fields.List(fields.String(required=True, description="数据_id")),
    'scope_id': fields.String(required=False, description="可选资产组 ID")
})


@ns.route('/delete/')
class DeleteARLAssetService(ARLResource):
    @auth
    @ns.expect(delete_service_fields)
    def post(self):
        """
        删除资产组中的系统服务（端点级精确联动）
        """
        args = self.parse_args(delete_service_fields)
        from app.services.asset_cascade_service import handle_dimension_delete
        return handle_dimension_delete(
            "service", True, args,
            build_ret_fn=utils.build_ret, success_msg=ErrorMsg.Success, db_getter=utils.conn_db,
        )
