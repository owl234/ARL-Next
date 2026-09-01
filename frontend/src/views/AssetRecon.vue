<template>
  <div style="background-color: var(--arl-bg-layout); padding: 24px; min-height: calc(100vh - 64px);">
    <div ref="actionBarRef" style="position: sticky; top: 0px; z-index: 10; background-color: var(--arl-bg-layout); margin: -24px -24px 16px -24px; padding: 24px 24px 16px 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">

    <div style="margin-bottom: 16px; display: flex; align-items: center; gap: 12px;">
      <a-button type="primary" @click="showTycModal">新建企业资产查询</a-button>
      <a-button type="primary" @click="showModal">新建 ICP 查询</a-button>
    </div>

    <div class="search-row" style="margin-bottom: 16px; ">
      <a-form :model="searchForm" layout="inline" style="row-gap: 16px;">
        <a-form-item label="任务名:">
          <a-input v-model:value="searchForm.name" placeholder="请输入任务名" style="width: 230px;" allowClear @pressEnter="onSearch">
            <template #suffix><search-outlined @click="onSearch" style="color: var(--arl-text-color); opacity: 0.25; cursor: pointer;"/></template>
          </a-input>
        </a-form-item>
        <a-form-item label="查询目标:">
          <a-input v-model:value="searchForm.target" placeholder="请输入查询目标" style="width: 230px;" allowClear @pressEnter="onSearch">
            <template #suffix><search-outlined @click="onSearch" style="color: var(--arl-text-color); opacity: 0.25; cursor: pointer;"/></template>
          </a-input>
        </a-form-item>
        <a-form-item label="状态:">
          <a-input v-model:value="searchForm.status" placeholder="请输入状态" style="width: 230px;" allowClear @pressEnter="onSearch">
            <template #suffix><search-outlined @click="onSearch" style="color: var(--arl-text-color); opacity: 0.25; cursor: pointer;"/></template>
          </a-input>
        </a-form-item>
        <a-form-item label="结束时间:">
          <a-range-picker
            v-model:value="searchForm.dateRange"
            :presets="rangePresets"
            :placeholder="['开始日期', '结束日期']"
            format="YYYY-MM-DD"
            style="width: 250px;"
            allowClear
            @change="onSearch"
            @openChange="onOpenChange"
          />
        </a-form-item>
      </a-form>
    </div>

    <div style="margin-bottom: 16px;">
      <a-button style="margin-right: 16px;" @click="resetSearch">清 除</a-button>
      <a-popconfirm title="确定要批量重启选中的任务吗？" ok-text="确定" cancel-text="取消" @confirm="handleBatchRestart">
        <a-button :disabled="selectedRowKeys.length === 0" style="margin-right: 16px;">批量重启</a-button>
      </a-popconfirm>
      <a-popconfirm title="确定要批量删除选中的任务吗？" @confirm="handleBatchDelete">
        <a-button danger :disabled="selectedRowKeys.length === 0" style="margin-right: 16px;">批量删除</a-button>
      </a-popconfirm>
      <a-button type="primary" :disabled="selectedRowKeys.length === 0" @click="handleBatchExport">批量导出</a-button>
    </div>

    
    </div>
