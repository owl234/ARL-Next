# Changelog (English)

This document records all major version evolution, new features, performance optimizations, and bug fixes of the ARL-Next project.

> 中文版：[CHANGELOG.md](./CHANGELOG.md)

---

## [v1.5.0] - 2026-11-19

### 🚀 New Features
- **Unified multi-protocol proxy pool and three-domain traffic routing**: added `proxy_service.py`, `osint_service/proxy_router.py`, and `ProxyManagePanel.vue` supporting `http`/`https`/`socks5`/`socks5h` proxy nodes with independent routing policies (`direct_only`, `fixed_proxy`, `failover`, `round_robin`) across `scan`, `osint`, and `intel` domains, private CIDR / domestic webhook / custom `NO_PROXY` bypass rules, and per-row multi-preset liveness probing; centralized 5-state egress status labels in `proxyStatus.js`.
- **Dedicated Nuclei vulnerability push, custom template ASM multi-protocol routing, and online dry-run debugging**: added the `nuclei_vuln` push channel and `nuclei_push_severities` filtering dispatched after terminal task state persistence; routed custom templates across ASM `web`, `network`, and `dns` buckets with support for custom-only policies (`include_community=False`), isolated community vs. custom execution channels, and `template_source` provenance tracking; added online single-target dry-run debugging (`/api/nuclei/template/test/`) and a standalone Nuclei vulnerability capsule in `TaskList.vue`.
- **Port-scan host discovery modes and task/policy website screenshot toggle (`site_capture`)**: introduced configurable `host_discovery_mode` (`auto` adaptive matrix / `skip` `-Pn` / `probe` forced discovery); added the `site_capture` toggle across tasks, policies, and presets (enabled by default for backward compatibility, skipping headless browser capture when disabled and excluding `catch_all_sites` default backends when enabled) with existing asset-group screenshot preservation in `SyncAsset`, empty-screenshot diff suppression in `monitor_diff`, and reference-checked cleanup in `DeleteTask`.
- **Enterprise OSINT batch stop, checkpoint resume, in-place detail backfill, and fast-app (`kapp`) support**: added `/api/icp/batch_stop/`, `/api/icp/resume/`, and `/api/icp/backfill_details/` endpoints and UI workflows; added fast-app (`kapp`) discovery, cross-source (`tyc+icp`) deduplication and merging, and adaptive dynamic table columns.
- **GitHub monitor triage deduplication workflow and MCP full-lifecycle tool governance**: added `github_triage.py`, `/api/github_result/*` triage status management, noisy-repository ignore lists, CSV export, manual scheduler triggers, and the `GithubCodeReader.vue` code viewer; expanded MCP governance with `/api/mcp/tools`, `search_assets`, `task_status`, `create_scan_task`, and `stop_scan_task` endpoints, scope switches, and synchronized Stdio bridge scripts.

### 🛠️ Performance & Refactoring
- **System Settings five-domain capsule architecture and route-leave guard overhaul**: redesigned `SystemSettings.vue` into five workflow domains with a unified `SECTION_SPECS` / `dirtySections` registry and a 3-choice leave confirmation modal (Stay / Discard & leave / Save all & leave); removed redundant credential banners, proxy placeholder cards, and the legacy `/merged_general` endpoint; unified top-right primary create button placement and trilingual action verb copy across list views.
- **Paginated OSINT progress heartbeats, incremental persistence, and bounded detail enrichment**: updated `job_runner.py` and `ymicp.py` with per-page progress heartbeats, incremental page persistence, and bounded per-batch detail enrichment (`detail_max_items=100`) paired with on-demand full backfill.

### 🐛 Bug Fixes & Hardening
- **OSINT multi-exit isolation, checkpoint resume cleanup, and crash recovery**: isolated TYC vs. MIIT cooldown scopes in `run_tyc_job` while sharing process-wide per-exit rate-limit locks; switched `blocked_exits` persistence to atomic MongoDB dot-key updates; cleaned partial uncompleted dimensions before resuming `run_icp_job` and set `recon_checkpoint.completed=True` upon completion; cleared stale `detail_backfill_running` locks and restored prior terminal statuses in `reconcile_orphan_tasks` and `_schedule_abort`; hardened `ymicp` non-captcha detail failover, detail WAF cooldown estimation, concurrent `detail_context` snapshots, TYC `403/429` failover, `_stop_single_icp_task` retryability, and asset-group organization update state isolation.
- **Production deployment `systemd 219` compatibility and release notes cache fix**: fixed `MainPID` extraction without `--value` and added 3-layer port 8888 updater self-kill protection in `start-prod.sh` on CentOS 7 (`systemd 219`); fixed empty release notes rendering, cross-worker shared caching, and bilingual fallback in `SystemUpdatePanel.vue` and `/api/system_config/check_update`.
- **Frontend KeepAlive lifecycle and notification completeness fixes**: fixed global listener and timer cleanup, discard-and-leave state resets, and background polling resumption across `SystemSettings.vue`, `ProxyManagePanel.vue`, `McpCenter.vue`, and `GithubManage.vue` under `<keep-alive>`; aligned `CdnRulePanel.vue` delete confirmation copy with instant persistence; auto-populated `task_name` in `sync_asset` and emitted task completion summaries on `nuclei_only_fallback`.

