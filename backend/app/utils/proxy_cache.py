# backend/app/utils/proxy_cache.py
"""
线程本地代理缓存（按目标站点验证）

设计：
- 缓存 key 与目标站点绑定
- 预缓存时用目标站点验证代理
- ★ 验证不通过 → 从代理池删除
- 每个线程、每个目标独立缓存
"""

import os
import time
import random
import threading
from typing import Optional, List
from urllib.parse import urlparse

import requests

from app import utils
from app.utils.proxy_client import proxy_client

logger = utils.get_logger()


# ═══════════════════════════════════════════════════════════
# 配置
# ═══════════════════════════════════════════════════════════

CACHE_SIZE = int(os.environ.get("ARL_PROXY_CACHE_SIZE", 5))
CACHE_TTL = int(os.environ.get("ARL_PROXY_CACHE_TTL", 60))
WARMUP_TIMEOUT = int(os.environ.get("ARL_PROXY_WARMUP_TIMEOUT", 10))
WARMUP_MAX_CANDIDATES = int(os.environ.get("ARL_PROXY_WARMUP_CANDIDATES", 30))
WARMUP_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
              "AppleWebKit/537.36 (KHTML, like Gecko) "
              "Chrome/122.0.0.0 Safari/537.36")


# ═══════════════════════════════════════════════════════════
# ProxyCache
# ═══════════════════════════════════════════════════════════

