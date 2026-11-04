<template>
  <div class="arl-page-container" :class="{ 'page-wide-text': pageLocale !== 'zh-CN' }">
    <!-- 未保存改动常驻提示：让"改过但没存"成为可见状态，而非点保存时才发现 -->
    <a-alert
      v-if="hasUnsavedChanges"
      type="warning"
      show-icon
      banner
      style="margin-bottom: 12px; border-radius: 6px;"
    >
      <template #message>
        <strong>{{ pageText('pages.unsavedSettingsCount', { count: unsavedCount }) }}</strong>
        <a @click="goToFirstDirty">{{ pageText('pages.goToUnsavedSettings') }}</a>
        {{ pageText('pages.saveEachChangeBeforeLeavingThisPage') }}
      </template>
    </a-alert>
    <!-- 设置项搜索：输入关键词直接定位到目标 Tab 并高亮，避免在 7 个 Tab 间盲翻 -->
    <div class="arl-settings-search">
      <a-input-search
        v-model:value="settingsKeyword"
        :placeholder="pageText('pages.searchSettingsEGFofaConcurrencyBlocklistWebhookOr')"
        allow-clear
        style="max-width: 520px;"
      >
        <template #prefix><span style="opacity: 0.45;">🔍</span></template>
      </a-input-search>
      <span v-if="settingsKeyword.trim()" class="arl-search-count">
        {{ pageText('pages.settingsMatchCount', { count: settingsSearchResults.length }) }}
      </span>
      <a v-if="settingsKeyword.trim()" @click="settingsKeyword = ''" class="page-small-text">{{ pageText('pages.clear') }}</a>
    </div>

    <!-- 搜索结果：点击直达对应 Tab 并高亮目标设置项 -->
    <div v-if="settingsKeyword.trim()" class="arl-search-panel">
      <div v-if="settingsSearchResults.length === 0" class="arl-search-empty">
        {{ pageText('pages.noMatchingSettingsTryFofaConcurrencyBlocklistWebhookProxy') }}
      </div>
      <div
        v-for="item in settingsSearchResults"
        :key="item.tab + item.label"
        class="arl-search-item"
        @click="jumpToSetting(item)"
      >
        <div class="arl-search-item-main">
          <span class="arl-search-item-label">{{ item.label }}</span>
          <span class="arl-search-item-desc">{{ item.desc }}</span>
        </div>
        <a-tag color="blue" style="margin: 0;">{{ item.tabLabel }}</a-tag>
      </div>
    </div>

    <!-- 全局凭据总览：内容跨「资产测绘与情报 / 通知与回调 / 高级扫描」三个 Tab，
         故置于 Tab 之外。默认折叠为一行摘要，需要时展开——避免每次进入设置页
         都被 12 项明细占据首屏。 -->
    <div v-if="credentialOverview.length" class="arl-global-cred">
      <div class="arl-cred-summary" @click="credExpanded = !credExpanded">
        <span class="arl-cred-chevron">{{ credExpanded ? '▾' : '▸' }}</span>
        <span class="arl-cred-summary-title">{{ pageText('pages.credentialConfigurationStatus') }}</span>
        <a-tag :color="missingRequiredCredentials.length ? 'red' : 'green'" style="margin: 0;">
          {{ pageText('pages.configuredCredentialsCount', { configured: configuredCredentialCount, total: credentialOverview.length }) }}
        </a-tag>
        <span v-if="missingRequiredCredentials.length" class="arl-cred-alert">
          {{ pageText('pages.missingCredentials', { names: missingRequiredCredentials.map(c => c.label).join(pageLocale !== 'zh-CN' ? ', ' : '、') }) }}
        </span>
        <span v-else class="arl-cred-ok">{{ pageText('pages.allRequiredCredentialsAreConfigured') }}</span>
        <a class="arl-cred-toggle">{{ credExpanded ? pageText('pages.collapse') : pageText('pages.showDetails') }}</a>
      </div>

      <div v-show="credExpanded" class="arl-cred-body">
        <div class="arl-cred-hint">
          {{ pageText('pages.credentialStatusHelp') }}
        </div>
        <a-row :gutter="[8, 8]" style="margin-top: 12px;">
          <a-col :span="8" v-for="item in credentialOverview" :key="item.key">
            <div class="arl-cred-item" :class="item.configured ? 'is-ok' : 'is-missing'">
              <span class="arl-cred-name">{{ item.label }}</span>
              <a-tag :color="item.configured ? 'green' : (item.required ? 'red' : 'default')" style="margin: 0;">
                {{ item.configured ? pageText('pages.configured') : (item.required ? pageText('pages.notConfiguredRequired') : pageText('pages.notConfiguredOptional')) }}
              </a-tag>
            </div>
          </a-col>
        </a-row>
      </div>
    </div>

    <a-tabs v-model:activeKey="activeKey">
      <!-- 统一字典与规则库 Tab -->
      <a-tab-pane key="api_config" :tab="tabTitle(pageText('pages.assetDiscoveryAndIntelligence'), Object.keys(pendingByGroup.api_config).length > 0)">
        <div style="max-width: 1000px; padding-bottom: 40px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <span style="color: var(--arl-text-color); opacity: 0.45;">
              {{ pageText('pages.manageApiCredentialsForExternalIntelligenceAndSearchServices') }}
            </span>
            <a-button
              type="primary"
              :class="{ 'arl-dirty-btn': Object.keys(pendingByGroup.api_config).length > 0 }"
              @click="saveGeneralConfig('api_config', pageText('pages.apiConfigurationSaved'))"
              :loading="generalSaveLoading"
            >
              {{ pageText('pages.saveApiConfiguration') }}
              <a-badge
                v-if="Object.keys(pendingByGroup.api_config).length > 0"
                :count="Object.keys(pendingByGroup.api_config).length"
                :offset="[8, -8]"
                color="#faad14"
              />
            </a-button>
          </div>
          
          <a-spin :spinning="generalLoading">
            <a-form :label-wrap="true" layout="vertical">

              <!-- 1. 空间测绘情报 -->
              <a-card data-setting-anchor="fofa" :title="pageText('pages.assetDiscoveryIntelligenceFofa')" size="small" class="page-config-card">
                <a-row :gutter="24">
                  <a-col :span="12">
                    <a-form-item label="FOFA URL" style="margin-bottom: 12px;">
                      <a-input v-model:value="generalForm.fofa_url" :placeholder="pageText('pages.eGHttpsFofaInfo')" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item label="FOFA KEY" style="margin-bottom: 12px;">
                      <a-input-password v-model:value="generalForm.fofa_key" :placeholder="pageText('pages.enterYourFofaApiKey')" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item :label="pageText('pages.maximumQueryPages')" class="page-flush-bottom">
                      <a-input-number v-model:value="generalForm.fofa_max_page" :min="1" style="width: 100%" />
                    </a-form-item>
                  </a-col>
                  <a-col :span="12">
                    <a-form-item :label="pageText('pages.resultsPerPage')" class="page-flush-bottom">
                      <a-input-number v-model:value="generalForm.fofa_page_size" :min="1" style="width: 100%" />
                    </a-form-item>
                  </a-col>
                </a-row>
              </a-card>

              <a-row :gutter="16">
                <!-- 2. 企业与代码监控 (左半边) -->
                <a-col :span="12">
                  <a-card data-setting-anchor="tyc" :title="pageText('pages.enterpriseDiscoveryCredentialsTianyanchaApi')" size="small" class="page-config-card-min-height">
                    <template #extra>
                      <a-tooltip :title="pageText('pages.optionalEnablesInvestmentRelationshipTraversalAndCrossCheckingAgainst')">
                        <info-circle-outlined style="color: #bfbfbf;" />
                      </a-tooltip>
                    </template>
                    <a-form-item :label="pageText('pages.tianyanchaIdXTycid')" class="page-field-spacing">
                      <a-input v-model:value="generalForm.tyc_id" :placeholder="pageText('pages.enterYourTianyanchaId')" />
                    </a-form-item>
                    <a-form-item :label="pageText('pages.tianyanchaTokenXAuthToken')" class="page-flush-bottom">
                      <a-input-password v-model:value="generalForm.tyc_token" :placeholder="pageText('pages.enterAJwtToken')" />
                    </a-form-item>
                  </a-card>
                </a-col>

                <!-- 3. 代码与搜索引擎 (右半边) -->
                <a-col :span="12">
                  <a-card data-setting-anchor="search_cookie" :title="pageText('pages.searchEnginesAndOpenSourceIntelligence')" size="small" class="page-config-card-fixed">
                    <a-form-item data-setting-anchor="github_token" :label="pageText('pages.githubTokenMonitoringTasks')" class="page-field-spacing">
                      <a-input-password v-model:value="generalForm.github_token" :placeholder="pageText('pages.enterYourGithubPat')" />
                    </a-form-item>
                    <a-form-item :label="pageText('pages.360SearchCookieAntiBotAccess')" class="page-flush-bottom">
                      <a-input-password v-model:value="generalForm.so_search_cookie" placeholder="so_search_cookie" />
                    </a-form-item>
                  </a-card>
                </a-col>
              </a-row>

              <!-- 单独一行放必应，如果上面放不下 -->
              <a-card size="small" style="margin-bottom: 16px; border-radius: 6px;">
                 <a-form-item :label="pageText('pages.bingSearchCookieBingSearchCookie')" class="page-flush-bottom">
                   <a-input-password v-model:value="generalForm.bing_search_cookie" :placeholder="pageText('pages.enterABingSearchCookie')" />
                 </a-form-item>
              </a-card>


              <!-- 4. 插件配置 -->
              <a-card data-setting-anchor="query_plugin" :title="pageText('pages.domainCollectionPluginConfigurationQueryPlugin')" size="small" class="page-rounded">
                <div style="background: var(--arl-bg-light); border-radius: 4px; padding: 12px;">
                  <a-row :gutter="[12, 12]">
                    <a-col :span="8" v-for="(conf, pluginName) in generalForm.query_plugin_config" :key="pluginName">
                      <div style="border: 1px solid var(--arl-border-color); background: var(--arl-bg-white); padding: 12px; border-radius: 4px; min-height: 110px; position: relative;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                          <a style="font-weight: 600; text-transform: uppercase; ">{{ pluginName }}</a>
                          <a-switch v-model:checked="conf.enable" size="small" />
                        </div>
                        
                        <a-input 
                          v-if="conf.hasOwnProperty('api_key')" 
                          v-model:value="conf.api_key" 
                          placeholder="API Key" 
                          size="small" 
                        />
                        <div v-if="pluginName === 'hunter_qax'" style="margin-top: 8px; display: flex; gap: 8px;">
                          <a-input-number v-model:value="conf.max_page" :placeholder="pageText('pages.maxPagesPlaceholder')" size="small" class="page-flex-input" />
                          <a-input-number v-model:value="conf.page_size" :placeholder="pageText('pages.pageSizePlaceholder')" size="small" class="page-flex-input" />
                        </div>
                        <div v-if="pluginName === 'certspotter'" style="margin-top: 8px;">
                          <a-input-number v-model:value="conf.max_page" :placeholder="pageText('pages.maxPagesPlaceholder')" size="small" class="page-full-width-input" />
                        </div>
                        <a-input 
                          v-if="conf.hasOwnProperty('quake_token')" 
                          v-model:value="conf.quake_token" 
                          placeholder="Quake Token" 
                          size="small"
                          style="margin-top: 8px;"
                        />
                        <div v-if="pluginName === 'passivetotal'" style="margin-top: 8px; display: flex; flex-direction: column; gap: 8px;">
                          <a-input v-model:value="conf.auth_email" :placeholder="pageText('pages.authEmailPlaceholder')" size="small" />
                          <a-input v-model:value="conf.auth_key" :placeholder="pageText('pages.authKeyPlaceholder')" size="small" />
                        </div>
                      </div>
                    </a-col>
                  </a-row>
                </div>
              </a-card>

            </a-form>
          </a-spin>
        </div>
      </a-tab-pane>
      <a-tab-pane key="dictionary" :tab="tabTitle(pageText('pages.dictionariesAndRules'), false)">
        <a-tabs v-model:activeKey="dictSubTab" type="card" class="dict-sub-tabs" style="margin-bottom: 16px;">
          <a-tab-pane key="dict" :tab="pageText('pages.textDictionaries')">
            <a-spin :spinning="loading || bruteLoading">
            <div style="display: flex; gap: 0; height: calc(100vh - 180px); min-height: 580px; border-radius: 12px; overflow: hidden; box-shadow: 0 12px 48px rgba(0, 0, 0, 0.08), 0 4px 16px rgba(0, 0, 0, 0.04); border: 1px solid rgba(0,0,0,0.05); background: var(--arl-bg-white);"> <!-- 左侧语义化菜单与独立滚动 -->
            <div style="width: 256px; flex-shrink: 0; border-right: 1px solid var(--arl-border-color); background: var(--arl-bg-white); display: flex; flex-direction: column;">
              <div style="padding: 16px; border-bottom: 1px solid var(--arl-border-color); display: flex; align-items: center; min-height: 64px; box-sizing: border-box;">
                <span class="page-panel-heading">{{ pageText('pages.dictionaryCategories') }}</span>
              </div>
              <div class="hide-scrollbar" style="flex: 1; overflow-y: auto;">
                <div style="padding: 12px 8px; display: flex; flex-direction: column; gap: 4px;">
                  <div
                    v-for="group in treeData" :key="group.key"
                    class="custom-list-item"
                    :class="{ 'is-active': selectedCategoryKeys.includes(group.key) }"
                    @click="handleCategorySelect({ key: group.key })"
                  >
                    <div style="display: flex; align-items: center; gap: 8px;">
                      <span style="opacity: 0.9;">🗂️</span>
                      <span class="dict-title" style="font-weight: 600;">{{ group.title }}</span>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 2. 中间：字典列表 -->
            <div style="width: 250px; flex-shrink: 0; border-right: 1px solid var(--arl-border-color); background: var(--arl-bg-white); display: flex; flex-direction: column;">
              <div style="padding: 16px; border-bottom: 1px solid var(--arl-border-color); min-height: 64px; box-sizing: border-box;">
                <div style="display: flex; gap: 8px;">
                  <a-input-search v-model:value="menuSearch" :placeholder="pageText('pages.searchDictionariesInThisCategory')" class="page-search-field" />
                  <a-button type="primary" @click="openCreateDictDrawer" class="page-icon-padding" :title="pageText('pages.newDictionary')">
                    <template #icon><span style="margin-right:0px;">➕</span></template>
                  </a-button>
                </div>
              </div>
              <div class="hide-scrollbar" style="flex: 1; overflow-y: auto; padding: 12px 8px;">
                <div v-if="currentFilteredDicts.length === 0" style="padding: 48px 24px; text-align: center; color: var(--arl-text-color); opacity: 0.65; display: flex; flex-direction: column; align-items: center; gap: 12px;">
                  <span style="font-size: 32px; opacity: 0.8;">📭</span>
                  <span class="page-label">{{ pageText('pages.noDictionariesInThisCategory') }}</span>
                  <span class="page-quiet-help">{{ pageText('pages.selectNewDictionaryAboveOrChooseAnotherCategory') }}</span>
                </div>
                <div style="display: flex; flex-direction: column; gap: 4px;">
                  <div
                    v-for="item in currentFilteredDicts" :key="item.key"
                    class="custom-list-item"
                    :class="{ 'is-active': unifiedSelectedKeys.includes(item.key) }"
                    @click="handleUnifiedSelect([item.key])"
                  >
                    <div style="display: flex; align-items: flex-start; gap: 8px;">
                      <span style="font-size: 16px; margin-top: 2px; opacity: 0.9;">📄</span>
                      <div style="display: flex; flex-direction: column; gap: 4px; flex: 1; min-width: 0;">
                        <span class="dict-title" style="white-space: nowrap; overflow: hidden; text-overflow: ellipsis; font-weight: 500;">{{ item.mainTitle }}</span>
                        <div style="display: flex; justify-content: space-between; align-items: center;">
                          <span class="dict-subtitle">{{ item.subTitle }}</span>
                          <div style="display: flex; gap: 4px; align-items: center;">
                            <a-tag v-if="item.is_builtin" color="purple" class="page-tiny-tag">{{ pageText('pages.builtIn') }}</a-tag>
                            <span class="dict-badge">txt</span>
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>

            <!-- 右侧统一操作面板 -->
            <div style="flex: 1; overflow: hidden; display: flex; flex-direction: column; min-width: 0; background: var(--arl-bg-white); position: relative;">

              <!-- 未选中时占位（健康看板） -->
              <div v-if="!unifiedSelectedType" class="health-dashboard-wrapper">
                <div class="health-dashboard-bg"></div>
                <div class="health-content">
                  <div class="health-icon-pulse">
                    <span style="font-size: 56px;">🌌</span>
                  </div>
                  <h3 class="health-title">{{ pageText('pages.dictionaryLibraryOverview') }}</h3>
                  <div class="health-stats-container">
                    <div class="health-stat-card primary-stat">
                      <div class="stat-value">{{ dictList.length }}</div>
                      <div class="stat-label">{{ pageText('pages.coreAssetDictionaries') }}</div>
                    </div>
                    <div class="health-stat-card warning-stat">
                      <div class="stat-value">{{ bruteDictList.length }}</div>
                      <div class="stat-label">{{ pageText('pages.credentialDictionaries') }}</div>
                    </div>
                  </div>
                  <div class="health-hint">
                    <span class="pulse-dot"></span>
                    <span>{{ pageText('pages.systemStatusIsHealthySelectADictionaryOnThe') }}</span>
                  </div>
                </div>
              </div>

              <!-- 统一操作面板（沉浸式代码编辑器预览与悬浮操作） -->
              <div v-else class="native-preview-container">
                <!-- 顶部固定操作栏 -->
                <div class="native-toolbar">
                   <div>
                     <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 4px;">
                       <h3 style="margin: 0; font-size: 16px; font-weight: 600; color: var(--arl-text-color);">{{ unifiedSelectedName }}</h3>
                       <a-tag :color="unifiedSelectedType === 'asset' ? 'blue' : 'orange'" style="margin: 0;">
                         {{ unifiedSelectedType === 'asset' ? pageText('pages.assetDiscovery') : pageText('pages.credentialChecks') }}
                       </a-tag>
                       <a-tag v-if="unifiedSelectedIsBuiltin" color="purple" style="margin: 0;">
                         {{ pageText('pages.systemBuiltIn') }}
                       </a-tag>
                     </div>
                     <div class="page-dictionary-summary">{{ pageText('pages.dictionaryDescriptionCount', { description: unifiedSelectedDesc, count: totalLines }) }}</div>
                   </div>
                   <div style="display: flex; gap: 8px; align-items: center;">
                      <a-button @click="handleDownloadDict" :loading="downloadLoading" :title="pageText('pages.exportDictionaryFile')">
                        <template #icon><span class="page-icon-gap">📥</span></template> {{ pageText('pages.exportDictionary') }}
                      </a-button>
                      <a-tooltip v-if="unifiedSelectedIsBuiltin" :title="pageText('pages.coreBuiltInDictionariesAreProtectedAndCannotBe')">
                        <a-button danger disabled>
                          <template #icon><span class="page-icon-gap">🗑️</span></template> {{ pageText('pages.deleteDictionary') }}
                        </a-button>
                      </a-tooltip>
                      <a-popconfirm
                        v-else
                        :title="pageText('pages.permanentlyDeleteThisDictionaryFileThisCannotBeUndone')"
                        placement="bottomRight"
                        @confirm="handleDeleteDict"
                      >
                        <a-button danger>
                          <template #icon><span class="page-icon-gap">🗑️</span></template> {{ pageText('pages.deleteDictionary') }}
                        </a-button>
                      </a-popconfirm>
                     <a-button @click="searchDrawerVisible = true">
                       <template #icon><span class="page-icon-gap">🔍</span></template> {{ pageText('pages.searchAndRemove') }}
                     </a-button>
                     <a-button type="primary" @click="appendDrawerVisible = true">
                       <template #icon><span class="page-icon-gap">➕</span></template> {{ pageText('pages.appendEntries') }}
                     </a-button>
                   </div>
                </div>
                
                <!-- 极简内容预览区 -->
                <div class="native-preview-area hide-scrollbar" style="display: flex; flex-direction: column; gap: 12px;">
                  <div style="display: flex; justify-content: space-between; align-items: center; background: var(--arl-bg-white); padding: 8px 16px; border-radius: 8px; border: 1px solid var(--arl-border-color); box-shadow: 0 1px 2px rgba(0,0,0,0.02);">
                    <div style="display: flex; align-items: center; gap: 8px;">
                      <span style="font-size: 13px; font-weight: 500; color: var(--arl-text-color);">
                        {{ pageText('pages.dictionaryPreviewCount', { shown: previewLimit, total: totalLines }) }}
                      </span>
                    </div>
                    <div style="display: flex; gap: 8px; align-items: center;">
                      <span class="page-muted-label">{{ pageText('pages.previewLines') }}</span>
                      <a-radio-group v-model:value="previewLimit" size="small" @change="() => fetchPreview(selectedDict)">
                        <a-radio-button :value="50">50</a-radio-button>
                        <a-radio-button :value="100">100</a-radio-button>
                        <a-radio-button :value="500">500</a-radio-button>
                        <a-radio-button :value="1000">1000</a-radio-button>
                      </a-radio-group>
                      <a-button size="small" @click="copyPreviewContent">
                        <template #icon><span class="page-small-icon-gap">📋</span></template> {{ pageText('pages.copyPreview') }}
                      </a-button>
                    </div>
                  </div>

                  <div class="native-code-wrapper" style="flex: 1;">
                    <div class="native-line-numbers" v-if="previewContent">
                      <div v-for="n in previewLinesCount" :key="n" class="line-number">{{ n }}</div>
                    </div>
                    <div class="native-code-content">
                      <div v-if="!previewContent" class="empty-code">
                        <span>{{ pageText('pages.thisDictionaryIsEmpty') }}</span>
                      </div>
                      <pre v-else class="code-text">{{ previewContent }}</pre>
                      <div v-if="totalLines > previewLimit" class="code-limit-hint">
                        {{ pageText('pages.dictionaryPreviewTail', { shown: previewLimit, total: totalLines }) }}
                      </div>
                    </div>
                  </div>
                </div>
              </div>

            </div>
          </div>
        </a-spin>

        <!-- 新建字典抽屉 -->
        <a-drawer v-model:open="createDictDrawerVisible" :title="pageText('pages.newDictionary')" placement="right" width="450" @close="resetCreateDictForm">
          <a-tabs v-model:activeKey="createDictTabKey">
            <!-- 手动输入新建 -->
            <a-tab-pane key="manual" :tab="pageText('pages.createFromText')">
              <div class="page-description">{{ pageText('pages.selectADictionaryCategoryAndEnterInitialContentThe') }}</div>
              <a-form :label-wrap="true" layout="vertical">
                <a-form-item :label="pageText('pages.dictionaryCategories')" required>
                  <a-select v-model:value="createDictForm.prefix">
                    <a-select-option value="domain_">{{ pageText('pages.subdomainDiscoveryDomain') }}</a-select-option>
                    <a-select-option value="altdns_">{{ pageText('pages.subdomainMutationDiscoveryAltdns') }}</a-select-option>
                    <a-select-option value="file_">{{ pageText('pages.directoryAndFileDisclosureFile') }}</a-select-option>
                    <a-select-option value="black">{{ pageText('pages.globalBlocklistBlack') }}</a-select-option>
                    <a-select-option value="port_">{{ pageText('pages.portScanPolicyPort') }}</a-select-option>
                    <a-select-option value="dnsserver_">{{ pageText('pages.dnsResolversDnsserver') }}</a-select-option>
                    <a-select-option value="username_">{{ pageText('pages.usernamesUsername') }}</a-select-option>
                    <a-select-option value="password_">{{ pageText('pages.passwordsPassword') }}</a-select-option>
                  </a-select>
                </a-form-item>
                <a-form-item :label="pageText('pages.dictionaryNameLettersNumbersAndUnderscoresOnly')" required>
                  <a-input v-model:value="createDictForm.customName" :placeholder="pageText('pages.eGTop100')" />
                </a-form-item>
                <a-form-item :label="pageText('pages.initialDictionaryContentOptional')">
                  <a-textarea v-model:value="createDictForm.content" :placeholder="pageText('pages.oneEntryPerLineBulkPasteIsSupportedUse')" :rows="8" @paste="handlePasteContent" />
                </a-form-item>
              </a-form>
              <div style="text-align: right; margin-top: 24px;">
                <a-button @click="createDictDrawerVisible = false" class="page-inline-gap">{{ pageText('tasks.cancel') }}</a-button>
                <a-button type="primary" :loading="createDictLoading" :disabled="!isCreateDictValid" @click="handleCreateDictManual">{{ pageText('pages.createDictionary') }}</a-button>
              </div>
            </a-tab-pane>

            <!-- 文件上传新建 -->
            <a-tab-pane key="upload" :tab="pageText('pages.createFromFile')">
              <div class="page-description">{{ pageText('pages.selectADictionaryCategoryAndUploadATxtFile') }}</div>
              <a-form :label-wrap="true" layout="vertical">
                <a-form-item :label="pageText('pages.dictionaryCategories')" required>
                  <a-select v-model:value="createDictForm.prefix">
                    <a-select-option value="domain_">{{ pageText('pages.subdomainDiscoveryDomain') }}</a-select-option>
                    <a-select-option value="altdns_">{{ pageText('pages.subdomainMutationDiscoveryAltdns') }}</a-select-option>
                    <a-select-option value="file_">{{ pageText('pages.directoryAndFileDisclosureFile') }}</a-select-option>
                    <a-select-option value="black">{{ pageText('pages.globalBlocklistBlack') }}</a-select-option>
                    <a-select-option value="port_">{{ pageText('pages.portScanPolicyPort') }}</a-select-option>
                    <a-select-option value="dnsserver_">{{ pageText('pages.dnsResolversDnsserver') }}</a-select-option>
                    <a-select-option value="username_">{{ pageText('pages.usernamesUsername') }}</a-select-option>
                    <a-select-option value="password_">{{ pageText('pages.passwordsPassword') }}</a-select-option>
                  </a-select>
                </a-form-item>
                <a-form-item :label="pageText('pages.dictionaryNameLettersNumbersAndUnderscoresOnly')" required>
                  <a-input v-model:value="createDictForm.customName" :placeholder="pageText('pages.eGTop100')" />
                </a-form-item>
                <a-form-item :label="pageText('pages.dictionaryFileTxt')" required>
                  <a-upload :file-list="createDictForm.fileList" :before-upload="(f) => { createDictForm.fileList = [f]; return false; }" @remove="createDictForm.fileList = []" accept=".txt">
                    <a-button><template #icon>📁</template> {{ pageText('pages.selectFile') }}</a-button>
                  </a-upload>
                </a-form-item>
              </a-form>
              <div style="text-align: right; margin-top: 24px;">
                <a-button @click="handleCreateDictUploadCancel" class="page-inline-gap">{{ pageText('tasks.cancel') }}</a-button>
                <a-button type="primary" :loading="createDictLoading" :disabled="!isCreateDictValid || createDictForm.fileList.length === 0" @click="handleCreateDictUpload">{{ pageText('pages.uploadAndCreate') }}</a-button>
              </div>
            </a-tab-pane>
          </a-tabs>
        </a-drawer>

        <!-- 上传字典弹窗 -->
        <!-- 追加数据抽屉（合并手动输入与大文件上传） -->
        <a-drawer v-model:open="appendDrawerVisible" :title="pageText('pages.appendDictionaryEntries')" placement="right" width="450">
          <a-tabs v-model:activeKey="appendMode" style="margin-bottom: 16px;">
            <a-tab-pane key="text" :tab="pageText('pages.pasteText')">
              <div class="page-compact-description">{{ pageText('pages.pasteEntriesToAppendOnePerLine') }}</div>
              <a-textarea v-model:value="newEntries" :rows="22" @paste="handlePasteNewEntries" :placeholder="pageText('pages.eGAdminRoot')" class="page-code-preview" />
              <div style="display: flex; justify-content: flex-end; gap: 12px;">
                <a-button @click="appendDrawerVisible = false">{{ pageText('tasks.cancel') }}</a-button>
                <a-button type="primary" @click="handleAppendAndClose" :loading="submitLoading" :disabled="!newEntries.trim()">{{ pageText('pages.saveEntries') }}</a-button>
              </div>
            </a-tab-pane>
            <a-tab-pane key="file" :tab="pageText('pages.uploadFile')">
              <div>
                <div style="margin-bottom: 16px; color: var(--arl-text-color); font-size: 13px;">
                  {{ pageText('pages.uploadTxtFilesWithMillionsOfLinesTheSystem') }}
                </div>
                <a-upload-dragger
                  name="file"
                  :multiple="false"
                  :customRequest="handleLargeUpload"
                  accept=".txt"
                  :showUploadList="false"
                >
                  <p class="ant-upload-drag-icon" style="font-size: 48px; margin-bottom: 16px;">
                    📄
                  </p>
                  <p class="ant-upload-text">{{ pageText('pages.clickOrDragATxtFileHere') }}</p>
                  <p class="ant-upload-hint">
                    {{ pageText('pages.plainTextOnlyOneEntryPerLine') }}
                  </p>
                </a-upload-dragger>
              </div>
            </a-tab-pane>
          </a-tabs>
        </a-drawer>

        <!-- 搜索清理抽屉 -->
        <a-drawer v-model:open="searchDrawerVisible" :title="pageText('pages.searchAndRemoveEntries')" placement="right" width="450">
          <div style="margin-bottom: 24px;">
            <div class="page-form-section-title">{{ pageText('pages.exactSearch') }}</div>
            <a-input-search
              v-model:value="searchKeyword"
              :placeholder="pageText('pages.enterAKeywordToSearchForEntries')"
              @search="handleSearch"
              :loading="searchLoading"
            >
              <template #enterButton><a-button type="primary">{{ pageText('pages.search') }}</a-button></template>
            </a-input-search>
            
            <div v-if="searchResult !== null" style="margin-top: 12px;">
              <div v-if="searchResult.length > 0" class="page-success-detail">{{ pageText('pages.found') }} {{ searchResult.length }} {{ pageText('pages.matchingEntries') }}</div>
              <div v-else class="page-error-detail">{{ pageText('pages.noMatchingEntries') }}</div>
              <div v-if="searchResult.length > 0" style="max-height: 300px; overflow-y: auto;">
                <div v-for="(item, idx) in searchResult" :key="idx" style="display: flex; align-items: center; justify-content: space-between; padding: 6px 12px; border-bottom: 1px solid var(--arl-border-color); background: var(--arl-bg-light); margin-bottom: 4px; border-radius: 4px;">
                  <span style="font-family: monospace; font-size: 12px; word-break: break-all; color: var(--arl-text-color);">{{ item }}</span>
                  <a-button type="text" danger size="small" @click="handleDeleteSingle(item)" :loading="deleteLoading">{{ pageText('tasks.delete') }}</a-button>
                </div>
              </div>
              <div v-if="searchResult.length === 100" class="page-warning-detail">{{ pageText('pages.onlyTheFirst100ResultsAreShownRefineYour') }}</div>
            </div>
          </div>
          
          <a-divider />
          
          <div>
            <div class="page-danger-section-title">{{ pageText('pages.deleteEntriesInBulk') }}</div>
            <div class="page-empty-detail">{{ pageText('pages.enterTheExactEntriesToDeleteOnePerLine') }}</div>
            <a-textarea v-model:value="batchDeleteEntries" :rows="10" :placeholder="pageText('pages.eGAdmin123123456')" class="page-code-summary" />
            <a-button danger block @click="handleDeleteBatchCustom" :loading="deleteLoading" :disabled="!batchDeleteEntries.trim()">{{ pageText('pages.deleteSubmittedEntries') }}</a-button>
          </div>
        </a-drawer>
      </a-tab-pane>

      <a-tab-pane key="cdn" :tab="pageText('pages.cdnFingerprintsAndRules')">
        <CdnRulePanel ref="cdnPanelRef" />
      </a-tab-pane>
        </a-tabs>
      </a-tab-pane>
      <a-tab-pane key="performance" :tab="tabTitle(pageText('pages.scanningAndConcurrency'), isPerformanceDirty || isSecurityDirty || Object.keys(pendingByGroup.system_general || {}).length > 0)">
        <a-tabs v-model:activeKey="scanSubTab" type="card" class="dict-sub-tabs" style="margin-bottom: 16px;">
          <a-tab-pane key="performance" :tab="tabTitle(pageText('pages.taskQueueConcurrency'), isPerformanceDirty)">
            <div style="max-width: 1000px; padding-bottom: 40px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <span style="color: var(--arl-text-color); opacity: 0.45;">
                  {{ pageText('pages.setTheNumberOfWorkerProcessesInEachTask') }}
                </span>
                <div>
                  <a-button @click="fetchPerformanceConfig" :loading="performanceLoading" style="margin-right: 8px;">
                    {{ pageText('pages.refreshStatus') }}
                  </a-button>
                  <a-button
                    type="primary"
                    @click="savePerformanceConfig"
                    :loading="performanceSaveLoading"
                    :disabled="!isPerformanceDirty"
                  >
                    {{ isPerformanceDirty ? pageText('pages.savePerformanceSettings') : pageText('pages.noPerformanceChanges') }}
                  </a-button>
                </div>
              </div>
              <a-spin :spinning="performanceLoading">
                <a-form :label-wrap="true" layout="vertical">
                  <!-- 语义分区说明：本页是「进程级队列并发」，与「高级扫描与环境」页的
                       「单任务内爆破线程数」是两套不同量级的指标，避免用户混淆调错 -->
                  <a-alert type="info" show-icon style="margin-bottom: 16px; border-radius: 6px;">
                    <template #message>
                      <div style="font-size: 13px; line-height: 1.8;">
                        <div>{{ pageText('pages.queueMemoryHelp', { heavy: (capacityInfo.queue_memory_caps_mb || {}).heavy || 488, light: (capacityInfo.queue_memory_caps_mb || {}).light || 292 }) }}</div>
                        <div><strong class="page-warning-emphasis">{{ pageText('pages.smallMemoryQueueHelp') }}</strong></div>
                        <div>{{ pageText('pages.perTaskConcurrencyHelp') }} <a @click="goToBruteConcurrent">{{ pageText('pages.scanningAndConcurrencyAdvancedScanningAndEnvironment') }}</a></div>
                      </div>
                    </template>
                  </a-alert>
                  <a-row :gutter="24">
                    <a-col :span="12">
                      <a-card data-setting-anchor="performance" :title="pageText('pages.heavyTaskScheduling')" size="small" class="page-config-card-danger">
                        <a-form-item>
                          <template #label>
                            <span>{{ pageText('pages.heavyTaskConcurrency') }}</span>
                            <a-tag v-if="runtimePerformance.runtime_heavy_concurrency !== null" color="blue" style="margin-left: 8px; font-size: 12px;">
                              {{ pageText('pages.runningProcessesCount', { count: runtimePerformance.runtime_heavy_concurrency }) }}
                            </a-tag>
                            <a-tag v-else color="default" class="page-choice-gap">{{ pageText('pages.workerOffline') }}</a-tag>
                            <a-popover placement="right">
                              <template #content>
                                <div style="max-width: 320px;">
                                  <div class="page-strong-heading">{{ pageText('pages.assignmentLongRunningTasks') }}</div>
                                  <ul style="padding-left: 18px; margin: 0; line-height: 1.8;">
                                    <li>{{ pageText('pages.regularDomainIpScans') }}</li>
                                    <li>{{ pageText('pages.riskScansBulkVulnerabilityChecks') }}</li>
                                    <li>{{ pageText('pages.scheduledDomainIpMonitoring') }}</li>
                                  </ul>
                                </div>
                              </template>
                              <InfoCircleOutlined style="margin-left: 4px; color: #888; cursor: pointer;" />
                            </a-popover>
                          </template>
                          <a-input-number v-model:value="performanceForm.celery_heavy_concurrency" :min="1" :max="128" style="width: 100%" />
                          <div style="margin-top: 8px; color: var(--arl-text-color); opacity: 0.45; font-size: 13px;">
                            {{ pageText('pages.controlConcurrencyForRegularScansRiskScansAndOther') }}
                          </div>
                          <div v-if="capacityInfo.heavy_recommended" class="arl-recommend-row">
                            <span>
                              <span class="arl-recommend-label">{{ pageText('pages.recommended') }}</span>
                              <strong>{{ capacityInfo.heavy_recommended }}</strong>
                              <span class="arl-recommend-basis">
                                {{ pageText('pages.queueMemoryBudget', { available: capacityInfo.available_memory_mb, budget: capacityInfo.headroom_mb }) }}
                              </span>
                            </span>
                            <a-button size="small" type="link" @click="applyRecommended(performanceForm, 'heavy')">{{ pageText('pages.apply') }}</a-button>
                          </div>
                          <div class="arl-recommend-basis" style="margin-top: 4px;">{{ capacityInfo.basis }}</div>
                          <a-alert
                            v-if="capacityInfo.steady_ok === false"
                            type="error"
                            show-icon
                            style="margin-top: 8px; border-radius: 6px;"
                          >
                            <template #message>
                              <span style="font-size: 12px;">
                                {{ pageText('pages.insufficientQueueMemory', { peak: capacityInfo.peak_used_mb, budget: capacityInfo.headroom_mb }) }}
                              </span>
                            </template>
                          </a-alert>
                        </a-form-item>
                      </a-card>
                    </a-col>
                    <a-col :span="12">
                      <a-card :title="pageText('pages.lightTaskScheduling')" size="small" class="page-config-card-success">
                        <a-form-item>
                          <template #label>
                            <span>{{ pageText('pages.lightTaskConcurrency') }}</span>
                            <a-tag v-if="runtimePerformance.runtime_light_concurrency !== null" color="green" style="margin-left: 8px; font-size: 12px;">
                              {{ pageText('pages.runningProcessesCount', { count: runtimePerformance.runtime_light_concurrency }) }}
                            </a-tag>
                            <a-tag v-else color="default" class="page-choice-gap">{{ pageText('pages.workerOffline') }}</a-tag>
                            <a-popover placement="right">
                              <template #content>
                                <div style="max-width: 320px;">
                                  <div class="page-strong-heading">{{ pageText('pages.assignmentSingleTargetApiTasks') }}</div>
                                  <ul style="padding-left: 18px; margin: 0; line-height: 1.8;">
                                    <li>{{ pageText('pages.assetSearchQueriesFofaEtc') }}</li>
                                    <li>{{ pageText('pages.updateAWebsiteScreenshotFingerprints') }}</li>
                                    <li>{{ pageText('pages.singleTargetWebInfoHunterWihExtraction') }}</li>
                                    <li>{{ pageText('pages.manuallyAddAWebsite') }}</li>
                                    <li>{{ pageText('pages.forceTaskDataSynchronization') }}</li>
                                  </ul>
                                </div>
                              </template>
                              <InfoCircleOutlined style="margin-left: 4px; color: #888; cursor: pointer;" />
                            </a-popover>
                          </template>
                          <a-input-number v-model:value="performanceForm.celery_light_concurrency" :min="1" :max="256" style="width: 100%" />
                          <div style="margin-top: 8px; color: var(--arl-text-color); opacity: 0.45; font-size: 13px;">
                            {{ pageText('pages.usesADedicatedQueueAndDoesNotWaitFor') }}
                          </div>
                          <div v-if="capacityInfo.light_recommended" class="arl-recommend-row">
                            <span>
                              <span class="arl-recommend-label">{{ pageText('pages.recommended') }}</span>
                              <strong>{{ capacityInfo.light_recommended }}</strong>
                              <span class="arl-recommend-basis">{{ pageText('pages.allocatedUsingThePeakMemoryModelLightTasksHave') }}</span>
                            </span>
                            <a-button size="small" type="link" @click="applyRecommended(performanceForm, 'light')">{{ pageText('pages.apply') }}</a-button>
                          </div>
                        </a-form-item>
                      </a-card>
                    </a-col>
                  </a-row>
                  <a-row :gutter="24">
                    <a-col :span="12">
                      <a-card :title="pageText('pages.externalIntelligenceTaskScheduling')" size="small" class="page-config-card-info">
                        <a-form-item>
                          <template #label>
                            {{ pageText('pages.osintTaskConcurrency') }}
                            <a-popover placement="right">
                              <template #content>
                                <div style="max-width: 320px;">
                                  <div class="page-strong-heading">{{ pageText('pages.assignmentExternalIntelligenceTasks') }}</div>
                                  <ul style="padding-left: 18px; margin: 0; line-height: 1.8;">
                                    <li>{{ pageText('pages.icpRecordsWebsitesAppsMiniPrograms') }}</li>
                                    <li>{{ pageText('pages.tianyanchaInvestmentRelationshipsAndAssetCollection') }}</li>
                                  </ul>
                                </div>
                              </template>
                              <InfoCircleOutlined style="margin-left: 4px; color: #888; cursor: pointer;" />
                            </a-popover>
                          </template>
                          <a-input-number v-model:value="performanceForm.osint_concurrency" :min="1" :max="128" style="width: 100%" />
                          <div style="margin-top: 8px; color: var(--arl-text-color); opacity: 0.45; font-size: 13px;">
                            {{ pageText('pages.controlConcurrentOsintRequestsToExternalServicesSuchAs') }}
                          </div>
                          <div v-if="capacityInfo.osint_recommended" class="arl-recommend-row">
                            <span>
                              <span class="arl-recommend-label">{{ pageText('pages.recommended') }}</span>
                              <strong>{{ capacityInfo.osint_recommended }}</strong>
                              <span class="arl-recommend-basis">{{ pageText('pages.keepTheDefaultToReduceExternalAntiBotRestrictions') }}</span>
                            </span>
                            <a-button size="small" type="link" @click="applyRecommended(performanceForm, 'osint')">{{ pageText('pages.apply') }}</a-button>
                          </div>
                        </a-form-item>
                      </a-card>
                    </a-col>
                    <a-col :span="12">
                      <a-card :title="pageText('pages.githubMonitoringScheduling')" size="small" class="page-config-card-purple">
                        <a-form-item>
                          <template #label>
                            <span>{{ pageText('pages.githubMonitoringConcurrency') }}</span>
                            <a-tag v-if="runtimePerformance.runtime_github_concurrency !== null" color="purple" style="margin-left: 8px; font-size: 12px;">
                              {{ pageText('pages.runningProcessesCount', { count: runtimePerformance.runtime_github_concurrency }) }}
                            </a-tag>
                            <a-tag v-else color="default" class="page-choice-gap">{{ pageText('pages.workerOffline') }}</a-tag>
                            <a-popover placement="right">
                              <template #content>
                                <div style="max-width: 320px;">
                                  <div class="page-strong-heading">{{ pageText('pages.assignmentGithubMonitoringTasks') }}</div>
                                  <ul style="padding-left: 18px; margin: 0; line-height: 1.8;">
                                    <li>{{ pageText('pages.codeLeakKeywordMonitoring') }}</li>
                                    <li>{{ pageText('pages.cveSecurityToolUpdates') }}</li>
                                    <li>{{ pageText('pages.researcherActivityMonitoring') }}</li>
                                  </ul>
                                </div>
                              </template>
                              <InfoCircleOutlined style="margin-left: 4px; color: #888; cursor: pointer;" />
                            </a-popover>
                          </template>
                          <a-input-number v-model:value="performanceForm.github_concurrency" :min="1" :max="64" style="width: 100%" />
                          <div style="margin-top: 8px; color: var(--arl-text-color); opacity: 0.45; font-size: 13px;">
                            {{ pageText('pages.usesTheDedicatedArlgithubQueueIndependentlyOfScanningTasks') }}
                          </div>
                          <div v-if="capacityInfo.github_recommended" class="arl-recommend-row">
                            <span>
                              <span class="arl-recommend-label">{{ pageText('pages.recommended') }}</span>
                              <strong>{{ capacityInfo.github_recommended }}</strong>
                              <span class="arl-recommend-basis">{{ pageText('pages.queueProcessLimit', { limit: (capacityInfo.queue_memory_caps_mb || {}).github || 292 }) }}</span>
                            </span>
                            <a-button size="small" type="link" @click="applyRecommended(performanceForm, 'github')">{{ pageText('pages.apply') }}</a-button>
                          </div>
                        </a-form-item>
                      </a-card>
                    </a-col>
                  </a-row>

                </a-form>
              </a-spin>
            </div>
          </a-tab-pane>
          <a-tab-pane key="security" :tab="tabTitle(pageText('pages.securityPolicyIpDomainScanExclusions'), isSecurityDirty)">
            <div style="max-width: 1000px; padding-bottom: 40px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <span style="color: var(--arl-text-color); opacity: 0.45;">
                  {{ pageText('pages.preventScanningSpecifiedIpsOrDomainsGloballySavedChanges') }}
                </span>
                <a-button
                  type="primary"
                  @click="saveSecurityPolicy"
                  :loading="securitySaveLoading"
                  :disabled="!isSecurityDirty"
                >
                  {{ isSecurityDirty ? pageText('pages.saveSecurityPolicy') : pageText('pages.noSecurityPolicyChanges') }}
                </a-button>
              </div>
              <a-spin :spinning="securityLoading">
                <a-form :label-wrap="true" layout="vertical">
                  <a-form-item data-setting-anchor="security" :label="pageText('pages.ipBlocklistSupportsCidrEG12700')">
                    <a-textarea v-model:value="securityForm.blackIpsText" :rows="8" :placeholder="pageText('pages.eG1270008100')" />
                  </a-form-item>
              
                  <a-form-item :label="pageText('pages.excludedDomainsSuffixMatchingEGGovCnOr')">
                    <a-textarea v-model:value="securityForm.forbiddenDomainsText" :rows="8" :placeholder="pageText('pages.eGGovCnEduCn')" />
                  </a-form-item>
                </a-form>
              </a-spin>
            </div>
          </a-tab-pane>
          <a-tab-pane key="system_general" :tab="tabTitle(pageText('pages.advancedScanningAndEnvironment'), Object.keys(pendingByGroup.system_general || {}).length > 0)">
            <div style="max-width: 1000px; padding-bottom: 40px;">
              <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
                <span style="color: var(--arl-text-color); opacity: 0.45;">
                  {{ pageText('pages.configurePerTaskExecutionSettingsOutboundProxyDefaultPorts') }}
                </span>
                <a-button
                  type="primary"
                  :class="{ 'arl-dirty-btn': Object.keys(pendingByGroup.system_general).length > 0 }"
                  @click="saveGeneralConfig('system_general', pageText('pages.advancedConfigurationSaved'))"
                  :loading="generalSaveLoading"
                >
                  {{ pageText('pages.saveAdvancedConfiguration') }}
                  <a-badge
                    v-if="Object.keys(pendingByGroup.system_general).length > 0"
                    :count="Object.keys(pendingByGroup.system_general).length"
                    :offset="[8, -8]"
                    color="#faad14"
                  />
                </a-button>
              </div>
              <a-spin :spinning="generalLoading">
                <a-form :label-wrap="true" layout="vertical">
                  <!-- 语义分区说明：本页的爆破并发度属于「单任务内」，与「任务队列并发」页的
                       进程数不是同一指标，避免用户跨页误填同量级数值 -->
                  <a-alert type="info" show-icon style="margin-bottom: 16px; border-radius: 6px;">
                    <template #message>
                      <div style="font-size: 13px; line-height: 1.8;">
                        {{ pageText('pages.dnsConcurrencyHelp') }} <a @click="goToQueueConcurrency">{{ pageText('pages.scanningAndConcurrencyTaskQueueConcurrency') }}</a>
                      </div>
                    </template>
                  </a-alert>
                  <a-row :gutter="24">
                    <a-col :span="12">
                      <a-form-item data-setting-anchor="proxy" :label="pageText('pages.systemProxyProxyHttpUrl')">
                        <a-input v-model:value="generalForm.proxy_url" :placeholder="pageText('pages.eGHttp1270018080')" />
                      </a-form-item>
                    </a-col>
                    <a-col :span="12">
                      <a-form-item data-setting-anchor="port_top_10" :label="pageText('pages.top10WebPortsUsedByFrontendPortScan')">
                        <a-input v-model:value="generalForm.port_top_10" :placeholder="pageText('pages.separateValuesWithCommas')" />
                      </a-form-item>
                    </a-col>
                  </a-row>

                  <a-row :gutter="24">
                    <a-col :span="12">
                      <a-form-item data-setting-anchor="brute_concurrent" :label="pageText('pages.dnsQueryConcurrencyForRegularSubdomainDiscovery')">
                        <a-input-number v-model:value="generalForm.domain_brute_concurrent" :min="1" style="width: 100%" />
                        <div class="arl-field-hint">
                          {{ pageText('pages.dnsQueryConcurrencyWithinOneTaskTheMassdns') }} <code>-s</code> {{ pageText('pages.optionRatherThanAProcessOrThreadCountHigher') }}
                        </div>
                      </a-form-item>
                    </a-col>
                    <a-col :span="12">
                      <a-form-item :label="pageText('pages.dnsQueryConcurrencyForSubdomainMutationDiscovery')">
                        <a-input-number v-model:value="generalForm.alt_dns_concurrent" :min="1" style="width: 100%" />
                        <div class="arl-field-hint">
                          {{ pageText('pages.usedDuringAltdnsDiscoveryItsDefaultIsHigherBecause') }}
                        </div>
                      </a-form-item>
                    </a-col>
                  </a-row>


                  <a-row :gutter="24">
                    <a-col :span="12">
                      <a-form-item data-setting-anchor="auth" :label="pageText('pages.apiAuthentication')">
                        <a-switch v-model:checked="generalForm.auth" :checked-children="pageText('pages.on')" :un-checked-children="pageText('pages.off')" />
                      </a-form-item>
                    </a-col>
                    <a-col :span="12">
                      <a-form-item label="API Token (Swagger API Key)">
                        <a-input-password v-model:value="generalForm.api_key" :placeholder="pageText('pages.apiKeyOnlyRequiredWhenApiAuthenticationIsEnabled')" />
                      </a-form-item>
                    </a-col>
                  </a-row>

                  <a-form-item data-setting-anchor="infra" :label="pageText('pages.infrastructureServiceConnectionsReadOnly')">
                    <div style="background: var(--arl-bg-light); border: 1px solid var(--arl-border-color); border-radius: 4px; padding: 16px;">
                      <a-descriptions bordered size="small" :column="1">
                        <a-descriptions-item :label="pageText('pages.celeryMessageQueueBrokerUrl')">
                          <code style="word-break: break-all;">{{ generalForm.celery_broker_url }}</code>
                        </a-descriptions-item>
                        <a-descriptions-item :label="pageText('pages.mongodbUri')">
                          <code style="word-break: break-all;">{{ generalForm.mongo_url }}</code>
                        </a-descriptions-item>
                        <a-descriptions-item :label="pageText('pages.defaultMongodbDatabase')">
                          <code>{{ generalForm.mongo_db }}</code>
                        </a-descriptions-item>
                        <a-descriptions-item :label="pageText('pages.absolutePathToGeoipCityDatabase')">
                          <code style="word-break: break-all;">{{ generalForm.geoip_city }}</code>
                        </a-descriptions-item>
                        <a-descriptions-item :label="pageText('pages.absolutePathToGeoipAsnDatabase')">
                          <code style="word-break: break-all;">{{ generalForm.geoip_asn }}</code>
                        </a-descriptions-item>
                        <a-descriptions-item :label="pageText('pages.absolutePathToIp2regionDatabase')">
                          <code style="word-break: break-all;">{{ generalForm.geoip_ip2region || '-' }}</code>
                        </a-descriptions-item>
                      </a-descriptions>
                    </div>
                  </a-form-item>
                </a-form>
              </a-spin>
            </div>
          </a-tab-pane>
        </a-tabs>
      </a-tab-pane>
      <a-tab-pane key="message_push" :tab="tabTitle(pageText('pages.notificationsAndCallbacks'), Object.keys(pendingByGroup.message_push).length > 0)">
        <div style="max-width: 1100px; padding-bottom: 40px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px;">
            <span style="color: var(--arl-text-color); opacity: 0.45;">
              {{ pageText('pages.configureNotificationsAfterMonitoringTasksFinishAndAutomatedWebhook') }}
            </span>
            <a-button
              type="primary"
              :class="{ 'arl-dirty-btn': Object.keys(pendingByGroup.message_push).length > 0 }"
              @click="saveGeneralConfig('message_push', pageText('pages.notificationConfigurationSaved'))"
              :loading="generalSaveLoading"
            >
              {{ pageText('pages.saveNotificationConfiguration') }}
              <a-badge
                v-if="Object.keys(pendingByGroup.message_push).length > 0"
                :count="Object.keys(pendingByGroup.message_push).length"
                :offset="[8, -8]"
                color="#faad14"
              />
            </a-button>
          </div>

          <a-spin :spinning="generalLoading">
            <a-form :label-wrap="true" layout="vertical">
              
              <!-- 1. 订阅消息类型 -->
              <a-card data-setting-anchor="push_options" :title="pageText('pages.subscribedEvents')" size="small" class="page-config-card-theme">
                <a-checkbox-group v-model:value="generalForm.push_options" style="width: 100%;">
                  <a-row>
                    <a-col :span="6" class="page-form-spacing"><a-checkbox value="task_complete">{{ pageText('pages.assetDiscoveryTaskCompleted') }}</a-checkbox></a-col>
                    <a-col :span="6" class="page-form-spacing"><a-checkbox value="github_leak">{{ pageText('pages.githubKeywordAlert') }}</a-checkbox></a-col>
                    <a-col :span="6" class="page-form-spacing"><a-checkbox value="github_cve">{{ pageText('pages.githubCveUpdate') }}</a-checkbox></a-col>
                    <a-col :span="6" class="page-form-spacing"><a-checkbox value="github_tools">{{ pageText('pages.githubSecurityToolUpdate') }}</a-checkbox></a-col>
                    <a-col :span="6"><a-checkbox value="github_hackers">{{ pageText('pages.githubResearcherActivity') }}</a-checkbox></a-col>
                    <a-col :span="6"><a-checkbox value="asset_site">{{ pageText('pages.websiteMonitoringUpdate') }}</a-checkbox></a-col>
                  </a-row>
                </a-checkbox-group>
              </a-card>

              <!-- 2. 即时通讯推送配置 (2列) -->
              <a-row :gutter="16">
                <!-- 钉钉 -->
                <a-col :span="12">
                  <a-card data-setting-anchor="im" :title="pageText('pages.dingtalkBot')" size="small" class="page-config-card-fixed-short">
                    <template #extra>
                      <a-button type="link" size="small" @click="handleTestPush('dingding')" :loading="testPushLoading.dingding">{{ pageText('pages.sendTest') }}</a-button>
                    </template>
                    <a-row :gutter="12">
                      <a-col :span="12">
                        <a-form-item label="Access Token" style="margin-bottom: 0;">
                          <a-input v-model:value="generalForm.dingding.access_token" :placeholder="pageText('pages.dingtalkToken')" size="small" />
                        </a-form-item>
                      </a-col>
                      <a-col :span="12">
                        <a-form-item :label="pageText('pages.signingSecret')" class="page-flush-bottom">
                          <a-input-password v-model:value="generalForm.dingding.secret" :placeholder="pageText('pages.dingtalkSecret')" size="small" />
                        </a-form-item>
                      </a-col>
                    </a-row>
                  </a-card>
                </a-col>

                <!-- 飞书 -->
                <a-col :span="12">
                  <a-card :title="pageText('pages.feishuBot')" size="small" class="page-config-card-fixed-short">
                    <template #extra>
                      <a-button type="link" size="small" @click="handleTestPush('feishu')" :loading="testPushLoading.feishu">{{ pageText('pages.sendTest') }}</a-button>
                    </template>
                    <a-form-item label="Webhook URL" style="margin-bottom: 8px;">
                      <a-input v-model:value="generalForm.feishu.webhook_url" :placeholder="pageText('pages.feishuWebhookUrl')" size="small" />
                    </a-form-item>
                    <a-form-item :label="pageText('pages.signingSecret')" class="page-flush-bottom">
                      <a-input-password v-model:value="generalForm.feishu.secret" :placeholder="pageText('pages.feishuSecret')" size="small" />
                    </a-form-item>
                  </a-card>
                </a-col>

                <!-- 企业微信 -->
                <a-col :span="12">
                  <a-card :title="pageText('pages.wecomBot')" size="small" class="page-config-card-fixed-short">
                    <template #extra>
                      <a-button type="link" size="small" @click="handleTestPush('wxwork')" :loading="testPushLoading.wxwork">{{ pageText('pages.sendTest') }}</a-button>
                    </template>
                    <a-form-item label="Webhook URL" style="margin-bottom: 0;">
                      <a-input v-model:value="generalForm.wxwork.webhook_url" :placeholder="pageText('pages.wecomWebhookUrl')" size="small" />
                    </a-form-item>
                  </a-card>
                </a-col>

                <!-- Telegram -->
                <a-col :span="12">
                  <a-card :title="pageText('pages.telegramBot')" size="small" class="page-config-card-fixed-short">
                    <template #extra>
                      <a-button type="link" size="small" @click="handleTestPush('telegram')" :loading="testPushLoading.telegram">{{ pageText('pages.sendTest') }}</a-button>
                    </template>
                    <a-row :gutter="12">
                      <a-col :span="12">
                        <a-form-item label="Bot Token" style="margin-bottom: 0;">
                          <a-input v-model:value="generalForm.telegram.bot_token" placeholder="Bot Token" size="small" />
                        </a-form-item>
                      </a-col>
                      <a-col :span="12">
                        <a-form-item label="Chat ID" style="margin-bottom: 0;">
                          <a-input v-model:value="generalForm.telegram.chat_id" :placeholder="pageText('pages.recipientChatId')" size="small" />
                        </a-form-item>
                      </a-col>
                    </a-row>
                  </a-card>
                </a-col>
              </a-row>

              <!-- 3. Webhook & Email (较复杂的配置放下方) -->
              <a-row :gutter="16">
                <!-- 全局 Webhook -->
                <a-col :span="12">
                  <a-card data-setting-anchor="webhook" :title="pageText('pages.globalWebhookCallback')" size="small" class="page-config-card-fixed-tall">
                    <template #extra>
                      <a-button type="link" size="small" @click="handleTestPush('webhook')" :loading="testPushLoading.webhook">{{ pageText('pages.sendTest') }}</a-button>
                    </template>
                    <a-form-item :label="pageText('pages.callbackPostUrl')" class="page-field-spacing">
                      <a-input v-model:value="generalForm.webhook_url" :placeholder="pageText('pages.urlOfTheEndpointReceivingJsonData')" size="small" />
                    </a-form-item>
                    <a-form-item :label="pageText('pages.authenticationTokenHeader')" class="page-flush-bottom">
                      <a-input v-model:value="generalForm.webhook_token" :placeholder="pageText('pages.tokenForAuthentication')" size="small" />
                    </a-form-item>
                  </a-card>
                </a-col>

                <!-- SMTP 邮件 -->
                <a-col :span="12">
                  <a-card :title="pageText('pages.smtpEmailNotifications')" size="small" class="page-config-card-fixed-tall">
                    <template #extra>
                      <a-button type="link" size="small" @click="handleTestPush('email')" :loading="testPushLoading.email">{{ pageText('pages.sendTest') }}</a-button>
                    </template>
                    <a-row :gutter="12">
                      <a-col :span="16">
                        <a-form-item data-setting-anchor="email" :label="pageText('pages.smtpHost')" class="page-form-spacing">
                          <a-input v-model:value="generalForm.email.host" placeholder="smtp.qq.com" size="small" />
                        </a-form-item>
                      </a-col>
                      <a-col :span="8">
                        <a-form-item :label="pageText('tasks.port')" class="page-form-spacing">
                          <a-input-number v-model:value="generalForm.email.port" style="width: 100%;" size="small" />
                        </a-form-item>
                      </a-col>
                      <a-col :span="12">
                        <a-form-item :label="pageText('pages.senderUsername')" class="page-form-spacing">
                          <a-input v-model:value="generalForm.email.username" :placeholder="pageText('pages.senderAccount')" size="small" />
                        </a-form-item>
                      </a-col>
                      <a-col :span="12">
                        <a-form-item :label="pageText('pages.authorizationCodePassword')" class="page-form-spacing">
                          <a-input-password v-model:value="generalForm.email.password" :placeholder="pageText('pages.authorizationPassword')" size="small" />
                        </a-form-item>
                      </a-col>
                      <a-col :span="24">
                        <a-form-item :label="pageText('pages.recipientsToCommaSeparated')" class="page-flush-bottom">
                          <a-input v-model:value="generalForm.email.to" placeholder="receiver@test.com" size="small" />
                        </a-form-item>
                      </a-col>
                    </a-row>
                  </a-card>
                </a-col>
              </a-row>

            </a-form>
          </a-spin>
        </div>
      </a-tab-pane>
      <a-tab-pane key="system_backup" :tab="tabTitle(pageText('pages.backupTab'), false)">
        <BackupRestorePanel ref="backupPanelRef" />
      </a-tab-pane>
      <a-tab-pane key="system_update" :tab="tabTitle(pageText('pages.systemVersionAndUpdates'), false)">
        <SystemUpdatePanel ref="updatePanelRef" />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';