<a-table :sticky="stickyConfig"
        :dataSource="taskList"
        :columns="columns"
        :loading="loading"
        :pagination="false"
        :scroll="{ x: 'max-content' }"
        :rowSelection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }"
        :rowKey="(record) => record._id"
        bordered
        style="margin-bottom: 16px;"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <a style="color: var(--arl-theme-color); font-weight: 500;" @click="viewTask(record)">{{ record.name }}</a>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="getStatusColor(record.status)">{{ record.status }}</a-tag>
        </template>
        <template v-else-if="column.key === 'statistic'">
          <div v-if="record.statistic" style="display: flex; gap: 8px; flex-wrap: wrap;">
            <a-badge :count="(record.statistic.asset_cnt || 0) - (record.statistic.invest_cnt || 0)" title="核心资产" />
            <a-badge v-if="record.statistic.invest_cnt !== undefined" :count="record.statistic.invest_cnt" title="对外投资" :number-style="{ backgroundColor: '#52c41a' }" />
          </div>
        </template>
        <template v-else-if="column.key === 'action'">
          <a-space size="small">
            <a-button type="link" size="small" @click="handleSync(record)" :disabled="record.status !== 'done' && record.status !== 'stop'">同步</a-button>
            <a-button type="link" size="small" @click="handleExport(record)">导出</a-button>
            <a-button type="link" size="small" @click="handleStop(record)" :disabled="record.status === 'done' || record.status === 'stop' || record.status === 'error'">停止</a-button>
            <a-button type="link" size="small" @click="handleRestart(record)" :disabled="record.status === 'running' || record.status === 'waiting'">重启</a-button>
            <a-popconfirm title="确定要删除该任务吗？" ok-text="确定" cancel-text="取消" @confirm="handleDelete(record)">
              <a-button type="link" danger size="small">删除</a-button>
            </a-popconfirm>
          </a-space>
        </template>
      </template>
    </a-table>

    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0 16px;">
      <div style="color: var(--arl-text-color); opacity: 0.65;">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
      <a-pagination :pageSizeOptions="$pageSizeOptions" v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" @showSizeChange="handleTableChange" />
    </div>
  </div>

  <a-modal
      v-model:open="visible"
      title="新建 ICP 查询"
      @ok="handleOk"
      :confirmLoading="submitLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
  >
    <a-form
        ref="formRef"
        :model="formState"
        :label-col="{ style: { width: '90px' } }"
        :wrapper-col="{ style: { width: 'calc(100% - 90px)' } }"
    >
      <a-form-item label="任务名称" name="name" :rules="[{ required: true, message: '请输入任务名称' }]">
        <a-input v-model:value="formState.name" placeholder="请输入任务名称" />
      </a-form-item>

      <a-form-item label="查询目标" name="target" :rules="[{ required: true, message: '请输入查询目标' }]">
        <a-input v-model:value="formState.target" placeholder="请输入查询目标" />
      </a-form-item>

      <a-form-item label="查询类型" name="query_type" :rules="[{ required: true, message: '请至少选择一种查询类型' }]">
        <a-checkbox-group v-model:value="formState.query_type">
          <a-checkbox value="web">网站查询</a-checkbox>
          <a-checkbox value="app">APP查询</a-checkbox>
          <a-checkbox value="mapp">小程序查询</a-checkbox>
          <a-checkbox value="kapp">快应用查询</a-checkbox>
        </a-checkbox-group>
      </a-form-item>
    </a-form>
  </a-modal>

  <a-modal
      v-model:open="tycVisible"
      title="新建企业资产查询"
      @ok="handleTycOk"
      :confirmLoading="tycSubmitLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
  >
    <a-form
        ref="tycFormRef"
        :model="tycFormState"
        :label-col="{ style: { width: '110px' } }"
        :wrapper-col="{ style: { width: 'calc(100% - 110px)' } }"
    >
      <a-alert
          v-if="!tycConfigCheck.valid && !tycConfigCheck.loading"
          type="warning"
          show-icon
          style="margin-bottom: 16px;"
      >
        <template #message>
          {{ tycConfigCheck.message || '未配置天眼查 ID 或 Token，请先完成配置。' }}
          <a @click="router.push({ path: '/systemSettings', query: { tab: 'api_config' } })" style="margin-left: 8px; font-weight: 500;">
            去配置 &rarr;
          </a>
        </template>
      </a-alert>
      <a-form-item label="任务名称" name="name" :rules="[{ required: true, message: '请输入任务名称' }]">
        <a-input v-model:value="tycFormState.name" placeholder="请输入任务名称" />
      </a-form-item>

      <a-form-item label="公司 ID" name="gid" :rules="[{ required: true, message: '请输入天眼查公司 ID' }]">
        <a-input v-model:value="tycFormState.gid" placeholder="例如：25174642" />
      </a-form-item>

      <a-form-item label="查询层数" name="depth" tooltip="1 表示查询当前目标企业自身资产，2 表示穿透其对外投资子公司，以此类推">
        <a-input-number v-model:value="tycFormState.depth" :min="1" :max="20" style="width: 100%;" />
      </a-form-item>

      <a-form-item label="最低投资比例" name="invest_ratio" tooltip="仅对对外投资生效，大于等于该比例才入库并递归。0或为空表示不限制；设置比例后，无持股比例数据的公司将自动丢弃">
        <a-input-number v-model:value="tycFormState.invest_ratio" addon-after="%" :min="0" :max="100" style="width: 100%;" placeholder="0 表示不限制" />
      </a-form-item>

      <a-form-item label="查询类型" name="query_type" :rules="[{ required: true, message: '请至少选择一种查询类型' }]">
        <a-checkbox-group v-model:value="tycFormState.query_type">
          <a-checkbox value="invest">对外投资</a-checkbox>
          <a-checkbox value="trademark">商标信息</a-checkbox>
          <a-checkbox value="web">备案网站</a-checkbox>
          <a-checkbox value="app">APP</a-checkbox>
          <a-checkbox value="mapp">小程序</a-checkbox>
          <a-checkbox value="wechat">微信公众号</a-checkbox>
          <a-checkbox value="weibo">微博</a-checkbox>
        </a-checkbox-group>
      </a-form-item>
    </a-form>
  </a-modal>

  <a-modal
      v-model:open="syncModalVisible"
      title="同步资产至资产分组"
      @ok="submitSync"
      wrapClassName="arl-theme-modal"
      okText="同 步"
      cancelText="取 消"
      width="580px"
      :confirmLoading="syncLoading"
      :okButtonProps="{ disabled: modalDataLoading || syncLoading }"
  >
    <a-spin :spinning="modalDataLoading" tip="正在加载资产组及预检数据...">
      <a-form :label-col="{ style: { width: '100px' } }" :wrapper-col="{ style: { width: 'calc(100% - 100px)' } }">
        <a-form-item label="同步方式">
          <a-radio-group v-model:value="syncFormState.mode" @change="onSyncScopeChange">
            <a-radio value="existing">关联已有资产组</a-radio>
            <a-radio value="new">新建资产组</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item v-if="syncFormState.mode === 'existing'" label="选择资产组" :rules="[{ required: true, message: '请选择资产组' }]">
          <a-select
            v-model:value="syncFormState.scope_id"
            placeholder="请选择资产组"
            show-search
            option-filter-prop="label"
            @change="onSyncScopeChange"
          >
            <a-select-option v-for="scope in assetScopes" :key="scope._id" :value="scope._id" :label="scope.name">
              {{ scope.name }}
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item v-if="syncFormState.mode === 'new'" label="资产组名称" :rules="[{ required: true, message: '请输入资产组名称' }]">
          <a-input v-model:value="syncFormState.target_name" placeholder="请输入资产组名称" @input="onSyncScopeChange" />
        </a-form-item>

        <!-- 增量预检提示 -->
        <a-alert
          v-if="syncDiffInfo.show"
          style="margin-bottom: 16px; margin-left: 20px; margin-right: 20px;"
          type="info"
          show-icon
        >
          <template #message>
            <div style="font-size: 13px;">
              本次任务共包含 <b>{{ syncDiffInfo.totalCount }}</b> 个网站域名：
              <span style="color: #1890ff; font-weight: bold;">{{ syncDiffInfo.newCount }} 个全新域名</span>，
              <span style="color: #8c8c8c;">{{ syncDiffInfo.duplicateCount }} 个已存在</span>。
            </div>
          </template>
        </a-alert>

        <a-divider style="margin: 12px 0 16px 0;" dashed />

        <a-form-item label="任务下发">
          <a-checkbox v-model:checked="syncFormState.auto_scan">
            立即对新发现域名发起探测任务
          </a-checkbox>
        </a-form-item>

        <template v-if="syncFormState.auto_scan">
          <a-form-item label="任务类型">
            <a-radio-group v-model:value="syncFormState.task_type">
              <a-radio value="oneshot">一次性扫描 (立刻深度探测并入库)</a-radio>
              <a-radio value="periodic">周期性监控 (定时自动化巡航)</a-radio>
            </a-radio-group>
          </a-form-item>

          <a-form-item label="扫描策略" :rules="[{ required: true, message: '请选择扫描策略' }]">
            <a-select
              v-model:value="syncFormState.policy_id"
              placeholder="请选择扫描策略"
              :options="policyList.map(p => ({ value: p._id, label: p.name }))"
            />
          </a-form-item>

          <a-form-item v-if="syncFormState.task_type === 'periodic'" label="运行间隔">
            <a-input-number
              v-model:value="syncFormState.interval_hours"
              :min="6"
              :max="720"
              style="width: 160px;"
              addon-after="小时"
            />
          </a-form-item>
        </template>
      </a-form>
    </a-spin>
  </a-modal>
