<div align="center">

  # ARL-Next
  **下一代 AI 原生全域资产测绘与漏洞监控基座**

  *Next-Generation AI-Native Attack Surface Reconnaissance & Asset Intelligence Platform*

  <p><b>企业全域穿透 · 全链路拓扑画像 · AI 原生协同调度 · 极速 2 分钟开箱自愈</b></p>

  <p>
    <a href="https://github.com/owl234/ARL-Next/releases"><img src="https://img.shields.io/github/v/release/owl234/ARL-Next?style=flat-square&color=blue" alt="Release"></a>
    <a href="https://github.com/owl234/ARL-Next/stargazers"><img src="https://img.shields.io/github/stars/owl234/ARL-Next?style=flat-square&color=gold" alt="Stars"></a>
    <a href="https://github.com/owl234/ARL-Next/network/members"><img src="https://img.shields.io/github/forks/owl234/ARL-Next?style=flat-square" alt="Forks"></a>
    <a href="./LICENSE"><img src="https://img.shields.io/badge/License-GPL%20v3-blue?style=flat-square" alt="License"></a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
    <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/Nmap-7.95%20LTS-blue?style=flat-square" alt="Nmap">
    <img src="https://img.shields.io/badge/MongoDB-7.0-47A248?style=flat-square&logo=mongodb&logoColor=white" alt="MongoDB">
    <img src="https://img.shields.io/badge/Vue-3.5-4FC08D?style=flat-square&logo=vuedotjs&logoColor=white" alt="Vue">
    <img src="https://img.shields.io/badge/MCP-Native-purple?style=flat-square" alt="MCP">
  </p>

  <p>
    <a href="#quick-deploy"><b>⚡ 2分钟极速安装</b></a> •
    <a href="#comparison"><b>💡 原版痛点对比</b></a> •
    <a href="#core-features"><b>✨ 核心特性</b></a> •
    <a href="./mcp-server/README.md"><b>🤖 MCP配置指南</b></a> •
    <a href="./CHANGELOG.md"><b>📜 更新日志</b></a> •
    <a href="./LICENSE"><b>📄 开源协议</b></a>
  </p>
</div>

<br/>

---

## 💡 什么是 ARL-Next？

> **ARL-Next** 是经典开源资产侦察灯塔 (ARL) 的现代化涅槃重构版本。
> 针对原版长期停更导致的**任务假死、内存泄露、安装报错、依赖过时**等致命缺陷进行了彻底的底层重构，并深度融入 **AI Agent (MCP) 原生调度**能力，进化为高性能、全维度闭环的下一代安全监控平台。

---

### <span id="comparison"></span>🥊 为什么选择 ARL-Next？(痛点对比)

| 核心痛点维度 | 🏚️ 原版 ARL (社区遗留版) | 🚀 ARL-Next (本项目) |
| :--- | :--- | :--- |
| **系统稳定性** | 扫描海量目标时 Celery 阻塞假死、内存泄漏 OOM | **微服务解耦** (截图/OSINT独立)，全栈解除内存硬限，批量入库彻底根除假死 |
| **AI 原生集成** | 无 AI 接口，仅限人工手动点击 | **原生 MCP 支持**，AI Agent 一句话接管资产挖掘与分析 |
| **企业资产穿透** | 无企业资产查询功能 | **公司股权穿透 + 全维度 ICP 深度下钻**，一键秒级打通集团子公司及**移动端 (APP/小程序/快应用)** 全量资产 (护网友好) |
| **部署与构建** | 依赖过时容易报错，需拉取海量外网包 | **阿里云国内预构建镜像**，多阶段构建，2分钟一键秒启动 |
| **现代化技术栈** | Python 3.6 / Vue2 / MongoDB 3.x / Nmap 7.70 严重脱节 | **Python 3.13 / Vue 3.5 / MongoDB 7.0 / Nmap 7.95 LTS** 现代底层全线跨代 |
| **敏感信息挖掘** | Go WIH 编译依赖沉重，跨平台常编译报错 | **纯 Python WIH 引擎** 零外部二进制依赖，内置三级风险评估与流式解析 |
| **交互与体验** | 页面滚动遮挡表头、分页重置、管理繁琐 | **操作栏/表头悬浮吸附 (Sticky)**、分页持久化、现代化三栏字典 |
| **情报与监控** | 缺少主动情报源、时区错乱导致重复告警 | **GitHub CVE & 泄露雷达**、原子级去重锁、精准时区对齐 |

