<template>
  <div class="arl-page-container">
    <!-- 吸顶 Hero 操作卡片 -->
    <div ref="actionBarRef" class="arl-hero-card">
      <div class="arl-toolbar-row">
        <!-- 左侧：紧凑搜索与重置 -->
        <div class="arl-filter-group">
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.policyName') }}</span>
            <a-input
              v-model:value="searchForm.name"
              :placeholder="pageText('pages.enterAPolicyName')"
              style="width: 210px;"
              allowClear
              size="small"
              @pressEnter="onSearch"
            >
              <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
            </a-input>
          </div>
          <a-button size="small" @click="resetSearch">
            <template #icon><undo-outlined /></template>
            {{ pageText('assets.reset') }}
          </a-button>
        </div>

        <!-- 右侧：主操作与批量删除 -->
        <div class="arl-actions-group">
          <a-button type="primary" size="small" @click="goToDetail">
            <template #icon><plus-outlined /></template>
            {{ pageText('pages.newPolicy') }}
          </a-button>
          <a-popconfirm
            :title="pageText('pages.deleteTheSelectedPoliciesLabel2')"
            :ok-text="pageText('assets.confirm')"
            :cancel-text="pageText('tasks.cancel')"
            @confirm="handleBatchDelete"
            :disabled="selectedRowKeys.length === 0"
          >
            <a-button danger size="small" :disabled="selectedRowKeys.length === 0">
              <template #icon><delete-outlined /></template>
              {{ pageText('tasks.deleteSelected') }}
            </a-button>
          </a-popconfirm>
        </div>
      </div>
    </div>

    <!-- 表格：统一小尺寸，保留 sticky -->
    <a-table
      :sticky="stickyConfig"
      :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: keys => selectedRowKeys = keys, preserveSelectedRowKeys: true }"
      :loading="loading"
      :dataSource="dataSource"
      :columns="columns"
      :pagination="false"
      size="small"
      :rowKey="(record) => record._id"
    >
      <template #bodyCell="{ column, record, index }">
        <template v-if="column.key === 'index'"><span>{{ (pagination.current - 1) * pagination.pageSize + index + 1 }}</span></template>

        <template v-else-if="column.key === 'action'">
          <div style="display: flex; gap: 6px;">
            <a-button size="small" @click="openDispatchModal(record)">{{ pageText('tasks.runDiscoveryNow') }}</a-button>
            <a-button size="small" @click="router.push({ path: '/policyDetail', query: { _id: record._id } })">{{ pageText('assets.edit') }}</a-button>
            <a-popconfirm
                :title="pageText('pages.deleteTheSelectedRecordsLabel2')"
                :ok-text="pageText('assets.confirm')"
                :cancel-text="pageText('tasks.cancel')"
                @confirm="handleDelete(record)"
            >
              <a-button size="small" danger>{{ pageText('tasks.delete') }}</a-button>
            </a-popconfirm>
          </div>
        </template>
      </template>

      <template #expandedRowRender="{ record }">
        <div class="policy-expanded-box">
          <div class="policy-section">
            <div class="policy-title">{{ pageText('tasks.domainsAndAssetDiscovery') }}</div>
            <div class="policy-row"><span class="policy-label">{{ pageText('tasks.subdomainWordlist') }}</span><span class="policy-val">{{ getDomainBruteText(record.policy) }}</span></div>
            <div class="policy-row"><span class="policy-label">{{ pageText('tasks.generatedSubdomainWordlist') }}</span><span class="policy-val">{{ getAltDnsText(record.policy) }}</span></div>
            <div class="policy-row"><span class="policy-label">{{ pageText('pages.enabledFeatures') }}</span><span class="policy-val">{{ getDomainConfigText(record.policy) }}</span></div>
          </div>
          <div class="policy-divider"></div>
          <div class="policy-section">
            <div class="policy-title">{{ pageText('tasks.portsAndServices') }}</div>
            <div class="policy-row"><span class="policy-label">{{ pageText('pages.portScanPolicy') }}</span><span class="policy-val">{{ getPortScanPolicyText(record.policy) }}</span></div>
            <div class="policy-row"><span class="policy-label">{{ pageText('pages.enabledFeatures') }}</span><span class="policy-val">{{ getIpConfigText(record.policy) }}</span></div>
          </div>
          <div class="policy-divider"></div>
          <div class="policy-section">
            <div class="policy-title">{{ pageText('tasks.webDiscovery') }}</div>
            <div class="policy-row"><span class="policy-label">{{ pageText('pages.fileDisclosureDictionary') }}</span><span class="policy-val">{{ getFileLeakText(record.policy) }}</span></div>
            <div class="policy-row"><span class="policy-label">{{ pageText('pages.enabledFeatures') }}</span><span class="policy-val">{{ getSiteConfigText(record.policy) }}</span></div>
          </div>
          <div class="policy-divider"></div>
          <div class="policy-section">
            <div class="policy-title">{{ pageText('tasks.vulnerabilityAndRiskScanning') }}</div>
            <div class="policy-row"><span class="policy-label">{{ pageText('tasks.nucleiScanning') }}</span><span class="policy-val">{{ record.policy?.site_config?.nuclei_scan ? pageText('pages.enabled') : pageText('pages.disabled') }}</span></div>
            <div class="policy-row"><span class="policy-label">{{ pageText('pages.pocVerification') }}</span><span class="policy-val">{{ getPocConfigText(record.policy) }}</span></div>
            <div class="policy-row"><span class="policy-label">{{ pageText('tasks.stageWeakBrute') }}</span><span class="policy-val">{{ getBruteConfigText(record.policy) }}</span></div>
          </div>
        </div>
      </template>
    </a-table>

    <!-- 统一微型分页栏 -->
    <div class="arl-pagination-bar">
      <div class="pagination-info">{{ pageText('tasks.paginationSummary', { pages: Math.ceil(pagination.total / pagination.pageSize) || 1, total: pagination.total }) }}</div>
      <a-pagination
        :pageSizeOptions="$pageSizeOptions"
        v-model:current="pagination.current"
        v-model:pageSize="pagination.pageSize"
        :total="pagination.total"
        show-size-changer
        size="small"
        @change="handleTableChange"
        @showSizeChange="handleTableChange"
      />
    </div>
  </div>

  <a-modal
      v-model:open="dispatchModalVisible"
      :title="pageText('tasks.runDiscoveryNow')"
      @ok="submitDispatch"
      :confirmLoading="dispatchLoading"
      width="520px"
      :okText="pageText('tasks.confirm')"
      :cancelText="pageText('assets.cancel')"
      destroyOnClose
  >
    <a-form :label-wrap="true" :model="dispatchForm" :label-col="{ span: pageLocale !== 'zh-CN' ? 7 : 5 }" :wrapper-col="{ span: pageLocale !== 'zh-CN' ? 16 : 18 }" class="page-modal-form">
      <a-form-item :label="pageText('tasks.taskTypeLabel')" required>
        <a-select v-model:value="dispatchForm.task_tag" @change="onTaskTagChange">
          <a-select-option value="task">{{ pageText('tasks.assetDiscoveryTasks') }}</a-select-option>
          <a-select-option value="risk_cruising">{{ pageText('tasks.riskScanningTask') }}</a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item :label="pageText('assets.taskName')" required>
        <a-input v-model:value="dispatchForm.name" :placeholder="pageText('tasks.enterATaskName')" />
      </a-form-item>

      <a-form-item :label="pageText('tasks.target')" required>
        <a-textarea v-model:value="dispatchForm.target" :rows="4" :placeholder="pageText('pages.enterTargetIpsOrDomainsOnePerLine')" />
      </a-form-item>
    </a-form>
  </a-modal>

