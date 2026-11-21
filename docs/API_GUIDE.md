<div align="center">
  <p>
    <a href="./API_GUIDE_en.md"><b>English</b></a> |
    <b>简体中文</b>
  </p>
</div>

# ARL-Next REST API 调用与二次开发约定指南

> 本指南汇总了 ARL-Next 平台的 API 基础规范、鉴权机制、特殊 HTTP 方法约定、状态流转约束以及数据命名空间说明，供自动化脚本、CI/CD 流水线及安全编排系统对接参考。<br>
> 完整且实时的 OpenAPI / Swagger 接口文档，可在平台部署拉起后访问 `https://<your-arl-host>:5173/api/doc` 在线调试。

---

## 1. 基础规范与网关路由

- **基础路径**：后端接口统一以 `/api` 为前缀。
- **协议与端口**：生产环境下所有请求均通过前端 Nginx 网关反向代理，默认地址为 `https://<your-arl-host>:5173/api/...`。
- **响应体格式**：所有接口均返回 JSON 格式数据，标准顶层响应字段包含业务码 `code` 与提示信息 `message`：
  ```json
  {
    "code": 200,
    "message": "success",
    "data": { ... }
  }
  ```
  > [!IMPORTANT]
  > 客户端**不能仅凭 HTTP 200 状态码判定业务成功**，必须同时校验响应体中的 `code === 200`（或对应业务成功码）。

---

## 2. 身份鉴权与安全机制

- **Header 鉴权（必需）**：启用平台鉴权时，请在 HTTP 请求头中传入：
  ```http
  Token: <your-token>
  ```
- **URL 中不接受账号凭据**：`?token=` 已停用，避免完整账号凭据进入网关和代理日志。受保护接口的认证拦截返回 HTTP 401 与 JSON `code: 401`；其他存量业务错误仍应检查 JSON `code`。
- **会话与迁移**：登录/刷新生成密码学随机令牌，有效期 24 小时；旧会话迁移时仅补一次 24 小时到期时间，重复启动不会续期。旧 MD5 密码在成功登录时升级为 scrypt，升级不重置已有密码。新建/重置账号不再使用固定初始密码；新密码长度为 12–1024 个字符。长期集成可配置独立的全权限 `API_KEY`，并在 MCP 客户端通过 `ARL_TOKEN` 使用；该 Key 仍需按管理制度轮换。
- **登录限速**：后端使用 MongoDB 原子计数，单账号每 5 分钟最多 10 次尝试，成功后清除账号计数；每个后端连接地址每分钟最多 60 次。生产网关另按实际客户端 IP 限制为每分钟 5 次、突发 5 次。超限返回 HTTP 429；后端同时提供 `Retry-After`。代理层限速不依赖客户端提供的转发头。
- **截图与文件**：截图需要同样的 Header 鉴权，前端获取 Blob 后显示并回收 URL。Nuclei 导出使用 Header 下载。大文件备份先通过已认证的 `POST /api/backup/download_ticket` 提交 `{"filename":"arl_backup_....tar.gz"}`，然后以 `GET /api/backup/download/<filename>?ticket=<ticket>` 下载。票据有效期 60 秒、仅限该文件、原子消费一次；账号登出、刷新令牌或 API Key 轮换后失效。票据不能访问其他 API；下载中断后重新申请票据。
- **更新服务**：控制操作仅接受 POST，令牌通过 `X-Update-Token` 或 JSON body 发送；`POST /api/system_config/request_update_token` 返回 5 分钟有效的控制令牌。查询网关状态时先传 `{"purpose":"status"}` 获取独立状态令牌。触发更新返回仅用于日志的 `log_token`，轮询 `/update_stream/log` 时放在 `X-Update-Read-Token` 请求头。只读令牌有效期 1 小时，摘要保存在宿主机 `/var/lib/arl-updater/read_token.json`（0600），容器重启不影响日志读取；每次更新会撤销上次的只读令牌。匿名日志读取和跨域通配访问已关闭。
- **安全红线**：严禁将真实 API Token 提交至公开代码仓库、Issue 讨论、公开运行日志或终端命令历史。
- **免鉴权环境**：若在测试或私有内网环境下于配置中关闭了平台鉴权，接口将跳过 Token 校验。对外开放部署时请务必确认网关与平台鉴权策略处于启用状态。

### 安全修复方案与验收范围

| 问题 | 修复措施 | 回归验收 |
| :--- | :--- | :--- |
| 备份解压越界 | 外层固定构件清单、SHA256、拒绝链接/特殊文件/重复成员；内层仅允许各自的截图、字典、插件目录；先暂存并校验所有构件及目标路径，再执行数据库覆盖恢复 | 路径穿越、软硬链接、目录错放、目标已有链接、哈希错误均在数据库恢复前拒绝；正常归档可还原 |
| favicon SSRF | HTTP(S) URL 校验、拒绝用户凭据、检查全部 DNS 地址和 IP/域名黑名单；连接固定到校验过的 IP，保留 Host/SNI，禁用重定向并限制响应为 2MB | 回环、链路本地、混合地址及黑名单目标不发请求；直连与代理均使用已校验的字面 IP |
| 第三方凭据 TLS | 通用请求默认验证证书；扫描目标显式选择自签兼容，且使用隔离连接池 | 不可信证书收不到 API 凭据，包括先访问自签扫描目标再访问 API 的情况 |
| 截图匿名读取 | 后端统一鉴权，前端携带请求头取图并设置私有不可缓存响应 | 匿名 401，合法凭据能显示和预览 |
| 下载 URL 泄露 Token | Header 下载与资源限定的短时单次票据 | 过期、重复使用、跨文件或会话撤销后的票据均失败 |
| 黑名单范围绕过 | 对完整 IP 区间/CIDR 检查交集，解析或策略读取失败时拒绝 | 范围中任意地址被禁止即阻止扫描 |
| CSV 公式注入 | 对数据和表头中的公式触发前缀按文本转义 | 包括带空白、制表和换行前缀的公式值 |
| 登录安全基线 | 随机初始密码、scrypt、失败限速、会话到期与凭据撤销 | 旧密码成功登录后升级；现有账号不被启动脚本重置 |
| 更新日志匿名读取 | 独立、短期、只读令牌；控制令牌限制用途和到期时间 | 匿名读取拒绝；后端不可达时有效日志令牌仍可用；状态令牌不能执行更新 |
| MCP 导出代码拼接 | 校验服务端 Origin，并将凭据作为字符串字面量序列化 | 恶意 Host 被拒绝；特殊字符 API Key 不能变为 Python 语句 |

升级应同步交付后端、前端网关和宿主机 updater。旧的 `?token=` 调用方需迁移到请求头；含链接或非标准构件的历史备份需先整理为标准归档。备份可能包含可执行的 Python PoC，只应恢复可信来源的归档；SHA256 用于完整性检查。第三方私有 API 使用自签证书时，应挂载可信 CA 并配置 `REQUESTS_CA_BUNDLE`，不得关闭 API 的 TLS 校验。本次 SSRF 修复限定 favicon 抓取链路；扫描浏览器、PoC 等执行环境仍应与管理网和云元数据网络隔离。回退到旧版会重新暴露本节列出的风险。

隔离回归入口：安装后端依赖及 `pytest`、`mongomock` 后运行 `python backend/test/run_security_regressions.py`。测试使用 MongoDB 替身、临时文件和本机 HTTP/TLS 服务，不触发真实扫描或部署操作。前端文件鉴权测试可在 `frontend/` 中运行 `node --test test/authenticatedFiles.test.js`。

---

## 3. 任务操作约定与状态流转约束

> [!WARNING]
> ARL-Next 任务管理接口包含部分由于历史兼容保留的特定 HTTP 方法与前置状态约束，对接时请务必遵循以下规范，避免盲目猜测 RESTful 动词。

### 核心任务接口速查表

