from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from app import utils
from app.modules import ErrorMsg
from . import base_query_fields, ARLResource, get_arl_parser

ns = Namespace('ip', description="IP信息")

logger = get_logger()

base_search_fields = {
    'ip': fields.String(required=False, description="IP"),
    'domain': fields.String(description="域名"),
    'port_info.port_id': fields.Integer(description="端口号"),
    'port_info.service_name': fields.String(description="系统服务名称"),
    'port_info.version': fields.String(description="系统服务版本"),
    'port_info.product': fields.String(description="产品"),
    'os_info.name': fields.String(description="操作系统名称"),
    "task_id": fields.String(description="任务ID"),
    "c_segment": fields.String(description="C段"),
    "ip_type": fields.String(description="IP类型，公网(PUBLIC)和内网(PRIVATE)"),
    "cdn_name": fields.String(description="CDN 厂商名称"),
    "geo_asn.number": fields.Integer(description="AS number"),
    "geo_asn.organization": fields.String(description="AS organization"),
    "geo_city.region_name": fields.String(description="GEO region_name"),
    "is_cdn": fields.String(description="是否为CDN (true/false)"),
    "save_date__dgt": fields.String(description="发现时间大于等于"),
    "save_date__dlt": fields.String(description="发现时间小于等于"),
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLIP(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        IP信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='ip')

        return data


@ns.route('/export/')
class ARLIPExport(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        端口导出
        """
        args = self.parser.parse_args()
        response = self.send_export_file(args=args, _type="ip")

        return response


@ns.route('/export_domain/')
class ARLIPExportDomain(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        从 IP 中导出域名
        """
        args = self.parser.parse_args()
        response = self.send_export_file_attr(args=args, collection="ip", field="domain")

        return response


@ns.route('/export_ip/')
class ARLIPExportIp(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        从 IP 中导出 IP
        """
        args = self.parser.parse_args()
        response = self.send_export_file_attr(args=args, collection="ip", field="ip")

        return response


delete_ip_fields = ns.model('deleteIpFields',  {
    '_id': fields.List(fields.String(required=True, description="IP _id")),
    'task_id': fields.String(required=False, description="可选任务 ID"),
    'source_type': fields.String(required=False, description="可选删除作用域：task | global")
})


@ns.route('/delete/')
class DeleteARLIP(ARLResource):
    @auth
    @ns.expect(delete_ip_fields)
    def post(self):
        """
        删除 IP（支持向下级联并向上解绑保留子域名）
        """
        args = self.parse_args(delete_ip_fields)
        from app.services.asset_cascade_service import handle_dimension_delete
        return handle_dimension_delete(
            "ip", False, args,
            build_ret_fn=utils.build_ret, success_msg=ErrorMsg.Success, db_getter=utils.conn_db,
        )
