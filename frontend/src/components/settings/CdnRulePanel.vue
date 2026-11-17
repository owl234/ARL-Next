<template>
  <div>
    <a-spin :spinning="cdnLoading">
      <div class="arl-split-workbench">
        <!-- 左侧：CDN 厂商清单 -->
        <div class="arl-split-sidebar">
          <div class="arl-split-sidebar-head">
            <a-input-search
              v-model:value="cdnSearchText"
              :placeholder="pageText('pages.searchCdns')"
              size="small"
              allow-clear
              style="flex: 1;"
            />
            <a-tooltip :title="pageText('pages.addCdnFingerprint')">
              <a-button type="primary" size="small" @click="openCdnDrawer">
                <template #icon><PlusOutlined /></template>
              </a-button>
            </a-tooltip>
          </div>
          <div class="cdn-summary-strip">
            {{ pageText('pages.cdnOverviewSummary', { count: cdnList.length, cnames: totalCnameCount, ips: totalIpCount }) }}
          </div>
          <div class="arl-split-sidebar-body">
            <ArlEmpty v-if="filteredCdnList.length === 0" :description="pageText('pages.cdnNotFound')" />
            <div
              v-for="item in filteredCdnList"
              :key="item.name"
              class="arl-split-item"
              :class="{ 'is-active': selectedCdnName === item.name }"
              @click="selectedCdnName = item.name"
            >
              <div class="cdn-item-row">
                <GlobalOutlined class="cdn-item-icon" />
                <div class="cdn-item-meta">
                  <span class="arl-split-item-title cdn-item-name">{{ item.name }}</span>
                  <span class="arl-split-item-sub">
                    {{ pageText('pages.cdnRuleCounts', { cnames: (item.cname_domain || []).length, ips: (item.ip_cidr || []).length }) }}
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧：详情与即时维护 -->
        <div class="arl-split-main">
          <div v-if="!selectedCdn" class="cdn-empty-center">
            <ArlEmpty :description="pageText('pages.cdnNotFound')">
              <a-button type="primary" size="small" @click="openCdnDrawer">
                <template #icon><PlusOutlined /></template>
                {{ pageText('pages.addCdnFingerprint') }}
              </a-button>
            </ArlEmpty>
          </div>

          <template v-else>
            <div class="arl-split-toolbar">
              <div>
                <div class="cdn-detail-title-row">
                  <h3 class="cdn-detail-title">{{ selectedCdn.name }}</h3>
                  <a-tag color="cyan" style="margin: 0;">{{ pageText('pages.cdnFingerprints') }}</a-tag>
                  <span class="cdn-instant-badge">{{ pageText('pages.settingsInstantModeHint') }}</span>
                </div>
                <div class="cdn-detail-sub">
                  {{ pageText('pages.cdnRuleCounts', { cnames: (selectedCdn.cname_domain || []).length, ips: (selectedCdn.ip_cidr || []).length }) }}
                </div>
              </div>
              <div style="display: flex; gap: 8px; align-items: center;">
                <a-popconfirm
                  :title="pageText('pages.deleteThisCdnTheDeletionTakesEffectAfterSaving')"
                  placement="bottomRight"
                  @confirm="deleteSelectedCdn"
                >
                  <a-button danger size="small" :loading="cdnSaveLoading">
                    <template #icon><DeleteOutlined /></template>
                    {{ pageText('pages.deleteFingerprint') }}
                  </a-button>
                </a-popconfirm>
                <a-button type="primary" ghost size="small" @click="editSelectedCdn">
                  <template #icon><EditOutlined /></template>
                  {{ pageText('pages.editFingerprint') }}
                </a-button>
              </div>
            </div>

            <div class="arl-split-preview-area">
              <!-- CNAME 规则 -->
              <div class="arl-code-wrapper cdn-rule-box">
                <div class="cdn-rule-head">
                  <span>{{ pageText('pages.cnameRulesLabel2') }}{{ (selectedCdn.cname_domain || []).length }})</span>
                  <a-button
                    size="small"
                    type="text"
                    @click="() => copyTextList(selectedCdn.cname_domain, pageText('pages.cnameRulesLabel3'))"
                  >
                    <template #icon><CopyOutlined /></template>
                    {{ pageText('pages.copy') }}
                  </a-button>
                </div>
                <div class="cdn-rule-content">
                  <div v-if="selectedCdn.cname_domain && selectedCdn.cname_domain.length > 0" class="arl-code-lines">
                    <div v-for="n in selectedCdn.cname_domain.length" :key="'cname-' + n" class="arl-code-line-num">{{ n }}</div>
                  </div>
                  <div class="arl-code-body">
                    <div v-if="!(selectedCdn.cname_domain && selectedCdn.cname_domain.length > 0)" class="arl-code-empty">
                      {{ pageText('pages.noCnameRules') }}
                    </div>
                    <pre v-else class="arl-code-pre">{{ selectedCdn.cname_domain.join('\n') }}</pre>
                  </div>
                </div>
              </div>

              <!-- IP CIDR 规则 -->
              <div class="arl-code-wrapper cdn-rule-box">
                <div class="cdn-rule-head">
                  <span>{{ pageText('pages.ipCidrRules') }}{{ (selectedCdn.ip_cidr || []).length }})</span>
                  <a-button
                    size="small"
                    type="text"
                    @click="() => copyTextList(selectedCdn.ip_cidr, pageText('pages.ipCidrRulesLabel2'))"
                  >
                    <template #icon><CopyOutlined /></template>
                    {{ pageText('pages.copy') }}
                  </a-button>
                </div>
                <div class="cdn-rule-content">
                  <div v-if="selectedCdn.ip_cidr && selectedCdn.ip_cidr.length > 0" class="arl-code-lines">
                    <div v-for="n in selectedCdn.ip_cidr.length" :key="'ip-' + n" class="arl-code-line-num">{{ n }}</div>
                  </div>
                  <div class="arl-code-body">
                    <div v-if="!(selectedCdn.ip_cidr && selectedCdn.ip_cidr.length > 0)" class="arl-code-empty">
                      {{ pageText('pages.noIpCidrRules') }}
                    </div>
                    <pre v-else class="arl-code-pre">{{ selectedCdn.ip_cidr.join('\n') }}</pre>
                  </div>
                </div>
              </div>
            </div>
          </template>
        </div>
      </div>
    </a-spin>

    <a-drawer
      v-model:open="cdnDrawerVisible"
      :title="isEditingCdn ? pageText('pages.editCdnFingerprint') : pageText('pages.addCdnFingerprint')"
      placement="right"
      width="460"
      @close="resetCdnForm"
    >
      <div style="display: flex; flex-direction: column; height: 100%;">
        <div style="flex: 1; overflow-y: auto; padding-right: 4px;">
          <a-form :label-wrap="true" :model="currentCdnForm" layout="vertical">
            <a-form-item :label="pageText('pages.cdnName')" required>
              <a-input v-model:value="currentCdnForm.name" :placeholder="pageText('pages.eGAlibabaCloudCdn')" />
            </a-form-item>
            <a-form-item :label="pageText('pages.cnameSuffixes')">
              <a-textarea v-model:value="currentCdnForm.cnameText" :rows="8" :placeholder="pageText('pages.oneCnameSuffixPerLineEGKunlunpiCom')" />
            </a-form-item>
            <a-form-item :label="pageText('pages.ipRangesCidr')">
              <a-textarea v-model:value="currentCdnForm.ipText" :rows="8" :placeholder="pageText('pages.oneIpRangePerLineEG10321')" />
            </a-form-item>
          </a-form>
        </div>
        <div style="border-top: 1px solid var(--arl-border-color); padding-top: 16px; text-align: right; margin-top: 16px;">
          <a-button @click="cdnDrawerVisible = false" style="margin-right: 8px;" :disabled="cdnSaveLoading">{{ pageText('tasks.cancel') }}</a-button>
          <a-button type="primary" :loading="cdnSaveLoading" @click="submitCdnDrawer">{{ pageText('pages.saveLabel2') }}</a-button>
        </div>
      </div>
    </a-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, nextTick, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { message } from 'ant-design-vue';
