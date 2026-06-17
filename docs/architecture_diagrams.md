# ARL-PRO 架构设计图册 (优化版)

以下是对 ARL-PRO 系统的架构与设计流程的深度可视化。新版架构图引入了分组、色彩视觉区分以及清晰的数据流向，使得逻辑更直观、更易读。

---

## 1. 系统核心拓扑图 (System Topology)
采用**颜色区分组件职责**，明确展示控制层（API）、数据流转层（队列/数据库）和执行层（Workers）之间的关系。

```mermaid
flowchart TB
    %% 样式定义：不同类型的组件使用不同颜色体系
    classDef client fill:#3b82f6,stroke:#2563eb,stroke-width:2px,color:#fff,rx:5px,ry:5px
    classDef api fill:#10b981,stroke:#059669,stroke-width:2px,color:#fff,rx:5px,ry:5px
    classDef worker fill:#8b5cf6,stroke:#7c3aed,stroke-width:2px,color:#fff,rx:5px,ry:5px
    classDef db fill:#f59e0b,stroke:#d97706,stroke-width:2px,color:#fff,rx:5px,ry:5px
    classDef target fill:#ef4444,stroke:#dc2626,stroke-width:2px,color:#fff,rx:10px,ry:10px

    Client(["💻 用户浏览器 / API 客户端"]):::client

    subgraph Core["🧠 核心调度控制层"]
        direction TB
        API["⚙️ Flask RESTX API 网关"]:::api
        Scheduler["⏰ Celery Beat (定时调度器)"]:::api
    end

    subgraph Data["🔄 状态与数据流转层"]
        direction LR
        MQ[("📨 RabbitMQ (消息中间件)")]:::db
        MongoDB[("🗄️ MongoDB (持久化存储)")]:::db
    end

    subgraph Workers["⚙️ 分布式执行节点层"]
        direction TB
        W_Default["🔨 Worker 节点 (Default 队列)"]:::worker
        W_Github["🔍 Worker 节点 (Github 队列)"]:::worker
    end
    
    Target(("🌐 互联网资产 / GitHub API")):::target

    %% 交互连线与流向
    Client -- "REST 请求" --> API
    API -- "读写状态与结果" --> MongoDB
    API -- "主动下发任务" --> MQ
    Scheduler -- "到期触发任务" --> MQ

    MQ -- "分配常规扫描任务" --> W_Default
    MQ -- "分配凭证发现任务" --> W_Github

    W_Default -- "并发发包/端口探测" --> Target
    W_Github -- "API 轮询/搜索" --> Target

    W_Default -- "上报站点/域名/漏洞指纹" --> MongoDB
    W_Github -- "上报泄露的敏感词" --> MongoDB
```

---

## 2. API 模块化全景图 (API Mindmap)
利用思维导图展示接口分类，使用 Emoji 进行**视觉锚点定位**，直观展示系统的四大基础骨架。

```mermaid
mindmap
  root((🚀 ARL 接口体系))
    🔐 权限与认证 (Auth)
      (POST /user/login - 登录)
      (GET /user/logout - 登出)
      (POST /user/change_pass - 改密)
    📋 核心任务调度 (Task Engine)
      [扫描生命周期]
        (POST /task/submit)
        (POST /task/stop)
        (POST /task/delete)
      [自动化与策略]
        (POST /scheduler/add)
        (POST /policy/add)
        (POST /asset_scope/add)
    🔎 资产与情报查询 (Data Query)
      [基础资产库]
        (GET /site/)
        (GET /domain/)
        (GET /ip/)
      [漏洞与特殊情报]
        (GET /vuln/)
        (GET /poc/)
        (GET /fingerprint/)
    🛠️ 数据流出与辅助 (Exports & Misc)
      (GET /export/ - Excel 导出)
      (GET /console/info - 仪表盘数据)
      (GET /task_fofa/ - FOFA联动)
```

---

## 3. 标准任务流转时序图 (Task Sequence)
加入背景色区块划分，将任务拆解为**“触发下发”、“异步执行”、“闭环取回”**三个阶段。

