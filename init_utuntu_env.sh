#!/bin/bash
# ARL-Next 节点环境全自动初始化脚本 (Ubuntu)
# 作用：安装 Docker 引擎、配置用户组、配置自动化流水线免密提权

set -e # 遇到错误立即停止执行

echo "🚀 开始初始化 ARL-Next 运行节点环境..."

# 1. 检测并安装 Docker 引擎
if ! command -v docker &> /dev/null; then
    echo "📦 检测到未安装 Docker，正在通过官方脚本安装 (可能需要 1-3 分钟)..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sudo sh get-docker.sh
    rm get-docker.sh
    echo "✅ Docker 安装完成！"
else
    echo "✅ Docker 已安装，跳过。"
fi

# 2. 配置 Docker 免 sudo 执行权限
echo "🔑 正在将当前用户 ($USER) 加入 docker 用户组..."
sudo usermod -aG docker $USER
echo "✅ Docker 权限配置完成！"

# 3. 为 GitHub Actions Runner 配置特定命令的免密提权 (极其关键)
echo "🛡️ 正在配置 CI/CD 自动化流水线提权规则..."
# 在 /etc/sudoers.d/ 创建专属规则文件，这是比修改 visudo 更安全、更规范的做法
SUDOERS_FILE="/tmp/arl_runner_sudoers"
echo "$USER ALL=(ALL) NOPASSWD: /usr/bin/apt-get, /usr/sbin/ufw" > $SUDOERS_FILE
sudo chown root:root $SUDOERS_FILE
sudo chmod 0440 $SUDOERS_FILE
sudo mv $SUDOERS_FILE /etc/sudoers.d/arl_runner_sudoers
echo "✅ 免密提权规则配置完成！"

echo "======================================================="
echo "🎉 环境初始化全部完成！"
echo "⚠️  【重要提示】：由于用户组权限变更，请您执行以下操作之一使其生效："
echo "   1. 执行命令: newgrp docker"
echo "   2. 或者退出当前终端重新 SSH 登录"
echo "   3. 如果配置了 GitHub Runner，请务必进入 runner 目录执行: sudo ./svc.sh stop && sudo ./svc.sh start"
echo "======================================================="