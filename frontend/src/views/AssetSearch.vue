<template>
  <div :class="['asset-search-page', 'arl-page-container', { 'is-virtual-mode': pagination.pageSize >= 100 }]">

    <div ref="actionBarRef" class="arl-hero-card">
      <div class="scope-hint-line">
        <span class="scope-hint-tag">{{ assetText('assets.allAssets') }}</span>
        <span>{{ assetText('assets.statisticsAndSearchesCoverAllAssetsAcrossAll') }}</span>
      </div>
      <a-tabs style="margin-bottom: 12px;" v-model:activeKey="activeTab" type="card" class="arl-detail-tabs">
        <a-tab-pane v-for="t in assetTabList" :key="t.key">
          <template #tab>
            <span class="asm-tab-item">
              <span>{{ t.label }}</span>
              <span
                v-if="overviewCounts[t.key] !== undefined"
                class="asm-tab-badge"
                :class="{ 'has-data': (overviewCounts[t.key] || 0) > 0 }"
              >{{ overviewCounts[t.key] === null ? '-' : overviewCounts[t.key] }}</span>
            </span>
          </template>
        </a-tab-pane>
      </a-tabs>

      <div v-if="activeTab === 'service'" style="margin-bottom: 12px; display: flex; align-items: center; gap: 8px;">
        <span class="asset-engine-label">{{ assetText('tasks.detectionEngine') }}</span>
        <a-radio-group v-model:value="serviceEngineType" button-style="solid" size="small" @change="onServiceEngineChange">
          <a-radio-button value="nmap">{{ assetText('tasks.portServicesNmap') }}</a-radio-button>
          <a-radio-button value="npoc">{{ assetText('assets.pythonPluginServicesLabel') }}</a-radio-button>
        </a-radio-group>
      </div>

      <div v-if="tabConfig[effectiveTab]?.searchFields" style="margin-bottom: 8px;">
        <a-form :label-wrap="true" :model="searchForm" layout="inline" class="asset-search-row-gap">
          <a-form-item v-for="field in tabConfig[effectiveTab].searchFields" :key="field.key" :label="field.label" :class="{ 'asset-status-field-wide': field.type === 'httpStatus' && assetLocale !== 'zh-CN' }">
            <HttpStatusFilter
              v-if="field.type === 'httpStatus'"
              v-model:value="searchForm[field.key]"
              size="small"
              @change="onSearch"
            />
            <a-select
              v-else-if="field.type === 'select'"
              v-model:value="searchForm[field.key]"
              :placeholder="assetText('tasks.selectField', { field: field.label })"
              style="width: 180px;"
              size="small"
              allowClear
              @change="onSearch"
            >
              <a-select-option v-for="opt in field.options" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </a-select-option>
            </a-select>

            <div
              v-else-if="field.hasOperatorSelect"
              style="display: flex; align-items: center; border: 1px solid var(--arl-border-color); border-radius: 4px; width: 280px; background: var(--arl-bg-white); height: 24px;"
            >
              <template v-if="field.type === 'select'">
                <a-select
                  v-model:value="searchForm[field.key]"
                  :placeholder="assetText('tasks.selectField', { field: field.label })"
                  :bordered="false"
                  size="small"
                  style="flex: 1; box-shadow: none;"
                  allowClear
                  @change="onSearch"
                >
                  <a-select-option v-for="opt in field.options" :key="opt.value" :value="opt.value">
                    {{ opt.label }}
                  </a-select-option>
                </a-select>
              </template>
              <template v-else>
                <a-input
                  v-model:value="searchForm[field.key]"
                  :placeholder="field.placeholder || assetText('tasks.enterField', { field: field.label })"
                  :bordered="false"
                  size="small"
                  style="flex: 1; box-shadow: none;"
                  allowClear
                  @pressEnter="onSearch"
                >
                  <template #suffix>
                    <search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" />
                  </template>
                </a-input>
              </template>
              <div style="width: 1px; height: 14px; background-color: var(--arl-border-color);"></div>
              <a-select
                v-model:value="field.operator"
                :bordered="false"
                size="small"
                class="asset-filter-operator" :class="{ 'asset-filter-operator-wide': assetLocale !== 'zh-CN' }"
                @change="onSearch"
              >
                <a-select-option v-for="op in field.operators" :key="op" :value="op">{{ formatAssetFilterOperator(op) }}</a-select-option>
              </a-select>
            </div>

            <a-input
              v-else
              v-model:value="searchForm[field.key]"
              :placeholder="assetText('tasks.enterField', { field: field.label })"
              style="width: 180px;"
              size="small"
              allowClear
              @pressEnter="onSearch"
            >
              <template #suffix>
                <search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" />
              </template>
            </a-input>
          </a-form-item>
        </a-form>
      </div>

      <div style="margin-top: 10px; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px;">
        <div style="display: flex; align-items: center; gap: 8px;">
          <a-button size="small" @click="resetSearch">
            <template #icon><undo-outlined /></template>
            {{ assetText('assets.reset') }}
          </a-button>
          <a-button v-if="tabConfig[effectiveTab]?.exportName" size="small" @click="handleExport">
            <template #icon><download-outlined /></template>
            {{ assetText('tasks.exportAssetType', { type: tabConfig[effectiveTab].exportName }) }}
          </a-button>
        </div>
        <div style="display: flex; align-items: center; gap: 8px;">
          <a-button v-if="activeTab === 'site'" type="primary" size="small" @click="openRiskModal">
            <template #icon><thunderbolt-outlined /></template>
            {{ assetText('tasks.createRiskScanningTask') }}
          </a-button>
        </div>
      </div>
    </div>

    <a-table :sticky="pagination.pageSize >= 100 ? false : stickyConfig"
        :loading="loading"
        :dataSource="dataSource"
        :columns="columns"
        :pagination="false"
        :scroll="pagination.pageSize >= 100 ? { y: tableScrollY, x: 'max-content' } : { x: 'max-content' }"
        :virtual="pagination.pageSize >= 100"
        size="small"
        :rowKey="(record) => record._id || record.id"
    >
            <template #bodyCell="{ column, record, index }">
        <template v-if="column.key === 'index'">
          <a style="">{{ (pagination.current - 1) * pagination.pageSize + index + 1 }}</a>
        </template>
