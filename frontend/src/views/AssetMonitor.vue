<template>
  <div style="background-color: #fff; padding: 24px; min-height: calc(100vh - 64px);">

    <div class="search-row" style="margin-bottom: 16px;">
      <div class="search-item">
        <span class="label">名称：</span>
        <a-input v-model:value="searchForm.name" placeholder="请输入名称进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
        </a-input>
      </div>
      <div class="search-item">
        <span class="label">域名：</span>
        <a-input v-model:value="searchForm.domain" placeholder="请输入域名进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
        </a-input>
      </div>
      <div class="search-item">
        <span class="label">资产范围ID：</span>
        <a-input v-model:value="searchForm.scope_id" placeholder="请输入资产范围ID进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
        </a-input>
      </div>
    </div>

    <div style="margin-bottom: 16px; display: flex; gap: 8px;">
      <a-button :disabled="!hasSelected" @click="handleBatchAction('delete')">批量删除</a-button>
      <a-button :disabled="!hasSelected" @click="handleBatchAction('stop')">批量停止</a-button>
      <a-button :disabled="!hasSelected" @click="handleBatchAction('recover')">批量恢复</a-button>
      <a-button :disabled="!hasSelected" @click="handleBatchAction('run')">批量下发</a-button>
    </div>

    <a-table
        :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }"
        :loading="loading"
        :dataSource="dataSource"
        :columns="columns"
        :pagination="false"
        size="middle"
        :rowKey="(record) => record._id"
    >
      <template #bodyCell="{ column, record, index }">

        <template v-if="column.key === 'index'">
          {{ (pagination.current - 1) * pagination.pageSize + index + 1 }}
        </template>

        <template v-if="column.key === 'scope_id'">
          <span
              style="color: #00bcd4; cursor: pointer;"
              @click="goToAssetScope(record.scope_id)"
          >
            {{ record.scope_id }}
          </span>
        </template>

        <template v-else-if="column.key === 'interval'">
          <span>{{ formatInterval(record.interval) }}</span>
        </template>

        <template v-else-if="column.key === 'run_number'">
          <span style="color: #00bcd4; cursor: pointer;">{{ record.run_number }}</span>
        </template>

        <template v-else-if="column.key === 'action'">
          <div style="display: flex; gap: 8px;">
            <a-button size="small" :disabled="record.status === 'stop'" @click="handleSingleAction('stop', record)">暂停</a-button>
            <a-button size="small" :disabled="record.status !== 'stop'" @click="handleSingleAction('resume', record)">恢复</a-button>
            <a-button size="small" @click="handleSingleAction('run', record)">立即下发</a-button>
            <a-button size="small" @click="handleSingleAction('delete', record)">删除</a-button>
          </div>
        </template>

      </template>
    </a-table>

    <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
      <div style="color: rgba(0,0,0,.65);">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
      <a-pagination v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" @showSizeChange="handleTableChange" />
    </div>

  </div>
</template>

<script setup>
import { ref, onMounted, reactive, computed, createVNode } from 'vue';
import request from '../utils/request';
import { message, Modal } from 'ant-design-vue';
import { SearchOutlined, ExclamationCircleOutlined } from '@ant-design/icons-vue';
import { useRouter } from 'vue-router';


const router = useRouter();

// 🚨 点击跳转到资产分组页，并在 URL 中带上 scope_id 参数
const goToAssetScope = (id) => {
  if (!id) return;
  router.push({
    path: '/group', // 确保这是你的“资产分组”页面的真实路由路径
    query: { scope_id: id }
  });
};

const loading = ref(false);
const dataSource = ref([]);
const searchForm = ref({});
const pagination = reactive({ current: 1, pageSize: 10, total: 0 });

const selectedRowKeys = ref([]);
const hasSelected = computed(() => selectedRowKeys.value.length > 0);
const onSelectChange = (keys) => { selectedRowKeys.value = keys; };

const columns = [
  { title: '序号', key: 'index', width: 80, align: 'center' },
  { title: '名称', dataIndex: 'name', key: 'name', width: 200 },
  { title: '域名', dataIndex: 'domain', key: 'domain', width: 180 },
  { title: '资产范围ID', key: 'scope_id', width: 220 },
  { title: '运行间隔', key: 'interval', width: 120 },
  { title: '上一次运行日期', dataIndex: 'last_run_date', key: 'last_run_date', width: 180 },
  { title: '下一次运行日期', dataIndex: 'next_run_date', key: 'next_run_date', width: 180 },
  { title: '运行次数', key: 'run_number', width: 100, align: 'center' },
  { title: '操作', key: 'action', width: 260 }
];

