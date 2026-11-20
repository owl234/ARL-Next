<div align="center">
  <p>
    <b>English</b> |
    <a href="./API_GUIDE.md"><b>简体中文</b></a>
  </p>
</div>

# ARL-Next REST API Calling Guide & Integration Conventions

> This guide outlines basic API specifications, authentication methods, legacy HTTP verb conventions, task state lifecycle rules, and data namespace architectures for automated scripts, CI/CD pipelines, and Security Orchestration, Automation, and Response (SOAR) workflows.<br>
> For full OpenAPI / Swagger schemas and interactive debugging, visit `https://<your-arl-host>:5173/api/doc` on your running deployment.

---

## 1. Core Conventions & Gateway Routing

- **Base Path**: All backend API endpoints are prefixed with `/api`.
- **Protocol & Gateway Port**: In production environments, all requests are routed through the frontend Nginx reverse proxy at `https://<your-arl-host>:5173/api/...`.
- **Payload Schema**: All endpoints return JSON objects. Top-level responses include business status code `code` and descriptive `message`:
  ```json
  {
    "code": 200,
    "message": "success",
    "data": { ... }
  }
  ```
  > [!IMPORTANT]
  > Clients **must not rely solely on HTTP 200 status codes** to infer business success; always inspect `code === 200` (or appropriate success codes) in the response payload.

---

## 2. Authentication & Security Policy

- **Header Authentication (Required)**: Pass the token in the HTTP header when authentication is enabled:
  ```http
  Token: <your-token>
  ```
- **No account credentials in URLs**: `?token=` is no longer accepted. Authentication decorators return HTTP 401 with JSON `code: 401`; continue checking JSON `code` for other legacy business errors.
- **Sessions and migration**: Login/refresh tokens use cryptographic randomness and expire after 24 hours. Legacy sessions receive a one-time 24-hour grace period; restarts do not extend it. Successful legacy-password login upgrades MD5 to scrypt. Existing passwords are preserved; new/reset passwords require 12–1024 characters and no longer use a fixed initial value. Long-running integrations may use a separately configured, full-privilege `API_KEY` (MCP: `ARL_TOKEN`), with an appropriate rotation policy.
- **Login limits**: MongoDB atomic counters allow 10 attempts per account per five minutes (account counter cleared on success) and 60 per backend peer address per minute. The production gateway separately limits each actual client IP to five per minute with a burst of five. Excess attempts return HTTP 429; backend responses include `Retry-After`.
- **Screenshots and downloads**: Screenshots require Header authentication; the frontend displays authenticated Blobs and releases their URLs. Nuclei exports use authenticated downloads. For large backups, call authenticated `POST /api/backup/download_ticket` with `{"filename":"arl_backup_....tar.gz"}`, then download using `GET /api/backup/download/<filename>?ticket=<ticket>`. Tickets expire after 60 seconds, are scoped to one file, are consumed atomically once, and are revoked by logout/session rotation/API Key rotation. They cannot authenticate other APIs. Request a new ticket after an interrupted download.
- **Updater**: Control operations require POST with `X-Update-Token` or a JSON token. Authenticated `POST /api/system_config/request_update_token` issues a five-minute control token; use `{"purpose":"status"}` for a separate status token. Triggering an update returns `log_token`; send it in `X-Update-Read-Token` when polling `/update_stream/log`. Log-only tokens last one hour and survive backend restarts; their digest is stored on the host at `/var/lib/arl-updater/read_token.json` (0600). A new update revokes the previous log token. Anonymous logs and wildcard CORS are disabled.
- **Security Red Line**: Never commit real API tokens to public version control, GitHub issues, publicly shared debug logs, or terminal command histories.
- **Unauthenticated Environments**: If authentication is explicitly disabled in the system configuration for air-gapped or testing environments, token verification is bypassed. Always ensure platform authentication and gateway access controls are enforced on exposed networks.

### Remediation and acceptance scope

| Issue | Remediation | Regression coverage |
| :--- | :--- | :--- |
| Backup extraction | Fixed component manifest and SHA256 checks; reject links, special files and duplicates; stage all components and validate dedicated data directories before database restore | Traversal, sibling-directory writes, existing symlinks and corrupt hashes rejected; valid archives restored |
| Favicon SSRF | Validate HTTP(S), domains and every resolved IP; pin the connection to a checked address with Host/SNI preserved; disable redirects and cap responses at 2MB | Forbidden targets never contacted; direct and proxied requests use literal checked IPs |
| Credential TLS | Verify certificates by default; explicit self-signed scan support uses a separate connection pool | Untrusted certificates receive no API credentials, including after an insecure scan |
| Anonymous screenshots | Header authentication and private/no-store responses | Anonymous denial and authenticated display/preview |
| Download credentials in URLs | Header downloads or short-lived, single-use scoped tickets | Expiry, replay, wrong-file and session-revocation rejection |
| IP blacklist bypass | Compare complete ranges/networks; fail closed on invalid policy/targets | Any overlap blocks scanning |
| CSV formulas | Escape formula prefixes in cells and headers | Includes whitespace, tab and newline prefixes |
| Login baseline | Random initial passwords, scrypt, throttling, expiry and revocation | Legacy hash upgrade and preservation of existing accounts |
| Updater logs | Scoped read-only tokens and expiring control/status tokens | Anonymous denial, backend-independent log polling, status tokens cannot trigger updates |
| MCP code generation | Validate server origins and serialize credentials as string literals | Host injection rejected; special-character keys remain data |

Upgrade the backend, frontend gateway and host updater together. Migrate `?token=` callers to headers. Historical archives containing links or nonstandard components must be normalized before restore. Archives can contain executable Python PoCs, so restore only trusted backups; SHA256 provides integrity checking. Private third-party APIs should use a mounted CA via `REQUESTS_CA_BUNDLE`, not disabled TLS verification. The SSRF change covers favicon fetching; browser/PoC execution still requires network isolation from management and cloud metadata services. Rolling back reopens these vulnerabilities.

For isolated regression checks, install the backend dependencies plus `pytest` and `mongomock`, then run `python backend/test/run_security_regressions.py`. The suites use a MongoDB substitute, temporary files and loopback HTTP/TLS servers, without real scanning or deployment. Run frontend file-authentication tests from `frontend/` with `node --test test/authenticatedFiles.test.js`.

---

## 3. Task Management & Lifecycle State Constraints

> [!WARNING]
> Due to backward compatibility, certain task endpoints retain specific HTTP method bindings and prerequisite lifecycle state checks. Strictly follow these conventions instead of guessing generic RESTful patterns.

