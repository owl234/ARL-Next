<!-- ARL-Next/frontend/src/components/platform/ProjectCard.vue -->
<template>
  <a-card hoverable class="project-card">
    <template #title>
      <div class="card-title">
        <PlatformTag :platform="project.platform" />
        <span class="project-name">
          {{ project.project_name || project.project_id }}
        </span>
      </div>
    </template>

    <template #extra>
      <a-tag :color="statusColor">{{ statusLabel }}</a-tag>
    </template>

    <div class="project-info">
      <div class="info-row">
        <span class="label">资产数：</span>
        <span class="value">{{ project.asset_count || 0 }}</span>
      </div>
      <div class="info-row">
        <span class="label">漏洞数：</span>
        <span class="value danger">
          {{ project.vuln_count || 0 }}
        </span>
      </div>
      <div class="info-row">
        <span class="label">创建时间：</span>
        <span class="value">{{ formatTime(project.created_at) }}</span>
      </div>
      <div class="info-row">
        <span class="label">抓取时间：</span>
        <span class="value">{{ formatTime(project.fetched_at) }}</span>
      </div>
    </div>

    <template #actions>
      <a-button type="link" size="small" @click="emit('detail')">
        详情
      </a-button>
      <a-button type="link" size="small" @click="emit('scan')">
        扫描
      </a-button>
      <a-button type="link" size="small" @click="emit('submit')">
        提交漏洞
      </a-button>
    </template>
  </a-card>
</template>

<script setup>
import { computed } from 'vue'
import dayjs from 'dayjs'
import PlatformTag from './PlatformTag.vue'

const props = defineProps({
  project: { type: Object, required: true },
})

const emit = defineEmits(['detail', 'scan', 'submit'])

const STATUS_MAP = {
  active:  { label: '活跃',   color: 'green' },
  expired: { label: '已过期', color: 'default' },
}

const statusLabel = computed(
  () => STATUS_MAP[props.project.status]?.label ||
        props.project.status
)
const statusColor = computed(
  () => STATUS_MAP[props.project.status]?.color || 'default'
)

function formatTime(t) {
  if (!t) return '-'
  return dayjs(t).format('YYYY-MM-DD HH:mm')
}
</script>

<style scoped>
.project-card { margin-bottom: 16px; }
.card-title { display: flex; align-items: center; gap: 8px; }
.project-name { font-weight: 600; }
.project-info { display: flex; flex-direction: column; gap: 6px; }
.info-row { display: flex; justify-content: space-between; font-size: 13px; }
.info-row .label { color: #8c8c8c; }
.info-row .value { color: #262626; font-weight: 500; }
.info-row .value.danger { color: #cf1322; }
</style>