</template>

<script setup>
defineOptions({ name: 'AssetRecon' });

import { ref, reactive, onMounted, watch, onActivated } from 'vue';
import dayjs from 'dayjs';
import { useSticky } from '../utils/useSticky';
const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

import { message, Modal } from 'ant-design-vue';
import { useRouter } from 'vue-router';
import { SearchOutlined } from '@ant-design/icons-vue';
import request from '../utils/request';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';

const router = useRouter();
const taskList = ref([]);
const loading = ref(false);
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

watch(() => pagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});

watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
});

const selectedRowKeys = ref([]);
const onSelectChange = (keys) => {
  selectedRowKeys.value = keys;
};

const syncModalVisible = ref(false);
const syncLoading = ref(false);
const modalDataLoading = ref(false);
const currentSyncTask = ref(null);
const assetScopes = ref([]);
const policyList = ref([]);
const currentTaskWebDomains = ref([]);
const syncDiffInfo = reactive({
  show: false,
  totalCount: 0,
  newCount: 0,
  duplicateCount: 0
});

const syncFormState = reactive({
  mode: 'existing',
  scope_id: undefined,
  target_name: '',
  auto_scan: false,
  task_type: 'oneshot',
  policy_id: undefined,
  interval_hours: 24
});

const rangePresets = ref([
  { label: '今天', value: [dayjs().startOf('day'), dayjs().endOf('day')] },
  { label: '近 7 天', value: [dayjs().subtract(6, 'day').startOf('day'), dayjs().endOf('day')] },
  { label: '近 30 天', value: [dayjs().subtract(29, 'day').startOf('day'), dayjs().endOf('day')] },
  { label: '本月', value: [dayjs().startOf('month'), dayjs().endOf('month')] },
]);

