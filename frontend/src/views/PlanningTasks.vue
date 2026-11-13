<template>
  <div class="arl-page-container">
    <div ref="actionBarRef" class="arl-hero-card">
      <a-tabs v-model:activeKey="activeTab" type="card" class="arl-detail-tabs" style="margin-bottom: 12px;" @change="onTabChange">
        <a-tab-pane key="planning" :tab="taskText('tasks.scheduledScans')"></a-tab-pane>
        <a-tab-pane key="monitor" :tab="taskText('tasks.continuousAssetMonitoring')"></a-tab-pane>
      </a-tabs>

      <!-- 扫描计划任务 操作栏 -->
      <template v-if="activeTab === 'planning'">
        <div class="arl-toolbar-row">
          <!-- 左侧：紧凑搜索条件 -->
          <div class="arl-filter-group">
            <div class="arl-filter-item">
              <span class="arl-filter-label">{{ taskText('tasks.taskNameLabel') }}</span>
              <a-input v-model:value="searchForm.name" :placeholder="taskText('tasks.enterATaskName')" class="task-width-140" allowClear size="small" @pressEnter="onPlanSearch">
                <template #suffix><search-outlined @click="onPlanSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
              </a-input>
            </div>
            <div class="arl-filter-item">
              <span class="arl-filter-label">{{ taskText('tasks.targetLabel') }}</span>
              <a-input v-model:value="searchForm.target" :placeholder="taskText('tasks.enterTargets')" class="task-width-140" allowClear size="small" @pressEnter="onPlanSearch">
                <template #suffix><search-outlined @click="onPlanSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
              </a-input>
            </div>
            <div class="arl-filter-item">
              <span class="arl-filter-label">{{ taskText('tasks.policyLabel') }}</span>
              <a-input v-model:value="searchForm.policy_name" :placeholder="taskText('tasks.enterAPolicy')" class="task-width-130" allowClear size="small" @pressEnter="onPlanSearch">
                <template #suffix><search-outlined @click="onPlanSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
              </a-input>
            </div>
            <div class="arl-filter-item">
              <span class="arl-filter-label">{{ taskText('tasks.scheduleTypeLabel') }}</span>
              <a-select v-model:value="searchForm.schedule_type" :placeholder="taskText('tasks.allTypes')" class="task-width-110" allowClear size="small" @change="onPlanSearch">
                <a-select-option value="future_scan">{{ taskText('tasks.oneTimeTask') }}</a-select-option>
                <a-select-option value="recurrent_scan">{{ taskText('tasks.recurringTask') }}</a-select-option>
              </a-select>
            </div>
            <div class="arl-filter-item">
              <span class="arl-filter-label">{{ taskText('tasks.statusLabel') }}</span>
              <a-select v-model:value="searchForm.schedule_status" :placeholder="taskText('tasks.allStatuses')" class="task-width-110" allowClear size="small" @change="onPlanSearch">
                <a-select-option value="done">{{ taskText('tasks.statusDone') }}</a-select-option>
                <a-select-option value="scheduled">{{ taskText('tasks.statusScheduled') }}</a-select-option>
                <a-select-option value="stop">{{ taskText('tasks.statusStop') }}</a-select-option>
                <a-select-option value="error">{{ taskText('tasks.statusError') }}</a-select-option>
              </a-select>
            </div>

            <a-button size="small" @click="resetPlanSearch">
              <template #icon><undo-outlined /></template>
              {{ taskText('tasks.reset') }}
            </a-button>
          </div>

          <!-- 右侧：单一主要操作 + 批量动作 -->
          <div class="arl-actions-group">
            <a-button type="primary" size="small" @click="openAddModal">
              <template #icon><plus-outlined /></template>
              {{ taskText('tasks.addScheduledTask') }}
            </a-button>

            <a-popconfirm :title="taskText('tasks.stopTheSelectedScheduledTasks')" :ok-text="taskText('tasks.confirm')" :cancel-text="taskText('tasks.cancel')" @confirm="handleBatchStop">
              <a-button size="small" :disabled="!hasPlanSelected">
                <template #icon><pause-circle-outlined /></template>
                {{ taskText('tasks.stopSelected') }}
              </a-button>
            </a-popconfirm>

            <a-button danger size="small" :disabled="!hasPlanSelected" @click="handleBatchDelete">
              <template #icon><delete-outlined /></template>
              {{ taskText('tasks.deleteSelected') }}
            </a-button>
          </div>
        </div>
      </template>

      <!-- 资产持续监控 操作栏 -->
      <template v-else-if="activeTab === 'monitor'">
        <div class="arl-toolbar-row">
          <!-- 左侧：检索条件 -->
          <div class="arl-filter-group">
            <div class="arl-filter-item">
              <span class="arl-filter-label">{{ taskText('tasks.nameLabel') }}</span>
              <a-input v-model:value="monitorSearchForm.name" :placeholder="taskText('tasks.enterAName')" class="task-width-160" allowClear size="small" @pressEnter="onMonitorSearch">
                <template #suffix><search-outlined @click="onMonitorSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
              </a-input>
            </div>
            <div class="arl-filter-item">
              <span class="arl-filter-label">{{ taskText('tasks.domain') }}</span>
              <a-input v-model:value="monitorSearchForm.domain" :placeholder="taskText('tasks.enterADomain')" class="task-width-160" allowClear size="small" @pressEnter="onMonitorSearch">
                <template #suffix><search-outlined @click="onMonitorSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
              </a-input>
            </div>
            <div class="arl-filter-item">
              <span class="arl-filter-label">{{ taskText('tasks.assetScopeIdLabel') }}</span>
              <a-input v-model:value="monitorSearchForm.scope_id" :placeholder="taskText('tasks.enterAScopeId')" class="task-width-160" allowClear size="small" @pressEnter="onMonitorSearch">
                <template #suffix><search-outlined @click="onMonitorSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
              </a-input>
            </div>

            <a-button size="small" @click="resetMonitorSearch">
              <template #icon><undo-outlined /></template>
              {{ taskText('tasks.reset') }}
            </a-button>
          </div>

          <!-- 右侧：批量动作 -->
          <div class="arl-actions-group">
            <a-button size="small" :disabled="!hasMonitorSelected" @click="handleMonitorBatchAction('run')">
              <template #icon><send-outlined /></template>
              {{ taskText('tasks.runSelected') }}
            </a-button>
            <a-button size="small" :disabled="!hasMonitorSelected" @click="handleMonitorBatchAction('recover')">
              <template #icon><play-circle-outlined /></template>
              {{ taskText('tasks.resumeSelected') }}
            </a-button>
            <a-button size="small" :disabled="!hasMonitorSelected" @click="handleMonitorBatchAction('stop')">
              <template #icon><pause-circle-outlined /></template>
              {{ taskText('tasks.stopSelected') }}
            </a-button>
            <a-button danger size="small" :disabled="!hasMonitorSelected" @click="handleMonitorBatchAction('delete')">
              <template #icon><delete-outlined /></template>
              {{ taskText('tasks.deleteSelected') }}
            </a-button>
          </div>
        </div>
      </template>

    </div>

    <!-- 扫描计划任务 表格 -->
    <template v-if="activeTab === 'planning'">
      <a-table :sticky="stickyConfig"
          :row-selection="{ selectedRowKeys: planSelectedRowKeys, onChange: onPlanSelectChange, preserveSelectedRowKeys: true }"
          :loading="loading"
          :dataSource="dataSource"
          :columns="columns"
          :pagination="false"
          size="small"
          :rowKey="(record) => record._id"
      >
        <template #emptyText>
          <ArlEmpty :description="taskText('tasks.noData')" />
        </template>

        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'schedule_type'">
            {{ record.schedule_type === 'future_scan' ? taskText('tasks.oneTimeTask') : taskText('tasks.recurringTask') }}
          </template>

          <template v-else-if="column.key === 'status'">
            <a-tag
                :color="
                record.status === 'scheduled' ? 'blue' :
                record.status === 'stop' ? 'warning' :
                record.status === 'error' ? 'error' :
                'success'
              "
            >
              {{ record.status === 'scheduled' ? taskText('tasks.statusScheduled') : formatTaskStatus(record.status) }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'time_config'">
            {{ record.schedule_type === 'future_scan' ? record.start_date : record.cron }}
          </template>

          <template v-else-if="column.key === 'action'">
            <div style="display: flex; gap: 6px;">
              <a-button
                  size="small"
                  :disabled="record.status === 'stop'"
                  @click="handleSingleAction('stop', record._id)"
              >{{ taskText('tasks.stop') }}</a-button>

              <a-popconfirm :title="taskText('tasks.confirmDeletionLabel')" @confirm="handleSingleAction('delete', record._id)">
                <a-button size="small" danger>{{ taskText('tasks.delete') }}</a-button>
              </a-popconfirm>

              <a-button
                  size="small"
                  :disabled="record.status === 'scheduled'"
                  @click="handleSingleAction('recover', record._id)"
              >{{ taskText('tasks.resume') }}</a-button>
            </div>
          </template>
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">{{ taskText('tasks.paginationSummary', { pages: Math.ceil(pagination.total / pagination.pageSize) || 1, total: pagination.total }) }}</div>
        <a-pagination
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="pagination.current"
          v-model:pageSize="pagination.pageSize"
          :total="pagination.total"
          show-size-changer
          size="small"
          @change="handlePlanTableChange"
          @showSizeChange="handlePlanTableChange"
        />
      </div>
    </template>

    <!-- 资产持续监控 表格 -->
    <template v-else-if="activeTab === 'monitor'">
      <a-table :sticky="stickyConfig"
          :row-selection="{ selectedRowKeys: monitorSelectedRowKeys, onChange: onMonitorSelectChange, preserveSelectedRowKeys: true }"
          :loading="monitorLoading"
          :dataSource="monitorDataSource"
          :columns="monitorColumns"
          :pagination="false"
          size="small"
          :rowKey="(record) => record._id"
      >
        <template #emptyText>
          <ArlEmpty :description="taskText('tasks.noData')" />
        </template>

        <template #bodyCell="{ column, record, index }">
          <template v-if="column.key === 'index'">
            {{ (monitorPagination.current - 1) * monitorPagination.pageSize + index + 1 }}
          </template>

          <template v-if="column.key === 'scope_id'">
            <a
                style="cursor: pointer;"
                @click="goToAssetScope(record.scope_id)"
            >
              {{ record.scope_id }}
            </a>
          </template>

          <template v-else-if="column.key === 'interval'">
            <span>{{ formatInterval(record.interval) }}</span>
          </template>

          <template v-else-if="column.key === 'run_number'">
            <a style="cursor: pointer;">{{ record.run_number }}</a>
          </template>

          <template v-else-if="column.key === 'action'">
            <div style="display: flex; gap: 6px;">
              <a-button size="small" :disabled="record.status === 'stop'" @click="handleMonitorSingleAction('stop', record)">{{ taskText('tasks.pause') }}</a-button>
              <a-button size="small" :disabled="record.status !== 'stop'" @click="handleMonitorSingleAction('resume', record)">{{ taskText('tasks.resume') }}</a-button>
              <a-button size="small" @click="handleMonitorSingleAction('run', record)">{{ taskText('tasks.runTaskNow') }}</a-button>
              <a-button size="small" danger @click="handleMonitorSingleAction('delete', record)">{{ taskText('tasks.delete') }}</a-button>
            </div>
          </template>
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">{{ taskText('tasks.paginationSummary', { pages: Math.ceil(monitorPagination.total / monitorPagination.pageSize) || 1, total: monitorPagination.total }) }}</div>
        <a-pagination
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="monitorPagination.current"
          v-model:pageSize="monitorPagination.pageSize"
          :total="monitorPagination.total"
          show-size-changer
          size="small"
          @change="handleMonitorTableChange"
          @showSizeChange="handleMonitorTableChange"
        />
      </div>
    </template>

    <a-modal
        v-model:open="addModalVisible"
        :title="taskText('tasks.addScheduledTask')"
        @ok="submitAdd"
        :confirmLoading="addLoading"
        width="520px"
        :okText="taskText('tasks.confirm')"
        :cancelText="taskText('tasks.cancel')"
        destroyOnClose
    >
      <a-form
        :label-wrap="true"
        ref="addFormRef"
        :model="addForm"
        :rules="addRules"
        :label-col="{ span: taskLocale !== 'zh-CN' ? 7 : 5 }"
        :wrapper-col="{ span: taskLocale !== 'zh-CN' ? 16 : 18 }"
        style="margin-top: 20px;"
      >
        <a-form-item :label="taskText('tasks.name')" name="name">
          <a-input v-model:value="addForm.name" :placeholder="taskText('tasks.enterAName')" />
        </a-form-item>
        <a-form-item
          :label="taskText('tasks.target')"
          name="target"
          :extra="taskText('tasks.enterDomainsIpsOrCidrRangesSeparatedBy')"
        >
          <a-textarea v-model:value="addForm.target" :rows="3" :placeholder="taskText('tasks.enterTargets')" />
        </a-form-item>

        <a-form-item :label="taskText('tasks.scheduleType')" name="schedule_type">
          <a-select v-model:value="addForm.schedule_type" @change="onScheduleTypeChange">
            <a-select-option value="future_scan">{{ taskText('tasks.oneTimeTask') }}</a-select-option>
            <a-select-option value="recurrent_scan">{{ taskText('tasks.recurringTask') }}</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item :label="taskText('tasks.policy')" name="policy_id">
          <a-select
            v-model:value="addForm.policy_id"
            :placeholder="taskText('tasks.selectAPolicy')"
            show-search
            option-filter-prop="label"
          >
            <a-select-option v-for="p in policyList" :key="p._id" :value="p._id">
              {{ p.name }} (PoC : {{ p.policy?.poc_config?.length || 0 }})
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item v-if="addForm.schedule_type === 'future_scan'" :label="taskText('tasks.startTime')" name="start_date">
          <a-date-picker
              v-model:value="addForm.start_date"
              show-time
              :disabled-date="disablePastDate"
              valueFormat="YYYY-MM-DD HH:mm:ss"
              style="width: 100%"
              :placeholder="taskText('tasks.selectAStartDate')"
          />
        </a-form-item>

        <a-form-item
          v-if="addForm.schedule_type === 'recurrent_scan'"
          label="Cron"
          name="cron"
          :extra="taskText('tasks.standardFiveFieldCronMinuteHourDayMonth')"
        >
          <a-input v-model:value="addForm.cron" :placeholder="taskText('tasks.enterCronEG001')" />
        </a-form-item>

        <a-form-item
          :label="taskText('tasks.taskCategory')"
          name="task_tag"
          :extra="taskText('tasks.assetDiscoveryParsesDomainAndIpTargetsTo')"
        >
          <a-select v-model:value="addForm.task_tag" :placeholder="taskText('tasks.selectATaskCategory')">
            <a-select-option value="task">{{ taskText('tasks.assetDiscoveryTasks') }}</a-select-option>
            <a-select-option value="risk_cruising">{{ taskText('tasks.riskScanningTask') }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';
import { formatTaskStatus } from '../constants/taskStatus';

defineOptions({ name: 'PlanningTasks' });

import { ref, reactive, onMounted, onDeactivated, computed, watch, createVNode } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useSticky } from '../utils/useSticky';
import request from '../utils/request';
import { message, Modal } from 'ant-design-vue';
import { SearchOutlined, ExclamationCircleOutlined, PlusOutlined, DeleteOutlined, UndoOutlined, PauseCircleOutlined, PlayCircleOutlined, SendOutlined } from '@ant-design/icons-vue';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import dayjs from 'dayjs';

const { t: taskText, locale: taskLocale } = useI18n({ useScope: 'global' });

const route = useRoute();
const router = useRouter();

const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

const activeTab = ref(route.query.tab === 'monitor' ? 'monitor' : 'planning');

const onTabChange = (key) => {
  router.replace({
    query: { ...route.query, tab: key }
  });
  if (key === 'monitor' && monitorDataSource.value.length === 0) {
    fetchMonitorData();
  } else if (key === 'planning' && dataSource.value.length === 0) {
    fetchPlanData();
  }
};

watch(() => route.query.tab, (newTab) => {
  if (newTab === 'monitor' && activeTab.value !== 'monitor') {
    activeTab.value = 'monitor';
    if (monitorDataSource.value.length === 0) {
      fetchMonitorData();
    }
  } else if (newTab === 'planning' && activeTab.value !== 'planning') {
    activeTab.value = 'planning';
    if (dataSource.value.length === 0) {
      fetchPlanData();
    }
  }
});

// ================= 全局分页共享 =================
const globalPageSize = useGlobalPageSize(10);

// ==========================================
// 1. 扫描计划任务逻辑
// ==========================================
const loading = ref(false);
const dataSource = ref([]);
const policyList = ref([]);
const searchForm = reactive({ name: '', target: '', policy_name: '', schedule_type: undefined, schedule_status: undefined });
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

const planSelectedRowKeys = ref([]);
const hasPlanSelected = computed(() => planSelectedRowKeys.value.length > 0);
const onPlanSelectChange = (keys) => { planSelectedRowKeys.value = keys; };

const columns = [
  { get title() { return taskText('tasks.taskName'); }, dataIndex: 'name', key: 'name', width: 150 },
  { get title() { return taskText('tasks.target'); }, dataIndex: 'target', key: 'target', width: 150 },
  { get title() { return taskText('tasks.type'); }, dataIndex: 'schedule_type', key: 'schedule_type', width: 100 },
  { get title() { return taskText('tasks.status'); }, dataIndex: 'status', key: 'status', width: 100 },
  { get title() { return taskText('tasks.policy'); }, dataIndex: 'policy_name', key: 'policy_name', width: 120 },
  { get title() { return taskText('tasks.schedule'); }, key: 'time_config', width: 180 },
  { get title() { return taskText('tasks.lastRun'); }, dataIndex: 'last_run_date', key: 'last_run_date', width: 180 },
  { get title() { return taskText('tasks.nextRun'); }, dataIndex: 'next_run_date', key: 'next_run_date', width: 180 },
  { get title() { return taskText('tasks.runCount'); }, dataIndex: 'run_number', key: 'run_number', width: 100 },
  { get title() { return taskText('tasks.actions'); }, key: 'action', width: 200 }
];

const fetchPlanData = async () => {
  loading.value = true;
  try {
    const params = { page: pagination.current, size: pagination.pageSize };
    if (searchForm.name) params.name = searchForm.name;
    if (searchForm.target) params.target = searchForm.target;
    if (searchForm.policy_name) params.policy_name = searchForm.policy_name;
    if (searchForm.schedule_type) params.schedule_type = searchForm.schedule_type;
    if (searchForm.schedule_status) params.schedule_status = searchForm.schedule_status;

    const res = await request.get('/task_schedule/', { params });
    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
      planSelectedRowKeys.value = [];
    }
  } catch (error) {
    message.error(taskText('tasks.failedToLoadScheduledTasks'));
  } finally {
    loading.value = false;
  }
};

