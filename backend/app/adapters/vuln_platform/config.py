# backend/app/adapters/vuln_platform/config.py
"""漏洞平台配置（Cookie 直接字符串配置）"""

from app.config import Config


# ═══════════════════════════════════════════════════════════
# 平台配置
# ═══════════════════════════════════════════════════════════

PLATFORM_CONFIG = {
    "butian": {
        "name": "补天平台", "enabled": True,
        "base_url": "https://www.butian.net",
        "login_url": "https://www.butian.net/User/login",
        "test_url": "https://www.butian.net/Rank/company",
        "rate_limit": "6/m", "default_delay": 1.0,
        "user_agent": "ARL-Next-Bot/1.0", "cookie_ttl_hours": 12,
        "max_retries": 3, "priority": 8, "requires_login": True,
        # ★ Cookie 直接字符串配置
        "cookie": "PHPSESSID=fbqvfkr0on38ks9msa07f6fja1; "
                  "__btu__=a2feef5d1c3c71bd3da0a08f91801a0913bac099; "
                  "__btc__=652f3272c68f2d04227f1a53dbebbd9988299f7f; "
                  "__btuc__=86dbfb67288e117f25553345c50c514ef84c4a13",
    },
    "vulbox": {
        "name": "漏洞盒子", "enabled": True,
        "base_url": "https://www.vulbox.com",
        "login_url": "https://www.vulbox.com/login",
        "test_url": "https://www.vulbox.com/project",
        "rate_limit": "12/m", "default_delay": 1.0,
        "user_agent": "ARL-Next-Bot/1.0", "cookie_ttl_hours": 24,
        "max_retries": 3, "priority": 7, "requires_login": True,
        "cookie": "",
    },
    "cnvd": {
        "name": "CNVD众测", "enabled": True,
        "base_url": "https://zc.cnvd.org.cn",
        "test_url": "https://zc.cnvd.org.cn/news/list",
        "rate_limit": "4/m", "default_delay": 1.0,
        "user_agent": "ARL-Next-Bot/1.0", "cookie_ttl_hours": 8,
        "max_retries": 2, "priority": 6, "requires_login": False,
        # 无需 Cookie
    },
    "edusrc": {
        "name": "EduSRC", "enabled": True,
        "base_url": "https://src.sjtu.edu.cn",
        "test_url": "https://src.sjtu.edu.cn/list/",
        "rate_limit": "6/m", "default_delay": 1.0,
        "user_agent": "ARL-Next-Bot/1.0", "cookie_ttl_hours": 12,
        "max_retries": 3, "priority": 6, "requires_login": True,
        "cookie": "",
    },
    "hackerone": {
        "name": "HackerOne", "enabled": False,
        "api_base": "https://api.hackerone.com/v1",
        "rate_limit": "30/m", "default_delay": 1.0,
        "user_agent": "ARL-Next-Bot/1.0", "cookie_ttl_hours": 720,
        "max_retries": 3, "priority": 5, "requires_login": False,
    },
    "generic": {
        "name": "通用导入", "enabled": True,
        "rate_limit": "60/m", "default_delay": 1.0,
        "priority": 5, "requires_login": False,
    },
}


# ═══════════════════════════════════════════════════════════
# Cookie 工具函数
# ═══════════════════════════════════════════════════════════

def get_cookie_string(platform_name):
    """
    获取平台 Cookie 字符串
    :return: str（浏览器复制的完整 cookie 字符串）或 ""
    """
    cfg = PLATFORM_CONFIG.get(platform_name, {})
    return (cfg.get("cookie") or "").strip()


def get_cookie_ttl(platform_name):
    """获取 Cookie 有效期（小时）"""
    cfg = PLATFORM_CONFIG.get(platform_name, {})
    return cfg.get("cookie_ttl_hours", 12)


# ═══════════════════════════════════════════════════════════
# 平台配置查询
# ═══════════════════════════════════════════════════════════

def get_platform_config(platform_name):
    """获取平台配置（合并动态覆盖值）"""
    if platform_name not in PLATFORM_CONFIG:
        raise ValueError("未知平台: {}".format(platform_name))

    config = dict(PLATFORM_CONFIG[platform_name])

    if not Config.VULN_PLATFORM_ENABLED:
        config["enabled"] = False

    if platform_name == "hackerone":
        username = Config.HACKERONE_USERNAME
        token = Config.HACKERONE_TOKEN
        if username and token:
            config["enabled"] = True
            config["username"] = username
            config["api_token"] = token

    return config


def get_enabled_platforms():
    """获取所有已启用平台"""
    return [k for k in PLATFORM_CONFIG
            if get_platform_config(k).get("enabled")]