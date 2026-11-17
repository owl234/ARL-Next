<template>
  <div class="arl-page-container" :class="{ 'page-wide-text': pageLocale !== 'zh-CN' }">
    <!-- 1. 顶部吸顶 Hero 卡片（与全站多页签页面统一规范） -->
    <div ref="actionBarRef" class="arl-hero-card">
      <div class="arl-hero-unified-bar">
        <div class="arl-hero-left">
          <div class="arl-hero-title">
            <RobotOutlined class="hero-brand-icon" />
            <span class="title-text">{{ pageText('pages.mcpCenterTitle') }}</span>
          </div>

          <div class="arl-capsule-switcher">
            <button
              type="button"
              class="arl-capsule-item"
              :class="{ 'is-active': activeTab === 'setup' }"
              @click="switchTab('setup')"
            >
              <ApiOutlined class="capsule-icon" />
              <span>{{ pageText('pages.mcpCapsuleSetup') }}</span>
            </button>

            <button
              type="button"
              class="arl-capsule-item"
              :class="{ 'is-active': activeTab === 'audit' }"
              @click="switchTab('audit')"
            >
              <BarChartOutlined class="capsule-icon" />
              <span>{{ pageText('pages.mcpCapsuleAudit') }}</span>
              <span v-if="overviewData.today_calls > 0 || autoRefreshEnabled" class="arl-capsule-count">
                <span v-if="autoRefreshEnabled" class="arl-capsule-dot is-pulse"></span>
                {{ overviewData.today_calls }}
              </span>
            </button>

            <button
              type="button"
              class="arl-capsule-item"
              :class="{ 'is-active': activeTab === 'keys' }"
              @click="switchTab('keys')"
            >
              <KeyOutlined class="capsule-icon" />
              <span>{{ pageText('pages.mcpCapsuleKeys') }}</span>
              <span v-if="overviewData.active_keys > 0" class="arl-capsule-count">
                {{ overviewData.active_keys }}
              </span>
            </button>

            <button
              type="button"
              class="arl-capsule-item"
              :class="{ 'is-active': activeTab === 'policy' }"
              @click="switchTab('policy')"
            >
              <SafetyCertificateOutlined class="capsule-icon" />
              <span>{{ pageText('pages.mcpCapsulePolicy') }}</span>
              <span v-if="isPolicyDirty" class="arl-capsule-count">
                <span class="arl-capsule-dot is-pulse"></span>
                {{ policyDirtyCount }}
              </span>
            </button>
          </div>
        </div>

        <div class="arl-hero-right">
          <a-tooltip :title="healthTooltipText" placement="bottomRight">
            <a-tag :color="healthTagColor" class="mcp-health-pill">
              <span v-if="overviewData.sse_status === 'online'" class="live-pulse"></span>
              <span>{{ healthLabelText }}</span>
            </a-tag>
          </a-tooltip>

          <a-tooltip
            v-if="activeTab === 'audit'"
            :title="autoRefreshEnabled ? pageText('pages.mcpAutoRefreshTip') : pageText('pages.mcpAutoRefreshPausedTip')"
          >
            <div class="auto-refresh-toggle">
              <a-switch v-model:checked="autoRefreshEnabled" size="small" />
              <span class="toggle-label">{{ pageText('tasks.autoRefresh') }}</span>
            </div>
          </a-tooltip>

          <a-button size="small" :loading="isRefreshing" @click="refreshActiveTab">
            <template #icon><ReloadOutlined /></template>
            {{ pageText('pages.refresh') }}
          </a-button>

          <template v-if="activeTab === 'setup'">
            <div class="arl-hero-v-divider"></div>
            <a-button size="small" @click="promptDrawerVisible = true">
              <template #icon><BookOutlined /></template>
              {{ pageText('pages.mcpPromptRecipesBtn') }}
            </a-button>
            <a-button type="primary" size="small" @click="handleCopySnippet">
              <template #icon><CopyOutlined /></template>
              {{ pageText('pages.mcpCopySnippet') }}
            </a-button>
          </template>

          <template v-else-if="activeTab === 'keys'">
            <div class="arl-hero-v-divider"></div>
            <a-button type="primary" size="small" @click="openCreateKeyModal">
              <template #icon><PlusOutlined /></template>
              {{ pageText('pages.mcpCreateKey') }}
            </a-button>
          </template>

          <template v-else-if="activeTab === 'policy'">
            <div class="arl-hero-v-divider"></div>
            <a-button size="small" :disabled="!isPolicyDirty" @click="resetPolicyChanges">
              <template #icon><UndoOutlined /></template>
              {{ pageText('pages.mcpResetPolicyBtn') }}
            </a-button>
            <a-button
              type="primary"
              size="small"
              :class="{ 'arl-dirty-btn': isPolicyDirty }"
              :loading="isSavingPolicy"
              @click="savePolicyConfig"
            >
              <template #icon><CheckOutlined /></template>
              {{ isPolicyDirty ? pageText('pages.mcpSavePolicyCount', { count: policyDirtyCount }) : pageText('pages.mcpSavePolicyBtn') }}
            </a-button>
          </template>
        </div>
      </div>

      <!-- 二级吸顶工具栏：调用监控筛选 -->
      <div v-if="activeTab === 'audit'" class="arl-toolbar-row arl-hero-sub-row">
        <div class="arl-filter-group">
          <a-select
            v-model:value="logFilter.time_range"
            style="width: 118px;"
            size="small"
            allow-clear
            :placeholder="pageText('pages.mcpFilterTimeAll')"
            @change="handleFilterTimeChange"
          >
            <a-select-option value="today">{{ pageText('pages.mcpFilterTimeToday') }}</a-select-option>
            <a-select-option value="24h">{{ pageText('pages.mcpFilterTime24h') }}</a-select-option>
            <a-select-option value="7d">{{ pageText('pages.mcpFilterTime7d') }}</a-select-option>
          </a-select>

          <a-select
            v-model:value="logFilter.key_id"
            style="width: 165px;"
            size="small"
            allow-clear
            :placeholder="pageText('pages.mcpFilterKeyPlaceholder')"
            @change="handleLogFilterImmediate"
          >
            <a-select-option value="legacy">{{ pageText('pages.mcpFilterLegacyTokenOption') }}</a-select-option>
            <a-select-option v-for="k in allKeyOptions" :key="k.id" :value="k.id">
              {{ k.name }} ({{ k.key_prefix }})
            </a-select-option>
          </a-select>

          <a-select
            v-model:value="logFilter.tool_name"
            style="width: 175px;"
            size="small"
            allow-clear
            :placeholder="pageText('pages.mcpFilterToolPlaceholder')"
            @change="handleLogFilterImmediate"
          >
            <a-select-option v-for="tool in MCP_TOOL_CATALOG" :key="tool.name" :value="tool.name">
              {{ tool.name }}
            </a-select-option>
          </a-select>

          <a-select
            v-model:value="logFilter.status"
            style="width: 132px;"
            size="small"
            allow-clear
            :placeholder="pageText('pages.mcpFilterStatusPlaceholder')"
            @change="handleFilterStatusChange"
          >
            <a-select-option value="success">{{ pageText('pages.mcpStatusSuccess') }}</a-select-option>
            <a-select-option value="error">{{ pageText('pages.mcpStatusError') }}</a-select-option>
            <a-select-option value="denied">{{ pageText('pages.mcpStatusDenied') }}</a-select-option>
            <a-select-option value="abnormal">{{ pageText('pages.mcpFilterAbnormal') }}</a-select-option>
          </a-select>

          <a-input
            v-model:value="logFilter.target"
            :placeholder="pageText('pages.mcpFilterTargetPlaceholder')"
            style="width: 190px;"
            size="small"
            allow-clear
            @pressEnter="handleLogFilterImmediate"
          >
            <template #suffix>
              <SearchOutlined class="input-search-icon" @click="handleLogFilterImmediate" />
            </template>
          </a-input>

          <a-button size="small" @click="handleLogFilterImmediate">
            <template #icon><SearchOutlined /></template>
            {{ pageText('pages.search') }}
          </a-button>

          <a-button size="small" @click="resetLogFilter">
            <template #icon><UndoOutlined /></template>
            {{ pageText('pages.reset') }}
          </a-button>
        </div>

        <div class="arl-actions-group">
          <a-button size="small" :loading="isExportingLogs" @click="exportLogsCsv">
            <template #icon><ExportOutlined /></template>
            {{ pageText('pages.exportCsv') }}
          </a-button>
        </div>
      </div>

      <!-- 二级吸顶工具栏：密钥管理筛选 -->
      <div v-else-if="activeTab === 'keys'" class="arl-toolbar-row arl-hero-sub-row">
        <div class="arl-filter-group">
          <a-input-search
            v-model:value="keySearchKeyword"
            :placeholder="pageText('pages.mcpSearchKeyPlaceholder')"
            style="width: 240px;"
            size="small"
            allow-clear
            @search="handleKeyFilterSearch"
          />

          <a-select
            v-model:value="keyStatusFilter"
            style="width: 150px;"
            size="small"
            allow-clear
            :placeholder="pageText('pages.mcpFilterKeyStatusPlaceholder')"
            @change="handleKeyFilterSearch"
          >
            <a-select-option value="active">{{ pageText('pages.mcpStatusActive') }}</a-select-option>
            <a-select-option value="expired">{{ pageText('pages.mcpStatusExpired') }}</a-select-option>
            <a-select-option value="revoked">{{ pageText('pages.mcpStatusRevoked') }}</a-select-option>
          </a-select>

          <a-button size="small" @click="resetKeyFilter">
            <template #icon><UndoOutlined /></template>
            {{ pageText('pages.reset') }}
          </a-button>
        </div>
      </div>
    </div>

    <!-- ================================================================ -->
    <!-- 视图 1: 接入与联调工作台 -->
    <!-- ================================================================ -->
    <div v-if="activeTab === 'setup'" class="mcp-section-stack">
      <!-- 通道与凭据控制条 -->
      <a-card size="small" class="mcp-surface-card">
        <div class="setup-control-bar">
          <div class="setup-field-group">
            <span class="field-label">{{ pageText('pages.mcpAccessMode') }}:</span>
            <a-radio-group v-model:value="mcpMode" button-style="solid" size="small" @change="updateConfigPreview">
              <a-radio-button value="sse">{{ pageText('pages.mcpModeRemoteSse') }}</a-radio-button>
              <a-radio-button value="stdio">{{ pageText('pages.mcpModeLocalStdio') }}</a-radio-button>
            </a-radio-group>
            <a-tag color="cyan" class="mcp-aligned-badge">{{ pageText('pages.mcpAllToolsAlignedTag') }}</a-tag>
          </div>

          <div class="setup-field-group setup-key-group">
            <span class="field-label">{{ pageText('pages.mcpBindKey') }}:</span>
            <div class="setup-key-controls">
              <a-select
                v-model:value="selectedKeyId"
                size="small"
                style="width: min(260px, 100%); min-width: 190px;"
                :placeholder="pageText('pages.mcpSelectKeyPlaceholder')"
                @change="handleKeySelectChange"
              >
                <a-select-option v-for="k in activeKeyOptions" :key="k.id" :value="k.id">
                  {{ k.name }} ({{ k.key_prefix }})
                </a-select-option>
                <a-select-option value="current_session">{{ pageText('pages.mcpCurrentSessionToken') }}</a-select-option>
              </a-select>

              <a-button type="dashed" size="small" @click="openCreateKeyModal">
                <template #icon><PlusOutlined /></template>
                {{ pageText('pages.mcpCreateKeyQuick') }}
              </a-button>

              <a-tag v-if="selectedKeyId === 'current_session'" color="warning">
                {{ pageText('pages.mcpLegacyTokenWarnTag') }}
              </a-tag>
              <a-tag v-else color="success">
                {{ pageText('pages.mcpDedicatedKeyTag') }}
              </a-tag>
            </div>
          </div>
        </div>

        <div v-if="selectedKeyId !== 'current_session'" class="setup-secret-row">
          <a-input-password
            v-model:value="keySecrets[selectedKeyId]"
            size="small"
            :placeholder="pageText('pages.mcpFullKeyPlaceholder')"
            autocomplete="off"
            style="max-width: 520px;"
          />
          <span class="field-hint" style="margin-top: 0;">{{ pageText('pages.mcpFullKeyHint') }}</span>
        </div>

        <div v-else class="setup-session-hint">
          <InfoCircleOutlined class="tip-icon" />
          <span>{{ pageText('pages.mcpLegacyTokenTip') }}</span>
        </div>

        <!-- 紧凑能力摘要条：全局安全策略 × 当前凭据交集 -->
        <div class="setup-capability-strip">
          <div class="setup-capability-badges">
            <span class="field-hint-label">{{ pageText('pages.mcpCapabilitySummaryLabel') }}:</span>

            <a-tooltip placement="bottomLeft">
              <template #title>
                <div class="cap-tooltip-list">
                  <div v-for="item in capabilitySummary.readItems" :key="item.name" class="cap-tooltip-row">
                    <code>{{ item.name }}</code>
                    <span>{{ formatCapabilityItemStatus(item) }}</span>
                  </div>
                </div>
              </template>
              <a-tag
                :color="capabilitySummary.readAllowed === capabilitySummary.readTotal ? 'blue' : (capabilitySummary.readAllowed > 0 ? 'warning' : 'default')"
                class="setup-cap-pill"
              >
                {{ pageText('pages.mcpCapabilityReadPill', { allowed: capabilitySummary.readAllowed, total: capabilitySummary.readTotal }) }}
              </a-tag>
            </a-tooltip>

            <a-tooltip placement="bottomLeft">
              <template #title>
                <div class="cap-tooltip-list">
                  <div v-for="item in capabilitySummary.writeItems" :key="item.name" class="cap-tooltip-row">
                    <code>{{ item.name }}</code>
                    <span>{{ formatCapabilityItemStatus(item) }}</span>
                  </div>
                </div>
              </template>
              <a-tag
                :color="capabilitySummary.writeAllowed === capabilitySummary.writeTotal ? 'orange' : (capabilitySummary.writeAllowed > 0 ? 'warning' : 'default')"
                class="setup-cap-pill"
              >
                {{ pageText('pages.mcpCapabilityWritePill', { allowed: capabilitySummary.writeAllowed, total: capabilitySummary.writeTotal }) }}
              </a-tag>
            </a-tooltip>
          </div>

          <div
            v-if="capabilitySummary.hasMissingScope || capabilitySummary.hasPolicyDisabled"
            class="setup-capability-hints"
          >
            <span v-if="capabilitySummary.hasMissingScope" class="cap-hint-group">
              <span class="cap-hint-text">
                {{ pageText('pages.mcpCapMissingScope', { scope: capabilitySummary.missingScopes.join(' / ') }) }}
              </span>
              <a-button type="link" size="small" style="padding: 0; height: auto;" @click="switchTab('keys')">
                {{ pageText('pages.mcpFixInKeys') }}
              </a-button>
            </span>

            <span v-if="capabilitySummary.hasPolicyDisabled" class="cap-hint-group">
              <span class="cap-hint-text">{{ pageText('pages.mcpCapPolicyDisabled') }}</span>
              <a-button type="link" size="small" style="padding: 0; height: auto;" @click="switchTab('policy')">
                {{ pageText('pages.mcpFixInPolicy') }}
              </a-button>
            </span>
          </div>
        </div>

        <!-- 通道异常或自签证书告警 -->
        <a-alert
          v-if="mcpMode === 'sse' && overviewData.sse_status === 'offline' && !isCheckingOverview"
          type="warning"
          show-icon
          style="margin-top: 12px;"
          :message="pageText('pages.mcpHealthRestOnly')"
          :description="pageText('pages.mcpHealthRestOnlyTip')"
        >
          <template #action>
            <a-button size="small" type="primary" ghost @click="switchToStdioMode">
              {{ pageText('pages.mcpSwitchToStdio') }}
            </a-button>
          </template>
        </a-alert>

        <a-alert
          v-else-if="mcpMode === 'sse' && isIpAccess"
          type="warning"
          show-icon
          style="margin-top: 12px;"
          :message="pageText('pages.mcpSseIpWarningTitle')"
        >
          <template #description>
            <div style="margin-top: 4px;">
              <div style="line-height: 1.5;">{{ pageText('pages.mcpSseIpWarningDesc') }}</div>
              <div style="margin-top: 8px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
                <a-button size="small" type="primary" ghost @click="switchToStdioMode">
                  {{ pageText('pages.mcpSwitchToStdio') }}
                </a-button>
                <a-button size="small" type="link" style="padding: 0;" @click="showCertGuide = !showCertGuide">
                  {{ showCertGuide ? pageText('pages.mcpHideCertGuide') : pageText('pages.mcpShowCertGuide') }}
                </a-button>
              </div>
              <div v-if="showCertGuide" class="cert-guide-box">
                <div style="margin-bottom: 6px;">{{ pageText('pages.mcpCertGuideStep1') }}</div>
                <div>{{ pageText('pages.mcpCertGuideStep2') }}</div>
              </div>
            </div>
          </template>
        </a-alert>
      </a-card>

      <!-- 双栏主工作区：左侧配置生成 / 右侧在线试跑台 -->
      <a-row :gutter="[14, 14]">
        <a-col :xs="24" :lg="14">
          <a-card size="small" :title="pageText('pages.mcpClientSectionTitle')" class="mcp-surface-card mcp-full-height">
            <a-tabs v-model:activeKey="selectedClient" type="card" size="small" class="arl-detail-tabs">
              <a-tab-pane key="cursor" tab="Cursor / Windsurf">
                <div class="client-desc">
                  {{ pageText('pages.mcpCursorGuideDesc') }} <code>mcp.json</code> / <code>mcp_config.json</code>:
                </div>
              </a-tab-pane>
              <a-tab-pane key="claude_code" :tab="pageText('pages.mcpClientClaudeCode')">
                <div class="client-desc">
                  {{ pageText('pages.mcpClaudeCodeCliDesc') }}
                </div>
              </a-tab-pane>
              <a-tab-pane key="claude_desktop" :tab="pageText('pages.mcpClientClaudeDesktop')">
                <div class="client-desc">
                  {{ pageText('pages.mcpClaudeDesktopGuideDesc') }} <code>claude_desktop_config.json</code>:
                </div>
              </a-tab-pane>
              <a-tab-pane key="antigravity" tab="Antigravity / JSON">
                <div class="client-desc">
                  {{ pageText('pages.mcpAntigravityGuideDesc') }}:
                </div>
              </a-tab-pane>
              <a-tab-pane key="sdk_env" :tab="pageText('pages.mcpClientSdkEnv')">
                <div class="client-desc">
                  {{ pageText('pages.mcpSdkEnvDesc') }}
                </div>
              </a-tab-pane>
            </a-tabs>

            <!-- Stdio 脚本路径与 Python 命令自定义 -->
            <div v-if="mcpMode === 'stdio'" class="stdio-options-bar">
              <div class="stdio-option-field">
                <span class="field-hint-label">{{ pageText('pages.mcpScriptPathLabel') }}:</span>
                <a-input
                  v-model:value="stdioScriptPath"
                  size="small"
                  :placeholder="pageText('pages.mcpScriptPathPlaceholder')"
                  style="width: 240px;"
                />
              </div>
              <div class="stdio-option-field">
                <span class="field-hint-label">{{ pageText('pages.mcpPythonCmdLabel') }}:</span>
                <a-radio-group v-model:value="stdioPythonBin" size="small">
                  <a-radio-button value="python3">python3</a-radio-button>
                  <a-radio-button value="python">python (Win)</a-radio-button>
                </a-radio-group>
              </div>
              <a-button
                size="small"
                :loading="isDownloadingScript"
                @click="handleDownloadScript"
              >
                <template #icon><DownloadOutlined /></template>
                {{ pageText('pages.downloadArlMcpPy') }}
              </a-button>
            </div>

            <div class="config-code-box">
              <pre class="code-pre"><code>{{ activeClientSnippet }}</code></pre>
              <div class="code-actions">
                <a-button type="primary" size="small" @click="handleCopySnippet">
                  <template #icon><CopyOutlined /></template>
                  {{ pageText('pages.copyConfiguration') }}
                </a-button>
              </div>
            </div>

            <div class="setup-footer-tips">
              <div class="tip-item">
                <SafetyCertificateOutlined class="tip-icon" />
                <span class="tip-text">{{ pageText('pages.mcpSecurityNotice') }}</span>
              </div>
              <div class="tip-item">
                <InfoCircleOutlined class="tip-icon" />
                <span class="tip-text">{{ pageText('pages.mcpDualAuthNotice') }}</span>
              </div>
            </div>
          </a-card>
        </a-col>

        <a-col :xs="24" :lg="10">
          <!-- 轻量只读工具试跑台 -->
          <a-card size="small" :title="pageText('pages.mcpPlaygroundTitle')" class="mcp-surface-card mcp-full-height">
              <a-form layout="vertical" size="small" class="playground-form">
                <a-row :gutter="10">
                  <a-col :xs="24" :sm="12">
                    <a-form-item :label="pageText('pages.mcpPlaygroundToolLabel')" style="margin-bottom: 10px;">
                      <a-select v-model:value="playgroundForm.tool">
                        <a-select-option value="get_asset_profile">get_asset_profile</a-select-option>
                        <a-select-option value="get_enterprise_profile">get_enterprise_profile</a-select-option>
                        <a-select-option value="search_assets">search_assets</a-select-option>
                        <a-select-option value="get_task_status">get_task_status</a-select-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col v-if="playgroundForm.tool === 'get_enterprise_profile'" :xs="24" :sm="12">
                    <a-form-item :label="pageText('pages.mcpPlaygroundCategoryLabel')" style="margin-bottom: 10px;">
                      <a-select v-model:value="playgroundForm.category">
                        <a-select-option value="all">all</a-select-option>
                        <a-select-option value="web">web</a-select-option>
                        <a-select-option value="app">app</a-select-option>
                        <a-select-option value="mapp">mapp</a-select-option>
                        <a-select-option value="wechat">wechat</a-select-option>
                        <a-select-option value="invest">invest</a-select-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col v-else-if="playgroundForm.tool === 'search_assets'" :xs="12" :sm="6">
                    <a-form-item :label="pageText('pages.mcpPlaygroundAssetTypeLabel')" style="margin-bottom: 10px;">
                      <a-select v-model:value="playgroundForm.asset_type">
                        <a-select-option value="site">site</a-select-option>
                        <a-select-option value="domain">domain</a-select-option>
                        <a-select-option value="ip">ip</a-select-option>
                        <a-select-option value="vuln">vuln</a-select-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col v-else-if="playgroundForm.tool === 'search_assets'" :xs="12" :sm="6">
                    <a-form-item :label="pageText('pages.mcpPlaygroundLimitLabel')" style="margin-bottom: 10px;">
                      <a-input-number v-model:value="playgroundForm.limit" :min="1" :max="50" style="width: 100%;" />
                    </a-form-item>
                  </a-col>
                  <a-col v-else-if="playgroundForm.tool === 'get_asset_profile'" :xs="24" :sm="12">
                    <a-form-item :label="pageText('pages.mcpPlaygroundTaskIdLabel')" style="margin-bottom: 10px;">
                      <a-input v-model:value="playgroundForm.task_id" allow-clear placeholder="24-hex" />
                    </a-form-item>
                  </a-col>
                </a-row>

                <div class="playground-run-row">
                  <a-input
                    v-model:value="playgroundForm.target"
                    :placeholder="playgroundForm.tool === 'get_task_status' ? '24-hex task_id' : pageText('pages.mcpPlaygroundTargetPlaceholder')"
                    allow-clear
                    @pressEnter="runPlaygroundTest"
                  />
                  <a-button
                    type="primary"
                    ghost
                    :loading="isPlaygroundRunning"
                    @click="runPlaygroundTest"
                  >
                    <template #icon><PlayCircleOutlined /></template>
                    {{ pageText('pages.mcpPlaygroundRunBtn') }}
                  </a-button>
                </div>
              </a-form>

              <div class="field-hint" style="margin-top: 8px;">
                {{ pageText('pages.mcpPlaygroundAuditNotice') }}
              </div>

              <div v-if="playgroundResult" class="playground-output-wrap">
                <div class="playground-meta-bar">
                  <div class="playground-meta-left">
                    <a-tag :color="playgroundResult.ok ? 'success' : 'error'" style="margin: 0;">
                      HTTP {{ playgroundResult.httpStatus }}
                    </a-tag>
                    <span :class="['mcp-duration-badge', getDurationClass(playgroundResult.durationMs)]">
                      {{ playgroundResult.durationMs }} ms
                    </span>
                    <span class="playground-token-badge">
                      {{ pageText('pages.mcpPlaygroundTokensEst', { tokens: playgroundResult.estTokens }) }}
                    </span>
                  </div>
                  <a-button type="link" size="small" style="padding: 0;" @click="switchTab('audit')">
                    {{ pageText('pages.mcpPlaygroundViewAudit') }}
                  </a-button>
                </div>
                <pre class="arl-mono-terminal playground-terminal"><code>{{ playgroundResult.body }}</code></pre>
              </div>
              <div v-else class="playground-placeholder">
                {{ pageText('pages.mcpPlaygroundEmptyResult') }}
              </div>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- ================================================================ -->
    <!-- 视图 2: 调用监控与下钻 -->
    <!-- ================================================================ -->
    <div v-else-if="activeTab === 'audit'" class="mcp-section-stack">
      <!-- 4 维核心指标卡（与 TaskList 统一） -->
      <div class="task-metric-cards-row">
        <div
          class="metric-stat-card"
          :class="{ active: activeMetricFilter === 'today' }"
          @click="toggleMetricFilter('today')"
        >
          <div class="stat-card-inner">
            <div class="stat-icon-box primary">
              <ThunderboltOutlined />
            </div>
            <div class="stat-info">
              <div class="stat-label">{{ pageText('pages.mcpTodayCalls') }}</div>
              <div class="stat-value">{{ overviewData.today_calls }}</div>
            </div>
          </div>
        </div>

        <div
          class="metric-stat-card"
          :class="{ active: activeMetricFilter === '7d' }"
          @click="toggleMetricFilter('7d')"
        >
          <div class="stat-card-inner">
            <div class="stat-icon-box info">
              <BarChartOutlined />
            </div>
            <div class="stat-info">
              <div class="stat-label">{{ pageText('pages.mcpWeekCalls') }}</div>
              <div class="stat-value">{{ overviewData.week_calls }}</div>
            </div>
          </div>
        </div>

        <div
          class="metric-stat-card"
          @click="switchTab('keys')"
        >
          <div class="stat-card-inner">
            <div class="stat-icon-box done">
              <KeyOutlined />
            </div>
            <div class="stat-info">
              <div class="stat-label">{{ pageText('pages.mcpActiveKeys') }}</div>
              <div class="stat-value done">{{ overviewData.active_keys }} <span class="stat-suffix">/ {{ overviewData.total_keys }}</span></div>
            </div>
          </div>
        </div>

        <div
          class="metric-stat-card"
          :class="{ active: activeMetricFilter === 'error_24h' }"
          @click="toggleMetricFilter('error_24h')"
        >
          <div class="stat-card-inner">
            <div class="stat-icon-box error">
              <AlertOutlined />
            </div>
            <div class="stat-info">
              <div class="stat-label">{{ pageText('pages.mcpErrors24h') }}</div>
              <div class="stat-value" :class="{ error: overviewData.error_calls_24h > 0 }">{{ overviewData.error_calls_24h }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 审计表格 -->
      <a-table
        :sticky="stickyConfig"
        :columns="logColumns"
        :data-source="logList"
        :loading="isLogsLoading"
        row-key="id"
        :scroll="{ x: 1460 }"
        :pagination="false"
        :custom-row="(record) => ({
          onClick: () => openLogDetail(record),
          style: { cursor: 'pointer' }
        })"
        size="small"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'created_at'">
            <span class="mcp-time-cell">{{ record.created_at }}</span>
          </template>

          <template v-else-if="column.key === 'key_name'">
            <a-tooltip :title="record.key_name">
              <a-tag :color="record.key_name === '[Legacy Token]' ? 'default' : 'blue'" class="mcp-key-tag">
                <KeyOutlined style="margin-right: 4px;" />
                <span class="mcp-key-text">{{ record.key_name || '-' }}</span>
              </a-tag>
            </a-tooltip>
          </template>

          <template v-else-if="column.key === 'client_ip'">
            <span class="mcp-ip-cell">{{ record.client_ip || '-' }}</span>
          </template>

          <template v-else-if="column.key === 'tool_name'">
            <a-tooltip :title="getToolMeta(record.tool_name).desc">
              <a-tag :color="getToolMeta(record.tool_name).color" class="mcp-tool-tag">
                <component :is="getToolMeta(record.tool_name).icon" class="mcp-tool-icon" />
                <span class="mcp-tool-label">{{ record.tool_name }}</span>
              </a-tag>
            </a-tooltip>
          </template>

          <template v-else-if="column.key === 'target'">
            <div class="mcp-target-cell">
              <a-tooltip v-if="record.target" :title="record.target">
                <span class="mcp-target-text">{{ record.target }}</span>
              </a-tooltip>
              <a-tooltip v-else-if="record.params_summary" :title="record.params_summary">
                <span class="mcp-target-placeholder">{{ record.params_summary }}</span>
              </a-tooltip>
              <span v-else class="mcp-target-empty">-</span>

              <div class="mcp-target-actions">
                <a-tooltip v-if="getAuditPivot(record).taskRoute" :title="pageText('pages.mcpPivotTaskBtn')">
                  <a-button
                    type="text"
                    size="small"
                    class="mcp-cell-pivot-btn"
                    @click.stop="navigateToPivot(getAuditPivot(record).taskRoute)"
                  >
                    <template #icon><DashboardOutlined /></template>
                  </a-button>
                </a-tooltip>

                <a-tooltip v-if="getAuditPivot(record).assetRoute" :title="pageText('pages.mcpPivotAssetBtn')">
                  <a-button
                    type="text"
                    size="small"
                    class="mcp-cell-pivot-btn"
                    @click.stop="navigateToPivot(getAuditPivot(record).assetRoute)"
                  >
                    <template #icon><GlobalOutlined /></template>
                  </a-button>
                </a-tooltip>

                <a-tooltip v-if="record.target" :title="pageText('pages.copy')">
                  <a-button
                    type="text"
                    size="small"
                    class="mcp-cell-copy-btn"
                    @click.stop="copyTextDirect(record.target)"
                  >
                    <template #icon><CopyOutlined /></template>
                  </a-button>
                </a-tooltip>
              </div>
            </div>
          </template>

          <template v-else-if="column.key === 'duration_ms'">
            <span :class="['mcp-duration-badge', getDurationClass(record.duration_ms)]">
              {{ record.duration_ms != null ? record.duration_ms + ' ms' : '-' }}
            </span>
          </template>

          <template v-else-if="column.key === 'status'">
            <a-tag v-if="record.status === 'success'" color="success">{{ pageText('pages.mcpStatusSuccess') }}</a-tag>
            <a-tag v-else-if="record.status === 'denied'" color="warning">{{ pageText('pages.mcpStatusDenied') }}</a-tag>
            <a-tag v-else color="error">{{ pageText('pages.mcpStatusError') }}</a-tag>
          </template>

          <template v-else-if="column.key === 'summary'">
            <a-tooltip v-if="record.error_message" :title="record.error_message" placement="topLeft">
              <span class="mcp-summary-error">
                <CloseCircleOutlined style="margin-right: 4px; flex-shrink: 0;" />
                <span class="mcp-summary-error-text">{{ record.error_message }}</span>
              </span>
            </a-tooltip>
            <a-tooltip v-else-if="record.summary" :title="record.summary" placement="topLeft">
              <span class="mcp-summary-text">{{ record.summary }}</span>
            </a-tooltip>
            <span v-else class="mcp-summary-empty">-</span>
          </template>

          <template v-else-if="column.key === 'action'">
            <a-button type="link" size="small" @click.stop="openLogDetail(record)">
              {{ pageText('pages.mcpViewDetail') }}
            </a-button>
          </template>
        </template>
        <template #emptyText>
          <ArlEmpty :description="pageText('tasks.noData')" />
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">{{ pageText('pages.totalItems', { total: logPagination.total }) }}</div>
        <a-pagination
          size="small"
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="logPagination.page"
          v-model:pageSize="logPagination.size"
          :total="logPagination.total"
          show-size-changer
          @change="handleLogPageChange"
          @showSizeChange="handleLogPageChange"
        />
      </div>
    </div>

    <!-- ================================================================ -->
    <!-- 视图 3: 密钥管理 -->
    <!-- ================================================================ -->
    <div v-else-if="activeTab === 'keys'" class="mcp-section-stack">
      <a-table
        :sticky="stickyConfig"
        :columns="keyColumns"
        :data-source="keyList"
        :loading="isKeysLoading"
        row-key="id"
        :scroll="{ x: 1120 }"
        :pagination="false"
        size="small"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <span style="font-weight: 500;">{{ record.name }}</span>
          </template>

          <template v-else-if="column.key === 'key_prefix'">
            <a-typography-text code>{{ record.key_prefix }}</a-typography-text>
          </template>

          <template v-else-if="column.key === 'scopes'">
            <div style="display: flex; gap: 4px; flex-wrap: wrap;">
              <a-tag v-if="record.scopes && record.scopes.includes('asset:read')" color="blue">
                {{ pageText('pages.mcpScopeRead') }}
              </a-tag>
              <a-tag v-if="record.scopes && record.scopes.includes('task:dispatch')" color="orange">
                {{ pageText('pages.mcpScopeDispatch') }}
              </a-tag>
            </div>
          </template>

          <template v-else-if="column.key === 'status'">
            <a-badge
              v-if="record.status === 'revoked'"
              status="error"
              :text="pageText('pages.mcpStatusRevoked')"
            />
            <a-badge
              v-else-if="isKeyExpired(record)"
              status="warning"
              :text="pageText('pages.mcpStatusExpired')"
            />
            <a-badge
              v-else
              status="success"
              :text="pageText('pages.mcpStatusActive')"
            />
          </template>

          <template v-else-if="column.key === 'expire_at'">
            <span v-if="record.expire_at" :class="{ 'text-expired': isKeyExpired(record) }">
              {{ record.expire_at }}
            </span>
            <span v-else style="color: var(--arl-text-secondary);">{{ pageText('pages.mcpExpireNever') }}</span>
          </template>

          <template v-else-if="column.key === 'last_active'">
            <span v-if="record.last_used_at">
              {{ record.last_used_at }}
              <span v-if="record.last_ip" style="color: var(--arl-text-secondary); font-size: 12px;">({{ record.last_ip }})</span>
            </span>
            <span v-else style="color: var(--arl-text-secondary);">-</span>
          </template>

          <template v-else-if="column.key === 'action'">
            <div class="key-row-actions">
              <a-button
                v-if="record.status === 'active' && !isKeyExpired(record)"
                type="link"
                size="small"
                @click="useKeyInSetup(record)"
              >
                {{ pageText('pages.mcpKeyActionUseSetup') }}
              </a-button>

              <a-button type="link" size="small" @click="viewKeyAuditLogs(record)">
                {{ pageText('pages.mcpKeyActionViewLogs') }}
              </a-button>

              <a-popconfirm
                :title="record.status === 'active' ? pageText('pages.mcpConfirmRevoke') : pageText('pages.mcpConfirmActivate')"
                :okText="pageText('pages.confirm')"
                :cancelText="pageText('tasks.cancel')"
                @confirm="toggleKeyStatus(record)"
              >
                <a-button type="link" size="small" :danger="record.status === 'active'">
                  {{ record.status === 'active' ? pageText('pages.mcpActionRevoke') : pageText('pages.mcpActionActivate') }}
                </a-button>
              </a-popconfirm>

              <a-popconfirm
                :title="pageText('pages.mcpConfirmDeleteKey')"
                :okText="pageText('pages.confirm')"
                :cancelText="pageText('tasks.cancel')"
                @confirm="deleteKey(record)"
              >
                <a-button type="link" size="small" danger>
                  {{ pageText('pages.delete') }}
                </a-button>
              </a-popconfirm>
            </div>
          </template>
        </template>
        <template #emptyText>
          <ArlEmpty :description="pageText('tasks.noData')" />
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">{{ pageText('pages.totalItems', { total: keyPagination.total }) }}</div>
        <a-pagination
          size="small"
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="keyPagination.page"
          v-model:pageSize="keyPagination.size"
          :total="keyPagination.total"
          show-size-changer
          @change="handleKeyPageChange"
          @showSizeChange="handleKeyPageChange"
        />
      </div>
    </div>

    <!-- ================================================================ -->
    <!-- 视图 4: 安全策略（双栏风险分组 + 顶栏主保存） -->
    <!-- ================================================================ -->
    <div v-else-if="activeTab === 'policy'" class="mcp-section-stack">
      <a-alert
        v-if="isPolicyDirty"
        type="warning"
        show-icon
        :message="pageText('pages.mcpUnsavedPolicyChanges')"
        :description="pageText('pages.saveEachChangeBeforeLeavingThisPage')"
      />

      <a-row :gutter="[14, 14]">
        <a-col :xs="24" :lg="14">
          <div class="mcp-right-stack">
            <a-card size="small" :title="pageText('pages.mcpPolicyReadGroupTitle')" class="mcp-surface-card">
              <div class="tool-switch-item" v-for="t in readToolConfigs" :key="t.key">
                <div class="tool-info">
                  <div class="tool-title">
                    <code>{{ t.key }}</code>
                    <a-tag color="blue" style="margin-left: 8px;">{{ pageText('pages.mcpTagRead') }}</a-tag>
                  </div>
                  <div class="tool-desc">{{ t.desc }}</div>
                </div>
                <div class="tool-action">
                  <a-switch v-model:checked="toolSwitches[t.key]" />
                </div>
              </div>
            </a-card>

            <a-card size="small" :title="pageText('pages.mcpPolicyWriteGroupTitle')" class="mcp-surface-card">
              <div class="tool-switch-item" v-for="t in writeToolConfigs" :key="t.key">
                <div class="tool-info">
                  <div class="tool-title">
                    <code>{{ t.key }}</code>
                    <a-tag color="orange" style="margin-left: 8px;">{{ pageText('pages.mcpTagWrite') }}</a-tag>
                  </div>
                  <div class="tool-desc">{{ t.desc }}</div>
                </div>
                <div class="tool-action">
                  <a-popconfirm
                    v-if="!toolSwitches[t.key]"
                    :title="pageText('pages.mcpRiskWriteNotice')"
                    :ok-text="pageText('pages.confirm')"
                    :cancel-text="pageText('tasks.cancel')"
                    @confirm="toolSwitches[t.key] = true"
                  >
                    <a-switch :checked="toolSwitches[t.key]" />
                  </a-popconfirm>
                  <a-switch v-else v-model:checked="toolSwitches[t.key]" />
                </div>
              </div>
            </a-card>
          </div>
        </a-col>

        <a-col :xs="24" :lg="10">
          <div class="mcp-right-stack">
            <a-card size="small" :title="pageText('pages.mcpQuotaTitle')" class="mcp-surface-card">
              <a-form layout="vertical" :label-wrap="true">
                <a-form-item :label="pageText('pages.mcpMaxSearchLimit')">
                  <a-input-number
                    v-model:value="policyForm.max_search_limit"
                    :min="1"
                    :max="200"
                    style="width: 100%; max-width: 240px;"
                  />
                  <div class="field-hint">{{ pageText('pages.mcpMaxSearchLimitHint') }}</div>
                </a-form-item>

                <a-form-item :label="pageText('pages.mcpRateLimitPerMin')" style="margin-bottom: 4px;">
                  <a-input-number
                    v-model:value="policyForm.rate_limit_per_min"
                    :min="10"
                    :max="1000"
                    style="width: 100%; max-width: 240px;"
                  />
                  <div class="field-hint">{{ pageText('pages.mcpRateLimitHint') }}</div>
                </a-form-item>
              </a-form>
            </a-card>

            <a-card size="small" :title="pageText('pages.mcpPolicyPresetsTitle')" class="mcp-surface-card">
              <div class="policy-preset-stack">
                <div class="policy-preset-item">
                  <div class="policy-preset-text">{{ pageText('pages.mcpPolicyPresetSafeDesc') }}</div>
                  <a-button size="small" @click="applyPolicyPreset('safe')">
                    {{ pageText('pages.mcpPolicyPresetSafeBtn') }}
                  </a-button>
                </div>

                <div class="policy-preset-item">
                  <div class="policy-preset-text">{{ pageText('pages.mcpPolicyPresetFullDesc') }}</div>
                  <a-popconfirm
                    :title="pageText('pages.mcpRiskWriteNotice')"
                    :ok-text="pageText('pages.confirm')"
                    :cancel-text="pageText('tasks.cancel')"
                    @confirm="applyPolicyPreset('full')"
                  >
                    <a-button size="small" danger ghost>
                      {{ pageText('pages.mcpPolicyPresetFullBtn') }}
                    </a-button>
                  </a-popconfirm>
                </div>
              </div>
            </a-card>
          </div>
        </a-col>
      </a-row>
    </div>

    <!-- 弹窗 1: 创建 API Key -->
    <a-modal
      v-model:open="createKeyModalVisible"
      :title="pageText('pages.mcpCreateKeyTitle')"
      @ok="handleCreateKeySubmit"
      :confirmLoading="isCreatingKey"
      @cancel="createKeyModalVisible = false"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      destroyOnClose
    >
      <a-form layout="vertical" :label-wrap="true" style="margin-top: 12px;">
        <a-form-item :label="pageText('pages.mcpPresetLabel')" style="margin-bottom: 12px;">
          <div style="display: flex; gap: 8px; flex-wrap: wrap;">
            <a-button
              size="small"
              :type="isReadOnlyPreset ? 'primary' : 'default'"
              :ghost="isReadOnlyPreset"
              @click="applyKeyPreset('readonly')"
            >
              {{ pageText('pages.mcpPresetReadOnly') }}
            </a-button>
            <a-button
              size="small"
              :type="!isReadOnlyPreset ? 'primary' : 'default'"
              :ghost="!isReadOnlyPreset"
              @click="applyKeyPreset('dispatch')"
            >
              {{ pageText('pages.mcpPresetReadWrite') }}
            </a-button>
          </div>
        </a-form-item>

        <a-form-item :label="pageText('pages.mcpKeyName')" required>
          <a-input
            v-model:value="newKeyForm.name"
            :placeholder="pageText('pages.mcpKeyNamePlaceholder')"
            maxlength="50"
            show-count
          />
        </a-form-item>

        <a-form-item :label="pageText('pages.mcpKeyScopes')" required>
          <a-checkbox-group v-model:value="newKeyForm.scopes">
            <a-checkbox value="asset:read">{{ pageText('pages.mcpScopeReadLabel') }}</a-checkbox>
            <a-checkbox value="task:dispatch">{{ pageText('pages.mcpScopeDispatchLabel') }}</a-checkbox>
          </a-checkbox-group>
          <div class="field-hint">{{ pageText('pages.mcpScopesHint') }}</div>
        </a-form-item>

        <a-alert
          v-if="newKeyForm.scopes.includes('task:dispatch') && !toolSwitches.create_scan_task && !toolSwitches.stop_scan_task"
          type="info"
          show-icon
          style="margin-bottom: 14px;"
          :message="pageText('pages.mcpDispatchGlobalOffNotice')"
        />

        <a-form-item :label="pageText('pages.mcpExpireDays')">
          <a-select v-model:value="newKeyForm.expire_days" style="width: 100%;">
            <a-select-option :value="1">{{ pageText('pages.mcpExpire1Day') }}</a-select-option>
            <a-select-option :value="7">7 {{ pageText('pages.days') }}</a-select-option>
            <a-select-option :value="30">30 {{ pageText('pages.days') }}</a-select-option>
            <a-select-option :value="90">90 {{ pageText('pages.days') }}</a-select-option>
            <a-select-option :value="180">180 {{ pageText('pages.days') }}</a-select-option>
            <a-select-option :value="0">{{ pageText('pages.mcpExpireNever') }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 弹窗 2: Key 创建成功展示明文 -->
    <a-modal
      v-model:open="keySuccessModalVisible"
      :title="pageText('pages.mcpKeyCreatedTitle')"
      :footer="null"
      width="560px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
    >
      <div style="margin-top: 8px;">
        <a-alert
          type="warning"
          show-icon
          :message="pageText('pages.mcpKeyCreatedWarning')"
          style="margin-bottom: 16px;"
        />

        <div style="font-weight: 500; margin-bottom: 6px;">{{ pageText('pages.mcpYourNewKey') }}:</div>
        <div style="display: flex; gap: 8px; margin-bottom: 16px;">
          <a-input :value="createdKeyPlaintext" readonly style="font-family: var(--arl-font-mono);" />
          <a-button type="primary" @click="handleCopyCreatedKey">
            <template #icon><CopyOutlined /></template>
            {{ pageText('pages.copy') }}
          </a-button>
        </div>

        <div style="display: flex; justify-content: flex-end;">
          <a-button type="default" @click="keySuccessModalVisible = false">
            {{ pageText('pages.close') }}
          </a-button>
        </div>
      </div>
    </a-modal>

    <!-- 抽屉 1: 审计日志详情（含联动跳转与拦截诊断） -->
    <a-drawer
      v-model:open="isLogDrawerVisible"
      :title="pageText('pages.mcpDrawerTitle')"
      placement="right"
      width="640"
      destroy-on-close
    >
      <div v-if="selectedLog" class="log-detail-container">
        <a-descriptions bordered :column="2" size="small" :title="pageText('pages.mcpLogDetailBasic')">
          <a-descriptions-item :label="pageText('pages.mcpLogTime')">
            {{ selectedLog.created_at }}
          </a-descriptions-item>
          <a-descriptions-item :label="pageText('pages.mcpLogClientIp')">
            <a-typography-text copyable>{{ selectedLog.client_ip || '-' }}</a-typography-text>
          </a-descriptions-item>
          <a-descriptions-item :label="pageText('pages.mcpLogKeyName')">
            {{ selectedLog.key_name }}
          </a-descriptions-item>
          <a-descriptions-item :label="pageText('pages.mcpLogTool')">
            <a-typography-text strong code>{{ selectedLog.tool_name }}</a-typography-text>
          </a-descriptions-item>
          <a-descriptions-item :label="pageText('pages.mcpLogStatus')">
            <a-tag v-if="selectedLog.status === 'success'" color="success">{{ pageText('pages.mcpStatusSuccess') }}</a-tag>
            <a-tag v-else-if="selectedLog.status === 'denied'" color="warning">{{ pageText('pages.mcpStatusDenied') }}</a-tag>
            <a-tag v-else color="error">{{ pageText('pages.mcpStatusError') }}</a-tag>
          </a-descriptions-item>
          <a-descriptions-item :label="pageText('pages.mcpLogDuration')">
            {{ selectedLog.duration_ms }} ms
          </a-descriptions-item>
          <a-descriptions-item :label="pageText('pages.mcpLogTarget')" :span="2">
            <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
              <a-typography-text code copyable v-if="selectedLog.target">{{ selectedLog.target }}</a-typography-text>
              <span v-else>-</span>
              <a-button
                v-if="getAuditPivot(selectedLog).taskRoute"
                size="small"
                type="link"
                style="padding: 0;"
                @click="navigateFromDrawer(getAuditPivot(selectedLog).taskRoute)"
              >
                <DashboardOutlined /> {{ pageText('pages.mcpPivotTaskBtn') }}
              </a-button>
              <a-button
                v-if="getAuditPivot(selectedLog).assetRoute"
                size="small"
                type="link"
                style="padding: 0;"
                @click="navigateFromDrawer(getAuditPivot(selectedLog).assetRoute)"
              >
                <GlobalOutlined /> {{ pageText('pages.mcpPivotAssetBtn') }}
              </a-button>
            </div>
          </a-descriptions-item>
        </a-descriptions>

        <!-- 被拦截时的排障直达提示 -->
        <a-alert
          v-if="selectedLog.status === 'denied'"
          type="warning"
          show-icon
          style="margin-top: 16px;"
          :message="isScopeDenied(selectedLog.error_message) ? pageText('pages.mcpDeniedHintScope') : pageText('pages.mcpDeniedHintPolicy')"
        >
          <template #action>
            <a-button
              size="small"
              type="link"
              @click="switchTabFromDrawer(isScopeDenied(selectedLog.error_message) ? 'keys' : 'policy')"
            >
              {{ isScopeDenied(selectedLog.error_message) ? pageText('pages.mcpFixInKeys') : pageText('pages.mcpFixInPolicy') }}
            </a-button>
          </template>
        </a-alert>

        <!-- 输入参数 JSON -->
        <div style="margin-top: 20px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <span style="font-weight: 600;">{{ pageText('pages.mcpLogDetailParams') }}</span>
            <a-button size="small" @click="handleCopyParams(selectedLog.params_summary)">
              <template #icon><CopyOutlined /></template>
              {{ pageText('pages.copy') }}
            </a-button>
          </div>
          <pre class="detail-code-block"><code>{{ formattedParams(selectedLog.params_summary) }}</code></pre>
        </div>

        <!-- 异常堆栈或返回摘要 -->
        <div style="margin-top: 20px;">
          <span style="font-weight: 600; display: block; margin-bottom: 8px;">{{ pageText('pages.mcpLogDetailResult') }}</span>
          <a-alert
            v-if="selectedLog.error_message"
            type="error"
            show-icon
            :message="selectedLog.error_message"
            style="white-space: pre-wrap; font-family: var(--arl-font-mono);"
          />
          <div v-else class="detail-summary-box">
            {{ selectedLog.summary || '-' }}
          </div>
        </div>
      </div>
    </a-drawer>

    <!-- 抽屉 2: PTES 渗透实战 Prompt 配方 -->
    <a-drawer
      v-model:open="promptDrawerVisible"
      :title="pageText('pages.mcpPromptDrawerTitle')"
      placement="right"
      width="560"
    >
      <div class="prompt-drawer-intro">{{ pageText('pages.mcpPromptDrawerIntro') }}</div>
      <div class="prompt-recipe-list">
        <a-card
          v-for="recipe in promptRecipes"
          :key="recipe.key"
          size="small"
          class="mcp-surface-card"
        >
          <template #title>
            <span style="font-size: 13px; font-weight: 600;">{{ recipe.title }}</span>
          </template>
          <template #extra>
            <a-button size="small" type="link" @click="copyTextDirect(recipe.body)">
              <template #icon><CopyOutlined /></template>
              {{ pageText('pages.copy') }}
            </a-button>
          </template>
          <div class="prompt-recipe-body">{{ recipe.body }}</div>
        </a-card>
      </div>
    </a-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, watch, onMounted, onActivated, onDeactivated, onUnmounted, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRoute, useRouter, onBeforeRouteLeave } from 'vue-router';
