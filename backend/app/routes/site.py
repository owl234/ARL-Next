import copy
from bson import ObjectId
from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from app.modules import ErrorMsg
from app import utils
from . import base_query_fields, ARLResource, get_arl_parser
from .http_status import HttpStatusCodes, HttpStatusResource


ns = Namespace('site', description="站点信息")

logger = get_logger()

base_search_fields = {
    'site': fields.String(required=False, description="站点URL"),
    'hostname': fields.String(description="主机名"),
    'ip': fields.String(description="ip"),
    'title': fields.String(description="标题"),
    'http_server': fields.String(description="Web servers"),
    'headers': fields.String(description="headers"),
    'finger': fields.String(description="指纹"),
    'finger__eq': fields.String(description="指纹精确匹配"),
    'status': fields.Integer(description="状态码"),
    'status__in': HttpStatusCodes(description="状态码多选，逗号分隔，例如 200,301,403"),
    'favicon.hash': fields.Integer(description="favicon hash"),
    'task_id': fields.String(description="任务 ID"),
    'tag': fields.String(description="标签列表"),
    "save_date__dgt": fields.String(description="发现时间大于等于"),
    "save_date__dlt": fields.String(description="发现时间小于等于"),
}

site_search_fields = copy.copy(base_search_fields)

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLSite(HttpStatusResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        站点信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args = args,  collection = 'site')

        return data


@ns.route('/export/')
class ARLSiteExport(HttpStatusResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        站点导出
        """
        args = self.parser.parse_args()
        response = self.send_export_file(args=args, _type="site")

        return response


save_result_set_fields = ns.model('SaveSiteResultSetFields', {
    '_id': fields.List(fields.String(required=True, description="选中的站点 _id 列表")),
    'task_id': fields.String(required=False, description="可选任务 ID 作用域约束"),
})


@ns.route('/save_result_set/')
class ARLSaveResultSet(HttpStatusResource):
    parser = get_arl_parser(site_search_fields, location='args')
    MAX_SELECTED_IDS = 500

    @staticmethod
    def _persist_site_result_set(items):
        cleaned = list(set([utils.url.cut_filename(x) for x in items if x]))
        if len(cleaned) == 0:
            return utils.build_ret(ErrorMsg.QueryResultIsEmpty, {})

        data = {
            "items": cleaned,
            "type": "site",
            "total": len(cleaned)
        }
        result = utils.conn_db('result_set').insert_one(data)

        ret_data = {
            "result_set_id": str(result.inserted_id),
            "result_total": len(cleaned),
            "type": "site",
        }
        return utils.build_ret(ErrorMsg.Success, ret_data)

    @auth
    @ns.expect(parser)
    def get(self):
        """
        按筛选条件保存站点结果集
        """
        args = self.parser.parse_args()
        query = self.build_db_query(args)
        items = utils.conn_db('site').distinct("site", query)
        return self._persist_site_result_set(items)

    @auth
    @ns.expect(save_result_set_fields)
    def post(self):
        """
        按勾选站点 _id 列表保存结果集（严格校验 ObjectId，避免空条件退化为全库查询）
        """
        args = self.parse_args(save_result_set_fields)
        raw_ids = args.get('_id')
        task_id = (args.get('task_id') or '').strip()

        if not isinstance(raw_ids, list) or len(raw_ids) == 0:
            return utils.build_ret({"code": 400, "message": "请提供有效的站点 _id 列表"}, {"count": 0})
        if len(raw_ids) > self.MAX_SELECTED_IDS:
            return utils.build_ret(
                {"code": 400, "message": f"单次最多选择 {self.MAX_SELECTED_IDS} 条站点记录"},
                {"count": len(raw_ids)},
            )

        obj_ids = []
        for raw_id in raw_ids:
            if not isinstance(raw_id, str) or not ObjectId.is_valid(raw_id.strip()):
                return utils.build_ret({"code": 400, "message": "请提供有效的站点 _id 列表"}, {"count": len(raw_ids)})
            obj_ids.append(ObjectId(raw_id.strip()))

        query = {"_id": {"$in": obj_ids}}
        if task_id:
            query["task_id"] = task_id

        items = utils.conn_db('site').distinct("site", query)
        return self._persist_site_result_set(items)


add_site_tag_fields = ns.model('AddSiteTagFields',  {
    "tag": fields.String(required=True, description="添加站点标签"),
    "_id": fields.String(description="站点ID", required=True)
})


@ns.route('/add_tag/')
class AddSiteTagARL(ARLResource):

    @auth
    @ns.expect(add_site_tag_fields)
    def post(self):
        """
        站点添加Tag
        """
        args = self.parse_args(add_site_tag_fields)
        site_id = args.pop("_id")
        tag = args.pop("tag")

        query = {"_id": ObjectId(site_id)}
        data = utils.conn_db('site').find_one(query)
        if not data:
            return utils.build_ret(ErrorMsg.SiteIdNotFound, {"site_id": site_id})

        tag_list = []
        old_tag = data.get("tag")
        if old_tag:
            if isinstance(old_tag, str):
                tag_list.append(old_tag)

            if isinstance(old_tag, list):
                tag_list.extend(old_tag)

        if tag in tag_list:
            return utils.build_ret(ErrorMsg.SiteTagIsExist, {"tag": tag})

        tag_list.append(tag)

        utils.conn_db('site').update_one(query, {"$set": {"tag": tag_list}})

        return utils.build_ret(ErrorMsg.Success, {"tag": tag})


delete_site_tag_fields = ns.model('DeleteSiteTagFields',  {
    "tag": fields.String(required=True, description="删除站点标签"),
    "_id": fields.String(description="站点ID", required=True)
})


@ns.route('/delete_tag/')
class DeleteSiteTagARL(ARLResource):

    @auth
    @ns.expect(delete_site_tag_fields)
    def post(self):
        """
        删除站点Tag
        """
        args = self.parse_args(delete_site_tag_fields)
        site_id = args.pop("_id")
        tag = args.pop("tag")

        query = {"_id": ObjectId(site_id)}
        data = utils.conn_db('site').find_one(query)
        if not data:
            return utils.build_ret(ErrorMsg.SiteIdNotFound, {"site_id": site_id})

        tag_list = []
        old_tag = data.get("tag")
        if old_tag:
            if isinstance(old_tag, str):
                tag_list.append(old_tag)

            if isinstance(old_tag, list):
                tag_list.extend(old_tag)

        if tag not in tag_list:
            return utils.build_ret(ErrorMsg.SiteTagNotExist, {"tag": tag})

        tag_list.remove(tag)

        utils.conn_db('site').update_one(query, {"$set": {"tag": tag_list}})

        return utils.build_ret(ErrorMsg.Success, {"tag": tag})


delete_site_fields = ns.model('deleteSiteFields',  {
    '_id': fields.List(fields.String(required=True, description="站点 _id")),
    'task_id': fields.String(required=False, description="可选任务 ID"),
    'source_type': fields.String(required=False, description="可选删除作用域：task | global")
})


@ns.route('/delete/')
class DeleteARLSite(ARLResource):
    @auth
    @ns.expect(delete_site_fields)
    def post(self):
        """
        删除站点（支持级联清理下级 L3 与指纹重算）
        """
        args = self.parse_args(delete_site_fields)
        from app.services.asset_cascade_service import handle_dimension_delete
        return handle_dimension_delete(
            "site", False, args,
            build_ret_fn=utils.build_ret, success_msg=ErrorMsg.Success, db_getter=utils.conn_db,
        )