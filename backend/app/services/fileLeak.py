import time
import difflib
from urllib.parse import urlparse, urljoin
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
from tld import get_tld
import itertools

from app import utils
from .baseThread import BaseThread

logger = utils.get_logger()

min_length = 100
max_length = 50*1024
read_timeout = 60
bool_ratio = 0.8
concurrency_count = 6

class URL():
    def __init__(self, url, payload):
        self.url = url
        self.payload = payload
        self._scope = None
        self._path = None

    def __ne__(self, other):
        return not self.__eq__(other)

    def __eq__(self, other):
        if isinstance(other, URL):
            return self.url == other.url
        else:
            return False

    def __hash__(self):
        return hash(self.url)


    def __str__(self):
        return self.url

    def __repr__(self):
        return "<URL> " + self.__str__()

    def __lt__(self, other):
        return self.url < other.url

    def __gt__(self, other):
        return self.url > other.url

    @property
    def scope(self) -> str:
        if self._scope is None:
            parse = urlparse(self.url)
            scope = "{}://{}".format(parse.scheme, parse.netloc)
            self._scope = scope

        return self._scope

    @property
    def path(self) -> str:
        if self._path is None:
            parse = urlparse(self.url)
            self._path = parse.path

        return self._path

class HTTPReq():
    def __init__(self, url: URL , read_timeout = 60, max_length = 50*1024):
        self.url = url
        self.read_timeout = read_timeout
        self.max_length = max_length
        self.conn = None
        self.status_code = None
        self.content = None

    def req(self):
        content = b''
        conn = utils.http_req(self.url.url, 'get', timeout=(3, 6), stream=True)
        self.conn = conn
        start_time = time.time()
        for data in conn.iter_content(chunk_size=512):
            if time.time() - start_time >= self.read_timeout:
                break
            content += data
            if len(content) >= int(self.max_length):
                break

        self.status_code = conn.status_code
        self.content = content[:self.max_length]

        content_len = self.conn.headers.get("Content-Length", len(self.content))
        self.conn.headers["Content-Length"] = content_len

        conn.close()

        return self.status_code, self.content




