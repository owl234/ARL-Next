<template>
  <a-modal
    :open="open"
    @update:open="$emit('update:open', $event)"
    :title="modalTitle"
    :footer="null"
    width="820px"
    centered
    destroyOnClose
  >
    <div style="margin-bottom: 16px; display: flex; justify-content: space-between; align-items: center; gap: 12px; flex-wrap: wrap;">
      <a-input
        v-model:value="searchKeyword"
        :placeholder="taskText('tasks.searchIpPortProductVersion')"
        style="width: 280px;"
        allowClear
      >
        <template #prefix>
          <SearchOutlined style="color: var(--arl-text-color); opacity: 0.45;" />
        </template>
      </a-input>

      <div style="display: flex; gap: 8px; align-items: center;">
        <span style="font-size: 13px; color: var(--arl-text-color); opacity: 0.65;">
          {{ taskText('tasks.showing') }} {{ filteredList.length }} / {{ totalCount }} {{ taskText('tasks.itemsLabel') }}
        </span>
        <a-button type="primary" ghost size="small" @click="copyAllEndpoints">
          <CopyOutlined /> {{ copyButtonText }}
        </a-button>
      </div>
    </div>

    <a-table
      :dataSource="filteredList"
      :columns="columns"
      :pagination="pagination"
      size="small"
      :scroll="{ y: 420 }"
      :rowKey="(record, idx) => `${record.ip}:${record.port_id}_${idx}`"
    >
      <template #bodyCell="{ column, record, index }">
        <template v-if="column.key === 'index'">
          {{ (pagination.current - 1) * pagination.pageSize + index + 1 }}
        </template>

        <template v-else-if="column.key === 'ip_port'">
          <div style="display: flex; align-items: center; gap: 6px;">
            <a
              v-if="isWebEndpoint(record)"
              :href="getEndpointUrl(record)"
              target="_blank"
              rel="noopener noreferrer"
              style="font-family: var(--arl-font-mono); font-size: 13px; text-decoration: underline;"
            >
              {{ record.ip }}:{{ record.port_id }}
            </a>
            <span v-else style="font-family: var(--arl-font-mono); font-size: 13px;">
              {{ record.ip }}:{{ record.port_id }}
            </span>
          </div>
        </template>

        <template v-else-if="column.key === 'product'">
          <span>{{ record.product || '-' }}</span>
        </template>

        <template v-else-if="column.key === 'version'">
          <span>{{ record.version || '-' }}</span>
        </template>

        <template v-else-if="column.key === 'action'">
          <a-button
            type="link"
            size="small"
            style="padding: 0; font-size: 12px;"
            @click="copySingleEndpoint(record)"
          >
            <CopyOutlined /> {{ taskText('tasks.copy') }}
          </a-button>
        </template>
      </template>
    </a-table>
  </a-modal>
</template>

<script setup>
import { useI18n } from 'vue-i18n';

import { ref, computed, watch, reactive, getCurrentInstance } from 'vue';
import { message } from 'ant-design-vue';
import { SearchOutlined, CopyOutlined } from '@ant-design/icons-vue';
import { copyText } from '../utils/clipboard';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';

const { t: taskText } = useI18n({ useScope: 'global' });
const pageSizeOptions = getCurrentInstance()?.appContext.config.globalProperties.$pageSizeOptions || ['10', '20', '50', '100', '200', '500'];
const globalPageSize = useGlobalPageSize(10);

const props = defineProps({
  open: { type: Boolean, required: true },
  record: { type: Object, default: () => ({}) }
});

defineEmits(['update:open']);

const searchKeyword = ref('');

const pagination = reactive({
  current: 1,
  pageSize: globalPageSize.value,
  size: 'small',
  showSizeChanger: true,
  pageSizeOptions,
  showTotal: (total) => taskText('tasks.totalCount', { count: total }),
  onChange: (page, pageSize) => {
    pagination.current = page;
    if (pageSize && pageSize !== pagination.pageSize) {
      pagination.pageSize = pageSize;
    }
    if (pagination.pageSize !== globalPageSize.value) {
      globalPageSize.value = pagination.pageSize;
    }
  }
});

watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
});

const totalCount = computed(() => {
  return props.record?.service_info?.length || 0;
});

const modalTitle = computed(() => {
  const name = props.record?.service_name || taskText('tasks.services');
  return taskText('tasks.serviceEndpointsNameCountEndpoints', { name: name, count: totalCount.value });
});

const copyButtonText = computed(() => {
  if (searchKeyword.value && filteredList.value.length !== totalCount.value) {
    return taskText('tasks.copyFilteredEndpointsCount', { count: filteredList.value.length });
  }
  return taskText('tasks.copyAllEndpointsCount', { count: totalCount.value });
});

const filteredList = computed(() => {
  const list = props.record?.service_info || [];
  const kw = (searchKeyword.value || '').trim().toLowerCase();
  if (!kw) return list;
  return list.filter(item => {
    const ip = String(item.ip || '').toLowerCase();
    const port = String(item.port_id || '').toLowerCase();
    const product = String(item.product || '').toLowerCase();
    const version = String(item.version || '').toLowerCase();
    return ip.includes(kw) || port.includes(kw) || product.includes(kw) || version.includes(kw) || `${ip}:${port}`.includes(kw);
  });
});

watch(() => props.open, (newVal) => {
  if (newVal) {
    pagination.current = 1;
    searchKeyword.value = '';
  } else {
    searchKeyword.value = '';
  }
});

watch(searchKeyword, () => {
  pagination.current = 1;
});

const isWebEndpoint = (item) => {
  const sName = (props.record?.service_name || '').toLowerCase();
  if (sName.includes('http') || sName.includes('web')) return true;
  const p = Number(item.port_id);
  return [80, 443, 8080, 8443, 8000, 8888].includes(p);
};

const getEndpointUrl = (item) => {
  const sName = (props.record?.service_name || '').toLowerCase();
  const p = Number(item.port_id) || 80;
  const isHttps = sName.includes('https') || p === 443 || p === 8443;
  const scheme = isHttps ? 'https' : 'http';
  const ipStr = String(item.ip || '');
  const host = ipStr.includes(':') && !ipStr.startsWith('[') ? `[${ipStr}]` : ipStr;
  const portSuffix = item.port_id ? `:${item.port_id}` : '';
  return `${scheme}://${host}${portSuffix}`;
};

const copyAllEndpoints = async () => {
  if (!filteredList.value.length) {
    message.warning(taskText('tasks.noEndpointsToCopy'));
    return;
  }
  const text = filteredList.value.map(item => `${item.ip}:${item.port_id}`).join('\n');
  const ok = await copyText(text);
  if (ok) {
    message.success(taskText('tasks.endpointsCopiedToClipboardCount', { count: filteredList.value.length }));
  } else {
    message.error(taskText('tasks.copyFailedPleaseCopyManually'));
  }
};

const copySingleEndpoint = async (item) => {
  const text = `${item.ip}:${item.port_id}`;
  const ok = await copyText(text);
  if (ok) {
    message.success(taskText('tasks.copiedValue', { value: text }));
  } else {
    message.error(taskText('tasks.copyFailed'));
  }
};

const columns = [
  { get title() { return taskText('tasks.no'); }, key: 'index', width: 65, align: 'center' },
  { get title() { return taskText('tasks.ipPort'); }, key: 'ip_port', width: 220 },
  { get title() { return taskText('tasks.product'); }, key: 'product', dataIndex: 'product', ellipsis: true },
  { get title() { return taskText('tasks.version'); }, key: 'version', dataIndex: 'version', width: 140, ellipsis: true },
  { get title() { return taskText('tasks.actions'); }, key: 'action', width: 80, align: 'center' }
];
</script>
