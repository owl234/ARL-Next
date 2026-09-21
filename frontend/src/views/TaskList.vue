<template>
  <div class="arl-task-page">
    <!-- 1. 吸顶操作栏与英雄头部卡片 (一体化常驻吸附在页面最顶部) -->
    <div ref="actionBarRef" class="arl-task-hero-card">
      <!-- 顶层主栏：标题 + 视角切换胶囊 + 全局控制与主创建按钮 -->
      <div class="task-hero-unified-bar">
        <!-- 左侧：页面标识与顶层 Tab 切换胶囊 -->
        <div class="task-hero-left">
          <div class="task-hero-title">
            <span class="title-text">任务管理中心</span>
          </div>
          <div class="task-view-capsule-switcher">
            <button
              class="capsule-btn"
              :class="{ active: activeMainTab === 'enterprise' }"
              @click="handleMainTabChange('enterprise')"
              title="切换至企业测绘任务 (OSINT)"
            >
              <bank-outlined class="capsule-icon" />
              <span>企业测绘任务</span>
              <span class="capsule-count" v-if="enterpriseRunningCount > 0">
                <span class="pulse-dot"></span>
                {{ enterpriseRunningCount }} 运行中
              </span>
            </button>
            <button
              class="capsule-btn"
              :class="{ active: activeMainTab === 'task' }"
              @click="handleMainTabChange('task')"
              title="切换至资产侦查任务 (ASM)"
            >
              <global-outlined class="capsule-icon" />
              <span>资产侦查任务</span>
              <span class="capsule-count" v-if="taskMetricCounts.running > 0">
                <span class="pulse-dot"></span>
                {{ taskMetricCounts.running }} 运行中
              </span>
            </button>
          </div>
        </div>

        <!-- 右侧：全局自适应静默轮询开关 + 手动刷新 + 主操作按钮 -->
        <div class="task-hero-right">
          <a-tooltip :title="autoRefreshEnabled ? '自动刷新已开启：有运行任务时每 8 秒静默同步' : '自动刷新已暂停'">
            <div class="auto-refresh-toggle">
              <a-switch
                v-model:checked="autoRefreshEnabled"
                size="small"
                @change="handleAutoRefreshToggle"
              />
              <span class="toggle-label">自动刷新</span>
            </div>
          </a-tooltip>

          <a-tooltip :title="lastRefreshTimeText ? `最后更新于: ${lastRefreshTimeText}` : '点击刷新列表数据'">
            <a-button
              size="small"
              class="task-refresh-btn"
              :loading="isRefreshing"
              @click="handleManualRefresh"
            >
              <template #icon><reload-outlined /></template>
              刷新
            </a-button>
          </a-tooltip>

          <a-divider type="vertical" style="height: 18px; margin: 0 4px;" />

          <!-- 企业测绘专属操作 -->
          <template v-if="activeMainTab === 'enterprise'">
            <a-button type="primary" size="small" class="primary-action-btn" @click="showTycModal">
              <template #icon><plus-outlined /></template>
              新建企业资产查询
            </a-button>
          </template>

          <!-- 资产侦查专属操作 -->
          <template v-else-if="activeMainTab === 'task'">
            <a-button type="primary" size="small" class="primary-action-btn" @click="showModal">
              <template #icon><plus-outlined /></template>
              新建侦查任务
            </a-button>
            <a-button size="small" @click="openFofaModal">
              <template #icon><thunderbolt-outlined /></template>
              FOFA 任务下发
            </a-button>
            <a-button size="small" @click="goToGlobalView">
              <template #icon><compass-outlined /></template>
              全局查看
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
          title="点击查看全部任务"
        >
          <div class="stat-card-inner">
            <div class="stat-icon-box all">
              <appstore-outlined />
            </div>
            <div class="stat-info">
              <div class="stat-label">全部任务</div>
              <div class="stat-value">{{ currentTotalCount }}</div>
            </div>
          </div>
        </div>

        <div
          class="metric-stat-card"
          :class="{ active: currentStatusFilter === 'running' }"
          @click="toggleStatusFilter('running')"
          title="点击快速筛选进行中/排队中的任务"
        >
          <div class="stat-card-inner">
            <div class="stat-icon-box running">
              <sync-outlined :spin="currentRunningCount > 0" />
            </div>
            <div class="stat-info">
              <div class="stat-label">
                <span>进行中 / 排队</span>
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
          title="点击快速筛选已完成的任务"
        >
          <div class="stat-card-inner">
            <div class="stat-icon-box done">
              <check-circle-outlined />
            </div>
            <div class="stat-info">
              <div class="stat-label">已完成</div>
              <div class="stat-value done">{{ currentDoneCount }}</div>
            </div>
          </div>
        </div>

        <div
          class="metric-stat-card"
          :class="{ active: currentStatusFilter === 'error' || currentStatusFilter === 'stop' }"
          @click="toggleStatusFilter('error')"
          title="点击快速筛选异常或已停止的任务"
        >
          <div class="stat-card-inner">
            <div class="stat-icon-box error">
              <close-circle-outlined />
            </div>
            <div class="stat-info">
              <div class="stat-label">异常 / 已停止</div>
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
                placeholder="任务名称"
                style="width: 220px;"
                allowClear
                @pressEnter="onReconSearch"
              >
                <template #prefix><search-outlined class="input-prefix-icon" /></template>
              </a-input>

              <a-input
                v-model:value="reconSearchForm.target"
                placeholder="查询目标企业/主体"
                style="width: 220px;"
                allowClear
                @pressEnter="onReconSearch"
              >
                <template #prefix><bank-outlined class="input-prefix-icon" /></template>
              </a-input>

              <a-select
                v-model:value="reconSearchForm.status"
                placeholder="任务状态"
                style="width: 140px;"
                allowClear
                @change="onReconSearch"
              >
                <a-select-option value="">全部状态</a-select-option>
                <a-select-option value="running">
                  <span class="status-option-item"><span class="status-dot running"></span> 进行中</span>
                </a-select-option>
                <a-select-option value="waiting">
                  <span class="status-option-item"><span class="status-dot waiting"></span> 等待中</span>
                </a-select-option>
                <a-select-option value="done">
                  <span class="status-option-item"><span class="status-dot done"></span> 已完成</span>
                </a-select-option>
                <a-select-option value="stop">
                  <span class="status-option-item"><span class="status-dot stop"></span> 已停止</span>
                </a-select-option>
                <a-select-option value="error">
                  <span class="status-option-item"><span class="status-dot error"></span> 异常失败</span>
                </a-select-option>
              </a-select>

              <a-range-picker
                v-model:value="reconSearchForm.dateRange"
                :presets="rangePresets"
                :placeholder="['结束开始日期', '结束截止日期']"
                format="YYYY-MM-DD"
                style="width: 240px;"
                allowClear
                @change="onReconSearch"
              />
            </div>

            <div class="filter-actions-group">
              <a-button type="primary" size="middle" @click="onReconSearch">查 询</a-button>
              <a-button size="middle" @click="resetReconSearch">重 置</a-button>
            </div>
          </div>
        </template>

        <!-- 2. 资产侦查任务检索栏 (常驻 + 高级折叠) -->
        <template v-else-if="activeMainTab === 'task'">
          <div class="resident-filter-bar">
            <div class="filter-inputs-group">
              <a-input
                v-model:value="searchForm.name"
                placeholder="任务名称"
                style="width: 210px;"
                allowClear
                @pressEnter="onSearch"
              >
                <template #prefix><search-outlined class="input-prefix-icon" /></template>
              </a-input>

              <a-input
                v-model:value="searchForm.target"
                placeholder="目标 (IP/域名/段)"
                style="width: 210px;"
                allowClear
                @pressEnter="onSearch"
              >
                <template #prefix><global-outlined class="input-prefix-icon" /></template>
              </a-input>

              <a-select
                v-model:value="searchForm.status"
                placeholder="任务状态"
                style="width: 140px;"
                allowClear
                @change="onSearch"
              >
                <a-select-option value="">全部状态</a-select-option>
                <a-select-option value="running">
                  <span class="status-option-item"><span class="status-dot running"></span> 进行中</span>
                </a-select-option>
                <a-select-option value="waiting">
                  <span class="status-option-item"><span class="status-dot waiting"></span> 等待中</span>
                </a-select-option>
                <a-select-option value="done">
                  <span class="status-option-item"><span class="status-dot done"></span> 已完成</span>
                </a-select-option>
                <a-select-option value="stop">
                  <span class="status-option-item"><span class="status-dot stop"></span> 已停止</span>
                </a-select-option>
                <a-select-option value="error">
                  <span class="status-option-item"><span class="status-dot error"></span> 异常失败</span>
                </a-select-option>
              </a-select>
            </div>

            <div class="filter-actions-group">
              <a-button type="primary" size="middle" @click="onSearch">查 询</a-button>
              <a-button size="middle" @click="resetSearch">重 置</a-button>
              <a-button
                size="middle"
                :type="isAdvancedFilterOpen ? 'primary' : 'default'"
                :ghost="isAdvancedFilterOpen"
                @click="isAdvancedFilterOpen = !isAdvancedFilterOpen"
              >
                <template #icon><filter-outlined /></template>
                {{ isAdvancedFilterOpen ? '收起筛选' : '高级筛选' }}
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
                <span class="filter-label">Task_Id:</span>
                <a-input
                  v-model:value="searchForm.task_id"
                  placeholder="请输入24位 Task_Id"
                  style="width: 220px;"
                  allowClear
                  @pressEnter="onSearch"
                />
              </div>

              <div class="filter-item">
                <span class="filter-label">任务类型:</span>
                <a-select
                  v-model:value="searchForm.type"
                  placeholder="全部类型"
                  style="width: 180px;"
                  allowClear
                  @change="onSearch"
                >
                  <a-select-option value="task">资产侦查任务</a-select-option>
                  <a-select-option value="monitor">资产监控任务</a-select-option>
                  <a-select-option value="risk_cruising">风险巡航任务</a-select-option>
                  <a-select-option value="site_update">资产站点更新</a-select-option>
                  <a-select-option value="wih">WIH 监控任务</a-select-option>
                </a-select>
              </div>

              <div class="filter-item">
                <span class="filter-label">站点数量:</span>
                <a-input-group compact class="count-input-group">
                  <a-select v-model:value="searchForm.site_operator" style="width: 65px;">
                    <a-select-option value="=">=</a-select-option>
                    <a-select-option value=">">&gt;</a-select-option>
                    <a-select-option value="<">&lt;</a-select-option>
                  </a-select>
                  <a-input
                    v-model:value="searchForm.site_count"
                    placeholder="数量"
                    style="width: 115px;"
                    allowClear
                    @pressEnter="onSearch"
                  />
                </a-input-group>
              </div>

              <div class="filter-item">
                <span class="filter-label">域名数量:</span>
                <a-input-group compact class="count-input-group">
                  <a-select v-model:value="searchForm.domain_operator" style="width: 65px;">
                    <a-select-option value="=">=</a-select-option>
                    <a-select-option value=">">&gt;</a-select-option>
                    <a-select-option value="<">&lt;</a-select-option>
                  </a-select>
                  <a-input
                    v-model:value="searchForm.domain_count"
                    placeholder="数量"
                    style="width: 115px;"
                    allowClear
                    @pressEnter="onSearch"
                  />
                </a-input-group>
              </div>

              <div class="filter-item">
                <span class="filter-label">WIH数量:</span>
                <a-input-group compact class="count-input-group">
                  <a-select v-model:value="searchForm.wih_operator" style="width: 65px;">
                    <a-select-option value="=">=</a-select-option>
                    <a-select-option value=">">&gt;</a-select-option>
                    <a-select-option value="<">&lt;</a-select-option>
                  </a-select>
                  <a-input
                    v-model:value="searchForm.wih_count"
                    placeholder="数量"
                    style="width: 115px;"
                    allowClear
                    @pressEnter="onSearch"
                  />
                </a-input-group>
              </div>
            </div>

            <div class="advanced-filter-footer">
              <a-button size="small" type="link" @click="resetAdvancedFilters">清空高级条件</a-button>
              <a-button size="small" type="link" @click="isAdvancedFilterOpen = false">收 起</a-button>
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
          已选中 <b>{{ activeMainTab === 'enterprise' ? enterpriseSelectedRowKeys.length : selectedRowKeys.length }}</b> 项任务
        </span>
      </div>

      <div class="batch-right">
        <!-- 企业测绘批量操作 -->
        <template v-if="activeMainTab === 'enterprise'">
          <a-popconfirm
            title="确定要批量重启选中的任务吗？"
            ok-text="确定"
            cancel-text="取消"
            @confirm="handleBatchRestartEnterprise"
          >
            <a-button size="small">
              <template #icon><sync-outlined /></template>
              批量重启
            </a-button>
          </a-popconfirm>

          <a-button size="small" @click="handleBatchExportEnterprise">
            <template #icon><export-outlined /></template>
            批量导出
          </a-button>

          <a-popconfirm
            title="确定要批量删除选中的企业任务吗？"
            ok-text="确定"
            cancel-text="取消"
            @confirm="handleBatchDeleteEnterprise"
          >
            <a-button size="small" danger>
              <template #icon><delete-outlined /></template>
              批量删除
            </a-button>
          </a-popconfirm>

          <a-button size="small" type="link" @click="enterpriseSelectedRowKeys = []">取消选择</a-button>
        </template>

        <!-- 资产侦查批量操作 -->
        <template v-else-if="activeMainTab === 'task'">
          <a-button size="small" @click="handleBatchStop">
            <template #icon><stop-outlined /></template>
            批量停止
          </a-button>

          <a-dropdown>
            <template #overlay>
              <a-menu @click="handleBatchExport">
                <a-menu-item key="cip">C段 批量导出</a-menu-item>
                <a-menu-item key="domain">域名批量导出</a-menu-item>
                <a-menu-item key="ip">IP 批量导出</a-menu-item>
                <a-menu-item key="ip_port">IP 端口批量导出</a-menu-item>
                <a-menu-item key="site">站点批量导出</a-menu-item>
                <a-menu-item key="url">URL 批量导出</a-menu-item>
                <a-menu-item key="wih">WIH 批量导出</a-menu-item>
              </a-menu>
            </template>
            <a-button size="small">
              <template #icon><export-outlined /></template>
              批量导出 <down-outlined />
            </a-button>
          </a-dropdown>

          <a-button size="small" danger @click="handleBatchDelete">
            <template #icon><delete-outlined /></template>
            批量删除
          </a-button>

          <a-button size="small" type="link" @click="selectedRowKeys = []">取消选择</a-button>
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
          class="modern-task-table"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'name'">
              <a class="task-title-link" @click="viewEnterpriseTask(record)">{{ record.name }}</a>
            </template>

            <template v-else-if="column.key === 'target'">
              <span class="task-target-text" :title="record.target">{{ record.target }}</span>
            </template>

            <template v-else-if="column.key === 'policy_options'">
              <a-tooltip v-if="hasEnterpriseOptions(record)" placement="bottom">
                <template #title>
                  <div class="options-tooltip-content">
                    <div class="tooltip-header">
                      {{ record.task_type === 'tyc' ? '天眼查测绘策略' : '工信部ICP查询策略' }}
                    </div>
                    <template v-if="record.task_type === 'tyc'">
                      <div class="tooltip-section-title">穿透策略</div>
                      <div class="option-item-line">• 投资穿透层级: {{ record.depth || 1 }} 层</div>
                      <div class="option-item-line">• 出资比例阈值: ≥ {{ record.invest_ratio !== undefined && record.invest_ratio !== null ? record.invest_ratio : 50 }}%</div>
                      <div class="option-item-line">• 工信部ICP双轨: {{ record.enable_icp !== false ? '已开启' : '未开启' }}</div>
                      <div class="tooltip-section-title" style="margin-top: 6px;">测绘维度</div>
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
                <span>默认配置</span>
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
                <a-tooltip :title="`核心资产: ${(record.statistic.asset_cnt || 0) - (record.statistic.invest_cnt || 0)}`">
                  <span class="stat-capsule domain">
                    <span class="stat-lbl">核心</span>
                    <span class="stat-num">{{ (record.statistic.asset_cnt || 0) - (record.statistic.invest_cnt || 0) }}</span>
                  </span>
                </a-tooltip>
                <a-tooltip v-if="record.statistic.invest_cnt !== undefined" :title="`对外投资: ${record.statistic.invest_cnt}`">
                  <span class="stat-capsule site">
                    <span class="stat-lbl">投资</span>
                    <span class="stat-num">{{ record.statistic.invest_cnt }}</span>
                  </span>
                </a-tooltip>
              </div>
              <span v-else style="color: var(--arl-text-secondary);">-</span>
            </template>

            <template v-else-if="column.key === 'sync_status'">
              <span v-if="record.sync_badge_status === 'no_web'" class="sync-empty-text">
                无网站资产
              </span>
              <div v-else-if="record.synced_scope_id" class="synced-badge-wrapper">
                <a-tag
                  color="blue"
                  class="synced-scope-tag"
                  @click="goToScope(record.synced_scope_id)"
                  title="点击前往该资产分组"
                >
                  <export-outlined />
                  <span>{{ record.synced_scope_name || '已同步' }}</span>
                </a-tag>
                <a-badge v-if="record.has_increment" count="有增量" :number-style="{ backgroundColor: '#52c41a', fontSize: '10px' }" />
              </div>
              <span v-else class="unsynced-text">
                <span class="status-dot stop"></span> 未同步
              </span>
            </template>

            <template v-else-if="column.key === 'action'">
              <div class="task-action-cell">
                <a-button type="link" size="small" class="primary-table-btn" @click="viewEnterpriseTask(record)">详情</a-button>

                <template v-if="record.sync_badge_status === 'no_web'">
                  <a-tooltip title="当前任务无网站资产可同步">
                    <a-button type="link" size="small" disabled>同步</a-button>
                  </a-tooltip>
                </template>
                <a-button
                  v-else
                  type="link"
                  size="small"
                  @click="handleSyncEnterprise(record)"
                  :disabled="record.status !== 'done' && record.status !== 'stop'"
                >
                  {{ record.synced_scope_id ? (record.has_increment ? '同步增量' : '再次同步') : '同步' }}
                </a-button>

                <a-dropdown>
                  <template #overlay>
                    <a-menu>
                      <a-menu-item key="export" @click="handleExportEnterprise(record)">
                        <export-outlined /> 导出 Excel 报告
                      </a-menu-item>
                      <a-menu-item
                        key="stop"
                        :disabled="record.status === 'done' || record.status === 'stop' || record.status === 'error'"
                        @click="handleStopEnterprise(record)"
                      >
                        <stop-outlined /> 停止任务
                      </a-menu-item>
                      <a-menu-item
                        key="restart"
                        :disabled="record.status === 'running' || record.status === 'waiting'"
                        @click="handleRestartEnterprise(record)"
                      >
                        <sync-outlined /> 重启任务
                      </a-menu-item>
                      <a-menu-divider />
                      <a-menu-item key="delete" danger @click="handleDeleteEnterprise(record)">
                        <delete-outlined /> 删除任务
                      </a-menu-item>
                    </a-menu>
                  </template>
                  <a-button type="text" size="small" class="more-action-btn">
                    更多 <down-outlined style="font-size: 10px;" />
                  </a-button>
                </a-dropdown>
              </div>
            </template>
          </template>
        </a-table>

        <div class="task-pagination-bar">
          <div class="pagination-info">
            共 {{ Math.ceil(enterprisePagination.total / enterprisePagination.pageSize) || 1 }} 页 / {{ enterprisePagination.total }} 条数据
          </div>
          <a-pagination
            :pageSizeOptions="['10', '20', '50']"
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
          class="modern-task-table"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'name'">
              <a class="task-title-link" @click="viewTask(record)">{{ record.name }}</a>
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
                <a-tooltip v-if="record.statistic.site_cnt !== undefined" :title="`站点: ${record.statistic.site_cnt}`">
                  <span class="stat-capsule site">
                    <span class="stat-lbl">站点</span>
                    <span class="stat-num">{{ record.statistic.site_cnt }}</span>
                  </span>
                </a-tooltip>
                <a-tooltip v-if="record.statistic.domain_cnt !== undefined" :title="`域名: ${record.statistic.domain_cnt}`">
                  <span class="stat-capsule domain">
                    <span class="stat-lbl">域名</span>
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
                <a-tooltip v-if="record.statistic.vuln_cnt !== undefined && record.statistic.vuln_cnt > 0" :title="`风险: ${record.statistic.vuln_cnt}`">
                  <span class="stat-capsule vuln">
                    <span class="stat-lbl">风险</span>
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
                    <div class="tooltip-header">已启用策略与配置</div>
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
              <a-tooltip v-if="record.service && record.service.length > 0" placement="bottom">
                <template #title>
                  <div class="service-time-tooltip">
                    <div class="tooltip-header">插件执行耗时明细</div>
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
            </template>

            <template v-else-if="column.key === 'task_id'">
              <a class="task-id-text" @click="viewTask(record)" :title="record._id">{{ record._id }}</a>
            </template>

            <template v-else-if="column.key === 'action'">
              <div class="task-action-cell">
                <a-button type="link" size="small" class="primary-table-btn" @click="viewTask(record)">详情</a-button>

                <a-button
                  type="link"
                  size="small"
                  :loading="record.restarting"
                  :disabled="(record.status !== 'done' && record.status !== 'stop' && record.status !== 'error') || record.restarting"
                  @click="restartTask(record)"
                >
                  重启
                </a-button>

                <a-dropdown>
                  <template #overlay>
                    <a-menu>
                      <a-menu-item
                        key="sync"
                        :disabled="record.status !== 'done' && record.status !== 'stop' && record.status !== 'error'"
                        @click="syncTask(record)"
                      >
                        <sync-outlined /> 同步至资产组
                      </a-menu-item>
                      <a-menu-item key="export" @click="exportTask(record)">
                        <export-outlined /> 导出 Excel 报告
                      </a-menu-item>
                      <a-menu-item
                        key="stop"
                        :disabled="record.status === 'done' || record.status === 'stop' || record.status === 'error'"
                        @click="stopSingleTask(record)"
                      >
                        <stop-outlined /> 停止任务
                      </a-menu-item>
                      <a-menu-divider />
                      <a-menu-item
                        key="delete"
                        danger
                        :disabled="record.status !== 'done' && record.status !== 'stop' && record.status !== 'error'"
                        @click="deleteSingleTask(record)"
                      >
                        <delete-outlined /> 删除任务
                      </a-menu-item>
                    </a-menu>
                  </template>
                  <a-button type="text" size="small" class="more-action-btn">
                    更多 <down-outlined style="font-size: 10px;" />
                  </a-button>
                </a-dropdown>
              </div>
            </template>
          </template>
        </a-table>

        <div class="task-pagination-bar">
          <div class="pagination-info">
            共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据
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
      title="新建资产侦查任务"
      @ok="handleOk"
      :confirmLoading="submitLoading"
      width="640px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      okText="下发任务"
      cancelText="取 消"
      :bodyStyle="{ padding: '16px 24px' }"
    >
      <a-form
        ref="formRef"
        :model="formState"
        layout="vertical"
      >
        <!-- A. 基础信息卡片 -->
        <div class="modal-section-card">
          <div class="section-title">
            <span class="section-indicator"></span> 基础信息
          </div>
          <a-row :gutter="16">
            <a-col :span="24">
              <a-form-item label="任务名称" name="name" :rules="[{ required: true, message: '请输入任务名称' }]">
                <a-input v-model:value="formState.name" placeholder="例如：某集团边界资产探测_2026Q3" />
              </a-form-item>
            </a-col>
            <a-col :span="24">
              <a-form-item label="探测目标" name="target" :rules="[{ required: true, message: '请输入目标' }]">
                <a-textarea
                  v-model:value="formState.target"
                  placeholder="请输入目标，支持域名 (example.com)、IP (1.1.1.1)、或 IP 掩码段 (192.168.1.0/24)，多个目标请换行输入"
                  :rows="3"
                  style="resize: vertical;"
                />
              </a-form-item>
            </a-col>
          </a-row>
        </div>

        <!-- B. 字典与策略配置 -->
        <div class="modal-section-card">
          <div class="section-title">
            <span class="section-indicator"></span> 字典与策略配置
          </div>
          <a-row :gutter="12">
            <a-col :span="12">
              <a-form-item label="域名爆破字典" name="domain_brute_type" :rules="[{ required: true }]">
                <a-select v-model:value="formState.domain_brute_type" placeholder="请选择字典">
                  <a-select-option v-for="item in domainDicts" :key="item.name" :value="item.name">{{ item.name }}</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="智能子域字典" name="alt_dns_dict" :rules="[{ required: true }]">
                <a-select v-model:value="formState.alt_dns_dict" placeholder="请选择字典">
                  <a-select-option v-for="item in altDnsDicts" :key="item.name" :value="item.name">{{ item.name }}</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="端口扫描类型" name="port_scan_type" :rules="[{ required: true }]">
                <a-select v-model:value="formState.port_scan_type" placeholder="请选择策略">
                  <a-select-option v-for="item in portDicts" :key="item.name" :value="item.name">{{ item.name }}</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
            <a-col :span="12">
              <a-form-item label="目录泄露字典" name="file_leak_dict" :rules="[{ required: true }]">
                <a-select v-model:value="formState.file_leak_dict" placeholder="请选择字典">
                  <a-select-option v-for="item in fileLeakDicts" :key="item.name" :value="item.name">{{ item.name }}</a-select-option>
                </a-select>
              </a-form-item>
            </a-col>
          </a-row>
        </div>

        <!-- C. 扫描插件启用配置 (支持预设与按类全选) -->
        <div class="modal-section-card">
          <div class="section-title-with-actions">
            <div class="section-title">
              <span class="section-indicator"></span> 扫描插件与调度策略
            </div>
            <div class="preset-btn-group">
              <span class="preset-tip">快捷预设:</span>
              <a-button size="small" @click="applyPreset('fast')">快速侦查</a-button>
              <a-button size="small" @click="applyPreset('normal')">常规探测</a-button>
              <a-button size="small" @click="applyPreset('deep')">深度全量</a-button>
            </div>
          </div>

          <div v-for="(category, catIndex) in pluginCategories" :key="catIndex" class="plugin-category-box">
            <div class="plugin-cat-header">
              <span class="cat-title">{{ category.title }}</span>
              <a-button size="small" type="link" @click="toggleCategory(category)">
                {{ isCategoryAllChecked(category) ? '取消全选' : '全选本类' }}
              </a-button>
            </div>
            <a-row :gutter="[12, 8]">
              <a-col :span="8" v-for="item in category.plugins" :key="item.key">
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
      title="同步任务至资产分组"
      @ok="handleSyncOk"
      :confirmLoading="syncLoading"
      width="480px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
    >
      <div style="margin: 16px 0 8px 0;">
        <p style="color: var(--arl-text-secondary); font-size: 13px;">请选择将该任务探测出的资产数据关联归属的资产分组：</p>
      </div>
      <a-form :model="syncFormState" layout="vertical">
        <a-form-item label="目标资产组" name="scope_id" :rules="[{ required: true, message: '请选择资产分组' }]">
          <a-select
            v-model:value="syncFormState.scope_id"
            placeholder="请选择资产分组"
            :options="syncOptions"
            allowClear
          >
            <template #notFoundContent>
              <div style="text-align: center; padding: 20px 0;">
                <p style="color: var(--arl-text-secondary); margin-top: 8px;">未找到匹配的目标资产分组</p>
              </div>
            </template>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 6. FOFA 任务下发弹窗 -->
    <a-modal
      v-model:open="fofaVisible"
      title="FOFA 任务下发"
      @ok="submitFofaTask"
      :confirmLoading="fofaSubmitLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      okText="下 发"
      cancelText="取 消"
      :bodyStyle="{ padding: '20px 28px' }"
    >
      <a-form
        ref="fofaFormRef"
        :model="fofaForm"
        layout="vertical"
      >
        <a-form-item label="任务名称" name="name" :rules="[{ required: true, message: '请输入任务名称' }]">
          <a-input v-model:value="fofaForm.name" placeholder="请输入任务名称" />
        </a-form-item>

        <a-form-item label="FOFA 查询语句" name="query" :rules="[{ required: true, message: '请输入查询语句' }]">
          <div style="display: flex; gap: 8px; align-items: center;">
            <a-input v-model:value="fofaForm.query" placeholder='例如：app="Apache" && country="CN"' style="flex: 1;" />
            <a-button type="primary" ghost @click="testFofaQuery" :loading="fofaTestLoading">连通测试</a-button>
          </div>
          <div v-if="fofaTested" class="fofa-test-result-box">
            <span class="fofa-badge">查询结果数: <b>{{ fofaResultCount }}</b></span>
          </div>
        </a-form-item>

        <a-form-item label="关联策略 (可选)" name="policy_id">
          <a-select
            v-model:value="fofaForm.policy_id"
            placeholder="请选择关联策略 (默认使用系统默认策略)"
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
defineOptions({ name: 'TaskList' });

