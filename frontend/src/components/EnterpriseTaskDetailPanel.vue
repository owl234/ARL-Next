<template>
  <div class="enterprise-task-detail-panel">
    <!-- 1. 统一吸顶 Hero 头部卡片 -->
    <div ref="actionBarRef" class="arl-hero-card">
      <div class="arl-hero-unified-bar">
        <div class="arl-hero-left">
          <button
            type="button"
            class="arl-detail-back-btn"
            @click="handleBack"
          >
            <arrow-left-outlined />
            <span>{{ taskText('pages.backToList').replace(/^<\s*/, '') }}</span>
          </button>

          <div class="arl-hero-v-divider"></div>

          <a-tooltip placement="bottomLeft">
            <template #title>
              <div style="word-break: break-all; max-height: 300px; overflow-y: auto; font-weight: normal; font-size: 13px;">
                <div v-for="(item, index) in targetList" :key="index">
                  {{ item }}
                </div>
              </div>
            </template>
            <span class="arl-hero-title" style="cursor: default;">{{ displayTitle }}</span>
          </a-tooltip>
          <a-tag v-if="taskTypeLabel" color="blue">{{ taskTypeLabel }}</a-tag>
          <a-tag v-if="taskStatusLabel" :color="taskStatusColor">{{ taskStatusLabel }}</a-tag>
          <a-tag
            v-if="taskRecord.synced_scope_id"
            color="blue"
            style="cursor: pointer; display: inline-flex; align-items: center; gap: 4px;"
            @click="goToScope(taskRecord.synced_scope_id, taskRecord.synced_scope_name)"
            :title="taskText('tasks.openThisAssetGroup')"
          >
            <export-outlined />
            <span>{{ taskText('tasks.managedIn') }} {{ taskRecord.synced_scope_name || taskText('tasks.assetGroup') }}</span>
          </a-tag>
        </div>

        <div class="arl-hero-right">
          <a-tooltip v-if="taskStatus === 'done' && (taskRecord.statistic?.web_cnt === 0)" :title="taskText('tasks.thisTaskHasNoWebsiteAssetsToSync')">
            <a-button type="primary" size="small" disabled>
              <template #icon><cloud-sync-outlined /></template>
              {{ taskText('tasks.syncToAssetGroup') }}
            </a-button>
          </a-tooltip>
          <a-button
            v-else
            type="primary"
            size="small"
            @click="openSyncModal"
            :disabled="taskStatus !== 'done' && taskStatus !== 'stop'"
          >
            <template #icon><cloud-sync-outlined /></template>
            {{ taskRecord.synced_scope_id ? (taskRecord.has_increment ? taskText('tasks.syncNewAssetsToAssetGroup') : taskText('tasks.syncToAssetGroupAgain')) : taskText('tasks.syncToAssetGroup') }}
          </a-button>
        </div>
      </div>

      <a-tabs
        v-model:activeKey="activeTab"
        type="card"
        size="small"
        class="arl-detail-tabs enterprise-detail-tabs"
        :class="{ 'is-log-tab': activeTab === 'log' }"
        @change="onTabChange"
      >
        <a-tab-pane key="web" :tab="taskText('tasks.websiteIcpRecordsCount', { count: queryCounts.web })"></a-tab-pane>
        <a-tab-pane key="app" :tab="`APP - ${queryCounts.app}`"></a-tab-pane>
        <a-tab-pane key="mapp" :tab="taskText('tasks.miniProgramsCount', { count: queryCounts.mapp })"></a-tab-pane>
        <a-tab-pane v-if="taskType === 'tyc'" key="wechat" :tab="taskText('tasks.officialAccountsCount', { count: queryCounts.wechat })"></a-tab-pane>
        <a-tab-pane v-if="taskType === 'tyc'" key="weibo" :tab="taskText('tasks.weiboAccountsCount', { count: queryCounts.weibo })"></a-tab-pane>
        <a-tab-pane key="kapp" :tab="taskText('tasks.quickAppsCount', { count: queryCounts.kapp })"></a-tab-pane>
        <a-tab-pane v-if="taskType === 'tyc'" key="invest" :tab="taskText('tasks.investmentsCountLabel', { count: queryCounts.invest })"></a-tab-pane>
        <a-tab-pane key="log" :tab="taskText('tasks.executionLogs')"></a-tab-pane>
      </a-tabs>

      <div v-show="activeTab !== 'log'" class="arl-toolbar-row">
        <div class="arl-filter-group">
          <a-button
            size="small"
            :type="filterExpanded ? 'primary' : 'default'"
            :ghost="filterExpanded"
            @click="filterExpanded = !filterExpanded"
          >
            <template #icon><filter-outlined /></template>
            {{ filterExpanded ? taskText('tasks.hideFilters') : taskText('tasks.advancedFilters') }}
            <a-badge
              v-if="activeFilterCount > 0"
              :count="activeFilterCount"
              :number-style="{ backgroundColor: 'var(--arl-theme-color)', marginLeft: '4px' }"
            />
          </a-button>
          <a-button size="small" @click="resetSearch">
            <template #icon><undo-outlined /></template>
            {{ taskText('tasks.clear') }}
          </a-button>
        </div>

        <div class="arl-actions-group">
          <a-button
            v-if="activeTab === 'web' && selectedWebRowKeys.length > 0"
            type="dashed"
            size="small"
            @click="openSyncModalWithSelected"
          >
            <template #icon><cloud-sync-outlined /></template>
            {{ taskText('tasks.syncSelectedDomainCount', { count: selectedWebRowKeys.length }) }}
          </a-button>
          <a-button size="small" :loading="exportLoading" @click="handleExport">
            <template #icon><download-outlined /></template>
            {{ taskText('tasks.exportData') }}
          </a-button>
        </div>
      </div>
    </div>

    <!-- 2. 可折叠检索条件网格面板 -->
    <div v-if="filterExpanded && activeTab !== 'log'" class="arl-filter-card">
      <div class="arl-filter-grid">
        <div v-for="col in filterColumns" :key="col.key" class="arl-filter-cell">
          <span class="arl-filter-cell-label">{{ col.title }}</span>
          <a-input-group compact v-if="['amount', 'percent'].includes(col.dataIndex)" style="display: flex;">
            <a-select
              v-model:value="searchFormOp[col.dataIndex]"
              size="small"
              style="width: 66px; flex-shrink: 0;"
              :options="[{value:'eq',label:'='},{value:'gt',label:'>'},{value:'lt',label:'<'}]"
            />
            <a-input
              v-model:value="searchForm[col.dataIndex]"
              size="small"
              style="flex: 1;"
              :placeholder="taskText('tasks.enterField', { field: col.title })"
              allowClear
              @pressEnter="onSearch"
            >
              <template #suffix><search-outlined @click="onSearch" style="color: var(--arl-text-color); opacity: 0.35; cursor: pointer;"/></template>
            </a-input>
          </a-input-group>
          <a-input
            v-else
            v-model:value="searchForm[col.dataIndex]"
            :placeholder="taskText('tasks.enterField', { field: col.title })"
            size="small"
            allowClear
            @pressEnter="onSearch"
          >
            <template #suffix><search-outlined @click="onSearch" style="color: var(--arl-text-color); opacity: 0.35; cursor: pointer;"/></template>
          </a-input>
        </div>
      </div>

      <div class="arl-filter-footer">
        <a-button size="small" @click="resetSearch">{{ taskText('tasks.clear') }}</a-button>
        <a-button type="primary" size="small" @click="onSearch">
          <template #icon><search-outlined /></template>
          {{ taskText('tasks.search') }}
        </a-button>
      </div>
    </div>

    <div v-show="activeTab !== 'log'">
      <a-table
        :sticky="stickyConfig"
        :dataSource="assetList"
        :columns="dynamicColumns"
        :loading="loading"
        :pagination="false"
        :row-selection="activeTab === 'web' ? { selectedRowKeys: selectedWebRowKeys, onChange: onWebSelectChange } : null"
        :scroll="pagination.pageSize >= 100 ? { y: 'calc(100vh - 380px)', x: 'max-content' } : { x: 'max-content' }"
        :virtual="pagination.pageSize >= 100"
        :rowKey="(record) => record._id || record.id || record.domain || record.ym || Math.random()"
        size="small"
        @change="handleTableChange"
      >
        <template #bodyCell="{ column, record, text, index }">
          <template v-if="column.key === 'index'">
            {{ (pagination.current - 1) * pagination.pageSize + index + 1 }}
          </template>
          <template v-else-if="column.key === 'icon'">
            <img v-if="text" :src="text" style="width:32px;height:32px;border-radius:4px;" />
          </template>
          <template v-else-if="column.key === 'brief' || column.key === 'recommend'">
            <div style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="text">
              {{ text || '-' }}
            </div>
          </template>
          <template v-else-if="column.key === 'serviceName' || column.key === 'name'">
            {{ record.serviceName || record.name || '-' }}
          </template>
          <template v-else-if="column.key === 'serviceLicence' || column.key === 'serviceFilingNumber'">
            {{ record.serviceLicence || record.serviceFilingNumber || record.liscense || '-' }}
          </template>
          <template v-else-if="column.key === 'unitName' || column.key === 'companyName'">
            {{ record.unitName || record.companyName || '-' }}
          </template>
          <template v-else-if="column.key === 'mainLicence'">
            {{ record.mainLicence || record.liscense || '-' }}
          </template>
          <template v-else-if="column.key === 'updateRecordTime' || column.key === 'examineDate'">
            {{ record.updateRecordTime || record.examineDate || '-' }}
          </template>
          <template v-else-if="column.key === 'raw'">
            <a-popover :title="taskText('tasks.rawData')" trigger="click" placement="left">
              <template #content>
                <div style="max-width: 400px; max-height: 400px; overflow: auto;">
                  <pre style="font-size: 12px;">{{ JSON.stringify(record, null, 2) }}</pre>
                </div>
              </template>
              <a-button type="link" size="small">{{ taskText('tasks.viewJson') }}</a-button>
            </a-popover>
          </template>
          <template v-else>
            {{ text || '-' }}
          </template>
        </template>
        <template #emptyText>
          <ArlEmpty :description="taskText('tasks.noData')" />
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">{{ taskText('tasks.paginationSummary', { pages: Math.ceil(pagination.total / pagination.pageSize) || 1, total: pagination.total }) }}</div>
        <a-pagination size="small" :pageSizeOptions="$pageSizeOptions" v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handlePaginationChange" @showSizeChange="handlePaginationChange" />
      </div>
    </div>

    <div v-show="activeTab === 'log'">
      <div style="border: 1px solid var(--arl-border-color); border-radius: 4px; padding: 8px; background-color: var(--arl-bg-light);">
        <div ref="terminalContainer" style="background-color: var(--arl-terminal-bg); color: var(--arl-terminal-text); border: 1px solid var(--arl-terminal-border); font-family: var(--arl-font-mono); padding: 16px; border-radius: 4px; height: calc(100vh - 240px); overflow-y: auto; font-size: 13px; line-height: 1.6; box-shadow: inset 0 2px 8px rgba(0,0,0,0.2);" @mouseenter="pauseScroll = true" @mouseleave="pauseScroll = false">
          <div v-for="(log, idx) in syslogList" :key="idx" style="margin-bottom: 6px; word-break: break-all; border-bottom: 1px dashed rgba(255,255,255,0.1); padding-bottom: 4px;">
            <a style="margin-right: 8px;">[{{ log.create_time }}]</a>
            <span :style="{ color: log.level === 'error' ? '#ff4d4f' : log.level === 'warning' ? '#faad14' : '#52c41a', fontWeight: 'bold', marginRight: '8px' }">[{{ (log.level || 'info').toUpperCase() }}]</span>
            <a style="margin-right: 8px;">[{{ log.title }}]</a>
            <span style="color: var(--arl-terminal-text);">{{ log.message }}</span>
          </div>
          <div v-if="syslogLoading && syslogList.length === 0" class="task-log-hint">{{ taskText('tasks.systemLoadingTaskExecutionLogs') }}</div>
          <div v-else-if="syslogList.length === 0" class="task-log-empty">{{ taskText('tasks.systemNoLogsYetTheTaskHasNot') }}</div>
        </div>
      </div>
    </div>

    <SyncToScopeModal
      v-model:open="syncModalVisible"
      :task="taskRecord"
      :preSelectedDomains="selectedWebDomains"
      @success="handleSyncSuccess"
    />
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';

