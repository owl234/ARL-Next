<template>
  <div class="policy-detail-container">
    <div class="policy-detail-header">
      <a-button type="link" @click="goBack" class="back-link-btn">{{ pageText('pages.backToList') }}</a-button>
      <h2 class="page-title">{{ isEdit ? pageText('pages.editPolicyConfiguration') : pageText('pages.newScanPolicy') }}</h2>
    </div>

    <a-form :label-wrap="true" :model="policyForm" layout="vertical" class="policy-form-layout">
      <!-- 基础信息卡片 -->
      <a-card :bordered="false" class="policy-section-card basic-info-card">
        <div class="section-card-title">
          <span class="indicator-bar"></span>{{ pageText('tasks.basicSettings') }}
        </div>
        <a-row :gutter="16">
          <a-col :span="12">
            <a-form-item :label="pageText('tasks.policyName')" required>
              <a-input v-model:value="policyForm.name" :placeholder="pageText('pages.enterAPolicyNameEGComprehensiveDiscovery')" />
            </a-form-item>
          </a-col>
          <a-col :span="12">
            <a-form-item :label="pageText('pages.policyDescription')">
              <a-input v-model:value="policyForm.desc" :placeholder="pageText('pages.describeWhenToUseThisPolicy')" />
            </a-form-item>
          </a-col>
        </a-row>
      </a-card>

      <!-- 四维功能折叠配置面板 -->
      <a-collapse v-model:activeKey="activePanels" :bordered="false" class="policy-collapse-box">
        
        <!-- 1. 域名与资产发现 -->
        <a-collapse-panel key="1" :header="pageText('tasks.domainsAndAssetDiscovery')">
          <div class="panel-action-bar">
            <a-checkbox :checked="isAllDomainSelected" @change="toggleAllDomain">{{ pageText('pages.selectThisGroup') }}</a-checkbox>
            <a-input v-model:value="domainSearch" :placeholder="pageText('pages.searchDomainDiscoveryOptions')" class="search-input" allowClear>
              <template #suffix><search-outlined class="search-icon" /></template>
            </a-input>
          </div>

          <div class="feature-item-list">
            <!-- 域名查询插件 -->
            <div v-show="matchSearch(pageText('tasks.domainLookupPlugins'), domainSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.domain_config.dns_query_plugin">{{ pageText('tasks.domainLookupPlugins') }}</a-checkbox>
                <span class="feature-hint">{{ pageText('pages.collectSubdomainsFromExternalPassiveDnsServicesSuchAs') }}</span>
              </div>
            </div>

            <!-- 域名爆破 + 内联字典 -->
            <div v-show="matchSearch(pageText('tasks.subdomainBruteForce'), domainSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.domain_config.domain_brute">{{ pageText('tasks.subdomainBruteForce') }}</a-checkbox>
                <span class="feature-hint">{{ pageText('pages.discoverSubdomainsUsingHighSpeedDictionaryBasedDnsQueries') }}</span>
              </div>
              <div v-if="policyForm.domain_config.domain_brute" class="sub-config-box">
                <a-form-item :label="pageText('pages.discoveryDictionary')" required class="inline-form-item">
                  <a-select v-model:value="policyForm.domain_config.domain_brute_type" :placeholder="pageText('pages.selectADiscoveryDictionary')" class="page-width-280">
                    <a-select-option v-for="item in domainDicts" :key="item.name" :value="item.name">{{ item.name }}</a-select-option>
                  </a-select>
                </a-form-item>
              </div>
            </div>

            <!-- DNS字典智能生成 + 内联字典 -->
            <div v-show="matchSearch(pageText('tasks.dnsWordlistGeneration'), domainSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.domain_config.alt_dns">{{ pageText('pages.dnsMutationDiscoveryAltdns') }}</a-checkbox>
                <span class="feature-hint">{{ pageText('pages.generatePrefixAndNumericSuffixVariationsFromDiscoveredSubdomains') }}</span>
              </div>
              <div v-if="policyForm.domain_config.alt_dns" class="sub-config-box">
                <a-form-item :label="pageText('pages.subdomainMutationDictionary')" required class="inline-form-item">
                  <a-select v-model:value="policyForm.domain_config.alt_dns_dict" :placeholder="pageText('pages.selectAMutationDictionary')" class="page-width-280">
                    <a-select-option v-for="item in altDnsDicts" :key="item.name" :value="item.name">{{ item.name }}</a-select-option>
                  </a-select>
                </a-form-item>
              </div>
            </div>

            <!-- ARL 历史查询 -->
            <div v-show="matchSearch(pageText('tasks.arlHistorySearch'), domainSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.domain_config.arl_search">{{ pageText('pages.arlHistoricalAssets') }}</a-checkbox>
                <span class="feature-hint">{{ pageText('pages.findRelatedSubdomainRecordsInThisSystemSHistorical') }}</span>
              </div>
            </div>
          </div>
        </a-collapse-panel>

        <!-- 2. 端口与服务发现 -->
        <a-collapse-panel key="2" :header="pageText('tasks.portsAndServices')">
          <div class="panel-action-bar">
            <a-checkbox :checked="isAllIpSelected" @change="toggleAllIp">{{ pageText('pages.selectThisGroup') }}</a-checkbox>
            <a-input v-model:value="ipSearch" :placeholder="pageText('pages.searchPortAndServiceDiscoveryOptions')" class="search-input" allowClear>
              <template #suffix><search-outlined class="search-icon" /></template>
            </a-input>
          </div>

          <div class="feature-item-list">
            <!-- 跳过 CDN -->
            <div v-show="matchSearch(pageText('tasks.skipCdn'), ipSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.ip_config.skip_scan_cdn_ip">{{ pageText('pages.skipCdnIpScans') }}</a-checkbox>
                <span class="feature-hint">{{ pageText('pages.skipFullPortScansForIpsIdentifiedAsCdn') }}</span>
              </div>
            </div>

            <!-- 端口扫描 + 策略/自定义/高级配置内联 -->
            <div v-show="matchSearch(pageText('tasks.portScanning'), ipSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.ip_config.port_scan">{{ pageText('tasks.portScanning') }}</a-checkbox>
                <span class="feature-hint">{{ pageText('pages.probeTcpPortsOnTargetIpAssets') }}</span>
              </div>
              <div v-if="policyForm.ip_config.port_scan" class="sub-config-box">
                <a-row :gutter="16">
                  <a-col :span="12">
                    <a-form-item :label="pageText('pages.portScanPolicy')" required class="inline-form-item">
                      <a-select v-model:value="policyForm.ip_config.port_scan_type" :placeholder="pageText('tasks.selectAPortScanPolicy')">
                        <a-select-option value="custom">{{ pageText('tasks.customPorts') }}</a-select-option>
                        <a-select-option v-for="item in portDicts" :key="item.name" :value="item.name">{{ item.name }}</a-select-option>
                      </a-select>
                    </a-form-item>
                  </a-col>
                  <a-col :span="12" v-if="policyForm.ip_config.port_scan_type === 'custom'">
                    <a-form-item :label="pageText('pages.customPortRange')" required class="inline-form-item">
                      <a-input v-model:value="policyForm.ip_config.port_custom" :placeholder="pageText('pages.eG8044380008080')" />
                    </a-form-item>
                  </a-col>
                </a-row>

                <!-- 高级发包配置收展 -->
                <div class="advanced-toggle-row">
                  <a-button type="link" size="small" @click="showAdvancedPortConfig = !showAdvancedPortConfig" style="padding: 0;">
                    {{ showAdvancedPortConfig ? pageText('pages.hideAdvancedPortScanSettings') : pageText('pages.showAdvancedPortScanSettingsRateConcurrencyExcludedPorts') }}
                  </a-button>
                </div>

                <div v-if="showAdvancedPortConfig" class="advanced-params-grid">
                  <a-row :gutter="16">
                    <a-col :span="8">
                      <a-form-item :label="pageText('pages.hostTimeout')" class="inline-form-item">
                        <a-select v-model:value="policyForm.ip_config.host_timeout_type">
                          <a-select-option value="default">{{ pageText('pages.default900s') }}</a-select-option>
                          <a-select-option value="custom">{{ pageText('pages.customTimeout') }}</a-select-option>
                        </a-select>
                      </a-form-item>
                    </a-col>
                    <a-col :span="8" v-if="policyForm.ip_config.host_timeout_type === 'custom'">
                      <a-form-item :label="pageText('pages.timeoutInSeconds')" required class="inline-form-item">
                        <a-input-number v-model:value="policyForm.ip_config.host_timeout" :min="1" style="width: 100%;" />
                      </a-form-item>
                    </a-col>
                    <a-col :span="8">
                      <a-form-item :label="pageText('pages.probeParallelism')" class="inline-form-item">
                        <a-input-number v-model:value="policyForm.ip_config.port_parallelism" :min="1" style="width: 100%;" />
                      </a-form-item>
                    </a-col>
                    <a-col :span="8">
                      <a-form-item :label="pageText('pages.minimumPacketRate')" class="inline-form-item">
                        <a-input-number v-model:value="policyForm.ip_config.port_min_rate" :min="1" style="width: 100%;" />
                      </a-form-item>
                    </a-col>
                    <a-col :span="16">
                      <a-form-item :label="pageText('pages.excludedPorts')" class="inline-form-item">
                        <a-input v-model:value="policyForm.ip_config.exclude_ports" :placeholder="pageText('pages.excludePortsEG910091021100')" />
                      </a-form-item>
                    </a-col>
                  </a-row>
                </div>
              </div>
            </div>

            <!-- 服务识别 (双轨合并为单一选项) -->
            <div v-show="matchSearch(pageText('tasks.serviceDetection'), ipSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.ip_config.service_detection">
                  <span class="page-medium-label">{{ pageText('tasks.serviceDetection') }}</span>
                  <a-tag color="blue" class="page-start-gap">{{ pageText('pages.combinedDetection') }}</a-tag>
                </a-checkbox>
                <span class="feature-hint">{{ pageText('pages.runFingerprintAnalysisAndProtocolBasedDetectionForHigh') }}</span>
              </div>
            </div>

            <!-- 操作系统识别 -->
            <div v-show="matchSearch(pageText('tasks.osDetection'), ipSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.ip_config.os_detection">{{ pageText('tasks.osDetection') }}</a-checkbox>
                <span class="feature-hint">{{ pageText('pages.identifyTheTargetOperatingSystemUsingTcpIpStack') }}</span>
              </div>
            </div>

            <!-- SSL 证书获取 -->
            <div v-show="matchSearch(pageText('tasks.sslCertificates'), ipSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.ip_config.ssl_cert">{{ pageText('tasks.sslCertificates') }}</a-checkbox>
                <span class="feature-hint">{{ pageText('pages.collectCertificatesFromHttpsAndTlsPortsIncludingSubject') }}</span>
              </div>
            </div>
          </div>
        </a-collapse-panel>

        <!-- 3. Web 深度探测 -->
        <a-collapse-panel key="3" :header="pageText('tasks.webDiscovery')">
          <div class="panel-action-bar">
            <a-checkbox :checked="isAllSiteSelected" @change="toggleAllSite">{{ pageText('pages.selectThisGroup') }}</a-checkbox>
            <a-input v-model:value="siteSearch" :placeholder="pageText('pages.searchWebDiscoveryOptions')" class="search-input" allowClear>
              <template #suffix><search-outlined class="search-icon" /></template>
            </a-input>
          </div>

          <div class="feature-item-list">
            <!-- 站点与指纹识别 -->
            <div v-show="matchSearch(pageText('tasks.websiteDiscoveryAndFingerprinting'), siteSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.site_config.site_identify">{{ pageText('tasks.websiteDiscoveryAndFingerprinting') }}</a-checkbox>
                <span class="feature-hint">{{ pageText('pages.collectHttpHeadersPageTitlesServerBannersAndCms') }}</span>
              </div>
            </div>

            <!-- 文件泄露 + 内联字典 -->
            <div v-show="matchSearch(pageText('tasks.fileDisclosure'), siteSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.file_leak">{{ pageText('pages.directoryAndFileDisclosureChecks') }}</a-checkbox>
                <span class="feature-hint">{{ pageText('pages.checkWebsitesForBackupFilesExposedSourceCodeSensitive') }}</span>
              </div>
              <div v-if="policyForm.file_leak" class="sub-config-box">
                <a-form-item :label="pageText('pages.directoryAndFileDisclosureDictionary')" required class="inline-form-item">
                  <a-select v-model:value="policyForm.file_leak_dict" :placeholder="pageText('tasks.selectAFileDiscoveryWordlist')" class="page-width-280">
                    <a-select-option v-for="item in fileLeakDicts" :key="item.name" :value="item.name">{{ item.name }}</a-select-option>
                  </a-select>
                </a-form-item>
              </div>
            </div>

            <!-- 搜索引擎调用 -->
            <div v-show="matchSearch(pageText('tasks.searchEngines'), siteSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.site_config.search_engines">{{ pageText('pages.searchEngines360Bing') }}</a-checkbox>
                <span class="feature-hint">{{ pageText('pages.searchPublicSearchEnginesForPagesAndUrlsAssociated') }}</span>
              </div>
            </div>

            <!-- 站点静态爬虫 -->
            <div v-show="matchSearch(pageText('tasks.websiteCrawler'), siteSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.site_config.site_spider">{{ pageText('pages.websiteCrawler') }}</a-checkbox>
                <span class="feature-hint">{{ pageText('pages.followLinksFromAFormSrcAndSimilarPage') }}</span>
              </div>
            </div>

            <!-- WIH 调用 -->
            <div v-show="matchSearch(pageText('tasks.wihExtraction'), siteSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.site_config.web_info_hunter">{{ pageText('pages.wihJavascriptAnalysis') }}</a-checkbox>
                <span class="feature-hint">{{ pageText('pages.staticallyAnalyzeJavascriptForApiRoutesHiddenSubdomainsAnd') }}</span>
              </div>
            </div>

            <!-- Host 碰撞 -->
            <div v-show="matchSearch(pageText('tasks.hostCollision'), siteSearch)" class="feature-item-block">
              <div class="feature-switch-row">
                <a-checkbox v-model:checked="policyForm.site_config.findvhost">{{ pageText('pages.hostHeaderDiscovery') }}</a-checkbox>
                <span class="feature-hint">{{ pageText('pages.testDomainAndIpCombinationsForExposedVirtualHosts') }}</span>
              </div>
            </div>
          </div>
        </a-collapse-panel>

        <!-- 4. 漏洞与风险巡航 -->
        <a-collapse-panel key="4" :header="pageText('tasks.vulnerabilityAndRiskScanning')">
          <!-- Nuclei 独立开关与细粒度策略配置 -->
          <div class="feature-item-block" style="padding-bottom: 16px; border-bottom: 1px solid var(--arl-border-color); margin-bottom: 16px;">
            <div class="feature-switch-row">
              <a-checkbox v-model:checked="policyForm.site_config.nuclei_scan">
                <span class="page-medium-label">{{ pageText('pages.nucleiAutomatedScanning') }}</span>
                <a-tag color="purple" class="page-start-gap">{{ pageText('pages.communityAndCustomTemplates') }}</a-tag>
              </a-checkbox>
              <span class="feature-hint">{{ pageText('pages.runNucleiTemplateChecksAgainstDiscoveredWebsites') }}</span>
            </div>

            <!-- Nuclei 细粒度过滤与自建模板配置 (纯开关矩阵，极简交互) -->
            <div v-if="policyForm.site_config.nuclei_scan" class="sub-config-box" style="margin-top: 12px;">
              <a-row :gutter="16">
                <a-col :span="13">
                  <a-form-item :label="pageText('pages.scanSeverity')" class="inline-form-item">
                    <a-checkbox-group v-model:value="policyForm.site_config.nuclei_config.severity" :options="nucleiSeverityOptions" />
                  </a-form-item>
                </a-col>
                <a-col :span="11">
                  <a-form-item :label="pageText('pages.blocklistAndCustomTemplates')" class="inline-form-item">
                    <div style="display: flex; flex-direction: column; gap: 8px;">
                      <a-checkbox v-model:checked="policyForm.site_config.nuclei_config.exclude_blacklist">
                        {{ pageText('pages.excludeTheGlobalFalsePositiveBlocklistRecommended') }}
                      </a-checkbox>
                      <a-checkbox
                        :checked="policyForm.site_config.nuclei_config.custom_template_mode === 'all_enabled'"
                        @change="(e) => policyForm.site_config.nuclei_config.custom_template_mode = e.target.checked ? 'all_enabled' : 'none'"
                      >
                        {{ pageText('pages.loadAllEnabledCustomTemplatesRecommended') }}
                      </a-checkbox>
                    </div>
                  </a-form-item>
                </a-col>
              </a-row>
            </div>
          </div>

          <!-- PoC 插件配置子区域 -->
          <div class="plugin-sub-section">
            <div class="sub-section-header">
              <div class="sub-section-title">
                <span>{{ pageText('pages.pocVerificationPlugins') }}</span>
                <span class="count-tag">{{ pageText('pages.selected') }} {{ selectedPocCount }} / {{ pocList.length }}</span>
              </div>
              <div class="sub-section-actions">
                <a-checkbox
                  :indeterminate="isPocIndeterminate"
                  :checked="isAllPocSelected"
                  @change="toggleAllPoc"
                >
                  {{ pageText('pages.selectAllPocs') }}
                </a-checkbox>
                <a-input v-model:value="pocSearch" :placeholder="pageText('pages.searchPocPlugins')" class="search-input" allowClear>
                  <template #suffix><search-outlined class="search-icon" /></template>
                </a-input>
              </div>
            </div>

            <!-- 分页分片渲染：只挂载当前页的 DOM 节点，海量插件零卡顿 -->
            <template v-if="filteredPocList.length > 0">
              <a-row :gutter="[12, 12]" class="plugin-checkbox-grid">
                <a-col :span="12" v-for="(item, index) in paginatedPocList" :key="item.plugin_name">
                  <div class="plugin-item-checkbox" :class="{ 'is-checked': selectedPocNames.has(item.plugin_name) }">
                    <a-checkbox
                      :checked="selectedPocNames.has(item.plugin_name)"
                      @change="(e) => togglePocItem(item.plugin_name, e.target.checked)"
                    >
                      <span class="index-num">{{ (pocPagination.current - 1) * pocPagination.pageSize + index + 1 }}.</span>
                      <span class="plugin-name-text">{{ item.vul_name || item.plugin_name }}</span>
                    </a-checkbox>
                  </div>
                </a-col>
              </a-row>

              <div v-if="filteredPocList.length > pocPagination.pageSize" class="plugin-pagination-row">
                <a-pagination
                  v-model:current="pocPagination.current"
                  v-model:pageSize="pocPagination.pageSize"
                  :total="filteredPocList.length"
                  :pageSizeOptions="['40', '60', '100', '200']"
                  show-size-changer
                  show-quick-jumper
                  size="small"
                />
              </div>
            </template>
            <div v-else class="plugin-empty-box">
              <a-empty :description="pageText('tasks.noData')" :image="simpleImage" />
            </div>
          </div>

          <a-divider style="margin: 20px 0;" />

          <!-- 弱口令爆破子区域 -->
          <div class="plugin-sub-section">
            <div class="sub-section-header">
              <div class="sub-section-title">
                <span>{{ pageText('pages.credentialCheckPlugins') }}</span>
                <span class="count-tag">{{ pageText('pages.selected') }} {{ selectedBruteCount }} / {{ bruteList.length }}</span>
              </div>
              <div class="sub-section-actions">
                <a-checkbox
                  :indeterminate="isBruteIndeterminate"
                  :checked="isAllBruteSelected"
                  @change="toggleAllBrute"
                >
                  {{ pageText('pages.selectAllCredentialChecks') }}
                </a-checkbox>
                <a-input v-model:value="bruteSearch" :placeholder="pageText('pages.searchCredentialCheckPlugins')" class="search-input" allowClear>
                  <template #suffix><search-outlined class="search-icon" /></template>
                </a-input>
              </div>
            </div>

            <!-- 分页分片渲染：只挂载当前页的 DOM 节点，海量插件零卡顿 -->
            <template v-if="filteredBruteList.length > 0">
              <a-row :gutter="[12, 12]" class="plugin-checkbox-grid">
                <a-col :span="12" v-for="(item, index) in paginatedBruteList" :key="item.plugin_name">
                  <div class="plugin-item-checkbox" :class="{ 'is-checked': selectedBruteNames.has(item.plugin_name) }">
                    <a-checkbox
                      :checked="selectedBruteNames.has(item.plugin_name)"
                      @change="(e) => toggleBruteItem(item.plugin_name, e.target.checked)"
                    >
                      <span class="index-num">{{ (brutePagination.current - 1) * brutePagination.pageSize + index + 1 }}.</span>
                      <span class="plugin-name-text">{{ item.vul_name || item.plugin_name }}</span>
                    </a-checkbox>
                  </div>
                </a-col>
              </a-row>

              <div v-if="filteredBruteList.length > brutePagination.pageSize" class="plugin-pagination-row">
                <a-pagination
                  v-model:current="brutePagination.current"
                  v-model:pageSize="brutePagination.pageSize"
                  :total="filteredBruteList.length"
                  :pageSizeOptions="['40', '60', '100', '200']"
                  show-size-changer
                  show-quick-jumper
                  size="small"
                />
              </div>
            </template>
            <div v-else class="plugin-empty-box">
              <a-empty :description="pageText('tasks.noData')" :image="simpleImage" />
            </div>
          </div>
        </a-collapse-panel>

      </a-collapse>

      <!-- 底部保存/取消操作条 -->
      <div class="policy-footer-actions">
        <a-button type="primary" size="large" class="submit-btn" @click="submitPolicy" :loading="submitLoading">{{ pageText('pages.savePolicy') }}</a-button>
        <a-button size="large" class="cancel-btn" @click="goBack">{{ pageText('assets.cancel') }}</a-button>
      </div>
    </a-form>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';