defineOptions({ name: 'SystemSettings' });
import {
  InfoCircleOutlined, ExclamationCircleOutlined,
  CheckCircleOutlined, CloseCircleOutlined
} from '@ant-design/icons-vue';
import { ref, reactive, onMounted, onUnmounted, onDeactivated, computed, nextTick, createVNode } from 'vue';
import { message, Modal } from 'ant-design-vue';
import request from '@/utils/request';
import { copyText } from '@/utils/clipboard';
import { useRoute, onBeforeRouteLeave } from 'vue-router';
import CdnRulePanel from '@/components/settings/CdnRulePanel.vue';
import BackupRestorePanel from '@/components/settings/BackupRestorePanel.vue';
import SystemUpdatePanel from '@/components/settings/SystemUpdatePanel.vue';

const { t: pageText, locale: pageLocale } = useI18n({ useScope: 'global' });

const cdnPanelRef = ref(null);
const backupPanelRef = ref(null);
const updatePanelRef = ref(null);

const route = useRoute();
const activeKey = ref('dictionary');
const dictSubTab = ref('dict');
const scanSubTab = ref('performance');
const loading = ref(false);
const searchLoading = ref(false);
const submitLoading = ref(false);
const deleteLoading = ref(false);

const menuSearch = ref('');
const menuOpenKeys = ref([]);
// ======================= 新建字典模块 =======================
const createDictDrawerVisible = ref(false);
const createDictTabKey = ref('manual');
const createDictLoading = ref(false);
const createDictForm = reactive({
  prefix: 'domain_',
  customName: '',
  content: '',
  fileList: []
});

