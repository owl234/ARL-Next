import time
import socket
import re
from collections import defaultdict
from urllib.parse import urlparse
from bson import ObjectId
from app import utils
from app import services
from app.config import Config
from contextlib import contextmanager
import traceback
import threading
from app.modules import CollectSource, WebSiteFetchStatus, WebSiteFetchOption
from app.services.nuclei_scan import nuclei_scan
from app.services import run_risk_cruising, BaseUpdateTask
try:
    import simhash
except ImportError:
    simhash = None
logger = utils.get_logger()


class TaskHeartbeat(object):
    """
    轻量级后台心跳守护器：
    1. 进入阶段（__enter__）立即执行一次心跳落库（Zero-delay Flush），消除短阶段与冷启动空白；
    2. 运行期间每隔 interval 秒由后台守护线程向 MongoDB 刷新 last_updated 与 update_date；
    3. 退出阶段（__exit__）补齐最终一次心跳 Flush，确保多阶段无缝衔接；
    4. 兼顾常规扫描任务（task）与 GitHub 任务（github_task）。
    """
    def __init__(self, task_id: str, interval: int = 60):
        self.task_id = str(task_id) if task_id else None
        self.interval = interval
        self._stop_event = threading.Event()
        self._thread = None

    def _flush_heartbeat(self):
        if not self.task_id or self.task_id == "global":
            return
        from bson import ObjectId
        try:
            now_ts = time.time()
            curr_d = utils.curr_date()
            ret = utils.conn_db('task').update_one(
                {"_id": ObjectId(self.task_id)},
                {"$set": {"last_updated": now_ts, "update_date": curr_d}}
            )
            if ret.matched_count == 0:
                utils.conn_db('github_task').update_one(
                    {"_id": ObjectId(self.task_id)},
                    {"$set": {"last_updated": now_ts, "update_date": curr_d}}
                )
        except Exception:
            pass

    def __enter__(self):
        if not self.task_id or self.task_id == "global":
            return self
        # 1. 进入时立即执行一次心跳落库
        self._flush_heartbeat()
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._thread:
            self._stop_event.set()
        # 2. 退出时补齐最后一次心跳落库
        self._flush_heartbeat()
        return False

    def _run(self):
        while not self._stop_event.wait(self.interval):
            self._flush_heartbeat()



# 任务类中一些相关公共类
class CommonTask(object):
    def __init__(self, task_id):
        self.task_id = task_id

    @contextmanager
    def safe_phase(self, phase_name: str, base_update=None):
        if base_update:
            base_update.update_task_field("status", phase_name)
        logger.info(f"Start phase: {phase_name} for task {self.task_id}")
        t1 = time.time()
        with TaskHeartbeat(self.task_id, interval=60):
            try:
                yield
            except Exception as e:
                logger.error(f"[容错阻断] 阶段 {phase_name} 发生致命错误: {e}")
                logger.error(traceback.format_exc())
                if base_update:
                    base_update.update_task_field("error_msg", str(e))
                    base_update.update_services(f"{phase_name}_error", 0.0)
            finally:
                elapse = time.time() - t1
                logger.info(f"End phase: {phase_name} for task {self.task_id}, cost: {elapse:.2f}s")
                if base_update:
                    base_update.update_services(phase_name, elapse)

    def insert_task_stat(self):
        query = {
            "_id": ObjectId(self.task_id)
        }

        stat = utils.arl.task_statistic(self.task_id)

        logger.info("insert task stat")

        update = {"$set": {"statistic": stat}}

        utils.conn_db('task').update_one(query, update)

    def insert_finger_stat(self):
        finger_stat_map = utils.arl.gen_stat_finger_map(self.task_id)
        logger.info("insert finger stat {}".format(len(finger_stat_map)))

        for key in finger_stat_map:
            data = finger_stat_map[key].copy()
            data["task_id"] = self.task_id
            utils.safe_insert_asset('stat_finger', ['task_id', 'name'], data)

    def insert_cip_stat(self):
        cip_map = utils.arl.gen_cip_map(self.task_id)
        logger.info("insert cip stat {}".format(len(cip_map)))

        for cidr_ip in cip_map:
            item = cip_map[cidr_ip]
            ip_list = list(item["ip_set"])
            domain_list = list(item["domain_set"])

            data = {
                "cidr_ip": cidr_ip,
                "ip_count": len(ip_list),
                "ip_list": ip_list,
                "domain_count": len(domain_list),
                "domain_list": domain_list,
                "task_id": self.task_id
            }

            utils.safe_insert_asset('cip', ['task_id', 'cidr_ip'], data)

    # 资产同步
    def sync_asset(self):
        options = getattr(self, 'options', {})
        if not options:
            logger.warning("not found options {}".format(self.task_id))
            return

        related_scope_id = options.get("related_scope_id", "")
        if not related_scope_id or len(related_scope_id) != 24:
            self._push_task_result_only()
            return

        services.sync_asset(task_id=self.task_id, scope_id=related_scope_id, push_flag=True)

        from app.utils.monitor_diff import log_monitor_diff_summary
        log_monitor_diff_summary(self.task_id)

    def _push_task_result_only(self):
        asset_map = {"domain": [], "ip": [], "site": [], "task_name": ""}
        asset_counter = {"domain": 0, "ip": 0, "site": 0}

        task_info = utils.conn_db('task').find_one({"_id": ObjectId(self.task_id)})
        if task_info:
            asset_map["task_name"] = task_info.get("name", "")

        for category in ["domain", "ip", "site"]:
            items = list(utils.conn_db(category).find({"task_id": self.task_id}))
            asset_counter[category] = len(items)
            asset_map[category] = items[:10]

        utils.message_push(
            asset_map=asset_map, 
            asset_counter=asset_counter, 
            update_map=asset_map, 
            update_counter=asset_counter
        )

    def common_run(self):
        self.insert_finger_stat()
        self.insert_cip_stat()
        self.insert_task_stat()
        self.sync_asset()


