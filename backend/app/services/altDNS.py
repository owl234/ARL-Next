import re
import tld
from collections import Counter
from app.config import Config
from app import utils
from .massdns import MassDNS

logger = utils.get_logger()

# 语义对仗定向替换组（极高命中率且不产生无序膨胀）
SEMANTIC_SWAP_GROUPS = [
    # 研发与发布环境组
    {"dev", "test", "qa", "uat", "pre", "prod", "boe", "ppe", "gray", "canary", "stage", "staging", "daily", "bench", "sit", "fat"},
    # 权限与内外网隔离组
    {"internal", "external", "intra", "extra", "priv", "private", "pub", "public", "inner", "outer"},
    # 主从与灾备高可用组
    {"master", "slave", "backup", "bak", "standby", "primary", "secondary", "main"},
    # 核心 IDC 地域与多中心组
    {"bj", "sh", "sz", "hz", "gz", "cd", "wh", "xa", "hk", "sg", "us", "eu", "beijing", "shanghai", "shenzhen", "hangzhou"},
    # 接口版本与协议组
    {"v1", "v2", "v3", "v4", "api", "openapi", "grpc", "ws"}
]


class DnsGen(object):
    def __init__(self, subdomains, words, base_domain=None):
        self.subdomains = subdomains
        self.base_domain = base_domain
        self.words = list(words) if words else []

        # 智能提取目标品牌与核心词根，注入动态变异池
        if self.base_domain:
            main_label = self.base_domain.split(".")[0].lower()
            if len(main_label) >= 3 and main_label not in self.words:
                self.words.append(main_label)
            # 常见品牌缩写切分（如 dcdapp -> dcd）
            m = re.match(r'^([a-z]{3,5})(?:app|web|net|vip|tech|group)$', main_label)
            if m:
                short_brand = m.group(1)
                if short_brand not in self.words:
                    self.words.append(short_brand)

    def partiate_domain(self, domain):
        """
        Split domain base on subdomain levels.
        """
        if self.base_domain:
            subdomain = re.sub(re.escape("." + self.base_domain) + "$", '', domain)
            return subdomain.split(".") + [self.base_domain]

        ext = tld.get_tld(domain.lower(), fail_silently=True, as_object=True, fix_protocol=True)
        if not ext:
            return domain.split(".")
        base_domain = "{}.{}".format(ext.domain, ext.suffix)
        parts = (ext.subdomain.split('.') + [base_domain])
        return [p for p in parts if p]

    def insert_word_every_index(self, parts):
        """
        Create new subdomain levels by inserting the words between existing levels
        """
        domains = []
        for w in self.words:
            for i in range(len(parts)):
                if i + 1 == len(parts):
                    break
                if w in parts[:-1]:
                    continue
                tmp_parts = list(parts[:-1])
                tmp_parts.insert(i, w)
                domains.append('{}.{}'.format('.'.join(tmp_parts), parts[-1]))
        return domains

    def insert_num_every_index(self, parts):
        """
        Create new subdomain levels with formatted numbers (1~5, 01~05, -1~-5, -01~-05)
        """
        domains = []
        num_patterns = [
            "{num}", "{num:02d}", "-{num}", "-{num:02d}"
        ]
        for num in range(1, 6):
            for i in range(len(parts[:-1])):
                for pat in num_patterns:
                    suffix = pat.format(num=num)
                    tmp_parts = list(parts[:-1])
                    tmp_parts[i] = '{}{}'.format(tmp_parts[i], suffix)
                    domains.append('{}.{}'.format('.'.join(tmp_parts), '.'.join(parts[-1:])))
        return domains

    def prepend_word_every_index(self, parts):
        """
        Prepend existing content with `WORD` and `WORD-`
        """
        domains = []
        for w in self.words:
            for i in range(len(parts[:-1])):
                if w in parts[:-1]:
                    continue
                tmp_parts = list(parts[:-1])
                tmp_parts[i] = '{}{}'.format(w, tmp_parts[i])
                domains.append('{}.{}'.format('.'.join(tmp_parts), parts[-1]))

                tmp_parts = list(parts[:-1])
                tmp_parts[i] = '{}-{}'.format(w, tmp_parts[i])
                domains.append('{}.{}'.format('.'.join(tmp_parts), parts[-1]))
        return domains

    def append_word_every_index(self, parts):
        """
        Append existing content with `WORD` and `WORD-`
        """
        domains = []
        for w in self.words:
            for i in range(len(parts[:-1])):
                if w in parts[:-1]:
                    continue
                tmp_parts = list(parts[:-1])
                tmp_parts[i] = '{}{}'.format(tmp_parts[i], w)
                domains.append('{}.{}'.format('.'.join(tmp_parts), '.'.join(parts[-1:])))

                tmp_parts = list(parts[:-1])
                tmp_parts[i] = '{}-{}'.format(tmp_parts[i], w)
                domains.append('{}.{}'.format('.'.join(tmp_parts), '.'.join(parts[-1:])))
        return domains

    def semantic_swap_word(self, parts):
        """
        基于语义对仗组（研发环境、内外网、IDC地域、主备）进行定向精准互换
        """
        domains = []
        sub_str = '.'.join(parts[:-1])
        for group in SEMANTIC_SWAP_GROUPS:
            for item in group:
                if item in sub_str:
                    for alt_item in group:
                        if item == alt_item:
                            continue
                        new_sub = sub_str.replace(item, alt_item)
                        domains.append('{}.{}'.format(new_sub, '.'.join(parts[-1:])))
        return domains

    def replace_word_with_word(self, parts):
        """
        If word longer than 3 is found in existing subdomain, replace it with other words from the dictionary
        """
        domains = []
        sub_str = '.'.join(parts[:-1])
        for w in self.words:
            if len(w) <= 3:
                continue
            if w in sub_str:
                for w_alt in self.words:
                    if w == w_alt or len(w_alt) <= 3:
                        continue
                    domains.append('{}.{}'.format(sub_str.replace(w, w_alt), '.'.join(parts[-1:])))
        return domains

    def cross_service_hyphen_projection(self):
        """
        自适应从已发现资产中学习连字符修饰符（如 -lq, -hl, -inner, -sinf, -motor 等机房/集群标识），
        并与所有存活的主业务前缀做交叉组合
        """
        domains = []
        if not self.base_domain:
            return domains

        modifiers = set()
        biz_prefixes = set()

        for d in self.subdomains:
            d_lower = d.lower().strip()
            if not d_lower.endswith("." + self.base_domain) or d_lower == self.base_domain:
                continue
            sub = d_lower[:- (len(self.base_domain) + 1)]
            parts = sub.split(".")
            for part in parts:
                if "-" in part:
                    tokens = part.split("-")
                    if len(tokens) == 2:
                        left, right = tokens[0].strip(), tokens[1].strip()
                        if left and right:
                            biz_prefixes.add(left)
                            modifiers.add(right)
                else:
                    if len(part) >= 2 and not part.isdigit():
                        biz_prefixes.add(part)

        core_biz = {"api", "app", "web", "admin", "gw", "gateway", "auth", "sso", "passport", "open", "m", "h5", "manage", "pay", "user", "order"}
        biz_prefixes.update(core_biz)

        for mod in modifiers:
            if len(mod) < 2 or len(mod) > 15:
                continue
            for biz in biz_prefixes:
                if len(biz) < 2 or len(biz) > 15 or biz == mod:
                    continue
                domains.append(f"{biz}-{mod}.{self.base_domain}")
                domains.append(f"{mod}-{biz}.{self.base_domain}")

        return domains

    def triplet_hyphen_projection(self):
        """
        动态约束三元复合连字符生成（如 biz-env-idc / biz-idc-env / biz-inner-idc）
        仅使用当前目标已实际探测存活的机房词、环境词与主业务词进行三段式定向交叉
        """
        domains = []
        if not self.base_domain:
            return domains

        modifiers = set()
        environments = set()
        biz_prefixes = set()

        known_envs = {
            "boe", "ppe", "test", "dev", "qa", "uat", "pre", "gray", "canary",
            "stage", "staging", "daily", "bench", "sit", "fat", "inner", "intra"
        }

        for d in self.subdomains:
            d_lower = d.lower().strip()
            if not d_lower.endswith("." + self.base_domain) or d_lower == self.base_domain:
                continue
            sub = d_lower[:- (len(self.base_domain) + 1)]
            parts = sub.split(".")
            for part in parts:
                tokens = part.split("-")
                for t in tokens:
                    t = t.strip()
                    if not t:
                        continue
                    if t in known_envs:
                        environments.add(t)
                    elif len(t) in [2, 3] and not t.isdigit():
                        modifiers.add(t)
                    elif len(t) >= 2 and not t.isdigit():
                        biz_prefixes.add(t)

        core_biz = {"api", "app", "web", "admin", "gw", "auth", "sso", "passport", "open", "m", "h5", "pay", "cs", "yxt", "mct", "saas", "zxt", "lh"}
        biz_prefixes.update(core_biz)

        if not environments:
            environments = {"boe", "ppe", "test", "dev", "gray", "inner"}
        if not modifiers:
            modifiers = {"lq", "hl", "sh", "bj", "sz", "hk"}

        for biz in list(biz_prefixes)[:25]:
            for env in environments:
                for idc in modifiers:
                    if biz in [env, idc] or env == idc:
                        continue
                    # 1. biz-env-idc.base_domain (如 mct-boe-hl, yxt-boe-lq)
                    domains.append(f"{biz}-{env}-{idc}.{self.base_domain}")
                    # 2. biz-idc-env.base_domain (如 mct-hl-boe)
                    domains.append(f"{biz}-{idc}-{env}.{self.base_domain}")
                    # 3. biz.env.idc.base_domain (如 mct.boe.hl)
                    domains.append(f"{biz}.{env}.{idc}.{self.base_domain}")

        return domains

    def run(self):
        seen = set()
        # 1. 目标级跨业务连字符自适应模式投影
        for perm in self.cross_service_hyphen_projection():
            perm_lower = perm.lower().strip()
            if perm_lower and perm_lower not in seen:
                seen.add(perm_lower)
                yield perm_lower

        # 2. 动态约束三元复合投影 (biz-env-idc / biz.env.idc)
        for perm in self.triplet_hyphen_projection():
            perm_lower = perm.lower().strip()
            if perm_lower and perm_lower not in seen:
                seen.add(perm_lower)
                yield perm_lower

        # 3. 单域名层级排列组合
        for domain in set(self.subdomains):
            parts = self.partiate_domain(domain)
            permutations = []
            permutations += self.insert_word_every_index(parts)
            permutations += self.insert_num_every_index(parts)
            permutations += self.prepend_word_every_index(parts)
            permutations += self.append_word_every_index(parts)
            permutations += self.semantic_swap_word(parts)
            permutations += self.replace_word_with_word(parts)

            for perm in permutations:
                perm_lower = perm.lower().strip()
                if perm_lower and perm_lower not in seen:
                    seen.add(perm_lower)
                    yield perm_lower



