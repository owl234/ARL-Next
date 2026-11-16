<template>
  <div
    class="settings-action-bar"
    :data-setting-anchor="anchor || undefined"
  >
    <span v-if="description" class="settings-action-desc">{{ description }}</span>
    <span v-else></span>
    <div class="settings-action-controls">
      <slot name="extra-actions" />
      <a-tag v-if="dirty" color="warning" style="margin: 0;">
        {{ pageText('pages.unsavedChanges') }}
      </a-tag>
      <a-popconfirm
        v-if="dirty"
        :title="pageText('pages.confirmResetSectionChanges')"
        :ok-text="pageText('pages.confirmResetBtn')"
        :cancel-text="pageText('pages.cancel')"
        ok-type="danger"
        @confirm="emit('reset')"
      >
        <a-button :disabled="saving">{{ pageText('pages.reset') }}</a-button>
      </a-popconfirm>
      <a-button
        type="primary"
        :disabled="!dirty"
        :loading="saving"
        :class="{ 'arl-dirty-btn': dirty }"
        @click="emit('save')"
      >
        {{ saveLabel }}
      </a-button>
    </div>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';

defineProps({
  description: {
    type: String,
    default: '',
  },
  saveLabel: {
    type: String,
    required: true,
  },
  dirty: {
    type: Boolean,
    default: false,
  },
  saving: {
    type: Boolean,
    default: false,
  },
  anchor: {
    type: String,
    default: '',
  },
});

const emit = defineEmits(['save', 'reset']);
const { t: pageText } = useI18n({ useScope: 'global' });
</script>

<style scoped>
.settings-action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
  margin-bottom: 16px;
  border-radius: 6px;
}

.settings-action-desc {
  color: var(--arl-text-color);
  opacity: 0.55;
  font-size: 13px;
}

.settings-action-controls {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
