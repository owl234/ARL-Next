from app import utils
from app.config import Config
import os

logger = utils.get_logger()


class MassDNS:
    """
    [第一性原理：底层武器库 - 高频 DNS 探测引擎封装]
    MassDNS 是一款由 C 语言编写的，性能极度狂野的批量 DNS 解析工具。
    在 ARL 中，它是【子域名收集】阶段的头号功臣。
    这个类的第一性原理非常简单：
    1. 将上层准备好的几万/几十万个域名列表，落盘存为临时文本文件 (domain_write)。
    2. 拼装 shell 命令，拉起 massdns 二进制文件去读取文本文件，并发向各大 DNS 根服务器发包 (mass_dns)。
    3. 捕获 massdns 输出的结果文件，使用正则/分割符提取出存活的域名、类型和 IP，并干掉因为泛解析导致的脏数据 (parse_mass_dns_output)。
    """
    def __init__(self, domains=None, mass_dns_bin=None,
                 dns_server=None, tmp_dir=None, wildcard_domain_ip=None, concurrent=0):

        if wildcard_domain_ip is None:  # 泛域名列表
            wildcard_domain_ip = []

        if concurrent == 0:
            concurrent = 100

        self.domains = domains
        self.tmp_dir = tmp_dir
        self.dns_server = dns_server
        
        # 为什么要有这两个随机文件名？
        # 因为 Celery 在分布式运行，同一台机器上可能同时跑着好几个爆破任务。
        # 用随机字符串做临时文件名，避免多进程之间发生文件读写踩踏（Race Condition）。
        self.domain_gen_output_path = os.path.join(tmp_dir,
                                                   "domain_gen_{}".format(utils.random_choices()))
        self.mass_dns_output_path = os.path.join(tmp_dir,
                                                 "mass_dns_{}".format(utils.random_choices()))
        self.mass_dns_bin = mass_dns_bin
        self.wildcard_domain_ip = wildcard_domain_ip
        self.concurrent = concurrent

    def domain_write(self):
        """
        [第一性原理：大数据的磁盘中转]
        不要试图把几十万的字典通过管道传给 C 程序，那会非常吃内存且容易截断。
        最稳妥的办法是写进 /tmp 目录下的临时文件，让工具自己去读文件。
        """
        cnt = 0
        with open(self.domain_gen_output_path, "w") as f:
            for domain in self.domains:
                domain = domain.strip()
                if not domain:
                    continue
                f.write(domain + "\n")
                cnt += 1

        logger.info("MassDNS dict {}".format(cnt))

    def mass_dns(self):
        """
        [第一性原理：进程拉起]
        组装 massdns 执行命令：
        -q: 极简输出模式
        -r: 指定 DNS Resolvers 列表（如 114.114.114.114，8.8.8.8）
        -o S: 输出格式设为简单模式 (domain type record)
        -w: 结果输出文件路径
        -s: 并发度，太高会把局域网路由器打挂，太低扫描慢
        """
        command = [self.mass_dns_bin, "-q",
                   "-r {}".format(self.dns_server),
                   "-o S",
                   "-w {}".format(self.mass_dns_output_path),
                   "-s {}".format(self.concurrent),
                   self.domain_gen_output_path,
                   "--root"
                   ]

        logger.info(" ".join(command))
        # 阻塞调用系统命令，设置极其夸张的超时时间（5天），因为在极限大字典下，爆破可能需要非常久
        utils.exec_system(command, timeout=5*24*60*60)

    def parse_mass_dns_output(self):
        """
        [第一性原理：输出结果清洗与泛解析对抗]
        黑客工具产生的原始数据是脏乱差的，必须经过我们的“安检”才能变成系统的标准数据。
        安检中最核心的逻辑是：过滤泛解析。
        """
        output = []
        with open(self.mass_dns_output_path, "r+", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                data = line.split(" ")
                if len(data) != 3:
                    continue
                domain, _type, record = data
                record = record.strip().strip(".")

                # 【泛解析对抗】：
                # 如果发现解析出来的 IP，存在于事先测好的“黑名单 IP（泛解析IP）”里，
                # 说明这是个假域名（不管你输入什么鬼画符子域名，DNS 都给你指到同一个页面），直接丢弃！
                if record in self.wildcard_domain_ip:
                    continue

                item = {
                    "domain": domain.strip("."),
                    "type": _type,
                    "record": record
                }
                output.append(item)

        # 阅后即焚，防止服务器硬盘被临时文件撑爆
        self._delete_file()
        return output

    def _delete_file(self):
        try:
            os.unlink(self.domain_gen_output_path)
            os.unlink(self.mass_dns_output_path)
        except Exception as e:
            logger.warning(e)

    def run(self):
        """经典的 准备 -> 执行 -> 回收 三段式流水线"""
        self.domain_write()
        self.mass_dns()
        output = self.parse_mass_dns_output()
        return output


def mass_dns(based_domain, words, wildcard_domain_ip=None):
    """
    [高级封装层]
    这是供外部（比如 tasks/domain.py 流水线）调用的直接入口。
    它的任务是：将用户的“主域名”和“字典数组”进行拼装。
    支持传统的前缀拼装 (word.based_domain) 以及更高级的 {fuzz} 占位符拼装。
    """
    if wildcard_domain_ip is None:
        wildcard_domain_ip = []

    domains = []
    is_fuzz_domain = "{fuzz}" in based_domain
    for word in words:
        word = word.strip()
        if word:
            if is_fuzz_domain:
                # 高级模式：比如输入是 api-{fuzz}.test.com
                domains.append(based_domain.replace("{fuzz}", word))
            else:
                # 常规模式：输入是 test.com，字典是 admin，拼装出 admin.test.com
                domains.append("{}.{}".format(word, based_domain))

    if not is_fuzz_domain:
        domains.append(based_domain)

    logger.info("start brute:{} words:{} wildcard_record:{}".format(
        based_domain, len(domains), ",".join(wildcard_domain_ip)))

    # 实例化上面的大杀器并开火
    mass = MassDNS(domains, mass_dns_bin=Config.MASSDNS_BIN,
                   dns_server=Config.DNS_SERVER, tmp_dir=Config.TMP_PATH,
                   wildcard_domain_ip=wildcard_domain_ip, concurrent=Config.DOMAIN_BRUTE_CONCURRENT)

    return mass.run()

