from xing.core.BasePlugin import BasePlugin
from xing.utils import http_req
from xing.core import PluginType, SchemeType


class Plugin(BasePlugin):
    def __init__(self):
        super(Plugin, self).__init__()
        self.plugin_type = PluginType.POC
        self.vul_name = "Kubelet API 未授权访问"
        self.app_name = 'Kubelet'
        self.scheme = [SchemeType.HTTPS, SchemeType.HTTP]
        self.severity = "Critical"
        self.description = "Kubernetes Kubelet API 未开启鉴权认证（常见于 10250/10255 端口），未经身份认证的攻击者可通过 API 端点直接列出节点运行的全部 Pod 容器详情，甚至执行命令接管节点。"
        self.remediation = "在 Kubelet 配置文件或启动参数中设置 --anonymous-auth=false 禁用匿名访问，并将 --authorization-mode 设置为 Webhook 或配置严格的双向 TLS 证书认证。"
        self.references = ["https://kubernetes.io/docs/reference/command-line-tools-reference/kubelet-authentication-authorization/"]

    def verify(self, target):
        paths = ["/pods", "/runningpods/"]
        for path in paths:
            url = target + path
            try:
                conn = http_req(url)
            except Exception:
                continue

            if not conn or not conn.ok:
                continue

            content = conn.content
            if b"<html" in content.lower():
                continue

            # 严格特征校验：必须命中 PodList，或者在包含 items+metadata 基础上必须同时具备 apiVersion 与容器规范（containers/spec），杜绝泛 REST API 误报
            is_pod_list = b'"kind":"PodList"' in content or b'"kind": "PodList"' in content
            is_k8s_items = (b'"items"' in content and b'"metadata"' in content and b'"apiVersion"' in content
                            and (b'"containers"' in content or b'"spec"' in content))

            if is_pod_list or is_k8s_items:
                self.logger.success("发现 Kubelet API 未授权访问 {}".format(self.target))
                return url

        return False