// 💡 核心逻辑：秒数转直观时间 (86400 -> 24 小时)
const formatInterval = (seconds) => {
  if (!seconds) return '-';
  if (seconds >= 3600 && seconds % 3600 === 0) return `${seconds / 3600} 小时`;
  if (seconds >= 60 && seconds % 60 === 0) return `${seconds / 60} 分钟`;
  return `${seconds} 秒`;
};

// 拉取表格数据
const fetchData = async () => {
  loading.value = true;
  try {
    const params = { page: pagination.current, size: pagination.pageSize };
    for (const key in searchForm.value) {
      if (searchForm.value[key]) params[key] = searchForm.value[key];
    }
    const res = await request.get('/scheduler/', { params });
    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
      selectedRowKeys.value = []; // 清空勾选
    }
  } catch (error) {
    message.error('加载资产监控数据失败');
  } finally {
    loading.value = false;
  }
};

const onSearch = () => { pagination.current = 1; fetchData(); };
const handleTableChange = (page, pageSize) => { pagination.current = page; pagination.pageSize = pageSize; fetchData(); };

// ==========================================
// 💡 操作逻辑区 (如果这几个 API 报错，请反馈抓包结果)
// ==========================================
const apiMap = {
  delete: '/scheduler/delete/',
  stop: '/scheduler/stop/',
  resume: '/scheduler/recover/',
  run: '/scheduler/run/'
};

const executeAction = async (actionType, ids) => {
  const url = apiMap[actionType];
  if (!url) return;

  try {
    let payload = {};
    if (actionType === 'delete') {
      payload = { job_id: ids };
    } else {
      payload = { job_id: ids[0] };
    }
    const res = await request.post(url, payload);
    if (res.code === 200) {
      message.success('操作成功！');
      fetchData();
    } else {
      message.error('操作失败: ' + res.message);
    }
  } catch (error) {
    message.error('网络请求异常');
  }
};

// 单行操作
const handleSingleAction = (actionType, record) => {
  const actionName = actionType === 'delete' ? '删除' : actionType === 'stop' ? '暂停' : actionType === 'resume' ? '恢复' : '立即下发';
  if (actionType === 'delete' || actionType === 'run') {
    Modal.confirm({
      title: '操作确认',
      icon: createVNode(ExclamationCircleOutlined),
      content: `确认要 ${actionName} 监控任务 [${record.name}] 吗？`,
      onOk: () => executeAction(actionType, [record._id])
    });
  } else {
    // 暂停/恢复通常不需要二次弹窗确认
    executeAction(actionType, [record._id]);
  }
};

// 批量操作
// ================= 任务监控：统一批量操作引擎 =================
const handleBatchAction = (action) => {
  // 1. 定义动作字典（路由字典与文案）
  const actionMap = {
    delete:  { title: '批量删除', text: '删除', url: '/scheduler/delete/', type: 'danger' },
    stop:    { title: '批量停止', text: '停止', url: '/scheduler/stop/batch', type: 'danger' },
    recover: { title: '批量恢复', text: '恢复', url: '/scheduler/recover/batch', type: 'primary' },
    run:     { title: '批量下发', text: '下发', url: '/scheduler/run/batch', type: 'primary' }
  };

  const current = actionMap[action];

  Modal.confirm({
    title: `${current.title}确认`,
    icon: createVNode(ExclamationCircleOutlined),
    content: `确定要对选中的 ${selectedRowKeys.value.length} 个任务执行【${current.text}】操作吗？`,
    okText: '确 定',
    okType: current.type,
    cancelText: '取 消',
    onOk: async () => {
      try {
        // 🚨 完美对齐抓包：使用 job_id 作为键名，传递数组
        const res = await request.post(current.url, {
          job_id: selectedRowKeys.value
        });

        if (res.code === 200) {
          message.success(`批量${current.text}成功！`);

          // 如果是删除操作，且把当前页删光了，自动回退一页
          if (action === 'delete' && dataSource.value.length === selectedRowKeys.value.length && pagination.current > 1) {
            pagination.current -= 1;
          }

          selectedRowKeys.value = []; // 清空选中状态
          fetchData(); // 🚨 完美对齐抓包的最后一步：重新拉取数据刷新表格
        } else {
          message.error(`${current.text}失败: ` + res.message);
        }
      } catch (error) {
        message.error(`请求异常，${current.text}失败`);
      }
    }
  });
};

onMounted(fetchData);
</script>

<style scoped>
.search-row {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 24px;
  align-items: center;
}
.search-item {
  display: flex;
  align-items: center;
}
.search-item .label {
  color: rgba(0,0,0,0.85);
  margin-right: 4px; /* 缩小标签和输入框的间距 */
  white-space: nowrap; /* 🚨 核心修复：移除 min-width，让文字自然适应宽度且不换行 */
}
</style>