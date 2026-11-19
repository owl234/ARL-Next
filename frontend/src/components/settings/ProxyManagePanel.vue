<template>
  <div class="proxy-panel-root" :class="{ 'page-wide-text': pageLocale !== 'zh-CN' }">
    <a-spin :spinning="initialLoading">
      <a-alert
        v-if="capabilitiesLoaded && !capabilities.pysocks_installed"
        type="warning"
        show-icon
        style="margin-bottom: 16px; border-radius: 8px;"
        :message="pageText('pages.proxyPysocksMissingWarning')"
      />

      <!-- 2. 代理节点池 -->
      <a-card size="small" class="proxy-section-card" data-setting-anchor="proxy">
        <template #title>
          <div class="card-header-flex">
            <div>
              <span class="section-title">{{ pageText('pages.proxyPoolTitle') }}</span>
              <span class="section-subtitle">{{ pageText('pages.proxyPoolSubtitle') }}</span>
            </div>
            <div class="card-header-actions">
              <a-dropdown-button
                size="small"
                :trigger="['click']"
                :loading="batchProbing"
                :disabled="!hasEnabledNodes"
                @click="handleBatchProbeNodes('egress_ip')"
              >
                <template #icon>
                  <DownOutlined />
                </template>
                {{ pageText('pages.proxyBatchProbeBtn') }}
                <template #overlay>
                  <a-menu @click="({ key }) => handleBatchProbeNodes(key)">
                    <a-menu-item v-for="preset in probePresetOptions" :key="preset.value">
                      {{ preset.label }}
                    </a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown-button>
              <a-button type="primary" size="small" @click="openNodeModal(null)">
                <template #icon><PlusOutlined /></template>
                {{ pageText('pages.proxyAddNodeBtn') }}
              </a-button>
            </div>
          </div>
        </template>

        <a-table
          :columns="nodeColumns"
          :data-source="config.nodes"
          :pagination="false"
          row-key="id"
          size="small"
          :scroll="{ x: 940 }"
        >
          <template #emptyText>
            <a-empty :description="pageText('pages.proxyNoNodesEmpty')" />
          </template>
          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'name'">
              <div class="node-name-cell">
                <div class="node-name-line">
                  <span class="node-name-text">{{ record.name }}</span>
                  <a-tag v-if="record.region_hint" color="cyan" style="margin: 0;">{{ record.region_hint }}</a-tag>
                  <a-tag v-if="record.has_password" color="default" style="margin: 0;">{{ pageText('pages.proxyAuthTag') }}</a-tag>
                </div>
                <div v-if="record.remark" class="node-remark-text">{{ record.remark }}</div>
              </div>
            </template>

            <template v-else-if="column.key === 'endpoint'">
              <div class="endpoint-cell">
                <a-tag :color="protocolTagColor(record.protocol)" style="margin: 0;">
                  {{ String(record.protocol || 'http').toUpperCase() }}
                </a-tag>
                <code class="endpoint-code">{{ record.display_url || `${record.protocol}://${record.host}:${record.port}` }}</code>
              </div>
            </template>

            <template v-else-if="column.key === 'enabled'">
              <a-switch
                :checked="!!record.enabled"
                size="small"
                :loading="togglingNodeId === record.id"
                @change="(val) => handleToggleNode(record, val)"
              />
            </template>

            <template v-else-if="column.key === 'last_probe'">
              <div v-if="record.last_probe" class="probe-result-cell">
                <div class="probe-tags">
                  <a-tag v-if="record.last_probe.preset" color="default" style="margin: 0;">
                    {{ probePresetShortLabel(record.last_probe.preset) }}
                  </a-tag>
                  <a-tag :color="record.last_probe.ok ? (record.last_probe.waf_blocked ? 'warning' : 'success') : 'error'" style="margin: 0;">
                    {{ record.last_probe.ok ? (record.last_probe.waf_blocked ? pageText('pages.proxyProbeWafBlocked') : pageText('pages.proxyProbeOk')) : pageText('pages.proxyProbeFail') }}
                  </a-tag>
                  <span v-if="record.last_probe.latency_ms != null" class="probe-metric">{{ record.last_probe.latency_ms }}ms</span>
                  <span v-if="record.last_probe.egress_ip" class="probe-ip">IP: {{ record.last_probe.egress_ip }}</span>
                </div>
                <div v-if="record.last_probe.detail" class="probe-detail" :title="record.last_probe.detail">
                  {{ record.last_probe.detail }}
                </div>
              </div>
              <span v-else class="probe-empty">{{ pageText('pages.proxyNotProbedYet') }}</span>
            </template>

            <template v-else-if="column.key === 'actions'">
              <a-space size="small">
                <a-dropdown-button
                  size="small"
                  :trigger="['click']"
                  :loading="probingNodeId === record.id"
                  @click="handleProbeExistingNode(record)"
                >
                  {{ pageText('pages.proxyProbeBtn') }}
                  <template #icon>
                    <DownOutlined />
                  </template>
                  <template #overlay>
                    <a-menu @click="({ key }) => handleProbeExistingNode(record, key)">
                      <a-menu-item v-for="preset in probePresetOptions" :key="preset.value">
                        {{ preset.label }}
                      </a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown-button>
                <a-button size="small" @click="openNodeModal(record)">
                  {{ pageText('pages.edit') }}
                </a-button>
                <a-popconfirm
                  :title="pageText('pages.proxyDeleteNodeConfirm', { name: record.name })"
                  :ok-text="pageText('pages.delete')"
                  :cancel-text="pageText('pages.cancel')"
                  ok-type="danger"
                  @confirm="handleDeleteNode(record)"
                >
                  <a-button size="small" danger :loading="deletingNodeId === record.id">
                    {{ pageText('pages.delete') }}
                  </a-button>
                </a-popconfirm>
              </a-space>
            </template>
          </template>
        </a-table>
      </a-card>

      <!-- 3. 三域流量分流策略与旁路规则 -->
      <a-card size="small" class="proxy-section-card" style="margin-top: 16px;">
        <template #title>
          <div class="card-header-flex">
            <div>
              <span class="section-title">{{ pageText('pages.proxyPoliciesTitle') }}</span>
              <span class="section-subtitle">{{ pageText('pages.proxyPoliciesSubtitle') }}</span>
            </div>
          </div>
        </template>

        <a-row :gutter="[16, 16]">
          <!-- 域 1: OSINT 企业测绘与备案 -->
          <a-col :xs="24" :lg="8">
            <div class="policy-domain-box" data-setting-anchor="osint">
              <div class="domain-header">
                <span class="domain-badge osint">OSINT</span>
                <span class="domain-title">{{ pageText('pages.proxyDomainOsintTitle') }}</span>
                <a-tag
                  v-if="showOsintHeaderStatus"
                  :color="osintStatusTagColor"
                  class="domain-status-tag"
                >
                  {{ osintStatusTagText }}
                </a-tag>
              </div>
              <p class="domain-desc">{{ pageText('pages.proxyDomainOsintDesc') }}</p>

              <a-form layout="vertical" size="small">
                <a-form-item :label="pageText('pages.proxyRoutingModeLabel')">
                  <a-select v-model:value="policyForm.osint.mode" :options="modeOptions" />
                </a-form-item>

                <a-form-item :label="pageText('pages.proxyBoundNodesLabel')">
                  <a-select
                    v-model:value="policyForm.osint.node_ids"
                    mode="multiple"
                    :disabled="policyForm.osint.mode === 'direct_only'"
                    :placeholder="pageText('pages.proxySelectBoundNodesPlaceholder')"
                    :options="nodeSelectOptions"
                    allow-clear
                  />
                </a-form-item>

                <a-form-item
                  v-if="policyForm.osint.mode === 'failover' || policyForm.osint.mode === 'round_robin'"
                  :label="pageText('pages.proxyIncludeDirectLabel')"
                >
                  <div class="switch-inline">
                    <a-switch v-model:checked="policyForm.osint.include_direct" size="small" />
                    <span class="switch-hint">{{ pageText('pages.proxyIncludeDirectHint') }}</span>
                  </div>
                </a-form-item>

                <a-form-item :label="pageText('pages.proxyOsintCooldownLabel')">
                  <a-input-number
                    v-model:value="policyForm.osint.cooldown_sec"
                    :min="30"
                    :max="3600"
                    :step="30"
                    style="width: 100%;"
                    addon-after="s"
                  />
                </a-form-item>
              </a-form>

              <div
                v-if="showOsintCooldownAlert"
                class="osint-cooldown-box"
                :class="osintCooldownBoxClass"
              >
                <div class="osint-cooldown-header">
                  <span class="osint-cooldown-title">
                    <span class="osint-status-dot" :class="osintCooldownBoxClass"></span>
                    {{ pageText('pages.proxyBlockedExitsLabel') }}
                  </span>
                  <a-button
                    size="small"
                    :loading="resetLoading"
                    :disabled="blockedExitsList.length === 0 && displayCooldownSec <= 0"
                    @click="handleResetCooldown"
                  >
                    {{ pageText('pages.proxyResetCooldownBtn') }}
                  </a-button>
                </div>

                <div v-if="blockedExitsList.length > 0" class="osint-blocked-list">
                  <div
                    v-for="item in blockedExitsList"
                    :key="item.exit_id"
                    class="osint-blocked-item"
                  >
                    <a-tag color="warning" style="margin: 0; flex-shrink: 0;">
                      {{ item.label || item.exit_id }} · {{ item.remaining_sec }}s
                    </a-tag>
                    <span v-if="item.reason || item.ip" class="osint-blocked-reason" :title="item.reason">
                      {{ item.reason }}<template v-if="item.ip"> ({{ item.ip }})</template>
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </a-col>

          <!-- 域 2: 主动扫描与测绘 (scan) -->
          <a-col :xs="24" :lg="8">
            <div class="policy-domain-box" data-setting-anchor="scan">
              <div class="domain-header">
                <span class="domain-badge scan">SCAN</span>
                <span class="domain-title">{{ pageText('pages.proxyDomainScanTitle') }}</span>
              </div>
              <p class="domain-desc">{{ pageText('pages.proxyDomainScanDesc') }}</p>

              <a-form layout="vertical" size="small">
                <a-form-item :label="pageText('pages.proxyRoutingModeLabel')">
                  <a-select v-model:value="policyForm.scan.mode" :options="modeOptions" />
                </a-form-item>

                <a-form-item :label="pageText('pages.proxyBoundNodesLabel')">
                  <a-select
                    v-model:value="policyForm.scan.node_ids"
                    mode="multiple"
                    :disabled="policyForm.scan.mode === 'direct_only'"
                    :placeholder="pageText('pages.proxySelectBoundNodesPlaceholder')"
                    :options="nodeSelectOptions"
                    allow-clear
                  />
                </a-form-item>

                <a-form-item
                  v-if="policyForm.scan.mode === 'failover' || policyForm.scan.mode === 'round_robin'"
                  :label="pageText('pages.proxyIncludeDirectLabel')"
                >
                  <div class="switch-inline">
                    <a-switch v-model:checked="policyForm.scan.include_direct" size="small" />
                    <span class="switch-hint">{{ pageText('pages.proxyIncludeDirectHint') }}</span>
                  </div>
                </a-form-item>

                <a-form-item :label="pageText('pages.proxyScanEnginesLabel')">
                  <div class="engine-switch-list">
                    <label class="engine-switch-row">
                      <a-switch v-model:checked="policyForm.scan.apply_to_nuclei" size="small" />
                      <span>Nuclei (-proxy)</span>
                    </label>
                    <label class="engine-switch-row">
                      <a-switch v-model:checked="policyForm.scan.apply_to_npoc" size="small" />
                      <span>NPoC (HTTP/SOCKS)</span>
                    </label>
                    <label class="engine-switch-row">
                      <a-switch v-model:checked="policyForm.scan.apply_to_puppeteer" size="small" />
                      <span>Puppeteer / Chromium</span>
                    </label>
                  </div>
                </a-form-item>

                <a-alert
                  v-if="showPuppeteerAuthWarning"
                  type="warning"
                  show-icon
                  style="margin-top: 4px;"
                  :message="pageText('pages.proxyPuppeteerAuthWarning')"
                />
              </a-form>
            </div>
          </a-col>

          <!-- 域 3: 开源情报与海外通知 (intel) -->
          <a-col :xs="24" :lg="8">
            <div class="policy-domain-box" data-setting-anchor="intel">
              <div class="domain-header">
                <span class="domain-badge intel">INTEL</span>
                <span class="domain-title">{{ pageText('pages.proxyDomainIntelTitle') }}</span>
              </div>
              <p class="domain-desc">{{ pageText('pages.proxyDomainIntelDesc') }}</p>

              <a-form layout="vertical" size="small">
                <a-form-item :label="pageText('pages.proxyRoutingModeLabel')">
                  <a-select v-model:value="policyForm.intel.mode" :options="modeOptions" />
                </a-form-item>

                <a-form-item :label="pageText('pages.proxyBoundNodesLabel')">
                  <a-select
                    v-model:value="policyForm.intel.node_ids"
                    mode="multiple"
                    :disabled="policyForm.intel.mode === 'direct_only'"
                    :placeholder="pageText('pages.proxySelectBoundNodesPlaceholder')"
                    :options="nodeSelectOptions"
                    allow-clear
                  />
                </a-form-item>

                <a-form-item
                  v-if="policyForm.intel.mode === 'failover' || policyForm.intel.mode === 'round_robin'"
                  :label="pageText('pages.proxyIncludeDirectLabel')"
                >
                  <div class="switch-inline">
                    <a-switch v-model:checked="policyForm.intel.include_direct" size="small" />
                    <span class="switch-hint">{{ pageText('pages.proxyIncludeDirectHint') }}</span>
                  </div>
                </a-form-item>
              </a-form>
            </div>
          </a-col>
        </a-row>

        <!-- 旁路直连白名单 -->
        <div class="bypass-section" data-setting-anchor="bypass">
          <div class="bypass-header">{{ pageText('pages.proxyBypassTitle') }}</div>
          <a-row :gutter="[16, 12]">
            <a-col :xs="24" :md="12">
              <div class="bypass-switches">
                <label class="bypass-switch-item">
                  <a-switch v-model:checked="bypassForm.bypass_private_cidr" size="small" />
                  <div>
                    <div class="bypass-item-title">{{ pageText('pages.proxyBypassPrivateCidrLabel') }}</div>
                    <div class="bypass-item-desc">{{ pageText('pages.proxyBypassPrivateCidrDesc') }}</div>
                  </div>
                </label>
                <label class="bypass-switch-item">
                  <a-switch v-model:checked="bypassForm.bypass_domestic_webhooks" size="small" />
                  <div>
                    <div class="bypass-item-title">{{ pageText('pages.proxyBypassDomesticWebhooksLabel') }}</div>
                    <div class="bypass-item-desc">{{ pageText('pages.proxyBypassDomesticWebhooksDesc') }}</div>
                  </div>
                </label>
              </div>
            </a-col>
            <a-col :xs="24" :md="12">
              <div class="bypass-item-title" style="margin-bottom: 6px;">{{ pageText('pages.proxyCustomNoProxyLabel') }}</div>
              <a-textarea
                v-model:value="customNoProxyText"
                :rows="3"
                :placeholder="pageText('pages.proxyCustomNoProxyPlaceholder')"
              />
            </a-col>
          </a-row>
        </div>
      </a-card>
    </a-spin>

    <!-- 新增/编辑代理节点弹窗 -->
    <a-modal
      v-model:open="nodeModalOpen"
      :title="editingNodeId ? pageText('pages.proxyEditNodeTitle') : pageText('pages.proxyAddNodeTitle')"
      width="560px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      :maskClosable="false"
    >
      <a-form layout="vertical" size="small">
        <div class="quick-uri-box">
          <div class="quick-uri-label">{{ pageText('pages.proxyQuickUriLabel') }}</div>
          <div class="quick-uri-row">
            <a-input
              v-model:value="quickUriText"
              :placeholder="pageText('pages.proxyQuickUriPlaceholder')"
              allow-clear
              @pressEnter="handleParseQuickUri"
            />
            <a-button @click="handleParseQuickUri">{{ pageText('pages.proxyParseUriBtn') }}</a-button>
          </div>
        </div>

        <a-row :gutter="12">
          <a-col :span="14">
            <a-form-item :label="pageText('pages.proxyNodeNameLabel')" required>
              <a-input v-model:value="nodeForm.name" :placeholder="pageText('pages.proxyNodeNamePlaceholder')" />
            </a-form-item>
          </a-col>
          <a-col :span="10">
            <a-form-item :label="pageText('pages.proxyNodeRegionLabel')">
              <a-input v-model:value="nodeForm.region_hint" :placeholder="pageText('pages.proxyNodeRegionPlaceholder')" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="12">
          <a-col :span="8">
            <a-form-item :label="pageText('pages.proxyProtocolLabel')" required>
              <a-select v-model:value="nodeForm.protocol" :options="protocolOptions" />
            </a-form-item>
          </a-col>
          <a-col :span="10">
            <a-form-item :label="pageText('pages.proxyHostLabel')" required>
              <a-input v-model:value="nodeForm.host" placeholder="192.0.2.10" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item :label="pageText('pages.proxyPortLabel')" required>
              <a-input-number v-model:value="nodeForm.port" :min="1" :max="65535" style="width: 100%;" />
            </a-form-item>
          </a-col>
        </a-row>

        <a-row :gutter="12">
          <a-col :span="12">
            <a-form-item :label="pageText('pages.proxyUsernameLabel')">
              <a-input v-model:value="nodeForm.username" :placeholder="pageText('pages.optionalLabel')" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="pageText('pages.proxyPasswordLabel')">
              <a-input-password
                v-model:value="nodeForm.password"
                :disabled="nodeForm.clear_password"
                :placeholder="editingHasPassword ? pageText('pages.proxyPasswordKeepPlaceholder') : pageText('pages.optionalLabel')"
              />
            </a-form-item>
          </a-col>
        </a-row>

        <div v-if="editingNodeId && editingHasPassword" style="margin-bottom: 10px;">
          <a-checkbox v-model:checked="nodeForm.clear_password">
            {{ pageText('pages.proxyClearPasswordLabel') }}
          </a-checkbox>
        </div>

        <a-row :gutter="12" align="middle">
          <a-col :span="18">
            <a-form-item :label="pageText('pages.proxyRemarkLabel')" style="margin-bottom: 8px;">
              <a-input v-model:value="nodeForm.remark" :placeholder="pageText('pages.optionalLabel')" />
            </a-form-item>
          </a-col>
          <a-col :span="6">
            <a-form-item :label="pageText('pages.status')" style="margin-bottom: 8px;">
              <a-switch v-model:checked="nodeForm.enabled" />
            </a-form-item>
          </a-col>
        </a-row>

        <div class="modal-probe-box">
          <div class="modal-probe-bar">
            <a-select
              v-model:value="modalProbePreset"
              size="small"
              style="flex: 1;"
              :options="probePresetOptions"
            />
            <a-button size="small" :loading="modalProbeLoading" @click="handleProbeDraft">
              {{ pageText('pages.proxyProbeDraftBtn') }}
            </a-button>
          </div>
          <a-alert
            v-if="modalProbeResult"
            :type="modalProbeResult.ok ? (modalProbeResult.waf_blocked ? 'warning' : 'success') : 'error'"
            show-icon
            style="margin-top: 8px;"
            :message="modalProbeSummaryText"
            :description="modalProbeResult.detail || ''"
          />
        </div>
      </a-form>

      <template #footer>
        <a-button @click="nodeModalOpen = false">{{ pageText('pages.cancel') }}</a-button>
        <a-button type="primary" :loading="nodeSaving" @click="handleSubmitNode">
          {{ pageText('pages.proxySaveNodeBtn') }}
        </a-button>
      </template>
    </a-modal>
  </div>
