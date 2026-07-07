from bson import ObjectId
from flask_restx import Resource, reqparse, fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg
from app import utils

ns = Namespace('asset_npoc_service', description="资产组Npoc服务信息")

logger = get_logger()

base_search_fields = {
    'scheme': fields.String(description="系统服务名称"),
    'host': fields.String(required=False, description="host"),
    'port': fields.String(description="端口号"),
    'target': fields.String(description="目标"),
    "scope_id": fields.String(description="资产范围ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLAssetNpocService(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组Npoc服务信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='asset_npoc_service')
        return data


@ns.route('/export/')
class ARLAssetNpocServiceExport(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组Npoc服务信息导出
        """
        args = self.parser.parse_args()
        response = self.send_export_file(args=args, _type="asset_npoc_service")
        return response


delete_npocservice_fields = ns.model('deleteAssetNpocService',  {
    '_id': fields.List(fields.String(required=True, description="数据_id"))
})


@ns.route('/delete/')
class DeleteARLAssetNpocService(ARLResource):
    @auth
    @ns.expect(delete_npocservice_fields)
    def post(self):
        """
        删除资产组Npoc服务信息
        """
        args = self.parse_args(delete_npocservice_fields)
        id_list = args.pop('_id', "")

        for _id in id_list:
            query = {'_id': ObjectId(_id)}
            utils.conn_db('asset_npoc_service').delete_one(query)

        return utils.build_ret(ErrorMsg.Success, {'_id': id_list})
