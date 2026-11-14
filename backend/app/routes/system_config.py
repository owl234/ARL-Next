from flask_restx import Namespace, fields
from app.utils.security_policy import get_security_policy, update_security_policy
from app.utils.performance_config import get_performance_config, update_performance_config
from . import ARLResource
from app.utils import auth

ns = Namespace("system_config", description="系统配置API")

# 定义输入模型用于Swagger和校验
security_policy_model = ns.model('SecurityPolicy', {
    'black_ips': fields.List(fields.String, required=True, description='IP黑名单(CIDR格式)'),
    'forbidden_domains': fields.List(fields.String, required=True, description='禁止扫描域名(后缀)')
})

performance_model = ns.model('Performance', {
    # 语义限定：以下三项均为 Celery Worker 进程数（-c 参数），非单任务内的线程/发包并发度
    'celery_heavy_concurrency': fields.Integer(required=True, description='重任务队列 Worker 进程数（受内存约束）'),
    'celery_light_concurrency': fields.Integer(required=True, description='轻任务队列 Worker 进程数（走独立通道）'),
    'osint_concurrency': fields.Integer(required=True, description='OSINT 任务并发进程数（受外网反爬约束）'),
    # 非必填：旧版前端不传该字段时应保持库中现值，而非重置
    'github_concurrency': fields.Integer(required=False, description='GitHub 监控队列 Worker 进程数（原先硬编码为 2）')
})

@ns.route('/security_policy')
class SecurityPolicy(ARLResource):
    @auth
    def get(self):
        """
        获取安全策略（IP黑名单与禁止域名）
        """
        black_ips, forbidden_domains = get_security_policy()
        return {
            "code": 200,
            "message": "success",
            "data": {
                "black_ips": black_ips,
                "forbidden_domains": forbidden_domains
            }
        }

    @auth
    @ns.expect(security_policy_model)
    def post(self):
        """
        更新安全策略（IP黑名单与禁止域名）
        """
        args = self.get_parser(security_policy_model).parse_args()
        black_ips = args.get('black_ips', [])
        forbidden_domains = args.get('forbidden_domains', [])

        # 过滤空值并去重
        black_ips = list({ip.strip() for ip in black_ips if ip.strip()})
        forbidden_domains = list({domain.strip() for domain in forbidden_domains if domain.strip()})

        # 校验黑名单格式，防止非法规则导致策略解析异常
        import ipaddress
        invalid_ips = []
        for item in black_ips:
            try:
                if '-' in item:
                    first, last = item.split('-', 1)
                    start = ipaddress.ip_address(first.strip())
                    last_str = last.strip()
                    if start.version == 4 and last_str.isdigit():
                        last_str = first.strip().rsplit('.', 1)[0] + '.' + last_str
                    end = ipaddress.ip_address(last_str)
                    if start.version != end.version or int(start) > int(end):
                        raise ValueError()
                elif '/' in item:
                    ipaddress.ip_network(item, strict=False)
                else:
                    addr = ipaddress.ip_address(item)
                    if getattr(addr, 'ipv4_mapped', None):
                        addr = addr.ipv4_mapped
            except Exception:
                invalid_ips.append(item)

        if invalid_ips:
            return {
                "code": 400,
                "message": f"存在非法的 IP 黑名单条目: {', '.join(invalid_ips[:5])}"
            }, 400

        update_security_policy(black_ips, forbidden_domains)

        return {
            "code": 200,
            "message": "安全策略更新成功"
        }

_POOL_SETTLE_TIMEOUT = 12.0
_POOL_SETTLE_INTERVAL = 0.5


def _runtime_pool_size(node_stats):
    """从 stats 结果中取节点当前运行进程数；无法判定时返回 None。

    只依赖 pool.processes（存活子进程 PID 列表）。pool.max-concurrency 是池构造时的
    启动值，pool_grow/pool_shrink 不会更新它，不能当作当前并发数。
    """
    if not isinstance(node_stats, dict):
        return None
    pool = node_stats.get('pool')
    if not isinstance(pool, dict):
        return None
    processes = pool.get('processes')
    if not isinstance(processes, list):
        return None
    return len(processes)