const onOpenChange = (open) => {
  if (open) {
    rangePresets.value = [
      { label: '今天', value: [dayjs().startOf('day'), dayjs().endOf('day')] },
      { label: '近 7 天', value: [dayjs().subtract(6, 'day').startOf('day'), dayjs().endOf('day')] },
      { label: '近 30 天', value: [dayjs().subtract(29, 'day').startOf('day'), dayjs().endOf('day')] },
      { label: '本月', value: [dayjs().startOf('month'), dayjs().endOf('month')] },
    ];
  }
};

const columns = [
  { title: '任务名', dataIndex: 'name', key: 'name', width: 180 },
  { title: '查询目标', dataIndex: 'target', key: 'target', width: 220 },
  { title: '查询类型', dataIndex: 'query_type', key: 'query_type', width: 180 },
  { title: '资产数量', dataIndex: 'statistic', key: 'statistic', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '开始时间', dataIndex: 'start_time', key: 'start_time', width: 160 },
  { title: '结束时间', dataIndex: 'end_time', key: 'end_time', width: 160 },
  { title: '任务 ID', dataIndex: '_id', key: '_id', width: 220 },
  { title: '操作', key: 'action', width: 200, fixed: 'right' }
];

const getStatusColor = (status) => {
  if (status === 'done') return 'success';
  if (status === 'error') return 'error';
  if (status === 'stop') return 'warning';
  if (status === 'waiting') return 'default';
  return 'processing';
};

const searchForm = reactive({ name: '', target: '', status: '', dateRange: null });

const fetchTasks = async (page = 1, size = 10, silent = false) => {
  if (!silent) {
    loading.value = true;
  }
  try {
    const queryParams = { page, size };
    if (searchForm.name) queryParams.name = searchForm.name;
    if (searchForm.target) queryParams.target = searchForm.target;
    if (searchForm.status) queryParams.status = searchForm.status;
    if (searchForm.dateRange && searchForm.dateRange.length === 2 && searchForm.dateRange[0] && searchForm.dateRange[1]) {
      queryParams.end_time__gte = dayjs(searchForm.dateRange[0]).startOf('day').format('YYYY-MM-DD HH:mm:ss');
      queryParams.end_time__lte = dayjs(searchForm.dateRange[1]).endOf('day').format('YYYY-MM-DD HH:mm:ss');
    }

    const res = await request.get('/icp/task', { params: queryParams });
    if (res.code === 200) {
      taskList.value = res.items || [];
      // 将返回的列表格式化展示，若是数组则逗号拼接
      taskList.value.forEach(item => {
        if (Array.isArray(item.query_type)) {
          item.query_type = item.query_type.join(', ');
        }
      });
      pagination.total = res.total || 0;
      pagination.current = page;
      pagination.pageSize = size;
    } else {
      console.error('获取列表失败:', res);
    }
  } catch (error) {
    console.error('API 请求失败:', error);
  } finally {
    if (!silent) {
      loading.value = false;
    }
  }
};