---

### <span id="core-features"></span>✨ 核心特性矩阵

* 🤖 **AI 原生调度**：内置标准化 MCP 服务，支持自然语言一键下发探测与 13 维资产全景大盘导出。（👉 [MCP 配置指南](./mcp-server/README.md)）
* 🚀 **高并发零假死**：微服务解耦与批量落库，全栈解除内存硬限制，海量资产吞吐平稳无阻。
* 🌐 **企业全域穿透**：覆盖股权穿透与全维度 ICP（网站/APP/小程序/快应用），自动化打通母子公司资产闭环。
* 🔍 **现代测绘引擎**：升级 Nmap 7.95 黄金 LTS 测绘基线；内置纯 Python WIH 敏感信息与凭证流式提取。
* 🛡️ **威胁情报雷达**：全球最新 CVE 漏洞与 GitHub 敏感凭证秒级原子去重监听，主动感知外部风险。
* ⚡ **开箱自愈运维**：2 分钟极速部署，容器级健康探针自动秒级排障，支持管理后台一键平滑热更。
* 🇨🇳 **国内极速拉取**：全线镜像预构建并托管于阿里云国内私库，免梯直连、零依赖拉取报错。

---

## 📸 界面预览

* **全局仪表盘 (Dashboard)**：实时监测宿主机物理内存与 Swap 水位、系统资源负载、扫描任务生命周期、多维风险态势大盘与全景操作日志流。
  
  <p align="center">
    <img src="./img/dashboard.png" alt="ARL-Next 全局仪表盘" width="850">
  </p>

<details open>
<summary><b>🖼️ 点击收起 / 展开更多核心业务界面</b></summary>

<br/>

* **企业级 OSINT 资产侦察**：支持企业 ICP 备案（网站/移动端 APP/微信小程序/快应用）穿透与公司股权穿透，一键关联并同步下发多维探测任务。
  
  <p align="center">
    <img src="./img/enterprise-asset-search.png" alt="企业资产侦察" width="800">
  </p>

* **任务下发与策略调度**：深度联动 Nuclei、100+ 专属漏洞 PoC 插件池及近万级 Web 指纹库 (8800+)，支持全生命周期下发与追踪。
  
  <p align="center">
    <img src="./img/task-new.png" alt="任务新建与策略选择" width="800">
  </p>
  
  <p align="center">
    <img src="./img/task-management1.png" alt="任务全生命周期管理" width="800">
  </p>

* **威胁情报与代码泄露雷达**：实时追踪全球最新 CVE 漏洞，自动化监听 GitHub 敏感代码与凭证泄露。
  
  <p align="center">
    <img src="./img/threat-intel-radar.png" alt="威胁情报雷达" width="800">
  </p>

* **系统设置与现代字典管理**：全新现代三栏式字典管理（支持在线预览/呼吸灯提示）、队列并发热扩缩容及告警通道。
  
  <p align="center">
    <img src="./img/system-settings.png" alt="系统设置与字典管理" width="800">
  </p>

</details>

---

## 🏗️ 架构设计

ARL-Next 采用前后端解耦、异步分布式任务队列与轻量微服务集群架构。整体数据流与模块交互如下：

