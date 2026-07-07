from bson import ObjectId
from flask_restx import Resource, reqparse, fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg
from app import utils

ns = Namespace('asset_service', description="资产组系统服务信息")

logger = get_logger()

base_search_fields = {
    'service_name': fields.String(description="系统服务名称"),
    'service_info.ip': fields.String(required=False, description="IP"),
    'service_info.port_id': fields.Integer(description="端口号"),
    'service_info.version': fields.String(description="系统服务版本"),
    'service_info.product': fields.String(description="产品"),
    "scope_id": fields.String(description="资产范围ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLAssetService(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组系统服务信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='asset_service')
        return data


delete_service_fields = ns.model('deleteAssetService',  {
    '_id': fields.List(fields.String(required=True, description="数据_id"))
})


@ns.route('/delete/')
class DeleteARLAssetService(ARLResource):
    @auth
    @ns.expect(delete_service_fields)
    def post(self):
        """
        删除资产组中的系统服务
        """
        args = self.parse_args(delete_service_fields)
        id_list = args.pop('_id', "")

        for _id in id_list:
            query = {'_id': ObjectId(_id)}
            utils.conn_db('asset_service').delete_one(query)

        return utils.build_ret(ErrorMsg.Success, {'_id': id_list})
