<div align="center">
  <p>
    <b>English</b> |
    <a href="./README.md"><b>简体中文</b></a>
  </p>
</div>

# ARL-Next MCP Server (v2.0)

> **Bring Enterprise Attack Surface Reconnaissance & Asset Intelligence to AI Agents**<br>
> Compliant with the Model Context Protocol (2024-11-05) standard, deeply adapted for **Cursor, Claude Desktop, Claude Code, Antigravity, and Windsurf**.

<p align="center">
  <a href="#cursor"><b>⚡ Cursor Integration</b></a> •
  <a href="#claude-desktop"><b>🖥️ Claude Desktop</b></a> •
  <a href="#claude-code"><b>💻 Claude Code CLI</b></a> •
  <a href="#antigravity-windsurf"><b>🚀 Antigravity / Windsurf</b></a> •
  <a href="#tools"><b>🧩 Capabilities & Prompts</b></a> •
  <a href="#faq"><b>🚨 Troubleshooting</b></a> •
  <a href="#architecture"><b>⚙️ Architecture & Internals</b></a>
</p>

---

## ⚡ 10-Second Quick Start (Choose by Your Client)

> [!TIP]
> **💡 Recommended Practice**: Log in to the ARL-Next Web Console and click **「MCP」** in the top navigation bar. The modal automatically generates a ready-to-use configuration populated with your host and API token. For manual configuration, copy the snippet matching your client below:

### <span id="cursor"></span>1. Cursor

- **Configuration File Path**: Project root `.cursor/mcp.json` or Global Settings (Features ➔ MCP Servers)
- **Preferred Mode: Remote Direct (SSE)** *(For domain deployments with valid TLS certificates)*:
  ```json
  {
    "mcpServers": {
      "arl-next": {
        "url": "https://arl.example.com:5173/mcp/sse",
        "headers": {
          "Authorization": "Bearer <Token copied from ARL Web Console>"
        }
      }
    }
  }
  ```
  *(Note: If your client does not support custom headers, direct URL query authentication is supported: `"url": "https://arl.example.com:5173/mcp/sse?token=<Token>"`)*
- **Alternative Mode: Private IP / Self-Signed TLS (Stdio Bridge)** *(Bypasses Node.js TLS rejection)*:
  ```json
  {
    "mcpServers": {
      "arl-next": {
        "command": "python3",
        "args": ["/absolute/path/to/ARL-Next/mcp-server/server.py"],
        "env": {
          "ARL_HOST": "https://192.168.1.100:5173",
          "ARL_TOKEN": "<Token copied from ARL Web Console>"
        }
      }
    }
  }
  ```

---

### <span id="claude-desktop"></span>2. Claude Desktop

- **Configuration File Path**:
  - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
  - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
- **Preferred Mode: Remote Direct (SSE)**:
  ```json
  {
    "mcpServers": {
      "arl-next": {
        "url": "https://arl.example.com:5173/mcp/sse",
        "headers": {
          "Authorization": "Bearer <Token copied from ARL Web Console>"
        }
      }
    }
  }
  ```
- **Alternative Mode: Private IP / Self-Signed TLS (Stdio Bridge)**:
  ```json
  {
    "mcpServers": {
      "arl-next": {
        "command": "python3",
        "args": ["/absolute/path/to/ARL-Next/mcp-server/server.py"],
        "env": {
          "ARL_HOST": "https://192.168.1.100:5173",
          "ARL_TOKEN": "<Token copied from ARL Web Console>"
        }
      }
    }
  }
  ```

---

### <span id="claude-code"></span>3. Claude Code CLI

Register globally with a single CLI command without creating virtual environments or installing third-party dependencies:

```bash
claude mcp add -s user arl-next \
  python3 "$(pwd)/mcp-server/server.py" \
  --env ARL_HOST="https://arl.example.com:5173" \
  --env ARL_TOKEN="<Token copied from ARL Web Console or ARL_auth.md>"
```

---

### <span id="antigravity-windsurf"></span>4. Antigravity / Windsurf