<!--表格-站点列-->
        <template v-else-if="column.key === 'site'">
          <div class="site-header">
            <a :href="record.site || record.url" target="_blank" style="font-weight: 500;">
              <img v-if="record.favicon && record.favicon.data" :src="`data:image/png;base64,${record.favicon.data}`" class="site-img" />
              <img v-else-if="typeof record.favicon === 'string'" :src="`data:image/png;base64,${record.favicon}`" class="site-img" />

              {{ record.site || record.url }}
            </a>

            <p v-if="record.favicon && record.favicon.hash" class="site-word">{{ assetText('tasks.faviconHash') }}: {{ record.favicon.hash }}</p>
            <p v-else-if="record.favicon_hash" class="site-word">{{ assetText('tasks.faviconHash') }}: {{ record.favicon_hash }}</p>

            <div class="mt5" style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">

              <a-tag v-if="record.is_entry || record.isEntry" class="asset-entry-tag">{{ assetText('tasks.entryPoint') }}</a-tag>

              <template v-for="(t, idx) in (record.tags || record.tag || []).filter(Boolean)" :key="idx">
                <a-tag style="background: var(--arl-bg-light); color: var(--arl-text-color); border-color: var(--arl-border-color);">
                  {{ formatAssetTag(t) }}
                </a-tag>
              </template>
            </div>
          </div>
        </template>

        <template v-else-if="column.key === 'title'">
          <a-tooltip placement="topLeft" :overlayStyle="{ maxWidth: '400px' }">
            <template #title>
              <div style="word-break: break-all;">
                {{ record.title }}
              </div>
            </template>
            <div style="max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
              {{ record.title }}
            </div>
          </a-tooltip>
        </template>

        <template v-else-if="column.key === 'headers'">
          <div class="scroll-x"><pre>{{ record.headers }}</pre></div>
        </template>



        <template v-else-if="column.key === 'finger'">
          <div v-if="record.finger && record.finger.length > 0" style="display: flex; flex-wrap: wrap; gap: 4px;">
            <a-tag v-for="f in record.finger.slice(0, 3)" :key="f.name" color="blue" style="margin: 0; white-space: normal; height: auto; text-align: left;">{{ f.name }}</a-tag>
            <a-popover v-if="record.finger.length > 3" placement="top">
              <template #content>
                <div style="display: flex; flex-wrap: wrap; gap: 4px; max-width: 300px; max-height: 200px; overflow-y: auto;">
                  <a-tag v-for="f in record.finger" :key="f.name" color="blue" style="margin: 0; white-space: normal; height: auto; text-align: left;">{{ f.name }}</a-tag>
                </div>
              </template>
              <a-tag style="margin: 0; cursor: pointer; border-style: dashed;">+{{ record.finger.length - 3 }}</a-tag>
            </a-popover>
          </div>
        </template>


        <template v-else-if="column.key === 'screenshot'">
          <img v-if="record.screenshot" :src="`/api${record.screenshot}`" style="width: 280px; height: 160px; object-fit: cover; object-position: top; cursor: pointer; border: 1px solid var(--arl-border-color); border-radius: 4px;" @click="handlePreview(`/api${record.screenshot}`)" />
          <span v-else>-</span>
        </template>
