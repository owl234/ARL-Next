from flask_restx import Namespace, fields
from app.utils import get_logger, auth
from app import utils
from . import base_query_fields, ARLResource

ns = Namespace('syslog', description="系统与任务日志接口")
logger = get_logger()

# 定义允许前端通过 URL 传入的参数（包含在 reqparse 中校验并提取）
base_search_fields = {
    'task_id': fields.String(required=False, description="任务ID"),
    'level': fields.String(required=False, description="日志级别"),
    'title': fields.String(required=False, description="日志标题"),
    'message': fields.String(required=False, description="日志内容")
}
base_search_fields.update(base_query_fields)

@ns.route('/')
class SyslogList(ARLResource):
    @auth
    def get(self):
        """
        分页获取系统或任务的日志记录
        """
        # 1. 提取并校验参数
        args = self.parse_args(base_search_fields, location='args')
        
        # 2. 如果前端传了 order 排序为空，则默认用倒序
        if not args.get('order'):
            args['order'] = '-create_time'
            
        # 3. 利用 ARLResource 的底层能力，自动组装 MongoDB 查询条件并分页
        data = self.build_data(args=args, collection='syslog')
        
        return data
