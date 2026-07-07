from bson import ObjectId
from flask_restx import Resource, reqparse, fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg
from app import utils

ns = Namespace('asset_stat_finger', description="资产组指纹统计信息")

logger = get_logger()

base_search_fields = {
    'name': fields.String(required=False, description="指纹名称"),
    "cnt": fields.Integer(description="数目"),
    "scope_id": fields.String(description="资产范围ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLAssetStatFinger(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组指纹统计信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='asset_stat_finger')
        return data


@ns.route('/export/')
class ARLAssetStatFingerExport(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组指纹统计信息导出
        """
        args = self.parser.parse_args()
        response = self.send_export_file(args=args, _type="asset_stat_finger")
        return response


delete_statfinger_fields = ns.model('deleteAssetStatFinger',  {
    '_id': fields.List(fields.String(required=True, description="数据_id"))
})


@ns.route('/delete/')
class DeleteARLAssetStatFinger(ARLResource):
    @auth
    @ns.expect(delete_statfinger_fields)
    def post(self):
        """
        删除资产组指纹统计信息
        """
        args = self.parse_args(delete_statfinger_fields)
        id_list = args.pop('_id', "")

        for _id in id_list:
            query = {'_id': ObjectId(_id)}
            utils.conn_db('asset_stat_finger').delete_one(query)

        return utils.build_ret(ErrorMsg.Success, {'_id': id_list})
