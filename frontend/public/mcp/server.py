#!/usr/bin/env python3
"""
ARL-Next Zero-Dependency MCP Server (JSON-RPC 2.0 over Stdio)
- 标准库实现：纯 Python 3 标准库（sys, json, urllib, ssl, concurrent.futures），无需 pip 安装额外依赖
- 轻量冷启动：跨平台（Mac/Linux/Windows）即插即用，低资源开销
- 聚焦资产画像：提供核心工具 `get_asset_profile`，收敛上下文 Token 开销
- 双阶引擎保障：优先调用后端原生 `/api/mcp/asset_profile` 聚合接口；若远端尚未就绪则自动降级到标准 REST 聚合，保障高可用
- 广泛客户端兼容：支持 Antigravity, Claude Code, OpenAI Codex, DeepSeek Harness, ZCode, WorkBuddy 等标准客户端
"""

import os
import sys
import json
import ssl
import re
import urllib.request
import urllib.error
import urllib.parse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

PROTOCOL_VERSION = "2024-11-05"
SERVER_NAME = "arl-next"
SERVER_VERSION = "2.0.0"

TOOL_GET_ASSET_PROFILE = {
    "name": "get_asset_profile",
    "description": "获取指定目标（站点URL/IP/子域名）的综合资产画像，包括解析IP、开放端口与服务、Web指纹与标题、SSL证书、已知漏洞及敏感泄露等关联情报。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "资产标的，支持域名 (如 test.com)、IP (如 1.2.3.4) 或站点 URL (如 https://test.com:8443)"
            },
            "task_id": {
                "type": "string",
                "description": "可选。24位任务 ID。若指定则锁定该任务上下文，未指定则智能匹配最新任务或全局资产"
            }
        },
        "required": ["target"]
    }
}

TOOL_GET_ENTERPRISE_PROFILE = {
    "name": "get_enterprise_profile",
    "description": "获取指定企业标的（企业全称、简称、备案域名如 qq.com 或备案号）的全景生态资产画像与组织架构（包括工商背景、ICP备案网站、移动APP、微信小程序、公众号、企业微博、快应用及投资控股关系）。支持按资产分类下钻分页查询。",
    "inputSchema": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "企业标的，支持企业工商全称（如'深圳市腾讯计算机系统有限公司'）、企业商业简称（如'腾讯'）、根域名（如'qq.com'，自动反查所属企业）或 ICP 备案主体/备案号"
            },
            "category": {
                "type": "string",
                "enum": ["all", "web", "app", "mapp", "wechat", "weibo", "kapp", "invest"],
                "default": "all",
                "description": "查询维度：'all'（默认总览画像与各维度统计指标）；'web'（网站备案域名）；'app'（移动应用）；'mapp'（微信小程序）；'wechat'（微信公众号）；'weibo'（企业微博）；'kapp'（快应用）；'invest'（对外投资与控股子公司）"
            },
            "page": {
                "type": "integer",
                "default": 1,
                "description": "下钻指定 category 时的页码（从 1 开始）"
            },
            "size": {
                "type": "integer",
                "default": 20,
                "description": "下钻指定 category 时每页记录条数（默认 20，最大 100）"
            },
            "task_id": {
                "type": "string",
                "description": "可选。24位企业测绘任务 ID。若指定则直接锁定该任务历史数据"
            }
        },
        "required": ["target"]
    }
}


# 默认预置凭据占位符（支持从 Web 端导出单文件客户端时动态预填充；优先级低于环境变量与 ARL_auth.md）
DEFAULT_HOST = ""
DEFAULT_TOKEN = ""

_EXECUTOR = ThreadPoolExecutor(max_workers=5)


