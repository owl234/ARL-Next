<template>
  <div class="arl-page-container">
    <!-- 1. 吸顶 Hero 控制卡片：主域胶囊切换 + Token/额度状态 + 自动轮询 + 主操作 + 子页签 + 工具栏 -->
    <div ref="actionBarRef" class="arl-hero-card">
      <div class="arl-hero-unified-bar">
        <div class="arl-hero-left">
          <div class="arl-hero-title">
            <github-outlined class="hero-brand-icon" />
            <span>{{ pageText('pages.githubMonitoring') }}</span>
          </div>

          <div class="arl-capsule-switcher">
            <button
              type="button"
              class="arl-capsule-item"
              :class="{ 'is-active': mainTab === 'dlp' }"
              @click="switchMainTab('dlp')"
            >
              <safety-outlined />
              <span>{{ pageText('pages.codeLeakMonitoring') }}</span>
              <span v-if="findingsStats.pending > 0 || findingsStats.running_tasks > 0" class="arl-capsule-count">
                <span v-if="findingsStats.running_tasks > 0" class="arl-capsule-dot is-pulse"></span>
                {{ findingsStats.pending }}
              </span>
            </button>

            <button
              type="button"
              class="arl-capsule-item"
              :class="{ 'is-active': mainTab === 'ti' }"
              @click="switchMainTab('ti')"
            >
              <radar-chart-outlined />
              <span>{{ pageText('pages.threatIntelligence') }}</span>
              <span v-if="runningRadarCount > 0" class="arl-capsule-count">
                <span class="arl-capsule-dot is-pulse"></span>
                {{ runningRadarCount }}
              </span>
            </button>
          </div>
        </div>

        <div class="arl-hero-right">
          <!-- Token 与双维度额度胶囊 -->
          <div class="gh-token-pill-wrap">
            <a-tooltip :title="tokenTooltipText" placement="bottomRight">
              <a-tag
                :color="tokenTagColor"
                class="gh-token-pill"
                @click="goToGithubTokenConfig"
              >
                <key-outlined />
                <span>{{ tokenPillLabel }}</span>
              </a-tag>
            </a-tooltip>
            <a-tooltip :title="pageText('pages.githubRecheckToken')">
              <a-button type="text" size="small" :loading="tokenChecking" @click="fetchTokenStatus">
                <template #icon><reload-outlined /></template>
              </a-button>
            </a-tooltip>
          </div>

          <a-tooltip :title="pageText('pages.githubAutoPollTooltip')">
            <div class="gh-auto-poll">
              <a-switch v-model:checked="autoPollEnabled" size="small" />
              <span class="gh-auto-poll-label">{{ pageText('pages.githubAutoPollLabel') }}</span>
            </div>
          </a-tooltip>

          <a-button size="small" :loading="isRefreshingActive" @click="refreshActiveView">
            <template #icon><sync-outlined :spin="isRefreshingActive" /></template>
            {{ pageText('tasks.refresh') }}
          </a-button>

          <a-divider type="vertical" style="height: 18px; margin: 0 2px;" />

          <template v-if="mainTab === 'dlp'">
            <template v-if="activeTabDlp === 'scheduler'">
              <a-button type="primary" size="small" @click="openSchedulerAdd">
                <template #icon><plus-outlined /></template>
                {{ pageText('pages.addPolicy') }}
              </a-button>
            </template>
            <template v-else-if="activeTabDlp === 'task'">
              <a-button type="primary" size="small" @click="openTaskAdd">
                <template #icon><plus-outlined /></template>
                {{ pageText('pages.newOneTimeTask') }}
              </a-button>
            </template>
            <template v-else>
              <a-button size="small" @click="openSchedulerAdd">
                <template #icon><clock-circle-outlined /></template>
                {{ pageText('pages.addPolicy') }}
              </a-button>
              <a-button type="primary" size="small" @click="openTaskAdd">
                <template #icon><plus-outlined /></template>
                {{ pageText('pages.newOneTimeTask') }}
              </a-button>
            </template>
          </template>
          <template v-else>
            <a-button
              v-if="activeTabTi === 'tools_target'"
              type="primary"
              size="small"
              @click="openToolAdd"
            >
              <template #icon><plus-outlined /></template>
              {{ pageText('pages.monitorATool') }}
            </a-button>
            <a-button
              v-else-if="activeTabTi === 'hackers_target'"
              type="primary"
              size="small"
              @click="openHackerAdd"
            >
              <template #icon><plus-outlined /></template>
              {{ pageText('pages.monitorAResearcher') }}
            </a-button>
            <a-button
              v-else
              type="primary"
              size="small"
              :loading="cveRunLoading || cveConfig.is_running"
              @click="runCveOnce"
            >
              <template #icon><thunderbolt-outlined /></template>
              {{ cveConfig.is_running ? pageText('pages.scanningInTheBackground') : pageText('pages.scanOnceNow') }}
            </a-button>
          </template>
        </div>
      </div>

      <!-- 仅在 Token 未配置、失效、限流或网络异常时展开提示条 -->
      <a-alert
        v-if="showTokenWarningAlert"
        :type="tokenStatus.status === 'rate_limited' ? 'warning' : 'error'"
        show-icon
        class="gh-token-alert"
      >
        <template #message>
          <span>{{ pageText('pages.githubTokenStatus') }} {{ tokenStatus.msg }}</span>
          <a class="gh-settings-link" @click="goToGithubTokenConfig">{{ pageText('tasks.openSettings') }}</a>
        </template>
        <template #description>
          {{ pageText('pages.thisModuleUsesAGithubTokenForCodeLeak') }}
        </template>
      </a-alert>

      <!-- 二级视角页签 (.arl-detail-tabs) -->
      <a-tabs
        v-if="mainTab === 'dlp'"
        v-model:activeKey="activeTabDlp"
        type="card"
        size="small"
        class="arl-detail-tabs gh-sub-tabs"
      >
        <a-tab-pane key="findings">
          <template #tab>
            <span class="gh-tab-label">
              <span>{{ pageText('pages.githubFindingsOverview') }}</span>
              <span class="gh-tab-badge" :class="{ 'is-highlight': findingsStats.pending > 0 }">
                {{ findingsStats.pending }}
              </span>
            </span>
          </template>
        </a-tab-pane>
        <a-tab-pane key="scheduler">
          <template #tab>
            <span class="gh-tab-label">
              <span>{{ pageText('pages.githubPoliciesTab') }}</span>
              <span class="gh-tab-badge">{{ schedulerPagination.total }}</span>
            </span>
          </template>
        </a-tab-pane>
        <a-tab-pane key="task">
          <template #tab>
            <span class="gh-tab-label">
              <span>{{ pageText('pages.githubTasksTab') }}</span>
              <span class="gh-tab-badge" :class="{ 'is-running': findingsStats.running_tasks > 0 }">
                {{ taskPagination.total }}
              </span>
            </span>
          </template>
        </a-tab-pane>
      </a-tabs>

      <a-tabs
        v-else
        v-model:activeKey="activeTabTi"
        type="card"
        size="small"
        class="arl-detail-tabs gh-sub-tabs"
      >
        <a-tab-pane key="cve_history">
          <template #tab>
            <span class="gh-tab-label">
              <span>{{ pageText('pages.cveMonitoring') }}</span>
              <span class="gh-tab-badge">{{ cveData.length }}</span>
            </span>
          </template>
        </a-tab-pane>
        <a-tab-pane key="tools_target">
          <template #tab>
            <span class="gh-tab-label">
              <span>{{ pageText('pages.securityToolTracking') }}</span>
              <span class="gh-tab-badge">{{ toolsData.length }}</span>
            </span>
          </template>
        </a-tab-pane>
        <a-tab-pane key="hackers_target">
          <template #tab>
            <span class="gh-tab-label">
              <span>{{ pageText('pages.researcherActivity') }}</span>
              <span class="gh-tab-badge">{{ hackersData.length }}</span>
            </span>
          </template>
        </a-tab-pane>
      </a-tabs>

      <!-- 三级：当前子页签紧凑工具栏 (.arl-toolbar-row) -->
      <!-- 1. 泄露命中总览工具栏 -->
      <div v-if="mainTab === 'dlp' && activeTabDlp === 'findings'" class="gh-findings-toolbar-wrap">
        <div class="arl-toolbar-row">
          <div class="arl-filter-group">
            <a-radio-group
              v-model:value="findingsQuickFilter"
              size="small"
              button-style="solid"
              @change="onFindingsQuickFilterChange"
            >
              <a-radio-button value="all">{{ pageText('pages.githubTriageAll') }} ({{ findingsStats.total }})</a-radio-button>
              <a-radio-button value="pending">{{ pageText('pages.githubTriagePending') }} ({{ findingsStats.pending }})</a-radio-button>
              <a-radio-button value="confirmed">{{ pageText('pages.githubTriageConfirmed') }} ({{ findingsStats.confirmed }})</a-radio-button>
              <a-radio-button value="false_positive">{{ pageText('pages.githubTriageFalsePositive') }} ({{ findingsStats.false_positive }})</a-radio-button>
              <a-radio-button value="ignored">{{ pageText('pages.githubTriageIgnoredView') }}</a-radio-button>
            </a-radio-group>

            <a-select
              v-model:value="findingsSearchForm.source_type"
              size="small"
              class="gh-width-120"
              @change="onFindingsSearch"
            >
              <a-select-option value="all">{{ pageText('pages.githubSourceAll') }}</a-select-option>
              <a-select-option value="task">{{ pageText('pages.githubSourceManual') }}</a-select-option>
              <a-select-option value="scheduler">{{ pageText('pages.githubSourceScheduler') }}</a-select-option>
            </a-select>

            <a-input
              v-model:value="findingsSearchForm.repo_full_name"
              :placeholder="pageText('pages.repositoryEGUserRepo')"
              size="small"
              class="gh-width-170"
              allowClear
              @pressEnter="onFindingsSearch"
            >
              <template #prefix><search-outlined class="gh-input-icon" /></template>
            </a-input>

            <a-input
              v-model:value="findingsSearchForm.path"
              :placeholder="pageText('pages.filePathEGConfigPy')"
              size="small"
              class="gh-width-160"
              allowClear
              @pressEnter="onFindingsSearch"
            />

            <a-input
              v-model:value="findingsSearchForm.human_content"
              :placeholder="pageText('pages.keywordInCode')"
              size="small"
              class="gh-width-160"
              allowClear
              @pressEnter="onFindingsSearch"
            />

            <a-button size="small" @click="resetFindingsSearch">
              <template #icon><undo-outlined /></template>
              {{ pageText('assets.reset') }}
            </a-button>

            <a-tag
              v-if="findingsSourceLabel"
              color="blue"
              closable
              @close="clearFindingsSourceContext"
            >
              {{ pageText('pages.githubFilterBySourceCleared', { name: findingsSourceLabel }) }}
            </a-tag>
          </div>

          <div class="arl-actions-group">
            <a-radio-group
              v-model:value="findingsGroupMode"
              size="small"
              @change="onFindingsGroupModeChange"
            >
              <a-radio-button value="flat">{{ pageText('pages.githubViewFlat') }}</a-radio-button>
              <a-radio-button value="repo">{{ pageText('pages.githubViewRepo') }}</a-radio-button>
            </a-radio-group>

            <a-button size="small" @click="openIgnoredReposDrawer">
              <template #icon><eye-invisible-outlined /></template>
              {{ pageText('pages.githubIgnoredRepoManage', { count: findingsStats.ignored_repos || 0 }) }}
            </a-button>

            <a-dropdown>
              <a-button size="small" :loading="findingsExportLoading">
                <template #icon><download-outlined /></template>
                {{ pageText('pages.export') }}
                <down-outlined />
              </a-button>
              <template #overlay>
                <a-menu @click="({ key }) => handleExportFindings(key)">
                  <a-menu-item key="csv">{{ pageText('pages.githubExportCsv') }}</a-menu-item>
                  <a-menu-item key="json">{{ pageText('pages.githubExportJson') }}</a-menu-item>
                </a-menu>
              </template>
            </a-dropdown>
          </div>
        </div>
      </div>

      <!-- 2. 周期监控策略工具栏 -->
      <div v-else-if="mainTab === 'dlp' && activeTabDlp === 'scheduler'" class="arl-toolbar-row">
        <div class="arl-filter-group">
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.policyName') }}</span>
            <a-input
              v-model:value="schedulerSearchForm.name"
              :placeholder="pageText('pages.enterAPolicyName')"
              size="small"
              class="gh-width-160"
              allowClear
              @pressEnter="onSchedulerSearch"
            />
          </div>
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.keyword') }}</span>
            <a-input
              v-model:value="schedulerSearchForm.keyword"
              :placeholder="pageText('pages.enterAKeyword')"
              size="small"
              class="gh-width-160"
              allowClear
              @pressEnter="onSchedulerSearch"
            />
          </div>
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('tasks.statusLabel') }}</span>
            <a-select
              v-model:value="schedulerSearchForm.status"
              :placeholder="pageText('pages.selectAStatus')"
              size="small"
              class="gh-width-130"
              allowClear
              @change="onSchedulerSearch"
            >
              <a-select-option value="running">{{ TASK_STATUS_LABEL.running }}</a-select-option>
              <a-select-option value="stop">{{ TASK_STATUS_LABEL.stop }}</a-select-option>
              <a-select-option value="error">{{ TASK_STATUS_LABEL.error }}</a-select-option>
            </a-select>
          </div>
          <a-button size="small" @click="resetSchedulerSearch">
            <template #icon><undo-outlined /></template>
            {{ pageText('assets.reset') }}
          </a-button>
        </div>
      </div>

      <!-- 3. 扫描任务记录工具栏 -->
      <div v-else-if="mainTab === 'dlp' && activeTabDlp === 'task'" class="arl-toolbar-row">
        <div class="arl-filter-group">
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('tasks.taskNameLabel') }}</span>
            <a-input
              v-model:value="taskSearchForm.name"
              :placeholder="pageText('tasks.enterATaskName')"
              size="small"
              class="gh-width-160"
              allowClear
              @pressEnter="onTaskSearch"
            />
          </div>
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.keyword') }}</span>
            <a-input
              v-model:value="taskSearchForm.keyword"
              :placeholder="pageText('pages.enterAKeyword')"
              size="small"
              class="gh-width-160"
              allowClear
              @pressEnter="onTaskSearch"
            />
          </div>
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.githubSourceFilterLabel') }}</span>
            <a-select
              v-model:value="taskSearchForm.source_type"
              size="small"
              class="gh-width-120"
              @change="onTaskSearch"
            >
              <a-select-option value="all">{{ pageText('pages.githubSourceAll') }}</a-select-option>
              <a-select-option value="task">{{ pageText('pages.githubSourceManual') }}</a-select-option>
              <a-select-option value="scheduler">{{ pageText('pages.githubSourceScheduler') }}</a-select-option>
            </a-select>
          </div>
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('tasks.statusLabel') }}</span>
            <a-select
              v-model:value="taskSearchForm.status"
              :placeholder="pageText('pages.selectAStatus')"
              size="small"
              class="gh-width-130"
              allowClear
              @change="onTaskSearch"
            >
              <a-select-option value="waiting">{{ TASK_STATUS_LABEL.waiting }}</a-select-option>
              <a-select-option value="running">{{ TASK_STATUS_LABEL.running }}</a-select-option>
              <a-select-option value="done">{{ TASK_STATUS_LABEL.done }}</a-select-option>
              <a-select-option value="error">{{ TASK_STATUS_LABEL.error }}</a-select-option>
              <a-select-option value="stop">{{ TASK_STATUS_LABEL.stop }}</a-select-option>
            </a-select>
          </div>
          <a-button size="small" @click="resetTaskSearch">
            <template #icon><undo-outlined /></template>
            {{ pageText('assets.reset') }}
          </a-button>
        </div>
      </div>

      <!-- 4. CVE 漏洞雷达工具栏 -->
      <div v-else-if="mainTab === 'ti' && activeTabTi === 'cve_history'" class="arl-toolbar-row">
        <div class="arl-filter-group">
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.cveId') }}</span>
            <a-input
              v-model:value="cveSearchForm.cve_name"
              :placeholder="pageText('pages.enterACveId')"
              size="small"
              class="gh-width-160"
              allowClear
              @pressEnter="onCveSearch"
            />
          </div>
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.description') }}</span>
            <a-input
              v-model:value="cveSearchForm.desc"
              :placeholder="pageText('pages.enterADescription')"
              size="small"
              class="gh-width-180"
              allowClear
              @pressEnter="onCveSearch"
            />
          </div>
          <div class="gh-inline-switch-box">
            <a-switch v-model:checked="cveSearchForm.todayOnly" size="small" @change="onCveSearch" />
            <span>{{ pageText('pages.githubOnlyTodayCve') }}</span>
          </div>
          <a-button size="small" @click="resetCveSearch">
            <template #icon><undo-outlined /></template>
            {{ pageText('assets.reset') }}
          </a-button>
        </div>

        <div class="arl-actions-group">
          <div class="gh-schedule-strip">
            <span>{{ pageText('pages.scheduledMonitoring') }}</span>
            <a-switch size="small" v-model:checked="cveConfig.enabled" @change="saveCveConfig" />
            <a-select
              v-if="cveConfig.enabled"
              size="small"
              v-model:value="cveConfig.interval"
              class="gh-width-110"
              @change="saveCveConfig"
            >
              <a-select-option :value="6">{{ pageText('pages.every6Hours') }}</a-select-option>
              <a-select-option :value="12">{{ pageText('pages.every12Hours') }}</a-select-option>
              <a-select-option :value="24">{{ pageText('pages.every24Hours') }}</a-select-option>
            </a-select>
          </div>
        </div>
      </div>

      <!-- 5. 武器库追踪工具栏 -->
      <div v-else-if="mainTab === 'ti' && activeTabTi === 'tools_target'" class="arl-toolbar-row">
        <div class="arl-filter-group">
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.toolUrl') }}</span>
            <a-input
              v-model:value="toolsSearchForm.repo_url"
              :placeholder="pageText('pages.enterAToolUrl')"
              size="small"
              class="gh-width-220"
              allowClear
              @pressEnter="onToolsSearch"
            />
          </div>
          <a-button size="small" @click="resetToolsSearch">
            <template #icon><undo-outlined /></template>
            {{ pageText('assets.reset') }}
          </a-button>
        </div>

        <div class="arl-actions-group">
          <div class="gh-schedule-strip">
            <span>{{ pageText('pages.monitoringEnabled') }}</span>
            <a-switch size="small" v-model:checked="toolsConfig.enabled" @change="saveToolsConfig" />
            <a-select
              v-if="toolsConfig.enabled"
              size="small"
              v-model:value="toolsConfig.interval"
              class="gh-width-110"
              @change="saveToolsConfig"
            >
              <a-select-option :value="1">{{ pageText('pages.everyHour') }}</a-select-option>
              <a-select-option :value="2">{{ pageText('pages.every2Hours') }}</a-select-option>
              <a-select-option :value="6">{{ pageText('pages.every6Hours') }}</a-select-option>
              <a-select-option :value="12">{{ pageText('pages.every12Hours') }}</a-select-option>
              <a-select-option :value="24">{{ pageText('pages.onceADay') }}</a-select-option>
            </a-select>
          </div>
          <a-button
            size="small"
            type="primary"
            ghost
            :loading="toolsRunLoading || toolsConfig.is_running"
            @click="runToolsOnce"
          >
            {{ toolsConfig.is_running ? pageText('pages.scanningInTheBackground') : pageText('pages.scanOnceNow') }}
          </a-button>
        </div>
      </div>

      <!-- 6. 安全研究员动态工具栏 -->
      <div v-else-if="mainTab === 'ti' && activeTabTi === 'hackers_target'" class="arl-toolbar-row">
        <div class="arl-filter-group">
          <div class="arl-filter-item">
            <span class="arl-filter-label">GitHub ID</span>
            <a-input
              v-model:value="hackersSearchForm.github_id"
              :placeholder="pageText('pages.enterAGithubId')"
              size="small"
              class="gh-width-180"
              allowClear
              @pressEnter="onHackersSearch"
            />
          </div>
          <a-button size="small" @click="resetHackersSearch">
            <template #icon><undo-outlined /></template>
            {{ pageText('assets.reset') }}
          </a-button>
        </div>

        <div class="arl-actions-group">
          <a-button size="small" @click="openHackersHistoryDrawer('')">
            <template #icon><history-outlined /></template>
            {{ pageText('pages.viewAllDiscoveredTools') }}
          </a-button>
          <div class="gh-schedule-strip">
            <span>{{ pageText('pages.monitoringEnabled') }}</span>
            <a-switch size="small" v-model:checked="hackersConfig.enabled" @change="saveHackersConfig" />
            <a-select
              v-if="hackersConfig.enabled"
              size="small"
              v-model:value="hackersConfig.interval"
              class="gh-width-110"
              @change="saveHackersConfig"
            >
              <a-select-option :value="1">{{ pageText('pages.everyHour') }}</a-select-option>
              <a-select-option :value="2">{{ pageText('pages.every2Hours') }}</a-select-option>
              <a-select-option :value="6">{{ pageText('pages.every6Hours') }}</a-select-option>
              <a-select-option :value="12">{{ pageText('pages.every12Hours') }}</a-select-option>
              <a-select-option :value="24">{{ pageText('pages.onceADay') }}</a-select-option>
            </a-select>
          </div>
          <a-button
            size="small"
            type="primary"
            ghost
            :loading="hackersRunLoading || hackersConfig.is_running"
            @click="runHackersOnce"
          >
            {{ hackersConfig.is_running ? pageText('pages.scanningInTheBackground') : pageText('pages.scanOnceNow') }}
          </a-button>
        </div>
      </div>
    </div>

    <!-- ================= 主内容表区域 ================= -->
    <!-- A1. 泄露命中总览（平铺明细 / 按仓库聚合） -->
    <template v-if="mainTab === 'dlp' && activeTabDlp === 'findings'">
      <a-table
        v-if="findingsGroupMode === 'flat'"
        :sticky="stickyConfig"
        :row-selection="{
          selectedRowKeys: findingsSelectedRowKeys,
          onChange: onFindingsSelectChange,
          preserveSelectedRowKeys: true
        }"
        :loading="findingsLoading"
        :dataSource="findingsData"
        :columns="findingsFlatColumns"
        :pagination="false"
        size="small"
        rowKey="hash_md5"
      >
        <template #emptyText>
          <ArlEmpty :description="pageText('pages.noCodeLeakFindings')" />
        </template>
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'repo_file'">
            <div class="gh-repo-file-cell">
              <div class="gh-repo-line">
                <a
                  :href="`https://github.com/${record.repo_full_name}`"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="gh-repo-link"
                >
                  {{ record.repo_full_name }}
                </a>
                <a-tag v-if="record.is_repo_ignored" color="default">{{ pageText('pages.githubTriageIgnoredView') }}</a-tag>
                <a-tag v-if="record.source_count > 1" color="purple">
                  {{ pageText('pages.githubHitSourcesCount', { count: record.source_count }) }}
                </a-tag>
              </div>
              <a
                :href="record.html_url || `https://github.com/${record.repo_full_name}/blob/HEAD/${record.path}`"
                target="_blank"
                rel="noopener noreferrer"
                class="gh-path-link"
              >
                {{ record.path }} <link-outlined />
              </a>
              <div class="gh-source-meta">
                <a-tag :color="record.source_type === 'scheduler' ? 'purple' : 'blue'">
                  {{ record.source_type === 'scheduler' ? pageText('pages.githubSourceScheduler') : pageText('pages.githubSourceManual') }}
                </a-tag>
                <span v-if="record.source_names?.length" class="gh-source-names">
                  {{ record.source_names.join(' / ') }}
                </span>
              </div>
            </div>
          </template>

          <template v-else-if="column.key === 'human_content'">
            <GithubCodeReader
              :content="record.human_content"
              :keyword="record.keyword"
              :html-url="record.html_url"
              :repo-full-name="record.repo_full_name"
              max-height="190px"
              @expand="openFindingDetailDrawer(record)"
            />
          </template>

          <template v-else-if="column.key === 'triage_status'">
            <div class="gh-triage-cell">
              <a-tag :color="triageStatusColor(record.triage_status)">
                {{ triageStatusLabel(record.triage_status) }}
              </a-tag>
              <div v-if="record.triage_note" class="gh-triage-note-preview" :title="record.triage_note">
                {{ record.triage_note }}
              </div>
            </div>
          </template>

          <template v-else-if="column.key === 'keyword_time'">
            <div class="gh-meta-stack">
              <a-tag color="blue">{{ record.keyword }}</a-tag>
              <span class="gh-time-text">{{ record.commit_date || record.insert_time || '-' }}</span>
            </div>
          </template>

          <template v-else-if="column.key === 'action'">
            <div class="gh-row-actions">
              <a-tooltip :title="pageText('pages.githubMarkConfirmed')">
                <a-button
                  size="small"
                  :type="record.triage_status === 'confirmed' ? 'primary' : 'default'"
                  @click="updateTriageStatus([record.hash_md5], 'confirmed')"
                >
                  <template #icon><check-outlined /></template>
                </a-button>
              </a-tooltip>
              <a-tooltip :title="pageText('pages.githubMarkFalsePositive')">
                <a-button
                  size="small"
                  :danger="record.triage_status === 'false_positive'"
                  @click="updateTriageStatus([record.hash_md5], 'false_positive')"
                >
                  <template #icon><close-outlined /></template>
                </a-button>
              </a-tooltip>
              <a-tooltip v-if="!record.is_repo_ignored" :title="pageText('pages.githubIgnoreRepo')">
                <a-popconfirm
                  :title="pageText('pages.githubIgnoreRepoConfirm', { repo: record.repo_full_name })"
                  :ok-text="pageText('pages.confirm')"
                  :cancel-text="pageText('tasks.cancel')"
                  @confirm="handleIgnoreRepos('add', [record.repo_full_name])"
                >
                  <a-button size="small">
                    <template #icon><eye-invisible-outlined /></template>
                  </a-button>
                </a-popconfirm>
              </a-tooltip>
              <a-tooltip v-else :title="pageText('pages.githubUnignoreRepo')">
                <a-button size="small" @click="handleIgnoreRepos('remove', [record.repo_full_name])">
                  <template #icon><eye-outlined /></template>
                </a-button>
              </a-tooltip>
            </div>
          </template>
        </template>
      </a-table>

      <!-- 按仓库聚合折叠表格 -->
      <a-table
        v-else
        :sticky="stickyConfig"
        :row-selection="{
          selectedRowKeys: findingsRepoSelectedKeys,
          onChange: onFindingsRepoSelectChange,
          preserveSelectedRowKeys: true
        }"
        :loading="findingsLoading"
        :dataSource="findingsRepoData"
        :columns="findingsRepoColumns"
        :pagination="false"
        size="small"
        rowKey="repo_full_name"
      >
        <template #emptyText>
          <ArlEmpty :description="pageText('pages.noCodeLeakFindings')" />
        </template>
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'repo_full_name'">
            <div class="gh-repo-line">
              <a
                :href="`https://github.com/${record.repo_full_name}`"
                target="_blank"
                rel="noopener noreferrer"
                class="gh-repo-link"
              >
                {{ record.repo_full_name }} <link-outlined />
              </a>
              <a-tag v-if="record.is_repo_ignored" color="default">{{ pageText('pages.githubTriageIgnoredView') }}</a-tag>
            </div>
          </template>

          <template v-else-if="column.key === 'file_count'">
            <a-tag color="blue">{{ record.file_count }}</a-tag>
          </template>

          <template v-else-if="column.key === 'breakdown'">
            <div class="gh-breakdown-tags">
              <a-tag v-if="record.pending_count > 0" color="warning">
                {{ pageText('pages.githubRepoPendingTag', { count: record.pending_count }) }}
              </a-tag>
              <a-tag v-if="record.confirmed_count > 0" color="error">
                {{ pageText('pages.githubRepoConfirmedTag', { count: record.confirmed_count }) }}
              </a-tag>
              <a-tag v-if="record.false_positive_count > 0" color="default">
                {{ pageText('pages.githubRepoFalsePositiveTag', { count: record.false_positive_count }) }}
              </a-tag>
            </div>
          </template>

          <template v-else-if="column.key === 'keywords'">
            <div class="gh-breakdown-tags">
              <a-tag v-for="kw in (record.keywords || [])" :key="kw" color="blue">{{ kw }}</a-tag>
            </div>
          </template>

          <template v-else-if="column.key === 'action'">
            <div class="gh-row-actions">
              <a-button
                size="small"
                @click="updateTriageStatus((record.files || []).map(f => f.hash_md5), 'false_positive')"
              >
                {{ pageText('pages.githubMarkFalsePositive') }}
              </a-button>
              <a-popconfirm
                v-if="!record.is_repo_ignored"
                :title="pageText('pages.githubIgnoreRepoConfirm', { repo: record.repo_full_name })"
                :ok-text="pageText('pages.confirm')"
                :cancel-text="pageText('tasks.cancel')"
                @confirm="handleIgnoreRepos('add', [record.repo_full_name])"
              >
                <a-button size="small">{{ pageText('pages.githubIgnoreRepo') }}</a-button>
              </a-popconfirm>
              <a-button
                v-else
                size="small"
                @click="handleIgnoreRepos('remove', [record.repo_full_name])"
              >
                {{ pageText('pages.githubUnignoreRepo') }}
              </a-button>
              <a-button size="small" @click="copyCloneForRepo(record.repo_full_name)">
                <template #icon><copy-outlined /></template>
              </a-button>
            </div>
          </template>
        </template>

        <template #expandedRowRender="{ record }">
          <div class="gh-repo-expanded-list">
            <div v-for="file in (record.files || [])" :key="file.hash_md5" class="gh-repo-expanded-item">
              <div class="gh-repo-expanded-head">
                <a
                  :href="file.html_url || `https://github.com/${file.repo_full_name}/blob/HEAD/${file.path}`"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="gh-path-link"
                >
                  {{ file.path }} <link-outlined />
                </a>
                <div class="gh-row-actions">
                  <a-tag :color="triageStatusColor(file.triage_status)">{{ triageStatusLabel(file.triage_status) }}</a-tag>
                  <span class="gh-time-text">{{ file.commit_date || '-' }}</span>
                  <a-button size="small" @click="updateTriageStatus([file.hash_md5], 'confirmed')">
                    {{ pageText('pages.githubMarkConfirmed') }}
                  </a-button>
                  <a-button size="small" @click="updateTriageStatus([file.hash_md5], 'false_positive')">
                    {{ pageText('pages.githubMarkFalsePositive') }}
                  </a-button>
                </div>
              </div>
              <GithubCodeReader
                :content="file.human_content"
                :keyword="file.keyword"
                :html-url="file.html_url"
                :repo-full-name="file.repo_full_name"
                max-height="170px"
                compact
                @expand="openFindingDetailDrawer(file)"
              />
            </div>
          </div>
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">
          {{ pageText('tasks.paginationSummary', { pages: Math.ceil(findingsPager.total / findingsPager.pageSize) || 1, total: findingsPager.total }) }}
        </div>
        <a-pagination
          size="small"
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="findingsPager.current"
          v-model:pageSize="findingsPager.pageSize"
          :total="findingsPager.total"
          show-size-changer
          @change="handleFindingsTableChange"
          @showSizeChange="handleFindingsTableChange"
        />
      </div>
    </template>

    <!-- A2. 周期监控策略列表 -->
    <template v-else-if="mainTab === 'dlp' && activeTabDlp === 'scheduler'">
      <a-table
        :sticky="stickyConfig"
        :row-selection="{
          selectedRowKeys: schedulerSelectedRowKeys,
          onChange: onSchedulerSelectChange,
          preserveSelectedRowKeys: true
        }"
        :loading="schedulerLoading"
        :dataSource="schedulerData"
        :columns="schedulerColumns"
        :pagination="false"
        size="small"
        :rowKey="(record) => record._id"
      >
        <template #emptyText>
          <ArlEmpty :description="pageText('pages.noPolicies')" />
        </template>
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <a class="gh-primary-link" @click="openResultDrawer(record, 'scheduler')">{{ record.name }}</a>
          </template>
          <template v-else-if="column.key === 'keyword'">
            <a-tag color="blue">{{ record.keyword }}</a-tag>
          </template>
          <template v-else-if="column.key === 'result_count'">
            <a-tooltip :title="pageText('pages.githubResultCountLinkTip')">
              <a-tag
                :color="(record.result_count || 0) > 0 ? 'geekblue' : 'default'"
                class="gh-clickable-tag"
                @click="jumpToFindingsFromSource('scheduler', record)"
              >
                {{ record.result_count || 0 }}
              </a-tag>
            </a-tooltip>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="formatGithubStatusColor(record.status)">
              {{ formatTaskStatus(record.status) }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <div class="gh-row-actions">
              <a-button size="small" type="link" class="gh-link-btn" @click="openResultDrawer(record, 'scheduler')">
                {{ pageText('pages.view') }}
              </a-button>
              <a-button size="small" type="primary" ghost @click="handleSchedulerRunNow([record._id])">
                {{ pageText('pages.githubRunNow') }}
              </a-button>
              <a-button
                size="small"
                :disabled="record.status !== 'running'"
                @click="handleSchedulerSingleAction('stop', record._id)"
              >
                {{ pageText('tasks.stop') }}
              </a-button>
              <a-button
                size="small"
                :disabled="record.status !== 'stop'"
                @click="handleSchedulerSingleAction('recover', record._id)"
              >
                {{ pageText('tasks.resume') }}
              </a-button>
              <a-button size="small" @click="openSchedulerEdit(record)">
                {{ pageText('pages.edit') }}
              </a-button>
              <a-popconfirm
                :title="pageText('pages.deleteThisPolicy')"
                :ok-text="pageText('pages.confirm')"
                :cancel-text="pageText('tasks.cancel')"
                @confirm="handleSchedulerSingleAction('delete', record._id)"
              >
                <a-button size="small" danger>{{ pageText('tasks.delete') }}</a-button>
              </a-popconfirm>
            </div>
          </template>
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">
          {{ pageText('tasks.paginationSummary', { pages: Math.ceil(schedulerPagination.total / schedulerPagination.pageSize) || 1, total: schedulerPagination.total }) }}
        </div>
        <a-pagination
          size="small"
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="schedulerPagination.current"
          v-model:pageSize="schedulerPagination.pageSize"
          :total="schedulerPagination.total"
          show-size-changer
          @change="handleSchedulerTableChange"
          @showSizeChange="handleSchedulerTableChange"
        />
      </div>
    </template>

    <!-- A3. 扫描任务记录列表 -->
    <template v-else-if="mainTab === 'dlp' && activeTabDlp === 'task'">
      <a-table
        :sticky="stickyConfig"
        :row-selection="{
          selectedRowKeys: taskSelectedRowKeys,
          onChange: onTaskSelectChange,
          preserveSelectedRowKeys: true
        }"
        :loading="taskLoading"
        :dataSource="taskData"
        :columns="taskColumns"
        :pagination="false"
        size="small"
        :rowKey="(record) => record._id"
      >
        <template #emptyText>
          <ArlEmpty :description="pageText('pages.noScanningTasks')" />
        </template>
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'name'">
            <a class="gh-primary-link" @click="openResultDrawer(record, 'task')">{{ record.name }}</a>
          </template>
          <template v-else-if="column.key === 'source_type'">
            <a-tag :color="record.source_type === 'scheduler' ? 'purple' : 'blue'">
              {{ record.source_type === 'scheduler' ? pageText('pages.githubSourceScheduler') : pageText('pages.githubSourceManual') }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'keyword'">
            <a-tag color="blue">{{ record.keyword }}</a-tag>
          </template>
          <template v-else-if="column.key === 'result_count'">
            <a-tooltip :title="pageText('pages.githubTaskResultCountTip')">
              <a-tag
                :color="(record.result_count || 0) > 0 ? 'geekblue' : 'default'"
                class="gh-clickable-tag"
                @click="openResultDrawer(record, 'task')"
              >
                {{ record.result_count || 0 }}
              </a-tag>
            </a-tooltip>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag :color="formatGithubStatusColor(record.status)">
              {{ formatTaskStatus(record.status) }}
            </a-tag>
          </template>
          <template v-else-if="column.key === 'action'">
            <div class="gh-row-actions">
              <a-button size="small" type="link" class="gh-link-btn" @click="openResultDrawer(record, 'task')">
                {{ pageText('pages.view') }}
              </a-button>
              <a-button size="small" type="primary" ghost @click="handleTaskRestart(record)">
                {{ pageText('tasks.restart') }}
              </a-button>
              <a-button
                size="small"
                :disabled="['done', 'stop', 'error'].includes(record.status)"
                @click="handleTaskSingleAction('stop', record._id)"
              >
                {{ pageText('tasks.stop') }}
              </a-button>
              <a-popconfirm
                :title="pageText('pages.deleteThisTask')"
                :ok-text="pageText('pages.confirm')"
                :cancel-text="pageText('tasks.cancel')"
                @confirm="handleTaskSingleAction('delete', record._id)"
              >
                <a-button size="small" danger>{{ pageText('tasks.delete') }}</a-button>
              </a-popconfirm>
            </div>
          </template>
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">
          {{ pageText('tasks.paginationSummary', { pages: Math.ceil(taskPagination.total / taskPagination.pageSize) || 1, total: taskPagination.total }) }}
        </div>
        <a-pagination
          size="small"
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="taskPagination.current"
          v-model:pageSize="taskPagination.pageSize"
          :total="taskPagination.total"
          show-size-changer
          @change="handleTaskTableChange"
          @showSizeChange="handleTaskTableChange"
        />
      </div>
    </template>

    <!-- B1. CVE 漏洞雷达列表 -->
    <template v-else-if="mainTab === 'ti' && activeTabTi === 'cve_history'">
      <a-table
        :sticky="stickyConfig"
        :row-selection="{
          selectedRowKeys: cveSelectedRowKeys,
          onChange: onCveSelectChange,
          preserveSelectedRowKeys: true
        }"
        :loading="cveLoading"
        :dataSource="pagedCveData"
        :columns="cveColumns"
        :pagination="false"
        size="small"
        rowKey="cve_name"
      >
        <template #emptyText>
          <ArlEmpty :description="pageText('pages.githubNoCveRecords')" />
        </template>
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'cve_name'">
            <div class="gh-cve-cell">
              <div class="gh-cve-title-row">
                <a :href="record.cve_url" target="_blank" rel="noopener noreferrer" class="gh-cve-link">
                  {{ record.cve_name }} <link-outlined />
                </a>
                <a-tag v-if="isTodayRecord(record.insert_time, record.pushed_at)" color="red">
                  {{ pageText('pages.githubTodayNewTag') }}
                </a-tag>
              </div>
              <div class="gh-cve-quick-ops">
                <a-button type="link" size="small" class="gh-mini-op" @click="copyString(record.cve_name)">
                  {{ pageText('pages.githubCopyCve') }}
                </a-button>
                <a-button type="link" size="small" class="gh-mini-op" @click="copyCloneForRepo(record.cve_url)">
                  git clone
                </a-button>
              </div>
            </div>
          </template>
          <template v-else-if="column.key === 'desc'">
            <a-typography-paragraph :ellipsis="{ rows: 2, expandable: true, symbol: pageText('pages.expand') }" class="page-flush-bottom">
              {{ record.desc }}
            </a-typography-paragraph>
          </template>
          <template v-else-if="column.key === 'action'">
            <div class="gh-row-actions">
              <a-button size="small" type="primary" ghost @click="goToNucleiSearch(record.cve_name)">
                {{ pageText('pages.githubCheckNuclei') }}
              </a-button>
              <a-popconfirm
                :title="pageText('tasks.confirmDeletionLabel')"
                :ok-text="pageText('pages.confirm')"
                :cancel-text="pageText('tasks.cancel')"
                @confirm="handleCveDelete(record.cve_name)"
              >
                <a-button size="small" danger>{{ pageText('tasks.delete') }}</a-button>
              </a-popconfirm>
            </div>
          </template>
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">
          {{ pageText('tasks.paginationSummary', { pages: Math.ceil(filteredCveData.length / cvePagination.pageSize) || 1, total: filteredCveData.length }) }}
        </div>
        <a-pagination
          size="small"
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="cvePagination.current"
          v-model:pageSize="cvePagination.pageSize"
          :total="filteredCveData.length"
          show-size-changer
          @change="onCveTableChange"
          @showSizeChange="onCveTableChange"
        />
      </div>
    </template>

    <!-- B2. 武器库追踪列表 -->
    <template v-else-if="mainTab === 'ti' && activeTabTi === 'tools_target'">
      <a-table
        :sticky="stickyConfig"
        :row-selection="{
          selectedRowKeys: toolsSelectedRowKeys,
          onChange: onToolsSelectChange,
          preserveSelectedRowKeys: true
        }"
        :loading="toolsLoading"
        :dataSource="pagedToolsData"
        :columns="toolsColumns"
        :pagination="false"
        size="small"
        rowKey="repo_url"
      >
        <template #emptyText>
          <ArlEmpty :description="pageText('pages.githubNoToolsMonitored')" />
        </template>
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'repo_url'">
            <div>
              <a :href="toGithubWebUrl(record.repo_url)" target="_blank" rel="noopener noreferrer" class="gh-primary-link">
                {{ extractRepoSlugFromApiUrl(record.repo_url) || record.repo_url }} <link-outlined />
              </a>
              <div v-if="record.release_name" class="gh-sub-caption">{{ record.release_name }}</div>
            </div>
          </template>
          <template v-else-if="column.key === 'last_tag'">
            <a
              v-if="record.last_tag && record.release_url"
              :href="record.release_url"
              target="_blank"
              rel="noopener noreferrer"
            >
              <a-tag color="cyan">{{ record.last_tag }} <link-outlined /></a-tag>
            </a>
            <a-tag v-else-if="record.last_tag" color="cyan">{{ record.last_tag }}</a-tag>
            <span v-else class="page-placeholder">{{ pageText('pages.noVersionAvailable') }}</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <div class="gh-row-actions">
              <a-button size="small" @click="openToolNotesDrawer(record)">
                {{ pageText('pages.githubToolReleaseNotes') }}
              </a-button>
              <a
                v-if="record.release_url"
                :href="record.release_url"
                target="_blank"
                rel="noopener noreferrer"
              >
                <a-button size="small" type="primary" ghost>{{ pageText('pages.githubToolReleasePage') }}</a-button>
              </a>
              <a-popconfirm
                :title="pageText('pages.stopMonitoringThisTool')"
                :ok-text="pageText('pages.confirm')"
                :cancel-text="pageText('tasks.cancel')"
                @confirm="handleToolDelete(record.repo_url)"
              >
                <a-button size="small" danger>{{ pageText('tasks.delete') }}</a-button>
              </a-popconfirm>
            </div>
          </template>
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">
          {{ pageText('tasks.paginationSummary', { pages: Math.ceil(filteredToolsData.length / toolsPagination.pageSize) || 1, total: filteredToolsData.length }) }}
        </div>
        <a-pagination
          size="small"
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="toolsPagination.current"
          v-model:pageSize="toolsPagination.pageSize"
          :total="filteredToolsData.length"
          show-size-changer
          @change="onToolsTableChange"
          @showSizeChange="onToolsTableChange"
        />
      </div>
    </template>

    <!-- B3. 安全研究员动态列表 -->
    <template v-else-if="mainTab === 'ti' && activeTabTi === 'hackers_target'">
      <a-table
        :sticky="stickyConfig"
        :row-selection="{
          selectedRowKeys: hackersSelectedRowKeys,
          onChange: onHackersSelectChange,
          preserveSelectedRowKeys: true
        }"
        :loading="hackersLoading"
        :dataSource="pagedHackersData"
        :columns="hackersColumns"
        :pagination="false"
        size="small"
        rowKey="github_id"
      >
        <template #emptyText>
          <ArlEmpty :description="pageText('pages.noResearchersMonitored')" />
        </template>
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'github_id'">
            <div class="gh-researcher-cell">
              <a-avatar :src="`https://github.com/${(record.github_id || '').trim()}.png`" size="default" />
              <a
                :href="`https://github.com/${(record.github_id || '').trim()}`"
                target="_blank"
                rel="noopener noreferrer"
                class="gh-primary-link"
              >
                {{ record.github_id }} <link-outlined />
              </a>
            </div>
          </template>
          <template v-else-if="column.key === 'found_count'">
            <a-tooltip :title="pageText('pages.githubDrawerClickFoundTip')">
              <a-tag
                :color="(record.found_count || 0) > 0 ? 'green' : 'default'"
                class="gh-clickable-tag"
                @click="openHackersHistoryDrawer(record.github_id)"
              >
                {{ record.found_count || 0 }}
              </a-tag>
            </a-tooltip>
          </template>
          <template v-else-if="column.key === 'action'">
            <div class="gh-row-actions">
              <a-button size="small" @click="openHackersHistoryDrawer(record.github_id)">
                {{ pageText('pages.view') }}
              </a-button>
              <a :href="`https://github.com/${record.github_id}`" target="_blank" rel="noopener noreferrer">
                <a-button size="small" type="primary" ghost>{{ pageText('pages.profile') }}</a-button>
              </a>
              <a-popconfirm
                :title="pageText('pages.stopMonitoring')"
                :ok-text="pageText('pages.confirm')"
                :cancel-text="pageText('tasks.cancel')"
                @confirm="handleHackerDelete(record.github_id)"
              >
                <a-button size="small" danger>{{ pageText('tasks.delete') }}</a-button>
              </a-popconfirm>
            </div>
          </template>
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">
          {{ pageText('tasks.paginationSummary', { pages: Math.ceil(filteredHackersData.length / hackersPagination.pageSize) || 1, total: filteredHackersData.length }) }}
        </div>
        <a-pagination
          size="small"
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="hackersPagination.current"
          v-model:pageSize="hackersPagination.pageSize"
          :total="filteredHackersData.length"
          show-size-changer
          @change="onHackersTableChange"
          @showSizeChange="onHackersTableChange"
        />
      </div>
    </template>

    <!-- ================= 底部悬浮批量操作条 (.arl-floating-action-bar) ================= -->
    <transition name="floating-slide">
      <div v-if="activeSelectedKeys.length > 0" class="arl-floating-action-bar">
        <div class="floating-info">
          <a-tag color="blue">{{ pageText('pages.githubSelectedCount', { count: activeSelectedKeys.length }) }}</a-tag>
          <a-button type="link" size="small" @click="clearActiveSelection">
            {{ pageText('pages.githubClearSelection') }}
          </a-button>
        </div>

        <div class="floating-actions">
          <template v-if="mainTab === 'dlp' && activeTabDlp === 'findings'">
            <template v-if="findingsGroupMode === 'flat'">
              <a-button size="small" type="primary" @click="updateTriageStatus(findingsSelectedRowKeys, 'confirmed')">
                {{ pageText('pages.githubMarkConfirmed') }}
              </a-button>
              <a-button size="small" @click="updateTriageStatus(findingsSelectedRowKeys, 'false_positive')">
                {{ pageText('pages.githubMarkFalsePositive') }}
              </a-button>
              <a-button size="small" @click="updateTriageStatus(findingsSelectedRowKeys, 'pending')">
                {{ pageText('pages.githubMarkPending') }}
              </a-button>
            </template>
            <a-button size="small" danger @click="confirmBatchIgnoreSelectedRepos">
              {{ pageText('pages.githubBatchIgnoreRepos') }}
            </a-button>
          </template>

          <template v-else-if="mainTab === 'dlp' && activeTabDlp === 'scheduler'">
            <a-button size="small" type="primary" @click="handleSchedulerRunNow(schedulerSelectedRowKeys)">
              {{ pageText('pages.githubRunSelected') }}
            </a-button>
            <a-button size="small" @click="confirmSchedulerBatchAction('stop')">
              {{ pageText('tasks.stopSelected') }}
            </a-button>
            <a-button size="small" danger @click="confirmSchedulerBatchAction('delete')">
              {{ pageText('tasks.deleteSelected') }}
            </a-button>
          </template>

          <template v-else-if="mainTab === 'dlp' && activeTabDlp === 'task'">
            <a-button size="small" @click="confirmTaskBatchAction('stop')">
              {{ pageText('tasks.stopSelected') }}
            </a-button>
            <a-button size="small" danger @click="confirmTaskBatchAction('delete')">
              {{ pageText('tasks.deleteSelected') }}
            </a-button>
          </template>

          <template v-else-if="mainTab === 'ti' && activeTabTi === 'cve_history'">
            <a-button size="small" danger @click="confirmThreatBatchDelete('cve')">
              {{ pageText('tasks.deleteSelected') }}
            </a-button>
          </template>

          <template v-else-if="mainTab === 'ti' && activeTabTi === 'tools_target'">
            <a-button size="small" danger @click="confirmThreatBatchDelete('tools')">
              {{ pageText('tasks.deleteSelected') }}
            </a-button>
          </template>

          <template v-else-if="mainTab === 'ti' && activeTabTi === 'hackers_target'">
            <a-button size="small" danger @click="confirmThreatBatchDelete('hackers')">
              {{ pageText('tasks.deleteSelected') }}
            </a-button>
          </template>
        </div>
      </div>
    </transition>

    <!-- ================= 抽屉 1: 泄露命中详情与研判备注 ================= -->
    <a-drawer
      :title="pageText('pages.githubFindingDetailTitle')"
      placement="right"
      :width="760"
      :open="findingDetailDrawerVisible"
      @close="findingDetailDrawerVisible = false"
    >
      <template v-if="findingDetailRecord">
        <div class="gh-drawer-summary-bar">
          <div class="gh-repo-line">
            <a
              :href="`https://github.com/${findingDetailRecord.repo_full_name}`"
              target="_blank"
              rel="noopener noreferrer"
              class="gh-repo-link"
            >
              {{ findingDetailRecord.repo_full_name }} <link-outlined />
            </a>
            <a-tag color="blue">{{ findingDetailRecord.keyword }}</a-tag>
            <a-tag :color="triageStatusColor(findingDetailRecord.triage_status)">
              {{ triageStatusLabel(findingDetailRecord.triage_status) }}
            </a-tag>
          </div>
          <div class="gh-drawer-submeta">
            <a
              :href="findingDetailRecord.html_url || `https://github.com/${findingDetailRecord.repo_full_name}/blob/HEAD/${findingDetailRecord.path}`"
              target="_blank"
              rel="noopener noreferrer"
              class="gh-path-link"
            >
              {{ findingDetailRecord.path }}
            </a>
            <span class="gh-time-text">{{ findingDetailRecord.commit_date || findingDetailRecord.insert_time || '-' }}</span>
          </div>
        </div>

        <GithubCodeReader
          :content="findingDetailRecord.human_content"
          :keyword="findingDetailRecord.keyword"
          :html-url="findingDetailRecord.html_url"
          :repo-full-name="findingDetailRecord.repo_full_name"
          max-height="380px"
          :expandable="false"
        />

        <div class="gh-triage-editor">
          <div class="gh-editor-row">
            <span class="gh-editor-label">{{ pageText('pages.githubColTriageStatus') }}</span>
            <a-radio-group v-model:value="findingDetailForm.triage_status" button-style="solid" size="small">
              <a-radio-button value="pending">{{ pageText('pages.githubTriagePending') }}</a-radio-button>
              <a-radio-button value="confirmed">{{ pageText('pages.githubTriageConfirmed') }}</a-radio-button>
              <a-radio-button value="false_positive">{{ pageText('pages.githubTriageFalsePositive') }}</a-radio-button>
            </a-radio-group>
          </div>
          <div class="gh-editor-row-col">
            <span class="gh-editor-label">{{ pageText('pages.githubTriageNoteLabel') }}</span>
            <a-textarea
              v-model:value="findingDetailForm.note"
              :rows="3"
              :placeholder="pageText('pages.githubTriageNotePlaceholder')"
            />
          </div>
          <div class="gh-editor-actions">
            <a-button type="primary" size="small" :loading="findingDetailSaving" @click="saveFindingDetailTriage">
              {{ pageText('pages.githubSaveTriageNote') }}
            </a-button>
          </div>
        </div>
      </template>
    </a-drawer>

    <!-- ================= 抽屉 2: 已屏蔽仓库管理 ================= -->
    <a-drawer
      :title="pageText('pages.githubIgnoredReposTitle')"
      placement="right"
      :width="620"
      :open="ignoredDrawerVisible"
      @close="ignoredDrawerVisible = false"
    >
      <div class="gh-ignored-add-row">
        <a-input
          v-model:value="newIgnoredRepoInput"
          :placeholder="pageText('pages.githubAddIgnoredRepoPlaceholder')"
          size="small"
          allowClear
          @pressEnter="submitNewIgnoredRepo"
        />
        <a-button type="primary" size="small" @click="submitNewIgnoredRepo">
          {{ pageText('pages.confirm') }}
        </a-button>
      </div>

      <a-table
        :loading="ignoredLoading"
        :dataSource="ignoredReposList"
        :columns="ignoredRepoColumns"
        :pagination="false"
        size="small"
        rowKey="repo_full_name"
      >
        <template #emptyText>
          <ArlEmpty :description="pageText('pages.githubIgnoredReposEmpty')" compact />
        </template>
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'repo_full_name'">
            <a :href="`https://github.com/${record.repo_full_name}`" target="_blank" rel="noopener noreferrer" class="gh-primary-link">
              {{ record.repo_full_name }} <link-outlined />
            </a>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button size="small" @click="handleIgnoreRepos('remove', [record.repo_full_name])">
              {{ pageText('pages.githubUnignoreRepo') }}
            </a-button>
          </template>
        </template>
      </a-table>
    </a-drawer>

    <!-- ================= 抽屉 3: 研究员发现记录抽屉 ================= -->
    <a-drawer
      :title="pageText('pages.toolsDiscoveredFromTrackedResearchers')"
      placement="right"
      :width="760"
      :open="historyDrawerVisible"
      @close="closeHackersHistoryDrawer"
    >
      <div class="gh-drawer-filter-row">
        <div class="arl-filter-item">
          <span class="arl-filter-label">{{ pageText('pages.githubDrawerResearcherFilter') }}</span>
          <a-select
            v-model:value="historyFilter.github_id"
            size="small"
            class="gh-width-170"
            @change="fetchHackersHistory"
          >
            <a-select-option value="">{{ pageText('pages.githubAllResearchersOption') }}</a-select-option>
            <a-select-option v-for="h in hackersData" :key="h.github_id" :value="h.github_id">
              {{ h.github_id }}
            </a-select-option>
          </a-select>
        </div>

        <a-input
          v-model:value="historyFilter.q"
          :placeholder="pageText('pages.githubDrawerRepoSearchPlaceholder')"
          size="small"
          class="gh-width-220"
          allowClear
          @pressEnter="fetchHackersHistory"
        >
          <template #suffix><search-outlined class="gh-input-icon" @click="fetchHackersHistory" /></template>
        </a-input>
      </div>

      <a-table
        :loading="historyLoading"
        :dataSource="hackersHistoryData"
        :columns="historyColumns"
        :pagination="{ pageSize: globalPageSize, showSizeChanger: true, pageSizeOptions: $pageSizeOptions, size: 'small' }"
        size="small"
        rowKey="full_name"
      >
        <template #emptyText>
          <ArlEmpty :description="pageText('tasks.noData')" compact />
        </template>
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'full_name'">
            <div>
              <a
                :href="record.html_url || `https://github.com/${record.full_name}`"
                target="_blank"
                rel="noopener noreferrer"
                class="gh-primary-link"
              >
                {{ record.full_name }} <link-outlined />
              </a>
              <div v-if="record.description" class="gh-sub-caption">{{ record.description }}</div>
            </div>
          </template>
          <template v-else-if="column.key === 'meta'">
            <div class="gh-meta-stack">
              <a-tag v-if="record.language" color="geekblue">{{ record.language }}</a-tag>
              <span v-if="record.stargazers_count !== undefined" class="gh-time-text">★ {{ record.stargazers_count }}</span>
            </div>
          </template>
          <template v-else-if="column.key === 'insert_time'">
            <span class="gh-time-text">{{ record.created_at || record.insert_time }}</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button size="small" @click="copyCloneForRepo(record.full_name)">git clone</a-button>
          </template>
        </template>
      </a-table>
    </a-drawer>

    <!-- ================= 抽屉 4: 工具更新日志预览抽屉 ================= -->
    <a-drawer
      :title="pageText('pages.githubToolReleaseDrawerTitle', { name: extractRepoSlugFromApiUrl(toolNotesRecord?.repo_url) || '' })"
      placement="right"
      :width="640"
      :open="toolNotesDrawerVisible"
      @close="toolNotesDrawerVisible = false"
    >
      <template v-if="toolNotesRecord">
        <div class="gh-drawer-summary-bar">
          <div class="gh-repo-line">
            <a-tag color="cyan">{{ toolNotesRecord.last_tag || pageText('pages.noVersionAvailable') }}</a-tag>
            <span class="gh-time-text">{{ toolNotesRecord.last_commit_time || '-' }}</span>
          </div>
          <a
            v-if="toolNotesRecord.release_url"
            :href="toolNotesRecord.release_url"
            target="_blank"
            rel="noopener noreferrer"
          >
            <a-button size="small" type="primary" ghost>{{ pageText('pages.githubToolReleasePage') }}</a-button>
          </a>
        </div>
        <pre v-if="toolNotesRecord.release_notes" class="gh-release-notes-box">{{ toolNotesRecord.release_notes }}</pre>
        <ArlEmpty v-else :description="pageText('pages.githubToolNoReleaseNotes')" compact />
      </template>
    </a-drawer>

    <!-- ================= 抽屉 5: 单次任务 / 策略详情抽屉 ================= -->
    <a-drawer
      :title="resultDrawerTitle"
      placement="right"
      :width="960"
      :open="resultDrawerVisible"
      @close="closeResultDrawer"
    >
      <div class="gh-drawer-summary-bar">
        <div class="gh-repo-line">
          <a-tag :color="resultDrawerType === 'task' ? 'blue' : 'purple'">
            {{ resultDrawerType === 'task' ? pageText('pages.oneTimeScanningTasks') : pageText('pages.recurringMonitoringPolicy') }}
          </a-tag>
          <span class="gh-drawer-title-name">{{ resultCurrentRecord?.name }}</span>
          <span class="page-summary-caption">{{ pageText('pages.keyword') }} {{ resultCurrentRecord?.keyword }}</span>
        </div>
        <div class="gh-row-actions">
          <a-button size="small" @click="jumpToFindingsFromDrawer">
            {{ pageText('pages.githubViewInOverview') }}
          </a-button>
          <a-button type="dashed" size="small" :loading="resultLoading" @click="fetchResultData">
            <template #icon><sync-outlined /></template> {{ pageText('tasks.refresh') }}
          </a-button>
        </div>
      </div>

      <a-tabs v-model:activeKey="resultActiveTab" type="card" class="arl-detail-tabs">
        <a-tab-pane key="result" :tab="pageText('pages.codeLeakFindings')">
          <div class="gh-drawer-filter-row">
            <a-input
              size="small"
              v-model:value="resultSearchForm.repo_full_name"
              :placeholder="pageText('pages.repositoryEGUserRepo')"
              class="page-width-180"
              allowClear
              @pressEnter="onResultSearch"
            />
            <a-input
              size="small"
              v-model:value="resultSearchForm.path"
              :placeholder="pageText('pages.filePathEGConfigPy')"
              class="page-width-180"
              allowClear
              @pressEnter="onResultSearch"
            />
            <a-input
              size="small"
              v-model:value="resultSearchForm.human_content"
              :placeholder="pageText('pages.keywordInCode')"
              class="page-width-180"
              allowClear
              @pressEnter="onResultSearch"
            />
            <a-button size="small" @click="resetResultSearch">{{ pageText('assets.reset') }}</a-button>
          </div>

          <a-table
            :loading="resultLoading"
            :dataSource="resultDataSource"
            :columns="resultColumns"
            :pagination="false"
            size="small"
            rowKey="_id"
          >
            <template #emptyText>
              <ArlEmpty :description="pageText('pages.noCodeLeakFindings')" />
            </template>
            <template #bodyCell="{ column, record }">
              <template v-if="column.key === 'repo_full_name'">
                <a :href="`https://github.com/${record.repo_full_name}`" target="_blank" rel="noopener noreferrer" class="gh-primary-link">
                  {{ record.repo_full_name }} <link-outlined />
                </a>
                <div class="gh-drawer-triage-inline">
                  <a-tag :color="triageStatusColor(record.triage_status)">
                    {{ triageStatusLabel(record.triage_status) }}
                  </a-tag>
                  <a-button size="small" type="link" @click="updateTriageStatus([record.hash_md5], 'confirmed')">
                    {{ pageText('pages.githubMarkConfirmed') }}
                  </a-button>
                  <a-button size="small" type="link" @click="updateTriageStatus([record.hash_md5], 'false_positive')">
                    {{ pageText('pages.githubMarkFalsePositive') }}
                  </a-button>
                </div>
              </template>
              <template v-else-if="column.key === 'path'">
                <a
                  :href="record.html_url || `https://github.com/${record.repo_full_name}/blob/HEAD/${record.path}`"
                  target="_blank"
                  rel="noopener noreferrer"
                  style="word-break: break-all;"
                >
                  {{ record.path }}
                </a>
              </template>
              <template v-else-if="column.key === 'human_content'">
                <GithubCodeReader
                  :content="record.human_content"
                  :keyword="record.keyword"
                  :html-url="record.html_url"
                  :repo-full-name="record.repo_full_name"
                  max-height="200px"
                  compact
                  @expand="openFindingDetailDrawer(record)"
                />
              </template>
              <template v-else-if="column.key === 'keyword'">
                <a-tag color="blue">{{ record.keyword }}</a-tag>
              </template>
              <template v-else-if="column.key === 'commit_date'">
                <span class="gh-time-text">{{ record.commit_date || record.insert_time || '-' }}</span>
              </template>
            </template>
          </a-table>

          <div class="arl-pagination-bar">
            <div class="pagination-info">
              {{ pageText('tasks.paginationSummary', { pages: Math.ceil(resultPagination.total / resultPagination.pageSize) || 1, total: resultPagination.total }) }}
            </div>
            <a-pagination
              size="small"
              :pageSizeOptions="$pageSizeOptions"
              v-model:current="resultPagination.current"
              v-model:pageSize="resultPagination.pageSize"
              :total="resultPagination.total"
              show-size-changer
              @change="handleResultTableChange"
              @showSizeChange="handleResultTableChange"
            />
          </div>
        </a-tab-pane>

        <a-tab-pane v-if="resultDrawerType === 'task'" key="log" :tab="pageText('pages.taskLogs')">
          <div ref="resultTerminalContainer" class="arl-mono-terminal gh-log-terminal">
            <div v-for="(log, idx) in resultLogDataSource" :key="log._id || idx" class="gh-log-line">
              <span class="gh-log-time">[{{ log.create_time }}]</span>
              <span :class="`gh-log-level is-${log.level || 'info'}`">[{{ (log.level || 'info').toUpperCase() }}]</span>
              <span v-if="log.title" class="gh-log-title">[{{ log.title }}]</span>
              <span>{{ log.message }}</span>
            </div>
            <div v-if="resultLogDataSource.length === 0 && !resultLogLoading" class="page-log-empty">{{ pageText('pages.systemNoLogsYet') }}</div>
            <div v-if="resultLogLoading" class="page-log-empty">{{ pageText('tasks.systemLoadingLogs') }}</div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-drawer>

    <!-- ================= 弹窗 1: 监控策略弹窗 (新增/修改 + Dork 预设 + Cron 预设) ================= -->
    <a-modal
      v-model:open="schedulerModalVisible"
      :title="schedulerIsEdit ? pageText('pages.editPolicy') : pageText('pages.addPolicy')"
      @ok="submitSchedulerModal"
      :confirmLoading="schedulerSubmitLoading"
      width="620px"
      :okText="pageText('pages.confirm')"
      :cancelText="pageText('tasks.cancel')"
      destroyOnClose
      wrapClassName="arl-theme-modal"
    >
      <a-form :label-wrap="true" :model="schedulerForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" class="page-modal-form">
        <a-form-item :label="pageText('tasks.policyName')" required>
          <a-input v-model:value="schedulerForm.name" :placeholder="pageText('pages.enterAPolicyNameLabel2')" />
        </a-form-item>

        <a-form-item :label="pageText('pages.keywordLabel2')" required>
          <a-input v-model:value="schedulerForm.keyword" :placeholder="pageText('pages.enterAKeyword')" />
          <div class="gh-preset-block">
            <div class="gh-preset-label">{{ pageText('pages.githubDorkPresetsLabel') }}</div>
            <div class="gh-preset-chips">
              <a-tag
                v-for="preset in dorkPresetsList"
                :key="preset.id"
                color="blue"
                class="gh-clickable-tag"
                @click="schedulerForm.keyword = applyDorkPresetHelper(schedulerForm.keyword, preset)"
              >
                + {{ pageText(preset.labelKey) }}
              </a-tag>
            </div>
          </div>
        </a-form-item>

        <a-form-item :label="pageText('pages.cronExpression')" required>
          <a-input v-model:value="schedulerForm.cron" :placeholder="pageText('pages.enterACronExpressionEG30')" />
          <div class="gh-preset-block">
            <div class="gh-preset-label">{{ pageText('pages.githubCronPresetsLabel') }}</div>
            <div class="gh-preset-chips">
              <a-tag
                v-for="cp in cronPresetsList"
                :key="cp.cron"
                class="gh-clickable-tag"
                @click="schedulerForm.cron = cp.cron"
              >
                {{ pageText(cp.labelKey) }} ({{ cp.cron }})
              </a-tag>
            </div>
          </div>
        </a-form-item>

        <a-alert type="info" show-icon class="gh-builtin-info">
          <template #message>{{ pageText('pages.githubBuiltinSuffixNoticeTitle') }}</template>
          <template #description>
            <div>{{ pageText('pages.githubBuiltinSuffixNoticeDesc') }}</div>
            <ul class="gh-bucket-list">
              <li v-for="bucket in builtinBucketsList" :key="bucket">{{ bucket }}</li>
            </ul>
          </template>
        </a-alert>
      </a-form>
    </a-modal>

    <!-- ================= 弹窗 2: 单次扫描弹窗 (Dork 预设 + 后缀说明) ================= -->
    <a-modal
      v-model:open="taskModalVisible"
      :title="pageText('pages.newOneTimeScan')"
      @ok="submitTaskModal"
      :confirmLoading="taskSubmitLoading"
      width="620px"
      :okText="pageText('pages.confirm')"
      :cancelText="pageText('tasks.cancel')"
      destroyOnClose
      wrapClassName="arl-theme-modal"
    >
      <a-form :label-wrap="true" :model="taskForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" class="page-modal-form">
        <a-form-item :label="pageText('assets.taskName')" required>
          <a-input v-model:value="taskForm.name" :placeholder="pageText('tasks.enterATaskName')" />
        </a-form-item>

        <a-form-item :label="pageText('pages.keywordLabel2')" required>
          <a-input v-model:value="taskForm.keyword" :placeholder="pageText('pages.enterAKeyword')" />
          <div class="gh-preset-block">
            <div class="gh-preset-label">{{ pageText('pages.githubDorkPresetsLabel') }}</div>
            <div class="gh-preset-chips">
              <a-tag
                v-for="preset in dorkPresetsList"
                :key="preset.id"
                color="blue"
                class="gh-clickable-tag"
                @click="taskForm.keyword = applyDorkPresetHelper(taskForm.keyword, preset)"
              >
                + {{ pageText(preset.labelKey) }}
              </a-tag>
            </div>
          </div>
        </a-form-item>

        <a-alert type="info" show-icon class="gh-builtin-info">
          <template #message>{{ pageText('pages.githubBuiltinSuffixNoticeTitle') }}</template>
          <template #description>
            <div>{{ pageText('pages.githubBuiltinSuffixNoticeDesc') }}</div>
            <ul class="gh-bucket-list">
              <li v-for="bucket in builtinBucketsList" :key="bucket">{{ bucket }}</li>
            </ul>
          </template>
        </a-alert>
      </a-form>
    </a-modal>

    <!-- ================= 弹窗 3: 工具监控新增 (批量 + 常用安全工具包) ================= -->
    <a-modal
      v-model:open="toolModalVisible"
      :title="pageText('pages.monitorATool')"
      @ok="submitToolModal"
      :confirmLoading="toolSubmitLoading"
      width="580px"
      :okText="pageText('pages.confirm')"
      :cancelText="pageText('tasks.cancel')"
      destroyOnClose
      wrapClassName="arl-theme-modal"
    >
      <a-form :label-wrap="true" :model="toolForm" layout="vertical" class="page-modal-form">
        <a-form-item :label="pageText('pages.repositoryUrl')" required :extra="pageText('pages.githubAddToolsBatchHint')">
          <a-textarea
            v-model:value="toolForm.repo_url"
            :rows="4"
            :placeholder="pageText('pages.githubToolsBatchPlaceholder')"
          />
        </a-form-item>
        <div class="gh-preset-block">
          <div class="gh-preset-label">{{ pageText('pages.githubPresetToolsLabel') }}</div>
          <div class="gh-preset-chips">
            <a-tag
              v-for="tool in redteamToolPresetsList"
              :key="tool.repo"
              color="cyan"
              class="gh-clickable-tag"
              @click="appendToolPreset(tool.repo)"
            >
              + {{ tool.repo }}
            </a-tag>
          </div>
        </div>
      </a-form>
    </a-modal>

    <!-- ================= 弹窗 4: 研究员监控新增 (支持批量) ================= -->
    <a-modal
      v-model:open="hackerModalVisible"
      :title="pageText('pages.monitorAResearcher')"
      @ok="submitHackerModal"
      :confirmLoading="hackerSubmitLoading"
      width="540px"
      :okText="pageText('pages.confirm')"
      :cancelText="pageText('tasks.cancel')"
      destroyOnClose
      wrapClassName="arl-theme-modal"
    >
      <a-form :label-wrap="true" :model="hackerForm" layout="vertical" class="page-modal-form">
        <a-form-item label="GitHub ID" required :extra="pageText('pages.githubAddHackersHint')">
          <a-textarea
            v-model:value="hackerForm.github_id"
            :rows="4"
            :placeholder="pageText('pages.githubHackersBatchPlaceholder')"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';
