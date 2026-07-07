from bson import ObjectId
from flask_restx import Resource, reqparse, fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg
from app import utils

ns = Namespace('asset_fileleak', description="资产组文件泄露信息")

logger = get_logger()

base_search_fields = {
    'url': fields.String(required=False, description="URL"),
    'site': fields.String(description="站点"),
    'content_length': fields.Integer(description="body 长度"),
    'status_code': fields.Integer(description="状态码"),
    'title': fields.String(description="标题"),
    "scope_id": fields.String(description="资产范围ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLAssetFileleak(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组文件泄露信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='asset_fileleak')
        return data


@ns.route('/export/')
class ARLAssetFileleakExport(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组文件泄露信息导出
        """
        args = self.parser.parse_args()
        response = self.send_export_file(args=args, _type="asset_fileleak")
        return response


delete_fileleak_fields = ns.model('deleteAssetFileleak',  {
    '_id': fields.List(fields.String(required=True, description="数据_id"))
})


@ns.route('/delete/')
class DeleteARLAssetFileleak(ARLResource):
    @auth
    @ns.expect(delete_fileleak_fields)
    def post(self):
        """
        删除资产组文件泄露信息
        """
        args = self.parse_args(delete_fileleak_fields)
        id_list = args.pop('_id', "")

        for _id in id_list:
            query = {'_id': ObjectId(_id)}
            utils.conn_db('asset_fileleak').delete_one(query)

        return utils.build_ret(ErrorMsg.Success, {'_id': id_list})
