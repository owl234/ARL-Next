

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
        self.fnv_hash = fnv_hash      # 唯一身份标识 (使用 FNV 算法生成的哈希值，防止完全相同的数据重复插入)

    def __str__(self):
        return "{} {} {} {}".format(self.recordType, self.content, self.source, self.site)

    def __repr__(self):
        return "<WihRecord>" + self.__str__()

    def __eq__(self, other):
        """
        【强去重校验】
        通过比对预先生成的 fnv_hash。只要类型、内容、来源都一样，哈希就一样。
        极大避免了多台分布式扫描器跑到了同一个 JS 文件导致数据库被相同泄露数据撑爆的问题。
        """
        return self.fnv_hash == other.fnv_hash

    def __hash__(self):
        return self.fnv_hash

    def dump_json(self):
        """
        自定义的序列化输出，直接给入库使用。
        注意：fnv_hash 被转成了 string，因为 MongoDB 对于超大数字处理有时会有兼容性问题。
        """
        return {
            "record_type": self.recordType,
            "content": self.content,
            "site": self.site,
            "source": self.source,
            "fnv_hash": str(self.fnv_hash),
        }