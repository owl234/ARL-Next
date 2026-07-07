<template>
  <div style="background-color: #fff; padding: 24px; min-height: calc(100vh - 64px);">
    <div style="margin-bottom: 16px; display: flex; align-items: center; gap: 12px;">
      <a-button type="primary" style="background-color: #00bcd4; border-color: #00bcd4;" @click="showTycModal">新建企业资产查询</a-button>
      <a-button style="background-color: #00bcd4; color: #fff; border-color: #00bcd4;" @click="showModal">新建 ICP 查询</a-button>
    </div>

    <div class="search-row" style="margin-bottom: 20px; background-color: #f9f9f9; padding: 16px; border-radius: 4px;">
      <a-form :model="searchForm" layout="inline" style="row-gap: 16px;">
        <a-form-item label="任务名:">
          <a-input v-model:value="searchForm.name" placeholder="请输入任务名" style="width: 230px;" allowClear @pressEnter="onSearch">
            <template #suffix><search-outlined @click="onSearch" style="color: rgba(0,0,0,.25); cursor: pointer;"/></template>
          </a-input>
        </a-form-item>
        <a-form-item label="公司名称:">
          <a-input v-model:value="searchForm.target" placeholder="请输入公司名称" style="width: 230px;" allowClear @pressEnter="onSearch">
            <template #suffix><search-outlined @click="onSearch" style="color: rgba(0,0,0,.25); cursor: pointer;"/></template>
          </a-input>
        </a-form-item>
        <a-form-item label="状态:">
          <a-input v-model:value="searchForm.status" placeholder="请输入状态" style="width: 230px;" allowClear @pressEnter="onSearch">
            <template #suffix><search-outlined @click="onSearch" style="color: rgba(0,0,0,.25); cursor: pointer;"/></template>
          </a-input>
        </a-form-item>
      </a-form>
    </div>

    <div style="margin-bottom: 16px;">
      <a-popconfirm title="确定要批量删除选中的任务吗？" @confirm="handleBatchDelete">
        <a-button danger :disabled="selectedRowKeys.length === 0">批量删除</a-button>
      </a-popconfirm>
    </div>

    <a-table
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
          <a style="color: #00bcd4; font-weight: 500;" @click="viewTask(record)">{{ record.name }}</a>
        </template>
        <template v-else-if="column.key === 'status'">
          <a-tag :color="getStatusColor(record.status)">{{ record.status }}</a-tag>
        </template>
        <template v-else-if="column.key === 'statistic'">
          <span v-if="record.statistic">{{ record.statistic.asset_cnt || 0 }}</span>
          <span v-else>0</span>
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
      <div style="color: rgba(0,0,0,.65);">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
      <a-pagination v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" @showSizeChange="handleTableChange" />
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

      <a-form-item label="公司名称" name="target" :rules="[{ required: true, message: '请输入公司名称' }]">
        <a-input v-model:value="formState.target" placeholder="请输入公司名称" />
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
        :label-col="{ style: { width: '90px' } }"
        :wrapper-col="{ style: { width: 'calc(100% - 90px)' } }"
    >
      <a-alert
          v-if="!tycConfigCheck.valid && !tycConfigCheck.loading"
          :message="tycConfigCheck.message"
          type="warning"
          show-icon
          style="margin-bottom: 16px;"
      />
      <a-form-item label="任务名称" name="name" :rules="[{ required: true, message: '请输入任务名称' }]">
        <a-input v-model:value="tycFormState.name" placeholder="请输入任务名称" />
      </a-form-item>

      <a-form-item label="公司 ID" name="gid" :rules="[{ required: true, message: '请输入天眼查公司 ID' }]">
        <a-input v-model:value="tycFormState.gid" placeholder="例如：25174642" />
      </a-form-item>

      <a-form-item label="查询层数" name="depth">
        <a-input-number v-model:value="tycFormState.depth" :min="0" :max="5" style="width: 100%;" />
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
      title="同步资产"
      @ok="submitSync"
      wrapClassName="arl-theme-modal"
      okText="同 步"
      cancelText="取 消"
      :confirmLoading="syncLoading"
  >
    <a-form :label-col="{ style: { width: '100px' } }" :wrapper-col="{ style: { width: 'calc(100% - 100px)' } }">
      <a-form-item label="同步方式">
        <a-radio-group v-model:value="syncFormState.mode">
          <a-radio value="existing">关联已有资产</a-radio>
          <a-radio value="new">新建资产</a-radio>
        </a-radio-group>
      </a-form-item>

      <a-form-item v-if="syncFormState.mode === 'existing'" label="选择资产组" :rules="[{ required: true, message: '请选择资产组' }]">
        <a-select
          v-model:value="syncFormState.scope_id"
          placeholder="请选择资产组"
          show-search
          option-filter-prop="label"
        >
          <a-select-option v-for="scope in assetScopes" :key="scope._id" :value="scope._id" :label="scope.name">
            {{ scope.name }}
          </a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item v-if="syncFormState.mode === 'new'" label="资产组名称" :rules="[{ required: true, message: '请输入资产组名称' }]">
        <a-input v-model:value="syncFormState.target_name" placeholder="请输入资产组名称" />
      </a-form-item>
    </a-form>
  </a-modal>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { message, Modal } from 'ant-design-vue';
