#!/usr/bin/env python3
"""
ARL-Next MCP Server (AI-Native Asset Reconnaissance & Intelligence Protocol)
Provides full 9-dimension asset intelligence, vulnerability data, and scan task orchestration.
"""

import os
import sys
import json
import urllib3
import requests
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from mcp.server.fastmcp import FastMCP

# Disable insecure HTTPS warnings for self-signed certificates
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

mcp = FastMCP(
    "arl-next",
    dependencies=["requests", "urllib3"]
)

def _get_auth():
    host = os.environ.get("ARL_HOST", "").strip()
    token = os.environ.get("ARL_TOKEN", "").strip()
    candidate_paths = [
        Path.cwd() / "ARL_auth.md",
        Path("/Users/sienchen/Documents/github_project/ARL-Next/ARL_auth.md"),
        Path("/Users/sienchen/Documents/github_project/Hunt-Next/ARL_auth.md"),
    ]
    if not host or not token:
        for cp in candidate_paths:
            if cp.exists():
                try:
                    content = cp.read_text(encoding="utf-8")
                    for line in content.splitlines():
                        if not host and line.startswith("ARL_HOST:"):
                            host = line.split(":", 1)[1].strip()
                        elif not token and line.startswith("ARL_TOKEN:"):
                            token = line.split(":", 1)[1].strip()
                        elif not token and "token" in line and "'" in line:
                            parts = line.split("'")
                            if len(parts) >= 4 and parts[1] == "token":
                                token = parts[3].strip()
                except Exception:
                    pass
    if not host:
        host = "https://111.228.59.202:5173"
    if not token:
        raise RuntimeError(
            "ARL API token not configured: set ARL_TOKEN env var or add 'ARL_TOKEN: <key>' "
            "to ARL_auth.md (see repo root ARL_auth.md). Refusing hardcoded default."
        )
    return host.rstrip("/"), token

def _request(method: str, endpoint: str, params: dict = None, json_data: dict = None, timeout: int = 15):
    """统一向 ARL 后端 API 发送请求

    注意:ARL 鉴权/业务失败返回 HTTP 200 + JSON `{"code":401,...}`(非 HTTP 4xx)。
    因此除 HTTP 状态码外,还需检查 JSON 的 `code` 字段。
    """
    host, token = _get_auth()
    url = f"{host}/api{endpoint}"
    headers = {
        "Token": token,
        "Content-Type": "application/json"
    }
    try:
        resp = requests.request(
            method=method,
            url=url,
            headers=headers,
            params=params,
            json=json_data,
            verify=False,
            timeout=timeout
        )
        if resp.status_code != 200:
            return {"code": resp.status_code, "message": f"HTTP Error {resp.status_code}: {resp.text}"}
        content_type = resp.headers.get("Content-Type", "")
        if "application/json" in content_type:
            data = resp.json()
            # ARL 用 HTTP 200 + JSON code!=200 表示业务失败(如鉴权 401),在此统一标记
            if isinstance(data, dict) and "code" in data and data["code"] != 200:
                return data
            return data
        return resp.text
    except Exception as e:
        return {"code": 500, "message": f"Connection error: {str(e)}"}



from pathlib import Path

def _resolve_task_id(target: str = "", task_id: str = "") -> tuple:
    """智能解析 task_id 与 target"""
    if task_id and len(task_id) == 24:
        return task_id, target or task_id, ""
        
    if not target:
        return None, "", "必须提供 target（如 dcdapp.com）或 24位的 task_id"
        
    # 查询该 target 最新相关的任务
    tasks_res = _request("GET", f"/task/?name={target}&size=50")
    if not isinstance(tasks_res, dict) or "items" not in tasks_res:
        tasks_res = _request("GET", f"/task/?target={target}&size=50")
        
    if isinstance(tasks_res, dict) and "items" in tasks_res:
        for item in tasks_res.get("items", []):
            if target in item.get("target", "") or target in item.get("name", "") or target in str(item.get("options", {})):
                return item.get("_id"), item.get("target") or target, item.get("name", "")
                
    return None, target, f"在 ARL 系统中未找到与目标 '{target}' 相关的扫描任务"

ALL_TABS = [
    "site", "domain", "ip", "cert", "wih", "fileleak", 
    "vuln", "nuclei_result", "service", "url", "npoc_service", 
    "stat_finger", "cip"
]

