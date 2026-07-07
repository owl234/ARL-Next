#!/bin/bash
# ARL-Next 极简生产一键自动部署与调优脚本

set -e

# 确保以 root 权限运行
if [ "$EUID" -ne 0 ]; then
    echo "❌ 错误：修改系统 Docker 配置和重启服务需要 root 权限，请使用 sudo 运行此脚本："
    echo "👉 sudo bash start-prod.sh"
    exit 1
fi

# ==================== 依赖检查与自动安装函数 ====================

# 1. 识别操作系统与包管理器
detect_os_and_pkg_manager() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS_NAME=$ID
        OS_LIKE=$ID_LIKE
    else
        OS_NAME="unknown"
        OS_LIKE="unknown"
    fi

    if command -v apt-get &>/dev/null; then
        PKG_MANAGER="apt-get"
        UPDATE_CMD="apt-get update -y"
        INSTALL_CMD="apt-get install -y"
    elif command -v yum &>/dev/null; then
        PKG_MANAGER="yum"
        UPDATE_CMD="yum makecache"
        INSTALL_CMD="yum install -y"
    elif command -v dnf &>/dev/null; then
        PKG_MANAGER="dnf"
        UPDATE_CMD="dnf makecache"
        INSTALL_CMD="dnf install -y"
    else
        PKG_MANAGER="unknown"
    fi
}

# 2. 检查并安装 Python 3
check_and_install_python3() {
    if command -v python3 &>/dev/null; then
        echo "✅ 检测到 Python 3 已安装：$(python3 --version | head -n 1)"
        return 0
    fi

    echo "⚠️ 未检测到 Python 3，尝试自动安装..."
    detect_os_and_pkg_manager

    if [ "$PKG_MANAGER" = "unknown" ]; then
        echo "❌ 错误：未识别的包管理器，请手动安装 python3 后重试。"
        exit 1
    fi

    echo "📦 正在使用 $PKG_MANAGER 安装 python3..."
    $UPDATE_CMD
    $INSTALL_CMD python3

    if command -v python3 &>/dev/null; then
        echo "✅ Python 3 安装成功！"
    else
        echo "❌ 错误：Python 3 自动安装失败，请手动安装后重试。"
        exit 1
    fi
}

# 3. 检查并安装 Docker Engine
check_and_install_docker() {
    if command -v docker &>/dev/null; then
        echo "✅ 检测到 Docker 已安装：$(docker --version | head -n 1)"
        return 0
    fi

    echo "⚠️ 未检测到 Docker Engine，尝试自动安装..."
    
    # 尝试使用官方 get.docker.com 脚本一键安装
    if command -v curl &>/dev/null || command -v wget &>/dev/null; then
        echo "🌐 正在通过 Docker 官方脚本下载并安装 Docker..."
        if command -v curl &>/dev/null; then
            curl -fsSL https://get.docker.com | sh
        else
            wget -qO- https://get.docker.com | sh
        fi
        
        # 启动并使能 Docker 服务
        if systemctl enable --now docker &>/dev/null || service docker start &>/dev/null; then
            echo "✅ Docker 服务已启动！"
        fi
    else
        # 尝试通过系统包管理器安装
        detect_os_and_pkg_manager
        if [ "$PKG_MANAGER" = "unknown" ]; then
            echo "❌ 错误：无法自动安装 Docker。请参考官方文档手动安装：https://docs.docker.com/engine/install/"
            exit 1
        fi
        
        echo "📦 正在通过 $PKG_MANAGER 尝试安装 docker..."
        if [ "$PKG_MANAGER" = "apt-get" ]; then
            $UPDATE_CMD
            $INSTALL_CMD docker.io
        else
            $UPDATE_CMD
            $INSTALL_CMD docker
        fi
    fi

    if command -v docker &>/dev/null; then
        echo "✅ Docker Engine 安装成功！"
    else
        echo "❌ 错误：Docker 自动安装失败。请参考官方文档手动安装：https://docs.docker.com/engine/install/"
        exit 1
    fi
}