```mermaid
graph TD
    %% 1. 接入层
    User["👨‍💻 安全分析师 (浏览器)"] -->|"HTTPS / Basic Auth (5173)"| Nginx["🖥️ Frontend (Nginx + Vue 3.5)"]
    Agent["🤖 AI Agent (Claude / Cursor)"] -.->|"MCP 协议 (Stdio)"| MCP["🤖 MCP Server (Python 原生)"]

    %% 2. API 网关层
    Nginx -->|"REST API 反代 (5000)"| Backend["⚙️ Backend API (Gunicorn / Python 3.13)"]
    MCP -->|"API Token 鉴权调用"| Backend

    %% 3. 调度与任务分流 (双轨解耦)
    Backend -->|"1. 异步直调 (16181)"| OSINT["🧩 OSINT 微服务"]
    Backend -->|"2. 生产扫描任务"| MQ(("⚡ RabbitMQ 3 (轻重/GitHub 多队列)"))

    %% 4. Celery Worker 扫描计算集群
    subgraph WorkerCluster ["⚙️ Celery Worker 扫描与调度集群"]
        MQ -->|"轻量队列 arltask_light"| W_Light["⚡ 轻任务 Worker (DNS/端口/指纹)"]
        MQ -->|"重载队列 arltask_heavy"| W_Heavy["🔥 重任务 Worker (Nuclei/PoC/爬虫)"]
        MQ -->|"威胁队列 arlgithub"| W_Git["🛡️ 威胁情报 Worker (CVE/代码泄露)"]
        
        Scheduler["⏰ 监控调度引擎 (Scheduler & Beat)"] -.->|"周期触发"| MQ
        W_Heavy -->|"HTTP 截图渲染 (5005)"| Puppeteer["🧩 Puppeteer 微服务 (无头截图/滚动自愈)"]
    end

    %% 5. 数据统一落库 (从上往下自然汇聚，彻底杜绝线条交叉穿透)
    Backend <-->|"大盘查询 / 状态读写"| DB[("🗄️ MongoDB 7.0 (联合索引大宽表)")]
    OSINT -->|"异步结果直接入库"| DB
    W_Light -->|"safe_insert_asset_many 批量写入"| DB
    W_Heavy -->|"bulk_write 批量写入"| DB
    W_Git -->|"原子 upsert 写入"| DB

    Autoheal["🛡️ Autoheal 守护探针"] -.->|"docker.sock 探活与秒级自愈"| WorkerCluster

    classDef default fill:#fbfbfb,stroke:#e0e0e0,stroke-width:1px;
    classDef core fill:#eef2ff,stroke:#6366f1,stroke-width:2px;
    classDef ai fill:#f5f3ff,stroke:#8b5cf6,stroke-width:2px;
    classDef db fill:#ecfdf5,stroke:#10b981,stroke-width:2px;
    classDef micro fill:#fffbeb,stroke:#f59e0b,stroke-width:1px;
    
    class Nginx,Backend,WorkerCluster,W_Light,W_Heavy,W_Git core;
    class Agent,MCP ai;
    class DB,MQ db;
    class OSINT,Puppeteer,Autoheal,Scheduler micro;
```

### 核心架构要点：

1. 🖥️ **展示与网关 (Frontend / Nginx)**：基于 **Vue 3.5 + Nginx**，支持全站表格/操作栏 **Sticky 悬浮吸附**与 **Basic Auth 前置网关防御**。
2. ⚙️ **业务与 AI 赋能 (Backend / MCP)**：基于 **Python 3.13 + Gunicorn**；内置 **原生 Python MCP** 赋能 AI Agent 调度与 13 维全景大盘导出。
3. 🧩 **OSINT 独立微服务**：专职公司资产与 ICP 异步情报收集，由 Backend 直调协程池，**彻底脱离 Celery 队列杜绝假死**。
4. ⚡ **多队列 Worker 集群**：拆分**轻量/重载/威胁情报**独立队列；重任务严格限制子进程生命周期彻底根除内存泄露；**底座升级 Nmap 7.95 黄金 LTS 稳定版**。
5. 🛡️ **微服务与自愈守护 (Puppeteer / Autoheal)**：独立容器专职无头截图并支持滚动自愈；**Autoheal 实时探针秒级恢复容器死锁**；纯 Python WIH 引擎高效解析敏感凭据。
6. 🗄️ **高吞吐持久层与性能释放 (MongoDB 7.0)**：全线升级 `bulk_write` 批量落库，核心表覆盖联合唯一索引并设 1GB 内存池保护；**全栈解除 Docker 容器内存硬限制 (`mem_limit`)**，充分释放机器硬件算力。

---

## <span id="quick-deploy"></span>🚀 部署指南

### 生产部署 (单 VPS 一键秒级上线) ⭐ 推荐

**适用环境**：公网云服务器 (Ubuntu / Debian / CentOS / 统信等)、企业内网服务器。  
**预估耗时**：自带 Docker 环境仅需 **1~2 分钟**；全新裸机从零安装约 **3~5 分钟**。

