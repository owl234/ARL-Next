<template>
  <div class="arl-page-container" :class="{ 'page-wide-text': taskLocale !== 'zh-CN' }">
    <!-- 1. 吸顶操作栏与英雄头部卡片 (一体化常驻吸附在页面最顶部) -->
    <div ref="actionBarRef" class="arl-hero-card">
      <!-- 顶层主栏：标题 + 视角切换胶囊 + 全局控制与主创建按钮 -->
      <div class="arl-hero-unified-bar">
        <!-- 左侧：页面标识与顶层 Tab 切换胶囊 -->
        <div class="arl-hero-left">
          <div class="arl-hero-title">
            <span class="title-text">{{ taskText('tasks.taskManagement') }}</span>
          </div>
          <div class="arl-capsule-switcher">
            <button
              type="button"
              class="arl-capsule-item"
              :class="{ 'is-active': activeMainTab === 'enterprise' }"
              @click="handleMainTabChange('enterprise')"
              :title="taskText('tasks.switchToEnterpriseOsintTasks')"
            >
              <bank-outlined class="capsule-icon" />
              <span>{{ taskText('tasks.enterpriseOsintTasks') }}</span>
              <span class="arl-capsule-count" v-if="enterpriseMetricCounts.running > 0">
                <span class="arl-capsule-dot is-pulse"></span>
                {{ enterpriseMetricCounts.running }} {{ taskText('tasks.running') }}
              </span>
            </button>
            <button
              type="button"
              class="arl-capsule-item"
              :class="{ 'is-active': activeMainTab === 'task' }"
              @click="handleMainTabChange('task')"
              :title="taskText('tasks.switchToAssetDiscoveryTasksAsm')"
            >
              <global-outlined class="capsule-icon" />
              <span>{{ taskText('tasks.assetDiscoveryTasks') }}</span>
              <span class="arl-capsule-count" v-if="taskMetricCounts.running > 0">
                <span class="arl-capsule-dot is-pulse"></span>
                {{ taskMetricCounts.running }} {{ taskText('tasks.running') }}
              </span>
            </button>
          </div>
        </div>

        <!-- 右侧：全局自适应静默轮询开关 + 手动刷新 + 主操作按钮 -->
        <div class="arl-hero-right">
          <a-tooltip :title="autoRefreshEnabled ? taskText('tasks.autoRefreshIsOnRefreshSilentlyEvery9') : taskText('tasks.autoRefreshPaused')">
            <div class="auto-refresh-toggle">
              <a-switch
                v-model:checked="autoRefreshEnabled"
                size="small"
                @change="handleAutoRefreshToggle"
              />
              <span class="toggle-label">{{ taskText('tasks.autoRefresh') }}</span>
            </div>
          </a-tooltip>

          <a-tooltip :title="lastRefreshTimeText ? taskText('tasks.lastUpdatedTime', { time: lastRefreshTimeText }) : taskText('tasks.refreshTheTaskList')">
            <a-button
              size="small"
              class="task-refresh-btn"
              :loading="isRefreshing"
              @click="handleManualRefresh"
            >
              <template #icon><reload-outlined /></template>
              {{ taskText('tasks.refresh') }}
            </a-button>
          </a-tooltip>

          <a-divider type="vertical" style="height: 18px; margin: 0 4px;" />

          <!-- 企业测绘专属操作 -->
          <template v-if="activeMainTab === 'enterprise'">
            <a-button type="primary" size="small" class="primary-action-btn" @click="showTycModal">
              <template #icon><plus-outlined /></template>
              {{ taskText('tasks.newEnterpriseOsintTask') }}
            </a-button>
          </template>

          <!-- 资产侦查专属操作 -->
          <template v-else-if="activeMainTab === 'task'">
            <a-button type="primary" size="small" class="primary-action-btn" @click="showModal">
              <template #icon><plus-outlined /></template>
              {{ taskText('tasks.newDiscoveryTask') }}
            </a-button>
            <a-button size="small" @click="openFofaModal">
              <template #icon><thunderbolt-outlined /></template>
              {{ taskText('tasks.createFofaTask') }}
            </a-button>
            <a-button size="small" @click="goToGlobalView">
              <template #icon><compass-outlined /></template>
              {{ taskText('tasks.globalView') }}
            </a-button>
          </template>
        </div>
      </div>

      <!-- 中层：任务运行态 4 维状态概览指标卡 (点击卡片可联动过滤) -->
      <div class="task-metric-cards-row">
        <div
          class="metric-stat-card"
          :class="{ active: currentStatusFilter === '' }"
          @click="toggleStatusFilter('')"
          :title="taskText('tasks.showAllTasks')"
        >
          <div class="stat-card-inner">
            <div class="stat-icon-box all">
              <appstore-outlined />
            </div>
            <div class="stat-info">
              <div class="stat-label">{{ taskText('tasks.allTasks') }}</div>
              <div class="stat-value">{{ currentTotalCount }}</div>
            </div>
          </div>
        </div>

        <div
          class="metric-stat-card"
          :class="{ active: currentStatusFilter === 'active' }"
          @click="toggleStatusFilter('active')"
          :title="taskText('tasks.showRunningAndQueuedTasks')"
        >
          <div class="stat-card-inner">
            <div class="stat-icon-box running">
              <sync-outlined :spin="currentRunningCount > 0" />
            </div>
            <div class="stat-info">
              <div class="stat-label">
                <span>{{ taskText('tasks.runningQueued') }}</span>
                <span v-if="currentRunningCount > 0" class="mini-pulse-beacon"></span>
              </div>
              <div class="stat-value running">{{ currentRunningCount }}</div>
            </div>
          </div>
        </div>

        <div
          class="metric-stat-card"
          :class="{ active: currentStatusFilter === 'done' }"
          @click="toggleStatusFilter('done')"
          :title="taskText('tasks.showCompletedTasks')"
        >
          <div class="stat-card-inner">
            <div class="stat-icon-box done">
              <check-circle-outlined />
            </div>
            <div class="stat-info">
              <div class="stat-label">{{ taskText('tasks.completed') }}</div>
              <div class="stat-value done">{{ currentDoneCount }}</div>
            </div>
          </div>
        </div>

        <div
          class="metric-stat-card"
          :class="{ active: currentStatusFilter === 'abnormal' }"
          @click="toggleStatusFilter('abnormal')"
          :title="taskText('tasks.showFailedAndStoppedTasks')"
        >
          <div class="stat-card-inner">
            <div class="stat-icon-box error">
              <close-circle-outlined />
            </div>
            <div class="stat-info">
              <div class="stat-label">{{ taskText('tasks.failedStopped') }}</div>
              <div class="stat-value error">{{ currentAbnormalCount }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 下层：常驻核心检索栏 + 可折叠高级筛选 -->
      <div class="task-filter-container">
        <!-- 1. 企业测绘任务检索栏 -->
        <template v-if="activeMainTab === 'enterprise'">
          <div class="resident-filter-bar">
            <div class="filter-inputs-group">
              <a-input
                v-model:value="reconSearchForm.name"
                :placeholder="taskText('tasks.taskName')"
                style="width: 220px;"
                size="small"
                allowClear
                @pressEnter="onReconSearch"
              >
                <template #prefix><search-outlined class="input-prefix-icon" /></template>
              </a-input>

              <a-input
                v-model:value="reconSearchForm.target"
                :placeholder="taskText('tasks.searchTargetOrganization')"
                style="width: 220px;"
                size="small"
                allowClear
                @pressEnter="onReconSearch"
              >
                <template #prefix><bank-outlined class="input-prefix-icon" /></template>
              </a-input>

              <a-select
                v-model:value="reconSearchForm.status"
                :placeholder="taskText('tasks.taskStatus')"
                style="width: 140px;"
                size="small"
                allowClear
                @change="onReconSearch"
              >
                <a-select-option value="">{{ taskText('tasks.allStatuses') }}</a-select-option>
                <a-select-option value="active">
                  <span class="status-option-item"><span class="status-dot running"></span> {{ taskText('tasks.runningQueued') }}</span>
                </a-select-option>
                <a-select-option value="running">
                  <span class="status-option-item"><span class="status-dot running"></span> {{ taskText('tasks.running') }}</span>
                </a-select-option>
                <a-select-option value="waiting">
                  <span class="status-option-item"><span class="status-dot waiting"></span> {{ taskText('tasks.waiting') }}</span>
                </a-select-option>
                <a-select-option value="done">
                  <span class="status-option-item"><span class="status-dot done"></span> {{ taskText('tasks.completed') }}</span>
                </a-select-option>
                <a-select-option value="stop">
                  <span class="status-option-item"><span class="status-dot stop"></span> {{ taskText('tasks.stopped') }}</span>
                </a-select-option>
                <a-select-option value="error">
                  <span class="status-option-item"><span class="status-dot error"></span> {{ taskText('tasks.failed') }}</span>
                </a-select-option>
                <a-select-option value="abnormal">
                  <span class="status-option-item"><span class="status-dot error"></span> {{ taskText('tasks.failedStopped') }}</span>
                </a-select-option>
              </a-select>

              <a-range-picker
                v-model:value="reconSearchForm.dateRange"
                :presets="rangePresets"
                :placeholder="[taskText('tasks.startDate'), taskText('tasks.endDate')]"
                format="YYYY-MM-DD"
                style="width: 240px;"
                size="small"
                allowClear
                @change="onReconSearch"
              />
            </div>

            <div class="filter-actions-group">
              <a-button size="small" @click="onReconSearch"><template #icon><search-outlined /></template>{{ taskText('tasks.search') }}</a-button>
              <a-button size="small" @click="resetReconSearch">{{ taskText('tasks.reset') }}</a-button>
            </div>
          </div>
        </template>

        <!-- 2. 资产侦查任务检索栏 (常驻 + 高级折叠) -->
        <template v-else-if="activeMainTab === 'task'">
          <div class="resident-filter-bar">
            <div class="filter-inputs-group">
              <a-input
                v-model:value="searchForm.name"
                :placeholder="taskText('tasks.taskName')"
                style="width: 210px;"
                size="small"
                allowClear
                @pressEnter="onSearch"
              >
                <template #prefix><search-outlined class="input-prefix-icon" /></template>
              </a-input>

              <a-input
                v-model:value="searchForm.target"
                :placeholder="taskText('tasks.targetIpDomainCidr')"
                style="width: 210px;"
                size="small"
                allowClear
                @pressEnter="onSearch"
              >
                <template #prefix><global-outlined class="input-prefix-icon" /></template>
              </a-input>

              <a-select
                v-model:value="searchForm.status"
                :placeholder="taskText('tasks.taskStatus')"
                style="width: 140px;"
                size="small"
                allowClear
                @change="onSearch"
              >
                <a-select-option value="">{{ taskText('tasks.allStatuses') }}</a-select-option>
                <a-select-option value="active">
                  <span class="status-option-item"><span class="status-dot running"></span> {{ taskText('tasks.runningQueued') }}</span>
                </a-select-option>
                <a-select-option value="running">
                  <span class="status-option-item"><span class="status-dot running"></span> {{ taskText('tasks.running') }}</span>
                </a-select-option>
                <a-select-option value="waiting">
                  <span class="status-option-item"><span class="status-dot waiting"></span> {{ taskText('tasks.waiting') }}</span>
                </a-select-option>
                <a-select-option value="done">
                  <span class="status-option-item"><span class="status-dot done"></span> {{ taskText('tasks.completed') }}</span>
                </a-select-option>
                <a-select-option value="stop">
                  <span class="status-option-item"><span class="status-dot stop"></span> {{ taskText('tasks.stopped') }}</span>
                </a-select-option>
                <a-select-option value="error">
                  <span class="status-option-item"><span class="status-dot error"></span> {{ taskText('tasks.failed') }}</span>
                </a-select-option>
                <a-select-option value="abnormal">
                  <span class="status-option-item"><span class="status-dot error"></span> {{ taskText('tasks.failedStopped') }}</span>
                </a-select-option>
              </a-select>
            </div>

            <div class="filter-actions-group">
              <a-button size="small" @click="onSearch"><template #icon><search-outlined /></template>{{ taskText('tasks.search') }}</a-button>
              <a-button size="small" @click="resetSearch">{{ taskText('tasks.reset') }}</a-button>
              <a-button
                size="small"
                :type="isAdvancedFilterOpen ? 'primary' : 'default'"
                :ghost="isAdvancedFilterOpen"
                @click="isAdvancedFilterOpen = !isAdvancedFilterOpen"
              >
                <template #icon><filter-outlined /></template>
                {{ isAdvancedFilterOpen ? taskText('tasks.hideFilters') : taskText('tasks.advancedFilters') }}
                <a-badge
                  v-if="activeAdvancedFilterCount > 0"
                  :count="activeAdvancedFilterCount"
                  :number-style="{ backgroundColor: 'var(--arl-theme-color)', marginLeft: '4px' }"
                />
              </a-button>
            </div>
          </div>

          <!-- 高级筛选折叠卡片 -->
          <div v-show="isAdvancedFilterOpen" class="advanced-filter-panel">
            <div class="advanced-filter-grid">
              <div class="filter-item">
                <span class="filter-label">{{ taskText('tasks.taskId') }}:</span>
                <a-input
                  v-model:value="searchForm.task_id"
                  :placeholder="taskText('tasks.enterA24CharacterTaskId')"
                  style="width: 220px;"
                  size="small"
                  allowClear
                  @pressEnter="onSearch"
                />
              </div>

              <div class="filter-item">
                <span class="filter-label">{{ taskText('tasks.taskType') }}</span>
                <a-select
                  v-model:value="searchForm.type"
                  :placeholder="taskText('tasks.allTypes')"
                  style="width: 180px;"
                  size="small"
                  allowClear
                  @change="onSearch"
                >
                  <a-select-option value="task">{{ taskText('tasks.assetDiscoveryTasks') }}</a-select-option>
                  <a-select-option value="monitor">{{ taskText('tasks.assetMonitoringTask') }}</a-select-option>
                  <a-select-option value="risk_cruising">{{ taskText('tasks.riskScanningTask') }}</a-select-option>
                  <a-select-option value="asset_site_update">{{ taskText('tasks.websiteAssetUpdate') }}</a-select-option>
                  <a-select-option value="asset_wih_update">{{ taskText('tasks.wihMonitoringTask') }}</a-select-option>
                </a-select>
              </div>

              <div class="filter-item">
                <span class="filter-label">{{ taskText('tasks.syncStatus') || '资产同步状态' }}</span>
                <a-select
                  v-model:value="searchForm.sync_status"
                  :placeholder="taskText('tasks.allStatuses') || '全部状态'"
                  style="width: 130px;"
                  size="small"
                  allowClear
                  @change="onSearch"
                >
                  <a-select-option value="waiting">{{ taskText('tasks.syncWaiting') || '等待同步' }}</a-select-option>
                  <a-select-option value="running">{{ taskText('tasks.syncRunning') || '同步中' }}</a-select-option>
                  <a-select-option value="default">{{ taskText('tasks.syncDone') || '已同步' }}</a-select-option>
                  <a-select-option value="error">{{ taskText('tasks.syncFailedLabel') || '同步失败' }}</a-select-option>
                </a-select>
              </div>

              <div class="filter-item">
                <span class="filter-label">{{ taskText('tasks.websitesLabel') }}</span>
                <a-input-group compact class="count-input-group">
                  <a-select v-model:value="searchForm.site_operator" size="small" style="width: 65px;">
                    <a-select-option value="=">=</a-select-option>
                    <a-select-option value=">">&gt;</a-select-option>
                    <a-select-option value="<">&lt;</a-select-option>
                  </a-select>
                  <a-input
                    v-model:value="searchForm.site_count"
                    :placeholder="taskText('tasks.count')"
                    style="width: 115px;"
                    size="small"
                    allowClear
                    @pressEnter="onSearch"
                  />
                </a-input-group>
              </div>

              <div class="filter-item">
                <span class="filter-label">{{ taskText('tasks.domainsLabel') }}</span>
                <a-input-group compact class="count-input-group">
                  <a-select v-model:value="searchForm.domain_operator" size="small" style="width: 65px;">
                    <a-select-option value="=">=</a-select-option>
                    <a-select-option value=">">&gt;</a-select-option>
                    <a-select-option value="<">&lt;</a-select-option>
                  </a-select>
                  <a-input
                    v-model:value="searchForm.domain_count"
                    :placeholder="taskText('tasks.count')"
                    style="width: 115px;"
                    size="small"
                    allowClear
                    @pressEnter="onSearch"
                  />
                </a-input-group>
              </div>

              <div class="filter-item">
                <span class="filter-label">{{ taskText('tasks.wihRecords') }}</span>
                <a-input-group compact class="count-input-group">
                  <a-select v-model:value="searchForm.wih_operator" size="small" style="width: 65px;">
                    <a-select-option value="=">=</a-select-option>
                    <a-select-option value=">">&gt;</a-select-option>
                    <a-select-option value="<">&lt;</a-select-option>
                  </a-select>
                  <a-input
                    v-model:value="searchForm.wih_count"
                    :placeholder="taskText('tasks.count')"
                    style="width: 115px;"
                    size="small"
                    allowClear
                    @pressEnter="onSearch"
                  />
                </a-input-group>
              </div>
            </div>

            <div class="advanced-filter-footer">
              <a-button size="small" type="link" @click="resetAdvancedFilters">{{ taskText('tasks.clearAdvancedFilters') }}</a-button>
              <a-button size="small" type="link" @click="isAdvancedFilterOpen = false">{{ taskText('tasks.collapse') }}</a-button>
            </div>
          </div>
        </template>
      </div>
    </div>

    <!-- 2. 动态浮动/吸附批量操作条 (有选中行时激活) -->
    <div
      v-if="(activeMainTab === 'enterprise' && enterpriseSelectedRowKeys.length > 0) || (activeMainTab === 'task' && hasSelected)"
      class="floating-batch-action-bar"
    >
      <div class="batch-left">
        <span class="selected-count-badge">
          {{ taskText('tasks.selected') }} <b>{{ activeMainTab === 'enterprise' ? enterpriseSelectedRowKeys.length : selectedRowKeys.length }}</b> {{ taskText('tasks.tasks') }}
        </span>
      </div>

      <div class="batch-right">
        <!-- 企业测绘批量操作 -->
        <template v-if="activeMainTab === 'enterprise'">
          <a-popconfirm
            :title="taskText('tasks.restartTheSelectedTasks')"
            :ok-text="taskText('tasks.confirm')"
            :cancel-text="taskText('tasks.cancel')"
            @confirm="handleBatchRestartEnterprise"
          >
            <a-button size="small">
              <template #icon><sync-outlined /></template>
              {{ taskText('tasks.restartSelected') }}
            </a-button>
          </a-popconfirm>

          <a-button size="small" @click="handleBatchExportEnterprise">
            <template #icon><export-outlined /></template>
            {{ taskText('tasks.exportSelected') }}
          </a-button>

          <a-popconfirm
            :title="taskText('tasks.deleteTheSelectedEnterpriseTasks')"
            :ok-text="taskText('tasks.confirm')"
            :cancel-text="taskText('tasks.cancel')"
            :disabled="enterpriseBatchDeleting"
            @confirm="handleBatchDeleteEnterprise"
          >
            <a-button
              size="small"
              danger
              :loading="enterpriseBatchDeleting"
              :disabled="enterpriseBatchDeleting"
            >
              <template #icon><delete-outlined /></template>
              {{ taskText('tasks.deleteSelected') }}
            </a-button>
          </a-popconfirm>

          <a-button size="small" type="link" @click="enterpriseSelectedRowKeys = []">{{ taskText('tasks.clearSelection') }}</a-button>
        </template>

        <!-- 资产侦查批量操作 -->
        <template v-else-if="activeMainTab === 'task'">
          <a-button size="small" @click="handleBatchStop">
            <template #icon><stop-outlined /></template>
            {{ taskText('tasks.stopSelected') }}
          </a-button>

          <a-dropdown>
            <template #overlay>
              <a-menu @click="handleBatchExport">
                <a-menu-item key="cip">{{ taskText('tasks.exportSelectedCClassNetworks') }}</a-menu-item>
                <a-menu-item key="domain">{{ taskText('tasks.exportSelectedDomains') }}</a-menu-item>
                <a-menu-item key="ip">{{ taskText('tasks.exportSelectedIps') }}</a-menu-item>
                <a-menu-item key="ip_port">{{ taskText('tasks.exportSelectedIpPortPairs') }}</a-menu-item>
                <a-menu-item key="site">{{ taskText('tasks.exportSelectedWebsites') }}</a-menu-item>
                <a-menu-item key="url">{{ taskText('tasks.exportSelectedUrls') }}</a-menu-item>
                <a-menu-item key="wih">{{ taskText('tasks.exportSelectedWihRecords') }}</a-menu-item>
              </a-menu>
            </template>
            <a-button size="small">
              <template #icon><export-outlined /></template>
              {{ taskText('tasks.exportSelected') }} <down-outlined />
            </a-button>
          </a-dropdown>

          <a-button size="small" danger @click="handleBatchDelete">
            <template #icon><delete-outlined /></template>
            {{ taskText('tasks.deleteSelected') }}
          </a-button>

          <a-button size="small" type="link" @click="selectedRowKeys = []">{{ taskText('tasks.clearSelection') }}</a-button>
        </template>
      </div>
    </div>

    <!-- 3. 主数据表格容器 -->
    <div class="arl-table-card">
      <!-- A. 企业测绘任务表格 -->
      <template v-if="activeMainTab === 'enterprise'">
        <a-table
          :sticky="stickyConfig"
          :row-selection="{ selectedRowKeys: enterpriseSelectedRowKeys, onChange: onEnterpriseSelectChange, preserveSelectedRowKeys: true }"
          :dataSource="enterpriseTaskList"
          :columns="enterpriseColumns"
          :loading="enterpriseLoading"
          :pagination="false"
          :scroll="{ x: 'max-content' }"
          :rowKey="(record) => record._id"
          size="small"
          class="modern-task-table"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'name'">
              <a class="task-title-link" @click="viewEnterpriseTask(record)">{{ record.name }}</a>
            </template>

            <template v-else-if="column.key === 'target'">
              <span class="task-target-text" :title="record.target">{{ record.target }}</span>
            </template>

            <template v-else-if="column.key === 'task_type'">
              <a-tag v-if="record.task_type === 'tyc'" color="blue" style="margin: 0; font-size: 12px; border-radius: 4px; padding: 1px 6px;">
                {{ taskText('tasks.combinedOsint') }}
              </a-tag>
              <a-tag v-else color="purple" style="margin: 0; font-size: 12px; border-radius: 4px; padding: 1px 6px;">
                {{ taskText('tasks.officialIcpRecords') }}
              </a-tag>
            </template>

            <template v-else-if="column.key === 'policy_options'">
              <a-tooltip v-if="hasEnterpriseOptions(record)" placement="bottom">
                <template #title>
                  <div class="options-tooltip-content">
                    <div class="tooltip-header">
                      {{ record.task_type === 'tyc' ? taskText('tasks.enterpriseOsintConfigurationCombinedSources') : taskText('tasks.enterpriseOsintConfigurationOfficialIcpRecords') }}
                    </div>
                    <template v-if="record.task_type === 'tyc'">
                      <div class="tooltip-section-title">{{ taskText('tasks.investmentTraversal') }}</div>
                      <div class="option-item-line">{{ taskText('tasks.investmentDepth') }} {{ record.depth || 1 }} {{ taskText('tasks.levels') }}</div>
                      <div class="option-item-line">{{ taskText('tasks.minimumOwnership') }} {{ record.invest_ratio !== undefined && record.invest_ratio !== null ? record.invest_ratio : 50 }}%</div>
                      <div class="option-item-line">{{ taskText('tasks.officialIcpCrossCheck') }} {{ record.enable_icp !== false ? taskText('tasks.enabled') : taskText('tasks.disabled') }}</div>
                      <div class="tooltip-section-title task-nested-content" >{{ taskText('tasks.assetCategories') }}</div>
                    </template>
                    <div v-for="(item, idx) in getEnterpriseQueryTypeLabels(record)" :key="idx" class="option-item-line">
                      • {{ item }}
                    </div>
                  </div>
                </template>
                <span class="options-badge-trigger">
                  <setting-outlined style="margin-right: 4px; font-size: 11px;" />
                  <span>{{ formatEnterpriseOptionsSummary(record) }}</span>
                </span>
              </a-tooltip>
              <span v-else class="options-badge-trigger" style="cursor: default; opacity: 0.65;">
                <setting-outlined style="margin-right: 4px; font-size: 11px;" />
                <span>{{ taskText('tasks.defaultConfiguration') }}</span>
              </span>
            </template>

            <template v-else-if="column.key === 'status'">
              <a-tag :color="getEnterpriseStatusColor(record.status)" class="task-status-tag">
                <component :is="getEnterpriseStatusIcon(record.status)" :spin="record.status === 'running'" />
                <span>{{ formatEnterpriseStatusText(record.status) }}</span>
              </a-tag>
            </template>

            <template v-else-if="column.key === 'statistic'">
              <div v-if="record.statistic" class="task-stats-capsules">
                <a-tooltip :title="taskText('tasks.coreAssetsCount', { count: (record.statistic.asset_cnt || 0) - (record.statistic.invest_cnt || 0) })">
                  <span class="stat-capsule domain">
                    <span class="stat-lbl">{{ taskText('tasks.core') }}</span>
                    <span class="stat-num">{{ (record.statistic.asset_cnt || 0) - (record.statistic.invest_cnt || 0) }}</span>
                  </span>
                </a-tooltip>
                <a-tooltip v-if="record.statistic.invest_cnt !== undefined" :title="taskText('tasks.investmentsCount', { count: record.statistic.invest_cnt })">
                  <span class="stat-capsule site">
                    <span class="stat-lbl">{{ taskText('tasks.investments') }}</span>
                    <span class="stat-num">{{ record.statistic.invest_cnt }}</span>
                  </span>
                </a-tooltip>
              </div>
              <span v-else style="color: var(--arl-text-secondary);">-</span>
            </template>

            <template v-else-if="column.key === 'sync_status'">
              <span v-if="record.sync_badge_status === 'no_web'" class="sync-empty-text">
                {{ taskText('tasks.noWebsiteAssets') }}
              </span>
              <div v-else-if="record.synced_scope_id" class="synced-badge-wrapper">
                <a-tag
                  color="blue"
                  class="synced-scope-tag"
                  @click="goToScope(record.synced_scope_id, record.synced_scope_name)"
                  :title="taskText('tasks.openThisAssetGroup')"
                >
                  <export-outlined />
                  <span>{{ record.synced_scope_name || taskText('tasks.managed') }}</span>
                </a-tag>
                <a-badge v-if="record.has_increment" class="task-increment-badge" :count="taskText('tasks.newAssets')" />
              </div>
              <span v-else class="unsynced-text">
                <span class="status-dot stop"></span> {{ taskText('tasks.notSynced') }}
              </span>
            </template>

            <template v-else-if="column.key === 'action'">
              <div class="task-action-cell">
                <a-button type="link" size="small" class="primary-table-btn" @click="viewEnterpriseTask(record)">{{ taskText('tasks.details') }}</a-button>

                <template v-if="record.sync_badge_status === 'no_web'">
                  <a-tooltip :title="taskText('tasks.thisTaskHasNoWebsiteAssetsToSync')">
                    <a-button type="link" size="small" disabled>{{ taskText('tasks.sync') }}</a-button>
                  </a-tooltip>
                </template>
                <a-button
                  v-else
                  type="link"
                  size="small"
                  @click="handleSyncEnterprise(record)"
                  :disabled="record.status !== 'done' && record.status !== 'stop'"
                >
                  {{ record.synced_scope_id ? (record.has_increment ? taskText('tasks.syncNewAssets') : taskText('tasks.syncAgain')) : taskText('tasks.sync') }}
                </a-button>

                <a-dropdown>
                  <template #overlay>
                    <a-menu>
                      <a-menu-item key="export" @click="handleExportEnterprise(record)">
                        <export-outlined /> {{ taskText('tasks.exportExcelReport') }}
                      </a-menu-item>
                      <a-menu-item
                        key="stop"
                        :disabled="record.status === 'done' || record.status === 'stop' || record.status === 'error'"
                        @click="handleStopEnterprise(record)"
                      >
                        <stop-outlined /> {{ taskText('tasks.stopTask') }}
                      </a-menu-item>
                      <a-menu-item
                        key="restart"
                        :disabled="record.status === 'running' || record.status === 'waiting'"
                        @click="handleRestartEnterprise(record)"
                      >
                        <sync-outlined /> {{ taskText('tasks.restartTask') }}
                      </a-menu-item>
                      <a-menu-divider />
                      <a-menu-item
                        key="delete"
                        danger
                        :disabled="!['done', 'stop', 'error'].includes(record.status)"
                        :title="!['done', 'stop', 'error'].includes(record.status) ? taskText('tasks.runningOrQueuedTasksCannotBeDeletedStop') : undefined"
                        @click="handleDeleteEnterprise(record)"
                      >
                        <delete-outlined /> {{ taskText('tasks.deleteTask') }}
                      </a-menu-item>
                    </a-menu>
                  </template>
                  <a-button type="text" size="small" class="more-action-btn">
                    {{ taskText('tasks.more') }} <down-outlined class="task-small-caption" />
                  </a-button>
                </a-dropdown>
              </div>
            </template>
          </template>
        </a-table>

        <div class="arl-pagination-bar">
          <div class="pagination-info">
            {{ taskText('tasks.paginationSummary', { pages: Math.ceil(enterprisePagination.total / enterprisePagination.pageSize) || 1, total: enterprisePagination.total }) }}
          </div>
          <a-pagination
            :pageSizeOptions="$pageSizeOptions"
            v-model:current="enterprisePagination.current"
            v-model:pageSize="enterprisePagination.pageSize"
            :total="enterprisePagination.total"
            show-size-changer
            size="small"
            @change="handleEnterpriseTableChange"
            @showSizeChange="handleEnterpriseTableChange"
          />
        </div>
      </template>

      <!-- B. 资产侦查任务表格 -->
      <template v-else-if="activeMainTab === 'task'">
        <a-table
          :sticky="stickyConfig"
          :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange, preserveSelectedRowKeys: true }"
          :dataSource="taskList"
          :columns="columns"
          :loading="loading"
          :pagination="false"
          :scroll="{ x: 'max-content' }"
          :rowKey="(record) => record.task_id || record._id"
          size="small"
          class="modern-task-table"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'name'">
              <a class="task-title-link" @click="viewTask(record)">{{ record.name }}</a>
            </template>

            <template v-else-if="column.key === 'asset_group'">
              <template v-if="getTaskAssetGroupState(record)">
                <a-tooltip :title="getTaskAssetGroupState(record).error || getTaskAssetGroupState(record).label">
                  <a-tag :color="getTaskAssetGroupState(record).color">
                    {{ getTaskAssetGroupState(record).text }}
                  </a-tag>
                </a-tooltip>
                <div class="task-asset-group-name">{{ getTaskAssetGroupState(record).label }}</div>
                <a-tooltip
                  v-if="hasSyncSummary(record)"
                  :title="taskText('tasks.syncSummaryBreakdown', { newCount: record.sync_summary.total_new || 0, updateCount: record.sync_summary.total_update || 0 })"
                >
                  <div class="task-sync-breakdown">
                    {{ taskText('tasks.syncSummaryBadge', { newCount: record.sync_summary.total_new || 0, updateCount: record.sync_summary.total_update || 0 }) }}
                  </div>
                </a-tooltip>
              </template>
              <span v-else>-</span>
            </template>

            <template v-else-if="column.key === 'target'">
              <a-tooltip placement="topLeft">
                <template #title>
                  <div class="target-tooltip-list">
                    <div
                      v-for="(item, index) in (Array.isArray(record.target) ? record.target : String(record.target).split(/[,\s]+/)).filter(Boolean)"
                      :key="index"
                      class="target-item-line"
                    >
                      {{ item.trim() }}
                    </div>
                  </div>
                </template>
                <div class="task-target-cell">
                  {{ record.target }}
                </div>
              </a-tooltip>
            </template>

            <template v-else-if="column.key === 'statistic'">
              <div v-if="record.statistic" class="task-stats-capsules">
                <a-tooltip v-if="record.statistic.site_cnt !== undefined" :title="taskText('tasks.websitesCount', { count: record.statistic.site_cnt })">
                  <span class="stat-capsule site">
                    <span class="stat-lbl">{{ taskText('tasks.websites') }}</span>
                    <span class="stat-num">{{ record.statistic.site_cnt }}</span>
                  </span>
                </a-tooltip>
                <a-tooltip v-if="record.statistic.domain_cnt !== undefined" :title="taskText('tasks.domainsCount', { count: record.statistic.domain_cnt })">
                  <span class="stat-capsule domain">
                    <span class="stat-lbl">{{ taskText('tasks.domains') }}</span>
                    <span class="stat-num">{{ record.statistic.domain_cnt }}</span>
                  </span>
                </a-tooltip>
                <a-tooltip v-if="record.statistic.ip_cnt !== undefined" :title="`IP: ${record.statistic.ip_cnt}`">
                  <span class="stat-capsule ip">
                    <span class="stat-lbl">IP</span>
                    <span class="stat-num">{{ record.statistic.ip_cnt }}</span>
                  </span>
                </a-tooltip>
                <a-tooltip v-if="record.statistic.wih_cnt !== undefined && record.statistic.wih_cnt > 0" :title="`WIH: ${record.statistic.wih_cnt}`">
                  <span class="stat-capsule wih">
                    <span class="stat-lbl">WIH</span>
                    <span class="stat-num">{{ record.statistic.wih_cnt }}</span>
                  </span>
                </a-tooltip>
                <a-tooltip v-if="record.statistic.vuln_cnt !== undefined && record.statistic.vuln_cnt > 0" :title="taskText('tasks.risksCount', { count: record.statistic.vuln_cnt })">
                  <span class="stat-capsule vuln">
                    <span class="stat-lbl">{{ taskText('tasks.risks') }}</span>
                    <span class="stat-num">{{ record.statistic.vuln_cnt }}</span>
                  </span>
                </a-tooltip>
              </div>
              <span v-else style="color: var(--arl-text-secondary);">-</span>
            </template>

            <template v-else-if="column.key === 'options'">
              <a-tooltip placement="bottom">
                <template #title>
                  <div class="options-tooltip-content">
                    <div class="tooltip-header">{{ taskText('tasks.enabledPluginsAndConfiguration') }}</div>
                    <div v-for="(item, index) in getDetailedOptions(record.options)" :key="index" class="option-item-line">
                      • {{ item }}
                    </div>
                  </div>
                </template>
                <span class="options-badge-trigger">
                  <setting-outlined style="margin-right: 4px; font-size: 11px;" />
                  <span>{{ formatOptionsSummary(record.options) }}</span>
                </span>
              </a-tooltip>
            </template>

            <template v-else-if="column.key === 'status'">
              <div class="task-status-cell">
                <a-tooltip v-if="record.service && record.service.length > 0" placement="bottom">
                  <template #title>
                    <div class="service-time-tooltip">
                      <div class="tooltip-header">{{ taskText('tasks.pluginExecutionTimes') }}</div>
                      <div v-for="(item, index) in record.service" :key="index" class="tooltip-row">
                        <span class="service-name">{{ pluginNameMap[item.name] || item.name }}:</span>
                        <span class="service-elapsed">{{ item.elapsed }}</span>
                      </div>
                    </div>
                  </template>
                  <div style="display: inline-block; cursor: pointer;">
                    <a-tag :color="getStatusTagColor(record.status)" class="task-status-tag">
                      <component :is="getStatusIcon(record.status)" :spin="isStatusRunning(record.status)" />
                      <span>{{ formatStatusText(record.status) }}</span>
                    </a-tag>
                  </div>
                </a-tooltip>
                <a-tag v-else :color="getStatusTagColor(record.status)" class="task-status-tag">
                  <component :is="getStatusIcon(record.status)" :spin="isStatusRunning(record.status)" />
                  <span>{{ formatStatusText(record.status) }}</span>
                </a-tag>
                <a-tooltip v-if="hasTaskErrorNotice(record)" placement="top">
                  <template #title>
                    <div class="task-error-tooltip">{{ formatTaskErrorTooltip(record) }}</div>
                  </template>
                  <ExclamationCircleOutlined
                    :class="record.status === 'error' ? 'task-error-notice-icon' : 'task-partial-warn-icon'"
                  />
                </a-tooltip>
              </div>
            </template>

            <template v-else-if="column.key === 'task_id'">
              <a class="task-id-text" @click="viewTask(record)" :title="record._id">{{ record._id }}</a>
            </template>

            <template v-else-if="column.key === 'action'">
              <div class="task-action-cell">
                <a-button type="link" size="small" class="primary-table-btn" @click="viewTask(record)">{{ taskText('tasks.details') }}</a-button>

                <a-button
                  type="link"
                  size="small"
                  :loading="record.restarting"
                  :disabled="(record.status !== 'done' && record.status !== 'stop' && record.status !== 'error') || record.restarting"
                  @click="restartTask(record)"
                >
                  {{ taskText('tasks.restart') }}
                </a-button>

                <a-dropdown>
                  <template #overlay>
                    <a-menu>
                      <a-menu-item
                        key="sync"
                        :disabled="record.status !== 'done' && record.status !== 'stop' && record.status !== 'error'"
                        @click="syncTask(record)"
                      >
                        <sync-outlined /> {{ taskText('tasks.syncToAssetGroup') }}
                      </a-menu-item>
                      <a-menu-item key="export" @click="exportTask(record)">
                        <export-outlined /> {{ taskText('tasks.exportExcelReport') }}
                      </a-menu-item>
                      <a-menu-item
                        key="stop"
                        :disabled="record.status === 'done' || record.status === 'stop' || record.status === 'error'"
                        @click="stopSingleTask(record)"
                      >
                        <stop-outlined /> {{ taskText('tasks.stopTask') }}
                      </a-menu-item>
                      <a-menu-divider />
                      <a-menu-item
                        key="delete"
                        danger
                        :disabled="record.status !== 'done' && record.status !== 'stop' && record.status !== 'error'"
                        @click="deleteSingleTask(record)"
                      >
                        <delete-outlined /> {{ taskText('tasks.deleteTask') }}
                      </a-menu-item>
                    </a-menu>
                  </template>
                  <a-button type="text" size="small" class="more-action-btn">
                    {{ taskText('tasks.more') }} <down-outlined class="task-small-caption" />
                  </a-button>
                </a-dropdown>
              </div>
            </template>
          </template>
        </a-table>

        <div class="arl-pagination-bar">
          <div class="pagination-info">
            {{ taskText('tasks.paginationSummary', { pages: Math.ceil(pagination.total / pagination.pageSize) || 1, total: pagination.total }) }}
          </div>
          <a-pagination
            :pageSizeOptions="$pageSizeOptions"
            v-model:current="pagination.current"
            v-model:pageSize="pagination.pageSize"
            :total="pagination.total"
            show-size-changer
            size="small"
            @change="handleTableChange"
            @showSizeChange="handleTableChange"
          />
        </div>
      </template>
    </div>

    <!-- 4. 添加侦查任务弹窗 (结构化重塑) -->
    <a-modal
      v-model:open="visible"
      :title="taskText('tasks.newAssetDiscoveryTask')"
      @ok="handleOk"
      :confirmLoading="submitLoading"
      width="640px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      :okText="taskText('tasks.createTask')"
      :cancelText="taskText('tasks.cancel')"
      :bodyStyle="{ padding: '16px 24px' }"
    >
      <a-form
        ref="formRef"
        :model="formState"
        layout="vertical"
        :label-wrap="true"
      >
        <!-- A. 基础信息卡片 -->
        <div class="modal-section-card">
          <div class="section-title">
            <span class="section-indicator"></span> {{ taskText('tasks.basicSettings') }}
          </div>
          <a-row :gutter="16">
            <a-col :span="24">
              <a-form-item :label="taskText('tasks.taskName')" name="name" :rules="[{ required: true, message: taskText('tasks.enterATaskName') }]">
                <a-input v-model:value="formState.name" :placeholder="taskText('tasks.exampleGroupBoundaryDiscovery2026q3')" />
              </a-form-item>
            </a-col>
            <a-col :span="24">
              <a-form-item :label="taskText('tasks.assetGroupOptional')" name="related_scope_id"
                :extra="taskText('tasks.resultsWillSyncToThisGroupAfterScanning')">
                <AssetScopeSelect v-model:value="formState.related_scope_id" />
              </a-form-item>
            </a-col>
            <a-col :span="24">
              <a-form-item :label="taskText('tasks.scanTargets')" name="target" :rules="[{ required: true, message: taskText('tasks.enterTargets') }]">
                <a-textarea
                  v-model:value="formState.target"
                  :placeholder="taskText('tasks.enterDomainsExampleComIps111')"
                  :rows="3"
                  style="resize: vertical;"
                />
                <!-- 如实预告任务派生数量：域名逐个建任务，IP/CIDR 合并为一个任务 -->
                <div v-if="fanoutHint.text" class="target-fanout-hint">
                  <InfoCircleOutlined />
                  <span>{{ fanoutHint.text }}</span>
                </div>
              </a-form-item>
            </a-col>
          </a-row>
        </div>

        <!-- B. 字典与策略配置 -->
        <div class="modal-section-card">
          <div class="section-title">
            <span class="section-indicator"></span> {{ taskText('tasks.wordlistsAndPolicies') }}
          </div>
          <a-row :gutter="12">
            <a-col :xs="24" :sm="12">
              <a-form-item :label="taskText('tasks.subdomainWordlist')" name="domain_brute_type" :rules="[{ required: !!formState.domain_brute, message: taskText('tasks.selectASubdomainWordlist') }]">
                <a-select v-model:value="formState.domain_brute_type" :disabled="!formState.domain_brute" :placeholder="taskText('tasks.selectAWordlist')">
                  <a-select-option v-for="item in domainDicts" :key="item.name" :value="item.name">{{ describeDict(item) }}</a-select-option>
                </a-select>
                <div v-if="!formState.domain_brute" class="dict-disabled-hint">{{ taskText('tasks.enableSubdomainEnumerationUnderScanPluginsAndScheduling') }}</div>
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12">
              <a-form-item :label="taskText('tasks.generatedSubdomainWordlist')" name="alt_dns_dict" :rules="[{ required: !!formState.alt_dns, message: taskText('tasks.selectAGeneratedWordlist') }]">
                <a-select v-model:value="formState.alt_dns_dict" :disabled="!formState.alt_dns" :placeholder="taskText('tasks.selectAWordlist')">
                  <a-select-option v-for="item in altDnsDicts" :key="item.name" :value="item.name">{{ describeDict(item) }}</a-select-option>
                </a-select>
                <div v-if="!formState.alt_dns" class="dict-disabled-hint">{{ taskText('tasks.enableDnsWordlistGenerationUnderScanPluginsAnd') }}</div>
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12">
              <a-form-item :label="taskText('tasks.portScanMode')" name="port_scan_type" :rules="[{ required: !!formState.port_scan, message: taskText('tasks.selectAPortScanPolicy') }]">
                <a-select v-model:value="formState.port_scan_type" :disabled="!formState.port_scan" :placeholder="taskText('tasks.selectAPolicy')">
                  <a-select-option v-for="item in portDicts" :key="item.name" :value="item.name">{{ describeDict(item) }}</a-select-option>
                </a-select>
                <div v-if="!formState.port_scan" class="dict-disabled-hint">{{ taskText('tasks.enablePortScanningUnderScanPluginsAndScheduling') }}</div>
              </a-form-item>
            </a-col>
            <a-col :xs="24" :sm="12">
              <a-form-item :label="taskText('tasks.fileDiscoveryWordlist')" name="file_leak_dict" :rules="[{ required: !!formState.file_leak, message: taskText('tasks.selectAFileDiscoveryWordlist') }]">
                <a-select v-model:value="formState.file_leak_dict" :disabled="!formState.file_leak" :placeholder="taskText('tasks.selectAWordlist')">
                  <a-select-option v-for="item in fileLeakDicts" :key="item.name" :value="item.name">{{ describeDict(item) }}</a-select-option>
                </a-select>
                <div v-if="!formState.file_leak" class="dict-disabled-hint">{{ taskText('tasks.enableFileDisclosureChecksUnderScanPluginsAnd') }}</div>
              </a-form-item>
            </a-col>
          </a-row>
        </div>

        <!-- C. 扫描插件启用配置 (支持预设与按类全选) -->
        <div class="modal-section-card">
          <div class="section-title-with-actions">
            <div class="section-title">
              <span class="section-indicator"></span> {{ taskText('tasks.scanPluginsAndScheduling') }}
            </div>
            <div class="preset-btn-group">
              <span class="preset-tip">{{ taskText('tasks.presets') }}</span>
              <a-tooltip :title="taskText('tasks.enableDomainLookupSubdomainEnumerationPortScanningCdn')">
                <a-button size="small" @click="applyPreset('fast')">{{ taskText('tasks.quickDiscovery') }}</a-button>
              </a-tooltip>
              <a-tooltip :title="taskText('tasks.addServiceDetectionSslCertificatesAndFileDisclosure')">
                <a-button size="small" @click="applyPreset('normal')">{{ taskText('tasks.standardDiscovery') }}</a-button>
              </a-tooltip>
              <a-tooltip :title="taskText('tasks.enableAllPluginsAndIncludeCdnNodeIps')">
                <a-button size="small" @click="applyPreset('deep')">{{ taskText('tasks.fullDiscovery') }}</a-button>
              </a-tooltip>
            </div>
          </div>

          <div v-for="(category, catIndex) in pluginCategories" :key="catIndex" class="plugin-category-box">
            <div class="plugin-cat-header">
              <span class="cat-title">{{ category.title }}</span>
              <a-button size="small" type="link" @click="toggleCategory(category)">
                {{ isCategoryAllChecked(category) ? taskText('tasks.clearThisCategory') : taskText('tasks.selectThisCategory') }}
              </a-button>
            </div>
            <a-row :gutter="[12, 8]">
              <a-col :xs="24" :sm="12" :md="8" v-for="item in category.plugins" :key="item.key">
                <a-checkbox v-model:checked="formState[item.key]">
                  <span class="plugin-check-label">{{ item.label }}</span>
                </a-checkbox>
              </a-col>
            </a-row>
          </div>
        </div>
      </a-form>
    </a-modal>

    <!-- 5. 同步至资产组弹窗 -->
    <a-modal
      v-model:open="syncVisible"
      :title="taskText('tasks.syncTaskToAssetGroup')"
      @ok="handleSyncOk"
      :confirmLoading="syncLoading"
      width="480px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      :okText="taskText('tasks.confirm')"
      :cancelText="taskText('tasks.cancel')"
    >
      <div style="margin: 16px 0 8px 0;">
        <p class="task-count-caption">{{ taskText('tasks.selectTheAssetGroupThatWillReceiveThis') }}</p>
      </div>
      <a-form :model="syncFormState" layout="vertical" :label-wrap="true">
        <a-form-item :label="taskText('tasks.targetAssetGroup')" name="scope_id" :rules="[{ required: true, message: taskText('tasks.selectAnAssetGroup') }]">
          <AssetScopeSelect v-model:value="syncFormState.scope_id" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 6. FOFA 任务下发弹窗 -->
    <a-modal
      v-model:open="fofaVisible"
      :title="taskText('tasks.createFofaTask')"
      @ok="submitFofaTask"
      :confirmLoading="fofaSubmitLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      :okText="taskText('tasks.createTask')"
      :cancelText="taskText('tasks.cancel')"
      :bodyStyle="{ padding: '20px 28px' }"
    >
      <a-form
        ref="fofaFormRef"
        :model="fofaForm"
        layout="vertical"
        :label-wrap="true"
      >
        <a-form-item :label="taskText('tasks.taskName')" name="name" :rules="[{ required: true, message: taskText('tasks.enterATaskName') }]">
          <a-input v-model:value="fofaForm.name" :placeholder="taskText('tasks.enterATaskName')" />
        </a-form-item>

        <a-form-item :label="taskText('tasks.fofaQuery')" name="query" :rules="[{ required: true, message: taskText('tasks.enterAQuery') }]">
          <div style="display: flex; gap: 8px; align-items: center;">
            <a-input v-model:value="fofaForm.query" :placeholder="taskText('tasks.exampleAppApacheCountryCn')" class="task-fill-space" />
            <a-button type="primary" ghost @click="testFofaQuery" :loading="fofaTestLoading">{{ taskText('tasks.testConnection') }}</a-button>
          </div>
          <div v-if="fofaTested" class="fofa-test-result-box">
            <span class="fofa-badge">{{ taskText('tasks.queryResults') }} <b>{{ fofaResultCount }}</b></span>
          </div>
        </a-form-item>

        <a-form-item :label="taskText('tasks.policyOptional')" name="policy_id">
          <a-select
            v-model:value="fofaForm.policy_id"
            :placeholder="taskText('tasks.selectAPolicyUsesTheSystemDefaultWhen')"
            :options="policyOptions"
            allowClear
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 7. 企业资产查询弹窗与同步组件 -->
    <TycTaskModal v-model:open="tycModalVisible" @success="handleEnterpriseCreateSuccess" />
    <SyncToScopeModal v-model:open="syncModalVisible" :task="currentSyncTask" @success="handleSyncSuccess" />
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';

