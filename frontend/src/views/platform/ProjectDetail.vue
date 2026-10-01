<!-- ARL-Next/frontend/src/views/platform/ProjectDetail.vue -->
<template>
  <div class="project-detail">
    <a-page-header
      :title="project.project_name || project.project_id"
      @back="router.back()"
    >
      <template #tags>
        <PlatformTag :platform="project.platform" />
        <a-tag
          :color="project.status === 'active' ? 'green' : 'default'"
        >
          {{ project.status }}
        </a-tag>
      </template>

      <template #extra>
        <a-space>
          <a-button @click="handleScan">
            <ThunderboltOutlined /> 下发扫描
          </a-button>
          <a-button type="primary" @click="handleSubmit">
            <CloudUploadOutlined /> 提交漏洞
          </a-button>
        </a-space>
      </template>
    </a-page-header>

    <a-tabs v-model:activeKey="activeTab">
      <a-tab-pane key="overview" tab="概览">
        <a-descriptions bordered :column="2">
          <a-descriptions-item label="项目 ID">
            {{ project.project_id }}
          </a-descriptions-item>
          <a-descriptions-item label="来源平台">
            <PlatformTag :platform="project.platform" />
          </a-descriptions-item>
          <a-descriptions-item label="资产数">
            {{ project.asset_count || 0 }}
          </a-descriptions-item>
          <a-descriptions-item label="漏洞数">
            {{ project.vuln_count || 0 }}
          </a-descriptions-item>
          <a-descriptions-item label="创建时间">
            {{ formatTime(project.created_at) }}
          </a-descriptions-item>
          <a-descriptions-item label="更新时间">
            {{ formatTime(project.updated_at) }}
          </a-descriptions-item>
          <a-descriptions-item label="抓取时间">
            {{ formatTime(project.fetched_at) }}
          </a-descriptions-item>
          <a-descriptions-item label="上次扫描">
            {{ formatTime(project.last_scan_at) }}
          </a-descriptions-item>
        </a-descriptions>

        <a-divider>测试范围</a-divider>
        <a-list
          size="small"
          bordered
          :data-source="project.scope || []"
        >
          <template #renderItem="{ item }">
            <a-list-item>{{ item }}</a-list-item>
          </template>
        </a-list>
      </a-tab-pane>

      <a-tab-pane key="targets" tab="目标列表">
        <a-table
          :columns="targetColumns"
          :data-source="targets"
          :loading="loading.targets"
          row-key="_id"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'scanned'">
              <a-tag :color="record.scanned ? 'green' : 'default'">
                {{ record.scanned ? '已扫描' : '待扫描' }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'target_type'">
              <a-tag>{{ record.target_type }}</a-tag>
            </template>
            <template v-else-if="column.key === 'created_at'">
              {{ formatTime(record.created_at) }}
            </template>
          </template>
        </a-table>
      </a-tab-pane>

      <a-tab-pane key="vulns" tab="漏洞列表">
        <a-table
          :columns="vulnColumns"
          :data-source="project.vulns || []"
          row-key="_id"
          size="small"
        >
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'severity'">
              <SeverityTag :severity="record.severity" />
            </template>
            <template v-else-if="column.key === 'submit_status'">
              <a-tag :color="submitStatusColor(record.submit_status)">
                {{ record.submit_status || '待提交' }}
              </a-tag>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-button
                type="link"
                size="small"
                :disabled="record.submit_status === 'submitted'"
                @click="handleSubmitVuln(record)"
              >
                提交
              </a-button>
            </template>
          </template>
        </a-table>
      </a-tab-pane>
    </a-tabs>

    <a-modal
      v-model:open="scanModal.visible"
      title="扫描配置"
      @ok="handleScanConfirm"
    >
      <a-form :model="scanModal.form" layout="vertical">
        <a-form-item label="扫描策略">
          <a-radio-group v-model:value="scanModal.form.profile">
            <a-radio value="quick">快速侦察</a-radio>
            <a-radio value="full">深度扫描</a-radio>
            <a-radio value="incremental">增量复扫</a-radio>
          </a-radio-group>
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { message } from 'ant-design-vue'
import {
  ThunderboltOutlined,
  CloudUploadOutlined,
} from '@ant-design/icons-vue'
import dayjs from 'dayjs'
import PlatformTag from '@/components/platform/PlatformTag.vue'
import SeverityTag from '@/components/platform/SeverityTag.vue'
import { usePlatformStore } from '@/stores/platform'

const route = useRoute()
const router = useRouter()
const store = usePlatformStore()

const { projectDetail, targets, loading } = storeToRefs(store)
const {
  loadProjectDetail,
  loadTargets,
  triggerScan,
  submitAllProjectVulns,
  submitSingleVuln,
} = store

const activeTab = ref('overview')
const fingerprint = route.params.fingerprint

const project = computed(() => projectDetail.value || {})

const scanModal = reactive({
  visible: false,
  form: { profile: 'quick' },
})

const targetColumns = [
  { title: '目标', dataIndex: 'target', key: 'target',
    ellipsis: true },
  { title: '类型', key: 'target_type', width: 80 },
  { title: '状态', key: 'scanned', width: 100 },
  { title: '创建时间', key: 'created_at', width: 160 },
]

const vulnColumns = [
  { title: '目标 URL', dataIndex: 'target_url',
    key: 'target_url', ellipsis: true },
  { title: '模板 ID', dataIndex: 'template_id',
    key: 'template_id', width: 180 },
  { title: '等级', key: 'severity', width: 80 },
  { title: '提交状态', key: 'submit_status', width: 100 },
  { title: '操作', key: 'action', width: 80 },
]

onMounted(async () => {
  await loadProjectDetail(fingerprint)
  await loadTargets({ project_fingerprint: fingerprint })
})

function handleScan() {
  scanModal.form.profile = 'quick'
  scanModal.visible = true
}

async function handleScanConfirm() {
  try {
    await triggerScan(fingerprint, scanModal.form)
    message.success('扫描任务已下发')
    scanModal.visible = false
  } catch (e) {
    message.error(e.message)
  }
}

async function handleSubmit() {
  try {
    const result = await submitAllProjectVulns(fingerprint)
    message.success(
      `提交完成：成功 ${result.success || 0}，` +
      `失败 ${result.failed || 0}`
    )
    await loadProjectDetail(fingerprint)
  } catch (e) {
    message.error(e.message)
  }
}

async function handleSubmitVuln(vuln) {
  try {
    await submitSingleVuln(vuln._id)
    message.success('提交成功')
    await loadProjectDetail(fingerprint)
  } catch (e) {
    message.error(e.message)
  }
}

function formatTime(t) {
  if (!t) return '-'
  return dayjs(t).format('YYYY-MM-DD HH:mm:ss')
}

function submitStatusColor(status) {
  return {
    submitted: 'green',
    failed: 'red',
    pending: 'orange',
  }[status] || 'default'
}
</script>

<style scoped>
.project-detail { padding: 16px; }
</style>