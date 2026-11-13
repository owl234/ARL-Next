<template>
  <div class="arl-page-container">
    
    <!-- 全局 Token 状态提示 -->
    <a-alert
      v-if="tokenStatus.status"
      :type="tokenStatus.status === 'valid' ? 'success' : 'error'"
      show-icon
      style="margin-bottom: 16px;"
    >
      <template #message>
        <span style="font-weight: 500;">
          {{ pageText('pages.githubTokenStatus') }}
          <span v-if="tokenStatus.status === 'valid'" style="color: #52c41a;">{{ tokenStatus.msg }}</span>
          <span v-else style="color: #f5222d;">{{ tokenStatus.msg }}</span>
        </span>
      </template>
      <template #description v-if="tokenStatus.status !== 'valid'">
        <div style="margin-top: 4px;">
          {{ pageText('pages.thisModuleUsesAGithubTokenForCodeLeak') }}
          <a @click="goToGithubTokenConfig" class="page-settings-link">{{ pageText('tasks.openSettings') }}</a>
        </div>
      </template>
    </a-alert>

    <a-tabs v-model:activeKey="mainTab" type="card" class="main-tabs" size="middle">
      
<!-- ================= MAIN TAB 2: 威胁情报雷达 (情报侧) ================= -->
<a-tab-pane key="ti" :tab="pageText('pages.threatIntelligence')">
  <a-card :bordered="false" style="border-radius: 8px;">
    


    <a-tabs v-model:activeKey="activeTabTi">
      <a-tab-pane key="cve_history" :tab="pageText('pages.cveMonitoring')">
        <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; background: var(--arl-bg-light); padding: 10px 14px; border-radius: 6px;">
          <div style="display: flex; align-items: center; gap: 12px; flex-wrap: wrap;">
            <div>
              <span class="page-inline-gap">{{ pageText('pages.scheduledMonitoring') }}</span>
              <a-switch size="small" v-model:checked="cveConfig.enabled" @change="saveCveConfig" />
            </div>
            <div v-if="cveConfig.enabled">
              <span class="page-inline-gap">{{ pageText('pages.fetchInterval') }}</span>
              <a-select size="small" v-model:value="cveConfig.interval" style="width: 120px" @change="saveCveConfig">
                <a-select-option :value="6">{{ pageText('pages.every6Hours') }}</a-select-option>
                <a-select-option :value="12">{{ pageText('pages.every12Hours') }}</a-select-option>
                <a-select-option :value="24">{{ pageText('pages.every24Hours') }}</a-select-option>
              </a-select>
            </div>
            <a-button size="small" type="primary" ghost @click="runCveOnce" :loading="cveRunLoading || cveConfig.is_running">{{ pageText('pages.scanOnceNow') }}</a-button>
            <a-tag v-if="cveConfig.is_running" color="processing">{{ pageText('pages.scanningInTheBackground') }}</a-tag>
          </div>
          <a-button size="small" type="dashed" @click="fetchCveData">
            <template #icon><sync-outlined /></template> {{ pageText('pages.refreshData') }}
          </a-button>
        </div>

        <!-- CVE搜索栏 -->
        <a-form :label-wrap="true" layout="inline" class="page-filter-form">
          <a-form-item :label="pageText('pages.cveId')">
            <a-input size="small" v-model:value="cveSearchForm.cve_name" :placeholder="pageText('pages.enterACveId')" class="page-width-180" allowClear @pressEnter="onCveSearch">
              <template #suffix><search-outlined @click="onCveSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </a-form-item>
          <a-form-item :label="pageText('pages.description')">
            <a-input size="small" v-model:value="cveSearchForm.desc" :placeholder="pageText('pages.enterADescription')" class="page-width-180" allowClear @pressEnter="onCveSearch">
              <template #suffix><search-outlined @click="onCveSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </a-form-item>
        </a-form>

        <div style="margin-bottom: 12px; display: flex; gap: 10px;">
          <a-button size="small" @click="resetCveSearch">{{ pageText('tasks.clear') }}</a-button>
          <a-popconfirm :title="pageText('pages.deleteTheSelectedRecords')" @confirm="handleCveBatchDelete">
            <a-button danger size="small" :disabled="!cveHasSelected">{{ pageText('tasks.deleteSelected') }}</a-button>
          </a-popconfirm>
        </div>
        <a-table :row-selection="{ selectedRowKeys: cveSelectedRowKeys, onChange: onCveSelectChange, preserveSelectedRowKeys: true }" :loading="cveLoading" :dataSource="pagedCveData" :columns="cveColumns" :pagination="false" size="small" rowKey="cve_name">
          <template #emptyText>
            <ArlEmpty :description="pageText('tasks.noData')" />
          </template>
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'cve_name'">
              <a :href="record.cve_url" target="_blank" style="color: #ff4d4f; font-weight: bold; font-size: 14px;">
                {{ record.cve_name }} <link-outlined />
              </a>
            </template>
            <template v-else-if="column.key === 'desc'">
              <a-typography-paragraph :ellipsis="{ rows: 2, expandable: true, symbol: pageText('pages.expand') }" class="page-flush-bottom">
                {{ record.desc }}
              </a-typography-paragraph>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-popconfirm :title="pageText('tasks.confirmDeletionLabel')" @confirm="handleCveDelete(record.cve_name)">
                <a-button size="small" type="primary" danger ghost>{{ pageText('tasks.delete') }}</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>
        <div class="arl-pagination-bar">
          <div class="pagination-info">{{ pageText('tasks.paginationSummary', { pages: Math.ceil(filteredCveData.length / cvePagination.pageSize) || 1, total: filteredCveData.length }) }}</div>
          <a-pagination size="small" :pageSizeOptions="$pageSizeOptions" v-model:current="cvePagination.current" v-model:pageSize="cvePagination.pageSize" :total="filteredCveData.length" show-size-changer @change="onCveTableChange" @showSizeChange="onCveTableChange" />
        </div>
      </a-tab-pane>

      <!-- 子 Tab 2: 武器库追踪 -->
      <a-tab-pane key="tools_target" :tab="pageText('pages.securityToolTracking')">
        <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;">
          <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
            <a-button size="small" type="primary" @click="openToolAdd">{{ pageText('pages.monitorATool') }}</a-button>
            <a-button size="small" type="primary" ghost @click="runToolsOnce" :loading="toolsRunLoading || toolsConfig.is_running">{{ pageText('pages.scanOnceNow') }}</a-button>
            <a-tag v-if="toolsConfig.is_running" color="processing">{{ pageText('pages.scanningInTheBackground') }}</a-tag>
            
            <div style="display: flex; align-items: center; gap: 8px; background: var(--arl-bg-light); padding: 4px 10px; border-radius: 4px; border: 1px solid var(--arl-border-color);">
              <span>{{ pageText('pages.monitoringEnabled') }}</span>
              <a-switch size="small" v-model:checked="toolsConfig.enabled" @change="saveToolsConfig" />
            </div>
            
            <div v-if="toolsConfig.enabled" style="display: flex; align-items: center; gap: 8px; background: var(--arl-bg-light); padding: 4px 10px; border-radius: 4px; border: 1px solid var(--arl-border-color);">
              <span>{{ pageText('pages.schedule') }}</span>
              <a-select size="small" v-model:value="toolsConfig.interval" style="width: 120px" @change="saveToolsConfig">
                <a-select-option :value="1">{{ pageText('pages.everyHour') }}</a-select-option>
                <a-select-option :value="2">{{ pageText('pages.every2Hours') }}</a-select-option>
                <a-select-option :value="6">{{ pageText('pages.every6Hours') }}</a-select-option>
                <a-select-option :value="12">{{ pageText('pages.every12Hours') }}</a-select-option>
                <a-select-option :value="24">{{ pageText('pages.onceADay') }}</a-select-option>
              </a-select>
            </div>
          </div>
          <a-button size="small" type="dashed" @click="fetchToolsData">
            <template #icon><sync-outlined /></template>
            {{ pageText('pages.refreshList') }}
          </a-button>
        </div>

        <!-- 武器库搜索栏 -->
        <a-form :label-wrap="true" layout="inline" class="page-filter-form">
          <a-form-item :label="pageText('pages.toolUrl')">
            <a-input size="small" v-model:value="toolsSearchForm.repo_url" :placeholder="pageText('pages.enterAToolUrl')" class="page-width-250" allowClear @pressEnter="onToolsSearch">
              <template #suffix><search-outlined @click="onToolsSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </a-form-item>
        </a-form>

        <div style="margin-bottom: 12px; display: flex; gap: 10px;">
          <a-button size="small" @click="resetToolsSearch">{{ pageText('tasks.clear') }}</a-button>
          <a-popconfirm :title="pageText('pages.deleteTheSelectedTools')" @confirm="handleToolsBatchDelete">
            <a-button danger size="small" :disabled="!toolsHasSelected">{{ pageText('tasks.deleteSelected') }}</a-button>
          </a-popconfirm>
        </div>

        <a-table :row-selection="{ selectedRowKeys: toolsSelectedRowKeys, onChange: onToolsSelectChange, preserveSelectedRowKeys: true }" :loading="toolsLoading" :dataSource="pagedToolsData" :columns="toolsColumns" :pagination="false" size="small" rowKey="repo_url">
          <template #emptyText>
            <ArlEmpty :description="pageText('tasks.noData')" />
          </template>
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'repo_url'">
              <a :href="record.repo_url.replace('api.github.com/repos', 'github.com')" target="_blank" style="color: var(--arl-theme-color); font-weight: 500;">
                {{ record.repo_url.split('/').pop() }} <link-outlined />
              </a>
              <div style="color: var(--arl-text-color); opacity: 0.45; font-size: 12px;">{{ record.repo_url }}</div>
            </template>
            <template v-else-if="column.key === 'last_tag'">
              <a-tag color="cyan" v-if="record.last_tag">{{ record.last_tag }}</a-tag>
              <span v-else class="page-placeholder">{{ pageText('pages.noVersionAvailable') }}</span>
            </template>
            <template v-else-if="column.key === 'action'">
              <a :href="record.repo_url.replace('api.github.com/repos', 'github.com')" target="_blank">
                <a-button size="small" type="primary" ghost class="page-inline-gap">{{ pageText('pages.view') }}</a-button>
              </a>
              <a-popconfirm :title="pageText('pages.stopMonitoringThisTool')" @confirm="handleToolDelete(record.repo_url)">
                <a-button size="small" type="primary" danger ghost>{{ pageText('tasks.delete') }}</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>
        <div class="arl-pagination-bar">
          <div class="pagination-info">{{ pageText('tasks.paginationSummary', { pages: Math.ceil(filteredToolsData.length / toolsPagination.pageSize) || 1, total: filteredToolsData.length }) }}</div>
          <a-pagination size="small" :pageSizeOptions="$pageSizeOptions" v-model:current="toolsPagination.current" v-model:pageSize="toolsPagination.pageSize" :total="filteredToolsData.length" show-size-changer @change="onToolsTableChange" @showSizeChange="onToolsTableChange" />
        </div>
      </a-tab-pane>

      <!-- 子 Tab 3: 黑客动态监测 -->
      <a-tab-pane key="hackers_target" :tab="pageText('pages.researcherActivity')">
        <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;">
          <div style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
            <a-button size="small" type="primary" @click="openHackerAdd">{{ pageText('pages.monitorAResearcher') }}</a-button>
            <a-button size="small" type="primary" ghost @click="runHackersOnce" :loading="hackersRunLoading || hackersConfig.is_running">{{ pageText('pages.scanOnceNow') }}</a-button>
            <a-tag v-if="hackersConfig.is_running" color="processing">{{ pageText('pages.scanningInTheBackground') }}</a-tag>
            
            <div style="display: flex; align-items: center; gap: 8px; background: var(--arl-bg-light); padding: 4px 10px; border-radius: 4px; border: 1px solid var(--arl-border-color);">
              <span>{{ pageText('pages.monitoringEnabled') }}</span>
              <a-switch size="small" v-model:checked="hackersConfig.enabled" @change="saveHackersConfig" />
            </div>
            
            <div v-if="hackersConfig.enabled" style="display: flex; align-items: center; gap: 8px; background: var(--arl-bg-light); padding: 4px 10px; border-radius: 4px; border: 1px solid var(--arl-border-color);">
              <span>{{ pageText('pages.schedule') }}</span>
              <a-select size="small" v-model:value="hackersConfig.interval" style="width: 120px" @change="saveHackersConfig">
                <a-select-option :value="1">{{ pageText('pages.everyHour') }}</a-select-option>
                <a-select-option :value="2">{{ pageText('pages.every2Hours') }}</a-select-option>
                <a-select-option :value="6">{{ pageText('pages.every6Hours') }}</a-select-option>
                <a-select-option :value="12">{{ pageText('pages.every12Hours') }}</a-select-option>
                <a-select-option :value="24">{{ pageText('pages.onceADay') }}</a-select-option>
              </a-select>
            </div>
          </div>
          <div style="display: flex; gap: 10px;">
            <a-button size="small" style="border-color: #fadb14; color: #faad14;" @click="openHackersHistoryDrawer">
              <template #icon>👀</template> {{ pageText('pages.viewAllDiscoveredTools') }}
            </a-button>
            <a-button size="small" type="dashed" @click="fetchHackersData">
              <template #icon><sync-outlined /></template>
              {{ pageText('pages.refreshList') }}
            </a-button>
          </div>
        </div>

        <!-- 黑客搜索栏 -->
        <a-form :label-wrap="true" layout="inline" class="page-filter-form">
          <a-form-item label="Github ID：">
            <a-input size="small" v-model:value="hackersSearchForm.github_id" :placeholder="pageText('pages.enterAGithubId')" class="page-width-180" allowClear @pressEnter="onHackersSearch">
              <template #suffix><search-outlined @click="onHackersSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </a-form-item>
        </a-form>

        <div style="margin-bottom: 12px; display: flex; gap: 10px;">
          <a-button size="small" @click="resetHackersSearch">{{ pageText('tasks.clear') }}</a-button>
          <a-popconfirm :title="pageText('pages.deleteTheSelectedResearchers')" @confirm="handleHackersBatchDelete">
            <a-button danger size="small" :disabled="!hackersHasSelected">{{ pageText('tasks.deleteSelected') }}</a-button>
          </a-popconfirm>
        </div>

        <a-table :row-selection="{ selectedRowKeys: hackersSelectedRowKeys, onChange: onHackersSelectChange, preserveSelectedRowKeys: true }" :loading="hackersLoading" :dataSource="pagedHackersData" :columns="hackersColumns" :pagination="false" size="small" rowKey="github_id">
          <template #emptyText>
            <ArlEmpty :description="pageText('pages.noResearchersMonitored')">
              <a-button type="link" size="small" @click="hackerForm.github_id = 'knownsec'; submitHackerModal()">{{ pageText('pages.addKnownsec') }}</a-button>
            </ArlEmpty>
          </template>
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'github_id'">
              <div style="display: flex; align-items: center; gap: 10px;">
                <a-avatar :src="`https://github.com/${(record.github_id || '').trim()}.png`" size="default" />
                <a :href="`https://github.com/${(record.github_id || '').trim()}`" target="_blank" style="font-weight: 500; font-size: 14px;">
                  {{ record.github_id }} <link-outlined />
                </a>
              </div>
            </template>
            <template v-if="column.key === 'found_count'">
              <a-badge :count="record.found_count" :number-style="{ backgroundColor: '#52c41a' }" show-zero />
            </template>
            <template v-if="column.key === 'action'">
              <a :href="`https://github.com/${record.github_id}`" target="_blank">
                <a-button size="small" type="primary" ghost class="page-inline-gap">{{ pageText('pages.profile') }}</a-button>
              </a>
              <a-popconfirm :title="pageText('pages.stopMonitoring')" @confirm="handleHackerDelete(record.github_id)">
                <a-button size="small" type="primary" danger ghost>{{ pageText('tasks.delete') }}</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>
        <div class="arl-pagination-bar">
          <div class="pagination-info">{{ pageText('tasks.paginationSummary', { pages: Math.ceil(filteredHackersData.length / hackersPagination.pageSize) || 1, total: filteredHackersData.length }) }}</div>
          <a-pagination size="small" :pageSizeOptions="$pageSizeOptions" v-model:current="hackersPagination.current" v-model:pageSize="hackersPagination.pageSize" :total="filteredHackersData.length" show-size-changer @change="onHackersTableChange" @showSizeChange="onHackersTableChange" />
        </div>
      </a-tab-pane>
    </a-tabs>
  </a-card>