### 🛡️ Security & Configuration
- **Nuclei argument allowlisting, multi-protocol template validation, and dry-run SSRF guards**: enforced strict `nuclei_config.severity` allowlists across `/api/task/`, `/api/policy/*`, and `NucleiScan`; inspected all YAML protocol blocks to prevent hybrid templates containing `code`/`headless`/`file`/`workflows` from bypassing ASM or dry-run restrictions; blocked loopback, cloud metadata (`169.254.169.254`), and internal container hostnames in online dry-run while respecting `BLACK_IPS`/`FORBIDDEN_DOMAINS`; passed authenticated proxies via `0o600` temporary files and masked `CalledProcessError` commands; switched community template path checks to `os.path.commonpath` and re-enabled TLS verification for template ZIP downloads.
- **Proxy credential redaction, GitHub radar input validation, and MCP boundary hardening**: masked proxy credentials and TYC tokens in `GET /api/system_config/general` and `run_recon_job` logs; enforced fail-closed behavior for OSINT `fixed_proxy` when bound nodes are disabled; validated string payloads and `interval` bounds in `github_threat` endpoints; clamped pagination in `MCPTaskDetailExport`, prioritized `X-Real-IP` and ignored `Basic` auth header shadowing in MCP SSE, and downgraded Stdio bridge tool lists to read-only tools on remote sync errors; synchronized bilingual `README`, `docs/QUICKSTART*.md`, `docs/API_GUIDE*.md`, and `mcp-server` documentation.

---

## [v1.4.6] - 2026-11-14

### 🚀 New Features
- **Attack-chain asset profile drawer overhaul and task sync incremental summary**: updated `ChainDrawer.vue` to apply `rootClassName` for theme padding and background alignment, adding dual sticky headers with a scroll-spy anchor rail, a default toggle hiding empty sections, loading skeletons, 10-row pagination, and trilingual support; converted `GroupAssetsDetail.vue` profile triggers into persistent lightweight pill buttons; persisted `sync_summary` (`total_new` / `total_update` and category breakdown) in `sync_asset` and rendered incremental sync badges alongside tiered phase failure notices (`phase_errors`, `error_msg`) in `TaskList.vue`.

### 🛠️ Performance & Refactoring
- **Packet-phase concurrency leasing and DNS resolution resilience**: added `packet_lease.py` combining atomic MongoDB leases with local `flock` fallback around packet-heavy `massdns` and `port_scan` phases (bounded by `system_config` or `1` slot by default, overridable within `1–16` via the internal `ARL_PACKET_PHASE_SLOTS` environment variable) with startup and failure cleanup of stale slots; extracted shared `dns_client` featuring public DNS rotation, transient timeout retries distinct from `NXDOMAIN`, recursive CNAME tracking, and reuse of pre-resolved `massdns` records to mitigate silent drops under concurrency.
- **Dual-state worker concurrency convergence and idle shrink fix**: exposed `pending_convergence` and `pending_nodes` runtime metrics in `/api/system_config/performance` and `SystemSettings.vue`; added `scheduler.reconcile_worker_concurrency()` to align concurrency drift when workers become idle; restored previous `SIGTERM` handlers upon exit from `celerytask.run_task()` so idle worker pools respond properly to `pool_shrink`.
- **Frontend visual tokens, shared empty-state component, and multi-locale layout unification**: consolidated global card, border, background, terminal, and sticky CSS tokens across `App.vue` and `style.css` (and removed the redundant `0.45` opacity `--arl-text-secondary` overwrite in `App.vue`); extracted `ArlEmpty.vue` and unified `.arl-pagination-bar` styling and responsive layouts across Chinese, English, and Russian locales.

### 🐛 Bug Fixes & Hardening
- **Worker boot generation tracking and orphan task convergence**: recorded per-worker `WORKER_BOOT_ID` and `worker_instances` snapshots during startup and task execution to recognize and converge orphaned tasks left by restarted or absent workers; implemented tiered `safe_phase` fault handling separating critical discovery failures from auxiliary phase errors while preserving partial results.
- **Fail-closed fingerprint deletion and cross-worker cache invalidation**: introduced the `fingerprint_deleted` tombstone collection and `fingerprint_initialized_v1` sentinel to prevent deleted rules from reappearing on cache refresh, scan execution, or restart; added `system_config`-backed `_fingerprint_cache_version` invalidation and `RLock` protection in `fingerprint_cache.py`; added aggregation-deduplicated unique indexes on `fingerprint.name` and `fingerprint_deleted.name` in `arlupdate.py`; updated `Fingerprint.vue` with deletion loading guards, deterministic `-update_date,-_id` sorting, non-preserved cross-page selection, and `human_rule` filter alignment.
- **KeepAlive view refresh and stale sync metadata cleanup**: added `onActivated` refresh with `firstActivation` deduplication to the policy list and null-safety guards in `PolicyDetail.vue`; fixed KeepAlive sidebar anchor drift in `AssetScope.vue`; cleared prior `sync_summary` across task re-sync (`SyncTask.post`, `sync_task_to_scope`) and task restart (`restart_task`, also clearing `phase_errors`), and gated `hasSyncSummary` against `waiting`, `running`, and `error` sync states.

### 🛡️ Security & Configuration
- **Bootstrap admin password preflight validation and documentation updates**: validated `ARL_ADMIN_PASSWORD` length (12–1024 chars from environment or `.env`) in `start-prod.sh` after Python environment setup, printing flow-specific login and `--reset` instructions while distinguishing Nginx Basic Auth from platform credentials; cleared stale `/tmp/arl_initial_admin_password` in `inject_user.py` whenever no random password is generated; replaced the legacy `"arlpass"` placeholder in `Login.vue` with localized prompts, and synchronized bilingual README, Quickstart, and API Guide docs.

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
