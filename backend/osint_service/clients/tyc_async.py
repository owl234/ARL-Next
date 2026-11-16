import aiohttp
import asyncio
import base64
from datetime import datetime, timezone, timedelta
import inspect
import json
import logging
import math
import time
from urllib.parse import urljoin

try:
    from load_config import config
    from proxy_router import (
        DIRECT_EXIT_ID,
        ExitCandidate,
        OsintProxyRouter,
        build_aiohttp_connector,
        extract_proxy_ip,
        mask_proxy_url_secret,
        normalize_proxy_url,
    )
except ImportError:
    from ..load_config import config
    from ..proxy_router import (
        DIRECT_EXIT_ID,
        ExitCandidate,
        OsintProxyRouter,
        build_aiohttp_connector,
        extract_proxy_ip,
        mask_proxy_url_secret,
        normalize_proxy_url,
    )

logger = logging.getLogger(__name__)


class AsyncTycException(Exception):
    pass


class TycAuthRequiredError(AsyncTycException):
    """天眼查 Token 失效或命中强制登录拦截（不可通过短暂等待自愈）。"""
    pass


def inspect_tyc_token(token):
    """解析 JWT 格式 tyc_token 的 exp 字段，返回轻量校验摘要（非 JWT 凭据视为不校验过期）。"""
    raw = str(token or "").strip()
    if not raw:
        return {"is_jwt": False, "valid": False, "expired": False, "exp": None, "expired_at": ""}
    parts = raw.split(".")
    if len(parts) != 3:
        return {"is_jwt": False, "valid": True, "expired": False, "exp": None, "expired_at": ""}
    try:
        payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8"))
        exp = payload.get("exp")
        if isinstance(exp, (int, float)):
            exp_ts = float(exp)
            tz = timezone(timedelta(hours=8))
            expired_at = datetime.fromtimestamp(exp_ts, tz=tz).strftime("%Y-%m-%d %H:%M:%S")
            now_ts = time.time()
            return {
                "is_jwt": True,
                "valid": exp_ts > now_ts,
                "expired": exp_ts <= now_ts,
                "exp": exp_ts,
                "expired_at": expired_at,
            }
    except Exception:
        pass
    return {"is_jwt": False, "valid": True, "expired": False, "exp": None, "expired_at": ""}


