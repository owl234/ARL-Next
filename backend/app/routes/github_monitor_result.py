from flask_restx import fields, Namespace
from app.services import github_triage
from app.utils import get_logger, auth
from . import base_query_fields, ARLResource, get_arl_parser

ns = Namespace('github_monitor_result', description="Github 监控结果详情")

logger = get_logger()

base_search_fields = {
    'path': fields.String(required=False, description="路径名称"),
    'repo_full_name': fields.String(description="仓库名称"),
    'human_content': fields.String(description="内容"),
    'keyword': fields.String(description="关键字"),
    "github_scheduler_id": fields.String(description="Github 监控ID"),
    'github_task_id': fields.String(description="任务ID")
}

base_search_fields.update(base_query_fields)


@ns.route('/')
class ARLGithubMonitorResult(ARLResource):
    parser = get_arl_parser(base_search_fields, location='args')

    @auth
    @ns.expect(parser)
    def get(self):
        """
        Github 监控结果详情
        """
        args = self.parser.parse_args()
        data = self.build_data(args=args, collection='github_monitor_result')
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
