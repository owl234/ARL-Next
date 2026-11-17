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

        <div class="arl-hero-right" style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          <a-popconfirm
            v-if="['stop', 'error'].includes(taskStatus) && taskRecord.has_checkpoint"
            :title="taskText('tasks.resumeFromCheckpointConfirm')"
            :ok-text="taskText('tasks.resumeFromCheckpointBtn')"
            :cancel-text="taskText('tasks.cancel')"
            @confirm="handleResumeCheckpoint"
          >
            <a-button type="primary" ghost size="small" :loading="resumeLoading">
              <template #icon><play-circle-outlined /></template>
              {{ taskText('tasks.resumeFromCheckpointBtn') }}
            </a-button>
          </a-popconfirm>
          <a-popconfirm
            v-if="['done', 'stop', 'error'].includes(taskStatus) && (taskRecord.missing_detail_cnt > 0 || taskRecord.detail_backfill_running)"
            :title="taskText('tasks.backfillDetailsConfirm', { count: taskRecord.missing_detail_cnt || 0 })"
            :ok-text="taskText('tasks.backfillDetailsBtn')"
            :cancel-text="taskText('tasks.cancel')"
            :disabled="backfillLoading || !!taskRecord.detail_backfill_running"
            @confirm="handleBackfillDetails"
          >
            <a-button size="small" :loading="backfillLoading || !!taskRecord.detail_backfill_running" :disabled="backfillLoading || !!taskRecord.detail_backfill_running">
              <template #icon><sync-outlined :spin="backfillLoading || !!taskRecord.detail_backfill_running" /></template>
              {{ taskRecord.detail_backfill_running ? taskText('tasks.backfillDetailsRunning') : taskText('tasks.backfillDetailsCountBtn', { count: taskRecord.missing_detail_cnt || 0 }) }}
            </a-button>
          </a-popconfirm>
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
            <img v-if="getOsintIcon(record)" :src="getOsintIcon(record)" style="width:32px;height:32px;border-radius:4px;" />
            <span v-else>-</span>
          </template>
          <template v-else-if="column.key === 'domain'">
            <a v-if="getOsintDomain(record)" :href="getOsintDomain(record).startsWith('http') ? getOsintDomain(record) : ('http://' + getOsintDomain(record))" target="_blank" rel="noopener noreferrer" style="color: var(--arl-theme-color); word-break: break-all;">
              {{ getOsintDomain(record) }}
            </a>
            <span v-else>-</span>
          </template>
          <template v-else-if="column.key === 'homeUrl'">
            <a v-if="getOsintHomeUrl(record)" :href="getOsintHomeUrl(record)" target="_blank" rel="noopener noreferrer" style="color: var(--arl-theme-color); word-break: break-all;">
              {{ getOsintHomeUrl(record) }}
            </a>
            <span v-else>-</span>
          </template>
          <template v-else-if="column.key === 'href'">
            <a v-if="record.href || record.homeUrl" :href="record.href || record.homeUrl" target="_blank" rel="noopener noreferrer" style="color: var(--arl-theme-color);">
              {{ taskText('assets.openWeibo') }} <export-outlined style="font-size: 11px;" />
            </a>
            <span v-else>-</span>
          </template>
          <template v-else-if="column.key === 'qrcode'">
            <a-popover v-if="record.codeImg" placement="right" trigger="hover">
              <template #content>
                <div style="text-align: center; padding: 4px;">
                  <img :src="record.codeImg" style="width: 150px; height: 150px; display: block;" />
                  <span style="font-size: 12px; color: #8c8c8c; margin-top: 4px; display: block;">{{ taskText('assets.scanWithWechatToFollow') }}</span>
                </div>
              </template>
              <a-tag color="blue" style="cursor: pointer;"><qrcode-outlined /> {{ taskText('assets.viewQrCode') }}</a-tag>
            </a-popover>
            <span v-else>-</span>
          </template>
          <template v-else-if="column.key === 'status'">
            <a-tag v-if="['存续', '在业', '正常'].includes(getOsintStatus(record))" color="success">
              {{ getOsintStatus(record) }}
            </a-tag>
            <a-tag v-else-if="['注销', '吊销', '撤销', '迁出'].includes(getOsintStatus(record))" color="error">
              {{ getOsintStatus(record) }}
            </a-tag>
            <a-tag v-else-if="getOsintStatus(record)">
              {{ getOsintStatus(record) }}
            </a-tag>
            <span v-else>-</span>
          </template>
          <template v-else-if="column.key === 'region'">
            {{ getOsintRegion(record) || '-' }}
          </template>
          <template v-else-if="column.key === 'estiblishTime'">
            {{ formatOsintDate(record.estiblishTime) }}
          </template>
          <template v-else-if="column.key === 'companyType'">
            {{ getOsintCompanyType(record) || '-' }}
          </template>
          <template v-else-if="column.key === 'category'">
            {{ getOsintCategory(record) || '-' }}
          </template>
          <template v-else-if="column.key === 'contentTypeName'">
            {{ getOsintContentType(record) || '-' }}
          </template>
          <template v-else-if="column.key === 'wechatId'">
            {{ getOsintWechatId(record) || '-' }}
          </template>
          <template v-else-if="column.key === 'legalPerson'">
            {{ getOsintLegalPerson(record) || '-' }}
          </template>
          <template v-else-if="column.key === 'brief' || column.key === 'recommend'">
            <div style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="getOsintBrief(record) || text">
              {{ getOsintBrief(record) || text || '-' }}
            </div>
          </template>
          <template v-else-if="column.key === 'serviceName' || column.key === 'name'">
            <template v-if="getOsintName(record)">{{ getOsintName(record) }}</template>
            <a-tooltip v-else-if="['app', 'mapp', 'kapp'].includes(activeTab) && record.dataId" :title="taskText('tasks.detailPendingHint')">
              <a-tag color="warning" style="margin-inline-end: 0;">{{ taskText('tasks.detailPendingBadge') }}</a-tag>
            </a-tooltip>
            <span v-else>-</span>
          </template>
          <template v-else-if="column.key === 'serviceLicence' || column.key === 'serviceFilingNumber'">
            {{ getOsintLicence(record) || '-' }}
          </template>
          <template v-else-if="column.key === 'unitName' || column.key === 'companyName'">
            {{ getOsintUnitName(record) || '-' }}
          </template>
          <template v-else-if="column.key === 'mainLicence'">
            {{ getOsintMainLicence(record) || '-' }}
          </template>
          <template v-else-if="column.key === 'updateRecordTime' || column.key === 'examineDate'">
            {{ getOsintUpdateTime(record) || '-' }}
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
import { ArrowLeftOutlined, FilterOutlined, UndoOutlined, SearchOutlined, DownloadOutlined, CloudSyncOutlined, ExportOutlined, PlayCircleOutlined, SyncOutlined, QrcodeOutlined } from '@ant-design/icons-vue';
import SyncToScopeModal from './SyncToScopeModal.vue';
import { message } from 'ant-design-vue';
import request from '../utils/request';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import { useSticky } from '../utils/useSticky';
import { formatTaskStatus, formatTaskStatusColor } from '../constants/taskStatus';
import {
  getOsintDomain,
  getOsintName,
  getOsintUnitName,
  getOsintCompanyType,
  getOsintLicence,
  getOsintMainLicence,
  getOsintUpdateTime,
  getOsintHomeUrl,
  getOsintIcon,
  getOsintBrief,
  getOsintCategory,
  getOsintContentType,
  getOsintWechatId,
  getOsintLegalPerson,
  getOsintStatus,
  getOsintRegion,
  formatOsintDate,
  buildEnterpriseOsintColumns
} from '../utils/enterpriseOsint';

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
const resumeLoading = ref(false);
const backfillLoading = ref(false);
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
  if (['web', 'app', 'mapp', 'kapp'].includes(tab)) {
    return { field: 'updateRecordTime', order: 'descend' };
  }
  return { field: null, order: null };
};

