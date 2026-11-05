# Changelog (English)

This document records all major version evolution, new features, performance optimizations, and bug fixes of the ARL-Next project.

> 中文版：[CHANGELOG.md](./CHANGELOG.md)

---

## [v1.4.5] - 2026-11-05

### 🚀 New Features
- **Asset scope feature card selector and Tianyancha recon UX enhancements**: overhauled the scope selection workflow in `AssetScope.vue` with an interactive card-based mode selector (supporting smooth switching between domains, IPs, and asset groups with high-contrast active states, capability tags, and descriptions); enhanced the `TycTaskModal.vue` Tianyancha recon dialog with optimized ICP deduplication layout and summary metrics; fully updated trilingual dictionaries across Chinese, English, and Russian (`assets.zh-CN.js`, `assets.en-US.js`, `assets.ru-RU.js`).

### 🛠️ Performance & Refactoring
- **Policy configuration batch PoC validation and chunked paginated rendering**: addressed UI latency under thousands of PoC plugins by introducing the `/api/policy/plugin/verify-batch` backend endpoint with concurrent chunked execution, timeout guards, and robust status mapping; re-engineered `PolicyDetail.vue` with paginated chunked rendering and decoupled `Set`-based lookups, eliminating deep reactivity overhead and ensuring microsecond-level batch selection responsiveness without main thread blocking; delivered automated backend and frontend test suites (`test_policy_plugin_batch.py` and `policyDetailPocPerformance.test.js`).

### 🐛 Bug Fixes & Hardening
- **System settings initial dirty-state debouncing and recommended concurrency mapping**: resolved premature "unsaved changes" banner flickering in `SystemSettings.vue` caused by asynchronous data arrival and mismatched reactive baselines; fixed field mapping in `applyRecommended` for performance concurrency sliders; introduced uninitialized state gating and precise dirty-tab navigation, accompanied by the `systemSettingsDirtyState.test.js` test suite.
- **MCP Center dark mode adaptation and platform theme alignment**: corrected styling discrepancies in `McpCenter.vue` under dark mode, revamping CSS variables for top status bars, metric cards, instruction panels, and audit log drawers to strictly comply with platform dark theme tokens.

### 🛡️ Security & Configuration
- **Deployment workflow step-by-step guidance and collapsible code blocks**: refined production installation guides across `README.md`, `README_en.md`, `docs/QUICKSTART.md`, and `docs/QUICKSTART_en.md` with explicit single-line execution prompts and collapsible snippet sections, mitigating operational errors during container setup and cold starts.

---

## [v1.4.4] - 2026-11-03

### 🚀 New Features
- **Native asynchronous MCP (Model Context Protocol) governance center**: introduced standard Model Context Protocol backend endpoints supporting native SSE direct streaming (`/mcp/sse`) and Stdio bridge dual modes; registered two core intelligence tools: `get_asset_profile` (two-stage adaptive drill-down by asset category with token budget controls) and `get_enterprise_profile` (enterprise ecosystem mapping); delivered a dedicated "MCP Center" frontend console featuring API key lifecycle management, sub-millisecond execution audit logging, token consumption dashboards, and whitelist access control; accompanied by automated pentest suites (`tools/verify_mcp_pentest.py`) and security validation test cases.
- **Group scope lifecycle governance with asset group dissolve and transfer**: overhauled group entity lifecycle, enabling safe group deletion along with options to either dissolve underlying asset groups (reverting to standalone scope) or transfer them to another designated parent group; upgraded UI hierarchy views and added secondary confirmation guardrails for irreversible operations.
- **Externalized alive probe port dictionary**: decoupled scanner alive host probing baselines from hardcoded routines into `backend/app/dicts/port_alive.txt`; purged conflicting high-false-positive ports (such as 843) while appending modern web, API, and microservice baseline ports; integrated automatic file seeding, deduplication, and normalization in the update pipeline.

### 🛠️ Performance & Refactoring
- **Hardware gateway probe resilience and bidirectional service enrichment**: enhanced `fetchSite` and `checkHTTP` probes to handle hardware gateways and reverse proxies returning 401/403 authorization challenges, empty payloads, or high latency; implemented bidirectional metadata feedback from web probing back into underlying service records to prevent missing assets under restrictive network filtering.
- **Asset search compact layout and dashboard single source of truth**: refactored the asset search interface into a compact grid layout with a smooth collapsible multi-dimensional filter bar for improved screen density; overhauled dashboard metric aggregation pipelines to decouple queue pending states from active execution counters, enforcing a single source of truth across task lifecycles.
- **System settings view modularization and bundle optimization**: decomposed the monolithic `SystemSettings.vue` into focused modular components (`BackupRestorePanel`, `CdnRulePanel`, `SystemUpdatePanel`), decoupling oversized routes and optimizing frontend bundle chunking for faster production loading.