import { ref, reactive, onMounted, computed, createVNode, watch, onActivated, onDeactivated, onUnmounted } from 'vue';
import { useSticky } from '../utils/useSticky';
import { Modal, message, Checkbox } from 'ant-design-vue';
import { useRouter, useRoute } from 'vue-router';
import {
  SearchOutlined, DownOutlined, ExclamationCircleOutlined, ExportOutlined,
  ReloadOutlined, FilterOutlined, CheckCircleOutlined,
  CloseCircleOutlined, ClockCircleOutlined, StopOutlined, PlusOutlined,
  DeleteOutlined, SyncOutlined, SettingOutlined, AppstoreOutlined,
  GlobalOutlined, BankOutlined, ThunderboltOutlined, CompassOutlined
} from '@ant-design/icons-vue';
import dayjs from 'dayjs';
import request from '../utils/request';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import TycTaskModal from '../components/TycTaskModal.vue';
import SyncToScopeModal from '../components/SyncToScopeModal.vue';

// --- 吸顶配置 ---
const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

// --- 路由与顶层 Tab 联动逻辑 ---
const router = useRouter();
const route = useRoute();
const activeMainTab = ref(route.query.tab === 'task' ? 'task' : 'enterprise');

// --- 字典配置 ---
const domainDicts = ref([]);
const altDnsDicts = ref([]);
const fileLeakDicts = ref([]);
const portDicts = ref([]);

