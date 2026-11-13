<template>
  <div>
    <a-spin :spinning="cdnLoading">
      <div style="display: flex; gap: 0; height: calc(100vh - 180px); min-height: 580px; border-radius: 12px; overflow: hidden; box-shadow: 0 12px 48px rgba(0, 0, 0, 0.08), 0 4px 16px rgba(0, 0, 0, 0.04); border: 1px solid rgba(0,0,0,0.05); background: var(--arl-bg-white);"> 
        
        <!-- 左侧：CDN 列表 -->
        <div style="width: 256px; flex-shrink: 0; border-right: 1px solid var(--arl-border-color); background: var(--arl-bg-white); display: flex; flex-direction: column;">
          <div style="padding: 16px; border-bottom: 1px solid var(--arl-border-color); min-height: 64px; box-sizing: border-box;">
            <div style="display: flex; gap: 8px;">
              <a-input-search v-model:value="cdnSearchText" :placeholder="pageText('pages.searchCdns')" class="page-search-field" />
              <a-button 
                v-if="isCdnDirty" 
                type="primary" 
                class="breathing-btn" 
                @click="saveCdnData" 
                :loading="cdnSaveLoading" 
                style="padding: 0 8px; background-color: #52c41a; border-color: #52c41a;" 
                :title="pageText('pages.unsavedChanges')"
              >
                <template #icon><span style="margin-right:0px;">💾</span></template>
              </a-button>
              <a-button type="primary" @click="openCdnDrawer" class="page-icon-padding" :title="pageText('pages.addCdnFingerprint')">
                <template #icon><span style="margin-right:0px;">➕</span></template>
              </a-button>
            </div>
          </div>
          <div class="hide-scrollbar" style="flex: 1; overflow-y: auto; padding: 12px 8px;">
            <div v-if="filteredCdnList.length === 0" style="padding: 48px 24px; text-align: center; color: var(--arl-text-color); opacity: 0.65; display: flex; flex-direction: column; align-items: center; gap: 12px;">
              <span style="font-size: 32px; opacity: 0.8;">📭</span>
              <span class="page-label">{{ pageText('pages.cdnNotFound') }}</span>
            </div>
            <div style="display: flex; flex-direction: column; gap: 4px;">
              <div
                v-for="item in filteredCdnList" :key="item.name"
                class="custom-list-item"
                :class="{ 'is-active': selectedCdnName === item.name }"
                @click="selectedCdnName = item.name"
              >
                <div style="display: flex; align-items: flex-start; gap: 8px;">
                  <span style="font-size: 16px; margin-top: 2px; opacity: 0.9;">🌐</span>
                  <div style="display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 0;">
                    <span class="dict-title" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500;">{{ item.name }}</span>
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                      <span class="dict-subtitle">{{ pageText('pages.cdnRuleCounts', { cnames: (item.cname_domain || []).length, ips: (item.ip_cidr || []).length }) }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- 右侧：详情面板 -->
        <div style="flex: 1; overflow: hidden; display: flex; flex-direction: column; min-width: 0; background: var(--arl-bg-white); position: relative;">
          <!-- 健康概览 -->
          <div v-if="!selectedCdn" class="health-dashboard-wrapper">
            <div class="health-dashboard-bg"></div>
            <div class="health-content">
              <div class="health-icon-pulse">
                <span style="font-size: 56px;">🌍</span>
              </div>
              <h3 class="health-title">{{ pageText('pages.cdnDataOverview') }}</h3>
              <div class="health-stats-container">
                <div class="health-stat-card primary-stat">
                  <div class="stat-value">{{ cdnList.length }}</div>
                  <div class="stat-label">{{ pageText('pages.cdnProviders') }}</div>
                </div>
                <div class="health-stat-card warning-stat">
                  <div class="stat-value">{{ totalCnameCount }}</div>
                  <div class="stat-label">{{ pageText('pages.cnameRules') }}</div>
                </div>
                <div class="health-stat-card danger-stat" style="background: rgba(245, 34, 45, 0.04); border: 1px solid rgba(245, 34, 45, 0.1);">
                  <div class="stat-value" style="color: #cf1322;">{{ totalIpCount }}</div>
                  <div class="stat-label page-danger-emphasis">{{ pageText('pages.ipRangeRules') }}</div>
                </div>
              </div>
              <div class="health-hint">
                <span class="pulse-dot"></span>
                <span>{{ pageText('pages.systemStatusIsHealthySelectACdnOnThe') }}</span>
              </div>
            </div>
          </div>
          
          <!-- CDN 详情与编辑 -->
          <div v-else class="native-preview-container">
            <div class="native-toolbar">
               <div>
                 <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 4px;">
                   <h3 style="margin: 0; font-size: 16px; font-weight: 600; color: var(--arl-text-color);">{{ selectedCdn.name }}</h3>
                   <a-tag color="cyan" class="page-flush-tag">{{ pageText('pages.cdnFingerprints') }}</a-tag>
                 </div>
                 <div class="page-secondary-help">{{ pageText('pages.cdnRuleCounts', { cnames: (selectedCdn.cname_domain || []).length, ips: (selectedCdn.ip_cidr || []).length }) }}</div>
               </div>
               <div style="display: flex; gap: 8px; align-items: center;">
                  <a-button 
                    v-if="isCdnDirty" 
                    type="primary" 
                    @click="saveCdnData" 
                    :loading="cdnSaveLoading"
                    class="breathing-btn"
                    style="background-color: #52c41a; border-color: #52c41a;"
                  >
                    <template #icon><span class="page-icon-gap">💾</span></template> {{ pageText('pages.saveChanges') }}
                  </a-button>
                  <a-popconfirm :title="pageText('pages.deleteThisCdnTheDeletionTakesEffectAfterSaving')" placement="bottomRight" @confirm="deleteSelectedCdn">
                    <a-button danger><template #icon><span class="page-icon-gap">🗑️</span></template> {{ pageText('pages.deleteFingerprint') }}</a-button>
                  </a-popconfirm>
                  <a-button type="primary" ghost @click="editSelectedCdn"><template #icon><span class="page-icon-gap">✏️</span></template> {{ pageText('pages.editFingerprint') }}</a-button>
               </div>
            </div>

            <!-- 极简内容预览区 (双区块) -->
            <div class="native-preview-area hide-scrollbar" style="display: flex; flex-direction: column; gap: 16px; padding-bottom: 24px;">
              
              <!-- CNAME 规则 -->
              <div class="native-code-wrapper" style="flex: none; display: flex; flex-direction: column; padding: 0;">
                <div style="padding: 8px 16px; background: var(--arl-bg-subtle); border-bottom: 1px solid var(--arl-border-color); font-weight: 500; font-size: 13px; color: var(--arl-text-color); display: flex; justify-content: space-between; align-items: center;">
                  <span>{{ pageText('pages.cnameRulesLabel2') }}{{ (selectedCdn.cname_domain || []).length }})</span>
                  <a-button size="small" type="text" @click="() => copyTextList(selectedCdn.cname_domain, pageText('pages.cnameRulesLabel3'))">
                    {{ pageText('pages.copy') }}
                  </a-button>
                </div>
                <div style="display: flex; position: relative; padding: 16px;">
                  <div class="native-line-numbers" v-if="selectedCdn.cname_domain && selectedCdn.cname_domain.length > 0">
                    <div v-for="n in selectedCdn.cname_domain.length" :key="'cname-'+n" class="line-number">{{ n }}</div>
                  </div>
                  <div class="native-code-content" style="min-height: 40px;">
                    <div v-if="!(selectedCdn.cname_domain && selectedCdn.cname_domain.length > 0)" class="empty-code" style="padding-top: 0;">
                      <span>{{ pageText('pages.noCnameRules') }}</span>
                    </div>
                    <pre v-else class="code-text">{{ selectedCdn.cname_domain.join('\n') }}</pre>
                  </div>
                </div>
              </div>

              <!-- IP CIDR 规则 -->
              <div class="native-code-wrapper" style="flex: none; display: flex; flex-direction: column; padding: 0;">
                <div style="padding: 8px 16px; background: var(--arl-bg-subtle); border-bottom: 1px solid var(--arl-border-color); font-weight: 500; font-size: 13px; color: var(--arl-text-color); display: flex; justify-content: space-between; align-items: center;">
                  <span>{{ pageText('pages.ipCidrRules') }}{{ (selectedCdn.ip_cidr || []).length }})</span>
                  <a-button size="small" type="text" @click="() => copyTextList(selectedCdn.ip_cidr, pageText('pages.ipCidrRulesLabel2'))">
                    {{ pageText('pages.copy') }}
                  </a-button>
                </div>
                <div style="display: flex; position: relative; padding: 16px;">
                  <div class="native-line-numbers" v-if="selectedCdn.ip_cidr && selectedCdn.ip_cidr.length > 0">
                    <div v-for="n in selectedCdn.ip_cidr.length" :key="'ip-'+n" class="line-number">{{ n }}</div>
                  </div>
                  <div class="native-code-content" style="min-height: 40px;">
                    <div v-if="!(selectedCdn.ip_cidr && selectedCdn.ip_cidr.length > 0)" class="empty-code" style="padding-top: 0;">
                      <span>{{ pageText('pages.noIpCidrRules') }}</span>
                    </div>
                    <pre v-else class="code-text">{{ selectedCdn.ip_cidr.join('\n') }}</pre>
                  </div>
                </div>
              </div>

            </div>
          </div>

        </div>
      </div>
    </a-spin>

    <a-drawer
      v-model:open="cdnDrawerVisible"
      :title="isEditingCdn ? pageText('pages.editCdnFingerprint') : pageText('pages.addCdnFingerprint')"
      placement="right"
      width="450"
      @close="resetCdnForm"
    >
      <div style="display: flex; flex-direction: column; height: 100%;">
        <div class="hide-scrollbar" style="flex: 1; overflow-y: auto; padding-right: 4px;">
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
          <a-button @click="cdnDrawerVisible = false" class="page-inline-gap">{{ pageText('tasks.cancel') }}</a-button>
          <a-button type="primary" @click="submitCdnDrawer">{{ pageText('pages.saveLabel2') }}</a-button>
        </div>
      </div>
    </a-drawer>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue';
