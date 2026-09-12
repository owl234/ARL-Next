# ARL-Next MCP Server (v2.0 极速低耗版)

> **极速响应 · 极致低 Token · 全客户端免装依赖通杀**<br>
> 专为 **Antigravity、Claude Code、OpenAI Codex、DeepSeek Harness、ZCode、WorkBuddy** 等全系列 AI Agent 深度优化的资产侦察情报协议。

---

## 🌟 核心特性与设计哲学

1. **⚡ 零依赖冷启动（< 20ms）**：
   - 彻底摆脱庞大的第三方库（无 `mcp[cli]`、无 `pydantic`、无 `requests`）。
   - 仅依赖 Python 3.8+ 原生标准库（`sys`, `json`, `urllib`, `ssl`），在任何机器上均可直接用系统 Python 瞬间启动，彻底消除环境依赖与虚拟环境配置故障。
2. **🎯 全链路画像（精准聚焦）**：
   - 摒弃以往大粒度、倾倒成百上千行 CSV 的反人类设计。
   - 仅暴露单一核心工具 `get_asset_profile`，单次调用即可穿透网络层（IP/端口/服务/Geo/ASN）、应用层（标题/状态码/Web指纹）、证书层（SANs/签发者）以及攻防层（历史漏洞/Nuclei命中标的/文件与敏感信息泄露）。
3. **📉 极致节省 Token（-85%+）**：
   - 系统级工具提示词从以往的 ~2,500 Token 骤降至 **~120 Token**。
   - 数据返回格式为**极致精简 JSON**，递归剪枝剔除所有 `null`、空数组与多余 header；端口与漏洞采取**全量紧凑平铺**展示，不遗漏任何边界风险。

---

## 🛠️ 工具参考

### `get_asset_profile`
获取指定目标的全链路资产综合情报。

#### 参数
- `target` (*string, 必填*)：资产标的，支持：
  - 子域名 / 主域名（如 `oa.example.com`）
  - IP 地址（如 `1.2.3.4`）
  - 站点完整 URL（如 `https://oa.example.com:8443`）
- `task_id` (*string, 可选*)：24 位 ARL 扫描任务 ID。若指定则锁定该任务上下文，未指定则智能匹配最新任务或全局资产库。

#### 返回样例（精炼紧凑 JSON）
```json
{
  "target": "admin.example.com",
  "resolved_ips": ["1.2.3.4"],
  "geo": "中国/浙江/杭州",
  "asn": "Hangzhou Alibaba Advertising Co.,Ltd.",
  "ports": [
    {"port": 80, "service": "http", "product": "nginx"},
    {"port": 443, "service": "https", "product": "nginx"},
    {"port": 8080, "service": "http", "product": "Spring-Boot"}
  ],
  "web": {
    "url": "https://admin.example.com",
    "status": 200,
    "title": "统一运营管理系统",
    "fingerprints": ["Vue.js", "Spring-Boot", "Nginx", "Shiro"]
  },
  "cert": {
    "issuer": "Let's Encrypt Authority X3",
    "sans": "*.example.com, example.com"
  },
  "vulns": [
    {"name": "Spring4Shell RCE", "severity": "high", "plugin": "CVE-2022-22965"}
  ],
  "leaks": [
    {"url": "https://admin.example.com/.git/config", "status": 200}
  ]
}
```

---

## 🚀 客户端接入配置指南

### 1. Claude Code
在命令行中直接注册（无需切换或创建虚拟环境）：
```bash
claude mcp add -s user arl-next \
  python3 "$(pwd)/mcp-server/server.py" \
  --env ARL_HOST="https://arl.example.com:5173" \
  --env ARL_TOKEN="<从 ARL_auth.md 中读取的 Token>"
```

### 2. Antigravity / Cursor / Windsurf (`mcp.json`)
在工作区或全局 `mcp.json` 中配置：
```json
{
  "mcpServers": {
    "arl-next": {
      "command": "python3",
      "args": ["/绝对路径/ARL-Next/mcp-server/server.py"],
      "env": {
        "ARL_HOST": "https://arl.example.com:5173",
        "ARL_TOKEN": "<从 ARL_auth.md 中读取的 Token>"
      }
    }
  }
}
```

### 3. OpenAI Codex / DeepSeek Harness / ZCode / WorkBuddy
直接在客户端对应的 MCP stdio 启动命令中填入：
- **Command**: `python3`
- **Args**: `["/绝对路径/ARL-Next/mcp-server/server.py"]`
- **Environment**:
  - `ARL_HOST`: `https://arl.example.com:5173`
  - `ARL_TOKEN`: `<从 ARL_auth.md 中读取的 Token>`
*(注：若未显式传环境变量，脚本会自动按顺序自动发现当前目录或项目根目录下的 `ARL_auth.md`)*
