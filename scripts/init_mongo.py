# ARL-Next/scripts/init_mongo.py
"""
MongoDB 初始化脚本
- 只创建漏洞平台聚合模块所需的 5 个新集合
- 只创建必要的索引（主键 + 唯一索引 + 高频查询索引）
- 不触碰 ARL-Next 现有 40 个集合
用法：
    cd ARL-Next && python scripts/init_mongo.py
"""

import os
import sys

BACKEND_DIR = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from pymongo import IndexModel, ASCENDING

from app import utils
from app.utils.conn import conn_db

logger = utils.get_logger()


# ═══════════════════════════════════════════════════════════
# 新增集合（统一前缀 vuln_platform_）
# ═══════════════════════════════════════════════════════════

NEW_COLLECTIONS = [
    "vuln_platform_projects",
    "vuln_platform_targets",
    "vuln_platform_scan_schedules",
    "vuln_platform_submit_records",
    "vuln_platform_vulns",
]


# ═══════════════════════════════════════════════════════════
# 索引定义（精简版：只保留必要索引）
# ═══════════════════════════════════════════════════════════

# 设计原则：
#   1. 时间字段不建索引 —— ObjectId 含时间戳，按 _id 排序即可
#   2. 装饰性字段不建索引 —— 只服务于展示，无高频查询
#   3. 组合索引覆盖高频查询 —— 遵循最左前缀原则
#   4. 唯一索引防重复 —— 数据完整性的最后一道防线

INDEX_DEFS = {
    # ── 项目表 ────────────────────────────────────────
    # 查询场景：
    #   - 按 fingerprint 查单条（唯一键）
    #   - 按 platform + project_id 查重（唯一键）
    #   - 按 status 查活跃项目
    "vuln_platform_projects": [
        IndexModel(
            [("fingerprint", ASCENDING)],
            unique=True,
            name="idx_fp_unique",
        ),
        IndexModel(
            [("platform", ASCENDING), ("project_id", ASCENDING)],
            unique=True,
            name="idx_platform_project_unique",
        ),
        IndexModel(
            [("status", ASCENDING)],
            name="idx_status",
        ),
    ],

    # ── 目标表 ────────────────────────────────────────
    # 查询场景：
    #   - 按 fingerprint 查单条（唯一键）
    #   - 按 project_fingerprint 查项目下所有目标
    #   - 按 scanned 查待扫描目标
    "vuln_platform_targets": [
        IndexModel(
            [("fingerprint", ASCENDING)],
            unique=True,
            name="idx_fp_unique",
        ),
        IndexModel(
            [("project_fingerprint", ASCENDING)],
            name="idx_project_fp",
        ),
        IndexModel(
            [("scanned", ASCENDING)],
            name="idx_scanned",
        ),
    ],

    # ── 调度表 ────────────────────────────────────────
    # 查询场景：
    #   - 按 project_fingerprint + profile 查重（唯一键）
    #   - 按 enabled 查已启用的调度
    "vuln_platform_scan_schedules": [
        IndexModel(
            [("project_fingerprint", ASCENDING),
             ("profile", ASCENDING)],
            unique=True,
            name="idx_project_profile_unique",
        ),
        IndexModel(
            [("enabled", ASCENDING)],
            name="idx_enabled",
        ),
    ],

    # ── 提交记录表 ────────────────────────────────────
    # 查询场景：
    #   - 按 vuln_id + platform 查重（唯一键）
    #   - 按 project_fingerprint 查项目提交历史
    #   - 按 status 查成功/失败记录
    "vuln_platform_submit_records": [
        IndexModel(
            [("vuln_id", ASCENDING), ("platform", ASCENDING)],
            unique=True,
            name="idx_vuln_platform_unique",
        ),
        IndexModel(
            [("project_fingerprint", ASCENDING)],
            name="idx_project_fp",
        ),
        IndexModel(
            [("status", ASCENDING)],
            name="idx_status",
        ),
    ],

    # ── 漏洞表 ────────────────────────────────────────
    # 查询场景：
    #   - 按 template_id + target_url + project_fp 查重（唯一键）
    #   - 按 project_fingerprint 查项目下所有漏洞
    #   - 按 submit_status 查待提交漏洞
    "vuln_platform_vulns": [
        IndexModel(
            [("template_id", ASCENDING),
             ("target_url", ASCENDING),
             ("project_fingerprint", ASCENDING)],
            unique=True,
            name="idx_template_target_project_unique",
        ),
        IndexModel(
            [("project_fingerprint", ASCENDING)],
            name="idx_project_fp",
        ),
        IndexModel(
            [("submit_status", ASCENDING)],
            name="idx_submit_status",
        ),
    ],
}


# ═══════════════════════════════════════════════════════════
# 辅助函数
# ═══════════════════════════════════════════════════════════

def get_db():
    """通过任意集合获取 Database 对象"""
    return conn_db("vuln_platform_projects").database