</a-tab-pane>

      <!-- ================= MAIN TAB 1: 代码泄露监控 (防守侧) ================= -->
      <a-tab-pane key="dlp" :tab="pageText('pages.codeLeakMonitoring')">
        <a-card :bordered="false" style="border-radius: 8px;">
          <a-tabs v-model:activeKey="activeTabDlp">
            <!-- 子 Tab 1: 周期策略管理 -->
            <a-tab-pane key="scheduler" :tab="pageText('pages.recurringMonitoringPolicies')">
        <div class="github-sticky-toolbar">
        <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
          <a-button size="small" type="primary" @click="openSchedulerAdd">{{ pageText('pages.addPolicy') }}</a-button>
          <a-button size="small" type="dashed" @click="fetchSchedulerData">
            <template #icon><sync-outlined /></template>
            {{ pageText('pages.refreshList') }}
          </a-button>
        </div>

        <!-- 策略搜索栏 -->
        <a-form :label-wrap="true" layout="inline" class="page-filter-form">
          <a-form-item :label="pageText('pages.policyName')">
            <a-input size="small" v-model:value="schedulerSearchForm.name" :placeholder="pageText('pages.enterAPolicyName')" class="page-width-180" allowClear @pressEnter="onSchedulerSearch">
              <template #suffix><search-outlined @click="onSchedulerSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </a-form-item>
          <a-form-item :label="pageText('pages.keyword')">
            <a-input size="small" v-model:value="schedulerSearchForm.keyword" :placeholder="pageText('pages.enterAKeyword')" class="page-width-180" allowClear @pressEnter="onSchedulerSearch">
              <template #suffix><search-outlined @click="onSchedulerSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </a-form-item>
          <a-form-item :label="pageText('tasks.statusLabel')">
            <a-select size="small" v-model:value="schedulerSearchForm.status" :placeholder="pageText('pages.selectAStatus')" class="page-width-180" allowClear @change="onSchedulerSearch">
              <a-select-option value="running">{{ TASK_STATUS_LABEL.running }}</a-select-option>
              <a-select-option value="stop">{{ TASK_STATUS_LABEL.stop }}</a-select-option>
              <a-select-option value="error">{{ TASK_STATUS_LABEL.error }}</a-select-option>
            </a-select>
          </a-form-item>
        </a-form>

        <!-- 批量操作 -->
        <div style="margin-bottom: 4px; display: flex; gap: 8px;">
          <a-button size="small" @click="resetSchedulerSearch">{{ pageText('tasks.clear') }}</a-button>
          <a-popconfirm :title="pageText('pages.deleteTheSelectedPolicies')" @confirm="handleSchedulerBatchDelete">
            <a-button danger size="small" :disabled="!schedulerHasSelected">{{ pageText('tasks.deleteSelected') }}</a-button>
          </a-popconfirm>
          <a-popconfirm :title="pageText('pages.stopTheSelectedPolicies')" @confirm="handleSchedulerBatchStop">
            <a-button size="small" :disabled="!schedulerHasSelected">{{ pageText('tasks.stopSelected') }}</a-button>
          </a-popconfirm>
        </div>

        </div>
        <!-- 策略表格 -->