</template>

<script setup>
import { computed, nextTick, onActivated, onDeactivated, onMounted, onUnmounted, reactive, ref } from 'vue';
import { useI18n } from 'vue-i18n';
import { message } from 'ant-design-vue';
import { DownOutlined, PlusOutlined } from '@ant-design/icons-vue';
import request from '@/utils/request';
import { formatProxyEgressLabel, formatProxyLevelClass, formatProxyTagColor } from '@/constants/proxyStatus';
import { parseProxyUri } from '@/utils/settingsHelpers';

const { t: pageText, locale: pageLocale } = useI18n({ useScope: 'global' });

const initialLoading = ref(true);
const refreshLoading = ref(false);
const resetLoading = ref(false);
const policySaving = ref(false);
const togglingNodeId = ref('');
const probingNodeId = ref('');
const batchProbing = ref(false);
const deletingNodeId = ref('');
const quickUriText = ref('');

const capabilitiesLoaded = ref(false);
const capabilities = reactive({
  pysocks_installed: true,
  protocols: ['http', 'https', 'socks5', 'socks5h'],
  presets: [],
});

const config = reactive({
  nodes: [],
  policies: {
    osint: { mode: 'direct_only', node_ids: [], include_direct: false, cooldown_sec: 300 },
    scan: { mode: 'direct_only', node_ids: [], include_direct: false, apply_to_nuclei: true, apply_to_npoc: true, apply_to_puppeteer: false },
    intel: { mode: 'direct_only', node_ids: [], include_direct: false },
  },
  bypass: {
    bypass_private_cidr: true,
    bypass_domestic_webhooks: true,
    custom_no_proxy: [],
  },
});