import { ref, reactive, shallowRef, watch, onMounted, computed } from 'vue';
import request from '../utils/request';
import { message, Empty } from 'ant-design-vue';
import { SearchOutlined } from '@ant-design/icons-vue';
import { useRouter, useRoute } from 'vue-router';

const simpleImage = Empty.PRESENTED_IMAGE_SIMPLE;

const { t: pageText, locale: pageLocale } = useI18n({ useScope: 'global' });

const router = useRouter();
const route = useRoute();
const policyId = route.query._id;
const isEdit = !!policyId;

const goBack = () => router.push('/policy');

// 默认展开所有核心探测面板
const activePanels = ref(['1', '2', '3', '4']);
const submitLoading = ref(false);
const showAdvancedPortConfig = ref(false);

const initPolicyForm = () => ({
  name: '',
  desc: '',
  domain_config: {
    domain_brute: false,
    alt_dns: false,
    arl_search: false,
    dns_query_plugin: false,
    domain_brute_type: undefined,
    alt_dns_dict: undefined
  },
  ip_config: {
    port_scan: false,
    service_detection: false,
    os_detection: false,
    ssl_cert: false,
    skip_scan_cdn_ip: false,
    port_scan_type: undefined,
    port_custom: '',
    host_timeout_type: 'default',
    host_timeout: 900,
    port_parallelism: 32,
    port_min_rate: 60,
    exclude_ports: ''
  },
  site_config: {
    site_identify: false,
    search_engines: false,
    site_spider: false,
    findvhost: false,
    nuclei_scan: false,
    nuclei_config: {
      severity: ['critical', 'high', 'medium', 'low'],
      custom_template_mode: 'all_enabled',
      exclude_blacklist: true
    },
    web_info_hunter: false
  },
  file_leak: false,
  file_leak_dict: undefined
});

