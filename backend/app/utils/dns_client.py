import os
import threading
import time
import dns.exception
import dns.resolver

_CACHE_LOCK = threading.Lock()
_DNS_SERVER_CACHE = {"path": None, "mtime": None, "servers": ()}
_RR_LOCK = threading.Lock()
_RR_CURSOR = 0

_TRANSIENT_ERRORS = (
    dns.exception.Timeout,
    dns.resolver.LifetimeTimeout,
    dns.resolver.NoNameservers,
    dns.exception.DNSException,
    OSError,
)


def _load_dns_servers(dns_server_path=None):
    """按文件 mtime 缓存加载上游公共 DNS 服务器列表，规避 Docker 内置 127.0.0.11 串行拥塞。"""
    if dns_server_path is None:
        try:
            from app.config import Config
            dns_server_path = getattr(Config, "DNS_SERVER", None)
        except Exception:
            dns_server_path = None

    if not dns_server_path or not os.path.isfile(dns_server_path):
        return ()

    try:
        mtime = os.path.getmtime(dns_server_path)
    except OSError:
        return ()

    with _CACHE_LOCK:
        if (
            _DNS_SERVER_CACHE["path"] == dns_server_path
            and _DNS_SERVER_CACHE["mtime"] == mtime
        ):
            return _DNS_SERVER_CACHE["servers"]

        servers = []
        try:
            with open(dns_server_path, "r", encoding="utf-8", errors="ignore") as f:
                for raw_line in f:
                    line = raw_line.strip()
                    if not line or line.startswith("#"):
                        continue
                    servers.append(line)
        except OSError:
            servers = []

        result = tuple(servers)
        _DNS_SERVER_CACHE["path"] = dns_server_path
        _DNS_SERVER_CACHE["mtime"] = mtime
        _DNS_SERVER_CACHE["servers"] = result
        return result


def _next_cursor():
    global _RR_CURSOR
    with _RR_LOCK:
        cur = _RR_CURSOR
        _RR_CURSOR = (cur + 1) % 1000000
        return cur


def _select_nameservers(servers, attempt=0, batch_size=4):
    """每次请求与重试轮转切分不同公共 DNS 批次，防止单节点超时拖垮整轮解析。"""
    if not servers:
        return None
    total = len(servers)
    count = min(batch_size, total)
    start = (_next_cursor() + attempt * count) % total
    return [servers[(start + i) % total] for i in range(count)]


def _build_resolver(nameservers=None, timeout=2.5, lifetime=5.0):
    """构造独立 Resolver 实例；具备上游列表时绕开容器 resolv.conf。"""
    if nameservers:
        resolver = dns.resolver.Resolver(configure=False)
        resolver.nameservers = list(nameservers)
    else:
        resolver = dns.resolver.Resolver(configure=True)
    resolver.timeout = timeout
    resolver.lifetime = lifetime
    return resolver


def _get_logger():
    from app.utils import get_logger
    return get_logger()


