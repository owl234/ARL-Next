[![MseeP.ai Security Assessment Badge](https://mseep.net/pr/owl234-arl-next-badge.png)](https://mseep.ai/app/owl234-arl-next)

<div align="center">

  # ARL-Next
  **AI 原生自动化资产侦察与漏洞监控平台**

  *Next-Generation AI-Native Asset Reconnaissance & Vulnerability Monitoring Platform*

  <p><b>告别任务假死与内存泄漏 · 拥抱 AI Agent 自动化调度 · 极速 2 分钟一键开箱即用</b></p>

  <p>
    <a href="https://github.com/owl234/ARL-Next/releases"><img src="https://img.shields.io/github/v/release/owl234/ARL-Next?style=flat-square&color=blue" alt="Release"></a>
    <a href="https://github.com/owl234/ARL-Next/stargazers"><img src="https://img.shields.io/github/stars/owl234/ARL-Next?style=flat-square&color=gold" alt="Stars"></a>
    <a href="https://github.com/owl234/ARL-Next/network/members"><img src="https://img.shields.io/github/forks/owl234/ARL-Next?style=flat-square" alt="Forks"></a>
    <a href="https://github.com/owl234/ARL-Next/blob/main/LICENSE"><img src="https://img.shields.io/github/license/owl234/ARL-Next?style=flat-square" alt="License"></a>
  </p>

  <p>
    <img src="https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white" alt="Docker">
    <img src="https://img.shields.io/badge/Python-3.13-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python">
    <img src="https://img.shields.io/badge/MongoDB-7.0-47A248?style=flat-square&logo=mongodb&logoColor=white" alt="MongoDB">
    <img src="https://img.shields.io/badge/Vue-3.x-4FC08D?style=flat-square&logo=vuedotjs&logoColor=white" alt="Vue">
    <img src="https://img.shields.io/badge/MCP-Native-purple?style=flat-square" alt="MCP">
  </p>

  <p>
    <a href="#quick-deploy"><b>⚡ 2分钟极速安装</b></a> •
    <a href="#comparison"><b>💡 原版痛点对比</b></a> •
    <a href="#core-features"><b>✨ 核心特性</b></a> •
    <a href="./mcp-server/README.md"><b>🤖 MCP配置指南</b></a> •
    <a href="#changelog"><b>📜 更新日志</b></a>
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
| **系统稳定性** | 扫描海量目标时 Celery 阻塞假死、任务丢失 | **微服务解耦** (截图/OSINT独立)，批量入库彻底根除假死 |
| **AI 原生集成** | 无 AI 接口，仅限人工手动点击 | **原生 MCP 支持**，AI Agent 一句话接管资产挖掘与分析 |
| **企业资产穿透** | 无企业资产查询功能 | **天眼查股权穿透 + ICP 深度下钻**，一键秒级打通集团与子公司全量资产 (护网友好) |
| **部署与构建** | 依赖过时容易报错，需拉取海量外网包 | **阿里云国内预构建镜像**，多阶段构建，2分钟一键秒启动 |
| **现代化技术栈** | Python 3.6 / Vue2 / MongoDB 3.x 严重脱节 | **Python 3.13 / Vue3 / MongoDB 7.0** 现代底层全线跨代 |
| **交互与体验** | 页面滚动遮挡表头、分页重置、管理繁琐 | **操作栏/表头悬浮吸附 (Sticky)**、分页持久化、现代化三栏字典 |
| **情报与监控** | 缺少主动情报源、时区错乱导致重复告警 | **GitHub CVE & 泄露雷达**、原子级去重锁、精准时区对齐 |

---

### <span id="core-features"></span>✨ 核心特性矩阵

* 🤖 **AI 原生赋能**：内置标准化 MCP 服务，直接接入 Claude / Cursor / Open-WebUI，实现用自然语言下发扫描与导出 13 维资产全景大盘。（👉 [MCP 配置指南](./mcp-server/README.md)）
* 🚀 **高并发极速引擎**：耗时截图与 OSINT 全面剥离为独立微服务；核心落库升级为 `bulk_write` 批量入库，轻松吞吐数十万级资产。
* 🌐 **全维度企业资产闭环**：深度打通企业 ICP 备案与天眼查股权穿透，自动化构建从“集团公司 ➔ 控股子公司 ➔ 域名 ➔ IP ➔ 端口 ➔ Web/组件 ➔ 漏洞”的完整链条。
* 🛡️ **威胁情报与代码雷达**：内置 GitHub CVE 与代码泄露监控引擎，毫秒级原子锁防重复告警，实时感知外部威胁。
* ⚡ **极简运维与自愈机制**：提供开箱即用的 2 分钟极速部署包，内置容器健康巡检与自愈机制，支持 Web 后台平滑热更新与 Basic Auth 前置防御。
* 🇨🇳 **国内网络深度优化**：全线镜像预构建并托管于阿里云国内私库，彻底告别海外网络阻断与 Pip/Docker 依赖拉取失败。

---

## 📸 界面预览

* **全局仪表盘 (Dashboard)**：实时监测系统资源水位、扫描任务生命周期、多维风险态势大盘与全景操作日志流。
  
  <p align="center">
    <img src="./img/dashboard.png" alt="ARL-Next 全局仪表盘" width="850">
  </p>

<details open>
<summary><b>🖼️ 点击收起 / 展开更多核心业务界面</b></summary>

<br/>

* **企业级 OSINT 资产侦察**：支持企业 ICP 备案穿透与天眼查股权穿透，一键关联并同步下发多维探测任务。
  
  <p align="center">
    <img src="./img/enterprise-asset-search.png" alt="企业资产侦察" width="800">
  </p>

* **任务下发与策略调度**：深度联动 Nuclei、PoC 插件池及 100+ Web 指纹库，支持全生命周期下发与追踪。
  
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
    User["👨‍💻 安全分析师 (浏览器)"] -->|"HTTPS / Basic Auth (5173)"| Nginx["🖥️ Frontend (Nginx + Vue 3)"]
    Agent["🤖 AI Agent (Claude / Cursor)"] -.->|"MCP 协议 (Stdio)"| MCP["🤖 MCP Server (Python 原生)"]

    %% 2. API 网关层
    Nginx -->|"REST API 反代 (5000)"| Backend["⚙️ Backend API (Gunicorn / Python 3.13)"]
    MCP -->|"API Token 鉴权调用"| Backend

    %% 3. 调度与任务分流 (双轨解耦)
    Backend -->|"1. 异步直调 (16181)"| OSINT["🧩 OSINT 微服务 (天眼查/ICP 协程池)"]
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
3. 🧩 **OSINT 独立微服务**：专职天眼查与 ICP 异步情报收集，由 Backend 直调协程池，**彻底脱离 Celery 队列杜绝假死**。
4. ⚡ **多队列 Worker 集群**：拆分**轻量/重载/威胁情报**独立队列；重任务严格限制子进程生命周期彻底根除内存泄露。
5. 🛡️ **微服务与自愈守护 (Puppeteer / Autoheal)**：独立容器专职无头截图并支持滚动自愈；**Autoheal 实时探针秒级恢复容器死锁**。
6. 🗄️ **高吞吐持久层 (MongoDB 7.0)**：全线升级 `bulk_write` 批量落库，核心表覆盖联合唯一索引并设 1GB 内存池保护。

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

在服务器终端 (需 root 权限) 粘贴并执行以下连缀指令。脚本将自动安装 Docker、自愈配置 Swap、从阿里云提取最新配置并一键拉起：

```bash
# 1. 安装基础工具并创建目录
apt-get update && apt-get install -y docker.io docker-compose-v2 openssl curl && \
mkdir -p ~/ARL-Next && cd ~/ARL-Next && \
# 2. 从阿里云国内镜像中提取全套部署编排
docker pull crpi-laul1izptqrf0tkf.cn-beijing.personal.cr.aliyuncs.com/owl234-arl-prod/arl-web:latest && \
docker rm -f arl-temp 2>/dev/null || true && \
docker create --name arl-temp crpi-laul1izptqrf0tkf.cn-beijing.personal.cr.aliyuncs.com/owl234-arl-prod/arl-web:latest && \
docker cp arl-temp:/code/start-prod.sh ./ && \
docker cp arl-temp:/code/docker-compose.prod.yml ./ && \
docker cp arl-temp:/code/updater ./ && \
docker cp arl-temp:/code/version.txt ./ && \
docker cp arl-temp:/code/frontend ./ && \
docker rm arl-temp && \
# 3. 赋予权限并启动
chmod +x start-prod.sh && \
bash start-prod.sh
```

##### 方法二：GitHub 源码克隆部署（适用于海外服务器 / 需二次开发）

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
| **第一层：Nginx Basic Auth 网关** | `admin` | `arl_next` | 前置防扫描器爆破，可在系统设置中一键关闭或修改 |
| **第二层：ARL-Next 系统登录** | `admin` | `arlpass` | 平台主账号，首次登录后建议立即修改 |

> [!TIP]
> **商业证书替换 (可选)**：将您申请的真实 SSL 证书重命名为 `arl.crt` 和 `arl.key` 放至 `ssl-certs/` 目录，然后再次执行 `bash start-prod.sh` 即可。
---

### 💻 开发环境部署 (前端本地 + Docker 后端)

- 👥 **适用场景**：二次开发、PoC 插件编写与深度调试。
- ⚡ **核心优势**：前后端彻底解耦，**双端热重载 (Hot Reload)** 实时生效，无需重复打包。
- ⚙️ **前置依赖**：本地已安装 Docker 与 Node.js 18+ (脚本会自动检测并配置 pnpm 环境)。

#### 🚀 一键拉起开发环境

```bash
git clone https://github.com/owl234/ARL-Next.git && cd ARL-Next
# 自动在后台启动后端容器组 (API / Worker / MongoDB / RabbitMQ)，并在前台启动 Vite 前端服务
bash start-dev.sh
```

启动完成后，访问 `http://localhost:5173` 即可实时预览开发界面（默认凭据：`admin` / `arlpass`）。

---

### 🗄️ 开发者调试端口与数据库直连 (开发环境专用)

> [!NOTE]
> 生产环境为保障安全性已默认切断所有底层中间件外网端口。开发环境下可通过以下地址直连调试：

| 调试组件 | 访问地址 / 连接串 | 账号 | 密码 | 说明 / 用途 |
| :--- | :--- | :--- | :--- | :--- |
| **🍃 MongoDB 7.0** | `mongodb://admin:admin@127.0.0.1:27018/arl?authSource=admin` | `admin` | `admin` | Navicat / Compass 数据库直连 |
| **🐇 RabbitMQ 管理台** | `http://127.0.0.1:15673` | `admin` | `admin` | 消息队列与消费者状态监控 |
| **🐇 RabbitMQ AMQP** | `amqp://admin:admin@127.0.0.1:5673/` | `admin` | `admin` | Celery 任务协议端口 |
| **⚙️ Backend API** | `http://127.0.0.1:5001/api/` | — | — | 后端 Flask RESTful 调试直连 |
| **🧩 OSINT 微服务** | `http://127.0.0.1:16182/docs` | — | — | 天眼查/ICP 异步微服务 Swagger |

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

**A:** 在服务器终端执行以下命令即可一键重置：
- **重置平台管理员账号 (admin / arlpass)**：
  ```bash
  docker exec -it arl-web-prod python3 /code/backend/inject_user.py
  ```
- **重置/查看 Basic Auth 凭据**：编辑工作目录下的 `frontend/.htpasswd`，或登录系统后在 **「系统设置」➔「安全防护」** 中一键热修改/关闭。
</details>

<details>
<summary><b>Q3: 点击 Web 端的“一键系统更新”时，提示 <code>[ERROR]触发更新失败</code>？</b></summary>
<br/>

**A:** 这种情况通常是因为宿主机更新守护进程未响应。请通过 SSH 登录终端执行以下命令重启更新服务：
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

## <span id="changelog"></span>📜 版本更新历史

<details open>
<summary><b>🚀 v1.2.0 (当前版本)</b></summary><br/>

* **交互与体验**：全站核心数据表格与顶部操作栏封装并引入悬浮吸附（`useSticky`）与局部平滑滚动，规避长页面滚动遮挡；统一全局分页器（`useGlobalPageSize`，支持单页 500 条）并实现 `localStorage` 持久化记忆；引入 Vue `Keep-Alive` 页面缓存与返回静默刷新机制。
* **现代化字典系统**：重构字典管理为三栏交互布局（分类/列表/编辑），支持分类 Emoji 命名、新建字典抽屉、txt/dic 在线预览与编辑、未保存呼吸灯提示及一键安全删除；重构字典加载与上传校验模块，收敛路径遍历风险。
* **调度与监控重构**：资产分组下发监控任务新增支持「周期性监控」与「一次性扫描」双模切换，一键下发即时比对增量与变动并精准反馈成功数；重构调度器执行引擎，引入二次防重消费校验与随机休眠，规避队列积压导致并发拉起重复任务；新增 `monitor_diff.py` 动态比对引擎，实现 13 类资产毫秒级基线对比、`new`/`update` 增量打标、未变动资产过滤与 Syslog 审计汇总；修复 SimHash 与联合索引计算，收敛监控防抖失效与内存泄漏。
* **告警推送升级**：全面重构 `push.py` 多通道告警引擎，支持 13 类资产新增（🌟）与变动（🔄）的 Markdown / HTML 结构化报文推送；原生适配钉钉、企业微信、飞书、Telegram 及 Email，内置 3500 字符防超长截断保护与无变动干净摘要。
* **扫描链路与容错隔离**：在 `CommonTask`、`DomainTask`、`IPTask`、`RiskCruising` 中全线引入 `safe_phase` 上下文管理器，实现各扫描阶段异常捕获与耗时审计，规避单插件报错导致 Celery 任务崩溃；调整 `nuclei_scan` 扫描时序至末尾防止目标被阻断；放宽 Nuclei 超时至 15 天；优化 AlienVault/Chaos 查询超时与天眼查防风控延时；文件泄露爆破改用生成器独立迭代规避漏扫。
* **高吞吐持久层**：全线模块升级 `safe_insert_asset_many` 与 `bulk_write` 批量入库，覆盖全量核心集合，消除 N+1 读写瓶颈与高并发主键冲突；支持轻重任务及 OSINT 并发数热扩缩容。
* **AI 原生与运维更新**：MCP 服务由 Node.js 彻底重构为轻量原生 Python 服务（FastMCP），输出深度重构为 AI 原生 CSV 流与 13 维全景资产大盘，Token 消耗降低 80%+；重构 `updater/updater.py` 支持生产镜像覆盖与开发环境 `git pull` 双模更新；优化 `start-prod.sh` 宿主机 Swap 精准探测与 Nginx Gzip 压缩分发。
</details>

<details>
<summary><b>v1.1.8</b></summary><br/>

* **架构跃升**：核心运行环境全面跨代至 **Python 3.13** 与 **MongoDB 7.0**。新增 `upgrade-mongo.sh` 自动化脚本，实现数据库大版本的无损平滑迁移。
* **内存治理**：引入极限防 OOM 机制。切换 RabbitMQ 为 Alpine 镜像，限制 MongoDB 最大内存池为 1GB；导出引擎重构为 `$group` 流式处理，彻底杜绝海量资产溢出。
* **CI/CD 重构**：全线引入 Docker 多阶段构建与 `uv` 极速包管理器，大幅缩减镜像体积。补全自动发版流，实现海外预构建镜像后直推国内阿里云私库。
* **稳定与安全**：底层引入 `contextvars` 根治异步任务上下文丢失；修复 `InfoHunter` 外部命令注入隐患；重构适配 `urllib3` 废弃 `get_host` 后的兼容性崩溃。
* **指纹与交互**：扩充 Vite、React、TOS 等现代 Web 指纹，站点监控新增 `body_length` 异动感知。前端新增 CIDR 气泡悬浮组件以优化聚合视图，MCP 新增 `asset_wih` 调度。
</details>

<details>
<summary><b>v1.1.7</b></summary><br/>

* **核心底座**：重构数据库落库机制，全面引入 `bulk_write` 与批量入库，为13张核心资产表增加联合唯一索引，彻底杜绝极端并发下的数据冗余，大幅提升大任务流性能。
* **网络引擎**：重构底层网络请求工具，引入自适应连接池及 10MB 响应截断保护机制，有效防止因恶意站点超大返回包导致的内存泄漏与任务假死。
* **爬虫自愈**：升级浏览器渲染微服务，新增滚动重启（Rolling Restart）与资源防泄漏自愈机制，根除大批量网页截图时可能产生的僵尸进程。
* **安全控制**：系统设置新增对平台 Basic Auth 防护的图形化热切换支持，底层自动重构并重载 Nginx 网关配置。
* **威胁雷达**：重构 Github CVE 与黑客工具监控逻辑，修复时区导致的数据遗漏，全面改用原子级 `upsert` 防竞争锁确保推送不重复。
* **任务调度**：深度重构 WIH 域名的多层级迭代探测逻辑，并增强全线端口扫描、Web 指纹等组件的错误容忍与忙碌重试策略。
* **前端交互**：大幅优化与重构 Dashboard 仪表盘统计、资产搜索、Github 管理、任务详情等多个核心视图页面，带来更优质的信息呈现。
* **UI 修正**：资产站点表格对齐原版经典字段，恢复状态码、标题展示，修复 WIH 来源映射，并修复“添加标签”功能的交互反馈。
* **部署增强**：增加启动环境自动化巡检，自动识别并清理因 Docker 导致错误生成的幽灵 `.htpasswd` 目录以确保服务正常启动。
* **其他杂项**：精简代码库，清理已废弃截图资源，并在开发文档中补充规范了版本推送的消息标准。
</details>

<details>
<summary><b>v1.1.6</b></summary><br/>

* **架构**：Puppeteer 从后台 Worker 中彻底分离为独立的 Node.js HTTP 微服务容器，大幅释放后台调度压力。
* **性能**：重构指纹识别引擎，引入 Aho-Corasick 多模式匹配算法与内存缓存，极速提升 Web 资产扫描效率。
* **爬虫**：优化 URL 去重算法，底层哈希池引入 Set 结构替代 List，将检索复杂度从 O(N²) 降至 O(1)，消除大规模爬取时的 CPU 瓶颈。
* **部署**：支持 Github 浅拉取 (Shallow clone) 部署兼容；启动脚本新增 API 动态健康检测，彻底消除早期 502 报错。
* **修复**：修复了任务列表 (Task List) 与资产侦察 (Asset Recon) 数据展示异常及状态同步问题。
</details>

<details>
<summary><b>v1.1.5</b></summary><br/>

* **架构**：重构 `icp_query` 为独立 `osint_service` 微服务，引入纯异步调度，降低主节点负载。
* **调度**：实现轻重任务队列分离 (FOFA 等轻查询独立)，并在系统设置中支持精细化并发数配置。
* **部署**：自动分配 2G Swap 解决 OOM 崩溃；多阶段构建缩减镜像体积；新增 Autoheal 容器自愈服务，自动监控并重启假死节点。
* **安全**：热更新服务 (`updater.py`) 增设内网白名单拦截机制，阻断公网调用；修复 Nginx 与 SSE 跨域限制。
* **功能**：任务列表新增“模糊/精确/数值”条件过滤及组合导出；核心任务层增加站点防重复插入机制。
</details>

<details>
<summary><b>v1.1.4</b></summary><br/>

* **修复**：补齐策略中缺失的 Host 碰撞配置，确保后台任务能正常联动与下发。
* **修复**：修复全局背景样式，解决长页面滚动时底部可能出现的白边与背景闪烁问题。
* **部署**：全方位重构一键部署与热更新底层健壮性。新增并发防冲突锁、配置文件原子级写入、网络断连自动重试机制；自动清理遗留幽灵容器与磁盘废弃镜像；增加平滑停机时间（60秒）以防产生扫描脏数据；并修复了多项可能导致部署瘫痪的边缘隐患。
* **构建**：升级 GitHub Actions 构建依赖版本。
</details>

<details>
<summary><b>v1.1.3</b></summary><br/>

* **AI原生**：首次引入 MCP (Model Context Protocol) Server，赋能外部 AI 大模型无缝接管资产调度与检索。
* **UI重构**：前端样式系统全面解耦重构，新增动态主题色与自定义背景，打造极客专属工作台。
* **安全**：生产环境 Nginx 全面启用 Basic Auth 强制前置拦截，容器启动自动生成强密码凭证，实现极致防护。
* **功能**：新增全局资产指纹细粒度检索功能，支持在全系统中穿透式定位目标站点。
</details>

<details>
<summary><b>v1.1.2</b></summary><br/>

* **核心**：新增系统一键升级机制，支持平滑热更新。
* **组件**：Nuclei 扫描引擎升级至 v3.11.0。
* **前端**：极致性能优化，修复 Auth 拦截器等验证问题。
</details>

<details>
<summary><b>v1.1.1</b></summary><br/>

* **资产**：资产范围 (Scope) 扩充，全面支持并严格区分 Domain 与 IP 类型的目标校验与调度。
* **功能**：新增自定义 PoC 源码在线读取、编辑与全可视化创建管理，增强了级联删除逻辑。
* **功能**：新增字典配置模块，提供弱口令字典查询、预览及可视化读写管理。
* **优化**：360 搜索引擎采集逻辑新增反爬熔断保护，追加高价值关键字深度挖掘；生产环境 Nginx 开启 Gzip 压缩。
* **修复**：修复前端详情页高级搜索表单及组件数据联动异常。
</details>

<details>
<summary><b>v1.1.0</b></summary><br/>

* **新增**：全新引入 GitHub 威胁情报雷达（支持 CVE 漏洞雷达、安全武器库及黑客动态监测）。
* **新增**：完善告警生态，支持 Telegram 机器人推送告警。
* **重构**：前端系统设置与 Github 管理页面结构重构，全面启用 HTTP/2 多路复用，大幅降低前端并发加载延迟。
* **修复**：修复 HTTP 存活检测与站点截图组件在 Docker 下的超时和崩溃 Bug，及仪表盘漏洞趋势无数据的 Bug。
</details>

<details>
<summary><b>v1.0.9</b></summary><br/>

* **重构**：分离后端 ARL 内部漏洞与 Nuclei 引擎扫描结果的统计逻辑。
* **交互**：Dashboard 漏洞统计卡片 UI 极简重构，支持按漏洞类型与危害等级点击下钻（Drill-down）。
* **交互**：资产查询页面支持接收仪表盘的联动请求，实现页面跳转与高级筛选项的自动填充。
</details>

<details>
<summary><b>v1.0.8</b></summary><br/>

* **功能**：完善 POC 导入机制，支持批量拖拽上传验证脚本，并提供标准 Python POC 模板下载。
* **架构**：引入 Celery 任务并发热扩缩容机制，修改并发数配置后即时生效，无需重启服务。
* **重构**：重构仪表盘底层查询逻辑，统一基于站点表单库进行海量数据的高效查询。
* **部署**：深度分离开发与生产环境启动脚本，增加 POC 独立数据卷挂载。
* **优化**：优化前端站点截图预览样式防变形，并持续迭代系统内置指纹库。
</details>

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
</p>

---

## ⚠️ 法律与免责声明

> [!CAUTION]
> **合规红线与免责条款**：  
> 本平台仅供经过合法授权的企业安全建设、SRC 漏洞挖掘、学术攻防演练及安全研究使用。使用本工具开展任何探测与扫描前，使用者必须确保已获得目标资产所有者的明确书面授权，并严格遵守《中华人民共和国网络安全法》及当地法律法规。  
> **严禁利用本工具从事任何未授权的入侵、攻击或破坏行为！** 任何因违规滥用导致的网络安全事故或法律责任，均由使用者本人独立承担，本项目作者与贡献者不承担任何直接或连带责任。

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


