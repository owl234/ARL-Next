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


async def _claim_recon_task(task_id):
    result = await db['icp_task'].update_one(
        {"_id": ObjectId(task_id), "status": "waiting"},
        {"$set": {"status": "running", "start_time": curr_date()}}
    )
    return result.matched_count == 1


async def _build_osint_proxy_router(options=None, syslog_cb=None):
    """初始化任务级 OSINT 多节点路由器，兼容 proxy_bundle 与 MongoDB 兜底同步。"""
    import os
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from proxy_router import OsintProxyRouter
    bundle = options.get("proxy_bundle") if isinstance(options, dict) else None
    legacy_proxy = options.get("proxy_url") if isinstance(options, dict) else None
    router = OsintProxyRouter(bundle=bundle, db=db, legacy_proxy=legacy_proxy, syslog_cb=syslog_cb)
    await router.sync_from_db(db)
    return router


async def _task_is_running(task_id):
    task = await db['icp_task'].find_one({"_id": ObjectId(task_id)}, {"status": 1})
    return task is not None and task.get("status") == "running"

async def run_recon_job(options):
    logger.info(f"Entering run_recon_job with options: {options}")
    options.get("task_id")
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
    if not task_id or not target:
        logger.error(f"Missing required ICP params for task {task_id}")
        if task_id:
            await _abort_recon_task(task_id, "ICP查询", "任务派发参数不完整(缺少 task_id 或查询目标)，无法启动查询")
        return

    if not await _claim_recon_task(task_id):
        logger.warning(f"ICP task {task_id} claim rejected (already running or not in waiting state)")
        await _log_rejected_claim(task_id, "ICP查询")
        return

    total_assets = 0
    error_msg = []
    
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
    
    counts = {"web": 0, "app": 0, "mapp": 0, "kapp": 0}
    
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
    proxy_router = await _build_osint_proxy_router(options, syslog_cb=insert_syslog)
    if hasattr(myicp, "attach_proxy_router"):
        myicp.attach_proxy_router(proxy_router)
    if proxy_router.has_structured_policy and proxy_router.get_mode() != "direct_only":
        await insert_syslog(
            "info", "出口策略",
            f"OSINT 出口策略模式: {proxy_router.get_mode()}，已绑定备用代理节点 {len(proxy_router.nodes)} 个"
        )
    await insert_syslog("info", "ICP查询", f"任务开始运行，目标: {target}，类型: {query_types}")

    for idx, qt in enumerate(query_types):
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
                res = await handlers[qt](target, "", "", proxy=sys_proxy)
                if not await _task_is_running(task_id):
                    return
                if res.get("code") == 200 and res.get("params"):
                    assets = res["params"].get("list", [])
                    if assets:
                        for asset in assets:
                            asset.pop('_id', None)
                            asset['task_id'] = task_id
                            asset['query_type'] = qt
                        await db['icp_asset'].insert_many(assets, ordered=False)
                    total_assets += len(assets)
                    counts[qt] += len(assets)
                    await update_stats()
                    await insert_syslog("info", f"{qt}查询", f"获取完成，共计 {len(assets)} 条资产")

                    # 详情降级可观测：上游在 params 上回传缺口量，避免"任务成功但列大面积空白"
                    missing = res["params"].get("_detail_missing") or 0
                    if missing:
                        reason = "触发创宇盾风控熔断" if res["params"].get("_detail_waf") else "详情接口未返回有效数据"
                        error_msg.append(f"{qt}: {reason}，{missing} 条详情缺失")
                        await insert_syslog(
                            "warning", f"{qt}查询",
                            f"数据已入库但详情不完整：{missing} 条缺失（{reason}），可稍后重跑本任务补全"
                        )
                elif res.get("code") != 200:
                    err_text = res.get('msg') or res.get('message') or 'error'
                    error_msg.append(f"{qt}: {err_text}")
                    await insert_syslog("warning", f"{qt}查询", f"接口返回异常: {err_text}")
            except Exception as e:
                logger.error(f"ICP Query exception for {qt}: {e}")
                error_msg.append(f"{qt} error: {str(e)}")
                await insert_syslog("error", f"{qt}查询", f"执行过程发生异常: {str(e)}")
        
    # 终态判定口径（与 TYC 任务保持一致）：
    # 只要成功抓取到资产即视为完成，确保前端【同步】资产组按钮畅通；
    # 仅当未入库任何资产且存在致命错误时，才标记为异常失败。
    task_status = "done" if total_assets > 0 else ("error" if error_msg else "done")
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
            }
        }
    }
    if error_msg:
        update_data["$set"]["error_msg"] = "; ".join(error_msg)
    await _finish_recon_task(task_id, task_status, update_data)
    await insert_syslog("info", "任务完成", f"ICP查询任务执行结束，共获取 {total_assets} 条资产")
    logger.info(f"ICP query task {task_id} completed.")


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
        item['category'] = item.get('classes') or item.get('category') or ''
        if company_name and not item.get('unitName'):
            item['unitName'] = company_name
    elif query_type == 'mapp':
        item['serviceLicence'] = item.get('serviceFilingNumber') or item.get('serviceLicence') or ''
        item['updateRecordTime'] = item.get('examineDate') or item.get('updateRecordTime') or ''
        if isinstance(item.get('miniProgramIcpRecordDetail'), dict):
            item['unitName'] = item['miniProgramIcpRecordDetail'].get('icpFilingSubjectInformation', {}).get('organizingName', '')
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


