import threading
from app import utils
from app.modules import DomainInfo
from .baseThread import BaseThread
logger = utils.get_logger()


class ResolverDomain(BaseThread):
    def __init__(self, domains, concurrency=6, pre_resolved=None):
        super().__init__(domains, concurrency=concurrency)
        self.resolver_map = {}
        self.pre_resolved = {}
        self._lock = threading.Lock()
        self.transient_failures = 0

        if isinstance(pre_resolved, dict):
            for dom, ips in pre_resolved.items():
                if not dom:
                    continue
                dom_key = str(dom).strip().strip(".").lower()
                if isinstance(ips, dict):
                    ips = ips.get("ips") or []
                clean_ips = [ip for ip in (ips or []) if ip and ip != "0.0.0.1"]
                if clean_ips:
                    self.pre_resolved[dom_key] = clean_ips

    '''
    {
        "api.baike.baidu.com":[
            "180.97.93.62",
            "180.97.93.61"
        ],
        "apollo.baidu.com":[
            "123.125.115.15"
        ],
        "www.baidu.com":[
            "180.101.49.12",
            "180.101.49.11"
        ]
    }
    '''
    def work(self, domain):
        curr_domain = domain
        if isinstance(domain, dict):
            curr_domain = domain.get("domain")

        elif isinstance(domain, DomainInfo):
            curr_domain = domain.domain

        if not curr_domain:
            return

        curr_domain = str(curr_domain).strip()
        dom_key = curr_domain.strip(".").lower()

        with self._lock:
            if curr_domain in self.resolver_map:
                return

        cached_ips = self.pre_resolved.get(dom_key)
        if cached_ips:
            with self._lock:
                self.resolver_map[curr_domain] = list(cached_ips)
            return

        ips, transient_failed = utils.get_ip_with_status(curr_domain)
        with self._lock:
            self.resolver_map[curr_domain] = ips
            if transient_failed:
                self.transient_failures += 1

    def run(self):
        pending_targets = []
        for domain in self.targets:
            curr_domain = domain
            if isinstance(domain, dict):
                curr_domain = domain.get("domain")
            elif isinstance(domain, DomainInfo):
                curr_domain = domain.domain
            if not curr_domain:
                continue
            curr_domain = str(curr_domain).strip()
            cached_ips = self.pre_resolved.get(curr_domain.strip(".").lower())
            if cached_ips:
                self.resolver_map[curr_domain] = list(cached_ips)
            else:
                pending_targets.append(domain)

        self.targets = pending_targets
        if self.targets:
            self._run()
        if self.transient_failures > 0:
            logger.warning(
                "ResolverDomain completed with %d transient DNS failures out of %d pending domains",
                self.transient_failures,
                len(self.targets),
            )
        return self.resolver_map


def resolver_domain(domains, concurrency=15, pre_resolved=None):
    r = ResolverDomain(domains, concurrency, pre_resolved=pre_resolved)
    return r.run()
