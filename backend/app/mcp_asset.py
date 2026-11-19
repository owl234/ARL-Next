#coding: utf-8
"""
全链路资产画像聚合核心逻辑 (从 app/routes/mcp.py 下沉独立解耦)
供 REST API (/api/mcp/asset_profile) 与 原生异步 MCP SSE 服务 (app/mcp_server.py) 共同复用。
"""

import ipaddress
import re
from bson import ObjectId
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse

from app import utils
from app.utils import get_logger

logger = get_logger()


def _clean_empty(val):
    """递归剥离字典/列表中的空值，最小化上下文 Token 占用"""
    if isinstance(val, dict):
        cleaned = {k: _clean_empty(v) for k, v in val.items()}
        return {k: v for k, v in cleaned.items() if v not in (None, "", [], {})}
    if isinstance(val, list):
        cleaned = [_clean_empty(v) for v in val]
        return [v for v in cleaned if v not in (None, "", [], {})]
    if isinstance(val, str):
        s = val.strip()
        return s if s and s not in ("-", "None", "null") else None
    if isinstance(val, ObjectId):
        return None
    return val


def build_asset_profile(target: str, task_id: str = ""):
    """全链路资产画像聚合器：单次查询跨集合关联 IP、端口服务、Web指纹、证书、漏洞与泄露"""
    target = target.strip()
    if not target:
        return {"code": 400, "message": "Target parameter is required"}

    # 1. 规范化输入标的（支持 IPv4 / IPv6 / 域名 / URL）
    def _is_valid_ip(val: str) -> bool:
        if not val:
            return False
        try:
            ipaddress.ip_address(val.strip("[]"))
            return True
        except ValueError:
            return False

    is_ip = _is_valid_ip(target)
    hostname = None
    target_ip = None
    url_target = None

    if "://" in target or target.startswith(("http:", "https:")):
        parsed = urlparse(target)
        hostname = (parsed.hostname or "").strip("[]").lower()
        url_target = target
        if _is_valid_ip(hostname):
            target_ip = hostname
    elif is_ip:
        target_ip = target.strip("[]")
    else:
        if ":" in target and not target.startswith("[") and not target.endswith(":"):
            hostname = target.split(":", 1)[0].strip()
        else:
            hostname = target.strip("[]").strip()
        # 防御形如 example.com/api/v1 的无协议头 URL 路径残留
        hostname = hostname.split("/")[0].strip().rstrip(".").lower()

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

            rec_val = doc.get("record_value") or doc.get("record")
            if rec_val:
                if isinstance(rec_val, list):
                    for v in rec_val:
                        if isinstance(v, str) and _is_valid_ip(v.strip()):
                            resolved_ips.add(v.strip())
                elif isinstance(rec_val, str) and _is_valid_ip(rec_val.strip()):
                    resolved_ips.add(rec_val.strip())
    elif is_ip:
        domain_query = {"$or": [{"ips": target_ip}, {"record_value": target_ip}, {"record": target_ip}], **task_filter}
        domain_docs = list(utils.conn_db('domain').find(domain_query).sort("_id", -1).limit(10))
        if not domain_docs and not task_filter:
            domain_docs = list(utils.conn_db('asset_domain').find({"$or": [{"ips": target_ip}, {"record_value": target_ip}, {"record": target_ip}]}).sort("_id", -1).limit(10))
        for doc in domain_docs:
            d = doc.get("domain")
            if d:
                related_domains.add(d)

    if resolved_ips:
        profile["resolved_ips"] = sorted(list(resolved_ips))
    if related_domains and not hostname:
        profile["related_domains"] = sorted(list(related_domains))

    all_ips_to_query = list(resolved_ips)

    # 构造左锚定（Left-Anchored）URL 正则，利用 B-Tree 索引前缀加速，规避无锚点正则全表扫描
    dom_url_prefix = None
    if hostname:
        escaped_dom = re.escape(hostname)
        dom_url_prefix = f"^https?://(?:[^/@:]*@)?(?:[a-zA-Z0-9.-]+\\.)?{escaped_dom}(?::\\d+)?(?:/|$)"

    ips_url_prefix = None
    if all_ips_to_query:
        valid_ips = [re.escape(ip) for ip in all_ips_to_query[:15] if ip]
        if valid_ips:
            ips_url_prefix = f"^https?://(?:[^/@:]*@)?(?:{'|'.join(valid_ips)})(?::\\d+)?(?:/|$)"

    url_prefixes = [p for p in (dom_url_prefix, ips_url_prefix) if p]
    combined_url_prefix = "|".join(url_prefixes) if url_prefixes else f"^https?://(?:[^/@:]*@)?{re.escape(target)}(?::\\d+)?(?:/|$)"

    exact_targets = {target}
    if hostname:
        exact_targets.add(hostname)
    if url_target:
        exact_targets.add(url_target)
    for ip in all_ips_to_query:
        exact_targets.add(ip)
    exact_target_list = list(exact_targets)

    # 3~6. 并行查询 IP/服务、Web站点/证书、漏洞、文件泄露与 WIH
    def _fetch_network():
        ports_map = {}
        geo_parts = []
        asn_info = None
        os_info_name = None
        if not all_ips_to_query:
            return geo_parts, asn_info, os_info_name, ports_map

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
        return geo_parts, asn_info, os_info_name, ports_map

    def _fetch_web_and_cert():
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
                    "subject": c_data.get("subject_dn") or c_data.get("subject"),
                    "issuer": c_data.get("issuer_dn") or c_data.get("issuer"),
                    "sans": c_data.get("extensions", {}).get("subjectAltName") if isinstance(c_data.get("extensions"), dict) else None,
                    "end_date": c_data.get("validity", {}).get("end") if isinstance(c_data.get("validity"), dict) else None
                }
                if any(cert_item.values()):
                    cert_list.append(cert_item)
                    break
        return web_list, cert_list

    def _fetch_vulns():
        vulns_list = []
        vuln_or = [
            {"target": {"$in": exact_target_list}},
            {"target": {"$regex": combined_url_prefix, "$options": "i"}},
            {"url": {"$regex": combined_url_prefix, "$options": "i"}},
        ]
        if hostname:
            vuln_or.append({"target": {"$regex": f"^{re.escape(hostname)}(?::\\d+)?$", "$options": "i"}})

        vuln_query = {"$or": vuln_or, **task_filter}
        vuln_docs = list(utils.conn_db('vuln').find(vuln_query).sort("_id", -1).limit(100))
        if not vuln_docs and not task_filter:
            vuln_docs = list(utils.conn_db('asset_vuln').find({"$or": vuln_or}).sort("_id", -1).limit(100))
        for v in vuln_docs:
            vulns_list.append({
                "name": v.get("vul_name") or v.get("vuln_name"),
                "category": v.get("vul_category") or v.get("vuln_type"),
                "severity": v.get("severity", "high"),
                "target": v.get("target")
            })

        nuclei_or = [
            {"target": {"$in": exact_target_list}},
            {"host": {"$in": exact_target_list}},
            {"target": {"$regex": combined_url_prefix, "$options": "i"}},
            {"vuln_url": {"$regex": combined_url_prefix, "$options": "i"}},
        ]
        if hostname:
            dom_hp = f"^(?:[a-zA-Z0-9.-]+\\.)?{re.escape(hostname)}(?::\\d+)?$"
            nuclei_or.append({"target": {"$regex": dom_hp, "$options": "i"}})
            nuclei_or.append({"vuln_url": {"$regex": dom_hp, "$options": "i"}})
        if all_ips_to_query:
            valid_ips = [re.escape(ip) for ip in all_ips_to_query[:15] if ip]
            if valid_ips:
                ip_hp = f"^(?:\\[?(?:{'|'.join(valid_ips)})\\]?)(?::\\d+)?$"
                nuclei_or.append({"target": {"$regex": ip_hp}})
                nuclei_or.append({"vuln_url": {"$regex": ip_hp}})
        nuclei_query = {"$or": nuclei_or, **task_filter}
        nuclei_docs = list(utils.conn_db('nuclei_result').find(nuclei_query).sort("_id", -1).limit(100))
        if not nuclei_docs and not task_filter:
            nuclei_docs = list(utils.conn_db('asset_nuclei_result').find({"$or": nuclei_or}).sort("_id", -1).limit(100))
        for n in nuclei_docs:
            vulns_list.append({
                "name": n.get("vuln_name"),
                "severity": n.get("vuln_severity"),
                "target": n.get("vuln_url") or n.get("target"),
                "template_id": n.get("template_id"),
                "template_source": n.get("template_source") or "community",
                "plugin": "nuclei"
            })
        return vulns_list

    def _fetch_leaks():
        leaks_list = []
        leak_or = [
            {"url": {"$in": exact_target_list}},
            {"url": {"$regex": combined_url_prefix, "$options": "i"}},
        ]
        leak_query = {"$or": leak_or, **task_filter}
        leak_docs = list(utils.conn_db('fileleak').find(leak_query).sort("_id", -1).limit(50))
        if not leak_docs and not task_filter:
            leak_docs = list(utils.conn_db('asset_fileleak').find({"$or": leak_or}).sort("_id", -1).limit(50))
        for lk in leak_docs:
            leaks_list.append({
                "url": lk.get("url"),
                "title": lk.get("title"),
                "status": lk.get("status_code")
            })

        wih_or = [
            {"site": {"$in": exact_target_list}},
            {"site": {"$regex": combined_url_prefix, "$options": "i"}},
            {"url": {"$regex": combined_url_prefix, "$options": "i"}},
        ]
        wih_query = {"$or": wih_or, **task_filter}
        wih_docs = list(utils.conn_db('wih').find(wih_query).sort("_id", -1).limit(50))
        if not wih_docs and not task_filter:
            wih_docs = list(utils.conn_db('asset_wih').find({"$or": wih_or}).sort("_id", -1).limit(50))
        for w in wih_docs:
            leaks_list.append({
                "type": w.get("record_type"),
                "content": w.get("content")
            })
        return leaks_list

    tasks = {
        "network": _fetch_network,
        "web_cert": _fetch_web_and_cert,
        "vulns": _fetch_vulns,
        "leaks": _fetch_leaks,
    }
    task_results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        future_map = {executor.submit(fn): name for name, fn in tasks.items()}
        for future in as_completed(future_map):
            name = future_map[future]
            try:
                task_results[name] = future.result()
            except Exception as ex:
                logger.warning(f"MCP build_asset_profile subtask {name} error: {ex}")

    geo_parts, asn_info, os_info_name, ports_map = task_results.get("network", ([], None, None, {}))
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

    web_list, cert_list = task_results.get("web_cert", ([], []))
    if web_list:
        profile["web"] = web_list[0] if len(web_list) == 1 else web_list
    if cert_list:
        profile["cert"] = cert_list[0] if len(cert_list) == 1 else cert_list

    vulns_list = task_results.get("vulns", [])
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

    leaks_list = task_results.get("leaks", [])
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