<!--        插槽-->
        <template v-else-if="column.key === 'record'">
          <div v-if="record.record && record.record.length">
            <div v-for="(r, i) in record.record" :key="i">{{ r }}</div>
          </div>
          <span v-else>-</span>
        </template>

        <template v-else-if="column.key === 'ips'">
          <div v-if="record.ips && record.ips.length">

            <a-tooltip
                v-if="record.ips.length > 5"
                placement="top"
                :overlayInnerStyle="{ maxHeight: '400px', overflowY: 'auto' }"
            >
              <template #title>
                <div v-for="(ip, i) in record.ips" :key="'all-'+i">{{ ip }}</div>
              </template>

              <div style="cursor: pointer;">
                <div v-for="(ip, i) in record.ips.slice(0, 5)" :key="i">{{ ip }}</div>
                <div class="asset-field-hint">{{ assetText('tasks.andMore') }} {{ record.ips.length }} {{ assetText('tasks.itemsLabel') }}</div>
              </div>
            </a-tooltip>

            <div v-else>
              <div v-for="(ip, i) in record.ips" :key="i">{{ ip }}</div>
            </div>

          </div>
          <span v-else>-</span>
        </template>
        <template v-else-if="column.key === 'os_info'">
          <span>{{ record.os_info?.name || '-' }}</span>
        </template>
        <template v-else-if="column.key === 'port_info'">
          <span>{{ record.port_info && record.port_info.length ? record.port_info.map(p => p.port_id).join(', ') : '-' }}</span>
        </template>
        <template v-else-if="column.key === 'domain'">

          <div v-if="Array.isArray(record.domain) && record.domain.length">
            <a-tooltip v-if="record.domain.length > 5" placement="top" :overlayInnerStyle="{ maxHeight: '400px', overflowY: 'auto' }">
              <template #title>
                <div v-for="(dom, i) in record.domain" :key="'all-dom-'+i">{{ dom }}</div>
              </template>
              <div style="cursor: pointer;">
                <div v-for="(dom, i) in record.domain.slice(0, 5)" :key="i">{{ dom }}</div>
                <div class="asset-field-hint">{{ assetText('tasks.andMore') }} {{ record.domain.length }} {{ assetText('tasks.itemsLabel') }}</div>
              </div>
            </a-tooltip>
            <div v-else>
              <div v-for="(dom, i) in record.domain" :key="i">{{ dom }}</div>
            </div>
          </div>

          <span v-else-if="typeof record.domain === 'string'">{{ record.domain }}</span>

          <span v-else>-</span>
        </template>
        <template v-else-if="column.key === 'geo_city'">
          <span>{{ formatGeo(record.geo_city) }}</span>
        </template>
        <template v-else-if="column.key === 'geo_asn'">
          <span>{{ record.geo_asn?.organization || '-' }}</span>
        </template>

        <template v-else-if="column.key === 'host'">
          <span>{{ record.ip || record.host }}{{ record.port ? ':' + record.port : '' }}</span>
        </template>
        <template v-else-if="column.key === 'cert_detail'">
          <div v-if="record.cert" style="font-size: 13px; line-height: 1.8; color: var(--arl-text-color); padding: 12px 0;">

            <div class="asset-section-heading">{{ assetText('tasks.basicInformation') }}</div>

            <div style="display: flex; margin-bottom: 6px;">
              <div class="asset-option-label">{{ assetText('tasks.subject') }}</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.subject_dn || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div class="asset-option-label">{{ assetText('tasks.issuer') }}</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.issuer_dn || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div class="asset-option-label">{{ assetText('tasks.subjectAlternativeNames') }}</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.extensions?.subjectAltName || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div class="asset-option-label">{{ assetText('tasks.serialNumber') }}</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.serial_number || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 16px;">
              <div class="asset-option-label">{{ assetText('tasks.time') }}</div>
              <div class="asset-option-value">{{ record.cert.validity?.start || '-' }} {{ assetText('tasks.to') }} {{ record.cert.validity?.end || '-' }}</div>
            </div>

            <div class="asset-section-heading">{{ assetText('tasks.fingerprints') }}</div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">SHA-256</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.fingerprint?.sha256 || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">SHA-1</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.fingerprint?.sha1 || '-' }}</div>
            </div>

            <div style="display: flex; margin-bottom: 6px;">
              <div style="width: 120px; text-align: right; margin-right: 12px; font-weight: 500;">MD5</div>
              <div style="flex: 1; word-break: break-all; color: var(--arl-text-color);">{{ record.cert.fingerprint?.md5 || '-' }}</div>
            </div>

          </div>
          <span v-else>-</span>
        </template>

        <template v-else-if="column.key === 'ip_port'">
          <div v-if="record.service_info && record.service_info.length">
            <div v-for="(info, i) in record.service_info" :key="i" style="line-height: 1.8;">
              {{ info.ip }}:{{ info.port_id }}
            </div>
          </div>
          <span v-else>-</span>
        </template>
        <template v-else-if="column.key === 'product'">
          <div v-if="record.service_info && record.service_info.length">
            <div v-for="(info, i) in record.service_info" :key="i" style="line-height: 1.8;">
              {{ info.product || '-' }}
            </div>
          </div>
          <span v-else>-</span>
        </template>

        <template v-else-if="column.key === 'fileleak_url' || column.key === 'url_link' || column.key === 'nuclei_vuln_url'">
          <a :href="record.url || record.vuln_url" target="_blank" style="word-break: break-all;">
            {{ record.url || record.vuln_url || '-' }}
          </a>
        </template>

        <template v-else-if="column.key === 'verify_data'">
          <div style="max-height: 100px; overflow-y: auto; color: #e57373; font-family: monospace; font-size: 12px; word-break: break-all;">
            {{ record.verify_data || record.proof || '-' }}
          </div>
        </template>

        <template v-else-if="column.key === 'cidr_ip'">
          <a style="cursor: pointer; font-family: monospace; font-size: 14px;" @click="openCidrDetail(record)">{{ record.cidr_ip || '-' }}</a>
        </template>

        <template v-else-if="column.key === 'ip_count_col'">
          <span>{{ record.ip_count || 0 }}</span>
        </template>

        <template v-else-if="column.key === 'domain_count_col'">
          <span>{{ record.domain_count || 0 }}</span>
        </template>

        <template v-else-if="column.key === 'verify_command'">
          <div style="max-height: 100px; overflow-y: auto; background: var(--arl-bg-light); padding: 4px 8px; border-radius: 4px; font-family: monospace; font-size: 12px; word-break: break-all;">
            {{ record.verify_command || record.curl_command || '-' }}
          </div>
        </template>

        <template v-else-if="column.key === 'finger_name'">
          <a style="cursor: pointer;" @click="openFingerModal(record.name)">{{ record.name || '-' }}</a>
        </template>

        <template v-else-if="column.key === 'wih_source'">
          <div style="word-break: break-all; color: var(--arl-text-color); line-height: 1.6;">
            {{ record.source || '-' }}
          </div>
        </template>

        <template v-else-if="column.key === 'content' && activeTab === 'wih'">
          <div class="wih-api-content">
            <span>{{ record.content }}</span>
            <div class="wih-api-actions"><a-button v-if="isApiEndpointRecord(record)" type="link" size="small" @click="showWihApiDetails(record)">{{ assetText('wihApi.viewDetails') }}</a-button></div>
          </div>
        </template>

        <template v-else-if="column.key === 'wih_site'">
          <div style="display: flex; align-items: center; gap: 8px;">
            <a :href="record.site" target="_blank" style="word-break: break-all;">
              {{ record.site || '-' }}
            </a>
            <a-popover v-if="record.sites && record.sites.length > 1" placement="topLeft">
              <template #content>
                <div style="max-height: 300px; overflow-y: auto; display: flex; flex-direction: column; gap: 4px;">
                  <a v-for="(s, idx) in record.sites.slice(1)" :key="idx" :href="s" target="_blank" style="word-break: break-all;">
                    {{ s }}
                  </a>
                </div>
              </template>
              <a-badge :count="assetText('tasks.countWebsites', { count: record.sites.length - 1 })" class="asset-site-count" />
            </a-popover>
          </div>
        </template>

      </template>
    </a-table>

    <WihApiDetailsDrawer v-model:open="wihApiDetailsOpen" :record="wihApiDetailsRecord" :context-key="route.fullPath + ':' + activeTab" />

    <!-- 综合C段详情弹窗 (提取为组件) -->
    <CidrDetailModal v-model:open="cipDetailModalVisible" :record="currentCidrRecord" />

    <div v-if="tabConfig[effectiveTab]" class="arl-pagination-bar">
      <div class="pagination-info">{{ assetText('tasks.paginationSummary', { pages: Math.ceil(pagination.total / pagination.pageSize) || 1, total: pagination.total }) }}</div>
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

    <a-modal v-model:open="previewVisible" :footer="null" width="85vw" centered @cancel="previewVisible = false" :bodyStyle="{ padding: '16px' }">
      <img :src="previewImage" style="width: 100%; max-height: 85vh; object-fit: contain; display: block;" />
    </a-modal>

    <a-modal v-model:open="riskVisible" :title="assetText('tasks.addRiskScanningTask')" @ok="submitRiskTask" :confirmLoading="riskSubmitLoading" width="520px" wrapClassName="arl-theme-modal" rootClassName="arl-theme-modal" :okText="assetText('tasks.confirm')" :cancelText="assetText('assets.cancel')">
      <a-form :label-wrap="true" :model="riskForm" :label-col="{ span: assetLocale !== 'zh-CN' ? 7 : 5 }" :wrapper-col="{ span: assetLocale !== 'zh-CN' ? 15 : 17 }" class="asset-risk-form">
        <a-form-item :label="assetText('tasks.policyName')" name="policy_id" :rules="[{ required: true, message: assetText('tasks.selectAPolicy') }]">
          <a-select v-model:value="riskForm.policy_id" :placeholder="assetText('tasks.selectAPolicy')" :options="policyOptions" show-search option-filter-prop="label" @change="handlePolicyChange"/>
        </a-form-item>
        <a-form-item :label="assetText('assets.taskName')" name="name" :rules="[{ required: true, message: assetText('tasks.enterATaskName') }]">
          <a-input v-model:value="riskForm.name" />
        </a-form-item>
        <div class="asset-risk-count">{{ assetText('tasks.targetsNumberSelected') }} {{ targetCount }}</div>
      </a-form>
    </a-modal>

  </div>



    <!-- 指纹统计关联站点弹窗 -->
    <a-modal v-model:open="fingerModalVisible" :title="assetText('tasks.websitesWithFingerprintName', { name: currentFingerName })" :footer="null" width="800px">
      <a-table
        :dataSource="fingerModalData"
        :columns="fingerModalColumns"
        :loading="fingerModalLoading"
        :pagination="false"
        size="small"
        rowKey="_id"
        :scroll="{ y: 400 }"
      >
        <template #bodyCell="{ column, record, index }">
          <template v-if="column.key === 'index'">{{ index + 1 }}</template>
          <template v-else-if="column.key === 'site'">
            <a :href="record.site || record.url" target="_blank">{{ record.site || record.url }}</a>
          </template>
          <template v-else-if="column.key === 'title'">
            <a-tooltip placement="topLeft" :overlayStyle="{ maxWidth: '400px' }">
              <template #title>
                <div style="word-break: break-all;">
                  {{ record.title }}
                </div>
              </template>
              <div style="max-width: 250px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
                {{ record.title }}
              </div>
            </a-tooltip>
          </template>
        </template>
      </a-table>
    </a-modal>

</template>

<script setup>
import { useI18n } from 'vue-i18n';
defineOptions({ name: 'AssetSearch' });

import { ref, onMounted, onActivated, onDeactivated, reactive, watch, onUnmounted, computed, nextTick } from 'vue';
import { useSticky } from '../utils/useSticky';
const actionBarRef = ref(null);
const { stickyConfig, actionBarHeight } = useSticky(actionBarRef);
import { useRoute } from 'vue-router';
import request from '../utils/request';
import HttpStatusFilter from '../components/HttpStatusFilter.vue';
import { buildAssetFilterParams, formatAssetFilterOperator } from '../utils/assetFilters';
import { message } from 'ant-design-vue';
import { SearchOutlined, UndoOutlined, DownloadOutlined, ThunderboltOutlined } from '@ant-design/icons-vue';
import CidrDetailModal from '../components/CidrDetailModal.vue';
import WihApiDetailsDrawer from '../components/WihApiDetailsDrawer.vue';
import { isApiEndpointRecord } from '../utils/wihApi';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import { createTabStateCache } from '../utils/useTabStateCache';
import { formatGeo } from '../utils/formatGeo';

const { t: assetText, locale: assetLocale } = useI18n({ useScope: 'global' });

const wihApiDetailsOpen = ref(false);
const wihApiDetailsRecord = ref(null);
const showWihApiDetails = record => {
  if (!isApiEndpointRecord(record)) return;
  wihApiDetailsRecord.value = record;
  wihApiDetailsOpen.value = true;
};

const formatAssetTag = tag => {
  const label = typeof tag === 'string' ? tag : (tag?.name || tag?.tag_name || tag);
  if (label === '入口') return assetText('tasks.entryPoint');
  if (label === '待测试') return assetText('assets.toTest');
  return label;
};