defineOptions({ name: 'TaskList' });

import { ref, reactive, onMounted, computed, createVNode, watch, onActivated, onDeactivated, onUnmounted } from 'vue';
import { useSticky } from '../utils/useSticky';
import { Modal, message, Checkbox } from 'ant-design-vue';
import { useRouter, useRoute } from 'vue-router';
import {
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  StopOutlined,
  SyncOutlined
} from '@ant-design/icons-vue';
import dayjs from 'dayjs';
import request from '../utils/request';
import { applyTaskStatistics, createTaskListClient } from '../utils/taskStatistics';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import { describeTaskFanout } from '../utils/targetParse';
import {
  PLUGIN_NAME_MAP,
  formatTaskStatus,
  formatTaskStatusColor
} from '../constants/taskStatus';
import TycTaskModal from '../components/TycTaskModal.vue';
import SyncToScopeModal from '../components/SyncToScopeModal.vue';
import AssetScopeSelect from '../components/AssetScopeSelect.vue';
import { getTaskAssetGroupState, hasSyncSummary } from '../utils/taskAssetGroups';

const { t: taskText, locale: taskLocale } = useI18n({ useScope: 'global' });

// --- 吸顶配置 ---
const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

// --- 路由与顶层 Tab 联动逻辑 ---
const router = useRouter();
const route = useRoute();
// 默认落地「企业测绘任务」；侧边栏与仪表盘入口均显式携带 ?tab= 参数，
// 避免同一路由出现两种默认落地页导致用户误判入口行为。
const activeMainTab = ref(route.query.tab === 'task' ? 'task' : 'enterprise');