defineOptions({ name: 'GithubManage' });
import { ref, reactive, onMounted, onActivated, onDeactivated, onUnmounted, computed, watch, nextTick, createVNode } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import request from '../utils/request';
import { message, Modal } from 'ant-design-vue';
import {
  SearchOutlined,
  SyncOutlined,
  LinkOutlined,
  ClockCircleOutlined,
  GithubOutlined,
  SafetyOutlined,
  RadarChartOutlined,
  KeyOutlined,
  ReloadOutlined,
  PlusOutlined,
  ThunderboltOutlined,
  UndoOutlined,
  DownloadOutlined,
  DownOutlined,
  EyeInvisibleOutlined,
  EyeOutlined,
  CheckOutlined,
  CloseOutlined,
  CopyOutlined,
  HistoryOutlined,
  ExclamationCircleOutlined,
} from '@ant-design/icons-vue';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import { useSticky } from '../utils/useSticky';
import { TASK_STATUS_LABEL, formatTaskStatus, formatTaskStatusColor, isGithubStageStatus } from '../constants/taskStatus';
import { copyText } from '../utils/clipboard';
import GithubCodeReader from '../components/github/GithubCodeReader.vue';
import {
  GITHUB_BUILTIN_BUCKETS,
  GITHUB_DORK_PRESETS,
  GITHUB_CRON_PRESETS,
  REDTEAM_TOOL_PRESETS,
  applyDorkPreset,
  parseMultilineList,
  extractRepoSlugFromApiUrl,
  toGithubWebUrl,
  buildGitCloneCmd,
} from '../utils/githubHelpers';

