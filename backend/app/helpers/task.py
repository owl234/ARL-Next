import bson
import re
from app import utils
from app.modules import TaskStatus, TaskTag, TaskType, CeleryAction

# 初始化日志记录器
logger = utils.get_logger()


def target2list(target):
    """
    目标清晰函数:把用户乱七八糟的输入,变成干净、无重复的列表.
    :param target:
    :return:
    """
    # 1. 掐头去尾去空格，并全部转换为小写字母（统一标准）
    target = target.strip().lower()

    # 2. 使用正则表达式 (re) 进行切割。r",|\s" 意思是：只要遇到“逗号”或者“任何空白符(包括空格、换行等)”，就切一刀。
    # 这样用户无论是用逗号隔开，还是分行输入，都能被正确切成一个个独立的目标。
    target_lists = re.split(r",|\s", target)

    # 3. 清除空白符：利用 filter 函数把切割过程中可能产生的“空字符串”过滤掉
    target_lists = list(filter(None, target_lists))

    # 4. 去重：把列表转换成集合(set，集合天生没有重复元素)，再转回列表
    target_lists = list(set(target_lists))

    return target_lists


def get_ip_domain_list(target):
    """
    目标分流与安检函数:将干净的列表分类为IP集合和域名集合,并拦截黑名单.
    :param target:
    :return:
    """
    # 1. 调用上面的清洗函数，拿到干净的目标列表
    target_lists = target2list(target)

    # 2. 准备两个“筐”（空集合 set() ），一个装 IP，一个装域名
    ip_list = set()
    domain_list = set()

    # 3. 开始遍历每一个清洗后的目标
    for item in target_lists:
        # 如果是空的，直接跳过（防守型编程）
        if not item:
            continue

        # 【安检通道 A：IP 地址】
        # 判断是不是合法的 IP 地址（原作者这里拼写错了：vaild -> valid，理解即可）
        if utils.is_vaild_ip_target(item):
            # 查黑名单：如果在黑名单里，立刻拉响警报（抛出异常，中断任务）
            if not utils.not_in_black_ips(item):
                raise Exception("{} 在黑名单IP中".format(item))
            # 没问题，扔进 IP 筐
            ip_list.add(item)

        # 【安检通道 B：禁止的特殊域名】
        # 比如 .gov.cn 等国家级域名，绝对不能瞎扫描，直接报警中断！
        elif utils.domain.is_forbidden_domain(item):
            raise Exception("{} 包含在禁止域名内".format(item))

        # 【安检通道 C：普通域名】
        # 判断是不是合法的域名
        elif utils.is_valid_domain(item):
            # 查系统黑名单
            if utils.check_domain_black(item):
                raise Exception("{} 包含在系统黑名单中".format(item))
            # 没问题，扔进域名筐
            domain_list.add(item)

        # 【安检通道 D：模糊匹配域名】
        # 比如 *.baidu.com 这种带星号的泛域名
        elif utils.is_valid_fuzz_domain(item):
            domain_list.add(item)

        # 【全都不符合】
        else:
            # 既不是IP也不是域名，直接报错退回
            raise Exception("{} 无效的目标".format(item))

    # 4. 安检全部通过，返回装满合格目标的两个筐
    return ip_list, domain_list


