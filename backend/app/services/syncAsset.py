import copy
import re
from bson import ObjectId
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
        self.update_asset_map = copy.deepcopy(self.new_asset_map)
        self.update_asset_counter = {k: 0 for k in self.available_category}
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
        task_data_cursor = conn(category).find({"task_id": self.task_id})
        
        chunk_size = 500
        chunk = []
        for data in task_data_cursor:
            chunk.append(data)
            if len(chunk) >= chunk_size:
                self._process_sync_chunk(category, dist_collection, chunk)
                chunk = []
                
        if chunk:
            self._process_sync_chunk(category, dist_collection, chunk)

    def _process_sync_chunk(self, category, dist_collection, chunk):
        from pymongo import InsertOne, ReplaceOne

        queries = []
        for data in chunk:
            data_content = data.get(category)
            query = {"scope_id": self.scope_id, category: data_content}

            if category == "wih":
                query = {"scope_id": self.scope_id, "site": data.get("site"), "fnv_hash": data["fnv_hash"]}
                data_content = f"{data.get('site')}_{data['fnv_hash']}"
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

            if "_id" in data:
                del data["_id"]
            data["scope_id"] = self.scope_id
            
            data["_tmp_query"] = query
            data["_tmp_data_content"] = data_content
            queries.append(query)
            
        existing_items = {}
        if queries:
            for old in conn(dist_collection).find({"$or": queries}):
                old_data_content = old.get(category)
                if category == "wih":
                    old_data_content = f"{old.get('site')}_{old.get('fnv_hash')}"
                elif category == "cert":
                    old_data_content = f"{old.get('ip')}_{old.get('cert', {}).get('fingerprint', {}).get('sha256')}"
                elif category == "service":
                    old_data_content = old.get("service_name")
                elif category == "fileleak":
                    old_data_content = old.get("url")
                elif category == "url":
                    old_data_content = old.get("url")
                elif category == "vuln":
                    old_data_content = f"{old.get('target')}_{old.get('vul_name')}"
                elif category == "npoc_service":
                    old_data_content = f"{old.get('host')}:{old.get('port')}"
                elif category == "cip":
                    old_data_content = old.get("cidr_ip")
                elif category == "nuclei_result":
                    old_data_content = f"{old.get('target')}_{old.get('template_id')}"
                elif category == "stat_finger":
                    old_data_content = old.get("name")
                    
                existing_items[old_data_content] = old

        bulk_operations = []
        for data in chunk:
            query = data.pop("_tmp_query")
            data_content = data.pop("_tmp_data_content")
            
            old = existing_items.get(data_content)
            
            if old is None:
                data["save_date"] = utils.curr_date_obj()
                data["update_date"] = data["save_date"]
                if category == 'site':
                    raw_tags = data.get("tag") or []
                    if isinstance(raw_tags, str):
                        raw_tags = [raw_tags]
                    elif not isinstance(raw_tags, list):
                        raw_tags = []
                    tags = list(dict.fromkeys(raw_tags))
                    if "待测试" not in tags:
                        tags.append("待测试")
                    data["tag"] = tags

                logger.debug("sync {}, insert {}  {} -> {}".format(
                    category, data_content, self.task_id, self.scope_id))

                if category in self.new_asset_map:
                    if self.new_asset_counter[category] < self.max_record_asset_count:
                        self.new_asset_map[category].append(copy.deepcopy(data))
                    self.new_asset_counter[category] += 1

                bulk_operations.append(InsertOne(data))

            if old and self.update_flag:
                curr_date = utils.curr_date_obj()
                data["save_date"] = old.get("save_date", curr_date)
                data["update_date"] = curr_date

                # [第一性原理：资产溯源防降级保护]
                # 若资产库原有资产已有具体技术来源（非 monitor），而新进入的记录来源为空或仅为 monitor，则严禁覆盖原有真实来源
                if category in ['domain', 'url']:
                    old_source = old.get("source")
                    new_source = data.get("source")
                    if old_source and old_source != 'monitor' and (not new_source or new_source == 'monitor'):
                        data["source"] = old_source

                if category == 'ip':
                    if data.get("domain") and old.get("domain"):
                        old["domain"].extend(data["domain"])
                        data["domain"] = list(set(old["domain"]))
                elif category == 'cip':
                    old_ip_list = old.get("ip_list") or []
                    new_ip_list = data.get("ip_list") or []
                    if isinstance(old_ip_list, str):
                        old_ip_list = [old_ip_list]
                    if isinstance(new_ip_list, str):
                        new_ip_list = [new_ip_list]
                    merged_ip_list = list(dict.fromkeys(old_ip_list + new_ip_list))

                    old_domain_list = old.get("domain_list") or []
                    new_domain_list = data.get("domain_list") or []
                    if isinstance(old_domain_list, str):
                        old_domain_list = [old_domain_list]
                    if isinstance(new_domain_list, str):
                        new_domain_list = [new_domain_list]
                    merged_domain_list = list(dict.fromkeys(old_domain_list + new_domain_list))

                    data["ip_list"] = merged_ip_list
                    data["ip_count"] = len(merged_ip_list)
                    data["domain_list"] = merged_domain_list
                    data["domain_count"] = len(merged_domain_list)
                elif category == 'service':
                    if data.get("service_info") and old.get("service_info"):
                        existing_keys = {f"{item['ip']}:{item['port_id']}" for item in old["service_info"] if 'ip' in item and 'port_id' in item}
                        for new_item in data["service_info"]:
                            if f"{new_item.get('ip')}:{new_item.get('port_id')}" not in existing_keys:
                                old["service_info"].append(new_item)
                        data["service_info"] = old["service_info"]
                elif category == 'site':
                    old_tags = old.get("tag") or []
                    if isinstance(old_tags, str):
                        old_tags = [old_tags]
                    elif not isinstance(old_tags, list):
                        old_tags = []
                    new_tags = data.get("tag") or []
                    if isinstance(new_tags, str):
                        new_tags = [new_tags]
                    elif not isinstance(new_tags, list):
                        new_tags = []
                    merged_tags = list(dict.fromkeys(old_tags + new_tags))

                    # 🛡️【特征对比判断】：存量站点日常扫描不复活「待测试」；仅当探测到新指纹、标题变更或状态码变动时重新打标
                    def _extract_finger_names(finger_data):
                        if not finger_data:
                            return set()
                        if isinstance(finger_data, str):
                            return {finger_data}
                        if not isinstance(finger_data, list):
                            return set()
                        names = set()
                        for item in finger_data:
                            if isinstance(item, dict) and item.get("name"):
                                names.add(item["name"])
                            elif isinstance(item, str):
                                names.add(item)
                        return names

                    old_fingers = _extract_finger_names(old.get("finger"))
                    new_fingers = _extract_finger_names(data.get("finger"))
                    has_new_finger = bool(new_fingers - old_fingers)

                    old_title = old.get("title") or ""
                    new_title = data.get("title") or ""
                    has_title_change = bool(new_title and new_title != old_title)

                    old_status = old.get("status")
                    new_status = data.get("status")
                    has_status_change = bool(new_status and new_status != old_status)

                    if has_new_finger or has_title_change or has_status_change:
                        if "待测试" not in merged_tags:
                            merged_tags.append("待测试")

                    data["tag"] = merged_tags

                if category in self.update_asset_map:
                    if self.update_asset_counter[category] < self.max_record_asset_count:
                        self.update_asset_map[category].append(copy.deepcopy(data))
                    self.update_asset_counter[category] += 1

                logger.debug("sync {}, replace {}  {} -> {}".format(
                    category, data_content, self.task_id, self.scope_id))
                bulk_operations.append(ReplaceOne(query, data))
                
        if bulk_operations:
            conn(dist_collection).bulk_write(bulk_operations, ordered=False)

    def run(self):
        logger.info("start sync {} -> {}".format(self.task_id, self.scope_id))
        for category in self.category_list:
            if category not in self.available_category:
                logger.warning("not found {} category in {}".format(category, self.available_category))
                continue

            self.sync_by_category(category)

        # 🛡️【第一性原理：零新增探针·多源情报反哺闭环】
        # 任务结算与资产入库后，利用已探明的 fileleak(200)/cert/vuln 数据原子反哺 site 指纹并清洗误杀标签
        try:
            self.enrich_and_heal_site_assets()
        except Exception as e:
            logger.error(f"SyncAsset enrich_and_heal_site_assets error: {e}", exc_info=True)

        logger.info("end sync {} -> {}, result: {}, update: {}".format(self.task_id, self.scope_id, self.new_asset_counter, self.update_asset_counter))

        if self.scope_id and self.task_id:
            try:
                task_info = utils.conn_db('task').find_one({"_id": ObjectId(self.task_id)})
                if task_info:
                    target_str = task_info.get("target", "")
                    from app.helpers import get_ip_domain_list, update_scope_domain_status
                    target_ips, target_domains = get_ip_domain_list(target_str)
                    for td in target_domains:
                        update_scope_domain_status(self.scope_id, td, "probed", self.task_id)
                    for tip in target_ips:
                        update_scope_domain_status(self.scope_id, tip, "probed", self.task_id)
            except Exception as e:
                logger.error(f"SyncAsset update domain/ip status error: {e}")

        return self.new_asset_map, self.new_asset_counter, self.update_asset_map, self.update_asset_counter

    def enrich_and_heal_site_assets(self):
        """
        [第一性原理：零新增探针·多源情报反哺闭环]
        利用本任务已采集的 fileleak(200)、cert、vuln 等情报，原子反哺站点指纹，
        并智能清洗误判的「无效」标签，确保云原生高危资产（如 K8s 节点）不再被遗漏。
        """
        if not self.task_id and not self.scope_id:
            return

        task_site_coll = conn('site')
        asset_site_coll = conn('asset_site')
        fileleak_coll = conn('fileleak')
        vuln_coll = conn('vuln')
        cert_coll = conn('cert')

        site_query = {"task_id": self.task_id} if self.task_id else {"scope_id": self.scope_id}
        sites = list(task_site_coll.find(site_query))
        if not sites and self.scope_id:
            sites = list(asset_site_coll.find({"scope_id": self.scope_id}))

        if not sites:
            return

        scope_or_task = []
        if self.scope_id:
            scope_or_task.append({"scope_id": self.scope_id})
        if self.task_id:
            scope_or_task.append({"task_id": self.task_id})
        base_scope_filter = {"$or": scope_or_task} if len(scope_or_task) > 1 else (scope_or_task[0] if scope_or_task else {})

        from collections import defaultdict
        from urllib.parse import urlparse
        from pymongo import UpdateOne

        # 预先批量拉取情报并构建内存哈希索引，规避循环内 N+1 查询开销
        # 1. 批量预载 fileleak (status_code 200, 301, 302)
        leaks_by_site = defaultdict(list)
        leak_base_filter = dict(base_scope_filter)
        leak_base_filter["status_code"] = {"$in": [200, 301, 302]}
        raw_leaks = list(fileleak_coll.find(leak_base_filter, {"site": 1, "url": 1, "status_code": 1}))
        if self.scope_id:
            raw_leaks.extend(list(conn('asset_fileleak').find(
                {"scope_id": self.scope_id, "status_code": {"$in": [200, 301, 302]}},
                {"site": 1, "url": 1, "status_code": 1}
            )))
        for lk in raw_leaks:
            s_key = lk.get("site")
            if s_key:
                leaks_by_site[s_key].append(lk)

        # 2. 批量预载 vuln
        vulns_by_target = defaultdict(list)
        raw_vulns = list(vuln_coll.find(base_scope_filter, {"target": 1, "vuln_url": 1, "app_name": 1, "plugin_name": 1}))
        if self.scope_id:
            raw_vulns.extend(list(conn('asset_vuln').find(
                {"scope_id": self.scope_id},
                {"target": 1, "vuln_url": 1, "app_name": 1, "plugin_name": 1}
            )))
        for v in raw_vulns:
            tgt = v.get("target")
            v_url = v.get("vuln_url")
            if tgt:
                vulns_by_target[tgt].append(v)
            if v_url and v_url != tgt:
                vulns_by_target[v_url].append(v)

        # 3. 批量预载 cert (按 ip:port 索引)
        certs_by_ip_port = defaultdict(list)
        raw_certs = list(cert_coll.find(base_scope_filter, {"ip": 1, "port": 1, "cert": 1}))
        if self.scope_id:
            raw_certs.extend(list(conn('asset_cert').find(
                {"scope_id": self.scope_id},
                {"ip": 1, "port": 1, "cert": 1}
            )))
        for c in raw_certs:
            c_ip = c.get("ip")
            c_port = c.get("port")
            if c_ip and c_port is not None:
                certs_by_ip_port[f"{c_ip}:{c_port}"].append(c)

        task_bulk_ops = []
        asset_bulk_ops = []

        for s in sites:
            site_url = s.get("site")
            if not site_url:
                continue

            ip = s.get("ip") or ""
            try:
                parsed = urlparse(site_url)
                if parsed.port:
                    site_port = parsed.port
                elif parsed.scheme == "https":
                    site_port = 443
                elif parsed.scheme == "http":
                    site_port = 80
                elif ":" in site_url.split("/")[0]:
                    site_port = int(site_url.split("/")[0].split(":")[1])
                else:
                    site_port = 80
            except Exception:
                site_port = 80

            existing_fingers = s.get("finger") or []
            if not isinstance(existing_fingers, list):
                existing_fingers = []

            orig_names = set()
            for f in existing_fingers:
                if isinstance(f, dict) and f.get("name"):
                    orig_names.add(f["name"])
                elif isinstance(f, str):
                    orig_names.add(f)

            current_names = set(orig_names)

            # 1. 关联反哺 fileleak 成果 (兼顾当前任务与存量资产库，内存 O(1) 匹配)
            leaks = leaks_by_site.get(site_url, [])
            for lk in leaks:
                u = lk.get("url", "")
                st = lk.get("status_code")
                if st == 200:
                    if u.endswith("/pods") or "/pods?" in u:
                        current_names.add("Kubernetes-Kubelet")
                    elif u.endswith("/healthz") or "/healthz?" in u:
                        if site_port == 10256:
                            current_names.add("Kubernetes-Kube-Proxy")
                        elif site_port in (10255, 10250):
                            current_names.add("Kubernetes-Kubelet")
                        elif site_port == 9091:
                            current_names.add("Milvus")
                        elif site_port == 8093:
                            current_names.add("Kubernetes-Edge")
                    elif u.endswith("/metrics") or "/metrics?" in u:
                        current_names.add("Prometheus-Metrics")
                    elif u.endswith("/readyz") or "/readyz?" in u or u.endswith("/livez") or "/livez?" in u:
                        current_names.add("Kubernetes-Probe")
                    elif "/actuator" in u:
                        current_names.add("Spring-Boot-Actuator")
                    elif "/swagger" in u or "/api-docs" in u or "/openapi.json" in u:
                        current_names.add("Swagger-UI")
                    elif "/api/v1/credential/users" in u or "/api/v1/collections" in u:
                        current_names.add("Milvus")
                elif st in (301, 302):
                    if u.endswith("/pms") or "/pms/" in u:
                        current_names.add("HP-System-Management")

            # 2. 关联反哺 vuln 成果 (内存 O(1) 匹配)
            vulns = vulns_by_target.get(site_url, [])
            for v in vulns:
                app_name = v.get("app_name") or v.get("plugin_name") or "Vulnerability"
                current_names.add(f"Vuln:{app_name}")

            # 3. 关联反哺 cert 成果 (按 IP 与端口精准对齐，内存 O(1) 匹配)
            if ip:
                certs = certs_by_ip_port.get(f"{ip}:{site_port}", [])
                for c in certs:
                    cert_dict = c.get("cert") or {}
                    subject_dn = (cert_dict.get("subject_dn") or "").lower()
                    issuer_dn = (cert_dict.get("issuer_dn") or "").lower()
                    if "konnectivity" in subject_dn or "konnectivity" in issuer_dn:
                        current_names.add("Kubernetes-Konnectivity")
                    elif "kubernetes" in subject_dn or "k8s" in subject_dn or "kubernetes" in issuer_dn:
                        current_names.add("Kubernetes")

            # 4. 判断是否有新增指纹或需自愈标签
            raw_tags = s.get("tag") or []
            if isinstance(raw_tags, str):
                raw_tags = [raw_tags]
            elif not isinstance(raw_tags, list):
                raw_tags = []

            has_invalid_tag = "无效" in raw_tags
            new_finger_names = current_names - orig_names

            if new_finger_names or (current_names and has_invalid_tag):
                updated_finger_list = []
                seen = set()
                for f in existing_fingers:
                    name = f.get("name") if isinstance(f, dict) else f
                    if name and name not in seen:
                        updated_finger_list.append(f if isinstance(f, dict) else {
                            "icon": "default.png", "name": name, "confidence": "100", "version": "", "website": "", "categories": []
                        })
                        seen.add(name)
                for name in sorted(current_names):
                    if name not in seen:
                        updated_finger_list.append({
                            "icon": "default.png", "name": name, "confidence": "100", "version": "", "website": "", "categories": []
                        })
                        seen.add(name)

                clean_tags = [t for t in raw_tags if t != "无效"]
                if "待测试" not in clean_tags:
                    clean_tags.append("待测试")

                task_bulk_ops.append(UpdateOne(
                    {"_id": s["_id"]},
                    {"$set": {"finger": updated_finger_list, "tag": clean_tags}}
                ))

                if self.scope_id:
                    asset_bulk_ops.append(UpdateOne(
                        {"scope_id": self.scope_id, "site": site_url},
                        {"$set": {"finger": updated_finger_list, "tag": clean_tags}}
                    ))

                if len(task_bulk_ops) >= 200:
                    task_site_coll.bulk_write(task_bulk_ops, ordered=False)
                    task_bulk_ops = []
                if len(asset_bulk_ops) >= 200:
                    asset_site_coll.bulk_write(asset_bulk_ops, ordered=False)
                    asset_bulk_ops = []

        if task_bulk_ops:
            task_site_coll.bulk_write(task_bulk_ops, ordered=False)
        if asset_bulk_ops:
            asset_site_coll.bulk_write(asset_bulk_ops, ordered=False)

