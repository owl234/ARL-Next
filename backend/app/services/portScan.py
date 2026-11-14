import ipaddress
import re
from app import utils
from app.utils import nmap, is_valid_exclude_ports
from app.utils.packet_lease import acquire_packet_slot
from app.config import Config
from app.modules import get_alive_ports

logger = utils.get_logger()

VALID_HOST_DISCOVERY_MODES = ("auto", "skip", "probe")


def normalize_host_discovery_mode(mode, strict=False):
    """Normalize host discovery mode to 'auto', 'skip', or 'probe'."""
    if mode is None:
        return "auto"
    if not isinstance(mode, str):
        if strict:
            raise ValueError("host_discovery_mode must be one of: auto, skip, probe")
        return "auto"
    normalized = mode.strip().lower()
    if not normalized:
        return "auto"
    if normalized in VALID_HOST_DISCOVERY_MODES:
        return normalized
    if strict:
        raise ValueError("host_discovery_mode must be one of: auto, skip, probe")
    return "auto"


def _parse_single_port_token(token):
    """Parse a port token ('80' or '8000-8010') into an inclusive (start, end) tuple."""
    if not token:
        return None
    cleaned = token.strip()
    if ":" in cleaned and cleaned.split(":", 1)[0].upper() in ("T", "U", "S"):
        cleaned = cleaned.split(":", 1)[1].strip()
    if "-" in cleaned:
        parts = cleaned.split("-", 1)
        try:
            start = int(parts[0].strip())
            end = int(parts[1].strip())
        except ValueError:
            return None
        if start > end:
            start, end = end, start
    else:
        try:
            start = end = int(cleaned)
        except ValueError:
            return None
    if end < 0 or start > 65535:
        return None
    return (max(0, start), min(65535, end))


def _parse_port_intervals(ports_str):
    """Parse comma-separated ports/ranges into sorted, merged (start, end) intervals."""
    if not ports_str:
        return []
    if isinstance(ports_str, (list, tuple, set)):
        raw = ",".join(str(x) for x in ports_str)
    else:
        raw = str(ports_str)
    intervals = []
    for token in raw.split(","):
        parsed = _parse_single_port_token(token)
        if parsed is not None:
            intervals.append(parsed)
    if not intervals:
        return []
    intervals.sort()
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        prev_start, prev_end = merged[-1]
        if start <= prev_end + 1:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))
    return merged


def _count_expanded_ports(ports_str):
    """Count total unique TCP ports after expanding comma-separated ranges."""
    return sum(end - start + 1 for start, end in _parse_port_intervals(ports_str))


def _subtract_intervals(base_interval, exclude_intervals):
    """Subtract sorted exclude intervals from a single (start, end) interval."""
    cur, b_end = base_interval
    remaining = []
    for e_start, e_end in exclude_intervals:
        if e_end < cur:
            continue
        if e_start > b_end:
            break
        if e_start > cur:
            remaining.append((cur, e_start - 1))
        cur = max(cur, e_end + 1)
        if cur > b_end:
            break
    if cur <= b_end:
        remaining.append((cur, b_end))
    return remaining


def _subtract_excluded_ports(alive_ports_str, exclude_ports_str):
    """Remove excluded ports from alive_ports_str, preserving untouched token formatting."""
    if not alive_ports_str or not exclude_ports_str:
        return alive_ports_str
    exclude_intervals = _parse_port_intervals(exclude_ports_str)
    if not exclude_intervals:
        return alive_ports_str
    result_tokens = []
    for raw_token in str(alive_ports_str).split(","):
        token = raw_token.strip()
        if not token:
            continue
        parsed = _parse_single_port_token(token)
        if parsed is None:
            result_tokens.append(token)
            continue
        remaining = _subtract_intervals(parsed, exclude_intervals)
        if len(remaining) == 1 and remaining[0] == parsed:
            result_tokens.append(token)
        else:
            for start, end in remaining:
                result_tokens.append(str(start) if start == end else "{}-{}".format(start, end))
    return ",".join(result_tokens)


def _count_single_target_ips(token):
    """Estimate expanded IP count for one target token (IP, CIDR, IPv4 range, or host)."""
    if not token:
        return 0
    try:
        ipaddress.ip_address(token)
        return 1
    except ValueError:
        pass
    if "/" in token:
        try:
            return ipaddress.ip_network(token, strict=False).num_addresses
        except ValueError:
            pass
    short_range = re.fullmatch(r"(\d+\.\d+\.\d+\.)(\d+)-(\d+)", token)
    if short_range:
        prefix, start_s, end_s = short_range.groups()
        try:
            ipaddress.IPv4Address(prefix + start_s)
            end_octet = int(end_s)
            start_octet = int(start_s)
            if 0 <= end_octet <= 255 and end_octet >= start_octet:
                return end_octet - start_octet + 1
        except ValueError:
            pass
    if "-" in token:
        left, right = token.split("-", 1)
        try:
            start_ip = ipaddress.IPv4Address(left.strip())
            end_ip = ipaddress.IPv4Address(right.strip())
            if int(end_ip) >= int(start_ip):
                return int(end_ip) - int(start_ip) + 1
        except ValueError:
            pass
    return 1


