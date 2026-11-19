import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
START_PROD = REPO_ROOT / "start-prod.sh"


def _extract_bash_functions(script_text: str, names: list[str]) -> str:
    """从 start-prod.sh 原文精确抽取指定顶层 Bash 函数体，确保测试直接执行生产代码。"""
    lines = script_text.splitlines()
    blocks: list[str] = []
    for name in names:
        pattern = re.compile(rf"^{re.escape(name)}\(\)\s*\{{\s*$")
        start_idx = None
        for idx, line in enumerate(lines):
            if pattern.match(line):
                start_idx = idx
                break
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


def _make_systemd219_systemctl(
    bin_dir: Path,
    log_file: Path,
    *,
    main_pid: str = "0",
    show_rc: int = 0,
    show_raw_output: str | None = None,
    is_active_rc: int = 0,
) -> Path:
    """构造严格模拟 CentOS 7 systemd 219 行为的假 systemctl：拒绝 --value 与 --now。"""
    if show_raw_output is None:
        show_body = f'printf "MainPID=%s\\n" "{main_pid}"'
    else:
        show_body = f"printf '%s' {show_raw_output!r}"

    script = f"""#!/bin/bash
printf '%s\\n' "$*" >> {str(log_file)!r}
for arg in "$@"; do
    case "$arg" in
        --value|--now)
            echo "systemctl: unrecognized option '$arg'" >&2
            exit 1
            ;;
    esac
done
case "$1" in
    show)
        if [ "{show_rc}" -ne 0 ]; then
            echo "Failed to get properties: Connection timed out" >&2
            exit {show_rc}
        fi
        {show_body}
        exit 0
        ;;
    is-active)
        exit {is_active_rc}
        ;;
    daemon-reload|enable|restart|start)
        exit 0
        ;;
    *)
        exit 0
        ;;
esac
"""
    return _write_exec(bin_dir / "systemctl", script)


def _make_fake_ss(bin_dir: Path, stdout_text: str, rc: int = 0) -> Path:
    script = f"""#!/bin/bash
cat <<'__FAKE_SS__'
{stdout_text}
__FAKE_SS__
exit {rc}
"""
    return _write_exec(bin_dir / "ss", script)


def _make_fake_netstat(bin_dir: Path, stdout_text: str, rc: int = 0) -> Path:
    script = f"""#!/bin/bash
cat <<'__FAKE_NETSTAT__'
{stdout_text}
__FAKE_NETSTAT__
exit {rc}
"""
    return _write_exec(bin_dir / "netstat", script)


def _run_harness(
    tmp_path: Path,
    func_names: list[str],
    body: str,
    *,
    bin_dir: Path,
    env_extra: dict[str, str] | None = None,
    cwd: Path | None = None,
    mock_kill: bool = True,
    surviving_pids: set[int] | None = None,
) -> tuple[subprocess.CompletedProcess, list[str]]:
    """在隔离 PATH 下执行从 start-prod.sh 抽取的真实函数，并记录 kill 调用轨迹。"""
    script_text = START_PROD.read_text(encoding="utf-8")
    extracted = _extract_bash_functions(script_text, func_names)
    kill_log = tmp_path / "kill.log"
    kill_log.write_text("", encoding="utf-8")

    # 用快速无延迟 sleep 避免测试耗时（保留真实系统其他基础命令）
    _write_exec(bin_dir / "sleep", "#!/bin/bash\nexit 0\n")

    kill_shim = ""
    if mock_kill:
        surviving = " ".join(str(p) for p in (surviving_pids or set()))
        kill_shim = f"""
kill() {{
    printf '%s\\n' "$*" >> {str(kill_log)!r}
    if [ "$1" = "-0" ]; then
        local target="$2"
        for sp in {surviving}; do
            if [ "$target" = "$sp" ]; then
                return 0
            fi
        done
        return 1
    fi
    return 0
}}
"""

    runner_script = f"""#!/bin/bash
set -e
{extracted}
{kill_shim}
{body}
"""
    env = os.environ.copy()
    env["PATH"] = f"{bin_dir}:/usr/bin:/bin:/usr/sbin:/sbin"
    if env_extra:
        env.update(env_extra)

    proc = subprocess.run(
        ["bash", "-c", runner_script],
        cwd=str(cwd or tmp_path),
        env=env,
        capture_output=True,
        text=True,
        timeout=15,
    )
    kill_calls = [line for line in kill_log.read_text(encoding="utf-8").splitlines() if line]
    return proc, kill_calls