const windowHeight = ref(typeof window !== 'undefined' ? window.innerHeight : 900);
const onWindowResize = () => {
  windowHeight.value = window.innerHeight;
};

// 动态测算可用纵向高度：
// windowHeight 减去 Header(64px) - Layout margin(32px) - 容器 padding(48px) - 底部分页栏(48px) - 表头(55px) 与操作栏动态高度
const tableScrollY = computed(() => {
  const barHeight = actionBarHeight.value || 180;
  const available = windowHeight.value - barHeight - 240;
  return Math.max(280, available);
});

const route = useRoute();
const isHydrating = ref(true);
const serviceEngineType = ref(route.query.tab === 'npoc_service' ? 'npoc' : 'nmap');
const activeTab = ref(route.query.tab === 'npoc_service' ? 'service' : (route.query.tab || 'site'));
const effectiveTab = computed(() => {
  if (activeTab.value === 'service' && serviceEngineType.value === 'npoc') {
    return 'npoc_service';
  }
  return activeTab.value;
});
const loading = ref(false);
const dataSource = ref([]);

// 资产维度页签定义（key 需与后端 /asset_overview/count 的 counts 键保持一致）
const assetTabList = [
  { key: 'site', get label() { return assetText('tasks.websites'); } },
  { key: 'domain', get label() { return assetText('tasks.subdomains'); } },
  { key: 'ip', label: 'IP' },
  { key: 'cert', get label() { return assetText('assets.sslCertificates'); } },
  { key: 'service', get label() { return assetText('tasks.services'); } },
  { key: 'fileleak', get label() { return assetText('tasks.fileDisclosure'); } },
  { key: 'url', get label() { return assetText('tasks.urls'); } },
  { key: 'cip', get label() { return assetText('tasks.cClassNetworks'); } },
  { key: 'stat_finger', get label() { return assetText('tasks.fingerprintStatistics'); } },
  { key: 'wih', label: 'WIH' },
  { key: 'vuln', get label() { return assetText('tasks.risks'); } },
  { key: 'nuclei_result', label: 'nuclei' }
];

// 各维度总量徽标：一次请求取回全部维度计数，避免为 12 个页签各发一次计数请求
// 取值为 null 表示该维度计数失败，徽标显示 "-" 而非 0
const overviewCounts = ref({});

const fetchOverviewCounts = async () => {
  try {
    const res = await request.get('/asset_overview/count');
    if (res.code === 200 && res.counts) {
      overviewCounts.value = res.counts;
    }
  } catch (e) {
    console.error('获取资产维度总览计数失败', e);
  }
};

const fingerModalVisible = ref(false);
const currentFingerName = ref('');
const fingerModalLoading = ref(false);
const fingerModalData = ref([]);
const fingerModalColumns = [
  { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
  { get title() { return assetText('tasks.websiteUrl'); }, key: 'site', width: 300 },
  { get title() { return assetText('tasks.title'); }, key: 'title', dataIndex: 'title', width: 200 },
  { get title() { return assetText('tasks.statusCode'); }, key: 'status', dataIndex: 'status', width: 100 }
];

const openFingerModal = async (fingerName) => {
  currentFingerName.value = fingerName;
  fingerModalVisible.value = true;
  fingerModalLoading.value = true;
  fingerModalData.value = [];
  try {
    const res = await request.get('/site/', {
      params: {
        finger: fingerName,
        page: 1,
        size: 100
      }
    });
    fingerModalData.value = res.items || res.data?.items || [];
  } catch (error) {
    console.error('Fetch finger sites failed:', error);
    message.error(assetText('tasks.failedToLoadAssociatedWebsites'));
  } finally {
    fingerModalLoading.value = false;
  }
};
const searchForm = ref({});
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });
let lastFetchedPage = 1;
let lastFetchedSize = globalPageSize.value;

watch(() => pagination.pageSize, (newSize) => {
  const target = Number(newSize) || 10;
  if (globalPageSize.value !== target) {
    globalPageSize.value = target;
  }
});

watch(globalPageSize, (newSize) => {
  const target = Number(newSize) || 10;
  if (pagination.pageSize !== target) {
    pagination.pageSize = target;
    tabCache.invalidateAllMemoryCaches();
    if (tabConfig[effectiveTab.value]) {
      fetchData();
    }
  }
});

const previewVisible = ref(false);
const previewImage = ref('');
const handlePreview = (url) => { previewImage.value = url; previewVisible.value = true; };

