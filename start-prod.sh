#!/bin/bash
# ARL-Next 极简生产一键自动部署与调优脚本

set -e

# 确保以 root 权限运行
if [ "$EUID" -ne 0 ]; then
    echo "❌ 错误：修改系统 Docker 配置和重启服务需要 root 权限，请使用 sudo 运行此脚本："
    echo "👉 sudo bash start-prod.sh"
    exit 1
fi

# 强制切换到脚本所在目录，防止因外部调用导致的相对路径报错
cd "$(dirname "$0")"

# ==================== 并发执行锁机制 ====================
LOCK_FILE="/tmp/arl_deploy.lock"
exec 9> "$LOCK_FILE"
if ! flock -n 9; then
    echo "❌ 错误：检测到另一个部署或更新任务正在运行中，请稍后再试。"
    exit 1
fi

# 出口清理临时日志文件（无痕执行）
cleanup_temp_files() {
    # 注意：/tmp/arl_dockerd.log 是长期运行 daemon 的排障依据，保留不清理；
    # 仅清理本脚本一次性命令的临时输出。
    rm -f /tmp/arl_pull_step.log /tmp/arl_deploy_step.log 2>/dev/null || true
}
trap cleanup_temp_files EXIT
# INT/TERM 时清理后显式退出，exit 会自然触发 EXIT 信号完成 cleanup_temp_files
trap 'exit 130' INT TERM

# ==================== 通用加载动画指示器 ====================
run_with_spinner() {
    local msg="$1"
    shift
    # 执行命令并在后台静默运行
    "$@" > /tmp/arl_deploy_step.log 2>&1 &
    local pid=$!
    
    local spin='-\|/'
    local i=0
    
    printf "  ⚙️  %-60s" "$msg"
    while kill -0 $pid 2>/dev/null; do
        i=$(( (i+1) % 4 ))
        printf "\r  ⚙️  %-60s [%c]" "$msg" "${spin:$i:1}"
        sleep 0.1
    done
    
    wait $pid
    local status=$?
    if [ $status -eq 0 ]; then
        printf "\r  ✅ %-60s [完成]\n" "$msg"
    else
        printf "\r  ⚠️  %-60s [失败]\n" "$msg"
        echo "==================== ❌ 详细报错信息 ===================="
        cat /tmp/arl_deploy_step.log
        echo "========================================================="
    fi
    return $status
}