def build_enterprise_profile(target: str, category: str = "all", page: int = 1, size: int = 20, task_id: str = "") -> dict:
    """企业生态资产画像聚合器：自适应识别企业标的、关联资产组态势，并提供总览与分维度下钻"""
    target = (target or "").strip()
    task_id = (task_id or "").strip()
    category = (category or "all").strip().lower()

    allowed_categories = {"all", "web", "app", "mapp", "wechat", "weibo", "kapp", "invest"}
    if category not in allowed_categories:
        return {"code": 400, "status": "error", "message": f"Unsupported category '{category}'. Allowed: {sorted(list(allowed_categories))}"}

    try:
        page = min(2_147_483_647, max(1, int(page or 1)))
    except (ValueError, TypeError, OverflowError):
        page = 1

    try:
        size = min(max(1, int(size or 20)), 100)
    except (ValueError, TypeError, OverflowError):
        size = 20

    if not target and not task_id:
        return {"code": 400, "status": "error", "message": "Target parameter is required"}

    # 1. 任务/标的解析与定位
    task_doc = None
    if task_id:
        if not ObjectId.is_valid(task_id):
            return {'code': 400, 'status': 'error', 'message': 'Invalid enterprise task_id'}
        task_doc = utils.conn_db('icp_task').find_one({'_id': ObjectId(task_id)})
        if not task_doc:
            return {'status': 'not_found', 'task_id': task_id, 'message': 'Enterprise task not found'}

    if not task_doc:
        # 1a. 检查 target 是否为域名/URL（如 qq.com，自动反查归属企业主体）
        hostname = None
        if "://" in target or target.startswith(("http:", "https:")):
            parsed = urlparse(target)
            hostname = (parsed.hostname or "").strip("[]").lower()
        elif "." in target and not re.search(r'[\u4e00-\u9fa5\s]', target):
            hostname = target.split("/")[0].split(":")[0].strip().lower()

        if hostname:
            base_domain = hostname[4:] if hostname.startswith("www.") else hostname
            domain_query = {
                "query_type": "web",
                "$or": [{"domain": hostname}, {"domain": base_domain}, {"ym": hostname}, {"ym": base_domain}]
            }
            domain_doc = utils.conn_db('icp_asset').find_one(domain_query, sort=[("_id", -1)])
            if domain_doc:
                ent_name = domain_doc.get("companyName") or domain_doc.get("unitName")
                if ent_name:
                    target = ent_name
                if not task_doc and domain_doc.get("task_id"):
                    try:
                        task_doc = utils.conn_db('icp_task').find_one({"_id": ObjectId(domain_doc["task_id"])})
                    except Exception:
                        pass

        # 1b. 在 icp_task 中检索（优先精确匹配）
        if not task_doc:
            exact_query = {
                "$or": [
                    {"company_name": target},
                    {"target": target},
                    {"name": target}
                ]
            }
            task_doc = utils.conn_db('icp_task').find_one(exact_query, sort=[("_id", -1)])

        # 1c. 模糊检索与多候选识别
        if not task_doc:
            reg = {"$regex": re.escape(target), "$options": "i"}
            candidate_tasks = list(utils.conn_db('icp_task').find({
                "$or": [
                    {"company_name": reg},
                    {"name": reg},
                    {"target": reg}
                ]
            }).sort("_id", -1).limit(10))

            if len(candidate_tasks) == 1:
                task_doc = candidate_tasks[0]
            elif len(candidate_tasks) > 1:
                # 按企业名称去重
                distinct_tasks = {}
                for t in candidate_tasks:
                    c_name = (t.get("company_name") or t.get("target") or t.get("name") or "").strip()
                    if c_name and c_name not in distinct_tasks:
                        distinct_tasks[c_name] = t
                if len(distinct_tasks) == 1:
                    task_doc = list(distinct_tasks.values())[0]
                else:
                    candidates = []
                    for c_name, t in distinct_tasks.items():
                        t_id = str(t["_id"])
                        cnt = utils.conn_db('icp_asset').count_documents({"task_id": t_id})
                        candidates.append({
                            "name": c_name,
                            "task_id": t_id,
                            "asset_count": cnt,
                            "task_status": t.get("status", "done")
                        })
                    return {
                        "status": "multiple_candidates",
                        "target": target,
                        "tip": "检索到多家匹配的企业，请在下一次调用中使用更精确的企业全称或传入具体的 task_id",
                        "candidates": candidates
                    }

        # 1d. 在 asset_scope 中检索企业绑定信息
        if not task_doc:
            reg = {"$regex": re.escape(target), "$options": "i"}
            scope_doc = utils.conn_db('asset_scope').find_one({
                "$or": [
                    {"enterprise_name": reg},
                    {"name": reg}
                ]
            }, sort=[("_id", -1)])
            if scope_doc and scope_doc.get("synced_icp_task_id"):
                try:
                    task_doc = utils.conn_db('icp_task').find_one({"_id": ObjectId(scope_doc["synced_icp_task_id"])})
                except Exception:
                    pass

        # 1e. 在 icp_asset 中直接检索归属记录
        if not task_doc:
            reg = {"$regex": re.escape(target), "$options": "i"}
            sample_asset = utils.conn_db('icp_asset').find_one({
                "$or": [{"companyName": reg}, {"unitName": reg}]
            }, sort=[("_id", -1)])
            if sample_asset and sample_asset.get("task_id"):
                try:
                    task_doc = utils.conn_db('icp_task').find_one({"_id": ObjectId(sample_asset["task_id"])})
                except Exception:
                    pass

    # 依然未检索到企业数据 -> 明确返回只读 not_found 与操作指引
    if not task_doc:
        return {
            "status": "not_found",
            "target": target,
            "message": f"未在 ARL 资产库中检索到与【{target}】匹配的企业测绘记录",
            "suggestion": "可前往 ARL Web 控制台【资产组 -> 新建资产组 -> 企业全景测绘建组】，或确认名称/域名无误后重试"
        }

    resolved_task_id = str(task_doc["_id"])
    company_name = task_doc.get("company_name") or task_doc.get("target") or task_doc.get("name") or target

    # 2. 查询绑定的资产组网络暴露面态势 (ASM 协同)
    bound_scope_info = None
    synced_scope_id = task_doc.get("synced_scope_id")
    scope_record = None
    if synced_scope_id and len(str(synced_scope_id)) == 24:
        try:
            scope_record = utils.conn_db('asset_scope').find_one({"_id": ObjectId(synced_scope_id)})
        except Exception:
            pass

    if not scope_record:
        scope_record = utils.conn_db('asset_scope').find_one({
            "$or": [
                {"synced_icp_task_id": resolved_task_id},
                {"enterprise_name": company_name}
            ]
        })

    if scope_record:
        s_id = str(scope_record["_id"])
        domain_arr = scope_record.get("domain_array") or scope_record.get("scope_array") or []
        managed_domains = len(domain_arr) if isinstance(domain_arr, list) else 0
        live_sites = utils.conn_db('asset_site').count_documents({"scope_id": s_id})
        vulns_cnt = utils.conn_db('asset_vuln').count_documents({"scope_id": s_id}) + utils.conn_db('asset_nuclei_result').count_documents({"scope_id": s_id})
        bound_scope_info = {
            "scope_id": s_id,
            "scope_name": scope_record.get("name", ""),
            "managed_domains": managed_domains,
            "live_sites": live_sites,
            "unresolved_risks": vulns_cnt
        }

    # 3. 总览模式 (category == "all")
    if category == "all":
        categories_list = ["web", "app", "mapp", "wechat", "weibo", "kapp", "invest"]
        counts = {}
        for cat in categories_list:
            counts[cat] = utils.conn_db('icp_asset').count_documents({"task_id": resolved_task_id, "query_type": cat})
        counts["total"] = sum(counts.values())

        # 采集高频核心样本 Top 3~5
        samples = {}
        web_docs = list(utils.conn_db('icp_asset').find({"task_id": resolved_task_id, "query_type": "web"}).limit(5))
        if web_docs:
            samples["web_top"] = [
                {
                    "domain": d.get("domain") or d.get("ym"),
                    "service_name": d.get("serviceName") or d.get("webName"),
                    "licence": d.get("serviceLicence") or d.get("liscense")
                }
                for d in web_docs
            ]

        app_docs = list(utils.conn_db('icp_asset').find({"task_id": resolved_task_id, "query_type": "app"}).limit(3))
        if app_docs:
            samples["app_top"] = [
                {
                    "name": d.get("name") or d.get("serviceName"),
                    "category": d.get("category")
                }
                for d in app_docs
            ]

        mapp_docs = list(utils.conn_db('icp_asset').find({"task_id": resolved_task_id, "query_type": "mapp"}).limit(3))
        if mapp_docs:
            samples["mapp_top"] = [
                {
                    "name": d.get("name") or d.get("serviceName"),
                    "unit_name": d.get("unitName") or d.get("companyName")
                }
                for d in mapp_docs
            ]

        wechat_docs = list(utils.conn_db('icp_asset').find({"task_id": resolved_task_id, "query_type": "wechat"}).limit(3))
        if wechat_docs:
            samples["wechat_top"] = [
                {
                    "name": d.get("name") or d.get("title"),
                    "wechat_id": d.get("wechatId") or d.get("publicNum")
                }
                for d in wechat_docs
            ]

        invest_docs = list(utils.conn_db('icp_asset').find({"task_id": resolved_task_id, "query_type": "invest"}).limit(5))
        if invest_docs:
            samples["invest_top"] = [
                {
                    "company_name": d.get("name") or d.get("companyName"),
                    "ratio": d.get("percent") or d.get("ratio"),
                    "legal_person": d.get("legalPerson") or d.get("legalPersonName")
                }
                for d in invest_docs
            ]

        ent_info = {
            "name": company_name,
            "task_id": resolved_task_id,
            "task_status": task_doc.get("status", "done"),
            "task_type": task_doc.get("task_type", "icp"),
            "gid": task_doc.get("gid", ""),
            "bound_scope": bound_scope_info
        }

        overview = {
            "status": "success",
            "enterprise_info": ent_info,
            "asset_counts": counts,
            "samples": samples,
            "drilldown_guidance": {
                "tip": f"当前为【{company_name}】全景生态资产总览画像。若需查看某维度的完整资产列表，请传入对应 category 参数下钻查询（例如 category='web' 查询全量备案域名；category='invest' 查询子公司架构）；若需对特定域名探查开放端口与漏洞风险，请调用 get_asset_profile(target='xxx.com')。"
            }
        }
        return _clean_empty(overview)

    # 4. 维度明细下钻模式 (category in ["web", "app", "mapp", "wechat", "weibo", "kapp", "invest"])
    query_cond = {"task_id": resolved_task_id, "query_type": category}
    total = utils.conn_db('icp_asset').count_documents(query_cond)
    skip = (page - 1) * size
    cursor = utils.conn_db('icp_asset').find(query_cond).skip(skip).limit(size)

    items = []
    for raw in cursor:
        item = {}
        if category == "web":
            item = {
                "domain": raw.get("domain") or raw.get("ym", ""),
                "service_name": raw.get("serviceName") or raw.get("webName") or raw.get("name", ""),
                "service_licence": raw.get("serviceLicence") or raw.get("liscense", ""),
                "unit_name": raw.get("unitName") or raw.get("companyName", ""),
                "update_time": raw.get("updateRecordTime") or raw.get("examineDate", ""),
                "home_url": raw.get("homeUrl", "")
            }
        elif category == "app":
            item = {
                "name": raw.get("name") or raw.get("serviceName", ""),
                "category": raw.get("category", ""),
                "service_licence": raw.get("serviceLicence") or raw.get("liscense", ""),
                "unit_name": raw.get("unitName") or raw.get("companyName", ""),
                "brief": raw.get("brief", "")
            }
        elif category == "mapp":
            item = {
                "name": raw.get("name") or raw.get("serviceName", ""),
                "category": raw.get("category", ""),
                "unit_name": raw.get("unitName") or raw.get("companyName", ""),
                "service_licence": raw.get("serviceLicence") or raw.get("liscense", "")
            }
        elif category == "wechat":
            item = {
                "name": raw.get("name") or raw.get("title", ""),
                "wechat_id": raw.get("wechatId") or raw.get("publicNum", ""),
                "unit_name": raw.get("unitName") or raw.get("companyName", ""),
                "brief": raw.get("brief", "")
            }
        elif category == "weibo":
            item = {
                "name": raw.get("name", ""),
                "home_url": raw.get("homeUrl", ""),
                "brief": raw.get("brief", "")
            }
        elif category == "kapp":
            item = {
                "name": raw.get("name") or raw.get("serviceName", ""),
                "unit_name": raw.get("unitName") or raw.get("companyName", ""),
                "service_licence": raw.get("serviceLicence", ""),
                "main_licence": raw.get("mainLicence", ""),
                "content_type": raw.get("contentTypeName", ""),
                "category": raw.get("category", "")
            }
        elif category == "invest":
            item = {
                "company_name": raw.get("name") or raw.get("companyName", ""),
                "ratio": raw.get("percent") or raw.get("ratio", ""),
                "legal_person": raw.get("legalPerson") or raw.get("legalPersonName", ""),
                "reg_status": raw.get("regStatus") or raw.get("status", ""),
                "reg_capital": raw.get("amount") or raw.get("regCapital", "")
            }
        cleaned_item = _clean_empty(item)
        if cleaned_item:
            items.append(cleaned_item)

    detail_result = {
        "status": "success",
        "enterprise_name": company_name,
        "task_id": resolved_task_id,
        "category": category,
        "pagination": {
            "page": page,
            "size": size,
            "total": total,
            "has_more": skip + len(items) < total
        },
        "items": items,
        "tip": f"已返回第 {page} 页数据（共 {total} 条）。若需探测特定资产技术暴露面，可调用 get_asset_profile(target='...')"
    }
    return _clean_empty(detail_result)


