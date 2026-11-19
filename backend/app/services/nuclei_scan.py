import ipaddress
import json
import os
import shlex
import shutil
import subprocess
from functools import lru_cache
from urllib.parse import urlparse

from app.config import Config
from app import utils

logger = utils.get_logger()

_ASM_WEB_PROTOCOLS = frozenset({"http", "requests", "websocket"})
_ASM_NETWORK_PROTOCOLS = frozenset({"tcp", "network", "ssl", "javascript"})
_ASM_DNS_PROTOCOLS = frozenset({"dns", "whois"})
_ASM_UNSUPPORTED_PROTOCOLS = frozenset({"code", "headless", "file", "workflows"})
_VALID_NUCLEI_SEVERITIES = frozenset({"critical", "high", "medium", "low", "info"})
_KNOWN_YAML_PROTOCOLS = (
    "http", "requests", "websocket",
    "tcp", "network", "ssl", "javascript",
    "dns", "whois",
    "code", "headless", "file", "workflows",
)


def _classify_protocol_bucket(protocol) -> str:
    if isinstance(protocol, (list, tuple, set, frozenset)):
        protos = [str(p or "").strip().lower() for p in protocol if str(p or "").strip()] or ["http"]
    else:
        protos = [str(protocol or "http").strip().lower()]
    if any(p in _ASM_UNSUPPORTED_PROTOCOLS for p in protos):
        return "unsupported"
    proto = protos[0]
    if proto in _ASM_WEB_PROTOCOLS:
        return "web"
    if proto in _ASM_NETWORK_PROTOCOLS:
        return "network"
    if proto in _ASM_DNS_PROTOCOLS:
        return "dns"
    return "web"


def _detect_doc_protocols(doc: dict) -> list:
    """提取模板文档中全部协议块（优先解析 YAML 内容以防多协议模板伪装绕过受限协议拦截）。"""
    found = []
    content = doc.get("content") or ""
    if content:
        try:
            import yaml
            parsed = yaml.safe_load(content)
            if isinstance(parsed, dict):
                for p in _KNOWN_YAML_PROTOCOLS:
                    val = parsed.get(p)
                    if isinstance(val, (list, dict)) and len(val) > 0:
                        np = "http" if p == "requests" else p
                        if np not in found:
                            found.append(np)
        except Exception:
            pass

    raw_list = doc.get("protocols")
    if isinstance(raw_list, list):
        for p in raw_list:
            np = "http" if str(p or "").strip().lower() == "requests" else str(p or "").strip().lower()
            if np and np not in found:
                found.append(np)

    proto = str(doc.get("protocol") or "").strip().lower()
    if proto:
        np = "http" if proto == "requests" else proto
        if np not in found:
            found.append(np)

    return found or ["http"]


def _detect_doc_protocol(doc: dict) -> str:
    protos = _detect_doc_protocols(doc)
    for p in protos:
        if p in _ASM_UNSUPPORTED_PROTOCOLS:
            return p
    return protos[0]


def _is_ip_literal(value: str) -> bool:
    if not value:
        return False
    try:
        ipaddress.ip_address(value.strip("[]"))
        return True
    except ValueError:
        return False


def _clean_targets(raw_targets) -> list:
    seen = set()
    cleaned = []
    for item in raw_targets or []:
        val = str(item or "").strip()
        if val and val not in seen:
            seen.add(val)
            cleaned.append(val)
    return cleaned


def _extract_dns_targets(web_targets: list, extra_dns: list) -> list:
    seen = set()
    domains = []
    for item in extra_dns or []:
        dom = str(item or "").strip().rstrip(".").lower()
        if dom and not _is_ip_literal(dom) and dom not in seen:
            seen.add(dom)
            domains.append(dom)

    for raw in web_targets or []:
        target = str(raw or "").strip()
        if not target:
            continue
        parsed = urlparse(target if "://" in target else f"http://{target}")
        host = (parsed.hostname or "").strip("[]").rstrip(".").lower()
        if host and not _is_ip_literal(host) and host not in seen:
            seen.add(host)
            domains.append(host)
    return domains


