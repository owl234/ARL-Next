import json
import re
from .IPy import IP
from app.config import Config


cdn_ip_cidr_list = []
cdn_cname_list = []
cdn_info = []

# 常见 CDN 厂商 ASN 组织关键词映射
ASN_CDN_RULES = [
    {"keywords": ["cloudflare"], "name": "Cloudflare CDN"},
    {"keywords": ["fastly"], "name": "Fastly CDN"},
    {"keywords": ["akamai"], "name": "Akamai CDN"},
    {"keywords": ["cloudfront", "amazon technologies inc", "amazon.com"], "name": "AWS CloudFront"},
    {"keywords": ["azureedge", "microsoft corporation"], "name": "Azure CDN"},
    {"keywords": ["wangsu", "chinanetcenter", "xiamen wangsu"], "name": "网宿科技 CDN"},
    {"keywords": ["baiduyun", "yunjiasu", "baidu.com"], "name": "百度云加速 CDN"},
    {"keywords": ["qcloud", "edgeone", "tencent cloud computing"], "name": "腾讯云 CDN/EdgeOne"},
    {"keywords": ["kunlun", "alibaba advertising", "alibaba.com", "alibabacloud", "alicdn"], "name": "阿里云 CDN/ESA"},
    {"keywords": ["hwclouds", "huawei software"], "name": "华为云 CDN"},
    {"keywords": ["qiniu"], "name": "七牛云 CDN"},
    {"keywords": ["bytedance", "volces", "volcengine", "beijing bytedance"], "name": "火山引擎/字节跳动 CDN"},
]

# 常见 CDN 厂商 CNAME 特征后缀
CNAME_CDN_RULES = [
    {"keywords": ["wscdns.com", "wsdvs.com", "ourwebpic.com", "chinanetcenter.com", "speedcdns.com"], "name": "网宿科技 CDN"},
    {"keywords": ["kunlun", "alikunlun", "tbcdn.cn", "alicdn.com", "alicloudwaf.com"], "name": "阿里云 CDN/ESA"},
    {"keywords": ["tc.cdntip.com", "qcloudcdn.com", "tcdn.qq.com", "edgeone.ai", "edgeone.cool", "dnsv1.com"], "name": "腾讯云 CDN/EdgeOne"},
    {"keywords": ["cdnhwc", "huaweicloudwaf"], "name": "华为云 CDN/WAF"},
    {"keywords": ["cloudflare.net", "cloudflare.com"], "name": "Cloudflare CDN"},
    {"keywords": ["cloudfront.net"], "name": "AWS CloudFront"},
    {"keywords": ["fastly.net", "fastlylb.net"], "name": "Fastly CDN"},
    {"keywords": ["akamaiedge.net", "akamai.net", "akamaitechnologies.com", "edgesuite.net", "edgekey.net"], "name": "Akamai CDN"},
    {"keywords": ["azureedge.net", "azurefd.net", "trafficmanager.net"], "name": "微软 Azure CDN / Front Door"},
    {"keywords": ["yunjiasu-cdn.net", "bdydns.com", "jomodns.com"], "name": "百度云加速 CDN"},
    {"keywords": ["qiniudns.com", "qbox.me"], "name": "七牛云 CDN"},
    {"keywords": ["volccdn.com", "bytecdn.cn", "volcbypass.com"], "name": "火山引擎/字节跳动 CDN"},
    {"keywords": ["aicdn.com", "upaiyun.com"], "name": "又拍云 CDN"},
    {"keywords": ["jcloud-cdn.com", "jdcdn.com", "jcloudlb.com"], "name": "京东云 CDN"},
]

# 常见 CDN / WAF HTTP 响应头特征
HEADER_CDN_INDICATORS = [
    "cf-ray", "x-amz-cf-id", "x-edge-connect-request-id",
    "x-alicdn-da-ups-status", "x-ws-request-id", "eagleid",
    "x-cdn-request-id", "x-fastly-request-id", "x-cache-lookup"
]

# 常见 CDN SSL 泛域名特征
SSL_CDN_DOMAINS = [
    "kunluncan.com", "kunlunaq.com", "kunlunar.com", "wscdns.com",
    "wsdvs.com", "ourwebpic.com", "cdngslb.com", "tbcdn.cn",
    "alicdn.com", "cloudflare.com", "cloudfront.net", "fastly.net",
    "azureedge.net", "volccdn.com", "bdydns.com"
]


def _init_cdn_info():
    from . import load_file
    global cdn_ip_cidr_list, cdn_cname_list, cdn_info
    if not cdn_info:
        cdn_ip_cidr_list = []
        cdn_cname_list = []
        try:
            data = "\n".join(load_file(Config.CDN_JSON_PATH))
            cdn_info = json.loads(data)

            for item in cdn_info:
                cdn_cname_list.extend(item.get("cname_domain", []))
                if item.get("ip_cidr"):
                    cdn_ip_cidr_list.extend(item["ip_cidr"])
        except Exception:
            cdn_info = []


def _ip_in_cidr_list(ip):
    for item in cdn_ip_cidr_list:
        if IP(ip) in IP(item):
            return True
    return False