// --- 字典配置 ---
const domainDicts = ref([]);
const altDnsDicts = ref([]);
const fileLeakDicts = ref([]);
const portDicts = ref([]);

// --- 状态中文化与插件中文名映射表（唯一事实源见 @/constants/taskStatus） ---
const pluginNameMap = PLUGIN_NAME_MAP;

// ==========================================
// 📊 顶部指标统计数据模型
// ==========================================
const taskMetricCounts = reactive({
  total: 0,
  running: 0,
  done: 0,
  abnormal: 0
});

const enterpriseMetricCounts = reactive({
  total: 0,
  running: 0,
  done: 0,
  abnormal: 0
});

const enterpriseRunningCount = ref(0);
const taskListClient = createTaskListClient(request);
let taskRequestVersion = 0;
let enterpriseRequestVersion = 0;
let taskStatisticsReady = false;
let enterpriseStatisticsReady = false;

const currentTotalCount = computed(() => {
  return activeMainTab.value === 'enterprise' ? enterpriseMetricCounts.total : taskMetricCounts.total;
});

const currentRunningCount = computed(() => {
  return activeMainTab.value === 'enterprise' ? enterpriseMetricCounts.running : taskMetricCounts.running;
});

const currentDoneCount = computed(() => {
  return activeMainTab.value === 'enterprise' ? enterpriseMetricCounts.done : taskMetricCounts.done;
});

