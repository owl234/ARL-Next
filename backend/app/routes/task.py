import re
import bson
from flask_restx import Resource, Api, reqparse, fields, Namespace
from bson import ObjectId
from app import celerytask
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser, conn
from app import utils
from app.modules import TaskStatus, ErrorMsg, TaskSyncStatus, CeleryAction, TaskTag, TaskType
from app.helpers import get_options_by_policy_id, submit_task_task,\
    submit_risk_cruising, get_scope_by_scope_id, check_target_in_scope
from app.helpers.task import get_task_data, restart_task


# 1. 成立“任务部门”：在 API 中划分出一个独立的命名空间 (Namespace)，
# 以后所有 /api/task/ 开头的接口都归这个部门管。
ns = Namespace('task', description="资产发现任务信息")


# 获取日志记录器，用于在控制台或文件里打印运行日志（比如报错信息）
logger = get_logger()


# ==========================================
# 场景 A：前端想要“搜索/查询”任务时，允许传的参数清单
# ==========================================
base_search_task_fields = {
    'name': fields.String(required=False, description="任务名"),
    'target': fields.String(description="任务目标"),
    'status': fields.String(description="任务状态"),
    '_id': fields.String(description="任务ID"),
    'task_tag': fields.String(description="监控任务和侦查任务tag"),

    # 下面是一大堆开关选项，支持按“是否开启了某个功能”来搜索任务
    'options.domain_brute': fields.Boolean(description="是否开启域名爆破"),
    'options.domain_brute_type': fields.String(description="域名爆破类型"),
    'options.port_scan_type': fields.Boolean(description="端口扫描类型"),
    'options.port_scan': fields.Boolean(description="是否的端口扫描"),
    'options.service_detection': fields.Boolean(description="是否开启服务识别"),
    'options.service_brute': fields.Boolean(description="是否开启服务弱口令爆破"),
    'options.os_detection': fields.Boolean(description="是否开启操作系统识别"),
    'options.site_identify': fields.Boolean(description="是否开启站点识别"),
    'options.file_leak': fields.Boolean(description="是否开启文件泄露扫描"),
    'options.alt_dns': fields.Boolean(description="是否开启DNS字典智能生成"),
    'options.search_engines': fields.Boolean(description="是否开启搜索引擎调用"),
    'options.site_spider': fields.Boolean(description="是否开启站点爬虫"),
    'options.arl_search': fields.Boolean(description="是否开启 ARL 历史查询"),
    'options.dns_query_plugin': fields.Boolean(description="是否开启域名插件查询"),
    'options.skip_scan_cdn_ip': fields.Boolean(description="是否跳过CDN IP端口扫描"),
    'options.nuclei_scan': fields.Boolean(description="是否开启nuclei 扫描"),
    'options.findvhost': fields.Boolean(description="是否开启Host碰撞检测"),
    'options.web_info_hunter': fields.Boolean(description="是否开启 webInfoHunter"),
    'options.npoc_service_detection': fields.Boolean(description="是否开启服务(python)识别"),

    # 翻译官(build_db_query)”,这里的后缀就是给它看的！
    'statistic.site_cnt': fields.Integer(description="站点数量等于"),
    'statistic.site_cnt__gt': fields.Integer(description="站点数量大于"),
    'statistic.site_cnt__lt': fields.Integer(description="站点数量小于"),
    'statistic.domain_cnt': fields.Integer(description="域名数量等于"),
    'statistic.domain_cnt__gt': fields.Integer(description="域名数量大于"),
    'statistic.domain_cnt__lt': fields.Integer(description="域名数量小于"),
    'statistic.wih_cnt': fields.Integer(description="WIH 数量等于"),
    'statistic.wih_cnt__gt': fields.Integer(description="WIH 数量大于"),
    'statistic.wih_cnt__lt': fields.Integer(description="WIH 数量小于"),
}


# 基础分页排序参数 (page, size, order)
# 直接合并（覆盖式合并）到搜索清单里！这样前端既能按名字搜，也能顺便分页了。
base_search_task_fields.update(base_query_fields) # 覆盖式合并

# 将普通的 Python 字典，正式注册为 Flask-RESTX 的“模型(Model)”，命名为 'SearchTask'。
# 注册后，系统会自动帮你生成漂亮的 Swagger 接口文档！
search_task_fields = ns.model('SearchTask', base_search_task_fields) #创建searchtask命名空间