const fetchPolicyList = async () => {
  const res = await request.get('/policy/', { params: { size: 1000, order: '-update_date' } });
  if (res.code === 200) policyList.value = res.items || [];
};

const resetPlanSearch = () => {
  Object.assign(searchForm, { name: '', target: '', policy_name: '', schedule_type: undefined, schedule_status: undefined });
  pagination.current = 1;
  onPlanSearch();
};

const onPlanSearch = () => { pagination.current = 1; fetchPlanData(); };
const handlePlanTableChange = (page, pageSize) => { pagination.current = page; pagination.pageSize = pageSize; fetchPlanData(); };

// 添加计划任务弹窗
const addModalVisible = ref(false);
const addLoading = ref(false);
const addFormRef = ref();
const addForm = reactive({
  name: '', target: '', schedule_type: 'future_scan',
  policy_id: undefined, task_tag: undefined,
  start_date: '', cron: ''
});

// 5 段 Cron 最小校验：分 时 日 月 周，允许 */n、a-b、a,b 与 * 形式
const CRON_SEGMENT_RE = /^(\*|\d+|\*\/\d+|\d+-\d+|\d+(,\d+)*)$/;

const isValidCron = (value) => {
  const segments = String(value || '').trim().split(/\s+/);
  if (segments.length !== 5) return false;
  return segments.every((seg) => {
    if (!CRON_SEGMENT_RE.test(seg)) return false;
    if (/^\d+$/.test(seg)) {
      const num = Number(seg);
      return num <= 59;
    }
    return true;
  });
};

