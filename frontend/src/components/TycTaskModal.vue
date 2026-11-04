<template>
  <a-modal
    :open="open"
    @update:open="val => $emit('update:open', val)"
    :title="taskText('tasks.newEnterpriseOsintTaskLabel')"
    @ok="handleSubmit"
    :confirmLoading="submitLoading"
    width="580px"
    wrapClassName="arl-theme-modal"
    :okText="taskText('tasks.startEnterpriseDiscovery')"
    :cancelText="taskText('tasks.cancel')"
    destroyOnClose
  >
    <a-spin :spinning="configChecking" :tip="taskText('tasks.checkingDiscoveryConfiguration')">
      <!-- 引擎能力状态动态提示 -->
      <a-alert
        v-if="!configChecking"
        :type="tycConfigValid ? 'info' : 'warning'"
        show-icon
        style="margin-bottom: 16px; border-radius: 6px; font-size: 12px;"
      >
        <template #message>
          <span v-if="tycConfigValid" style="color: var(--arl-text-color); line-height: 1.5;">
            {{ taskText('tasks.enterpriseReadyHint') }}
          </span>
          <span v-else-if="tycErrorType === 'banned_location'" style="color: var(--arl-text-color); line-height: 1.5;">
            {{ taskText('tasks.enterpriseBannedLocationHint') }}
            <a @click="goToProxyConfig" class="task-settings-link">{{ taskText('tasks.openProxySettings') }}</a>
          </span>
          <span v-else-if="tycConfigured && tycErrorMsg" style="color: var(--arl-text-color); line-height: 1.5;">
            {{ tycErrorMsg }}
            <a @click="goToApiConfig" class="task-settings-link">{{ taskText('tasks.openSettings') }}</a>
          </span>
          <span v-else style="color: var(--arl-text-color); line-height: 1.5;">
            {{ taskText('tasks.enterpriseIcpHint') }}
            <a @click="goToApiConfig" class="task-settings-link">{{ taskText('tasks.openSettings') }}</a>
          </span>
        </template>
      </a-alert>

      <a-form
        :label-wrap="true"
        ref="formRef"
        :model="formState"
        :rules="rules"
        :label-col="{ style: { width: taskLocale !== 'zh-CN' ? '140px' : '100px' } }"
        :wrapper-col="{ style: { width: taskLocale !== 'zh-CN' ? 'calc(100% - 140px)' : 'calc(100% - 100px)' } }"
      >
        <!-- 核心企业目标输入框 -->
        <a-form-item
          :label="taskText('tasks.targetOrganization')"
          name="rawTarget"
          :tooltip="taskText('tasks.enterATianyanchaCompanyUrlEGHttps')"
        >
          <a-input
            v-model:value="formState.rawTarget"
            :placeholder="taskText('tasks.pasteATianyanchaUrlGidOrEnterThe')"
            allowClear
            @pressEnter="handleSubmit"
          >
            <template #prefix>
              <component :is="parsedGid ? 'LinkOutlined' : 'BankOutlined'" style="color: #bfbfbf;" />
            </template>
          </a-input>

          <!-- 智能识别反馈状态 -->
          <div v-if="parsedGid" style="margin-top: 5px; font-size: 12px; color: var(--ant-primary-color); display: flex; align-items: center; gap: 4px;">
            <check-circle-outlined />
            <span>{{ taskText('tasks.parsedTianyanchaGid') }} <b>{{ parsedGid }}</b> {{ taskText('tasks.theGidWillBeVerifiedAndCombinedDiscovery') }}</span>
          </div>
          <div v-else-if="isCompanyName" style="margin-top: 5px; font-size: 12px; color: #722ed1; display: flex; align-items: center; gap: 4px;">
            <safety-certificate-outlined />
            <span>{{ taskText('tasks.organizationIdentified') }} <b>{{ formState.rawTarget.trim() }}</b> {{ taskText('tasks.sourceMiitIcpRecords') }}</span>
          </div>
        </a-form-item>

        <!-- 任务名称 (选填，自动补齐) -->
        <a-form-item
          :label="taskText('tasks.taskName')"
          name="name"
          :tooltip="taskText('tasks.optionalUsesTheOfficialCompanyNameOrTarget')"
        >
          <a-input
            v-model:value="formState.name"
            :placeholder="taskText('tasks.optionalAStandardEnterpriseDiscoveryTaskNameWill')"
            allowClear
            @pressEnter="handleSubmit"
          />
        </a-form-item>

        <!-- 高级测绘参数（常驻平铺展示） -->
        <div style="background: var(--arl-bg-light); border: 1px solid var(--arl-border-color); border-radius: 6px; padding: 12px 14px; margin-top: 10px; margin-bottom: 12px;">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
            <span class="task-section-caption">{{ taskText('tasks.advancedDiscoverySettings') }}</span>
          </div>

          <a-row :gutter="16">
            <a-col :span="taskLocale !== 'zh-CN' ? 24 : 12">
              <a-form-item
                :label="taskText('tasks.investmentDepthLabel')"
                :label-col="{ style: { width: taskLocale !== 'zh-CN' ? '140px' : '80px' } }"
                :wrapper-col="{ style: { width: taskLocale !== 'zh-CN' ? 'calc(100% - 140px)' : 'calc(100% - 80px)' } }"
                style="margin-bottom: 8px;"
                :tooltip="taskText('tasks.recursiveDepthForSubsidiariesAndInvesteeCompanies1')"
              >
                <a-input-number
                  v-model:value="formState.depth"
                  :min="1"
                  :max="20"
                  size="small"
                  style="width: 100%;"
                  :addon-after="taskText('tasks.levels')"
                />
              </a-form-item>
            </a-col>
            <a-col :span="taskLocale !== 'zh-CN' ? 24 : 12">
              <a-form-item
                :label="taskText('tasks.minimumOwnershipLabel')"
                :label-col="{ style: { width: taskLocale !== 'zh-CN' ? '140px' : '80px' } }"
                :wrapper-col="{ style: { width: taskLocale !== 'zh-CN' ? 'calc(100% - 140px)' : 'calc(100% - 80px)' } }"
                style="margin-bottom: 8px;"
                :tooltip="taskText('tasks.minimumOwnershipShareForInvestments1100')"
              >
                <a-input-number
                  v-model:value="formState.invest_ratio"
                  :min="1"
                  :max="100"
                  size="small"
                  style="width: 100%;"
                  addon-after="%"
                />
              </a-form-item>
            </a-col>
          </a-row>

          <div class="arl-settings-row">
            <div class="settings-row-left">
              <div class="settings-row-title-wrap">
                <span class="settings-row-title">{{ taskText('tasks.icpCrossCheck') }}</span>
                <a-tooltip :title="taskText('tasks.crossCheckAgainstOfficialMiitIcpRecordsAnd')">
                  <question-circle-outlined class="settings-row-help" />
                </a-tooltip>
              </div>
              <div class="settings-row-subtitle">
                {{ taskText('tasks.crossCheckAgainstOfficialMiitIcpRecordsAnd') }}
              </div>
            </div>
            <div class="settings-row-right">
              <a-switch v-model:checked="formState.enable_icp" size="small" />
              <span class="settings-row-status">
                {{ formState.enable_icp ? taskText('tasks.enabledRecommended') : taskText('tasks.disabled') }}
              </span>
            </div>
          </div>

          <a-alert
            v-if="formState.depth > 1"
            type="warning"
            show-icon
            style="margin-top: 10px; margin-bottom: 4px; font-size: 12px; border-radius: 4px;"
            :message="taskText('tasks.investmentDepthHint', { depth: formState.depth })"
          />

          <a-form-item
            :label="taskText('tasks.assetCategories')"
            :label-col="{ style: { width: taskLocale !== 'zh-CN' ? '140px' : '80px' } }"
            :wrapper-col="{ style: { width: taskLocale !== 'zh-CN' ? 'calc(100% - 140px)' : 'calc(100% - 80px)' } }"
            style="margin-top: 12px; margin-bottom: 0;"
          >
            <a-checkbox-group v-model:value="formState.query_type" style="display: flex; flex-wrap: wrap; gap: 6px;">
              <a-checkbox value="invest">{{ taskText('tasks.investments') }}</a-checkbox>
              <a-checkbox value="web">{{ taskText('tasks.websiteIcpRecords') }}</a-checkbox>
              <a-checkbox value="app">{{ taskText('tasks.mobileApps') }}</a-checkbox>
              <a-checkbox value="mapp">{{ taskText('tasks.wechatMiniPrograms') }}</a-checkbox>
              <a-checkbox value="wechat">{{ taskText('tasks.wechatOfficialAccounts') }}</a-checkbox>
              <a-checkbox value="weibo">{{ taskText('tasks.corporateWeiboAccounts') }}</a-checkbox>
            </a-checkbox-group>
          </a-form-item>
        </div>
      </a-form>
    </a-spin>
  </a-modal>
