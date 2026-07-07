from bson import ObjectId
from flask_restx import Resource, reqparse, fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg
from app import utils

ns = Namespace('asset_vuln', description="资产组漏洞信息")

logger = get_logger()

base_search_fields = {
    'plg_name': fields.String(required=False, description="plugin ID"),
    'plg_type': fields.String(description="类别"),
    'vul_name': fields.String(description="漏洞名称"),
    'app_name': fields.String(description="应用名"),
    'target': fields.String(description="目标"),
    "scope_id": fields.String(description="资产范围ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLAssetVuln(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组漏洞信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='asset_vuln')
        return data


@ns.route('/export/')
class ARLAssetVulnExport(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组漏洞信息导出
        """
        args = self.parser.parse_args()
        response = self.send_export_file(args=args, _type="asset_vuln")
        return response


delete_vuln_fields = ns.model('deleteAssetVuln',  {
    '_id': fields.List(fields.String(required=True, description="数据_id"))
})


@ns.route('/delete/')
class DeleteARLAssetVuln(ARLResource):
    @auth
    @ns.expect(delete_vuln_fields)
    def post(self):
        """
        删除资产组漏洞信息
        """
        args = self.parse_args(delete_vuln_fields)
        id_list = args.pop('_id', "")

        for _id in id_list:
            query = {'_id': ObjectId(_id)}
            utils.conn_db('asset_vuln').delete_one(query)

        return utils.build_ret(ErrorMsg.Success, {'_id': id_list})
