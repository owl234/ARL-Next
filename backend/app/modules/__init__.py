from .ipInfo import PortInfo, IPInfo
from .baseInfo import BaseInfo
from .domainInfo import DomainInfo
from .pageInfo import PageInfo
from .wihRecord import WihRecord
from app.config import Config


class ScanPortType:
    """
    [枚举：端口扫描策略]
    定义了几种常见的端口扫描范围，映射到 config.py 中的具体配置。
    """
    TEST = Config.TOP_10    # 测试模式：极速扫最常见的10个Web端口
    TOP100 = Config.TOP_100 # 常规模式：扫常见的100个服务端口
    TOP1000 = Config.TOP_1000 # 深度模式：扫常见的1000个端口
    ALL = "0-65535"         # 全端口扫描，极度耗时，非特殊情况不建议使用


class DomainDictType:
    """[枚举：字典类型] 域名爆破使用的字典规模"""
    TEST = Config.DOMAIN_DICT_TEST
    BIG = Config.DOMAIN_DICT_2W


class CollectSource:
    """
    [第一性原理：数据溯源]
    记录资产数据是通过什么渠道收集到的。这不仅用于界面展示“发现来源”，
    更在权重判断、置信度分析时起关键作用（比如爆破发现的置信度可能高于某个老旧第三方API）。
    """
    DOMAIN_BRUTE = "domain_brute" # 子域名爆破获取
    BAIDU = "baidu"               # 百度搜索爬取
    ALTDNS = "alt_dns"            # 组合变种词爆破
    ARL = "arl"                   # 系统内部历史数据碰撞
    SITESPIDER = "site_spider"    # 爬虫在网页中发现的链接
    SEARCHENGINE = "search_engine"# 空间测绘引擎(FOFA, Quake等)
    MONITOR = "monitor"           # 计划监控任务自动发现


class TaskStatus:
    WAITING = "waiting"
    DONE = "done"
    ERROR = "error"
    STOP = "stop"


class TaskScheduleStatus:
    DONE = "done"
    SCHEDULED = "scheduled"
    STOP = "stop"
    ERROR = "error"


class TaskTag:
    """任务标签"""

    """带资产发现的任务"""
    TASK = "task"

    """域名监控任务"""
    MONITOR = "monitor"

    """风险巡航任务"""
    RISK_CRUISING = "risk_cruising"


class TaskType:
    """
    [第一性原理：业务类型隔离]
    定义了后端引擎究竟在跑什么类型的任务。
    它决定了 Celery worker 拿到任务后，到底该走哪一条流水线 (Pipeline)。
    """
    IP = "ip"                           # IP任务流水线
    DOMAIN = "domain"                   # 域名任务流水线
    RISK_CRUISING = "risk_cruising"     # 站点风险巡航(PoC漏扫等)
    ASSET_SITE_UPDATE = "asset_site_update" # 更新资产库站点信息
    FOFA = "fofa"                       # 空间测绘查询任务
    ASSET_SITE_ADD = "asset_site_add"   # 手动录入资产站点
    ASSET_WIH_UPDATE = "asset_wih_update" # 更新资产Web信息搜集


class SiteAutoTag:
    ENTRY = "入口"
    INVALID = "无效"


class TaskSyncStatus:
    WAITING = "waiting"
    RUNNING = "running"
    ERROR = "error"
    DEFAULT = "default"


class SchedulerStatus:
    RUNNING = "running"
    STOP = "stop"


class AssetScopeType:
    DOMAIN = "domain"
    IP = "ip"


class PoCCategory:
    POC = "漏洞PoC"
    SNIFFER = "协议识别"
    SYSTEM_BRUTE = "服务弱口令"
    WEBB_RUTE = "应用弱口令"


class WebSiteFetchOption:
    # 针对WEB站点，可选功能选项
    SITE_CAPTURE = "site_capture"
    SEARCH_ENGINES = "search_engines"
    SITE_SPIDER = "site_spider"
    FILE_LEAK = "file_leak"
    POC_RUN = "poc_config"
    SITE_IDENTIFY = "site_identify"
    NUCLEI_SCAN = "nuclei_scan"  # nuclei 扫描
    Info_Hunter = "web_info_hunter"  # 对 JS 调用WebInfoHunter


