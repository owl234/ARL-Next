from bson import ObjectId
from flask_restx import fields, Namespace
import re
from app.utils import get_logger, auth, conn_db as conn
from app import utils
from app.modules import ErrorMsg
from . import base_query_fields, ARLResource, get_arl_parser

ns = Namespace('cip', description="C段 ip 统计信息")

logger = get_logger()

base_search_fields = {
    'cidr_ip': fields.String(required=False, description="C段"),
    "task_id": fields.String(description="任务 ID"),
    "ip_count": fields.Integer(description="IP 个数"),
    "domain_count": fields.Integer(description="解析到该 C 段域名个数")
}

base_search_fields.update(base_query_fields)


class CIPResource(ARLResource):
    def build_data(self, args=None, collection='cip'):
        """
        覆盖 ARLResource.build_data，默认按 IP数 + 域名数降序排列
        针对全局查询去重：如果没有指定 task_id，自动使用 $group + $setUnion 归并数据
        """
        # 判断前端是否显式传递了 order
        has_custom_order = False
        if args and args.get('order'):
            has_custom_order = True

        default_field = self.get_default_field(args)
        page = default_field.get("page", 1)
        size = default_field.get("size", 10)
        orderby_list = default_field.get('order', [("_id", -1)])

        query = self.build_db_query(args)

        pipeline = [{"$match": query}]

        if "task_id" not in query:
            pipeline.extend([
                {
                    "$group": {
                        "_id": "$cidr_ip",
                        "cidr_ip": {"$first": "$cidr_ip"},
                        "ip_list_all": {"$push": {"$ifNull": ["$ip_list", []]}},
                        "domain_list_all": {"$push": {"$ifNull": ["$domain_list", []]}},
                        "save_date": {"$max": "$save_date"},
                        "task_id": {"$first": "$task_id"}
                    }
                },
                {
                    "$addFields": {
                        "ip_list": {
                            "$reduce": {
                                "input": "$ip_list_all",
                                "initialValue": [],
                                "in": {"$setUnion": ["$$value", "$$this"]}
                            }
                        },
                        "domain_list": {
                            "$reduce": {
                                "input": "$domain_list_all",
                                "initialValue": [],
                                "in": {"$setUnion": ["$$value", "$$this"]}
                            }
                        }
                    }
                },
                {
                    "$addFields": {
                        "ip_count": {"$size": "$ip_list"},
                        "domain_count": {"$size": "$domain_list"}
                    }
                },
                {
                    "$project": {
                        "ip_list_all": 0,
                        "domain_list_all": 0
                    }
                }
            ])

        pipeline.append({
            "$addFields": {
                "ip_domain_count": {
                    "$add": [
                        {"$ifNull": ["$ip_count", 0]},
                        {"$ifNull": ["$domain_count", 0]}
                    ]
                }
            }
        })

        if not has_custom_order:
            pipeline.append({"$sort": {"ip_domain_count": -1, "cidr_ip": 1}})
        else:
            sort_dict = {}
            for field, direction in orderby_list:
                sort_dict[field] = direction
            pipeline.append({"$sort": sort_dict})

        pipeline.append({"$skip": size * (page - 1)})
        pipeline.append({"$limit": size})

        result = list(conn(collection).aggregate(pipeline))

        if "task_id" not in query:
            # 全局搜索：实际总数为去重后的C段数
            count = len(conn(collection).distinct("cidr_ip", query))
        else:
            if not query:
                count = conn(collection).estimated_document_count()
            else:
                count = conn(collection).count_documents(query)

        items = self.build_return_items(result)

        special_keys = ["_id", "save_date", "update_date", "create_time"]
        for key in query:
            if key in special_keys:
                query[key] = str(query[key])
            raw_value = query[key]
            if isinstance(raw_value, dict):
                if "$not" in raw_value:
                    if isinstance(raw_value["$not"], type(re.compile(""))):
                        raw_value["$not"] = raw_value["$not"].pattern

        data = {
            "page": page,
            "size": size,
            "total": count,
            "items": items,
            "query": query,
            "code": 200
        }
        return data


@ns.route('/')
class ARLCIPList(CIPResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        C 段统计信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='cip')

        return data


@ns.route('/export/')
class ARLCIPExport(CIPResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        C 段 IP 导出
        """
        args = self.parser.parse_args()
        response = self.send_export_file(args=args, _type="cip")

        return response


delete_result_fields = ns.model('deleteCipResult', {
    '_id': fields.List(fields.String, required=True, description="待删除的记录 ID")
})


@ns.route('/delete/')
class DeleteARLCIP(ARLResource):
    @auth
    @ns.expect(delete_result_fields, validate=True)
    def post(self):
        """删除任务 C 段结果。"""
        args = self.parse_args(delete_result_fields)
        id_list = args.get('_id') or []
        # 先校验整批，避免无效 ID 导致前面的记录已被删除。
        if not id_list or any(not ObjectId.is_valid(value) for value in id_list):
            return utils.build_ret(
                {"code": 999, "message": "请提供有效的记录 ID 列表"}, {'_id': id_list}
            )
        result = utils.conn_db('cip').delete_many({'_id': {'$in': [ObjectId(value) for value in id_list]}})
        return utils.build_ret(ErrorMsg.Success, {'_id': id_list, 'deleted_count': result.deleted_count})
