import time
import os
import random
import copy
from urllib.parse import urlparse
from collections import Counter
from app import utils
from app.config import Config
from app import services
from app import modules
from app.modules import ScanPortType, get_scan_ports, DomainDictType, CollectSource, TaskStatus
from app.services import fetchCert, run_risk_cruising, run_sniffer, BaseUpdateTask
from app.services.commonTask import CommonTask, WebSiteFetch, build_url_item
from app.helpers.domain import find_private_domain_by_task_id, find_public_ip_by_task_id
from app.services.findVhost import find_vhost
from app.services.dns_query import run_query_plugin
from app.services.searchEngines import search_engines

logger = utils.get_logger()

'''
域名爆破
'''


class DomainBrute(object):
    def __init__(self, base_domain, word_file=None, wildcard_domain_ip=None):
        if word_file is None:
            word_file = Config.DOMAIN_DICT_2W
        if wildcard_domain_ip is None:
            wildcard_domain_ip = []
        self.base_domain = base_domain
        self.base_domain_scope = "." + base_domain.strip(".")
        self.word_file = word_file

        self.brute_out = []
        self.resolver_map = {}
        self.domain_info_list = []
        self.domain_cnames = []
        self.brute_domain_map = {}  # 保存了通过massdns获取的结果
        self.wildcard_domain_ip = wildcard_domain_ip  # 保存获取的泛解析IP

    def _brute_domain(self):
        dicts_generator = utils.load_file_generator(self.word_file)
        self.brute_out = services.mass_dns(self.base_domain, dicts_generator, self.wildcard_domain_ip)

    def _resolver(self):
        domains = []
        domain_cname_record = []
        for x in self.brute_out:
            current_domain = x["domain"].lower()
            if not utils.domain_parsed(current_domain):
                continue

            # 删除掉过长的域名
            if len(current_domain) - len(self.base_domain) >= Config.DOMAIN_MAX_LEN:
                continue

            if utils.check_domain_black(current_domain):
                continue

            if current_domain not in domains:
                domains.append(current_domain)

            self.brute_domain_map[current_domain] = x["record"]

            if x["type"] == 'CNAME':
                self.domain_cnames.append(current_domain)
                current_record_domain = x['record']

                if not utils.domain_parsed(current_record_domain):
                    continue

                if utils.check_domain_black(current_record_domain):
                    continue
                if current_record_domain not in domain_cname_record:
                    domain_cname_record.append(current_record_domain)

        for domain in domain_cname_record:
            if not domain.endswith(self.base_domain_scope):
                continue
            if domain not in domains:
                domains.append(domain)

        start_time = time.time()
        logger.info("start resolver {} {}".format(self.base_domain, len(domains)))
        self.resolver_map = services.resolver_domain(domains)
        elapse = time.time() - start_time
        logger.info("end resolver {} result {}, elapse {}".format(self.base_domain,
                                                                  len(self.resolver_map), elapse))

    '''
    DomainInfo
    '''

    def run(self):
        start_time = time.time()
        logger.info("start brute {} with generator dicts".format(self.base_domain))
        self._brute_domain()
        elapse = time.time() - start_time
        logger.info("end brute {}, result {}, elapse {}".format(self.base_domain,
                                                                len(self.brute_out), elapse))

        self._resolver()

        filtered_dynamic_count = 0
        for domain in self.resolver_map:
            ips = self.resolver_map[domain]
            if ips:
                # 🛡️ 方案 4：智能拦截动态自指 CDN 边缘基础设施节点 (0 误杀)
                if utils.is_dynamic_ip_edge_domain(domain, resolved_ips=ips):
                    filtered_dynamic_count += 1
                    continue

                if domain in self.domain_cnames:
                    item = {
                        "domain": domain,
                        "type": "CNAME",
                        "record": [self.brute_domain_map[domain]],
                        "ips": ips
                    }
                else:
                    item = {
                        "domain": domain,
                        "type": "A",
                        "record": ips,
                        "ips": ips
                    }
                self.domain_info_list.append(modules.DomainInfo(**item))

        if filtered_dynamic_count > 0:
            logger.info("[+] 🛡️ 智能过滤: 共拦截 {} 个动态 IP / P2P-CDN 边缘基础设施节点 (已跳过入库与后续扫描)".format(filtered_dynamic_count))

        self.domain_info_list = list(set(self.domain_info_list))
        return self.domain_info_list