const runtime = reactive({
  domain: 'osint',
  mode: 'direct_only',
  state: 'direct_ok',
  active_exit_id: '__direct__',
  active_node_name: '',
  cooldown_remaining_sec: 0,
  blocked_exits: [],
  puppeteer_compat_warning: false,
});

const policyForm = reactive({
  osint: { mode: 'direct_only', node_ids: [], include_direct: false, cooldown_sec: 300 },
  scan: { mode: 'direct_only', node_ids: [], include_direct: false, apply_to_nuclei: true, apply_to_npoc: true, apply_to_puppeteer: false },
  intel: { mode: 'direct_only', node_ids: [], include_direct: false },
});

const bypassForm = reactive({
  bypass_private_cidr: true,
  bypass_domestic_webhooks: true,
});
const customNoProxyText = ref('');
const baselineSnapshot = ref('');

const cooldownTickOffset = ref(0);
let tickTimer = null;

const nodeModalOpen = ref(false);
const nodeSaving = ref(false);
const editingNodeId = ref('');
const editingHasPassword = ref(false);
const modalProbePreset = ref('egress_ip');
const modalProbeLoading = ref(false);
const modalProbeResult = ref(null);

const nodeForm = reactive({
  name: '',
  protocol: 'socks5h',
  host: '',
  port: 1080,
  username: '',
  password: '',
  clear_password: false,
  region_hint: '',
  remark: '',
  enabled: true,
});

