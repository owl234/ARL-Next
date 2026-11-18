<template>
  <div class="arl-page-container arl-settings-page" :class="{ 'page-wide-text': pageLocale !== 'zh-CN' }">
    <!-- 统一吸顶 Hero 控制中枢（对齐全站 TaskList / McpCenter / GithubManage 规范） -->
    <div ref="actionBarRef" class="arl-hero-card">
      <div class="arl-hero-unified-bar">
        <div class="arl-hero-left">
          <div class="arl-hero-title">
            <SettingOutlined class="hero-brand-icon" />
            <span class="title-text">{{ pageText('navigation.settings') }}</span>
          </div>

          <div class="arl-capsule-switcher">
            <button
              v-for="dom in DOMAIN_TABS"
              :key="dom.key"
              type="button"
              class="arl-capsule-item"
              :class="{ 'is-active': activeKey === dom.key }"
              @click="switchDomain(dom.key)"
            >
              <component :is="dom.icon" class="capsule-icon" />
              <span>{{ pageText(dom.labelKey) }}</span>
              <span v-if="domainDirtyCounts[dom.key] > 0" class="arl-capsule-count">
                <span class="arl-capsule-dot is-pulse"></span>
                {{ domainDirtyCounts[dom.key] }}
              </span>
            </button>
          </div>
        </div>

        <div class="arl-hero-right">
          <!-- 全局设置快速搜索（/ 或 Cmd/Ctrl+K 聚焦，下拉浮层不撑开页面） -->
          <div class="hero-search-anchor" ref="searchBoxWrapRef">
            <a-input
              ref="searchInputRef"
              v-model:value="settingsKeyword"
              :placeholder="pageText('pages.settingsSearchShortcutPlaceholder')"
              size="small"
              allow-clear
              class="hero-search-input"
              @keydown.esc="settingsKeyword = ''"
            >
              <template #prefix>
                <SearchOutlined style="opacity: 0.45;" />
              </template>
            </a-input>

            <div v-if="settingsKeyword.trim()" class="arl-hero-search-dropdown">
              <div class="arl-search-dropdown-meta">
                <span>{{ pageText('pages.settingsMatchCount', { count: settingsSearchResults.length }) }}</span>
                <a class="page-small-text" @click="settingsKeyword = ''">{{ pageText('pages.clear') }}</a>
              </div>
              <div v-if="settingsSearchResults.length === 0" class="arl-search-empty">
                {{ pageText('pages.noMatchingSettingsTryFofaConcurrencyBlocklistWebhookProxy') }}
              </div>
              <div v-else class="arl-search-dropdown-list">
                <div
                  v-for="item in settingsSearchResults"
                  :key="item.tab + ':' + item.anchor + ':' + item.label"
                  class="arl-search-item"
                  @click="jumpToSetting(item)"
                >
                  <div class="arl-search-item-main">
                    <span class="arl-search-item-label">{{ item.label }}</span>
                    <span class="arl-search-item-desc">{{ item.desc }}</span>
                  </div>
                  <a-tag color="blue" style="margin: 0;">{{ item.tabLabel }}</a-tag>
                </div>
              </div>
            </div>
          </div>

          <div class="arl-hero-v-divider"></div>

          <!-- 统一操作区：当前页为可保存表单时提供重置/保存，多分区脏态提供全部保存，主按钮固定在最右侧 -->
          <template v-if="activeViewSections.length > 0">
            <a-button
              v-if="activeKey === 'scanning_arsenal' && arsenalSubTab === 'concurrency'"
              size="small"
              :loading="performanceLoading"
              @click="fetchPerformanceConfig"
            >
              <template #icon><ReloadOutlined /></template>
              {{ pageText('pages.refreshStatus') }}
            </a-button>

            <a-popconfirm
              v-if="activeSectionDirty"
              :title="pageText('pages.confirmResetSectionChanges')"
              :ok-text="pageText('pages.confirmResetBtn')"
              :cancel-text="pageText('pages.cancel')"
              ok-type="danger"
              @confirm="resetActiveViewSections"
            >
              <a-button size="small" :disabled="batchSaving || activeSectionSaving">
                <template #icon><UndoOutlined /></template>
                {{ pageText('pages.reset') }}
              </a-button>
            </a-popconfirm>

            <a-button
              v-if="unsavedCount > 1"
              size="small"
              :loading="batchSaving"
              @click="saveAllDirtySections"
            >
              {{ pageText('pages.saveAllCount', { count: unsavedCount }) }}
            </a-button>

            <a-button
              type="primary"
              size="small"
              :disabled="!activeSectionDirty"
              :loading="activeSectionSaving"
              :class="{ 'arl-dirty-btn': activeSectionDirty }"
              @click="saveActiveViewSections"
            >
              <template #icon><CheckOutlined /></template>
              {{ activeSectionDirty ? pageText('pages.settingsSaveSectionBtn') : pageText('pages.settingsAllSavedStatus') }}
            </a-button>
          </template>

          <template v-else-if="unsavedCount > 0">
            <a-popconfirm
              :title="pageText('pages.confirmResetAllChanges', { count: unsavedCount })"
              :ok-text="pageText('pages.confirmResetBtn')"
              :cancel-text="pageText('pages.cancel')"
              ok-type="danger"
              @confirm="resetAllDirtySections"
            >
              <a-button size="small" :disabled="batchSaving">
                <template #icon><UndoOutlined /></template>
                {{ pageText('pages.resetAllChanges') }}
              </a-button>
            </a-popconfirm>

            <a-button size="small" @click="goToFirstDirty">
              {{ pageText('pages.settingsJumpFirstDirty', { count: unsavedCount }) }}
            </a-button>

            <a-button
              type="primary"
              size="small"
              class="arl-dirty-btn"
              :loading="batchSaving"
              @click="saveAllDirtySections"
            >
              <template #icon><CheckOutlined /></template>
              {{ pageText('pages.saveAllCount', { count: unsavedCount }) }}
            </a-button>
          </template>

          <a-tag v-else color="success" style="margin: 0;">
            {{ pageText('pages.settingsAllSavedStatus') }}
          </a-tag>
        </div>
      </div>

      <!-- 二级导航（按当前主域动态呈现统一卡片页签） -->
      <div v-if="activeKey === 'egress_guardrails'" class="hero-subtabs-row">
        <a-tabs v-model:activeKey="guardrailSubTab" type="card" size="small" class="arl-detail-tabs settings-hero-tabs">
          <a-tab-pane key="proxy" :tab="tabTitle(pageText('pages.settingsSubProxy'), !!proxyPanelRef?.hasUnsavedChanges?.())" />
          <a-tab-pane key="security" :tab="tabTitle(pageText('pages.settingsSubGuardrails'), isSecurityDirty)" />
        </a-tabs>
      </div>

      <div v-else-if="activeKey === 'scanning_arsenal'" class="hero-subtabs-row">
        <a-tabs v-model:activeKey="arsenalSubTab" type="card" size="small" class="arl-detail-tabs settings-hero-tabs">
          <a-tab-pane
            key="concurrency"
            :tab="tabTitle(pageText('pages.settingsSubConcurrency'), isPerformanceDirty || Object.keys(pendingByGroup.scan_params || {}).length > 0)"
          />
          <a-tab-pane key="dict" :tab="pageText('pages.settingsSubDict')" />
          <a-tab-pane key="cdn" :tab="pageText('pages.settingsSubCdn')" />
        </a-tabs>
      </div>

      <div v-else-if="activeKey === 'system_ops'" class="hero-subtabs-row">
        <a-tabs v-model:activeKey="opsSubTab" type="card" size="small" class="arl-detail-tabs settings-hero-tabs">
          <a-tab-pane key="auth_infra" :tab="tabTitle(pageText('pages.settingsSubAuthInfra'), Object.keys(pendingByGroup.system_auth || {}).length > 0)" />
          <a-tab-pane key="backup" :tab="pageText('pages.settingsSubBackup')" />
          <a-tab-pane key="update" :tab="pageText('pages.settingsSubUpdate')" />
        </a-tabs>
      </div>
    </div>

    <!-- ================================================================ -->
    <!-- 主域 1：情报凭据（默认首屏） -->
    <!-- ================================================================ -->
    <div v-show="activeKey === 'intel'" class="settings-section-container">
      <a-spin :spinning="generalLoading">
        <a-form :label-wrap="true" layout="vertical">
          <!-- 1. FOFA 空间测绘 -->
          <a-card data-setting-anchor="fofa" size="small" class="page-config-card">
            <template #title>
              <div class="card-title-with-meta">
                <RadarChartOutlined class="card-title-icon" />
                <span>{{ pageText('pages.assetDiscoveryIntelligenceFofa') }}</span>
                <a-tag color="purple" class="proxy-route-tag" @click="jumpToProxyDomain('intel')">
                  {{ pageText('pages.proxyDomainTagPrefix', { domain: 'INTEL' }) }}
                </a-tag>
                <a-tag v-if="intelChecks.fofa.status !== 'idle'" :color="intelChecks.fofa.color" style="margin: 0;">
                  {{ intelChecks.fofa.text }}
                </a-tag>
              </div>
            </template>
            <template #extra>
              <a-button size="small" :loading="intelChecks.fofa.loading" @click="verifyFofaConnection">
                <template #icon><ApiOutlined /></template>
                {{ pageText('pages.testFofaBtn') }}
              </a-button>
            </template>

            <a-row :gutter="24">
              <a-col :xs="24" :md="12">
                <a-form-item label="FOFA URL" style="margin-bottom: 12px;">
                  <a-input v-model:value="generalForm.fofa_url" :placeholder="pageText('pages.eGHttpsFofaInfo')" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="12">
                <a-form-item label="FOFA KEY" style="margin-bottom: 12px;">
                  <a-input-password v-model:value="generalForm.fofa_key" :placeholder="pageText('pages.enterYourFofaApiKey')" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="12">
                <a-form-item :label="pageText('pages.maximumQueryPages')" class="page-flush-bottom">
                  <a-input-number v-model:value="generalForm.fofa_max_page" :min="1" style="width: 100%" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="12">
                <a-form-item :label="pageText('pages.resultsPerPage')" class="page-flush-bottom">
                  <a-input-number v-model:value="generalForm.fofa_page_size" :min="1" style="width: 100%" />
                </a-form-item>
              </a-col>
            </a-row>
          </a-card>

          <!-- 2. 天眼查 & GitHub Token -->
          <a-row :gutter="16">
            <a-col :xs="24" :lg="12">
              <a-card data-setting-anchor="tyc" size="small" class="page-config-card">
                <template #title>
                  <div class="card-title-with-meta">
                    <BankOutlined class="card-title-icon" />
                    <span>{{ pageText('pages.enterpriseDiscoveryCredentialsTianyanchaApi') }}</span>
                    <a-tag color="orange" class="proxy-route-tag" @click="jumpToProxyDomain('osint')">
                      {{ pageText('pages.proxyDomainTagPrefix', { domain: 'OSINT' }) }}
                    </a-tag>
                    <a-tag v-if="intelChecks.tyc.status !== 'idle'" :color="intelChecks.tyc.color" style="margin: 0;">
                      {{ intelChecks.tyc.text }}
                    </a-tag>
                  </div>
                </template>
                <template #extra>
                  <a-button size="small" :loading="intelChecks.tyc.loading" @click="verifyTycCredentials">
                    <template #icon><SafetyCertificateOutlined /></template>
                    {{ pageText('pages.testTycBtn') }}
                  </a-button>
                </template>

                <a-form-item :label="pageText('pages.tianyanchaIdXTycid')" class="page-field-spacing">
                  <a-input v-model:value="generalForm.tyc_id" :placeholder="pageText('pages.enterYourTianyanchaId')" />
                </a-form-item>
                <a-form-item :label="pageText('pages.tianyanchaTokenXAuthToken')" style="margin-bottom: 6px;">
                  <a-input-password v-model:value="generalForm.tyc_token" :placeholder="pageText('pages.enterAJwtToken')" />
                </a-form-item>
                <div class="arl-field-hint">{{ pageText('pages.tycFallbackTip') }}</div>
              </a-card>
            </a-col>

            <a-col :xs="24" :lg="12">
              <a-card data-setting-anchor="github_token" size="small" class="page-config-card">
                <template #title>
                  <div class="card-title-with-meta">
                    <GithubOutlined class="card-title-icon" />
                    <span>GitHub Token</span>
                    <a-tag color="purple" class="proxy-route-tag" @click="jumpToProxyDomain('intel')">
                      {{ pageText('pages.proxyDomainTagPrefix', { domain: 'INTEL' }) }}
                    </a-tag>
                    <a-tag v-if="intelChecks.github.status !== 'idle'" :color="intelChecks.github.color" style="margin: 0;">
                      {{ intelChecks.github.text }}
                    </a-tag>
                  </div>
                </template>
                <template #extra>
                  <a-button size="small" :loading="intelChecks.github.loading" @click="verifyGithubToken">
                    <template #icon><KeyOutlined /></template>
                    {{ pageText('pages.testGithubBtn') }}
                  </a-button>
                </template>

                <a-form-item :label="pageText('pages.githubTokenMonitoringTasks')" style="margin-bottom: 6px;">
                  <a-input-password v-model:value="generalForm.github_token" :placeholder="pageText('pages.enterYourGithubPat')" />
                </a-form-item>
                <div class="arl-field-hint">{{ pageText('pages.requiredForCodeLeakMonitoringAndCveTracking') }}</div>
              </a-card>
            </a-col>
          </a-row>

          <!-- 3. 搜索引擎反爬 Cookie（统一卡片，消除孤岛） -->
          <a-card data-setting-anchor="search_cookie" size="small" class="page-config-card">
            <template #title>
              <div class="card-title-with-meta">
                <SearchOutlined class="card-title-icon" />
                <span>{{ pageText('pages.searchEnginesAndOpenSourceIntelligence') }}</span>
              </div>
            </template>
            <a-row :gutter="24">
              <a-col :xs="24" :md="12">
                <a-form-item :label="pageText('pages.360SearchCookieAntiBotAccess')" class="page-flush-bottom">
                  <a-input-password v-model:value="generalForm.so_search_cookie" :placeholder="pageText('pages.enterA360SearchCookie')" />
                </a-form-item>
              </a-col>
              <a-col :xs="24" :md="12">
                <a-form-item :label="pageText('pages.bingSearchCookieBingSearchCookie')" class="page-flush-bottom">
                  <a-input-password v-model:value="generalForm.bing_search_cookie" :placeholder="pageText('pages.enterABingSearchCookie')" />
                </a-form-item>
              </a-col>
            </a-row>
          </a-card>

          <!-- 4. 域名收集扩展插件 (QUERY_PLUGIN) -->
          <a-card data-setting-anchor="query_plugin" size="small" class="page-rounded">
            <template #title>
              <div class="card-title-with-meta">
                <AppstoreOutlined class="card-title-icon" />
                <span>{{ pageText('pages.domainCollectionPluginConfigurationQueryPlugin') }}</span>
              </div>
            </template>
            <template #extra>
              <a-radio-group v-model:value="pluginFilterMode" size="small" button-style="solid">
                <a-radio-button value="all">{{ pageText('pages.pluginFilterAll', { count: pluginTotalCount }) }}</a-radio-button>
                <a-radio-button value="enabled">{{ pageText('pages.pluginFilterEnabled', { count: pluginEnabledCount }) }}</a-radio-button>
                <a-radio-button value="key_required">{{ pageText('pages.pluginFilterWithKey', { count: pluginWithKeyCount }) }}</a-radio-button>
              </a-radio-group>
            </template>

            <ArlEmpty v-if="filteredQueryPlugins.length === 0" :description="pageText('pages.pluginFilterEmpty')" />
            <div v-else class="plugin-grid-container">
              <a-row :gutter="[12, 12]">
                <a-col :xs="24" :sm="12" :lg="8" v-for="[pluginName, conf] in filteredQueryPlugins" :key="pluginName">
                  <div class="plugin-tile-card">
                    <div class="plugin-tile-header">
                      <span class="plugin-tile-name">{{ pluginName }}</span>
                      <a-switch v-model:checked="conf.enable" size="small" />
                    </div>

                    <a-input-password
                      v-if="hasOwn(conf, 'api_key')"
                      v-model:value="conf.api_key"
                      placeholder="API Key"
                      size="small"
                    />
                    <div v-if="pluginName === 'hunter_qax'" class="plugin-tile-pair">
                      <a-input-number v-model:value="conf.max_page" :placeholder="pageText('pages.maxPagesPlaceholder')" size="small" class="page-flex-input" />
                      <a-input-number v-model:value="conf.page_size" :placeholder="pageText('pages.pageSizePlaceholder')" size="small" class="page-flex-input" />
                    </div>
                    <div v-if="pluginName === 'certspotter'" style="margin-top: 8px;">
                      <a-input-number v-model:value="conf.max_page" :placeholder="pageText('pages.maxPagesPlaceholder')" size="small" class="page-full-width-input" />
                    </div>
                    <a-input-password
                      v-if="hasOwn(conf, 'quake_token')"
                      v-model:value="conf.quake_token"
                      placeholder="Quake Token"
                      size="small"
                      style="margin-top: 8px;"
                    />
                    <div v-if="pluginName === 'passivetotal'" class="plugin-tile-stack">
                      <a-input v-model:value="conf.auth_email" :placeholder="pageText('pages.authEmailPlaceholder')" size="small" />
                      <a-input-password v-model:value="conf.auth_key" :placeholder="pageText('pages.authKeyPlaceholder')" size="small" />
                    </div>
                    <div v-if="!pluginRequiresCredential(conf, pluginName)" class="plugin-free-badge">
                      {{ pageText('pages.pluginNoCredentialNeeded') }}
                    </div>
                  </div>
                </a-col>
              </a-row>
            </div>
          </a-card>
        </a-form>
      </a-spin>
    </div>

    <!-- ================================================================ -->
    <!-- 主域 2：代理与红线 -->
    <!-- ================================================================ -->
    <div v-if="visitedDomains.egress_guardrails" v-show="activeKey === 'egress_guardrails'">
      <div v-if="visitedSubTabs.proxy" v-show="guardrailSubTab === 'proxy'">
        <ProxyManagePanel ref="proxyPanelRef" />
      </div>

      <div v-show="guardrailSubTab === 'security'" class="settings-section-container">
        <a-spin :spinning="securityLoading">
          <a-card data-setting-anchor="security" size="small" class="page-config-card">
            <template #title>
              <div class="card-title-with-meta">
                <SafetyOutlined class="card-title-icon" />
                <span>{{ pageText('pages.securityPolicyIpDomainScanExclusions') }}</span>
              </div>
            </template>

            <div class="guardrail-preset-bar">
              <span class="guardrail-preset-label">{{ pageText('pages.guardrailPresetLabel') }}</span>
              <div class="guardrail-preset-actions">
                <a-button size="small" @click="applyGuardrailIpPreset('add')">
                  {{ pageText('pages.guardrailPresetAddPrivate') }}
                </a-button>
                <a-button size="small" @click="applyGuardrailIpPreset('remove')">
                  {{ pageText('pages.guardrailPresetRemovePrivate') }}
                </a-button>
                <a-button size="small" @click="applyGuardrailDomainPreset">
                  {{ pageText('pages.guardrailPresetAddGovEdu') }}
                </a-button>
              </div>
            </div>

            <a-form :label-wrap="true" layout="vertical">
              <a-row :gutter="16">
                <a-col :xs="24" :lg="12">
                  <div class="guardrail-editor-box">
                    <div class="guardrail-editor-header">
                      <span class="guardrail-editor-title">{{ pageText('pages.ipBlocklistSupportsCidrEG12700') }}</span>
                      <a-tag color="blue" style="margin: 0;">
                        {{ pageText('pages.guardrailValidCount', { count: securityAnalysis.ipCount }) }}
                      </a-tag>
                    </div>
                    <a-textarea
                      v-model:value="securityForm.blackIpsText"
                      :rows="10"
                      class="guardrail-mono-textarea"
                      :placeholder="pageText('pages.eG1270008100')"
                    />
                    <a-alert
                      v-if="securityAnalysis.invalidIps.length > 0"
                      type="error"
                      show-icon
                      style="margin-top: 8px;"
                      :message="pageText('pages.guardrailInvalidLines', {
                        count: securityAnalysis.invalidIps.length,
                        line: securityAnalysis.invalidIps[0].line,
                        sample: securityAnalysis.invalidIps[0].raw
                      })"
                    />
                  </div>
                </a-col>

                <a-col :xs="24" :lg="12">
                  <div class="guardrail-editor-box">
                    <div class="guardrail-editor-header">
                      <span class="guardrail-editor-title">{{ pageText('pages.excludedDomainsSuffixMatchingEGGovCnOr') }}</span>
                      <a-tag color="blue" style="margin: 0;">
                        {{ pageText('pages.guardrailValidCount', { count: securityAnalysis.domainCount }) }}
                      </a-tag>
                    </div>
                    <a-textarea
                      v-model:value="securityForm.forbiddenDomainsText"
                      :rows="10"
                      class="guardrail-mono-textarea"
                      :placeholder="pageText('pages.eGGovCnEduCn')"
                    />
                    <a-alert
                      v-if="securityAnalysis.invalidDomains.length > 0"
                      type="warning"
                      show-icon
                      style="margin-top: 8px;"
                      :message="pageText('pages.guardrailInvalidLines', {
                        count: securityAnalysis.invalidDomains.length,
                        line: securityAnalysis.invalidDomains[0].line,
                        sample: securityAnalysis.invalidDomains[0].raw
                      })"
                    />
                  </div>
                </a-col>
              </a-row>
            </a-form>

            <!-- 目标命中预检 (Dry-Run) -->
            <div class="guardrail-dryrun-box">
              <div class="guardrail-dryrun-title">
                <AimOutlined />
                <span>{{ pageText('pages.guardrailDryRunTitle') }}</span>
              </div>
              <div class="guardrail-dryrun-row">
                <a-input
                  v-model:value="guardrailDryRunInput"
                  :placeholder="pageText('pages.guardrailDryRunPlaceholder')"
                  allow-clear
                  style="max-width: 460px;"
                />
                <a-tag
                  v-if="guardrailDryRunResult.status !== 'empty'"
                  :color="guardrailDryRunTagColor"
                  style="margin: 0;"
                >
                  {{ guardrailDryRunText }}
                </a-tag>
              </div>
            </div>
          </a-card>
        </a-spin>
      </div>
    </div>

    <!-- ================================================================ -->
    <!-- 主域 3：扫描与武器库 -->
    <!-- ================================================================ -->
    <div v-show="activeKey === 'scanning_arsenal'">
      <!-- 3.1 并发与默认参数 -->
      <div v-show="arsenalSubTab === 'concurrency'" class="settings-section-container">
        <a-spin :spinning="performanceLoading || generalLoading">
          <a-form :label-wrap="true" layout="vertical">
            <!-- 区域 A：进程级队列并发 -->
            <div class="section-group-header">
              <ThunderboltOutlined />
              <span>{{ pageText('pages.concurrencySectionQueueTitle') }}</span>
            </div>

            <a-alert type="info" show-icon style="margin-bottom: 14px; border-radius: 6px;">
              <template #message>
                <div style="font-size: 13px; line-height: 1.75;">
                  <div>{{ pageText('pages.queueMemoryHelp', { heavy: (capacityInfo.queue_memory_caps_mb || {}).heavy || 488, light: (capacityInfo.queue_memory_caps_mb || {}).light || 292 }) }}</div>
                  <div><strong class="page-warning-emphasis">{{ pageText('pages.smallMemoryQueueHelp') }}</strong></div>
                </div>
              </template>
            </a-alert>

            <a-alert
              v-if="pendingConvergence"
              type="warning"
              show-icon
              class="performance-pending-alert"
              :message="pendingConvergenceText"
            />

            <a-row :gutter="16">
              <a-col :xs="24" :lg="12">
                <a-card data-setting-anchor="performance" :title="pageText('pages.heavyTaskScheduling')" size="small" class="page-config-card-danger">
                  <a-form-item class="page-flush-bottom">
                    <template #label>
                      <span>{{ pageText('pages.heavyTaskConcurrency') }}</span>
                      <a-tag v-if="runtimePerformance.runtime_heavy_concurrency !== null" color="blue" style="margin-left: 8px; font-size: 12px;">
                        {{ pageText('pages.runningProcessesCount', { count: runtimePerformance.runtime_heavy_concurrency }) }}
                      </a-tag>
                      <a-tag v-else color="default" class="page-choice-gap">{{ pageText('pages.workerOffline') }}</a-tag>
                      <a-popover placement="right">
                        <template #content>
                          <div style="max-width: 320px;">
                            <div class="page-strong-heading">{{ pageText('pages.assignmentLongRunningTasks') }}</div>
                            <ul style="padding-left: 18px; margin: 0; line-height: 1.8;">
                              <li>{{ pageText('pages.regularDomainIpScans') }}</li>
                              <li>{{ pageText('pages.riskScansBulkVulnerabilityChecks') }}</li>
                              <li>{{ pageText('pages.scheduledDomainIpMonitoring') }}</li>
                            </ul>
                          </div>
                        </template>
                        <InfoCircleOutlined style="margin-left: 4px; color: var(--arl-text-secondary); cursor: pointer;" />
                      </a-popover>
                    </template>
                    <a-input-number v-model:value="performanceForm.celery_heavy_concurrency" :min="1" :max="128" style="width: 100%" />
                    <div class="arl-field-hint">{{ pageText('pages.controlConcurrencyForRegularScansRiskScansAndOther') }}</div>
                    <div v-if="capacityInfo.heavy_recommended" class="arl-recommend-row">
                      <span>
                        <span class="arl-recommend-label">{{ pageText('pages.recommended') }}</span>
                        <strong>{{ capacityInfo.heavy_recommended }}</strong>
                        <span class="arl-recommend-basis">
                          {{ pageText('pages.queueMemoryBudget', { available: capacityInfo.available_memory_mb, budget: capacityInfo.headroom_mb }) }}
                        </span>
                      </span>
                      <a-button size="small" type="link" @click="applyRecommended(performanceForm, 'heavy')">{{ pageText('pages.apply') }}</a-button>
                    </div>
                    <div v-if="capacityInfo.basis" class="arl-recommend-basis" style="margin-top: 4px;">{{ capacityInfo.basis }}</div>
                    <a-alert
                      v-if="capacityInfo.steady_ok === false"
                      type="error"
                      show-icon
                      style="margin-top: 8px; border-radius: 6px;"
                    >
                      <template #message>
                        <span style="font-size: 12px;">
                          {{ pageText('pages.insufficientQueueMemory', { peak: capacityInfo.peak_used_mb, budget: capacityInfo.headroom_mb }) }}
                        </span>
                      </template>
                    </a-alert>
                  </a-form-item>
                </a-card>
              </a-col>

              <a-col :xs="24" :lg="12">
                <a-card :title="pageText('pages.lightTaskScheduling')" size="small" class="page-config-card-success">
                  <a-form-item class="page-flush-bottom">
                    <template #label>
                      <span>{{ pageText('pages.lightTaskConcurrency') }}</span>
                      <a-tag v-if="runtimePerformance.runtime_light_concurrency !== null" color="green" style="margin-left: 8px; font-size: 12px;">
                        {{ pageText('pages.runningProcessesCount', { count: runtimePerformance.runtime_light_concurrency }) }}
                      </a-tag>
                      <a-tag v-else color="default" class="page-choice-gap">{{ pageText('pages.workerOffline') }}</a-tag>
                      <a-popover placement="right">
                        <template #content>
                          <div style="max-width: 320px;">
                            <div class="page-strong-heading">{{ pageText('pages.assignmentSingleTargetApiTasks') }}</div>
                            <ul style="padding-left: 18px; margin: 0; line-height: 1.8;">
                              <li>{{ pageText('pages.assetSearchQueriesFofaEtc') }}</li>
                              <li>{{ pageText('pages.updateAWebsiteScreenshotFingerprints') }}</li>
                              <li>{{ pageText('pages.singleTargetWebInfoHunterWihExtraction') }}</li>
                              <li>{{ pageText('pages.manuallyAddAWebsite') }}</li>
                              <li>{{ pageText('pages.forceTaskDataSynchronization') }}</li>
                            </ul>
                          </div>
                        </template>
                        <InfoCircleOutlined style="margin-left: 4px; color: var(--arl-text-secondary); cursor: pointer;" />
                      </a-popover>
                    </template>
                    <a-input-number v-model:value="performanceForm.celery_light_concurrency" :min="1" :max="256" style="width: 100%" />
                    <div class="arl-field-hint">{{ pageText('pages.usesADedicatedQueueAndDoesNotWaitFor') }}</div>
                    <div v-if="capacityInfo.light_recommended" class="arl-recommend-row">
                      <span>
                        <span class="arl-recommend-label">{{ pageText('pages.recommended') }}</span>
                        <strong>{{ capacityInfo.light_recommended }}</strong>
                        <span class="arl-recommend-basis">{{ pageText('pages.allocatedUsingThePeakMemoryModelLightTasksHave') }}</span>
                      </span>
                      <a-button size="small" type="link" @click="applyRecommended(performanceForm, 'light')">{{ pageText('pages.apply') }}</a-button>
                    </div>
                  </a-form-item>
                </a-card>
              </a-col>

              <a-col :xs="24" :lg="12">
                <a-card :title="pageText('pages.externalIntelligenceTaskScheduling')" size="small" class="page-config-card-info">
                  <a-form-item class="page-flush-bottom">
                    <template #label>
                      <span>{{ pageText('pages.osintTaskConcurrency') }}</span>
                      <a-popover placement="right">
                        <template #content>
                          <div style="max-width: 320px;">
                            <div class="page-strong-heading">{{ pageText('pages.assignmentExternalIntelligenceTasks') }}</div>
                            <ul style="padding-left: 18px; margin: 0; line-height: 1.8;">
                              <li>{{ pageText('pages.icpRecordsWebsitesAppsMiniPrograms') }}</li>
                              <li>{{ pageText('pages.tianyanchaInvestmentRelationshipsAndAssetCollection') }}</li>
                            </ul>
                          </div>
                        </template>
                        <InfoCircleOutlined style="margin-left: 4px; color: var(--arl-text-secondary); cursor: pointer;" />
                      </a-popover>
                    </template>
                    <a-input-number v-model:value="performanceForm.osint_concurrency" :min="1" :max="128" style="width: 100%" />
                    <div class="arl-field-hint">{{ pageText('pages.controlConcurrentOsintRequestsToExternalServicesSuchAs') }}</div>
                    <div v-if="capacityInfo.osint_recommended" class="arl-recommend-row">
                      <span>
                        <span class="arl-recommend-label">{{ pageText('pages.recommended') }}</span>
                        <strong>{{ capacityInfo.osint_recommended }}</strong>
                        <span class="arl-recommend-basis">{{ pageText('pages.keepTheDefaultToReduceExternalAntiBotRestrictions') }}</span>
                      </span>
                      <a-button size="small" type="link" @click="applyRecommended(performanceForm, 'osint')">{{ pageText('pages.apply') }}</a-button>
                    </div>
                  </a-form-item>
                </a-card>
              </a-col>

              <a-col :xs="24" :lg="12">
                <a-card :title="pageText('pages.githubMonitoringScheduling')" size="small" class="page-config-card-purple">
                  <a-form-item class="page-flush-bottom">
                    <template #label>
                      <span>{{ pageText('pages.githubMonitoringConcurrency') }}</span>
                      <a-tag v-if="runtimePerformance.runtime_github_concurrency !== null" color="purple" style="margin-left: 8px; font-size: 12px;">
                        {{ pageText('pages.runningProcessesCount', { count: runtimePerformance.runtime_github_concurrency }) }}
                      </a-tag>
                      <a-tag v-else color="default" class="page-choice-gap">{{ pageText('pages.workerOffline') }}</a-tag>
                      <a-popover placement="right">
                        <template #content>
                          <div style="max-width: 320px;">
                            <div class="page-strong-heading">{{ pageText('pages.assignmentGithubMonitoringTasks') }}</div>
                            <ul style="padding-left: 18px; margin: 0; line-height: 1.8;">
                              <li>{{ pageText('pages.codeLeakKeywordMonitoring') }}</li>
                              <li>{{ pageText('pages.cveSecurityToolUpdates') }}</li>
                              <li>{{ pageText('pages.researcherActivityMonitoring') }}</li>
                            </ul>
                          </div>
                        </template>
                        <InfoCircleOutlined style="margin-left: 4px; color: var(--arl-text-secondary); cursor: pointer;" />
                      </a-popover>
                    </template>
                    <a-input-number v-model:value="performanceForm.github_concurrency" :min="1" :max="64" style="width: 100%" />
                    <div class="arl-field-hint">{{ pageText('pages.usesTheDedicatedArlgithubQueueIndependentlyOfScanningTasks') }}</div>
                    <div v-if="capacityInfo.github_recommended" class="arl-recommend-row">
                      <span>
                        <span class="arl-recommend-label">{{ pageText('pages.recommended') }}</span>
                        <strong>{{ capacityInfo.github_recommended }}</strong>
                        <span class="arl-recommend-basis">{{ pageText('pages.queueProcessLimit', { limit: (capacityInfo.queue_memory_caps_mb || {}).github || 292 }) }}</span>
                      </span>
                      <a-button size="small" type="link" @click="applyRecommended(performanceForm, 'github')">{{ pageText('pages.apply') }}</a-button>
                    </div>
                  </a-form-item>
                </a-card>
              </a-col>
            </a-row>

            <!-- 区域 B：单任务内发包并发与默认端口 -->
            <div class="section-group-header" style="margin-top: 8px;">
              <ControlOutlined />
              <span>{{ pageText('pages.concurrencySectionTaskTitle') }}</span>
            </div>

            <a-card size="small" class="page-config-card">
              <a-row :gutter="24">
                <a-col :xs="24" :md="12">
                  <a-form-item data-setting-anchor="brute_concurrent" :label="pageText('pages.dnsQueryConcurrencyForRegularSubdomainDiscovery')">
                    <a-input-number v-model:value="generalForm.domain_brute_concurrent" :min="1" style="width: 100%" />
                    <div class="arl-field-hint">
                      {{ pageText('pages.dnsQueryConcurrencyWithinOneTaskTheMassdns') }} <code>-s</code> {{ pageText('pages.optionRatherThanAProcessOrThreadCountHigher') }}
                    </div>
                  </a-form-item>
                </a-col>
                <a-col :xs="24" :md="12">
                  <a-form-item :label="pageText('pages.dnsQueryConcurrencyForSubdomainMutationDiscovery')">
                    <a-input-number v-model:value="generalForm.alt_dns_concurrent" :min="1" style="width: 100%" />
                    <div class="arl-field-hint">
                      {{ pageText('pages.usedDuringAltdnsDiscoveryItsDefaultIsHigherBecause') }}
                    </div>
                  </a-form-item>
                </a-col>
              </a-row>

              <a-form-item data-setting-anchor="port_top_10" class="page-flush-bottom">
                <template #label>
                  <span>{{ pageText('pages.top10WebPortsUsedByFrontendPortScan') }}</span>
                  <a-tag color="blue" style="margin-left: 8px;">
                    {{ pageText('pages.portCountSummary', { count: portTop10Info.count }) }}
                  </a-tag>
                </template>
                <a-input v-model:value="generalForm.port_top_10" :placeholder="pageText('pages.separateValuesWithCommas')" />
                <a-alert
                  v-if="portTop10Info.invalidItems.length > 0"
                  type="warning"
                  show-icon
                  style="margin-top: 8px;"
                  :message="pageText('pages.portInvalidWarning', { items: portTop10Info.invalidItems.join(', ') })"
                />
              </a-form-item>
            </a-card>
          </a-form>
        </a-spin>
      </div>

      <!-- 3.2 字典武器库 -->
      <div v-show="arsenalSubTab === 'dict'" data-setting-anchor="dict">
        <a-spin :spinning="loading || bruteLoading">
          <div class="arl-split-workbench">
            <!-- 1. 左侧：分类导航（支持全部分类） -->
            <div class="arl-split-sidebar" style="width: 224px;">
              <div class="arl-split-sidebar-head">
                <span class="page-panel-heading">{{ pageText('pages.dictionaryCategories') }}</span>
              </div>
              <div class="dict-summary-strip">
                {{ pageText('pages.dictOverviewSummary', { assetCount: dictList.length, bruteCount: bruteDictList.length }) }}
              </div>
              <div class="arl-split-sidebar-body">
                <div
                  class="arl-split-item"
                  :class="{ 'is-active': selectedCategoryKeys.includes('__all__') }"
                  @click="handleCategorySelect({ key: '__all__' })"
                >
                  <div class="dict-cat-row">
                    <AppstoreOutlined />
                    <span class="arl-split-item-title">{{ pageText('pages.dictAllCategories') }}</span>
                  </div>
                </div>
                <div
                  v-for="group in treeData"
                  :key="group.key"
                  class="arl-split-item"
                  :class="{ 'is-active': selectedCategoryKeys.includes(group.key) }"
                  @click="handleCategorySelect({ key: group.key })"
                >
                  <div class="dict-cat-row">
                    <KeyOutlined v-if="group.key === 'group_brute_all'" />
                    <FolderOutlined v-else />
                    <span class="arl-split-item-title" style="flex: 1; min-width: 0;">{{ group.title }}</span>
                    <span class="arl-split-item-badge">{{ group.children.length }}</span>
                  </div>
                </div>
              </div>
            </div>

            <!-- 2. 中间：字典清单（在全部分类或关键字搜索下支持跨分类检索） -->
            <div class="arl-split-sidebar" style="width: 268px;">
              <div class="arl-split-sidebar-head">
                <a-input-search
                  v-model:value="menuSearch"
                  :placeholder="pageText('pages.dictSearchAllPlaceholder')"
                  size="small"
                  allow-clear
                  style="flex: 1;"
                />
                <a-tooltip :title="pageText('pages.newDictionary')">
                  <a-button type="primary" size="small" @click="openCreateDictDrawer">
                    <template #icon><PlusOutlined /></template>
                  </a-button>
                </a-tooltip>
              </div>
              <div class="arl-split-sidebar-body">
                <ArlEmpty
                  v-if="currentFilteredDicts.length === 0"
                  :description="pageText('pages.noDictionariesInThisCategory')"
                />
                <div
                  v-for="item in currentFilteredDicts"
                  :key="item.key"
                  class="arl-split-item"
                  :class="{ 'is-active': unifiedSelectedKeys.includes(item.key) }"
                  @click="handleUnifiedSelect([item.key])"
                >
                  <div class="dict-item-row">
                    <FileTextOutlined class="dict-item-icon" />
                    <div class="dict-item-meta">
                      <span class="arl-split-item-title dict-item-name">{{ item.mainTitle }}</span>
                      <div class="dict-item-bottom">
                        <span class="arl-split-item-sub">{{ item.subTitle }}</span>
                        <a-tag v-if="item.is_builtin" color="purple" class="page-tiny-tag">{{ pageText('pages.builtIn') }}</a-tag>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 3. 右侧：内容预览与维护面板 -->
            <div class="arl-split-main">
              <div v-if="!unifiedSelectedType" class="dict-empty-center">
                <ArlEmpty :description="pageText('pages.noDictionariesInThisCategory')" />
              </div>

              <template v-else>
                <div class="arl-split-toolbar">
                  <div>
                    <div class="dict-detail-head-row">
                      <h3 class="dict-detail-title">{{ unifiedSelectedName }}</h3>
                      <a-tag :color="unifiedSelectedType === 'asset' ? 'blue' : 'orange'" style="margin: 0;">
                        {{ unifiedSelectedType === 'asset' ? pageText('pages.assetDiscovery') : pageText('pages.credentialChecks') }}
                      </a-tag>
                      <a-tag v-if="unifiedSelectedIsBuiltin" color="purple" style="margin: 0;">
                        {{ pageText('pages.systemBuiltIn') }}
                      </a-tag>
                      <span class="dict-instant-badge">{{ pageText('pages.settingsInstantModeHint') }}</span>
                    </div>
                    <div class="page-dictionary-summary">
                      {{ pageText('pages.dictionaryDescriptionCount', { description: unifiedSelectedDesc, count: totalLines }) }}
                    </div>
                  </div>
                  <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
                    <a-button size="small" @click="handleDownloadDict" :loading="downloadLoading">
                      <template #icon><DownloadOutlined /></template>
                      {{ pageText('pages.exportDictionary') }}
                    </a-button>
                    <a-tooltip v-if="unifiedSelectedIsBuiltin" :title="pageText('pages.coreBuiltInDictionariesAreProtectedAndCannotBe')">
                      <a-button danger size="small" disabled>
                        <template #icon><DeleteOutlined /></template>
                        {{ pageText('pages.deleteDictionary') }}
                      </a-button>
                    </a-tooltip>
                    <a-popconfirm
                      v-else
                      :title="pageText('pages.permanentlyDeleteThisDictionaryFileThisCannotBeUndone')"
                      placement="bottomRight"
                      @confirm="handleDeleteDict"
                    >
                      <a-button danger size="small">
                        <template #icon><DeleteOutlined /></template>
                        {{ pageText('pages.deleteDictionary') }}
                      </a-button>
                    </a-popconfirm>
                    <a-button size="small" @click="searchDrawerVisible = true">
                      <template #icon><SearchOutlined /></template>
                      {{ pageText('pages.searchAndRemove') }}
                    </a-button>
                    <a-button type="primary" size="small" @click="appendDrawerVisible = true">
                      <template #icon><PlusOutlined /></template>
                      {{ pageText('pages.appendEntries') }}
                    </a-button>
                  </div>
                </div>

                <div class="arl-split-preview-area">
                  <div class="dict-preview-bar">
                    <span class="dict-preview-title">
                      {{ pageText('pages.dictionaryPreviewCount', { shown: previewLimit, total: totalLines }) }}
                    </span>
                    <div style="display: flex; gap: 8px; align-items: center;">
                      <span class="page-muted-label">{{ pageText('pages.previewLines') }}</span>
                      <a-radio-group v-model:value="previewLimit" size="small" @change="() => fetchPreview(selectedDict)">
                        <a-radio-button :value="50">50</a-radio-button>
                        <a-radio-button :value="100">100</a-radio-button>
                        <a-radio-button :value="500">500</a-radio-button>
                        <a-radio-button :value="1000">1000</a-radio-button>
                      </a-radio-group>
                      <a-button size="small" @click="copyPreviewContent">
                        <template #icon><CopyOutlined /></template>
                        {{ pageText('pages.copyPreview') }}
                      </a-button>
                    </div>
                  </div>

                  <div class="arl-code-wrapper">
                    <div class="arl-code-lines" v-if="previewContent">
                      <div v-for="n in previewLinesCount" :key="n" class="arl-code-line-num">{{ n }}</div>
                    </div>
                    <div class="arl-code-body">
                      <div v-if="!previewContent" class="arl-code-empty">
                        {{ pageText('pages.thisDictionaryIsEmpty') }}
                      </div>
                      <pre v-else class="arl-code-pre">{{ previewContent }}</pre>
                      <div v-if="totalLines > previewLimit" class="arl-code-limit-hint">
                        {{ pageText('pages.dictionaryPreviewTail', { shown: previewLimit, total: totalLines }) }}
                      </div>
                    </div>
                  </div>
                </div>
              </template>
            </div>
          </div>
        </a-spin>

        <!-- 新建字典抽屉 -->
        <a-drawer v-model:open="createDictDrawerVisible" :title="pageText('pages.newDictionary')" placement="right" width="450" @close="resetCreateDictForm">
          <a-tabs v-model:activeKey="createDictTabKey">
            <a-tab-pane key="manual" :tab="pageText('pages.createFromText')">
              <div class="page-description">{{ pageText('pages.selectADictionaryCategoryAndEnterInitialContentThe') }}</div>
              <a-form :label-wrap="true" layout="vertical">
                <a-form-item :label="pageText('pages.dictionaryCategories')" required>
                  <a-select v-model:value="createDictForm.prefix">
                    <a-select-option value="domain_">{{ pageText('pages.subdomainDiscoveryDomain') }}</a-select-option>
                    <a-select-option value="altdns_">{{ pageText('pages.subdomainMutationDiscoveryAltdns') }}</a-select-option>
                    <a-select-option value="file_">{{ pageText('pages.directoryAndFileDisclosureFile') }}</a-select-option>
                    <a-select-option value="black">{{ pageText('pages.globalBlocklistBlack') }}</a-select-option>
                    <a-select-option value="port_">{{ pageText('pages.portScanPolicyPort') }}</a-select-option>
                    <a-select-option value="dnsserver_">{{ pageText('pages.dnsResolversDnsserver') }}</a-select-option>
                    <a-select-option value="username_">{{ pageText('pages.usernamesUsername') }}</a-select-option>
                    <a-select-option value="password_">{{ pageText('pages.passwordsPassword') }}</a-select-option>
                  </a-select>
                </a-form-item>
                <a-form-item :label="pageText('pages.dictionaryNameLettersNumbersAndUnderscoresOnly')" required>
                  <a-input v-model:value="createDictForm.customName" :placeholder="pageText('pages.eGTop100')" />
                </a-form-item>
                <a-form-item :label="pageText('pages.initialDictionaryContentOptional')">
                  <a-textarea v-model:value="createDictForm.content" :placeholder="pageText('pages.oneEntryPerLineBulkPasteIsSupportedUse')" :rows="8" @paste="handlePasteContent" />
                </a-form-item>
              </a-form>
              <div style="text-align: right; margin-top: 24px;">
                <a-button @click="createDictDrawerVisible = false" class="page-inline-gap">{{ pageText('tasks.cancel') }}</a-button>
                <a-button type="primary" :loading="createDictLoading" :disabled="!isCreateDictValid" @click="handleCreateDictManual">{{ pageText('pages.createDictionary') }}</a-button>
              </div>
            </a-tab-pane>

            <a-tab-pane key="upload" :tab="pageText('pages.createFromFile')">
              <div class="page-description">{{ pageText('pages.selectADictionaryCategoryAndUploadATxtFile') }}</div>
              <a-form :label-wrap="true" layout="vertical">
                <a-form-item :label="pageText('pages.dictionaryCategories')" required>
                  <a-select v-model:value="createDictForm.prefix">
                    <a-select-option value="domain_">{{ pageText('pages.subdomainDiscoveryDomain') }}</a-select-option>
                    <a-select-option value="altdns_">{{ pageText('pages.subdomainMutationDiscoveryAltdns') }}</a-select-option>
                    <a-select-option value="file_">{{ pageText('pages.directoryAndFileDisclosureFile') }}</a-select-option>
                    <a-select-option value="black">{{ pageText('pages.globalBlocklistBlack') }}</a-select-option>
                    <a-select-option value="port_">{{ pageText('pages.portScanPolicyPort') }}</a-select-option>
                    <a-select-option value="dnsserver_">{{ pageText('pages.dnsResolversDnsserver') }}</a-select-option>
                    <a-select-option value="username_">{{ pageText('pages.usernamesUsername') }}</a-select-option>
                    <a-select-option value="password_">{{ pageText('pages.passwordsPassword') }}</a-select-option>
                  </a-select>
                </a-form-item>
                <a-form-item :label="pageText('pages.dictionaryNameLettersNumbersAndUnderscoresOnly')" required>
                  <a-input v-model:value="createDictForm.customName" :placeholder="pageText('pages.eGTop100')" />
                </a-form-item>
                <a-form-item :label="pageText('pages.dictionaryFileTxt')" required>
                  <a-upload :file-list="createDictForm.fileList" :before-upload="(f) => { createDictForm.fileList = [f]; return false; }" @remove="createDictForm.fileList = []" accept=".txt">
                    <a-button><template #icon><FolderOutlined /></template> {{ pageText('pages.selectFile') }}</a-button>
                  </a-upload>
                </a-form-item>
              </a-form>
              <div style="text-align: right; margin-top: 24px;">
                <a-button @click="handleCreateDictUploadCancel" class="page-inline-gap">{{ pageText('tasks.cancel') }}</a-button>
                <a-button type="primary" :loading="createDictLoading" :disabled="!isCreateDictValid || createDictForm.fileList.length === 0" @click="handleCreateDictUpload">{{ pageText('pages.uploadAndCreate') }}</a-button>
              </div>
            </a-tab-pane>
          </a-tabs>
        </a-drawer>

        <!-- 追加条目抽屉 -->
        <a-drawer v-model:open="appendDrawerVisible" :title="pageText('pages.appendDictionaryEntries')" placement="right" width="450">
          <a-tabs v-model:activeKey="appendMode" style="margin-bottom: 16px;">
            <a-tab-pane key="text" :tab="pageText('pages.pasteText')">
              <div class="page-compact-description">{{ pageText('pages.pasteEntriesToAppendOnePerLine') }}</div>
              <a-textarea v-model:value="newEntries" :rows="22" @paste="handlePasteNewEntries" :placeholder="pageText('pages.eGAdminRoot')" class="page-code-preview" />
              <div style="display: flex; justify-content: flex-end; gap: 12px;">
                <a-button @click="appendDrawerVisible = false">{{ pageText('tasks.cancel') }}</a-button>
                <a-button type="primary" @click="handleAppendAndClose" :loading="submitLoading" :disabled="!newEntries.trim()">{{ pageText('pages.saveEntries') }}</a-button>
              </div>
            </a-tab-pane>
            <a-tab-pane key="file" :tab="pageText('pages.uploadFile')">
              <div>
                <div style="margin-bottom: 16px; color: var(--arl-text-color); font-size: 13px;">
                  {{ pageText('pages.uploadTxtFilesWithMillionsOfLinesTheSystem') }}
                </div>
                <a-upload-dragger
                  name="file"
                  :multiple="false"
                  :customRequest="handleLargeUpload"
                  accept=".txt"
                  :showUploadList="false"
                >
                  <p class="ant-upload-drag-icon"><InboxOutlined /></p>
                  <p class="ant-upload-text">{{ pageText('pages.clickOrDragATxtFileHere') }}</p>
                  <p class="ant-upload-hint">{{ pageText('pages.plainTextOnlyOneEntryPerLine') }}</p>
                </a-upload-dragger>
              </div>
            </a-tab-pane>
          </a-tabs>
        </a-drawer>

        <!-- 搜索清理抽屉 -->
        <a-drawer v-model:open="searchDrawerVisible" :title="pageText('pages.searchAndRemoveEntries')" placement="right" width="450">
          <div style="margin-bottom: 24px;">
            <div class="page-form-section-title">{{ pageText('pages.exactSearch') }}</div>
            <a-input-search
              v-model:value="searchKeyword"
              :placeholder="pageText('pages.enterAKeywordToSearchForEntries')"
              @search="handleSearch"
              :loading="searchLoading"
            >
              <template #enterButton><a-button type="primary">{{ pageText('pages.search') }}</a-button></template>
            </a-input-search>

            <div v-if="searchResult !== null" style="margin-top: 12px;">
              <div v-if="searchResult.length > 0" class="page-success-detail">{{ pageText('pages.found') }} {{ searchResult.length }} {{ pageText('pages.matchingEntries') }}</div>
              <div v-else class="page-error-detail">{{ pageText('pages.noMatchingEntries') }}</div>
              <div v-if="searchResult.length > 0" style="max-height: 300px; overflow-y: auto;">
                <div v-for="(item, idx) in searchResult" :key="idx" style="display: flex; align-items: center; justify-content: space-between; padding: 6px 12px; border-bottom: 1px solid var(--arl-border-color); background: var(--arl-bg-light); margin-bottom: 4px; border-radius: 4px;">
                  <span style="font-family: monospace; font-size: 12px; word-break: break-all; color: var(--arl-text-color);">{{ item }}</span>
                  <a-button type="text" danger size="small" @click="handleDeleteSingle(item)" :loading="deleteLoading">{{ pageText('tasks.delete') }}</a-button>
                </div>
              </div>
              <div v-if="searchResult.length === 100" class="page-warning-detail">{{ pageText('pages.onlyTheFirst100ResultsAreShownRefineYour') }}</div>
            </div>
          </div>

          <a-divider />

          <div>
            <div class="page-danger-section-title">{{ pageText('pages.deleteEntriesInBulk') }}</div>
            <div class="page-empty-detail">{{ pageText('pages.enterTheExactEntriesToDeleteOnePerLine') }}</div>
            <a-textarea v-model:value="batchDeleteEntries" :rows="10" :placeholder="pageText('pages.eGAdmin123123456')" class="page-code-summary" />
            <a-button danger block @click="handleDeleteBatchCustom" :loading="deleteLoading" :disabled="!batchDeleteEntries.trim()">{{ pageText('pages.deleteSubmittedEntries') }}</a-button>
          </div>
        </a-drawer>
      </div>

      <!-- 3.3 CDN 识别规则 -->
      <div v-if="visitedSubTabs.cdn" v-show="arsenalSubTab === 'cdn'" data-setting-anchor="cdn">
        <CdnRulePanel ref="cdnPanelRef" />
      </div>
    </div>

    <!-- ================================================================ -->
    <!-- 主域 4：告警与回调 -->
    <!-- ================================================================ -->
    <div v-show="activeKey === 'notifications'" class="settings-section-container">
      <a-spin :spinning="generalLoading">
        <a-form :label-wrap="true" layout="vertical">
          <a-alert
            type="info"
            show-icon
            style="margin-bottom: 14px; border-radius: 6px;"
            :message="pageText('pages.testPushDraftHint')"
          />

          <a-card data-setting-anchor="push_options" size="small" class="page-config-card-theme">
            <template #title>
              <div class="card-title-with-meta">
                <BellOutlined class="card-title-icon" />
                <span>{{ pageText('pages.subscribedEvents') }}</span>
              </div>
            </template>
            <a-checkbox-group v-model:value="generalForm.push_options" style="width: 100%;">
              <a-row :gutter="[12, 8]">
                <a-col :xs="24" :sm="12" :md="8" :xl="6" class="page-form-spacing"><a-checkbox value="task_complete">{{ pageText('pages.assetDiscoveryTaskCompleted') }}</a-checkbox></a-col>
                <a-col :xs="24" :sm="12" :md="8" :xl="6" class="page-form-spacing"><a-checkbox value="nuclei_vuln">{{ pageText('pages.nucleiVulnerabilityAlert') }}</a-checkbox></a-col>
                <a-col :xs="24" :sm="12" :md="8" :xl="6" class="page-form-spacing"><a-checkbox value="github_leak">{{ pageText('pages.githubKeywordAlert') }}</a-checkbox></a-col>
                <a-col :xs="24" :sm="12" :md="8" :xl="6" class="page-form-spacing"><a-checkbox value="github_cve">{{ pageText('pages.githubCveUpdate') }}</a-checkbox></a-col>
                <a-col :xs="24" :sm="12" :md="8" :xl="6" class="page-form-spacing"><a-checkbox value="github_tools">{{ pageText('pages.githubSecurityToolUpdate') }}</a-checkbox></a-col>
                <a-col :xs="24" :sm="12" :md="8" :xl="6"><a-checkbox value="github_hackers">{{ pageText('pages.githubResearcherActivity') }}</a-checkbox></a-col>
                <a-col :xs="24" :sm="12" :md="8" :xl="6"><a-checkbox value="asset_site">{{ pageText('pages.websiteMonitoringUpdate') }}</a-checkbox></a-col>
              </a-row>
            </a-checkbox-group>
            <div v-if="(generalForm.push_options || []).includes('nuclei_vuln')" class="nuclei-push-severity-box" style="margin-top: 12px; padding-top: 12px; border-top: 1px dashed var(--border-color-split, #f0f0f0);">
              <div style="margin-bottom: 8px; font-size: 13px; color: var(--text-color-secondary, #595959);">
                {{ pageText('pages.nucleiPushSeverityFilter') }}
              </div>
              <a-checkbox-group v-model:value="generalForm.nuclei_push_severities" :options="nucleiPushSeverityOptions" />
            </div>
          </a-card>

          <!-- 6 通道自适应网格卡片（无固定高度，带已配置/未配置角标与代理域标注） -->
          <a-row :gutter="[16, 16]">
            <!-- 钉钉 -->
            <a-col :xs="24" :lg="12">
              <a-card data-setting-anchor="im" size="small" class="notify-channel-card">
                <template #title>
                  <div class="card-title-with-meta">
                    <MessageOutlined class="card-title-icon" />
                    <span>{{ pageText('pages.dingtalkBot') }}</span>
                    <a-tag :color="channelStatus.dingding ? 'success' : 'default'" style="margin: 0;">
                      {{ channelStatus.dingding ? pageText('pages.channelConfiguredTag') : pageText('pages.channelUnconfiguredTag') }}
                    </a-tag>
                    <a-tag color="cyan" style="margin: 0;">{{ pageText('pages.channelBypassDomesticTag') }}</a-tag>
                  </div>
                </template>
                <template #extra>
                  <a-button type="link" size="small" @click="handleTestPush('dingding')" :loading="testPushLoading.dingding">{{ pageText('pages.sendTest') }}</a-button>
                </template>
                <a-row :gutter="12">
                  <a-col :xs="24" :sm="12">
                    <a-form-item label="Access Token" class="page-flush-bottom">
                      <a-input-password v-model:value="generalForm.dingding.access_token" :placeholder="pageText('pages.dingtalkToken')" size="small" />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24" :sm="12">
                    <a-form-item :label="pageText('pages.signingSecret')" class="page-flush-bottom">
                      <a-input-password v-model:value="generalForm.dingding.secret" :placeholder="pageText('pages.dingtalkSecret')" size="small" />
                    </a-form-item>
                  </a-col>
                </a-row>
              </a-card>
            </a-col>

            <!-- 飞书 -->
            <a-col :xs="24" :lg="12">
              <a-card size="small" class="notify-channel-card">
                <template #title>
                  <div class="card-title-with-meta">
                    <MessageOutlined class="card-title-icon" />
                    <span>{{ pageText('pages.feishuBot') }}</span>
                    <a-tag :color="channelStatus.feishu ? 'success' : 'default'" style="margin: 0;">
                      {{ channelStatus.feishu ? pageText('pages.channelConfiguredTag') : pageText('pages.channelUnconfiguredTag') }}
                    </a-tag>
                    <a-tag color="cyan" style="margin: 0;">{{ pageText('pages.channelBypassDomesticTag') }}</a-tag>
                  </div>
                </template>
                <template #extra>
                  <a-button type="link" size="small" @click="handleTestPush('feishu')" :loading="testPushLoading.feishu">{{ pageText('pages.sendTest') }}</a-button>
                </template>
                <a-form-item label="Webhook URL" style="margin-bottom: 8px;">
                  <a-input v-model:value="generalForm.feishu.webhook_url" :placeholder="pageText('pages.feishuWebhookUrl')" size="small" />
                </a-form-item>
                <a-form-item :label="pageText('pages.signingSecret')" class="page-flush-bottom">
                  <a-input-password v-model:value="generalForm.feishu.secret" :placeholder="pageText('pages.feishuSecret')" size="small" />
                </a-form-item>
              </a-card>
            </a-col>

            <!-- 企业微信 -->
            <a-col :xs="24" :lg="12">
              <a-card size="small" class="notify-channel-card">
                <template #title>
                  <div class="card-title-with-meta">
                    <MessageOutlined class="card-title-icon" />
                    <span>{{ pageText('pages.wecomBot') }}</span>
                    <a-tag :color="channelStatus.wxwork ? 'success' : 'default'" style="margin: 0;">
                      {{ channelStatus.wxwork ? pageText('pages.channelConfiguredTag') : pageText('pages.channelUnconfiguredTag') }}
                    </a-tag>
                    <a-tag color="cyan" style="margin: 0;">{{ pageText('pages.channelBypassDomesticTag') }}</a-tag>
                  </div>
                </template>
                <template #extra>
                  <a-button type="link" size="small" @click="handleTestPush('wxwork')" :loading="testPushLoading.wxwork">{{ pageText('pages.sendTest') }}</a-button>
                </template>
                <a-form-item label="Webhook URL" class="page-flush-bottom">
                  <a-input v-model:value="generalForm.wxwork.webhook_url" :placeholder="pageText('pages.wecomWebhookUrl')" size="small" />
                </a-form-item>
              </a-card>
            </a-col>

            <!-- Telegram -->
            <a-col :xs="24" :lg="12">
              <a-card size="small" class="notify-channel-card">
                <template #title>
                  <div class="card-title-with-meta">
                    <SendOutlined class="card-title-icon" />
                    <span>{{ pageText('pages.telegramBot') }}</span>
                    <a-tag :color="channelStatus.telegram ? 'success' : 'default'" style="margin: 0;">
                      {{ channelStatus.telegram ? pageText('pages.channelConfiguredTag') : pageText('pages.channelUnconfiguredTag') }}
                    </a-tag>
                    <a-tag color="purple" class="proxy-route-tag" @click="jumpToProxyDomain('intel')">
                      {{ pageText('pages.channelProxyIntelTag') }}
                    </a-tag>
                  </div>
                </template>
                <template #extra>
                  <a-button type="link" size="small" @click="handleTestPush('telegram')" :loading="testPushLoading.telegram">{{ pageText('pages.sendTest') }}</a-button>
                </template>
                <a-row :gutter="12">
                  <a-col :xs="24" :sm="12">
                    <a-form-item label="Bot Token" class="page-flush-bottom">
                      <a-input-password v-model:value="generalForm.telegram.bot_token" placeholder="Bot Token" size="small" />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24" :sm="12">
                    <a-form-item label="Chat ID" class="page-flush-bottom">
                      <a-input v-model:value="generalForm.telegram.chat_id" :placeholder="pageText('pages.recipientChatId')" size="small" />
                    </a-form-item>
                  </a-col>
                </a-row>
              </a-card>
            </a-col>

            <!-- 全局 Webhook -->
            <a-col :xs="24" :lg="12">
              <a-card data-setting-anchor="webhook" size="small" class="notify-channel-card">
                <template #title>
                  <div class="card-title-with-meta">
                    <LinkOutlined class="card-title-icon" />
                    <span>{{ pageText('pages.globalWebhookCallback') }}</span>
                    <a-tag :color="channelStatus.webhook ? 'success' : 'default'" style="margin: 0;">
                      {{ channelStatus.webhook ? pageText('pages.channelConfiguredTag') : pageText('pages.channelUnconfiguredTag') }}
                    </a-tag>
                    <a-tag color="purple" class="proxy-route-tag" @click="jumpToProxyDomain('intel')">
                      {{ pageText('pages.channelProxyIntelTag') }}
                    </a-tag>
                  </div>
                </template>
                <template #extra>
                  <a-space size="small">
                    <a-popover placement="topRight" :title="pageText('pages.webhookSchemaTitle')">
                      <template #content>
                        <div style="max-width: 340px; font-size: 12px; line-height: 1.6;">
                          <p style="margin-bottom: 6px;">{{ pageText('pages.webhookSchemaDesc') }}</p>
                          <pre class="webhook-schema-pre">{{ WEBHOOK_SAMPLE_PAYLOAD }}</pre>
                        </div>
                      </template>
                      <a-button type="link" size="small">{{ pageText('pages.webhookSchemaBtn') }}</a-button>
                    </a-popover>
                    <a-button type="link" size="small" @click="handleTestPush('webhook')" :loading="testPushLoading.webhook">{{ pageText('pages.sendTest') }}</a-button>
                  </a-space>
                </template>
                <a-form-item :label="pageText('pages.callbackPostUrl')" class="page-field-spacing">
                  <a-input v-model:value="generalForm.webhook_url" :placeholder="pageText('pages.urlOfTheEndpointReceivingJsonData')" size="small" />
                </a-form-item>
                <a-form-item :label="pageText('pages.authenticationTokenHeader')" class="page-flush-bottom">
                  <a-input-password v-model:value="generalForm.webhook_token" :placeholder="pageText('pages.tokenForAuthentication')" size="small" />
                </a-form-item>
              </a-card>
            </a-col>

            <!-- SMTP 邮件 -->
            <a-col :xs="24" :lg="12">
              <a-card size="small" class="notify-channel-card">
                <template #title>
                  <div class="card-title-with-meta">
                    <MailOutlined class="card-title-icon" />
                    <span>{{ pageText('pages.smtpEmailNotifications') }}</span>
                    <a-tag :color="channelStatus.email ? 'success' : 'default'" style="margin: 0;">
                      {{ channelStatus.email ? pageText('pages.channelConfiguredTag') : pageText('pages.channelUnconfiguredTag') }}
                    </a-tag>
                  </div>
                </template>
                <template #extra>
                  <a-button type="link" size="small" @click="handleTestPush('email')" :loading="testPushLoading.email">{{ pageText('pages.sendTest') }}</a-button>
                </template>
                <a-row :gutter="12">
                  <a-col :xs="24" :sm="16">
                    <a-form-item data-setting-anchor="email" :label="pageText('pages.smtpHost')" class="page-form-spacing">
                      <a-input v-model:value="generalForm.email.host" placeholder="smtp.qq.com" size="small" />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24" :sm="8">
                    <a-form-item :label="pageText('tasks.port')" class="page-form-spacing">
                      <a-input-number v-model:value="generalForm.email.port" style="width: 100%;" size="small" />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24" :sm="12">
                    <a-form-item :label="pageText('pages.senderUsername')" class="page-form-spacing">
                      <a-input v-model:value="generalForm.email.username" :placeholder="pageText('pages.senderAccount')" size="small" />
                    </a-form-item>
                  </a-col>
                  <a-col :xs="24" :sm="12">
                    <a-form-item :label="pageText('pages.authorizationCodePassword')" class="page-form-spacing">
                      <a-input-password v-model:value="generalForm.email.password" :placeholder="pageText('pages.authorizationPassword')" size="small" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="24">
                    <a-form-item :label="pageText('pages.recipientsToCommaSeparated')" class="page-flush-bottom">
                      <a-input v-model:value="generalForm.email.to" placeholder="receiver@test.com" size="small" />
                    </a-form-item>
                  </a-col>
                </a-row>
              </a-card>
            </a-col>
          </a-row>
        </a-form>
      </a-spin>
    </div>

    <!-- ================================================================ -->
    <!-- 主域 5：系统运维 -->
    <!-- ================================================================ -->
    <div v-if="visitedDomains.system_ops" v-show="activeKey === 'system_ops'">
      <!-- 5.1 API 安全认证与基础设施诊断 -->
      <div v-show="opsSubTab === 'auth_infra'" class="settings-section-container">
        <a-spin :spinning="generalLoading">
          <a-alert
            type="info"
            show-icon
            style="margin-bottom: 16px; border-radius: 6px;"
            :message="pageText('pages.authDistinctionTitle')"
            :description="pageText('pages.authDistinctionBody')"
          />

          <a-form :label-wrap="true" layout="vertical">
            <a-card data-setting-anchor="auth" size="small" class="page-config-card">
              <template #title>
                <div class="card-title-with-meta">
                  <KeyOutlined class="card-title-icon" />
                  <span>{{ pageText('pages.apiAuthentication') }}</span>
                </div>
              </template>
              <template #extra>
                <a-space size="small">
                  <a-button size="small" @click="handleGenerateApiKey">{{ pageText('pages.generateApiKeyBtn') }}</a-button>
                  <a-button size="small" :disabled="!generalForm.api_key" @click="handleCopyApiHeaderExample">
                    <template #icon><CopyOutlined /></template>
                    {{ pageText('pages.copyCurlExampleBtn') }}
                  </a-button>
                </a-space>
              </template>

              <a-row :gutter="24">
                <a-col :xs="24" :md="8">
                  <a-form-item :label="pageText('pages.apiAuthentication')" class="page-flush-bottom">
                    <a-switch v-model:checked="generalForm.auth" :checked-children="pageText('pages.on')" :un-checked-children="pageText('pages.off')" />
                  </a-form-item>
                </a-col>
                <a-col :xs="24" :md="16">
                  <a-form-item label="API Token (Swagger API Key)" class="page-flush-bottom">
                    <a-input-password v-model:value="generalForm.api_key" :placeholder="pageText('pages.apiKeyOnlyRequiredWhenApiAuthenticationIsEnabled')" />
                  </a-form-item>
                </a-col>
              </a-row>
            </a-card>

            <a-card data-setting-anchor="infra" size="small" class="page-config-card">
              <template #title>
                <div class="card-title-with-meta">
                  <DatabaseOutlined class="card-title-icon" />
                  <span>{{ pageText('pages.infrastructureServiceConnectionsReadOnly') }}</span>
                </div>
              </template>
              <template #extra>
                <a-button size="small" type="text" @click="revealInfraSecrets = !revealInfraSecrets">
                  <template #icon>
                    <EyeInvisibleOutlined v-if="revealInfraSecrets" />
                    <EyeOutlined v-else />
                  </template>
                  {{ revealInfraSecrets ? pageText('pages.hideRawSecrets') : pageText('pages.showRawSecrets') }}
                </a-button>
              </template>

              <a-descriptions bordered size="small" :column="1">
                <a-descriptions-item :label="pageText('pages.celeryMessageQueueBrokerUrl')">
                  <code style="word-break: break-all;">{{ displayBrokerUri }}</code>
                </a-descriptions-item>
                <a-descriptions-item :label="pageText('pages.mongodbUri')">
                  <code style="word-break: break-all;">{{ displayMongoUri }}</code>
                </a-descriptions-item>
                <a-descriptions-item :label="pageText('pages.defaultMongodbDatabase')">
                  <code>{{ generalForm.mongo_db }}</code>
                </a-descriptions-item>
                <a-descriptions-item :label="pageText('pages.absolutePathToGeoipCityDatabase')">
                  <code style="word-break: break-all;">{{ generalForm.geoip_city }}</code>
                </a-descriptions-item>
                <a-descriptions-item :label="pageText('pages.absolutePathToGeoipAsnDatabase')">
                  <code style="word-break: break-all;">{{ generalForm.geoip_asn }}</code>
                </a-descriptions-item>
                <a-descriptions-item :label="pageText('pages.absolutePathToIp2regionDatabase')">
                  <code style="word-break: break-all;">{{ generalForm.geoip_ip2region || '-' }}</code>
                </a-descriptions-item>
              </a-descriptions>
            </a-card>
          </a-form>
        </a-spin>
      </div>

      <!-- 5.2 数据备份与恢复 -->
      <div v-if="visitedSubTabs.backup" v-show="opsSubTab === 'backup'" data-setting-anchor="backup">
        <BackupRestorePanel ref="backupPanelRef" />
      </div>

      <!-- 5.3 版本与系统更新 -->
      <div v-if="visitedSubTabs.update" v-show="opsSubTab === 'update'" data-setting-anchor="update">
        <SystemUpdatePanel ref="updatePanelRef" />
      </div>
    </div>

    <!-- 离开系统设置三选一防护弹窗 -->
    <a-modal
      v-model:open="leaveConfirmVisible"
      :title="pageText('pages.unsavedConfigurationChangesLabel2')"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      :maskClosable="false"
      @cancel="() => resolveLeaveGuard(false)"
    >
      <div class="arl-leave-modal-body">
        <ExclamationCircleOutlined class="arl-leave-modal-icon" />
        <div class="arl-leave-modal-content">
          <p style="margin-bottom: 8px;">
            {{ pageText('pages.thereAreCountUnsavedConfigurationChangesLeavingThisPage', { count: unsavedCount }) }}
          </p>
          <div class="arl-leave-section-tags">
            <a-tag v-for="sec in dirtySections" :key="sec.key" color="warning" style="margin: 0;">
              {{ sec.label }}
            </a-tag>
          </div>
        </div>
      </div>
      <template #footer>
        <a-button :disabled="batchSaving" @click="() => resolveLeaveGuard(false)">
          {{ pageText('tasks.stayOnThisPage') }}
        </a-button>
        <a-button danger :disabled="batchSaving" @click="() => resolveLeaveGuard(true)">
          {{ pageText('pages.discardChangesAndLeave') }}
        </a-button>
        <a-button type="primary" :loading="batchSaving" @click="handleLeaveSaveAndGo">
          {{ pageText('pages.saveAllAndLeave') }}
        </a-button>
      </template>
    </a-modal>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';