import { message, Modal } from 'ant-design-vue';
import {
  RobotOutlined,
  ReloadOutlined,
  CopyOutlined,
  DownloadOutlined,
  SafetyCertificateOutlined,
  InfoCircleOutlined,
  PlusOutlined,
  ThunderboltOutlined,
  BarChartOutlined,
  KeyOutlined,
  AlertOutlined,
  SearchOutlined,
  ExportOutlined,
  AimOutlined,
  BankOutlined,
  DashboardOutlined,
  StopOutlined,
  CloseCircleOutlined,
  ApiOutlined,
  BookOutlined,
  UndoOutlined,
  CheckOutlined,
  PlayCircleOutlined,
  GlobalOutlined
} from '@ant-design/icons-vue';
import request from '@/utils/request';
import { copyText } from '@/utils/clipboard';
import {
  resolveMcpCredential,
  createStdioServerConfig,
  buildClientConfigSnippet,
  MCP_TOOL_CATALOG,
  evaluateToolAccess,
  summarizeToolCapabilities,
  extractAuditPivot
} from '@/utils/mcpCredentials';
import { useSticky } from '@/utils/useSticky';
import { useGlobalPageSize } from '@/utils/useGlobalPageSize';

const { t, locale: pageLocale } = useI18n({ useScope: 'global' });
const pageText = t;
const route = useRoute();
const router = useRouter();

