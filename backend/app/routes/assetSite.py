from bson import ObjectId
from flask_restx import fields, Namespace, reqparse
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg, TaskTag
from app import utils, services
from app.helpers import (
    find_asset_site_not_in_scope,
    submit_add_asset_site_task,
    target2list,
    get_options_by_policy_id
)

ns = Namespace('asset_site', description="资产组站点信息")

logger = get_logger()

base_search_fields = {
    'site': fields.String(required=False, description="站点URL"),
    'hostname': fields.String(description="主机名"),
    'ip': fields.String(description="ip"),
    'title': fields.String(description="标题"),
    'http_server': fields.String(description="Web servers"),
    'headers': fields.String(description="headers"),
    'finger': fields.String(description="指纹"),
    'finger__eq': fields.String(description="指纹精确匹配"),
    'status': fields.Integer(description="状态码"),
    'favicon.hash': fields.Integer(description="favicon hash"),
    'task_id': fields.String(description="任务 ID"),
    'scope_id': fields.String(description="范围 ID"),
    "update_date__dgt": fields.String(description="更新时间大于"),
    "update_date__dlt": fields.String(description="更新时间小于"),
    'tag': fields.String(description="标签列表")
}

site_search_fields = base_search_fields.copy()

base_search_fields.update(base_query_fields)

add_site_fields = ns.model('addAssetSite',  {
    'site': fields.String(required=True, description="站点"),
    'scope_id': fields.String(required=True, description="资产组范围ID"),
    'policy_id': fields.String(description="策略 ID"),
})


@ns.route('/')
class ARLAssetSite(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产站点信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='asset_site')

        return data

    @auth
    @ns.expect(add_site_fields)
    def post(self):
        """
        添加站点到资产组中
        """
        args = self.parse_args(add_site_fields)
        site = args.pop("site")  # 这里可能提交大量的
        scope_id = args.pop("scope_id")
        policy_id = args.pop("policy_id")

        scope_data = utils.conn_db('asset_scope').find_one({"_id": ObjectId(scope_id)})
        if not scope_data:
            return utils.build_ret(ErrorMsg.NotFoundScopeID, {"scope_id": scope_id})



        sites = target2list(site)
        if not sites:
            return utils.build_ret(ErrorMsg.URLInvalid, {"site": site})

        not_in_scope_sites = find_asset_site_not_in_scope(sites, scope_id)
        if not_in_scope_sites:
            return utils.build_ret(ErrorMsg.TaskTargetNotInScope, {"not_in_scope_sites": site})

        name = "添加站点-{}".format(scope_data["name"])

        options = {
            'site_identify': False,
            'site_capture': False,
            'file_leak': False,
            'site_spider': False,
            'search_engines': False,
            'related_scope_id': scope_id
        }

        try:
            if policy_id and len(policy_id) == 24:
                policy_options = get_options_by_policy_id(policy_id=policy_id, task_tag=TaskTag.RISK_CRUISING)
                if policy_options:
                    policy_options["related_scope_id"] = scope_id
                    options.update(policy_options)

            task_data = submit_add_asset_site_task(task_name=name, target=sites, options=options)
        except Exception as e:
            logger.exception(e)
            return utils.build_ret(ErrorMsg.Error, {"error": str(e)})

        return utils.build_ret(ErrorMsg.Success, task_data)