def _wait_pool_size(inspector, node, target, timeout=_POOL_SETTLE_TIMEOUT):
    """轮询等待节点运行进程数达到 target，返回 (最终进程数, 是否达到)。

    池的伸缩由 billiard 的 Supervisor 线程异步补齐（约 0.8s 一轮），命令返回后
    进程数不会立刻变化，需要等待收敛才能判定结果。
    """
    import time
    deadline = time.monotonic() + timeout
    size = None
    while True:
        size = _runtime_pool_size((inspector.stats() or {}).get(node))
        if size == target:
            return size, True
        if time.monotonic() >= deadline:
            return size, False
        time.sleep(_POOL_SETTLE_INTERVAL)


@ns.route('/performance')
class Performance(ARLResource):
    @auth
    def get(self):
        """
        获取性能配置及实时运行进程数
        """
        config = get_performance_config()
        runtime_heavy = None
        runtime_light = None
        runtime_github = None

        try:
            from app.celerytask import celery as celery_app
            stats = celery_app.control.inspect(timeout=1.0).stats()
            if stats:
                for node, node_stats in stats.items():
                    pool_info = node_stats.get('pool', {})
                    processes = pool_info.get('processes')
                    concurrency = len(processes) if processes is not None else pool_info.get('max-concurrency', 0)
                    if 'arltask_heavy' in node:
                        runtime_heavy = (runtime_heavy or 0) + concurrency
                    elif 'arltask_light' in node:
                        runtime_light = (runtime_light or 0) + concurrency
                    elif 'arlgithub' in node:
                        runtime_github = (runtime_github or 0) + concurrency
        except Exception:
            pass

        target_heavy = config.get("celery_heavy_concurrency", 1)
        target_light = config.get("celery_light_concurrency", 1)
        target_github = config.get("github_concurrency", 1)

        pending_items = []
        if runtime_heavy is not None and runtime_heavy != target_heavy:
            pending_items.append({"queue": "arltask_heavy", "label": "重任务", "target": target_heavy, "runtime": runtime_heavy})
        if runtime_light is not None and runtime_light != target_light:
            pending_items.append({"queue": "arltask_light", "label": "轻任务", "target": target_light, "runtime": runtime_light})
        if runtime_github is not None and runtime_github != target_github:
            pending_items.append({"queue": "arlgithub", "label": "GitHub 监控", "target": target_github, "runtime": runtime_github})

        return {
            "code": 200,
            "message": "success",
            "data": {
                "celery_heavy_concurrency": target_heavy,
                "celery_light_concurrency": target_light,
                "osint_concurrency": config.get("osint_concurrency", 1),
                "github_concurrency": target_github,
                "runtime_heavy_concurrency": runtime_heavy,
                "runtime_light_concurrency": runtime_light,
                "runtime_github_concurrency": runtime_github,
                "pending_convergence": len(pending_items) > 0,
                "pending_nodes": pending_items
            }
        }

    @auth
    @ns.expect(performance_model)
    def post(self):
        """
        更新性能配置 (支持热扩缩容与精准状态反馈)
        """
        args = self.get_parser(performance_model).parse_args()
        new_heavy = args.get('celery_heavy_concurrency') or 1
        new_light = args.get('celery_light_concurrency') or 1
        new_osint = args.get('osint_concurrency') or 1
        # 未传 github_concurrency（如旧版前端）时为 None，交由 update_performance_config
        # 保留库中现值，避免一次保存把它意外重置为默认值。
        raw_github = args.get('github_concurrency')
        new_github = None

        if new_heavy < 1:
            new_heavy = 1
        if new_light < 1:
            new_light = 1
        if new_osint < 1:
            new_osint = 1
        if raw_github is not None:
            new_github = int(raw_github)
            if new_github < 1:
                new_github = 1

        old_config = get_performance_config()
        old_osint = old_config.get("osint_concurrency") or 1
        
        diff_osint = new_osint - old_osint

        update_performance_config(new_heavy, new_light, new_osint, new_github)

        feedback_messages = ["性能配置已保存。"]
        pending_nodes = []

        # 每次提交都读取运行状态，相同目标值可以重试此前失败的调整。
        # 说明：pool_grow/pool_shrink 的 ok 回复仅代表命令被接收，不代表并发数已变化
        # （billiard 的 _processes 记账值不经 inspect 暴露，shrink 在进程忙时会静默不生效）。
        # 因此调整后重新读取运行进程数，只回报实际观察到的变化。
        try:
            from app.celerytask import celery as celery_app
            inspector = celery_app.control.inspect(timeout=1.5)
            stats = inspector.stats()
            if stats:
                # github 队列仅在显式指定时参与热调整：未传该字段表示保留现值，
                # 此时不应把它拖进比对与扩缩容流程。
                queue_targets = [
                    ("arltask_heavy", new_heavy, "重任务"),
                    ("arltask_light", new_light, "轻任务"),
                ]
                if new_github is not None:
                    queue_targets.append(("arlgithub", new_github, "GitHub 监控"))

                for key, desired, label in queue_targets:
                    nodes = [node for node in stats if key in node]
                    if not nodes:
                        feedback_messages.append(f"未检测到在线的{label} Worker 节点，将在下次重启生效；")
                        pending_nodes.append({
                            "queue": key,
                            "label": label,
                            "node": None,
                            "target": desired,
                            "runtime": None,
                            "reason": "offline",
                        })
                    for node in nodes:
                        before = _runtime_pool_size(stats.get(node))
                        if before is None:
                            feedback_messages.append(f"{label}节点 {node} 未返回运行进程数，请稍后重试；")
                            pending_nodes.append({
                                "queue": key,
                                "label": label,
                                "node": node,
                                "target": desired,
                                "runtime": None,
                                "reason": "unknown_runtime",
                            })
                            continue
                        diff = desired - before
                        if diff == 0:
                            continue
                        action = "扩容" if diff > 0 else "缩容"
                        try:
                            adjust = celery_app.control.pool_grow if diff > 0 else celery_app.control.pool_shrink
                            replies = adjust(n=abs(diff), destination=[node], reply=True, timeout=1.5)
                            result = next((item[node] for item in (replies or []) if isinstance(item, dict) and node in item), None)
                            if not isinstance(result, dict) or 'ok' not in result or 'error' in result:
                                error = result.get('error', '未收到节点确认') if isinstance(result, dict) else '未收到节点确认'
                                feedback_messages.append(f"{label}节点 {node} 调整未确认 ({error})，请稍后重新提交以重试；")
                                pending_nodes.append({
                                    "queue": key,
                                    "label": label,
                                    "node": node,
                                    "target": desired,
                                    "runtime": before,
                                    "reason": "unconfirmed",
                                })
                                continue
                        except Exception as e:
                            feedback_messages.append(f"{label}节点 {node} 热扩缩容执行异常 ({e})，请稍后重新提交以重试；")
                            pending_nodes.append({
                                "queue": key,
                                "label": label,
                                "node": node,
                                "target": desired,
                                "runtime": before,
                                "reason": "rpc_error",
                            })
                            continue
                        # 池伸缩是异步补齐，命令返回后进程数不会立即变化，需等待收敛再判定。
                        after, reached = _wait_pool_size(inspector, node, desired)
                        if reached:
                            feedback_messages.append(f"{label}节点 {node} 已{action}至 {after} 个并发进程；")
                        elif after is None:
                            feedback_messages.append(f"{label}节点 {node} 已接收{action}指令，但未回读运行进程数，请稍后重新提交以核实；")
                            pending_nodes.append({
                                "queue": key,
                                "label": label,
                                "node": node,
                                "target": desired,
                                "runtime": None,
                                "reason": "unverified",
                            })
                        else:
                            # 命令被接收但进程数未达目标（如进程仍被任务占用导致缩容暂缓）。
                            feedback_messages.append(
                                f"{label}节点 {node} 已接收{action}指令，运行进程数仍为 {after}，"
                                f"请稍后重新提交以重试（任务空闲后调度器也将自动对齐）；"
                            )
                            pending_nodes.append({
                                "queue": key,
                                "label": label,
                                "node": node,
                                "target": desired,
                                "runtime": after,
                                "reason": "busy_deferred" if diff < 0 else "pending_settle",
                            })
            else:
                feedback_messages.append("Celery 服务未响应，请稍后重新提交以重试；配置也将在重启时生效。")
                pending_nodes.append({
                    "queue": "all",
                    "label": "Celery",
                    "node": None,
                    "target": None,
                    "runtime": None,
                    "reason": "celery_unresponsive",
                })
        except Exception as e:
            feedback_messages.append(f"热扩缩容通信异常 ({e})，请稍后重新提交以重试或重启容器。")
            pending_nodes.append({
                "queue": "all",
                "label": "Celery",
                "node": None,
                "target": None,
                "runtime": None,
                "reason": "rpc_exception",
            })

        if diff_osint != 0:
            feedback_messages.append("OSINT 任务并发将在 10 秒内由后台看门狗自动更新。")

        return {
            "code": 200,
            "message": " ".join(feedback_messages),
            "pending_convergence": len(pending_nodes) > 0,
            "pending_nodes": pending_nodes,
            "data": {
                "pending_convergence": len(pending_nodes) > 0,
                "pending_nodes": pending_nodes,
                "celery_heavy_concurrency": new_heavy,
                "celery_light_concurrency": new_light,
                "osint_concurrency": new_osint,
                "github_concurrency": new_github if new_github is not None else old_config.get("github_concurrency", 1),
            }
        }


