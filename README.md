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

**ARL-Next** 是 ARL (资产侦察灯塔) 的现代化重构版本，提供**极简、高效的自动化资产发现与漏洞监控方案**。其核心亮点包括：

* **引擎代际更替**：淘汰 PhantomJS，平滑升级为 Chromium + Puppeteer 动态爬虫与最新的 Nuclei 漏洞扫描引擎。
* **多维资产闭环**：打通“边界 ➔ 拓扑 ➔ 指纹 ➔ 漏洞”闭环，集成 ICP 与天眼查，支持拉取企业旗下 APP、小程序、公众号及微博等多元资产。
* **部署与极速二开**：生产脚本支持环境自检与内核网络调优；开发环境支持代码卷挂载与 Vite 极速热更新，天然适配 AI 辅助开发。

---

## 📸 界面预览

* **全局仪表盘**：实时展示系统资源消耗、任务执行队列、多维资产统计与后台运行日志流。
  <br><img src="./img/dashboard.png" alt="仪表盘" width="800"><br>

* **企业资产查询**：支持 ICP 备案与天眼查关联检索，一键同步资产（网站/小程序/APP/公众号/微博）下发扫描任务。
  <br><img src="./img/enterprise-asset-search.png" alt="ICP备案查询" width="800"><br>

* **任务管理**：支持扫描任务全生命周期追踪、POC 插件按需自由组合与多维资产拓扑过滤。
  <br><img src="./img/task-new.png" alt="任务新建" width="800"><br>
  <br><img src="./img/task-management1.png" alt="任务管理" width="800"><br>

* **系统设置**：集成 Fofa/天眼查 API 热配置、字典云端热更新、扫描并发调度微调，以及五大告警通道（钉钉/飞书/企微/邮件/Webhook）一键测试。
  <br><img src="./img/system-settings.png" alt="系统设置" width="800"><br>

---

## 🏗️ 架构设计

ARL-Next 采用前后端解耦的微服务架构，核心模块及版本如下：

1. **展示层 (Frontend)**：基于 **Vue 3.5** + **Vite 5.4** + **Ant Design Vue 4.2** 构建，生产环境由 **Nginx (Alpine)** 托管并提供 HTTPS 安全网关。
2. **业务 API 层 (Backend)**：基于 **Python 3.8+** 与 **Flask 2.0**，处理 JWT 权限鉴定、网关分发与本地化备案查询微服务。
3. **消息队列 (Broker)**：采用 **RabbitMQ 3.x**，实现 API 服务与异步高并发扫描任务之间的解耦分发。
4. **任务执行层 (Workers)**：基于 **Celery 5.2** 的分布式集群（含普通任务 Worker 与 Celery Beat 定时调度），负责运行 **Nuclei 3.3** 与子域名爆破等底层任务。
5. **数据存储 (Database)**：使用 **MongoDB 4.0**，承载千万级大宽表资产数据与漏洞结果落地。

---

## 🚀 部署指南

### 开发环境部署：前端本地 + Docker 后端源码

**适用**：二次开发人员、安全研究者。  
**优势**：后端服务全栈容器化，通过代码卷（`./:/code`）实现源码即时热更；前端本地独立运行并反代请求，解耦彻底。

> **前置条件**：安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/)、[Node.js](https://nodejs.org/)，并配置 pnpm: `npm install -g pnpm`

---

#### 🚀 启动步骤

```bash
# 1. 克隆并进入项目目录
git clone https://github.com/owl234/ARL-Next && cd ARL-Next

# 2. 运行一键开发脚本（自动拉起后端容器、安装前端依赖并启动 Vite）
bash start-dev.sh
```
启动后，浏览器访问 `http://localhost:5173` 即可开始开发。

> 💡 **核心开发细节**：
> * **双端热更新**：后端 Docker 挂载本地代码即时生效，前端由 Vite 极速热重载。
> * **默认凭据**：系统管理员账号密码为：`admin` / `arlpass`。
> * **API 代理**：后端接口暴露于宿主机 `5001` 端口，前端代理已预设反代至此端口。
> * **本地 HTTPS**：若有安全限制，可将 `mkcert` 生成的 `localhost.pem` 与 `localhost-key.pem` 放入根目录 `certs/` 下，服务将自动以 `https://localhost:5173` 启动。

---

#### 🛠️ 常用开发命令

```bash
# 查看开发容器状态
docker compose -f docker-compose.dev.yml ps

# 实时查看 API 与 Worker 容器日志
docker compose -f docker-compose.dev.yml logs -f arl-web arl-worker

# 停止开发环境（保留数据卷）
docker compose -f docker-compose.dev.yml down
```

---

### 生产环境部署方案：极简 HTTPS 部署

**适用**：本地开发测试、单机极简运行。  
**优势**：
1. **一键免交互拉起**：部署脚本 [start-prod.sh](./start-prod.sh) 会自动检测并一键免交互生成 10 年期的本地自签名 SSL 证书，无需任何手动输入或外部申请。
2. **强安全边界**：公网仅暴露前端 **5173 端口**。API 后端、MongoDB、RabbitMQ 等敏感服务端口全部对外关闭，实现网络隐形。
3. **零配置 SSL**：前端 Nginx 容器直接挂载自动生成的自签名证书，原生提供高并发的 HTTPS/SSL 安全防护。

#### 🚀 部署步骤

```bash
# 1. 克隆项目
git clone https://github.com/owl234/ARL-Next && cd ARL-Next

# 2. 运行一键部署脚本（自动生成 10 年期自签名 SSL 证书并拉起容器）
sudo bash start-prod.sh
```
部署完成后，通过浏览器访问 `https://your-server-ip:5173` 即可登录使用。

> 🛡️ **自签名证书警告提示**
> 
> 首次通过浏览器访问时会遇到“证书不受信任”的红色警告。这并非安全漏洞（数据传输依然是强加密的），只需在浏览器中点击 **“高级” (Advanced) -> “继续访问/忽略警告” (Continue)** 即可正常进入系统。

> ⚙️ **证书与反代微调**：
> 默认自动完成证书生成与反向代理。若您有自备的公网受信任 SSL 证书，只需将证书与私钥命名为 `arl.crt` 和 `arl.key` 放入 `./ssl-certs/` 目录下即可，脚本会自动识别并挂载。如有特殊路由需求，请直接编辑 Nginx 配置文件 [frontend/default.conf.prod](./frontend/default.conf.prod)，修改后执行 `sudo bash start-prod.sh` 重新构建。

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
* **认证库 (authSource):** `admin` （存储账号凭据的安全验证库）
* **认证账号/密码:** `admin` / `admin`
* **业务数据存储库:** `arl` （直连后实际操作该库获取资产数据）
* **直连 URI**: `mongodb://admin:admin@127.0.0.1:27018/arl?authSource=admin`

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
* **威零安全团队** (<img src="img/weiling.jpg" width="18" height="18" align="absmiddle" /> 微信公众号)：提供了 16,985 条指纹数据，极大丰富了本项目的资产指纹识别维度。
* 在二次开发和重构的过程中，本项目也参考并借鉴了以下优秀的 ARL 衍生开源项目：
  * [Aabyss-Team/ARL](https://github.com/Aabyss-Team/ARL)
  * [adysec/ARL](https://github.com/adysec/ARL)

我们对上述开源项目作者、安全团队及社区贡献者表示最诚挚的感谢！ARL-Next 也将秉持开源互助的初心，持续为信息安全社区贡献力量。

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


