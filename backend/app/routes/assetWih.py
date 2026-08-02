from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from bson import ObjectId
from app.modules import ErrorMsg
from app import utils

ns = Namespace('asset_wih', description="资产组 WEB Info Hunter 信息")

logger = get_logger()

base_search_fields = {
    'record_type': fields.String(required=False, description="记录类型"),
    'record_type__neq': fields.String(required=False, description="记录类型不等于（全匹配）"),
    'record_type__not': fields.String(required=False, description="记录类型不包含"),
    'content': fields.String(description="内容"),
    'source': fields.String(description="来源 JS URL"),
    'site': fields.String(description="站点URL"),
    "update_date__dgt": fields.String(description="更新时间大于"),
    "update_date__dlt": fields.String(description="更新时间小于"),
    'scope_id': fields.String(description="范围 ID")
}


base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLAssetWebInfoHunter(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组 WEB Info Hunter 信息查询 (使用聚合管道按 fnv_hash 聚合关联站点)
        """
        args = self.parser.parse_args()
        
        # 1. 提取基础控制参数
        default_field = self.get_default_field(args)
        page = default_field.get("page", 1)
        size = default_field.get("size", 10)
        orderby_list = default_field.get('order', [("_id", -1)])
        
        # 2. 获取 match 条件
        query = self.build_db_query(args)

        # 3. 构造 aggregation pipeline
        sort_dict = {field: direction for field, direction in orderby_list}
        
        pipeline_data = [
            {"$match": query},
            {
                "$group": {
                    "_id": "$fnv_hash",
                    "fnv_hash": {"$first": "$fnv_hash"},
                    "record_type": {"$first": "$record_type"},
                    "content": {"$first": "$content"},
                    "source": {"$first": "$source"},
                    "scope_id": {"$first": "$scope_id"},
                    "sites": {"$addToSet": "$site"},
                    "site": {"$first": "$site"},  # 兼容旧前端字段
                    "save_date": {"$first": "$save_date"},
                    "update_date": {"$max": "$update_date"}
                }
            },
            {"$sort": sort_dict},
            {"$skip": size * (page - 1)},
            {"$limit": size}
        ]

        # 4. 构造 count pipeline
        pipeline_count = [
            {"$match": query},
            {"$group": {"_id": "$fnv_hash"}},
            {"$count": "total"}
        ]

        result = list(utils.conn_db('asset_wih').aggregate(pipeline_data))
        count_res = list(utils.conn_db('asset_wih').aggregate(pipeline_count))
        total = count_res[0]["total"] if count_res else 0

        # 5. 格式化数据并返回
        items = self.build_return_items(result)
        
        # 兼容基类 query 日志转换
        special_keys = ["_id", "save_date", "update_date"]
        for key in query:
            if key in special_keys:
                query[key] = str(query[key])
            import re
            if isinstance(query[key], dict) and "$not" in query[key]:
                if isinstance(query[key]["$not"], type(re.compile(""))):
                    query[key]["$not"] = query[key]["$not"].pattern

        return {
            "page": page,
            "size": size,
            "total": total,
            "items": items,
            "query": query,
            "code": 200
        }


@ns.route('/export/')
class ARLAssetWIHExport(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产分组 WIH 导出
        """
        args = self.parser.parse_args()
        response = self.send_export_file(args=args, _type="asset_wih")

        return response


delete_asset_wih_fields = ns.model('deleteAssetWih',  {
    '_id': fields.List(fields.String(required=True, description="数据_id"))
})


@ns.route('/delete/')
class DeleteARLAssetWIH(ARLResource):
    @auth
    @ns.expect(delete_asset_wih_fields)
    def post(self):
        """
        批量删除资产组中的 wih 数据（按 fnv_hash 或 ObjectId 删除，整组消除）
        """
        args = self.parse_args(delete_asset_wih_fields)
        id_list = args.pop('_id', [])
        
        if not id_list:
            return utils.build_ret(ErrorMsg.Success, {'_id': []})

        # 兼容老的 _id 删除以及新的 fnv_hash 删除
        object_ids = []
        fnv_hashes = []
        for _id in id_list:
            if len(str(_id)) == 24:  # ObjectId 长度通常为 24 的 hex
                try:
                    object_ids.append(ObjectId(_id))
                except Exception:
                    fnv_hashes.append(_id)
            else:
                fnv_hashes.append(_id)
        
        or_conds = []
        if object_ids:
            or_conds.append({'_id': {'$in': object_ids}})
        if fnv_hashes:
            or_conds.append({'fnv_hash': {'$in': fnv_hashes}})
            
        if or_conds:
            utils.conn_db('asset_wih').delete_many({'$or': or_conds})

        return utils.build_ret(ErrorMsg.Success, {'_id': id_list})