### Core Task Operations Reference

| Operation | HTTP Method & Path | Parameters / Request Payload | Prerequisites & Constraints |
| :--- | :--- | :--- | :--- |
| **List Tasks** | `GET /api/task/` | Query params: `target`, `status`, `page`, `size`; optionally `include_statistics=1` | Returns paginated task records |
| **Scan Task Statistics** | `GET /api/task/statistics` | None | Returns aggregated count per state without loading records |
| **Enterprise Task Statistics** | `GET /api/icp/task/statistics` | None | Returns status statistics for enterprise OSINT / ICP tasks |
| **Stop Single Task** | `GET /api/task/stop/<task_id>` | URL path param: `task_id` (24-char hex) | ⚠️ **Note: Uses GET to perform state mutation** (terminates the task). Do not use `POST` or `DELETE` |
| **Batch Stop Tasks** | `POST /api/task/batch_stop/` | JSON: see OpenAPI schema | Stops multiple tasks simultaneously |
| **Stop Single Enterprise Task** | `GET /api/icp/stop/<task_id>` | URL path param: `task_id` (24-char hex) | ⚠️ **Note: Uses GET to perform state mutation**; cancels the `osint-service` task and clears any asset group update lock; returns code `105` if already finished |
| **Batch Stop Enterprise Tasks** | `POST /api/icp/batch_stop/` | JSON: `{"task_ids": ["<task_id>"]}` (`task_id` alias also accepted) | Stops active enterprise OSINT tasks, clears group update locks, skips finished tasks, and returns `stopped_ids`, `skipped_ids`, and `failed_ids` |
| **Resume Enterprise Task** | `POST /api/icp/resume/<task_id>` | URL path param: `task_id` | Requires terminal state (`stop` or `error`) with an incomplete `recon_checkpoint`; resumes remaining entities/dimensions in place while preserving existing assets |
| **Backfill Missing Details** | `POST /api/icp/backfill_details/<task_id>` | URL path param: `task_id`; optional JSON: `{"query_types": ["app", "mapp", "kapp"]}` | Requires terminal task state; backfills empty `serviceName` entries without a 100-item batch cap (refreshing `dataId=0` or rotated IDs by filing number), merges cross-source duplicates, and recalculates statistics in place |
| **Delete Task** | `POST /api/task/delete/` | JSON: `{"task_id": ["<task_id>"], "del_task_data": false, "del_synced_asset": false}` | ⚠️ **State Constraint**: Only tasks in terminal states (`done`, `stop`, `error`) can be deleted; active tasks return error code `104`. `del_synced_asset` defaults to `false` (preserving asset group archives) and only takes effect when `del_task_data: true`, removing `asset_*` records exclusively produced by the deleted task(s) and rebuilding derived collections |
| **Restart Task** | `POST /api/task/restart/` | JSON: `{"task_id": ["<task_id>"]}` | Only stopped/finished tasks can be restarted |
| **Run Scheduled Task Now** | `POST /api/task_schedule/run/` | JSON: `{"_id": ["<schedule_id>"]}` | Immediately dispatches the selected scheduled scan(s) into the scheduling queue, incrementing `run_number` and updating `last_run_date` (recalculates `next_run_date` when a recurring schedule is in `scheduled` state) |

### Associate New Scan Tasks with Asset Groups

When creating a reconnaissance task, optionally select an existing asset group. The selector supports name search and pagination. Completed tasks use the existing asset synchronization pipeline; this does not create periodic monitoring or extend the group's configured scope.

`POST /api/task/` accepts an optional JSON field `related_scope_id`, for example:

```json
{"name": "Boundary discovery", "target": "www.example.com", "related_scope_id": "<asset_scope_id>"}
```

Before creating any tasks in a batch, the backend checks group existence and verifies that all domain, IP, or CIDR targets belong to its scope. Existing target validation and blacklist checks remain active. Omitting the field preserves ordinary scan behavior. Restarting an associated task retains the group ID, revalidates the current scope, and clears the new task's previous sync outcome.

The task list distinguishes synchronization after completion, queued synchronization, active synchronization, success, and failure. Failure reasons appear in a tooltip. Scan results and synchronization status are retained independently; selecting a group does not indicate successful synchronization. The group and target scope are checked again before synchronization.

`POST /api/task/sync/` supports finished domain and IP tasks with `task_id` and `scope_id`. Full scope validation still applies. The request records a queued state before dispatch and records dispatch errors. Both automatic and manual synchronization record `synced_scope_id` / `synced_scope_name` along with `sync_summary` (`total_new`, `total_update`, and per-type `new` / `update` breakdowns) on success or `sync_error` on failure, without automatic retries. Partial errors in auxiliary phases preserve discovered assets and record details in `error_msg` and `phase_errors`, while failures in critical discovery phases transition the task to `error`.

Task creation supports scoping by asset group; Nuclei YAML/ZIP import is provided by the PoC management page and is not duplicated here.

### Port Scan Host Discovery Strategy (`host_discovery_mode`)

`POST /api/task/` (top-level `host_discovery_mode`), `POST /api/policy/add/`, and `POST /api/policy/edit/` (`policy.ip_config.host_discovery_mode`) configure Nmap host discovery before TCP port scanning. Tasks can also be filtered via `GET /api/task/?options.host_discovery_mode=<mode>`:

| Value | Behavior |
| :--- | :--- |
| `auto` (default; omitted, `null`, or empty resolves to `auto`) | Selects strategy from expanded target IPs × expanded TCP ports:<br>• `<= 60` ports (and not `1-65535`): always `-Pn`<br>• `61–2000` ports (covers `top100` / `top1000`): `-Pn` for `<= 16` IPs; `-PE -PS<alive_port>` for `> 16` IPs<br>• `> 2000` ports or `1-65535`: `-Pn` for `<= 2` IPs; `-PE -PS<alive_port>` for `> 2` IPs |
| `skip` | Force direct port scan with `-Pn` (skip host discovery) |
| `probe` | Force host discovery with `-PE -PS<alive_port>` before scanning ports |

> **Validation & Exclusions**: Non-empty values other than `auto`, `skip`, and `probe` are rejected. When host discovery runs (`-PE -PS`), ports configured in `exclude_ports` are automatically subtracted from the alive-port list (falling back to `-PE` only if every alive port is excluded).

Example (force direct `-Pn` scan on an RFC 5737 block):

```json
{"name": "Direct segment scan", "target": "192.0.2.0/24", "port_scan": true, "port_scan_type": "top100", "host_discovery_mode": "skip"}
```

