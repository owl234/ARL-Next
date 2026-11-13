<template>
  <a-modal
    :open="open"
    @update:open="val => $emit('update:open', val)"
    :title="step === 'form' ? taskText('tasks.syncAssetsToAssetGroup') : taskText('tasks.assetsSynced')"
    wrapClassName="arl-theme-modal"
    width="680px"
    :destroyOnClose="true"
    :footer="null"
  >
    <!-- 步骤 1：同步配置与域名预检表单 -->
    <a-spin :spinning="modalDataLoading || syncLoading" :tip="syncLoading ? taskText('tasks.syncingDataAndQueuingTasks') : taskText('tasks.loadingAssetGroupsAndPreviewData')">
      <div v-if="step === 'form'">
        <!-- 明确"同步"的实际作用，避免被理解为拉取最新数据 -->
        <div style="background: var(--arl-bg-light); border: 1px solid var(--arl-border-color); border-radius: 4px; padding: 8px 12px; margin-bottom: 16px; font-size: 12px; color: var(--arl-text-color); opacity: 0.85; line-height: 1.6;">
          {{ taskText('tasks.syncDescription') }}
        </div>
        <a-form :label-wrap="true" :label-col="{ style: { width: taskLocale !== 'zh-CN' ? '140px' : '100px' } }" :wrapper-col="{ style: { width: taskLocale !== 'zh-CN' ? 'calc(100% - 140px)' : 'calc(100% - 100px)' } }">

          <a-form-item :label="taskText('tasks.parentOrganization')">
            <a-select
              v-model:value="syncFormState.group_id"
              :placeholder="taskText('tasks.selectAParentOrganizationOptional')"
              allowClear
              show-search
              option-filter-prop="label"
              @change="onGroupChange"
            >
              <a-select-option v-for="g in groupList" :key="g._id" :value="g._id" :label="g.name">
                {{ g.name }}
              </a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item :label="taskText('tasks.syncMode')">
            <a-radio-group v-model:value="syncFormState.mode" @change="onSyncScopeChange">
              <a-radio value="existing">{{ taskText('tasks.linkAnExistingAssetGroup') }}</a-radio>
              <a-radio value="new">{{ taskText('tasks.createAnAssetGroup') }}</a-radio>
            </a-radio-group>
          </a-form-item>

          <a-form-item v-if="syncFormState.mode === 'existing'" :label="taskText('tasks.chooseAssetGroup')" :rules="[{ required: true, message: taskText('tasks.selectAnAssetGroup') }]">
            <a-select
              v-model:value="syncFormState.scope_id"
              :placeholder="taskText('tasks.selectAnAssetGroup')"
              show-search
              option-filter-prop="label"
              @change="onSyncScopeChange"
            >
              <a-select-option
                v-for="scope in filteredScopes"
                :key="scope._id"
                :value="scope._id"
                :label="scope.name"
              >
                <div style="display: flex; justify-content: space-between; align-items: center;">
                  <span>{{ scope.name }}</span>
                  <span v-if="scope.group_name" style="font-size: 11px; color: var(--arl-text-color); opacity: 0.55; margin-left: 8px;">
                    [{{ scope.group_name }}]
                  </span>
                </div>
              </a-select-option>
            </a-select>
          </a-form-item>

          <a-form-item v-if="syncFormState.mode === 'new'" :label="taskText('tasks.assetGroupName')" :rules="[{ required: true, message: taskText('tasks.enterAnAssetGroupName') }]">
            <a-input v-model:value="syncFormState.target_name" :placeholder="taskText('tasks.enterAnAssetGroupName')" @input="onSyncScopeChange" />
          </a-form-item>

          <!-- 增量预检摘要与穿透面板 -->
          <div style="margin: 0 16px 16px 16px; border: 1px solid var(--arl-border-color); border-radius: 6px; overflow: hidden; background: var(--arl-bg-light);">
            <div style="padding: 10px 14px; display: flex; justify-content: space-between; align-items: center;">
              <div style="font-size: 13px;">
                {{ taskText('tasks.domainSummary', { count: diffStats.totalCount }) }}
                <span class="task-new-count">{{ taskText('tasks.newDomainCount', { count: diffStats.newCount }) }}</span>
                <span class="task-existing-count">{{ taskText('tasks.existingDomainCount', { count: diffStats.duplicateCount }) }}</span>
                <span class="task-selection-count">{{ taskText('tasks.selectedLabel') }} {{ selectedDomainKeys.length }}/{{ diffStats.totalCount }})</span>
              </div>
              <a-button type="link" size="small" style="padding: 0;" @click="isDomainPanelExpanded = !isDomainPanelExpanded">
                {{ isDomainPanelExpanded ? taskText('tasks.hideDomainDetails') : taskText('tasks.showDomainSelection') }}
              </a-button>
            </div>

            <!-- 展开的域名明细与快速过滤面板 -->
            <div v-show="isDomainPanelExpanded" style="border-top: 1px solid var(--arl-border-color); padding: 10px 14px; background: var(--arl-bg-white);">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; gap: 8px; flex-wrap: wrap;">
                <a-radio-group v-model:value="domainFilterTab" size="small" button-style="solid">
                  <a-radio-button value="all">{{ taskText('tasks.allDomainCount', { count: diffStats.totalCount }) }}</a-radio-button>
                  <a-radio-button value="new">{{ taskText('tasks.newDomainTabCount', { count: diffStats.newCount }) }}</a-radio-button>
                  <a-radio-button value="duplicate">{{ taskText('tasks.existingDomainTabCount', { count: diffStats.duplicateCount }) }}</a-radio-button>
                </a-radio-group>
                <div style="display: flex; gap: 6px; align-items: center;">
                  <a-input
                    v-model:value="domainSearchKey"
                    :placeholder="taskText('tasks.filterDomains')"
                    size="small"
                    style="width: 140px;"
                    allowClear
                  />
                  <a-button size="small" @click="selectAllDomains">{{ taskText('tasks.selectAll') }}</a-button>
                  <a-button size="small" @click="selectOnlyNewDomains">{{ taskText('tasks.selectNewOnly') }}</a-button>
                  <a-button size="small" @click="unselectAllDomains">{{ taskText('tasks.clearThisCategory') }}</a-button>
                </div>
              </div>

              <!-- 域名勾选列表 -->
              <div style="max-height: 180px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px; padding-right: 4px;">
                <div
                  v-for="d in displayedDomainList"
                  :key="d.domain"
                  style="display: flex; align-items: center; justify-content: space-between; padding: 4px 8px; border-radius: 4px; background: var(--arl-bg-light, #fafafa); font-size: 12px; font-family: monospace;"
                >
                  <a-checkbox
                    :checked="selectedDomainKeys.includes(d.domain)"
                    @change="e => toggleDomainSelect(d.domain, e.target.checked)"
                  >
                    <span>{{ d.domain }}</span>
                  </a-checkbox>
                  <a-tag v-if="d.isNew" color="blue" size="small" class="task-compact-tag">{{ taskText('tasks.new') }}</a-tag>
                  <a-tag v-else color="default" size="small" class="task-compact-tag">{{ taskText('tasks.existing') }}</a-tag>
                </div>
                <div v-if="displayedDomainList.length === 0" style="text-align: center; color: #bfbfbf; padding: 16px 0; font-size: 12px;">
                  {{ taskText('tasks.noMatchingDomains') }}
                </div>
              </div>
            </div>
          </div>

          <a-divider style="margin: 12px 0 16px 0;" dashed />

          <a-form-item :label="taskText('tasks.runDiscoveryNow')">
            <a-checkbox v-model:checked="syncFormState.auto_scan">
              {{ taskText('tasks.automaticallyScanNewlyDiscoveredDomainsNow') }}
            </a-checkbox>
          </a-form-item>

          <template v-if="syncFormState.auto_scan">
            <a-form-item :label="taskText('tasks.taskTypeLabel')">
              <a-radio-group v-model:value="syncFormState.task_type">
                <a-radio value="oneshot">{{ taskText('tasks.oneTimeScanDiscoverAndSaveAssets') }}</a-radio>
                <a-radio value="periodic">{{ taskText('tasks.recurringMonitoringScheduledScans') }}</a-radio>
              </a-radio-group>
            </a-form-item>

            <a-form-item
              :label="taskText('tasks.scanPolicy')"
              :required="syncFormState.auto_scan"
              :rules="syncFormState.auto_scan ? [{ required: true, message: taskText('tasks.selectAScanPolicy') }] : []"
            >
              <a-select
                v-model:value="syncFormState.policy_id"
                :placeholder="taskText('tasks.selectAScanPolicy')"
                show-search
                option-filter-prop="label"
                :options="policyList.map(p => ({ value: p._id, label: `${p.name} (PoC : ${p.policy?.poc_config?.length || 0})` }))"
              />
              <div v-if="syncFormState.auto_scan && !syncFormState.policy_id" class="policy-required-hint">
                {{ taskText('tasks.runDiscoveryNowIsEnabledSelectAScan') }}
              </div>
            </a-form-item>

            <a-form-item v-if="syncFormState.task_type === 'periodic'" :label="taskText('tasks.runInterval')">
              <a-input-number
                v-model:value="syncFormState.interval_hours"
                :min="6"
                :max="720"
                style="width: 160px;"
                :addon-after="taskText('tasks.hours')"
              />
            </a-form-item>
          </template>

          <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 24px;">
            <a-button @click="$emit('update:open', false)">{{ taskText('tasks.cancel') }}</a-button>
            <a-button type="primary" :loading="syncLoading" :disabled="modalDataLoading || selectedDomainKeys.length === 0" @click="submitSync">
              {{ taskText('tasks.syncDomainCount', { count: selectedDomainKeys.length }) }}
            </a-button>
          </div>
        </a-form>
      </div>

      <!-- 步骤 2：同步结果看板 -->
      <div v-else-if="step === 'result'" style="padding: 12px 16px 4px 16px;">
        <div style="text-align: center; margin-bottom: 24px;">
          <div style="font-size: 40px; margin-bottom: 8px;">🎉</div>
          <div class="task-result-heading">{{ taskText('tasks.assetsSynced') }}</div>
          <div style="font-size: 13px; color: var(--arl-text-color); opacity: 0.65; margin-top: 4px;">
            {{ taskText('tasks.enterpriseDiscoveryResultsWereSavedToTheAsset') }}
          </div>
        </div>

        <div style="background: var(--arl-bg-light); border: 1px solid var(--arl-border-color); border-radius: 8px; padding: 16px; margin-bottom: 24px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; font-size: 14px;">
            <span class="task-secondary-label">{{ taskText('tasks.targetGroup') }}</span>
            <span style="font-weight: 600;">
              <span v-if="syncResult.group_name" style="color: var(--arl-theme-color);">{{ syncResult.group_name }} / </span>
              <span>{{ syncResult.target_name }}</span>
            </span>
          </div>

          <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; text-align: center;">
            <div style="padding: 12px 8px; background: var(--arl-bg-white); border-radius: 6px; border: 1px solid var(--arl-border-color);">
              <div style="font-size: 20px; font-weight: bold; color: var(--arl-theme-color);">+{{ syncResult.insert_count || 0 }}</div>
              <div class="task-result-label">{{ taskText('tasks.newDomainsSaved') }}</div>
            </div>
            <div style="padding: 12px 8px; background: var(--arl-bg-white); border-radius: 6px; border: 1px solid var(--arl-border-color);">
              <div style="font-size: 20px; font-weight: bold; color: #8c8c8c;">{{ syncResult.duplicate_count || 0 }}</div>
              <div class="task-result-label">{{ taskText('tasks.duplicateDomainsSkipped') }}</div>
            </div>
            <div style="padding: 12px 8px; background: var(--arl-bg-white); border-radius: 6px; border: 1px solid var(--arl-border-color);">
              <div style="font-size: 20px; font-weight: bold; color: #52c41a;">{{ syncResult.task_triggered_count || 0 }}</div>
              <div class="task-result-label">{{ taskText('tasks.discoveryTasksQueued') }}</div>
            </div>
          </div>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 12px; margin-top: 20px;">
          <a-button @click="handleStayHere">{{ taskText('tasks.stayOnCurrentPage') }}</a-button>
          <a-button type="primary" @click="handleGoToScope">
            {{ taskText('tasks.openAssetGroup') }}
          </a-button>
        </div>
      </div>
    </a-spin>
  </a-modal>