class AltDNS(object):
    def __init__(self, subdomains, base_domain, words, wildcard_domain_ip=None):
        self.subdomains = subdomains
        self.base_domain = base_domain
        self.words = words
        if wildcard_domain_ip is None:
            wildcard_domain_ip = []
        self.wildcard_domain_ip = wildcard_domain_ip

    def run(self):
        domains = DnsGen(set(self.subdomains), self.words,
                         base_domain=self.base_domain).run()

        logger.info("start AltDNS:{} wildcard_record:{}".format(
            self.base_domain, ",".join(self.wildcard_domain_ip)))

        mass = MassDNS(domains, mass_dns_bin=Config.MASSDNS_BIN,
                       dns_server=Config.DNS_SERVER, tmp_dir=Config.TMP_PATH,
                       wildcard_domain_ip=self.wildcard_domain_ip, concurrent=Config.ALT_DNS_CONCURRENT)

        return mass.run()


def alt_dns(subdomains, base_domain=None, words=None, wildcard_domain_ip=None):
    if len(subdomains) == 0:
        return []

    a = AltDNS(subdomains, base_domain,
               words=words, wildcard_domain_ip=wildcard_domain_ip)
    raw_domains_info = a.run()

    domains_info = []
    records = [x['record'] for x in raw_domains_info]
    records_count = Counter(records)
    for info in raw_domains_info:
        if records_count[info['record']] >= 15:
            continue
        domains_info.append(info)

    return domains_info
