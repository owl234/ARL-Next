# 阶段一：构建依赖环境
FROM python:3.13-slim AS builder

WORKDIR /osint_service

# 安装 curl 下载 uv，随后卸载以保持极简化，规避 urllib 被 403 拦截的问题
RUN apt-get update && apt-get install -y --no-install-recommends curl ca-certificates && \
    curl -LsSf https://astral.sh/uv/install.sh | env UV_INSTALL_DIR="/usr/local/bin" sh && \
    apt-get purge -y --auto-remove curl && rm -rf /var/lib/apt/lists/*

# 创建虚拟环境（物理隔离）
RUN python3 -m venv /opt/venv
ENV VIRTUAL_ENV="/opt/venv"
ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# 优先单独拷贝 requirements.txt，确保业务代码的修改不会导致每次都重新下载依赖！
COPY requirements.txt .
RUN uv pip install --no-cache -r requirements.txt && \
    pip uninstall -y pip setuptools

# 阶段二：生产运行环境 (强制遵守纯净运行环境红线)
FROM python:3.13-slim

WORKDIR /osint_service

# 仅拷贝上一个阶段编译好的隔离虚拟环境
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 最后拷贝业务代码
COPY . /osint_service/

EXPOSE 16181

CMD ["python3", "icpApi.py"]
