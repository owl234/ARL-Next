from aiohttp import web
import asyncio
import inspect
import logging
import re

logger = logging.getLogger(__name__)

background_tasks = set()

async def watchdog_task(app):
    """异步看门狗：定时轮询 MongoDB 获取最新并发配置并热更新"""
    task_manager = app.get('task_manager')
    # 第一次获取动态信号量，设置兜底默认值 1
    semaphore = task_manager.get_semaphore("recon_task", 1, dynamic=True)
    try:
        from clients.job_runner import db
        while True:
            try:
                db_config = await db.system_config.find_one({"_id": "performance"})
                limit = db_config.get("osint_concurrency", 1) if db_config else 1
                if hasattr(semaphore, "set_limit"):
                    await semaphore.set_limit(limit)
            except Exception as e:
                logger.error(f"Watchdog failed to fetch config: {e}")
            await asyncio.sleep(10)
    except asyncio.CancelledError:
        pass

def submit_recon_job(task_manager, data):
    """将 Recon 任务提交至受信号量限制的协程池"""
    task_id = data.get("task_id")
    existing = task_manager.get_task(task_id)
    if existing is not None and not existing.done():
        logger.info(f"Task {task_id} already in flight, skip duplicate submit.")
        _schedule_syslog(
            task_id, "warning", "任务派发",
            "本次派发被忽略：该任务已在协程池中运行，未重复启动。"
        )
        return existing
    semaphore = task_manager.get_semaphore("recon_task", 1, dynamic=True)
    from clients.job_runner import run_recon_job

    async def bounded_recon_job():
        async with semaphore:
            await run_recon_job(data)

    task = asyncio.create_task(bounded_recon_job())
    background_tasks.add(task)
    task_manager.add_task(task_id, task)

    def handle_task_result(t):
        background_tasks.discard(t)
        # 取消是正常控制流：任务是被 stop 主动终止的，不作为异常上报。
        if t.cancelled():
            logger.info(f"Background task {task_id} cancelled.")
            return
        try:
            t.result()
        except Exception as e:
            logger.error(f"Background task {task_id} crashed: {e}", exc_info=True)
            _schedule_syslog(
                task_id, "error", "任务异常",
                f"测绘协程异常终止，任务未能正常收尾：{e}"
            )
            _schedule_abort(task_id, f"测绘协程异常终止：{e}")

    task.add_done_callback(handle_task_result)
    return task


def _schedule_syslog(task_id, level, title, message):
    """
    在后台协程崩溃的回调中补写运行日志。

    回调运行在事件循环上且可能处于异常收尾路径，统一以独立 Task 异步投递，
    避免阻塞或二次抛出；写库失败仅落 logger。
    """
    if not task_id:
        return

    async def _write():
        try:
            from clients.job_runner import db, curr_date
            await db['syslog'].insert_one({
                "task_id": str(task_id),
                "level": level,
                "title": title,
                "message": message,
                "create_time": curr_date()
            })
        except Exception as log_err:
            logger.error(f"Failed to write syslog for crashed task {task_id}: {log_err}")

    try:
        asyncio.create_task(_write())
    except Exception as e:
        logger.error(f"Failed to schedule syslog write for task {task_id}: {e}")


def _schedule_abort(task_id, message):
    """协程崩溃后显式将任务收敛到 error 终态，避免长期滞留 running。"""
    if not task_id:
        return

    async def _abort():
        try:
            from clients.job_runner import db, curr_date
            from bson import ObjectId
            await db['icp_task'].update_one(
                {"_id": ObjectId(str(task_id)), "status": {"$in": ["waiting", "running"]}},
                {"$set": {"status": "error", "end_time": curr_date(), "error_msg": message}}
            )
        except Exception as abort_err:
            logger.error(f"Failed to abort crashed task {task_id}: {abort_err}")

    try:
        asyncio.create_task(_abort())
    except Exception as e:
        logger.error(f"Failed to schedule abort for task {task_id}: {e}")


def _validate_recon_start_payload(data):
    task_id = data.get("task_id") if isinstance(data, dict) else None
    if not isinstance(task_id, str) or not re.fullmatch(r"[0-9a-fA-F]{24}", task_id):
        return None, web.json_response({"code": 400, "msg": "Invalid task_id"}, status=400)
    task_type = data.get("type")
    if task_type not in ("icp", "tyc"):
        return None, web.json_response({"code": 400, "msg": "Invalid task type"}, status=400)
    # ICP 任务以 target 为查询目标；TYC 任务改由 gid 指定主体，不带 target，
    # 故校验必须按类型区分，否则会误拒全部 TYC 派发。
    if task_type == "icp" and (not isinstance(data.get("target"), str) or not data["target"].strip()):
        return None, web.json_response({"code": 400, "msg": "Invalid target"}, status=400)
    if task_type == "tyc" and not str(data.get("gid") or "").strip():
        return None, web.json_response({"code": 400, "msg": "Invalid gid"}, status=400)
    return task_id, None