# *** 对用户提交的站点或者是发现的站点进行后续处理
class WebSiteFetch(object):
    def __init__(self, task_id: str, sites: list, options: dict, scope_domain: list = None, domain_black_list: list = None):
        self.task_id = task_id
        self.sites = sites  # ** 这个是用户提交的目标
        self.options = options
        self.base_update_task = BaseUpdateTask(self.task_id)
        self.site_info_list = []  # *** 这个是来自 services.fetch_site 的结果
        self.available_sites = []  # *** 这个是存活的站点
        self.web_analyze_map = dict()
        self.wih_domain_set = set()  # 用于保存来自wih的域名，已添加的域名不再添加
        self.wih_record_set = set()  # 用于保存来自wih的记录，已添加的记录不再添加

        # 用于判断应该收集的子域名
        if not scope_domain:
            scope_domain = []
            
        if not domain_black_list:
            domain_black_list = []

        self.scope_domain = scope_domain
        self.domain_black_list = domain_black_list
        self.page_url_set = set()
        self.search_engines_result = dict()
        self.catch_all_sites = set()  # 独立持久化集合，保存泛解析/默认后端站点（防止内存清空后状态丢失）
        self._poc_sites = None  # 用于PoC 执行， 文件目录爆破 的目标
        self._task_domain_set = None  # 用于保存任务中的域名

    @property
    def task_domain_set(self):
        if self._task_domain_set is None:
            self._task_domain_set = set(utils.arl.get_domain_by_id(self.task_id))

        return self._task_domain_set

    def site_identify(self):
        # ** 调用指纹识别
        self.web_analyze_map = services.web_analyze(self.available_sites)

    def __str__(self):
        return "<WebSiteFetch> task_id:{}, sites: {}, available_sites:{}".format(
            self.task_id, len(self.sites), len(self.available_sites))

    def save_site_info(self):
        # [第一性原理：防御重复站点] 查询该 task_id 目前数据库中已有的 site 列表
        existing_sites = set()
        for doc in utils.conn_db('site').find({'task_id': self.task_id}, {'site': 1}):
            existing_sites.add(doc.get('site'))
            
        deduplicated_site_info_list = []
        seen_sites_in_list = set()

        for site_info in self.site_info_list:
            curr_site = site_info["site"]
            
            # 若数据库已存在，或本次列表内已出现过，则剔除
            if curr_site in existing_sites or curr_site in seen_sites_in_list:
                continue
                
            seen_sites_in_list.add(curr_site)
            deduplicated_site_info_list.append(site_info)

            site_path = "/image/" + self.task_id
            file_name = '{}/{}.jpg'.format(site_path, utils.gen_filename(curr_site))
            site_info["task_id"] = self.task_id
            site_info["screenshot"] = file_name

            # 调用读取站点识别的结果，并且去重
            if self.web_analyze_map:
                finger_list = self.web_analyze_map.get(curr_site, [])
                known_finger_set = set()
                for finger_item in site_info["finger"]:
                    known_finger_set.add(finger_item["name"].lower())

                for analyze_finger in finger_list:
                    analyze_name = analyze_finger["name"].lower()
                    if analyze_name not in known_finger_set:
                        site_info["finger"].append(analyze_finger)

        self.site_info_list = deduplicated_site_info_list
        from app.utils.monitor_diff import tag_monitor_diff
        
        filtered_list = []
        for info in self.site_info_list:
            tag_monitor_diff("site", info)
            if info.get("change_status") != "unchanged":
                filtered_list.append(info)
                
        self.site_info_list = filtered_list

        logger.info("save_site_info site:{}, {}".format(len(self.site_info_list), self.__str__()))
        if self.site_info_list:
            from pymongo import UpdateOne
            operations = []
            for info in self.site_info_list:
                operations.append(UpdateOne(
                    {'task_id': info['task_id'], 'site': info['site']},
                    {'$set': info},
                    upsert=True
                ))
            if operations:
                utils.conn_db('site').bulk_write(operations)

    def site_screenshot(self):
        # ***站点截图***
        capture_save_dir = Config.SCREENSHOT_DIR + "/" + self.task_id
        services.site_screenshot(self.available_sites, concurrency=4, capture_dir=capture_save_dir)

    def site_spider(self):
        # *** 执行静态爬虫
        entry_urls_list = []  # 是一个二维数组
        for site in self.available_sites:
            o = urlparse(site)
            if o.path != "":
                continue

            entry_urls = [site]
            entry_urls.extend(self.search_engines_result.get(site, []))
            entry_urls_list.append(entry_urls)

        site_spider_result = services.site_spider_thread(entry_urls_list)
        spider_urls = []
        for site in site_spider_result:
            target_urls = site_spider_result[site]
            new_target_urls = []
            for url in target_urls:
                if url in self.page_url_set:
                    continue
                new_target_urls.append(url)

                self.page_url_set.add(url)

            if not new_target_urls:
                continue

            spider_urls.extend(new_target_urls)

        if len(spider_urls) > 0:
            logger.info("spider_urls {} task_id:{}".format( len(spider_urls), self.task_id))
            page_map = services.page_fetch(spider_urls)
            for url in page_map:
                item = build_url_item(url, self.task_id, source=CollectSource.SITESPIDER)
                item.update(page_map[url])
                item["task_id"] = self.task_id
                utils.safe_insert_asset('url', ['task_id', 'url'], item)

    CATCH_ALL_CONTROL_TIMEOUT = 6.1
    CATCH_ALL_CONTROL_CONCURRENCY = 6
    CATCH_ALL_CONTROL_MAX_ENTRY = 30
    CATCH_ALL_CONTROL_SIMHASH_DISTANCE = 3

    @staticmethod
    def _wildcard_parent(hostname):
        """提取用于随机 Host 探测的父级域名，支持二级公共后缀与纯 IP 早退"""
        if not hostname:
            return None

        hostname = hostname.strip().strip(".").lower()
        if utils.is_vaild_ip_target(hostname):
            return None

        fld = utils.get_fld(hostname) or ""
        parent = hostname.split(".", 1)[1] if "." in hostname else ""
        if parent and fld and parent.endswith(fld):
            return parent

        return fld or None

    @classmethod
    def _simhash_within_distance(cls, simhash_a, simhash_b, max_distance=None):
        """容忍默认后端页面里的时间戳 / 随机 token：按汉明距离判定"""
        if max_distance is None:
            max_distance = cls.CATCH_ALL_CONTROL_SIMHASH_DISTANCE

        if str(simhash_a) == str(simhash_b):
            return True

        try:
            val_a = int(simhash_a)
            val_b = int(simhash_b)
            distance = bin(val_a ^ val_b).count("1")
            return distance <= max_distance
        except Exception:
            pass

        if simhash:
            try:
                distance = simhash.Simhash(int(simhash_a)).distance(simhash.Simhash(int(simhash_b)))
                return distance <= max_distance
            except Exception:
                return False

        return False

    def _probe_catch_all_reference(self, url, host_header):
        """请求一次，取回用于比对的响应快照；失败返回 None"""
        try:
            conn = utils.http_req(url, headers={"Host": host_header},
                                  timeout=self.CATCH_ALL_CONTROL_TIMEOUT,
                                  allow_redirects=True)
        except Exception:
            return None

        content = conn.content or b""
        body_simhash = ""
        if simhash:
            try:
                body_simhash = str(simhash.Simhash(conn.text).value)
            except Exception:
                body_simhash = ""

        return {
            "status": conn.status_code,
            "title": utils.get_title(content),
            "body_length": len(content),
            "simhash": body_simhash,
        }

    def _fetch_catch_all_reference(self, ip, scheme, port, hostname):
        """
        双探针交叉验证基准快照：
        并发发送 2 个随机标签 Host 对照请求，
        仅当两个探针响应状态码一致且 SimHash 汉明距离 <= 3 时确立有效基准；
        否则视为网络抖动或 WAF 频控/挑战页干扰，放弃确立基准以防全站误判。
        """
        parent = self._wildcard_parent(hostname)
        if not parent:
            return None

        rand_tag_1 = "wf" + utils.random_choices(6) + "." + parent
        rand_tag_2 = "wf" + utils.random_choices(6) + "." + parent

        ip_netloc = "[{}]".format(ip) if ":" in ip else ip
        netloc = "{}:{}".format(ip_netloc, port)
        base_url = "{}://{}/".format(scheme, netloc)

        snap1 = None
        snap2 = None
        try:
            with utils.ContextAwareThreadPoolExecutor(max_workers=2) as executor:
                f1 = executor.submit(self._probe_catch_all_reference, base_url, rand_tag_1)
                f2 = executor.submit(self._probe_catch_all_reference, base_url, rand_tag_2)
                snap1 = f1.result()
                snap2 = f2.result()
        except Exception as e:
            logger.debug("dual-probe catch_all reference error: {}".format(e))
            return None

        # 若直连 IP 失败且 DNS 存在泛解析，降级尝试随机域名直连
        if not snap1 or not snap2:
            if utils.get_ip(rand_tag_1, log_flag=False):
                url1 = "{}://{}:{}/".format(scheme, rand_tag_1, port)
                url2 = "{}://{}:{}/".format(scheme, rand_tag_2, port)
                try:
                    with utils.ContextAwareThreadPoolExecutor(max_workers=2) as executor:
                        f1 = executor.submit(self._probe_catch_all_reference, url1, rand_tag_1)
                        f2 = executor.submit(self._probe_catch_all_reference, url2, rand_tag_2)
                        snap1 = f1.result()
                        snap2 = f2.result()
                except Exception:
                    return None

        if not snap1 or not snap2:
            return None

        # 双探针交叉校验：状态码一致且正文 SimHash 接近
        if snap1.get("status") != snap2.get("status"):
            logger.info("catch_all baseline rejected for entry {}: status inconsistent ({} vs {})".format(
                netloc, snap1.get("status"), snap2.get("status")))
            return None

        sim1 = snap1.get("simhash") or ""
        sim2 = snap2.get("simhash") or ""
        if sim1 and sim2:
            if not self._simhash_within_distance(sim1, sim2):
                logger.info("catch_all baseline rejected for entry {}: SimHash distance exceeds threshold".format(netloc))
                return None
        else:
            if (snap1.get("title") or "") != (snap2.get("title") or ""):
                return None
            if abs(int(snap1.get("body_length") or 0) - int(snap2.get("body_length") or 0)) > 50:
                return None

        return snap1

    GENERIC_SERVERS = {
        "nginx", "apache", "iis", "tengine", "openresty", "lighttpd", "caddy",
        "microsoft-iis", "apache-http-server", "apache-httpd", "byte-nginx",
        "apache2 debian 默认页", "apache2 ubuntu 默认页", "iis 默认页"
    }

    INFRA_TOKENS = {
        "cdn", "waf", "proxy", "gateway", "alb", "slb", "elb", "tlb", "clb", "nlb",
        "volcalb", "loadbalancer", "cloudflare", "akamai", "fastly", "imperva",
        "incapsula", "envoy", "traefik", "haproxy", "squid", "varnish", "kong"
    }

    VENDOR_TOKENS = {
        "bytedance", "aliyun", "tencent", "baidu", "huawei", "cloud", "aws",
        "azure", "google", "microsoft", "volcengine", "volc"
    }

    NOISE_TOKENS = {"server", "service", "vhost", "default", "edge"}

    @classmethod
    def _is_infra_fingerprint(cls, name):
        """判定指纹是否属于基础设施（CDN/WAF/网关/负载均衡/通用Web服务器），此类指纹不能作为业务特赦凭据"""
        if not name or not isinstance(name, str):
            return False
        lower = name.lower().strip()
        if lower in cls.GENERIC_SERVERS:
            return True
        tokens = set(re.split(r"[\s\-_/]+", lower))
        if tokens.intersection(cls.INFRA_TOKENS):
            non_infra = tokens - cls.INFRA_TOKENS - cls.VENDOR_TOKENS - cls.NOISE_TOKENS
            if not non_infra:
                return True
        return False

    @classmethod
    def _has_business_amnesty(cls, item):
        """
        多维业务特征特赦 (Amnesty) - 内置记忆化缓存 (O(1) 防跨层重复计算):
        即使站点与默认后端基准相似，若具备强业务特征，予以特赦放行。
        """
        if "has_business_amnesty" in item:
            return item["has_business_amnesty"]

        res = cls._compute_business_amnesty(item)
        item["has_business_amnesty"] = res
        return res

    @classmethod
    def _compute_business_amnesty(cls, item):
        title = (item.get("title") or "").strip().lower()
        if title:
            business_keywords = [
                "登录", "登陆", "后台", "管理", "系统", "平台", "用户中心",
                "login", "admin", "portal", "dashboard", "console", "manager", "sso"
            ]
            if any(k in title for k in business_keywords):
                return True

        # 独立框架 / CMS 指纹（排除通用 Web 服务器与 CDN/WAF/负载均衡等基础设施指纹）
        finger_list = item.get("finger") or item.get("finger_name") or []
        if isinstance(finger_list, list) and finger_list:
            for fg in finger_list:
                fg_name = (fg if isinstance(fg, str) else fg.get("name", "")).strip()
                if fg_name and not cls._is_infra_fingerprint(fg_name):
                    return True

        # SSL 证书非泛解析精确匹配
        cert_info = item.get("cert") or item.get("ssl_cert") or {}
        if isinstance(cert_info, dict):
            subject_cn = (cert_info.get("subject_cn") or cert_info.get("common_name") or "").lower().strip()
            hostname = (item.get("hostname") or "").lower().strip()
            if subject_cn and hostname and subject_cn == hostname and not subject_cn.startswith("*"):
                return True

        return False

    def _is_catch_all_by_control(self, item, reference):
        """站点响应与随机标签的参照响应一致 => 命中的是默认后端"""
        # 特赦机制优先：若具有明确业务特征，豁免打标与阻断
        if self._has_business_amnesty(item):
            return False

        if item.get("status") != reference.get("status"):
            return False

        item_simhash = item.get("simhash") or ""
        ref_simhash = reference.get("simhash") or ""
        if item_simhash and ref_simhash:
            return self._simhash_within_distance(item_simhash, ref_simhash)

        if (item.get("title") or "") != (reference.get("title") or ""):
            return False
        return int(item.get("body_length") or 0) == int(reference.get("body_length") or 0)

    @staticmethod
    def _mark_catch_all_by_control(item, reference):
        if not isinstance(item.get("tag"), list):
            item["tag"] = []
        if "catch_all_vhost" not in item["tag"]:
            item["tag"].append("catch_all_vhost")

        item["is_catch_all"] = True
        item["catch_all_evidence"] = {
            "mode": "dual_probe_random_host_control",
            "ref_status": reference.get("status"),
            "ref_title": reference.get("title"),
            "simhash_matched": bool(item.get("simhash")) and item.get("simhash") == reference.get("simhash"),
        }

    def filter_catch_all_by_control_probe(self):
        """
        首道防线：逐入口双探针随机 Host 对照。
        1. 命中默认后端的站点打标 catch_all_vhost；
        2. 保留第 1 个作为代表站点入库，其余冗余站点从 site_info_list 剔除；
        3. 将全部命中站点写入 catch_all_sites 阻断集合（阻断下游 PoC/file_leak/爬虫/截图）；
        4. 支持任务选项 block_catch_all: False 回退为仅标注模式。
        """
        if not self.site_info_list:
            return

        should_block = True
        if hasattr(self, 'options') and isinstance(self.options, dict):
            should_block = self.options.get("block_catch_all", True)

        entry_map = {}
        for item in self.site_info_list:
            site = item.get("site")
            ip = item.get("ip")
            if not site or not ip:
                continue

            try:
                parsed = urlparse(site)
            except Exception:
                continue

            scheme = parsed.scheme or "http"
            port = parsed.port or (443 if scheme == "https" else 80)
            hostname = item.get("hostname") or parsed.hostname or ""
            entry = entry_map.setdefault((ip, scheme, port), {"hostname": hostname, "items": []})
            entry["items"].append(item)

        if not entry_map:
            return

        entries = list(entry_map.items())[:self.CATCH_ALL_CONTROL_MAX_ENTRY]

        def _probe(idx):
            (ip, scheme, port), entry = entries[idx]
            return self._fetch_catch_all_reference(ip=ip, scheme=scheme,
                                                   port=port, hostname=entry["hostname"])

        reference_map = {}
        try:
            from concurrent.futures import as_completed
            with utils.ContextAwareThreadPoolExecutor(max_workers=self.CATCH_ALL_CONTROL_CONCURRENCY) as executor:
                future_map = {executor.submit(_probe, idx): idx for idx in range(len(entries))}
                for future in as_completed(future_map):
                    idx = future_map[future]
                    try:
                        snapshot = future.result()
                    except Exception:
                        continue
                    if snapshot:
                        reference_map[idx] = snapshot
        except Exception as e:
            logger.warning("catch_all control probe error: {}".format(e))
            return

        marked_cnt = 0
        discarded_sites_set = set()

        for idx, ((ip, scheme, port), entry) in enumerate(entries):
            reference = reference_map.get(idx)
            if not reference:
                continue

            matched_items = []
            for item in entry["items"]:
                if self._is_catch_all_by_control(item, reference):
                    self._mark_catch_all_by_control(item, reference)
                    matched_items.append(item)
                    marked_cnt += 1

            if matched_items:
                # 处置动作：将命中站点全部加入阻断集合
                for m_item in matched_items:
                    m_site = m_item.get("site")
                    if m_site:
                        self.catch_all_sites.add(m_site)
                        cut_m = utils.url.cut_filename(m_site)
                        if cut_m:
                            self.catch_all_sites.add(cut_m)

                # 若启用阻断（默认）：保留首个代表站点，剔除其余冗余站点
                if should_block and len(matched_items) > 1:
                    for d_item in matched_items[1:]:
                        d_site = d_item.get("site")
                        if d_site:
                            discarded_sites_set.add(d_site)

        if discarded_sites_set:
            self.site_info_list = [s for s in self.site_info_list if s.get("site") not in discarded_sites_set]
            if self.available_sites:
                self.available_sites = [s for s in self.available_sites if s not in discarded_sites_set]
            logger.info("filter_catch_all_by_control_probe: marked {} default-backend sites, discarded {} redundant sites, retained representative sites".format(
                marked_cnt, len(discarded_sites_set)))
        else:
            logger.info("filter_catch_all_by_control_probe: probed {} entries, marked {} default-backend sites".format(
                len(entries), marked_cnt))

    def filter_catch_all_vhost(self):
        """
        第二道防线：对抓取到的站点结果进行默认后端/泛解析反代去噪与聚类兜底。
        针对状态码 {400, 403, 404, 500, 502, 503, 504}，按 (ip, status, length_bin, title) 聚类。
        当聚类数量 >= 10 时，保留第 1 个作为代表站点打标，其余剔除，并在下游扫描中全面阻断。
        """
        if not self.site_info_list:
            return

        target_status_codes = {400, 403, 404, 500, 502, 503, 504}
        clusters = defaultdict(list)

        for item in self.site_info_list:
            # 已经由首道防线（对照探针）处理过的默认后端跳过，避免重复聚类；
            # 具备业务特赦的站点享有绝对豁免权，严禁被第二层粗粒度聚类误杀 (Fix Issue #49)
            # (同时覆盖 MAX_ENTRY 截断未入探针、网络超时未建基准的极端边界场景)
            if item.get("is_catch_all") or self._has_business_amnesty(item):
                continue

            status = item.get("status")
            if status not in target_status_codes:
                continue

            ip = item.get("ip")
            if not ip:
                hostname = item.get("hostname")
                if not hostname and item.get("site"):
                    try:
                        hostname = urlparse(item["site"]).hostname
                    except Exception:
                        hostname = None
                if hostname:
                    try:
                        ip = socket.gethostbyname(hostname)
                        item["ip"] = ip
                    except Exception:
                        ip = None

            if not ip:
                continue

            body_len = item.get("body_length")
            if body_len is None:
                body_len = len(item.get("content", b"")) if "content" in item else 0

            length_bin = int(body_len / 100) * 100
            title = item.get("title") or ""
            cluster_key = (ip, status, length_bin, title)
            clusters[cluster_key].append(item)

        discarded_sites_set = set()
        for cluster_key, site_items in clusters.items():
            if len(site_items) >= 10:
                rep = site_items[0]
                if "tag" not in rep or not isinstance(rep.get("tag"), list):
                    rep["tag"] = []
                if "catch_all_vhost" not in rep["tag"]:
                    rep["tag"].append("catch_all_vhost")
                rep["is_catch_all"] = True

                rep_site = rep.get("site")
                if rep_site:
                    self.catch_all_sites.add(rep_site)
                    cut_rep = utils.url.cut_filename(rep_site)
                    if cut_rep:
                        self.catch_all_sites.add(cut_rep)

                for d_item in site_items[1:]:
                    d_site = d_item.get("site")
                    if d_site:
                        discarded_sites_set.add(d_site)
                        self.catch_all_sites.add(d_site)
                        cut_d = utils.url.cut_filename(d_site)
                        if cut_d:
                            self.catch_all_sites.add(cut_d)

        if discarded_sites_set:
            self.site_info_list = [s for s in self.site_info_list if s.get("site") not in discarded_sites_set]
            if self.available_sites:
                self.available_sites = [s for s in self.available_sites if s not in discarded_sites_set]
            logger.info("filter_catch_all_vhost: filtered {} redundant default vhost sites, retained representative sites".format(len(discarded_sites_set)))

    def fetch_site(self):
        # ***站点信息获取***
        self.site_info_list = services.fetch_site(self.sites)
        # 首道防线：基于双探针的高精度随机 Host 对照（阻断冗余并防 WAF 污染）
        self.filter_catch_all_by_control_probe()
        # 第二道防线：传统聚类兜底（针对网络超时未能确立基准的边缘站点）
        self.filter_catch_all_vhost()
        for site_info in self.site_info_list:
            curr_site = site_info["site"]
            self.available_sites.append(curr_site)

    def file_leak(self):
        file_leak_dicts_path = Config.FILE_LEAK_TOP_2k
        if hasattr(self, 'options') and self.options.get("file_leak_dict"):
            from app.utils import get_safe_dict_path
            try:
                file_leak_dicts_path = get_safe_dict_path(self.options.get("file_leak_dict"))
            except Exception as e:
                logger.error(f"加载文件泄露字典失败: {e}")
                pass
        
        all_items = []
        for site in self.poc_sites:
            # Recreate generator for each site since generators are exhausted after one iteration
            file_leak_dicts = utils.load_file_generator(file_leak_dicts_path)
            pages = services.file_leak([site], file_leak_dicts)
            for page in pages:
                item = page.dump_json()
                item["task_id"] = self.task_id
                item["site"] = site
                all_items.append(item)
        if all_items:
            utils.safe_insert_asset_many('fileleak', ['task_id', 'site', 'url'], all_items)

    @property
    def poc_sites(self):
        if self._poc_sites is None:
            self._poc_sites = set()
            for x in self.available_sites:
                cut_target = utils.url.cut_filename(x)
                if cut_target in self.catch_all_sites or x in self.catch_all_sites:
                    continue
                if cut_target:
                    self._poc_sites.add(cut_target)

        return self._poc_sites

    def risk_cruising(self, npoc_service_target_set: set):
        # *** 运行PoC任务, 需要自己在外层手动调用
        poc_config = self.options.get("poc_config", [])
        plugins = []
        for info in poc_config:
            if not info.get("enable"):
                continue
            plugins.append(info["plugin_name"])

        poc_targets = self.poc_sites

        if npoc_service_target_set is not None:
            poc_targets = self.poc_sites | npoc_service_target_set

        result = run_risk_cruising(plugins=plugins, targets=poc_targets)
        if result:
            for item in result:
                item["task_id"] = self.task_id
                item["save_date"] = utils.curr_date()
                if "plg_name" in item:
                    item["plugin_name"] = item.get("plg_name")
                if "target" in item:
                    item["vuln_url"] = item.get("target")
            utils.safe_insert_asset_many('vuln', ['task_id', 'vuln_url', 'plugin_name'], result)

    def nuclei_scan(self):
        logger.info("start nuclei_scan， poc_sites:{}".format(len(self.poc_sites)))
        scan_results = nuclei_scan(list(self.poc_sites))
        if scan_results:
            for item in scan_results:
                item["task_id"] = self.task_id
                item["save_date"] = utils.curr_date()
            utils.safe_insert_asset_many('nuclei_result', ['task_id', 'template_id', 'host'], scan_results)

        logger.info("end nuclei_scan， result:{}".format(len(scan_results)))

    def run_func(self, name: str, func: callable):
        logger.info("start run {}, {}".format(name, self.__str__()))
        self.base_update_task.update_task_field("status", name)
        t1 = time.time()
        with TaskHeartbeat(self.task_id, interval=60):
            func()
        elapse = time.time() - t1

        # 新增：恢复细颗粒度记录
        if hasattr(self, 'base_update_task') and self.base_update_task:
            self.base_update_task.update_services(name, round(elapse, 2))

        logger.info("end run {} ({:.2f}s), {}".format(name, elapse, self.__str__()))

    def update_page_url_set(self):
        from app.helpers import get_url_by_task_id
        # page_url_set 从数据库读取搜索引擎爬取到的URL
        urls = get_url_by_task_id(self.task_id)
        self.page_url_set |= set(urls)

        for u in self.page_url_set:
            o = urlparse(u)
            ret_url = "{}://{}".format(o.scheme, o.netloc)
            entry_urls = self.search_engines_result.get(ret_url, [])
            entry_urls.append(u)
            self.search_engines_result[ret_url] = entry_urls

    def add_wih_domain_set(self, record):
        if self.domain_black_list:
            if domain_in_scope_domain(record.content, self.domain_black_list):
                return

        if record.recordType == "domain":
            if self.scope_domain:
                if not domain_in_scope_domain(record.content, self.scope_domain):
                    return
            
            if utils.check_domain_black(record.content) or utils.is_forbidden_domain(record.content):
                return

            if record.content in self.wih_domain_set:
                return

            self.wih_domain_set.add(record.content)

    def run_web_info_hunter(self):
        records = set(services.run_wih(self.sites))
        all_items = []
        for record in records:
            # 先判断记录是否已经存在
            if record.fnv_hash in self.wih_record_set:
                continue

            self.add_wih_domain_set(record)

            item = record.dump_json()
            item["task_id"] = self.task_id
            all_items.append(item)
            self.wih_record_set.add(record.fnv_hash)
            
        if all_items:
            utils.safe_insert_asset_many('wih', ['task_id', 'site', 'fnv_hash'], all_items)

    def run(self):
        # *** 对站点进行基本信息的获取
        self.run_func(WebSiteFetchStatus.FETCH_SITE, self.fetch_site)

        """ *** 执行站点识别 """
        if self.options.get(WebSiteFetchOption.SITE_IDENTIFY):
            self.run_func(WebSiteFetchStatus.SITE_IDENTIFY, self.site_identify)

        """ *** 保存站点信息到数据库 """
        self.save_site_info()

        # 清空，节省内存
        self.site_info_list = []

        """ *** 站点截图（强制执行） *** """
        self.run_func(WebSiteFetchStatus.SITE_CAPTURE, self.site_screenshot)

        """ ***调用站点爬虫发现URL """
        if self.options.get(WebSiteFetchOption.SITE_SPIDER):
            self.update_page_url_set()
            self.run_func(WebSiteFetchStatus.SITE_SPIDER, self.site_spider)



        """ *** 对站点调用 WebInfoHunter """
        if self.options.get(WebSiteFetchOption.Info_Hunter):
            self.run_func(WebSiteFetchStatus.Info_Hunter, self.run_web_info_hunter)


def domain_in_scope_domain(domain: str, scope_domain: list):
    for scope in scope_domain:
        if domain == scope or domain.endswith("." + scope):
            return True
    return False


def build_url_item(site, task_id, source):
    item = {
        "site": site,
        "task_id": task_id,
        "source": source
    }
    domain_parsed = utils.domain_parsed(site)
    if domain_parsed:
        item["fld"] = domain_parsed["fld"]

    return item
