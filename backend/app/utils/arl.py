from bson import ObjectId
from .conn import conn_db
from .IPy import IP
import re


def get_task_ids(domain):
    query = {"target": domain}
    return [str(item["_id"]) for item in conn_db('task').find(query, {"_id": 1})]


def get_domain_by_id(task_id):
    query = {"task_id": task_id}
    return [item["domain"] for item in conn_db('domain').find(query, {"domain": 1, "_id": 0}) if item.get("domain")]


def arl_domain(domain):
    from app.utils.domain import is_valid_domain
    if not domain or not is_valid_domain(domain):
        return []

    suffix = "." + domain
    domains = set()

    task_ids = get_task_ids(domain)
    if task_ids:
        for i in range(0, len(task_ids), 1000):
            chunk = task_ids[i:i + 1000]
            for item in conn_db('domain').find({"task_id": {"$in": chunk}}, {"domain": 1, "_id": 0}):
                dom = item.get("domain")
                if dom and dom.endswith(suffix):
                    domains.add(dom)

    scope_ids = get_scope_ids(domain)
    if scope_ids:
        for i in range(0, len(scope_ids), 1000):
            chunk = scope_ids[i:i + 1000]
            for item in conn_db('asset_domain').find({"scope_id": {"$in": chunk}}, {"domain": 1, "_id": 0}):
                dom = item.get("domain")
                if dom and dom.endswith(suffix):
                    domains.add(dom)

    return list(domains)


def get_asset_domain_by_id(scope_id):
    query = {"scope_id": scope_id}
    return [item["domain"] for item in conn_db('asset_domain').find(query, {"domain": 1, "_id": 0}) if item.get("domain")]


def get_monitor_domain_by_id(scope_id):
    query = {"scope_id": scope_id}
    items = conn_db('scheduler').find(query, {"domain": 1, "_id": 0})
    return [item["domain"] for item in items if "domain" in item]


def scope_data_by_id(scope_id):
    query = {"_id": ObjectId(scope_id)}
    item = conn_db('asset_scope').find_one(query)

    return item


def get_scope_ids(domain):
    query = {"scope_array": domain}
    return [str(item["_id"]) for item in conn_db('asset_scope').find(query, {"_id": 1})]


def task_statistic(task_id=None):
    """对任务中的资产信息进行统计"""
    query = dict()
    if isinstance(task_id, str) and len(task_id) == 24:
        query["task_id"] = task_id

    ret = dict()
    table_list = ['site', 'domain', 'ip', 'cert', 'service', 'fileleak']
    table_list.extend(['url', 'vuln', 'npoc_service', 'cip'])
    table_list.extend(["nuclei_result", "stat_finger", "wih"])
    for table in table_list:
        cnt = conn_db(table).count_documents(query)
        stat_key = table + "_cnt"
        ret[stat_key] = cnt

    return ret


def gen_cip_map(task_id=None):
    query = dict()
    if isinstance(task_id, str) and len(task_id) == 24:
        query["task_id"] = task_id

    results = conn_db('ip').find(query, {"ip": 1, "domain": 1, "_id": 0})
    cip_map = dict()

    for result in results:
        ip_val = result.get("ip")
        if not ip_val or ":" in str(ip_val):
            continue
        try:
            cip = IP(str(ip_val) + "/24", make_net=True).strNormal(1)
        except Exception:
            continue

        raw_domains = result.get("domain")
        if isinstance(raw_domains, list):
            curr_domains = {d for d in raw_domains if isinstance(d, str) and d}
        elif isinstance(raw_domains, str) and raw_domains:
            curr_domains = {raw_domains}
        else:
            curr_domains = set()

        count_map = cip_map.get(cip)
        if count_map is None:
            cip_map[cip] = {
                "domain_set": set(curr_domains),
                "ip_set": {ip_val}
            }
        else:
            if curr_domains:
                count_map["domain_set"] |= curr_domains
            count_map["ip_set"].add(ip_val)

    return cip_map


def gen_stat_finger_map(task_id=None):
    query = dict()
    if isinstance(task_id, str) and len(task_id) == 24:
        query["task_id"] = task_id

    results = conn_db('site').find(query, {"finger": 1, "_id": 0})
    finger_map = dict()
    for result in results:
        fingers = result.get("finger")
        if not isinstance(fingers, list):
            continue

        seen_in_site = set()
        for finger in fingers:
            if isinstance(finger, dict):
                name = finger.get("name")
            elif isinstance(finger, str):
                name = finger
            else:
                name = None
            if not name or not isinstance(name, str):
                continue

            key = name.lower()
            if key in seen_in_site:
                continue
            seen_in_site.add(key)

            if key not in finger_map:
                finger_map[key] = {
                    "name": name,
                    "cnt": 1
                }
            else:
                finger_map[key]["cnt"] += 1

    return finger_map


def build_port_custom(port_custom):
    port_list = []
    splits = port_custom.split(",")
    if len(splits) < 1:
        return ""
    for item in splits:
        item = item.strip()
        if re.match(r"^[\d\-]+$", item):
            port_list.append(item)
        else:
            return item

    return port_list