async def _upsert_task_asset(task_id, query_type, asset, company_name, task_assets_index, source="tyc"):
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
        update_fields = {}
        # 1. 归属单位（以最新记录优先更新）
        target_unit = asset.get("unitName") or company_name
        if target_unit:
            update_fields["unitName"] = target_unit
            update_fields["companyName"] = target_unit

        # 2. 备案号
        lic_val = asset.get("serviceLicence") or asset.get("serviceFilingNumber") or asset.get("liscense") or asset.get("mainLicence")
        if lic_val:
            update_fields["serviceLicence"] = lic_val
            update_fields["liscense"] = lic_val
            if query_type in ["mapp", "kapp"]:
                update_fields["serviceFilingNumber"] = lic_val

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

        # 5. 链接与主页
        hu = asset.get("homeUrl") or asset.get("webSite") or asset.get("href") or asset.get("url")
        if hu:
            if isinstance(hu, list) and hu:
                update_fields["homeUrl"] = hu[0]
            elif isinstance(hu, str):
                update_fields["homeUrl"] = hu
                if query_type == "weibo":
                    update_fields["href"] = hu

        # 6. 分类/图标/简介/微信号
        if asset.get("category") or asset.get("classes"):
            update_fields["category"] = asset.get("category") or asset.get("classes")
        if asset.get("icon") or asset.get("titleImgURL") or asset.get("codeImg") or asset.get("ico"):
            update_fields["icon"] = asset.get("icon") or asset.get("titleImgURL") or asset.get("codeImg") or asset.get("ico")
        if asset.get("brief") or asset.get("recommend") or asset.get("info"):
            update_fields["brief"] = asset.get("brief") or asset.get("recommend") or asset.get("info")
        if asset.get("wechatId") or asset.get("publicNum"):
            update_fields["wechatId"] = asset.get("wechatId") or asset.get("publicNum")
        if asset.get("miniProgramIcpRecordDetail"):
            update_fields["miniProgramIcpRecordDetail"] = asset.get("miniProgramIcpRecordDetail")

        if source == "icp":
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
        if key:
            index_dict[key] = new_id
        if lic_key:
            index_dict[lic_key] = new_id
        return True