// 与后端 FutureDateInvalid 校验对齐：禁止选择过去的时间
const disablePastDate = (current) => current && current < dayjs().startOf('day');

const addRules = {
  name: [{ required: true, get message() { return taskText('tasks.enterAName'); } }],
  target: [{ required: true, get message() { return taskText('tasks.enterTargets'); } }],
  schedule_type: [{ required: true, get message() { return taskText('tasks.selectAScheduleType'); } }],
  policy_id: [{ required: true, get message() { return taskText('tasks.selectAPolicy'); } }],
  task_tag: [{ required: true, get message() { return taskText('tasks.selectATaskCategory'); } }],
  start_date: [{ required: true, get message() { return taskText('tasks.selectAStartTime'); } }],
  cron: [
    { required: true, get message() { return taskText('tasks.enterACronExpression'); } },
    {
      validator: (_rule, value) => {
        if (!value || isValidCron(value)) return Promise.resolve();
        return Promise.reject(taskText('tasks.invalidCronUseFiveFieldsEG0'));
      }
    }
  ]
};

const openAddModal = () => {
  Object.assign(addForm, {
    name: '', target: '', schedule_type: 'future_scan',
    policy_id: undefined, task_tag: undefined, start_date: '', cron: ''
  });
  addModalVisible.value = true;
};

