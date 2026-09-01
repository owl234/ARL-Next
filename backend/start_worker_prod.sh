#!/bin/bash
# ARL-Next 容器内后端统一自启脚本

set -e

echo "🚀 等待数据库和消息队列就绪..."
/usr/bin/wait-for-it.sh mongodb:27017 -t 60
/usr/bin/wait-for-it.sh rabbitmq:5672 -t 60

cd /code/backend
source /code/backend/.venv-docker/bin/activate
# (可选) 在启动前用 sed 临时将 config.yaml 中的 127.0.0.1 替换为容器内部的网络别名
# 这样你原本的代码完全不用改！
# 确保应用读到正确的配置文件
cp /code/backend/config.yaml /tmp/config.yaml.tmp
sed -i 's/127.0.0.1:27018/mongodb:27017/g' /tmp/config.yaml.tmp
sed -i 's/127.0.0.1:5673/rabbitmq:5672/g' /tmp/config.yaml.tmp
cp -f /tmp/config.yaml.tmp /code/backend/app/config.yaml
rm -f /tmp/config.yaml.tmp

echo "🚀 正在后台拉起 Celery 任务处理器..."
# 获取配置中的并发数量，添加了极强的异常捕获以防止 MongoDB 未就绪时导致的 Bash 崩溃
HEAVY=$(python3 -c "
try:
    from app.utils.performance_config import get_performance_config
    print(get_performance_config().get('celery_heavy_concurrency', 2))
except Exception:
    print(2)
" 2>/dev/null || echo 2)
if ! [[ "$HEAVY" =~ ^[0-9]+$ ]]; then HEAVY=2; fi

LIGHT=$(python3 -c "
try:
    from app.utils.performance_config import get_performance_config
    print(get_performance_config().get('celery_light_concurrency', 2))
except Exception:
    print(2)
" 2>/dev/null || echo 2)
if ! [[ "$LIGHT" =~ ^[0-9]+$ ]]; then LIGHT=2; fi

if [ "$HEAVY" -gt 0 ] || [ "$LIGHT" -gt 0 ]; then
    echo "Starting HEAVY workers: $HEAVY, LIGHT workers: $LIGHT"

    if [ "$LIGHT" -gt 0 ]; then
        # 后台启动轻任务队列，并给它更大的 tasks-per-child 与 300MB 内存熔断
        python3 /code/backend/.venv-docker/bin/celery -A app.celerytask.celery worker -Q arltask_light -n arltask_light -c "$LIGHT" --max-tasks-per-child=50 --max-memory-per-child=300000 -l info &
    fi
    
    if [ "$HEAVY" -gt 0 ]; then
        # 后台启动重任务队列，并且严格限制 max-tasks-per-child=5 与 500MB 内存优雅熔断（任务执行后回收）
        python3 /code/backend/.venv-docker/bin/celery -A app.celerytask.celery worker -Q arltask,arltask_heavy -n arltask_heavy -c "$HEAVY" --max-tasks-per-child=5 --max-memory-per-child=500000 -l info &
    fi
else
    echo "Both Concurrency is 0, sleep"
    sleep 3600000000
fi

# 后台启动 GitHub 扫描 Celery worker (配置 300MB 内存熔断)
python3 /code/backend/.venv-docker/bin/celery -A app.celerytask.celery worker -Q arlgithub -n arlgithub -c 2 --max-tasks-per-child=100 --max-memory-per-child=300000 -l info &
# 后台启动 Celery 定时任务调度器 (Scheduler)
python3 /code/backend/.venv-docker/bin/celery -A app.celerytask.celery beat -l info &

echo "🚀 正在前台拉起 ARL 监控任务调度引擎..."
python3 -m app.scheduler
