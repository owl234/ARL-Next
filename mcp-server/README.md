<div align="center">
  <p>
    <a href="./README_en.md"><b>English</b></a> |
    <b>简体中文</b>
  </p>
</div>

# ARL-Next MCP Server (v2.0)

> **让 AI Agent 原生接入企业级网络资产测绘与漏洞情报能力**<br>
> 遵循 Model Context Protocol (2024-11-05) 标准规范，支持 **Cursor、Claude Desktop、Claude Code、Antigravity、Windsurf** 等全主流客户端。

<p align="center">
  <a href="#cursor"><b>⚡ Cursor 接入</b></a> •
  <a href="#claude-desktop"><b>🖥️ Claude Desktop</b></a> •
  <a href="#claude-code"><b>💻 Claude Code CLI</b></a> •
  <a href="#antigravity-windsurf"><b>🚀 Antigravity / Windsurf</b></a> •
  <a href="#tools"><b>🧩 工具能力与实战</b></a> •
  <a href="#faq"><b>🚨 故障排查与自愈</b></a> •
  <a href="#architecture"><b>⚙️ 架构与进阶</b></a>
</p>

---

## ⚡ 10 秒极速接入（按你的客户端选择）

> [!TIP]
> **💡 最省心的做法**：登录 ARL-Next Web 控制台，点击顶部导航栏右上角 **「MCP」**，弹窗已根据当前访问地址与账号权限预生成完整配置，支持一键复制或一键导出脚本。若手动配置，请直接对号入座复制下方卡片：

### <span id="cursor"></span>1. Cursor

- **配置文件路径**：项目根目录 `.cursor/mcp.json` 或 全局设置（Features ➔ MCP Servers）
- **首选配置：远程直连 (Remote SSE)** *(适用于公网域名或合规证书)*：
  ```json
  {
    "mcpServers": {
      "arl-next": {
        "url": "https://arl.example.com:5173/mcp/sse",
        "headers": {
          "Authorization": "Bearer <从 ARL 控制台复制的 Token>"
        }
      }
    }
  }
  ```
  *(注：若客户端不支持自定义 Headers，可直接使用 `"url": "https://arl.example.com:5173/mcp/sse?token=<Token>"`)*
- **备选配置：私网 IP / 自签证书环境 (Stdio 桥接)** *(自动加载自签证书，规避 Node.js TLS 拦截)*：
  ```json
  {
    "mcpServers": {
      "arl-next": {
        "command": "python3",
        "args": ["/绝对路径/ARL-Next/mcp-server/server.py"],
        "env": {
          "ARL_HOST": "https://192.168.1.100:5173",
          "ARL_TOKEN": "<从 ARL 控制台复制的 Token>"
        }
      }
    }
  }
  ```

---

### <span id="claude-desktop"></span>2. Claude Desktop

- **配置文件路径**：
  - **macOS**：`~/Library/Application Support/Claude/claude_desktop_config.json`
  - **Windows**：`%APPDATA%\Claude\claude_desktop_config.json`
- **首选配置：远程直连 (Remote SSE)**：
  ```json
  {
    "mcpServers": {
      "arl-next": {
        "url": "https://arl.example.com:5173/mcp/sse",
        "headers": {
          "Authorization": "Bearer <从 ARL 控制台复制的 Token>"
        }
      }
    }
  }
  ```
- **备选配置：私网 IP / 自签证书环境 (Stdio 桥接)**：
  ```json
  {
    "mcpServers": {
      "arl-next": {
        "command": "python3",
        "args": ["/绝对路径/ARL-Next/mcp-server/server.py"],
        "env": {
          "ARL_HOST": "https://192.168.1.100:5173",
          "ARL_TOKEN": "<从 ARL 控制台复制的 Token>"
        }
      }
    }
  }
  ```

---

### <span id="claude-code"></span>3. Claude Code CLI

无需创建虚拟环境或下载第三方依赖，在终端中直接执行一行命令完成用户级全局注册：

```bash
claude mcp add -s user arl-next \
  python3 "$(pwd)/mcp-server/server.py" \
  --env ARL_HOST="https://arl.example.com:5173" \
  --env ARL_TOKEN="<从 ARL 控制台或 ARL_auth.md 获取的 Token>"
```

---