| 操作事项 | HTTP 方法及完整路径 | 请求参数 / 请求体格式 | 状态要求与注意事项 |
| :--- | :--- | :--- | :--- |
| **查询任务列表** | `GET /api/task/` | 查询参数：`target`、`status`、`page`、`size`；可追加 `include_statistics=1` | 分页返回任务列表 |
| **查询扫描任务统计** | `GET /api/task/statistics` | 无 | 仅返回各状态任务数量汇总，不遍历任务详情 |
| **查询企业任务统计** | `GET /api/icp/task/statistics` | 无 | 仅返回企业工商/ICP 任务的全局状态统计 |
| **停止单个任务** | `GET /api/task/stop/<task_id>` | URL 路径参数：`task_id` (24位十六进制) | ⚠️ **注意：此接口使用 GET 方法执行状态变更**（终止任务执行），切勿误认为只读接口，亦不要使用 `POST` 或 `DELETE` |
| **批量停止任务** | `POST /api/task/batch_stop/` | JSON：接口文档所示请求体 | 批量停止指定任务列表 |
| **停止单个企业任务** | `GET /api/icp/stop/<task_id>` | URL 路径参数：`task_id` (24位十六进制) | ⚠️ **注意：此接口使用 GET 方法执行状态变更**；终止 `osint-service` 测绘协程并释放关联资产组更新锁；已结束任务返回错误码 `105` |
| **批量停止企业任务** | `POST /api/icp/batch_stop/` | JSON：`{"task_ids": ["<task_id>"]}`（兼容 `task_id` 字段） | 逐项终止活跃企业测绘任务并释放关联资产组更新锁，自动跳过已结束任务，返回 `stopped_ids` / `skipped_ids` / `failed_ids` 明细 |
| **断点续跑企业任务** | `POST /api/icp/resume/<task_id>` | URL 路径参数：`task_id` | 仅允许处于 `stop` 或 `error` 且存在未完成 `recon_checkpoint` 的任务；原位恢复剩余主体与维度测绘，保留已入库资产 |
| **原位补全缺失详情** | `POST /api/icp/backfill_details/<task_id>` | URL 路径参数：`task_id`；可选 JSON：`{"query_types": ["app", "mapp", "kapp"]}` | 仅允许终态任务；取消单批 100 条截断上限，原位补全 `serviceName` 为空的条目（对 `dataId=0` 或已轮换失效记录按备案号重刷最新 `dataId`），并执行跨源同名合并与统计校准，不新建任务 |
| **删除任务** | `POST /api/task/delete/` | JSON：`{"task_id": ["<task_id>"], "del_task_data": false, "del_synced_asset": false}` | ⚠️ **前置条件约束**：仅允许删除处于 `done`、`stop` 或 `error` 结束态的任务；进行中任务将返回错误码 `104`。`del_synced_asset` 默认为 `false`（保留资产组台账），仅在同时指定 `del_task_data: true` 时生效，清理仅由被删任务独占同步至资产组的记录并重算派生统计 |
| **重启任务** | `POST /api/task/restart/` | JSON：`{"task_id": ["<task_id>"]}` | 仅允许重启已结束的任务 |
| **立即执行计划任务** | `POST /api/task_schedule/run/` | JSON：`{"_id": ["<schedule_id>"]}` | 立即触发所选扫描计划任务派发进入调度队列，并递增 `run_number`、刷新 `last_run_date`（周期计划处于 `scheduled` 时同步重算 `next_run_date`） |

### 新建任务关联资产组

新建资产侦查任务时，可选择一个已有资产组，也可保持不关联。资产组选项支持名称搜索和分页加载；选择后，任务完成会通过现有资产同步流程将结果同步到该组，不创建周期监控，也不自动扩展资产组范围。

`POST /api/task/` 新增可选 JSON 字段 `related_scope_id`，例如：

```json
{"name": "边界资产探测", "target": "www.example.com", "related_scope_id": "<asset_scope_id>"}
```

后端在批量创建任务之前检查资产组是否存在，以及所有域名、IP 或 CIDR 目标是否属于该组；保留系统原有目标和黑名单校验。不传该字段时沿用原普通扫描行为。重启关联任务时保留组 ID，重新校验当前范围，并清除新任务的旧同步状态。

任务列表的资产组列区分完成后同步、等待同步、同步中、已同步和同步失败；失败原因在提示中展示。扫描结果与同步状态独立保留，选择了资产组不代表已经同步成功。同步前再次检查组是否存在及任务目标范围；组被删除或范围改变时不继续同步。

`POST /api/task/sync/` 支持已结束的域名和 IP 任务，参数为 `task_id`、`scope_id`；仍需完整范围校验。同步任务派发前记录等待状态，派发失败记录原因。自动同步和手动同步成功后记录 `synced_scope_id` / `synced_scope_name` 及 `sync_summary`（包含 `total_new` 新增计数、`total_update` 存量更新计数与按资产维度的 `new` / `update` 明细），失败时记录 `sync_error`，不自动重试。对于非核心阶段发生的局部异常，任务仍保留已发现资产并正常进入终态，同时在 `error_msg` 与 `phase_errors` 字段记录分阶段异常明细；核心发现阶段失败则使任务进入 `error` 状态。

任务创建支持按资产组圈定范围；Nuclei YAML/ZIP 导入由 PoC 管理页提供，此处不再重复实现。

### 端口扫描存活探测策略 (`host_discovery_mode`)

`POST /api/task/`（顶层字段 `host_discovery_mode`）、`POST /api/policy/add/` 与 `POST /api/policy/edit/`（位于 `policy.ip_config.host_discovery_mode`）支持设置端口扫描前的主机存活探测模式，同时支持通过 `GET /api/task/?options.host_discovery_mode=<mode>` 按策略筛选任务：

| 取值 | 行为说明 |
| :--- | :--- |
| `auto`（默认，缺失或空值时按此处理） | 按「展开后的目标 IP 数 × 展开后的扫描端口数」自动选择：<br>• 端口数 `<= 60`（且非 `1-65535`）：始终 `-Pn` 直扫<br>• 端口数 `61~2000`（覆盖 `top100` / `top1000`）：`<= 16` 个 IP 用 `-Pn`，`> 16` 个 IP 用 `-PE -PS<alive_port>`<br>• 端口数 `> 2000` 或 `1-65535`：`<= 2` 个 IP 用 `-Pn`，`> 2` 个 IP 用 `-PE -PS<alive_port>` |
| `skip` | 强制跳过存活探测，固定使用 `-Pn` 直接扫描端口 |
| `probe` | 强制先执行存活探测（`-PE -PS<alive_port>`），仅对存活主机继续扫描 |

> **约束说明**：传入 `auto` / `skip` / `probe` 之外的非空值将被服务端拒绝。启用 `-PE -PS` 探活时，系统会自动从常用探测端口集（`port_alive.txt`）中剔除 `exclude_ports` 所列端口；若探测端口全部被排除，则退化为仅发送 `-PE` 探测。

示例（强制对目标网段直接 `-Pn` 扫描）：

```json
{"name": "内网直扫", "target": "192.0.2.0/24", "port_scan": true, "port_scan_type": "top100", "host_discovery_mode": "skip"}
```

### 站点截图开关 (`site_capture`)

`POST /api/task/`（顶层字段 `site_capture`）、`POST /api/policy/add/` 与 `POST /api/policy/edit/`（位于 `policy.site_config.site_capture`）支持控制 ASM 任务是否执行无头浏览器页面截图；所有基于策略下发的任务（策略侦察、风险巡航、计划任务、资产组域名/IP 监控与一次性扫描、手动添加站点/域名、Fofa 及 MCP 调度）均自动继承策略中的 `site_capture` 配置：

