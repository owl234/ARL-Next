<template>
  <a-modal :open="open" @update:open="$emit('update:open', $event)" :title="taskText('tasks.cClassNetworkDetailsNetwork', { network: currentCidrIp })" :footer="null" width="700px">
    <a-table
      :dataSource="cipDetailData"
      :columns="cipDetailColumns"
      :pagination="false"
      size="small"
      :scroll="{ y: 400 }"
      :loading="cipDetailLoading"
      rowKey="ip"
    >
      <template #emptyText>
        <ArlEmpty v-if="loadFailed" :description="taskText('tasks.failedToLoadCClassNetworkDetailsClose')" compact>
          <a-button size="small" type="primary" @click="fetchDetail">{{ taskText('tasks.reload') }}</a-button>
        </ArlEmpty>
        <ArlEmpty v-else :description="taskText('tasks.noAssociatedDomainRecordsForThisCClass')" compact />
      </template>
      <template #bodyCell="{ column, record, index }">
        <template v-if="column.key === 'index'">
          {{ index + 1 }}
        </template>
        <template v-else-if="column.key === 'domains'">
          <div v-if="record.domains && record.domains.length > 0">
            <div v-for="(domain, idx) in record.domains" :key="idx" style="font-family: var(--arl-font-mono);">
              {{ domain }}
            </div>
          </div>
          <span v-else style="color: var(--arl-text-secondary);">-</span>
        </template>
      </template>
    </a-table>
  </a-modal>
</template>

<script setup>
import { useI18n } from 'vue-i18n';

import { ref, watch } from 'vue';
import request from '../utils/request';
import { message } from 'ant-design-vue';

const { t: taskText } = useI18n({ useScope: 'global' });

const props = defineProps({
  open: { type: Boolean, required: true },
  record: { type: Object, default: () => ({}) }
});

const emit = defineEmits(['update:open']);

const cipDetailLoading = ref(false);
const cipDetailData = ref([]);
const currentCidrIp = ref('');
const loadFailed = ref(false);

const cipDetailColumns = [
  { get title() { return taskText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
  { title: 'IP', dataIndex: 'ip', key: 'ip', width: 150 },
  { get title() { return taskText('tasks.domainsAssociatedWithIp'); }, key: 'domains', width: 300 }
];

const fetchDetail = async () => {
  if (!props.record) return;
  cipDetailLoading.value = true;
  loadFailed.value = false;
  cipDetailData.value = [];
  try {
    const res = await request.get('/asset_cip/ip_domain_detail/', { params: { cidr_id: props.record._id || props.record.id } });
    if (res.code === 200) {
      cipDetailData.value = res.data?.items || res.items || [];
    } else {
      loadFailed.value = true;
      message.error(res.message || taskText('tasks.failedToLoadCClassNetworkDetails'));
    }
  } catch (error) {
    loadFailed.value = true;
    message.error(taskText('tasks.failedToLoadCClassNetworkDetailsPlease'));
  } finally {
    cipDetailLoading.value = false;
  }
};

watch(() => props.open, (newVal) => {
  if (newVal && props.record) {
    currentCidrIp.value = props.record.cidr_ip || '-';
    fetchDetail();
  }
});
</script>
