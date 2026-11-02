import os
import re

try:
    import geoip2.database
except Exception:
    geoip2 = None

from app.config import Config
from .IPy import IP
from .xdb_searcher import XdbSearcher
from .geo_pinyin import parse_ip2region_record


def is_vaild_ip_target(ip):
    if re.match(
            r"^\d+\.\d+\.\d+\.\d+$|^\d+\.\d+\.\d+\.\d+/\d+$|^\d+\.\d+\.\d+.\d+-\d+$", ip):
        return True
    else:
        return False


def is_v4_ip(ip_str):
    import ipaddress
    try:
        return isinstance(ipaddress.ip_address(str(ip_str).strip("[]")), ipaddress.IPv4Address)
    except (ValueError, TypeError):
        return False


def is_v6_ip(ip_str):
    import ipaddress
    try:
        return isinstance(ipaddress.ip_address(str(ip_str).strip("[]")), ipaddress.IPv6Address)
    except (ValueError, TypeError):
        return False


def transfer_ip_scope(target):
    """
    将目标IP,IP段转换为合法的CIDR表示方法
    """
    from . import get_logger
    logger = get_logger()

    try:
        return IP(target, make_net=True).strNormal(1)
    except Exception as e:
        logger.warn("error on ip_scope {} {}".format(target, e))


def not_in_black_ips(target):
    """Reject any overlap with a blocked network, including ranges and CIDRs."""
    import ipaddress
    from . import get_logger
    from app.utils.security_policy import get_security_policy
    logger = get_logger()

    def interval(value):
        value = str(value).strip()
        if '-' in value:
            first, last = value.split('-', 1)
            start = ipaddress.ip_address(first)
            if start.version == 4 and last.isdigit():
                last = first.rsplit('.', 1)[0] + '.' + last
            end = ipaddress.ip_address(last)
            if start.version != end.version or int(start) > int(end):
                raise ValueError('Invalid IP range')
            return start.version, int(start), int(end)
        if '/' in value:
            network = ipaddress.ip_network(value, strict=False)
            return network.version, int(network.network_address), int(network.broadcast_address)
        address = ipaddress.ip_address(value)
        if getattr(address, 'ipv4_mapped', None):
            address = address.ipv4_mapped
        return address.version, int(address), int(address)

    try:
        black_ips, _ = get_security_policy()
        version, first, last = interval(target)
        for blocked in black_ips:
            try:
                blocked_version, blocked_first, blocked_last = interval(blocked)
            except Exception as be:
                logger.warning("invalid black_ips entry {}: {}".format(blocked, be))
                continue
            if version == blocked_version and first <= blocked_last and blocked_first <= last:
                return False
    except Exception as e:
        logger.warning("error on check black ip {} {}".format(target, e))
        return False

    return True


import threading

_asn_reader = None
_city_reader = None
_xdb_searcher = None

_asn_lock = threading.Lock()
_city_lock = threading.Lock()
_xdb_lock = threading.Lock()


def _resolve_db_path(configured_path, default_filename):
    """
    智能解析数据库路径：
    1. 优先使用配置文件中的绝对路径（如容器内 /code/backend/GeoLite2/...）
    2. 若文件不存在，自动尝试本地仓库中的相对路径 (../GeoLite2/...)，保证宿主机与容器内外均可运行
    """
    if configured_path and os.path.isfile(configured_path):
        return configured_path

    curr_dir = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        os.path.join(curr_dir, "../../GeoLite2", default_filename),
        os.path.join(os.getcwd(), "backend/GeoLite2", default_filename),
        os.path.join(os.getcwd(), "GeoLite2", default_filename),
        os.path.join("/code/backend/GeoLite2", default_filename),
        os.path.join("/code/GeoLite2", default_filename),
        os.path.join("/data/GeoLite2", default_filename),
    ]
    for p in candidates:
        if os.path.isfile(p):
            return p

    return None


def _get_asn_reader():
    global _asn_reader
    if _asn_reader is None:
        with _asn_lock:
            if _asn_reader is None:
                if geoip2 is None:
                    _asn_reader = False
                    return None
                db_path = _resolve_db_path(Config.GEOIP_ASN, "GeoLite2-ASN.mmdb")
                if db_path:
                    try:
                        _asn_reader = geoip2.database.Reader(db_path)
                    except Exception:
                        _asn_reader = False
                else:
                    _asn_reader = False
    return _asn_reader if _asn_reader is not False else None


def _get_city_reader():
    global _city_reader
    if _city_reader is None:
        with _city_lock:
            if _city_reader is None:
                if geoip2 is None:
                    _city_reader = False
                    return None
                db_path = _resolve_db_path(Config.GEOIP_CITY, "GeoLite2-City.mmdb")
                if db_path:
                    try:
                        _city_reader = geoip2.database.Reader(db_path)
                    except Exception:
                        _city_reader = False
                else:
                    _city_reader = False
    return _city_reader if _city_reader is not False else None


