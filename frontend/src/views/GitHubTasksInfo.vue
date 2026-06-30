<template>
  <div style="background-color: #fff; padding: 24px; min-height: calc(100vh - 64px);">
    <a-tabs v-model:activeKey="activeTab" type="card">
      
      <!-- ================= Tab 1: 扫描结果 ================= -->
      <a-tab-pane key="result" tab="扫描结果">
        <div class="search-row" style="margin-bottom: 16px; background-color: #f9f9f9; padding: 16px; border-radius: 4px;">
          <div class="search-item">
            <span class="label">路径名：</span>
            <a-input v-model:value="searchForm.path" placeholder="请输入路径名进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
              <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
            </a-input>
          </div>
          <div class="search-item">
            <span class="label">仓库名：</span>
            <a-input v-model:value="searchForm.repo_full_name" placeholder="请输入仓库名进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
              <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
            </a-input>
          </div>
          <div class="search-item">
            <span class="label">内容：</span>
            <a-input v-model:value="searchForm.human_content" placeholder="请输入内容进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
              <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
            </a-input>
          </div>
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
          <template #emptyText>
            <div style="padding: 40px 0;">
              <inbox-outlined style="font-size: 48px; color: #d9d9d9;" />
              <div style="color: #999; margin-top: 8px;">暂无数据</div>
            </div>
          </template>
          <template #bodyCell="{ column, record, text }">
            <template v-if="column.key === 'repo_full_name'">
              <a :href="`https://github.com/${record.repo_full_name}`" target="_blank" style="color: #00bcd4; word-break: break-all; font-weight: 500;">
                {{ record.repo_full_name }}
              </a>
            </template>
            <template v-else-if="column.key === 'path'">
              <a :href="record.html_url" target="_blank" style="color: #00bcd4; word-break: break-all;">
                {{ record.path }}
              </a>
            </template>
            <template v-else-if="column.key === 'human_content'">
              <div style="white-space: pre-wrap; word-break: break-word; font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace; max-height: 300px; overflow-y: auto; background: #fafafa; padding: 12px; border-radius: 6px; border: 1px solid #f0f0f0; font-size: 13px; line-height: 1.5715; color: #333; margin: 4px 0;">
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
          <div style="color: rgba(0,0,0,.65);">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
          <a-pagination v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" />
        </div>
      </a-tab-pane>

      <!-- ================= Tab 2: 执行日志 ================= -->
      <a-tab-pane key="log" tab="任务日志">
        <div style="margin-bottom: 16px; display: flex; justify-content: flex-end;">
          <a-button type="dashed" @click="fetchLogData">
            <template #icon><sync-outlined /></template>
            刷新日志
          </a-button>
        </div>
        
        <a-table
            :loading="logLoading"
            :dataSource="logDataSource"
            :columns="logColumns"
            :pagination="false"
            size="middle"
            :rowKey="(record) => record._id"
        >
          <template #emptyText>
            <div style="padding: 40px 0;">
              <inbox-outlined style="font-size: 48px; color: #d9d9d9;" />
              <div style="color: #999; margin-top: 8px;">暂无日志数据</div>
            </div>
          </template>
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'level'">
              <a-tag :color="record.level === 'error' ? 'error' : record.level === 'warning' ? 'warning' : 'blue'">
                {{ record.level }}
              </a-tag>
            </template>
          </template>
        </a-table>

        <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
          <div style="color: rgba(0,0,0,.65);">共 {{ Math.ceil(logPagination.total / logPagination.pageSize) || 1 }} 页 / {{ logPagination.total }} 条数据</div>
          <a-pagination v-model:current="logPagination.current" v-model:pageSize="logPagination.pageSize" :total="logPagination.total" show-size-changer @change="handleLogTableChange" />
        </div>
      </a-tab-pane>

    </a-tabs>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch } from 'vue';
import { useRoute } from 'vue-router';
import request from '../utils/request';
import { message } from 'ant-design-vue';
import { SearchOutlined, InboxOutlined, SyncOutlined } from '@ant-design/icons-vue';

const route = useRoute();
const activeTab = ref('result');

const loading = ref(false);
const dataSource = ref([]);

// 🚨 核心：接住上级页面传来的任务 ID
const taskId = route.query._id || '';

const searchForm = reactive({ path: '', repo_full_name: '', human_content: '' });
const pagination = reactive({ current: 1, pageSize: 10, total: 0 });

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
const logPagination = reactive({ current: 1, pageSize: 10, total: 0 });

const logColumns = [
  { title: '时间', dataIndex: 'create_time', key: 'create_time', width: 200 },
  { title: '级别', dataIndex: 'level', key: 'level', width: 100 },
  { title: '标题', dataIndex: 'title', key: 'title', width: 150 },
  { title: '内容', dataIndex: 'message', key: 'message' }
];

const fetchLogData = async () => {
  if (!taskId) return;
  
  logLoading.value = true;
  try {
    const params = {
      page: logPagination.current,
      size: logPagination.pageSize,
      task_id: taskId
    };
    const res = await request.get('/syslog/', { params });
    if (res.code === 200) {
      logDataSource.value = res.items || [];
      logPagination.total = res.total || 0;
    }
  } catch (error) {
    message.error('加载任务日志失败');
  } finally {
    logLoading.value = false;
  }
};

const handleLogTableChange = (page, pageSize) => { logPagination.current = page; logPagination.pageSize = pageSize; fetchLogData(); };

watch(activeTab, (newTab) => {
  if (newTab === 'result') {
    fetchData();
  } else if (newTab === 'log') {
    fetchLogData();
  }
});

onMounted(() => {
  fetchData();
  fetchLogData();
});
</script>

<style scoped>
.search-row { display: flex; flex-wrap: wrap; gap: 16px 12px; align-items: center; }
.search-item { display: flex; align-items: center; }
.search-item .label { color: rgba(0,0,0,0.85); margin-right: 8px; min-width: 60px; text-align: right; white-space: nowrap; }
</style>