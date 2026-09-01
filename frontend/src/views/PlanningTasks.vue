<template>
  <div style="background-color: var(--arl-bg-layout); padding: 24px; min-height: calc(100vh - 64px);">
    <div ref="actionBarRef" style="position: sticky; top: 0px; z-index: 10; background-color: var(--arl-bg-layout); margin: -24px -24px 16px -24px; padding: 24px 24px 16px 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">


    <div style="margin-bottom: 20px;">
      <a-button type="primary" @click="openAddModal">添加计划任务</a-button>
    </div>

    <div class="search-row" style="margin-bottom: 16px; ">
      <div class="search-item">
        <span class="label">任务名称：</span>
        <a-input v-model:value="searchForm.name" placeholder="请输入任务名称搜索" style="width: 160px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
        </a-input>
      </div>
      <div class="search-item">
        <span class="label">目标：</span>
        <a-input v-model:value="searchForm.target" placeholder="请输入目标搜索" style="width: 160px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
        </a-input>
      </div>
      <div class="search-item">
        <span class="label">策略名称：</span>
        <a-input v-model:value="searchForm.policy_name" placeholder="请输入策略搜索" style="width: 160px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
        </a-input>
      </div>
      <div class="search-item">
        <span class="label">计划类型：</span>
        <a-select v-model:value="searchForm.schedule_type" placeholder="选择计划类型" style="width: 160px;" allowClear @change="onSearch">
          <a-select-option value="future_scan">定时任务</a-select-option>
          <a-select-option value="recurrent_scan">周期任务</a-select-option>
        </a-select>
      </div>
      <div class="search-item">
        <span class="label">状态：</span>
        <a-select v-model:value="searchForm.schedule_status" placeholder="请选择状态进行搜索" style="width: 180px;" allowClear @change="onSearch">
          <a-select-option value="done">done</a-select-option>
          <a-select-option value="scheduled">scheduled</a-select-option>
          <a-select-option value="stop">stop</a-select-option>
          <a-select-option value="error">error</a-select-option>
        </a-select>
      </div>
    </div>

    <div style="margin-bottom: 16px; display: flex; gap: 8px;">
      <a-button @click="resetSearch">清 除</a-button>
      <a-popconfirm title="确认删除所选数据吗？" @confirm="handleBatchDelete">
        <a-button :disabled="!hasSelected">批量删除</a-button>
      </a-popconfirm>
      <a-popconfirm title="确认停止所选数据吗？" @confirm="handleBatchStop">
        <a-button :disabled="!hasSelected">批量停止</a-button>
      </a-popconfirm>
    </div>

    
    </div>
<a-table :sticky="stickyConfig"
        :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }"
        :loading="loading"
        :dataSource="dataSource"
        :columns="columns"
        :pagination="false"
        size="middle"
        :rowKey="(record) => record._id"
    >
      <template #emptyText>
        <div style="padding: 40px 0;">
          <inbox-outlined style="font-size: 48px; color: var(--arl-border-color);" />
          <div style="color: var(--arl-text-color); opacity: 0.45; margin-top: 8px;">暂无数据</div>
        </div>
      </template>

      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'schedule_type'">
          {{ record.schedule_type === 'future_scan' ? '定时任务' : '周期任务' }}
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
            {{ record.status }}
          </a-tag>
        </template>

        <template v-else-if="column.key === 'time_config'">
          {{ record.schedule_type === 'future_scan' ? record.start_date : record.cron }}
        </template>

        <template v-else-if="column.key === 'action'">
          <a-button
              size="small"
              style="margin-right: 8px;"
              :disabled="record.status === 'stop'"
              @click="handleSingleAction('stop', record._id)"
          >停止</a-button>

          <a-popconfirm title="确认删除？" @confirm="handleSingleAction('delete', record._id)">
            <a-button size="small" style="margin-right: 8px;">删除</a-button>
          </a-popconfirm>

          <a-button
              size="small"
              :disabled="record.status === 'scheduled'"
              @click="handleSingleAction('recover', record._id)"
          >恢复</a-button>
        </template>
      </template>
    </a-table>

    <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
      <div style="color: var(--arl-text-color); opacity: 0.65;">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
      <a-pagination :pageSizeOptions="$pageSizeOptions" v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" />
    </div>

    <a-modal
        v-model:open="addModalVisible"
        title="添加计划任务"
        @ok="submitAdd"
        :confirmLoading="addLoading"
        width="520px"
        okText="确定"
        cancelText="取消"
        destroyOnClose
    >
      <a-form :model="addForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">
        <a-form-item label="名称" required>
          <a-input v-model:value="addForm.name" placeholder="请输入名称" />
        </a-form-item>
        <a-form-item label="目标" required>
          <a-textarea v-model:value="addForm.target" :rows="3" placeholder="请输入目标" />
        </a-form-item>

        <a-form-item label="计划类型" required>
          <a-select v-model:value="addForm.schedule_type" @change="onScheduleTypeChange">
            <a-select-option value="future_scan">定时任务</a-select-option>
            <a-select-option value="recurrent_scan">周期任务</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="策略" required>
          <a-select v-model:value="addForm.policy_id" placeholder="请选择策略">
            <a-select-option v-for="p in policyList" :key="p._id" :value="p._id">{{ p.name }}</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item v-if="addForm.schedule_type === 'future_scan'" label="开始时间" required>
          <a-date-picker
              v-model:value="addForm.start_date"
              show-time
              valueFormat="YYYY-MM-DD HH:mm:ss"
              style="width: 100%"
              placeholder="请选择开始日期"
          />
        </a-form-item>

        <a-form-item v-if="addForm.schedule_type === 'recurrent_scan'" label="Cron" required>
          <a-input v-model:value="addForm.cron" placeholder="请输入Cron，如 0 0 */1 * *" />
        </a-form-item>

        <a-form-item label="任务类别" required>
          <a-select v-model:value="addForm.task_tag" placeholder="请选择任务类别">
            <a-select-option value="task">资产侦查任务</a-select-option>
            <a-select-option value="risk_cruising">风险巡航任务</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

  </div>
