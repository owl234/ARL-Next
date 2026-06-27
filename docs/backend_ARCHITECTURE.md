# ARL Backend 架构与开发指南

本文档旨在帮助开发者快速理解 ARL (Asset Reconnaissance Lighthouse) 后端的整体架构、代码执行流转以及各核心目录的作用，为二次开发和调试提供参考。

## 1. 技术栈概述

- **Web 框架**: Flask + Flask-RESTX (用于构建 API 和 Swagger 文档)
- **异步任务队列**: Celery (核心调度引擎)
- **消息中间件**: RabbitMQ / Redis (作为 Celery 的 Broker)
- **数据库**: MongoDB (使用 PyMongo 进行交互)
- **底层驱动引擎**: Python `subprocess` 调用各类安全工具 (Massdns, Nmap 等)

---

## 2. 核心目录结构与文件清单

后端服务的所有核心代码均位于 `backend/` 目录下。下面列出了该目录下所有一级文件/目录以及核心 `app/` 目录下的完整结构说明：

### 2.1 Backend 根目录清单 (`backend/`)

```text
backend/
├── ARL-NPoC/                # [子模块] 存放 NPoC (Network Proof of Concept) 漏洞检测框架的独立组件，用于执行更复杂的漏洞利用检测。
├── GeoLite2/                # [数据/资源] 存放 MaxMind 的 GeoIP 离线数据库，用于将 IP 地址解析为地理位置（城市、ASN等）。
├── poc/                     # [插件/脚本] 存放自定义或开源的漏洞检测 PoC (Proof of Concept) 脚本集合。
├── Dockerfile               # 用于构建 ARL 后端 Docker 镜像的配置文件。
├── config-docker.example.yaml # Docker 环境下使用的配置文件模板。
├── config-docker.yaml       # Docker 环境下真正生效的配置文件（通常由 .example 复制而来）。
├── requirements.txt         # Python 依赖包清单（如 Flask, Celery, pymongo 等），用于 pip 安装。
├── wait-for-it.sh           # 一个工具脚本，用于在 Docker 启动时等待特定的服务（如 MongoDB, RabbitMQ）启动就绪后再启动后端服务。
└── app/                     # [核心] 后端主要的业务代码逻辑存放处，详细解析见下文。
```

### 2.2 App 业务逻辑目录树 (`backend/app/`)

`app/` 是 ARL 后端的心脏，采用了清晰的 MVC + 异步调度解耦设计：

```text
backend/app/
├── __init__.py              # 初始化文件，用于忽略一些告警信息。
├── __main__.py              # 允许通过 `python -m app` 的方式启动应用。
├── main.py                  # [入口文件] Flask APP 初始化、扩展注册、API路由挂载。开发测试时直接运行此文件可启动 Web 服务器。
├── config.py                # [配置中心] 包含各种字典路径、超时设置、TOP端口及对 config.yaml 的加载解析。
├── config.yaml.example      # 本地非 Docker 环境下的配置文件模板。
├── config.yaml              # 本地非 Docker 环境下真正生效的配置文件。
├── celerytask.py            # [异步调度中心] Celery 的初始化、Worker 启动入口，以及通过 action_map 分发任务到具体的 task。
├── scheduler.py             # 定时任务调度器，用于配置并执行周期性的监控任务（如 Github 监控、资产巡航）。
│
├── routes/                  # [API 路由层] (接收请求)
│   ├── __init__.py          # 定义基类 ARLResource，包含统一的参数校验、数据库查询构造、分页等核心功能。
│   ├── task.py              # 处理任务下发、查询、停止等操作的接口。
│   ├── site.py, ip.py...    # 对应各类资产展示的接口（站点、IP、域名等）。
│   └── ...                  # 共有约30个具体的路由文件，对应前端的各个页面和功能。
│
├── helpers/                 # [助手业务层] (拆解与分发)
│   ├── task.py              # 接收 API 传来的数据，将复杂的输入拆分为独立的子任务，写入 MongoDB，最终调用 celerytask.arl_task.delay() 投递到消息队列。
│   └── ...                  # 辅助工具函数集合，连接 API 和 Celery 的桥梁。
│
├── tasks/                   # [干活车间/执行层] (流水线组装)
│   ├── domain.py            # 域名收集流水线（如：DomainBrute -> ScanPort -> WebSiteFetch -> OsDetect）。
│   ├── ip.py                # IP扫描流水线。
│   ├── poc.py               # 漏洞和 PoC 验证执行逻辑。
│   ├── github.py            # Github 信息泄露监控的执行逻辑。
│   ├── scheduler.py         # 定时监控任务的具体执行器。
│   └── asset_site.py / asset_wih.py # 资产变更、同步等运维级任务逻辑。
│
├── services/                # [武器库/底层驱动层] (工具封装)
│   ├── massdns.py           # 封装 massdns 的子进程调用、文件输入输出和结果清洗。
│   ├── portScan.py          # 基于 python-nmap 的端口扫描封装。
│   ├── fileLeak.py          # 目录/备份文件泄露探测引擎。
│   ├── fetchSite.py         # 网站页面内容、Title、Header 抓取服务。
│   ├── findVhost.py         # Host 碰撞和虚拟主机发现探测。
│   ├── searchEngines.py     # 各类空间测绘引擎（Fofa, Quake 等）API 接口对接。
│   ├── webhook.py           # 消息推送服务（飞书、钉钉、企业微信等）。
│   └── ...                  # 共约 35 个服务脚本，是系统能力的基础。
│
├── modules/                 # [数据模型与枚举常量] 
│   ├── __init__.py          # 存放各种业务相关的枚举和常量定义（如 TaskStatus 任务状态字典, CeleryAction 等）。
│   └── domainInfo.py...     # 核心数据结构的类定义，用于规范化各服务间流转的数据包格式。
│
├── utils/                   # [通用工具类]
│   ├── __init__.py          # 包含数据库连接工厂 (conn_db)、日志初始化 (get_logger)。
│   ├── common.py            # 杂项函数（MD5、随机字符串生成等）。
│   ├── http.py              # 基于 requests 封装的通用 HTTP 请求工具。
│   └── ...                  # 其他通用辅助函数，提供基础的编码、加解密等能力。
│
├── tools/                   # [第三方二进制工具库]
│   ├── massdns              # massdns 的 Linux 编译好的二进制可执行文件。
│   ├── driver.js            # puppeteer / 无头浏览器操作相关的 JS 驱动脚本。
│   └── screenshot.js        # 用于给站点资产截图的 JS 脚本。
│
├── dicts/                   # [资产探测字典集]
│   ├── domain_2w.txt        # 默认的 2 万子域名前缀爆破字典。
│   ├── file_top_200.txt     # / file_top_2000.txt: 常见敏感文件泄露、备份文件、Git 探测字典。
│   ├── wih_rules.yml        # Web Info Hunter (Web 信息搜集) 用于匹配 JS 中泄露 API 密钥、密码的正则规则库。
│   ├── webapp.json          # 网站指纹特征库（用于 CMS 识别）。
│   └── ...                  # 各类黑名单、解析服务器列表等基础数据文件。
│
└── tmp/                     # [临时目录]
                             # 运行时动态生成，用于存放扫描过程中的临时文件（如 massdns 的输入输出文件），使用完通常会被代码自动清理。
```