// 切换计划类型时清空不适用的排期字段；若原本已填写则提示用户，避免静默丢失
const onScheduleTypeChange = () => {
  const hadValue = !!addForm.start_date || !!addForm.cron;
  addForm.start_date = '';
  addForm.cron = '';
  // 清空后消除上一类型遗留的字段级校验态
  addFormRef.value?.clearValidate(['start_date', 'cron']);
  if (hadValue) {
    message.info(taskText('tasks.scheduleTypeChangedPleaseEnterTheScheduleAgain'));
  }
};

const submitAdd = async () => {
  try {
    await addFormRef.value.validate();
  } catch (error) {
    // 交由 antd 展示字段级错误提示
    return;
  }

  const payload = {
    name: addForm.name,
    target: addForm.target,
    schedule_type: addForm.schedule_type,
    policy_id: addForm.policy_id,
    task_tag: addForm.task_tag
  };

  if (addForm.schedule_type === 'future_scan') {
    payload.start_date = addForm.start_date;
  } else {
    payload.cron = addForm.cron;
  }

  addLoading.value = true;
  try {
    const res = await request.post('/task_schedule/', payload);
    if (res.code === 200) {
      message.success(taskText('tasks.scheduledTaskCreated'));
      addModalVisible.value = false;
      onPlanSearch();
    } else {
      message.error(res.message || taskText('tasks.failedToCreateTask'));
    }
  } catch (error) {
    message.error(taskText('tasks.requestFailedTaskWasNotCreated'));
  } finally {
    addLoading.value = false;
  }
};

