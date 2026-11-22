import re
from app import utils
from app.modules import SiteAutoTag
logger = utils.get_logger()

GENERIC_SERVERS = {
    "nginx", "apache", "iis", "tengine", "openresty", "lighttpd", "caddy",
    "microsoft-iis", "apache-http-server", "apache-httpd", "byte-nginx",
    "apache2 debian 默认页", "apache2 ubuntu 默认页", "iis 默认页",
    "tencentedgeone", "edgeone", "ecdn", "dcdn", "azure edge network",
    "lego server",
}

INFRA_TOKENS = {
    "cdn", "waf", "proxy", "gateway", "alb", "slb", "elb", "tlb", "clb", "nlb",
    "volcalb", "loadbalancer", "cloudflare", "akamai", "fastly", "imperva",
    "incapsula", "envoy", "traefik", "haproxy", "squid", "varnish", "kong",
    "edgeone", "tencentedgeone", "cloudfront", "azureedge", "alicdn", "qcloudcdn",
    "tcdn", "ecdn", "dcdn", "volccdn", "yunjiasu", "wangsu", "cdn77", "arvancloud",
    "esa", "apisix", "openresty", "tengine", "block",
}

VENDOR_TOKENS = {
    "bytedance", "aliyun", "alibaba", "tencent", "qcloud", "baidu", "huawei",
    "cloud", "aws", "amazon", "azure", "google", "microsoft", "volcengine", "volc",
    "qiniu", "upaiyun", "jcloud", "wangsu", "chinanetcenter", "5centscdn",
}

NOISE_TOKENS = {"server", "service", "vhost", "default", "edge", "network", "page", "platform"}


def is_infra_fingerprint(name) -> bool:
    """判定指纹是否属于基础设施（CDN/WAF/边缘网关/负载均衡/通用 Web 服务器），此类指纹不作为业务特赦凭据"""
    if not name or not isinstance(name, str):
        return False
    lower = name.lower().strip()
    if lower in GENERIC_SERVERS:
        return True
    tokens = {t for t in re.split(r"[\s\-_/()]+", lower) if t}
    if tokens.intersection(INFRA_TOKENS):
        non_infra = tokens - INFRA_TOKENS - VENDOR_TOKENS - NOISE_TOKENS
        if not non_infra:
            return True
    return False


def has_business_fingerprint(finger_list) -> bool:
    """判断指纹列表中是否包含至少一个非基础设施（业务/CMS/框架）指纹"""
    if not isinstance(finger_list, list) or not finger_list:
        return False
    for fg in finger_list:
        fg_name = (fg if isinstance(fg, str) else (fg.get("name", "") if isinstance(fg, dict) else "")).strip()
        if fg_name and not is_infra_fingerprint(fg_name):
            return True
    return False


class AutoTag:
    def __init__(self, site_info):
        self.site_info = site_info
        self.status = self.site_info.get("status", 0)
        self.title = self.site_info.get("title", "")
        self.headers = self.site_info.get("headers", "")

    def run(self):
        body_length = self.site_info.get("body_length", 0)
        finger = self.site_info.get("finger") or []

        # 仅当识别出具体业务/应用/CMS 指纹时豁免无效站点打标；纯 CDN/边缘网关/通用 Web 服务器指纹不予豁免
        if has_business_fingerprint(finger):
            return

        if self.is_invalid_title():
            return self._set_invalid_tag()

        # 边缘节点 / 网关拒收未绑定 Host 的空体或短错误页直接标为无效
        if self.status in (418, 421) and body_length <= 1000:
            self._set_invalid_tag()
            return

        # 🛡️【现代 API / 云原生 / 微服务 404 保护】
        # 很多微服务、K8s 组件、REST API 根路径仅返回 404 (如 nosniff, text/plain 或 application/json)
        # 这类端点具有极高渗透与探测价值，保留默认待测试状态，豁免打上“无效”标签
        if self.is_40x():
            headers_lower = self.headers.lower() if isinstance(self.headers, str) else ""
            if "nosniff" in headers_lower or "application/json" in headers_lower:
                return

        if not self.title and "/html" in self.headers:
            if body_length >= 200 and self.status == 200:
                self._set_entry_tag()
                return

        if body_length <= 300:
            if not self.is_redirected() and not self.title:
                self._set_invalid_tag()
                return

        if body_length <= 1000:
            if self.is_40x() or self.is_50x():
                self._set_invalid_tag()
                return

        if self.is_redirected():
            if not self.is_out():
                self._set_invalid_tag()
                return

            if "Location: https://url.cn/sorry" in self.headers:
                self._set_invalid_tag()
                return

            header_split = self.headers.split("\n")
            for line in header_split:
                if "Location:" in line:
                    hostname = self.site_info.get("hostname")
                    if hostname and hostname in line:
                        return self._set_invalid_tag()
                    else:
                        return self._set_entry_tag()

            return self._set_invalid_tag()

        self._set_entry_tag()

    def is_redirected(self):
        if self.status in [301, 302, 303]:
            return True
        else:
            return False

    def is_40x(self):
        if self.status in [401, 403, 404]:
            return True
        else:
            return False

    def is_50x(self):
        if self.status in [500, 501, 502, 503, 504]:
            return True
        else:
            return False

    def _set_entry_tag(self):
        """
        打标签为入口
        """
        raw_tags = self.site_info.get("tag") or []
        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]
        elif not isinstance(raw_tags, list):
            raw_tags = []
        tags = [t for t in raw_tags if t != SiteAutoTag.INVALID]
        if SiteAutoTag.ENTRY not in tags:
            tags.append(SiteAutoTag.ENTRY)
        self.site_info["tag"] = tags

    def _set_invalid_tag(self):
        """
        打标签为无效（具备业务指纹豁免）
        """
        if has_business_fingerprint(self.site_info.get("finger")):
            return
        raw_tags = self.site_info.get("tag") or []
        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]
        elif not isinstance(raw_tags, list):
            raw_tags = []
        tags = [t for t in raw_tags if t != SiteAutoTag.ENTRY]
        if SiteAutoTag.INVALID not in tags:
            tags.append(SiteAutoTag.INVALID)
        self.site_info["tag"] = tags

    def is_invalid_title(self):
        """
        判断是否是默认无效标题
        """
        invalid_title = ["Welcome to nginx", "IIS7", "Apache Tomcat"]
        invalid_title.extend(["Welcome to CentOS", "Apache HTTP Server Test Page"])
        invalid_title.extend(["Test Page for the Nginx HTTP"])
        invalid_title.extend(["500 Internal Server Error"])
        invalid_title.extend(["Error 404--Not Found"])
        invalid_title.extend(["Welcome to OpenResty"])
        invalid_title.extend(["没有找到站点", "404 not found"])
        invalid_title.extend(["页面不存在", "访问拦截", "403 Forbidden"])
        invalid_title.extend(["Page Not Found"])
        
        for t in invalid_title:
            if t in self.title:
                return True

        return False

    def is_out(self):
        out = ["Location: https://", "Location: http://", "Location: //"]
        for o in out:
            if o in self.headers:
                return True

        return False


def auto_tag(site_info):
    if isinstance(site_info, list):
        for info in site_info:
            a = AutoTag(info)
            a.run()
        return site_info

    if isinstance(site_info, dict):
        a = AutoTag(site_info)
        a.run()
        return site_info
