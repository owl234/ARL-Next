<template>
  <div class="mcp-center-container page-container">
    <!-- 1. 顶部 Hero 卡片 -->
    <div class="mcp-hero-card">
      <div class="mcp-hero-header">
        <div class="mcp-hero-left">
          <div class="mcp-hero-title">
            <RobotOutlined class="hero-icon" />
            <span class="title-text">{{ pageText('pages.mcpCenterTitle') }}</span>
            <a-tag color="success" class="status-tag">
              <span class="live-pulse"></span>
              {{ pageText('pages.mcpServerRunning') }}
            </a-tag>
          </div>
          <div class="mcp-hero-subtitle">
            {{ pageText('pages.mcpCenterSubtitle') }}
          </div>
        </div>
        <div class="mcp-hero-actions">
          <a-button @click="refreshAllData" :loading="isRefreshing">
            <template #icon><ReloadOutlined /></template>
            {{ pageText('pages.refresh') }}
          </a-button>
        </div>
      </div>
    </div>

    <!-- 2. 主选项卡 -->
    <a-card :bordered="false" class="mcp-content-card">
      <a-tabs v-model:activeKey="activeTab" @change="handleTabChange" class="mcp-main-tabs">
        <!-- Tab 1: 客户端接入向导 -->
        <a-tab-pane key="client_setup" :tab="pageText('pages.mcpTabClientSetup')">
          <div class="tab-section-wrapper">
            <!-- 模式切换与 Key 选择 -->
            <div class="setup-control-bar">
              <div class="setup-field-group">
                <span class="field-label">{{ pageText('pages.mcpAccessMode') }}:</span>
                <a-radio-group v-model:value="mcpMode" button-style="solid" @change="updateConfigPreview">
                  <a-radio-button value="sse">{{ pageText('pages.mcpModeRemoteSse') }}</a-radio-button>
                  <a-radio-button value="stdio">{{ pageText('pages.mcpModeLocalStdio') }}</a-radio-button>
                </a-radio-group>
              </div>

              <div class="setup-field-group">
                <span class="field-label">{{ pageText('pages.mcpBindKey') }}:</span>
                <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                  <a-select
                    v-model:value="selectedKeyId"
                    style="width: 260px;"
                    :placeholder="pageText('pages.mcpSelectKeyPlaceholder')"
                    @change="handleKeySelectChange"
                  >
                    <a-select-option value="current_session">{{ pageText('pages.mcpCurrentSessionToken') }}</a-select-option>
                    <a-select-option v-for="k in activeKeyOptions" :key="k.id" :value="k.id">
                      {{ k.name }} ({{ k.key_prefix }})
                    </a-select-option>
                  </a-select>
                  <a-button type="dashed" size="small" @click="openCreateKeyModal">
                    <template #icon><PlusOutlined /></template>
                    {{ pageText('pages.mcpCreateKeyQuick') }}
                  </a-button>
                  <a-tag v-if="selectedKeyId === 'current_session'" color="warning">
                    {{ pageText('pages.mcpSessionTokenTag') }}
                  </a-tag>
                  <a-tag v-else color="success">
                    {{ pageText('pages.mcpDedicatedKeyTag') }}
                  </a-tag>
                </div>
                <a-input-password
                  v-if="selectedKeyId !== 'current_session'"
                  v-model:value="keySecrets[selectedKeyId]"
                  :placeholder="pageText('pages.mcpFullKeyPlaceholder')"
                  autocomplete="off"
                  style="max-width: 520px; margin-top: 8px;"
                />
                <div v-if="selectedKeyId !== 'current_session'" class="field-hint">
                  {{ pageText('pages.mcpFullKeyHint') }}
                </div>
              </div>
            </div>

            <!-- IP / 自签证书友好提示 -->
            <div v-if="mcpMode === 'sse' && isIpAccess" style="margin-bottom: 16px;">
              <a-alert
                type="warning"
                show-icon
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
                    <div v-if="showCertGuide" style="margin-top: 10px; padding: 10px 12px; background: rgba(0, 0, 0, 0.03); border: 1px solid var(--arl-border-color, rgba(0, 0, 0, 0.06)); border-radius: 6px; font-size: 12px; line-height: 1.6;">
                      <div style="margin-bottom: 6px;">{{ pageText('pages.mcpCertGuideStep1') }}</div>
                      <div>{{ pageText('pages.mcpCertGuideStep2') }}</div>
                    </div>
                  </div>
                </template>
              </a-alert>
            </div>

            <!-- 客户端选项卡 (Cursor / Windsurf / Claude Code / Antigravity) -->
            <div class="client-tabs-wrapper">
              <a-tabs v-model:activeKey="selectedClient" type="card" size="small">
                <a-tab-pane key="cursor" tab="Cursor / Windsurf">
                  <div class="client-desc">
                    {{ pageText('pages.mcpCursorGuideDesc') }} <code>mcp.json</code>:
                  </div>
                </a-tab-pane>
                <a-tab-pane key="claude" tab="Claude Code / Desktop">
                  <div class="client-desc">
                    {{ pageText('pages.mcpClaudeGuideDesc') }} <code>claude_desktop_config.json</code>:
                  </div>
                </a-tab-pane>
                <a-tab-pane key="antigravity" tab="Antigravity / SDK">
                  <div class="client-desc">
                    {{ pageText('pages.mcpAntigravityGuideDesc') }}:
                  </div>
                </a-tab-pane>
              </a-tabs>

              <!-- 配置预览与一键复制 -->
              <div class="config-code-box">
                <pre class="code-pre"><code>{{ configSnippet }}</code></pre>
                <div class="code-actions">
                  <a-button type="primary" size="small" @click="handleCopySnippet">
                    <template #icon><CopyOutlined /></template>
                    {{ pageText('pages.copyConfiguration') }}
                  </a-button>
                  <a-button
                    v-if="mcpMode === 'stdio'"
                    type="default"
                    size="small"
                    :loading="isDownloadingScript"
                    @click="handleDownloadScript"
                  >
                    <template #icon><DownloadOutlined /></template>
                    {{ pageText('pages.downloadArlMcpPy') }}
                  </a-button>
                </div>
              </div>
            </div>

            <!-- 安全与环境使用指引 -->
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
          </div>
        </a-tab-pane>

        <!-- Tab 2: API Key 密钥管理 -->
        <a-tab-pane key="api_keys" :tab="pageText('pages.mcpTabKeyManagement')">
          <div class="tab-section-wrapper">
            <div class="table-toolbar">
              <div class="toolbar-left">
                <a-input-search
                  v-model:value="keySearchKeyword"
                  :placeholder="pageText('pages.mcpSearchKeyPlaceholder')"
                  style="width: 260px;"
                  allow-clear
                  @search="fetchKeys"
                />
              </div>
              <div class="toolbar-right">
                <a-button type="primary" @click="openCreateKeyModal">
                  <template #icon><PlusOutlined /></template>
                  {{ pageText('pages.mcpCreateKey') }}
                </a-button>
              </div>
            </div>

            <a-table
              :columns="keyColumns"
              :data-source="keyList"
              :loading="isKeysLoading"
              row-key="id"
              :pagination="{
                current: keyPagination.page,
                pageSize: keyPagination.size,
                total: keyPagination.total,
                showSizeChanger: true,
                pageSizeOptions: ['10', '20', '50'],
                showTotal: (total) => pageText('pages.totalItems', { total })
              }"
              @change="handleKeyTableChange"
              size="middle"
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
                    :status="record.status === 'active' ? 'success' : 'error'"
                    :text="record.status === 'active' ? pageText('pages.mcpStatusActive') : pageText('pages.mcpStatusRevoked')"
                  />
                </template>

                <template v-else-if="column.key === 'last_active'">
                  <span v-if="record.last_used_at">
                    {{ record.last_used_at }}
                    <span v-if="record.last_ip" style="color: var(--arl-text-secondary); font-size: 12px;">({{ record.last_ip }})</span>
                  </span>
                  <span v-else style="color: var(--arl-text-secondary);">-</span>
                </template>

                <template v-else-if="column.key === 'action'">
                  <div style="display: flex; gap: 8px;">
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
            </a-table>
          </div>
        </a-tab-pane>

        <!-- Tab 3: 调用审计日志 -->
        <a-tab-pane key="audit_logs" :tab="pageText('pages.mcpTabAuditLogs')">
          <div class="tab-section-wrapper">
            <!-- 统计指标卡片 -->
            <div class="metrics-grid">
              <a-card
                size="small"
                class="metric-card interactive-metric"
                :class="{ 'metric-active': activeMetricFilter === 'today' }"
                @click="toggleMetricFilter('today')"
              >
                <a-statistic
                  :title="pageText('pages.mcpTodayCalls')"
                  :value="overviewData.today_calls"
                  :value-style="{ color: 'var(--arl-theme-color)' }"
                >
                  <template #prefix><ThunderboltOutlined /></template>
                </a-statistic>
              </a-card>
              <a-card
                size="small"
                class="metric-card interactive-metric"
                :class="{ 'metric-active': activeMetricFilter === '7d' }"
                @click="toggleMetricFilter('7d')"
              >
                <a-statistic
                  :title="pageText('pages.mcpWeekCalls')"
                  :value="overviewData.week_calls"
                >
                  <template #prefix><BarChartOutlined /></template>
                </a-statistic>
              </a-card>
              <a-card
                size="small"
                class="metric-card interactive-metric"
                @click="activeTab = 'api_keys'"
              >
                <a-statistic
                  :title="pageText('pages.mcpActiveKeys')"
                  :value="overviewData.active_keys"
                  :suffix="'/ ' + overviewData.total_keys"
                >
                  <template #prefix><KeyOutlined /></template>
                </a-statistic>
              </a-card>
              <a-card
                size="small"
                class="metric-card interactive-metric"
                :class="{ 'metric-active': activeMetricFilter === 'error_24h' }"
                @click="toggleMetricFilter('error_24h')"
              >
                <a-statistic
                  :title="pageText('pages.mcpErrors24h')"
                  :value="overviewData.error_calls_24h"
                  :value-style="{ color: overviewData.error_calls_24h > 0 ? '#ff4d4f' : 'inherit' }"
                >
                  <template #prefix><AlertOutlined /></template>
                </a-statistic>
              </a-card>
            </div>

            <!-- 筛选栏 -->
            <div class="table-toolbar" style="margin-top: 16px;">
              <div class="toolbar-left" style="display: flex; gap: 10px; flex-wrap: wrap;">
                <a-select
                  v-model:value="logFilter.time_range"
                  style="width: 120px;"
                  allow-clear
                  :placeholder="pageText('pages.mcpFilterTimeAll')"
                  @change="handleFilterTimeChange"
                >
                  <a-select-option value="today">{{ pageText('pages.mcpFilterTimeToday') }}</a-select-option>
                  <a-select-option value="24h">{{ pageText('pages.mcpFilterTime24h') }}</a-select-option>
                  <a-select-option value="7d">{{ pageText('pages.mcpFilterTime7d') }}</a-select-option>
                </a-select>

                <a-select
                  v-model:value="logFilter.tool_name"
                  style="width: 180px;"
                  allow-clear
                  :placeholder="pageText('pages.mcpFilterToolPlaceholder')"
                >
                  <a-select-option value="get_asset_profile">get_asset_profile</a-select-option>
                  <a-select-option value="get_enterprise_profile">get_enterprise_profile</a-select-option>
                  <a-select-option value="search_assets">search_assets</a-select-option>
                  <a-select-option value="get_task_status">get_task_status</a-select-option>
                  <a-select-option value="create_scan_task">create_scan_task</a-select-option>
                  <a-select-option value="stop_scan_task">stop_scan_task</a-select-option>
                </a-select>

                <a-select
                  v-model:value="logFilter.status"
                  style="width: 140px;"
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
                  style="width: 200px;"
                  allow-clear
                  @pressEnter="fetchLogs"
                />

                <a-button type="primary" @click="fetchLogs">
                  <template #icon><SearchOutlined /></template>
                  {{ pageText('pages.search') }}
                </a-button>
                <a-button @click="resetLogFilter">
                  {{ pageText('pages.reset') }}
                </a-button>
              </div>

              <div class="toolbar-right">
                <a-button @click="exportLogsCsv" :loading="isExportingLogs">
                  <template #icon><ExportOutlined /></template>
                  {{ pageText('pages.exportCsv') }}
                </a-button>
              </div>
            </div>

            <!-- 审计日志表格 -->
            <a-table
              :columns="logColumns"
              :data-source="logList"
              :loading="isLogsLoading"
              row-key="id"
              :pagination="{
                current: logPagination.page,
                pageSize: logPagination.size,
                total: logPagination.total,
                showSizeChanger: true,
                pageSizeOptions: ['10', '20', '50'],
                showTotal: (total) => pageText('pages.totalItems', { total })
              }"
              :custom-row="(record) => ({
                onClick: () => openLogDetail(record),
                style: { cursor: 'pointer' }
              })"
              @change="handleLogTableChange"
              size="middle"
            >
              <template #bodyCell="{ column, record }">
                <template v-if="column.key === 'tool_name'">
                  <a-typography-text strong>{{ record.tool_name }}</a-typography-text>
                </template>

                <template v-else-if="column.key === 'target'">
                  <span v-if="record.target" style="font-family: monospace;">{{ record.target }}</span>
                  <span v-else style="color: var(--arl-text-secondary); font-size: 12px;">{{ record.params_summary }}</span>
                </template>

                <template v-else-if="column.key === 'duration_ms'">
                  <span>{{ record.duration_ms }} ms</span>
                </template>

                <template v-else-if="column.key === 'status'">
                  <a-tag v-if="record.status === 'success'" color="success">{{ pageText('pages.mcpStatusSuccess') }}</a-tag>
                  <a-tag v-else-if="record.status === 'denied'" color="warning">{{ pageText('pages.mcpStatusDenied') }}</a-tag>
                  <a-tag v-else color="error">{{ pageText('pages.mcpStatusError') }}</a-tag>
                </template>

                <template v-else-if="column.key === 'summary'">
                  <a-tooltip v-if="record.error_message" :title="record.error_message">
                    <span style="color: #ff4d4f;">{{ record.error_message }}</span>
                  </a-tooltip>
                  <span v-else>{{ record.summary || '-' }}</span>
                </template>

                <template v-else-if="column.key === 'action'">
                  <a-button type="link" size="small" @click.stop="openLogDetail(record)">
                    {{ pageText('pages.mcpViewDetail') }}
                  </a-button>
                </template>
              </template>
            </a-table>
          </div>
        </a-tab-pane>

        <!-- Tab 4: 工具安全策略 -->
        <a-tab-pane key="tool_policy" :tab="pageText('pages.mcpTabToolPolicy')">
          <div class="tab-section-wrapper" style="max-width: 800px;">
            <div v-if="isPolicyDirty" style="margin-bottom: 16px;">
              <a-alert
                type="info"
                show-icon
                :message="pageText('pages.mcpUnsavedPolicyChanges')"
                :description="pageText('pages.saveEachChangeBeforeLeavingThisPage')"
              />
            </div>

            <a-card size="small" :title="pageText('pages.mcpToolSwitchesTitle')" class="policy-card">
              <div class="tool-switch-item" v-for="t in toolSwitchConfigs" :key="t.key">
                <div class="tool-info">
                  <div class="tool-title">
                    <code>{{ t.key }}</code>
                    <a-tag :color="t.isDangerous ? 'orange' : 'blue'" style="margin-left: 8px;">
                      {{ t.isDangerous ? pageText('pages.mcpTagWrite') : pageText('pages.mcpTagRead') }}
                    </a-tag>
                  </div>
                  <div class="tool-desc">{{ t.desc }}</div>
                </div>
                <div class="tool-action">
                  <a-popconfirm
                    v-if="t.isDangerous && !toolSwitches[t.key]"
                    :title="pageText('pages.mcpRiskWriteNotice')"
                    :ok-text="pageText('pages.confirm')"
                    :cancel-text="pageText('tasks.cancel')"
                    @confirm="toolSwitches[t.key] = true"
                  >
                    <a-switch :checked="toolSwitches[t.key]" />
                  </a-popconfirm>
                  <a-switch
                    v-else
                    v-model:checked="toolSwitches[t.key]"
                  />
                </div>
              </div>
            </a-card>

            <a-card size="small" :title="pageText('pages.mcpQuotaTitle')" class="policy-card" style="margin-top: 16px;">
              <a-form layout="vertical">
                <a-form-item :label="pageText('pages.mcpMaxSearchLimit')">
                  <a-input-number
                    v-model:value="policyForm.max_search_limit"
                    :min="1"
                    :max="200"
                    style="width: 220px;"
                  />
                  <div class="field-hint">{{ pageText('pages.mcpMaxSearchLimitHint') }}</div>
                </a-form-item>

                <a-form-item :label="pageText('pages.mcpRateLimitPerMin')">
                  <a-input-number
                    v-model:value="policyForm.rate_limit_per_min"
                    :min="10"
                    :max="1000"
                    style="width: 220px;"
                  />
                  <div class="field-hint">{{ pageText('pages.mcpRateLimitHint') }}</div>
                </a-form-item>
              </a-form>
            </a-card>

            <div style="margin-top: 20px; display: flex; justify-content: flex-end;">
              <a-button
                type="primary"
                :loading="isSavingPolicy"
                :danger="isPolicyDirty"
                @click="savePolicyConfig"
              >
                {{ isPolicyDirty ? pageText('pages.mcpSavePolicyCount', { count: policyDirtyCount }) : pageText('pages.saveSettings') }}
              </a-button>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-card>

    <!-- 弹窗 1: 创建 API Key -->
    <a-modal
      v-model:open="createKeyModalVisible"
      :title="pageText('pages.mcpCreateKeyTitle')"
      @ok="handleCreateKeySubmit"
      :confirmLoading="isCreatingKey"
      @cancel="createKeyModalVisible = false"
      destroyOnClose
    >
      <a-form layout="vertical" style="margin-top: 12px;">
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

        <a-form-item :label="pageText('pages.mcpExpireDays')">
          <a-select v-model:value="newKeyForm.expire_days" style="width: 100%;">
            <a-select-option :value="0">{{ pageText('pages.mcpExpireNever') }}</a-select-option>
            <a-select-option :value="7">7 {{ pageText('pages.days') }}</a-select-option>
            <a-select-option :value="30">30 {{ pageText('pages.days') }}</a-select-option>
            <a-select-option :value="90">90 {{ pageText('pages.days') }}</a-select-option>
            <a-select-option :value="180">180 {{ pageText('pages.days') }}</a-select-option>
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
          <a-input :value="createdKeyPlaintext" readonly style="font-family: monospace;" />
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

    <!-- 抽屉: 审计日志详情 -->
    <a-drawer
      v-model:open="isLogDrawerVisible"
      :title="pageText('pages.mcpDrawerTitle')"
      placement="right"
      width="640"
      destroy-on-close
    >
      <div v-if="selectedLog" class="log-detail-container">
        <!-- 基础元数据 -->
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
            <a-typography-text code copyable v-if="selectedLog.target">{{ selectedLog.target }}</a-typography-text>
            <span v-else>-</span>
          </a-descriptions-item>
        </a-descriptions>

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
            style="white-space: pre-wrap; font-family: monospace;"
          />
          <div v-else class="detail-summary-box">
            {{ selectedLog.summary || '-' }}
          </div>
        </div>
      </div>
    </a-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue';
