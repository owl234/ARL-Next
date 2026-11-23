import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
START_PROD = REPO_ROOT / "start-prod.sh"
START_WEB = REPO_ROOT / "backend" / "start_web_prod.sh"
COMPOSE_PROD = REPO_ROOT / "docker-compose.prod.yml"


def _extract_bash_functions(script_text: str, names: list[str]) -> str:
    lines = script_text.splitlines()
    blocks: list[str] = []
    for name in names:
        pattern = re.compile(rf"^{re.escape(name)}\(\)\s*\{{\s*$")
        start_idx = next((i for i, l in enumerate(lines) if pattern.match(l)), None)
        assert start_idx is not None, f"未在 start-prod.sh 中找到函数: {name}"

        end_idx = None
        heredoc_delim = None
        for idx in range(start_idx + 1, len(lines)):
            line = lines[idx]
            if heredoc_delim is not None:
                if line == heredoc_delim:
                    heredoc_delim = None
                continue
            hd = re.search(r"<<-?\s*['\"]?([A-Za-z_][A-Za-z0-9_]*)['\"]?\s*$", line)
            if hd:
                heredoc_delim = hd.group(1)
                continue
            if line == "}":
                end_idx = idx
                break
        assert end_idx is not None, f"函数 {name} 未找到闭合花括号"
        blocks.append("\n".join(lines[start_idx : end_idx + 1]))
    return "\n\n".join(blocks)