</template>

<script setup>
import { useI18n } from 'vue-i18n';

import { ref, reactive, computed, watch } from 'vue';
import { useRouter } from 'vue-router';
import { Modal, message } from 'ant-design-vue';
import {
  LinkOutlined,
  BankOutlined,
  CheckCircleOutlined,
  SafetyCertificateOutlined,
  QuestionCircleOutlined
} from '@ant-design/icons-vue';
import request from '../utils/request';

const { t: taskText, locale: taskLocale } = useI18n({ useScope: 'global' });

const props = defineProps({
  open: {
    type: Boolean,
    default: false
  }
});

const emit = defineEmits(['update:open', 'success']);
const router = useRouter();

const formRef = ref();
const submitLoading = ref(false);
const configChecking = ref(false);
const tycConfigValid = ref(false);
const tycConfigured = ref(false);
const tycErrorType = ref('');
const tycErrorMsg = ref('');

const formState = reactive({
  name: '',
  rawTarget: '',
  depth: 1,
  invest_ratio: 50,
  query_type: ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo'],
  enable_icp: true
});

const rules = {
  rawTarget: [{ required: true, get message() { return taskText('tasks.enterATianyanchaUrlGidOrFullRegistered'); }, trigger: 'blur' }]
};

// 正则解析企业输入
const parseTargetInput = (input) => {
  if (!input) return { gid: '', isUrl: false, isName: false };
  const str = input.trim();
  const urlMatch = str.match(/(?:tianyancha\.com\/company\/|^company\/)([a-zA-Z0-9]+)/i);
  if (urlMatch && urlMatch[1]) {
    return { gid: urlMatch[1], isUrl: true, isName: false };
  }
  // 仅纯数字串视为 GID（天眼查 GID 为数字）；其余字母数字混排按企业名称处理，
  // 交由后端检索匹配，避免误把普通输入当成 GID。
  if (/^\d+$/.test(str)) {
    return { gid: str, isUrl: false, isName: false };
  }
  if (str.length >= 2) {
    return { gid: '', isUrl: false, isName: true };
  }
  return { gid: '', isUrl: false, isName: false };
};

