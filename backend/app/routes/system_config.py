from flask_restx import Namespace, Resource, fields
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
    'celery_concurrency': fields.Integer(required=True, description='Celery并发数')
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
        celery_concurrency = get_performance_config()
        return {
            "code": 200,
            "message": "success",
            "data": {
                "celery_concurrency": celery_concurrency
            }
        }

    @auth
    @ns.expect(performance_model)
    def post(self):
        """
        更新性能配置
        """
        args = self.get_parser(performance_model).parse_args()
        celery_concurrency = args.get('celery_concurrency', 2)

        # 简单校验
        if celery_concurrency < 1:
            celery_concurrency = 1

        update_performance_config(celery_concurrency)

        return {
            "code": 200,
            "message": "性能配置更新成功，请手动重启Celery服务以生效"
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
            "email": {
                "host": Config.EMAIL_HOST,
                "port": Config.EMAIL_PORT,
                "username": Config.EMAIL_USERNAME,
                "password": Config.EMAIL_PASSWORD,
                "to": Config.EMAIL_TO
            },
            "query_plugin_config": Config.QUERY_PLUGIN_CONFIG
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
        if "fofa_max_page" in req_data: doc["fofa_max_page"] = int(req_data["fofa_max_page"])
        if "fofa_page_size" in req_data: doc["fofa_page_size"] = int(req_data["fofa_page_size"])
        if "github_token" in req_data: doc["github_token"] = req_data["github_token"]

        if "tyc_id" in req_data: doc["tyc_id"] = req_data["tyc_id"]
        if "tyc_token" in req_data: doc["tyc_token"] = req_data["tyc_token"]

        # 代理与并发
        if "proxy_url" in req_data: doc["proxy_url"] = req_data["proxy_url"]
        if "port_top_10" in req_data: doc["port_top_10"] = req_data["port_top_10"]
        if "domain_brute_concurrent" in req_data: doc["domain_brute_concurrent"] = int(req_data["domain_brute_concurrent"])
        if "alt_dns_concurrent" in req_data: doc["alt_dns_concurrent"] = int(req_data["alt_dns_concurrent"])

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
        if "email" in req_data:
            doc["email_host"] = req_data["email"].get("host")
            doc["email_port"] = req_data["email"].get("port")
            doc["email_username"] = req_data["email"].get("username")
            doc["email_password"] = req_data["email"].get("password")
            doc["email_to"] = req_data["email"].get("to")
        if "query_plugin_config" in req_data: doc["query_plugin_config"] = req_data["query_plugin_config"]

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
        from app.utils.push import dingding_send, feishu_send, wx_work_send, send_email
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

