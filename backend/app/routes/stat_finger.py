from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from app.modules import ErrorMsg
from . import base_query_fields, ARLResource, get_arl_parser
from app import utils

ns = Namespace('stat_finger', description="指纹统计信息")

logger = get_logger()

base_search_fields = {
    'name': fields.String(required=False, description="指纹名称"),  # 字段名没搞好
    'name__eq': fields.String(required=False, description="指纹名称精确匹配"),
    "task_id": fields.String(description="任务 ID"),
    "cnt": fields.Integer(description="数目"),
    "save_date__dgt": fields.String(description="发现时间大于等于"),
    "save_date__dlt": fields.String(description="发现时间小于等于"),
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLStatFingerprint(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        指纹统计信息查询
        """
        args_dict = dict(self.parser.parse_args())
        has_custom_order = bool(args_dict.get("order"))
        default_field = self.get_default_field(args_dict)
        page = default_field.get("page", 1)
        size = default_field.get("size", 10)
        orderby_list = default_field.get("order", [("_id", -1)])

        query = self.build_db_query(args_dict)
        post_save_date_filter = query.pop("save_date", None)

        if has_custom_order:
            sort_dict = {field: direction for field, direction in orderby_list}
            if "cnt" not in sort_dict:
                sort_dict["cnt"] = -1
        else:
            sort_dict = {"cnt": -1, "_id": 1}

        # 使用聚合管道将同名指纹 cnt 累加，发现时间严格取首次出现 ($min)，最近出现取 ($max)
        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$name",
                "cnt": {"$sum": "$cnt"},
                "change_status": {"$first": "$change_status"},
                "update_diff": {"$first": "$update_diff"},
                "save_date": {"$min": "$save_date"},
                "latest_save_date": {"$max": "$save_date"},
                "raw_update_date": {"$max": "$update_date"},
            }},
            {"$addFields": {
                "update_date": {"$max": ["$raw_update_date", "$latest_save_date"]},
            }},
        ]
        if post_save_date_filter is not None:
            pipeline.append({"$match": {"save_date": post_save_date_filter}})
        pipeline.extend([
            {"$project": {
                "_id": "$_id",
                "name": "$_id",
                "cnt": 1,
                "change_status": 1,
                "update_diff": 1,
                "save_date": 1,
                "update_date": 1,
            }},
            {"$sort": sort_dict},
            {"$skip": (page - 1) * size},
            {"$limit": size}
        ])
        raw_items = list(self._aggregate(utils.conn_db('stat_finger'), pipeline))
        items = self.build_return_items(raw_items)

        # 计算去重后的指纹总数（与 post-group 时间筛选严格一致）
        count_pipeline = [
            {"$match": query},
            {"$group": {"_id": "$name", "save_date": {"$min": "$save_date"}}},
        ]
        if post_save_date_filter is not None:
            count_pipeline.append({"$match": {"save_date": post_save_date_filter}})
        total = len(list(self._aggregate(utils.conn_db('stat_finger'), count_pipeline)))

        return {
            "page": page,
            "size": size,
            "total": total,
            "items": items,
            "code": 200
        }


delete_result_fields = ns.model('deleteStatFinger', {
    '_id': fields.List(fields.String, required=False, description="指纹记录 _id 或指纹名称列表"),
    'name': fields.List(fields.String, required=False, description="指纹名称列表"),
    'task_id': fields.String(required=False, description="可选任务 ID（限定任务作用域）"),
    'source_type': fields.String(required=False, description="可选删除作用域：task | global")
})


@ns.route('/delete/')
class DeleteARLStatFingerprint(ARLResource):
    @auth
    @ns.expect(delete_result_fields)
    def post(self):
        """
        删除指纹统计信息（同时从对应作用域站点的 finger 数组中剥离该指纹，保留宿主站点）
        """
        args = self.parse_args(delete_result_fields)
        from app.services.asset_cascade_service import handle_dimension_delete
        return handle_dimension_delete(
            "stat_finger", False, args,
            build_ret_fn=utils.build_ret, success_msg=ErrorMsg.Success, db_getter=utils.conn_db,
        )