### Website Screenshot Toggle (`site_capture`)

`POST /api/task/` (top-level `site_capture`), `POST /api/policy/add/`, and `POST /api/policy/edit/` (`policy.site_config.site_capture`) control whether ASM tasks run headless-browser screenshots. Policy-driven tasks (policy scans, risk cruising, scheduled scans, asset-group domain/IP monitoring and one-shot scans, manual site/domain additions, Fofa tasks, and MCP dispatch) inherit `site_capture` from the selected policy:

| Value | Behavior |
| :--- | :--- |
| `true` (default; omitted or `null` resolves to `true`) | Captures screenshots for alive sites not marked as default-backend (`catch_all`) and records `/image/<task_id>/<file>.jpg` |
| `false` | Skips the screenshot stage and stores `screenshot: ""`; syncing to an asset group preserves any existing screenshot on the stored `asset_site` record rather than clearing it |

> **Scope Notes**: Standalone WIH monitoring (which screenshots newly discovered subdomain sites) and website change monitoring (lightweight HTTP polling without screenshots) do not bind scan policies and keep their existing behavior. Sites marked as `catch_all` default backends skip screenshots even when `site_capture` is `true`.

Example (disable screenshots to reduce runtime on large scans):

```json
{"name": "Fast asset recon", "target": "example.com", "port_scan": true, "site_identify": true, "site_capture": false}
```

### Best Practices for Task Deletion

To delete currently running tasks programmatically, execute a two-stage sequence:
1. Call `GET /api/task/stop/<task_id>` to transition the task to `stop` state;
2. Confirm the task has reached a terminal state, then call `POST /api/task/delete/`. Deletion requests on active tasks are rejected by the server with `{"code": 104, "message": "任务运行中"}`.

### Aggregated Statistics Parameter (`include_statistics=1`)

- Supplying `include_statistics=1` to `GET /api/task/` or `GET /api/icp/task` appends an aggregated `statistics` object to the response payload:
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
  - `active`: Total active tasks (`running + waiting`).
  - `abnormal`: Total abnormally terminated tasks (`error + stop`).
  - `running`: Includes intermediate stages (port scan, service recognition, risk cruising, etc.).
  - **Scope**: Statistics represent the entire collection and do not change with page number or keyword filters.
- **Degradation Resilience**: If metric aggregation encounters an error, the core task list is still returned, annotated with `statistics_error: true` (and `statistics` omitted). Clients should retain previous valid statistics rather than zeroing them out.

---

## 4. Result Query Namespaces

ARL-Next separates reconnaissance outputs into **Task-Specific Outputs** and **Asset Group Archives**, using dedicated API namespaces:

| Asset Type | Single Task Query Namespace (via `task_id`) | Asset Group Query Namespace (via `scope_id`) |
| :--- | :--- | :--- |
| **Subdomain** | `/api/domain/` | `/api/asset_domain/` |
| **IP Address** | `/api/ip/` | `/api/asset_ip/` |
| **Web Site** | `/api/site/` | `/api/asset_site/` |
| **Other Dimensions** | `/api/wih/`, `/api/vuln/`, `/api/fileleak/`, etc. | `/api/asset_wih/`, `/api/asset_vuln/`, etc. |

> [!NOTE]
> - Task-level queries require a valid `task_id`;
> - Group-level queries require a valid `scope_id`;
> - These namespaces map to separate underlying MongoDB collections and indexing schemes. Consult `/api/doc` for exact query fields and filtering options.

### WIH API candidates (static discovery)

Add or enable the following entry in the active `WIH_RULE_PATH` file, keeping the other rules, then run an existing WIH task:

```yaml
rules:
  - id: api_endpoint
    enabled: true
```

This rule is disabled by default. It supplements existing path, URL and sensitive-information rules. Enabling only `enabled` reuses downloaded scripts without requesting candidate endpoints. Active collection requires the separate `probe` option below.

Supported calls with static string arguments are `fetch`, `window.fetch`, `globalThis.fetch`, `axios(config)`, `axios(url, config)`, `axios.request(...)` and the `get/post/put/patch/delete/head/options` Axios methods. Fetch URLs use the final document response URL and first `<base href>`, never the CDN script directory. Axios uses an explicit per-call `baseURL` with Axios concatenation semantics, preserving prefixes such as `/v1`. An unknown base keeps the original path with `api_request.url: null`; an unknown method is `UNKNOWN`.

Variable evaluation, concatenation, interpolated templates, Axios instance aliases, runtime defaults and interceptors are outside this stage. Unsupported expressions are not reported as resolved endpoints. Existing WIH matching continues unchanged. The lexical extractor is not a full JavaScript parser. Limits are 200 additional candidates per site, 100,000 tokens per script 512 tokens per call and 8,192 source characters per string literal; reaching a limit never stops the existing WIH scan.

Results use `/api/wih/` for tasks and `/api/asset_wih/` for asset groups. Filter by `record_type__eq=api_endpoint`, then `content=POST` or a path fragment. The `content` field includes the method, resolved URL when available and original path. The `source` field includes the script URL and line; inline-script line numbers are relative to the extracted script text. For example:

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

`verified: false` means no HTTP response has been received for the candidate. These candidates are not confirmed vulnerabilities. The optional `api_request` metadata requires no backfill; legacy serialization and deduplication identifiers are unchanged. Candidates with the same method, original path and resolved URL use existing site-level deduplication and retain the first source. Different methods remain distinct.

List and `/export/` endpoints share filters. Single, task-batch and asset-group-batch WIH text exports preserve the candidate source. Export formats for existing record types remain unchanged.

### WIH endpoint reachability and response collection

Enable both boolean options on the built-in rule, then run a WIH task:

```yaml
rules:
  - id: api_endpoint
    enabled: true
    probe: true
```

`probe` defaults to `false`. A disabled rule, a custom `pattern`, the string `"true"`, or `probe` alone does not enable requests.