import { useI18n } from 'vue-i18n';
import { onBeforeRouteLeave } from 'vue-router';
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
  ExportOutlined
} from '@ant-design/icons-vue';
import request from '@/utils/request';
import { copyText } from '@/utils/clipboard';
import { resolveMcpCredential, createStdioServerConfig } from '@/utils/mcpCredentials';

const { t } = useI18n({ useScope: 'global' });
const pageText = t;

// 1. 全局状态
const activeTab = ref('client_setup');
const isRefreshing = ref(false);
const hostname = window.location.hostname;
const isIpAccess = ref(/^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$/.test(hostname) || hostname === 'localhost' || hostname === '127.0.0.1');

// 2. Tab 1: 客户端接入
const mcpMode = ref(isIpAccess.value ? 'stdio' : 'sse');
const showCertGuide = ref(false);
const selectedKeyId = ref('current_session');
const keySecrets = reactive({});
const selectedClient = ref('cursor');
const isDownloadingScript = ref(false);

const switchToStdioMode = () => {
  mcpMode.value = 'stdio';
  updateConfigPreview();
};

const activeKeyOptions = ref([]);

// 3. Tab 2: Key 列表与管理
const keySearchKeyword = ref('');
const keyList = ref([]);
const isKeysLoading = ref(false);
const keyPagination = reactive({ page: 1, size: 10, total: 0 });

