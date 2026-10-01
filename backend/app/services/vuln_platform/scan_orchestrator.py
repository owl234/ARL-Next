# backend/app/services/vuln_platform/scan_orchestrator.py
"""
分阶段扫描编排服务
- 负责扫描任务的准备、下发
- 不执行实际扫描（由 Celery Worker 执行）
"""

from app import utils
from app.utils import mq
from app.models import ProjectModel
from .project_service import ProjectService
from .target_service import TargetService

logger = utils.get_logger()


# ═══════════════════════════════════════════════════════════
# 扫描策略配置
# ═══════════════════════════════════════════════════════════

SCAN_PROFILES = {
    "quick": {
        "name": "快速侦察",
        "nuclei_severity": "critical,high",
        "nuclei_tags": "misconfiguration,technologies",
        "max_workers": 10,
        "priority": 9,
        "auto_submit": True,
    },
    "full": {
        "name": "深度扫描",
        "nuclei_severity": "critical,high,medium",
        "nuclei_tags": "",
        "max_workers": 15,
        "priority": 5,
        "auto_submit": True,
    },
    "incremental": {
        "name": "增量复扫",
        "nuclei_severity": "critical,high",
        "nuclei_tags": "misconfiguration",
        "max_workers": 8,
        "priority": 3,
        "auto_submit": True,
    },
}


# ═══════════════════════════════════════════════════════════
# ScanOrchestrator
# ═══════════════════════════════════════════════════════════