| 取值 | 行为说明 |
| :--- | :--- |
| `true`（默认，缺失或 `null` 时按此处理） | 对存活且未被识别为默认后端（`catch_all`）的站点执行无头浏览器截图并写入 `/image/<task_id>/<file>.jpg` |
| `false` | 跳过截图阶段，站点文档 `screenshot` 字段写入空串 `""`；同步至资产组时若存量站点已有历史截图，将予以保留而不覆盖抹除 |

> **边界说明**：WIH 独立监控（对新增子域的存活站点补截）与站点变更监控（轻量 HTTP 巡检，不截图）不绑定扫描策略，维持既有行为；被 `catch_all` 机制识别的默认后端站点即使开启 `site_capture` 也会跳过截图。

示例（关闭截图以加快大批量侦察任务执行）：

```json
{"name": "快速资产探测", "target": "example.com", "port_scan": true, "site_identify": true, "site_capture": false}
```

### 任务生命周期与删除最佳实践

若需通过自动化脚本删除正在执行中的任务，必须严格执行两阶段操作：
1. 先调用 `GET /api/task/stop/<task_id>` 将任务终止至 `stop` 状态；
2. 校验任务状态确认进入终态后，再调用 `POST /api/task/delete/` 提交删除。直接对运行态任务请求删除将被服务端拒绝并返回 `{"code": 104, "message": "任务运行中"}`。

### 统计指标参数 (`include_statistics=1`)

- 在调用 `GET /api/task/?include_statistics=1` 或 `GET /api/icp/task?include_statistics=1` 时，响应结构中将附加 `statistics` 字段：
  ```json
  {
    "total": 120,
    "running": 2,
    "waiting": 1,
    "done": 110,
    "error": 5,
    "stop": 2,
    "active": 3,
    "abnormal": 7
  }
  ```
  - `active`：活跃任务总数（`running + waiting`）。
  - `abnormal`：非正常结束任务总数（`error + stop`）。
  - `running`：对于扫描任务，涵盖了端口扫描、服务识别、风险巡航等各阶段中间态。
  - **统计范围**：统计数据是按对应任务集合全局聚合计算的，不随当前分页或关键词筛选发生变动。
- **容错降级设计**：若后端在统计聚合阶段遇到偶发异常，列表主数据依然会正常返回，并附加 `statistics_error: true`（省略 `statistics` 字段）。客户端应做容错兜底，保留上一轮有效统计值，避免界面闪烁或误显为零任务。

---

## 4. 查询结果的命名空间隔离规范

ARL-Next 将资产数据分为**任务临时成果**与**资产组归档资产**两个独立的数据集，在接口路径上存在明确的命名空间隔离：

| 资产类型 | 单任务检索命名空间 (按 `task_id`) | 资产组检索命名空间 (按 `scope_id`) |
| :--- | :--- | :--- |
| **子域名** | `/api/domain/` | `/api/asset_domain/` |
| **IP 地址** | `/api/ip/` | `/api/asset_ip/` |
| **Web 站点** | `/api/site/` | `/api/asset_site/` |
| **其他维度** | `/api/wih/`、`/api/vuln/`、`/api/fileleak/` 等 | `/api/asset_wih/`、`/api/asset_vuln/` 等 |

> [!NOTE]
> - 按任务查询时，入参必须指定对应探测的 `task_id`；
> - 按资产组查询时，入参必须指定目标资产组的 `scope_id`；
> - 两个命名空间对应不同的 MongoDB 底层持久化集合与联合索引，字段定义与筛选维度请以 `/api/doc` 最新说明为准。

### WIH 接口候选（静态识别）

在当前生效的 `WIH_RULE_PATH` 规则文件中新增或启用以下规则，然后运行已有的 WIH 任务：

```yaml
rules:
  # 保留其他已有规则，仅新增或修改这一项。
  - id: api_endpoint
    enabled: true
```

此规则默认关闭，不替代已有的 `path`、URL 或敏感信息规则。仅启用 `enabled` 时复用已下载的页面内联脚本和外部 JS，不请求候选接口。主动采集需要单独启用下文的 `probe`。

- 支持静态字符串参数的 `fetch`、`window.fetch`、`globalThis.fetch`、`axios(config)`、`axios(url, config)`、`axios.request(...)` 和 `axios.get/post/put/patch/delete/head/options(...)`。
- Fetch 相对地址按页面实际响应地址及首个 `<base href>` 补全，外部 JS 位于 CDN 时也不使用 CDN 目录。Axios 按调用内明确的 `baseURL` 拼接，保留 `/v1` 等路径前缀；未能确定基址时保留原始路径，`api_request.url` 为 `null`。未知方法记为 `UNKNOWN`。
- 不执行动态表达式，不推断变量、字符串拼接、带插值的模板、Axios 实例别名、运行时 defaults 或拦截器。无法静态确认的表达式不会被标为完整接口；原有 WIH 规则继续按原方式提取。
- 每个站点最多新增 200 条候选；每段脚本最多处理 100,000 个词法单元，单个调用最多处理 512 个词法单元，单个字符串最多解码 8,192 个源字符。达到上限只停止附加接口提取，不停止原有 WIH 扫描。该提取器是有明确语法范围的静态分析，并非完整 JavaScript 解析器。

结果复用 `/api/wih/`（任务）和 `/api/asset_wih/`（资产组），可按 `record_type__eq=api_endpoint` 筛选，再用 `content=POST` 或路径片段缩小范围。`content` 包含方法、补全后的地址及原始路径，`source` 保留来源和脚本内行号；内联脚本行号相对于提取后的脚本文本。示例：

```json
{
  "record_type": "api_endpoint",
  "content": "GET https://app.example.test/api/users [path: /api/users]",
  "site": "https://app.example.test/",
  "source": "https://cdn.example.test/app.js [script:line 12]",
  "risk_level": "LOW",
  "api_request": {
    "method": "GET", "path": "/api/users", "url": "https://app.example.test/api/users",
    "client": "fetch", "line": 12, "verified": false
  }
}
```

`verified: false` 表示尚未收到候选接口的 HTTP 响应；`LOW` 为现有 WIH 分类中的低风险候选。`api_request` 为可选附加信息，历史记录无需回填，旧记录的序列化和去重标识保持原样。同一方法、原始路径和补全地址的候选复用现有站点级去重，保留首次来源，不合并不同方法。

列表和对应的 `/export/` 共用筛选参数；单项、任务批量及资产组批量 WIH 文本导出均保留接口候选的来源，其他类型的导出格式保持原样。

### WIH 接口可达性与响应采集

在上述内置规则中同时启用两个布尔开关，随后运行 WIH 任务：

```yaml
rules:
  - id: api_endpoint
    enabled: true
    probe: true
```

`probe` 默认 `false`。仅配置 `probe`、禁用规则、使用自定义 `pattern` 或填写字符串 `"true"` 均不会开启主动采集。

- 只请求与任务原始 `site` 的协议、主机、有效端口完全相同的完整 GET、HEAD 候选；相对路径须先能按静态规则补全。跨域 API、不同端口、页面跨域重定向后生成的接口仍保留为候选，但不自动扩展扫描范围。
- 保留原始方法，不将 POST、PUT、PATCH、DELETE、OPTIONS 或 UNKNOWN 改为 GET。请求不带请求体、页面 Cookie、脚本认证头或 netrc 认证；沿用 WIH 的显式代理与 TLS 证书校验设置。URL 的路径和查询参数按提取结果发送。
- 每站点最多探测 20 个不同的 `(method, url)`，重复候选复用结果。同源重定向最多跟随 3 次，每次发送前校验同源、循环及现有 `api_endpoint` 排除规则；跨域、不同端口、协议变化和含用户密码的地址会停止跟随。
- 连接及读取超时分别为 3 秒；每个候选按 10 秒、每个站点按 60 秒的预算，在请求前及正文读取期间检查。底层 DNS、连接和阻塞读取仍受网络库行为影响，这些预算不构成任务总时长的硬上限。配额用尽或采集失败不删除静态候选，也不影响先行完成的原有 WIH 提取。
- 保存最后一次已收到的 HTTP 响应状态、URL、UTC 检查时间、耗时和重定向链。仅保存 Content-Type、Content-Length、Server、Allow 四种响应头，各最多 1,024 字符，不保存 Set-Cookie 等认证头。GET 文本响应最多保留 16 KiB 解码前字节的摘要；JSON、XML、JavaScript 等按文本处理，HEAD、二进制及未知类型不读取正文。摘要可能包含敏感数据，沿用现有 WIH 接口鉴权；不会执行或渲染其中的 HTML、脚本。