const nucleiSeverityOptions = [
  { get label() { return pageText('pages.critical'); }, value: 'critical' },
  { get label() { return pageText('pages.high'); }, value: 'high' },
  { get label() { return pageText('pages.medium'); }, value: 'medium' },
  { get label() { return pageText('pages.low'); }, value: 'low' },
  { get label() { return pageText('pages.info'); }, value: 'info' }
];

const policyForm = reactive(initPolicyForm());

const pocList = shallowRef([]);
const bruteList = shallowRef([]);
const selectedPocNames = ref(new Set());
const selectedBruteNames = ref(new Set());
const domainDicts = ref([]);
const altDnsDicts = ref([]);
const fileLeakDicts = ref([]);
const portDicts = ref([]);
const hasPocLoaded = ref(false);

const domainSearch = ref('');
const ipSearch = ref('');
const siteSearch = ref('');
const pocSearch = ref('');
const bruteSearch = ref('');

const matchSearch = (text, keyword) => {
  if (!keyword) return true;
  return text.toLowerCase().includes(keyword.toLowerCase().trim());
};

const normalizeDomainDict = (val) => {
  if (!val) return val;
  const map = {
    'big': 'domain_2w.txt',
    'test': 'domain_top300.txt',
    'domain_2w': 'domain_2w.txt',
    'domain_top300': 'domain_top300.txt'
  };
  return map[val] || val;
};