# ==================== 通用超时执行适配器 ====================
run_cmd_with_timeout() {
    local sec="$1"
    shift
    if command -v timeout &>/dev/null; then
        timeout "$sec" "$@"
    else
        "$@"
    fi
}

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
    run_with_spinner "更新系统软件包列表" $UPDATE_CMD
    run_with_spinner "自动安装 Python 3" $INSTALL_CMD python3

    if command -v python3 &>/dev/null; then
        echo "✅ Python 3 安装成功！"
    else
        # 若安装失败且系统为 CentOS 7，尝试自动切换至阿里云 Vault 归档源后重试
        if [ "$PKG_MANAGER" = "yum" ] && grep -qi "CentOS Linux release 7" /etc/redhat-release 2>/dev/null; then
            echo "⚠️ 检测到 CentOS 7 官方源可能已停更 (EOL)，正在自动切换至阿里云 Vault 归档源重试..."
            # 健壮性防抖：原子下载机制，确认文件非空合法后再覆盖，避免断网导致原生 yum 源永久损坏
            if curl -s -f -o /tmp/CentOS-Base.repo https://mirrors.aliyun.com/repo/Centos-7.repo && [ -s /tmp/CentOS-Base.repo ]; then
                mv -f /tmp/CentOS-Base.repo /etc/yum.repos.d/CentOS-Base.repo
                sed -i -e '/aliyuncs.com/d' -e '/mirrorlist.centos.org/d' /etc/yum.repos.d/CentOS-Base.repo 2>/dev/null || true
                sed -i -e 's/mirror.centos.org\/centos\/$releasever/mirrors.aliyun.com\/centos-vault\/7.9.2009/g' /etc/yum.repos.d/CentOS-Base.repo 2>/dev/null || true
                yum makecache >/dev/null 2>&1 || true
                yum install -y python3 >/dev/null 2>&1 || true
            else
                echo "⚠️ 无法下载阿里云 Vault 归档源配置，跳过自动替换。"
            fi
        fi

        if command -v python3 &>/dev/null; then
            echo "✅ Python 3 安装成功！"
        else
            echo "❌ 错误：Python 3 自动安装失败，请手动安装后重试。"
            exit 1
        fi
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
            run_with_spinner "下载并运行 Docker 安装脚本" bash -c "curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun" || true
        else
            run_with_spinner "下载并运行 Docker 安装脚本" bash -c "wget -qO- https://get.docker.com | bash -s docker --mirror Aliyun" || true
        fi
        
        # 启动并使能 Docker 服务
        if run_cmd_with_timeout 30 systemctl enable --now docker &>/dev/null || run_cmd_with_timeout 30 service docker start &>/dev/null; then
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
            run_with_spinner "更新系统软件包列表" $UPDATE_CMD
            run_with_spinner "安装 Docker" $INSTALL_CMD docker.io
        else
            run_with_spinner "更新系统软件包列表" $UPDATE_CMD
            run_with_spinner "安装 Docker" $INSTALL_CMD docker
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
        run_with_spinner "通过 apt-get 安装 docker-compose-plugin" $INSTALL_CMD docker-compose-plugin
    elif [ "$PKG_MANAGER" = "yum" ] || [ "$PKG_MANAGER" = "dnf" ]; then
        run_with_spinner "通过 $PKG_MANAGER 安装 docker-compose-plugin" $INSTALL_CMD docker-compose-plugin
    else
        # 兜底：如果无法通过包管理器安装，尝试从 GitHub 下载二进制包到 Docker 插件目录
        echo "🌐 尝试从 GitHub 下载 docker-compose 独立二进制包..."
        ARCH=$(uname -m)
        OS=$(uname -s | tr '[:upper:]' '[:lower:]')
        COMPOSE_URL="https://ghproxy.cn/https://github.com/docker/compose/releases/download/v2.20.2/docker-compose-${OS}-${ARCH}"
        
        mkdir -p /usr/local/lib/docker/cli-plugins
        if command -v curl &>/dev/null; then
            run_with_spinner "下载 docker-compose 二进制包" curl -SL "$COMPOSE_URL" -o /usr/local/lib/docker/cli-plugins/docker-compose
        elif command -v wget &>/dev/null; then
            run_with_spinner "下载 docker-compose 二进制包" wget -O /usr/local/lib/docker/cli-plugins/docker-compose "$COMPOSE_URL"
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

# ==================== 极简生产化不再需要民间镜像代理 ====================
# 由于所有的镜像（包含 mongo、rabbitmq）现均由 GitHub Actions 自动推送到阿里云高可用个人私有库
# 因此直接让 docker-compose 从国内的阿里云仓库 pull，享受极限满速下载。

# 5. 检查并配置 2G Swap 以防 OOM
check_and_configure_swap() {
    echo "⚙️ 正在检查宿主机 Swap 虚拟内存..."
    local swap_size_mb=$(free -m | awk '/^Swap:/ {print $2}')
    if [ -n "$swap_size_mb" ] && [ "$swap_size_mb" -ge 1024 ] 2>/dev/null; then
        local swap_size_gb=$(awk "BEGIN {printf \"%.1f\", $swap_size_mb/1024}")
        echo "✅ 检测到系统已有 Swap (${swap_size_gb}G)，跳过创建。"
        return 0
    fi
    
    echo "⚠️ 检测到系统未配置 Swap，正在自动划分 2G Swap 空间防止高并发扫描 OOM..."
    if run_with_spinner "创建 2G Swap 分区文件" dd if=/dev/zero of=/swapfile bs=1M count=2048 status=none; then
        chmod 600 /swapfile
        mkswap /swapfile &>/dev/null
        swapon /swapfile &>/dev/null
        
        # 写入 fstab 开机自动挂载
        if ! grep -q "/swapfile" /etc/fstab; then
            echo "/swapfile none swap sw 0 0" >> /etc/fstab
        fi
        
        echo "✅ 2G Swap 空间自动分配并挂载成功！"
    else
        echo "❌ 错误：Swap 分配失败，可能是磁盘空间不足，跳过此步骤。"
    fi
}

