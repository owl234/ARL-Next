# backend/app/adapters/vuln_platform/butian.py
"""补天平台适配器"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from app import utils
from .base import BasePlatformAdapter

logger = utils.get_logger()


class BuTianAdapter(BasePlatformAdapter):

    MAX_PAGES = 500
    DEFAULT_CONCURRENCY = 5

    def __init__(self, platform_name="butian", db=None):
        super().__init__(platform_name, db=db)

    def fetch_projects(self, max_pages=None, concurrency=None):
        """获取补天项目列表"""
        concurrency = concurrency or self.DEFAULT_CONCURRENCY
        max_pages = min(max_pages or self.MAX_PAGES, self.MAX_PAGES)

        # ★ 预缓存代理（针对补天实际 API 地址验证）
        base = self.config["base_url"]
        target_url = "{}/Reward/pub".format(base)
        self.warmup_proxy(target_url=target_url,
                           size=concurrency * 2)

        # 确保 Cookie 有效
        if self.cookie_mgr:
            if not self.cookie_mgr.ensure_valid(
                    self.config["test_url"], self._login):
                raise RuntimeError("补天 Cookie 维护失败")

        # ── 第 1 页获取总数 ──────────────────────────
        first_data = self._fetch_page_json(1)
        if not first_data:
            logger.error("补天首页请求失败")
            return []

        data = first_data.get("data", {})
        total_pages = min(data.get("count", 0), max_pages)
        first_list = data.get("list", [])

        if not first_list:
            logger.warning("补天第 1 页无数据")
            return []

        logger.info("补天共 {} 页".format(total_pages))

        # ── 容器 ──────────────────────────────────
        projects = []
        seen_ids = set()
        seen_lock = threading.Lock()
        progress = {"done": 1, "total": total_pages}
        progress_lock = threading.Lock()

        self._collect_projects(first_list, projects, seen_ids)

        # ── 并发抓取剩余页 ──────────────────────────
        if total_pages > 1:
            self._fetch_remaining_pages(
                start=2, end=total_pages,
                projects=projects, seen_ids=seen_ids,
                seen_lock=seen_lock,
                progress=progress, progress_lock=progress_lock,
                concurrency=concurrency)

        logger.info("补天共获取 {} 个项目".format(len(projects)))
        return projects

    def _fetch_remaining_pages(self, start, end, projects, seen_ids,
                                seen_lock, progress, progress_lock,
                                concurrency=5):
        pages = list(range(start, end + 1))

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            future_to_page = {
                executor.submit(self._fetch_single_page, page): page
                for page in pages
            }

            for future in as_completed(future_to_page):
                page = future_to_page[future]
                try:
                    page_list = future.result()
                except Exception as e:
                    logger.error("第 {} 页异常: {}".format(page, e))
                    page_list = []

                if not page_list:
                    continue

                with seen_lock:
                    self._collect_projects(page_list, projects, seen_ids)

                with progress_lock:
                    progress["done"] += 1

    def _fetch_single_page(self, page):
        data = self._fetch_page_json(page)
        if not data:
            return []
        return data.get("data", {}).get("list", [])

    def _fetch_page_json(self, page):
        """请求补天单页 JSON（POST）"""
        url = "{}/Reward/pub".format(self.config["base_url"])

        resp = self._safe_request(
            url,
            method="POST",
            data={"ajax": "1", "name": "", "p": str(page)},
            headers={
                "X-Requested-With": "XMLHttpRequest",
                "Referer": "{}/Reward/plan".format(
                    self.config["base_url"]),
            },
            use_proxy=True,
            timeout=15)

        if resp.status_code != 200:
            logger.warning("HTTP {}: p={}".format(resp.status_code, page))
            return None

        try:
            result = resp.json()
        except Exception as e:
            logger.error("JSON 解析失败 [p={}]: {}".format(page, e))
            return None

        if result.get("status") != 1:
            return None
        return result

    def _collect_projects(self, items, projects, seen_ids):
        for item in items:
            company_id = str(item.get("company_id", "")).strip()
            company_name = (item.get("company_name") or "").strip()
            if not company_id or company_id in seen_ids:
                continue
            seen_ids.add(company_id)
            projects.append({
                "project_id": company_id,
                "project_name": company_name or "补天项目-{}".format(company_id),
                "scope": [],
                "platform": "butian",
                "avatar": item.get("avatar", ""),
            })

    def fetch_scope(self, project_id):
        url = "{}/Reward/plan/{}".format(
            self.config["base_url"], project_id)
        try:
            resp = self._safe_request(url)
            if resp.status_code != 200:
                return []
            return self._extract_scope(resp.text)
        except Exception as e:
            logger.error("获取范围失败 [{}]: {}".format(project_id, e))
            return []

    def submit_vulnerability(self, vuln_data):
        logger.info("补天提交漏洞: {}".format(
            vuln_data.get("title", "N/A")))
        return {
            "success": False,
            "platform_vuln_id": None,
            "message": "补天提交需处理极验滑块，请配置后启用",
        }

    def _login(self):
        logger.warning("补天未实现自动登录")
        return ""

    def _extract_scope(self, html):
        import re
        scope = set()
        domain_pattern = re.compile(
            r'(?:域名|目标|范围|资产)[：:\s]*'
            r'([a-zA-Z0-9*][a-zA-Z0-9*.-]*\.[a-zA-Z]{2,})',
            re.IGNORECASE)
        for m in domain_pattern.finditer(html):
            scope.add(m.group(1).strip().lower())
        ip_pattern = re.compile(r'\b((?:\d{1,3}\.){3}\d{1,3})\b')
        for m in ip_pattern.finditer(html):
            scope.add(m.group(1))
        return sorted(scope)