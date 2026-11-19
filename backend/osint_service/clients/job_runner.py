import logging
import asyncio
import time
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson import ObjectId
from .tyc_async import AsyncTycClient
import re
import random

logger = logging.getLogger(__name__)
MONGO_URI = "mongodb://admin:admin@mongodb:27017/?authSource=admin"
client = AsyncIOMotorClient(MONGO_URI)
db = client['arl']

def curr_date():
    tz = timezone(timedelta(hours=8))
    return datetime.now(tz).strftime("%Y-%m-%d %H:%M:%S")


async def _resolve_system_proxy(options=None):
    """
    读取系统全局代理配置 (system_config.general_config.proxy_url)：
    1. 优先使用任务派发 options 中携带的 proxy_url；
    2. 兜底实时查询 MongoDB system_config 集合中的 general_config.proxy_url。
    """
    raw_proxy = ""
    if isinstance(options, dict):
        raw_proxy = str(options.get("proxy_url") or "").strip()
    if not raw_proxy:
        try:
            doc = await db['system_config'].find_one({"_id": "general_config"}, {"proxy_url": 1})
            if doc and doc.get("proxy_url"):
                raw_proxy = str(doc.get("proxy_url") or "").strip()
        except Exception as e:
            logger.warning(f"Failed to read proxy_url from system_config: {e}")
    if not raw_proxy:
        return None
    if "://" not in raw_proxy:
        raw_proxy = f"http://{raw_proxy}"
    return raw_proxy


# 熔断等待上限：超过此值说明 IP 被连续封禁，等待无意义，直接跳过保任务收尾
WAF_WAIT_MAX_SECONDS = 300


async def _wait_waf_cooldown_once(myicp, task_id, scene, insert_syslog=None):
    """
    熔断命中后等待冷却结束再试一次（仅一次，不循环）。

    语义：此前是命中即 continue 永久跳过该类型，导致大任务限流期内
    数据整段丢失；现改为睡到冷却结束（至多等 WAF_WAIT_MAX_SECONDS），
    醒后直接返回 True 由调用方正常发起查询，不再二次检查。
    等待期间任务被手动停止，由调用方循环头状态检查负责退出。
    返回 True=已等待可继续查询，False=无需等待或无需重试直接跳过。
    """
    delay_fn = getattr(myicp, "get_earliest_unblock_delay", None)
    if callable(delay_fn):
        try:
            wait = float(delay_fn())
        except (TypeError, ValueError):
            wait = 0.0
    else:
        block_ts = getattr(myicp, "_waf_block_ts", 0.0) or 0.0
        cooldown = getattr(myicp, "waf_cooldown", WAF_WAIT_MAX_SECONDS) or WAF_WAIT_MAX_SECONDS
        try:
            wait = float(block_ts) + float(cooldown) - time.time()
        except (TypeError, ValueError):
            return False
    if wait <= 0:
        return True
    if wait > WAF_WAIT_MAX_SECONDS:
        return False
    msg = f"{scene}命中熔断，等待 {int(wait)}s 后重试一次"
    logger.info(f"Task {task_id} {msg}")
    if insert_syslog is not None:
        try:
            await insert_syslog("info", scene, msg)
        except Exception:
            pass
    await asyncio.sleep(wait)
    return True


async def _claim_recon_task(task_id, allowed_statuses=("waiting",), is_resume=False):
    status_filter = allowed_statuses[0] if len(allowed_statuses) == 1 else {"$in": list(allowed_statuses)}
    set_fields = {"status": "running"}
    if is_resume:
        set_fields["end_time"] = "-"
        set_fields["error_msg"] = ""
    else:
        set_fields["start_time"] = curr_date()
    result = await db['icp_task'].update_one(
        {"_id": ObjectId(task_id), "status": status_filter},
        {"$set": set_fields}
    )
    return result.matched_count == 1


async def _build_osint_proxy_router(options=None, syslog_cb=None, service_scope=""):
    """初始化任务级 OSINT 多节点路由器，兼容 proxy_bundle 与 MongoDB 兜底同步。"""
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from proxy_router import OsintProxyRouter
    bundle = options.get("proxy_bundle") if isinstance(options, dict) else None
    legacy_proxy = options.get("proxy_url") if isinstance(options, dict) else None
    router = OsintProxyRouter(
        bundle=bundle,
        db=db,
        legacy_proxy=legacy_proxy,
        syslog_cb=syslog_cb,
        service_scope=service_scope,
    )
    await router.sync_from_db(db)
    return router


def _sanitize_options_for_log(options):
    """脱敏 run_recon_job 入口日志，严禁将代理明文密码或 tyc_token 写入控制台/日志文件。"""
    if not isinstance(options, dict):
        return options
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from proxy_router import mask_proxy_url_secret
    except Exception:
        mask_proxy_url_secret = lambda u: "***" if u else ""

    safe = {}
    for k, v in options.items():
        if k in ("tyc_token", "token", "password", "secret"):
            safe[k] = "***" if v else ""
        elif k == "tyc_id":
            s_val = str(v or "")
            safe[k] = (s_val[:3] + "***") if len(s_val) > 3 else ("***" if s_val else "")
        elif k == "proxy_url":
            safe[k] = mask_proxy_url_secret(v) if v else ""
        elif k == "proxy_bundle" and isinstance(v, dict):
            pol = v.get("policy") or {}
            nodes = v.get("nodes") or []
            safe[k] = {
                "mode": pol.get("mode", "direct_only"),
                "node_count": len(nodes) if isinstance(nodes, list) else 0,
            }
        else:
            safe[k] = v
    return safe


async def _task_is_running(task_id):
    task = await db['icp_task'].find_one({"_id": ObjectId(task_id)}, {"status": 1})
    return task is not None and task.get("status") == "running"

async def run_recon_job(options):
    logger.info(f"Entering run_recon_job with options: {_sanitize_options_for_log(options)}")
    action = options.get("action") or ("resume" if options.get("resume") else "start")
    if action == "backfill_details":
        await run_backfill_details_job(options)
        return
    recon_type = options.get("type", "tyc")
    if recon_type == "tyc":
        await run_tyc_job(options)
    elif recon_type == "icp":
        await run_icp_job(options)


async def _sync_scope_after_task_completion(task_id, task_status, error_msg=""):
    try:
        scope_doc = await db['asset_scope'].find_one({"updating_icp_task_id": str(task_id)})
        if scope_doc:
            if task_status == "done":
                await db['asset_scope'].update_one(
                    {"_id": scope_doc["_id"], "updating_icp_task_id": str(task_id)},
                    {
                        "$set": {"synced_icp_task_id": str(task_id)},
                        "$unset": {
                            "updating_icp_task_id": "",
                            "last_update_error": "",
                            "last_update_error_task_id": "",
                            "last_update_error_time": ""
                        }
                    }
                )
                logger.info(f"Promoted updating_icp_task_id {task_id} to synced_icp_task_id for scope {scope_doc['_id']}")
            elif task_status == "error":
                await db['asset_scope'].update_one(
                    {"_id": scope_doc["_id"], "updating_icp_task_id": str(task_id)},
                    {
                        "$set": {
                            "last_update_error": error_msg or "后台测绘任务执行失败",
                            "last_update_error_task_id": str(task_id),
                            "last_update_error_time": curr_date()
                        },
                        "$unset": {"updating_icp_task_id": ""}
                    }
                )
                logger.warning(f"Cleared updating_icp_task_id {task_id} after error for scope {scope_doc['_id']}")
            elif task_status == "stop":
                await db['asset_scope'].update_one(
                    {"_id": scope_doc["_id"], "updating_icp_task_id": str(task_id)},
                    {"$unset": {"updating_icp_task_id": ""}}
                )
                logger.warning(f"Cleared updating_icp_task_id {task_id} for scope {scope_doc['_id']}")
    except Exception as e:
        logger.error(f"_sync_scope_after_task_completion error: {e}")


async def _finish_recon_task(task_id, task_status, update_data):
    result = await db['icp_task'].update_one(
        {"_id": ObjectId(task_id), "status": "running"}, update_data
    )
    # 停止或删除后到达的旧结果不能切换资产组当前数据。
    if result.matched_count:
        err_msg = ""
        if isinstance(update_data, dict):
            err_msg = (update_data.get("$set") or {}).get("error_msg", "")
        await _sync_scope_after_task_completion(task_id, task_status, error_msg=err_msg)


async def _abort_recon_task(task_id, title, message):
    """
    派发阶段的致命异常收尾：显式将任务置为 error 并补写运行日志。

    任务在异常退出前可能已被 _claim_recon_task 置为 running，若不收尾会永久停留
    在"进行中"；同时派发阶段的异常发生在 insert_syslog 闭包建立之前，无法复用，
    故在此直接写入 syslog 集合，保证任务详情运行日志可见。
    """
    try:
        res = await db['icp_task'].update_one(
            {"_id": ObjectId(task_id), "status": {"$in": ["waiting", "running"]}},
            {"$set": {
                "status": "error",
                "end_time": curr_date(),
                "error_msg": message
            }}
        )
        if getattr(res, "matched_count", 0):
            await _sync_scope_after_task_completion(task_id, "error", error_msg=message)
    except Exception as abort_err:
        logger.error(f"Failed to abort recon task {task_id}: {abort_err}")
    try:
        await db['syslog'].insert_one({
            "task_id": task_id,
            "level": "error",
            "title": title,
            "message": message,
            "create_time": curr_date()
        })
    except Exception as log_err:
        logger.error(f"Failed to write abnormal syslog for task {task_id}: {log_err}")


async def _log_rejected_claim(task_id, title):
    """任务未被受理(重复派发或状态非 waiting)：仅补写运行日志，不改变既有状态。"""
    try:
        current = await db['icp_task'].find_one({"_id": ObjectId(task_id)}, {"status": 1})
    except Exception:
        current = None
    status_label = (current or {}).get("status", "未知")
    try:
        await db['syslog'].insert_one({
            "task_id": task_id,
            "level": "warning",
            "title": title,
            "message": f"本次派发未被受理：任务当前状态为 [{status_label}]，非排队中；"
                       f"通常为重复派发或已被其他 Worker 接管，本条记录不代表任务失败。",
            "create_time": curr_date()
        })
    except Exception as log_err:
        logger.error(f"Failed to write rejected-claim syslog for task {task_id}: {log_err}")