@ns.route('/export/')
class ARLSiteExport(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产分组站点导出
        """
        args = self.parser.parse_args()
        response = self.send_export_file(args=args, _type="asset_site")

        return response


def add_site_to_scope(site, scope_id):
    fetch_site_data = services.fetch_site([site])
    web_analyze_data = services.web_analyze([site])
    finger = web_analyze_data.get(site, [])
    curr_date = utils.curr_date_obj()
    if fetch_site_data:
        item = fetch_site_data[0]
        item["finger"] = finger
        item["screenshot"] = ""
        item["scope_id"] = scope_id
        item["save_date"] = curr_date
        item["update_date"] = curr_date
        raw_tags = item.get("tag") or []
        if isinstance(raw_tags, str):
            raw_tags = [raw_tags]
        elif not isinstance(raw_tags, list):
            raw_tags = []
        tags = list(dict.fromkeys(raw_tags))
        if "待测试" not in tags:
            tags.append("待测试")
        item["tag"] = tags

        utils.conn_db('asset_site').insert_one(item)


delete_asset_site_fields = ns.model('deleteAssetSite',  {
    '_id': fields.List(fields.String(required=True, description="站点 _id"))
})


@ns.route('/delete/')
class DeleteARLAssetSite(ARLResource):
    @auth
    @ns.expect(delete_asset_site_fields)
    def post(self):
        """
        删除资产组中的站点
        """
        args = self.parse_args(delete_asset_site_fields)
        id_list = args.pop('_id', "")
        for _id in id_list:
            query = {'_id': ObjectId(_id)}
            utils.conn_db('asset_site').delete_one(query)

        return utils.build_ret(ErrorMsg.Success, {'_id': id_list})


@ns.route('/save_result_set/')
class ARLSaveResultSet(ARLResource):
    parser = get_arl_parser(site_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        保存资产站点到结果集
        """
        args = self.parser.parse_args()
        query = self.build_db_query(args)
        items = utils.conn_db('asset_site').distinct("site", query)

        items = list(set([utils.url.cut_filename(x) for x in items]))

        if len(items) == 0:
            return utils.build_ret(ErrorMsg.QueryResultIsEmpty, {})

        data = {
            "items": items,
            "type": "asset_site",
            "total": len(items)
        }
        result = utils.conn_db('result_set').insert_one(data)

        ret_data = {
            "result_set_id": str(result.inserted_id),
            "result_total": len(items),
            "type": "asset_site"
        }

        return utils.build_ret(ErrorMsg.Success, ret_data)


add_asset_site_tag_fields = ns.model('AddAssetSiteTagFields',  {
    "tag": fields.String(required=True, description="添加站点标签"),
    "_id": fields.String(description="资产站点ID", required=True)
})


@ns.route('/add_tag/')
class AddAssetSiteTagARL(ARLResource):

    @auth
    @ns.expect(add_asset_site_tag_fields)
    def post(self):
        """
        资产站点添加Tag
        """
        args = self.parse_args(add_asset_site_tag_fields)
        site_id = args.pop("_id")
        tag = args.pop("tag")

        query = {"_id": ObjectId(site_id)}
        data = utils.conn_db('asset_site').find_one(query)
        if not data:
            return utils.build_ret(ErrorMsg.SiteIdNotFound, {"site_id": site_id})

        tag_list = []
        old_tag = data.get("tag")
        if old_tag:
            if isinstance(old_tag, str):
                tag_list.append(old_tag)

            if isinstance(old_tag, list):
                tag_list.extend(old_tag)

        if tag in tag_list:
            return utils.build_ret(ErrorMsg.SiteTagIsExist, {"tag": tag})

        tag_list.append(tag)

        utils.conn_db('asset_site').update_one(query, {"$set": {"tag": tag_list}})

        return utils.build_ret(ErrorMsg.Success, {"tag": tag})


delete_asset_site_tag_fields = ns.model('delete_asset_site_tag_fields',  {
    "tag": fields.String(required=True, description="删除资产站点标签"),
    "_id": fields.String(description="资产站点ID", required=True)
})


@ns.route('/delete_tag/')
class DeleteAssetSiteTagARL(ARLResource):

    @auth
    @ns.expect(delete_asset_site_tag_fields)
    def post(self):
        """
        删除资产站点Tag
        """
        args = self.parse_args(delete_asset_site_tag_fields)
        site_id = args.pop("_id")
        tag = args.pop("tag")

        query = {"_id": ObjectId(site_id)}
        data = utils.conn_db('asset_site').find_one(query)
        if not data:
            return utils.build_ret(ErrorMsg.SiteIdNotFound, {"site_id": site_id})

        tag_list = []
        old_tag = data.get("tag")
        if old_tag:
            if isinstance(old_tag, str):
                tag_list.append(old_tag)

            if isinstance(old_tag, list):
                tag_list.extend(old_tag)

        if tag not in tag_list:
            return utils.build_ret(ErrorMsg.SiteTagNotExist, {"tag": tag})

        tag_list.remove(tag)

        utils.conn_db('asset_site').update_one(query, {"$set": {"tag": tag_list}})

        return utils.build_ret(ErrorMsg.Success, {"tag": tag})


subdomain_chain_parser = reqparse.RequestParser(bundle_errors=True)
subdomain_chain_parser.add_argument('scope_id', type=str, required=True, help='scope_id 不能为空', location='args')
subdomain_chain_parser.add_argument('domain', type=str, required=True, help='domain 不能为空', location='args')


@ns.route('/subdomain_chain/')
class ARLAssetSubdomainChain(ARLResource):

    @auth
    @ns.expect(subdomain_chain_parser)
    def get(self):
        """
        根据子域名全链路聚合查询资产画像
        自上而下包含：站点基础信息、子域名解析、关联IP、SSL证书、开放服务、文件泄露、敏感URL、风险漏洞、Nuclei
        """
        import re
        import ipaddress
        from urllib.parse import urlparse
        from concurrent.futures import ThreadPoolExecutor, as_completed

        args = subdomain_chain_parser.parse_args()
        scope_id = (args.get('scope_id') or '').strip()
        raw_domain = (args.get('domain') or '').strip()

        if not scope_id:
            return utils.build_ret(ErrorMsg.NotFoundScopeID, {"scope_id": scope_id})
        if not raw_domain:
            return utils.build_ret(ErrorMsg.DomainInvalid, {"domain": raw_domain})

        clean_domain = raw_domain
        if "://" in clean_domain:
            parsed = urlparse(clean_domain)
            clean_domain = parsed.hostname or clean_domain
        elif "/" in clean_domain:
            clean_domain = clean_domain.split("/")[0]
        if ":" in clean_domain and not clean_domain.startswith("["):
            clean_domain = clean_domain.split(":")[0]
        clean_domain = clean_domain.strip("[]").strip().rstrip(".").lower()

        try:
            # 1. 采用 Python 标准库精确校验 IPv4 与 IPv6，规避手写正则漏洞
            is_ip_input = False
            try:
                ipaddress.ip_address(clean_domain)
                is_ip_input = True
            except ValueError:
                is_ip_input = False

            all_ips = set()
            if is_ip_input:
                all_ips.add(clean_domain)

            # 辅助构建严格的左锚定（Left-Anchored）URL 正则，充分利用 B-Tree 索引前缀加速，杜绝 COLLSCAN 全表扫描
            escaped_dom = re.escape(clean_domain)
            dom_url_prefix = f"^https?://(?:[^/@:]*@)?(?:[a-zA-Z0-9.-]+\\.)?{escaped_dom}(?::\\d+)?(?:/|$)"

            # 1. 站点信息 (asset_site) - 仅裁剪超大 body，保留 favicon.data 以供画像展示
            site_or = [
                {"hostname": clean_domain},
                {"site": {"$regex": dom_url_prefix, "$options": "i"}}
            ]
            if is_ip_input:
                site_or.append({"ip": clean_domain})
            site_query = {
                "scope_id": scope_id,
                "$or": site_or
            }
            site_projection = {"body": 0}
            site_cursor = utils.conn_db('asset_site').find(site_query, site_projection).sort([("_id", -1)]).limit(50)
            site_items = self.build_return_items(site_cursor)

            # 2. 子域名与解析记录 (asset_domain)
            if is_ip_input:
                domain_query = {
                    "scope_id": scope_id,
                    "$or": [
                        {"ips": clean_domain},
                        {"record": clean_domain}
                    ]
                }
            else:
                domain_query = {
                    "scope_id": scope_id,
                    "domain": clean_domain
                }
            domain_cursor = utils.conn_db('asset_domain').find(domain_query).sort([("_id", -1)]).limit(50)
            domain_items = self.build_return_items(domain_cursor)

            # 汇总解析所得 IP 集合
            for s in site_items:
                ip_val = s.get("ip")
                if ip_val and isinstance(ip_val, str) and ip_val.strip():
                    all_ips.add(ip_val.strip())

            for d in domain_items:
                ips = d.get("ips")
                if isinstance(ips, list):
                    for ip in ips:
                        if ip and isinstance(ip, str) and ip.strip():
                            all_ips.add(ip.strip())
                elif isinstance(ips, str) and ips.strip():
                    for ip in ips.split(","):
                        if ip.strip():
                            all_ips.add(ip.strip())

                records = d.get("record")
                if isinstance(records, list):
                    for r in records:
                        r_str = str(r).strip()
                        try:
                            ipaddress.ip_address(r_str)
                            all_ips.add(r_str)
                        except ValueError:
                            pass
                elif isinstance(records, str):
                    r_str = records.strip()
                    try:
                        ipaddress.ip_address(r_str)
                        all_ips.add(r_str)
                    except ValueError:
                        pass

            resolved_ips = list(all_ips)

            # 3. IP 与归属信息 (asset_ip) - 双向聚合：既查已解析到的 IP，也按 domain 查，并将发现的新 IP 反哺
            ip_or = []
            if resolved_ips:
                ip_or.append({"ip": {"$in": resolved_ips}})
            if not is_ip_input:
                ip_or.append({"domain": clean_domain})

            ip_items = []
            if ip_or:
                ip_query = {"scope_id": scope_id, "$or": ip_or}
                ip_cursor = utils.conn_db('asset_ip').find(ip_query).sort([("_id", -1)]).limit(50)
                ip_items = self.build_return_items(ip_cursor)
                for item in ip_items:
                    if item.get("ip"):
                        all_ips.add(item["ip"])
                resolved_ips = list(all_ips)

            # 构造多 IP 左锚定正则模式
            ips_url_prefix = None
            if resolved_ips:
                valid_ips = [re.escape(ip) for ip in resolved_ips[:15] if ip]
                if valid_ips:
                    pattern = "|".join(valid_ips)
                    ips_url_prefix = f"^https?://(?:[^/@:]*@)?(?:{pattern})(?::\\d+)?(?:/|$)"

            # 4~11. 并发并行查询各衍生资产集合（线程池隔离加速）
            def fetch_cert():
                cert_or = [
                    {"cert.extensions.subjectAltName": {"$regex": escaped_dom, "$options": "i"}},
                    {"cert.subject_dn": {"$regex": escaped_dom, "$options": "i"}}
                ]
                if resolved_ips:
                    cert_or.append({"ip": {"$in": resolved_ips}})
                cert_query = {"scope_id": scope_id, "$or": cert_or}
                cert_cursor = utils.conn_db('asset_cert').find(cert_query).sort([("_id", -1)]).limit(50)
                return self.build_return_items(cert_cursor)

            def fetch_service():
                if not resolved_ips:
                    return []
                service_query = {"scope_id": scope_id, "service_info.ip": {"$in": resolved_ips}}
                service_cursor = utils.conn_db('asset_service').find(service_query).sort([("_id", -1)]).limit(100)
                raw_service_items = self.build_return_items(service_cursor)
                service_items = []
                for s in raw_service_items:
                    matching_infos = [info for info in s.get("service_info", []) if info.get("ip") in resolved_ips]
                    if matching_infos:
                        s["service_info"] = matching_infos
                        service_items.append(s)
                return service_items

            def fetch_npoc():
                # 优先使用 host 精准匹配（充分利用 host 字段索引）
                npoc_or = [{"host": clean_domain}]
                if resolved_ips:
                    npoc_or.append({"host": {"$in": resolved_ips}})
                # 补充 URL target 的左锚定正则
                npoc_or.append({"target": {"$regex": dom_url_prefix, "$options": "i"}})
                if ips_url_prefix:
                    npoc_or.append({"target": {"$regex": ips_url_prefix}})
                npoc_query = {"scope_id": scope_id, "$or": npoc_or}
                npoc_cursor = utils.conn_db('asset_npoc_service').find(npoc_query).sort([("_id", -1)]).limit(100)
                return self.build_return_items(npoc_cursor)

            def fetch_fileleak():
                fileleak_or = [
                    {"url": {"$regex": dom_url_prefix, "$options": "i"}}
                ]
                if ips_url_prefix:
                    fileleak_or.append({"url": {"$regex": ips_url_prefix}})
                fileleak_query = {"scope_id": scope_id, "$or": fileleak_or}
                fileleak_cursor = utils.conn_db('asset_fileleak').find(fileleak_query).sort([("_id", -1)]).limit(50)
                return self.build_return_items(fileleak_cursor)

            def fetch_url():
                url_or = [
                    {"url": {"$regex": dom_url_prefix, "$options": "i"}}
                ]
                if ips_url_prefix:
                    url_or.append({"url": {"$regex": ips_url_prefix}})
                url_query = {"scope_id": scope_id, "$or": url_or}
                url_cursor = utils.conn_db('asset_url').find(url_query).sort([("_id", -1)]).limit(50)
                return self.build_return_items(url_cursor)

            def fetch_wih():
                wih_or = [
                    {"site": {"$regex": dom_url_prefix, "$options": "i"}},
                    {"source": {"$regex": dom_url_prefix, "$options": "i"}}
                ]
                if ips_url_prefix:
                    wih_or.append({"site": {"$regex": ips_url_prefix}})
                    wih_or.append({"source": {"$regex": ips_url_prefix}})
                wih_query = {"scope_id": scope_id, "$or": wih_or}
                wih_cursor = utils.conn_db('asset_wih').find(wih_query).sort([("_id", -1)]).limit(100)
                return self.build_return_items(wih_cursor)

            def fetch_vuln():
                vuln_or = [
                    {"target": clean_domain},
                    {"target": {"$regex": f"^{escaped_dom}(?::\\d+)?$", "$options": "i"}},
                    {"target": {"$regex": dom_url_prefix, "$options": "i"}}
                ]
                if resolved_ips:
                    vuln_or.append({"target": {"$in": resolved_ips}})
                    if ips_url_prefix:
                        vuln_or.append({"target": {"$regex": ips_url_prefix}})
                vuln_query = {"scope_id": scope_id, "$or": vuln_or}
                vuln_cursor = utils.conn_db('asset_vuln').find(vuln_query).sort([("_id", -1)]).limit(50)
                return self.build_return_items(vuln_cursor)

            def fetch_nuclei():
                nuclei_or = [
                    {"target": clean_domain},
                    {"target": {"$regex": dom_url_prefix, "$options": "i"}},
                    {"vuln_url": {"$regex": dom_url_prefix, "$options": "i"}}
                ]
                if resolved_ips:
                    nuclei_or.append({"target": {"$in": resolved_ips}})
                    if ips_url_prefix:
                        nuclei_or.append({"target": {"$regex": ips_url_prefix}})
                        nuclei_or.append({"vuln_url": {"$regex": ips_url_prefix}})
                nuclei_query = {"scope_id": scope_id, "$or": nuclei_or}
                nuclei_cursor = utils.conn_db('asset_nuclei_result').find(nuclei_query).sort([("_id", -1)]).limit(50)
                return self.build_return_items(nuclei_cursor)

            def fetch_cip():
                derived_cidrs = set()
                for ip in resolved_ips:
                    try:
                        derived_cidrs.add(str(ipaddress.ip_network(f"{ip}/24", strict=False)))
                    except Exception:
                        pass

                cip_or = []
                if derived_cidrs:
                    cip_or.append({"cidr_ip": {"$in": list(derived_cidrs)}})
                if resolved_ips:
                    cip_or.append({"ip_list": {"$in": resolved_ips}})
                if not is_ip_input:
                    cip_or.append({"domain_list": clean_domain})

                if not cip_or:
                    return []

                cip_query = {"scope_id": scope_id, "$or": cip_or}
                cip_cursor = utils.conn_db('asset_cip').find(cip_query).sort([("_id", -1)]).limit(50)
                return self.build_return_items(cip_cursor)

            def sanitize_chain_items(items):
                """
                【第一性原理：全链路画像脱敏与纯净拓扑保障】
                剔除任务级监控对比历史字段 (update_diff / change_status)，
                彻底消除由基线对比引入的整个资产组数以百计的历史无关 IP 泄漏，大幅压缩 JSON 体积。
                """
                if not items:
                    return []
                for item in items:
                    if isinstance(item, dict):
                        item.pop("update_diff", None)
                        item.pop("change_status", None)
                return items

            tasks = {
                "cip": fetch_cip,
                "cert": fetch_cert,
                "service": fetch_service,
                "npoc_service": fetch_npoc,
                "fileleak": fetch_fileleak,
                "url": fetch_url,
                "wih": fetch_wih,
                "vuln": fetch_vuln,
                "nuclei_result": fetch_nuclei
            }
            results = {}
            with ThreadPoolExecutor(max_workers=min(9, len(tasks))) as executor:
                future_map = {executor.submit(func): key for key, func in tasks.items()}
                for future in as_completed(future_map):
                    key = future_map[future]
                    try:
                        results[key] = sanitize_chain_items(future.result())
                    except Exception as task_err:
                        logger.warning(f"subdomain_chain subtask {key} error: {task_err}")
                        results[key] = []

            # 统一对前置同步拉取的资产进行脱敏清洗
            clean_site_items = sanitize_chain_items(site_items)
            clean_domain_items = sanitize_chain_items(domain_items)
            clean_ip_items = sanitize_chain_items(ip_items)

            cip_items = results.get("cip", [])
            cert_items = results.get("cert", [])
            service_items = results.get("service", [])
            npoc_items = results.get("npoc_service", [])
            fileleak_items = results.get("fileleak", [])
            url_items = results.get("url", [])
            wih_items = results.get("wih", [])
            vuln_items = results.get("vuln", [])
            nuclei_items = results.get("nuclei_result", [])

            summary = {
                "resolved_ips": len(resolved_ips),
                "site": len(clean_site_items),
                "domain_records": len(clean_domain_items),
                "ip": len(clean_ip_items),
                "cip": len(cip_items),
                "cert": len(cert_items),
                "service": len(service_items),
                "npoc_service": len(npoc_items),
                "fileleak": len(fileleak_items),
                "url": len(url_items),
                "wih": len(wih_items),
                "vuln": len(vuln_items),
                "nuclei_result": len(nuclei_items)
            }

            data = {
                "scope_id": scope_id,
                "target": clean_domain,
                "domain": clean_domain,
                "export_time": utils.curr_date(),
                "resolved_ips": resolved_ips,
                "summary": summary,
                "site": clean_site_items,
                "domain_records": clean_domain_items,
                "ip": clean_ip_items,
                "cip": cip_items,
                "cert": cert_items,
                "service": service_items,
                "npoc_service": npoc_items,
                "fileleak": fileleak_items,
                "url": url_items,
                "wih": wih_items,
                "vuln": vuln_items,
                "nuclei_result": nuclei_items
            }

            return utils.build_ret(ErrorMsg.Success, data)
        except Exception as e:
            logger.exception(f"subdomain_chain query error: {e}")
            return utils.build_ret(ErrorMsg.Error, {"error": str(e)})
