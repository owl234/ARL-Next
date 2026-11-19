import re
from urllib.parse import urlparse

from flask import Blueprint, request, jsonify
from app import utils
from app.config import Config
from app.modules import ErrorMsg

github_threat_bp = Blueprint('github_threat', __name__)


def _normalize_repo_api_url(raw_url: str) -> str:
    """Normalize GitHub web URL, API URL, or `owner/repo` shorthand into API repo URL."""
    text = (raw_url or '').strip()
    if not text:
        return ""
    text = text.split('#', 1)[0].split('?', 1)[0].strip().rstrip('/')
    if text.endswith('.git'):
        text = text[:-4]

    owner_repo = ""
    if "api.github.com/repos/" in text.lower():
        parsed = urlparse(text)
        parts = [p for p in parsed.path.split('/') if p]
        if len(parts) >= 3 and parts[0].lower() == "repos":
            owner_repo = f"{parts[1]}/{parts[2]}"
    elif "github.com/" in text.lower():
        if not text.lower().startswith(("http://", "https://")):
            text = "https://" + text.lstrip("/")
        parsed = urlparse(text)
        if parsed.netloc.lower().endswith("github.com"):
            parts = [p for p in parsed.path.split('/') if p]
            if len(parts) >= 2:
                owner_repo = f"{parts[0]}/{parts[1]}"
    elif "/" in text and "://" not in text and not text.startswith("/"):
        parts = [p for p in text.split('/') if p]
        if len(parts) == 2:
            owner_repo = f"{parts[0]}/{parts[1]}"

    if not owner_repo:
        return ""
    owner, repo = owner_repo.split('/', 1)
    if not re.match(r'^[A-Za-z0-9._-]+$', owner) or not re.match(r'^[A-Za-z0-9._-]+$', repo):
        return ""
    return f"https://api.github.com/repos/{owner}/{repo}"


def _normalize_github_id(raw_id: str) -> str:
    """Extract a clean GitHub username/org slug from ID, @mention, or profile URL."""
    text = (raw_id or '').strip()
    if not text:
        return ""
    text = text.split('#', 1)[0].split('?', 1)[0].strip().rstrip('/')
    if "github.com/" in text.lower():
        if not text.lower().startswith(("http://", "https://")):
            text = "https://" + text.lstrip("/")
        parsed = urlparse(text)
        parts = [p for p in parsed.path.split('/') if p]
        text = parts[0] if parts else ""
    text = text.lstrip('@').strip()
    if not text or not re.match(r'^[A-Za-z0-9-]+$', text):
        return ""
    return text


@github_threat_bp.before_request
def _require_auth():
    """本 Blueprint 内所有端点(含删除、改配置、触发扫描)均需登录态。

    其余 /api/* 路由均由 @auth 装饰器逐个鉴权，本组通过 register_blueprint 注册，
    缺少统一校验，导致匿名用户可清空监控目标、篡改监控配置并触发外网扫描。
    """
    if request.method == "OPTIONS":
        return
    if Config.AUTH and not utils.user_login_header():
        return jsonify({"message": "not login", "code": 401, "data": {}})


@github_threat_bp.route('/tools_target', methods=['GET'])
def get_tools_target():
    data = list(utils.conn_db("github_tools_target").find({}, {"_id": 0}))
    return utils.build_ret(ErrorMsg.Success, data)


