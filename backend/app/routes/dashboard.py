from flask_restx import Namespace
from app.utils import get_logger, auth, conn_db as conn
from app import utils
from app.modules import ErrorMsg, TaskStatus
from . import ARLResource
from datetime import datetime, timedelta
import psutil
from bson.objectid import ObjectId

ns = Namespace('dashboard', description="仪表盘接口")
logger = get_logger()

@ns.route('/stats')
class DashboardStats(ARLResource):
    @auth
    def get(self):
        """获取顶部统计卡片数据"""
        # 1. 总站点数量
        total_assets = conn('asset_site').count({})
        
        # 2. 今日执行任务数与今日新增站点
        today_str = datetime.now().strftime("%Y-%m-%d") + " 00:00:00"
        today_tasks = conn('task').count({"start_time": {"$gte": today_str}})
        
        today_start_dt = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_oid = ObjectId.from_datetime(today_start_dt)
        today_new_assets = conn('asset_site').count({"_id": {"$gte": today_start_oid}})
        
        # 3. 漏洞分类统计 (拆分 ARL 和 Nuclei)
        arl_total = conn('vuln').count({})
        nuclei_critical = conn('nuclei_result').count({"vuln_severity": "critical"})
        nuclei_high = conn('nuclei_result').count({"vuln_severity": "high"})
        nuclei_medium = conn('nuclei_result').count({"vuln_severity": "medium"})
        nuclei_low = conn('nuclei_result').count({"vuln_severity": "low"})
        
        # 4. GitHub 监控数
        github_monitors = conn('github_monitor_task').count({})
        
        data = {
            "total_assets": total_assets,
            "today_tasks": today_tasks,
            "today_new_assets": today_new_assets,
            "vuln": {
                "arl_total": arl_total,
                "nuclei_critical": nuclei_critical,
                "nuclei_high": nuclei_high,
                "nuclei_medium": nuclei_medium,
                "nuclei_low": nuclei_low
            },
            "github_monitors": github_monitors
        }
        return utils.build_ret(ErrorMsg.Success, data)

@ns.route('/trend')
class DashboardTrend(ARLResource):
    @auth
    def get(self):
        """获取最近7天风险趋势"""
        days = []
        assets = []
        vulns = []
        leaks = []
        cves = []
        
        for i in range(6, -1, -1):
            target_date = datetime.now().astimezone() - timedelta(days=i)
            day_str = target_date.strftime("%m-%d")
            start_dt = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = target_date.replace(hour=23, minute=59, second=59, microsecond=999999)
            
            # 当日新增站点和漏洞
            start_oid = ObjectId.from_datetime(start_dt)
            end_oid = ObjectId.from_datetime(end_dt)
            c_assets = conn('asset_site').count({"_id": {"$gte": start_oid, "$lte": end_oid}})
            start_dt_str = start_dt.strftime("%Y-%m-%d %H:%M:%S")
            end_dt_str = end_dt.strftime("%Y-%m-%d %H:%M:%S")
            c_vulns = conn('vuln').count({"save_date": {"$gte": start_dt_str, "$lte": end_dt_str}}) + \
                      conn('nuclei_result').count({"save_date": {"$gte": start_dt_str, "$lte": end_dt_str}})
            
            # 当日新增 Github 动态
            c_leaks = conn('github_monitor_result').count({"_id": {"$gte": start_oid, "$lte": end_oid}})
            c_cves = conn('github_cve_history').count({"_id": {"$gte": start_oid, "$lte": end_oid}})
            
            days.append(day_str)
            assets.append(c_assets)
            vulns.append(c_vulns)
            leaks.append(c_leaks)
            cves.append(c_cves)
            
        data = {
            "days": days,
            "assets": assets,
            "vulns": vulns,
            "leaks": leaks,
            "cves": cves
        }
        return utils.build_ret(ErrorMsg.Success, data)

@ns.route('/logs')
class DashboardLogs(ARLResource):
    @auth
    def get(self):
        """获取系统最新动态"""
        # 取最新的10条 syslog
        cursor = conn('syslog').find({}, {"_id": 0}).sort("create_time", -1).limit(10)
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
                "message": "资产灯塔系统 ARL v2.6.2 启动成功，日志系统已初始化。",
                "create_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }]
            
        return utils.build_ret(ErrorMsg.Success, {"logs": logs})

@ns.route('/sysinfo')
class DashboardSysInfo(ARLResource):
    @auth
    def get(self):
        """获取系统信息 (CPU, 内存, 任务队列)"""
        # 1. CPU, Memory, Disk
        cpu_percent = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        mem_percent = mem.percent
        disk = psutil.disk_usage('/')
        disk_percent = disk.percent
        
        # 2. Background Tasks (task & github_task)
        # 只要不是 waiting, done, error, stop，统统算作正在运行
        non_running_statuses = [TaskStatus.DONE, TaskStatus.WAITING, TaskStatus.ERROR, TaskStatus.STOP]
        running_tasks = conn('task').count({"status": {"$nin": non_running_statuses}})
        waiting_tasks = conn('task').count({"status": TaskStatus.WAITING})
        
        # Also check github tasks
        running_tasks += conn('github_task').count({"status": {"$nin": non_running_statuses}})
        waiting_tasks += conn('github_task').count({"status": TaskStatus.WAITING})

        # Also check icp tasks
        running_tasks += conn('icp_task').count({"status": {"$nin": non_running_statuses}})
        waiting_tasks += conn('icp_task').count({"status": TaskStatus.WAITING})
        
        # GitHub Business Metrics (Today's Leaks & Intel)
        today_start_dt = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
        today_start_oid = ObjectId.from_datetime(today_start_dt)
        
        today_github_leaks = conn('github_monitor_result').count({"_id": {"$gte": today_start_oid}})
        
        today_github_cves = conn('github_cve_history').count({"_id": {"$gte": today_start_oid}})
        today_github_hackers = conn('github_hackers_history').count({"_id": {"$gte": today_start_oid}})
        today_github_intel_general = conn('github_result').count({"_id": {"$gte": today_start_oid}})
        today_github_intel = today_github_intel_general + today_github_cves + today_github_hackers
        
        total_github_tools = conn('github_tools_target').count({})
        total_github_hackers = conn('github_hackers_target').count({})
        total_github_cves = conn('github_cve_history').count({})
        
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
        return utils.build_ret(ErrorMsg.Success, data)
