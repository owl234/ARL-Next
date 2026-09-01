# 从当前目录（注意那个小点 '.' 代表当前文件夹）下的 policy.py 文件中，
# 导入名为 get_options_by_policy_id 的函数（通过策略ID获取配置选项）。
from .policy import get_options_by_policy_id

# 从当前目录下的 task.py 文件中，批量导入与任务调度和处理相关的核心函数。
# 使用小括号 () 可以让代码分行写，更加整洁易读。
from .task import (
    submit_task,                  # 提交主扫描任务
    build_task_data,              # 构建任务的数据结构（准备跑任务前的物料）
    get_ip_domain_list,           # 提取目标中的 IP 和域名列表
    submit_task_task,             # 核心调度函数：真正把任务塞给 Celery worker 去跑的地方
    submit_risk_cruising,         # 提交“风险巡航”任务（一种周期性的安全检查）
    target2list,                  # 将用户输入的各种目标格式（逗号分隔、换行等）统一转成标准的 Python 列表
    submit_add_asset_site_task    # 提交“添加资产站点”的子任务
)

# 从当前目录下的 scope.py 文件中，导入与“扫描范围（Scope）”限制相关的函数。
# 比如用来判断某个 IP 或域名是否在允许扫描的白名单内。
from .scope import (
    get_scope_by_scope_id,
    check_target_in_scope,
    update_scope_domain_status,
    get_scope_domain_stat,
    trigger_scope_domain_scan
)

# 从当前目录下的 url.py 文件中，导入通过任务ID查询 URL 结果的函数。
from .url import get_url_by_task_id

# 从当前目录下的 scheduler.py（定时调度任务模块）中，导入查重函数。
# 用来判断是不是已经有相同的“站点更新监控”或“WIH（Web Info Hunter）更新监控”任务在跑了。
from .scheduler import have_same_site_update_monitor, have_same_wih_update_monitor

# 从当前目录下的 asset_site.py（资产站点模块）中，导入查找“不在扫描范围内的站点”的函数。
from .asset_site import find_asset_site_not_in_scope


# 从当前目录下的 domain.py（域名处理模块）中，批量导入域名和 IP 的查询函数。
from .domain import (
    find_domain_by_task_id,           # 根据任务ID找普通域名
    find_private_domain_by_task_id,   # 根据任务ID找内网/私有域名
    find_public_ip_by_task_id         # 根据任务ID找公网 IP
)