响应通过现有 `/api/wih/` 和 `/api/asset_wih/` 的 JSON 列表返回，位于 `api_request.probe`。本阶段未新增响应详情界面、接口截图或漏洞判断，文本导出也不附带响应正文。示例：

```json
{
  "verified": true,
  "probe": {
    "state": "responded", "method": "GET", "status_code": 403,
    "url": "https://app.example.test/api/users",
    "last_attempt_url": "https://app.example.test/api/users",
    "checked_at": "2026-01-01T00:00:00+00:00", "elapsed_ms": 12,
    "headers": {"content-type": "application/json"}, "redirects": [],
    "body_preview": "{\"error\":\"forbidden\"}", "body_bytes": 21, "body_truncated": false
  }
}
```

`state=responded` 和 `verified=true` 仅证明收到 HTTP 响应，401、403、404、5xx 同样会记录，不能证明接口有效、无需认证或存在漏洞。重定向停止时用 `redirect_stop` 说明原因；后续一跳失败会保留上一跳响应，在 `error` 和 `last_attempt_url` 中标明失败，不能据此认定最终地址可达。正文读取失败仍保留状态和已读摘要，使用 `body_error`、`body_truncated` 标记不完整。

未收到任何 HTTP 响应时 `state=error`，`error` 区分 `timeout`、`connection_error`、`tls_error`、`request_error`、`time_budget`，不保存异常原文。未尝试的候选为 `state=skipped`，`reason` 区分 `unsupported_method`、`unresolved_url`、`outside_origin`、`excluded`、`site_quota`、`site_budget`。资产组监控会刷新已有候选的本次采集状态，不因状态变化重复发送新增通知；关闭主动采集后的静态扫描保留先前响应，响应时间以 `checked_at` 为准。新增嵌套字段均为可选，不需迁移或回填历史数据。

### 维度计数接口

`GET /api/asset_overview/count` 一次性返回底层 13 个资产集合的维度计数，用于客户端渲染维度页签的数量徽标，避免为每个维度单独发起计数请求。支持可选查询参数 `scope_id`：

- **省略 `scope_id`**：统计全局无前缀资产集合（`site`、`domain`、`ip` 等 13 个集合）的聚合总量；
- **传入 `scope_id=<asset_scope_id>`**：统计指定资产组下 `asset_*` 集合（`asset_site`、`asset_domain` 等 13 个集合）的维度总量，口径与各 `/api/asset_*/` 列表接口的 `total` 严格一致。

响应示例：

```json
{
  "code": 200,
  "message": "success",
  "counts": {
    "site": 12800, "domain": 45600, "ip": 9800, "cert": 3200,
    "service": 15400, "fileleak": 210, "url": 76200, "vuln": 540,
    "npoc_service": 1300, "cip": 860, "stat_finger": 320,
    "nuclei_result": 97, "wih": 44
  }
}
```

> [!IMPORTANT]
> - 省略 `scope_id` 返回的是**全局无前缀集合聚合口径**，传入 `scope_id` 返回的是**指定资产组 `asset_*` 集合口径**，二者统计范围不同，不可混用推导；
> - `counts` 返回底层 **13 个资产集合**的计数；前端「资产搜索」「资产组详情」「任务详情」与全链路资产画像抽屉统一展示 **12 个资产维度**（含 `nuclei_result`），其中 `service` 已在后端按 `(ip, port_id)` 单端点融合 Nmap 端口服务与 Python 插件服务（`npoc_service` 集合保留用于内部扫描链路与向下兼容），「服务」页签徽标与 `GET /api/service/`（全局按 `(ip, port_id)` 跨任务去重）及 `GET /api/asset_service/` 的 `total` 严格一致；
> - 各维度计数口径与其对应列表接口保持一致，例如全局 `service` 统计跨任务去重后的 `(ip, port_id)` 端点数、`cip` 统计去重后的 C 段数、`stat_finger` 统计去重后的指纹名数量，而非原始集合文档数；
> - 单个维度计数失败时该字段返回 `null`，客户端应视为「未知」并避免渲染为 `0`。

### 系统服务单端点融合查询与导出约定

`GET /api/service/`（全局与任务级）与 `GET /api/asset_service/`（资产组级）统一返回按 `(ip, port_id)` 归并后的单端点服务记录（融合 Nmap 端口服务与 Python 插件握手识别结果）：

- **融合与校准规则**：同一 `(ip, port_id)` 同时命中 Nmap 与 Python 插件时自动合并为单条记录，Python 协议握手结果优先校准 `unknown` / `tcpwrapped` 等弱服务名，保留 Nmap 探测到的 `product` 与 `version`，并通过 `sources` 数组标注识别来源（`["nmap"]`、`["npoc"]` 或 `["nmap", "npoc"]`）；全局查询（不传 `task_id`）按 `(ip, port_id)` 跨任务去重归并。
- **筛选与导出**：支持按 `service_name`、`ip`、`port_id`、`product`、`version`、`sources`（`nmap` | `npoc`）筛选（向下兼容 `service_info.*`、`host`、`port`、`scheme` 参数）；`GET /api/service/export/` 与 `GET /api/asset_service/export/` 支持按相同筛选条件导出去重后的 `scheme://ip:port` 文本清单。

### 资产级联删除与派生重算约定

平台 26 个维度删除接口（13 个无前缀 `/api/<dim>/delete/`，含 `POST /api/stat_finger/delete/`；13 个前缀 `/api/asset_<dim>/delete/`）共用统一的层级级联、作用域隔离与派生集合重算规则：

- **批量上限与参数校验**：单次删除请求最多接受 **500** 项待删标识（`_id` / `name` / CIDR），空列表、非法 ID 或超过上限统一返回错误码 `400`。`GET /api/stat_finger/` 与 `GET /api/asset_stat_finger/` 的返回项均包含 `"_id"` 字段（与指纹 `name` 等值），删除时支持传入 `_id` 或 `name`；`POST /api/cip/delete/` 与 `POST /api/asset_cip/delete/` 同时接受 24 位 ObjectId 与 CIDR 字符串。
- **作用域隔离（`source_type`）**：
  - **资产组视图（`/api/asset_<dim>/delete/`）**：支持传入 `scope_id`，仅清理该资产组 `asset_*` 台账及显式绑定至该组的任务（`scope_id`、`sync_scope_id`、`synced_scope_id`、`options.scope_id`、`options.related_scope_id`、`options.scheduler_id`）内的对应记录，不影响其他存活资产组或未绑定该组的独立扫描任务。
  - **任务与全局视图（`/api/<dim>/delete/`）**：支持可选字段 `task_id` 与 `source_type`（可选 `"task"` 或 `"global"`，缺省为 `"task"`）。`source_type: "task"` 时仅作用于对应任务（若任务已显式绑定资产组，则同步清理所属资产组及关联绑定任务）；仅当显式传入 `source_type: "global"` 时，才执行跨资产组、跨任务的全局级联清理。