<a-table
            :row-selection="{ selectedRowKeys: schedulerSelectedRowKeys, onChange: onSchedulerSelectChange, preserveSelectedRowKeys: true }"
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
              <a style="color: var(--arl-theme-color); font-weight: 500;" @click="openResultDrawer(record, 'scheduler')">{{ record.name }}</a>
            </template>

            <template v-else-if="column.key === 'status'">
              <a-tag :color="record.status === 'running' ? 'blue' : record.status === 'stop' ? 'warning' : 'error'">
                {{ TASK_STATUS_LABEL[record.status] || record.status }}
              </a-tag>
            </template>

            <template v-else-if="column.key === 'action'">
              <a-button
                  size="small"
                  type="link"
                  style="padding: 0 4px; margin-right: 8px;"
                  @click="openResultDrawer(record, 'scheduler')"
              >{{ pageText('pages.view') }}</a-button>

              <a-button
                  size="small"
                  style="margin-right: 8px;"
                  :disabled="record.status !== 'running'"
                  @click="handleSchedulerSingleAction('stop', record._id)"
              >{{ pageText('tasks.stop') }}</a-button>
              
              <a-button
                  size="small"
                  style="margin-right: 8px;"
                  :disabled="record.status !== 'stop' && record.status !== 'error'"
                  @click="handleSchedulerSingleAction('recover', record._id)"
              >{{ pageText('tasks.resume') }}</a-button>

              <a-button size="small" class="page-inline-gap" @click="openSchedulerEdit(record)">{{ pageText('pages.edit') }}</a-button>

              <a-popconfirm :title="pageText('pages.deleteThisPolicy')" @confirm="handleSchedulerSingleAction('delete', record._id)">
                <a-button size="small">{{ pageText('tasks.delete') }}</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>

        <!-- 策略分页 -->
        <div class="arl-pagination-bar">
          <div class="pagination-info">{{ pageText('tasks.paginationSummary', { pages: Math.ceil(schedulerPagination.total / schedulerPagination.pageSize) || 1, total: schedulerPagination.total }) }}</div>
          <a-pagination size="small" :pageSizeOptions="$pageSizeOptions" v-model:current="schedulerPagination.current" v-model:pageSize="schedulerPagination.pageSize" :total="schedulerPagination.total" show-size-changer @change="handleSchedulerTableChange" @showSizeChange="handleSchedulerTableChange" />
        </div>
      </a-tab-pane>

      <!-- 子 Tab 2: 单次扫描任务 -->
      <a-tab-pane key="task" :tab="pageText('pages.oneTimeScanningTasks')">
        <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center;">
          <a-button size="small" type="primary" @click="openTaskAdd">{{ pageText('pages.newOneTimeTask') }}</a-button>
          <a-button size="small" type="dashed" @click="fetchTaskData">
            <template #icon><sync-outlined /></template>
            {{ pageText('pages.refreshList') }}
          </a-button>
        </div>

        <!-- 任务搜索栏 -->
        <a-form :label-wrap="true" layout="inline" class="page-filter-form">
          <a-form-item :label="pageText('tasks.taskNameLabel')">
            <a-input size="small" v-model:value="taskSearchForm.name" :placeholder="pageText('tasks.enterATaskName')" class="page-width-180" allowClear @pressEnter="onTaskSearch">
              <template #suffix><search-outlined @click="onTaskSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </a-form-item>
          <a-form-item :label="pageText('pages.keyword')">
            <a-input size="small" v-model:value="taskSearchForm.keyword" :placeholder="pageText('pages.enterAKeyword')" class="page-width-180" allowClear @pressEnter="onTaskSearch">
              <template #suffix><search-outlined @click="onTaskSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </a-form-item>
          <a-form-item :label="pageText('tasks.statusLabel')">
            <a-select size="small" v-model:value="taskSearchForm.status" :placeholder="pageText('pages.selectAStatus')" class="page-width-180" allowClear @change="onTaskSearch">
              <a-select-option value="waiting">{{ TASK_STATUS_LABEL.waiting }}</a-select-option>
              <a-select-option value="running">{{ TASK_STATUS_LABEL.running }}</a-select-option>
              <a-select-option value="done">{{ TASK_STATUS_LABEL.done }}</a-select-option>
              <a-select-option value="error">{{ TASK_STATUS_LABEL.error }}</a-select-option>
              <a-select-option value="stop">{{ TASK_STATUS_LABEL.stop }}</a-select-option>
            </a-select>
          </a-form-item>
        </a-form>

        <!-- 批量操作 -->
        <div style="margin-bottom: 12px; display: flex; gap: 8px;">
          <a-button size="small" @click="resetTaskSearch">{{ pageText('tasks.clear') }}</a-button>
          <a-popconfirm :title="pageText('pages.deleteTheSelectedTasks')" @confirm="handleTaskBatchDelete">
            <a-button danger size="small" :disabled="!taskHasSelected">{{ pageText('tasks.deleteSelected') }}</a-button>
          </a-popconfirm>
          <a-popconfirm :title="pageText('pages.stopTheSelectedTasks')" @confirm="handleTaskBatchStop">
            <a-button size="small" :disabled="!taskHasSelected">{{ pageText('tasks.stopSelected') }}</a-button>
          </a-popconfirm>
        </div>

        <!-- 任务表格 -->
        <a-table
            :row-selection="{ selectedRowKeys: taskSelectedRowKeys, onChange: onTaskSelectChange, preserveSelectedRowKeys: true }"
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
              <a style="color: var(--arl-theme-color); font-weight: 500;" @click="openResultDrawer(record, 'task')">{{ record.name }}</a>
            </template>

            <template v-else-if="column.key === 'status'">
              <a-tag
                  :color="
                  record.status === 'running' || record.status === 'waiting' ? 'blue' :
                  record.status === 'error' ? 'error' :
                  'success'
                "
              >
                {{ TASK_STATUS_LABEL[record.status] || record.status }}
              </a-tag>
            </template>

            <template v-else-if="column.key === 'action'">
              <a-button
                  size="small"
                  type="link"
                  style="padding: 0 4px; margin-right: 8px;"
                  @click="openResultDrawer(record, 'task')"
              >{{ pageText('pages.view') }}</a-button>

              <a-button
                  size="small"
                  style="margin-right: 8px;"
                  type="primary" ghost
                  @click="handleTaskRestart(record)"
              >{{ pageText('tasks.restart') }}</a-button>

              <a-button
                  size="small"
                  style="margin-right: 8px;"
                  :disabled="record.status === 'done' || record.status === 'stop' || record.status === 'error'"
                  @click="handleTaskSingleAction('stop', record._id)"
              >{{ pageText('tasks.stop') }}</a-button>

              <a-popconfirm :title="pageText('pages.deleteThisTask')" @confirm="handleTaskSingleAction('delete', record._id)">
                <a-button size="small">{{ pageText('tasks.delete') }}</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>

        <!-- 任务分页 -->
        <div class="arl-pagination-bar">
          <div class="pagination-info">{{ pageText('tasks.paginationSummary', { pages: Math.ceil(taskPagination.total / taskPagination.pageSize) || 1, total: taskPagination.total }) }}</div>
          <a-pagination size="small" :pageSizeOptions="$pageSizeOptions" v-model:current="taskPagination.current" v-model:pageSize="taskPagination.pageSize" :total="taskPagination.total" show-size-changer @change="handleTaskTableChange" @showSizeChange="handleTaskTableChange" />
        </div>
      </a-tab-pane>
    </a-tabs>
  </a-card>