@github_threat_bp.route('/tools_target', methods=['POST'])
def add_tools_target():
    req_data = request.json or {}
    db = utils.conn_db("github_tools_target")

    # 批量订阅模式
    if isinstance(req_data.get('repo_urls'), list):
        added, skipped, invalid = 0, 0, 0
        for raw in req_data.get('repo_urls') or []:
            repo_url = _normalize_repo_api_url(str(raw))
            if not repo_url:
                invalid += 1
                continue
            if db.find_one({"repo_url": repo_url}):
                skipped += 1
                continue
            db.insert_one({
                "repo_url": repo_url,
                "last_tag": "",
                "last_commit_time": "",
                "release_url": "",
                "release_name": "",
                "release_notes": "",
                "insert_time": utils.curr_date()
            })
            added += 1
        return utils.build_ret(ErrorMsg.Success, {
            "added": added,
            "skipped": skipped,
            "invalid": invalid,
            "msg": f"新增 {added} 个，跳过重复 {skipped} 个，无效 {invalid} 个"
        })

    repo_url = _normalize_repo_api_url(req_data.get('repo_url', ''))
    if not repo_url:
        return utils.build_ret(ErrorMsg.Error, {"error": "请输入正确的 Github 地址或 owner/repo，如 https://github.com/chaitin/xray"})

    if db.find_one({"repo_url": repo_url}):
        return utils.build_ret(ErrorMsg.Error, {"error": "该工具已被监控"})

    db.insert_one({
        "repo_url": repo_url,
        "last_tag": "",
        "last_commit_time": "",
        "release_url": "",
        "release_name": "",
        "release_notes": "",
        "insert_time": utils.curr_date()
    })
    return utils.build_ret(ErrorMsg.Success, {"msg": "添加成功"})


def _extract_valid_str_list(raw_values):
    """严格提取非空字符串列表，拒绝嵌套对象以防 MongoDB 查询操作符注入。"""
    if not isinstance(raw_values, list):
        return None
    cleaned = []
    for item in raw_values:
        if not isinstance(item, str):
            return None
        val = item.strip()
        if val:
            cleaned.append(val)
    return cleaned


def _extract_valid_str(raw_value):
    if not isinstance(raw_value, str):
        return None
    val = raw_value.strip()
    return val or None


def _parse_radar_config_payload(raw_json):
    if not isinstance(raw_json, dict):
        return None, None, "请求体必须为 JSON 对象"
    enabled = bool(raw_json.get('enabled', False))
    raw_interval = raw_json.get('interval', 6)
    if isinstance(raw_interval, bool):
        return None, None, "interval 必须为有效正数"
    try:
        interval_val = float(raw_interval)
    except (TypeError, ValueError):
        return None, None, "interval 必须为有效正数"
    if not (0.5 <= interval_val <= 720):
        return None, None, "interval 必须在 0.5 到 720 小时之间"
    interval_norm = int(interval_val) if interval_val.is_integer() else round(interval_val, 2)
    return enabled, interval_norm, None


@github_threat_bp.route('/tools_target/delete', methods=['POST'])
def delete_tools_target():
    req_data = request.get_json(silent=True)
    if not isinstance(req_data, dict):
        return utils.build_ret(ErrorMsg.Error, {"error": "无效的请求体"})
    if 'repo_urls' in req_data:
        repo_urls = _extract_valid_str_list(req_data.get('repo_urls'))
        if repo_urls is None:
            return utils.build_ret(ErrorMsg.Error, {"error": "repo_urls 必须为字符串列表"})
        if repo_urls:
            utils.conn_db("github_tools_target").delete_many({"repo_url": {"$in": repo_urls}})
    else:
        repo_url = _extract_valid_str(req_data.get('repo_url'))
        if not repo_url:
            return utils.build_ret(ErrorMsg.Error, {"error": "repo_url 必须为非空字符串"})
        utils.conn_db("github_tools_target").delete_one({"repo_url": repo_url})
    return utils.build_ret(ErrorMsg.Success, {"msg": "删除成功"})


@github_threat_bp.route('/hackers_target', methods=['GET'])
def get_hackers_target():
    data = list(utils.conn_db("github_hackers_target").find({}, {"_id": 0}))
    history_data = list(utils.conn_db("github_hackers_history").find({}, {"_id": 0}))

    for target in data:
        gid = target.get('github_id', '').strip()
        # full_name 格式通常为 owner/repo, 所以 owner 就是 github_id
        # 此处不区分大小写比较
        count = sum(1 for h in history_data if h.get("full_name", "").lower().startswith(f"{gid.lower()}/"))
        target['found_count'] = count

    return utils.build_ret(ErrorMsg.Success, data)


