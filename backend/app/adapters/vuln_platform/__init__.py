# backend/app/adapters/vuln_platform/__init__.py
"""漏洞平台适配层 — 工厂函数与注册表"""

from app import utils
from .config import (
    PLATFORM_CONFIG, get_platform_config, get_enabled_platforms,
)

logger = utils.get_logger()

_ADAPTER_REGISTRY = {}


def register_adapter(platform_name, adapter_class):
    _ADAPTER_REGISTRY[platform_name] = adapter_class


def get_adapter(platform_name, db=None):
    if platform_name not in _ADAPTER_REGISTRY:
        _lazy_import_adapters()
    adapter_class = _ADAPTER_REGISTRY.get(platform_name)
    if not adapter_class:
        raise ValueError("未找到平台适配器: {}".format(platform_name))
    return adapter_class(platform_name, db=db)


def _lazy_import_adapters():
    _import_pairs = [
        ("butian", ".butian", "BuTianAdapter"),
        ("vulbox", ".vulbox", "VulboxAdapter"),
        ("cnvd", ".cnvd", "CnvdAdapter"),
        ("edusrc", ".edusrc", "EduSrcAdapter"),
        ("hackerone", ".hackerone", "HackerOneAdapter"),
        ("generic", ".generic", "GenericAdapter"),
    ]
    for name, module_path, class_name in _import_pairs:
        if name in _ADAPTER_REGISTRY:
            continue
        try:
            module = __import__(
                "app.adapters.vuln_platform{}".format(module_path),
                fromlist=[class_name])
            adapter_class = getattr(module, class_name)
            register_adapter(name, adapter_class)
        except ImportError as e:
            logger.warning("适配器 {} 导入失败: {}".format(name, e))


def get_all_adapters(db=None):
    _lazy_import_adapters()
    adapters = {}
    for name in get_enabled_platforms():
        try:
            adapters[name] = get_adapter(name, db=db)
        except ValueError as e:
            logger.warning("跳过未注册平台 {}: {}".format(name, e))
    return adapters


__all__ = [
    "register_adapter", "get_adapter", "get_all_adapters",
    "PLATFORM_CONFIG", "get_platform_config", "get_enabled_platforms",
]