**核心优势**：
* ⚡ **国内极限满速**：直连阿里云北京 ACR 镜像私库，彻底告别海外网络阻断。
* 📦 **开箱即用极简**：免复杂环境配置、免 `docker login`，剔除冗余编译链。
* 🛡️ **双层安全防护**：内置 SSL 证书与 **Basic Auth 前置网关防御**，核心组件全私有网络隔离。
* 🔄 **Web 平滑热更**：支持直接在管理后台一键无感热升级，免去繁琐的 SSH 终端操作。
* 🩺 **全自动健康探活**：内置 API 就绪轮询机制与 Swap 内存自愈，服务就绪再放行，告别 502 报错。

---

#### 🚀 部署方式选择

##### 方法一：国内极速一键部署（⭐ 推荐 · 绕过 GitHub 阻断）

在服务器终端 (需 root 权限) 粘贴并执行对应系统的连缀指令。脚本将从阿里云国内镜像提取全套部署编排，并自动配置 Swap、安装/补齐 Docker 与 Compose 插件后一键拉起：

> [!TIP]
> `start-prod.sh` 内置全套环境探针，支持自动安装 Docker、补齐 Docker Compose 插件并调优内核，裸机亦可顺畅运行。

**Ubuntu / Debian / 统信 系统**：
```bash
# 1. 安装基础工具并创建目录
apt-get update && apt-get install -y docker.io openssl curl && \
mkdir -p ~/ARL-Next && cd ~/ARL-Next && \
# 2. 从阿里云国内镜像提取全套部署编排并启动
docker pull crpi-laul1izptqrf0tkf.cn-beijing.personal.cr.aliyuncs.com/owl234-arl-prod/arl-web:latest && \
docker rm -f arl-temp 2>/dev/null || true && \
docker create --name arl-temp crpi-laul1izptqrf0tkf.cn-beijing.personal.cr.aliyuncs.com/owl234-arl-prod/arl-web:latest && \
docker cp arl-temp:/code/start-prod.sh ./ && \
docker cp arl-temp:/code/docker-compose.prod.yml ./ && \
docker cp arl-temp:/code/updater ./ && \
docker cp arl-temp:/code/version.txt ./ && \
docker cp arl-temp:/code/CHANGELOG.md ./ && \
docker cp arl-temp:/code/frontend ./ && \
docker rm -f arl-temp && \
chmod +x start-prod.sh && bash start-prod.sh
```

**CentOS / RHEL / Alibaba Cloud Linux / TencentOS 系统**：
```bash
# 1. 安装基础工具、自动补齐 Docker 并创建目录
(command -v docker &>/dev/null || curl -fsSL https://get.docker.com | bash -s docker --mirror Aliyun) && \
systemctl enable --now docker 2>/dev/null || true && \
yum install -y openssl curl && \
mkdir -p ~/ARL-Next && cd ~/ARL-Next && \
# 2. 从阿里云国内镜像提取全套部署编排并启动
docker pull crpi-laul1izptqrf0tkf.cn-beijing.personal.cr.aliyuncs.com/owl234-arl-prod/arl-web:latest && \
docker rm -f arl-temp 2>/dev/null || true && \
docker create --name arl-temp crpi-laul1izptqrf0tkf.cn-beijing.personal.cr.aliyuncs.com/owl234-arl-prod/arl-web:latest && \
docker cp arl-temp:/code/start-prod.sh ./ && \
docker cp arl-temp:/code/docker-compose.prod.yml ./ && \
docker cp arl-temp:/code/updater ./ && \
docker cp arl-temp:/code/version.txt ./ && \
docker cp arl-temp:/code/CHANGELOG.md ./ && \
docker cp arl-temp:/code/frontend ./ && \
docker rm -f arl-temp && \
chmod +x start-prod.sh && bash start-prod.sh
```

##### 方法二：GitHub 源码克隆部署（适用于海外服务器 / 源码部署）

> [!TIP]
> `start-prod.sh` 内置全套环境探针，裸机运行亦会自动安装 Docker 并优化内核配置。

```bash
git clone --depth 1 https://github.com/owl234/ARL-Next.git && cd ARL-Next
chmod +x start-prod.sh
bash start-prod.sh
```

---

#### 🔑 访问与初始凭据

部署完成后，在浏览器中访问：`https://<你的服务器IP>:5173`（首次自签名证书请无视浏览器不安全提示）。

| 验证层级 | 默认账号 | 默认密码 | 说明 |
| :--- | :--- | :--- | :--- |
| **第一层：Nginx Basic Auth 网关** | `admin` | `arl_next` | 前置防扫描器爆破（默认关闭，可在顶部导航栏一键开启或修改） |
| **第二层：ARL-Next 系统登录** | `admin` | `arlpass` | 平台主账号，首次登录后建议立即修改 |

