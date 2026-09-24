from celery import current_task
from celery.exceptions import MaxRetriesExceededError, Retry
from bson import ObjectId
from bson.errors import InvalidId
from pymongo.errors import PyMongoError
from app.utils import conn_db as conn, arl_task_id_var
from .domain import DomainTask
from .ip import IPTask
from app import utils
from app.modules import TaskStatus, CollectSource, SchedulerStatus
from app.services import sync_asset, build_domain_info, sync_asset
import time
from app.scheduler import update_scheduler_run
from app.services import webhook
from app.services.commonTask import TaskHeartbeat

logger = utils.get_logger()

def domain_executors(base_domain=None, scheduler_id=None, scope_id=None, options=None, name=""):
    logger.info("start domain_executors {} {} {}".format(base_domain, scope_id, options))
    try:
        query = {"_id": ObjectId(scheduler_id)}
        item = utils.conn_db('scheduler').find_one(query)
        if not item:
            logger.info("stop  domain_executors {}  not found scheduler_id {}".format(base_domain, scheduler_id))
            return

        if item.get("status") == SchedulerStatus.STOP:
            logger.info("stop  domain_executors {}  scheduler_id {} is stop ".format(base_domain, scheduler_id))
            return

        # 关口 3：Worker 消费端前置校验（核验目标是否仍属于当前资产组 - Issue #48 Fail-Closed 加固）
        if scope_id:
            try:
                scope_obj = utils.conn_db('asset_scope').find_one({"_id": ObjectId(str(scope_id))})
                if not scope_obj or base_domain not in scope_obj.get("scope_array", []):
                    logger.warning("stop domain_executors: target {} is no longer in scope {}, dropping task.".format(base_domain, scope_id))
                    return
            except InvalidId as ex:
                logger.error(f"stop domain_executors: invalid scope_id '{scope_id}': {ex}. Dropping task.")
                return
            except PyMongoError as ex:
                logger.warning(f"retry domain_executors: MongoDB error checking scope {scope_id}: {ex}")
                task_obj = current_task._get_current_object() if current_task else None
                if task_obj:
                    try:
                        task_obj.retry(exc=ex, countdown=30, max_retries=3)
                    except MaxRetriesExceededError:
                        logger.error(f"stop domain_executors: max retries exceeded for scope {scope_id}. Dropping task (fail-closed).")
                        return
                return
            except Exception as ex:
                logger.error(f"stop domain_executors: unexpected error checking scope {scope_id}: {ex}. Dropping task (fail-closed).")
                return

        wrap_domain_executors(base_domain=base_domain, scheduler_id=scheduler_id, scope_id=scope_id, options=options, name=name)
    except Retry:
        raise
    except Exception as e:
        logger.exception(e)


