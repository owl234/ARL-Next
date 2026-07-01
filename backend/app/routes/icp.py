from flask_restx import Namespace, fields
from app.utils import get_logger, auth, build_ret, curr_date, conn_db
from app.modules import TaskStatus, ErrorMsg
from . import ARLResource, get_arl_parser, base_query_fields
from app import celerytask
import bson

ns = Namespace('icp', description="ICP 备案查询")
logger = get_logger()

# 基础搜索字段
base_search_icp_task_fields = {
    'name': fields.String(required=False, description="任务名"),
    'target': fields.String(description="公司名称"),
    'status': fields.String(description="任务状态"),
    'query_type': fields.String(description="查询类型"),
    '_id': fields.String(description="任务ID")
}
base_search_icp_task_fields.update(base_query_fields)
search_icp_task_fields = ns.model('SearchIcpTask', base_search_icp_task_fields)

# 新建任务参数
add_icp_task_fields = ns.model('AddIcpTask', {
    'name': fields.String(required=True, example="腾讯备案查询", description="任务名"),
    'target': fields.String(required=True, example="深圳市腾讯计算机系统有限公司", description="目标公司"),
    'query_type': fields.List(fields.String, required=True, example=["web", "app"], description="查询类型列表(web/app/mapp/kapp)")
})

@ns.route('/task')
class IcpTask(ARLResource):
    parser = get_arl_parser(search_icp_task_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        获取 ICP 任务列表
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='icp_task')
        return data

    @auth
    @ns.expect(add_icp_task_fields)
    def post(self):
        """
        新建 ICP 查询任务
        """
        args = self.parse_args(add_icp_task_fields)
        name = args.get('name')
        target = args.get('target')
        query_type = args.get('query_type')

        task_data = {
            "name": name,
            "target": target,
            "query_type": query_type,
            "status": TaskStatus.WAITING,
            "start_time": curr_date(),
            "end_time": "-",
            "statistic": {
                "asset_cnt": 0
            }
        }
        
        # 存入数据库
        conn = conn_db('icp_task')
        result = conn.insert_one(task_data)
        task_id = str(result.inserted_id)

        # 异步调度 celery
        options = {
            "task_id": task_id,
            "target": target,
            "query_type": query_type
        }
        
        # 将任务发给 celery
        celerytask.icp_query_task.delay(options=options)

        return build_ret(ErrorMsg.Success, {"task_id": task_id})


# 资产搜索字段
base_search_icp_asset_fields = {
    'task_id': fields.String(description="任务ID"),
    'unitName': fields.String(description="主办单位名称"),
    'domain': fields.String(description="域名"),
    'mainLicence': fields.String(description="主备案号"),
    'query_type': fields.String(description="查询类型"),
    '_id': fields.String(description="资产ID")
}
base_search_icp_asset_fields.update(base_query_fields)
search_icp_asset_fields = ns.model('SearchIcpAsset', base_search_icp_asset_fields)

@ns.route('/asset')
class IcpAsset(ARLResource):
    parser = get_arl_parser(search_icp_asset_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        获取 ICP 资产列表
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='icp_asset')
        return data


@ns.route('/stop/<string:task_id>')
class IcpTaskStop(ARLResource):
    @auth
    def get(self, task_id):
        """停止 ICP 任务 (单任务)"""
        try:
            query = {"_id": bson.ObjectId(task_id)}
            update = {"$set": {"status": TaskStatus.STOP, "end_time": curr_date()}}
            conn_db('icp_task').update_one(query, update)
            return build_ret(ErrorMsg.Success, {"task_id": task_id})
        except Exception as e:
            return build_ret(ErrorMsg.Error, {"error": str(e)})


@ns.route('/delete/<string:task_id>')
class IcpTaskDelete(ARLResource):
    @auth
    def get(self, task_id):
        """删除 ICP 任务 (单任务)"""
        try:
            # 删任务和资产
            query = {"_id": bson.ObjectId(task_id)}
            conn_db('icp_task').delete_one(query)
            conn_db('icp_asset').delete_many({"task_id": task_id})
            return build_ret(ErrorMsg.Success, {"task_id": task_id})
        except Exception as e:
            return build_ret(ErrorMsg.Error, {"error": str(e)})


