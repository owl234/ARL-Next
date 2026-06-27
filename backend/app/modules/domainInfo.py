from .baseInfo import BaseInfo


class DomainInfo(BaseInfo):
    """
    [第一性原理：领域数据模型 - 域名]
    这是贯穿整个域名扫描生命周期的核心数据结构。
    当我们在 massdns 中爆破出一个域名，或者从接口接收到一个域名时，
    都会实例化这个类。它将域名的基本属性（域名本身、解析记录、解析类型、指向的IP）
    紧紧绑定在一起，确保在整个业务流转中数据的完整性和一致性。
    """
    def __init__(self, domain, record, type, ips):
        """
        初始化域名信息对象。
        :param domain: 字符串，域名本身 (例如: "www.example.com")
        :param record: 列表，解析记录的值 (例如: ["1.1.1.1"] 或 ["cname.example.com"])
        :param type: 字符串，DNS解析类型 (例如: "A", "CNAME")
        :param ips: 列表，最终解析到的 IPv4/IPv6 地址列表。如果是 A 记录，通常和 record 一致。
        """
        self.record_list = record
        self.domain = domain
        self.type = type
        self.ip_list = ips

    def __eq__(self, other):
        """
        【集合去重第一性原理：判等逻辑】
        在扫描过程中，很可能会通过不同的渠道（字典爆破、搜索引擎、网页爬取）
        多次发现同一个域名。
        重写 __eq__ 方法，告诉 Python：只要两个 DomainInfo 对象的 domain 字符串相同，
        它们就是同一个对象。这在做列表去重时非常关键。
        """
        if isinstance(other, DomainInfo):
            if self.domain == other.domain:
                return True

    def __hash__(self):
        """
        【集合去重第一性原理：哈希散列】
        要让对象能被放进 set() (集合) 里进行极速去重，就必须实现 __hash__ 方法。
        这里直接返回 domain 字符串的哈希值，配合 __eq__，
        完美实现了 `list(set(domain_info_list))` 的极速去重。
        """
        return hash(self.domain)

    def _dump_json(self):
        """
        履行基类 BaseInfo 的契约：
        将类属性打包成可以直接插入 MongoDB 的字典格式。
        """
        item = {
            "domain": self.domain,
            "record": self.record_list,
            "type": self.type,
            "ips": self.ip_list
        }
        return item