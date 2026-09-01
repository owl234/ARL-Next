from flask_restx import fields, Namespace
from app.utils import auth, truncate_string
from app.modules import ErrorMsg
from . import base_query_fields, ARLResource, get_arl_parser
from app import scheduler as app_scheduler, utils
from app.modules import SchedulerStatus, AssetScopeType, TaskTag
from app.helpers import (
    get_options_by_policy_id,
    have_same_site_update_monitor,
    have_same_wih_update_monitor
)

ns = Namespace('scheduler', description="资产监控任务信息")

base_search_fields = {
    '_id': fields.String(description="监控任务job_id"),
    'domain': fields.String(description="要监控的域名"),
    'scope_id': fields.String(description="资产组范围ID"),
    'interval': fields.String(description="运行间隔，单位S"),
    'next_run_time': fields.String(description="下一次运行时间戳"),
    'next_run_date': fields.Integer(description="下一次运行日期"),
    'last_run_time': fields.Integer(description="上一次运行时间戳"),
    'last_run_date': fields.String(description="上一次运行时间日期"),
    'run_number': fields.String(description="运行次数"),
    "name": fields.String(description="名称")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLScheduler(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        监控任务查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='scheduler')

        return data


add_scheduler_fields = ns.model('addScheduler', {
    "scope_id": fields.String(required=True, description="添加资产范围"),
    "domain": fields.String(required=True, description="域名"),  # 多个域名可以用,隔开
    "interval": fields.Integer(description="间隔，单位是秒"),  # 单位是S
    "name": fields.String(description="监控任务名称"),  # 名称为空即自动生成
    "policy_id": fields.String(description="策略ID")
})


@ns.route('/add/')
class AddARLScheduler(ARLResource):

    @auth
    @ns.expect(add_scheduler_fields)
    def post(self):
        """
        添加监控周期任务
        """
        args = self.parse_args(add_scheduler_fields)
        scope_id = args.pop("scope_id")
        domain = args.pop("domain")
        interval = args.pop("interval")
        name = args.pop("name")
        policy_id = args.pop("policy_id", "")

        if interval < 3600 * 6:
            return utils.build_ret(ErrorMsg.IntervalLessThan3600, {"interval": interval})

        monitor_domain = utils.arl.get_monitor_domain_by_id(scope_id)
        scope_data = utils.arl.scope_data_by_id(scope_id)

        if not scope_data:
            return utils.build_ret(ErrorMsg.NotFoundScopeID, {"scope_id": scope_id})

        task_options = None
        if policy_id and len(policy_id) == 24:
            task_options = get_options_by_policy_id(policy_id, TaskTag.TASK)
            if task_options is None:
                return utils.build_ret(ErrorMsg.PolicyIDNotFound, {"policy_id": policy_id})

        domains = domain.split(",")
        domain_targets = []
        ip_targets = []

        for x in domains:
            curr_target = x.strip()
            if not curr_target:
                continue

            if curr_target not in scope_data["scope_array"]:
                return utils.build_ret(ErrorMsg.DomainNotFoundViaScope,
                                       {"domain": curr_target, "scope_id": scope_id})

            if curr_target in monitor_domain:
                return utils.build_ret(ErrorMsg.DomainViaJob,
                                       {"domain": curr_target, "scope_id": scope_id})

            if utils.is_valid_domain(curr_target):
                domain_targets.append(curr_target)
            else:
                ip_targets.append(curr_target)

        ret_data = []

        # 下发 域名类型监控任务
        if domain_targets:
            from app.helpers.scope import update_scope_domain_status
            for x in domain_targets:
                curr_name = name
                if not name:
                    curr_name = "监控-{}-{}".format(scope_data["name"], x)

                curr_name = truncate_string(curr_name)

                scheduler_id = app_scheduler.add_scheduler(domain=x, scope_id=scope_id,
                                               options=task_options, interval=interval,
                                               name=curr_name, scope_type=AssetScopeType.DOMAIN)
                update_scope_domain_status(scope_id, x, "scanning", scheduler_id)
                ret_data.append({"domain": x, "scope_id": scope_id, "scheduler_id": scheduler_id})

        # 下发IP 类型监控任务
        if ip_targets:
            from app.helpers.scope import update_scope_domain_status
            curr_name = name
            ip_target = " ".join(ip_targets)
            if not name:
                curr_name = "监控-{}-{}".format(scope_data["name"], ip_target)

            curr_name = truncate_string(curr_name)

            scheduler_id = app_scheduler.add_scheduler(domain=ip_target, scope_id=scope_id,
                                           options=task_options, interval=interval,
                                           name=curr_name, scope_type=AssetScopeType.IP)
            for x in ip_targets:
                update_scope_domain_status(scope_id, x, "scanning", scheduler_id)
            ret_data.append({"domain": ip_target, "scope_id": scope_id, "scheduler_id": scheduler_id})

        return utils.build_ret(ErrorMsg.Success, ret_data)


delete_scheduler_fields = ns.model('deleteScheduler', {
    "scheduler_id": fields.List(fields.String(description="监控任务ID列表"))
})


@ns.route('/delete/')
class DeleteARLScheduler(ARLResource):

    @auth
    @ns.expect(delete_scheduler_fields)
    def post(self):
        """
        删除监控周期任务
        """
        args = self.parse_args(delete_scheduler_fields)
        job_id_list = args.get("scheduler_id", [])

        ret_data = {"scheduler_id": job_id_list}

        for scheduler_id in job_id_list:
            item = app_scheduler.find_scheduler(scheduler_id)
            if not item:
                return utils.build_ret(ErrorMsg.JobNotFound, ret_data)

        for scheduler_id in job_id_list:
            app_scheduler.delete_scheduler(scheduler_id)

        return utils.build_ret(ErrorMsg.Success, ret_data)


recover_scheduler_fields = ns.model('recoverScheduler', {
    "scheduler_id": fields.String(required=True, description="监控任务ID")
})


# 下面有个批量恢复的，这个接口后面再删除
@ns.route('/recover/')
class RecoverARLScheduler(ARLResource):

    @auth
    @ns.expect(recover_scheduler_fields)
    def post(self):
        """
        恢复监控周期任务
        """
        args = self.parse_args(recover_scheduler_fields)
        scheduler_id = args.get("scheduler_id")

        item = app_scheduler.find_scheduler(scheduler_id)
        if not item:
            return utils.build_ret(ErrorMsg.JobNotFound, {"scheduler_id": scheduler_id})

        status = item.get("status", SchedulerStatus.RUNNING)
        if status != SchedulerStatus.STOP:
            return utils.build_ret(ErrorMsg.SchedulerStatusNotStop, {"scheduler_id": scheduler_id})

        app_scheduler.recover_scheduler(scheduler_id)

        return utils.build_ret(ErrorMsg.Success, {"scheduler_id": scheduler_id})


batch_recover_scheduler_fields = ns.model('batchRecoverScheduler', {
    "scheduler_id": fields.List(fields.String(required=True, description="监控任务ID列表"))
})


@ns.route('/recover/batch')
class BatchRecoverARLScheduler(ARLResource):

    @auth
    @ns.expect(batch_recover_scheduler_fields)
    def post(self):
        """
        批量恢复监控周期任务
        """
        args = self.parse_args(batch_recover_scheduler_fields)
        job_id_list = args.get("scheduler_id", [])
        for scheduler_id in job_id_list:
            item = app_scheduler.find_scheduler(scheduler_id)
            if not item:
                return utils.build_ret(ErrorMsg.JobNotFound, {"scheduler_id": scheduler_id})

            status = item.get("status", SchedulerStatus.RUNNING)
            if status != SchedulerStatus.STOP:
                return utils.build_ret(ErrorMsg.SchedulerStatusNotStop, {"scheduler_id": scheduler_id})

            app_scheduler.recover_scheduler(scheduler_id)

        return utils.build_ret(ErrorMsg.Success, {"scheduler_id": job_id_list})


stop_scheduler_fields = ns.model('stopScheduler', {
    "scheduler_id": fields.String(required=True, description="监控任务ID")
})


# 下面有个批量停止的，这个接口后面再删除
@ns.route('/stop/')
class StopARLScheduler(ARLResource):

    @auth
    @ns.expect(stop_scheduler_fields)
    def post(self):
        """
        停止监控周期任务
        """
        args = self.parse_args(stop_scheduler_fields)
        scheduler_id = args.get("scheduler_id")

        item = app_scheduler.find_scheduler(scheduler_id)
        if not item:
            return utils.build_ret(ErrorMsg.JobNotFound, {"scheduler_id": scheduler_id})

        status = item.get("status", SchedulerStatus.RUNNING)
        if status != SchedulerStatus.RUNNING:
            return utils.build_ret(ErrorMsg.SchedulerStatusNotRunning, {"scheduler_id": scheduler_id})

        app_scheduler.stop_scheduler(scheduler_id)

        return utils.build_ret(ErrorMsg.Success, {"scheduler_id": scheduler_id})


batch_stop_scheduler_fields = ns.model('batchStopScheduler', {
    "scheduler_id": fields.List(fields.String(required=True, description="监控任务ID列表"))
})


@ns.route('/stop/batch')
class BatchStopARLScheduler(ARLResource):

    @auth
    @ns.expect(batch_stop_scheduler_fields)
    def post(self):
        """
        停止监控周期任务
        """
        args = self.parse_args(batch_stop_scheduler_fields)
        job_id_list = args.get("scheduler_id", [])
        for scheduler_id in job_id_list:
            item = app_scheduler.find_scheduler(scheduler_id)
            if not item:
                return utils.build_ret(ErrorMsg.JobNotFound, {"scheduler_id": scheduler_id})

            status = item.get("status", SchedulerStatus.RUNNING)
            if status != SchedulerStatus.RUNNING:
                return utils.build_ret(ErrorMsg.SchedulerStatusNotRunning, {"scheduler_id": scheduler_id})

            app_scheduler.stop_scheduler(scheduler_id)

        return utils.build_ret(ErrorMsg.Success, {"scheduler_id": job_id_list})


add_scheduler_site_fields = ns.model('addSchedulerSite', {
    "scope_id": fields.String(required=True, description="资产范围 id"),
    "interval": fields.Integer(description="间隔，单位是秒", example=3600 * 23),  # 单位是S
    "name": fields.String(description="监控任务名称"),  # 名称为空即自动生成
})


@ns.route('/add/site_monitor/')
class AddSiteScheduler(ARLResource):

    @auth
    @ns.expect(add_scheduler_site_fields)
    def post(self):
        """
        添加站点更新监控周期任务
        """
        args = self.parse_args(add_scheduler_site_fields)
        scope_id = args.pop("scope_id")
        interval = args.pop("interval")
        name = args.pop("name")

        if interval < 3600 * 6:
            return utils.build_ret(ErrorMsg.IntervalLessThan3600, {"interval": interval})

        scope_data = utils.arl.scope_data_by_id(scope_id)

        if not scope_data:
            return utils.build_ret(ErrorMsg.NotFoundScopeID, {"scope_id": scope_id})

        if have_same_site_update_monitor(scope_id=scope_id):
            return utils.build_ret(ErrorMsg.DomainSiteViaJob, {"scope_id": scope_id,
                                                               "scope_name": scope_data['name']})

        if not name:
            name = "站点监控-{}".format(scope_data["name"])

        _id = app_scheduler.add_asset_site_monitor_job(scope_id=scope_id,
                                                       name=name,
                                                       interval=interval)

        return utils.build_ret(ErrorMsg.Success, {"schedule_id": _id})


add_scheduler_wih_fields = ns.model('addSchedulerWih', {
    "scope_id": fields.String(required=True, description="资产范围 id"),
    "interval": fields.Integer(description="间隔，单位是秒", example=3600 * 23),  # 单位是S
    "name": fields.String(description="监控任务名称", example=""),  # 名称为空即自动生成
})


@ns.route('/add/wih_monitor/')
class AddWihScheduler(ARLResource):

    @auth
    @ns.expect(add_scheduler_wih_fields)
    def post(self):
        """
        添加WIH更新监控周期任务
        """
        args = self.parse_args(add_scheduler_wih_fields)
        scope_id = args.pop("scope_id")
        interval = args.pop("interval")
        name = args.pop("name")

        if interval < 3600 * 6:
            return utils.build_ret(ErrorMsg.IntervalLessThan3600, {"interval": interval})

        scope_data = utils.arl.scope_data_by_id(scope_id)

        if not scope_data:
            return utils.build_ret(ErrorMsg.NotFoundScopeID, {"scope_id": scope_id})

        if have_same_wih_update_monitor(scope_id=scope_id):
            return utils.build_ret(ErrorMsg.DomainSiteViaJob, {"scope_id": scope_id,
                                                               "scope_name": scope_data['name']})

        if not name:
            name = "WIH 监控-{}".format(scope_data["name"])

        _id = app_scheduler.add_asset_wih_monitor_job(scope_id=scope_id,
                                                      name=name,
                                                      interval=interval)

        return utils.build_ret(ErrorMsg.Success, {"schedule_id": _id})


run_scheduler_fields = ns.model('runScheduler', {
    "scheduler_id": fields.String(required=True, description="监控任务ID")
})


@ns.route('/run/')
class RunARLScheduler(ARLResource):

    @auth
    @ns.expect(run_scheduler_fields)
    def post(self):
        """
        立即执行监控周期任务
        """
        args = self.parse_args(run_scheduler_fields)
        scheduler_id = args.get("scheduler_id")

        item = app_scheduler.find_scheduler(scheduler_id)
        if not item:
            return utils.build_ret(ErrorMsg.JobNotFound, {"scheduler_id": scheduler_id})

        app_scheduler.run_scheduler(scheduler_id)

        return utils.build_ret(ErrorMsg.Success, {"scheduler_id": scheduler_id})


batch_run_scheduler_fields = ns.model('batchRunScheduler', {
    "scheduler_id": fields.List(fields.String(required=True, description="监控任务ID列表"))
})


@ns.route('/run/batch')
class BatchRunARLScheduler(ARLResource):

    @auth
    @ns.expect(batch_run_scheduler_fields)
    def post(self):
        """
        批量立即执行监控周期任务
        """
        args = self.parse_args(batch_run_scheduler_fields)
        job_id_list = args.get("scheduler_id", [])
        for scheduler_id in job_id_list:
            item = app_scheduler.find_scheduler(scheduler_id)
            if not item:
                return utils.build_ret(ErrorMsg.JobNotFound, {"scheduler_id": scheduler_id})

            app_scheduler.run_scheduler(scheduler_id)

        return utils.build_ret(ErrorMsg.Success, {"scheduler_id": job_id_list})


one_time_scan_fields = ns.model('oneTimeScan', {
    "scope_id": fields.String(required=True, description="资产范围 id"),
    "domain": fields.String(required=True, description="目标域名，多个逗号分隔"),
    "policy_id": fields.String(required=True, description="策略ID"),
    "name": fields.String(description="一次性扫描任务名称", example=""),
})

@ns.route('/one_time_scan/')
class OneTimeScanScheduler(ARLResource):
    @auth
    @ns.expect(one_time_scan_fields)
    def post(self):
        """
        下发一次性资产监控并同步的任务
        """
        args = self.parse_args(one_time_scan_fields)
        scope_id = args.pop("scope_id")
        domain = args.pop("domain")
        policy_id = args.pop("policy_id")
        name = args.pop("name", "")

        scope_data = utils.arl.scope_data_by_id(scope_id)
        if not scope_data:
            return utils.build_ret(ErrorMsg.NotFoundScopeID, {"scope_id": scope_id})

        task_options = get_options_by_policy_id(policy_id, TaskTag.TASK)
        if task_options is None:
            return utils.build_ret(ErrorMsg.PolicyIDNotFound, {"policy_id": policy_id})

        domains = domain.split(",")
        domain_targets = []
        ip_targets = []
        for x in domains:
            curr_target = x.strip()
            if not curr_target:
                continue
            if utils.is_valid_domain(curr_target):
                domain_targets.append(curr_target)
            else:
                ip_targets.append(curr_target)
                
        if not domain_targets and not ip_targets:
            return utils.build_ret(ErrorMsg.DomainInvalid, {"domain": domain})
            
        from app.modules import CeleryAction, CeleryRoutingKey
        from app import celerytask
        
        ret_data = []
        # 下发 域名类型一次性扫描
        if domain_targets:
            from app.helpers.scope import update_scope_domain_status
            for x in domain_targets:
                curr_name = name
                if not name:
                    curr_name = "一次性扫描-{}-{}".format(scope_data["name"], x)
                curr_name = truncate_string(curr_name)
                
                task_data = {
                    "domain": x,
                    "scope_id": scope_id,
                    "type": AssetScopeType.DOMAIN,
                    "monitor_options": task_options,
                    "name": curr_name
                }
                options = {
                    "celery_action": CeleryAction.ONESHOT_DOMAIN_EXEC_TASK,
                    "data": task_data
                }
                celery_id = celerytask.arl_task.apply_async(kwargs={'options': options}, queue=CeleryRoutingKey.ASSET_TASK_HEAVY)
                update_scope_domain_status(scope_id, x, "scanning", str(celery_id))
                ret_data.append({"domain": x, "celery_id": str(celery_id)})

        # 下发 IP 类型一次性扫描
        if ip_targets:
            from app.helpers.scope import update_scope_domain_status
            curr_name = name
            ip_target = " ".join(ip_targets)
            if not name:
                curr_name = "一次性扫描-{}-{}".format(scope_data["name"], ip_target)
            curr_name = truncate_string(curr_name)

            task_data = {
                "domain": ip_target,
                "scope_id": scope_id,
                "type": AssetScopeType.IP,
                "monitor_options": task_options,
                "name": curr_name
            }
            options = {
                "celery_action": CeleryAction.ONESHOT_IP_EXEC_TASK,
                "data": task_data
            }
            celery_id = celerytask.arl_task.apply_async(kwargs={'options': options}, queue=CeleryRoutingKey.ASSET_TASK_HEAVY)
            for x in ip_targets:
                update_scope_domain_status(scope_id, x, "scanning", str(celery_id))
            ret_data.append({"domain": ip_target, "celery_id": str(celery_id)})
            
        return utils.build_ret(ErrorMsg.Success, ret_data)