const openCreateDictDrawer = () => {
  createDictDrawerVisible.value = true;
  if (selectedCategoryKeys.value.length > 0) {
    const key = selectedCategoryKeys.value[0];
    if (key.includes('子域名爆破')) {
      createDictForm.prefix = 'domain_';
    } else if (key.includes('智能子域爆破')) {
      createDictForm.prefix = 'altdns_';
    } else if (key.includes('目录文件泄露')) {
      createDictForm.prefix = 'file_';
    } else if (key.includes('端口扫描策略')) {
      createDictForm.prefix = 'port_';
    } else if (key.includes('DNS 解析')) {
      createDictForm.prefix = 'dnsserver_';
    } else if (key.includes('全局黑名单拦截')) {
      createDictForm.prefix = 'black';
    } else if (key.includes('group_brute_')) {
      createDictForm.prefix = 'username_';
    }
  }
};

const isCreateDictValid = computed(() => {
  return createDictForm.customName && /^[a-zA-Z0-9_]+$/.test(createDictForm.customName);
});

// 新建字典时按前缀自动路由：username_/password_ → 弱口令字典目录 (brute_dict)，其余 → 资产字典目录 (dictionary)
const isBruteCreatePrefix = computed(() => {
  return createDictForm.prefix === 'username_' || createDictForm.prefix === 'password_';
});
const createDictApiBase = computed(() => isBruteCreatePrefix.value ? '/api/brute_dict' : '/api/dictionary');