defineOptions({ name: 'McpCenter' });

const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);
const globalPageSize = useGlobalPageSize(10);

const VALID_TABS = ['setup', 'audit', 'keys', 'policy'];
const normalizeTab = (val) => {
  const map = { client_setup: 'setup', audit_logs: 'audit', api_keys: 'keys', tool_policy: 'policy' };
  const mapped = map[val] || val;
  return VALID_TABS.includes(mapped) ? mapped : 'setup';
};

// 1. 全局与导航状态
const activeTab = ref(normalizeTab(route.query?.tab));
const isRefreshing = ref(false);
const isCheckingOverview = ref(true);
const autoRefreshEnabled = ref(false);
let autoRefreshTimer = null;

const hostname = window.location.hostname;
const isIpAccess = ref(/^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$/.test(hostname) || hostname === 'localhost' || hostname === '127.0.0.1');

// 2. 接入与联调 (Tab: setup)
const mcpMode = ref(isIpAccess.value ? 'stdio' : 'sse');
const showCertGuide = ref(false);
const selectedKeyId = ref('current_session');
const keySecrets = reactive({});
const selectedClient = ref('cursor');
const stdioScriptPath = ref('~/Downloads/arl_mcp.py');
const stdioPythonBin = ref('python3');
const isDownloadingScript = ref(false);
const promptDrawerVisible = ref(false);