@github_threat_bp.route('/hackers_history', methods=['GET'])
def get_hackers_history():
    github_id = (request.args.get('github_id') or '').strip()
    keyword = (request.args.get('q') or '').strip()

    and_clauses = []
    if github_id:
        and_clauses.append({"full_name": {"$regex": f"^{re.escape(github_id)}/", "$options": "i"}})
    if keyword:
        kw_re = {"$regex": re.escape(keyword), "$options": "i"}
        and_clauses.append({"$or": [{"full_name": kw_re}, {"description": kw_re}, {"language": kw_re}]})

    query = {}
    if len(and_clauses) == 1:
        query = and_clauses[0]
    elif len(and_clauses) > 1:
        query = {"$and": and_clauses}

    data = list(utils.conn_db("github_hackers_history").find(query, {"_id": 0}).sort("insert_time", -1))
    return utils.build_ret(ErrorMsg.Success, data)


@github_threat_bp.route('/hackers_target', methods=['POST'])
def add_hackers_target():
    req_data = request.json or {}
    db = utils.conn_db("github_hackers_target")

    if isinstance(req_data.get('github_ids'), list):
        added, skipped, invalid = 0, 0, 0
        for raw in req_data.get('github_ids') or []:
            gid = _normalize_github_id(str(raw))
            if not gid:
                invalid += 1
                continue
            if db.find_one({"github_id": {"$regex": f"^{re.escape(gid)}$", "$options": "i"}}):
                skipped += 1
                continue
            db.insert_one({
                "github_id": gid,
                "insert_time": utils.curr_date()
            })
            added += 1
        return utils.build_ret(ErrorMsg.Success, {
            "added": added,
            "skipped": skipped,
            "invalid": invalid,
            "msg": f"新增 {added} 个，跳过重复 {skipped} 个，无效 {invalid} 个"
        })

    github_id = _normalize_github_id(req_data.get('github_id', ''))
    if not github_id:
        return utils.build_ret(ErrorMsg.Error, {"error": "请输入有效的 Github ID 或主页地址"})

    if db.find_one({"github_id": {"$regex": f"^{re.escape(github_id)}$", "$options": "i"}}):
        return utils.build_ret(ErrorMsg.Error, {"error": "该研究员已被监控"})

    db.insert_one({
        "github_id": github_id,
        "insert_time": utils.curr_date()
    })
    return utils.build_ret(ErrorMsg.Success, {"msg": "添加成功"})


@github_threat_bp.route('/hackers_target/delete', methods=['POST'])
def delete_hackers_target():
    req_data = request.get_json(silent=True)
    if not isinstance(req_data, dict):
        return utils.build_ret(ErrorMsg.Error, {"error": "无效的请求体"})
    if 'github_ids' in req_data:
        github_ids = _extract_valid_str_list(req_data.get('github_ids'))
        if github_ids is None:
            return utils.build_ret(ErrorMsg.Error, {"error": "github_ids 必须为字符串列表"})
        if github_ids:
            utils.conn_db("github_hackers_target").delete_many({"github_id": {"$in": github_ids}})
    else:
        github_id = _extract_valid_str(req_data.get('github_id'))
        if not github_id:
            return utils.build_ret(ErrorMsg.Error, {"error": "github_id 必须为非空字符串"})
        utils.conn_db("github_hackers_target").delete_one({"github_id": github_id})
    return utils.build_ret(ErrorMsg.Success, {"msg": "删除成功"})


@github_threat_bp.route('/cve_history', methods=['GET'])
def get_cve_history():
    try:
        limit = max(1, min(500, int(request.args.get('limit', 100))))
    except (TypeError, ValueError):
        limit = 100
    data = list(utils.conn_db("github_cve_history").find({}, {"_id": 0}).sort("insert_time", -1).limit(limit))
    return utils.build_ret(ErrorMsg.Success, data)