</template>

<script setup>
import { useI18n } from 'vue-i18n';
defineOptions({ name: 'Policy' });

import { ref, reactive, onMounted, onActivated, onDeactivated, watch } from 'vue';
import { useSticky } from '../utils/useSticky';
const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

import { useRouter } from 'vue-router'; // 引入路由
import request from '../utils/request';
import { message } from 'ant-design-vue';
import { SearchOutlined, PlusOutlined, DeleteOutlined, UndoOutlined } from '@ant-design/icons-vue';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';

const { t: pageText, locale: pageLocale } = useI18n({ useScope: 'global' });

const router = useRouter(); // 实例化路由
const loading = ref(false);
const dataSource = ref([]);
const searchForm = ref({});
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

watch(() => pagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});

watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
});
const selectedRowKeys = ref([]);

const columns = [
  { get title() { return pageText('tasks.no'); }, key: 'index', width: 80, align: 'center' },
  { get title() { return pageText('tasks.name'); }, dataIndex: 'name', key: 'name', width: 250 },
  { get title() { return pageText('assets.description'); }, dataIndex: 'desc', key: 'desc', width: 300 },
  { get title() { return pageText('assets.updatedAtLabel'); }, dataIndex: 'update_date', key: 'update_date', width: 200 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 250 }
];