> [!TIP]
> - **网络与防火墙开放**：请确保云服务器控制台安全组及系统本地防火墙（如 `ufw allow 5173/tcp` 或 `firewall-cmd --permanent --add-port=5173/tcp && firewall-cmd --reload`）已放行 **5173** TCP 端口。
> - **商业证书替换 (可选)**：将您申请的真实 SSL 证书重命名为 `arl.crt` 和 `arl.key` 放至 `ssl-certs/` 目录，然后再次执行 `bash start-prod.sh` 即可。

---

### 🔄 生产环境版本升级

ARL-Next 支持 **Web 管理后台一键热更新**（在「系统设置」中无感升级）与 **终端标准手动升级**：

#### 方案一：Web 管理后台一键热更新（⭐ 官方首选推荐）

登录 ARL-Next 平台 ➔ 进入 **「系统设置」** 页面 ➔ 点击 **「一键系统更新」**。<br/>
宿主机更新守护进程将自动拉取最新构建、同步最新编排脚本与版本文件，并在后台完成容器热重启与全量健康探活，全程无需登录终端。

#### 方案二：终端标准手动升级

在服务器终端进入 ARL-Next 部署目录，根据您的初次安装方式执行对应升级命令：

* **Git 源码克隆用户 (方法二部署)**：
  ```bash
  cd ~/ARL-Next && git pull && sudo bash start-prod.sh
  ```

* **免 Git 一键部署用户 (方法一部署)**：
  在终端执行以下连缀指令，重新同步最新的编排脚本并平滑拉起：
  ```bash
  cd ~/ARL-Next && \
  docker pull crpi-laul1izptqrf0tkf.cn-beijing.personal.cr.aliyuncs.com/owl234-arl-prod/arl-web:latest && \
  docker run --rm -v $(pwd):/host crpi-laul1izptqrf0tkf.cn-beijing.personal.cr.aliyuncs.com/owl234-arl-prod/arl-web:latest bash -c "cp /code/start-prod.sh /host/start-prod.sh && cp /code/docker-compose.prod.yml /host/docker-compose.prod.yml && cp /code/updater -r /host/updater 2>/dev/null || true; mkdir -p /host/frontend && cp /code/frontend/default.conf.prod /host/frontend/default.conf.prod 2>/dev/null || true; cp /code/version.txt /host/version.txt 2>/dev/null || true; cp /code/CHANGELOG.md /host/CHANGELOG.md 2>/dev/null || true" && \
  sudo bash start-prod.sh
  ```

> [!TIP]
> **底层执行保障**：
> - **数据无损平滑演进**：内置增量迁移逻辑，存量 MongoDB 数据与索引 100% 完整保留，杜绝升级崩溃。
> - **全微服务稳定快照**：自动为当前运行的全量微服务镜像（Web、Worker、Puppeteer、OSINT等）打上 `backup-stable` 标签，保障异常时可秒级回退。
> - **极速拉取与探活**：直连阿里云北京 ACR 镜像私库拉取最新构建，API 动态探活就绪后再放行。

---

## ❓ 常见问题与运维排错 (FAQ)

<details open>
<summary><b>Q1: 首次通过 HTTPS 访问时，浏览器提示“不安全 / 您的连接不是私密连接”？</b></summary>
<br/>

**A:** 系统首次启动时会自动签发本地自签名 SSL 证书。
- 点击浏览器页面的 **“高级” ➔ “继续前往 (不安全)”** 即可正常访问（Chrome 浏览器亦可在页面任意空白处直接键盘盲打 `thisisunsafe` 跳过警告）。
- **配置真实域名证书**：将您申请的证书重命名为 `arl.crt` 和 `arl.key` 放至 `ssl-certs/` 目录，执行 `bash start-prod.sh` 即可无缝切换。
</details>

<details>
<summary><b>Q2: 忘记系统登录密码或 Basic Auth 防爆破凭证怎么办？</b></summary>
<br/>

**A:** 在服务器终端执行以下操作即可一键重置：
- **重置平台管理员账号 (admin / arlpass)**：
  ```bash
  docker exec -it arl-web-prod /code/backend/.venv-docker/bin/python3 /code/backend/inject_user.py --reset
  ```
  > [!NOTE]
  > 平台启动时默认保护现有密码，追加 `--reset` 参数将强制将 `admin` 密码重置为初始密码 `arlpass`。请在宿主机受信环境下执行。