- **层级级联与派生重算**：
  - 根实体删除自动向下清理关联记录（例如删域名级联清理同域站点、URL、文件泄露、漏洞、Nuclei、WIH 与不再被其他存活域名或网段配置引用的孤儿 IP；删 IP 解除 `domain.ips` 关联但保留域名文档；删服务仅精准剥离该记录所含 `(service_name, ip, port_id)` 端点而不误删同服务名下的其他 IP；删指纹统计仅从宿主站点 `finger` 数组中剥离对应指纹标签而保留站点本身）。
  - 删除完成后自动从存活主表重算受影响范围的派生集合（`cip` / `asset_cip`、`stat_finger` / `asset_stat_finger`、`service` / `asset_service`），校准受影响任务的 `statistic` 计数，并失效跨进程仪表盘与监控缓存。
- **资产组与持续监控联动**：
  - 删除资产组（`POST /api/asset_scope/delete/`）或移除范围目标（`GET /api/asset_scope/delete/`、`POST /api/asset_scope/update/`）同步清理该组 13 个 `asset_*` 集合、关联监控计划及显式绑定任务；若资产组存在进行中的企业测绘更新任务（`updating_icp_task_id`），将先尝试终止并解除 `icp_task` 的 `synced_scope_id`/`synced_scope_name` 绑定（保留 `icp_task` 与 `icp_asset` 原始记录）。资产组改名时同步刷新默认命名的 `scheduler.name`、`icp_task.synced_scope_name` 及绑定任务中的资产组名称字段。
  - 暂停或删除持续监控计划（`POST /api/scheduler/stop/`、`POST /api/scheduler/stop/batch`、`POST /api/scheduler/delete/`）会同步终止该计划派生的进行中与排队中监控任务（暂停时将 `next_run_date` 置为 `"-"`）并刷新 `asset_scope.domain_status`，历史已完成任务与已入库资产保持保留；`GET /api/scheduler/` 返回列表项时自动关联 `asset_scope` 补齐可读的 `scope_name` 字段。

### 资产列表 HTTP 状态码多选筛选

全局资产搜索、任务详情和资产组详情中的站点、URL、文件泄露列表支持状态码多选，选择或清除后立即生效。同一字段的多个状态码按 OR 匹配，与其他条件及 `task_id` / `scope_id` 按 AND 组合；列表查询、导出接口以及站点结果集共用筛选参数规范：

- **站点接口**（`/api/site/`、`/api/asset_site/`）：使用 `status__in=200,301,403`。
- **URL 与文件泄露接口**（`/api/url/`、`/api/asset_url/`、`/api/fileleak/`、`/api/asset_fileleak/`）：使用 `status_code__in=200,403`。
- **参数格式与约束**：参数为逗号分隔的字符串，单项仅接受 100 到 599 的整数状态码，最多支持 500 项；空字符串、无效值或重复参数均返回 HTTP 400 业务错误。若需清除筛选，直接省略该参数即可。
- **向下兼容性**：原有单值标量参数（`status=200`、`status_code=200`）保持兼容；若同时传入单值与多选参数，系统将自动取二者的交集。任务自身运行状态的过滤不受影响，保持原格式。

> [!NOTE]
> - 示例：`GET /api/site/?task_id=<task_id>&status__in=200,403` 查询该任务中状态码为 200 或 403 的站点。相同参数亦完全适用于 `/api/site/export/` 导出及 `/api/site/save_result_set/` 结果集保存接口；按资产组检索时只需将查询参数替换为 `scope_id` 并访问 `/api/asset_site/`。
> - 当前接口实现仅支持针对状态码字段的枚举匹配与字段间 AND 组合，暂不支持自由输入布尔表达式或跨任意字段的 OR 逻辑。

### 12 维资产发现时间、更新时间筛选与排序

任务集合（`site`、`domain`、`ip`、`cert`、`service`、`fileleak`、`url`、`cip`、`stat_finger`、`wih`、`vuln`、`nuclei_result` 及兼容表 `npoc_service`）与对应资产组集合（`asset_*`）统一将发现时间 `save_date`（以及资产组表的更新时间 `update_date`）以服务器本地时区 BSON `datetime` 持久化，并在响应中序列化为 `YYYY-MM-DD HH:MM:SS` 字符串：

- **时间范围筛选（闭区间）**：
  - 全部 12 维任务接口与资产组接口均支持 `save_date__dgt`（发现时间 ≥）与 `save_date__dlt`（发现时间 ≤）；
  - 全部 12 维资产组接口（`/api/asset_*/`）同时支持 `update_date__dgt`（更新时间 ≥）与 `update_date__dlt`（更新时间 ≤）；
  - 参数格式支持 `YYYY-MM-DD HH:MM:SS` 或 `YYYY-MM-DD`（仅传日期时，下界自动按 `00:00:00` 解析，上界按 `23:59:59` 解析）。
- **服务端排序**：全部列表接口均支持 `order=-save_date`（按发现时间倒序）与 `order=+save_date`（按发现时间正序）；不传 `order` 时保持各维度默认排序（普通维度按 `_id` 倒序，`cip`/`asset_cip` 按 IP+域名数降序，`stat_finger`/`asset_stat_finger` 按命中数降序）。
- **跨任务聚合口径**：全局资产搜索中按端点/网段/指纹跨任务归并的 `GET /api/service/`、`GET /api/cip/` 与 `GET /api/stat_finger/`，严格以最早记录（`$min`）作为 `save_date`（首次发现时间），以最近观测（`$max`）作为 `update_date`（最近出现时间），且 `save_date__dgt`/`save_date__dlt` 过滤作用于归并后的首次发现时间，确保列表与总数口径一致。
- **同步入组与导出**：任务资产首次同步至资产组时，`asset_*` 沿用任务记录的原始 `save_date`，并将 `update_date` 对齐该值，仅在后续复扫或监控刷新时推进 `update_date`。文本清单导出（`.txt`）保持原单目标格式不变，证书 JSON 导出（`/api/cert/export/`、`/api/asset_cert/export/`）同步包含 `save_date` 与 `update_date` 字段。

---

## 5. 错误码约定与客户端分支建议

| 错误码 | 含义 | 典型场景 |
| :--- | :--- | :--- |
| `200` | 业务成功 | 所有成功响应 |
| `104` | 任务进行中 | 删除/操作进行中任务时返回，需先停止任务 |
| `999` | 参数校验错误 | 参数缺失、格式非法或超出上限（如资产组 ID 列表为空或单次超过 500 个、无效的资产组/集团 ID 等） |

> [!NOTE]
> - `999` 为通用的参数校验错误码，具体原因请读取响应中的 `message` 与 `data.error` 字段。
> - 客户端在 `switch/if` 分支中应保留 `default` 兜底分支，避免因未枚举的错误码导致静默失败。
> - 错误码在任务类接口与企业任务接口间尚未完全统一（例如企业任务删除在活跃状态下可能返回 `400`），对接时请以 `/api/doc` 与实测响应为准。

### WIH 接口请求与响应详情

任务详情、全局资产搜索和资产组详情的 WIH 列表中，`record_type=api_endpoint` 的记录提供接口详情入口。三个页面复用同一抽屉，展示列表已返回的 `api_request` 和 `api_request.probe`，打开详情不会请求目标接口，也不会触发截图或主动复测。

- 请求信息保留原始路径、补全 URL、方法、所属站点、脚本来源、调用方式及脚本内行号。
- 未采集、已收到 HTTP 响应、请求失败和已跳过分别展示；401、403、404、5xx 仍按实际 HTTP 观测显示，不判定为接口有效、无需认证或存在漏洞。
- 最后收到响应的地址与最近尝试地址分别展示，保留重定向链、停止原因、失败信息、采集时间和耗时；后续跳转失败不能证明最终地址可达。
- 响应头和正文摘要按纯文本显示，可复制已保存的内容，不执行 HTML 或脚本。截断、正文读取失败、空正文、HEAD 及未采集的响应类型分别提示；复制摘要不会补取完整正文。
- 历史记录缺少结构化信息时保留原始内容和来源，不推断方法或可达性。切换任务、资产组、页签或离开页面时关闭详情，避免混淆记录归属。界面文案随中、英、俄语言设置更新，原始响应及来源保持原值。