const switchToStdioMode = () => {
  mcpMode.value = 'stdio';
  updateConfigPreview();
};

const activeKeyOptions = ref([]);
const allKeyOptions = ref([]);

// 只读试跑台状态
const playgroundForm = reactive({
  tool: 'get_asset_profile',
  target: '',
  task_id: '',
  category: 'all',
  asset_type: 'site',
  limit: 10
});
const isPlaygroundRunning = ref(false);
const playgroundResult = ref(null);

// 3. 密钥管理 (Tab: keys)
const keySearchKeyword = ref('');
const keyStatusFilter = ref(undefined);
const keyList = ref([]);
const isKeysLoading = ref(false);
const keyPagination = reactive({ page: 1, size: globalPageSize.value, total: 0 });

const keyColumns = computed(() => [
  { title: pageText('pages.mcpColName'), dataIndex: 'name', key: 'name', width: 170 },
  { title: pageText('pages.mcpColKeyPrefix'), dataIndex: 'key_prefix', key: 'key_prefix', width: 150 },
  { title: pageText('pages.mcpColScopes'), key: 'scopes', width: 170 },
  { title: pageText('pages.mcpColStatus'), key: 'status', width: 110 },
  { title: pageText('pages.mcpColExpireAt'), dataIndex: 'expire_at', key: 'expire_at', width: 165 },
  { title: pageText('pages.mcpColLastActive'), key: 'last_active', width: 200 },
  { title: pageText('pages.mcpColCreatedAt'), dataIndex: 'created_at', key: 'created_at', width: 165 },
  { title: pageText('pages.action'), key: 'action', width: 250, fixed: 'right' }
]);