const onSearch = () => fetchTasks(1, pagination.pageSize);
const resetSearch = () => {
  searchForm.name = '';
  searchForm.target = '';
  searchForm.status = '';
  searchForm.dateRange = null;
  onSearch();
};
const handleTableChange = (page, pageSize) => fetchTasks(page, pageSize);

onMounted(() => fetchTasks(pagination.current, pagination.pageSize));

const visible = ref(false);
const submitLoading = ref(false);
const formRef = ref();

const formState = reactive({
  name: "",
  target: "",
  query_type: ["web"]
});

const showModal = () => { visible.value = true; };

const handleOk = async () => {
  try {
    await formRef.value.validate();
    submitLoading.value = true;
    const res = await request.post('/icp/task', formState);
    if (res.code === 200) {
      message.success('任务创建成功');
      visible.value = false;
      fetchTasks(1, pagination.pageSize);
    } else {
      message.error(res.message || '创建失败');
    }
  } catch (error) {
    console.error(error);
  } finally {
    submitLoading.value = false;
  }
};

const tycVisible = ref(false);
const tycSubmitLoading = ref(false);
const tycFormRef = ref();

const tycFormState = reactive({
  name: "",
  gid: "",
  depth: 1,
  invest_ratio: 50,
  query_type: ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo']
});

const tycConfigCheck = reactive({
  loading: false,
  valid: true,
  message: ''
});

const showTycModal = async () => {
  tycVisible.value = true;
  // 重置表单状态，确保每次打开时恢复默认配置
  tycFormState.depth = 1;
  tycFormState.query_type = ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo'];
  
  tycConfigCheck.loading = true;
  tycConfigCheck.valid = true;
  tycConfigCheck.message = '';
  try {
    const res = await request.get('/icp/tyc_check');
    if (res.code === 200) {
      tycConfigCheck.valid = res.data.valid;
      tycConfigCheck.message = res.data.message;
    }
  } catch (error) {
    console.error(error);
  } finally {
    tycConfigCheck.loading = false;
  }
};

const handleTycOk = async () => {
  try {
    await tycFormRef.value.validate();

    if (!tycConfigCheck.valid) {
      Modal.confirm({
        title: '天眼查配置无效',
        content: tycConfigCheck.message || '未配置天眼查 ID 或 Token，请先完成配置后再创建任务。',
        okText: '去配置',
        cancelText: '取消',
        onOk() {
          router.push({ path: '/systemSettings', query: { tab: 'api_config' } });
        }
      });
      return;
    }

    tycSubmitLoading.value = true;
    const res = await request.post('/icp/tyc_task', tycFormState);
    if (res.code === 200) {
      message.success('企业资产查询任务创建成功');
      tycVisible.value = false;
      fetchTasks(1, pagination.pageSize);
    } else {
      message.error(res.message || '创建失败');
    }
  } catch (error) {
    console.error(error);
  } finally {
    tycSubmitLoading.value = false;
  }
};

