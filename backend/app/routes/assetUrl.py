from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from .http_status import HttpStatusCodes, HttpStatusResource
from app.modules import ErrorMsg
from app import utils

ns = Namespace('asset_url', description="资产组URL信息")

logger = get_logger()

base_search_fields = {
    'fld': fields.String(required=False, description="IP"),
    'site': fields.String(description="域名"),
    'url': fields.String(required=False, description="URL"),
    'content_length': fields.Integer(description="body 长度"),
    'status_code': fields.Integer(description="状态码"),
    'status_code__in': HttpStatusCodes(description="状态码多选，逗号分隔，例如 200,301,403"),
    'title': fields.String(description="标题"),
    'source': fields.String(description="来源"),
    "save_date__dgt": fields.String(description="发现时间大于等于"),
    "save_date__dlt": fields.String(description="发现时间小于等于"),
    "update_date__dgt": fields.String(description="更新时间大于等于"),
    "update_date__dlt": fields.String(description="更新时间小于等于"),
    "insert_time__dgt": fields.String(description="插入时间大于"),
    "insert_time__dlt": fields.String(description="插入时间小于"),
    "scope_id": fields.String(description="资产范围ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLAssetUrl(HttpStatusResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组URL信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='asset_url')
        return data


@ns.route('/export/')
class ARLAssetUrlExport(HttpStatusResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组URL信息导出
        """
        args = self.parser.parse_args()
        response = self.send_export_file(args=args, _type="asset_url")
        return response


delete_url_fields = ns.model('deleteAssetUrl',  {
    '_id': fields.List(fields.String(required=True, description="数据_id")),
    'scope_id': fields.String(required=False, description="可选资产组 ID")
})


@ns.route('/delete/')
class DeleteARLAssetUrl(ARLResource):
    @auth
    @ns.expect(delete_url_fields)
    def post(self):
        """
        删除资产组URL信息
        """
        args = self.parse_args(delete_url_fields)
        from app.services.asset_cascade_service import handle_dimension_delete
        return handle_dimension_delete(
            "url", True, args,
            build_ret_fn=utils.build_ret, success_msg=ErrorMsg.Success, db_getter=utils.conn_db,
        )