class WebSiteFetchStatus:
    # 针对WEB站点任务可能的状态
    FETCH_SITE = "fetch_site"
    SITE_CAPTURE = "site_capture"
    SEARCH_ENGINES = "search_engines"
    SITE_SPIDER = "site_spider"
    FILE_LEAK = "file_leak"
    SITE_IDENTIFY = "site_identify"
    POC_RUN = "poc_run"
    NUCLEI_SCAN = "nuclei_scan"
    Info_Hunter = "web_info_hunter"  # 对 JS 调用WebInfoHunter


class CeleryRoutingKey:
    ASSET_TASK = "arltask"
    GITHUB_TASK = "arlgithub"


class CeleryAction:
    """
    [第一性原理：命令分发路由表 (Command Pattern)]
    这是连接 `helpers/task.py` (下发者) 和 `celerytask.py` (执行者) 的通信暗号。
    下发任务时，将特定的 Action 塞进消息队列；Worker 收到后，根据这个暗号
    去 action_map 里找对应的处理函数。
    如果你想给系统新增一种全新的任务类别，首先就得在这里注册它的“接头暗号”！
    """
    IP_TASK = "ip_task"                         # 暗号：跑常规IP任务
    DOMAIN_TASK = "domain_task"                 # 暗号：跑常规域名任务
    DOMAIN_EXEC_TASK = "domain_exec_task"       # 暗号：跑域名监测任务
    IP_EXEC_TASK = "ip_exec_task"               # 暗号：跑IP监测任务
    DOMAIN_TASK_SYNC_TASK = "domain_task_sync_task" # 暗号：同步已有任务资产
    RUN_RISK_CRUISING = "run_risk_cruising"     # 暗号：运行漏洞/风险巡航
    FOFA_TASK = "fofa_task"                     # 暗号：运行Fofa查询
    GITHUB_TASK_TASK = "github_task_task"       # 暗号：跑Github信息泄露搜索
    GITHUB_TASK_MONITOR = "github_task_monitor" # 暗号：跑Github监控
    ASSET_SITE_UPDATE = "asset_site_update"     # 暗号：执行资产站点更新
    ADD_ASSET_SITE_TASK = "add_asset_site_task" # 暗号：执行资产站点添加
    ASSET_WIH_UPDATE = "asset_wih_update"       # 暗号：执行资产WIH更新


