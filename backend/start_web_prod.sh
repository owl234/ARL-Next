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
# 配置源优先级：运行时 config.yaml > 入库模板 config.yaml.example
CONFIG_SRC=/code/backend/config.yaml
if [ ! -f "$CONFIG_SRC" ]; then
    CONFIG_SRC=/code/backend/config.yaml.example
fi
cp "$CONFIG_SRC" /tmp/config.yaml.tmp
sed -i 's/127.0.0.1:27018/mongodb:27017/g' /tmp/config.yaml.tmp
sed -i 's/127.0.0.1:5673/rabbitmq:5672/g' /tmp/config.yaml.tmp
cp -f /tmp/config.yaml.tmp /code/backend/app/config.yaml
rm -f /tmp/config.yaml.tmp

echo "🛡️ 正在确保默认管理员账号存在..."
python3 inject_user.py

WEB_WORKERS="${ARL_WEB_WORKERS:-4}"
if ! [[ "$WEB_WORKERS" =~ ^[1-9][0-9]*$ ]]; then
    echo "⚠️ 警告：ARL_WEB_WORKERS=${WEB_WORKERS} 非法，已回退为默认值 4"
    WEB_WORKERS=4
elif [ "$WEB_WORKERS" -gt 16 ]; then
    echo "⚠️ 警告：ARL_WEB_WORKERS=${WEB_WORKERS} 超出上限，已收敛为 16"
    WEB_WORKERS=16
fi

echo "🚀 正在前台拉起 Web Backend API (workers=${WEB_WORKERS}, threads=4)..."
gunicorn --preload -b 0.0.0.0:5000 app.main:arl_app -w "$WEB_WORKERS" --threads 4 --worker-class gthread -t 120 --max-requests 1000 --max-requests-jitter 50