defineOptions({ name: 'SystemSettings' });
import {
  SettingOutlined,
  ApiOutlined,
  SafetyOutlined,
  ThunderboltOutlined,
  BellOutlined,
  ToolOutlined,
  SearchOutlined,
  ReloadOutlined,
  UndoOutlined,
  CheckOutlined,
  InfoCircleOutlined,
  ExclamationCircleOutlined,
  RadarChartOutlined,
  BankOutlined,
  GithubOutlined,
  KeyOutlined,
  SafetyCertificateOutlined,
  AppstoreOutlined,
  ControlOutlined,
  FolderOutlined,
  FileTextOutlined,
  PlusOutlined,
  DownloadOutlined,
  DeleteOutlined,
  CopyOutlined,
  InboxOutlined,
  MessageOutlined,
  SendOutlined,
  LinkOutlined,
  MailOutlined,
  DatabaseOutlined,
  EyeOutlined,
  EyeInvisibleOutlined,
  AimOutlined,
} from '@ant-design/icons-vue';
import { ref, reactive, onMounted, onUnmounted, onDeactivated, computed, nextTick, watch, createVNode } from 'vue';
import { message, Modal } from 'ant-design-vue';
import request from '@/utils/request';
import { copyText } from '@/utils/clipboard';
import {
  analyzeSecurityPolicy,
  applySecurityPreset,
  SECURITY_IP_PRESETS,
  SECURITY_DOMAIN_PRESETS,
  testTargetAgainstGuardrails,
  maskConnectionUri,
  generateStrongApiKey,
  parsePortListInfo,
} from '@/utils/settingsHelpers';
import { useRoute, onBeforeRouteLeave } from 'vue-router';
import ArlEmpty from '@/components/ArlEmpty.vue';
import CdnRulePanel from '@/components/settings/CdnRulePanel.vue';
import ProxyManagePanel from '@/components/settings/ProxyManagePanel.vue';
import BackupRestorePanel from '@/components/settings/BackupRestorePanel.vue';
import SystemUpdatePanel from '@/components/settings/SystemUpdatePanel.vue';

