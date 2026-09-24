from bson import ObjectId
from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg
from app import utils

# 成立“资产组 IP”部门，专门管理经过确认的 IP 资产
ns = Namespace('asset_ip', description="资产组IP信息")

logger = get_logger()

# ==========================================
# 表单 1：搜索正式 IP 时的可用条件
# ==========================================
base_search_fields = {
    'ip': fields.String(required=False, description="IP"),
    'domain': fields.String(description="域名"),
    # 【注意这里的写法】：带小数点的键名！这对应了 MongoDB 的嵌套查询
    'port_info.port_id': fields.Integer(description="端口号"),
    'port_info.service_name': fields.String(description="系统服务名称"),
    'port_info.version': fields.String(description="系统服务版本"),
    'port_info.product': fields.String(description="产品"),
    'os_info.name': fields.String(description="操作系统名称"),

    "task_id": fields.String(description="任务ID"),
    "update_date__dgt": fields.String(description="更新时间大于"),
    "update_date__dlt": fields.String(description="更新时间小于"),
    "scope_id": fields.String(description="资产范围ID"),
    "ip_type": fields.String(description="IP类型，公网(PUBLIC)和内网(PRIVATE)"),
    "cdn_name": fields.String(description="CDN 厂商名称")
}

# 合并分页排序基础字段
base_search_fields.update(base_query_fields)


# ==========================================
# 接口 A：查询 IP 列表 (GET /)
# ==========================================
@ns.route('/')
class ARLAssetIP(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        IP信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='asset_ip')

        return data



# ==========================================
# 接口 B：默认导出 IP (GET /export/)
# ==========================================
@ns.route('/export/')
class ARLAssetIPExport(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产分组端口导出
        """
        args = self.parser.parse_args()
        # 调用基础导出（对于 asset_ip，底层说明书会把它拼接成 IP:端口 的格式）
        response = self.send_export_file(args=args, _type="asset_ip")

        return response


# ==========================================
# 接口 C：精准导出纯 IP (GET /export_ip/)
# ==========================================
@ns.route('/export_ip/')
class ARLIPExportIp(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        从 资产分组 IP 中导出 IP
        """
        args = self.parser.parse_args()
        # 调用万能导出器！指定只从 asset_ip 表里，抠出 "ip" 这个字段
        response = self.send_export_file_attr(args=args, collection="asset_ip", field="ip")

        return response


# ==========================================
# 接口 D：精准导出域名 (GET /export_domain/)
# ==========================================
@ns.route('/export_domain/')
class ARLIPExportDomain(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        从 资产分组 IP 中导出 域名
        """
        args = self.parser.parse_args()
        response = self.send_export_file_attr(args=args, collection="asset_ip", field="domain")

        return response

# ==========================================
# 接口 E：删除 IP 记录 (POST /delete/)
# ==========================================
delete_ip_fields = ns.model('deleteAssetIP',  {
    '_id': fields.List(fields.String(required=True, description="数据_id"))
})


@ns.route('/delete/')
class DeleteARLAssetIP(ARLResource):
    @auth
    @ns.expect(delete_ip_fields)
    def post(self):
        """
        删除资产组中的IP
        """
        args = self.parse_args(delete_ip_fields)
        id_list = args.pop('_id', "")

        # 挨个物理删除
        for _id in id_list:
            query = {'_id': ObjectId(_id)}
            utils.conn_db('asset_ip').delete_one(query)

        return utils.build_ret(ErrorMsg.Success, {'_id': id_list})