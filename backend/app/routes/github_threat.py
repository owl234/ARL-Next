from flask import Blueprint, request, jsonify
from app import utils
from app.config import Config
from app.modules import ErrorMsg

github_threat_bp = Blueprint('github_threat', __name__)


@github_threat_bp.before_request
def _require_auth():
    """本 Blueprint 内所有端点(含删除、改配置、触发扫描)均需登录态。

    其余 /api/* 路由均由 @auth 装饰器逐个鉴权，本组通过 register_blueprint 注册，
    缺少统一校验，导致匿名用户可清空监控目标、篡改监控配置并触发外网扫描。
    """
    if Config.AUTH and not utils.user_login_header():
        return jsonify({"message": "not login", "code": 401, "data": {}}), 401

@github_threat_bp.route('/tools_target', methods=['GET'])
def get_tools_target():
    data = list(utils.conn_db("github_tools_target").find({}, {"_id": 0}))
    return utils.build_ret(ErrorMsg.Success, data)

@github_threat_bp.route('/tools_target', methods=['POST'])
def add_tools_target():
    req_data = request.json
    repo_url = req_data.get('repo_url', '').strip()
    
    # 自动转换常见的 GitHub 链接格式为 API 格式
    if "github.com" in repo_url and "api.github.com" not in repo_url:
        repo_url = repo_url.replace("https://github.com/", "https://api.github.com/repos/")
        repo_url = repo_url.replace("http://github.com/", "https://api.github.com/repos/")
    
    if not repo_url or "api.github.com/repos" not in repo_url:
        return utils.build_ret(ErrorMsg.Error, {"error": "请输入正确的 Github 地址或 API 格式，如 https://github.com/chaitin/xray"})
        
    db = utils.conn_db("github_tools_target")
    if db.find_one({"repo_url": repo_url}):
        return utils.build_ret(ErrorMsg.Error, {"error": "该工具已被监控"})
        
    db.insert_one({
        "repo_url": repo_url,
        "last_tag": "",
        "last_commit_time": "",
        "insert_time": utils.curr_date()
    })
    return utils.build_ret(ErrorMsg.Success, {"msg": "添加成功"})

@github_threat_bp.route('/tools_target/delete', methods=['POST'])
def delete_tools_target():
    repo_urls = request.json.get('repo_urls')
    if isinstance(repo_urls, list):
        utils.conn_db("github_tools_target").delete_many({"repo_url": {"$in": repo_urls}})
    else:
        repo_url = request.json.get('repo_url')
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
    data = list(utils.conn_db("github_hackers_history").find({}, {"_id": 0}).sort("insert_time", -1))
    return utils.build_ret(ErrorMsg.Success, data)

@github_threat_bp.route('/hackers_target', methods=['POST'])
def add_hackers_target():
    github_id = request.json.get('github_id', '').strip()
    if not github_id:
        return utils.build_ret(ErrorMsg.Error, {"error": "请输入大牛的 Github ID"})
        
    db = utils.conn_db("github_hackers_target")
    if db.find_one({"github_id": github_id}):
        return utils.build_ret(ErrorMsg.Error, {"error": "该大佬已被监控"})
        
    db.insert_one({
        "github_id": github_id,
        "insert_time": utils.curr_date()
    })
    return utils.build_ret(ErrorMsg.Success, {"msg": "添加成功"})

@github_threat_bp.route('/hackers_target/delete', methods=['POST'])
def delete_hackers_target():
    github_ids = request.json.get('github_ids')
    if isinstance(github_ids, list):
        utils.conn_db("github_hackers_target").delete_many({"github_id": {"$in": github_ids}})
    else:
        github_id = request.json.get('github_id')
        utils.conn_db("github_hackers_target").delete_one({"github_id": github_id})
    return utils.build_ret(ErrorMsg.Success, {"msg": "删除成功"})

@github_threat_bp.route('/cve_history', methods=['GET'])
def get_cve_history():
    # 获取最新的 100 条 CVE 抓取记录，按时间倒序
    data = list(utils.conn_db("github_cve_history").find({}, {"_id": 0}).sort("insert_time", -1).limit(100))
    return utils.build_ret(ErrorMsg.Success, data)

@github_threat_bp.route('/cve_history/delete', methods=['POST'])
def delete_cve_history():
    cve_names = request.json.get('cve_names')
    if isinstance(cve_names, list):
        utils.conn_db("github_cve_history").delete_many({"cve_name": {"$in": cve_names}})
    else:
        cve_name = request.json.get('cve_name')
        utils.conn_db("github_cve_history").delete_one({"cve_name": cve_name})
    return utils.build_ret(ErrorMsg.Success, {"msg": "删除成功"})


@github_threat_bp.route('/cve_config', methods=['GET'])
def get_cve_config():
    db = utils.conn_db("system_config")
    conf = db.find_one({"_id": "cve_radar_config"})
    if not conf:
        conf = {"enabled": False, "interval": 6}
        db.insert_one({"_id": "cve_radar_config", **conf})
    
    return utils.build_ret(ErrorMsg.Success, {"enabled": conf.get("enabled", False), "interval": conf.get("interval", 6)})