const parseNoProxyList = (text) => {
  const parts = String(text || '').split(/[\s,;]+/).map((s) => s.trim().toLowerCase()).filter(Boolean);
  return Array.from(new Set(parts));
};

const currentPolicySnapshot = () => JSON.stringify({
  policies: {
    osint: {
      mode: policyForm.osint.mode,
      node_ids: [...(policyForm.osint.node_ids || [])],
      include_direct: !!policyForm.osint.include_direct,
      cooldown_sec: Number(policyForm.osint.cooldown_sec || 300),
    },
    scan: {
      mode: policyForm.scan.mode,
      node_ids: [...(policyForm.scan.node_ids || [])],
      include_direct: !!policyForm.scan.include_direct,
      apply_to_nuclei: !!policyForm.scan.apply_to_nuclei,
      apply_to_npoc: !!policyForm.scan.apply_to_npoc,
      apply_to_puppeteer: !!policyForm.scan.apply_to_puppeteer,
    },
    intel: {
      mode: policyForm.intel.mode,
      node_ids: [...(policyForm.intel.node_ids || [])],
      include_direct: !!policyForm.intel.include_direct,
    },
  },
  bypass: {
    bypass_private_cidr: !!bypassForm.bypass_private_cidr,
    bypass_domestic_webhooks: !!bypassForm.bypass_domestic_webhooks,
    custom_no_proxy: parseNoProxyList(customNoProxyText.value),
  },
});