- **重置/查看 Basic Auth 凭据**：编辑工作目录下的 `frontend/.htpasswd`，或登录系统后在顶部导航栏「安全防护」图标中一键热开启/修改/关闭。
</details>

<details>
<summary><b>Q3: 点击 Web 端的“一键系统更新”时，提示 <code>[ERROR]触发更新失败</code>？</b></summary>
<br/>

**A:** 这种情况通常是因为宿主机更新守护进程未响应。您可以通过以下两种方式解决：
- **方式 1 (推荐)：直接在终端执行生产环境标准手动升级**
  ```bash
  cd ~/ARL-Next && sudo bash start-prod.sh
  ```
- **方式 2：重启宿主机更新服务后重试 Web 更新**
  ```bash
  sudo systemctl restart arl-updater.service
  ```
</details>

<details>
<summary><b>Q4: 扫描任务较多时，如何调整系统并发性能？</b></summary>
<br/>

**A:** ARL-Next 支持**动态热调整并发**，无需重启容器！
- 登录平台 ➔ 进入 **「系统设置」** 页面；
- 可视化调整 **轻任务并发数**（DNS/端口/指纹）、**重任务并发数**（Nuclei/PoC）及 **OSINT 并发数**，保存后系统将自动热生效。
</details>

<details>
<summary><b>Q5: 常用 Docker 容器维护与日志排查命令速查？</b></summary>
<br/>

```bash
# 查看所有容器运行状态与健康探针
docker compose -f docker-compose.prod.yml ps

# 实时查看扫描 Worker 执行日志
docker compose -f docker-compose.prod.yml logs -f arl-worker

# 平滑停止或重启全部服务
docker compose -f docker-compose.prod.yml restart
```
</details>

---

## 📜 更新日志

详细的版本演进历史、各版本特性与问题修复记录，请参阅 ➔ [**CHANGELOG.md**](./CHANGELOG.md)

---

## 🤝 致谢

本项目站在巨人的肩膀上，特此鸣谢以下项目与团队：