const normalizePortDict = (val) => {
  if (!val) return val;
  const map = {
    'top100': 'port_top100.txt',
    'top1000': 'port_top1000.txt',
    'bughunter': 'port_bughunter.txt',
    'port_top100': 'port_top100.txt',
    'port_top1000': 'port_top1000.txt',
    'port_bughunter': 'port_bughunter.txt'
  };
  return map[val] || val;
};

// ================= 面板 1：域名探测全选联动 =================
const isAllDomainSelected = computed(() => {
  const dc = policyForm.domain_config;
  return dc.domain_brute && dc.alt_dns && dc.arl_search && dc.dns_query_plugin;
});
const toggleAllDomain = (e) => {
  const val = e.target.checked;
  const dc = policyForm.domain_config;
  dc.domain_brute = dc.alt_dns = dc.arl_search = dc.dns_query_plugin = val;
};

// ================= 面板 2：端口与服务全选联动 =================
const isAllIpSelected = computed(() => {
  const ic = policyForm.ip_config;
  return ic.port_scan && ic.service_detection && ic.os_detection && ic.ssl_cert && ic.skip_scan_cdn_ip;
});
const toggleAllIp = (e) => {
  const val = e.target.checked;
  const ic = policyForm.ip_config;
  ic.port_scan = ic.service_detection = ic.os_detection = ic.ssl_cert = ic.skip_scan_cdn_ip = val;
};

