from app import utils
from app.utils import nmap, is_valid_exclude_ports
from app.config import Config

logger = utils.get_logger()


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
                 exclude_ports=None,
                 ):
        self.targets = " ".join(targets)
        self.ports = ports
        self.max_host_group = 32 # Nmap 每次并行扫描的 IP 组大小
        # 存活探测端口集：如果不用 ICMP (ping)，就靠探测这些高频端口来判断主机是否存活
        self.alive_port = "22,80,443,843,3389,8007-8011,8443,9090,8080-8091,8093,8099,5000-5004,2222,3306,1433,21,25"
        # -sT: TCP 连接扫描 (不需要 root 权限，且更准)
        # -n: 不做反向 DNS 解析 (极大提升速度)
        # --open: 只输出 open 状态的端口
        self.nmap_arguments = "-sT -n --open"
        self.max_retries = 3
        self.host_timeout = 60*5
        self.parallelism = port_parallelism  # 默认 32，控制并发探针数
        self.min_rate = port_min_rate  # 默认64，控制发包速率底线
        self.exclude_ports = exclude_ports

        # [动态参数调优策略]
        # 依据用户是否开启了 服务识别 (-sV) 或 OS识别 (-O)，动态增加超时时间。
        if service_detect:
            self.host_timeout += 60 * 5
            self.nmap_arguments += " -sV"

        if os_detect:
            self.host_timeout += 60 * 4
            self.nmap_arguments += " -O"

        # 【第一性原理：防蜜罐与防网络阻塞】
        # 如果要扫描的端口数 > 60个，说明是中大规模扫描，不建议用全端口禁 ping (-Pn)。
        # 改为发特定的 TCP 包 (-PE -PS) 去探活，活的才扫，死的直接跳过。并且减少重试次数 (-max-retries 2)。
        if len(self.ports.split(",")) > 60:
            self.nmap_arguments += " -PE -PS{}".format(self.alive_port)
            self.max_retries = 2
        else:
            # 端口少的话，直接 -Pn (默认所有主机存活，不探活直接扫)，最准。
            if self.ports != "0-65535":
                self.nmap_arguments += " -Pn"

        # 全端口(0-65535)扫描是极度危险且耗时的操作，必须采用极端的调优参数
        if self.ports == "0-65535":
            self.max_host_group = 2             # 减小并发组，防止把路由器连接数打满
            self.min_rate = max(self.min_rate, 800) # 强制提高发包下限速率
            self.parallelism = max(self.parallelism, 128)

            self.nmap_arguments += " -PE -PS{}".format(self.alive_port)
            self.host_timeout += 60 * 5
            self.max_retries = 2

        # 极限性能微调参数
        self.nmap_arguments += " --max-rtt-timeout 800ms" # 如果包 800ms 还没回，就不等了
        self.nmap_arguments += " --min-rate {}".format(self.min_rate)
        self.nmap_arguments += " --script-timeout 6s"     # 单个脚本超时
        self.nmap_arguments += " --max-hostgroup {}".format(self.max_host_group)

        # 依据传过来的超时为准
        if custom_host_timeout is not None:
            if int(custom_host_timeout) > 0:
                self.host_timeout = custom_host_timeout
        self.nmap_arguments += " --host-timeout {}s".format(self.host_timeout)
        self.nmap_arguments += " --min-parallelism {}".format(self.parallelism)
        self.nmap_arguments += " --max-retries {}".format(self.max_retries)

        if self.exclude_ports is not None:
            if self.exclude_ports != "" and\
                    is_valid_exclude_ports(self.exclude_ports):
                self.nmap_arguments += " --exclude-ports {}".format(self.exclude_ports)

    def run(self):
        logger.info("nmap target {}  ports {}  arguments {}".format(
            self.targets[:20], self.ports[:20], self.nmap_arguments))
        nm = nmap.PortScanner()
        # [执行扫描] 这个函数会阻塞，直到所有 IP 扫描完毕
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


def port_scan(targets, ports=Config.TOP_10, service_detect=False, os_detect=False,
              port_parallelism=32, port_min_rate=64, custom_host_timeout=None, exclude_ports=None):
    """
    [高级封装层]
    供外部 Celery Task 调用的入口函数。
    会在调用底层 Nmap 前，做一次极速去重和黑名单过滤。
    """
    targets = list(set(targets)) # IP 去重
    targets = list(filter(utils.not_in_black_ips, targets)) # 过滤内部网段或黑名单
    ps = PortScan(targets=targets, ports=ports, service_detect=service_detect, os_detect=os_detect,
                  port_parallelism=port_parallelism, port_min_rate=port_min_rate,
                  custom_host_timeout=custom_host_timeout,
                  exclude_ports=exclude_ports,
                  )
    return ps.run()