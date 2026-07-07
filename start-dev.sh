#!/bin/bash
# ARL-Next 极简开发环境一键启动脚本

set -e

echo "🚀 正在启动后台 Docker 开发服务 (API / Worker / MongoDB / RabbitMQ)..."
# 1. 自动以守护进程方式构建并启动后端容器组
docker compose -f docker-compose.dev.yml up -d --build

# 2. 进入前端目录并准备本地开发服务
echo "📦 正在检查并准备前端本地开发环境..."
cd frontend

# 检测本地是否安装了 pnpm，如果没有则尝试自动全局安装
if ! command -v pnpm &> /dev/null; then
    echo "⚠️ 提示：本地未检测到 pnpm 包管理器，尝试通过 npm 自动安装..."
    npm install -g pnpm || sudo npm install -g pnpm
fi

echo "📥 正在安装前端 node_modules 依赖包 (首次运行较慢)..."
pnpm install

echo "✨ 正在前台拉起前端 Vite 本地开发服务器 (支持修改代码实时重载)..."
pnpm run dev
