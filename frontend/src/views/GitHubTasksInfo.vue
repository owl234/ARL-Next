<template>
  <div style="background-color: var(--arl-bg-layout); padding: 24px; min-height: calc(100vh - 64px);">
    <div style="margin-bottom: 16px;">
      <a-button @click="goBack" style="margin-right: 16px;">
        <template #icon><left-outlined /></template>
        返回上一页
      </a-button>
      <span style="font-size: 16px; font-weight: bold;">单次扫描任务详情</span>
    </div>
    <a-tabs v-model:activeKey="activeTab" type="card">
      
      <!-- ================= Tab 1: 扫描结果 ================= -->
      <a-tab-pane key="result" tab="扫描结果">

        <div ref="actionBarRef" style="position: sticky; top: 0px; z-index: 10; background-color: var(--arl-bg-layout); margin: -24px -24px 16px -24px; padding: 24px 24px 16px 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">
        <div class="search-row" style="margin-bottom: 16px; ">
          <div class="search-item">
            <span class="label">路径名：</span>
            <a-input v-model:value="searchForm.path" placeholder="请输入路径名进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
              <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </div>
          <div class="search-item">
            <span class="label">仓库名：</span>
            <a-input v-model:value="searchForm.repo_full_name" placeholder="请输入仓库名进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
              <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </div>
          <div class="search-item">
            <span class="label">内容：</span>
            <a-input v-model:value="searchForm.human_content" placeholder="请输入内容进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
              <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
            </a-input>
          </div>
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
          <template #bodyCell="{ column, record, text }">
            <template v-if="column.key === 'repo_full_name'">
              <a :href="`https://github.com/${record.repo_full_name}`" target="_blank" style="word-break: break-all; font-weight: 500;">
                {{ record.repo_full_name }}
              </a>
            </template>
            <template v-else-if="column.key === 'path'">
              <a :href="record.html_url" target="_blank" style="word-break: break-all;">
                {{ record.path }}
              </a>
            </template>
            <template v-else-if="column.key === 'human_content'">
              <div style="white-space: pre-wrap; word-break: break-word; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace; max-height: 300px; overflow-y: auto; background: var(--arl-bg-light); padding: 12px; border-radius: 6px; border: 1px solid var(--arl-border-color); font-size: 13px; line-height: 1.5715; color: var(--arl-text-color); margin: 4px 0;">
                {{ record.human_content }}
              </div>
            </template>
            <template v-else-if="column.key === 'keyword'">
              <a-tag color="blue">{{ record.keyword }}</a-tag>
            </template>
            <template v-else>
              {{ text }}
            </template>
          </template>
        </a-table>

        <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
          <div style="color: var(--arl-text-color); opacity: 0.65;">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
          <a-pagination :pageSizeOptions="$pageSizeOptions" v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" />
        </div>
      </a-tab-pane>

      <!-- ================= Tab 2: 执行日志 ================= -->
      <a-tab-pane key="log" tab="任务日志">
        <div style="border: 1px solid var(--arl-border-color); border-radius: 4px; padding: 8px; background-color: var(--arl-bg-light);">
          <div ref="terminalContainer" style="background-color: #001529; color: #e6f7ff; font-family: 'Fira Code', Consolas, 'Courier New', monospace; padding: 16px; border-radius: 4px; height: calc(100vh - 220px); overflow-y: auto; font-size: 13px; line-height: 1.6; box-shadow: inset 0 2px 8px rgba(0,0,0,0.2);">
            <div v-for="(log, idx) in logDataSource" :key="log._id || idx" style="margin-bottom: 6px; word-break: break-all; border-bottom: 1px dashed rgba(255,255,255,0.1); padding-bottom: 4px;">
              <a style="margin-right: 8px;">[{{ log.create_time }}]</a>
              <span :style="{ color: log.level === 'error' ? '#ff4d4f' : log.level === 'warning' ? '#faad14' : '#52c41a', fontWeight: 'bold', marginRight: '8px' }">[{{ (log.level || 'info').toUpperCase() }}]</span>
              <a style="margin-right: 8px;" v-if="log.title">[{{ log.title }}]</a>
              <span style="color: #e6f7ff;">{{ log.message }}</span>
            </div>
            <div v-if="logDataSource.length === 0 && !logLoading" style="color: rgba(255,255,255,0.45); font-style: italic;">[System] 暂无日志记录...</div>
            <div v-if="logLoading" style="color: rgba(255,255,255,0.45); font-style: italic;">[System] 正在拉取日志...</div>
          </div>
        </div>
      </a-tab-pane>

    </a-tabs>
  </div>
