# -*- coding: utf-8 -*-
"""
PyInfoHunter: High-Performance, Zero-Disk, Pure-Python WIH Scanning Engine.
Fetches HTML/JS in memory, applies 4-tier waterfall chunk discovery,
and extracts sensitive information with rule matching & 64-bit FNV-1a deduplication.
"""

import time
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

logger = logging.getLogger("arlv2.wih")

def _get_proxy():
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
        session.headers.update(self.headers)
        if self.proxy:
            session.proxies = {"http": self.proxy, "https": self.proxy}
        else:
            session.trust_env = False
        # Mount standard retry adapter with connection pool
        adapter = requests.adapters.HTTPAdapter(pool_connections=20, pool_maxsize=50, max_retries=1)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def _safe_stream_get(self, session: requests.Session, url: str) -> Optional[str]:
        """
        Stream GET with 5MB cutoff to prevent OOM and memory exhaustion.
        """
        try:
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
                return raw_bytes.decode("utf-8")
            except UnicodeDecodeError:
                return raw_bytes.decode("latin1", errors="ignore")

        except Exception as e:
            logger.debug(f"Error fetching {url}: {e}")
            return None

    def _scan_single_site(self, site: str) -> List[WihRecord]:
        site_records: Set[WihRecord] = set()
        session = self._create_session()

        try:
            # 1. Fetch Entry HTML
            html_text = self._safe_stream_get(session, site)
            if not html_text:
                return []

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