def wrap_domain_executors(base_domain=None, scheduler_id=None, scope_id=None, options=None, name=""):
    import time
    import random
    
    # 随机休眠避免并发冲突
    time.sleep(random.uniform(0.1, 1.0))
    
    # 二次防重：防止多个 Celery Worker 同时消费到队列中积压的重复消息
    running_tasks = conn('task').count_documents({
        "options.scheduler_id": scheduler_id,
        "status": {"$nin": [TaskStatus.DONE, TaskStatus.ERROR, TaskStatus.STOP]}
    })
    
    if running_tasks > 0:
        logger.warning(f"Task overlap prevented in worker: scheduler {scheduler_id} is already running. Dropping duplicate message.")
        return

    celery_id = "celery_id_placeholder"

    if current_task._get_current_object():
        celery_id = current_task.request.id

    task_data = {
        'name': name,
        'target': base_domain,
        'start_time': '-',
        'status': 'waiting',
        'type': 'domain',
        'task_tag': 'monitor',  #标记为监控任务
        'end_time': '-',
        'service': [],
        'options': {
            'domain_brute': True,
            'domain_brute_type': 'test',
            'alt_dns': False,
            'arl_search': True,
            'port_scan_type': 'test',
            'port_scan': True,
            'service_detection': False,
            'service_brute': False,
            'os_detection': False,
            'site_identify': False,
            'site_capture': False,
            'file_leak': False,
            'site_spider': False,
            'search_engines': False,
            'ssl_cert': False,
            'fofa_search': False,
            'dns_query_plugin': False,
            'web_info_hunter': False,
            'scope_id': scope_id,
            'scheduler_id': scheduler_id
        },
        'celery_id': celery_id
    }
    if options is None:
        options = {}
    task_data["options"].update(options)

    conn('task').insert_one(task_data)
    task_id = str(task_data.pop("_id"))
    
    arl_task_id_var.set(task_id)
        
    domain_executor = DomainExecutor(base_domain, task_id, task_data["options"])
    try:
        update_scheduler_run(scheduler_id)
        new_domain = domain_executor.run()
        sync_asset(task_id, scope_id, update_flag=True, push_flag=True, task_name=name)
        if new_domain:
            webhook.domain_asset_web_hook(task_id=task_id, scope_id=scope_id)
        if scope_id and base_domain:
            from app.helpers.scope import update_scope_domain_status
            update_scope_domain_status(scope_id, base_domain, "probed", task_id)
    except Exception as e:
        logger.exception(e)
        domain_executor.update_task_field("status", TaskStatus.ERROR)
        domain_executor.update_task_field("end_time", utils.curr_date())
        if scope_id and base_domain:
            from app.helpers.scope import update_scope_domain_status
            update_scope_domain_status(scope_id, base_domain, "error", task_id)

    logger.info("end domain_executors {} {} {}".format(base_domain, scope_id, options))


def oneshot_domain_executors(base_domain=None, scope_id=None, options=None, name="", task_id=None):
    celery_id = "celery_id_placeholder"

    if current_task._get_current_object():
        celery_id = current_task.request.id

    task_data = {
        'name': name,
        'target': base_domain,
        'start_time': '-',
        'status': 'waiting',
        'type': 'domain',
        'task_tag': 'monitor',  # 标记为监控任务，以便正常走后期的联动逻辑
        'end_time': '-',
        'service': [],
        'options': {
            'domain_brute': True,
            'domain_brute_type': 'test',
            'alt_dns': False,
            'arl_search': True,
            'port_scan_type': 'test',
            'port_scan': True,
            'service_detection': False,
            'service_brute': False,
            'os_detection': False,
            'site_identify': False,
            'site_capture': False,
            'file_leak': False,
            'site_spider': False,
            'search_engines': False,
            'ssl_cert': False,
            'fofa_search': False,
            'dns_query_plugin': False,
            'web_info_hunter': False,
            'scope_id': scope_id
        },
        'celery_id': celery_id
    }
    if options is None:
        options = {}
    task_data["options"].update(options)

    if task_id:
        # 收养重启/预建的任务记录，避免重复落库，保证重启链路可追踪
        conn('task').update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {"celery_id": celery_id, "target": base_domain, "options": task_data["options"]}}
        )
    else:
        conn('task').insert_one(task_data)
        task_id = str(task_data.pop("_id"))

    arl_task_id_var.set(task_id)

    domain_executor = DomainExecutor(base_domain, task_id, task_data["options"])
    try:
        new_domain = domain_executor.run()
        sync_asset(task_id, scope_id, update_flag=True, push_flag=True, task_name=name)
        if new_domain:
            webhook.domain_asset_web_hook(task_id=task_id, scope_id=scope_id)
        if scope_id and base_domain:
            from app.helpers.scope import update_scope_domain_status
            update_scope_domain_status(scope_id, base_domain, "probed", task_id)
    except Exception as e:
        logger.exception(e)
        domain_executor.update_task_field("status", TaskStatus.ERROR)
        domain_executor.update_task_field("end_time", utils.curr_date())
        if scope_id and base_domain:
            from app.helpers.scope import update_scope_domain_status
            update_scope_domain_status(scope_id, base_domain, "error", task_id)

    logger.info("end oneshot_domain_executors {} {} {}".format(base_domain, scope_id, options))