class ScanOrchestrator(object):
    """分阶段扫描编排服务"""

    def __init__(self, db=None):
        self.db = db or utils.conn_db()
        self.project_service = ProjectService(self.db)
        self.target_service = TargetService(self.db)

    # ═══════════════════════════════════════════════
    # 核心：下发扫描
    # ═══════════════════════════════════════════════

    def dispatch_scan(self, project_fingerprint, profile="quick",
                       auto_submit=None):
        """
        下发扫描任务
        :param project_fingerprint: 项目指纹
        :param profile: 扫描策略（quick/full/incremental）
        :param auto_submit: 是否自动提交（None 则用 profile 默认值）
        :return: {"dispatched": bool, ...}
        """
        # 1. 校验策略
        scan_config = SCAN_PROFILES.get(profile)
        if not scan_config:
            logger.warning("未知扫描策略: {}".format(profile))
            return {"dispatched": False,
                    "reason": "unknown_profile"}

        # 2. 校验项目
        project = self.project_service.get(project_fingerprint)
        if not project:
            return {"dispatched": False,
                    "reason": "project_not_found"}

        # 3. 获取待扫描目标
        targets = self.target_service.list_pending(
            project_fingerprint)
        if not targets:
            logger.info("项目 {} 无待扫描目标".format(
                project_fingerprint))
            return {"dispatched": False,
                    "reason": "no_pending_targets"}

        scope = [t["target"] for t in targets]
        source_platform = project.get("platform")

        # 4. 构造扫描请求
        scan_request = {
            "project_fingerprint": project_fingerprint,
            "source_platform": source_platform,
            "scope": scope,
            "scan_config": scan_config,
            "profile": profile,
        }

        # 5. 决定是否自动提交
        if auto_submit is None:
            auto_submit = scan_config.get("auto_submit", True)

        # 6. 下发任务
        try:
            if auto_submit:
                result = mq.send_scan_with_auto_submit(
                    scan_request,
                    priority=scan_config.get("priority", 5))
            else:
                result = mq.send_execute_scan(
                    scan_request,
                    priority=scan_config.get("priority", 5))

            if not result:
                return {"dispatched": False,
                        "reason": "mq_send_failed"}
        except Exception as e:
            logger.error("扫描任务下发失败: {}".format(e))
            return {"dispatched": False,
                    "reason": "mq_error",
                    "error": str(e)}

        # 7. 更新项目状态
        self.project_service.update_scan_state(
            project_fingerprint,
            phase=profile, status="dispatched")

        logger.info(
            "扫描任务已下发: project={}, profile={}, "
            "targets={}, auto_submit={}".format(
                project_fingerprint, profile,
                len(scope), auto_submit))

        return {
            "dispatched": True,
            "profile": profile,
            "source_platform": source_platform,
            "target_count": len(scope),
            "auto_submit": auto_submit,
            "task_id": result.id if result else None,
        }

    # ═══════════════════════════════════════════════
    # 便捷方法
    # ═══════════════════════════════════════════════

    def quick_recon(self, project_fingerprint):
        """快速侦察"""
        return self.dispatch_scan(
            project_fingerprint, "quick")

    def full_scan(self, project_fingerprint):
        """深度扫描"""
        return self.dispatch_scan(
            project_fingerprint, "full")

    def incremental_rescan(self, project_fingerprint):
        """增量复扫"""
        return self.dispatch_scan(
            project_fingerprint, "incremental")

    # ═══════════════════════════════════════════════
    # 批量下发
    # ═══════════════════════════════════════════════

    def dispatch_all(self, profile="quick"):
        """
        下发所有活跃项目的扫描
        :return: [{"project": str, "dispatched": bool, ...}, ...]
        """
        projects = self.project_service.list_active()
        results = []

        for p in projects:
            fingerprint = p["fingerprint"]
            r = self.dispatch_scan(fingerprint, profile)
            results.append({
                "project": fingerprint,
                "platform": p.get("platform"),
                **r,
            })

        dispatched = sum(
            1 for r in results if r.get("dispatched"))
        logger.info(
            "批量扫描下发: {}/{} 个项目".format(
                dispatched, len(projects)))

        return results

    # ═══════════════════════════════════════════════
    # 定时复扫
    # ═══════════════════════════════════════════════

    def weekly_full_rescan(self):
        """每周全量复扫"""
        return self.dispatch_all(profile="full")

    def daily_incremental_rescan(self):
        """每日增量复扫"""
        return self.dispatch_all(profile="incremental")

    # ═══════════════════════════════════════════════
    # 范围变化检查
    # ═══════════════════════════════════════════════

    def check_and_rescan(self, project_fingerprint):
        """
        检查项目范围变化，有变化则触发增量复扫
        :return: {"dispatched": bool, ...}
        """
        from app.adapters.vuln_platform import get_adapter
        from app.adapters.vuln_platform.dedup import (
            IncrementalDeduplicator,
        )

        # 1. 获取项目
        project = self.project_service.get(project_fingerprint)
        if not project:
            return {"dispatched": False,
                    "reason": "project_not_found"}

        platform = project.get("platform")
        project_id = project.get("project_id")
        if not platform or not project_id:
            return {"dispatched": False,
                    "reason": "missing_platform_info"}

        # 2. 拉取平台最新范围
        try:
            adapter = get_adapter(platform, db=self.db)
            new_scope = adapter.fetch_scope(project_id)
        except Exception as e:
            logger.error(
                "[{}] 获取范围失败: {}".format(platform, e))
            return {"dispatched": False,
                    "reason": "fetch_failed",
                    "error": str(e)}

        if not new_scope:
            return {"dispatched": False,
                    "reason": "empty_scope"}

        # 3. 计算新增目标
        current_fps = [
            IncrementalDeduplicator.compute_subdomain_fingerprint(s)
            for s in new_scope
        ]
        new_fps = self.project_service.get_new_assets(
            project_fingerprint, current_fps)

        if not new_fps:
            logger.debug("项目 {} 无新增资产".format(
                project_fingerprint))
            return {"dispatched": False,
                    "reason": "no_changes"}

        # 4. 导入新目标
        added = self.target_service.upsert_from_project(
            project_fingerprint, platform, new_scope)

        logger.info(
            "项目 {} 发现 {} 个新目标".format(
                project_fingerprint, added))

        # 5. 触发增量复扫
        return self.incremental_rescan(project_fingerprint)

    def check_all_projects(self):
        """检查所有活跃项目的范围变化"""
        projects = self.project_service.list_active()
        results = []

        for p in projects:
            r = self.check_and_rescan(p["fingerprint"])
            if r.get("dispatched"):
                results.append({
                    "project": p["fingerprint"],
                    **r,
                })

        logger.info(
            "范围检查完成: {}/{} 个项目有变化".format(
                len(results), len(projects)))

        return {
            "projects_with_changes": len(results),
            "details": results,
        }