列表查询、筛选、计数、导出、删除权限及扫描流程沿用原有行为，新增详情不要求迁移历史记录。

---

## 6. MCP 协议端点约定 (Model Context Protocol)

ARL-Next 集成了 Model Context Protocol (MCP 2024-11-05 规范)，支持 AI 协同分析与外部智能体对接。系统提供**远程原生 SSE** 与 **本地 Stdio 桥接** 双模支持。

> [!NOTE]
> 详细的渗透测试实战用例体系与全维可观测性验证方案参见 [MCP 渗透测试实战用例体系](./MCP_PENTEST_TEST_CASES.md)。配套自动化测试套件位于 [verify_mcp_pentest.py](../tools/verify_mcp_pentest.py)。

### 端点清单

| 访问路径 | 协议与动词 | 说明 | 鉴权通道 |
| :--- | :--- | :--- | :--- |
| `/mcp/sse` | HTTP GET (`text/event-stream`) | 远程 MCP SSE 握手端点，维持长连接并推送 `endpoint` 与消息事件 | `Authorization: Bearer <TOKEN>`、`Token: <TOKEN>` 或 `?token=<TOKEN>` |
| `/mcp/message` | HTTP POST (`application/json`) | 远程 MCP 消息上行端点，接收 JSON-RPC 2.0 请求（需携带 `?sessionId=`） | 同上 |
| `/api/mcp/tools` | HTTP GET (`application/json`) | 按当前凭据 Scope 与全局开关交集返回可用 MCP 工具列表与参数 Schema | `Token: <TOKEN>` 或 `Authorization: Bearer <TOKEN>` |
| `/api/mcp/asset_profile` | HTTP GET (`application/json`) | 原生多维资产画像聚合接口，跨集合提取网络/Web/证书/漏洞/泄露情报 | `Token: <TOKEN>` 或 `Authorization: Bearer <TOKEN>` |
| `/api/mcp/enterprise_profile` | HTTP GET (`application/json`) | 原生企业生态资产画像聚合接口，自适应解析企业、提供概览统计与分维度下钻 | `Token: <TOKEN>` 或 `Authorization: Bearer <TOKEN>` |
| `/api/mcp/search_assets` | HTTP GET (`application/json`) | 多维资产条件检索接口（支持 `site`/`domain`/`ip`/`vuln`，受 `max_search_limit` 约束） | `Token: <TOKEN>` 或 `Authorization: Bearer <TOKEN>` |
| `/api/mcp/task_status` | HTTP GET (`application/json`) | 查询指定 24 位扫描任务执行进度、状态与资产发现统计摘要 | `Token: <TOKEN>` 或 `Authorization: Bearer <TOKEN>` |
| `/api/mcp/create_scan_task` | HTTP POST (`application/json`) | 受控创建资产扫描任务（需 `task:dispatch` Scope 且全局工具开关启用） | `Token: <TOKEN>` 或 `Authorization: Bearer <TOKEN>` |
| `/api/mcp/stop_scan_task` | HTTP POST (`application/json`) | 受控终止排队中或进行中的资产扫描任务（需 `task:dispatch` Scope 且全局工具开关启用） | `Token: <TOKEN>` 或 `Authorization: Bearer <TOKEN>` |
| `/api/mcp/export_server` | HTTP GET / POST (`text/x-python`) | 导出客户端脚本；专用 Key 使用 POST JSON 的 `raw_key`，GET 仅使用当前登录凭据 | 登录 Token 或系统 API Key |
| `/api/mcp/task_detail_export`| HTTP GET (`text/csv`) | 任务详情分维度安全 CSV 数据导出（内置公式注入防御） | `Token: <TOKEN>` |
| `/api/mcp/overview` | HTTP GET (`application/json`) | MCP 治理中心大盘与调用统计概览（调用量、活跃 Key、异常数、SSE 实时连通探活 `sse_status`/`sse_sessions`） | `Token: <TOKEN>` |
| `/api/mcp/keys` | HTTP GET / POST (`application/json`) | MCP 专用 API Key 列表查询（支持 `keyword` 与 `status`: active/expired/revoked 筛选及 `is_expired` 状态计算）与签发 | `Token: <TOKEN>` |
| `/api/mcp/logs` | HTTP GET (`application/json`) | MCP 调用审计日志分页查询（支持 `time_range`：today/24h/7d，`status`：success/error/denied/abnormal） | `Token: <TOKEN>` |
| `/api/mcp/logs/export` | HTTP GET (`text/csv`) | 导出符合筛选条件的审计日志 CSV 文件 | `Token: <TOKEN>` |
| `/api/mcp/config` | HTTP GET / POST (`application/json`) | 获取与保存 MCP 全局工具开关与频控配额策略 | `Token: <TOKEN>` |

### 渐进式工具集规范

| 工具名称 | 类别 | 核心入参 | 功能说明 | 启用条件 |
| :--- | :--- | :--- | :--- | :--- |
| `get_asset_profile` | 只读画像 | `target` (必填), `task_id` (可选) | 综合资产情报关联（IP/端口/服务/Web指纹/证书/漏洞/泄露） | 默认启用 |
| `get_enterprise_profile` | 只读画像 | `target` (必填), `category`, `page`, `size`, `task_id` | 企业全景生态资产画像与组织架构（工商背景、ICP备案、APP、小程序、快应用、公众号、微博、投资关系） | 默认启用 |
| `search_assets` | 只读检索 | `query` (必填), `asset_type`, `limit` | 依条件检索站点、IP、域名或已知漏洞记录 | 默认启用 |
| `get_task_status` | 只读状态 | `task_id` (必填) | 查询任务执行状态、进度与统计数据 | 默认启用 |
| `create_scan_task` | 受控调度 | `name`, `target`, `policy_id` | 通过标准目标校验与轻重队列投递扫描任务 | 管理台启用工具且 Key 具有 `task:dispatch` |
| `stop_scan_task` | 受控调度 | `task_id` (必填) | 撤销 Celery 任务并记录停止状态 | 管理台启用工具且 Key 具有 `task:dispatch` |

- `tools/list` 和执行入口使用相同的全局开关及 Key Scope。数据库中的显式开关优先；没有保存开关时，`ARL_MCP_ENABLE_DISPATCH` 作为写工具的默认值。
- SSE 每条上行消息重新校验握手凭据；吊销、删除、到期或轮换凭据后，旧 `sessionId` 不能继续调用。显式请求头必须与握手凭据一致。有效期统一按 UTC 判断。
- Stdio 专用 Key 可通过 `/api/mcp/tools` 动态发现可用工具，并按 Scope 与全局开关访问对应工具端点（只读 `asset:read` 对应 `/api/mcp/asset_profile`、`/api/mcp/enterprise_profile`、`/api/mcp/search_assets`、`/api/mcp/task_status`；受控调度 `task:dispatch` 对应 `/api/mcp/create_scan_task`、`/api/mcp/stop_scan_task`），不具备其他管理 REST 接口权限。SSE 和上述 6 个 REST 工具端点共用每个凭据的固定分钟限额；被权限或开关拒绝的调用同样计入限额；超限返回 HTTP `429` 和 `Retry-After`，每分钟仅记录首次超限审计，配额存储不可用时返回 `503`。
- 管理台生成配置需要完整 Key。新建 Key 的明文仅保留在当前页面；再次打开页面时需粘贴先前保存的完整值，不能使用列表中的脱敏前缀。导出脚本使用 `POST /api/mcp/export_server`，JSON 为 `{"host":"https://arl.example","raw_key":"<完整 MCP Key>"}`；账号凭据仍放在 `Token` 请求头。GET 不接受 `raw_key`。
- `create_scan_task` 对混合目标可能创建多个任务，响应通过 `task_ids` 返回全部 ID，兼容字段 `task_id` 为第一个 ID。策略绑定的资产范围仍在提交前统一校验。