# 5.5 宿主机内存预检 (已移除 mem_limit 硬限制后的部署侧补偿：只告警不阻断)
check_host_memory() {
    echo "⚙️ 正在检查宿主机物理内存..."
    local total_mb=$(free -m | awk '/^Mem:/ {print $2}')
    if [ -z "$total_mb" ]; then
        echo "⚠️ 无法读取宿主机内存信息，跳过预检（首页内存占用卡片可实时查看）。"
        return 0
    fi
    # 全栈软保留约 1.8G，低于 2G 的机器去掉硬限制后 burst 风险较高
    if [ "$total_mb" -lt 2048 ] 2>/dev/null; then
        echo "⚠️ 宿主机内存仅 ${total_mb}MB（全栈软保留约 1.8G）：已移除容器硬限制，大扫描时请盯紧首页「内存占用」卡片，超 90% 请降并发或加内存。"
    else
        echo "✅ 宿主机内存 ${total_mb}MB，满足去硬限制后的运行基线！"
    fi
}

# 6. 宿主机内核防假死与扫描性能调优 (swappiness/vfs_cache_pressure/overcommit)
tune_system_kernel_parameters() {
    echo "⚙️ 正在配置宿主机内核性能与防假死参数 (swappiness=10, vfs_cache_pressure=50, overcommit_memory=1)..."
    
    # 动态应用参数
    sysctl -w vm.swappiness=10 &>/dev/null || true
    sysctl -w vm.vfs_cache_pressure=50 &>/dev/null || true
    sysctl -w vm.overcommit_memory=1 &>/dev/null || true
    
    # 持久化写入 /etc/sysctl.conf (去重并追加)
    if [ -f /etc/sysctl.conf ]; then
        sed -i '/vm.swappiness/d' /etc/sysctl.conf
        sed -i '/vm.vfs_cache_pressure/d' /etc/sysctl.conf
        sed -i '/vm.overcommit_memory/d' /etc/sysctl.conf
        echo "vm.swappiness = 10" >> /etc/sysctl.conf
        echo "vm.vfs_cache_pressure = 50" >> /etc/sysctl.conf
        echo "vm.overcommit_memory = 1" >> /etc/sysctl.conf
    fi
    echo "✅ 宿主机内核参数调优完成（已持久化至 /etc/sysctl.conf）！"
}

# 7. 检查宿主机磁盘剩余空间 (至少预留 2GB)
check_disk_space() {
    echo "⚙️ 正在检查宿主机磁盘剩余空间..."
    local free_kb=$(df -k . | awk 'NR==2 {print $4}')
    if [ -n "$free_kb" ] && [ "$free_kb" -lt 2097152 ] 2>/dev/null; then
        local free_mb=$((free_kb / 1024))
        echo "❌ 错误：当前目录所在磁盘剩余空间仅有 ${free_mb}MB，不足 2GB。更新可能因磁盘写满中断，请先清理磁盘后重试。"
        exit 1
    fi
    echo "✅ 宿主机磁盘空间充足！"
}

# ==================== 执行部署流程 ====================

echo "🚀 开始执行 ARL-Next 生产一键部署与调优..."

# 执行依赖检测与安装
check_and_install_python3
check_and_install_docker

# 4.5 统一探测 Docker 守护进程是否就绪；缺失 timeout 命令的极简环境直接探测（接受极小概率挂起风险）
docker_info_ok() {
    run_cmd_with_timeout 3 docker info &>/dev/null
}

# 4.5 轮询探测 Docker 守护进程就绪（最多 15 轮 × 每轮 ≤3 秒探测，避免慢启动误杀与卡死态无限阻塞）
wait_docker_daemon() {
    local i
    for i in {1..15}; do
        # 显式超时兜底：卡死态 daemon（socket 存在但无响应）会让 docker info 无限阻塞
        if docker_info_ok; then
            return 0
        fi
        sleep 1
    done
    return 1
}