def _write_exec(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def _run_start_prod_funcs(
    tmp_path: Path,
    func_names: list[str],
    body: str,
    *,
    bin_dir: Path | None = None,
    env_extra: dict[str, str] | None = None,
    isolated_path: bool = False,
) -> subprocess.CompletedProcess:
    extracted = _extract_bash_functions(START_PROD.read_text(encoding="utf-8"), func_names)
    runner = f"#!/bin/bash\nset -e\n{extracted}\n{body}\n"

    env = os.environ.copy()
    if isolated_path:
        safe_bin = tmp_path / "safe_bin"
        safe_bin.mkdir(exist_ok=True)
        for tool in ("bash", "sh", "awk", "cat", "chmod", "grep", "printf", "sed", "tr", "umask", "env"):
            resolved = shutil.which(tool)
            if resolved and not (safe_bin / tool).exists():
                (safe_bin / tool).symlink_to(resolved)
        env["PATH"] = f"{bin_dir}:{safe_bin}" if bin_dir else str(safe_bin)
    elif bin_dir:
        env["PATH"] = f"{bin_dir}:/usr/bin:/bin:/usr/sbin:/sbin"

    if env_extra:
        env.update(env_extra)

    return subprocess.run(
        ["bash", "-c", runner],
        cwd=str(tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )


def test_compose_prod_memory_profile_and_oom_hierarchy():
    data = yaml.safe_load(COMPOSE_PROD.read_text(encoding="utf-8"))
    services = data["services"]

    # 1. Web workers 参数化，默认 4
    web_env = services["arl-web"]["environment"]
    assert "ARL_WEB_WORKERS=${ARL_WEB_WORKERS:-4}" in web_env

    # 2. Puppeteer 启用 init: true、参数化轮转上限、oom_score_adj 高于 worker 扫描基线(500)
    puppeteer = services["arl-puppeteer"]
    worker = services["arl-worker"]
    assert puppeteer.get("init") is True
    assert puppeteer["oom_score_adj"] == 600
    assert puppeteer["oom_score_adj"] > worker["oom_score_adj"]
    assert "PUPPETEER_MAX_REQUESTS=${PUPPETEER_MAX_REQUESTS:-200}" in puppeteer["environment"]

    # 3. MongoDB 参数化 WiredTiger 缓存，持久化卷名保持向下兼容不变
    mongo = services["mongodb"]
    assert mongo["command"] == ["--wiredTigerCacheSizeGB", "${MONGO_WT_CACHE_GB:-1}"]
    assert "mongo_data_v7:/data/db" in mongo["volumes"]
    assert "mongo_data_v7" in data["volumes"]


def test_start_web_prod_workers_validation_and_preload():
    syntax = subprocess.run(["bash", "-n", str(START_WEB)], capture_output=True, text=True)
    assert syntax.returncode == 0, syntax.stderr
    text = START_WEB.read_text(encoding="utf-8")
    assert "gunicorn --preload" in text

    # 提取校验片段独立测试各种边界输入
    snippet = "\n".join(
        line for line in text.splitlines()
        if not line.strip().startswith("gunicorn")
    )
    match = re.search(r'(WEB_WORKERS="\$\{ARL_WEB_WORKERS:-4\}".*?^fi)', snippet, re.S | re.M)
    assert match is not None
    guard_code = match.group(1)

    cases = [
        ("", "4"),
        ("2", "2"),
        ("1", "1"),
        ("0", "4"),
        ("-3", "4"),
        ("abc", "4"),
        ("32", "16"),
    ]
    for raw, expected in cases:
        env = os.environ.copy()
        if raw == "":
            env.pop("ARL_WEB_WORKERS", None)
        else:
            env["ARL_WEB_WORKERS"] = raw
        proc = subprocess.run(
            ["bash", "-c", f"{guard_code}\nprintf '%s' \"$WEB_WORKERS\""],
            env=env,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        assert proc.stdout.splitlines()[-1] == expected, f"raw={raw!r} got={proc.stdout!r}"


def test_configure_memory_profile_low_mem_populates_only_missing_keys(tmp_path):
    env_file = tmp_path / ".env"

    # 1. 全新 4G 宿主机（3914MB）：自动创建 0600 权限 .env 并补齐三项参数
    proc = _run_start_prod_funcs(
        tmp_path,
        ["ensure_env_default", "configure_memory_profile"],
        "configure_memory_profile",
        env_extra={"ARL_HOST_MEM_MB": "3914", "ARL_ENV_FILE": str(env_file)},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert env_file.is_file()
    assert (env_file.stat().st_mode & 0o777) == 0o600
    content = env_file.read_text(encoding="utf-8")
    assert "ARL_WEB_WORKERS=2" in content
    assert "MONGO_WT_CACHE_GB=0.5" in content
    assert "PUPPETEER_MAX_REQUESTS=100" in content

    # 2. 用户已自定义某项值（含 export 写法）时绝不覆盖
    env_file2 = tmp_path / ".env.custom"
    env_file2.write_text(
        "ARL_ADMIN_PASSWORD=keep_secret_value_1234\n"
        "export ARL_WEB_WORKERS=3\n"
        "# MONGO_WT_CACHE_GB=2\n",
        encoding="utf-8",
    )
    proc2 = _run_start_prod_funcs(
        tmp_path,
        ["ensure_env_default", "configure_memory_profile"],
        "configure_memory_profile",
        env_extra={"ARL_HOST_MEM_MB": "4096", "ARL_ENV_FILE": str(env_file2)},
    )
    assert proc2.returncode == 0, proc2.stdout + proc2.stderr
    content2 = env_file2.read_text(encoding="utf-8")
    assert "ARL_ADMIN_PASSWORD=keep_secret_value_1234" in content2
    assert "export ARL_WEB_WORKERS=3" in content2
    assert "ARL_WEB_WORKERS=2" not in content2
    assert "MONGO_WT_CACHE_GB=0.5" in content2
    assert "PUPPETEER_MAX_REQUESTS=100" in content2


def test_configure_memory_profile_high_mem_skips_low_mem_overrides(tmp_path):
    env_file = tmp_path / ".env"
    proc = _run_start_prod_funcs(
        tmp_path,
        ["ensure_env_default", "configure_memory_profile"],
        "configure_memory_profile",
        env_extra={"ARL_HOST_MEM_MB": "8192", "ARL_ENV_FILE": str(env_file)},
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert not env_file.exists()
    assert "宿主机内存充裕" in proc.stdout


def test_tune_system_kernel_parameters_conntrack_raise_and_preserve_higher(tmp_path):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    sysctl_log = tmp_path / "sysctl.log"
    _write_exec(
        bin_dir / "sysctl",
        f"#!/bin/bash\nprintf '%s\\n' \"$*\" >> {str(sysctl_log)!r}\nexit 0\n",
    )

    sysctl_dir = tmp_path / "sysctl.d"
    sysctl_dir.mkdir()
    nf_dir = tmp_path / "netfilter"
    nf_dir.mkdir()
    (nf_dir / "nf_conntrack_max").write_text("65536\n", encoding="utf-8")

    proc = _run_start_prod_funcs(
        tmp_path,
        ["tune_system_kernel_parameters"],
        "tune_system_kernel_parameters",
        bin_dir=bin_dir,
        env_extra={
            "ARL_SYSCTL_DIR": str(sysctl_dir),
            "ARL_PROC_NETFILTER_DIR": str(nf_dir),
        },
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    tuning = (sysctl_dir / "99-arl-tuning.conf").read_text(encoding="utf-8")
    assert "vm.swappiness = 10" in tuning
    assert "net.netfilter.nf_conntrack_max = 262144" in tuning
    assert "net.netfilter.nf_conntrack_tcp_timeout_established = 600" in tuning
    assert "net.netfilter.nf_conntrack_tcp_timeout_time_wait = 30" in tuning

    # 已配置更大上限（524288）时绝不缩容
    (nf_dir / "nf_conntrack_max").write_text("524288\n", encoding="utf-8")
    proc2 = _run_start_prod_funcs(
        tmp_path,
        ["tune_system_kernel_parameters"],
        "tune_system_kernel_parameters",
        bin_dir=bin_dir,
        env_extra={
            "ARL_SYSCTL_DIR": str(sysctl_dir),
            "ARL_PROC_NETFILTER_DIR": str(nf_dir),
        },
    )
    assert proc2.returncode == 0
    tuning2 = (sysctl_dir / "99-arl-tuning.conf").read_text(encoding="utf-8")
    assert "net.netfilter.nf_conntrack_max = 524288" in tuning2

    # 无 nf_conntrack 目录时优雅跳过连接表调优，不报错
    proc3 = _run_start_prod_funcs(
        tmp_path,
        ["tune_system_kernel_parameters"],
        "tune_system_kernel_parameters",
        bin_dir=bin_dir,
        env_extra={
            "ARL_SYSCTL_DIR": str(sysctl_dir),
            "ARL_PROC_NETFILTER_DIR": str(tmp_path / "missing_nf"),
        },
    )
    assert proc3.returncode == 0
    tuning3 = (sysctl_dir / "99-arl-tuning.conf").read_text(encoding="utf-8")
    assert "vm.swappiness = 10" in tuning3
    assert "nf_conntrack_max" not in tuning3


def test_configure_earlyoom_guard_systemd219_and_graceful_fallback(tmp_path):
    # 场景 1：已安装 earlyoom 的 Ubuntu/systemd 宿主机，校验配置内容且绝不使用 --now
    bin_ok = tmp_path / "bin_ok"
    bin_ok.mkdir()
    sc_log = tmp_path / "sc.log"
    _write_exec(bin_ok / "earlyoom", "#!/bin/bash\nexit 0\n")
    _write_exec(
        bin_ok / "systemctl",
        f"""#!/bin/bash
printf '%s\\n' "$*" >> {str(sc_log)!r}
for arg in "$@"; do
    [ "$arg" = "--now" ] && exit 1
    [ "$arg" = "--value" ] && exit 1
done
exit 0
""",
    )
    default_dir = tmp_path / "etc_default"
    default_dir.mkdir()
    run_systemd = tmp_path / "run_systemd"
    run_systemd.mkdir()

    proc = _run_start_prod_funcs(
        tmp_path,
        ["run_cmd_with_timeout", "detect_os_and_pkg_manager", "configure_earlyoom_guard"],
        "configure_earlyoom_guard",
        bin_dir=bin_ok,
        isolated_path=True,
        env_extra={
            "ARL_SYSTEMD_RUN_DIR": str(run_systemd),
            "ARL_EARLYOOM_DEFAULT_DIR": str(default_dir),
            "ARL_EARLYOOM_SYSCONFIG_DIR": str(tmp_path / "no_sysconfig"),
        },
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    cfg = (default_dir / "earlyoom").read_text(encoding="utf-8")
    assert "--prefer '(chromium|chrome)'" in cfg
    assert "--avoid '(sshd|mongod|" in cfg
    sc_calls = sc_log.read_text(encoding="utf-8").splitlines()
    assert "enable earlyoom" in sc_calls
    assert "restart earlyoom" in sc_calls
    assert all("--now" not in c for c in sc_calls)

    # 场景 2：用户声明 ARL_EARLYOOM_CUSTOM=1 时保留自定义配置
    custom_text = "ARL_EARLYOOM_CUSTOM=1\nEARLYOOM_ARGS=\"-m 5\"\n"
    (default_dir / "earlyoom").write_text(custom_text, encoding="utf-8")
    proc_custom = _run_start_prod_funcs(
        tmp_path,
        ["run_cmd_with_timeout", "detect_os_and_pkg_manager", "configure_earlyoom_guard"],
        "configure_earlyoom_guard",
        bin_dir=bin_ok,
        isolated_path=True,
        env_extra={
            "ARL_SYSTEMD_RUN_DIR": str(run_systemd),
            "ARL_EARLYOOM_DEFAULT_DIR": str(default_dir),
            "ARL_EARLYOOM_SYSCONFIG_DIR": str(tmp_path / "no_sysconfig"),
        },
    )
    assert proc_custom.returncode == 0
    assert (default_dir / "earlyoom").read_text(encoding="utf-8") == custom_text

    # 场景 3：CentOS 7 / 无源导致 earlyoom 安装失败时必须优雅跳过，绝不阻断部署
    bin_miss = tmp_path / "bin_miss"
    bin_miss.mkdir()
    _write_exec(bin_miss / "systemctl", "#!/bin/bash\nexit 0\n")
    _write_exec(bin_miss / "yum", "#!/bin/bash\nexit 1\n")
    proc_miss = _run_start_prod_funcs(
        tmp_path,
        ["run_cmd_with_timeout", "detect_os_and_pkg_manager", "configure_earlyoom_guard"],
        "configure_earlyoom_guard",
        bin_dir=bin_miss,
        isolated_path=True,
        env_extra={
            "ARL_SYSTEMD_RUN_DIR": str(run_systemd),
            "ARL_EARLYOOM_DEFAULT_DIR": str(default_dir),
        },
    )
    assert proc_miss.returncode == 0, proc_miss.stdout + proc_miss.stderr
    assert "优雅跳过" in proc_miss.stdout
