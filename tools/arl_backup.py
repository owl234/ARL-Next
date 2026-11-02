#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ARL-Next 一键全量数据备份与恢复 CLI 运维工具
支持在宿主机环境（自动透传 Docker）或容器内部直接执行。
"""

import os
import sys
import shutil
import argparse
import subprocess
import json
import time

def is_running_in_docker() -> bool:
    """判断当前脚本是否运行在 Docker 容器内"""
    if os.path.exists('/.dockerenv'):
        return True
    try:
        with open('/proc/1/cgroup', 'rt') as f:
            return 'docker' in f.read()
    except Exception:
        return False


def get_web_container_name() -> str:
    """获取正在运行的 ARL Web 容器名称"""
    candidates = ["arl-web-prod", "arl-web", "backend"]
    for name in candidates:
        res = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )
        if res.returncode == 0 and res.stdout.strip().lower() == "true":
            return name
    return "arl-web-prod"


def _resolve_container_script_path(web_container: str) -> str:
    """解析容器内 arl_backup.py 路径，优先 /code/tools/arl_backup.py，兼容 /code/backend/tools/arl_backup.py 回退"""
    primary = "/code/tools/arl_backup.py"
    fallback = "/code/backend/tools/arl_backup.py"
    for path in (primary, fallback):
        check = subprocess.run(
            ["docker", "exec", web_container, "test", "-f", path],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if check.returncode == 0:
            return path
    # 若旧版容器内尚无该脚本，自动同步当前脚本至容器 /code/tools/arl_backup.py
    subprocess.run(["docker", "exec", web_container, "mkdir", "-p", "/code/tools"], check=True)
    subprocess.run(["docker", "cp", os.path.abspath(__file__), f"{web_container}:{primary}"], check=True)
    return primary


def run_inside_container(cmd_args):
    """当在宿主机运行时，自动将命令透传到 arl-web 容器内执行"""
    web_container = get_web_container_name()
    print(f"🐳 检测到当前在宿主机环境，正在透传至容器 [{web_container}] 执行...")
    
    # 检查是否有文件参数需要同步进容器，以及是否指定了宿主机 --output 导出路径
    transformed_args = list(cmd_args)
    host_output_path = ""
    host_output_is_dir = False
    container_output_tmp = f"/tmp/arl_backup_cli_out_{os.getpid()}.tar.gz"
    uploaded_temp_files = []
    skip_next = False

    for idx, arg in enumerate(transformed_args):
        if skip_next:
            skip_next = False
            continue
        if arg == "--output" and idx + 1 < len(transformed_args):
            raw_out = transformed_args[idx + 1]
            if raw_out:
                host_output_is_dir = raw_out.endswith(("/", "\\")) or os.path.isdir(raw_out)
                host_output_path = os.path.abspath(raw_out)
                transformed_args[idx + 1] = container_output_tmp
            skip_next = True
            continue
        if arg.startswith("--output="):
            raw_out = arg.split("=", 1)[1]
            if raw_out:
                host_output_is_dir = raw_out.endswith(("/", "\\")) or os.path.isdir(raw_out)
                host_output_path = os.path.abspath(raw_out)
                transformed_args[idx] = f"--output={container_output_tmp}"
            continue
        if not arg.startswith("-") and os.path.isfile(arg):
            filename = os.path.basename(arg)
            dest = f"/code/backend/data/backups/{filename}"
            # 检查容器内是否已存在同名且大小一致的文件
            check_res = subprocess.run(
                ["docker", "exec", web_container, "stat", "-c", "%s", dest],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
            )
            local_size = str(os.path.getsize(arg))
            if check_res.returncode != 0 or check_res.stdout.strip() != local_size:
                print(f"📦 正在传输备份文件至容器: {arg} -> {web_container}:{dest} ...")
                subprocess.run(["docker", "exec", web_container, "mkdir", "-p", "/code/backend/data/backups"], check=True)
                subprocess.run(["docker", "cp", arg, f"{web_container}:{dest}"], check=True)
                if transformed_args and transformed_args[0] == "info":
                    uploaded_temp_files.append(dest)
            transformed_args[idx] = filename

    container_script = _resolve_container_script_path(web_container)

    # 仅在具备真实 TTY 交互终端时才附加 -t，避免非交互脚本/SSH 批处理报错
    tty_flag = ["-t"] if sys.stdin.isatty() else []
    container_full_cmd = [
        "docker", "exec", "-i"
    ] + tty_flag + [
        web_container,
        "/code/backend/.venv-docker/bin/python",
        container_script
    ] + transformed_args

    try:
        res = subprocess.run(container_full_cmd)
        if res.returncode == 0 and host_output_path:
            try:
                target_host_file = host_output_path
                if host_output_is_dir or os.path.isdir(target_host_file):
                    os.makedirs(target_host_file, exist_ok=True)
                    target_host_file = os.path.join(target_host_file, f"arl_backup_{int(time.time())}.tar.gz")
                else:
                    os.makedirs(os.path.dirname(target_host_file) or ".", exist_ok=True)
                subprocess.run(["docker", "cp", f"{web_container}:{container_output_tmp}", target_host_file], check=True)
                print(f"📥 已将备份文件同步至宿主机: {target_host_file}")
            finally:
                subprocess.run(
                    ["docker", "exec", web_container, "rm", "-f", container_output_tmp],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE
                )
    finally:
        for temp_dest in uploaded_temp_files:
            subprocess.run(
                ["docker", "exec", web_container, "rm", "-f", temp_dest],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE
            )
    sys.exit(res.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="ARL-Next 一键全量数据备份与恢复 CLI 工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 创建全量备份（包含所有 MongoDB 集合与站点截图）
  python3 tools/arl_backup.py backup --note "升级前全量快照"

  # 创建轻量级备份（排除 tmp_screenshot 站点大图）
  python3 tools/arl_backup.py backup --no-screenshots

  # 列出所有现存备份
  python3 tools/arl_backup.py list

  # 查看指定备份包详情
  python3 tools/arl_backup.py info arl_backup_20261021_215500_abc123.tar.gz

  # 覆盖恢复备份包（--drop 模式）
  python3 tools/arl_backup.py restore arl_backup_20261021_215500_abc123.tar.gz --force
        """
    )
    subparsers = parser.add_subparsers(dest="subcommand", help="子命令")

    # backup 子命令
    p_backup = subparsers.add_parser("backup", help="创建系统全量备份归档")
    p_backup.add_argument("--no-screenshots", action="store_true", help="排除站点资产截图以显著压缩体积")
    p_backup.add_argument("--note", type=str, default="", help="备份说明或备注")
    p_backup.add_argument("--output", type=str, default="", help="备份包保存路径或目标文件名")

    # restore 子命令
    p_restore = subparsers.add_parser("restore", help="覆盖导入并恢复备份数据 (--drop 模式)")
    p_restore.add_argument("archive", type=str, help="待恢复的备份文件路径或文件名")
    p_restore.add_argument("--force", action="store_true", help="若系统有扫描任务在运行，强制终止并覆盖恢复")

    # list 子命令
    subparsers.add_parser("list", help="列出本地现存的所有备份文件")

    # info 子命令
    p_info = subparsers.add_parser("info", help="查看指定备份文件的元数据与资产大盘统计")
    p_info.add_argument("archive", type=str, help="备份文件路径或文件名")

    args = parser.parse_args()

    if not args.subcommand:
        parser.print_help()
        sys.exit(1)

    # 宿主机环境自动透传
    if not is_running_in_docker():
        # 尝试检查本地能否直连 Python 后端
        try:
            import app.services.backup_service
        except ImportError:
            # 本地无环境，直接透传至 Docker 容器
            run_inside_container(sys.argv[1:])

    # 容器内或已导入后端环境的执行逻辑
    # 动态把 backend 加到 sys.path
    curr_dir = os.path.dirname(os.path.abspath(__file__))
    parent_dir = os.path.abspath(os.path.join(curr_dir, ".."))
    backend_dir = os.path.join(parent_dir, "backend") if os.path.isdir(os.path.join(parent_dir, "backend")) else parent_dir
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)

    from app.services.backup_service import (
        create_backup_archive,
        restore_backup_archive,
        list_all_backups,
        read_archive_manifest,
        get_backup_dir,
        get_running_task_count
    )

    if args.subcommand == "backup":
        include_screenshots = not args.no_screenshots
        print("\n" + "=" * 60)
        print("🚀 ARL-Next 开始创建系统全量备份...")
        print(f"📸 包含资产截图: {'是' if include_screenshots else '否 (已排除)'}")
        if args.note:
            print(f"📝 备份备注: {args.note}")
        print("=" * 60)
        
        t0 = time.time()
        try:
            res = create_backup_archive(include_screenshots=include_screenshots, note=args.note)
            elapsed = round(time.time() - t0, 2)
            archive_path = os.path.join(get_backup_dir(), res["archive_name"])
            
            # 若指定了 output 且不同于源路径，则移动/复制
            if args.output:
                out_is_dir = args.output.endswith(("/", "\\")) or os.path.isdir(args.output)
                out_path = os.path.abspath(args.output)
                if out_is_dir or os.path.isdir(out_path):
                    os.makedirs(out_path, exist_ok=True)
                    out_path = os.path.join(out_path, res["archive_name"])
                else:
                    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
                if os.path.abspath(archive_path) != os.path.abspath(out_path):
                    shutil.move(archive_path, out_path)
                    archive_path = out_path

            print("\n" + "=" * 60)
            print("🎉 恭喜！系统备份已成功生成！")
            print(f"📁 备份文件: {archive_path}")
            print(f"📦 文件体积: {round(res['size'] / 1024 / 1024, 2)} MB")
            print(f"⏱️ 耗时: {elapsed} 秒")
            stats = res.get("mongo_stats", {}).get("summary", {})
            print(f"📊 资产总览: 任务测绘资产 {stats.get('task_assets', 0)} 条 | 监控资产组 {stats.get('scope_assets', 0)} 条")
            print(f"📋 任务总数: {stats.get('total_tasks', 0)} | 用户总数: {stats.get('total_users', 0)}")
            print("=" * 60 + "\n")
        except Exception as e:
            print(f"\n❌ 备份失败: {e}\n", file=sys.stderr)
            sys.exit(1)

    elif args.subcommand == "list":
        backups = list_all_backups()
        running_tasks = get_running_task_count()
        print("\n" + "=" * 75)
        print(f"🗂️  ARL-Next 现存备份清单 (运行中及排队中的任务: {running_tasks} 个)")
        print("=" * 75)
        if not backups:
            print("暂无任何备份文件。您可以使用 'python3 tools/arl_backup.py backup' 创建首个备份。")
        else:
            fmt = "{:<45} {:<12} {:<20} {:<10}"
            print(fmt.format("文件名", "大小 (MB)", "创建时间", "含截图"))
            print("-" * 75)
            for b in backups:
                sz_mb = f"{round(b['size'] / 1024 / 1024, 2)} MB"
                ctime = (b.get("created_at") or "")[:19].replace("T", " ")
                scr = "是" if b.get("include_screenshots") else "否"
                print(fmt.format(b["filename"], sz_mb, ctime, scr))
        print("=" * 75 + "\n")

    elif args.subcommand == "info":
        target = args.archive
        if not os.path.isabs(target) and not os.path.isfile(target):
            target = os.path.join(get_backup_dir(), target)
            
        if not os.path.isfile(target):
            print(f"❌ 错误: 未找到备份文件 {target}", file=sys.stderr)
            sys.exit(1)

        try:
            manifest = read_archive_manifest(target)
            print("\n" + "=" * 60)
            print(f"📋 备份包元数据: {os.path.basename(target)}")
            print("=" * 60)
            print(f"• ARL 版本: {manifest.get('arl_version')}")
            print(f"• 创建时间: {manifest.get('created_at')}")
            print(f"• 包含截图: {'是' if manifest.get('include_screenshots') else '否'}")
            if manifest.get('note'):
                print(f"• 备份备注: {manifest.get('note')}")
            
            stats = manifest.get("mongo_stats", {})
            sumry = stats.get("summary", {})
            print("\n📊 核心业务数据统计:")
            print(f"  - 集合总数: {stats.get('total_collections')} 个")
            print(f"  - 文档总数: {stats.get('total_documents')} 条")
            print(f"  - 任务测绘资产: {sumry.get('task_assets', 0)} 条")
            print(f"  - 监控资产组: {sumry.get('scope_assets', 0)} 条")
            print(f"  - 历史任务: {sumry.get('total_tasks', 0)} 个")
            print(f"  - 用户账号: {sumry.get('total_users', 0)} 个")
            print("=" * 60 + "\n")
        except Exception as e:
            print(f"❌ 解析备份包失败: {e}", file=sys.stderr)
            sys.exit(1)

    elif args.subcommand == "restore":
        target = args.archive
        if not os.path.isabs(target) and not os.path.isfile(target):
            target = os.path.join(get_backup_dir(), target)

        if not os.path.isfile(target):
            print(f"❌ 错误: 未找到待恢复的备份文件 {target}", file=sys.stderr)
            sys.exit(1)

        # 校验任务
        running_count = get_running_task_count()
        force_restore = bool(args.force)
        if running_count > 0 and not force_restore:
            print(f"\n⚠️  警告: 系统当前有 {running_count} 个正在执行的扫描任务！")
            print("覆盖恢复将会清空现有数据库并中断这些任务。")
            confirm = input("如确认继续，请输入 'yes'，或带 --force 参数运行: ").strip().lower()
            if confirm != "yes":
                print("操作已取消。")
                sys.exit(0)
            force_restore = True

        print("\n" + "=" * 60)
        print("⚠️  ARL-Next 开始执行全量覆盖恢复 (--drop 模式)...")
        print(f"📦 备份源文件: {target}")
        print("=" * 60)
        
        t0 = time.time()
        try:
            res = restore_backup_archive(archive_path=target, force=force_restore)
            elapsed = round(time.time() - t0, 2)
            print("\n" + "=" * 60)
            print("🎉 恭喜！数据覆盖恢复全部成功！")
            print(f"⏱️ 耗时: {elapsed} 秒")
            print(f"📚 恢复集合数: {res.get('total_collections_restored')} 个")
            print(f"📄 恢复文档数: {res.get('total_documents_restored')} 条")
            if res.get("verified"):
                print("✅ 数据完整性校验: 100% 吻合")
            else:
                print(f"⚠️ 差异报告: {res.get('discrepancies')}")
            print("=" * 60 + "\n")
        except Exception as e:
            print(f"\n❌ 恢复失败: {e}\n", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
