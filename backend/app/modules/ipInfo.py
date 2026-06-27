from .baseInfo import BaseInfo
from app import utils


class IPInfo(BaseInfo):
    """
    [第一性原理：领域数据模型 - IP 资产]
    这是比 DomainInfo 更重型的“货车”。
    在网络空间测绘中，一个 IP 是最基础的物理节点。它不仅包含它本身，还挂载着：
    1. 开放了哪些端口 (PortInfo)
    2. 运行着什么操作系统 (OSInfo)
    3. 它的地理位置 (ASN, City)
    4. 它的网络属性 (是否属于 CDN, 公网还是内网)
    """
    def __init__(self, ip, port_info, os_info, domain, cdn_name):
        self.ip = ip
        self.port_info_list = port_info # 包含了一堆 PortInfo 对象的列表
        self.os_info = os_info          # Nmap 探测出的操作系统指纹字典
        self.domain = domain            # 如果是从域名解析来的，记录关联的域名
        self._geo_asn = None            # 懒加载：地理自治系统号 (ASN)
        self._geo_city = None           # 懒加载：地理城市
        self._ip_type = None            # 懒加载：IP 类型 (PUBLIC 公网 / PRIVATE 内网)
        self.cdn_name = cdn_name        # 如果被识别为 CDN，记录 CDN 厂商名称

    @property
    def geo_asn(self):
        """
        【第一性原理：延迟计算/懒加载 (Lazy Evaluation)】
        网络空间测绘中，IP 数量巨大。如果我们在实例化时就去查本地 GeoIP 数据库，
        会极大地拖慢端口扫描等底层操作的速度。
        使用 @property，只有在最终入库前，真正访问 `obj.geo_asn` 时，才会触发查询计算。
        且计算过一次后，缓存在 `_geo_asn` 中，避免重复查询。
        """
        if self._geo_asn:
            return self._geo_asn

        else:
            if self.ip_type == "PUBLIC":
                self._geo_asn = utils.get_ip_asn(self.ip)
            else:
                self._geo_asn = {}

        return self._geo_asn

    @property
    def geo_city(self):
        """懒加载获取城市信息，逻辑同 geo_asn"""
        if self._geo_city:
            return self._geo_city

        else:
            if self.ip_type == "PUBLIC":
                self._geo_city = utils.get_ip_city(self.ip)
            else:
                self._geo_city = {}

        return self._geo_city

    @property
    def ip_type(self):
        """懒加载判断内外网"""
        if self._ip_type:
            return self._ip_type

        else:
            self._ip_type = utils.get_ip_type(self.ip)

        return self._ip_type

    def __eq__(self, other):
        """【集合去重】基于 IP 字符串的判等"""
        if isinstance(other, IPInfo):
            if self.ip == other.ip:
                return True

    def __hash__(self):
        """【集合去重】配合 __eq__ 实现基于 set() 的极速去重"""
        return hash(self.ip)

    def _dump_json(self):
        """
        将当前复杂的 IPInfo 及内部嵌套的 PortInfo 统一序列化，
        打平后返回一个干净的字典，直接塞入 MongoDB。
        """
        port_info = []
        # 注意：这里递归调用了内部 PortInfo 的 dump_json
        for x in self.port_info_list:
            port_info.append(x.dump_json(flag=False))

        item = {
            "ip": self.ip,
            "domain": self.domain,
            "port_info": port_info,
            "os_info": self.os_info,
            "ip_type": self.ip_type,
            "geo_asn": self.geo_asn,  # 触发懒加载计算
            "geo_city": self.geo_city,# 触发懒加载计算
            "cdn_name": self.cdn_name
        }
        return item


class PortInfo(BaseInfo):
    """
    [第一性原理：领域数据模型 - 端口服务]
    挂载在 IP 实体下的子模块。
    记录了 Nmap 扫描出来的一个端口的具体服务信息（如 HTTP, MySQL, SSH）。
    """
    def __init__(self, port_id, service_name = "", version = "", protocol = "tcp", product=""):
        self.port_id = port_id          # 端口号 (如: 80, 443)
        self.service_name = service_name# 服务名称 (如: http, ssh)
        self.version = version          # 服务版本号 (如: 1.18.0)
        self.protocol = protocol        # 协议类型 (tcp/udp)
        self.product = product          # 具体的产品名 (如: nginx)

    def __eq__(self, other):
        """
        【去重】基于 port_id (端口号)。
        因为在同一个 IP 下，端口号必定是唯一的。
        """
        if isinstance(other, PortInfo):
            if self.port_id == other.port_id:
                return True

    def __hash__(self):
        return hash(self.port_id)


    def _dump_json(self):
        item = {
            "port_id": self.port_id,
            "service_name": self.service_name,
            "version": self.version,
            "protocol": self.protocol,
            "product": self.product
        }
        return item
