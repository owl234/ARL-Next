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

            # 3. 如果是 200 OK 的页面，抹去页面里反射回来的 payload（防止因为路径回显导致页面不一样）
            self_content = self.content.replace(self.url.payload.encode(), b"")
            other_content = other.content.replace(other.url.payload.encode(), b"")

            # 如果两个页面的大小差距在 5 个字节以内，直接认为一模一样！(应对极其微小的动态时间戳差异)
            if abs(len(self_content) - len(other_content)) <= 5:
                self.times += 1
                return True

            # 如果页面大小差距极大（超过10%或500字节），那绝对是两个不同的页面
            min_len_content = min(len(self_content),  len(other_content))
            if abs(len(self_content) - len(other_content)) >= max(500, int(min_len_content*0.1)):
                return False

            # 如果 Title 相同，认为是同一类页面（比如都有同样的错误标题）
            if len(self.title) > 2 and self.title == other.title:
                return True

            # 【终极武器】：使用 difflib 计算两个页面的文本相似度，超过 80% (bool_ratio) 就认为是相同的 404 页面
            quick_ratio = difflib.SequenceMatcher(None, self_content, other_content).quick_ratio()
            if quick_ratio >= bool_ratio:
                self.times +=1
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
        # 但注意，接下来它还要经受 check_page_200() 的地狱级拷问
        if page not in self.page404_set:
            self.page200_set.add(page)


    def build_404_page(self):
        """
        [第一性原理：建立基线]
        扫描开始前的第一件事，就是访问 /not_found_2222_111，
        把服务器的“真实 404 反馈面貌”记录下来，加入黑名单库 (self.page404_set)。
        后面任何跟它“长得像”（通过 Page.__eq__ 相似度对比）的页面，都会被直接干掉。
        """
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

    def run(self):
        """
        [第一性原理：扫描三部曲]
        1. 建立 404 基线 (build_404_page)
        2. 多线程狂奔，并发探测所有字典路径 (_run)
        3. 对所有初步成活的结果进行二次证伪 (check_page_200)
        """
        t1 = time.time()
        logger.info("start fileleak {}".format(len(self.targets)))

        self.build_404_page()

        self._run()

        self.check_page_200()

        elapse = time.time() - t1
        logger.info("end fileleak elapse {}".format(elapse))

        return self.page200_set

    def http_req(self, url: URL):
        try:
            req = HTTPReq(url)
            req.req()
            return req
        except Exception as e:
            logger.warning("error on {}".format(e))
            self.error_times += 1
            raise e

    def is_404_page(self, page: Page):
        if page.status_code not in self.page200_code_list:
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
        这是防止误报的最强防线。
        假设你扫到了一个 /admin.php 返回 200 OK，并且内容看起来也很正常。怎么证明它是真的？
        很简单：你在后面加点垃圾字符，去请求 /admin.php1337。
        如果 /admin.php1337 也返回 200 OK 且页面相似，那说明这整个目录都在骗人，/admin.php 也是假的！
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

        # 最终真理：从白名单中剔除掉所有与黑名单（基线404和1337测试页面）相似度过高的页面
        # 这里的相减操作 `-=` 底层会狂热调用 Page.__eq__ 的文本相似度算法！
        self.page200_set -= self.page404_set


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
    total = len(map_url)
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

