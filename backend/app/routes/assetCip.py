from bson import ObjectId
import re
from flask_restx import Resource, reqparse, fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg
from app import utils

ns = Namespace('asset_cip', description="资产组C段信息")

logger = get_logger()

base_search_fields = {
    'cidr_ip': fields.String(required=False, description="C段"),
    "ip_count": fields.Integer(description="IP 个数"),
    "domain_count": fields.Integer(description="解析到该 C 段域名个数"),
    "scope_id": fields.String(description="资产范围ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLAssetCip(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组C段信息查询
        """
        # args 需要转为普通的 dict，以便 get_default_field 中可以使用 pop()
        args_dict = dict(self.parser.parse_args())
        
        # 1. 提取基础参数 (会把 page, size, order pop 出来)
        default_field = self.get_default_field(args_dict)
        page = default_field.get("page", 1)
        size = default_field.get("size", 10)
        
        # 2. 翻译查询条件
        query = self.build_db_query(args_dict)

        # 3. 聚合查询，强制按 (ip_count + domain_count) 降序
        pipeline = [
            {"$match": query},
            {"$addFields": {
                "total_cnt": {
                    "$add": [
                        {"$ifNull": ["$ip_count", 0]},
                        {"$ifNull": ["$domain_count", 0]}
                    ]
                }
            }},
            {"$sort": {"total_cnt": -1, "_id": -1}},
            {"$skip": size * (page - 1)},
            {"$limit": size}
        ]
        
        result = list(utils.conn_db('asset_cip').aggregate(pipeline))
        
        # 4. 计算总数
        if not query:
            count = utils.conn_db('asset_cip').estimated_document_count()
        else:
            count = utils.conn_db('asset_cip').count_documents(query)

        # 5. 格式化数据
        items = self.build_return_items(result)
        
        # 6. 【扫尾工作】：把查询条件 query 里的特殊对象也变成普通字符串
        special_keys = ["_id", "save_date", "update_date", "create_time"]
        for key in query:
            if key in special_keys:
                query[key] = str(query[key])

            raw_value = query[key]
            if isinstance(raw_value, dict):
                if "$not" in raw_value:
                    if isinstance(raw_value["$not"], type(re.compile(""))):
                        raw_value["$not"] = raw_value["$not"].pattern

        return {
            "page": page,
            "size": size,
            "total": count,
            "items": items,
            "query": query,
            "code": 200
        }


@ns.route('/export/')
class ARLAssetCipExport(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组C段信息导出
        """
        args = self.parser.parse_args()
        response = self.send_export_file(args=args, _type="asset_cip")
        return response


delete_cip_fields = ns.model('deleteAssetCip',  {
    '_id': fields.List(fields.String(required=True, description="数据_id"))
})


@ns.route('/delete/')
class DeleteARLAssetCip(ARLResource):
    @auth
    @ns.expect(delete_cip_fields)
    def post(self):
        """
        删除资产组C段信息
        """
        args = self.parse_args(delete_cip_fields)
        id_list = args.pop('_id', "")

        for _id in id_list:
            query = {'_id': ObjectId(_id)}
            utils.conn_db('asset_cip').delete_one(query)

        return utils.build_ret(ErrorMsg.Success, {'_id': id_list})

# ==========================================
# 接口：查询某个 C段 的 IP-域名映射详情 (GET /ip_domain_detail/)
# ==========================================
ip_domain_fields = {
    'cidr_id': fields.String(required=True, description="C段 _id"),
}

@ns.route('/ip_domain_detail/')
class ARLAssetCipIPDomainDetail(ARLResource):
    parser = get_arl_parser(ip_domain_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        获取 C段 内 IP 和域名的对应关系
        """
        args = self.parser.parse_args()
        cidr_id = args.get("cidr_id")
        if not cidr_id:
            return utils.build_ret(ErrorMsg.ArgsError, {"error": "Missing cidr_id"})
            
        # 1. 优先尝试从 asset_cip 找 (资产组场景)
        collection_type = "asset"
        cip_doc = utils.conn_db('asset_cip').find_one({'_id': ObjectId(cidr_id)})
        
        # 2. 如果没找到，尝试从 cip 找 (任务详情场景)
        if not cip_doc:
            cip_doc = utils.conn_db('cip').find_one({'_id': ObjectId(cidr_id)})
            collection_type = "task"
            
        if not cip_doc:
            return {"code": 200, "message": f"C段未找到(cidr_id={cidr_id})", "data": {"items": []}}
            
        ip_list = cip_doc.get("ip_list", [])
        scope_id = cip_doc.get("scope_id", "")
        task_id = cip_doc.get("task_id", "")
        
        # 3. 确定该去哪个表查 IP
        # 如果是资产组场景，去 asset_ip 查；如果是任务场景，去 ip 查
        ip_collection_name = 'asset_ip' if collection_type == "asset" else 'ip'
        
        # 从对应的表里查出这些 IP 关联的域名
        query = {"ip": {"$in": ip_list}}
        if collection_type == "asset" and scope_id:
            query["scope_id"] = scope_id
        elif collection_type == "task" and task_id:
            query["task_id"] = task_id
            
        ip_docs = list(utils.conn_db(ip_collection_name).find(query, {"ip": 1, "domain": 1, "_id": 0}))
        
        # 整理成字典，方便前端展示
        result_items = []
        
        # 如果依然为空，把调试信息直接打在 message 里，方便查明真相
        debug_msg = "success"
        if len(ip_docs) == 0:
            debug_msg = f"未找到IP记录(类型:{collection_type})。ip数={len(ip_list)}, 表={ip_collection_name}, 条件={query}"
        for doc in ip_docs:
            result_items.append({
                "ip": doc.get("ip"),
                "domains": doc.get("domain", [])
            })
            
        return {"code": 200, "message": debug_msg, "data": {"items": result_items}}