class AsyncTycClient:
    def __init__(self, gid, token, proxy=None, proxy_router=None):
        self.gid = gid
        self.token = token
        self.proxy = self._normalize_proxy(proxy)
        self.proxy_router = proxy_router or OsintProxyRouter(legacy_proxy=self.proxy)
        self.base_url = "https://capi.tianyancha.com"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:152.0) Gecko/20100101 Firefox/152.0",
            "Version": "TYC-Web",
            "X-Tycid": self.gid,
            "X-Auth-Token": self.token,
            "Content-Type": "application/json",
            "Origin": "https://www.tianyancha.com",
            "Referer": "https://www.tianyancha.com/"
        }
        self.page_size = 100
        self._progress_cb = None
        self._should_stop_cb = None
        self._issue_cb = None
        self._fetch_issues = []

    def inspect_token_status(self):
        return inspect_tyc_token(self.token)

    def attach_task_hooks(self, *, progress_cb=None, should_stop_cb=None, issue_cb=None):
        """挂载 TYC 分页进度日志、协同终止与异常截断回调"""
        self._progress_cb = progress_cb
        self._should_stop_cb = should_stop_cb
        self._issue_cb = issue_cb

    def consume_fetch_issues(self):
        issues = list(self._fetch_issues)
        self._fetch_issues.clear()
        return issues

    async def _emit_issue(self, scene_label, issue):
        self._fetch_issues.append(issue)
        if self._issue_cb is None:
            return
        try:
            res = self._issue_cb(scene_label, issue)
            if inspect.isawaitable(res):
                await res
        except Exception as e:
            logger.warning(f"TYC 异常回调执行失败: {e}")

    def _get_system_int_config(self, key, default):
        val = getattr(getattr(config, "system", object()), key, None)
        if val is None or val == "":
            return default
        try:
            return int(val)
        except (TypeError, ValueError):
            return default

    async def _emit_progress(self, scene_label, message):
        if self._progress_cb is None:
            return
        try:
            res = self._progress_cb(scene_label, message)
            if inspect.isawaitable(res):
                await res
        except Exception as e:
            logger.warning(f"TYC 进度回调执行异常: {e}")

    async def _check_should_stop(self):
        if self._should_stop_cb is None:
            return False
        try:
            res = self._should_stop_cb()
            if inspect.isawaitable(res):
                return bool(await res)
            return bool(res)
        except Exception as e:
            logger.warning(f"TYC 停止检查回调异常: {e}")
            return False

    @staticmethod
    def _normalize_proxy(proxy):
        return normalize_proxy_url(proxy)

    def _get_candidates(self):
        if self.proxy_router and self.proxy_router.has_structured_policy:
            cands = self.proxy_router.get_candidates()
            if cands:
                return cands
            # 若天眼查出口全部短期标记冷却，兜底保留主直连+绑定备机让调用方做最后一次尝试并吐出明确提示
            allowed = self.proxy_router._all_allowed_exits()
            if allowed:
                return allowed
        if self.proxy:
            ip = extract_proxy_ip(self.proxy) or self.proxy
            return [ExitCandidate(
                exit_id=f"explicit:{ip}",
                name=mask_proxy_url_secret(self.proxy),
                proxy_url=self.proxy,
                ip=ip,
            )]
        return [ExitCandidate(exit_id=DIRECT_EXIT_ID, name="主服务器直连", proxy_url=None, ip="")]

    async def _request(self, method, path, json_data=None, params=None, max_retries=3):
        import random
        await asyncio.sleep(random.uniform(5, 10))
        if not self.gid or not self.token:
            raise AsyncTycException("未配置天眼查 ID 或 Token。")

        url = urljoin(self.base_url, path)
        candidates = self._get_candidates()

        for cand_idx, cand in enumerate(candidates):
            has_next_cand = cand_idx + 1 < len(candidates)
            next_cand = candidates[cand_idx + 1] if has_next_cand else None
            connector, req_proxy = build_aiohttp_connector(cand.proxy_url, connector_config={"ssl": False})
            try:
                async with aiohttp.ClientSession(connector=connector) as session:
                    for attempt in range(max_retries):
                        try:
                            if method.upper() == 'POST':
                                async with session.post(url, headers=self.headers, json=json_data, timeout=15, proxy=req_proxy) as res:
                                    status = res.status
                                    text = await res.text()
                                    data = await res.json() if "application/json" in res.headers.get("Content-Type", "") else None
                            else:
                                async with session.get(url, headers=self.headers, params=params, timeout=15, proxy=req_proxy) as res:
                                    status = res.status
                                    text = await res.text()
                                    data = await res.json() if "application/json" in res.headers.get("Content-Type", "") else None
                        except asyncio.TimeoutError:
                            if attempt < max_retries - 1:
                                await asyncio.sleep(5 * (attempt + 1))
                                continue
                            if has_next_cand and self.proxy_router:
                                self.proxy_router.mark_exit_blocked(cand.exit_id, reason="天眼查 API 请求超时", ip=cand.ip, cooldown_sec=60)
                                await self.proxy_router.persist_runtime_status()
                                await self.proxy_router.emit_syslog(
                                    "warning", "天眼查出口切换",
                                    f"出口 [{cand.name}] 请求天眼查超时，已隔离 60s 并切换至 [{next_cand.name}] 重试"
                                )
                                break
                            raise AsyncTycException("天眼查 API 请求超时")
                        except Exception as e:
                            if attempt < max_retries - 1:
                                await asyncio.sleep(5 * (attempt + 1))
                                continue
                            if has_next_cand and self.proxy_router:
                                self.proxy_router.mark_exit_blocked(cand.exit_id, reason=f"天眼查连接异常 ({type(e).__name__})", ip=cand.ip, cooldown_sec=60)
                                await self.proxy_router.persist_runtime_status()
                                await self.proxy_router.emit_syslog(
                                    "warning", "天眼查出口切换",
                                    f"出口 [{cand.name}] 连接天眼查异常 ({type(e).__name__})，已切换至 [{next_cand.name}] 重试"
                                )
                                break
                            raise AsyncTycException(f"网络异常: {e}")

                        body_text = text or ""
                        if status == 401:
                            raise TycAuthRequiredError("TYC Token 已失效 (HTTP 401)")
                        elif status == 419 or "bannedLocation" in body_text or "301000" in body_text:
                            if self.proxy_router:
                                self.proxy_router.mark_exit_blocked(
                                    cand.exit_id,
                                    reason="天眼查地域围栏拦截 (419 bannedLocation)",
                                    ip=cand.ip,
                                    cooldown_sec=300,
                                )
                                await self.proxy_router.persist_runtime_status()
                            if has_next_cand:
                                if self.proxy_router:
                                    await self.proxy_router.emit_syslog(
                                        "warning", "天眼查出口切换",
                                        f"出口 [{cand.name}] 触发天眼查地域围栏 (419 bannedLocation)，已切换至 [{next_cand.name}] 重试"
                                    )
                                break
                            raise AsyncTycException(
                                "当前服务器出口 IP 非中国大陆地区，已被天眼查地域围栏拦截 (bannedLocation)，"
                                "请在「系统设置 -> 代理与出口策略」中配置中国大陆境内代理。"
                            )
                        elif status in [403, 429]:
                            if attempt < max_retries - 1:
                                logger.warning(f"触发限流(HTTP {status})，挂起 {15 * (attempt + 1)} 秒后重试 (Attempt {attempt+1}/{max_retries})...")
                                await asyncio.sleep(15 * (attempt + 1))
                                continue
                            raise AsyncTycException("触发天眼查风控拦截或限流。")
                        elif status != 200:
                            raise AsyncTycException(f"天眼查 API 请求失败, HTTP {status}, {body_text[:100]}")

                        if not data:
                            if self.proxy_router:
                                self.proxy_router.mark_exit_active(cand.exit_id)
                            return None

                        state = str(data.get("state", "")).lower()
                        message = str(data.get("message", ""))
                        error_code = str(data.get("errorCode", ""))
                        if message == "bannedLocation" or error_code == "301000":
                            if self.proxy_router:
                                self.proxy_router.mark_exit_blocked(
                                    cand.exit_id,
                                    reason="天眼查地域围栏拦截 (bannedLocation)",
                                    ip=cand.ip,
                                    cooldown_sec=300,
                                )
                                await self.proxy_router.persist_runtime_status()
                            if has_next_cand:
                                if self.proxy_router:
                                    await self.proxy_router.emit_syslog(
                                        "warning", "天眼查出口切换",
                                        f"出口 [{cand.name}] 触发天眼查地域围栏 (bannedLocation)，已切换至 [{next_cand.name}] 重试"
                                    )
                                break
                            raise AsyncTycException(
                                "当前服务器出口 IP 非中国大陆地区，已被天眼查地域围栏拦截 (bannedLocation)，"
                                "请在「系统设置 -> 代理与出口策略」中配置中国大陆境内代理。"
                            )

                        # 1. 过滤正常的无数据场景
                        if "无数据" in message or "未找到" in message or "为空" in message:
                            if self.proxy_router:
                                self.proxy_router.mark_exit_active(cand.exit_id)
                            return None

                        # 2. 精准识别鉴权拦截与可重试风控异常
                        if state != "ok":
                            if any(kw in message for kw in ["请登录", "未登录", "登录失效", "登录已过期", "登录"]):
                                raise TycAuthRequiredError(f"天眼查鉴权拦截: {message}")
                            if any(kw in message for kw in ["频繁", "验证码", "异常", "机器人", "操作过快", "校验"]):
                                if attempt < max_retries - 1:
                                    logger.warning(f"触发风控 ({message})，挂起 {15 * (attempt + 1)} 秒后重试 (Attempt {attempt+1}/{max_retries})...")
                                    await asyncio.sleep(15 * (attempt + 1))
                                    continue
                                raise AsyncTycException(f"触发天眼查风控拦截: {message}")
                            else:
                                raise AsyncTycException(f"天眼查业务异常: state={state}, message={message}")

                        if self.proxy_router:
                            prev = self.proxy_router.active_exit_id
                            self.proxy_router.mark_exit_active(cand.exit_id)
                            if prev != cand.exit_id:
                                await self.proxy_router.persist_runtime_status()

                        if 'data' not in data:
                            return None

                        return data.get('data')
            finally:
                await connector.close()

        raise AsyncTycException("天眼查 API 所有候选出口均请求失败")

    async def fetch_all_pages(self, method, path, total_key, list_key, gid_field="gid", gid_val=None, extra_payload=None, delay=1.5, scene_label="", record_issue=True):
        results = []
        page_num = 1
        expected_total = 0
        page_step = max(1, self._get_system_int_config("progress_log_page_step", 5))
        interval_sec = max(1, self._get_system_int_config("progress_log_interval_sec", 30))
        label = scene_label or "资产"
        last_log_ts = time.monotonic()

        while True:
            if await self._check_should_stop():
                logger.info(f"TYC {label}分页检测到任务停止，提前退出（已完成 {len(results)} 条）")
                break
            params = None
            json_data = None
            payload = {"pageSize": self.page_size, "pageNum": page_num}
            payload[gid_field] = gid_val
            if extra_payload:
                payload.update(extra_payload)
            if method.upper() == 'POST':
                json_data = payload
            else:
                params = payload
            try:
                data = await self._request(method, path, json_data=json_data, params=params)
            except Exception as e:
                logger.error(f"分页获取失败 (页码: {page_num}): {e}")
                if record_issue:
                    await self._emit_issue(label, {
                        "scene": label,
                        "gid": str(gid_val or ""),
                        "page_num": page_num,
                        "fetched": len(results),
                        "expected_total": int(expected_total or 0),
                        "reason": str(e),
                        "auth_required": isinstance(e, TycAuthRequiredError),
                    })
                break
            if not data:
                break
            items = data.get(list_key, [])
            if not items:
                break
            results.extend(items)
            total = data.get(total_key, 0) or 0
            if total and not expected_total:
                expected_total = total
            total_pages = max(1, math.ceil(total / self.page_size)) if total and self.page_size else page_num
            done = len(results) >= total

            now_ts = time.monotonic()
            if page_num == 1 and total_pages > page_step and not done:
                await self._emit_progress(
                    label,
                    f"正在拉取目标 {gid_val} TYC {label}：共 {total} 条（约 {total_pages} 页），第 1/{total_pages} 页，累计 {len(results)} 条",
                )
                last_log_ts = now_ts
            elif page_num > 1 and (
                (total_pages > page_step and (page_num % page_step == 0 or done))
                or (now_ts - last_log_ts >= interval_sec)
            ):
                await self._emit_progress(
                    label,
                    f"正在拉取目标 {gid_val} TYC {label}：第 {page_num}/{total_pages} 页，累计 {len(results)}/{total or len(results)} 条",
                )
                last_log_ts = now_ts

            if done:
                break
            page_num += 1
            if await self._check_should_stop():
                logger.info(f"TYC {label}分页检测到任务停止，提前退出（已完成 {len(results)} 条）")
                break
            await asyncio.sleep(delay)
        return results

    async def get_invest_list(self, gid):
        extra = {"benefitSharesType": 1, "percentLevel": "-100", "registation": "-100", "province": "-100", "category": "-100", "fullSearchText": ""}
        return await self.fetch_all_pages("POST", "/cloud-company-background/company/investListV2", "total", "result", "gid", gid, extra, scene_label="对外投资")

    async def get_icp_record_list(self, gid):
        return await self.fetch_all_pages("GET", "/cloud-intellectual-property/intellectualProperty/icpRecordList", "itemTotal", "item", "id", gid, scene_label="网站备案")

    async def get_mini_program_list(self, gid):
        return await self.fetch_all_pages("GET", "/cloud-intellectual-property/intellectualProperty/miniProgramIcpRecordList", "itemTotal", "miniProgramIcpRecordList", "gid", gid, scene_label="小程序")

    async def get_app_list(self, gid):
        return await self.fetch_all_pages("GET", "/cloud-business-state/v3/ar/appbkinfo", "count", "items", "id", gid, scene_label="APP")

    async def get_app_icp_record_list(self, gid):
        return await self.fetch_all_pages("GET", "/cloud-intellectual-property/intellectualProperty/appIcpRecordList", "itemTotal", "appIcpRecordList", "gid", gid, scene_label="APP备案")

    async def get_wechat_list(self, gid):
        return await self.fetch_all_pages("GET", "/cloud-business-state/wechat/list", "count", "resultList", "graphId", gid, scene_label="微信公众号")

    async def get_weibo_list(self, gid):
        return await self.fetch_all_pages("GET", "/cloud-business-state/weibo/list", "total", "result", "graphId", gid, scene_label="微博")

    async def get_company_name(self, gid):
        """
        根据 GID 定向提取企业官方工商全称
        优先调用 /biz-service/cloud-other-information/companyinfo/companyPhoneList
        兜底尝试从备案网站/小程序中反向提取主体名称
        """
        if not gid:
            return ""
        try:
            # 1. 优先调用年报电话接口（内含法定企业全称）
            path = "/biz-service/cloud-other-information/companyinfo/companyPhoneList"
            data = await self._request("GET", path, params={"gid": str(gid)})
            if data and isinstance(data, dict):
                phone_list = data.get("phoneList") or []
                for p in phone_list:
                    if isinstance(p, dict):
                        cname = p.get("companyName")
                        if cname and isinstance(cname, str) and len(cname.strip()) > 3:
                            return cname.strip()
                claim_info = data.get("claimInfo") or {}
                if isinstance(claim_info, dict):
                    cname = claim_info.get("companyName")
                    if cname and isinstance(cname, str) and len(cname.strip()) > 3:
                        return cname.strip()
        except Exception as e:
            logger.warning(f"Failed to fetch companyPhoneList for GID {gid}: {e}")

        # 2. 兜底策略 1：从网站备案记录中提取主体全称（仅取首条探测，不记录分页截断告警）
        try:
            web_records = await self.fetch_all_pages(
                "GET",
                "/cloud-intellectual-property/intellectualProperty/icpRecordList",
                "itemTotal",
                "item",
                "id",
                gid,
                scene_label="网站备案",
                record_issue=False,
            )
            if web_records:
                for item in web_records:
                    cn = item.get('companyName') or item.get('unitName')
                    if cn and isinstance(cn, str) and len(cn.strip()) > 3:
                        return cn.strip()
        except Exception as e:
            logger.warning(f"Fallback icpRecordList for GID {gid} failed: {e}")

        # 3. 兜底策略 2：从小程序备案记录中提取主体全称
        try:
            mapp_records = await self.fetch_all_pages(
                "GET",
                "/cloud-intellectual-property/intellectualProperty/miniProgramIcpRecordList",
                "itemTotal",
                "miniProgramIcpRecordList",
                "gid",
                gid,
                scene_label="小程序",
                record_issue=False,
            )
            if mapp_records:
                for item in mapp_records:
                    detail = item.get('miniProgramIcpRecordDetail') or {}
                    cn = detail.get('icpFilingSubjectInformation', {}).get('organizingName')
                    if cn and isinstance(cn, str) and len(cn.strip()) > 3:
                        return cn.strip()
        except Exception as e:
            logger.warning(f"Fallback miniProgram list for GID {gid} failed: {e}")

        return ""

    async def search_suggest(self, keyword):
        """
        根据企业关键词定向检索匹配官方天眼查企业 (异步版本)
        POST /cloud-tempest/search/suggest/v3
        Payload: {"keyword": keyword}
        """
        if not keyword or not str(keyword).strip():
            return None
        keyword = str(keyword).strip()
        path = "/cloud-tempest/search/suggest/v3"
        try:
            data = await self._request("POST", path, json_data={"keyword": keyword})
            if data and isinstance(data, list) and len(data) > 0:
                first = data[0]
                gid = str(first.get("id") or first.get("graphId") or "")
                name = first.get("comName") or first.get("name") or ""
                clean_name = name.replace("<em>", "").replace("</em>", "").strip() if name else ""
                if gid:
                    return {
                        "gid": gid,
                        "company_name": clean_name or keyword,
                        "raw": first
                    }
        except Exception as e:
            logger.warning(f"Failed to async search_suggest for {keyword}: {e}")
        return None