</a-tab-pane>



    </a-tabs>

    <!-- ================= 黑客发现记录抽屉 ================= -->
    <a-drawer
      :title="pageText('pages.toolsDiscoveredFromTrackedResearchers')"
      placement="right"
      :width="600"
      :open="historyDrawerVisible"
      @close="closeHackersHistoryDrawer"
    >
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
            <a :href="`https://github.com/${record.full_name}`" target="_blank" style="font-weight: 500; color: var(--arl-theme-color);">
              {{ record.full_name }} <link-outlined />
            </a>
          </template>
          <template v-else-if="column.key === 'insert_time'">
            <span style="color: var(--arl-text-color);"><clock-circle-outlined /> {{ record.insert_time }}</span>
          </template>
        </template>
      </a-table>
    </a-drawer>

    <!-- ================= GitHub 任务与监控结果详情抽屉 ================= -->
    <a-drawer
      :title="resultDrawerTitle"
      placement="right"
      :width="920"
      :open="resultDrawerVisible"
      @close="closeResultDrawer"
    >
      <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; background: var(--arl-bg-light); padding: 12px 16px; border-radius: 6px;">
        <div style="display: flex; align-items: center; gap: 12px;">
          <a-tag :color="resultDrawerType === 'task' ? 'blue' : 'purple'">
            {{ resultDrawerType === 'task' ? pageText('pages.oneTimeScanningTasks') : pageText('pages.recurringMonitoringPolicy') }}
          </a-tag>
          <span style="font-weight: 600; font-size: 14px;">{{ resultCurrentRecord?.name }}</span>
          <span class="page-summary-caption">{{ pageText('pages.keyword') }}{{ resultCurrentRecord?.keyword }}</span>
        </div>
        <a-button type="dashed" size="small" @click="fetchResultData" :loading="resultLoading">
          <template #icon><sync-outlined /></template> {{ pageText('tasks.refresh') }}
        </a-button>
      </div>

      <a-tabs v-model:activeKey="resultActiveTab" type="card">
        <!-- Tab 1: 命中结果 -->
        <a-tab-pane key="result" :tab="pageText('pages.codeLeakFindings')">
          <!-- 搜索过滤栏 -->
          <div style="display: flex; flex-wrap: wrap; gap: 10px; margin-bottom: 12px; align-items: center;">
            <a-input size="small" v-model:value="resultSearchForm.repo_full_name" :placeholder="pageText('pages.repositoryEGUserRepo')" class="page-width-180" allowClear @pressEnter="onResultSearch">
              <template #suffix><search-outlined @click="onResultSearch" style="cursor: pointer; opacity: 0.4;" /></template>
            </a-input>
            <a-input size="small" v-model:value="resultSearchForm.path" :placeholder="pageText('pages.filePathEGConfigPy')" class="page-width-180" allowClear @pressEnter="onResultSearch">
              <template #suffix><search-outlined @click="onResultSearch" style="cursor: pointer; opacity: 0.4;" /></template>
            </a-input>
            <a-input size="small" v-model:value="resultSearchForm.human_content" :placeholder="pageText('pages.keywordInCode')" class="page-width-180" allowClear @pressEnter="onResultSearch">
              <template #suffix><search-outlined @click="onResultSearch" style="cursor: pointer; opacity: 0.4;" /></template>
            </a-input>
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
            <template #bodyCell="{ column, record, text }">
              <template v-if="column.key === 'repo_full_name'">
                <a :href="`https://github.com/${record.repo_full_name}`" target="_blank" style="word-break: break-all; font-weight: 500;">
                  {{ record.repo_full_name }} <link-outlined style="font-size: 11px;" />
                </a>
              </template>
              <template v-else-if="column.key === 'path'">
                <a :href="record.html_url || `https://github.com/${record.repo_full_name}/blob/master/${record.path}`" target="_blank" style="word-break: break-all;">
                  {{ record.path }}
                </a>
              </template>
              <template v-else-if="column.key === 'human_content'">
                <div style="white-space: pre-wrap; word-break: break-word; font-family: var(--arl-font-mono); max-height: 240px; overflow-y: auto; background: var(--arl-bg-light); padding: 10px; border-radius: 6px; border: 1px solid var(--arl-border-color); font-size: 12px; line-height: 1.5; color: var(--arl-text-color);">
                  {{ record.human_content }}
                </div>
              </template>
              <template v-else-if="column.key === 'keyword'">
                <a-tag color="blue">{{ record.keyword }}</a-tag>
              </template>
              <template v-else-if="column.key === 'commit_date'">
                <span style="font-size: 12px; color: var(--arl-text-color); opacity: 0.85;">{{ record.commit_date || record.insert_time || '-' }}</span>
              </template>
            </template>
          </a-table>

          <div class="arl-pagination-bar">
            <div class="pagination-info">{{ pageText('tasks.paginationSummary', { pages: Math.ceil(resultPagination.total / resultPagination.pageSize) || 1, total: resultPagination.total }) }}</div>
            <a-pagination size="small" :pageSizeOptions="$pageSizeOptions" v-model:current="resultPagination.current" v-model:pageSize="resultPagination.pageSize" :total="resultPagination.total" show-size-changer @change="handleResultTableChange" @showSizeChange="handleResultTableChange" />
          </div>
        </a-tab-pane>

        <!-- Tab 2: 任务日志 (仅单次任务支持 syslog) -->
        <a-tab-pane v-if="resultDrawerType === 'task'" key="log" :tab="pageText('pages.taskLogs')">
          <div style="border: 1px solid var(--arl-border-color); border-radius: 4px; padding: 8px; background-color: var(--arl-bg-light);">
            <div ref="resultTerminalContainer" style="background-color: var(--arl-terminal-bg); color: var(--arl-terminal-text); border: 1px solid var(--arl-terminal-border); font-family: var(--arl-font-mono); padding: 14px; border-radius: 6px; height: 500px; overflow-y: auto; font-size: 12px; line-height: 1.6;">
              <div v-for="(log, idx) in resultLogDataSource" :key="log._id || idx" style="margin-bottom: 4px; word-break: break-all; border-bottom: 1px dashed rgba(255,255,255,0.08); padding-bottom: 2px;">
                <span style="margin-right: 8px; opacity: 0.7;">[{{ log.create_time }}]</span>
                <span :style="{ color: log.level === 'error' ? '#ff4d4f' : log.level === 'warning' ? '#faad14' : '#52c41a', fontWeight: 'bold', marginRight: '8px' }">[{{ (log.level || 'info').toUpperCase() }}]</span>
                <span style="margin-right: 8px;" v-if="log.title">[{{ log.title }}]</span>
                <span style="color: var(--arl-terminal-text);">{{ log.message }}</span>
              </div>
              <div v-if="resultLogDataSource.length === 0 && !resultLogLoading" class="page-log-empty">{{ pageText('pages.systemNoLogsYet') }}</div>
              <div v-if="resultLogLoading" class="page-log-empty">{{ pageText('tasks.systemLoadingLogs') }}</div>
            </div>
          </div>
        </a-tab-pane>
      </a-tabs>
    </a-drawer>

    <!-- ================= 策略弹窗 (新增/修改) ================= -->
    <a-modal
        v-model:open="schedulerModalVisible"
        :title="schedulerIsEdit ? pageText('pages.editPolicy') : pageText('pages.addPolicy')"
        @ok="submitSchedulerModal"
        :confirmLoading="schedulerSubmitLoading"
        width="520px"
        :okText="pageText('pages.confirm')"
        :cancelText="pageText('tasks.cancel')"
        destroyOnClose
    >
      <a-form :label-wrap="true" :model="schedulerForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" class="page-modal-form">
        <a-form-item :label="pageText('tasks.policyName')" required>
          <a-input v-model:value="schedulerForm.name" :placeholder="pageText('pages.enterAPolicyNameLabel2')" />
        </a-form-item>

        <a-form-item :label="pageText('pages.keywordLabel2')" required>
          <a-input v-model:value="schedulerForm.keyword" :placeholder="pageText('pages.enterAKeyword')" />
        </a-form-item>

        <a-form-item :label="pageText('pages.cronExpression')" required>
          <a-input v-model:value="schedulerForm.cron" :placeholder="pageText('pages.enterACronExpressionEG30')" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- ================= 任务弹窗 (新增) ================= -->
    <a-modal
        v-model:open="taskModalVisible"
        :title="pageText('pages.newOneTimeScan')"
        @ok="submitTaskModal"
        :confirmLoading="taskSubmitLoading"
        width="520px"
        :okText="pageText('pages.confirm')"
        :cancelText="pageText('tasks.cancel')"
        destroyOnClose
    >
      <a-form :label-wrap="true" :model="taskForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" class="page-modal-form">
        <a-form-item :label="pageText('assets.taskName')" required>
          <a-input v-model:value="taskForm.name" :placeholder="pageText('tasks.enterATaskName')" />
        </a-form-item>

        <a-form-item :label="pageText('pages.keywordLabel2')" required>
          <a-input v-model:value="taskForm.keyword" :placeholder="pageText('pages.enterAKeyword')" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- ================= 工具新增弹窗 ================= -->
    <a-modal
        v-model:open="toolModalVisible"
        :title="pageText('pages.monitorATool')"
        @ok="submitToolModal"
        width="520px"
        :okText="pageText('pages.confirm')"
        :cancelText="pageText('tasks.cancel')"
        destroyOnClose
    >
      <a-form :label-wrap="true" :model="toolForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" class="page-modal-form">
        <a-form-item :label="pageText('pages.repositoryUrl')" required>
          <a-input v-model:value="toolForm.repo_url" :placeholder="pageText('pages.eGHttpsGithubComChaitinXray')" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- ================= 大佬新增弹窗 ================= -->
    <a-modal
        v-model:open="hackerModalVisible"
        :title="pageText('pages.monitorAResearcher')"
        @ok="submitHackerModal"
        width="520px"
        :okText="pageText('pages.confirm')"
        :cancelText="pageText('tasks.cancel')"
        destroyOnClose
    >
      <a-form :label-wrap="true" :model="hackerForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" class="page-modal-form">
        <a-form-item label="Github ID" required>
          <a-input v-model:value="hackerForm.github_id" :placeholder="pageText('pages.eGKnownsec')" />
        </a-form-item>
      </a-form>
    </a-modal>

  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';