// --- 状态中文化与插件中文名映射表 ---
const pluginNameMap = {
  domain_brute: '域名爆破',
  dns_query_plugin: '域名查询',
  arl_search: '历史查询',
  alt_dns: 'DNS智能生成',
  recursive_domain_brute: '递归爆破',
  port_scan: '端口扫描',
  ssl_cert: 'SSL证书获取',
  service_detection: '服务识别',
  os_detection: '系统识别',
  find_site: '站点发现',
  site_identify: '指纹识别',
  search_engines: '搜索引擎',
  site_spider: '站点爬虫',
  file_leak: '文件泄露',
  find_vhost: 'Host碰撞',
  findvhost: 'Host碰撞',
  npoc_service_detection: 'Python服务识别',
  poc_run: 'PoC验证',
  nuclei_scan: 'Nuclei扫描',
  weak_brute: '弱口令爆破',
  wih_domain_update: 'WIH更新',
  web_info_hunter: 'WIH探测',
  running: '运行中',
  waiting: '排队等待',
  done: '已完成',
  stop: '已停止',
  error: '异常失败'
};

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

const currentTotalCount = computed(() => {
  return activeMainTab.value === 'enterprise' ? enterprisePagination.total : pagination.total;
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

// 拉取资产侦查任务 4 维指标计数
const fetchTaskMetricCounts = async () => {
  try {
    const [runningRes, waitingRes, doneRes, errorRes, stopRes] = await Promise.allSettled([
      request.get('/task/', { params: { status: 'running', size: 1 } }),
      request.get('/task/', { params: { status: 'waiting', size: 1 } }),
      request.get('/task/', { params: { status: 'done', size: 1 } }),
      request.get('/task/', { params: { status: 'error', size: 1 } }),
      request.get('/task/', { params: { status: 'stop', size: 1 } })
    ]);

    const running = (runningRes.status === 'fulfilled' && runningRes.value.code === 200 ? (runningRes.value.total || 0) : 0);
    const waiting = (waitingRes.status === 'fulfilled' && waitingRes.value.code === 200 ? (waitingRes.value.total || 0) : 0);
    const done = (doneRes.status === 'fulfilled' && doneRes.value.code === 200 ? (doneRes.value.total || 0) : 0);
    const error = (errorRes.status === 'fulfilled' && errorRes.value.code === 200 ? (errorRes.value.total || 0) : 0);
    const stop = (stopRes.status === 'fulfilled' && stopRes.value.code === 200 ? (stopRes.value.total || 0) : 0);

    taskMetricCounts.running = running + waiting;
    taskMetricCounts.done = done;
    taskMetricCounts.abnormal = error + stop;
  } catch (e) {
    console.error('获取资产侦查指标失败:', e);
  }
};

// 拉取企业测绘任务 4 维指标计数
const fetchEnterpriseMetricCounts = async () => {
  try {
    const [runningRes, waitingRes, doneRes, errorRes, stopRes] = await Promise.allSettled([
      request.get('/icp/task', { params: { status: 'running', size: 1 } }),
      request.get('/icp/task', { params: { status: 'waiting', size: 1 } }),
      request.get('/icp/task', { params: { status: 'done', size: 1 } }),
      request.get('/icp/task', { params: { status: 'error', size: 1 } }),
      request.get('/icp/task', { params: { status: 'stop', size: 1 } })
    ]);

    const running = (runningRes.status === 'fulfilled' && runningRes.value.code === 200 ? (runningRes.value.total || 0) : 0);
    const waiting = (waitingRes.status === 'fulfilled' && waitingRes.value.code === 200 ? (waitingRes.value.total || 0) : 0);
    const done = (doneRes.status === 'fulfilled' && doneRes.value.code === 200 ? (doneRes.value.total || 0) : 0);
    const error = (errorRes.status === 'fulfilled' && errorRes.value.code === 200 ? (errorRes.value.total || 0) : 0);
    const stop = (stopRes.status === 'fulfilled' && stopRes.value.code === 200 ? (stopRes.value.total || 0) : 0);

    enterpriseMetricCounts.running = running + waiting;
    enterpriseMetricCounts.done = done;
    enterpriseMetricCounts.abnormal = error + stop;
    enterpriseRunningCount.value = running + waiting;
  } catch (e) {
    console.error('获取企业测绘指标失败:', e);
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
      if (enterpriseMetricCounts.running > 0) {
        await fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize, true);
        fetchEnterpriseMetricCounts();
      }
    } else {
      if (taskMetricCounts.running > 0) {
        await fetchTasks(pagination.current, pagination.pageSize, true);
        fetchTaskMetricCounts();
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
    message.success('已开启任务自动刷新 (检测到运行中任务时静默同步)');
    startSmartPolling();
  } else {
    message.info('已暂停自动刷新');
    stopSmartPolling();
  }
};

const handleManualRefresh = async () => {
  isRefreshing.value = true;
  try {
    if (activeMainTab.value === 'enterprise') {
      await fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize);
      await fetchEnterpriseMetricCounts();
    } else {
      await fetchTasks(pagination.current, pagination.pageSize);
      await fetchTaskMetricCounts();
    }
    lastRefreshTime.value = new Date();
    message.success('任务列表已刷新');
  } catch (e) {
    message.error('刷新失败');
  } finally {
    isRefreshing.value = false;
  }
};

// ==========================================
// 🏢 企业测绘任务专属逻辑 (OSINT)
// ==========================================
const rangePresets = ref([
  { label: '今天', value: [dayjs().startOf('day'), dayjs().endOf('day')] },
  { label: '近 7 天', value: [dayjs().subtract(6, 'day').startOf('day'), dayjs().endOf('day')] },
  { label: '近 30 天', value: [dayjs().subtract(29, 'day').startOf('day'), dayjs().endOf('day')] },
  { label: '本月', value: [dayjs().startOf('month'), dayjs().endOf('month')] },
]);

const reconSearchForm = reactive({
  name: '',
  target: '',
  status: '',
  dateRange: null
});

const enterpriseTaskList = ref([]);
const enterpriseLoading = ref(false);
const enterprisePagination = reactive({ current: 1, pageSize: 10, total: 0 });
const enterpriseSelectedRowKeys = ref([]);
const onEnterpriseSelectChange = (keys) => {
  enterpriseSelectedRowKeys.value = keys;
};

const fetchEnterpriseTasks = async (page = 1, size = 10, silent = false) => {
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

    const res = await request.get('/icp/task', { params: queryParams });
    if (res.code === 200) {
      enterpriseTaskList.value = res.items || [];
      enterprisePagination.total = res.total || 0;
      enterprisePagination.current = page;
      enterprisePagination.pageSize = size;
      lastRefreshTime.value = new Date();
    }
  } catch (error) {
    console.error('获取企业测绘列表失败:', error);
  } finally {
    if (!silent) enterpriseLoading.value = false;
  }
};