const { t: pageText, locale: pageLocale } = useI18n({ useScope: 'global' });

const cdnPanelRef = ref(null);
const proxyPanelRef = ref(null);
const backupPanelRef = ref(null);
const updatePanelRef = ref(null);
const searchInputRef = ref(null);
const searchBoxWrapRef = ref(null);

const route = useRoute();

// 5 个渗透实战主域与默认首屏（默认打开「情报凭据」）
const DOMAIN_TABS = [
  { key: 'intel', labelKey: 'pages.settingsDomainIntel', icon: ApiOutlined },
  { key: 'egress_guardrails', labelKey: 'pages.settingsDomainGuardrails', icon: SafetyOutlined },
  { key: 'scanning_arsenal', labelKey: 'pages.settingsDomainArsenal', icon: ThunderboltOutlined },
  { key: 'notifications', labelKey: 'pages.settingsDomainNotifications', icon: BellOutlined },
  { key: 'system_ops', labelKey: 'pages.settingsDomainOps', icon: ToolOutlined },
];

const activeKey = ref('intel');
const guardrailSubTab = ref('proxy');
const arsenalSubTab = ref('concurrency');
const opsSubTab = ref('auth_infra');

// 懒挂载追踪：避免未访问子面板在首屏抢跑请求，访问后保持 Keep-Alive
const visitedDomains = reactive({
  intel: true,
  egress_guardrails: false,
  scanning_arsenal: true,
  notifications: true,
  system_ops: false,
});
const visitedSubTabs = reactive({
  proxy: false,
  cdn: false,
  backup: false,
  update: false,
});