def _get_auth():
    """获取 ARL 凭据，优先级：1. 环境变量 > 2. 本地 ARL_auth.md > 3. 预置静态凭据 DEFAULT_HOST/DEFAULT_TOKEN"""
    host = os.environ.get("ARL_HOST", "").strip()
    token = os.environ.get("ARL_TOKEN", "").strip()

    candidate_paths = [
        Path.cwd() / "ARL_auth.md",
        Path(__file__).resolve().parent / "ARL_auth.md",
        Path(__file__).resolve().parent.parent / "ARL_auth.md",
    ]
    # 动态向上遍历最多 3 级父目录查找
    curr = Path.cwd().resolve()
    for _ in range(3):
        cp = curr / "ARL_auth.md"
        if cp not in candidate_paths:
            candidate_paths.append(cp)
        curr = curr.parent

    if not host or not token:
        for cp in candidate_paths:
            if cp.exists():
                try:
                    content = cp.read_text(encoding="utf-8")
                    for line in content.splitlines():
                        line_s = line.strip()
                        if not host and line_s.startswith("ARL_HOST:"):
                            host = line_s.split(":", 1)[1].strip()
                        elif not token and line_s.startswith("ARL_TOKEN:"):
                            token = line_s.split(":", 1)[1].strip()
                        elif not token and "token" in line_s and "'" in line_s:
                            parts = line_s.split("'")
                            if len(parts) >= 4 and parts[1] == "token":
                                token = parts[3].strip()
                except Exception:
                    pass

    # 优先级 3：若环境变量与本地 ARL_auth.md 均未提供，则读取导出时预置的默认凭据
    if not host and DEFAULT_HOST:
        host = DEFAULT_HOST.strip()
    if not token and DEFAULT_TOKEN:
        token = DEFAULT_TOKEN.strip()

    if not host:
        host = "https://127.0.0.1:5173"
    return host.rstrip("/"), token


def _resolve_ca_bundle(host):
    """解析启动时自动发现的本地证书，返回 (路径, 是否为 ARL 本地自签证书)。

    仅当目标主机是本机回环地址时才自动信任本地自签证书，避免经隧道/代理连接
    远程部署时，被本地文件静默放行任意证书。
    """
    explicit = os.environ.get("ARL_CA_BUNDLE", "").strip()
    if explicit:
        return os.path.expanduser(explicit), False

    hostname = urllib.parse.urlparse(host).hostname or ""
    if hostname not in ("127.0.0.1", "localhost", "::1"):
        return "", False

    # 客户端与服务端可能同处一个部署目录（服务端容器内 /code，客户端 /code/frontend/public/mcp）；
    # cwd 与 __file__ 两条路径同时覆盖本地跑于仓库根目录的情形。.certs 为 docker-compose.prod.yml
    # 的宿主挂载目录，certs 为 start-prod.sh 同步出的客户端可发现路径。
    # 用 parent 目录而非 __file__ 本身做 resolve：对文件取 resolve 会解析符号链接（如 macOS
    # 的 /tmp -> /private/tmp），可能把路径提升到部署根之外，导致向上遍历落空。
    here = Path(__file__).parent.resolve()
    roots = []
    for anchor in (here, here.parent, here.parent.parent, here.parent.parent.parent,
                   Path.cwd().resolve(), Path.cwd().resolve().parent):
        if anchor not in roots:
            roots.append(anchor)

    for suffix in (".certs", "certs"):
        for root in roots:
            crt = root / suffix / "arl.crt"
            if crt.is_file():
                return str(crt), True

    for suffix in ("ARL_auth.md", "ARL_server.md"):
        for root in roots:
            doc = root / suffix
            if not doc.is_file():
                continue
            try:
                content = doc.read_text(encoding="utf-8")
            except Exception:
                continue
            for line in content.splitlines():
                line_s = line.strip()
                if line_s.startswith("ARL_LOCAL_CERT:"):
                    found = Path(line_s.split(":", 1)[1].strip())
                    if found.is_file():
                        return str(found), True
    return "", False


def _api_status(http_status, data):
    """兼容旧 REST 接口通过 HTTP 200 返回业务错误的约定。"""
    if http_status != 200 or not isinstance(data, dict):
        return http_status
    try:
        business_code = int(data.get("code", 200))
    except (TypeError, ValueError):
        return 502
    if business_code == 200:
        return http_status
    return business_code if 400 <= business_code <= 599 else 502


_INSECURE_VALUES = ("false", "0", "no", "off")
_IPV4_RE = r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$'
_INSECURE_WARNED = [False]


