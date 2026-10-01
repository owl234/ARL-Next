# backend/app/utils/redis_client.py
"""
Redis 客户端封装（单例、线程安全）
"""

import os
import threading

from app import utils

logger = utils.get_logger()


# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

REDIS_URL = os.environ.get(
    "ARL_REDIS_URL",
    os.environ.get("DB_CONN", "redis://127.0.0.1:6379/0"))


# ═══════════════════════════════════════════════════════════
# RedisClient
# ═══════════════════════════════════════════════════════════

class RedisClient(object):
    """Redis 客户端（单例、线程安全）"""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, url=None):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self, url=None):
        if getattr(self, "_initialized", False):
            return
        self.url = url or REDIS_URL
        self._conn = None
        self._init_conn()
        self._initialized = True

    def _init_conn(self):
        if not self.url:
            logger.warning("[RedisClient] 未配置 Redis URL")
            return

        try:
            import redis
            self._conn = redis.from_url(
                self.url,
                decode_responses=True,
                socket_timeout=5,
                socket_connect_timeout=5,
                health_check_interval=30,
            )
            self._conn.ping()
            logger.info("[RedisClient] 已连接: {}".format(
                self._mask(self.url)))
        except ImportError:
            logger.warning("[RedisClient] 未安装 redis 库")
            self._conn = None
        except Exception as e:
            logger.warning("[RedisClient] 连接失败: {}".format(e))
            self._conn = None

    @property
    def conn(self):
        if self._conn is None:
            self._init_conn()
        return self._conn

    def is_connected(self):
        if self._conn is None:
            return False
        try:
            return self._conn.ping()
        except Exception:
            return False

    # ── Hash 操作 ─────────────────────────────────
    def hash_all(self, key):
        try:
            return self.conn.hkeys(key) or []
        except Exception as e:
            logger.warning("[RedisClient] hkeys 失败: {}".format(e))
            return []

    def hash_random(self, key, count=1):
        try:
            result = self.conn.hrandfield(key, count)
            if result:
                return result if isinstance(result, list) else [result]
        except Exception:
            try:
                import random
                keys = self.conn.hkeys(key) or []
                if keys:
                    random.shuffle(keys)
                    return keys[:count]
            except Exception as e:
                logger.warning("[RedisClient] hrandfield 失败: {}".format(e))
        return []

    def hash_get(self, key, field):
        try:
            return self.conn.hget(key, field)
        except Exception:
            return None

    def hash_delete(self, key, *fields):
        try:
            return self.conn.hdel(key, *fields)
        except Exception as e:
            logger.warning("[RedisClient] hdel 失败: {}".format(e))
            return 0

    def hash_count(self, key):
        try:
            return self.conn.hlen(key) or 0
        except Exception:
            return 0

    def hash_set(self, key, field, value):
        try:
            return self.conn.hset(key, field, value)
        except Exception as e:
            logger.warning("[RedisClient] hset 失败: {}".format(e))
            return 0

    # ── 通用操作 ──────────────────────────────────
    def get(self, key):
        return self._safe(lambda: self.conn.get(key))

    def set(self, key, value, ex=None):
        return self._safe(lambda: self.conn.set(key, value, ex=ex))

    def delete(self, *keys):
        return self._safe(lambda: self.conn.delete(*keys))

    def exists(self, key):
        return self._safe(lambda: self.conn.exists(key))

    def _safe(self, func):
        try:
            return func()
        except Exception as e:
            logger.warning("[RedisClient] 操作失败: {}".format(e))
            return None

    @staticmethod
    def _mask(url):
        if "@" in url:
            proto, rest = url.split("://", 1) if "://" in url \
                else ("redis", url)
            creds, host = rest.rsplit("@", 1)
            if ":" in creds:
                user = creds.split(":", 1)[0]
                return "{}://{}:***@{}".format(proto, user, host)
        return url


# 全局单例
redis_client = RedisClient()