const performPlanAction = async (actionType, idArray) => {
  try {
    const url = `/task_schedule/${actionType}/`;
    const res = await request.post(url, { _id: idArray });
    if (res.code === 200) {
      message.success(taskText('tasks.operationCompleted'));
      fetchPlanData();
    } else {
      message.error(res.message || taskText('tasks.operationFailedLabel'));
    }
  } catch (e) {
    message.error(taskText('tasks.requestFailed'));
  }
};

const handleSingleAction = (type, id) => performPlanAction(type, [id]);
const handleBatchStop = () => performPlanAction('stop', planSelectedRowKeys.value);

// 批量删除为不可逆操作：确认框必须列出待删除对象清单，避免用户只看到数量无法复核范围
const handleBatchDelete = () => {
  const selectedIds = planSelectedRowKeys.value;
  if (selectedIds.length === 0) return;

  const names = (dataSource.value || [])
    .filter(item => selectedIds.includes(item._id))
    .map(item => item.name || item._id);

  const preview = names.slice(0, 10).map(n => `· ${n}`).join('\n');
  const more = names.length > 10 ? taskText('tasks.andCountMore', { count: names.length - 10 }) : '';

  Modal.confirm({
    title: taskText('tasks.deleteSelectedScheduledTasksCount', { count: selectedIds.length }),
    icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
    content: taskText('tasks.theseScheduledTasksAndTheirSchedulingConfigurationWill', { names: preview, more: more }),
    okText: taskText('tasks.confirmDeletionCount', { count: selectedIds.length }),
    okButtonProps: { danger: true },
    cancelText: taskText('tasks.cancel'),
    onOk: () => performPlanAction('delete', selectedIds)
  });
};


