#!/bin/bash

# ARL-Next 本地开发环境(容器内)初始化脚本
# 此脚本应在 arl-dev-env 容器内部执行！
# 所有的系统二进制工具将被安装到 /usr/local/bin 中，而不是 /code 下。

set -e

echo "🚀 开始在容器内初始化 ARL-Next 后端开发环境..."

# 1. 替换国内高速镜像源 (Ubuntu 22.04 Jammy)
echo "📦 配置高速 APT 镜像源..."
ARCH=$(dpkg --print-architecture)
if [ "$ARCH" = "arm64" ] || [ "$ARCH" = "armhf" ]; then
    UBUNTU_REPO="mirrors.aliyun.com/ubuntu-ports"
else
    UBUNTU_REPO="mirrors.aliyun.com/ubuntu"
fi

cat <<EOF > /etc/apt/sources.list
deb http://${UBUNTU_REPO}/ jammy main restricted universe multiverse
deb http://${UBUNTU_REPO}/ jammy-security main restricted universe multiverse
deb http://${UBUNTU_REPO}/ jammy-updates main restricted universe multiverse
deb http://${UBUNTU_REPO}/ jammy-backports main restricted universe multiverse
EOF

apt-get update -o Acquire::Retries=10

# 2. 安装核心编译依赖和 Python 环境
echo "📦 安装系统级依赖和编译工具..."
apt-get install -y --no-install-recommends \
    wget unzip bzip2 git curl tzdata \
    gcc g++ make automake autoconf libtool \
    libffi-dev libssl-dev python3 python3-dev python3-pip python3-venv \
    libxml2-dev libxslt1-dev zlib1g-dev \
    fontconfig chromium-browser fonts-wqy-zenhei fonts-wqy-microhei

# 3. 编译 MassDNS (全局安装)
if ! command -v massdns &> /dev/null; then
    echo "🔨 开始从源码编译 MassDNS..."
    cd /tmp
    wget https://github.com/blechschmidt/massdns/archive/refs/tags/v1.1.0.tar.gz
    tar xvf v1.1.0.tar.gz
    cd massdns-1.1.0
    make -j$(nproc)
    cp bin/massdns /usr/local/bin/massdns
    chmod +x /usr/local/bin/massdns
    echo "✅ MassDNS 编译安装完成！"
else
    echo "✅ MassDNS 已全局安装。"
fi

# 4. 编译 Nmap 7.95
if ! command -v nmap &> /dev/null; then
    echo "🔨 开始从源码编译 Nmap 7.95..."
    cd /tmp
    wget https://nmap.org/dist/nmap-7.95.tar.bz2
    bzip2 -cd nmap-7.95.tar.bz2 | tar xvf -
    cd nmap-7.95
    ./configure --without-zenmap
    make -j$(nproc)
    make install
    echo "✅ Nmap 编译安装完成！"
else
    echo "✅ Nmap 已安装。"
fi

# 5. 下载 Nuclei (Go 编译二进制，跨平台)
if ! command -v nuclei &> /dev/null; then
    echo "🚀 开始安装 Nuclei..."
    cd /tmp
    ARCH=$(dpkg --print-architecture)
    if [ "$ARCH" = "amd64" ]; then
        NUCLEI_ZIP="nuclei_3.3.0_linux_amd64.zip"
    else
        NUCLEI_ZIP="nuclei_3.3.0_linux_arm64.zip"
    fi
    wget -t 10 --retry-connrefused "https://github.com/projectdiscovery/nuclei/releases/download/v3.3.0/$NUCLEI_ZIP" -O $NUCLEI_ZIP || wget -t 10 "https://ghproxy.cn/https://github.com/projectdiscovery/nuclei/releases/download/v3.3.0/$NUCLEI_ZIP" -O $NUCLEI_ZIP
    unzip $NUCLEI_ZIP
    mv nuclei /usr/local/bin/
    chmod +x /usr/local/bin/nuclei
    echo "✅ Nuclei 安装完成！"
    /usr/local/bin/nuclei -update-templates || true
fi

# 6. 配置 Python 虚拟环境与依赖
echo "🐍 开始安装 Python 依赖库..."
cd /code/backend
# 为了防止与宿主机Mac本地可能已经存在的 .venv 冲突，我们在容器里专用 .venv-docker
rm -rf .venv-docker
python3 -m venv .venv-docker
source .venv-docker/bin/activate
pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
pip install -e ./ARL-NPoC

echo "🎉 容器内开发环境初始化完成！"
echo "你可以使用以下命令激活 Python 虚拟环境并启动应用："
echo "source /code/backend/.venv-docker/bin/activate && python3 -m app.main"
