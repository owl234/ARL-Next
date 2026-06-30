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