> [!NOTE]
> - 生产反向代理已针对 `/mcp/sse` 配置专用流式转发（禁用缓冲、长连接保活 24 小时）；
> - 经 IP 访问自签证书部署时，客户端若因 TLS 校验阻断直连，推荐使用本地 Stdio 脚本接入（已内置证书自适应），或将服务端 CA 证书导入系统信任库。

- MCP Scope、有效期和工具开关拒绝非法输入；局部策略更新保留未提交的开关。搜索条件按文字匹配，列表分页限制为 1–100 条。
- MCP 请求体最大 16 MiB；每个会话最多 16 个在途请求、服务最多 64 个。请求在发出 202 前进入处理队列，断连后已接收的执行仍计入容量，无法投递的回复有超时清理。

## 7. 备份恢复时的任务处理

恢复先校验完整归档，再暂停扫描队列消费并检查 Worker、运行任务和排队任务。存在未完成任务时需要 `force=true`；强制恢复会撤销运行、预取、定时和排队任务，并等待 Worker 确认停止后才执行 `mongorestore --drop`。恢复期间队列保持暂停，恢复前数据对应的剩余消息在恢复后清理，未完成任务状态置为已停止，再恢复消费。

Worker 不可达、控制指令没有完整确认或停止超时，均中止恢复。数据库覆盖已经开始后若恢复失败，队列保持暂停；管理员应先检查数据和恢复错误，确认后再重启 Worker。Web 与 CLI 都使用此检查，需要可响应控制指令的 Worker 和消息队列。

`running_tasks` 统计扫描与 GitHub 任务中的未完成项，包含排队中的任务。

- 恢复前除 Celery 确认外，还核对 broker 消费者为零、原任务子进程已退出；无法确认时不执行数据库覆盖。备份与恢复共用持久目录内的跨进程操作锁。
- `force` 必须为 JSON 布尔值，字符串 `"false"` 不被接受；未结束的企业测绘任务不能由 Celery 强制恢复中断，必须先结束这些任务。
- 恢复须在维护窗口暂停外部数据库写入、任务提交和计划调度。本流程不代替对外部写入者的维护隔离，也不保证在节点重启或网络分区下的分布式一致性。

## 8. 系统代理池与三域分流治理

代理节点池、三域流量策略（`osint` / `scan` / `intel`）与旁路白名单统一持久化在 `system_config`（`_id: "proxy_config"`）中，运行态切换与冷却状态由 `_id: "proxy_runtime_status"` 维护；所有代理治理接口均需携带管理员 `Token` 请求头。

| 方法 | 路径 | 用途 |
| :--- | :--- | :--- |
| `GET` | `/api/system_config/proxy` | 读取节点池配置（`password` 置空、`has_password` + 掩码 `display_url`）、`osint` 运行态及能力清单（`pysocks_installed`、`protocols`、`presets`） |
| `POST` | `/api/system_config/proxy/nodes` | 新增代理节点（`protocol` 支持 `http` / `https` / `socks5` / `socks5h`，端口 `1–65535`） |
| `PUT` | `/api/system_config/proxy/nodes/<node_id>` | 更新节点信息；未传入新密码时保留原密码，传入 `clear_password: true` 可清除密码 |
| `DELETE` | `/api/system_config/proxy/nodes/<node_id>` | 删除节点并从三域绑定中自动摘除；失去可用节点且无直连兜底的域将平滑回退为 `direct_only` |
| `PUT` | `/api/system_config/proxy/policies` | 增量更新 `policies`（`osint` / `scan` / `intel`）与 `bypass`（`bypass_private_cidr`、`bypass_domestic_webhooks`、`custom_no_proxy`） |
| `POST` | `/api/system_config/proxy/probe` | 基于固定安全白名单预设探测节点连通性（禁止自定义外部 URL 以防 SSRF） |
| `POST` | `/api/system_config/proxy/cooldown/reset` | 手动重置 `osint` 出口冷却状态并通知 `osint-service`，返回 `osint_notified` 与最新 `runtime` |

- **分流模式与域级开关**：支持 `direct_only`、`failover`、`round_robin`、`fixed_proxy`。其中 `osint.cooldown_sec` 取值范围限制为 `30–3600` 秒（默认 `300`）；`scan` 域另提供 `apply_to_nuclei`、`apply_to_npoc`、`apply_to_puppeteer` 开关。
- **探针预设枚举**：`POST /api/system_config/proxy/probe` 的 `preset` 仅接受 `egress_ip`、`miit`、`tianyancha`、`github`；其中 `miit` 预设将无创宇盾 WAF 拦截特征的 HTTP `521` 挑战视为连通可用（未阻断）。
- **关联状态与兼容约束**：
  - `GET /api/dashboard/sysinfo`（`data.proxy`）与 `GET /api/icp/tyc_check`（`data.proxy_status`）均复用同一 `runtime` 运行态势模型，核心 `state` 枚举为 `direct_ok`、`backup_active`、`proxy_active`、`degraded_blocked`、`proxy_unavailable`。
  - 当 `scan` 域启用 `apply_to_puppeteer` 且绑定了含账号密码的代理节点时，由于 Chromium `--proxy-server` 原生不支持带鉴权代理，Puppeteer 会自动降级直连并在 `runtime.puppeteer_compat_warning` 中返回提示。
  - 旧版 `POST /api/system_config/general` 传入 `proxy_url` 时仍会兼容同步至 `legacy-default` 节点。

## 9. GitHub 监控与泄露研判接口

代码泄露命中统一按文件指纹（`hash_md5`）跨单次任务（`github_result`）与周期策略（`github_monitor_result`）合并去重，研判状态持久化于 `github_triage`，屏蔽仓库持久化于 `github_ignored_repo`；以下接口均需携带管理员 `Token` 请求头。

| 方法 | 路径 | 用途 |
| :--- | :--- | :--- |
| `GET` | `/api/github_result/overview/` | 分页查询跨任务去重后的代码泄露命中；支持 `source_type`（`all`/`task`/`scheduler`）、`triage_status`、`group_by`（`flat`/`repo`）、`only_ignored` 与关键词筛选 |
| `GET` | `/api/github_result/stats/` | 获取去重后的研判口径统计（`pending`、`confirmed`、`false_positive`、`total`、`ignored_repos`、`running_tasks`、`running_schedulers`） |
| `POST` | `/api/github_result/triage/` | 按 `hash_md5s` 批量更新研判状态（`pending` / `confirmed` / `false_positive`）与备注 `note`，同步回写存量结果并供后续任务自动继承 |
| `GET` / `POST` | `/api/github_result/ignored_repos/` | 读取、新增或移出噪声仓库屏蔽列表（`action`: `add` / `remove`，`repo_full_names`）；已屏蔽仓库默认从待研判视图隐去且不触发周期告警推送 |
| `GET` | `/api/github_result/export/` | 按当前筛选条件导出去重命中结果（`format`: `csv` / `json`，单次上限 50,000 条，CSV 对公式前缀做字面转义） |
| `POST` | `/api/github_scheduler/run/` | 传入 `_id` 列表，立即触发指定周期监控策略执行一次 |
| `GET` | `/api/github_threat/token_status` | 经 `intel` 代理域探测 GitHub API 连通性与双维度额度（同时返回 `core` 与 `search` 剩余限额） |
| `GET` | `/api/github_threat/hackers_history` | 查询监控研究员开源工具发现记录，支持可选 `github_id` 与 `q`（仓库名/简介/语言）过滤 |

- **仪表盘统计口径同步**：`GET /api/dashboard/stats` 中的 `github_monitors` 统计 `github_scheduler` 集合记录数；`POST /api/github_threat/tools_target` 与 `POST /api/github_threat/hackers_target` 均同时兼容单条提交与批量数组（`repo_urls` / `github_ids`）。

## 10. 消息推送与 Nuclei 漏洞告警回调