const markVisitedState = () => {
  if (visitedDomains[activeKey.value] !== undefined) {
    visitedDomains[activeKey.value] = true;
  }
  if (activeKey.value === 'egress_guardrails' && guardrailSubTab.value === 'proxy') {
    visitedSubTabs.proxy = true;
  } else if (activeKey.value === 'scanning_arsenal' && arsenalSubTab.value === 'cdn') {
    visitedSubTabs.cdn = true;
  } else if (activeKey.value === 'system_ops') {
    if (opsSubTab.value === 'backup') visitedSubTabs.backup = true;
    else if (opsSubTab.value === 'update') visitedSubTabs.update = true;
  }
};

watch([activeKey, guardrailSubTab, arsenalSubTab, opsSubTab], markVisitedState, { immediate: true });

const switchDomain = (key) => {
  activeKey.value = key;
};

const loading = ref(false);
const searchLoading = ref(false);
const submitLoading = ref(false);
const deleteLoading = ref(false);

const menuSearch = ref('');
const menuOpenKeys = ref([]);

const hasOwn = (obj, key) => !!obj && Object.prototype.hasOwnProperty.call(obj, key);

// ======================= 情报凭据：插件筛选与原位校验 =======================
const pluginFilterMode = ref('all');

const pluginRequiresCredential = (conf, name) => (
  hasOwn(conf, 'api_key') || hasOwn(conf, 'quake_token') || name === 'passivetotal'
);

const queryPluginEntries = computed(() => Object.entries(generalForm.value.query_plugin_config || {}));
const pluginTotalCount = computed(() => queryPluginEntries.value.length);
const pluginEnabledCount = computed(() => queryPluginEntries.value.filter(([, c]) => !!c?.enable).length);
const pluginWithKeyCount = computed(() => queryPluginEntries.value.filter(([n, c]) => pluginRequiresCredential(c, n)).length);

const filteredQueryPlugins = computed(() => {
  const entries = queryPluginEntries.value;
  if (pluginFilterMode.value === 'enabled') {
    return entries.filter(([, c]) => !!c?.enable);
  }
  if (pluginFilterMode.value === 'key_required') {
    return entries.filter(([n, c]) => pluginRequiresCredential(c, n));
  }
  return entries;
});

const intelChecks = reactive({
  fofa: { loading: false, status: 'idle', color: 'default', text: '' },
  tyc: { loading: false, status: 'idle', color: 'default', text: '' },
  github: { loading: false, status: 'idle', color: 'default', text: '' },
});

const ensureIntelSavedBeforeCheck = async () => {
  const dirtyKeys = Object.keys(pendingByGroup.value.api_config || {});
  if (dirtyKeys.length === 0) return { savedNow: false, ok: true };
  const ok = await saveGeneralConfig('api_config', '', { silentSuccess: true });
  return { savedNow: true, ok };
};

const verifyFofaConnection = async () => {
  intelChecks.fofa.loading = true;
  try {
    const { savedNow, ok } = await ensureIntelSavedBeforeCheck();
    if (!ok) return;
    const res = await request.post('/task_fofa/test', { query: 'port="80"' });
    if (res.code === 200) {
      const size = res.data?.size ?? res.data?.total ?? 0;
      intelChecks.fofa.status = 'ok';
      intelChecks.fofa.color = 'success';
      intelChecks.fofa.text = pageText('pages.fofaProbeOk', { size });
      message.success(savedNow ? pageText('pages.autoSavedAndChecked') : intelChecks.fofa.text);
    } else {
      intelChecks.fofa.status = 'error';
      intelChecks.fofa.color = 'error';
      intelChecks.fofa.text = pageText('pages.fofaProbeErr', { msg: res.message || pageText('tasks.testFailed') });
      message.error(intelChecks.fofa.text);
    }
  } catch (err) {
    const msg = err?.response?.data?.message || pageText('tasks.testRequestFailedCheckTheConfiguration');
    intelChecks.fofa.status = 'error';
    intelChecks.fofa.color = 'error';
    intelChecks.fofa.text = pageText('pages.fofaProbeErr', { msg });
    message.error(intelChecks.fofa.text);
  } finally {
    intelChecks.fofa.loading = false;
  }
};

const verifyTycCredentials = async () => {
  intelChecks.tyc.loading = true;
  try {
    const { savedNow, ok } = await ensureIntelSavedBeforeCheck();
    if (!ok) return;
    const res = await request.get('/icp/tyc_check');
    if (res.code === 200 && res.data) {
      if (!res.data.configured) {
        intelChecks.tyc.status = 'unconfigured';
        intelChecks.tyc.color = 'default';
        intelChecks.tyc.text = pageText('pages.tycStatusUnconfigured');
        message.info(savedNow ? pageText('pages.autoSavedAndChecked') : intelChecks.tyc.text);
      } else if (res.data.valid) {
        intelChecks.tyc.status = 'ok';
        intelChecks.tyc.color = 'success';
        intelChecks.tyc.text = pageText('pages.tycStatusValid');
        message.success(savedNow ? pageText('pages.autoSavedAndChecked') : intelChecks.tyc.text);
      } else {
        intelChecks.tyc.status = 'error';
        intelChecks.tyc.color = 'error';
        intelChecks.tyc.text = pageText('pages.tycStatusInvalid', { msg: res.data.message || pageText('tasks.testFailed') });
        message.warning(intelChecks.tyc.text);
      }
    }
  } catch (err) {
    const msg = err?.response?.data?.message || pageText('tasks.testRequestFailedCheckTheConfiguration');
    intelChecks.tyc.status = 'error';
    intelChecks.tyc.color = 'error';
    intelChecks.tyc.text = pageText('pages.tycStatusInvalid', { msg });
    message.error(intelChecks.tyc.text);
  } finally {
    intelChecks.tyc.loading = false;
  }
};

const verifyGithubToken = async () => {
  intelChecks.github.loading = true;
  try {
    const { savedNow, ok } = await ensureIntelSavedBeforeCheck();
    if (!ok) return;
    const res = await request.get('/github_threat/token_status');
    if (res.code === 200 && res.data) {
      const d = res.data;
      if (d.status === 'valid') {
        intelChecks.github.status = 'ok';
        intelChecks.github.color = 'success';
        intelChecks.github.text = pageText('pages.githubStatusValid', {
          core: d.core?.remaining ?? 0,
          coreLimit: d.core?.limit ?? 5000,
          search: d.search?.remaining ?? 0,
          searchLimit: d.search?.limit ?? 30,
        });
        message.success(savedNow ? pageText('pages.autoSavedAndChecked') : intelChecks.github.text);
      } else if (d.status === 'rate_limited') {
        intelChecks.github.status = 'warning';
        intelChecks.github.color = 'warning';
        intelChecks.github.text = pageText('pages.githubStatusLimited', {
          search: d.search?.remaining ?? 0,
          searchLimit: d.search?.limit ?? 30,
        });
        message.warning(intelChecks.github.text);
      } else {
        intelChecks.github.status = 'error';
        intelChecks.github.color = 'error';
        intelChecks.github.text = d.msg || pageText('tasks.testFailed');
        message.warning(intelChecks.github.text);
      }
    }
  } catch (err) {
    const msg = err?.response?.data?.message || pageText('tasks.testRequestFailedCheckTheConfiguration');
    intelChecks.github.status = 'error';
    intelChecks.github.color = 'error';
    intelChecks.github.text = msg;
    message.error(msg);
  } finally {
    intelChecks.github.loading = false;
  }
};

const jumpToProxyDomain = (domainAnchor) => {
  activeKey.value = 'egress_guardrails';
  guardrailSubTab.value = 'proxy';
  nextTick(() => {
    proxyPanelRef.value?.focusSection?.(domainAnchor);
  });
};

// ======================= 新建字典模块 =======================
const createDictDrawerVisible = ref(false);
const createDictTabKey = ref('manual');
const createDictLoading = ref(false);
const createDictForm = reactive({
  prefix: 'domain_',
  customName: '',
  content: '',
  fileList: [],
});