const currentAbnormalCount = computed(() => {
  return activeMainTab.value === 'enterprise' ? enterpriseMetricCounts.abnormal : taskMetricCounts.abnormal;
});

const currentStatusFilter = computed(() => {
  return activeMainTab.value === 'enterprise' ? reconSearchForm.status : searchForm.status;
});

// 点击指标卡切换筛选状态
const toggleStatusFilter = (targetStatus) => {
  if (activeMainTab.value === 'enterprise') {
    if (reconSearchForm.status === targetStatus) {
      reconSearchForm.status = '';
    } else {
      reconSearchForm.status = targetStatus;
    }
    onReconSearch();
  } else {
    if (searchForm.status === targetStatus) {
      searchForm.status = '';
    } else {
      searchForm.status = targetStatus;
    }
    onSearch();
  }
};

// ==========================================
// 🔄 自适应静默轮询机制 (Smart Polling)
// ==========================================
const autoRefreshEnabled = ref(true);
const isRefreshing = ref(false);
const lastRefreshTime = ref(null);
let pollingTimer = null;

const lastRefreshTimeText = computed(() => {
  return lastRefreshTime.value ? dayjs(lastRefreshTime.value).format('HH:mm:ss') : '';
});

const startSmartPolling = () => {
  stopSmartPolling();
  if (!autoRefreshEnabled.value) return;

  pollingTimer = setInterval(async () => {
    // 仅在有进行中任务或激活状态时静默更新
    if (activeMainTab.value === 'enterprise') {
      if (!enterpriseStatisticsReady || enterpriseMetricCounts.running > 0) {
        await fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize, true);
      }
    } else {
      if (!taskStatisticsReady || taskMetricCounts.running > 0) {
        await fetchTasks(pagination.current, pagination.pageSize, true);
      }
    }
  }, 9000);
};

const stopSmartPolling = () => {
  if (pollingTimer) {
    clearInterval(pollingTimer);
    pollingTimer = null;
  }
};

const handleAutoRefreshToggle = (enabled) => {
  if (enabled) {
    message.success(taskText('tasks.autoRefreshEnabledRefreshSilentlyWhileTasksAre'));
    startSmartPolling();
  } else {
    message.info(taskText('tasks.autoRefreshPaused'));
    stopSmartPolling();
  }
};

const handleManualRefresh = async () => {
  isRefreshing.value = true;
  try {
    if (activeMainTab.value === 'enterprise') {
      await fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize);
    } else {
      await fetchTasks(pagination.current, pagination.pageSize);
    }
    lastRefreshTime.value = new Date();
    message.success(taskText('tasks.taskListRefreshed'));
  } catch (e) {
    message.error(taskText('tasks.refreshFailed'));
  } finally {
    isRefreshing.value = false;
  }
};

// ==========================================
// 🏢 企业测绘任务专属逻辑 (OSINT)
// ==========================================
const rangePresets = ref([
  { get label() { return taskText('tasks.today'); }, value: [dayjs().startOf('day'), dayjs().endOf('day')] },
  { get label() { return taskText('tasks.last7Days'); }, value: [dayjs().subtract(6, 'day').startOf('day'), dayjs().endOf('day')] },
  { get label() { return taskText('tasks.last30Days'); }, value: [dayjs().subtract(29, 'day').startOf('day'), dayjs().endOf('day')] },
  { get label() { return taskText('tasks.thisMonth'); }, value: [dayjs().startOf('month'), dayjs().endOf('month')] },
]);

const reconSearchForm = reactive({
  name: '',
  target: '',
  status: '',
  dateRange: null
});

const enterpriseTaskList = ref([]);
const enterpriseLoading = ref(false);
const enterpriseBatchDeleting = ref(false);
const enterpriseTaskCache = new Map();
const globalPageSize = useGlobalPageSize(10);
const enterprisePagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });
const enterpriseSelectedRowKeys = ref([]);
const onEnterpriseSelectChange = (keys) => {
  enterpriseSelectedRowKeys.value = keys;
};

const fetchEnterpriseTasks = async (page = 1, size = 10, silent = false, includeStatistics = true) => {
  const requestVersion = ++enterpriseRequestVersion;
  if (!silent) enterpriseLoading.value = true;
  try {
    const queryParams = { page, size };
    if (reconSearchForm.name) queryParams.name = reconSearchForm.name;
    if (reconSearchForm.target) queryParams.target = reconSearchForm.target;
    if (reconSearchForm.status) queryParams.status = reconSearchForm.status;
    if (reconSearchForm.dateRange && reconSearchForm.dateRange.length === 2 && reconSearchForm.dateRange[0] && reconSearchForm.dateRange[1]) {
      queryParams.end_time__gte = dayjs(reconSearchForm.dateRange[0]).startOf('day').format('YYYY-MM-DD HH:mm:ss');
      queryParams.end_time__lte = dayjs(reconSearchForm.dateRange[1]).endOf('day').format('YYYY-MM-DD HH:mm:ss');
    }

    const res = await taskListClient.get('/icp/task', queryParams, includeStatistics);
    if (requestVersion !== enterpriseRequestVersion) return;

    if (res.code === 200) {
      if (applyTaskStatistics(enterpriseMetricCounts, res.statistics)) {
        enterpriseStatisticsReady = true;
        enterpriseRunningCount.value = enterpriseMetricCounts.running;
      }
      enterpriseTaskList.value = res.items || [];
      (res.items || []).forEach(item => {
        if (item && item._id) {
          enterpriseTaskCache.set(item._id, item);
        }
      });
      enterprisePagination.total = res.total || 0;
      enterprisePagination.current = page;
      enterprisePagination.pageSize = size;
      lastRefreshTime.value = new Date();
    }
  } catch (error) {
    console.error('获取企业测绘列表失败:', error);
  } finally {
    if (requestVersion === enterpriseRequestVersion) enterpriseLoading.value = false;
  }
};

const onReconSearch = () => {
  fetchEnterpriseTasks(1, enterprisePagination.pageSize);
};