@mcp.tool()
def export_task_assets(target: str = "", task_id: str = "", output_dir: str = "") -> str:
    """
    一键导出目标资产（如 dcdapp.com）或指定任务的所有资产数据，落盘为本地 CSV 文件并返回 AI 战术资产大盘。

    适用场景 / 自然语言触发：
    - "请使用 arl-next mcp 工具导出 dcdapp.com 的所有资产数据"
    - "导出目标 XX 的所有资产"
    - "导出 XX 资产数据"
    - "把 XX 的扫描结果保存到本地"

    功能特性：
    1. 自动根据目标名（target）定位 ARL 中最新的扫描任务；
    2. 并发拉取全部 13 大维度（站点 site、子域名 domain、IP、证书 cert、WIH 敏感信息、文件泄露 fileleak、漏洞 vuln、Nuclei结果、服务 service、URL、服务识别 npoc、指纹 stat_finger、C段 cip）；
    3. 全量保存为本地 CSV 文件（默认位于 recon/<target>/arl/ 或自定义 output_dir）；
    4. 返回极其节省 Token 的精炼 Markdown 资产大盘摘要。

    参数：
    - target: 目标名称/主域名（例如 "dcdapp.com"），支持模糊匹配最新任务。
    - task_id: 可选，24位的 ARL 任务 ID。若提供则优先使用。
    - output_dir: 可选，自定义本地导出目录路径。
    """
    resolved_id, resolved_target, err = _resolve_task_id(target, task_id)
    if not resolved_id:
        return f"【错误】{err}"
        
    target_clean = resolved_target.replace("/", "_").replace(":", "_").strip()
    
    # 确定本地落盘路径
    if output_dir:
        base_dir = Path(output_dir)
    else:
        cwd = Path.cwd()
        if (cwd / "recon").exists() or cwd.name == "Hunt-Next":
            base_dir = cwd / "recon" / target_clean / "arl"
        else:
            base_dir = cwd / f"recon_{target_clean}"
            
    base_dir.mkdir(parents=True, exist_ok=True)
    
    # 并发拉取 13 个维度的全量 CSV 数据
    stats = {}
    
    def _fetch_and_save(tab_name):
        csv_data = _request("GET", "/mcp/task_detail_export", params={"task_id": resolved_id, "tab": tab_name, "limit": 0})
        if isinstance(csv_data, str) and csv_data.strip():
            file_path = base_dir / f"{tab_name}.csv"
            file_path.write_text(csv_data, encoding="utf-8")
            # 计算行数（减去表头）
            lines = [l for l in csv_data.strip().splitlines() if l.strip()]
            count = max(0, len(lines) - 1)
            return tab_name, count
        else:
            # 空文件也建立，方便工具链索引
            (base_dir / f"{tab_name}.csv").write_text("", encoding="utf-8")
            return tab_name, 0

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(_fetch_and_save, tab) for tab in ALL_TABS]
        for future in as_completed(futures):
            tab, count = future.result()
            stats[tab] = count

    # 生成 AI 战术作战大盘摘要
    summary_md = f"""# 🎯 资产大盘报告：{resolved_target}
> 任务 ID: `{resolved_id}` | 本地落盘路径: `{base_dir.absolute()}`

## 📊 全局维度资产统计
| 资产维度 | 检出数量 | 对应本地 CSV 存档 |
| :--- | :--- | :--- |
| **站点 (site)** | {stats.get('site', 0)} 条 | `{base_dir / 'site.csv'}` |
| **子域名 (domain)** | {stats.get('domain', 0)} 条 | `{base_dir / 'domain.csv'}` |
| **IP 资产 (ip)** | {stats.get('ip', 0)} 条 | `{base_dir / 'ip.csv'}` |
| **SSL 证书 (cert)** | {stats.get('cert', 0)} 条 | `{base_dir / 'cert.csv'}` |
| **敏感信息 (wih)** | {stats.get('wih', 0)} 条 | `{base_dir / 'wih.csv'}` |
| **文件泄露 (fileleak)** | {stats.get('fileleak', 0)} 条 | `{base_dir / 'fileleak.csv'}` |
| **已确认风险 (vuln)** | {stats.get('vuln', 0)} 条 | `{base_dir / 'vuln.csv'}` |
| **Nuclei 探测点** | {stats.get('nuclei_result', 0)} 条 | `{base_dir / 'nuclei_result.csv'}` |
| **端口服务 (service)** | {stats.get('service', 0)} 条 | `{base_dir / 'service.csv'}` |
| **URL 爬虫记录** | {stats.get('url', 0)} 条 | `{base_dir / 'url.csv'}` |
| **Python服务识别** | {stats.get('npoc_service', 0)} 条 | `{base_dir / 'npoc_service.csv'}` |
| **指纹统计 (stat_finger)** | {stats.get('stat_finger', 0)} 条 | `{base_dir / 'stat_finger.csv'}` |
| **C 段网段 (cip)** | {stats.get('cip', 0)} 条 | `{base_dir / 'cip.csv'}` |

## 🚀 关键突破点提示
"""
    if stats.get('vuln', 0) > 0 or stats.get('nuclei_result', 0) > 0:
        summary_md += f"- ⚠️ **发现高危风险**：包含 {stats.get('vuln', 0)} 个漏洞及 {stats.get('nuclei_result', 0)} 个 Nuclei 命中标的，请优先审查 `vuln.csv`。\n"
    if stats.get('fileleak', 0) > 0 or stats.get('wih', 0) > 0:
        summary_md += f"- 🔑 **发现敏感信息/泄露**：包含 {stats.get('fileleak', 0)} 处文件泄露与 {stats.get('wih', 0)} 处 WIH 敏感字段，请检查 `fileleak.csv` 与 `wih.csv`。\n"
    if stats.get('site', 0) > 0:
        summary_md += f"- 🌐 **Web 资产总览**：已收敛 {stats.get('site', 0)} 个 Web 站点与 {stats.get('ip', 0)} 个主机节点。\n"
        
    summary_md += f"\n💡 **说明**：全部 13 维全量资产已成功保存为本地 CSV 文件，无需重复拉取，可直接供后续渗透脚本或 AI 深入分析使用。"
    
    return summary_md