# ==========================================
# 场景 B：前端想要“新建(下发)”任务时，必须传的参数清单
# ==========================================
add_task_fields = ns.model('AddTask', { # 创建添加任务命名空间。
    # 新建任务时，名字和目标是必须填写的 (required=True)
    'name': fields.String(required=True, example="task name", description="任务名"),
    'target': fields.String(required=True, example="www.freebuf.com", description="目标"),

    # 下面全是各种扫描策略的开关选项，example 代表在接口文档里显示的默认测试值
    "domain_brute": fields.Boolean(example=True),
    'domain_brute_type': fields.String(example="test"),
    "port_scan_type": fields.String(example="test", description="端口扫描类型"),
    "port_scan": fields.Boolean(example=True),
    "service_detection": fields.Boolean(example=False),
    "service_brute": fields.Boolean(example=False),
    "os_detection": fields.Boolean(example=False),
    "site_identify": fields.Boolean(example=False),
    "site_capture": fields.Boolean(example=False),
    "file_leak": fields.Boolean(example=False),
    "search_engines": fields.Boolean(example=False),
    "site_spider": fields.Boolean(example=False),
    "arl_search": fields.Boolean(example=False),
    "alt_dns": fields.Boolean(example=False),
    "ssl_cert": fields.Boolean(example=False),
    "dns_query_plugin": fields.Boolean(example=False, default=False),
    "skip_scan_cdn_ip": fields.Boolean(example=False, default=False),
    "nuclei_scan": fields.Boolean(description="nuclei 扫描", example=False, default=False),
    "findvhost": fields.Boolean(example=False, default=False),
    "web_info_hunter": fields.Boolean(example=False, default=False, description="WEB JS 中的信息收集"),
    "npoc_service_detection": fields.Boolean(example=False, default=False, description="服务(python)识别"),
})


# 将这个类绑定到 /api/task/ 根路径上
@ns.route('/')
class ARLTask(ARLResource): # 继承我们在阶段一拆解过的“大基类” ARLResource

    # 提前准备好 GET 请求用的“查询参数解析器”
    parser = get_arl_parser(search_task_fields, location='args')

    # ==========================================
    # GET 接口：负责分页查询和展示任务列表
    # ==========================================
    @auth  # 安全校验：必须带有正确的 Token 才能访问这个接口
    @ns.expect(parser)  # 告诉 Swagger 文档：调用这个接口需要带上 parser 里定义的那些参数
    def get(self):
        """
        任务信息查询
        """
        # 1. 提取参数：获取前端传来的页码、过滤条件（比如任务状态、任务名字）
        args = self.parser.parse_args()

        # 2. 一键查库：调用基类强大的 build_data 方法，
        # 自动完成“翻译Mongo语句、分页、查 task 表、包装”一条龙服务！
        data = self.build_data(args=args, collection='task')

        # 3. 自愈补全：如果任务缺失统计数据（例如异常退出的任务），则实时计算并自动写回数据库
        from bson import ObjectId
        for item in data.get("items", []):
            stat = item.get("statistic")
            if not stat or not isinstance(stat, dict) or "site_cnt" not in stat:
                task_id = item.get("_id")
                if task_id:
                    try:
                        computed_stat = utils.arl.task_statistic(task_id)
                        item["statistic"] = computed_stat
                        # 自动修复写回数据库
                        utils.conn_db('task').update_one({"_id": ObjectId(task_id)}, {"$set": {"statistic": computed_stat}})
                    except Exception as e:
                        logger.error(f"Failed to auto-heal task statistic for {task_id}: {e}")

        # 4. 直接把查到的标准格式数据返回给前端
        return data


    # ==========================================
    # POST 接口：负责接收参数并下发新的侦察任务
    # ==========================================
    @auth
    @ns.expect(add_task_fields) # 告诉前端：发 POST 请求必须按 add_task_fields 的格式传 JSON
    def post(self):
        """
        任务提交
        """

        # 1. 解析前端传来的 JSON 表单数据
        args = self.parse_args(add_task_fields)

        # 2. 分离核心参数：用 pop 把任务名和目标单独拿出来，
        #    这样 args 字典里剩下的就全是纯粹的“扫描选项(options)”了（比如 port_scan: True）
        name = args.pop('name')
        target = args.pop('target')

        try:
            # 3. 核心业务逻辑：调用助手函数 submit_task_task
            #    (这个函数内部会把任务存进数据库，并交给 Celery 异步执行)
            task_data_list = submit_task_task(target=target, name=name, options=args)
        except Exception as e:
            # 【安全防御】：如果下发任务时内部报错了，记录日志，并友好地告诉前端“出错了”
            logger.exception(e)
            return utils.build_ret(ErrorMsg.Error, {"error": str(e)})

        # 4. 如果目标解析出来是空的（比如传了个无效的域名），拦截并报错
        if not task_data_list:
            return utils.build_ret(ErrorMsg.TaskTargetIsEmpty, {"target": target})

        # 5. 组装成功的回复包裹
        ret = {
            "code": 200,
            "message": "success",
            "items": task_data_list
        }

        # 把新建成功的任务信息返回给前端
        return ret

        # return utils.build_ret(ErrorMsg.Success, {"items": task_data_list})