const tabConfig = reactive({
  site: {
    url: '/site/',
    exportUrl: '/site/export/',
    get exportName() { return assetText('tasks.websites'); },
    searchFields: [
      { get label() { return assetText('tasks.websites'); }, key: 'site', operator: '=' },
      { get label() { return assetText('tasks.title'); }, key: 'title', operator: '=' },
      { get label() { return assetText('tasks.webServer'); }, key: 'http_server', operator: '=' },
      { get label() { return assetText('tasks.statusCode'); }, key: 'status', type: 'httpStatus' },
      { get label() { return assetText('tasks.headers'); }, key: 'headers', operator: '=' },
      {
        get label() { return assetText('tasks.fingerprints'); },
        key: 'finger',
        operator: '模糊匹配',
        hasOperatorSelect: true,
        operators: ['模糊匹配', '精确匹配']
      },
      { get label() { return assetText('tasks.faviconHash'); }, key: 'favicon.hash', operator: '=' },
      { get label() { return assetText('tasks.tags'); }, key: 'tag', operator: '=' }
    ],
    // 💥 修复：删除了瞎加的 IP、端口和操作列，完全对齐原版站点表格！表格控制
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return assetText('tasks.websites'); }, key: 'site', width: 250 },
      { get title() { return assetText('tasks.statusCode'); }, dataIndex: 'status', key: 'status', width: 100, align: 'center' },
      { get title() { return assetText('tasks.title'); }, dataIndex: 'title', key: 'title', width: 200 },
      { get title() { return assetText('tasks.headers'); }, key: 'headers',width: 500},
      { get title() { return assetText('tasks.fingerprints'); }, key: 'finger', width: 150 },
      { get title() { return assetText('tasks.screenshot'); }, key: 'screenshot', width: 280 } // 保持宽度给图片留足空间
    ]
  },
  // 💡 新增：子域名 Tab 的 1:1 配置
  domain: {
    url: '/domain/',
    exportUrl: '/domain/export/',
    get exportName() { return assetText('tasks.subdomains'); },
    searchFields: [
      { get label() { return assetText('tasks.domains'); }, key: 'domain', operator: '=' },
      { get label() { return assetText('tasks.recordValue'); }, key: 'record', operator: '=' },
      { get label() { return assetText('tasks.type'); }, key: 'type', operator: '=' },
      { label: 'IP', key: 'ips', operator: '=' },
      { get label() { return assetText('tasks.source'); }, key: 'source', operator: '=' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return assetText('tasks.domains'); }, dataIndex: 'domain', key: 'domain', width: 250 },
      { get title() { return assetText('tasks.dnsRecordType'); }, dataIndex: 'type', key: 'type', width: 120 },
      { get title() { return assetText('tasks.recordValue'); }, key: 'record', width: 300 },
      { get title() { return assetText('tasks.associatedIps'); }, key: 'ips', width: 250 },
      { get title() { return assetText('tasks.source'); }, dataIndex: 'source', key: 'source', width: 150 }
    ]
  },

  // 💡 新增：IP Tab 的 1:1 配置
  ip: {
    url: '/ip/',
    deleteUrl: '/ip/delete/', // 视上一轮测试情况，如果删不掉请改回 '/site/delete/'
    exportUrl: '/ip/export/',
    get exportName() { return assetText('tasks.ipPorts'); },
    searchFields: [
      { label: 'IP', key: 'ip', operator: '=' },
      // 🚨 核心修复：对齐后端的嵌套对象查询字段
      { get label() { return assetText('tasks.port'); }, key: 'port_info.port_id', operator: '=' },
      { get label() { return assetText('tasks.operatingSystem'); }, key: 'os_info.name', operator: '=' },
      { get label() { return assetText('tasks.domains'); }, key: 'domain', operator: '=' },
      { label: 'CDN', key: 'cdn_name', operator: '=', get placeholder() { return assetText('tasks.enterACdnProviderOrOriginServer'); } },
      {
        get label() { return assetText('tasks.ipType'); },
        key: 'ip_type',
        operator: '=',
        type: 'select',
        options: [
          { get label() { return assetText('tasks.publicPublic'); }, value: 'PUBLIC' },
          { get label() { return assetText('tasks.privatePrivate'); }, value: 'PRIVATE' }
        ]
      }
    ],
    cols: [
      // ... 列配置保持不变 ...
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { title: 'IP', dataIndex: 'ip', key: 'ip', width: 160 },
      { get title() { return assetText('tasks.operatingSystem'); }, key: 'os_info', width: 150 },
      { get title() { return assetText('tasks.openPorts'); }, key: 'port_info', width: 200 },
      { get title() { return assetText('tasks.associatedDomains'); }, key: 'domain', width: 250 },
      { title: 'CDN', dataIndex: 'cdn_name', key: 'cdn_name', width: 150 },
      { get title() { return assetText('assets.location'); }, key: 'geo_city', width: 180 },
      { get title() { return assetText('assets.asOrganization'); }, key: 'geo_asn', width: 280 }
    ]
  },
  // 💡 重新构建：1:1 对齐截图的 SSL证书 配置
  cert: {
    url: '/cert/',
    exportUrl: '/cert/export/',
    get exportName() { return assetText('assets.sslCertificates'); },
    searchFields: [
      { get label() { return assetText('tasks.ipFields'); }, key: 'ip', operator: '=' },
      { get label() { return assetText('tasks.issuer'); }, key: 'cert.issuer_dn', operator: '=' },
      { get label() { return assetText('tasks.subject'); }, key: 'cert.subject_dn', operator: '=' },
      { label: 'SHA-1', key: 'cert.fingerprint.sha1', operator: '=' },
      { get label() { return assetText('tasks.subjectAlternativeNames'); }, key: 'cert.extensions.subjectAltName', operator: '=' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return assetText('tasks.host'); }, key: 'host', width: 180 },
      { get title() { return assetText('tasks.sslCertificateInformation'); }, key: 'cert_detail', width: 900 } // 留出巨大的空间给卡片
    ]
  },

  // 💡 新增：服务 Tab 的 1:1 配置
  service: {
    url: '/service/',
    // 服务 Tab 不配置 exportUrl，保持无导出按钮的视图布局
    searchFields: [
      { get label() { return assetText('tasks.services'); }, key: 'service_name', operator: '=' },
      { label: 'IP', key: 'service_info.ip', operator: '=' },
      { get label() { return assetText('tasks.port'); }, key: 'service_info.port_id', operator: '=' },
      { get label() { return assetText('tasks.product'); }, key: 'service_info.product', operator: '=' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return assetText('tasks.services'); }, dataIndex: 'service_name', key: 'service_name', width: 150, align: 'center' },
      { get title() { return assetText('tasks.ipPort'); }, key: 'ip_port', width: 300 },
      { get title() { return assetText('tasks.product'); }, key: 'product', width: 250 }
    ]
  },

  // 💡 新增：文件泄露 Tab 的 1:1 配置
  fileleak: {
    url: '/fileleak/',
    // 🚨 同样不配置 exportUrl，隐身导出按钮
    searchFields: [
      { label: 'URL', key: 'url', operator: '=' },
      { get label() { return assetText('tasks.title'); }, key: 'title', operator: '=' },
      { get label() { return assetText('tasks.statusCode'); }, key: 'status_code', type: 'httpStatus' },
      { get label() { return assetText('tasks.bodyLength'); }, key: 'content_length', operator: '=' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { title: 'URL', key: 'fileleak_url', width: 500 }, // 用专属 key 渲染超链接
      { get title() { return assetText('tasks.title'); }, dataIndex: 'title', key: 'title', width: 250 },
      { get title() { return assetText('tasks.statusCode'); }, dataIndex: 'status_code', key: 'status_code', width: 100, align: 'center' },
      { get title() { return assetText('tasks.bodyLength'); }, dataIndex: 'content_length', key: 'content_length', width: 120, align: 'center' }
    ]
  },

  // 💡 新增：URL信息 Tab 的 1:1 配置
  url: {
    url: '/url/',
    exportUrl: '/url/export/', // 恢复导出接口
    get exportName() { return assetText('tasks.urls'); },     // 自动生成 URL 导出按钮
    searchFields: [
      { label: 'URL', key: 'url', operator: '=' },
      { get label() { return assetText('tasks.title'); }, key: 'title', operator: '=' },
      { get label() { return assetText('tasks.statusCode'); }, key: 'status_code', type: 'httpStatus' },
      {
        get label() { return assetText('tasks.bodyLength'); },
        key: 'content_length',
        operator: '等于',
        hasOperatorSelect: true,
        operators: ['等于', '大于', '小于']
      },
      {
        get label() { return assetText('tasks.source'); },
        key: 'source',
        type: 'select',
        options: [
          { get label() { return assetText('tasks.crawlerSiteSpider'); }, value: 'site_spider' },
          { get label() { return assetText('tasks.searchEngineSearchEngine'); }, value: 'search_engine' },
          { label: 'AlienVault', value: 'alienvault' },
          { label: 'WaybackMachine', value: 'waybackmachine' },
          { label: 'CommonCrawl', value: 'commoncrawl' },
          { get label() { return assetText('tasks.fuzzing'); }, value: 'fuzz' }
        ],
        operator: '='
      }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { title: 'URL', key: 'url_link', width: 450 }, // 专用 key 渲染超链接
      { get title() { return assetText('tasks.title'); }, dataIndex: 'title', key: 'title', width: 200 },
      { get title() { return assetText('tasks.statusCode'); }, dataIndex: 'status_code', key: 'status_code', width: 100, align: 'center' },
      { get title() { return assetText('tasks.bodyLength'); }, dataIndex: 'content_length', key: 'content_length', width: 120, align: 'center' },
      { get title() { return assetText('tasks.source'); }, dataIndex: 'source', key: 'source', width: 150 }
    ]
  },

  // 💡 新增：风险 Tab 的 1:1 配置
  vuln: {
    url: '/vuln/',
    // 🚨 截图显示无导出按钮，所以不配置 exportUrl
    searchFields: [
      { get label() { return assetText('tasks.vulnerabilityName'); }, key: 'vul_name', operator: '=' },
      { get label() { return assetText('tasks.category'); }, key: 'vul_category', operator: '=' }, // ARL 常用的类别字段名
      { get label() { return assetText('tasks.applicationName'); }, key: 'app_name', operator: '=' },
      { get label() { return assetText('tasks.target'); }, key: 'target', operator: '=' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return assetText('tasks.vulnerabilityName'); }, dataIndex: 'vul_name', key: 'vul_name', width: 250 },
      { get title() { return assetText('tasks.category'); }, dataIndex: 'vul_category', key: 'vul_category', width: 120 },
      { get title() { return assetText('tasks.applicationName'); }, dataIndex: 'app_name', key: 'app_name', width: 150 },
      { get title() { return assetText('tasks.target'); }, dataIndex: 'target', key: 'target', width: 200 },
      { get title() { return assetText('tasks.credentials'); }, key: 'verify_data', width: 350 }, // 凭证通常较长，用插槽渲染
      { get title() { return assetText('tasks.discoveredAt'); }, dataIndex: 'insert_time', key: 'insert_time', width: 160 }
    ]
  },

  // 💡 新增：Python 插件服务 Tab 的 1:1 配置
  npoc_service: {
    url: '/npoc_service/',
    // 🚨 截图显示无导出按钮，不配置 exportUrl
    searchFields: [
      { get label() { return assetText('tasks.protocol'); }, key: 'scheme', operator: '=' },
      { get label() { return assetText('tasks.host'); }, key: 'host', operator: '=' },
      { get label() { return assetText('tasks.port'); }, key: 'port', operator: '=' },
      { get label() { return assetText('tasks.target'); }, key: 'target', operator: '=' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return assetText('tasks.protocol'); }, dataIndex: 'scheme', key: 'scheme', width: 150 },
      { get title() { return assetText('tasks.host'); }, dataIndex: 'host', key: 'host', width: 200 },
      { get title() { return assetText('tasks.port'); }, dataIndex: 'port', key: 'port', width: 100, align: 'center' },
      { get title() { return assetText('tasks.target'); }, dataIndex: 'target', key: 'target', width: 250 },
      { get title() { return assetText('tasks.savedAt'); }, dataIndex: 'insert_time', key: 'insert_time', width: 180 }
    ]
  },

  // 💡 新增：C段 Tab 的 1:1 配置
  cip: {
    url: '/cip/',
    exportUrl: '/cip/export/', // 恢复导出接口
    get exportName() { return assetText('tasks.cClassNetworks'); },         // 自动生成 C 段导出按钮
    searchFields: [
      { get label() { return assetText('tasks.cClassNetworks'); }, key: 'cidr_ip', operator: '=' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return assetText('tasks.cClassNetworks'); }, dataIndex: 'cidr_ip', key: 'cidr_ip', width: 300 },
      { get title() { return assetText('tasks.ipCount'); }, key: 'ip_count_col', width: 150, align: 'center' },
      { get title() { return assetText('tasks.domainCount'); }, key: 'domain_count_col', width: 150, align: 'center' }
    ]
  },

  // 💡 新增：nuclei Tab 的 1:1 配置
  nuclei_result: {
    url: '/nuclei_result/',
    deleteUrl: '/nuclei_result/delete/', // 视后端情况，如果报错可改为 '/site/delete/'
    // 🚨 截图显示无导出按钮，不配置 exportUrl
    searchFields: [
      { get label() { return assetText('tasks.templateId'); }, key: 'template_id', operator: '=' },
      { get label() { return assetText('tasks.target'); }, key: 'target', operator: '=' },
      { get label() { return assetText('tasks.vulnerableUrl'); }, key: 'vuln_url', operator: '=' },
      { get label() { return assetText('tasks.vulnerabilityName'); }, key: 'vuln_name', operator: '=' },
      {
        get label() { return assetText('tasks.severity'); },
        key: 'vuln_severity',
        operator: '=',
        type: 'select',
        options: [
          { get label() { return assetText('assets.critical'); }, value: 'critical' },
          { get label() { return assetText('assets.high'); }, value: 'high' },
          { get label() { return assetText('assets.medium'); }, value: 'medium' },
          { get label() { return assetText('assets.low'); }, value: 'low' },
          { get label() { return assetText('assets.informational'); }, value: 'info' }
        ]
      }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return assetText('tasks.templateId'); }, dataIndex: 'template_id', key: 'template_id', width: 180 },
      { get title() { return assetText('tasks.target'); }, dataIndex: 'target', key: 'target', width: 200 },
      { get title() { return assetText('tasks.vulnerableUrl'); }, key: 'nuclei_vuln_url', width: 300 }, // 用专用 key 渲染超链接
      { get title() { return assetText('tasks.vulnerabilityName'); }, dataIndex: 'vuln_name', key: 'vul_name', width: 200 },
      { get title() { return assetText('tasks.severity'); }, dataIndex: 'vuln_severity', key: 'vuln_severity', width: 100, align: 'center' },
      { get title() { return assetText('tasks.savedAt'); }, dataIndex: 'insert_time', key: 'insert_time', width: 160 },
      { get title() { return assetText('tasks.verificationCommand'); }, key: 'verify_command', width: 350 } // 命令可能很长，用插槽防撑破
    ]
  },

  // 💡 新增：指纹统计 Tab 的 1:1 配置
  stat_finger: {
    url: '/stat_finger/',
    deleteUrl: '/site/delete/', // 视后端情况，如果报错可改为 '/site/delete/'
    // 🚨 截图显示无导出按钮
    searchFields: [
      {
        get label() { return assetText('tasks.fingerprints'); },
        key: 'name',
        operator: '模糊匹配',
        hasOperatorSelect: true,
        operators: ['模糊匹配', '精确匹配']
      } // 后端字段是 name
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 80, align: 'center' },
      { get title() { return assetText('tasks.fingerprints'); }, key: 'finger_name', width: 500 }, // 用专用 key 渲染青蓝字体
      { get title() { return assetText('tasks.count'); }, dataIndex: 'cnt', key: 'cnt', width: 200 }
    ]
  },


  // 💡 新增：WIH (Web Info Hunter) Tab 的 1:1 配置