```mermaid
sequenceDiagram
    autonumber
    actor User as "👤 操作用户"
    participant API as "⚙️ ARL 后端"
    participant DB as "🗄️ MongoDB"
    participant MQ as "📨 RabbitMQ"
    participant Worker as "🔨 扫描引擎 (Worker)"
    participant Target as "🌐 目标系统"

    rect rgba(59, 130, 246, 0.1)
    Note over User,Target: 阶段一：任务下发与分发
    User->>API: 提交探测任务 (POST /task/submit)
    API->>DB: 写入 Task 记录 (状态: waiting)
    API->>MQ: 推送扫描消息体至 default 队列
    API-->>User: 响应 Task ID
    end

    rect rgba(139, 92, 246, 0.1)
    Note over User,Target: 阶段二：异步分布式执行
    MQ->>Worker: 引擎监听并获取任务
    Worker->>DB: 更新 Task 状态 (状态: running)
    
    loop 多并发引擎探测
        Worker->>Target: DNS解析/端口扫描/HTTP探测
        Target-->>Worker: 返回页面特征与端口指纹
        Worker->>DB: 流式落库 (SITE/DOMAIN/VULN 等表)
    end
    end

    rect rgba(16, 185, 129, 0.1)
    Note over User,Target: 阶段三：任务完结与回查
    Worker->>DB: 任务收尾 (状态: done)
    User->>API: 用户刷新页面 (GET /site/?task_id=xxx)
    API->>DB: 拉取已完成的资产清单
    API-->>User: 渲染数据大屏
    end
```

---

## 4. 数据库实体关系图 (ER Diagram)
明确了主键(PK)、外键(FK)的关系，以及核心集合（Collection）之间是一对多还是一对一。

```mermaid
erDiagram
    %% 核心配置与调度表
    ASSET_SCOPE {
        ObjectId _id PK "范围唯一ID"
        string name "组名称"
        array scope_array "白名单目标列表"
    }
    POLICY {
        ObjectId _id PK "策略唯一ID"
        string name "策略名称"
        object domain_config "子域爆破等选项"
        object site_config "站点抓取等选项"
    }
    TASK {
        ObjectId _id PK "任务唯一标识"
        string name "任务名称"
        string status "执行状态 (running/done/error)"
        string target "原始目标"
        ObjectId policy_id FK "关联使用的策略"
    }

    %% 任务产出结果表
    SITE {
        ObjectId _id PK
        string site "完整 Web 站点地址"
        string title "提取到的网页标题"
        int status "HTTP状态码"
        ObjectId task_id FK "产生该数据的任务"
    }
    DOMAIN {
        ObjectId _id PK
        string domain "解析后的子域名"
        string record "A/CNAME 记录值"
        ObjectId task_id FK
    }
    VULN {
        ObjectId _id PK
        string vuln_name "POC漏洞名称"
        string vuln_url "漏洞存在路径"
        ObjectId task_id FK
    }

    %% 关系连线
    ASSET_SCOPE ||--o{ POLICY : "作为前置条件限制扫描 (1:N)"
    POLICY ||--o{ TASK : "配置检测行为模板 (1:N)"
    TASK ||--|{ SITE : "产出有效站点资产 (1:N)"
    TASK ||--|{ DOMAIN : "产出域名解析记录 (1:N)"
    TASK ||--o{ VULN : "触发扫描出漏洞 (1:N)"
```

---

## 5. Celery 异步队列调度图 (Celery Queues)
展示不同的任务触发方式是如何根据路由键（Route Key）分流到具有不同并发配置的隔离队列中，实现性能管控的。

```mermaid
flowchart LR
    classDef trigger fill:#10b981,color:#fff,stroke:#059669,stroke-width:2px,rx:10px
    classDef queue fill:#f59e0b,color:#fff,stroke:#d97706,stroke-width:2px,rx:5px
    classDef worker fill:#3b82f6,color:#fff,stroke:#2563eb,stroke-width:2px,rx:10px
    
    subgraph Triggers ["🔥 任务触发源"]
        API(["👋 前端人工提交"]):::trigger
        Beat(["⏰ Celery Beat 周期任务"]):::trigger
    end

    subgraph RabbitMQ ["📫 消息路由 (Message Broker)"]
        direction TB
        EX{Exchange 路由交换机}
        Q_Default[("📦 Queue: default<br/>(常规扫描堆栈)")]:::queue
        Q_Github[("📦 Queue: github<br/>(凭证爬取堆栈)")]:::queue
    end

    subgraph Workers ["🚜 工作节点集群 (Celery Workers)"]
        direction TB
        W_Main["🚀 ARL 主执行器<br/>适用高并发(如Nmap/HTTP)"]:::worker
        W_Github["🔍 Github API 执行器<br/>低并发/限流防封"]:::worker
    end

    %% 连线关系
    API -->|实时推送指令| EX
    Beat -->|Cron 表达式到期| EX
    
    EX -- "RoutingKey: default" --> Q_Default
    EX -- "RoutingKey: github" --> Q_Github
    
    Q_Default -.->|"Worker 认领任务"| W_Main
    Q_Github -.->|"Worker 认领任务"| W_Github
```