# ***域名监控任务　＊＊＊
class DomainExecutor(DomainTask):
    def __init__(self, base_domain, task_id, options):
        super().__init__(base_domain, task_id, options)
        self.domain_set = set()
        self.scope_id = options["scope_id"]
        self.scope_domain_set = None
        self.new_domain_set = None
        self.task_tag = "monitor"
        self.wildcard_map = {}

    def run(self):
        with TaskHeartbeat(self.task_id, interval=60):
            return self._run_phases()

    def _run_phases(self):
        base_update = self.base_update_task
        self.update_task_field("start_time", utils.curr_date())

        
        self.domain_fetch()

        if self.options.get("search_engines"):
            with self.safe_phase("search_engines", base_update):
                self.search_engines()

        for domain_info in self.domain_info_list:
            self.domain_set.add(domain_info.domain)

        with self.safe_phase("domain_sync", base_update):
            self.set_scope_domain()
            target_scope_domains = {d for d in self.scope_domain_set if d == self.base_domain or d.endswith("." + self.base_domain)}
            new_domain_set = self.domain_set | target_scope_domains
            self.new_domain_set = new_domain_set
            self.set_wildcard_ip_set()
            self.set_domain_info_list()

        # 返回发现的新域名，在后续进行同步到资产组
        ret_new_domain_set = set()
        for domain_info in self.domain_info_list:
            ret_new_domain_set.add(domain_info.domain)

        # 仅仅对新增域名保留
        self.start_ip_fetch()
            
        self.start_site_fetch()

        with self.safe_phase("process_wih_domains", base_update):
            self.process_wih_domains()

        if self.options.get("findvhost"):
            with self.safe_phase("find_vhost", base_update):
                self.start_find_vhost()

        if self.options.get("npoc_service_detection") or self.options.get("poc_config") or self.options.get("brute_config"):
            with self.safe_phase("poc_run", base_update):
                self.start_poc_run()
            
        if self.options.get("file_leak"):
            if hasattr(self, 'web_site_fetch') and self.web_site_fetch:
                self.web_site_fetch.run_func("file_leak", self.web_site_fetch.file_leak)

        # nuclei_scan 放在最后执行，防止高并发扫描把目标打挂或者触发IP封禁
        if self.options.get("nuclei_scan"):
            if hasattr(self, 'web_site_fetch') and self.web_site_fetch:
                self.web_site_fetch.run_func("nuclei_scan", self.web_site_fetch.nuclei_scan)

        with self.safe_phase("task_stats", base_update):
            # cidr ip 结果统计，插入cip 集合中
            self.insert_cip_stat()

            # 任务指纹信息统计
            self.insert_finger_stat()
            # 任务结果统计
            self.insert_task_stat()

        self.update_task_field("status", TaskStatus.DONE)
        self.update_task_field("end_time", utils.curr_date())

        return ret_new_domain_set

    def set_scope_domain(self):
        """
        查询资产库中域名，并继承已有资产的原始 source 溯源信息
        """
        self.scope_domain_set = set()
        if not self.scope_id:
            return
        cursor = conn('asset_domain').find({"scope_id": str(self.scope_id)}, {"domain": 1, "source": 1})
        for item in cursor:
            d = item.get("domain")
            if d:
                d_lower = d.lower().strip()
                self.scope_domain_set.add(d_lower)
                # 存量资产如果之前已有真实来源，记录在 domain_source_map 中，避免被覆盖
                if d_lower not in self.domain_source_map and item.get("source"):
                    self.domain_source_map[d_lower] = item.get("source")

    def set_domain_info_list(self):
        """
        将domain_info_list替换为仅仅包括新增域名
        """
        self.domain_info_list = []
        self.record_map = {}
        logger.info("start build domain monitor task, new domain {}".format(len(self.new_domain_set)))
        t1 = time.time()

        self.task_tag = "task" #标记为正常任务，让build_domain_info 工作
        new = self.build_domain_info(self.new_domain_set)
        new = self.clear_domain_info_by_record(new)
        self.task_tag = "monitor"

        if getattr(self, 'wildcard_map', None):
            new = self.clear_wildcard_domain_info(new)

        elapse = time.time() - t1
        logger.info("end build domain monitor task  {}, elapse {}".format(
            len(new), elapse))

        #删除前面步骤插入的域名
        conn('domain').delete_many({"task_id": self.task_id})

        #重新保存新发现的域名
        self.save_domain_info_list(new, CollectSource.MONITOR)
        self.domain_info_list = new

    def set_wildcard_ip_set(self):
        """
        针对每个可能存在泛解析的父级域名进行独立探测，建立 (parent_domain -> wildcard_metadata) 映射
        采用 3 次探活交叉验证与公共 CDN 排除，避免 Anycast/轮询 IP 污染与误杀合法业务
        """
        self.wildcard_map = {}
        parent_domains = set()
        base = (getattr(self, "base_domain", None) or "").lower().strip()
        for domain in self.new_domain_set:
            if not domain:
                continue
            curr = domain.lower().strip()
            if base:
                while curr.endswith("." + base):
                    curr = curr.split(".", 1)[1]
                    parent_domains.add(curr)
                parent_domains.add(base)

        public_cdn_roots = {
            "kunlunsl.com", "alicdn.com", "cloudflare.net",
            "akamaiedge.net", "azureedge.net", "w.kunlungr.com",
            "cloudflaressl.com"
        }

        for parent in parent_domains:
            samples_ip = []
            samples_cname = []
            for _ in range(3):
                rand = "wf" + utils.random_choices(6) + "." + parent
                ips = set(utils.get_ip(rand, log_flag=False) or [])
                cnames = {c.lower().strip().rstrip(".") for c in (utils.get_cname(rand, log_flag=False) or []) if c}
                if ips:
                    samples_ip.append(ips)
                if cnames:
                    samples_cname.append(cnames)

            if len(samples_ip) >= 2:
                all_ips = set.union(*samples_ip)
                is_rotating = not (len(samples_ip) == 3 and samples_ip[0] == samples_ip[1] == samples_ip[2])
                static_cnames = set()
                if len(samples_cname) >= 2:
                    common_cnames = set.intersection(*samples_cname)
                    for cname in common_cnames:
                        cname_norm = cname.lower().strip().rstrip(".")
                        if not any(cname_norm == cdn or cname_norm.endswith("." + cdn) for cdn in public_cdn_roots):
                            static_cnames.add(cname_norm)

                self.wildcard_map[parent] = {
                    "ips": all_ips,
                    "is_rotating": is_rotating,
                    "static_cnames": static_cnames
                }
                logger.info(f"detected wildcard zone: *.{parent} -> ips:{len(all_ips)}, rotating:{is_rotating}, static_cnames:{static_cnames}")

        logger.info("start get wildcard_map with {} wildcard zones".format(len(self.wildcard_map)))

    def clear_wildcard_domain_info(self, info_list):
        if not getattr(self, 'wildcard_map', None):
            return info_list
        cnt = 0
        new = []
        scope_domains = set()
        if getattr(self, 'scope_domain_set', None):
            scope_domains.update(d.lower().strip() for d in self.scope_domain_set if d)
        if getattr(self, 'scope_domains', None):
            scope_domains.update(d.lower().strip() for d in self.scope_domains if d)

        for info in info_list:
            if isinstance(info, dict):
                domain = (info.get("domain") or "").lower().strip()
                record_list = info.get("record") or info.get("record_list") or []
                rec_type = info.get("type") or ""
                ip_list = info.get("ips") or info.get("ip_list") or []
                cname_val = info.get("cname")
            else:
                domain = (getattr(info, "domain", "") or "").lower().strip()
                record_list = getattr(info, "record_list", []) or []
                rec_type = getattr(info, "type", "") or ""
                ip_list = getattr(info, "ip_list", []) or []
                cname_val = getattr(info, "cname", None)

            if not domain:
                new.append(info)
                continue

            # 存量白名单豁免
            if domain in scope_domains:
                new.append(info)
                continue

            info_ips = set(ip_list)
            info_cnames = set()
            if rec_type == "CNAME" and record_list:
                info_cnames.update(c.lower().strip().rstrip(".") for c in record_list if isinstance(c, str))
            if cname_val:
                if isinstance(cname_val, (list, set)):
                    info_cnames.update(c.lower().strip().rstrip(".") for c in cname_val if isinstance(c, str))
                elif isinstance(cname_val, str):
                    info_cnames.add(cname_val.lower().strip().rstrip("."))

            is_wildcard = False
            # 仅对其直接父级或上层域名的泛解析规则进行校验
            for parent, wc_info in self.wildcard_map.items():
                if domain.endswith("." + parent) and domain != parent:
                    if isinstance(wc_info, dict):
                        wc_ips = wc_info.get("ips", set())
                        is_rotating = wc_info.get("is_rotating", False)
                        static_cnames = wc_info.get("static_cnames", set())
                    else:
                        wc_ips = set(wc_info)
                        is_rotating = False
                        static_cnames = set()

                    # CNAME 规则优先：若子域 CNAME 命中 wc_info["static_cnames"]，判定为泛解析拦截
                    if info_cnames and static_cnames and (info_cnames & static_cnames):
                        is_wildcard = True
                        break

                    # IP 规则判定（静态与轮转统一引入交集比例阈值，规避多 A 记录绕过）
                    if info_ips and wc_ips:
                        common = info_ips & wc_ips
                        threshold = 0.5
                        if is_rotating:
                            if len(common) / len(info_ips) >= threshold:
                                is_wildcard = True
                                break
                        else:
                            # 静态泛解析：若子域全部 IP 均为泛解析 IP（子集），或子域多 A 记录中泛解析 IP 占比达到阈值
                            if info_ips.issubset(wc_ips) or (len(common) / len(info_ips) >= threshold):
                                is_wildcard = True
                                break

            if is_wildcard:
                cnt += 1
                continue
            new.append(info)

        logger.info("clear_wildcard_domain_info filtered: {}".format(cnt))
        return new