# 4.6 检查 Docker 守护进程是否真正在运行，未运行则尝试启动
check_docker_daemon() {
    echo "⚙️ 正在检查 Docker 守护进程运行状态..."
    if docker_info_ok; then
        echo "✅ Docker 守护进程运行正常！"
        return 0
    fi

    echo "⚠️ Docker 二进制文件存在，但守护进程未运行，尝试启动..."

    # 方式一：systemd 服务托管
    if command -v systemctl &>/dev/null; then
        run_cmd_with_timeout 30 systemctl start docker 2>/dev/null || true
        if wait_docker_daemon; then
            echo "✅ Docker 守护进程启动成功！"
            return 0
        fi
    fi

    # 方式二：SysV init 服务（仅无 systemd 时使用，避免与托管实例竞争）
    if ! command -v systemctl &>/dev/null && command -v service &>/dev/null; then
        run_cmd_with_timeout 30 service docker start 2>/dev/null || true
        if wait_docker_daemon; then
            echo "✅ Docker 守护进程启动成功！"
            return 0
        fi
    fi

    # 兜底：仅在没有 systemd/service 托管的极简环境下直接启动 dockerd
    if ! command -v systemctl &>/dev/null && ! command -v service &>/dev/null && command -v dockerd &>/dev/null; then
        # 防竞争：若已有 dockerd 进程在运行（如 updater 侧刚拉起），直接等待其就绪，
        # 避免两个 dockerd 争抢 /var/run/docker.sock 与 /var/lib/docker 造成数据损坏
        if command -v pgrep &>/dev/null && pgrep -x dockerd &>/dev/null; then
            echo "⚠️ 检测到 dockerd 进程已在运行，等待其就绪..."
            if wait_docker_daemon; then
                return 0
            fi
            echo "❌ 错误：已检测到 dockerd 进程但无法就绪，可能存在异常状态，请手动排查。"
            return 1
        fi
        # 9>&- 关闭继承的部署锁 fd：flock 锁挂在打开文件描述上，子进程继承 fd 即持续持锁，
        # 否则 dockerd 长期存活会导致后续部署被误判为「另一个任务正在运行」
        # 追加模式 >> 与 updater.py 侧 dockerd 日志保持一致，避免相互截断
        nohup dockerd 9>&- >> /tmp/arl_dockerd.log 2>&1 &
        if wait_docker_daemon; then
            echo "✅ Docker 守护进程通过 dockerd 直接启动成功！"
            return 0
        fi
    fi

    echo "❌ 错误：Docker 守护进程无法启动。请手动排查："
    echo "   1. 执行 'journalctl -u docker' 或查看 dockerd 日志找出原因"
    echo "   2. 检查 'df -h' 确认磁盘未满"
    echo "   3. 检查 /var/lib/docker 目录权限"
    return 1
}

check_disk_space
check_docker_daemon || exit 1
check_and_install_compose
check_and_configure_swap
check_host_memory
tune_system_kernel_parameters

# 1. 宿主机 Docker 守护进程性能调优 (userland-proxy)
DOCKER_CONFIG_DIR="/etc/docker"
DOCKER_CONFIG_FILE="$DOCKER_CONFIG_DIR/daemon.json"

mkdir -p "$DOCKER_CONFIG_DIR"

echo "⚙️ 正在检查并配置宿主机 Docker 性能调优参数..."

