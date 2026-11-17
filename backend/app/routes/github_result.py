from urllib.parse import quote
import time

from flask import make_response
from flask_restx import fields, Namespace

from app import utils
from app.modules import ErrorMsg
from app.services import github_triage
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser

ns = Namespace('github_result', description="Github 结果详情")

logger = get_logger()

base_search_fields = {
    'path': fields.String(required=False, description="路径名称"),
    'repo_full_name': fields.String(description="仓库名称"),
    'human_content': fields.String(description="内容"),
    'github_task_id': fields.String(description="任务ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLGithubResult(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        Github 结果详情查询
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='github_result')
        items = data.get("items") or []
        if items:
            triage_map = github_triage.get_triage_status_map(
                [item.get("hash_md5") for item in items if item.get("hash_md5")]
            )
            ignored_set = set(github_triage.get_ignored_repo_names())
            for item in items:
                h = item.get("hash_md5")
                persisted = triage_map.get(h) if h else None
                if persisted:
                    item["triage_status"] = persisted["triage_status"]
                    item["triage_note"] = persisted["note"]
                    item["triage_updated_at"] = persisted["updated_at"]
                else:
                    item["triage_status"] = item.get("triage_status") or github_triage.TRIAGE_PENDING
                item["is_repo_ignored"] = item.get("repo_full_name", "") in ignored_set

        return data


overview_search_fields = {
    'page': fields.Integer(description="当前页数", example=1),
    'size': fields.Integer(description="页面大小", example=10),
    'source_type': fields.String(description="来源类型: all | task | scheduler"),
    'github_task_id': fields.String(description="任务ID"),
    'github_scheduler_id': fields.String(description="周期策略ID"),
    'repo_full_name': fields.String(description="仓库名称"),
    'path': fields.String(description="文件路径"),
    'human_content': fields.String(description="代码内容"),
    'keyword': fields.String(description="关键字"),
    'triage_status': fields.String(description="研判状态: pending | confirmed | false_positive"),
    'include_ignored': fields.String(description="是否包含屏蔽仓库"),
    'only_ignored': fields.String(description="仅看屏蔽仓库"),
    'group_by': fields.String(description="展示模式: flat | repo"),
}


def _parse_bool_arg(val) -> bool:
    return str(val or "").strip().lower() in ("1", "true", "yes", "on")


def _extract_overview_filters(args: dict) -> dict:
    return {
        "page": args.get("page") or 1,
        "size": args.get("size") or 10,
        "source_type": (args.get("source_type") or "all").strip(),
        "github_task_id": (args.get("github_task_id") or "").strip(),
        "github_scheduler_id": (args.get("github_scheduler_id") or "").strip(),
        "repo_full_name": (args.get("repo_full_name") or "").strip(),
        "path": (args.get("path") or "").strip(),
        "human_content": (args.get("human_content") or "").strip(),
        "keyword": (args.get("keyword") or "").strip(),
        "triage_status": (args.get("triage_status") or "").strip(),
        "include_ignored": _parse_bool_arg(args.get("include_ignored")),
        "only_ignored": _parse_bool_arg(args.get("only_ignored")),
        "group_by": (args.get("group_by") or "flat").strip(),
    }


@ns.route('/overview/')
class ARLGithubResultOverview(ARLResource):
    parser = get_arl_parser(overview_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        统一去重后的 GitHub 泄露命中总览（支持按仓库聚合与研判过滤）
        """
        args = self.parser.parse_args()
        filters = _extract_overview_filters(args)
        data = github_triage.query_unified_findings(filters)
        return utils.build_ret(ErrorMsg.Success, data)


@ns.route('/stats/')
class ARLGithubResultStats(ARLResource):
    @auth
    def get(self):
        """
        获取代码泄露命中研判统计与运行状态计数
        """
        stats = github_triage.get_findings_stats()
        return utils.build_ret(ErrorMsg.Success, stats)


triage_fields = ns.model('GithubResultTriage', {
    'hash_md5s': fields.List(fields.String(required=True), required=True, description="命中文件指纹列表"),
    'triage_status': fields.String(required=True, description="研判状态: pending | confirmed | false_positive"),
    'note': fields.String(required=False, description="研判备注"),
})


@ns.route('/triage/')
class ARLGithubResultTriage(ARLResource):
    @auth
    @ns.expect(triage_fields)
    def post(self):
        """
        更新命中结果的研判状态（按文件指纹跨任务共享）
        """
        args = self.parse_args(triage_fields)
        hash_md5s = args.get("hash_md5s") or []
        triage_status = (args.get("triage_status") or "").strip()
        note = args.get("note")
        if triage_status not in github_triage.VALID_TRIAGE_STATUSES:
            return utils.build_ret(ErrorMsg.Error, {"error": f"不支持的研判状态: {triage_status}"})
        if not hash_md5s:
            return utils.build_ret(ErrorMsg.Error, {"error": "请至少选择一条命中记录"})

        res = github_triage.set_triage_status(hash_md5s, triage_status, note=note)
        return utils.build_ret(ErrorMsg.Success, res)


ignored_repo_fields = ns.model('GithubIgnoredRepo', {
    'action': fields.String(required=True, description="操作: add | remove"),
    'repo_full_names': fields.List(fields.String(required=True), required=True, description="仓库全名列表"),
    'reason': fields.String(required=False, description="屏蔽原因"),
})


@ns.route('/ignored_repos/')
class ARLGithubIgnoredRepos(ARLResource):
    @auth
    def get(self):
        """
        获取已屏蔽的噪声仓库列表
        """
        items = github_triage.list_ignored_repos()
        return utils.build_ret(ErrorMsg.Success, {"items": items, "total": len(items)})

    @auth
    @ns.expect(ignored_repo_fields)
    def post(self):
        """
        新增或移出屏蔽仓库列表
        """
        args = self.parse_args(ignored_repo_fields)
        action = (args.get("action") or "").strip()
        repos = args.get("repo_full_names") or []
        reason = args.get("reason") or ""
        if action not in ("add", "remove"):
            return utils.build_ret(ErrorMsg.Error, {"error": "action 必须为 add 或 remove"})
        res = github_triage.manage_ignored_repos(action, repos, reason=reason)
        return utils.build_ret(ErrorMsg.Success, res)


export_fields = dict(overview_search_fields)
export_fields['format'] = fields.String(description="导出格式: csv | json", example="csv")


@ns.route('/export/')
class ARLGithubResultExport(ARLResource):
    parser = get_arl_parser(export_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        按当前筛选条件导出代码泄露命中结果（CSV / JSON）
        """
        args = self.parser.parse_args()
        export_format = (args.get("format") or "csv").strip().lower()
        if export_format not in ("csv", "json"):
            export_format = "csv"

        filters = _extract_overview_filters(args)
        content, content_type, base_name = github_triage.export_unified_findings(filters, export_format)
        ext = "json" if export_format == "json" else "csv"
        filename = f"{base_name.rsplit('.', 1)[0]}_{int(time.time())}.{ext}"
        response = make_response(content)
        response.headers['Content-Type'] = content_type
        response.headers['Access-Control-Expose-Headers'] = 'Content-Disposition'
        response.headers['Content-Disposition'] = f'attachment; filename={quote(filename)}'
        return response
