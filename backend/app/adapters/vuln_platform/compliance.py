# backend/app/adapters/vuln_platform/compliance.py
"""合规性检查器：robots.txt 检查 + 请求速率控制（线程安全）"""

import time
import threading
from urllib.robotparser import RobotFileParser
from urllib.parse import urlparse

from app import utils

logger = utils.get_logger()


class ComplianceChecker(object):

    def __init__(self, user_agent="ARL-Next-Bot/1.0",
                 default_delay=3.0):
        self.user_agent = user_agent
        self.default_delay = default_delay
        self._robots_cache = {}
        self._last_request_time = {}
        self._robots_lock = threading.Lock()
        self._rate_lock = threading.Lock()

    def can_fetch(self, url):
        parsed = urlparse(url)
        base_url = "{}://{}".format(parsed.scheme, parsed.netloc)
        if base_url not in self._robots_cache:
            with self._robots_lock:
                if base_url not in self._robots_cache:
                    rp = RobotFileParser()
                    robots_url = "{}/robots.txt".format(base_url)
                    try:
                        rp.set_url(robots_url)
                        rp.read()
                        self._robots_cache[base_url] = rp
                    except Exception as e:
                        logger.warning(
                            "robots.txt 读取失败 {}: {}".format(
                                robots_url, e))
                        self._robots_cache[base_url] = None

        rp = self._robots_cache.get(base_url)
        if rp is None:
            return True
        return rp.can_fetch(self.user_agent, url)

    def get_crawl_delay(self, url):
        parsed = urlparse(url)
        base_url = "{}://{}".format(parsed.scheme, parsed.netloc)
        rp = self._robots_cache.get(base_url)
        if rp:
            delay = rp.crawl_delay(self.user_agent)
            if delay:
                return float(delay)
        return self.default_delay

    def wait_if_needed(self, url):
        parsed = urlparse(url)
        domain = parsed.netloc
        delay = self.get_crawl_delay(url)
        with self._rate_lock:
            if domain not in self._last_request_time:
                self._last_request_time[domain] = time.time()
                return
            last_time = self._last_request_time[domain]
            elapsed = time.time() - last_time
            if elapsed < delay:
                time.sleep(delay - elapsed)
            self._last_request_time[domain] = time.time()