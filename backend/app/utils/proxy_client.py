# backend/app/utils/proxy_client.py
"""
外部代理池客户端
- 优先 Redis 直读（user_proxy Hash）
- Redis 不可用降级到 HTTP API
- 不区分协议（统一获取）
"""

import os
import time
import random
import json
from typing import Optional, List, Dict, Any

import requests

from app import utils
from app.utils.redis_client import redis_client

logger = utils.get_logger()


# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

PROXY_REDIS_KEY = os.environ.get("ARL_PROXY_REDIS_KEY", "user_proxy")
PROXY_POOL_API = os.environ.get("ARL_PROXY_POOL_API",
                                  "http://127.0.0.1:5010")
GET_RETRY = int(os.environ.get("ARL_PROXY_GET_RETRY", 3))
API_TIMEOUT = int(os.environ.get("ARL_PROXY_API_TIMEOUT", 5))
VALIDATE_URL = os.environ.get("ARL_PROXY_VALIDATE_URL",
                                "https://httpbin.org/ip")


# ═══════════════════════════════════════════════════════════
# HTTP 会话
# ═══════════════════════════════════════════════════════════

_session = requests.Session()
_session.headers.update({"User-Agent": "ARL-Next-ProxyClient/1.0"})


# ═══════════════════════════════════════════════════════════
# 工具函数
# ═══════════════════════════════════════════════════════════

def _api_get(path, params=None):
    url = "{}{}".format(PROXY_POOL_API, path)
    try:
        resp = _session.get(url, params=params, timeout=API_TIMEOUT)
        if resp.status_code != 200:
            return None
        return resp.json()
    except requests.exceptions.Timeout:
        logger.warning("[ProxyClient] API {} 超时".format(path))
        return None
    except requests.exceptions.ConnectionError:
        logger.warning("[ProxyClient] 无法连接代理池 {}".format(PROXY_POOL_API))
        return None
    except Exception as e:
        logger.error("[ProxyClient] API {} 调用失败: {}".format(path, e))
        return None


def _format_proxy(raw):
    if not raw:
        return None
    raw = raw.strip()
    if raw.startswith(("http://", "https://",
                        "socks4://", "socks5://")):
        return raw
    return "http://{}".format(raw)


def _strip_protocol(proxy):
    if not proxy:
        return ""
    for prefix in ("http://", "https://",
                    "socks4://", "socks5://"):
        if proxy.startswith(prefix):
            return proxy[len(prefix):]
    return proxy


def _check_proxy(field):
    """基于 Redis Value 判断代理可用性（统一，不区分协议）"""
    try:
        value = redis_client.hash_get(PROXY_REDIS_KEY, field)
        if not value:
            return False

        if isinstance(value, str):
            try:
                data = json.loads(value)
            except Exception:
                return True
        else:
            data = value

        if not isinstance(data, dict):
            return True

        # last_status 必须非 False
        if data.get("last_status") is False:
            return False

        # 失败次数过多
        fail_count = data.get("fail_count", 0)
        if isinstance(fail_count, int) and fail_count > 10:
            return False

        return True
    except Exception:
        return True


# ═══════════════════════════════════════════════════════════
# 核心接口
# ═══════════════════════════════════════════════════════════

def get_proxy(retry=GET_RETRY):
    """获取一个代理（统一，不区分协议）"""
    if redis_client.is_connected():
        proxy = _get_proxy_from_redis()
        if proxy:
            return proxy
    return _get_proxy_from_api(retry=retry)


def _get_proxy_from_redis():
    """从 Redis Hash 随机获取可用代理"""
    try:
        key = PROXY_REDIS_KEY

        fields = redis_client.hash_random(key, count=10)
        if fields:
            for f in fields:
                if f and _check_proxy(f):
                    proxy = _format_proxy(f)
                    if proxy:
                        return proxy

        all_fields = redis_client.hash_all(key)
        if all_fields:
            random.shuffle(all_fields)
            for f in all_fields[:20]:
                if _check_proxy(f):
                    return _format_proxy(f)
    except Exception as e:
        logger.warning("[ProxyClient] Redis 读取失败: {}".format(e))
    return None