### 🐛 Bug Fixes & Hardening
- **WIH recon heartbeat persistence and detail inspection drawer**: implemented periodic heartbeat updates during long-running WIH API discovery runs to prevent scheduler timeouts; added an inspection drawer displaying raw HTTP request paths and response payloads with sensitive data masking and full trilingual localization.
- **Task list filter enum synchronization and navigation fixes**: fixed route query synchronization when filtering tasks across multiple compound states; rectified option reset glitches during navigation from asset groups or enterprise recon, keeping filter states strictly bound to pagination.
- **Legacy Linux kernel container runtime compatibility**: refined frontend Nginx container startup probes and configuration profiles for hosts running older kernels (< 4.19), addressing container hang conditions and self-healing startup failures.

### 🛡️ Security & Configuration
- **Backup archive staging sandbox and directory traversal prevention**: re-engineered the backup restore engine with `backup_archive.py` and `backup_workers.py` to enforce strict archive path and filename verification, isolating decompression within a temporary staging sandbox to eliminate path traversal risks; added global mutual exclusion locks during restore executions.
- **Session token expiration lifecycle and sensitive asset authentication**: introduced bounded `token_expire_at` grace periods and MongoDB TTL index auto-cleanup for user session tokens; enforced authentication headers and signed download tickets (`download_ticket`) for asset screenshot previews and updater binaries; fortified IP blacklist parsing against syntax errors.
- **Production image toolchain enrichment and GeoIP population refinement**: bundled essential `tools/` CLI suites and `mongodump` binaries inside `Dockerfile.prod`; refined GeoIP volume pre-population to guarantee smooth container initialization in offline or air-gapped environments.

---

## [v1.4.3] - 2026-10-23

### 🚀 New Features
- **One-click full system backup and clean restore**: implemented multi-worker state-synchronized `BackupProgressTracker` covering 49 MongoDB collections, plugins, custom dictionaries, and optional screenshots; supports `--drop` clean-slate overwrite restore with automated index reconstruction and cache invalidation; provides `/api/backup/*` RESTful streaming endpoints; adds "Data Backup & Restore" tab in System Settings with live progress and safe confirmation guardrails; introduces `tools/arl_backup.py` CLI utility for transparent execution across both host and container environments.
- **Web Info Hunter (WIH) API candidate extraction and same-origin reachability probe**: enhanced static analysis to recognize fetch and axios request candidates from JavaScript syntax (extracting template literals, relative endpoints, and HTTP methods); added controlled same-origin reachability probing (`api_probe`) capturing response status and truncated body previews with automatic stripping of sensitive headers and cookies; updated export utilities to include detected API endpoints and methods.
- **Multilingual internationalization framework (ZH / EN / RU)**: deeply integrated `vue-i18n` with instant switching across Simplified Chinese (zh-CN), English (en-US), and Russian (ru-RU), covering login, dashboard, task management, asset scope, policy configuration, threat radar, and system settings; decoupled task status terms from phase mappings to prevent parameter mutation across locale changes.

### 🛠️ Performance & Refactoring
- **Tiered rate-limit and circuit breaker architecture for MIIT ICP queries**: built a multi-tiered breaker isolating list queries from detail requests, featuring healthy proxy awareness, request-level physical pacing (8-15s inter-subject delay), automated ban proxy ejection, and precise client IP attribution under KnownSec WAF; added automatic cool-down retry to prevent permanent task skipping.
- **Quick App (Kapp) multi-identifier query and schema normalization**: added standard column rendering and default update time sorting for Quick Apps in enterprise task details; decoupled entity licence and service licence multi-way compound matching; improved openpyxl virtual workbook export compatibility.
- **Task detail collection scope alignment**: detail queries and deletions uniformly resolve against asset-group data sources, mitigating delete endpoint exceptions while preserving collection namespace fallbacks.

### 🐛 Bug Fixes & Hardening
- **Enterprise recon auto-grouping and navigation stabilization**: fixed backend scheduler anomalies in enterprise panorama auto-grouping, suppressed duplicate confirmation prompts when switching asset group tabs, and improved Tianyancha geographical boundary tips.
- **Backup dashboard polling stabilization**: resolved progress indicator flickering to 0% and long wait stalls during large asset archive packing, improving state takeover upon reconnection.
- **Global status terminology standardization**: corrected variant status expressions across locale files to strictly adhere to the project baseline vocabulary (`running` In progress / `waiting` Queued / `done` Completed / `stop` Stopped / `error` Failed).

### 🛡️ Security & Configuration
- **Nginx gateway security upgrade**: upgraded frontend production Nginx to 1.30.6, addressing upstream security vulnerabilities and unbuffering streaming for large backup archives.
- **Dedicated persistent volume for backups**: added `arl_backups` named volume in `docker-compose.prod.yml` to isolate and persist backup archives across container recreation, keeping `mongo_data_v7` fully compatible.
- **Recommended hardware specs documentation**: clarified 4-core CPU and 4GB RAM minimum recommended hardware baseline in both Chinese and English README and quickstart documentation to safeguard multi-task concurrency and large-scale asset discovery.