class _PinnedCAContext:
    """以可信 CA 完成链校验后，放行主机名不匹配的自签部署。

    ARL-Next 首次启动自动签发的证书 CN=localhost 且不含 SAN 扩展，局域网部署
    只能以 IP 访问，证书无法覆盖该地址。此时证书链本身仍经 CA 验证（不可伪造），
    仅跳过主机名匹配，避免"默认安全"演变为"默认不可用"。
    显式设置 ARL_STRICT_HOSTNAME=true 可要求主机名严格匹配。
    该折衷仍不可绕过的攻击面（TLS 层）在 mcp-server/README.md 中列明。

    采用组合而非继承 ssl.SSLContext：其 C 层在 __new__ 中完成初始化，
    Python 子类的 __init__ 无法可靠承接构造参数。
    """

    def __init__(self, ca_bundle_path):
        self._inner = ssl.create_default_context(cafile=ca_bundle_path)
        self._inner.check_hostname = False
        self._inner.verify_mode = ssl.CERT_REQUIRED

    def wrap_socket(self, sock, *args, **kwargs):
        return self._inner.wrap_socket(sock, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._inner, name)


def _build_ssl_context(url):
    """按配置解析 TLS 上下文：显式关闭 > 可信 CA > 系统默认。

    返回 (上下文, 对端证书复检回调, 是否已关闭证书校验)。
    """
    if os.environ.get("ARL_TLS_VERIFY", "true").strip().lower() in _INSECURE_VALUES:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        return ctx, None, True

    ca_bundle, is_local_self_signed = _resolve_ca_bundle(_get_auth()[0])
    if not ca_bundle:
        return ssl.create_default_context(), None, False

    if not os.path.isfile(ca_bundle):
        if not is_local_self_signed:
            raise FileNotFoundError(f"ARL_CA_BUNDLE 指向的证书文件不存在或不可读: {ca_bundle}")
        # 自动发现的本地证书缺失时静默回退，不阻断开箱即用流程
        return ssl.create_default_context(), None, False

    strict = os.environ.get("ARL_STRICT_HOSTNAME", "").strip().lower() in ("true", "1", "yes", "on")
    if strict:
        return ssl.create_default_context(cafile=ca_bundle), None, False

    # 证书未覆盖该地址时主机名匹配无解，仅保留链校验：
    #   - 自动发现的本地自签证书：CN=localhost 且无 SAN，访问地址为 IP，必然不匹配
    #   - 显式 ARL_CA_BUNDLE 且目标为 IP 字面量
    # 域名目标仍走完整校验，两种情形下证书链均不可绕过。
    hostname = urllib.parse.urlparse(url).hostname or ""
    if not is_local_self_signed and not re.match(_IPV4_RE, hostname):
        return ssl.create_default_context(cafile=ca_bundle), None, False
    return _PinnedCAContext(ca_bundle), _verify_peer_instead(url, ca_bundle), False


def _peer_hosts(cert):
    """提取证书覆盖的主机名集合（仅取 SAN，与 ssl 模块的主机名判定口径一致）。

    has_san 为假时主机名匹配本就无解（Python 3.10+ 起不再回退 CN），
    此时与访问地址比较必然不等，正是需要放行的场景。
    """
    san = cert.get("subjectAltName") or []
    return {value for kind, value in san if kind in ("DNS", "IP Address")}


def _verify_peer_instead(url, ca_bundle_path):
    """主机名跳过匹配时，改为自行校验对端证书，避免连接被静默替换。"""

    def check(sock):
        try:
            cert = sock.getpeercert()
        except Exception:
            return
        if not cert:
            return
        hosts = _peer_hosts(cert)
        if hosts and not any(h.lower() in ("localhost", "127.0.0.1", "::1") for h in hosts):
            return
        actual = urllib.parse.urlparse(url).hostname or ""
        print(
            f"[arl-mcp] 警告: 对端证书声明的名称 {sorted(hosts)} 与访问地址 {actual} 不匹配，"
            f"已按 ARL_CA_BUNDLE 完成证书链校验（未校验主机名）。如部署已配置正确域名，"
            f"请将 ARL_HOST 改为该域名以获得完整校验；如确需兼容自签证书，可将该证书"
            f"复制为 {ca_bundle_path} 并设置 ARL_CA_BUNDLE={ca_bundle_path},"
            f"或设置 ARL_TLS_VERIFY=false。",
            file=sys.stderr,
        )

    return check