const openCreateDictDrawer = () => {
  createDictDrawerVisible.value = true;
  if (selectedCategoryKeys.value.length > 0) {
    const key = selectedCategoryKeys.value[0];
    if (key.includes('子域名爆破')) {
      createDictForm.prefix = 'domain_';
    } else if (key.includes('智能子域爆破')) {
      createDictForm.prefix = 'altdns_';
    } else if (key.includes('目录文件泄露')) {
      createDictForm.prefix = 'file_';
    } else if (key.includes('端口扫描策略')) {
      createDictForm.prefix = 'port_';
    } else if (key.includes('DNS 解析')) {
      createDictForm.prefix = 'dnsserver_';
    } else if (key.includes('全局黑名单拦截')) {
      createDictForm.prefix = 'black';
    } else if (key.includes('group_brute_')) {
      createDictForm.prefix = 'username_';
    }
  }
};

const isCreateDictValid = computed(() => (
  createDictForm.customName && /^[a-zA-Z0-9_]+$/.test(createDictForm.customName)
));

const isBruteCreatePrefix = computed(() => (
  createDictForm.prefix === 'username_' || createDictForm.prefix === 'password_'
));
const createDictApiBase = computed(() => (isBruteCreatePrefix.value ? '/api/brute_dict' : '/api/dictionary'));

const resetCreateDictForm = () => {
  createDictForm.prefix = 'domain_';
  createDictForm.customName = '';
  createDictForm.content = '';
  createDictForm.fileList = [];
  createDictTabKey.value = 'manual';
};

// ======================= 字典后台导入受控轮询 =======================
const activeDictPollTimers = ref(new Set());

const clearAllDictPollTimers = () => {
  for (const timer of activeDictPollTimers.value) {
    clearInterval(timer);
  }
  activeDictPollTimers.value.clear();
};

const handlePasteContent = (e) => {
  const clipboardData = e.clipboardData || window.clipboardData;
  if (!clipboardData) return;
  const pastedText = clipboardData.getData('text') || '';
  if (pastedText.length > 2 * 1024 * 1024) {
    e.preventDefault();
    message.warning(pageText('pages.pasteBlockedContentIsTooLargeSizeMbRendering', { size: (pastedText.length / 1024 / 1024).toFixed(1) }), 6);
  } else if (pastedText.length > 500 * 1024) {
    message.info(pageText('pages.largeContentDetectedSizeMbCreatingTheDictionaryWill', { size: (pastedText.length / 1024 / 1024).toFixed(1) }));
  }
};

const handlePasteNewEntries = (e) => {
  const clipboardData = e.clipboardData || window.clipboardData;
  if (!clipboardData) return;
  const pastedText = clipboardData.getData('text') || '';
  if (pastedText.length > 2 * 1024 * 1024) {
    e.preventDefault();
    message.warning(pageText('pages.pasteBlockedContentIsTooLargeSizeMbRenderingThis', { size: (pastedText.length / 1024 / 1024).toFixed(1) }), 6);
  }
};

const startDictPolling = (taskId, targetName, apiBase, isBrute, isAppend = false) => {
  const hideMsg = message.loading(pageText('pages.dictionaryNameModeImportRunningInTheBackgroundYou', { name: targetName, mode: isAppend ? pageText('pages.append') : '' }), 0);
  let pollCount = 0;
  const MAX_POLL_COUNT = 300;
  let lastUpdateTime = null;
  let staleCount = 0;
  let consecutive404Count = 0;
  const MAX_CONSECUTIVE_404 = 5;

  const timer = setInterval(async () => {
    pollCount++;
    if (pollCount > MAX_POLL_COUNT) {
      clearInterval(timer);
      activeDictPollTimers.value.delete(timer);
      hideMsg();
      message.warning(pageText('pages.dictionaryNameIsTakingLongerToImportForegroundPolling', { name: targetName }));
      return;
    }

    try {
      const statusRes = await request.get(`${apiBase}/upload_status`, { params: { task_id: taskId } });
      if (statusRes.code === 200 && statusRes.data) {
        consecutive404Count = 0;
        const data = statusRes.data;

        if (data.status === 'pending') return;

        if (data.status === 'processing') {
          if (data.update_time && data.update_time === lastUpdateTime) {
            staleCount++;
            if (staleCount >= 60) {
              clearInterval(timer);
              activeDictPollTimers.value.delete(timer);
              hideMsg();
              message.warning(pageText('pages.dictionaryNameImportHasNotReportedProgressForAn', { name: targetName }));
              return;
            }
          } else {
            lastUpdateTime = data.update_time;
            staleCount = 0;
          }
        }

        if (data.status === 'completed') {
          clearInterval(timer);
          activeDictPollTimers.value.delete(timer);
          hideMsg();
          message.success(pageText('pages.dictionaryNameModeImportCompletedAddedAddedDuplicatesSkipped', {
            name: targetName,
            mode: isAppend ? pageText('pages.append') : '',
            added: data.inserted_lines,
            duplicates: data.ignored_lines,
          }));
          if (isBrute) fetchBruteDictList(false);
          else fetchDictList(false);
          if (isAppend) fetchPreview(targetName);
        } else if (data.status === 'error') {
          clearInterval(timer);
          activeDictPollTimers.value.delete(timer);
          hideMsg();
          message.error(pageText('pages.failedToImportNameReasonLabel2', { name: targetName, reason: data.message || pageText('tasks.unknownError') }));
        }
      } else if (statusRes.code === 404) {
        consecutive404Count++;
        if (consecutive404Count >= MAX_CONSECUTIVE_404) {
          clearInterval(timer);
          activeDictPollTimers.value.delete(timer);
          hideMsg();
          message.warning(pageText('pages.importTaskStateWasLostReasonRefreshAndVerify', { reason: statusRes.message || pageText('pages.taskNotFound') }));
        }
      } else {
        clearInterval(timer);
        activeDictPollTimers.value.delete(timer);
        hideMsg();
        message.warning(pageText('pages.unexpectedImportTaskStateReasonRefreshAndVerifyThe', { reason: statusRes.message || pageText('tasks.unknownError') }));
      }
    } catch {
      // 忽略轮询网络抖动
    }
  }, 2000);

  activeDictPollTimers.value.add(timer);
};

const handleCreateDictManual = async () => {
  const targetName = `${createDictForm.prefix}${createDictForm.customName}.txt`;
  const rawContent = createDictForm.content || '';

  createDictLoading.value = true;
  try {
    const lineCount = (rawContent.match(/\n/g) || []).length;
    if (rawContent.length > 500 * 1024 || lineCount > 5000) {
      const blob = new Blob([rawContent], { type: 'text/plain' });
      const formData = new FormData();
      formData.append('file', blob, targetName);
      formData.append('name', targetName);

      const res = await request.post(`${createDictApiBase.value}/upload_large`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000,
      });
      if (res.code === 200) {
        message.info(pageText('pages.largeDictionaryAboutCountLinesUsingTheBackgroundStreaming', { count: lineCount + 1 }));
        const apiBase = createDictApiBase.value;
        const isBrute = isBruteCreatePrefix.value;
        createDictDrawerVisible.value = false;
        resetCreateDictForm();
        startDictPolling(res.task_id, targetName, apiBase, isBrute, false);
        return;
      }
      message.error(res.message || pageText('pages.failedToCreate'));
      return;
    }

    const res = await request.post(`${createDictApiBase.value}/create`, {
      name: targetName,
      content: rawContent,
    });
    if (res.code === 200) {
      message.success(pageText('pages.dictionaryNameCreated', { name: targetName }));
      const isBrute = isBruteCreatePrefix.value;
      createDictDrawerVisible.value = false;
      resetCreateDictForm();
      if (isBrute) fetchBruteDictList();
      else fetchDictList();
    } else {
      message.error(res.message || pageText('pages.failedToCreate'));
    }
  } catch {
    message.error(pageText('pages.dictionaryCreationRequestFailed'));
  } finally {
    createDictLoading.value = false;
  }
};

const handleCreateDictUploadCancel = () => {
  if (createDictLoading.value) {
    message.warning(pageText('pages.uploadInProgressPleaseWaitBeforeCanceling'));
    return;
  }
  createDictDrawerVisible.value = false;
  resetCreateDictForm();
};

const handleCreateDictUpload = async () => {
  const targetName = `${createDictForm.prefix}${createDictForm.customName}.txt`;
  const file = createDictForm.fileList[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', targetName);

  createDictLoading.value = true;
  try {
    const res = await request.post(`${createDictApiBase.value}/upload_large`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    });
    if (res.code === 200) {
      const apiBase = createDictApiBase.value;
      const isBrute = isBruteCreatePrefix.value;
      createDictDrawerVisible.value = false;
      resetCreateDictForm();
      startDictPolling(res.task_id, targetName, apiBase, isBrute, false);
    } else {
      message.error(res.message || pageText('pages.uploadFailedLabel2'));
    }
  } catch {
    message.error(pageText('pages.uploadRequestFailed'));
  } finally {
    createDictLoading.value = false;
  }
};

// ======================= 追加字典逻辑 =======================
const appendDrawerVisible = ref(false);
const appendMode = ref('text');

const handleLargeUpload = async (info) => {
  const file = info.file;
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', unifiedSelectedName.value);

  const targetName = unifiedSelectedName.value;
  const currentType = unifiedSelectedType.value;
  const uploadUrl = currentType === 'asset' ? '/api/dictionary/upload_large' : '/api/brute_dict/upload_large';
  const apiBase = currentType === 'asset' ? '/api/dictionary' : '/api/brute_dict';
  const isBrute = currentType !== 'asset';

  try {
    const res = await request.post(uploadUrl, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000,
    });

    if (res.code === 200) {
      appendDrawerVisible.value = false;
      startDictPolling(res.task_id, targetName, apiBase, isBrute, true);
    } else {
      message.error(res.message || pageText('pages.uploadFailedLabel2'));
    }
  } catch {
    message.error(pageText('pages.networkOrServerError'));
  }
};

const searchDrawerVisible = ref(false);
const batchDeleteEntries = ref('');

const generalLoading = ref(false);
const generalSaveLoading = ref(false);

const testPushLoading = reactive({
  dingding: false,
  feishu: false,
  wxwork: false,
  telegram: false,
  email: false,
  webhook: false,
});

const WEBHOOK_SAMPLE_PAYLOAD = JSON.stringify({
  type: 'domain_monitor | site_monitor | nuclei_vuln',
  task_id: '65f0...',
  task_data: { name: 'example.com', status: 'done', end_time: '2026-11-18 12:00:00' },
  scope_id: '65f1...',
  summary: { total: 2, severity_counts: { critical: 1, high: 1, medium: 0, low: 0, info: 0 } },
  nuclei_results: [{ template_id: 'CVE-2024-0001', vuln_severity: 'high', vuln_url: 'https://example.com' }],
}, null, 2);

const nucleiPushSeverityOptions = [
  { get label() { return pageText('pages.critical'); }, value: 'critical' },
  { get label() { return pageText('pages.high'); }, value: 'high' },
  { get label() { return pageText('pages.medium'); }, value: 'medium' },
  { get label() { return pageText('pages.low'); }, value: 'low' },
  { get label() { return pageText('pages.info'); }, value: 'info' },
];

const handleTestPush = async (type) => {
  let config = {};
  if (type === 'webhook') {
    config = {
      webhook_url: generalForm.value.webhook_url,
      webhook_token: generalForm.value.webhook_token,
    };
  } else {
    config = generalForm.value[type];
  }

  testPushLoading[type] = true;
  try {
    const res = await request.post('/api/system_config/test_push', {
      push_type: type,
      config,
    });

    if (res.code === 200) {
      message.success(res.message || pageText('pages.testNotificationSent'));
    } else {
      message.error(res.message || pageText('pages.failedToSendTestNotification'));
    }
  } catch (error) {
    message.error(pageText('pages.testRequestFailedCheckTheNetworkConnection'));
    console.error(error);
  } finally {
    testPushLoading[type] = false;
  }
};

// ======================= 全局配置脏状态追踪 (Hero 唯一中枢) =======================
const GENERAL_FIELD_GROUPS = {
  api_config: ['fofa_key', 'fofa_url', 'fofa_max_page', 'fofa_page_size', 'github_token',
    'tyc_id', 'tyc_token', 'so_search_cookie', 'bing_search_cookie', 'query_plugin_config'],
  message_push: ['push_options', 'nuclei_push_severities', 'dingding', 'feishu', 'wxwork', 'telegram', 'email',
    'webhook_url', 'webhook_token'],
  scan_params: ['port_top_10', 'domain_brute_concurrent', 'alt_dns_concurrent'],
  system_auth: ['auth', 'api_key'],
};

const isConfigInitialized = ref(false);
const generalBaseline = ref({});
const cloneDeep = (val) => (val === undefined ? undefined : JSON.parse(JSON.stringify(val)));
const capacityInfo = ref({});

const captureBaseline = () => {
  generalBaseline.value = cloneDeep(generalForm.value);
};

const changedFields = computed(() => {
  const base = generalBaseline.value;
  const cur = generalForm.value;
  const changed = {};
  const collect = (groupKeys) => {
    groupKeys.forEach((key) => {
      if (JSON.stringify(cur[key]) !== JSON.stringify(base[key])) {
        changed[key] = cur[key];
      }
    });
  };
  Object.values(GENERAL_FIELD_GROUPS).forEach(collect);
  return changed;
});

const pendingByGroup = computed(() => {
  const out = {};
  const changed = changedFields.value;
  Object.entries(GENERAL_FIELD_GROUPS).forEach(([group, keys]) => {
    const subset = {};
    keys.forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(changed, key)) subset[key] = changed[key];
    });
    out[group] = subset;
  });
  return out;
});

const securityBaseline = ref({ blackIpsText: '', forbiddenDomainsText: '' });
const performanceBaseline = ref({
  celery_heavy_concurrency: 1,
  celery_light_concurrency: 1,
  osint_concurrency: 1,
  github_concurrency: 1,
});

const isSecurityDirty = computed(() => (
  securityForm.value.blackIpsText !== securityBaseline.value.blackIpsText
  || securityForm.value.forbiddenDomainsText !== securityBaseline.value.forbiddenDomainsText
));

const isPerformanceDirty = computed(() => (
  performanceForm.value.celery_heavy_concurrency !== performanceBaseline.value.celery_heavy_concurrency
  || performanceForm.value.celery_light_concurrency !== performanceBaseline.value.celery_light_concurrency
  || performanceForm.value.osint_concurrency !== performanceBaseline.value.osint_concurrency
  || performanceForm.value.github_concurrency !== performanceBaseline.value.github_concurrency
));

const batchSaving = ref(false);
const leaveConfirmVisible = ref(false);
let pendingLeaveResolver = null;
let allowDirtyDeactivateOnce = false;

const isSectionRefDirty = (panelRef) => (
  typeof panelRef !== 'undefined' && !!panelRef.value?.hasUnsavedChanges?.()
);

// 统一可编辑配置分区注册表（与 5 主域壳层一一映射）
const SECTION_SPECS = [
  {
    key: 'api_config',
    tab: 'intel',
    anchor: 'fofa',
    get label() { return pageText('pages.settingsDomainIntel'); },
    isDirty: () => Object.keys(pendingByGroup.value.api_config || {}).length > 0,
    isSaving: () => generalSaveLoading.value,
    save: (opts) => saveGeneralConfig('api_config', pageText('pages.apiConfigurationSaved'), opts),
    reset: (opts) => resetGeneralGroup('api_config', opts),
  },
  {
    key: 'proxy',
    tab: 'egress_guardrails',
    subTab: 'proxy',
    anchor: 'proxy',
    get label() { return pageText('pages.settingsSubProxy'); },
    isDirty: () => isSectionRefDirty(typeof proxyPanelRef !== 'undefined' ? proxyPanelRef : undefined),
    isSaving: () => (typeof proxyPanelRef !== 'undefined' && !!proxyPanelRef.value?.isSaving?.()),
    save: (opts) => (typeof proxyPanelRef !== 'undefined' ? proxyPanelRef.value?.saveChanges?.(opts) : Promise.resolve(false)),
    reset: (opts) => (typeof proxyPanelRef !== 'undefined' ? proxyPanelRef.value?.resetChanges?.(opts) : undefined),
  },
  {
    key: 'security',
    tab: 'egress_guardrails',
    subTab: 'security',
    anchor: 'security',
    get label() { return pageText('pages.settingsSubGuardrails'); },
    isDirty: () => isSecurityDirty.value,
    isSaving: () => securitySaveLoading.value,
    save: (opts) => saveSecurityPolicy(opts),
    reset: (opts) => resetSecurityForm(opts),
  },
  {
    key: 'performance',
    tab: 'scanning_arsenal',
    subTab: 'concurrency',
    anchor: 'performance',
    get label() { return pageText('pages.taskQueueConcurrency'); },
    isDirty: () => isPerformanceDirty.value,
    isSaving: () => performanceSaveLoading.value,
    save: (opts) => savePerformanceConfig(opts),
    reset: (opts) => resetPerformanceForm(opts),
  },
  {
    key: 'scan_params',
    tab: 'scanning_arsenal',
    subTab: 'concurrency',
    anchor: 'brute_concurrent',
    get label() { return pageText('pages.settingsSubConcurrency'); },
    isDirty: () => Object.keys(pendingByGroup.value.scan_params || {}).length > 0,
    isSaving: () => generalSaveLoading.value,
    save: (opts) => saveGeneralConfig('scan_params', pageText('pages.advancedConfigurationSaved'), opts),
    reset: (opts) => resetGeneralGroup('scan_params', opts),
  },
  {
    key: 'message_push',
    tab: 'notifications',
    anchor: 'push_options',
    get label() { return pageText('pages.settingsDomainNotifications'); },
    isDirty: () => Object.keys(pendingByGroup.value.message_push || {}).length > 0,
    isSaving: () => generalSaveLoading.value,
    save: (opts) => saveGeneralConfig('message_push', pageText('pages.notificationConfigurationSaved'), opts),
    reset: (opts) => resetGeneralGroup('message_push', opts),
  },
  {
    key: 'system_auth',
    tab: 'system_ops',
    subTab: 'auth_infra',
    anchor: 'auth',
    get label() { return pageText('pages.settingsSubAuthInfra'); },
    isDirty: () => Object.keys(pendingByGroup.value.system_auth || {}).length > 0,
    isSaving: () => generalSaveLoading.value,
    save: (opts) => saveGeneralConfig('system_auth', pageText('pages.advancedConfigurationSaved'), opts),
    reset: (opts) => resetGeneralGroup('system_auth', opts),
  },
];

const dirtySections = computed(() => {
  if (typeof isConfigInitialized !== 'undefined' && !isConfigInitialized.value) return [];
  return SECTION_SPECS.filter((sec) => sec.isDirty());
});

const hasUnsavedChanges = computed(() => dirtySections.value.length > 0);
const unsavedCount = computed(() => dirtySections.value.length);

const domainDirtyCounts = computed(() => {
  const counts = {
    intel: 0,
    egress_guardrails: 0,
    scanning_arsenal: 0,
    notifications: 0,
    system_ops: 0,
  };
  dirtySections.value.forEach((sec) => {
    if (counts[sec.tab] !== undefined) counts[sec.tab] += 1;
  });
  return counts;
});

const currentSubTabForDomain = (domainKey) => {
  if (domainKey === 'egress_guardrails') return guardrailSubTab.value;
  if (domainKey === 'scanning_arsenal') return arsenalSubTab.value;
  if (domainKey === 'system_ops') return opsSubTab.value;
  return undefined;
};

const activeViewSections = computed(() => {
  const curTab = activeKey.value;
  const sub = currentSubTabForDomain(curTab);
  return SECTION_SPECS.filter((sec) => sec.tab === curTab && (!sec.subTab || sec.subTab === sub));
});

const activeSectionDirty = computed(() => {
  if (typeof isConfigInitialized !== 'undefined' && !isConfigInitialized.value) return false;
  return activeViewSections.value.some((sec) => sec.isDirty());
});

const activeSectionSaving = computed(() => activeViewSections.value.some((sec) => sec.isSaving()));

const saveActiveViewSections = async () => {
  const targets = activeViewSections.value.filter((sec) => sec.isDirty());
  if (targets.length === 0) return true;
  if (targets.length === 1) {
    return targets[0].save();
  }
  // 并发与默认参数同页包含队列进程数 (performance) 与单任务发包参数 (scan_params) 时串行提交
  let allOk = true;
  for (const sec of targets) {
    const ok = await sec.save({ silentSuccess: true });
    if (!ok) allOk = false;
  }
  if (allOk) {
    message.success(pageText('pages.performanceSettingsUpdated'));
  }
  return allOk;
};

const resetActiveViewSections = () => {
  const targets = activeViewSections.value.filter((sec) => sec.isDirty());
  targets.forEach((sec, idx) => sec.reset({ silent: idx > 0 }));
};

