import time
from pyquery import PyQuery as pq
import binascii
from urllib.parse import urljoin, urlparse
from urllib3.util.url import parse_url, get_host
import mmh3
from app import utils
from .baseThread import BaseThread

logger = utils.get_logger()
from .autoTag import auto_tag
from app.utils import http_req, normal_url
# Removed static load_fingerprint as we now rely fully on DB

class FetchSite(BaseThread):
    """
    [第一性原理：底层武器库 - Web 站点侦察兵]
    在获取到了活着的 IP 和端口后，如果是 Web 端口（80/443等），就会移交给这个类。
    它的任务有三个：
    1. 发起 HTTP 请求，拿回网页的 Title、Headers 和 Body。
    2. 计算网页 Favicon (网站图标) 的哈希值。
    3. 将 Body 和 Header 丢进指纹库（Fingerprint），识别出这个网站用的是什么 CMS (如 WordPress, 致远OA)。
    
    它继承了 BaseThread，意味着它自带多线程并发能力，可以同时抓取多个站点。
    """
    def __init__(self, sites, concurrency=6, http_timeout=None):
        super().__init__(sites, concurrency)
        self.site_info_list = []
        self.http_timeout = http_timeout
        if http_timeout is None:
            self.http_timeout = (10.1, 30.1)

    def fetch_fingerprint(self, item, content):
        """
        [第一性原理：Web 指纹识别 (统一版)]
        指纹识别不仅靠网页里的关键字，还有 HTTP 响应头（比如 Server 字段），以及独一无二的 Favicon Hash。
        现在的规则已全部统一存储在数据库中，直接通过 finger_db_identify 进行全量匹配。
        """
        favicon_hash = item["favicon"].get("hash", 0)
        
        result = finger_identify(content=content, header=item["headers"],
                                 title=item["title"], favicon_hash=str(favicon_hash))
        
        # 去重
        result = set(result)

        finger = []
        for name in result:
            finger_item = {
                "icon": "default.png",
                "name": name,
                "confidence": "80",
                "version": "",
                "website": "https://www.riskivy.com",
                "categories": []
            }
            finger.append(finger_item)

        if finger:
            item["finger"] = finger

    def work(self, site, max_redirect=5):
        """
        [第一性原理：爬虫核心引擎]
        这是 BaseThread 强制要求重写的工作函数，每个线程就跑这个逻辑。
        """
        # 防止遇到恶意网站配置了无限 302 重定向死循环，设置最大重定向次数
        if max_redirect <= 0:
            return

        _, hostname, _ = get_host(site)

        # 核心：发起 HTTP 请求
        conn = utils.http_req(site, timeout=self.http_timeout)
        item = {
            "site": site[:200],
            "hostname": hostname,
            "ip": "",
            "title": utils.get_title(conn.content),
            "status": conn.status_code,
            "headers": utils.get_headers(conn),
            "http_server": conn.headers.get("Server", ""),
            "body_length": len(conn.content),
            "finger": [],
            "favicon": fetch_favicon(site) # 触发提取 Icon 哈希
        }

        self.fetch_fingerprint(item, content=conn.content)
        
        domain_parsed = utils.domain_parsed(hostname)
        if domain_parsed:
            item["fld"] = domain_parsed["fld"]
            ips = utils.get_ip(hostname)
            if ips:
                item["ip"] = ips[0]
        else:
            item["ip"] = hostname

        # 【第一性原理：重定向链跟踪】
        # 如果是 200/403 等正常状态码，或者是重定向链的最后一次（max_redirect==1），就保存结果
        if max_redirect == 5 or max_redirect == 1 \
                or (conn.status_code != 301 and conn.status_code != 302):
            self.site_info_list.append(item)

        # 遇到 301/302，我们需要跟进去看看到底跳转去了哪里
        if conn.status_code == 301 or conn.status_code == 302:
            url_302 = urljoin(site, conn.headers.get("Location", ""))
            url_302 = normal_url(url_302)

            # 防御性编程，防止目标服务器搞个超级长的 URL 把我们内存干爆
            if len(url_302) > 260:
                return

            # 如果跳转后的 URL 跟原 URL 不同，并且是在同域名同协议下，那就继续往下层钻
            if url_302 != site and same_netloc_and_scheme(url_302, site):
                self.work(url_302, max_redirect=max_redirect - 1)

    def run(self):
        t1 = time.time()
        logger.info("start fetch site {}".format(len(self.targets)))
        # 调用父类 BaseThread 的 _run()，启动多线程大军开始干活
        self._run()
        elapse = time.time() - t1
        logger.info("end fetch site elapse {}".format(elapse))

        # 对站点信息自动打标签（比如如果返回特定的 404 页面特征，就打上“无效站点”标签）
        auto_tag(self.site_info_list)

        return self.site_info_list