# 4. 检查并安装 Docker Compose 插件
check_and_install_compose() {
    # 检查 docker compose 插件是否可用
    if docker compose version &>/dev/null; then
        echo "✅ 检测到 Docker Compose 插件已安装：$(docker compose version | head -n 1)"
        return 0
    fi

    echo "⚠️ 未检测到 Docker Compose v2 插件，尝试自动安装..."
    detect_os_and_pkg_manager

    if [ "$PKG_MANAGER" = "apt-get" ]; then
        echo "📦 正在通过 apt-get 安装 docker-compose-plugin..."
        $UPDATE_CMD
        $INSTALL_CMD docker-compose-plugin || $INSTALL_CMD docker-compose
    elif [ "$PKG_MANAGER" = "yum" ] || [ "$PKG_MANAGER" = "dnf" ]; then
        echo "📦 正在通过 $PKG_MANAGER 安装 docker-compose-plugin..."
        $INSTALL_CMD docker-compose-plugin || $INSTALL_CMD docker-compose
    else
        # 兜底：如果无法通过包管理器安装，尝试从 GitHub 下载二进制包到 Docker 插件目录
        echo "🌐 尝试从 GitHub 下载 docker-compose 独立二进制包..."
        ARCH=$(uname -m)
        OS=$(uname -s | tr '[:upper:]' '[:lower:]')
        COMPOSE_URL="https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-${OS}-${ARCH}"
        
        mkdir -p /usr/local/lib/docker/cli-plugins
        if command -v curl &>/dev/null; then
            curl -SL "$COMPOSE_URL" -o /usr/local/lib/docker/cli-plugins/docker-compose
        elif command -v wget &>/dev/null; then
            wget -O /usr/local/lib/docker/cli-plugins/docker-compose "$COMPOSE_URL"
        fi
        chmod +x /usr/local/lib/docker/cli-plugins/docker-compose
        
        # 软链接
        ln -sf /usr/local/lib/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose
    fi

    # 验证安装
    if docker compose version &>/dev/null; then
        echo "✅ Docker Compose 插件安装成功！"
    elif command -v docker-compose &>/dev/null; then
        echo "✅ 检测到独立版 docker-compose 已安装。配置别名兼容..."
        if [ ! -f /usr/local/lib/docker/cli-plugins/docker-compose ] && command -v docker-compose &>/dev/null; then
            mkdir -p /usr/local/lib/docker/cli-plugins
            ln -sf "$(which docker-compose)" /usr/local/lib/docker/cli-plugins/docker-compose
        fi
    else
        echo "❌ 错误：Docker Compose 自动安装失败，请手动安装后重试。"
        exit 1
    fi
}

echo "🚀 开始执行 ARL-Next 生产一键部署与调优..."

# 执行依赖检测与安装
check_and_install_python3
check_and_install_docker
check_and_install_compose

# 1. 宿主机 Docker 守护进程性能调优 (userland-proxy)
DOCKER_CONFIG_DIR="/etc/docker"
DOCKER_CONFIG_FILE="$DOCKER_CONFIG_DIR/daemon.json"

mkdir -p "$DOCKER_CONFIG_DIR"

echo "⚙️ 正在检查并配置宿主机 Docker 性能调优参数..."

# 使用 Python 脚本安全读取/修改 JSON，防止格式损坏
UPDATED=$(python3 -c "
import json, os
path = '$DOCKER_CONFIG_FILE'
data = {}
if os.path.exists(path) and os.path.getsize(path) > 0:
    try:
        with open(path, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print('ERROR')
        exit(0)
if data.get('userland-proxy') != False:
    data['userland-proxy'] = False
    with open(path, 'w') as f:
        json.dump(data, f, indent=4)
    print('UPDATED')
else:
    print('NO_CHANGE')
")

if [ "$UPDATED" = "ERROR" ]; then
    echo "⚠️ 警告：无法解析已有的 $DOCKER_CONFIG_FILE，可能存在 JSON 语法错误，跳过自动性能配置。"
elif [ "$UPDATED" = "UPDATED" ]; then
    echo "✅ 已成功配置 'userland-proxy': false 参数。正在重启 Docker 服务使配置生效..."
    if systemctl restart docker &>/dev/null || service docker restart &>/dev/null; then
        echo "✅ Docker 服务重启成功！"
    else
        echo "⚠️ 警告：无法通过 systemctl 或 service 重启 Docker 服务，这可能是因为您运行在非 systemd 环境中。"
        echo "👉 请在部署完成后手动重启 Docker 服务以使性能调优生效。"
    fi
else
    echo "✅ 宿主机 Docker 性能参数已是最佳状态，无需修改。"
fi

# 2. 准备证书存放目录
echo "📁 正在检查证书存放目录..."
mkdir -p ./ssl-certs

if [ ! -f "./ssl-certs/arl.crt" ] || [ ! -f "./ssl-certs/arl.key" ]; then
    echo "⚠️ 提示：未在 ./ssl-certs/ 目录下检测到 arl.crt 或 arl.key。"
    echo "👉 请在容器拉起后，将公网 SSL 证书与私钥放入其中以启用 HTTPS。"
fi

# 3. 一键构建并拉起生产服务
echo "🐳 正在一键构建并拉起生产多服务容器组..."
docker compose -f docker-compose.prod.yml up -d --build

# 4. 获取本地与公网真实 IP 并展示
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}' || ip route get 1.1.1.1 2>/dev/null | awk '{print $7}' || echo "127.0.0.1")
LOCAL_IP=$(echo "$LOCAL_IP" | xargs)

PUBLIC_IP=$(curl -s --max-time 1.5 ifconfig.me 2>/dev/null || echo "")
PUBLIC_IP=$(echo "$PUBLIC_IP" | xargs)

echo "🎉 部署完成！"
echo "🌟 所有组件均已在 Docker 私有网络内隔离启动，公网仅对外暴露前端 5173 端口。"
echo "👉 请通过浏览器访问以下地址之一登录系统："
echo "   - 本地/局域网访问: https://$LOCAL_IP:5173"
if [ -n "$PUBLIC_IP" ] && [ "$PUBLIC_IP" != "$LOCAL_IP" ]; then
    echo "   - 公网访问:        https://$PUBLIC_IP:5173"
fi