const { t: pageText } = useI18n({ useScope: 'global' });
const router = useRouter();
const route = useRoute();
const globalPageSize = useGlobalPageSize(10);

const actionBarRef = ref(null);
const { stickyConfig } = typeof useSticky === 'function' ? useSticky(actionBarRef) : { stickyConfig: computed(() => false) };

const dorkPresetsList = computed(() => GITHUB_DORK_PRESETS);
const cronPresetsList = computed(() => GITHUB_CRON_PRESETS);
const builtinBucketsList = computed(() => GITHUB_BUILTIN_BUCKETS);
const redteamToolPresetsList = computed(() => REDTEAM_TOOL_PRESETS);

const applyDorkPresetHelper = (current, preset) => applyDorkPreset(current, preset);

const goToGithubTokenConfig = () => {
  router.push({ path: '/systemSettings', query: { tab: 'api_config', focus: 'github_token' } });
};

const goToNucleiSearch = (cveName) => {
  router.push({ path: '/pocList', query: { tab: 'nuclei', search: cveName } });
};

// ==========================================
// 顶层双域切换 & 路由同步
// ==========================================
const mainTab = ref('dlp');
const activeTabDlp = ref('findings');
const activeTabTi = ref('cve_history');
const autoPollEnabled = ref(true);
const isRefreshingActive = ref(false);