const createKeyModalVisible = ref(false);
const isCreatingKey = ref(false);
const newKeyForm = reactive({
  name: '',
  scopes: ['asset:read'],
  expire_days: 7
});
const isReadOnlyPreset = computed(() => !newKeyForm.scopes.includes('task:dispatch'));

const keySuccessModalVisible = ref(false);
const createdKeyPlaintext = ref('');

// 4. 调用监控 (Tab: audit)
const overviewData = reactive({
  today_calls: 0,
  week_calls: 0,
  total_keys: 0,
  active_keys: 0,
  error_calls_24h: 0,
  service_status: 'running',
  sse_status: 'offline',
  sse_sessions: 0
});

const activeMetricFilter = ref('');
const isLogDrawerVisible = ref(false);
const selectedLog = ref(null);

const logFilter = reactive({
  time_range: undefined,
  key_id: undefined,
  tool_name: undefined,
  status: undefined,
  target: ''
});
const logList = ref([]);
const isLogsLoading = ref(false);
const isExportingLogs = ref(false);
const logPagination = reactive({ page: 1, size: globalPageSize.value, total: 0 });

const logColumns = computed(() => [
  { title: pageText('pages.mcpLogTime'), dataIndex: 'created_at', key: 'created_at', width: 170, fixed: 'left' },
  { title: pageText('pages.mcpLogKeyName'), dataIndex: 'key_name', key: 'key_name', width: 145, ellipsis: true },
  { title: pageText('pages.mcpLogClientIp'), dataIndex: 'client_ip', key: 'client_ip', width: 130 },
  { title: pageText('pages.mcpLogTool'), dataIndex: 'tool_name', key: 'tool_name', width: 205 },
  { title: pageText('pages.mcpLogTarget'), dataIndex: 'target', key: 'target', width: 270, ellipsis: true },
  { title: pageText('pages.mcpLogDuration'), dataIndex: 'duration_ms', key: 'duration_ms', width: 105, align: 'center' },
  { title: pageText('pages.mcpLogStatus'), dataIndex: 'status', key: 'status', width: 100, align: 'center' },
  { title: pageText('pages.mcpLogSummary'), dataIndex: 'summary', key: 'summary', minWidth: 200, ellipsis: true },
  { title: pageText('pages.action'), key: 'action', width: 85, fixed: 'right', align: 'center' }
]);

// 5. 安全策略 (Tab: policy)
const isSavingPolicy = ref(false);
const toolSwitches = reactive({
  get_asset_profile: true,
  get_enterprise_profile: true,
  search_assets: true,
  get_task_status: true,
  create_scan_task: false,
  stop_scan_task: false
});
const policyForm = reactive({
  max_search_limit: 50,
  rate_limit_per_min: 120
});

const toolSwitchConfigs = computed(() => [
  { key: 'get_asset_profile', desc: pageText('pages.mcpToolDescProfile'), isDangerous: false },
  { key: 'get_enterprise_profile', desc: pageText('pages.mcpToolDescEnterprise'), isDangerous: false },
  { key: 'search_assets', desc: pageText('pages.mcpToolDescSearch'), isDangerous: false },
  { key: 'get_task_status', desc: pageText('pages.mcpToolDescTask'), isDangerous: false },
  { key: 'create_scan_task', desc: pageText('pages.mcpToolDescCreate'), isDangerous: true },
  { key: 'stop_scan_task', desc: pageText('pages.mcpToolDescStop'), isDangerous: true }
]);
const readToolConfigs = computed(() => toolSwitchConfigs.value.filter(t => !t.isDangerous));
const writeToolConfigs = computed(() => toolSwitchConfigs.value.filter(t => t.isDangerous));

// 6. 计算健康度、能力矩阵、配置片段
const healthTagColor = computed(() => {
  if (isCheckingOverview.value) return 'default';
  return overviewData.sse_status === 'online' ? 'success' : 'warning';
});

const healthLabelText = computed(() => {
  if (isCheckingOverview.value) return pageText('pages.mcpHealthChecking');
  return overviewData.sse_status === 'online'
    ? pageText('pages.mcpHealthAllOnline')
    : pageText('pages.mcpHealthRestOnly');
});

const healthTooltipText = computed(() => {
  if (isCheckingOverview.value) return pageText('pages.mcpHealthChecking');
  return overviewData.sse_status === 'online'
    ? pageText('pages.mcpHealthAllOnlineTip', { sessions: overviewData.sse_sessions || 0 })
    : pageText('pages.mcpHealthRestOnlyTip');
});

const selectedKeyRecord = computed(() => {
  if (selectedKeyId.value === 'current_session') return null;
  return activeKeyOptions.value.find(k => k.id === selectedKeyId.value) || null;
});

const effectiveCapabilities = computed(() => {
  return evaluateToolAccess({
    toolSwitches,
    keyScopes: selectedKeyRecord.value ? selectedKeyRecord.value.scopes : null,
    isSessionToken: selectedKeyId.value === 'current_session'
  });
});

