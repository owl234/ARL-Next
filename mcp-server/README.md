# ARL-Next MCP Server

> 让 Claude Code 直接对接 ARL（资产侦察灯塔），以极其节省 Token 的 CSV 格式获取目标资产情报。

## 它能做什么

当前暴露 **6 个全功能双向智能工具**：

1. `export_task_assets`：一键导出目标 13 维全量资产为本地 CSV 并返回极简战术大盘摘要。
2. `get_task_detail_export`：按需在对话中获取单维度的 CSV 数据（支持列裁剪与分页）。
3. `list_arl_tasks`：轻量分页查询 ARL-Next 扫描任务列表（表格形式，极省 Token）。
4. `create_scan_task`：AI 主动向 ARL-Next 下发针对性资产侦察或漏洞扫描任务。
5. `stop_arl_task`：AI 主动终止/中止正在运行的 ARL-Next 任务。
6. `sync_assets_to_scope`：将 AI 本地发现的新资产反哺同步回 ARL-Next 资产分组（AssetScope）。

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ARL_HOST` | ARL 后端 API 地址 | `https://111.228.59.202:5173` |
| `ARL_TOKEN` | ARL API Token | 自动优先从环境变量或 `ARL_auth.md` 中读取 |

## 快速开始

### 方式 A：Python 虚拟环境（Claude Code / AGY 推荐）

```bash
cd mcp-server
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

注册到 Claude Code（替换地址与 Token）：

```bash
claude mcp add -s user arl-next-mcp \
  "$(pwd)/.venv/bin/python" "$(pwd)/server.py" \
  --env ARL_HOST="https://111.228.59.202:5173" \
  --env ARL_TOKEN="<从 ARL_auth.md 读取 ARL_TOKEN>"
```

### 方式 B：Docker

```bash
docker build -t arl-next-mcp:latest .
```

客户端 MCP 配置：

```json
"ARL-Next": {
  "command": "docker",
  "args": ["run", "-i", "--rm", "-e", "ARL_HOST", "-e", "ARL_TOKEN", "arl-next-mcp:latest"],
  "env": {
    "ARL_HOST": "https://111.228.59.202:5173",
    "ARL_TOKEN": "<从 ARL_auth.md 读取 ARL_TOKEN>"
  }
}
```

## 工具参考

### 1. `export_task_assets`
一键全量导出目标全部 13 维资产到本地 CSV，并返回极简 Markdown 战术总览。
- 参数：`target` (string), `task_id` (string, 可选), `output_dir` (string, 可选)。

### 2. `get_task_detail_export`
在对话流中按需提取特定维度的 CSV 数据，支持列过滤。
- 参数：`target` (string), `task_id` (string), `tab` (string, 默认 site), `page` (int), `limit` (int), `columns` (list[str])。

### 3. `list_arl_tasks`
查询 ARL 任务列表。
- 参数：`page` (int, 默认 1), `size` (int, 默认 15), `query` (string), `status` (string)。

### 4. `create_scan_task`
主动向 ARL 下发扫描任务。
- 参数：`target` (string, 必填), `name` (string), `port_scan` (bool), `service_detection` (bool), `domain_brute` (bool), `file_leak` (bool), `nuclei_scan` (bool), `poc_names` (list[str])。

### 5. `stop_arl_task`
终止指定的 ARL 扫描任务。
- 参数：`task_id` (string, 24位 ObjectID)。

### 6. `sync_assets_to_scope`
将本地发现的新资产反哺至 ARL-Next 资产组。
- 参数：`scope_name` (string), `assets` (list[str])。

## 依赖

`mcp>=1.0.0,<2.0.0`、`requests`、`urllib3`（见 `requirements.txt`）。
