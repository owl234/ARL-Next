# backend/app/tasks/vuln_platform.py
"""漏洞平台相关 Celery 任务"""

from celery import shared_task

from app import utils
from app.utils.time import utcnow

logger = utils.get_logger()


# ═══════════════════════════════════════════════════════════
# 抓取任务
# ═══════════════════════════════════════════════════════════

@shared_task(queue="platform_fetch", priority=7)
def fetch_all_projects():
    """抓取所有已启用平台"""
    from app.services.vuln_platform import ProjectService

    try:
        service = ProjectService()
        result = service.fetch_all_platforms()
        logger.info("全平台抓取完成: {}".format(result))
        return {"platforms": result}
    except Exception as e:
        logger.error("全平台抓取失败: {}".format(e))
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════
# 扫描任务
# ═══════════════════════════════════════════════════════════

@shared_task(queue="scan", priority=5)
def execute_scan(scan_request):
    """执行扫描任务"""
    from app.services.vuln_platform import (
        ProjectService, TargetService, VulnService,
    )
    from app.services.vuln_platform.scan_thread import (
        nuclei_scan_thread,
    )

    project_fp = scan_request["project_fingerprint"]
    source_platform = scan_request.get("source_platform")
    scope = scan_request["scope"]
    scan_config = scan_request["scan_config"]

    logger.info("执行扫描: project={}, targets={}".format(
        project_fp, len(scope)))

    project_service = ProjectService()
    target_service = TargetService()
    vuln_service = VulnService()

    # 执行扫描
    try:
        findings = nuclei_scan_thread(
            targets=scope,
            scan_config=scan_config,
            project_fingerprint=project_fp,
            source_platform=source_platform,
            concurrency=scan_config.get("max_workers", 10))
    except Exception as e:
        logger.error("扫描任务失败: project={}, error={}".format(
            project_fp, e))
        raise

    # 漏洞落库
    new_count = 0
    for f in findings:
        is_new, _ = vuln_service.insert_or_update_finding(
            f, project_fp, source_platform)
        if is_new:
            new_count += 1

    # 更新项目状态
    project_service.update_scan_state(
        project_fp, status="completed",
        vuln_count=len(findings))

    # 标记目标已扫描
    for t in scope:
        target_doc = target_service.list_pending()  # 简化处理
        # 实际应按 target 值查找
    logger.info("扫描完成: project={}, findings={}, new={}".format(
        project_fp, len(findings), new_count))

    return {
        "project": project_fp,
        "findings": len(findings),
        "new": new_count,
    }


# ═══════════════════════════════════════════════════════════
# 自动提交任务
# ═══════════════════════════════════════════════════════════

@shared_task(queue="platform_fetch", priority=8)
def auto_submit_project_vulns(project_fingerprint):
    """扫描完成后自动提交项目漏洞"""
    from app.services.vuln_platform import VulnSubmitter

    try:
        result = VulnSubmitter().submit_project_vulns(
            project_fingerprint)
        logger.info("项目 {} 自动提交结果: {}".format(
            project_fingerprint, result))
        return result
    except Exception as e:
        logger.error("项目 {} 提交失败: {}".format(
            project_fingerprint, e))
        return {"error": str(e)}


# ═══════════════════════════════════════════════════════════
# 调度任务
# ═══════════════════════════════════════════════════════════

@shared_task(queue="platform_fetch", priority=6)
def dispatch_all_scans(profile="quick"):
    """下发所有项目的扫描"""
    from app.services.vuln_platform import ScanOrchestrator

    try:
        result = ScanOrchestrator().dispatch_all(profile)
        logger.info("批量扫描下发完成: {}".format(len(result)))
        return {"dispatched": len(result), "details": result}
    except Exception as e:
        logger.error("批量扫描下发失败: {}".format(e))
        return {"error": str(e)}