// ================= 面板 3：Web 探测全选联动 =================
const isAllSiteSelected = computed(() => {
  const sc = policyForm.site_config;
  return sc.site_identify && sc.search_engines && sc.site_spider &&
      sc.findvhost && sc.web_info_hunter && policyForm.file_leak;
});
const toggleAllSite = (e) => {
  const val = e.target.checked;
  const sc = policyForm.site_config;
  sc.site_identify = sc.search_engines = sc.site_spider = sc.findvhost = sc.web_info_hunter = val;
  policyForm.file_leak = val;
};

// ================= 面板 4：漏洞插件过滤与全选联动 =================
const pocPagination = reactive({
  current: 1,
  pageSize: 60
});

const brutePagination = reactive({
  current: 1,
  pageSize: 60
});

watch(pocSearch, () => {
  pocPagination.current = 1;
}, { flush: 'sync' });

watch(() => pocPagination.pageSize, () => {
  pocPagination.current = 1;
}, { flush: 'sync' });

watch(bruteSearch, () => {
  brutePagination.current = 1;
}, { flush: 'sync' });

watch(() => brutePagination.pageSize, () => {
  brutePagination.current = 1;
}, { flush: 'sync' });

const filteredPocList = computed(() => {
  const kw = (pocSearch.value || '').toLowerCase().trim();
  if (!kw) return pocList.value;
  return pocList.value.filter(p =>
      (p.vul_name && p.vul_name.toLowerCase().includes(kw)) ||
      (p.plugin_name && p.plugin_name.toLowerCase().includes(kw))
  );
});

const filteredBruteList = computed(() => {
  const kw = (bruteSearch.value || '').toLowerCase().trim();
  if (!kw) return bruteList.value;
  return bruteList.value.filter(p =>
      (p.vul_name && p.vul_name.toLowerCase().includes(kw)) ||
      (p.plugin_name && p.plugin_name.toLowerCase().includes(kw))
  );
});

const paginatedPocList = computed(() => {
  const total = filteredPocList.value.length;
  if (!total) return [];
  const maxPage = Math.max(1, Math.ceil(total / pocPagination.pageSize));
  const page = Math.min(Math.max(1, pocPagination.current), maxPage);
  const start = (page - 1) * pocPagination.pageSize;
  return filteredPocList.value.slice(start, start + pocPagination.pageSize);
});

const paginatedBruteList = computed(() => {
  const total = filteredBruteList.value.length;
  if (!total) return [];
  const maxPage = Math.max(1, Math.ceil(total / brutePagination.pageSize));
  const page = Math.min(Math.max(1, brutePagination.current), maxPage);
  const start = (page - 1) * brutePagination.pageSize;
  return filteredBruteList.value.slice(start, start + brutePagination.pageSize);
});

const selectedPocCount = computed(() => {
  const sel = selectedPocNames.value;
  if (!sel.size) return 0;
  let count = 0;
  const list = pocList.value;
  for (let i = 0; i < list.length; i++) {
    if (sel.has(list[i].plugin_name)) count++;
  }
  return count;
});

const selectedBruteCount = computed(() => {
  const sel = selectedBruteNames.value;
  if (!sel.size) return 0;
  let count = 0;
  const list = bruteList.value;
  for (let i = 0; i < list.length; i++) {
    if (sel.has(list[i].plugin_name)) count++;
  }
  return count;
});

const pocSelectedFilteredCount = computed(() => {
  const list = filteredPocList.value;
  const sel = selectedPocNames.value;
  if (!list.length || !sel.size) return 0;
  let count = 0;
  for (let i = 0; i < list.length; i++) {
    if (sel.has(list[i].plugin_name)) count++;
  }
  return count;
});

const isAllPocSelected = computed(() => {
  const list = filteredPocList.value;
  return list.length > 0 && pocSelectedFilteredCount.value === list.length;
});

const isPocIndeterminate = computed(() => {
  const count = pocSelectedFilteredCount.value;
  return count > 0 && count < filteredPocList.value.length;
});

const bruteSelectedFilteredCount = computed(() => {
  const list = filteredBruteList.value;
  const sel = selectedBruteNames.value;
  if (!list.length || !sel.size) return 0;
  let count = 0;
  for (let i = 0; i < list.length; i++) {
    if (sel.has(list[i].plugin_name)) count++;
  }
  return count;
});

const isAllBruteSelected = computed(() => {
  const list = filteredBruteList.value;
  return list.length > 0 && bruteSelectedFilteredCount.value === list.length;
});

