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
| **删除任务** | `POST /api/task/delete/` | JSON：`{"task_id": ["<task_id>"], "del_task_data": false}` | ⚠️ **前置条件约束**：仅允许删除处于 `done`、`stop` 或 `error` 结束态的任务；运行中任务将返回错误码 `104`（“任务运行中”） |
| **重启任务** | `POST /api/task/restart/` | JSON：`{"task_id": ["<task_id>"]}` | 仅允许重启已结束的任务 |

### 新建任务关联资产组

新建资产侦查任务时，可选择一个已有资产组，也可保持不关联。资产组选项支持名称搜索和分页加载；选择后，任务完成会通过现有资产同步流程将结果同步到该组，不创建周期监控，也不自动扩展资产组范围。

`POST /api/task/` 新增可选 JSON 字段 `related_scope_id`，例如：

```json
{"name": "边界资产探测", "target": "www.example.com", "related_scope_id": "<asset_scope_id>"}
```

后端在批量创建任务之前检查资产组是否存在，以及所有域名、IP 或 CIDR 目标是否属于该组；保留系统原有目标和黑名单校验。不传该字段时沿用原普通扫描行为。重启关联任务时保留组 ID，重新校验当前范围，并清除新任务的旧同步状态。

任务列表的资产组列区分完成后同步、等待同步、同步中、已同步和同步失败；失败原因在提示中展示。扫描结果与同步状态独立保留，选择了资产组不代表已经同步成功。同步前再次检查组是否存在及任务目标范围；组被删除或范围改变时不继续同步。

`POST /api/task/sync/` 支持已结束的域名和 IP 任务，参数为 `task_id`、`scope_id`；仍需完整范围校验。同步任务派发前记录等待状态，派发失败记录原因。自动同步和手动同步成功后记录 `synced_scope_id` / `synced_scope_name`，失败时记录 `sync_error`，不自动重试。

任务创建支持按资产组圈定范围；Nuclei YAML/ZIP 导入由 PoC 管理页提供，此处不再重复实现。

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

### 全局维度计数接口

`GET /api/asset_overview/count` 一次性返回上述各资产维度的**全库总量**，用于客户端渲染维度页签的数量徽标，避免为每个维度单独发起一次计数请求。

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
> - 该接口返回的是**全局聚合口径**，与按 `task_id` / `scope_id` 过滤的列表接口**不是同一统计范围**，不可用于推导单个任务或单个资产组的资产量；
> - 各维度计数口径与其对应列表接口保持一致，例如 `cip` 统计去重后的 C 段数、`stat_finger` 统计去重后的指纹名数量，而非底层集合文档数；
> - 单个维度计数失败时该字段返回 `null`，客户端应视为「未知」并避免渲染为 `0`。

### 资产列表 HTTP 状态码多选筛选

全局资产搜索、任务详情和资产组详情中的站点、URL、文件泄露列表支持状态码多选，选择或清除后立即生效。同一字段的多个状态码按 OR 匹配，与其他条件及 `task_id` / `scope_id` 按 AND 组合；列表查询、导出接口以及站点结果集共用筛选参数规范：

- **站点接口**（`/api/site/`、`/api/asset_site/`）：使用 `status__in=200,301,403`。
- **URL 与文件泄露接口**（`/api/url/`、`/api/asset_url/`、`/api/fileleak/`、`/api/asset_fileleak/`）：使用 `status_code__in=200,403`。
- **参数格式与约束**：参数为逗号分隔的字符串，单项仅接受 100 到 599 的整数状态码，最多支持 500 项；空字符串、无效值或重复参数均返回 HTTP 400 业务错误。若需清除筛选，直接省略该参数即可。
- **向下兼容性**：原有单值标量参数（`status=200`、`status_code=200`）保持兼容；若同时传入单值与多选参数，系统将自动取二者的交集。任务自身运行状态的过滤不受影响，保持原格式。