@github_threat_bp.route('/cve_config', methods=['POST'])
def set_cve_config():
    enabled = request.json.get('enabled', False)
    interval = request.json.get('interval', 6)
    utils.conn_db("system_config").update_one(
        {"_id": "cve_radar_config"},
        {"$set": {"enabled": enabled, "interval": interval}},
        upsert=True
    )
    return utils.build_ret(ErrorMsg.Success, {"msg": "保存成功"})

@github_threat_bp.route('/cve_run_once', methods=['POST'])
def run_cve_once():
    from app.tasks.github_threat_monitor import GithubCveMonitorTask
    try:
        GithubCveMonitorTask().run()
    except Exception as e:
        utils.get_logger().error(f"Manual CVE run error: {e}")
        return utils.build_ret(ErrorMsg.Error, {"msg": f"扫描失败: {str(e)}"})
    return utils.build_ret(ErrorMsg.Success, {"msg": "扫描完成！"})

@github_threat_bp.route('/tools_config', methods=['GET'])
def get_tools_config():
    db = utils.conn_db("system_config")
    conf = db.find_one({"_id": "tools_radar_config"})
    if not conf:
        conf = {"enabled": False, "interval": 6}
        db.insert_one({"_id": "tools_radar_config", **conf})
    
    return utils.build_ret(ErrorMsg.Success, {"enabled": conf.get("enabled", False), "interval": conf.get("interval", 6)})

@github_threat_bp.route('/tools_config', methods=['POST'])
def set_tools_config():
    enabled = request.json.get('enabled', False)
    interval = request.json.get('interval', 6)
    utils.conn_db("system_config").update_one(
        {"_id": "tools_radar_config"},
        {"$set": {"enabled": enabled, "interval": interval}},
        upsert=True
    )
    return utils.build_ret(ErrorMsg.Success, {"msg": "保存成功"})

@github_threat_bp.route('/tools_run_once', methods=['POST'])
def run_tools_once():
    from app.tasks.github_threat_monitor import GithubToolsMonitorTask
    try:
        GithubToolsMonitorTask().run()
    except Exception as e:
        utils.get_logger().error(f"Manual Tools run error: {e}")
        return utils.build_ret(ErrorMsg.Error, {"msg": f"扫描失败: {str(e)}"})
    return utils.build_ret(ErrorMsg.Success, {"msg": "扫描完成！"})

@github_threat_bp.route('/hackers_config', methods=['GET'])
def get_hackers_config():
    db = utils.conn_db("system_config")
    conf = db.find_one({"_id": "hackers_radar_config"})
    if not conf:
        conf = {"enabled": False, "interval": 6}
        db.insert_one({"_id": "hackers_radar_config", **conf})
    
    return utils.build_ret(ErrorMsg.Success, {"enabled": conf.get("enabled", False), "interval": conf.get("interval", 6)})

@github_threat_bp.route('/hackers_config', methods=['POST'])
def set_hackers_config():
    enabled = request.json.get('enabled', False)
    interval = request.json.get('interval', 6)
    utils.conn_db("system_config").update_one(
        {"_id": "hackers_radar_config"},
        {"$set": {"enabled": enabled, "interval": interval}},
        upsert=True
    )
    return utils.build_ret(ErrorMsg.Success, {"msg": "保存成功"})

@github_threat_bp.route('/hackers_run_once', methods=['POST'])
def run_hackers_once():
    from app.tasks.github_threat_monitor import GithubHackersMonitorTask
    try:
        GithubHackersMonitorTask().run()
    except Exception as e:
        utils.get_logger().error(f"Manual Hackers run error: {e}")
        return utils.build_ret(ErrorMsg.Error, {"msg": f"扫描失败: {str(e)}"})
    return utils.build_ret(ErrorMsg.Success, {"msg": "扫描完成！"})


@github_threat_bp.route('/token_status', methods=['GET'])
def get_token_status():
    from app.config import Config
    token = getattr(Config, 'GITHUB_TOKEN', '')
    if not token:
        return utils.build_ret(ErrorMsg.Success, {"status": "missing", "msg": "未配置 Token"})
        
    import requests
    try:
        headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        res = requests.get("https://api.github.com/rate_limit", headers=headers, timeout=5)
        if res.status_code == 200:
            rate = res.json().get("resources", {}).get("core", {})
            remaining = rate.get("remaining", 0)
            return utils.build_ret(ErrorMsg.Success, {"status": "valid", "msg": f"生效中 (剩余额度: {remaining})"})
        else:
            return utils.build_ret(ErrorMsg.Success, {"status": "invalid", "msg": "Token 无效或已过期"})
    except Exception:
        return utils.build_ret(ErrorMsg.Success, {"status": "error", "msg": f"网络请求失败"})