async def run_icp_job(options):
    task_id = options.get("task_id")
    target = options.get("target")
    query_types = options.get("query_type", [])
    is_resume = bool(options.get("resume"))
    if not task_id or not target:
        logger.error(f"Missing required ICP params for task {task_id}")
        if task_id:
            await _abort_recon_task(task_id, "ICP查询", "任务派发参数不完整(缺少 task_id 或查询目标)，无法启动查询")
        return

    allowed = ("waiting", "stop", "error") if is_resume else ("waiting",)
    if not await _claim_recon_task(task_id, allowed_statuses=allowed, is_resume=is_resume):
        logger.warning(f"ICP task {task_id} claim rejected (already running or not in claimable state)")
        await _log_rejected_claim(task_id, "ICP查询")
        return

    total_assets = 0
    error_msg = []
    counts = {"web": 0, "app": 0, "mapp": 0, "kapp": 0}
    completed_qts = set()
    if is_resume:
        task_doc = await db['icp_task'].find_one({"_id": ObjectId(task_id)}, {"recon_checkpoint": 1, "statistic": 1})
        cp = (task_doc or {}).get("recon_checkpoint") or {}
        completed_qts = set(cp.get("completed_qts") or [])
        # 清理未完成维度的半成品记录并按已完成维度精确重算计数，防止中途中断维度在续跑时产生重复记录与统计双计
        uncompleted_qts = [q for q in query_types if q not in completed_qts]
        if uncompleted_qts:
            try:
                await db['icp_asset'].delete_many({"task_id": task_id, "query_type": {"$in": uncompleted_qts}})
            except Exception as del_err:
                logger.warning(f"Failed to clean partial icp_asset for resume {task_id}: {del_err}")
        stat = (task_doc or {}).get("statistic") or {}
        for k in counts:
            if k in completed_qts:
                try:
                    existing_cnt = await db['icp_asset'].count_documents({"task_id": task_id, "query_type": k})
                except Exception:
                    existing_cnt = int(stat.get(f"{k}_cnt") or 0)
                counts[k] = existing_cnt if existing_cnt > 0 else int(stat.get(f"{k}_cnt") or 0)
            else:
                counts[k] = 0
        total_assets = sum(counts.values())
    
    # We must import ymicp dynamically since we are in clients/
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from ymicp import beian

    try:
        myicp = beian()
    except Exception as init_icp_err:
        logger.error(f"Failed to initialize beian for ICP job {task_id}: {init_icp_err}")
        await _abort_recon_task(
            task_id, "ICP查询",
            f"工信部备案查询模块初始化失败，任务无法执行：{init_icp_err}"
        )
        return

    handlers = {
        "web": myicp.ymWeb,
        "app": myicp.ymApp,
        "mapp": myicp.ymMiniApp,
        "kapp": myicp.ymKuaiApp,
    }
    
    async def insert_syslog(level, title, message):
        log_doc = {
            "task_id": task_id,
            "level": level,
            "title": title,
            "message": message,
            "create_time": curr_date()
        }
        try:
            await db['syslog'].insert_one(log_doc)
        except Exception:
            pass

    async def update_stats():
        await db['icp_task'].update_one({"_id": ObjectId(task_id)}, {"$set": {"statistic": {
            "asset_cnt": total_assets,
            "web_cnt": counts.get("web", 0),
            "app_cnt": counts.get("app", 0),
            "mapp_cnt": counts.get("mapp", 0),
            "kapp_cnt": counts.get("kapp", 0)
        }}})

    sys_proxy = await _resolve_system_proxy(options)
    proxy_router = await _build_osint_proxy_router(options, syslog_cb=insert_syslog, service_scope="miit")
    if hasattr(myicp, "attach_proxy_router"):
        myicp.attach_proxy_router(proxy_router)
    if proxy_router.has_structured_policy and proxy_router.get_mode() != "direct_only":
        await insert_syslog(
            "info", "出口策略",
            f"OSINT 出口策略模式: {proxy_router.get_mode()}，已绑定备用代理节点 {len(proxy_router.nodes)} 个"
        )
    if is_resume:
        await insert_syslog("info", "断点续跑", f"ICP 任务从断点恢复执行，已完成维度: {sorted(completed_qts) or '无'}")
    else:
        await insert_syslog("info", "ICP查询", f"任务开始运行，目标: {target}，类型: {query_types}")

    try:
        for idx, qt in enumerate(query_types):
            if qt in completed_qts:
                continue
            # 实时检测任务是否被主动终止
            task_info = await db['icp_task'].find_one({"_id": ObjectId(task_id)}, {"status": 1})
            if not task_info or task_info.get("status") != "running":
                await insert_syslog("warning", "任务中止", "检测到 ICP 查询任务已被手动停止，退出执行流程。")
                logger.info(f"ICP task {task_id} manually stopped.")
                return

            if idx > 0:
                await asyncio.sleep(random.uniform(2.0, 5.0))
                
            if qt in handlers:
                try:
                    # 全局 WAF 熔断：等待冷却后重试一次（仅一次），而非永久跳过该维度
                    _waf_check = getattr(myicp, "_is_global_waf_blocked", None)
                    if callable(_waf_check) and _waf_check():
                        waited = await _wait_waf_cooldown_once(myicp, task_id, f"{qt}查询")
                        if not waited:
                            error_msg.append(f"{qt}: 出口网络被创宇盾封禁，跳过该维度查询")
                            await insert_syslog("warning", f"{qt}查询", "检测到出口网络触发创宇盾封禁，跳过该维度查询，稍后可重跑补全")
                            continue
                        # 长等待后复查任务状态：等待期间用户可能已手动停止
                        if not await _task_is_running(task_id):
                            return
                    await insert_syslog("info", f"{qt}查询", f"开始获取 {qt} 资产数据...")
                    dim_state = {"page_persisted": False, "count": 0}
                    dataid_to_docid = {}
                    if hasattr(myicp, "attach_task_hooks"):
                        async def _icp_progress_cb(_sp, _stage, message, _qt=qt):
                            await insert_syslog("info", f"{_qt}查询", message)

                        async def _icp_page_cb(_sp, items_batch, _page_num, _total_pages, _qt=qt, _state=dim_state, _id_map=dataid_to_docid):
                            nonlocal total_assets
                            if not await _task_is_running(task_id):
                                return
                            docs = []
                            for asset in items_batch:
                                doc = dict(asset)
                                doc.pop('_id', None)
                                doc_id = ObjectId()
                                doc['_id'] = doc_id
                                doc['task_id'] = task_id
                                doc['query_type'] = _qt
                                doc['source'] = 'icp'
                                if doc.get('dataId') is not None:
                                    _id_map[str(doc['dataId'])] = doc_id
                                docs.append(doc)
                            if not docs:
                                return
                            _state["page_persisted"] = True
                            await db['icp_asset'].insert_many(docs, ordered=False)
                            _state["count"] += len(docs)
                            total_assets += len(docs)
                            counts[_qt] += len(docs)
                            await update_stats()

                        async def _icp_detail_cb(_sp, enriched_items, _qt=qt, _id_map=dataid_to_docid):
                            if not await _task_is_running(task_id):
                                return
                            for item in enriched_items:
                                did = str(item.get("dataId") or "").strip()
                                fields = {
                                    k: v for k, v in item.items()
                                    if k not in ("_id", "task_id", "query_type") and v not in (None, "")
                                }
                                if not fields:
                                    continue
                                sn = (item.get("serviceName") or item.get("name") or item.get("appName") or "").strip()
                                if sn:
                                    fields["serviceName"] = sn
                                    fields.setdefault("name", sn)
                                    if _qt == "app":
                                        fields["appName"] = sn
                                if did and did in _id_map:
                                    await db['icp_asset'].update_one({"_id": _id_map[did]}, {"$set": fields})
                                elif did:
                                    await db['icp_asset'].update_one(
                                        {"task_id": task_id, "query_type": _qt, "dataId": item.get("dataId")},
                                        {"$set": fields},
                                    )

                        async def _icp_should_stop_cb():
                            return not await _task_is_running(task_id)

                        myicp.attach_task_hooks(
                            progress_cb=_icp_progress_cb,
                            page_cb=_icp_page_cb,
                            detail_cb=_icp_detail_cb,
                            should_stop_cb=_icp_should_stop_cb,
                            wait_on_detail_waf=True,
                        )

                    try:
                        res = await handlers[qt](target, "", "", proxy=sys_proxy)
                    finally:
                        if hasattr(myicp, "attach_task_hooks"):
                            myicp.attach_task_hooks()

                    if not await _task_is_running(task_id):
                        return
                    if res.get("code") == 200 and res.get("params"):
                        if res["params"].get("_stopped"):
                            return
                        assets = res["params"].get("list", [])
                        if not dim_state["page_persisted"]:
                            if assets:
                                for asset in assets:
                                    asset.pop('_id', None)
                                    asset['task_id'] = task_id
                                    asset['query_type'] = qt
                                    asset.setdefault('source', 'icp')
                                await db['icp_asset'].insert_many(assets, ordered=False)
                            total_assets += len(assets)
                            counts[qt] += len(assets)
                            await update_stats()
                            assets_count = len(assets)
                        else:
                            assets_count = dim_state["count"]

                        await insert_syslog("info", f"{qt}查询", f"获取完成，共计 {assets_count} 条资产")

                        # 详情降级/上限截断可观测：上游在 params 上回传缺口与跳过统计，避免"任务成功但列大面积空白"
                        missing = res["params"].get("_detail_missing") or 0
                        skipped_cap = res["params"].get("_detail_skipped_cap") or 0
                        circuit_break = bool(res["params"].get("_detail_circuit_break") or res["params"].get("_detail_waf"))
                        if missing or skipped_cap or circuit_break:
                            reasons = []
                            if res["params"].get("_detail_waf"):
                                reasons.append("触发创宇盾风控熔断")
                            elif circuit_break:
                                reasons.append("详情接口连续失败触发保护熔断")
                            if skipped_cap > 0:
                                reasons.append(f"受单批详情上限控制跳过 {skipped_cap} 条详情查询")
                            if not reasons:
                                reasons.append("详情接口未返回有效数据")
                            reason_text = "；".join(reasons)
                            if missing and not (skipped_cap > 0 and not circuit_break and missing == skipped_cap):
                                error_msg.append(f"{qt}: {reason_text}，{missing} 条详情缺失")
                            await insert_syslog(
                                "warning", f"{qt}查询",
                                f"数据已入库（基础备案号已保留），部分详情未补全：共 {missing} 条无详情（{reason_text}）"
                            )
                        completed_qts.add(qt)
                        await db['icp_task'].update_one(
                            {"_id": ObjectId(task_id)},
                            {"$set": {"recon_checkpoint": {"completed_qts": sorted(completed_qts), "updated_at": curr_date()}}}
                        )
                    elif res.get("code") != 200:
                        err_text = res.get('msg') or res.get('message') or 'error'
                        error_msg.append(f"{qt}: {err_text}")
                        await insert_syslog("warning", f"{qt}查询", f"接口返回异常: {err_text}")
                except Exception as e:
                    logger.error(f"ICP Query exception for {qt}: {e}")
                    error_msg.append(f"{qt} error: {str(e)}")
                    await insert_syslog("error", f"{qt}查询", f"执行过程发生异常: {str(e)}")
    finally:
        cleanup_fn = getattr(myicp, "cleanup", None)
        if callable(cleanup_fn):
            try:
                await cleanup_fn()
            except Exception:
                pass
        
    # 终态判定口径（与 TYC 任务保持一致）：
    # 只要成功抓取到资产即视为完成，确保前端【同步】资产组按钮畅通；
    # 仅当未入库任何资产且存在致命错误时，才标记为异常失败。
    task_status = "done" if total_assets > 0 else ("error" if error_msg else "done")
    all_qts_completed = all(q in completed_qts for q in query_types)
    update_data = {
        "$set": {
            "status": task_status,
            "end_time": curr_date(),
            "statistic": {
                "asset_cnt": total_assets,
                "web_cnt": counts["web"],
                "app_cnt": counts["app"],
                "mapp_cnt": counts["mapp"],
                "kapp_cnt": counts["kapp"]
            },
            "recon_checkpoint": {
                "completed_qts": sorted(completed_qts),
                "completed": bool(task_status == "done" and all_qts_completed),
                "updated_at": curr_date(),
            },
        }
    }
    if error_msg:
        update_data["$set"]["error_msg"] = "; ".join(error_msg)
    await _finish_recon_task(task_id, task_status, update_data)
    await insert_syslog("info", "任务完成", f"ICP查询任务执行结束，共获取 {total_assets} 条资产")
    logger.info(f"ICP query task {task_id} completed.")


def _apply_nested_tyc_icp_detail(item, detail_key):
    """提取 TYC appIcpRecordDetail / miniProgramIcpRecordDetail 嵌套结构中的主体与审批字段"""
    detail = item.get(detail_key)
    if not isinstance(detail, dict):
        return
    subj = detail.get('icpFilingSubjectInformation') or {}
    if isinstance(subj, dict):
        if not item.get('unitName') and subj.get('organizingName'):
            item['unitName'] = subj['organizingName']
        if not item.get('mainLicence') and subj.get('mainLicence'):
            item['mainLicence'] = subj['mainLicence']
        if not item.get('companyType') and subj.get('natureName'):
            item['companyType'] = subj['natureName']
        if not item.get('natureName') and subj.get('natureName'):
            item['natureName'] = subj['natureName']
    svc = detail.get('icpFilingServiceInformation') or {}
    if isinstance(svc, dict):
        if not item.get('serviceName') and svc.get('serviceName'):
            item['serviceName'] = svc['serviceName']
        if not item.get('serviceLicence') and svc.get('serviceLicence'):
            item['serviceLicence'] = svc['serviceLicence']
        if not item.get('contentTypeName') and svc.get('contentTypeName'):
            item['contentTypeName'] = svc['contentTypeName']
    if not item.get('contentTypeName') and detail.get('contentTypeName'):
        item['contentTypeName'] = detail['contentTypeName']
    if not item.get('mainLicence') and detail.get('mainLicence'):
        item['mainLicence'] = detail['mainLicence']