const onReconSearch = () => {
  fetchEnterpriseTasks(1, enterprisePagination.pageSize);
  fetchEnterpriseMetricCounts();
};

const resetReconSearch = () => {
  reconSearchForm.name = '';
  reconSearchForm.target = '';
  reconSearchForm.status = '';
  reconSearchForm.dateRange = null;
  onReconSearch();
};

const handleEnterpriseTableChange = (page, pageSize) => fetchEnterpriseTasks(page, pageSize);

const TYC_QUERY_TYPE_LABELS = {
  invest: '对外投资',
  web: '网站备案',
  app: '移动APP',
  mapp: '微信小程序',
  wechat: '微信公众号',
  weibo: '企业微博',
  trademark: '企业商标'
};

const ICP_QUERY_TYPE_LABELS = {
  web: '网站备案',
  app: '移动APP',
  mapp: '微信小程序',
  kapp: '快应用'
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
  if (!queryType.length) return ['默认查询'];
  return queryType.map(k => map[k] || k);
};

const formatEnterpriseOptionsSummary = (record) => {
  if (!record) return '默认配置';
  const queryCount = Array.isArray(record.query_type) ? record.query_type.length : 0;

  if (record.task_type === 'tyc') {
    let activeCount = queryCount;
    if (record.depth !== undefined) activeCount++;
    if (record.invest_ratio !== undefined) activeCount++;
    if (record.enable_icp !== false) activeCount++;
    return `已配置 ${activeCount} 项策略`;
  }

  if (queryCount > 0) {
    return `${queryCount} 项查询维度`;
  }
  return '默认配置';
};

