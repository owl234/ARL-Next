from flask_restx import Namespace, fields
from app.utils.security_policy import get_security_policy, update_security_policy
from app.utils.performance_config import get_performance_config, update_performance_config
from . import ARLResource
from app.utils import auth

ns = Namespace("system_config", description="系统配置API")

# 定义输入模型用于Swagger和校验
security_policy_model = ns.model('SecurityPolicy', {
    'black_ips': fields.List(fields.String, required=True, description='IP黑名单(CIDR格式)'),
    'forbidden_domains': fields.List(fields.String, required=True, description='禁止扫描域名(后缀)')
})

performance_model = ns.model('Performance', {
    'celery_heavy_concurrency': fields.Integer(required=True, description='重任务Celery并发数'),
    'celery_light_concurrency': fields.Integer(required=True, description='轻任务Celery并发数'),
    'osint_concurrency': fields.Integer(required=True, description='OSINT任务并发数')
})

@ns.route('/security_policy')
class SecurityPolicy(ARLResource):
    @auth
    def get(self):
        """
        获取安全策略（IP黑名单与禁止域名）
        """
        black_ips, forbidden_domains = get_security_policy()
        return {
            "code": 200,
            "message": "success",
            "data": {
                "black_ips": black_ips,
                "forbidden_domains": forbidden_domains
            }
        }

    @auth
    @ns.expect(security_policy_model)
    def post(self):
        """
        更新安全策略（IP黑名单与禁止域名）
        """
        args = self.get_parser(security_policy_model).parse_args()
        black_ips = args.get('black_ips', [])
        forbidden_domains = args.get('forbidden_domains', [])

        # 简单过滤空值并去重
        black_ips = list(set([ip.strip() for ip in black_ips if ip.strip()]))
        forbidden_domains = list(set([domain.strip() for domain in forbidden_domains if domain.strip()]))

        update_security_policy(black_ips, forbidden_domains)

        return {
            "code": 200,
            "message": "安全策略更新成功"
        }

@ns.route('/performance')
class Performance(ARLResource):
    @auth
    def get(self):
        """
        获取性能配置
        """
        config = get_performance_config()
        return {
            "code": 200,
            "message": "success",
            "data": {
                "celery_heavy_concurrency": config.get("celery_heavy_concurrency", 2),
                "celery_light_concurrency": config.get("celery_light_concurrency", 3),
                "osint_concurrency": config.get("osint_concurrency", 1)
            }
        }

    @auth
    @ns.expect(performance_model)
    def post(self):
        """
        更新性能配置 (支持热扩缩容)
        """
        args = self.get_parser(performance_model).parse_args()
        new_heavy = args.get('celery_heavy_concurrency', 2)
        new_light = args.get('celery_light_concurrency', 3)
        new_osint = args.get('osint_concurrency', 1)

        if new_heavy < 1:
            new_heavy = 1
        if new_light < 1:
            new_light = 1
        if new_osint < 1:
            new_osint = 1

        old_config = get_performance_config()
        old_heavy = old_config.get("celery_heavy_concurrency", 2)
        old_light = old_config.get("celery_light_concurrency", 3)
        old_osint = old_config.get("osint_concurrency", 1)
        
        diff_heavy = new_heavy - old_heavy
        diff_light = new_light - old_light
        new_osint - old_osint

        update_performance_config(new_heavy, new_light, new_osint)

        msg = "性能配置更新成功。"
        
        # 热扩缩容重任务
        if diff_heavy != 0 or diff_light != 0:
            try:
                from app.celerytask import celery as celery_app
                active_nodes = celery_app.control.inspect().ping()
                if active_nodes:
                    heavy_nodes = [node for node in active_nodes.keys() if node.startswith('celery@arltask_heavy')]
                    light_nodes = [node for node in active_nodes.keys() if node.startswith('celery@arltask_light')]
                    
                    if heavy_nodes:
                        if diff_heavy > 0:
                            celery_app.control.broadcast('pool_grow', n=diff_heavy, destination=heavy_nodes)
                        elif diff_heavy < 0:
                            celery_app.control.broadcast('pool_shrink', n=abs(diff_heavy), destination=heavy_nodes)
                    
                    if light_nodes:
                        if diff_light > 0:
                            celery_app.control.broadcast('pool_grow', n=diff_light, destination=light_nodes)
                        elif diff_light < 0:
                            celery_app.control.broadcast('pool_shrink', n=abs(diff_light), destination=light_nodes)
                    
                    msg += " 并发进程热扩缩容指令已下发！"
                else:
                    msg += " Celery未响应，并发改变将在下次重启生效。"
            except Exception:
                msg += " 热扩缩容执行异常，请重启容器。"

        return {
            "code": 200,
            "message": msg
        }