# 端口扫描
class ScanPort(object):
    def __init__(self, domain_info_list, option):
        self.domain_info_list = domain_info_list
        self.ipv4_map = {}
        self.ip_cdn_map = {}
        self.have_cdn_ip_list = []
        self.skip_scan_cdn_ip = False

        if option is None:
            option = {
                "ports": get_scan_ports(ScanPortType.TOP100),
                "service_detect": False,
                "os_detect": False,
                "port_parallelism": 32,
                "port_min_rate": 64,
                "custom_host_timeout": None,
                "exclude_ports": None
            }

        if 'skip_scan_cdn_ip' in option:
            self.skip_scan_cdn_ip = option["skip_scan_cdn_ip"]
            del option["skip_scan_cdn_ip"]

        self.option = option

    def get_cdn_name(self, ip, domain_info):
        cname = domain_info.record_list[0] if (domain_info.type == "CNAME" and domain_info.record_list) else ""
        return utils.get_cdn_name_comprehensive(ip=ip, cname=cname, ip_count=len(domain_info.ip_list))

    def run(self):
        for info in self.domain_info_list:
            for ip in info.ip_list:
                old_domain = self.ipv4_map.get(ip, set())
                old_domain.add(info.domain)
                self.ipv4_map[ip] = old_domain

                if ip not in self.ip_cdn_map:
                    cdn_name = self.get_cdn_name(ip, info)
                    self.ip_cdn_map[ip] = cdn_name
                    if cdn_name:
                        self.have_cdn_ip_list.append(ip)

        all_ipv4_list = self.ipv4_map.keys()
        if self.skip_scan_cdn_ip:
            all_ipv4_list = list(set(all_ipv4_list) - set(self.have_cdn_ip_list))

        start_time = time.time()
        logger.info("start port_scan {}".format(len(all_ipv4_list)))
        ip_port_result = []
        if all_ipv4_list:
            ip_port_result = services.port_scan(all_ipv4_list, **self.option)
            elapse = time.time() - start_time
            logger.info("end port_scan result {}, elapse {}".format(len(ip_port_result), elapse))

        ip_info_obj = []
        for result in ip_port_result:
            curr_ip = result["ip"]
            result["domain"] = list(self.ipv4_map[curr_ip])
            result["cdn_name"] = self.ip_cdn_map.get(curr_ip, "")

            port_info_obj_list = []
            for port_info in result["port_info"]:
                port_info_obj_list.append(modules.PortInfo(**port_info))

            result["port_info"] = port_info_obj_list

            ip_info_obj.append(modules.IPInfo(**result))

        if self.skip_scan_cdn_ip:
            fake_cdn_ip_info = self.build_fake_cdn_ip_info()
            ip_info_obj.extend(fake_cdn_ip_info)

        return ip_info_obj

    def build_fake_cdn_ip_info(self):
        ret = []
        map_80_port = {
            "port_id": 80,
            "service_name": "http",
            "version": "",
            "protocol": "tcp",
            "product": ""
        }
        fake_80_port = modules.PortInfo(**map_80_port)

        map_443_port = {
            "port_id": 443,
            "service_name": "https",
            "version": "",
            "protocol": "tcp",
            "product": ""
        }
        fake_443_port = modules.PortInfo(**map_443_port)
        fake_port_info = [fake_80_port, fake_443_port]

        for ip in self.ip_cdn_map:
            cdn_name = self.ip_cdn_map[ip]
            if not cdn_name:
                continue

            item = {
                "ip": ip,
                "domain": list(self.ipv4_map[ip]),
                "port_info": copy.deepcopy(fake_port_info),
                "cdn_name": cdn_name,
                "os_info": {}

            }
            ret.append(modules.IPInfo(**item))

        return ret


'''
站点发现
'''


class FindSite(object):
    def __init__(self, ip_info_list):
        self.ip_info_list = ip_info_list

    def _build(self):
        url_temp_list = []
        for info in self.ip_info_list:
            for domain in info.domain:
                for port_info in info.port_info_list:
                    port_id = port_info.port_id
                    if port_id == 80:
                        url_temp = "http://{}".format(domain)
                        url_temp_list.append(url_temp)
                        continue

                    if port_id == 443:
                        url_temp = "https://{}".format(domain)
                        url_temp_list.append(url_temp)
                        continue

                    url_temp1 = "http://{}:{}".format(domain, port_id)
                    url_temp2 = "https://{}:{}".format(domain, port_id)
                    url_temp_list.append(url_temp1)
                    url_temp_list.append(url_temp2)

        return url_temp_list

    def run(self):
        url_temp_list = set(self._build())
        start_time = time.time()
        check_map = services.check_http(url_temp_list)

        # 去除https和http相同的
        alive_site = []
        for x in check_map:
            if x.startswith("https://"):
                alive_site.append(x)

            elif x.startswith("http://"):
                x_temp = "https://" + x[7:]
                if x_temp not in check_map:
                    alive_site.append(x)

        elapse = time.time() - start_time
        logger.info("end check_http result {}, elapse {}".format(len(alive_site), elapse))

        return alive_site


'''
域名智能组合
'''


class AltDNS(object):
    def __init__(self, domain_info_list, base_domain, wildcard_domain_ip=None, alt_dns_dict=None):
        self.domain_info_list = domain_info_list
        self.base_domain = base_domain
        self.wildcard_domain_ip = wildcard_domain_ip
        self.alt_dns_dict = alt_dns_dict
        self.domains = []
        self.subdomains = []
        inner_dicts = "test adm admin api app beta demo dev front int internal intra ops pre pro prod qa sit staff stage test uat"
        self.dicts = inner_dicts.split()

    def _fetch_domains(self):
        base_len = len(self.base_domain)
        for item in self.domain_info_list:
            if not item.domain.endswith("." + self.base_domain):
                continue

            if utils.check_domain_black("a." + item.domain):
                continue

            self.domains.append(item.domain)
            subdomain = item.domain[:- (base_len + 1)]
            if "." in subdomain:
                self.subdomains.append(subdomain.split(".")[-1])

        random.shuffle(self.subdomains)

        most_cnt = 50
        if len(self.domains) < 1000:
            most_cnt = 30
            self.dicts.extend(self._load_dict())

        sub_dicts = list(dict(Counter(self.subdomains).most_common(most_cnt)).keys())
        self.dicts.extend(sub_dicts)

        self.dicts = list(set(self.dicts))

    def _load_dict(self):
        """加载内部字典"""
        d = set()
        dict_path = Config.altdns_dict_path
        if self.alt_dns_dict:
            from app.utils import get_safe_dict_path
            try:
                dict_path = get_safe_dict_path(self.alt_dns_dict)
            except Exception as e:
                logger.error("加载 alt_dns_dict 失败: {}".format(e))
                pass
                
        for x in utils.load_file_generator(dict_path):
            x = x.strip()
            if x:
                d.add(x)

        return list(d)

    def run(self):
        t1 = time.time()
        self._fetch_domains()

        logger.info("start {} AltDNS {}  dict {}".format(self.base_domain,
                                                         len(self.domains), len(self.dicts)))

        out = services.alt_dns(self.domains, self.base_domain,
                               self.dicts, wildcard_domain_ip=self.wildcard_domain_ip)

        elapse = time.time() - t1
        logger.info("end AltDNS result {}, elapse {}".format(len(out), elapse))

        return out


