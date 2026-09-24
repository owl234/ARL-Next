from bson import ObjectId
from app import utils
from app.services.commonTask import CommonTask, WebSiteFetch, TaskHeartbeat
from app.modules import TaskStatus
from app.tasks.poc import RiskCruising
from app.services import webhook
logger = utils.get_logger()


class AssetSiteUpdateTask(CommonTask):
    def __init__(self, task_id, scope_id):
        super().__init__(task_id=task_id)

        self.task_id = task_id
        self.scope_id = scope_id
        self.collection = "task"
        self.results = []

    def update_status(self, value):
        query = {"_id": ObjectId(self.task_id)}
        update = {"$set": {"status": value}}
        utils.conn_db(self.collection).update_one(query, update)

    def set_start_time(self):
        query = {"_id": ObjectId(self.task_id)}
        update = {"$set": {"start_time": utils.curr_date()}}
        utils.conn_db(self.collection).update_one(query, update)

    def set_end_time(self):
        query = {"_id": ObjectId(self.task_id)}
        update = {"$set": {"end_time": utils.curr_date()}}
        utils.conn_db(self.collection).update_one(query, update)

    def save_task_site(self, site_info_list):
        # [第一性原理：防御重复站点] 查询该 task_id 目前数据库中已有的 site 列表
        existing_sites = set()
        for doc in utils.conn_db('site').find({'task_id': self.task_id}, {'site': 1}):
            existing_sites.add(doc.get('site'))

        seen_sites_in_list = set()
        insert_count = 0

        filtered_sites = []
        for site_info in site_info_list:
            curr_site = site_info.get("site")
            if curr_site in existing_sites or curr_site in seen_sites_in_list:
                continue
            seen_sites_in_list.add(curr_site)
            site_info["task_id"] = self.task_id
            filtered_sites.append(site_info)
            
        if filtered_sites:
            utils.safe_insert_asset_many('site', ['task_id', 'site'], filtered_sites)
            insert_count += len(filtered_sites)
            
        logger.info("save {} to {}".format(insert_count, self.task_id))

    def monitor(self):
        from app.services.asset_site_monitor import AssetSiteMonitor, Domain2SiteMonitor
        self.update_status("fetch site")
        monitor = AssetSiteMonitor(scope_id=self.scope_id)
        monitor.build_change_list()

        if monitor.site_change_info_list:
            self.save_task_site(monitor.site_change_info_list)

        self.update_status("domain site monitor")
        domain2site_monitor = Domain2SiteMonitor(scope_id=self.scope_id)
        if domain2site_monitor.run():
            self.save_task_site(domain2site_monitor.site_info_list)

        self.update_status("send notify")
        html_report = ""
        if monitor.site_change_info_list:
            html_report = monitor.build_html_report()

        if domain2site_monitor.site_info_list:
            html_report += "\n<br/>"
            html_report += domain2site_monitor.html_report

        html_title = "[站点监控-{}] 灯塔消息推送".format(monitor.scope_name)
        
        markdown_report = ""
        if monitor.site_change_info_list:
            markdown_report = monitor.build_markdown_report()

        if domain2site_monitor.site_info_list:
            markdown_report += "\n"
            markdown_report += domain2site_monitor.dingding_markdown

        if markdown_report:
            # 防截断机制：限制最大字符数，避免推送失败
            if len(markdown_report) > 8000:
                markdown_report = markdown_report[:8000] + "\n\n> ⚠️ **预警：内容超出第三方推送长度限制，已被折叠，请登录控制台查看完整清单！**"
            from app.utils.push import unified_push
            unified_push("asset_site", html_title, markdown_report)

        if html_report or markdown_report:
            webhook.site_asset_web_hook(task_id=self.task_id, scope_id=self.scope_id)

    def run(self):
        with TaskHeartbeat(self.task_id, interval=60):
            self.set_start_time()
            self.monitor()
            self.insert_task_stat()
            self.update_status(TaskStatus.DONE)
            self.set_end_time()



# 资产站点更新监控任务
def asset_site_update_task(task_id, scope_id, scheduler_id):
    from app.scheduler import update_scheduler_run

    task = AssetSiteUpdateTask(task_id=task_id, scope_id=scope_id)
    try:
        update_scheduler_run(scheduler_id=scheduler_id)
        task.run()
    except Exception as e:
        logger.exception(e)

        task.update_status(TaskStatus.ERROR)
        task.set_end_time()


class AddAssetSiteTask(RiskCruising):
    def __init__(self, task_id):
        super().__init__(task_id=task_id)

    def asset_site_deduplication(self):
        related_scope_id = self.options.get("related_scope_id", "")
        if not related_scope_id:
            raise Exception("not found related_scope_id, task_id:{}".format(self.task_id))

        new_targets = []

        for url in self.targets:
            if "://" not in url:
                url = "http://" + url

            # 这里简单去下
            url = url.strip("/")
            site_data = utils.conn_db('asset_site').find_one({"site": url, "scope_id": related_scope_id})
            if site_data:
                logger.info("{} is in scope".format(url))
                continue
            new_targets.append(url)
        self.targets = new_targets

    def work(self):
        with self.safe_phase("asset_site_deduplication", self):
            self.asset_site_deduplication()
        
        with self.safe_phase("pre_set_site", self):
            self.pre_set_site()
            
        if self.user_target_site_set:
            web_site_fetch = WebSiteFetch(task_id=self.task_id,
                                          sites=list(self.user_target_site_set),
                                          options=self.options)
            with self.safe_phase("web_site_fetch", self):
                web_site_fetch.run()

            if self.options.get("file_leak"):
                with self.safe_phase("file_leak", self):
                    web_site_fetch.run_func("file_leak", web_site_fetch.file_leak)

            if self.options.get("nuclei_scan"):
                with self.safe_phase("nuclei_scan", self):
                    web_site_fetch.run_func("nuclei_scan", web_site_fetch.nuclei_scan)

        with self.safe_phase("common_run", self):
            self.common_run()


# 添加资产站点任务
def run_add_asset_site_task(task_id):
    query = {"_id": ObjectId(task_id)}
    task_data = utils.conn_db('task').find_one(query)

    if not task_data:
        return

    if task_data["status"] != "waiting":
        return

    r = AddAssetSiteTask(task_id)
    r.run()