const resetCreateDictForm = () => {
  createDictForm.prefix = 'domain_';
  createDictForm.customName = '';
  createDictForm.content = '';
  createDictForm.fileList = [];
  createDictTabKey.value = 'manual';
};

// ======================= 字典后台导入全受控轮询器 =======================
const activeDictPollTimers = ref(new Set());

const clearAllDictPollTimers = () => {
  for (const timer of activeDictPollTimers.value) {
    clearInterval(timer);
  }
  activeDictPollTimers.value.clear();
};

const handlePasteContent = (e) => {
  const clipboardData = e.clipboardData || window.clipboardData;
  if (!clipboardData) return;
  const pastedText = clipboardData.getData('text') || '';
  if (pastedText.length > 2 * 1024 * 1024) {
    e.preventDefault();
    message.warning(pageText('pages.pasteBlockedContentIsTooLargeSizeMbRendering', { size: (pastedText.length / 1024 / 1024).toFixed(1) }), 6);
  } else if (pastedText.length > 500 * 1024) {
    message.info(pageText('pages.largeContentDetectedSizeMbCreatingTheDictionaryWill', { size: (pastedText.length / 1024 / 1024).toFixed(1) }));
  }
};

const handlePasteNewEntries = (e) => {
  const clipboardData = e.clipboardData || window.clipboardData;
  if (!clipboardData) return;
  const pastedText = clipboardData.getData('text') || '';
  if (pastedText.length > 2 * 1024 * 1024) {
    e.preventDefault();
    message.warning(pageText('pages.pasteBlockedContentIsTooLargeSizeMbRenderingThis', { size: (pastedText.length / 1024 / 1024).toFixed(1) }), 6);
  }
};

const startDictPolling = (taskId, targetName, apiBase, isBrute, isAppend = false) => {
  const hideMsg = message.loading(pageText('pages.dictionaryNameModeImportRunningInTheBackgroundYou', { name: targetName, mode: isAppend ? pageText('pages.append') : '' }), 0);
  let pollCount = 0;
  const MAX_POLL_COUNT = 300; // 最多轮询 300 次 (10分钟)
  let lastUpdateTime = null;
  let staleCount = 0;
  let consecutive404Count = 0;
  const MAX_CONSECUTIVE_404 = 5; // 容忍最多 5 次（10秒）404 排队/延迟窗口

  const timer = setInterval(async () => {
    pollCount++;
    if (pollCount > MAX_POLL_COUNT) {
      clearInterval(timer);
      activeDictPollTimers.value.delete(timer);
      hideMsg();
      message.warning(pageText('pages.dictionaryNameIsTakingLongerToImportForegroundPolling', { name: targetName }));
      return;
    }

    try {
      const statusRes = await request.get(`${apiBase}/upload_status`, { params: { task_id: taskId } });
      if (statusRes.code === 200 && statusRes.data) {
        consecutive404Count = 0; // 重置 404 计数
        const data = statusRes.data;

        // 排队等待状态
        if (data.status === 'pending') {
          return;
        }

        // 心跳停滞检测：若连续 60 次轮询（120秒）且 update_time 毫无变化，提示可能中断并熔断
        if (data.status === 'processing') {
          if (data.update_time && data.update_time === lastUpdateTime) {
            staleCount++;
            if (staleCount >= 60) {
              clearInterval(timer);
              activeDictPollTimers.value.delete(timer);
              hideMsg();
              message.warning(pageText('pages.dictionaryNameImportHasNotReportedProgressForAn', { name: targetName }));
              return;
            }
          } else {
            lastUpdateTime = data.update_time;
            staleCount = 0;
          }
        }

        if (data.status === 'completed') {
          clearInterval(timer);
          activeDictPollTimers.value.delete(timer);
          hideMsg();
          message.success(pageText('pages.dictionaryNameModeImportCompletedAddedAddedDuplicatesSkipped', { name: targetName, mode: isAppend ? pageText('pages.append') : '', added: data.inserted_lines, duplicates: data.ignored_lines }));
          if (isBrute) {
            fetchBruteDictList(false);
          } else {
            fetchDictList(false);
          }
          if (isAppend) {
            fetchPreview(targetName);
          }
        } else if (data.status === 'error') {
          clearInterval(timer);
          activeDictPollTimers.value.delete(timer);
          hideMsg();
          message.error(pageText('pages.failedToImportNameReasonLabel2', { name: targetName, reason: data.message || pageText('tasks.unknownError') }));
        }
      } else if (statusRes.code === 404) {
        // 允许排队空窗期容错：Worker 启动消费前可能存在短暂 404
        consecutive404Count++;
        if (consecutive404Count >= MAX_CONSECUTIVE_404) {
          clearInterval(timer);
          activeDictPollTimers.value.delete(timer);
          hideMsg();
          message.warning(pageText('pages.importTaskStateWasLostReasonRefreshAndVerify', { reason: statusRes.message || pageText('pages.taskNotFound') }));
        }
      } else {
        // 任务不存在或状态异常
        clearInterval(timer);
        activeDictPollTimers.value.delete(timer);
        hideMsg();
        message.warning(pageText('pages.unexpectedImportTaskStateReasonRefreshAndVerifyThe', { reason: statusRes.message || pageText('tasks.unknownError') }));
      }
    } catch (e) {
      // 忽略轮询网络抖动
    }
  }, 2000);

  activeDictPollTimers.value.add(timer);
};

const handleCreateDictManual = async () => {
  let targetName = `${createDictForm.prefix}${createDictForm.customName}.txt`;
  const rawContent = createDictForm.content || '';

  createDictLoading.value = true;
  try {
    // 智能流式分流：若内容大于 500KB 或超过 5000 行，自动打包为 Blob 走后台异步 upload_large 通道，
    // 避免超大 JSON 请求造成 Gunicorn Worker 线程长时间同步阻塞与 120s 超时
    const lineCount = (rawContent.match(/\n/g) || []).length;
    if (rawContent.length > 500 * 1024 || lineCount > 5000) {
      const blob = new Blob([rawContent], { type: 'text/plain' });
      const formData = new FormData();
      formData.append('file', blob, targetName);
      formData.append('name', targetName);

      const res = await request.post(`${createDictApiBase.value}/upload_large`, formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
        timeout: 300000
      });
      if (res.code === 200) {
        message.info(pageText('pages.largeDictionaryAboutCountLinesUsingTheBackgroundStreaming', { count: lineCount + 1 }));
        const apiBase = createDictApiBase.value;
        const isBrute = isBruteCreatePrefix.value;
        createDictDrawerVisible.value = false;
        resetCreateDictForm();
        startDictPolling(res.task_id, targetName, apiBase, isBrute, false);
        return;
      } else {
        message.error(res.message || pageText('pages.failedToCreate'));
        return;
      }
    }

    const res = await request.post(`${createDictApiBase.value}/create`, {
      name: targetName,
      content: rawContent
    });
    if (res.code === 200) {
      message.success(pageText('pages.dictionaryNameCreated', { name: targetName }));
      const isBrute = isBruteCreatePrefix.value;
      createDictDrawerVisible.value = false;
      resetCreateDictForm();
      if (isBrute) {
        fetchBruteDictList();
      } else {
        fetchDictList();
      }
    } else {
      message.error(res.message || pageText('pages.failedToCreate'));
    }
  } catch (error) {
    message.error(pageText('pages.dictionaryCreationRequestFailed'));
  } finally {
    createDictLoading.value = false;
  }
};

const handleCreateDictUploadCancel = () => {
  if (createDictLoading.value) {
    message.warning(pageText('pages.uploadInProgressPleaseWaitBeforeCanceling'));
    return;
  }
  createDictDrawerVisible.value = false;
  resetCreateDictForm();
};

const handleCreateDictUpload = async () => {
  let targetName = `${createDictForm.prefix}${createDictForm.customName}.txt`;

  const file = createDictForm.fileList[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', targetName);

  createDictLoading.value = true;
  try {
    const res = await request.post(`${createDictApiBase.value}/upload_large`, formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 300000
    });
    if (res.code === 200) {
      const apiBase = createDictApiBase.value;
      const isBrute = isBruteCreatePrefix.value;
      createDictDrawerVisible.value = false;
      resetCreateDictForm();
      startDictPolling(res.task_id, targetName, apiBase, isBrute, false);
    } else {
      message.error(res.message || pageText('pages.uploadFailedLabel2'));
    }
  } catch (error) {
    message.error(pageText('pages.uploadRequestFailed'));
  } finally {
    createDictLoading.value = false;
  }
};