error_map = {
    'CeleryIdNotFound': {
        "message": "没有找到Celery id",
        "code": 102,
    },
    'NotFoundTask': {
        "message": "没有找到任务",
        "code": 103,
    },
    "TaskIsRunning": {
        "message": "任务运行中",
        "code": 104,
    },
    "TaskIsDone": {
        "message": "任务已经完成",
        "code": 105,
    },
    "Success": {
        "message": "success",
        "code": 200,
    },
    "NotLogin": {
        "message": "未登录",
        "code": 401,
    },
    "NotFoundScopeID": {
        "message": "没有找到资产范围ID",
        "code": 601,
    },
    "NotFoundScope": {
        "message": "没有找到对应的资产范围",
        "code": 602,
    },
    "ExistScope": {
        "message": "已存在对应的资产范围",
        "code": 603,
    },
    "IntervalLessThan3600": {
        "message": "监控任务时间间隔不能小于6小时（21600s）",
        "code": 700,
    },
    "DomainNotFoundViaScope": {
        "message": "域名不在给定的资产范围中",
        "code": 701,
    },
    "DomainViaJob": {
        "message": "给定资产范围中的域名已经存在监控任务",
        "code": 699,
    },
    "DomainNotViaJob": {
        "message": "给定资产范围中的域名不存在监控任务",
        "code": 698,
    },
    "JobNotFound": {
        "message": "监控任务未找到",
        "code": 702,
    },
    "DomainInvalid": {
        "message": "域名无效",
        "code": 703,
    },
    "TargetInvalid": {
        "message": "任务目标无效",
        "code": 704,
    },
    "IPInBlackIps": {
        "message": "目标IP不允许下发",
        "code": 705,
    },
    "TaskTargetIsEmpty": {
        "message": "任务目标为空",
        "code": 706,
    },
    "TaskSyncDealing": {
        "message": "任务资产同步处理中",
        "code": 801,
    },
    "TaskTypeIsNotDomain": {
        "message": "不是域名发现任务",
        "code": 802,
    },
    "TaskTargetNotInScope": {
        "message": "任务目标不在资产组中",
        "code": 802,
    },
    "DomainInScope": {
        "message": "域名已经存在指定资产组中",
        "code": 803,
    },
    "URLInvalid": {
        "message": "URL无效",
        "code": 804,
    },
    "SiteURLNotDomain": {
        "message": "非域名类型URL",
        "code": 805,
    },
    "SiteInScope": {
        "message": "站点已在指定资产中",
        "code": 806,
    },
    "DomainNotFoundNotInScope": {
            "message": "没有发现可以添加的域名",
            "code": 807,
    },
    "SchedulerStatusNotRunning": {
        "message": "监控任务非运行状态",
        "code": 901,
    },
    "SchedulerStatusNotStop": {
        "message": "监控任务非停止状态",
        "code": 902,
    },
    "ResultSetIDNotFound": {
        "message": "结果集 ID 没有找到",
        "code": 1001,
    },
    "ResultSetIsEmpty": {
        "message": "结果集中目标为空",
        "code": 1002,
    },
    "PoCTargetIsEmpty": {
        "message": "PoC 任务目标为空",
        "code": 1003,
    },
    "QueryResultIsEmpty": {
        "message": "查询结果为空",
        "code": 1004,
    },
    "PolicyIDNotFound": {
        "message": "策略不存在",
        "code": 1100,
    },
    "RiskCruisingPoCConfigIsEmpty": {
        "message": "风险巡航任务选择的策略PoC配置字段不能为空",
        "code": 1101,
    },
    "BruteTaskBruteConfigIsEmpty": {
        "message": "弱口令任务选择的策略爆破配置字段不能为空",
        "code": 1102,
    },
    "PolicyDataIsEmpty": {
        "message": "策略数据为空",
        "code": 1103,
    },
    "FofaConnectError": {
        "message": "连接Fofa API异常",
        "code": 1201,
    },
    "FofaKeyError": {
        "message": "Fofa 认证信息错误",
        "code": 1202,
    },
    "FofaResultEmpty": {
        "message": "Fofa 查询结果为空",
        "code": 1203,
    },
    "SiteIdNotFound": {
        "message": "站点没有找到",
        "code": 1300,
    },
    "SiteTagIsExist": {
        "message": "站点标签已经存在",
        "code": 1301,
    },
    "SiteTagNotExist": {
        "message": "站点标签没有找到",
        "code": 1302,
    },
    "ScopeTypeIsNotIP": {
        "message": "资产组IP范围无效",
        "code": 1303,
    },
    "IsForbiddenDomain": {
        "message": "包含在禁止域名内",
        "code": 1401,
    },
    "RuleInvalid": {
        "message": "规则无效",
        "code": 1402,
    },
    "GithubKeywordEmpty": {
        "message": "关键字为空",
        "code": 1501,
    },
    "Error": {
        "message": "系统异常",
        "code": 500,
    },
    "CronError": {
        "message": "Cron 表达式错误",
        "code": 1502,
    },
    "IPInvalid": {
        "message": "IP 无效",
        "code": 1503,
    },
    "IPNotFoundViaScope": {
        "message": "不在给定的资产范围中",
        "code": 1504,
    },
    "PortCustomInvalid": {
        "message": "自定义端口信息错误",
        "code": 1506,
    },
    "TaskScheduleTypeInvalid": {
        "message": "计划任务类型错误",
        "code": 1601,
    },
    "DateInvalid": {
        "message": "时间错误",
        "code": 1602,
    },
    "TaskTagInvalid": {
        "message": "任务类型错误",
        "code": 1603,
    },
    "FutureDateInvalid": {
        "message": "时间已经过去了",
        "code": 1604,
    },
    "TaskScheduleNotFound": {
        "message": "计划任务没有找到",
        "code": 1605,
    },
    "DomainSiteViaJob": {
        "message": "资产站点更新任务已存在",
        "code": 1607,
    },
    "AddAssetSiteNotSupportIP": {
        "message": "不支持对IP资产组添加站点",
        "code": 1608,
    },
    "RuleAlreadyExists": {
        "message": "规则已存在",
        "code": 1609,
    },
    "ExcludePortsInvalid": {
        "message": "nmap 排除端口错误",
        "code": 1610,
    },
}