const isBruteIndeterminate = computed(() => {
  const count = bruteSelectedFilteredCount.value;
  return count > 0 && count < filteredBruteList.value.length;
});

const togglePocItem = (pluginName, checked) => {
  const next = new Set(selectedPocNames.value);
  if (checked) {
    next.add(pluginName);
  } else {
    next.delete(pluginName);
  }
  selectedPocNames.value = next;
};

const toggleBruteItem = (pluginName, checked) => {
  const next = new Set(selectedBruteNames.value);
  if (checked) {
    next.add(pluginName);
  } else {
    next.delete(pluginName);
  }
  selectedBruteNames.value = next;
};

const toggleAllPoc = (e) => {
  const checked = e?.target ? e.target.checked : !!e;
  const next = new Set(selectedPocNames.value);
  const targetList = filteredPocList.value;
  if (checked) {
    for (let i = 0; i < targetList.length; i++) {
      next.add(targetList[i].plugin_name);
    }
  } else {
    for (let i = 0; i < targetList.length; i++) {
      next.delete(targetList[i].plugin_name);
    }
  }
  selectedPocNames.value = next;
};

const toggleAllBrute = (e) => {
  const checked = e?.target ? e.target.checked : !!e;
  const next = new Set(selectedBruteNames.value);
  const targetList = filteredBruteList.value;
  if (checked) {
    for (let i = 0; i < targetList.length; i++) {
      next.add(targetList[i].plugin_name);
    }
  } else {
    for (let i = 0; i < targetList.length; i++) {
      next.delete(targetList[i].plugin_name);
    }
  }
  selectedBruteNames.value = next;
};

// ================= 生命周期：数据加载与编辑回填 =================
onMounted(async () => {
  try {
    const [pocRes, bruteRes, dictRes] = await Promise.all([
      request.get('/poc/', { params: { plugin_type: 'poc', size: 100000 } }),
      request.get('/poc/', { params: { plugin_type: 'brute', size: 100000 } }),
      request.get('/dictionary/list')
    ]);

    if (dictRes.code === 200 && dictRes.data) {
      domainDicts.value = dictRes.data.filter(item => item.category && item.category.includes(pageText('pages.subdomainDiscovery')) && !item.category.includes(pageText('pages.smart')));
      altDnsDicts.value = dictRes.data.filter(item => item.category && item.category.includes(pageText('pages.subdomainMutationDiscovery')));
      fileLeakDicts.value = dictRes.data.filter(item => item.category && (item.category.includes(pageText('pages.directoryAndFileDisclosure')) || item.category.includes(pageText('pages.directoryAndFileDisclosures'))));
      portDicts.value = dictRes.data.filter(item => item.category && item.category.includes(pageText('pages.portScanPolicy')) && item.name !== 'port_custom.txt' && item.name !== 'port_alive.txt');

      if (!isEdit) {
        if (domainDicts.value.length > 0) policyForm.domain_config.domain_brute_type = domainDicts.value[0].name;
        if (altDnsDicts.value.length > 0) policyForm.domain_config.alt_dns_dict = altDnsDicts.value[0].name;
        if (fileLeakDicts.value.length > 0) policyForm.file_leak_dict = fileLeakDicts.value[0].name;
        if (portDicts.value.length > 0) policyForm.ip_config.port_scan_type = portDicts.value[0].name;
      }
    }

    if (pocRes.code === 200) {
      const uniquePoc = new Map();
      (pocRes.items || []).forEach(p => {
        if (!uniquePoc.has(p.plugin_name)) {
          uniquePoc.set(p.plugin_name, Object.freeze({
            plugin_name: p.plugin_name,
            vul_name: p.vul_name || p.plugin_name
          }));
        }
      });
      pocList.value = Object.freeze(Array.from(uniquePoc.values()));
    }

    if (bruteRes.code === 200) {
      const uniqueBrute = new Map();
      (bruteRes.items || []).forEach(p => {
        if (!uniqueBrute.has(p.plugin_name)) {
          uniqueBrute.set(p.plugin_name, Object.freeze({
            plugin_name: p.plugin_name,
            vul_name: p.vul_name || p.plugin_name
          }));
        }
      });
      bruteList.value = Object.freeze(Array.from(uniqueBrute.values()));
    }

    if (pocRes.code === 200 && bruteRes.code === 200) {
      hasPocLoaded.value = true;
    }

    // 编辑模式回填
    if (isEdit) {
      const detailRes = await request.get('/policy/', { params: { _id: policyId } });
      if (detailRes.code === 200 && detailRes.items && detailRes.items.length > 0) {
        const data = detailRes.items[0];

        policyForm.name = data.name || '';
        policyForm.desc = data.desc || '';
        Object.assign(policyForm.domain_config, data.policy?.domain_config || {});
        Object.assign(policyForm.ip_config, data.policy?.ip_config || {});
        Object.assign(policyForm.site_config, data.policy?.site_config || {});
        if (!policyForm.site_config.nuclei_config) {
          policyForm.site_config.nuclei_config = {
            severity: ['critical', 'high', 'medium', 'low'],
            custom_template_mode: 'all_enabled',
            exclude_blacklist: true
          };
        } else {
          if (policyForm.site_config.nuclei_config.exclude_blacklist === undefined) {
            policyForm.site_config.nuclei_config.exclude_blacklist = true;
          }
          if (!policyForm.site_config.nuclei_config.custom_template_mode) {
            policyForm.site_config.nuclei_config.custom_template_mode = 'all_enabled';
          }
        }

        // 字典历史别名归一化回填
        if (policyForm.domain_config.domain_brute_type) {
          policyForm.domain_config.domain_brute_type = normalizeDomainDict(policyForm.domain_config.domain_brute_type);
        }
        if (policyForm.ip_config.port_scan_type) {
          policyForm.ip_config.port_scan_type = normalizePortDict(policyForm.ip_config.port_scan_type);
        }

        // 统一双轨服务识别回填：若历史开启了 npoc_service_detection 或 service_detection，均视为开启
        const isSvcDetect = !!(data.policy?.ip_config?.service_detection || data.policy?.npoc_service_detection);
        policyForm.ip_config.service_detection = isSvcDetect;

        // 文件泄露回填
        policyForm.file_leak = !!(data.policy?.file_leak || data.policy?.site_config?.file_leak);
        if (data.policy?.file_leak_dict || data.policy?.site_config?.file_leak_dict) {
          policyForm.file_leak_dict = data.policy.file_leak_dict || data.policy.site_config?.file_leak_dict;
        }

        // 若配置了自定义高级发包参数，自动展开高级参数面板
        if (policyForm.ip_config.host_timeout_type === 'custom' || policyForm.ip_config.exclude_ports) {
          showAdvancedPortConfig.value = true;
        }

        // PoC 插件勾选回填：仅回填当前存在的有效插件，避免历史已废弃插件导致保存报错
        const validPocSet = new Set(pocList.value.map(p => p.plugin_name));
        const loadedPocSet = new Set();
        data.policy?.poc_config?.forEach(p => {
          if (p.enable && validPocSet.has(p.plugin_name)) loadedPocSet.add(p.plugin_name);
        });
        selectedPocNames.value = loadedPocSet;

        // 弱口令插件勾选回填：仅回填当前存在的有效插件
        const validBruteSet = new Set(bruteList.value.map(p => p.plugin_name));
        const loadedBruteSet = new Set();
        data.policy?.brute_config?.forEach(p => {
          if (p.enable && validBruteSet.has(p.plugin_name)) loadedBruteSet.add(p.plugin_name);
        });
        selectedBruteNames.value = loadedBruteSet;
      } else {
        message.error(pageText('pages.policyNotFoundOrAlreadyDeleted'));
        router.push('/policy');
        return;
      }
    }
  } catch (e) {
    message.error(pageText('pages.failedToLoadPolicies'));
  }
});

