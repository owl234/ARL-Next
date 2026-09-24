from bson import ObjectId
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
    "cdn_type": fields.String(description="CDN过滤类型: all/origin/cdn"),
    "is_cdn": fields.Boolean(description="是否CDN"),
    "geo_asn.number": fields.Integer(description="AS number"),
    "geo_asn.organization": fields.String(description="AS organization"),
    "geo_city.region_name": fields.String(description="GEO region_name")
}

base_search_fields.update(base_query_fields)


class BaseIPResource(ARLResource):
    """任务详情 IP 基础资源类：提供统一的 CDN 状态动态条件构造"""
    def build_db_query(self, args):
        args_copy = dict(args) if args else {}
        cdn_type = args_copy.pop("cdn_type", None)
        is_cdn = args_copy.pop("is_cdn", None)

        # 归一化布尔判定，防止字符串/整型松散类型失效
        is_origin_req = cdn_type == "origin" or is_cdn in (False, "false", "False", 0)
        is_cdn_req = cdn_type == "cdn" or is_cdn in (True, "true", "True", 1)

        # 防御幽灵参数互斥：当明确指定筛选独立源站时，剥离前端可能残留的 cdn_name 检索词
        if is_origin_req:
            args_copy.pop("cdn_name", None)

        q = super().build_db_query(args_copy)

        if is_origin_req:
            q.setdefault("$and", []).extend([
                {"$or": [{"is_cdn": False}, {"is_cdn": {"$exists": False}}]},
                {"$or": [{"cdn_name": ""}, {"cdn_name": None}, {"cdn_name": {"$exists": False}}]}
            ])
        elif is_cdn_req:
            # 采用 append 进入 $and 数组，彻底规避直接顶层赋值破坏原有 $or 查询条件的风险
            q.setdefault("$and", []).append({
                "$or": [
                    {"is_cdn": True},
                    {"cdn_name": {"$exists": True, "$nin": ["", None]}}
                ]
            })

        return q


@ns.route('/')
class ARLIP(BaseIPResource):
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
class ARLIPExport(BaseIPResource):
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
class ARLIPExportDomain(BaseIPResource):
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
class ARLIPExportIp(BaseIPResource):
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
    '_id': fields.List(fields.String(required=True, description="IP _id"))
})


@ns.route('/delete/')
class DeleteARLIP(ARLResource):
    @auth
    @ns.expect(delete_ip_fields)
    def post(self):
        """
        删除 IP
        """
        args = self.parse_args(delete_ip_fields)
        id_list = args.pop('_id', [])
        for _id in id_list:
            query = {'_id': ObjectId(_id)}
            utils.conn_db('ip').delete_one(query)

        return utils.build_ret(ErrorMsg.Success, {'_id': id_list})