class Page():
    def __init__(self, req: HTTPReq):
        self.raw_req = req
        self.url = req.url
        self.content = req.content
        self.body_length = len(self.content)
        self.times = 0
        self.status_code = req.status_code
        self._title = None
        self._location_url = None
        self._is_back_up_path = None
        self._is_back_up_page = None
        self.back_up_suffix_list = [".tar", ".tar.gz", ".zip", ".rar", ".7z", ".bz2", ".gz", ".war"]
        self.clean_content = self.content.replace(self.url.payload.encode(), b"")

    def __eq__(self, other):
        """
        [第一性原理：假 404 页面的终极对抗算法 (页面相似度)]
        Web 扫描最头疼的就是“软 404”：你随便访问一个不存在的路径，服务器居然给你返回 200 OK，并展示一个“抱歉，页面找不到”的自建页面。
        如果你单纯用 HTTP 状态码去判断，那所有的文件都会被误报为“存在”。
        这里的 __eq__ 是整个模块的灵魂。它的核心思想是：判断两个页面是否本质上是同一个页面（即使它们因为动态时间、动态路径有微小的差别）。
        """
        if isinstance(other, Page):
            # 1. 状态码不同，肯定不是同一个页面
            if self.status_code != other.status_code:
                return False

            # 2. 如果两者都是 302 跳转
            if self.is_302() and other.is_302():
                self_new_url = self.location_url
                other_new_url = other.location_url

                self_new_url = urljoin(self.url.url, self_new_url)
                other_new_url = urljoin(other.url.url, other_new_url)

                if self_new_url.endswith(self.url.payload+ "/"):
                    if other_new_url.endswith(other.url.payload + "/"):
                        if not self.url.payload.endswith("/") and not other.url.payload.endswith("/"):
                            return False

                self_new_path = urlparse(self_new_url).path
                other_new_path = urlparse(other_new_url).path

                # 把各自请求的特定 payload 替换成统一的占位符 $AAAA$，然后比对跳转路径是否一致
                path1 = self_new_path.replace(self.url.payload, "$AAAA$")
                path2 = other_new_path.replace(other.url.payload, "$AAAA$")

                if urlparse(self_new_url).netloc == urlparse(other_new_url).netloc:
                    if path1 == path2 and self_new_path.endswith("$AAAA$/"):
                        if not self.url.payload.endswith("/") and not other.url.payload.endswith("/"):
                            return False

                if path1 == path2:
                    self.times += 1
                    return True
                else:
                    return False

            # 3. 如果是 200 OK 的页面，使用已经抹去页面里反射回来的 payload 的 clean_content
            self_content = self.clean_content
            other_content = other.clean_content
            
            if self_content == other_content:
                self.times += 1
                return True

            # 如果两个页面的大小差距在 5 个字节以内，直接认为一模一样！(应对极其微小的动态时间戳差异)
            if abs(len(self_content) - len(other_content)) <= 5:
                self.times += 1
                return True

            # 如果页面大小差距极大（超过10%或500字节），那绝对是两个不同的页面
            min_len_content = min(len(self_content),  len(other_content))
            if abs(len(self_content) - len(other_content)) >= max(500, int(min_len_content*0.1)):
                return False

            # 【终极武器】：使用 difflib 计算两个页面的特征切片文本相似度，超过 80% (bool_ratio) 就认为是相同的 404 页面
            # 截取前 4KB 特征切片比对，避免全量 50KB 构建庞大字符索引表引发的 CPU 100% 与堆内存碎片化
            s_sample = self_content[:4096] if len(self_content) > 4096 else self_content
            o_sample = other_content[:4096] if len(other_content) > 4096 else other_content
            quick_ratio = difflib.SequenceMatcher(None, s_sample, o_sample).quick_ratio()
            if quick_ratio >= bool_ratio:
                self.times += 1
                return True
            else:
                return False

        else:
            return False

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        p = urlparse(self.url.url)
        return hash(p.scheme + "://" + p.netloc)

    @property
    def location_url(self) -> str:
        if self._location_url is None:
            location = self.raw_req.conn.headers.get("Location", "")
            new_url = urljoin(self.url.url, location)
            self._location_url =  new_url.split("?")[0]

        return self._location_url

    def is_302(self):
        return self.status_code in [301, 302, 307, 308]


    @property
    def title(self) -> str:
        if self._title is None:
            self._title = utils.get_title(self.content).strip()

        return self._title

    @property
    def is_backup_path(self) -> bool:
        if self._is_back_up_path is None:
            for suffix in self.back_up_suffix_list:
                if self.url.path.endswith(suffix):
                    self._is_back_up_path = True
                    return self._is_back_up_path

            self._is_back_up_path = False

        return self._is_back_up_path

    @property
    def is_backup_page(self) -> bool:
        if self._is_back_up_page is None:
            content_type = self.raw_req.conn.headers.get("Content-Type", "")
            if "application" in content_type.lower():
                self._is_back_up_page = True
            else:
                self._is_back_up_page = False

        return self._is_back_up_page

    def __str__(self):
        msg = "[{}][{}][{}]{}".format(self.status_code, self.title, len(self.content), self.url)
        return msg

    def __repr__(self):
        return "<Page> "+ self.__str__()

    def dump_json(self):
        item = {
            "title": self.title,
            "url": str(self.url),
            "content_length": len(self.content),
            "status_code": self.status_code,
        }

        return item


