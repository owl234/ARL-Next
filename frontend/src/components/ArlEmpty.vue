<template>
  <div class="arl-empty-wrap" :class="{ 'is-compact': compact }">
    <a-empty :image="Empty.PRESENTED_IMAGE_SIMPLE" :description="description">
      <slot />
    </a-empty>
  </div>
</template>

<script setup>
import { Empty } from 'ant-design-vue';

defineProps({
  description: {
    type: String,
    default: undefined,
  },
  compact: {
    type: Boolean,
    default: false,
  },
});
</script>

<style scoped>
.arl-empty-wrap {
  padding: 20px 0;
  display: flex;
  align-items: center;
  justify-content: center;
}
.arl-empty-wrap.is-compact {
  padding: 8px 0;
}
.arl-empty-wrap :deep(.ant-empty) {
  margin-block: 0;
}
.arl-empty-wrap :deep(.ant-empty-description) {
  color: var(--arl-text-secondary);
  font-size: 13px;
}
</style>