// ================= 提交表单 =================
const submitPolicy = async () => {
  if (isEdit && !hasPocLoaded.value) {
    return message.error(pageText('pages.pluginDataIsStillLoadingWaitBeforeSaving'));
  }
  if (!policyForm.name?.trim()) return message.warning(pageText('pages.policyNameCannotBeEmpty'));

  // 条件校验：仅在勾选对应功能时，校验字典必选项
  if (policyForm.domain_config.domain_brute && !policyForm.domain_config.domain_brute_type) {
    return message.warning(pageText('pages.selectADictionaryWhenSubdomainDiscoveryIsEnabled'));
  }
  if (policyForm.domain_config.alt_dns && !policyForm.domain_config.alt_dns_dict) {
    return message.warning(pageText('pages.selectAMutationDictionaryWhenSubdomainMutationDiscoveryIs'));
  }
  if (policyForm.ip_config.port_scan) {
    if (!policyForm.ip_config.port_scan_type) {
      return message.warning(pageText('pages.selectAScanPolicyWhenPortScanningIsEnabled'));
    }
    if (policyForm.ip_config.port_scan_type === 'custom' && !policyForm.ip_config.port_custom?.trim()) {
      return message.warning(pageText('pages.enterAPortRangeForTheCustomPortPolicy'));
    }
    if (policyForm.ip_config.host_timeout_type === 'custom') {
      if (!policyForm.ip_config.host_timeout || policyForm.ip_config.host_timeout < 1) {
        return message.warning(pageText('pages.customHostTimeoutMustBeAtLeast1Second'));
      }
    }
  }
  if (policyForm.file_leak && !policyForm.file_leak_dict) {
    return message.warning(pageText('pages.selectADictionaryWhenFileDisclosureChecksAreEnabled'));
  }

  submitLoading.value = true;
  try {
    const pocNameMap = new Map((pocList?.value || []).map(p => [p.plugin_name, p.vul_name]));
    const poc_config = [];
    const pocSet = (typeof selectedPocNames !== 'undefined' && selectedPocNames?.value) ? selectedPocNames.value : null;
    if (pocSet && pocSet.size > 0) {
      for (const name of pocSet) {
        if (pocNameMap.has(name)) {
          poc_config.push({
            plugin_name: name,
            vul_name: pocNameMap.get(name) || name,
            enable: true
          });
        }
      }
    } else if (Array.isArray(pocList?.value)) {
      for (const p of pocList.value) {
        if (p?.enable && p.plugin_name) {
          poc_config.push({
            plugin_name: p.plugin_name,
            vul_name: p.vul_name || p.plugin_name,
            enable: true
          });
        }
      }
    }

    const bruteNameMap = new Map((bruteList?.value || []).map(p => [p.plugin_name, p.vul_name]));
    const brute_config = [];
    const bruteSet = (typeof selectedBruteNames !== 'undefined' && selectedBruteNames?.value) ? selectedBruteNames.value : null;
    if (bruteSet && bruteSet.size > 0) {
      for (const name of bruteSet) {
        if (bruteNameMap.has(name)) {
          brute_config.push({
            plugin_name: name,
            vul_name: bruteNameMap.get(name) || name,
            enable: true
          });
        }
      }
    } else if (Array.isArray(bruteList?.value)) {
      for (const p of bruteList.value) {
        if (p?.enable && p.plugin_name) {
          brute_config.push({
            plugin_name: p.plugin_name,
            vul_name: p.vul_name || p.plugin_name,
            enable: true
          });
        }
      }
    }

    const policyData = {
      name: policyForm.name.trim(),
      desc: policyForm.desc || '',
      policy: {
        domain_config: { ...policyForm.domain_config },
        ip_config: { ...policyForm.ip_config },
        npoc_service_detection: policyForm.ip_config.service_detection,
        site_config: { ...policyForm.site_config },
        file_leak: policyForm.file_leak,
        file_leak_dict: policyForm.file_leak_dict || 'file_top_2000.txt',
        poc_config,
        brute_config
      }
    };

    let res;
    if (isEdit) {
      res = await request.post('/policy/edit/', {
        policy_id: policyId,
        policy_data: policyData
      });
    } else {
      res = await request.post('/policy/add/', policyData);
    }

    if (res.code === 200) {
      message.success(isEdit ? pageText('pages.policyUpdated') : pageText('pages.policyCreated'));
      router.push('/policy');
    } else {
      message.error((isEdit ? pageText('pages.edit') : pageText('pages.create')) + pageText('pages.failed') + (res.message || pageText('tasks.unknownError')));
    }
  } catch (error) {
    message.error(pageText('pages.requestFailedChangesWereNotSaved'));
  } finally {
    submitLoading.value = false;
  }
};
</script>