- Only resolved GET and HEAD URLs with the original task site's exact scheme, hostname and effective port are requested. Cross-origin APIs, other ports and endpoints derived from a cross-origin document redirect remain candidates without expanding the request scope.
- Methods are preserved. POST, PUT, PATCH, DELETE, OPTIONS and UNKNOWN are not converted to GET. No body, page cookies, script authentication headers or netrc authentication is sent. Existing explicit WIH proxy and TLS verification settings apply. Extracted URL paths and query parameters are preserved.
- Up to 20 distinct `(method, url)` candidates are attempted per site; duplicates reuse the observation. Up to 3 same-origin redirects are followed, checking origin, loops and existing `api_endpoint` exclusions before each hop. Cross-origin, port/scheme changes and URLs containing user credentials stop redirect following.
- Connect/read timeouts are 3 seconds each. A 10-second candidate budget and a 60-second site budget are checked before requests and while reading bodies. DNS, connection and blocking reads remain subject to the network library; these budgets are not a hard limit on total task duration. Limits and failures preserve passive candidates and the existing WIH extraction completed before probing.
- Observations include the last received HTTP status/URL, UTC check time, elapsed time and redirect chain. Only Content-Type, Content-Length, Server and Allow headers are stored, capped at 1,024 characters each. Set-Cookie and other authentication headers are omitted. GET text responses retain at most 16 KiB before decoding, including JSON, XML and JavaScript. HEAD, binary and unknown media types have no captured body. Previews may contain sensitive data and remain behind existing WIH authentication. HTML and scripts are not executed or rendered.

Existing `/api/wih/` and `/api/asset_wih/` JSON lists return observations under `api_request.probe`. This stage does not add a response detail UI, endpoint screenshots or vulnerability classification. Text exports omit response bodies. Example metadata:

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

`state=responded` and `verified=true` indicate an HTTP response, including 401, 403, 404 and 5xx. They do not establish endpoint validity, unauthenticated access or a vulnerability. `redirect_stop` explains a stopped redirect. If a later hop fails, the last HTTP response remains, with `error` and `last_attempt_url` identifying the failed attempt; the final destination has not been verified. Body failures preserve headers and partial data, using `body_error` and `body_truncated`.

With no received HTTP response, `state=error` uses `timeout`, `connection_error`, `tls_error`, `request_error` or `time_budget`, without raw exception messages. Unattempted candidates use `state=skipped` with `reason` set to `unsupported_method`, `unresolved_url`, `outside_origin`, `excluded`, `site_quota` or `site_budget`. Asset-group monitoring refreshes existing observations without repeating new-record notifications. Passive scans after disabling probes preserve earlier observations; use `checked_at` for their age. All nested fields are optional and require no historical migration or backfill.

### Dimension Counts

`GET /api/asset_overview/count` returns counts for all 13 underlying asset collections in a single response to render per-tab badges without issuing one count request per dimension. An optional `scope_id` query parameter selects the counting scope:

- **Omitted `scope_id`**: Returns global aggregate totals across the 13 unprefixed collections (`site`, `domain`, `ip`, etc.).
- **With `scope_id=<asset_scope_id>`**: Returns per-dimension totals across the 13 `asset_*` collections (`asset_site`, `asset_domain`, etc.) for that asset group, matching the `total` of each `/api/asset_*/` list endpoint.

Example response:

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
> - Omitting `scope_id` returns **global unprefixed collection aggregates**, whereas providing `scope_id` returns **asset-group `asset_*` totals**; do not conflate the two scopes;
> - `counts` returns totals for all **13 underlying asset collections**; the UI views (**Asset search**, **Asset group details**, **Task details**, and the asset relationship profile drawer) consistently present **12 asset dimensions** (including `nuclei_result`), where `service` fuses Nmap port services and Python plugin services per `(ip, port_id)` endpoint on the backend (the `npoc_service` collection is retained for internal scan pipelines and backward compatibility). The **Services** badge matches `total` from `GET /api/service/` (deduplicated globally by `(ip, port_id)` across tasks) and `GET /api/asset_service/`;
> - Each dimension's counting rule matches its corresponding list endpoint — for example global `service` counts distinct `(ip, port_id)` endpoints across tasks, `cip` counts distinct C-blocks, and `stat_finger` counts distinct fingerprint names, rather than raw document counts;
> - A dimension whose count fails is returned as `null`. Clients should treat it as "unknown" and avoid rendering it as `0`.

### Unified Per-Endpoint Service Query & Export Conventions

`GET /api/service/` (global and per-task) and `GET /api/asset_service/` (per-asset-group) return unified per-endpoint `(ip, port_id)` records combining Nmap port service detection and Python sniffer plugin results:

- **Fusion & Calibration**: When both Nmap and Python sniffer plugins detect the same `(ip, port_id)`, they merge into a single record. Python protocol handshakes take precedence over weak service labels such as `unknown` or `tcpwrapped`, while preserving Nmap `product` and `version` metadata and recording detection origins in `sources` (`["nmap"]`, `["npoc"]`, or `["nmap", "npoc"]`). Global queries (omitting `task_id`) deduplicate across tasks by `(ip, port_id)`.
- **Filtering & Export**: Supports filtering by `service_name`, `ip`, `port_id`, `product`, `version`, and `sources` (`nmap` | `npoc`), with backward-compatible aliases (`service_info.*`, `host`, `port`, `scheme`). `GET /api/service/export/` and `GET /api/asset_service/export/` export deduplicated `scheme://ip:port` lists using the same query parameters.

### Asset Cascade Deletion & Derived Collection Recalculation

All 26 dimension delete endpoints (13 unprefixed `/api/<dim>/delete/`, including `POST /api/stat_finger/delete/`; and 13 prefixed `/api/asset_<dim>/delete/`) follow unified hierarchy cascading, scope isolation, and derived-collection rebuild rules:

- **Batch Limit & Input Validation**: Each delete call accepts at most **500** target identifiers (`_id` / `name` / CIDR); empty lists, invalid IDs, or oversized batches fail fast with code `400`. Both `GET /api/stat_finger/` and `GET /api/asset_stat_finger/` project `"_id"` equal to the fingerprint `name`, and their delete endpoints accept `_id` or `name`. `POST /api/cip/delete/` and `POST /api/asset_cip/delete/` accept both 24-hex ObjectIds and CIDR strings.
- **Scope Isolation (`source_type`)**:
  - **Asset Group Namespace (`/api/asset_<dim>/delete/`)**: Accepts optional `scope_id`; deletes strictly within that group's `asset_*` collections and tasks explicitly bound to it (`scope_id`, `sync_scope_id`, `synced_scope_id`, `options.scope_id`, `options.related_scope_id`, `options.scheduler_id`), leaving other asset groups and unbound standalone tasks intact.
  - **Task & Global Namespace (`/api/<dim>/delete/`)**: Accepts optional `task_id` and `source_type` (`"task"` default or `"global"`). Under `"task"`, deletion stays scoped to the target task (plus its explicitly bound asset group and sibling bound tasks if bound); pass `"source_type": "global"` explicitly to cascade across all asset groups and tasks.
