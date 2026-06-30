#!/bin/bash

# 确保进入项目根目录
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "🚀 正在一键拉起 ARL-Next 本地开发环境..."

# 1. 确保底层的数据库和队列处于启动状态
brew services start mongodb-community@7.0 2>/dev/null
brew services start redis 2>/dev/null

# 2. 使用 concurrently 并发执行前端、后端API和Celery任务
# 好处：统一管理日志（不同颜色区分），且按一次 Ctrl+C 就能干净地关掉所有进程！
npx concurrently \
  -n "WEB_API,WORKER,VUE_APP" \
  -c "bgBlue.bold,bgMagenta.bold,bgGreen.bold" \
  "cd backend && source .venv/bin/activate && python3 -m app.main" \
  'cd backend && source .venv/bin/activate && CONC=$(python3 -c "from app.utils.performance_config import get_performance_config; print(get_performance_config())" | tail -n 1) && celery -A app.celerytask.celery worker -Q arltask -n arltask -c ${CONC:-2} -l info' \
  "cd frontend && pnpm run dev"
