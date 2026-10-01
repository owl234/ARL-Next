# backend/app/services/vuln_platform/nuclei_thread.py
"""Nuclei 扫描多线程任务"""

import time
import json
import subprocess

from app import utils
from app.services.baseThread import BaseThread

logger = utils.get_logger()


class NucleiScanThread(BaseThread):
    """Nuclei 多目标并发扫描"""

    def __init__(self, targets, scan_config,
                 project_fingerprint=None, source_platform=None,
                 concurrency=10):
        super().__init__(targets=targets, concurrency=concurrency)
        self.scan_config = scan_config or {}
        self.project_fingerprint = project_fingerprint
        self.source_platform = source_platform
        self.findings = []

    def work(self, target):
        """对单个目标执行 Nuclei 扫描"""
        cmd = self._build_cmd(target)
        try:
            logger.debug("[Nuclei] 扫描: {}".format(target))
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.scan_config.get("timeout_seconds", 600))
            findings = self._parse_output(result.stdout)
            if findings:
                for f in findings:
                    f["project_fingerprint"] = \
                        self.project_fingerprint
                    f["platform"] = self.source_platform
                    f["target_url"] = target
                self.findings.extend(findings)
                logger.info("[Nuclei] {} 发现 {} 个漏洞".format(
                    target, len(findings)))
        except subprocess.TimeoutExpired:
            logger.warning("[Nuclei] {} 扫描超时".format(target))
        except Exception as e:
            logger.warning("[Nuclei] {} 扫描异常: {}".format(
                target, e))

    def _build_cmd(self, target):
        cmd = [
            "nuclei",
            "-u", target,
            "-severity", self.scan_config.get(
                "nuclei_severity", "critical,high"),
            "-jsonl",
            "-silent",
            "-timeout", "10",
            "-retries", "1",
        ]
        tags = self.scan_config.get("nuclei_tags")
        if tags:
            cmd.extend(["-tags", tags])
        return cmd

    def _parse_output(self, stdout):
        findings = []
        for line in stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                findings.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return findings

    def run(self):
        t1 = time.time()
        logger.info("start nuclei scan, project:{}, targets:{}"
                    .format(self.project_fingerprint,
                            len(self.targets)))
        self._run()
        elapse = time.time() - t1
        logger.info("end nuclei scan ({:.2f}s), findings:{}"
                    .format(elapse, len(self.findings)))
        return self.findings


def nuclei_scan_thread(targets, scan_config,
                        project_fingerprint=None,
                        source_platform=None, concurrency=10):
    t = NucleiScanThread(
        targets=targets,
        scan_config=scan_config,
        project_fingerprint=project_fingerprint,
        source_platform=source_platform,
        concurrency=concurrency)
    return t.run()