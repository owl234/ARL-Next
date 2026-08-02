<template>
  <a-modal :open="open" @update:open="$emit('update:open', $event)" :title="`C段详情：${currentCidrIp}`" :footer="null" width="700px">
    <a-table 
      :dataSource="cipDetailData" 
      :columns="cipDetailColumns" 
      :pagination="false" 
      size="small"
      :scroll="{ y: 400 }"
      :loading="cipDetailLoading"
      rowKey="ip"
    >
      <template #bodyCell="{ column, record, index }">
        <template v-if="column.key === 'index'">
          {{ index + 1 }}
        </template>
        <template v-else-if="column.key === 'domains'">
          <div v-if="record.domains && record.domains.length > 0">
            <div v-for="(domain, idx) in record.domains" :key="idx" style="font-family: monospace;">
              {{ domain }}
            </div>
          </div>
          <span v-else style="color: #ccc;">-</span>
        </template>
      </template>
    </a-table>
  </a-modal>
</template>

<script setup>
import { ref, watch } from 'vue';
import request from '../utils/request';
import { message } from 'ant-design-vue';

const props = defineProps({
  open: { type: Boolean, required: true },
  record: { type: Object, default: () => ({}) }
});

const emit = defineEmits(['update:open']);

const cipDetailLoading = ref(false);
const cipDetailData = ref([]);
const currentCidrIp = ref('');

const cipDetailColumns = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: 'IP', dataIndex: 'ip', key: 'ip', width: 150 },
  { title: 'IP对应的域名', key: 'domains', width: 300 }
];

watch(() => props.open, async (newVal) => {
  if (newVal && props.record) {
    currentCidrIp.value = props.record.cidr_ip || '-';
    cipDetailLoading.value = true;
    cipDetailData.value = [];
    try {
      const res = await request.get('/asset_cip/ip_domain_detail/', { params: { cidr_id: props.record._id || props.record.id } });
      if (res.message && res.message !== 'success') {
        message.warning(res.message);
      }
      if (res.code === 200) {
        cipDetailData.value = res.data?.items || res.items || [];
      } else {
        message.error(res.message || '获取C段详情失败');
      }
    } catch (error) {
      message.error('请求出错');
    } finally {
      cipDetailLoading.value = false;
    }
  }
});
</script>