const keyColumns = [
  { title: pageText('pages.mcpColName'), dataIndex: 'name', key: 'name' },
  { title: pageText('pages.mcpColKeyPrefix'), dataIndex: 'key_prefix', key: 'key_prefix' },
  { title: pageText('pages.mcpColScopes'), key: 'scopes' },
  { title: pageText('pages.mcpColStatus'), key: 'status' },
  { title: pageText('pages.mcpColExpireAt'), dataIndex: 'expire_at', key: 'expire_at' },
  { title: pageText('pages.mcpColLastActive'), key: 'last_active' },
  { title: pageText('pages.mcpColCreatedAt'), dataIndex: 'created_at', key: 'created_at' },
  { title: pageText('pages.action'), key: 'action', width: 140 }
];

// 新建 Key 表单
const createKeyModalVisible = ref(false);
const isCreatingKey = ref(false);
const newKeyForm = reactive({
  name: '',
  scopes: ['asset:read'],
  expire_days: 0
});

// 新建完成展示
const keySuccessModalVisible = ref(false);
const createdKeyPlaintext = ref('');

// 4. Tab 3: 审计日志与指标
const overviewData = reactive({
  today_calls: 0,
  week_calls: 0,
  total_keys: 0,
  active_keys: 0,
  error_calls_24h: 0,
  service_status: 'running'
});

