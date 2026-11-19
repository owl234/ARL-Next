import bson
from app import utils
from app.modules import TaskTag


def normalize_site_capture(value, default: bool = True) -> bool:
    """归一化站点截图开关（缺省/None 返回 default；兼容布尔值与常见字符串布尔值）。"""
    if value is None:
        return bool(default)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in ("false", "0", "no", "off", ""):
            return False
        if normalized in ("true", "1", "yes", "on"):
            return True
    return bool(value)


def get_options_by_policy_id(policy_id, task_tag):
    if not policy_id or not bson.ObjectId.is_valid(str(policy_id)):
        return None

    query = {
        "_id": bson.ObjectId(policy_id)
    }
    data = utils.conn_db("policy").find_one(query)
    if not data:
        return None

    policy = dict(data.get("policy") or {})
    options = {
        "policy_name": data.get("name", "")
    }
    domain_config = dict(policy.pop("domain_config", None) or {})
    ip_config = dict(policy.pop("ip_config", None) or {})
    site_config = dict(policy.pop("site_config", None) or {})

    # 移除死字段；site_capture 缺省默认开启以保持历史兼容
    policy.pop("scope_config", None)
    site_config["site_capture"] = normalize_site_capture(site_config.get("site_capture"))

    """仅仅资产发现任务需要这些"""
    if task_tag == TaskTag.TASK:
        options.update(domain_config)
        options.update(ip_config)

    options.update(site_config)
    options.update(policy)

    # 🛡️ 双轨服务识别统一：若开启 service_detection，自动协同开启 npoc_service_detection
    is_service_detect = bool(options.get("service_detection") or options.get("npoc_service_detection"))
    if is_service_detect:
        options["service_detection"] = True
        options["npoc_service_detection"] = True

    # 🛡️ 兼容文件泄露字段双向回退（真值与自定义字典优先）
    if site_config.get("file_leak") and not options.get("file_leak"):
        options["file_leak"] = site_config["file_leak"]
    if site_config.get("file_leak_dict") and (not options.get("file_leak_dict") or options.get("file_leak_dict") == "file_top_2000.txt"):
        options["file_leak_dict"] = str(site_config["file_leak_dict"])

    return options