- **Hierarchy Cascade & Derived Rebuilds**:
  - Deleting higher-level entities cascades down the asset hierarchy (e.g., deleting a domain removes its subdomains, sites, URLs, file leaks, vulns, Nuclei findings, WIH records, and orphan IPs unreferenced by surviving domains or CIDR configs; deleting an IP unbinds `domain.ips` while preserving the domain; deleting a `service` strips only the exact `(service_name, ip, port_id)` endpoints in that document without wiping unrelated IPs sharing the same service name; deleting `stat_finger` pulls the fingerprint entry from host sites while retaining the sites).
  - After mutation, derived collections (`cip` / `asset_cip`, `stat_finger` / `asset_stat_finger`, `service` / `asset_service`) are rebuilt from surviving host tables, affected `task.statistic` counters are recalculated, and cross-process dashboard/monitor caches are invalidated.
- **Asset Group & Scheduler Linkage**:
  - Deleting an asset group (`POST /api/asset_scope/delete/`) or removing seed targets (`GET /api/asset_scope/delete/`, `POST /api/asset_scope/update/`) synchronously cleans up its 13 `asset_*` collections, schedulers, and explicitly bound tasks; any in-flight enterprise recon update (`updating_icp_task_id`) is terminated and `icp_task.synced_scope_id`/`synced_scope_name` are unset while preserving `icp_task` and `icp_asset`. Renaming an asset group updates default-named `scheduler.name`, `icp_task.synced_scope_name`, and bound task scope-name fields.
  - Stopping or deleting continuous monitors (`POST /api/scheduler/stop/`, `POST /api/scheduler/stop/batch`, `POST /api/scheduler/delete/`) revokes active or queued tasks spawned by those schedulers (resetting `next_run_date` to `"-"` when stopped) and refreshes `asset_scope.domain_status`, while retaining historical completed tasks and archived assets; `GET /api/scheduler/` automatically enriches each returned item with its resolved `scope_name`.

### Multiple HTTP Status Code Filtering for Asset Lists

The site, URL, and file leak lists in Global Asset Search, Task Details, and Asset Group Details support multiple status selection, taking effect immediately upon selection or clearance. Status codes within the same field are matched with OR; other filters and `task_id` / `scope_id` are combined with AND. List queries, export endpoints, and site result sets share the same filter conversion:

- **Site Endpoints** (`/api/site/`, `/api/asset_site/`): Use `status__in=200,301,403`.
- **URL & File Leak Endpoints** (`/api/url/`, `/api/asset_url/`, `/api/fileleak/`, `/api/asset_fileleak/`): Use `status_code__in=200,403`.
- **Parameter Format & Validation**: Send a single comma-separated parameter containing integer codes from 100 to 599, with at most 500 entries. Empty strings, invalid values, and repeated parameters return HTTP 400. Omit the parameter to clear the filter.
- **Backward Compatibility**: Existing scalar parameters (`status=200`, `status_code=200`) remain supported; if both scalar and multiselect parameters are provided, their intersection is applied. Task execution status filters retain their existing format.

> [!NOTE]
> - Example: `GET /api/site/?task_id=<task_id>&status__in=200,403` selects sites from that task with status 200 or 403. The same parameters apply to `/api/site/export/` and `/api/site/save_result_set/`. For asset group queries, replace the parameter with `scope_id` and query `/api/asset_site/`.
> - Current support is restricted to status code field enumeration and field-level AND combinations; arbitrary boolean expressions or cross-field OR logic are not supported.

---

## 5. Error Code Conventions & Client Branching

| Code | Meaning | Typical Scenario |
| :--- | :--- | :--- |
| `200` | Business success | All successful responses |
| `104` | Task is running | Returned when deleting/operating on a running task; stop the task first |
| `999` | Parameter validation error | Missing/invalid parameters or exceeded limits (e.g. empty asset group ID list or more than 500 in a single request, invalid asset group/group ID) |

> [!NOTE]
> - `999` is a generic parameter-validation code; read `message` and `data.error` for the specific cause.
> - Clients should always keep a `default` branch in `switch/if` handling to avoid silently ignoring unmapped codes.
> - Error codes are not yet fully unified between task and enterprise-task endpoints (for example, enterprise task deletion may return `400` when the task is active); always verify against `/api/doc` and actual responses.

### WIH API request and response details

WIH lists in task details, global asset search and asset-group details provide an API details action for `record_type=api_endpoint`. All three views share one drawer, using the `api_request` and `api_request.probe` metadata already returned by the list. Opening it does not request the endpoint, capture a screenshot or rerun a probe.

- Request details preserve the original path, resolved URL, method, site, script source, client and line within the script.
- Not collected, HTTP response received, request failed and skipped are separate states. Statuses including 401, 403, 404 and 5xx remain HTTP observations and do not establish endpoint validity, unauthenticated access or a vulnerability.
- The last HTTP response URL and last attempted URL are shown separately, alongside redirect history, stop reasons, errors, collection time and duration. A failed later hop does not verify its destination.
- Headers and body previews are displayed as plain text and can be copied without executing HTML or scripts. Incomplete reads, truncation, empty bodies, HEAD and skipped body types have separate notices. Copying a preview does not fetch the full body.
- Legacy records retain their content and source without inferring methods or reachability. Changing task, asset group or tab, or leaving the view, closes the drawer to avoid mixing record contexts. Labels follow Chinese, English or Russian preferences; raw responses and sources remain unchanged.

Existing list queries, filters, counts, exports, deletion permissions and scans are unchanged. No historical migration is required.

---

## 6. MCP Protocol Conventions (Model Context Protocol)

ARL-Next integrates the Model Context Protocol (MCP 2024-11-05 specification) for AI agent collaboration. It supports both **Remote Native SSE** and **Local Stdio Bridge** integration modes.

> [!NOTE]
> For full-lifecycle penetration testing test case specifications and observability verification matrices, see [MCP Penetration Testing Test Cases](./MCP_PENTEST_TEST_CASES_en.md). The accompanying automated test suite is located at [verify_mcp_pentest.py](../tools/verify_mcp_pentest.py).

### Endpoint Matrix