const applyRouteTabQuery = (tabVal) => {
  if (!tabVal) return;
  if (['findings', 'scheduler', 'task'].includes(tabVal)) {
    mainTab.value = 'dlp';
    activeTabDlp.value = tabVal;
  } else if (['cve_history', 'tools_target', 'hackers_target'].includes(tabVal)) {
    mainTab.value = 'ti';
    activeTabTi.value = tabVal;
  }
};

const switchMainTab = (tab) => {
  mainTab.value = tab;
};

// ==========================================
// Token 与双维度限流状态
// ==========================================
const tokenChecking = ref(false);
const tokenStatus = reactive({
  status: '',
  msg: '',
  core: { remaining: 0, limit: 0 },
  search: { remaining: 0, limit: 0 },
});

const fetchTokenStatus = async () => {
  tokenChecking.value = true;
  try {
    const res = await request.get('/github_threat/token_status');
    if (res.code === 200 && res.data) {
      tokenStatus.status = res.data.status || '';
      tokenStatus.msg = res.data.msg || '';
      tokenStatus.core = res.data.core || { remaining: 0, limit: 0 };
      tokenStatus.search = res.data.search || { remaining: 0, limit: 0 };
    }
  } catch (error) {
    console.error(error);
  } finally {
    tokenChecking.value = false;
  }
};