const capabilitySummary = computed(() => summarizeToolCapabilities(effectiveCapabilities.value));

const formatCapabilityItemStatus = (item) => {
  if (item.allowed) return pageText('pages.mcpCapAvailable');
  if (item.reason === 'missing_scope') return pageText('pages.mcpCapMissingScope', { scope: item.scope });
  return pageText('pages.mcpCapPolicyDisabled');
};

const promptRecipes = computed(() => [
  { key: 'stage1', title: pageText('pages.mcpPromptStage1Title'), body: pageText('pages.mcpPromptStage1Body') },
  { key: 'stage2', title: pageText('pages.mcpPromptStage2Title'), body: pageText('pages.mcpPromptStage2Body') },
  { key: 'stage3', title: pageText('pages.mcpPromptStage3Title'), body: pageText('pages.mcpPromptStage3Body') },
  { key: 'stage4', title: pageText('pages.mcpPromptStage4Title'), body: pageText('pages.mcpPromptStage4Body') }
]);

const currentTokenValue = computed(() => {
  return resolveMcpCredential(selectedKeyId.value, localStorage.getItem('token'), keySecrets);
});

const configSnippet = computed(() => {
  const host = `${window.location.protocol}//${window.location.host}`;
  const token = currentTokenValue.value || '<YOUR_MCP_KEY>';
  const scriptPathArg = typeof stdioScriptPath !== 'undefined' && stdioScriptPath.value ? stdioScriptPath.value : undefined;
  const pyArg = typeof stdioPythonBin !== 'undefined' && stdioPythonBin.value ? stdioPythonBin.value : undefined;

  if (mcpMode.value === 'sse') {
    const sseConfig = {
      mcpServers: {
        'arl-next': {
          url: `${host}/mcp/sse`,
          headers: {
            Authorization: `Bearer ${token}`
          }
        }
      }
    };
    return JSON.stringify(sseConfig, null, 2);
  }
  const stdioConfig = {
    mcpServers: {
      'arl-next': createStdioServerConfig(scriptPathArg, pyArg ? { pythonBin: pyArg } : undefined)
    }
  };
  return JSON.stringify(stdioConfig, null, 2);
});

const activeClientSnippet = computed(() => {
  const host = `${window.location.protocol}//${window.location.host}`;
  return buildClientConfigSnippet({
    client: selectedClient.value,
    mode: mcpMode.value,
    host,
    token: currentTokenValue.value,
    scriptPath: stdioScriptPath.value,
    pythonBin: stdioPythonBin.value
  });
});

// 7. 辅助与格式化方法
const isKeyExpired = (record) => {
  if (!record) return false;
  if (typeof record.is_expired === 'boolean') return record.is_expired;
  if (!record.expire_at) return false;
  const iso = String(record.expire_at).replace(' ', 'T') + 'Z';
  const parsed = Date.parse(iso);
  return Number.isFinite(parsed) && parsed <= Date.now();
};

const getAuditPivot = (record) => extractAuditPivot(record);

const navigateToPivot = (routeObj) => {
  if (routeObj) router.push(routeObj);
};

const navigateFromDrawer = (routeObj) => {
  isLogDrawerVisible.value = false;
  navigateToPivot(routeObj);
};

const switchTabFromDrawer = (tabKey) => {
  isLogDrawerVisible.value = false;
  switchTab(tabKey);
};

const isScopeDenied = (errMsg = '') => {
  const lower = String(errMsg).toLowerCase();
  return lower.includes('scope') || lower.includes('asset:read') || lower.includes('task:dispatch');
};

const getToolMeta = (toolName) => {
  const metaMap = {
    get_asset_profile: { icon: AimOutlined, color: 'cyan', desc: pageText('pages.mcpToolDescProfile') },
    get_enterprise_profile: { icon: BankOutlined, color: 'purple', desc: pageText('pages.mcpToolDescEnterprise') },
    search_assets: { icon: SearchOutlined, color: 'blue', desc: pageText('pages.mcpToolDescSearch') },
    get_task_status: { icon: DashboardOutlined, color: 'geekblue', desc: pageText('pages.mcpToolDescTask') },
    create_scan_task: { icon: ThunderboltOutlined, color: 'orange', desc: pageText('pages.mcpToolDescCreate') },
    stop_scan_task: { icon: StopOutlined, color: 'red', desc: pageText('pages.mcpToolDescStop') }
  };
  return metaMap[toolName] || { icon: ThunderboltOutlined, color: 'default', desc: toolName || '' };
};

const getDurationClass = (ms) => {
  if (ms == null) return '';
  if (ms < 200) return 'duration-fast';
  if (ms <= 1000) return 'duration-medium';
  return 'duration-slow';
};

const copyTextDirect = async (text) => {
  if (!text) return;
  const ok = await copyText(text);
  if (ok) message.success(pageText('pages.copySuccess'));
};

const openLogDetail = (record) => {
  selectedLog.value = record;
  isLogDrawerVisible.value = true;
};

const handleCopyParams = async (params) => {
  const text = formattedParams(params);
  const ok = await copyText(text);
  if (ok) message.success(pageText('pages.copySuccess'));
};

const formattedParams = (str) => {
  if (!str) return '{}';
  try {
    const parsed = JSON.parse(str);
    return JSON.stringify(parsed, null, 2);
  } catch {
    return str;
  }
};

// 8. 导航与数据拉取
const switchTab = (tabKey) => {
  const nextTab = normalizeTab(tabKey);
  if (activeTab.value !== nextTab) {
    activeTab.value = nextTab;
    router.replace({ query: { ...route.query, tab: nextTab } });
  }
  handleTabChange(nextTab);
};

watch(() => route.query?.tab, (newVal) => {
  if (!newVal) return;
  const normalized = normalizeTab(String(newVal));
  if (normalized !== activeTab.value) {
    activeTab.value = normalized;
    handleTabChange(normalized);
  }
});

const handleTabChange = (key) => {
  if (key === 'keys') fetchKeys();
  else if (key === 'audit') {
    fetchOverview();
    fetchActiveKeyOptions();
    fetchLogs();
  } else if (key === 'policy') {
    fetchConfig();
  }
  syncAutoRefreshTimer();
};

const refreshActiveTab = async () => {
  isRefreshing.value = true;
  try {
    if (activeTab.value === 'setup') {
      await Promise.all([fetchOverview(), fetchActiveKeyOptions(), fetchConfig()]);
    } else if (activeTab.value === 'audit') {
      await Promise.all([fetchOverview(), fetchActiveKeyOptions(), fetchLogs()]);
    } else if (activeTab.value === 'keys') {
      await Promise.all([fetchOverview(), fetchKeys()]);
    } else if (activeTab.value === 'policy') {
      await Promise.all([fetchOverview(), fetchConfig()]);
    }
    message.success(pageText('pages.refreshSuccess'));
  } catch (e) {
    console.error('Failed to refresh data', e);
  } finally {
    isRefreshing.value = false;
  }
};

const fetchOverview = async () => {
  try {
    const res = await request.get('/mcp/overview');
    if (res && (res.code === 200 || res.data?.code === 200)) {
      const data = res.code === 200 ? res.data : res.data.data;
      if (data) Object.assign(overviewData, data);
    }
  } catch (e) {
    console.error('fetchOverview error', e);
  } finally {
    isCheckingOverview.value = false;
  }
};

const fetchActiveKeyOptions = async () => {
  try {
    const res = await request.get('/mcp/keys', {
      params: { page: 1, size: 100, keyword: '' }
    });
    if (res && (res.code === 200 || res.data?.code === 200)) {
      const data = (res.code === 200 ? res.data : res.data.data) || {};
      const items = data.items || [];
      allKeyOptions.value = items;
      activeKeyOptions.value = items.filter(k => k.status === 'active' && !isKeyExpired(k));
    }
  } catch (e) {
    console.error('fetchActiveKeyOptions error', e);
  }
};

const fetchKeys = async () => {
  isKeysLoading.value = true;
  try {
    const keyword = keySearchKeyword.value.trim();
    const res = await request.get('/mcp/keys', {
      params: {
        page: keyPagination.page,
        size: keyPagination.size,
        keyword,
        status: keyStatusFilter.value
      }
    });
    if (res && (res.code === 200 || res.data?.code === 200)) {
      const data = (res.code === 200 ? res.data : res.data.data) || {};
      keyList.value = data.items || [];
      keyPagination.total = data.total || 0;
    }
  } catch (e) {
    console.error('fetchKeys error', e);
  } finally {
    isKeysLoading.value = false;
  }
};

const handleKeyFilterSearch = () => {
  keyPagination.page = 1;
  fetchKeys();
};

const resetKeyFilter = () => {
  keySearchKeyword.value = '';
  keyStatusFilter.value = undefined;
  keyPagination.page = 1;
  fetchKeys();
};

const handleKeyPageChange = (page, pageSize) => {
  keyPagination.page = page;
  if (pageSize && pageSize !== keyPagination.size) {
    keyPagination.size = pageSize;
  }
  if (keyPagination.size !== globalPageSize.value) {
    globalPageSize.value = keyPagination.size;
  }
  fetchKeys();
};

const openCreateKeyModal = () => {
  newKeyForm.name = '';
  newKeyForm.scopes = ['asset:read'];
  newKeyForm.expire_days = 7;
  createKeyModalVisible.value = true;
};

const applyKeyPreset = (preset) => {
  if (preset === 'readonly') {
    newKeyForm.scopes = ['asset:read'];
    if (!newKeyForm.expire_days) newKeyForm.expire_days = 7;
  } else {
    newKeyForm.scopes = ['asset:read', 'task:dispatch'];
    if (!newKeyForm.expire_days) newKeyForm.expire_days = 7;
  }
};

const handleCreateKeySubmit = async () => {
  if (!newKeyForm.name.trim()) {
    message.warning(pageText('pages.mcpKeyNameRequired'));
    return;
  }
  isCreatingKey.value = true;
  try {
    const res = await request.post('/mcp/keys', newKeyForm);
    if (res && (res.code === 200 || res.data?.code === 200)) {
      const data = (res.code === 200 ? res.data : res.data.data) || {};
      createKeyModalVisible.value = false;
      createdKeyPlaintext.value = data.raw_key;
      if (data.id) {
        keySecrets[data.id] = data.raw_key;
        selectedKeyId.value = data.id;
      }
      keySuccessModalVisible.value = true;
      await Promise.all([
        fetchKeys(),
        typeof fetchActiveKeyOptions === 'function' ? fetchActiveKeyOptions() : Promise.resolve(),
        typeof fetchOverview === 'function' ? fetchOverview() : Promise.resolve()
      ]);
    } else {
      message.error(res?.message || res?.data?.message || pageText('pages.failed'));
    }
  } catch (e) {
    message.error(pageText('pages.failed'));
  } finally {
    isCreatingKey.value = false;
  }
};

const toggleKeyStatus = async (record) => {
  const targetStatus = record.status === 'active' ? 'revoked' : 'active';
  try {
    const res = await request.post(`/mcp/keys/${record.id}/status`, { status: targetStatus });
    if (res && (res.code === 200 || res.data?.code === 200)) {
      message.success(pageText('pages.operationSuccess'));
      await Promise.all([fetchKeys(), fetchActiveKeyOptions(), fetchOverview()]);
    } else {
      message.error(res?.message || res?.data?.message || pageText('pages.failed'));
    }
  } catch (e) {
    message.error(pageText('pages.failed'));
  }
};

const deleteKey = async (record) => {
  try {
    const res = await request.delete(`/mcp/keys/${record.id}`);
    if (res && (res.code === 200 || res.data?.code === 200)) {
      message.success(pageText('pages.deleteSuccess'));
      if (selectedKeyId.value === record.id) {
        selectedKeyId.value = 'current_session';
      }
      await Promise.all([fetchKeys(), fetchActiveKeyOptions(), fetchOverview()]);
    } else {
      message.error(res?.message || res?.data?.message || pageText('pages.failed'));
    }
  } catch (e) {
    message.error(pageText('pages.failed'));
  }
};

const useKeyInSetup = (record) => {
  selectedKeyId.value = record.id;
  switchTab('setup');
};

