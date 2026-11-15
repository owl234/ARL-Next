# -*- coding: utf-8 -*-
"""
PyInfoHunter: High-Performance, Zero-Disk, Pure-Python WIH Scanning Engine.
Fetches HTML/JS in memory, applies 4-tier waterfall chunk discovery,
and extracts sensitive information with rule matching & 64-bit FNV-1a deduplication.
"""

import time
import json
from urllib.parse import urlparse
from typing import List, Set, Dict, Optional, Tuple
from concurrent.futures import as_completed
import logging
import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

from app.utils import ContextAwareThreadPoolExecutor
from app.modules import WihRecord
from .fnv1a import fnv1a_64
from .rule_engine import WihRuleEngine
from .chunk_parser import WebpackChunkParser
from .api_extractor import MAX_API_REQUESTS, document_base_url, extract_api_requests
from .api_probe import ApiProbe, ApiProbeSession

logger = logging.getLogger("arlv2.wih")

def _get_proxy(target_url=None):
    try:
        from app.services.proxy_service import resolve_proxy_url
        proxy = resolve_proxy_url(domain="scan", target_url=target_url)
        return proxy if proxy else None
    except Exception:
        try:
            from app.config import Config
            proxy = getattr(Config, "PROXY_URL", None)
            return proxy if proxy else None
        except Exception:
            return None

# Safety Limits to prevent OOM, infinite loops, and WAF blocks
MAX_JS_SIZE = 5 * 1024 * 1024       # 5 MB max per JS file
MAX_CHUNKS_PER_SITE = 200           # 200 dynamic chunks quota per site
CHUNK_CONSECUTIVE_ERRORS_LIMIT = 5   # Break on 5 consecutive 404/403 errors
DEFAULT_TIMEOUT = (5.0, 15.0)       # (connect_timeout, read_timeout)


class _FetchedText(str):
    """在不改变文本调用方式的前提下保留重定向后的页面地址。"""

    def __new__(cls, value, response_url):
        result = super().__new__(cls, value)
        result.response_url = response_url
        return result


