import re
from flask_restx import fields, Namespace
from app.utils import get_logger, auth, conn_db as conn
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg
from app import utils
from app.services.service_fusion import (
    build_service_endpoint_doc,
    choose_service_name,
    format_service_endpoint_for_return,
    merge_sources,
)

ns = Namespace('service', description="系统服务信息")

logger = get_logger()

base_search_fields = {
    'service_name': fields.String(description="系统服务/协议名称"),
    'scheme': fields.String(description="协议名称(兼容别名)"),
    'ip': fields.String(required=False, description="IP/主机"),
    'host': fields.String(required=False, description="主机(兼容别名)"),
    'port_id': fields.String(description="端口号"),
    'port': fields.String(description="端口号(兼容别名)"),
    'product': fields.String(description="服务产品"),
    'version': fields.String(description="服务版本"),
    'target': fields.String(description="目标URI"),
    'sources': fields.String(description="识别来源 (nmap | npoc)"),
    'source': fields.String(description="识别来源(兼容别名)"),
    'service_info.ip': fields.String(required=False, description="IP(兼容字段)"),
    'service_info.port_id': fields.String(description="端口号(兼容字段)"),
    'service_info.version': fields.String(description="系统服务版本(兼容字段)"),
    'service_info.product': fields.String(description="产品(兼容字段)"),
    "task_id": fields.String(description="任务ID"),
}

base_search_fields.update(base_query_fields)