def _normalize_tyc_asset(item, query_type, company_name=None):
    """TYC 资产入库前规整核心别名，提升底层统一性"""
    if not isinstance(item, dict):
        return item
    item.pop('_id', None)
    if query_type == 'web':
        item['domain'] = item.get('ym') or item.get('domain') or ''
        item['unitName'] = item.get('companyName') or item.get('unitName') or (company_name or '')
        item['serviceLicence'] = item.get('liscense') or item.get('serviceLicence') or ''
        item['updateRecordTime'] = item.get('examineDate') or item.get('updateRecordTime') or ''
        item['serviceName'] = item.get('webName') or item.get('serviceName') or ''
        ws = item.get('webSite')
        if isinstance(ws, list) and ws:
            item['homeUrl'] = ws[0]
        elif isinstance(ws, str):
            item['homeUrl'] = ws
    elif query_type == 'app':
        _apply_nested_tyc_icp_detail(item, 'appIcpRecordDetail')
        sn = item.get('serviceName') or item.get('appName') or item.get('name') or item.get('filterName') or ''
        if sn:
            item['serviceName'] = sn
            if not item.get('name'):
                item['name'] = sn
            if not item.get('appName'):
                item['appName'] = sn
        lic = item.get('serviceLicence') or item.get('serviceFilingNumber') or item.get('liscense') or ''
        if lic:
            item['serviceLicence'] = lic
            if not item.get('serviceFilingNumber'):
                item['serviceFilingNumber'] = lic
        dt = item.get('updateRecordTime') or item.get('examineDate') or ''
        if dt:
            item['updateRecordTime'] = dt
        item['category'] = item.get('category') or item.get('classes') or item.get('type') or ''
        if not item.get('icon'):
            item['icon'] = item.get('productLogo') or item.get('appLogo') or ''
        if company_name and not item.get('unitName'):
            item['unitName'] = company_name
    elif query_type == 'mapp':
        _apply_nested_tyc_icp_detail(item, 'miniProgramIcpRecordDetail')
        sn = item.get('serviceName') or item.get('name') or ''
        if sn:
            item['serviceName'] = sn
            if not item.get('name'):
                item['name'] = sn
        item['serviceLicence'] = item.get('serviceFilingNumber') or item.get('serviceLicence') or ''
        item['updateRecordTime'] = item.get('examineDate') or item.get('updateRecordTime') or ''
        if not item.get('category'):
            item['category'] = item.get('classes') or item.get('type') or ''
        if company_name and not item.get('unitName'):
            item['unitName'] = company_name
    elif query_type == 'wechat':
        item['name'] = item.get('title') or item.get('name') or ''
        item['wechatId'] = item.get('publicNum') or item.get('wechatId') or ''
        item['brief'] = item.get('recommend') or item.get('brief') or ''
        item['icon'] = item.get('titleImgURL') or item.get('codeImg') or item.get('icon') or ''
        if company_name and not item.get('unitName'):
            item['unitName'] = company_name
    elif query_type == 'weibo':
        item['icon'] = item.get('ico') or item.get('icon') or ''
        item['brief'] = item.get('info') or item.get('brief') or ''
        if company_name and not item.get('unitName'):
            item['unitName'] = company_name
    elif query_type == 'invest':
        item['legalPerson'] = item.get('legalPersonName') or item.get('legalPerson') or ''
        item['status'] = item.get('regStatus') or item.get('status') or ''
        if company_name and not item.get('unitName'):
            item['unitName'] = company_name

    if company_name and not item.get('companyName'):
        item['companyName'] = company_name
    return item


def _build_asset_merge_fields(query_type, asset, company_name=None):
    """从增量资产对象提取非空规范化更新字段，供跨源合并与原位详情回写复用。"""
    update_fields = {}
    # 1. 归属单位（以最新记录优先更新）
    target_unit = asset.get("unitName") or company_name
    if target_unit:
        update_fields["unitName"] = target_unit
        update_fields["companyName"] = target_unit

    # 2. 服务备案号与主体备案号（web 兼容主备案号，app/mapp/kapp 独立保留 mainLicence）
    lic_val = asset.get("serviceLicence") or asset.get("serviceFilingNumber") or asset.get("liscense")
    if not lic_val and query_type == "web":
        lic_val = asset.get("mainLicence")
    if lic_val:
        update_fields["serviceLicence"] = lic_val
        update_fields["liscense"] = lic_val
        if query_type in ("app", "mapp", "kapp"):
            update_fields["serviceFilingNumber"] = lic_val
    if asset.get("mainLicence"):
        update_fields["mainLicence"] = asset["mainLicence"]

    # 3. 核准与更新时间
    update_time = asset.get("updateRecordTime") or asset.get("examineDate")
    if update_time:
        update_fields["updateRecordTime"] = update_time
        update_fields["examineDate"] = update_time

    # 4. 业务名称
    sn = asset.get("serviceName") or asset.get("webName") or asset.get("appName") or asset.get("name") or asset.get("title")
    if sn:
        update_fields["serviceName"] = sn
        if query_type == "web":
            update_fields["webName"] = sn
        elif query_type == "app":
            update_fields["appName"] = sn
            update_fields["name"] = sn
        elif query_type in ("mapp", "kapp"):
            update_fields["name"] = sn

    # 5. 链接与主页
    hu = asset.get("homeUrl") or asset.get("webSite") or asset.get("href") or asset.get("url")
    if hu:
        if isinstance(hu, list) and hu:
            update_fields["homeUrl"] = hu[0]
        elif isinstance(hu, str):
            update_fields["homeUrl"] = hu
            if query_type == "weibo":
                update_fields["href"] = hu

    # 6. 分类/审批/版本/性质/图标/简介/微信号/详情载荷
    if asset.get("category") or asset.get("classes"):
        update_fields["category"] = asset.get("category") or asset.get("classes")
    if asset.get("contentTypeName"):
        update_fields["contentTypeName"] = asset["contentTypeName"]
    if asset.get("version"):
        update_fields["version"] = asset["version"]
    if asset.get("dataId"):
        update_fields["dataId"] = asset["dataId"]
    if asset.get("companyType") or asset.get("natureName"):
        ct = asset.get("companyType") or asset.get("natureName")
        update_fields["companyType"] = ct
        update_fields["natureName"] = ct
    if asset.get("icon") or asset.get("titleImgURL") or asset.get("codeImg") or asset.get("ico") or asset.get("productLogo") or asset.get("appLogo"):
        update_fields["icon"] = (
            asset.get("icon") or asset.get("titleImgURL") or asset.get("codeImg")
            or asset.get("ico") or asset.get("productLogo") or asset.get("appLogo")
        )
    if asset.get("brief") or asset.get("recommend") or asset.get("info"):
        update_fields["brief"] = asset.get("brief") or asset.get("recommend") or asset.get("info")
    if asset.get("wechatId") or asset.get("publicNum"):
        update_fields["wechatId"] = asset.get("wechatId") or asset.get("publicNum")
    if asset.get("miniProgramIcpRecordDetail"):
        update_fields["miniProgramIcpRecordDetail"] = asset.get("miniProgramIcpRecordDetail")
    if asset.get("appIcpRecordDetail"):
        update_fields["appIcpRecordDetail"] = asset.get("appIcpRecordDetail")

    return update_fields


async def _upsert_task_asset(task_id, query_type, asset, company_name, task_assets_index, source="tyc", doc_sources=None):
    """
    统一任务全局资产去重与智能增量合并引擎：
    1. 网站备案 (web)：按标准化域名 (domain/ym) 全局去重；
    2. 移动 APP (app)：按 APP 名称 (serviceName/name/appName) 全局去重；无名称以备案号兜底；
    3. 微信小程序 (mapp)：按小程序名称 (serviceName/name) 全局去重；无名称以备案号兜底；
    4. 微信公众号 (wechat)：按公众号名称 (name/title) 全局去重；无名称以 wechatId/publicNum 兜底；
    5. 微博 (weibo)：按标准化微博主页链接 (href/url) 全局去重；无链接以名称兜底；
    6. 快应用 (kapp)：按快应用名称 (serviceName/name) 全局去重；无名称以备案号兜底；
    7. 对外投资 (invest)：按子公司 GID/名称全局去重。

    冲突处理：智能增量合并，以最新记录优先更新主体 unitName 与非空技术字段，不重复计入资产总数。
    返回值：is_new (bool) - 是否为首发新资产
    """
    if not await _task_is_running(task_id):
        return False

    key = None
    lic_key = None

    if query_type == "web":
        val = (asset.get("domain") or asset.get("ym") or "").strip().lower()
        if val.startswith("http://"):
            val = val[7:]
        elif val.startswith("https://"):
            val = val[8:]
        val = val.split("/")[0].split(":")[0].strip()
        if not val:
            return False
        key = val
        asset["domain"] = key
        asset["ym"] = key

    elif query_type == "app":
        raw_name = (asset.get("serviceName") or asset.get("name") or asset.get("appName") or "").strip()
        lic = (asset.get("serviceLicence") or asset.get("serviceFilingNumber") or asset.get("liscense") or "").strip()
        if raw_name:
            key = raw_name.lower()
        if lic:
            lic_key = lic.lower()
        if not key and lic_key:
            key = lic_key
        if not key:
            return False

    elif query_type == "mapp":
        raw_name = (asset.get("serviceName") or asset.get("name") or "").strip()
        lic = (asset.get("serviceLicence") or asset.get("serviceFilingNumber") or "").strip()
        if raw_name:
            key = raw_name.lower()
        if lic:
            lic_key = lic.lower()
        if not key and lic_key:
            key = lic_key
        if not key:
            return False

    elif query_type == "wechat":
        raw_name = (asset.get("name") or asset.get("title") or "").strip()
        wid = (asset.get("wechatId") or asset.get("publicNum") or "").strip()
        if raw_name:
            key = raw_name.lower()
        elif wid:
            key = wid.lower()
        if not key:
            return False

    elif query_type == "weibo":
        raw_link = (asset.get("href") or asset.get("url") or asset.get("link") or "").strip()
        if raw_link:
            clean_link = re.sub(r'\?.*$', '', raw_link).rstrip('/').lower()
            key = clean_link
        else:
            raw_name = (asset.get("name") or asset.get("title") or "").strip()
            if raw_name:
                key = raw_name.lower()
        if not key:
            return False

    elif query_type == "kapp":
        raw_name = (asset.get("serviceName") or asset.get("name") or "").strip()
        lic = (asset.get("serviceLicence") or asset.get("serviceFilingNumber") or "").strip()
        if raw_name:
            key = raw_name.lower()
        if lic:
            lic_key = lic.lower()
        if not key and lic_key:
            key = lic_key
        if not key:
            return False

    elif query_type == "invest":
        key = str(asset.get("id") or asset.get("name") or "").strip().lower()
        if not key:
            return False

    index_dict = task_assets_index.setdefault(query_type, {})
    doc_id = None
    if key and key in index_dict:
        doc_id = index_dict[key]
    elif lic_key and lic_key in index_dict:
        doc_id = index_dict[lic_key]

    if doc_id:
        update_fields = _build_asset_merge_fields(query_type, asset, company_name=company_name)

        # 仅当跨数据源合并（如既有记录来自 tyc 且本次来自 icp）时才置位 source_synced='tyc+icp'，
        # 防止纯 MIIT 内部二次合并或详情补全回写把 icp 独占记录误标为 tyc+icp
        if source == "icp":
            existing_src = doc_sources.get(doc_id) if doc_sources is not None else None
            existing_synced = None
            if existing_src is None:
                try:
                    existing_doc = await db['icp_asset'].find_one({"_id": doc_id}, {"source": 1, "source_synced": 1})
                    if existing_doc:
                        existing_src = existing_doc.get("source")
                        existing_synced = existing_doc.get("source_synced")
                        if doc_sources is not None and existing_src:
                            doc_sources[doc_id] = existing_src
                except Exception:
                    pass
            if existing_src == "tyc" or existing_synced == "tyc+icp":
                update_fields["source_synced"] = "tyc+icp"

        if update_fields:
            await db['icp_asset'].update_one({"_id": doc_id}, {"$set": update_fields})

        if key:
            index_dict[key] = doc_id
        if lic_key:
            index_dict[lic_key] = doc_id

        return False
    else:
        asset["task_id"] = task_id
        asset["query_type"] = query_type
        if not asset.get("unitName") and company_name:
            asset["unitName"] = company_name
        if not asset.get("companyName") and company_name:
            asset["companyName"] = company_name
        asset["source"] = source
        ins = await db['icp_asset'].insert_one(asset)
        new_id = ins.inserted_id
        if doc_sources is not None:
            doc_sources[new_id] = source
        if key:
            index_dict[key] = new_id
        if lic_key:
            index_dict[lic_key] = new_id
        return True