import {
  GlobalOutlined,
  PlusOutlined,
  DeleteOutlined,
  EditOutlined,
  CopyOutlined,
} from '@ant-design/icons-vue';
import ArlEmpty from '@/components/ArlEmpty.vue';
import request from '@/utils/request';
import { copyText } from '@/utils/clipboard';

const { t: pageText } = useI18n({ useScope: 'global' });

const cdnList = ref([]);
const cdnLoading = ref(false);
const cdnSaveLoading = ref(false);
const cdnSearchText = ref('');
const selectedCdnName = ref('');

const filteredCdnList = computed(() => {
  if (!cdnSearchText.value) return cdnList.value;
  const kw = cdnSearchText.value.toLowerCase();
  return cdnList.value.filter((item) => item.name.toLowerCase().includes(kw));
});

const selectedCdn = computed(() => {
  if (!selectedCdnName.value) return null;
  return cdnList.value.find((item) => item.name === selectedCdnName.value) || null;
});

const totalCnameCount = computed(() => cdnList.value.reduce((acc, curr) => acc + (curr.cname_domain || []).length, 0));
const totalIpCount = computed(() => cdnList.value.reduce((acc, curr) => acc + (curr.ip_cidr || []).length, 0));

const ensureDefaultSelection = () => {
  if (cdnList.value.length === 0) {
    selectedCdnName.value = '';
    return;
  }
  if (!selectedCdnName.value || !cdnList.value.some((c) => c.name === selectedCdnName.value)) {
    selectedCdnName.value = cdnList.value[0].name;
  }
};