// ======================= 追加字典逻辑 =======================
const appendDrawerVisible = ref(false);
const appendMode = ref('text');

// 上传字典状态
// 执行大文件上传
const handleLargeUpload = async (info) => {
  const file = info.file;
  if (!file) return;

  const formData = new FormData();
  formData.append('file', file);
  formData.append('name', unifiedSelectedName.value);

  const targetName = unifiedSelectedName.value;
  const currentType = unifiedSelectedType.value;

  const uploadUrl = currentType === 'asset' ? '/api/dictionary/upload_large' : '/api/brute_dict/upload_large';
  const apiBase = currentType === 'asset' ? '/api/dictionary' : '/api/brute_dict';
  const isBrute = currentType !== 'asset';

  try {
    const res = await request.post(uploadUrl, formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      },
      timeout: 300000
    });

    if (res.code === 200) {
      appendDrawerVisible.value = false;
      startDictPolling(res.task_id, targetName, apiBase, isBrute, true);
    } else {
      message.error(res.message || pageText('pages.uploadFailedLabel2'));
    }
  } catch (error) {
    message.error(pageText('pages.networkOrServerError'));
  }
};
const searchDrawerVisible = ref(false);
const batchDeleteEntries = ref('');

const generalLoading = ref(false);
const generalSaveLoading = ref(false);
const activePushPanels = ref(['dingding', 'feishu', 'wxwork', 'telegram', 'email', 'webhook']);

const testPushLoading = reactive({
  dingding: false,
  feishu: false,
  wxwork: false,
  telegram: false,
  email: false,
  webhook: false
});

const handleTestPush = async (type) => {
  let config = {};
  if (type === 'webhook') {
    config = {
      webhook_url: generalForm.value.webhook_url,
      webhook_token: generalForm.value.webhook_token
    };
  } else {
    config = generalForm.value[type];
  }
  
  testPushLoading[type] = true;
  try {
    const res = await request.post('/api/system_config/test_push', {
      push_type: type,
      config: config
    });
    
    if (res.code === 200) {
      message.success(res.message || pageText('pages.testNotificationSent'));
    } else {
      message.error(res.message || pageText('pages.failedToSendTestNotification'));
    }
  } catch (error) {
    message.error(pageText('pages.testRequestFailedCheckTheNetworkConnection'));
    console.error(error);
  } finally {
    testPushLoading[type] = false;
  }
};

// ======================= 全局配置脏状态追踪 (P0) =======================
// 每个一级 Tab 对应一个配置分组。用户只提交"当前分组内发生变更的字段"，
// 避免在 A 页改完未保存、切到 B 页点保存时用 B 页旧值覆盖 A 页修改。
const GENERAL_FIELD_GROUPS = {
  api_config: ['fofa_key', 'fofa_url', 'fofa_max_page', 'fofa_page_size', 'github_token',
               'tyc_id', 'tyc_token', 'so_search_cookie', 'bing_search_cookie', 'query_plugin_config'],
  message_push: ['push_options', 'dingding', 'feishu', 'wxwork', 'telegram', 'email',
                 'webhook_url', 'webhook_token'],
  system_general: ['proxy_url', 'port_top_10', 'domain_brute_concurrent', 'alt_dns_concurrent',
                   'auth', 'api_key'],
};

// 首轮配置基准同步完成标记：在挂载并首轮同步基准前，所有脏状态判定恒为 false / {}，
// 杜绝首屏因接口异步返回耗时差（如 Celery inspect 阻塞 1s）造成的虚假未保存提示与路由拦截。
const isConfigInitialized = ref(false);

// 打开页面时保存的基线快照，用于 diff 出真正变更的字段
const generalBaseline = ref({});

const cloneDeep = (val) => (val === undefined ? undefined : JSON.parse(JSON.stringify(val)));

// 生效值视图：仅含可编辑且非敏感字段，用于回显"当前系统实际生效值"
const mergedConfig = ref({});
const credentialStatus = ref({});
const capacityInfo = ref({});

const captureBaseline = () => {
  generalBaseline.value = cloneDeep(generalForm.value);
};

// 以基线为准逐字段比较，得出所有变更字段（跨分组）
const changedFields = computed(() => {
  const base = generalBaseline.value;
  const cur = generalForm.value;
  const changed = {};
  const collect = (groupKeys) => {
    groupKeys.forEach((key) => {
      if (JSON.stringify(cur[key]) !== JSON.stringify(base[key])) {
        changed[key] = cur[key];
      }
    });
  };
  Object.values(GENERAL_FIELD_GROUPS).forEach(collect);
  return changed;
});

// 按分组切出各自待提交的字段
const pendingByGroup = computed(() => {
  const out = {};
  const changed = changedFields.value;
  Object.entries(GENERAL_FIELD_GROUPS).forEach(([group, keys]) => {
    const subset = {};
    keys.forEach((key) => {
      if (Object.prototype.hasOwnProperty.call(changed, key)) subset[key] = changed[key];
    });
    out[group] = subset;
  });
  return out;
});

// 安全策略与性能配置走独立接口，各自维护基线
const securityBaseline = ref({ blackIpsText: '', forbiddenDomainsText: '' });
const performanceBaseline = ref({
  celery_heavy_concurrency: 1,
  celery_light_concurrency: 1,
  osint_concurrency: 1,
  github_concurrency: 1,
});

const isSecurityDirty = computed(() =>
  securityForm.value.blackIpsText !== securityBaseline.value.blackIpsText
  || securityForm.value.forbiddenDomainsText !== securityBaseline.value.forbiddenDomainsText);

const isPerformanceDirty = computed(() => (
  performanceForm.value.celery_heavy_concurrency !== performanceBaseline.value.celery_heavy_concurrency
  || performanceForm.value.celery_light_concurrency !== performanceBaseline.value.celery_light_concurrency
  || performanceForm.value.osint_concurrency !== performanceBaseline.value.osint_concurrency
  || performanceForm.value.github_concurrency !== performanceBaseline.value.github_concurrency));

// 全局是否存在未保存改动（含安全策略与性能配置两个独立接口）
const hasUnsavedChanges = computed(() => {
  if (typeof isConfigInitialized !== 'undefined' && !isConfigInitialized.value) return false;
  return (
    Object.keys(changedFields.value).length > 0
    || isSecurityDirty.value
    || isPerformanceDirty.value
  );
});

// 未保存改动总数，用于页头常驻提示
const unsavedCount = computed(() => {
  if (typeof isConfigInitialized !== 'undefined' && !isConfigInitialized.value) return 0;
  const detail = Object.keys(changedFields.value).length;
  return detail
    + (isSecurityDirty.value ? 1 : 0)
    + (isPerformanceDirty.value ? 1 : 0);
});

// ======================= 设置项索引与搜索 (P2) =======================
// 每条索引把「用户会搜的词」映射到「Tab + 锚点」，keywords 覆盖中英文与别名，
// 让用户不必记住设置项藏在哪个 Tab（这是 L1 定位成本的主要来源）。
const SETTINGS_INDEX = [
  // 全局凭据总览（不在任何 Tab 内，锚点指向页面顶部的折叠条）
  { tab: 'api_config', get tabLabel() { return pageText('pages.globalOverview'); }, get label() { return pageText('pages.credentialConfigurationOverview'); }, anchor: 'credential_status',
    get desc() { return pageText('pages.viewTheConfigurationStatusOfAll12CredentialsAcross'); },
    keywords: ['凭据', '配置状态', '已配置', '未配置', 'credential', 'token', '密钥', '总览', "全站总览 / 凭据配置状态总览 / 一屏查看全部 12 项凭据的配置状态（跨多个 Tab）"] },
  // 资产测绘与情报
  { tab: 'api_config', get tabLabel() { return pageText('pages.assetDiscoveryAndIntelligence'); }, get label() { return pageText('pages.fofaDiscoveryCredentials'); }, anchor: 'fofa',
    get desc() { return pageText('pages.fofaUrlApiKeyAndQueryPageLimits'); }, keywords: ['fofa', '空间测绘', 'api key', '情报', "资产测绘与情报 / FOFA 空间测绘凭据 / FOFA URL / KEY 与查询页数"] },
  { tab: 'api_config', get tabLabel() { return pageText('pages.assetDiscoveryAndIntelligence'); }, get label() { return pageText('pages.tianyanchaEnterpriseDiscoveryCredentials'); }, anchor: 'tyc',
    get desc() { return pageText('pages.xTycidXAuthTokenFallsBackToMiit'); }, keywords: ['天眼查', 'tyc', '股权穿透', '企业', "资产测绘与情报 / 天眼查企业测绘凭据 / X-Tycid / X-Auth-Token，未配置时降级为工信部 ICP"] },
  { tab: 'api_config', get tabLabel() { return pageText('pages.assetDiscoveryAndIntelligence'); }, label: 'GitHub Token', anchor: 'github_token',
    get desc() { return pageText('pages.requiredForCodeLeakMonitoringAndCveTracking'); }, keywords: ['github', 'token', 'pat', '监控', '泄露', 'cve', "资产测绘与情报 / GitHub Token / 代码泄露监控与 CVE 追踪的硬依赖"] },
  { tab: 'api_config', get tabLabel() { return pageText('pages.assetDiscoveryAndIntelligence'); }, get label() { return pageText('pages.searchEngineCookies'); }, anchor: 'search_cookie',
    get desc() { return pageText('pages.cookiesUsedToAccess360SearchAndBingSearch'); }, keywords: ['cookie', '360', '必应', 'bing', '搜索', '反爬', "资产测绘与情报 / 搜索引擎 Cookie / 360 搜索与必应搜索的反爬 Cookie"] },
  { tab: 'api_config', get tabLabel() { return pageText('pages.assetDiscoveryAndIntelligence'); }, get label() { return pageText('pages.domainCollectionPlugins'); }, anchor: 'query_plugin',
    get desc() { return pageText('pages.queryPluginDataSourceSwitchesAndCredentials'); }, keywords: ['插件', 'plugin', 'quake', 'hunter', 'virustotal', '扩展', "资产测绘与情报 / 域名收集扩展插件 / QUERY_PLUGIN 各数据源开关与凭据"] },
  // 字典与规则库
  { tab: 'dictionary', get tabLabel() { return pageText('pages.dictionariesAndRules'); }, get label() { return pageText('pages.textDictionaries'); }, anchor: 'dict',
    get desc() { return pageText('pages.manageSubdomainPortDirectoryAndCredentialDictionaries'); }, keywords: ['字典', 'dict', '弱口令', '爆破', '子域名', '端口', '目录', "字典与规则库 / 通用文本字典 / 子域名 / 端口 / 目录 / 弱口令字典管理"] },
  { tab: 'dictionary', get tabLabel() { return pageText('pages.dictionariesAndRules'); }, get label() { return pageText('pages.cdnFingerprintsAndRulesLabel2'); }, anchor: 'cdn',
    get desc() { return pageText('pages.cnameAndIpCidrRulesForIdentifyingCdns'); }, keywords: ['cdn', 'cname', 'cidr', '特征', '规则', "字典与规则库 / CDN 特征与规则 / CNAME 与 IP CIDR 特征库，用于 CDN 识别"] },
  // 扫描与并发
  { tab: 'performance', get tabLabel() { return pageText('pages.scanningAndConcurrencyQueueConcurrency'); }, get label() { return pageText('pages.taskQueueConcurrencyWorkerProcesses'); }, anchor: 'performance',
    get desc() { return pageText('pages.memoryConstrainedWorkerProcessCountsForHeavyLightAnd'); },
    keywords: ['并发', '线程', '性能', '队列', 'celery', 'worker', '进程', '扩容', '缩容', "扫描与并发 · 队列并发 / 任务队列并发（Worker 进程数） / 重任务 / 轻任务 / OSINT 的 Worker 进程数，受内存约束"] },
  { tab: 'security', get tabLabel() { return pageText('pages.scanningAndConcurrencySecurityPolicy'); }, get label() { return pageText('pages.securityPolicyIpBlocklist'); }, anchor: 'security',
    get desc() { return pageText('pages.ipRangesExcludedFromScanningIncludingSystemDefaults'); }, keywords: ['黑名单', 'blacklist', 'ip', 'cidr', '禁止', '安全策略', "扫描与并发 · 安全策略 / 安全策略：IP 黑名单 / 禁止扫描的 IP 段（含系统默认值）"] },
  { tab: 'security', get tabLabel() { return pageText('pages.scanningAndConcurrencySecurityPolicy'); }, get label() { return pageText('pages.securityPolicyExcludedDomains'); }, anchor: 'security',
    get desc() { return pageText('pages.domainSuffixesExcludedFromScanningEGGovCn'); }, keywords: ['禁止域名', '域名', '禁扫', '安全策略', 'gov.cn', "扫描与并发 · 安全策略 / 安全策略：禁止扫描域名 / 按后缀匹配的禁扫域名（如 gov.cn）"] },
  { tab: 'system_general', get tabLabel() { return pageText('pages.scanningAndConcurrencyAdvancedScanning'); }, get label() { return pageText('pages.systemProxy'); }, anchor: 'proxy',
    get desc() { return pageText('pages.proxyUrlOutboundProxyForScanningTraffic'); }, keywords: ['代理', 'proxy', '出口', 'http_url', "扫描与并发 · 高级扫描 / 系统代理地址 / PROXY_URL，扫描流量出口代理"] },
  { tab: 'system_general', get tabLabel() { return pageText('pages.scanningAndConcurrencyAdvancedScanning'); }, get label() { return pageText('pages.dnsQueryConcurrencyWithinATask'); }, anchor: 'brute_concurrent',
    get desc() { return pageText('pages.massdnsQueryConcurrencyForRegularAndMutationDiscoveryThis'); },
    keywords: ['线程', '爆破', '并发', '并发度', 'dns', '域名', 'altdns', 'massdns', '发包', "扫描与并发 · 高级扫描 / DNS 发包并发度（单任务内） / 常规爆破与 DNS 智能生成的 massdns 发包并发度，非进程数"] },
  { tab: 'system_general', get tabLabel() { return pageText('pages.scanningAndConcurrencyAdvancedScanning'); }, get label() { return pageText('pages.top10PortList'); }, anchor: 'port_top_10',
    get desc() { return pageText('pages.defaultPortListUsedByFrontendTestOptions'); }, keywords: ['端口', 'port', 'top10', '扫描', "扫描与并发 · 高级扫描 / 端口扫描 Top 10 端口串 / 前端测试选项使用的默认端口列表"] },
  { tab: 'system_general', get tabLabel() { return pageText('pages.scanningAndConcurrencyAdvancedScanning'); }, get label() { return pageText('pages.infrastructureConnections'); }, anchor: 'infra',
    get desc() { return pageText('pages.readOnlyBrokerMongodbGeoipConnectionDetails'); }, keywords: ['mongodb', 'broker', 'celery', 'geoip', '数据库', '基础设施', "扫描与并发 · 高级扫描 / 基础服务连接信息 / 只读展示 Broker / MongoDB / GeoIP 路径"] },
  // 通知与系统
  { tab: 'message_push', get tabLabel() { return pageText('pages.notificationsAndCallbacks'); }, get label() { return pageText('pages.subscribedEventTypes'); }, anchor: 'push_options',
    get desc() { return pageText('pages.chooseWhichEventsSendNotifications'); }, keywords: ['订阅', '推送', '通知', '告警', '消息类型', "通知与回调 / 订阅消息类型 / 选择哪些事件触发推送"] },
  { tab: 'message_push', get tabLabel() { return pageText('pages.notificationsAndCallbacks'); }, get label() { return pageText('pages.dingtalkFeishuWecomTelegramBots'); }, anchor: 'im',
    get desc() { return pageText('pages.messagingNotificationChannelsAndTestDelivery'); }, keywords: ['钉钉', 'dingding', '飞书', 'feishu', '企业微信', 'wxwork', 'telegram', '机器人', 'webhook', "通知与回调 / 钉钉 / 飞书 / 企微 / Telegram 机器人 / 即时通讯告警通道与测试发送"] },
  { tab: 'message_push', get tabLabel() { return pageText('pages.notificationsAndCallbacks'); }, get label() { return pageText('pages.globalWebhookCallbackLabel2'); }, anchor: 'webhook',
    get desc() { return pageText('pages.postJsonToAnExternalEndpointWhenATask'); }, keywords: ['webhook', '回调', 'callback', 'post', '接口', "通知与回调 / 系统全局 Webhook 回调 / 任务完成后向外部接口 POST JSON"] },
  { tab: 'message_push', get tabLabel() { return pageText('pages.notificationsAndCallbacks'); }, get label() { return pageText('pages.smtpEmailNotificationsLabel2'); }, anchor: 'email',
    get desc() { return pageText('pages.mailServerSenderAndRecipientConfiguration'); }, keywords: ['邮件', 'email', 'smtp', '推送', "通知与回调 / SMTP 邮件推送 / 邮件服务器、发件人与收件人配置"] },
  { tab: 'system_general', get tabLabel() { return pageText('pages.scanningAndConcurrencyAdvancedScanning'); }, get label() { return pageText('pages.apiAuthentication'); }, anchor: 'auth',
    get desc() { return pageText('pages.swaggerApiAuthenticationAndApiToken'); }, keywords: ['api', '认证', 'auth', 'token', 'swagger', '安全', "扫描与并发 · 高级扫描 / API 安全认证机制 / Swagger API 认证开关与 API Token"] },
  { tab: 'system_backup', get tabLabel() { return pageText('pages.backupTab'); }, get label() { return pageText('pages.backupTitle'); }, anchor: 'backup',
    get desc() { return pageText('pages.backupIndexDescription'); }, keywords: ['备份', '恢复', 'backup', 'restore', '导出', '导入', '快照', '全量备份', '迁移'] },
  { tab: 'system_update', get tabLabel() { return pageText('pages.systemVersionAndUpdates'); }, get label() { return pageText('pages.systemVersionAndUpdates'); }, anchor: 'update',
    get desc() { return pageText('pages.versionComparisonReleaseNotesAndSystemUpdates'); }, keywords: ['版本', '更新', '升级', 'update', 'version', 'changelog', "系统版本与更新 / 系统版本与更新 / 版本比对、更新日志与一键更新"] },
];

const settingsKeyword = ref('');
const highlightedAnchor = ref('');