async def _run_company_icp_enrichment(task_id, company_name, myicp, task_assets_index, counts, total_assets_holder, insert_syslog, update_stats, proxy=None, known_named_lics=None, enabled_miit_types=None, doc_sources=None, detail_waf_waited=None):
    """
    针对指定企业主体发起工信部官方备案双轨查重与补全
    """
    if not company_name or not myicp:
        return

    # 检查任务是否中止
    task_info = await db['icp_task'].find_one({"_id": ObjectId(task_id)}, {"status": 1})
    if not task_info or task_info.get("status") != "running":
        return

    await insert_syslog("info", "工信部查重", f"正在对主体【{company_name}】发起工信部官方备案双轨查重与补全...")

    handlers = {
        "web": (myicp.ymWeb, "网站备案"),
        "app": (myicp.ymApp, "移动APP"),
        "mapp": (myicp.ymMiniApp, "小程序"),
        "kapp": (myicp.ymKuaiApp, "快应用"),
    }

    for qt, (handler, label) in handlers.items():
        if enabled_miit_types is not None and qt not in enabled_miit_types:
            continue
        # 实时检测任务是否被主动终止
        task_info = await db['icp_task'].find_one({"_id": ObjectId(task_id)}, {"status": 1})
        if not task_info or task_info.get("status") != "running":
            logger.info(f"Task {task_id} manually stopped during ICP enrichment.")
            return

        # 全局 WAF 熔断：等待冷却后重试一次（仅一次），而非永久跳过剩余类型
        _waf_check = getattr(myicp, "_is_global_waf_blocked", None)
        if callable(_waf_check) and _waf_check():
            waited = await _wait_waf_cooldown_once(myicp, task_id, "工信部查重", insert_syslog)
            if not waited:
                await insert_syslog("warning", "工信部查重", f"主体【{company_name}】检测到出口网络触发创宇盾熔断，跳过该类型补全")
                continue
            # 长等待后复查任务状态：等待期间用户可能已手动停止
            task_info = await db['icp_task'].find_one({"_id": ObjectId(task_id)}, {"status": 1})
            if not task_info or task_info.get("status") != "running":
                logger.info(f"Task {task_id} manually stopped during WAF cooldown wait.")
                return

        await asyncio.sleep(random.uniform(8.0, 15.0))

        dim_state = {"page_persisted": False, "new_count": 0, "merged_count": 0}
        if hasattr(myicp, "attach_task_hooks"):
            async def _enrich_progress_cb(_sp, _stage, message, _label=label):
                await insert_syslog("info", f"工信部查重·{_label}", message)

            async def _enrich_should_stop_cb():
                return not await _task_is_running(task_id)

            def _enrich_skip_detail_fn(_sp, item, _qt=qt):
                if known_named_lics is None:
                    return False
                lic = (item.get("serviceLicence") or item.get("serviceFilingNumber") or item.get("liscense") or "").strip().lower()
                return bool(lic and lic in known_named_lics.get(_qt, ()))

            async def _enrich_page_cb(_sp, items_batch, _page_num, _total_pages, _qt=qt, _state=dim_state):
                if not await _task_is_running(task_id):
                    return
                _state["page_persisted"] = True
                batch_new = 0
                for asset in items_batch:
                    doc = dict(asset)
                    doc.pop('_id', None)
                    is_new = await _upsert_task_asset(
                        task_id=task_id,
                        query_type=_qt,
                        asset=doc,
                        company_name=company_name,
                        task_assets_index=task_assets_index,
                        source="icp",
                        doc_sources=doc_sources,
                    )
                    if is_new:
                        batch_new += 1
                        _state["new_count"] += 1
                    else:
                        _state["merged_count"] += 1
                    if known_named_lics is not None and _qt in known_named_lics:
                        sn = (doc.get("serviceName") or doc.get("name") or doc.get("appName") or "").strip()
                        lic_v = (doc.get("serviceLicence") or doc.get("serviceFilingNumber") or doc.get("liscense") or "").strip().lower()
                        if sn and lic_v:
                            known_named_lics[_qt].add(lic_v)
                if batch_new > 0:
                    counts[_qt] = counts.get(_qt, 0) + batch_new
                    total_assets_holder[0] += batch_new
                    await update_stats()

            async def _enrich_detail_cb(_sp, enriched_items, _qt=qt, _state=dim_state):
                if not await _task_is_running(task_id):
                    return
                index_dict = task_assets_index.setdefault(_qt, {})
                stat_changed = False
                for item in enriched_items:
                    raw_name = (item.get("serviceName") or item.get("name") or item.get("appName") or "").strip()
                    lic = (item.get("serviceLicence") or item.get("serviceFilingNumber") or item.get("liscense") or "").strip()
                    name_key = raw_name.lower() if raw_name else ""
                    lic_key = lic.lower() if lic else ""
                    if known_named_lics is not None and _qt in known_named_lics and raw_name and lic_key:
                        known_named_lics[_qt].add(lic_key)

                    name_doc_id = index_dict.get(name_key) if name_key else None
                    lic_doc_id = index_dict.get(lic_key) if lic_key else None
                    doc_copy = dict(item)
                    doc_copy.pop('_id', None)
                    extra_fields = {
                        k: v for k, v in doc_copy.items()
                        if k not in ("_id", "task_id", "query_type") and v not in (None, "")
                    }

                    if name_doc_id and lic_doc_id and name_doc_id != lic_doc_id:
                        await _upsert_task_asset(
                            task_id=task_id,
                            query_type=_qt,
                            asset=doc_copy,
                            company_name=company_name,
                            task_assets_index=task_assets_index,
                            source="icp",
                            doc_sources=doc_sources,
                        )
                        if extra_fields:
                            await db['icp_asset'].update_one({"_id": name_doc_id}, {"$set": extra_fields})
                        await _delete_asset_doc(db['icp_asset'], lic_doc_id)
                        index_dict[lic_key] = name_doc_id
                        if counts.get(_qt, 0) > 0:
                            counts[_qt] -= 1
                        if total_assets_holder[0] > 0:
                            total_assets_holder[0] -= 1
                        if _state["new_count"] > 0:
                            _state["new_count"] -= 1
                        _state["merged_count"] += 1
                        stat_changed = True
                    else:
                        target_id = lic_doc_id or name_doc_id
                        is_new = await _upsert_task_asset(
                            task_id=task_id,
                            query_type=_qt,
                            asset=doc_copy,
                            company_name=company_name,
                            task_assets_index=task_assets_index,
                            source="icp",
                            doc_sources=doc_sources,
                        )
                        resolved_id = target_id or index_dict.get(name_key) or index_dict.get(lic_key)
                        if resolved_id and extra_fields:
                            await db['icp_asset'].update_one({"_id": resolved_id}, {"$set": extra_fields})
                        if is_new:
                            _state["new_count"] += 1
                            counts[_qt] = counts.get(_qt, 0) + 1
                            total_assets_holder[0] += 1
                            stat_changed = True
                if stat_changed:
                    await update_stats()

            allow_detail_waf_wait = bool(detail_waf_waited is None or not detail_waf_waited[0])
            if allow_detail_waf_wait and detail_waf_waited is not None:
                detail_waf_open_fn = getattr(myicp, "_detail_waf_open", None)
                if callable(detail_waf_open_fn) and detail_waf_open_fn():
                    detail_waf_waited[0] = True
            myicp.attach_task_hooks(
                progress_cb=_enrich_progress_cb,
                page_cb=_enrich_page_cb,
                detail_cb=_enrich_detail_cb,
                should_stop_cb=_enrich_should_stop_cb,
                skip_detail_fn=_enrich_skip_detail_fn,
                wait_on_detail_waf=allow_detail_waf_wait,
            )

        try:
            try:
                res = await handler(company_name, "", "", proxy=proxy)
            finally:
                if hasattr(myicp, "attach_task_hooks"):
                    myicp.attach_task_hooks()

            if not await _task_is_running(task_id):
                logger.info(f"Task {task_id} manually stopped during ICP enrichment.")
                return
            if res.get("code") == 200 and res.get("params") and res["params"].get("_stopped"):
                logger.info(f"Task {task_id} stopped cleanly during MIIT pagination/detail.")
                return

            if res.get("code") == 200 and res.get("params"):
                assets = res["params"].get("list", [])
                if not dim_state["page_persisted"]:
                    batch_new = 0
                    if assets:
                        for asset in assets:
                            asset.pop('_id', None)
                            is_new = await _upsert_task_asset(
                                task_id=task_id,
                                query_type=qt,
                                asset=asset,
                                company_name=company_name,
                                task_assets_index=task_assets_index,
                                source="icp",
                                doc_sources=doc_sources,
                            )
                            if is_new:
                                batch_new += 1
                                dim_state["new_count"] += 1
                            else:
                                dim_state["merged_count"] += 1

                    if batch_new > 0:
                        counts[qt] = counts.get(qt, 0) + batch_new
                        total_assets_holder[0] += batch_new
                        await update_stats()

                new_count = dim_state["new_count"]
                merged_count = dim_state["merged_count"]
                if new_count > 0 or merged_count > 0:
                    msg = f"主体【{company_name}】工信部 {label} 查重完成：智能补全强化 {merged_count} 条，新增漏网资产 {new_count} 条"
                    notes = []
                    skipped_cap = res["params"].get("_detail_skipped_cap") or 0
                    circuit_break = bool(res["params"].get("_detail_circuit_break") or res["params"].get("_detail_waf"))
                    missing = res["params"].get("_detail_missing") or 0
                    if skipped_cap > 0:
                        notes.append(f"受单批详情上限控制跳过 {skipped_cap} 条详情查询（已保留基础备案号）")
                    if circuit_break:
                        notes.append("详情接口触发保护熔断")
                    elif missing > 0 and skipped_cap == 0:
                        notes.append(f"{missing} 条未获取到详情")
                    if notes:
                        msg += f"；{'，'.join(notes)}"
                    await insert_syslog("info", "工信部查重", msg)
                else:
                    await insert_syslog("info", "工信部查重", f"主体【{company_name}】工信部 {label} 查重完成：官方暂无收录该主体资产")
            elif res.get("code") != 200:
                msg = str(res.get("message") or res.get("msg") or f"状态码 {res.get('code')}")
                if "创宇盾" in msg or "黑客" in msg:
                    await insert_syslog("warning", "工信部查重", f"主体【{company_name}】查询 {label} 触发创宇盾风控，跳过该主体该类型查询")
                    continue
                elif "无数据" in msg or "为空" in msg:
                    await insert_syslog("info", "工信部查重", f"主体【{company_name}】工信部 {label} 查重完成：官方暂无收录该主体资产")
                elif any(kw in msg for kw in ["验证码", "频率", "频次", "拦截", "风控", "禁止访问", "稍后再试", "访问频繁", "403"]):
                    await insert_syslog("warning", "工信部查重", f"主体【{company_name}】查询 {label} 触发工信部接口限制 ({msg})，跳过该主体该类型查询")
                    continue
                else:
                    logger.warning(f"ICP enrichment query for {company_name} {qt} returned: {msg}")
                    await insert_syslog("warning", "工信部查重", f"主体【{company_name}】工信部 {label} 查询响应: {msg}")
        except Exception as err:
            err_msg = str(err)
            logger.warning(f"ICP enrichment exception for {company_name} {qt}: {err}")
            if any(kw in err_msg for kw in ["创宇盾", "黑客", "403", "ClientConnectorError", "TimeoutError"]):
                await insert_syslog("warning", "工信部查重", f"主体【{company_name}】工信部 {label} 网络/风控异常 ({err_msg})，跳过该主体该类型查询")
                continue
            else:
                await insert_syslog("warning", "工信部查重", f"主体【{company_name}】工信部 {label} 查询异常 ({err_msg})，已平滑降级跳过")


