from bson import ObjectId
import re
from flask_restx import fields, Namespace
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
    "update_date__dgt": fields.String(description="更新时间大于"),
    "update_date__dlt": fields.String(description="更新时间小于"),
    "insert_time__dgt": fields.String(description="插入时间大于"),
    "insert_time__dlt": fields.String(description="插入时间小于"),
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
    '_id': fields.List(fields.String(required=False, description="数据 _id 或 C 段 CIDR")),
    'cidr_ip': fields.List(fields.String(required=False, description="可选 C 段 CIDR 列表")),
    'scope_id': fields.String(required=False, description="可选资产组 ID（按 CIDR 删除时必填）")
})


@ns.route('/delete/')
class DeleteARLAssetCip(ARLResource):
    @auth
    @ns.expect(delete_cip_fields)
    def post(self):
        """
        删除资产组C段信息（展开下属 IP 执行完整级联清理）
        """
        args = self.parse_args(delete_cip_fields)
        from app.services.asset_cascade_service import handle_dimension_delete
        return handle_dimension_delete(
            "cip", True, args,
            build_ret_fn=utils.build_ret, success_msg=ErrorMsg.Success, db_getter=utils.conn_db,
        )

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

        ip_list = []
        query = {}
        ip_collection_name = 'ip'
        collection_type = "unknown"
        
        # 1. 尝试判定是否为单个任务或资产组的合规 ObjectId
        if ObjectId.is_valid(cidr_id):
            collection_type = "asset"
            cip_doc = utils.conn_db('asset_cip').find_one({'_id': ObjectId(cidr_id)})
            
            if not cip_doc:
                cip_doc = utils.conn_db('cip').find_one({'_id': ObjectId(cidr_id)})
                collection_type = "task"
                
            if not cip_doc:
                return {"code": 200, "message": f"C段未找到(cidr_id={cidr_id})", "data": {"items": []}}
                
            ip_list = cip_doc.get("ip_list", [])
            scope_id = cip_doc.get("scope_id", "")
            task_id = cip_doc.get("task_id", "")
            
            ip_collection_name = 'asset_ip' if collection_type == "asset" else 'ip'
            query = {"ip": {"$in": ip_list}}
            if collection_type == "asset" and scope_id:
                query["scope_id"] = scope_id
            elif collection_type == "task" and task_id:
                query["task_id"] = task_id
        else:
            # 2. 全局搜索传过来的是真实 C段字符串 (如: 192.168.1.0/24)
            collection_type = "global"
            cip_docs = list(utils.conn_db('cip').find({'cidr_ip': cidr_id}))
            if not cip_docs:
                return {"code": 200, "message": f"全局C段未找到(cidr_ip={cidr_id})", "data": {"items": []}}
            
            merged_ip_set = set()
            for doc in cip_docs:
                merged_ip_set.update(doc.get("ip_list", []))
            
            ip_list = list(merged_ip_set)
            ip_collection_name = 'ip'
            query = {"ip": {"$in": ip_list}}
            
        # 3. 从对应的表里查出这些 IP 关联的域名
        ip_docs = list(utils.conn_db(ip_collection_name).find(query, {"ip": 1, "domain": 1, "_id": 0}))
        
        # 4. 组装结果并深度去重
        result_items = []
        debug_msg = "success"
        if len(ip_docs) == 0:
            debug_msg = f"未找到IP记录(类型:{collection_type})。ip数={len(ip_list)}, 表={ip_collection_name}, 条件={query}"
            
        ip_domain_map = {}
        for doc in ip_docs:
            ip = doc.get("ip")
            domains = doc.get("domain", [])
            if not isinstance(domains, list):
                domains = []
            if ip not in ip_domain_map:
                ip_domain_map[ip] = set()
            ip_domain_map[ip].update(domains)
            
        for ip, domains_set in ip_domain_map.items():
            result_items.append({
                "ip": ip,
                "domains": list(domains_set)
            })
            
        return {"code": 200, "message": debug_msg, "data": {"items": result_items}}
