from flask_restx import Namespace
from app.utils import get_logger, auth, conn_db as conn
from app import utils
from app.modules import ErrorMsg, TaskStatus
from . import ARLResource
import time
from datetime import datetime, timedelta
import psutil
from bson.objectid import ObjectId

ns = Namespace('dashboard', description="仪表盘接口")
logger = get_logger()

# 仪表盘短期内存缓存，降低高频并发统计与 RabbitMQ 连接开销
_DASHBOARD_CACHE = {
    "stats": {"data": None, "ts": 0},
    "trend": {"data": None, "ts": 0},
    "sysinfo": {"data": None, "ts": 0},
    "widgets": {"data": None, "ts": 0},
}


def _get_tz_offset_str():
    """获取当前时区偏移字符串，如 '+08:00'"""
    tz_str = datetime.now().astimezone().strftime("%z")  # e.g. '+0800'
    if len(tz_str) == 5:
        return f"{tz_str[:3]}:{tz_str[3:]}"
    return "+08:00"


@ns.route('/stats')
class DashboardStats(ARLResource):
    @auth
    def get(self):
        """获取顶部统计卡片数据"""
        now = time.time()
        if _DASHBOARD_CACHE["stats"]["data"] and (now - _DASHBOARD_CACHE["stats"]["ts"] < 15):
            return utils.build_ret(ErrorMsg.Success, _DASHBOARD_CACHE["stats"]["data"])

        # 1. 总站点数量 (O(1) 极速读取元数据)
        try:
            total_assets = conn('asset_site').estimated_document_count()
        except Exception:
            total_assets = conn('asset_site').count_documents({})
        
        # 2. 今日执行任务数与今日新增站点 (通过 _id 索引范围极速命中)
        today_str = datetime.now().strftime("%Y-%m-%d") + " 00:00:00"
        today_tasks = conn('task').count_documents({"start_time": {"$gte": today_str}})
        
        today_start_dt = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_oid = ObjectId.from_datetime(today_start_dt)
        today_new_assets = conn('asset_site').count_documents({"_id": {"$gte": today_start_oid}})
        
        # 3. 漏洞分类统计 (ARL 全量 O(1) + Nuclei 单次聚合分组)
        try:
            arl_total = conn('vuln').estimated_document_count()
        except Exception:
            arl_total = conn('vuln').count_documents({})

        nuclei_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        try:
            pipeline = [
                {"$group": {"_id": "$vuln_severity", "count": {"$sum": 1}}}
            ]
            for item in conn('nuclei_result').aggregate(pipeline):
                sev = item.get("_id")
                if sev in nuclei_counts:
                    nuclei_counts[sev] = item.get("count", 0)
        except Exception as e:
            logger.error(f"Failed to aggregate nuclei severity: {e}")
            for sev in nuclei_counts:
                nuclei_counts[sev] = conn('nuclei_result').count_documents({"vuln_severity": sev})
        
        # 4. GitHub 监控数
        try:
            github_monitors = conn('github_monitor_task').estimated_document_count()
        except Exception:
            github_monitors = conn('github_monitor_task').count_documents({})
        
        data = {
            "total_assets": total_assets,
            "today_tasks": today_tasks,
            "today_new_assets": today_new_assets,
            "vuln": {
                "arl_total": arl_total,
                "nuclei_critical": nuclei_counts["critical"],
                "nuclei_high": nuclei_counts["high"],
                "nuclei_medium": nuclei_counts["medium"],
                "nuclei_low": nuclei_counts["low"]
            },
            "github_monitors": github_monitors
        }
        _DASHBOARD_CACHE["stats"] = {"data": data, "ts": time.time()}
        return utils.build_ret(ErrorMsg.Success, data)