import { useI18n } from 'vue-i18n';
import { message } from 'ant-design-vue';
import request from '@/utils/request';
import { copyText } from '@/utils/clipboard';

const { t: pageText } = useI18n({ useScope: 'global' });

const cdnList = ref([]);
const originalCdnList = ref([]);
const cdnLoading = ref(false);
const cdnSaveLoading = ref(false);

const isCdnDirty = computed(() => {
  return JSON.stringify(cdnList.value) !== JSON.stringify(originalCdnList.value);
});

const cdnSearchText = ref('');
const selectedCdnName = ref('');

const filteredCdnList = computed(() => {
  if (!cdnSearchText.value) return cdnList.value;
  return cdnList.value.filter(item =>
    item.name.toLowerCase().includes(cdnSearchText.value.toLowerCase())
  );
});

const selectedCdn = computed(() => {
  if (!selectedCdnName.value) return null;
  return cdnList.value.find(item => item.name === selectedCdnName.value);
});

const totalCnameCount = computed(() => {
  return cdnList.value.reduce((acc, curr) => acc + (curr.cname_domain || []).length, 0);
});

const totalIpCount = computed(() => {
  return cdnList.value.reduce((acc, curr) => acc + (curr.ip_cidr || []).length, 0);
});

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
  ipText: ''
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
  currentEditIndex.value = cdnList.value.findIndex(c => c.name === selectedCdn.value.name);
  currentCdnForm.name = selectedCdn.value.name;
  currentCdnForm.cnameText = (selectedCdn.value.cname_domain || []).join('\n');
  currentCdnForm.ipText = (selectedCdn.value.ip_cidr || []).join('\n');
  cdnDrawerVisible.value = true;
};