const isPolicyDirty = computed(() => {
  if (!baselineSnapshot.value) return false;
  return currentPolicySnapshot() !== baselineSnapshot.value;
});

const hasUnsavedChanges = () => isPolicyDirty.value;

const protocolOptions = computed(() => ([
  { value: 'socks5h', label: pageText('pages.proxyProtoSocks5hLabel') },
  { value: 'socks5', label: pageText('pages.proxyProtoSocks5Label') },
  { value: 'http', label: 'HTTP' },
  { value: 'https', label: 'HTTPS' },
]));

const modeOptions = computed(() => ([
  { value: 'direct_only', label: pageText('pages.proxyModeDirectOnly') },
  { value: 'failover', label: pageText('pages.proxyModeFailover') },
  { value: 'round_robin', label: pageText('pages.proxyModeRoundRobin') },
  { value: 'fixed_proxy', label: pageText('pages.proxyModeFixedProxy') },
]));

const nodeSelectOptions = computed(() => (config.nodes || []).map((n) => ({
  value: n.id,
  label: `${n.name} (${String(n.protocol || '').toUpperCase()} · ${n.host}:${n.port})${n.enabled ? '' : ` [${pageText('pages.disabledLabel')}]`}`,
})));

const PROBE_PRESET_I18N_MAP = {
  egress_ip: { labelKey: 'pages.proxyPresetEgressIp', shortKey: 'pages.proxyPresetEgressIpShort' },
  miit: { labelKey: 'pages.proxyPresetMiit', shortKey: 'pages.proxyPresetMiitShort' },
  tianyancha: { labelKey: 'pages.proxyPresetTianyancha', shortKey: 'pages.proxyPresetTianyanchaShort' },
  github: { labelKey: 'pages.proxyPresetGithub', shortKey: 'pages.proxyPresetGithubShort' },
};

const probePresetShortLabel = (preset) => {
  const entry = PROBE_PRESET_I18N_MAP[preset];
  return entry ? pageText(entry.shortKey) : String(preset || '');
};

const probePresetOptions = computed(() => {
  const backendPresets = capabilities.presets && capabilities.presets.length > 0
    ? capabilities.presets
    : Object.keys(PROBE_PRESET_I18N_MAP).map((key) => ({ key, label: '' }));
  return backendPresets.map((p) => {
    const entry = PROBE_PRESET_I18N_MAP[p.key];
    return {
      value: p.key,
      label: entry ? pageText(entry.labelKey) : p.label,
    };
  });
});

const nodeColumns = computed(() => ([
  { title: pageText('pages.proxyColName'), key: 'name', width: 200 },
  { title: pageText('pages.proxyColEndpoint'), key: 'endpoint', width: 250 },
  { title: pageText('pages.status'), key: 'enabled', width: 90, align: 'center' },
  { title: pageText('pages.proxyColProbe'), key: 'last_probe', width: 260 },
  { title: pageText('pages.action'), key: 'actions', width: 240, align: 'right' },
]));

const blockedExitsList = computed(() => (runtime.blocked_exits || [])
  .map((item) => ({
    ...item,
    remaining_sec: Math.max(0, Number(item.remaining_sec || 0) - cooldownTickOffset.value),
  }))
  .filter((item) => item.remaining_sec > 0));

const displayCooldownSec = computed(() => {
  const raw = Number(runtime.cooldown_remaining_sec || 0);
  if (raw <= 0) return 0;
  return Math.max(0, raw - cooldownTickOffset.value);
});

const showOsintHeaderStatus = computed(() => (
  runtime.state !== 'direct_ok'
  || blockedExitsList.value.length > 0
  || displayCooldownSec.value > 0
));

const showOsintCooldownAlert = computed(() => (
  blockedExitsList.value.length > 0
  || displayCooldownSec.value > 0
  || runtime.state === 'degraded_blocked'
));

const osintCooldownBoxClass = computed(() => formatProxyLevelClass(runtime.state));

const osintStatusTagColor = computed(() => formatProxyTagColor(runtime.state));

const osintStatusTagText = computed(() => formatProxyEgressLabel(runtime, {
  cooldownSecOverride: displayCooldownSec.value,
}));

const showPuppeteerAuthWarning = computed(() => {
  if (runtime.puppeteer_compat_warning) return true;
  if (!policyForm.scan.apply_to_puppeteer || policyForm.scan.mode === 'direct_only') return false;
  const boundSet = new Set(policyForm.scan.node_ids || []);
  return (config.nodes || []).some((n) => (
    n.enabled
    && (boundSet.size === 0 || boundSet.has(n.id))
    && (!!n.username || !!n.has_password)
  ));
});

const modalProbeSummaryText = computed(() => {
  if (!modalProbeResult.value) return '';
  const r = modalProbeResult.value;
  const parts = [];
  parts.push(r.ok ? (r.waf_blocked ? pageText('pages.proxyProbeWafBlocked') : pageText('pages.proxyProbeOk')) : pageText('pages.proxyProbeFail'));
  if (r.status_code) parts.push(`HTTP ${r.status_code}`);
  if (r.latency_ms != null) parts.push(`${r.latency_ms}ms`);
  if (r.egress_ip) parts.push(`IP: ${r.egress_ip}`);
  return parts.join(' · ');
});

const protocolTagColor = (proto) => {
  const p = String(proto || '').toLowerCase();
  if (p.startsWith('socks')) return 'purple';
  if (p === 'https') return 'cyan';
  return 'blue';
};

