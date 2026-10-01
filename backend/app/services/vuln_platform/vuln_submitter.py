# backend/app/services/vuln_platform/vuln_submitter.py
"""
漏洞自动提交服务
核心策略：从哪个平台获取的项目，检测出的漏洞就提交回该平台
"""

from app import utils
from app.adapters.vuln_platform import get_adapter
from .project_service import ProjectService
from .submit_service import SubmitService
from .vuln_service import VulnService

logger = utils.get_logger()


class VulnSubmitter(object):
    """漏洞自动提交服务"""

    def __init__(self, db=None):
        self.db = db or utils.conn_db()
        self.project_service = ProjectService(self.db)
        self.vuln_service = VulnService(self.db)
        self.submit_service = SubmitService(self.db)

    # ═══════════════════════════════════════════════
    # 来源平台解析
    # ═══════════════════════════════════════════════

    def resolve_source_platform(self, vuln):
        """解析漏洞来源平台"""
        if vuln.get("platform"):
            return vuln["platform"]

        project_fp = vuln.get("project_fingerprint")
        if project_fp:
            project = self.project_service.get(project_fp)
            if project and project.get("platform"):
                return project["platform"]

        target = vuln.get("target_url", "").lower()
        if target:
            platform = self._match_platform_by_target(target)
            if platform:
                return platform

        return self._fallback_route(vuln)

    def _match_platform_by_target(self, target):
        for project in self.project_service.list_active():
            for scope_item in project.get("scope", []):
                if scope_item and scope_item.lower() in target:
                    return project["platform"]
        return None

    def _fallback_route(self, vuln):
        target = vuln.get("target_url", "").lower()
        severity = vuln.get("severity", "").lower()
        if ".edu.cn" in target:
            return "edusrc"
        if any(kw in target for kw in [".gov.cn", ".org.cn"]):
            return "cnvd"
        if severity in ("critical", "high"):
            return "butian"
        return "vulbox"

    # ═══════════════════════════════════════════════
    # 提交
    # ═══════════════════════════════════════════════

    def submit(self, vuln_id, platform=None, force=False):
        """提交单个漏洞"""
        vuln = self.vuln_service.get(vuln_id)
        if not vuln:
            return {"success": False,
                    "message": "漏洞不存在: {}".format(vuln_id)}

        # 检查是否已提交
        existing = self.submit_service.find_success_by_vuln(vuln_id)
        if existing and not force:
            return {"success": False,
                    "message": "漏洞已提交到 {}".format(
                        existing["platform"])}

        # 解析目标平台
        target_platform = platform or self.resolve_source_platform(vuln)

        try:
            adapter = get_adapter(target_platform, db=self.db)
        except ValueError as e:
            return {"success": False,
                    "message": "适配器不可用: {}".format(e)}

        # 执行提交
        try:
            result = adapter.submit_vulnerability(vuln)
        except Exception as e:
            logger.error("[{}] 漏洞 {} 提交异常: {}".format(
                target_platform, vuln_id, e))
            result = {"success": False, "message": str(e)}

        # 记录提交结果
        record = {
            "vuln_id": vuln_id,
            "platform": target_platform,
            "source_platform": vuln.get("platform") or target_platform,
            "project_fingerprint": vuln.get("project_fingerprint"),
            "success": result.get("success", False),
            "platform_vuln_id": result.get("platform_vuln_id"),
            "message": result.get("message", ""),
            "status": "submitted" if result.get("success")
                      else "failed",
        }
        self.submit_service.insert(record)

        # 更新漏洞状态
        self.vuln_service.update_submit_state(
            vuln_id, target_platform,
            "submitted" if result.get("success") else "failed",
            platform_vuln_id=result.get("platform_vuln_id"),
            message=result.get("message"))

        logger.info("漏洞 {} 提交结果: {} → {}".format(
            vuln_id, target_platform,
            "成功" if result.get("success") else "失败"))

        return record

    def batch_submit(self, vuln_ids, platform=None):
        """批量提交"""
        results = {"success": 0, "failed": 0,
                   "by_platform": {}, "details": []}

        for vid in vuln_ids:
            r = self.submit(vid, platform=platform)
            if r.get("success"):
                results["success"] += 1
            else:
                results["failed"] += 1

            p = r.get("platform", "unknown")
            results["by_platform"].setdefault(
                p, {"success": 0, "failed": 0})
            key = "success" if r.get("success") else "failed"
            results["by_platform"][p][key] += 1

            results["details"].append(r)

        return results

    def submit_project_vulns(self, project_fingerprint):
        """提交项目下所有未提交漏洞"""
        project = self.project_service.get(project_fingerprint)
        if not project:
            return {"success": False, "message": "项目不存在"}

        platform = project.get("platform")
        vulns = self.vuln_service.list_pending_submit(
            project_fingerprint)

        if not vulns:
            return {"success": True, "message": "无待提交漏洞",
                    "count": 0}

        return self.batch_submit(
            [v["_id"] for v in vulns], platform=platform)