// ==========================================
// 2. 资产持续监控逻辑
// ==========================================
const monitorLoading = ref(false);
const monitorDataSource = ref([]);
const monitorSearchForm = ref({});
const monitorPagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

const monitorSelectedRowKeys = ref([]);
const hasMonitorSelected = computed(() => monitorSelectedRowKeys.value.length > 0);
const onMonitorSelectChange = (keys) => { monitorSelectedRowKeys.value = keys; };

const monitorColumns = [
  { get title() { return taskText('tasks.no'); }, key: 'index', width: 80, align: 'center' },
  { get title() { return taskText('tasks.name'); }, dataIndex: 'name', key: 'name', width: 200 },
  { get title() { return taskText('tasks.domains'); }, dataIndex: 'domain', key: 'domain', width: 180 },
  { get title() { return taskText('tasks.assetScopeId'); }, key: 'scope_id', width: 220 },
  { get title() { return taskText('tasks.runInterval'); }, key: 'interval', width: 120 },
  { get title() { return taskText('tasks.lastRunDate'); }, dataIndex: 'last_run_date', key: 'last_run_date', width: 180 },
  { get title() { return taskText('tasks.nextRunDate'); }, dataIndex: 'next_run_date', key: 'next_run_date', width: 180 },
  { get title() { return taskText('tasks.runCount'); }, key: 'run_number', width: 100, align: 'center' },
  { get title() { return taskText('tasks.actions'); }, key: 'action', width: 260 }
];