| Path | Protocol & Method | Description | Authentication Channel |
| :--- | :--- | :--- | :--- |
| `/mcp/sse` | HTTP GET (`text/event-stream`) | Remote MCP SSE handshake endpoint; maintains persistent stream and yields `endpoint` events | `Authorization: Bearer <TOKEN>`, `Token: <TOKEN>`, or `?token=<TOKEN>` |
| `/mcp/message` | HTTP POST (`application/json`) | Remote MCP upstream channel; receives JSON-RPC 2.0 messages (requires `?sessionId=`) | Same as above |
| `/api/mcp/tools` | HTTP GET (`application/json`) | Return effective MCP tool definitions and schemas under current credential scopes and global policy | `Token: <TOKEN>` or `Authorization: Bearer <TOKEN>` |
| `/api/mcp/asset_profile` | HTTP GET (`application/json`) | Native multi-dimensional asset profiling REST endpoint across network/web/cert/vuln collections | `Token: <TOKEN>` or `Authorization: Bearer <TOKEN>` |
| `/api/mcp/enterprise_profile` | HTTP GET (`application/json`) | Native enterprise ecosystem asset profiling endpoint with adaptive target routing, overview metrics, and dimension drilldown | `Token: <TOKEN>` or `Authorization: Bearer <TOKEN>` |
| `/api/mcp/search_assets` | HTTP GET (`application/json`) | Multi-dimensional asset search endpoint (`site`/`domain`/`ip`/`vuln`, bounded by `max_search_limit`) | `Token: <TOKEN>` or `Authorization: Bearer <TOKEN>` |
| `/api/mcp/task_status` | HTTP GET (`application/json`) | Query scanning progress, execution state, and metric summary for a 24-hex task ID | `Token: <TOKEN>` or `Authorization: Bearer <TOKEN>` |
| `/api/mcp/create_scan_task` | HTTP POST (`application/json`) | Controlled scan task submission endpoint (requires `task:dispatch` scope and enabled tool switch) | `Token: <TOKEN>` or `Authorization: Bearer <TOKEN>` |
| `/api/mcp/stop_scan_task` | HTTP POST (`application/json`) | Controlled scan task cancellation endpoint (requires `task:dispatch` scope and enabled tool switch) | `Token: <TOKEN>` or `Authorization: Bearer <TOKEN>` |
| `/api/mcp/export_server` | HTTP GET / POST (`text/x-python`) | Export a client script; dedicated keys use POST JSON `raw_key`, GET uses the current account credential only | Login token or system API key |
| `/api/mcp/task_detail_export`| HTTP GET (`text/csv`) | Task detail CSV export across specific tabs with formula injection mitigation | `Token: <TOKEN>` |
| `/api/mcp/overview` | HTTP GET (`application/json`) | MCP Governance Center dashboard & call stats (call count, active keys, error count, live `sse_status`/`sse_sessions` probe) | `Token: <TOKEN>` |
| `/api/mcp/keys` | HTTP GET / POST (`application/json`) | Query and issue dedicated MCP API Keys (supports `keyword` and `status`: active/expired/revoked filtering plus `is_expired`) | `Token: <TOKEN>` |
| `/api/mcp/logs` | HTTP GET (`application/json`) | MCP invocation audit logs pagination (supports `time_range`: today/24h/7d, `status`: success/error/denied/abnormal) | `Token: <TOKEN>` |
| `/api/mcp/logs/export` | HTTP GET (`text/csv`) | Export filtered invocation audit logs to CSV | `Token: <TOKEN>` |
| `/api/mcp/config` | HTTP GET / POST (`application/json`) | Retrieve and update MCP global tool switches and rate-limit quotas | `Token: <TOKEN>` |

### Progressive Toolset Matrix

| Tool Name | Category | Primary Inputs | Description | Activation Condition |
| :--- | :--- | :--- | :--- | :--- |
| `get_asset_profile` | Read-only Profile | `target` (required), `task_id` (optional) | Unified asset intelligence correlation (IPs, ports, services, fingerprints, certs, vulns, leaks) | Enabled by default |
| `get_enterprise_profile` | Read-only Profile | `target` (required), `category`, `page`, `size`, `task_id` | Enterprise ecosystem profile and organizational structure (corporate background, ICP domains, mobile apps, mini programs, fast apps, official accounts, Weibo, investments) | Enabled by default |
| `search_assets` | Read-only Search | `query` (required), `asset_type`, `limit` | Searches sites, IPs, domains, or known vulnerabilities | Enabled by default |
| `get_task_status` | Read-only Status | `task_id` (required) | Inspects scanning progress, execution state, and metric counts | Enabled by default |
| `create_scan_task` | Controlled Dispatch | `name`, `target`, `policy_id` | Uses standard target validation and queue routing | Tool enabled in governance settings and `task:dispatch` scope |
| `stop_scan_task` | Controlled Dispatch | `task_id` (required) | Revokes the Celery task and records its stopped state | Tool enabled in governance settings and `task:dispatch` scope |

- Discovery and execution share tool switches and key scopes. Explicit database switches take precedence; `ARL_MCP_ENABLE_DISPATCH` supplies the write-tool default only when no switch is saved.
- Every SSE message revalidates the handshake credential. Revocation, deletion, expiry or rotation prevents an existing session from making further calls. Explicit headers must match the handshake credential. Expiry is evaluated in UTC.
- Dedicated Stdio keys discover permitted tools via `/api/mcp/tools` and access the matching tool REST endpoints under key scopes and global policy (`asset:read` for `/api/mcp/asset_profile`, `/api/mcp/enterprise_profile`, `/api/mcp/search_assets`, and `/api/mcp/task_status`; `task:dispatch` for `/api/mcp/create_scan_task` and `/api/mcp/stop_scan_task`), without acquiring general administrator REST access. SSE and all six tool endpoints share a per-credential fixed-minute quota. Denied tool calls count toward the quota. Exceeding it returns HTTP `429` with `Retry-After`, with only the first over-limit attempt per minute audited; an unavailable quota store returns `503`.
- Configuration generation requires a complete key. Newly created plaintext stays in the current page only; after reopening it, paste the previously saved full value. Masked prefixes are never credentials. Export with `POST /api/mcp/export_server` and JSON `{"host":"https://arl.example","raw_key":"<complete MCP key>"}`, keeping the account credential in the `Token` header. GET rejects `raw_key`.
- Mixed targets may create multiple scan tasks. `task_ids` contains all resulting IDs; the compatibility field `task_id` contains the first. Policy-bound asset scopes are validated before submission.

> [!NOTE]
> - Production Nginx reverse proxy routes `/mcp/sse` with unbuffered streaming and a 24-hour persistent timeout;
> - When accessing self-signed IP deployments, if the client drops connections due to TLS chain verification, use the local Stdio script (built-in certificate pinning) or import the server CA certificate into the operating system trust store.