class PyInfoHunter:
    """
    Pure Python Web Info Hunter Engine.
    """
    def __init__(self,
                 sites: List[str],
                 concurrency: int = 6,
                 rule_path: Optional[str] = None,
                 max_chunks_per_site: int = MAX_CHUNKS_PER_SITE):
        self.sites = list(dict.fromkeys(sites))  # Deduplicate preserving order
        self.concurrency = max(1, concurrency)
        self.max_chunks = max_chunks_per_site
        self.rule_engine = WihRuleEngine(rule_path)
        self.api_enabled = any(rule["id"] == "api_endpoint" and not rule.get("compiled")
                               for rule in self.rule_engine.rules)
        self.api_probe_enabled = any(
            rule["id"] == "api_endpoint" and not rule.get("compiled") and rule.get("probe")
            for rule in self.rule_engine.rules
        )
        self.chunk_parser = WebpackChunkParser(max_chunks_per_site=max_chunks_per_site)
        self.proxy = _get_proxy()
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "*/*",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8"
        }

    def _create_session(self) -> requests.Session:
        session = requests.Session()
        session.verify = False
        session.trust_env = False
        session.headers.update(self.headers)
        proxy = _get_proxy() or self.proxy
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}
        # Mount standard retry adapter with connection pool
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=50, max_retries=1)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _create_api_session(self):
        session = ApiProbeSession()
        session.verify = False  # 与现有 WIH 站点采集保持一致。
        session.trust_env = False  # 禁止隐式加载 netrc 认证及环境代理。
        session.headers.update({
            "User-Agent": self.headers["User-Agent"], "Accept": "*/*", "Accept-Encoding": "identity",
        })
        proxy = _get_proxy() or self.proxy
        if proxy:
            session.proxies = {"http": proxy, "https": proxy}
        return session

    def _probe_api_records(self, site, records):
        if not self.api_probe_enabled:
            return

        def _make_site_api_session():
            sess = self._create_api_session()
            if isinstance(sess, requests.Session):
                p = _get_proxy(target_url=site)
                sess.proxies = {"http": p, "https": p} if p else {}
            return sess

        probe = ApiProbe(site, _make_site_api_session)
        try:
            candidates = [record for record in records if record.api_request is not None]
            for record in sorted(candidates, key=lambda r: (r.api_request["method"],
                                                           r.api_request["url"] or "", r.api_request["path"])):
                source, _, label = record.source.rpartition(" [")
                source_tag = "inline" if label.startswith("inline-") else "script"

                def is_excluded(url):
                    content = "{} {}".format(record.api_request["method"], url)
                    return self.rule_engine.is_excluded("api_endpoint", content, site, source, source_tag)

                result = probe.collect(record.api_request, is_excluded)
                record.api_request["probe"] = result
                record.api_request["verified"] = result["state"] == "responded"
        except Exception as error:
            logger.warning("API response collection failed for %s: %s", site, type(error).__name__)
        finally:
            probe.close()

    def _safe_stream_get(self, session: requests.Session, url: str) -> Optional[str]:
        """
        Stream GET with 5MB cutoff to prevent OOM and memory exhaustion.
        """
        try:
            if isinstance(session, requests.Session):
                per_url_proxy = _get_proxy(target_url=url)
                session.proxies = {"http": per_url_proxy, "https": per_url_proxy} if per_url_proxy else {}
            with session.get(url, stream=True, timeout=DEFAULT_TIMEOUT, allow_redirects=True) as resp:
                if resp.status_code >= 400:
                    return None

                content_type = resp.headers.get("Content-Type", "").lower()
                # If Content-Type is image/binary, skip
                if any(bt in content_type for bt in ("image/", "audio/", "video/", "octet-stream", "zip", "pdf")):
                    return None

                content_len_header = resp.headers.get("Content-Length")
                if content_len_header and int(content_len_header) > MAX_JS_SIZE * 2:
                    logger.debug(f"Skipping huge file ({content_len_header} bytes): {url}")
                    return None

                chunks = []
                total_read = 0
                fetch_start = time.time()
                for chunk in resp.iter_content(chunk_size=32768):
                    # Defense against Slowloris: absolute 30s cap on stream reading
                    if time.time() - fetch_start > 30.0:
                        logger.warning(f"Slow stream timeout exceeded on {url}")
                        break

                    chunks.append(chunk)
                    total_read += len(chunk)
                    if total_read >= MAX_JS_SIZE:
                        break

                raw_bytes = b"".join(chunks)

            # Attempt UTF-8 decode, fallback to latin1
            try:
                text = raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                text = raw_bytes.decode("latin1", errors="ignore")
            return _FetchedText(text, getattr(resp, "url", url)) if self.api_enabled else text

        except Exception as e:
            logger.debug(f"Error fetching {url}: {e}")
            return None

    def _collect_api_requests(self, code, site, source_url, source_tag, base_url, records, limit,
                              source_label=None):
        if not self.api_enabled or limit <= 0:
            return 0
        added = 0
        try:
            for request in extract_api_requests(code, document_base=base_url, limit=limit):
                content = "{} {}".format(request["method"], request["url"] or request["path"])
                if request["url"] and request["url"] != request["path"]:
                    content += " [path: {}]".format(request["path"])
                if self.rule_engine.is_excluded("api_endpoint", content, site, source_url, source_tag):
                    continue
                # 独立的类型前缀及请求方法防止与原始路径、其他方法的记录互相覆盖。
                identity = json.dumps(["api_endpoint", site, request["method"], request["path"], request["url"]])
                record = WihRecord(
                    record_type="api_endpoint", content=content,
                    source="{} [{}:line {}]".format(source_url, source_label or source_tag, request["line"]),
                    site=site, fnv_hash=fnv1a_64(identity), api_request=request,
                )
                if record not in records:
                    records.add(record)
                    added += 1
        except Exception as error:
            # 附加提取失败时，原有规则和脚本发现仍继续执行。
            logger.warning("API candidate extraction failed for %s: %s", source_url, error)
        return added

    def _scan_single_site(self, site: str) -> List[WihRecord]:
        site_records: Set[WihRecord] = set()
        api_count = 0
        session = self._create_session()

        try:
            # 1. Fetch Entry HTML
            html_text = self._safe_stream_get(session, site)
            if not html_text:
                return []
            base_url = None
            if self.api_enabled:
                try:
                    base_url = document_base_url(html_text, getattr(html_text, "response_url", None) or site)
                except Exception as error:
                    logger.warning("API document base resolution failed for %s: %s", site, error)

            # 2. Extract Sensitive Information from HTML directly
            html_matches = self.rule_engine.extract_from_text(
                html_text,
                target_site=site,
                source_url=site,
                source_tag="page"
            )
            for r_type, content in html_matches:
                rec_hash = fnv1a_64(content)
                site_records.add(WihRecord(
                    record_type=r_type,
                    content=content,
                    source=f"{site} [page]",
                    site=site,
                    fnv_hash=rec_hash
                ))

            # 3. Extract Tier 1 Scripts & Next.js Manifest from HTML
            dom_data = self.chunk_parser.extract_from_html(html_text, site)
            
            # Scan inline scripts
            for idx, inline_code in enumerate(dom_data.get("inline_scripts", [])):
                inline_matches = self.rule_engine.extract_from_text(
                    inline_code,
                    target_site=site,
                    source_url=site,
                    source_tag="inline"
                )
                for r_type, content in inline_matches:
                    rec_hash = fnv1a_64(content)
                    site_records.add(WihRecord(
                        record_type=r_type,
                        content=content,
                        source=f"{site} [inline-{idx+1}]",
                        site=site,
                        fnv_hash=rec_hash
                    ))
                api_count += self._collect_api_requests(
                    inline_code, site, site, "inline", base_url,
                    site_records, MAX_API_REQUESTS - api_count, source_label="inline-{}".format(idx + 1),
                )

            # 4. Queue Scripts to Fetch and Expand Chunks
            to_fetch_scripts = list(dom_data.get("scripts", set()))
            fetched_scripts = set()
            discovered_chunks = set(to_fetch_scripts)
            consecutive_errors = 0

            while to_fetch_scripts and len(fetched_scripts) < self.max_chunks:
                # Process in batches
                batch = to_fetch_scripts[:10]
                to_fetch_scripts = to_fetch_scripts[10:]

                for script_url in batch:
                    if script_url in fetched_scripts:
                        continue
                    fetched_scripts.add(script_url)

                    js_text = self._safe_stream_get(session, script_url)
                    if not js_text:
                        consecutive_errors += 1
                        if consecutive_errors >= CHUNK_CONSECUTIVE_ERRORS_LIMIT:
                            logger.debug(f"Consecutive errors reached limit for {site}, halting chunk expansion")
                            to_fetch_scripts.clear()
                            break
                        continue
                    else:
                        consecutive_errors = 0

                    # Extract Sensitive Info from JS
                    js_matches = self.rule_engine.extract_from_text(
                        js_text,
                        target_site=site,
                        source_url=script_url,
                        source_tag="script"
                    )
                    for r_type, content in js_matches:
                        rec_hash = fnv1a_64(content)
                        site_records.add(WihRecord(
                            record_type=r_type,
                            content=content,
                            source=f"{script_url} [script]",
                            site=site,
                            fnv_hash=rec_hash
                        ))
                    api_count += self._collect_api_requests(
                        js_text, site, script_url, "script", base_url,
                        site_records, MAX_API_REQUESTS - api_count,
                    )

                    # Expand dynamic Webpack / Vite / Next.js chunks if within quota
                    if len(discovered_chunks) < self.max_chunks:
                        new_chunks = self.chunk_parser.extract_chunks_from_js(js_text, script_url)
                        for nc in new_chunks:
                            if nc not in discovered_chunks and len(discovered_chunks) < self.max_chunks:
                                discovered_chunks.add(nc)
                                to_fetch_scripts.append(nc)

        except Exception as e:
            logger.warning(f"Error during PyInfoHunter scan on {site}: {e}")
        finally:
            session.close()

        self._probe_api_records(site, site_records)
        return list(site_records)

    def run(self) -> List[WihRecord]:
        t1 = time.time()
        logger.info(f"Start PyInfoHunter scan on {len(self.sites)} sites (concurrency={self.concurrency})")

        if not self.sites:
            return []

        all_results: Set[WihRecord] = set()

        if len(self.sites) == 1:
            records = self._scan_single_site(self.sites[0])
            all_results.update(records)
        else:
            executor = ContextAwareThreadPoolExecutor(max_workers=self.concurrency)
            try:
                future_to_site = {executor.submit(self._scan_single_site, s): s for s in self.sites}
                for future in as_completed(future_to_site):
                    site = future_to_site[future]
                    try:
                        records = future.result()
                        all_results.update(records)
                    except Exception as e:
                        logger.error(f"PyInfoHunter worker failed for {site}: {e}")
            except BaseException as e:
                logger.warning(f"PyInfoHunter interrupted or task revoked, terminating threadpool: {e}")
                executor.shutdown(wait=False, cancel_futures=True)
                raise
            finally:
                executor.shutdown(wait=False)

        elapsed = time.time() - t1
        logger.info(f"PyInfoHunter finished in {elapsed:.2f}s, found {len(all_results)} records across {len(self.sites)} sites")
        return list(all_results)


def run_wih_python(sites: List[str]) -> List[WihRecord]:
    from app.config import Config
    hunter = PyInfoHunter(sites=sites, rule_path=Config.WIH_RULE_PATH)
    return hunter.run()