const viewTask = (record) => {
  const stats = record.statistic || {};
  router.push({
    path: '/assetRecon/assetDetail',
    query: {
      task_id: record._id,
      name: record.name,
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

const handleExport = async (record) => {
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
    console.error('导出失败', error);
    message.error({ content: '导出失败', key: 'export', duration: 2 });
  }
};

const handleBatchExport = async () => {
  if (selectedRowKeys.value.length === 0) {
    message.warning('请先勾选需要导出的任务');
    return;
  }
  try {
    message.loading({ content: '正在批量导出...', key: 'batch_export', duration: 0 });
    const res = await request.post('/icp/batch_export', {
      task_id: selectedRowKeys.value
    }, { responseType: 'blob' });

    const blob = new Blob([res.data || res]);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `batch_icp_export.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    message.success({ content: '批量导出成功', key: 'batch_export', duration: 2 });
  } catch (error) {
    console.error('批量导出失败', error);
    message.error({ content: '批量导出失败', key: 'batch_export', duration: 2 });
  }
};

const onSyncScopeChange = () => {
  if (!currentTaskWebDomains.value || currentTaskWebDomains.value.length === 0) {
    syncDiffInfo.show = false;
    return;
  }

  const total = currentTaskWebDomains.value.length;
  if (syncFormState.mode === 'existing') {
    if (!syncFormState.scope_id) {
      syncDiffInfo.show = false;
      return;
    }
    const targetScope = assetScopes.value.find(s => s._id === syncFormState.scope_id);
    const scopeDomainArray = (targetScope?.domain_array || targetScope?.scope_array || []).map(d => d.toLowerCase().trim());
    const duplicates = currentTaskWebDomains.value.filter(d => scopeDomainArray.includes(d.toLowerCase().trim()));
    const newDomains = currentTaskWebDomains.value.filter(d => !scopeDomainArray.includes(d.toLowerCase().trim()));

    syncDiffInfo.show = true;
    syncDiffInfo.totalCount = total;
    syncDiffInfo.duplicateCount = duplicates.length;
    syncDiffInfo.newCount = newDomains.length;
  } else {
    // 新建模式：若同名则比对，若不同名则全是新增
    const targetScope = assetScopes.value.find(s => s.name === syncFormState.target_name?.trim());
    if (targetScope) {
      const scopeDomainArray = (targetScope.domain_array || targetScope.scope_array || []).map(d => d.toLowerCase().trim());
      const duplicates = currentTaskWebDomains.value.filter(d => scopeDomainArray.includes(d.toLowerCase().trim()));
      const newDomains = currentTaskWebDomains.value.filter(d => !scopeDomainArray.includes(d.toLowerCase().trim()));
      syncDiffInfo.show = true;
      syncDiffInfo.totalCount = total;
      syncDiffInfo.duplicateCount = duplicates.length;
      syncDiffInfo.newCount = newDomains.length;
    } else {
      syncDiffInfo.show = true;
      syncDiffInfo.totalCount = total;
      syncDiffInfo.duplicateCount = 0;
      syncDiffInfo.newCount = total;
    }
  }
};

const handleSync = async (record) => {
  currentSyncTask.value = record;
  syncFormState.mode = 'existing';
  syncFormState.scope_id = undefined;
  syncFormState.target_name = record.name;
  syncFormState.auto_scan = false;
  syncFormState.task_type = 'oneshot';
  syncFormState.interval_hours = 24;
  syncDiffInfo.show = false;
  currentTaskWebDomains.value = [];

  // 第一时间展示弹窗，消除用户点击延迟感
  syncModalVisible.value = true;
  modalDataLoading.value = true;

  try {
    const [scopeRes, policyRes, assetRes] = await Promise.all([
      request.get('/asset_scope/', { params: { size: 1000 } }),
      policyList.value.length === 0 ? request.get('/policy/', { params: { size: 1000 } }) : Promise.resolve({ code: 200, items: policyList.value }),
      request.get('/icp/asset', { params: { task_id: record._id, query_type: 'web', size: 10000 } })
    ]);

    if (scopeRes.code === 200) {
      assetScopes.value = scopeRes.items || scopeRes.data?.items || [];
    }
    if (policyRes.code === 200 && policyRes.items) {
      policyList.value = policyRes.items || [];
      if (!syncFormState.policy_id && policyList.value.length > 0) {
        syncFormState.policy_id = policyList.value[0]._id;
      }
    }
    if (assetRes.code === 200) {
      const items = assetRes.items || assetRes.data?.items || [];
      const domains = new Set();
      items.forEach(item => {
        const d = item.domain || item.ym;
        if (d && typeof d === 'string') {
          domains.add(d.trim());
        }
      });
      currentTaskWebDomains.value = Array.from(domains);
    }
    // 异步加载完成后计算增量比对数据
    onSyncScopeChange();
  } catch (error) {
    console.error('获取同步预检数据失败', error);
  } finally {
    modalDataLoading.value = false;
  }
};

const submitSync = async () => {
  if (syncFormState.mode === 'existing' && !syncFormState.scope_id) {
    message.error('请选择关联的资产组');
    return;
  }
  if (syncFormState.mode === 'new' && !syncFormState.target_name) {
    message.error('请输入资产组名称');
    return;
  }
  if (syncFormState.auto_scan && !syncFormState.policy_id) {
    message.error('请选择扫描策略');
    return;
  }

  try {
    syncLoading.value = true;
    const payload = {
      mode: syncFormState.mode,
      target_name: syncFormState.target_name,
      scope_id: syncFormState.scope_id,
      auto_scan: syncFormState.auto_scan,
      task_type: syncFormState.task_type,
      policy_id: syncFormState.policy_id,
      interval_hours: syncFormState.interval_hours
    };
    const res = await request.post(`/icp/sync/${currentSyncTask.value._id}`, payload);
    if (res.code === 200) {
      const data = res.data || res;
      const insertCount = data.insert_count || 0;
      const duplicateCount = data.duplicate_count || 0;
      const targetName = data.target_name || payload.target_name;
      const taskTriggeredCount = data.task_triggered_count || 0;
      
      let successMsg = `同步成功，同步新增域名 ${insertCount} 条、重复 ${duplicateCount} 条`;
      if (taskTriggeredCount > 0) {
        successMsg += `，已成功下发 ${taskTriggeredCount} 个资产探测任务！`;
      }
      
      message.success({ content: successMsg, key: 'syncIcp', duration: 4 });
      syncModalVisible.value = false;
    } else {
      message.error({ content: res.message || '同步失败', key: 'syncIcp', duration: 2 });
    }
  } catch (error) {
    console.error('同步失败', error);
    message.error({ content: '网络错误，同步失败', key: 'syncIcp', duration: 2 });
  } finally {
    syncLoading.value = false;
  }
};

const handleBatchDelete = async () => {
  if (!selectedRowKeys.value.length) return;
  try {
    message.loading({ content: '正在批量删除...', key: 'batchDelete', duration: 0 });
    const res = await request.post('/icp/delete/', { task_ids: selectedRowKeys.value });
    if (res.code === 200) {
      message.success({ content: '批量删除成功', key: 'batchDelete', duration: 2 });
      selectedRowKeys.value = [];
      fetchTasks(pagination.current, pagination.pageSize);
    } else {
      message.error({ content: res.message || '批量删除失败', key: 'batchDelete', duration: 2 });
    }
  } catch (error) {
    console.error('批量删除失败', error);
    message.error({ content: '网络错误，批量删除失败', key: 'batchDelete', duration: 2 });
  }
};

const handleBatchRestart = async () => {
  if (!selectedRowKeys.value.length) return;
  try {
    message.loading({ content: '正在批量重启...', key: 'batchRestart', duration: 0 });
    const res = await request.post('/icp/restart/', { task_ids: selectedRowKeys.value });
    if (res.code === 200) {
      const data = res.data || {};
      const restarted = data.restarted_count ?? selectedRowKeys.value.length;
      const skipped = data.skipped_count || 0;

      let msg = `成功重启 ${restarted} 个任务`;
      if (skipped > 0) {
        msg += `（已自动跳过 ${skipped} 个运行中/等待中任务）`;
      }

      message.success({ content: msg, key: 'batchRestart', duration: 3 });
      selectedRowKeys.value = [];
      fetchTasks(pagination.current, pagination.pageSize);
    } else {
      message.error({ content: res.message || '批量重启失败', key: 'batchRestart', duration: 3 });
    }
  } catch (error) {
    console.error('批量重启失败', error);
    message.error({ content: '网络错误，批量重启失败', key: 'batchRestart', duration: 3 });
  }
};

const handleStop = async (record) => {
  try {
    const res = await request.get(`/icp/stop/${record._id}`);
    if (res.code === 200) {
      message.success('已停止任务');
      fetchTasks(pagination.current, pagination.pageSize);
    } else {
      message.error(res.message || '停止失败');
    }
  } catch (error) {
    console.error('停止任务失败', error);
  }
};

const handleRestart = async (record) => {
  try {
    const res = await request.get(`/icp/restart/${record._id}`);
    if (res.code === 200) {
      message.success('已重启任务');
      fetchTasks(pagination.current, pagination.pageSize);
    } else {
      message.error(res.message || '重启失败');
    }
  } catch (error) {
    console.error('重启任务失败', error);
  }
};

const handleDelete = async (record) => {
  try {
    const res = await request.get(`/icp/delete/${record._id}`);
    if (res.code === 200) {
      message.success('删除成功');
      // 如果当前页只有一条且非第一页，删除后回到上一页
      if (taskList.value.length === 1 && pagination.current > 1) {
        pagination.current -= 1;
      }
      fetchTasks(pagination.current, pagination.pageSize);
    } else {
      message.error(res.message || '删除失败');
    }
  } catch (error) {
    console.error('删除任务失败', error);
  }
};

onActivated(() => {
  fetchTasks(pagination.current, pagination.pageSize, true);
});
</script>
