<template>
  <div style="background-color: #fff; padding: 24px; min-height: calc(100vh - 64px);">
    <a-page-header
      :title="`任务名: ${taskName || taskId}`"
      @back="() => router.back()"
      style="padding: 0 0 24px 0;"
    />

    <a-tabs v-model:activeKey="activeTab" type="card" class="arl-detail-tabs" @change="onTabChange">
      <a-tab-pane key="web" :tab="`网站查询 - ${queryCounts.web}`"></a-tab-pane>
      <a-tab-pane key="app" :tab="`APP查询 - ${queryCounts.app}`"></a-tab-pane>
      <a-tab-pane key="mapp" :tab="`小程序查询 - ${queryCounts.mapp}`"></a-tab-pane>
      <a-tab-pane key="kapp" :tab="`快应用查询 - ${queryCounts.kapp}`"></a-tab-pane>
      <a-tab-pane key="log" tab="运行日志"></a-tab-pane>
    </a-tabs>

    <div v-show="activeTab !== 'log'">
      <div style="margin-bottom: 16px;">
      <a-form :model="searchForm" layout="inline" style="row-gap: 16px;">
        <a-form-item label="主办单位名称:">
          <a-input v-model:value="searchForm.unitName" placeholder="请输入主办单位名称" style="width: 230px;" allowClear @pressEnter="onSearch">
            <template #suffix><search-outlined @click="onSearch" style="color: rgba(0,0,0,.25); cursor: pointer;"/></template>
          </a-input>
        </a-form-item>
        <a-form-item label="域名:">
          <a-input v-model:value="searchForm.domain" placeholder="请输入域名" style="width: 230px;" allowClear @pressEnter="onSearch">
            <template #suffix><search-outlined @click="onSearch" style="color: rgba(0,0,0,.25); cursor: pointer;"/></template>
          </a-input>
        </a-form-item>
        <a-form-item label="主备案号:">
          <a-input v-model:value="searchForm.mainLicence" placeholder="请输入主备案号" style="width: 230px;" allowClear @pressEnter="onSearch">
            <template #suffix><search-outlined @click="onSearch" style="color: rgba(0,0,0,.25); cursor: pointer;"/></template>
          </a-input>
        </a-form-item>
      </a-form>
    </div>

    <a-table
        :dataSource="assetList"
        :columns="columns"
        :loading="loading"
        :pagination="false"
        :scroll="{ x: 'max-content' }"
        :rowKey="(record) => record._id"
        bordered
        style="margin-bottom: 16px;"
    >
    </a-table>

      <div style="display: flex; justify-content: space-between; align-items: center; padding: 0 16px;">
        <div style="color: rgba(0,0,0,.65);">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
        <a-pagination v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" @showSizeChange="handleTableChange" />
      </div>
    </div>

    <div v-show="activeTab === 'log'">
      <div style="border: 1px solid #e8e8e8; border-radius: 4px; padding: 8px; background-color: #fafafa;">
        <div style="background-color: #001529; color: #e6f7ff; font-family: 'Fira Code', Consolas, 'Courier New', monospace; padding: 16px; border-radius: 4px; height: 60vh; overflow-y: auto; font-size: 13px; line-height: 1.6; box-shadow: inset 0 2px 8px rgba(0,0,0,0.2);">
          <div v-for="(log, idx) in syslogList" :key="idx" style="margin-bottom: 6px; word-break: break-all; border-bottom: 1px dashed rgba(255,255,255,0.1); padding-bottom: 4px;">
            <span style="color: #00bcd4; margin-right: 8px;">[{{ log.create_time }}]</span>
            <span :style="{ color: log.level === 'error' ? '#ff4d4f' : log.level === 'warning' ? '#faad14' : '#52c41a', fontWeight: 'bold', marginRight: '8px' }">[{{ (log.level || 'info').toUpperCase() }}]</span>
            <span style="color: #1890ff; margin-right: 8px;">[{{ log.title }}]</span>
            <span style="color: #e6f7ff;">{{ log.message }}</span>
          </div>
          <div v-if="syslogList.length === 0" style="color: rgba(255,255,255,0.45); font-style: italic;">[System] 暂无日志记录... (等待日志生成或当前为历史遗留任务)</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { SearchOutlined } from '@ant-design/icons-vue';
import request from '../utils/request';

const route = useRoute();
const router = useRouter();
const query = route.query || {};

const taskId = query.task_id;
const taskName = query.name;

const activeTab = ref('web');
const queryCounts = reactive({
  web: Number(query.web_cnt) || 0,
  app: Number(query.app_cnt) || 0,
  mapp: Number(query.mapp_cnt) || 0,
  kapp: Number(query.kapp_cnt) || 0,
});

const assetList = ref([]);
const loading = ref(false);
const pagination = reactive({ current: 1, pageSize: 10, total: 0 });

const syslogList = ref([]);
let syslogTimer = null;

const columns = [
  { title: '主办单位名称', dataIndex: 'unitName', key: 'unitName', width: 220 },
  { title: '单位性质', dataIndex: 'natureName', key: 'natureName', width: 120 },
  { title: '主备案号', dataIndex: 'mainLicence', key: 'mainLicence', width: 180 },
  { title: '域名', dataIndex: 'domain', key: 'domain', width: 200 },
  { title: '网站名称', dataIndex: 'serviceName', key: 'serviceName', width: 200 },
  { title: '服务许可', dataIndex: 'serviceLicence', key: 'serviceLicence', width: 180 },
  { title: '更新时间', dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 160 }
];

const searchForm = reactive({ unitName: '', domain: '', mainLicence: '' });

const fetchAssets = async (page = 1, size = 10) => {
  loading.value = true;
  try {
    const queryParams = { page, size, task_id: taskId, query_type: activeTab.value };
    if (searchForm.unitName) queryParams.unitName = searchForm.unitName;
    if (searchForm.domain) queryParams.domain = searchForm.domain;
    if (searchForm.mainLicence) queryParams.mainLicence = searchForm.mainLicence;

    const res = await request.get('/icp/asset', { params: queryParams });
    if (res.code === 200) {
      assetList.value = res.items || [];
      pagination.total = res.total || 0;
      pagination.current = page;
      pagination.pageSize = size;
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
const handleTableChange = (page, pageSize) => fetchAssets(page, pageSize);

const fetchSyslog = async () => {
  try {
    const res = await request.get('/syslog/', { params: { task_id: taskId, size: 500, order: 'create_time' } });
    if (res.code === 200) {
      syslogList.value = res.items || [];
    }
  } catch (error) {
    console.error('获取日志失败:', error);
  }
};

const onTabChange = () => {
  if (activeTab.value === 'log') {
    fetchSyslog();
    if (!syslogTimer) {
      syslogTimer = setInterval(fetchSyslog, 3000);
    }
  } else {
    fetchAssets(1, pagination.pageSize);
    if (syslogTimer) {
      clearInterval(syslogTimer);
      syslogTimer = null;
    }
  }
};

onMounted(() => {
  if (taskId) {
    fetchAssets(pagination.current, pagination.pageSize);
  }
});

onUnmounted(() => {
  if (syslogTimer) {
    clearInterval(syslogTimer);
  }
});
</script>