# 1. 印制表格：批量停止任务时，必须传一个包含多个任务ID的列表
batch_stop_fields = ns.model('BatchStop',  {
    "task_id": fields.List(fields.String(description="任务 ID"), required=True),
})


# ==========================================
# 接口 A：批量停止任务 (POST /batch_stop/)
# ==========================================
@ns.route('/batch_stop/')
class BatchStopTask(ARLResource):

    @auth
    @ns.expect(batch_stop_fields)
    def post(self):
        """
        任务批量停止
        """
        args = self.parse_args(batch_stop_fields)
        task_id_list = args.pop("task_id", [])  # 拿到所有需要停止的任务 ID

        # 遍历每一个任务 ID，逐个调用底层的 stop_task 函数
        for task_id in task_id_list:
            if not task_id:
                continue
            stop_task(task_id)

        # 这里不关心中间是否有失败，直接统一返回成功给前端
        return utils.build_ret(ErrorMsg.Success, {})


# ==========================================
# 接口 B：单个停止任务 (GET /stop/<task_id>)
# ==========================================
@ns.route('/stop/<string:task_id>')     # 注意这里的写法，直接把变量写在了 URL 路径里
class StopTask(ARLResource):
    @auth
    def get(self, task_id=None):
        """
        任务停止
        """
        return stop_task(task_id=task_id)


# ==========================================
# 核心底层逻辑：真正去中止任务的函数
# ==========================================
def stop_task(task_id):
    """任务停止"""
    # 1. 定义哪些状态属于“已经结束”（完成、已停止、报错）
    done_status = [TaskStatus.DONE, TaskStatus.STOP, TaskStatus.ERROR]

    # 2. 去数据库查一下这个任务当前的真实情况
    task_data = utils.conn_db('task').find_one({'_id': ObjectId(task_id)})
    if not task_data:
        return utils.build_ret(ErrorMsg.NotFoundTask, {"task_id": task_id})

    # 3. 如果任务本来就已经结束了，就不需要再去杀进程了，直接返回
    if task_data["status"] in done_status:
        return utils.build_ret(ErrorMsg.TaskIsDone, {"task_id": task_id})

    # 4. 获取后台真正干活的工人的编号 (celery_id)
    celery_id = task_data.get("celery_id")
    if not celery_id:
        return utils.build_ret(ErrorMsg.CeleryIdNotFound, {"task_id": task_id})

    # 5. 【核心杀手锏】：连接到 Celery 的控制台
    control = celerytask.celery.control

    # 向指定的工人发送 SIGTERM (强制终止) 信号，要求他立刻放下手头的工作！
    control.revoke(celery_id, signal='SIGTERM', terminate=True)

    # 6. 打扫战场：不管工人死没死透，在数据库里强制把任务状态改成 "已停止 (STOP)"，并记录结束时间
    # $set 是 MongoDB 专属语法，代表只更新这两个指定的字段，不影响其他字段
    update_data = {"$set": {"status": TaskStatus.STOP, "end_time": utils.curr_date()}}
    utils.conn_db('task').update_one({'_id': ObjectId(task_id)}, update_data)

    return utils.build_ret(ErrorMsg.Success, {"task_id": task_id})


