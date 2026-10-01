<!-- ARL-Next/frontend/src/views/platform/SubmitRecords.vue -->
<template>
  <div class="submit-records">
    <div class="toolbar">
      <a-space>
        <a-select
          v-model:value="filter.platform"
          placeholder="选择平台"
          style="width: 160px"
          allow-clear
          @change="handleFilterChange"
        >
          <a-select-option
            v-for="p in enabledPlatforms"
            :key="p.name"
            :value="p.name"
          >
            {{ p.display_name || p.name }}
          </a-select-option>
        </a-select>

        <a-select
          v-model:value="filter.status"
          placeholder="提交状态"
          style="width: 140px"
          allow-clear
          @change="handleFilterChange"
        >
          <a-select-option value="submitted">已提交</a-select-option>
          <a-select-option value="failed">失败</a-select-option>
        </a-select>
      </a-space>

      <a-button @click="loadRecords">
        <template #icon><ReloadOutlined /></template>
        刷新
      </a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="submitRecords"
      :loading="loading.submitRecords"
      :pagination="paginationConfig"
      row-key="_id"
      @change="handleTableChange"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'platform'">
          <PlatformTag :platform="record.platform" />
        </template>
        <template v-else-if="column.key === 'source_platform'">
          <PlatformTag :platform="record.source_platform" />
        </template>
        <template v-else-if="column.key === 'success'">
          <a-tag :color="record.success ? 'green' : 'red'">
            {{ record.success ? '成功' : '失败' }}
          </a-tag>
        </template>
        <template v-else-if="column.key === 'created_at'">
          {{ formatTime(record.created_at) }}
        </template>
        <template v-else-if="column.key === 'message'">
          <a-tooltip :title="record.message">
            <span class="message-ellipsis">
              {{ record.message || '-' }}
            </span>
          </a-tooltip>
        </template>
      </template>
    </a-table>
  </div>
</template>

<script setup>
import { reactive, computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { ReloadOutlined } from '@ant-design/icons-vue'
import dayjs from 'dayjs'
import PlatformTag from '@/components/platform/PlatformTag.vue'
import { usePlatformStore } from '@/stores/platform'

const store = usePlatformStore()

const {
  submitRecords,
  recordTotal,
  loading,
  enabledPlatforms,
} = storeToRefs(store)

const {
  loadPlatforms,
  loadSubmitRecords,
} = store

const filter = reactive({
  platform: undefined,
  status: undefined,
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
})

const columns = [
  { title: '漏洞 ID', dataIndex: 'vuln_id',
    key: 'vuln_id', width: 200, ellipsis: true },
  { title: '目标平台', key: 'platform', width: 100 },
  { title: '来源平台', key: 'source_platform', width: 100 },
  { title: '结果', key: 'success', width: 80 },
  { title: '平台编号', dataIndex: 'platform_vuln_id',
    key: 'platform_vuln_id', width: 160 },
  { title: '消息', key: 'message', ellipsis: true },
  { title: '创建时间', key: 'created_at', width: 160 },
]

const paginationConfig = computed(() => ({
  current: pagination.page,
  pageSize: pagination.pageSize,
  total: recordTotal.value,
  showSizeChanger: true,
  showTotal: (t) => `共 ${t} 条`,
}))

onMounted(() => {
  loadPlatforms()
  loadRecords()
})

async function loadRecords() {
  await loadSubmitRecords({
    platform: filter.platform,
    status: filter.status,
    page: pagination.page,
    page_size: pagination.pageSize,
  })
}

function handleFilterChange() {
  pagination.page = 1
  loadRecords()
}

function handleTableChange(pag) {
  pagination.page = pag.current
  pagination.pageSize = pag.pageSize
  loadRecords()
}

function formatTime(t) {
  if (!t) return '-'
  return dayjs(t).format('YYYY-MM-DD HH:mm:ss')
}
</script>

<style scoped>
.submit-records { padding: 16px; }
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.message-ellipsis {
  display: inline-block;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
</style>