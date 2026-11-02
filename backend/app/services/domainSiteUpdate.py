import time
from app.services import build_domain_info,\
    probe_http, fetch_site, BaseUpdateTask

from app.helpers import find_domain_by_task_id

from app import utils


logger = utils.get_logger()


class DomainSiteUpdate(object):
    def __init__(self, task_id: str, domains: list, source: str):
        self.task_id = task_id
        self.domains = domains
        self.source = source
        self.domain_info_list = []
        self.available_sites = []
        self.base_update_task = BaseUpdateTask(self.task_id)

    def save_domain_info(self):
        domain_info_list = build_domain_info(self.domains)
        from app.utils.monitor_diff import tag_monitor_diff
        
        filtered_list = []
        for domain_info_obj in domain_info_list:
            domain_info = domain_info_obj.dump_json(flag=False)
            domain_info["task_id"] = self.task_id
            domain_info["source"] = self.source
            domain_parsed = utils.domain_parsed(domain_info["domain"])
            if domain_parsed:
                domain_info["fld"] = domain_parsed["fld"]
                
            tag_monitor_diff("domain", domain_info)
            if domain_info.get("change_status") != "unchanged":
                utils.conn_db('domain').insert_one(domain_info)
                filtered_list.append(domain_info_obj)

        self.domain_info_list = filtered_list

    def probe_sites(self):
        available_domains = []
        for domain_info_obj in self.domain_info_list:
            available_domains.append(domain_info_obj.domain)

        self.available_sites = probe_http(available_domains, 15)

    def save_site_info(self):
        site_info_list = fetch_site(self.available_sites)

        # [第一性原理：防御重复站点] 查询该 task_id 目前数据库中已有的 site 列表
        existing_sites = set()
        for doc in utils.conn_db('site').find({'task_id': self.task_id}, {'site': 1}):
            existing_sites.add(doc.get('site'))

        deduplicated_site_info_list = []
        seen_sites_in_list = set()

        for site_info in site_info_list:
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

        site_info_list = deduplicated_site_info_list
        from app.utils.monitor_diff import tag_monitor_diff
        
        filtered_list = []
        for info in site_info_list:
            tag_monitor_diff("site", info)
            if info.get("change_status") != "unchanged":
                filtered_list.append(info)
                
        site_info_list = filtered_list

        if site_info_list:
            from pymongo import UpdateOne
            operations = []
            for info in site_info_list:
                operations.append(UpdateOne(
                    {'task_id': info['task_id'], 'site': info['site']},
                    {'$set': info},
                    upsert=True
                ))
            if operations:
                utils.conn_db('site').bulk_write(operations)

        # 站点识别反哺系统服务与端口资产
        try:
            from app.services.commonTask import sync_service_from_site
            sync_service_from_site(self.task_id, site_info_list)
        except Exception as e:
            logger.warning("sync_service_from_site error in domainSiteUpdate for task {}: {}".format(self.task_id, e))

        # Update available_sites to exactly match the fetched sites
        # This ensures site_screenshot targets the exact URLs in the database
        self.available_sites = []
        for site_info in site_info_list:
            self.available_sites.append(site_info["site"])

    # 对域名进行检查，如果域名不在任务范围内，就不进行更新
    def set_and_check_domains(self):
        task_domains = find_domain_by_task_id(self.task_id)
        self.domains = list(set(self.domains) - set(task_domains))

    def site_screenshot(self):
        from app.config import Config
        from app import services
        
        logger.info("start domain site screenshot task_id: {}, len: {}".format(self.task_id, len(self.available_sites)))
        capture_save_dir = Config.SCREENSHOT_DIR + "/" + self.task_id
        services.site_screenshot(self.available_sites, concurrency=4, capture_dir=capture_save_dir)
        logger.info("end domain site screenshot")

    def run(self):
        status_name = f"{self.source}_domain_update"

        self.set_and_check_domains()

        logger.info("start domain site update task_id: {}, len:{}, source: {}".format(self.task_id,
                                                                                      len(self.domains), self.source))
        self.base_update_task.update_task_field("status", status_name)

        t1 = time.time()
        self.save_domain_info()
        self.probe_sites()
        self.save_site_info()
        self.site_screenshot()
        elapse = time.time() - t1

        self.base_update_task.update_services(status_name, elapse)

        logger.info("end domain site update elapse {}".format(elapse))


# 将域名直接加到任务数据中，只加到域名和站点表中，
# 没有检验添加的域名是否在任务范围中
# 会检验域名是否已经存在任务中
def domain_site_update(task_id: str, domains: list, source: str):
    DomainSiteUpdate(task_id, domains, source).run()