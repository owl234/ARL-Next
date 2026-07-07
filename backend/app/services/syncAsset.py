import copy
import re
from app.utils import conn_db as conn
from app import utils
logger = utils.get_logger()


class SyncAsset(object):
    def __init__(self, task_id, scope_id, update_flag=False,  category=None, task_name=""):
        self.available_category = [
            "site", "domain", "ip", "wih",
            "cert", "service", "fileleak", "url", "vuln", 
            "npoc_service", "cip", "nuclei_result", "stat_finger"
        ]

        if category is None:
            self.category_list = self.available_category
        else:
            self.category_list = category

        self.task_id = task_id
        self.scope_id = scope_id
        self.task_name = task_name
        self.update_flag = update_flag

        self.new_asset_map = {
            "site": [],
            "domain": [],
            "ip": [],
            "task_name": task_name,
            "wih": [],
            "cert": [],
            "service": [],
            "fileleak": [],
            "url": [],
            "vuln": [],
            "npoc_service": [],
            "cip": [],
            "nuclei_result": [],
            "stat_finger": []
        }

        self.new_asset_counter = {k: 0 for k in self.available_category}
        self.max_record_asset_count = 10

    def site_in_asset_site(self, site: str) -> bool:
        """站点包含? 和 ; 非严格判断站点是否在资产组里面"""

        # "?" 和 ";"不在就返回False
        if "?" not in site and ";" not in site:
            return False

        site = site.split("?")[0]
        site = site.split(";")[0]

        query = {"scope_id": self.scope_id, "site": {"$regex": "^" + re.escape(site)}}
        item = conn("asset_site").find_one(query)
        if item is None:
            return False
        return True

    def sync_by_category(self, category):
        dist_collection = 'asset_{}'.format(category)
        for data in conn(category).find({"task_id": self.task_id}):
            data_content = data.get(category)
            query = {"scope_id": self.scope_id, category: data_content}

            if category == "wih":
                query = {"scope_id": self.scope_id, "fnv_hash": data["fnv_hash"]}
                data_content = data["fnv_hash"]
            elif category == "cert":
                query = {"scope_id": self.scope_id, "ip": data.get("ip"), "cert.fingerprint.sha256": data.get("cert", {}).get("fingerprint", {}).get("sha256")}
                data_content = f"{data.get('ip')}_{data.get('cert', {}).get('fingerprint', {}).get('sha256')}"
            elif category == "service":
                query = {"scope_id": self.scope_id, "service_name": data.get("service_name")}
                data_content = data.get("service_name")
            elif category == "fileleak":
                query = {"scope_id": self.scope_id, "url": data.get("url")}
                data_content = data.get("url")
            elif category == "url":
                query = {"scope_id": self.scope_id, "url": data.get("url")}
                data_content = data.get("url")
            elif category == "vuln":
                query = {"scope_id": self.scope_id, "target": data.get("target"), "vul_name": data.get("vul_name")}
                data_content = f"{data.get('target')}_{data.get('vul_name')}"
            elif category == "npoc_service":
                query = {"scope_id": self.scope_id, "host": data.get("host"), "port": data.get("port")}
                data_content = f"{data.get('host')}:{data.get('port')}"
            elif category == "cip":
                query = {"scope_id": self.scope_id, "cidr_ip": data.get("cidr_ip")}
                data_content = data.get("cidr_ip")
            elif category == "nuclei_result":
                query = {"scope_id": self.scope_id, "target": data.get("target"), "template_id": data.get("template_id")}
                data_content = f"{data.get('target')}_{data.get('template_id')}"
            elif category == "stat_finger":
                query = {"scope_id": self.scope_id, "name": data.get("name")}
                data_content = data.get("name")

            del data["_id"]
            data["scope_id"] = self.scope_id

            # 如果site存在就先粗暴跳过
            if category == "site" and self.site_in_asset_site(data["site"]):
                continue

            old = conn(dist_collection).find_one(query)
            if old is None:
                data["save_date"] = utils.curr_date_obj()
                data["update_date"] = data["save_date"]
                logger.debug("sync {}, insert {}  {} -> {}".format(
                    category, data_content, self.task_id, self.scope_id))

                #记录新插入的资产
                if category in self.new_asset_map:
                    if self.new_asset_counter[category] < self.max_record_asset_count:
                        self.new_asset_map[category].append(copy.deepcopy(data))
                    self.new_asset_counter[category] += 1

                conn(dist_collection).insert_one(data)

            if old and self.update_flag:
                curr_date = utils.curr_date_obj()
                data["save_date"] = old.get("save_date", curr_date)
                data["update_date"] = curr_date
                if category == 'ip':
                    if data.get("domain") and old.get("domain"):
                        old["domain"].extend(data["domain"])
                        data["domain"] = list(set(old["domain"]))
                elif category == 'service':
                    if data.get("service_info") and old.get("service_info"):
                        # Merge list of dicts based on ip and port
                        existing_keys = {f"{item['ip']}:{item['port_id']}" for item in old["service_info"] if 'ip' in item and 'port_id' in item}
                        for new_item in data["service_info"]:
                            if f"{new_item.get('ip')}:{new_item.get('port_id')}" not in existing_keys:
                                old["service_info"].append(new_item)
                        data["service_info"] = old["service_info"]

                logger.debug("sync {}, replace {}  {} -> {}".format(
                    category, data_content, self.task_id, self.scope_id))
                conn(dist_collection).find_one_and_replace(query, data)

    def run(self):
        logger.info("start sync {} -> {}".format(self.task_id, self.scope_id))
        for category in self.category_list:
            if category not in self.available_category:
                logger.warning("not found {} category in {}".format(category, self.available_category))
                continue

            self.sync_by_category(category)

        logger.info("end sync {} -> {}, result: {}".format(self.task_id, self.scope_id, self.new_asset_counter))

        return self.new_asset_map, self.new_asset_counter


def sync_asset(task_id, scope_id, update_flag=False,  category=None, push_flag=False, task_name=""):
    sync = SyncAsset(task_id=task_id, scope_id=scope_id,
                     update_flag=update_flag, category=category, task_name=task_name)
    new_asset_map, new_asset_counter = sync.run()
    if 'ip' in new_asset_map:
        new_asset_map.pop('ip')

    if 'ip' in new_asset_counter:
        new_asset_counter.pop('ip')

    if push_flag:
        utils.message_push(asset_map=new_asset_map, asset_counter=new_asset_counter)