const settingsSearchResults = computed(() => {
  const kw = settingsKeyword.value.trim().toLowerCase();
  if (!kw) return [];
  return SETTINGS_INDEX.filter((item) => {
    const haystack = [item.label, item.desc, item.tabLabel, ...(item.keywords || [])]
      .join(' ').toLowerCase();
    return haystack.includes(kw);
  });
});

const scrollAndFlashAnchor = (selector, retries = 3) => {
  nextTick(() => {
    const el = document.querySelector(selector);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
      el.classList.add('arl-anchor-flash');
      setTimeout(() => el.classList.remove('arl-anchor-flash'), 2200);
    } else if (retries > 0) {
      setTimeout(() => scrollAndFlashAnchor(selector, retries - 1), 60);
    }
  });
};

// 点击搜索结果：切到目标 Tab（含嵌套子 Tab），并把锚点元素滚动进视野 + 短暂高亮
const jumpToSetting = (item) => {
  // 三组 Tab 均使用嵌套子结构：需同时切换外层 activeKey 与内层子 Tab
  if (item.tab === 'dictionary') {
    activeKey.value = 'dictionary';
    dictSubTab.value = item.anchor === 'cdn' ? 'cdn' : 'dict';
  } else if (item.tab === 'security' || item.tab === 'system_general') {
    activeKey.value = 'performance';
    scanSubTab.value = item.tab;
  } else if (item.tab === 'performance') {
    activeKey.value = 'performance';
    scanSubTab.value = 'performance';
  } else {
    activeKey.value = item.tab;
  }
  settingsKeyword.value = '';
  highlightedAnchor.value = item.anchor;
  // 全局凭据总览位于 Tab 之外且默认折叠：需先展开再滚动
  if (item.anchor === 'credential_status') {
    credExpanded.value = true;
  }
  const isSubTab = item.anchor === 'cdn' || item.anchor === 'dict';
  let selector;
  if (isSubTab) {
    selector = '.dict-sub-tabs';
  } else if (item.anchor === 'credential_status') {
    selector = '.arl-global-cred';
  } else {
    selector = `[data-setting-anchor="${item.anchor}"]`;
  }
  scrollAndFlashAnchor(selector);
};

// 两套并发指标互相指引，避免用户在同一页找不到对应字段
const goToBruteConcurrent = () => {
  activeKey.value = 'performance';
  scanSubTab.value = 'system_general';
  scrollAndFlashAnchor('[data-setting-anchor="brute_concurrent"]');
};

const goToQueueConcurrency = () => {
  activeKey.value = 'performance';
  scanSubTab.value = 'performance';
  scrollAndFlashAnchor('[data-setting-anchor="performance"]');
};

// 定位第一个存在未保存改动的 Tab，供提示条一键跳转
const firstDirtyTabKey = computed(() => {
  if (isSecurityDirty.value || isPerformanceDirty.value || Object.keys(pendingByGroup.value.system_general || {}).length > 0) {
    return 'performance';
  }
  const order = ['api_config', 'message_push'];
  for (const group of order) {
    if (Object.keys(pendingByGroup.value[group] || {}).length > 0) return group;
  }
  return 'api_config';
});

const goToFirstDirty = () => {
  if (isPerformanceDirty.value) {
    activeKey.value = 'performance';
    scanSubTab.value = 'performance';
    return;
  }
  if (isSecurityDirty.value) {
    activeKey.value = 'performance';
    scanSubTab.value = 'security';
    return;
  }
  if (Object.keys(pendingByGroup.value.system_general || {}).length > 0) {
    activeKey.value = 'performance';
    scanSubTab.value = 'system_general';
    return;
  }
  if (Object.keys(pendingByGroup.value.api_config || {}).length > 0) {
    activeKey.value = 'api_config';
    return;
  }
  if (Object.keys(pendingByGroup.value.message_push || {}).length > 0) {
    activeKey.value = 'message_push';
    return;
  }
  activeKey.value = 'api_config';
};

// 关闭/刷新浏览器窗口时兜底拦截（系统级，无法自定义文案）
const handleBeforeUnload = (e) => {
  if (!hasUnsavedChanges.value) return;
  e.preventDefault();
  e.returnValue = '';
};

// Tab 标题挂角标，让"未保存"成为常驻可见状态而非点保存才发现
const tabTitle = (base, dirty) => (dirty ? `${base} ·` : base);

// 分组保存：只提交本组变更字段
const saveGeneralGroup = async (group, loadingRef, successText) => {
  const payload = pendingByGroup.value[group] || {};
  if (Object.keys(payload).length === 0) {
    message.info(pageText('pages.noUnsavedChangesInThisGroup'));
    return false;
  }
  loadingRef.value = true;
  try {
    const res = await request.post('/api/system_config/general', payload);
    if (res.code === 200) {
      message.success(successText || pageText('pages.changesSavedCount', { count: Object.keys(payload).length }));
      // 仅把本组已提交的字段写回基线，其他分组的未保存改动继续保持脏状态
      Object.keys(payload).forEach((key) => {
        generalBaseline.value[key] = cloneDeep(payload[key]);
      });
      return true;
    }
    message.error(res.message || pageText('pages.failedToSaveLabel2'));
    return false;
  } catch (error) {
    message.error(pageText('pages.failedToSaveConfigurationLabel2'));
    console.error(error);
    return false;
  } finally {
    loadingRef.value = false;
  }
};

// 凭据状态展示模型：label 为面向用户的业务名称，required 标记"不配就没法用"的硬依赖
const CREDENTIAL_LABELS = [
  { key: 'github_token', label: 'GitHub Token', required: true },
  { key: 'fofa_key', label: 'FOFA KEY', required: false },
  { key: 'tyc_id', get label() { return pageText('pages.tianyanchaId'); }, required: false },
  { key: 'tyc_token', get label() { return pageText('pages.tianyanchaToken'); }, required: false },
  { key: 'so_search_cookie', get label() { return pageText('pages.360SearchCookie'); }, required: false },
  { key: 'bing_search_cookie', get label() { return pageText('pages.bingSearchCookie'); }, required: false },
  { key: 'dingding_access_token', get label() { return pageText('pages.dingtalkBotLabel2'); }, required: false },
  { key: 'feishu_webhook', get label() { return pageText('pages.feishuBotLabel2'); }, required: false },
  { key: 'wx_work_webhook', get label() { return pageText('pages.wecomBotLabel2'); }, required: false },
  { key: 'tg_bot_token', get label() { return pageText('pages.telegramBotLabel2'); }, required: false },
  { key: 'email_username', get label() { return pageText('pages.smtpEmail'); }, required: false },
  { key: 'api_key', label: 'API Token', required: false },
];

const credentialOverview = computed(() => CREDENTIAL_LABELS.map((meta) => ({
  ...meta,
  configured: Boolean((credentialStatus.value[meta.key] || {}).configured),
})));

// 全局凭据条默认折叠：12 项明细常驻首屏会挤占视觉空间
const credExpanded = ref(false);

const configuredCredentialCount = computed(() =>
  credentialOverview.value.filter((c) => c.configured).length);

// 仅"必需但未配置"的项才值得红色告警；可选项缺失属正常状态
const missingRequiredCredentials = computed(() =>
  credentialOverview.value.filter((c) => c.required && !c.configured));

const fetchMergedConfig = async () => {
  try {
    const res = await request.get('/api/system_config/merged_general');
    if (res.code === 200 && res.data) {
      mergedConfig.value = res.data;
      credentialStatus.value = res.data.credentials || {};
      // 只读字段以生效值为准回显（如 FOFA URL、线程数），让用户看到真实生效状态
      ['fofa_url', 'fofa_max_page', 'fofa_page_size', 'proxy_url', 'port_top_10',
       'domain_brute_concurrent', 'alt_dns_concurrent', 'auth'].forEach((key) => {
        if (res.data[key] !== undefined && res.data[key] !== null && res.data[key] !== '') {
          generalForm.value[key] = res.data[key];
          generalBaseline.value[key] = cloneDeep(res.data[key]);
        }
      });
    }
  } catch (e) {
    console.error('获取生效值失败', e);
  }
};

const fetchCapacityProbe = async () => {
  try {
    const res = await request.get('/api/system_config/capacity_probe');
    if (res.code === 200 && res.data) capacityInfo.value = res.data;
  } catch (e) {
    console.error('获取容量推荐值失败', e);
  }
};

const RECOMMENDED_FIELD_MAP = {
  heavy: 'celery_heavy_concurrency',
  light: 'celery_light_concurrency',
  osint: 'osint_concurrency',
  github: 'github_concurrency',
};

// 从「生效值」一键回填，降低"该填什么"的决策成本
const applyRecommended = (formRef, key) => {
  const rec = capacityInfo.value[`${key}_recommended`];
  if (rec) {
    const targetKey = RECOMMENDED_FIELD_MAP[key] || key;
    formRef.value[targetKey] = rec;
    message.success(pageText('pages.appliedRecommendedValueValue', { value: rec }));
  }
};

const generalForm = ref({
  celery_broker_url: '',
  mongo_url: '',
  mongo_db: '',
  geoip_city: '',
  geoip_asn: '',
  geoip_ip2region: '',
  
  fofa_key: '',
  fofa_url: '',
  fofa_max_page: 5,
  fofa_page_size: 2000,
  github_token: '',
  tyc_id: '',
  tyc_token: '',
  so_search_cookie: '',
  bing_search_cookie: '',
  
  proxy_url: '',
  port_top_10: '',
  domain_brute_concurrent: 300,
  alt_dns_concurrent: 1500,
  

  
  auth: false,
  api_key: '',
  
  webhook_url: '',
  webhook_token: '',
  
  dingding: { secret: '', access_token: '' },
  feishu: { webhook_url: '', secret: '' },
  wxwork: { webhook_url: '' },
  telegram: { bot_token: '', chat_id: '' },
  email: { host: '', port: 465, username: '', password: '', to: '' },
  query_plugin_config: {},
  push_options: ['task_complete', 'github_leak', 'github_cve', 'github_tools', 'github_hackers', 'asset_site']
});
captureBaseline();

const fetchGeneralConfig = async () => {
  generalLoading.value = true;
  try {
    const res = await request.get('/api/system_config/general');
    if (res.code === 200) {
      // 深度合并防止旧数据结构缺失导致报错
      generalForm.value = {
        ...generalForm.value,
        ...res.data,
        dingding: { ...generalForm.value.dingding, ...(res.data.dingding || {}) },
        feishu: { ...generalForm.value.feishu, ...(res.data.feishu || {}) },
        wxwork: { ...generalForm.value.wxwork, ...(res.data.wxwork || {}) },
        telegram: { ...generalForm.value.telegram, ...(res.data.telegram || {}) },
        email: { ...generalForm.value.email, ...(res.data.email || {}) }
      };
      // 先拉生效值回填只读项，再确立基线：否则回填本身会被误判为"用户改动"
      await fetchMergedConfig();
      captureBaseline();
    } else {
      message.error(res.message || pageText('pages.failedToLoadGeneralSystemConfiguration'));
      if (!isConfigInitialized.value) {
        captureBaseline();
      }
    }
  } catch (error) {
    message.error(pageText('pages.generalSystemConfigurationRequestFailed'));
    console.error(error);
    if (!isConfigInitialized.value) {
      captureBaseline();
    }
  } finally {
    generalLoading.value = false;
  }
};

// 三个 Tab 共用同一个提交入口，但只提交各自分组内的变更字段
const saveGeneralConfig = async (group = 'api_config', successText = '') =>
  saveGeneralGroup(group, generalSaveLoading, successText);

const dictList = ref([]);
const selectedDict = ref(null);
const bruteLoading = ref(false);
const bruteDictList = ref([]);  // [{name, size}, ...]

// ======================= 字典元数据配置 =======================
const ASSET_DICT_META = {
  'domain_2w.txt':       { get label() { return pageText('pages.mainSubdomainDictionary20000Entries'); }, group: '🌍 子域名爆破' },
  'altdnsdict.txt':      { get label() { return pageText('pages.subdomainMutationWords'); },   group: '🧠 智能子域爆破' },
  'dnsserver.txt':       { get label() { return pageText('pages.dnsResolverList'); },     group: '🌐 DNS 解析配置' },
  'file_top_200.txt':    { get label() { return pageText('pages.top200Paths'); },       group: '📂 目录文件泄露' },
  'file_top_2000.txt':   { get label() { return pageText('pages.top2000Paths'); },      group: '📂 目录文件泄露' },

  'port_top100.txt':     { get label() { return pageText('pages.top100CommonPorts'); },          group: '🔌 端口扫描策略' },
  'port_top1000.txt':    { get label() { return pageText('pages.top1000CommonPorts'); },         group: '🔌 端口扫描策略' },
  'port_custom.txt':     { get label() { return pageText('tasks.customPorts'); },             group: '🔌 端口扫描策略' },
  'port_all.txt':        { get label() { return pageText('tasks.allPorts165535'); },       group: '🔌 端口扫描策略' },
  'port_alive.txt':      { get label() { return pageText('pages.aliveProbePorts'); },      group: '🔌 端口扫描策略' },

  'blackdomain.txt':     { get label() { return pageText('pages.rootDomainExclusionDictionary'); },     group: '🛡️ 全局黑名单拦截' },
  'black_asset_site.txt':{ get label() { return pageText('pages.maliciousUnwantedWebsiteBlocklist'); },  group: '🛡️ 全局黑名单拦截' },
  'blackhexie.txt':      { get label() { return pageText('pages.sensitiveWordFilterDictionary'); },       group: '🛡️ 全局黑名单拦截' },
};

const assetMenuGroups = computed(() => {
  const groups = { '🌍 子域名爆破': [], '🧠 智能子域爆破': [], '📂 目录文件泄露': [], '🔌 端口扫描策略': [], '🌐 DNS 解析配置': [], '🛡️ 全局黑名单拦截': [] };
  
  const getGroupAndLabel = (dictName) => {
    if (ASSET_DICT_META[dictName]) {
      return { group: ASSET_DICT_META[dictName].group, label: ASSET_DICT_META[dictName].label };
    }
    if (dictName.startsWith('domain_')) return { group: '🌍 子域名爆破', label: dictName };
    if (dictName.startsWith('altdns_')) return { group: '🧠 智能子域爆破', label: dictName };
    if (dictName.startsWith('dnsserver_')) return { group: '🌐 DNS 解析配置', label: dictName };
    if (dictName.startsWith('file_')) return { group: '📂 目录文件泄露', label: dictName };
    if (dictName.startsWith('black')) return { group: '🛡️ 全局黑名单拦截', label: dictName };
    if (dictName.startsWith('port_')) return { group: '🔌 端口扫描策略', label: dictName };
    return null;
  };

  dictList.value.forEach(dict => {
    const meta = getGroupAndLabel(dict.name);
    if (!meta) return;
    
    if (!groups[meta.group]) groups[meta.group] = [];
    groups[meta.group].push({
      ...dict,
      title: meta.label
    });
  });
  return groups;
});

// 弱口令字典：按服务名分组（提取 username_ssh.txt → SSH）
const bruteSvcGroups = computed(() => {
  const groups = {};
  const SVC_LABEL = {
    ssh: 'SSH', ftp: 'FTP', mysql: 'MySQL', redis: 'Redis', mongodb: 'MongoDB',
    postgresql: 'PostgreSQL', sqlserver: 'SQL Server', rdp: 'RDP',
    tomcat: 'Tomcat', jenkins: 'Jenkins', gitlab: 'GitLab', grafana: 'Grafana',
    harbor: 'Harbor', nexus: 'Nexus', nacos: 'Nacos', apisix: 'APISIX',
    activemq: 'ActiveMQ', openfire: 'OpenFire', manageiq: 'ManageIQ',
    shiro: 'Shiro Key', imap: 'IMAP', pop3: 'POP3', smtp: 'SMTP',
    exchange: 'Exchange', csts: 'CSTS', clickhouse: 'ClickHouse',
    'alibaba-druid': 'Alibaba Druid'
  };
  bruteDictList.value.forEach(item => {
    // 通用弱口令字典（如 common_password.txt）归入独立分组
    if (item.name.startsWith('common_') && item.name.endsWith('.txt')) {
      if (!groups['通用弱口令']) groups['通用弱口令'] = [];
      groups['通用弱口令'].push(item);
      return;
    }
    const m = item.name.match(/^(?:username|password)_(.+)\.txt$/);
    if (!m) return;
    const svcKey = m[1];
    const svc = SVC_LABEL[svcKey] || svcKey.toUpperCase();
    if (!groups[svc]) groups[svc] = [];
    // username_* 排前面
    if (item.name.startsWith('username_')) groups[svc].unshift(item);
    else groups[svc].push(item);
  });
  return groups;
});

const formatDictionaryGroup = group => {
  const keys = {
    '🌍 子域名爆破': 'pages.dictionaryGroupDomains',
    '🧠 智能子域爆破': 'pages.dictionaryGroupMutations',
    '📂 目录文件泄露': 'pages.dictionaryGroupFiles',
    '🔌 端口扫描策略': 'pages.dictionaryGroupPorts',
    '🌐 DNS 解析配置': 'pages.dictionaryGroupDns',
    '🛡️ 全局黑名单拦截': 'pages.dictionaryGroupBlocklist'
  };
  return keys[group] ? pageText(keys[group]) : group;
};

const treeData = computed(() => {
  const data = [];
  // 资产字典分组
  Object.entries(assetMenuGroups.value).forEach(([group, items]) => {
    if (items.length) {
      const children = items.map(item => {
        const friendly = item.title && item.title !== item.name ? item.title : item.name;
        return {
          mainTitle: friendly,
          subTitle: item.name,
          key: `asset__${item.name}`,
          is_builtin: item.is_builtin
        };
      });
      data.push({ title: formatDictionaryGroup(group), key: `group_asset_${group}`, selectable: false, children });
    }
  });
  // 弱口令字典分组（将所有协议合并到一个大组，极大提升简洁度）
  const npocChildren = [];
  Object.entries(bruteSvcGroups.value).forEach(([svc, items]) => {
    if (items.length) {
      items.forEach(item => {
        // 自动将 username_/password_ 翻译为友好的中文前缀
        let friendlyPrefix = '';
        if (item.name.startsWith('username_')) friendlyPrefix = pageText('pages.usernameDictionary');
        else if (item.name.startsWith('password_')) friendlyPrefix = pageText('pages.passwordDictionary');
        else if (item.name.includes('common_')) friendlyPrefix = pageText('pages.commonCredentialDictionary');

        // 通用弱口令组内直接显示文件名，避免 "[通用弱口令] 通用弱口令" 冗余
        const mainTitle = svc === '通用弱口令'
          ? (item.name.includes('common_') ? item.name : `${friendlyPrefix || item.name}`)
          : `[${svc}] ${friendlyPrefix || item.name}`;

        npocChildren.push({
          mainTitle,
          subTitle: item.name,
          key: `brute__${item.name}`,
          is_builtin: item.is_builtin
        });
      });
    }
  });
  if (npocChildren.length > 0) {
    data.push({ title: pageText('pages.credentialDictionariesLabel2'), key: 'group_brute_all', children: npocChildren });
  }
  return data;
});

