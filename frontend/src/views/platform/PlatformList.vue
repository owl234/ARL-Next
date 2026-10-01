<!-- ARL-Next/frontend/src/views/platform/PlatformList.vue -->
<template>
  <div class="platform-list">
    <a-row :gutter="16">
      <a-col
        v-for="p in platforms"
        :key="p.name"
        :xs="24" :sm="12" :md="8" :lg="6"
      >
        <a-card class="platform-card">
          <template #title>
            <PlatformTag :platform="p.name" />
            <span style="margin-left: 8px">
              {{ p.display_name || p.name }}
            </span>
          </template>
          <template #extra>
            <a-tag color="green">启用</a-tag>
          </template>

          <div class="platform-info">
            <div class="info-row">
              <span class="label">速率限制：</span>
              <span class="value">{{ p.rate_limit || '-' }}</span>
            </div>
            <div class="info-row">
              <span class="label">默认延迟：</span>
              <span class="value">
                {{ p.default_delay || '-' }} s
              </span>
            </div>
            <div class="info-row">
              <span class="label">需登录：</span>
              <span class="value">
                {{ p.requires_login ? '是' : '否' }}
              </span>
            </div>
          </div>

          <template #actions>
            <a-button
              type="link"
              size="small"
              @click="handleFetch(p.name)"
            >
              抓取项目
            </a-button>
          </template>
        </a-card>
      </a-col>
    </a-row>
  </div>
</template>

<script setup>
import { onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { message } from 'ant-design-vue'
import PlatformTag from '@/components/platform/PlatformTag.vue'
import { usePlatformStore } from '@/stores/platform'

const store = usePlatformStore()
const { platforms } = storeToRefs(store)
const { loadPlatforms, triggerFetch } = store

onMounted(() => {
  loadPlatforms()
})

async function handleFetch(name) {
  try {
    await triggerFetch({ platform: name })
    message.success(`已触发 ${name} 抓取`)
  } catch (e) {
    message.error(e.message)
  }
}
</script>

<style scoped>
.platform-list { padding: 16px; }
.platform-card { margin-bottom: 16px; }
.platform-info { display: flex; flex-direction: column; gap: 6px; }
.info-row { display: flex; justify-content: space-between; font-size: 13px; }
.info-row .label { color: #8c8c8c; }
.info-row .value { color: #262626; font-weight: 500; }
</style>