async def _hydrate_task_state_from_db(task_id, task_assets_index, doc_sources, known_named_lics, counts, total_assets_holder):
    """断点续跑时从 icp_asset 重建内存去重索引、已知许可集合与分维度计数。"""
    assets_col = db['icp_asset']
    find_fn = getattr(assets_col, "find", None)
    if not callable(find_fn):
        return
    cursor = find_fn({"task_id": task_id})
    docs = []
    if hasattr(cursor, "to_list"):
        docs = await cursor.to_list(length=50000)
    elif hasattr(cursor, "__aiter__"):
        async for d in cursor:
            docs.append(d)
    elif isinstance(cursor, list):
        docs = cursor

    for doc in docs:
        qt = doc.get("query_type")
        if qt not in task_assets_index:
            continue
        doc_id = doc.get("_id")
        if doc_id is not None:
            doc_sources[doc_id] = doc.get("source") or "icp"
        counts[qt] = counts.get(qt, 0) + 1
        total_assets_holder[0] += 1

        idx_map = task_assets_index[qt]
        key = None
        lic_key = None
        if qt == "web":
            val = (doc.get("domain") or doc.get("ym") or "").strip().lower()
            val = val.replace("http://", "").replace("https://", "").split("/")[0].split(":")[0].strip()
            key = val or None
        elif qt in ("app", "mapp", "kapp"):
            rn = (doc.get("serviceName") or doc.get("name") or doc.get("appName") or "").strip()
            lic = (doc.get("serviceLicence") or doc.get("serviceFilingNumber") or doc.get("liscense") or "").strip()
            if rn:
                key = rn.lower()
            if lic:
                lic_key = lic.lower()
            if not key and lic_key:
                key = lic_key
            if rn and lic_key and qt in known_named_lics:
                known_named_lics[qt].add(lic_key)
        elif qt == "wechat":
            rn = (doc.get("name") or doc.get("title") or "").strip()
            wid = (doc.get("wechatId") or doc.get("publicNum") or "").strip()
            key = (rn or wid).lower() or None
        elif qt == "weibo":
            rl = (doc.get("href") or doc.get("url") or doc.get("link") or "").strip()
            if rl:
                key = re.sub(r'\?.*$', '', rl).rstrip('/').lower()
            else:
                rn = (doc.get("name") or doc.get("title") or "").strip()
                key = rn.lower() if rn else None
        elif qt == "invest":
            key = str(doc.get("id") or doc.get("name") or "").strip().lower() or None

        if doc_id is not None:
            if key:
                idx_map[key] = doc_id
            if lic_key:
                idx_map[lic_key] = doc_id