class FileLeak(BaseThread):
    """
    [第一性原理：底层武器库 - 敏感文件泄露探针]
    这个类的核心职责不是“发请求”，而是“证伪”。
    扫描器最怕的是海量的 False Positive（误报）。这个类花了一半以上的代码在做“双重验证”。
    """
    def __init__(self, target, urls, concurrency=8):
        super().__init__(urls, concurrency = concurrency)
        self.target = target.rstrip("/") + "/"
        self.urls = urls
        # 【基准 404 测试路径】：一个绝对不可能存在的路径。
        # 用来打底，看看服务器在遇到真 404 的时候到底会返回什么妖魔鬼怪。
        self.path_404 = "not_found_2222_111"
        self.page404_set = set() # 存放所有被判定为“假页面”的黑名单集合
        self.page200_set = set() # 存放初步判定为成功的页面
        self.page200_code_list = [200, 301, 302, 500]
        # 【黑名单正则与特征】：一旦网页 Title 或 Body 里有这些，就一棍子打死，认为是 404 页面
        self.page404_title = ["404", "不存在", "错误", "403", "禁止访问", "请求含有不合法的参数"]
        self.page404_title.extend(["网络防火墙", "访问拦截", "由于安全原因JSP功能默认关闭"])
        self.page404_content = [b'<script>document.getElementById("a-link").click();</script>']
        self.location404 = ["/auth/login/", "error.html"]
        self.page_all = []
        self.error_times = 0
        self.record_page = False
        self.skip_302 = False
        self.location_404_url = set()
        self.is_spa_wildcard = False

    def work(self, url):
        if self.error_times >= 20:
            return
        req = self.http_req(url)
        page = Page(req)

        if self.record_page:
            self.page_all.append(page)

        # 如果一眼看去就是典型的 404 页面，直接扔进黑名单垃圾桶
        if self.is_404_page(page):
            self.page404_set.add(page)
            return

        # 如果它初步看起来像是真的（没有命中黑名单特征），先放入白名单
        if page not in self.page404_set:
            self.page200_set.add(page)

    def build_404_page(self):
        """
        【第一性原理：动态基线学习】
        1. 请求基础 404 测试路径 /not_found_2222_111
        2. 发起随机 Hash 路径探测，识别 SPA 路由与 CDN 泛 200 行为
        """
        import uuid
        url_404 = URL(self.target + self.path_404, self.path_404)
        logger.info("req => {}".format(url_404))
        page_404 = Page(self.http_req(url_404))
        self.page404_set.add(page_404)
        if self.record_page:
            self.page_all.append(page_404)

        if page_404.is_302():
            self.location_404_url.add(page_404.location_url)

        if page_404.is_302() and page_404.location_url.endswith(page_404.url.payload + "/"):
            self.skip_302 = True

        # 发送第二个随机探测包判定 SPA 泛解析
        try:
            rand_path = f"chk_probe_{uuid.uuid4().hex[:8]}"
            url_rand = URL(self.target + rand_path, rand_path)
            page_rand = Page(self.http_req(url_rand))
            self.page404_set.add(page_rand)
            if page_404.status_code == 200 and page_rand.status_code == 200:
                content_type = page_404.raw_req.conn.headers.get("Content-Type", "")
                if "text/html" in content_type.lower() or "application/xhtml" in content_type.lower():
                    self.is_spa_wildcard = True
                    logger.info("Target {} detected as SPA / Wildcard 200 Catch-All".format(self.target))
        except Exception:
            pass

    def http_req(self, url: URL):
        try:
            req = HTTPReq(url)
            req.req()
            return req
        except Exception as e:
            logger.warning("error on {}".format(e))
            self.error_times += 1
            raise e

    def run(self):
        t1 = time.time()
        logger.info("start fileleak {}".format(len(self.targets)))

        self.build_404_page()

        self._run()

        self.check_page_200()

        elapse = time.time() - t1
        logger.info("end fileleak elapse {}".format(elapse))

        return self.page200_set

    def verify_magic_signature(self, page: Page) -> bool:
        """
        【高危敏感文件真实魔数/特征强校验】
        针对 Git、SVN、源码压缩包、Actuator、Swagger、配置文件进行真实性校验
        """
        path_lower = page.url.path.lower()
        content = page.content
        if not content:
            return False

        content_str = ""
        try:
            content_str = content[:2048].decode('utf-8', errors='ignore')
        except Exception:
            pass

        # 1. 过滤明显的 HTML 404 / 默认错误页假 200
        is_html = content.lstrip().startswith(b"<!doctype") or content.lstrip().startswith(b"<html") or "<title>" in content_str.lower()

        # 2. 如果判定为 SPA 单页应用，且不是明确的 API/二进制接口，过滤所有普通 HTML
        if getattr(self, 'is_spa_wildcard', False) and is_html:
            if "swagger-ui" not in content_str.lower():
                return False

        # 3. Git 泄露校验
        if "/.git/" in path_lower or path_lower.endswith("/.git"):
            if b"[core]" in content or b"repositoryformatversion" in content or b"ref: refs/heads/" in content or b"PACK" in content[:16]:
                return True
            return False

        # 4. SVN 泄露校验
        if "/.svn/" in path_lower or path_lower.endswith("/.svn"):
            if b"svn://" in content or b"dir\n" in content or (content[:4].isdigit()):
                return True
            return False

        # 5. 压缩包与备份文件校验 (.zip, .rar, .7z, .tar.gz, .bak, .sql)
        backup_exts = [".zip", ".rar", ".7z", ".tar.gz", ".tgz", ".tar", ".bak", ".sql", ".dump"]
        if any(path_lower.endswith(ext) for ext in backup_exts):
            if is_html or content.lstrip().startswith(b"{\"code\"") or content.lstrip().startswith(b"{\"msg\""):
                return False
            if path_lower.endswith(".zip") and not (content.startswith(b"PK\x03\x04") or content.startswith(b"PK\x05\x06")):
                return False
            if path_lower.endswith(".rar") and not content.startswith(b"Rar!"):
                return False
            if path_lower.endswith(".7z") and not content.startswith(b"7z\xbc\xaf"):
                return False
            if path_lower.endswith(".sql"):
                sql_kws = ["create table", "insert into", "-- mysql", "drop table", "database"]
                if not any(kw in content_str.lower() for kw in sql_kws):
                    return False
            return True

        # 6. Spring Boot Actuator 校验
        if "/actuator/" in path_lower or path_lower.endswith("/actuator"):
            if is_html:
                return False
            actuator_kws = ["contexts", "_links", "names", "beans", "health", "metrics", "mappings", "status"]
            if any(kw in content_str.lower() for kw in actuator_kws):
                return True
            return False

        # 7. Swagger / OpenAPI 校验
        if any(kw in path_lower for kw in ["swagger", "api-docs", "openapi"]):
            if "swagger" in content_str.lower() or "openapi" in content_str.lower() or "paths" in content_str.lower() or "swagger-ui" in content_str.lower():
                return True
            return False

        # 8. 敏感配置文件 (.env, .yml, .yaml, .properties, .conf, .ini, secrets)
        config_exts = [".env", ".yml", ".yaml", ".properties", ".conf", ".ini", "secrets.yml", "config.json"]
        if any(path_lower.endswith(ext) or ext in path_lower for ext in config_exts):
            if is_html:
                return False

        return True

    def is_404_page(self, page: Page):
        if page.status_code not in self.page200_code_list:
            return True

        if not self.verify_magic_signature(page):
            return True

        if page.is_backup_path:
            if not page.is_backup_page:
                return True

        for title in self.page404_title:
            if title in page.title:
                return True

        for content in self.page404_content:
            if content in page.content:
                return True

        if "/." in page.url.url and page.status_code == 200:
            if len(page.content) == 0:
                return True

        if page.is_302():
            for location_404 in self.location404:
                if location_404 in page.location_url:
                    return True

            if not page.location_url.endswith(page.url.payload + "/"):
                self.location_404_url.add(page.location_url)
                return True

            return page.location_url in self.location_404_url

        return False

    def check_page_200(self):
        """
        [第一性原理：证伪算法 (False Positive Mitigation)]
        通过 1337 扰乱测试与真实特征强校验双重过滤
        """
        for page in self.page200_set:
            if page in self.page404_set:
                continue

            if self.skip_302:
                self.page404_set.add(page)
                continue

            # 生成对应的加了 1337 扰乱字符的对照 URL
            url_404_list = self.gen_check_url(page.url)

            for url_404 in url_404_list:
                page_404 = Page(self.http_req(url_404))
                # 将扰乱测试页面加入黑名单库
                self.page404_set.add(page_404)

                if page_404.is_302() and page_404.location_url.endswith(page_404.url.payload + "/"):
                    self.page404_set.add(page)
                    self.skip_302 = True

        # 最终真理：从白名单中剔除掉所有与黑名单相似度过高的页面
        self.page200_set -= self.page404_set

        # 二次强校验过滤
        valid_pages = set()
        for page in self.page200_set:
            if self.verify_magic_signature(page):
                valid_pages.add(page)
            else:
                logger.info("Discarded false positive by magic signature: {}".format(page.url))
        self.page200_set = valid_pages


    def gen_check_url(self, url: URL):
        """
        生成用于证伪测试的 URL (就是在这个原本认为是正确的 url 后面拼上 a1337)
        """
        payload = url.payload
        if url.path in url.scope:
            check_url = url.url + "1337"
        else:
            check_url = url.url.replace(url.path, url.path + "1337")
        end_check_url = URL(check_url, payload + "1337")

        payload_list = ["..", "?", "etc/passwd"]
        for p in payload_list:
            if p in payload:
                check_url = url.url.replace(p, p + "a1337")
                payload = payload.replace(p, p + "a1337")
                return [URL(check_url, payload)]

        if "." in url.path and "." in payload:
            path = url.path.replace(".", "a1337.")
            check_url = "{}{}".format(url.scope, path)
            payload = payload.replace(".", "a1337.")
            return [URL(check_url, payload), end_check_url]

        if url.path.endswith("/"):
            path = url.path[:-1] + "a1337/"
            check_url = "{}{}".format(url.scope, path)
            payload = payload + "a1337/"
            return [URL(check_url, payload)]

        return [end_check_url]