const viewKeyAuditLogs = (record) => {
  activeMetricFilter.value = '';
  logFilter.time_range = undefined;
  logFilter.tool_name = undefined;
  logFilter.status = undefined;
  logFilter.target = '';
  logFilter.key_id = record.id;
  logPagination.page = 1;
  switchTab('audit');
};

const toggleMetricFilter = (type) => {
  if (activeMetricFilter.value === type) {
    activeMetricFilter.value = '';
    logFilter.time_range = undefined;
    logFilter.status = undefined;
  } else {
    activeMetricFilter.value = type;
    if (type === 'today') {
      logFilter.time_range = 'today';
      logFilter.status = undefined;
    } else if (type === '7d') {
      logFilter.time_range = '7d';
      logFilter.status = undefined;
    } else if (type === 'error_24h') {
      logFilter.time_range = '24h';
      logFilter.status = 'abnormal';
    }
  }
  logPagination.page = 1;
  fetchLogs();
};

const handleFilterTimeChange = () => {
  syncActiveMetricCard();
  logPagination.page = 1;
  fetchLogs();
};

const handleFilterStatusChange = () => {
  syncActiveMetricCard();
  logPagination.page = 1;
  fetchLogs();
};

const handleLogFilterImmediate = () => {
  logPagination.page = 1;
  fetchLogs();
};

const syncActiveMetricCard = () => {
  if (logFilter.time_range === '24h' && logFilter.status === 'abnormal') {
    activeMetricFilter.value = 'error_24h';
  } else if (logFilter.time_range === 'today' && !logFilter.status) {
    activeMetricFilter.value = 'today';
  } else if (logFilter.time_range === '7d' && !logFilter.status) {
    activeMetricFilter.value = '7d';
  } else {
    activeMetricFilter.value = '';
  }
};

const fetchLogs = async () => {
  isLogsLoading.value = true;
  try {
    const res = await request.get('/mcp/logs', {
      params: {
        page: logPagination.page,
        size: logPagination.size,
        time_range: logFilter.time_range,
        key_id: logFilter.key_id,
        tool_name: logFilter.tool_name,
        status: logFilter.status,
        target: logFilter.target
      }
    });
    if (res && (res.code === 200 || res.data?.code === 200)) {
      const data = (res.code === 200 ? res.data : res.data.data) || {};
      logList.value = data.items || [];
      logPagination.total = data.total || 0;
    }
  } catch (e) {
    console.error('fetchLogs error', e);
  } finally {
    isLogsLoading.value = false;
  }
};

const handleLogPageChange = (page, pageSize) => {
  logPagination.page = page;
  if (pageSize && pageSize !== logPagination.size) {
    logPagination.size = pageSize;
  }
  if (logPagination.size !== globalPageSize.value) {
    globalPageSize.value = logPagination.size;
  }
  fetchLogs();
};

watch(globalPageSize, (newSize) => {
  keyPagination.size = newSize;
  logPagination.size = newSize;
});

const resetLogFilter = () => {
  activeMetricFilter.value = '';
  logFilter.time_range = undefined;
  logFilter.key_id = undefined;
  logFilter.tool_name = undefined;
  logFilter.status = undefined;
  logFilter.target = '';
  logPagination.page = 1;
  fetchLogs();
};

const exportLogsCsv = async () => {
  isExportingLogs.value = true;
  try {
    const token = localStorage.getItem('token') || '';
    const query = new URLSearchParams();
    if (logFilter.time_range) query.append('time_range', logFilter.time_range);
    if (logFilter.key_id) query.append('key_id', logFilter.key_id);
    if (logFilter.tool_name) query.append('tool_name', logFilter.tool_name);
    if (logFilter.status) query.append('status', logFilter.status);
    if (logFilter.target) query.append('target', logFilter.target);

    const res = await fetch(`/api/mcp/logs/export?${query.toString()}`, {
      headers: { Token: token }
    });
    if (!res.ok) {
      let errMsg = '';
      try {
        const errData = await res.json();
        errMsg = errData?.message || '';
      } catch {
        // 忽略非 JSON 错误体
      }
      message.error(errMsg || pageText('pages.exportFailed'));
      return;
    }
    const blob = await res.blob();
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = 'mcp_audit_logs.csv';
    link.click();
    URL.revokeObjectURL(link.href);
    message.success(pageText('pages.exportSuccess'));
  } catch (e) {
    message.error(pageText('pages.exportFailed'));
  } finally {
    isExportingLogs.value = false;
  }
};

// 9. 只读工具在线试跑台执行逻辑
const runPlaygroundTest = async () => {
  const token = currentTokenValue.value;
  if (!token) {
    message.warning(pageText('pages.mcpPlaygroundMissingKeyWarn'));
    return;
  }
  const targetVal = playgroundForm.target.trim();
  const taskIdVal = playgroundForm.task_id.trim();
  if (!targetVal && !(playgroundForm.tool === 'get_enterprise_profile' && taskIdVal)) {
    message.warning(pageText('pages.mcpPlaygroundTargetPlaceholder'));
    return;
  }

  let endpoint = '/api/mcp/asset_profile';
  const query = new URLSearchParams();
  if (playgroundForm.tool === 'get_asset_profile') {
    query.set('target', targetVal);
    if (taskIdVal) query.set('task_id', taskIdVal);
  } else if (playgroundForm.tool === 'get_enterprise_profile') {
    endpoint = '/api/mcp/enterprise_profile';
    if (targetVal) query.set('target', targetVal);
    if (taskIdVal) query.set('task_id', taskIdVal);
    query.set('category', playgroundForm.category || 'all');
  } else if (playgroundForm.tool === 'search_assets') {
    endpoint = '/api/mcp/search_assets';
    query.set('query', targetVal);
    query.set('asset_type', playgroundForm.asset_type || 'site');
    query.set('limit', String(playgroundForm.limit || 10));
  } else if (playgroundForm.tool === 'get_task_status') {
    endpoint = '/api/mcp/task_status';
    query.set('task_id', targetVal);
  }

  isPlaygroundRunning.value = true;
  const started = performance.now();
  try {
    const res = await fetch(`${endpoint}?${query.toString()}`, {
      method: 'GET',
      headers: { Token: token, Accept: 'application/json' }
    });
    const text = await res.text();
    const durationMs = Math.round(performance.now() - started);
    let formatted = text;
    try {
      formatted = JSON.stringify(JSON.parse(text), null, 2);
    } catch {
      // 保留原始响应体
    }
    playgroundResult.value = {
      ok: res.ok,
      httpStatus: res.status,
      durationMs,
      estTokens: Math.max(1, Math.ceil(text.length / 4)),
      body: formatted
    };
    fetchOverview();
  } catch (e) {
    playgroundResult.value = {
      ok: false,
      httpStatus: 0,
      durationMs: Math.round(performance.now() - started),
      estTokens: 0,
      body: String(e?.message || e)
    };
  } finally {
    isPlaygroundRunning.value = false;
  }
};

// 10. 工具安全策略脏状态感知与预设
const savedPolicySnapshot = ref('');

const currentPolicySnapshot = computed(() => JSON.stringify({
  switches: { ...toolSwitches },
  max_search_limit: policyForm.max_search_limit,
  rate_limit_per_min: policyForm.rate_limit_per_min
}));

const isPolicyDirty = computed(() => {
  return savedPolicySnapshot.value !== '' && savedPolicySnapshot.value !== currentPolicySnapshot.value;
});

const policyDirtyCount = computed(() => {
  if (!isPolicyDirty.value) return 0;
  let count = 0;
  try {
    const saved = JSON.parse(savedPolicySnapshot.value);
    for (const k in toolSwitches) {
      if (saved.switches && toolSwitches[k] !== saved.switches[k]) count++;
    }
    if (policyForm.max_search_limit !== saved.max_search_limit) count++;
    if (policyForm.rate_limit_per_min !== saved.rate_limit_per_min) count++;
  } catch {
    count = 1;
  }
  return count;
});

const resetPolicyChanges = () => {
  if (!savedPolicySnapshot.value) return;
  try {
    const saved = JSON.parse(savedPolicySnapshot.value);
    if (saved.switches) Object.assign(toolSwitches, saved.switches);
    if (saved.max_search_limit) policyForm.max_search_limit = saved.max_search_limit;
    if (saved.rate_limit_per_min) policyForm.rate_limit_per_min = saved.rate_limit_per_min;
  } catch {
    // 忽略解析异常
  }
};

const applyPolicyPreset = (mode) => {
  const enableDispatch = mode === 'full';
  toolSwitches.get_asset_profile = true;
  toolSwitches.get_enterprise_profile = true;
  toolSwitches.search_assets = true;
  toolSwitches.get_task_status = true;
  toolSwitches.create_scan_task = enableDispatch;
  toolSwitches.stop_scan_task = enableDispatch;
};

const fetchConfig = async () => {
  try {
    const res = await request.get('/mcp/config');
    if (res && (res.code === 200 || res.data?.code === 200)) {
      const data = (res.code === 200 ? res.data : res.data.data) || {};
      if (data.tool_switches) Object.assign(toolSwitches, data.tool_switches);
      if (data.max_search_limit) policyForm.max_search_limit = data.max_search_limit;
      if (data.rate_limit_per_min) policyForm.rate_limit_per_min = data.rate_limit_per_min;
      savedPolicySnapshot.value = JSON.stringify({
        switches: { ...toolSwitches },
        max_search_limit: policyForm.max_search_limit,
        rate_limit_per_min: policyForm.rate_limit_per_min
      });
    }
  } catch (e) {
    console.error('fetchConfig error', e);
  }
};

const savePolicyConfig = async () => {
  isSavingPolicy.value = true;
  try {
    const res = await request.post('/mcp/config', {
      tool_switches: toolSwitches,
      max_search_limit: policyForm.max_search_limit,
      rate_limit_per_min: policyForm.rate_limit_per_min
    });
    if (res && (res.code === 200 || res.data?.code === 200)) {
      message.success(pageText('pages.saveSuccess'));
      savedPolicySnapshot.value = currentPolicySnapshot.value;
    } else {
      message.error(res?.message || res?.data?.message || pageText('pages.failed'));
    }
  } catch (e) {
    message.error(pageText('pages.failed'));
  } finally {
    isSavingPolicy.value = false;
  }
};

onBeforeRouteLeave(() => {
  if (!isPolicyDirty.value) return true;
  return new Promise((resolve) => {
    Modal.confirm({
      title: pageText('pages.unsavedConfigurationChangesLabel2'),
      content: pageText('pages.thereAreCountUnsavedConfigurationChangesLeavingThisPage', { count: policyDirtyCount.value }),
      okText: pageText('pages.discardChangesAndLeave'),
      okType: 'danger',
      cancelText: pageText('tasks.stayOnThisPage'),
      onOk: () => resolve(true),
      onCancel: () => resolve(false)
    });
  });
});

// 11. 复制与导出脚本
const handleCopySnippet = async () => {
  if (!currentTokenValue.value) {
    message.warning(pageText('pages.mcpFullKeyRequired'));
    return;
  }
  const snippetText = typeof activeClientSnippet !== 'undefined' ? activeClientSnippet.value : configSnippet.value;
  const ok = await copyText(snippetText);
  if (ok) message.success(pageText('pages.mcpConfigurationCopiedToClipboard'));
};

const handleCopyCreatedKey = async () => {
  const ok = await copyText(createdKeyPlaintext.value);
  if (ok) message.success(pageText('pages.copySuccess'));
};

const handleDownloadScript = async () => {
  if (!currentTokenValue.value) {
    message.warning(pageText('pages.mcpFullKeyRequired'));
    return;
  }
  isDownloadingScript.value = true;
  try {
    const host = `${window.location.protocol}//${window.location.host}`;
    const token = currentTokenValue.value;
    const res = await fetch('/api/mcp/export_server', {
      method: 'POST',
      headers: { Token: localStorage.getItem('token') || '', 'Content-Type': 'application/json' },
      body: JSON.stringify({ host, ...(selectedKeyId.value === 'current_session' ? {} : { raw_key: token }) })
    });
    if (res.ok) {
      const blob = await res.blob();
      const link = document.createElement('a');
      link.href = URL.createObjectURL(blob);
      link.download = 'arl_mcp.py';
      link.click();
      URL.revokeObjectURL(link.href);
      message.success(pageText('pages.arlMcpPyExportedDownloadStarted'));
    } else {
      message.error(pageText('pages.failed'));
    }
  } catch (e) {
    message.error(pageText('pages.failed'));
  } finally {
    isDownloadingScript.value = false;
  }
};