async def run_tyc_job(options):
    task_id = options.get("task_id")
    gid = options.get("gid")
    depth = min(20, max(1, int(options.get("depth", 1) or 1)))
    invest_ratio = options.get("invest_ratio", 0)
    query_types = options.get("query_type", [])
    enable_icp = bool(options.get("enable_icp", True))
    is_resume = bool(options.get("resume"))
    tyc_id = options.get("tyc_id")
    tyc_token = options.get("tyc_token")
    if not task_id or not tyc_id or not tyc_token:
        logger.error(f"Missing required TYC params for task {task_id}")
        if task_id:
            await _abort_recon_task(task_id, "派发参数缺失", "任务派发参数不完整(缺少 task_id / 天眼查凭据)，无法启动测绘")
        return
    allowed = ("waiting", "stop", "error") if is_resume else ("waiting",)
    if not await _claim_recon_task(task_id, allowed_statuses=allowed, is_resume=is_resume):
        logger.warning(f"TYC task {task_id} claim rejected (already running or not in claimable state)")
        await _log_rejected_claim(task_id, "TYC查询")
        return

    raw_max_companies = options.get("max_companies")
    if raw_max_companies is None:
        try:
            import sys as _sys
            import os as _os
            _sys.path.append(_os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
            from load_config import config as _osint_cfg
            raw_max_companies = getattr(getattr(_osint_cfg, "system", object()), "max_traverse_companies", 100)
        except Exception:
            raw_max_companies = 100
    try:
        max_companies = int(raw_max_companies) if raw_max_companies is not None else 100
    except (TypeError, ValueError):
        max_companies = 100

    total_assets_holder = [0]
    error_msg = []
    counts = {"web": 0, "app": 0, "mapp": 0, "wechat": 0, "weibo": 0, "invest": 0, "kapp": 0}

    myicp = None
    icp_init_error = ""
    if enable_icp:
        try:
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from ymicp import beian
            myicp = beian()
        except Exception as init_icp_err:
            logger.error(f"Failed to initialize beian for TYC job {task_id}: {init_icp_err}")
            enable_icp = False
            myicp = None
            icp_init_error = str(init_icp_err)

    async def insert_syslog(level, title, message):
        log_doc = {
            "task_id": task_id,
            "level": level,
            "title": title,
            "message": message,
            "create_time": curr_date()
        }
        try:
            await db['syslog'].insert_one(log_doc)
        except Exception:
            pass

    async def update_stats():
        await db['icp_task'].update_one({"_id": ObjectId(task_id)}, {"$set": {"statistic": {
            "asset_cnt": total_assets_holder[0],
            "invest_cnt": counts.get("invest", 0),
            "web_cnt": counts.get("web", 0),
            "app_cnt": counts.get("app", 0),
            "mapp_cnt": counts.get("mapp", 0),
            "wechat_cnt": counts.get("wechat", 0),
            "weibo_cnt": counts.get("weibo", 0),
            "kapp_cnt": counts.get("kapp", 0)
        }}})

    task_assets_index = {
        "web": {},
        "app": {},
        "mapp": {},
        "wechat": {},
        "weibo": {},
        "kapp": {},
        "invest": {}
    }
    doc_sources = {}
    gid_to_name = {}
    known_named_lics = {"app": set(), "mapp": set(), "kapp": set()}
    root_company_name = ""

    existing_task_doc = await db['icp_task'].find_one({"_id": ObjectId(task_id)})
    if options.get("company_name"):
        root_company_name = options.get("company_name").strip()
    elif existing_task_doc and existing_task_doc.get("company_name"):
        root_company_name = str(existing_task_doc.get("company_name")).strip()

    checkpoint = (existing_task_doc or {}).get("recon_checkpoint") or {}
    if is_resume:
        await _hydrate_task_state_from_db(
            task_id, task_assets_index, doc_sources, known_named_lics, counts, total_assets_holder
        )
        if isinstance(checkpoint.get("gid_to_name"), dict):
            gid_to_name.update({str(k): str(v) for k, v in checkpoint["gid_to_name"].items() if v})

    sys_proxy = await _resolve_system_proxy(options)
    proxy_router = await _build_osint_proxy_router(options, syslog_cb=insert_syslog, service_scope="tyc")
    miit_proxy_router = await _build_osint_proxy_router(options, syslog_cb=insert_syslog, service_scope="miit")
    client = AsyncTycClient(gid=tyc_id, token=tyc_token, proxy=sys_proxy, proxy_router=proxy_router)

    truncation_notes = []
    truncation_seen = set()
    if hasattr(client, "attach_task_hooks"):
        async def _tyc_progress_cb(scene_label, msg):
            await insert_syslog("info", f"TYC·{scene_label}", msg)

        async def _tyc_should_stop_cb():
            return not await _task_is_running(task_id)

        async def _tyc_issue_cb(scene_label, issue):
            fetched = issue.get("fetched", 0)
            expected_total = issue.get("expected_total", 0)
            page_num = issue.get("page_num", 1)
            reason = issue.get("reason", "未知异常")
            exp_tip = f"（预期总计 {expected_total} 条）" if expected_total else ""
            await insert_syslog(
                "warning",
                f"TYC·{scene_label}",
                f"目标 {issue.get('gid') or gid} {scene_label}分页在第 {page_num} 页被拦截或失败（{reason}），已保留前序 {fetched} 条{exp_tip}",
            )
            note = f"TYC {scene_label}: {reason}"
            if note not in truncation_seen:
                truncation_seen.add(note)
                truncation_notes.append(note)

        client.attach_task_hooks(
            progress_cb=_tyc_progress_cb,
            should_stop_cb=_tyc_should_stop_cb,
            issue_cb=_tyc_issue_cb,
        )

    if hasattr(client, "inspect_token_status"):
        tok_status = client.inspect_token_status()
        if tok_status.get("is_jwt") and tok_status.get("expired"):
            expired_at = tok_status.get("expired_at") or "未知时间"
            msg = (
                f"当前配置的 tyc_token 已于 {expired_at} 过期，天眼查第 2 页起可能触发「请登录以使用完整功能」截断；"
                f"本次任务将自动保留第 1 页兜底数据并继续联动工信部补全，建议尽快前往系统设置更新凭据。"
            )
            await insert_syslog("warning", "凭据预检", msg)
            truncation_notes.append(f"tyc_token 已于 {expired_at} 过期")

    if myicp and hasattr(myicp, "attach_proxy_router"):
        myicp.attach_proxy_router(miit_proxy_router)
    if proxy_router.has_structured_policy and proxy_router.get_mode() != "direct_only":
        await insert_syslog(
            "info", "出口策略",
            f"企业测绘出口策略模式: {proxy_router.get_mode()}，已绑定备用代理节点 {len(proxy_router.nodes)} 个"
        )

    # 若尚未获取官方全称，直接调用接口定向解析根企业全称
    if not root_company_name:
        try:
            parsed_name = await client.get_company_name(gid)
            if parsed_name:
                root_company_name = parsed_name
                await db['icp_task'].update_one(
                    {"_id": ObjectId(task_id)},
                    {"$set": {"company_name": root_company_name}}
                )
                await insert_syslog("info", "主体解析", f"已成功定向解析到天眼查根企业官方全称【{root_company_name}】(GID: {gid})")
            else:
                await insert_syslog(
                    "warning", "主体解析",
                    f"根企业 GID {gid} 未能解析到官方工商全称：天眼查各接口均未返回有效主体名称。"
                    f"该 GID 可能无效、已注销或非企业节点；本次任务将跳过工信部备案双轨补全。"
                )
        except Exception as e:
            logger.warning(f"Failed to get root company name for GID {gid}: {e}")
            await insert_syslog(
                "warning", "主体解析",
                f"根企业 GID {gid} 解析官方工商全称异常：{e}。"
                f"本次任务将跳过工信部备案双轨补全。"
            )

    if root_company_name:
        gid_to_name[str(gid)] = root_company_name

    # 工信部双轨查重维度与任务 query_type 对齐（未选 kapp 时不再盲目空跑快应用请求）
    if query_types:
        enabled_miit_types = [qt for qt in ("web", "app", "mapp", "kapp") if qt in query_types]
    else:
        enabled_miit_types = ["web", "app", "mapp", "kapp"]

    type_map = {
        "invest": "对外投资",
        "web": "备案网站",
        "app": "APP",
        "mapp": "小程序",
        "wechat": "微信公众号",
        "weibo": "微博",
        "kapp": "快应用",
    }
    modules_str = ",".join([type_map.get(qt, qt) for qt in query_types])
    ratio_str = f"{invest_ratio}%" if invest_ratio and float(invest_ratio) > 0 else "无限制"
    icp_tip = "开启" if enable_icp else "关闭"
    if is_resume:
        await insert_syslog("info", "断点续跑", f"任务从断点恢复执行（已入库 {total_assets_holder[0]} 条资产），目标(GID): {gid}")
    else:
        config_msg = f"任务开始运行，配置如下：目标(GID): {gid}，查询层数: {depth}，最低投资比例: {ratio_str}，需查询模块: {modules_str}，工信部ICP联动: {icp_tip}"
        await insert_syslog("info", "TYC查询", config_msg)
    if icp_init_error:
        await insert_syslog(
            "warning", "工信部查重",
            f"工信部备案查询模块初始化失败，本次任务已自动降级为纯天眼查测绘，"
            f"不含工信部官方备案补全：{icp_init_error}"
        )

    visited_gids = set(str(x) for x in (checkpoint.get("visited_gids") or [gid])) if is_resume else {str(gid)}
    gids_to_query = list(checkpoint.get("level_gids") or [gid]) if is_resume else [gid]
    start_level = int(checkpoint.get("current_level") or 0) if is_resume else 0
    tyc_done_gids = set(str(x) for x in (checkpoint.get("tyc_done_gids") or [])) if is_resume else set()
    miit_done_gids = set(str(x) for x in (checkpoint.get("miit_done_gids") or [])) if is_resume else set()
    next_gids_resume = list(checkpoint.get("next_gids") or []) if is_resume else []
    max_cap_logged = bool(checkpoint.get("max_companies_reached")) if is_resume else False

    current_level_holder = [start_level]
    current_level_gids_holder = [list(gids_to_query)]
    current_next_gids_holder = [list(next_gids_resume)]
    stopped_flag = [False]

    async def _save_checkpoint(completed=False):
        try:
            await db['icp_task'].update_one(
                {"_id": ObjectId(task_id)},
                {"$set": {"recon_checkpoint": {
                    "current_level": current_level_holder[0],
                    "level_gids": [str(x) for x in current_level_gids_holder[0]],
                    "next_gids": [str(x) for x in current_next_gids_holder[0]],
                    "visited_gids": sorted(visited_gids),
                    "gid_to_name": dict(gid_to_name),
                    "tyc_done_gids": sorted(tyc_done_gids),
                    "miit_done_gids": sorted(miit_done_gids),
                    "max_companies_reached": max_cap_logged,
                    "completed": bool(completed),
                    "updated_at": curr_date(),
                }}}
            )
        except Exception as cp_err:
            logger.debug(f"Failed to persist recon_checkpoint for {task_id}: {cp_err}")

    async def _ingest_tyc_batch(qt, raw_items, dedup_tip, syslog_title):
        new_cnt = 0
        merged_cnt = 0
        for item in raw_items:
            item = _normalize_tyc_asset(item, qt, company_name=current_company_name)
            if qt in known_named_lics:
                sn_val = (item.get("serviceName") or item.get("name") or item.get("appName") or "").strip()
                lic_val = (item.get("serviceLicence") or item.get("serviceFilingNumber") or item.get("liscense") or "").strip().lower()
                if sn_val and lic_val:
                    known_named_lics[qt].add(lic_val)
            is_new = await _upsert_task_asset(
                task_id, qt, item, current_company_name, task_assets_index, source="tyc", doc_sources=doc_sources
            )
            if is_new:
                new_cnt += 1
            else:
                merged_cnt += 1
        counts[qt] += new_cnt
        total_assets_holder[0] += new_cnt
        await update_stats()
        log_tip = f"新增 {new_cnt} 条记录"
        if merged_cnt > 0:
            log_tip += f"，{dedup_tip} {merged_cnt} 条"
        await insert_syslog("info", syslog_title, f"目标 {current_gid} {syslog_title.replace('查询', '')}查询完成，{log_tip}")

    miit_queue = None
    miit_consumer_task = None
    detail_waf_waited = [False]
    if enable_icp and myicp and enabled_miit_types:
        miit_queue = asyncio.Queue()

        async def _miit_consumer():
            while True:
                q_item = await miit_queue.get()
                try:
                    if q_item is None:
                        break
                    c_gid, c_name = q_item
                    if str(c_gid) in miit_done_gids:
                        continue
                    if not await _task_is_running(task_id):
                        stopped_flag[0] = True
                        break
                    if hasattr(miit_proxy_router, "allow_primary_failback"):
                        miit_proxy_router.allow_primary_failback()
                    if c_name:
                        await _run_company_icp_enrichment(
                            task_id=task_id,
                            company_name=c_name,
                            myicp=myicp,
                            task_assets_index=task_assets_index,
                            counts=counts,
                            total_assets_holder=total_assets_holder,
                            insert_syslog=insert_syslog,
                            update_stats=update_stats,
                            proxy=sys_proxy,
                            known_named_lics=known_named_lics,
                            enabled_miit_types=enabled_miit_types,
                            doc_sources=doc_sources,
                            detail_waf_waited=detail_waf_waited,
                        )
                        if not await _task_is_running(task_id):
                            stopped_flag[0] = True
                            break
                    else:
                        await insert_syslog("warning", "工信部查重", f"企业 GID {c_gid} 未能获取到官方全称，跳过工信部二次查重")
                    miit_done_gids.add(str(c_gid))
                    await _save_checkpoint(completed=False)
                finally:
                    miit_queue.task_done()

        miit_consumer_task = asyncio.create_task(_miit_consumer())
        # 断点恢复时先将此前已完成 TYC 但尚未跑完 MIIT 的主体补入消费队列
        if is_resume:
            for done_gid in sorted(tyc_done_gids):
                if done_gid not in miit_done_gids:
                    await miit_queue.put((done_gid, gid_to_name.get(done_gid, "")))

    try:
        for level in range(start_level, depth):
            current_level_holder[0] = level
            current_level_gids_holder[0] = list(gids_to_query)
            next_gids = list(next_gids_resume) if (is_resume and level == start_level and next_gids_resume) else []
            next_gids_resume = []
            current_next_gids_holder[0] = next_gids
            await insert_syslog("info", "TYC查询", f"开始执行第 {level + 1} 层穿透查询，共 {len(gids_to_query)} 个目标...")

            for idx, current_gid in enumerate(gids_to_query):
                if stopped_flag[0]:
                    break
                # 在抓取每家公司前检查任务是否被中止
                task_info = await db['icp_task'].find_one({"_id": ObjectId(task_id)}, {"status": 1})
                if not task_info or task_info.get("status") != "running":
                    await insert_syslog("warning", "任务中止", "检测到任务已被手动停止，退出执行流程。")
                    logger.info(f"Task {task_id} manually stopped.")
                    stopped_flag[0] = True
                    return

                if str(current_gid) in tyc_done_gids:
                    continue

                current_company_name = root_company_name if str(current_gid) == str(gid) else gid_to_name.get(str(current_gid), "")
                if not current_company_name:
                    try:
                        current_company_name = await client.get_company_name(current_gid)
                        if current_company_name:
                            gid_to_name[str(current_gid)] = current_company_name
                            if str(current_gid) == str(gid):
                                root_company_name = current_company_name
                                await db['icp_task'].update_one({"_id": ObjectId(task_id)}, {"$set": {"company_name": root_company_name}})
                            await insert_syslog("info", "主体解析", f"已成功定向解析到企业官方全称【{current_company_name}】(GID: {current_gid})")
                        else:
                            await insert_syslog(
                                "warning", "主体解析",
                                f"子企业 GID {current_gid} 未能解析到官方工商全称，"
                                f"其资产仍会正常抓取入库，但主体名称字段将为空，且跳过该主体的工信部备案补全。"
                            )
                    except Exception as e:
                        logger.warning(f"Failed to get company name for GID {current_gid}: {e}")
                        await insert_syslog(
                            "warning", "主体解析",
                            f"子企业 GID {current_gid} 解析官方工商全称异常：{e}。"
                            f"其资产仍会正常抓取入库，但主体名称字段将为空，且跳过该主体的工信部备案补全。"
                        )

                if idx > 0:
                    await asyncio.sleep(random.uniform(5.0, 8.0))

                # 股权穿透 (投资)
                if "invest" in query_types:
                    await asyncio.sleep(random.uniform(2.0, 5.0))
                    try:
                        await insert_syslog("info", "投资查询", f"正在查询目标 {current_gid} 的对外投资...")
                        invest_list = await client.get_invest_list(current_gid)
                        if invest_list:
                            passed_count = 0
                            dropped_count = 0
                            dropped_unknown_names = []

                            for item in invest_list:
                                item['task_id'] = task_id
                                item['query_type'] = 'invest'

                                pct = item.get("percent")
                                percent_num = None
                                if pct and isinstance(pct, str):
                                    try:
                                        percent_num = float(pct.replace("%", "").strip())
                                        item['percent_num'] = percent_num
                                    except ValueError:
                                        pass
                                elif isinstance(pct, (int, float)):
                                    percent_num = float(pct)
                                    item['percent_num'] = percent_num

                                rc = item.get("amount")
                                if rc and isinstance(rc, str):
                                    m = re.search(r"(\d+(\.\d+)?)", rc.replace(",", ""))
                                    if m:
                                        try:
                                            item['amount_num'] = float(m.group(1))
                                        except ValueError:
                                            pass
                                elif isinstance(rc, (int, float)):
                                    item['amount_num'] = float(rc)

                                # 判定是否达标
                                is_passed = True

                                if invest_ratio and float(invest_ratio) > 0:
                                    if percent_num is not None:
                                        if percent_num < float(invest_ratio):
                                            is_passed = False
                                    else:
                                        # 严格模式：设置了最低投资比例时，无具体持股比例数据的子公司直接丢弃
                                        is_passed = False
                                        cname = item.get("name", item.get("id", "未知公司"))
                                        dropped_unknown_names.append(cname)

                                if is_passed:
                                    item = _normalize_tyc_asset(item, 'invest', company_name=current_company_name)
                                    is_new = await _upsert_task_asset(
                                        task_id, 'invest', item, current_company_name, task_assets_index, source="tyc", doc_sources=doc_sources
                                    )
                                    sub_gid = str(item.get("id"))
                                    sub_name = item.get("name")
                                    if sub_gid and sub_name:
                                        gid_to_name[sub_gid] = sub_name.strip()
                                    if sub_gid and sub_gid not in visited_gids:
                                        if max_companies <= 0 or len(visited_gids) < max_companies:
                                            visited_gids.add(sub_gid)
                                            next_gids.append(item.get("id"))
                                        elif not max_cap_logged:
                                            max_cap_logged = True
                                            await insert_syslog(
                                                "warning", "深穿透保护",
                                                f"已达到单任务穿透主体数量上限（{max_companies} 家），停止向更深层扩展新子公司"
                                            )
                                    if is_new:
                                        passed_count += 1
                                else:
                                    dropped_count += 1

                            counts["invest"] += passed_count
                            total_assets_holder[0] += passed_count
                            await update_stats()

                            await insert_syslog("info", "投资查询", f"目标 {current_gid} 投资查询完成，共发现 {len(invest_list)} 家对外投资，其中 {passed_count} 家达标(入库并递归)，{dropped_count} 家因比例不足或缺失被丢弃。")
                            if dropped_unknown_names:
                                await insert_syslog("info", "投资查询", f"目标 {current_gid} 的以下子公司因无具体投资比例数据，在最低投资比例限制下已被丢弃: {', '.join(dropped_unknown_names)}")
                    except Exception as e:
                        logger.error(f"TYC Query exception for invest: {e}")
                        error_msg.append(f"invest error: {str(e)}")
                        await insert_syslog("error", "投资查询", f"目标 {current_gid} 投资查询异常: {str(e)}")

                # 网站备案
                if "web" in query_types:
                    await asyncio.sleep(random.uniform(2.0, 5.0))
                    try:
                        await insert_syslog("info", "网站查询", f"正在查询目标 {current_gid} 的网站备案...")
                        web_list = await client.get_icp_record_list(current_gid)
                        if web_list:
                            await _ingest_tyc_batch('web', web_list, "全局域名去重合并", "网站查询")
                    except Exception as e:
                        logger.error(f"TYC Query exception for web: {e}")
                        error_msg.append(f"web error: {str(e)}")
                        await insert_syslog("error", "网站查询", f"目标 {current_gid} 网站查询异常: {str(e)}")

                # App查询（联动应用市场详情与新版 APP ICP 备案接口，提前补齐备案号并减少 MIIT 重复补抓）
                if "app" in query_types:
                    await asyncio.sleep(random.uniform(2.0, 5.0))
                    try:
                        await insert_syslog("info", "APP查询", f"正在查询目标 {current_gid} 的APP...")
                        app_list = list(await client.get_app_list(current_gid) or [])
                        app_icp_fn = getattr(client, "get_app_icp_record_list", None)
                        if callable(app_icp_fn):
                            try:
                                app_icp_list = await app_icp_fn(current_gid)
                                if app_icp_list:
                                    app_list.extend(app_icp_list)
                            except Exception as app_icp_err:
                                logger.warning(f"TYC appIcpRecordList exception for {current_gid}: {app_icp_err}")
                        if app_list:
                            await _ingest_tyc_batch('app', app_list, "同名APP去重合并", "APP查询")
                    except Exception as e:
                        logger.error(f"TYC Query exception for app: {e}")
                        error_msg.append(f"app error: {str(e)}")
                        await insert_syslog("error", "APP查询", f"目标 {current_gid} APP查询异常: {str(e)}")

                # 微信公众号
                if "wechat" in query_types:
                    await asyncio.sleep(random.uniform(2.0, 5.0))
                    try:
                        await insert_syslog("info", "微信查询", f"正在查询目标 {current_gid} 的微信公众号...")
                        wechat_list = await client.get_wechat_list(current_gid)
                        if wechat_list:
                            await _ingest_tyc_batch('wechat', wechat_list, "同名公众号去重合并", "微信查询")
                    except Exception as e:
                        logger.error(f"TYC Query exception for wechat: {e}")
                        error_msg.append(f"wechat error: {str(e)}")
                        await insert_syslog("error", "微信查询", f"目标 {current_gid} 微信查询异常: {str(e)}")

                # 微博
                if "weibo" in query_types:
                    await asyncio.sleep(random.uniform(2.0, 5.0))
                    try:
                        await insert_syslog("info", "微博查询", f"正在查询目标 {current_gid} 的微博...")
                        weibo_list = await client.get_weibo_list(current_gid)
                        if weibo_list:
                            await _ingest_tyc_batch('weibo', weibo_list, "同链接微博去重合并", "微博查询")
                    except Exception as e:
                        logger.error(f"TYC Query exception for weibo: {e}")
                        error_msg.append(f"weibo error: {str(e)}")
                        await insert_syslog("error", "微博查询", f"目标 {current_gid} 微博查询异常: {str(e)}")

                # 微信小程序
                if "mapp" in query_types:
                    await asyncio.sleep(random.uniform(2.0, 5.0))
                    try:
                        await insert_syslog("info", "小程序查询", f"正在查询目标 {current_gid} 的小程序...")
                        mapp_list = await client.get_mini_program_list(current_gid)
                        if mapp_list:
                            await _ingest_tyc_batch('mapp', mapp_list, "同名小程序去重合并", "小程序查询")
                    except Exception as e:
                        logger.error(f"TYC Query exception for mapp: {e}")
                        error_msg.append(f"mapp error: {str(e)}")
                        await insert_syslog("error", "小程序查询", f"目标 {current_gid} 小程序查询异常: {str(e)}")

                tyc_done_gids.add(str(current_gid))
                current_next_gids_holder[0] = list(next_gids)
                await _save_checkpoint(completed=False)

                # 投递至 MIIT 单消费者队列并发查重（TYC 生产者继续处理下一家主体）
                if miit_queue is not None and str(current_gid) not in miit_done_gids:
                    await miit_queue.put((current_gid, current_company_name))

            if stopped_flag[0] or not await _task_is_running(task_id):
                stopped_flag[0] = True
                return

            gids_to_query = next_gids
            current_level_holder[0] = level + 1
            current_level_gids_holder[0] = list(gids_to_query)
            current_next_gids_holder[0] = []
            await _save_checkpoint(completed=False)
            if not gids_to_query:
                break

        if miit_queue is not None and miit_consumer_task is not None:
            await miit_queue.put(None)
            await miit_consumer_task
            if stopped_flag[0] or not await _task_is_running(task_id):
                return
    finally:
        if miit_consumer_task is not None and not miit_consumer_task.done():
            miit_consumer_task.cancel()
            try:
                await miit_consumer_task
            except (asyncio.CancelledError, Exception):
                pass
        if myicp:
            try:
                await myicp.cleanup()
            except Exception:
                pass

    if stopped_flag[0] or not await _task_is_running(task_id):
        return

    all_errors = list(error_msg) + list(truncation_notes)
    tyc_task_status = "done" if total_assets_holder[0] > 0 else ("error" if all_errors else "done")
    update_data = {
        "$set": {
            "status": tyc_task_status,
            "end_time": curr_date(),
            "statistic": {
                "asset_cnt": total_assets_holder[0],
                "invest_cnt": counts["invest"],
                "web_cnt": counts["web"],
                "app_cnt": counts["app"],
                "mapp_cnt": counts["mapp"],
                "wechat_cnt": counts["wechat"],
                "weibo_cnt": counts["weibo"],
                "kapp_cnt": counts["kapp"]
            },
            "recon_checkpoint": {
                "current_level": current_level_holder[0],
                "level_gids": [],
                "next_gids": [],
                "visited_gids": sorted(visited_gids),
                "gid_to_name": dict(gid_to_name),
                "tyc_done_gids": sorted(tyc_done_gids),
                "miit_done_gids": sorted(miit_done_gids),
                "max_companies_reached": max_cap_logged,
                "completed": True,
                "updated_at": curr_date(),
            },
        }
    }
    if all_errors:
        update_data["$set"]["error_msg"] = "; ".join(all_errors)
    await _finish_recon_task(task_id, tyc_task_status, update_data)
    await insert_syslog("info", "任务完成", f"TYC+工信部联合测绘任务执行结束，共获取 {total_assets_holder[0]} 条资产")
    logger.info(f"TYC query task {task_id} completed.")


async def _read_cursor_docs(cursor, limit=50000):
    if hasattr(cursor, "to_list"):
        return await cursor.to_list(length=limit)
    if hasattr(cursor, "__aiter__"):
        return [d async for d in cursor]
    if isinstance(cursor, list):
        return list(cursor)
    return []


async def _delete_asset_doc(assets_col, doc_id):
    if doc_id is None:
        return
    del_one = getattr(assets_col, "delete_one", None)
    if callable(del_one):
        await del_one({"_id": doc_id})
        return
    del_many = getattr(assets_col, "delete_many", None)
    if callable(del_many):
        await del_many({"_id": doc_id})


async def _recompute_task_statistic(task_id):
    """依据 icp_asset 实际落库文档重算 icp_task.statistic，确保去重删除后计数一致。"""
    assets_col = db['icp_asset']
    docs = await _read_cursor_docs(assets_col.find({"task_id": task_id}, {"query_type": 1}))
    counts = {"web": 0, "app": 0, "mapp": 0, "wechat": 0, "weibo": 0, "kapp": 0, "invest": 0}
    total = 0
    for d in docs:
        qt = d.get("query_type")
        total += 1
        if qt in counts:
            counts[qt] += 1
    stat = {"asset_cnt": total, **{f"{k}_cnt": v for k, v in counts.items()}}
    await db['icp_task'].update_one({"_id": ObjectId(task_id)}, {"$set": {"statistic": stat}})
    return stat


async def _merge_into_existing_named_doc(assets_col, qt, target_doc, incoming_item, company_name=""):
    """将待合并条目（或原位补全后的 MIIT 记录）的增量字段无损并入既有同名记录，并跨源标记 tyc+icp。"""
    merged_fields = _build_asset_merge_fields(qt, incoming_item, company_name=company_name)
    # 不覆盖既有非空来源专属展示字段（如 TYC 图标/简介/分类），仅填补缺失字段；备案/主体等权威字段以非空补全
    update_set = {}
    for k, v in merged_fields.items():
        if v in (None, ""):
            continue
        existing_val = target_doc.get(k)
        if k in ("icon", "brief", "category") and existing_val not in (None, ""):
            continue
        if existing_val != v:
            update_set[k] = v

    incoming_src = incoming_item.get("source")
    target_src = target_doc.get("source")
    if (target_src == "tyc" and incoming_src in ("icp", None)) or target_doc.get("source_synced") == "tyc+icp":
        if target_doc.get("source_synced") != "tyc+icp":
            update_set["source_synced"] = "tyc+icp"

    if update_set and target_doc.get("_id") is not None:
        await assets_col.update_one({"_id": target_doc["_id"]}, {"$set": update_set})
        target_doc.update(update_set)
    return update_set


async def _refresh_stale_miit_docs(
    myicp,
    sp,
    qt,
    label,
    task_id,
    stale_docs,
    default_company_name,
    proxy_url,
    assets_col,
    doc_by_id,
    named_by_qt,
    insert_syslog,
    should_stop_cb,
):
    """
    为 dataId=0 或因 MIIT 索引轮换返回空占位的历史记录，按备案号/主体重刷最新 dataId。

    返回 (直接补全数, 去重合并数, 待继续查询详情的文档列表)。
    """
    if not stale_docs or not hasattr(myicp, "_query_beian_page"):
        return 0, 0, []

    docs_by_unit = {}
    for doc in stale_docs:
        lic = (doc.get("serviceLicence") or doc.get("serviceFilingNumber") or doc.get("liscense") or "").strip()
        if not lic:
            continue
        unit_name = (doc.get("unitName") or doc.get("companyName") or default_company_name or "").strip()
        if not unit_name:
            continue
        docs_by_unit.setdefault(unit_name, []).append((lic.lower(), lic, doc))

    if not docs_by_unit:
        return 0, 0, []

    direct_filled = 0
    dedup_merged = 0
    refreshed_docs = []
    waited_once = False
    qt_name_map = named_by_qt.setdefault(qt, {})
    total_stale = sum(len(v) for v in docs_by_unit.values())
    await insert_syslog("info", f"详情补全·{label}", f"检测到 {total_stale} 条历史或失效 dataId 记录，开始重刷最新工信部列表索引...")

    async def _query_page_with_wait(query_keyword, page_num, page_size):
        nonlocal waited_once
        ok, payload, _ = await myicp._query_beian_page(query_keyword, sp, page_num, page_size, proxy=proxy_url)
        if not ok and not waited_once and getattr(myicp, "_waf_open", lambda: False)():
            waited_once = True
            if await _wait_waf_cooldown_once(myicp, task_id, f"详情补全·{label}", insert_syslog):
                ok, payload, _ = await myicp._query_beian_page(query_keyword, sp, page_num, page_size, proxy=proxy_url)
        return ok, payload

    def _safe_refresh_fields(list_item):
        fields = {}
        for k, v in list_item.items():
            if k in ("_id", "task_id", "query_type") or v in (None, ""):
                continue
            if k in ("dataId", "serviceType") and v == 0:
                continue
            fields[k] = v
        return fields

    async def _apply_list_match(doc, list_item):
        nonlocal direct_filled, dedup_merged
        doc_id = doc.get("_id")
        fields = _safe_refresh_fields(list_item)
        new_did = fields.get("dataId")
        new_sn = (fields.get("serviceName") or fields.get("name") or fields.get("appName") or "").strip()
        if new_sn:
            fields["serviceName"] = new_sn
            fields.setdefault("name", new_sn)
            if qt == "app":
                fields["appName"] = new_sn
            dup_named = qt_name_map.get(new_sn.lower())
            if dup_named is not None and dup_named.get("_id") != doc_id:
                orig_doc = dict(doc)
                orig_doc.update(fields)
                await _merge_into_existing_named_doc(
                    assets_col, qt, dup_named, orig_doc, company_name=orig_doc.get("unitName") or ""
                )
                if doc_id is not None:
                    await _delete_asset_doc(assets_col, doc_id)
                    doc_by_id.pop(doc_id, None)
                dedup_merged += 1
                direct_filled += 1
                return
            if doc_id is not None and fields:
                await assets_col.update_one({"_id": doc_id}, {"$set": fields})
                doc.update(fields)
                qt_name_map[new_sn.lower()] = doc
            direct_filled += 1
            return

        if new_did and str(new_did).strip() != "0":
            if doc_id is not None and fields:
                await assets_col.update_one({"_id": doc_id}, {"$set": fields})
                doc.update(fields)
            refreshed_docs.append(doc)

    async def _query_single_licence(lic_key, group_items):
        raw_lic = group_items[0][0]
        ok, payload = await _query_page_with_wait(raw_lic, 1, 10)
        if not ok or not isinstance(payload, dict):
            return
        lst = (payload.get("params") or {}).get("list") or []
        match_item = next(
            (it for it in lst if (it.get("serviceLicence") or "").strip().lower() == lic_key),
            lst[0] if len(lst) == 1 else None,
        )
        if match_item:
            for _, doc in group_items:
                await _apply_list_match(doc, match_item)

    for unit_name, entries in docs_by_unit.items():
        if await should_stop_cb():
            break
        wanted_by_lic = {}
        for lic_key, raw_lic, doc in entries:
            wanted_by_lic.setdefault(lic_key, []).append((raw_lic, doc))

        if len(wanted_by_lic) <= 5:
            for lic_key, group_items in wanted_by_lic.items():
                if await should_stop_cb() or getattr(myicp, "_waf_open", lambda: False)():
                    break
                await _query_single_licence(lic_key, group_items)
                await asyncio.sleep(random.uniform(0.6, 1.2))
            continue

        remaining_keys = set(wanted_by_lic.keys())
        page_num = 1
        total_pages = 1
        while page_num <= total_pages and remaining_keys:
            if await should_stop_cb():
                break
            ok, payload = await _query_page_with_wait(unit_name, page_num, 26)
            if not ok or not isinstance(payload, dict):
                break
            if page_num == 1 and hasattr(myicp, "_get_total_pages"):
                total_pages = max(1, int(myicp._get_total_pages(payload, 26) or 1))
            lst = (payload.get("params") or {}).get("list") or []
            for it in lst:
                lic_key = (it.get("serviceLicence") or "").strip().lower()
                if lic_key in remaining_keys:
                    remaining_keys.discard(lic_key)
                    for _, doc in wanted_by_lic[lic_key]:
                        await _apply_list_match(doc, it)
            if not lst:
                break
            page_num += 1
            if page_num <= total_pages and remaining_keys:
                await asyncio.sleep(random.uniform(1.0, 1.8))

        # MIIT 按主体分页偶发存在翻页窗口漏项/排序漂移，对遗留少数未命中项回退按备案号精准检索
        if remaining_keys and not await should_stop_cb() and not getattr(myicp, "_waf_open", lambda: False)():
            for lic_key in list(remaining_keys):
                if await should_stop_cb() or getattr(myicp, "_waf_open", lambda: False)():
                    break
                await _query_single_licence(lic_key, wanted_by_lic[lic_key])
                await asyncio.sleep(random.uniform(0.6, 1.2))

    if refreshed_docs or direct_filled:
        await insert_syslog(
            "info",
            f"详情补全·{label}",
            f"列表索引重刷完成：直出命名 {direct_filled} 条，待续查最新 dataId {len(refreshed_docs)} 条。",
        )
    return direct_filled, dedup_merged, refreshed_docs


async def run_backfill_details_job(options):
    """
    原位补全已有任务中缺失名称（serviceName 为空且带 dataId）的 APP/小程序/快应用详情，
    取消单批 100 条截断并执行幂等跨源同名合并与统计校准，结束后恢复任务原先终态。
    """
    task_id = options.get("task_id")
    if not task_id:
        return

    task_doc = await db['icp_task'].find_one({"_id": ObjectId(task_id)})
    if not task_doc:
        logger.warning(f"Backfill task {task_id} not found")
        return
    prev_status = task_doc.get("status")
    if prev_status not in ("done", "stop", "error"):
        logger.warning(f"Backfill task {task_id} skipped: status={prev_status}")
        return

    claim_res = await db['icp_task'].update_one(
        {"_id": ObjectId(task_id), "status": prev_status},
        {"$set": {
            "status": "running",
            "detail_backfill_running": True,
            "detail_backfill_prev_status": prev_status,
        }},
    )
    if getattr(claim_res, "matched_count", 0) != 1:
        return

    async def insert_syslog(level, title, message):
        try:
            await db['syslog'].insert_one({
                "task_id": task_id,
                "level": level,
                "title": title,
                "message": message,
                "create_time": curr_date(),
            })
        except Exception:
            pass

    target_qts = options.get("query_types") or ["app", "mapp", "kapp"]
    sp_map = {"app": (1, "移动APP"), "mapp": (2, "小程序"), "kapp": (3, "快应用")}
    myicp = None
    filled_total = 0
    remaining_total = 0
    dedup_merged_total = 0
    try:
        import sys
        import os
        sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from ymicp import beian

        myicp = beian()
        sys_proxy = await _resolve_system_proxy(options)
        proxy_router = await _build_osint_proxy_router(options, syslog_cb=insert_syslog)
        if hasattr(myicp, "attach_proxy_router"):
            myicp.attach_proxy_router(proxy_router)

        assets_col = db['icp_asset']
        all_docs = await _read_cursor_docs(assets_col.find({
            "task_id": task_id,
            "query_type": {"$in": list(target_qts)},
        }))

        # 1. 预索引已有命名记录并幂等合并存量同名重复行（如历史 TYC+MIIT 裂变记录）
        doc_by_id = {}
        named_by_qt = {}
        named_by_lic_qt = {}
        for doc in all_docs:
            qt = doc.get("query_type")
            if qt not in sp_map:
                continue
            did_obj = doc.get("_id")
            sn = (doc.get("serviceName") or doc.get("name") or doc.get("appName") or "").strip()
            lic = (doc.get("serviceLicence") or doc.get("serviceFilingNumber") or doc.get("liscense") or "").strip().lower()
            if sn:
                name_key = sn.lower()
                qt_name_map = named_by_qt.setdefault(qt, {})
                existing_named = qt_name_map.get(name_key)
                if existing_named is not None and existing_named.get("_id") != did_obj:
                    await _merge_into_existing_named_doc(assets_col, qt, existing_named, doc, company_name=doc.get("unitName") or "")
                    await _delete_asset_doc(assets_col, did_obj)
                    dedup_merged_total += 1
                    continue
                qt_name_map[name_key] = doc
                if lic:
                    named_by_lic_qt.setdefault(qt, {})[lic] = doc
            if did_obj is not None:
                doc_by_id[did_obj] = doc

        # 2. 收集待补全条目；若其备案号已与既有命名记录匹配则直接就地合并，无需再请求 MIIT
        missing_with_did = {}
        zero_did_by_qt = {}
        for doc in list(doc_by_id.values()):
            qt = doc.get("query_type")
            if qt not in sp_map:
                continue
            sn = (doc.get("serviceName") or doc.get("name") or doc.get("appName") or "").strip()
            if sn:
                continue
            lic = (doc.get("serviceLicence") or doc.get("serviceFilingNumber") or doc.get("liscense") or "").strip().lower()
            if lic and lic in named_by_lic_qt.get(qt, {}):
                existing_named = named_by_lic_qt[qt][lic]
                if existing_named.get("_id") != doc.get("_id"):
                    await _merge_into_existing_named_doc(assets_col, qt, existing_named, doc, company_name=doc.get("unitName") or "")
                    await _delete_asset_doc(assets_col, doc.get("_id"))
                    doc_by_id.pop(doc.get("_id"), None)
                    dedup_merged_total += 1
                    filled_total += 1
                    continue
            did = doc.get("dataId")
            if did not in (None, "", 0, "0"):
                missing_with_did.setdefault(qt, []).append(doc)
            elif lic:
                zero_did_by_qt.setdefault(qt, []).append(doc)

        pending_count = sum(len(v) for v in missing_with_did.values()) + sum(len(v) for v in zero_did_by_qt.values())
        if pending_count == 0:
            if dedup_merged_total > 0:
                await _recompute_task_statistic(task_id)
                await insert_syslog("info", "详情补全", f"已完成存量同源/同名记录去重合并 {dedup_merged_total} 条，当前无剩余待补全资产。")
            else:
                await insert_syslog("info", "详情补全", "当前任务不存在缺失名称的待补全资产。")
            return

        await insert_syslog("info", "详情补全", f"开始原位补全缺失详情，共发现 {pending_count} 条待补全记录（不限单批 100 条上限）...")
        default_company_name = (task_doc.get("company_name") or task_doc.get("name") or "").strip()

        active_qts = [qt for qt in sp_map if missing_with_did.get(qt) or zero_did_by_qt.get(qt)]
        for qt in active_qts:
            if not await _task_is_running(task_id):
                break
            sp, label = sp_map[qt]
            docs_with_did = list(missing_with_did.get(qt) or [])
            zero_docs = list(zero_did_by_qt.get(qt) or [])

            async def _bf_progress_cb(_sp, _stage, message, _label=label):
                await insert_syslog("info", f"详情补全·{_label}", message)

            async def _bf_should_stop_cb():
                return not await _task_is_running(task_id)

            async def _enrich_batch(target_docs):
                nonlocal filled_total, dedup_merged_total
                if not target_docs or not await _task_is_running(task_id):
                    return False
                id_by_dataid = {str(d.get("dataId")): d.get("_id") for d in target_docs if d.get("dataId") not in (None, "", 0, "0")}

                async def _bf_detail_cb(_sp, enriched_items, _id_map=id_by_dataid, _qt=qt):
                    nonlocal filled_total, dedup_merged_total
                    if not await _task_is_running(task_id):
                        return
                    qt_name_map = named_by_qt.setdefault(_qt, {})
                    for item in enriched_items:
                        did = str(item.get("dataId") or "").strip()
                        doc_id = _id_map.get(did) or item.get("_id")
                        extra_fields = {
                            k: v for k, v in item.items()
                            if k not in ("_id", "task_id", "query_type")
                            and v not in (None, "")
                            and not (k in ("dataId", "serviceType") and v == 0)
                        }
                        if not extra_fields:
                            continue
                        sn = (item.get("serviceName") or item.get("name") or item.get("appName") or "").strip()
                        if sn:
                            extra_fields["serviceName"] = sn
                            extra_fields.setdefault("name", sn)
                            if _qt == "app":
                                extra_fields["appName"] = sn

                            dup_named = qt_name_map.get(sn.lower())
                            if dup_named is not None and dup_named.get("_id") != doc_id:
                                orig_doc = dict(doc_by_id.get(doc_id) or {})
                                orig_doc.update(extra_fields)
                                await _merge_into_existing_named_doc(
                                    assets_col, _qt, dup_named, orig_doc,
                                    company_name=orig_doc.get("unitName") or "",
                                )
                                if doc_id is not None:
                                    await _delete_asset_doc(assets_col, doc_id)
                                    doc_by_id.pop(doc_id, None)
                                dedup_merged_total += 1
                                filled_total += 1
                                continue

                            filled_total += 1
                        if doc_id is not None:
                            await assets_col.update_one({"_id": doc_id}, {"$set": extra_fields})
                            if doc_id in doc_by_id:
                                doc_by_id[doc_id].update(extra_fields)
                            if sn:
                                qt_name_map[sn.lower()] = doc_by_id.get(doc_id) or {"_id": doc_id, **extra_fields}

                myicp.attach_task_hooks(
                    progress_cb=_bf_progress_cb,
                    detail_cb=_bf_detail_cb,
                    should_stop_cb=_bf_should_stop_cb,
                )
                try:
                    res = await myicp._enrich_app_details(
                        {"code": 200, "success": True, "params": {"list": target_docs}},
                        sp,
                        {},
                        sys_proxy,
                        target_name=default_company_name,
                        max_items=0,
                        wait_on_detail_waf=True,
                    )
                    prm = res.get("params") or {}
                    return bool(prm.get("_detail_circuit_break") or prm.get("_detail_waf") or prm.get("_stopped"))
                finally:
                    myicp.attach_task_hooks()

            aborted_or_waf = await _enrich_batch(docs_with_did)

            still_stale = [
                d for d in (docs_with_did + zero_docs)
                if d.get("_id") in doc_by_id
                and not (d.get("serviceName") or d.get("name") or d.get("appName") or "").strip()
            ]
            if still_stale and not aborted_or_waf and await _task_is_running(task_id):
                d_fill, d_merge, refreshed_docs = await _refresh_stale_miit_docs(
                    myicp, sp, qt, label, task_id, still_stale,
                    default_company_name, sys_proxy, assets_col, doc_by_id,
                    named_by_qt, insert_syslog, _bf_should_stop_cb,
                )
                filled_total += d_fill
                dedup_merged_total += d_merge
                if refreshed_docs and await _task_is_running(task_id):
                    await _enrich_batch(refreshed_docs)

            remaining_total += sum(
                1 for d in (docs_with_did + zero_docs)
                if d.get("_id") in doc_by_id
                and not (d.get("serviceName") or d.get("name") or d.get("appName") or "").strip()
            )

        if dedup_merged_total > 0 or filled_total > 0:
            await _recompute_task_statistic(task_id)

        merge_note = f"，并去重合并 {dedup_merged_total} 条重复记录" if dedup_merged_total > 0 else ""
        await insert_syslog(
            "info",
            "详情补全",
            f"原位补全结束：本次成功补全 {filled_total} 条{merge_note}，仍剩余 {remaining_total} 条待补全。",
        )
    except Exception as e:
        logger.error(f"Backfill details exception for {task_id}: {e}")
        await insert_syslog("error", "详情补全", f"原位补全异常: {e}")
    finally:
        if myicp:
            try:
                await myicp.cleanup()
            except Exception:
                pass
        cur = await db['icp_task'].find_one({"_id": ObjectId(task_id)}, {"status": 1})
        if cur and cur.get("status") == "running":
            await db['icp_task'].update_one(
                {"_id": ObjectId(task_id), "status": "running"},
                {
                    "$set": {"status": prev_status, "detail_backfill_last_time": curr_date()},
                    "$unset": {"detail_backfill_running": "", "detail_backfill_prev_status": ""},
                },
            )
        else:
            await db['icp_task'].update_one(
                {"_id": ObjectId(task_id)},
                {"$unset": {"detail_backfill_running": "", "detail_backfill_prev_status": ""}},
            )