def _cname_in_cname_list(cname):
    for item in cdn_cname_list:
        if cname.endswith("." + item) or cname == item:
            return True
    return False


def get_cdn_name_by_ip(ip):
    """通过静态 CIDR 库与 ASN 组织综合判定 IP 是否属于 CDN"""
    from . import get_logger, get_ip_asn
    logger = get_logger()
    try:
        _init_cdn_info()

        # 1. 静态 CIDR 匹配
        if _ip_in_cidr_list(ip):
            for item in cdn_info:
                if item.get("ip_cidr"):
                    for ip_cidr in item["ip_cidr"]:
                        if IP(ip) in IP(ip_cidr):
                            return item.get("name", "CDN")

        # 2. ASN 组织动态匹配
        asn_info = get_ip_asn(ip)
        if asn_info and asn_info.get("organization"):
            org_lower = asn_info["organization"].lower()
            for rule in ASN_CDN_RULES:
                for kw in rule["keywords"]:
                    if kw in org_lower:
                        return rule["name"]

    except Exception as e:
        logger.warning("error in get_cdn_name_by_ip: {} {}".format(e, ip))

    return ""


def get_cdn_name_by_cname(cname):
    """通过 CNAME 域名规则及关键字判定 CDN"""
    from . import get_logger
    logger = get_logger()
    if not cname:
        return ""

    cname_lower = cname.lower().strip(".")
    try:
        _init_cdn_info()

        # 1. 精确规则匹配
        for rule in CNAME_CDN_RULES:
            for kw in rule["keywords"]:
                if cname_lower.endswith(kw) or kw in cname_lower:
                    return rule["name"]

        # 2. 静态 cdn_info 匹配
        if _cname_in_cname_list(cname_lower):
            for item in cdn_info:
                for target in item.get("cname_domain", []):
                    if cname_lower.endswith(target):
                        return item.get("name", "CDN")

        # 3. 通用关键词后备匹配
        check_list = ["gslb", "dns", "cache", "cdn", "edge", "anycast"]
        for check in check_list:
            if check in cname_lower:
                return "CDN"

    except Exception as e:
        logger.warning("error in get_cdn_name_by_cname: {} {}".format(e, cname))

    return ""


def get_cdn_name_by_headers(headers: dict) -> str:
    """通过 HTTP 响应头指纹识别 CDN / WAF"""
    if not headers or not isinstance(headers, dict):
        return ""

    headers_lower = {k.lower(): str(v).lower() for k, v in headers.items()}

    # 1. 检查专属 CDN Request-ID / 追踪 Header
    for indicator in HEADER_CDN_INDICATORS:
        if indicator in headers_lower:
            if "alicdn" in indicator or "eagleid" in indicator:
                return "阿里云 CDN/ESA"
            elif "cf-ray" in indicator:
                return "Cloudflare"
            elif "amz-cf" in indicator:
                return "AWS CloudFront"
            elif "fastly" in indicator:
                return "Fastly CDN"
            elif "ws-request" in indicator:
                return "网宿科技 CDN"
            return "CDN"

    # 2. 检查 Via 头
    via = headers_lower.get("via", "")
    if via:
        if any(k in via for k in ["alicdn", "l2nm", "cn9642", "tengine"]):
            return "阿里云 CDN"
        elif "cloudflare" in via:
            return "Cloudflare"
        elif "varnish" in via or "squid" in via or "cdn" in via:
            return "CDN"

    # 3. 检查 Server 头
    server = headers_lower.get("server", "")
    if server:
        if "cloudflare" in server:
            return "Cloudflare"
        elif "yunjiasu" in server:
            return "百度云加速 CDN"
        elif "waf" in server or "tengine/waf" in server:
            return "云WAF / 反向代理"

    return ""


def get_cdn_name_by_ssl(sans: list) -> str:
    """通过 SSL 证书 SAN 域名判定是否为公共 CDN 共享泛证书"""
    if not sans or not isinstance(sans, list):
        return ""

    for san in sans:
        san_lower = str(san).lower()
        for cdn_domain in SSL_CDN_DOMAINS:
            if cdn_domain in san_lower:
                return "CDN 共享证书"

    return ""


def get_cdn_name_comprehensive(ip: str, cname: str = "", headers: dict = None, ssl_sans: list = None, ip_count: int = 0) -> str:
    """
    【四维融合 CDN 判定引擎】
    综合 CIDR、CNAME、ASN、HTTP Headers、SSL SAN 与 IP 解析离散度
    """
    # 1. 优先检查 CNAME
    if cname:
        name = get_cdn_name_by_cname(cname)
        if name:
            return name

    # 2. 检查 IP 及 ASN
    if ip:
        name = get_cdn_name_by_ip(ip)
        if name:
            return name

    # 3. 检查 SSL 证书 SAN
    if ssl_sans:
        name = get_cdn_name_by_ssl(ssl_sans)
        if name:
            return name

    # 4. 检查 HTTP 响应头
    if headers:
        name = get_cdn_name_by_headers(headers)
        if name:
            return name

    # 5. 单域名多地解析离散判定 (大于等于 4 个 IP 通常为 CDN 节点集群)
    if ip_count >= 4:
        return "CDN"

    return ""

