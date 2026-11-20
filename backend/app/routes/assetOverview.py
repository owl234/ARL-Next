from concurrent.futures import as_completed
from flask_restx import Namespace, fields
from app.utils import get_logger, auth, conn_db as conn
from app.services.asset_cascade_service import get_shared_executor
from . import ARLResource, get_arl_parser

ns = Namespace('asset_overview', description="资产维度总览计数")

logger = get_logger()

# 资产维度 → 集合映射（底层共 13 个资产集合）。
# 供前端「资产搜索」与「资产组详情」12 个维度页签渲染数量徽标，其中 service 与 npoc_service 合并归入「服务」页签。
OVERVIEW_COLLECTIONS = [
    ("site", "site"),
    ("domain", "domain"),
    ("ip", "ip"),
    ("cert", "cert"),
    ("service", "service"),
    ("fileleak", "fileleak"),
    ("url", "url"),
    ("vuln", "vuln"),
    ("npoc_service", "npoc_service"),
    ("cip", "cip"),
    ("stat_finger", "stat_finger"),
    ("nuclei_result", "nuclei_result"),
    ("wih", "wih"),
]

overview_count_fields = {
    "scope_id": fields.String(required=False, description="可选资产组 ID；传入时统计该资产组 13 张 asset_* 表计数"),
}


def _count_collection(name, scope_id=None):
    """
    统计单个资产集合的总量。

    各集合的「总量」口径与其列表接口保持一致，避免徽标数字与点进去的结果数不符：
      - 全局模式（无 scope_id）：
        - cip：列表页累计的是去重后的 C 段数，故此处按 cidr_ip 去重计数；
        - stat_finger：列表页按指纹名分组展示，故此处统计去重后的指纹名数量；
        - 其余集合：直接统计文档数。
      - 资产组模式（含 scope_id）：
        - asset_stat_finger：按 scope_id 匹配后按指纹名分组去重计数；
        - 其余 12 张 asset_* 集合：按 scope_id 精确 count_documents。
    """
    try:
        if scope_id:
            col = conn(f"asset_{name}")
            if name == "stat_finger":
                pipeline = [
                    {"$match": {"scope_id": scope_id}},
                    {"$group": {"_id": "$name"}},
                ]
                return len(list(col.aggregate(pipeline)))
            return col.count_documents({"scope_id": scope_id})

        col = conn(name)
        if name == "cip":
            return len(col.distinct("cidr_ip"))
        if name == "stat_finger":
            pipeline = [{"$group": {"_id": "$name"}}]
            return len(list(col.aggregate(pipeline)))
        if name == "service":
            pipeline = [
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
            agg_res = list(col.aggregate(pipeline))
            return agg_res[0]["total"] if agg_res else 0
        return col.estimated_document_count()
    except Exception as e:
        logger.error(f"Failed to count collection {name} (scope_id={scope_id}): {e}")
        return None


@ns.route('/count')
class AssetOverviewCount(ARLResource):
    parser = get_arl_parser(overview_count_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产维度总览计数

        一次性并发返回 13 个资产集合的计数（支持可选 scope_id 参数）：
        - 无 scope_id：供「资产搜索」全局页渲染页签数量徽标；
        - 传 scope_id：供「资产组详情」首屏单次拉取全维度数量徽标；
        计数失败的维度以 null 返回，前端应视为「未知」而非 0。
        """
        args = self.parser.parse_args()
        scope_id = (args.get("scope_id") or "").strip() or None

        counts = {}
        executor = get_shared_executor()
        future_map = {
            executor.submit(_count_collection, collection, scope_id): key
            for key, collection in OVERVIEW_COLLECTIONS
        }
        for fut in as_completed(future_map):
            key = future_map[fut]
            try:
                counts[key] = fut.result()
            except Exception as e:
                logger.error(f"Concurrent count failed for {key} (scope_id={scope_id}): {e}")
                counts[key] = None

        return {
            "code": 200,
            "message": "success",
            "counts": counts
        }
