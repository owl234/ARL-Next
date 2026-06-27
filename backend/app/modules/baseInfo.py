import json


class BaseInfo:
    """
    [第一性原理：对象的标准化输出]
    这是 ARL 系统中所有核心数据实体的【基类】。
    无论是域名信息 (DomainInfo)、IP信息 (IpInfo) 还是其他扫描结果，都必须继承这个类。
    它的唯一目的是：提供统一的“序列化”接口，把复杂的 Python 对象一键转换成 JSON 格式，
    方便后续直接存入 MongoDB 数据库，或者通过 API 返回给前端。
    """
    
    def __str__(self):
        """
        魔术方法：当使用 print(obj) 打印这个对象时，会自动调用 dump_json() 输出 JSON 字符串。
        方便在控制台调试时直观地看到对象内容。
        """
        return self.dump_json()

    def __repr__(self):
        """
        魔术方法：在交互式解释器中直接输入变量名回车，或在日志中记录时，输出其 JSON 字符串格式。
        """
        return self.dump_json()

    def dump_json(self, flag = True):
        """
        序列化调度方法：将当前对象转化为字典或 JSON 字符串。
        
        :param flag: 布尔值。如果为 True，返回 JSON 格式的字符串（用于网络传输或日志记录）。
                     如果为 False，返回 Python 字典对象（用于插入 MongoDB 数据库）。
        :return: JSON 字符串 或 Python 字典
        """
        item = self._dump_json()
        if flag:
            return json.dumps(item)
        else:
            return item

    def _dump_json(self):
        """
        【契约方法/抽象方法】
        基类不实现具体的转换逻辑，而是强制要求所有继承它的子类（如 DomainInfo）
        必须重写（Override）这个方法，将自己的属性打包成一个字典并返回。
        如果子类忘记重写，就会抛出 NotImplementedError 异常。
        """
        raise NotImplementedError()