<!-- ARL-Next/frontend/src/views/platform/ProjectDashboard.vue -->
<template>
  <div class="project-dashboard">
    <a-row :gutter="16" class="stats-row">
      <a-col :span="6">
        <a-statistic title="项目总数" :value="projectTotal" />
      </a-col>
      <a-col :span="6">
        <a-statistic
          title="活跃项目"
          :value="projectStats.byStatus.active"
        />
      </a-col>
      <a-col :span="6">
        <a-statistic
          title="已过期"
          :value="projectStats.byStatus.expired"
        />
      </a-col>
      <a-col :span="6">
        <a-statistic
          title="平台数"
          :value="enabledPlatforms.length"
        />
      </a-col>
    </a-row>

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
          placeholder="项目状态"
          style="width: 140px"
          allow-clear
          @change="handleFilterChange"
        >
          <a-select-option value="active">活跃</a-select-option>
          <a-select-option value="expired">已过期</a-select-option>
        </a-select>

        <a-input-search
          v-model:value="filter.keyword"
          placeholder="搜索项目名称"
          style="width: 240px"
          @search="handleFilterChange"
        />
      </a-space>

      <a-space>
        <a-button
          type="primary"
          :loading="loading.projects"
          @click="handleFetchAll"
        >
          <template #icon><ReloadOutlined /></template>
          抓取全部平台
        </a-button>
        <a-dropdown>
          <a-button>
            单平台抓取 <DownOutlined />
          </a-button>
          <template #overlay>
            <a-menu @click="handleFetchOne">
              <a-menu-item
                v-for="p in enabledPlatforms"
                :key="p.name"
              >
                {{ p.display_name || p.name }}
              </a-menu-item>
            </a-menu>
          </template>
        </a-dropdown>
      </a-space>
    </div>

    <a-spin :spinning="loading.projects">
      <a-row :gutter="16">
        <a-col
          v-for="project in projects"
          :key="project.fingerprint"
          :xs="24" :sm="12" :md="8" :lg="6"
        >
          <ProjectCard
            :project="project"
            @detail="handleDetail(project)"
            @scan="handleScan(project)"
            @submit="handleSubmit(project)"
          />
        </a-col>
      </a-row>

      <a-empty
        v-if="!loading.projects && projects.length === 0"
      />
    </a-spin>

    <div class="pagination">
      <a-pagination
        v-model:current="pagination.page"
        v-model:page-size="pagination.pageSize"
        :total="projectTotal"
        :show-size-changer="true"
        :show-total="(t) => `共 ${t} 个`"
        @change="loadProjects"
      />
    </div>

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
import { ref, reactive, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import { message, Modal } from 'ant-design-vue'
import {
  ReloadOutlined,
  DownOutlined,
} from '@ant-design/icons-vue'
import ProjectCard from '@/components/platform/ProjectCard.vue'
import { usePlatformStore } from '@/stores/platform'

const router = useRouter()
const store = usePlatformStore()

// ★ state 和 getters 用 storeToRefs 解构
const {
  projects,
  projectTotal,
  projectStats,
  enabledPlatforms,
  loading,
} = storeToRefs(store)

// ★ actions 直接解构
const {
  loadPlatforms,
  loadProjects: storeLoadProjects,
  triggerFetch,
  triggerScan,
  submitAllProjectVulns,
} = store

const filter = reactive({
  platform: undefined,
  status: undefined,
  keyword: '',
})

const pagination = reactive({
  page: 1,
  pageSize: 20,
})

const scanModal = reactive({
  visible: false,
  fingerprint: '',
  form: {
    profile: 'quick',
  },
})

onMounted(async () => {
  await loadPlatforms()
  await loadProjects()
})

async function loadProjects() {
  await storeLoadProjects({
    platform: filter.platform,
    status: filter.status,
    keyword: filter.keyword,
    page: pagination.page,
    page_size: pagination.pageSize,
  })
}

function handleFilterChange() {
  pagination.page = 1
  loadProjects()
}

async function handleFetchAll() {
  try {
    await triggerFetch({})
    message.success('已触发全平台抓取')
    setTimeout(loadProjects, 3000)
  } catch (e) {
    message.error(e.message)
  }
}

async function handleFetchOne({ key }) {
  try {
    await triggerFetch({ platform: key })
    message.success(`已触发 ${key} 抓取`)
    setTimeout(loadProjects, 3000)
  } catch (e) {
    message.error(e.message)
  }
}

function handleDetail(project) {
  router.push(`/platform/projects/${project.fingerprint}`)
}

function handleScan(project) {
  scanModal.fingerprint = project.fingerprint
  scanModal.form.profile = 'quick'
  scanModal.visible = true
}

async function handleScanConfirm() {
  try {
    await triggerScan(scanModal.fingerprint, scanModal.form)
    message.success('扫描任务已下发')
    scanModal.visible = false
  } catch (e) {
    message.error(e.message)
  }
}

function handleSubmit(project) {
  Modal.confirm({
    title: '确认提交漏洞',
    content:
      `将项目「${project.project_name}」的所有未提交漏洞` +
      `提交到 ${project.platform} 平台？`,
    async onOk() {
      try {
        const result = await submitAllProjectVulns(
          project.fingerprint)
        message.success(
          `提交完成：成功 ${result.success || 0}，` +
          `失败 ${result.failed || 0}`
        )
      } catch (e) {
        message.error(e.message)
      }
    },
  })
}
</script>

<style scoped>
.project-dashboard { padding: 16px; }
.stats-row { margin-bottom: 16px; }
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.pagination { margin-top: 24px; text-align: right; }
</style>