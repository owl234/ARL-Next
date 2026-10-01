<!-- ARL-Next/frontend/src/components/platform/SeverityTag.vue -->
<template>
  <a-tag :color="color">{{ label }}</a-tag>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  severity: { type: String, default: 'info' },
})

const SEVERITY_MAP = {
  critical: { label: '严重', color: 'red' },
  high:     { label: '高危', color: 'orange' },
  medium:   { label: '中危', color: 'gold' },
  low:      { label: '低危', color: 'blue' },
  info:     { label: '信息', color: 'default' },
}

const label = computed(() => {
  const key = (props.severity || '').toLowerCase()
  return SEVERITY_MAP[key]?.label || props.severity
})
const color = computed(() => {
  const key = (props.severity || '').toLowerCase()
  return SEVERITY_MAP[key]?.color || 'default'
})
</script>