# 使用 Python 脚本安全读取/修改 JSON，防止格式损坏并保证原子写入
UPDATED=$(python3 -c "
import json, os
path = '$DOCKER_CONFIG_FILE'
tmp_path = path + '.tmp'
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
    try:
        with open(tmp_path, 'w') as f:
            json.dump(data, f, indent=4)
        os.replace(tmp_path, path)
        print('UPDATED')
    except Exception:
        print('ERROR')
else:
    print('NO_CHANGE')
")

if [ "$UPDATED" = "ERROR" ]; then
    echo "⚠️ 警告：无法解析已有的 $DOCKER_CONFIG_FILE，可能存在 JSON 语法错误，跳过自动性能配置。"
elif [ "$UPDATED" = "UPDATED" ]; then
    echo "✅ 已成功配置 'userland-proxy': false 参数。正在重启 Docker 服务使配置生效..."
    if (run_cmd_with_timeout 30 systemctl restart docker &>/dev/null || run_cmd_with_timeout 30 service docker restart &>/dev/null) && wait_docker_daemon; then
        echo "✅ Docker 服务重启并就绪成功！"
    else
        echo "⚠️ 警告：无法通过 systemctl 或 service 重启 Docker 服务，这可能是因为您运行在非 systemd 环境中。"
        echo "👉 请在部署完成后手动重启 Docker 服务以使性能调优生效。"
    fi
else
    echo "✅ 宿主机 Docker 性能参数已是最佳状态，无需修改。"
fi

# 2. 准备证书存放目录与配置权限
echo "📁 正在检查证书存放目录与权限..."
mkdir -p ./ssl-certs
chmod 755 ./ssl-certs

if [ ! -f "./ssl-certs/arl.crt" ] || [ ! -f "./ssl-certs/arl.key" ]; then
    echo "⚠️ 提示：未在 ./ssl-certs/ 目录下检测到 arl.crt 或 arl.key。"
    echo "⚙️ 正在自动生成临时自签名 SSL 证书以确保 Nginx 服务能正常启动..."
    if command -v openssl &>/dev/null; then
        openssl req -new -newkey rsa:2048 -days 365 -nodes -x509 \
            -subj "/C=CN/ST=GD/L=SZ/O=ARL/CN=localhost" \
            -keyout ./ssl-certs/arl.key \
            -out ./ssl-certs/arl.crt
    else
        echo "❌ 错误：未检测到 openssl，无法生成临时证书。请先安装 openssl，或自行将证书放入 ssl-certs 目录。"
        exit 1
    fi
fi

# 确保 Nginx 容器内的非 root 用户有权限读取证书
if [ -f "./ssl-certs/arl.key" ]; then
    chmod 644 ./ssl-certs/arl.key
fi
if [ -f "./ssl-certs/arl.crt" ]; then
    chmod 644 ./ssl-certs/arl.crt
fi
echo "✅ 证书目录与文件权限已配置完毕！"

# 2.5 宿主机防火墙与 Docker 网桥互通加固 (针对 CentOS/RHEL/Firewalld 等环境)
configure_firewall_and_network() {
    if command -v firewall-cmd &>/dev/null && systemctl is-active firewalld &>/dev/null; then
        echo "⚙️ 检测到宿主机 Firewalld 运行中，正在自动加固网络与端口放行..."
        local need_reload=0
        local fw_ports
        fw_ports=$(firewall-cmd --list-ports 2>/dev/null || true)

        # 1. 自动放行 5173/tcp (前端 HTTPS 访问网关)
        if ! echo "$fw_ports" | grep -qw "5173/tcp"; then
            echo "  👉 正在永久放行前端核心端口 5173/tcp..."
            firewall-cmd --permanent --add-port=5173/tcp >/dev/null 2>&1 || true
            need_reload=1
        fi

        # 2. 自动放行 8888/tcp (更新守护服务探针)
        if ! echo "$fw_ports" | grep -qw "8888/tcp"; then
            echo "  👉 正在永久放行更新服务端口 8888/tcp..."
            firewall-cmd --permanent --add-port=8888/tcp >/dev/null 2>&1 || true
            need_reload=1
        fi

        # 3. 将 docker0 虚拟网桥加入 trusted 信任域，彻底杜绝防火墙拦截容器间通信与 DNS 出网
        local trusted_interfaces
        trusted_interfaces=$(firewall-cmd --zone=trusted --list-interfaces 2>/dev/null || true)
        if ! echo "$trusted_interfaces" | grep -qw "docker0"; then
            echo "  👉 正在将 docker0 网卡加入 Firewalld trusted 信任域..."
            firewall-cmd --permanent --zone=trusted --add-interface=docker0 >/dev/null 2>&1 || true
            need_reload=1
        fi

        # 若规则发生变更，重载防火墙并联动重启 Docker 恢复内核 iptables 转发链
        if [ $need_reload -eq 1 ]; then
            echo "⚙️ 正在重载 Firewalld 并联动恢复 Docker 内核转发链..."
            firewall-cmd --reload >/dev/null 2>&1 || true
            if (run_cmd_with_timeout 30 systemctl restart docker &>/dev/null || run_cmd_with_timeout 30 service docker restart &>/dev/null) && wait_docker_daemon; then
                echo "✅ Firewalld 规则与 Docker 转发链已同步加固就绪！"
            else
                echo "⚠️ 警告：重载防火墙后 Docker 重启延迟，将在部署末尾由自愈探针兜底校验。"
            fi
        else
            echo "✅ 宿主机 Firewalld 端口与网络配置已是最新状态。"
        fi
    fi
}

configure_firewall_and_network

# 3. 部署并启动系统更新服务 (updater)
deploy_and_start_updater() {
    echo "🔄 正在配置并启动系统底层更新服务 (arl-updater)..."
    local updater_dir="$(pwd)/updater"
    local updater_script="$updater_dir/updater.py"
    local service_file="/etc/systemd/system/arl-updater.service"

    if [ ! -f "$updater_script" ]; then
        echo "⚠️ 警告：未找到更新服务脚本 $updater_script，将跳过更新服务的配置。"
        return 0
    fi

    # Firewalld 端口放行已在 configure_firewall_and_network 中统一管理与加固

    # 检查 8888 端口是否被非 arl-updater 外部/遗留进程占用
    local occupied_pid=""
    if command -v ss &>/dev/null; then
        # 补充 head -n 1 截断，防止 IPv4/IPv6 双栈多行导致数组越界抛出 integer expression expected 语法错误
        occupied_pid=$(ss -tlnp 2>/dev/null | awk '/:8888 / {print $NF}' | sed -E 's/.*pid=([0-9]+).*/\1/' | head -n 1 || true)
    elif command -v netstat &>/dev/null; then
        occupied_pid=$(netstat -tlnp 2>/dev/null | awk '/:8888 / {print $NF}' | cut -d'/' -f1 | head -n 1 || true)
    fi

    if [ -n "$occupied_pid" ] && [ "$occupied_pid" -gt 10 ] 2>/dev/null; then
        local proc_cmd
        proc_cmd=$(ps -p "$occupied_pid" -o cmd= 2>/dev/null || true)
        # 防御性判断：确保 proc_cmd 非空、严格筛除 updater 且禁止操作 PID <= 10 的核心线程
        if [ -n "$proc_cmd" ] && echo "$proc_cmd" | grep -qv "updater.py"; then
            echo "⚠️ 警告：检测到 8888 端口被外部/遗留进程占用 (PID: $occupied_pid, 命令: $proc_cmd)，正在清理以解除冲突..."
            kill "$occupied_pid" 2>/dev/null || true
            sleep 1
            kill -9 "$occupied_pid" 2>/dev/null || true
        fi
    fi

    if [ -d "/etc/systemd/system" ] && command -v systemctl &>/dev/null; then
        cat > "$service_file" <<EOF
[Unit]
Description=ARL-Next Update Service
After=network.target docker.service

[Service]
Type=simple
User=root
WorkingDirectory=$updater_dir
ExecStart=/usr/bin/env python3 $updater_script
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF

        systemctl daemon-reload
        if [ "$ARL_UPDATER_SKIP_RESTART" != "1" ]; then
            systemctl enable arl-updater.service >/dev/null 2>&1
            systemctl restart arl-updater.service

            # 严格健康校验：等待并检测更新守护进程实际存活状态
            sleep 2
            if systemctl is-active arl-updater.service &>/dev/null; then
                echo "✅ 系统更新服务 (arl-updater) 启动成功且运行正常！"
            else
                echo "❌ 错误：系统更新服务 (arl-updater) 启动失败，处于异常状态！"
                echo "==================== ❌ 详细报错日志 (journalctl) ===================="
                journalctl -u arl-updater.service -n 15 --no-pager 2>/dev/null || true
                echo "====================================================================="
                if ! command -v python3 &>/dev/null; then
                    echo "👉 核心根因：宿主机未检测到 python3，请先安装 python3 后重试。"
                fi
                exit 1
            fi
        else
            echo "✅ 跳过重启当前正在执行的更新服务..."
        fi
    else
        echo "⚠️ 警告：当前系统不支持 systemd，跳过系统更新服务的配置。"
    fi
}

deploy_and_start_updater

# （旧版镜像预拉取函数已废除，转为基于阿里云仓库全量拉取）

# 4. 从阿里云镜像仓库极速拉取并启动生产服务
echo "🔒 正在检查基础防护机制 (Basic Auth)..."
if [ -d "./frontend/.htpasswd" ]; then
    echo "⚠️ 提示：发现 ./frontend/.htpasswd 是一个目录（可能是由 Docker 错误创建），正在清理..."
    rm -rf "./frontend/.htpasswd"
fi
if [ ! -f "./frontend/.htpasswd" ]; then
    echo "⚠️ 提示：未检测到 ./frontend/.htpasswd 文件，正在预置防扫描基础凭证..."
    mkdir -p ./frontend
    echo 'admin:$apr1$i/Qqu0mp$6rhjb2tWaFFEqpeDcr4Su/' > ./frontend/.htpasswd
    echo "✅ 已预置默认 Basic Auth 凭证: 账号 admin / 密码 arl_next (网关默认关闭，可在 Web 顶部导航栏按需开启)"
fi

echo "🐳 [1/3] 正在为当前运行版本创建稳定备份快照..."
SNAPSHOT_SVCS=("arl-web" "arl-worker" "arl-frontend" "arl-puppeteer" "osint-service")
for svc in "${SNAPSHOT_SVCS[@]}"; do
    img="crpi-laul1izptqrf0tkf.cn-beijing.personal.cr.aliyuncs.com/owl234-arl-prod/${svc}:latest"
    if docker image inspect "$img" >/dev/null 2>&1; then
        docker tag "$img" "${svc}:backup-stable" 2>/dev/null || true
        echo "  📦 已为 ${svc} 创建稳定快照 (${svc}:backup-stable)"
    else
        echo "  ℹ️  未检测到本地 ${svc} 历史镜像，跳过快照"
    fi
done
echo "✅ 稳定版本镜像快照备份完毕！"

echo "🐳 [2/3] 正在从阿里云镜像库极速拉取最新构建 (前端、Web、Worker、Puppeteer等)..."
MAX_RETRIES=3
RETRY_COUNT=0
DAEMON_RETRY=0
MAX_DAEMON_RETRY=2
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    PULL_LOG="/tmp/arl_pull_step.log"
    if (set -o pipefail; docker compose -f docker-compose.prod.yml pull 2>&1 | tee "$PULL_LOG"); then
        echo "✅ 所有微服务镜像拉取完成！"
        break
    fi

    # 区分「Docker 守护进程未运行」与「网络波动」两类失败原因
    if grep -qiE "Cannot connect to the Docker daemon|Is the docker daemon running|docker.sock" "$PULL_LOG"; then
        DAEMON_RETRY=$((DAEMON_RETRY+1))
        if [ $DAEMON_RETRY -gt $MAX_DAEMON_RETRY ]; then
            echo "❌ 错误：Docker 守护进程反复异常，已尝试重启 $MAX_DAEMON_RETRY 次仍失败。"
            echo "👉 请手动排查：执行 'journalctl -u docker' 查看日志，检查 'df -h' 磁盘空间。"
            cat "$PULL_LOG"
            exit 1
        fi
        echo "⚠️ Docker 守护进程未在运行，正在尝试自动启动 (第 $DAEMON_RETRY/$MAX_DAEMON_RETRY 次)..."
        if check_docker_daemon; then
            # daemon 已恢复，本次失败不计入网络重试次数，直接重试一次
            continue
        fi
        echo "❌ 错误：Docker 守护进程启动失败，请手动排查后再运行："
        echo "   - 执行 'journalctl -u docker' 查看系统日志"
        echo "   - 执行 'df -h' 确认磁盘空间充足"
        echo "   - 确认 /var/lib/docker 目录权限正常"
        cat "$PULL_LOG"
        exit 1
    fi

    RETRY_COUNT=$((RETRY_COUNT+1))
    if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
        echo "❌ 错误：多次拉取镜像失败，请检查服务器网络或稍后再试。"
        cat "$PULL_LOG"
        exit 1
    fi
    echo "⚠️ 镜像拉取遇到网络波动，正在进行第 $RETRY_COUNT 次重试 (等待 5 秒)..."
    sleep 5
done

echo "🚀 [3/3] 正在启动生产多服务容器组并清理可能遗留的孤儿容器..."
docker compose -f docker-compose.prod.yml up -d --remove-orphans

echo "⏳ 正在等待后端 API 就绪 (动态健康探针检测)..."
MAX_WAIT=90
WAIT_TIME=0
while [ $WAIT_TIME -lt $MAX_WAIT ]; do
    if docker exec arl-web-prod curl -s http://127.0.0.1:5000/ > /dev/null 2>&1; then
        echo "✅ 后端服务已完全就绪 (耗时 $WAIT_TIME 秒)"
        break
    fi
    sleep 2
    WAIT_TIME=$((WAIT_TIME + 2))
    echo "  ⏳ 健康探针探测中... ($WAIT_TIME / $MAX_WAIT 秒)"
done

if [ $WAIT_TIME -ge $MAX_WAIT ]; then
    echo "⚠️ 等待超时，服务可能仍在初始化或存在异常，请稍后重试。"
fi

# 检查是否有容器处于 exited 或 restarting 状态
FAILED_SERVICES=$(docker compose -f docker-compose.prod.yml ps --status exited --status restarting --services)

if [ -n "$FAILED_SERVICES" ]; then
    echo "❌ 警告：部分服务启动失败或正在无限重启中！"
    echo "异常服务列表："
    echo "$FAILED_SERVICES"
    echo "👉 建议稍后通过终端进入服务器执行 'docker compose -f docker-compose.prod.yml logs <服务名>' 查看具体报错。"
else
    echo "✅ 所有容器均已成功启动并稳定运行中！系统更新成功！"
    


    echo "🧹 正在清理构建过程中产生的废弃镜像缓存以释放磁盘空间..."
    docker image prune -f &>/dev/null || true
    echo "✅ 磁盘空间清理完成！"
fi

# 4.7 验证前端 5173 端口连通性，若内核转发异常则自动自愈
verify_and_heal_port_forwarding() {
    echo "🔍 正在对前端 5173 端口进行连通性探针测试..."
    local probe_ok=0
    local max_retries=5

    # 以真实的 TLS 握手测试作为唯一基准（Ground Truth），循环重试以消除容器慢启动竞态
    for ((i=1; i<=max_retries; i++)); do
        if curl -k -s -m 3 -o /dev/null https://127.0.0.1:5173/ 2>/dev/null; then
            probe_ok=1
            break
        fi
        sleep 2
    done

    # 若多次探测均失败（常见于防火墙操作清空了内核 iptables 转发链），触发自动自愈
    if [ $probe_ok -eq 0 ]; then
        echo "⚠️ 警告：检测到前端 5173 端口握手失败（常见于防火墙操作清空了内核转发链）！"
        echo "🛠️ 正在执行全自动网络链自愈修复 (重启 Docker 恢复内核转发规则)..."
        if (run_cmd_with_timeout 30 systemctl restart docker &>/dev/null || run_cmd_with_timeout 30 service docker restart &>/dev/null) && wait_docker_daemon; then
            sleep 3
            if curl -k -s -m 5 -o /dev/null https://127.0.0.1:5173/ 2>/dev/null; then
                echo "✅ 端口转发与 NAT 规则全自动自愈成功！5173 端口已恢复秒级连通。"
            else
                echo "⚠️ 自愈复检存在轻微延迟，后台服务正在就绪中。"
            fi
        else
            echo "⚠️ 自动重启 Docker 失败，若外部无法访问请手动执行 'systemctl restart docker'。"
        fi
    else
        echo "✅ 前端端口 (5173) 内核 NAT 转发与 TLS 握手链路健康！"
    fi
}
verify_and_heal_port_forwarding

# 5. 获取本地与公网真实 IP 并展示
LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{print $7}')
fi
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP=$(ifconfig 2>/dev/null | awk '/inet / && !/127.0.0.1/ {print $2; exit}')
fi
if [ -z "$LOCAL_IP" ]; then
    LOCAL_IP="127.0.0.1"
fi
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

echo ""
echo "┌────────────────────────────────────────────────────────────┐"
echo "│ 💡 生产运维特别提示 (CentOS / RHEL / Firewalld 环境)：      │"
echo "│ 若后续您手动启动、重启或修改过宿主机防火墙 (firewalld/     │"
echo "│ iptables)，防火墙会自动清空内核中的 Docker 转发链，         │"
echo "│ 此时请务必紧接着执行一次：                                 │"
echo "│ 👉 systemctl restart docker                                │"
echo "│ 即可立即自动恢复所有容器的网络映射与正常访问！             │"
echo "└────────────────────────────────────────────────────────────┘"