const activeMetricFilter = ref('');
const isLogDrawerVisible = ref(false);
const selectedLog = ref(null);

const logFilter = reactive({
  time_range: undefined,
  tool_name: undefined,
  status: undefined,
  target: ''
});
const logList = ref([]);
const isLogsLoading = ref(false);
const isExportingLogs = ref(false);
const logPagination = reactive({ page: 1, size: 10, total: 0 });

const logColumns = [
  { title: pageText('pages.mcpLogTime'), dataIndex: 'created_at', key: 'created_at', width: 170 },
  { title: pageText('pages.mcpLogKeyName'), dataIndex: 'key_name', key: 'key_name' },
  { title: pageText('pages.mcpLogClientIp'), dataIndex: 'client_ip', key: 'client_ip', width: 130 },
  { title: pageText('pages.mcpLogTool'), key: 'tool_name' },
  { title: pageText('pages.mcpLogTarget'), key: 'target' },
  { title: pageText('pages.mcpLogDuration'), key: 'duration_ms', width: 100 },
  { title: pageText('pages.mcpLogStatus'), key: 'status', width: 100 },
  { title: pageText('pages.mcpLogSummary'), key: 'summary' },
  { title: pageText('pages.action'), key: 'action', width: 80, fixed: 'right' }
];

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