- Invalid scopes, expiry values and tool switches are rejected. Partial policy updates retain omitted switches. Search filters are literal text and list page sizes are bounded to 1–100.
- MCP bodies are limited to 16 MiB, with at most 16 in-flight requests per session and 64 per service. Processing is enqueued before HTTP 202; accepted work remains counted after disconnect and undeliverable responses time out.

## 7. Task handling during backup restoration

After validating the entire archive, restoration pauses scan consumers and checks workers, active work and queued work. Pending work requires `force=true`. Forced restoration revokes active, reserved, scheduled and queued tasks, then waits for workers to confirm termination before `mongorestore --drop`. Consumers remain paused throughout restoration. Remaining messages belonging to the old data are cleared, unfinished tasks are marked stopped, and consumption resumes.

Unreachable workers, missing control acknowledgements or a stop timeout abort restoration. A failure after database replacement starts leaves consumers paused; inspect the data and restore error before restarting workers. Both Web and CLI restoration require responsive workers and a reachable broker for these checks.

`running_tasks` now counts unfinished scan and GitHub tasks, including queued tasks.

- Restoration checks that broker consumer counts reach zero and the original pool children exit, in addition to Celery acknowledgements. Backup and restore share an operation lock in their persistent directory.
- `force` must be a JSON boolean; the string `"false"` is rejected. Unfinished enterprise recon cannot be terminated through Celery and blocks restoration.
- Use a maintenance window with external database writers, new submissions and schedulers paused. This workflow does not isolate external writers or promise distributed consistency across node restarts or network partitions.

## 8. System Proxy Pool & Traffic Domain Routing

The proxy node pool, three traffic-domain policies (`osint` / `scan` / `intel`), and bypass rules are persisted in `system_config` (`_id: "proxy_config"`), while exit switching and WAF cooldown state live in `_id: "proxy_runtime_status"`. All proxy management endpoints require the administrator `Token` header.

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `GET` | `/api/system_config/proxy` | Fetch pool configuration (`password` cleared, with `has_password` and masked `display_url`), `osint` runtime status, and server capabilities (`pysocks_installed`, `protocols`, `presets`) |
| `POST` | `/api/system_config/proxy/nodes` | Create a proxy node (`protocol`: `http`, `https`, `socks5`, `socks5h`; `port`: `1–65535`) |
| `PUT` | `/api/system_config/proxy/nodes/<node_id>` | Update a node; omitting password preserves the existing credential, while `clear_password: true` clears it |
| `DELETE` | `/api/system_config/proxy/nodes/<node_id>` | Delete a node and detach it from domain policies; domains left without usable exits fall back to `direct_only` |
| `PUT` | `/api/system_config/proxy/policies` | Incrementally update `policies` (`osint`, `scan`, `intel`) and `bypass` (`bypass_private_cidr`, `bypass_domestic_webhooks`, `custom_no_proxy`) |
| `POST` | `/api/system_config/proxy/probe` | Probe connectivity using fixed allowlisted presets only (arbitrary custom URLs are rejected to prevent SSRF) |
| `POST` | `/api/system_config/proxy/cooldown/reset` | Reset `osint` cooldown state manually and notify `osint-service`, returning `osint_notified` and updated `runtime` |

- **Routing Modes & Domain Options**: Modes include `direct_only`, `failover`, `round_robin`, and `fixed_proxy`. `osint.cooldown_sec` accepts `30–3600` seconds (default `300`), and `scan` additionally exposes `apply_to_nuclei`, `apply_to_npoc`, and `apply_to_puppeteer`.
- **Probe Presets**: `POST /api/system_config/proxy/probe` restricts `preset` to `egress_ip`, `miit`, `tianyancha`, and `github`. For `miit`, an HTTP `521` challenge without WAF block signatures is treated as reachable (not blocked).
- **Runtime Fields & Compatibility**:
  - `GET /api/dashboard/sysinfo` (`data.proxy`) and `GET /api/icp/tyc_check` (`data.proxy_status`) expose the same runtime model (`state`: `direct_ok`, `backup_active`, `proxy_active`, `degraded_blocked`, or `proxy_unavailable`).
  - When `scan.apply_to_puppeteer` is enabled with credentialed nodes, Puppeteer falls back to direct egress (Chromium `--proxy-server` does not natively support proxy authentication) and reports the notice in `runtime.puppeteer_compat_warning`.
  - Legacy `proxy_url` updates via `POST /api/system_config/general` remain synchronized to the `legacy-default` node.

## 9. GitHub Monitoring & Leak Triage Endpoints

Code leak findings are deduplicated across one-time scans (`github_result`) and recurring policies (`github_monitor_result`) by `hash_md5`. Triage state persists in `github_triage`, and ignored repositories persist in `github_ignored_repo`. All endpoints require the administrator `Token` header.

| Method | Endpoint | Purpose |
| :--- | :--- | :--- |
| `GET` | `/api/github_result/overview/` | Query deduplicated leak findings with pagination; supports `source_type` (`all`/`task`/`scheduler`), `triage_status`, `group_by` (`flat`/`repo`), `only_ignored`, and field filters |
| `GET` | `/api/github_result/stats/` | Return deduplicated triage counters (`pending`, `confirmed`, `false_positive`, `total`, `ignored_repos`, `running_tasks`, `running_schedulers`) |
| `POST` | `/api/github_result/triage/` | Update triage status (`pending` / `confirmed` / `false_positive`) and `note` by `hash_md5s`, propagating to existing hits and future scans |
| `GET` / `POST` | `/api/github_result/ignored_repos/` | List, add, or remove ignored repositories (`action`: `add` / `remove`, `repo_full_names`); ignored repos are hidden from default triage and muted from recurring alerts |
| `GET` | `/api/github_result/export/` | Export filtered deduplicated findings (`format`: `csv` / `json`, capped at 50,000 rows, with CSV formula prefix neutralization) |
| `POST` | `/api/github_scheduler/run/` | Trigger immediate execution for one or more recurring policies (`_id` list) |
| `GET` | `/api/github_threat/token_status` | Probe GitHub API via the `intel` proxy domain and return both `core` and `search` rate-limit quotas |
| `GET` | `/api/github_threat/hackers_history` | Query tools discovered from tracked researchers with optional `github_id` and `q` (repo/description/language) filters |

- **Dashboard & Batch Alignment**: `github_monitors` in `GET /api/dashboard/stats` counts `github_scheduler` documents; `POST /api/github_threat/tools_target` and `POST /api/github_threat/hackers_target` accept both single items and batch lists (`repo_urls` / `github_ids`).