// 💡 修复：WIH (Web Info Hunter) Tab 配置
  wih: {
    url: '/wih/',
    exportUrl: '/wih/export/',
    exportName: 'WIH',
    searchFields: [
      {
        get label() { return assetText('tasks.recordType'); },
        key: 'record_type',
        operator: '等于',
        hasOperatorSelect: true,
        operators: ['等于', '不等于']
      },
      { get label() { return assetText('tasks.content'); }, key: 'content', operator: '=' },
      { get label() { return assetText('tasks.sourceJs'); }, key: 'source', operator: '=' },
      { get label() { return assetText('tasks.sourceWebsite'); }, key: 'site', operator: '=' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return assetText('tasks.recordType'); }, dataIndex: 'record_type', key: 'record_type', width: 120 },
      { get title() { return assetText('tasks.content'); }, dataIndex: 'content', key: 'content', width: 250 },
      { get title() { return assetText('tasks.sourceJs'); }, key: 'wih_source', width: 450 },
      { get title() { return assetText('tasks.sourceWebsite'); }, dataIndex: 'site', key: 'wih_site', width: 250 }
    ]
  }
});

const tabCache = createTabStateCache({
  getStorageKey: () => 'ARL_ASSET_SEARCH_TAB_STATE',
  tabConfig,
  defaultTab: 'site'
});

const columns = ref(tabConfig[effectiveTab.value]?.cols || tabConfig.site.cols);

// 切换服务识别引擎
const onServiceEngineChange = () => {
  const prevTabKey = effectiveTab.value === 'npoc_service' ? 'service' : 'npoc_service';
  tabCache.saveCurrentTab(prevTabKey, searchForm.value, pagination.current);

  const currentTabKey = effectiveTab.value;
  searchForm.value = tabCache.getTabSearchForm(currentTabKey);
  tabCache.applyTabOperators(currentTabKey);
  pagination.current = tabCache.getTabPage(currentTabKey);
  columns.value = tabConfig[currentTabKey]?.cols || [];

  const cached = tabCache.getMemoryCache(currentTabKey, pagination.pageSize);
  if (cached) {
    dataSource.value = cached.dataSource;
    pagination.total = cached.total;
    lastFetchedPage = pagination.current;
    lastFetchedSize = pagination.pageSize;
  } else {
    fetchData();
  }
};

