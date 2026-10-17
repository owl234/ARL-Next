from bson import ObjectId
from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from app import utils
from app.modules import ErrorMsg
from . import base_query_fields, ARLResource, get_arl_parser
from .http_status import HttpStatusCodes, HttpStatusResource

ns = Namespace('url', description="URL信息")

logger = get_logger()

base_search_fields = {
    'fld': fields.String(required=False, description="IP"),
    'site': fields.String(description="域名"),
    'url': fields.String(required=False, description="URL"),
    'content_length': fields.Integer(description="body 长度"),
    'content_length__gt': fields.Integer(description="body 长度大于"),
    'content_length__lt': fields.Integer(description="body 长度小于"),
    'status_code': fields.Integer(description="状态码"),
    'status_code__in': HttpStatusCodes(description="状态码多选，逗号分隔，例如 200,301,403"),
    'title': fields.String(description="标题"),
    'source': fields.String(description="来源"),
    "task_id": fields.String(description="任务ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLUrl(HttpStatusResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        URL信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='url')

        return data


@ns.route('/export/')
class ARLUrlExport(HttpStatusResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        URL 导出
        """
        args = self.parser.parse_args()
        response = self.send_export_file(args=args, _type="url")

        return response


delete_result_fields = ns.model('deleteUrlResult', {
    '_id': fields.List(fields.String, required=True, description="待删除的记录 ID")
})


@ns.route('/delete/')
class DeleteARLUrl(ARLResource):
    @auth
    @ns.expect(delete_result_fields, validate=True)
    def post(self):
        """删除任务 URL 结果。"""
        args = self.parse_args(delete_result_fields)
        id_list = args.get('_id') or []
        # 先校验整批，避免无效 ID 导致前面的记录已被删除。
        if not id_list or any(not ObjectId.is_valid(value) for value in id_list):
            return utils.build_ret(
                {"code": 999, "message": "请提供有效的记录 ID 列表"}, {'_id': id_list}
            )
        result = utils.conn_db('url').delete_many({'_id': {'$in': [ObjectId(value) for value in id_list]}})
        return utils.build_ret(ErrorMsg.Success, {'_id': id_list, 'deleted_count': result.deleted_count})