TOOL_GET_ASSET_PROFILE = {
    "name": "get_asset_profile",
    "description": "获取指定目标（站点URL/IP/子域名）的综合资产画像，包括解析IP、开放端口与服务、Web指纹与标题、SSL证书、已知漏洞及敏感泄露等关联情报。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "资产标的，支持域名 (如 example.com)、IP (如 192.0.2.1) 或站点 URL (如 https://example.com:8443)"
            },
            "task_id": {
                "type": "string",
                "description": "可选。24位任务 ID。若指定则锁定该任务上下文，未指定则智能匹配最新任务或全局资产"
            }
        },
        "required": ["target"]
    }
}

TOOL_GET_ENTERPRISE_PROFILE = {
    "name": "get_enterprise_profile",
    "description": "获取指定企业标的（企业全称、简称、备案域名如 qq.com 或备案号）的全景生态资产画像与组织架构（包括工商背景、ICP备案网站、移动APP、微信小程序、公众号、企业微博、快应用及投资控股关系）。支持按资产分类下钻分页查询。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "企业标的，支持企业工商全称（如'深圳市腾讯计算机系统有限公司'）、企业商业简称（如'腾讯'）、根域名（如'qq.com'，自动反查所属企业）或 ICP 备案主体/备案号"
            },
            "category": {
                "type": "string",
                "enum": ["all", "web", "app", "mapp", "wechat", "weibo", "kapp", "invest"],
                "default": "all",
                "description": "查询维度：'all'（默认总览画像与各维度统计指标）；'web'（网站备案域名）；'app'（移动应用）；'mapp'（微信小程序）；'wechat'（微信公众号）；'weibo'（企业微博）；'kapp'（快应用）；'invest'（对外投资与控股子公司）"
            },
            "page": {
                "type": "integer",
                "default": 1,
                "description": "下钻指定 category 时的页码（从 1 开始）"
            },
            "size": {
                "type": "integer",
                "default": 20,
                "description": "下钻指定 category 时每页记录条数（默认 20，最大 100）"
            },
            "task_id": {
                "type": "string",
                "description": "可选。24位企业测绘任务 ID。若指定则直接锁定该任务历史数据"
            }
        },
        "required": ["target"]
    }
}