// 🚨 核心逻辑调整：去掉 task_id 参数，纯净的全局搜索
const fetchData = async () => {
  const currentTab = effectiveTab.value;
  const config = tabConfig[currentTab];
  if (!config) return;

  const currentReqTab = currentTab;
  loading.value = true;
  try {
    const params = { page: pagination.current, size: pagination.pageSize };
    Object.assign(params, buildAssetFilterParams(searchForm.value, config.searchFields));
    const res = await request.get(config.url, { params });
    // 竞态防御：若响应到达时 Tab 已切换，丢弃过期响应
    if (effectiveTab.value !== currentReqTab) return;

    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
      lastFetchedPage = pagination.current;
      lastFetchedSize = pagination.pageSize;
      tabCache.updateMemoryCache(currentTab, dataSource.value, pagination.total, pagination.pageSize);
      tabCache.saveCurrentTab(currentTab, searchForm.value, pagination.current);
    }
  } catch (error) {
    if (effectiveTab.value === currentReqTab) {
      message.error(assetText('tasks.failedToLoadAssetData'));
    }
  } finally {
    if (effectiveTab.value === currentReqTab) {
      loading.value = false;
    }
  }
};

const handleExport = async () => {
  const currentTab = effectiveTab.value;
  const config = tabConfig[currentTab];
  if (!config || !config.exportUrl) return;

  try {
    message.loading({ content: assetText('tasks.generatingTypeExport', { type: config.exportName }), key: 'export_data' });
    const params = { page: 1, size: 100000 };
    Object.assign(params, buildAssetFilterParams(searchForm.value, config.searchFields));
    const res = await request.get(config.exportUrl, { params, responseType: 'blob' });
    const isCert = currentTab === 'cert';
    const mimeType = isCert ? 'application/json;charset=utf-8' : 'text/plain;charset=utf-8';
    const ext = isCert ? 'json' : 'txt';

    const blob = new Blob([res], { type: mimeType });
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `ARL_Global_${currentTab}_Export.${ext}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
    message.success({ content: assetText('tasks.typeExportCompleted', { type: config.exportName }), key: 'export_data', duration: 2 });
  } catch (error) {
    message.error({ content: assetText('assets.exportFailed'), key: 'export_data', duration: 2 });
  }
};

const onSearch = () => {
  pagination.current = 1;
  tabCache.saveCurrentTab(effectiveTab.value, searchForm.value, 1);
  fetchData();
};
const resetSearch = () => {
  searchForm.value = {};
  tabCache.resetTabState(effectiveTab.value);
  pagination.current = 1;
  fetchData();
};
const handleTableChange = (page, pageSize) => {
  const targetSize = Number(pageSize) || Number(pagination.pageSize) || 10;
  const sizeChanged = targetSize !== lastFetchedSize;
  const targetPage = sizeChanged ? 1 : (Number(page) || 1);

  // 防御重复触发：只有在单页条数未变且目标页码与已拉取页码完全相同时才阻断
  if (!sizeChanged && targetPage === lastFetchedPage && targetSize === lastFetchedSize) {
    return;
  }

  lastFetchedPage = targetPage;
  lastFetchedSize = targetSize;

  pagination.current = targetPage;
  pagination.pageSize = targetSize;

  if (sizeChanged) {
    tabCache.invalidateAllMemoryCaches();
    globalPageSize.value = targetSize;
  }

  tabCache.saveCurrentTab(effectiveTab.value, searchForm.value, pagination.current);
  fetchData();
};

watch(activeTab, (newVal, oldVal) => {
  const prevEffective = (oldVal === 'service' && serviceEngineType.value === 'npoc') ? 'npoc_service' : oldVal;
  if (prevEffective && tabConfig[prevEffective] && !isHydrating.value) {
    tabCache.saveCurrentTab(prevEffective, searchForm.value, pagination.current);
  }

  const currentTab = effectiveTab.value;
  if (tabConfig[currentTab]) {
    columns.value = tabConfig[currentTab].cols;

    // 恢复新选项卡的搜索表单、操作符与页码
    searchForm.value = tabCache.getTabSearchForm(currentTab);
    tabCache.applyTabOperators(currentTab);
    pagination.current = tabCache.getTabPage(currentTab);

    // 检查 URL query 是否为当前 Tab 提供了下钻参数覆盖
    let hasQueryOverrides = false;
    if (route.query && (route.query.tab === currentTab || (!route.query.tab && currentTab === 'site'))) {
      for (const key in route.query) {
        if (key !== 'tab') {
          searchForm.value[key] = route.query[key];
          hasQueryOverrides = true;
        }
      }
      if (hasQueryOverrides) {
        tabCache.saveCurrentTab(currentTab, searchForm.value, pagination.current);
      }
    }

    // 检查内存数据缓存（若有外部 query 下钻参数则强制穿透缓存，同时校验 pageSize）
    const cached = !hasQueryOverrides ? tabCache.getMemoryCache(currentTab, pagination.pageSize) : null;
    if (cached) {
      dataSource.value = cached.dataSource;
      pagination.total = cached.total;
      lastFetchedPage = pagination.current;
      lastFetchedSize = pagination.pageSize;
    } else {
      fetchData();
    }
  }
});

onMounted(() => {
  const restoredTab = tabCache.init();
  let queryTab = route.query.tab;
  if (queryTab === 'npoc_service') {
    serviceEngineType.value = 'npoc';
    queryTab = 'service';
  } else if (queryTab === 'service') {
    serviceEngineType.value = 'nmap';
  } else if (!queryTab && restoredTab === 'npoc_service') {
    serviceEngineType.value = 'npoc';
  }

  // 优先级：若 URL 带了 tab 参数则以 URL 为准，否则以 SessionStorage 恢复的为准
  const targetTab = (queryTab && tabConfig[queryTab])
    ? queryTab
    : ((restoredTab && tabConfig[restoredTab]) ? (restoredTab === 'npoc_service' ? 'service' : restoredTab) : 'site');

  window.addEventListener('resize', onWindowResize);

  if (activeTab.value !== targetTab) {
    activeTab.value = targetTab;
  } else {
    const currentTab = effectiveTab.value;
    columns.value = tabConfig[currentTab].cols;
    searchForm.value = tabCache.getTabSearchForm(currentTab);
    tabCache.applyTabOperators(currentTab);
    pagination.current = tabCache.getTabPage(currentTab);

    // 若 URL query 有额外搜索参数，覆盖进 searchForm 并保存
    let hasQueryOverrides = false;
    for (const key in route.query) {
      if (key !== 'tab') {
        searchForm.value[key] = route.query[key];
        hasQueryOverrides = true;
      }
    }
    if (hasQueryOverrides) {
      tabCache.saveCurrentTab(currentTab, searchForm.value, 1);
    }

    const cached = !hasQueryOverrides ? tabCache.getMemoryCache(currentTab) : null;
    if (cached) {
      dataSource.value = cached.dataSource;
      pagination.total = cached.total;
    } else {
      fetchData();
    }
  }

  nextTick(() => {
    isHydrating.value = false;
  });

  // 页签数量徽标：与列表数据并行拉取，不阻塞表格渲染
  fetchOverviewCounts();
});

onActivated(() => {
  // 页面被 keep-alive 复用时刷新徽标，避免数量停留在离开前的旧值
  fetchOverviewCounts();
});

onUnmounted(() => {
  window.removeEventListener('resize', onWindowResize);
});



// 风险任务下发 (全局模式)
const riskVisible = ref(false);
const riskSubmitLoading = ref(false);
const policyOptions = ref([]);
const riskForm = reactive({ policy_id: undefined, name: '' });
const targetCount = ref(0);
const currentResultSetId = ref('');

const openRiskModal = async () => {
  targetCount.value = pagination.total;
  if (targetCount.value === 0) return message.warning(assetText('tasks.noAssetTargetsAreAvailableForScanning'));

  riskForm.policy_id = undefined;
  riskForm.name = '';
  currentResultSetId.value = '';
  message.loading({ content: assetText('assets.preparingAllMatchingAssets'), key: 'risk_prepare' });

  try {
    const policyPromise = request.get('/policy/', { params: { size: 1000 } });
    const setParams = buildAssetFilterParams(searchForm.value, tabConfig[effectiveTab.value].searchFields);
    const resultSetPromise = request.get('/site/save_result_set/', { params: setParams });
    const [policyRes, resultSetRes] = await Promise.all([policyPromise, resultSetPromise]);

    if (policyRes.code === 200) {
      policyOptions.value = (policyRes.items || []).map(item => ({
        value: item._id, label: `${item.name} (PoC : ${item.policy?.poc_config?.length || 0})`
      }));
    }
    if (resultSetRes.code === 200) currentResultSetId.value = resultSetRes.data.result_set_id;

    message.success({ content: assetText('assets.ready'), key: 'risk_prepare', duration: 2 });
    riskVisible.value = true;
  } catch (error) {
    message.error({ content: assetText('assets.failedToPrepareData'), key: 'risk_prepare', duration: 2 });
  }
};

const handlePolicyChange = (val, option) => { if (option) riskForm.name = `风险巡航任务-${option.label}`; };

const submitRiskTask = async () => {
  if (!riskForm.policy_id || !riskForm.name) return message.warning(assetText('assets.completeAllRequiredFields'));
  riskSubmitLoading.value = true;
  try {
    const res = await request.post('/task/policy/', {
      name: riskForm.name, task_tag: 'risk_cruising', target: '',
      policy_id: riskForm.policy_id, result_set_id: currentResultSetId.value
    });
    if (res.code === 200) {
      message.success(assetText('tasks.riskScanningTaskCreated'));
      riskVisible.value = false;
    } else message.error(assetText('tasks.failedToCreateTaskLabel') + res.message);
  } catch (error) { message.error(assetText('assets.failedToCreateTask')); }
  finally { riskSubmitLoading.value = false; }
};

// 标签管理相关逻辑已被移除（大盘数据不再支持绑定标签）

// C段详情弹窗 (提取为组件)
const cipDetailModalVisible = ref(false);
const currentCidrRecord = ref(null);

const openCidrDetail = (record) => {
  currentCidrRecord.value = record;
  cipDetailModalVisible.value = true;
};

onDeactivated(() => {
  cipDetailModalVisible.value = false;
  previewVisible.value = false;
  riskVisible.value = false;
  fingerModalVisible.value = false;
});
</script>

<style scoped>
.wih-api-content { display: flex; flex-direction: column; gap: 4px; overflow-wrap: anywhere; }
.wih-api-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }

.asset-site-count :deep(.ant-badge-count) { background-color: #1890ff; color: #fff; cursor: pointer; border-radius: 4px; padding: 0 6px; font-size: 12px; }

.asset-filter-operator { width: 85px; box-shadow: none; }
.asset-filter-operator-wide { width: 130px; }
.asset-status-field-wide :deep(.ant-form-item-control) { width: 270px; }

/* 页签数量徽标：与资产组详情页 ASM 视图保持同一视觉语言 */
.asm-tab-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
}

.asm-tab-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 16px;
  height: 14px;
  padding: 0 4px;
  border-radius: 7px;
  font-size: 10px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-weight: 500;
  background: var(--arl-bg-light);
  color: var(--arl-text-secondary);
  transition: all 0.2s;
}

.asm-tab-badge.has-data {
  background: color-mix(in srgb, var(--arl-theme-color) 12%, transparent);
  color: var(--arl-theme-color);
  font-weight: 600;
}

/* 全库 / 资产组范围的显式标注：两页 tab 结构一致，需明确各自数据范围避免误读 */
.scope-hint-line {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--arl-text-secondary);
}

.scope-hint-tag {
  flex-shrink: 0;
  padding: 1px 8px;
  border-radius: 10px;
  font-size: 12px;
  font-weight: 500;
  color: var(--arl-primary-color, #1890ff);
  background: var(--arl-primary-bg, rgba(24, 144, 255, 0.1));
  border: 1px solid var(--arl-primary-border, rgba(24, 144, 255, 0.3));
}
.site-header { line-height: 1.5; word-break: break-all; }
.site-img { width: 16px; height: 16px; margin-right: 8px; vertical-align: middle; }
.site-word { color: var(--arl-text-color) !important; font-size: 14px !important; margin-top: 4px; margin-bottom: 0; line-height: 1.5; }
.add-tag { color: var(--arl-text-color); cursor: pointer; font-size: 12px; margin-left: 8px; border: 1px dashed var(--arl-border-color); padding: 0 7px; border-radius: 2px; background: var(--arl-bg-light); transition: all 0.3s; }
.add-tag:hover {  }
.mt5 { margin-top: 5px; }

.scroll-x { background: transparent; border: none; padding: 8px; width: 100%; max-width: 600px; overflow-x: auto; overflow-y: hidden; }
.scroll-x pre { margin: 0; padding: 0; background-color: transparent; border: none; font-family: Consolas, Menlo, Courier, monospace; font-size: 12px; line-height: 1.5; color: var(--arl-text-color); opacity: 0.65; white-space: pre; word-wrap: normal; }
.scroll-x::-webkit-scrollbar { height: 6px; }
.scroll-x::-webkit-scrollbar-track { background: transparent; }
.scroll-x::-webkit-scrollbar-thumb { background-color: rgba(144, 147, 153, 0.3); border-radius: 4px; }
.scroll-x::-webkit-scrollbar-thumb:hover { background-color: rgba(144, 147, 153, 0.6); }

:deep(.ant-tabs-card-bar .ant-tabs-tab) { border-radius: 2px 2px 0 0 !important; margin-right: 4px !important; border: 1px solid var(--arl-border-color) !important; background: var(--arl-bg-light) !important; transition: all 0.3s; }
:deep(.ant-tabs-card-bar .ant-tabs-tab-active) { background: var(--arl-bg-white) !important; border-bottom-color: transparent !important;  font-weight: 500; }
:deep(.ant-tabs-tab:hover) {  }

.asset-search-page.is-virtual-mode {
  height: calc(100vh - 96px);
  min-height: auto !important;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.asset-search-page.is-virtual-mode :deep(.ant-table-wrapper) {
  flex: 1;
  min-height: 0;
  overflow: hidden;
}

.asset-engine-label { font-size: 13px; color: var(--arl-text-secondary); }
.asset-search-row-gap { row-gap: 10px; }
.asset-entry-tag { background: var(--arl-bg-light); color: var(--arl-text-color); border-color: var(--arl-border-color); }
.asset-field-hint { color: var(--arl-text-color); opacity: 0.45; margin-top: 2px; }
.asset-section-heading { font-weight: 600; font-size: 14px; margin-bottom: 12px; }
.asset-option-label { width: 120px; text-align: right; margin-right: 12px; font-weight: 500; }
.asset-option-value { flex: 1; color: var(--arl-text-color); }
.asset-risk-form { margin-top: 20px; }
.asset-risk-count { margin-left: 104px; color: var(--arl-text-color); margin-top: 16px; }
</style>