const fetchData = async () => {
  loading.value = true;
  try {
    const params = { page: pagination.current, size: pagination.pageSize, order: '-update_date' };
    if (searchForm.value.name) params.name = searchForm.value.name;
    const res = await request.get('/policy/', { params });
    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
    }
  } catch (error) { message.error(pageText('pages.failedToLoadPolicies')); } finally { loading.value = false; }
};

const resetSearch = () => {
  searchForm.value = {};
  pagination.current = 1;
  onSearch();
};

const onSearch = () => { pagination.current = 1; fetchData(); };
const handleTableChange = (page, pageSize) => { pagination.current = page; pagination.pageSize = pageSize; fetchData(); };

// 🚨 核心跳转函数
const goToDetail = () => {
  router.push('/policyDetail'); // 跳往独立的配置页面
};

// ======================== 展开行字典与摘要翻译 ========================
const dictNameMap = {
  get 'big'() { return pageText('pages.largeDictionaryDomain2wTxt'); },
  get 'test'() { return pageText('pages.testDictionaryDomainTop300Txt'); },
  get 'domain_2w.txt'() { return pageText('pages.largeDictionaryDomain2wTxt'); },
  get 'domain_top300.txt'() { return pageText('pages.testDictionaryDomainTop300Txt'); },
  get 'top100'() { return pageText('pages.top100Ports'); },
  get 'top1000'() { return pageText('pages.top1000Ports'); },
  get 'bughunter'() { return pageText('pages.bughunterPorts'); },
  get 'port_top100.txt'() { return pageText('pages.top100Ports'); },
  get 'port_top1000.txt'() { return pageText('pages.top1000Ports'); },
  get 'port_bughunter.txt'() { return pageText('pages.bughunterPorts'); },
  get 'all'() { return pageText('pages.allPorts'); }
};
const getDictName = (val) => (dictNameMap[val] || val || '-');

const getDomainBruteText = (p) => {
  if (!p?.domain_config?.domain_brute) return pageText('tasks.disabled');
  return getDictName(p.domain_config.domain_brute_type);
};

const getAltDnsText = (p) => {
  if (!p?.domain_config?.alt_dns) return pageText('tasks.disabled');
  return p.domain_config.alt_dns_dict || 'altdnsdict.txt';
};

const getPortScanPolicyText = (p) => {
  if (!p?.ip_config?.port_scan) return pageText('tasks.disabled');
  if (p.ip_config.port_scan_type === 'custom') {
    return pageText('pages.customPortsPorts', { ports: p.ip_config.port_custom || '-' });
  }
  return getDictName(p.ip_config.port_scan_type);
};

