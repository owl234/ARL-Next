from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg
from app import utils

ns = Namespace('asset_stat_finger', description="资产组指纹统计信息")

logger = get_logger()

base_search_fields = {
    'name': fields.String(required=False, description="指纹名称"),
    'name__eq': fields.String(required=False, description="指纹名称精确匹配"),
    "cnt": fields.Integer(description="数目"),
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
class ARLAssetStatFinger(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组指纹统计信息查询
        """
        args_dict = dict(self.parser.parse_args())
        has_custom_order = bool(args_dict.get("order"))
        default_field = self.get_default_field(args_dict)
        page = default_field.get("page", 1)
        size = default_field.get("size", 10)
        orderby_list = default_field.get("order", [("_id", -1)])

        query = self.build_db_query(args_dict)
        post_save_date_filter = query.pop("save_date", None)
        post_update_date_filter = query.pop("update_date", None)

        if has_custom_order:
            sort_dict = {field: direction for field, direction in orderby_list}
            if "cnt" not in sort_dict:
                sort_dict["cnt"] = -1
        else:
            sort_dict = {"cnt": -1, "_id": 1}

        post_match = {}
        if post_save_date_filter is not None:
            post_match["save_date"] = post_save_date_filter
        if post_update_date_filter is not None:
            post_match["update_date"] = post_update_date_filter

        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$name",
                "cnt": {"$sum": "$cnt"},
                "save_date": {"$min": "$save_date"},
                "latest_save_date": {"$max": "$save_date"},
                "raw_update_date": {"$max": "$update_date"},
            }},
            {"$addFields": {
                "update_date": {"$max": ["$raw_update_date", "$latest_save_date"]},
            }},
        ]
        if post_match:
            pipeline.append({"$match": post_match})
        pipeline.extend([
            {"$project": {
                "_id": "$_id",
                "name": "$_id",
                "cnt": 1,
                "save_date": 1,
                "update_date": 1,
            }},
            {"$sort": sort_dict},
            {"$skip": (page - 1) * size},
            {"$limit": size}
        ])
        raw_items = list(self._aggregate(utils.conn_db('asset_stat_finger'), pipeline))
        items = self.build_return_items(raw_items)

        count_pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$name",
                "save_date": {"$min": "$save_date"},
                "latest_save_date": {"$max": "$save_date"},
                "raw_update_date": {"$max": "$update_date"},
            }},
            {"$addFields": {
                "update_date": {"$max": ["$raw_update_date", "$latest_save_date"]},
            }},
        ]
        if post_match:
            count_pipeline.append({"$match": post_match})
        total = len(list(self._aggregate(utils.conn_db('asset_stat_finger'), count_pipeline)))

        return {
            "page": page,
            "size": size,
            "total": total,
            "items": items,
            "code": 200
        }


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
    '_id': fields.List(fields.String(required=False, description="数据 _id 或指纹名称")),
    'name': fields.List(fields.String(required=False, description="指纹名称列表")),
    'scope_id': fields.String(required=False, description="资产组 ID（按指纹名称删除时必填）")
})


@ns.route('/delete/')
class DeleteARLAssetStatFinger(ARLResource):
    @auth
    @ns.expect(delete_statfinger_fields)
    def post(self):
        """
        删除资产组指纹统计信息（同步从资产组站点 finger 中剥离该指纹，保留宿主站点）
        """
        args = self.parse_args(delete_statfinger_fields)
        from app.services.asset_cascade_service import handle_dimension_delete
        return handle_dimension_delete(
            "stat_finger", True, args,
            build_ret_fn=utils.build_ret, success_msg=ErrorMsg.Success, db_getter=utils.conn_db,
        )
