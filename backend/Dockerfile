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
# 使用国内阿里云镜像源加速 apt-get (可选，建议在本地构建时开启)
RUN sed -i 's/deb.debian.org/mirrors.aliyun.com/g' /etc/apt/sources.list && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    nmap \
    gcc \
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

RUN npm config set registry https://registry.npmmirror.com/ && \
    npm install -g puppeteer-core@10.4.0

# 5. 复制依赖清单并安装 (利用 Docker 缓存)
COPY requirements.txt /code/
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 6. 安装本地 ARL-NPoC 插件库
COPY ARL-NPoC /code/ARL-NPoC/
RUN pip install /code/ARL-NPoC/

# 7. 复制所有后端代码
COPY . /code/

# 8. 赋予脚本执行权限
RUN cp /code/wait-for-it.sh /usr/bin/wait-for-it.sh && \
    chmod +x /usr/bin/wait-for-it.sh

# 9. 赋予 ARL 自带工具执行权限
RUN chmod +x /code/app/tools/massdns /code/app/tools/phantomjs || true

EXPOSE 5000

CMD ["/bin/bash"]