def _request_api(endpoint: str, params: dict = None) -> tuple:
    """向 ARL 后端发送统一 HTTP GET 请求 (返回 status_code, data)，支持快速超时控制"""
    host, token = _get_auth()
    if not token:
        return 401, {"status": "error", "message": "ARL API token not configured"}

    query_str = urllib.parse.urlencode(params) if params else ""
    url = f"{host}/api{endpoint}"
    if query_str:
        url = f"{url}?{query_str}"

    headers = {
        "Token": token,
        "Accept": "application/json",
        "User-Agent": "ARL-Next-MCP/2.0"
    }

    req = urllib.request.Request(url, headers=headers, method="GET")

    try:
        ctx, peer_check, insecure = _build_ssl_context(url)
        # 设置 8 秒快速超时，避免 Agent 终端长时间挂起
        with urllib.request.urlopen(req, context=ctx, timeout=8) as resp:
            if peer_check:
                peer_check(resp.fp.raw._sock)
            data = json.loads(resp.read().decode("utf-8"))
            result = _api_status(resp.status, data), data
    except FileNotFoundError as e:
        return 500, {"message": str(e)}
    except urllib.error.HTTPError as e:
        try:
            err_data = json.loads(e.read().decode("utf-8"))
            return e.code, err_data
        except Exception:
            return e.code, {"message": str(e)}
    except Exception as e:
        return 500, {"message": str(e)}

    if insecure and _INSECURE_WARNED[0] is False:
        _INSECURE_WARNED[0] = True
        print(
            "[arl-mcp] 警告: ARL_TLS_VERIFY=false 已关闭服务端证书校验，连接可能被中间人截获，"
            "仅限临时测试使用。生产环境请改用 ARL_CA_BUNDLE 指定可信证书。",
            file=sys.stderr,
        )
    return result


def _clean_empty(val, depth=0, max_depth=10):
    """递归清理空值 (None, '', [], {})，生成器推导与递归深度限制保护"""
    if depth > max_depth:
        return val
    if isinstance(val, dict):
        return {k: v for k, v in ((k, _clean_empty(sub_v, depth + 1, max_depth)) for k, sub_v in val.items()) if v not in (None, "", [], {})}
    elif isinstance(val, list):
        return [v for v in (_clean_empty(item, depth + 1, max_depth) for item in val) if v not in (None, "", [], {})]
    elif val is None or val == "":
        return None
    return val


def _request_items(endpoint, params):
    code, data = _request_api(endpoint, params)
    code = _api_status(code, data)
    if code == 200 and (not isinstance(data, dict) or not isinstance(data.get("items"), list)):
        return 502, []
    return code, data.get("items", []) if isinstance(data, dict) else []


def _profile_error(code, target):
    if code == 200:
        return None
    if code in (401, 403):
        return {"status": "auth_error", "message": "ARL 鉴权失败：Token 无效或已过期，请检查 ARL_TOKEN 配置", "target": target}
    return {"status": "error", "message": f"ARL 兼容接口查询失败 (HTTP {code})，无法确认资产结果", "target": target}


