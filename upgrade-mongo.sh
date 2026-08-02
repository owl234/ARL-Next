#!/bin/bash
# MongoDB 4.0 -> 7.0 自动化安全升级脚本
set -e

COMPOSE_FILE="docker-compose.prod.yml"
BACKUP_DIR="./mongo_backup_$(date +%Y%m%d%H%M%S)"
MONGO_USER="admin"
MONGO_PASS="admin"
AUTH_DB="admin"
CONTAINER_NAME="arl-mongodb-prod"

echo "================================================="
echo " 🚀 ARL-Next MongoDB 4.0 -> 7.0 自动升级程序"
echo "================================================="

echo "[1/6] 停止所有业务侧容器，避免备份时产生脏数据..."
docker compose -f $COMPOSE_FILE stop arl-worker arl-puppeteer arl-web arl-frontend osint-service autoheal

echo "[2/6] 导出 MongoDB 4.0 数据 (保存在容器内并提取至宿主机)..."
docker compose -f $COMPOSE_FILE exec mongodb sh -c "mkdir -p /tmp/backup && mongodump -u $MONGO_USER -p $MONGO_PASS --authenticationDatabase $AUTH_DB --out /tmp/backup"
docker cp $CONTAINER_NAME:/tmp/backup $BACKUP_DIR
echo "✅ 数据已成功备份至宿主机: $BACKUP_DIR"

echo "[3/6] 停止旧版 4.0 数据库..."
docker compose -f $COMPOSE_FILE stop mongodb
docker compose -f $COMPOSE_FILE rm -f mongodb

echo "[4/6] 修改配置文件 $COMPOSE_FILE (切版本 & 建新卷)..."
# 替换为 7.0 官方公有镜像
sed -i.bak 's|image: crpi-laul1izptqrf0tkf.cn-beijing.personal.cr.aliyuncs.com/owl234-arl-prod/mongo:4.0.27|image: mongo:7.0|g' $COMPOSE_FILE
# 替换数据卷，保障旧卷无损
sed -i.bak 's/mongo_data/mongo_data_v7/g' $COMPOSE_FILE
echo "✅ 已生成全新数据卷 mongo_data_v7"

echo "[5/6] 启动 MongoDB 7.0 新库并等待初始化..."
docker compose -f $COMPOSE_FILE up -d mongodb
echo "⏳ 等待 15 秒让数据库完全启动并创建 admin 账号..."
sleep 15

echo "[6/6] 导入旧数据至 MongoDB 7.0..."
docker cp $BACKUP_DIR $CONTAINER_NAME:/tmp/backup
docker compose -f $COMPOSE_FILE exec mongodb sh -c "mongorestore -u $MONGO_USER -p $MONGO_PASS --authenticationDatabase $AUTH_DB --dir /tmp/backup"

echo "================================================="
echo " 🎉 升级完成！恢复所有业务容器..."
docker compose -f $COMPOSE_FILE up -d

echo "================================================="
echo " 💡 升级后状态报告:"
echo " 1. 业务已全部拉起，数据库现运行在 MongoDB 7.0"
echo " 2. 旧版数据卷 'mongo_data' 原封不动保留，随时可回滚"
echo " 3. 宿主机备份文件夹: $BACKUP_DIR (建议系统稳定运行三天后再删除)"
echo " 4. $COMPOSE_FILE 原文件已备份为 ${COMPOSE_FILE}.bak"
echo "================================================="