defineOptions({ name: 'GithubManage' });
import { ref, reactive, onMounted, onDeactivated, onUnmounted, computed, watch, nextTick } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import request from '../utils/request';
import { message, Modal } from 'ant-design-vue';
import { SearchOutlined, SyncOutlined, LinkOutlined, ClockCircleOutlined } from '@ant-design/icons-vue';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import { TASK_STATUS_LABEL } from '../constants/taskStatus';

const { t: pageText } = useI18n({ useScope: 'global' });

const router = useRouter();

// 深链到系统设置的 GitHub Token 字段并高亮，避免用户自己在设置页翻找
const goToGithubTokenConfig = () => {
  router.push({ path: '/systemSettings', query: { tab: 'api_config', focus: 'github_token' } });
};
const route = useRoute();
const globalPageSize = useGlobalPageSize(10);
const mainTab = ref('ti');
const activeTabDlp = ref('scheduler');
const activeTabTi = ref('cve_history');

// 💡 优先识别 URL 中传过来的参数（例如 dashboard 跳转过来默认指向对应 Tab）
onMounted(() => {
  if (route.query.tab && ['task', 'scheduler'].includes(route.query.tab)) {
    mainTab.value = 'dlp';
    activeTabDlp.value = route.query.tab;
  } else if (route.query.tab && ['cve_history', 'tools_target', 'hackers_target'].includes(route.query.tab)) {
    mainTab.value = 'ti';
    activeTabTi.value = route.query.tab;
  }
  fetchSchedulerData();
  fetchTaskData();
  fetchToolsData();
  fetchHackersData();
  fetchCveData();
  fetchCveConfig();
  fetchToolsConfig();
  fetchHackersConfig();
  fetchTokenStatus();
});