class ProxyCache(object):
    """线程本地代理缓存（按目标站点验证）"""

    def __init__(self, size=CACHE_SIZE, ttl=CACHE_TTL):
        self.size = size
        self.ttl = ttl
        self._local = threading.local()

    # ═══════════════════════════════════════════════
    # 预缓存
    # ═══════════════════════════════════════════════

    def warmup(self, target_url: str, force: bool = False,
                size: int = None) -> int:
        """预缓存代理（针对实际目标站点验证）"""
        size = size or self.size
        cache = self._ensure_cache(target_url, force=force, size=size)
        count = len(cache["proxies"])

        logger.info(
            "[ProxyCache] 线程 {} 预缓存 [{}]: {} 个代理".format(
                threading.current_thread().name,
                self._mask_url(target_url), count))
        return count

    # ═══════════════════════════════════════════════
    # 核心方法
    # ═══════════════════════════════════════════════

    def get(self, target_url: str) -> Optional[str]:
        """获取一个代理"""
        cache = self._ensure_cache(target_url)
        if not cache["proxies"]:
            return None
        return random.choice(cache["proxies"])

    def mark_dead(self, target_url: str, proxy: str):
        """标记代理失效"""
        if not proxy:
            return

        cache = self._get_cache(target_url)
        if not cache:
            return

        if proxy in cache["proxies"]:
            cache["proxies"].remove(proxy)
            logger.debug(
                "[ProxyCache] 线程 {} [{}] 移除 {}（剩余 {}）".format(
                    threading.current_thread().name,
                    self._mask_url(target_url),
                    proxy, len(cache["proxies"])))

            if len(cache["proxies"]) < self.size // 2:
                self._fill_cache(cache, target_url)

    def clear(self, target_url: str = None):
        if target_url:
            cache_key = self._get_cache_key(target_url)
            setattr(self._local, cache_key, None)
        else:
            self._local.__dict__.clear()

    def get_proxies(self, target_url: str) -> List[str]:
        """获取当前缓存的代理列表"""
        cache = self._get_cache(target_url)
        if not cache:
            return []
        return list(cache["proxies"])

    def stats(self, target_url: str = None) -> dict:
        if target_url:
            cache = self._get_cache(target_url)
            return {
                "thread": threading.current_thread().name,
                "target": self._mask_url(target_url),
                "count": len(cache["proxies"]) if cache else 0,
                "age": round(time.time() - cache["time"], 1) if cache else 0,
                "size": self.size,
                "ttl": self.ttl,
            }
        return {
            "thread": threading.current_thread().name,
            "caches": dict(getattr(self._local, "__dict__", {})),
        }

    # ═══════════════════════════════════════════════
    # 内部方法
    # ═══════════════════════════════════════════════

    def _get_cache_key(self, target_url: str) -> str:
        try:
            netloc = urlparse(target_url).netloc or "default"
        except Exception:
            netloc = "default"
        safe = netloc.replace(".", "_").replace(":", "_")
        return "cache_{}".format(safe)

    def _get_cache(self, target_url: str):
        cache_key = self._get_cache_key(target_url)
        return getattr(self._local, cache_key, None)

    def _ensure_cache(self, target_url: str, force: bool = False,
                       size: int = None) -> dict:
        cache_key = self._get_cache_key(target_url)
        now = time.time()
        cache = getattr(self._local, cache_key, None)
        size = size or self.size

        if cache is None:
            cache = {"proxies": [], "time": now, "target": target_url}
            setattr(self._local, cache_key, cache)
            self._fill_cache(cache, target_url, size)
            return cache

        if force:
            cache["proxies"] = []
            cache["time"] = now
            self._fill_cache(cache, target_url, size)
            return cache

        if now - cache["time"] > self.ttl:
            logger.debug(
                "[ProxyCache] 线程 {} [{}] 缓存过期，刷新".format(
                    threading.current_thread().name,
                    self._mask_url(target_url)))
            cache["proxies"] = []
            cache["time"] = now
            self._fill_cache(cache, target_url, size)
        elif len(cache["proxies"]) < size // 2:
            self._fill_cache(cache, target_url, size)

        return cache

    def _fill_cache(self, cache: dict, target_url: str,
                     size: int = None):
        """
        填充缓存（针对目标站点验证）
        ★ 验证不通过 → 从代理池删除
        """
        size = size or self.size
        need = size - len(cache["proxies"])
        if need <= 0:
            return

        logger.debug(
            "[ProxyCache] 线程 {} [{}] 补充 {} 个代理".format(
                threading.current_thread().name,
                self._mask_url(target_url), need))

        candidates_tried = 0
        deleted_count = 0

        while len(cache["proxies"]) < size \
                and candidates_tried < WARMUP_MAX_CANDIDATES:
            candidates_tried += 1

            # 1. 从代理池取候选
            try:
                raw = proxy_client.get_proxy()
                if not raw:
                    logger.warning("[ProxyCache] 代理池为空")
                    break
            except Exception as e:
                logger.debug("[ProxyCache] 获取代理失败: {}".format(e))
                break

            # 2. 跳过已缓存的
            if raw in cache["proxies"]:
                continue

            # 3. 用目标站点验证
            if self._validate_for_target(raw, target_url):
                # ★ 验证通过 → 加入缓存
                cache["proxies"].append(raw)
                logger.debug(
                    "[ProxyCache] ✓ {} 可访问 {}".format(
                        raw, self._mask_url(target_url)))
            else:
                # ★ 验证不通过 → 从代理池删除
                try:
                    proxy_client.delete_proxy(raw)
                    deleted_count += 1
                    logger.info(
                        "[ProxyCache] ✗ {} 无法访问 {}，"
                        "已从代理池删除".format(
                            raw, self._mask_url(target_url)))
                except Exception as e:
                    logger.debug(
                        "[ProxyCache] 删除失败 {}: {}".format(raw, e))

        logger.debug(
            "[ProxyCache] 线程 {} [{}] 填充完成: {}/{} "
            "（尝试 {} 个，删除 {} 个）".format(
                threading.current_thread().name,
                self._mask_url(target_url),
                len(cache["proxies"]), size,
                candidates_tried, deleted_count))

    def _validate_for_target(self, proxy: str, target_url: str) -> bool:
        """用目标站点验证代理"""
        if not proxy or not target_url:
            return False

        try:
            resp = requests.get(
                target_url,
                proxies={"http": proxy, "https": proxy},
                headers={"User-Agent": WARMUP_UA},
                timeout=WARMUP_TIMEOUT,
                verify=False,
                allow_redirects=False)

            status = resp.status_code
            # 有响应即视为代理通
            return status in (200, 201, 204, 301, 302, 307, 308,
                               401, 403, 404, 429)
        except requests.exceptions.ProxyError:
            return False
        except requests.exceptions.Timeout:
            return False
        except requests.exceptions.ConnectionError:
            return False
        except Exception as e:
            logger.debug(
                "[ProxyCache] 验证异常 {} → {}: {}".format(
                    proxy, self._mask_url(target_url), e))
            return False

    @staticmethod
    def _mask_url(url: str) -> str:
        if not url:
            return ""
        try:
            return urlparse(url).netloc or url[:40]
        except Exception:
            return url[:40]


# 全局单例
proxy_cache = ProxyCache()

if __name__ == "__main__":
    proxy_cache.warmup("")