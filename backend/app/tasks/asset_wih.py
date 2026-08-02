import time
from app import utils
from app.modules import TaskStatus
from app.utils import get_logger
from app.services.commonTask import CommonTask
from app.services import BaseUpdateTask, domain_site_update, sync_asset
from app.services.asset_wih_monitor import asset_wih_monitor
from app.helpers.asset_domain import find_domain_by_scope_id
from app.helpers.scope import get_scope_by_scope_id

logger = get_logger()


class AssetWihUpdateTask(CommonTask):
    def __init__(self, task_id: str, scope_id: str):
        super().__init__(task_id=task_id)

        self.task_id = task_id
        self.scope_id = scope_id
        self.base_update_task = BaseUpdateTask(self.task_id)
        self.wih_results = []

        self._scope_sub_domains = None

    def run(self):
        logger.info("run AssetWihUpdateTask, task_id:{} scope_id: {}".format(self.task_id, self.scope_id))
        self.run_wih_monitor()

        self.wih_results_save()

        if self.wih_results:
            self.run_wih_domain_update()

        # 插入统计信息
        self.insert_stat()

        logger.info("end AssetWihUpdateTask, task_id:{} results: {}".format(self.task_id, len(self.wih_results)))

    def insert_stat(self):
        self.insert_finger_stat()
        self.insert_task_stat()

    def wih_results_save(self):
        from pymongo import UpdateOne
        bulk_operations = []
        for record in self.wih_results:
            item = record.dump_json()
            item["task_id"] = self.task_id
            
            # 使用 UpdateOne 构建 Upsert 操作
            query = {"task_id": self.task_id, "site": item["site"], "fnv_hash": item["fnv_hash"]}
            bulk_operations.append(UpdateOne(query, {"$set": item}, upsert=True))
            
            # 分批写入防止内存爆炸
            if len(bulk_operations) >= 1000:
                utils.conn_db('wih').bulk_write(bulk_operations, ordered=False)
                bulk_operations.clear()
                
        # 写入残余批次
        if bulk_operations:
            utils.conn_db('wih').bulk_write(bulk_operations, ordered=False)

    def run_wih_monitor(self):
        service_name = "wih_monitor"
        self.base_update_task.update_task_field("status", service_name)
        start_time = time.time()

        self.wih_results = asset_wih_monitor(self.scope_id)

        elapsed = time.time() - start_time

        self.base_update_task.update_services(service_name, elapsed)

    @property
    def scope_sub_domains(self):
        if self._scope_sub_domains is None:
            self._scope_sub_domains = set(find_domain_by_scope_id(self.scope_id))
        return self._scope_sub_domains

    def run_wih_domain_update(self):
        scope_data = get_scope_by_scope_id(self.scope_id)
        if not scope_data:
            return

        if "domain_array" in scope_data:
            domain_array = scope_data.get("domain_array", [])
        else:
            if scope_data.get("scope_type") == "domain":
                domain_array = scope_data.get("scope_array", [])
            else:
                return

        if not domain_array:
            return

        domains = []
        for item in self.wih_results:
            if item.recordType == "domain":
                # 由于这些记录在入库前的 asset_wih_monitor 阶段已做过强校验（范围与黑名单），此处只需校验是否为新子域名即可
                if item.content in self.scope_sub_domains:
                    continue

                domains.append(item.content)

        if domains:
            domain_site_update(self.task_id, domains, "wih")

            sync_asset(task_id=self.task_id, scope_id=self.scope_id)


# 资产WIH更新监控任务
def asset_wih_update_task(task_id, scope_id, scheduler_id):
    from app.scheduler import update_job_run

    task = AssetWihUpdateTask(task_id=task_id, scope_id=scope_id)
    task.base_update_task.update_task_field("start_time", utils.curr_date())

    try:
        update_job_run(job_id=scheduler_id)
        task.run()
        task.base_update_task.update_task_field("status", TaskStatus.DONE)
    except Exception as e:
        logger.exception(e)

        task.base_update_task.update_task_field("status", TaskStatus.ERROR)

    task.base_update_task.update_task_field("end_time", utils.curr_date())