@mcp.tool()
def get_task_detail_export(target: str = "", task_id: str = "", tab: str = "site", page: int = 1, limit: int = 100, columns: list[str] = None) -> str:
    """
    按需获取指定目标或任务的详细数据列表（直接返回内存中的 CSV 格式文本）。
    支持分页与特定字段筛选（极其节省 Token）。

    参数：
    - target: 目标名称（如 dcdapp.com）。如果未传 task_id 则自动根据 target 解析任务。
    - task_id: 24位 ARL 任务 ID。
    - tab: 获取的数据类型，支持 'site', 'domain', 'ip', 'cert', 'wih', 'fileleak', 'vuln', 'nuclei_result', 'service', 'url', 'npoc_service', 'stat_finger', 'cip'。
    - page: 页码，默认为 1。
    - limit: 每页返回的数据条数，默认为 100。若为 0 则返回全量。
    - columns: 需要返回的特定列名列表，例如 ["IP", "开放端口"]。
    """
    resolved_id, _, err = _resolve_task_id(target, task_id)
    if not resolved_id:
        return f"【错误】{err}"
        
    params = {
        "task_id": resolved_id,
        "tab": tab,
        "page": page,
        "limit": limit
    }
    if columns:
        params["columns"] = ",".join(columns)
        
    res = _request("GET", "/mcp/task_detail_export", params=params)
    
    if isinstance(res, dict):
        return json.dumps(res, ensure_ascii=False)
    
    return res

@mcp.tool()
def list_arl_tasks(page: int = 1, size: int = 15, query: str = "", status: str = "") -> str:
    """
    列出 ARL-Next 中的扫描任务列表（极其节省 Token 的精炼表格）。
    
    参数：
    - page: 页码，默认 1
    - size: 每页数量，默认 15
    - query: 模糊匹配任务名或目标（如 'bytedance.com'）
    - status: 过滤任务状态（如 'done', 'running', 'stop', 'error'）
    """
    params = {"page": page, "size": size}
    if query:
        params["target"] = query
    if status:
        params["status"] = status
        
    res = _request("GET", "/task/", params=params)
    if not isinstance(res, dict) or "items" not in res:
        return f"[-] 查询失败: {res}"
        
    items = res.get("items", [])
    total = res.get("total", len(items))
    out = [f"📋 ARL-Next 任务总数: {total} (当前第 {page} 页 / 共 {len(items)} 条)", "| 任务 ID | 状态 | 目标 | 任务名称 |", "| :--- | :---: | :--- | :--- |"]
    for it in items:
        tid = it.get("_id", "")
        st = it.get("status", "")
        tgt = it.get("target", "")
        nm = it.get("name", "")
        out.append(f"| `{tid}` | `{st}` | {tgt} | {nm} |")
    return "\n".join(out)

