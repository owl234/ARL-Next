<!-- ARL-Next/frontend/src/components/platform/PlatformTag.vue -->
<template>
  <a-tag :color="color">{{ label }}</a-tag>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  platform: { type: String, required: true },
})

const PLATFORM_MAP = {
  butian:    { label: '补天',      color: 'blue' },
  vulbox:    { label: '漏洞盒子',  color: 'green' },
  cnvd:      { label: 'CNVD',      color: 'orange' },
  edusrc:    { label: 'EduSRC',    color: 'purple' },
  hackerone: { label: 'HackerOne', color: 'red' },
  generic:   { label: '通用',      color: 'default' },
}

const label = computed(
  () => PLATFORM_MAP[props.platform]?.label || props.platform
)
const color = computed(
  () => PLATFORM_MAP[props.platform]?.color || 'default'
)
</script>