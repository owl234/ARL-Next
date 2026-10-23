<template>
  <a-drawer :open="open" :title="t('wihApi.title')" width="min(760px, 100vw)" @close="$emit('update:open', false)">
    <div v-if="open" class="wih-api-details">
      <a-alert type="info" show-icon :message="t('wihApi.observationNotice')" />
      <a-alert v-if="details.legacy" type="warning" show-icon :message="t('wihApi.legacyNotice')" />
      <a-descriptions bordered size="small" :column="1">
        <a-descriptions-item :label="t('wihApi.state')">
          <a-tag :color="stateColor">{{ t(`wihApi.${details.stateKey}`) }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item :label="t('wihApi.method')"><code>{{ details.method || missing }}</code></a-descriptions-item>
        <a-descriptions-item :label="t('wihApi.url')">
          <div class="wih-api-value">
            <code>{{ details.url || missing }}</code>
            <a-button v-if="details.url" type="link" size="small" @click="copyValue(details.url)">{{ t('wihApi.copy') }}</a-button>
          </div>
        </a-descriptions-item>
        <a-descriptions-item :label="t('wihApi.path')"><code>{{ details.path || missing }}</code></a-descriptions-item>
        <a-descriptions-item :label="t('wihApi.site')"><code>{{ details.site || missing }}</code></a-descriptions-item>
        <a-descriptions-item :label="t('wihApi.source')"><code>{{ details.source || missing }}</code></a-descriptions-item>
        <a-descriptions-item :label="t('wihApi.client')">{{ details.client || missing }}</a-descriptions-item>
        <a-descriptions-item :label="t('wihApi.line')">{{ details.line ?? missing }}</a-descriptions-item>
        <a-descriptions-item v-if="details.legacy" :label="t('wihApi.originalContent')"><pre>{{ details.content || missing }}</pre></a-descriptions-item>
        <a-descriptions-item :label="t('wihApi.statusCode')">{{ details.statusCode ?? missing }}</a-descriptions-item>
        <a-descriptions-item :label="t('wihApi.responseUrl')"><code>{{ details.responseUrl || missing }}</code></a-descriptions-item>
        <a-descriptions-item :label="t('wihApi.lastAttemptUrl')"><code>{{ details.lastAttemptUrl || missing }}</code></a-descriptions-item>
        <a-descriptions-item :label="t('wihApi.checkedAt')">{{ details.checkedAt || missing }}</a-descriptions-item>
        <a-descriptions-item :label="t('wihApi.elapsed')">{{ details.elapsedMs === null ? missing : t('wihApi.milliseconds', { value: details.elapsedMs }) }}</a-descriptions-item>
        <a-descriptions-item v-if="details.reason" :label="t('wihApi.skipReason')">{{ reasonText(details.reason) }}</a-descriptions-item>
        <a-descriptions-item v-if="details.error" :label="t('wihApi.requestErrorLabel')">{{ reasonText(details.error) }}</a-descriptions-item>
        <a-descriptions-item v-if="details.redirectStop" :label="t('wihApi.redirectStop')">{{ reasonText(details.redirectStop) }}</a-descriptions-item>
      </a-descriptions>

      <section v-if="details.redirects.length">
        <h3>{{ t('wihApi.redirects') }}</h3>
        <ol class="wih-api-redirects">
          <li v-for="(hop, index) in details.redirects" :key="index"><code>{{ hop.statusCode ?? missing }} {{ hop.url || missing }}</code></li>
        </ol>
      </section>
      <section>
        <div class="wih-api-heading">
          <h3>{{ t('wihApi.headers') }}</h3>
          <a-button v-if="details.headers" type="link" size="small" @click="copyValue(details.headers)">{{ t('wihApi.copy') }}</a-button>
        </div>
        <pre v-if="details.headers">{{ details.headers }}</pre>
        <p v-else class="wih-api-muted">{{ t('wihApi.noHeaders') }}</p>
      </section>
      <section>
        <div class="wih-api-heading">
          <h3>{{ t('wihApi.body') }}</h3>
          <a-button v-if="details.bodyCollected && details.body" type="link" size="small" @click="copyValue(details.body)">{{ t('wihApi.copy') }}</a-button>
        </div>
        <p v-if="details.bodyBytes !== null" class="wih-api-muted">{{ t('wihApi.bodyBytes', { count: details.bodyBytes }) }}</p>
        <a-alert v-if="details.bodyTruncated" type="warning" show-icon :message="t('wihApi.bodyIncomplete')" />
        <a-alert v-if="details.bodyError" type="warning" show-icon :message="t('wihApi.bodyReadError', { reason: reasonText(details.bodyError) })" />
        <pre v-if="details.bodyCollected && details.body">{{ details.body }}</pre>
        <p v-else-if="details.bodySkipped" class="wih-api-muted">{{ reasonText(details.bodySkipped) }}</p>
        <p v-else class="wih-api-muted">{{ t(details.bodyCollected ? 'wihApi.emptyBody' : 'wihApi.noBody') }}</p>
      </section>
    </div>
  </a-drawer>
</template>

<script setup>
import { computed, onDeactivated, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { message } from 'ant-design-vue';
import { copyText } from '../utils/clipboard';
import { getWihApiDetails, PROBE_REASON_KEYS } from '../utils/wihApi';

const props = defineProps({
  open: { type: Boolean, required: true },
  record: { type: Object, default: null },
  contextKey: { type: String, default: '' },
});
const emit = defineEmits(['update:open']);
const { t } = useI18n({ useScope: 'global' });
const missing = '—';
const details = computed(() => getWihApiDetails(props.record));
const stateColor = computed(() => ({ responded: 'blue', error: 'orange' }[details.value.state] || 'default'));
const reasonText = reason => Object.hasOwn(PROBE_REASON_KEYS, reason)
  ? t(`wihApi.${PROBE_REASON_KEYS[reason]}`) : t('wihApi.unknownReason', { reason });
watch(() => props.contextKey, () => emit('update:open', false));
onDeactivated(() => emit('update:open', false));

const copyValue = async value => {
  try {
    if (await copyText(value)) {
      message.success(t('wihApi.copied'));
      return;
    }
  } catch {
    // 浏览器拒绝剪贴板权限时保留详情，提示用户手动复制。
  }
  message.warning(t('wihApi.copyFailed'));
};
</script>

<style scoped>
.wih-api-details { display: flex; flex-direction: column; gap: 16px; }
.wih-api-details code, .wih-api-details pre { overflow-wrap: anywhere; word-break: break-word; }
.wih-api-details pre { white-space: pre-wrap; max-height: 360px; overflow: auto; background: var(--arl-bg-light); padding: 12px; border-radius: 6px; margin: 8px 0 0; }
.wih-api-details h3 { margin: 0; font-size: 14px; }
.wih-api-value, .wih-api-heading { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.wih-api-value code { min-width: 0; }
.wih-api-value :deep(.ant-btn) { flex-shrink: 0; }
.wih-api-muted { color: var(--arl-text-color); opacity: 0.65; margin: 8px 0 0; }
.wih-api-redirects { margin: 8px 0 0; padding-inline-start: 24px; }
</style>