- **Configuration File Path**:
  - **Windsurf**: `~/.codeium/windsurf/mcp_config.json`
  - **Antigravity**: Workspace `.gemini/antigravity-cli/mcp/` or Global Settings
- **Configuration Content**: Identical to Cursor; paste the snippet into your client's `mcpServers` node.

---

## <span id="tools"></span>🧩 Core Capabilities & Agent Interactions

ARL-Next MCP registers 6 standardized tools with read-only reconnaissance enabled by default and controlled task dispatching:

### 1. Tool Matrix

| Tool Name | Core Purpose | Default Access | Typical Application |
| :--- | :--- | :--- | :--- |
| `get_asset_profile` | 5-Dimensional Asset Profile | **Read-Only (Open)** | Query ports, services, Web fingerprints, TLS certs, historical vulnerabilities, and file leaks |
| `get_enterprise_profile` | Enterprise Ecosystem Profile | **Read-Only (Open)** | Query corporate structure, ICP domains, mobile apps, mini programs, official accounts, Weibo, and investments |
| `search_assets` | Full-Database Search | **Read-Only (Open)** | Search sites, domains, IPs, or vulnerabilities by keyword |
| `get_task_status` | Task Status Tracking | **Read-Only (Open)** | Inspect real-time progress percentages and metric summaries of a 24-character task ID |
| `create_scan_task` | Submit Scan Task | **Guarded (Requires Auth)** | Trigger ARL regular reconnaissance or periodic risk-cruising tasks |
| `stop_scan_task` | Cancel Scan Task | **Guarded (Requires Auth)** | Abort a queued or actively executing task |

### 2. Typical Agent Prompts & Interactions

Once connected, interact with your AI Agent using natural language:

- **Scenario 1: Single Target Attack Surface Drill-Down**
  > **💬 Prompt**: "Analyze the network exposure and known vulnerabilities of `target.example.com`."<br>
  > **🤖 Agent Action**: Invokes `get_asset_profile(target="target.example.com")` to gather open ports, tech fingerprints, SSL certificates, and CVE findings in a single request, presenting a structured security summary.
- **Scenario 2: Enterprise Ecosystem Reconnaissance & ASM Correlation**
  > **💬 Prompt**: "Find out what mobile apps and mini programs Xiaomi operates, and list its primary ICP domains."<br>
  > **🤖 Agent Action**: Invokes `get_enterprise_profile(target="Xiaomi")` to retrieve an overview profile and top asset samples, drills down with `get_enterprise_profile(target="Xiaomi", category="app")` as needed, and evaluates exposure risks via `get_asset_profile` on core domains.
- **Scenario 3: Component & Tech Stack Reconnaissance**
  > **💬 Prompt**: "Search our database for all site assets running Spring Boot or Nginx."<br>
  > **🤖 Agent Action**: Invokes `search_assets(query="Spring Boot", asset_type="site")` and returns matching endpoints, IP mappings, and associated scan jobs.
- **Scenario 4: Controlled Task Dispatch & Status Monitoring**
  > **💬 Prompt**: "Launch a reconnaissance task against IP `192.0.2.1` and summarize the results when done."<br>
  > **🤖 Agent Action**: Invokes `create_scan_task(target="192.0.2.1")`, monitors progress via `get_task_status(task_id="...")`, and notifies upon completion.

---

## <span id="faq"></span>🚨 Troubleshooting & Self-Healing FAQ

### Q1: Client fails with `DEPTH_ZERO_SELF_SIGNED_CERT` or `UNABLE_TO_VERIFY_LEAF_SIGNATURE`
- **🔴 Symptom**: Cursor or Claude Desktop rejects connection with an untrusted certificate error.
- **🔍 Root Cause**: Cursor and Claude Desktop run on Electron / Node.js, which strictly validates TLS certificates against trusted system CAs and rejects private LAN IPs or self-signed certs.
- **⚡ Solution (Recommended)**:
  1. **Preferred**: Switch to the **「Local Stdio Bridge」** configuration. The exported Python script natively handles self-signed CA chains and IP SAN adaptation without TLS blocking.
  2. **If persisting with Remote SSE**: Import the server's CA certificate (`certs/arl.crt`) into your operating system's trusted root certification authorities (macOS Keychain set to "Always Trust" / Windows Certificate Manager). (Note: Adding `NODE_TLS_REJECT_UNAUTHORIZED` in `mcp.json` has no effect as SSE transport does not spawn subprocesses).