</template>

<script setup>

import { ref, reactive, onMounted, computed, watch } from 'vue';
import { useSticky } from '../utils/useSticky';
const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

import request from '../utils/request';
import { message } from 'ant-design-vue';
import { SearchOutlined, InboxOutlined } from '@ant-design/icons-vue';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';

const loading = ref(false);
const dataSource = ref([]);
const policyList = ref([]);

// 搜索与分页
const searchForm = reactive({ name: '', target: '', policy_name: '', schedule_type: undefined, schedule_status: undefined });
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

watch(() => pagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});

watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
});

// 表格多选
const selectedRowKeys = ref([]);
const hasSelected = computed(() => selectedRowKeys.value.length > 0);
const onSelectChange = (keys) => { selectedRowKeys.value = keys; };

// 真实表头配置
const columns = [
  { title: '任务名', dataIndex: 'name', key: 'name', width: 150 },
  { title: '目标', dataIndex: 'target', key: 'target', width: 150 },
  { title: '类型', dataIndex: 'schedule_type', key: 'schedule_type', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '策略', dataIndex: 'policy_name', key: 'policy_name', width: 120 },
  { title: '时间配置', key: 'time_config', width: 180 },
  { title: '上次运行时间', dataIndex: 'last_run_date', key: 'last_run_date', width: 180 },
  { title: '下次运行时间', dataIndex: 'next_run_date', key: 'next_run_date', width: 180 },
  { title: '运行次数', dataIndex: 'run_number', key: 'run_number', width: 100 },
  { title: '操作', key: 'action', width: 200 }
];

// ================= 数据拉取 =================
const fetchData = async () => {
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
      selectedRowKeys.value = [];
    }
  } catch (error) {
    message.error('加载计划任务失败');
  } finally {
    loading.value = false;
  }
};

const fetchPolicyList = async () => {
  const res = await request.get('/policy/', { params: { size: 1000, order: '-update_date' } });
  if (res.code === 200) policyList.value = res.items || [];
};

const resetSearch = () => {
  Object.assign(searchForm, { name: '', target: '', policy_name: '', schedule_type: undefined, schedule_status: undefined });
  pagination.current = 1;
  onSearch();
};

const onSearch = () => { pagination.current = 1; fetchData(); };
const handleTableChange = (page, pageSize) => { pagination.current = page; pagination.pageSize = pageSize; fetchData(); };

// ================= 弹窗交互与发包 =================
const addModalVisible = ref(false);
const addLoading = ref(false);
const addForm = reactive({
  name: '', target: '', schedule_type: 'future_scan',
  policy_id: undefined, task_tag: undefined,
  start_date: '', cron: ''
});

const openAddModal = () => {
  Object.assign(addForm, {
    name: '', target: '', schedule_type: 'future_scan',
    policy_id: undefined, task_tag: undefined, start_date: '', cron: ''
  });
  addModalVisible.value = true;
};

// 切换类型时清空无用的字段，保持整洁
const onScheduleTypeChange = (val) => {
  addForm.start_date = '';
  addForm.cron = '';
};

const submitAdd = async () => {
  if (!addForm.name || !addForm.target || !addForm.policy_id || !addForm.task_tag) {
    return message.warning('请填写所有必填项！');
  }

  const payload = {
    name: addForm.name,
    target: addForm.target,
    schedule_type: addForm.schedule_type,
    policy_id: addForm.policy_id,
    task_tag: addForm.task_tag
  };

  // 🚨 根据类型，精准组装对应的动态字段
  if (addForm.schedule_type === 'future_scan') {
    if (!addForm.start_date) return message.warning('请选择开始时间！');
    payload.start_date = addForm.start_date;
  } else {
    if (!addForm.cron) return message.warning('请输入Cron表达式！');
    payload.cron = addForm.cron;
  }

  addLoading.value = true;
  try {
    const res = await request.post('/task_schedule/', payload);
    // 这里拦截一下它非常经典的 1502 Cron错误
    if (res.code === 200) {
      message.success('计划任务创建成功！');
      addModalVisible.value = false;
      onSearch();
    } else {
      message.error(res.message || '创建失败');
    }
  } catch (error) {
    message.error('请求异常，创建失败');
  } finally {
    addLoading.value = false;
  }
};

// ================= 行操作与批量操作 =================
// actionType: 'stop' | 'recover' | 'delete'
const performAction = async (actionType, idArray) => {
  try {
    const url = `/task_schedule/${actionType}/`;
    const res = await request.post(url, { _id: idArray });
    if (res.code === 200) {
      message.success('操作成功！');
      fetchData();
    } else {
      message.error(res.message || '操作失败');
    }
  } catch (e) {
    message.error('请求异常');
  }
};

const handleSingleAction = (type, id) => performAction(type, [id]);
const handleBatchStop = () => performAction('stop', selectedRowKeys.value);
const handleBatchDelete = () => performAction('delete', selectedRowKeys.value);

onMounted(() => {
  fetchData();
  fetchPolicyList();
});
</script>

<style scoped>
.search-row { display: flex; flex-wrap: wrap; gap: 16px 12px; align-items: center; }
.search-item { display: flex; align-items: center; }
.search-item .label { color: var(--arl-text-color); margin-right: 8px; min-width: 60px; text-align: right; white-space: nowrap; }
</style>