const resetReconSearch = () => {
  reconSearchForm.name = '';
  reconSearchForm.target = '';
  reconSearchForm.status = '';
  reconSearchForm.dateRange = null;
  onReconSearch();
};

const handleEnterpriseTableChange = (page, pageSize) => {
  if (pageSize && pageSize !== globalPageSize.value) {
    globalPageSize.value = pageSize;
  }
  fetchEnterpriseTasks(page, pageSize || enterprisePagination.pageSize, false, false);
};

const TYC_QUERY_TYPE_LABELS = {
  get invest() { return taskText('tasks.investments'); },
  get web() { return taskText('tasks.websiteIcpRecords'); },
  get app() { return taskText('tasks.mobileApps'); },
  get mapp() { return taskText('tasks.wechatMiniPrograms'); },
  get wechat() { return taskText('tasks.wechatOfficialAccounts'); },
  get weibo() { return taskText('tasks.corporateWeiboAccounts'); }
};

const ICP_QUERY_TYPE_LABELS = {
  get web() { return taskText('tasks.websiteIcpRecords'); },
  get app() { return taskText('tasks.mobileApps'); },
  get mapp() { return taskText('tasks.wechatMiniPrograms'); },
  get kapp() { return taskText('tasks.quickApps'); }
};

const hasEnterpriseOptions = (record) => {
  if (!record) return false;
  return Boolean(
    (Array.isArray(record.query_type) && record.query_type.length > 0) ||
    record.depth !== undefined ||
    record.invest_ratio !== undefined ||
    record.task_type === 'tyc'
  );
};

const getEnterpriseQueryTypeLabels = (record) => {
  const queryType = Array.isArray(record.query_type) ? record.query_type : [];
  const map = record.task_type === 'tyc' ? TYC_QUERY_TYPE_LABELS : ICP_QUERY_TYPE_LABELS;
  if (!queryType.length) return [taskText('tasks.defaultQuery')];
  return queryType.map(k => map[k] || k);
};

const formatEnterpriseOptionsSummary = (record) => {
  if (!record) return taskText('tasks.defaultConfiguration');
  const queryCount = Array.isArray(record.query_type) ? record.query_type.length : 0;

  if (record.task_type === 'tyc') {
    let activeCount = queryCount;
    if (record.depth !== undefined) activeCount++;
    if (record.invest_ratio !== undefined) activeCount++;
    if (record.enable_icp !== false) activeCount++;
    return taskText('tasks.configuredPoliciesCount', { count: activeCount });
  }

  if (queryCount > 0) {
    return taskText('tasks.queryCategoriesCount', { count: queryCount });
  }
  return taskText('tasks.defaultConfiguration');
};

// 这些列配置会复用，读取标题时再翻译，使已打开的页面能随语言更新。
const enterpriseColumns = [
  { get title() { return taskText('tasks.taskName'); }, dataIndex: 'name', key: 'name', width: 220, ellipsis: true },
  { get title() { return taskText('tasks.queryTarget'); }, dataIndex: 'target', key: 'target', width: 200, ellipsis: true },
  { get title() { return taskText('tasks.discoveryMode'); }, dataIndex: 'task_type', key: 'task_type', width: 110 },
  { get title() { return taskText('tasks.policyConfiguration'); }, key: 'policy_options', width: 140 },
  { get title() { return taskText('tasks.status'); }, dataIndex: 'status', key: 'status', width: 120 },
  { get title() { return taskText('tasks.coreInvestments'); }, key: 'statistic', width: 140 },
  { get title() { return taskText('tasks.syncStatus'); }, key: 'sync_status', width: 150 },
  { get title() { return taskText('tasks.endTime'); }, dataIndex: 'end_time', key: 'end_time', width: 160 },
  { get title() { return taskText('tasks.actions'); }, key: 'action', width: 170, fixed: 'right' }
];

const getEnterpriseStatusColor = (status) => {
  return formatTaskStatusColor(status);
};

const getEnterpriseStatusIcon = (status) => {
  if (status === 'done') return CheckCircleOutlined;
  if (status === 'error') return CloseCircleOutlined;
  if (status === 'stop') return StopOutlined;
  if (status === 'waiting') return ClockCircleOutlined;
  return SyncOutlined;
};

const formatEnterpriseStatusText = (status) => formatTaskStatus(status);

const tycModalVisible = ref(false);
const syncModalVisible = ref(false);
const currentSyncTask = ref(null);

const showTycModal = () => {
  tycModalVisible.value = true;
};

const handleEnterpriseCreateSuccess = () => {
  fetchEnterpriseTasks(1, enterprisePagination.pageSize);
};

const handleSyncEnterprise = (record) => {
  currentSyncTask.value = record;
  syncModalVisible.value = true;
};

const handleSyncSuccess = (result) => {
  if (currentSyncTask.value) {
    currentSyncTask.value.synced_scope_id = result.scope_id;
    currentSyncTask.value.synced_scope_name = result.target_name;
  }
  fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize, true);
};

const goToScope = (scopeId, scopeName) => {
  if (scopeId) {
    router.push({
      path: '/groupAssetsManagement/groupAssetsDetail',
      query: { scope_id: scopeId, targetName: scopeName || '', view: 'osint' }
    });
  }
};

const viewEnterpriseTask = (record) => {
  const stats = record.statistic || {};
  router.push({
    path: '/taskList/taskDetail',
    query: {
      task_id: record._id,
      name: record.name,
      target: record.target,
      task_type: record.task_type || 'icp',
      web_cnt: stats.web_cnt || 0,
      app_cnt: stats.app_cnt || 0,
      mapp_cnt: stats.mapp_cnt || 0,
      kapp_cnt: stats.kapp_cnt || 0,
      invest_cnt: stats.invest_cnt || 0,
      wechat_cnt: stats.wechat_cnt || 0,
      weibo_cnt: stats.weibo_cnt || 0,
    }
  });
};

const handleExportEnterprise = async (record) => {
  try {
    message.loading({ content: taskText('tasks.exporting'), key: 'export', duration: 0 });
    const res = await request.get(`/icp/export/${record._id}`, { responseType: 'blob' });
    const blob = new Blob([res.data || res]);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${record.name || 'icp_export'}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    message.success({ content: taskText('tasks.exportCompleted'), key: 'export', duration: 2 });
  } catch (error) {
    message.error({ content: taskText('tasks.exportFailed'), key: 'export', duration: 2 });
  }
};

const handleBatchExportEnterprise = async () => {
  if (enterpriseSelectedRowKeys.value.length === 0) {
    message.warning(taskText('tasks.selectTasksToExportFirst'));
    return;
  }
  try {
    message.loading({ content: taskText('tasks.exportingSelectedTasks'), key: 'batch_export', duration: 0 });
    const res = await request.post('/icp/batch_export', {
      task_id: enterpriseSelectedRowKeys.value
    }, { responseType: 'blob' });
    const blob = new Blob([res.data || res]);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', 'batch_icp_export.xlsx');
    document.body.appendChild(link);
    link.click();
    link.remove();
    message.success({ content: taskText('tasks.selectedTasksExported'), key: 'batch_export', duration: 2 });
  } catch (error) {
    message.error({ content: taskText('tasks.failedToExportSelectedTasks'), key: 'batch_export', duration: 2 });
  }
};

const handleBatchDeleteEnterprise = async () => {
  if (!enterpriseSelectedRowKeys.value.length || enterpriseBatchDeleting.value) return;

  // 严格前置白名单校验：从缓存及当前页记录中解析状态，非终态任务坚决拦截
  const activeSelected = enterpriseSelectedRowKeys.value.filter(id => {
    const item = enterpriseTaskCache.get(id) || enterpriseTaskList.value.find(t => t._id === id);
    return item && !['done', 'stop', 'error'].includes(item.status);
  });
  if (activeSelected.length > 0) {
    message.warning(taskText('tasks.someSelectedTasksAreRunningOrUnfinishedStop'));
    return;
  }

  enterpriseBatchDeleting.value = true;
  try {
    message.loading({ content: taskText('tasks.deletingSelectedTasks'), key: 'batchDelete', duration: 0 });
    const res = await request.post('/icp/delete/', { task_ids: enterpriseSelectedRowKeys.value });
    if (res.code === 200) {
      message.success({ content: taskText('tasks.selectedTasksDeleted'), key: 'batchDelete', duration: 2 });
      enterpriseSelectedRowKeys.value.forEach(id => enterpriseTaskCache.delete(id));
      const deletedCount = res.deleted_count || enterpriseSelectedRowKeys.value.length;
      enterpriseSelectedRowKeys.value = [];
      const remainingCount = Math.max(0, enterprisePagination.total - deletedCount);
      const maxPage = Math.max(1, Math.ceil(remainingCount / enterprisePagination.pageSize));
      const targetPage = Math.min(enterprisePagination.current, maxPage);
      fetchEnterpriseTasks(targetPage, enterprisePagination.pageSize);
    } else {
      message.error({ content: res.message || taskText('tasks.failedToDeleteSelectedTasks'), key: 'batchDelete', duration: 3 });
    }
  } catch (error) {
    message.error({ content: taskText('tasks.networkErrorFailedToDeleteSelectedTasks'), key: 'batchDelete', duration: 2 });
  } finally {
    enterpriseBatchDeleting.value = false;
  }
};

const handleBatchRestartEnterprise = async () => {
  if (!enterpriseSelectedRowKeys.value.length) return;
  try {
    message.loading({ content: taskText('tasks.restartingSelectedTasks'), key: 'batchRestart', duration: 0 });
    const res = await request.post('/icp/restart/', { task_ids: enterpriseSelectedRowKeys.value });
    if (res.code === 200) {
      message.success({ content: taskText('tasks.selectedTasksQueuedForRestart'), key: 'batchRestart', duration: 3 });
      enterpriseSelectedRowKeys.value = [];
      fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize);
    } else {
      message.error({ content: res.message || taskText('tasks.failedToRestartSelectedTasks'), key: 'batchRestart', duration: 3 });
    }
  } catch (error) {
    message.error({ content: taskText('tasks.failedToRestartSelectedTasks'), key: 'batchRestart', duration: 2 });
  }
};

const handleStopEnterprise = (record) => {
  Modal.confirm({
    title: taskText('tasks.stopEnterpriseTask'),
    icon: createVNode(ExclamationCircleOutlined),
    content: taskText('tasks.stopEnterpriseTaskNameItWillNoLonger', { name: record.name }),
    okText: taskText('tasks.confirmStop'),
    okButtonProps: { danger: true },
    cancelText: taskText('tasks.cancel'),
    onOk: () => executeStopEnterprise(record)
  });
};

const executeStopEnterprise = async (record) => {
  try {
    const res = await request.get(`/icp/stop/${record._id}`);
    if (res.code === 200) {
      message.success(taskText('tasks.taskStopped'));
      fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize);
    } else {
      message.error(res.message || taskText('tasks.failedToStopTaskLabel'));
    }
  } catch (error) {
    console.error('停止任务失败', error);
  }
};

const handleRestartEnterprise = (record) => {
  Modal.confirm({
    title: taskText('tasks.restartEnterpriseTask'),
    icon: createVNode(ExclamationCircleOutlined),
    content: taskText('tasks.restartEnterpriseTaskNameThisWillRunDiscovery', { name: record.name }),
    okText: taskText('tasks.confirmRestart'),
    cancelText: taskText('tasks.cancel'),
    onOk: () => executeRestartEnterprise(record)
  });
};

const executeRestartEnterprise = async (record) => {
  try {
    const res = await request.get(`/icp/restart/${record._id}`);
    if (res.code === 200) {
      message.success(taskText('tasks.taskRestarted'));
      fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize);
    } else {
      message.error(res.message || taskText('tasks.failedToRestartTaskLabel'));
    }
  } catch (error) {
    console.error('重启任务失败', error);
  }
};

const handleDeleteEnterprise = async (record) => {
  if (!['done', 'stop', 'error'].includes(record.status)) {
    message.warning(taskText('tasks.runningOrQueuedTasksCannotBeDeletedStop'));
    return;
  }

  Modal.confirm({
    title: taskText('tasks.confirmDeletion'),
    icon: createVNode(ExclamationCircleOutlined),
    content: taskText('tasks.deleteEnterpriseTaskName', { name: record.name || record._id }),
    okText: taskText('tasks.confirm'),
    cancelText: taskText('tasks.cancel'),
    okButtonProps: { danger: true },
    onOk: async () => {
      try {
        const res = await request.post('/icp/delete/', { task_ids: [record._id] });
        if (res.code === 200) {
          message.success(taskText('tasks.deletedSuccessfully'));
          enterpriseTaskCache.delete(record._id);
          enterpriseSelectedRowKeys.value = enterpriseSelectedRowKeys.value.filter(id => id !== record._id);
          const remainingCount = Math.max(0, enterprisePagination.total - 1);
          const maxPage = Math.max(1, Math.ceil(remainingCount / enterprisePagination.pageSize));
          const targetPage = Math.min(enterprisePagination.current, maxPage);
          fetchEnterpriseTasks(targetPage, enterprisePagination.pageSize);
        } else {
          message.error(res.message || taskText('tasks.deletionFailedLabel'));
        }
      } catch (error) {
        message.error(taskText('tasks.networkErrorDeletionFailed'));
        console.error('删除任务失败', error);
      }
    }
  });
};

// ==========================================
// 🔍 资产侦查任务表格与数据逻辑 (ASM)
// ==========================================
const taskList = ref([]);
const loading = ref(false);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0, showSizeChanger: true });

watch(() => pagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});

watch(() => enterprisePagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});

watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
  enterprisePagination.pageSize = newSize;
});

// 列配置
const columns = [
  { get title() { return taskText('tasks.taskName'); }, dataIndex: 'name', key: 'name', width: 200, sorter: true, ellipsis: true },
  { get title() { return taskText('tasks.target'); }, dataIndex: 'target', key: 'target', width: 220, sorter: true, ellipsis: true },
  { get title() { return taskText('tasks.assetCounts'); }, dataIndex: 'statistic', key: 'statistic', width: 210 },
  { get title() { return taskText('tasks.assetGroup'); }, key: 'asset_group', width: 180 },
  { get title() { return taskText('tasks.policyConfiguration'); }, dataIndex: 'options', key: 'options', width: 140 },
  { get title() { return taskText('tasks.status'); }, dataIndex: 'status', key: 'status', width: 150 },
  { get title() { return taskText('tasks.startTime'); }, dataIndex: 'start_time', key: 'start_time', width: 160 },
  { get title() { return taskText('tasks.endTime'); }, dataIndex: 'end_time', key: 'end_time', width: 160 },
  { get title() { return taskText('tasks.taskId'); }, dataIndex: '_id', key: 'task_id', width: 190 },
  { get title() { return taskText('tasks.actions'); }, key: 'action', fixed: 'right', width: 160 },
];