TOOL_SEARCH_ASSETS = {
    "name": "search_assets",
    "description": "按条件检索 ARL 资产库中的站点、IP、域名或漏洞记录。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "检索关键字（如域名关键词、服务名称、Web指纹或端口号）"
            },
            "asset_type": {
                "type": "string",
                "enum": ["site", "domain", "ip", "vuln"],
                "description": "资产类别，默认为 site（可选 site, domain, ip, vuln）"
            },
            "limit": {
                "type": "integer",
                "description": "返回条目上限（1-50，默认 10）"
            }
        },
        "required": ["query"]
    }
}

TOOL_GET_TASK_STATUS = {
    "name": "get_task_status",
    "description": "查询指定 24 位任务 ID 的扫描进度、运行状态与资产统计摘要。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "24 位 ARL 扫描任务 ID"
            }
        },
        "required": ["task_id"]
    }
}

TOOL_CREATE_SCAN_TASK = {
    "name": "create_scan_task",
    "description": "【受控调度】向 ARL 调度队列提交新的资产扫描任务（需启用工具开关并具备 task:dispatch 权限）。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "扫描任务名称"
            },
            "target": {
                "type": "string",
                "description": "扫描目标（多个目标以换行或逗号分隔）"
            },
            "policy_id": {
                "type": "string",
                "description": "可选。24位扫描策略模板 ID；未传则使用系统默认策略"
            }
        },
        "required": ["name", "target"]
    }
}