def domain_brute(base_domain, word_file=None, wildcard_domain_ip=None):
    if word_file is None:
        word_file = Config.DOMAIN_DICT_2W
    if wildcard_domain_ip is None:
        wildcard_domain_ip = []

    b = DomainBrute(base_domain, word_file, wildcard_domain_ip)
    return b.run()


def scan_port(domain_info_list, option=None):
    s = ScanPort(domain_info_list, option)
    return s.run()


def find_site(ip_info_list):
    f = FindSite(ip_info_list)
    return f.run()


def alt_dns(domain_info_list, base_domain, wildcard_domain_ip=None, alt_dns_dict=None):
    a = AltDNS(domain_info_list, base_domain, wildcard_domain_ip=wildcard_domain_ip, alt_dns_dict=alt_dns_dict)
    return a.run()


def ssl_cert(ip_info_list, base_domain):
    try:
        f = fetchCert.SSLCert(ip_info_list, base_domain)
        return f.run()
    except Exception as e:
        logger.exception(e)

    return {}


'''
domain_brute
domain_brute_type  test big bigbig
port_scan_type
port_scan
service_detection
service_brute
os_detection
link_fetch
site_identify
site_capture
file_leak
alt_dns
ssl_cert
skip_scan_cdn_ip
dns_query_plugin
'''

MAX_MAP_COUNT = getattr(Config, "DOMAIN_MAX_MAP_COUNT", 200)

RECURSIVE_SENSITIVE_PREFIXES = {
    "api", "app", "dev", "test", "qa", "uat", "pre", "boe", "ppe",
    "admin", "gw", "gateway", "k8s", "corp", "intra", "inner", "cloud",
    "saas", "pass", "service", "node", "web", "mobile", "h5", "open", "lead", "leads"
}