# (附赠的一张表格) 印制删除任务的表格，询问是否连带删除扫出来的资产数据
delete_task_fields = ns.model('DeleteTask',  {
    'del_task_data': fields.Boolean(required=False, default=False, description="是否删除任务数据"),
    'task_id': fields.List(fields.String(required=True, description="任务ID"))
})


# ==========================================
# 接口 A：任务删除 (POST /delete/)
# ==========================================
@ns.route('/delete/')
class DeleteTask(ARLResource):
    @auth
    @ns.expect(delete_task_fields)  # 使用上一段发的那个表格进行参数校验
    def post(self):
        """
        任务删除
        """
        # 1. 明确只有结束状态的任务才能被删除
        done_status = [TaskStatus.DONE, TaskStatus.STOP, TaskStatus.ERROR]

        args = self.parse_args(delete_task_fields)
        task_id_list = args.pop('task_id')      # 拿到要删除的任务ID列表
        del_task_data_flag = args.pop('del_task_data')  # 拿到用户的抉择：要不要把扫出来的资产数据一起删了？


        # 2. 【第一层循环：纯校验】（Fail-Fast 机制）
        # 在删任何东西之前，先把所有任务检查一遍，防止删到一半发现有个任务不能删。
        for task_id in task_id_list:
            task_data = utils.conn_db('task').find_one({'_id': ObjectId(task_id)})
            if not task_data:
                return utils.build_ret(ErrorMsg.NotFoundTask, {"task_id": task_id})

            # 如果有个任务还在运行中，立刻打回，拒绝整个删除请求
            if task_data["status"] not in done_status:
                return utils.build_ret(ErrorMsg.TaskIsRunning, {"task_id": task_id})

        # 3. 【第二层循环：真删除】
        for task_id in task_id_list:
            # 先把任务表 (task) 里的这条任务记录删掉
            utils.conn_db('task').delete_many({'_id': ObjectId(task_id)})

            # 这是一个硬编码的“关联表清单”，包含了所有可能存有扫描结果的表
            table_list = ["cert", "domain", "fileleak","ip", "service",
                          "site", "url", "vuln", "cip", "npoc_service", "wih", "nuclei_result", "stat_finger"]

            # 如果用户勾选了“连带删除扫描数据”
            if del_task_data_flag:
                for name in table_list:
                    # 去每一个结果表里，把归属于这个 task_id 的数据全部清空
                    utils.conn_db(name).delete_many({'task_id': task_id})

        return utils.build_ret(ErrorMsg.Success, {"task_id": task_id_list})


# ==========================================
# 印制表格：同步任务结果时，必须指定“哪个任务”同步到“哪个资产组”
# ==========================================
sync_task_fields = ns.model('SyncTask',  {
    'task_id': fields.String(required=True, description="任务ID"),
    'scope_id': fields.String(required=True, description="资产范围ID"),
})


# ==========================================
# 接口 B：将任务结果同步到资产组 (POST /sync/)
# ==========================================
@ns.route('/sync/')
class SyncTask(ARLResource):
    @auth
    @ns.expect(sync_task_fields)
    def post(self):
        """
        将任务结果同步到资产组
        """
        done_status = [TaskStatus.DONE, TaskStatus.STOP, TaskStatus.ERROR]
        args = self.parse_args(sync_task_fields)
        task_id = args.pop('task_id')
        scope_id = args.pop('scope_id')

        query = {'_id': ObjectId(task_id)}
        task_data = utils.conn_db('task').find_one(query)

        # 1. 疯狂的安全与逻辑校验（极其严谨）
        if not task_data:
            return utils.build_ret(ErrorMsg.NotFoundTask, {"task_id": task_id})

        asset_scope_data = utils.conn_db('asset_scope').find_one({'_id': ObjectId(scope_id)})
        if not asset_scope_data:
            return utils.build_ret(ErrorMsg.NotFoundScopeID, {"task_id": task_id})

        # 目前系统逻辑限制：只允许 domain (域名) 类型的任务进行同步
        if task_data.get("type") != "domain":
            return utils.build_ret(ErrorMsg.TaskTypeIsNotDomain, {"task_id": task_id})

        # 核心校验：这个任务扫的目标，真的属于这个资产组(公司)的授权范围吗？
        if not utils.is_in_scopes(task_data["target"], asset_scope_data["scope_array"]):
            return utils.build_ret(ErrorMsg.TaskTargetNotInScope, {"task_id": task_id})

        if task_data["status"] not in done_status:
            return utils.build_ret(ErrorMsg.TaskIsRunning, {"task_id": task_id})

        # 获取任务当前的同步状态，如果查不到，默认是 DEFAULT (从未同步过)
        task_sync_status = task_data.get("sync_status", TaskSyncStatus.DEFAULT)

        # 如果它已经在同步中 (WAITING/DOING) 或者同步完成 (DONE)，拒绝重复点击
        if task_sync_status not in [TaskSyncStatus.DEFAULT, TaskSyncStatus.ERROR]:
            return utils.build_ret(ErrorMsg.TaskSyncDealing, {"task_id": task_id})

        # 2. 校验全通过！先把状态改成“等待同步中”
        task_data["sync_status"] = TaskSyncStatus.WAITING

        # 3. 组装给工人的指令包
        options = {
            "celery_action": CeleryAction.DOMAIN_TASK_SYNC_TASK,
            "data": {
                "task_id": task_id,
                "scope_id": scope_id
            }
        }
        # 4. 【异步下发】：用 .delay() 把活派给 Celery 工人去后台慢慢干
        celerytask.arl_task.delay(options=options)

        # 5. 更新数据库里这条任务的状态（保存刚刚改的 WAITING）
        conn('task').find_one_and_replace(query, task_data)

        # 6. 立刻给前端返回成功，不用等工人干完
        return utils.build_ret(ErrorMsg.Success, {"task_id": task_id})