const isStatusRunning = (status) => {
  return !['done', 'error', 'stop', 'waiting'].includes(status);
};

const getStatusTagColor = (status) => {
  return formatTaskStatusColor(status);
};

const getStatusIcon = (status) => {
  if (status === 'done') return CheckCircleOutlined;
  if (status === 'error') return CloseCircleOutlined;
  if (status === 'stop') return StopOutlined;
  if (status === 'waiting') return ClockCircleOutlined;
  return SyncOutlined;
};

const formatStatusText = (status) => formatTaskStatus(status);

const hasTaskErrorNotice = (record) => {
  if (!record) return false;
  if (record.error_msg) return true;
  if (record.phase_errors && Object.keys(record.phase_errors).length > 0) return true;
  return record.status === 'error' && Boolean(record.end_reason);
};

const formatTaskErrorTooltip = (record) => {
  if (!record) return '';
  let detail = record.error_msg || '';
  if (!detail && record.phase_errors && typeof record.phase_errors === 'object') {
    detail = Object.entries(record.phase_errors)
      .map(([phase, msg]) => `[${phase}] ${msg}`)
      .join('；');
  }
  if (!detail && record.status === 'error' && record.end_reason) {
    detail = record.end_reason;
  }
  if (record.status === 'done' && detail) {
    return taskText('tasks.partialFailureNotice', { error: detail });
  }
  return detail;
};

const formatOptionsSummary = (options) => {
  if (!options) return taskText('tasks.defaultConfiguration');
  let activeCount = 0;
  for (const key in options) {
    if (options[key] === true) activeCount++;
  }
  return taskText('tasks.enabledPluginsCount', { count: activeCount });
};

const getDetailedOptions = (options) => {
  if (!options) return [taskText('tasks.defaultConfiguration')];
  const detailed = [];

  for (const key in options) {
    if (options[key] === true) {
      const plugin = pluginList.find(item => item.key === key);
      if (plugin) detailed.push(plugin.label);
    }
  }

  if (options.domain_brute_type) {
    const typeMap = { test: taskText('tasks.test'), big: taskText('tasks.largeWordlist') };
    detailed.push(taskText('tasks.subdomainWordlistName', { name: typeMap[options.domain_brute_type] || options.domain_brute_type }));
  }
  if (options.port_scan_type && options.port_scan_type !== 'null' && options.port_scan_type !== null) {
    const typeMap = { test: taskText('tasks.test'), top100: 'TOP100', top1000: 'TOP1000', all: taskText('tasks.allPorts') };
    detailed.push(taskText('tasks.portScanPolicyName', { name: typeMap[options.port_scan_type] || options.port_scan_type.toUpperCase() }));
  }
  if (options.alt_dns_dict) {
    detailed.push(taskText('tasks.generatedSubdomainWordlistName', { name: options.alt_dns_dict }));
  }
  if (options.file_leak_dict) {
    detailed.push(taskText('tasks.fileDiscoveryWordlistName', { name: options.file_leak_dict }));
  }

  return detailed.length > 0 ? detailed : [taskText('tasks.noAdditionalOptions')];
};

// 搜索表单与高级筛选折叠状态
const isAdvancedFilterOpen = ref(false);
const searchForm = reactive({
  name: '', target: '', task_id: '', type: undefined,
  status: '', site_count: '', site_operator: '=',
  domain_count: '', domain_operator: '=', wih_count: '', wih_operator: '=',
  sync_status: undefined
});

const activeAdvancedFilterCount = computed(() => {
  let count = 0;
  if (searchForm.task_id) count++;
  if (searchForm.type) count++;
  if (searchForm.sync_status) count++;
  if (searchForm.site_count !== '' && searchForm.site_count !== null && searchForm.site_count !== undefined) count++;
  if (searchForm.domain_count !== '' && searchForm.domain_count !== null && searchForm.domain_count !== undefined) count++;
  if (searchForm.wih_count !== '' && searchForm.wih_count !== null && searchForm.wih_count !== undefined) count++;
  return count;
});

const resetAdvancedFilters = () => {
  searchForm.task_id = '';
  searchForm.type = undefined;
  searchForm.sync_status = undefined;
  searchForm.site_count = '';
  searchForm.site_operator = '=';
  searchForm.domain_count = '';
  searchForm.domain_operator = '=';
  searchForm.wih_count = '';
  searchForm.wih_operator = '=';
  onSearch();
};

// 表格多选逻辑
const selectedRowKeys = ref([]);
const hasSelected = computed(() => selectedRowKeys.value.length > 0);
const onSelectChange = (keys) => {
  selectedRowKeys.value = keys;
};

// 获取任务列表数据
const fetchTasks = async (page = 1, size = 10, silent = false, includeStatistics = true) => {
  const requestVersion = ++taskRequestVersion;
  if (!silent) loading.value = true;
  try {
    const queryParams = { page, size };

    if (searchForm.name) queryParams.name = searchForm.name;
    if (searchForm.target) queryParams.target = searchForm.target;
    if (searchForm.status) queryParams.status = searchForm.status;
    if (searchForm.task_id) queryParams._id = searchForm.task_id;
    if (searchForm.type) queryParams.task_tag = searchForm.type;
    if (searchForm.sync_status) queryParams.sync_status = searchForm.sync_status;

    const appendCountParam = (count, operator, baseKey) => {
      if (count !== '' && count !== null && count !== undefined) {
        if (operator === '=') queryParams[baseKey] = count;
        else if (operator === '>') queryParams[`${baseKey}_gt`] = count;
        else if (operator === '<') queryParams[`${baseKey}_lt`] = count;
      }
    };

    appendCountParam(searchForm.site_count, searchForm.site_operator, 'statistic.site_cnt');
    appendCountParam(searchForm.domain_count, searchForm.domain_operator, 'statistic.domain_cnt');
    appendCountParam(searchForm.wih_count, searchForm.wih_operator, 'statistic.wih_cnt');

    const res = await taskListClient.get('/task/', queryParams, includeStatistics);
    if (requestVersion !== taskRequestVersion) return;

    if (res.code === 200) {
      if (applyTaskStatistics(taskMetricCounts, res.statistics)) taskStatisticsReady = true;
      taskList.value = res.items || [];
      pagination.total = res.total || 0;
      pagination.current = page;
      pagination.pageSize = size;
      lastRefreshTime.value = new Date();
    }
  } catch (error) {
    console.error('获取资产侦查任务失败:', error);
  } finally {
    if (requestVersion === taskRequestVersion) loading.value = false;
  }
};

const onSearch = () => {
  fetchTasks(1, pagination.pageSize);
};

const resetSearch = () => {
  Object.assign(searchForm, {
    name: '', target: '', task_id: '', type: undefined,
    status: '', site_count: '', site_operator: '=',
    domain_count: '', domain_operator: '=', wih_count: '', wih_operator: '=',
    sync_status: undefined
  });
  onSearch();
};

const handleTableChange = (page, pageSize) => fetchTasks(page, pageSize, false, false);

// ==========================================
// 💥 任务批量操作
// ==========================================
const handleBatchDelete = () => {
  if (!hasSelected.value) {
    message.warning(taskText('tasks.selectTasksToDeleteFirst'));
    return;
  }

  const validKeys = selectedRowKeys.value.filter(key => key != null);
  if (validKeys.length === 0) return;

  // 默认不勾选：级联删除资产数据不可恢复，须由用户显式确认
  let isDeleteData = false;

  // 跨页选择时勾选项可能不在当前可见页，列出名称便于用户复核范围
  const selectedNames = taskList.value
    .filter(item => validKeys.includes(item._id || item.task_id))
    .map(item => item.name)
    .filter(Boolean);
  const visibleCount = taskList.value.filter(item => validKeys.includes(item._id || item.task_id)).length;

  Modal.confirm({
    title: taskText('tasks.deleteSelectedTasks'),
    icon: createVNode(ExclamationCircleOutlined),
    content: createVNode('div', { style: 'margin-top: 8px;' }, [
      createVNode('div', { style: 'margin-bottom: 14px; color: var(--arl-text-color);' }, taskText('tasks.deleteTheSelectedTasksCount', { count: validKeys.length })),
      selectedNames.length > 0 ? createVNode('div', {
        style: 'max-height: 120px; overflow-y: auto; background: var(--arl-bg-light); padding: 6px 8px; border-radius: 4px; margin-bottom: 14px; font-size: 12px; color: var(--arl-text-color); opacity: 0.85; line-height: 1.6;'
      }, [
        createVNode('div', { style: 'font-weight: 500; margin-bottom: 4px;' }, taskText('tasks.theFollowingTasksWillBeDeleted', {  })),
        createVNode('div', null, `· ${selectedNames.join('\n· ')}`),
        visibleCount < validKeys.length
          ? createVNode('div', { style: 'margin-top: 4px; color: #faad14;' }, taskText('tasks.includesCountSelectionsRetainedFromOtherPages', { count: validKeys.length - visibleCount }))
          : null
      ]) : null,
      createVNode(Checkbox, {
        defaultChecked: isDeleteData,
        onChange: (e) => { isDeleteData = e.target.checked; }
      }, () => taskText('tasks.alsoPermanentlyDeleteAllAssetsOwnedByThese'))
    ]),
    okText: taskText('tasks.confirmDeletion'),
    cancelText: taskText('tasks.cancel'),
    okButtonProps: { danger: true },
    onOk: async () => {
      try {
        const res = await request.post('/task/delete/', {
          del_task_data: isDeleteData,
          task_id: validKeys
        });

        if (res.code === 200) {
          message.success(taskText('tasks.tasksDeletedCount', { count: validKeys.length }));
          selectedRowKeys.value = [];
          fetchTasks(1, pagination.pageSize);
        } else {
          message.error(taskText('tasks.deletionFailed') + (res.message || taskText('tasks.unknownError')));
        }
      } catch (error) {
        message.error(taskText('tasks.networkErrorPleaseTryAgainLater'));
      }
    }
  });
};

const handleBatchStop = () => {
  if (!hasSelected.value) {
    message.warning(taskText('tasks.selectTasksToStopFirst'));
    return;
  }

  const validKeys = selectedRowKeys.value.filter(key => key != null);
  if (validKeys.length === 0) return;

  const selectedRecords = taskList.value.filter(item => validKeys.includes(item._id || item.task_id));
  const activeCount = selectedRecords.filter(item => !['done', 'stop', 'error'].includes(item.status)).length;
  const finishedCount = validKeys.length - activeCount;

  let modalContent = taskText('tasks.stopTheSelectedTasksCount', { count: validKeys.length });
  if (activeCount > 0 && finishedCount > 0) {
    modalContent = taskText('tasks.ofTotalSelectedTasksRunningAreRunningAnd', { total: validKeys.length, running: activeCount, finished: finishedCount });
  }

  Modal.confirm({
    title: taskText('tasks.stopTasks'),
    icon: createVNode(ExclamationCircleOutlined),
    content: modalContent,
    okText: taskText('tasks.confirmStop'),
    cancelText: taskText('tasks.cancel'),
    onOk: async () => {
      try {
        const res = await request.post('/task/batch_stop/', { task_id: validKeys });
        if (res.code === 200) {
          message.success(taskText('tasks.stopRequestSentLabel'));
          selectedRowKeys.value = [];
          fetchTasks(pagination.current, pagination.pageSize);
        } else {
          message.error(taskText('tasks.failedToStopTask') + (res.message || taskText('tasks.unknownError')));
        }
      } catch (error) {
        message.error(taskText('tasks.networkErrorPleaseTryAgainLater'));
      }
    }
  });
};