def _load_recursive_dict():
    dict_path = os.path.join(Config.basedir, 'dicts', 'domain_top300.txt')
    if os.path.exists(dict_path):
        words = []
        with open(dict_path, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                w = line.strip().lower()
                if w and not w.startswith('#'):
                    words.append(w)
        if words:
            return words
    return [
        "api", "app", "web", "admin", "dev", "test", "qa", "uat", "pre", "prod",
        "gateway", "gw", "service", "auth", "sso", "login", "pay", "order", "user",
        "data", "bi", "report", "open", "h5", "m", "static", "img", "res", "doc",
        "manage", "mis", "portal", "inner", "intra", "corp", "k8s", "node", "core"
    ]

RECURSIVE_TOP_DICT = _load_recursive_dict()



class DomainTask(CommonTask):
    def __init__(self, base_domain=None, task_id=None, options=None):
        super().__init__(task_id=task_id)

        self.base_domain = base_domain
        self.task_id = task_id
        self.options = options

        self.domain_info_list = []  # 在 start_site_fetch 运行后会清空，用来释放内存
        self.ip_info_list = []
        self.ip_set = set()
        self.site_list = []
        self.record_map = {}
        self.ipv4_map = {}
        self.cert_map = {}
        self.service_info_list = []
        # 用来区分是正常任务还是监控任务
        self.task_tag = "task"

        # 用来存放泛解析域名映射的IP
        self._not_found_domain_ips = None
        self._domain_dict_size = None
        self._domain_word_file = None

        self.npoc_service_target_set = set()

        self.web_site_fetch = None

        self.wih_domain_set = set()  # 通过调用 WebInfoHunter 获取的域名集合

        option_scan_port_type = self.options.get("port_scan_type", "test")
        
        if option_scan_port_type == "custom" and self.options.get("port_custom"):
            actual_ports = self.options.get("port_custom")
        else:
            actual_ports = get_scan_ports(option_scan_port_type)

        scan_port_option = {
            "ports": actual_ports,
            "service_detect": self.options.get("service_detection", False),
            "os_detect": self.options.get("os_detection", False),
            "skip_scan_cdn_ip": self.options.get("skip_scan_cdn_ip", False),  # 跳过扫描CDN IP
            "port_parallelism": self.options.get("port_parallelism", 32),  # 探测报文并行度
            "port_min_rate": self.options.get("port_min_rate", 64),  # 最少发包速率
            "custom_host_timeout": None,  # 主机超时时间(s)
            "exclude_ports": self.options.get("exclude_ports", None)  # 排除的端口
        }

        # 只有当设置为自定义时才会去设置超时时间
        if self.options.get("host_timeout_type") == "custom":
            scan_port_option["custom_host_timeout"] = self.options.get("host_timeout", 60 * 15)

        self.scan_port_option = scan_port_option

        self.base_update_task = BaseUpdateTask(self.task_id)

    @property
    def domain_word_file(self) -> str:
        if self._domain_word_file is None:
            domain_brute_type = self.options.get("domain_brute_type", "test")
            if domain_brute_type.endswith(".txt"):
                from app.utils import get_safe_dict_path
                domain_word_file = get_safe_dict_path(domain_brute_type)
            else:
                brute_dict_map = {
                    "big": DomainDictType.BIG
                }
                domain_word_file = brute_dict_map.get(domain_brute_type, DomainDictType.BIG)
            self._domain_word_file = domain_word_file

        return self._domain_word_file

    @property
    def domain_dict_size(self):
        if self._domain_dict_size is None:
            count = 0
            for _ in utils.load_file_generator(self.domain_word_file):
                count += 1
            self._domain_dict_size = count

        return self._domain_dict_size

    @property
    def not_found_domain_ips(self):
        # ** 用来判断是否是泛解析域名，采用双随机探测交叉验证，防止单次调度或CDN随机节点误判
        if self._not_found_domain_ips is None:
            fake_domain_1 = "at" + utils.random_choices(6) + "." + self.base_domain
            fake_domain_2 = "at" + utils.random_choices(6) + "." + self.base_domain
            ips1 = utils.get_ip(fake_domain_1, log_flag=False)
            ips2 = utils.get_ip(fake_domain_2, log_flag=False)

            if ips1 and ips2 and set(ips1) == set(ips2):
                self._not_found_domain_ips = list(ips1)
                cnames = utils.get_cname(fake_domain_1, log_flag=False)
                if cnames:
                    self._not_found_domain_ips.extend(cnames)
            else:
                self._not_found_domain_ips = []

            if self._not_found_domain_ips:
                logger.info("not_found_domain_ips  {} {}".format(self.base_domain, self._not_found_domain_ips))

        return self._not_found_domain_ips

    def save_domain_info_list(self, domain_info_list, source=CollectSource.DOMAIN_BRUTE):
        for domain_info_obj in domain_info_list:
            domain_info = domain_info_obj.dump_json(flag=False)
            domain_info["task_id"] = self.task_id
            domain_info["source"] = source
            domain_parsed = utils.domain_parsed(domain_info["domain"])
            if domain_parsed:
                domain_info["fld"] = domain_parsed["fld"]
            utils.safe_insert_asset('domain', ['task_id', 'domain'], domain_info)

    def domain_brute(self):
        # 调用工具去进行域名爆破，如果存在泛解析，会把包含泛解析的IP的域名给删除
        domain_info_list = domain_brute(self.base_domain, word_file=self.domain_word_file,
                                        wildcard_domain_ip=self.not_found_domain_ips)

        domain_info_list = self.clear_domain_info_by_record(domain_info_list)
        if self.task_tag == "task":
            self.save_domain_info_list(domain_info_list, source=CollectSource.DOMAIN_BRUTE)
        self.domain_info_list.extend(domain_info_list)

    def clear_domain_info_by_record(self, domain_info_list):
        new_list = []
        for info in domain_info_list:
            if not info.record_list:
                continue

            record = info.record_list[0]

            ip = info.ip_list[0]

            # 解决泛解析域名问题，果断剔除
            if ip in self.not_found_domain_ips:
                continue

            cnt = self.record_map.get(record, 0)
            cnt += 1
            self.record_map[record] = cnt
            if cnt > MAX_MAP_COUNT:
                continue

            new_list.append(info)

        return new_list

    def arl_search(self):
        arl_t1 = time.time()
        logger.info("start arl fetch {}".format(self.base_domain))
        arl_all_domains = utils.arl_domain(self.base_domain)
        domain_info_list = self.build_domain_info(arl_all_domains)
        if self.task_tag == "task":
            domain_info_list = self.clear_domain_info_by_record(domain_info_list)
            self.save_domain_info_list(domain_info_list, source=CollectSource.ARL)

        self.domain_info_list.extend(domain_info_list)
        elapse = time.time() - arl_t1
        logger.info("end arl fetch {} {} elapse {}".format(
            self.base_domain, len(domain_info_list), elapse))

    def build_domain_info(self, domains):
        """
        构建domain_info_list 带去重功能
        """
        fake_list = []
        domains_set = set()
        for item in domains:
            domain = item
            if isinstance(item, dict):
                domain = item["domain"]

            domain = domain.lower().strip()
            if domain in domains_set:
                continue
            domains_set.add(domain)

            if utils.check_domain_black(domain):
                continue

            fake = {
                "domain": domain,
                "type": "CNAME",
                "record": [],
                "ips": []
            }
            fake_info = modules.DomainInfo(**fake)
            if fake_info not in self.domain_info_list:
                fake_list.append(fake_info)

        if self.task_tag == "monitor":
            return fake_list
        domain_info_list = services.build_domain_info(fake_list)

        return domain_info_list

    def alt_dns_current(self):
        primary_domain = utils.get_fld(self.base_domain)
        # 当前下发的是主域名，就跳过
        if primary_domain == self.base_domain or primary_domain == "":
            return []
        fake = {
            "domain": self.base_domain,
            "type": "CNAME",
            "record": [],
            "ips": []
        }
        fake_info = modules.DomainInfo(**fake)

        logger.info("alt_dns_current {}, primary_domain:{}".format(self.base_domain, primary_domain))
        data = alt_dns([fake_info], primary_domain, wildcard_domain_ip=self.not_found_domain_ips, alt_dns_dict=self.options.get("alt_dns_dict"))

        return data

    def alt_dns(self):
        if self.task_tag == "monitor" and len(self.domain_info_list) >= 800:
            logger.info("skip alt_dns on monitor {}".format(self.base_domain))
            return

        if len(self.domain_info_list) > 300 and len(self.not_found_domain_ips) > 0:
            logger.warning("{} 域名泛解析, 当前子域名{}, 大于300, 不进行alt_dns".format(
                self.base_domain, len(self.domain_info_list)))
            return

        alt_dns_current_out = self.alt_dns_current()

        alt_dns_out = alt_dns(self.domain_info_list, self.base_domain, wildcard_domain_ip=self.not_found_domain_ips, alt_dns_dict=self.options.get("alt_dns_dict"))

        alt_dns_out.extend(alt_dns_current_out)
        # 没有结果，直接返回
        if len(alt_dns_out) <= 0:
            return

        alt_domain_info_list = self.build_domain_info(alt_dns_out)
        if self.task_tag == "task":
            alt_domain_info_list = self.clear_domain_info_by_record(alt_domain_info_list)

            logger.info("alt_dns real result:{}".format(len(alt_domain_info_list)))

            if len(alt_domain_info_list) > 0:
                self.save_domain_info_list(alt_domain_info_list,
                                           source=CollectSource.ALTDNS)

        self.domain_info_list.extend(alt_domain_info_list)

    def port_scan(self):
        ip_info_list = scan_port(self.domain_info_list, self.scan_port_option)

        for ip_info_obj in ip_info_list:
            ip_info = ip_info_obj.dump_json(flag=False)
            ip_info["task_id"] = self.task_id

            utils.safe_insert_asset('ip', ['task_id', 'ip'], ip_info)

        self.ip_info_list.extend(ip_info_list)

    def find_site(self):
        if self.options.get("port_scan"):
            '''***站点寻找***'''
            sites = find_site(self.ip_info_list)
        else:
            sites = services.probe_http(self.domain_info_list)

        self.site_list.extend(sites)

    def update_services(self, service_name, elapsed):
        self.base_update_task.update_services(service_name=service_name, elapsed=elapsed)

    def update_task_field(self, field=None, value=None):
        self.base_update_task.update_task_field(field=field, value=value)

    def gen_ipv4_map(self):
        ipv4_map = {}
        for domain_info in self.domain_info_list:
            for ip in domain_info.ip_list:
                old_domain = ipv4_map.get(ip, set())
                old_domain.add(domain_info.domain)
                ipv4_map[ip] = old_domain
                self.ip_set.add(ip)

        self.ipv4_map = ipv4_map

    # 只是保存没有开放端口的
    def save_ip_info(self):
        fake_ip_info_list = []
        for ip in self.ipv4_map:
            data = {
                "ip": ip,
                "domain": list(self.ipv4_map[ip]),
                "port_info": [],
                "os_info": {},
                "cdn_name": utils.get_cdn_name_by_ip(ip)
            }
            info_obj = modules.IPInfo(**data)
            if info_obj not in self.ip_info_list:
                fake_ip_info_list.append(info_obj)

        for ip_info_obj in fake_ip_info_list:
            ip_info = ip_info_obj.dump_json(flag=False)
            ip_info["task_id"] = self.task_id
            utils.safe_insert_asset('ip', ['task_id', 'ip'], ip_info)

    def save_service_info(self):
        self.service_info_list = []
        services_list = set()
        for _data in self.ip_info_list:
            port_info_list = _data.port_info_list
            for _info in port_info_list:
                if _info.service_name:
                    if _info.service_name not in services_list:
                        _result = {}
                        _result["service_name"] = _info.service_name
                        _result["service_info"] = []
                        _result["service_info"].append({'ip': _data.ip,
                                                        'port_id': _info.port_id,
                                                        'product': _info.product,
                                                        'version': _info.version})
                        _result["task_id"] = self.task_id
                        self.service_info_list.append(_result)
                        services_list.add(_info.service_name)
                    else:
                        for service_info in self.service_info_list:
                            if service_info.get("service_name") == _info.service_name:
                                service_info['service_info'].append({'ip': _data.ip,
                                                                     'port_id': _info.port_id,
                                                                     'product': _info.product,
                                                                     'version': _info.version})
        if self.service_info_list:
            for srv_item in self.service_info_list:
                utils.safe_insert_asset('service', ['task_id', 'service_name'], srv_item)

    def ssl_cert(self):
        if self.options.get("port_scan"):
            self.cert_map = ssl_cert(self.ip_info_list, self.base_domain)
        else:
            self.cert_map = ssl_cert(self.ip_set, self.base_domain)

        cert_domains = set()
        for target in self.cert_map:
            if ":" not in target:
                continue
            ip = target.split(":")[0]
            port = int(target.split(":")[1])
            cert_data = self.cert_map[target]
            item = {
                "ip": ip,
                "port": port,
                "cert": cert_data,
                "task_id": self.task_id,
            }
            utils.safe_insert_asset('cert', ['task_id', 'ip', 'port'], item)

            # 核心优化：从 TLS 证书 SAN / CN 中提取属于 base_domain 的有效子域名
            extracted = utils.extract_domains_from_cert(cert_data, self.base_domain)
            cert_domains.update(extracted)

        if cert_domains:
            logger.info(f"extracted {len(cert_domains)} subdomains from SSL certs for {self.base_domain}")
            cert_domain_info_list = self.build_domain_info(list(cert_domains))
            if self.task_tag == "task":
                cert_domain_info_list = self.clear_domain_info_by_record(cert_domain_info_list)
                self.save_domain_info_list(cert_domain_info_list, source="ssl_cert")
            self.domain_info_list.extend(cert_domain_info_list)


    def build_single_domain_info(self, domain):
        _type = "A"
        cname = utils.get_cname(domain)
        if cname:
            _type = 'CNAME'
        ips = utils.get_ip(domain)
        if _type == "A":
            record = ips
        else:
            record = cname

        if not ips:
            return

        item = {
            "domain": domain,
            "type": _type,
            "record": record,
            "ips": ips
        }

        return modules.DomainInfo(**item)

    # *** 执行域名查询插件
    def dns_query_plugin(self):
        logger.info("start run dns_query_plugin {}".format(self.base_domain))
        results = run_query_plugin(self.base_domain, [])
        sources_map = dict()
        for result in results:
            domain = result["domain"]
            source = result["source"]
            source_domains = sources_map.get(source, [])
            source_domains.append(domain)
            sources_map[source] = source_domains

        cnt = 0  # 统计真实数据
        for source in sources_map:
            source_domains = sources_map[source]
            if not source_domains:
                continue
            logger.info("start build domain info, source:{}".format(source))
            domain_info_list = self.build_domain_info(source_domains)
            if self.task_tag == "task":
                domain_info_list = self.clear_domain_info_by_record(domain_info_list)
                self.save_domain_info_list(domain_info_list, source=source)

            cnt += len(domain_info_list)
            self.domain_info_list.extend(domain_info_list)

        logger.info("end run dns_query_plugin {}, result {}, real result:{}".format(
            self.base_domain, len(results), cnt))

    def domain_fetch(self):
        '''****域名爆破开始****'''
        if self.options.get("domain_brute"):
            self.update_task_field("status", "domain_brute")
            with self.safe_phase("domain_brute", self.base_update_task):
                self.domain_brute()
        else:
            domain_info = self.build_single_domain_info(self.base_domain)
            if domain_info:
                self.domain_info_list.append(domain_info)
                self.save_domain_info_list([domain_info])

        if "{fuzz}" in self.base_domain:
            return

        # ***域名插件查询****
        if self.options.get("dns_query_plugin"):
            self.update_task_field("status", "dns_query_plugin")
            with self.safe_phase("dns_query_plugin", self.base_update_task):
                self.dns_query_plugin()

        if self.options.get("arl_search"):
            self.update_task_field("status", "arl_search")
            with self.safe_phase("arl_search", self.base_update_task):
                self.arl_search()

        '''***智能域名生成****'''
        if self.options.get("alt_dns"):
            self.update_task_field("status", "alt_dns")
            with self.safe_phase("alt_dns", self.base_update_task):
                self.alt_dns()

        '''***智能多级递归爆破****'''
        if self.options.get("domain_brute"):
            self.update_task_field("status", "recursive_domain_brute")
            with self.safe_phase("recursive_domain_brute", self.base_update_task):
                self.recursive_domain_brute()

    def recursive_domain_brute(self):
        """
        [第一性原理：针对高价值三级子域的智能多级递归爆破]
        当发现开发/测试/网关/API等高价值三级域名时，使用精选 Top 300 词库探测四级/五级内层子域
        """
        t1 = time.time()
        base_len = len(self.base_domain)
        target_subs = set()
        for item in self.domain_info_list:
            domain = item.domain.lower().strip()
            if not domain.endswith("." + self.base_domain) or domain == self.base_domain:
                continue
            sub = domain[:- (base_len + 1)]
            # 针对直接三级子域名（如 dev.xxx.com, api.xxx.com）
            labels = sub.split(".")
            if len(labels) == 1:
                prefix = labels[0]
                if prefix in RECURSIVE_SENSITIVE_PREFIXES or any(p in prefix for p in ["dev", "test", "api", "qa", "uat", "pre", "boe", "ppe", "admin", "gw"]):
                    target_subs.add(domain)

        if not target_subs:
            return

        logger.info("start recursive_domain_brute on {} sub-targets for {}".format(len(target_subs), self.base_domain))
        recursive_discovered = []
        for sub_target in list(target_subs)[:10]:  # 限制最多同时对前 10 个高价值子域执行递归，保障极速性能
            r1 = "rf" + utils.random_choices(6) + "." + sub_target
            r2 = "rf" + utils.random_choices(6) + "." + sub_target
            ips1 = set(utils.get_ip(r1, log_flag=False) or [])
            ips2 = set(utils.get_ip(r2, log_flag=False) or [])
            wildcard_ips = []
            if ips1 and ips2 and ips1 == ips2:
                wildcard_ips = list(ips1)

            out = services.mass_dns(sub_target, RECURSIVE_TOP_DICT, wildcard_ips)
            for x in out:
                rec_domain = x.get("domain", "").lower().strip()
                if rec_domain and rec_domain.endswith("." + self.base_domain):
                    recursive_discovered.append(rec_domain)

        if recursive_discovered:
            recursive_discovered = list(set(recursive_discovered))
            logger.info("recursive_domain_brute found {} raw candidates".format(len(recursive_discovered)))
            domain_info_list = self.build_domain_info(recursive_discovered)
            if self.task_tag == "task":
                domain_info_list = self.clear_domain_info_by_record(domain_info_list)
                self.save_domain_info_list(domain_info_list, source="recursive_brute")
            self.domain_info_list.extend(domain_info_list)

        elapse = time.time() - t1
        logger.info("end recursive_domain_brute result {}, elapse {:.2f}s".format(len(recursive_discovered), elapse))


    def start_ip_fetch(self):
        self.gen_ipv4_map()

        '''***端口扫描开始***'''
        if self.options.get("port_scan"):
            self.update_task_field("status", "port_scan")
            with self.safe_phase("port_scan", self.base_update_task):
                self.port_scan()

        '''***证书获取***'''
        if self.options.get("ssl_cert"):
            self.update_task_field("status", "ssl_cert")
            with self.safe_phase("ssl_cert", self.base_update_task):
                self.ssl_cert()

        # 服务信息存储
        if self.options.get("service_detection"):
            self.save_service_info()
        self.save_ip_info()

    def start_site_fetch(self):
        self.update_task_field("status", "find_site")
        with self.safe_phase("find_site", self.base_update_task):
            self.find_site()

        # 对 domain_info_list 进行清空，回收内存
        self.domain_info_list = []

        web_site_fetch = WebSiteFetch(task_id=self.task_id,
                                      sites=self.site_list, options=self.options,
                                      scope_domain=[self.base_domain])
        web_site_fetch.run()

        self.wih_domain_set = web_site_fetch.wih_domain_set

        self.web_site_fetch = web_site_fetch

    def npoc_service_detection(self):
        targets = []
        for ip_info in self.ip_info_list:
            for port_info in ip_info.port_info_list:
                skip_port_list = [80, 443, 843]
                if port_info.port_id in skip_port_list:
                    continue

                targets.append("{}:{}".format(ip_info.ip, port_info.port_id))

        result = run_sniffer(targets)
        for item in result:
            self.npoc_service_target_set.add(item["target"])
            item["task_id"] = self.task_id
            item["save_date"] = utils.curr_date()
            utils.safe_insert_asset('npoc_service', ['task_id', 'target'], item)

    def start_poc_run(self):
        """poc run"""
        """服务识别（python）实现"""
        if self.options.get("npoc_service_detection"):
            self.update_task_field("status", "npoc_service_detection")
            self.npoc_service_detection()

        """ *** npoc 调用 """
        if self.options.get("poc_config"):
            self.update_task_field("status", "poc_run")
            self.web_site_fetch.risk_cruising(self.npoc_service_target_set)

        """弱口令爆破服务"""
        if self.options.get("brute_config"):
            self.update_task_field("status", "weak_brute")
            self.brute_config()

    def brute_config(self):
        plugins = []
        brute_config = self.options.get("brute_config")
        for x in brute_config:
            if not x.get("enable"):
                continue
            plugins.append(x["plugin_name"])

        if not plugins:
            return
        targets = self.site_list.copy()
        targets += list(self.npoc_service_target_set)
        result = run_risk_cruising(targets=targets, plugins=plugins)
        for item in result:
            item["task_id"] = self.task_id
            item["save_date"] = utils.curr_date()
            if "plg_name" in item:
                item["plugin_name"] = item.get("plg_name")
            if "target" in item:
                item["vuln_url"] = item.get("target")
            utils.safe_insert_asset('vuln', ['task_id', 'vuln_url', 'plugin_name'], item)

    def find_vhost_vuln(self):
        domains = find_private_domain_by_task_id(self.task_id)
        if not domains:
            return

        ips = find_public_ip_by_task_id(self.task_id)
        results = find_vhost(ips=ips, domains=domains)
        for result in results:
            save_item = dict()
            save_item["plg_name"] = "FindVhost"
            save_item["plg_type"] = "scan"
            save_item["vul_name"] = "发现Host碰撞漏洞"
            save_item["app_name"] = "web"
            save_item["target"] = result["url"]
            save_item["verify_data"] = "{}-{}-{}-{}".format(result["domain"],
                                                            result["title"],
                                                            result["status_code"],
                                                            result["body_length"])
            save_item["verify_obj"] = result
            save_item["task_id"] = self.task_id
            save_item["save_date"] = utils.curr_date()
            save_item["plugin_name"] = save_item["plg_name"]
            save_item["vuln_url"] = save_item["target"]
            utils.safe_insert_asset('vuln', ['task_id', 'vuln_url', 'plugin_name'], save_item)

    def start_find_vhost(self):
        if self.options.get("findvhost"):
            self.update_task_field("status", "find_vhost")
            self.find_vhost_vuln()

    # 搜索引擎调用
    def search_engines(self):
        if not self.options.get("search_engines"):
            return

        if "{fuzz}" in self.base_domain:
            return

        self.update_task_field("status", "search_engines")
        search_engines_urls = search_engines(self.base_domain)
        t1 = time.time()

        urls = set()  # 保存通过搜索引擎获取到的URL
        domains = set()
        for url in search_engines_urls:
            parse = urlparse(url)
            netloc = parse.netloc
            netloc_domain = netloc.split(":")[0]

            # 只是过滤有效URL
            if netloc_domain.endswith("." + self.base_domain) or \
                    self.base_domain == netloc_domain:
                domains.add(netloc_domain)
            else:
                continue

            # 过滤掉路径为首页的URL
            if parse.path == "/" or parse.path == "":
                continue

            urls.add(url)

        # 可能发现新的域名， 这里保存起来
        domain_info_list = []
        if len(domains) > 0:
            domain_info_list = self.build_domain_info(domains)
            if self.task_tag == "task":
                domain_info_list = self.clear_domain_info_by_record(domain_info_list)
                self.save_domain_info_list(domain_info_list, source=CollectSource.SEARCHENGINE)
            self.domain_info_list.extend(domain_info_list)

        elapse = time.time() - t1
        self.update_services("search_engines", elapse)

        logger.info("search_engines {}, result domain:{} url:{}".format(self.base_domain,
                                                                        len(domain_info_list),
                                                                        len(urls)))

        # 构建Page 信息
        if len(urls) > 0:
            page_map = services.page_fetch(urls)
            for url in page_map:
                item = build_url_item(url, self.task_id, source=CollectSource.SEARCHENGINE)
                item.update(page_map[url])
                item["task_id"] = self.task_id
                utils.safe_insert_asset('url', ['task_id', 'url'], item)

    def process_wih_domains(self):
        if not self.wih_domain_set:
            return

        self.update_task_field("status", "wih_domain_update")
        t1 = time.time()
        
        from app.helpers import find_domain_by_task_id
        processed_domains = set(find_domain_by_task_id(self.task_id))
        
        iteration = 1
        while self.wih_domain_set - processed_domains:
            new_domains = list(self.wih_domain_set - processed_domains)
            processed_domains.update(new_domains)
            
            logger.info("wih_domain_update iteration {} found {} new domains".format(iteration, len(new_domains)))
            
            domain_info_list = self.build_domain_info(new_domains)
            if self.task_tag in ["task", "monitor"]:
                domain_info_list = self.clear_domain_info_by_record(domain_info_list)
                self.save_domain_info_list(domain_info_list, source="wih")
            
            if not domain_info_list:
                break
                
            new_sites = services.probe_http([d.domain for d in domain_info_list], 15)
            if not new_sites:
                continue
                
            self.site_list.extend(new_sites)
            
            web_site_fetch = WebSiteFetch(task_id=self.task_id,
                                          sites=new_sites, options=self.options,
                                          scope_domain=[self.base_domain])
            web_site_fetch.run()
            
            self.wih_domain_set.update(web_site_fetch.wih_domain_set)
            
            iteration += 1

        # 更新主体 web_site_fetch 的 sites 列表，确保后续 poc_run 能扫描到新增的站点
        if hasattr(self, 'web_site_fetch') and self.web_site_fetch:
            self.web_site_fetch.sites = self.site_list.copy()

        elapse = time.time() - t1
        self.update_services("wih_domain_update", elapse)

    def run(self):
        base_update = self.base_update_task
        self.update_task_field("start_time", utils.curr_date())

        self.domain_fetch()

        # 搜索引擎调用
        with self.safe_phase("search_engines", base_update):
            self.search_engines()

        self.start_ip_fetch()

        self.start_site_fetch()

        with self.safe_phase("process_wih_domains", base_update):
            self.process_wih_domains()

        if self.options.get("findvhost"):
            with self.safe_phase("find_vhost", base_update):
                self.start_find_vhost()

        if self.options.get("npoc_service_detection") or self.options.get("poc_config") or self.options.get("brute_config"):
            with self.safe_phase("poc_run", base_update):
                self.start_poc_run()
            
        if self.options.get("file_leak"):
            with self.safe_phase("file_leak", base_update):
                if hasattr(self, 'web_site_fetch') and self.web_site_fetch:
                    self.web_site_fetch.run_func("file_leak", self.web_site_fetch.file_leak)

        # nuclei_scan 放在最后执行，防止高并发扫描把目标打挂或者触发IP封禁
        if self.options.get("nuclei_scan"):
            with self.safe_phase("nuclei_scan", base_update):
                if hasattr(self, 'web_site_fetch') and self.web_site_fetch:
                    self.web_site_fetch.run_func("nuclei_scan", self.web_site_fetch.nuclei_scan)

        # 执行统计和同步操作
        with self.safe_phase("common_run", base_update):
            self.common_run()

        self.update_task_field("status", TaskStatus.DONE)
        self.update_task_field("end_time", utils.curr_date())


def domain_task(base_domain, task_id, options):
    d = DomainTask(base_domain=base_domain, task_id=task_id, options=options)
    try:
        d.run()
    except Exception as e:
        logger.exception(e)
        d.update_task_field("status", TaskStatus.ERROR)
        d.update_task_field("end_time", utils.curr_date())