// 监听内部 Tab 切换拉取数据
watch(activeTabDlp, (newTab) => {
  if (newTab === 'scheduler') fetchSchedulerData();
  else if (newTab === 'task') fetchTaskData();
});

watch(activeTabTi, (newTab) => {
  if (newTab === 'cve_history') fetchCveData();
  else if (newTab === 'tools_target') fetchToolsData();
  else if (newTab === 'hackers_target') fetchHackersData();
});

// ==========================================
// ⚙️ 模块 A: 监控策略管理 (github_scheduler)
// ==========================================
const schedulerLoading = ref(false);
const schedulerData = ref([]);
const schedulerSearchForm = reactive({ name: '', keyword: '', status: undefined });
const schedulerPagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });


const schedulerSelectedRowKeys = ref([]);
const schedulerHasSelected = computed(() => schedulerSelectedRowKeys.value.length > 0);
const onSchedulerSelectChange = (keys) => { schedulerSelectedRowKeys.value = keys; };

const schedulerColumns = [
  { get title() { return pageText('tasks.policyName'); }, dataIndex: 'name', key: 'name', width: 150 },
  { get title() { return pageText('pages.keywordLabel2'); }, dataIndex: 'keyword', key: 'keyword', width: 150 },
  { get title() { return pageText('pages.cronExpression'); }, dataIndex: 'cron', key: 'cron', width: 150 },
  { get title() { return pageText('tasks.status'); }, dataIndex: 'status', key: 'status', width: 100 },
  { get title() { return pageText('tasks.runCount'); }, dataIndex: 'run_number', key: 'run_number', width: 100 },
  { get title() { return pageText('tasks.lastRun'); }, dataIndex: 'last_run_date', key: 'last_run_date', width: 180 },
  { get title() { return pageText('tasks.nextRun'); }, dataIndex: 'next_run_date', key: 'next_run_date', width: 180 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 280 }
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
  } catch (error) {
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

const goToSchedulerDetail = (record) => {
  openResultDrawer(record, 'scheduler');
};

const performSchedulerAction = async (actionType, idArray) => {
  try {
    const url = `/github_scheduler/${actionType}/`;
    const res = await request.post(url, { _id: idArray });
    if (res.code === 200) {
      message.success(pageText('tasks.operationCompleted'));
      fetchSchedulerData();
    } else {
      message.error(res.message || pageText('tasks.operationFailedLabel'));
    }
  } catch (e) {
    message.error(pageText('tasks.requestFailed'));
  }
};

const handleSchedulerSingleAction = (type, id) => performSchedulerAction(type, [id]);
const handleSchedulerBatchDelete = () => performSchedulerAction('delete', schedulerSelectedRowKeys.value);
const handleSchedulerBatchStop = () => performSchedulerAction('stop', schedulerSelectedRowKeys.value);

// 策略弹窗逻辑
const schedulerModalVisible = ref(false);
const schedulerSubmitLoading = ref(false);
const schedulerIsEdit = ref(false);
const schedulerEditId = ref('');
const schedulerForm = reactive({ name: '', keyword: '', cron: '' });

const openSchedulerAdd = () => {
  schedulerIsEdit.value = false;
  schedulerEditId.value = '';
  Object.assign(schedulerForm, { name: '', keyword: '', cron: '' });
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
  } catch (error) {
    message.error(pageText('tasks.requestFailed'));
  } finally {
    schedulerSubmitLoading.value = false;
  }
};


// ==========================================
// 👷 模块 B: 扫描任务实例 (github_task)
// ==========================================
const taskLoading = ref(false);
const taskData = ref([]);
const taskSearchForm = reactive({ name: '', keyword: '', status: undefined });
const taskPagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

const taskSelectedRowKeys = ref([]);
const taskHasSelected = computed(() => taskSelectedRowKeys.value.length > 0);
const onTaskSelectChange = (keys) => { taskSelectedRowKeys.value = keys; };

const taskColumns = [
  { get title() { return pageText('tasks.taskName'); }, dataIndex: 'name', key: 'name', width: 150 },
  { get title() { return pageText('pages.keywordLabel2'); }, dataIndex: 'keyword', key: 'keyword', width: 150 },
  { get title() { return pageText('pages.results'); }, dataIndex: 'result_count', key: 'result_count', width: 100 },
  { get title() { return pageText('tasks.status'); }, dataIndex: 'status', key: 'status', width: 100 },
  { get title() { return pageText('tasks.startTime'); }, dataIndex: 'start_time', key: 'start_time', width: 180 },
  { get title() { return pageText('tasks.endTime'); }, dataIndex: 'end_time', key: 'end_time', width: 180 },
  { get title() { return pageText('pages.taskId'); }, dataIndex: '_id', key: '_id', width: 200 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 150 }
];

