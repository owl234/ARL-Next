

HIGH_RISK_TYPES = {
    "secret_key", "access_key", "access_token", "wechat_corpid", "wechat_appid",
    "jwt", "ak_sk", "password", "private_key", "api_key", "aliyun_ak", "tencent_ak",
    "aws_ak", "ssh_key", "token", "app_secret", "corp_secret"
}
MEDIUM_RISK_TYPES = {
    "api_path", "api_route", "internal_ip", "id_card", "phone", "auth_url", "internal_domain"
}


class WihRecord:
    """
    [第一性原理：领域数据模型 - Web Info Hunter (信息泄露)]
    这与其他实体不同，它没有继承 BaseInfo，但自己实现了序列化方法。
    WihRecord 用于记录在前端 JS 代码中匹配到的“敏感信息”（如 AccessKey, 身份证号、隐藏API接口）。
    """
    def __init__(self, record_type, content, source, site, fnv_hash):
        self.recordType = record_type # 泄露的数据类型 (比如: "aliyun_ak", "id_card", "api_path")
        self.content = content        # 具体泄露的真实内容 (比如: "LTAI5t...xxx")
        self.source = source          # 证据来源，即是从哪个 JS 文件或页面发现的
        self.site = site              # 所属的站点 (比如: https://www.example.com)
        # [强制类型约束] 实例化时即转为字符串，保证全局哈希一致性，彻底阻断大整型溢出及下游兼容性风险
        self.fnv_hash = str(fnv_hash) if fnv_hash else ""

    @property
    def risk_level(self):
        rtype = str(self.recordType).lower()
        if rtype in HIGH_RISK_TYPES or any(k in rtype for k in ["secret", "token", "appid", "corpid", "key", "jwt", "pass"]):
            return "CRITICAL"
        elif rtype in MEDIUM_RISK_TYPES or any(k in rtype for k in ["api", "ip", "auth"]):
            return "MEDIUM"
        return "LOW"

    def __str__(self):
        return "[{}] {} {} {} {}".format(self.risk_level, self.recordType, self.content, self.source, self.site)

    def __repr__(self):
        return "<WihRecord>" + self.__str__()

    def __eq__(self, other):
        """
        【强去重校验】
        结合 fnv_hash 与 site。
        避免跨域（不同子域名）发生相同文件（如 app.js）泄露时，被错误地全局去重，导致安全团队遗漏受影响站点。
        """
        return self.fnv_hash == other.fnv_hash and self.site == other.site

    def __hash__(self):
        return hash((self.fnv_hash, self.site))

    def dump_json(self):
        """
        自定义的序列化输出，直接给入库使用。
        注意：fnv_hash 在实例化时已转为了 string，因为 MongoDB 对于超大数字处理有时会有兼容性问题。
        """
        return {
            "record_type": self.recordType,
            "content": self.content,
            "site": self.site,
            "source": self.source,
            "fnv_hash": self.fnv_hash,
            "risk_level": self.risk_level
        }