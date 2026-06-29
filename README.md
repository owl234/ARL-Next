<div align="center">


  # ARL-PRO
  **企业级自动化资产侦察与漏洞监控“灯塔”**

  <p>
    <a href="https://github.com/owl234/arl-pro/actions"><img src="https://img.shields.io/github/actions/workflow/status/owl234/arl-pro/ci.yml?style=flat-square&logo=github&label=Build" alt="build"></a>
    <a href="https://hub.docker.com/"><img src="https://img.shields.io/badge/docker-ready-blue.svg?style=flat-square&logo=docker" alt="Docker"></a>
    <a href="https://github.com/owl234/arl-pro/releases"><img src="https://img.shields.io/github/v/release/owl234/arl-pro?style=flat-square&color=success" alt="Release"></a>
    <img src="https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square&logo=python" alt="Python">
    <img src="https://img.shields.io/badge/vue-3.x-4fc08d?style=flat-square&logo=vuedotjs" alt="Vue">
  </p>

  [**English**](./README_EN.md) | [**更新日志**](./CHANGELOG.md) | [**在线文档**](https://your-doc-link.com)
</div>

<br/>

---

## 💡 什么是 ARL-PRO？

ARL-PRO 旨在为安全团队、红蓝对抗工程师及 Bug Bounty 猎人提供一套**开箱即用**的资产全周期监控与漏洞发现平台。

彻底告别繁杂的脚本拼接，ARL-PRO 将资产发现、端口扫描、指纹识别到漏洞探测融为一体，并通过现代化的 Vue 控制台为您呈现全局安全态势。

## 🤝 致谢与声明 (Acknowledgments)

**ARL-PRO** 是基于优秀的开源项目 [ARL (Asset Reconnaissance Lighthouse) 资产侦察灯塔](https://github.com/TophantTechnology/ARL) 进行深度重构与二次开发的企业级增强版本。

我们对原 ARL 开发团队为信息安全开源社区做出的巨大贡献表示最诚挚的感谢！原项目奠定了自动化资产收集与漏洞扫描的坚实基础。本着开源互助的精神，ARL-PRO 将继续遵循开源精神，并将持续为其注入新的活力。

### 🌟 为什么要重构 ARL-PRO？(与原版的区别)

随着网络环境的演变和安全人员需求的升级，我们对原项目进行了现代化改造，以解决原版在当今复杂环境下的部分痛点：

* **现代化前端栈**：彻底重构前端，基于 Vue 3 + 现代 UI 框架构建，提供更流畅的交互体验和更直观的数据大屏。
* **部署与运维架构解耦**：引入全面的 Docker 化与 CI/CD 自动化构建流程，支持 Cloudflare Tunnel 零端口暴露部署，数据持久化（Volumes）更加安全可靠。
---

## ✨ 核心特性 (Features)

* **🛡️ 零信任架构与全链路 HTTPS (New)**
  彻底解决浏览器安全限制与公网暴露风险。本地开发采用 `mkcert` 无缝实现 HTTPS 热重载；生产环境引入 Cloudflare Tunnel 内网穿透，服务器实现**“零入站端口”**暴露，完美隐身于公网扫描器与 DDoS 攻击之外，并享受免维护的长效边缘证书。
* **🔥 现代化前后端分离架构**
  彻底告别臃肿。前端基于 Vue 3 + Vite 构建现代化 SPA 面板，后端依托 Python 3.8+ 与 Flask 提供纯粹的 RESTful API。这带来了毫秒级的交互体验和极佳的二次开发扩展性。
* **⚡ 全自动 CI/CD 敏捷交付**
  时间应该花在挖掘逻辑上，而不是运维上。本项目已完全打通 GitHub Actions 自动化流水线。代码一经 Push，系统自动在云端构建不可变的纯净 Docker 镜像，并跨网络全自动部署到你的生产节点，实现基础设施的“丝滑热更”。
* **🌍 生产级分布式调度与高并发**
  以 RabbitMQ 为消息中枢，Celery 分布式工作节点为执行引擎。你可以轻松将核心扫描 Worker 和专门的 GitHub 敏感信息监控 Worker 分散部署，实现真正的高并发多节点协同扫描。
* **📸 现代 Web 无头渲染引擎 (New)**
  彻底重构了底层截图与指纹探测引擎，抛弃陈旧的 PhantomJS，全面拥抱原生 Chromium 与 Puppeteer。完美支持 React、Vue 等现代 SPA（单页面应用）的智能长截图和 Wappalyzer 深度指纹解析，内置中文字库彻底解决乱码问题，让每一次资产快照都如肉眼所见般精准。
* **⚔️ 硬核武器库无缝集成**
  内置庞大且不断更新的 ARL-NPoC 武器库，并无缝对接 FOFA 等第三方资产引擎。结合资产梳理、指纹识别、端口扫描，实现从“发现资产”到“自动打出 Payload”的完整闭环。

---

## 🏗️ 架构设计 (Architecture)

ARL-PRO 采用经典且强健的微服务容器编排设计，并在网关层进行了现代化的零信任改造：

1.  **安全网关与展示层 (Frontend / Gateway)**：
  * **本地**：Vite 本地 HTTPS 服务器 -> Vite 代理转发 -> 后端 HTTP。
  * **生产**：Cloudflare 边缘节点 (SSL 卸载) -> 加密隧道 (Cloudflared) -> 内部 Nginx (HTTP 80) -> 后端 API。
2.  **业务逻辑层 (Backend)**：Gunicorn 驱动的 Flask 应用，负责接收前端指令、操作 MongoDB 数据库，并将重量级扫描任务分发至消息队列。
3.  **消息总线 (Broker)**：RabbitMQ 承担任务排队与状态分发的高吞吐工作。
4.  **异步执行层 (Workers)**：核心节点 (worker)、GitHub 监控节点 (worker-github) 与 定时调度器 (scheduler) 精准协同。
5.  **持久化存储 (Database)**：MongoDB 负责海量扫描结果与配置资产的落地存储。

---

## 🔐 配置管理与数据安全 (Configuration & Data Security)

本项目在生产环境严格遵循 DevSecOps 标准，杜绝任何密钥硬编码泄露风险：

### 1. 防泄漏配置隔离机制
* **代码库原则**：Git 仓库中仅保留 `backend/config-docker.example.yaml` 模板文件，不包含任何真实密码或 Token。
* **本地生效原则**：真正控制生产环境的 `.env`（存储随机生成的数据库密码）和 `config-docker.yaml`（存储第三方 API 密钥）已经被 `.gitignore` 保护。CI/CD 拉取最新代码时**绝对不会**覆盖或抹除您在服务器上配置的凭据。

### 2. 业务数据 0 丢失 (Volumes 持久化)
每次 CI/CD 自动部署本质上是销毁旧容器并使用新镜像启动新容器。我们通过 Docker Named Volumes 实现了数据的完全解耦：
* `arl_db_test`：持久化存储 MongoDB 中的所有扫描资产与漏洞数据。
* `arl_tmp_test`：存储报表等临时文件。
* `arl_screenshot_test`：存储系统自动截取的资产快照。
* `arl_upload_poc_test`：存储用户自定义上传的 PoC 文件。
  **结论：只要不手动执行 `docker volume rm`，任何高频的代码自动更新都不会导致您的业务数据丢失。**

---

## 🏗️ 环境隔离架构设计 (Architecture: Local vs Prod)

为了兼顾“极致的开发效率”与“铁桶般的生产安全”，项目做了严格的环境分离：

| 特性 | 本地开发环境 (`docker-compose.local.yml`) | 生产/CI 环境 (`docker-compose.test.yml`) |
| :--- | :--- | :--- |
| **代码运行方式** | **挂载覆写 (Bind Mounts)**: 宿主机的 `./backend` 直接映射入容器。 | **不可变基础设施 (Immutable)**: 容器 100% 运行从 GHCR 拉取的纯净只读镜像。 |
| **热重载 (Hot Reload)** | ✅ 支持。保存代码瞬间生效，方便联调。 | ❌ 不支持。彻底杜绝“线上直接改代码”造成的幽灵 Bug。 |
| **镜像构建** | 每次启动需在本地 `build`。 | 由 GitHub Actions 统一构建，节点仅需 `pull`。 |
| **外部流量接入** | `localhost` 直连测试。 | Cloudflare Tunnel 加密隧道，服务器真正实现“零入站端口”。 |

---

## 🚀 极速部署 (Quick Start)

我们为开发者提供了两套编排方案，以平衡“开发效率”与“生产稳定”。

### 方案 A：本地极速迭代调试流 

适用于二次开发、编写 PoC 与前后端联调。采用热重载机制，代码修改浏览器/接口即刻生效。

### Windows 版

**1.克隆代码**
```bash
git clone https://github.com/owl234/arl-pro
cd arl-pro
```

**2. 准备本地受信任证书 (必须)**
为了让本地联调拥有合法的 HTTPS 绿锁并解决跨域问题，需先生成本地证书：
```powershell
# 1. 在项目根目录下载 mkcert (Windows 为例)
Invoke-WebRequest -Uri "https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-windows-amd64.exe" -OutFile "mkcert.exe"

# 2. 将根证书安装到系统信任库 (如遇弹窗请点击"是")
.\mkcert.exe -install

# 3. 创建目录并签发 localhost 证书，完成后将文件重命名为 localhost.pem 和 localhost-key.pem
mkdir certs
cd certs
..\mkcert.exe localhost 127.0.0.1
```
*(注意：`certs/` 目录已加入 `.gitignore` 防止私钥泄露)*

**3. 启动本地环境**
```bash
# 启动后端底座（挂载本地源码，暴露 5003 端口供 Vite 代理）
docker-compose -f docker-compose.local.yml build backend
docker-compose -f docker-compose.local.yml up -d backend worker worker-github scheduler mongodb rabbitmq

# 另起终端启动前端（原生支持 https://localhost:3000）
cd frontend
npm install -g pnpm
pnpm install
pnpm run dev
```

### Mac版

**1.克隆代码**
```bash
git clone https://github.com/owl234/arl-pro
cd arl-pro
```

**2. 准备本地受信任证书 (必须)**
为了让本地联调拥有合法的 HTTPS 绿锁并解决跨域问题，需先生成本地证书。在 macOS 上，推荐使用 Homebrew 来安装`mkcert`：
```bash
# 1. 使用 Homebrew 安装 mkcert（如果你的 Mac 还没安装 Homebrew，需先安装）
brew install mkcert

# (可选) 如果你使用 Firefox 浏览器进行调试，建议额外执行 brew install nss

# 2. 将根证书安装到系统信任库 (可能需要输入你的 Mac 开机密码或验证 Touch ID)
mkcert -install

# 3. 创建目录并签发 localhost 证书，这里直接指定输出符合项目要求的文件名
mkdir certs
cd certs
mkcert -cert-file localhost.pem -key-file localhost-key.pem localhost 127.0.0.1
```
*(注意：`certs/` 目录已加入 `.gitignore` 防止私钥泄露)*

**3. 启动本地环境**

**启动后端底座**（挂载本地源码，暴露 5003 端口供 Vite 代理）：
请确保你的 Mac 已经启动了 Docker Desktop。
```bash
# 退回项目根目录 (如果你刚刚在 certs 目录下)
cd ..

# 构建并启动后端与核心依赖
docker-compose -f docker-compose.local.yml build backend
docker-compose -f docker-compose.local.yml up -d backend worker worker-github scheduler mongodb rabbitmq
```
**启动前端开发服务器**（原生支持 https://localhost:3000）：
请确保你的 Mac 已经安装了 Node.js 环境。另开启一个新的终端窗口执行：
```bash
cd frontend
npm install -g pnpm
pnpm install
pnpm run dev
```


## 数据库连接(可选)

在数据库客户端(比如 Navicat )中新建MongoDB连接,填入以下环境初始化参数:

- **Host (主机地址):** 127.0.0.1 或 localhost
- **Port (端口):** 27017
- **Authentication (认证信息):**
  - **Database (认证库):** admin (根用户在此库认证)
  - **Username (用户名):** admin
  - **Password (密码):** admin

核心业务数据库: ARLV2 (后端数据在此)

### 方案 B：生产环境全自动 CI/CD 流 (Production & Zero Trust)

适用于部署到 VPS 监控节点的正式环境，实现免开放端口的绝对隐身与全自动发布。

**1. 域名与基础环境准备**
* 将您的主域名托管至 **Cloudflare**，并选择 Free (免费) 计划。
* 在干净的 Ubuntu 生产节点执行初始化脚本配置基础 Docker 环境：
  ```bash
  chmod +x init_ubuntu_env.sh
  ./init_ubuntu_env.sh
  ```
* 在项目仓库 Settings -> Actions -> Runners 中绑定该 Ubuntu 节点。

**2. 建立 Cloudflare Tunnel 隧道**
* 登录 Cloudflare -> **Zero Trust** 面板。
* 展开 **Networks** -> **Tunnels**，点击 **Create a tunnel** (选择 Cloudflared 连接器)。
* 在页面下方获取对应操作系统的 `curl -L ...` 安装命令，并登录您的 Ubuntu 虚拟机执行该命令。
* 待控制台显示 `Connected` 后进入路由配置：
  * **Subdomain**: `arl` (您的系统访问前缀)
  * **Domain**: 选择托管的主域名
  * **Service Type**: 选择 `HTTP` (🚨 必须选 HTTP，云端已完成加解密)
  * **Service URL**: `localhost:80`

**3. 初始化生产安全配置**

在第一次触发 CI/CD 自动部署前，需在服务器上初始化安全环境变量（生成强密码与脱敏配置）：
```bash
git clone https://github.com/owl234/arl-pro
cd arl-pro
chmod +x init_env.sh
./init_env.sh
```
**4. 享受全自动部署**

- 后续只需向 GitHub 的 main 分支 Push 代码。
- CI/CD 管道会自动打包构建最新的前后端 Docker 镜像至 GitHub Packages (GHCR)。
- 部署节点会自动拉取新镜像并平滑重启服务，过程仅需数分钟。
- 访问 https://arl.您的域名.com 即可使用最新版的系统。

**初始账号密码：** `admin / arlpass` （登录后请立即通过 `https://arl.yourdomain.com` 修改）

---

## ⚠️ 声明与免责 (Disclaimer)

本工具（ARL-PRO）仅面向合法授权的企业安全建设、SRC 漏洞挖掘以及安全研究学术交流。

使用本工具进行资产扫描与漏洞探测时，请务必遵守当地法律法规（如《中华人民共和国网络安全法》）及目标平台的测试范围规定。未经授权对目标进行探测属非法行为。使用者因使用本工具造成的任何直接或间接的法律责任与后果，由使用者自行承担，项目作者及贡献者不负任何连带责任。

---

## 🌟 Star 历史 (Star History)

<div align="center">

感谢每一位点亮星星的朋友，你们的支持是我们持续前行的最大动力 ✨

<a href="https://github.com/owl234/arl-pro/stargazers">
  <img src="https://img.shields.io/github/stars/owl234/arl-pro?style=for-the-badge&logo=github&logoColor=white&label=Stars&color=FFD700&labelColor=1a1a2e" alt="GitHub Stars">
</a>
&nbsp;
<a href="https://github.com/owl234/arl-pro/network/members">
  <img src="https://img.shields.io/github/forks/owl234/arl-pro?style=for-the-badge&logo=github&logoColor=white&label=Forks&color=4fc08d&labelColor=1a1a2e" alt="GitHub Forks">
</a>
&nbsp;
<a href="https://github.com/owl234/arl-pro/watchers">
  <img src="https://img.shields.io/github/watchers/owl234/arl-pro?style=for-the-badge&logo=github&logoColor=white&label=Watchers&color=58a6ff&labelColor=1a1a2e" alt="GitHub Watchers">
</a>

<br/><br/>

[![Star History Chart](https://api.star-history.com/svg?repos=owl234/arl-pro&type=Date)](https://star-history.com/#owl234/arl-pro&Date)

</div>