const fetchTaskData = async () => {
  taskLoading.value = true;
  try {
    const params = { page: taskPagination.current, size: taskPagination.pageSize };
    if (taskSearchForm.name) params.name = taskSearchForm.name;
    if (taskSearchForm.keyword) params.keyword = taskSearchForm.keyword;
    if (taskSearchForm.status) params.status = taskSearchForm.status;

    const res = await request.get('/github_task/', { params });
    if (res.code === 200) {
      taskData.value = (res.items || []).map(item => {
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
  } catch (error) {
    message.error(pageText('pages.failedToLoadScanningTasks'));
  } finally {
    taskLoading.value = false;
  }
};

const resetTaskSearch = () => {
  Object.assign(taskSearchForm, { name: '', keyword: '', status: undefined });
  taskPagination.current = 1;
  onTaskSearch();
};
const onTaskSearch = () => { taskPagination.current = 1; fetchTaskData(); };
const handleTaskTableChange = (page, pageSize) => {
  taskPagination.current = page;
  taskPagination.pageSize = pageSize;
  fetchTaskData();
};

const goToTaskDetail = (record) => {
  openResultDrawer(record, 'task');
};

// ================= GitHub 任务与监控命中结果抽屉 =================
const resultDrawerVisible = ref(false);
const resultDrawerType = ref('task'); // 'task' | 'scheduler'
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
  { get title() { return pageText('pages.filePath'); }, dataIndex: 'path', key: 'path', width: 260 },
  { get title() { return pageText('pages.codeMatchedContent'); }, dataIndex: 'human_content', key: 'human_content' },
  { get title() { return pageText('pages.committedRecordedAt'); }, dataIndex: 'commit_date', key: 'commit_date', width: 170 },
  { get title() { return pageText('pages.keywordLabel2'); }, dataIndex: 'keyword', key: 'keyword', width: 110 }
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
      size: resultPagination.pageSize
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
  } catch (e) {
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
  if (resultPagination.pageSize !== globalPageSize.value) {
    globalPageSize.value = resultPagination.pageSize;
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
      order: 'create_time'
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
  } catch (e) {
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

const performTaskAction = async (actionType, idArray) => {
  try {
    const url = `/github_task/${actionType}/`;
    const res = await request.post(url, { _id: idArray });
    if (res.code === 200) {
      message.success(pageText('tasks.operationCompleted'));
      fetchTaskData();
    } else {
      message.error(res.message || pageText('tasks.operationFailedLabel'));
    }
  } catch (e) {
    message.error(pageText('tasks.requestFailed'));
  }
};

const handleTaskSingleAction = (type, id) => performTaskAction(type, [id]);
const handleTaskBatchDelete = () => performTaskAction('delete', taskSelectedRowKeys.value);
const handleTaskBatchStop = () => performTaskAction('stop', taskSelectedRowKeys.value);

const handleTaskRestart = async (record) => {
  try {
    const res = await request.post('/github_task/', { name: record.name, keyword: record.keyword });
    if (res.code === 200) {
      message.success(pageText('pages.taskRestartedANewTaskWasQueued'));
      onTaskSearch();
    } else {
      message.error(pageText('tasks.failedToRestartTask') + res.message);
    }
  } catch (error) {
    message.error(pageText('tasks.requestFailed'));
  }
};

// 新增任务弹窗
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
    } else {
      message.error(pageText('tasks.failedToCreateTaskLabel') + res.message);
    }
  } catch (error) {
    message.error(pageText('tasks.requestFailed'));
  } finally {
    taskSubmitLoading.value = false;
  }
};

// ==========================================
// 🛠️ 模块 C: 红队工具监控 (github_tools_target)
// ==========================================
const toolsLoading = ref(false);
const toolsData = ref([]);

const toolsSearchForm = reactive({ repo_url: '' });
const appliedToolsSearchForm = reactive({ repo_url: '' });
const onToolsSearch = () => { Object.assign(appliedToolsSearchForm, toolsSearchForm); toolsPagination.current = 1; };

const filteredToolsData = computed(() => {
  return toolsData.value.filter(item => {
    if (appliedToolsSearchForm.repo_url && !item.repo_url.toLowerCase().includes(appliedToolsSearchForm.repo_url.toLowerCase())) return false;
    return true;
  });
});

const toolsPagination = reactive({ current: 1, pageSize: globalPageSize.value });
const pagedToolsData = computed(() => {
  const start = (toolsPagination.current - 1) * toolsPagination.pageSize;
  return filteredToolsData.value.slice(start, start + toolsPagination.pageSize);
});
const onToolsTableChange = (page, pageSize) => { toolsPagination.current = page; toolsPagination.pageSize = pageSize; };
const resetToolsSearch = () => { toolsSearchForm.repo_url = ''; Object.assign(appliedToolsSearchForm, toolsSearchForm); toolsPagination.current = 1; };

const toolsSelectedRowKeys = ref([]);
const toolsHasSelected = computed(() => toolsSelectedRowKeys.value.length > 0);
const onToolsSelectChange = (keys) => { toolsSelectedRowKeys.value = keys; };

const handleToolsBatchDelete = async () => {
  const res = await request.post('/github_threat/tools_target/delete', { repo_urls: toolsSelectedRowKeys.value });
  if (res.code === 200) {
    message.success(pageText('pages.selectedRecordsDeleted'));
    toolsSelectedRowKeys.value = [];
    fetchToolsData();
  } else {
    message.error(res.message);
  }
};

const toolModalVisible = ref(false);
const toolForm = reactive({ repo_url: '' });

const toolsColumns = [
  { get title() { return pageText('pages.toolNameUrl'); }, dataIndex: 'repo_url', key: 'repo_url', width: 350 },
  { get title() { return pageText('pages.latestVersion'); }, dataIndex: 'last_tag', key: 'last_tag', width: 120 },
  { get title() { return pageText('pages.releasedAt'); }, dataIndex: 'last_commit_time', key: 'last_commit_time', width: 150 },
  { get title() { return pageText('pages.recordedAt'); }, dataIndex: 'insert_time', key: 'insert_time', width: 150 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 150 }
];

const fetchToolsData = async () => {
  toolsLoading.value = true;
  try {
    const res = await request.get('/github_threat/tools_target');
    if (res.code === 200) {
      toolsData.value = res.data || [];
    }
  } catch (error) {
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

const submitToolModal = async () => {
  if (!toolForm.repo_url) return message.warning(pageText('pages.urlCannotBeEmpty'));
  const res = await request.post('/github_threat/tools_target', toolForm);
  if (res.code === 200) {
    message.success(pageText('pages.added'));
    toolModalVisible.value = false;
    fetchToolsData();
  } else {
    message.error(res.message);
  }
};

// ==========================================
// 🧑‍💻 模块 D: 大佬动态监控 (github_hackers_target)
// ==========================================
const hackersLoading = ref(false);
const hackersData = ref([]);

const hackersSearchForm = reactive({ github_id: '' });
const appliedHackersSearchForm = reactive({ github_id: '' });
const onHackersSearch = () => { Object.assign(appliedHackersSearchForm, hackersSearchForm); hackersPagination.current = 1; };

const filteredHackersData = computed(() => {
  return hackersData.value.filter(item => {
    if (appliedHackersSearchForm.github_id && !item.github_id.toLowerCase().includes(appliedHackersSearchForm.github_id.toLowerCase())) return false;
    return true;
  });
});

const hackersPagination = reactive({ current: 1, pageSize: globalPageSize.value });
const pagedHackersData = computed(() => {
  const start = (hackersPagination.current - 1) * hackersPagination.pageSize;
  return filteredHackersData.value.slice(start, start + hackersPagination.pageSize);
});
const onHackersTableChange = (page, pageSize) => { hackersPagination.current = page; hackersPagination.pageSize = pageSize; };
const resetHackersSearch = () => { hackersSearchForm.github_id = ''; Object.assign(appliedHackersSearchForm, hackersSearchForm); hackersPagination.current = 1; };

const hackersSelectedRowKeys = ref([]);
const hackersHasSelected = computed(() => hackersSelectedRowKeys.value.length > 0);
const onHackersSelectChange = (keys) => { hackersSelectedRowKeys.value = keys; };

const handleHackersBatchDelete = async () => {
  const res = await request.post('/github_threat/hackers_target/delete', { github_ids: hackersSelectedRowKeys.value });
  if (res.code === 200) {
    message.success(pageText('pages.selectedRecordsDeleted'));
    hackersSelectedRowKeys.value = [];
    fetchHackersData();
  } else {
    message.error(res.message);
  }
};

const hackerModalVisible = ref(false);
const hackerForm = reactive({ github_id: '' });

const historyDrawerVisible = ref(false);
const historyLoading = ref(false);
const hackersHistoryData = ref([]);

const hackersColumns = [
  { get title() { return pageText('pages.githubIdResearcherTeam'); }, dataIndex: 'github_id', key: 'github_id', width: 250 },
  { get title() { return pageText('pages.openSourceToolsDiscovered'); }, dataIndex: 'found_count', key: 'found_count', width: 180 },
  { get title() { return pageText('pages.monitoringAddedAt'); }, dataIndex: 'insert_time', key: 'insert_time', width: 180 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 150 }
];

const historyColumns = [
  { get title() { return pageText('tasks.discoveredAt'); }, dataIndex: 'insert_time', key: 'insert_time', width: 180 },
  { get title() { return pageText('pages.toolRepositoryPath'); }, dataIndex: 'full_name', key: 'full_name' }
];

const openHackersHistoryDrawer = () => {
  historyDrawerVisible.value = true;
  fetchHackersHistory();
};

const closeHackersHistoryDrawer = () => {
  historyDrawerVisible.value = false;
};

const fetchHackersHistory = async () => {
  historyLoading.value = true;
  try {
    const res = await request.get('/github_threat/hackers_history');
    if (res.code === 200) {
      hackersHistoryData.value = res.data || [];
    }
  } catch (error) {
    message.error(pageText('pages.failedToLoadDiscoveredTools'));
  } finally {
    historyLoading.value = false;
  }
};

const fetchHackersData = async () => {
  hackersLoading.value = true;
  try {
    const res = await request.get('/github_threat/hackers_target');
    if (res.code === 200) {
      hackersData.value = res.data || [];
    }
  } catch (error) {
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
  if (!hackerForm.github_id) return message.warning(pageText('pages.idCannotBeEmpty'));
  const res = await request.post('/github_threat/hackers_target', hackerForm);
  if (res.code === 200) {
    message.success(pageText('pages.added'));
    hackerModalVisible.value = false;
    fetchHackersData();
  } else {
    message.error(res.message);
  }
};

// ==========================================
// 🛡️ 模块 E: CVE 监控历史 (github_cve_history)
// ==========================================
const cveLoading = ref(false);
const cveData = ref([]);

const cveSearchForm = reactive({ cve_name: '', desc: '' });
const appliedCveSearchForm = reactive({ cve_name: '', desc: '' });
const onCveSearch = () => { Object.assign(appliedCveSearchForm, cveSearchForm); cvePagination.current = 1; };

const filteredCveData = computed(() => {
  return cveData.value.filter(item => {
    if (appliedCveSearchForm.cve_name && !item.cve_name.toLowerCase().includes(appliedCveSearchForm.cve_name.toLowerCase())) return false;
    if (appliedCveSearchForm.desc && !item.desc.toLowerCase().includes(appliedCveSearchForm.desc.toLowerCase())) return false;
    return true;
  });
});

const cvePagination = reactive({ current: 1, pageSize: globalPageSize.value });

// 所有分页状态初始化后再注册监听，避免首次读取尚未声明的变量。
watch(globalPageSize, (newSize) => {
  schedulerPagination.pageSize = newSize;
  taskPagination.pageSize = newSize;
  toolsPagination.pageSize = newSize;
  hackersPagination.pageSize = newSize;
  cvePagination.pageSize = newSize;
  resultPagination.pageSize = newSize;
});

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
const resetCveSearch = () => { cveSearchForm.cve_name = ''; cveSearchForm.desc = ''; Object.assign(appliedCveSearchForm, cveSearchForm); cvePagination.current = 1; };

const cveSelectedRowKeys = ref([]);
const cveHasSelected = computed(() => cveSelectedRowKeys.value.length > 0);
const onCveSelectChange = (keys) => { cveSelectedRowKeys.value = keys; };

const handleCveBatchDelete = async () => {
  const res = await request.post('/github_threat/cve_history/delete', { cve_names: cveSelectedRowKeys.value });
  if (res.code === 200) {
    message.success(pageText('pages.selectedRecordsDeleted'));
    cveSelectedRowKeys.value = [];
    fetchCveData();
  } else {
    message.error(res.message);
  }
};

const handleCveDelete = async (cve_name) => {
  const res = await request.post('/github_threat/cve_history/delete', { cve_name });
  if (res.code === 200) {
    message.success(pageText('tasks.deletedSuccessfully'));
    fetchCveData();
  } else {
    message.error(res.message);
  }
};


const cveColumns = [
  { get title() { return pageText('pages.cveIdLabel2'); }, dataIndex: 'cve_name', key: 'cve_name', width: 150 },
  { get title() { return pageText('pages.githubUrl'); }, dataIndex: 'cve_url', key: 'cve_url', width: 250 },
  { get title() { return pageText('pages.officialDescription'); }, dataIndex: 'desc', key: 'desc', width: 450 },
  { get title() { return pageText('pages.latestPush'); }, dataIndex: 'pushed_at', key: 'pushed_at', width: 120 },
  { get title() { return pageText('pages.recordedAtLabel2'); }, dataIndex: 'insert_time', key: 'insert_time', width: 180 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 100 }
];

const fetchCveData = async () => {
  cveLoading.value = true;
  try {
    const res = await request.get('/github_threat/cve_history');
    if (res.code === 200) {
      cveData.value = res.data || [];
    }
  } catch (error) {
    message.error(pageText('pages.failedToLoadCveMonitoringRecords'));
  } finally {
    cveLoading.value = false;
  }
};

const cveConfig = reactive({ enabled: false, interval: 6, is_running: false });
const cveRunLoading = ref(false);

const fetchCveConfig = async () => {
  try {
    const res = await request.get('/github_threat/cve_config');
    if (res.code === 200) {
      cveConfig.enabled = res.data.enabled;
      cveConfig.interval = res.data.interval;
      cveConfig.is_running = !!res.data.is_running;
    }
  } catch (error) {
    console.error(error);
  }
};

const saveCveConfig = async () => {
  try {
    const res = await request.post('/github_threat/cve_config', cveConfig);
    if (res.code === 200) {
      message.success(pageText('pages.configurationSaved'));
    } else {
      message.error(res.message || pageText('pages.failedToSaveConfiguration'));
    }
  } catch (error) {
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
      fetchCveData();
    } else {
      message.warning(res.data?.msg || res.message || pageText('pages.unableToStart'));
    }
  } catch (error) {
    message.error(pageText('pages.requestFailed'));
  } finally {
    cveRunLoading.value = false;
  }
};

const tokenStatus = reactive({ status: '', msg: '' });
const fetchTokenStatus = async () => {
  try {
    const res = await request.get('/github_threat/token_status');
    if (res.code === 200) {
      tokenStatus.status = res.data.status;
      tokenStatus.msg = res.data.msg;
    }
  } catch (error) {
    console.error(error);
  }
};

const toolsConfig = reactive({ enabled: false, interval: 6, is_running: false });
const toolsRunLoading = ref(false);
const hackersConfig = reactive({ enabled: false, interval: 6, is_running: false });
const hackersRunLoading = ref(false);

const fetchToolsConfig = async () => {
  try {
    const res = await request.get('/github_threat/tools_config');
    if (res.code === 200) {
      toolsConfig.enabled = res.data.enabled;
      toolsConfig.interval = res.data.interval;
      toolsConfig.is_running = !!res.data.is_running;
    }
  } catch (error) {
    console.error(error);
  }
};

const saveToolsConfig = async () => {
  try {
    const res = await request.post('/github_threat/tools_config', toolsConfig);
    if (res.code === 200) {
      message.success(pageText('pages.configurationSaved'));
    } else {
      message.error(res.message || pageText('pages.failedToSaveConfiguration'));
    }
  } catch (error) {
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
      fetchToolsData();
    } else {
      message.warning(res.data?.msg || res.message || pageText('pages.unableToStart'));
    }
  } catch (error) {
    message.error(pageText('pages.requestFailed'));
  } finally {
    toolsRunLoading.value = false;
  }
};

const fetchHackersConfig = async () => {
  try {
    const res = await request.get('/github_threat/hackers_config');
    if (res.code === 200) {
      hackersConfig.enabled = res.data.enabled;
      hackersConfig.interval = res.data.interval;
      hackersConfig.is_running = !!res.data.is_running;
    }
  } catch (error) {
    console.error(error);
  }
};

const saveHackersConfig = async () => {
  try {
    const res = await request.post('/github_threat/hackers_config', hackersConfig);
    if (res.code === 200) {
      message.success(pageText('pages.configurationSaved'));
    } else {
      message.error(res.message || pageText('pages.failedToSaveConfiguration'));
    }
  } catch (error) {
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
      fetchHackersData();
    } else {
      message.warning(res.data?.msg || res.message || pageText('pages.unableToStart'));
    }
  } catch (error) {
    message.error(pageText('pages.requestFailed'));
  } finally {
    hackersRunLoading.value = false;
  }
};

onDeactivated(() => {
  historyDrawerVisible.value = false;
  schedulerModalVisible.value = false;
  taskModalVisible.value = false;
  toolModalVisible.value = false;
  hackerModalVisible.value = false;
  resultDrawerVisible.value = false;
  stopResultSyslogTimer();
});

onUnmounted(() => {
  stopResultSyslogTimer();
});
</script>

<style scoped>
.page-settings-link { margin-left: 4px; }
.page-inline-gap { margin-right: 8px; }
.page-width-180 { width: 180px; }
.page-flush-bottom { margin-bottom: 0; }
.page-width-250 { width: 250px; }
.page-placeholder { color: var(--arl-text-color); opacity: 0.25; }
.page-summary-caption { color: var(--arl-text-color); opacity: 0.65; font-size: 12px; }
.page-log-empty { color: rgba(255,255,255,0.45); font-style: italic; }

.github-sticky-toolbar {
  position: sticky;
  top: 0;
  z-index: 10;
  background-color: var(--arl-bg-sticky);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  padding: 12px 0 8px;
  margin-bottom: 12px;
  border-bottom: 1px solid var(--arl-border-color);
}

.page-filter-form { row-gap: 16px; margin-bottom: 16px; }
.page-modal-form { margin-top: 20px; }
</style>
