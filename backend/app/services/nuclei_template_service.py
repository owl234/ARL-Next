import os
import re
import yaml
import json
import shutil
import zipfile
import subprocess
import tempfile
import threading
import time
from datetime import datetime
from urllib.parse import urlsplit
import requests

from app import utils
from app.utils import get_logger
from app.config import Config

logger = get_logger()

# 官方社区模板内存索引缓存
_community_cache = {
    "templates": [],
    "last_load": 0,
    "dir": "",
    "lock": threading.Lock(),
    "cache_epoch": 0.0
}

_sync_lock = threading.Lock()


def get_community_templates_dir() -> str:
    """获取官方社区模板存储路径"""
    custom_env = os.environ.get("NUCLEI_TEMPLATES_PATH")
    if custom_env and os.path.exists(custom_env):
        return os.path.abspath(custom_env)

    candidates = [
        "/root/nuclei-templates",
        os.path.expanduser("~/nuclei-templates"),
        os.path.expanduser("~/.local/nuclei-templates"),
        os.path.join(Config.basedir, "nuclei-templates"),
    ]
    for p in candidates:
        if os.path.exists(p) and os.path.isdir(p):
            return os.path.abspath(p)
    return ""


def get_nuclei_template_version_info() -> dict:
    """获取本地模板安装版本与官方最新版本信息"""
    cfg_candidates = [
        "/root/.config/nuclei/.templates-config.json",
        os.path.expanduser("~/.config/nuclei/.templates-config.json"),
        os.path.join(Config.basedir, ".config/nuclei/.templates-config.json")
    ]
    cur_ver = "未知"
    latest_ver = "未知"
    cfg_file = None

    for p in cfg_candidates:
        if os.path.exists(p):
            cfg_file = p
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)
                    cur_ver = cfg_data.get("nuclei-templates-version", cur_ver)
                    latest_ver = cfg_data.get("nuclei-templates-latest-version", latest_ver)
            except Exception:
                pass
            break

    if cur_ver == "未知":
        try:
            res = subprocess.run(["nuclei", "-tv"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
            combined = (res.stdout or "") + "\n" + (res.stderr or "")
            m = re.search(r'v\d+\.\d+\.\d+', combined)
            if m:
                cur_ver = m.group(0)
        except Exception:
            pass

    has_update = False
    if cur_ver != "未知" and latest_ver != "未知" and cur_ver != latest_ver:
        has_update = True

    return {
        "current_version": cur_ver,
        "latest_version": latest_ver,
        "has_update": has_update,
        "config_file": cfg_file
    }


def update_templates_config_version(new_version: str):
    """更新本地 .templates-config.json 中的版本号标记"""
    cfg_candidates = [
        "/root/.config/nuclei/.templates-config.json",
        os.path.expanduser("~/.config/nuclei/.templates-config.json"),
    ]
    for p in cfg_candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    cfg_data = json.load(f)
                cfg_data["nuclei-templates-version"] = new_version
                if "nuclei-templates-latest-version" in cfg_data:
                    cfg_data["nuclei-templates-latest-version"] = new_version
                with open(p, "w", encoding="utf-8") as f:
                    json.dump(cfg_data, f, indent=2)
                return True
            except Exception as e:
                logger.warning(f"Failed to update {p}: {e}")
    return False


def extract_templates_zip_to_dir(zip_file_path: str, target_dir: str) -> int:
    """解压覆盖 nuclei 模板 zip 包到 target_dir (带 Zip Slip 防护)"""
    os.makedirs(target_dir, exist_ok=True)
    count = 0
    with zipfile.ZipFile(zip_file_path, 'r') as zf:
        namelist = zf.namelist()
        if not namelist:
            return 0

        # 判断是否有唯一的公共根目录 (例如 nuclei-templates-10.5.0/)
        # 防护：不能把标准协议分类目录 (如 http, network, dns, cves) 当成多余的顶层包装目录剥离
        # 防御：禁止将 '..' 或以特殊符号开头的目录作为公共前缀剥离，防御恶意 Zip Slip 变体
        standard_dirs = {"http", "network", "dns", "ssl", "dast", "cloud", "code", "file", "headless", "helpers", "javascript", "profiles", "workflows", "cves"}
        top_dirs = set(p.split('/')[0] for p in namelist if '/' in p)
        common_prefix = ""
        if len(top_dirs) == 1:
            first_top = list(top_dirs)[0]
            if first_top not in standard_dirs and not first_top.startswith(('.', '/', '\\')):
                if all(p.startswith(first_top + '/') or p == first_top for p in namelist):
                    common_prefix = first_top + '/'

        abs_target = os.path.abspath(target_dir)
        for member in zf.infolist():
            raw_parts = [p.strip() for p in member.filename.replace('\\', '/').split('/') if p.strip()]
            if '..' in raw_parts or member.filename.startswith(('/', '\\')):
                continue

            rel_name = member.filename
            if common_prefix and rel_name.startswith(common_prefix):
                rel_name = rel_name[len(common_prefix):]
            if not rel_name or rel_name.startswith(('/', '\\', '..')):
                continue

            dest_path = os.path.abspath(os.path.join(abs_target, rel_name))
            if not dest_path.startswith(abs_target):
                continue

            if member.is_dir():
                os.makedirs(dest_path, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(dest_path), exist_ok=True)
                with zf.open(member) as src, open(dest_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
                count += 1
    return count


_ANSI_RE = re.compile(r'\x1b\[[0-9;?]*[ -/]*[@-~]')


def strip_ansi(text: str) -> str:
    """移除终端输出中的 ANSI 颜色与控制转义序列。"""
    if not text:
        return ""
    return _ANSI_RE.sub("", text)


def normalize_dry_run_target(raw_target: str, protocol: str = "http"):
    """根据模板协议规范化单目标输入，防止参数注入与跨协议误拼前缀。"""
    if not isinstance(raw_target, str):
        return False, "目标格式非法"
    target = raw_target.strip()
    if not target:
        return False, "目标地址不能为空"
    if any(ch.isspace() or ord(ch) < 32 for ch in target):
        return False, "单目标即时调试仅支持单个目标，不能包含空格、换行或控制字符"
    if target.startswith("-"):
        return False, "非法目标格式，不能以 '-' 开头"

    proto = (protocol or "http").strip().lower()
    if proto in {"http", "headless"}:
        if not target.lower().startswith(("http://", "https://")):
            target = "http://" + target
        return True, target
    if proto == "websocket":
        if not target.lower().startswith(("ws://", "wss://", "http://", "https://")):
            target = "http://" + target
        return True, target

    if proto in {"dns", "tcp", "network", "ssl", "whois"}:
        if target.lower().startswith(("http://", "https://")):
            parsed = urlsplit(target)
            if not parsed.netloc:
                return False, "无效的目标主机或端口"
            target = parsed.netloc
        elif "/" in target:
            target = target.split("/", 1)[0]
        if not target:
            return False, "无效的目标地址"
        return True, target

    return True, target


def _extract_nuclei_error_summary(raw_output: str) -> str:
    """从 Nuclei 输出中提取核心错误信息，过滤启动 ASCII Banner。"""
    cleaned = strip_ansi(raw_output).strip()
    if not cleaned:
        return ""
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    key_lines = [line for line in lines if any(tag in line for tag in ("[ERR]", "[FTL]", "cause=", "Invalid "))]
    if key_lines:
        return "\n".join(key_lines[-4:])
    return "\n".join(lines[-5:])


def parse_and_validate_nuclei_yaml(content: str, run_nuclei_validate: bool = False):
    """
    解析与静态校验 Nuclei 模板 YAML
    返回: (is_valid: bool, data_or_error: dict|str)
    """
    if not isinstance(content, str) or not content.strip():
        return False, "模板内容不能为空"

    try:
        doc = yaml.safe_load(content)
    except Exception as e:
        return False, f"YAML 语法解析错误: {e}"

    if not isinstance(doc, dict):
        return False, "Nuclei 模板必须为顶层 YAML 映射/字典格式"

    template_id = doc.get("id")
    if not template_id or not isinstance(template_id, str):
        return False, "缺少根节点 'id'（模板唯一标识）"

    template_id = template_id.strip()
    if not re.match(r'^[a-zA-Z0-9_\-\.]+$', template_id):
        return False, "模板 id 只能包含英文字母、数字、点号(.)、下划线(_)和连字符(-)"

    info = doc.get("info")
    if not info or not isinstance(info, dict):
        return False, "缺少 'info' 元数据块"

    name = info.get("name")
    if name is None or isinstance(name, bool) or not str(name).strip():
        return False, "info 节点下缺少有效 'name'（漏洞名称）"

    raw_author = info.get("author")
    if isinstance(raw_author, list):
        authors = [str(a).strip() for a in raw_author if a is not None and not isinstance(a, bool) and str(a).strip()]
        author = ", ".join(authors)
    elif raw_author is not None and not isinstance(raw_author, bool):
        author = str(raw_author).strip()
    else:
        author = ""
    if not author:
        return False, "info 节点下缺少有效 'author'（模板作者，Nuclei 引擎要求必填）"

    raw_severity = info.get("severity")
    valid_severities = {"info", "low", "medium", "high", "critical", "unknown"}
    if raw_severity is None or isinstance(raw_severity, bool) or not str(raw_severity).strip():
        return False, "info 节点下缺少有效 'severity'（可选值: info/low/medium/high/critical/unknown）"
    severity = str(raw_severity).strip().lower()
    if severity not in valid_severities:
        return False, f"无效的危害级别 severity '{raw_severity}'，可选值: info/low/medium/high/critical/unknown"

    raw_tags = info.get("tags", [])
    tags = []
    seen_tags = set()
    if isinstance(raw_tags, str):
        candidates = [t.strip().lower() for t in raw_tags.split(",") if t.strip()]
    elif isinstance(raw_tags, list):
        candidates = [str(t).strip().lower() for t in raw_tags if t is not None and str(t).strip()]
    else:
        candidates = []
    for tag in candidates:
        if tag not in seen_tags:
            seen_tags.add(tag)
            tags.append(tag)

    known_protocols = [
        "http", "requests", "dns", "tcp", "network", "ssl",
        "websocket", "whois", "code", "javascript", "headless", "file", "workflows"
    ]
    found_protocols = []
    for p in known_protocols:
        if p in doc:
            val = doc.get(p)
            if isinstance(val, (list, dict)) and len(val) > 0:
                found_protocols.append(p)
            else:
                return False, f"协议配置块 '{p}' 不能为空"
    if not found_protocols:
        return False, "模板缺少有效的协议探测块（如 http、dns、tcp、ssl、network、workflows 等）"

    protocol = "http" if found_protocols[0] == "requests" else found_protocols[0]

    description = str(info.get("description", "")).strip() if info.get("description") is not None else ""
    reference = info.get("reference", [])
    if isinstance(reference, str):
        reference = [reference]
    elif not isinstance(reference, list):
        reference = []

    metadata = {
        "template_id": template_id,
        "name": str(name).strip(),
        "severity": severity,
        "tags": tags,
        "protocol": protocol,
        "author": author,
        "description": description,
        "reference": reference,
        "content": content
    }

    # 深度语义校验 nuclei -duc -no-color -validate
    nuclei_bin = shutil.which("nuclei") if run_nuclei_validate else None
    if run_nuclei_validate and nuclei_bin:
        tmp_path = os.path.join(Config.TMP_PATH, f"validate_{utils.random_choices(8)}.yaml")
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                f.write(content)
            cmd = [nuclei_bin, "-duc", "-no-color", "-validate", "-t", tmp_path]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=15)
            if res.returncode != 0:
                summary = _extract_nuclei_error_summary(res.stderr or res.stdout)
                return False, f"Nuclei 语义验证不通过: {summary or f'退出码 {res.returncode}'}"
        except subprocess.TimeoutExpired:
            return False, "Nuclei 语义验证超时，请检查模板语法或稍后重试"
        except OSError as e:
            logger.warning(f"nuclei -validate unavailable, fallback to static check: {e}")
        finally:
            if os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except Exception:
                    pass

    return True, metadata


ASM_WEB_PROTOCOLS = frozenset({"http", "requests", "websocket"})
ASM_NETWORK_PROTOCOLS = frozenset({"tcp", "network", "ssl", "javascript"})
ASM_DNS_PROTOCOLS = frozenset({"dns", "whois"})
ASM_UNSUPPORTED_PROTOCOLS = frozenset({"code", "headless", "file", "workflows"})


def classify_asm_protocol(protocol: str) -> str:
    """将 Nuclei 模板协议归类为 ASM 执行桶: web / network / dns / unsupported。"""
    proto = str(protocol or "http").strip().lower()
    if proto in ASM_WEB_PROTOCOLS:
        return "web"
    if proto in ASM_NETWORK_PROTOCOLS:
        return "network"
    if proto in ASM_DNS_PROTOCOLS:
        return "dns"
    if proto in ASM_UNSUPPORTED_PROTOCOLS:
        return "unsupported"
    return "web"


def is_asm_supported_protocol(protocol: str) -> bool:
    return classify_asm_protocol(protocol) != "unsupported"


def _run_nuclei_validate_path(nuclei_bin: str, target_path: str, timeout: int = 15):
    cmd = [nuclei_bin, "-duc", "-no-color", "-validate", "-t", target_path]
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=timeout)


def validate_nuclei_templates_batch(entries: list):
    """
    批量执行 nuclei -validate 语义校验：
    1. 整批落盘至临时目录一次校验，全部合法时 O(1) 通过；
    2. 存在异常模板时自动二分定位具体失败文件并提取摘要，兼顾大 ZIP 导入耗时与精度；
    3. 运行环境无 nuclei 可执行文件时降级放行（保留静态校验结果）。
    返回: (passed_entries: list, failures: list[{"filename": str, "reason": str}])
    """
    if not entries:
        return [], []

    nuclei_bin = shutil.which("nuclei")
    if not nuclei_bin:
        return list(entries), []

    passed = []
    failures = []

    def _validate_subset(subset: list, work_root: str, depth: int = 0):
        if not subset:
            return

        if len(subset) == 1:
            entry = subset[0]
            single_path = os.path.join(work_root, f"single_{depth}_{utils.random_choices(6)}.yaml")
            try:
                with open(single_path, "w", encoding="utf-8") as f:
                    f.write(entry["meta"]["content"])
                res = _run_nuclei_validate_path(nuclei_bin, single_path, timeout=15)
                if res.returncode == 0:
                    passed.append(entry)
                else:
                    summary = _extract_nuclei_error_summary(res.stderr or res.stdout)
                    failures.append({
                        "filename": entry["filename"],
                        "reason": f"Nuclei 语义验证不通过: {summary or f'退出码 {res.returncode}'}",
                    })
            except subprocess.TimeoutExpired:
                failures.append({
                    "filename": entry["filename"],
                    "reason": "Nuclei 语义验证超时，请检查模板语法或稍后重试",
                })
            except OSError as e:
                logger.warning(f"nuclei -validate unavailable during batch import, fallback to static check: {e}")
                passed.append(entry)
            finally:
                if os.path.exists(single_path):
                    try:
                        os.unlink(single_path)
                    except Exception:
                        pass
            return

        batch_dir = os.path.join(work_root, f"batch_{depth}_{utils.random_choices(6)}")
        os.makedirs(batch_dir, exist_ok=True)
        try:
            for idx, entry in enumerate(subset):
                fpath = os.path.join(batch_dir, f"tpl_{idx:05d}.yaml")
                with open(fpath, "w", encoding="utf-8") as f:
                    f.write(entry["meta"]["content"])

            timeout_sec = min(120, max(20, len(subset) * 2))
            res = _run_nuclei_validate_path(nuclei_bin, batch_dir, timeout=timeout_sec)
            if res.returncode == 0:
                passed.extend(subset)
                return
        except subprocess.TimeoutExpired:
            pass
        except OSError as e:
            logger.warning(f"nuclei -validate unavailable during batch import, fallback to static check: {e}")
            passed.extend(subset)
            return
        finally:
            shutil.rmtree(batch_dir, ignore_errors=True)

        mid = len(subset) // 2
        _validate_subset(subset[:mid], work_root, depth + 1)
        _validate_subset(subset[mid:], work_root, depth + 1)

    os.makedirs(Config.TMP_PATH, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=Config.TMP_PATH, prefix="nuclei_import_val_") as tmp_root:
        _validate_subset(list(entries), tmp_root)

    return passed, failures


def load_community_index(force_refresh: bool = False):
    """加载官方社区模板轻量索引 (支持多工作进程基于 MongoDB 状态感知与缓存失效)"""
    now = time.time()
    c_dir = get_community_templates_dir()
    if not c_dir or not os.path.isdir(c_dir):
        return []

    remote_epoch = 0.0
    try:
        sync_doc = utils.conn_db('nuclei_sync_log').find_one({'_id': 'latest_sync'}, {'cache_epoch': 1})
        if sync_doc and 'cache_epoch' in sync_doc:
            remote_epoch = float(sync_doc['cache_epoch'])
    except Exception:
        pass

    with _community_cache["lock"]:
        cached_epoch = _community_cache.get("cache_epoch", 0.0)
        is_stale = (remote_epoch > cached_epoch) or (not _community_cache["templates"]) or (_community_cache["dir"] != c_dir)

        if not force_refresh and not is_stale and (now - _community_cache["last_load"] < 1800):
            return _community_cache["templates"]

        if force_refresh:
            remote_epoch = now
            try:
                utils.conn_db('nuclei_sync_log').update_one(
                    {'_id': 'latest_sync'},
                    {'$set': {'cache_epoch': remote_epoch, 'updated_at': utils.curr_date()}},
                    upsert=True
                )
            except Exception:
                pass

        templates = []
        cves_json = os.path.join(c_dir, "cves.json")

        if os.path.exists(cves_json):
            try:
                with open(cves_json, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            item = json.loads(line)
                            info = item.get("Info", {})
                            templates.append({
                                "template_id": item.get("ID", ""),
                                "name": info.get("Name", "") or item.get("ID", ""),
                                "severity": str(info.get("Severity", "unknown")).lower(),
                                "description": info.get("Description", ""),
                                "file_path": item.get("file_path", ""),
                                "tags": ["cve"],
                                "type": "cve"
                            })
                        except Exception:
                            continue
            except Exception as e:
                logger.warning(f"Failed to read cves.json: {e}")

        for cat in ["http", "network", "dns", "ssl", "dast"]:
            cat_path = os.path.join(c_dir, cat)
            if not os.path.exists(cat_path):
                continue
            for root, dirs, files in os.walk(cat_path):
                if "cves" in root:
                    continue
                for fname in files:
                    if fname.endswith(('.yaml', '.yml')):
                        rel = os.path.relpath(os.path.join(root, fname), c_dir)
                        base_id = os.path.splitext(fname)[0]
                        templates.append({
                            "template_id": base_id,
                            "name": base_id,
                            "severity": "unknown",
                            "description": "",
                            "file_path": rel,
                            "tags": [cat],
                            "type": cat
                        })

        _community_cache["templates"] = templates
        _community_cache["last_load"] = now
        _community_cache["dir"] = c_dir
        _community_cache["cache_epoch"] = remote_epoch
        return templates


def get_current_sync_doc() -> dict:
    """获取最新同步状态记录"""
    col = utils.conn_db('nuclei_sync_log')
    doc = col.find_one({'_id': 'latest_sync'})
    ver_info = get_nuclei_template_version_info()
    if not doc:
        return {
            "status": "idle",
            "sync_mode": "online",
            "start_time": "",
            "end_time": "",
            "current_version": ver_info.get("current_version", "未知"),
            "latest_version": ver_info.get("latest_version", "未知"),
            "has_update": ver_info.get("has_update", False),
            "before_total": 0,
            "after_total": 0,
            "diff_count": 0,
            "log": "",
            "error_message": "",
            "updated_at": ""
        }
    doc.pop('_id', None)
    doc["current_version"] = ver_info.get("current_version", doc.get("current_version", "未知"))
    doc["latest_version"] = ver_info.get("latest_version", doc.get("latest_version", "未知"))
    doc["has_update"] = ver_info.get("has_update", False)
    return doc


def run_community_sync_worker(mode: str = "online", offline_zip_path: str = None):
    """
    官方社区模板后台同步工作线程：
    支持 GitHub 镜像加速下载、版本与差量双重校验、离线 ZIP 覆盖及 Worker 容器协同广播
    """
    col = utils.conn_db('nuclei_sync_log')
    start_time = utils.curr_date()
    ver_info = get_nuclei_template_version_info()
    c_dir = get_community_templates_dir() or "/root/nuclei-templates"

    before_list = load_community_index(force_refresh=False)
    before_total = len(before_list)

    sync_state = {
        "status": "syncing",
        "sync_mode": mode,
        "start_time": start_time,
        "end_time": "",
        "current_version": ver_info.get("current_version", "未知"),
        "latest_version": ver_info.get("latest_version", "未知"),
        "has_update": ver_info.get("has_update", False),
        "before_total": before_total,
        "after_total": before_total,
        "diff_count": 0,
        "log": f"[{datetime.now().strftime('%H:%M:%S')}] 🚀 开始启动官方社区模板同步任务 (模式: {mode})...\n",
        "error_message": "",
        "updated_at": start_time
    }
    col.update_one({'_id': 'latest_sync'}, {'$set': sync_state}, upsert=True)

    def _append_log(msg: str):
        line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n"
        sync_state["log"] += line
        logger.info(f"[NucleiSync] {msg}")
        col.update_one({'_id': 'latest_sync'}, {
            '$set': {'log': sync_state["log"], 'updated_at': utils.curr_date()}
        })

    success = False
    error_msg = ""
    updated_version = ver_info.get("latest_version", ver_info.get("current_version", "未知"))

    try:
        if mode == "offline_zip":
            _append_log(f"📦 正在解析本地离线模板 ZIP 包: {offline_zip_path}")
            if not offline_zip_path or not os.path.isfile(offline_zip_path):
                raise Exception("未找到有效的离线模板 ZIP 文件")

            count = extract_templates_zip_to_dir(offline_zip_path, c_dir)
            _append_log(f"✅ 离线模板解压完成，成功覆盖解包 {count} 个文件")
            success = True

        else:
            _append_log(f"🌐 探测当前模板状态: 本地版本 [{ver_info.get('current_version')}], 官方最新 [{ver_info.get('latest_version')}]")
            _append_log("⚡ 启动多通道 GitHub 镜像加速下载链路...")

            mirrors = [
                "https://ghfast.top/",
                "https://ghproxy.net/"
            ]
            try:
                from app.services.proxy_service import resolve_proxy_url, resolve_requests_proxies, mask_proxy_url_secret
                intel_proxy = resolve_proxy_url(domain="intel", target_url="https://github.com/")
            except Exception:
                resolve_requests_proxies = None
                mask_proxy_url_secret = None
                intel_proxy = ""
            if intel_proxy:
                mirrors = [""] + mirrors
                masked_proxy = mask_proxy_url_secret(intel_proxy) if mask_proxy_url_secret else intel_proxy
                _append_log(f"🌐 检测到 intel 域系统代理 [{masked_proxy}]，优先直连 GitHub 官方源（支持回退国内镜像）")
            latest_tag = ver_info.get('latest_version') or 'v10.5.0'
            candidate_raw_urls = [
                f"https://github.com/projectdiscovery/nuclei-templates/archive/refs/tags/{latest_tag}.zip",
                "https://github.com/projectdiscovery/nuclei-templates/releases/latest/download/nuclei-templates.zip"
            ]

            tmp_download = os.path.join(Config.TMP_PATH, f"nuclei_release_{utils.random_choices(8)}.zip")
            downloaded = False

            for raw_url in candidate_raw_urls:
                if downloaded:
                    break
                for mirror in mirrors:
                    target_url = f"{mirror}{raw_url}"
                    source_label = "GitHub 官方直连(经代理)" if not mirror else f"镜像源 [{mirror}]"
                    _append_log(f"🔗 尝试从 {source_label} 下载: {os.path.basename(raw_url)}...")
                    try:
                        t0 = time.time()
                        req_proxies = resolve_requests_proxies(target_url=target_url, domain="intel") if resolve_requests_proxies else None
                        resp = requests.get(
                            target_url,
                            stream=True,
                            timeout=60,
                            verify=False,
                            allow_redirects=True,
                            proxies=req_proxies,
                            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                        )
                        if resp.status_code == 200:
                            total_bytes = 0
                            with open(tmp_download, "wb") as f:
                                for chunk in resp.iter_content(chunk_size=128 * 1024):
                                    if chunk:
                                        f.write(chunk)
                                        total_bytes += len(chunk)
                            cost = round(time.time() - t0, 2)
                            size_mb = round(total_bytes / (1024 * 1024), 2)
                            _append_log(f"✅ {source_label} 下载成功！包体积: {size_mb} MB，耗时: {cost}s")
                            downloaded = True
                            break
                        else:
                            _append_log(f"⚠️ {source_label} 返回非 200 响应: HTTP {resp.status_code}，切换下一个...")
                    except Exception as ex:
                        _append_log(f"⚠️ {source_label} 连接异常: {ex}，切换下一个...")

            if downloaded and os.path.exists(tmp_download):
                _append_log(f"📂 正在解压覆盖到官方模板目录: {c_dir}")
                extracted_cnt = extract_templates_zip_to_dir(tmp_download, c_dir)
                _append_log(f"✅ 解压完成，已原子更新 {extracted_cnt} 个模板相关文件")
                success = True
                try:
                    os.unlink(tmp_download)
                except Exception:
                    pass
            else:
                _append_log("⚠️ 下载通道受阻，尝试执行 nuclei 原生 CLI 更新指令作为兜底...")
                cmd = ["nuclei", "-ut", "-ud", c_dir, "-duc=false"]
                cmd_env = os.environ.copy()
                if intel_proxy:
                    cmd_env["HTTP_PROXY"] = intel_proxy
                    cmd_env["HTTPS_PROXY"] = intel_proxy
                    cmd_env["ALL_PROXY"] = intel_proxy
                _append_log(f"执行命令: {' '.join(cmd)}")
                proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120, env=cmd_env)
                combined_output = (proc.stdout or "") + "\n" + (proc.stderr or "")
                _append_log(f"CLI 输出:\n{combined_output.strip()}")

                bad_keywords = ["failed to update", "failed to download", "deadline exceeded", "timeout", "Client.Timeout"]
                has_fatal_error = any(bk in combined_output for bk in bad_keywords)

                if has_fatal_error:
                    raise Exception(f"Nuclei CLI 原生更新失败 (网络超时或被重置): {combined_output[:180]}")
                else:
                    success = True

        if success:
            if ver_info.get("latest_version") and ver_info.get("latest_version") != "未知":
                updated_version = ver_info.get("latest_version")
                update_templates_config_version(updated_version)
                _append_log(f"🏷️ 本地版本标记已同步跃升至: {updated_version}")

            _append_log("🔄 正在重新加载内存模板索引并核算差量...")
            after_list = load_community_index(force_refresh=True)
            after_total = len(after_list)
            diff_cnt = after_total - before_total
            _append_log(f"📊 模板索引刷新成功: 更新前 {before_total} 条 -> 更新后 {after_total} 条 (增量: {'+' if diff_cnt >= 0 else ''}{diff_cnt} 条)")

            try:
                from app.celerytask import celery
                celery.send_task('app.celerytask.nuclei_template_sync_task', queue='arltask_light')
                _append_log("📡 已向 Celery 发送 Worker 协同更新指令，保持后台扫描与面板一致")
            except Exception as e:
                _append_log(f"ℹ️ Worker 协同广播提示: {e}")

            sync_state["status"] = "success"
            sync_state["after_total"] = after_total
            sync_state["diff_count"] = diff_cnt
            sync_state["current_version"] = updated_version
            sync_state["has_update"] = False
            sync_state["cache_epoch"] = time.time()
            _append_log("🎉 官方社区模板库同步完成！")

    except Exception as e:
        error_msg = str(e)
        logger.exception(f"Nuclei sync worker error: {e}")
        _append_log(f"❌ 同步流程异常终止: {error_msg}")
        sync_state["status"] = "failed"
        sync_state["error_message"] = error_msg
    finally:
        sync_state["end_time"] = utils.curr_date()
        sync_state["updated_at"] = utils.curr_date()
        col.update_one({'_id': 'latest_sync'}, {'$set': sync_state})
        if offline_zip_path and os.path.exists(offline_zip_path):
            try:
                os.unlink(offline_zip_path)
            except Exception:
                pass