def build_task_data(task_name, task_target, task_type, task_tag, options):
    """
    构建任务数据函数:把散装的参数打包成一个标准的字典,也就是准备存入MongoDB的数据格式
    :param task_name:
    :param task_target:
    :param task_type:
    :param task_tag:
    :param options:
    :return:
    """
    # 1. 检查任务类型 (task_type) 是否合法
    # 只能是 IP扫描、域名扫描 或 风险巡航
    avail_task_type = [TaskType.IP, TaskType.DOMAIN, TaskType.RISK_CRUISING]
    if task_type not in avail_task_type:
        raise Exception("{} 无效的 task_type".format(task_type))

    # 2. 检查任务标签 (task_tag) 是否合法
    # 只能是 风险巡航、监控 或 普通任务
    avail_task_tag = [TaskTag.RISK_CRUISING, TaskTag.MONITOR, TaskTag.TASK]
    if task_tag not in avail_task_tag:
        raise Exception("{} 无效的 task_tag".format(task_tag))

    # 3. 检查配置选项 (options) 必须是字典格式（包含各种扫描开关和策略）
    if not isinstance(options, dict):
        raise Exception("{} 不是 dict".format(options))

    # 4. 复制一份选项，防止修改原始数据
    options_cp = options.copy()

    # 5. 自动纠偏逻辑：如果是纯 IP 扫描任务，强行关闭域名相关的扫描插件
    if task_type == TaskType.IP:
        disable_options = {
            "domain_brute": False,     # 关闭域名爆破
            "alt_dns": False,          # 关闭 DNS 变异字典
            "dns_query_plugin": False, # 关闭 DNS 查询插件
            "arl_search": False        # 关闭 ARL 历史库搜索
        }
        # 更新并覆盖到我们复制的选项字典中
        options_cp.update(disable_options)

    # 6. 打包核心：构建标准的“任务档案袋” (这个结构最后会存进 MongoDB)
    task_data = {
        'name': task_name,                # 任务名称
        'target': task_target,            # 扫描目标
        'start_time': '-',                # 刚创建还没开始，所以是 '-'
        'status': TaskStatus.WAITING,     # 状态标记为“等待中(waiting)”
        'type': task_type,                # 任务类型
        "task_tag": task_tag,             # 任务标签
        'options': options_cp,            # 刚刚处理好的配置选项
        "end_time": "-",                  # 结束时间为空
        "service": [],                    # 预留空列表给后续的服务识别结果
        "celery_id": ""                   # 预留空位给稍后 Celery 分配的进程 ID
    }

    # 7. 特殊任务定制：单独对“风险巡航”任务进行界面展示优化
    if task_tag == TaskTag.RISK_CRUISING:
        poc_config = options.get("poc_config", [])  ## 获取要跑的 PoC (漏洞验证脚本) 列表

        # 如果是从历史结果集(result_set_id)发起的巡航
        if options.get("result_set_id"):
            # pop 提取并删除原字典中的这两个 key
            result_set_id = options.pop("result_set_id")
            result_set_len = options.pop("result_set_len")
            # 重新拼凑一句话给前端展示
            target_field = "目标：{}， PoC：{}".format(result_set_len, len(poc_config))
            task_data["result_set_id"] = result_set_id
        else:
            # 如果是直接输入目标发起的巡航
            target_field = "目标：{}， PoC：{}".format(len(task_target), len(poc_config))
            # 风险巡航有自己单独的字段存目标
            task_data["cruising_target"] = task_target

        # 偷梁换柱：把给普通扫描用的 target 字段，替换成上面拼凑的汉字描述，方便前端直接显示
        task_data["target"] = target_field

    return task_data


def submit_task(task_data):
    """
    底层发车函数:把准备好的“任务共担”存入数据库,并按铃叫 Celery 工人来干活
    :param task_data:
    :return:
    """

    # 局部导入 celerytask（为了防止 Python 中的“循环导入”报错，这在大型项目里很常见）
    from app import celerytask

    target = task_data["target"]
    # 1. 存档：把刚建好的任务工单先存进 MongoDB 的 'task' 表里
    utils.conn_db('task').insert_one(task_data)

    # 2. 拿流水号：MongoDB 会自动生成一个自带的专属 ID（_id）。
    # 使用 pop 把它拿出来并从字典里删掉，然后转成普通字符串，存为我们自己定义的 task_id。
    task_id = str(task_data.pop("_id"))
    task_data["task_id"] = task_id

    # 3. 翻译动作指令：把系统的“任务类型”翻译成 Celery 工人能听懂的“动作指令”
    celery_action = ""
    type_map_action = {
        TaskType.DOMAIN: CeleryAction.DOMAIN_TASK,           # 域名任务
        TaskType.IP: CeleryAction.IP_TASK,                   # IP任务
        TaskType.RISK_CRUISING: CeleryAction.RUN_RISK_CRUISING, # 风险巡航
        TaskType.ASSET_SITE_UPDATE: CeleryAction.ASSET_SITE_UPDATE,
        TaskType.FOFA: CeleryAction.FOFA_TASK,
        TaskType.ASSET_SITE_ADD: CeleryAction.ADD_ASSET_SITE_TASK,
        TaskType.ASSET_WIH_UPDATE: CeleryAction.ASSET_WIH_UPDATE,
    }

    task_type = task_data["type"]
    if task_type in type_map_action:
        celery_action = type_map_action[task_type]

    # 断言：确保一定拿到了动作指令，拿不到就直接报错崩溃（防御式编程）
    assert celery_action

    # 4. 再次打包：把指令和工单包在一起，准备发给工人
    task_options = {
        "celery_action": celery_action,
        "data": task_data
    }

    try:
        # 5. 【真正的灵魂所在】：调用 .delay() 异步下发任务！ƒ
        # 这行代码一执行，任务就被扔进了消息队列（如 RabbitMQ/Redis），Celery 工人会在后台接单执行。
        celery_id = celerytask.arl_task.delay(options=task_options)

        # 记录日志
        logger.info("target:{} task_id:{} celery_id:{}".format(target, task_id, celery_id))

        # 6. 回写快递单号：把 Celery 分配的进程 ID (celery_id) 更新回 MongoDB 数据库里
        values = {"$set": {"celery_id": str(celery_id)}}
        task_data["celery_id"] = str(celery_id)
        utils.conn_db('task').update_one({"_id": bson.ObjectId(task_id)}, values)

    except Exception as e:
        # 7. 异常擦屁股：如果下发给工人失败了（比如消息队列挂了），
        # 赶紧把刚才存在数据库里状态还是“WAITING”的垃圾数据删掉，防止数据库里堆满永远不会执行的死任务。
        utils.conn_db('task').delete_one({"_id": bson.ObjectId(task_id), "status": TaskStatus.WAITING})
        logger.info("下发失败 {}".format(target))
        raise e # 继续往上抛出错误给前端

    return task_data