def _get_proxy_from_api(retry=GET_RETRY):
    """从 HTTP API 获取代理"""
    for _ in range(retry):
        data = _api_get("/get/")
        if data and data.get("proxy"):
            proxy = _format_proxy(data["proxy"])
            if proxy:
                return proxy
        time.sleep(1)

    logger.warning("[ProxyClient] 代理池无可用代理")
    return None


def delete_proxy(proxy):
    """删除失效代理"""
    if not proxy:
        return False

    raw = _strip_protocol(proxy)
    success = False

    if redis_client.is_connected():
        try:
            removed = redis_client.hash_delete(PROXY_REDIS_KEY, raw)
            if removed > 0:
                logger.info("[ProxyClient] Redis 已删除: {}".format(raw))
                success = True
        except Exception as e:
            logger.warning("[ProxyClient] Redis 删除失败: {}".format(e))

    data = _api_get("/delete/", {"proxy": raw})
    if data is not None:
        success = True
    return success


def get_all():
    """获取所有代理"""
    if redis_client.is_connected():
        try:
            fields = redis_client.hash_all(PROXY_REDIS_KEY)
            if fields:
                return [_format_proxy(f) for f in fields if f]
        except Exception:
            pass

    data = _api_get("/all/")
    if data and isinstance(data, dict):
        return [_format_proxy(p) for p in data.get("proxy", []) if p]
    return []


def get_count():
    if redis_client.is_connected():
        try:
            count = redis_client.hash_count(PROXY_REDIS_KEY)
            if count > 0:
                return count
        except Exception:
            pass
    data = _api_get("/count/")
    return data.get("count", 0) if data else 0


def validate_proxy(proxy, test_url=VALIDATE_URL, timeout=10):
    """真实请求验证代理"""
    if not proxy:
        return False
    try:
        resp = _session.get(
            test_url,
            proxies={"http": proxy, "https": proxy},
            timeout=timeout)
        return resp.status_code == 200
    except Exception:
        return False


def get_valid_proxy(max_attempts=5):
    """获取一个经过验证的可用代理"""
    for _ in range(max_attempts):
        proxy = get_proxy()
        if not proxy:
            return None
        if validate_proxy(proxy):
            return proxy
        delete_proxy(proxy)
    return None


def is_online():
    if redis_client.is_connected():
        return True
    try:
        resp = _session.get("{}/".format(PROXY_POOL_API), timeout=3)
        return resp.status_code in (200, 404)
    except Exception:
        return False


def get_status():
    online = is_online()
    if not online:
        return {"online": False, "api": PROXY_POOL_API, "count": 0}

    mode = "redis" if redis_client.is_connected() else "http"
    return {
        "online": True,
        "mode": mode,
        "api": PROXY_POOL_API,
        "count": get_count(),
    }


# ═══════════════════════════════════════════════════════════
# 类封装
# ═══════════════════════════════════════════════════════════

class ProxyClient(object):
    def __init__(self, api=None):
        self.api = api or PROXY_POOL_API

    def get_proxy(self, retry=GET_RETRY):
        return get_proxy(retry=retry)

    def delete_proxy(self, proxy):
        return delete_proxy(proxy)

    def get_all(self):
        return get_all()

    def get_count(self):
        return get_count()

    def validate_proxy(self, proxy, test_url=VALIDATE_URL, timeout=10):
        return validate_proxy(proxy, test_url, timeout)

    def get_valid_proxy(self, max_attempts=5):
        return get_valid_proxy(max_attempts=max_attempts)

    def is_online(self):
        return is_online()

    def get_status(self):
        return get_status()


proxy_client = ProxyClient()