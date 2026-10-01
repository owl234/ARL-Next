# backend/app/adapters/vuln_platform/butian.py
"""
补天平台适配器
- 项目列表：POST https://www.butian.net/Reward/pub
  请求体：ajax=1&name=&p={page}
- 分页策略：data.count 即总页数
- 并发策略：第1页串行获取总数，剩余页多线程并发
"""

import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from app import utils
from .base import BasePlatformAdapter

logger = utils.get_logger()


class BuTianAdapter(BasePlatformAdapter):
    """补天平台适配器"""

    MAX_PAGES = 500
    DEFAULT_CONCURRENCY = 5

    def __init__(self, platform_name="butian", db=None):
        super().__init__(platform_name, db=db)

    # ═══════════════════════════════════════════════════════
    # 项目获取（多线程并发）
    # ═══════════════════════════════════════════════════════

    def fetch_projects(self, max_pages=None, concurrency=None):
        """
        获取补天公益 SRC 厂商列表（POST + 多线程）
        :param max_pages: 最大抓取页数
        :param concurrency: 并发线程数
        :return: 项目列表
        """
        concurrency = concurrency or self.DEFAULT_CONCURRENCY
        max_pages = min(max_pages or self.MAX_PAGES, self.MAX_PAGES)

        # 确保 Cookie 有效
        if self.cookie_mgr:
            if not self.cookie_mgr.ensure_valid(
                    self.config["test_url"], self._login):
                raise RuntimeError("补天 Cookie 维护失败，请手动更新")

        # ── 第 1 页：串行获取总页数 ───────────────────
        first_data = self._fetch_page_json(1)
        if not first_data:
            logger.error("补天首页请求失败")
            return []

        data = first_data.get("data", {})
        total_pages = data.get("count", 0)      # count 即总页数
        first_list = data.get("list", [])

        if not first_list:
            logger.warning("补天第 1 页无数据")
            return []

        total_pages = min(total_pages, max_pages)
        logger.info(
            "补天共 {} 页，每页 {} 条，并发数 {}，预计抓取 {} 页".format(
                total_pages, len(first_list), concurrency, total_pages))

        # ── 线程安全容器 ──────────────────────────────
        projects = []
        seen_ids = set()
        seen_lock = threading.Lock()
        progress = {"done": 1, "total": total_pages}
        progress_lock = threading.Lock()

        # 收集第 1 页
        self._collect_projects(first_list, projects, seen_ids)
        logger.info("第 1/{} 页解析到 {} 个厂商".format(
            total_pages, len(projects)))

        # ── 剩余页并发 ────────────────────────────────
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
        """多线程并发抓取剩余页"""
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
                    logger.error("第 {} 页抓取异常: {}".format(page, e))
                    page_list = []

                if not page_list:
                    logger.warning("第 {} 页无数据".format(page))
                    continue

                with seen_lock:
                    new_count = self._collect_projects(
                        page_list, projects, seen_ids)

                with progress_lock:
                    progress["done"] += 1
                    done = progress["done"]
                    total = progress["total"]

                logger.info(
                    "第 {}/{} 页解析到 {} 个新厂商（累计 {}）".format(
                        done, total, new_count, len(projects)))

    def _fetch_single_page(self, page):
        """单页抓取（供线程池调用）"""
        page_data = self._fetch_page_json(page)
        if not page_data:
            return []
        return page_data.get("data", {}).get("list", [])

    # ═══════════════════════════════════════════════════════
    # 核心请求方法（POST）
    # ═══════════════════════════════════════════════════════

    def _fetch_page_json(self, page):
        """
        请求单页 JSON 数据
        补天 /Reward/pub 接口需要 POST 请求，并携带 ajax=1
        """
        url = "{}/Reward/pub".format(self.config["base_url"])

        # 请求体参数
        data = {
            "ajax": "1",
            "name": "",
            "p": str(page),
        }

        # 额外的请求头
        extra_headers = {
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "{}/Reward/plan".format(
                self.config["base_url"]),
        }

        try:
            resp = self._safe_request(
                url, method="POST", headers=extra_headers, data=data)
        except PermissionError:
            logger.warning("robots.txt 禁止，跳过: {}".format(url))
            return None
        except Exception as e:
            logger.error("请求失败 [{}]: {}".format(url, e))
            return None

        # Cookie 失效处理
        if resp.status_code in (301, 302):
            logger.warning("Cookie 失效，触发刷新")
            if self.cookie_mgr:
                if not self.cookie_mgr.ensure_valid(
                        self.config["test_url"], self._login):
                    logger.error("Cookie 刷新失败")
                    return None
                try:
                    resp = self._safe_request(
                        url, method="POST",
                        headers=extra_headers, data=data)
                except Exception as e:
                    logger.error("重试失败: {}".format(e))
                    return None

        if resp.status_code != 200:
            logger.warning("HTTP {}: {}".format(
                resp.status_code, url))
            return None

        # 解析 JSON
        try:
            result = resp.json()
        except Exception as e:
            logger.error("JSON 解析失败 [{}]: {}".format(url, e))
            return None

        if result.get("status") != 1:
            logger.warning("补天接口异常: status={}, info={}".format(
                result.get("status"), result.get("info")))
            return None

        return result

    # ═══════════════════════════════════════════════════════
    # 解析与去重
    # ═══════════════════════════════════════════════════════

    def _collect_projects(self, items, projects, seen_ids):
        """从 list 中解析项目并合并（调用方需加锁）"""
        new_count = 0
        for item in items:
            company_id = str(item.get("company_id", "")).strip()
            company_name = (item.get("company_name") or "").strip()

            if not company_id:
                continue
            if company_id in seen_ids:
                continue

            seen_ids.add(company_id)
            projects.append({
                "project_id": company_id,
                "project_name": company_name or "补天项目-{}".format(
                    company_id),
                "scope": [],
                "platform": "butian",
                "avatar": item.get("avatar", ""),
            })
            new_count += 1
        return new_count

    # ═══════════════════════════════════════════════════════
    # 项目范围获取
    # ═══════════════════════════════════════════════════════

    def fetch_scope(self, project_id):
        """获取补天项目测试范围"""
        url = "{}/Reward/plan/{}".format(
            self.config["base_url"], project_id)
        try:
            resp = self._safe_request(url)
            if resp.status_code != 200:
                logger.warning("项目 {} 详情页返回 {}".format(
                    project_id, resp.status_code))
                return []
            return self._extract_scope(resp.text)
        except Exception as e:
            logger.error("获取补天项目范围失败 [{}]: {}".format(
                project_id, e))
            return []

    # ═══════════════════════════════════════════════════════
    # 漏洞提交
    # ═══════════════════════════════════════════════════════

    def submit_vulnerability(self, vuln_data):
        logger.info("补天提交漏洞: {} @ {}".format(
            vuln_data.get("title", "N/A"),
            vuln_data.get("target_url", "N/A")))
        return {
            "success": False,
            "platform_vuln_id": None,
            "message": "补天提交需处理极验滑块，请配置后启用",
        }

    # ═══════════════════════════════════════════════════════
    # 辅助方法
    # ═══════════════════════════════════════════════════════

    def _login(self):
        logger.warning(
            "补天未实现自动登录，请手动更新 "
            "config.py 中 butian.cookie 字段")
        return ""

    def _extract_scope(self, html):
        """从详情页 HTML 提取测试范围"""
        import re
        scope = set()

        domain_pattern = re.compile(
            r'(?:域名|目标|范围|资产)[：:\s]*'
            r'([a-zA-Z0-9*][a-zA-Z0-9*.-]*\.[a-zA-Z]{2,})',
            re.IGNORECASE
        )
        for match in domain_pattern.finditer(html):
            scope.add(match.group(1).strip().lower())

        ip_pattern = re.compile(r'\b((?:\d{1,3}\.){3}\d{1,3})\b')
        for match in ip_pattern.finditer(html):
            scope.add(match.group(1))

        cidr_pattern = re.compile(
            r'\b((?:\d{1,3}\.){3}\d{1,3}/\d{1,2})\b')
        for match in cidr_pattern.finditer(html):
            scope.add(match.group(1))

        return sorted(scope)