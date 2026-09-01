# -*- coding: utf-8 -*-
"""
Modern Frontend Bundle Reverse Extractor & Waterfall Chunk Parser.
Zero-Dependency Standard Library Implementation.
Supports:
  Tier 1: HTML DOM <script>, <link preload>, Next.js  Manifest
  Tier 2: Webpack 3 / 4 / 5 Runtime (Dictionary / Array / Ternary / jsonp / __webpack_require__.u)
  Tier 3: Vite / Rollup  & dynamic 
  Tier 4: Normalization, publicPath Resolution, and Common Library Filtering.
"""

import re
import json
from urllib.parse import urljoin, urlparse
import logging
from typing import Set, List, Dict, Optional, Any

logger = logging.getLogger("arlv2.wih")

# Common third-party vendor libraries to ignore from chunk parsing
COMMON_VENDOR_SCRIPTS = {
    "vue.js", "vue.min.js", "vue.runtime.min.js",
    "react.js", "react.min.js", "react-dom.js", "react-dom.min.js", "react-dom.production.min.js",
    "jquery.js", "jquery.min.js", "jquery-3.6.0.min.js",
    "lodash.js", "lodash.min.js",
    "axios.js", "axios.min.js",
    "element-ui.js", "element-plus.js", "element-plus.min.js",
    "antd.min.js", "ant-design-vue.min.js",
    "echarts.js", "echarts.min.js",
    "bootstrap.js", "bootstrap.min.js",
    "moment.js", "moment.min.js",
    "core-js.min.js", "regenerator-runtime.js",
    "highlight.min.js", "crypto-js.min.js"
}

# Webpack dictionary mappings: {0:"a1b2", 1:"c3d4"} or {"admin":"a1b2", "login":"c3d4"}
WEBPACK_DICT_PATTERN = re.compile(
    r'\{(?:\s*[\'"]?[a-zA-Z0-9_\-]+[\'"]?\s*:\s*[\'"][a-zA-Z0-9_\-]*[\'"]\s*,)+'
    r'\s*[\'"]?[a-zA-Z0-9_\-]+[\'"]?\s*:\s*[\'"][a-zA-Z0-9_\-]*[\'"]\s*,?\s*\}'
)

# Webpack 5 nested ternary expressions: (123 === e ? "a1b2" : 456 === e ? "c3d4" : ...)
WEBPACK_TERNARY_PATTERN = re.compile(
    r'([a-zA-Z0-9_\-]+)\s*===?\s*[a-zA-Z0-9_$]+\s*\?\s*[\'"]([a-zA-Z0-9_\-]+)[\'"]'
)

# Vite __vitePreload: __vitePreload(() => ["assets/chunk-1.js", ...]) or minified functions
VITE_PRELOAD_PATTERN = re.compile(
    r'__vitePreload\s*\([^\[]*\[([^\]]+)\]'
)

# Dynamic import patterns: import("./chunk-xxx.js") or import('/assets/xxx.js')
DYNAMIC_IMPORT_PATTERN = re.compile(
    r'(?:import|importScripts)\s*\(\s*[\'"]([^\'"]+\.js(?:\?[^\'"]*)?)[\'"]\s*\)'
)

# Generic JS filename pattern in code: "chunk-12345.js" or "static/js/2.12345.chunk.js"
GENERIC_CHUNK_PATTERN = re.compile(
    r'[\'"]([a-zA-Z0-9_\-/]+\.(?:chunk|bundle|pages|app)?[a-zA-Z0-9_\-.]*\.js)[\'"]'
)

# Webpack publicPath pattern: __webpack_require__.p = "/static/js/" or "/_next/" or "/"
WEBPACK_PUBLIC_PATH_PATTERN = re.compile(
    r'__webpack_require__\.p\s*=\s*[\'"]([^\'"]+)[\'"]'
)

# HTML Script Tag Extraction Patterns
HTML_SCRIPT_SRC_PATTERN = re.compile(r'<script[^>]+src=(?:[\'"]([^\'"\s>]+)[\'"]|([^\'"\s>]+))', re.IGNORECASE)
HTML_INLINE_SCRIPT_PATTERN = re.compile(r'<script([^>]*)>([\s\S]*?)</script>', re.IGNORECASE)
HTML_LINK_PRELOAD_PATTERN = re.compile(r'<link[^>]+href=(?:[\'"]([^\'"\s>]+)[\'"]|([^\'"\s>]+))[^>]*>', re.IGNORECASE)
HTML_NEXT_DATA_PATTERN = re.compile(r'<script[^>]+id=[\'"]?__NEXT_DATA__[\'"]?[^>]*>([\s\S]*?)</script>', re.IGNORECASE)