def _get_xdb_searcher():
    global _xdb_searcher
    if _xdb_searcher is None:
        with _xdb_lock:
            if _xdb_searcher is None:
                configured = getattr(Config, "GEOIP_IP2REGION", "")
                db_path = _resolve_db_path(configured, "ip2region_v4.xdb")
                if db_path:
                    try:
                        _xdb_searcher = XdbSearcher.load_from_file(db_path)
                    except Exception:
                        _xdb_searcher = False
                else:
                    _xdb_searcher = False
    return _xdb_searcher if _xdb_searcher is not False else None


def get_ip_asn(ip):
    from . import get_logger
    logger = get_logger()
    item = {}
    try:
        reader = _get_asn_reader()
        if reader:
            response = reader.asn(ip)
            item["number"] = response.autonomous_system_number
            item["organization"] = response.autonomous_system_organization
    except Exception as e:
        logger.debug("{} {}".format(e, ip))

    # 若 MaxMind 未能解析出 organization，尝试从 ip2region 获取 ISP 补充
    if not item.get("organization"):
        try:
            xdb = _get_xdb_searcher()
            if xdb:
                raw_info = xdb.search(ip)
                if raw_info:
                    parsed = parse_ip2region_record(raw_info)
                    if parsed.get("isp"):
                        item["organization"] = parsed["isp"]
        except Exception as e:
            logger.debug("xdb asn fallback error: {} {}".format(e, ip))

    return item


def get_ip_city(ip):
    from . import get_logger
    logger = get_logger()
    geo_data = {}

    # 1. 尝试从 MaxMind GeoLite2 获取国际信息与基础经纬度
    try:
        reader = _get_city_reader()
        if reader:
            response = reader.city(ip)
            geo_data = {
                "city": response.city.name,
                "latitude": response.location.latitude,
                "longitude": response.location.longitude,
                "country_name": response.country.name,
                "country_code": response.country.iso_code,
                "region_name": response.subdivisions.most_specific.name,
                "region_code": response.subdivisions.most_specific.iso_code,
            }
    except Exception as e:
        logger.debug("GeoLite2 lookup exception: {} {}".format(e, ip))

    # 2. 尝试从 ip2region 获取高精度国内省份、城市与 ISP
    xdb_geo = {}
    try:
        xdb = _get_xdb_searcher()
        if xdb:
            raw_str = xdb.search(ip)
            if raw_str:
                xdb_geo = parse_ip2region_record(raw_str)
    except Exception as e:
        logger.debug("xdb lookup exception: {} {}".format(e, ip))

    # 3. 双轨结果深度融合 (Dual-Track Graceful Fusion)
    if not geo_data and not xdb_geo:
        return {}

    if not geo_data:
        # GeoLite2 缺失时完全采用 xdb_geo
        return {
            "city": xdb_geo.get("city"),
            "latitude": None,
            "longitude": None,
            "country_name": xdb_geo.get("country_name"),
            "country_code": xdb_geo.get("country_code"),
            "region_name": xdb_geo.get("region_name"),
            "region_code": xdb_geo.get("region_code"),
            "isp": xdb_geo.get("isp"),
        }

    if not xdb_geo:
        # xdb 缺失时采用 geo_data
        return geo_data

    # 两者均存在时进行智能融合：
    # 中国境内 IP 优先使用 ip2region 的省份、城市及国别信息，保留 GeoLite2 的经纬度
    if xdb_geo.get("country_code") == "CN":
        geo_data["country_name"] = "China"
        geo_data["country_code"] = "CN"
        if xdb_geo.get("region_name"):
            geo_data["region_name"] = xdb_geo["region_name"]
        if xdb_geo.get("region_code"):
            geo_data["region_code"] = xdb_geo["region_code"]
        if xdb_geo.get("city"):
            geo_data["city"] = xdb_geo["city"]
        if xdb_geo.get("isp"):
            geo_data["isp"] = xdb_geo["isp"]
    else:
        # 海外 IP：以 GeoLite2 为准，若缺少 city/region 则由 xdb 补充
        if not geo_data.get("city") and xdb_geo.get("city"):
            geo_data["city"] = xdb_geo["city"]
        if not geo_data.get("region_name") and xdb_geo.get("region_name"):
            geo_data["region_name"] = xdb_geo["region_name"]
        if xdb_geo.get("isp"):
            geo_data["isp"] = xdb_geo["isp"]

    return geo_data


def get_ip_type(ip):
    from . import get_logger
    logger = get_logger()
    try:
        # 国内好多企业把这两个段当成内网域名
        if ip.startswith("9.") or ip.startswith("11."):
            return "PRIVATE"

        ip_type = IP(ip).iptype()

        # 为了方便全部设置为 PRIVATE
        if ip_type in ["CARRIER_GRADE_NAT", "LOOPBACK", "RESERVED"]:
            return "PRIVATE"

        return ip_type

    except Exception as e:
        logger.warning("{} {}".format(e, ip))
        return "ERROR"


def ip_in_scope(ip, scope_list):
    from . import get_logger
    logger = get_logger()

    for item in scope_list:
        try:
            if IP(ip) in IP(item):
                return True
        except Exception as e:
            logger.warning("{} {} {}".format(e, ip, item))

