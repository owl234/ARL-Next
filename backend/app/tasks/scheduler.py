from celery import current_task
from bson import ObjectId
from app.utils import conn_db as conn, arl_task_id_var
from .domain import DomainTask
from .ip import IPTask
from app import utils
from app.modules import TaskStatus, CollectSource, SchedulerStatus
from app.services import sync_asset, build_domain_info, sync_asset
import time
from app.scheduler import update_scheduler_run
from app.services import webhook

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
            logger.info("stop  ip_executors {}  scheduler_id {} is stop ".format(base_domain, scheduler_id))
            return

        wrap_domain_executors(base_domain=base_domain, scheduler_id=scheduler_id, scope_id=scope_id, options=options, name=name)
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


def oneshot_domain_executors(base_domain=None, scope_id=None, options=None, name=""):
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
        base_update = self.base_update_task
        self.update_task_field("start_time", utils.curr_date())
        
        self.domain_fetch()
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
        查询资产库中域名
        """
        self.scope_domain_set = set(utils.get_asset_domain_by_id(self.scope_id))

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
        针对每个可能存在泛解析的父级域名进行独立探测，建立 (parent_domain -> wildcard_ips) 映射
        采用双随机探测交叉验证，避免 CDN Anycast 节点 IP 污染全局并误杀合法业务
        """
        self.wildcard_map = {}
        parent_domains = set()
        for domain in self.new_domain_set:
            cut_name = utils.domain.cut_first_name(domain)
            if cut_name:
                parent_domains.add(cut_name)

        for parent in parent_domains:
            rand1 = "wf" + utils.random_choices(6) + "." + parent
            rand2 = "wf" + utils.random_choices(6) + "." + parent
            ips1 = set(utils.get_ip(rand1, log_flag=False) or [])
            ips2 = set(utils.get_ip(rand2, log_flag=False) or [])
            if ips1 and ips2 and ips1 == ips2:
                self.wildcard_map[parent] = ips1
                logger.info(f"detected wildcard zone: *.{parent} -> {ips1}")

        logger.info("start get wildcard_map with {} wildcard zones".format(len(self.wildcard_map)))

    def clear_wildcard_domain_info(self, info_list):
        if not getattr(self, 'wildcard_map', None):
            return info_list
        cnt = 0
        new = []
        for info in info_list:
            domain = info.domain
            is_wildcard = False
            # 仅对其直接父级或上层域名的泛解析规则进行校验
            for parent, wc_ips in self.wildcard_map.items():
                if domain.endswith("." + parent) and domain != parent:
                    info_ips = set(info.ip_list)
                    if info_ips and info_ips.issubset(wc_ips):
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

    def insert_task_data(self):
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

        update_scheduler_run(scheduler_id)
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

def oneshot_ip_executors(target, scope_id, task_name, options):
    # This is a one-time execution, no scheduler_id
    executor = IPExecutor(target, scope_id, task_name, "oneshot", options)
    try:
        executor.insert_task_data()
        executor.run()
        executor.sync_asset_site_wih()

        from app.helpers.scope import update_scope_domain_status
        for ip in target.split():
            update_scope_domain_status(scope_id, ip, "probed", executor.task_id)
    except Exception as e:
        logger.warning("error on oneshot_ip_executors {}".format(executor.ip_target))
        logger.exception(e)
        executor.base_update_task.update_task_field("status", TaskStatus.ERROR)
        from app.helpers.scope import update_scope_domain_status
        for ip in target.split():
            update_scope_domain_status(scope_id, ip, "error", getattr(executor, 'task_id', None))