def _get_community_templates_dir() -> str:
    try:
        from app.services.nuclei_template_service import get_community_templates_dir
        return get_community_templates_dir() or ""
    except Exception:
        pass
    try:
        from app.routes.nuclei import get_community_templates_dir
        return get_community_templates_dir() or ""
    except Exception:
        return ""


@lru_cache(maxsize=8)
def _detect_json_flag(binary_identity):
    """仅缓存成功检测；进程或可执行文件变化后使用新的缓存键。"""
    binary_path = binary_identity[1]
    for flag in ("-jsonl", "-json"):
        result = subprocess.run([binary_path, "-duc", flag, "-version"],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        if result.returncode == 0:
            return flag

    # 保留原有区别：无法运行的引擎跳过，能运行但不支持 JSON 的引擎报错。
    result = subprocess.run([binary_path, "-version"],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
    if result.returncode != 0:
        raise OSError("Nuclei version check failed")
    raise RuntimeError("Nuclei does not support -jsonl or -json")


def resolve_nuclei_proxy(targets):
    """按 scan 域代理策略解析 Nuclei 可用代理及脱敏字符串。"""
    nuclei_proxy = ""
    masked_proxy = ""
    try:
        from app.services.proxy_service import (
            load_proxy_config,
            mask_proxy_url_secret,
            resolve_proxy_url,
            should_bypass_url,
        )
        proxy_cfg = load_proxy_config()
        scan_pol = (proxy_cfg.get("policies") or {}).get("scan") or {}
        if scan_pol.get("apply_to_nuclei", True):
            non_bypassed = [
                t for t in (targets or [])
                if not should_bypass_url(str(t), proxy_cfg.get("bypass"), domain="scan")
            ]
            if non_bypassed or not targets:
                raw_proxy = resolve_proxy_url(domain="scan")
                if raw_proxy:
                    # Go/Nuclei dialer expects socks5:// rather than socks5h://
                    if raw_proxy.lower().startswith("socks5h://"):
                        nuclei_proxy = "socks5://" + raw_proxy[len("socks5h://"):]
                    else:
                        nuclei_proxy = raw_proxy
                    masked_proxy = mask_proxy_url_secret(nuclei_proxy)
    except Exception as exc:
        logger.debug(f"resolve nuclei proxy failed: {exc}")
    return nuclei_proxy, masked_proxy


def _partition_nuclei_targets_by_proxy(targets):
    """将目标按代理旁路规则拆分为 (需走代理目标列表, 直连旁路目标列表)。"""
    cleaned = list(targets or [])
    if not cleaned:
        return [], []
    try:
        from app.services.proxy_service import load_proxy_config, should_bypass_url
        proxy_cfg = load_proxy_config()
        scan_pol = (proxy_cfg.get("policies") or {}).get("scan") or {}
        if not scan_pol.get("apply_to_nuclei", True):
            return [], cleaned
        bypass_cfg = proxy_cfg.get("bypass")
        proxied = []
        direct = []
        for t in cleaned:
            if should_bypass_url(str(t), bypass_cfg, domain="scan"):
                direct.append(t)
            else:
                proxied.append(t)
        return proxied, direct
    except Exception:
        return cleaned, []


def _dir_has_yaml_templates(directory: str) -> bool:
    if not directory or not os.path.isdir(directory):
        return False
    for _, _, files in os.walk(directory):
        if any(name.endswith((".yaml", ".yml")) for name in files):
            return True
    return False


class NucleiScan(object):
    def __init__(self, targets: list, options: dict = None, extra_targets: dict = None):
        self.targets = targets or []
        self.options = options or {}
        self.extra_targets = extra_targets if isinstance(extra_targets, dict) else {}

        tmp_path = Config.TMP_PATH
        rand_str = utils.random_choices()

        self.nuclei_target_path = os.path.join(tmp_path,
                                               f"nuclei_target_{rand_str}.txt")

        self.nuclei_result_path = os.path.join(tmp_path,
                                               f"nuclei_result_{rand_str}.json")
        self.nuclei_custom_result_path = None

        self.custom_templates_path = None
        self.nuclei_exclude_file = None
        self.nuclei_bin_path = "nuclei"

        # 按协议桶物化的自建模板目录与执行通道追踪
        self._custom_bucket_dirs = {}
        self._custom_bucket_counts = {}
        self._custom_skipped_unsupported = []
        self._extra_tmp_files = []
        self._result_sources = []

        # 在nuclei 2.9.1 中 将-json 参数改成了 -jsonl 参数。
        self.nuclei_json_flag = None

    def _get_nuclei_config(self) -> dict:
        cfg = self.options.get("nuclei_config")
        if isinstance(cfg, dict) and cfg:
            return cfg
        site_cfg = self.options.get("site_config")
        if isinstance(site_cfg, dict) and isinstance(site_cfg.get("nuclei_config"), dict):
            return site_cfg["nuclei_config"]
        return cfg if isinstance(cfg, dict) else {}

    def _check_json_flag(self):
        binary_path = shutil.which(self.nuclei_bin_path)
        if not binary_path:
            raise FileNotFoundError("Nuclei executable not found")
        binary_path = os.path.realpath(binary_path)
        stat = os.stat(binary_path)
        identity = (os.getpid(), binary_path, stat.st_dev, stat.st_ino,
                    stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns)
        self.nuclei_json_flag = _detect_json_flag(identity)
        # 检测和实际扫描使用同一可执行文件，避免 PATH 顺序变化。
        self.nuclei_bin_path = binary_path

    def _materialize_custom_templates(self):
        """从数据库物化已启用的自建 Nuclei 模板，按协议自动分桶（web / network / dns）。"""
        self._custom_bucket_dirs = {}
        self._custom_bucket_counts = {}
        self._custom_skipped_unsupported = []
        self.custom_templates_path = None

        try:
            nuclei_config = self._get_nuclei_config()
            mode = str(nuclei_config.get("custom_template_mode") or "all_enabled").strip().lower()
            if mode == "none":
                return

            query = {"enable": True}
            if mode == "selected":
                selected_ids = [
                    str(x).strip()
                    for x in (nuclei_config.get("selected_custom_templates") or [])
                    if str(x).strip()
                ]
                if not selected_ids:
                    return
                query = {"template_id": {"$in": selected_ids}, "enable": True}
            elif mode == "tags":
                selected_tags = [
                    str(x).strip().lower()
                    for x in (nuclei_config.get("selected_tags") or [])
                    if str(x).strip()
                ]
                if not selected_tags:
                    return
                query = {"tags": {"$in": selected_tags}, "enable": True}

            extra_exclude = {
                str(eid).strip().lower()
                for eid in (nuclei_config.get("extra_exclude_ids") or [])
                if eid and isinstance(eid, str) and eid.strip()
            }

            col = utils.conn_db('nuclei_template')
            custom_docs = list(col.find(query))
            if not custom_docs:
                return

            bucket_docs = {"web": [], "network": [], "dns": []}
            for doc in custom_docs:
                content = doc.get("content", "")
                if not content or not str(content).strip():
                    continue
                raw_tid = str(doc.get("template_id") or "").strip()
                if extra_exclude and raw_tid.lower() in extra_exclude:
                    continue

                proto = _detect_doc_protocol(doc)
                bucket = _classify_protocol_bucket(proto)
                if bucket == "unsupported":
                    self._custom_skipped_unsupported.append((raw_tid or "unknown", proto))
                    continue
                bucket_docs[bucket].append(doc)

            if self._custom_skipped_unsupported:
                skipped_desc = ", ".join(f"{tid}({proto})" for tid, proto in self._custom_skipped_unsupported[:10])
                suffix = f" 等共 {len(self._custom_skipped_unsupported)} 条" if len(self._custom_skipped_unsupported) > 10 else ""
                logger.warning(
                    f"Skipped {len(self._custom_skipped_unsupported)} custom nuclei template(s) with unsupported ASM protocol "
                    f"(code/headless/file/workflows): {skipped_desc}{suffix}"
                )

            total_written = 0
            for bucket in ("web", "network", "dns"):
                docs_in_bucket = bucket_docs[bucket]
                if not docs_in_bucket:
                    continue

                rand_str = utils.random_choices(8)
                dir_prefix = "nuclei_custom" if bucket == "web" else f"nuclei_custom_{bucket}"
                bucket_dir = os.path.join(Config.TMP_PATH, f"{dir_prefix}_{rand_str}")
                os.makedirs(bucket_dir, exist_ok=True)

                written_cnt = 0
                used_names = set()
                for idx, doc in enumerate(docs_in_bucket):
                    content = doc.get("content", "")
                    t_id = os.path.basename(str(doc.get("template_id") or "temp")).strip()
                    if t_id in ("", ".", ".."):
                        t_id = f"temp_{idx}"
                    fname = f"{t_id}.yaml"
                    if fname.lower() in used_names:
                        fname = f"{t_id}_{idx}.yaml"
                    used_names.add(fname.lower())
                    file_path = os.path.join(bucket_dir, fname)
                    with open(file_path, "w", encoding="utf-8") as f:
                        f.write(content)
                    written_cnt += 1

                if written_cnt > 0:
                    self._custom_bucket_dirs[bucket] = bucket_dir
                    self._custom_bucket_counts[bucket] = written_cnt
                    total_written += written_cnt
                    if self.custom_templates_path is None:
                        self.custom_templates_path = bucket_dir
                else:
                    shutil.rmtree(bucket_dir, ignore_errors=True)

            if total_written > 0:
                bucket_summary = ", ".join(f"{b}={cnt}" for b, cnt in self._custom_bucket_counts.items())
                logger.info(f"Materialized {total_written} custom nuclei templates ({bucket_summary})")
        except Exception as e:
            logger.warning(f"Failed to materialize custom nuclei templates: {e}")

    def _prepare_exclude_file(self) -> str:
        """根据策略配置与全局黑名单生成社区模板排除清单文件 (-eid)"""
        try:
            nuclei_config = self._get_nuclei_config()
            exclude_blacklist = nuclei_config.get("exclude_blacklist", True)

            exclude_ids = set()
            if exclude_blacklist:
                docs = utils.conn_db('nuclei_blacklist').find({}, {"template_id": 1})
                for d in docs:
                    tid = d.get("template_id")
                    if tid and isinstance(tid, str) and tid.strip():
                        exclude_ids.add(tid.strip())

            extra_ids = nuclei_config.get("extra_exclude_ids") or []
            if isinstance(extra_ids, list):
                for eid in extra_ids:
                    if eid and isinstance(eid, str) and eid.strip():
                        exclude_ids.add(eid.strip())

            if exclude_ids:
                rand_str = utils.random_choices(8)
                self.nuclei_exclude_file = os.path.join(Config.TMP_PATH, f"nuclei_exclude_{rand_str}.txt")
                with open(self.nuclei_exclude_file, "w", encoding="utf-8") as f:
                    written_set = set()
                    for tid in sorted(exclude_ids):
                        for variant in [tid, tid.lower(), tid.upper()]:
                            if variant not in written_set:
                                f.write(variant + "\n")
                                written_set.add(variant)
                logger.info(f"Generated Nuclei exclude file with {len(written_set)} template entries: {self.nuclei_exclude_file}")
                return self.nuclei_exclude_file
        except Exception as e:
            logger.warning(f"Failed to prepare nuclei exclude file: {e}")
        return None

    def _delete_file(self):
        raw_paths = [
            (self.nuclei_target_path, False),
            (self.nuclei_result_path, False),
            (self.nuclei_custom_result_path, False),
            (self.custom_templates_path, True),
            (self.nuclei_exclude_file, False),
        ]
        for bdir in self._custom_bucket_dirs.values():
            raw_paths.append((bdir, True))
        for item in self._extra_tmp_files:
            raw_paths.append(item)

        seen = set()
        for path, is_directory in raw_paths:
            if not path or path in seen:
                continue
            seen.add(path)
            try:
                if is_directory:
                    shutil.rmtree(path)
                else:
                    os.unlink(path)
            except FileNotFoundError:
                pass
            except OSError as e:
                # 一个路径清理失败时继续处理其余路径，并保留原扫描异常。
                logger.warning(f"Failed to remove Nuclei temporary path {path}: {e}")

    def check_have_nuclei(self) -> bool:
        try:
            self._check_json_flag()
            return True
        except (OSError, subprocess.SubprocessError) as e:
            logger.debug(f"{e}")

        return False

    def _gen_target_file(self, targets=None, target_path=None):
        dest = target_path or self.nuclei_target_path
        target_list = self.targets if targets is None else targets
        with open(dest, "w", encoding="utf-8") as f:
            for domain in target_list:
                domain = str(domain).strip()
                if not domain:
                    continue
                f.write(domain + "\n")
        return dest

    def _parse_result_file(self, result_path: str, template_source: str = "community") -> list:
        results = []
        if not result_path or not os.path.exists(result_path):
            return results

        with open(result_path, "r", encoding="utf-8", errors="replace") as f:
            while True:
                line = f.readline()
                if not line:
                    break
                line = line.strip()
                if not line:
                    continue

                try:
                    data = json.loads(line)
                    target = _result_target(data)
                    item = {
                        "template_url": data.get("template-url", ""),
                        "template_id": data.get("template-id", ""),
                        "template_source": template_source,
                        "vuln_name": data.get("info", {}).get("name", ""),
                        "vuln_severity": data.get("info", {}).get("severity", ""),
                        "vuln_url": data.get("matched-at", ""),
                        "curl_command": data.get("curl-command", ""),
                        "target": target,
                        "host": target,
                        "extracted_results": data.get("extracted-results", [])
                    }
                    results.append(item)
                except Exception as e:
                    logger.debug(f"Failed to parse nuclei line: {e}")

        return results

    def dump_result(self) -> list:
        if self._result_sources:
            results = []
            for path, source in self._result_sources:
                results.extend(self._parse_result_file(path, template_source=source))
            return results

        results = self._parse_result_file(self.nuclei_result_path, template_source="community")
        if self.nuclei_custom_result_path:
            results.extend(self._parse_result_file(self.nuclei_custom_result_path, template_source="custom"))
        return results

    def _run_nuclei_command(self, result_path, *, template_dir=None, tags_arg=None,
                            sev_arg="-severity low,medium,high,critical",
                            exclude_file=None, target_path=None, nuclei_proxy="", masked_proxy=""):
        target_file = target_path or self.nuclei_target_path
        command = [
            shlex.quote(self.nuclei_bin_path), "-duc",
        ]
        if template_dir:
            command.append(f"-t {shlex.quote(template_dir)}")
        if tags_arg:
            command.append(tags_arg)
        if sev_arg:
            command.append(sev_arg)
        command.extend([
            f"-l {shlex.quote(target_file)}",
            self.nuclei_json_flag,
            "-stats",
            "-stats-interval 60",
            f"-o {shlex.quote(result_path)}",
        ])

        if exclude_file and os.path.exists(exclude_file):
            command.append(f"-eid {shlex.quote(exclude_file)}")

        if nuclei_proxy:
            if "@" in nuclei_proxy:
                proxy_file = os.path.join(Config.TMP_PATH, f"nuclei_proxy_{utils.random_choices(8)}.txt")
                fd = os.open(proxy_file, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
                with os.fdopen(fd, "w", encoding="utf-8") as pf:
                    pf.write(nuclei_proxy + "\n")
                self._extra_tmp_files.append((proxy_file, False))
                command.append(f"-proxy {shlex.quote(proxy_file)}")
            else:
                command.append(f"-proxy {shlex.quote(nuclei_proxy)}")

        masked_command = list(command)
        if nuclei_proxy and masked_proxy:
            masked_command = [
                part.replace(shlex.quote(nuclei_proxy), shlex.quote(masked_proxy)).replace(nuclei_proxy, masked_proxy)
                for part in masked_command
            ]
        log_cmd = " ".join(masked_command)
        if nuclei_proxy and masked_proxy and "@" in nuclei_proxy:
            log_cmd = f"{log_cmd} (proxy={masked_proxy})"
        logger.info(log_cmd)
        completed = utils.exec_system(command, timeout=15 * 24 * 60 * 60)
        if completed.returncode != 0:
            raise subprocess.CalledProcessError(completed.returncode, masked_command)

    def exec_nuclei(self):
        self._result_sources = []
        web_targets = _clean_targets(self.targets)
        if web_targets:
            self._gen_target_file(web_targets, self.nuclei_target_path)

        self._materialize_custom_templates()

        nuclei_config = self._get_nuclei_config()
        include_community = nuclei_config.get("include_community", True)
        if isinstance(include_community, str):
            include_community = include_community.strip().lower() not in ("false", "0", "no", "")
        else:
            include_community = bool(include_community)

        severities = nuclei_config.get("severity") or ["low", "medium", "high", "critical"]
        if isinstance(severities, list) and severities:
            cleaned_sevs = list(dict.fromkeys(
                str(s).strip().lower()
                for s in severities
                if str(s).strip().lower() in _VALID_NUCLEI_SEVERITIES
            ))
            sev_arg = "-severity " + ",".join(cleaned_sevs) if cleaned_sevs else "-severity low,medium,high,critical"
        else:
            sev_arg = "-severity low,medium,high,critical"

        exclude_file = self._prepare_exclude_file() if include_community else None

        # 组装独立的执行通道计划：社区通道与按协议分桶的自建通道互不干扰
        planned_runs = []
        has_custom_buckets = bool(self._custom_bucket_dirs)

        if include_community and web_targets:
            comm_dir = _get_community_templates_dir()
            if _dir_has_yaml_templates(comm_dir):
                planned_runs.append({
                    "name": "community",
                    "template_source": "community",
                    "template_dir": comm_dir,
                    "tags_arg": "-tags cve,http",
                    "sev_arg": sev_arg,
                    "exclude_file": exclude_file,
                    "targets": web_targets,
                    "use_primary_target": True,
                    "result_path": self.nuclei_result_path,
                })
            elif not has_custom_buckets:
                planned_runs.append({
                    "name": "community",
                    "template_source": "community",
                    "template_dir": None,
                    "tags_arg": "-tags cve,http",
                    "sev_arg": sev_arg,
                    "exclude_file": exclude_file,
                    "targets": web_targets,
                    "use_primary_target": True,
                    "result_path": self.nuclei_result_path,
                })
            else:
                logger.warning("Community nuclei templates directory is empty or unavailable; skipping community channel")

        network_targets = _clean_targets(web_targets + list(self.extra_targets.get("network") or []))
        dns_targets = _extract_dns_targets(web_targets, self.extra_targets.get("dns") or [])
        bucket_target_map = {
            "web": (web_targets, True),
            "network": (network_targets, False),
            "dns": (dns_targets, False),
        }

        for bucket in ("web", "network", "dns"):
            bucket_dir = self._custom_bucket_dirs.get(bucket)
            if not bucket_dir or not _dir_has_yaml_templates(bucket_dir):
                continue

            b_targets, use_primary = bucket_target_map[bucket]
            if not b_targets:
                logger.info(
                    f"Skipping custom nuclei [{bucket}] channel ({self._custom_bucket_counts.get(bucket, 0)} templates): "
                    f"no matching targets"
                )
                continue

            if not planned_runs:
                res_path = self.nuclei_result_path
            elif self.nuclei_custom_result_path is None:
                self.nuclei_custom_result_path = os.path.join(
                    Config.TMP_PATH, f"nuclei_custom_result_{utils.random_choices()}.json"
                )
                res_path = self.nuclei_custom_result_path
            else:
                res_path = os.path.join(
                    Config.TMP_PATH, f"nuclei_custom_{bucket}_result_{utils.random_choices()}.json"
                )
                self._extra_tmp_files.append((res_path, False))

            # 自建通道不套用社区 -tags cve,http、社区 -severity 与全局黑名单 -eid
            planned_runs.append({
                "name": f"custom:{bucket}",
                "template_source": "custom",
                "template_dir": bucket_dir,
                "tags_arg": None,
                "sev_arg": None,
                "exclude_file": None,
                "targets": b_targets,
                "use_primary_target": use_primary and b_targets == web_targets,
                "result_path": res_path,
            })

        if not planned_runs:
            logger.info(
                f"No runnable Nuclei scan channels (include_community={include_community}, "
                f"custom_buckets={dict(self._custom_bucket_counts)}, web_targets={len(web_targets)})"
            )
            return

        succeeded_runs = 0
        errors = []

        for run_spec in planned_runs:
            run_targets = run_spec["targets"]
            nuclei_proxy, masked_proxy = resolve_nuclei_proxy(run_targets)
            sub_batches = []
            if nuclei_proxy:
                proxied_t, direct_t = _partition_nuclei_targets_by_proxy(run_targets)
                if proxied_t and direct_t:
                    sub_batches.append((
                        f"{run_spec['name']}:proxy", proxied_t, False, nuclei_proxy, masked_proxy, run_spec["result_path"]
                    ))
                    direct_res_path = os.path.join(
                        Config.TMP_PATH,
                        f"nuclei_direct_{run_spec['name'].replace(':', '_')}_{utils.random_choices()}.json",
                    )
                    self._extra_tmp_files.append((direct_res_path, False))
                    sub_batches.append((
                        f"{run_spec['name']}:direct", direct_t, False, "", "", direct_res_path
                    ))
                elif proxied_t:
                    sub_batches.append((
                        run_spec["name"], proxied_t, run_spec["use_primary_target"], nuclei_proxy, masked_proxy, run_spec["result_path"]
                    ))
                else:
                    sub_batches.append((
                        run_spec["name"], direct_t or run_targets, run_spec["use_primary_target"], "", "", run_spec["result_path"]
                    ))
            else:
                sub_batches.append((
                    run_spec["name"], run_targets, run_spec["use_primary_target"], "", "", run_spec["result_path"]
                ))

            for batch_name, batch_targets, use_primary_flag, b_proxy, b_masked_proxy, b_res_path in sub_batches:
                if use_primary_flag and batch_targets == web_targets:
                    target_file = self.nuclei_target_path
                else:
                    target_file = os.path.join(
                        Config.TMP_PATH,
                        f"nuclei_target_{batch_name.replace(':', '_')}_{utils.random_choices()}.txt",
                    )
                    self._gen_target_file(batch_targets, target_file)
                    self._extra_tmp_files.append((target_file, False))

                try:
                    self._run_nuclei_command(
                        b_res_path,
                        template_dir=run_spec["template_dir"],
                        tags_arg=run_spec["tags_arg"],
                        sev_arg=run_spec["sev_arg"],
                        exclude_file=run_spec["exclude_file"],
                        target_path=target_file,
                        nuclei_proxy=b_proxy,
                        masked_proxy=b_masked_proxy,
                    )
                    succeeded_runs += 1
                    self._result_sources.append((b_res_path, run_spec["template_source"]))
                except Exception as exc:
                    logger.error(f"Nuclei channel [{batch_name}] execution failed: {exc}")
                    errors.append((batch_name, exc))

        if succeeded_runs == 0 and errors:
            raise errors[0][1]
        if errors:
            failed_names = ", ".join(name for name, _ in errors)
            logger.warning(
                f"Nuclei partial channel failure ({failed_names}); preserved findings from {succeeded_runs} succeeded channel(s)"
            )

    def run(self):
        if not self.check_have_nuclei():
            logger.warning("not found nuclei")
            return []

        self._check_json_flag()
        try:
            self.exec_nuclei()
            return self.dump_result()
        finally:
            self._delete_file()


def _result_target(data):
    # 新版 host 仅含主机名；url 保留协议、端口及原始目标路径。
    if data.get("url"):
        return data["url"]
    host = data.get("host") or ""
    port = data.get("port")
    if host and (port or data.get("scheme")) and "://" not in host:
        try:
            if ipaddress.ip_address(host.strip("[]")).version == 6:
                host = f"[{host.strip('[]')}]"
        except ValueError:
            pass
        # 兼容旧版已含端口的 host，避免重复拼接。
        if port and (":" not in host or host.endswith("]")):
            host = f"{host}:{port}"
    if host and data.get("scheme") and "://" not in host:
        host = f"{data['scheme']}://{host}"
    return host or data.get("matched-at", "")


def nuclei_scan(targets: list, options: dict = None, extra_targets: dict = None):
    has_extra = isinstance(extra_targets, dict) and any(extra_targets.get(k) for k in ("network", "dns"))
    if not targets and not has_extra:
        return []

    n = NucleiScan(targets=targets or [], options=options, extra_targets=extra_targets)
    return n.run()
