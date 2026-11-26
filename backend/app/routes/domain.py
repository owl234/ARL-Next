from flask_restx import fields, Namespace
from app.utils import get_logger, auth
from app import utils
from app.modules import ErrorMsg
from . import base_query_fields, ARLResource, get_arl_parser

# 定义一个 Flask-RESTX 的命名空间（Namespace），相当于给 API 路由分了个组
# 这里的 'domain' 会成为 URL 的一部分（比如 /api/domain/），并在 Swagger 文档里显示为“域名信息”
ns = Namespace('domain', description="域名信息")

# 初始化日志记录器，方便记录系统运行状态或报错
logger = get_logger()

# 定义“基础搜索字段”字典。这其实是告诉 Swagger 文档和前端：
# “如果要来我这里查域名数据，你可以按以下这些条件来搜！”
base_search_fields = {
    'domain': fields.String(required=False, description="域名"),
    'record': fields.String(description="解析值"),
    'type': fields.String(description="解析类型"),
    'ips': fields.String(description="IP"),
    'source': fields.String(description="来源"),
    "save_date__dgt": fields.String(description="发现时间大于等于"),
    "save_date__dlt": fields.String(description="发现时间小于等于"),
    "task_id": fields.String(description="任务ID")
}

# 把全局通用的查询字段（比如 page 页码、size 每页几条数据）合并进我们刚刚定义的特定搜索字段里。
base_search_fields.update(base_query_fields)


# ==========================================
# 接口一：查询域名列表 (GET /api/domain/)
# ==========================================
@ns.route('/')  # 定义路由路径，结合之前的 ns 命名空间，实际路径是 /domain/
class ARLDomain(ARLResource):   # 继承自全能基类 ARLResource
    # 利用刚刚建好的 base_search_fields 字典，生成一个专门解析 URL 参数的解析器
    parser = get_arl_parser(base_search_fields, location='args')

    @auth   # 必须登录才能访问
    @ns.expect(parser)  # 告诉 Swagger 文档：我需要这些参数
    def get(self):
        """
        域名信息查询
        """
        # 1. 拿到前端传过来的查询参数（比如搜哪个域名、看第几页）
        args = self.parser.parse_args()

        # 2. 💡 联动第一阶段：召唤基类的 build_data 大法！
        # 直接告诉基类：“拿着这些条件，去 'domain' 这张表里帮我查数据，做分页，算总数！”
        data = self.build_data(args=args, collection='domain')

        # 3. 把打包好的完美数据返回给前端
        return data

# ==========================================
# 接口二：导出域名数据 (GET /api/domain/export/)
# ==========================================
@ns.route('/export/')
class ARLDomainExport(ARLResource):
    # 导出的查询条件和上面普通查询一模一样
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        域名导出
        """
        args = self.parser.parse_args()

        # 💡 联动第一阶段：召唤基类的 send_export_file 大法！
        # 直接告诉基类：“拿着这些条件，去把 'domain' 数据查出来，生成 Excel/CSV 文件发给用户！”
        response = self.send_export_file(args=args, _type="domain")

        return response

# ==========================================
# 接口三：删除域名数据 (POST /api/domain/delete/)
# ==========================================
# 定义一个表单模型：告诉前端，删除操作你需要传一个名叫 '_id' 的列表过来，里面装满字符串
delete_domain_fields = ns.model('deleteDomainFields',  {
    '_id': fields.List(fields.String(required=True, description="域名 _id")),
    'task_id': fields.String(required=False, description="可选任务 ID"),
    'source_type': fields.String(required=False, description="可选删除作用域：task | global")
})


@ns.route('/delete/')
class DeleteARLDomain(ARLResource):
    @auth
    @ns.expect(delete_domain_fields)
    def post(self):
        """
        删除域名（支持级联清理下级站点/L3 与孤儿 IP 回收）
        """
        args = self.parse_args(delete_domain_fields)
        from app.services.asset_cascade_service import handle_dimension_delete
        return handle_dimension_delete(
            "domain", False, args,
            build_ret_fn=utils.build_ret, success_msg=ErrorMsg.Success, db_getter=utils.conn_db,
        )
