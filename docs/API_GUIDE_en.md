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

- **Header Authentication (Recommended)**: Pass the token in the HTTP header when authentication is enabled:
  ```http
  Token: <your-token>
  ```
- **Query Parameter (Fallback)**: The backend also supports `?token=<your-token>`. However, query tokens are often recorded in Web server access logs, reverse proxies, and browser histories. **Headers are strongly recommended**.
- **Security Red Line**: Never commit real API tokens to public version control, GitHub issues, publicly shared debug logs, or terminal command histories.
- **Unauthenticated Environments**: If authentication is explicitly disabled in the system configuration for air-gapped or testing environments, token verification is bypassed. Always ensure platform authentication and gateway access controls are enforced on exposed networks.

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
| **Delete Task** | `POST /api/task/delete/` | JSON: `{"task_id": ["<task_id>"], "del_task_data": false}` | ⚠️ **State Constraint**: Only tasks in terminal states (`done`, `stop`, `error`) can be deleted. Running tasks return error code `104` ("Task is running") |
| **Restart Task** | `POST /api/task/restart/` | JSON: `{"task_id": ["<task_id>"]}` | Only stopped/finished tasks can be restarted |

### Associate New Scan Tasks with Asset Groups

When creating a reconnaissance task, optionally select an existing asset group. The selector supports name search and pagination. Completed tasks use the existing asset synchronization pipeline; this does not create periodic monitoring or extend the group's configured scope.

`POST /api/task/` accepts an optional JSON field `related_scope_id`, for example:

```json
{"name": "Boundary discovery", "target": "www.example.com", "related_scope_id": "<asset_scope_id>"}
```

Before creating any tasks in a batch, the backend checks group existence and verifies that all domain, IP, or CIDR targets belong to its scope. Existing target validation and blacklist checks remain active. Omitting the field preserves ordinary scan behavior. Restarting an associated task retains the group ID, revalidates the current scope, and clears the new task's previous sync outcome.

The task list distinguishes synchronization after completion, queued synchronization, active synchronization, success, and failure. Failure reasons appear in a tooltip. Scan results and synchronization status are retained independently; selecting a group does not indicate successful synchronization. The group and target scope are checked again before synchronization.

`POST /api/task/sync/` supports finished domain and IP tasks with `task_id` and `scope_id`. Full scope validation still applies. The request records a queued state before dispatch and records dispatch errors. Both automatic and manual synchronization record `synced_scope_id` / `synced_scope_name` on success or `sync_error` on failure, without automatic retries.

Task creation supports scoping by asset group; Nuclei YAML/ZIP import is provided by the PoC management page and is not duplicated here.

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
  - `running`: Includes intermediate stages (port scan, service recognition, risk巡航, etc.).
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

### Global Dimension Counts

`GET /api/asset_overview/count` returns the **global totals** for every asset dimension listed above in a single response. It is intended for rendering per-tab count badges without issuing one count request per dimension.

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
> - The counts are **global aggregates** and are **not** the same scope as the `task_id` / `scope_id` filtered list endpoints. Do not use them to infer the asset volume of a single task or asset group;
> - Each dimension's counting rule matches its corresponding list endpoint — for example `cip` counts distinct C-blocks and `stat_finger` counts distinct fingerprint names, rather than raw document counts;
> - A dimension whose count fails is returned as `null`. Clients should treat it as "unknown" and avoid rendering it as `0`.

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