const getFileLeakText = (p) => {
  const enabled = p?.file_leak || p?.site_config?.file_leak;
  if (!enabled) return pageText('tasks.disabled');
  return p?.file_leak_dict || p?.site_config?.file_leak_dict || 'file_top_2000.txt';
};

const getDomainConfigText = (p) => {
  if (!p) return '-'; const l = [];
  if (p.domain_config?.dns_query_plugin) l.push(pageText('tasks.domainLookupPlugins'));
  if (p.domain_config?.domain_brute) l.push(pageText('tasks.subdomainBruteForce'));
  if (p.domain_config?.alt_dns) l.push(pageText('tasks.dnsWordlistGeneration'));
  if (p.domain_config?.arl_search) l.push(pageText('pages.arlHistory'));
  return l.join('、') || '-';
};

const getIpConfigText = (p) => {
  if (!p) return '-'; const l = [];
  if (p.ip_config?.skip_scan_cdn_ip) l.push(pageText('tasks.skipCdn'));
  if (p.ip_config?.port_scan) l.push(pageText('tasks.portScanning'));
  if (p.ip_config?.service_detection || p.npoc_service_detection) l.push(pageText('tasks.serviceDetection'));
  if (p.ip_config?.os_detection) l.push(pageText('tasks.osDetection'));
  if (p.ip_config?.ssl_cert) l.push(pageText('tasks.stageSslCert'));
  return l.join('、') || '-';
};

const getSiteConfigText = (p) => {
  if (!p) return '-'; const l = [];
  if (p.site_config?.site_identify) l.push(pageText('tasks.websiteDiscoveryAndFingerprinting'));
  if (p.file_leak || p.site_config?.file_leak) l.push(pageText('tasks.fileDisclosure'));
  if (p.site_config?.search_engines) l.push(pageText('tasks.searchEngines'));
  if (p.site_config?.site_spider) l.push(pageText('tasks.websiteCrawler'));
  if (p.site_config?.web_info_hunter) l.push(pageText('tasks.wihExtraction'));
  if (p.site_config?.findvhost) l.push(pageText('tasks.hostCollision'));
  return l.join('、') || '-';
};

const getPocConfigText = (p) => {
  const active = p?.poc_config?.filter(x => x.enable) || [];
  if (active.length === 0) return pageText('pages.noPluginsEnabled');
  return pageText('pages.enabledCountNamesSuffix', { count: active.length, names: active.slice(0, 3).map(x => x.vul_name || x.plugin_name).join('、'), suffix: active.length > 3 ? pageText('pages.etc') : '' });
};

const getBruteConfigText = (p) => {
  const active = p?.brute_config?.filter(x => x.enable) || [];
  if (active.length === 0) return pageText('pages.credentialChecksDisabled');
  return pageText('pages.enabledCountNamesSuffix', { count: active.length, names: active.slice(0, 3).map(x => x.vul_name || x.plugin_name).join('、'), suffix: active.length > 3 ? pageText('pages.etc') : '' });
};

let firstActivation = true;
onMounted(() => fetchData());

onActivated(async () => {
  // KeepAlive 首次激活时 onMounted 已启动加载，消除并发双重触发
  if (firstActivation) {
    firstActivation = false;
    return;
  }
  await fetchData();
});

// ================= 任务下发逻辑 =================
const dispatchModalVisible = ref(false);
const dispatchLoading = ref(false);
const currentPolicy = ref(null);

const dispatchForm = reactive({
  task_tag: 'task',
  name: '',
  target: ''
});

// 打开弹窗并初始化数据
const openDispatchModal = (record) => {
  currentPolicy.value = record;
  dispatchForm.task_tag = 'task';
  dispatchForm.target = '';
  // 智能联动：默认任务名称为“资产侦查任务-策略名”
  dispatchForm.name = `资产侦查任务-${record.name}`;
  dispatchModalVisible.value = true;
};

// 监听下拉框切换，动态改变任务名称前缀
const onTaskTagChange = (val) => {
  const prefix = val === 'task' ? '资产侦查任务' : '风险巡航任务';
  dispatchForm.name = `${prefix}-${currentPolicy.value?.name}`;
};