const filteredTreeData = computed(() => {
  if (!menuSearch.value.trim()) return treeData.value;
  const kw = menuSearch.value.toLowerCase();
  return treeData.value.map(group => {
    const matchedChildren = group.children.filter(c => 
      (c.mainTitle && c.mainTitle.toLowerCase().includes(kw)) || 
      (c.subTitle && c.subTitle.toLowerCase().includes(kw))
    );
    return { ...group, children: matchedChildren };
  }).filter(group => group.children.length > 0);
});

watch(treeData, (newVal) => {
  if (menuOpenKeys.value.length === 0 && newVal.length > 0) {
    menuOpenKeys.value = newVal.map(g => g.key);
  }
  if (newVal.length > 0 && (!selectedCategoryKeys.value.length || !newVal.find(g => g.key === selectedCategoryKeys.value[0]))) {
    selectedCategoryKeys.value = [newVal[0].key];
  }
}, { immediate: true });


const handleAppendAndClose = async () => {
  const ok = await handleAppend();
  if (ok) appendDrawerVisible.value = false;
};

const handleDeleteBatchCustom = () => {
  if (!batchDeleteEntries.value.trim()) return;
  const entryCount = batchDeleteEntries.value.split('\n').map(x => x.trim()).filter(Boolean).length;
  Modal.confirm({
    title: pageText('pages.deleteDictionaryEntries'),
    icon: createVNode(ExclamationCircleOutlined),
    content: pageText('pages.deleteTheSubmittedEntriesCountFromTheCurrentDictionary', { count: entryCount }),
    okText: pageText('tasks.confirmDeletion'),
    okButtonProps: { danger: true },
    cancelText: pageText('assets.cancel'),
    onOk: async () => {
      const ok = await deleteEntries(batchDeleteEntries.value);
      if (ok) {
        batchDeleteEntries.value = '';
        searchDrawerVisible.value = false;
      }
      return ok;
    }
  });
};

// 分类选择状态（默认对齐首个分类的唯一分组 key）
const selectedCategoryKeys = ref(['group_asset_🌍 子域名爆破']);

const handleCategorySelect = ({ key }) => {
  selectedCategoryKeys.value = [key];
  menuSearch.value = '';
};

// 统一字典选择状态
const unifiedSelectedKeys = ref([]);
const unifiedSelectedType = ref('');  // 'asset' | 'brute'
const unifiedSelectedName = ref('');
const unifiedSelectedDesc = computed(() => {
  const name = unifiedSelectedName.value;
  if (unifiedSelectedType.value === 'asset') {
    return ASSET_DICT_META[name]?.label || pageText('pages.assetDiscoveryDictionary');
  }
  if (unifiedSelectedType.value === 'brute') {
    return name.startsWith('username_') ? pageText('pages.usernameDictionaryCredentialChecks') : pageText('pages.passwordDictionaryCredentialChecks');
  }
  return '';
});

const unifiedSelectedIsBuiltin = computed(() => {
  if (!unifiedSelectedName.value) return false;
  if (unifiedSelectedType.value === 'asset') {
    const item = dictList.value.find(d => d.name === unifiedSelectedName.value);
    return item ? Boolean(item.is_builtin) : false;
  } else if (unifiedSelectedType.value === 'brute') {
    const item = bruteDictList.value.find(d => d.name === unifiedSelectedName.value);
    return item ? Boolean(item.is_builtin) : false;
  }
  return false;
});

const currentFilteredDicts = computed(() => {
  if (!selectedCategoryKeys.value.length) return [];
  const activeKey = selectedCategoryKeys.value[0];
  const group = filteredTreeData.value.find(g => g.key === activeKey);
  return group ? group.children || [] : [];
});

const handleUnifiedSelect = (selectedKeys, info) => {
  const key = Array.isArray(selectedKeys) ? selectedKeys[0] : selectedKeys;
  unifiedSelectedKeys.value = [key];
  searchKeyword.value = '';
  searchResult.value = null;
  newEntries.value = '';
  previewContent.value = '';
  totalLines.value = 0;
  if (key && key.startsWith('asset__')) {
    const name = key.slice(7);
    unifiedSelectedType.value = 'asset';
    unifiedSelectedName.value = name;
    selectedDict.value = name;
    fetchPreview(name);
  } else if (key && key.startsWith('brute__')) {
    const name = key.slice(7);
    unifiedSelectedType.value = 'brute';
    unifiedSelectedName.value = name;
    selectedDict.value = name;
    fetchPreview(name);
  } else {
    unifiedSelectedType.value = '';
    unifiedSelectedName.value = '';
    selectedDict.value = null;
  }
};

const previewContent = ref('');
const totalLines = ref(0);
const previewLimit = ref(100);

const previewLinesCount = computed(() => {
  if (!previewContent.value) return 0;
  return previewContent.value.split('\n').length;
});

const downloadLoading = ref(false);
const handleDownloadDict = async () => {
  if (!selectedDict.value) return;
  downloadLoading.value = true;
  try {
    const res = await request.get(`${dictApiBase.value}/download`, {
      params: { name: selectedDict.value },
      responseType: 'blob'
    });
    // 后端异常时以 HTTP 4xx/5xx 返回，axios 会走 catch 分支
    const blob = new Blob([res], { type: 'text/plain;charset=utf-8' });
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = selectedDict.value;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);
    message.success(pageText('pages.dictionaryNameExported', { name: selectedDict.value }));
  } catch (e) {
    let errMsg = pageText('pages.failedToExportDictionary');
    if (e.response && e.response.data instanceof Blob) {
      try {
        const text = await e.response.data.text();
        const parsed = JSON.parse(text);
        if (parsed.message) errMsg = parsed.message;
      } catch (_) { /* ignore parse errors */ }
    }
    message.error(errMsg);
    console.error(e);
  } finally {
    downloadLoading.value = false;
  }
};

const copyPreviewContent = async () => {
  if (!previewContent.value) {
    message.warning(pageText('pages.noContentToCopy'));
    return;
  }
  const ok = await copyText(previewContent.value);
  if (ok) {
    message.success(pageText('pages.previewCopiedToClipboard'));
  } else {
    message.error(pageText('pages.copyFailedSelectAndCopyTheTextManually'));
  }
};

const searchKeyword = ref('');
const searchResult = ref(null);

const newEntries = ref('');

// 根据当前选中类型返回 API 前缀
const dictApiBase = computed(() =>
  unifiedSelectedType.value === 'brute' ? '/api/brute_dict' : '/api/dictionary'
);

// 获取字典列表
const fetchDictList = async (showLoading = true) => {
  if (showLoading) loading.value = true;
  try {
    const res = await request.get('/api/dictionary/list');
    if (res.code === 200) {
      dictList.value = res.data || [];
    } else {
      message.error(res.message || pageText('pages.failedToLoadDictionaryList'));
    }
  } catch (error) {
    message.error(pageText('pages.dictionaryListRequestFailed'));
    console.error(error);
  } finally {
    if (showLoading) loading.value = false;
  }
};

// 获取预览（自动路由到对应 API）
const fetchPreview = async (name) => {
  if (!name) return;
  loading.value = true;
  try {
    const res = await request.get(`${dictApiBase.value}/preview`, {
      params: { name, limit: previewLimit.value }
    });
    if (res.code === 200) {
      previewContent.value = res.data.lines.join('\n');
      totalLines.value = res.data.total;
    } else {
      message.error(res.message || pageText('pages.failedToLoadPreview'));
    }
  } catch (error) {
    message.error(pageText('pages.previewRequestFailed'));
    console.error(error);
  } finally {
    loading.value = false;
  }
};

// 搜索功能（自动路由）
const handleSearch = async () => {
  if (!searchKeyword.value.trim()) {
    message.warning(pageText('pages.enterASearchKeyword'));
    return;
  }
  searchLoading.value = true;
  try {
    const res = await request.get(`${dictApiBase.value}/search`, {
      params: { name: selectedDict.value, keyword: searchKeyword.value }
    });
    if (res.code === 200) {
      searchResult.value = res.data.matches;
      if (res.data.matches.length > 0) {
        message.success(pageText('pages.matchingEntriesCount', { count: res.data.matches.length }));
      } else {
        message.info(pageText('pages.noEntriesContainThisKeyword'));
      }
    } else {
      message.error(res.message || pageText('pages.searchFailed'));
    }
  } catch (error) {
    message.error(pageText('pages.searchRequestFailed'));
    console.error(error);
  } finally {
    searchLoading.value = false;
  }
};

// 追加条目（自动路由），返回是否成功
const handleAppend = async () => {
  if (!newEntries.value.trim()) return false;

  const contentSize = new Blob([newEntries.value]).size;
  if (contentSize > 2 * 1024 * 1024) {
    message.warning(pageText('pages.appendedTextExceeds2MbSubmittingItThroughThe'));
    return false;
  }

  // 智能格式校验（阻断无效输入）
  const lines = newEntries.value.split('\n').map(s => s.trim()).filter(s => s);
  if (selectedDict.value && selectedDict.value.startsWith('port_')) {
    const invalidPorts = lines.filter(p => !/^\d+$/.test(p) || parseInt(p) < 1 || parseInt(p) > 65535);
    if (invalidPorts.length > 0) {
      message.error(pageText('pages.invalidPortNumberEGPortEnterIntegersFrom', { port: invalidPorts[0] }));
      return false;
    }
  } else if (selectedDict.value && selectedDict.value.includes('domain')) {
    const invalidDomains = lines.filter(d => /[\s,;!@#%^&*()<>{}\[\]]/.test(d));
    if (invalidDomains.length > 0) {
       message.error(pageText('pages.theSubdomainDictionaryContainsInvalidCharactersSuchAsSpaces'));
       return false;
    }
  }

  submitLoading.value = true;
  try {
    const res = await request.post(`${dictApiBase.value}/append`, {
      name: selectedDict.value,
      content: newEntries.value
    });
    if (res.code === 200) {
      message.success(pageText('pages.savedSubmittedSubmittedNewEntriesAddedAdded', { submitted: res.data.total_submitted, added: res.data.added }));
      newEntries.value = '';
      fetchDictList();
      fetchBruteDictList();
      fetchPreview(selectedDict.value);
      return true;
    } else {
      message.error(res.message || pageText('pages.failedToSaveLabel2'));
      return false;
    }
  } catch (error) {
    message.error(pageText('pages.saveRequestFailed'));
    console.error(error);
    return false;
  } finally {
    submitLoading.value = false;
  }
};


// 单条删除
const handleDeleteSingle = (item) => {
  if (!item) return false;
  Modal.confirm({
    title: pageText('pages.deleteDictionaryEntry'),
    icon: createVNode(ExclamationCircleOutlined),
    content: pageText('pages.deleteEntryEntryFromTheCurrentDictionary', { entry: item }),
    okText: pageText('tasks.confirmDeletion'),
    okButtonProps: { danger: true },
    cancelText: pageText('assets.cancel'),
    onOk: async () => {
      const ok = await deleteEntries(item);
      if (ok && searchResult.value) {
        searchResult.value = searchResult.value.filter(x => x !== item);
      }
      return ok;
    }
  });
  return true;
};

// 删除选中字典文件
const handleDeleteDict = () => {
  if (!selectedDict.value) return;
  const targetName = selectedDict.value;
  Modal.confirm({
    title: pageText('pages.deleteDictionaryFile'),
    icon: createVNode(ExclamationCircleOutlined),
    content: pageText('pages.permanentlyDeleteDictionaryNameAndAllItsEntriesThis', { name: targetName }),
    okText: pageText('tasks.confirmDeletion'),
    okButtonProps: { danger: true },
    cancelText: pageText('assets.cancel'),
    onOk: () => executeDeleteDict(targetName)
  });
};

const executeDeleteDict = async (targetName) => {
  loading.value = true;
  try {
    const res = await request.post(`${dictApiBase.value}/delete_file`, {
      name: targetName
    });
    if (res.code === 200) {
      message.success(pageText('pages.dictionaryNameDeleted', { name: targetName }));
      // 重置选中状态
      unifiedSelectedKeys.value = [];
      selectedDict.value = '';
      previewContent.value = '';
      totalLines.value = 0;
      
      // 重新拉取列表
      if (unifiedSelectedType.value === 'brute') {
        fetchBruteDictList();
      } else {
        fetchDictList();
      }
      unifiedSelectedType.value = '';
    } else {
      message.error(res.message || pageText('tasks.deletionFailedLabel'));
    }
  } catch (error) {
    message.error(pageText('pages.deleteRequestFailed'));
    console.error(error);
  } finally {
    loading.value = false;
  }
};

// 公共删除逻辑（自动路由）
const deleteEntries = async (content) => {
  if (!content || !content.trim()) return false;
  deleteLoading.value = true;
  try {
    const res = await request.post(`${dictApiBase.value}/delete_entries`, {
      name: selectedDict.value,
      content: content
    });
    if (res.code === 200) {
      message.success(pageText('pages.deletionCompletedSubmittedSubmittedDeletedDeleted', { submitted: res.data.total_submitted, deleted: res.data.deleted }));
      fetchDictList();
      fetchBruteDictList();
      fetchPreview(selectedDict.value);
      return true;
    } else {
      message.error(res.message || pageText('tasks.deletionFailedLabel'));
      return false;
    }
  } catch (error) {
    message.error(pageText('pages.deleteRequestFailed'));
    console.error(error);
    return false;
  } finally {
    deleteLoading.value = false;
  }
};

// ======================= 安全策略管理逻辑 =======================
const securityForm = ref({ blackIpsText: '', forbiddenDomainsText: '' });
const securityLoading = ref(false);
const securitySaveLoading = ref(false);

const fetchSecurityPolicy = async () => {
  securityLoading.value = true;
  try {
    const res = await request.get('/api/system_config/security_policy');
    if (res.code === 200) {
      securityForm.value.blackIpsText = (res.data.black_ips || []).join('\n');
      securityForm.value.forbiddenDomainsText = (res.data.forbidden_domains || []).join('\n');
      securityBaseline.value = cloneDeep(securityForm.value);
    } else {
      message.error(res.message || pageText('pages.failedToLoadSecurityPolicy'));
      if (!isConfigInitialized.value) {
        securityBaseline.value = cloneDeep(securityForm.value);
      }
    }
  } catch (error) {
    message.error(pageText('pages.securityPolicyRequestFailed'));
    console.error(error);
    if (!isConfigInitialized.value) {
      securityBaseline.value = cloneDeep(securityForm.value);
    }
  } finally {
    securityLoading.value = false;
  }
};

const saveSecurityPolicy = async () => {
  securitySaveLoading.value = true;
  try {
    const black_ips = securityForm.value.blackIpsText.split('\n').map(s => s.trim()).filter(s => s);
    const forbidden_domains = securityForm.value.forbiddenDomainsText.split('\n').map(s => s.trim()).filter(s => s);

    const res = await request.post('/api/system_config/security_policy', {
      black_ips,
      forbidden_domains
    });
    
    if (res.code === 200) {
      message.success(pageText('pages.securityPolicyUpdated'));
      securityBaseline.value = cloneDeep(securityForm.value);
      fetchSecurityPolicy(); // 重新拉取确认
    } else {
      message.error(res.message || pageText('pages.failedToSaveLabel2'));
    }
  } catch (error) {
    message.error(pageText('pages.failedToSaveSecurityPolicy'));
    console.error(error);
  } finally {
    securitySaveLoading.value = false;
  }
};

// ======================= 性能配置管理逻辑 =======================
const performanceForm = ref({
  celery_heavy_concurrency: 1,
  celery_light_concurrency: 1,
  osint_concurrency: 1,
  github_concurrency: 1,
});
const runtimePerformance = ref({ runtime_heavy_concurrency: null, runtime_light_concurrency: null, runtime_github_concurrency: null });
const performanceLoading = ref(false);
const performanceSaveLoading = ref(false);

const fetchPerformanceConfig = async () => {
  performanceLoading.value = true;
  try {
    const res = await request.get('/api/system_config/performance');
    if (res.code === 200) {
      performanceForm.value.celery_heavy_concurrency = res.data.celery_heavy_concurrency || 1;
      performanceForm.value.celery_light_concurrency = res.data.celery_light_concurrency || 1;
      performanceForm.value.osint_concurrency = res.data.osint_concurrency || 1;
      performanceForm.value.github_concurrency = res.data.github_concurrency || 1;
      runtimePerformance.value.runtime_heavy_concurrency = res.data.runtime_heavy_concurrency ?? null;
      runtimePerformance.value.runtime_light_concurrency = res.data.runtime_light_concurrency ?? null;
      runtimePerformance.value.runtime_github_concurrency = res.data.runtime_github_concurrency ?? null;
      performanceBaseline.value = cloneDeep(performanceForm.value);
    } else {
      message.error(res.message || pageText('pages.failedToLoadPerformanceSettings'));
      if (!isConfigInitialized.value) {
        performanceBaseline.value = cloneDeep(performanceForm.value);
      }
    }
  } catch (error) {
    message.error(pageText('pages.performanceSettingsRequestFailed'));
    console.error(error);
    if (!isConfigInitialized.value) {
      performanceBaseline.value = cloneDeep(performanceForm.value);
    }
  } finally {
    performanceLoading.value = false;
  }
};

const savePerformanceConfig = async () => {
  performanceSaveLoading.value = true;
  try {
    const res = await request.post('/api/system_config/performance', {
      celery_heavy_concurrency: performanceForm.value.celery_heavy_concurrency,
      celery_light_concurrency: performanceForm.value.celery_light_concurrency,
      osint_concurrency: performanceForm.value.osint_concurrency,
      github_concurrency: performanceForm.value.github_concurrency
    });
    
    if (res.code === 200) {
      message.success(res.message || pageText('pages.performanceSettingsUpdated'), 5);
      performanceBaseline.value = cloneDeep(performanceForm.value);
      fetchPerformanceConfig();
    } else {
      message.error(res.message || pageText('pages.failedToSaveLabel2'));
    }
  } catch (error) {
    message.error(pageText('pages.failedToSavePerformanceSettings'));
    console.error(error);
  } finally {
    performanceSaveLoading.value = false;
  }
};

// ======================= 弱口令字典管理逻辑 =======================
// (Moved bruteLoading and bruteDictList to the top to avoid TDZ)

const fetchBruteDictList = async (showLoading = true) => {
  if (showLoading) bruteLoading.value = true;
  try {
    const res = await request.get('/api/brute_dict/list');
    if (res.code === 200) {
      bruteDictList.value = res.data || [];
    } else {
      message.error(res.message || pageText('pages.failedToLoadCredentialDictionaries'));
    }
  } catch (error) {
    message.error(pageText('pages.credentialDictionaryRequestFailed'));
    console.error(error);
  } finally {
    if (showLoading) bruteLoading.value = false;
  }
};

const probeActiveBackupTask = async () => {
  try {
    const res = await request.get('/api/backup/status');
    if (res.code === 200 && res.data && ['backing_up', 'restoring'].includes(res.data.status)) {
      activeKey.value = 'system_backup';
    }
  } catch (e) {
    // 页面初始化静默容错
  }
};

onMounted(async () => {
  probeActiveBackupTask();

  if (route.query.tab) {
    if (route.query.tab === 'cdn') {
      activeKey.value = 'dictionary';
      dictSubTab.value = 'cdn';
    } else if (route.query.tab === 'security' || route.query.tab === 'system_general') {
      // security / system_general 已收敛为「扫描与并发」的子 Tab，深链需同时切换内外两层
      activeKey.value = 'performance';
      scanSubTab.value = route.query.tab;
    } else {
      activeKey.value = route.query.tab;
    }
  }
  // 支持 ?focus=<anchor> 深链：业务页可直接把用户送到具体设置项并高亮
  if (route.query.focus) {
    const target = SETTINGS_INDEX.find((i) => i.anchor === route.query.focus);
    if (target) {
      jumpToSetting({ ...target, tab: route.query.tab || target.tab });
    } else {
      scrollAndFlashAnchor(`[data-setting-anchor="${route.query.focus}"]`);
    }
  }
  window.addEventListener('beforeunload', handleBeforeUnload);
  fetchCapacityProbe();
  fetchDictList();
  fetchBruteDictList();
  try {
    await Promise.allSettled([
      fetchSecurityPolicy(),
      fetchPerformanceConfig(),
      fetchGeneralConfig(),
    ]);
  } finally {
    isConfigInitialized.value = true;
  }
});

onDeactivated(() => {
  // 组件被 keep-alive 缓存，切走时改动仍在内存中，这里只做显式提醒不做阻断
  if (hasUnsavedChanges.value) {
    message.warning(pageText('pages.thereAreCountUnsavedConfigurationChangesSaveThemBefore', { count: unsavedCount.value }), 5);
  }
  createDictDrawerVisible.value = false;
  appendDrawerVisible.value = false;
  searchDrawerVisible.value = false;
  cdnPanelRef.value?.closeDrawer?.();
  updatePanelRef.value?.closeModals?.();
  backupPanelRef.value?.closeModals?.();
  clearAllDictPollTimers();
});

onUnmounted(() => {
  window.removeEventListener('beforeunload', handleBeforeUnload);
  updatePanelRef.value?.stopUpdateTimers?.();
  clearAllDictPollTimers();
  backupPanelRef.value?.stopProgressTracking?.();
});

// 路由级离开拦截：组件被 keep-alive 缓存时 onDeactivated 只提示不阻断，
// 真正的拦停放在路由守卫，避免用户携带未保存改动跳转到其他页面。
onBeforeRouteLeave(() => {
  if (!hasUnsavedChanges.value) return true;
  return new Promise((resolve) => {
    Modal.confirm({
      title: pageText('pages.unsavedConfigurationChangesLabel2'),
      icon: createVNode(ExclamationCircleOutlined),
      content: pageText('pages.thereAreCountUnsavedConfigurationChangesLeavingThisPage', { count: unsavedCount.value }),
      okText: pageText('pages.discardChangesAndLeave'),
      okType: 'danger',
      cancelText: pageText('tasks.stayOnThisPage'),
      onOk: () => resolve(true),
      onCancel: () => resolve(false),
    });
  });
});
</script>

<style scoped>
.page-flex-input { flex: 1; }
.page-full-width-input { width: 100%; }
/* ================== 设置项搜索样式 (P2) ================== */
.arl-settings-search {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.arl-search-count {
  font-size: 12px;
  color: var(--arl-text-color);
  opacity: 0.55;
}

.arl-search-panel {
  max-width: 760px;
  margin-bottom: 16px;
  border: 1px solid var(--arl-border-color);
  border-radius: 8px;
  background: var(--arl-bg-white);
  overflow: hidden;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.04);
}

.arl-search-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 10px 14px;
  cursor: pointer;
  border-bottom: 1px solid var(--arl-border-color);
  transition: background 0.2s;
}

.arl-search-item:last-child {
  border-bottom: none;
}

.arl-search-item:hover {
  background: var(--arl-bg-light);
}

.arl-search-item-main {
  display: flex;
  flex-direction: column;
  gap: 3px;
  min-width: 0;
}

.arl-search-item-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--arl-text-color);
}