# ***IP监控任务　＊＊＊
class IPExecutor(IPTask):
    def __init__(self, target, scope_id, task_name, scheduler_id, options):
        super().__init__(ip_target=target, task_id=None, options=options)
        self.scope_id = scope_id
        self.task_name = task_name
        self.scheduler_id = scheduler_id
        self.task_tag = "monitor"  # 标记为监控任务

    def port_scan(self):
        # 提取历史资产，确保资产组里的旧 IP 也能被重扫
        self.set_asset_ip()
        
        target_set = set(self.ip_target.split())
        
        # 解析当前的输入目标范围
        import ipaddress
        target_networks = []
        for t in target_set:
            try:
                target_networks.append(ipaddress.ip_network(t, strict=False))
            except Exception:
                pass
                
        # 仅合并属于当前目标网段的历史 IP
        for ip in self.asset_ip_info_map.keys():
            try:
                ip_obj = ipaddress.ip_address(ip)
                if any(ip_obj in net for net in target_networks):
                    target_set.add(ip)
            except Exception:
                pass
            
        self.ip_target = " ".join(target_set)
        
        # 交给底层的端口扫描引擎执行
        super().port_scan()

    def insert_task_data(self, task_id=None):
        celery_id = ""
        if current_task._get_current_object():
            celery_id = current_task.request.id

        task_data = {
            'name': self.task_name,
            'target': self.ip_target,
            'start_time': '-',
            'end_time': '-',
            'status': TaskStatus.WAITING,
            'type': 'ip',
            'task_tag': 'monitor',  # 标记为监控任务
            'service': [],
            'options': {
                "port_scan_type": "test",
                "port_scan": True,
                "service_detection": False,
                "os_detection": False,
                "site_identify": False,
                "site_capture": False,
                "file_leak": False,
                "site_spider": False,
                "ssl_cert": False,
                'web_info_hunter': False,
                'scope_id': self.scope_id,
                'scheduler_id': self.scheduler_id
            },
            'celery_id': celery_id
        }

        if self.options is None:
            self.options = {}

        task_data["options"].update(self.options)

        if task_id:
            # 收养重启/预建的任务记录，避免重复落库，保证重启链路可追踪
            conn('task').update_one(
                {"_id": ObjectId(task_id)},
                {"$set": {"celery_id": celery_id, "target": self.ip_target, "options": task_data["options"]}}
            )
            self.task_id = task_id
        else:
            conn('task').insert_one(task_data)
            self.task_id = str(task_data.pop("_id"))

        arl_task_id_var.set(self.task_id)

        # base_update_task 初始化在前，再设置回task_id
        self.base_update_task.task_id = self.task_id

    def set_asset_ip(self):
        if self.task_tag != 'monitor':
            return

        query = {"scope_id": self.scope_id}
        items = list(utils.conn_db('asset_ip').find(query, {"ip": 1, "port_info": 1}))
        for item in items:
            self.asset_ip_info_map[item["ip"]] = item
            for port_info in item["port_info"]:
                ip_port = "{}:{}".format(item["ip"], port_info["port_id"])
                self.asset_ip_port_set.add(ip_port)

    def async_ip_info(self):
        new_ip_info_list = []
        for ip_info in self.ip_info_list:
            curr_ip = ip_info["ip"]
            curr_date_obj = utils.curr_date_obj()

            # 新发现的IP ，直接入资产集合
            if curr_ip not in self.asset_ip_info_map:
                asset_ip_info = ip_info.copy()
                asset_ip_info["scope_id"] = self.scope_id
                asset_ip_info["domain"] = []
                asset_ip_info["save_date"] = curr_date_obj
                asset_ip_info["update_date"] = curr_date_obj
                utils.conn_db('asset_ip').insert_one(asset_ip_info)
                utils.conn_db('ip').insert_one(ip_info)
                new_ip_info_list.append(ip_info)
                continue

            # 保存新发现的端口
            new_port_info_list = []
            for port_info in ip_info["port_info"]:
                ip_port = "{}:{}".format(curr_ip, port_info["port_id"])
                if ip_port not in self.asset_ip_port_set:
                    new_port_info_list.append(port_info)

            if new_port_info_list:
                asset_ip_info = self.asset_ip_info_map[curr_ip]
                asset_ip_info["port_info"].extend(new_port_info_list)

                update_info = dict()
                update_info["update_date"] = utils.curr_date_obj()
                update_info["port_info"] = asset_ip_info["port_info"]
                query = {"_id": asset_ip_info["_id"]}
                utils.conn_db('asset_ip').update_one(query, {"$set": update_info})

                # 存入数据库记录，只记录新发现的端口
                ip_info_copy = ip_info.copy()
                ip_info_copy["port_info"] = new_port_info_list
                utils.conn_db('ip').insert_one(ip_info_copy)

            # 无论是否发现新端口，无论是一次性扫描还是周期任务，
            # 都不再丢弃已有端口，让该IP全量进入后续流程，实现 100% 重扫。
            new_ip_info_list.append(ip_info)

        self.ip_info_list = new_ip_info_list
        logger.info("found new ip_info {}".format(len(self.ip_info_list)))

    # 同步全部资产信息（包含站点、wih、风险等）
    def sync_asset_site_wih(self):
        sync_asset(self.task_id, self.scope_id, update_flag=False,
                   push_flag=True, task_name=self.task_name)