// ======================= 设置项索引与搜索 =======================
const SETTINGS_INDEX = [
  // 主域 1：情报凭据
  { tab: 'intel', get tabLabel() { return pageText('pages.settingsDomainIntel'); }, get label() { return pageText('pages.fofaDiscoveryCredentials'); }, anchor: 'fofa',
    get desc() { return pageText('pages.fofaUrlApiKeyAndQueryPageLimits'); }, keywords: ['fofa', '空间测绘', 'api key', '情报', '测试连接'] },
  { tab: 'intel', get tabLabel() { return pageText('pages.settingsDomainIntel'); }, get label() { return pageText('pages.tianyanchaEnterpriseDiscoveryCredentials'); }, anchor: 'tyc',
    get desc() { return pageText('pages.xTycidXAuthTokenFallsBackToMiit'); }, keywords: ['天眼查', 'tyc', '股权穿透', '企业', 'icp'] },
  { tab: 'intel', get tabLabel() { return pageText('pages.settingsDomainIntel'); }, label: 'GitHub Token', anchor: 'github_token',
    get desc() { return pageText('pages.requiredForCodeLeakMonitoringAndCveTracking'); }, keywords: ['github', 'token', 'pat', '监控', '泄露', 'cve', '额度'] },
  { tab: 'intel', get tabLabel() { return pageText('pages.settingsDomainIntel'); }, get label() { return pageText('pages.searchEngineCookies'); }, anchor: 'search_cookie',
    get desc() { return pageText('pages.cookiesUsedToAccess360SearchAndBingSearch'); }, keywords: ['cookie', '360', '必应', 'bing', '搜索', '反爬'] },
  { tab: 'intel', get tabLabel() { return pageText('pages.settingsDomainIntel'); }, get label() { return pageText('pages.domainCollectionPlugins'); }, anchor: 'query_plugin',
    get desc() { return pageText('pages.queryPluginDataSourceSwitchesAndCredentials'); }, keywords: ['插件', 'plugin', 'quake', 'hunter', 'virustotal', 'securitytrails', 'zoomeye', 'chaos', '扩展'] },
  // 主域 2：代理与红线
  { tab: 'egress_guardrails', subTab: 'proxy', get tabLabel() { return pageText('pages.settingsSubProxy'); }, get label() { return pageText('pages.systemProxy'); }, anchor: 'proxy',
    get desc() { return pageText('pages.proxyConfigDesc'); }, keywords: ['代理', 'proxy', '出口', 'socks5', 'socks5h', 'failover', '分流', 'osint', 'bypass', '旁路', 'uri'] },
  { tab: 'egress_guardrails', subTab: 'security', get tabLabel() { return pageText('pages.settingsSubGuardrails'); }, get label() { return pageText('pages.securityPolicyIpBlocklist'); }, anchor: 'security',
    get desc() { return pageText('pages.ipRangesExcludedFromScanningIncludingSystemDefaults'); }, keywords: ['黑名单', 'blacklist', 'ip', 'cidr', '禁止', '安全策略', '内网', '红线', 'rfc1918'] },
  { tab: 'egress_guardrails', subTab: 'security', get tabLabel() { return pageText('pages.settingsSubGuardrails'); }, get label() { return pageText('pages.securityPolicyExcludedDomains'); }, anchor: 'security',
    get desc() { return pageText('pages.domainSuffixesExcludedFromScanningEGGovCn'); }, keywords: ['禁止域名', '域名', '禁扫', '安全策略', 'gov.cn', 'edu.cn', '红线'] },
  // 主域 3：扫描与武器库
  { tab: 'scanning_arsenal', subTab: 'concurrency', get tabLabel() { return pageText('pages.settingsSubConcurrency'); }, get label() { return pageText('pages.taskQueueConcurrencyWorkerProcesses'); }, anchor: 'performance',
    get desc() { return pageText('pages.memoryConstrainedWorkerProcessCountsForHeavyLightAnd'); }, keywords: ['并发', '线程', '性能', '队列', 'celery', 'worker', '进程', '扩容', '缩容', 'concurrency'] },
  { tab: 'scanning_arsenal', subTab: 'concurrency', get tabLabel() { return pageText('pages.settingsSubConcurrency'); }, get label() { return pageText('pages.dnsQueryConcurrencyWithinATask'); }, anchor: 'brute_concurrent',
    get desc() { return pageText('pages.massdnsQueryConcurrencyForRegularAndMutationDiscoveryThis'); }, keywords: ['线程', '爆破', '并发', '并发度', 'dns', '域名', 'altdns', 'massdns', '发包', 'concurrency'] },
  { tab: 'scanning_arsenal', subTab: 'concurrency', get tabLabel() { return pageText('pages.settingsSubConcurrency'); }, get label() { return pageText('pages.top10PortList'); }, anchor: 'port_top_10',
    get desc() { return pageText('pages.defaultPortListUsedByFrontendTestOptions'); }, keywords: ['端口', 'port', 'top10', '扫描', '并发'] },
  { tab: 'scanning_arsenal', subTab: 'dict', get tabLabel() { return pageText('pages.settingsSubDict'); }, get label() { return pageText('pages.textDictionaries'); }, anchor: 'dict',
    get desc() { return pageText('pages.manageSubdomainPortDirectoryAndCredentialDictionaries'); }, keywords: ['字典', 'dict', '弱口令', '爆破', '子域名', '端口', '目录'] },
  { tab: 'scanning_arsenal', subTab: 'cdn', get tabLabel() { return pageText('pages.settingsSubCdn'); }, get label() { return pageText('pages.cdnFingerprintsAndRulesLabel2'); }, anchor: 'cdn',
    get desc() { return pageText('pages.cnameAndIpCidrRulesForIdentifyingCdns'); }, keywords: ['cdn', 'cname', 'cidr', '特征', '规则'] },
  // 主域 4：告警与回调
  { tab: 'notifications', get tabLabel() { return pageText('pages.settingsDomainNotifications'); }, get label() { return pageText('pages.subscribedEventTypes'); }, anchor: 'push_options',
    get desc() { return pageText('pages.chooseWhichEventsSendNotifications'); }, keywords: ['订阅', '推送', '通知', '告警', '消息类型', 'nuclei', '漏洞'] },
  { tab: 'notifications', get tabLabel() { return pageText('pages.settingsDomainNotifications'); }, get label() { return pageText('pages.dingtalkFeishuWecomTelegramBots'); }, anchor: 'im',
    get desc() { return pageText('pages.messagingNotificationChannelsAndTestDelivery'); }, keywords: ['钉钉', 'dingding', '飞书', 'feishu', '企业微信', 'wxwork', 'telegram', '机器人'] },
  { tab: 'notifications', get tabLabel() { return pageText('pages.settingsDomainNotifications'); }, get label() { return pageText('pages.globalWebhookCallbackLabel2'); }, anchor: 'webhook',
    get desc() { return pageText('pages.postJsonToAnExternalEndpointWhenATask'); }, keywords: ['webhook', '回调', 'callback', 'post', '接口'] },
  { tab: 'notifications', get tabLabel() { return pageText('pages.settingsDomainNotifications'); }, get label() { return pageText('pages.smtpEmailNotificationsLabel2'); }, anchor: 'email',
    get desc() { return pageText('pages.mailServerSenderAndRecipientConfiguration'); }, keywords: ['邮件', 'email', 'smtp', '推送'] },
  // 主域 5：系统运维
  { tab: 'system_ops', subTab: 'auth_infra', get tabLabel() { return pageText('pages.settingsSubAuthInfra'); }, get label() { return pageText('pages.apiAuthentication'); }, anchor: 'auth',
    get desc() { return pageText('pages.swaggerApiAuthenticationAndApiToken'); }, keywords: ['api', '认证', 'auth', 'token', 'swagger', '安全'] },
  { tab: 'system_ops', subTab: 'auth_infra', get tabLabel() { return pageText('pages.settingsSubAuthInfra'); }, get label() { return pageText('pages.infrastructureConnections'); }, anchor: 'infra',
    get desc() { return pageText('pages.readOnlyBrokerMongodbGeoipConnectionDetails'); }, keywords: ['mongodb', 'broker', 'celery', 'geoip', '数据库', '基础设施'] },
  { tab: 'system_ops', subTab: 'backup', get tabLabel() { return pageText('pages.settingsSubBackup'); }, get label() { return pageText('pages.backupTitle'); }, anchor: 'backup',
    get desc() { return pageText('pages.backupIndexDescription'); }, keywords: ['备份', '恢复', 'backup', 'restore', '导出', '导入', '快照', '迁移'] },
  { tab: 'system_ops', subTab: 'update', get tabLabel() { return pageText('pages.settingsSubUpdate'); }, get label() { return pageText('pages.systemVersionAndUpdates'); }, anchor: 'update',
    get desc() { return pageText('pages.versionComparisonReleaseNotesAndSystemUpdates'); }, keywords: ['版本', '更新', '升级', 'update', 'version', 'changelog'] },
];

const settingsKeyword = ref('');
const highlightedAnchor = ref('');

const settingsSearchResults = computed(() => {
  const kw = settingsKeyword.value.trim().toLowerCase();
  if (!kw) return [];
  return SETTINGS_INDEX.filter((item) => {
    const haystack = [item.label, item.desc, item.tabLabel, ...(item.keywords || [])]
      .join(' ').toLowerCase();
    return haystack.includes(kw);
  });
});

const scrollAndFlashAnchor = (selector, retries = 4) => {
  nextTick(() => {
    const el = document.querySelector(selector);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.classList.add('arl-anchor-flash');
      setTimeout(() => el.classList.remove('arl-anchor-flash'), 2200);
    } else if (retries > 0) {
      setTimeout(() => scrollAndFlashAnchor(selector, retries - 1), 80);
    }
  });
};

const applyDomainAndSubTab = (tab, subTab) => {
  activeKey.value = tab;
  if (tab === 'egress_guardrails' && subTab) guardrailSubTab.value = subTab;
  else if (tab === 'scanning_arsenal' && subTab) arsenalSubTab.value = subTab;
  else if (tab === 'system_ops' && subTab) opsSubTab.value = subTab;
  markVisitedState();
};

const jumpToSetting = (item) => {
  applyDomainAndSubTab(item.tab, item.subTab);
  settingsKeyword.value = '';
  highlightedAnchor.value = item.anchor;
  if (item.tab === 'egress_guardrails' && item.subTab === 'proxy') {
    nextTick(() => {
      proxyPanelRef.value?.focusSection?.(item.anchor);
    });
    return;
  }
  if (item.tab === 'scanning_arsenal' && item.subTab === 'cdn') {
    nextTick(() => {
      cdnPanelRef.value?.focusSection?.('cdn');
    });
    return;
  }
  scrollAndFlashAnchor(`[data-setting-anchor="${item.anchor}"]`);
};

const navigateToSection = (sec) => {
  if (!sec) return;
  applyDomainAndSubTab(sec.tab, sec.subTab);
  if (sec.key === 'proxy') {
    nextTick(() => {
      if (typeof proxyPanelRef !== 'undefined') proxyPanelRef.value?.focusSection?.(sec.anchor);
    });
  } else if (sec.anchor && typeof scrollAndFlashAnchor === 'function') {
    scrollAndFlashAnchor(`[data-setting-anchor="${sec.anchor}"]`);
  }
};

const firstDirtyTabKey = computed(() => dirtySections.value[0]?.tab || 'intel');

const goToFirstDirty = () => {
  const target = dirtySections.value[0];
  if (target) {
    navigateToSection(target);
    return;
  }
  activeKey.value = 'intel';
};

const handleBeforeUnload = (e) => {
  if (!hasUnsavedChanges.value) return;
  e.preventDefault();
  e.returnValue = '';
};

const tabTitle = (base, dirty) => (dirty ? `${base} ·` : base);

// ======================= 分组保存与全部重置 =======================
const saveGeneralGroup = async (group, loadingRef, successText, { silentSuccess = false } = {}) => {
  const payload = pendingByGroup.value[group] || {};
  if (Object.keys(payload).length === 0) return true;
  loadingRef.value = true;
  try {
    const res = await request.post('/api/system_config/general', payload);
    if (res.code === 200) {
      if (!silentSuccess) {
        message.success(successText || pageText('pages.changesSavedCount', { count: Object.keys(payload).length }));
      }
      Object.keys(payload).forEach((key) => {
        generalBaseline.value[key] = cloneDeep(payload[key]);
      });
      return true;
    }
    message.error(res.message || pageText('pages.failedToSaveLabel2'));
    return false;
  } catch (error) {
    message.error(pageText('pages.failedToSaveConfigurationLabel2'));
    console.error(error);
    return false;
  } finally {
    loadingRef.value = false;
  }
};

const resetGeneralGroup = (group, { silent = false } = {}) => {
  const keys = GENERAL_FIELD_GROUPS[group] || [];
  keys.forEach((key) => {
    generalForm.value[key] = cloneDeep(generalBaseline.value[key]);
  });
  if (!silent) {
    message.info(pageText('pages.sectionChangesReset'));
  }
};

const saveAllDirtySections = async () => {
  const targets = [...dirtySections.value];
  if (targets.length === 0) return true;
  batchSaving.value = true;
  const failed = [];
  let savedCount = 0;
  try {
    for (const sec of targets) {
      const ok = await sec.save({ silentSuccess: true });
      if (ok) savedCount += 1;
      else failed.push(sec);
    }
    if (failed.length === 0) {
      message.success(pageText('pages.savedAllSectionsCount', { count: savedCount }));
      return true;
    }
    navigateToSection(failed[0]);
    if (savedCount > 0) {
      message.warning(pageText('pages.saveAllPartialFailed'));
    }
    return false;
  } finally {
    batchSaving.value = false;
  }
};

const resetAllDirtySections = () => {
  const targets = [...dirtySections.value];
  targets.forEach((sec) => sec.reset({ silent: true }));
  message.info(pageText('pages.allChangesReset'));
};

const fetchCapacityProbe = async () => {
  try {
    const res = await request.get('/api/system_config/capacity_probe');
    if (res.code === 200 && res.data) capacityInfo.value = res.data;
  } catch (e) {
    console.error('获取容量推荐值失败', e);
  }
};

const RECOMMENDED_FIELD_MAP = {
  heavy: 'celery_heavy_concurrency',
  light: 'celery_light_concurrency',
  osint: 'osint_concurrency',
  github: 'github_concurrency',
};

const applyRecommended = (formRef, key) => {
  const rec = capacityInfo.value[`${key}_recommended`];
  if (rec) {
    const targetKey = RECOMMENDED_FIELD_MAP[key] || key;
    formRef.value[targetKey] = rec;
    message.success(pageText('pages.appliedRecommendedValueValue', { value: rec }));
  }
};

const generalForm = ref({
  celery_broker_url: '',
  mongo_url: '',
  mongo_db: '',
  geoip_city: '',
  geoip_asn: '',
  geoip_ip2region: '',

  fofa_key: '',
  fofa_url: '',
  fofa_max_page: 5,
  fofa_page_size: 2000,
  github_token: '',
  tyc_id: '',
  tyc_token: '',
  so_search_cookie: '',
  bing_search_cookie: '',

  port_top_10: '',
  domain_brute_concurrent: 300,
  alt_dns_concurrent: 1500,

  auth: false,
  api_key: '',

  webhook_url: '',
  webhook_token: '',

  dingding: { secret: '', access_token: '' },
  feishu: { webhook_url: '', secret: '' },
  wxwork: { webhook_url: '' },
  telegram: { bot_token: '', chat_id: '' },
  email: { host: '', port: 465, username: '', password: '', to: '' },
  query_plugin_config: {},
  push_options: ['task_complete', 'nuclei_vuln', 'github_leak', 'github_cve', 'github_tools', 'github_hackers', 'asset_site'],
  nuclei_push_severities: ['critical', 'high', 'medium', 'low'],
});
captureBaseline();

const channelStatus = computed(() => {
  const f = generalForm.value;
  return {
    dingding: !!(f.dingding?.access_token && f.dingding?.access_token.trim()),
    feishu: !!(f.feishu?.webhook_url && f.feishu?.webhook_url.trim()),
    wxwork: !!(f.wxwork?.webhook_url && f.wxwork?.webhook_url.trim()),
    telegram: !!(f.telegram?.bot_token?.trim() && f.telegram?.chat_id?.trim()),
    webhook: !!(f.webhook_url && f.webhook_url.trim()),
    email: !!(f.email?.host?.trim() && f.email?.username?.trim() && f.email?.to?.trim()),
  };
});

const portTop10Info = computed(() => parsePortListInfo(generalForm.value.port_top_10));

const revealInfraSecrets = ref(false);
const displayBrokerUri = computed(() => (
  revealInfraSecrets.value ? (generalForm.value.celery_broker_url || '-') : (maskConnectionUri(generalForm.value.celery_broker_url) || '-')
));
const displayMongoUri = computed(() => (
  revealInfraSecrets.value ? (generalForm.value.mongo_url || '-') : (maskConnectionUri(generalForm.value.mongo_url) || '-')
));

const handleGenerateApiKey = () => {
  generalForm.value.api_key = generateStrongApiKey(32);
  message.success(pageText('pages.apiKeyGenerated'));
};

const handleCopyApiHeaderExample = async () => {
  const key = generalForm.value.api_key || '<API_KEY>';
  const ok = await copyText(`Token: ${key}`);
  if (ok) {
    message.success(pageText('pages.curlExampleCopied'));
  } else {
    message.error(pageText('pages.copyFailedSelectAndCopyTheTextManually'));
  }
};

const fetchGeneralConfig = async () => {
  generalLoading.value = true;
  try {
    const res = await request.get('/api/system_config/general');
    if (res.code === 200) {
      generalForm.value = {
        ...generalForm.value,
        ...res.data,
        push_options: Array.isArray(res.data.push_options) ? res.data.push_options : generalForm.value.push_options,
        nuclei_push_severities: Array.isArray(res.data.nuclei_push_severities) ? res.data.nuclei_push_severities : generalForm.value.nuclei_push_severities,
        dingding: { ...generalForm.value.dingding, ...(res.data.dingding || {}) },
        feishu: { ...generalForm.value.feishu, ...(res.data.feishu || {}) },
        wxwork: { ...generalForm.value.wxwork, ...(res.data.wxwork || {}) },
        telegram: { ...generalForm.value.telegram, ...(res.data.telegram || {}) },
        email: { ...generalForm.value.email, ...(res.data.email || {}) },
      };
      captureBaseline();
    } else {
      message.error(res.message || pageText('pages.failedToLoadGeneralSystemConfiguration'));
      if (!isConfigInitialized.value) captureBaseline();
    }
  } catch (error) {
    message.error(pageText('pages.generalSystemConfigurationRequestFailed'));
    console.error(error);
    if (!isConfigInitialized.value) captureBaseline();
  } finally {
    generalLoading.value = false;
  }
};

const saveGeneralConfig = async (group = 'api_config', successText = '', opts = {}) => (
  saveGeneralGroup(group, generalSaveLoading, successText, opts)
);

// ======================= 字典管理逻辑 =======================
const dictList = ref([]);
const selectedDict = ref(null);
const bruteLoading = ref(false);
const bruteDictList = ref([]);

const ASSET_DICT_META = {
  'domain_2w.txt':       { get label() { return pageText('pages.mainSubdomainDictionary20000Entries'); }, group: '🌍 子域名爆破' },
  'altdnsdict.txt':      { get label() { return pageText('pages.subdomainMutationWords'); }, group: '🧠 智能子域爆破' },
  'dnsserver.txt':       { get label() { return pageText('pages.dnsResolverList'); }, group: '🌐 DNS 解析配置' },
  'file_top_200.txt':    { get label() { return pageText('pages.top200Paths'); }, group: '📂 目录文件泄露' },
  'file_top_2000.txt':   { get label() { return pageText('pages.top2000Paths'); }, group: '📂 目录文件泄露' },

  'port_top100.txt':     { get label() { return pageText('pages.top100CommonPorts'); }, group: '🔌 端口扫描策略' },
  'port_top1000.txt':    { get label() { return pageText('pages.top1000CommonPorts'); }, group: '🔌 端口扫描策略' },
  'port_custom.txt':     { get label() { return pageText('tasks.customPorts'); }, group: '🔌 端口扫描策略' },
  'port_all.txt':        { get label() { return pageText('tasks.allPorts165535'); }, group: '🔌 端口扫描策略' },
  'port_alive.txt':      { get label() { return pageText('pages.aliveProbePorts'); }, group: '🔌 端口扫描策略' },

  'blackdomain.txt':     { get label() { return pageText('pages.rootDomainExclusionDictionary'); }, group: '🛡️ 全局黑名单拦截' },
  'black_asset_site.txt':{ get label() { return pageText('pages.maliciousUnwantedWebsiteBlocklist'); }, group: '🛡️ 全局黑名单拦截' },
  'blackhexie.txt':      { get label() { return pageText('pages.sensitiveWordFilterDictionary'); }, group: '🛡️ 全局黑名单拦截' },
};

