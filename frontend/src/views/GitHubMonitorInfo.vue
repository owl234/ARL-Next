<template>
  <div style="background-color: var(--arl-bg-layout); padding: 24px; min-height: calc(100vh - 64px);">
    <div ref="actionBarRef" style="position: sticky; top: 0px; z-index: 10; background-color: var(--arl-bg-layout); margin: -24px -24px 16px -24px; padding: 24px 24px 16px 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">


    <div class="search-row" style="margin-bottom: 16px; ">
      <div class="search-item">
        <span class="label">仓库：</span>
        <a-input v-model:value="searchForm.repo_full_name" placeholder="请输入仓库进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
        </a-input>
      </div>
      <div class="search-item">
        <span class="label">内容：</span>
        <a-input v-model:value="searchForm.human_content" placeholder="请输入内容进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
        </a-input>
      </div>
      <div class="search-item">
        <span class="label">路径：</span>
        <a-input v-model:value="searchForm.path" placeholder="请输入路径进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
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
    </a-table>

    <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
      <div style="color: var(--arl-text-color); opacity: 0.65;">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
      <a-pagination :pageSizeOptions="$pageSizeOptions" v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" />
    </div>

  </div>
</template>

<script setup>

import { ref, reactive, onMounted, watch } from 'vue';
import { useSticky } from '../utils/useSticky';
const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

import { useRoute } from 'vue-router';
import request from '../utils/request';
import { message } from 'ant-design-vue';
import { SearchOutlined, InboxOutlined } from '@ant-design/icons-vue';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';

const route = useRoute();
const loading = ref(false);
const dataSource = ref([]);

// 🚨 核心：接住 GitHub监控列表 传来的 ID
const schedulerId = route.query._id || '';

const searchForm = reactive({ repo_full_name: '', human_content: '', path: '' });
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

// 🚨 表头严格对齐截图：仓库名、路径、内容、关键字、更新时间
const columns = [
  { title: '仓库名', dataIndex: 'repo_full_name', key: 'repo_full_name', width: 200 },
  { title: '路径', dataIndex: 'path', key: 'path', width: 250 },
  { title: '内容', dataIndex: 'human_content', key: 'human_content', width: 350 },
  { title: '关键字', dataIndex: 'keyword', key: 'keyword', width: 150 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 200 }
];

// ================= 数据拉取 =================
const fetchData = async () => {
  if (!schedulerId) return;

  loading.value = true;
  try {
    const params = {
      page: pagination.current,
      size: pagination.pageSize,
      github_scheduler_id: schedulerId // 🚨 监控详情专用参数
    };

    if (searchForm.repo_full_name) params.repo_full_name = searchForm.repo_full_name;
    if (searchForm.human_content) params.human_content = searchForm.human_content;
    if (searchForm.path) params.path = searchForm.path;

    // 🚨 监控详情专用 API
    const res = await request.get('/github_monitor_result/', { params });
    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
      selectedRowKeys.value = [];
    }
  } catch (error) {
    message.error('加载监控详情失败');
  } finally {
    loading.value = false;
  }
};

const onSearch = () => { pagination.current = 1; fetchData(); };
const handleTableChange = (page, pageSize) => { pagination.current = page; pagination.pageSize = pageSize; fetchData(); };

onMounted(() => {
  fetchData();
});
</script>

<style scoped>
.search-row { display: flex; flex-wrap: wrap; gap: 16px 12px; align-items: center; }
.search-item { display: flex; align-items: center; }
.search-item .label { color: var(--arl-text-color); margin-right: 8px; min-width: 60px; text-align: right; white-space: nowrap; }
</style>