</template>

<script setup>
import { useI18n } from 'vue-i18n';

import { ref, reactive, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { message } from 'ant-design-vue';
import request from '../utils/request';

const { t: taskText, locale: taskLocale } = useI18n({ useScope: 'global' });

const props = defineProps({
  open: { type: Boolean, required: true },
  task: { type: Object, default: () => ({}) },
  preSelectedDomains: { type: Array, default: () => [] }
});

const emit = defineEmits(['update:open', 'success']);
const router = useRouter();

const step = ref('form'); // 'form' | 'result'
const modalDataLoading = ref(false);
const syncLoading = ref(false);

const groupList = ref([]);
const assetScopes = ref([]);
const policyList = ref([]);
const allTaskWebDomains = ref([]);
const selectedDomainKeys = ref([]);

const isDomainPanelExpanded = ref(false);
const domainFilterTab = ref('all'); // 'all' | 'new' | 'duplicate'
const domainSearchKey = ref('');

const syncFormState = reactive({
  group_id: undefined,
  mode: 'existing',
  scope_id: undefined,
  target_name: '',
  auto_scan: false,
  task_type: 'oneshot',
  policy_id: undefined,
  interval_hours: 24
});

const syncResult = reactive({
  scope_id: '',
  target_name: '',
  group_name: '',
  insert_count: 0,
  duplicate_count: 0,
  task_triggered_count: 0
});

// 根据选择的集团过滤资产组
const filteredScopes = computed(() => {
  if (!syncFormState.group_id) {
    return assetScopes.value;
  }
  return assetScopes.value.filter(s => s.group_id === syncFormState.group_id);
});

// 当切换集团时联动校验资产组
const onGroupChange = () => {
  if (syncFormState.mode === 'existing') {
    if (syncFormState.scope_id) {
      const match = filteredScopes.value.find(s => s._id === syncFormState.scope_id);
      if (!match) {
        syncFormState.scope_id = filteredScopes.value.length > 0 ? filteredScopes.value[0]._id : undefined;
      }
    } else if (filteredScopes.value.length > 0) {
      syncFormState.scope_id = filteredScopes.value[0]._id;
    }
  }
  calculateDiff();
};

// 当前目标资产组已有域名集合
const currentTargetScopeDomains = computed(() => {
  if (syncFormState.mode === 'existing') {
    if (!syncFormState.scope_id) return new Set();
    const scope = assetScopes.value.find(s => s._id === syncFormState.scope_id);
    const list = scope?.domain_array || scope?.scope_array || [];
    return new Set(list.map(d => String(d).trim().toLowerCase()));
  } else {
    // 新建模式，若同名则比对
    const scope = assetScopes.value.find(s => s.name === syncFormState.target_name?.trim());
    if (scope) {
      const list = scope?.domain_array || scope?.scope_array || [];
      return new Set(list.map(d => String(d).trim().toLowerCase()));
    }
    return new Set();
  }
});

// 增量差异统计
const diffStats = computed(() => {
  const existingSet = currentTargetScopeDomains.value;
  const total = allTaskWebDomains.value.length;
  let dupCount = 0;
  let newCount = 0;
  for (const d of allTaskWebDomains.value) {
    if (existingSet.has(d.toLowerCase())) {
      dupCount++;
    } else {
      newCount++;
    }
  }
  return {
    totalCount: total,
    duplicateCount: dupCount,
    newCount: newCount
  };
});

// 域名明细列表与状态标记
const processedDomainList = computed(() => {
  const existingSet = currentTargetScopeDomains.value;
  return allTaskWebDomains.value.map(domain => {
    const isNew = !existingSet.has(domain.toLowerCase());
    return {
      domain,
      isNew
    };
  });
});

// 过滤后的域名展示列表
const displayedDomainList = computed(() => {
  return processedDomainList.value.filter(item => {
    if (domainFilterTab.value === 'new' && !item.isNew) return false;
    if (domainFilterTab.value === 'duplicate' && item.isNew) return false;
    if (domainSearchKey.value.trim()) {
      return item.domain.toLowerCase().includes(domainSearchKey.value.trim().toLowerCase());
    }
    return true;
  });
});

const calculateDiff = () => {
  // 触发响应式重算
};

const onSyncScopeChange = () => {
  calculateDiff();
};

const toggleDomainSelect = (domain, checked) => {
  if (checked) {
    if (!selectedDomainKeys.value.includes(domain)) {
      selectedDomainKeys.value.push(domain);
    }
  } else {
    selectedDomainKeys.value = selectedDomainKeys.value.filter(d => d !== domain);
  }
};

const selectAllDomains = () => {
  selectedDomainKeys.value = allTaskWebDomains.value.slice();
};

const selectOnlyNewDomains = () => {
  selectedDomainKeys.value = processedDomainList.value.filter(d => d.isNew).map(d => d.domain);
};

const unselectAllDomains = () => {
  selectedDomainKeys.value = [];
};

// 监听弹窗打开状态，初始化加载数据
watch(() => props.open, async (newVal) => {
  if (newVal && props.task && props.task._id) {
    step.value = 'form';
    modalDataLoading.value = true;
    isDomainPanelExpanded.value = false;
    domainFilterTab.value = 'all';
    domainSearchKey.value = '';

    syncFormState.group_id = undefined;
    syncFormState.mode = 'existing';
    syncFormState.scope_id = props.task.synced_scope_id || undefined;
    syncFormState.target_name = props.task.name || props.task.target || '';
    syncFormState.auto_scan = false;
    syncFormState.task_type = 'oneshot';
    syncFormState.interval_hours = 24;

    try {
      const [groupRes, scopeRes, policyRes, assetRes] = await Promise.all([
        request.get('/asset_group/', { params: { size: 1000 } }),
        request.get('/asset_scope/', { params: { size: 1000 } }),
        policyList.value.length === 0 ? request.get('/policy/', { params: { size: 1000 } }) : Promise.resolve({ code: 200, items: policyList.value }),
        request.get('/icp/asset', { params: { task_id: props.task._id, query_type: 'web', size: 10000 } })
      ]);

      if (groupRes.code === 200) {
        groupList.value = groupRes.items || groupRes.data?.items || [];
      }
      if (scopeRes.code === 200) {
        assetScopes.value = scopeRes.items || scopeRes.data?.items || [];
      }
      if (policyRes.code === 200 && policyRes.items) {
        // 不做静默兜底：扫描策略必须由用户显式选择，避免无意识地下发探测/周期任务
        policyList.value = policyRes.items || [];
      }

      // 处理任务域名
      if (assetRes.code === 200) {
        const items = assetRes.items || assetRes.data?.items || [];
        const domainSet = new Set();
        items.forEach(item => {
          const d = item.domain || item.ym;
          if (d && typeof d === 'string') {
            domainSet.add(d.trim());
          }
        });
        allTaskWebDomains.value = Array.from(domainSet);
      }

      // 如果外部传入了预选域名，优先使用
      if (props.preSelectedDomains && props.preSelectedDomains.length > 0) {
        selectedDomainKeys.value = props.preSelectedDomains.slice();
      } else {
        selectedDomainKeys.value = allTaskWebDomains.value.slice();
      }

      // 若已有同步资产组，自动反查所属集团
      if (syncFormState.scope_id) {
        const matchedScope = assetScopes.value.find(s => s._id === syncFormState.scope_id);
        if (matchedScope && matchedScope.group_id) {
          syncFormState.group_id = matchedScope.group_id;
        }
      }
    } catch (error) {
      console.error('加载同步弹窗数据失败', error);
      message.error(taskText('tasks.failedToLoadAssetGroups'));
    } finally {
      modalDataLoading.value = false;
    }
  }
});

const submitSync = async () => {
  if (syncFormState.mode === 'existing' && !syncFormState.scope_id) {
    message.error(taskText('tasks.selectAnExistingAssetGroup'));
    return;
  }
  if (syncFormState.mode === 'new' && !syncFormState.target_name.trim()) {
    message.error(taskText('tasks.enterAnAssetGroupName'));
    return;
  }
  if (selectedDomainKeys.value.length === 0) {
    message.error(taskText('tasks.selectAtLeastOneDomainToSync'));
    return;
  }
  if (syncFormState.auto_scan && !syncFormState.policy_id) {
    message.error(taskText('tasks.selectAScanPolicy'));
    return;
  }

  try {
    syncLoading.value = true;
    const payload = {
      mode: syncFormState.mode,
      target_name: syncFormState.target_name.trim(),
      scope_id: syncFormState.scope_id,
      group_id: syncFormState.group_id,
      selected_domains: selectedDomainKeys.value,
      auto_scan: syncFormState.auto_scan,
      task_type: syncFormState.task_type,
      policy_id: syncFormState.policy_id,
      interval_hours: syncFormState.interval_hours
    };

    const res = await request.post(`/icp/sync/${props.task._id}`, payload);
    if (res.code === 200) {
      const data = res.data || res;
      syncResult.scope_id = data.scope_id || payload.scope_id;
      syncResult.target_name = data.target_name || payload.target_name;
      syncResult.group_name = data.group_name || '';
      syncResult.insert_count = data.insert_count || 0;
      syncResult.duplicate_count = data.duplicate_count || 0;
      syncResult.task_triggered_count = data.task_triggered_count || 0;

      // 原位切换为结果看板
      step.value = 'result';
      emit('success', syncResult);
    } else {
      message.error(res.message || taskText('tasks.syncFailedLabel'));
    }
  } catch (error) {
    console.error('同步失败', error);
    message.error(taskText('tasks.networkErrorSyncFailed'));
  } finally {
    syncLoading.value = false;
  }
};

const handleStayHere = () => {
  emit('update:open', false);
};

const handleGoToScope = () => {
  emit('update:open', false);
  if (syncResult.scope_id) {
    router.push({
      path: '/group',
      query: { scope_id: syncResult.scope_id }
    });
  } else {
    router.push('/group');
  }
};
</script>

<style scoped>
/* 扫描策略为条件必填项，缺少时给出显式提示而非静默兜底 */
.policy-required-hint {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--arl-warning-color, #faad14);
}

.task-new-count { color: var(--arl-theme-color); font-weight: bold; margin-right: 8px; }
.task-existing-count { color: #8c8c8c; margin-right: 8px; }
.task-selection-count { margin-left: 8px; color: #52c41a; }
.task-compact-tag { margin-right: 0; }
.task-result-heading { font-size: 18px; font-weight: 600; }
.task-secondary-label { color: var(--arl-text-color); opacity: 0.75; }
.task-result-label { font-size: 12px; color: var(--arl-text-color); opacity: 0.65; margin-top: 4px; }
</style>