const assetMenuGroups = computed(() => {
  const groups = { '🌍 子域名爆破': [], '🧠 智能子域爆破': [], '📂 目录文件泄露': [], '🔌 端口扫描策略': [], '🌐 DNS 解析配置': [], '🛡️ 全局黑名单拦截': [] };

  const getGroupAndLabel = (dictName) => {
    if (ASSET_DICT_META[dictName]) {
      return { group: ASSET_DICT_META[dictName].group, label: ASSET_DICT_META[dictName].label };
    }
    if (dictName.startsWith('domain_')) return { group: '🌍 子域名爆破', label: dictName };
    if (dictName.startsWith('altdns_')) return { group: '🧠 智能子域爆破', label: dictName };
    if (dictName.startsWith('dnsserver_')) return { group: '🌐 DNS 解析配置', label: dictName };
    if (dictName.startsWith('file_')) return { group: '📂 目录文件泄露', label: dictName };
    if (dictName.startsWith('black')) return { group: '🛡️ 全局黑名单拦截', label: dictName };
    if (dictName.startsWith('port_')) return { group: '🔌 端口扫描策略', label: dictName };
    return null;
  };

  dictList.value.forEach((dict) => {
    const meta = getGroupAndLabel(dict.name);
    if (!meta) return;
    if (!groups[meta.group]) groups[meta.group] = [];
    groups[meta.group].push({ ...dict, title: meta.label });
  });
  return groups;
});

const bruteSvcGroups = computed(() => {
  const groups = {};
  const SVC_LABEL = {
    ssh: 'SSH', ftp: 'FTP', mysql: 'MySQL', redis: 'Redis', mongodb: 'MongoDB',
    postgresql: 'PostgreSQL', sqlserver: 'SQL Server', rdp: 'RDP',
    tomcat: 'Tomcat', jenkins: 'Jenkins', gitlab: 'GitLab', grafana: 'Grafana',
    harbor: 'Harbor', nexus: 'Nexus', nacos: 'Nacos', apisix: 'APISIX',
    activemq: 'ActiveMQ', openfire: 'OpenFire', manageiq: 'ManageIQ',
    shiro: 'Shiro Key', imap: 'IMAP', pop3: 'POP3', smtp: 'SMTP',
    exchange: 'Exchange', csts: 'CSTS', clickhouse: 'ClickHouse',
    'alibaba-druid': 'Alibaba Druid',
  };
  bruteDictList.value.forEach((item) => {
    if (item.name.startsWith('common_') && item.name.endsWith('.txt')) {
      if (!groups['通用弱口令']) groups['通用弱口令'] = [];
      groups['通用弱口令'].push(item);
      return;
    }
    const m = item.name.match(/^(?:username|password)_(.+)\.txt$/);
    if (!m) return;
    const svcKey = m[1];
    const svc = SVC_LABEL[svcKey] || svcKey.toUpperCase();
    if (!groups[svc]) groups[svc] = [];
    if (item.name.startsWith('username_')) groups[svc].unshift(item);
    else groups[svc].push(item);
  });
  return groups;
});

const formatDictionaryGroup = (group) => {
  const keys = {
    '🌍 子域名爆破': 'pages.dictionaryGroupDomains',
    '🧠 智能子域爆破': 'pages.dictionaryGroupMutations',
    '📂 目录文件泄露': 'pages.dictionaryGroupFiles',
    '🔌 端口扫描策略': 'pages.dictionaryGroupPorts',
    '🌐 DNS 解析配置': 'pages.dictionaryGroupDns',
    '🛡️ 全局黑名单拦截': 'pages.dictionaryGroupBlocklist',
  };
  return keys[group] ? pageText(keys[group]) : group;
};

const treeData = computed(() => {
  const data = [];
  Object.entries(assetMenuGroups.value).forEach(([group, items]) => {
    if (items.length) {
      const children = items.map((item) => {
        const friendly = item.title && item.title !== item.name ? item.title : item.name;
        return {
          mainTitle: friendly,
          subTitle: item.name,
          key: `asset__${item.name}`,
          is_builtin: item.is_builtin,
        };
      });
      data.push({ title: formatDictionaryGroup(group), key: `group_asset_${group}`, selectable: false, children });
    }
  });
  const npocChildren = [];
  Object.entries(bruteSvcGroups.value).forEach(([svc, items]) => {
    if (items.length) {
      items.forEach((item) => {
        let friendlyPrefix = '';
        if (item.name.startsWith('username_')) friendlyPrefix = pageText('pages.usernameDictionary');
        else if (item.name.startsWith('password_')) friendlyPrefix = pageText('pages.passwordDictionary');
        else if (item.name.includes('common_')) friendlyPrefix = pageText('pages.commonCredentialDictionary');

        const mainTitle = svc === '通用弱口令'
          ? (item.name.includes('common_') ? item.name : `${friendlyPrefix || item.name}`)
          : `[${svc}] ${friendlyPrefix || item.name}`;

        npocChildren.push({
          mainTitle,
          subTitle: item.name,
          key: `brute__${item.name}`,
          is_builtin: item.is_builtin,
        });
      });
    }
  });
  if (npocChildren.length > 0) {
    data.push({ title: pageText('pages.credentialDictionariesLabel2'), key: 'group_brute_all', children: npocChildren });
  }
  return data;
});

const filteredTreeData = computed(() => {
  if (!menuSearch.value.trim()) return treeData.value;
  const kw = menuSearch.value.toLowerCase();
  return treeData.value.map((group) => {
    const matchedChildren = group.children.filter((c) => (
      (c.mainTitle && c.mainTitle.toLowerCase().includes(kw))
      || (c.subTitle && c.subTitle.toLowerCase().includes(kw))
    ));
    return { ...group, children: matchedChildren };
  }).filter((group) => group.children.length > 0);
});

const selectedCategoryKeys = ref(['group_asset_🌍 子域名爆破']);

const handleCategorySelect = ({ key }) => {
  selectedCategoryKeys.value = [key];
};

const unifiedSelectedKeys = ref([]);
const unifiedSelectedType = ref('');
const unifiedSelectedName = ref('');
const unifiedSelectedDesc = computed(() => {
  const name = unifiedSelectedName.value;
  if (unifiedSelectedType.value === 'asset') {
    return ASSET_DICT_META[name]?.label || pageText('pages.assetDiscoveryDictionary');
  }
  if (unifiedSelectedType.value === 'brute') {
    return name.startsWith('username_') ? pageText('pages.usernameDictionaryCredentialChecks') : pageText('pages.passwordDictionaryCredentialChecks');
  }
  return '';
});

const unifiedSelectedIsBuiltin = computed(() => {
  if (!unifiedSelectedName.value) return false;
  if (unifiedSelectedType.value === 'asset') {
    const item = dictList.value.find((d) => d.name === unifiedSelectedName.value);
    return item ? Boolean(item.is_builtin) : false;
  }
  if (unifiedSelectedType.value === 'brute') {
    const item = bruteDictList.value.find((d) => d.name === unifiedSelectedName.value);
    return item ? Boolean(item.is_builtin) : false;
  }
  return false;
});

// 支持全部分类或关键字跨分类全局检索
const currentFilteredDicts = computed(() => {
  const kw = menuSearch.value.trim();
  const activeCat = selectedCategoryKeys.value[0];
  if (kw || activeCat === '__all__' || !activeCat) {
    return filteredTreeData.value.flatMap((g) => g.children || []);
  }
  const group = filteredTreeData.value.find((g) => g.key === activeCat);
  return group ? group.children || [] : [];
});

watch(treeData, (newVal) => {
  if (menuOpenKeys.value.length === 0 && newVal.length > 0) {
    menuOpenKeys.value = newVal.map((g) => g.key);
  }
  if (
    newVal.length > 0
    && selectedCategoryKeys.value[0] !== '__all__'
    && (!selectedCategoryKeys.value.length || !newVal.find((g) => g.key === selectedCategoryKeys.value[0]))
  ) {
    selectedCategoryKeys.value = [newVal[0].key];
  }
  // 消除空状态阻断：首次加载且未选择时自动选中首份字典直接预览
  if (!unifiedSelectedName.value && newVal.length > 0) {
    const firstItem = newVal.flatMap((g) => g.children || [])[0];
    if (firstItem) {
      handleUnifiedSelect([firstItem.key]);
    }
  }
}, { immediate: true });

const handleAppendAndClose = async () => {
  const ok = await handleAppend();
  if (ok) appendDrawerVisible.value = false;
};

const handleDeleteBatchCustom = () => {
  if (!batchDeleteEntries.value.trim()) return;
  const entryCount = batchDeleteEntries.value.split('\n').map((x) => x.trim()).filter(Boolean).length;
  Modal.confirm({
    title: pageText('pages.deleteDictionaryEntries'),
    icon: createVNode(ExclamationCircleOutlined),
    content: pageText('pages.deleteTheSubmittedEntriesCountFromTheCurrentDictionary', { count: entryCount }),
    okText: pageText('tasks.confirmDeletion'),
    okButtonProps: { danger: true },
    cancelText: pageText('assets.cancel'),
    onOk: async () => {
      const ok = await deleteEntries(batchDeleteEntries.value);
      if (ok) {
        batchDeleteEntries.value = '';
        searchDrawerVisible.value = false;
      }
      return ok;
    },
  });
};

const handleUnifiedSelect = (selectedKeys) => {
  const key = Array.isArray(selectedKeys) ? selectedKeys[0] : selectedKeys;
  unifiedSelectedKeys.value = key ? [key] : [];
  searchKeyword.value = '';
  searchResult.value = null;
  newEntries.value = '';
  previewContent.value = '';
  totalLines.value = 0;
  if (key && key.startsWith('asset__')) {
    const name = key.slice(7);
    unifiedSelectedType.value = 'asset';
    unifiedSelectedName.value = name;
    selectedDict.value = name;
    fetchPreview(name);
  } else if (key && key.startsWith('brute__')) {
    const name = key.slice(7);
    unifiedSelectedType.value = 'brute';
    unifiedSelectedName.value = name;
    selectedDict.value = name;
    fetchPreview(name);
  } else {
    unifiedSelectedType.value = '';
    unifiedSelectedName.value = '';
    selectedDict.value = null;
  }
};

const previewContent = ref('');
const totalLines = ref(0);
const previewLimit = ref(100);

const previewLinesCount = computed(() => {
  if (!previewContent.value) return 0;
  return previewContent.value.split('\n').length;
});

const downloadLoading = ref(false);
const handleDownloadDict = async () => {
  if (!selectedDict.value) return;
  downloadLoading.value = true;
  try {
    const res = await request.get(`${dictApiBase.value}/download`, {
      params: { name: selectedDict.value },
      responseType: 'blob',
    });
    const blob = new Blob([res], { type: 'text/plain;charset=utf-8' });
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = selectedDict.value;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
    message.success(pageText('pages.dictionaryNameExported', { name: selectedDict.value }));
  } catch (e) {
    let errMsg = pageText('pages.failedToExportDictionary');
    if (e.response && e.response.data instanceof Blob) {
      try {
        const text = await e.response.data.text();
        const parsed = JSON.parse(text);
        if (parsed.message) errMsg = parsed.message;
      } catch { /* ignore */ }
    }
    message.error(errMsg);
    console.error(e);
  } finally {
    downloadLoading.value = false;
  }
};

const copyPreviewContent = async () => {
  if (!previewContent.value) {
    message.warning(pageText('pages.noContentToCopy'));
    return;
  }
  const ok = await copyText(previewContent.value);
  if (ok) {
    message.success(pageText('pages.previewCopiedToClipboard'));
  } else {
    message.error(pageText('pages.copyFailedSelectAndCopyTheTextManually'));
  }
};

const searchKeyword = ref('');
const searchResult = ref(null);
const newEntries = ref('');

const dictApiBase = computed(() => (
  unifiedSelectedType.value === 'brute' ? '/api/brute_dict' : '/api/dictionary'
));

const fetchDictList = async (showLoading = true) => {
  if (showLoading) loading.value = true;
  try {
    const res = await request.get('/api/dictionary/list');
    if (res.code === 200) {
      dictList.value = res.data || [];
    } else {
      message.error(res.message || pageText('pages.failedToLoadDictionaryList'));
    }
  } catch (error) {
    message.error(pageText('pages.dictionaryListRequestFailed'));
    console.error(error);
  } finally {
    if (showLoading) loading.value = false;
  }
};

const fetchPreview = async (name) => {
  if (!name) return;
  loading.value = true;
  try {
    const res = await request.get(`${dictApiBase.value}/preview`, {
      params: { name, limit: previewLimit.value },
    });
    if (res.code === 200) {
      previewContent.value = res.data.lines.join('\n');
      totalLines.value = res.data.total;
    } else {
      message.error(res.message || pageText('pages.failedToLoadPreview'));
    }
  } catch (error) {
    message.error(pageText('pages.previewRequestFailed'));
    console.error(error);
  } finally {
    loading.value = false;
  }
};

const handleSearch = async () => {
  if (!searchKeyword.value.trim()) {
    message.warning(pageText('pages.enterASearchKeyword'));
    return;
  }
  searchLoading.value = true;
  try {
    const res = await request.get(`${dictApiBase.value}/search`, {
      params: { name: selectedDict.value, keyword: searchKeyword.value },
    });
    if (res.code === 200) {
      searchResult.value = res.data.matches;
      if (res.data.matches.length > 0) {
        message.success(pageText('pages.matchingEntriesCount', { count: res.data.matches.length }));
      } else {
        message.info(pageText('pages.noEntriesContainThisKeyword'));
      }
    } else {
      message.error(res.message || pageText('pages.searchFailed'));
    }
  } catch (error) {
    message.error(pageText('pages.searchRequestFailed'));
    console.error(error);
  } finally {
    searchLoading.value = false;
  }
};

