from bson import ObjectId
from flask_restx import Resource, reqparse, fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg
from app import utils

ns = Namespace('asset_cip', description="资产组C段信息")

logger = get_logger()

base_search_fields = {
    'cidr_ip': fields.String(required=False, description="C段"),
    "ip_count": fields.Integer(description="IP 个数"),
    "domain_count": fields.Integer(description="解析到该 C 段域名个数"),
    "scope_id": fields.String(description="资产范围ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLAssetCip(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组C段信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='asset_cip')
        return data


@ns.route('/export/')
class ARLAssetCipExport(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组C段信息导出
        """
        args = self.parser.parse_args()
        response = self.send_export_file(args=args, _type="asset_cip")
        return response


delete_cip_fields = ns.model('deleteAssetCip',  {
    '_id': fields.List(fields.String(required=True, description="数据_id"))
})


@ns.route('/delete/')
class DeleteARLAssetCip(ARLResource):
    @auth
    @ns.expect(delete_cip_fields)
    def post(self):
        """
        删除资产组C段信息
        """
        args = self.parse_args(delete_cip_fields)
        id_list = args.pop('_id', "")

        for _id in id_list:
            query = {'_id': ObjectId(_id)}
            utils.conn_db('asset_cip').delete_one(query)

        return utils.build_ret(ErrorMsg.Success, {'_id': id_list})
