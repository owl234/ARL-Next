# backend/app/routes/platform.py
"""漏洞平台聚合路由"""

from flask import request
from flask_restx import fields, Namespace

from app.utils import (
    get_logger, auth, build_ret, conn_db,
)
from app.modules import ErrorMsg
from . import ARLResource, base_query_fields, get_arl_parser
from app.models import (
    ProjectModel, TargetModel, ScanScheduleModel,
    SubmitRecordModel, VulnExtModel,
)

ns = Namespace('platform', description="漏洞平台聚合")
logger = get_logger()


# ═══════════════════════════════════════════════════════════
# ★ 序列化辅助（新增）
# ═══════════════════════════════════════════════════════════

def _serialize_items(items, model_cls):
    """用 Model 序列化 items（datetime / ObjectId → 字符串）"""
    return [
        model_cls(d).dump_json(flag=False)
        for d in (items or [])
    ]


def _serialize_data(data, model_cls):
    """就地序列化 build_data 返回的 items"""
    if isinstance(data, dict) and "items" in data:
        data["items"] = _serialize_items(data["items"], model_cls)
    return data


# ═══════════════════════════════════════════════════════════
# 搜索字段定义
# ═══════════════════════════════════════════════════════════

project_search_fields = {
    'project_name': fields.String(description="项目名称"),
    'platform': fields.String(description="来源平台"),
    'status': fields.String(description="项目状态"),
    'project_id': fields.String(description="平台侧项目 ID"),
}
project_search_fields.update(base_query_fields)
search_project_fields = ns.model('SearchProject', project_search_fields)


target_search_fields = {
    'project_fingerprint': fields.String(description="项目指纹"),
    'platform': fields.String(description="平台"),
    'target': fields.String(description="目标"),
    'target_type': fields.String(description="目标类型"),
    'status': fields.String(description="状态"),
    'scanned': fields.String(description="是否已扫描"),
}
target_search_fields.update(base_query_fields)
search_target_fields = ns.model('SearchTarget', target_search_fields)


record_search_fields = {
    'platform': fields.String(description="目标平台"),
    'source_platform': fields.String(description="来源平台"),
    'project_fingerprint': fields.String(description="项目指纹"),
    'status': fields.String(description="状态"),
}
record_search_fields.update(base_query_fields)
search_record_fields = ns.model('SearchRecord', record_search_fields)


schedule_search_fields = {
    'project_fingerprint': fields.String(description="项目指纹"),
    'profile': fields.String(description="扫描策略"),
    'enabled': fields.String(description="是否启用"),
}
schedule_search_fields.update(base_query_fields)
search_schedule_fields = ns.model('SearchSchedule', schedule_search_fields)


# ═══════════════════════════════════════════════════════════
# 操作类表单模型
# ═══════════════════════════════════════════════════════════

fetch_project_fields = ns.model('FetchProject', {
    'platform': fields.String(description="平台名称"),
})

scan_project_fields = ns.model('ScanProject', {
    'profile': fields.String(description="扫描策略", default='quick'),
})

submit_vuln_fields = ns.model('SubmitVuln', {
    'platform': fields.String(description="指定平台"),
    'force': fields.Boolean(default=False),
})

batch_submit_fields = ns.model('BatchSubmitVuln', {
    'vuln_ids': fields.List(fields.String, required=True),
    'platform': fields.String(description="指定平台"),
})

schedule_create_fields = ns.model('ScheduleCreate', {
    'project_fingerprint': fields.String(required=True),
    'profile': fields.String(required=True),
    'cron_expression': fields.String(required=True),
    'enabled': fields.Boolean(default=True),
})

schedule_toggle_fields = ns.model('ScheduleToggle', {
    'enabled': fields.Boolean(required=True),
})


# ═══════════════════════════════════════════════════════════
# 平台列表（配置类，非分页）
# ═══════════════════════════════════════════════════════════

@ns.route('/platforms/')
class ARLPlatformList(ARLResource):

    @auth
    def get(self):
        """获取所有已启用平台"""
        from app.adapters.vuln_platform.config import (
            PLATFORM_CONFIG, get_platform_config,
        )
        items = []
        for name in PLATFORM_CONFIG:
            cfg = get_platform_config(name)
            if not cfg.get("enabled"):
                continue
            items.append({
                "name": name,
                "display_name": cfg.get("name", name),
                "rate_limit": cfg.get("rate_limit"),
                "default_delay": cfg.get("default_delay"),
                "requires_login": cfg.get("requires_login", False),
                "cookie_ttl_hours": cfg.get("cookie_ttl_hours"),
                "priority": cfg.get("priority"),
            })
        return {
            "code": 200,
            "message": "success",
            "items": items,
            "total": len(items),
        }