# ==========================================
# 接口 A：反查目标属于哪个资产组 (GET /sync_scope/)
# ==========================================
sync_scope_fields = ns.model('SyncScope',  {
    'target': fields.String(required=True, description="需要同步的目标"),
})


# ******* 根据目标找到要同步的资产分组ID *********
@ns.route('/sync_scope/')
class Target2Scope(ARLResource):
    parser = get_arl_parser(sync_scope_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        从目标反查资产分组
        """
        args = self.parser.parse_args()
        target = args.pop("target")

        # 1. 格式校验：传进来的必须是个合法的域名（不能瞎填）
        if not utils.is_valid_domain(target):
            return utils.build_ret(ErrorMsg.DomainInvalid, {"target": target})

        # 2. 提取主域名：比如传进来 a.b.baidu.com，get_fld 会提取出 baidu.com
        args["scope_array"] = utils.get_fld(target)
        args["size"] = 100
        args["order"] = "_id"

        # 3. 粗筛：去数据库里把包含 "baidu.com" 的资产组全捞出来
        data = self.build_data(args=args, collection='asset_scope')
        ret = []

        # 4. 精筛：遍历粗筛出来的资产组，用 is_in_scopes 进行严格的正则或子域名匹配
        for item in data["items"]:
            if utils.is_in_scopes(target, item["scope_array"]):
                ret.append(item)    # 如果完全匹配，放入最终返回的列表中

        data["items"] = ret
        data["total"] = len(ret)
        return data


# ==========================================
# 接口 B：通过策略(模板)下发任务 (POST /policy/)
# ==========================================
task_by_policy_fields = ns.model('TaskByPolicy', {
    "name": fields.String(description="任务名称", default=True, required=True),
    "task_tag": fields.String(description="任务类型标签", enum=["task", "risk_cruising"], required=True), # task=侦察打野, risk_cruising=风险巡航
    "target": fields.String(description="任务目标", example="", required=False),
    "policy_id": fields.String(description="策略 ID", example="603c65316591e73dd717d176", required=True), # 核心：策略模板的ID
    "result_set_id": fields.String(description="结果集 ID", example="603c65316591e73dd717d176", required=False)
})


# ******* 通过指定策略ID 下发任务 *********
@ns.route('/policy/')
class TaskByPolicy(ARLResource):
    @auth
    @ns.expect(task_by_policy_fields)
    def post(self):
        """
        任务通过策略下发
        """
        args = self.parse_args(task_by_policy_fields)
        name = args.pop("name")
        policy_id = args.pop("policy_id")
        target = args.pop("target")
        task_tag = args.pop("task_tag")
        result_set_id = args.pop("result_set_id")
        task_tag_enum = task_by_policy_fields["task_tag"].enum

        # 安全防御：限制任务类型只能是表单里规定的那两种
        if task_tag not in task_tag_enum:
            return utils.build_ret("task_tag 只能取 {}".format(",".join(task_tag_enum)), {})

        # 1. 【核心魔法】：根据 policy_id，去数据库里把预设好的一大堆扫描选项(options)拿出来！
        options = get_options_by_policy_id(policy_id, task_tag)

        if not options:
            return utils.build_ret(ErrorMsg.PolicyIDNotFound, {"policy_id": policy_id})

        task_data_list = []
        try:
            # 场景一：普通的资产发现任务
            if task_tag == TaskTag.TASK:
                # 【越权防御】：有些策略是绑定了特定资产组的，检查用户输入的目标有没有超框！
                related_scope_id = options.get("related_scope_id", "")
                if related_scope_id:
                    scope_data = get_scope_by_scope_id(scope_id=related_scope_id)
                    if not scope_data:
                        return utils.build_ret(ErrorMsg.NotFoundScopeID, {"scope_id": related_scope_id})

                    # 强行比对：如果你扫的目标不在绑定的资产组里，这里会直接抛出报错中断
                    check_target_in_scope(target=target, scope_list=scope_data["scope_array"])

                # 校验全过，把目标和“套用模板取出来的options”派发给 Celery
                task_data_list = submit_task_task(target=target, name=name, options=options)
                if not task_data_list:
                    return utils.build_ret(ErrorMsg.TaskTargetIsEmpty, {"target": target})

            # 场景二：高级的风险巡航任务（专门用来打特定漏洞的）
            if task_tag == TaskTag.RISK_CRUISING:
                # 巡航可以直接打以前扫出来的“结果集(result_set_id)”
                if result_set_id:
                    query = {"_id": ObjectId(result_set_id)}
                    item = utils.conn_db('result_set').find_one(query, {"total": 1})
                    if not item:
                        return utils.build_ret(ErrorMsg.ResultSetIDNotFound, {"result_set_id": result_set_id})

                    target_len = item["total"]

                    if target_len == 0:
                        return utils.build_ret(ErrorMsg.ResultSetIsEmpty, {"result_set_id": result_set_id})

                    options["result_set_id"] = result_set_id
                    options["result_set_len"] = target_len

                    task_data_list = submit_risk_cruising(target=target, name=name, options=options)
                    if not task_data_list:
                        return utils.build_ret(ErrorMsg.Error, {"result_set_id": result_set_id})

                else:
                    # 也可以直接打普通的 target
                    task_data_list = submit_risk_cruising(target=target, name=name, options=options)
                    if not task_data_list:
                        return utils.build_ret(ErrorMsg.TaskTargetIsEmpty, {"target": target})
        except Exception as e:
            logger.exception(e)
            return utils.build_ret(ErrorMsg.Error, {"error": str(e)})

        return utils.build_ret(ErrorMsg.Success, {"items": task_data_list})


# ==========================================
# 接口 C：重启任务 (POST /restart/)
# ==========================================
# 【注意】：原作者复制粘贴忘了改名字，这里 model 名字还是 'DeleteTask'，但内部字段没写错。
restart_task_fields = ns.model('DeleteTask',  {
    'task_id': fields.List(fields.String(required=True, description="任务ID"))
})


# ******* 重新下发任务功能 *********
@ns.route('/restart/')
class TaskRestart(ARLResource):
    @auth
    @ns.expect(restart_task_fields)
    def post(self):
        """
        任务重启
        """
        done_status = [TaskStatus.DONE, TaskStatus.STOP, TaskStatus.ERROR]
        args = self.parse_args(restart_task_fields)
        task_id_list = args.pop('task_id')

        try:
            for task_id in task_id_list:
                task_data = get_task_data(task_id)
                if not task_data:
                    return utils.build_ret(ErrorMsg.NotFoundTask, {"task_id": task_id})

                # 防御逻辑：只有已经结束的任务才能重启，还在跑的不能重启
                if task_data["status"] not in done_status:
                    return utils.build_ret(ErrorMsg.TaskIsRunning, {"task_id": task_id})

                # 调用底层重启逻辑（通常是原样提取配置，生成一个新任务丢给 Celery）
                restart_task(task_id)

        except Exception as e:
            return utils.build_ret(ErrorMsg.Error, {"error": str(e)})

        return utils.build_ret(ErrorMsg.Success, {"task_id": task_id_list})