const tokenTagColor = computed(() => {
  if (tokenStatus.status === 'valid') return 'success';
  if (tokenStatus.status === 'rate_limited') return 'warning';
  if (['missing', 'invalid', 'error'].includes(tokenStatus.status)) return 'error';
  return 'default';
});

const tokenPillLabel = computed(() => {
  if (!tokenStatus.status) return pageText('pages.githubTokenChecking');
  if (tokenStatus.status === 'valid') {
    return pageText('pages.githubTokenHealthyPill', {
      core: tokenStatus.core?.remaining ?? 0,
      search: tokenStatus.search?.remaining ?? 0,
    });
  }
  if (tokenStatus.status === 'rate_limited') {
    return pageText('pages.githubTokenRateLimitedPill', {
      search: tokenStatus.search?.remaining ?? 0,
      limit: tokenStatus.search?.limit ?? 30,
    });
  }
  if (tokenStatus.status === 'missing') return pageText('pages.githubTokenMissingPill');
  if (tokenStatus.status === 'invalid') return pageText('pages.githubTokenInvalidPill');
  return pageText('pages.githubTokenErrorPill');
});

const tokenTooltipText = computed(() => pageText('pages.githubTokenQuotaTooltip', {
  core: tokenStatus.core?.remaining ?? 0,
  coreLimit: tokenStatus.core?.limit ?? 5000,
  search: tokenStatus.search?.remaining ?? 0,
  searchLimit: tokenStatus.search?.limit ?? 30,
}));

const showTokenWarningAlert = computed(() =>
  ['missing', 'invalid', 'error', 'rate_limited'].includes(tokenStatus.status)
);

// ==========================================
// 通用工具：复制、状态格式化、批量确认框
// ==========================================
const copyString = async (text) => {
  if (!text) return;
  try {
    await copyText(text);
    message.success(pageText('pages.copiedToClipboard'));
  } catch {
    message.error(pageText('pages.requestFailed'));
  }
};

const copyCloneForRepo = (repoOrUrl) => {
  const cmd = buildGitCloneCmd(repoOrUrl);
  if (cmd) copyString(cmd);
};

const formatGithubStatusColor = (status) => {
  if (isGithubStageStatus(status)) return 'processing';
  return formatTaskStatusColor(status);
};

const triageStatusColor = (st) => {
  if (st === 'confirmed') return 'error';
  if (st === 'false_positive') return 'default';
  return 'warning';
};

const triageStatusLabel = (st) => {
  if (st === 'confirmed') return pageText('pages.githubTriageConfirmed');
  if (st === 'false_positive') return pageText('pages.githubTriageFalsePositive');
  return pageText('pages.githubTriagePending');
};

const isTodayRecord = (...dateStrs) => {
  const now = new Date();
  const today = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  return dateStrs.some(s => typeof s === 'string' && s.startsWith(today));
};

const confirmBatchItems = ({ actionLabel, items, danger = false, onOk }) => {
  const preview = items.slice(0, 8);
  const remain = items.length - preview.length;
  Modal.confirm({
    title: pageText('pages.githubConfirmBatchTitle', { count: items.length }),
    icon: createVNode(ExclamationCircleOutlined),
    okText: pageText('pages.confirm'),
    cancelText: pageText('tasks.cancel'),
    okButtonProps: { danger },
    content: createVNode('div', null, [
      createVNode('p', { style: 'margin-bottom: 8px;' }, pageText('pages.githubConfirmBatchSummary', { action: actionLabel })),
      createVNode(
        'ul',
        { style: 'max-height: 180px; overflow-y: auto; padding-left: 18px; margin: 0;' },
        [
          ...preview.map(label => createVNode('li', { style: 'word-break: break-all;' }, label)),
          ...(remain > 0 ? [createVNode('li', { style: 'opacity: 0.7;' }, pageText('pages.githubConfirmBatchMore', { count: remain }))] : []),
        ]
      ),
    ]),
    onOk,
  });
};

// ==========================================
// 模块 0: 泄露命中总览 (Triage Inbox)
// ==========================================
const findingsLoading = ref(false);
const findingsExportLoading = ref(false);
const findingsData = ref([]);
const findingsRepoData = ref([]);
const findingsGroupMode = ref('flat');
const findingsQuickFilter = ref('all');
const findingsSourceLabel = ref('');
const findingsStats = reactive({
  pending: 0,
  confirmed: 0,
  false_positive: 0,
  total: 0,
  ignored_repos: 0,
  running_tasks: 0,
  running_schedulers: 0,
});
const findingsSearchForm = reactive({
  source_type: 'all',
  github_task_id: '',
  github_scheduler_id: '',
  repo_full_name: '',
  path: '',
  human_content: '',
  keyword: '',
  triage_status: '',
  only_ignored: false,
});
const findingsPager = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });
const findingsSelectedRowKeys = ref([]);
const findingsSelectedMap = ref({});
const findingsRepoSelectedKeys = ref([]);

const onFindingsSelectChange = (keys, rows) => {
  findingsSelectedRowKeys.value = keys;
  const nextMap = { ...findingsSelectedMap.value };
  (rows || []).forEach((r) => {
    if (r?.hash_md5) nextMap[r.hash_md5] = r;
  });
  findingsSelectedMap.value = nextMap;
};
const onFindingsRepoSelectChange = (keys) => {
  findingsRepoSelectedKeys.value = keys;
};

const findingsFlatColumns = [
  { get title() { return pageText('pages.githubColRepoAndFile'); }, key: 'repo_file', width: 290 },
  { get title() { return pageText('pages.codeMatchedContent'); }, key: 'human_content' },
  { get title() { return pageText('pages.githubColTriageStatus'); }, key: 'triage_status', width: 130 },
  { get title() { return pageText('pages.keywordLabel2'); }, key: 'keyword_time', width: 165 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 120 },
];

const findingsRepoColumns = [
  { get title() { return pageText('pages.repository'); }, dataIndex: 'repo_full_name', key: 'repo_full_name', width: 280 },
  { get title() { return pageText('pages.githubColFileCount'); }, dataIndex: 'file_count', key: 'file_count', width: 110 },
  { get title() { return pageText('pages.githubColTriageBreakdown'); }, key: 'breakdown', width: 240 },
  { get title() { return pageText('pages.keywordLabel2'); }, key: 'keywords' },
  { get title() { return pageText('pages.committedRecordedAt'); }, dataIndex: 'latest_commit_date', key: 'latest_commit_date', width: 170 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 240 },
];

const buildFindingsQueryParams = () => {
  const params = {
    page: findingsPager.current,
    size: findingsPager.pageSize,
    group_by: findingsGroupMode.value,
    source_type: findingsSearchForm.source_type || 'all',
  };
  if (findingsSearchForm.github_task_id) params.github_task_id = findingsSearchForm.github_task_id;
  if (findingsSearchForm.github_scheduler_id) params.github_scheduler_id = findingsSearchForm.github_scheduler_id;
  if (findingsSearchForm.repo_full_name) params.repo_full_name = findingsSearchForm.repo_full_name;
  if (findingsSearchForm.path) params.path = findingsSearchForm.path;
  if (findingsSearchForm.human_content) params.human_content = findingsSearchForm.human_content;
  if (findingsSearchForm.keyword) params.keyword = findingsSearchForm.keyword;
  if (findingsSearchForm.only_ignored) {
    params.only_ignored = 'true';
  } else if (findingsSearchForm.triage_status) {
    params.triage_status = findingsSearchForm.triage_status;
  }
  return params;
};

const fetchFindingsStats = async () => {
  try {
    const res = await request.get('/github_result/stats/');
    if (res.code === 200 && res.data) {
      Object.assign(findingsStats, res.data);
    }
  } catch (e) {
    console.error(e);
  }
};

const fetchFindingsData = async () => {
  findingsLoading.value = true;
  try {
    const res = await request.get('/github_result/overview/', { params: buildFindingsQueryParams() });
    if (res.code === 200 && res.data) {
      if (findingsGroupMode.value === 'repo') {
        findingsRepoData.value = res.data.items || [];
      } else {
        findingsData.value = res.data.items || [];
      }
      findingsPager.total = res.data.total || 0;
    }
  } catch {
    message.error(pageText('pages.failedToLoadFindings'));
  } finally {
    findingsLoading.value = false;
  }
};

const onFindingsQuickFilterChange = () => {
  const val = findingsQuickFilter.value;
  findingsSearchForm.only_ignored = val === 'ignored';
  findingsSearchForm.triage_status = ['pending', 'confirmed', 'false_positive'].includes(val) ? val : '';
  findingsPager.current = 1;
  findingsSelectedRowKeys.value = [];
  findingsRepoSelectedKeys.value = [];
  fetchFindingsData();
};

const onFindingsGroupModeChange = () => {
  findingsPager.current = 1;
  findingsSelectedRowKeys.value = [];
  findingsRepoSelectedKeys.value = [];
  fetchFindingsData();
};

const onFindingsSearch = () => {
  findingsPager.current = 1;
  fetchFindingsData();
};

const resetFindingsSearch = () => {
  findingsQuickFilter.value = 'all';
  findingsSourceLabel.value = '';
  Object.assign(findingsSearchForm, {
    source_type: 'all',
    github_task_id: '',
    github_scheduler_id: '',
    repo_full_name: '',
    path: '',
    human_content: '',
    keyword: '',
    triage_status: '',
    only_ignored: false,
  });
  findingsPager.current = 1;
  fetchFindingsData();
};

const clearFindingsSourceContext = () => {
  findingsSourceLabel.value = '';
  findingsSearchForm.github_task_id = '';
  findingsSearchForm.github_scheduler_id = '';
  findingsSearchForm.source_type = 'all';
  findingsPager.current = 1;
  fetchFindingsData();
};

const jumpToFindingsFromSource = (type, record) => {
  mainTab.value = 'dlp';
  activeTabDlp.value = 'findings';
  findingsQuickFilter.value = 'all';
  findingsSearchForm.triage_status = '';
  findingsSearchForm.only_ignored = false;
  if (type === 'scheduler') {
    findingsSearchForm.source_type = 'scheduler';
    findingsSearchForm.github_scheduler_id = record._id;
    findingsSearchForm.github_task_id = '';
  } else {
    findingsSearchForm.source_type = 'all';
    findingsSearchForm.github_task_id = record._id;
    findingsSearchForm.github_scheduler_id = '';
  }
  findingsSourceLabel.value = record.name || record.keyword || record._id;
  findingsPager.current = 1;
  fetchFindingsData();
};

const jumpToFindingsFromDrawer = () => {
  const rec = resultCurrentRecord.value;
  if (!rec) return;
  closeResultDrawer();
  jumpToFindingsFromSource(resultDrawerType.value, rec);
};

