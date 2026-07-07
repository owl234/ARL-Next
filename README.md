<div align="center">

  # ARL-Next
  **自动化资产侦察与漏洞监控平台**

  <p>
    <a href="https://hub.docker.com/"><img src="https://img.shields.io/badge/docker-ready-blue.svg?style=flat-square&logo=docker" alt="Docker"></a>
    <img src="https://img.shields.io/badge/python-3.8%2B-blue?style=flat-square&logo=python" alt="Python">
    <img src="https://img.shields.io/badge/vue-3.x-4fc08d?style=flat-square&logo=vuedotjs" alt="Vue">
  </p>
</div>

<br/>

---

## 💡 什么是 ARL-Next？

**ARL-Next** 是 ARL (资产侦察灯塔) 的现代化重构版本，旨在为安全团队提供**极简、高效的自动化资产发现与漏洞监控方案**。

针对传统安全工具环境配置繁琐、代码高度耦合、二次开发困难等历史包袱，ARL-Next 进行了彻底的底层重构，其核心亮点在于：

* **底层引擎全面换代**：淘汰已停更的老旧组件（如 PhantomJS），平滑迁移至 Chrome for Testing + Puppeteer，并全面升级至最新的 Nuclei 漏洞引擎。
* **一站式业务闭环**：打通从“**企业边界查询 (ICP/TYC) ➔ 资产拓扑发现 ➔ 指纹识别 ➔ 自动化漏洞打点**”的全链路。
* **极简部署与 AI 友好二开**：后端与中间件全栈容器化，前端彻底解耦（Vue 3）。告别环境依赖地狱，实现极低门槛的二次开发，非常适合由 AI 辅助进行功能魔改。

---

## 📸 界面预览

* **全局仪表盘**：直观呈现资产分布、任务状态与实时日志，全局安全态势一目了然。
  <br><img src="./img/dashboard.png" alt="仪表盘" width="800"><br>

* **企业资产查询**：内置 ICP 备案与天眼查查询，快速摸清企业资产边界（网站/APP/公众号等），支持一键下发自动化扫描任务。
  <br><img src="./img/enterprise-asset-search.png" alt="ICP备案查询" width="800"><br>

* **任务管理**：精细化的任务调度与状态追踪，支持多维度过滤；新增优化的插件分类与资产分组视图，交互更直观。
<br><img src="./img/task-new.png" alt="任务新建" width="800"><br>
  <br><img src="./img/task-management1.png" alt="任务管理" width="800"><br>

* **系统设置**：支持 Web 端热更新扫描字典、灵活调整任务并发，以及配置多渠道（钉钉/飞书/企微/邮件/Webhook）告警推送，并提供一键连通性测试。
  <br><img src="./img/system-settings.png" alt="系统设置" width="800"><br>

---

## 🏗️ 架构设计

ARL-Next 采用清晰的微服务架构设计，各模块职责明确：

1. **展示层 (Frontend)**：基于 Vue 3 + Vite 构建，负责用户交互与数据可视化。
2. **业务 API 层 (Backend)**：基于 Flask，负责接收前端指令、鉴权，并调度底层任务（包含已规范化整合至此的 ICP_Query 等独立模块）。
3. **消息中间件 (Broker)**：采用 **RabbitMQ**，负责高效可靠地分发并解耦庞大的异步扫描任务。
4. **异步执行层 (Workers)**：Celery 分布式集群（含普通 Worker、GitHub 监控、定时调度器），专门执行耗时的漏洞扫描和资产收集。
5. **持久化存储 (Database)**：使用 **MongoDB**，承载海量扫描结果与大宽表资产数据的落地。

---

## 🚀 部署指南

### 开发环境部署方案：前端本地 + Docker 后端源码

**适用对象**：二次开发者、安全研究人员。
**方案优势**：后端全套服务（API / Worker / ICP 服务 / 数据库 / MQ）运行在 Docker 容器中，且**通过代码卷挂载实现修改即时生效**。前端在本地 Vite 环境独立运行并代理请求，彻底解耦，体验丝滑。

