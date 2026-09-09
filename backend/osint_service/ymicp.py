# -*- coding: utf-8 -*-
import asyncio
import aiohttp
import time
import hashlib
import re
import base64
import os
import io
import numpy as np
from PIL import Image
import ujson
import random
import uuid
from aiohttp import TCPConnector
from mlog import logger
import warnings
warnings.filterwarnings("ignore", category=UserWarning)
import ssl
import subprocess
import locale
from contextlib import asynccontextmanager
import threading
from load_config import config
from cachetools import TTLCache
ssl._create_default_https_context = ssl._create_unverified_context()


def is_public_ipv6(ipv6):
    return not (ipv6.startswith("fe80") or ipv6.startswith("fc00") or ipv6.startswith("fd00"))

# 获取本地IPv6地址
def _run_cmd_capture(cmd):
    """执行系统命令并自动多编码尝试解码，失败返回空字符串"""
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate(timeout=5)
    except Exception:
        return ""
    if not out:
        return ""
    enc_candidates = [
        "utf-8",
        locale.getpreferredencoding(False) or "",
        "gbk",
        "cp936",
        "latin-1",
    ]
    for enc in enc_candidates:
        if not enc:
            continue
        try:
            return out.decode(enc)
        except Exception:
            continue
    return out.decode("utf-8", errors="ignore")

def get_local_ipv6_addresses():
    """跨平台获取本机公网IPv6地址，自动处理编码/异常"""
    addresses = []
    try:
        if os.name == 'nt':  # Windows
            output = _run_cmd_capture(["netsh", "interface", "ipv6", "show", "addresses"])
            if not output:
                return []
            for line in output.splitlines():
                line_strip = line.strip()
                # 兼容中文(公用/手动)及可能的英文(Public/Manual)
                if any(k in line_strip for k in ("公用", "手动", "Public", "Manual")) and ":" in line_strip:
                    parts = line_strip.split()
                    candidate = parts[-1]
                    candidate = candidate.strip()
                    # 去除可能的/前缀长度
                    candidate = candidate.split("/")[0]
                    if ":" in candidate and is_public_ipv6(candidate):
                        addresses.append(candidate)
        else:  # Linux / mac
            output = _run_cmd_capture(["ip", "-6", "addr", "show"])
            if not output:
                return []
            for line in output.splitlines():
                line_strip = line.strip()
                if ("inet6" in line_strip) and ("scope global" in line_strip):
                    try:
                        candidate = line_strip.split()[1].split("/")[0]
                        if is_public_ipv6(candidate):
                            addresses.append(candidate)
                    except Exception:
                        continue
    except Exception:
        return []
    # 去重
    return list(dict.fromkeys(addresses))