def finger_identify(content: bytes, header: str, title: str, favicon_hash: str):
    """
    编码处理层：把不同网站奇葩的编码统一转成 utf-8，
    如果实在转不了，就用 gbk 强行解码（并忽略无法解析的字符），保证指纹识别引擎不抛异常崩掉。
    """
    from app.services import finger_db_identify

    try:
        content = content.decode("utf-8")
    except UnicodeDecodeError:
        content = content.decode("gbk", "ignore")

    variables = {
        "body": content,
        "header": header,
        "title": title,
        "icon_hash": favicon_hash
    }

    return finger_db_identify(variables)


def same_netloc_and_scheme(u1, u2):
    u1 = normal_url(u1)
    u2 = normal_url(u2)
    parsed1 = parse_url(u1)
    parsed2 = parse_url(u2)

    if parsed1.scheme == parsed2.scheme and parsed1.netloc == parsed2.netloc:
        return True

    return False


def fetch_favicon(url):
    f = FetchFavicon(url)
    return f.run()


def fetch_site(sites, concurrency=15, http_timeout=None):
    """
    [高级封装层]
    为外部流水线提供直接调用的入口函数。
    每次拉起前，强制去数据库同步最新的用户自定义指纹规则，保证规则库永远最新。
    """
    from app.services import finger_db_cache
    finger_db_cache.update_cache()

    f = FetchSite(sites, concurrency=concurrency, http_timeout=http_timeout)
    return f.run()


class FetchFavicon(object):
    """
    [第一性原理：Favicon 猎手]
    网站的图标往往蕴含着极高价值的指纹（很多开发嫌麻烦不会去改默认的 Spring Boot 或 Tomcat 图标）。
    但网站的图标存放位置千奇百怪。
    这个类的目的就是：不惜一切代价，把那个小图标挖出来并算成 Hash。
    """
    def __init__(self, url):
        self.url = url
        self.favicon_url = None
        pass

    def build_result(self, data):
        result = {
            "data": data,
            "url": self.favicon_url,
            # [核心算法：mmh3] fofa 等测绘引擎通用的图标哈希算法。
            "hash": mmh3.hash(data)
        }
        return result

    def run(self):
        result = {}
        try:
            # 策略一：简单粗暴，直接去根目录找 /favicon.ico (90% 的网站是这样)
            favicon_url = urljoin(self.url, "/favicon.ico")
            data = self.get_favicon_data(favicon_url)
            if data:
                self.favicon_url = favicon_url
                return self.build_result(data)

            # 策略二：如果根目录没有，说明是奇葩前端框架，去解析网页 HTML 源码，找到 <link rel="icon"> 标签指定的路径
            favicon_url = self.find_icon_url_from_html()
            if not favicon_url:
                return result
            data = self.get_favicon_data(favicon_url)
            if data:
                self.favicon_url = favicon_url
                return self.build_result(data)

        except Exception as e:
            logger.warning("error on {} {}".format(self.url, e))

        return result

    def get_favicon_data(self, favicon_url):
        conn = http_req(favicon_url)
        if conn.status_code != 200:
            return

        # 图标体积一般不可能小于 80 字节，防误报
        if len(conn.content) <= 80:
            logger.debug("favicon content len lt 100")
            return

        # 确保拿到的是图片，而不是被 WAF 拦截的返回页面
        if "image" in conn.headers.get("Content-Type", ""):
            data = self.encode_bas64_lines(conn.content)
            return data

    def encode_bas64_lines(self, s):
        """
        [第一性原理：Base64 折叠]
        为什么这里要把 Base64 切割成每 76 个字符一行？
        因为 mmh3 计算图标哈希时，业界约定的算法必须遵循早期邮件附件的标准格式（MIME-Base64），
        不按照 76 字符换行算出来的 Hash 根本无法拿到 Fofa 上去碰撞。
        """
        MAXLINESIZE = 76  # Excluding the CRLF
        MAXBINSIZE = (MAXLINESIZE // 4) * 3
        pieces = []
        for i in range(0, len(s), MAXBINSIZE):
            chunk = s[i: i + MAXBINSIZE]
            pieces.append(bytes.decode(binascii.b2a_base64(chunk)))
        return "".join(pieces)

    def find_icon_url_from_html(self):
        """用 pyquery (类似 jQuery 的操作语法) 提取 HTML 中的图标链接"""
        conn = http_req(self.url)
        if b"<link" not in conn.content:
            return
        d = pq(conn.content)
        links = d('link').items()
        icon_link_list = []
        for link in links:
            if link.attr("href") and 'icon' in link.attr("rel"):
                icon_link_list.append(link)

        for link in icon_link_list:
            if "shortcut" in link:
                return urljoin(self.url, link.attr('href'))

        if icon_link_list:
            return urljoin(self.url, icon_link_list[0].attr('href'))
