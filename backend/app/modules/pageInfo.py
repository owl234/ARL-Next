from .baseInfo import BaseInfo

class PageInfo(BaseInfo):
    """
    [第一性原理：领域数据模型 - Web 站点快照]
    代表爬虫或指纹识别引擎访问一个 URL 后，拿到的最核心元数据。
    它主要用于记录并展示站点存活状态，是资产面板中“站点”那一栏的数据骨架。
    """
    def __init__(self, title, url, content_length, status_code):
        self.title = title                 # 网页的 <title> 标签内容
        self.url = url                     # 访问的完整 URL (包含 http/https)
        self.content_length = content_length # 网页返回报文的体积大小 (可用于相似度对比)
        self.status_code = status_code     # HTTP 状态码 (200, 302, 404 等)

    def __eq__(self, other):
        """【集合去重】不同的请求如果访问了相同的 URL，就当做重复数据剔除"""
        if isinstance(other, PageInfo):
            if self.url == other.url:
                return True

    def __hash__(self):
        return hash(self.url)

    def _dump_json(self):
        item = {
            "title": self.title,
            "url": self.url,
            "content_length": self.content_length,
            "status_code": self.status_code
        }
        return item