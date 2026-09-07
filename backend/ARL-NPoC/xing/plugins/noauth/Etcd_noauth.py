from xing.core.BasePlugin import BasePlugin
from xing.utils import http_req
from xing.core import PluginType, SchemeType


class Plugin(BasePlugin):
    def __init__(self):
        super(Plugin, self).__init__()
        self.plugin_type = PluginType.POC
        self.vul_name = "etcd 未授权访问"
        self.app_name = 'etcd'
        self.scheme = [SchemeType.HTTPS, SchemeType.HTTP]
        self.severity = "Critical"
        self.description = "etcd 分布式键值存储服务未开启身份认证（默认端口 2379），攻击者可通过 HTTP REST API 或 gRPC-Gateway 直接读取甚至篡改集群核心键值数据、配置信息及密钥凭据。"
        self.remediation = "通过 etcdctl user add 和 etcdctl auth enable 启用用户鉴权；并在生产环境中强制启用 TLS 双向证书认证（--client-cert-auth=true），限制仅集群受信任节点可访问 2379 端口。"
        self.references = ["https://etcd.io/docs/latest/op-guide/authentication/"]

    def verify(self, target):
        # /version 为 etcd 公开端点，仅用于确认目标确为 etcd，不单独构成未授权命中
        try:
            conn = http_req(target + "/version")
        except Exception:
            return False
        if not conn.ok:
            return False
        content = conn.content
        if b"<html" in content.lower():
            return False
        if b'"etcdserver"' not in content or b'"etcdcluster"' not in content:
            return False

        # 数据端点鉴权探针：未开启鉴权时返回 200 与真实数据，开启鉴权时返回 401
        probes = [
            ("/v2/keys", "get", None),
            ("/v3/kv/range", "post", {"key": "Lw=="}),
        ]
        for path, method, data in probes:
            try:
                if method == "post":
                    conn = http_req(target + path, method="post", json=data)
                else:
                    conn = http_req(target + path)
            except Exception:
                continue
            if not conn.ok:
                continue
            resp = conn.content
            if b"<html" in resp.lower():
                continue
            if b'"action":"get"' in resp or b'"node":{' in resp or b'"kvs"' in resp or (b'"header":{' in resp and (b'"cluster_id"' in resp or b'"revision"' in resp)):
                self.logger.success("发现 etcd 未授权访问 {}".format(self.target))
                return target + path

        return False