def test_start_prod_bash_syntax_valid():
    proc = subprocess.run(["bash", "-n", str(START_PROD)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_start_prod_no_systemd_post_219_flags():
    text = START_PROD.read_text(encoding="utf-8")
    assert not re.search(r"systemctl\s+show\b[^\n]*--value\b", text), (
        "systemctl show --value 不兼容 systemd 219 (CentOS 7)"
    )
    assert not re.search(r"systemctl\s+enable\b[^\n]*--now\b", text), (
        "systemctl enable --now 不兼容未打补丁的 systemd 219"
    )


def test_systemd219_main_pid_matches_updater_not_killed(tmp_path):
    """回归核心场景：systemd 219 下运行中的 arl-updater 监听 8888 时，绝不能被误杀。"""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    systemctl_log = tmp_path / "systemctl.log"
    systemd_dir = tmp_path / "systemd"
    systemd_dir.mkdir()
    updater_dir = tmp_path / "updater"
    updater_dir.mkdir()
    (updater_dir / "updater.py").write_text("# dummy updater\n", encoding="utf-8")

    _make_systemd219_systemctl(bin_dir, systemctl_log, main_pid="23456", is_active_rc=0)
    _make_fake_ss(
        bin_dir,
        "\n".join(
            [
                "State      Recv-Q Send-Q Local Address:Port               Peer Address:Port",
                'LISTEN     0      128          0.0.0.0:8888                     0.0.0.0:*                   users:(("python3",pid=23456,fd=3))',
                'LISTEN     0      128             [::]:8888                        [::]:*                   users:(("python3",pid=23456,fd=4))',
            ]
        ),
    )

    proc, kill_calls = _run_harness(
        tmp_path,
        [
            "get_systemd_service_main_pid",
            "is_ancestor_or_self_pid",
            "get_port_8888_listener_pids",
            "cleanup_port_8888_conflicts",
            "deploy_and_start_updater",
        ],
        "deploy_and_start_updater",
        bin_dir=bin_dir,
        cwd=tmp_path,
        env_extra={"ARL_SYSTEMD_DIR": str(systemd_dir)},
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert kill_calls == [], f"不应误杀 arl-updater 主进程，实际 kill 调用: {kill_calls}"
    assert "启动成功且运行正常" in proc.stdout
    assert (systemd_dir / "arl-updater.service").is_file()

    sc_calls = systemctl_log.read_text(encoding="utf-8").splitlines()
    assert "show -p MainPID arl-updater.service" in sc_calls
    assert "restart arl-updater.service" in sc_calls
    assert all("--value" not in line for line in sc_calls)


def test_web_ui_self_update_skip_restart_never_kills_updater_even_if_systemctl_fails(tmp_path):
    """Web 在线更新 (ARL_UPDATER_SKIP_RESTART=1) 时即使 systemctl 异常也绝不杀 8888 进程。"""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    systemctl_log = tmp_path / "systemctl.log"
    systemd_dir = tmp_path / "systemd"
    systemd_dir.mkdir()
    updater_dir = tmp_path / "updater"
    updater_dir.mkdir()
    (updater_dir / "updater.py").write_text("# dummy updater\n", encoding="utf-8")

    _make_systemd219_systemctl(bin_dir, systemctl_log, show_rc=1)
    _make_fake_ss(
        bin_dir,
        'LISTEN 0 128 0.0.0.0:8888 0.0.0.0:* users:(("python3",pid=23456,fd=3))',
    )

    proc, kill_calls = _run_harness(
        tmp_path,
        [
            "get_systemd_service_main_pid",
            "is_ancestor_or_self_pid",
            "get_port_8888_listener_pids",
            "cleanup_port_8888_conflicts",
            "deploy_and_start_updater",
        ],
        "cleanup_port_8888_conflicts\ndeploy_and_start_updater",
        bin_dir=bin_dir,
        cwd=tmp_path,
        env_extra={
            "ARL_SYSTEMD_DIR": str(systemd_dir),
            "ARL_UPDATER_SKIP_RESTART": "1",
        },
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert kill_calls == []
    assert "跳过重启当前正在执行的更新服务" in proc.stdout
    sc_calls = systemctl_log.read_text(encoding="utf-8").splitlines()
    assert "daemon-reload" in sc_calls
    assert all(not line.startswith("restart ") for line in sc_calls)


def test_ancestor_pid_guard_never_kills_parent_process(tmp_path):
    """即使未传 ARL_UPDATER_SKIP_RESTART 且 MainPID=0，也绝不杀自身或其祖先进程。"""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    systemctl_log = tmp_path / "systemctl.log"
    parent_pid = os.getpid()

    _make_systemd219_systemctl(bin_dir, systemctl_log, main_pid="0")
    _make_fake_ss(
        bin_dir,
        f'LISTEN 0 128 0.0.0.0:8888 0.0.0.0:* users:(("python3",pid={parent_pid},fd=3))',
    )

    proc, kill_calls = _run_harness(
        tmp_path,
        [
            "get_systemd_service_main_pid",
            "is_ancestor_or_self_pid",
            "get_port_8888_listener_pids",
            "cleanup_port_8888_conflicts",
        ],
        f"""
is_ancestor_or_self_pid "$$"
is_ancestor_or_self_pid "{parent_pid}"
if is_ancestor_or_self_pid "999999"; then
    echo "UNEXPECTED_ANCESTOR" >&2
    exit 2
fi
cleanup_port_8888_conflicts
""",
        bin_dir=bin_dir,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert kill_calls == [], f"不应误杀祖先进程 {parent_pid}，实际 kill 调用: {kill_calls}"
    assert "祖先进程" in proc.stdout


@pytest.mark.parametrize(
    "show_rc,show_raw",
    [
        (1, None),
        (0, ""),
        (0, "MainPID=not_a_number\n"),
    ],
)
def test_systemd_show_failure_is_fail_closed(tmp_path, show_rc, show_raw):
    """systemctl show 执行失败或输出非法时必须 fail-closed，跳过清理以防误杀。"""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    systemctl_log = tmp_path / "systemctl.log"

    _make_systemd219_systemctl(
        bin_dir, systemctl_log, show_rc=show_rc, show_raw_output=show_raw
    )
    _make_fake_ss(
        bin_dir,
        'LISTEN 0 128 0.0.0.0:8888 0.0.0.0:* users:(("python3",pid=34567,fd=3))',
    )

    proc, kill_calls = _run_harness(
        tmp_path,
        [
            "get_systemd_service_main_pid",
            "is_ancestor_or_self_pid",
            "get_port_8888_listener_pids",
            "cleanup_port_8888_conflicts",
        ],
        "cleanup_port_8888_conflicts",
        bin_dir=bin_dir,
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert kill_calls == []
    assert "无法通过 systemctl 读取 arl-updater.service 的 MainPID" in proc.stdout


def test_external_and_orphan_listeners_cleaned_selectively(tmp_path):
    """仅清理非 MainPID、非祖先、PID > 10 的冲突进程；SIGTERM 退出不补发 SIGKILL，顽固进程补发 SIGKILL。"""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    systemctl_log = tmp_path / "systemctl.log"

    _make_systemd219_systemctl(bin_dir, systemctl_log, main_pid="23456")
    _make_fake_ss(
        bin_dir,
        "\n".join(
            [
                "State Recv-Q Send-Q Local Address:Port Peer Address:Port",
                'LISTEN 0 128 0.0.0.0:8888 0.0.0.0:* users:(("python3",pid=23456,fd=3),("orphan",pid=45678,fd=4),("stubborn",pid=45679,fd=5),("init",pid=1,fd=6))',
            ]
        ),
    )

    proc, kill_calls = _run_harness(
        tmp_path,
        [
            "get_systemd_service_main_pid",
            "is_ancestor_or_self_pid",
            "get_port_8888_listener_pids",
            "cleanup_port_8888_conflicts",
        ],
        "cleanup_port_8888_conflicts",
        bin_dir=bin_dir,
        surviving_pids={45679},
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    # 23456 (MainPID) 与 1 (PID <= 10) 绝不被杀
    assert all("23456" not in c and " 1" not in f" {c}" for c in kill_calls)
    # 45678 收到 SIGTERM 后已退出 -> 不补发 -9
    assert "45678" in kill_calls
    assert "-0 45678" in kill_calls
    assert "-9 45678" not in kill_calls
    # 45679 收到 SIGTERM 后仍存活 -> 补发 -9
    assert "45679" in kill_calls
    assert "-0 45679" in kill_calls
    assert "-9 45679" in kill_calls


def test_ss_legacy_iproute3_modern_iproute4_port_boundaries_and_netstat_fallback(tmp_path):
    """验证旧版 CentOS 7 ss (iproute 3.10 无 pid=)、新版 ss、Netid 列、端口边界与 netstat 回退。"""
    # 1. 旧版 CentOS 7 iproute2 3.10 格式 + 相似端口干扰项
    bin_legacy = tmp_path / "bin_legacy"
    bin_legacy.mkdir()
    _make_fake_ss(
        bin_legacy,
        "\n".join(
            [
                "State      Recv-Q Send-Q Local Address:Port               Peer Address:Port",
                'LISTEN     0      5                 *:8888                     *:*                   users:(("python3",12345,3),("my proc",12346,4))',
                'LISTEN     0      5                :::8888                    :::*                   users:(("python3",12345,5))',
                'LISTEN     0      5                 *:18888                    *:*                   users:(("other",77777,3))',
                'LISTEN     0      5                 *:88880                    *:*                   users:(("other",88888,3))',
            ]
        ),
    )
    proc_legacy, _ = _run_harness(
        tmp_path,
        ["get_port_8888_listener_pids"],
        "get_port_8888_listener_pids",
        bin_dir=bin_legacy,
        mock_kill=False,
    )
    assert proc_legacy.returncode == 0, proc_legacy.stderr
    assert proc_legacy.stdout.splitlines() == ["12345", "12346"]

    # 2. 带 Netid 列的新版 ss 格式
    bin_netid = tmp_path / "bin_netid"
    bin_netid.mkdir()
    _make_fake_ss(
        bin_netid,
        'tcp LISTEN 0 128 0.0.0.0:8888 0.0.0.0:* users:(("python3",pid=23457,fd=3))',
    )
    proc_netid, _ = _run_harness(
        tmp_path,
        ["get_port_8888_listener_pids"],
        "get_port_8888_listener_pids",
        bin_dir=bin_netid,
        mock_kill=False,
    )
    assert proc_netid.returncode == 0, proc_netid.stderr
    assert proc_netid.stdout.splitlines() == ["23457"]

    # 3. ss 失败时自动回退 netstat -tlnp
    bin_fallback = tmp_path / "bin_fallback"
    bin_fallback.mkdir()
    _make_fake_ss(bin_fallback, "", rc=1)
    _make_fake_netstat(
        bin_fallback,
        "\n".join(
            [
                "Active Internet connections (only servers)",
                "Proto Recv-Q Send-Q Local Address           Foreign Address         State       PID/Program name",
                "tcp        0      0 0.0.0.0:8888            0.0.0.0:*               LISTEN      54321/python3",
                "tcp6       0      0 :::8888                 :::*                    LISTEN      54321/python3",
                "tcp        0      0 0.0.0.0:8888            0.0.0.0:*               LISTEN      -",
                "tcp        0      0 0.0.0.0:18888           0.0.0.0:*               LISTEN      99999/other",
            ]
        ),
    )
    proc_fb, _ = _run_harness(
        tmp_path,
        ["get_port_8888_listener_pids"],
        "get_port_8888_listener_pids",
        bin_dir=bin_fallback,
        mock_kill=False,
    )
    assert proc_fb.returncode == 0, proc_fb.stderr
    assert proc_fb.stdout.splitlines() == ["54321"]


def test_non_systemd_host_skips_port_8888_cleanup(tmp_path):
    """非 systemd 宿主机不部署 arl-updater.service，也不得清理 8888 端口进程。"""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    updater_dir = tmp_path / "updater"
    updater_dir.mkdir()
    (updater_dir / "updater.py").write_text("# dummy updater\n", encoding="utf-8")
    _make_fake_ss(
        bin_dir,
        'LISTEN 0 128 0.0.0.0:8888 0.0.0.0:* users:(("python3",pid=45678,fd=3))',
    )

    proc, kill_calls = _run_harness(
        tmp_path,
        [
            "get_systemd_service_main_pid",
            "is_ancestor_or_self_pid",
            "get_port_8888_listener_pids",
            "cleanup_port_8888_conflicts",
            "deploy_and_start_updater",
        ],
        "deploy_and_start_updater",
        bin_dir=bin_dir,
        cwd=tmp_path,
        env_extra={"ARL_SYSTEMD_DIR": str(tmp_path / "nonexistent_systemd")},
    )

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert kill_calls == []
    assert "当前系统不支持 systemd" in proc.stdout


def test_real_ephemeral_conflict_process_terminated_and_ancestor_spared(tmp_path):
    """端到端真实信号验证（不 mock kill/ps）：真实外部占位进程被终止，真实父进程被祖先链护栏放行。"""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    systemctl_log = tmp_path / "systemctl.log"
    parent_pid = os.getpid()

    dummy = subprocess.Popen(["/bin/sleep", "30"])
    try:
        _make_systemd219_systemctl(bin_dir, systemctl_log, main_pid="0")
        _make_fake_ss(
            bin_dir,
            "\n".join(
                [
                    "State Recv-Q Send-Q Local Address:Port Peer Address:Port",
                    f'LISTEN 0 128 0.0.0.0:8888 0.0.0.0:* users:(("parent",pid={parent_pid},fd=3),("sleep",pid={dummy.pid},fd=4))',
                ]
            ),
        )

        proc, _ = _run_harness(
            tmp_path,
            [
                "get_systemd_service_main_pid",
                "is_ancestor_or_self_pid",
                "get_port_8888_listener_pids",
                "cleanup_port_8888_conflicts",
            ],
            "cleanup_port_8888_conflicts",
            bin_dir=bin_dir,
            mock_kill=False,
        )

        assert proc.returncode == 0, proc.stdout + proc.stderr
        assert "祖先进程" in proc.stdout
        assert f"PID: {dummy.pid}" in proc.stdout
        assert "sleep 30" in proc.stdout
        # 验证真实外部进程已被终止
        rc = dummy.wait(timeout=5)
        assert rc != 0
    finally:
        if dummy.poll() is None:
            dummy.kill()
            dummy.wait(timeout=5)


def test_docker_install_systemd219_splits_enable_and_start(tmp_path):
    """验证 check_and_install_docker 在 systemd 219 下拆分 enable + start，不传 --now。"""
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    systemctl_log = tmp_path / "systemctl.log"
    _make_systemd219_systemctl(bin_dir, systemctl_log)

    # 假 curl 输出安装脚本：安装后生成假 docker 可执行文件
    docker_bin = bin_dir / "docker"
    _write_exec(
        bin_dir / "curl",
        f"""#!/bin/bash
cat <<'__INSTALLER__'
#!/bin/bash
cat > {str(docker_bin)!r} <<'__DOCKER__'
#!/bin/bash
echo "Docker version 24.0.0"
__DOCKER__
chmod +x {str(docker_bin)!r}
__INSTALLER__
""",
    )
    script_text = START_PROD.read_text(encoding="utf-8")
    extracted = _extract_bash_functions(
        script_text,
        ["run_with_spinner", "run_cmd_with_timeout", "check_and_install_docker"],
    )
    _write_exec(bin_dir / "sleep", "#!/bin/bash\nexit 0\n")

    safe_bin = tmp_path / "safe_bin"
    safe_bin.mkdir()
    for tool in ("bash", "sh", "cat", "chmod", "head", "printf", "rm", "timeout"):
        resolved = shutil.which(tool)
        if resolved:
            (safe_bin / tool).symlink_to(resolved)

    runner = f"""#!/bin/bash
set -e
{extracted}
check_and_install_docker
"""
    env = os.environ.copy()
    # 仅暴露必需基础工具与测试桩目录，避免 Linux 宿主机 /usr/bin/docker 短路安装分支
    env["PATH"] = f"{bin_dir}:{safe_bin}"

    step_log = Path("/tmp/arl_deploy_step.log")
    existed_before = step_log.exists()
    try:
        proc = subprocess.run(
            ["bash", "-c", runner],
            cwd=str(tmp_path),
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
    finally:
        if not existed_before and step_log.exists():
            step_log.unlink()

    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "Docker 服务已启动" in proc.stdout
    sc_calls = systemctl_log.read_text(encoding="utf-8").splitlines()
    assert "enable docker" in sc_calls
    assert "start docker" in sc_calls
    assert all("--now" not in line for line in sc_calls)