// 5. Tab 4: 工具策略
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

const toolSwitchConfigs = [
  { key: 'get_asset_profile', desc: pageText('pages.mcpToolDescProfile'), isDangerous: false },
  { key: 'get_enterprise_profile', desc: pageText('pages.mcpToolDescEnterprise'), isDangerous: false },
  { key: 'search_assets', desc: pageText('pages.mcpToolDescSearch'), isDangerous: false },
  { key: 'get_task_status', desc: pageText('pages.mcpToolDescTask'), isDangerous: false },
  { key: 'create_scan_task', desc: pageText('pages.mcpToolDescCreate'), isDangerous: true },
  { key: 'stop_scan_task', desc: pageText('pages.mcpToolDescStop'), isDangerous: true }
];

// 6. 计算配置片段
const currentTokenValue = computed(() => {
  return resolveMcpCredential(selectedKeyId.value, localStorage.getItem('token'), keySecrets);
});

const configSnippet = computed(() => {
  const host = `${window.location.protocol}//${window.location.host}`;
  const token = currentTokenValue.value || '<YOUR_MCP_KEY>';

  if (mcpMode.value === 'sse') {
    const sseConfig = {
      "mcpServers": {
        "arl-next": {
          "url": `${host}/mcp/sse`,
          "headers": {
            "Authorization": `Bearer ${token}`
          }
        }
      }
    };
    return JSON.stringify(sseConfig, null, 2);
  } else {
    const stdioConfig = {
      "mcpServers": {
        "arl-next": createStdioServerConfig()
      }
    };
    return JSON.stringify(stdioConfig, null, 2);
  }
});