const handleFindingsTableChange = (page, pageSize) => {
  findingsPager.current = page;
  findingsPager.pageSize = pageSize;
  fetchFindingsData();
};

const updateTriageStatus = async (hashList, status, note) => {
  const clean = [...new Set((hashList || []).filter(Boolean))];
  if (!clean.length) return;
  try {
    const payload = { hash_md5s: clean, triage_status: status };
    if (typeof note === 'string') payload.note = note;
    const res = await request.post('/github_result/triage/', payload);
    if (res.code === 200) {
      message.success(pageText('pages.githubTriageUpdated'));
      findingsSelectedRowKeys.value = [];
      await Promise.all([fetchFindingsData(), fetchFindingsStats()]);
      if (resultDrawerVisible.value) {
        fetchResultData();
      }
    } else {
      message.error(res.message || pageText('tasks.operationFailedLabel'));
    }
  } catch {
    message.error(pageText('tasks.requestFailed'));
  }
};

// 详情与备注抽屉
const findingDetailDrawerVisible = ref(false);
const findingDetailRecord = ref(null);
const findingDetailSaving = ref(false);
const findingDetailForm = reactive({ triage_status: 'pending', note: '' });

const openFindingDetailDrawer = (record) => {
  findingDetailRecord.value = record;
  findingDetailForm.triage_status = record.triage_status || 'pending';
  findingDetailForm.note = record.triage_note || '';
  findingDetailDrawerVisible.value = true;
};

const saveFindingDetailTriage = async () => {
  if (!findingDetailRecord.value?.hash_md5) return;
  findingDetailSaving.value = true;
  try {
    await updateTriageStatus(
      [findingDetailRecord.value.hash_md5],
      findingDetailForm.triage_status,
      findingDetailForm.note,
    );
    findingDetailRecord.value.triage_status = findingDetailForm.triage_status;
    findingDetailRecord.value.triage_note = findingDetailForm.note;
    findingDetailDrawerVisible.value = false;
  } finally {
    findingDetailSaving.value = false;
  }
};

// 屏蔽仓库抽屉与批量屏蔽
const ignoredDrawerVisible = ref(false);
const ignoredLoading = ref(false);
const ignoredReposList = ref([]);
const newIgnoredRepoInput = ref('');
const ignoredRepoColumns = [
  { get title() { return pageText('pages.repository'); }, dataIndex: 'repo_full_name', key: 'repo_full_name' },
  { get title() { return pageText('pages.githubIgnoredCreatedAt'); }, dataIndex: 'created_at', key: 'created_at', width: 170 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 110 },
];

const fetchIgnoredRepos = async () => {
  ignoredLoading.value = true;
  try {
    const res = await request.get('/github_result/ignored_repos/');
    if (res.code === 200) {
      ignoredReposList.value = res.data?.items || [];
    }
  } finally {
    ignoredLoading.value = false;
  }
};

const openIgnoredReposDrawer = () => {
  ignoredDrawerVisible.value = true;
  fetchIgnoredRepos();
};

const handleIgnoreRepos = async (action, repoList) => {
  const clean = [...new Set((repoList || []).filter(Boolean))];
  if (!clean.length) return;
  try {
    const res = await request.post('/github_result/ignored_repos/', {
      action,
      repo_full_names: clean,
    });
    if (res.code === 200) {
      message.success(
        action === 'add' ? pageText('pages.githubRepoIgnoredSuccess') : pageText('pages.githubRepoUnignoredSuccess')
      );
      findingsSelectedRowKeys.value = [];
      findingsRepoSelectedKeys.value = [];
      await Promise.all([fetchFindingsData(), fetchFindingsStats()]);
      if (ignoredDrawerVisible.value) {
        fetchIgnoredRepos();
      }
    } else {
      message.error(res.message || pageText('tasks.operationFailedLabel'));
    }
  } catch {
    message.error(pageText('tasks.requestFailed'));
  }
};

const submitNewIgnoredRepo = async () => {
  const val = newIgnoredRepoInput.value.trim();
  if (!val) return;
  await handleIgnoreRepos('add', [val]);
  newIgnoredRepoInput.value = '';
};

const confirmBatchIgnoreSelectedRepos = () => {
  let repos = [];
  if (findingsGroupMode.value === 'repo') {
    repos = [...findingsRepoSelectedKeys.value];
  } else {
    repos = findingsSelectedRowKeys.value
      .map((hash) => {
        const fromCurrent = findingsData.value.find(item => item.hash_md5 === hash);
        return (fromCurrent || findingsSelectedMap.value[hash])?.repo_full_name;
      })
      .filter(Boolean);
    repos = [...new Set(repos)];
  }
  if (!repos.length) return;
  confirmBatchItems({
    actionLabel: pageText('pages.githubBatchIgnoreRepos'),
    items: repos,
    danger: true,
    onOk: () => handleIgnoreRepos('add', repos),
  });
};

const handleExportFindings = async (format) => {
  findingsExportLoading.value = true;
  try {
    const params = { ...buildFindingsQueryParams(), format };
    delete params.page;
    delete params.size;
    delete params.group_by;
    const res = await request.get('/github_result/export/', { params, responseType: 'blob' });
    const mime = format === 'json' ? 'application/json;charset=utf-8' : 'text/csv;charset=utf-8';
    const blob = new Blob([res], { type: mime });
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `github_leak_findings.${format === 'json' ? 'json' : 'csv'}`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
  } catch {
    message.error(pageText('tasks.exportFailed'));
  } finally {
    findingsExportLoading.value = false;
  }
};

// ==========================================
// ⚙️ 模块 A: 监控策略管理 (github_scheduler)
// ==========================================
const schedulerLoading = ref(false);
const schedulerData = ref([]);
const schedulerSearchForm = reactive({ name: '', keyword: '', status: undefined });
const schedulerPagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });
const schedulerSelectedRowKeys = ref([]);
const onSchedulerSelectChange = (keys) => { schedulerSelectedRowKeys.value = keys; };

const schedulerColumns = [
  { get title() { return pageText('tasks.policyName'); }, dataIndex: 'name', key: 'name', width: 160 },
  { get title() { return pageText('pages.keywordLabel2'); }, dataIndex: 'keyword', key: 'keyword', width: 160 },
  { get title() { return pageText('pages.cronExpression'); }, dataIndex: 'cron', key: 'cron', width: 130 },
  { get title() { return pageText('pages.results'); }, dataIndex: 'result_count', key: 'result_count', width: 95 },
  { get title() { return pageText('tasks.status'); }, dataIndex: 'status', key: 'status', width: 110 },
  { get title() { return pageText('tasks.runCount'); }, dataIndex: 'run_number', key: 'run_number', width: 85 },
  { get title() { return pageText('tasks.lastRun'); }, dataIndex: 'last_run_date', key: 'last_run_date', width: 165 },
  { get title() { return pageText('tasks.nextRun'); }, dataIndex: 'next_run_date', key: 'next_run_date', width: 165 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 290 },
];

const fetchSchedulerData = async () => {
  schedulerLoading.value = true;
  try {
    const params = { page: schedulerPagination.current, size: schedulerPagination.pageSize };
    if (schedulerSearchForm.name) params.name = schedulerSearchForm.name;
    if (schedulerSearchForm.keyword) params.keyword = schedulerSearchForm.keyword;
    if (schedulerSearchForm.status) params.status = schedulerSearchForm.status;

    const res = await request.get('/github_scheduler/', { params });
    if (res.code === 200) {
      schedulerData.value = res.items || [];
      schedulerPagination.total = res.total || 0;
      schedulerSelectedRowKeys.value = [];
    }
  } catch {
    message.error(pageText('pages.failedToLoadMonitoringPolicies'));
  } finally {
    schedulerLoading.value = false;
  }
};

const resetSchedulerSearch = () => {
  Object.assign(schedulerSearchForm, { name: '', keyword: '', status: undefined });
  schedulerPagination.current = 1;
  onSchedulerSearch();
};
const onSchedulerSearch = () => { schedulerPagination.current = 1; fetchSchedulerData(); };
const handleSchedulerTableChange = (page, pageSize) => {
  schedulerPagination.current = page;
  schedulerPagination.pageSize = pageSize;
  fetchSchedulerData();
};

const performSchedulerAction = async (actionType, idArray) => {
  try {
    const res = await request.post(`/github_scheduler/${actionType}/`, { _id: idArray });
    if (res.code === 200) {
      message.success(pageText('tasks.operationCompleted'));
      fetchSchedulerData();
      fetchFindingsStats();
    } else {
      message.error(res.message || pageText('tasks.operationFailedLabel'));
    }
  } catch {
    message.error(pageText('tasks.requestFailed'));
  }
};

const handleSchedulerRunNow = async (idArray) => {
  try {
    const res = await request.post('/github_scheduler/run/', { _id: idArray });
    if (res.code === 200) {
      message.success(pageText('pages.githubPolicyTriggered'));
      schedulerSelectedRowKeys.value = [];
      fetchSchedulerData();
      fetchTaskData();
      fetchFindingsStats();
    } else {
      message.error(res.message || pageText('tasks.operationFailedLabel'));
    }
  } catch {
    message.error(pageText('tasks.requestFailed'));
  }
};

const handleSchedulerSingleAction = (type, id) => performSchedulerAction(type, [id]);

const resolveSelectedNames = (keys, list, idField = '_id', labelField = 'name') =>
  keys.map((k) => list.find(item => item[idField] === k)?.[labelField] || k);

const confirmSchedulerBatchAction = (actionType) => {
  const ids = [...schedulerSelectedRowKeys.value];
  if (!ids.length) return;
  const labels = resolveSelectedNames(ids, schedulerData.value, '_id', 'name');
  confirmBatchItems({
    actionLabel: actionType === 'delete' ? pageText('tasks.deleteSelected') : pageText('tasks.stopSelected'),
    items: labels,
    danger: actionType === 'delete',
    onOk: () => performSchedulerAction(actionType, ids),
  });
};

// 策略弹窗逻辑
const schedulerModalVisible = ref(false);
const schedulerSubmitLoading = ref(false);
const schedulerIsEdit = ref(false);
const schedulerEditId = ref('');
const schedulerForm = reactive({ name: '', keyword: '', cron: '' });

const openSchedulerAdd = () => {
  schedulerIsEdit.value = false;
  schedulerEditId.value = '';
  Object.assign(schedulerForm, { name: '', keyword: '', cron: '0 */6 * * *' });
  schedulerModalVisible.value = true;
};

const openSchedulerEdit = (record) => {
  schedulerIsEdit.value = true;
  schedulerEditId.value = record._id;
  Object.assign(schedulerForm, { name: record.name, keyword: record.keyword, cron: record.cron });
  schedulerModalVisible.value = true;
};

const submitSchedulerModal = async () => {
  if (!schedulerForm.name || !schedulerForm.keyword || !schedulerForm.cron) {
    return message.warning(pageText('pages.completeAllRequiredFields'));
  }
  schedulerSubmitLoading.value = true;
  try {
    let res;
    if (schedulerIsEdit.value) {
      const payload = { _id: schedulerEditId.value, ...schedulerForm };
      res = await request.post('/github_scheduler/update/', payload);
    } else {
      res = await request.post('/github_scheduler/', schedulerForm);
    }
    if (res.code === 200) {
      message.success(schedulerIsEdit.value ? pageText('pages.policyUpdated') : pageText('pages.policyCreated'));
      schedulerModalVisible.value = false;
      onSchedulerSearch();
    } else {
      message.error(res.message || pageText('tasks.operationFailedLabel'));
    }
  } catch {
    message.error(pageText('tasks.requestFailed'));
  } finally {
    schedulerSubmitLoading.value = false;
  }
};

// ==========================================
// 👷 模块 B: 扫描任务记录 (github_task)
// ==========================================
const taskLoading = ref(false);
const taskData = ref([]);
const taskSearchForm = reactive({ name: '', keyword: '', status: undefined, source_type: 'all' });
const taskPagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });
const taskSelectedRowKeys = ref([]);
const onTaskSelectChange = (keys) => { taskSelectedRowKeys.value = keys; };

const taskColumns = [
  { get title() { return pageText('tasks.taskName'); }, dataIndex: 'name', key: 'name', width: 170 },
  { get title() { return pageText('pages.githubSourceLabel'); }, dataIndex: 'source_type', key: 'source_type', width: 110 },
  { get title() { return pageText('pages.keywordLabel2'); }, dataIndex: 'keyword', key: 'keyword', width: 160 },
  { get title() { return pageText('pages.results'); }, dataIndex: 'result_count', key: 'result_count', width: 95 },
  { get title() { return pageText('tasks.status'); }, dataIndex: 'status', key: 'status', width: 150 },
  { get title() { return pageText('tasks.startTime'); }, dataIndex: 'start_time', key: 'start_time', width: 165 },
  { get title() { return pageText('tasks.endTime'); }, dataIndex: 'end_time', key: 'end_time', width: 165 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 220 },
];

const fetchTaskData = async () => {
  taskLoading.value = true;
  try {
    const params = { page: taskPagination.current, size: taskPagination.pageSize };
    if (taskSearchForm.name) params.name = taskSearchForm.name;
    if (taskSearchForm.keyword) params.keyword = taskSearchForm.keyword;
    if (taskSearchForm.status) params.status = taskSearchForm.status;
    if (taskSearchForm.source_type && taskSearchForm.source_type !== 'all') {
      params.source_type = taskSearchForm.source_type;
    }

    const res = await request.get('/github_task/', { params });
    if (res.code === 200) {
      taskData.value = (res.items || []).map((item) => {
        if (item.statistic && item.statistic.github_result_cnt !== undefined) {
          item.result_count = item.statistic.github_result_cnt;
        } else if (!item.result_count) {
          item.result_count = 0;
        }
        return item;
      });
      taskPagination.total = res.total || 0;
      taskSelectedRowKeys.value = [];
    }
  } catch {
    message.error(pageText('pages.failedToLoadScanningTasks'));
  } finally {
    taskLoading.value = false;
  }
};

const resetTaskSearch = () => {
  Object.assign(taskSearchForm, { name: '', keyword: '', status: undefined, source_type: 'all' });
  taskPagination.current = 1;
  onTaskSearch();
};
const onTaskSearch = () => { taskPagination.current = 1; fetchTaskData(); };
const handleTaskTableChange = (page, pageSize) => {
  taskPagination.current = page;
  taskPagination.pageSize = pageSize;
  fetchTaskData();
};

const performTaskAction = async (actionType, idArray) => {
  try {
    const res = await request.post(`/github_task/${actionType}/`, { _id: idArray });
    if (res.code === 200) {
      message.success(pageText('tasks.operationCompleted'));
      fetchTaskData();
      fetchFindingsStats();
    } else {
      message.error(res.message || pageText('tasks.operationFailedLabel'));
    }
  } catch {
    message.error(pageText('tasks.requestFailed'));
  }
};

const handleTaskSingleAction = (type, id) => performTaskAction(type, [id]);

const confirmTaskBatchAction = (actionType) => {
  const ids = [...taskSelectedRowKeys.value];
  if (!ids.length) return;
  const labels = resolveSelectedNames(ids, taskData.value, '_id', 'name');
  confirmBatchItems({
    actionLabel: actionType === 'delete' ? pageText('tasks.deleteSelected') : pageText('tasks.stopSelected'),
    items: labels,
    danger: actionType === 'delete',
    onOk: () => performTaskAction(actionType, ids),
  });
};

const handleTaskRestart = async (record) => {
  try {
    const res = await request.post('/github_task/', { name: record.name, keyword: record.keyword });
    if (res.code === 200) {
      message.success(pageText('pages.taskRestartedANewTaskWasQueued'));
      onTaskSearch();
      fetchFindingsStats();
    } else {
      message.error(pageText('tasks.failedToRestartTask') + res.message);
    }
  } catch {
    message.error(pageText('tasks.requestFailed'));
  }
};

const taskModalVisible = ref(false);
const taskSubmitLoading = ref(false);
const taskForm = reactive({ name: '', keyword: '' });

const openTaskAdd = () => {
  taskForm.name = '';
  taskForm.keyword = '';
  taskModalVisible.value = true;
};

const submitTaskModal = async () => {
  if (!taskForm.name || !taskForm.keyword) {
    return message.warning(pageText('pages.enterATaskNameAndKeyword'));
  }
  taskSubmitLoading.value = true;
  try {
    const res = await request.post('/github_task/', taskForm);
    if (res.code === 200) {
      message.success(pageText('pages.oneTimeScanningTaskCreated'));
      taskModalVisible.value = false;
      onTaskSearch();
      fetchFindingsStats();
    } else {
      message.error(pageText('tasks.failedToCreateTaskLabel') + res.message);
    }
  } catch {
    message.error(pageText('tasks.requestFailed'));
  } finally {
    taskSubmitLoading.value = false;
  }
};