const enterpriseColumns = [
  { title: '任务名称', dataIndex: 'name', key: 'name', width: 220, ellipsis: true },
  { title: '查询目标', dataIndex: 'target', key: 'target', width: 200, ellipsis: true },
  { title: '类型', dataIndex: 'task_type', key: 'task_type', width: 100, customRender: ({ text }) => text === 'tyc' ? '天眼查' : '工信部ICP' },
  { title: '策略配置', key: 'policy_options', width: 140 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 120 },
  { title: '核心/投资', key: 'statistic', width: 140 },
  { title: '同步状态', key: 'sync_status', width: 150 },
  { title: '结束时间', dataIndex: 'end_time', key: 'end_time', width: 160 },
  { title: '操作', key: 'action', width: 170, fixed: 'right' }
];

const getEnterpriseStatusColor = (status) => {
  const map = {
    done: 'success',
    running: 'processing',
    waiting: 'default',
    stop: 'warning',
    error: 'error'
  };
  return map[status] || 'default';
};

const getEnterpriseStatusIcon = (status) => {
  if (status === 'done') return CheckCircleOutlined;
  if (status === 'error') return CloseCircleOutlined;
  if (status === 'stop') return StopOutlined;
  if (status === 'waiting') return ClockCircleOutlined;
  return SyncOutlined;
};

const formatEnterpriseStatusText = (status) => {
  const map = {
    done: '已完成',
    running: '进行中',
    waiting: '排队中',
    stop: '已停止',
    error: '异常失败'
  };
  return map[status] || status;
};

const tycModalVisible = ref(false);
const syncModalVisible = ref(false);
const currentSyncTask = ref(null);

const showTycModal = () => {
  tycModalVisible.value = true;
};

const handleEnterpriseCreateSuccess = () => {
  fetchEnterpriseTasks(1, enterprisePagination.pageSize);
  fetchEnterpriseMetricCounts();
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

const goToScope = (scopeId) => {
  if (scopeId) {
    router.push({ path: '/group', query: { scope_id: scopeId } });
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
      trademark_cnt: stats.trademark_cnt || 0,
      wechat_cnt: stats.wechat_cnt || 0,
      weibo_cnt: stats.weibo_cnt || 0,
    }
  });
};

const handleExportEnterprise = async (record) => {
  try {
    message.loading({ content: '正在导出...', key: 'export', duration: 0 });
    const res = await request.get(`/icp/export/${record._id}`, { responseType: 'blob' });
    const blob = new Blob([res.data || res]);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${record.name || 'icp_export'}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    message.success({ content: '导出成功', key: 'export', duration: 2 });
  } catch (error) {
    message.error({ content: '导出失败', key: 'export', duration: 2 });
  }
};

const handleBatchExportEnterprise = async () => {
  if (enterpriseSelectedRowKeys.value.length === 0) {
    message.warning('请先勾选需要导出的任务');
    return;
  }
  try {
    message.loading({ content: '正在批量导出...', key: 'batch_export', duration: 0 });
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
    message.success({ content: '批量导出成功', key: 'batch_export', duration: 2 });
  } catch (error) {
    message.error({ content: '批量导出失败', key: 'batch_export', duration: 2 });
  }
};

