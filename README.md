<div align="center">

  # ARL-Next
  **自动化资产侦察与漏洞监控平台**

  <p>
    <a href="https://github.com/owl234/arl-next/actions"><img src="https://img.shields.io/github/actions/workflow/status/owl234/arl-next/ci.yml?style=flat-square&logo=github&label=Build" alt="build"></a>
    <a href="https://hub.docker.com/"><img src="https://img.shields.io/badge/docker-ready-blue.svg?style=flat-square&logo=docker" alt="Docker"></a>
    <a href="https://github.com/owl234/arl-next/releases"><img src="https://img.shields.io/github/v/release/owl234/arl-next?style=flat-square&color=success" alt="Release"></a>
    <img src="https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square&logo=python" alt="Python">
    <img src="https://img.shields.io/badge/vue-3.x-4fc08d?style=flat-square&logo=vuedotjs" alt="Vue">
  </p>

  [**English**](./README_EN.md) | [**本地开发教程**](./docs/local_dev_guide.md) | [**更新日志**](./CHANGELOG.md) | [**在线文档**](https://your-doc-link.com)
</div>

<br/>

---

## 💡 什么是 ARL-Next？

ARL-Next 旨在为安全团队及红蓝对抗工程师提供一套开箱即用的资产监控与漏洞发现平台。它将资产发现、端口扫描、指纹识别到漏洞探测融为一体，并通过 Vue 3 控制台呈现全局安全态势。

## 🤝 致谢与声明

**ARL-Next** 是基于开源项目 [ARL (Asset Reconnaissance Lighthouse) 资产侦察灯塔](https://github.com/TophantTechnology/ARL) 进行重构与二次开发的增强版本。

我们对原 ARL 开发团队为信息安全开源社区做出的巨大贡献表示最诚挚的感谢！本着开源互助的精神，ARL-Next 将继续遵循开源精神。

### 🌟 为什么要重构 ARL-Next？

随着网络环境的演变，我们对原项目进行了现代化改造，以解决部分历史痛点：

* **前端栈升级**：重构前端，基于 Vue 3 + 现代 UI 框架构建，提供更流畅的交互体验。
* **部署架构解耦**：引入全面的 Docker 化构建流程，支持自动化部署与数据卷解耦持久化。

---

## ✨ 核心特性

* **前后端分离架构**
  前端基于 Vue 3 + Vite + Ant Design Vue 构建 SPA 面板，后端依托 Python 3.8+ 与 Flask 提供 RESTful API，提高交互体验和二次开发扩展性。
* **现代 Web 无头渲染**
  重构底层截图与指纹探测引擎，使用 Chromium 与 Puppeteer 替代 PhantomJS。支持 React、Vue 等 SPA（单页面应用）截图和 Wappalyzer 指纹解析，内置中文字库解决乱码问题。
* **Nuclei v3 漏洞引擎**
  内置 Nuclei v3.3.0 及最新漏洞模板，支持 `-tags` 分类扫描。PoC 武器库持续更新，并对接 FOFA 等第三方资产引擎，实现自动化资产收集与漏洞探测。
* **可视化仪表盘**
  新增 Dashboard 统计面板，一览资产总量（域名 / IP / 站点）、任务执行状态及系统实时负载，支持系统日志自动轮转（30 天 TTL）。
* **系统设置中心**
  全新系统设置页面，支持在 Web 界面直接管理：扫描字典（预览 / 搜索 / 追加 / 删除条目）、自定义端口扫描范围（内置 Top 100 / Top 1000 / 全端口字典）、FOFA / GitHub Token / 代理等全局参数，以及钉钉 / 飞书 / 企业微信 / Email 消息推送配置。
* **GitHub 管理整合**
  将 GitHub 任务列表与监控列表合并为统一的管理界面，减少导航层级，操作更直接。

---

## 🏗️ 架构设计

ARL-Next 采用微服务容器编排设计：

1. **安全网关与展示层 (Frontend)**：基于 Vite 构建前端代理与静态资源托管。
2. **业务逻辑层 (Backend)**：基于 Flask，负责接收前端指令、操作 MongoDB 数据库。
3. **异步执行层 (Workers)**：核心节点 (worker)、GitHub 监控节点 (worker-github) 与定时调度器 (scheduler) 协同处理高耗时扫描任务。
4. **持久化存储 (Database)**：MongoDB 负责海量扫描结果与资产数据的落地。

---

## 🚀 部署指南

我们为开发者提供了两套部署方案，满足从二次开发到生产环境的不同需求。

### 方案 A：前端本地 + Docker 后端源码部署 (推荐开发者使用)

**适用场景**：调试前端 UI、修改后端接口逻辑。后端所有服务（API / Worker / 数据库）运行在 Docker 中（**源码卷挂载，修改代码即时生效**），前端在本地以 Vite 开发服务器运行，通过代理透传请求。

> **前置条件**：已安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/) 和 [Node.js](https://nodejs.org/)（附带 npm），并全局安装 pnpm：`npm install -g pnpm`

---

#### 第一步：构建并启动后端容器

```bash
# 克隆代码
git clone https://github.com/owl234/arl-next
cd arl-next

# 首次构建后端镜像（含 MassDNS / Nmap / Nuclei / Chromium，耗时约 10~20 分钟）
# 后续代码变更无需重复 build，直接 up 即可
docker-compose -f docker-compose.local.yml build backend

# 启动全部后端服务（backend API、worker、worker-github、scheduler、MongoDB、RabbitMQ）
# 后端 API 将监听在本机的 5003 端口
docker-compose -f docker-compose.local.yml up -d backend worker worker-github scheduler mongodb rabbitmq
```

> **说明**：`docker-compose.local.yml` 将 `./backend` 目录以卷挂载的方式注入容器，修改后端 Python 代码后 gunicorn 会自动重载，无需重新 build 镜像。

---

#### 第二步：初始化管理员账号（仅首次）

容器启动后，向后端容器内注入默认管理员账号：

```bash
docker exec arl_backend_local bash -c \
  "cd /code/backend && python3 inject_user.py"
```

默认账号密码：`admin` / `arlpass`

---

#### 第三步：配置前端 API 代理

确认 `frontend/vite.config.js` 中的代理地址与 `docker-compose.local.yml` 中 backend 暴露的端口一致：

```js
// frontend/vite.config.js
proxy: {
  '/api': {
    target: 'http://127.0.0.1:5003',  // 对应 docker-compose.local.yml 的 "5003:5000"
    changeOrigin: true,
  }
}
```

---

#### 第四步：启动前端开发服务器

```bash
cd frontend

# 首次安装依赖
pnpm install

# 启动 Vite 开发服务器（支持热重载）
pnpm run dev
```

启动后访问控制台打印的本地地址（默认 `https://localhost:5174`）即可进入系统。

> **HTTPS 证书（可选）**：如需开启 HTTPS 避免浏览器安全拦截，可使用 `mkcert` 生成本地证书并放置于项目根目录 `certs/` 下，Vite 会自动读取。详见 [本地开发教程](./docs/local_dev_guide.md)。

---

#### 常用后端管理命令

```bash
# 查看所有容器状态
docker-compose -f docker-compose.local.yml ps

# 实时查看后端日志
docker-compose -f docker-compose.local.yml logs -f backend

# 停止所有后端容器
docker-compose -f docker-compose.local.yml down
```

---



## 🗄️ 数据库直连指引 (可选)

开发期间如需直连数据库查看数据，可使用以下参数（如果是通过 Docker 启动，需确保暴露了相应端口）：

**MongoDB 核心数据库**
* **Host:** `127.0.0.1`
* **Port:** `27017`
* **认证库 (Database):** `admin`
*(业务数据均存储在 `ARLV2` 数据库中)*

**RabbitMQ 消息队列**
* **Host:** `127.0.0.1`
* **Port:** `5672`
* **认证:** `admin` / `admin`

---

## ⚠️ 声明与免责

本工具仅面向合法授权的企业安全建设、SRC 漏洞挖掘以及安全研究学术交流。
使用本工具进行资产扫描与漏洞探测时，请务必遵守当地法律法规（如《中华人民共和国网络安全法》）及目标平台的测试范围规定。未经授权对目标进行探测属非法行为。使用者因使用本工具造成的任何直接或间接的法律责任与后果，由使用者自行承担，项目作者及贡献者不负任何连带责任。

---

## 🌟 Star History

<div align="center">

<a href="https://github.com/owl234/arl-next/stargazers">
  <img src="https://img.shields.io/github/stars/owl234/arl-next?style=for-the-badge&logo=github&logoColor=white&label=Stars&color=FFD700&labelColor=1a1a2e" alt="GitHub Stars">
</a>

<br/>

[![Star History Chart](https://api.star-history.com/svg?repos=owl234/arl-next&type=Date)](https://star-history.com/#owl234/arl-next&Date)

</div>
