import time
import socket
from collections import defaultdict
from urllib.parse import urlparse
from bson import ObjectId
from app import utils
from app import services
from app.config import Config
from contextlib import contextmanager
import traceback
from app.modules import CollectSource, WebSiteFetchStatus, WebSiteFetchOption
from app.services.nuclei_scan import nuclei_scan
from app.services import run_risk_cruising, BaseUpdateTask
logger = utils.get_logger()


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

    def filter_catch_all_vhost(self):
        """
        对抓取到的站点结果进行默认后端/泛解析反代去噪与聚类。
        针对状态码 {400, 403, 404, 500, 502, 503, 504}，按 (ip, status, length_bin, title) 聚类。
        当聚类数量 >= 10 时，保留第 1 个作为代表站点打标，其余剔除，并在下游扫描中全面阻断。
        """
        if not self.site_info_list:
            return

        target_status_codes = {400, 403, 404, 500, 502, 503, 504}
        clusters = defaultdict(list)

        for item in self.site_info_list:
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

    # ==================================================================
    # 泛解析 / 默认后端：随机标签对照判定（只标注，不剔除、不阻断下游扫描）
    # 场景多的时候，靠聚类 + 状态码白名单 + 长度分桶往往收不住。这里换一个
    # 不依赖场景枚举的判据：用随机标签的 Host 打到同一入口取一次参照响应，
    # 再与站点自身的响应比对 —— 一致即说明命中的是默认后端。
    # 静态/轮转、404/200、是否 CDN、多 A 记录，都用同一个判据覆盖。
    # ==================================================================
    CATCH_ALL_CONTROL_TIMEOUT = (3.1, 6.1)
    CATCH_ALL_CONTROL_MAX_ENTRY = 30
    CATCH_ALL_CONTROL_CONCURRENCY = 6
    # 与 asset_site_monitor.compare_simhash 保持一致：距离 <= 3 视为同一页面
    CATCH_ALL_CONTROL_SIMHASH_DISTANCE = 3

    @staticmethod
    def _wildcard_parent(hostname):
        """
        随机标签的挂载点

        - 纯 IP 访问直接跳过，避免拼出 wfxxxx.168.1.1 这种无效 Host
        - 优先用站点的直接父域；父域落在公共后缀里（如 co.uk / edu.cn）时回退到可注册主域
        """
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

    @staticmethod
    def _simhash_within_distance(simhash_a, simhash_b, max_distance=CATCH_ALL_CONTROL_SIMHASH_DISTANCE):
        """容忍默认后端页面里的时间戳 / 随机 token：按汉明距离判定，而不是字符串全等"""
        if simhash_a == simhash_b:
            return True

        try:
            import simhash
            distance = simhash.Simhash(int(simhash_a)).distance(simhash.Simhash(int(simhash_b)))
        except Exception:
            return False

        return distance <= max_distance

    def _probe_catch_all_reference(self, url, host_header):
        """请求一次，取回用于比对的响应快照；失败返回 None"""
        try:
            conn = utils.http_req(url, headers={"Host": host_header},
                                  timeout=self.CATCH_ALL_CONTROL_TIMEOUT,
                                  allow_redirects=True)
        except Exception:
            return None

        content = conn.content or b""
        try:
            import simhash
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
        用随机标签取该入口的参照响应，返回 dict 或 None

        1) 直连入口 IP + 随机标签 Host：不依赖 DNS 上是否真的存在泛解析
        2) 兜底再试随机域名直连，且仅在 DNS 上确认存在泛解析时才发起，
           避免没有泛解析时白等一次递归查询
        """
        parent = self._wildcard_parent(hostname)
        if not parent:
            return None

        random_host = "wf" + utils.random_choices(6) + "." + parent
        ip_netloc = "[{}]".format(ip) if ":" in ip else ip
        netloc = "{}:{}".format(ip_netloc, port)

        snapshot = self._probe_catch_all_reference("{}://{}/".format(scheme, netloc), random_host)
        if snapshot:
            return snapshot

        if utils.get_ip(random_host, log_flag=False):
            return self._probe_catch_all_reference("{}://{}/".format(scheme, random_host), random_host)

        return None

    def _is_catch_all_by_control(self, item, reference):
        """站点响应与随机标签的参照响应一致 => 命中的是默认后端"""
        if item.get("status") != reference.get("status"):
            return False

        item_simhash = item.get("simhash") or ""
        ref_simhash = reference.get("simhash") or ""
        if item_simhash and ref_simhash:
            # 用汉明距离容差，避免页面里的时间戳 / 随机 token 把同一个页面判成两个
            return self._simhash_within_distance(item_simhash, ref_simhash)

        # 正文指纹缺失时退回 title + 长度比对
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
            "mode": "random_host_control",
            "ref_status": reference.get("status"),
            "ref_title": reference.get("title"),
            "simhash_matched": bool(item.get("simhash")) and item.get("simhash") == reference.get("simhash"),
        }

    def mark_catch_all_by_control_probe(self):
        """
        逐入口做随机标签对照，给命中默认后端的站点打 catch_all_vhost 标记。

        注意：只标注 —— 不剔除站点，也不写入 self.catch_all_sites（即不阻断 PoC / fileleak），
        避免在验证充分之前改变现有扫描行为；是否让它参与过滤交给下游决定。
        """
        if not self.site_info_list:
            return

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

        # 注意：这里不能用 services.baseThread.thread_map —— 它的 _run 会把整数 0 当成空目标跳过
        # （baseThread.py 里的 `if not target: continue`），第 0 个入口永远拿不到参照响应。
        # utils.ContextAwareThreadPoolExecutor 是仓库自带的，同样会透传 arl_task_id 上下文。
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

        marked = 0
        for idx, ((ip, scheme, port), entry) in enumerate(entries):
            reference = reference_map.get(idx)
            if not reference:
                continue

            for item in entry["items"]:
                if self._is_catch_all_by_control(item, reference):
                    self._mark_catch_all_by_control(item, reference)
                    marked += 1

        logger.info("mark_catch_all_by_control_probe: probed {} entries, marked {} default-backend sites".format(
            len(entries), marked))

    def fetch_site(self):
        # ***站点信息获取***
        self.site_info_list = services.fetch_site(self.sites)
        self.filter_catch_all_vhost()
        # 随机标签对照：补一层不依赖聚类阈值的判定（只标注，不剔除）
        self.mark_catch_all_by_control_probe()
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