const deleteSelectedCdn = () => {
  if (!selectedCdn.value) return;
  const index = cdnList.value.findIndex(c => c.name === selectedCdn.value.name);
  if (index > -1) {
    cdnList.value.splice(index, 1);
    selectedCdnName.value = '';
    message.success(pageText('pages.deletedLocallySaveAllChangesToApply'));
  }
};

const resetCdnForm = () => {
  cdnDrawerVisible.value = false;
};

const submitCdnDrawer = () => {
  if (!currentCdnForm.name.trim()) {
    message.warning(pageText('pages.enterACdnName'));
    return;
  }
  const cname_domain = currentCdnForm.cnameText.split('\n').map(s => s.trim()).filter(s => s);
  const ip_cidr = currentCdnForm.ipText.split('\n').map(s => s.trim()).filter(s => s);

  const cidrRe = /^(\d{1,3}\.){3}\d{1,3}(\/\d{1,2})?$/;
  const invalidCidr = ip_cidr.filter(cidr => {
    if (!cidrRe.test(cidr)) return true;
    const parts = cidr.split('/');
    const octets = parts[0].split('.').map(Number);
    if (octets.some(o => o < 0 || o > 255)) return true;
    if (parts[1] && (parseInt(parts[1]) < 0 || parseInt(parts[1]) > 32)) return true;
    return false;
  });
  if (invalidCidr.length > 0) {
    message.error(pageText('pages.invalidIpEGIpUseAnIpv4Address', { ip: invalidCidr[0] }));
    return;
  }
  const invalidCname = cname_domain.filter(d => /[\s/\\]/.test(d));
  if (invalidCname.length > 0) {
    message.error(pageText('pages.invalidCnameSuffixEGSuffixUseADomain', { suffix: invalidCname[0] }));
    return;
  }

  if (isEditingCdn.value && currentEditIndex.value > -1) {
    cdnList.value[currentEditIndex.value] = {
      name: currentCdnForm.name.trim(),
      cname_domain,
      ip_cidr
    };
    selectedCdnName.value = currentCdnForm.name.trim();
  } else {
    if (cdnList.value.find(c => c.name === currentCdnForm.name.trim())) {
      message.warning(pageText('pages.thisCdnNameAlreadyExists'));
      return;
    }
    cdnList.value.unshift({
      name: currentCdnForm.name.trim(),
      cname_domain,
      ip_cidr
    });
    selectedCdnName.value = currentCdnForm.name.trim();
  }
  cdnDrawerVisible.value = false;
};