const syncPolicyFormFromConfig = (cfg, { resetDirty = false } = {}) => {
  const pol = cfg?.policies || {};
  const by = cfg?.bypass || {};

  if (resetDirty || !isPolicyDirty.value) {
    Object.assign(policyForm.osint, {
      mode: pol.osint?.mode || 'direct_only',
      node_ids: [...(pol.osint?.node_ids || [])],
      include_direct: !!pol.osint?.include_direct,
      cooldown_sec: Number(pol.osint?.cooldown_sec || 300),
    });
    Object.assign(policyForm.scan, {
      mode: pol.scan?.mode || 'direct_only',
      node_ids: [...(pol.scan?.node_ids || [])],
      include_direct: !!pol.scan?.include_direct,
      apply_to_nuclei: pol.scan?.apply_to_nuclei !== false,
      apply_to_npoc: pol.scan?.apply_to_npoc !== false,
      apply_to_puppeteer: !!pol.scan?.apply_to_puppeteer,
    });
    Object.assign(policyForm.intel, {
      mode: pol.intel?.mode || 'direct_only',
      node_ids: [...(pol.intel?.node_ids || [])],
      include_direct: !!pol.intel?.include_direct,
    });
    bypassForm.bypass_private_cidr = by.bypass_private_cidr !== false;
    bypassForm.bypass_domestic_webhooks = by.bypass_domestic_webhooks !== false;
    customNoProxyText.value = (by.custom_no_proxy || []).join('\n');
    baselineSnapshot.value = currentPolicySnapshot();
  } else {
    // 即使策略区存在未保存修改，仍应清理已从节点池中删除的无效 node_id 引用
    const validIds = new Set((cfg?.nodes || []).map((n) => n.id));
    policyForm.osint.node_ids = (policyForm.osint.node_ids || []).filter((id) => validIds.has(id));
    policyForm.scan.node_ids = (policyForm.scan.node_ids || []).filter((id) => validIds.has(id));
    policyForm.intel.node_ids = (policyForm.intel.node_ids || []).filter((id) => validIds.has(id));
  }
};

const applyServerPayload = (data, options = {}) => {
  if (!data) return;
  if (data.config) {
    config.nodes = Array.isArray(data.config.nodes) ? data.config.nodes : [];
    if (data.config.policies) config.policies = data.config.policies;
    if (data.config.bypass) config.bypass = data.config.bypass;
    syncPolicyFormFromConfig(data.config, options);
  }
  if (data.runtime) {
    Object.assign(runtime, data.runtime);
    cooldownTickOffset.value = 0;
  }
  if (data.capabilities) {
    capabilities.pysocks_installed = data.capabilities.pysocks_installed !== false;
    capabilities.protocols = data.capabilities.protocols || capabilities.protocols;
    capabilities.presets = data.capabilities.presets || [];
    capabilitiesLoaded.value = true;
  }
};

const fetchProxyConfig = async (showInitialSpin = true) => {
  if (showInitialSpin) initialLoading.value = true;
  else refreshLoading.value = true;
  try {
    const res = await request.get('/api/system_config/proxy');
    if (res.code === 200 && res.data) {
      applyServerPayload(res.data, { resetDirty: showInitialSpin });
    } else if (res.message) {
      message.error(res.message);
    }
  } catch (err) {
    const msg = err?.response?.data?.message;
    if (msg) message.error(msg);
  } finally {
    initialLoading.value = false;
    refreshLoading.value = false;
  }
};

const hasEnabledNodes = computed(() => (config.nodes || []).some((n) => !!n.enabled));

const openNodeModal = (node) => {
  modalProbeResult.value = null;
  quickUriText.value = '';
  if (node) {
    editingNodeId.value = node.id;
    editingHasPassword.value = !!node.has_password;
    Object.assign(nodeForm, {
      name: node.name || '',
      protocol: node.protocol || 'socks5h',
      host: node.host || '',
      port: Number(node.port || 1080),
      username: node.username || '',
      password: '',
      clear_password: false,
      region_hint: node.region_hint || '',
      remark: node.remark || '',
      enabled: !!node.enabled,
    });
  } else {
    editingNodeId.value = '';
    editingHasPassword.value = false;
    Object.assign(nodeForm, {
      name: '',
      protocol: 'socks5h',
      host: '',
      port: 1080,
      username: '',
      password: '',
      clear_password: false,
      region_hint: '',
      remark: '',
      enabled: true,
    });
  }
  nodeModalOpen.value = true;
};

const validateNodeDraft = () => {
  const name = String(nodeForm.name || '').trim();
  const host = String(nodeForm.host || '').trim();
  const port = Number(nodeForm.port);
  if (!name) {
    message.warning(pageText('pages.proxyNameRequiredWarn'));
    return false;
  }
  if (!host) {
    message.warning(pageText('pages.proxyHostRequiredWarn'));
    return false;
  }
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    message.warning(pageText('pages.proxyPortInvalidWarn'));
    return false;
  }
  return true;
};

const buildNodeRequestPayload = () => {
  const payload = {
    name: String(nodeForm.name || '').trim(),
    protocol: nodeForm.protocol,
    host: String(nodeForm.host || '').trim(),
    port: Number(nodeForm.port),
    username: String(nodeForm.username || '').trim(),
    region_hint: String(nodeForm.region_hint || '').trim(),
    remark: String(nodeForm.remark || '').trim(),
    enabled: !!nodeForm.enabled,
  };
  if (nodeForm.clear_password) {
    payload.clear_password = true;
  } else if (nodeForm.password) {
    payload.password = nodeForm.password;
  }
  return payload;
};

const handleSubmitNode = async () => {
  if (!validateNodeDraft()) return;
  nodeSaving.value = true;
  try {
    const payload = buildNodeRequestPayload();
    const res = editingNodeId.value
      ? await request.put(`/api/system_config/proxy/nodes/${encodeURIComponent(editingNodeId.value)}`, payload)
      : await request.post('/api/system_config/proxy/nodes', payload);
    if (res.code === 200 && res.data) {
      applyServerPayload(res.data);
      nodeModalOpen.value = false;
      message.success(res.message || pageText('pages.saveSuccess'));
    } else if (res.message) {
      message.error(res.message);
    }
  } catch (err) {
    const msg = err?.response?.data?.message;
    if (msg) message.error(msg);
  } finally {
    nodeSaving.value = false;
  }
};

const handleToggleNode = async (record, checked) => {
  togglingNodeId.value = record.id;
  try {
    const res = await request.put(`/api/system_config/proxy/nodes/${encodeURIComponent(record.id)}`, {
      name: record.name,
      protocol: record.protocol,
      host: record.host,
      port: Number(record.port),
      username: record.username || '',
      region_hint: record.region_hint || '',
      remark: record.remark || '',
      enabled: !!checked,
    });
    if (res.code === 200 && res.data) {
      applyServerPayload(res.data);
      message.success(pageText('pages.operationSuccess'));
    } else if (res.message) {
      message.error(res.message);
    }
  } catch (err) {
    const msg = err?.response?.data?.message;
    if (msg) message.error(msg);
  } finally {
    togglingNodeId.value = '';
  }
};

