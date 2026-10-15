import ipaddress
import json
import os
import shlex
import shutil
import subprocess
from functools import lru_cache

from app.config import Config
from app import utils

logger = utils.get_logger()


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


class NucleiScan(object):
    def __init__(self, targets: list, options: dict = None):
        self.targets = targets
        self.options = options or {}

        tmp_path = Config.TMP_PATH
        rand_str = utils.random_choices()

        self.nuclei_target_path = os.path.join(tmp_path,
                                               f"nuclei_target_{rand_str}.txt")

        self.nuclei_result_path = os.path.join(tmp_path,
                                               f"nuclei_result_{rand_str}.json")

        self.custom_templates_path = None
        self.nuclei_exclude_file = None
        self.nuclei_bin_path = "nuclei"

        # 在nuclei 2.9.1 中 将-json 参数改成了 -jsonl 参数。
        self.nuclei_json_flag = None

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
        """从数据库物化已启用的自建 Nuclei 模板到临时扫描目录"""
        try:
            nuclei_config = self.options.get("nuclei_config") or self.options.get("site_config", {}).get("nuclei_config") or {}
            mode = nuclei_config.get("custom_template_mode", "all_enabled")

            query = {"enable": True}
            if mode == "selected" and nuclei_config.get("selected_custom_templates"):
                query = {"template_id": {"$in": nuclei_config["selected_custom_templates"]}, "enable": True}
            elif mode == "tags" and nuclei_config.get("selected_tags"):
                query = {"tags": {"$in": nuclei_config["selected_tags"]}, "enable": True}

            col = utils.conn_db('nuclei_template')
            custom_docs = list(col.find(query))

            if custom_docs:
                rand_str = utils.random_choices(8)
                self.custom_templates_path = os.path.join(Config.TMP_PATH, f"nuclei_custom_{rand_str}")
                os.makedirs(self.custom_templates_path, exist_ok=True)

                written_cnt = 0
                for doc in custom_docs:
                    content = doc.get("content", "")
                    t_id = doc.get("template_id", "temp")
                    if content:
                        file_path = os.path.join(self.custom_templates_path, f"{t_id}.yaml")
                        with open(file_path, "w", encoding="utf-8") as f:
                            f.write(content)
                        written_cnt += 1

                logger.info(f"Materialized {written_cnt} custom nuclei templates to {self.custom_templates_path}")
        except Exception as e:
            logger.warning(f"Failed to materialize custom nuclei templates: {e}")

    def _prepare_exclude_file(self) -> str:
        """根据策略配置与全局黑名单生成 Nuclei 排除清单文件 (-eid)"""
        try:
            nuclei_config = self.options.get("nuclei_config") or self.options.get("site_config", {}).get("nuclei_config") or {}
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
        paths = [(self.nuclei_target_path, False), (self.nuclei_result_path, False),
                 (self.custom_templates_path, True), (self.nuclei_exclude_file, False)]
        for path, is_directory in paths:
            if not path:
                continue
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

    def _gen_target_file(self):
        with open(self.nuclei_target_path, "w") as f:
            for domain in self.targets:
                domain = domain.strip()
                if not domain:
                    continue
                f.write(domain + "\n")

    def dump_result(self) -> list:
        results = []
        if not os.path.exists(self.nuclei_result_path):
            return results

        with open(self.nuclei_result_path, "r", encoding="utf-8", errors="replace") as f:
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

    def exec_nuclei(self):
        self._gen_target_file()
        self._materialize_custom_templates()

        nuclei_config = self.options.get("nuclei_config") or self.options.get("site_config", {}).get("nuclei_config") or {}
        severities = nuclei_config.get("severity") or ["low", "medium", "high", "critical"]
        if isinstance(severities, list) and severities:
            sev_arg = "-severity " + ",".join([s.strip().lower() for s in severities if s.strip()])
        else:
            sev_arg = "-severity low,medium,high,critical"

        command = [
            shlex.quote(self.nuclei_bin_path), "-duc",
            "-tags cve,http",
            sev_arg,
            f"-l {self.nuclei_target_path}",
            self.nuclei_json_flag,
            "-stats",
            "-stats-interval 60",
            f"-o {self.nuclei_result_path}",
        ]

        # 若存在排除清单文件，拼接 -eid 参数排除误报模板
        exclude_file = self._prepare_exclude_file()
        if exclude_file and os.path.exists(exclude_file):
            command.append(f"-eid {exclude_file}")

        # 若存在物化的自建模板目录，拼接 -t 参数加载
        if self.custom_templates_path and os.path.exists(self.custom_templates_path):
            from app.routes.nuclei import get_community_templates_dir
            comm_dir = get_community_templates_dir()
            # 当显式指定 -t 自建模板时，Nuclei 默认只扫 -t 路径；
            # 若同时存在官方模板目录，一并注入保证社区底座不丢失
            if comm_dir:
                command.insert(2, f"-t {comm_dir}")
            command.insert(2, f"-t {self.custom_templates_path}")

        logger.info(" ".join(command))
        completed = utils.exec_system(command, timeout=15 * 24 * 60 * 60)
        if completed.returncode != 0:
            raise subprocess.CalledProcessError(completed.returncode, command)

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


def nuclei_scan(targets: list, options: dict = None):
    if not targets:
        return []

    n = NucleiScan(targets=targets, options=options)
    return n.run()