@ns.route('/merged_general')
class MergedGeneralConfig(ARLResource):
    """
    获取用于前端"已生效值"对比的合并视图。

    /general 返回的是按后端 config 键名组织、且已应用数据库覆盖后的生效值，
    但它既包含只读的基础设施字段，也包含不能回显给前端的凭据（API Key、
    各类 Token / 密码）。本接口只暴露可编辑且非敏感的字段，供前端回显
    "当前系统实际生效值"，让用户能分辨空输入框是"未配置"还是"已配置"。
    """
    @auth
    def get(self):
        from app.config import Config

        return {
            "code": 200,
            "message": "success",
            "data": {
                "fofa_url": Config.FOFA_URL,
                "fofa_max_page": Config.FOFA_MAX_PAGE,
                "fofa_page_size": Config.FOFA_PAGE_SIZE,
                "proxy_url": Config.PROXY_URL,
                "port_top_10": Config.TOP_10,
                "domain_brute_concurrent": Config.DOMAIN_BRUTE_CONCURRENT,
                "alt_dns_concurrent": Config.ALT_DNS_CONCURRENT,
                "auth": Config.AUTH,
                "push_options": Config.PUSH_OPTIONS,
                "query_plugin_config": Config.QUERY_PLUGIN_CONFIG,
                # 仅回显"是否已配置"的布尔值，绝不返回凭据明文或掩码片段
                "credentials": _credential_presence(),
                "security_policy_source": _security_policy_source(),
            }
        }