全局推送配置通过 `GET` / `POST /api/system_config/general` 读写（需管理员 `Token` 请求头），覆盖钉钉、飞书、企业微信、Telegram、SMTP 邮件及全局 Webhook 回调六类通道。

| 字段 | 类型 | 说明 |
| :--- | :--- | :--- |
| `push_options` | `string[]` | 订阅事件列表，新增 `nuclei_vuln`（Nuclei 漏洞告警）；存量环境启动迁移时默认自动补齐并尊重后续手动取消 |
| `nuclei_push_severities` | `string[]` | Nuclei 告警严重等级白名单，可选 `critical`、`high`、`medium`、`low`、`info`，默认 `["critical", "high", "medium", "low"]` |

- **触发时机与去重边界**：
  - 常规域名/IP 扫描、风险巡航（`RiskCruising`）、添加资产站点与资产组监控任务均在全部扫描阶段与资产同步完成后（任务处于 `done` 且写入 `end_time`）统一触发推送；单任务聚合发送 1 条告警，按严重等级排序并展示前 20 条明细（企业微信通道按 2,000 UTF-8 字节边界安全截断）。
  - 关联资产组或监控任务仅推送首次新发现且尚不存在于 `asset_nuclei_result` 的漏洞；未关联资产组的独立任务推送本次任务的全部匹配结果。手动同步（`POST /api/task/sync/`）与模板在线调试（`POST /api/nuclei/template/test/`）不触发推送。
- **全局 Webhook `nuclei_vuln` 载荷格式**：当配置 `webhook_url` 且订阅 `nuclei_vuln` 并命中等级过滤条件时，向 `webhook_url` 发送 `POST` 请求（配置 `webhook_token` 时附带请求头 `Token: <webhook_token>`）：

```json
{
  "type": "nuclei_vuln",
  "task_id": "65f0...",
  "task_data": {
    "name": "example.com",
    "target": "https://arl.example.com",
    "type": "domain",
    "task_tag": "task",
    "start_time": "2026-11-18 20:00:00",
    "status": "done",
    "end_time": "2026-11-18 20:05:00"
  },
  "scope_id": "65f1...",
  "scope_data": { "name": "核心资产组", "scope_type": "domain" },
  "summary": {
    "total": 1,
    "truncated": false,
    "severity_counts": { "critical": 0, "high": 1, "medium": 0, "low": 0, "info": 0 }
  },
  "nuclei_results": [
    {
      "template_id": "CVE-2026-0001",
      "template_source": "community",
      "vuln_name": "Example Vulnerability",
      "vuln_severity": "high",
      "vuln_url": "https://arl.example.com/probe",
      "target": "https://arl.example.com",
      "host": "https://arl.example.com"
    }
  ]
}
```

> 单次 Webhook 回调中 `nuclei_results` 最多携带 100 条明细，超出时 `summary.truncated` 为 `true`。

## 11. Nuclei 自建模板管理与在线单目标即时调试

自建模板生命周期与在线调试通过 `/api/nuclei/template/*` 端点管理（需携带有效 `Token` 请求头）：

| 端点 | 方法 | 说明 |
| :--- | :--- | :--- |
| `/api/nuclei/template/create/` | `POST` | 新建自建 YAML 模板，接收 `content`（必填）与 `enable`（可选布尔值，默认 `true`），返回 `template_id` 与 `enable` |
| `/api/nuclei/template/update/` | `POST` | 更新已有自建模板，接收 `template_id` 与 `content`；支持在 YAML 中修改 `id` 完成重命名（与存量冲突时返回 `code: 999`） |
| `/api/nuclei/template/import/` | `POST` | 批量导入 `.yaml` / `.yml` 或 `.zip` 模板；先完成静态校验，再批量调用 `nuclei -duc -no-color -validate` 语义校验（失败条目写入 `fail_details` 且不落库） |
| `/api/nuclei/template/test/` | `POST` | 在线单目标即时调试（Dry Run），限时 30 秒执行；接收 `target`（必填）与 `content`（或已入库的 `template_id`） |

- **模板静态与语义校验契约**：
  - `create` / `update` / `import` 强制校验顶层 YAML 映射、`id`（仅限 `a-zA-Z0-9_.-`）、`info.name`、`info.author`（字符串或非空字符串列表）、`info.severity` 白名单（`info` / `low` / `medium` / `high` / `critical` / `unknown`）及至少一个非空协议/工作流块（`http`、`requests`、`dns`、`tcp`、`network`、`ssl`、`websocket`、`whois`、`code`、`javascript`、`headless`、`file`、`workflows`）。
  - 当运行环境检测到 `nuclei` 二进制时，额外执行 `nuclei -duc -no-color -validate` 深度语义校验（缺失二进制时自动降级为静态校验）；`create` / `update` 校验失败或 `template_id` 重复均返回 `code: 999` 与明确提示，`import` 校验失败条目被拒收并汇总至 `fail_details`。
- **在线单目标即时调试（`POST /api/nuclei/template/test/`）规范**：
  - **目标协议自适应与防注入**：拒绝空白符、换行/控制字符及以 `-` 开头的目标输入；对 `http` / `headless` 自动补齐 `http://`（`websocket` 保留 `ws(s)://` / `http(s)://`），对 `dns` / `tcp` / `network` / `ssl` / `whois` 自动剥离多余的 `http(s)://` 前缀与路径段。
  - **代理与输出清洗**：复用全局 `scan` 域代理策略（`apply_to_nuclei`）并在日志与回显中对代理凭据脱敏；移除终端 ANSI 颜色转义序列并优先基于 `-jle` 解析结构化命中（旧版引擎自动回退无 ANSI 文本行判定）。
  - **响应字段**：成功（`code: 200`）时 `data` 包含 `matched`、`matched_count`、`findings`（每项含 `template_id`、`name`、`severity`、`matched_at`、`curl_command`、`extracted_results`）、`target`、`output`、`returncode`、`cost_seconds`；当 `nuclei` 退出码非 0 时返回 `code: 999`，`message` 给出核心错误摘要，`data.output` 与 `data.returncode` 仍保留完整诊断日志。
- **ASM 任务通道隔离与按协议分流**：
  - `nuclei_config`（可用于 `POST /api/task/`、`POST /api/policy/add/`、`POST /api/policy/edit/`）支持字段：`include_community`（布尔值，默认 `true`；设为 `false` 可仅运行自建模板）、`severity`（社区通道等级过滤，默认 `["low","medium","high","critical"]`）、`exclude_blacklist`（布尔值，默认 `true`，仅作用于社区通道）、`custom_template_mode`（`all_enabled` / `selected` / `tags` / `none`）、`selected_custom_templates`、`selected_tags`、`extra_exclude_ids`。
  - 社区模板通道保持 `-tags cve,http`、策略 `severity` 与全局黑名单 `-eid` 约束；自建模板通道不受社区 `-tags`、`severity` 与全局黑名单限制（含 `info`/`unknown` 级别均执行），并按协议自动分流投喂 ASM 资产：`http`/`websocket` 扫描存活 Web 站点（含 WIH 衍生站点），`tcp`/`network`/`ssl`/`javascript` 额外投喂开放端口 `ip:port`，`dns`/`whois` 额外投喂发现的子域名；`code`/`headless`/`file`/`workflows` 协议当前仅支持单目标调试，ASM 任务执行前自动跳过并记录告警日志。
  - 双通道与分桶执行相互隔离：单通道异常不会丢弃其余已成功通道的命中结果；无可执行模板或无匹配目标时安全跳过。
  - 命中结果写入 `template_source`（`custom` / `community`），`GET /api/nuclei_result/` 与 `GET /api/asset_nuclei_result/` 均支持按 `template_source` 筛选；`POST /api/task/policy/` 支持可选字段 `related_scope_id`，用于资产组风险巡航任务完成后将命中结果同步回 `asset_nuclei_result` / `asset_vuln`。