const goToAssetScope = (id) => {
  if (!id) return;
  router.push({
    path: '/group',
    query: { scope_id: id }
  });
};

const formatInterval = (seconds) => {
  if (!seconds) return '-';
  if (seconds >= 3600 && seconds % 3600 === 0) return taskText('tasks.countHours', { count: seconds / 3600 });
  if (seconds >= 60 && seconds % 60 === 0) return taskText('tasks.countMinutes', { count: seconds / 60 });
  return taskText('tasks.countSeconds', { count: seconds });
};

const fetchMonitorData = async () => {
  monitorLoading.value = true;
  try {
    const params = { page: monitorPagination.current, size: monitorPagination.pageSize };
    for (const key in monitorSearchForm.value) {
      if (monitorSearchForm.value[key]) params[key] = monitorSearchForm.value[key];
    }
    const res = await request.get('/scheduler/', { params });
    if (res.code === 200) {
      monitorDataSource.value = res.items || [];
      monitorPagination.total = res.total || 0;
      monitorSelectedRowKeys.value = [];
    }
  } catch (error) {
    message.error(taskText('tasks.failedToLoadAssetMonitors'));
  } finally {
    monitorLoading.value = false;
  }
};

const resetMonitorSearch = () => {
  monitorSearchForm.value = {};
  monitorPagination.current = 1;
  onMonitorSearch();
};

const onMonitorSearch = () => { monitorPagination.current = 1; fetchMonitorData(); };
const handleMonitorTableChange = (page, pageSize) => { monitorPagination.current = page; monitorPagination.pageSize = pageSize; fetchMonitorData(); };

const monitorApiMap = {
  delete: '/scheduler/delete/',
  stop: '/scheduler/stop/',
  resume: '/scheduler/recover/',
  run: '/scheduler/run/'
};