<style scoped>
.policy-detail-container {
  background-color: var(--arl-bg-layout);
  padding: 24px;
  min-height: calc(100vh - 64px);
  position: relative;
}

.policy-detail-header {
  display: flex;
  align-items: center;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--arl-border-color);
  padding-bottom: 16px;
}

.back-link-btn {
  padding: 0;
  margin-right: 16px;
  font-size: 14px;
  color: var(--arl-theme-color);
}

.page-title {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  color: var(--arl-text-color);
}

.policy-form-layout {
  max-width: 1040px;
  margin: 0 auto;
}

.policy-section-card {
  background: var(--arl-bg-card, #ffffff);
  border-radius: 8px;
  margin-bottom: 20px;
  border: 1px solid var(--arl-border-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.section-card-title {
  display: flex;
  align-items: center;
  font-size: 15px;
  font-weight: 600;
  color: var(--arl-text-color);
  margin-bottom: 16px;
}

.indicator-bar {
  display: inline-block;
  width: 4px;
  height: 16px;
  background-color: var(--arl-theme-color, #1890ff);
  border-radius: 2px;
  margin-right: 8px;
}

.policy-collapse-box {
  background: transparent;
  margin-bottom: 24px;
}

:deep(.ant-collapse-item) {
  background: var(--arl-bg-card, #ffffff);
  border-radius: 8px !important;
  margin-bottom: 16px;
  border: 1px solid var(--arl-border-color) !important;
  overflow: hidden;
  transition: border-color 0.25s ease, box-shadow 0.25s ease;
}

:deep(.ant-collapse-item.ant-collapse-item-active) {
  border-color: color-mix(in srgb, var(--arl-theme-color) 45%, var(--arl-border-color)) !important;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.12);
}

:deep(.ant-collapse-header) {
  font-weight: 600;
  font-size: 15px;
  background-color: var(--arl-bg-card, #ffffff) !important;
  padding: 14px 20px !important;
  color: var(--arl-text-color) !important;
  border-bottom: 1px solid transparent;
  transition: background-color 0.2s ease, border-color 0.2s ease;
}

:deep(.ant-collapse-item.ant-collapse-item-active > .ant-collapse-header) {
  border-bottom: 1px solid var(--arl-border-color);
}

:deep(.ant-collapse-content) {
  background-color: var(--arl-bg-card, #ffffff) !important;
  color: var(--arl-text-color) !important;
  border-top: none !important;
}

:deep(.ant-collapse-content-box) {
  padding: 16px 20px !important;
}

.panel-action-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding-bottom: 12px;
  border-bottom: 1px solid var(--arl-border-color);
}

.search-input {
  width: 240px;
}

.search-icon {
  color: var(--arl-text-color);
  opacity: 0.35;
}

.feature-item-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.feature-item-block {
  display: flex;
  flex-direction: column;
}

.feature-switch-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.feature-hint {
  color: var(--arl-text-color);
  opacity: 0.55;
  font-size: 13px;
  margin-left: 8px;
}

.sub-config-box {
  background-color: var(--arl-bg-subcard, #f8f9fa);
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
  padding: 14px 18px;
  margin-top: 10px;
  margin-left: 24px;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.05);
}

.inline-form-item {
  margin-bottom: 0 !important;
}

.advanced-toggle-row {
  margin-top: 12px;
  margin-bottom: 6px;
}

.advanced-params-grid {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--arl-border-color);
}

.plugin-sub-section {
  display: flex;
  flex-direction: column;
}

.sub-section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.sub-section-title {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 14px;
  font-weight: 600;
}

.count-tag {
  font-size: 12px;
  font-weight: 500;
  padding: 2px 10px;
  background: color-mix(in srgb, var(--arl-theme-color) 14%, transparent);
  border: 1px solid color-mix(in srgb, var(--arl-theme-color) 32%, transparent);
  border-radius: 12px;
  color: var(--arl-theme-color);
  letter-spacing: 0.3px;
}

.sub-section-actions {
  display: flex;
  align-items: center;
  gap: 16px;
}

.plugin-checkbox-grid {
  max-height: 380px;
  overflow-y: auto;
  padding-right: 6px;
}

.plugin-pagination-row {
  display: flex;
  justify-content: flex-end;
  margin-top: 14px;
  padding-top: 10px;
  border-top: 1px dashed var(--arl-border-color);
}

.plugin-empty-box {
  padding: 32px 0;
  display: flex;
  justify-content: center;
  align-items: center;
}

.plugin-item-checkbox {
  padding: 6px 10px;
  border-radius: 6px;
  transition: all 0.2s ease;
  border: 1px solid transparent;
  cursor: pointer;
}

.plugin-item-checkbox :deep(.ant-checkbox-wrapper) {
  width: 100%;
  display: inline-flex;
  align-items: center;
}

.plugin-item-checkbox:hover {
  background-color: rgba(255, 255, 255, 0.05);
}

:not(body.dark-mode) .plugin-item-checkbox:hover {
  background-color: rgba(0, 0, 0, 0.035);
}

.plugin-item-checkbox.is-checked {
  background-color: color-mix(in srgb, var(--arl-theme-color) 8%, transparent);
  border-color: color-mix(in srgb, var(--arl-theme-color) 22%, transparent);
}

.plugin-item-checkbox.is-checked .plugin-name-text {
  color: var(--arl-text-color);
  font-weight: 500;
}

.index-num {
  opacity: 0.45;
  margin-right: 4px;
  font-size: 12px;
}

.plugin-name-text {
  font-size: 13px;
}

.policy-footer-actions {
  position: sticky;
  bottom: 16px;
  z-index: 99;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  padding: 10px 24px;
  margin: 32px auto 16px auto;
  width: fit-content;
  background: color-mix(in srgb, var(--arl-bg-card, #141414) 85%, transparent);
  border: 1px solid var(--arl-border-color);
  border-radius: 28px;
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.25);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.submit-btn {
  width: 140px;
  height: 38px;
  font-size: 14px;
  font-weight: 500;
  border-radius: 20px;
}

.cancel-btn {
  width: 100px;
  height: 38px;
  font-size: 14px;
  border-radius: 20px;
}

.page-width-280 { width: 280px; }
.page-medium-label { font-weight: 500; }
.page-start-gap { margin-left: 8px; }
</style>