### <span id="antigravity-windsurf"></span>4. Antigravity / Windsurf

- **配置文件路径**：
  - **Windsurf**：`~/.codeium/windsurf/mcp_config.json`
  - **Antigravity**：工作区 `.gemini/antigravity-cli/mcp/` 或全局设置
- **配置内容**：与 Cursor 完全一致，将配置填入对应的 `mcpServers` 节点即可立即生效。

---

## <span id="tools"></span>🧩 核心能力与 Agent 交互实战

ARL-Next MCP 注册了 6 项核心标准化工具，默认开启只读情报查询，敏感调度严格受控：

### 1. 工具矩阵清单

| 工具名称 | 核心职责 | 默认权限 | 典型应用场景 |
| :--- | :--- | :--- | :--- |
| `get_asset_profile` | 五维资产画像下钻 | **只读（开放）** | 查询指定域名、IP 或 URL 的端口服务、Web 指纹、证书、历史漏洞及敏感泄露 |
| `get_enterprise_profile` | 企业全景生态画像 | **只读（开放）** | 查询企业组织架构、ICP 备案域名、移动 APP、小程序、公众号、微博及投资控股关系 |
| `search_assets` | 全库条件检索 | **只读（开放）** | 按关键字匹配站点、域名、IP 或漏洞资产 |
| `get_task_status` | 任务状态跟踪 | **只读（开放）** | 查询指定 24 位任务 ID 的实时进度百分比与统计结果 |
| `create_scan_task` | 下发扫描任务 | **受控（需授权开启）** | 驱动 ARL 创建常规资产扫描或风险巡航任务 |
| `stop_scan_task` | 终止扫描任务 | **受控（需授权开启）** | 终止正在排队或执行中的特定任务 |

### 2. 典型 Agent 交互指令示例

在连接 MCP 后，直接在 AI 对话框中用自然语言对 Agent 下达指令：

- **场景一：单资产暴露面深度画像**
  > **💬 提问**：“帮我分析 `target.example.com` 的网络暴露面与已知风险。”<br>
  > **🤖 Agent 动作**：自动调用 `get_asset_profile(target="target.example.com")`，单次获取网络层（开放端口/协议）、应用层（标题/中间件指纹）、证书链及攻防层历史漏洞，输出结构化安全态势摘要。
- **场景二：企业生态资产穿透与暴露面联动**
  > **💬 提问**：“查一下小米有哪些移动 APP 和小程序，主要备案域名是什么？”<br>
  > **🤖 Agent 动作**：自动调用 `get_enterprise_profile(target="小米")` 获取生态画像总览与核心资产样本，按需调用 `get_enterprise_profile(target="小米", category="app")` 下钻明细，并对核心域名调用 `get_asset_profile` 评估暴露风险。
- **场景三：技术栈特征与组件资产排查**
  > **💬 提问**：“检索我们资产库中所有运行 Spring Boot 或 Nginx 的站点。”<br>
  > **🤖 Agent 动作**：自动调用 `search_assets(query="Spring Boot", asset_type="site")`，返回匹配的站点列表、IP 及关联任务。
- **场景四：受控任务创建与进度追踪**
  > **💬 提问**：“对 IP `192.0.2.1` 下发一次常规扫描，并在完成后告诉我资产发现情况。”<br>
  > **🤖 Agent 动作**：调用 `create_scan_task(target="192.0.2.1")` 创建任务，周期性通过 `get_task_status(task_id="...")` 追踪执行进度并汇报。

---

## <span id="faq"></span>🚨 常见排错与自愈专栏

### Q1: 客户端报错 `DEPTH_ZERO_SELF_SIGNED_CERT` 或 `UNABLE_TO_VERIFY_LEAF_SIGNATURE`
- **🔴 症状**：Cursor / Claude Desktop 无法连接，错误日志提示证书不受信任。
- **🔍 根因**：客户端运行于 Electron / Node.js 体系，默认严格拦截未受系统信任机构签名的自签名证书或局域网 IP。
- **⚡ 解决（推荐）**：
  1. **首选方案**：改用各客户端卡片中的 **「本地 Stdio 桥接」** 模式。导出的 Python 脚本已内置针对自签证书与私网 IP 的安全兼容校验，零证书拦截报错。
  2. **若坚持远程 SSE 直连**：需将服务端的 CA 证书（`certs/arl.crt`）导入客户端操作系统的受信任根证书库（macOS 钥匙串设置为“始终信任” / Windows 受信任的根证书颁发机构），使系统网络栈天然信任。（注：请勿在 `mcp.json` 中配置 `NODE_TLS_REJECT_UNAUTHORIZED`，SSE 模式下不会被识别）。