const handleBatchExport = async ({ key }) => {
  if (!hasSelected.value) {
    message.warning(taskText('tasks.selectTasksToExportFirst'));
    return;
  }

  const validKeys = selectedRowKeys.value.filter(k => k != null);
  if (validKeys.length === 0) return;

  try {
    message.loading({ content: taskText('tasks.generatingExportFile'), key: 'exporting' });
    const res = await request.post(`/batch_export/${key}/`, {
      task_id: validKeys
    }, {
      responseType: 'blob'
    });

    const blob = new Blob([res], { type: 'text/plain;charset=utf-8' });
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `batch_export_${key}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    message.success({ content: taskText('tasks.selectedTasksExported'), key: 'exporting', duration: 2 });
  } catch (error) {
    console.error('批量导出异常:', error);
    message.error({ content: taskText('tasks.exportFailedCheckTheConsole'), key: 'exporting', duration: 2 });
  }
};

// ==========================================
// 💥 单行操作逻辑 (详情、重启、停止、删除、导出、同步)
// ==========================================
const viewTask = (record) => {
  if (!record || !record._id) return;
  const query = {
    task_id: record._id,
    targetName: record.target
  };
  if (record.statistic) {
    Object.assign(query, record.statistic);
  }
  router.push({ path: '/taskList/taskDetail', query });
};

const restartTask = async (record) => {
  if (record.restarting) return;
  record.restarting = true;
  try {
    const res = await request.post('/task/restart/', {
      task_id: [record._id || record.task_id]
    });

    if (res.code === 200) {
      const newTaskId = res.data?.new_task_id?.[0];
      if (newTaskId) {
        message.success(taskText('tasks.taskRestartedNewTaskIdId', { id: newTaskId }));
      } else {
        message.success(taskText('tasks.taskRestartedWithANewTaskRecord'));
      }
      fetchTasks(pagination.current, pagination.pageSize);
    } else {
      const errMsg = res.data?.error || res.message || taskText('tasks.unknownError');
      message.error(taskText('tasks.failedToRestartTask') + errMsg);
    }
  } catch (error) {
    message.error(taskText('tasks.networkErrorFailedToRestartTask'));
  } finally {
    record.restarting = false;
  }
};

const stopSingleTask = async (record) => {
  try {
    const res = await request.get(`/task/stop/${record._id || record.task_id}`);
    if (res.code === 200) {
      message.success(taskText('tasks.stopRequestSent'));
      fetchTasks(pagination.current, pagination.pageSize);
    } else {
      message.error(taskText('tasks.failedToStopTask') + (res.message || taskText('tasks.unknownError')));
    }
  } catch (error) {
    message.error(taskText('tasks.networkErrorFailedToStopTask'));
  }
};

const deleteSingleTask = (record) => {
  let isDeleteData = true;

  Modal.confirm({
    title: taskText('tasks.deleteTask'),
    icon: createVNode(ExclamationCircleOutlined),
    content: createVNode('div', { style: 'margin-top: 8px;' }, [
      createVNode('div', { style: 'margin-bottom: 14px; color: var(--arl-text-color);' }, taskText('tasks.deleteTaskName', { name: record.name || record._id })),
      createVNode(Checkbox, {
        defaultChecked: isDeleteData,
        onChange: (e) => { isDeleteData = e.target.checked; }
      }, () => taskText('tasks.alsoPermanentlyDeleteAllAssetsAssociatedWithThis'))
    ]),
    okText: taskText('tasks.confirmDeletion'),
    cancelText: taskText('tasks.cancel'),
    okButtonProps: { danger: true },
    onOk: async () => {
      try {
        const res = await request.post('/task/delete/', {
          task_id: [record._id || record.task_id],
          del_task_data: isDeleteData
        });

        if (res.code === 200) {
          message.success(taskText('tasks.taskDeleted'));
          fetchTasks(pagination.current, pagination.pageSize);
        } else {
          message.error(taskText('tasks.deletionFailed') + (res.message || taskText('tasks.unknownError')));
        }
      } catch (error) {
        message.error(taskText('tasks.networkErrorDeletionFailed'));
      }
    }
  });
};

const exportTask = async (record) => {
  try {
    message.loading({ content: taskText('tasks.generatingExcelExport'), key: 'exporting_excel' });
    const res = await request.get(`/export/${record._id || record.task_id}`, {
      responseType: 'blob'
    });

    const blob = new Blob([res], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `ARL_Task_${record.name || record._id}_Export.xlsx`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    message.success({ content: taskText('tasks.excelExportCompleted'), key: 'exporting_excel', duration: 2 });
  } catch (error) {
    message.error({ content: taskText('tasks.exportFailedCheckTheConsole'), key: 'exporting_excel', duration: 2 });
  }
};

// 同步任务至资产组
const syncVisible = ref(false);
const syncLoading = ref(false);
const currentSyncRecord = ref(null);
const syncFormState = reactive({ scope_id: undefined });

const syncTask = (record) => {
  currentSyncRecord.value = record;
  syncFormState.scope_id = record.sync_scope_id || record.options?.related_scope_id || record.synced_scope_id || undefined;
  syncVisible.value = true;
};

const handleSyncOk = async () => {
  if (!syncFormState.scope_id) {
    message.warning(taskText('tasks.selectATargetAssetGroup'));
    return;
  }

  syncLoading.value = true;
  try {
    const res = await request.post('/task/sync/', {
      scope_id: syncFormState.scope_id,
      task_id: currentSyncRecord.value._id || currentSyncRecord.value.task_id
    });

    if (res.code === 200) {
      message.success(taskText('tasks.syncTaskQueued'));
      syncVisible.value = false;
      fetchTasks(pagination.current, pagination.pageSize);
    } else {
      message.error(taskText('tasks.syncFailed') + (res.data?.error || res.message || taskText('tasks.unknownError')));
    }
  } catch (error) {
    message.error(taskText('tasks.networkErrorPleaseTryAgainLater'));
  } finally {
    syncLoading.value = false;
  }
};

// ==========================================
// ➕ 新建资产侦查任务弹窗逻辑
// ==========================================
const visible = ref(false);
const submitLoading = ref(false);
const formRef = ref();

const pluginCategories = [
  {
    get title() { return taskText('tasks.domainsAndAssetDiscovery'); },
    plugins: [
      { key: 'dns_query_plugin', get label() { return taskText('tasks.domainLookupPlugins'); } },
      { key: 'domain_brute', get label() { return taskText('tasks.subdomainBruteForce'); } },
      { key: 'alt_dns', get label() { return taskText('tasks.dnsWordlistGeneration'); } },
      { key: 'arl_search', get label() { return taskText('tasks.arlHistorySearch'); } }
    ]
  },
  {
    get title() { return taskText('tasks.portsAndServices'); },
    plugins: [
      { key: 'skip_scan_cdn_ip', get label() { return taskText('tasks.skipCdn'); } },
      { key: 'port_scan', get label() { return taskText('tasks.portScanning'); } },
      { key: 'service_detection', get label() { return taskText('tasks.serviceDetection'); } },
      { key: 'os_detection', get label() { return taskText('tasks.osDetection'); } },
      { key: 'ssl_cert', get label() { return taskText('tasks.sslCertificates'); } }
    ]
  },
  {
    get title() { return taskText('tasks.webDiscovery'); },
    plugins: [
      { key: 'site_identify', get label() { return taskText('tasks.websiteDiscoveryAndFingerprinting'); } },
      { key: 'search_engines', get label() { return taskText('tasks.searchEngines'); } },
      { key: 'site_spider', get label() { return taskText('tasks.websiteCrawler'); } },
      { key: 'web_info_hunter', get label() { return taskText('tasks.wihExtraction'); } },
      { key: 'file_leak', get label() { return taskText('tasks.fileDisclosure'); } },
      { key: 'findvhost', get label() { return taskText('tasks.hostCollision'); } }
    ]
  },
  {
    get title() { return taskText('tasks.vulnerabilityAndRiskScanning'); },
    plugins: [
      { key: 'nuclei_scan', get label() { return taskText('tasks.nucleiScanning'); } }
    ]
  }
];

const pluginList = pluginCategories.flatMap(cat => cat.plugins);

const defaultPlugins = {
  domain_brute: true, alt_dns: true, dns_query_plugin: true, arl_search: true,
  port_scan: true, service_detection: false, os_detection: false, ssl_cert: false,
  skip_scan_cdn_ip: true, site_identify: false, search_engines: false, site_spider: false,
  file_leak: false, findvhost: false, nuclei_scan: false, web_info_hunter: false,
  npoc_service_detection: false
};

const defaultFormState = {
  name: "",
  target: "",
  related_scope_id: undefined,
  domain_brute_type: undefined,
  port_scan_type: undefined,
  alt_dns_dict: undefined,
  file_leak_dict: undefined,
  ...defaultPlugins
};

const formState = reactive({ ...defaultFormState });

// 提交前如实预告任务派生数量（域名逐个建任务，IP/CIDR 合并为一个任务）
const fanoutHint = computed(() => describeTaskFanout(formState.target));

// 字典下拉的可读标签：把磁盘文件名转换为「含义 (规模)」，
// 避免用户需要从 domain_2w.txt / port_top1000.txt 等文件名反推字典规模。
const dictLabelOverrides = {
  get 'domain_2w.txt'() { return taskText('tasks.largeWordlistAbout20000Entries'); },
  get 'domain_top300.txt'() { return taskText('tasks.smallWordlistAbout300Entries'); },
  get 'altdnsdict.txt'() { return taskText('tasks.generatedWordlist'); },
  get 'port_top100.txt'() { return taskText('tasks.top100Ports'); },
  get 'port_top1000.txt'() { return taskText('tasks.top1000Ports'); },
  get 'port_all.txt'() { return taskText('tasks.allPorts165535'); },
  get 'port_custom.txt'() { return taskText('tasks.customPorts'); },
  get 'file_top_200.txt'() { return taskText('tasks.smallWordlistAbout200Entries'); },
  get 'file_top_2000.txt'() { return taskText('tasks.largeWordlistAbout2000Entries'); }
};

const formatDictSize = (bytes) => {
  if (!Number.isFinite(bytes) || bytes <= 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
};

const describeDict = (item) => {
  if (!item) return '';
  const base = dictLabelOverrides[item.name];
  if (base) return base;
  const size = formatDictSize(item.size);
  return size ? `${item.name} (${size})` : item.name;
};

const showModal = () => {
  visible.value = true;
};

const isCategoryAllChecked = (category) => {
  return category.plugins.every(p => formState[p.key]);
};

const toggleCategory = (category) => {
  const allChecked = isCategoryAllChecked(category);
  category.plugins.forEach(p => {
    formState[p.key] = !allChecked;
  });
};

const applyPreset = (type) => {
  if (type === 'fast') {
    Object.keys(defaultPlugins).forEach(k => { formState[k] = false; });
    formState.dns_query_plugin = true;
    formState.domain_brute = true;
    formState.port_scan = true;
    formState.skip_scan_cdn_ip = true;
    formState.site_identify = true;
    message.info(taskText('tasks.quickDiscoveryPresetApplied'));
  } else if (type === 'normal') {
    Object.keys(defaultPlugins).forEach(k => { formState[k] = defaultPlugins[k]; });
    formState.site_identify = true;
    formState.file_leak = true;
    formState.service_detection = true;
    formState.ssl_cert = true;
    message.info(taskText('tasks.standardDiscoveryPresetApplied'));
  } else if (type === 'deep') {
    // 「深度全量」会一并关闭「跳过 CDN」，显著扩大扫描面，先向用户明示后果再套用
    Modal.confirm({
      title: taskText('tasks.applyTheFullDiscoveryPreset'),
      icon: createVNode(ExclamationCircleOutlined, { style: 'color: #faad14;' }),
      content: taskText('tasks.thisEnablesAll16PluginsAndIncludesCdn'),
      okText: taskText('tasks.applyPreset'),
      cancelText: taskText('tasks.cancel'),
      onOk: () => {
        Object.keys(defaultPlugins).forEach(k => { formState[k] = true; });
        formState.skip_scan_cdn_ip = false;
        message.info(taskText('tasks.fullDiscoveryPresetApplied'));
      }
    });
  }
};

const doSubmitTask = async () => {
  submitLoading.value = true;
  try {
    const payload = { ...formState };
    // 🛡️ 服务识别双向严格协同（开启同开，关闭同关）
    payload.npoc_service_detection = !!payload.service_detection;
    const res = await request.post('/task/', payload);
    if (res.code === 200) {
      // 域名目标会被拆分为多个任务，此处按实际返回的任务数如实回报
      const createdCount = Array.isArray(res.items) ? res.items.length : 0;
      message.success(createdCount > 1 ? taskText('tasks.tasksCreatedCount', { count: createdCount }) : taskText('tasks.taskCreated'));
      visible.value = false;
      formState.related_scope_id = undefined;
      fetchTasks(1, pagination.pageSize);
    } else {
      message.error(taskText('tasks.failedToCreateTaskLabel') + (res.data?.error || res.message || taskText('tasks.unknownError')));
    }
  } catch (error) {
    if (!error.errorFields) message.error(taskText('tasks.networkError'));
  } finally {
    submitLoading.value = false;
  }
};

const handleOk = async () => {
  try {
    await formRef.value.validate();
  } catch (error) {
    // 表单校验未通过，交由 antd 展示字段级错误提示
    if (!error.errorFields) message.error(taskText('tasks.networkError'));
    return;
  }

  const { taskCount, text } = fanoutHint.value;

  // 仅在会发生「一个输入派生多个任务」时二次确认，避免用户误以为只下发一个任务
  if (taskCount > 1) {
    Modal.confirm({
      title: taskText('tasks.createMultipleTasks'),
      icon: createVNode(ExclamationCircleOutlined, { style: 'color: #faad14;' }),
      content: taskText('tasks.summaryEachDomainTaskIsQueuedAndExecuted', { summary: text }),
      okText: taskText('tasks.createTasksCount', { count: taskCount }),
      cancelText: taskText('tasks.goBack'),
      onOk: () => doSubmitTask()
    });
    return;
  }

  await doSubmitTask();
};

// ==========================================
// 💥 FOFA 任务下发
// ==========================================
const fofaVisible = ref(false);
const fofaSubmitLoading = ref(false);
const fofaTestLoading = ref(false);
const fofaResultCount = ref(0);
const fofaTested = ref(false);
const policyOptions = ref([]);
const fofaFormRef = ref();

const fofaForm = reactive({
  name: '',
  query: '',
  policy_id: undefined
});

const openFofaModal = async () => {
  fofaForm.name = '';
  fofaForm.query = '';
  fofaForm.policy_id = undefined;
  fofaResultCount.value = 0;
  fofaTested.value = false;
  if (fofaFormRef.value) fofaFormRef.value.clearValidate();

  fofaVisible.value = true;

  try {
    const res = await request.get('/policy/', { params: { page: 1, size: 1000 } });
    if (res.code === 200) {
      policyOptions.value = (res.items || []).map(item => ({
        value: item._id,
        label: item.name
      }));
    }
  } catch (error) {
    console.error('拉取关联策略失败:', error);
  }
};

const testFofaQuery = async () => {
  if (!fofaForm.query) {
    message.warning(taskText('tasks.enterAQueryBeforeTesting'));
    return;
  }

  fofaTestLoading.value = true;
  try {
    const res = await request.post('/task_fofa/test', { query: fofaForm.query });
    if (res.code === 200) {
      fofaResultCount.value = res.data?.size || res.data?.total || 0;
      fofaTested.value = true;
      message.success(taskText('tasks.connectionTestSucceeded'));
    } else {
      fofaResultCount.value = 0;
      fofaTested.value = true;
      message.error(res.message || taskText('tasks.testFailed'));
    }
  } catch (error) {
    fofaResultCount.value = 0;
    fofaTested.value = true;
    message.error(taskText('tasks.testRequestFailedCheckTheConfiguration'));
  } finally {
    fofaTestLoading.value = false;
  }
};

const submitFofaTask = async () => {
  try {
    await fofaFormRef.value.validate();
    fofaSubmitLoading.value = true;
    const res = await request.post('/task_fofa/submit', {
      name: fofaForm.name,
      query: fofaForm.query,
      policy_id: fofaForm.policy_id
    });

    if (res.code === 200) {
      message.success(taskText('tasks.fofaTaskCreated'));
      fofaVisible.value = false;
      fetchTasks(1, pagination.pageSize);
    } else {
      message.error(res.message || taskText('tasks.failedToCreateTask'));
    }
  } catch (error) {
    if (!error.errorFields) message.error(taskText('tasks.networkRequestFailed'));
  } finally {
    fofaSubmitLoading.value = false;
  }
};

const goToGlobalView = () => {
  router.push({
    path: '/taskList/taskDetail',
    query: {
      targetName: '全局',
    }
  });
};

// ==========================================
// 🚀 顶层 Tab 与状态联动
// ==========================================
watch(() => [route.query.tab, route.query.status], ([newTab, newStatus], [oldTab, oldStatus] = []) => {
  // 核心加固：仅在当前路由处于任务管理页面时响应外部 query 联动，避免切至其他页面时误重置
  if (!route.path.startsWith('/taskList')) return;

  const targetTab = newTab === 'task' ? 'task' : (newTab === 'enterprise' ? 'enterprise' : activeMainTab.value);
  const tabChanged = activeMainTab.value !== targetTab;
  if (tabChanged) {
    activeMainTab.value = targetTab;
  }

  const targetForm = targetTab === 'enterprise' ? reconSearchForm : searchForm;
  const statusParam = (typeof newStatus === 'string') ? newStatus : '';
  const statusQueryChanged = newStatus !== oldStatus;
  const statusChanged = targetForm.status !== statusParam;

  if (statusQueryChanged && statusChanged) {
    targetForm.status = statusParam;
  }

  if (tabChanged || (statusQueryChanged && statusChanged)) {
    if (targetTab === 'enterprise') {
      fetchEnterpriseTasks(1, enterprisePagination.pageSize);
    } else {
      fetchTasks(1, pagination.pageSize);
    }
  }
});

const handleMainTabChange = (key) => {
  activeMainTab.value = key;
  const nextQuery = { ...route.query };
  delete nextQuery.view;
  nextQuery.tab = key;
  router.replace({ query: nextQuery });
  if (key === 'enterprise') {
    fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize);
  } else {
    fetchTasks(pagination.current, pagination.pageSize);
  }
  startSmartPolling();
};

// ==========================================
// 📌 生命周期钩子与字典拉取
// ==========================================
onMounted(async () => {
  if (route.query?.view) {
    const nextQuery = { ...route.query };
    delete nextQuery.view;
    router.replace({ query: nextQuery });
  }

  const queryStatus = route.query?.status;
  if (typeof queryStatus === 'string' && queryStatus) {
    if (activeMainTab.value === 'enterprise') {
      reconSearchForm.status = queryStatus;
    } else {
      searchForm.status = queryStatus;
    }
  }

  if (activeMainTab.value === 'enterprise') {
    fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize);
  } else {
    fetchTasks(pagination.current, pagination.pageSize);
  }

  startSmartPolling();

  try {
    const dictRes = await request.get('/dictionary/list');
    if (dictRes.code === 200 && dictRes.data) {
      domainDicts.value = dictRes.data.filter(item => item.category && item.category.includes('子域名爆破') && !item.category.includes('智能'));
      altDnsDicts.value = dictRes.data.filter(item => item.category && item.category.includes('智能子域爆破'));
      fileLeakDicts.value = dictRes.data.filter(item => item.category && (item.category.includes('目录文件泄露') || item.category.includes('目录与文件泄露')));
      portDicts.value = dictRes.data.filter(item => item.category && item.category.includes('端口扫描策略') && item.name !== 'port_alive.txt');

      if (domainDicts.value.length > 0) formState.domain_brute_type = domainDicts.value[0].name;
      if (altDnsDicts.value.length > 0) formState.alt_dns_dict = altDnsDicts.value[0].name;
      if (fileLeakDicts.value.length > 0) formState.file_leak_dict = fileLeakDicts.value[0].name;
      if (portDicts.value.length > 0) formState.port_scan_type = portDicts.value[0].name;
    }
  } catch (error) {
    console.error('拉取字典列表失败:', error);
  }
});

let firstActivation = true;
onActivated(() => {
  // KeepAlive 首次激活时 onMounted 已启动加载，消除并发双重触发
  if (firstActivation) {
    firstActivation = false;
    return;
  }
  if (activeMainTab.value === 'enterprise') {
    fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize, true);
  } else {
    fetchTasks(pagination.current, pagination.pageSize, true);
  }
  startSmartPolling();
});

onDeactivated(() => {
  stopSmartPolling();
  // 离开页面时安全收起弹窗，避免浮层遮挡其他视图
  visible.value = false;
  fofaVisible.value = false;
  syncVisible.value = false;
  tycModalVisible.value = false;
  syncModalVisible.value = false;
});

onUnmounted(() => {
  stopSmartPolling();
});
</script>

<style scoped>
/* ==========================================================================
   任务管理专属样式（基础容器、Hero、胶囊与分页已收敛至 style.css）
   ========================================================================== */
/* 任务列表「资产组」列：组名需弱化显示，与标签层级区分 */
.task-asset-group-name {
  font-size: 12px;
  color: var(--arl-text-secondary);
  line-height: 1.5;
  word-break: break-all;
}

.arl-hero-title .title-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--arl-text-color);
  letter-spacing: -0.2px;
}

.capsule-icon {
  font-size: 13px;
}

.auto-refresh-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--arl-text-secondary);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.task-refresh-btn {
  font-size: 12px;
}

.primary-action-btn {
  box-shadow: 0 2px 4px color-mix(in srgb, var(--arl-theme-color) 20%, transparent);
}

/* ==========================================================================
   中层：任务运行态 4 维状态概览指标卡
   ========================================================================== */
.task-metric-cards-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--arl-border-color);
}

.metric-stat-card {
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
  padding: 8px 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

.metric-stat-card:hover {
  background: var(--arl-bg-white);
  border-color: var(--arl-theme-color);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
  transform: translateY(-1px);
}

.metric-stat-card.active {
  background: var(--arl-bg-white);
  border-color: var(--arl-theme-color);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--arl-theme-color) 15%, transparent);
}

.stat-card-inner {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stat-icon-box {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  flex-shrink: 0;
}

.stat-icon-box.all {
  background: var(--arl-theme-soft-bg);
  color: var(--arl-theme-color);
}

.stat-icon-box.running {
  background: rgba(82, 196, 26, 0.12);
  color: #52c41a;
}

.stat-icon-box.done {
  background: rgba(0, 188, 212, 0.12);
  color: #00bcd4;
}

.stat-icon-box.error {
  background: rgba(255, 77, 79, 0.1);
  color: #ff4d4f;
}

.stat-info {
  min-width: 0;
  flex: 1;
}

.stat-label {
  font-size: 12px;
  color: var(--arl-text-secondary);
  line-height: 1.2;
  display: flex;
  align-items: center;
  gap: 4px;
}

.mini-pulse-beacon {
  width: 5px;
  height: 5px;
  background: #52c41a;
  border-radius: 50%;
  animation: pulseBeacon 1.6s infinite ease-in-out;
}

.stat-value {
  font-size: 17px;
  font-weight: 600;
  color: var(--arl-text-color);
  line-height: 1.3;
  margin-top: 2px;
}

.stat-value.running { color: #52c41a; }
.stat-value.done { color: var(--arl-theme-color); }
.stat-value.error { color: #ff4d4f; }

/* ==========================================================================
   下层：常驻核心检索与折叠高级筛选
   ========================================================================== */
.task-filter-container {
  padding-top: 10px;
}

.resident-filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}

.filter-inputs-group {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-actions-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.input-prefix-icon {
  color: var(--arl-text-secondary);
  opacity: 0.6;
}

.status-option-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}

.status-dot.running { background: #1890ff; }
.status-dot.waiting { background: #d9d9d9; }
.status-dot.done { background: #52c41a; }
.status-dot.stop { background: #faad14; }
.status-dot.error { background: #ff4d4f; }

/* 折叠高级筛选卡片 */
.advanced-filter-panel {
  margin-top: 10px;
  padding: 12px 14px;
  background: var(--arl-bg-light);
  border: 1px dashed var(--arl-border-color);
  border-radius: 6px;
  animation: slideDownFilter 0.2s ease;
}

@keyframes slideDownFilter {
  from { opacity: 0; transform: translateY(-4px); }
  to { opacity: 1; transform: translateY(0); }
}

.advanced-filter-grid {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}

.filter-item {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.filter-label {
  font-size: 13px;
  color: var(--arl-text-secondary);
  white-space: nowrap;
}

.advanced-filter-footer {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  margin-top: 8px;
  padding-top: 6px;
  border-top: 1px solid var(--arl-border-color);
}

/* ==========================================================================
   浮动批量操作激活条
   ========================================================================== */
.floating-batch-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: var(--arl-theme-soft-bg);
  border: 1px solid var(--arl-theme-soft-border);
  border-radius: 6px;
  margin-bottom: 12px;
  animation: batchFadeIn 0.25s ease;
}

@keyframes batchFadeIn {
  from { opacity: 0; transform: translateY(-3px); }
  to { opacity: 1; transform: translateY(0); }
}

.selected-count-badge {
  font-size: 13px;
  color: var(--arl-theme-color);
}

.batch-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ==========================================================================
   表格与数据单元格设计
   ========================================================================== */
.arl-table-card {
  background: var(--arl-bg-white);
  border: 1px solid var(--arl-border-color);
  border-radius: 8px;
  padding: 12px 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
}

.task-title-link {
  font-weight: 500;
  color: var(--arl-theme-color);
  transition: color 0.2s;
}

.task-title-link:hover {
  text-decoration: underline;
}

.task-target-cell {
  max-width: 220px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-family: var(--arl-font-mono);
  color: var(--arl-text-color);
}

.task-target-text {
  max-width: 190px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: inline-block;
}

.target-tooltip-list {
  max-height: 260px;
  overflow-y: auto;
  font-family: var(--arl-font-mono);
}

.target-item-line {
  line-height: 1.8;
  font-size: 12px;
}

/* 统计胶囊 */
.task-stats-capsules {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.stat-capsule {
  display: inline-flex;
  align-items: center;
  font-size: 11px;
  padding: 1px 6px;
  border-radius: 3px;
  line-height: 16px;
  gap: 3px;
  cursor: default;
}

.stat-capsule.site { background: rgba(0, 188, 212, 0.12); color: #00838f; }
.stat-capsule.domain { background: rgba(24, 144, 255, 0.14); color: #1890ff; }
.stat-capsule.ip { background: rgba(82, 196, 26, 0.12); color: #389e0d; }
.stat-capsule.wih { background: rgba(250, 173, 20, 0.15); color: #d48806; }
.stat-capsule.vuln { background: rgba(255, 77, 79, 0.15); color: #cf1322; }

.stat-lbl { opacity: 0.8; font-weight: 400; }
.stat-num { font-weight: 600; }

/* 策略配置 */
.options-badge-trigger {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  color: var(--arl-text-secondary);
  background: var(--arl-bg-light);
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid var(--arl-border-color);
  cursor: pointer;
  transition: all 0.2s;
}

.options-badge-trigger:hover {
  border-color: var(--arl-theme-color);
  color: var(--arl-theme-color);
}

.options-tooltip-content {
  line-height: 1.8;
  font-size: 12px;
  max-width: 320px;
}

.tooltip-header {
  font-weight: 600;
  margin-bottom: 4px;
  padding-bottom: 4px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.2);
}

.option-item-line {
  font-size: 12px;
}

.tooltip-section-title {
  font-size: 11px;
  color: var(--arl-primary-light);
  font-weight: 600;
  margin-top: 4px;
  margin-bottom: 2px;
  letter-spacing: 0.5px;
}

/* 状态标签 */
.task-status-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.task-partial-warn-icon {
  color: #faad14;
  font-size: 14px;
  cursor: pointer;
}

.task-error-notice-icon {
  color: #ff4d4f;
  font-size: 14px;
  cursor: pointer;
}

.task-error-tooltip {
  max-width: 360px;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.6;
}

.task-sync-breakdown {
  margin-top: 2px;
  font-size: 11px;
  font-family: var(--arl-font-mono);
  color: var(--arl-text-secondary);
}

.task-status-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  padding: 1px 8px;
  border-radius: 4px;
  margin-right: 0;
}

.service-time-tooltip {
  min-width: 180px;
  font-size: 12px;
}

.tooltip-row {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  line-height: 1.8;
}

.service-name { opacity: 0.85; }
.service-elapsed { font-weight: 500; font-family: var(--arl-font-mono); }

.task-id-text {
  font-family: var(--arl-font-mono);
  font-size: 12px;
  color: var(--arl-text-secondary);
}
.task-id-text:hover {
  color: var(--arl-theme-color);
}

.task-action-cell {
  display: flex;
  align-items: center;
  gap: 4px;
}

.primary-table-btn {
  padding: 0 4px;
  font-weight: 500;
}

.more-action-btn {
  padding: 0 4px;
  font-size: 12px;
  color: var(--arl-text-secondary);
}
.more-action-btn:hover {
  color: var(--arl-theme-color);
}

/* 同步状态标签 */
.synced-badge-wrapper {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.synced-scope-tag {
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  margin-right: 0;
}

.sync-empty-text {
  color: var(--arl-text-secondary);
  opacity: 0.5;
  font-size: 12px;
}

.unsynced-text {
  color: #faad14;
  font-size: 12px;
  font-weight: 500;
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

/* ==========================================================================
   弹窗排版样式
   ========================================================================== */
.modal-section-card {
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
  padding: 12px 16px;
  margin-bottom: 12px;
}

/* 任务派生数量预告：域名逐个建任务，IP/CIDR 合并为一个任务 */
.target-fanout-hint {
  display: flex;
  align-items: flex-start;
  gap: 6px;
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--arl-text-secondary);
}

.target-fanout-hint .anticon {
  margin-top: 2px;
  color: var(--arl-theme-color);
}

/* 字典下拉被依赖开关禁用时，显式告知解锁位置，避免用户面对灰置控件无从下手 */
.dict-disabled-hint {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--arl-text-secondary);
}

.section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--arl-text-color);
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
}

.section-title-with-actions {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.preset-btn-group {
  display: flex;
  align-items: center;
  gap: 6px;
}

.preset-tip {
  font-size: 12px;
  color: var(--arl-text-secondary);
}

.section-indicator {
  width: 3px;
  height: 12px;
  background: var(--arl-theme-color);
  border-radius: 2px;
  display: inline-block;
}

.plugin-category-box {
  background: var(--arl-bg-white);
  border: 1px solid var(--arl-border-color);
  border-radius: 4px;
  padding: 8px 12px;
  margin-bottom: 8px;
}

.plugin-cat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 6px;
  padding-bottom: 4px;
  border-bottom: 1px dashed var(--arl-border-color);
}

.cat-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--arl-text-color);
}

.plugin-check-label {
  font-size: 12px;
  color: var(--arl-text-color);
}

.fofa-test-result-box {
  margin-top: 8px;
  padding: 6px 12px;
  background: var(--arl-bg-light);
  border-radius: 4px;
  border: 1px solid var(--arl-border-color);
}

.fofa-badge {
  font-size: 12px;
  color: var(--arl-text-color);
}

.count-input-group {
  display: inline-flex;
}

.task-nested-content { margin-top: 6px; }
.task-increment-badge :deep(.ant-badge-count) { background-color: #52c41a; font-size: 10px; }
.task-small-caption { font-size: 10px; }
.task-count-caption { color: var(--arl-text-secondary); font-size: 13px; }
.task-fill-space { flex: 1; }

.metric-stat-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
}

.page-wide-text .stat-label {
  line-height: 1.3;
  flex-wrap: wrap;
  overflow-wrap: anywhere;
}

@media (max-width: 1440px) {
  .page-wide-text .task-metric-cards-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1366px) {
  .task-metric-cards-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .task-metric-cards-row,
  .page-wide-text .task-metric-cards-row {
    grid-template-columns: 1fr;
  }
}
</style>
