import requests
import json
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
            "Content-Type": "application/json"
        }
        self.page_size = 100

    def _request(self, method, path, json_data=None, params=None):
        if not self.gid or not self.token:
            raise TycException("未配置天眼查 ID 或 Token，请在系统设置 -> 三方API配置中完善信息。")

        url = urljoin(self.base_url, path)
        try:
            if method.upper() == 'POST':
                res = requests.post(url, headers=self.headers, json=json_data, timeout=15)
            else:
                res = requests.get(url, headers=self.headers, params=params, timeout=15)
        except requests.exceptions.Timeout:
            raise TycException("天眼查 API 请求超时")
        except requests.exceptions.RequestException as e:
            raise TycException(f"网络异常: {e}")

        if res.status_code == 401:
            raise TycTokenExpiredException("TYC Token 已失效，请在系统设置中更新。")
        elif res.status_code in [403, 429]:
            raise TycRiskControlException("触发天眼查风控拦截或限流，请更换 Token 或稍后再试。")
        elif res.status_code != 200:
            raise TycException(f"天眼查 API 请求失败, HTTP {res.status_code}, {res.text[:100]}")

        try:
            data = res.json()
        except ValueError:
            raise TycException("天眼查 API 返回非预期的数据格式（非 JSON）")

        # 判断天眼查的业务状态码（通常在 data 外部有个 state 字段，但依赖实际返回，暂时仅使用 200 判断）
        if 'data' not in data:
             # 如果接口没有 data，说明无数据或错误
             return None

        return data.get('data')

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
            # 商标接口的页码和分页键名不一样 (ps, pn)
            if "trademarkList" in path:
                payload = {
                    "ps": self.page_size,
                    "pn": page_num
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

    def get_trademark_list(self, gid):
        """商标"""
        extra = {
            "category": "-100",
            "fullSearchText": "",
            "sortField": "",
            "sortType": ""
        }
        return self.fetch_all_pages("POST", "/cloud-intellectual-property/intellectualProperty/trademarkList",
                                  total_key="viewtotal", list_key="items", gid_field="id", gid_val=gid, extra_payload=extra)

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

    def check_token(self):
        """
        校验天眼查 ID 与 Token 是否有效
        通过发送一个最简请求来检测
        """
        if not self.gid or not self.token:
            return False, "未配置天眼查 ID 或 Token，请在系统设置 -> 三方API配置中完善信息。"

        path = "/cloud-business-state/weibo/list"
        params = {
            "pageSize": 1,
            "pageNum": 1,
            "graphId": self.gid
        }
        try:
            self._request("GET", path, params=params)
            return True, "天眼查 ID & Token 校验成功，有效"
        except TycTokenExpiredException as e:
            return False, str(e)
        except TycRiskControlException as e:
            return False, str(e)
        except TycException as e:
            return False, f"天眼查 API 异常: {e}"
        except Exception as e:
            return False, f"天眼查连接异常: {e}"

