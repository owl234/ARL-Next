from bson import ObjectId
from flask_restx import Resource, reqparse, fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
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
    'title': fields.String(description="标题"),
    'source': fields.String(description="来源"),
    "scope_id": fields.String(description="资产范围ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLAssetUrl(ARLResource):
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
class ARLAssetUrlExport(ARLResource):
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
    '_id': fields.List(fields.String(required=True, description="数据_id"))
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
        id_list = args.pop('_id', "")

        for _id in id_list:
            query = {'_id': ObjectId(_id)}
            utils.conn_db('asset_url').delete_one(query)

        return utils.build_ret(ErrorMsg.Success, {'_id': id_list})