### Q2: 接口调用返回 `401 Unauthorized` 或 `Invalid or expired token`
- **🔴 症状**：客户端所有工具调用均提示鉴权失败。
- **🔍 根因**：未配置正确的 Authorization 请求头，或管理员在 Web 端点击了「刷新 Token」使旧凭据立即作废。
- **⚡ 解决**：在 ARL-Next 顶部导航栏打开「MCP」，一键复制最新有效 Token 并同步更新配置文件中的凭据字段。

### Q3: 执行任务下发提示 `Task dispatching is disabled on this MCP server`
- **🔴 症状**：调用 `create_scan_task` 或 `stop_scan_task` 时被拒绝。
- **🔍 根因**：安全保护策略。ARL-Next 默认仅开放只读查询，防止 Agent 意外触发全量扫描挤占扫描队列。
- **⚡ 解决**：管理员在 MCP 治理中心启用对应工具，并为 Key 授予 `task:dispatch`。工具发现与执行会立即使用已保存的开关；`ARL_MCP_ENABLE_DISPATCH` 仅在未保存对应开关时提供默认值。

### Q4: 远程 SSE 连接频繁断开或出现 `504 Gateway Timeout`
- **🔴 症状**：建立连接后几分钟无响应自动中断，或流式推送超时。
- **🔍 根因**：外部反向代理（如额外的 SLB、WAF 或自建 Nginx）开启了代理缓冲（buffering）或读写超时阈值过短。
- **⚡ 解决**：确保外层反向代理配置中包含 `proxy_read_timeout 86400s; proxy_buffering off;`。ARL-Next 内置 Nginx 已默认配置流式无缓冲代理。

---

## <span id="architecture"></span><details><summary><b>⚙️ 深入了解：底层架构设计哲学与证书细节（点击展开）</b></summary>

### 1. 独立异步微服务解耦长连接
ARL-Next 主 Web API 采用 Gunicorn 多进程线程池模型（16 线程），若直接承载持久化 SSE 长连接，几个 Agent 连接即可耗尽 Web 线程池导致控制台瘫痪。为此，ARL-Next 设计了独立的 `arl-mcp` 异步微服务容器（基于 Python 3.13 原生 `asyncio`），内存占用仅约 60MB，与主业务线程池物理隔离，支持毫秒级握手与高并发事件流分发。

### 2. 紧凑数据递归剪枝（Context-Efficient）
为规避 Agent 上下文 Token 的无效消耗，MCP 服务端与客户端内置递归剪枝算法：
- 剔除所有响应中的 `null`、空列表 `[]` 与空对象 `{}`。
- 去除 HTTP 冗余响应头与大段底层调试字段。
- 将端口与脆弱性指标平铺结构化，确保关键安全情报在高密度上下文中不被截断。

### 3. 本地脚本证书策略全景

| 部署形态 | `ARL_HOST` 取值 | 证书校验逻辑 |
| :--- | :--- | :--- |
| **客户端与服务端同机** | `https://127.0.0.1:5173` | **无需配置**。脚本检测到 `certs/arl.crt`（或 `ARL_auth.md` 记录的路径）即自动信任 |
| **已配置受信任公共证书** | `https://arl.example.com` | **无需配置**。完整校验证书链与主机名 |
| **远程自签部署（经 IP 访问）** | `https://<服务器IP>:5173` | 将服务端证书复制到客户端后设置 `ARL_CA_BUNDLE=/绝对路径/arl.crt` |

- 远程自签场景下证书默认不包含该 IP 的 SAN 扩展，脚本校验证书链后自动跳过主机名匹配，并在 stderr 输出提示。如需强制主机名匹配，设置 `ARL_STRICT_HOSTNAME=true`。
- 临时测试环境可显式设置 `ARL_TLS_VERIFY=false` 关闭全部证书校验（客户端将在 stderr 输出一次性安全告警）。

</details>