const copyTextList = async (list, label = pageText('tasks.content')) => {
  if (!list || !list.length) {
    message.warning(pageText('pages.noDataForType', { type: label }));
    return;
  }
  const ok = await copyText(list.join('\n'));
  if (ok) {
    message.success(pageText('pages.typeCopiedToClipboard', { type: label }));
  } else {
    message.error(pageText('pages.copyFailedSelectAndCopyTheTextManually'));
  }
};

const cdnDrawerVisible = ref(false);
const isEditingCdn = ref(false);
const currentCdnForm = reactive({
  name: '',
  cnameText: '',
  ipText: '',
});
const currentEditIndex = ref(-1);

const openCdnDrawer = () => {
  isEditingCdn.value = false;
  currentEditIndex.value = -1;
  currentCdnForm.name = '';
  currentCdnForm.cnameText = '';
  currentCdnForm.ipText = '';
  cdnDrawerVisible.value = true;
};

const editSelectedCdn = () => {
  if (!selectedCdn.value) return;
  isEditingCdn.value = true;
  currentEditIndex.value = cdnList.value.findIndex((c) => c.name === selectedCdn.value.name);
  currentCdnForm.name = selectedCdn.value.name;
  currentCdnForm.cnameText = (selectedCdn.value.cname_domain || []).join('\n');
  currentCdnForm.ipText = (selectedCdn.value.ip_cidr || []).join('\n');
  cdnDrawerVisible.value = true;
};

const resetCdnForm = () => {
  cdnDrawerVisible.value = false;
};

const persistCdnList = async (nextList, successText) => {
  cdnSaveLoading.value = true;
  try {
    const res = await request.post('/api/cdn_dict/save', { data: nextList });
    if (res.code === 200) {
      cdnList.value = nextList;
      ensureDefaultSelection();
      if (successText) message.success(successText);
      return true;
    }
    message.error(res.message || pageText('pages.failedToSaveLabel2'));
    return false;
  } catch (error) {
    const errMsg = error?.response?.data?.message || pageText('pages.saveRequestFailed');
    message.error(errMsg);
    console.error(error);
    return false;
  } finally {
    cdnSaveLoading.value = false;
  }
};

const deleteSelectedCdn = async () => {
  if (!selectedCdn.value) return;
  const targetName = selectedCdn.value.name;
  const nextList = cdnList.value.filter((c) => c.name !== targetName);
  const ok = await persistCdnList(nextList, pageText('pages.cdnInstantDeleted', { name: targetName }));
  if (ok) {
    ensureDefaultSelection();
  }
};

