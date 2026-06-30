# 1. 🚀 升级基础镜像到 bullseye，解决 404 仓库问题
FROM python:3.8-slim-bullseye

# 2. 设置工作目录
WORKDIR /code

# 3. 设置环境变量
ENV PYTHONUNBUFFERED=1 \
    TZ=Asia/Shanghai \
    LANG=en_US.UTF-8 \
    DEBIAN_FRONTEND=noninteractive \
    NODE_PATH=/usr/local/lib/node_modules

# 4. 🚀 [系统级重构] 安装系统依赖 & Nmap 武器库
# 使用阿里云镜像源替换默认源，极大加速 apt 下载 (尤其是 chromium 等大文件)
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    echo "deb http://mirrors.aliyun.com/debian/ bullseye main non-free contrib" > /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian-security/ bullseye-security main" >> /etc/apt/sources.list && \
    echo "deb http://mirrors.aliyun.com/debian/ bullseye-updates main non-free contrib" >> /etc/apt/sources.list && \
    apt-get update -o Acquire::Retries=10 && \
    apt-get install -y --no-install-recommends -o Acquire::Retries=10 --fix-missing \
    wget \
    unzip \
    bzip2 \
    gcc \
    automake \
    autoconf \
    libtool \
    g++ \
    libffi-dev \
    libssl-dev \
    python3-dev \
    libxml2-dev \
    libxslt1-dev \
    zlib1g-dev \
    make \
    fontconfig \
    chromium \
    nodejs \
    npm \
    fonts-wqy-zenhei \
    fonts-wqy-microhei \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# 从源码编译安装最新版 Nmap 7.95 (自带最新特征库)
RUN wget https://nmap.org/dist/nmap-7.95.tar.bz2 && \
    bzip2 -cd nmap-7.95.tar.bz2 | tar xvf - && \
    cd nmap-7.95 && \
    ./configure --without-zenmap && \
    make -j$(nproc) && \
    make install && \
    cd .. && \
    rm -rf nmap-7.95 nmap-7.95.tar.bz2


# 下载并安装 Nuclei v3.3.0 及其漏洞模板 (通过 ghproxy 加速下载)
RUN wget -t 10 --retry-connrefused https://mirror.ghproxy.com/https://github.com/projectdiscovery/nuclei/releases/download/v3.3.0/nuclei_3.3.0_linux_amd64.zip && \
    unzip nuclei_3.3.0_linux_amd64.zip && \
    mv nuclei /usr/local/bin/ && \
    rm -rf nuclei_3.3.0_linux_amd64.zip README* LICENSE.md && \
    nuclei -update-templates

# 下载并安装 wih (Web Info Hunter) 自动适配架构，通过 ghproxy 加速
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then \
        wget -t 10 --retry-connrefused -O /usr/local/bin/wih https://mirror.ghproxy.com/https://raw.githubusercontent.com/adysec/ARL/master/tools/wih/wih_linux_amd64; \
    elif [ "$ARCH" = "arm64" ]; then \
        wget -t 10 --retry-connrefused -O /usr/local/bin/wih https://mirror.ghproxy.com/https://raw.githubusercontent.com/adysec/ARL/master/tools/wih/wih_linux_arm64; \
    fi && \
    chmod +x /usr/local/bin/wih

RUN npm config set registry https://registry.npmmirror.com/ && \
    npm install -g puppeteer-core@10.4.0

# 5. 复制依赖清单并安装 (利用 Docker 缓存)
COPY requirements.txt /code/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 6. 安装本地 ARL-NPoC 插件库
COPY ARL-NPoC /code/ARL-NPoC/
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install /code/ARL-NPoC/

# 7. 复制所有后端代码
COPY . /code/

# 8. 赋予脚本执行权限
RUN cp /code/wait-for-it.sh /usr/bin/wait-for-it.sh && \
    chmod +x /usr/bin/wait-for-it.sh

# 9. 赋予 ARL 自带工具执行权限
RUN chmod +x /code/app/tools/massdns /code/app/tools/phantomjs || true

EXPOSE 5000

CMD ["/bin/bash"]