const updateConfigPreview = () => {};
const handleKeySelectChange = () => {};

// 12. 实时静默轮询管理
const clearAutoRefreshTimer = () => {
  if (autoRefreshTimer) {
    clearInterval(autoRefreshTimer);
    autoRefreshTimer = null;
  }
};

const syncAutoRefreshTimer = () => {
  clearAutoRefreshTimer();
  if (activeTab.value === 'audit' && autoRefreshEnabled.value) {
    autoRefreshTimer = setInterval(() => {
      fetchOverview();
      fetchLogs();
    }, 8000);
  }
};

watch(autoRefreshEnabled, () => {
  syncAutoRefreshTimer();
});

onMounted(() => {
  fetchOverview();
  fetchActiveKeyOptions();
  fetchConfig();
  if (activeTab.value === 'keys') fetchKeys();
  else if (activeTab.value === 'audit') fetchLogs();
  syncAutoRefreshTimer();
});

onActivated(() => {
  fetchOverview();
  syncAutoRefreshTimer();
});

onDeactivated(() => {
  clearAutoRefreshTimer();
});

onUnmounted(() => {
  clearAutoRefreshTimer();
});
</script>

<style scoped>
.hero-brand-icon {
  font-size: 18px;
  color: var(--arl-theme-color);
}

.mcp-health-pill {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  border-radius: 12px;
  font-weight: 500;
  margin: 0;
  padding: 2px 10px;
}

.live-pulse {
  width: 7px;
  height: 7px;
  background-color: #52c41a;
  border-radius: 50%;
  box-shadow: 0 0 0 rgba(82, 196, 26, 0.4);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { box-shadow: 0 0 0 0 rgba(82, 196, 26, 0.7); }
  70% { box-shadow: 0 0 0 6px rgba(82, 196, 26, 0); }
  100% { box-shadow: 0 0 0 0 rgba(82, 196, 26, 0); }
}

.auto-refresh-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
}

.toggle-label {
  font-size: 12px;
  color: var(--arl-text-secondary);
}

.mcp-section-stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.mcp-surface-card {
  border-radius: 8px;
}

.mcp-full-height {
  height: 100%;
}

.mcp-right-stack {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.setup-control-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px 24px;
}

.setup-field-group {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  min-width: 0;
}

.setup-key-controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.field-label {
  font-weight: 500;
  font-size: 13px;
  color: var(--arl-text-color);
}

.mcp-aligned-badge {
  margin: 0;
}

.setup-secret-row {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px dashed var(--arl-border-color);
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.setup-session-hint {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--arl-border-color);
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--arl-text-secondary);
}

.setup-capability-strip {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px dashed var(--arl-border-color);
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px 16px;
}

.setup-capability-badges {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.setup-cap-pill {
  margin: 0;
  cursor: help;
}

.setup-capability-hints {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
}

.cap-hint-group {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.cap-hint-text {
  color: var(--arl-text-secondary);
}

.cap-tooltip-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 220px;
}

.cap-tooltip-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-size: 12px;
}

.cap-tooltip-row code {
  font-family: var(--arl-font-mono);
  font-size: 11px;
  color: inherit;
  background: rgba(255, 255, 255, 0.14);
  padding: 1px 5px;
  border-radius: 3px;
}

.cert-guide-box {
  margin-top: 10px;
  padding: 10px 12px;
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
  font-size: 12px;
  line-height: 1.6;
  color: var(--arl-text-color);
}

.client-desc {
  font-size: 13px;
  margin-bottom: 10px;
  color: var(--arl-text-secondary);
}

.stdio-options-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px 16px;
  padding: 8px 12px;
  margin-bottom: 10px;
  border-radius: 6px;
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
}

.stdio-option-field {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.field-hint-label {
  font-size: 12px;
  color: var(--arl-text-secondary);
  white-space: nowrap;
}

.config-code-box {
  position: relative;
  background: var(--arl-terminal-bg);
  border-radius: 8px;
  border: 1px solid var(--arl-terminal-border);
  overflow: hidden;
}

.code-pre {
  margin: 0;
  padding: 18px 120px 18px 18px;
  font-size: 13px;
  font-family: var(--arl-font-mono);
  color: var(--arl-terminal-text);
  overflow-x: auto;
  line-height: 1.6;
}

.code-actions {
  position: absolute;
  top: 12px;
  right: 12px;
  display: flex;
  gap: 8px;
}

.setup-footer-tips {
  margin-top: 16px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
  color: var(--arl-text-secondary);
}

.tip-item {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.tip-icon {
  color: var(--arl-theme-color);
  margin-top: 2px;
  flex-shrink: 0;
}

/* 在线试跑台 */
.playground-run-row {
  display: flex;
  gap: 8px;
  align-items: center;
}

.playground-output-wrap {
  margin-top: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.playground-meta-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
}

.playground-meta-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.playground-token-badge {
  font-size: 12px;
  font-family: var(--arl-font-mono);
  color: var(--arl-text-secondary);
}

.playground-terminal {
  margin: 0;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-word;
}

.playground-placeholder {
  margin-top: 12px;
  padding: 14px 12px;
  border-radius: 6px;
  border: 1px dashed var(--arl-border-color);
  background: var(--arl-bg-light);
  font-size: 12px;
  color: var(--arl-text-secondary);
  text-align: center;
}

/* TaskList 一致的 4 维指标卡 */
.task-metric-cards-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

@media (max-width: 1200px) {
  .task-metric-cards-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .task-metric-cards-row {
    grid-template-columns: 1fr;
  }
}

.metric-stat-card {
  background: var(--arl-bg-card);
  border: 1px solid var(--arl-border-color);
  border-radius: 8px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

.metric-stat-card:hover {
  border-color: color-mix(in srgb, var(--arl-theme-color) 45%, var(--arl-border-color));
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);
}

.metric-stat-card.active {
  border-color: var(--arl-theme-color);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--arl-theme-color) 20%, transparent);
  background: color-mix(in srgb, var(--arl-theme-color) 5%, var(--arl-bg-card));
}

.stat-card-inner {
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-icon-box {
  width: 38px;
  height: 38px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
  flex-shrink: 0;
}

.stat-icon-box.primary {
  background: color-mix(in srgb, var(--arl-theme-color) 14%, transparent);
  color: var(--arl-theme-color);
}

.stat-icon-box.info {
  background: rgba(24, 144, 255, 0.12);
  color: #1890ff;
}

.stat-icon-box.done {
  background: rgba(82, 196, 26, 0.12);
  color: #52c41a;
}

.stat-icon-box.error {
  background: rgba(255, 77, 79, 0.12);
  color: #ff4d4f;
}

.stat-info {
  min-width: 0;
}

.stat-label {
  font-size: 12px;
  color: var(--arl-text-secondary);
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  color: var(--arl-text-color);
  line-height: 1.3;
}

.stat-value.done {
  color: #52c41a;
}

.stat-value.error {
  color: #ff4d4f;
}

.stat-suffix {
  font-size: 13px;
  font-weight: 400;
  color: var(--arl-text-secondary);
}

/* 策略与开关 */
.tool-switch-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 10px 0;
  border-bottom: 1px solid var(--arl-border-color);
}

.tool-switch-item:last-child {
  border-bottom: none;
}

.tool-title {
  display: flex;
  align-items: center;
}

.tool-desc {
  font-size: 12px;
  color: var(--arl-text-secondary);
  margin-top: 4px;
}

.policy-preset-stack {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.policy-preset-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
}

.policy-preset-text {
  font-size: 12px;
  color: var(--arl-text-secondary);
  line-height: 1.5;
}

.field-hint {
  font-size: 12px;
  color: var(--arl-text-secondary);
  margin-top: 4px;
}

.detail-code-block {
  background: var(--arl-terminal-bg);
  border-radius: 6px;
  padding: 12px 16px;
  color: var(--arl-terminal-text);
  font-family: var(--arl-font-mono);
  font-size: 12px;
  line-height: 1.5;
  max-height: 320px;
  overflow: auto;
  margin: 0;
}

.detail-summary-box {
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--arl-text-color);
  line-height: 1.6;
}

/* 表格单元格样式 */
.mcp-time-cell {
  white-space: nowrap;
  font-family: var(--arl-font-mono);
  font-variant-numeric: tabular-nums;
  font-size: 12px;
  color: var(--arl-text-color);
}

.mcp-key-tag {
  display: inline-flex;
  align-items: center;
  max-width: 135px;
  margin: 0;
}

.mcp-key-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mcp-ip-cell {
  font-family: var(--arl-font-mono);
  font-size: 12px;
  color: var(--arl-text-secondary);
  white-space: nowrap;
}

.mcp-tool-tag {
  display: inline-flex;
  align-items: center;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: 4px;
  margin: 0;
  max-width: 195px;
}

.mcp-tool-icon {
  margin-right: 5px;
  font-size: 13px;
  flex-shrink: 0;
}

.mcp-tool-label {
  font-family: var(--arl-font-mono);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mcp-target-cell {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
  max-width: 100%;
}

.mcp-target-text {
  font-family: var(--arl-font-mono);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: var(--arl-text-color);
}

.mcp-target-placeholder {
  color: var(--arl-text-secondary);
  font-size: 12px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mcp-target-actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
}

.mcp-cell-copy-btn,
.mcp-cell-pivot-btn {
  opacity: 0.55;
  padding: 0 4px;
  height: 22px;
  color: var(--arl-text-secondary);
  transition: opacity 0.2s, color 0.2s;
}

.mcp-target-cell:hover .mcp-cell-copy-btn,
.mcp-target-cell:hover .mcp-cell-pivot-btn {
  opacity: 1;
  color: var(--arl-theme-color);
}

.mcp-duration-badge {
  display: inline-block;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-family: var(--arl-font-mono);
  font-variant-numeric: tabular-nums;
  font-weight: 500;
  white-space: nowrap;
}

.duration-fast {
  background-color: #f6ffed;
  color: #389e0d;
  border: 1px solid #b7eb8f;
}

.duration-medium {
  background-color: var(--arl-theme-soft-bg);
  color: var(--arl-theme-color);
  border: 1px solid var(--arl-theme-soft-border);
}

.duration-slow {
  background-color: #fff7e6;
  color: #d46b08;
  border: 1px solid #ffd591;
}

body.dark-mode .duration-fast {
  background-color: rgba(82, 196, 26, 0.15);
  color: #73d13d;
  border-color: rgba(82, 196, 26, 0.35);
}

body.dark-mode .duration-medium {
  background-color: color-mix(in srgb, var(--arl-theme-color) 16%, transparent);
  color: var(--arl-primary-light);
  border-color: var(--arl-theme-soft-border);
}

body.dark-mode .duration-slow {
  background-color: rgba(250, 140, 22, 0.15);
  color: #ffa940;
  border-color: rgba(250, 140, 22, 0.35);
}

.mcp-summary-error {
  display: inline-flex;
  align-items: center;
  color: #ff4d4f;
  font-size: 12px;
  max-width: 100%;
  overflow: hidden;
}

.mcp-summary-error-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.mcp-summary-text {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 12px;
  color: var(--arl-text-color);
}

.mcp-summary-empty,
.mcp-target-empty {
  color: var(--arl-text-secondary);
}

.key-row-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 2px;
}

.key-row-actions :deep(.ant-btn-link) {
  padding: 0 6px;
}

.text-expired {
  color: #faad14;
}

.input-search-icon {
  cursor: pointer;
  color: var(--arl-text-secondary);
}

.prompt-drawer-intro {
  font-size: 13px;
  color: var(--arl-text-secondary);
  margin-bottom: 14px;
  line-height: 1.6;
}

.prompt-recipe-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.prompt-recipe-body {
  font-size: 12px;
  line-height: 1.65;
  color: var(--arl-text-color);
  font-family: var(--arl-font-mono);
  white-space: pre-wrap;
}
</style>