> [!NOTE]
> - 示例：`GET /api/site/?task_id=<task_id>&status__in=200,403` 查询该任务中状态码为 200 或 403 的站点。相同参数亦完全适用于 `/api/site/export/` 导出及 `/api/site/save_result_set/` 结果集保存接口；按资产组检索时只需将查询参数替换为 `scope_id` 并访问 `/api/asset_site/`。
> - 当前接口实现仅支持针对状态码字段的枚举匹配与字段间 AND 组合，暂不支持自由输入布尔表达式或跨任意字段的 OR 逻辑。

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
> 详细的渗透测试实战用例体系与全维可观测性验证方案参见 [MCP 渗透测试实战用例体系](./MCP_PENTEST_TEST_CASES.md)。配套自动化测试套件位于 [verify_mcp_pentest.py](file:///Users/sienchen/Documents/github_project/ARL-Next/tools/verify_mcp_pentest.py)。

### 端点清单

| 访问路径 | 协议与动词 | 说明 | 鉴权通道 |
| :--- | :--- | :--- | :--- |
| `/mcp/sse` | HTTP GET (`text/event-stream`) | 远程 MCP SSE 握手端点，维持长连接并推送 `endpoint` 与消息事件 | `Authorization: Bearer <TOKEN>`、`Token: <TOKEN>` 或 `?token=<TOKEN>` |
| `/mcp/message` | HTTP POST (`application/json`) | 远程 MCP 消息上行端点，接收 JSON-RPC 2.0 请求（需携带 `?sessionId=`） | 同上 |
| `/api/mcp/asset_profile` | HTTP GET (`application/json`) | 原生多维资产画像聚合接口，跨集合提取网络/Web/证书/漏洞/泄露情报 | `Token: <TOKEN>` |
| `/api/mcp/enterprise_profile` | HTTP GET (`application/json`) | 原生企业生态资产画像聚合接口，自适应解析企业、提供概览统计与分维度下钻 | `Token: <TOKEN>` |
| `/api/mcp/export_server` | HTTP GET / POST (`text/x-python`) | 导出客户端脚本；专用 Key 使用 POST JSON 的 `raw_key`，GET 仅使用当前登录凭据 | 登录 Token 或系统 API Key |
| `/api/mcp/task_detail_export`| HTTP GET (`text/csv`) | 任务详情分维度安全 CSV 数据导出（内置公式注入防御） | `Token: <TOKEN>` |
| `/api/mcp/overview` | HTTP GET (`application/json`) | MCP 治理中心大盘与调用统计概览（调用量、活跃 Key、异常数） | `Token: <TOKEN>` |
| `/api/mcp/keys` | HTTP GET / POST (`application/json`) | MCP 专用 API Key 列表查询与签发（支持细粒度 Scope 授权） | `Token: <TOKEN>` |
| `/api/mcp/logs` | HTTP GET (`application/json`) | MCP 调用审计日志分页查询（支持 `time_range`：today/24h/7d，`status`：success/error/denied/abnormal） | `Token: <TOKEN>` |
| `/api/mcp/logs/export` | HTTP GET (`text/csv`) | 导出符合筛选条件的审计日志 CSV 文件 | `Token: <TOKEN>` |
| `/api/mcp/config` | HTTP GET / POST (`application/json`) | 获取与保存 MCP 全局工具开关与频控配额策略 | `Token: <TOKEN>` |

### 渐进式工具集规范

| 工具名称 | 类别 | 核心入参 | 功能说明 | 启用条件 |
| :--- | :--- | :--- | :--- | :--- |
| `get_asset_profile` | 只读画像 | `target` (必填), `task_id` (可选) | 综合资产情报关联（IP/端口/服务/Web指纹/证书/漏洞/泄露） | 默认启用 |
| `get_enterprise_profile` | 只读画像 | `target` (必填), `category`, `page`, `size`, `task_id` | 企业全景生态资产画像与组织架构（工商背景、ICP备案、APP、小程序、公众号、微博、投资关系） | 默认启用 |
| `search_assets` | 只读检索 | `query` (必填), `asset_type`, `limit` | 依条件检索站点、IP、域名或已知漏洞记录 | 默认启用 |
| `get_task_status` | 只读状态 | `task_id` (必填) | 查询任务执行状态、进度与统计数据 | 默认启用 |
| `create_scan_task` | 受控调度 | `name`, `target`, `policy_id` | 通过标准目标校验与轻重队列投递扫描任务 | 管理台启用工具且 Key 具有 `task:dispatch` |
| `stop_scan_task` | 受控调度 | `task_id` (必填) | 撤销 Celery 任务并记录停止状态 | 管理台启用工具且 Key 具有 `task:dispatch` |

- `tools/list` 和执行入口使用相同的全局开关及 Key Scope。数据库中的显式开关优先；没有保存开关时，`ARL_MCP_ENABLE_DISPATCH` 作为写工具的默认值。
- SSE 每条上行消息重新校验握手凭据；吊销、删除、到期或轮换凭据后，旧 `sessionId` 不能继续调用。显式请求头必须与握手凭据一致。有效期统一按 UTC 判断。
- Stdio 专用 Key 可访问只读 `/api/mcp/asset_profile` 和 `/api/mcp/enterprise_profile`，需要 `asset:read`，不具备其他管理 REST 接口权限。SSE 和两个只读接口共用每个凭据的固定分钟限额；被权限或开关拒绝的调用同样计入限额；超限返回 HTTP `429` 和 `Retry-After`，每分钟仅记录首次超限审计，配额存储不可用时返回 `503`。
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