// ================= GitHub 任务与监控命中结果抽屉 =================
const resultDrawerVisible = ref(false);
const resultDrawerType = ref('task');
const resultCurrentRecord = ref(null);
const resultDrawerTitle = computed(() => {
  const record = resultCurrentRecord.value;
  if (!record) return '';
  return resultDrawerType.value === 'task'
    ? pageText('pages.oneTimeScanResultsName', { name: record.name })
    : pageText('pages.recurringMonitoringFindingsName', { name: record.name });
});
const resultActiveTab = ref('result');
const resultLoading = ref(false);
const resultDataSource = ref([]);
const resultSearchForm = reactive({ path: '', repo_full_name: '', human_content: '' });
const resultPagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

const resultColumns = [
  { get title() { return pageText('pages.repository'); }, dataIndex: 'repo_full_name', key: 'repo_full_name', width: 220 },
  { get title() { return pageText('pages.filePath'); }, dataIndex: 'path', key: 'path', width: 210 },
  { get title() { return pageText('pages.codeMatchedContent'); }, dataIndex: 'human_content', key: 'human_content' },
  { get title() { return pageText('pages.committedRecordedAt'); }, dataIndex: 'commit_date', key: 'commit_date', width: 155 },
  { get title() { return pageText('pages.keywordLabel2'); }, dataIndex: 'keyword', key: 'keyword', width: 110 },
];

const openResultDrawer = (record, type) => {
  resultCurrentRecord.value = record;
  resultDrawerType.value = type;
  resultActiveTab.value = 'result';
  resultSearchForm.path = '';
  resultSearchForm.repo_full_name = '';
  resultSearchForm.human_content = '';
  resultPagination.current = 1;
  resultDrawerVisible.value = true;
  fetchResultData();
};

const closeResultDrawer = () => {
  resultDrawerVisible.value = false;
  stopResultSyslogTimer();
};

const fetchResultData = async () => {
  if (!resultCurrentRecord.value?._id) return;
  resultLoading.value = true;
  try {
    const params = {
      page: resultPagination.current,
      size: resultPagination.pageSize,
    };
    if (resultDrawerType.value === 'task') {
      params.github_task_id = resultCurrentRecord.value._id;
    } else {
      params.github_scheduler_id = resultCurrentRecord.value._id;
    }
    if (resultSearchForm.path) params.path = resultSearchForm.path;
    if (resultSearchForm.repo_full_name) params.repo_full_name = resultSearchForm.repo_full_name;
    if (resultSearchForm.human_content) params.human_content = resultSearchForm.human_content;

    const apiUrl = resultDrawerType.value === 'task' ? '/github_result/' : '/github_monitor_result/';
    const res = await request.get(apiUrl, { params });
    if (res.code === 200) {
      resultDataSource.value = res.items || [];
      resultPagination.total = res.total || 0;
    }
  } catch {
    message.error(pageText('pages.failedToLoadFindings'));
  } finally {
    resultLoading.value = false;
  }
};

const onResultSearch = () => {
  resultPagination.current = 1;
  fetchResultData();
};

const resetResultSearch = () => {
  resultSearchForm.path = '';
  resultSearchForm.repo_full_name = '';
  resultSearchForm.human_content = '';
  resultPagination.current = 1;
  fetchResultData();
};

const handleResultTableChange = (page, pageSize) => {
  resultPagination.current = page;
  if (pageSize && pageSize !== resultPagination.pageSize) {
    resultPagination.pageSize = pageSize;
  }
  fetchResultData();
};

// ================= 日志查询 (单次扫描) =================
const resultLogLoading = ref(false);
const resultLogDataSource = ref([]);
const resultTerminalContainer = ref(null);
let resultSyslogTimer = null;

const fetchResultLogData = async (isPolling = false) => {
  if (!resultCurrentRecord.value?._id || resultDrawerType.value !== 'task') return;
  if (!isPolling) resultLogLoading.value = true;
  try {
    const params = {
      size: 50000,
      task_id: resultCurrentRecord.value._id,
      order: 'create_time',
    };
    const res = await request.get('/syslog/', { params });
    if (res.code === 200) {
      resultLogDataSource.value = res.items || [];
      nextTick(() => {
        if (resultTerminalContainer.value) {
          resultTerminalContainer.value.scrollTop = resultTerminalContainer.value.scrollHeight;
        }
      });
    }
  } catch {
    if (!isPolling) message.error(pageText('tasks.failedToLoadTaskLogs'));
  } finally {
    if (!isPolling) resultLogLoading.value = false;
  }
};

const startResultSyslogTimer = () => {
  stopResultSyslogTimer();
  fetchResultLogData();
  resultSyslogTimer = setInterval(() => fetchResultLogData(true), 5000);
};

const stopResultSyslogTimer = () => {
  if (resultSyslogTimer) {
    clearInterval(resultSyslogTimer);
    resultSyslogTimer = null;
  }
};

watch(resultActiveTab, (tab) => {
  if (tab === 'result') {
    stopResultSyslogTimer();
    fetchResultData();
  } else if (tab === 'log') {
    startResultSyslogTimer();
  }
});

// ==========================================
// 🛠️ 模块 C: 武器库追踪 (github_tools_target)
// ==========================================
const toolsLoading = ref(false);
const toolsData = ref([]);
const toolsSearchForm = reactive({ repo_url: '' });
const appliedToolsSearchForm = reactive({ repo_url: '' });
const onToolsSearch = () => { Object.assign(appliedToolsSearchForm, toolsSearchForm); toolsPagination.current = 1; };

const filteredToolsData = computed(() =>
  toolsData.value.filter((item) => {
    if (appliedToolsSearchForm.repo_url && !item.repo_url.toLowerCase().includes(appliedToolsSearchForm.repo_url.toLowerCase())) {
      return false;
    }
    return true;
  })
);

const toolsPagination = reactive({ current: 1, pageSize: globalPageSize.value });
const pagedToolsData = computed(() => {
  const start = (toolsPagination.current - 1) * toolsPagination.pageSize;
  return filteredToolsData.value.slice(start, start + toolsPagination.pageSize);
});
const onToolsTableChange = (page, pageSize) => { toolsPagination.current = page; toolsPagination.pageSize = pageSize; };
const resetToolsSearch = () => { toolsSearchForm.repo_url = ''; Object.assign(appliedToolsSearchForm, toolsSearchForm); toolsPagination.current = 1; };

const toolsSelectedRowKeys = ref([]);
const onToolsSelectChange = (keys) => { toolsSelectedRowKeys.value = keys; };

const toolModalVisible = ref(false);
const toolSubmitLoading = ref(false);
const toolForm = reactive({ repo_url: '' });

const toolNotesDrawerVisible = ref(false);
const toolNotesRecord = ref(null);
const openToolNotesDrawer = (record) => {
  toolNotesRecord.value = record;
  toolNotesDrawerVisible.value = true;
};

const toolsColumns = [
  { get title() { return pageText('pages.toolNameUrl'); }, dataIndex: 'repo_url', key: 'repo_url', width: 320 },
  { get title() { return pageText('pages.latestVersion'); }, dataIndex: 'last_tag', key: 'last_tag', width: 150 },
  { get title() { return pageText('pages.releasedAt'); }, dataIndex: 'last_commit_time', key: 'last_commit_time', width: 145 },
  { get title() { return pageText('pages.recordedAt'); }, dataIndex: 'insert_time', key: 'insert_time', width: 165 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 220 },
];

const fetchToolsData = async () => {
  toolsLoading.value = true;
  try {
    const res = await request.get('/github_threat/tools_target');
    if (res.code === 200) {
      toolsData.value = res.data || [];
    }
  } catch {
    message.error(pageText('pages.failedToLoadMonitoredTools'));
  } finally {
    toolsLoading.value = false;
  }
};

const handleToolDelete = async (repo_url) => {
  const res = await request.post('/github_threat/tools_target/delete', { repo_url });
  if (res.code === 200) {
    message.success(pageText('pages.monitoringStopped'));
    fetchToolsData();
  }
};

const openToolAdd = () => {
  toolForm.repo_url = '';
  toolModalVisible.value = true;
};

const appendToolPreset = (repoSlug) => {
  const existing = parseMultilineList(toolForm.repo_url);
  const full = `https://github.com/${repoSlug}`;
  if (!existing.includes(repoSlug) && !existing.includes(full)) {
    existing.push(full);
    toolForm.repo_url = existing.join('\n');
  }
};

const submitToolModal = async () => {
  const items = parseMultilineList(toolForm.repo_url);
  if (!items.length) return message.warning(pageText('pages.urlCannotBeEmpty'));

  toolSubmitLoading.value = true;
  try {
    const payload = items.length > 1 ? { repo_urls: items } : { repo_url: items[0] };
    const res = await request.post('/github_threat/tools_target', payload);
    if (res.code === 200) {
      message.success(res.data?.msg || pageText('pages.added'));
      toolModalVisible.value = false;
      fetchToolsData();
    } else {
      message.error(res.data?.error || res.message);
    }
  } finally {
    toolSubmitLoading.value = false;
  }
};

// ==========================================
// 🧑‍💻 模块 D: 安全研究员动态 (github_hackers_target)
// ==========================================
const hackersLoading = ref(false);
const hackersData = ref([]);
const hackersSearchForm = reactive({ github_id: '' });
const appliedHackersSearchForm = reactive({ github_id: '' });
const onHackersSearch = () => { Object.assign(appliedHackersSearchForm, hackersSearchForm); hackersPagination.current = 1; };

const filteredHackersData = computed(() =>
  hackersData.value.filter((item) => {
    if (appliedHackersSearchForm.github_id && !item.github_id.toLowerCase().includes(appliedHackersSearchForm.github_id.toLowerCase())) {
      return false;
    }
    return true;
  })
);

const hackersPagination = reactive({ current: 1, pageSize: globalPageSize.value });
const pagedHackersData = computed(() => {
  const start = (hackersPagination.current - 1) * hackersPagination.pageSize;
  return filteredHackersData.value.slice(start, start + hackersPagination.pageSize);
});
const onHackersTableChange = (page, pageSize) => { hackersPagination.current = page; hackersPagination.pageSize = pageSize; };
const resetHackersSearch = () => { hackersSearchForm.github_id = ''; Object.assign(appliedHackersSearchForm, hackersSearchForm); hackersPagination.current = 1; };

const hackersSelectedRowKeys = ref([]);
const onHackersSelectChange = (keys) => { hackersSelectedRowKeys.value = keys; };

const hackerModalVisible = ref(false);
const hackerSubmitLoading = ref(false);
const hackerForm = reactive({ github_id: '' });

const historyDrawerVisible = ref(false);
const historyLoading = ref(false);
const hackersHistoryData = ref([]);
const historyFilter = reactive({ github_id: '', q: '' });

const hackersColumns = [
  { get title() { return pageText('pages.githubIdResearcherTeam'); }, dataIndex: 'github_id', key: 'github_id', width: 250 },
  { get title() { return pageText('pages.openSourceToolsDiscovered'); }, dataIndex: 'found_count', key: 'found_count', width: 170 },
  { get title() { return pageText('pages.monitoringAddedAt'); }, dataIndex: 'insert_time', key: 'insert_time', width: 180 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 200 },
];

const historyColumns = [
  { get title() { return pageText('pages.toolRepositoryPath'); }, dataIndex: 'full_name', key: 'full_name' },
  { get title() { return pageText('pages.githubRepoLanguage'); }, key: 'meta', width: 140 },
  { get title() { return pageText('tasks.discoveredAt'); }, dataIndex: 'insert_time', key: 'insert_time', width: 165 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 100 },
];

const fetchHackersHistory = async () => {
  historyLoading.value = true;
  try {
    const params = {};
    if (historyFilter.github_id) params.github_id = historyFilter.github_id;
    if (historyFilter.q) params.q = historyFilter.q;
    const res = await request.get('/github_threat/hackers_history', { params });
    if (res.code === 200) {
      hackersHistoryData.value = res.data || [];
    }
  } catch {
    message.error(pageText('pages.failedToLoadDiscoveredTools'));
  } finally {
    historyLoading.value = false;
  }
};

const openHackersHistoryDrawer = (githubId = '') => {
  historyFilter.github_id = typeof githubId === 'string' ? githubId : '';
  historyFilter.q = '';
  historyDrawerVisible.value = true;
  fetchHackersHistory();
};

const closeHackersHistoryDrawer = () => {
  historyDrawerVisible.value = false;
};

const fetchHackersData = async () => {
  hackersLoading.value = true;
  try {
    const res = await request.get('/github_threat/hackers_target');
    if (res.code === 200) {
      hackersData.value = res.data || [];
    }
  } catch {
    message.error(pageText('pages.failedToLoadTrackedResearchers'));
  } finally {
    hackersLoading.value = false;
  }
};

const handleHackerDelete = async (github_id) => {
  const res = await request.post('/github_threat/hackers_target/delete', { github_id });
  if (res.code === 200) {
    message.success(pageText('pages.monitoringStopped'));
    fetchHackersData();
  }
};

const openHackerAdd = () => {
  hackerForm.github_id = '';
  hackerModalVisible.value = true;
};

const submitHackerModal = async () => {
  const ids = parseMultilineList(hackerForm.github_id);
  if (!ids.length) return message.warning(pageText('pages.idCannotBeEmpty'));

  hackerSubmitLoading.value = true;
  try {
    const payload = ids.length > 1 ? { github_ids: ids } : { github_id: ids[0] };
    const res = await request.post('/github_threat/hackers_target', payload);
    if (res.code === 200) {
      message.success(res.data?.msg || pageText('pages.added'));
      hackerModalVisible.value = false;
      fetchHackersData();
    } else {
      message.error(res.data?.error || res.message);
    }
  } finally {
    hackerSubmitLoading.value = false;
  }
};

// ==========================================
// 🛡️ 模块 E: CVE 漏洞雷达 (github_cve_history)
// ==========================================
const cveLoading = ref(false);
const cveData = ref([]);
const cveSearchForm = reactive({ cve_name: '', desc: '', todayOnly: false });
const appliedCveSearchForm = reactive({ cve_name: '', desc: '', todayOnly: false });
const onCveSearch = () => { Object.assign(appliedCveSearchForm, cveSearchForm); cvePagination.current = 1; };

const filteredCveData = computed(() =>
  cveData.value.filter((item) => {
    if (appliedCveSearchForm.cve_name && !item.cve_name.toLowerCase().includes(appliedCveSearchForm.cve_name.toLowerCase())) {
      return false;
    }
    if (appliedCveSearchForm.desc && !(item.desc || '').toLowerCase().includes(appliedCveSearchForm.desc.toLowerCase())) {
      return false;
    }
    if (appliedCveSearchForm.todayOnly && !isTodayRecord(item.insert_time, item.pushed_at)) {
      return false;
    }
    return true;
  })
);

const cvePagination = reactive({ current: 1, pageSize: globalPageSize.value });

// 所有分页状态初始化后再注册监听，同步全局每页条数
watch(globalPageSize, (newSize) => {
  findingsPager.pageSize = newSize;
  schedulerPagination.pageSize = newSize;
  taskPagination.pageSize = newSize;
  toolsPagination.pageSize = newSize;
  hackersPagination.pageSize = newSize;
  cvePagination.pageSize = newSize;
  resultPagination.pageSize = newSize;
});

watch(() => findingsPager.pageSize, (newSize) => { globalPageSize.value = newSize; });
watch(() => schedulerPagination.pageSize, (newSize) => { globalPageSize.value = newSize; });
watch(() => taskPagination.pageSize, (newSize) => { globalPageSize.value = newSize; });
watch(() => toolsPagination.pageSize, (newSize) => { globalPageSize.value = newSize; });
watch(() => hackersPagination.pageSize, (newSize) => { globalPageSize.value = newSize; });
watch(() => cvePagination.pageSize, (newSize) => { globalPageSize.value = newSize; });
watch(() => resultPagination.pageSize, (newSize) => { globalPageSize.value = newSize; });

const pagedCveData = computed(() => {
  const start = (cvePagination.current - 1) * cvePagination.pageSize;
  return filteredCveData.value.slice(start, start + cvePagination.pageSize);
});
const onCveTableChange = (page, pageSize) => { cvePagination.current = page; cvePagination.pageSize = pageSize; };
const resetCveSearch = () => {
  Object.assign(cveSearchForm, { cve_name: '', desc: '', todayOnly: false });
  Object.assign(appliedCveSearchForm, cveSearchForm);
  cvePagination.current = 1;
};

const cveSelectedRowKeys = ref([]);
const onCveSelectChange = (keys) => { cveSelectedRowKeys.value = keys; };

const handleCveDelete = async (cve_name) => {
  const res = await request.post('/github_threat/cve_history/delete', { cve_name });
  if (res.code === 200) {
    message.success(pageText('tasks.deletedSuccessfully'));
    fetchCveData();
  } else {
    message.error(res.message);
  }
};