class ErrorMsg:
    CeleryIdNotFound = error_map["CeleryIdNotFound"]
    NotFoundTask = error_map["NotFoundTask"]
    TaskIsRunning = error_map["TaskIsRunning"]
    TaskIsDone = error_map["TaskIsDone"]
    Success = error_map["Success"]
    NotLogin = error_map["NotLogin"]
    NotFoundScopeID = error_map["NotFoundScopeID"]
    NotFoundScope = error_map["NotFoundScope"]
    ExistScope = error_map["ExistScope"]
    IntervalLessThan3600 = error_map["IntervalLessThan3600"]
    DomainNotFoundViaScope = error_map["DomainNotFoundViaScope"]
    DomainViaJob = error_map["DomainViaJob"]
    DomainNotViaJob = error_map["DomainNotViaJob"]
    JobNotFound = error_map["JobNotFound"]
    DomainInvalid = error_map["DomainInvalid"]
    TargetInvalid = error_map["TargetInvalid"]
    IPInBlackIps = error_map["IPInBlackIps"]
    TaskSyncDealing = error_map["TaskSyncDealing"]
    TaskTypeIsNotDomain = error_map["TaskTypeIsNotDomain"]
    TaskTargetNotInScope = error_map["TaskTargetNotInScope"]
    DomainInScope = error_map["DomainInScope"]
    SiteInScope = error_map["SiteInScope"]
    URLInvalid = error_map["URLInvalid"]
    SiteURLNotDomain = error_map["SiteURLNotDomain"]
    SchedulerStatusNotRunning = error_map["SchedulerStatusNotRunning"]
    SchedulerStatusNotStop = error_map["SchedulerStatusNotStop"]
    DomainNotFoundNotInScope = error_map["DomainNotFoundNotInScope"]
    ResultSetIDNotFound = error_map["ResultSetIDNotFound"]
    ResultSetIsEmpty = error_map["ResultSetIsEmpty"]
    PoCTargetIsEmpty = error_map["PoCTargetIsEmpty"]
    QueryResultIsEmpty = error_map["QueryResultIsEmpty"]
    TaskTargetIsEmpty = error_map["TaskTargetIsEmpty"]
    PolicyIDNotFound = error_map["PolicyIDNotFound"]
    PolicyDataIsEmpty = error_map["PolicyDataIsEmpty"]
    RiskCruisingPoCConfigIsEmpty = error_map["RiskCruisingPoCConfigIsEmpty"]
    BruteTaskBruteConfigIsEmpty = error_map["BruteTaskBruteConfigIsEmpty"]
    FofaConnectError = error_map["FofaConnectError"]
    FofaKeyError = error_map["FofaKeyError"]
    FofaResultEmpty = error_map["FofaResultEmpty"]
    SiteIdNotFound = error_map["SiteIdNotFound"]
    SiteTagIsExist = error_map["SiteTagIsExist"]
    SiteTagNotExist = error_map["SiteTagNotExist"]
    ScopeTypeIsNotIP = error_map["ScopeTypeIsNotIP"]
    IsForbiddenDomain = error_map["IsForbiddenDomain"]
    RuleInvalid = error_map["RuleInvalid"]
    GithubKeywordEmpty = error_map["GithubKeywordEmpty"]
    Error = error_map["Error"]
    CronError = error_map["CronError"]
    IPInvalid = error_map["IPInvalid"]
    IPNotFoundViaScope = error_map["IPNotFoundViaScope"]
    PortCustomInvalid = error_map["PortCustomInvalid"]
    TaskScheduleTypeInvalid = error_map["TaskScheduleTypeInvalid"]
    DateInvalid = error_map["DateInvalid"]
    TaskTagInvalid = error_map["TaskTagInvalid"]
    FutureDateInvalid = error_map["FutureDateInvalid"]
    TaskScheduleNotFound = error_map["TaskScheduleNotFound"]
    DomainSiteViaJob = error_map["DomainSiteViaJob"]
    AddAssetSiteNotSupportIP = error_map["AddAssetSiteNotSupportIP"]
    RuleAlreadyExists = error_map["RuleAlreadyExists"]
    ExcludePortsInvalid = error_map["ExcludePortsInvalid"]