@github_threat_bp.route('/cve_history/delete', methods=['POST'])
def delete_cve_history():
    req_data = request.get_json(silent=True)
    if not isinstance(req_data, dict):
        return utils.build_ret(ErrorMsg.Error, {"error": "无效的请求体"})
    if 'cve_names' in req_data:
        cve_names = _extract_valid_str_list(req_data.get('cve_names'))
        if cve_names is None:
            return utils.build_ret(ErrorMsg.Error, {"error": "cve_names 必须为字符串列表"})
        if cve_names:
            utils.conn_db("github_cve_history").delete_many({"cve_name": {"$in": cve_names}})
    else:
        cve_name = _extract_valid_str(req_data.get('cve_name'))
        if not cve_name:
            return utils.build_ret(ErrorMsg.Error, {"error": "cve_name 必须为非空字符串"})
        utils.conn_db("github_cve_history").delete_one({"cve_name": cve_name})
    return utils.build_ret(ErrorMsg.Success, {"msg": "删除成功"})


@github_threat_bp.route('/cve_config', methods=['GET'])
def get_cve_config():
    db = utils.conn_db("system_config")
    conf = db.find_one({"_id": "cve_radar_config"})
    if not conf:
        conf = {"enabled": False, "interval": 6, "is_running": False}
        db.insert_one({"_id": "cve_radar_config", **conf})

    return utils.build_ret(ErrorMsg.Success, {
        "enabled": conf.get("enabled", False),
        "interval": conf.get("interval", 6),
        "is_running": conf.get("is_running", False)
    })


@github_threat_bp.route('/cve_config', methods=['POST'])
def set_cve_config():
    enabled, interval, err = _parse_radar_config_payload(request.get_json(silent=True))
    if err:
        return utils.build_ret(ErrorMsg.Error, {"error": err})
    utils.conn_db("system_config").update_one(
        {"_id": "cve_radar_config"},
        {"$set": {"enabled": enabled, "interval": interval}},
        upsert=True
    )
    return utils.build_ret(ErrorMsg.Success, {"msg": "保存成功"})


@github_threat_bp.route('/cve_run_once', methods=['POST'])
def run_cve_once():
    from app.tasks.github_threat_monitor import dispatch_threat_task
    try:
        success, msg = dispatch_threat_task("cve", force=True)
        if success:
            return utils.build_ret(ErrorMsg.Success, {"msg": msg, "is_running": True})
        else:
            return utils.build_ret(ErrorMsg.Error, {"msg": msg, "is_running": False})
    except Exception as e:
        utils.get_logger().error(f"Manual CVE dispatch error: {e}")
        return utils.build_ret(ErrorMsg.Error, {"msg": f"下发失败: {str(e)}"})


@github_threat_bp.route('/tools_config', methods=['GET'])
def get_tools_config():
    db = utils.conn_db("system_config")
    conf = db.find_one({"_id": "tools_radar_config"})
    if not conf:
        conf = {"enabled": False, "interval": 6, "is_running": False}
        db.insert_one({"_id": "tools_radar_config", **conf})

    return utils.build_ret(ErrorMsg.Success, {
        "enabled": conf.get("enabled", False),
        "interval": conf.get("interval", 6),
        "is_running": conf.get("is_running", False)
    })


@github_threat_bp.route('/tools_config', methods=['POST'])
def set_tools_config():
    enabled, interval, err = _parse_radar_config_payload(request.get_json(silent=True))
    if err:
        return utils.build_ret(ErrorMsg.Error, {"error": err})
    utils.conn_db("system_config").update_one(
        {"_id": "tools_radar_config"},
        {"$set": {"enabled": enabled, "interval": interval}},
        upsert=True
    )
    return utils.build_ret(ErrorMsg.Success, {"msg": "保存成功"})


@github_threat_bp.route('/tools_run_once', methods=['POST'])
def run_tools_once():
    from app.tasks.github_threat_monitor import dispatch_threat_task
    try:
        success, msg = dispatch_threat_task("tools", force=True)
        if success:
            return utils.build_ret(ErrorMsg.Success, {"msg": msg, "is_running": True})
        else:
            return utils.build_ret(ErrorMsg.Error, {"msg": msg, "is_running": False})
    except Exception as e:
        utils.get_logger().error(f"Manual Tools dispatch error: {e}")
        return utils.build_ret(ErrorMsg.Error, {"msg": f"下发失败: {str(e)}"})