@ns.route('/trend')
class DashboardTrend(ARLResource):
    @auth
    def get(self):
        """获取最近7天风险趋势（单次聚合管道秒级统计）"""
        now = time.time()
        if _DASHBOARD_CACHE["trend"]["data"] and (now - _DASHBOARD_CACHE["trend"]["ts"] < 60):
            return utils.build_ret(ErrorMsg.Success, _DASHBOARD_CACHE["trend"]["data"])

        # 生成最近7天日期轴
        days = []
        for i in range(6, -1, -1):
            target_date = datetime.now().astimezone() - timedelta(days=i)
            days.append(target_date.strftime("%m-%d"))

        seven_days_ago_dt = (datetime.now().astimezone() - timedelta(days=6)).replace(hour=0, minute=0, second=0, microsecond=0)
        start_oid = ObjectId.from_datetime(seven_days_ago_dt)
        tz_offset = _get_tz_offset_str()

        # 通用按 ObjectId 日期聚合函数 (采用 $convert 提供异常数据容错保护)
        def _aggregate_daily_by_oid(col_name):
            counts = {}
            pipeline = [
                {"$match": {"_id": {"$gte": start_oid}}},
                {"$group": {
                    "_id": {
                        "$dateToString": {
                            "format": "%m-%d",
                            "date": {
                                "$convert": {
                                    "input": "$_id",
                                    "to": "date",
                                    "onError": None,
                                    "onNull": None
                                }
                            },
                            "timezone": tz_offset
                        }
                    },
                    "count": {"$sum": 1}
                }}
            ]
            try:
                for item in conn(col_name).aggregate(pipeline):
                    day_key = item.get("_id")
                    if day_key:
                        counts[day_key] = item.get("count", 0)
            except Exception as e:
                logger.error(f"Trend aggregation failed on {col_name}: {e}")
            return counts

        # 并行/单次聚合各指标
        asset_counts = _aggregate_daily_by_oid('asset_site')
        vuln_counts = _aggregate_daily_by_oid('vuln')
        nuclei_counts = _aggregate_daily_by_oid('nuclei_result')
        leak_counts = _aggregate_daily_by_oid('github_monitor_result')
        cve_counts = _aggregate_daily_by_oid('github_cve_history')

        assets = [asset_counts.get(d, 0) for d in days]
        vulns = [vuln_counts.get(d, 0) + nuclei_counts.get(d, 0) for d in days]
        leaks = [leak_counts.get(d, 0) for d in days]
        cves = [cve_counts.get(d, 0) for d in days]

        data = {
            "days": days,
            "assets": assets,
            "vulns": vulns,
            "leaks": leaks,
            "cves": cves
        }
        _DASHBOARD_CACHE["trend"] = {"data": data, "ts": time.time()}
        return utils.build_ret(ErrorMsg.Success, data)