@ns.route('/general')
class GeneralConfig(ARLResource):
    @auth
    def get(self):
        """
        获取常规全局配置 (混合数据库与yaml默认配置)
        """
        from app.config import Config

        data = {
            "celery_broker_url": Config.CELERY_BROKER_URL,
            "mongo_url": Config.MONGO_URL,
            "mongo_db": Config.MONGO_DB,
            "geoip_city": Config.GEOIP_CITY,
            "geoip_asn": Config.GEOIP_ASN,

            "fofa_key": Config.FOFA_KEY,
            "fofa_url": Config.FOFA_URL,
            "fofa_max_page": Config.FOFA_MAX_PAGE,
            "fofa_page_size": Config.FOFA_PAGE_SIZE,
            "so_search_cookie": Config.SO_SEARCH_COOKIE,
            "bing_search_cookie": Config.BING_SEARCH_COOKIE,
            "github_token": Config.GITHUB_TOKEN,

            "tyc_id": Config.TYC_ID,
            "tyc_token": Config.TYC_TOKEN,

            "proxy_url": Config.PROXY_URL,
            "port_top_10": Config.TOP_10,
            "domain_brute_concurrent": Config.DOMAIN_BRUTE_CONCURRENT,
            "alt_dns_concurrent": Config.ALT_DNS_CONCURRENT,

            "file_leak_dict": Config.FILE_LEAK_TOP_2k,
            "domain_dict": Config.DOMAIN_DICT_2W,

            "auth": Config.AUTH,
            "api_key": Config.API_KEY,

            "webhook_url": Config.WEB_HOOK_URL,
            "webhook_token": Config.WEB_HOOK_TOKEN,

            "dingding": {
                "secret": Config.DINGDING_SECRET,
                "access_token": Config.DINGDING_ACCESS_TOKEN
            },
            "feishu": {
                "webhook_url": Config.FEISHU_WEBHOOK,
                "secret": Config.FEISHU_SECRET
            },
            "wxwork": {
                "webhook_url": Config.WX_WORK_WEBHOOK
            },
            "telegram": {
                "bot_token": Config.TG_BOT_TOKEN,
                "chat_id": Config.TG_CHAT_ID
            },
            "email": {
                "host": Config.EMAIL_HOST,
                "port": Config.EMAIL_PORT,
                "username": Config.EMAIL_USERNAME,
                "password": Config.EMAIL_PASSWORD,
                "to": Config.EMAIL_TO
            },
            "query_plugin_config": Config.QUERY_PLUGIN_CONFIG,
            "push_options": Config.PUSH_OPTIONS
        }

        return {
            "code": 200,
            "message": "success",
            "data": data
        }

    @auth
    def post(self):
        """
        保存常规全局配置
        """
        from flask import request
        from app.utils.conn import conn_db
        from app.config import clear_system_config_cache

        req_data = request.json
        if not req_data:
            return {"code": 400, "message": "请求体为空"}

        doc = {}
        # 外部API
        if "fofa_key" in req_data: doc["fofa_key"] = req_data["fofa_key"]
        if "fofa_url" in req_data: doc["fofa_url"] = req_data["fofa_url"]
        if "fofa_max_page" in req_data and req_data["fofa_max_page"] is not None: doc["fofa_max_page"] = int(req_data["fofa_max_page"] or 0)
        if "fofa_page_size" in req_data and req_data["fofa_page_size"] is not None: doc["fofa_page_size"] = int(req_data["fofa_page_size"] or 0)
        
        if "so_search_cookie" in req_data: doc["so_search_cookie"] = req_data["so_search_cookie"]
        if "bing_search_cookie" in req_data: doc["bing_search_cookie"] = req_data["bing_search_cookie"]
        if "github_token" in req_data: doc["github_token"] = req_data["github_token"]

        if "tyc_id" in req_data: doc["tyc_id"] = req_data["tyc_id"]
        if "tyc_token" in req_data: doc["tyc_token"] = req_data["tyc_token"]

        # 代理与并发
        if "proxy_url" in req_data: doc["proxy_url"] = req_data["proxy_url"]
        if "port_top_10" in req_data: doc["port_top_10"] = req_data["port_top_10"]
        if "domain_brute_concurrent" in req_data and req_data["domain_brute_concurrent"] is not None: doc["domain_brute_concurrent"] = int(req_data["domain_brute_concurrent"] or 0)
        if "alt_dns_concurrent" in req_data and req_data["alt_dns_concurrent"] is not None: doc["alt_dns_concurrent"] = int(req_data["alt_dns_concurrent"] or 0)

        # 字典
        if "file_leak_dict" in req_data: doc["file_leak_dict"] = req_data["file_leak_dict"]
        if "domain_dict" in req_data: doc["domain_dict"] = req_data["domain_dict"]

        # 认证
        if "auth" in req_data: doc["auth"] = bool(req_data["auth"])
        if "api_key" in req_data: doc["api_key"] = req_data["api_key"]

        # Webhook
        if "webhook_url" in req_data: doc["webhook_url"] = req_data["webhook_url"]
        if "webhook_token" in req_data: doc["webhook_token"] = req_data["webhook_token"]

        # 消息推送
        if "dingding" in req_data:
            doc["dingding_secret"] = req_data["dingding"].get("secret")
            doc["dingding_access_token"] = req_data["dingding"].get("access_token")
        if "feishu" in req_data:
            doc["feishu_webhook"] = req_data["feishu"].get("webhook_url")
            doc["feishu_secret"] = req_data["feishu"].get("secret")
        if "wxwork" in req_data:
            doc["wx_work_webhook"] = req_data["wxwork"].get("webhook_url")
        if "telegram" in req_data:
            doc["tg_bot_token"] = req_data["telegram"].get("bot_token")
            doc["tg_chat_id"] = req_data["telegram"].get("chat_id")
        if "email" in req_data:
            doc["email_host"] = req_data["email"].get("host")
            doc["email_port"] = req_data["email"].get("port")
            doc["email_username"] = req_data["email"].get("username")
            doc["email_password"] = req_data["email"].get("password")
            doc["email_to"] = req_data["email"].get("to")
        if "query_plugin_config" in req_data: doc["query_plugin_config"] = req_data["query_plugin_config"]
        if "push_options" in req_data: doc["push_options"] = req_data["push_options"]

        conn_db('system_config').update_one(
            {"_id": "general_config"},
            {"$set": doc},
            upsert=True
        )

        # 清除缓存
        clear_system_config_cache()

        return {
            "code": 200,
            "message": "全局配置更新成功"
        }