class ServiceResource(ARLResource):
    query_field_map = {
        **ARLResource.query_field_map,
        "service_info.ip": "ip",
        "service_info.port_id": "port_id",
        "service_info.product": "product",
        "service_info.version": "version",
        "host": "ip",
        "port": "port_id",
        "scheme": "service_name",
        "source": "sources",
    }

    def build_db_query(self, args):
        raw_port = None
        if isinstance(args, dict):
            for pk in ("port_id", "port", "service_info.port_id", "port_id__eq", "port__eq", "service_info.port_id__eq"):
                val = args.get(pk)
                if val is not None and str(val).strip() != "":
                    raw_port = str(val).strip()
                    break

        query = super().build_db_query(args)

        if raw_port is not None:
            if raw_port.isdigit():
                query["port_id"] = int(raw_port)
            else:
                query["port_id"] = -1

        if "sources" in query and isinstance(query["sources"], str):
            src_val = query["sources"].strip().lower()
            if src_val == "python":
                src_val = "npoc"
            query["sources"] = src_val

        return query

    def build_return_items(self, data):
        normalized = [format_service_endpoint_for_return(item) for item in data]
        return super().build_return_items(normalized)

    def build_data(self, args=None, collection='service'):
        has_custom_order = bool(args and args.get('order'))
        default_field = self.get_default_field(args)
        page = default_field.get("page", 1)
        size = default_field.get("size", 10)
        orderby_list = default_field.get('order', [("_id", -1)])

        query = self.build_db_query(args)

        # 全局「资产搜索」模式（无 task_id 且查询无前缀 service 表）：按 (ip, port_id) 跨任务去重归并
        if collection == 'service' and "task_id" not in query:
            pipeline = [
                {"$match": query},
                {"$sort": {"_id": -1}},
                {
                    "$group": {
                        "_id": {
                            "ip": {"$ifNull": ["$ip", "$_id"]},
                            "port_id": {"$ifNull": ["$port_id", 0]},
                        },
                        "doc_id": {"$first": "$_id"},
                        "ip": {"$first": "$ip"},
                        "port_id": {"$first": "$port_id"},
                        "service_names": {"$push": "$service_name"},
                        "products": {"$push": "$product"},
                        "versions": {"$push": "$version"},
                        "targets": {"$push": "$target"},
                        "sources_all": {"$push": "$sources"},
                        "service_info": {"$first": "$service_info"},
                        "save_date": {"$max": "$save_date"},
                        "update_date": {"$max": "$update_date"},
                        "task_id": {"$first": "$task_id"},
                    }
                },
            ]

            if not has_custom_order:
                pipeline.append({"$sort": {"doc_id": -1}})
            else:
                sort_dict = {}
                for field, direction in orderby_list:
                    sort_key = "doc_id" if field == "_id" else field
                    sort_dict[sort_key] = direction
                pipeline.append({"$sort": sort_dict})

            pipeline.append({"$skip": size * (page - 1)})
            pipeline.append({"$limit": size})

            raw_grouped = list(conn(collection).aggregate(pipeline))
            merged_items = []
            for grp in raw_grouped:
                ip_val = grp.get("ip")
                port_val = grp.get("port_id")
                if not ip_val or port_val is None:
                    # 兼容未迁移的旧版嵌套记录
                    fallback_doc = {
                        "_id": grp.get("doc_id"),
                        "task_id": grp.get("task_id"),
                        "service_name": (grp.get("service_names") or [""])[0],
                        "service_info": grp.get("service_info") or [],
                        "save_date": grp.get("save_date"),
                    }
                    merged_items.append(fallback_doc)
                    continue

                best_svc = ""
                for sn in (grp.get("service_names") or []):
                    best_svc = choose_service_name(best_svc, sn, prefer_new=False)
                best_prod = next((str(p).strip() for p in (grp.get("products") or []) if p and str(p).strip()), "")
                best_ver = next((str(v).strip() for v in (grp.get("versions") or []) if v and str(v).strip()), "")
                best_target = next((str(t).strip() for t in (grp.get("targets") or []) if t and str(t).strip()), "")
                merged_src = merge_sources(*(grp.get("sources_all") or []))

                ep_doc = build_service_endpoint_doc(
                    owner_field="task_id",
                    owner_id=grp.get("task_id"),
                    ip=ip_val,
                    port_id=port_val,
                    service_name=best_svc,
                    product=best_prod,
                    version=best_ver,
                    target=best_target,
                    sources=merged_src,
                    save_date=grp.get("save_date"),
                    update_date=grp.get("update_date") or grp.get("save_date"),
                    extra_fields={"_id": grp.get("doc_id")},
                )
                merged_items.append(ep_doc)

            count_pipeline = [
                {"$match": query},
                {
                    "$group": {
                        "_id": {
                            "ip": {"$ifNull": ["$ip", "$_id"]},
                            "port_id": {"$ifNull": ["$port_id", 0]},
                        }
                    }
                },
                {"$group": {"_id": None, "total": {"$sum": 1}}},
            ]
            agg_cnt = list(conn(collection).aggregate(count_pipeline))
            count = agg_cnt[0]["total"] if agg_cnt else 0
            items = self.build_return_items(merged_items)
        else:
            if collection and collection.startswith("asset_") and "task_id" in query:
                task_id = query["task_id"]
                if isinstance(task_id, str) and len(task_id) == 24:
                    from app.utils.monitor_diff import _get_task_scope_id
                    if _get_task_scope_id(task_id):
                        query["change_status"] = {"$in": ["new", "update"]}

            result = conn(collection).find(query).sort(orderby_list).skip(size * (page - 1)).limit(size)
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
            if isinstance(raw_value, dict) and "$not" in raw_value:
                if isinstance(raw_value["$not"], type(re.compile(""))):
                    raw_value["$not"] = raw_value["$not"].pattern

        return {
            "page": page,
            "size": size,
            "total": count,
            "items": items,
            "query": query,
            "code": 200,
        }


@ns.route('/')
class ARLService(ServiceResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        服务信息查询（融合 Nmap 与 Python 插件识别结果）
        """
        args = self.parser.parse_args()
        return self.build_data(args=args, collection='service')


@ns.route('/export/')
class ARLServiceExport(ServiceResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        服务信息导出
        """
        args = self.parser.parse_args()
        return self.send_export_file(args=args, _type="service")


delete_service_fields = ns.model('deleteService', {
    '_id': fields.List(fields.String(required=True, description="数据_id")),
    'task_id': fields.String(required=False, description="可选任务 ID"),
    'source_type': fields.String(required=False, description="可选删除作用域：task | global")
})


@ns.route('/delete/')
class DeleteARLService(ARLResource):
    @auth
    @ns.expect(delete_service_fields)
    def post(self):
        """
        删除系统服务信息（按端点级精确剥离端口）
        """
        args = self.parse_args(delete_service_fields)
        from app.services.asset_cascade_service import handle_dimension_delete
        return handle_dimension_delete(
            "service", False, args,
            build_ret_fn=utils.build_ret, success_msg=ErrorMsg.Success, db_getter=utils.conn_db,
        )
