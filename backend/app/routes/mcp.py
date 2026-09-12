#coding: utf-8

from flask import make_response, request
from flask_restx import Resource, Namespace
from bson import ObjectId
import csv
import io

from app.utils import get_logger, auth
from app import utils

ns = Namespace('mcp', description="MCP API 接口")
logger = get_logger()

@ns.route('/task_detail_export')
class MCPTaskDetailExport(Resource):
    @auth
    def get(self):
        """
        MCP专用任务数据导出接口，返回CSV格式
        """
        task_id = request.args.get('task_id', '')
        tab = request.args.get('tab', 'site')
        try:
            page = int(request.args.get('page', 1))
            limit = int(request.args.get('limit', 100))
        except ValueError:
            page = 1
            limit = 100
            
        columns_str = request.args.get('columns', '')
        columns = [c.strip() for c in columns_str.split(',') if c.strip()] if columns_str else []

        if not task_id or len(task_id) != 24:
            return {"code": 400, "message": "Invalid task_id"}, 400

        allowed_tabs = ["site", "domain", "ip", "wih", "fileleak", "vuln", "nuclei_result", "cert", "service", "url", "npoc_service", "stat_finger", "cip"]
        if tab not in allowed_tabs:
            return {"code": 400, "message": f"Unsupported tab. Allowed: {allowed_tabs}"}, 400
            
        query = {"task_id": task_id}
        skip = (page - 1) * limit
        
        projection = None
        if tab == "site":
            projection = {"favicon.data": 0, "body": 0, "header": 0, "headers": 0} # 剔除庞大且无用的字段
            
        cursor = utils.conn_db(tab).find(query, projection).skip(skip).limit(limit)
        items = list(cursor)
        
        if not items:
            response = make_response("")
            response.headers['Content-Type'] = 'text/csv'
            return response
            
        flattened_items = []
        for item in items:
            flat_item = {}
            for k, v in item.items():
                if k == '_id':
                    flat_item[k] = str(v)
                elif tab == 'ip' and k == 'port_info' and isinstance(v, list):
                    flat_item['开放端口'] = " ".join([str(p.get('port_id', '')) for p in v if 'port_id' in p])
                elif tab == 'ip' and k == 'geo_city' and isinstance(v, dict):
                    parts = [p for p in [v.get('country_name'), v.get('region_name'), v.get('city')] if p and p not in ('None', 'null', '0')]
                    clean_p = []
                    for item_p in parts:
                        if not clean_p or clean_p[-1] != item_p:
                            clean_p.append(item_p)
                    flat_item['geo'] = "/".join(clean_p)
                elif tab == 'ip' and k == 'geo_asn' and isinstance(v, dict):
                    flat_item['as'] = v.get('organization', '')
                elif tab == 'ip' and k == 'os_info' and isinstance(v, dict):
                    flat_item['操作系统'] = v.get('name', '')
                elif tab == 'site' and k == 'finger' and isinstance(v, list):
                    flat_item['finger'] = " ".join([f.get('name', '') for f in v if 'name' in f])
                elif tab == 'cert' and isinstance(v, dict):
                    flat_item[k] = "; ".join([f"{sub_k}:{sub_v}" for sub_k, sub_v in v.items() if sub_v])
                elif isinstance(v, list):
                    flat_item[k] = " ".join([str(i) for i in v])
                elif isinstance(v, dict):
                    # Flatten simple dicts
                    flat_item[k] = "; ".join([f"{sub_k}:{sub_v}" for sub_k, sub_v in v.items() if sub_v and not isinstance(sub_v, (dict, list))])
                else:
                    flat_item[k] = str(v)
            flattened_items.append(flat_item)
            
        if columns:
            headers = columns
        else:
            headers_set = set()
            for flat_item in flattened_items:
                headers_set.update(flat_item.keys())
            headers = sorted(list(headers_set))
            
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(flattened_items)
        
        response = make_response(output.getvalue())
        response.headers['Content-Type'] = 'text/csv; charset=utf-8'
        return response


def _clean_empty(val, depth=0, max_depth=10):
    """递归清理空值 (None, '', [], {})，单遍生成器推导并带递归深度防爆保护"""
    if depth > max_depth:
        return val
    if isinstance(val, dict):
        return {k: v for k, v in ((k, _clean_empty(sub_v, depth + 1, max_depth)) for k, sub_v in val.items()) if v not in (None, "", [], {})}
    elif isinstance(val, list):
        return [v for v in (_clean_empty(item, depth + 1, max_depth) for item in val) if v not in (None, "", [], {})]
    elif val is None or val == "":
        return None
    return val