const handleDeleteNode = async (record) => {
  deletingNodeId.value = record.id;
  try {
    const res = await request.delete(`/api/system_config/proxy/nodes/${encodeURIComponent(record.id)}`);
    if (res.code === 200 && res.data) {
      applyServerPayload(res.data);
      message.success(pageText('pages.deleteSuccess'));
    } else if (res.message) {
      message.error(res.message);
    }
  } catch (err) {
    const msg = err?.response?.data?.message;
    if (msg) message.error(msg);
  } finally {
    deletingNodeId.value = '';
  }
};

const handleProbeExistingNode = async (record, preset = 'egress_ip') => {
  probingNodeId.value = record.id;
  try {
    const res = await request.post('/api/system_config/proxy/probe', {
      node_id: record.id,
      preset: preset || 'egress_ip',
      save_result: true,
    });
    if (res.code === 200 && res.data) {
      applyServerPayload(res.data);
      const r = res.data.result || {};
      if (r.ok && !r.waf_blocked) {
        message.success(`${record.name}: ${r.latency_ms || 0}ms${r.egress_ip ? ` (${r.egress_ip})` : ''}`);
      } else if (r.ok && r.waf_blocked) {
        message.warning(`${record.name}: ${r.detail || pageText('pages.proxyProbeWafBlocked')}`);
      } else {
        message.error(`${record.name}: ${r.detail || pageText('pages.proxyProbeFail')}`);
      }
    }
  } catch (err) {
    const msg = err?.response?.data?.message;
    if (msg) message.error(msg);
  } finally {
    probingNodeId.value = '';
  }
};

const handleParseQuickUri = () => {
  const parsed = parseProxyUri(quickUriText.value);
  if (!parsed.ok) {
    message.warning(pageText('pages.proxyUriInvalidWarn'));
    return;
  }
  nodeForm.protocol = parsed.protocol;
  nodeForm.host = parsed.host;
  nodeForm.port = parsed.port;
  nodeForm.username = parsed.username || '';
  if (parsed.password) {
    nodeForm.password = parsed.password;
    nodeForm.clear_password = false;
  }
  if (!String(nodeForm.name || '').trim()) {
    nodeForm.name = `${parsed.protocol.toUpperCase()}-${parsed.host}`;
  }
  message.success(pageText('pages.proxyUriParsedSuccess'));
};

const handleBatchProbeNodes = async (preset = 'egress_ip') => {
  const targets = (config.nodes || []).filter((n) => !!n.enabled);
  if (targets.length === 0) {
    message.warning(pageText('pages.proxyBatchProbeNoEnabled'));
    return;
  }
  batchProbing.value = true;
  let okCount = 0;
  let failCount = 0;
  try {
    for (const node of targets) {
      probingNodeId.value = node.id;
      try {
        const res = await request.post('/api/system_config/proxy/probe', {
          node_id: node.id,
          preset: preset || 'egress_ip',
          save_result: true,
        });
        if (res.code === 200 && res.data) {
          applyServerPayload(res.data);
          const r = res.data.result || {};
          if (r.ok && !r.waf_blocked) okCount += 1;
          else failCount += 1;
        } else {
          failCount += 1;
        }
      } catch {
        failCount += 1;
      }
    }
    const text = pageText('pages.proxyBatchProbeDone', { ok: okCount, fail: failCount });
    if (failCount === 0) message.success(text);
    else message.warning(text);
  } finally {
    probingNodeId.value = '';
    batchProbing.value = false;
  }
};

const handleProbeDraft = async () => {
  if (!validateNodeDraft()) return;
  modalProbeLoading.value = true;
  modalProbeResult.value = null;
  try {
    const res = await request.post('/api/system_config/proxy/probe', {
      node_id: editingNodeId.value || undefined,
      draft: buildNodeRequestPayload(),
      preset: modalProbePreset.value,
      save_result: false,
    });
    if (res.code === 200 && res.data) {
      modalProbeResult.value = res.data.result || null;
    }
  } catch (err) {
    const msg = err?.response?.data?.message;
    if (msg) message.error(msg);
  } finally {
    modalProbeLoading.value = false;
  }
};

const resetPolicyEdits = ({ silent = false } = {}) => {
  syncPolicyFormFromConfig(config, { resetDirty: true });
  if (!silent) {
    message.info(pageText('pages.sectionChangesReset'));
  }
};

const handleSavePolicies = async ({ silentSuccess = false } = {}) => {
  for (const dom of ['osint', 'scan', 'intel']) {
    if (policyForm[dom].mode === 'fixed_proxy' && (!policyForm[dom].node_ids || policyForm[dom].node_ids.length === 0)) {
      message.warning(pageText('pages.proxyFixedModeRequiresNodeWarn', { domain: dom.toUpperCase() }));
      return false;
    }
  }
  policySaving.value = true;
  try {
    const payload = JSON.parse(currentPolicySnapshot());
    const res = await request.put('/api/system_config/proxy/policies', payload);
    if (res.code === 200 && res.data) {
      applyServerPayload(res.data, { resetDirty: true });
      if (!silentSuccess) {
        message.success(res.message || pageText('pages.saveSuccess'));
      }
      return true;
    } else if (res.message) {
      message.error(res.message);
    }
    return false;
  } catch (err) {
    const msg = err?.response?.data?.message;
    if (msg) message.error(msg);
    return false;
  } finally {
    policySaving.value = false;
  }
};

const handleResetCooldown = async () => {
  resetLoading.value = true;
  try {
    const res = await request.post('/api/system_config/proxy/cooldown/reset');
    if (res.code === 200 && res.data) {
      if (res.data.runtime) {
        Object.assign(runtime, res.data.runtime);
        cooldownTickOffset.value = 0;
      }
      message.success(res.message || pageText('pages.operationSuccess'));
    } else if (res.message) {
      message.error(res.message);
    }
  } catch (err) {
    const msg = err?.response?.data?.message;
    if (msg) message.error(msg);
  } finally {
    resetLoading.value = false;
  }
};

let lastCooldownRefreshAt = 0;