def init_collections(db):
    """只创建新增集合，不触碰现有"""
    existing = set(db.list_collection_names())
    created = []
    skipped = []

    for name in NEW_COLLECTIONS:
        if name in existing:
            skipped.append(name)
            logger.info("⚠️  已存在（跳过）: {}".format(name))
            continue
        try:
            db.create_collection(name)
            created.append(name)
            logger.info("✅ 已创建: {}".format(name))
        except Exception as e:
            logger.warning("创建失败 {}: {}".format(name, e))

    logger.info("")
    logger.info("创建: {}, 已存在: {}".format(
        len(created), len(skipped)))
    return created, skipped


def init_indexes(db):
    """为新增集合创建索引"""
    total = 0
    for coll_name, indexes in INDEX_DEFS.items():
        if not indexes:
            logger.warning("跳过 {}：无索引定义".format(coll_name))
            continue
        try:
            db[coll_name].create_indexes(indexes)
            total += len(indexes)
            logger.info("✅ 索引就绪: {} ({} 个)".format(
                coll_name, len(indexes)))
        except Exception as e:
            logger.warning("索引异常 [{}]: {}".format(coll_name, e))
    logger.info("")
    logger.info("共创建 {} 个索引（不含 _id）".format(total))


def print_summary(db):
    """打印初始化后的全量状态"""
    logger.info("")
    logger.info("=" * 70)
    logger.info("MongoDB 集合总览")
    logger.info("=" * 70)

    all_collections = sorted(db.list_collection_names())
    new_colls = [c for c in all_collections
                 if c in NEW_COLLECTIONS]
    existing_colls = [c for c in all_collections
                      if c not in NEW_COLLECTIONS]

    # 新增集合详情
    logger.info("")
    logger.info("【漏洞平台聚合（新增）{} 个】".format(len(new_colls)))
    logger.info("-" * 70)
    for name in new_colls:
        try:
            coll = db[name]
            doc_count = coll.count_documents({})
            indexes = list(coll.list_indexes())
            logger.info("")
            logger.info("  📋 {} (文档: {}, 索引: {})".format(
                name, doc_count, len(indexes)))
            for idx in indexes:
                idx_name = idx.get("name", "")
                idx_key = dict(idx.get("key", {}))
                unique_mark = " [unique]" \
                    if idx.get("unique") else ""
                logger.info("      - {}{}".format(
                    idx_name, unique_mark))
                logger.info("        {}".format(idx_key))
        except Exception as e:
            logger.info("  ❌ {} (不可访问: {})".format(name, e))

    # 原有集合列表
    logger.info("")
    logger.info("【ARL-Next 原有 {} 个（未修改）】".format(
        len(existing_colls)))
    logger.info("-" * 70)
    # 分行展示
    per_line = 4
    for i in range(0, len(existing_colls), per_line):
        chunk = existing_colls[i:i + per_line]
        logger.info("  " + "  ".join(
            "{:<22}".format(c) for c in chunk))

    logger.info("")
    logger.info("=" * 70)
    logger.info("总计: {} 个集合".format(len(all_collections)))
    logger.info("=" * 70)


def print_index_statistics(db):
    """打印索引统计（用于对比优化效果）"""
    logger.info("")
    logger.info("索引统计")
    logger.info("-" * 70)

    for name in NEW_COLLECTIONS:
        try:
            coll = db[name]
            indexes = list(coll.list_indexes())
            # 排除 _id 索引
            business_indexes = [
                idx for idx in indexes
                if idx.get("name") != "_id_"
            ]
            unique_count = sum(
                1 for idx in business_indexes
                if idx.get("unique"))
            normal_count = len(business_indexes) - unique_count

            logger.info(
                "  {:<35} 业务索引: {} "
                "(唯一: {}, 普通: {})".format(
                    name, len(business_indexes),
                    unique_count, normal_count))
        except Exception:
            pass


# ═══════════════════════════════════════════════════════════
# 主入口
# ═══════════════════════════════════════════════════════════

def main():
    logger.info("=" * 70)
    logger.info("ARL-Next MongoDB 初始化")
    logger.info("前缀: vuln_platform_")
    logger.info("原则: 只创建必要索引（主键 + 唯一 + 高频查询）")
    logger.info("=" * 70)

    # 1. 连接数据库
    try:
        db = get_db()
        logger.info("已连接数据库: {}".format(db.name))
    except Exception as e:
        logger.error("无法连接 MongoDB: {}".format(e))
        logger.error("请检查 config.yaml 中的 MONGO 配置")
        sys.exit(1)

    # 2. 创建集合
    init_collections(db)

    # 3. 创建索引
    init_indexes(db)

    # 4. 打印集合详情
    print_summary(db)

    # 5. 打印索引统计
    print_index_statistics(db)

    logger.info("")
    logger.info("✅ 初始化完成，现有集合未被修改")


if __name__ == "__main__":
    main()