@ns.route('/logs')
class DashboardLogs(ARLResource):
    @auth
    def get(self):
        """获取系统最新动态"""
        # 过滤掉内部偶发历史报错，取最新的10条业务 syslog
        query = {
            "message": {"$not": {"$regex": "TaskStatus.*attribute.*RUNNING", "$options": "i"}}
        }
        cursor = conn('syslog').find(query, {"_id": 0}).sort("create_time", -1).limit(10)
        logs = []
        for log in cursor:
            if "create_time" in log:
                log["create_time"] = str(log["create_time"])
            logs.append(log)
        
        # 如果表是空的，预置一条启动日志方便前端展示
        if not logs:
            logs = [{
                "level": "info",
                "title": "系统启动",
                "message": "资产灯塔系统 ARL-Next 运行正常，日志系统已初始化。",
                "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }]
            
        return utils.build_ret(ErrorMsg.Success, {"logs": logs})


@ns.route('/sysinfo')
class DashboardSysInfo(ARLResource):
    @auth
    def get(self):
        """获取系统信息 (CPU, 内存, 任务队列) - 内置 3s 微缓存削峰"""
        now = time.time()
        if _DASHBOARD_CACHE["sysinfo"]["data"] and (now - _DASHBOARD_CACHE["sysinfo"]["ts"] < 3):
            return utils.build_ret(ErrorMsg.Success, _DASHBOARD_CACHE["sysinfo"]["data"])

        # 1. CPU, Memory, Disk (非阻塞实时采样)
        cpu_percent = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        mem_percent = mem.percent
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        
        # 2. Background Tasks (task & github_task)
        non_running_statuses = [TaskStatus.DONE, TaskStatus.WAITING, TaskStatus.ERROR, TaskStatus.STOP]
        running_tasks = conn('task').count_documents({"status": {"$nin": non_running_statuses}})
        waiting_tasks = conn('task').count_documents({"status": TaskStatus.WAITING})
        
        # Also check github tasks
        running_tasks += conn('github_task').count_documents({"status": {"$nin": non_running_statuses}})
        waiting_tasks += conn('github_task').count_documents({"status": TaskStatus.WAITING})

        # Also check icp tasks
        running_tasks += conn('icp_task').count_documents({"status": {"$nin": non_running_statuses}})
        waiting_tasks += conn('icp_task').count_documents({"status": TaskStatus.WAITING})
        
        # 3. RabbitMQ Real Queue Depth
        try:
            from app.celerytask import celery
            from app.modules import CeleryRoutingKey
            with celery.connection_or_acquire() as broker_conn:
                for q in [CeleryRoutingKey.ASSET_TASK, CeleryRoutingKey.ASSET_TASK_HEAVY, CeleryRoutingKey.ASSET_TASK_LIGHT, CeleryRoutingKey.GITHUB_TASK]:
                    try:
                        _, message_count, _ = broker_conn.default_channel.queue_declare(queue=q, passive=True)
                        waiting_tasks += (message_count or 0)
                    except Exception:
                        pass
        except Exception as e:
            logger.debug(f"RabbitMQ queue depth check skipped: {e}")
        
        # GitHub Business Metrics (Today's Leaks & Intel via ObjectId range)
        today_start_dt = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_oid = ObjectId.from_datetime(today_start_dt)
        
        today_github_leaks = conn('github_monitor_result').count_documents({"_id": {"$gte": today_start_oid}})
        today_github_cves = conn('github_cve_history').count_documents({"_id": {"$gte": today_start_oid}})
        today_github_hackers = conn('github_hackers_history').count_documents({"_id": {"$gte": today_start_oid}})
        today_github_intel_general = conn('github_result').count_documents({"_id": {"$gte": today_start_oid}})
        today_github_intel = today_github_intel_general + today_github_cves + today_github_hackers
        
        try:
            total_github_tools = conn('github_tools_target').estimated_document_count()
            total_github_hackers = conn('github_hackers_target').estimated_document_count()
            total_github_cves = conn('github_cve_history').estimated_document_count()
        except Exception:
            total_github_tools = conn('github_tools_target').count_documents({})
            total_github_hackers = conn('github_hackers_target').count_documents({})
            total_github_cves = conn('github_cve_history').count_documents({})
        
        data = {
            "cpu_percent": cpu_percent,
            "cpu_count": psutil.cpu_count(logical=True),
            "mem_percent": mem_percent,
            "mem_total_gb": round(mem.total / (1024 ** 3), 2),
            "disk_percent": disk_percent,
            "tasks": {
                "running": running_tasks,
                "waiting": waiting_tasks
            },
            "github_today": {
                "leaks": today_github_leaks,
                "intel": today_github_intel
            },
            "github_today_breakdown": {
                "cves": today_github_cves,
                "hackers": today_github_hackers,
                "general": today_github_intel_general
            },
            "github_totals": {
                "cves": total_github_cves,
                "tools": total_github_tools,
                "hackers": total_github_hackers
            }
        }
        _DASHBOARD_CACHE["sysinfo"] = {"data": data, "ts": time.time()}
        return utils.build_ret(ErrorMsg.Success, data)


@ns.route('/widgets')
class DashboardWidgets(ARLResource):
    @auth
    def get(self):
        """获取仪表盘拓展组件数据 (Top5指纹组件, 实时活跃任务流)"""
        now = time.time()
        if _DASHBOARD_CACHE.get("widgets") and _DASHBOARD_CACHE["widgets"]["data"] and (now - _DASHBOARD_CACHE["widgets"]["ts"] < 15):
            return utils.build_ret(ErrorMsg.Success, _DASHBOARD_CACHE["widgets"]["data"])

        # 1. Top 5 Web 指纹/服务组件分布 (带聚合容错)
        top_fingerprints = []
        try:
            pipeline = [
                {"$unwind": "$finger"},
                {"$group": {"_id": "$finger.name", "count": {"$sum": 1}}},
                {"$match": {"_id": {"$nin": ["", None, "default"]}}},
                {"$sort": {"count": -1}},
                {"$limit": 5}
            ]
            for item in conn('asset_site').aggregate(pipeline):
                name = item.get("_id")
                cnt = item.get("count", 0)
                if name:
                    top_fingerprints.append({"name": str(name), "count": cnt})
        except Exception as e:
            logger.error(f"Failed to aggregate top fingerprints: {e}")

        # 如果无 finger 聚合结果，尝试按 http_server 聚合 fallback
        if not top_fingerprints:
            try:
                pipeline_srv = [
                    {"$match": {"http_server": {"$nin": ["", None]}}},
                    {"$group": {"_id": "$http_server", "count": {"$sum": 1}}},
                    {"$sort": {"count": -1}},
                    {"$limit": 5}
                ]
                for item in conn('asset_site').aggregate(pipeline_srv):
                    name = item.get("_id")
                    cnt = item.get("count", 0)
                    if name:
                        top_fingerprints.append({"name": str(name), "count": cnt})
            except Exception as e:
                logger.error(f"Failed to aggregate http_server: {e}")

        # 2. 活跃/最新任务流 (最新 5 条)
        active_tasks = []
        try:
            non_running_statuses = [TaskStatus.DONE, TaskStatus.ERROR, TaskStatus.STOP]
            non_done_cursor = conn('task').find(
                {"status": {"$nin": non_running_statuses}},
                {"_id": 1, "name": 1, "target": 1, "status": 1, "start_time": 1, "type": 1, "site_count": 1}
            ).sort("start_time", -1).limit(5)
            
            for t in non_done_cursor:
                st = t.get("status", "running")
                if st == TaskStatus.WAITING:
                    st_label = "waiting"
                else:
                    st_label = "running"
                active_tasks.append({
                    "id": str(t.get("_id")),
                    "name": t.get("name", "未命名任务"),
                    "target": t.get("target", "-"),
                    "status": st_label,
                    "start_time": str(t.get("start_time", "")),
                    "type": t.get("type", "task"),
                    "site_count": t.get("site_count", 0)
                })

            # 如果运行中任务少于 5 条，拉取最新完成的任务补充展示
            if len(active_tasks) < 5:
                needed = 5 - len(active_tasks)
                existing_ids = [ObjectId(x["id"]) for x in active_tasks if ObjectId.is_valid(x["id"])]
                recent_cursor = conn('task').find(
                    {"_id": {"$nin": existing_ids}},
                    {"_id": 1, "name": 1, "target": 1, "status": 1, "start_time": 1, "end_time": 1, "type": 1, "site_count": 1}
                ).sort("start_time", -1).limit(needed)
                
                for t in recent_cursor:
                    st = t.get("status", "done")
                    active_tasks.append({
                        "id": str(t.get("_id")),
                        "name": t.get("name", "未命名任务"),
                        "target": t.get("target", "-"),
                        "status": st if st in ["done", "error", "stop"] else "done",
                        "start_time": str(t.get("start_time", "")),
                        "type": t.get("type", "task"),
                        "site_count": t.get("site_count", 0)
                    })
        except Exception as e:
            logger.error(f"Failed to query active tasks: {e}")

        data = {
            "top_fingerprints": top_fingerprints,
            "active_tasks": active_tasks
        }
        _DASHBOARD_CACHE["widgets"] = {"data": data, "ts": time.time()}
        return utils.build_ret(ErrorMsg.Success, data)