def sync_asset(task_id, scope_id, update_flag=False,  category=None, push_flag=False, task_name=""):
    sync = SyncAsset(task_id=task_id, scope_id=scope_id,
                     update_flag=update_flag, category=category, task_name=task_name)
    ret = sync.run()
    if not ret or not isinstance(ret, tuple) or len(ret) != 4:
        return {}, {}, {}, {}
    new_asset_map, new_asset_counter, update_asset_map, update_asset_counter = ret

    # 将本次同步的新增入库与更新存量计数落库到 task.sync_summary，便于列表页区分零新增与存量刷新。
    # 该逻辑内联在 sync_asset 中，以兼容仅按函数名通过 AST 加载 SyncAsset/sync_asset 的测试框架。
    if task_id:
        try:
            tid = ObjectId(str(task_id))
            clean_new = {
                k: int(v) for k, v in (new_asset_counter or {}).items()
                if isinstance(v, (int, float)) and int(v) > 0
            }
            clean_update = {
                k: int(v) for k, v in (update_asset_counter or {}).items()
                if isinstance(v, (int, float)) and int(v) > 0
            }
            summary = {
                "new": clean_new,
                "update": clean_update,
                "total_new": sum(clean_new.values()),
                "total_update": sum(clean_update.values()),
                "updated_at": utils.curr_date(),
            }
            task_col = conn('task')
            if hasattr(task_col, "update_one"):
                task_col.update_one({"_id": tid}, {"$set": {"sync_summary": summary}})
        except Exception as exc:
            logger.debug("record task sync_summary failed for %s: %s", task_id, exc)

    if push_flag:
        utils.message_push(asset_map=new_asset_map, asset_counter=new_asset_counter, update_map=update_asset_map, update_counter=update_asset_counter)

    return new_asset_map, new_asset_counter, update_asset_map, update_asset_counter