const handleBatchDeleteEnterprise = async () => {
  if (!enterpriseSelectedRowKeys.value.length) return;
  try {
    message.loading({ content: '正在批量删除...', key: 'batchDelete', duration: 0 });
    const res = await request.post('/icp/delete/', { task_ids: enterpriseSelectedRowKeys.value });
    if (res.code === 200) {
      message.success({ content: '批量删除成功', key: 'batchDelete', duration: 2 });
      enterpriseSelectedRowKeys.value = [];
      fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize);
      fetchEnterpriseMetricCounts();
    } else {
      message.error({ content: res.message || '批量删除失败', key: 'batchDelete', duration: 2 });
    }
  } catch (error) {
    message.error({ content: '批量删除失败', key: 'batchDelete', duration: 2 });
  }
};

const handleBatchRestartEnterprise = async () => {
  if (!enterpriseSelectedRowKeys.value.length) return;
  try {
    message.loading({ content: '正在批量重启...', key: 'batchRestart', duration: 0 });
    const res = await request.post('/icp/restart/', { task_ids: enterpriseSelectedRowKeys.value });
    if (res.code === 200) {
      message.success({ content: '成功下发批量重启', key: 'batchRestart', duration: 3 });
      enterpriseSelectedRowKeys.value = [];
      fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize);
      fetchEnterpriseMetricCounts();
    } else {
      message.error({ content: res.message || '批量重启失败', key: 'batchRestart', duration: 3 });
    }
  } catch (error) {
    message.error({ content: '批量重启失败', key: 'batchRestart', duration: 3 });
  }
};

const handleStopEnterprise = async (record) => {
  try {
    const res = await request.get(`/icp/stop/${record._id}`);
    if (res.code === 200) {
      message.success('已停止任务');
      fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize);
      fetchEnterpriseMetricCounts();
    } else {
      message.error(res.message || '停止失败');
    }
  } catch (error) {
    console.error('停止任务失败', error);
  }
};

const handleRestartEnterprise = async (record) => {
  try {
    const res = await request.get(`/icp/restart/${record._id}`);
    if (res.code === 200) {
      message.success('已重启任务');
      fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize);
      fetchEnterpriseMetricCounts();
    } else {
      message.error(res.message || '重启失败');
    }
  } catch (error) {
    console.error('重启任务失败', error);
  }
};

const handleDeleteEnterprise = async (record) => {
  Modal.confirm({
    title: '删除确认',
    icon: createVNode(ExclamationCircleOutlined),
    content: `确认要删除企业测绘任务「${record.name || record._id}」吗？`,
    okText: '确 定',
    cancelText: '取 消',
    okButtonProps: { danger: true },
    onOk: async () => {
      try {
        const res = await request.post('/icp/delete/', { task_ids: [record._id] });
        if (res.code === 200) {
          message.success('删除成功');
          fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize);
          fetchEnterpriseMetricCounts();
        } else {
          message.error(res.message || '删除失败');
        }
      } catch (error) {
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
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0, showSizeChanger: true });

watch(() => pagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});

watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
});

// 列配置
const columns = [
  { title: '任务名', dataIndex: 'name', key: 'name', width: 200, sorter: true, ellipsis: true },
  { title: '目标', dataIndex: 'target', key: 'target', width: 220, sorter: true, ellipsis: true },
  { title: '资产统计', dataIndex: 'statistic', key: 'statistic', width: 210 },
  { title: '策略配置', dataIndex: 'options', key: 'options', width: 140 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 150 },
  { title: '开始时间', dataIndex: 'start_time', key: 'start_time', width: 160 },
  { title: '结束时间', dataIndex: 'end_time', key: 'end_time', width: 160 },
  { title: 'Task_Id', dataIndex: '_id', key: 'task_id', width: 190 },
  { title: '操作', key: 'action', fixed: 'right', width: 160 },
];

const isStatusRunning = (status) => {
  return !['done', 'error', 'stop', 'waiting'].includes(status);
};

const getStatusTagColor = (status) => {
  if (status === 'done') return 'success';
  if (status === 'error') return 'error';
  if (status === 'stop') return 'warning';
  if (status === 'waiting') return 'default';
  return 'processing';
};

const getStatusIcon = (status) => {
  if (status === 'done') return CheckCircleOutlined;
  if (status === 'error') return CloseCircleOutlined;
  if (status === 'stop') return StopOutlined;
  if (status === 'waiting') return ClockCircleOutlined;
  return SyncOutlined;
};

const formatStatusText = (status) => {
  if (status === 'done') return '已完成';
  if (status === 'error') return '异常失败';
  if (status === 'stop') return '已停止';
  if (status === 'waiting') return '排队中';

  const pluginName = pluginNameMap[status] || status;
  return `${pluginName}`;
};

const formatOptionsSummary = (options) => {
  if (!options) return '默认配置';
  let activeCount = 0;
  for (const key in options) {
    if (options[key] === true) activeCount++;
  }
  return `已启用 ${activeCount} 项策略`;
};

const getDetailedOptions = (options) => {
  if (!options) return ['默认配置'];
  const detailed = [];

  for (const key in options) {
    if (options[key] === true) {
      const plugin = pluginList.find(item => item.key === key);
      if (plugin) detailed.push(plugin.label);
    }
  }

  if (options.domain_brute_type) {
    const typeMap = { test: '测试', big: '大字典' };
    detailed.push(`域名爆破字典: ${typeMap[options.domain_brute_type] || options.domain_brute_type}`);
  }
  if (options.port_scan_type && options.port_scan_type !== 'null' && options.port_scan_type !== null) {
    const typeMap = { test: '测试', top100: 'TOP100', top1000: 'TOP1000', all: '全端口' };
    detailed.push(`端口扫描策略: ${typeMap[options.port_scan_type] || options.port_scan_type.toUpperCase()}`);
  }
  if (options.alt_dns_dict) {
    detailed.push(`智能子域字典: ${options.alt_dns_dict}`);
  }
  if (options.file_leak_dict) {
    detailed.push(`文件泄露字典: ${options.file_leak_dict}`);
  }

  return detailed.length > 0 ? detailed : ['无额外选项'];
};

// 搜索表单与高级筛选折叠状态
const isAdvancedFilterOpen = ref(false);
const searchForm = reactive({
  name: '', target: '', task_id: '', type: undefined,
  status: '', site_count: '', site_operator: '=',
  domain_count: '', domain_operator: '=', wih_count: '', wih_operator: '='
});

const activeAdvancedFilterCount = computed(() => {
  let count = 0;
  if (searchForm.task_id) count++;
  if (searchForm.type) count++;
  if (searchForm.site_count !== '' && searchForm.site_count !== null && searchForm.site_count !== undefined) count++;
  if (searchForm.domain_count !== '' && searchForm.domain_count !== null && searchForm.domain_count !== undefined) count++;
  if (searchForm.wih_count !== '' && searchForm.wih_count !== null && searchForm.wih_count !== undefined) count++;
  return count;
});

