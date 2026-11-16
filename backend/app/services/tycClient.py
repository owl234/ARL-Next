import base64
from datetime import datetime, timezone, timedelta
import json
import requests
import time
from urllib.parse import urljoin
from app.config import Config
import logging

logger = logging.getLogger(__name__)

class TycException(Exception):
    pass

class TycTokenExpiredException(TycException):
    pass

class TycRiskControlException(TycException):
    pass

class TycBannedLocationException(TycException):
    pass

class TycClient:
    def __init__(self):
        self.gid = Config.TYC_ID
        self.token = Config.TYC_TOKEN
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

    @staticmethod
    def _get_proxies(target_url=None):
        try:
            from app.services.proxy_service import resolve_requests_proxies
            proxies = resolve_requests_proxies(target_url=target_url, domain="osint")
            if proxies:
                return proxies
        except Exception:
            pass
        proxy_url = str(getattr(Config, "PROXY_URL", "") or "").strip()
        if not proxy_url:
            return None
        if "://" not in proxy_url:
            proxy_url = f"http://{proxy_url}"
        return {"http": proxy_url, "https": proxy_url}

    def _request(self, method, path, json_data=None, params=None):
        if not self.gid or not self.token:
            raise TycException("未配置天眼查 ID 或 Token，请在系统设置 -> 三方API配置中完善信息。")

        url = urljoin(self.base_url, path)
        try:
            from app.services.proxy_service import (
                mask_proxy_url_secret,
                record_osint_exit_event,
                resolve_proxy_candidates,
            )
            candidates = resolve_proxy_candidates(domain="osint", target_url=url)
        except Exception:
            mask_proxy_url_secret = None
            record_osint_exit_event = None
            fallback = self._get_proxies(url)
            candidates = [fallback.get("https") if isinstance(fallback, dict) else None]

        if not candidates:
            candidates = [None]

        for idx, candidate_proxy in enumerate(candidates):
            has_next = idx + 1 < len(candidates)
            proxies = {"http": candidate_proxy, "https": candidate_proxy} if candidate_proxy else None
            exit_label = (
                mask_proxy_url_secret(candidate_proxy)
                if (candidate_proxy and mask_proxy_url_secret)
                else ("DIRECT" if not candidate_proxy else candidate_proxy)
            )
            try:
                if method.upper() == 'POST':
                    res = requests.post(url, headers=self.headers, json=json_data, timeout=15, proxies=proxies)
                else:
                    res = requests.get(url, headers=self.headers, params=params, timeout=15, proxies=proxies)
            except requests.exceptions.Timeout:
                if record_osint_exit_event:
                    record_osint_exit_event(candidate_proxy, blocked=True, cooldown_sec=60, reason="天眼查 API 请求超时")
                if has_next:
                    logger.warning("TycClient exit [%s] timeout, failing over to next exit", exit_label)
                    continue
                raise TycException("天眼查 API 请求超时")
            except requests.exceptions.RequestException as e:
                if record_osint_exit_event:
                    record_osint_exit_event(candidate_proxy, blocked=True, cooldown_sec=60, reason=f"网络异常: {type(e).__name__}")
                if has_next:
                    logger.warning("TycClient exit [%s] request error (%s), failing over to next exit", exit_label, type(e).__name__)
                    continue
                raise TycException(f"网络异常: {e}")

            body_text = res.text or ""
            if res.status_code == 401:
                raise TycTokenExpiredException("TYC Token 已失效，请在系统设置中更新。")
            elif res.status_code == 419 or "bannedLocation" in body_text or "301000" in body_text:
                if record_osint_exit_event:
                    record_osint_exit_event(candidate_proxy, blocked=True, cooldown_sec=300, reason="天眼查地域围栏拦截 (419 bannedLocation)")
                if has_next:
                    logger.warning("TycClient exit [%s] hit bannedLocation, failing over to next exit", exit_label)
                    continue
                raise TycBannedLocationException(
                    "当前服务器出口 IP 非中国大陆地区，已被天眼查地域围栏拦截 (bannedLocation)，"
                    "请在「系统设置 -> 代理与出口策略」中配置中国大陆境内代理。"
                )
            elif res.status_code in [403, 429]:
                raise TycRiskControlException("触发天眼查风控拦截或限流，请更换 Token 或稍后再试。")
            elif res.status_code != 200:
                raise TycException(f"天眼查 API 请求失败, HTTP {res.status_code}, {body_text[:100]}")

            try:
                data = res.json()
            except ValueError:
                raise TycException("天眼查 API 返回非预期的数据格式（非 JSON）")

            if isinstance(data, dict) and (
                str(data.get("message", "")) == "bannedLocation" or str(data.get("errorCode", "")) == "301000"
            ):
                if record_osint_exit_event:
                    record_osint_exit_event(candidate_proxy, blocked=True, cooldown_sec=300, reason="天眼查地域围栏拦截 (bannedLocation)")
                if has_next:
                    logger.warning("TycClient exit [%s] JSON bannedLocation, failing over to next exit", exit_label)
                    continue
                raise TycBannedLocationException(
                    "当前服务器出口 IP 非中国大陆地区，已被天眼查地域围栏拦截 (bannedLocation)，"
                    "请在「系统设置 -> 代理与出口策略」中配置中国大陆境内代理。"
                )

            if isinstance(data, dict):
                state = str(data.get("state", "")).lower()
                message = str(data.get("message", ""))
                if state and state != "ok" and not any(h in message for h in ("无数据", "未找到", "为空")):
                    if any(k in message for k in ("请登录", "未登录", "登录失效", "登录")):
                        raise TycTokenExpiredException(f"TYC Token 已失效或未登录: {message}")
                    if any(k in message for k in ("频繁", "验证码", "机器人", "操作过快")):
                        raise TycRiskControlException(f"触发天眼查风控拦截: {message}")

            if record_osint_exit_event:
                record_osint_exit_event(candidate_proxy, blocked=False)

            if 'data' not in data:
                return None

            return data.get('data')

        raise TycException("天眼查 API 所有候选出口均请求失败")

    def fetch_all_pages(self, method, path, total_key, list_key, gid_field="gid", gid_val=None, extra_payload=None, delay=1.5):
        """
        通用分页抓取逻辑
        total_key: 响应中表示总数的键名 (如 total, viewtotal, itemTotal, count)
        list_key: 响应中包含数据列表的键名 (如 result, items, item, miniProgramIcpRecordList, resultList)
        """
        results = []
        page_num = 1

        while True:
            params = None
            json_data = None

            payload = {
                "pageSize": self.page_size,
                "pageNum": page_num
            }

            payload[gid_field] = gid_val

            if extra_payload:
                payload.update(extra_payload)

            if method.upper() == 'POST':
                json_data = payload
            else:
                params = payload

            try:
                data = self._request(method, path, json_data=json_data, params=params)
            except TycException as e:
                # 遇到风控、过期、或者配置错误，直接向上抛出
                raise e
            except Exception as e:
                logger.error(f"分页获取失败 (页码: {page_num}): {e}")
                break

            if not data:
                break

            # 获取列表数据
            items = data.get(list_key, [])
            if not items:
                break

            results.extend(items)

            # 获取总数
            total = data.get(total_key, 0)

            if len(results) >= total:
                break

            page_num += 1
            # 延时防风控
            time.sleep(delay)

        return results

    # ================= 各类资产查询接口 =================

    def get_invest_list(self, gid):
        """对外投资"""
        extra = {
            "benefitSharesType": 1,
            "percentLevel": "-100",
            "registation": "-100",
            "province": "-100",
            "category": "-100",
            "fullSearchText": ""
        }
        return self.fetch_all_pages("POST", "/cloud-company-background/company/investListV2",
                                  total_key="total", list_key="result", gid_field="gid", gid_val=gid, extra_payload=extra)

    def get_icp_record_list(self, gid):
        """备案网站"""
        return self.fetch_all_pages("GET", "/cloud-intellectual-property/intellectualProperty/icpRecordList",
                                  total_key="itemTotal", list_key="item", gid_field="id", gid_val=gid)

    def get_mini_program_list(self, gid):
        """小程序备案"""
        return self.fetch_all_pages("GET", "/cloud-intellectual-property/intellectualProperty/miniProgramIcpRecordList",
                                  total_key="itemTotal", list_key="miniProgramIcpRecordList", gid_field="gid", gid_val=gid)

    def get_app_list(self, gid):
        """APP (原版)"""
        return self.fetch_all_pages("GET", "/cloud-business-state/v3/ar/appbkinfo",
                                  total_key="count", list_key="items", gid_field="id", gid_val=gid)

    def get_app_icp_record_list(self, gid):
        """APP (新版 ICP 备案)"""
        return self.fetch_all_pages("GET", "/cloud-intellectual-property/intellectualProperty/appIcpRecordList",
                                  total_key="itemTotal", list_key="appIcpRecordList", gid_field="gid", gid_val=gid)

    def get_wechat_list(self, gid):
        """微信公众号"""
        return self.fetch_all_pages("GET", "/cloud-business-state/wechat/list",
                                  total_key="count", list_key="resultList", gid_field="graphId", gid_val=gid)

    def get_weibo_list(self, gid):
        """微博"""
        return self.fetch_all_pages("GET", "/cloud-business-state/weibo/list",
                                  total_key="total", list_key="result", gid_field="graphId", gid_val=gid)

    @staticmethod
    def _inspect_jwt_expiry(token):
        raw = str(token or "").strip()
        parts = raw.split(".")
        if len(parts) != 3:
            return None
        try:
            payload_b64 = parts[1] + "=" * (-len(parts[1]) % 4)
            payload = json.loads(base64.urlsafe_b64decode(payload_b64.encode("ascii")).decode("utf-8"))
            exp = payload.get("exp")
            if isinstance(exp, (int, float)):
                return float(exp)
        except Exception:
            pass
        return None

    def check_token_detail(self):
        """
        校验天眼查 ID 与 Token 是否有效，并返回结构化错误分类
        返回: (valid: bool, message: str, error_type: str)
        """
        if not self.gid or not self.token:
            return False, "未配置天眼查 ID 或 Token，请在系统设置 -> 三方API配置中完善信息。", "unconfigured"

        exp_ts = self._inspect_jwt_expiry(self.token)
        if exp_ts is not None and exp_ts <= time.time():
            tz = timezone(timedelta(hours=8))
            expired_at = datetime.fromtimestamp(exp_ts, tz=tz).strftime("%Y-%m-%d %H:%M:%S")
            return False, f"TYC Token 已于 {expired_at} 过期（第 2 页起将被要求登录），请在系统设置中更新。", "token_expired"

        path = "/cloud-business-state/weibo/list"
        params = {
            "pageSize": 1,
            "pageNum": 1,
            "graphId": self.gid
        }
        try:
            self._request("GET", path, params=params)
            return True, "天眼查 ID & Token 校验成功，有效", ""
        except TycBannedLocationException as e:
            return False, str(e), "banned_location"
        except TycTokenExpiredException as e:
            return False, str(e), "token_expired"
        except TycRiskControlException as e:
            return False, str(e), "risk_control"
        except TycException as e:
            return False, f"天眼查 API 异常: {e}", "api_error"
        except Exception as e:
            return False, f"天眼查连接异常: {e}", "network_error"

    def check_token(self):
        """
        校验天眼查 ID 与 Token 是否有效
        通过发送一个最简请求来检测
        """
        valid, msg, _ = self.check_token_detail()
        return valid, msg

    def get_company_name(self, gid):
        """
        根据 GID 定向提取企业官方工商全称 (同步版)
        优先调用 /biz-service/cloud-other-information/companyinfo/companyPhoneList
        兜底尝试从备案网站/小程序中反向提取主体名称
        """
        if not gid:
            return ""
        try:
            path = "/biz-service/cloud-other-information/companyinfo/companyPhoneList"
            data = self._request("GET", path, params={"gid": str(gid)})
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

        try:
            web_records = self.get_icp_record_list(gid)
            if web_records:
                for item in web_records:
                    cn = item.get('companyName') or item.get('unitName')
                    if cn and isinstance(cn, str) and len(cn.strip()) > 3:
                        return cn.strip()
        except Exception as e:
            logger.warning(f"Fallback icpRecordList for GID {gid} failed: {e}")

        return ""

    def search_suggest(self, keyword):
        """
        根据企业关键词定向检索匹配官方天眼查企业 (返回包含 GID 和官方公司全称的首选结果)
        POST /cloud-tempest/search/suggest/v3
        Payload: {"keyword": keyword}
        """
        if not keyword or not str(keyword).strip():
            return None
        keyword = str(keyword).strip()
        path = "/cloud-tempest/search/suggest/v3"
        try:
            data = self._request("POST", path, json_data={"keyword": keyword})
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
            logger.warning(f"Failed to search_suggest for {keyword}: {e}")
        return None