import { useRouter } from 'vue-router';
import { SearchOutlined } from '@ant-design/icons-vue';
import request from '../utils/request';

const router = useRouter();
const taskList = ref([]);
const loading = ref(false);
const pagination = reactive({ current: 1, pageSize: 10, total: 0 });

const selectedRowKeys = ref([]);
const onSelectChange = (keys) => {
  selectedRowKeys.value = keys;
};

const syncModalVisible = ref(false);
const syncLoading = ref(false);
const currentSyncTask = ref(null);
const assetScopes = ref([]);
const syncFormState = reactive({
  mode: 'existing',
  scope_id: undefined,
  target_name: ''
});

const columns = [
  { title: '任务名', dataIndex: 'name', key: 'name', width: 180 },
  { title: '公司名称', dataIndex: 'target', key: 'target', width: 220 },
  { title: '查询类型', dataIndex: 'query_type', key: 'query_type', width: 180 },
  { title: '资产数量', dataIndex: 'statistic', key: 'statistic', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '开始时间', dataIndex: 'start_time', key: 'start_time', width: 160 },
  { title: '结束时间', dataIndex: 'end_time', key: 'end_time', width: 160 },
  { title: '操作', key: 'action', width: 200, fixed: 'right' }
];

const getStatusColor = (status) => {
  if (status === 'done') return 'success';
  if (status === 'error') return 'error';
  if (status === 'waiting') return 'default';
  return 'processing';
};

const searchForm = reactive({ name: '', target: '', status: '' });

const fetchTasks = async (page = 1, size = 10) => {
  loading.value = true;
  try {
    const queryParams = { page, size };
    if (searchForm.name) queryParams.name = searchForm.name;
    if (searchForm.target) queryParams.target = searchForm.target;
    if (searchForm.status) queryParams.status = searchForm.status;

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
    loading.value = false;
  }
};

const onSearch = () => fetchTasks(1, pagination.pageSize);
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
  depth: 0,
  query_type: []
});

const tycConfigCheck = reactive({
  loading: false,
  valid: true,
  message: ''
});

const showTycModal = async () => {
  tycVisible.value = true;
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
      Modal.warning({
        title: '天眼查配置无效',
        content: tycConfigCheck.message || '未配置天眼查 ID 或 Token，请在系统设置中配置后再试。',
        okText: '知道了'
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
    path: '/icpQuery/assetDetail',
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

const handleSync = async (record) => {
  currentSyncTask.value = record;
  syncFormState.mode = 'existing';
  syncFormState.scope_id = undefined;
  syncFormState.target_name = record.target || record.name;

  try {
    const res = await request.get('/asset_scope/', { params: { size: 1000 } });
    if (res.code === 200) {
      assetScopes.value = res.items || res.data?.items || [];
    }
  } catch (error) {
    console.error('获取资产分组失败', error);
  }

  syncModalVisible.value = true;
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

  try {
    syncLoading.value = true;
    const payload = {
      mode: syncFormState.mode,
      target_name: syncFormState.target_name,
      scope_id: syncFormState.scope_id
    };
    const res = await request.post(`/icp/sync/${currentSyncTask.value._id}`, payload);
    if (res.code === 200) {
      message.success({ content: res.message || '同步成功', key: 'syncIcp', duration: 2 });
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
</script>