> **前置条件**：已安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/) 和 [Node.js](https://nodejs.org/)（附带 npm），并全局安装 pnpm：`npm install -g pnpm`

---

#### 第一步：克隆仓库并进入目录
```bash
git clone https://github.com/owl234/ARL-Next
cd ARL-Next
```

#### 第二步：运行一键开发环境启动脚本
在项目根目录下直接运行一键开发脚本（脚本会自动在后台构建并拉起后端 Docker 容器组，自动在本地检测并安装前端依赖，随后在终端前台启动 Vite 开发服务器）：
```bash
bash start-dev.sh
```
运行后，稍作等待，终端将直接显示前端 Vite 开发服务的访问地址（默认 `http://localhost:5173`），打开浏览器即可登录并进行二次开发。

> **说明**：
> 1. **代码热更新**：后端 Docker 挂载了本地项目目录，前端由 Vite 进行热重载，修改任意前后端代码均会即时生效。
> 2. **默认管理员账号**：容器启动时会自动重置并注入默认管理员账号，账号密码为：`admin` / `arlpass`。
> 3. **API 代理映射**：后端 API 服务映射在宿主机的 `5001` 端口上。前端 `vite.config.js` 已内置对宿主机 `127.0.0.1:5001` 的代理映射，开箱即用，无需手动修改任何参数。
> 4. **HTTPS 证书（可选）**：如需开启 HTTPS 以防范浏览器安全限制，可使用 `mkcert localhost` 生成本地证书并将 `localhost.pem` 与 `localhost-key.pem` 放置于项目根目录 `certs/` 下，开发服务器将自动读取并升级为 `https://localhost:5173` 运行。

---

#### 常用开发管理命令

```bash
# 查看所有容器状态
docker compose -f docker-compose.dev.yml ps

# 实时查看后端主服务（API、Worker）的混合日志（基于服务名）
docker compose -f docker-compose.dev.yml logs -f web worker

# 停止开发环境（不丢失数据）
docker compose -f docker-compose.dev.yml down
```

---

### 生产环境部署方案：公网极简 HTTPS 部署

**适用对象**：生产环境公网部署、轻量化单机部署。
**方案优势**：
1. **极低摩擦**：直接利用前端容器内 **Vite 服务原生提供公网 HTTPS 安全服务**。
2. **极小外部暴露面**：公网**仅对外开放前端的 5173 端口**。其余所有核心组件（API 后端、数据库 MongoDB、队列 RabbitMQ 等）的外网端口暴露全部关闭，彻底在公网隐形，极大降低了被攻击和被指纹扫描的风险。
3. **极低内部损耗**：容器间通信全部处于 Docker 隔离的 `arl-net` 网桥内。配合关闭 Docker 的 `userland-proxy` 代理，内部通信完全由 Linux 内核态进行转发，网络性能接近原生网卡。

#### 第一步：克隆仓库并进入目录
在您的公网生产服务器上执行以下命令拉取项目代码：
```bash
git clone https://github.com/owl234/ARL-Next
cd ARL-Next
```

#### 第二步：准备证书文件
在项目根目录下创建一个 `ssl-certs` 文件夹（命名与 compose 配置保持一致），将您的公网 SSL 证书与私钥命名并放入其中：
*   `./ssl-certs/arl.crt`
*   `./ssl-certs/arl.key`

> [!TIP]
> **如何快速获取免费的公网 SSL 证书？**
> 如果您没有现成证书，可使用 Linux 官方推荐的免费工具 **Certbot** (Let's Encrypt) 快速申请（需确保您的域名已解析到此服务器且 80 端口暂未被占用）：
> ```bash
> # 1. 安装 certbot 工具
> sudo apt update && sudo apt install -y certbot
> # 2. 自动生成免费公网证书 (请将 arl.yourdomain.com 换成您的域名)
> sudo certbot certonly --standalone -d arl.yourdomain.com
> # 3. 拷贝生成的证书与私钥到项目目录下并重命名
> cp /etc/letsencrypt/live/arl.yourdomain.com/fullchain.pem ./ssl-certs/arl.crt
> cp /etc/letsencrypt/live/arl.yourdomain.com/privkey.pem ./ssl-certs/arl.key
> ```

#### 第三步：运行一键部署与自动调优脚本
在项目根目录下，直接执行以下命令拉起整套环境（脚本会自动在宿主机进行**多系统环境依赖自检与自适应预装**，配置 Docker 性能调优，并一键构建拉起生产容器）：
```bash
# 使用 sudo 运行以自动完成依赖预装与系统级性能调优
sudo bash start-prod.sh
```

> [!NOTE]
> **新版一键部署脚本已集成自动环境补全与多系统容错：**
> 1. **依赖自动补全**：脚本在执行时会自动识别系统发行版（如 Ubuntu、Debian、CentOS 等），如果宿主机未安装 `python3`、`docker` 或 `docker-compose-plugin`，脚本将自动调用系统包管理器（`apt`/`yum`/`dnf`）或官方脚本完成一键预装。
> 2. **Docker Compose 下载兜底**：如果遇到系统包管理器缺失，脚本会自动从官方 GitHub 源下载对应架构的最优 Compose 二进制包安装，确保部署不中断。
> 3. **服务重启与非 systemd 环境容错**：脚本在对宿主机 Docker 的守护进程进行性能调优（配置 `userland-proxy: false`）后，会自动兼容 `systemctl` 与 `service` 两种服务重启方式。若宿主机处于不支持 systemd 的隔离容器环境，会通过警告引导手动重启，而不会报错中断退出。

> [!TIP]
> **HTTPS 与 API 代理配置：**
> 生产环境默认启用了 HTTPS，并通过 Docker 内部网络将 API 转发给后端服务。若有特殊需求，您可以在 [docker-compose.prod.yml](./docker-compose.prod.yml) 的 `arl-frontend` 服务下微调以下环境变量：
> *   `VITE_HTTPS` (默认 `true`)：控制是否启用 HTTPS。
> *   `VITE_API_TARGET` (默认 `http://arl-web:5000`)：配置前端反向代理指向的后端容器地址及端口。

启动后直接通过浏览器访问 `https://your-server-ip:5173` 即可登录并使用系统。

#### 常用生产管理命令
```bash
# 查看生产环境所有容器状态
docker compose -f docker-compose.prod.yml ps

# 实时查看生产环境 Web 和 Worker 容器的运行日志（基于服务名）
docker compose -f docker-compose.prod.yml logs -f arl-web arl-worker

# 停止生产环境容器（数据会持久化在 volume 中，不会丢失）
docker compose -f docker-compose.prod.yml down
```

---

## 🗄️ 数据库直连指引 (可选)

开发期间如需直连数据库查看数据，可使用以下参数（如果是通过 Docker 启动，需确保暴露了相应端口）：

**MongoDB 核心数据库**
* **Host:** `127.0.0.1`
* **Port:** `27018`
* **认证库 (Database):** `admin`
*(业务数据均存储在 `arl` 数据库中)*

**RabbitMQ 消息队列**
* **Host:** `127.0.0.1`
* **Port:** `5673`
* **认证:** `admin` / `admin`

---

## 📅 未来计划 (Roadmap)

* [ ] **撰写完整使用手册**：提供详细的从部署到实战的操作指南。

---

## 🤝 致谢

* **ARL-Next** 核心引擎是基于开源项目 [ARL (Asset Reconnaissance Lighthouse) 资产侦察灯塔](https://github.com/TophantTechnology/ARL) 进行现代化重构的增强版本。
* 本项目集成的 **企业资产查询 (ICP 等)** 模块，其核心逻辑基于优秀的开源项目 [ICP_Query](https://github.com/HG-ha/ICP_Query) 进行二次开发。
* 在二次开发和重构的过程中，本项目也参考并借鉴了以下优秀的 ARL 衍生开源项目：
  * [Aabyss-Team/ARL](https://github.com/Aabyss-Team/ARL)
  * [adysec/ARL](https://github.com/adysec/ARL)

我们对原 ARL 团队及 ICP_Query 作者为开源安全社区做出的巨大贡献表示最诚挚的感谢！ARL-Next 也将秉持开源互助的初心，持续为信息安全社区贡献力量。

---

## ⚠️ 声明与免责

本工具仅面向合法授权的企业安全建设、SRC 漏洞挖掘以及安全研究学术交流。
使用本工具进行资产扫描与漏洞探测时，请务必遵守当地法律法规（如《中华人民共和国网络安全法》）及目标平台的测试范围规定。未经授权对目标进行探测属非法行为。使用者因使用本工具造成的任何直接或间接的法律责任与后果，由使用者自行承担，项目作者及贡献者不负任何连带责任。

---

## 💬 问题反馈与交流

在使用过程中如遇到 Bug、有新的功能建议，或是想探讨安全开发与红蓝对抗技术，欢迎通过 GitHub Issues 提交反馈。

同时也欢迎通过以下方式与我联系交流：

<table align="center">
  <tr>
    <td align="center" style="padding: 0 60px;"><b>个人微信</b></td>
    <td align="center" style="padding: 0 60px;"><b>QQ交流群</b></td>
  </tr>
  <tr>
    <td align="center" style="padding: 0 60px;"><img src="./img/wechat.png" alt="个人微信" height="525" /></td>
    <td align="center" style="padding: 0 60px;"><img src="./img/qq_group.jpg" alt="QQ交流群" height="525" /></td>
  </tr>
</table>


---

## 🌟 Star History

**⭐ 如果本项目为你的安全工作带来了便利，不妨点个 Star 支持一下！**

<div align="center">

<a href="https://www.star-history.com/?repos=owl234%2Farl-next&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=owl234/arl-next&type=date&theme=dark&legend=top-left&sealed_token=vNF3XBBUYjnOkZ1XfTODaJEURB73qlNr1zXyCH6HOUbJGKju3QmIb7pVDyjCK67Ra-ukzG7dgZ3B3HDpCKJ3raveN9bOCec7r6gDILhjGrYbcVEV2Gy5Ew" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=owl234/arl-next&type=date&legend=top-left&sealed_token=vNF3XBBUYjnOkZ1XfTODaJEURB73qlNr1zXyCH6HOUbJGKju3QmIb7pVDyjCK67Ra-ukzG7dgZ3B3HDpCKJ3raveN9bOCec7r6gDILhjGrYbcVEV2Gy5Ew" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=owl234/arl-next&type=date&legend=top-left&sealed_token=vNF3XBBUYjnOkZ1XfTODaJEURB73qlNr1zXyCH6HOUbJGKju3QmIb7pVDyjCK67Ra-ukzG7dgZ3B3HDpCKJ3raveN9bOCec7r6gDILhjGrYbcVEV2Gy5Ew" />
 </picture>
</a>

</div>


