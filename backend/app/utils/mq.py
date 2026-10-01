# backend/app/utils/mq.py
"""
Celery 任务发送统一封装
- 统一任务名、队列、优先级
- 所有漏洞平台任务通过此模块发送
"""

from app import utils

logger = utils.get_logger()


# ═══════════════════════════════════════════════════════════
# 队列常量
# ═══════════════════════════════════════════════════════════

QUEUE_FETCH = "platform_fetch"      # 抓取队列（抓取、检查、提交）
QUEUE_SCAN = "scan"                  # 扫描队列（Nuclei 等）


# ═══════════════════════════════════════════════════════════
# 任务名常量（与 celerytask.py 保持一致）
# ═══════════════════════════════════════════════════════════

TASK_FETCH_ALL = "app.celerytask.vuln_platform_fetch_all"
TASK_FETCH_ONE = "app.celerytask.vuln_platform_fetch_one"
TASK_EXECUTE_SCAN = "app.celerytask.vuln_platform_execute_scan"
TASK_AUTO_SUBMIT = "app.celerytask.vuln_platform_auto_submit"
TASK_CHECK_SCOPE = "app.celerytask.vuln_platform_check_scope"
TASK_COOKIE_CHECK = "app.celerytask.vuln_platform_cookie_check"
TASK_WEEKLY_RESCAN = "app.celerytask.vuln_platform_weekly_rescan"
TASK_DAILY_RESCAN = "app.celerytask.vuln_platform_daily_rescan"


# ═══════════════════════════════════════════════════════════
# 内部发送函数
# ═══════════════════════════════════════════════════════════

def _send(task_name, args=None, kwargs=None,
          queue=QUEUE_FETCH, priority=5):
    """
    统一任务发送入口
    :param task_name: 完整任务名（如 app.celerytask.xxx）
    :param args: 位置参数
    :param kwargs: 关键字参数
    :param queue: 队列名
    :param priority: 优先级（0-9，越高越优先）
    :return: AsyncResult 或 None
    """
    from app.celerytask import celery

    try:
        result = celery.send_task(
            task_name,
            args=args or [],
            kwargs=kwargs or {},
            queue=queue,
            priority=priority,
        )
        logger.info(
            "任务已投递 [{}] {} (task_id={})".format(
                queue, task_name, result.id))
        return result
    except Exception as e:
        logger.error(
            "任务投递失败 [{}] {}: {}".format(
                queue, task_name, e))
        return None


# ═══════════════════════════════════════════════════════════
# 抓取类任务
# ═══════════════════════════════════════════════════════════

def send_fetch_all(priority=7):
    """
    下发全平台抓取任务
    :return: AsyncResult
    """
    return _send(
        TASK_FETCH_ALL,
        queue=QUEUE_FETCH,
        priority=priority,
    )


def send_fetch_one(platform_name, priority=7):
    """
    下发单平台抓取任务
    :param platform_name: 平台名称（butian/vulbox/cnvd/...）
    """
    return _send(
        TASK_FETCH_ONE,
        args=[platform_name],
        queue=QUEUE_FETCH,
        priority=priority,
    )


# ═══════════════════════════════════════════════════════════
# 扫描类任务
# ═══════════════════════════════════════════════════════════

def send_execute_scan(scan_request, priority=5):
    """
    下发扫描任务
    :param scan_request: {
        "project_fingerprint": str,
        "source_platform": str,
        "scope": list[str],
        "scan_config": dict,
        "profile": str,
    }
    """
    return _send(
        TASK_EXECUTE_SCAN,
        args=[scan_request],
        queue=QUEUE_SCAN,
        priority=priority,
    )


# ═══════════════════════════════════════════════════════════
# 提交类任务
# ═══════════════════════════════════════════════════════════

def send_auto_submit(project_fingerprint, priority=8):
    """
    下发自动提交任务（扫描完成后调用）
    :param project_fingerprint: 项目指纹
    """
    return _send(
        TASK_AUTO_SUBMIT,
        args=[project_fingerprint],
        queue=QUEUE_FETCH,
        priority=priority,
    )


# ═══════════════════════════════════════════════════════════
# 检查类任务
# ═══════════════════════════════════════════════════════════

def send_check_scope(priority=6):
    """下发项目范围变化检查任务"""
    return _send(
        TASK_CHECK_SCOPE,
        queue=QUEUE_FETCH,
        priority=priority,
    )


def send_cookie_check(priority=5):
    """下发 Cookie 健康检查任务"""
    return _send(
        TASK_COOKIE_CHECK,
        queue=QUEUE_FETCH,
        priority=priority,
    )


# ═══════════════════════════════════════════════════════════
# 复扫类任务
# ═══════════════════════════════════════════════════════════

def send_weekly_rescan(priority=8):
    """下发每周全量复扫任务"""
    return _send(
        TASK_WEEKLY_RESCAN,
        queue=QUEUE_FETCH,
        priority=priority,
    )


def send_daily_rescan(priority=4):
    """下发每日增量复扫任务"""
    return _send(
        TASK_DAILY_RESCAN,
        queue=QUEUE_FETCH,
        priority=priority,
    )


# ═══════════════════════════════════════════════════════════
# 组合任务：扫描 + 自动提交（Chain）
# ═══════════════════════════════════════════════════════════

def send_scan_with_auto_submit(scan_request, priority=5):
    """
    下发「扫描 → 自动提交」链式任务
    使用 Celery chain 保证顺序执行

    :param scan_request: 同 send_execute_scan
    :return: AsyncResult
    """
    from celery import chain
    from app.celerytask import (
        vuln_platform_execute_scan,
        vuln_platform_auto_submit,
    )

    project_fp = scan_request["project_fingerprint"]

    try:
        pipeline = chain(
            vuln_platform_execute_scan.s(scan_request),
            vuln_platform_auto_submit.si(project_fp),
        )
        result = pipeline.apply_async(
            queue=QUEUE_SCAN, priority=priority)
        logger.info(
            "Chain 已投递: scan → submit "
            "(project={}, task_id={})".format(
                project_fp, result.id))
        return result
    except Exception as e:
        logger.error("Chain 投递失败: {}".format(e))
        return None


# ═══════════════════════════════════════════════════════════
# 调试辅助
# ═══════════════════════════════════════════════════════════

def get_queue_info():
    """
    获取各队列的待处理任务数（需要 RabbitMQ 管理插件）
    仅用于调试
    """
    import os
    import requests

    host = os.environ.get("RABBITMQ_HOST", "localhost")
    port = os.environ.get("RABBITMQ_PORT", "15672")
    user = os.environ.get("RABBITMQ_USER", "admin")
    password = os.environ.get("RABBITMQ_PASS", "admin")

    api = "http://{}:{}/api".format(host, port)
    try:
        resp = requests.get(
            "{}/queues".format(api),
            auth=(user, password), timeout=5)
        if resp.status_code != 200:
            return {}
        result = {}
        for q in resp.json():
            result[q["name"]] = {
                "messages": q.get("messages", 0),
                "consumers": q.get("consumers", 0),
            }
        return result
    except Exception as e:
        logger.warning("获取队列信息失败: {}".format(e))
        return {}