@ns.route('/restart/<string:task_id>')
class IcpTaskRestart(ARLResource):
    @auth
    def get(self, task_id):
        """重启 ICP 任务 (单任务)"""
        try:
            task = conn_db('icp_task').find_one({"_id": bson.ObjectId(task_id)})
            if not task:
                return build_ret(ErrorMsg.NotFoundTask, {"task_id": task_id})
            
            # 删除旧资产
            conn_db('icp_asset').delete_many({"task_id": task_id})
            
            # 更新任务状态
            update = {
                "$set": {
                    "status": TaskStatus.WAITING, 
                    "start_time": curr_date(), 
                    "end_time": "-", 
                    "statistic": {"asset_cnt": 0},
                    "error_msg": ""
                }
            }
            conn_db('icp_task').update_one({"_id": bson.ObjectId(task_id)}, update)
            
            # 重新发起
            options = {
                "task_id": task_id,
                "target": task["target"],
                "query_type": task.get("query_type", ["web"])
            }
            celerytask.icp_query_task.delay(options=options)
            
            return build_ret(ErrorMsg.Success, {"task_id": task_id})
        except Exception as e:
            return build_ret(ErrorMsg.Error, {"error": str(e)})


from flask import make_response
import io
import csv

@ns.route('/export/<string:task_id>')
class IcpTaskExport(ARLResource):
    @auth
    def get(self, task_id):
        """导出 ICP 资产 (单任务)"""
        try:
            assets = list(conn_db('icp_asset').find({"task_id": task_id}))
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # 写表头
            writer.writerow(['主办单位名称', '单位性质', '主备案号', '域名', '网站名称', '服务许可', '更新时间', '查询类型'])
            
            for item in assets:
                writer.writerow([
                    item.get('unitName', ''),
                    item.get('natureName', ''),
                    item.get('mainLicence', ''),
                    item.get('domain', ''),
                    item.get('serviceName', ''),
                    item.get('serviceLicence', ''),
                    item.get('updateRecordTime', ''),
                    item.get('query_type', '')
                ])
                
            response = make_response(output.getvalue().encode('utf-8-sig'))
            response.headers["Content-Disposition"] = f"attachment; filename=icp_export_{task_id}.csv"
            response.headers["Content-type"] = "text/csv"
            return response
        except Exception as e:
            return build_ret(ErrorMsg.Error, {"error": str(e)})


@ns.route('/sync/<string:task_id>')
class IcpTaskSync(ARLResource):
    @auth
    def get(self, task_id):
        """将 ICP 任务中的网站域名同步至资产分组"""
        try:
            task = conn_db('icp_task').find_one({"_id": bson.ObjectId(task_id)})
            if not task:
                return build_ret(ErrorMsg.NotFoundTask, {"task_id": task_id})
            
            target_name = task.get('target', '未知公司')
            
            # 查出当前任务下所有 web 查询的资产 (只取网站)
            assets = list(conn_db('icp_asset').find({"task_id": task_id, "query_type": "web"}))
            domains = set()
            for asset in assets:
                d = asset.get('domain')
                if d and isinstance(d, str):
                    domains.add(d.strip())
            
            if not domains:
                return build_ret(ErrorMsg.Error, {"error": "未发现网站资产，无法同步"})
            
            # 查找是否已有同名的资产分组
            scope = conn_db('asset_scope').find_one({"name": target_name, "scope_type": "domain"})
            if scope:
                # 合并
                old_array = scope.get("scope_array", [])
                new_array = list(set(old_array) | domains)
                conn_db('asset_scope').update_one(
                    {"_id": scope["_id"]},
                    {"$set": {
                        "scope_array": new_array,
                        "scope": ",".join(new_array)
                    }}
                )
            else:
                # 新建
                new_array = list(domains)
                scope_data = {
                    "name": target_name,
                    "scope_type": "domain",
                    "scope": ",".join(new_array),
                    "scope_array": new_array,
                    "black_scope": "",
                    "black_scope_array": []
                }
                conn_db('asset_scope').insert_one(scope_data)
                
            return build_ret(ErrorMsg.Success, {"msg": f"成功同步了 {len(domains)} 个域名到资产分组 '{target_name}'"})
        except Exception as e:
            return build_ret(ErrorMsg.Error, {"error": str(e)})
