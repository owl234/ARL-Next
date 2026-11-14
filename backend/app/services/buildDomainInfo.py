import time
import threading
from app import modules
from app import utils
from .baseThread import BaseThread
logger = utils.get_logger()


class BuildDomainInfo(BaseThread):
    def __init__(self, domains, concurrency=6, pre_resolved=None):
        super().__init__(domains, concurrency=concurrency)
        self.domain_info_list = []
        self.pre_resolved = {}
        self._lock = threading.Lock()
        self.transient_failures = 0

        if isinstance(pre_resolved, dict):
            for dom, entry in pre_resolved.items():
                if not dom or not isinstance(entry, dict):
                    continue
                self.pre_resolved[str(dom).strip().strip(".").lower()] = entry

    def work(self, target):
        domain = target
        if hasattr(target, "domain"):
            domain = target.domain

        dom_key = (domain or "").strip().strip(".").lower()
        cached = self.pre_resolved.get(dom_key) if dom_key else None

        ips = list(cached.get("ips") or []) if cached else []
        if not ips:
            ips, transient_failed = utils.get_ip_with_status(domain, log_flag=False)
            if transient_failed:
                with self._lock:
                    self.transient_failures += 1
        if not ips:
            return

        # 🛡️ 方案 4：智能拦截动态自指 CDN 边缘基础设施节点 (0 误杀)
        if utils.is_dynamic_ip_edge_domain(domain, resolved_ips=ips):
            return

        if cached and cached.get("cnames"):
            cnames = list(cached["cnames"])
        else:
            cnames = utils.get_cname(domain, False)

        info = {
            "domain": domain,
            "type": "A",
            "record": ips,
            "ips": ips
        }

        if cnames:
            info["type"] = 'CNAME'
            info["record"] = cnames

        with self._lock:
            self.domain_info_list.append(modules.DomainInfo(**info))

    def run(self):
        t1 = time.time()
        logger.info("start build Domain info {}".format(len(self.targets)))
        self._run()
        elapse = time.time() - t1
        if self.transient_failures > 0:
            logger.warning(
                "build Domain info finished with %d transient DNS failures",
                self.transient_failures,
            )
        logger.info("end build Domain info {} elapse {}".format(len(self.domain_info_list), elapse))

        return self.domain_info_list


def build_domain_info(domains, concurrency=15, pre_resolved=None):
    p = BuildDomainInfo(domains, concurrency=concurrency, pre_resolved=pre_resolved)
    return p.run()
