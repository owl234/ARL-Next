#!/bin/bash
# ARL-Next 容器内后端统一自启脚本

set -e

echo "🚀 等待数据库和消息队列就绪..."
sleep 5

# 如果虚拟环境不存在，说明是第一次启动，自动创建并安装依赖
if [ ! -d "/code/backend/.venv-docker" ]; then
    echo "🐍 初次运行，正在容器内部创建专用的 Python 虚拟环境..."
    cd /code/backend
    python3 -m venv .venv-docker
    source .venv-docker/bin/activate
    pip install --upgrade pip -i https://pypi.tuna.tsinghua.edu.cn/simple
    pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
    pip install -e ./ARL-NPoC
else
    cd /code/backend
    source /code/backend/.venv-docker/bin/activate
fi

# (可选) 在启动前用 sed 临时将 config.yaml 中的 127.0.0.1 替换为容器内部的网络别名
# 这样你原本的代码完全不用改！
# 确保应用读到正确的配置文件
cp /code/backend/config.yaml /tmp/config.yaml.tmp
sed -i 's/127.0.0.1:27018/mongodb:27017/g' /tmp/config.yaml.tmp
sed -i 's/127.0.0.1:5673/rabbitmq:5672/g' /tmp/config.yaml.tmp
cp -f /tmp/config.yaml.tmp /code/backend/app/config.yaml
rm -f /tmp/config.yaml.tmp

echo "🚀 正在后台拉起 Celery 任务处理器..."
# 尝试获取系统的最佳并发数配置
CONC=$(python3 -c "from app.utils.performance_config import get_performance_config; print(get_performance_config())" 2>/dev/null | tail -n 1)



# 后台启动 Celery
celery -A app.celerytask.celery worker -Q arltask -n arltask -c ${CONC:-2} -l info &
# 后台启动 GitHub 扫描 Celery worker
celery -A app.celerytask.celery worker -Q arlgithub -n arlgithub -c 2 -l info &
# 后台启动 Celery 定时任务调度器 (Scheduler)
celery -A app.celerytask.celery beat -l info &

echo "🚀 正在前台拉起 ARL 监控任务调度引擎..."
python3 -m app.scheduler