from app.services.system_config_service import (
    _credential_presence,
    _security_policy_source,
    dispatch_test_push,
    _UPDATE_CACHE,
    get_local_version_str,
    get_local_changelog_section,
    is_version_greater,
    check_system_update_info,
)


@ns.route('/capacity_probe')
class CapacityProbe(ARLResource):
    """
    返回可用内存预算与各并发项的推荐值。

    原本用户需要自己完成"读说明得知单 Worker 内存上限 → 查机器内存 → 扣除常驻
    占用 → 心算进程数"四步推导。此接口把该推导前置到后端。

    推荐值须同时满足两个约束，缺一都会给出危险建议：

    【约束 A · 稳态】以 MemAvailable 为基准。它已扣除内核、常驻容器与可回收
    缓存，是"不触发换页还能分配多少"的直接度量。早期实现按 (总内存 - 固定预留)
    估算，在小内存多容器部署上会显著高估——实测 MongoDB(≈1G) + Web(≈0.7G) +
    Puppeteer(≈0.26G) 等常驻合计可达 2G 以上，固定预留 1G 远远不够。

    【约束 B · 峰值】更关键的一条：各队列的 --max-memory-per-child 是**熔断上限**
    而非典型占用，多个队列可能同时逼近各自上限。故预算必须按
    Σ(队列并发 × 该队列单进程上限) 校验最坏情形，否则"稳态看起来够用、
    峰值必然 OOM"（本项目 2 核 3.8G 机器上实测 1/1 稳定、2/2 必 OOM 即此原因）。

    注意三个队列的上限并不相同（heavy 488MB / light 292MB / github 292MB），
    按同一个数值估算会同时错在两个方向。
    """
    @auth
    def get(self):
        mem = _read_memory_report()
        total_mem_mb = mem.get("total_memory_mb")
        available_mb = mem.get("available_memory_mb")

        heavy_recommended = None
        light_recommended = None
        github_recommended = None
        osint_recommended = 1
        basis = "未能读取内存信息，请以实际运行情况为准"
        headroom_mb = None
        steady_ok = None
        peak_used_mb = None

        if total_mem_mb and available_mb is not None:
            # 预算 = 可用内存 - 突发余量。余量取 15% 或 256MB 的较大者，
            # 避免把预算顶满后任何一次内存抖动都触发 OOM Killer。
            reserve_mb = max(256, int(available_mb * 0.15))
            headroom_mb = max(0, available_mb - reserve_mb)

            # 按峰值模型分配：三个队列共享同一份预算，且各自单进程上限不同。
            # 权重反映典型负载下愿意分给该队列的比例（重任务最重，故占比最高）。
            alloc = _allocate_concurrency(headroom_mb)
            heavy_recommended = alloc["heavy"]
            light_recommended = alloc["light"]
            github_recommended = alloc["github"]
            peak_used_mb = alloc["peak_used_mb"]
            steady_ok = alloc["steady_ok"]

            caps = QUEUE_MEMORY_CAPS_MB
            basis = (
                f"可用内存 {available_mb}MB - 突发余量 {reserve_mb}MB = 预算 {headroom_mb}MB。"
                f"按峰值模型分配（各队列单进程上限：重 {caps['heavy']}MB / "
                f"轻 {caps['light']}MB / GitHub {caps['github']}MB），"
                f"推荐 重{heavy_recommended} 轻{light_recommended} GitHub{github_recommended}，"
                f"最坏情形峰值合计 {peak_used_mb}MB"
                + ("" if steady_ok else "，已超出预算，故收敛至最小可用值")
            )

        return {
            "code": 200,
            "message": "success",
            "data": {
                "total_memory_mb": total_mem_mb,
                "available_memory_mb": available_mb,
                "headroom_mb": headroom_mb,
                "heavy_recommended": heavy_recommended,
                "light_recommended": light_recommended,
                "github_recommended": github_recommended,
                # OSINT 受外网反爬约束，与内存无关，恒为 1
                "osint_recommended": osint_recommended,
                "per_worker_memory_mb": QUEUE_MEMORY_CAPS_MB["heavy"],
                "queue_memory_caps_mb": dict(QUEUE_MEMORY_CAPS_MB),
                "peak_used_mb": peak_used_mb,
                # 预算不足以支撑"各队列各 1 进程"的最小配置时为 False，
                # 前端据此提示用户扩容而非假装推荐值安全
                "steady_ok": steady_ok,
                "basis": basis,
            }
        }