const confirmThreatBatchDelete = (kind) => {
  if (kind === 'cve') {
    const names = [...cveSelectedRowKeys.value];
    if (!names.length) return;
    confirmBatchItems({
      actionLabel: pageText('tasks.deleteSelected'),
      items: names,
      danger: true,
      onOk: async () => {
        const res = await request.post('/github_threat/cve_history/delete', { cve_names: names });
        if (res.code === 200) {
          message.success(pageText('pages.selectedRecordsDeleted'));
          cveSelectedRowKeys.value = [];
          fetchCveData();
        } else {
          message.error(res.message);
        }
      },
    });
  } else if (kind === 'tools') {
    const urls = [...toolsSelectedRowKeys.value];
    if (!urls.length) return;
    const labels = urls.map(u => extractRepoSlugFromApiUrl(u) || u);
    confirmBatchItems({
      actionLabel: pageText('tasks.deleteSelected'),
      items: labels,
      danger: true,
      onOk: async () => {
        const res = await request.post('/github_threat/tools_target/delete', { repo_urls: urls });
        if (res.code === 200) {
          message.success(pageText('pages.selectedRecordsDeleted'));
          toolsSelectedRowKeys.value = [];
          fetchToolsData();
        } else {
          message.error(res.message);
        }
      },
    });
  } else if (kind === 'hackers') {
    const ids = [...hackersSelectedRowKeys.value];
    if (!ids.length) return;
    confirmBatchItems({
      actionLabel: pageText('tasks.deleteSelected'),
      items: ids,
      danger: true,
      onOk: async () => {
        const res = await request.post('/github_threat/hackers_target/delete', { github_ids: ids });
        if (res.code === 200) {
          message.success(pageText('pages.selectedRecordsDeleted'));
          hackersSelectedRowKeys.value = [];
          fetchHackersData();
        } else {
          message.error(res.message);
        }
      },
    });
  }
};

const cveColumns = [
  { get title() { return pageText('pages.cveIdLabel2'); }, dataIndex: 'cve_name', key: 'cve_name', width: 200 },
  { get title() { return pageText('pages.officialDescription'); }, dataIndex: 'desc', key: 'desc' },
  { get title() { return pageText('pages.latestPush'); }, dataIndex: 'pushed_at', key: 'pushed_at', width: 120 },
  { get title() { return pageText('pages.recordedAtLabel2'); }, dataIndex: 'insert_time', key: 'insert_time', width: 165 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 195 },
];

const fetchCveData = async () => {
  cveLoading.value = true;
  try {
    const res = await request.get('/github_threat/cve_history');
    if (res.code === 200) {
      cveData.value = res.data || [];
    }
  } catch {
    message.error(pageText('pages.failedToLoadCveMonitoringRecords'));
  } finally {
    cveLoading.value = false;
  }
};

// ==========================================
// 威胁情报三雷达统一配置与静默轮询
// ==========================================
const cveConfig = reactive({ enabled: false, interval: 6, is_running: false });
const cveRunLoading = ref(false);
const toolsConfig = reactive({ enabled: false, interval: 6, is_running: false });
const toolsRunLoading = ref(false);
const hackersConfig = reactive({ enabled: false, interval: 6, is_running: false });
const hackersRunLoading = ref(false);

const runningRadarCount = computed(() =>
  [cveConfig.is_running, toolsConfig.is_running, hackersConfig.is_running].filter(Boolean).length
);

const fetchCveConfig = async () => {
  try {
    const res = await request.get('/github_threat/cve_config');
    if (res.code === 200 && res.data) {
      const wasRunning = cveConfig.is_running;
      cveConfig.enabled = res.data.enabled;
      cveConfig.interval = res.data.interval;
      cveConfig.is_running = !!res.data.is_running;
      if (wasRunning && !cveConfig.is_running) fetchCveData();
    }
  } catch (e) { console.error(e); }
};

const saveCveConfig = async () => {
  try {
    const res = await request.post('/github_threat/cve_config', cveConfig);
    if (res.code === 200) message.success(pageText('pages.configurationSaved'));
    else message.error(res.message || pageText('pages.failedToSaveConfiguration'));
  } catch {
    message.error(pageText('pages.failedToSaveConfiguration'));
  }
};

const runCveOnce = async () => {
  cveRunLoading.value = true;
  try {
    const res = await request.post('/github_threat/cve_run_once');
    if (res.code === 200) {
      message.success(res.data?.msg || pageText('pages.cveMonitoringTaskQueued'));
      cveConfig.is_running = true;
      fetchCveConfig();
    } else {
      message.warning(res.data?.msg || res.message || pageText('pages.unableToStart'));
    }
  } catch {
    message.error(pageText('pages.requestFailed'));
  } finally {
    cveRunLoading.value = false;
  }
};

const fetchToolsConfig = async () => {
  try {
    const res = await request.get('/github_threat/tools_config');
    if (res.code === 200 && res.data) {
      const wasRunning = toolsConfig.is_running;
      toolsConfig.enabled = res.data.enabled;
      toolsConfig.interval = res.data.interval;
      toolsConfig.is_running = !!res.data.is_running;
      if (wasRunning && !toolsConfig.is_running) fetchToolsData();
    }
  } catch (e) { console.error(e); }
};

const saveToolsConfig = async () => {
  try {
    const res = await request.post('/github_threat/tools_config', toolsConfig);
    if (res.code === 200) message.success(pageText('pages.configurationSaved'));
    else message.error(res.message || pageText('pages.failedToSaveConfiguration'));
  } catch {
    message.error(pageText('pages.failedToSaveConfiguration'));
  }
};

const runToolsOnce = async () => {
  toolsRunLoading.value = true;
  try {
    const res = await request.post('/github_threat/tools_run_once');
    if (res.code === 200) {
      message.success(res.data?.msg || pageText('pages.securityToolMonitoringTaskQueued'));
      toolsConfig.is_running = true;
      fetchToolsConfig();
    } else {
      message.warning(res.data?.msg || res.message || pageText('pages.unableToStart'));
    }
  } catch {
    message.error(pageText('pages.requestFailed'));
  } finally {
    toolsRunLoading.value = false;
  }
};

const fetchHackersConfig = async () => {
  try {
    const res = await request.get('/github_threat/hackers_config');
    if (res.code === 200 && res.data) {
      const wasRunning = hackersConfig.is_running;
      hackersConfig.enabled = res.data.enabled;
      hackersConfig.interval = res.data.interval;
      hackersConfig.is_running = !!res.data.is_running;
      if (wasRunning && !hackersConfig.is_running) fetchHackersData();
    }
  } catch (e) { console.error(e); }
};

const saveHackersConfig = async () => {
  try {
    const res = await request.post('/github_threat/hackers_config', hackersConfig);
    if (res.code === 200) message.success(pageText('pages.configurationSaved'));
    else message.error(res.message || pageText('pages.failedToSaveConfiguration'));
  } catch {
    message.error(pageText('pages.failedToSaveConfiguration'));
  }
};

const runHackersOnce = async () => {
  hackersRunLoading.value = true;
  try {
    const res = await request.post('/github_threat/hackers_run_once');
    if (res.code === 200) {
      message.success(res.data?.msg || pageText('pages.researcherMonitoringTaskQueued'));
      hackersConfig.is_running = true;
      fetchHackersConfig();
    } else {
      message.warning(res.data?.msg || res.message || pageText('pages.unableToStart'));
    }
  } catch {
    message.error(pageText('pages.requestFailed'));
  } finally {
    hackersRunLoading.value = false;
  }
};

// ==========================================
// 当前激活页签多选状态与全局刷新/静默轮询
// ==========================================
const activeSelectedKeys = computed(() => {
  if (mainTab.value === 'dlp') {
    if (activeTabDlp.value === 'findings') {
      return findingsGroupMode.value === 'repo' ? findingsRepoSelectedKeys.value : findingsSelectedRowKeys.value;
    }
    if (activeTabDlp.value === 'scheduler') return schedulerSelectedRowKeys.value;
    if (activeTabDlp.value === 'task') return taskSelectedRowKeys.value;
  } else {
    if (activeTabTi.value === 'cve_history') return cveSelectedRowKeys.value;
    if (activeTabTi.value === 'tools_target') return toolsSelectedRowKeys.value;
    if (activeTabTi.value === 'hackers_target') return hackersSelectedRowKeys.value;
  }
  return [];
});

const clearActiveSelection = () => {
  findingsSelectedRowKeys.value = [];
  findingsRepoSelectedKeys.value = [];
  schedulerSelectedRowKeys.value = [];
  taskSelectedRowKeys.value = [];
  cveSelectedRowKeys.value = [];
  toolsSelectedRowKeys.value = [];
  hackersSelectedRowKeys.value = [];
};

const refreshActiveView = async () => {
  isRefreshingActive.value = true;
  try {
    await fetchFindingsStats();
    if (mainTab.value === 'dlp') {
      if (activeTabDlp.value === 'findings') await fetchFindingsData();
      else if (activeTabDlp.value === 'scheduler') await fetchSchedulerData();
      else if (activeTabDlp.value === 'task') await fetchTaskData();
    } else {
      if (activeTabTi.value === 'cve_history') await Promise.all([fetchCveData(), fetchCveConfig()]);
      else if (activeTabTi.value === 'tools_target') await Promise.all([fetchToolsData(), fetchToolsConfig()]);
      else if (activeTabTi.value === 'hackers_target') await Promise.all([fetchHackersData(), fetchHackersConfig()]);
    }
  } finally {
    isRefreshingActive.value = false;
  }
};

let backgroundPollTimer = null;
const startBackgroundPoll = () => {
  stopBackgroundPoll();
  backgroundPollTimer = setInterval(() => {
    if (!autoPollEnabled.value) return;
    if (runningRadarCount.value > 0) {
      fetchCveConfig();
      fetchToolsConfig();
      fetchHackersConfig();
    }
    if (findingsStats.running_tasks > 0) {
      fetchFindingsStats();
      if (mainTab.value === 'dlp') {
        if (activeTabDlp.value === 'task') fetchTaskData();
        else if (activeTabDlp.value === 'findings') fetchFindingsData();
      }
    }
  }, 6000);
};

const stopBackgroundPoll = () => {
  if (backgroundPollTimer) {
    clearInterval(backgroundPollTimer);
    backgroundPollTimer = null;
  }
};

watch(() => route.query.tab, (newTab) => {
  applyRouteTabQuery(newTab);
});

watch(activeTabDlp, (newTab) => {
  if (newTab === 'findings') fetchFindingsData();
  else if (newTab === 'scheduler') fetchSchedulerData();
  else if (newTab === 'task') fetchTaskData();
});

watch(activeTabTi, (newTab) => {
  if (newTab === 'cve_history') fetchCveData();
  else if (newTab === 'tools_target') fetchToolsData();
  else if (newTab === 'hackers_target') fetchHackersData();
});

onMounted(() => {
  applyRouteTabQuery(route.query.tab);
  fetchFindingsStats();
  fetchFindingsData();
  fetchSchedulerData();
  fetchTaskData();
  fetchToolsData();
  fetchHackersData();
  fetchCveData();
  fetchCveConfig();
  fetchToolsConfig();
  fetchHackersConfig();
  fetchTokenStatus();
  startBackgroundPoll();
});

onActivated(() => {
  startBackgroundPoll();
});

onDeactivated(() => {
  historyDrawerVisible.value = false;
  findingDetailDrawerVisible.value = false;
  ignoredDrawerVisible.value = false;
  toolNotesDrawerVisible.value = false;
  schedulerModalVisible.value = false;
  taskModalVisible.value = false;
  toolModalVisible.value = false;
  hackerModalVisible.value = false;
  resultDrawerVisible.value = false;
  stopResultSyslogTimer();
  stopBackgroundPoll();
});

onUnmounted(() => {
  stopResultSyslogTimer();
  stopBackgroundPoll();
});
</script>

<style scoped>
.hero-brand-icon {
  margin-right: 6px;
  color: var(--arl-theme-color);
}

.gh-token-pill-wrap {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.gh-token-pill {
  margin: 0;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
}

.gh-auto-poll {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.gh-auto-poll-label {
  font-size: 12px;
  color: var(--arl-text-secondary);
}

.gh-token-alert {
  margin-top: 10px;
}

.gh-settings-link {
  margin-left: 8px;
  font-weight: 500;
}

.gh-sub-tabs {
  margin-top: 10px;
}

.gh-tab-label {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.gh-tab-badge {
  font-family: var(--arl-font-mono);
  font-size: 11px;
  padding: 0 6px;
  border-radius: 9px;
  background: var(--arl-bg-hover);
  color: var(--arl-text-secondary);
}

.gh-tab-badge.is-highlight {
  background: rgba(250, 173, 20, 0.2);
  color: #d48806;
  font-weight: 600;
}

.gh-tab-badge.is-running {
  background: rgba(24, 144, 255, 0.16);
  color: var(--arl-theme-color);
  font-weight: 600;
}

.gh-findings-toolbar-wrap {
  width: 100%;
}

.gh-width-110 { width: 110px; }
.gh-width-120 { width: 120px; }
.gh-width-130 { width: 130px; }
.gh-width-160 { width: 160px; }
.gh-width-170 { width: 170px; }
.gh-width-180 { width: 180px; }
.gh-width-220 { width: 220px; }
.page-width-180 { width: 180px; }

.gh-input-icon {
  color: var(--arl-text-color);
  opacity: 0.35;
}

.gh-inline-switch-box,
.gh-schedule-strip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
  padding: 3px 8px;
  font-size: 12px;
  color: var(--arl-text-color);
}

.gh-repo-file-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.gh-repo-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.gh-repo-link,
.gh-primary-link {
  color: var(--arl-theme-color);
  font-weight: 500;
  word-break: break-all;
}

.gh-path-link {
  font-family: var(--arl-font-mono);
  font-size: 12px;
  word-break: break-all;
  color: var(--arl-text-color);
}

.gh-path-link:hover {
  color: var(--arl-theme-color);
}

.gh-source-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.gh-source-names {
  font-size: 12px;
  color: var(--arl-text-secondary);
}

.gh-triage-cell,
.gh-meta-stack {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.gh-triage-note-preview {
  font-size: 12px;
  color: var(--arl-text-secondary);
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.gh-time-text {
  font-size: 12px;
  color: var(--arl-text-secondary);
}

.gh-row-actions {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.gh-link-btn {
  padding: 0 4px;
}

.gh-clickable-tag {
  cursor: pointer;
}

.gh-breakdown-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
}

.gh-repo-expanded-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  padding: 6px 8px;
}

.gh-repo-expanded-item {
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
  padding: 8px 10px;
  background: var(--arl-bg-card);
}

.gh-repo-expanded-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 6px;
}

.gh-cve-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.gh-cve-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.gh-cve-link {
  color: #cf1322;
  font-weight: 600;
  font-size: 13px;
}

:global(body.dark-mode) .gh-cve-link {
  color: #ff7875;
}

.gh-cve-quick-ops {
  display: flex;
  align-items: center;
  gap: 8px;
}

.gh-mini-op {
  padding: 0;
  height: auto;
  font-size: 12px;
}

.gh-researcher-cell {
  display: flex;
  align-items: center;
  gap: 10px;
}

.gh-sub-caption {
  font-size: 12px;
  color: var(--arl-text-secondary);
  margin-top: 2px;
}

.gh-drawer-summary-bar {
  margin-bottom: 14px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
  padding: 10px 14px;
  border-radius: 6px;
}

.gh-drawer-submeta {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.gh-drawer-title-name {
  font-weight: 600;
  font-size: 14px;
}

.gh-drawer-filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 12px;
  align-items: center;
}

.gh-drawer-triage-inline {
  margin-top: 6px;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 4px;
}

.gh-triage-editor {
  margin-top: 16px;
  padding: 12px 14px;
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
  background: var(--arl-bg-light);
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.gh-editor-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.gh-editor-row-col {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.gh-editor-label {
  font-size: 13px;
  font-weight: 500;
  color: var(--arl-text-color);
}

.gh-editor-actions {
  display: flex;
  justify-content: flex-end;
}

.gh-ignored-add-row {
  display: flex;
  gap: 8px;
  margin-bottom: 14px;
}

.gh-release-notes-box {
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--arl-font-mono);
  font-size: 12px;
  line-height: 1.6;
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
  padding: 12px 14px;
  max-height: 540px;
  overflow-y: auto;
  color: var(--arl-text-color);
}

.gh-log-terminal {
  height: 480px;
  overflow-y: auto;
}

.gh-log-line {
  margin-bottom: 4px;
  word-break: break-all;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.08);
  padding-bottom: 2px;
}

.gh-log-time {
  margin-right: 8px;
  opacity: 0.7;
}

.gh-log-level {
  font-weight: bold;
  margin-right: 8px;
  color: #52c41a;
}

.gh-log-level.is-error { color: #ff4d4f; }
.gh-log-level.is-warning { color: #faad14; }

.gh-log-title {
  margin-right: 8px;
}

.gh-preset-block {
  margin-top: 8px;
}

.gh-preset-label {
  font-size: 12px;
  color: var(--arl-text-secondary);
  margin-bottom: 6px;
}

.gh-preset-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.gh-builtin-info {
  margin-top: 6px;
}

.gh-bucket-list {
  margin: 6px 0 0;
  padding-left: 16px;
  font-family: var(--arl-font-mono);
  font-size: 11px;
}

.page-flush-bottom { margin-bottom: 0; }
.page-placeholder { color: var(--arl-text-color); opacity: 0.3; }
.page-summary-caption { color: var(--arl-text-secondary); font-size: 12px; }
.page-log-empty { color: rgba(255, 255, 255, 0.45); font-style: italic; }
.page-modal-form { margin-top: 16px; }
</style>
