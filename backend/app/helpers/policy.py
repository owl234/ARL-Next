import bson
from app import utils
from app.modules import TaskTag


VALID_NUCLEI_SEVERITIES = frozenset({"critical", "high", "medium", "low", "info"})
VALID_NUCLEI_CUSTOM_MODES = ("all_enabled", "selected", "tags", "none")


def normalize_nuclei_config(raw_cfg, nuclei_scan_enabled: bool = False, strict_severity: bool = False):
    """归一化并校验 Nuclei 扫描细粒度配置，保持对历史策略与任务参数的向下兼容。"""
    if raw_cfg is not None and not isinstance(raw_cfg, dict):
        return None, "无效的 nuclei_config 格式，必须为对象"
    cfg = dict(raw_cfg) if isinstance(raw_cfg, dict) else {}

    raw_inc = cfg.get("include_community", True)
    if isinstance(raw_inc, str):
        include_community = raw_inc.strip().lower() not in ("false", "0", "no", "")
    else:
        include_community = bool(raw_inc)

    mode = str(cfg.get("custom_template_mode") or "all_enabled").strip().lower()
    if mode not in VALID_NUCLEI_CUSTOM_MODES:
        return None, f"无效的自建模板模式: {mode}"

    raw_sevs = cfg.get("severity")
    if raw_sevs is not None and not isinstance(raw_sevs, list):
        return None, "无效的 severity 参数，必须为列表"
    if isinstance(raw_sevs, list) and raw_sevs:
        severities = []
        seen_sevs = set()
        for item in raw_sevs:
            s_val = str(item).strip().lower()
            if not s_val:
                continue
            if s_val not in VALID_NUCLEI_SEVERITIES:
                if strict_severity:
                    return None, f"无效的 Nuclei 危害级别: {item}"
                continue
            if s_val not in seen_sevs:
                seen_sevs.add(s_val)
                severities.append(s_val)
        if not severities:
            severities = ["critical", "high", "medium", "low"]
    else:
        severities = ["critical", "high", "medium", "low"]

    selected_templates = list(dict.fromkeys(
        str(x).strip() for x in (cfg.get("selected_custom_templates") or []) if str(x).strip()
    ))
    selected_tags = list(dict.fromkeys(
        str(x).strip().lower() for x in (cfg.get("selected_tags") or []) if str(x).strip()
    ))
    extra_exclude_ids = list(dict.fromkeys(
        str(x).strip() for x in (cfg.get("extra_exclude_ids") or []) if str(x).strip()
    ))

    if nuclei_scan_enabled:
        if not include_community and mode == "none":
            return None, "启用 Nuclei 扫描时，社区模板库与自建模板不能同时关闭"
        if mode == "selected" and not selected_templates:
            return None, "自建模板选择为「指定模板」时，请至少选择 1 个自建模板"
        if mode == "tags" and not selected_tags:
            return None, "自建模板选择为「按标签筛选」时，请至少选择 1 个标签"

    normalized = {
        "include_community": include_community,
        "severity": severities,
        "exclude_blacklist": bool(cfg.get("exclude_blacklist", True)),
        "custom_template_mode": mode,
        "selected_custom_templates": selected_templates,
        "selected_tags": selected_tags,
    }
    if extra_exclude_ids:
        normalized["extra_exclude_ids"] = extra_exclude_ids
    return normalized, None


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