# 直接根据目标下发任务
def submit_task_task(target, name, options):
    """
    业务大管家:接收前端传来的散装目标,分门别类,调用上面的发车函数.
    :param target:
    :param name:
    :param options:
    :return:
    """
    task_data_list = []

    # 1. 唤醒第一道安检门：把目标分流成 IP 筐和 域名筐
    ip_list, domain_list = get_ip_domain_list(target)

    # 2. 处理 IP 筐：把所有 IP 缝合在一起，当成【一个大任务】下发！
    if ip_list:
        ip_target = " ".join(ip_list)# 用空格把所有 IP 拼成一个长字符串

        # 唤醒打单机：生成标准工单
        task_data = build_task_data(task_name=name, task_target=ip_target,
                                    task_type=TaskType.IP, task_tag=TaskTag.TASK,
                                    options=options)

        # 派给底层发车函数
        task_data = submit_task(task_data)
        task_data_list.append(task_data)

    # 3. 处理域名筐：把每一个域名拆开，【一个域名建一个独立任务】下发！
    if domain_list:
        for domain_target in domain_list:
            task_data = build_task_data(task_name=name, task_target=domain_target,
                                        task_type=TaskType.DOMAIN, task_tag=TaskTag.TASK,
                                        options=options)
            task_data = submit_task(task_data)
            task_data_list.append(task_data)

    # 4. 把生成的所有任务详情返回给 API 层（前端展示用）
    return task_data_list


# 风险巡航任务下发
def submit_risk_cruising(target, name, options):
    target_lists = target2list(target)
    task_data_list = []
    task_data = build_task_data(task_name=name, task_target=target_lists,
                                task_type=TaskType.RISK_CRUISING, task_tag=TaskTag.RISK_CRUISING,
                                options=options)

    task_data = submit_task(task_data)
    task_data_list.append(task_data)

    return task_data_list


def submit_add_asset_site_task(task_name: str, target: list, options: dict) -> dict:
    task_data = {
        'name': task_name,
        'target': "站点：{}".format(len(target)),
        'start_time': '-',
        'status': TaskStatus.WAITING,
        'type': TaskType.ASSET_SITE_ADD,
        "task_tag": TaskTag.RISK_CRUISING,
        'options': options,
        "end_time": "-",
        "service": [],
        "cruising_target": target,
        "celery_id": ""
    }
    task_data = submit_task(task_data)
    return task_data


def get_task_data(task_id):
    task_data = utils.conn_db('task').find_one({'_id': bson.ObjectId(task_id)})
    return task_data


def restart_task(task_id):
    name_pre = "重新运行-"
    task_data = get_task_data(task_id)
    if not task_data:
        raise Exception("没有找到 task_id : {}".format(task_id))

    # 把一些基础字段初始化
    task_data.pop("_id")
    task_data["start_time"] = "-"
    task_data["status"] = TaskStatus.WAITING
    task_data["end_time"] = "-"
    task_data["service"] = []
    task_data["celery_id"] = ""
    if "statistic" in task_data:
        task_data.pop("statistic")

    name = task_data["name"]
    if name_pre not in name:
        task_data["name"] = name_pre + name

    task_type = task_data["type"]
    task_tag = task_data.get("task_tag", "")

    # 特殊情况单独判断
    if task_type == TaskType.RISK_CRUISING and task_tag == TaskTag.RISK_CRUISING:
        if task_data.get("result_set_id"):
            raise Exception("task_id : {}, 不支持该任务重新运行".format(task_id))

    # 监控任务的重新下发有点麻烦
    if task_type == TaskType.DOMAIN and task_tag == TaskTag.MONITOR:
        raise Exception("task_id : {}, 不支持该任务重新运行".format(task_id))

    elif task_type == TaskType.IP and task_data["options"].get("scope_id"):
        raise Exception("task_id : {}, 不支持该任务重新运行".format(task_id))

    submit_task(task_data)

    return task_data