// 方法实现
const refreshAllData = async () => {
  isRefreshing.value = true;
  try {
    await Promise.all([fetchOverview(), fetchKeys(), fetchLogs(), fetchConfig()]);
    message.success(pageText('pages.refreshSuccess'));
  } catch (e) {
    console.error('Failed to refresh data', e);
  } finally {
    isRefreshing.value = false;
  }
};

const handleTabChange = (key) => {
  if (key === 'api_keys') fetchKeys();
  else if (key === 'audit_logs') {
    fetchOverview();
    fetchLogs();
  } else if (key === 'tool_policy') fetchConfig();
};

const fetchOverview = async () => {
  try {
    const res = await request.get('/mcp/overview');
    if (res && res.data && res.data.code === 200) {
      Object.assign(overviewData, res.data.data);
    }
  } catch (e) {
    console.error('fetchOverview error', e);
  }
};

const fetchKeys = async () => {
  isKeysLoading.value = true;
  try {
    const res = await request.get('/mcp/keys', {
      params: {
        page: keyPagination.page,
        size: keyPagination.size,
        keyword: keySearchKeyword.value
      }
    });
    if (res && res.data && res.data.code === 200) {
      const data = res.data.data;
      keyList.value = data.items || [];
      keyPagination.total = data.total || 0;
      activeKeyOptions.value = (data.items || []).filter(k => k.status === 'active');
    }
  } catch (e) {
    console.error('fetchKeys error', e);
  } finally {
    isKeysLoading.value = false;
  }
};