def resolve_records(
    domain,
    rdtype="A",
    log_flag=True,
    retries=2,
    nameservers=None,
    timeout=2.5,
    lifetime=5.0,
    backoff_base=0.15,
):
    """
    解析指定域名的 DNS 记录并区分确定性否定与瞬时故障。

    返回值:
        (records: list[str], transient_error: bool)
        - NXDOMAIN / NoAnswer 属于确定性否定，不触发重试，返回 ([], False)
        - Timeout / NoNameservers 等瞬时异常会轮换上游 DNS 重试，耗尽后返回 ([], True)
    """
    domain = (domain or "").strip()
    if not domain:
        return [], False

    logger = _get_logger()
    configured_servers = tuple(nameservers) if nameservers else _load_dns_servers()
    attempts = max(1, int(retries) + 1)
    last_exc = None

    for attempt in range(attempts):
        batch = _select_nameservers(configured_servers, attempt=attempt)
        resolver = _build_resolver(nameservers=batch, timeout=timeout, lifetime=lifetime)
        try:
            answers = resolver.resolve(domain, rdtype)
            records = []
            for rdata in answers:
                if rdtype == "A":
                    addr = getattr(rdata, "address", "").strip()
                    if addr and addr != "0.0.0.1" and addr not in records:
                        records.append(addr)
                elif rdtype == "CNAME":
                    target = str(getattr(rdata, "target", rdata)).strip(".").lower()
                    if target and target not in records:
                        records.append(target)
                else:
                    val = str(rdata).strip()
                    if val and val not in records:
                        records.append(val)
            return records, False
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer) as exc:
            if log_flag:
                if rdtype == "CNAME":
                    logger.debug("%s %s", domain, exc)
                else:
                    logger.info("%s %s", domain, exc)
            return [], False
        except _TRANSIENT_ERRORS as exc:
            last_exc = exc
            if attempt < attempts - 1 and backoff_base > 0:
                time.sleep(min(0.8, backoff_base * (2 ** attempt)))
        except Exception as exc:
            last_exc = exc
            break

    if last_exc is not None and (log_flag or rdtype == "CNAME"):
        logger.warning(
            "DNS %s resolution failed for %s after %d attempt(s): %s",
            rdtype,
            domain,
            attempts,
            last_exc,
        )
    return [], True


def get_ip(domain, log_flag=True, retries=2):
    """解析域名 A 记录列表（直连公共 DNS 池并在瞬时超时后自动重试）。"""
    ips, _ = resolve_records(domain, rdtype="A", log_flag=log_flag, retries=retries)
    return ips


def get_ip_with_status(domain, log_flag=True, retries=2):
    """解析域名 A 记录并同时返回是否遭遇瞬时 DNS 故障。"""
    return resolve_records(domain, rdtype="A", log_flag=log_flag, retries=retries)


def get_cname(domain, log_flag=True, retries=2):
    """解析域名 CNAME 记录列表。"""
    cnames, _ = resolve_records(domain, rdtype="CNAME", log_flag=log_flag, retries=retries)
    return cnames


def extract_massdns_records(raw_records):
    """
    聚合 MassDNS 原始输出，提取每个域名的直接 A IP 与 CNAME，并尝试沿着同批次内的
    CNAME 链路补全目标 IP，减少后续重复 DNS 查询。
    """
    by_domain = {}
    for item in raw_records or ():
        if not isinstance(item, dict):
            continue
        domain = (item.get("domain") or "").strip().strip(".").lower()
        rtype = (item.get("type") or "").strip().upper()
        record = (item.get("record") or "").strip().strip(".")
        if not domain or not record:
            continue

        entry = by_domain.setdefault(domain, {"ips": [], "cnames": []})
        if rtype == "A":
            if record != "0.0.0.1" and record not in entry["ips"]:
                entry["ips"].append(record)
        elif rtype == "CNAME":
            cname = record.lower()
            if cname not in entry["cnames"]:
                entry["cnames"].append(cname)

    # 若 MassDNS 仅输出了 CNAME 行而未回填 A，则顺着同批次已解析的 CNAME 目标链补齐 IP
    for domain, entry in by_domain.items():
        if entry["ips"] or not entry["cnames"]:
            continue
        visited = {domain}
        frontier = list(entry["cnames"])
        depth = 0
        while frontier and depth < 5:
            next_frontier = []
            for target in frontier:
                if target in visited:
                    continue
                visited.add(target)
                target_entry = by_domain.get(target)
                if not target_entry:
                    continue
                for ip in target_entry["ips"]:
                    if ip not in entry["ips"]:
                        entry["ips"].append(ip)
                for next_cname in target_entry["cnames"]:
                    if next_cname not in visited:
                        next_frontier.append(next_cname)
            frontier = next_frontier
            depth += 1

    return by_domain