class beian:
    def __init__(self):
        self.typj = {
            0: ujson.dumps(
                {"pageNum": "", "pageSize": "", "unitName": "", "serviceType": 1}
            ),  # 网站
            1: ujson.dumps(
                {"pageNum": "", "pageSize": "", "unitName": "", "serviceType": 6}
            ),  # APP
            2: ujson.dumps(
                {"pageNum": "", "pageSize": "", "unitName": "", "serviceType": 7}
            ),  # 小程序
            3: ujson.dumps(
                {"pageNum": "", "pageSize": "", "unitName": "", "serviceType": 8}
            ),  # 快应用
        }
        self.btypj = {
            0: ujson.dumps({"domainName": ""}),
            1: ujson.dumps({"serviceName": "", "serviceType": 6}),
            2: ujson.dumps({"serviceName": "", "serviceType": 7}),
            3: ujson.dumps({"serviceName": "", "serviceType": 8}),
        }
        self.session = None
        self.cookie_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.41 Safari/537.36 Edg/101.0.1210.32"
        }
        self.home = "https://beian.miit.gov.cn/"
        self.url = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/auth"
        self.getCheckImage = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/image/getCheckImagePoint"
        self.checkImage = (
            "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/image/checkImage"
        )
        # 正常查询
        self.queryByCondition = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/icpAbbreviateInfo/queryByCondition"
        # 违法违规域名查询
        self.blackqueryByCondition = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/blackListDomain/queryByCondition"
        # 违法违规APP,小程序,快应用
        self.blackappAndMiniByCondition = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/blackListDomain/queryByCondition_appAndMini"
        # APP/小程序/快应用详情查询接口
        self.queryDetailByAppAndMiniId = "https://hlwicpfwc.miit.gov.cn/icpproject_query/api/icpAbbreviateInfo/queryDetailByAppAndMiniId"
        self.sign = "eyJ0eXBlIjozLCJleHREYXRhIjp7InZhZnljb2RlX2ltYWdlX2tleSI6IjUyZWI1ZTcyODViNzRmNWJhM2YwYzBkNTg0YTg3NmVmIn0sImUiOjE3NTY5NzAyNDg4MjN9.Ngpkwn4T7sQoQF9pCk_sQQpH61wQUEKnK2sQ8hDIq-Q"
        self.token = ""
        self.token_expire = 0
        self.timeout = aiohttp.ClientTimeout(total=getattr(getattr(config, 'system', object()), 'http_client_timeout', 30))
        self.local_ipv6_addresses = get_local_ipv6_addresses() if getattr(getattr(getattr(config, 'proxy', object()), 'local_ipv6_pool', object()), 'enable', False) else []
        self.ipv6_index = 0
        
        self._ipv6_lock = threading.Lock()  # IPv6轮询锁
        
        # 连接池配置
        self.connector_config = {
            'limit': 100,
            'limit_per_host': 30,
            'ttl_dns_cache': 300,
            'use_dns_cache': True,
            'ssl': False,
            'keepalive_timeout': 30
        }

        self._blocked_ip_cache = TTLCache(maxsize=1000, ttl=300)
        self._blocked_ip_lock = threading.Lock()

        # WAF 熔断状态挂在实例上：同一任务内 web/app/mapp/kapp 共享，避免换类型就重新撞封禁
        self._waf_block_ts = 0.0
        self.waf_cooldown = 120  # 秒，到期后半开重试详情补全
        self._token_lock = None

    @property
    def token_lock(self):
        """惰性绑定当前事件循环的异步锁，用于 Token 续期 DCL"""
        if self._token_lock is None:
            self._token_lock = asyncio.Lock()
        return self._token_lock

    def _waf_open(self):
        """熔断是否处于开启态（冷却期内不再发起详情请求）"""
        return (time.time() - self._waf_block_ts) < self.waf_cooldown

    def _waf_trip(self, scene):
        """开启熔断，仅在首次触发时打印告警，避免批内刷屏"""
        first_trip = not self._waf_open()
        self._waf_block_ts = time.time()
        if first_trip:
            logger.warning(
                f"{scene}触发创宇盾拦截，启动熔断降级：跳过后续详情请求，冷却 {self.waf_cooldown}s"
            )

    def _session_local_ip(self, session):
        """
        取回本次会话实际绑定的出口地址。
        优先读 get_session 打上的 _arl_local_ip 标记，不依赖 aiohttp 私有属性；
        仅在标记缺失时按版本回退探测（3.9 的 _local_addr / 3.12+ 的 _local_addr_infos）。
        """
        connector = getattr(session, "_connector", None)
        if connector is None:
            return None
        ip = getattr(connector, "_arl_local_ip", None)
        if ip:
            return ip
        addr = getattr(connector, "_local_addr", None) or getattr(connector, "_local_addr_infos", None)
        try:
            if isinstance(addr, (list, tuple)) and addr:
                first = addr[0]
                if isinstance(first, (list, tuple)) and first:
                    return first[-1][0]
                if isinstance(first, str):
                    return first
        except (IndexError, KeyError, TypeError, AttributeError):
            return None
        return None


    def _add_blocked_ip(self, ip):
        """将IP添加到黑名单缓存"""
        if not ip:
            return
        with self._blocked_ip_lock:
            self._blocked_ip_cache[ip] = True
            logger.info(f"IP {ip} 被创宇盾拦截已添加到黑名单缓存，5分钟后恢复使用")

    def _is_ip_blocked(self, ip):
        """检查IP是否在黑名单缓存中"""
        if not ip:
            return False
        with self._blocked_ip_lock:
            return ip in self._blocked_ip_cache
        
    def _get_next_ipv6(self):
        """线程安全的IPv6轮询，跳过被拦截的IP"""
        if not self.local_ipv6_addresses:
            return None
        
        with self._ipv6_lock:
            attempts = 0
            max_attempts = len(self.local_ipv6_addresses) * 2  # 最多尝试两轮
            
            while attempts < max_attempts:
                if self.ipv6_index >= len(self.local_ipv6_addresses):
                    self.ipv6_index = 0
                
                ipv6 = self.local_ipv6_addresses[self.ipv6_index]
                self.ipv6_index += 1
                attempts += 1
                
                # 检查IP是否被拦截
                if not self._is_ip_blocked(ipv6):
                    return ipv6
                else:
                    logger.debug(f"跳过被拦截的IPv6地址: {ipv6}")
            
            logger.warning("所有IPv6地址都被拦截，暂无可用地址")
            return None

    async def _get_connector(self, local_ipv6=None):
        if local_ipv6:
            connector = TCPConnector(
                local_addr=(local_ipv6, 0),
                **self.connector_config
            )
        else:
            connector = TCPConnector(**self.connector_config)
        
        return connector

    @asynccontextmanager
    async def get_session(self, proxy=""):
        local_ipv6 = None
        if not proxy and self.local_ipv6_addresses:
            local_ipv6 = self._get_next_ipv6()
            if local_ipv6:
                logger.info(f"使用本地IPv6地址: {local_ipv6}")
        
        # 为每个session创建独立的连接器
        connector = await self._get_connector(local_ipv6)
        # 标记本会话真实出口地址，供 WAF 拦截时精确归因（跨 aiohttp 版本稳定）
        connector._arl_local_ip = local_ipv6
        
        session = aiohttp.ClientSession(
            timeout=self.timeout,
            connector=connector,
            headers={'Connection': 'keep-alive'}
        )
        
        try:
            yield session
        finally:
            # 确保session和connector都被正确关闭
            await session.close()
            await connector.close()

    async def get_token(self, proxy="", force=False):
        base_header = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/101.0.4951.41 Safari/537.36 Edg/101.0.1210.32",
            "Origin": "https://beian.miit.gov.cn",
            "Referer": "https://beian.miit.gov.cn/",
            "Cookie": f"__jsluid_s={uuid.uuid4().hex}",
            "Accept": "application/json, text/plain, */*",
        }
        
        now_ms = int(time.time() * 1000)
        if not force and (self.token_expire - now_ms > 60000):
            return True, self.token, base_header

        if not hasattr(self, '_token_async_lock'):
            self._token_async_lock = asyncio.Lock()

        async with self._token_async_lock:
            now_ms = int(time.time() * 1000)
            if not force and (self.token_expire - now_ms > 60000):
                return True, self.token, base_header

            timeStamp = round(time.time() * 1000)
            authSecret = "testtest" + str(timeStamp)
            authKey = hashlib.md5(authSecret.encode(encoding="UTF-8")).hexdigest()
            auth_data = {"authKey": authKey, "timeStamp": timeStamp}
            
            try:
                async with self.get_session(proxy) as session:
                    current_ip = self._session_local_ip(session)
                    async with session.post(self.url, data=auth_data, headers=base_header, proxy=proxy if proxy else None) as req:
                        req_text = await req.text()

                if "当前访问疑似黑客攻击" in req_text:
                    if current_ip:
                        self._add_blocked_ip(current_ip)
                    else:
                        # 无法定位真实出口地址时不做索引猜测：并发下 ipv6_index 已被其它协程推进，
                        # 按 index-1 归因会误封健康 IP，交由 _arl_local_ip 精确标记处理
                        logger.warning("WAF 拦截但未能定位出口地址，跳过黑名单写入")
                    return False, "当前访问已被创宇盾拦截", ""

                t = ujson.loads(req_text)
                token = t["params"]["bussiness"]
                expire = int(time.time() * 1000) + t["params"]["expire"]

                self.token = token
                self.token_expire = expire

                return True, token, base_header
            except Exception as e:
                logger.warning(f"get_token Faile : {e}")
                return False, str(e), ""

    async def get_cookie(self, proxy=""):
        async with await self.get_session(proxy) as session:
            async with session.get(self.home, headers=self.cookie_headers, proxy=proxy if proxy else None) as req:
                await req.text()
                return re.compile("[0-9a-z]{32}").search(str(req.cookies))[0]

    def get_clientUid(self):
        characters = "0123456789abcdef"
        unique_id = ["0"] * 36

        for i in range(36):
            unique_id[i] = random.choice(characters)

        unique_id[14] = "4"
        unique_id[19] = characters[(3 & int(unique_id[19], 16)) | 8]
        unique_id[8] = unique_id[13] = unique_id[18] = unique_id[23] = "-"

        point_id = "point-" + "".join(unique_id)

        return ujson.dumps({"clientUid": point_id})

    def match_slider_offset(self, small_image_b64, big_image_b64):
        """在大图上找与滑块同尺寸的纯色正方形缺口区域，返回其 x 偏移量"""
        big_img = np.array(Image.open(io.BytesIO(base64.b64decode(big_image_b64))).convert("RGB"))
        small_img = np.array(Image.open(io.BytesIO(base64.b64decode(small_image_b64))))
        sh, sw = small_img.shape[:2]

        # 缩小到一半
        resized = big_img[::2, ::2]
        h, w = resized.shape[:2]
        min_side = int(min(sw, sh) * 0.5 * 0.5)

        # 量化颜色，编码为单通道整数
        q = (resized.astype(np.int32) // 4) * 4
        color_id = q[:, :, 0] + q[:, :, 1] * 256 + q[:, :, 2] * 65536

        # 找出现次数最多的几个颜色（缺口灰色通常是高频色之一）
        flat_colors = color_id.ravel()
        unique, counts = np.unique(flat_colors, return_counts=True)
        # 只检查出现次数前 5 的颜色
        top_indices = np.argsort(counts)[-5:]

        best_area = 0
        best_x = 0

        for idx in top_indices:
            c = unique[idx]
            mask = color_id == c
            # 对每行求该颜色的连续像素数，利用列方向累积
            # 列投影：每列有多少连续行是该颜色
            col_run = np.zeros((h, w), dtype=np.int32)
            col_run[0] = mask[0].astype(np.int32)
            for y in range(1, h):
                col_run[y] = np.where(mask[y], col_run[y - 1] + 1, 0)

            # 对每行找符合高度条件的列段的最大宽度
            for y in range(min_side, h):
                row = col_run[y] >= min_side
                if not np.any(row):
                    continue
                # 找连续 True 段
                d = np.diff(row.astype(np.int8))
                starts = np.where(d == 1)[0] + 1
                ends = np.where(d == -1)[0] + 1
                if row[0]:
                    starts = np.concatenate([[0], starts])
                if row[-1]:
                    ends = np.concatenate([ends, [w]])
                for s, e in zip(starts, ends):
                    run_w = e - s
                    if s <= sw // 4:
                        continue
                    run_h = int(col_run[y, s])
                    ratio = run_w / run_h if run_h > 0 else 0
                    if 0.7 < ratio < 1.4 and run_w * run_h > best_area:
                        best_area = run_w * run_h
                        best_x = s

        if best_area == 0:
            return False, "未找到缺口"

        offset_x = best_x * 2
        logger.info(f"缺口定位: x={offset_x}, 滑块={sw}x{sh}")
        return True, offset_x

    async def check_img(self, proxy=""):
        success, token, base_header = await self.get_token(proxy)
        if not success:
            logger.info(f"获取token失败：{token}")
            return False, token, '', '', ''
        try:
            data = self.get_clientUid()
            length = str(len(str(data).encode("utf-8")))
            base_header.update({"Content-Length": length, "token": token})
            base_header["Content-Type"] = "application/json"
            try:
                async with self.get_session(proxy) as session:
                    async with session.post(self.getCheckImage, data=data, headers=base_header, proxy=proxy if proxy else None) as req:
                        res = await req.json()
            except Exception as e:
                logger.info(f"请求验证码时失败：{e}")
                return False, f"请求验证码时失败：{e}", '', '', ''

            p_uuid = res["params"]["uuid"]
            big_image = res["params"]["bigImage"]
            small_image = res["params"]["smallImage"]

            start = time.time()
            match_success, offset_x = self.match_slider_offset(small_image, big_image)
            if not match_success:
                logger.info(f"滑块匹配失败：{offset_x}")
                return False, "滑块匹配失败", '', '', ''
            logger.info(f"滑块匹配用时 {time.time() - start:.4f}s")

            check_data = ujson.dumps({"key": p_uuid, "value": str(offset_x)})
            logger.info(f"checkImage 请求体: {check_data}")
            length = str(len(check_data.encode("utf-8")))
            base_header.update({"Content-Length": length})
            async with self.get_session(proxy) as session:
                async with session.post(self.checkImage, data=check_data, headers=base_header, proxy=proxy if proxy else None) as req:
                    res = await req.text()

            data = ujson.loads(res)
            logger.info(f"checkImage 响应: code={data.get('code')}, msg={data.get('msg')}, success={data.get('success')}")
            if not data.get("success", False):
                captcha_config = getattr(config, 'captcha', object())
                if getattr(captcha_config, 'save_failed_img', False):
                    save_path = getattr(captcha_config, 'save_failed_img_path', './failed_captcha')
                    for folder in [f'{save_path}/ibig', f'{save_path}/isma']:
                        os.makedirs(folder, exist_ok=True)
                    filename = f"{uuid.uuid4()}.jpg"
                    with open(f"{save_path}/isma/{filename}", "wb") as f:
                        f.write(base64.b64decode(small_image))
                    with open(f"{save_path}/ibig/{filename}", "wb") as f:
                        f.write(base64.b64decode(big_image))
                    logger.info(f"失败验证码已保存: {filename}")
                return False, "验证码识别失败", '', '', ''
            else:
                sign = data["params"]
                return True, p_uuid, token, sign, base_header

        except Exception as e:
            logger.warning(f"check_image Faile : {e}")
            return False, str(e), '', '', ''

    async def getAppAndMiniDetail(self, dataId, serviceType, p_uuid, token, sign, base_header, proxy="", session=None):
        """优化的详情获取，移除会话复用"""
        info = {"dataId": dataId, "serviceType": serviceType}
        length = str(len(str(ujson.dumps(info, ensure_ascii=False)).encode("utf-8")))

        detail_header = base_header.copy()
        detail_header.update({"Content-Length": length, "uuid": p_uuid, "token": token, "sign": sign})

        if not getattr(getattr(config, 'captcha', object()), 'enable', False):
            detail_header.pop("uuid", None)
            detail_header.pop("Content-Length", None)

        # 优先使用传入的会话，否则创建新会话
        current_ip = None
        if session:
            current_ip = self._session_local_ip(session)
            if getattr(getattr(config, 'captcha', object()), 'enable', False):
                async with session.post(self.queryDetailByAppAndMiniId,
                                        data=ujson.dumps(info, ensure_ascii=False),
                                        headers=detail_header,
                                        proxy=proxy if proxy else None) as req:
                    res = await req.text()
            else:
                async with session.post(f"{self.queryDetailByAppAndMiniId}",
                                        json=info,
                                        headers=detail_header,
                                        proxy=proxy if proxy else None) as req:
                    res = await req.text()
        else:
            async with self.get_session(proxy) as session:
                current_ip = self._session_local_ip(session)
                if getattr(getattr(config, 'captcha', object()), 'enable', False):
                    async with session.post(self.queryDetailByAppAndMiniId,
                                            data=ujson.dumps(info, ensure_ascii=False),
                                            headers=detail_header,
                                            proxy=proxy if proxy else None) as req:
                        res = await req.text()
                else:
                    async with session.post(f"{self.queryDetailByAppAndMiniId}",
                                            json=info,
                                            headers=detail_header,
                                            proxy=proxy if proxy else None) as req:
                        res = await req.text()
        if "当前访问疑似黑客攻击" in res or "已被创宇盾拦截" in res:
            logger.warning("详情获取触发创宇盾拦截，记录黑名单IP并熔断")
            if current_ip:
                self._add_blocked_ip(current_ip)
            else:
                # 无法定位真实出口地址时不做索引猜测：并发下 ipv6_index 已被其它协程推进，
                # 按 index-1 归因会误封健康 IP，交由 _arl_local_ip 精确标记处理
                logger.warning("WAF 拦截但未能定位出口地址，跳过黑名单写入")
            return False, {"code": 403, "msg": "当前访问已被创宇盾拦截", "success": False}

        try:
            return True, ujson.loads(res)
        except Exception as e:
            logger.warning(f"解析详情响应失败: {e}, 响应文本截断: {res[:100]}")
            return False, {"code": 500, "msg": f"解析异常: {e}", "success": False}


    def _is_auto_pagination(self, pageNum, pageSize):
        """未显式传分页参数时，默认拉取全部页。"""
        return pageNum in (None, "") and pageSize in (None, "")

    def _get_total_pages(self, result, page_size):
        params = result.get("params", {}) if isinstance(result, dict) else {}
        pages = params.get("pages") or params.get("lastPage")
        if pages:
            try:
                return max(int(pages), 1)
            except (TypeError, ValueError):
                pass

        total = params.get("total")
        try:
            total = int(total)
            return max((total + page_size - 1) // page_size, 1)
        except (TypeError, ValueError):
            return 1

    async def _query_beian_page(self, name, sp, pageNum, pageSize, proxy=""):
        info = ujson.loads(self.typj.get(sp))
        info["pageNum"] = pageNum
        info["pageSize"] = pageSize
        info["unitName"] = name
        current_ip = None
        
        if getattr(getattr(config, 'captcha', object()), 'enable', False):
            success, p_uuid, token, sign, base_header = await self.check_img(proxy)
            if not success:
                logger.info(f"打码失败：{p_uuid}")
                return False, p_uuid, None

            length = str(len(str(ujson.dumps(info, ensure_ascii=False)).encode("utf-8")))
            base_header.update({"Content-Length": length, "uuid": p_uuid, "token": token, "sign": sign})
            
            async with self.get_session(proxy) as session:
                current_ip = self._session_local_ip(session)
                async with session.post(self.queryByCondition,
                                        data=ujson.dumps(info, ensure_ascii=False),
                                        headers=base_header,
                                        proxy=proxy if proxy else None) as req:
                    res = await req.text()
        else:
            success, token, base_header = await self.get_token(proxy)
            sign = ""
            p_uuid = ""
            if not success:
                logger.info(f"获取token失败")
                return False, None, None
            base_header.update({"token": token, "sign": self.sign})

            async with self.get_session(proxy) as session:
                current_ip = self._session_local_ip(session)
                async with session.post(f"{self.queryByCondition}/",
                                        json=info,
                                        headers=base_header,
                                        proxy=proxy if proxy else None) as req:
                    res = await req.text()

        if "当前访问疑似黑客攻击" in res or "已被创宇盾拦截" in res:
            # 熔断只取决于"是否被封"，不依赖出口地址能否归因（未启用 IPv6 池时同样需要止血）
            self._waf_trip("列表查询")
            if current_ip:
                self._add_blocked_ip(current_ip)
            else:
                # 无法定位真实出口地址时不做索引猜测：并发下 ipv6_index 已被其它协程推进，
                # 按 index-1 归因会误封健康 IP，交由 _arl_local_ip 精确标记处理
                logger.warning("WAF 拦截但未能定位出口地址，跳过黑名单写入")
            return False, "当前访问已被创宇盾拦截", None

        try:
            result = ujson.loads(res)
        except Exception as e:
            # 创宇盾拦截页常为 HTML，与详情侧保持同款容错，避免异常被 autoget 吞成无信息 code=122
            snippet = (res or "")[:120].replace("\n", " ")
            logger.warning(f"列表查询响应解析失败: {e}, 响应片段: {snippet}")
            return False, f"列表查询响应解析失败: {e}", None

        detail_context = {
            "p_uuid": p_uuid,
            "token": token,
            "sign": sign if getattr(getattr(config, 'captcha', object()), 'enable', False) else self.sign,
            "base_header": base_header,
        }
        return True, result, detail_context

    async def _enrich_app_details(self, result, sp, detail_context, proxy):
        """为APP/小程序/快应用结果补充详情。"""
        if (sp in (1, 2, 3)
            and result.get("success")
            and result.get("params", {}).get("list")):
            
            items = result["params"]["list"]
            if not items:
                return result
                
            # 使用现有的 detail_concurrency 配置，合理收敛单节点并发
            max_concurrency = min(
                getattr(getattr(config, "system", object()), "detail_concurrency", 5),
                len(items),
                10
            )
            max_concurrency = max(1, max_concurrency)
            sem = asyncio.Semaphore(max_concurrency)
            stats = {"enriched": 0}
            pending_cnt = sum(1 for it in items if "dataId" in it)

            async def ensure_token_valid():
                # captcha 模式下 p_uuid/sign 与旧 token 成对签发，中途换 token 会使鉴权三元组失配
                if getattr(getattr(config, 'captcha', object()), 'enable', False):
                    return
                now_ms = int(time.time() * 1000)
                # 第一次快检：若 token 剩余时间充足（>=60s），无需争抢锁直接放行
                if self.token_expire - now_ms >= 60000:
                    return
                # 双检锁（DCL）：仅允许首个获锁协程真正发起刷新，其余并发协程获锁后复检直接复用最新 token
                async with self.token_lock:
                    now_ms = int(time.time() * 1000)
                    if self.token_expire - now_ms >= 60000:
                        detail_context["token"] = self.token
                        return
                    try:
                        logger.info("ICP Token 即将过期，正在自动刷新 Token...")
                        tok_ok, new_tok, _ = await self.get_token(proxy)
                        if tok_ok:
                            # 仅替换 token，保留 base_header 以维持 __jsluid_s 会话身份连续
                            detail_context["token"] = new_tok
                            logger.info("ICP Token 自动刷新成功")
                    except Exception as e:
                        logger.warning(f"刷新 Token 异常: {e}")

            async def fetch_detail(item):
                if self._waf_open() or "dataId" not in item:
                    return item

                serviceType = 6 if sp == 1 else (7 if sp == 2 else 8)
                try:
                    async with sem:
                        if self._waf_open():
                            return item
                        await ensure_token_valid()
                        d_success, d_data = await self.getAppAndMiniDetail(
                            item["dataId"], serviceType, detail_context["p_uuid"],
                            detail_context["token"], detail_context["sign"],
                            detail_context["base_header"], proxy
                        )

                    if d_success and isinstance(d_data, dict) and d_data.get("success") and d_data.get("params"):
                        merged_item = item.copy()
                        merged_item.update(d_data["params"])
                        stats["enriched"] += 1
                        return merged_item
                    else:
                        if isinstance(d_data, dict) and (d_data.get("code") == 403 or "已被创宇盾拦截" in str(d_data)):
                            self._waf_trip("详情获取")
                        else:
                            logger.warning(f"详情获取未成功 dataId={item.get('dataId')}")
                        return item
                except Exception as e:
                    logger.error(f"详情获取异常 dataId={item.get('dataId')} err={e}")
                    return item

            # 采用受控批次并发执行，每批次间留有短暂安全间隔维持平稳速率
            batch_size = max_concurrency
            detailed_list = []

            for i in range(0, len(items), batch_size):
                if self._waf_open():
                    # 遭遇 WAF 拦截，平滑降级，将剩余未请求的原始条目直接填充并终止
                    detailed_list.extend(items[i:])
                    break

                batch = items[i:i + batch_size]
                tasks = [fetch_detail(item) for item in batch]
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)

                # 处理结果
                for j, res in enumerate(batch_results):
                    if isinstance(res, Exception):
                        logger.error(f"批次任务异常: {res}")
                        detailed_list.append(batch[j])
                    else:
                        detailed_list.append(res)

                if i + batch_size < len(items) and not self._waf_open():
                    await asyncio.sleep(0.3)

            result["params"]["list"] = detailed_list
            missing = max(pending_cnt - stats["enriched"], 0)
            if missing:
                # 降级可观测：缺口量沿调用链上抛，供任务侧标记与用户感知
                result["params"]["_detail_missing"] = missing
                result["params"]["_detail_waf"] = self._waf_open()
            logger.info(
                f"并发详情获取完成，总计 {len(detailed_list)} 条 (详情缺失: {missing}, WAF熔断: {self._waf_open()})"
            )
            
        return result

    async def getbeian(self, name, sp, pageNum, pageSize, proxy=""):
        auto_pagination = self._is_auto_pagination(pageNum, pageSize)
        if auto_pagination:
            first_page = 1
            page_size = 26
        else:
            first_page = int(pageNum or 1)
            page_size = int(pageSize or 26)

        success, result, detail_context = await self._query_beian_page(
            name, sp, first_page, page_size, proxy
        )
        if not success:
            return False, result

        if not auto_pagination:
            result = await self._enrich_app_details(result, sp, detail_context, proxy)
            return True, result

        params = result.get("params", {})
        all_items = list(params.get("list") or [])
        total_pages = self._get_total_pages(result, page_size)

        for current_page in range(2, total_pages + 1):
            await asyncio.sleep(2.0)  # 防止请求过快触发 MIIT 403 防火墙
            success, page_result, page_detail_context = await self._query_beian_page(
                name, sp, current_page, page_size, proxy
            )
            if not success:
                logger.warning(f"分页获取失败，已抓取至第 {current_page-1} 页，停止继续翻页")
                break # 不直接抛出错误，而是保留已获取的前几页数据

            page_params = page_result.get("params", {})
            all_items.extend(page_params.get("list") or [])
            detail_context = page_detail_context or detail_context

        params["list"] = all_items
        params["pageNum"] = 1
        params["pageSize"] = len(all_items)
        result["params"] = params

        result = await self._enrich_app_details(result, sp, detail_context, proxy)
        return True, result

    async def getblackbeian(self, name, sp, proxy=""):
        info = ujson.loads(self.btypj.get(sp))
        if sp == 0:
            info["domainName"] = name
        else:
            info["serviceName"] = name


        if getattr(getattr(config, 'captcha', object()), 'enable', False):
            success, p_uuid, token, sign, base_header = await self.check_img(proxy)
            if not success:
                return False, p_uuid
            
            length = str(len(str(ujson.dumps(info, ensure_ascii=False)).encode("utf-8")))
            base_header.update(
                {"Content-Length": length, "uuid": p_uuid, "token": token, "sign": sign}
            )
            async with self.get_session(proxy) as session:
                current_ip = self._session_local_ip(session)
                async with session.post((self.blackqueryByCondition if sp == 0 else self.blackappAndMiniByCondition),
                                         data=ujson.dumps(info, ensure_ascii=False),
                                         headers=base_header, proxy=proxy if proxy else None) as req:
                    res = await req.text()
            
        else:
            success, token, base_header = await self.get_token(proxy)
            sign = ""
            p_uuid = ""
            if not success:
                logger.info(f"获取token失败")
                return False, None
            base_header.update({"token": token, "sign": self.sign})

            async with self.get_session(proxy) as session:
                current_ip = self._session_local_ip(session)
                async with session.post((f"{self.blackqueryByCondition}/" if sp == 0 else f"{self.blackappAndMiniByCondition}/"),
                                            json=info, 
                                            headers=base_header, proxy=proxy if proxy else None) as req:
                    res = await req.text()

        if "当前访问疑似黑客攻击" in res:
            if current_ip:
                self._add_blocked_ip(current_ip)
            else:
                # 无法定位真实出口地址时不做索引猜测：并发下 ipv6_index 已被其它协程推进，
                # 按 index-1 归因会误封健康 IP，交由 _arl_local_ip 精确标记处理
                logger.warning("WAF 拦截但未能定位出口地址，跳过黑名单写入")
            return False, "当前访问已被创宇盾拦截"

        return True,ujson.loads(res)

    async def autoget(self, name, sp, pageNum="", pageSize="", proxy="", b=1):
        try:
            if proxy != "":
                success,data = (
                    await self.getbeian(name, sp, pageNum, pageSize, proxy)
                    if b == 1
                    else await self.getblackbeian(name, sp, proxy)
                )
            else:
                success,data = (
                    await self.getbeian(name, sp, pageNum, pageSize)
                    if b == 1
                    else await self.getblackbeian(name, sp)
                )
            if not success:
                return {"code":500,"message":data}
            if data["code"] == 500 or not success:
                return {"code": 122, "message": "工信部服务器异常"}
        except Exception as e:
            return {"code": 122, "message": "查询失败","error":str(e)}
        
        return data

    # APP备案查询
    async def ymApp(self, name, pageNum="", pageSize="", proxy=""):
        return await self.autoget(name, 1, pageNum, pageSize, proxy)

    # 网站备案查询
    async def ymWeb(self, name, pageNum="", pageSize="", proxy=""):
        return await self.autoget(name, 0, pageNum, pageSize, proxy)

    # 小程序备案查询
    async def ymMiniApp(self, name, pageNum="", pageSize="", proxy=""):
        return await self.autoget(name, 2, pageNum, pageSize, proxy)

    # 快应用备案查询
    async def ymKuaiApp(self, name, pageNum="", pageSize="", proxy=""):
        return await self.autoget(name, 3, pageNum, pageSize, proxy)



    async def cleanup(self):
        """清理资源 - 移除连接器缓存相关代码"""
        logger.info("beian资源清理完成")

    def __del__(self):
        """析构函数，确保资源清理"""
        try:
            pass
        except:
            pass

if __name__ == "__main__":
    async def main():
        a = beian()
        try:
            # 官方单页查询pageSize最大支持26
            # 页面索引pageNum从1开始,第一页可以不写
            data = await a.ymWeb("深圳市腾讯计算机系统有限公司")
            print(f"查询结果：\n{data}")
            data = await a.ymApp("深圳市腾讯计算机系统有限公司")
            print(f"查询结果：\n{data}")
        finally:
            await a.cleanup()  # 确保资源清理

    asyncio.run(main())

    """
    在其他代码模块中调用（异步）

        from ymicp import beian

        icp = beian()
        try:
            data = await icp.ymApp("微信")
        finally:
            await icp.cleanup()  # 重要：确保资源清理
    
    """