async def start_recon(request):
    try:
        data = await request.json()
        task_id, err_resp = _validate_recon_start_payload(data)
        if err_resp is not None:
            return err_resp

        task_manager = request.app.get('task_manager')
        submit_recon_job(task_manager, data)
        return web.json_response({"code": 200, "msg": "Task accepted", "task_id": task_id})
    except Exception as e:
        return web.json_response({"code": 500, "msg": str(e)}, status=500)


async def resume_recon(request):
    try:
        data = await request.json()
        task_id, err_resp = _validate_recon_start_payload(data)
        if err_resp is not None:
            return err_resp

        payload = dict(data)
        payload["resume"] = True
        payload["action"] = "resume"
        task_manager = request.app.get('task_manager')
        submit_recon_job(task_manager, payload)
        return web.json_response({"code": 200, "msg": "Resume accepted", "task_id": task_id})
    except Exception as e:
        return web.json_response({"code": 500, "msg": str(e)}, status=500)


async def backfill_details_recon(request):
    try:
        data = await request.json()
        task_id = data.get("task_id") if isinstance(data, dict) else None
        if not isinstance(task_id, str) or not re.fullmatch(r"[0-9a-fA-F]{24}", task_id):
            return web.json_response({"code": 400, "msg": "Invalid task_id"}, status=400)

        payload = dict(data)
        payload["action"] = "backfill_details"
        task_manager = request.app.get('task_manager')
        submit_recon_job(task_manager, payload)
        return web.json_response({"code": 200, "msg": "Backfill accepted", "task_id": task_id})
    except Exception as e:
        return web.json_response({"code": 500, "msg": str(e)}, status=500)

async def stop_recon(request):
    try:
        data = await request.json()
        task_id = data.get("task_id") if isinstance(data, dict) else None
        if not isinstance(task_id, str) or not re.fullmatch(r"[0-9a-fA-F]{24}", task_id):
            return web.json_response({"code": 400, "msg": "Invalid task_id"}, status=400)
        
        task_manager = request.app.get('task_manager')
        await task_manager.cancel_task(task_id)
        logger.info(f"Task {task_id} cancellation completed via API.")
        return web.json_response({"code": 200, "msg": "Task stopped", "task_id": task_id})
    except Exception as e:
        return web.json_response({"code": 500, "msg": str(e)}, status=500)


async def reconcile_orphan_tasks(app):
    """
    服务启动自愈机制：
    1. 将服务异常重启导致中断的 running 任务置为已停止 (stop)，附注说明供按需手动重启。
    2. 扫描 MongoDB 中残留的 waiting 任务（按创建时间 FIFO 排序），自动重新构建参数并入队排队。
    """
    await asyncio.sleep(1)
    task_manager = app.get('task_manager')
    try:
        import sys
        from clients.job_runner import db, curr_date
        job_runner_mod = sys.modules.get("clients.job_runner")

        # 1. 处置服务异常重启前中断的 running 任务 -> 置为已停止 (stop)，并同步清理资产组更新锁定指针
        interrupted_tasks = await db['icp_task'].find({"status": "running"}).to_list(length=200)
        sync_scope_fn = getattr(job_runner_mod, "_sync_scope_after_task_completion", None)
        for it in interrupted_tasks:
            try:
                it_id = str(it["_id"])
                logger.warning(f"Reconciling interrupted running task {it_id} -> stop")
                await db['icp_task'].update_one(
                    {"_id": it["_id"]},
                    {"$set": {
                        "status": "stop",
                        "end_time": curr_date(),
                        "error_msg": "服务异常重启中断，已自动置为已停止，可按需手动重启"
                    }}
                )
                if inspect.iscoroutinefunction(sync_scope_fn):
                    await sync_scope_fn(it_id, "stop")
                _schedule_syslog(
                    it_id, "warning", "任务中断",
                    "osint-service 异常重启导致本次测绘中断，任务已自动置为已停止，可按需手动重启。"
                )
            except Exception as it_err:
                logger.error(f"Failed to reconcile interrupted task {it.get('_id')}: {it_err}")
                _schedule_syslog(
                    str(it.get("_id")), "error", "任务自愈",
                    f"处理服务重启前中断的任务时发生异常：{it_err}"
                )

        # 2. 扫描残留的 waiting 任务并重新入队排队 (按 FIFO 启动时间正序)
        waiting_tasks = await db['icp_task'].find({"status": "waiting"}).sort("start_time", 1).to_list(length=500)
        if not waiting_tasks:
            logger.info("Startup reconciliation completed: no waiting tasks found.")
            return

        logger.info(f"Startup reconciliation: found {len(waiting_tasks)} waiting tasks to re-enqueue.")

        # 查询天眼查全局配置备用
        general_config = await db['system_config'].find_one({"_id": "general_config"})
        tyc_id = general_config.get("tyc_id", "") if general_config else ""
        tyc_token = general_config.get("tyc_token", "") if general_config else ""

        for wt in waiting_tasks:
            try:
                tid = str(wt["_id"])
                if task_manager.get_task(tid):
                    continue

                query_type = wt.get("query_type", [])
                if isinstance(query_type, str):
                    query_type = [q.strip() for q in query_type.split(',') if q.strip()]

                is_tyc = wt.get("task_type") == "tyc" or "gid" in wt

                if is_tyc:
                    if not tyc_id or not tyc_token:
                        logger.warning(f"Task {tid} requires TYC credentials but none configured. Marking as error.")
                        await db['icp_task'].update_one(
                            {"_id": wt["_id"]},
                            {"$set": {"status": "error", "error_msg": "系统未配置天眼查凭据，自愈恢复失败"}}
                        )
                        _schedule_syslog(
                            tid, "error", "任务自愈",
                            "服务重启后自动恢复失败：系统未配置天眼查凭据，任务已置为异常失败，"
                            "请前往系统设置补充凭据后手动重启。"
                        )
                        continue

                    options = {
                        "task_id": tid,
                        "target": wt.get("target") or f"TYC_{wt.get('gid')}",
                        "gid": wt.get("gid"),
                        "depth": wt.get("depth", 1),
                        "invest_ratio": wt.get("invest_ratio", 0),
                        "query_type": query_type,
                        "enable_icp": wt.get("enable_icp", True),
                        "company_name": wt.get("company_name", ""),
                        "name": wt.get("name", ""),
                        "type": "tyc",
                        "tyc_id": tyc_id,
                        "tyc_token": tyc_token,
                        "resume": bool(wt.get("is_resumed") and wt.get("recon_checkpoint")),
                    }
                else:
                    options = {
                        "task_id": tid,
                        "target": wt.get("target"),
                        "query_type": query_type,
                        "type": "icp",
                        "resume": bool(wt.get("is_resumed") and wt.get("recon_checkpoint")),
                    }

                submit_recon_job(task_manager, options)
                logger.info(f"Re-enqueued waiting task {tid} ({wt.get('name')}) successfully.")
                _schedule_syslog(
                    tid, "info", "任务自愈",
                    "服务重启后已自动将该排队任务重新入队，等待调度执行。"
                )
            except Exception as wt_err:
                logger.error(f"Failed to re-enqueue waiting task {wt.get('_id')}: {wt_err}")
                _schedule_syslog(
                    str(wt.get("_id")), "error", "任务自愈",
                    f"服务重启后自动恢复该排队任务失败：{wt_err}"
                )

    except Exception as e:
        logger.error(f"Failed to reconcile orphan tasks: {e}", exc_info=True)