TOOL_STOP_SCAN_TASK = {
    "name": "stop_scan_task",
    "description": "【受控调度】紧急终止正在排队或进行中的 ARL 扫描任务。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "task_id": {
                "type": "string",
                "description": "24 位 ARL 扫描任务 ID"
            }
        },
        "required": ["task_id"]
    }
}

MCP_TOOL_DEFINITIONS = (
    TOOL_GET_ASSET_PROFILE,
    TOOL_GET_ENTERPRISE_PROFILE,
    TOOL_SEARCH_ASSETS,
    TOOL_GET_TASK_STATUS,
    TOOL_CREATE_SCAN_TASK,
    TOOL_STOP_SCAN_TASK,
)


def search_mcp_assets(query: str, asset_type: str = "site", limit: int = 10, max_search_limit: int = 50):
    """按关键词跨资产集合受限检索，供 SSE 与 REST 通道共用"""
    raw_query = str(query or "").strip()
    if not raw_query:
        return {"status": "error", "message": "Missing required parameter: query"}, True
    escaped = re.escape(raw_query)
    coll_name = str(asset_type or "site").strip().lower()
    if coll_name not in ("site", "domain", "ip", "vuln"):
        coll_name = "site"
    try:
        requested_limit = int(limit if limit is not None else 10)
    except (TypeError, ValueError):
        return {"status": "error", "message": "Invalid integer parameter: limit"}, True
    bounded_limit = min(max(requested_limit, 1), max(1, int(max_search_limit)))

    if coll_name == "site":
        filter_cond = {"$or": [{"site": {"$regex": escaped, "$options": "i"}}, {"title": {"$regex": escaped, "$options": "i"}}]}
        proj = {"favicon.data": 0, "body": 0, "header": 0}
    elif coll_name == "domain":
        filter_cond = {"domain": {"$regex": escaped, "$options": "i"}}
        proj = None
    elif coll_name == "ip":
        filter_cond = {"ip": {"$regex": escaped, "$options": "i"}}
        proj = None
    else:
        filter_cond = {"$or": [{"target": {"$regex": escaped, "$options": "i"}}, {"vul_name": {"$regex": escaped, "$options": "i"}}]}
        proj = None

    cursor = utils.conn_db(coll_name).find(filter_cond, proj).sort("_id", -1).limit(bounded_limit)
    items = list(cursor)
    for it in items:
        if "_id" in it:
            it["_id"] = str(it["_id"])
    return _clean_empty({"items": items, "total": len(items), "type": coll_name}), False