const parsedGid = computed(() => {
  const parsed = parseTargetInput(formState.rawTarget);
  return parsed.gid;
});

const isCompanyName = computed(() => {
  const parsed = parseTargetInput(formState.rawTarget);
  return parsed.isName;
});

const checkTycConfig = async () => {
  configChecking.value = true;
  try {
    const res = await request.get('/icp/tyc_check');
    if (res.code === 200 && res.data) {
      tycConfigValid.value = !!res.data.valid;
      tycConfigured.value = !!res.data.configured;
      tycErrorType.value = res.data.error_type || '';
      tycErrorMsg.value = res.data.message || '';
    } else {
      tycConfigValid.value = false;
      tycConfigured.value = false;
      tycErrorType.value = '';
      tycErrorMsg.value = '';
    }
  } catch (error) {
    console.error('检测天眼查配置异常:', error);
    tycConfigValid.value = false;
    tycConfigured.value = false;
    tycErrorType.value = '';
    tycErrorMsg.value = '';
  } finally {
    configChecking.value = false;
  }
};

// 跳转系统设置前暂存输入，返回时恢复，避免用户已填写的目标被清空后需重新输入
let pendingDraft = null;

const goToApiConfig = () => {
  pendingDraft = { rawTarget: formState.rawTarget, name: formState.name };
  emit('update:open', false);
  // focus 参数让系统设置页直接定位并高亮天眼查凭据卡片
  router.push({ path: '/systemSettings', query: { tab: 'api_config', focus: 'tyc' } });
};

const goToProxyConfig = () => {
  pendingDraft = { rawTarget: formState.rawTarget, name: formState.name };
  emit('update:open', false);
  router.push({ path: '/systemSettings', query: { tab: 'system_general', focus: 'proxy' } });
};

watch(() => props.open, (val) => {
  if (val) {
    const draft = pendingDraft;
    pendingDraft = null;
    formState.name = draft ? draft.name : '';
    formState.rawTarget = draft ? draft.rawTarget : '';
    formState.depth = 1;
    formState.invest_ratio = 50;
    formState.query_type = ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo'];
    formState.enable_icp = true;
    checkTycConfig();
  }
});