---

## 3. 核心业务数据流转 (Data Flow)

以**“下发一个新的扫描任务”**为例，数据在后端的完整流转链路如下：

1. **[API 路由层] `routes/task.py`**
   - 前端发起 POST 请求。
   - `Flask-RESTX` 拦截并校验参数 (`add_task_fields`)，确保必填项（如 `target`, `name`）和各类扫描开关选项合法。
   - 提取参数后，转交。

2. **[助手业务层] `helpers/task.py` -> `submit_task_task()`**
   - 接收混合目标，进行**分拣**（将目标分离为 IP 组和 域名组）。
   - 为每一组目标在 MongoDB 的 `task` 表中创建初始记录（状态为 `WAITING`）。
   - **异步投递**：调用 `celerytask.arl_task.delay(options)`，将任务打包投递给 RabbitMQ 消息队列。API 请求到此结束并响应前端。

3. **[异步调度层] `celerytask.py` -> `run_task()`**
   - 后台运行的 Celery Worker 监听队列，收到消息。
   - 根据消息中指定的 `celery_action`（如 `DOMAIN_TASK`），在 `action_map` 中找到对应的调度函数并执行。

4. **[执行层] `tasks/domain.py` -> `domain_task()`**
   - 核心流水线启动。以积木的方式依次实例化并运行各种处理器：
     - `DomainBrute().run()`: 获取子域名列表。
     - `ScanPort().run()`: 获取存活端口。
     - `WebSiteFetch().run()`: HTTP 请求获取 Title/Status。
     - ...
   - 每一道工序处理完毕后，都会将结果（资产、漏洞等）实时插入到对应的 MongoDB 业务表中。

5. **[底层引擎层] `services/`**
   - 上述执行层在运行时，会调用 `services` 里的脚本来完成具体工作（例如 `DomainBrute` 调用了 `services/massdns.py`）。
   - `services` 负责处理底层命令行拼接、调用 `subprocess` 并将杂乱的 stdout 结果结构化为字典供上层使用。

---

## 4. 二次开发实战指南

### 4.1 如何新增一个自定义扫描插件（如：Nuclei 漏扫）

如果你想在现有的资产发现任务中，加入一项新的扫描工序：

1. **编写底层封装**：
   在 `services/` 下新建 `nuclei_scan.py`，使用 `subprocess` 调用 nuclei，并解析生成的 JSON 结果文件，返回一个结构化的 Python 列表。
2. **加入执行流水线**：
   在 `tasks/domain.py` 或 `tasks/ip.py` 中，编写一个类（如 `class NucleiTask(object):`），在 `run()` 方法中调用你刚写的 service，并将结果写入数据库。然后在最底部的 `domain_task` 主函数中，将其加入到流水线链条的适当位置。
3. **增加前端开关 (可选)**：
   在 `routes/task.py` 的 `add_task_fields` 模型中增加一个布尔值字段 `"nuclei_scan": fields.Boolean()`，以便前端可以通过打钩来控制是否开启该工序。

### 4.2 本地调试建议

- 调试 API 接口时，直接运行 `python -m app`（指向 `main.py`），可以在 IDE 中对 `routes/` 和 `helpers/` 下的代码打断点。
- 调试扫描任务执行逻辑时，需要以 Celery 模式启动：`celery -A app.celerytask.celery worker -l info`。在 IDE 中配置对应的 Celery 运行环境，即可对 `tasks/` 和 `services/` 里的代码进行断点调试。