@mcp.tool()
def create_scan_task(target: str, name: str = "", port_scan: bool = True, service_detection: bool = True, domain_brute: bool = True, file_leak: bool = False, nuclei_scan: bool = False, poc_names: list[str] = None) -> str:
    """
    向 ARL-Next 主动下发新建资产侦察或漏洞扫描任务。
    
    参数：
    - target: 目标域名或IP（如 'test.example.com'），必填
    - name: 任务名称（若为空则自动命名为 'AI-Agent-<target>-<时间>'）
    - port_scan: 是否开启端口扫描，默认 True
    - service_detection: 是否开启服务识别，默认 True
    - domain_brute: 是否开启子域名爆破，默认 True
    - file_leak: 是否开启敏感文件泄露扫描，默认 False
    - nuclei_scan: 是否开启 Nuclei CVE 漏洞扫描，默认 False
    - poc_names: 可选指定执行的 PoC 插件名称列表（例如 ['Adminer_PHP_Identify']）
    """
    from datetime import datetime
    if not target:
        return "【错误】target 不能为空"
        
    if not name:
        now_tag = datetime.now().strftime("%m%d_%H%M")
        name = f"AI-Agent-{target}-{now_tag}"
        
    payload = {
        "name": name,
        "target": target,
        "port_scan": port_scan,
        "service_detection": service_detection,
        "domain_brute": domain_brute,
        "file_leak": file_leak,
        "nuclei_scan": nuclei_scan,
        "site_identify": True,
        "ssl_cert": True,
        "site_capture": False,
        "search_engines": False,
        "site_spider": False,
        "arl_search": True,
        "alt_dns": False,
        "dns_query_plugin": True,
        "skip_scan_cdn_ip": True
    }
    
    if poc_names:
        payload["poc_config"] = [{"plugin_name": p} for p in poc_names]
        
    res = _request("POST", "/task/", json_data=payload)
    if isinstance(res, dict) and res.get("code") == 200:
        items = res.get("items", [])
        tids = [it.get("task_id") for it in items if isinstance(it, dict) and it.get("task_id")]
        return f"✅ 成功在 ARL-Next 创建扫描任务！\n- 任务名称: {name}\n- 目标: {target}\n- 生成 Task ID: {', '.join(tids) if tids else '已入队'}\n- 扫描配置: 端口扫描={port_scan}, 服务识别={service_detection}, 域名爆破={domain_brute}, Nuclei={nuclei_scan}, PoC数={len(poc_names or [])}"
    else:
        return f"❌ 任务创建失败: {res}"

@mcp.tool()
def stop_arl_task(task_id: str) -> str:
    """
    主动停止/中止 ARL-Next 中正在运行的扫描任务。
    
    参数：
    - task_id: 24位 ARL 任务 ID
    """
    if not task_id or len(task_id) != 24:
        return "【错误】必须提供合法的 24位 task_id"
    res = _request("GET", f"/task/stop/{task_id}")
    if isinstance(res, dict) and res.get("code") == 200:
        return f"✅ 任务 {task_id} 已成功发送终止信号并标记停止。"
    return f"[-] 停止任务失败: {res}"

@mcp.tool()
def sync_assets_to_scope(scope_name: str, assets: list[str]) -> str:
    """
    将 AI 在侦察中发现的新资产（子域名/IP）反哺同步回 ARL-Next 资产分组（AssetScope）。
    
    参数：
    - scope_name: 资产组名称（如 '抖音业务线-AI扩充'）
    - assets: 资产列表（域名或 IP 列表）
    """
    if not scope_name or not assets:
        return "【错误】scope_name 和 assets 不能为空"
        
    scope_str = "\n".join([a.strip() for a in assets if a.strip()])
    payload = {
        "name": scope_name,
        "scope": scope_str,
        "black_scope": "",
        "scope_type": "mixed"
    }
    res = _request("POST", "/asset_scope/", json_data=payload)
    if isinstance(res, dict) and res.get("code") == 200:
        return f"✅ 成功将 {len(assets)} 个新资产反哺同步至 ARL-Next 资产组「{scope_name}」！"
    return f"[-] 反哺资产组失败: {res}"

if __name__ == "__main__":
    mcp.run()