def normal_url(url):
    scheme_map = {
        'http': 80,
        "https": 443
    }
    o = urlparse(url)

    scheme = o.scheme
    hostname = o.hostname
    path = o.path

    if scheme not in scheme_map:
        return ""

    if o.path == "":
        path = "/"


    if o.port == scheme_map[o.scheme] or o.port is None:
        ret_url = "{}://{}{}".format(scheme, hostname, path)

    else:
        ret_url = "{}://{}:{}{}".format(scheme, hostname, o.port, path)

    if o.query:
        ret_url = ret_url + "?" + o.query

    return ret_url


import os




class GenBackDicts:
    """
    [第一性原理：动态指纹生成字典]
    死板的扫描器只知道加载一份固定的 backup.zip 字典去跑。
    高级的扫描器会基于“当前目标特征”去动态生成字典。
    比如遇到 target.com/admin/ 目录，它会把 target/admin 拆开，
    自动组合出 target.zip, target.tar.gz, admin.rar 等高命中率的压缩包字典。
    """
    def __init__(self, url):
        self.target = normal_url(url)
        self.suffixs = [".tar", ".tar.gz", ".zip", ".rar", ".7z", ".bz2", ".gz", "_bak.rar", ".war"]
        self.backup_path_deep = 7
        self.dymaic_dicts_deep = 5
        self.path = urlparse(self.target).path


    def gen_dict_from_domain(self):
        """基于域名切词：比如 news.baidu.com -> news.zip, baidu.rar"""
        result = []
        res = get_tld(self.target, as_object=True, fail_silently=True)
        if res:
            result = [x for x in [str(res.parsed_url.netloc).split(":")[0], res.fld, res.subdomain,
                                 res.domain] + res.subdomain.split(".") if x != ""]

        return set(result)

    def gen_backup_dicts(self, nemes):
        """做笛卡尔积组合，生成爆炸式的组合字典"""
        out = []
        items = itertools.product(nemes, self.suffixs)
        for x in items:
            out.append("".join(x))
        return out

    def gen_dict_from_path(self):
        """基于路径切词：比如 /api/v1/auth/ -> auth.zip"""
        out = []
        dirs = os.path.dirname(self.path).split("/")
        if len(dirs)> 1 and dirs[-1]:
            out = self.gen_backup_dicts([dirs[-1]])
        return out


    def gen(self):
        """字典生成总线"""
        ret = set()
        names = self.gen_dict_from_domain()

        for x in  self.gen_backup_dicts(names):
            ret.add(URL(urljoin(self.target, x), x))

        for x in  self.gen_dict_from_path():
            ret.add(URL(urljoin(self.target, x), x))
            ret.add(URL(urljoin(self.target, "./../"+ x), x))

        return ret