const fetchCdnList = async () => {
  cdnLoading.value = true;
  try {
    const res = await request.get('/api/cdn_dict/list');
    if (res.code === 200) {
      cdnList.value = res.data || [];
      originalCdnList.value = JSON.parse(JSON.stringify(cdnList.value));
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

const saveCdnData = async () => {
  cdnSaveLoading.value = true;
  try {
    const res = await request.post('/api/cdn_dict/save', {
      data: cdnList.value
    });
    if (res.code === 200) {
      message.success(pageText('pages.allChangesSaved'));
      originalCdnList.value = JSON.parse(JSON.stringify(cdnList.value));
      fetchCdnList();
    } else {
      message.error(res.message || pageText('pages.failedToSaveLabel2'));
    }
  } catch (error) {
    message.error(pageText('pages.saveRequestFailed'));
    console.error(error);
  } finally {
    cdnSaveLoading.value = false;
  }
};

const closeDrawer = () => {
  cdnDrawerVisible.value = false;
};

onMounted(() => {
  fetchCdnList();
});

defineExpose({
  fetchCdnList,
  closeDrawer
});
</script>

<style scoped>
.page-search-field { flex: 1; border-radius: 4px; }
.page-icon-padding { padding: 0 8px; }
.page-label { font-size: 13px; font-weight: 500; }
.page-icon-gap { margin-right: 4px; }
.page-inline-gap { margin-right: 8px; }
.page-danger-emphasis { color: #cf1322; }
.page-flush-tag { margin: 0; }
.page-secondary-help { color: var(--arl-text-color); opacity: 0.55; font-size: 12px; }

.custom-list-item {
  padding: 10px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  border: 1px solid transparent;
  color: var(--arl-text-color);
}
.custom-list-item:hover {
  background: var(--arl-bg-light);
  transform: translateX(4px);
}
.custom-list-item.is-active {
  background: var(--arl-theme-color);
  color: #fff;
  box-shadow: 0 4px 12px color-mix(in srgb, var(--arl-theme-color) 30%, transparent);
}
.custom-list-item.is-active .dict-title,
.custom-list-item.is-active .dict-subtitle {
  color: #fff;
}
.dict-subtitle {
  font-size: 12px;
  opacity: 0.65;
}
.hide-scrollbar::-webkit-scrollbar {
  display: none;
}
.hide-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

.health-dashboard-wrapper {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--arl-bg-white);
  overflow: hidden;
}
.health-dashboard-bg {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: radial-gradient(circle at 50% -20%, color-mix(in srgb, var(--arl-theme-color) 12%, transparent), transparent 60%),
              radial-gradient(circle at -20% 80%, rgba(114, 46, 209, 0.05), transparent 50%);
  pointer-events: none;
}
.health-content {
  position: relative;
  z-index: 1;
  text-align: center;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
}
.health-icon-pulse {
  animation: float 4s ease-in-out infinite;
  margin-bottom: 8px;
}
@keyframes float {
  0% { transform: translateY(0px); }
  50% { transform: translateY(-10px); }
  100% { transform: translateY(0px); }
}
.health-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--arl-text-color);
  margin: 0;
  letter-spacing: 0.5px;
}
.health-stats-container {
  display: flex;
  gap: 24px;
  margin-top: 16px;
}
.health-stat-card {
  background: var(--arl-bg-subcard);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--arl-border-color);
  border-radius: 16px;
  padding: 24px 40px;
  min-width: 180px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.06);
  transition: transform 0.3s ease, box-shadow 0.3s ease, border-color 0.3s ease;
}
.health-stat-card:hover {
  transform: translateY(-4px);
  box-shadow: 0 12px 32px rgba(0,0,0,0.12);
  border-color: color-mix(in srgb, var(--arl-theme-color) 35%, var(--arl-border-color));
}
.stat-value {
  font-size: 36px;
  font-weight: 800;
  background-clip: text;
  -webkit-background-clip: text;
  color: transparent;
  line-height: 1.2;
}
.primary-stat .stat-value {
  background-image: linear-gradient(135deg, var(--arl-theme-color) 0%, #36cfc9 100%);
}
.warning-stat .stat-value {
  background-image: linear-gradient(135deg, #fa8c16 0%, #ffc53d 100%);
}
.stat-label {
  font-size: 14px;
  color: var(--arl-text-secondary);
  margin-top: 8px;
  font-weight: 500;
}
.health-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 32px;
  color: var(--arl-text-secondary);
  font-size: 13px;
  background: var(--arl-bg-subcard);
  padding: 8px 16px;
  border-radius: 20px;
  border: 1px solid var(--arl-border-color);
}
.pulse-dot {
  width: 8px;
  height: 8px;
  background: #52c41a;
  border-radius: 50%;
  box-shadow: 0 0 0 0 rgba(82, 196, 26, 0.7);
  animation: dotPulse 2s infinite;
}
@keyframes dotPulse {
  0% { box-shadow: 0 0 0 0 rgba(82, 196, 26, 0.7); }
  70% { box-shadow: 0 0 0 8px rgba(82, 196, 26, 0); }
  100% { box-shadow: 0 0 0 0 rgba(82, 196, 26, 0); }
}

.native-preview-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--arl-bg-white);
  position: relative;
  overflow: hidden;
}
.native-toolbar {
  padding: 16px 24px;
  border-bottom: 1px solid var(--arl-border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: var(--arl-bg-white);
  min-height: 64px;
}
.native-preview-area {
  flex: 1;
  display: flex;
  overflow-y: auto;
  padding: 24px;
  background: var(--arl-bg-light);
}
.native-code-wrapper {
  flex: 1;
  display: flex;
  background: var(--arl-bg-white);
  border: 1px solid var(--arl-border-color);
  border-radius: 8px;
  padding: 20px;
  box-shadow: 0 1px 2px rgba(0,0,0,0.02);
  font-family: 'Fira Code', 'SFMono-Regular', Consolas, Menlo, monospace;
  font-size: 13px;
  line-height: 1.6;
}
.native-line-numbers {
  display: flex;
  flex-direction: column;
  padding-right: 16px;
  border-right: 1px solid var(--arl-border-color);
  margin-right: 16px;
  color: var(--arl-text-color);
  opacity: 0.35;
  text-align: right;
  user-select: none;
  min-width: 40px;
}
.line-number {
  height: 21px;
}
.native-code-content {
  flex: 1;
  min-width: 0;
}
.code-text {
  margin: 0;
  color: var(--arl-text-color);
  opacity: 0.85;
  white-space: pre-wrap;
  word-break: break-all;
  font-family: inherit;
}
.empty-code {
  color: var(--arl-text-color);
  opacity: 0.3;
  font-style: italic;
  padding-top: 20px;
  text-align: center;
}

@keyframes btn-breathing {
  0% { box-shadow: 0 0 0 0 rgba(82, 196, 26, 0.4); }
  70% { box-shadow: 0 0 0 6px rgba(82, 196, 26, 0); }
  100% { box-shadow: 0 0 0 0 rgba(82, 196, 26, 0); }
}
.breathing-btn {
  animation: btn-breathing 2s infinite;
}
</style>