## 10. Notifications & Nuclei Vulnerability Alert Callbacks

Global notification settings are managed via `GET` / `POST /api/system_config/general` (administrator `Token` header required) across DingTalk, Feishu, WeCom, Telegram, SMTP email, and Global Webhook callbacks.

| Field | Type | Description |
| :--- | :--- | :--- |
| `push_options` | `string[]` | Subscribed event list, now including `nuclei_vuln` (Nuclei vulnerability alert); existing configurations are backfilled once during startup migration while preserving subsequent opt-outs |
| `nuclei_push_severities` | `string[]` | Severity allowlist for Nuclei alerts (`critical`, `high`, `medium`, `low`, `info`), defaulting to `["critical", "high", "medium", "low"]` |

- **Trigger Timing & Deduplication**:
  - Regular domain/IP scans, risk cruising (`RiskCruising`), add-asset-site tasks, and scope monitoring tasks dispatch alerts after all scan phases and asset synchronization complete (`status = "done"` and `end_time` recorded). Each task sends one aggregated alert ordered by severity with up to 20 detail items (WeCom text payloads are truncated cleanly at 2,000 UTF-8 bytes).
  - Scope-bound and monitoring tasks push only newly discovered vulnerabilities absent from `asset_nuclei_result`, whereas standalone unscoped tasks push all matched findings of the task. Manual task sync (`POST /api/task/sync/`) and online template dry-runs (`POST /api/nuclei/template/test/`) do not emit alerts.
- **Global Webhook `nuclei_vuln` Payload**: When `webhook_url` is configured, `nuclei_vuln` is subscribed, and filtered findings are non-empty, ARL-Next sends a `POST` request to `webhook_url` (with `Token: <webhook_token>` header when configured):

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
  "scope_data": { "name": "Core Asset Scope", "scope_type": "domain" },
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

> Each Webhook callback includes up to 100 entries in `nuclei_results`; when exceeded, `summary.truncated` is `true`.

## 11. Custom Nuclei Templates & Online Single-Target Dry Run

Custom template lifecycle and online debugging are exposed under `/api/nuclei/template/*` (valid `Token` header required):

| Endpoint | Method | Description |
| :--- | :--- | :--- |
| `/api/nuclei/template/create/` | `POST` | Creates a custom YAML template; accepts `content` (required) and `enable` (optional boolean, default `true`), returning `template_id` and `enable` |
| `/api/nuclei/template/update/` | `POST` | Updates an existing custom template with `template_id` and `content`; supports renaming via YAML `id` (returns `code: 999` on ID conflict) |
| `/api/nuclei/template/import/` | `POST` | Bulk imports `.yaml`/`.yml` or `.zip` templates; runs static checks followed by batch `nuclei -duc -no-color -validate` semantic validation (invalid items are rejected into `fail_details`) |
| `/api/nuclei/template/test/` | `POST` | Runs an online single-target dry run (30-second timeout); accepts `target` (required) and `content` (or stored `template_id`) |

- **Template Static & Semantic Validation Contract**:
  - `create`, `update`, and `import` validate top-level YAML mapping, `id` (`a-zA-Z0-9_.-`), `info.name`, `info.author` (string or non-empty list of strings), `info.severity` allowlist (`info`, `low`, `medium`, `high`, `critical`, `unknown`), and at least one non-empty protocol/workflow section (`http`, `requests`, `dns`, `tcp`, `network`, `ssl`, `websocket`, `whois`, `code`, `javascript`, `headless`, `file`, `workflows`).
  - When the `nuclei` binary is present on `PATH`, semantic validation additionally runs `nuclei -duc -no-color -validate` (falling back to static checks when absent). Validation errors and duplicate IDs return `code: 999` on `create`/`update`, while failed items in `import` are rejected and reported in `fail_details`.
- **Online Single-Target Dry Run (`POST /api/nuclei/template/test/`)**:
  - **Protocol-Aware Target Normalization**: Rejects whitespace, newlines/control characters, and leading `-` arguments. Prepends `http://` for `http`/`headless` targets without a scheme (preserving `ws(s)://`/`http(s)://` for `websocket`), and strips unintended `http(s)://` schemes and paths for `dns`/`tcp`/`network`/`ssl`/`whois` templates.
  - **Proxy Alignment & Output Cleaning**: Reuses the `scan` domain proxy policy (`apply_to_nuclei`) with credentials masked in logs and output; strips ANSI escape codes and extracts structured matches via `-jle` (falling back to plain stdout parsing on legacy Nuclei builds).
  - **Response Fields**: On success (`code: 200`), `data` contains `matched`, `matched_count`, `findings` (`template_id`, `name`, `severity`, `matched_at`, `curl_command`, `extracted_results`), `target`, `output`, `returncode`, and `cost_seconds`. When `nuclei` exits non-zero, the endpoint returns `code: 999` with a concise error summary in `message` while preserving diagnostic `output` and `returncode` in `data`.
- **ASM Channel Isolation & Protocol-Based Target Routing**:
  - `nuclei_config` (supported by `POST /api/task/`, `POST /api/policy/add/`, and `POST /api/policy/edit/`) accepts `include_community` (boolean, default `true`; set `false` for custom-only scans), `severity` (community channel allowlist, default `["low","medium","high","critical"]`), `exclude_blacklist` (boolean, default `true`, community channel only), `custom_template_mode` (`all_enabled` / `selected` / `tags` / `none`), `selected_custom_templates`, `selected_tags`, and `extra_exclude_ids`.
  - The community channel enforces `-tags cve,http`, policy `severity`, and global `-eid` blocklist rules. Custom template channels bypass community `-tags`, `severity` (allowing `info`/`unknown` templates to run), and the global blocklist, routing ASM assets by protocol: `http`/`websocket` target alive web sites (including WIH-discovered sites), `tcp`/`network`/`ssl`/`javascript` also target discovered open `ip:port` endpoints, and `dns`/`whois` also target discovered subdomains. `code`, `headless`, `file`, and `workflows` templates are currently supported for dry runs only and are skipped before automated ASM execution with warning logs.
  - Channels are fault-isolated: an error in one channel preserves findings from succeeded channels, and channels with zero runnable templates or zero targets are skipped cleanly.
  - Findings record `template_source` (`custom` or `community`), filterable via `GET /api/nuclei_result/` and `GET /api/asset_nuclei_result/`. `POST /api/task/policy/` accepts an optional `related_scope_id` so risk cruising tasks launched from an asset group sync findings back to `asset_nuclei_result` and `asset_vuln`.
