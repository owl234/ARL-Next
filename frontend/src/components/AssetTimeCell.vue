<template>
  <span v-if="!primaryTime" class="arl-time-empty">-</span>
  <a-tooltip v-else-if="showSecondaryLine" placement="topLeft">
    <template #title>
      <div class="arl-time-tooltip">
        <div>{{ t('tasks.discoveredAt') }}: {{ primaryTime }}</div>
        <div>{{ secondaryFullLabel }}: {{ secondaryTime }}</div>
      </div>
    </template>
    <span :class="['arl-time-cell', { 'is-inline': inline }]">
      <span class="arl-time-primary">{{ primaryTime }}</span>
      <span class="arl-time-secondary">{{ secondaryShortLabel }}: {{ secondaryTime }}</span>
    </span>
  </a-tooltip>
  <span v-else class="arl-time-cell">
    <span class="arl-time-primary">{{ primaryTime }}</span>
  </span>
</template>

<script setup>
import { computed } from 'vue';
import { useI18n } from 'vue-i18n';

const { t } = useI18n({ useScope: 'global' });

const props = defineProps({
  record: {
    type: Object,
    default: () => ({})
  },
  showSecondary: {
    type: Boolean,
    default: false
  },
  secondaryMode: {
    type: String,
    default: 'update' // 'update' | 'latest'
  },
  inline: {
    type: Boolean,
    default: false
  }
});

const normalizeTimeText = (val) => {
  if (val == null || val === '') return '';
  const text = String(val).trim();
  if (!text || text === 'None' || text === 'null' || text === 'undefined') return '';
  return text.replace(/\.\d+$/, '');
};

const primaryTime = computed(() => {
  const rec = props.record || {};
  return (
    normalizeTimeText(rec.save_date) ||
    normalizeTimeText(rec.update_date) ||
    normalizeTimeText(rec.insert_time)
  );
});

const secondaryTime = computed(() => {
  const rec = props.record || {};
  return normalizeTimeText(rec.update_date);
});

const showSecondaryLine = computed(() => {
  return Boolean(
    props.showSecondary &&
    primaryTime.value &&
    secondaryTime.value &&
    secondaryTime.value !== primaryTime.value
  );
});

const secondaryShortLabel = computed(() => {
  return props.secondaryMode === 'latest'
    ? t('assets.latestShortPrefix')
    : t('assets.updatedShortPrefix');
});

const secondaryFullLabel = computed(() => {
  return props.secondaryMode === 'latest'
    ? t('assets.latestShortPrefix')
    : t('assets.updatedAtLabel');
});
</script>

<style scoped>
.arl-time-cell {
  display: inline-flex;
  flex-direction: column;
  gap: 2px;
  line-height: 1.35;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}

.arl-time-cell.is-inline {
  flex-direction: row;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 6px;
}

.arl-time-primary {
  font-size: 12.5px;
  color: var(--arl-text-color);
}

.arl-time-secondary {
  font-size: 11px;
  color: var(--arl-text-secondary, rgba(140, 140, 140, 0.9));
  opacity: 0.85;
}

.arl-time-empty {
  color: var(--arl-text-secondary, rgba(140, 140, 140, 0.65));
}

.arl-time-tooltip {
  font-size: 12px;
  line-height: 1.6;
  font-variant-numeric: tabular-nums;
}
</style>
