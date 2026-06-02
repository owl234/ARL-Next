# 阶段一：构建 Vue3 代码
FROM node:20-alpine AS builder
WORKDIR /app

## 启用 corepack 以支持 pnpm
#RUN corepack enable && corepack prepare pnpm@latest --activate

# 🎯 修复核心：放弃 corepack 的 latest 机制，显式全局安装极其稳定的 pnpm v9
RUN npm install -g pnpm@9

# 利用 Docker 缓存层，先复制 package.json 和 pnpm-lock.yaml
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# 复制源码并打包
COPY . .
RUN pnpm run build

# 阶段二：使用 Nginx 部署静态文件
FROM nginx:alpine
# 将构建好的 dist 文件复制到 Nginx 默认目录
COPY --from=builder /app/dist /usr/share/nginx/html

# 这里预留一个自定义 Nginx 配置的坑位（解决路由和反向代理问题）
# COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]



# 阶段二：使用 Nginx 部署静态文件
FROM nginx:alpine
COPY --from=builder /app/dist /usr/share/nginx/html

# 🚀 [必须新增这行代码]：将你的反向代理配置塞进容器
COPY default.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]