def _fallback_aggregate_profile(target: str, task_id: str = "") -> dict:
    """当后端 /api/mcp/asset_profile 未部署时，纯客户端极速并发聚合 ARL 各基础维度"""
    host, token = _get_auth()
    if not token:
        return {
            "status": "auth_error",
            "message": "ARL 鉴权失败：未检测到有效 ARL_TOKEN，请检查环境变量或 ARL_auth.md",
            "target": target
        }

    is_ip = bool(re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', target))
    hostname = None
    target_ip = None

    if "://" in target or target.startswith(("http:", "https:")):
        parsed = urllib.parse.urlparse(target)
        hostname = parsed.hostname or ""
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', hostname):
            target_ip = hostname
    elif is_ip:
        target_ip = target
    else:
        hostname = target.split(":", 1)[0].strip() if ":" in target else target.strip()
        # 防御无协议头 URL 路径残留
        hostname = hostname.split("/")[0].strip()

    profile = {"target": target}
    resolved_ips = set()
    if target_ip:
        resolved_ips.add(target_ip)

    # 并发查询各维度 (复用全局单例线程池)
    task_param = {"task_id": task_id} if task_id and len(task_id) == 24 else {}

    def fetch_domain():
        if hostname:
            p = {"domain": hostname, "size": 5, **task_param}
            c, items = _request_items("/domain/", p)
            return "domain", c, items
        elif is_ip:
            p = {"ips": target_ip, "size": 10, **task_param}
            c, items = _request_items("/domain/", p)
            return "domain", c, items
        return "domain", 200, []

    def fetch_site():
        p = {"size": 10, **task_param}
        if hostname:
            p["site"] = hostname
        elif target_ip:
            p["ip"] = target_ip
        c, items = _request_items("/site/", p)
        return "site", c, items

    def fetch_vuln():
        p = {"size": 30, **task_param}
        if hostname:
            p["target"] = hostname
        elif target_ip:
            p["target"] = target_ip
        c, items = _request_items("/vuln/", p)
        return "vuln", c, items

    def fetch_nuclei():
        p = {"size": 30, **task_param}
        if hostname:
            p["target"] = hostname
        elif target_ip:
            p["target"] = target_ip
        c, items = _request_items("/nuclei_result/", p)
        return "nuclei", c, items

    def fetch_leak():
        p = {"size": 30, **task_param}
        if hostname:
            p["url"] = hostname
        elif target_ip:
            p["url"] = target_ip
        c, items = _request_items("/fileleak/", p)
        return "fileleak", c, items

    futures = [
        _EXECUTOR.submit(fetch_domain),
        _EXECUTOR.submit(fetch_site),
        _EXECUTOR.submit(fetch_vuln),
        _EXECUTOR.submit(fetch_nuclei),
        _EXECUTOR.submit(fetch_leak),
    ]
    results = {}
    for f in futures:
        k, c, items = f.result()
        error = _profile_error(c, target)
        if error:
            return error
        results[k] = items

    # 聚合 Domain 与 IP
    for d in results.get("domain", []):
        ips = d.get("ips") or []
        if isinstance(ips, list):
            for ip in ips:
                if isinstance(ip, str) and ip.strip():
                    resolved_ips.add(ip.strip())
        rec_val = d.get("record_value")
        if rec_val and isinstance(rec_val, str) and re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', rec_val):
            resolved_ips.add(rec_val)

    # 聚合 Site
    web_list = []
    for s in results.get("site", []):
        s_ip = s.get("ip")
        if s_ip:
            resolved_ips.add(s_ip)
        fingers = [f.get("name") for f in s.get("finger", []) if isinstance(f, dict) and f.get("name")]
        web_list.append({
            "url": s.get("site"),
            "status": s.get("status"),
            "title": s.get("title"),
            "fingerprints": fingers
        })

    # 查询 IP 维度详情
    all_ips = list(resolved_ips)
    ports_map = {}
    geo_parts = []
    asn_name = None

    if all_ips:
        profile["resolved_ips"] = sorted(all_ips)
        for ip in all_ips[:3]:
            p = {"ip": ip, "size": 1, **task_param}
            code, items = _request_items("/ip/", p)
            error = _profile_error(code, target)
            if error:
                return error
            if items:
                ip_item = items[0]
                if not geo_parts:
                    g = ip_item.get("geo_city", {})
                    parts = [g.get("country_name"), g.get("region_name"), g.get("city")]
                    geo_parts = [p for p in parts if p and str(p) not in ('None', 'null', '0')]
                if not asn_name:
                    asn_name = ip_item.get("as_organization") or ip_item.get("geo_asn", {}).get("organization")
                for pt in ip_item.get("port_info", []):
                    pid = pt.get("port_id")
                    if pid:
                        ports_map[pid] = {
                            "port": pid,
                            "service": pt.get("service_name"),
                            "product": pt.get("product"),
                            "version": pt.get("version")
                        }

    if geo_parts:
        profile["geo"] = "/".join(geo_parts)
    if asn_name:
        profile["asn"] = asn_name
    if ports_map:
        sorted_ports = sorted(ports_map.values(), key=lambda x: x.get("port", 0))
        if len(sorted_ports) > 100:
            profile["ports"] = sorted_ports[:100]
            profile["_meta_ports_total"] = len(sorted_ports)
            profile["_meta_ports_truncated"] = True
        else:
            profile["ports"] = sorted_ports
    if web_list:
        profile["web"] = web_list[0] if len(web_list) == 1 else web_list

    # 聚合漏洞与泄露
    vulns = []
    for v in results.get("vuln", []):
        vulns.append({
            "name": v.get("vul_name") or v.get("vuln_name"),
            "severity": v.get("severity", "high"),
            "target": v.get("target")
        })
    for n in results.get("nuclei", []):
        vulns.append({
            "name": n.get("vuln_name"),
            "severity": n.get("vuln_severity"),
            "target": n.get("vuln_url") or n.get("target"),
            "plugin": "nuclei"
        })
    if vulns:
        if len(vulns) > 100:
            profile["vulns"] = vulns[:100]
            profile["_meta_vulns_total"] = len(vulns)
            profile["_meta_vulns_truncated"] = True
        else:
            profile["vulns"] = vulns

    leaks = []
    for lk in results.get("fileleak", []):
        url_val = str(lk.get("url") or "")
        if (target in url_val) or any(ip in url_val for ip in resolved_ips):
            leaks.append({"url": url_val, "title": lk.get("title"), "status": lk.get("status_code")})
    if leaks:
        profile["leaks"] = leaks

    clean = _clean_empty(profile)
    if not clean or list(clean.keys()) == ["target"]:
        return {
            "status": "not_found",
            "target": target,
            "tip": "未在 ARL 检索到该资产记录"
        }
    return clean


def _fetch_asset_profile(target: str, task_id: str = "") -> dict:
    """双阶获取画像：优先原生 /api/mcp/asset_profile，缺失时自动降级到 REST 聚合"""
    params = {"target": target}
    if task_id:
        params["task_id"] = task_id

    code, resp_data = _request_api("/mcp/asset_profile", params)
    if code == 200 and isinstance(resp_data, dict) and "code" not in resp_data:
        return resp_data

    # 拦截鉴权失败 (401 及 403)
    if code in (401, 403) or (isinstance(resp_data, dict) and resp_data.get("code") in (401, 403)):
        return {
            "status": "auth_error",
            "message": "ARL 鉴权失败：Token 无效或已过期，请检查 ARL_TOKEN 配置",
            "target": target
        }

    # 仅当原生接口未部署 (404/405) 时，才降级为客户端并发聚合
    if code in (404, 405):
        return _fallback_aggregate_profile(target, task_id)

    # 其余网络中断、连接被拒或服务端异常 (5xx) 直接报错，避免 5 路并发子请求放大超时与故障
    err_msg = resp_data.get("message") if isinstance(resp_data, dict) else str(resp_data)
    return {
        "status": "error",
        "message": f"ARL 服务端响应异常 (HTTP {code}): {err_msg}",
        "target": target
    }


def _fallback_aggregate_enterprise_profile(target: str, category: str = "all", page: int = 1, size: int = 20, task_id: str = "") -> dict:
    """当后端原生 /api/mcp/enterprise_profile 未部署时，纯客户端降级调用标准 /api/icp/task 与 /api/icp/asset 接口聚合"""
    host, token = _get_auth()
    if not token:
        return {
            "status": "auth_error",
            "message": "ARL 鉴权失败：未检测到有效 ARL_TOKEN，请检查环境变量或 ARL_auth.md",
            "target": target
        }

    task_item = None
    if task_id:
        c, tasks = _request_items("/icp/task", {"_id": task_id})
        err = _profile_error(c, target)
        if err:
            return err
        if tasks:
            task_item = tasks[0]

    if not task_item:
        c, tasks = _request_items("/icp/task", {"name": target, "size": 10})
        err = _profile_error(c, target)
        if err:
            return err
        if not tasks:
            c, tasks = _request_items("/icp/task", {"target": target, "size": 10})
            err = _profile_error(c, target)
            if err:
                return err

        if tasks:
            task_item = tasks[0]

    if not task_item:
        return {
            "status": "not_found",
            "target": target,
            "message": f"未在 ARL 资产库中检索到与【{target}】匹配的企业测绘记录",
            "suggestion": "可前往 ARL Web 控制台【资产组 -> 新建资产组 -> 企业全景测绘建组】，或确认名称/域名无误后重试"
        }

    tid = str(task_item.get("_id") or task_item.get("id") or "")
    comp_name = task_item.get("company_name") or task_item.get("target") or task_item.get("name") or target

    if category == "all":
        counts = {}
        for cat in ["web", "app", "mapp", "wechat", "weibo", "kapp", "invest"]:
            code, resp_raw = _request_api("/icp/asset", {"task_id": tid, "query_type": cat, "size": 1})
            if isinstance(resp_raw, dict) and "total" in resp_raw:
                counts[cat] = resp_raw["total"]
            else:
                counts[cat] = len(resp_raw.get("items", [])) if isinstance(resp_raw, dict) else 0
        counts["total"] = sum(counts.values())

        samples = {}
        _, web_items = _request_items("/icp/asset", {"task_id": tid, "query_type": "web", "size": 5})
        if web_items:
            samples["web_top"] = [
                {
                    "domain": x.get("domain") or x.get("ym"),
                    "service_name": x.get("serviceName") or x.get("webName"),
                    "licence": x.get("serviceLicence") or x.get("liscense")
                }
                for x in web_items
            ]

        return _clean_empty({
            "status": "success",
            "enterprise_info": {
                "name": comp_name,
                "task_id": tid,
                "task_status": task_item.get("status", "done"),
                "task_type": task_item.get("task_type", "icp")
            },
            "asset_counts": counts,
            "samples": samples,
            "drilldown_guidance": {
                "tip": f"当前为【{comp_name}】全景生态资产总览画像。若需查看某维度的完整资产列表，请传入对应 category 参数下钻查询（例如 category='web' 查询全量备案域名）；若需对特定域名探查开放端口与漏洞风险，请调用 get_asset_profile(target='xxx.com')。"
            }
        })
    else:
        code, resp_raw = _request_api("/icp/asset", {"task_id": tid, "query_type": category, "page": page, "size": size})
        err = _profile_error(code, target)
        if err:
            return err
        items = resp_raw.get("items", []) if isinstance(resp_raw, dict) else []
        total = resp_raw.get("total", len(items)) if isinstance(resp_raw, dict) else len(items)
        return _clean_empty({
            "status": "success",
            "enterprise_name": comp_name,
            "task_id": tid,
            "category": category,
            "pagination": {
                "page": page,
                "size": size,
                "total": total,
                "has_more": ((page - 1) * size + len(items)) < total
            },
            "items": items,
            "tip": f"已返回第 {page} 页数据（共 {total} 条）。若需探测特定资产技术暴露面，可调用 get_asset_profile(target='...')"
        })


def _fetch_enterprise_profile(target: str, category: str = "all", page: int = 1, size: int = 20, task_id: str = "") -> dict:
    """双阶获取企业生态画像：优先原生 /api/mcp/enterprise_profile，缺失时自动降级到 REST 聚合"""
    params = {"target": target, "category": category, "page": page, "size": size}
    if task_id:
        params["task_id"] = task_id

    code, resp_data = _request_api("/mcp/enterprise_profile", params)
    if code == 200 and isinstance(resp_data, dict) and "code" not in resp_data:
        return resp_data

    # 拦截鉴权失败 (401 及 403)
    if code in (401, 403) or (isinstance(resp_data, dict) and resp_data.get("code") in (401, 403)):
        return {
            "status": "auth_error",
            "message": "ARL 鉴权失败：Token 无效或已过期，请检查 ARL_TOKEN 配置",
            "target": target
        }

    # 仅当原生接口未部署 (404/405) 时，才降级为客户端标准接口聚合
    if code in (404, 405):
        return _fallback_aggregate_enterprise_profile(target=target, category=category, page=page, size=size, task_id=task_id)

    err_msg = resp_data.get("message") if isinstance(resp_data, dict) else str(resp_data)
    return {
        "status": "error",
        "message": f"ARL 服务端响应异常 (HTTP {code}): {err_msg}",
        "target": target
    }


def handle_request(req: dict) -> dict:
    """处理 JSON-RPC 2.0 协议请求"""
    req_id = req.get("id")
    method = req.get("method", "")
    params = req.get("params", {})

    # 1. 协议初始化握手
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {
                    "tools": {
                        "listChanged": False
                    }
                },
                "serverInfo": {
                    "name": SERVER_NAME,
                    "version": SERVER_VERSION
                }
            }
        }

    # 2. 客户端完成初始化通知（Notification，无返回值）
    if method in ("notifications/initialized", "initialized"):
        return None

    # 3. 探活 ping
    if method == "ping":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {}
        }

    # 4. 列出可用工具集
    if method == "tools/list":
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "result": {
                "tools": [TOOL_GET_ASSET_PROFILE, TOOL_GET_ENTERPRISE_PROFILE]
            }
        }

    # 5. 调用工具
    if method == "tools/call":
        tool_name = params.get("name", "")
        args = params.get("arguments", {})

        if tool_name == "get_asset_profile":
            target = str(args.get("target", "")).strip()
            task_id = str(args.get("task_id", "")).strip()

            if not target:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": json.dumps({"status": "error", "message": "Missing required parameter: target"}, ensure_ascii=False)}
                        ],
                        "isError": True
                    }
                }

            profile_data = _fetch_asset_profile(target=target, task_id=task_id)
            is_error = isinstance(profile_data, dict) and profile_data.get("status") in ("auth_error", "error")
            # 采用紧凑 JSON 序列化（消除多余空格与缩进，节省上下文 Token）
            compact_json_str = json.dumps(profile_data, ensure_ascii=False, separators=(",", ":"))

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": compact_json_str
                        }
                    ],
                    "isError": is_error
                }
            }

        elif tool_name == "get_enterprise_profile":
            target = str(args.get("target", "")).strip()
            category = str(args.get("category", "all")).strip()
            page = args.get("page", 1)
            size = args.get("size", 20)
            task_id = str(args.get("task_id", "")).strip()

            if not target and not task_id:
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": json.dumps({"status": "error", "message": "Missing required parameter: target"}, ensure_ascii=False)}
                        ],
                        "isError": True
                    }
                }

            profile_data = _fetch_enterprise_profile(target=target, category=category, page=page, size=size, task_id=task_id)
            is_error = isinstance(profile_data, dict) and profile_data.get("status") in ("auth_error", "error")
            compact_json_str = json.dumps(profile_data, ensure_ascii=False, separators=(",", ":"))

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": compact_json_str
                        }
                    ],
                    "isError": is_error
                }
            }

        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Tool '{tool_name}' not found"
            }
        }

    # 未知方法
    if req_id is not None:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {
                "code": -32601,
                "message": f"Method '{method}' not recognized"
            }
        }

    return None