# 各队列单进程内存上限（MB），取自 start_worker_prod.sh 的 --max-memory-per-child。
# 该值是 celery 的**熔断上限**而非典型占用：进程逼近上限时会被回收，
# 但多个队列可能同时逼近各自上限，故按峰值叠加校验预算。
# 调整启动脚本中的 --max-memory-per-child 时必须同步此处，否则推荐值失真。
QUEUE_MEMORY_CAPS_MB = {
    "heavy": 500000 // 1024,   # arltask,arltask_heavy
    "light": 300000 // 1024,   # arltask_light
    "github": 300000 // 1024,  # arlgithub
}

# 预算在三个队列间的分配权重。重任务单任务耗时最长、进程上限最高，
# 给最多份额；轻任务走独立通道但单点请求为主；GitHub 队列任务量通常最小。
_QUEUE_WEIGHTS = {"heavy": 0.5, "light": 0.3, "github": 0.2}

# 各队列并发的硬上限，与 CONCURRENCY_BOUNDS 保持一致
_QUEUE_MAX = {"heavy": 128, "light": 256, "github": 64}


def _allocate_concurrency(headroom_mb):
    """在给定内存预算下按峰值模型分配各队列并发数。

    返回 {"heavy", "light", "github", "peak_used_mb", "steady_ok"}。

    算法：先按权重算出各队列的预算份额，各自除以本队列单进程上限得到候选并发；
    再校验 Σ(并发 × 上限) 是否落在 headroom 内——权重分配在数学上已保证这一点，
    此校验用于防御权重或上限被改动后引入的不一致，并在超预算时按队列优先级
    依次收敛（先削 GitHub，再削轻任务，最后削重任务），保证重任务优先。

    每个队列至少保留 1：全部置 0 等同于停用能力，不应由"内存紧张"自动触发，
    该决策须由用户显式做出。
    """
    caps = QUEUE_MEMORY_CAPS_MB
    # 只装并发数，不含派生的统计字段，避免峰值计算把统计值也当作队列
    alloc = {}
    for q, weight in _QUEUE_WEIGHTS.items():
        budget = int(headroom_mb * weight)
        alloc[q] = max(1, min(_QUEUE_MAX[q], budget // caps[q]))

    def peak_of(a):
        return sum(a[q] * caps[q] for q in _QUEUE_WEIGHTS)

    # 收敛顺序：先牺牲权重最低的队列，保证重任务优先级
    for q in ("github", "light", "heavy"):
        while peak_of(alloc) > headroom_mb and alloc[q] > 1:
            alloc[q] -= 1

    return {
        **alloc,
        "peak_used_mb": peak_of(alloc),
        # 预算低于最小可行峰值（三队列各 1）时必然超出，需如实上报，
        # 由前端提示用户"当前内存不足以支撑最小配置"，而非假装推荐值安全。
        "steady_ok": peak_of(alloc) <= headroom_mb,
    }


def _read_memory_report():
    """读取内存报告（MB）。

    返回 {"total_memory_mb", "available_memory_mb"}，任一字段读不到即为 None，
    由调用方降级为不展示推荐值。

    优先使用 MemAvailable：它是内核给出的"无需换页即可分配"的估算，
    已计入可回收缓存与 slab，比 MemFree 更贴近真实可分配量（MemFree 会把
    大量 buff/cache 误判为不可用，导致保守到不可用）。
    """
    report = {"total_memory_mb": None, "available_memory_mb": None}

    total_kb = None
    available_kb = None
    try:
        with open('/proc/meminfo', 'r', encoding='utf-8') as f:
            for line in f:
                if line.startswith('MemTotal:'):
                    total_kb = int(line.split()[1])
                elif line.startswith('MemAvailable:'):
                    available_kb = int(line.split()[1])
                if total_kb is not None and available_kb is not None:
                    break
    except Exception:
        pass

    # 容器可能被设置了内存限额：此时容器视角的 MemTotal 是宿主机值，
    # 需要与 cgroup 限额取小，避免按宿主机整机内存推荐而撑爆容器限额。
    limit_mb = None
    for path in ('/sys/fs/cgroup/memory.max',
                 '/sys/fs/cgroup/memory/memory.limit_in_bytes'):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                raw = f.read().strip()
            if raw and raw != 'max':
                val = int(raw)
                # 未设限额时 cgroup 给出极大值，视为无效
                if 0 < val < (1 << 62):
                    limit_mb = val // (1024 * 1024)
                    break
        except Exception:
            continue

    if total_kb is not None:
        total_mb = total_kb // 1024
        if limit_mb:
            total_mb = min(total_mb, limit_mb)
        report["total_memory_mb"] = total_mb

    if available_kb is not None:
        available_mb = available_kb // 1024
        if limit_mb:
            available_mb = min(available_mb, limit_mb)
        report["available_memory_mb"] = available_mb
    elif limit_mb:
        # 读不到 MemAvailable 但有限额时，退化为按限额估算
        report["available_memory_mb"] = limit_mb

    return report


@ns.route('/general')
class GeneralConfig(ARLResource):
    @auth
    def get(self):
        """
        获取常规全局配置 (混合数据库与yaml默认配置)
        """
        from app.config import Config

        data = {
            "celery_broker_url": Config.CELERY_BROKER_URL,
            "mongo_url": Config.MONGO_URL,
            "mongo_db": Config.MONGO_DB,
            "geoip_city": Config.GEOIP_CITY,
            "geoip_asn": Config.GEOIP_ASN,
            "geoip_ip2region": getattr(Config, "GEOIP_IP2REGION", ""),

            "fofa_key": Config.FOFA_KEY,
            "fofa_url": Config.FOFA_URL,
            "fofa_max_page": Config.FOFA_MAX_PAGE,
            "fofa_page_size": Config.FOFA_PAGE_SIZE,
            "so_search_cookie": Config.SO_SEARCH_COOKIE,
            "bing_search_cookie": Config.BING_SEARCH_COOKIE,
            "github_token": Config.GITHUB_TOKEN,

            "tyc_id": Config.TYC_ID,
            "tyc_token": Config.TYC_TOKEN,

            "proxy_url": Config.PROXY_URL,
            "port_top_10": Config.TOP_10,
            "domain_brute_concurrent": Config.DOMAIN_BRUTE_CONCURRENT,
            "alt_dns_concurrent": Config.ALT_DNS_CONCURRENT,

            "file_leak_dict": Config.FILE_LEAK_TOP_2k,
            "domain_dict": Config.DOMAIN_DICT_2W,

            "auth": Config.AUTH,
            "api_key": Config.API_KEY,

            "webhook_url": Config.WEB_HOOK_URL,
            "webhook_token": Config.WEB_HOOK_TOKEN,

            "dingding": {
                "secret": Config.DINGDING_SECRET,
                "access_token": Config.DINGDING_ACCESS_TOKEN
            },
            "feishu": {
                "webhook_url": Config.FEISHU_WEBHOOK,
                "secret": Config.FEISHU_SECRET
            },
            "wxwork": {
                "webhook_url": Config.WX_WORK_WEBHOOK
            },
            "telegram": {
                "bot_token": Config.TG_BOT_TOKEN,
                "chat_id": Config.TG_CHAT_ID
            },
            "email": {
                "host": Config.EMAIL_HOST,
                "port": Config.EMAIL_PORT,
                "username": Config.EMAIL_USERNAME,
                "password": Config.EMAIL_PASSWORD,
                "to": Config.EMAIL_TO
            },
            "query_plugin_config": Config.QUERY_PLUGIN_CONFIG,
            "push_options": Config.PUSH_OPTIONS
        }

        return {
            "code": 200,
            "message": "success",
            "data": data
        }

    @auth
    def post(self):
        """
        保存常规全局配置（支持部分字段提交）

        前端按 Tab 分组维护脏字段，仅提交发生变更的字段，避免"在 A 页改完未保存、
        切到 B 页点保存"时用 B 页的旧值覆盖 A 页的修改。未出现在请求体中的字段
        保持数据库原值不变。
        """
        from flask import request
        from app.utils.conn import conn_db
        from app.config import clear_system_config_cache, bump_system_config_version

        req_data = request.json
        if not req_data:
            return {"code": 400, "message": "请求体为空"}

        doc = {}
        # 外部API
        if "fofa_key" in req_data: doc["fofa_key"] = req_data["fofa_key"]
        if "fofa_url" in req_data: doc["fofa_url"] = req_data["fofa_url"]
        if "fofa_max_page" in req_data and req_data["fofa_max_page"] is not None: doc["fofa_max_page"] = int(req_data["fofa_max_page"] or 0)
        if "fofa_page_size" in req_data and req_data["fofa_page_size"] is not None: doc["fofa_page_size"] = int(req_data["fofa_page_size"] or 0)
        
        if "so_search_cookie" in req_data: doc["so_search_cookie"] = req_data["so_search_cookie"]
        if "bing_search_cookie" in req_data: doc["bing_search_cookie"] = req_data["bing_search_cookie"]
        if "github_token" in req_data: doc["github_token"] = req_data["github_token"]

        if "tyc_id" in req_data: doc["tyc_id"] = req_data["tyc_id"]
        if "tyc_token" in req_data: doc["tyc_token"] = req_data["tyc_token"]

        # 代理与并发
        if "proxy_url" in req_data: doc["proxy_url"] = req_data["proxy_url"]
        if "port_top_10" in req_data: doc["port_top_10"] = req_data["port_top_10"]
        if "domain_brute_concurrent" in req_data and req_data["domain_brute_concurrent"] is not None: doc["domain_brute_concurrent"] = int(req_data["domain_brute_concurrent"] or 0)
        if "alt_dns_concurrent" in req_data and req_data["alt_dns_concurrent"] is not None: doc["alt_dns_concurrent"] = int(req_data["alt_dns_concurrent"] or 0)

        # 字典
        if "file_leak_dict" in req_data: doc["file_leak_dict"] = req_data["file_leak_dict"]
        if "domain_dict" in req_data: doc["domain_dict"] = req_data["domain_dict"]

        # 认证
        if "auth" in req_data: doc["auth"] = bool(req_data["auth"])
        if "api_key" in req_data: doc["api_key"] = req_data["api_key"]

        # Webhook
        if "webhook_url" in req_data: doc["webhook_url"] = req_data["webhook_url"]
        if "webhook_token" in req_data: doc["webhook_token"] = req_data["webhook_token"]

        # 消息推送
        if "dingding" in req_data:
            doc["dingding_secret"] = req_data["dingding"].get("secret")
            doc["dingding_access_token"] = req_data["dingding"].get("access_token")
        if "feishu" in req_data:
            doc["feishu_webhook"] = req_data["feishu"].get("webhook_url")
            doc["feishu_secret"] = req_data["feishu"].get("secret")
        if "wxwork" in req_data:
            doc["wx_work_webhook"] = req_data["wxwork"].get("webhook_url")
        if "telegram" in req_data:
            doc["tg_bot_token"] = req_data["telegram"].get("bot_token")
            doc["tg_chat_id"] = req_data["telegram"].get("chat_id")
        if "email" in req_data:
            doc["email_host"] = req_data["email"].get("host")
            doc["email_port"] = req_data["email"].get("port")
            doc["email_username"] = req_data["email"].get("username")
            doc["email_password"] = req_data["email"].get("password")
            doc["email_to"] = req_data["email"].get("to")
        if "query_plugin_config" in req_data: doc["query_plugin_config"] = req_data["query_plugin_config"]
        if "push_options" in req_data: doc["push_options"] = req_data["push_options"]

        # 空提交直接短路：既避免无意义的 upsert，也让前端"无改动点保存"有明确反馈。
        if not doc:
            return {
                "code": 200,
                "message": "未检测到变更字段，配置未改动"
            }

        conn_db('system_config').update_one(
            {"_id": "general_config"},
            {"$set": doc},
            upsert=True
        )

        # 清除本进程缓存，并递增跨进程版本号让其他 gunicorn worker 的缓存同步作废，
        # 否则用户保存后立即刷新可能仍看到旧值（多 worker 各自持有进程内缓存）。
        clear_system_config_cache()
        bump_system_config_version()

        return {
            "code": 200,
            "message": "全局配置更新成功",
            "data": {"updated_keys": sorted(doc.keys())}
        }

@ns.route('/test_push')
class TestPush(ARLResource):
    @auth
    def post(self):
        """
        测试消息推送配置
        """
        from flask import request
        req_data = request.json
        if not req_data:
            return {"code": 400, "message": "请求体为空"}

        push_type = req_data.get("push_type")
        config = req_data.get("config", {})
        return dispatch_test_push(push_type, config)


from flask import request as flask_req


@ns.route('/local_version')
class LocalVersion(ARLResource):
    @auth
    def get(self):
        """
        获取当前本地版本号（通过读取版本文件）
        """
        version = get_local_version_str()
        return {"code": 200, "message": "success", "data": {"version": version}}


@ns.route('/check_update')
class CheckUpdate(ARLResource):
    @auth
    def get(self):
        """
        检查系统版本更新与获取更新日志（带内存缓存与本地回退）
        """
        force_refresh = flask_req.args.get('refresh', '').lower() in ('1', 'true')
        result_data = check_system_update_info(force_refresh=force_refresh)
        return {"code": 200, "message": "success", "data": result_data}

@ns.route('/request_update_token')
class RequestUpdateToken(ARLResource):
    @auth
    def post(self):
        """
        请求一个用于进行系统更新的一次性 Token
        """
        from app.utils.updater_token import issue_updater_token
        purpose = (flask_req.get_json(silent=True) or {}).get('purpose', 'control')
        try:
            token = issue_updater_token(purpose)
            return {"code": 200, "message": "Token 生成成功", "data": {"token": token}}
        except ValueError as exc:
            return {'code': 400, 'message': str(exc)}, 400
        except Exception as e:
            return {"code": 500, "message": f"生成更新 Token 失败: {str(e)}"}


@ns.route('/running_task_count')
class RunningTaskCount(ARLResource):
    @auth
    def get(self):
        """
        获取当前系统中正在执行的扫描任务数量（用于更新前置预检与任务告警）
        """
        from app.modules import TaskStatus
        from app.utils import conn_db
        non_running = [TaskStatus.DONE, TaskStatus.WAITING, TaskStatus.ERROR, TaskStatus.STOP]
        count = conn_db('task').count_documents({"status": {"$nin": non_running}})
        return {"code": 200, "message": "success", "data": {"running_count": count}}