---

## [v1.4.2] - 2026-10-19

### 🚀 New Features
- **Enterprise panorama recon with backend-driven auto-grouping**: Tianyancha and MIIT ICP lookups merged into enterprise panorama recon (panorama dual-track / official filing). Registered company names auto-match Tianyancha GIDs and upgrade to dual-track pivoting; auto-grouping intents (`auto_group`, `auto_group_scan`, scan policy and interval) are consumed by the backend scheduler instead of browser polling, with in-flight tasks backfilled by incremental migration; stale `updating_icp_task_id` markers are promoted or cleaned up according to task terminal states.
- **Asset-group association for ordinary scan tasks**: the new recon task form offers an optional related asset group, with results synced to it on completion; fan-out is previewed honestly (one task per domain, merged task for IP/CIDR); the task list shows the linked group and sync state, with sync dispatched through a unified group selector.
- **Multi-select HTTP status filtering**: site assets support combined multi-status filtering (`status__in` / `status_code__in`); invalid input fails fast to narrow query scope; coexisting legacy single-value conditions intersect, independent of parameter order.
- **Searchable system settings with credential overview**: keyword search jumps to target tabs with highlighting; cross-tab credential states collapse into one summary line (folded by default); unsaved changes stay visible with jump links; the update page adds open-source repo and release links.
- **Aggregate status filters aligned with statistics**: task-list metric cards and filters share backend semantics (`active` = non-terminal, `abnormal` = `error + stop`), keeping card counts equal to filtered results; phase states render uniformly as "进行中 · \<phase\>".

### 🛠️ Performance & Refactoring
- **Settings IA regroup with concurrency governance**: settings converge into recon intel, dictionaries, scan & concurrency, notifications, and version & update; the GitHub monitor queue joins concurrency governance with peak-model recommendations; the three queue values are defined as Worker process counts, distinct from per-task blasting concurrency; omitted fields keep stored values on save to avoid silent overwrites; pool scaling retries against runtime process counts and reports observed convergence.
- **On-demand GeoIP with image decoupling**: `ip2region` / `GeoLite2` databases no longer ship in images; `tools/fetch_geoip.py` fetches and verifies them into the `arl_geoip` named volume at deploy time (GeoLite2 skipped with degraded service without `MAXMIND_LICENSE_KEY`); memory-swap observation tooling and per-queue OOM priorities added.
- **Config template / runtime config split**: effective runtime config separated from committed templates; environment markers and credentials in test scripts injected via environment variables; microservice sources and committed build artifacts excluded from build context; runtime screenshot dir untracked.
- **Nuclei engine capability caching**: redundant startup probes merged with cached engine capabilities, reducing repeated probe overhead.

### 🐛 Fixes & Hardening
- **Nuclei result attribution and failure visibility**: results keep target ports so findings from different services are not merged; scan process failures are reported with temp files cleaned up; recon abnormal paths converge on terminal-state and log observability.
- **Task sync chain hardening**: sync uses unified scope validation for domain and IP tasks, atomic claim before dispatch to avoid duplicate delivery, error state with cause preserved on dispatch failure; task-detail data namespaces corrected with global source fallback; malformed task IDs return not-found instead of degrading to system errors.
- **WIH builtin rules take effect**: missing builtin extraction rules backfilled so enabling them works; external asset text written as literal XLSX cells to block formula injection.
- **OSINT dispatch/cancel semantics**: dispatch params validated per task type with Tianyancha target field backfilled; cancellation no longer misreported as crashes; dispatch confirmation and cancellation semantics added before task deletion.
- **MCP self-signed deployment availability**: default certificate verification breaking clients on self-signed deployments mitigated — local certificates auto-trusted on loopback only with chain verification kept, remote deployments via `ARL_CA_BUNDLE`; both client copies kept in sync.
- **Frontend interaction convergence**: panorama recon advanced params always visible; dangerous-operation defaults, statistics semantics, and status terms unified; asset deletion target namespaces corrected.

### 🛡️ Security & Configuration
- **TLS verification for push channels**: Telegram, DingTalk, Feishu, and WeCom push enable TLS certificate verification, narrowing MITM exposure.
- **MongoDB fd limit raised**: `docker-compose.prod.yml` sets `nofile` to 65535 to avoid official warnings under concurrent queries over many collections; new `arl_geoip` named volume; existing persistent volume names unchanged.
- **Smooth DB evolution**: incremental migrations backfill missing concurrency fields (fill-missing-only), in-flight recon auto-group intents, and stale grouping-state healing; scope index gains `updating_icp_task_id`; every step isolated by single-step fault tolerance so one failure never blocks startup.
- **Doc wording convergence**: API conventions moved to `docs/API_GUIDE.md` (bilingual), README keeps global capabilities and quick entries; capability claims not matching implementation removed; asset-group terminology unified with community templates added; cert/credential ignore rules completed and verified.