def ip_executor(target, scope_id, task_name, scheduler_id, options):
    import time
    import random
    
    # 随机休眠避免并发冲突
    time.sleep(random.uniform(0.1, 1.0))
    
    # 二次防重：防止队列积压导致的重复消费
    running_tasks = conn('task').count_documents({
        "options.scheduler_id": scheduler_id,
        "status": {"$nin": [TaskStatus.DONE, TaskStatus.ERROR, TaskStatus.STOP]}
    })
    
    if running_tasks > 0:
        logger.warning(f"Task overlap prevented in worker: IP scheduler {scheduler_id} is already running. Dropping duplicate message.")
        return

    try:
        query = {"_id": ObjectId(scheduler_id)}
        item = utils.conn_db('scheduler').find_one(query)
        if not item:
            logger.info("stop  ip_executors {}  not found scheduler_id {}".format(target, scheduler_id))
            return

        if item.get("status") == SchedulerStatus.STOP:
            logger.info("stop  ip_executors {}  scheduler_id {} is stop ".format(target, scheduler_id))
            return

        # 关口 3：Worker 消费端前置校验（核验 IP 目标是否仍属于当前资产组 - Issue #48 Fail-Closed 加固）
        if scope_id:
            try:
                scope_obj = utils.conn_db('asset_scope').find_one({"_id": ObjectId(str(scope_id))})
                if not scope_obj:
                    logger.warning(f"stop ip_executors: scope {scope_id} not found, dropping task.")
                    return
                valid_scopes = set(scope_obj.get("scope_array", []))
                valid_targets = [t for t in target.split() if t in valid_scopes]
                if not valid_targets:
                    logger.warning(f"stop ip_executors: target(s) '{target}' no longer in scope {scope_id}, dropping task.")
                    return
                target = " ".join(valid_targets)
            except InvalidId as ex:
                logger.error(f"stop ip_executors: invalid scope_id '{scope_id}': {ex}. Dropping task.")
                return
            except PyMongoError as ex:
                logger.warning(f"retry ip_executors: MongoDB error checking scope {scope_id}: {ex}")
                task_obj = current_task._get_current_object() if current_task else None
                if task_obj:
                    try:
                        task_obj.retry(exc=ex, countdown=30, max_retries=3)
                    except MaxRetriesExceededError:
                        logger.error(f"stop ip_executors: max retries exceeded for scope {scope_id}. Dropping task (fail-closed).")
                        return
                return
            except Exception as ex:
                logger.error(f"stop ip_executors: unexpected error checking scope {scope_id}: {ex}. Dropping task (fail-closed).")
                return

        update_scheduler_run(scheduler_id)
    except Retry:
        raise
    except Exception as e:
        logger.exception(e)
        return

    executor = IPExecutor(target, scope_id, task_name, scheduler_id, options)
    try:
        executor.insert_task_data()
        executor.run()
        executor.sync_asset_site_wih()

        from app.helpers.scope import update_scope_domain_status
        for ip in target.split():
            update_scope_domain_status(scope_id, ip, "probed", executor.task_id)

    except Exception as e:
        logger.warning("error on ip_executor {}".format(executor.ip_target))
        logger.exception(e)
        executor.base_update_task.update_task_field("status", TaskStatus.ERROR)
        from app.helpers.scope import update_scope_domain_status
        for ip in target.split():
            update_scope_domain_status(scope_id, ip, "error", getattr(executor, 'task_id', None))

def oneshot_ip_executors(target, scope_id, task_name, options, task_id=None):
    # This is a one-time execution, no scheduler_id
    executor = IPExecutor(target, scope_id, task_name, "oneshot", options)
    try:
        executor.insert_task_data(task_id=task_id)
        executor.run()
        executor.sync_asset_site_wih()

        from app.helpers.scope import update_scope_domain_status
        for ip in target.split():
            update_scope_domain_status(scope_id, ip, "probed", executor.task_id)
    except Exception as e:
        logger.warning("error on oneshot_ip_executors {}".format(executor.ip_target))
        logger.exception(e)
        executor.base_update_task.update_task_field("status", TaskStatus.ERROR)
        executor.base_update_task.update_task_field("end_time", utils.curr_date())
        from app.helpers.scope import update_scope_domain_status
        for ip in target.split():
            update_scope_domain_status(scope_id, ip, "error", getattr(executor, 'task_id', None))