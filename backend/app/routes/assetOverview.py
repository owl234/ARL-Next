from flask_restx import Namespace
from app.utils import get_logger, auth, conn_db as conn
from . import ARLResource

ns = Namespace('asset_overview', description="资产维度总览计数")

logger = get_logger()

# 资产维度 → 集合映射（底层共 13 个资产集合）。
# 供前端「资产搜索」页 12 个维度页签渲染数量徽标，其中 service 与 npoc_service 合并归入「服务」页签。
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


def _count_collection(name):
    """
    统计单个资产集合的总量。

    各集合的「总量」口径与其列表接口保持一致，避免徽标数字与点进去的结果数不符：
      - cip：列表页累计的是去重后的 C 段数，故此处按 cidr_ip 去重计数；
      - stat_finger：列表页按指纹名分组展示，故此处统计去重后的指纹名数量；
      - 其余集合：直接统计文档数。
    """
    try:
        col = conn(name)
        if name == "cip":
            return len(col.distinct("cidr_ip"))
        if name == "stat_finger":
            pipeline = [{"$group": {"_id": "$name"}}]
            return len(list(col.aggregate(pipeline)))
        return col.estimated_document_count()
    except Exception as e:
        logger.error(f"Failed to count collection {name}: {e}")
        return None


@ns.route('/count')
class AssetOverviewCount(ARLResource):
    @auth
    def get(self):
        """
        资产维度总览计数

        一次性返回各资产维度的总量，供前端渲染页签数量徽标使用，
        避免前端为每个维度单独发起一次计数请求。

        返回结构中 counts 包含底层 13 个资产集合的计数（前端「资产搜索」页共 12 个维度页签，
        其中 service 与 npoc_service 合并归入「服务」页签）；
        计数失败的维度以 null 返回，前端应视为「未知」而非 0。
        """
        counts = {}
        for key, collection in OVERVIEW_COLLECTIONS:
            counts[key] = _count_collection(collection)

        return {
            "code": 200,
            "message": "success",
            "counts": counts
        }