const startTickTimer = () => {
  stopTimers();
  tickTimer = setInterval(() => {
    if (runtime.cooldown_remaining_sec > 0 || (runtime.blocked_exits || []).length > 0) {
      cooldownTickOffset.value += 1;
      const now = Date.now();
      if (
        displayCooldownSec.value === 0
        && blockedExitsList.value.length === 0
        && !refreshLoading.value
        && (now - lastCooldownRefreshAt >= 10000)
      ) {
        lastCooldownRefreshAt = now;
        fetchProxyConfig(false);
      }
    }
  }, 1000);
};

const stopTimers = () => {
  if (tickTimer) {
    clearInterval(tickTimer);
    tickTimer = null;
  }
};

const closeModals = () => {
  nodeModalOpen.value = false;
};

const focusSection = (anchor, retries = 3) => {
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
  fetchProxyConfig(true);
  startTickTimer();
});

onActivated(() => {
  startTickTimer();
});

onDeactivated(() => {
  stopTimers();
  closeModals();
});

onUnmounted(() => {
  stopTimers();
});

defineExpose({
  fetchProxyConfig,
  hasUnsavedChanges,
  saveChanges: handleSavePolicies,
  resetChanges: resetPolicyEdits,
  isSaving: () => policySaving.value,
  stopTimers,
  closeModals,
  focusSection,
});
</script>

<style scoped>
.proxy-panel-root {
  max-width: 1240px;
  padding-bottom: 24px;
}

.quick-uri-box {
  margin-bottom: 12px;
  padding: 10px 12px;
  border-radius: 6px;
  border: 1px dashed var(--arl-border-color);
  background: var(--arl-bg-light);
}
.quick-uri-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--arl-text-secondary);
  margin-bottom: 6px;
}
.quick-uri-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.osint-status-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #faad14;
  flex-shrink: 0;
}
.osint-status-dot.is-danger { background: #ff4d4f; }
.osint-status-dot.is-warning { background: #faad14; }
.osint-status-dot.is-info { background: #1677ff; }
.osint-status-dot.is-ok { background: #52c41a; }

.proxy-section-card {
  border-radius: 8px;
  border: 1px solid var(--arl-border-color);
  background: var(--arl-bg-card);
}

.card-header-flex {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 10px;
}

.section-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--arl-text-color);
  margin-right: 10px;
}

.section-subtitle {
  font-size: 12px;
  font-weight: 400;
  color: var(--arl-text-color);
  opacity: 0.6;
}

.card-header-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.node-name-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.node-name-line {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}
.node-name-text {
  font-weight: 600;
  color: var(--arl-text-color);
}
.node-remark-text {
  font-size: 12px;
  color: var(--arl-text-color);
  opacity: 0.6;
}

.endpoint-cell {
  display: flex;
  align-items: center;
  gap: 6px;
}
.endpoint-code {
  font-size: 12px;
  font-family: 'SFMono-Regular', Consolas, monospace;
  color: var(--arl-text-color);
  opacity: 0.85;
}

.probe-result-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.probe-tags {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12px;
}
.probe-metric {
  font-family: monospace;
  color: var(--arl-text-color);
}
.probe-ip {
  font-family: monospace;
  color: var(--arl-text-color);
  opacity: 0.78;
}
.probe-detail {
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.6;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.probe-empty {
  font-size: 12px;
  color: var(--arl-text-color);
  opacity: 0.45;
}

.policy-domain-box {
  height: 100%;
  border: 1px solid var(--arl-border-color);
  border-radius: 8px;
  padding: 14px;
  background: var(--arl-bg-light);
}

.domain-header {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 6px;
}
.domain-status-tag {
  margin: 0 0 0 auto;
}
.osint-cooldown-box {
  margin-top: 12px;
  padding: 10px 12px;
  border: 1px solid var(--arl-border-color);
  border-left: 3px solid #faad14;
  border-radius: 6px;
  background: var(--arl-bg-white);
}
.osint-cooldown-box.is-danger {
  border-left-color: #ff4d4f;
}
.osint-cooldown-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}
.osint-cooldown-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  font-weight: 600;
  color: var(--arl-text-color);
}
.osint-blocked-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.osint-blocked-item {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
  font-size: 12px;
}
.osint-blocked-reason {
  color: var(--arl-text-color);
  opacity: 0.75;
  word-break: break-word;
}
.domain-badge {
  font-size: 11px;
  font-weight: 700;
  padding: 2px 7px;
  border-radius: 4px;
  letter-spacing: 0.4px;
}
.domain-badge.osint { background: rgba(250, 140, 22, 0.14); color: #d46b08; }
.domain-badge.scan { background: rgba(22, 119, 255, 0.14); color: #1677ff; }
.domain-badge.intel { background: rgba(114, 46, 209, 0.14); color: #722ed1; }

.domain-title {
  font-weight: 600;
  font-size: 14px;
  color: var(--arl-text-color);
}
.domain-desc {
  font-size: 12px;
  color: var(--arl-text-color);
  opacity: 0.68;
  margin-bottom: 12px;
  min-height: 34px;
}

.switch-inline {
  display: flex;
  align-items: center;
  gap: 8px;
}
.switch-hint {
  font-size: 12px;
  color: var(--arl-text-color);
  opacity: 0.72;
}

.engine-switch-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.engine-switch-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--arl-text-color);
  cursor: pointer;
}

.bypass-section {
  margin-top: 16px;
  padding: 14px;
  border: 1px solid var(--arl-border-color);
  border-radius: 8px;
  background: var(--arl-bg-light);
}
.bypass-header {
  font-weight: 600;
  font-size: 13px;
  color: var(--arl-text-color);
  margin-bottom: 10px;
}
.bypass-switches {
  display: flex;
  flex-direction: column;
  gap: 10px;
}
.bypass-switch-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  cursor: pointer;
}
.bypass-item-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--arl-text-color);
}
.bypass-item-desc {
  font-size: 12px;
  color: var(--arl-text-color);
  opacity: 0.62;
}

.modal-probe-box {
  border-top: 1px solid var(--arl-border-color);
  padding-top: 10px;
  margin-top: 6px;
}
.modal-probe-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

@media (max-width: 768px) {
  .domain-desc { min-height: 0; }
}
</style>