def get_mcp_task_status(task_id: str):
    """查询指定 24 位扫描任务的状态与统计进度"""
    tid = str(task_id or "").strip()
    if not tid or len(tid) != 24 or not ObjectId.is_valid(tid):
        return {"status": "error", "message": "Invalid 24-character task_id"}, True
    t_doc = utils.conn_db('task').find_one({"_id": ObjectId(tid)})
    if not t_doc:
        return {"status": "not_found", "message": f"Task {tid} not found"}, False
    return _clean_empty({
        "task_id": str(t_doc.get("_id")),
        "name": t_doc.get("name"),
        "status": t_doc.get("status"),
        "target": t_doc.get("target"),
        "start_time": str(t_doc.get("start_time", "")),
        "end_time": str(t_doc.get("end_time", "")),
        "progress": t_doc.get("statistic", {})
    }), False


def create_mcp_scan_task(name: str, target: str, policy_id: str = ""):
    """通过标准策略与队列校验提交扫描任务"""
    task_name = str(name or "").strip()
    target_str = str(target or "").strip()
    pol_id = str(policy_id or "").strip()
    if not task_name or not target_str:
        return {"status": "error", "message": "Both name and target are required"}, True

    from app.helpers.policy import get_options_by_policy_id
    from app.helpers.task import submit_task_task
    from app.modules import TaskTag

    if not pol_id:
        p_doc = utils.conn_db('policy').find_one({"is_default": True}) or utils.conn_db('policy').find_one({})
        if p_doc:
            pol_id = str(p_doc["_id"])
    if not pol_id:
        return {"status": "error", "message": "No scan policy available to submit task"}, True

    options = get_options_by_policy_id(pol_id, TaskTag.TASK)
    if not options:
        return {"status": "error", "message": "Scan policy not found"}, True
    tasks = submit_task_task(target=target_str, name=task_name, options=options)
    if not tasks:
        return {"status": "error", "message": "No valid scan targets"}, True
    task_ids = [str(task['task_id']) for task in tasks]
    return {
        "status": "success",
        "task_id": task_ids[0],
        "task_ids": task_ids,
        "message": "Tasks submitted to queue"
    }, False


def stop_mcp_scan_task(task_id: str):
    """请求停止排队或运行中的扫描任务"""
    tid = str(task_id or "").strip()
    if not tid or len(tid) != 24 or not ObjectId.is_valid(tid):
        return {"status": "error", "message": "Invalid 24-character task_id"}, True
    from app.routes.task import stop_task
    response = stop_task(tid)
    ok = response.get('code') == 200
    return {
        "status": "success" if ok else "error",
        "task_id": tid,
        "message": response.get('message', '')
    }, not ok
