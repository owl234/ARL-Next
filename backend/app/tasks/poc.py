from threading import Thread
from app import utils
from app.modules import TaskStatus
from app.services import npoc
from app.config import Config
import time
from bson import ObjectId
from urllib.parse import urlparse
from app.services.commonTask import CommonTask, WebSiteFetch, TaskHeartbeat

logger = utils.get_logger()


def run_risk_cruising_task(task_id):
    query = {"_id": ObjectId(task_id)}
    task_data = utils.conn_db('task').find_one(query)

    if not task_data:
        return
    if task_data["status"] != "waiting":
        return

    r = RiskCruising(task_id)
    r.run()


class RiskCruising(CommonTask):
    def __init__(self, task_id):
        super().__init__(task_id=task_id)

        self.task_id = task_id
        query = {"_id": ObjectId(task_id)}
        self.query = query
        task_data = utils.conn_db('task').find_one(query)
        self.task_data = task_data
        self.options = self.task_data.get("options", {})

        self.poc_plugin_name = []
        self.brute_plugin_name = []
        self.result_set_id = self.task_data.get("result_set_id")
        self.targets = self.task_data.get("cruising_target")
        self.sniffer_target_set = set()
        self.npoc_service_target_set = set()
        self.user_target_site_set = set()  # 用户提交的目录站点
        self.available_sites = []

    def init_plugin_name(self):
        poc_config = self.options.get("poc_config", [])
        plugin_name = []
        for item in poc_config:
            if item.get("enable"):
                plugin_name.append(item["plugin_name"])

        self.poc_plugin_name = plugin_name

        brute_config = self.options.get("brute_config", [])
        plugin_name = []
        for item in brute_config:
            if item.get("enable"):
                plugin_name.append(item["plugin_name"])

        self.brute_plugin_name = plugin_name

    def set_relay_targets(self):
        # 对用户提交的 1.1.1.1:22 数据 进行设置到 sniffer_target_set
        if self.targets:
            for x in self.targets:
                o = urlparse(x)
                if not o.scheme and x:
                    self.sniffer_target_set.add(x)
                    continue

                if o.scheme in ["http", "https"]:
                    continue

                if o.netloc:
                    self.sniffer_target_set.add(o.netloc)

        if not self.result_set_id:
            return
        # 根据 result_set_id 查询 站点
        query_result_set = {"_id": ObjectId(self.result_set_id)}
        item = utils.conn_db('result_set').find_one(query_result_set)
        targets = item["items"]
        utils.conn_db('result_set').delete_one(query_result_set)
        self.targets = targets

    def npoc_service_detection(self):
        logger.info("start npoc_service_detection {}".format(len(self.sniffer_target_set)))
        result = npoc.run_sniffer(self.sniffer_target_set)
        for item in result:
            self.npoc_service_target_set.add(item["target"])
            item["task_id"] = self.task_id
            item["save_date"] = utils.curr_date()
        if result:
            utils.safe_insert_asset_many('npoc_service', ['task_id', 'target'], result)

    def run_poc(self):
        """运行poc，获取进度"""
        targets = self.available_sites + list(self.npoc_service_target_set)
        logger.info("start run poc {}*{}".format(len(self.poc_plugin_name), len(targets)))

        run_total = len(self.poc_plugin_name) * len(targets)
        npoc_instance = npoc.NPoC(tmp_dir=Config.TMP_PATH, concurrency=10)
        run_thread = Thread(target=npoc_instance.run_poc, args=(self.poc_plugin_name, targets))
        run_thread.start()
        while run_thread.is_alive():
            time.sleep(5)
            if npoc_instance.runner is not None:
                status = "poc {}/{}".format(npoc_instance.runner.runner_cnt, run_total)
                logger.info("[{}]runner cnt {}/{}".format(self.task_id,
                                                          npoc_instance.runner.runner_cnt, run_total))
                self.update_task_field("status", status)

        result = npoc_instance.result
        if result:
            for item in result:
                item["task_id"] = self.task_id
                item["save_date"] = utils.curr_date()
                if "plg_name" in item:
                    item["plugin_name"] = item.get("plg_name")
                if "target" in item:
                    item["vuln_url"] = item.get("target")
            utils.safe_insert_asset_many('vuln', ['task_id', 'target', 'plugin_name'], result)

    def run_brute(self):
        """运行爆破，获取进度"""
        target = self.available_sites + list(self.npoc_service_target_set)
        plugin_name = self.brute_plugin_name
        logger.info("start run brute {}*{}".format(len(plugin_name), len(target)))
        run_total = len(plugin_name) * len(target)

        npoc_instance = npoc.NPoC(tmp_dir=Config.TMP_PATH, concurrency=10)
        run_thread = Thread(target=npoc_instance.run_poc, args=(plugin_name, target))
        run_thread.start()
        while run_thread.is_alive():
            time.sleep(5)
            if npoc_instance.runner is not None:
                status = "brute {}/{}".format(npoc_instance.runner.runner_cnt, run_total)
                logger.info("[{}]runner cnt {}/{}".format(self.task_id,
                                                          npoc_instance.runner.runner_cnt, run_total))
                self.update_task_field("status", status)

        result = npoc_instance.result
        if result:
            for item in result:
                item["task_id"] = self.task_id
                item["save_date"] = utils.curr_date()
                if "plg_name" in item:
                    item["plugin_name"] = item.get("plg_name")
                if "target" in item:
                    item["vuln_url"] = item.get("target")
            utils.safe_insert_asset_many('vuln', ['task_id', 'target', 'plugin_name'], result)

    def update_services(self, status, elapsed):
        try:
            elapsed_val = float(elapsed)
        except (ValueError, TypeError):
            logger.error(f"update_services elapsed format error: {elapsed}")
            elapsed_val = 0.0
        elapsed_str = "{:.2f}".format(elapsed_val)
        self.update_task_field("status", status)
        update = {"$push": {"service": {"name": status, "elapsed": float(elapsed_str)}}}
        utils.conn_db('task').update_one(self.query, update)

    def update_task_field(self, field=None, value=None):
        update = {"$set": {field: value}}
        utils.conn_db('task').update_one(self.query, update)

    def pre_set_site(self):
        # *** 对用户提交的数据 保存到 user_target_site_set
        for x in self.targets:
            if "://" not in x:
                self.user_target_site_set.add("http://{}".format(x))
                continue

            if not x.startswith("http"):
                continue

            self.user_target_site_set.add(x)

    def work(self):
        # 对目标进行预先处理
        with self.safe_phase("pre_process", self):
            self.set_relay_targets()
            self.pre_set_site()

        web_site_fetch = WebSiteFetch(task_id=self.task_id,
                                      sites=list(self.user_target_site_set), options=self.options)
        
        with self.safe_phase("web_site_fetch", self):
            web_site_fetch.run()
            self.available_sites = web_site_fetch.available_sites

        with self.safe_phase("init_plugin_name", self):
            self.init_plugin_name()
            
        if self.options.get("npoc_service_detection"):
            with self.safe_phase("npoc_service_detection", self):
                self.npoc_service_detection()

        if self.options.get("file_leak"):
            with self.safe_phase("file_leak", self):
                web_site_fetch.run_func("file_leak", web_site_fetch.file_leak)

        if self.brute_plugin_name:
            with self.safe_phase("weak_brute", self):
                self.run_brute()

        if self.poc_plugin_name:
            with self.safe_phase("PoC", self):
                self.run_poc()

        with self.safe_phase("common_run", self):
            self.common_run()

        # nuclei_scan 放在最后执行，防止高并发扫描把目标打挂或者触发IP封禁
        if self.options.get("nuclei_scan"):
            with self.safe_phase("nuclei_scan", self):
                web_site_fetch.run_func("nuclei_scan", web_site_fetch.nuclei_scan)

    def run(self):
        with TaskHeartbeat(self.task_id, interval=60):
            try:
                self.update_task_field("start_time", utils.curr_date())
                self.work()
                self.update_task_field("status", TaskStatus.DONE)
            except Exception as e:
                self.update_task_field("status", TaskStatus.ERROR)
                logger.exception(e)

            self.update_task_field("end_time", utils.curr_date())