const handleKeyTableChange = (pagination) => {
  keyPagination.page = pagination.current;
  keyPagination.size = pagination.pageSize;
  fetchKeys();
};

const openCreateKeyModal = () => {
  newKeyForm.name = '';
  newKeyForm.scopes = ['asset:read'];
  newKeyForm.expire_days = 0;
  createKeyModalVisible.value = true;
};

const handleCreateKeySubmit = async () => {
  if (!newKeyForm.name.trim()) {
    message.warning(pageText('pages.mcpKeyNameRequired'));
    return;
  }
  isCreatingKey.value = true;
  try {
    const res = await request.post('/mcp/keys', newKeyForm);
    if (res && res.data && res.data.code === 200) {
      createKeyModalVisible.value = false;
      createdKeyPlaintext.value = res.data.data.raw_key;
      keySecrets[res.data.data.id] = res.data.data.raw_key;
      keySuccessModalVisible.value = true;
      await fetchKeys();
      if (res.data.data.id) {
        selectedKeyId.value = res.data.data.id;
      }
    } else {
      message.error(res?.data?.message || pageText('pages.failed'));
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
    if (res && res.data && res.data.code === 200) {
      message.success(pageText('pages.operationSuccess'));
      fetchKeys();
    } else {
      message.error(res?.data?.message || pageText('pages.failed'));
    }
  } catch (e) {
    message.error(pageText('pages.failed'));
  }
};

const deleteKey = async (record) => {
  try {
    const res = await request.delete(`/mcp/keys/${record.id}`);
    if (res && res.data && res.data.code === 200) {
      message.success(pageText('pages.deleteSuccess'));
      fetchKeys();
    } else {
      message.error(res?.data?.message || pageText('pages.failed'));
    }
  } catch (e) {
    message.error(pageText('pages.failed'));
  }
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
        tool_name: logFilter.tool_name,
        status: logFilter.status,
        target: logFilter.target
      }
    });
    if (res && res.data && res.data.code === 200) {
      const data = res.data.data;
      logList.value = data.items || [];
      logPagination.total = data.total || 0;
    }
  } catch (e) {
    console.error('fetchLogs error', e);
  } finally {
    isLogsLoading.value = false;
  }
};

const handleLogTableChange = (pagination) => {
  logPagination.page = pagination.current;
  logPagination.size = pagination.pageSize;
  fetchLogs();
};

const resetLogFilter = () => {
  activeMetricFilter.value = '';
  logFilter.time_range = undefined;
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
    if (logFilter.tool_name) query.append('tool_name', logFilter.tool_name);
    if (logFilter.status) query.append('status', logFilter.status);
    if (logFilter.target) query.append('target', logFilter.target);

    const res = await fetch(`/api/mcp/logs/export?${query.toString()}`, {
      headers: { Token: token }
    });
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

// 工具安全策略脏状态感知
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

const fetchConfig = async () => {
  try {
    const res = await request.get('/mcp/config');
    if (res && res.data && res.data.code === 200) {
      const data = res.data.data;
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
    if (res && res.data && res.data.code === 200) {
      message.success(pageText('pages.saveSuccess'));
      savedPolicySnapshot.value = currentPolicySnapshot.value;
    } else {
      message.error(res?.data?.message || pageText('pages.failed'));
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
      onCancel: () => resolve(false),
    });
  });
});

