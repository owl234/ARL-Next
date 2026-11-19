from bson import ObjectId
from flask_restx import fields, Namespace
from app import utils
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser
from app.modules import ErrorMsg
from app.helpers import submit_task_task, get_ip_domain_list, get_options_by_policy_id
from app.modules import TaskTag

# 建立“资产组域名”命名空间,用于管理确认的域名资产
ns = Namespace('asset_domain', description="资产组域名信息")

logger = get_logger()

# ==========================================
# 表单 1：搜索正式域名时可用的条件（带分页）
# ==========================================
base_search_fields = {
    'domain': fields.String(required=False, description="域名"),
    'record': fields.String(description="解析值"),
    'type': fields.String(description="解析类型"),
    'ips': fields.String(description="IP"),
    'source': fields.String(description="来源"),
    "task_id": fields.String(description="来源任务 ID"),
    "update_date__dgt": fields.String(description="更新时间大于"),
    "update_date__dlt": fields.String(description="更新时间小于"),
    'scope_id': fields.String(description="范围 ID")
}

# 合并分页排序基础字段
base_search_fields.update(base_query_fields)


# ==========================================
# 表单 2：手动添加新域名到资产组时，必须填写的字段
# ==========================================
add_domain_fields = ns.model('addAssetDomain',  {
    'domain': fields.String(required=True, description="域名"),
    'scope_id': fields.String(required=True, description="资产组范围ID"),
    'policy_id': fields.String(description="策略 ID"),
})


@ns.route('/')
class ARLAssetDomain(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    # ==========================================
    # 接口 A：查询资产组里的域名 (GET)
    # ==========================================
    @auth
    @ns.expect(parser)
    def get(self):
        """
        域名信息查询
        """
        args = self.parser.parse_args()
        # 一键完成翻译、查库、分页、返回
        data = self.build_data(args=args, collection='asset_domain')

        return data

    # ==========================================
    # 接口 B：手动添加新域名到资产组 (POST) - 【核心逻辑】
    # ==========================================
    @auth
    @ns.expect(add_domain_fields)
    def post(self):
        """
        添加域名到资产组中
        """
        args = self.parse_args(add_domain_fields)
        raw_domain = args.pop("domain")
        scope_id = args.pop("scope_id")
        policy_id = args.pop("policy_id")

        try:
            # 1. 文本处理：把用户填的一长串文本，提取成干净的域名列表
            _, domain_list = get_ip_domain_list(raw_domain)
        except Exception as e:
            return utils.build_ret(ErrorMsg.Error, {"error": str(e)})

        # 2. 校验资产组是否存在
        scope_data = utils.conn_db('asset_scope').find_one({"_id": ObjectId(scope_id)})
        if not scope_data:
            return utils.build_ret(ErrorMsg.NotFoundScopeID, {"scope_id": scope_id})

        # 兜底旧数据结构
        if "domain_array" not in scope_data:
            st = scope_data.get("scope_type")
            sa = scope_data.get("scope_array", [])
            scope_data["domain_array"] = sa if st == 'domain' else []

        if not scope_data.get("domain_array"):
            return utils.build_ret(ErrorMsg.Error, {"error": "该资产组不包含任何合法主域名，无法添加子域名"})

        domain_in_scope_list = []   # 用来装“已经存在”的域名
        add_domain_list = []      # 用来装“真正需要添加”的新域名

        # 4. 挨个审查用户提交的域名
        for domain in domain_list:
            # 【越权防御】：检查将要添加的 domain 是否从属于 domain_array 中的任何一个目标范围内
            if not utils.domain.is_in_scopes(domain, scope_data.get("domain_array", [])):
                return utils.build_ret(ErrorMsg.DomainNotFoundViaScope, {"domain": domain})

            # 查重：去数据库看看这个域名是不是已经在这个资产组里了
            domain_data = utils.conn_db("asset_domain").find_one({"domain": domain, "scope_id": scope_id})
            if domain_data:
                domain_in_scope_list.append(domain)
                continue    # 如果存在，记录下来并跳过

            # 如果是新的，放进待添加列表
            add_domain_list.append(domain)

        # 整理一份汇报数据给前端
        ret_data = {
            "domain": ",".join(add_domain_list),
            "scope_id": scope_id,
            "domain_in_scope": ",".join(domain_in_scope_list),
            "add_domain_len": len(add_domain_list)
        }

        # 如果发现全都是已经存在的域名，直接返回“未找到新域名”
        if len(add_domain_list) == 0:
            return utils.build_ret(ErrorMsg.DomainNotFoundNotInScope, ret_data)

        # 5. 【系统亮点：资产发现转任务】
        # ARL 不会直接把域名写进数据库！它会把这些新域名当做目标，发起一次新的扫描任务！
        target = " ".join(add_domain_list)
        name = "添加域名-{}".format(scope_data["name"]) # 自动生成一个任务名

        options = {
            'domain_brute': True,
            'domain_brute_type': 'test',
            'port_scan_type': 'top100',
            'port_scan': True,
            'service_detection': False,
            'service_brute': False,
            'os_detection': False,
            'site_identify': False,
            'site_capture': True,
            'file_leak': False,
            'alt_dns': False,
            'site_spider': False,
            'search_engines': False,
            'ssl_cert': False,
            'fofa_search': False,
            'dns_query_plugin': False,
            'related_scope_id': scope_id    # 关键：告诉任务，扫完后结果自动归档到这个资产组！
        }

        try:
            # 如果用户指定了扫描策略 (policy_id)
            if policy_id and len(policy_id) == 24:
                policy_options = get_options_by_policy_id(policy_id=policy_id, task_tag=TaskTag.TASK)
                if policy_options:
                    policy_options["related_scope_id"] = scope_id
                    options.update(policy_options)  # 用策略的高级配置覆盖掉默认的基础配置

            # 调用我们在 task.py 里熟悉的底层老大：派发任务给 Celery 工人！
            submit_task_task(target=target, name=name, options=options)
        except Exception as e:
            logger.exception(e)
            return utils.build_ret(ErrorMsg.Error, {"error": str(e)})

        return utils.build_ret(ErrorMsg.Success, ret_data)


# ==========================================
# 表单 3 与接口 C：删除资产组中的域名 (POST /delete/)
# ==========================================
delete_domain_fields = ns.model('deleteAssetDomain',  {
    '_id': fields.List(fields.String(required=True, description="数据_id"))
})


@ns.route('/delete/')
class DeleteARLAssetDomain(ARLResource):
    @auth
    @ns.expect(delete_domain_fields)
    def post(self):
        """
        删除资产组中的域名
        """
        args = self.parse_args(delete_domain_fields)
        id_list = args.pop('_id', "")
        # 遍历前端传来的 ID 列表，挨个去数据库里物理删除
        for _id in id_list:
            query = {'_id': ObjectId(_id)}
            utils.conn_db('asset_domain').delete_one(query)

        return utils.build_ret(ErrorMsg.Success, {'_id': id_list})


# ==========================================
# 接口 D：导出资产组域名 (GET /export/)
# ==========================================
@ns.route('/export/')
class ARLAssetDomainExport(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        资产组域名导出
        """
        args = self.parser.parse_args()
        # 复用强大的万能导出函数！
        response = self.send_export_file(args=args, _type="asset_domain")

        return response