def _count_target_ips(targets):
    """Count total expanded target IPs across a list or whitespace-separated target string."""
    if not targets:
        return 0
    if isinstance(targets, str):
        raw_items = [targets]
    else:
        raw_items = targets
    tokens = []
    for item in raw_items:
        if not item:
            continue
        for token in str(item).split():
            if token:
                tokens.append(token)
    unique_tokens = list(dict.fromkeys(tokens))
    return sum(_count_single_target_ips(token) for token in unique_tokens)


class PortScan:
    """
    [第一性原理：底层武器库 - 端口扫描及指纹识别]
    这是整个 ARL 系统的核心资产发现引擎。它底层是对 python-nmap 的深度二次封装。
    端口扫描的第一性原理难点不在于“如何发包”，而在于“如何在速度与准确性之间走钢丝”，
    以及“如何对抗各种奇葩的网络环境（比如防火墙丢包、CDN、全端口蜜罐）”。
    这个类中充满了无数实战中总结出的经验参数（如超时控制、并发度、探活策略）。
    """
    def __init__(self, targets, ports=None, service_detect=False, os_detect=False,
                 port_parallelism=None, port_min_rate=None, custom_host_timeout=None,
                 exclude_ports=None, alive_port=None, host_discovery_mode="auto",
                 ):
        self.targets = " ".join(targets)
        self.ports = ports
        self.host_discovery_mode = normalize_host_discovery_mode(host_discovery_mode)
        self.target_ip_count = _count_target_ips(targets)
        self.expanded_port_count = _count_expanded_ports(self.ports)
        self.max_host_group = 32 # Nmap 每次并行扫描的 IP 组大小
        # 存活探测端口集：如果不用 ICMP (ping)，就靠探测这些高频端口来判断主机是否存活
        if alive_port:
            if isinstance(alive_port, list):
                self.alive_port = ",".join(str(p) for p in alive_port)
            else:
                self.alive_port = str(alive_port).strip()
        else:
            self.alive_port = get_alive_ports()
        # -sT: TCP 连接扫描 (不需要 root 权限，且更准)
        # -n: 不做反向 DNS 解析 (极大提升速度)
        # --open: 只输出 open 状态的端口
        self.nmap_arguments = "-sT -n --open"
        self.max_retries = 3
        self.host_timeout = 60*5
        # 🛡️ 第一性原理：类型安全与数值边界保底，彻底杜绝 None 或非法值注入导致的 Nmap 崩溃
        try:
            self.parallelism = int(port_parallelism) if port_parallelism is not None else 32
            if not (1 <= self.parallelism <= 1000):
                self.parallelism = 32
        except (ValueError, TypeError):
            self.parallelism = 32

        try:
            self.min_rate = int(port_min_rate) if port_min_rate is not None else 64
            if not (1 <= self.min_rate <= 10000):
                self.min_rate = 64
        except (ValueError, TypeError):
            self.min_rate = 64

        self.exclude_ports = exclude_ports

        # [动态参数调优策略]
        # 依据用户是否开启了 服务识别 (-sV) 或 OS识别 (-O)，动态增加超时时间。
        if service_detect:
            self.host_timeout += 60 * 5
            self.nmap_arguments += " -sV"

        if os_detect:
            self.host_timeout += 60 * 4
            self.nmap_arguments += " -O"

        # 【第一性原理：基于 IP 规模 × 展开端口数的二维探活决策】
        # 1. host_discovery_mode == "skip": 强制 -Pn
        # 2. host_discovery_mode == "probe": 强制 -PE -PS<alive_port>
        # 3. host_discovery_mode == "auto" (默认):
        #    - 端口数 <= 60 (且非全端口): 始终 -Pn
        #    - 端口数 61~2000 (覆盖 Top100/Top1000): IP <= 16 用 -Pn，IP > 16 用 -PE -PS
        #    - 端口数 > 2000 或全端口 (1-65535): IP <= 2 用 -Pn，IP > 2 用 -PE -PS
        is_all_ports = (isinstance(self.ports, str) and self.ports.strip() == "1-65535") or self.expanded_port_count >= 65535
        if self.host_discovery_mode == "skip":
            use_host_discovery = False
        elif self.host_discovery_mode == "probe":
            use_host_discovery = True
        elif is_all_ports or self.expanded_port_count > 2000:
            use_host_discovery = self.target_ip_count > 2
        elif self.expanded_port_count > 60:
            use_host_discovery = self.target_ip_count > 16
        else:
            use_host_discovery = False

        self.effective_alive_port = self.alive_port
        if use_host_discovery:
            if self.exclude_ports:
                self.effective_alive_port = _subtract_excluded_ports(
                    self.alive_port, self.exclude_ports
                )
            if self.effective_alive_port:
                self.discovery_strategy = "-PE -PS"
                self.nmap_arguments += " -PE -PS{}".format(self.effective_alive_port)
            else:
                self.discovery_strategy = "-PE"
                self.nmap_arguments += " -PE"
        else:
            self.discovery_strategy = "-Pn"
            self.nmap_arguments += " -Pn"

        if self.expanded_port_count > 60 or is_all_ports:
            self.max_retries = 2

        # 全端口(1-65535)扫描是极度危险且耗时的操作，必须采用极端的调优参数
        if is_all_ports:
            self.max_host_group = 2             # 减小并发组，防止把路由器连接数打满
            self.min_rate = max(self.min_rate, 800) # 强制提高发包下限速率
            self.parallelism = max(self.parallelism, 128)
            self.host_timeout += 60 * 5
            self.max_retries = 2

        # 极限性能微调参数
        self.nmap_arguments += " --max-rtt-timeout 800ms" # 如果包 800ms 还没回，就不等了
        self.nmap_arguments += " --min-rate {}".format(self.min_rate)
        self.nmap_arguments += " --script-timeout 6s"     # 单个脚本超时
        self.nmap_arguments += " --max-hostgroup {}".format(self.max_host_group)

        # 依据传过来的超时为准
        if custom_host_timeout is not None:
            try:
                timeout_val = int(custom_host_timeout)
                if 1 <= timeout_val <= 86400:
                    self.host_timeout = timeout_val
            except (ValueError, TypeError):
                pass
        self.nmap_arguments += " --host-timeout {}s".format(self.host_timeout)
        self.nmap_arguments += " --min-parallelism {}".format(self.parallelism)
        self.nmap_arguments += " --max-retries {}".format(self.max_retries)

        if self.exclude_ports is not None:
            if self.exclude_ports != "" and\
                    is_valid_exclude_ports(self.exclude_ports):
                self.nmap_arguments += " --exclude-ports {}".format(self.exclude_ports)

    def run(self):
        if not self.targets or not self.targets.strip():
            return []
        logger.info(
            "nmap target {}  ports {}  ips={} expanded_ports={} discovery_mode={} strategy={}  arguments {}".format(
                self.targets[:20],
                (self.ports or "")[:20],
                self.target_ip_count,
                self.expanded_port_count,
                self.host_discovery_mode,
                self.discovery_strategy,
                self.nmap_arguments,
            )
        )
        nm = nmap.PortScanner()
        # [执行扫描] 申请重发包租约槽位并阻塞执行，避免多任务高并发扫端口打爆主机状态表
        with acquire_packet_slot(phase="port_scan"):
            nm.scan(hosts=self.targets, ports=self.ports, arguments=self.nmap_arguments)
        
        ip_info_list = []
        for host in nm.all_hosts():
            port_info_list = []
            for proto in nm[host].all_protocols():
                port_len = len(nm[host][proto])

                for port in nm[host][proto]:
                    # 【第一性原理：全端口蜜罐对抗 (Honeypot Mitigation)】
                    # 黑客防御界有一种东西叫“全端口蜜罐”（你扫它任何端口都是 open 的，目的是拖死你的扫描器或投毒）。
                    # 这里的逻辑极其粗暴但有效：如果发现这个 IP 竟然开放了 >600 个端口，
                    # 并且当前处理的端口不是 80 或 443（Web刚需端口），直接抛弃！
                    if port_len > 600 and (port not in [80, 443]):
                        continue

                    port_info = nm[host][proto][port]
                    item = {
                        "port_id": port,
                        "service_name": port_info["name"],
                        "version": port_info["version"],
                        "product": port_info["product"],
                        "protocol": proto
                    }

                    port_info_list.append(item)

            osmatch_list = nm[host].get("osmatch", [])
            os_info = self.os_match_by_accuracy(osmatch_list)

            ip_info = {
                "ip": host,
                "port_info": port_info_list,
                "os_info": os_info
            }
            ip_info_list.append(ip_info)

        return ip_info_list

    def os_match_by_accuracy(self, os_match_list):
        """
        [数据清洗] 
        Nmap 的操作系统探测会返回很多个可能的选项（附带准确率）。
        我们只取准确率 (accuracy) > 90% 的结果，宁缺毋滥。
        """
        for os_match in os_match_list:
            accuracy = os_match.get('accuracy', '0')
            if int(accuracy) > 90:
                return os_match

        return {}


def port_scan(targets, ports=None, service_detect=False, os_detect=False,
              port_parallelism=32, port_min_rate=64, custom_host_timeout=None, exclude_ports=None,
              alive_port=None, host_discovery_mode="auto"):
    """
    [高级封装层]
    供外部 Celery Task 调用的入口函数。
    会在调用底层 Nmap 前，做一次极速去重和黑名单过滤。
    """
    if ports is None:
        ports = Config.TOP_10
    targets = list(set(targets)) # IP 去重
    targets = list(filter(utils.not_in_black_ips, targets)) # 过滤内部网段或黑名单
    ps = PortScan(targets=targets, ports=ports, service_detect=service_detect, os_detect=os_detect,
                  port_parallelism=port_parallelism, port_min_rate=port_min_rate,
                  custom_host_timeout=custom_host_timeout,
                  exclude_ports=exclude_ports,
                  alive_port=alive_port,
                  host_discovery_mode=host_discovery_mode,
                  )
    return ps.run()