### Q2: Requests return `401 Unauthorized` or `Invalid or expired token`
- **🔴 Symptom**: Tool calls fail with authentication errors.
- **🔍 Root Cause**: Missing Authorization header, or an administrator clicked "Refresh Token" in the Web Console, immediately revoking previous credentials.
- **⚡ Solution**: Open the "MCP" modal in the ARL-Next top navigation bar, copy the latest token, and update your client configuration.

### Q3: Task dispatch returns `Task dispatching is disabled on this MCP server`
- **🔴 Symptom**: Calling `create_scan_task` or `stop_scan_task` is rejected.
- **🔍 Root Cause**: Security safeguard. ARL-Next MCP defaults to read-only mode to prevent agents from unintentionally flooding the scan queue.
- **⚡ Fix**: Enable the tool in the MCP Governance Center and grant the key `task:dispatch`. Discovery and execution use saved switches immediately; `ARL_MCP_ENABLE_DISPATCH` provides a default only when no corresponding switch is saved.

### Q4: Remote SSE connection frequently disconnects or returns `504 Gateway Timeout`
- **🔴 Symptom**: Connection terminates unexpectedly after several minutes, or streaming requests time out.
- **🔍 Root Cause**: An external upstream proxy (e.g., custom SLB, WAF, or outer Nginx) has response buffering enabled or short timeout thresholds.
- **⚡ Solution**: Ensure outer reverse proxies specify `proxy_read_timeout 86400s; proxy_buffering off;`. ARL-Next's built-in Nginx container includes these streaming optimizations by default.

---

## <span id="architecture"></span><details><summary><b>⚙️ Architecture & Technical Reference (Click to expand)</b></summary>

### 1. Dedicated Asynchronous Microservice for Stream Isolation
ARL-Next's primary Web API runs on Gunicorn's multi-process worker model (16 worker threads). Direct persistent SSE streams would quickly starve the Web thread pool. To resolve this, ARL-Next isolates MCP streaming inside a dedicated `arl-mcp` microservice container (powered by Python 3.13 `asyncio`), consuming only ~60MB of RAM and ensuring fast handshakes without impacting the Web UI.

### 2. Context-Efficient Recursive Pruning
To prevent token waste in agent contexts, both the MCP server and client scripts implement recursive JSON pruning:
- Strips all `null` values, empty arrays `[]`, and empty objects `{}`.
- Excludes redundant HTTP headers and verbose debugging metadata.
- Flattens port and vulnerability indicators so critical security signals are never truncated.

### 3. Local Script TLS Certificate Policy

| Deployment Scenario | `ARL_HOST` Value | Verification Behavior |
| :--- | :--- | :--- |
| **Client on the same host** | `https://127.0.0.1:5173` | **None needed.** Automatically trusts `certs/arl.crt` (or path in `ARL_auth.md`) |
| **Trusted public certificate** | `https://arl.example.com` | **None needed.** Full certificate chain and hostname verification |
| **Remote self-signed (IP access)** | `https://<server-ip>:5173` | Copy server certificate to client and set `ARL_CA_BUNDLE=/abs/path/arl.crt` |

- Under remote self-signed scenarios where the certificate lacks SAN extensions for the IP, the script verifies the certificate chain and automatically skips hostname matching (printing a notice to stderr). To enforce strict hostname checks, set `ARL_STRICT_HOSTNAME=true`.
- For temporary testing only, `ARL_TLS_VERIFY=false` disables all TLS verification (a warning will be printed to stderr).

</details>