# ═══════════════════════════════════════════════════════════
# 项目列表 / 触发抓取
# ═══════════════════════════════════════════════════════════

@ns.route('/projects/')
class ARLProject(ARLResource):
    parser = get_arl_parser(search_project_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """项目列表（分页，扁平结构）"""
        args = self.parser.parse_args()
        data = self.build_data(
            args=args, collection='vuln_platform_projects')
        # ★ 序列化 items（修复 datetime 500 错误）
        return _serialize_data(data, ProjectModel)

    @auth
    @ns.expect(fetch_project_fields)
    def post(self):
        """触发抓取"""
        args = self.parse_args(fetch_project_fields)
        platform = args.get("platform")

        from app.services.vuln_platform import ProjectService
        try:
            service = ProjectService()
            if platform:
                result = service.fetch_and_sync(platform)
            else:
                result = service.fetch_all_platforms()
            return build_ret(ErrorMsg.Success, result)
        except Exception as e:
            logger.exception(e)
            return build_ret(ErrorMsg.Error, {"error": str(e)})


# ═══════════════════════════════════════════════════════════
# 项目详情 / 删除
# ═══════════════════════════════════════════════════════════

@ns.route('/projects/<string:fingerprint>/')
class ARLProjectDetail(ARLResource):

    @auth
    def get(self, fingerprint):
        """项目详情"""
        from app.services.vuln_platform import (
            ProjectService, TargetService, VulnService,
        )
        project = ProjectService().get(fingerprint)
        if not project:
            return build_ret(
                ErrorMsg.NotFoundScopeID,
                {"fingerprint": fingerprint})

        targets = TargetService().list_by_project(fingerprint)
        vulns = VulnService().list_by_project(fingerprint)

        item = ProjectModel(project).dump_json(flag=False)
        # ★ 序列化 targets / vulns
        item["targets"] = _serialize_items(targets, TargetModel)
        item["vulns"] = _serialize_items(vulns, VulnExtModel)
        return build_ret(ErrorMsg.Success, item)

    @auth
    def delete(self, fingerprint):
        """删除项目"""
        from app.utils import db as db_utils
        count = db_utils.delete_many(
            ProjectModel.COLLECTION,
            {"fingerprint": fingerprint})
        return build_ret(ErrorMsg.Success, {
            "fingerprint": fingerprint,
            "deleted": count,
        })


# ═══════════════════════════════════════════════════════════
# 下发扫描
# ═══════════════════════════════════════════════════════════

@ns.route('/projects/<string:fingerprint>/scan/')
class ARLProjectScan(ARLResource):

    @auth
    @ns.expect(scan_project_fields)
    def post(self, fingerprint):
        """下发扫描"""
        args = self.parse_args(scan_project_fields)
        profile = args.get("profile") or "quick"

        from app.services.vuln_platform import (
            ProjectService, ScanOrchestrator,
        )
        project = ProjectService().get(fingerprint)
        if not project:
            return build_ret(
                ErrorMsg.NotFoundScopeID,
                {"fingerprint": fingerprint})

        try:
            result = ScanOrchestrator().dispatch_scan(
                fingerprint, profile)
            return build_ret(ErrorMsg.Success, result)
        except Exception as e:
            logger.exception(e)
            return build_ret(ErrorMsg.Error, {"error": str(e)})


# ═══════════════════════════════════════════════════════════
# 提交项目所有漏洞
# ═══════════════════════════════════════════════════════════

@ns.route('/projects/<string:fingerprint>/submit_vulns/')
class ARLProjectSubmitVulns(ARLResource):

    @auth
    def post(self, fingerprint):
        """提交项目所有未提交漏洞"""
        from app.services.vuln_platform import VulnSubmitter
        try:
            result = VulnSubmitter().submit_project_vulns(fingerprint)
            return build_ret(ErrorMsg.Success, result)
        except Exception as e:
            logger.exception(e)
            return build_ret(ErrorMsg.Error, {"error": str(e)})


# ═══════════════════════════════════════════════════════════
# 目标列表
# ═══════════════════════════════════════════════════════════

@ns.route('/targets/')
class ARLTarget(ARLResource):
    parser = get_arl_parser(search_target_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """目标列表（分页，扁平结构）"""
        args = self.parser.parse_args()
        data = self.build_data(
            args=args, collection='vuln_platform_targets')
        # ★ 序列化
        return _serialize_data(data, TargetModel)


# ═══════════════════════════════════════════════════════════
# 漏洞提交
# ═══════════════════════════════════════════════════════════

@ns.route('/vulns/<string:vuln_id>/submit/')
class ARLVulnSubmit(ARLResource):

    @auth
    @ns.expect(submit_vuln_fields)
    def post(self, vuln_id):
        """提交单个漏洞"""
        args = self.parse_args(submit_vuln_fields)
        from app.services.vuln_platform import VulnSubmitter

        try:
            result = VulnSubmitter().submit(
                vuln_id,
                platform=args.get("platform"),
                force=args.get("force", False))
            return build_ret(ErrorMsg.Success, result)
        except Exception as e:
            logger.exception(e)
            return build_ret(ErrorMsg.Error, {"error": str(e)})


@ns.route('/vulns/batch_submit/')
class ARLVulnBatchSubmit(ARLResource):

    @auth
    @ns.expect(batch_submit_fields)
    def post(self):
        """批量提交漏洞"""
        args = self.parse_args(batch_submit_fields)
        vuln_ids = args.get("vuln_ids") or []
        if not vuln_ids:
            return build_ret(ErrorMsg.Error,
                              {"error": "vuln_ids 不能为空"})

        from app.services.vuln_platform import VulnSubmitter
        try:
            result = VulnSubmitter().batch_submit(
                vuln_ids, platform=args.get("platform"))
            return build_ret(ErrorMsg.Success, result)
        except Exception as e:
            logger.exception(e)
            return build_ret(ErrorMsg.Error, {"error": str(e)})


# ═══════════════════════════════════════════════════════════
# 提交记录列表
# ═══════════════════════════════════════════════════════════

@ns.route('/submit_records/')
class ARLSubmitRecord(ARLResource):
    parser = get_arl_parser(search_record_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """提交记录列表（分页，扁平结构）"""
        args = self.parser.parse_args()
        data = self.build_data(
            args=args, collection='vuln_platform_submit_records')
        # ★ 序列化
        return _serialize_data(data, SubmitRecordModel)


# ═══════════════════════════════════════════════════════════
# 调度列表 / 创建
# ═══════════════════════════════════════════════════════════

@ns.route('/schedules/')
class ARLSchedule(ARLResource):
    parser = get_arl_parser(search_schedule_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """调度列表（分页，扁平结构）"""
        args = self.parser.parse_args()
        data = self.build_data(
            args=args, collection='vuln_platform_scan_schedules')
        # ★ 序列化
        return _serialize_data(data, ScanScheduleModel)

    @auth
    @ns.expect(schedule_create_fields)
    def post(self):
        """创建/更新调度"""
        args = self.parse_args(schedule_create_fields)
        from app.services.vuln_platform import ScheduleService

        try:
            result = ScheduleService().upsert(args)
            return build_ret(ErrorMsg.Success, result)
        except Exception as e:
            logger.exception(e)
            return build_ret(ErrorMsg.Error, {"error": str(e)})


# ═══════════════════════════════════════════════════════════
# 调度切换 / 删除
# ═══════════════════════════════════════════════════════════

@ns.route('/schedules/<string:schedule_id>/')
class ARLScheduleDetail(ARLResource):

    @auth
    @ns.expect(schedule_toggle_fields)
    def put(self, schedule_id):
        """启用/禁用调度"""
        args = self.parse_args(schedule_toggle_fields)
        from app.services.vuln_platform import ScheduleService

        try:
            ScheduleService().toggle(schedule_id,
                                      args.get("enabled"))
            return build_ret(ErrorMsg.Success, {"_id": schedule_id})
        except Exception as e:
            return build_ret(ErrorMsg.Error, {"error": str(e)})

    @auth
    def delete(self, schedule_id):
        """删除调度"""
        from app.services.vuln_platform import ScheduleService

        try:
            count = ScheduleService().remove(schedule_id)
            return build_ret(ErrorMsg.Success, {
                "_id": schedule_id,
                "deleted": count,
            })
        except Exception as e:
            return build_ret(ErrorMsg.Error, {"error": str(e)})