.arl-search-item-desc {
  font-size: 12px;
  color: var(--arl-text-color);
  opacity: 0.5;
}

.arl-search-empty {
  padding: 20px 14px;
  text-align: center;
  font-size: 13px;
  color: var(--arl-text-color);
  opacity: 0.55;
}

/* 全局凭据状态条（跨 Tab 总览，默认折叠） */
.arl-global-cred {
  margin-bottom: 12px;
  border: 1px solid var(--arl-border-color);
  border-radius: 8px;
  background: var(--arl-bg-white);
  overflow: hidden;
}

.arl-cred-summary {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.arl-cred-summary:hover {
  background: var(--arl-bg-light);
}

.arl-cred-chevron {
  font-size: 12px;
  color: var(--arl-text-color);
  opacity: 0.5;
  width: 12px;
}

.arl-cred-summary-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--arl-text-color);
}

.arl-cred-alert {
  font-size: 12px;
  color: #cf1322;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.arl-cred-ok {
  font-size: 12px;
  color: var(--arl-text-color);
  opacity: 0.5;
  flex: 1;
}

.arl-cred-toggle {
  font-size: 12px;
  flex-shrink: 0;
}

.arl-cred-body {
  padding: 0 14px 14px;
  border-top: 1px solid var(--arl-border-color);
}

/* 字段级说明（区分并发语义等易混指标） */
.arl-field-hint {
  margin-top: 6px;
  font-size: 12px;
  line-height: 1.7;
  color: var(--arl-text-color);
  opacity: 0.5;
}

.arl-field-hint code {
  background: rgba(0, 0, 0, 0.05);
  padding: 1px 4px;
  border-radius: 3px;
}

/* 跳转后短暂高亮目标设置项 */
.arl-anchor-flash {
  animation: arl-anchor-flash 2.2s ease-out;
}

@keyframes arl-anchor-flash {
  0% { box-shadow: 0 0 0 3px rgba(22, 119, 255, 0.45); }
  60% { box-shadow: 0 0 0 3px rgba(22, 119, 255, 0.25); }
  100% { box-shadow: 0 0 0 0 rgba(22, 119, 255, 0); }
}

/* ================== 未保存改动与推荐值提示样式 ================== */
/* 有脏字段的保存按钮：呼吸边框，与 CDN Tab 已有的 breathing-btn 范式保持一致 */
.arl-dirty-btn {
  box-shadow: 0 0 0 2px rgba(250, 173, 20, 0.35);
}

.arl-recommend-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: color-mix(in srgb, var(--arl-theme-color) 6%, transparent);
  border: 1px dashed color-mix(in srgb, var(--arl-theme-color) 30%, transparent);
  font-size: 13px;
}

.arl-recommend-label {
  color: var(--arl-text-color);
  opacity: 0.6;
  margin-right: 6px;
}

.arl-recommend-basis {
  color: var(--arl-text-color);
  opacity: 0.5;
  font-size: 12px;
}

.arl-cred-hint {
  color: var(--arl-text-color);
  opacity: 0.55;
  font-size: 12px;
  line-height: 1.6;
}

.arl-cred-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  border-radius: 6px;
  border: 1px solid var(--arl-border-color);
  background: var(--arl-bg-white);
}

.arl-cred-item.is-ok {
  border-left: 3px solid #52c41a;
}

.arl-cred-item.is-missing {
  border-left: 3px solid #d9d9d9;
}

.arl-cred-name {
  font-size: 13px;
  color: var(--arl-text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 可以在此处添加自定义样式 */

.cdn-textarea {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  resize: none;
  padding: 16px;
  font-family: 'Fira Code', 'Consolas', monospace;
  font-size: 14px;
  color: #a6e22e;
  line-height: 1.6;
  white-space: pre-wrap;
  word-break: break-all;
}
.cdn-textarea::placeholder {
  color: rgba(255, 255, 255, 0.2);
}
.purple-glow:hover {
  box-shadow: 0 12px 48px rgba(114, 46, 209, 0.25) !important;
}
.pulse-btn {
  animation: btnPulse 2s infinite;
}
@keyframes btnPulse {
  0% { box-shadow: 0 0 0 0 rgba(24, 144, 255, 0.7); }
  70% { box-shadow: 0 0 0 10px rgba(24, 144, 255, 0); }
  100% { box-shadow: 0 0 0 0 rgba(24, 144, 255, 0); }
}

/* 字典管理现代化升级样式 */
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
  box-shadow: 0 4px 12px rgba(24, 144, 255, 0.3);
}
.custom-list-item.is-active .dict-title,
.custom-list-item.is-active .dict-subtitle {
  color: #fff;
}
.custom-list-item.is-active .dict-badge {
  background: rgba(255,255,255,0.2);
  color: #fff;
}
.dict-subtitle {
  font-size: 12px;
  opacity: 0.65;
}
.dict-badge {
  font-size: 10px;
  background: rgba(0,0,0,0.05);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--arl-text-color);
  opacity: 0.6;
}
.hide-scrollbar::-webkit-scrollbar {
  display: none;
}
.hide-scrollbar {
  -ms-overflow-style: none;
  scrollbar-width: none;
}

/* 仪表盘（空状态）样式 */
.health-dashboard-wrapper {
  flex: 1;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--arl-bg-white, #f8fafc);
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
  color: var(--arl-text-color, #1e293b);
  margin: 0;
  letter-spacing: 0.5px;
}
.health-stats-container {
  display: flex;
  gap: 24px;
  margin-top: 16px;
}
.health-stat-card {
  background: var(--arl-bg-subcard, rgba(255, 255, 255, 0.6));
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid var(--arl-border-color, rgba(255, 255, 255, 0.8));
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
  background-image: linear-gradient(135deg, var(--arl-theme-color, #1890ff) 0%, #36cfc9 100%);
}
.warning-stat .stat-value {
  background-image: linear-gradient(135deg, #fa8c16 0%, #ffc53d 100%);
}
.stat-label {
  font-size: 14px;
  color: var(--arl-text-secondary, #64748b);
  margin-top: 8px;
  font-weight: 500;
}
.health-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 32px;
  color: var(--arl-text-secondary, #94a3b8);
  font-size: 13px;
  background: var(--arl-bg-subcard, rgba(255,255,255,0.5));
  padding: 8px 16px;
  border-radius: 20px;
  border: 1px solid var(--arl-border-color, rgba(255,255,255,0.6));
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

/* 代码区还原极简素雅风格 */
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
  background: var(--arl-bg-light); /* 非常浅的底色区分 */
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
  height: 21px; /* 与 line-height: 1.6 和 font-size: 13px 对应，大致是 20.8px */
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
.code-limit-hint {
  color: var(--arl-theme-color);
  margin-top: 24px;
  font-style: italic;
  border-top: 1px dashed var(--arl-border-color);
  padding-top: 16px;
  opacity: 0.7;
}

@keyframes btn-breathing {
  0% { box-shadow: 0 0 0 0 rgba(82, 196, 26, 0.4); }
  70% { box-shadow: 0 0 0 6px rgba(82, 196, 26, 0); }
  100% { box-shadow: 0 0 0 0 rgba(82, 196, 26, 0); }
}
.breathing-btn {
  animation: btn-breathing 2s infinite;
}

/* ================== 系统更新 Modal 实时态势与分层芯片样式 ================== */
.update-heartbeat-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(82, 196, 26, 0.12);
  color: #52c41a;
  border: 1px solid rgba(82, 196, 26, 0.3);
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.heartbeat-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #52c41a;
  animation: pulse-dot 1.5s infinite ease-in-out;
}

@keyframes pulse-dot {
  0% { transform: scale(0.8); opacity: 0.5; }
  50% { transform: scale(1.3); opacity: 1; }
  100% { transform: scale(0.8); opacity: 0.5; }
}

.update-layer-box {
  margin-bottom: 12px;
  background: rgba(22, 119, 255, 0.04);
  border: 1px dashed rgba(22, 119, 255, 0.3);
  border-radius: 6px;
  padding: 8px 12px;
}

.update-layer-header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: #1677ff;
  margin-bottom: 6px;
}

.update-layer-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 80px;
  overflow-y: auto;
}

.layer-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--arl-bg-white);
  border: 1px solid var(--arl-border-color);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-family: monospace;
}

.layer-id {
  font-weight: 600;
  color: #1677ff;
}

.layer-status {
  color: var(--arl-text-color);
  opacity: 0.85;
}

.page-small-text { font-size: 12px; }
.page-config-card { margin-bottom: 16px; border-radius: 6px; }
.page-flush-bottom { margin-bottom: 0; }
.page-config-card-min-height { margin-bottom: 16px; border-radius: 6px; min-height: 190px; }
.page-field-spacing { margin-bottom: 12px; }
.page-config-card-fixed { margin-bottom: 16px; border-radius: 6px; height: 190px; }
.page-rounded { border-radius: 6px; }
.page-panel-heading { font-weight: 600; font-size: 14px; color: var(--arl-text-color); }
.page-search-field { flex: 1; border-radius: 4px; }
.page-icon-padding { padding: 0 8px; }
.page-label { font-size: 13px; font-weight: 500; }
.page-quiet-help { font-size: 12px; opacity: 0.7; }
.page-tiny-tag { margin: 0; font-size: 10px; line-height: 16px; padding: 0 4px; border-radius: 2px; }
.page-dictionary-summary { color: var(--arl-text-color); opacity: 0.55; font-size: 12px; font-family: 'Fira Code', monospace; }
.page-icon-gap { margin-right:4px; }
.page-muted-label { font-size: 12px; opacity: 0.65; color: var(--arl-text-color); }
.page-small-icon-gap { margin-right:2px; }
.page-description { margin-bottom: 16px; color: var(--arl-text-color); font-size: 13px; }
.page-inline-gap { margin-right: 8px; }
.page-compact-description { margin-bottom: 12px; color: var(--arl-text-color); font-size: 13px; }
.page-code-preview { font-family: monospace; font-size: 12px; margin-bottom: 24px; }
.page-form-section-title { margin-bottom: 8px; font-weight: 500; font-size: 14px; }
.page-success-detail { margin-bottom: 8px; color: #52c41a; font-size: 13px; }
.page-error-detail { margin-bottom: 8px; color: #ff4d4f; font-size: 13px; }
.page-warning-detail { color: #faad14; font-size: 12px; margin-top: 8px; }
.page-danger-section-title { margin-bottom: 8px; font-weight: 500; font-size: 14px; color: #ff4d4f; }
.page-empty-detail { margin-bottom: 8px; color: var(--arl-text-color); opacity: 0.45; font-size: 12px; }
.page-code-summary { font-family: monospace; font-size: 12px; margin-bottom: 16px; }
.page-danger-emphasis { color: #cf1322; }
.page-flush-tag { margin: 0; }
.page-secondary-help { color: var(--arl-text-color); opacity: 0.55; font-size: 12px; }
.page-warning-emphasis { color: #d46b08; }
.page-config-card-danger { margin-bottom: 16px; border-radius: 6px; border-left: 4px solid #ff4d4f; }
.page-choice-gap { margin-left: 8px; font-size: 12px; }
.page-strong-heading { font-weight: bold; margin-bottom: 8px; }
.page-config-card-success { margin-bottom: 16px; border-radius: 6px; border-left: 4px solid #52c41a; }
.page-config-card-info { margin-bottom: 16px; border-radius: 6px; border-left: 4px solid #1890ff; }
.page-config-card-purple { margin-bottom: 16px; border-radius: 6px; border-left: 4px solid #722ed1; }
.page-config-card-theme { margin-bottom: 16px; border-radius: 6px; border-left: 4px solid var(--arl-theme-color); }
.page-form-spacing { margin-bottom: 8px; }
.page-config-card-fixed-short { margin-bottom: 16px; border-radius: 6px; height: 180px; }
.page-config-card-fixed-tall { margin-bottom: 16px; border-radius: 6px; height: 260px; }
.page-dialog-content { max-width: 800px; }
.page-sidebar-heading { font-weight: 600; font-size: 15px; color: var(--arl-text-color); }
.page-small-heading { font-weight: 600; font-size: 12px; }
.page-primary-action { border-radius: 6px; padding: 0 32px; font-weight: 600; }

.page-wide-text .page-config-card-fixed,
.page-wide-text .page-config-card-fixed-short,
.page-wide-text .page-config-card-fixed-tall { height: auto; min-height: 190px; }
.page-wide-text .arl-cred-summary { flex-wrap: wrap; row-gap: 8px; }
.page-wide-text .arl-cred-item { flex-wrap: wrap; gap: 6px; }
.page-wide-text :deep(.ant-card-head-title) { white-space: normal; line-height: 1.5; padding: 12px 0; }
</style>