// 提交发包
const submitDispatch = async () => {
  if (!dispatchForm.name || !dispatchForm.target) {
    return message.warning(pageText('pages.enterBothATaskNameAndTargets'));
  }

  dispatchLoading.value = true;
  try {
    const payload = {
      policy_id: currentPolicy.value._id,
      name: dispatchForm.name,
      task_tag: dispatchForm.task_tag,
      target: dispatchForm.target
    };

    const res = await request.post('/task/policy/', payload);

    if (res.code === 200) {
      message.success(pageText('tasks.taskCreated'));
      dispatchModalVisible.value = false;
      // 成功后一般不需要刷新策略列表，用户会自己去任务监控页面看
    } else if (res.code === 500) {
      // 🚨 原汁原味拦截 500 报错（如：不在关联的资产组范围内）
      message.error(res.message || res.data?.error || pageText('pages.systemError'));
    } else {
      message.error(pageText('tasks.failedToCreateTaskLabel') + res.message);
    }
  } catch (error) {
    message.error(pageText('pages.requestFailedTaskWasNotQueued'));
  } finally {
    dispatchLoading.value = false;
  }
};

// ================= 单个删除策略逻辑 =================
const handleDelete = async (record) => {
  try {
    // 🚨 核心对齐：抓包显示哪怕删除一个，Payload 也必须是包含 ID 的数组
    const payload = {
      policy_id: [record._id]
    };

    const res = await request.post('/policy/delete/', payload);

    if (res.code === 200) {
      message.success(pageText('pages.policyDeleted'));

      // 体验优化：如果当前页只有一条数据，删除后自动退回上一页
      if (dataSource.value.length === 1 && pagination.current > 1) {
        pagination.current -= 1;
      }

      // 重新拉取列表数据
      fetchData();
    } else {
      message.error(pageText('tasks.deletionFailed') + res.message);
    }
  } catch (error) {
    message.error(pageText('assets.requestFailedAssetGroupWasNotDeleted'));
  }
};

// ================= 批量删除策略逻辑 =================
const handleBatchDelete = async () => {
  if (selectedRowKeys.value.length === 0) {
    return message.warning(pageText('pages.selectPoliciesToDeleteFirst'));
  }
  try {
    const payload = {
      policy_id: selectedRowKeys.value
    };

    const res = await request.post('/policy/delete/', payload);

    if (res.code === 200) {
      message.success(pageText('pages.selectedPoliciesDeleted'));
      
      // 体验优化：如果当前页数据全被删除了，退回上一页
      if (dataSource.value.length === selectedRowKeys.value.length && pagination.current > 1) {
        pagination.current -= 1;
      }
      
      selectedRowKeys.value = []; // 清空选中
      fetchData(); // 重新拉取列表数据
    } else {
      message.error(pageText('pages.bulkDeletionFailed') + res.message);
    }
  } catch (error) {
    message.error(pageText('pages.requestFailedSelectedRecordsWereNotDeleted'));
  }
};

onDeactivated(() => {
  dispatchModalVisible.value = false;
});
</script>

<style scoped>
.policy-expanded-box { margin: 8px 16px 16px 16px; background: var(--arl-bg-white); border: 1px solid var(--arl-border-color); border-radius: 6px; }
.policy-section { padding: 16px 24px; }
.policy-title { font-weight: bold; color: var(--arl-text-color); margin-bottom: 16px; }
.policy-row { display: flex; margin-bottom: 12px; line-height: 1.5; }
.policy-row:last-child { margin-bottom: 0; }
.policy-label { color: var(--arl-text-color); width: 130px; flex-shrink: 0; }
.policy-val { color: var(--arl-text-color); word-break: break-word; }
.policy-divider { height: 1px; background: var(--arl-border-color); margin: 0; }

.page-modal-form { margin-top: 20px; }
</style>