const resetAdvancedFilters = () => {
  searchForm.task_id = '';
  searchForm.type = undefined;
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
const fetchTasks = async (page = 1, size = 10, silent = false) => {
  if (!silent) loading.value = true;
  try {
    const queryParams = { page, size };

    if (searchForm.name) queryParams.name = searchForm.name;
    if (searchForm.target) queryParams.target = searchForm.target;
    if (searchForm.status) queryParams.status = searchForm.status;
    if (searchForm.task_id) queryParams._id = searchForm.task_id;
    if (searchForm.type) queryParams.task_tag = searchForm.type;

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

    const res = await request.get('/task/', { params: queryParams });

    if (res.code === 200) {
      taskList.value = res.items || [];
      pagination.total = res.total || 0;
      pagination.current = page;
      pagination.pageSize = size;
      lastRefreshTime.value = new Date();
    }
  } catch (error) {
    console.error('获取资产侦查任务失败:', error);
  } finally {
    if (!silent) loading.value = false;
  }
};

const onSearch = () => {
  fetchTasks(1, pagination.pageSize);
  fetchTaskMetricCounts();
};

const resetSearch = () => {
  Object.assign(searchForm, {
    name: '', target: '', task_id: '', type: undefined,
    status: '', site_count: '', site_operator: '=',
    domain_count: '', domain_operator: '=', wih_count: '', wih_operator: '='
  });
  onSearch();
};

const handleTableChange = (page, pageSize) => fetchTasks(page, pageSize);

// ==========================================
// 💥 任务批量操作
// ==========================================
const handleBatchDelete = () => {
  if (!hasSelected.value) {
    message.warning('请先勾选需要删除的任务');
    return;
  }

  const validKeys = selectedRowKeys.value.filter(key => key != null);
  if (validKeys.length === 0) return;

  let isDeleteData = true;

  Modal.confirm({
    title: '批量删除任务确认',
    icon: createVNode(ExclamationCircleOutlined),
    content: createVNode('div', { style: 'margin-top: 8px;' }, [
      createVNode('div', { style: 'margin-bottom: 14px; color: var(--arl-text-color);' }, `确认要删除选中的 ${validKeys.length} 项任务吗？`),
      createVNode(Checkbox, {
        defaultChecked: isDeleteData,
        onChange: (e) => { isDeleteData = e.target.checked; }
      }, () => '同时级联删除该任务关联的所有资产数据 (不可恢复)')
    ]),
    okText: '确认删除',
    cancelText: '取 消',
    okButtonProps: { danger: true },
    onOk: async () => {
      try {
        const res = await request.post('/task/delete/', {
          del_task_data: isDeleteData,
          task_id: validKeys
        });

        if (res.code === 200) {
          message.success(`成功删除 ${validKeys.length} 项任务`);
          selectedRowKeys.value = [];
          fetchTasks(1, pagination.pageSize);
          fetchTaskMetricCounts();
        } else {
          message.error('删除失败: ' + (res.message || '未知错误'));
        }
      } catch (error) {
        message.error('网络异常，请稍后重试');
      }
    }
  });
};

const handleBatchStop = () => {
  if (!hasSelected.value) {
    message.warning('请先勾选需要停止的任务');
    return;
  }

  const validKeys = selectedRowKeys.value.filter(key => key != null);
  if (validKeys.length === 0) return;

  const selectedRecords = taskList.value.filter(item => validKeys.includes(item._id || item.task_id));
  const activeCount = selectedRecords.filter(item => !['done', 'stop', 'error'].includes(item.status)).length;
  const finishedCount = validKeys.length - activeCount;

  let modalContent = `确认要停止选中的 ${validKeys.length} 项任务吗？`;
  if (activeCount > 0 && finishedCount > 0) {
    modalContent = `选中的 ${validKeys.length} 项任务中包含 ${activeCount} 项正在运行，${finishedCount} 项已结束任务将自动跳过。确认执行停止操作吗？`;
  }

  Modal.confirm({
    title: '停止任务确认',
    icon: createVNode(ExclamationCircleOutlined),
    content: modalContent,
    okText: '确认停止',
    cancelText: '取 消',
    onOk: async () => {
      try {
        const res = await request.post('/task/batch_stop/', { task_id: validKeys });
        if (res.code === 200) {
          message.success('停止指令已下发');
          selectedRowKeys.value = [];
          fetchTasks(pagination.current, pagination.pageSize);
          fetchTaskMetricCounts();
        } else {
          message.error('停止失败: ' + (res.message || '未知错误'));
        }
      } catch (error) {
        message.error('网络异常，请稍后重试');
      }
    }
  });
};

const handleBatchExport = async ({ key }) => {
  if (!hasSelected.value) {
    message.warning('请先勾选需要导出的任务');
    return;
  }

  const validKeys = selectedRowKeys.value.filter(k => k != null);
  if (validKeys.length === 0) return;

  try {
    message.loading({ content: '正在生成导出文件...', key: 'exporting' });
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

    message.success({ content: '批量导出成功！', key: 'exporting', duration: 2 });
  } catch (error) {
    console.error('批量导出异常:', error);
    message.error({ content: '导出失败，请查看控制台', key: 'exporting', duration: 2 });
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
        message.success(`任务已重启，新任务 ID: ${newTaskId} 🚀`);
      } else {
        message.success('任务已重启，已生成新任务！🚀');
      }
      fetchTasks(pagination.current, pagination.pageSize);
      fetchTaskMetricCounts();
    } else {
      const errMsg = res.data?.error || res.message || '未知错误';
      message.error('重启失败: ' + errMsg);
    }
  } catch (error) {
    message.error('网络异常，重启失败');
  } finally {
    record.restarting = false;
  }
};

const stopSingleTask = async (record) => {
  try {
    const res = await request.get(`/task/stop/${record._id || record.task_id}`);
    if (res.code === 200) {
      message.success('已发送停止指令 🛑');
      fetchTasks(pagination.current, pagination.pageSize);
      fetchTaskMetricCounts();
    } else {
      message.error('停止失败: ' + (res.message || '未知错误'));
    }
  } catch (error) {
    message.error('网络异常，停止失败');
  }
};

const deleteSingleTask = (record) => {
  let isDeleteData = true;

  Modal.confirm({
    title: '删除任务确认',
    icon: createVNode(ExclamationCircleOutlined),
    content: createVNode('div', { style: 'margin-top: 8px;' }, [
      createVNode('div', { style: 'margin-bottom: 14px; color: var(--arl-text-color);' }, `确认要删除任务「${record.name || record._id}」吗？`),
      createVNode(Checkbox, {
        defaultChecked: isDeleteData,
        onChange: (e) => { isDeleteData = e.target.checked; }
      }, () => '同时级联删除该任务关联的所有资产数据 (不可恢复)')
    ]),
    okText: '确认删除',
    cancelText: '取 消',
    okButtonProps: { danger: true },
    onOk: async () => {
      try {
        const res = await request.post('/task/delete/', {
          task_id: [record._id || record.task_id],
          del_task_data: isDeleteData
        });

        if (res.code === 200) {
          message.success('任务删除成功');
          fetchTasks(pagination.current, pagination.pageSize);
          fetchTaskMetricCounts();
        } else {
          message.error('删除失败: ' + (res.message || '未知错误'));
        }
      } catch (error) {
        message.error('网络异常，删除失败');
      }
    }
  });
};

const exportTask = async (record) => {
  try {
    message.loading({ content: '正在生成 Excel 导出文件...', key: 'exporting_excel' });
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

    message.success({ content: 'Excel 导出成功！', key: 'exporting_excel', duration: 2 });
  } catch (error) {
    message.error({ content: '导出异常，请查看控制台', key: 'exporting_excel', duration: 2 });
  }
};

// 同步任务至资产组
const syncVisible = ref(false);
const syncLoading = ref(false);
const syncOptions = ref([]);
const currentSyncRecord = ref(null);
const syncFormState = reactive({ scope_id: undefined });

const syncTask = async (record) => {
  currentSyncRecord.value = record;
  syncFormState.scope_id = undefined;
  syncOptions.value = [];
  syncVisible.value = true;

  try {
    const res = await request.get('/task/sync_scope/', {
      params: { target: record.target }
    });

    if (res.code === 200) {
      syncOptions.value = (res.items || []).map(item => ({
        value: item._id,
        label: item.name
      }));
    }
  } catch (error) {
    console.error('获取资产选项失败:', error);
  }
};

const handleSyncOk = async () => {
  if (!syncFormState.scope_id) {
    message.warning('请选择目标资产组');
    return;
  }

  syncLoading.value = true;
  try {
    const res = await request.post('/task/sync/', {
      scope_id: syncFormState.scope_id,
      task_id: currentSyncRecord.value._id || currentSyncRecord.value.task_id
    });

    if (res.code === 200) {
      message.success('同步任务下发成功 🚀');
      syncVisible.value = false;
      fetchTasks(pagination.current, pagination.pageSize);
    } else {
      message.error('同步失败: ' + (res.message || '未知错误'));
    }
  } catch (error) {
    message.error('网络异常，请稍后再试');
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
    title: '🌐 基础资产侦查',
    plugins: [
      { key: 'dns_query_plugin', label: '域名查询插件' },
      { key: 'domain_brute', label: '域名爆破' },
      { key: 'alt_dns', label: 'DNS字典智能生成' },
      { key: 'arl_search', label: 'ARL 历史查询' }
    ]
  },
  {
    title: '⚡️ 端口与服务发现',
    plugins: [
      { key: 'skip_scan_cdn_ip', label: '跳过CDN' },
      { key: 'port_scan', label: '端口扫描' },
      { key: 'service_detection', label: '服务识别' },
      { key: 'os_detection', label: '操作系统识别' },
      { key: 'ssl_cert', label: 'SSL 证书获取' }
    ]
  },
  {
    title: '🕷️ Web 深度探测',
    plugins: [
      { key: 'site_identify', label: '站点与指纹识别' },
      { key: 'search_engines', label: '搜索引擎调用' },
      { key: 'site_spider', label: '站点爬虫' },
      { key: 'web_info_hunter', label: 'WIH 调用' },
      { key: 'file_leak', label: '文件泄露' },
      { key: 'findvhost', label: 'Host 碰撞' },
      { key: 'npoc_service_detection', label: '服务(python)识别' },
      { key: 'nuclei_scan', label: 'nuclei 扫描' }
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
  domain_brute_type: undefined,
  port_scan_type: undefined,
  alt_dns_dict: undefined,
  file_leak_dict: undefined,
  ...defaultPlugins
};

const formState = reactive({ ...defaultFormState });

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
    message.info('已载入「快速侦查」预设方案');
  } else if (type === 'normal') {
    Object.keys(defaultPlugins).forEach(k => { formState[k] = defaultPlugins[k]; });
    formState.site_identify = true;
    formState.file_leak = true;
    formState.service_detection = true;
    formState.ssl_cert = true;
    message.info('已载入「常规全面探测」预设方案');
  } else if (type === 'deep') {
    Object.keys(defaultPlugins).forEach(k => { formState[k] = true; });
    formState.skip_scan_cdn_ip = false;
    message.info('已载入「深度全量测绘」预设方案');
  }
};