async def _run_company_icp_enrichment(task_id, company_name, myicp, task_assets_index, counts, total_assets_holder, insert_syslog, update_stats, proxy=None):
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
        try:
            res = await handler(company_name, "", "", proxy=proxy)
            if res.get("code") == 200 and res.get("params"):
                assets = res["params"].get("list", [])
                new_count = 0
                merged_count = 0
                if assets:
                    for asset in assets:
                        asset.pop('_id', None)
                        is_new = await _upsert_task_asset(
                            task_id=task_id,
                            query_type=qt,
                            asset=asset,
                            company_name=company_name,
                            task_assets_index=task_assets_index,
                            source="icp"
                        )
                        if is_new:
                            new_count += 1
                        else:
                            merged_count += 1

                if new_count > 0:
                    counts[qt] = counts.get(qt, 0) + new_count
                    total_assets_holder[0] += new_count
                    await update_stats()

                if new_count > 0 or merged_count > 0:
                    await insert_syslog("info", "工信部查重", f"主体【{company_name}】工信部 {label} 查重完成：智能补全强化 {merged_count} 条，新增漏网资产 {new_count} 条")
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


async def run_tyc_job(options):
    task_id = options.get("task_id")
    gid = options.get("gid")
    depth = min(25, max(1, int(options.get("depth", 1) or 1)))
    invest_ratio = options.get("invest_ratio", 0)
    query_types = options.get("query_type", [])
    enable_icp = bool(options.get("enable_icp", True))
    tyc_id = options.get("tyc_id")
    tyc_token = options.get("tyc_token")
    if not task_id or not tyc_id or not tyc_token:
        logger.error(f"Missing required TYC params for task {task_id}")
        if task_id:
            await _abort_recon_task(task_id, "派发参数缺失", "任务派发参数不完整(缺少 task_id / 天眼查凭据)，无法启动测绘")
        return
    if not await _claim_recon_task(task_id):
        logger.warning(f"TYC task {task_id} claim rejected (already running or not in waiting state)")
        await _log_rejected_claim(task_id, "TYC查询")
        return
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
    gid_to_name = {}
    root_company_name = ""
    # 优先从 task 传参或数据库读取已解析好的官方 company_name
    if options.get("company_name"):
        root_company_name = options.get("company_name").strip()
    if not root_company_name:
        task_doc = await db['icp_task'].find_one({"_id": ObjectId(task_id)}, {"company_name": 1})
        if task_doc and task_doc.get("company_name"):
            root_company_name = task_doc.get("company_name").strip()

    sys_proxy = await _resolve_system_proxy(options)
    proxy_router = await _build_osint_proxy_router(options, syslog_cb=insert_syslog)
    client = AsyncTycClient(gid=tyc_id, token=tyc_token, proxy=sys_proxy, proxy_router=proxy_router)
    if myicp and hasattr(myicp, "attach_proxy_router"):
        myicp.attach_proxy_router(proxy_router)
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

    type_map = {
        "invest": "对外投资",
        "web": "备案网站",
        "app": "APP",
        "mapp": "小程序",
        "wechat": "微信公众号",
        "weibo": "微博"
    }
    modules_str = ",".join([type_map.get(qt, qt) for qt in query_types])
    ratio_str = f"{invest_ratio}%" if invest_ratio and float(invest_ratio) > 0 else "无限制"
    icp_tip = "开启" if enable_icp else "关闭"
    config_msg = f"任务开始运行，配置如下：目标(GID): {gid}，查询层数: {depth}，最低投资比例: {ratio_str}，需查询模块: {modules_str}，工信部ICP联动: {icp_tip}"
    await insert_syslog("info", "TYC查询", config_msg)
    if icp_init_error:
        await insert_syslog(
            "warning", "工信部查重",
            f"工信部备案查询模块初始化失败，本次任务已自动降级为纯天眼查测绘，"
            f"不含工信部官方备案补全：{icp_init_error}"
        )

    visited_gids = {str(gid)}
    gids_to_query = [gid]
    try:
        for level in range(depth):
            await insert_syslog("info", "TYC查询", f"开始执行第 {level + 1} 层穿透查询，共 {len(gids_to_query)} 个目标...")
            next_gids = []
            for idx, current_gid in enumerate(gids_to_query):
                # 在抓取每家公司前检查任务是否被中止
                task_info = await db['icp_task'].find_one({"_id": ObjectId(task_id)}, {"status": 1})
                if not task_info or task_info.get("status") != "running":
                    await insert_syslog("warning", "任务中止", "检测到任务已被手动停止，退出执行流程。")
                    logger.info(f"Task {task_id} manually stopped.")
                    return

                current_company_name = root_company_name if current_gid == gid else gid_to_name.get(str(current_gid), "")
                if not current_company_name:
                    try:
                        current_company_name = await client.get_company_name(current_gid)
                        if current_company_name:
                            gid_to_name[str(current_gid)] = current_company_name
                            if current_gid == gid:
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
                                    is_new = await _upsert_task_asset(task_id, 'invest', item, current_company_name, task_assets_index, source="tyc")
                                    sub_gid = str(item.get("id"))
                                    sub_name = item.get("name")
                                    if sub_gid and sub_name:
                                        gid_to_name[sub_gid] = sub_name.strip()
                                    if sub_gid and sub_gid not in visited_gids:
                                        visited_gids.add(sub_gid)
                                        next_gids.append(item.get("id"))
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
                            new_web_count = 0
                            merged_web_count = 0
                            for item in web_list:
                                item = _normalize_tyc_asset(item, 'web', company_name=current_company_name)
                                is_new = await _upsert_task_asset(task_id, 'web', item, current_company_name, task_assets_index, source="tyc")
                                if is_new:
                                    new_web_count += 1
                                else:
                                    merged_web_count += 1

                            counts["web"] += new_web_count
                            total_assets_holder[0] += new_web_count
                            await update_stats()
                            log_tip = f"新增 {new_web_count} 条记录"
                            if merged_web_count > 0:
                                log_tip += f"，全局域名去重合并 {merged_web_count} 条"
                            await insert_syslog("info", "网站查询", f"目标 {current_gid} 网站备案查询完成，{log_tip}")
                    except Exception as e:
                        logger.error(f"TYC Query exception for web: {e}")
                        error_msg.append(f"web error: {str(e)}")
                        await insert_syslog("error", "网站查询", f"目标 {current_gid} 网站查询异常: {str(e)}")

                # App查询
                if "app" in query_types:
                    await asyncio.sleep(random.uniform(2.0, 5.0))
                    try:
                        await insert_syslog("info", "APP查询", f"正在查询目标 {current_gid} 的APP...")
                        app_list = await client.get_app_list(current_gid)
                        if app_list:
                            new_app_count = 0
                            merged_app_count = 0
                            for item in app_list:
                                item = _normalize_tyc_asset(item, 'app', company_name=current_company_name)
                                is_new = await _upsert_task_asset(task_id, 'app', item, current_company_name, task_assets_index, source="tyc")
                                if is_new:
                                    new_app_count += 1
                                else:
                                    merged_app_count += 1

                            counts["app"] += new_app_count
                            total_assets_holder[0] += new_app_count
                            await update_stats()
                            log_tip = f"新增 {new_app_count} 条记录"
                            if merged_app_count > 0:
                                log_tip += f"，同名APP去重合并 {merged_app_count} 条"
                            await insert_syslog("info", "APP查询", f"目标 {current_gid} APP查询完成，{log_tip}")
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
                            new_wechat_count = 0
                            merged_wechat_count = 0
                            for item in wechat_list:
                                item = _normalize_tyc_asset(item, 'wechat', company_name=current_company_name)
                                is_new = await _upsert_task_asset(task_id, 'wechat', item, current_company_name, task_assets_index, source="tyc")
                                if is_new:
                                    new_wechat_count += 1
                                else:
                                    merged_wechat_count += 1

                            counts["wechat"] += new_wechat_count
                            total_assets_holder[0] += new_wechat_count
                            await update_stats()
                            log_tip = f"新增 {new_wechat_count} 条记录"
                            if merged_wechat_count > 0:
                                log_tip += f"，同名公众号去重合并 {merged_wechat_count} 条"
                            await insert_syslog("info", "微信查询", f"目标 {current_gid} 微信查询完成，{log_tip}")
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
                            new_weibo_count = 0
                            merged_weibo_count = 0
                            for item in weibo_list:
                                item = _normalize_tyc_asset(item, 'weibo', company_name=current_company_name)
                                is_new = await _upsert_task_asset(task_id, 'weibo', item, current_company_name, task_assets_index, source="tyc")
                                if is_new:
                                    new_weibo_count += 1
                                else:
                                    merged_weibo_count += 1

                            counts["weibo"] += new_weibo_count
                            total_assets_holder[0] += new_weibo_count
                            await update_stats()
                            log_tip = f"新增 {new_weibo_count} 条记录"
                            if merged_weibo_count > 0:
                                log_tip += f"，同链接微博去重合并 {merged_weibo_count} 条"
                            await insert_syslog("info", "微博查询", f"目标 {current_gid} 微博查询完成，{log_tip}")
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
                            new_mapp_count = 0
                            merged_mapp_count = 0
                            for item in mapp_list:
                                item = _normalize_tyc_asset(item, 'mapp', company_name=current_company_name)
                                is_new = await _upsert_task_asset(task_id, 'mapp', item, current_company_name, task_assets_index, source="tyc")
                                if is_new:
                                    new_mapp_count += 1
                                else:
                                    merged_mapp_count += 1

                            counts["mapp"] += new_mapp_count
                            total_assets_holder[0] += new_mapp_count
                            await update_stats()
                            log_tip = f"新增 {new_mapp_count} 条记录"
                            if merged_mapp_count > 0:
                                log_tip += f"，同名小程序去重合并 {merged_mapp_count} 条"
                            await insert_syslog("info", "小程序查询", f"目标 {current_gid} 小程序查询完成，{log_tip}")
                    except Exception as e:
                        logger.error(f"TYC Query exception for mapp: {e}")
                        error_msg.append(f"mapp error: {str(e)}")
                        await insert_syslog("error", "小程序查询", f"目标 {current_gid} 小程序查询异常: {str(e)}")

                # 工信部官方备案双轨查重与补全 (针对当前企业实体)
                if enable_icp and myicp:
                    if current_company_name:
                        await _run_company_icp_enrichment(
                            task_id=task_id,
                            company_name=current_company_name,
                            myicp=myicp,
                            task_assets_index=task_assets_index,
                            counts=counts,
                            total_assets_holder=total_assets_holder,
                            insert_syslog=insert_syslog,
                            update_stats=update_stats,
                            proxy=sys_proxy
                        )
                    else:
                        await insert_syslog("warning", "工信部查重", f"企业 GID {current_gid} 未能获取到官方全称，跳过工信部二次查重")

            gids_to_query = next_gids
            if not gids_to_query:
                break
    finally:
        if myicp:
            try:
                await myicp.cleanup()
            except Exception:
                pass

    tyc_task_status = "done" if total_assets_holder[0] > 0 else ("error" if error_msg else "done")
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
            }
        }
    }
    if error_msg:
        update_data["$set"]["error_msg"] = "; ".join(error_msg)
    await _finish_recon_task(task_id, tyc_task_status, update_data)
    await insert_syslog("info", "任务完成", f"TYC+工信部联合测绘任务执行结束，共获取 {total_assets_holder[0]} 条资产")
    logger.info(f"TYC query task {task_id} completed.")
