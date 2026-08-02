from app.helpers import asset_site, get_scope_by_scope_id
from app.services import run_wih
from app.utils import get_logger, check_domain_black
from app.modules import WihRecord
from app import utils

logger = get_logger()


class AssetWihMonitor(object):
    def __init__(self, scope_id: str):
        self.scope_id = scope_id
        self.scope_domains = []  # 资产分组中的域名范围
        self.scope_name = None  # 资产分组名称
        self.sites = []

    def init_scope_data(self):
        scope_data = get_scope_by_scope_id(self.scope_id)
        if not scope_data:
            raise Exception("没有找到资产组 {}".format(self.scope_id))

        self.scope_name = scope_data.get("name", "")
        # 直接使用 domain_array，兼容历史数据则回退至 scope_array
        if "domain_array" in scope_data:
            self.scope_domains = scope_data.get("domain_array", [])
        else:
            scope_type = scope_data.get("scope_type", "")
            if scope_type == "domain":
                self.scope_domains = scope_data.get("scope_array", [])

        self.sites = asset_site.find_site_by_scope_id(self.scope_id)


    def _batch_save_wih_results(self, wih_results) -> list:
        results = []
        from pymongo import UpdateOne
        batch_size = 1000

        for i in range(0, len(wih_results), batch_size):
            batch_items = wih_results[i:i + batch_size]
            bulk_operations = []

            # 1. 抽取当前批次的查询条件
            or_conditions = []
            for item in batch_items:
                or_conditions.append({"site": item.site, "fnv_hash": item.fnv_hash})

            # 2. 仅针对当前批次查询已存在的记录，构建微型内存映射集合
            existing_set = set()
            if or_conditions:
                cursor = utils.conn_db('asset_wih').find(
                    {"scope_id": self.scope_id, "$or": or_conditions},
                    {"site": 1, "fnv_hash": 1, "_id": 0}
                )
                existing_set = {(doc.get("site", ""), str(doc.get("fnv_hash", ""))) for doc in cursor}

            # 3. 遍历批次构建原子操作
            for item in batch_items:
                dedup_key = (item.site, str(item.fnv_hash))
                query = {"scope_id": self.scope_id, "site": item.site, "fnv_hash": item.fnv_hash}

                if dedup_key in existing_set:
                    # 已存在，仅更新最后发现时间
                    bulk_operations.append(UpdateOne(query, {"$set": {"update_date": utils.curr_date_obj()}}))
                else:
                    # 预过滤逻辑（黑名单、合规性检查）
                    if item.recordType == "domain":
                        if self.scope_domains:
                            if not domain_in_scope_domain(item.content, self.scope_domains):
                                continue
                        if utils.check_domain_black(item.content) or utils.is_forbidden_domain(item.content):
                            continue
                    
                    # 确定为新增漏洞
                    record_dict = item.dump_json()
                    curr_date = utils.curr_date_obj()
                    record_dict.update({
                        "scope_id": self.scope_id,
                        "save_date": curr_date,
                        "update_date": curr_date
                    })
                    
                    bulk_operations.append(UpdateOne(query, {"$set": record_dict}, upsert=True))
                    results.append(item)
                    # 为了防止批次内自身存在重复项，加入微型集合
                    existing_set.add(dedup_key)
            
            # 4. 执行微批次写入
            if bulk_operations:
                utils.conn_db('asset_wih').bulk_write(bulk_operations, ordered=False)
                
        return results

    def run(self):
        self.init_scope_data()

        logger.info("run AssetWihMonitor, scope_id: {} sites: {}".format(self.scope_id, len(self.sites)))

        if len(self.sites) == 0:
            return []

        wih_results = run_wih(self.sites)
        results = self._batch_save_wih_results(wih_results)

        logger.info("AssetWihMonitor, scope_id: {} results: {}".format(self.scope_id, len(results)))

        return results


def asset_wih_monitor(scope_id: str):
    monitor = AssetWihMonitor(scope_id)
    results = monitor.run()
    return results


def domain_in_scope_domain(domain: str, scope_domain: list):
    for scope in scope_domain:
        if domain == scope or domain.endswith("." + scope):
            return True
    return False