async def proxy_status(request):
    try:
        from clients.job_runner import db
        from proxy_router import OsintProxyRouter
        router = OsintProxyRouter(db=db)
        await router.sync_from_db(db)
        return web.json_response({
            "code": 200,
            "data": {
                "mode": router.get_mode(),
                "active_exit_id": router.active_exit_id,
                "blocked_exits": router.blocked_exits,
                "earliest_unblock_delay": round(router.earliest_unblock_delay(), 2),
                "node_count": len(router.nodes),
            },
        })
    except Exception as e:
        return web.json_response({"code": 500, "msg": str(e)}, status=500)


async def proxy_reset_cooldown(request):
    try:
        from clients.job_runner import db
        from proxy_router import DIRECT_EXIT_ID, PROXY_RUNTIME_DOC_ID, bump_global_reset_epoch
        import time as _time
        bump_global_reset_epoch()
        await db["system_config"].update_one(
            {"_id": PROXY_RUNTIME_DOC_ID},
            {"$set": {
                "blocked_exits": {},
                "active_exit_id": DIRECT_EXIT_ID,
                "last_switch_reason": "管理员手动重置冷却状态",
                "last_switch_at": int(_time.time()),
                "updated_at": int(_time.time()),
            }},
            upsert=True,
        )
        return web.json_response({"code": 200, "msg": "Cooldown reset"})
    except Exception as e:
        return web.json_response({"code": 500, "msg": str(e)}, status=500)


def setup_recon_routes(app):
    app.router.add_post("/api/v1/recon/start", start_recon)
    app.router.add_post("/api/v1/recon/resume", resume_recon)
    app.router.add_post("/api/v1/recon/backfill_details", backfill_details_recon)
    app.router.add_post("/api/v1/recon/stop", stop_recon)
    app.router.add_get("/api/v1/recon/proxy_status", proxy_status)
    app.router.add_post("/api/v1/recon/proxy_reset_cooldown", proxy_reset_cooldown)

    async def start_watchdog(app):
        app["watchdog_task"] = asyncio.create_task(watchdog_task(app))

    async def cleanup_watchdog(app):
        if "watchdog_task" in app:
            app["watchdog_task"].cancel()
            try:
                await app["watchdog_task"]
            except asyncio.CancelledError:
                pass

    async def start_reconciliation(app):
        app["reconciliation_task"] = asyncio.create_task(reconcile_orphan_tasks(app))

    async def cleanup_reconciliation(app):
        if "reconciliation_task" in app:
            app["reconciliation_task"].cancel()
            try:
                await app["reconciliation_task"]
            except asyncio.CancelledError:
                pass

    app.on_startup.append(start_watchdog)
    app.on_startup.append(start_reconciliation)
    app.on_cleanup.append(cleanup_watchdog)
    app.on_cleanup.append(cleanup_reconciliation)