class GenURL():
    def __init__(self, target, dicts):
        self.target = normal_url(target).split("?")[0]
        self.dicts = set(dicts)
        self.urls = set()

    def build_urls(self):
        target = os.path.dirname(self.target)
        for d in self.dicts:
            u = URL("{}/{}".format(target, d.strip()), d.strip())
            self.urls.add(u)

    def gen(self, flag = True):
        if urlparse(self.target).path == "/":
            self.dicts |= GenBackDicts(self.target).gen_dict_from_domain()

        self.build_urls()
        if flag:
            self.urls |=  GenBackDicts(self.target).gen()

        return self.urls

from typing import  List

def file_leak(targets, dicts, gen_dict = True) -> List[Page]:
    all_gen_url = set()
    map_url = dict()

    for site in targets:
        site = normal_url(site.strip())
        if not site:
            continue

        map_url[URL(site, "").scope] = set()
        a = GenURL(site, dicts)
        all_gen_url |= a.gen(gen_dict)

    for url in all_gen_url:
        map_url[url.scope].add(url)

    cnt = 0
    len(map_url)
    ret = []
    for target in map_url:
        cnt += 1

        try:
            f = FileLeak(target, map_url[target], concurrency_count)
            pages = f.run()
            for page in pages:
                logger.info("found => {}".format(page))

            ret.extend(pages)
        except Exception as e:
            logger.info("error on {}, {}".format(target, e))
            logger.exception(e)

    return ret

