import re
import ipaddress
import tld
from app.config import Config

blackdomain_list = None
blackhexie_list = None


def check_domain_black(domain):
    from app.utils import get_logger
    logger = get_logger()

    global blackdomain_list
    global blackhexie_list
    if blackdomain_list is None:
        with open(Config.black_domain_path) as f:
            blackdomain_list = f.readlines()

    for item in blackdomain_list:
        item = item.strip()
        if item and (domain == item or domain.endswith("." + item)):
            return True

    if blackhexie_list is None:
        with open(Config.black_hexie_path) as f:
            blackhexie_list = f.readlines()

    try:
        for item in blackhexie_list:
            item = item.strip()
            _, _, subdomain = tld.parse_tld(domain, fix_protocol=True, fail_silently=True)
            if subdomain and item and item.strip() in subdomain:
                return True
    except Exception as e:
        logger.warning("Error on: {}, {}".format(domain, e))
        return False

    return False


def is_forbidden_domain(domain):
    from app.utils.security_policy import get_security_policy
    _, forbidden_domains = get_security_policy()
    
    for f_domain in forbidden_domains:
        if not f_domain:
            continue
            
        if domain.endswith("." + f_domain):
            return True
        if domain == f_domain:
            return True

    return False


def is_valid_domain(domain):
    from app.utils import domain_parsed
    if "." not in domain:
        return False

    invalid_chars = "!@#$%&*():_\\"
    for c in invalid_chars:
        if c in domain:
            return False

    # 不允许下发特殊二级域名
    if domain in ["com.cn", "gov.cn", "edu.cn"]:
        return False

    if domain_parsed(domain):
        return True

    return False


def is_valid_fuzz_domain(domain):
    from app.utils import domain_parsed
    if "{fuzz}" not in domain:
        return False

    domain = domain.replace("{fuzz}", "12fuzz12")
    parsed = domain_parsed(domain)
    if not parsed:
        return False

    if "12fuzz12" in parsed['fld']:
        return False

    return True


def is_in_scope(src_domain, target_domain):
    from app.utils import get_fld

    fld1 = get_fld(src_domain)
    fld2 = get_fld(target_domain)

    if not fld1 or not fld2:
        return False

    if fld1 != fld2:
        return False

    if src_domain == target_domain:
        return True

    return src_domain.endswith("."+target_domain)


def is_in_scopes(domain, scopes):
    for target_scope in scopes:
        if is_in_scope(domain, target_scope):
            return True

    return False


def cut_first_name(domain):
    """将子域名剔除前面一节名称"""
    domain_parts, non_zero_i, _ = tld.utils.process_url(domain, fix_protocol=True, fail_silently=True)
    if not domain_parts:
        return

    if non_zero_i == 1:
        return

    item = ".".join(domain_parts[1:])
    return item


def extract_dynamic_ip_from_domain(domain: str):
    """
    从子域名中提取潜在的 IPv4 结构。
    支持格式：
      - 117-187-206-224.example.com
      - 117_187_206_224.example.com
      - node-117-187-206-224.example.com
      - ip-117-187-206-224.example.com
      - edge-117-187-206-224.example.com
    返回标准的 IPv4 字符串，若无则返回 None
    """
    if not domain or not isinstance(domain, str):
        return None
        
    pattern = r'(?:^|[._-])(?:(?:node|ip|edge|host|server|cdn|pcdn)[._-])?(\d{1,3})[-_.](\d{1,3})[-_.](\d{1,3})[-_.](\d{1,3})(?:[._-]|$)'
    m = re.search(pattern, domain.lower())
    if not m:
        return None
        
    try:
        octets = [int(g) for g in m.groups()]
        if all(0 <= o <= 255 for o in octets):
            return '.'.join(map(str, octets))
    except Exception:
        pass
    return None


def is_private_or_reserved_ip(ip_str: str) -> bool:
    """判断是否为 RFC1918 私网/回环/保留 IP（这些 IP 坚决不视为 CDN 噪音，予以豁免保留）"""
    try:
        ip_obj = ipaddress.ip_address(ip_str)
        return ip_obj.is_private or ip_obj.is_loopback or ip_obj.is_reserved or ip_obj.is_link_local
    except Exception:
        return False


def is_dynamic_ip_edge_domain(domain: str, resolved_ips=None, strict_dns: bool = True) -> bool:
    """
    双重自指校验：
    1. 域名中提取出有效 IPv4
    2. 该 IP 属于公网 IP（非内网私有 IP，RFC1918 豁免）
    3. 如果提供了 resolved_ips，则要求 extracted_ip 必须存在于 resolved_ips 中（100% 确定性）
    4. 若未提供 resolved_ips 且 strict_dns=True，则保持保守策略返回 False，避免无 DNS 解析下的静态误判
    """
    extracted_ip = extract_dynamic_ip_from_domain(domain)
    if not extracted_ip:
        return False
        
    # RFC 1918 私网 IP 豁免保护（内网资产极高价值，绝不拦截）
    if is_private_or_reserved_ip(extracted_ip):
        return False
        
    # 如果有 DNS 解析结果，必须严格自指匹配
    if resolved_ips is not None:
        if isinstance(resolved_ips, (list, set, tuple)):
            return extracted_ip in resolved_ips
        elif isinstance(resolved_ips, str):
            return extracted_ip == resolved_ips
    elif strict_dns:
        return False
            
    return True

