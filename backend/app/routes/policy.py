from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg
from app import utils
from bson import ObjectId
from flask_restx.fields import Nested
from flask_restx.model import Model

ns = Namespace('policy', description="策略信息")

logger = get_logger()

base_search_fields = {
    'name': fields.String(required=False, description="策略名称"),
    "_id": fields.String(description="策略ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLPolicy(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        策略信息查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='policy')

        return data


'''域名相关配置选项'''
domain_config_fields = ns.model('domainConfig', {
    "domain_brute": fields.Boolean(description="域名爆破", default=True),
    "domain_brute_type": fields.String(description="域名爆破类型(big)", example="big"),
    "alt_dns": fields.Boolean(description="DNS字典智能生成", default=True),
    "alt_dns_dict": fields.String(description="智能子域爆破字典选择", default="altdnsdict.txt"),
    "arl_search": fields.Boolean(description="ARL 历史查询", default=True),
    "dns_query_plugin": fields.Boolean(description="域名插件查询", default=False)
})

'''IP 相关配置选项'''
ip_config_fields = ns.model('ipConfig', {
    "port_scan": fields.Boolean(description="端口扫描", default=True),
    "port_scan_type": fields.String(description="端口扫描类型(test|top100|top1000|all|custom)", example="test"),
    "service_detection": fields.Boolean(description="服务识别", default=False),
    "os_detection": fields.Boolean(description="操作系统识别", default=False),
    "ssl_cert": fields.Boolean(description="SSL 证书获取", default=False),
    "skip_scan_cdn_ip": fields.Boolean(description="跳过 CDN IP扫描", default=True),  # 这个参数强制生效
    "port_custom": fields.String(description="自定义扫描端口", default="80,443"),  # 仅端口扫描类型为 custom 时生效
    "host_timeout_type": fields.String(description="主机超时时间类别（default|custom）", default="default"),
    "host_timeout": fields.Integer(description="主机超时时间(s)", default=900),
    "port_parallelism": fields.Integer(description="探测报文并行度", default=32),
    "port_min_rate": fields.Integer(description="最少发包速率", default=60),
    "exclude_ports": fields.String(description="排除扫描端口", default=""),
})

'''站点相关配置选项'''
site_config_fields = ns.model('siteConfig', {
    "site_identify": fields.Boolean(description="站点识别", default=False),
    "site_capture": fields.Boolean(description="站点截图", default=False),
    "search_engines": fields.Boolean(description="搜索引擎调用", default=False),
    "site_spider": fields.Boolean(description="站点爬虫", default=False),
    "nuclei_scan": fields.Boolean(description="nuclei 扫描", default=False),
    "nuclei_config": fields.Raw(description="nuclei 扫描细粒度配置", default={}),
    "findvhost": fields.Boolean(description="Host 碰撞", default=False),
    "web_info_hunter": fields.Boolean(example=False, default=False, description="web JS 中的信息收集"),
})

'''资产组关联配置'''
scope_config_fields = ns.model('scopeConfig', {
    "scope_id": fields.String(description="资产组 ID", default=""),
})

add_policy_fields = ns.model('addPolicy', {
    "name": fields.String(required=True, description="策略名称"),
    "desc": fields.String(description="策略描述信息"),
    "policy": fields.Nested(ns.model("policy", {
        "domain_config": fields.Nested(domain_config_fields),
        "ip_config": fields.Nested(ip_config_fields),
        "site_config": fields.Nested(site_config_fields),
        "file_leak": fields.Boolean(description="文件泄漏", default=False),
        "file_leak_dict": fields.String(description="文件泄露字典选择", default="file_top_2000.txt"),
        "npoc_service_detection": fields.Boolean(description="服务识别（纯python实现）", default=False),
        "poc_config": fields.List(fields.Nested(ns.model('pocConfig', {
            "plugin_name": fields.String(description="poc 插件名称ID", default=False),
            "enable": fields.Boolean(description="是否启用", default=True)
        }))),
        "brute_config": fields.List(fields.Nested(ns.model('bruteConfig', {
            "plugin_name": fields.String(description="poc 插件名称ID", default=False),
            "enable": fields.Boolean(description="是否启用", default=True)
        }))),
        "scope_config": fields.Nested(scope_config_fields)
    }, required=True)
                            )
})


@ns.route('/add/')
class AddARLPolicy(ARLResource):

    @auth
    @ns.expect(add_policy_fields)
    def post(self):
        """
        策略添加
        """
        args = self.parse_args(add_policy_fields)
        name = str(args.pop("name", "")).strip()
        if not name:
            return utils.build_ret("策略名称不能为空", {})

        policy = args.pop("policy", {})
        if policy is None:
            return utils.build_ret("Missing policy parameter", {})

        domain_config = policy.pop("domain_config", {}) or {}
        domain_config = self._update_arg(domain_config, domain_config_fields)
        ip_config = policy.pop("ip_config", {}) or {}
        port_scan_type = ip_config.get("port_scan_type", "test")
        if port_scan_type == "custom":
            port_custom = ip_config.get("port_custom") or "80,443"
            port_list = utils.arl.build_port_custom(port_custom)
            if isinstance(port_list, str):
                return utils.build_ret(ErrorMsg.PortCustomInvalid, {"port_custom": port_list})

            ip_config["port_custom"] = ",".join(port_list)

        exclude_ports = ip_config.get("exclude_ports", "")
        if exclude_ports:
            if not utils.is_valid_exclude_ports(exclude_ports):
                return utils.build_ret(ErrorMsg.ExcludePortsInvalid, {"exclude_ports": exclude_ports})

        # 🛡️ 发包并发与速率参数范围防御与归一化
        try:
            p_val = int(ip_config.get("port_parallelism", 32) or 32)
            ip_config["port_parallelism"] = 32 if p_val <= 0 else min(p_val, 1000)
        except (ValueError, TypeError):
            ip_config["port_parallelism"] = 32

        try:
            r_val = int(ip_config.get("port_min_rate", 60) or 60)
            ip_config["port_min_rate"] = 60 if r_val <= 0 else min(r_val, 10000)
        except (ValueError, TypeError):
            ip_config["port_min_rate"] = 60

        try:
            t_val = int(ip_config.get("host_timeout", 900) or 900)
            ip_config["host_timeout"] = 900 if t_val <= 0 else min(t_val, 86400)
        except (ValueError, TypeError):
            ip_config["host_timeout"] = 900

        ip_config = self._update_arg(ip_config, ip_config_fields)

        site_config = policy.pop("site_config", {}) or {}
        site_config = self._update_arg(site_config, site_config_fields)

        poc_config = policy.pop("poc_config", [])
        if poc_config is None:
            poc_config = []

        poc_config = _update_plugin_config(poc_config)
        if isinstance(poc_config, str):
            return utils.build_ret(poc_config, {})

        brute_config = policy.pop("brute_config", [])
        if brute_config is None:
            brute_config = []
        brute_config = _update_plugin_config(brute_config)
        if isinstance(brute_config, str):
            return utils.build_ret(brute_config, {})

        file_leak = fields.boolean(policy.pop("file_leak", False))
        raw_leak_dict = policy.pop("file_leak_dict", None)
        if not raw_leak_dict or not str(raw_leak_dict).strip():
            file_leak_dict = "file_top_2000.txt"
        else:
            file_leak_dict = str(raw_leak_dict).strip()
        
        # 兼容若从 site_config 传入 file_leak 的情形
        if "file_leak" in site_config and not file_leak:
            file_leak = fields.boolean(site_config.get("file_leak", False))
        if "file_leak_dict" in site_config and (file_leak_dict == "file_top_2000.txt" or not file_leak_dict):
            site_val = site_config.get("file_leak_dict")
            if site_val and str(site_val).strip():
                file_leak_dict = str(site_val).strip()

        # 统一服务识别：类型安全解析并自动双轨协同
        raw_npoc = policy.pop("npoc_service_detection", None)
        npoc_val = fields.boolean(raw_npoc) if raw_npoc is not None else False
        is_service_detect = bool(ip_config.get("service_detection", False) or npoc_val)
        ip_config["service_detection"] = is_service_detect
        npoc_service_detection = is_service_detect

        desc = args.pop("desc", "")

        # 宽容处理并丢弃 scope_config / site_capture 死字段
        policy.pop("scope_config", None)
        site_config.pop("site_capture", None)

        item = {
            "name": name,
            "policy": {
                "domain_config": domain_config,
                "ip_config": ip_config,
                "site_config": site_config,
                "poc_config": poc_config,
                "brute_config": brute_config,
                "file_leak": file_leak,
                "file_leak_dict": file_leak_dict,
                "npoc_service_detection": npoc_service_detection
            },
            "desc": desc,
            "update_date": utils.curr_date()
        }
        utils.conn_db("policy").insert_one(item)

        return utils.build_ret(ErrorMsg.Success, {"policy_id": str(item["_id"])})

    def _update_arg(self, arg_dict, default_module):
        default_dict = get_dict_default_from_module(default_module)
        if arg_dict is None:
            return default_dict

        default_dict.update(arg_dict)

        for x in default_dict:
            if x not in default_module:
                continue

            default_dict[x] = default_module[x].format(default_dict[x])

        return default_dict


def plugin_name_in_arl(name):
    query = {
        "plugin_name": name
    }
    item = utils.conn_db('poc').find_one(query)
    return item


def get_dict_default_from_module(module):
    ret = {}
    for x in module:
        v = module[x]
        ret[x] = None
        if v.default is not None:
            ret[x] = v.default

        if v.example is not None:
            ret[x] = v.example

    return ret


delete_policy_fields = ns.model('DeletePolicy', {
    'policy_id': fields.List(fields.String(required=True, description="策略ID", example="603c65316591e73dd717d176"))
})


@ns.route('/delete/')
class DeletePolicy(ARLResource):
    @auth
    @ns.expect(delete_policy_fields)
    def post(self):
        """
        策略删除
        """
        args = self.parse_args(delete_policy_fields)
        policy_id_list = args.pop('policy_id')
        for policy_id in policy_id_list:
            if not policy_id or not ObjectId.is_valid(str(policy_id)):
                continue
            utils.conn_db('policy').delete_one({'_id': ObjectId(policy_id)})

        """这里直接返回成功了"""
        return utils.build_ret(ErrorMsg.Success, {})


edit_policy_fields = ns.model('editPolicy', {
    'policy_id': fields.String(required=True, description="策略ID", example="603c65316591e73dd717d176"),
    'policy_data': fields.Nested(ns.model("policyData", {}))
})


@ns.route('/edit/')
class EditPolicy(ARLResource):
    @auth
    @ns.expect(edit_policy_fields)
    def post(self):
        """
        策略编辑
        """
        args = self.parse_args(edit_policy_fields)
        policy_id = args.pop('policy_id', '')
        if not policy_id or not ObjectId.is_valid(str(policy_id)):
            return utils.build_ret(ErrorMsg.PolicyIDNotFound, {})

        policy_data = args.pop('policy_data', {})
        query = {'_id': ObjectId(policy_id)}
        item = utils.conn_db('policy').find_one(query)

        if not item:
            return utils.build_ret(ErrorMsg.PolicyIDNotFound, {})

        if not policy_data:
            return utils.build_ret(ErrorMsg.PolicyDataIsEmpty, {})

        # 兼容外部传入扁平化 policy_data (未显式包含 policy 根键)
        if "policy" not in policy_data:
            extracted_policy = {}
            for k in list(policy_data.keys()):
                if k not in ["name", "desc"]:
                    extracted_policy[k] = policy_data.pop(k)
            policy_data["policy"] = extracted_policy

        allow_keys = gen_model_policy_keys(add_policy_fields["policy"])
        allow_keys.extend(["name", "desc", "policy"])

        item = change_policy_dict(item, policy_data, allow_keys)

        poc_config = item["policy"].pop("poc_config", [])
        poc_config = _update_plugin_config(poc_config)
        if isinstance(poc_config, str):
            return utils.build_ret(poc_config, {})
        item["policy"]["poc_config"] = poc_config

        brute_config = item["policy"].pop("brute_config", [])
        brute_config = _update_plugin_config(brute_config)
        if isinstance(brute_config, str):
            return utils.build_ret(brute_config, {})
        item["policy"]["brute_config"] = brute_config

        # 🛡️ 统一服务识别合并与死字段清理：精准捕获外部更新意图并保持双轨协同
        policy_obj = item.setdefault("policy", {})
        ip_cfg = policy_obj.setdefault("ip_config", {})

        incoming_policy = policy_data.get("policy", {}) if isinstance(policy_data.get("policy"), dict) else {}
        incoming_ip = incoming_policy.get("ip_config", {}) if isinstance(incoming_policy.get("ip_config"), dict) else {}

        if "service_detection" in incoming_ip:
            is_svc_detect = bool(incoming_ip["service_detection"])
        elif "npoc_service_detection" in incoming_policy:
            is_svc_detect = bool(incoming_policy["npoc_service_detection"])
        else:
            is_svc_detect = bool(ip_cfg.get("service_detection", False) or policy_obj.get("npoc_service_detection", False))

        ip_cfg["service_detection"] = is_svc_detect
        policy_obj["npoc_service_detection"] = is_svc_detect

        policy_obj.pop("scope_config", None)
        if "site_config" in policy_obj and isinstance(policy_obj["site_config"], dict):
            policy_obj["site_config"].pop("site_capture", None)

        incoming_site = incoming_policy.get("site_config", {}) if isinstance(incoming_policy.get("site_config"), dict) else {}
        if "nuclei_config" in incoming_site and isinstance(incoming_site["nuclei_config"], dict):
            site_cfg = policy_obj.setdefault("site_config", {})
            site_cfg["nuclei_config"] = incoming_site["nuclei_config"]

        # 🛡️ 排除端口格式校验（防非法字符入库）
        incoming_exclude_ports = incoming_ip.get("exclude_ports")
        if incoming_exclude_ports is not None and str(incoming_exclude_ports).strip():
            if not utils.is_valid_exclude_ports(str(incoming_exclude_ports).strip()):
                return utils.build_ret(ErrorMsg.ExcludePortsInvalid, {"exclude_ports": str(incoming_exclude_ports).strip()})

        # 🛡️ 自定义端口格式校验
        if incoming_ip.get("port_scan_type") == "custom":
            port_custom = incoming_ip.get("port_custom") or ip_cfg.get("port_custom") or "80,443"
            port_list = utils.arl.build_port_custom(port_custom)
            if isinstance(port_list, str):
                return utils.build_ret(ErrorMsg.PortCustomInvalid, {"port_custom": port_list})
            ip_cfg["port_custom"] = ",".join(port_list)

        # 🛡️ 发包并发与速率参数范围防御与归一化
        try:
            p_val = int(ip_cfg.get("port_parallelism", 32) or 32)
            ip_cfg["port_parallelism"] = 32 if p_val <= 0 else min(p_val, 1000)
        except (ValueError, TypeError):
            ip_cfg["port_parallelism"] = 32

        try:
            r_val = int(ip_cfg.get("port_min_rate", 60) or 60)
            ip_cfg["port_min_rate"] = 60 if r_val <= 0 else min(r_val, 10000)
        except (ValueError, TypeError):
            ip_cfg["port_min_rate"] = 60

        try:
            t_val = int(ip_cfg.get("host_timeout", 900) or 900)
            ip_cfg["host_timeout"] = 900 if t_val <= 0 else min(t_val, 86400)
        except (ValueError, TypeError):
            ip_cfg["host_timeout"] = 900

        # 兼容文件泄露字典判空与默认回退
        if policy_obj.get("file_leak"):
            if not policy_obj.get("file_leak_dict") or not str(policy_obj.get("file_leak_dict")).strip():
                policy_obj["file_leak_dict"] = "file_top_2000.txt"

        item["update_date"] = utils.curr_date()
        utils.conn_db('policy').find_one_and_replace(query, item)
        item.pop('_id')

        return utils.build_ret(ErrorMsg.Success, {"data": item})


def _update_plugin_config(config):
    if not isinstance(config, (list, tuple)):
        return []

    plugin_name_set = set()
    unique_items = []
    for item in config:
        if not isinstance(item, dict):
            continue
        plugin_name = item.get("plugin_name")
        enable = item.get("enable")
        if plugin_name is None or enable is None:
            continue
        plugin_name = str(plugin_name).strip()
        if not plugin_name:
            continue
        if plugin_name in plugin_name_set:
            continue

        plugin_name_set.add(plugin_name)
        unique_items.append({"plugin_name": plugin_name, "enable": bool(enable)})

    if not unique_items:
        return []

    # 批量聚合校验：使用 $in 消除 N+1 数据库风暴，仅投影必要字段，规避海量插件保存时 Gunicorn 超时
    plugin_names = [item["plugin_name"] for item in unique_items]
    poc_map = {}
    chunk_size = 5000
    for i in range(0, len(plugin_names), chunk_size):
        chunk = plugin_names[i:i + chunk_size]
        cursor = utils.conn_db('poc').find(
            {"plugin_name": {"$in": chunk}},
            {"plugin_name": 1, "vul_name": 1}
        )
        if cursor:
            for doc in cursor:
                name = doc.get("plugin_name")
                if name and name not in poc_map:
                    poc_map[name] = doc

    ret = []
    for item in unique_items:
        plugin_name = item["plugin_name"]
        plugin_info = poc_map.get(plugin_name)
        if not plugin_info:
            return "没有找到 {} 插件".format(plugin_name)

        config_item = {
            "plugin_name": plugin_name,
            "vul_name": plugin_info.get("vul_name") or "",
            "enable": item["enable"]
        }
        ret.append(config_item)

    return ret


# change_policy_dict, 用于修改策略，支持新的字段被修改
def change_policy_dict(old_data, new_data, allow_keys):
    if not isinstance(new_data, dict):
        return

    for key in new_data:
        if key not in allow_keys:
            continue

        next_old_data = old_data.get(key)
        next_new_data = new_data[key]
        if next_old_data is None:
            old_data[key] = next_new_data
            continue

        next_new_data_type = type(next_new_data)
        next_old_data_type = type(next_old_data)

        if isinstance(next_old_data, dict):
            if key == "nuclei_config":
                old_data[key] = next_new_data
            else:
                change_policy_dict(next_old_data, next_new_data, allow_keys)

        elif isinstance(next_old_data, list) and isinstance(next_new_data, list):
            old_data[key] = next_new_data

        elif next_new_data_type == next_old_data_type:
            old_data[key] = next_new_data

    return old_data  # 返回data


# gen_model_policy_keys  递归生成策略的key (解决合法性问题)
def gen_model_policy_keys(model):
    if isinstance(model, Model):
        keys = []
        for name in model:
            keys.append(name)
            keys.extend(gen_model_policy_keys(model[name]))

        return keys

    elif isinstance(model, Nested):
        return gen_model_policy_keys(model.model)
    else:
        return []