const executeMonitorAction = async (actionType, ids) => {
  const url = monitorApiMap[actionType];
  if (!url) return;

  try {
    let payload = {};
    if (actionType === 'delete') {
      payload = { scheduler_id: ids };
    } else {
      payload = { scheduler_id: ids[0] };
    }
    const res = await request.post(url, payload);
    if (res.code === 200) {
      message.success(taskText('tasks.operationCompleted'));
      fetchMonitorData();
    } else {
      message.error(taskText('tasks.operationFailed') + res.message);
    }
  } catch (error) {
    message.error(taskText('tasks.networkRequestFailed'));
  }
};

const handleMonitorSingleAction = (actionType, record) => {
  const actionName = actionType === 'delete' ? taskText('tasks.delete') : actionType === 'stop' ? taskText('tasks.pause') : actionType === 'resume' ? taskText('tasks.resume') : taskText('tasks.run');
  if (actionType === 'delete' || actionType === 'run') {
    Modal.confirm({
      title: actionType === 'delete' ? taskText('tasks.deleteMonitoringTask') : taskText('tasks.runMonitoringTask'),
      icon: createVNode(ExclamationCircleOutlined, actionType === 'delete' ? { style: 'color: #ff4d4f;' } : undefined),
      content: actionType === 'delete'
        ? taskText('tasks.deleteMonitoringTaskNameItsSchedulingConfigurationWill', { name: record.name })
        : taskText('tasks.runMonitoringTaskNameNowItWillBe', { name: record.name }),
      okText: actionType === 'delete' ? taskText('tasks.confirmDeletion') : taskText('tasks.confirm'),
      okButtonProps: actionType === 'delete' ? { danger: true } : undefined,
      cancelText: taskText('tasks.cancel'),
      onOk: () => executeMonitorAction(actionType, [record._id])
    });
  } else {
    executeMonitorAction(actionType, [record._id]);
  }
};

const handleMonitorBatchAction = (action) => {
  const actionMap = {
    delete:  { title: taskText('tasks.deleteSelected'), text: taskText('tasks.delete'), url: '/scheduler/delete/', type: 'danger' },
    stop:    { title: taskText('tasks.stopSelected'), text: taskText('tasks.stop'), url: '/scheduler/stop/batch', type: 'danger' },
    recover: { title: taskText('tasks.resumeSelected'), text: taskText('tasks.resume'), url: '/scheduler/recover/batch', type: 'primary' },
    run:     { title: taskText('tasks.runSelected'), text: taskText('tasks.run'), url: '/scheduler/run/batch', type: 'primary' }
  };

  const current = actionMap[action];
  if (!current) return;

  Modal.confirm({
    title: taskText('tasks.confirmAction', { action: current.title }),
    icon: createVNode(ExclamationCircleOutlined),
    content: taskText('tasks.applyActionToTheSelectedTasksCount', { count: monitorSelectedRowKeys.value.length, action: current.text }),
    okText: taskText('tasks.confirm'),
    okType: current.type,
    cancelText: taskText('tasks.cancel'),
    onOk: async () => {
      try {
        const res = await request.post(current.url, {
          scheduler_id: monitorSelectedRowKeys.value
        });

        if (res.code === 200) {
          message.success(taskText('tasks.batchOperationCompletedAction', { action: current.text }));
          if (action === 'delete' && monitorDataSource.value.length === monitorSelectedRowKeys.value.length && monitorPagination.current > 1) {
            monitorPagination.current -= 1;
          }
          monitorSelectedRowKeys.value = [];
          fetchMonitorData();
        } else {
          message.error(taskText('tasks.actionFailed', { action: current.text }) + res.message);
        }
      } catch (error) {
        message.error(taskText('tasks.requestFailedCouldNotAction', { action: current.text }));
      }
    }
  });
};

// ================= 监听与生命周期 =================
watch(() => pagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});
watch(() => monitorPagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});
watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
  monitorPagination.pageSize = newSize;
});

onMounted(() => {
  if (activeTab.value === 'monitor') {
    fetchMonitorData();
  } else {
    fetchPlanData();
  }
  fetchPolicyList();
});

onDeactivated(() => {
  addModalVisible.value = false;
});
</script>
<style scoped>
.task-width-140 { width: 140px; }
.task-width-130 { width: 130px; }
.task-width-110 { width: 110px; }
.task-width-160 { width: 160px; }
</style>