const handleSubmit = async () => {
  try {
    await formRef.value.validate();
    const targetStr = (formState.rawTarget || '').trim();
    const customName = (formState.name || '').trim();
    const parsed = parseTargetInput(targetStr);

    if (!parsed.gid && !parsed.isName) {
      message.error(taskText('tasks.noValidTargetRecognizedEnterATianyanchaUrl'));
      return;
    }

    // 分流场景 1: 输入了天眼查 GID / 链接
    if (parsed.gid) {
      if (!tycConfigValid.value) {
        if (tycErrorType.value === 'banned_location') {
          Modal.confirm({
            title: taskText('tasks.tianyanchaLocationRestrictedTitle'),
            content: taskText('tasks.tianyanchaLocationRestrictedContent'),
            okText: taskText('tasks.configureSystemProxy'),
            cancelText: taskText('tasks.stayOnThisPage'),
            onOk() {
              goToProxyConfig();
            }
          });
          return;
        }
        if (tycConfigured.value && tycErrorMsg.value) {
          Modal.confirm({
            title: taskText('tasks.tianyanchaCredentialCheckFailedTitle'),
            content: tycErrorMsg.value,
            okText: taskText('tasks.configureCredentials'),
            cancelText: taskText('tasks.stayOnThisPage'),
            onOk() {
              goToApiConfig();
            }
          });
          return;
        }
        Modal.confirm({
          title: taskText('tasks.tianyanchaCommercialCredentialsAreNotConfigured'),
          content: taskText('tasks.investmentTraversalForATianyanchaGidRequiresCommercial'),
          okText: taskText('tasks.configureCredentials'),
          cancelText: taskText('tasks.stayOnThisPage'),
          onOk() {
            goToApiConfig();
          }
        });
        return;
      }

      submitLoading.value = true;
      const taskName = customName || ('TYC_' + parsed.gid);
      const payload = {
        name: taskName,
        gid: parsed.gid,
        depth: formState.depth || 1,
        invest_ratio: formState.invest_ratio || 50,
        enable_icp: formState.enable_icp !== false,
        query_type: formState.query_type
      };
      if (customName) {
        payload.company_name = customName;
      }
      const res = await request.post('/icp/tyc_task', payload);
      if (res.code === 200) {
        message.success(taskText('tasks.enterpriseDiscoveryTaskNameCreated', { name: taskName }));
        emit('update:open', false);
        emit('success', res);
      } else {
        message.error(res.message || taskText('tasks.failedToCreateTask'));
      }
      return;
    }

    // 分流场景 2: 输入了企业工商全称
    submitLoading.value = true;
    const taskName = customName || targetStr;
    const payload = {
      name: taskName,
      target: targetStr,
      depth: formState.depth || 1,
      invest_ratio: formState.invest_ratio || 50,
      enable_icp: formState.enable_icp !== false,
      query_type: formState.query_type
    };
    const res = await request.post('/icp/task', payload);
    if (res.code === 200) {
      const modeTip = res.data?.matched_tyc ? taskText('tasks.automaticallyIdentifiedAndUpgradedToCombinedDiscovery') : '';
      message.success(taskText('tasks.enterpriseDiscoveryTaskNameCreatedDetails', { name: taskName, details: modeTip }));
      emit('update:open', false);
      emit('success', res);
    } else {
      message.error(res.message || taskText('tasks.failedToCreateTask'));
    }

  } catch (error) {
    console.error('提交企业全景测绘任务失败', error);
  } finally {
    submitLoading.value = false;
  }
};
</script>

<style scoped>
/* 投资层级成本提示：层级越高，天眼查付费额度消耗越大 */
.depth-cost-hint {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--arl-warning-color, #faad14);
}

.task-settings-link { margin-left: 4px; }
.task-section-caption { font-weight: 500; font-size: 13px; }

/* 通栏设置项行 (ICP 双轨查重) */
.arl-settings-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--arl-bg-white, #ffffff);
  border: 1px solid var(--arl-border-color, #e8e8e8);
  border-radius: 6px;
  margin-top: 10px;
  transition: border-color 0.2s;
}

.arl-settings-row:hover {
  border-color: var(--arl-theme-color, #1890ff);
}

.settings-row-left {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
  padding-right: 16px;
  flex: 1;
}

.settings-row-title-wrap {
  display: flex;
  align-items: center;
  gap: 6px;
}

.settings-row-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--arl-text-color, #262626);
}

.settings-row-help {
  color: #bfbfbf;
  cursor: pointer;
  font-size: 13px;
  transition: color 0.2s;
}

.settings-row-help:hover {
  color: var(--arl-theme-color, #1890ff);
}

.settings-row-subtitle {
  font-size: 12px;
  color: var(--arl-text-color, #8c8c8c);
  opacity: 0.75;
  line-height: 1.4;
}

.settings-row-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.settings-row-status {
  font-size: 12px;
  color: var(--arl-text-color, #595959);
  opacity: 0.75;
  min-width: 72px;
  white-space: nowrap;
}
</style>