const resetTabSort = (tab) => {
  const def = getDefaultSortForTab(tab);
  sortState.field = def.field;
  sortState.order = def.order;
};

const dynamicColumns = computed(() => {
  return buildEnterpriseOsintColumns(taskText, activeTab.value, assetList.value, {
    includeManagedStatus: false,
    indexWidth: 65,
    rawTitleKey: 'tasks.details',
    rawWidth: 80,
    sortState
  });
});

const allTabFilterColumns = computed(() => {
  return buildEnterpriseOsintColumns(taskText, activeTab.value, assetList.value, {
    includeManagedStatus: false,
    includeAllOptional: true,
    indexWidth: 65,
    rawTitleKey: 'tasks.details',
    rawWidth: 80,
    sortState
  });
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
  (allTabFilterColumns.value || []).filter(
    col => col.dataIndex && !['index', 'raw', 'icon', 'qrcode', 'examineDate', 'updateRecordTime', 'estiblishTime'].includes(col.key)
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
let wasBackfilling = false;

const ensureDetailPolling = () => {
  if (!taskTimer && taskId.value) {
    taskTimer = setInterval(fetchTaskStatistic, 5000);
  }
  if (activeTab.value === 'log' && !syslogTimer) {
    startSyslogTimer();
  }
};

const handleResumeCheckpoint = async () => {
  if (!taskId.value || resumeLoading.value) return;
  resumeLoading.value = true;
  try {
    const res = await request.post(`/icp/resume/${taskId.value}`);
    if (res && res.code === 200) {
      message.success(taskText('tasks.resumeFromCheckpointStarted'));
      taskStatus.value = 'waiting';
      await fetchTaskStatistic();
      ensureDetailPolling();
    } else {
      message.error(res?.data?.error || res?.message || taskText('tasks.resumeFromCheckpointFailed'));
    }
  } catch (err) {
    message.error(taskText('tasks.networkRequestFailed'));
  } finally {
    resumeLoading.value = false;
  }
};

const handleBackfillDetails = async () => {
  if (!taskId.value || backfillLoading.value) return;
  backfillLoading.value = true;
  try {
    const res = await request.post(`/icp/backfill_details/${taskId.value}`, {
      query_types: ['app', 'mapp', 'kapp']
    });
    if (res && res.code === 200) {
      message.success(taskText('tasks.backfillDetailsStarted'));
      taskRecord.value = { ...taskRecord.value, detail_backfill_running: true };
      wasBackfilling = true;
      await fetchTaskStatistic();
      ensureDetailPolling();
    } else {
      message.error(res?.data?.error || res?.message || taskText('tasks.backfillDetailsFailed'));
    }
  } catch (err) {
    message.error(taskText('tasks.networkRequestFailed'));
  } finally {
    backfillLoading.value = false;
  }
};

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
      const isBackfilling = !!taskData.detail_backfill_running;
      if (['done', 'error', 'stop'].includes(currentStatus) && !isBackfilling) {
        if (taskTimer) {
          clearInterval(taskTimer);
          taskTimer = null;
        }
        stopSyslogTimer();
        if (activeTab.value === 'log') {
          fetchSyslog(true);
        } else if ((lastStatus && !['done', 'error', 'stop'].includes(lastStatus)) || wasBackfilling) {
          fetchAssets(pagination.current, pagination.pageSize);
        }
      }
      lastStatus = currentStatus;
      wasBackfilling = isBackfilling;
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
