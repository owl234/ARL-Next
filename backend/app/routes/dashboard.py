from flask_restx import Namespace
from app.utils import get_logger, auth, conn_db as conn
from app import utils
from app.modules import ErrorMsg, TaskStatus
from . import ARLResource
from datetime import datetime, timedelta
import psutil

ns = Namespace('dashboard', description="仪表盘接口")
logger = get_logger()

# 在模块加载时确保 syslog 拥有 30 天 TTL 索引
try:
    # 2592000 秒 = 30天
    conn('syslog').create_index([("create_time", 1)], expireAfterSeconds=2592000, background=True)
except Exception as e:
    logger.error("syslog ttl index error: {}".format(e))

@ns.route('/stats')
class DashboardStats(ARLResource):
    @auth
    def get(self):
        """获取顶部统计卡片数据"""
        # 1. 总资产数量 (domain + ip + site)
        total_assets = conn('asset_domain').count({}) + conn('asset_ip').count({}) + conn('asset_site').count({})
        
        # 2. 今日执行任务数与今日新增资产
        today_str = datetime.now().strftime("%Y-%m-%d") + " 00:00:00"
        today_tasks = conn('task').count({"start_time": {"$gte": today_str}})
        today_new_assets = (
            conn('asset_domain').count({"update_date": {"$gte": today_str}}) +
            conn('asset_ip').count({"update_date": {"$gte": today_str}}) +
            conn('asset_site').count({"update_date": {"$gte": today_str}})
        )
        
        # 3. 漏洞分类统计
        critical = conn('nuclei_result').count({"vuln_severity": "critical"})
        high = conn('nuclei_result').count({"vuln_severity": "high"}) + conn('vuln').count({})
        medium = conn('nuclei_result').count({"vuln_severity": "medium"})
        low = conn('nuclei_result').count({"vuln_severity": "low"})
        
        # 4. GitHub 监控数
        github_monitors = conn('github_monitor_task').count({})
        
        data = {
            "total_assets": total_assets,
            "today_tasks": today_tasks,
            "today_new_assets": today_new_assets,
            "vuln": {
                "critical": critical,
                "high": high,
                "medium": medium,
                "low": low
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
        
        for i in range(6, -1, -1):
            target_date = datetime.now() - timedelta(days=i)
            day_str = target_date.strftime("%m-%d")
            start = target_date.strftime("%Y-%m-%d 00:00:00")
            end = target_date.strftime("%Y-%m-%d 23:59:59")
            
            # 当日新增资产和漏洞
            c_assets = conn('asset_domain').count({"update_date": {"$gte": start, "$lte": end}})
            c_vulns = conn('vuln').count({"save_date": {"$gte": start, "$lte": end}}) + \
                      conn('nuclei_result').count({"save_date": {"$gte": start, "$lte": end}})
            
            days.append(day_str)
            assets.append(c_assets)
            vulns.append(c_vulns)
            
        data = {
            "days": days,
            "assets": assets,
            "vulns": vulns
        }
        return utils.build_ret(ErrorMsg.Success, data)

@ns.route('/logs')
class DashboardLogs(ARLResource):
    @auth
    def get(self):
        """获取系统最新动态"""
        # 取最新的10条 syslog
        cursor = conn('syslog').find({}, {"_id": 0}).sort("create_time", -1).limit(10)
        logs = list(cursor)
        
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
        
        data = {
            "cpu_percent": cpu_percent,
            "mem_percent": mem_percent,
            "disk_percent": disk_percent,
            "tasks": {
                "running": running_tasks,
                "waiting": waiting_tasks
            }
        }
        return utils.build_ret(ErrorMsg.Success, data)