const submitCdnDrawer = async () => {
  const name = currentCdnForm.name.trim();
  if (!name) {
    message.warning(pageText('pages.enterACdnName'));
    return;
  }
  const cname_domain = currentCdnForm.cnameText.split('\n').map((s) => s.trim()).filter(Boolean);
  const ip_cidr = currentCdnForm.ipText.split('\n').map((s) => s.trim()).filter(Boolean);

  const cidrRe = /^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/;
  const invalidCidr = ip_cidr.filter((cidr) => {
    if (!cidrRe.test(cidr)) return true;
    const parts = cidr.split('/');
    const octets = parts[0].split('.').map(Number);
    if (octets.some((o) => o < 0 || o > 255)) return true;
    if (parts[1] && (parseInt(parts[1], 10) < 0 || parseInt(parts[1], 10) > 32)) return true;
    return false;
  });
  if (invalidCidr.length > 0) {
    message.error(pageText('pages.invalidIpEGIpUseAnIpv4Address', { ip: invalidCidr[0] }));
    return;
  }
  const invalidCname = cname_domain.filter((d) => /[\s/\\]/.test(d));
  if (invalidCname.length > 0) {
    message.error(pageText('pages.invalidCnameSuffixEGSuffixUseADomain', { suffix: invalidCname[0] }));
    return;
  }

  const nextList = JSON.parse(JSON.stringify(cdnList.value));
  if (isEditingCdn.value && currentEditIndex.value > -1) {
    const duplicate = nextList.some((c, idx) => idx !== currentEditIndex.value && c.name === name);
    if (duplicate) {
      message.warning(pageText('pages.thisCdnNameAlreadyExists'));
      return;
    }
    nextList[currentEditIndex.value] = { name, cname_domain, ip_cidr };
  } else {
    if (nextList.some((c) => c.name === name)) {
      message.warning(pageText('pages.thisCdnNameAlreadyExists'));
      return;
    }
    nextList.unshift({ name, cname_domain, ip_cidr });
  }

  const ok = await persistCdnList(nextList, pageText('pages.cdnInstantSaved', { name }));
  if (ok) {
    selectedCdnName.value = name;
    cdnDrawerVisible.value = false;
  }
};

const fetchCdnList = async () => {
  cdnLoading.value = true;
  try {
    const res = await request.get('/api/cdn_dict/list');
    if (res.code === 200) {
      cdnList.value = res.data || [];
      ensureDefaultSelection();
    } else {
      message.error(res.message || pageText('pages.failedToLoadCdnList'));
    }
  } catch (error) {
    message.error(pageText('pages.cdnListRequestFailed'));
    console.error(error);
  } finally {
    cdnLoading.value = false;
  }
};

const closeDrawer = () => {
  cdnDrawerVisible.value = false;
};

const focusSection = (anchor = 'cdn', retries = 3) => {
  if (!anchor) return;
  nextTick(() => {
    const el = document.querySelector(`[data-setting-anchor="${anchor}"]`);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.classList.add('arl-anchor-flash');
      setTimeout(() => el.classList.remove('arl-anchor-flash'), 2200);
    } else if (retries > 0) {
      setTimeout(() => focusSection(anchor, retries - 1), 60);
    }
  });
};

onMounted(() => {
  fetchCdnList();
});

defineExpose({
  fetchCdnList,
  closeDrawer,
  hasUnsavedChanges: () => false,
  isSaving: () => cdnSaveLoading.value,
  focusSection,
});
</script>

<style scoped>
.cdn-summary-strip {
  padding: 6px 14px;
  font-size: 12px;
  color: var(--arl-text-secondary);
  background: var(--arl-bg-light);
  border-bottom: 1px solid var(--arl-border-color);
}
.cdn-item-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}
.cdn-item-icon {
  margin-top: 3px;
  opacity: 0.78;
  flex-shrink: 0;
}
.cdn-item-meta {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  flex: 1;
}
.cdn-item-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.cdn-empty-center {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}
.cdn-detail-title-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 4px;
}
.cdn-detail-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--arl-text-color);
}
.cdn-instant-badge {
  font-size: 12px;
  color: var(--arl-text-secondary);
}
.cdn-detail-sub {
  font-size: 12px;
  color: var(--arl-text-secondary);
}
.cdn-rule-box {
  flex: none;
  display: flex;
  flex-direction: column;
  padding: 0;
  overflow: hidden;
}
.cdn-rule-head {
  padding: 8px 14px;
  background: var(--arl-bg-subtle);
  border-bottom: 1px solid var(--arl-border-color);
  font-weight: 500;
  font-size: 13px;
  color: var(--arl-text-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.cdn-rule-content {
  display: flex;
  position: relative;
  padding: 14px 16px;
}
</style>
