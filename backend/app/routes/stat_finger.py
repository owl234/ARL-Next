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
        args = self.parser.parse_args()
        query = self.build_db_query(args)

        # 使用聚合管道来将同名指纹的 cnt 累加
        pipeline = [
            {"$match": query},
            {"$group": {
                "_id": "$name", 
                "cnt": {"$sum": "$cnt"},
                "change_status": {"$first": "$change_status"},
                "update_diff": {"$first": "$update_diff"}
            }},
            {"$project": {
                "_id": "$_id",
                "name": "$_id",
                "cnt": 1,
                "change_status": 1,
                "update_diff": 1
            }},
            {"$sort": {"cnt": -1}},
            {"$skip": (args.page - 1) * args.size},
            {"$limit": args.size}
        ]
        items = list(utils.conn_db('stat_finger').aggregate(pipeline))

        # 计算去重后的指纹总数
        count_pipeline = [
            {"$match": query},
            {"$group": {"_id": "$name"}}
        ]
        total = len(list(utils.conn_db('stat_finger').aggregate(count_pipeline)))

        return {
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