const handleOk = async () => {
  try {
    await formRef.value.validate();
    submitLoading.value = true;
    const res = await request.post('/task/', formState);
    if (res.code === 200) {
      message.success('任务下发成功！');
      visible.value = false;
      fetchTasks(1, pagination.pageSize);
      fetchTaskMetricCounts();
    } else {
      message.error('下发失败: ' + (res.message || '未知错误'));
    }
  } catch (error) {
    if (!error.errorFields) message.error('网络异常');
  } finally {
    submitLoading.value = false;
  }
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
    message.warning('请先输入查询语句再进行测试');
    return;
  }

  fofaTestLoading.value = true;
  try {
    const res = await request.post('/task_fofa/test', { query: fofaForm.query });
    if (res.code === 200) {
      fofaResultCount.value = res.data?.size || res.data?.total || 0;
      fofaTested.value = true;
      message.success('测试连接成功');
    } else {
      fofaResultCount.value = 0;
      fofaTested.value = true;
      message.error(res.message || '测试失败');
    }
  } catch (error) {
    fofaResultCount.value = 0;
    fofaTested.value = true;
    message.error('测试请求异常，请检查配置');
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
      message.success('FOFA 任务下发成功！');
      fofaVisible.value = false;
      fetchTasks(1, pagination.pageSize);
      fetchTaskMetricCounts();
    } else {
      message.error(res.message || '任务下发失败');
    }
  } catch (error) {
    if (!error.errorFields) message.error('网络请求异常');
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
// 🚀 顶层 Tab 切换
// ==========================================
watch(() => route.query.tab, (newTab) => {
  // 核心加固：仅在当前路由处于任务管理页面时响应外部 query 联动，避免切至其他页面时将 activeMainTab 误重置为 enterprise
  if (!route.path.startsWith('/taskList')) return;
  if (newTab === 'task' && activeMainTab.value !== 'task') {
    activeMainTab.value = 'task';
  } else if (newTab === 'enterprise' && activeMainTab.value !== 'enterprise') {
    activeMainTab.value = 'enterprise';
  }
});

const handleMainTabChange = (key) => {
  activeMainTab.value = key;
  const nextQuery = { ...route.query };
  delete nextQuery.view;
  if (key === 'task') {
    nextQuery.tab = 'task';
  } else {
    delete nextQuery.tab;
  }
  router.replace({ query: nextQuery });
  if (key === 'enterprise') {
    fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize);
    fetchEnterpriseMetricCounts();
  } else {
    fetchTasks(pagination.current, pagination.pageSize);
    fetchTaskMetricCounts();
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

  if (activeMainTab.value === 'enterprise') {
    fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize);
    fetchEnterpriseMetricCounts();
  } else {
    fetchTasks(pagination.current, pagination.pageSize);
    fetchTaskMetricCounts();
  }

  startSmartPolling();

  try {
    const dictRes = await request.get('/dictionary/list');
    if (dictRes.code === 200 && dictRes.data) {
      domainDicts.value = dictRes.data.filter(item => item.category && item.category.includes('子域名爆破') && !item.category.includes('智能'));
      altDnsDicts.value = dictRes.data.filter(item => item.category && item.category.includes('智能子域爆破'));
      fileLeakDicts.value = dictRes.data.filter(item => item.category && (item.category.includes('目录文件泄露') || item.category.includes('目录与文件泄露')));
      portDicts.value = dictRes.data.filter(item => item.category && item.category.includes('端口扫描策略'));

      if (domainDicts.value.length > 0) formState.domain_brute_type = domainDicts.value[0].name;
      if (altDnsDicts.value.length > 0) formState.alt_dns_dict = altDnsDicts.value[0].name;
      if (fileLeakDicts.value.length > 0) formState.file_leak_dict = fileLeakDicts.value[0].name;
      if (portDicts.value.length > 0) formState.port_scan_type = portDicts.value[0].name;
    }
  } catch (error) {
    console.error('拉取字典列表失败:', error);
  }
});

onActivated(() => {
  if (activeMainTab.value === 'enterprise') {
    fetchEnterpriseTasks(enterprisePagination.current, enterprisePagination.pageSize, true);
    fetchEnterpriseMetricCounts();
  } else {
    fetchTasks(pagination.current, pagination.pageSize, true);
    fetchTaskMetricCounts();
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
   页面容器与吸顶英雄卡片体系
   ========================================================================== */
.arl-task-page {
  background-color: var(--arl-bg-layout);
  padding: 16px 20px;
  min-height: calc(100vh - 64px);
}

.arl-task-hero-card {
  position: sticky;
  top: 0;
  z-index: 20;
  background: var(--arl-bg-white);
  border: 1px solid var(--arl-border-color);
  border-radius: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  padding: 12px 18px;
  margin-bottom: 12px;
  transition: all 0.25s ease;
}

/* 顶层主栏：左侧胶囊 + 右侧控制 */
.task-hero-unified-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 12px;
  padding-bottom: 10px;
  border-bottom: 1px solid var(--arl-border-color);
}

.task-hero-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.task-hero-title .title-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--arl-text-color);
  letter-spacing: -0.2px;
}

/* 视角切换胶囊栏 */
.task-view-capsule-switcher {
  display: inline-flex;
  align-items: center;
  background: var(--arl-bg-light);
  padding: 3px;
  border-radius: 6px;
  border: 1px solid var(--arl-border-color);
}

.capsule-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border: none;
  background: transparent;
  color: var(--arl-text-secondary);
  font-size: 13px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  line-height: 1.5;
}

.capsule-btn:hover {
  color: var(--arl-text-color);
}

.capsule-btn.active {
  background: var(--arl-bg-white);
  color: var(--arl-theme-color);
  font-weight: 500;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.08);
}

.capsule-icon {
  font-size: 13px;
}

.capsule-count {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  padding: 1px 6px;
  background: rgba(24, 144, 255, 0.1);
  color: var(--arl-theme-color);
  border-radius: 10px;
  font-weight: 500;
}

.pulse-dot {
  width: 6px;
  height: 6px;
  background-color: #52c41a;
  border-radius: 50%;
  animation: pulseBeacon 1.6s infinite ease-in-out;
}

@keyframes pulseBeacon {
  0% { transform: scale(0.9); opacity: 0.7; }
  50% { transform: scale(1.3); opacity: 1; box-shadow: 0 0 6px #52c41a; }
  100% { transform: scale(0.9); opacity: 0.7; }
}

/* 英雄栏右侧控制区 */
.task-hero-right {
  display: flex;
  align-items: center;
  gap: 10px;
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
  box-shadow: 0 2px 4px rgba(24, 144, 255, 0.2);
}

/* ==========================================================================
   中层：任务运行态 4 维状态概览指标卡
   ========================================================================== */
.task-metric-cards-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
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
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.15);
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
  background: rgba(24, 144, 255, 0.1);
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
  border-top: 1px solid rgba(0, 0, 0, 0.04);
}

/* ==========================================================================
   浮动批量操作激活条
   ========================================================================== */
.floating-batch-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: rgba(24, 144, 255, 0.08);
  border: 1px solid rgba(24, 144, 255, 0.3);
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
  font-family: monospace, sans-serif;
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
  font-family: monospace;
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
.stat-capsule.domain { background: rgba(24, 144, 255, 0.12); color: #096dd9; }
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
  color: var(--arl-primary-light, #91caff);
  font-weight: 600;
  margin-top: 4px;
  margin-bottom: 2px;
  letter-spacing: 0.5px;
}

/* 状态标签 */
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
.service-elapsed { font-weight: 500; font-family: monospace; }

.task-id-text {
  font-family: monospace;
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

/* 分页条 */
.task-pagination-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 4px 4px 4px;
}

.pagination-info {
  font-size: 13px;
  color: var(--arl-text-secondary);
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
</style>