</template>

<script setup>

import { ref, reactive, onMounted, watch, nextTick, onUnmounted } from 'vue';
import { useSticky } from '../utils/useSticky';
const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

import { useRoute, useRouter } from 'vue-router';
import request from '../utils/request';
import { message } from 'ant-design-vue';
import { SearchOutlined, InboxOutlined, SyncOutlined, LeftOutlined } from '@ant-design/icons-vue';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';

const route = useRoute();
const router = useRouter();
const activeTab = ref('result');

const goBack = () => {
  // 返回带上之前的 tab 参数，保证退回的是任务列表而不是策略列表
  router.push({ path: '/GitHubTasks/GitHubTasksList', query: { tab: 'task' } });
};

const loading = ref(false);
const dataSource = ref([]);

// 🚨 核心：接住上级页面传来的任务 ID
const taskId = route.query._id || '';

const searchForm = reactive({ path: '', repo_full_name: '', human_content: '' });
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

watch(() => pagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});

watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
});

const selectedRowKeys = ref([]);
const onSelectChange = (keys) => { selectedRowKeys.value = keys; };

const columns = [
  { title: '仓库名', dataIndex: 'repo_full_name', key: 'repo_full_name', width: 220 },
  { title: '路径', dataIndex: 'path', key: 'path', width: 260 },
  { title: '内容', dataIndex: 'human_content', key: 'human_content' },
  { title: '提交时间', dataIndex: 'commit_date', key: 'commit_date', width: 170 },
  { title: '关键字', dataIndex: 'keyword', key: 'keyword', width: 100 }
];

// ================= 数据拉取 =================
const fetchData = async () => {
  if (!taskId) {
    message.warning('缺少任务 ID，无法加载数据');
    return;
  }

  loading.value = true;
  try {
    const params = {
      page: pagination.current,
      size: pagination.pageSize,
      github_task_id: taskId // 🚨 对应抓包里的准确参数
    };

    // 动态拼接搜索条件
    if (searchForm.path) params.path = searchForm.path;
    if (searchForm.repo_full_name) params.repo_full_name = searchForm.repo_full_name;
    if (searchForm.human_content) params.human_content = searchForm.human_content;

    // 🚨 任务详情的专用 API 接口
    const res = await request.get('/github_result/', { params });
    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
      selectedRowKeys.value = [];
    }
  } catch (error) {
    message.error('加载任务详情失败');
  } finally {
    loading.value = false;
  }
};

const onSearch = () => { pagination.current = 1; fetchData(); };
const handleTableChange = (page, pageSize) => { pagination.current = page; pagination.pageSize = pageSize; fetchData(); };

// ================= 日志拉取 =================
const logLoading = ref(false);
const logDataSource = ref([]);
const terminalContainer = ref(null);
let syslogTimer = null;

const fetchLogData = async (isPolling = false) => {
  if (!taskId) return;
  if (!isPolling) logLoading.value = true;
  
  try {
    const params = {
      size: 50000,
      task_id: taskId,
      order: 'create_time'
    };
    const res = await request.get('/syslog/', { params });
    if (res.code === 200) {
      logDataSource.value = res.items || [];
      nextTick(() => {
        if (terminalContainer.value) {
          terminalContainer.value.scrollTop = terminalContainer.value.scrollHeight;
        }
      });
    }
  } catch (error) {
    if (!isPolling) message.error('加载任务日志失败');
  } finally {
    if (!isPolling) logLoading.value = false;
  }
};

const startSyslogTimer = () => {
  if (syslogTimer) clearInterval(syslogTimer);
  fetchLogData();
  syslogTimer = setInterval(() => fetchLogData(true), 5000);
};

const stopSyslogTimer = () => {
  if (syslogTimer) {
    clearInterval(syslogTimer);
    syslogTimer = null;
  }
};

watch(activeTab, (newTab) => {
  if (newTab === 'result') {
    stopSyslogTimer();
    fetchData();
  } else if (newTab === 'log') {
    startSyslogTimer();
  }
});

onMounted(() => {
  fetchData();
  if (activeTab.value === 'log') {
    startSyslogTimer();
  }
});

onUnmounted(() => {
  stopSyslogTimer();
});
</script>

<style scoped>
.search-row { display: flex; flex-wrap: wrap; gap: 16px 12px; align-items: center; }
.search-item { display: flex; align-items: center; }
.search-item .label { color: var(--arl-text-color); margin-right: 8px; min-width: 60px; text-align: right; white-space: nowrap; }
</style>