@ns.route('/test_push')
class TestPush(ARLResource):
    @auth
    def post(self):
        """
        测试消息推送配置
        """
        from flask import request
        from app.utils.push import dingding_send, feishu_send, wx_work_send, send_email, telegram_send
        from app.utils import http_req

        req_data = request.json
        if not req_data:
            return {"code": 400, "message": "请求体为空"}

        push_type = req_data.get("push_type")
        config = req_data.get("config", {})
        
        test_msg = "*【ARL-Next 系统通知】这是一条测试消息，您的推送配置一切正常。*"
        test_html = f"<div><b>【ARL-Next 系统通知】</b>这是一条测试消息，您的推送配置一切正常。</div>"

        try:
            if push_type == "dingding":
                access_token = config.get("access_token")
                secret = config.get("secret")
                if not access_token or not secret:
                    return {"code": 400, "message": "钉钉测试失败：Token 或 Secret 不能为空"}
                res = dingding_send(msg=test_msg, access_token=access_token, secret=secret, msgtype="markdown")
                if res.get("errcode") != 0:
                    return {"code": 500, "message": f"钉钉推送失败: {res}"}
                return {"code": 200, "message": "钉钉测试推送成功"}

            elif push_type == "feishu":
                webhook_url = config.get("webhook_url")
                secret = config.get("secret")
                if not webhook_url or not secret:
                    return {"code": 400, "message": "飞书测试失败：Webhook URL 或 Secret 不能为空"}
                res = feishu_send(msg=test_msg, webhook_url=webhook_url, secret=secret)
                if res.get("code") != 0:
                    return {"code": 500, "message": f"飞书推送失败: {res}"}
                return {"code": 200, "message": "飞书测试推送成功"}

            elif push_type == "wxwork":
                webhook_url = config.get("webhook_url")
                if not webhook_url:
                    return {"code": 400, "message": "企业微信测试失败：Webhook URL 不能为空"}
                res = wx_work_send(msg=test_msg, webhook_url=webhook_url)
                if res.get("errcode") != 0:
                    return {"code": 500, "message": f"企业微信推送失败: {res}"}
                return {"code": 200, "message": "企业微信测试推送成功"}
            elif push_type == "telegram":
                bot_token = config.get("bot_token")
                chat_id = config.get("chat_id")
                if not bot_token or not chat_id:
                    return {"code": 400, "message": "Telegram 测试失败：Bot Token 或 Chat ID 不能为空"}
                res = telegram_send(msg=test_msg, bot_token=bot_token, chat_id=chat_id)
                if not res.get("ok"):
                    return {"code": 500, "message": f"Telegram 推送失败: {res}"}
                return {"code": 200, "message": "Telegram 测试推送成功"}

            elif push_type == "email":
                host = config.get("host")
                port = config.get("port")
                username = config.get("username")
                password = config.get("password")
                to = config.get("to")
                if not all([host, port, username, password, to]):
                    return {"code": 400, "message": "邮件测试失败：所有邮件配置字段均不能为空"}
                try:
                    port = int(port)
                except ValueError:
                    return {"code": 400, "message": "邮件测试失败：端口必须为数字"}
                
                send_email(host=host, port=port, mail=username, password=password, to=to, title="[ARL-Next] 邮件测试推送", html=test_html)
                return {"code": 200, "message": "邮件测试推送成功"}

            elif push_type == "webhook":
                webhook_url = config.get("webhook_url")
                webhook_token = config.get("webhook_token")
                if not webhook_url:
                    return {"code": 400, "message": "Webhook 测试失败：回调 URL 不能为空"}
                
                headers = {}
                if webhook_token:
                    headers["Token"] = webhook_token
                
                payload = {
                    "type": "test_push",
                    "message": "这是一条 ARL-Next 系统的 Webhook 测试数据",
                    "timestamp": __import__('time').time()
                }
                conn = http_req(webhook_url, method='post', json=payload, headers=headers, timeout=10)
                if conn.status_code >= 400:
                    return {"code": 500, "message": f"Webhook 请求失败，状态码: {conn.status_code}, 响应: {conn.text[:200]}"}
                return {"code": 200, "message": "Webhook 测试回调成功"}
            
            else:
                return {"code": 400, "message": "不支持的测试推送类型"}

        except Exception as e:
            return {"code": 500, "message": f"测试推送过程中发生异常: {str(e)}"}