class WebpackChunkParser:
    """
    Deep chunk parser for modern single-page applications.
    """
    def __init__(self, max_chunks_per_site: int = 200):
        self.max_chunks = max_chunks_per_site

    def extract_from_html(self, html: str, base_url: str) -> Dict[str, Any]:
        """
        Tier 1: HTML DOM scripts, preload links, and Next.js __NEXT_DATA__
        """
        result = {
            "scripts": set(),
            "inline_scripts": [],
            "next_manifest_urls": set()
        }

        if not html:
            return result

        try:
            # 1. Extract <script src=...>
            for match in HTML_SCRIPT_SRC_PATTERN.finditer(html):
                src = match.group(1) or match.group(2)
                if src:
                    full_url = urljoin(base_url, src.strip())
                    if self._is_valid_script_url(full_url):
                        result["scripts"].add(full_url)

            # 2. Extract Inline Scripts
            for match in HTML_INLINE_SCRIPT_PATTERN.finditer(html):
                attrs = match.group(1).lower()
                if "src=" not in attrs:
                    clean_text = match.group(2).strip()
                    if clean_text:
                        result["inline_scripts"].append(clean_text)

            # 3. Extract <link rel="preload/modulepreload" href="...">
            for link_match in HTML_LINK_PRELOAD_PATTERN.finditer(html):
                tag_str = link_match.group(0).lower()
                if "preload" in tag_str or ".js" in tag_str:
                    href = link_match.group(1) or link_match.group(2)
                    if href:
                        href = href.strip()
                        if href.endswith(".js") or "script" in tag_str:
                            full_url = urljoin(base_url, href)
                            if self._is_valid_script_url(full_url):
                                result["scripts"].add(full_url)

            # 4. Next.js __NEXT_DATA__ JSON inspection
            next_match = HTML_NEXT_DATA_PATTERN.search(html)
            if next_match:
                try:
                    next_json_str = next_match.group(1).strip()
                    if next_json_str:
                        next_obj = json.loads(next_json_str)
                        build_id = next_obj.get("buildId")
                        if build_id:
                            m1 = urljoin(base_url, f"/_next/static/{build_id}/_buildManifest.js")
                            m2 = urljoin(base_url, f"/_next/static/{build_id}/_ssgManifest.js")
                            result["next_manifest_urls"].add(m1)
                            result["next_manifest_urls"].add(m2)
                            result["scripts"].add(m1)
                            result["scripts"].add(m2)

                        page = next_obj.get("page", "")
                        if page and build_id:
                            clean_page = page.lstrip("/")
                            if clean_page:
                                page_chunk = urljoin(base_url, f"/_next/static/chunks/pages/{clean_page}.js")
                                result["scripts"].add(page_chunk)
                except Exception as e:
                    logger.debug(f"Error parsing Next.js __NEXT_DATA__: {e}")

        except Exception as e:
            logger.warning(f"Error extracting HTML scripts {base_url}: {e}")

        return result

    def extract_chunks_from_js(self, js_code: str, base_script_url: str) -> Set[str]:
        """
        Tier 2 & 3: Webpack / Vite / Next.js chunk extraction from JavaScript code.
        """
        if not js_code or len(js_code) < 50:
            return set()

        chunk_urls: Set[str] = set()
        public_path = self._extract_public_path(js_code, base_script_url)

        # 1. Webpack Dictionary / Chunk ID mappings
        webpack_chunks = self._extract_webpack_dict_chunks(js_code)
        for chunk in webpack_chunks:
            full_url = urljoin(public_path, chunk)
            if self._is_valid_script_url(full_url):
                chunk_urls.add(full_url)

        # 2. Webpack 5 Ternary mappings
        ternary_chunks = self._extract_webpack_ternary_chunks(js_code)
        for chunk in ternary_chunks:
            full_url = urljoin(public_path, chunk)
            if self._is_valid_script_url(full_url):
                chunk_urls.add(full_url)

        # 3. Vite __vitePreload extraction
        vite_chunks = self._extract_vite_preload_chunks(js_code)
        for chunk in vite_chunks:
            full_url = urljoin(public_path, chunk)
            if self._is_valid_script_url(full_url):
                chunk_urls.add(full_url)

        # 4. Dynamic import("...")
        dynamic_imports = self._extract_dynamic_imports(js_code)
        for chunk in dynamic_imports:
            full_url = urljoin(public_path, chunk)
            if self._is_valid_script_url(full_url):
                chunk_urls.add(full_url)

        # 5. Next.js _buildManifest.js self-parsing
        if "_buildManifest.js" in base_script_url:
            next_chunks = self._extract_nextjs_build_manifest(js_code)
            for chunk in next_chunks:
                full_url = urljoin(base_script_url, chunk)
                if self._is_valid_script_url(full_url):
                    chunk_urls.add(full_url)

        # 6. Generic Heuristic chunk names
        generic_chunks = self._extract_generic_chunks(js_code)
        for chunk in generic_chunks:
            full_url = urljoin(public_path, chunk)
            if self._is_valid_script_url(full_url):
                chunk_urls.add(full_url)

        return chunk_urls

    def _extract_public_path(self, js_code: str, fallback_url: str) -> str:
        match = WEBPACK_PUBLIC_PATH_PATTERN.search(js_code)
        if match:
            p = match.group(1).strip()
            if p:
                if not p.endswith("/") and not p.endswith("="):
                    p = p + "/"
                return urljoin(fallback_url, p)
        parsed = urlparse(fallback_url)
        path = parsed.path
        dir_path = path.rsplit("/", 1)[0] + "/" if "/" in path else "/"
        return f"{parsed.scheme}://{parsed.netloc}{dir_path}"

    def _extract_webpack_dict_chunks(self, js_code: str) -> Set[str]:
        chunks = set()
        # 仅在 webpack 运行时上下文附近提取 chunk 字典映射，避免匹配到 JSON 配置/i18n 等无关键值对
        # 上下文标识: __webpack_require__, chunkId, installedChunks, webpackJsonp, __webpack_modules__
        context_markers = ("__webpack_require__", "chunkId", "installedChunks", "webpackJsonp", "__webpack_modules__", "mini-css")
        has_webpack_context = any(marker in js_code for marker in context_markers)
        if not has_webpack_context:
            return chunks
        for match in WEBPACK_DICT_PATTERN.finditer(js_code):
            block = match.group(0)
            for kv_match in re.finditer(r'[\'\"]?([a-zA-Z0-9_\-]+)[\'\"]?\s*:\s*[\'\"]([a-zA-Z0-9_\-]{6,40})[\'"]', block):
                k, v = kv_match.groups()
                chunks.add(f"{k}.{v}.js")
                chunks.add(f"chunk-{k}.{v}.js")
        return chunks

    def _extract_webpack_ternary_chunks(self, js_code: str) -> Set[str]:
        chunks = set()
        matches = WEBPACK_TERNARY_PATTERN.findall(js_code)
        for chunk_id, chunk_hash in matches:
            chunks.add(f"{chunk_id}.{chunk_hash}.js")
            chunks.add(f"chunk-{chunk_id}.{chunk_hash}.js")
        return chunks

    def _extract_vite_preload_chunks(self, js_code: str) -> Set[str]:
        chunks = set()
        for match in VITE_PRELOAD_PATTERN.finditer(js_code):
            inner = match.group(1)
            raw_files = re.findall(r'[\'"]([^\'"]+\.js)[\'"]', inner)
            for f in raw_files:
                chunks.add(f.strip())
        return chunks

    def _extract_dynamic_imports(self, js_code: str) -> Set[str]:
        chunks = set()
        for match in DYNAMIC_IMPORT_PATTERN.finditer(js_code):
            target = match.group(1).strip()
            if target and not target.startswith("data:"):
                chunks.add(target)
        return chunks

    def _extract_nextjs_build_manifest(self, js_code: str) -> Set[str]:
        chunks = set()
        manifest_chunks = re.findall(r'[\'"](static/chunks/[^\'"]+\.js)[\'"]', js_code)
        for c in manifest_chunks:
            chunks.add(f"/_next/{c}")
        return chunks

    def _extract_generic_chunks(self, js_code: str) -> Set[str]:
        chunks = set()
        matches = GENERIC_CHUNK_PATTERN.findall(js_code)
        for m in matches:
            clean = m.strip()
            if clean.endswith(".js") and "/" not in clean[:1]:
                if len(clean) <= 80 and not any(c in clean for c in (" ", ";", "(", ")")):
                    chunks.add(clean)
        return chunks

    def _is_valid_script_url(self, url: str) -> bool:
        if not url or not (url.startswith("http://") or url.startswith("https://")):
            return False
        
        parsed = urlparse(url)
        filename = parsed.path.rsplit("/", 1)[-1].lower() if "/" in parsed.path else ""
        
        if filename in COMMON_VENDOR_SCRIPTS:
            return False

        for ext in (".map", ".css", ".png", ".jpg", ".svg", ".ico", ".json", ".wasm", ".zip"):
            if parsed.path.lower().endswith(ext):
                return False

        return True