* **核心架构**：基于经典开源项目 [ARL 资产侦察灯塔](https://github.com/TophantTechnology/ARL) 深度重构，并参考了 [Aabyss-Team/ARL](https://github.com/Aabyss-Team/ARL) 与 [adysec/ARL](https://github.com/adysec/ARL) 等优秀实践。
* **指纹数据**：特别鸣谢 **威零安全团队** (<img src="./img/weiling.jpg" width="18" height="18" align="absmiddle" /> 公众号) 提供的万级高质量 Web 指纹库支撑。
* **功能灵感**：OSINT 企业查询深度借鉴了 [ICP_Query](https://github.com/HG-ha/ICP_Query)，威胁监控模块汲取了 [github-cve-monitor](https://github.com/yhy0/github-cve-monitor) 的优雅设计。

ARL-Next 将始终秉持开源互助的黑客初心，持续为网络安全攻防与企业防御建设贡献力量！

---

## 💖 赞助与支持

ARL-Next 的持续高频迭代离不开社区伙伴的慷慨支持。特别致谢以下赞助者：

<p align="center">
  <img src="./img/buymeacoffee.png" width="180" alt="Buy Me A Coffee" />
</p>

<p align="center">
  <a href="https://github.com/robotfish001" target="_blank">
    <img src="https://github.com/robotfish001.png" width="48" height="48" style="border-radius: 50%; margin: 0 8px;" alt="robotfish-001" title="感谢 robotfish-001 的支持！"/>
  </a>
  <a href="https://github.com/phpmac" target="_blank">
    <img src="https://github.com/phpmac.png" width="48" height="48" style="border-radius: 50%; margin: 0 8px;" alt="phpmac" title="感谢 phpmac 的支持！"/>
  </a>
  <a href="https://github.com/123lpone" target="_blank">
    <img src="https://github.com/123lpone.png" width="48" height="48" style="border-radius: 50%; margin: 0 8px;" alt="123lpone" title="感谢 123lpone 的支持！"/>
  </a>
  <a href="https://github.com/ZQ-Rookie-Hacker" target="_blank">
    <img src="https://github.com/ZQ-Rookie-Hacker.png" width="48" height="48" style="border-radius: 50%; margin: 0 8px;" alt="ZQ-Rookie-Hacker" title="感谢 ZQ-Rookie-Hacker 的支持！"/>
  </a>
</p>

---

## ⚠️ 法律与免责声明

> [!CAUTION]
> **合规红线与免责条款**：  
> 本平台仅供经过合法授权的企业安全建设、SRC 漏洞挖掘、学术攻防演练及安全研究使用。使用本工具开展任何探测与扫描前，使用者必须确保已获得目标资产所有者的明确书面授权，并严格遵守《中华人民共和国网络安全法》及当地法律法规。  
> **严禁利用本工具从事任何未授权的入侵、攻击或破坏行为！** 任何因违规滥用导致的网络安全事故或法律责任，均由使用者本人独立承担，本项目作者与贡献者不承担任何直接或连带责任。

---

## 📄 开源协议 (License)

ARL-Next 项目遵循 [GNU General Public License v3.0 (GPL-3.0)](./LICENSE) 开源许可证协议。

* 🆓 **自由与开源**：您可以免费用于企业自建、安全研究、资产测绘与攻防演练，并享有自由阅读、修改与定制源码的权利。
* 🌐 **传染与同协议共享**：若您在二次开发中修改或基于本项目构建衍生作品并向第三方分发，必须保持在相同的 GPL-3.0 许可证下完整开源相关代码。
* ⚖️ **署名与免责保留**：任何形式的源码复制与再分发，均须保留原始作者版权声明、许可证全文以及免责条款。

---

## 💬 交流群与反馈通道

- 🐛 **Bug 提交与功能建议**：欢迎通过 [GitHub Issues](https://github.com/owl234/ARL-Next/issues) 提交反馈，通常 24 小时内跟进。
- 💡 **技术交流与群聊**：欢迎扫码添加作者微信或加入 QQ 交流群，探讨资产测绘、红蓝对抗与 AI 自动化安全。
- 📢 **版本发版动态**：关注微信公众号【**owl安全**】，第一时间接收最新发版、镜像更新与安全干货推送！

<table align="center">
  <tr>
    <td align="center" style="padding: 10px 25px;"><b>👤 个人微信</b></td>
    <td align="center" style="padding: 10px 25px;"><b>📢 微信公众号 (owl安全)</b></td>
    <td align="center" style="padding: 10px 25px;"><b>🐧 QQ 技术交流群</b></td>
  </tr>
  <tr>
    <td align="center" style="padding: 10px 25px;"><img src="./img/wechat.png" alt="个人微信" width="210" /></td>
    <td align="center" style="padding: 10px 25px;"><img src="./img/wechat_public.jpg" alt="微信公众号 owl安全" width="210" /></td>
    <td align="center" style="padding: 10px 25px;"><img src="./img/qq_group.jpg" alt="QQ交流群" width="210" /></td>
  </tr>
</table>

---

## 🌟 Star 走势与支持

**⭐ 如果 ARL-Next 解决了你长期被扫描假死困扰的痛点，请随手点亮右上角的 Star 支持一下！**

<div align="center">

<a href="https://www.star-history.com/?repos=owl234%2Farl-next&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=owl234/arl-next&type=date&theme=dark&legend=top-left&sealed_token=vNF3XBBUYjnOkZ1XfTODaJEURB73qlNr1zXyCH6HOUbJGKju3QmIb7pVDyjCK67Ra-ukzG7dgZ3B3HDpCKJ3raveN9bOCec7r6gDILhjGrYbcVEV2Gy5Ew" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=owl234/arl-next&type=date&legend=top-left&sealed_token=vNF3XBBUYjnOkZ1XfTODaJEURB73qlNr1zXyCH6HOUbJGKju3QmIb7pVDyjCK67Ra-ukzG7dgZ3B3HDpCKJ3raveN9bOCec7r6gDILhjGrYbcVEV2Gy5Ew" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=owl234/arl-next&type=date&legend=top-left&sealed_token=vNF3XBBUYjnOkZ1XfTODaJEURB73qlNr1zXyCH6HOUbJGKju3QmIb7pVDyjCK67Ra-ukzG7dgZ3B3HDpCKJ3raveN9bOCec7r6gDILhjGrYbcVEV2Gy5Ew" />
 </picture>
</a>

</div>


