#!/bin/bash
# ARL 生产环境自动化初始化脚本

echo "🚀 开始初始化 ARL 部署环境..."

# 1. 自动生成或加载 .env 环境变量文件
if [ ! -f ".env" ]; then
    echo "📄 未检测到 .env 文件，正在生成高强度随机密码..."
    # 使用 openssl 生成 16 位的强随机密码
    MONGO_PASS=$(openssl rand -hex 8)
    RABBITMQ_PASS=$(openssl rand -hex 8)

    cat <<EOF > .env
# ==========================================
# ARL 生产环境系统级配置 (由 init_env.sh 自动生成)
# ==========================================
MONGO_PASSWORD=${MONGO_PASS}
RABBITMQ_PASSWORD=${RABBITMQ_PASS}

# 可以在这里添加其他的环境变量
EOF
    echo "✅ .env 文件已生成！"
else
    echo "✅ .env 文件已存在，保留当前环境变量。"
fi

# 2. 自动生成 config-docker.yaml
if [ ! -f "backend/config-docker.yaml" ]; then
    echo "📄 未检测到 config-docker.yaml，正在从模板构建..."

    # 复制模板
    cp backend/config-docker.example.yaml backend/config-docker.yaml

    # 将刚刚生成的随机密码替换到配置文件中 (使用 sed)
    # 注意：这里的 sed 兼容 Linux (Ubuntu/CentOS)
    source .env
    sed -i "s/YOUR_RABBITMQ_PASS/${RABBITMQ_PASSWORD}/g" backend/config-docker.yaml
    sed -i "s/YOUR_MONGO_PASS/${MONGO_PASSWORD}/g" backend/config-docker.yaml

    echo "✅ config-docker.yaml 已自动生成并注入了安全密码！"
    echo "⚠️ 提示: FOFA Key, Webhook 等第三方配置需手动编辑 backend/config-docker.yaml 补充。"
else
    echo "✅ config-docker.yaml 已存在，跳过生成。"
fi

# 3. 设置数据卷目录权限 (防止 Docker 挂载时出现 Permission Denied)
echo "🔧 初始化数据卷目录..."
mkdir -p mongo_data
chmod -R 777 mongo_data

echo "🎉 恭喜！环境初始化完成。"
echo "下一步，您可以直接运行: docker compose -f docker-compose.test.yml up -d"