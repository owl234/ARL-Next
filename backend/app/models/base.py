# ARL-Next/app/models/base.py
"""
数据模型基类
- 使用 Python 原生类型声明字段（str / int / datetime / ObjectId）
- 支持 typing 泛型（List[str] / Dict[str, Any] / Optional[str]）
- 统一通用字段（_id / created_at / updated_at）
- 提供序列化能力
- 不含数据库操作
"""

import json
from datetime import datetime
from typing import (
    Any, List, Dict, Optional, Union,
    get_origin, get_args,
)
from bson import ObjectId


# ═══════════════════════════════════════════════════════════
# 通用字段定义（使用 Python 原生类型）
# ═══════════════════════════════════════════════════════════

COMMON_FIELDS = {
    "_id": ObjectId,
}

TIMESTAMP_FIELDS = {
    "created_at": datetime,
    "updated_at": datetime,
}


# ═══════════════════════════════════════════════════════════
# 类型判断工具
# ═══════════════════════════════════════════════════════════

# 需要序列化为字符串的类型
STRINGIFY_TYPES = (ObjectId, datetime)


def _unwrap_optional(tp):
    """
    解包 Optional[T] / Union[T, None] / T | None
    返回内部的实际类型
    """
    origin = get_origin(tp)
    if origin is Union:  # Union[T, None] 或 Optional[T]
        args = [a for a in get_args(tp) if a is not type(None)]
        if len(args) == 1:
            return args[0]
        return args
    return tp


def needs_stringify(tp):
    """
    判断类型是否需要序列化为字符串
    - 直接是 ObjectId / datetime
    - 泛型内部含 ObjectId / datetime
    """
    # 解包 Optional
    tp = _unwrap_optional(tp)

    # 直接匹配
    if tp in STRINGIFY_TYPES:
        return True

    # 泛型（List[X] / Dict[K, V] / ...）
    origin = get_origin(tp)
    if origin is not None:
        for arg in get_args(tp):
            if needs_stringify(arg):
                return True

    return False


def type_to_name(tp):
    """
    把 Python 类型转为可读的名称
    用于日志、错误提示、未来映射到其他数据库
    """
    tp = _unwrap_optional(tp)
    origin = get_origin(tp)

    if origin is not None:
        # 泛型类型
        origin_name = getattr(origin, "__name__", str(origin))
        args = get_args(tp)
        args_str = ", ".join(type_to_name(a) for a in args)
        return "{}[{}]".format(origin_name, args_str)

    # 基础类型
    if hasattr(tp, "__name__"):
        return tp.__name__

    return str(tp)


# ═══════════════════════════════════════════════════════════
# BaseModel
# ═══════════════════════════════════════════════════════════

class BaseModel(object):
    """
    所有数据模型的基类

    子类只需定义：
      - COLLECTION: 集合名
      - FIELDS:     业务字段（使用 Python 原生类型）
      - INDEXES:    索引定义

    示例：
        class ProjectModel(BaseModel):
            COLLECTION = "vuln_platform_projects"
            FIELDS = {
                "fingerprint": str,
                "platform": str,
                "scope": List[str],
                "asset_count": int,
                "fetched_at": datetime,
            }
    """

    # ── 子类必须定义 ──────────────────────────────────
    COLLECTION = None
    FIELDS = {}
    INDEXES = []

    # ── 通用字段开关 ──────────────────────────────────
    ENABLE_CREATED_AT = True
    ENABLE_UPDATED_AT = True

    # ── 实例化 ────────────────────────────────────────
    def __init__(self, data=None):
        if data:
            for k, v in data.items():
                setattr(self, k, v)

    # ═══════════════════════════════════════════════════
    # Schema
    # ═══════════════════════════════════════════════════

    @classmethod
    def get_common_fields(cls):
        """通用字段（_id + 时间戳）"""
        fields = dict(COMMON_FIELDS)
        if cls.ENABLE_CREATED_AT:
            fields["created_at"] = datetime
        if cls.ENABLE_UPDATED_AT:
            fields["updated_at"] = datetime
        return fields

    @classmethod
    def get_schema(cls):
        """完整 schema = 通用字段 + 业务字段"""
        schema = cls.get_common_fields()
        schema.update(cls.FIELDS or {})
        return schema

    @classmethod
    def get_indexes(cls):
        return cls.INDEXES or []

    @classmethod
    def stringify_fields(cls):
        """
        需要序列化为字符串的字段
        自动从 schema 类型推导
        """
        return [
            k for k, tp in cls.get_schema().items()
            if needs_stringify(tp)
        ]

    @classmethod
    def default_order(cls):
        """默认排序"""
        if cls.ENABLE_CREATED_AT:
            return "-created_at"
        return "-_id"

    # ═══════════════════════════════════════════════════
    # 时间戳
    # ═══════════════════════════════════════════════════

    @staticmethod
    def now():
        """统一 UTC 时间入口"""
        return utcnow()

    @classmethod
    def touch_create(cls, doc):
        now = cls.now()
        if cls.ENABLE_CREATED_AT and "created_at" not in doc:
            doc["created_at"] = now
        if cls.ENABLE_UPDATED_AT and "updated_at" not in doc:
            doc["updated_at"] = now
        return doc

    @classmethod
    def touch_update(cls, update_fields):
        if cls.ENABLE_UPDATED_AT:
            update_fields["updated_at"] = cls.now()
        return update_fields

    # ═══════════════════════════════════════════════════
    # 序列化
    # ═══════════════════════════════════════════════════

    def __str__(self):
        return self.dump_json()

    def __repr__(self):
        return self.dump_json()

    def dump_json(self, flag=True):
        item = self._dump_json()
        if flag:
            return json.dumps(item, ensure_ascii=False, default=str)
        return item

    def _dump_json(self):
        result = {}
        stringify = self.stringify_fields()
        for k in self.get_schema():
            v = getattr(self, k, None)
            if v is None:
                continue
            if k in stringify:
                # ObjectId / datetime 转字符串
                if isinstance(v, list):
                    result[k] = [str(x) for x in v]
                elif isinstance(v, dict):
                    result[k] = {
                        kk: str(vv) if isinstance(
                            vv, STRINGIFY_TYPES) else vv
                        for kk, vv in v.items()
                    }
                else:
                    result[k] = str(v)
            else:
                result[k] = v
        return result

    def to_dict(self):
        return self._dump_json()

    # ═══════════════════════════════════════════════════
    # 校验
    # ═══════════════════════════════════════════════════

    @classmethod
    def validate(cls):
        if not cls.COLLECTION:
            raise ValueError(
                "{} 未定义 COLLECTION".format(cls.__name__))
        return True

    # ═══════════════════════════════════════════════════
    # 调试辅助
    # ═══════════════════════════════════════════════════

    @classmethod
    def describe_schema(cls):
        """
        打印可读的 schema
        用于调试或生成文档
        """
        lines = ["=== {} ({}) ===".format(
            cls.__name__, cls.COLLECTION)]
        for name, tp in cls.get_schema().items():
            lines.append("  {:<24} {}".format(
                name, type_to_name(tp)))
        return "\n".join(lines)