import os
import re
import time
import requests
from flask import request as flask_req

_UPDATE_CACHE = {
    "timestamp": 0,
    "data": None
}

def get_local_version_str() -> str:
    """读取本地版本号"""
    candidates = [
        '/code/version.txt',
        'version.txt',
        os.path.join(os.path.dirname(__file__), '../../../version.txt')
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    v = f.read().strip()
                    if v:
                        return v
            except Exception:
                pass
    return '未知版本'

def get_local_changelog_section(tag: str) -> str:
    """从本地 CHANGELOG.md 中提取指定版本的更新说明"""
    candidates = [
        '/code/CHANGELOG.md',
        'CHANGELOG.md',
        os.path.join(os.path.dirname(__file__), '../../../CHANGELOG.md')
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    content = f.read()
                pattern = rf'##\s*\[?{re.escape(tag)}\]?.*?\n(.*?)(?=\n##\s*\[?v|\Z)'
                match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
                if match:
                    notes = match.group(1).strip()
                    return re.sub(r'\n---+\s*$', '', notes).strip()
            except Exception:
                pass
    return ''

def is_version_greater(v1: str, v2: str) -> bool:
    """比较版本号 v1 是否大于 v2 (支持 v1.2.0-fix1 等格式)"""
    if not v1 or not v2 or v1 == '未知版本' or v2 == '未知版本':
        return False
    
    clean1 = v1.lstrip('v').strip()
    clean2 = v2.lstrip('v').strip()
    
    base1, *suffix1 = clean1.split('-', 1)
    base2, *suffix2 = clean2.split('-', 1)
    
    parts1 = [int(x) for x in re.findall(r'\d+', base1)]
    parts2 = [int(x) for x in re.findall(r'\d+', base2)]
    
    for i in range(max(len(parts1), len(parts2))):
        n1 = parts1[i] if i < len(parts1) else 0
        n2 = parts2[i] if i < len(parts2) else 0
        if n1 > n2:
            return True
        if n1 < n2:
            return False
            
    s1 = suffix1[0] if suffix1 else ''
    s2 = suffix2[0] if suffix2 else ''
    
    if s1 and not s2:
        return True
    if not s1 and s2:
        return False
    if s1 and s2:
        nums1 = [int(x) for x in re.findall(r'\d+', s1)]
        nums2 = [int(x) for x in re.findall(r'\d+', s2)]
        num1 = nums1[0] if nums1 else 0
        num2 = nums2[0] if nums2 else 0
        if num1 != num2:
            return num1 > num2
        return s1 > s2
    return False

@ns.route('/local_version')
class LocalVersion(ARLResource):
    @auth
    def get(self):
        """
        获取当前本地版本号（通过读取版本文件）
        """
        version = get_local_version_str()
        return {"code": 200, "message": "success", "data": {"version": version}}

@ns.route('/check_update')
class CheckUpdate(ARLResource):
    @auth
    def get(self):
        """
        检查系统版本更新与获取更新日志（带内存缓存与高可用兜底）
        """
        global _UPDATE_CACHE
        local_v = get_local_version_str()
        force_refresh = flask_req.args.get('refresh', '').lower() in ('1', 'true')
        now = time.time()
        
        # 1. 检查缓存 (1小时有效)
        if not force_refresh and _UPDATE_CACHE["data"] and (now - _UPDATE_CACHE["timestamp"] < 3600):
            cached_data = _UPDATE_CACHE["data"].copy()
            cached_data["local_version"] = local_v
            cached_data["has_new_version"] = is_version_greater(cached_data.get("remote_version", ""), local_v)
            cached_data["is_cached"] = True
            return {"code": 200, "message": "success", "data": cached_data}
            
        remote_v = None
        release_notes = ""
        html_url = "https://github.com/owl234/ARL-Next"
        published_at = ""
        is_offline = False
        
        headers = {
            "User-Agent": "ARL-Next-Server",
            "Accept": "application/vnd.github.v3+json"
        }
        
        # 2. 尝试从 GitHub Releases 获取最新正式发版
        try:
            resp = requests.get("https://api.github.com/repos/owl234/ARL-Next/releases/latest", headers=headers, timeout=4)
            if resp.status_code == 200:
                rel_data = resp.json()
                remote_v = rel_data.get("tag_name")
                release_notes = rel_data.get("body", "")
                html_url = rel_data.get("html_url", html_url)
                published_at = rel_data.get("published_at", "")
        except Exception:
            pass
            
        # 3. 如果 Releases 为空，回退尝试从 Tags 列表提取
        if not remote_v:
            try:
                tag_resp = requests.get("https://api.github.com/repos/owl234/ARL-Next/tags", headers=headers, timeout=4)
                if tag_resp.status_code == 200:
                    tags = tag_resp.json()
                    if tags and isinstance(tags, list):
                        valid_tags = [t.get("name") for t in tags if t.get("name")]
                        if valid_tags:
                            # 降序排列找到最高版本
                            valid_tags.sort(key=lambda t: [int(x) for x in re.findall(r'\d+', t.split('-')[0])], reverse=True)
                            remote_v = valid_tags[0]
            except Exception:
                pass
                
        # 4. 如果未能获取到 release_notes，尝试从本地 CHANGELOG.md 中匹配
        target_tag_for_notes = remote_v or local_v
        if not release_notes and target_tag_for_notes:
            release_notes = get_local_changelog_section(target_tag_for_notes)
            
        # 5. 如果 GitHub 完全不可达，进行优雅本地兜底
        if not remote_v:
            remote_v = local_v
            is_offline = True
            if not release_notes:
                release_notes = get_local_changelog_section(local_v)
                
        has_new = is_version_greater(remote_v, local_v)
        
        result_data = {
            "local_version": local_v,
            "remote_version": remote_v,
            "has_new_version": has_new,
            "release_notes": release_notes,
            "html_url": html_url,
            "published_at": published_at,
            "is_cached": False,
            "is_offline": is_offline
        }
        
        # 写入缓存
        _UPDATE_CACHE["timestamp"] = now
        _UPDATE_CACHE["data"] = result_data
        
        return {"code": 200, "message": "success", "data": result_data}

@ns.route('/request_update_token')
class RequestUpdateToken(ARLResource):
    @auth
    def post(self):
        """
        请求一个用于进行系统更新的一次性 Token
        """
        import uuid
        token = str(uuid.uuid4()).replace('-', '')
        
        try:
            with open('/tmp/arl_update_token', 'w') as f:
                f.write(token)
            return {"code": 200, "message": "Token 生成成功", "data": {"token": token}}
        except Exception as e:
            return {"code": 500, "message": f"生成更新 Token 失败: {str(e)}"}


@ns.route('/running_task_count')
class RunningTaskCount(ARLResource):
    @auth
    def get(self):
        """
        获取当前系统中正在执行的扫描任务数量（用于更新前置预检与任务告警）
        """
        from app.modules import TaskStatus
        from app.utils import conn_db
        non_running = [TaskStatus.DONE, TaskStatus.WAITING, TaskStatus.ERROR, TaskStatus.STOP]
        count = conn_db('task').count_documents({"status": {"$nin": non_running}})
        return {"code": 200, "message": "success", "data": {"running_count": count}}