def build_asset_profile(target: str, task_id: str = ""):
    """全链路资产画像聚合器：单次查询跨集合关联 IP、端口服务、Web指纹、证书、漏洞与泄露"""
    import re
    from urllib.parse import urlparse

    target = target.strip()
    if not target:
        return {"code": 400, "message": "Target parameter is required"}

    # 1. 规范化输入标的
    is_ip = bool(re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', target))
    hostname = None
    target_ip = None
    url_target = None

    if "://" in target or target.startswith(("http:", "https:")):
        parsed = urlparse(target)
        hostname = parsed.hostname or ""
        url_target = target
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', hostname):
            target_ip = hostname
    elif is_ip:
        target_ip = target
    else:
        if ":" in target and not target.endswith(":"):
            hostname = target.split(":", 1)[0].strip()
        else:
            hostname = target.strip()
        # 防御形如 example.com/api/v1 的无协议头 URL 路径残留
        hostname = hostname.split("/")[0].strip()

    task_filter = {}
    if task_id and len(task_id) == 24:
        task_filter["task_id"] = task_id

    profile = {"target": target}
    resolved_ips = set()
    if target_ip:
        resolved_ips.add(target_ip)

    related_domains = set()
    if hostname:
        related_domains.add(hostname)

    # 2. DNS / Domain 解析层
    if hostname:
        domain_query = {"domain": hostname, **task_filter}
        domain_docs = list(utils.conn_db('domain').find(domain_query).sort("_id", -1).limit(5))
        if not domain_docs and not task_filter:
            domain_docs = list(utils.conn_db('asset_domain').find({"domain": hostname}).sort("_id", -1).limit(5))

        for doc in domain_docs:
            ips = doc.get("ips") or []
            if isinstance(ips, list):
                for ip in ips:
                    if isinstance(ip, str) and ip.strip():
                        resolved_ips.add(ip.strip())
            elif isinstance(ips, str) and ips.strip():
                resolved_ips.add(ips.strip())

            rec_val = doc.get("record_value")
            if rec_val:
                if isinstance(rec_val, list):
                    for v in rec_val:
                        if isinstance(v, str) and re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', v.strip()):
                            resolved_ips.add(v.strip())
                elif isinstance(rec_val, str) and re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', rec_val.strip()):
                    resolved_ips.add(rec_val.strip())
    elif is_ip:
        domain_query = {"$or": [{"ips": target_ip}, {"record_value": target_ip}], **task_filter}
        domain_docs = list(utils.conn_db('domain').find(domain_query).sort("_id", -1).limit(10))
        if not domain_docs and not task_filter:
            domain_docs = list(utils.conn_db('asset_domain').find({"$or": [{"ips": target_ip}, {"record_value": target_ip}]}).sort("_id", -1).limit(10))
        for doc in domain_docs:
            d = doc.get("domain")
            if d:
                related_domains.add(d)

    if resolved_ips:
        profile["resolved_ips"] = sorted(list(resolved_ips))
    if related_domains and not hostname:
        profile["related_domains"] = sorted(list(related_domains))

    # 3. IP / 网络层 (地理位置、ASN、操作系统、开放端口)
    ports_map = {}
    geo_parts = []
    asn_info = None
    os_info_name = None

    all_ips_to_query = list(resolved_ips)
    if all_ips_to_query:
        ip_query = {"ip": {"$in": all_ips_to_query}, **task_filter}
        ip_docs = list(utils.conn_db('ip').find(ip_query).sort("_id", -1).limit(20))
        if not ip_docs and not task_filter:
            ip_docs = list(utils.conn_db('asset_ip').find({"ip": {"$in": all_ips_to_query}}).sort("_id", -1).limit(20))

        for doc in ip_docs:
            if not geo_parts:
                geo = doc.get("geo_city", {})
                if isinstance(geo, dict):
                    parts = [p for p in [geo.get("country_name"), geo.get("region_name"), geo.get("city")] if p and str(p) not in ('None', 'null', '0')]
                    clean_geo = []
                    for g in parts:
                        if not clean_geo or clean_geo[-1] != g:
                            clean_geo.append(g)
                    if clean_geo:
                        geo_parts = clean_geo
            if not asn_info:
                asn = doc.get("geo_asn", {})
                if isinstance(asn, dict) and asn.get("organization"):
                    asn_info = asn.get("organization")
            if not os_info_name:
                os_doc = doc.get("os_info", {})
                if isinstance(os_doc, dict) and os_doc.get("name"):
                    os_info_name = os_doc.get("name")
            port_list = doc.get("port_info", [])
            if isinstance(port_list, list):
                for p in port_list:
                    if isinstance(p, dict) and "port_id" in p:
                        pid = p.get("port_id")
                        ports_map[pid] = {
                            "port": pid,
                            "service": p.get("service_name"),
                            "product": p.get("product"),
                            "version": p.get("version")
                        }

        # 查询 service 集合做补充
        service_query = {"$or": [{"service_info.ip": {"$in": all_ips_to_query}}, {"ip": {"$in": all_ips_to_query}}], **task_filter}
        srv_docs = list(utils.conn_db('service').find(service_query).sort("_id", -1).limit(50))
        for s in srv_docs:
            srv_info = s.get("service_info", {}) if isinstance(s.get("service_info"), dict) else {}
            pid = srv_info.get("port_id") or s.get("port")
            if pid:
                p_item = ports_map.get(pid, {"port": pid})
                p_item["service"] = s.get("service_name") or srv_info.get("service_name") or p_item.get("service")
                p_item["product"] = srv_info.get("product") or s.get("product") or p_item.get("product")
                p_item["version"] = srv_info.get("version") or s.get("version") or p_item.get("version")
                ports_map[pid] = p_item

    if geo_parts:
        profile["geo"] = "/".join(geo_parts)
    if asn_info:
        profile["asn"] = asn_info
    if os_info_name:
        profile["os"] = os_info_name
    if ports_map:
        sorted_ports = sorted(ports_map.values(), key=lambda x: x.get("port", 0))
        if len(sorted_ports) > 100:
            profile["ports"] = sorted_ports[:100]
            profile["_meta_ports_total"] = len(sorted_ports)
            profile["_meta_ports_truncated"] = True
        else:
            profile["ports"] = sorted_ports

    # 4. Web 站点层 (状态码、标题、Web 指纹)
    site_conditions = []
    if hostname:
        site_conditions.append({"hostname": hostname})
        site_conditions.append({"site": {"$regex": f"^https?://{re.escape(hostname)}(:[0-9]+)?(/.*)?$"}})
    if target_ip:
        site_conditions.append({"ip": target_ip})
    elif resolved_ips:
        site_conditions.append({"ip": {"$in": list(resolved_ips)}})
    if url_target:
        site_conditions.append({"site": url_target})

    web_list = []
    cert_list = []
    seen_sites = set()

    if site_conditions:
        site_query = {"$or": site_conditions, **task_filter}
        site_docs = list(utils.conn_db('site').find(site_query, {"favicon.data": 0, "body": 0, "header": 0}).sort("_id", -1).limit(20))
        if not site_docs and not task_filter:
            site_docs = list(utils.conn_db('asset_site').find({"$or": site_conditions}, {"favicon.data": 0, "body": 0, "header": 0}).sort("_id", -1).limit(20))

        for s in site_docs:
            s_url = s.get("site")
            if not s_url or s_url in seen_sites:
                continue
            seen_sites.add(s_url)

            fingers = []
            f_data = s.get("finger", [])
            if isinstance(f_data, list):
                for f in f_data:
                    if isinstance(f, dict) and f.get("name"):
                        fingers.append(f.get("name"))
                    elif isinstance(f, str) and f.strip():
                        fingers.append(f.strip())

            web_list.append({
                "url": s_url,
                "status": s.get("status"),
                "title": s.get("title"),
                "fingerprints": fingers
            })

            ssl_info = s.get("ssl_cert", {})
            if isinstance(ssl_info, dict) and ssl_info:
                cert_item = {
                    "subject": ssl_info.get("subject_dn") or ssl_info.get("subject"),
                    "issuer": ssl_info.get("issuer_dn") or ssl_info.get("issuer"),
                    "sans": ssl_info.get("extensions", {}).get("subjectAltName") if isinstance(ssl_info.get("extensions"), dict) else None,
                    "end_date": ssl_info.get("validity", {}).get("end") if isinstance(ssl_info.get("validity"), dict) else None
                }
                if any(cert_item.values()):
                    cert_list.append(cert_item)

    if not cert_list and (hostname or all_ips_to_query):
        cert_query = {"$or": [{"ip": {"$in": all_ips_to_query}}], **task_filter}
        cert_docs = list(utils.conn_db('cert').find(cert_query).sort("_id", -1).limit(5))
        for c in cert_docs:
            c_data = c.get("cert", {}) if isinstance(c.get("cert"), dict) else {}
            cert_item = {
                "subject": c_data.get("subject_dn") or c.get("subject"),
                "issuer": c_data.get("issuer_dn") or c.get("issuer"),
                "sans": c_data.get("extensions", {}).get("subjectAltName") if isinstance(c_data.get("extensions"), dict) else None,
                "end_date": c_data.get("validity", {}).get("end") if isinstance(c_data.get("validity"), dict) else None
            }
            if any(cert_item.values()):
                cert_list.append(cert_item)
                break

    if web_list:
        profile["web"] = web_list[0] if len(web_list) == 1 else web_list
    if cert_list:
        profile["cert"] = cert_list[0] if len(cert_list) == 1 else cert_list

    # 5. 漏洞与安全风险层 (全量紧凑平铺)
    search_keywords = [re.escape(target)]
    if hostname and hostname != target:
        search_keywords.append(re.escape(hostname))
    for ip in resolved_ips:
        search_keywords.append(re.escape(ip))

    pattern = "|".join(search_keywords)
    vulns_list = []

    vuln_query = {"$or": [{"target": {"$regex": pattern}}, {"url": {"$regex": pattern}}], **task_filter}
    vuln_docs = list(utils.conn_db('vuln').find(vuln_query).sort("_id", -1).limit(100))
    if not vuln_docs and not task_filter:
        vuln_docs = list(utils.conn_db('asset_vuln').find({"$or": [{"target": {"$regex": pattern}}, {"url": {"$regex": pattern}}]}).sort("_id", -1).limit(100))
    for v in vuln_docs:
        vulns_list.append({
            "name": v.get("vul_name") or v.get("vuln_name"),
            "category": v.get("vul_category") or v.get("vuln_type"),
            "severity": v.get("severity", "high"),
            "target": v.get("target")
        })

    nuclei_query = {"$or": [{"target": {"$regex": pattern}}, {"vuln_url": {"$regex": pattern}}], **task_filter}
    nuclei_docs = list(utils.conn_db('nuclei_result').find(nuclei_query).sort("_id", -1).limit(100))
    if not nuclei_docs and not task_filter:
        nuclei_docs = list(utils.conn_db('asset_nuclei_result').find({"$or": [{"target": {"$regex": pattern}}, {"vuln_url": {"$regex": pattern}}]}).sort("_id", -1).limit(100))
    for n in nuclei_docs:
        vulns_list.append({
            "name": n.get("vuln_name"),
            "severity": n.get("vuln_severity"),
            "target": n.get("vuln_url") or n.get("target"),
            "plugin": "nuclei"
        })

    if vulns_list:
        seen_vuln = set()
        dedup_vulns = []
        for v in vulns_list:
            key = (v.get("name"), v.get("target"))
            if key not in seen_vuln:
                seen_vuln.add(key)
                dedup_vulns.append(v)
        if len(dedup_vulns) > 100:
            profile["vulns"] = dedup_vulns[:100]
            profile["_meta_vulns_total"] = len(dedup_vulns)
            profile["_meta_vulns_truncated"] = True
        else:
            profile["vulns"] = dedup_vulns

    # 6. 文件泄露与敏感信息 (fileleak & wih)
    leaks_list = []
    leak_query = {"url": {"$regex": pattern}, **task_filter}
    leak_docs = list(utils.conn_db('fileleak').find(leak_query).sort("_id", -1).limit(50))
    if not leak_docs and not task_filter:
        leak_docs = list(utils.conn_db('asset_fileleak').find({"url": {"$regex": pattern}}).sort("_id", -1).limit(50))
    for lk in leak_docs:
        leaks_list.append({
            "url": lk.get("url"),
            "title": lk.get("title"),
            "status": lk.get("status_code")
        })

    wih_query = {"$or": [{"site": {"$regex": pattern}}, {"url": {"$regex": pattern}}], **task_filter}
    wih_docs = list(utils.conn_db('wih').find(wih_query).sort("_id", -1).limit(50))
    if not wih_docs and not task_filter:
        wih_docs = list(utils.conn_db('asset_wih').find({"$or": [{"site": {"$regex": pattern}}, {"url": {"$regex": pattern}}]}).sort("_id", -1).limit(50))
    for w in wih_docs:
        leaks_list.append({
            "type": w.get("record_type"),
            "content": w.get("content")
        })

    if leaks_list:
        profile["leaks"] = leaks_list

    # 7. 递归剔除 null 与空结构
    clean_profile = _clean_empty(profile)

    if not clean_profile or list(clean_profile.keys()) == ["target"]:
        return {
            "status": "not_found",
            "target": target,
            "tip": "未在 ARL 检索到该资产记录"
        }

    return clean_profile


@ns.route('/asset_profile')
class MCPAssetProfile(Resource):
    @auth
    def get(self):
        """
        MCP 资产全链路画像接口（站点/IP/子域名维度精准聚合，极致低 Token 剪枝输出）
        """
        target = request.args.get('target', '').strip()
        task_id = request.args.get('task_id', '').strip()
        if not target:
            return {"code": 400, "message": "Missing target parameter"}, 400

        data = build_asset_profile(target, task_id)
        return data