const handleAppend = async () => {
  if (!newEntries.value.trim()) return false;

  const contentSize = new Blob([newEntries.value]).size;
  if (contentSize > 2 * 1024 * 1024) {
    message.warning(pageText('pages.appendedTextExceeds2MbSubmittingItThroughThe'));
    return false;
  }

  const lines = newEntries.value.split('\n').map((s) => s.trim()).filter(Boolean);
  if (selectedDict.value && selectedDict.value.startsWith('port_')) {
    const invalidPorts = lines.filter((p) => !/^\d+$/.test(p) || parseInt(p, 10) < 1 || parseInt(p, 10) > 65535);
    if (invalidPorts.length > 0) {
      message.error(pageText('pages.invalidPortNumberEGPortEnterIntegersFrom', { port: invalidPorts[0] }));
      return false;
    }
  } else if (selectedDict.value && selectedDict.value.includes('domain')) {
    const invalidDomains = lines.filter((d) => /[\s,;!@#%^&*()<>{}[\]]/.test(d));
    if (invalidDomains.length > 0) {
      message.error(pageText('pages.theSubdomainDictionaryContainsInvalidCharactersSuchAsSpaces'));
      return false;
    }
  }

  submitLoading.value = true;
  try {
    const res = await request.post(`${dictApiBase.value}/append`, {
      name: selectedDict.value,
      content: newEntries.value,
    });
    if (res.code === 200) {
      message.success(pageText('pages.savedSubmittedSubmittedNewEntriesAddedAdded', { submitted: res.data.total_submitted, added: res.data.added }));
      newEntries.value = '';
      fetchDictList();
      fetchBruteDictList();
      fetchPreview(selectedDict.value);
      return true;
    }
    message.error(res.message || pageText('pages.failedToSaveLabel2'));
    return false;
  } catch (error) {
    message.error(pageText('pages.saveRequestFailed'));
    console.error(error);
    return false;
  } finally {
    submitLoading.value = false;
  }
};

const handleDeleteSingle = (item) => {
  if (!item) return false;
  Modal.confirm({
    title: pageText('pages.deleteDictionaryEntry'),
    icon: createVNode(ExclamationCircleOutlined),
    content: pageText('pages.deleteEntryEntryFromTheCurrentDictionary', { entry: item }),
    okText: pageText('tasks.confirmDeletion'),
    okButtonProps: { danger: true },
    cancelText: pageText('assets.cancel'),
    onOk: async () => {
      const ok = await deleteEntries(item);
      if (ok && searchResult.value) {
        searchResult.value = searchResult.value.filter((x) => x !== item);
      }
      return ok;
    },
  });
  return true;
};

const handleDeleteDict = () => {
  if (!selectedDict.value) return;
  const targetName = selectedDict.value;
  Modal.confirm({
    title: pageText('pages.deleteDictionaryFile'),
    icon: createVNode(ExclamationCircleOutlined),
    content: pageText('pages.permanentlyDeleteDictionaryNameAndAllItsEntriesThis', { name: targetName }),
    okText: pageText('tasks.confirmDeletion'),
    okButtonProps: { danger: true },
    cancelText: pageText('assets.cancel'),
    onOk: () => executeDeleteDict(targetName),
  });
};

const executeDeleteDict = async (targetName) => {
  const wasBrute = unifiedSelectedType.value === 'brute';
  loading.value = true;
  try {
    const res = await request.post(`${dictApiBase.value}/delete_file`, { name: targetName });
    if (res.code === 200) {
      message.success(pageText('pages.dictionaryNameDeleted', { name: targetName }));
      unifiedSelectedKeys.value = [];
      unifiedSelectedName.value = '';
      unifiedSelectedType.value = '';
      selectedDict.value = '';
      previewContent.value = '';
      totalLines.value = 0;

      if (wasBrute) await fetchBruteDictList();
      else await fetchDictList();
    } else {
      message.error(res.message || pageText('tasks.deletionFailedLabel'));
    }
  } catch (error) {
    message.error(pageText('pages.deleteRequestFailed'));
    console.error(error);
  } finally {
    loading.value = false;
  }
};

const deleteEntries = async (content) => {
  if (!content || !content.trim()) return false;
  deleteLoading.value = true;
  try {
    const res = await request.post(`${dictApiBase.value}/delete_entries`, {
      name: selectedDict.value,
      content,
    });
    if (res.code === 200) {
      message.success(pageText('pages.deletionCompletedSubmittedSubmittedDeletedDeleted', { submitted: res.data.total_submitted, deleted: res.data.deleted }));
      fetchDictList();
      fetchBruteDictList();
      fetchPreview(selectedDict.value);
      return true;
    }
    message.error(res.message || pageText('tasks.deletionFailedLabel'));
    return false;
  } catch (error) {
    message.error(pageText('pages.deleteRequestFailed'));
    console.error(error);
    return false;
  } finally {
    deleteLoading.value = false;
  }
};

// ======================= 安全策略与红线预检逻辑 =======================
const securityForm = ref({ blackIpsText: '', forbiddenDomainsText: '' });
const securityLoading = ref(false);
const securitySaveLoading = ref(false);
const guardrailDryRunInput = ref('');

const securityAnalysis = computed(() => (
  analyzeSecurityPolicy(securityForm.value.blackIpsText, securityForm.value.forbiddenDomainsText)
));

const guardrailDryRunResult = computed(() => (
  testTargetAgainstGuardrails(
    guardrailDryRunInput.value,
    securityForm.value.blackIpsText,
    securityForm.value.forbiddenDomainsText,
  )
));

const guardrailDryRunTagColor = computed(() => {
  const st = guardrailDryRunResult.value.status;
  if (st === 'allowed') return 'success';
  if (st === 'blocked_ip' || st === 'blocked_domain') return 'error';
  if (st === 'invalid') return 'warning';
  return 'default';
});

const guardrailDryRunText = computed(() => {
  const r = guardrailDryRunResult.value;
  if (r.status === 'allowed') return pageText('pages.guardrailDryRunAllowed', { target: r.target });
  if (r.status === 'blocked_ip') return pageText('pages.guardrailDryRunBlockedIp', { rule: r.matchedRule });
  if (r.status === 'blocked_domain') return pageText('pages.guardrailDryRunBlockedDomain', { rule: r.matchedRule });
  if (r.status === 'invalid') return pageText('pages.guardrailDryRunInvalid');
  return '';
});

const applyGuardrailIpPreset = (mode) => {
  securityForm.value.blackIpsText = applySecurityPreset(
    securityForm.value.blackIpsText,
    SECURITY_IP_PRESETS.rfc1918,
    mode,
  );
};

const applyGuardrailDomainPreset = () => {
  securityForm.value.forbiddenDomainsText = applySecurityPreset(
    securityForm.value.forbiddenDomainsText,
    SECURITY_DOMAIN_PRESETS.govEdu,
    'add',
  );
};

const fetchSecurityPolicy = async () => {
  securityLoading.value = true;
  try {
    const res = await request.get('/api/system_config/security_policy');
    if (res.code === 200) {
      securityForm.value.blackIpsText = (res.data.black_ips || []).join('\n');
      securityForm.value.forbiddenDomainsText = (res.data.forbidden_domains || []).join('\n');
      securityBaseline.value = cloneDeep(securityForm.value);
    } else {
      message.error(res.message || pageText('pages.failedToLoadSecurityPolicy'));
      if (!isConfigInitialized.value) securityBaseline.value = cloneDeep(securityForm.value);
    }
  } catch (error) {
    message.error(pageText('pages.securityPolicyRequestFailed'));
    console.error(error);
    if (!isConfigInitialized.value) securityBaseline.value = cloneDeep(securityForm.value);
  } finally {
    securityLoading.value = false;
  }
};

const resetSecurityForm = ({ silent = false } = {}) => {
  securityForm.value = cloneDeep(securityBaseline.value);
  if (!silent) message.info(pageText('pages.sectionChangesReset'));
};

const saveSecurityPolicy = async ({ silentSuccess = false } = {}) => {
  securitySaveLoading.value = true;
  try {
    const black_ips = securityForm.value.blackIpsText.split('\n').map((s) => s.trim()).filter(Boolean);
    const forbidden_domains = securityForm.value.forbiddenDomainsText.split('\n').map((s) => s.trim()).filter(Boolean);

    const res = await request.post('/api/system_config/security_policy', {
      black_ips,
      forbidden_domains,
    });

    if (res.code === 200) {
      securityBaseline.value = cloneDeep(securityForm.value);
      if (!silentSuccess) message.success(pageText('pages.securityPolicyUpdated'));
      fetchSecurityPolicy();
      return true;
    }
    message.error(res.message || pageText('pages.failedToSaveLabel2'));
    return false;
  } catch (error) {
    const errMsg = error?.response?.data?.message || pageText('pages.failedToSaveSecurityPolicy');
    message.error(errMsg);
    console.error(error);
    return false;
  } finally {
    securitySaveLoading.value = false;
  }
};

// ======================= 性能配置管理逻辑 =======================
const performanceForm = ref({
  celery_heavy_concurrency: 1,
  celery_light_concurrency: 1,
  osint_concurrency: 1,
  github_concurrency: 1,
});
const runtimePerformance = ref({ runtime_heavy_concurrency: null, runtime_light_concurrency: null, runtime_github_concurrency: null });
const pendingConvergence = ref(false);
const pendingNodes = ref([]);
const performanceLoading = ref(false);
const performanceSaveLoading = ref(false);

const pendingConvergenceText = computed(() => {
  if (!pendingConvergence.value) return '';
  const details = (pendingNodes.value || [])
    .filter((item) => item && item.queue && item.queue !== 'all')
    .map((item) => {
      const runtimeLabel = item.runtime === null || item.runtime === undefined
        ? pageText('pages.performanceRuntimeOffline')
        : String(item.runtime);
      return pageText('pages.performanceQueueTargetRuntime', {
        label: item.label || item.queue,
        target: item.target ?? '-',
        runtime: runtimeLabel,
      });
    })
    .join('；');
  return pageText('pages.performanceConvergencePendingAlert', {
    details: details || pageText('pages.performanceRuntimeOffline'),
  });
});

const fetchPerformanceConfig = async () => {
  performanceLoading.value = true;
  try {
    const res = await request.get('/api/system_config/performance');
    if (res.code === 200) {
      performanceForm.value.celery_heavy_concurrency = res.data.celery_heavy_concurrency || 1;
      performanceForm.value.celery_light_concurrency = res.data.celery_light_concurrency || 1;
      performanceForm.value.osint_concurrency = res.data.osint_concurrency || 1;
      performanceForm.value.github_concurrency = res.data.github_concurrency || 1;
      runtimePerformance.value.runtime_heavy_concurrency = res.data.runtime_heavy_concurrency ?? null;
      runtimePerformance.value.runtime_light_concurrency = res.data.runtime_light_concurrency ?? null;
      runtimePerformance.value.runtime_github_concurrency = res.data.runtime_github_concurrency ?? null;
      pendingConvergence.value = Boolean(res.data.pending_convergence);
      pendingNodes.value = Array.isArray(res.data.pending_nodes) ? res.data.pending_nodes : [];
      performanceBaseline.value = cloneDeep(performanceForm.value);
    } else {
      message.error(res.message || pageText('pages.failedToLoadPerformanceSettings'));
      if (!isConfigInitialized.value) performanceBaseline.value = cloneDeep(performanceForm.value);
    }
  } catch (error) {
    message.error(pageText('pages.performanceSettingsRequestFailed'));
    console.error(error);
    if (!isConfigInitialized.value) performanceBaseline.value = cloneDeep(performanceForm.value);
  } finally {
    performanceLoading.value = false;
  }
};

const resetPerformanceForm = ({ silent = false } = {}) => {
  performanceForm.value = cloneDeep(performanceBaseline.value);
  if (!silent) message.info(pageText('pages.sectionChangesReset'));
};

const savePerformanceConfig = async ({ silentSuccess = false } = {}) => {
  performanceSaveLoading.value = true;
  try {
    const res = await request.post('/api/system_config/performance', {
      celery_heavy_concurrency: performanceForm.value.celery_heavy_concurrency,
      celery_light_concurrency: performanceForm.value.celery_light_concurrency,
      osint_concurrency: performanceForm.value.osint_concurrency,
      github_concurrency: performanceForm.value.github_concurrency,
    });

    if (res.code === 200) {
      const isPending = Boolean(res.pending_convergence || res.data?.pending_convergence);
      if (isPending) {
        pendingConvergence.value = true;
        pendingNodes.value = res.pending_nodes || res.data?.pending_nodes || [];
        if (!silentSuccess) message.warning(res.message || pageText('pages.performanceSettingsUpdated'), 6);
      } else {
        pendingConvergence.value = false;
        pendingNodes.value = [];
        if (!silentSuccess) message.success(res.message || pageText('pages.performanceSettingsUpdated'), 5);
      }
      performanceBaseline.value = cloneDeep(performanceForm.value);
      fetchPerformanceConfig();
      return true;
    }
    message.error(res.message || pageText('pages.failedToSaveLabel2'));
    return false;
  } catch (error) {
    message.error(pageText('pages.failedToSavePerformanceSettings'));
    console.error(error);
    return false;
  } finally {
    performanceSaveLoading.value = false;
  }
};

const fetchBruteDictList = async (showLoading = true) => {
  if (showLoading) bruteLoading.value = true;
  try {
    const res = await request.get('/api/brute_dict/list');
    if (res.code === 200) {
      bruteDictList.value = res.data || [];
    } else {
      message.error(res.message || pageText('pages.failedToLoadCredentialDictionaries'));
    }
  } catch (error) {
    message.error(pageText('pages.credentialDictionaryRequestFailed'));
    console.error(error);
  } finally {
    if (showLoading) bruteLoading.value = false;
  }
};

const probeActiveBackupTask = async () => {
  try {
    const res = await request.get('/api/backup/status');
    if (res.code === 200 && res.data && ['backing_up', 'restoring'].includes(res.data.status)) {
      applyDomainAndSubTab('system_ops', 'backup');
    }
  } catch {
    // 页面初始化静默容错
  }
};

// 全向历史深链路由兼容映射
const LEGACY_TAB_MAP = {
  api_config: { tab: 'intel' },
  intel: { tab: 'intel' },
  proxy: { tab: 'egress_guardrails', subTab: 'proxy' },
  security: { tab: 'egress_guardrails', subTab: 'security' },
  egress_guardrails: { tab: 'egress_guardrails', subTab: 'proxy' },
  performance: { tab: 'scanning_arsenal', subTab: 'concurrency' },
  dictionary: { tab: 'scanning_arsenal', subTab: 'dict' },
  cdn: { tab: 'scanning_arsenal', subTab: 'cdn' },
  scanning_arsenal: { tab: 'scanning_arsenal', subTab: 'concurrency' },
  message_push: { tab: 'notifications' },
  notifications: { tab: 'notifications' },
  system_backup: { tab: 'system_ops', subTab: 'backup' },
  system_update: { tab: 'system_ops', subTab: 'update' },
  system_ops: { tab: 'system_ops', subTab: 'auth_infra' },
};

const applyRouteDeepLink = (query) => {
  if (!query) return;
  const rawTab = query.tab;
  const rawFocus = query.focus;

  if (rawTab === 'system_general') {
    if (rawFocus === 'proxy') {
      applyDomainAndSubTab('egress_guardrails', 'proxy');
      nextTick(() => proxyPanelRef.value?.focusSection?.('proxy'));
      return;
    }
    if (rawFocus === 'auth' || rawFocus === 'infra') {
      applyDomainAndSubTab('system_ops', 'auth_infra');
    } else {
      applyDomainAndSubTab('scanning_arsenal', 'concurrency');
    }
  } else if (rawTab && LEGACY_TAB_MAP[rawTab]) {
    const mapped = LEGACY_TAB_MAP[rawTab];
    applyDomainAndSubTab(mapped.tab, query.subTab || mapped.subTab);
  }

  if (rawFocus) {
    if (activeKey.value === 'egress_guardrails' && guardrailSubTab.value === 'proxy') {
      nextTick(() => proxyPanelRef.value?.focusSection?.(rawFocus));
      return;
    }
    const target = SETTINGS_INDEX.find((i) => i.anchor === rawFocus);
    if (target && !rawTab) {
      jumpToSetting(target);
    } else {
      scrollAndFlashAnchor(`[data-setting-anchor="${rawFocus}"]`);
    }
  }
};

watch(
  () => [route.query.tab, route.query.subTab, route.query.focus],
  ([tab, subTab, focus]) => {
    if (tab || subTab || focus) {
      applyRouteDeepLink(route.query);
      if (activeKey.value === 'egress_guardrails' && guardrailSubTab.value === 'proxy') {
        proxyPanelRef.value?.fetchProxyConfig?.(false);
      }
    }
  },
);

// 键盘快捷键 `/` 与 `Cmd/Ctrl+K` 聚焦搜索框，点击外部关闭下拉
const handleGlobalKeydown = (e) => {
  const tag = (e.target?.tagName || '').toUpperCase();
  const inEditable = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT' || e.target?.isContentEditable;
  if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
    e.preventDefault();
    searchInputRef.value?.focus?.();
    return;
  }
  if (!inEditable && e.key === '/') {
    e.preventDefault();
    searchInputRef.value?.focus?.();
  }
};

const handleDocumentClick = (e) => {
  if (!settingsKeyword.value) return;
  if (searchBoxWrapRef.value && !searchBoxWrapRef.value.contains(e.target)) {
    settingsKeyword.value = '';
  }
};

onMounted(async () => {
  probeActiveBackupTask();
  applyRouteDeepLink(route.query);
  window.addEventListener('beforeunload', handleBeforeUnload);
  window.addEventListener('keydown', handleGlobalKeydown);
  document.addEventListener('click', handleDocumentClick);

  fetchCapacityProbe();
  fetchDictList();
  fetchBruteDictList();
  try {
    await Promise.allSettled([
      fetchSecurityPolicy(),
      fetchPerformanceConfig(),
      fetchGeneralConfig(),
    ]);
  } finally {
    isConfigInitialized.value = true;
  }
});

const resolveLeaveGuard = (allowLeave) => {
  if (allowLeave) allowDirtyDeactivateOnce = true;
  leaveConfirmVisible.value = false;
  if (pendingLeaveResolver) {
    const resolve = pendingLeaveResolver;
    pendingLeaveResolver = null;
    resolve(allowLeave);
  }
};

const handleLeaveSaveAndGo = async () => {
  const ok = await saveAllDirtySections();
  resolveLeaveGuard(ok);
};

onDeactivated(() => {
  if (hasUnsavedChanges.value && !allowDirtyDeactivateOnce) {
    message.warning(pageText('pages.thereAreCountUnsavedConfigurationChangesSaveThemBefore', { count: unsavedCount.value }), 5);
  }
  allowDirtyDeactivateOnce = false;
  createDictDrawerVisible.value = false;
  appendDrawerVisible.value = false;
  searchDrawerVisible.value = false;
  cdnPanelRef.value?.closeDrawer?.();
  proxyPanelRef.value?.closeModals?.();
  updatePanelRef.value?.closeModals?.();
  backupPanelRef.value?.closeModals?.();
  clearAllDictPollTimers();
});

onUnmounted(() => {
  resolveLeaveGuard(false);
  window.removeEventListener('beforeunload', handleBeforeUnload);
  window.removeEventListener('keydown', handleGlobalKeydown);
  document.removeEventListener('click', handleDocumentClick);
  proxyPanelRef.value?.stopTimers?.();
  updatePanelRef.value?.stopUpdateTimers?.();
  clearAllDictPollTimers();
  backupPanelRef.value?.stopProgressTracking?.();
});

onBeforeRouteLeave(() => {
  allowDirtyDeactivateOnce = false;
  if (!hasUnsavedChanges.value) return true;
  return new Promise((resolve) => {
    pendingLeaveResolver = resolve;
    leaveConfirmVisible.value = true;
  });
});
</script>

<style scoped>
.arl-settings-page {
  padding-bottom: 32px;
}

.hero-brand-icon {
  color: var(--arl-theme-color);
  margin-right: 6px;
}

.hero-search-anchor {
  position: relative;
}

.hero-search-input {
  width: 210px;
}

.arl-hero-search-dropdown {
  position: absolute;
  top: calc(100% + 6px);
  right: 0;
  width: min(520px, 85vw);
  z-index: 40;
  border: 1px solid var(--arl-border-color);
  border-radius: 8px;
  background: var(--arl-bg-card);
  box-shadow: 0 12px 28px rgba(0, 0, 0, 0.14);
  overflow: hidden;
}

.arl-search-dropdown-meta {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 12px;
  font-size: 12px;
  color: var(--arl-text-secondary);
  background: var(--arl-bg-light);
  border-bottom: 1px solid var(--arl-border-color);
}

.arl-search-dropdown-list {
  max-height: 360px;
  overflow-y: auto;
}

.arl-search-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  cursor: pointer;
  border-bottom: 1px solid var(--arl-border-color);
  transition: background 0.15s;
}
.arl-search-item:last-child {
  border-bottom: none;
}
.arl-search-item:hover {
  background: var(--arl-bg-light);
}
.arl-search-item-main {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.arl-search-item-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--arl-text-color);
}
.arl-search-item-desc {
  font-size: 12px;
  color: var(--arl-text-secondary);
}
.arl-search-empty {
  padding: 20px 14px;
  text-align: center;
  font-size: 13px;
  color: var(--arl-text-secondary);
}

.hero-subtabs-row {
  margin-top: 10px;
}

.settings-hero-tabs :deep(.ant-tabs-nav) {
  margin-bottom: 0 !important;
}

.settings-section-container {
  max-width: 1240px;
}

.card-title-with-meta {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.card-title-icon {
  color: var(--arl-theme-color);
}

.proxy-route-tag {
  margin: 0;
  cursor: pointer;
}

.plugin-grid-container {
  background: var(--arl-bg-light);
  border-radius: 6px;
  padding: 12px;
}

.plugin-tile-card {
  border: 1px solid var(--arl-border-color);
  background: var(--arl-bg-card);
  padding: 12px;
  border-radius: 6px;
  min-height: 92px;
}

.plugin-tile-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.plugin-tile-name {
  font-weight: 600;
  text-transform: uppercase;
  color: var(--arl-theme-color);
}

.plugin-tile-pair {
  margin-top: 8px;
  display: flex;
  gap: 8px;
}

.plugin-tile-stack {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.plugin-free-badge {
  font-size: 12px;
  color: var(--arl-text-secondary);
}

/* 禁扫红线工作台 */
.guardrail-preset-bar {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 12px;
  margin-bottom: 14px;
  border-radius: 6px;
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
}

.guardrail-preset-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--arl-text-secondary);
}

.guardrail-preset-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.guardrail-editor-box {
  display: flex;
  flex-direction: column;
}

.guardrail-editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
}

.guardrail-editor-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--arl-text-color);
}

.guardrail-mono-textarea {
  font-family: var(--arl-font-mono);
  font-size: 12px;
}

.guardrail-dryrun-box {
  margin-top: 16px;
  padding: 12px 14px;
  border-radius: 6px;
  background: var(--arl-bg-light);
  border: 1px dashed var(--arl-border-color);
}

.guardrail-dryrun-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 500;
  color: var(--arl-text-color);
  margin-bottom: 8px;
}

.guardrail-dryrun-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

/* 并发分组标题 */
.section-group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--arl-text-color);
  margin-bottom: 10px;
}

/* 字典工作台局部细节 */
.dict-summary-strip {
  padding: 6px 14px;
  font-size: 12px;
  color: var(--arl-text-secondary);
  background: var(--arl-bg-light);
  border-bottom: 1px solid var(--arl-border-color);
}

.dict-cat-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.dict-item-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.dict-item-icon {
  margin-top: 3px;
  opacity: 0.78;
  flex-shrink: 0;
}

.dict-item-meta {
  display: flex;
  flex-direction: column;
  gap: 3px;
  flex: 1;
  min-width: 0;
}

.dict-item-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dict-item-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 6px;
}

.dict-empty-center {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}

.dict-detail-head-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 4px;
}

.dict-detail-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--arl-text-color);
}

.dict-instant-badge {
  font-size: 12px;
  color: var(--arl-text-secondary);
}

.dict-preview-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  background: var(--arl-bg-card);
  padding: 8px 14px;
  border-radius: 6px;
  border: 1px solid var(--arl-border-color);
}

.dict-preview-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--arl-text-color);
}

/* 通知通道卡片（自适应高度） */
.notify-channel-card {
  height: 100%;
  border-radius: 8px;
}

.webhook-schema-pre {
  margin: 0;
  padding: 8px;
  border-radius: 4px;
  font-family: var(--arl-font-mono);
  font-size: 11px;
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
  overflow-x: auto;
}

/* 公共样式类 */
.page-flex-input { flex: 1; }
.page-full-width-input { width: 100%; }
.page-small-text { font-size: 12px; }
.page-config-card { margin-bottom: 16px; border-radius: 8px; }
.page-flush-bottom { margin-bottom: 0; }
.page-field-spacing { margin-bottom: 12px; }
.page-rounded { border-radius: 8px; }
.page-panel-heading { font-weight: 600; font-size: 14px; color: var(--arl-text-color); }
.page-tiny-tag { margin: 0; font-size: 10px; line-height: 16px; padding: 0 4px; border-radius: 2px; }
.page-dictionary-summary { color: var(--arl-text-secondary); font-size: 12px; font-family: var(--arl-font-mono); }
.page-muted-label { font-size: 12px; color: var(--arl-text-secondary); }
.page-description { margin-bottom: 16px; color: var(--arl-text-color); font-size: 13px; }
.page-inline-gap { margin-right: 8px; }
.page-compact-description { margin-bottom: 12px; color: var(--arl-text-color); font-size: 13px; }
.page-code-preview { font-family: var(--arl-font-mono); font-size: 12px; margin-bottom: 24px; }
.page-form-section-title { margin-bottom: 8px; font-weight: 500; font-size: 14px; }
.page-success-detail { margin-bottom: 8px; color: #52c41a; font-size: 13px; }
.page-error-detail { margin-bottom: 8px; color: #ff4d4f; font-size: 13px; }
.page-warning-detail { color: #faad14; font-size: 12px; margin-top: 8px; }
.page-danger-section-title { margin-bottom: 8px; font-weight: 500; font-size: 14px; color: #ff4d4f; }
.page-empty-detail { margin-bottom: 8px; color: var(--arl-text-secondary); font-size: 12px; }
.page-code-summary { font-family: var(--arl-font-mono); font-size: 12px; margin-bottom: 16px; }
.page-warning-emphasis { color: #d46b08; }
.page-config-card-danger { margin-bottom: 16px; border-radius: 8px; border-left: 4px solid #ff4d4f; }
.page-choice-gap { margin-left: 8px; font-size: 12px; }
.page-strong-heading { font-weight: bold; margin-bottom: 8px; }
.page-config-card-success { margin-bottom: 16px; border-radius: 8px; border-left: 4px solid #52c41a; }
.page-config-card-info { margin-bottom: 16px; border-radius: 8px; border-left: 4px solid var(--arl-theme-color); }
.page-config-card-purple { margin-bottom: 16px; border-radius: 8px; border-left: 4px solid #722ed1; }
.page-config-card-theme { margin-bottom: 16px; border-radius: 8px; border-left: 4px solid var(--arl-theme-color); }
.page-form-spacing { margin-bottom: 8px; }
.performance-pending-alert { margin-bottom: 16px; border-radius: 6px; }

.arl-field-hint {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--arl-text-secondary);
}
.arl-field-hint code {
  background: var(--arl-bg-hover);
  padding: 1px 4px;
  border-radius: 3px;
}

.arl-recommend-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--arl-theme-color) 6%, transparent);
  border: 1px dashed color-mix(in srgb, var(--arl-theme-color) 30%, transparent);
  font-size: 13px;
}
.arl-recommend-label {
  color: var(--arl-text-secondary);
  margin-right: 6px;
}
.arl-recommend-basis {
  color: var(--arl-text-secondary);
  font-size: 12px;
}

.arl-leave-modal-body {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.arl-leave-modal-icon {
  font-size: 20px;
  color: #faad14;
  margin-top: 2px;
  flex-shrink: 0;
}
.arl-leave-modal-content {
  flex: 1;
  min-width: 0;
}
.arl-leave-section-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.page-wide-text :deep(.ant-card-head-title) {
  white-space: normal;
  line-height: 1.5;
  padding: 8px 0;
}
</style>