@github_threat_bp.route('/hackers_config', methods=['GET'])
def get_hackers_config():
    db = utils.conn_db("system_config")
    conf = db.find_one({"_id": "hackers_radar_config"})
    if not conf:
        conf = {"enabled": False, "interval": 6, "is_running": False}
        db.insert_one({"_id": "hackers_radar_config", **conf})

    return utils.build_ret(ErrorMsg.Success, {
        "enabled": conf.get("enabled", False),
        "interval": conf.get("interval", 6),
        "is_running": conf.get("is_running", False)
    })


@github_threat_bp.route('/hackers_config', methods=['POST'])
def set_hackers_config():
    enabled, interval, err = _parse_radar_config_payload(request.get_json(silent=True))
    if err:
        return utils.build_ret(ErrorMsg.Error, {"error": err})
    utils.conn_db("system_config").update_one(
        {"_id": "hackers_radar_config"},
        {"$set": {"enabled": enabled, "interval": interval}},
        upsert=True
    )
    return utils.build_ret(ErrorMsg.Success, {"msg": "保存成功"})


@github_threat_bp.route('/hackers_run_once', methods=['POST'])
def run_hackers_once():
    from app.tasks.github_threat_monitor import dispatch_threat_task
    try:
        success, msg = dispatch_threat_task("hackers", force=True)
        if success:
            return utils.build_ret(ErrorMsg.Success, {"msg": msg, "is_running": True})
        else:
            return utils.build_ret(ErrorMsg.Error, {"msg": msg, "is_running": False})
    except Exception as e:
        utils.get_logger().error(f"Manual Hackers dispatch error: {e}")
        return utils.build_ret(ErrorMsg.Error, {"msg": f"下发失败: {str(e)}"})


@github_threat_bp.route('/token_status', methods=['GET'])
def get_token_status():
    token = getattr(Config, 'GITHUB_TOKEN', '')
    if not token:
        return utils.build_ret(ErrorMsg.Success, {"status": "missing", "msg": "未配置 Token"})

    try:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        res = utils.http_req(
            "https://api.github.com/rate_limit",
            headers=headers,
            timeout=(5, 5),
            proxy_domain="intel",
        )
        if not res:
            return utils.build_ret(ErrorMsg.Success, {"status": "error", "msg": "网络请求失败"})
        if res.status_code == 200:
            resources = res.json().get("resources", {})
            core = resources.get("core", {})
            search = resources.get("search", {})
            core_remaining = int(core.get("remaining", 0) or 0)
            core_limit = int(core.get("limit", 0) or 0)
            search_remaining = int(search.get("remaining", 0) or 0)
            search_limit = int(search.get("limit", 0) or 0)

            payload = {
                "core": {
                    "remaining": core_remaining,
                    "limit": core_limit,
                    "reset": core.get("reset", 0),
                },
                "search": {
                    "remaining": search_remaining,
                    "limit": search_limit,
                    "reset": search.get("reset", 0),
                },
            }
            if core_remaining <= 0 or (search_limit > 0 and search_remaining <= 0):
                return utils.build_ret(ErrorMsg.Success, {
                    "status": "rate_limited",
                    "msg": f"限流中 (Core: {core_remaining}, Search: {search_remaining})",
                    **payload,
                })
            return utils.build_ret(ErrorMsg.Success, {
                "status": "valid",
                "msg": f"生效中 (Core: {core_remaining}, Search: {search_remaining})",
                **payload,
            })
        elif res.status_code in (401, 403):
            return utils.build_ret(ErrorMsg.Success, {"status": "invalid", "msg": "Token 无效或已过期"})
        else:
            return utils.build_ret(ErrorMsg.Success, {"status": "error", "msg": f"API 响应异常 ({res.status_code})"})
    except Exception:
        return utils.build_ret(ErrorMsg.Success, {"status": "error", "msg": "网络请求失败"})