import { ref, reactive, onMounted, onUnmounted, onActivated, onDeactivated, watch, nextTick, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { ArrowLeftOutlined, FilterOutlined, UndoOutlined, SearchOutlined, DownloadOutlined, CloudSyncOutlined, ExportOutlined } from '@ant-design/icons-vue';
import SyncToScopeModal from './SyncToScopeModal.vue';
import { message } from 'ant-design-vue';
import request from '../utils/request';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import { useSticky } from '../utils/useSticky';
import { formatTaskStatus, formatTaskStatusColor } from '../constants/taskStatus';

const { t: taskText } = useI18n({ useScope: 'global' });

const route = useRoute();
const router = useRouter();

const taskId = computed(() => (route.query?.task_id ? String(route.query.task_id) : ''));
const taskName = ref(route.query?.name || '');
const taskTarget = ref(route.query?.target || '');
const taskType = ref(route.query?.task_type || 'icp');
const taskStatus = ref('');
const taskRecord = ref({});

const syncModalVisible = ref(false);
const selectedWebRowKeys = ref([]);
const selectedWebDomains = ref([]);

const handleBack = () => {
  router.push({ path: '/taskList', query: { tab: 'enterprise' } });
};

const onWebSelectChange = (keys, rows) => {
  selectedWebRowKeys.value = keys;
  const domains = [];
  rows.forEach(r => {
    const d = r.domain || r.ym;
    if (d && typeof d === 'string') domains.push(d.trim());
  });
  selectedWebDomains.value = domains;
};

const openSyncModal = () => {
  selectedWebDomains.value = [];
  syncModalVisible.value = true;
};

const openSyncModalWithSelected = () => {
  syncModalVisible.value = true;
};

const handleSyncSuccess = (res) => {
  taskRecord.value.synced_scope_id = res.scope_id;
  taskRecord.value.synced_scope_name = res.target_name;
  fetchTaskStatistic();
};

const goToScope = (scopeId, scopeName) => {
  if (scopeId) {
    router.push({
      path: '/groupAssetsManagement/groupAssetsDetail',
      query: { scope_id: scopeId, targetName: scopeName || '', view: 'osint' }
    });
  }
};

const targetList = computed(() => {
  const t = taskTarget.value || taskName.value || taskId.value || taskText('tasks.unknownTarget');
  return String(t).split(/[,\s]+/).filter(Boolean);
});

const displayTitle = computed(() => {
  const list = targetList.value;
  if (list.length <= 1) {
    return taskText('tasks.assetsRelatedToTarget', { target: list[0] || taskText('tasks.target') });
  }
  return taskText('tasks.assetsRelatedToTargetAndOtherTargetsCount', { target: list[0], count: list.length });
});

const taskTypeLabel = computed(() => {
  if (taskType.value === 'tyc') return taskText('tasks.combinedSources');
  if (taskType.value === 'icp') return taskText('tasks.officialIcpRecordsLabel');
  return taskText('tasks.enterpriseOsint');
});

const taskStatusLabel = computed(() => {
  return formatTaskStatus(taskStatus.value);
});

const taskStatusColor = computed(() => {
  return formatTaskStatusColor(taskStatus.value);
});

const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

const getAvailableTabs = (type = taskType.value) => {
  if (type === 'icp') {
    return ['web', 'app', 'mapp', 'kapp', 'log'];
  }
  return ['web', 'app', 'mapp', 'wechat', 'weibo', 'kapp', 'invest', 'log'];
};

const validTabs = ['web', 'app', 'mapp', 'kapp', 'invest', 'wechat', 'weibo', 'log'];
const activeTab = ref(route.query?.tab && validTabs.includes(route.query.tab) ? route.query.tab : 'web');
const queryCounts = reactive({
  web: 0,
  app: 0,
  mapp: 0,
  kapp: 0,
  invest: 0,
  wechat: 0,
  weibo: 0,
});

const syncEnterpriseQueryCounts = (q = route.query) => {
  queryCounts.web = Number(q?.web_cnt) || 0;
  queryCounts.app = Number(q?.app_cnt) || 0;
  queryCounts.mapp = Number(q?.mapp_cnt) || 0;
  queryCounts.kapp = Number(q?.kapp_cnt) || 0;
  queryCounts.invest = Number(q?.invest_cnt) || 0;
  queryCounts.wechat = Number(q?.wechat_cnt) || 0;
  queryCounts.weibo = Number(q?.weibo_cnt) || 0;
};
syncEnterpriseQueryCounts();

const assetList = ref([]);
const loading = ref(false);
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

const syslogList = ref([]);
let syslogTimer = null;
const terminalContainer = ref(null);
const pauseScroll = ref(false);
const syslogLoading = ref(false);

const sortState = reactive({
  field: null,
  order: null
});

const getDefaultSortForTab = (tab) => {
  if (tab === 'kapp') {
    return { field: 'updateRecordTime', order: 'descend' };
  }
  const isTyc = taskType.value === 'tyc';
  if (isTyc) {
    if (tab === 'web' || tab === 'mapp') {
      return { field: 'examineDate', order: 'descend' };
    }
  } else {
    if (['web', 'app', 'mapp'].includes(tab)) {
      return { field: 'updateRecordTime', order: 'descend' };
    }
  }
  return { field: null, order: null };
};

const resetTabSort = (tab) => {
  const def = getDefaultSortForTab(tab);
  sortState.field = def.field;
  sortState.order = def.order;
};

const webColumns = [
  { get title() { return taskText('tasks.organizationName'); }, dataIndex: 'companyName', key: 'companyName', width: 220 },
  { get title() { return taskText('tasks.organizationType'); }, dataIndex: 'companyType', key: 'companyType', width: 120 },
  { get title() { return taskText('tasks.primaryIcpNumber'); }, dataIndex: 'liscense', key: 'liscense', width: 180 },
  { get title() { return taskText('tasks.domains'); }, dataIndex: 'ym', key: 'ym', width: 200 },
  { get title() { return taskText('tasks.websiteName'); }, dataIndex: 'webName', key: 'webName', width: 200 },
  { get title() { return taskText('tasks.reviewDate'); }, dataIndex: 'examineDate', key: 'examineDate', width: 120 },
  { get title() { return taskText('tasks.details'); }, key: 'raw', width: 80 }
];

const mappColumns = [
  { get title() { return taskText('tasks.miniProgramName'); }, dataIndex: 'serviceName', key: 'serviceName', width: 200 },
  { get title() { return taskText('tasks.icpNumber'); }, dataIndex: 'serviceFilingNumber', key: 'serviceFilingNumber', width: 200 },
  { get title() { return taskText('tasks.reviewDate'); }, dataIndex: 'examineDate', key: 'examineDate', width: 120 },
  { get title() { return taskText('tasks.details'); }, key: 'raw', width: 80 }
];

const appColumns = [
  { get title() { return taskText('tasks.icon'); }, dataIndex: 'icon', key: 'icon', width: 60 },
  { get title() { return taskText('tasks.appName'); }, dataIndex: 'name', key: 'name', width: 150 },
  { get title() { return taskText('tasks.category'); }, dataIndex: 'classes', key: 'classes', width: 100 },
  { get title() { return taskText('tasks.appType'); }, dataIndex: 'type', key: 'type', width: 100 },
  { get title() { return taskText('tasks.description'); }, dataIndex: 'brief', key: 'brief', width: 300, ellipsis: true },
  { get title() { return taskText('tasks.details'); }, key: 'raw', width: 80 }
];

const investColumns = [
  { get title() { return taskText('tasks.investeeCompany'); }, dataIndex: 'name', key: 'name', width: 220 },
  { get title() { return taskText('tasks.legalRepresentative'); }, dataIndex: 'legalPersonName', key: 'legalPersonName', width: 120 },
  { get title() { return taskText('tasks.registeredCapital'); }, dataIndex: 'amount', key: 'amount', width: 120 },
  { get title() { return taskText('tasks.ownershipShare'); }, dataIndex: 'percent', key: 'percent', width: 100 },
  { get title() { return taskText('tasks.details'); }, key: 'raw', width: 80 }
];

const wechatColumns = [
  { get title() { return taskText('tasks.avatar'); }, dataIndex: 'titleImgURL', key: 'icon', width: 60 },
  { get title() { return taskText('tasks.officialAccountName'); }, dataIndex: 'title', key: 'title', width: 200 },
  { get title() { return taskText('tasks.wechatId'); }, dataIndex: 'publicNum', key: 'publicNum', width: 150 },
  { get title() { return taskText('tasks.description'); }, dataIndex: 'recommend', key: 'recommend', width: 300, ellipsis: true },
  { get title() { return taskText('tasks.details'); }, key: 'raw', width: 80 }
];

const weiboColumns = [
  { get title() { return taskText('tasks.weiboAccountName'); }, dataIndex: 'name', key: 'name', width: 200 },
  { get title() { return taskText('tasks.weiboUrl'); }, dataIndex: 'href', key: 'href', width: 250 },
  { get title() { return taskText('tasks.details'); }, key: 'raw', width: 80 }
];

const baseIcpColumns = [
  { get title() { return taskText('tasks.organizationName'); }, dataIndex: 'unitName', key: 'unitName', width: 220 },
  { get title() { return taskText('tasks.organizationType'); }, dataIndex: 'natureName', key: 'natureName', width: 120 },
  { get title() { return taskText('tasks.primaryIcpNumber'); }, dataIndex: 'mainLicence', key: 'mainLicence', width: 180 },
  { get title() { return taskText('tasks.domains'); }, dataIndex: 'domain', key: 'domain', width: 200 },
  { get title() { return taskText('tasks.websiteName'); }, dataIndex: 'serviceName', key: 'serviceName', width: 200 },
  { get title() { return taskText('tasks.reviewDate'); }, dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 140 },
  { get title() { return taskText('tasks.details'); }, key: 'raw', width: 80 }
];

const mobileIcpColumns = [
  { get title() { return taskText('tasks.applicationName'); }, dataIndex: 'serviceName', key: 'serviceName', width: 200 },
  { get title() { return taskText('tasks.serviceIcpNumber'); }, dataIndex: 'serviceLicence', key: 'serviceLicence', width: 200 },
  { get title() { return taskText('tasks.organizationName'); }, dataIndex: 'unitName', key: 'unitName', width: 220 },
  { get title() { return taskText('tasks.primaryIcpNumber'); }, dataIndex: 'mainLicence', key: 'mainLicence', width: 180 },
  { get title() { return taskText('tasks.approvalType'); }, dataIndex: 'contentTypeName', key: 'contentTypeName', width: 150 },
  { get title() { return taskText('tasks.reviewDate'); }, dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 140 },
  { get title() { return taskText('tasks.details'); }, key: 'raw', width: 80 }
];

const kappColumns = [
  { get title() { return taskText('tasks.quickAppName'); }, dataIndex: 'serviceName', key: 'serviceName', width: 200 },
  { get title() { return taskText('tasks.quickAppIcpNumber'); }, dataIndex: 'serviceLicence', key: 'serviceLicence', width: 200 },
  { get title() { return taskText('tasks.organizationName'); }, dataIndex: 'unitName', key: 'unitName', width: 220 },
  { get title() { return taskText('tasks.primaryIcpNumber'); }, dataIndex: 'mainLicence', key: 'mainLicence', width: 180 },
  { get title() { return taskText('tasks.approvalType'); }, dataIndex: 'contentTypeName', key: 'contentTypeName', width: 150 },
  { get title() { return taskText('tasks.reviewDate'); }, dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 140 },
  { get title() { return taskText('tasks.details'); }, key: 'raw', width: 80 }
];

const genericColumns = [
  { get title() { return taskText('tasks.name'); }, dataIndex: 'filterName', key: 'filterName', width: 200 },
  { get title() { return taskText('tasks.details'); }, key: 'raw', width: 80 }
];

const dynamicColumns = computed(() => {
  const isTyc = taskType.value === 'tyc';
  let cols = [];
  if (activeTab.value === 'invest') cols = investColumns;
  else if (activeTab.value === 'wechat') cols = wechatColumns;
  else if (activeTab.value === 'weibo') cols = weiboColumns;
  else if (activeTab.value === 'kapp') cols = kappColumns;
  else if (isTyc) {
    if (activeTab.value === 'web') cols = webColumns;
    else if (activeTab.value === 'mapp') cols = mappColumns;
    else if (activeTab.value === 'app') cols = appColumns;
    else cols = genericColumns;
  } else {
    if (activeTab.value === 'web') cols = baseIcpColumns;
    else if (['app', 'mapp'].includes(activeTab.value)) cols = mobileIcpColumns;
    else cols = genericColumns;
  }

  const processedCols = cols.map((col) => {
    if (col.key === 'examineDate' || col.key === 'updateRecordTime') {
      return {
        ...col,
        sorter: true,
        sortOrder: sortState.field === col.key ? sortState.order : null
      };
    }
    return col;
  });

  return [
    { title: taskText('tasks.no'), key: 'index', width: 70, align: 'center' },
    ...processedCols
  ];
});

const exportLoading = ref(false);
const handleExport = async () => {
  if (!taskId.value) return;
  try {
    exportLoading.value = true;
    message.loading({ content: taskText('tasks.exporting'), key: 'export', duration: 0 });
    const res = await request.get(`/icp/export/${taskId.value}`, { responseType: 'blob' });
    const resData = res.data || res;
    if (resData.type === 'application/json' || (res.headers && res.headers['content-type']?.includes('application/json'))) {
      message.error({ content: taskText('tasks.exportFailedUnexpectedApiResponse'), key: 'export', duration: 2 });
      return;
    }
    const blob = new Blob([resData]);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${taskName.value || taskTarget.value || 'icp_export'}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(url);
    message.success({ content: taskText('tasks.exportCompleted'), key: 'export', duration: 2 });
  } catch (error) {
    console.error('导出失败:', error);
    message.error({ content: taskText('tasks.exportFailed'), key: 'export', duration: 2 });
  } finally {
    exportLoading.value = false;
  }
};

const searchForm = reactive({});
const searchFormOp = reactive({ amount: 'eq', percent: 'eq' });
const filterExpanded = ref(false);
const filterColumns = computed(() =>
  (dynamicColumns.value || []).filter(
    col => !['index', 'raw', 'icon', 'examineDate', 'updateRecordTime'].includes(col.key)
  )
);
const activeFilterCount = computed(() =>
  Object.values(searchForm).filter(v => v !== undefined && v !== null && v !== '').length
);

const hasActiveSearch = () => {
  return Object.values(searchForm).some((val) => val !== undefined && val !== null && val !== '');
};

const resetSearch = () => {
  for (const key in searchForm) {
    delete searchForm[key];
  }
  searchFormOp.amount = 'eq';
  searchFormOp.percent = 'eq';
  pagination.current = 1;
  fetchAssets(1, pagination.pageSize);
};

const fetchAssets = async (page = 1, size = 10) => {
  loading.value = true;
  try {
    let orderParam = '-_id';
    if (sortState.field && sortState.order) {
      orderParam = (sortState.order === 'ascend' ? '+' : '-') + sortState.field;
    } else {
      const def = getDefaultSortForTab(activeTab.value);
      if (def.field && def.order) {
        orderParam = (def.order === 'ascend' ? '+' : '-') + def.field;
      }
    }

    const queryParams = { page, size, task_id: taskId.value, query_type: activeTab.value, order: orderParam };
    for (const [key, val] of Object.entries(searchForm)) {
      if (val !== undefined && val !== null && val !== '') {
        if (['amount', 'percent'].includes(key)) {
          const op = searchFormOp[key] || 'eq';
          const fieldName = key + '_num';
          if (op === 'gt') queryParams[`${fieldName}__ngt`] = val;
          else if (op === 'lt') queryParams[`${fieldName}__nlt`] = val;
          else queryParams[fieldName] = val;
        } else {
          queryParams[key] = val;
        }
      }
    }

    const res = await request.get('/icp/asset', { params: queryParams });
    if (res.code === 200) {
      assetList.value = res.items || [];
      pagination.total = res.total || 0;
      pagination.current = page;
      pagination.pageSize = size;
      if (!hasActiveSearch() && Object.prototype.hasOwnProperty.call(queryCounts, activeTab.value)) {
        queryCounts[activeTab.value] = pagination.total;
      }
    } else {
      console.error('获取资产列表失败:', res);
    }
  } catch (error) {
    console.error('API 请求失败:', error);
  } finally {
    loading.value = false;
  }
};

const onSearch = () => fetchAssets(1, pagination.pageSize);
const handleTableChange = (paginationData, filters, sorter) => {
  if (sorter && sorter.field && sorter.order) {
    sortState.field = sorter.field;
    sortState.order = sorter.order;
  } else {
    const def = getDefaultSortForTab(activeTab.value);
    sortState.field = def.field;
    sortState.order = def.order;
  }
  pagination.current = 1;
  fetchAssets(1, pagination.pageSize);
};

const handlePaginationChange = (page, pageSize) => {
  fetchAssets(page, pageSize);
};

const fetchSyslog = async (isPolling = false) => {
  if (!taskId.value) return;
  try {
    if (!isPolling) syslogLoading.value = true;
    const res = await request.get('/syslog/', {
      params: {
        task_id: taskId.value,
        size: 50000,
        order: 'create_time',
        _t: Date.now()
      }
    });
    if (res.code === 200) {
      syslogList.value = res.items || [];
      if (!pauseScroll.value) {
        nextTick(() => {
          if (terminalContainer.value) {
            terminalContainer.value.scrollTop = terminalContainer.value.scrollHeight;
          }
        });
      }
    }
  } catch (error) {
    console.error('获取日志失败:', error);
  } finally {
    if (!isPolling) syslogLoading.value = false;
  }
};

const startSyslogTimer = () => {
  if (syslogTimer) {
    clearInterval(syslogTimer);
    syslogTimer = null;
  }
  fetchSyslog();
  const isTerminal = ['done', 'error', 'stop'].includes(taskStatus.value);
  if (!isTerminal) {
    syslogTimer = setInterval(() => {
      fetchSyslog(true);
    }, 5000);
  }
};

const stopSyslogTimer = () => {
  if (syslogTimer) {
    clearInterval(syslogTimer);
    syslogTimer = null;
  }
};

const onTabChange = (key) => {
  for (const k of Object.keys(searchForm)) {
    delete searchForm[k];
  }
  for (const k of Object.keys(searchFormOp)) {
    delete searchFormOp[k];
  }

  if (key === 'invest') {
    searchFormOp['amount'] = 'eq';
    searchFormOp['percent'] = 'eq';
  }

  resetTabSort(key);

  if (key === 'log') {
    startSyslogTimer();
  } else {
    stopSyslogTimer();
    assetList.value = [];
    fetchAssets(1, globalPageSize.value);
  }
};

let taskTimer = null;
let lastStatus = '';

const fetchTaskStatistic = async () => {
  if (!taskId.value) return;
  try {
    const res = await request.get('/icp/task', { params: { _id: taskId.value, _t: Date.now() } });
    if (res.code === 200 && res.items && res.items.length > 0) {
      const taskData = res.items[0];
      taskRecord.value = taskData;
      if (taskData.name) taskName.value = taskData.name;
      if (taskData.target) taskTarget.value = taskData.target;
      if (taskData.task_type) taskType.value = taskData.task_type;
      taskStatus.value = taskData.status || '';

      const stat = taskData.statistic || {};
      queryCounts.web = stat.web_cnt !== undefined ? stat.web_cnt : queryCounts.web;
      queryCounts.app = stat.app_cnt !== undefined ? stat.app_cnt : queryCounts.app;
      queryCounts.mapp = stat.mapp_cnt !== undefined ? stat.mapp_cnt : queryCounts.mapp;
      queryCounts.kapp = stat.kapp_cnt !== undefined ? stat.kapp_cnt : queryCounts.kapp;
      queryCounts.invest = stat.invest_cnt !== undefined ? stat.invest_cnt : queryCounts.invest;
      queryCounts.wechat = stat.wechat_cnt !== undefined ? stat.wechat_cnt : queryCounts.wechat;
      queryCounts.weibo = stat.weibo_cnt !== undefined ? stat.weibo_cnt : queryCounts.weibo;

      const currentStatus = taskData.status;
      if (['done', 'error', 'stop'].includes(currentStatus)) {
        if (taskTimer) {
          clearInterval(taskTimer);
          taskTimer = null;
        }
        stopSyslogTimer();
        if (activeTab.value === 'log') {
          fetchSyslog(true);
        } else if (lastStatus && !['done', 'error', 'stop'].includes(lastStatus)) {
          fetchAssets(pagination.current, pagination.pageSize);
        }
      }
      lastStatus = currentStatus;
    }
  } catch (error) {
    console.error('获取任务统计失败:', error);
  }
};

const loadedEnterpriseTaskId = ref('');

const reloadEnterpriseTaskData = () => {
  if (taskTimer) {
    clearInterval(taskTimer);
    taskTimer = null;
  }
  stopSyslogTimer();

  loadedEnterpriseTaskId.value = taskId.value;
  taskName.value = route.query?.name || '';
  taskTarget.value = route.query?.target || '';
  taskType.value = route.query?.task_type || 'icp';
  taskStatus.value = '';
  taskRecord.value = {};
  selectedWebRowKeys.value = [];
  selectedWebDomains.value = [];
  assetList.value = [];
  syncEnterpriseQueryCounts(route.query);

  const allowed = getAvailableTabs(taskType.value);
  if (!allowed.includes(activeTab.value)) {
    activeTab.value = 'web';
  }

  if (taskId.value) {
    if (activeTab.value === 'log') {
      startSyslogTimer();
    } else {
      resetTabSort(activeTab.value);
      fetchAssets(1, pagination.pageSize);
    }
    fetchTaskStatistic();
    taskTimer = setInterval(fetchTaskStatistic, 5000);
  }
};

watch(taskId, () => {
  if (!route.path.startsWith('/taskList/taskDetail')) return;
  const t = route.query?.task_type;
  if (t !== 'tyc' && t !== 'icp') return;
  reloadEnterpriseTaskData();
});

watch(() => route.query?.tab, (newTab) => {
  if (!route.path.startsWith('/taskList/taskDetail')) return;
  const allowed = getAvailableTabs(taskType.value);
  if (newTab && allowed.includes(newTab) && newTab !== activeTab.value) {
    activeTab.value = newTab;
    onTabChange(newTab);
  }
});

onMounted(() => {
  reloadEnterpriseTaskData();
});

onUnmounted(() => {
  stopSyslogTimer();
  if (taskTimer) {
    clearInterval(taskTimer);
    taskTimer = null;
  }
});

onDeactivated(() => {
  stopSyslogTimer();
  if (taskTimer) {
    clearInterval(taskTimer);
    taskTimer = null;
  }
  syncModalVisible.value = false;
  rawDetailVisible.value = false;
});

onActivated(() => {
  const t = route.query?.task_type;
  if (t !== 'tyc' && t !== 'icp') return;
  if (loadedEnterpriseTaskId.value !== taskId.value) {
    reloadEnterpriseTaskData();
  } else if (taskId.value) {
    fetchTaskStatistic();
    const isTerminal = ['done', 'error', 'stop'].includes(taskStatus.value);
    if (!taskTimer && !isTerminal) {
      taskTimer = setInterval(fetchTaskStatistic, 5000);
    }
    if (activeTab.value === 'log') {
      if (!syslogTimer && !isTerminal) {
        startSyslogTimer();
      } else if (syslogList.value.length === 0) {
        fetchSyslog();
      }
    }
  }
});
</script>

<style scoped>
.enterprise-detail-tabs :deep(.ant-tabs-nav) { margin-bottom: 10px; }
.enterprise-detail-tabs.is-log-tab :deep(.ant-tabs-nav) { margin-bottom: 0; }
.task-log-hint { color: rgba(255,255,255,0.65); font-style: italic; }
.task-log-empty { color: rgba(255,255,255,0.45); font-style: italic; }
</style>