const handleCopySnippet = async () => {
  if (!currentTokenValue.value) {
    message.warning(pageText('pages.mcpFullKeyRequired'));
    return;
  }
  const ok = await copyText(configSnippet.value);
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

onMounted(() => {
  fetchOverview();
  fetchKeys();
  fetchConfig();
});
</script>

<style scoped>
.mcp-center-container {
  padding: 16px;
}

.mcp-hero-card {
  background: var(--arl-card-bg, #ffffff);
  border-radius: 8px;
  padding: 20px 24px;
  margin-bottom: 16px;
  border: 1px solid var(--arl-border-color, #e2e8f0);
}

.mcp-hero-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.mcp-hero-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 20px;
  font-weight: 600;
  color: var(--arl-text-color, #1e293b);
}

.hero-icon {
  font-size: 24px;
  color: var(--arl-theme-color, #1890ff);
}

.status-tag {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-weight: 500;
  border-radius: 12px;
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

.mcp-hero-subtitle {
  margin-top: 6px;
  font-size: 13px;
  color: var(--arl-text-secondary, #64748b);
}

.mcp-content-card {
  border-radius: 8px;
}

.tab-section-wrapper {
  padding-top: 8px;
}

.setup-control-bar {
  display: flex;
  align-items: center;
  gap: 32px;
  margin-bottom: 18px;
  padding: 12px 16px;
  background: var(--arl-bg-light, #f8fafc);
  border-radius: 6px;
}

.setup-field-group {
  display: flex;
  align-items: center;
  gap: 10px;
}

.field-label {
  font-weight: 500;
  font-size: 13px;
  color: var(--arl-text-color, #334155);
}

.client-tabs-wrapper {
  margin-top: 14px;
}

.client-desc {
  font-size: 13px;
  margin-bottom: 10px;
  color: var(--arl-text-secondary, #64748b);
}

.config-code-box {
  position: relative;
  background: #0f172a;
  border-radius: 8px;
  border: 1px solid #1e293b;
  overflow: hidden;
}

.code-pre {
  margin: 0;
  padding: 18px 20px;
  font-size: 13px;
  font-family: 'Fira Code', monospace;
  color: #38bdf8;
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
  margin-top: 18px;
  display: flex;
  flex-direction: column;
  gap: 8px;
  font-size: 12px;
  color: var(--arl-text-secondary, #64748b);
}

.tip-item {
  display: flex;
  align-items: center;
  gap: 8px;
}

.tip-icon {
  color: var(--arl-theme-color, #1890ff);
}

.table-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
}

.metric-card {
  border-radius: 6px;
}

.policy-card {
  border-radius: 6px;
}

.tool-switch-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 0;
  border-bottom: 1px solid var(--arl-border-color, #f1f5f9);
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
  color: var(--arl-text-secondary, #64748b);
  margin-top: 4px;
}

.field-hint {
  font-size: 12px;
  color: var(--arl-text-secondary, #64748b);
  margin-top: 4px;
}

.interactive-metric {
  cursor: pointer;
  transition: all 0.25s ease;
  user-select: none;
}

.interactive-metric:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.metric-active {
  border-color: var(--arl-theme-color, #1890ff) !important;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.2) !important;
  background: rgba(24, 144, 255, 0.02);
}

.detail-code-block {
  background: #0f172a;
  border-radius: 6px;
  padding: 12px 16px;
  color: #38bdf8;
  font-family: 'Fira Code', monospace;
  font-size: 12px;
  line-height: 1.5;
  max-height: 320px;
  overflow: auto;
  margin: 0;
}

.detail-summary-box {
  background: var(--arl-bg-light, #f8fafc);
  border: 1px solid var(--arl-border-color, #e2e8f0);
  border-radius: 6px;
  padding: 10px 14px;
  font-size: 13px;
  color: var(--arl-text-color, #334155);
  line-height: 1.6;
}
</style>