def main():
    """标准输入输出事件主循环，支持原生换行符 (NDJSON) 与 LSP Content-Length 两种协议帧"""
    in_stream = sys.stdin.buffer if hasattr(sys.stdin, "buffer") else sys.stdin
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    while True:
        try:
            line = in_stream.readline()
            if not line:
                break
        except Exception:
            break

        line_bytes = line if isinstance(line, bytes) else line.encode("utf-8")
        # 处理可能附带 Content-Length: 的 LSP 帧协议
        if line_bytes.lower().startswith(b"content-length:"):
            try:
                length_str = line_bytes.split(b":", 1)[1].strip()
                content_length = int(length_str)
                # 循环丢弃后续所有附带的 Header，直到真正的空行
                while True:
                    h_line = in_stream.readline()
                    if not h_line or not h_line.strip():
                        break
                raw_body = in_stream.read(content_length)
                body = raw_body.decode("utf-8", errors="replace") if isinstance(raw_body, bytes) else raw_body
                req = json.loads(body)
                try:
                    resp = handle_request(req)
                except Exception as e:
                    resp = {
                        "jsonrpc": "2.0",
                        "id": req.get("id") if isinstance(req, dict) else None,
                        "error": {"code": -32603, "message": f"Internal server error: {str(e)}"}
                    }
                if resp is not None:
                    out_body = json.dumps(resp, ensure_ascii=False)
                    out_bytes = out_body.encode("utf-8")
                    sys.stdout.write(f"Content-Length: {len(out_bytes)}\r\n\r\n{out_body}\r\n")
                    sys.stdout.flush()
            except Exception:
                pass
            continue

        # 标准换行符分隔的 JSON-RPC 消息 (NDJSON)
        line_str = line.decode("utf-8", errors="replace").strip() if isinstance(line, bytes) else line.strip()
        if not line_str:
            continue

        try:
            req = json.loads(line_str)
        except Exception:
            continue

        try:
            resp = handle_request(req)
        except Exception as e:
            resp = {
                "jsonrpc": "2.0",
                "id": req.get("id") if isinstance(req, dict) else None,
                "error": {"code": -32603, "message": f"Internal server error: {str(e)}"}
            }

        if resp is not None:
            out_str = json.dumps(resp, ensure_ascii=False)
            sys.stdout.write(out_str + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
