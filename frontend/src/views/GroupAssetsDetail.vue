<template>
  <div style="background-color: var(--arl-bg-layout); padding: 12px 16px; min-height: calc(100vh - 64px);">
    <!-- 1. 一体化资产画像 Hero 头部卡片 (常驻吸附在页面最顶部 top: 0，极简单行整合) -->
    <div ref="heroRef" class="arl-hero-card hero-sticky-card">
      <div class="hero-unified-bar">
        <!-- 左侧：返回 + 标题 + 分组标签 + 类型 + 测绘状态 (去重) -->
        <div class="hero-left-section" :class="{ 'hero-left-section-wide': assetLocale !== 'zh-CN' }">
          <a-button type="text" class="hero-back-btn" @click="handleBack" :title="assetText('assets.backToAssetGroupList')">
            <template #icon><arrow-left-outlined /></template>
            <span>{{ assetText('assets.backToAssetGroups') }}</span>
          </a-button>

          <div class="hero-title-wrapper">
            <a-tooltip :title="targetName" placement="bottomLeft">
              <span class="hero-title-text">{{ targetName }}</span>
            </a-tooltip>
            <a-tag v-if="scopeGroupName" color="orange" class="hero-scope-tag">
              <cluster-outlined /> {{ scopeGroupName }}
            </a-tag>
            <a-tag v-if="scopeType" color="blue" class="hero-scope-tag">
              {{ scopeType.toUpperCase() }}
            </a-tag>
          </div>

          <div class="hero-v-divider"></div>

          <div class="hero-meta-section">
            <template v-if="boundIcpTaskId">
              <a-tooltip placement="bottom">
                <template #title>
                  <div style="font-size: 12px; line-height: 1.6;">
                    <div>{{ assetText('assets.linkedOrganization') }} {{ scopeEnterpriseName || targetName }}</div>
                    <div v-if="taskTarget && taskTarget.startsWith('TYC_')">{{ assetText('assets.organizationId') }} {{ taskTarget }}</div>
                    <div v-if="taskTypeLabel">{{ assetText('tasks.taskType') }} {{ taskTypeLabel }}</div>
                    <div v-if="taskStatusLabel">{{ assetText('assets.discoveryStatus') }} {{ taskStatusLabel }}</div>
                  </div>
                </template>
                <span v-if="scopeEnterpriseName && scopeEnterpriseName !== targetName" class="hero-enterprise-label">
                  <bank-outlined class="meta-icon" />
                  <span class="enterprise-text">{{ scopeEnterpriseName }}</span>
                </span>
                <span v-else class="hero-enterprise-icon-only">
                  <bank-outlined class="meta-icon" />
                </span>
              </a-tooltip>
              <a-tag v-if="scopeUpdatingTaskId" color="processing" class="hero-mini-tag">
                <sync-outlined :spin="true" class="asset-status-icon" /> {{ assetText('assets.updatingDiscovery') }}
              </a-tag>
              <a-tag v-else-if="taskStatusLabel" :color="taskStatusColor" class="hero-mini-tag">
                {{ taskStatusLabel }}
              </a-tag>
              <a-badge v-if="scopeHasIncrement" :count="assetText('tasks.newAssets')" class="asset-increment-badge" />
            </template>
            <template v-else>
              <a-tooltip :title="assetText('assets.noOrganizationLinkedClickToRetrieveCompanyRecords')" placement="bottom">
                <span class="hero-unbound-label" @click="openBindModal" style="cursor: pointer;">
                  <link-outlined style="margin-right: 4px;" />
                  {{ assetText('assets.noOrganizationLinked') }}
                </span>
              </a-tooltip>
            </template>
          </div>
        </div>

        <!-- 右侧：OSINT / ASM 视角切换胶囊 -->
        <div class="hero-right-section">
          <div class="capsule-switcher">
            <button
              class="capsule-btn"
              :class="{ active: currentView === 'osint' }"
              @click="currentView = 'osint'"
              :title="assetText('assets.switchToEnterpriseOsintAssets')"
            >
              <bank-outlined class="capsule-icon" />
              <span>{{ assetText('assets.enterpriseAssetsOsint') }}</span>
              <span class="capsule-count" v-if="osintTotalCount > 0">{{ osintTotalCount }}</span>
              <span v-if="scopeHasIncrement" class="capsule-dot"></span>
            </button>
            <button
              class="capsule-btn"
              :class="{ active: currentView === 'asm' }"
              @click="currentView = 'asm'"
              :title="assetText('assets.switchToNetworkExposureAssets')"
            >
              <global-outlined class="capsule-icon" />
              <span>{{ assetText('assets.networkExposureAsm') }}</span>
              <span class="capsule-count" v-if="asmTotalCount > 0">{{ asmTotalCount }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>

      <!-- 2. 网络暴露面 (ASM) 专属控制与筛选区 (吸附于 Hero 头部正下方) -->
      <div v-show="currentView === 'asm'" ref="asmControlRef" class="asm-control-box" :style="{ top: heroHeight + 'px' }">
        <div class="scope-hint-line">
          <span class="scope-hint-tag">{{ assetText('assets.thisAssetGroup') }}</span>
          <span>{{ assetText('assets.thisViewShowsOnlyAssetsManagedByThis') }}</span>
        </div>
        <!-- 维度 Tabs 导航 (带数量徽标与平滑滚动) -->
        <a-tabs v-model:activeKey="activeTab" type="card" size="small" class="arl-detail-tabs asm-tabs-nav">
          <a-tab-pane v-for="t in asmTabList" :key="t.key">
            <template #tab>
              <span class="asm-tab-item">
                <span>{{ t.label }}</span>
                <span class="asm-tab-badge" :class="{ 'has-data': (t.key === 'service' ? ((asmCounts.service || 0) + (asmCounts.npoc_service || 0)) : (asmCounts[t.key] || 0)) > 0 }">
                  {{ t.key === 'service' ? ((asmCounts.service || 0) + (asmCounts.npoc_service || 0)) : (asmCounts[t.key] || 0) }}
                </span>
              </span>
            </template>
          </a-tab-pane>
        </a-tabs>

        <!-- 系统服务识别引擎筛选控制条 -->
        <div v-if="activeTab === 'service'" style="margin-top: 8px; margin-bottom: 4px; display: flex; align-items: center; gap: 10px; background: var(--arl-bg-light); padding: 8px 14px; border-radius: 6px; border: 1px solid var(--arl-border-color);">
          <span class="asset-option-heading">{{ assetText('tasks.detectionEngine') }}</span>
          <a-radio-group v-model:value="serviceEngineType" button-style="solid" size="small" @change="onServiceEngineChange">
            <a-radio-button value="nmap">{{ assetText('assets.portServiceCount', { count: asmCounts.service || 0 }) }}</a-radio-button>
            <a-radio-button value="npoc">{{ assetText('assets.pluginServiceCount', { count: asmCounts.npoc_service || 0 }) }}</a-radio-button>
          </a-radio-group>
        </div>

        <!-- 普通资产列表检索与操作工具栏 (上下分层：业务操作行 + 直接平铺紧凑检索卡片) -->
        <div class="asm-toolbar-container">
          <div class="toolbar-row">
            <div class="toolbar-left">
              <span class="toolbar-title-text">{{ assetText('assets.categoryHeading', { category: tabConfig[effectiveTab]?.tabName || assetText('tasks.assets') }) }}</span>
              <span class="toolbar-meta-count">
                {{ assetText('assets.recordCount', { count: effectiveTab === 'service' ? asmCounts.service : (effectiveTab === 'npoc_service' ? asmCounts.npoc_service : (asmCounts[activeTab] || 0)) }) }}
              </span>
            </div>

            <div class="toolbar-right">
              <a-button v-if="activeTab === 'site'" type="primary" size="small" @click="openAddSiteModal">
                <template #icon><plus-outlined /></template>
                {{ assetText('assets.addWebsite') }}
              </a-button>
              <a-button v-if="activeTab === 'domain'" type="primary" size="small" @click="openAddDomainModal">
                <template #icon><plus-outlined /></template>
                {{ assetText('assets.addSubdomain') }}
              </a-button>
              <a-button v-if="activeTab !== 'ip' && tabConfig[effectiveTab]?.exportUrl" size="small" @click="handleExport">
                <template #icon><download-outlined /></template>
                {{ assetText('tasks.exportAssetType', { type: tabConfig[effectiveTab].tabName }) }}
              </a-button>
              <template v-if="activeTab === 'ip'">
                <a-button size="small" @click="handleIPExport('port')">{{ assetText('assets.exportPorts') }}</a-button>
                <a-button size="small" @click="handleIPExport('domain')">{{ assetText('assets.exportDomains') }}</a-button>
                <a-button type="primary" ghost size="small" @click="handleIPExport('ip')">
                  <template #icon><download-outlined /></template>
                  {{ assetText('assets.exportIps') }}
                </a-button>
              </template>
              <a-button v-if="activeTab === 'site'" type="dashed" danger size="small" @click="openRiskModal">
                <template #icon><bug-outlined /></template>
                {{ assetText('assets.riskScan') }}
              </a-button>

              <!-- 高级筛选折叠展开切换按钮 -->
              <a-button
                v-if="tabConfig[effectiveTab]?.searchFields?.length"
                size="small"
                :type="isAdvancedFilterOpen ? 'primary' : 'default'"
                :ghost="isAdvancedFilterOpen"
                @click="isAdvancedFilterOpen = !isAdvancedFilterOpen"
              >
                <template #icon><filter-outlined /></template>
                {{ isAdvancedFilterOpen ? assetText('tasks.hideFilters') : assetText('tasks.advancedFilters') }}
                <a-badge
                  v-if="activeFilterCount > 0"
                  :count="activeFilterCount"
                  :number-style="{ backgroundColor: 'var(--arl-theme-color)', marginLeft: '4px', fontSize: '10px' }"
                />
                <down-outlined v-if="!isAdvancedFilterOpen" style="font-size: 10px; margin-left: 2px;" />
                <up-outlined v-else style="font-size: 10px; margin-left: 2px;" />
              </a-button>
            </div>
          </div>

          <!-- 可折叠展开的紧凑多字段栅格筛选卡片 -->
          <transition name="fade-slide">
            <div v-show="isAdvancedFilterOpen" v-if="tabConfig[effectiveTab]?.searchFields?.length" class="asm-filter-card">
            <a-form :label-wrap="true" :model="searchForm" class="filter-grid-form">
              <a-row :gutter="[12, 6]">
                <a-col
                  v-for="field in tabConfig[effectiveTab].searchFields.filter(f => !f.hidden)"
                  :key="field.key"
                  :xs="24" :sm="12" :md="assetLocale !== 'zh-CN' ? 12 : 8" :lg="assetLocale !== 'zh-CN' ? 8 : 6"
                >
                  <div class="filter-field-cell">
                    <span class="filter-field-label" :class="{ 'filter-field-label-wide': assetLocale !== 'zh-CN' }" :title="field.label">{{ field.label }}</span>
                    <div class="filter-field-widget">
                      <!-- 下拉选择 -->
                      <HttpStatusFilter
                        v-if="field.type === 'httpStatus'"
                        v-model:value="searchForm[field.key]"
                        @change="onSearch"
                      />
                      <a-select
                        v-else-if="field.type === 'select'"
                        v-model:value="searchForm[field.key]"
                        :placeholder="assetText('tasks.selectField', { field: field.label })"
                        style="width: 100%;"
                        size="small"
                        allowClear
                        @change="onSearch"
                      >
                        <a-select-option v-for="opt in field.options" :key="opt.value" :value="opt.value">{{ opt.label }}</a-select-option>
                      </a-select>

                      <!-- 日期区间选择 -->
                      <a-range-picker
                        v-else-if="field.type === 'dateRange'"
                        v-model:value="searchForm[field.key]"
                        :placeholder="[assetText('tasks.startDate'), assetText('tasks.endDate')]"
                        style="width: 100%;"
                        size="small"
                        @change="onSearch"
                      />

                      <!-- 组合操作符输入框 (如 等于/不等于) -->
                      <div
                        v-else-if="field.hasOperatorSelect"
                        class="filter-operator-box"
                      >
                        <a-input
                          v-model:value="searchForm[field.key]"
                          :placeholder="field.placeholder || assetText('tasks.enterField', { field: field.label })"
                          :bordered="false"
                          size="small"
                          class="operator-text-input"
                          allowClear
                          @pressEnter="onSearch"
                        >
                          <template #suffix>
                            <search-outlined class="filter-search-icon" @click="onSearch" />
                          </template>
                        </a-input>
                        <div class="operator-divider"></div>
                        <a-select
                          v-model:value="field.operator"
                          :bordered="false"
                          size="small"
                          class="operator-op-select" :class="{ 'operator-op-select-wide': assetLocale !== 'zh-CN' }"
                          @change="onSearch"
                        >
                          <a-select-option v-for="op in field.operators" :key="op" :value="op">{{ formatAssetFilterOperator(op) }}</a-select-option>
                        </a-select>
                      </div>

                      <!-- 普通文本输入框 -->
                      <a-input
                        v-else
                        v-model:value="searchForm[field.key]"
                        :placeholder="field.placeholder || assetText('tasks.enterField', { field: field.label })"
                        style="width: 100%;"
                        size="small"
                        allowClear
                        @pressEnter="onSearch"
                      >
                        <template #suffix>
                          <search-outlined class="filter-search-icon" @click="onSearch" />
                        </template>
                      </a-input>
                    </div>
                  </div>
                </a-col>
              </a-row>

              <!-- 底部操作与状态条 -->
              <div class="filter-footer-row">
                <div class="filter-badge-status">
                  <template v-if="activeFilterCount > 0">
                    <span class="active-indicator-dot"></span>
                    <span>{{ assetText('assets.filtersApplied', { count: activeFilterCount }) }}</span>
                  </template>
                  <span v-else class="filter-idle-text">{{ assetText('assets.pressEnterOrClickTheSearchIconTo') }}</span>
                </div>
                <div class="filter-action-btns">
                  <a-button size="small" @click="resetSearch">
                    <template #icon><redo-outlined /></template>
                    {{ assetText('tasks.reset') }}
                  </a-button>
                  <a-button type="primary" size="small" @click="onSearch">
                    <template #icon><search-outlined /></template>
                    {{ assetText('tasks.search') }}
                  </a-button>
                </div>
              </div>
            </a-form>
          </div>
          </transition>
        </div>
      </div>

    <div v-show="currentView === 'asm'">
    <a-table
      :sticky="pagination.pageSize >= 100 ? false : asmStickyConfig"
      :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }"
      :loading="loading"
      :dataSource="dataSource"
      :columns="columns"
      :pagination="false"
      :scroll="pagination.pageSize >= 100 ? { y: tableScrollY, x: 'max-content' } : { x: 'max-content' }"
      :virtual="pagination.pageSize >= 100"
      size="small"
      class="modern-clean-table"
      :rowKey="(record) => record._id || record.id"
    >
      <template #bodyCell="{ column, record, index }">

        <template v-if="column.key === 'index'">
          <a style="">{{ (pagination.current - 1) * pagination.pageSize + index + 1 }}</a>
        </template>

        <template v-else-if="column.key === 'site'">
          <div class="site-header">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
              <div style="display: flex; align-items: center; gap: 6px; overflow: hidden;">
                <img v-if="record.favicon && record.favicon.data" :src="`data:image/png;base64,${record.favicon.data}`" class="site-img" />
                <a :href="record.site || record.url" target="_blank" style="font-weight: 500; word-break: break-all;">
                  {{ record.site || record.url }}
                </a>
                <a-tooltip :title="assetText('assets.copyWebsite')">
                  <a-button type="text" size="small" class="cell-copy-btn" @click.stop="handleCopyText(record.site || record.url)">
                    <copy-outlined style="font-size: 11px; opacity: 0.65;" />
                  </a-button>
                </a-tooltip>
              </div>
              <a-button type="link" size="small" class="chain-action-btn" style="padding: 0; height: auto; font-size: 12px; flex-shrink: 0;" @click="openChainDrawer(record.hostname || record.site)">
                <compass-outlined />{{ assetText('assets.profile') }}
              </a-button>
            </div>
            <div class="mt5" style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">
              <!-- 1. 置顶渲染「待测试」标签 -->
              <a-tag
                v-if="getTags(record).includes('待测试')"
                class="tag-pending-test"
              >
                {{ assetText('assets.toTest') }}
                <a-popconfirm
                  :title="assetText('assets.removeTheToTestTag')"
                  :ok-text="assetText('assets.confirm')"
                  :cancel-text="assetText('tasks.cancel')"
                  @confirm="handleDeleteTag(record, '待测试')"
                >
                  <span class="ant-tag-close-icon" @click.stop>
                    <close-outlined />
                  </span>
                </a-popconfirm>
              </a-tag>

              <!-- 2. 渲染「入口」标签 -->
              <a-tag
                v-if="getTags(record).includes('入口')"
                style="background: var(--arl-bg-light); color: var(--arl-text-color); border-color: var(--arl-border-color);"
              >
                {{ assetText('tasks.entryPoint') }}
                <a-popconfirm
                  :title="assetText('tasks.removeTheEntryPointTag')"
                  :ok-text="assetText('assets.confirm')"
                  :cancel-text="assetText('tasks.cancel')"
                  @confirm="handleDeleteTag(record, '入口')"
                >
                  <span class="ant-tag-close-icon" @click.stop>
                    <close-outlined />
                  </span>
                </a-popconfirm>
              </a-tag>

              <!-- 3. 渲染其余业务自定义标签 -->
              <template v-for="t in getTags(record)" :key="t">
                <a-tag
                  v-if="t !== '待测试' && t !== '入口'"
                  style="background: var(--arl-bg-light); color: var(--arl-text-color); border-color: var(--arl-border-color);"
                >
                  {{ t }}
                  <a-popconfirm
                    :title="assetText('tasks.removeTagTag', { tag: t })"
                    :ok-text="assetText('assets.confirm')"
                    :cancel-text="assetText('tasks.cancel')"
                    @confirm="handleDeleteTag(record, t)"
                  >
                    <span class="ant-tag-close-icon" @click.stop>
                      <close-outlined />
                    </span>
                  </a-popconfirm>
                </a-tag>
              </template>
              <span class="add-tag asset-clickable" @click="openTagModal(record)" >{{ assetText('tasks.addTag') }}</span>
            </div>
          </div>
        </template>

        <template v-else-if="column.key === 'status'">
          <span>{{ record.status || '-' }}</span>
        </template>

        <template v-else-if="column.key === 'screenshot'">
          <img v-if="record.screenshot" :src="`/api${record.screenshot}`" style="width: 240px; height: 135px; object-fit: cover; object-position: top; cursor: pointer; border: 1px solid var(--arl-border-color); border-radius: 4px;" @click="handlePreview(`/api${record.screenshot}`)" />
          <span v-else>-</span>
        </template>

        <template v-else-if="column.key === 'title'">
          <a-tooltip placement="topLeft" :overlayStyle="{ maxWidth: '400px' }">
            <template #title>
              <div style="word-break: break-all;">
                {{ record.title }}
              </div>
            </template>
            <div style="max-width: 190px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
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

        <template v-else-if="column.key === 'record'">
          <div v-if="record.record && record.record.length"><div v-for="(r, i) in record.record" :key="i">{{ r }}</div></div>
          <span v-else-if="typeof record.record === 'string'">{{ record.record }}</span>
          <span v-else>-</span>
        </template>
        <template v-else-if="column.key === 'ips'">
          <div v-if="record.ips && record.ips.length">
            <a-tooltip v-if="record.ips.length > 5" placement="top" :overlayInnerStyle="{ maxHeight: '400px', overflowY: 'auto' }">
              <template #title><div v-for="(ip, i) in record.ips" :key="'all-ip-'+i">{{ ip }}</div></template>
              <div style="cursor: pointer;">
                <div v-for="(ip, i) in record.ips.slice(0, 5)" :key="i">{{ ip }}</div>
                <div class="asset-field-hint">{{ assetText('tasks.andMore') }} {{ record.ips.length }} {{ assetText('tasks.itemsLabel') }}</div>
              </div>
            </a-tooltip>
            <div v-else><div v-for="(ip, i) in record.ips" :key="i">{{ ip }}</div></div>
          </div>
          <span v-else>-</span>
        </template>

        <template v-else-if="column.key === 'ip'">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span style="font-weight: 500; font-family: monospace;">{{ record.ip }}</span>
              <a-tooltip :title="assetText('assets.copyIp')">
                <a-button type="text" size="small" class="cell-copy-btn" @click.stop="handleCopyText(record.ip)">
                  <copy-outlined style="font-size: 11px; opacity: 0.65;" />
                </a-button>
              </a-tooltip>
            </div>
            <a-button type="link" size="small" class="chain-action-btn" style="padding: 0; height: auto; font-size: 12px; flex-shrink: 0;" @click="openChainDrawer(record.ip)">
              <compass-outlined />{{ assetText('assets.profile') }}
            </a-button>
          </div>
        </template>

        <template v-else-if="column.key === 'port_info'">
          <span>{{ record.port_info && record.port_info.length ? record.port_info.map(p => p.port_id).join(', ') : '-' }}</span>
        </template>
        <template v-else-if="column.key === 'os_info'"><span>{{ record.os_info?.name || '-' }}</span></template>
        <template v-else-if="column.key === 'geo_city'"><span>{{ formatGeo(record.geo_city) }}</span></template>
        <template v-else-if="column.key === 'geo_asn'"><span>{{ record.geo_asn?.organization || '-' }}</span></template>
        <template v-else-if="column.key === 'domain'">
          <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px;">
            <div v-if="Array.isArray(record.domain)" style="display: flex; flex-direction: column; gap: 2px;">
              <div v-for="(dom, i) in record.domain" :key="i" style="display: flex; align-items: center; gap: 4px;">
                <span style="font-family: monospace;">{{ dom }}</span>
                <a-tooltip :title="assetText('assets.copyDomain')">
                  <a-button type="text" size="small" class="cell-copy-btn" @click.stop="handleCopyText(dom)">
                    <copy-outlined style="font-size: 11px; opacity: 0.65;" />
                  </a-button>
                </a-tooltip>
              </div>
            </div>
            <div v-else style="display: flex; align-items: center; gap: 6px;">
              <span style="font-weight: 500;">{{ record.domain }}</span>
              <a-tooltip :title="assetText('assets.copyDomain')">
                <a-button type="text" size="small" class="cell-copy-btn" @click.stop="handleCopyText(record.domain)">
                  <copy-outlined style="font-size: 11px; opacity: 0.65;" />
                </a-button>
              </a-tooltip>
            </div>
            <a-button v-if="!Array.isArray(record.domain)" type="link" size="small" class="chain-action-btn" style="padding: 0; height: auto; font-size: 12px; flex-shrink: 0;" @click="openChainDrawer(record.domain)">
              <compass-outlined />{{ assetText('assets.profile') }}
            </a-button>
          </div>
        </template>

        <template v-else-if="column.key === 'ip_cdn_tag'">
          <a-tag v-if="record.is_cdn || record.cdn_name" color="blue">
            {{ record.cdn_name || assetText('tasks.cdnNode') }}
          </a-tag>
          <a-tag v-else color="green">
            {{ assetText('tasks.originServer') }}
          </a-tag>
        </template>

        <template v-else-if="column.key === 'source'">
          <div style="word-break: break-all; color: var(--arl-text-color); line-height: 1.6;">
            <a :href="record.source" target="_blank" style="color: var(--arl-text-color); text-decoration: none;">
              {{ record.source || '-' }}
            </a>
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


        <template v-else-if="column.key === 'cert_detail'">
          <div v-if="record.cert" class="cert-grid-container">
            <a-row :gutter="[16, 4]">
              <!-- 左列：基础信息 -->
              <a-col :xs="24" :sm="14">
                <div class="cert-micro-row">
                  <span class="cert-micro-label">{{ assetText('assets.subject') }}</span>
                  <span class="cert-micro-val font-mono" :title="record.cert.subject_dn">{{ record.cert.subject_dn || '-' }}</span>
                </div>
                <div class="cert-micro-row">
                  <span class="cert-micro-label">{{ assetText('assets.issuer') }}</span>
                  <span class="cert-micro-val" :title="record.cert.issuer_dn">{{ record.cert.issuer_dn || '-' }}</span>
                </div>
                <div class="cert-micro-row">
                  <span class="cert-micro-label">{{ assetText('assets.alternativeNames') }}</span>
                  <span class="cert-micro-val font-mono" :title="record.cert.extensions?.subjectAltName">{{ record.cert.extensions?.subjectAltName || '-' }}</span>
                </div>
                <div class="cert-micro-row">
                  <span class="cert-micro-label">{{ assetText('assets.validity') }}</span>
                  <span class="cert-micro-val">{{ record.cert.validity?.start || '-' }} {{ assetText('tasks.to') }} {{ record.cert.validity?.end || '-' }}</span>
                </div>
              </a-col>

              <!-- 右列：指纹与序列号 -->
              <a-col :xs="24" :sm="10">
                <div class="cert-micro-row">
                  <span class="cert-micro-label">{{ assetText('assets.serialNumber') }}</span>
                  <span class="cert-micro-val font-mono" :title="record.cert.serial_number">{{ record.cert.serial_number || '-' }}</span>
                </div>
                <div class="cert-micro-row">
                  <span class="cert-micro-label">SHA-256：</span>
                  <span class="cert-micro-val font-mono" :title="record.cert.fingerprint?.sha256">{{ record.cert.fingerprint?.sha256 || '-' }}</span>
                </div>
                <div class="cert-micro-row">
                  <span class="cert-micro-label">SHA-1：</span>
                  <span class="cert-micro-val font-mono" :title="record.cert.fingerprint?.sha1">{{ record.cert.fingerprint?.sha1 || '-' }}</span>
                </div>
                <div class="cert-micro-row">
                  <span class="cert-micro-label">MD5：</span>
                  <span class="cert-micro-val font-mono" :title="record.cert.fingerprint?.md5">{{ record.cert.fingerprint?.md5 || '-' }}</span>
                </div>
              </a-col>
            </a-row>
          </div>
          <span v-else>-</span>
        </template>
        <template v-else-if="column.key === 'ip_port'">
          <div v-if="record.service_info && record.service_info.length">
            <div v-for="(info, i) in record.service_info.slice(0, 3)" :key="i" style="line-height: 1.8; font-family: monospace;">
              {{ info.ip }}:{{ info.port_id }}
            </div>
            <div v-if="record.service_info.length > 3" style="margin-top: 4px;">
              <a-button
                type="link"
                size="small"
                style="padding: 0; height: auto; font-size: 12px;"
                @click="openServiceDetailModal(record)"
              >
                {{ assetText('tasks.viewAllTotal', { count: record.service_info.length }) }}
              </a-button>
            </div>
          </div>
          <span v-else>-</span>
        </template>
        <template v-else-if="column.key === 'product'">
          <div v-if="record.service_info && record.service_info.length">
            <div v-for="(info, i) in record.service_info.slice(0, 3)" :key="i" style="line-height: 1.8;">
              {{ info.product || '-' }}
            </div>
            <div
              v-if="record.service_info.length > 3"
              style="margin-top: 4px; height: 22px; line-height: 22px; color: var(--arl-text-color); opacity: 0.45; font-size: 12px;"
            >
              ...
            </div>
          </div>
          <span v-else>-</span>
        </template>
        <template v-else-if="column.key === 'fileleak_url' || column.key === 'url_link' || column.key === 'nuclei_vuln_url'">
          <a :href="record.url || record.vuln_url" target="_blank" style="word-break: break-all;">{{ record.url || record.vuln_url || '-' }}</a>
        </template>
        <template v-else-if="column.key === 'verify_data'">
          <div style="max-height: 100px; overflow-y: auto; color: #e57373; font-family: monospace; font-size: 12px; word-break: break-all;">{{ record.verify_data || record.proof || '-' }}</div>
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
          <div style="max-height: 100px; overflow-y: auto; background: var(--arl-bg-light); padding: 4px 8px; border-radius: 4px; font-family: monospace; font-size: 12px; word-break: break-all;">{{ record.verify_command || record.curl_command || '-' }}</div>
        </template>
        <template v-else-if="column.key === 'finger_name'">
          <a style="cursor: pointer;" @click="openFingerModal(record.name)">{{ record.name || '-' }}</a>
        </template>
        <template v-else-if="column.key === 'host'">
          <span>{{ record.ip || record.host }}{{ record.port ? ':' + record.port : '' }}</span>
        </template>
        <template v-else-if="column.key === 'update_date'">
          <span>{{ record.update_date || record.insert_time || '-' }}</span>
        </template>
      </template>

      <template #emptyText>
        <div class="empty-default-box">
          <a-empty :description="assetText('assets.noAssetData')" />
        </div>
      </template>
    </a-table>

    <!-- 指纹统计关联站点弹窗 -->    <!-- 指纹统计关联站点弹窗 -->
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

    <WihApiDetailsDrawer v-model:open="wihApiDetailsOpen" :record="wihApiDetailsRecord" :context-key="route.fullPath + ':' + activeTab" />

    <!-- 综合C段详情弹窗 (提取为组件) -->
    <CidrDetailModal v-model:open="cipDetailModalVisible" :record="currentCidrRecord" />

    <!-- 系统服务端点详情弹窗 (提取为组件) -->
    <ServiceDetailModal v-model:open="serviceDetailModalVisible" :record="currentServiceRecord" />

    <!-- 图片预览组件 -->
    <a-modal v-model:open="previewVisible" :footer="null" width="85vw" centered @cancel="previewVisible = false" :bodyStyle="{ padding: '16px' }">
      <img :src="previewImage" style="width: 100%; max-height: 85vh; object-fit: contain; display: block;" />
    </a-modal>

    <!-- 添加标签弹窗 -->
    <a-modal v-model:open="tagVisible" :title="assetText('tasks.addTag')" @ok="submitTag" :confirmLoading="tagSubmitLoading" width="400px" :okText="assetText('tasks.confirm')" :cancelText="assetText('assets.cancel')">
      <div style="margin-top: 20px;">
        <a-input v-model:value="newTagValue" :placeholder="assetText('tasks.enterATagName')" />
      </div>
    </a-modal>


    <div v-if="tabConfig[effectiveTab]" style="display: flex; justify-content: space-between; align-items: center; padding: 0 16px; margin-top: 10px;">
      <div class="asset-summary-caption">{{ assetText('tasks.paginationSummary', { pages: Math.ceil(pagination.total / pagination.pageSize) || 1, total: pagination.total }) }}</div>
      <a-pagination size="small" :pageSizeOptions="$pageSizeOptions" v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" @showSizeChange="handleTableChange" />
    </div>

    <!-- 悬浮浮动批处理条 (Floating Action Bar) -->
    <transition name="floating-slide">
      <div v-if="hasSelected" class="arl-floating-action-bar">
        <div class="floating-info">
          <check-circle-filled style="color: var(--arl-theme-color); font-size: 16px;" />
          <span>{{ assetText('tasks.selected') }} <b class="asset-selection-number">{{ selectedRowKeys.length }}</b> {{ assetText('assets.assets') }}</span>
        </div>
        <div class="floating-actions">
          <a-button danger size="middle" @click="handleBatchDelete">
            <template #icon><delete-outlined /></template>
            {{ assetText('tasks.deleteSelected') }}
          </a-button>
          <a-button v-if="activeTab === 'site'" type="primary" size="middle" @click="openRiskModal">
            <template #icon><bug-outlined /></template>
            {{ assetText('assets.riskScanCount', { count: selectedRowKeys.length }) }}
          </a-button>
          <a-button size="middle" @click="selectedRowKeys = []">{{ assetText('tasks.clearSelection') }}</a-button>
        </div>
      </div>
    </transition>
  </div>

  <!-- OSINT 企业生态资产视角 -->
  <div v-show="currentView === 'osint'">
    <EnterpriseOsintPanel
      v-if="boundIcpTaskId"
      ref="osintPanelRef"
      :task-id="boundIcpTaskId"
      :scope-id="scope_id"
      :enterprise-name="scopeEnterpriseName"
      :updating-task-id="scopeUpdatingTaskId"
      :hide-header="true"
      :sticky-top-offset="heroHeight"
      @taskLoaded="handleOsintLoaded"
      @synced="handleOsintSynced"
      @openBind="openBindModal"
      @refreshed="(newTid) => { if (newTid) { boundIcpTaskId = newTid; scopeUpdatingTaskId = ''; fetchBoundTaskDetail(newTid); fetchScopeMeta(); } }"
    />
    <div v-else class="osint-unbound-box">
      <a-empty :description="assetText('assets.noOrganizationLinked')" />
    </div>
  </div>

    <a-modal v-model:open="addSiteVisible" :title="assetText('assets.addWebsite')" @ok="submitAddSite" :confirmLoading="addSiteLoading" width="520px" :okText="assetText('tasks.confirm')" :cancelText="assetText('assets.cancel')" destroyOnClose>
      <a-form :label-wrap="true" ref="addSiteFormRef" :model="addSiteForm" :rules="addSiteRules" :label-col="{ span: assetLocale !== 'zh-CN' ? 6 : 4 }" :wrapper-col="{ span: assetLocale !== 'zh-CN' ? 17 : 19 }" class="asset-risk-form">
        <a-form-item :label="assetText('tasks.websites')" name="site">
          <a-textarea v-model:value="addSiteForm.site" :rows="4" :placeholder="assetText('assets.theWebsiteWillBeScannedForItsTitle')" />
        </a-form-item>
        <a-form-item :label="assetText('tasks.policy')" name="policy_id">
          <a-select v-model:value="addSiteForm.policy_id" :placeholder="assetText('tasks.selectAPolicy')">
            <a-select-option v-for="p in policies" :key="p._id" :value="p._id">{{ p.name }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="riskModalVisible" :title="assetText('tasks.addRiskScanningTask')" @ok="submitRiskTask" :confirmLoading="riskLoading" width="520px" :okText="assetText('tasks.confirm')" :cancelText="assetText('assets.cancel')" destroyOnClose>
      <a-form :label-wrap="true" ref="riskFormRef" :model="riskForm" :rules="riskRules" :label-col="{ span: assetLocale !== 'zh-CN' ? 7 : 5 }" :wrapper-col="{ span: assetLocale !== 'zh-CN' ? 16 : 18 }" class="asset-risk-form">

        <a-form-item :label="assetText('tasks.policyName')" name="policy_id">
          <a-select v-model:value="riskForm.policy_id" :placeholder="assetText('tasks.selectAPolicy')" @change="handleRiskPolicyChange">
            <a-select-option v-for="p in policies" :key="p._id" :value="p._id">
              {{ p.name }} (PoC : {{ getPocCount(p) }})
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item :label="assetText('assets.taskName')" name="name">
          <a-input v-model:value="riskForm.name" :placeholder="assetText('tasks.enterATaskName')" allowClear />
        </a-form-item>

        <a-form-item :label="assetText('tasks.target')" class="asset-flush-bottom">
          <span class="asset-muted">{{ assetText('assets.selectedTargets') }} {{ currentTargetCount }}</span>
        </a-form-item>

      </a-form>
    </a-modal>

    <a-modal v-model:open="addDomainVisible" :title="assetText('assets.addSubdomain')" @ok="submitAddDomain" :confirmLoading="addDomainLoading" width="520px" :okText="assetText('tasks.confirm')" :cancelText="assetText('assets.cancel')" destroyOnClose>
      <a-form :label-wrap="true" ref="addDomainFormRef" :model="addDomainForm" :rules="addDomainRules" :label-col="{ span: assetLocale !== 'zh-CN' ? 6 : 4 }" :wrapper-col="{ span: assetLocale !== 'zh-CN' ? 17 : 19 }" class="asset-risk-form">
        <a-form-item :label="assetText('tasks.subdomains')" name="domain">
          <a-textarea v-model:value="addDomainForm.domain" :rows="4" :placeholder="assetText('assets.aDiscoveryTaskWillRetrieveIpsWebsitesAnd')" />
        </a-form-item>
        <a-form-item :label="assetText('tasks.policy')" name="policy_id">
          <a-select v-model:value="addDomainForm.policy_id" :placeholder="assetText('tasks.selectAPolicy')">
            <a-select-option v-for="p in policies" :key="p._id" :value="p._id">{{ p.name }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 绑定企业主体弹窗 -->
    <a-modal
      v-model:open="bindModalVisible"
      :title="boundIcpTaskId ? assetText('assets.changeLinkedOrganization') : assetText('assets.linkOrganization')"
      @ok="handleBindSubmit"
      :confirmLoading="bindLoading"
      width="540px"
      wrapClassName="arl-theme-modal"
      :okText="assetText('tasks.confirm')"
      :cancelText="assetText('assets.cancel')"
      destroyOnClose
    >
      <a-form :label-wrap="true" :label-col="{ span: assetLocale !== 'zh-CN' ? 7 : 5 }" :wrapper-col="{ span: assetLocale !== 'zh-CN' ? 16 : 18 }" class="asset-risk-form">
        <a-form-item :label="assetText('assets.linkMethod')">
          <a-radio-group v-model:value="bindMode">
            <a-radio value="existing">{{ assetText('assets.selectAnExistingDiscoveryTask') }}</a-radio>
            <a-radio value="new">{{ assetText('assets.startNewEnterpriseDiscovery') }}</a-radio>
          </a-radio-group>
        </a-form-item>

        <template v-if="bindMode === 'existing'">
          <a-form-item :label="assetText('tasks.enterpriseOsint')" required>
            <a-select
              v-model:value="selectedBindTaskId"
              :placeholder="assetText('assets.selectAnExistingEnterpriseDiscoveryTask')"
              show-search
              option-filter-prop="label"
              :options="completedIcpTasks.map(t => ({
                value: t._id,
                label: t.task_type === 'tyc'
                  ? assetText('assets.nameCombinedDiscoveryTarget', { name: t.name || t.target, target: t.gid || (t.target ? t.target.replace(/^TYC_/, '') : '') })
                  : assetText('assets.nameOfficialIcpRecords', { name: t.target || t.name })
              }))"
            />
          </a-form-item>
        </template>

        <template v-else>
          <a-form-item
            :label="assetText('tasks.targetOrganization')"
            required
            :tooltip="assetText('assets.pasteATianyanchaCompanyUrlSuchAsHttps')"
          >
            <a-input
              v-model:value="newEnterpriseTarget"
              :placeholder="assetText('assets.pasteATianyanchaUrlGidOrFullRegistered')"
              allowClear
              @pressEnter="handleBindSubmit"
            >
              <template #prefix>
                <component :is="parsedBindGid ? 'LinkOutlined' : 'BankOutlined'" style="color: #bfbfbf;" />
              </template>
            </a-input>
            <div v-if="parsedBindGid" style="margin-top: 4px; font-size: 12px; color: var(--ant-primary-color); display: flex; align-items: center; gap: 4px;">
              <check-circle-outlined /> <span>{{ assetText('tasks.parsedTianyanchaGid') }} <b>{{ parsedBindGid }}</b> {{ assetText('tasks.theGidWillBeVerifiedAndCombinedDiscovery') }}</span>
            </div>
            <div v-else-if="newEnterpriseTarget.trim().length >= 2" style="margin-top: 4px; font-size: 12px; color: #722ed1; display: flex; align-items: center; gap: 4px;">
              <safety-certificate-outlined /> <span>{{ assetText('assets.registeredOrganizationIdentifiedSourceOfficialMiitIcpRecords') }}</span>
            </div>
          </a-form-item>
        </template>
      </a-form>
    </a-modal>

    <!-- 全链路画像滑出抽屉 -->
    <ChainDrawer
      v-model:open="chainDrawerVisible"
      :target="chainDrawerTarget"
      :scope-id="scope_id"
      @close="handleDrawerClose"
    />

    <!-- 原始数据 JSON 抽屉 -->
    <RawDataDrawer
      v-model:open="rawDrawerVisible"
      :data="currentRawRecord"
    />


  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';
defineOptions({ name: 'GroupAssetsDetail' });

import { ref, onMounted, reactive, watch, computed, createVNode, onUnmounted, onDeactivated, nextTick } from 'vue';
const heroRef = ref(null);
const asmControlRef = ref(null);
const heroHeight = ref(48);
const asmControlHeight = ref(80);
const scrollContainer = ref(null);

let heroResizeObserver = null;
let asmResizeObserver = null;

const updateHeroHeight = () => {
  if (heroRef.value && typeof heroRef.value.getBoundingClientRect === 'function') {
    const rect = heroRef.value.getBoundingClientRect();
    if (rect.height > 0) {
      heroHeight.value = Math.round(rect.height);
    }
  }
};

const updateAsmControlHeight = () => {
  if (asmControlRef.value && typeof asmControlRef.value.getBoundingClientRect === 'function') {
    const rect = asmControlRef.value.getBoundingClientRect();
    if (rect.height > 0) {
      asmControlHeight.value = Math.round(rect.height);
    }
  }
};

const totalAsmOffsetHeader = computed(() => {
  return heroHeight.value + asmControlHeight.value;
});

const asmStickyConfig = computed(() => {
  if (!scrollContainer.value) return false;
  return {
    offsetHeader: totalAsmOffsetHeader.value,
    offsetScroll: 0,
    getContainer: () => scrollContainer.value
  };
});

const windowHeight = ref(typeof window !== 'undefined' ? window.innerHeight : 800);
const onWindowResize = () => {
  windowHeight.value = window.innerHeight;
};

// 当 pageSize >= 100 开启虚拟滚动时，动态计算 tableScrollY 可视滚动区域高度
const tableScrollY = computed(() => {
  const barHeight = totalAsmOffsetHeader.value || 300;
  const available = windowHeight.value - barHeight - 160;
  return Math.max(300, available);
});

onMounted(() => {
  scrollContainer.value = document.querySelector('.ant-layout-content');
  window.addEventListener('resize', onWindowResize);

  heroResizeObserver = new ResizeObserver(updateHeroHeight);
  if (heroRef.value) {
    heroResizeObserver.observe(heroRef.value);
  }
  updateHeroHeight();

  asmResizeObserver = new ResizeObserver(updateAsmControlHeight);
  if (asmControlRef.value) {
    asmResizeObserver.observe(asmControlRef.value);
  }
  updateAsmControlHeight();
});

onUnmounted(() => {
  window.removeEventListener('resize', onWindowResize);
  if (heroResizeObserver) heroResizeObserver.disconnect();
  if (asmResizeObserver) asmResizeObserver.disconnect();
});

import { useRoute, useRouter } from 'vue-router';
import request from '../utils/request';
import HttpStatusFilter from '../components/HttpStatusFilter.vue';
import { buildAssetFilterParams, formatAssetFilterOperator } from '../utils/assetFilters';
import { formatGeo } from '../utils/formatGeo';
import { message, Modal } from 'ant-design-vue';
import dayjs from 'dayjs';
import CidrDetailModal from '../components/CidrDetailModal.vue';
import WihApiDetailsDrawer from '../components/WihApiDetailsDrawer.vue';
import { isApiEndpointRecord } from '../utils/wihApi';
import ServiceDetailModal from '../components/ServiceDetailModal.vue';
import EnterpriseOsintPanel from '../components/EnterpriseOsintPanel.vue';
import ChainDrawer from '../components/ChainDrawer.vue';
import RawDataDrawer from '../components/RawDataDrawer.vue';
import { copyText } from '../utils/clipboard';
import {
  ArrowLeftOutlined,
  ExclamationCircleOutlined,
  LinkOutlined,
  BankOutlined,
  ClusterOutlined,
  SyncOutlined,
  GlobalOutlined,
  PlusOutlined,
  DownloadOutlined,
  BugOutlined,
  FilterOutlined,
  DownOutlined,
  UpOutlined,
  SearchOutlined,
  RedoOutlined,
  CopyOutlined,
  CompassOutlined,
  CloseOutlined,
  DeleteOutlined,
  CheckCircleOutlined,
  SafetyCertificateOutlined
} from '@ant-design/icons-vue';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import { formatTaskStatus, formatTaskStatusColor } from '../constants/taskStatus';
import { createTabStateCache } from '../utils/useTabStateCache';

const { t: assetText, locale: assetLocale } = useI18n({ useScope: 'global' });

const wihApiDetailsOpen = ref(false);
const wihApiDetailsRecord = ref(null);
const showWihApiDetails = record => {
  if (!isApiEndpointRecord(record)) return;
  wihApiDetailsRecord.value = record;
  wihApiDetailsOpen.value = true;
};

const route = useRoute();
const router = useRouter();

const handleBack = () => {
  router.push('/group');
};
// 🚨 修复 1：使用 computed，让路由参数具备真正的响应式
const scope_id = computed(() => route.query.scope_id || '');
const scopeEnterpriseName = ref('');
const targetName = computed(() => {
  const t = route.query.targetName;
  if (!t || /^[0-9a-fA-F]{24}$/.test(t) || t === '未知资产') {
    return scopeEnterpriseName.value || (t === '未知资产' ? assetText('assets.unknownAsset') : t) || assetText('assets.enterpriseAssets');
  }
  return t;
});

// 高级筛选折叠状态
const isAdvancedFilterOpen = ref(true);

// 双视角状态 (OSINT vs ASM，默认优先激活 OSINT)
const currentView = ref(route.query.view === 'asm' ? 'asm' : 'osint');

// 监听 currentView 变化，通过 router.replace 同步更新 URL query 参数
watch(currentView, (newVal) => {
  if (route.query.view !== newVal) {
    router.replace({
      query: {
        ...route.query,
        view: newVal
      }
    });
  }
});

// 监听路由 query.view 变化，支持浏览器前进/后退联动
watch(() => route.query.view, (newVal) => {
  const target = newVal === 'asm' ? 'asm' : 'osint';
  if (currentView.value !== target) {
    currentView.value = target;
  }
});

const osintPanelRef = ref(null);
const boundIcpTaskId = ref('');
const scopeUpdatingTaskId = ref('');
const scopeHasIncrement = ref(false);
const scopeGroupName = ref('');
const scopeType = ref('');
const scopeDomainList = ref([]);
const boundTaskRecord = ref({});
const taskTarget = ref('');
const taskTypeLabel = computed(() => {
  const type = boundTaskRecord.value.task_type;
  if (type === 'tyc') return assetText('tasks.combinedSources');
  if (type === 'icp') return assetText('tasks.officialIcpRecordsLabel');
  return boundIcpTaskId.value ? assetText('tasks.enterpriseOsint') : '';
});
const taskStatusLabel = computed(() => boundTaskRecord.value.status ? formatTaskStatus(boundTaskRecord.value.status) : '');
const taskStatusColor = ref('default');
const osintTotalCount = ref(0);

const asmTabList = [
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

const asmCounts = reactive({
  site: 0,
  domain: 0,
  ip: 0,
  cert: 0,
  service: 0,
  fileleak: 0,
  url: 0,
  cip: 0,
  stat_finger: 0,
  wih: 0,
  vuln: 0,
  npoc_service: 0,
  nuclei_result: 0
});

const asmTotalCount = computed(() => {
  return Object.values(asmCounts).reduce((acc, cur) => acc + (Number(cur) || 0), 0);
});

const activeFilterCount = computed(() => {
  let cnt = 0;
  for (const k in searchForm.value) {
    const val = searchForm.value[k];
    if (val !== '' && val != null) {
      if (Array.isArray(val) && val.length === 0) continue;
      cnt++;
    }
  }
  return cnt;
});

const handleCopyText = async (text) => {
  if (!text) return;
  const ok = await copyText(String(text).trim());
  if (ok) message.success(assetText('assets.copiedValue', { value: text }));
};

const chainDrawerVisible = ref(false);
const chainDrawerTarget = ref('');

const openChainDrawer = (target) => {
  if (!target) return;
  const cleanTarget = String(target).trim();
  chainDrawerTarget.value = cleanTarget;
  chainDrawerVisible.value = true;
  if (route.query.chain_target !== cleanTarget) {
    const nextQuery = { ...route.query, chain_target: cleanTarget };
    router.replace({ query: nextQuery });
  }
};

const handleDrawerClose = () => {
  chainDrawerVisible.value = false;
  if (route.query.chain_target) {
    const nextQuery = { ...route.query };
    delete nextQuery.chain_target;
    router.replace({ query: nextQuery });
  }
};

const rawDrawerVisible = ref(false);
const currentRawRecord = ref({});

const openRawDrawer = (record) => {
  currentRawRecord.value = record;
  rawDrawerVisible.value = true;
};

const handleOsintLoaded = (payload) => {
  if (!payload) return;
  boundTaskRecord.value = payload.task || {};
  taskTarget.value = payload.taskTarget || '';
  taskStatusColor.value = payload.taskStatusColor || 'default';
  osintTotalCount.value = payload.totalCount || 0;
};

const fetchBoundTaskDetail = async (taskId) => {
  if (!taskId) return;
  try {
    const res = await request.get('/icp/task', { params: { _id: taskId } });
    if (res.code === 200 && res.items && res.items.length > 0) {
      const task = res.items[0];
      boundTaskRecord.value = task;
      taskTarget.value = task.target || '';
      taskStatusColor.value = formatTaskStatusColor(task.status);
      const stats = task.statistic || {};
      osintTotalCount.value = (
        (stats.web_cnt || 0) +
        (stats.app_cnt || 0) +
        (stats.mapp_cnt || 0) +
        (stats.wechat_cnt || 0) +
        (stats.weibo_cnt || 0) +
        (stats.kapp_cnt || 0) +
        (stats.invest_cnt || 0)
      );
    }
  } catch (e) {}
};

const fetchAsmCounts = async () => {
  if (!scope_id.value) return;
  const keys = Object.keys(tabConfig);
  await Promise.allSettled(
    keys.map(async (key) => {
      const config = tabConfig[key];
      if (!config || !config.url) return;
      try {
        const res = await request.get(config.url, {
          params: { page: 1, size: 1, scope_id: scope_id.value }
        });
        if (res && res.code === 200) {
          asmCounts[key] = res.total || 0;
        }
      } catch (e) {}
    })
  );
};

const bindModalVisible = ref(false);
const bindLoading = ref(false);
const bindMode = ref('existing');
const selectedBindTaskId = ref(undefined);
const completedIcpTasks = ref([]);
const newEnterpriseTarget = ref('');

const parseBindTargetInput = (input) => {
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

const parsedBindGid = computed(() => {
  const parsed = parseBindTargetInput(newEnterpriseTarget.value);
  return parsed.gid;
});

const fetchScopeMeta = async () => {
  if (!scope_id.value) return;
  try {
    const res = await request.get('/asset_scope/', { params: { _id: scope_id.value } });
    if (res && res.code === 200 && res.items && res.items.length > 0) {
      const item = res.items[0];
      boundIcpTaskId.value = item.synced_icp_task_id || '';
      scopeUpdatingTaskId.value = item.updating_icp_task_id || '';
      scopeEnterpriseName.value = item.enterprise_name || item.name || '';
      scopeHasIncrement.value = !!item.has_increment;
      scopeGroupName.value = item.group_name || '';
      scopeType.value = item.scope_type || '';
      scopeDomainList.value = item.domain_array || (item.scope ? item.scope.split(',').map(s => s.trim()).filter(Boolean) : []);
      if (boundIcpTaskId.value) {
        fetchBoundTaskDetail(boundIcpTaskId.value);
      }
      fetchAsmCounts();
    }
  } catch (err) {
    console.error('获取资产组企业元信息失败', err);
  }
};

const openBindModal = async () => {
  bindModalVisible.value = true;
  selectedBindTaskId.value = boundIcpTaskId.value || undefined;
  newEnterpriseTarget.value = '';
  bindMode.value = 'existing';
  try {
    const res = await request.get('/icp/task', { params: { size: 100 } });
    if (res && res.code === 200) {
      completedIcpTasks.value = res.items || [];
    }
  } catch (err) {
    console.error('获取已完成测绘任务失败', err);
  }
};

const executeBindExisting = async () => {
  bindLoading.value = true;
  try {
    const res = await request.post('/asset_scope/bind_enterprise/', {
      scope_id: scope_id.value,
      task_id: selectedBindTaskId.value
    });
    if (res && res.code === 200) {
      message.success(boundIcpTaskId.value ? assetText('assets.linkedOrganizationUpdated') : assetText('assets.organizationLinked'));
      bindModalVisible.value = false;
      fetchScopeMeta();
      currentView.value = 'osint';
    } else {
      message.error(res.message || assetText('assets.failedToLinkOrganization'));
    }
  } catch (err) {
    message.error(assetText('assets.networkRequestFailed'));
  } finally {
    bindLoading.value = false;
  }
};

const executeBindNew = async () => {
  const targetVal = newEnterpriseTarget.value.trim();
  if (!targetVal) {
    message.warning(assetText('assets.enterATianyanchaCompanyUrlGidOrFull'));
    return;
  }
  const parsed = parseBindTargetInput(targetVal);
  if (!parsed.gid && !parsed.isName) {
    message.warning(assetText('tasks.noValidTargetRecognizedEnterATianyanchaUrl'));
    return;
  }
  bindLoading.value = true;
  try {
    let createRes;
    if (parsed.gid) {
      createRes = await request.post('/icp/tyc_task', {
        name: `${targetName.value}全景测绘`,
        gid: parsed.gid,
        company_name: targetName.value,
        depth: 1,
        invest_ratio: 50,
        enable_icp: true,
        query_type: ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo']
      });
    } else {
      createRes = await request.post('/icp/task', {
        name: `${targetName.value}全景测绘`,
        target: targetVal,
        query_type: ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo']
      });
    }

    if (createRes && createRes.code === 200) {
      const newTaskId = createRes.data?.task_id || createRes.data?._id || createRes.task_id;
      if (newTaskId) {
        await request.post('/asset_scope/bind_enterprise/', {
          scope_id: scope_id.value,
          task_id: newTaskId
        });
      }
      message.success(assetText('assets.enterpriseDiscoveryStartedAndLinked'));
      bindModalVisible.value = false;
      fetchScopeMeta();
      currentView.value = 'osint';
    } else {
      message.error(createRes.message || assetText('assets.failedToCreateDiscoveryTask'));
    }
  } catch (err) {
    message.error(assetText('assets.networkRequestFailed'));
  } finally {
    bindLoading.value = false;
  }
};

const handleBindSubmit = async () => {
  if (bindMode.value === 'existing') {
    if (!selectedBindTaskId.value) {
      message.warning(assetText('assets.selectADiscoveryTaskToLink'));
      return;
    }
    // 若已绑定主体且用户选择了不同的测绘任务，弹出二次确认
    if (boundIcpTaskId.value && selectedBindTaskId.value !== boundIcpTaskId.value) {
      Modal.confirm({
        title: assetText('assets.changeLinkedOrganizationLabel'),
        content: assetText('assets.changingTheLinkedOrganizationAlsoReplacesTheCompany'),
        okText: assetText('assets.changeOrganization'),
        cancelText: assetText('tasks.cancel'),
        onOk: () => {
          executeBindExisting();
        }
      });
      return;
    }
    await executeBindExisting();
  } else {
    // 若已绑定主体，用户选择发起新测绘并绑定，也弹出二次确认
    if (boundIcpTaskId.value) {
      Modal.confirm({
        title: assetText('assets.startDiscoveryAndChangeLinkedOrganization'),
        content: assetText('assets.thisAssetGroupAlreadyHasALinkedOrganization'),
        okText: assetText('assets.startDiscovery'),
        cancelText: assetText('tasks.cancel'),
        onOk: () => {
          executeBindNew();
        }
      });
      return;
    }
    await executeBindNew();
  }
};

const handleOsintSynced = () => {
  fetchScopeMeta();
  if (fetchData) fetchData();
};

const isScopeSwitching = ref(false);
const activeTab = ref('site');
const serviceEngineType = ref('nmap'); // 'nmap' | 'npoc'
const effectiveTab = computed(() => {
  if (activeTab.value === 'service' && serviceEngineType.value === 'npoc') {
    return 'npoc_service';
  }
  return activeTab.value;
});

const onServiceEngineChange = () => {
  const currentTab = effectiveTab.value;
  selectedRowKeys.value = [];
  columns.value = tabConfig[currentTab]?.cols || [];
  searchForm.value = tabCache.getTabSearchForm(currentTab);
  tabCache.applyTabOperators(currentTab);
  pagination.current = tabCache.getTabPage(currentTab) || 1;
  const cached = tabCache.getMemoryCache(currentTab, pagination.pageSize);
  if (cached) {
    dataSource.value = cached.dataSource;
    pagination.total = cached.total;
    lastFetchedPage = pagination.current;
    lastFetchedSize = pagination.pageSize;
  } else {
    fetchData();
  }
};
const loading = ref(false);
const dataSource = ref([]);

const previewVisible = ref(false);
const previewImage = ref('');
const handlePreview = (url) => { previewImage.value = url; previewVisible.value = true; };
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

const selectedRowKeys = ref([]);
const hasSelected = computed(() => selectedRowKeys.value.length > 0);
const onSelectChange = (keys) => { selectedRowKeys.value = keys; };

// 标签管理逻辑
const tagVisible = ref(false);
const tagSubmitLoading = ref(false);
const newTagValue = ref('');
const currentTagRecord = ref(null);

const openTagModal = (record) => {
  currentTagRecord.value = record;
  newTagValue.value = '';
  tagVisible.value = true;
};

const getTags = (record) => {
  if (!record || !record.tag) return [];
  return Array.isArray(record.tag) ? record.tag : [record.tag];
};

const syncTagState = (targetId, newTags) => {
  if (!targetId) return;
  // 同步常规列表 dataSource 中的对应项
  if (Array.isArray(dataSource.value)) {
    const tableSite = dataSource.value.find(s => (s._id || s.id) === targetId);
    if (tableSite) {
      tableSite.tag = [...newTags];
    }
  }
};

const submitTag = async () => {
  if (!newTagValue.value.trim()) {
    message.warning(assetText('assets.tagContentCannotBeEmpty'));
    return;
  }
  tagSubmitLoading.value = true;
  try {
    const targetId = currentTagRecord.value?._id || currentTagRecord.value?.id;
    const tag = newTagValue.value.trim();
    const res = await request.post('/asset_site/add_tag/', {
      _id: targetId,
      tag: tag
    });
    if (res.code === 200) {
      message.success(assetText('tasks.tagAdded'));
      tagVisible.value = false;
      if (currentTagRecord.value) {
        if (!Array.isArray(currentTagRecord.value.tag)) {
          currentTagRecord.value.tag = currentTagRecord.value.tag ? [currentTagRecord.value.tag] : [];
        }
        if (!currentTagRecord.value.tag.includes(tag)) {
          currentTagRecord.value.tag.push(tag);
        }
        syncTagState(targetId, currentTagRecord.value.tag);
      }
      tabCache.invalidateMemoryCache(activeTab.value);
      tabCache.invalidateMemoryCache('site');
      fetchData(); // 重新加载数据
    } else {
      message.error(res.message || assetText('tasks.failedToAddTag'));
    }
  } catch (error) {
    message.error(assetText('tasks.requestFailed'));
  } finally {
    tagSubmitLoading.value = false;
  }
};

const handleDeleteTag = async (record, tag) => {
  const targetId = record?._id || record?.id;
  if (!targetId) return;
  try {
    const res = await request.post('/asset_site/delete_tag/', {
      _id: targetId,
      tag: tag
    });
    if (res.code === 200) {
      message.success(assetText('tasks.removedTagTag', { tag: tag }));
      const currentTags = Array.isArray(record.tag) ? record.tag : (record.tag ? [record.tag] : []);
      record.tag = currentTags.filter(t => t !== tag);
      syncTagState(targetId, record.tag);
      tabCache.invalidateMemoryCache(activeTab.value);
      tabCache.invalidateMemoryCache('site');
    } else {
      message.error(res.message || assetText('tasks.failedToDeleteTag'));
    }
  } catch (error) {
    message.error(assetText('tasks.requestFailed'));
  }
};

// 指纹统计弹窗状态与方法
const fingerModalVisible = ref(false);
const currentFingerName = ref('');
const fingerModalData = ref([]);
const fingerModalLoading = ref(false);

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
    const res = await request.get('/asset_site/', {
      params: {
        scope_id: scope_id.value,
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

// C段详情弹窗 (提取为组件)
const cipDetailModalVisible = ref(false);
const currentCidrRecord = ref(null);

const openCidrDetail = (record) => {
  currentCidrRecord.value = record;
  cipDetailModalVisible.value = true;
};

// 系统服务端点详情弹窗
const serviceDetailModalVisible = ref(false);
const currentServiceRecord = ref(null);

const openServiceDetailModal = (record) => {
  currentServiceRecord.value = record;
  serviceDetailModalVisible.value = true;
};


// 💡 针对分组详情定制的 Config (以站点为例，去掉了截图，加了更新时间)
// 💡 完整版的 Config：涵盖站点、域名、IP、WIH
// 💡 修复版 Config：使用 asset_ 前缀的专属接口，并修正日期字段
const tabConfig = reactive({
  site: {
    url: '/asset_site/', // 🚨 核心修复：加了 asset_ 前缀
    exportUrl: '/asset_site/export/', // 🚨 绑定抓包里的导出 URL
    get tabName() { return assetText('tasks.websites'); },
    searchFields: [
      { get label() { return assetText('tasks.websites'); }, key: 'site', operator: '=' },
      { get label() { return assetText('tasks.title'); }, key: 'title', operator: '=' },
      { get label() { return assetText('tasks.webServer'); }, key: 'http_server', operator: '=' },
      { get label() { return assetText('tasks.statusCode'); }, key: 'status', type: 'httpStatus' },
      // 🚨 补充丢失的 4 个字段
      { get label() { return assetText('tasks.headers'); }, key: 'headers', operator: '=' },
      { get label() { return assetText('tasks.fingerprints'); }, key: 'finger', operator: '=' },
      { get label() { return assetText('tasks.faviconHash'); }, key: 'favicon.hash', operator: '=' },
      { get label() { return assetText('tasks.tags'); }, key: 'tag', operator: '=' },
      { get label() { return assetText('assets.updatedAtLabel'); }, key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 50, align: 'center' },
      { get title() { return assetText('tasks.websites'); }, dataIndex: 'site', key: 'site', width: 260 },
      { get title() { return assetText('tasks.statusCode'); }, dataIndex: 'status', key: 'status', width: 75, align: 'center' },
      { get title() { return assetText('tasks.title'); }, dataIndex: 'title', key: 'title', width: 200 },
      { get title() { return assetText('tasks.headers'); }, key: 'headers', width: 360 },
      { get title() { return assetText('tasks.fingerprints'); }, key: 'finger', width: 200 },
      { get title() { return assetText('assets.updatedAtLabel'); }, dataIndex: 'update_date', key: 'update_date', width: 160, align: 'center' },
      { get title() { return assetText('tasks.screenshot'); }, key: 'screenshot', width: 250 }
    ]
  },
  domain: {
    url: '/asset_domain/',
    exportUrl: '/asset_domain/export/',
    get tabName() { return assetText('tasks.subdomains'); },
    // 🚨 修复：严格对齐截图中的 6 个搜索框顺序和文案
    searchFields: [
      { get label() { return assetText('tasks.domains'); }, key: 'domain', operator: '=' },
      { get label() { return assetText('tasks.recordValue'); }, key: 'record', operator: '=' },
      { get label() { return assetText('tasks.type'); }, key: 'type', operator: '=' }, // 调整到第 3 位
      { label: 'IP', key: 'ips', operator: '=' },    // 调整到第 4 位
      { get label() { return assetText('tasks.source'); }, key: 'source', operator: '=' },
      { get label() { return assetText('assets.updatedAtLabel'); }, key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      // ... cols 保持不变，上一轮猜得完全正确 ...
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return assetText('tasks.domains'); }, dataIndex: 'domain', key: 'domain', width: 220 },
      { get title() { return assetText('tasks.dnsRecordType'); }, dataIndex: 'type', key: 'type', width: 100 },
      { get title() { return assetText('tasks.recordValue'); }, key: 'record', width: 280 },
      { get title() { return assetText('tasks.associatedIps'); }, key: 'ips', width: 280 },
      { get title() { return assetText('tasks.source'); }, dataIndex: 'source', key: 'source', width: 150 },
      { get title() { return assetText('assets.updatedAtLabel'); }, dataIndex: 'update_date', key: 'update_date', width: 180 }
    ]
  },
  ip: {
    url: '/asset_ip/',
    tabName: 'IP',
    // IP 列表搜索字段配置（首个为下拉框）
    searchFields: [
      { get label() { return assetText('tasks.ipType'); }, key: 'ip_type', type: 'select', options: [{ get label() { return assetText('tasks.publicPublic'); }, value: 'PUBLIC' }, { get label() { return assetText('tasks.privatePrivate'); }, value: 'PRIVATE' }] },
      { label: 'IP', key: 'ip', operator: '=' },
      { get label() { return assetText('tasks.port'); }, key: 'port_info.port_id', operator: '=' },
      { get label() { return assetText('tasks.operatingSystem'); }, key: 'os_info.name', operator: '=' }, // ARL 默认 OS 字段名
      { get label() { return assetText('tasks.domains'); }, key: 'domain', operator: '=' },
      { label: 'CDN', key: 'cdn_name', operator: '=', get placeholder() { return assetText('tasks.enterACdnProviderOrOriginServer'); } },
      { get label() { return assetText('assets.updatedAtLabel'); }, key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { title: 'IP', dataIndex: 'ip', key: 'ip', width: 160 },
      { get title() { return assetText('tasks.operatingSystem'); }, key: 'os_info', width: 150 },
      { get title() { return assetText('tasks.openPorts'); }, key: 'port_info', width: 200 },
      { get title() { return assetText('tasks.associatedDomains'); }, key: 'domain', width: 250 },
      { get title() { return assetText('tasks.cdnStatus'); }, key: 'ip_cdn_tag', width: 150 },
      { get title() { return assetText('assets.location'); }, key: 'geo_city', width: 180 },
      { get title() { return assetText('assets.asOrganization'); }, key: 'geo_asn', width: 280 },
      { get title() { return assetText('assets.updatedAtLabel'); }, dataIndex: 'update_date', key: 'update_date', width: 180 }
    ]
  },
  wih: {
    url: '/asset_wih/',
    exportUrl: '/asset_wih/export/', // 🚨 激活“导出WIH”按钮
    tabName: 'WIH',
    // WIH 列表搜索字段配置（记录类型带操作符下拉选择）
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
    // WIH 表格列定义（绑定 source 键名）
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return assetText('tasks.recordType'); }, dataIndex: 'record_type', key: 'record_type', width: 120 },
      { get title() { return assetText('tasks.content'); }, dataIndex: 'content', key: 'content', width: 250 },
      { get title() { return assetText('tasks.sourceJs'); }, dataIndex: 'source', key: 'source', width: 450 }, // 绑定 source
      { get title() { return assetText('tasks.sourceWebsite'); }, dataIndex: 'site', key: 'wih_site', width: 250 },
      { get title() { return assetText('assets.updatedAtLabel'); }, dataIndex: 'update_date', key: 'update_date', width: 180 }
    ]
  },
  cert: {
    url: '/asset_cert/',
    exportUrl: '/asset_cert/export/',
    get tabName() { return assetText('assets.sslCertificates'); },
    searchFields: [
      { get label() { return assetText('tasks.ipFields'); }, key: 'ip', operator: '=' },
      { get label() { return assetText('tasks.issuer'); }, key: 'cert.issuer_dn', operator: '=' },
      { get label() { return assetText('tasks.subject'); }, key: 'cert.subject_dn', operator: '=' },
      { label: 'SHA-1', key: 'cert.fingerprint.sha1', operator: '=' },
      { get label() { return assetText('tasks.subjectAlternativeNames'); }, key: 'cert.extensions.subjectAltName', operator: '=' },
      { get label() { return assetText('assets.updatedAtLabel'); }, key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return assetText('tasks.host'); }, key: 'host', width: 180 },
      { get title() { return assetText('tasks.sslCertificateInformation'); }, key: 'cert_detail', width: 900 },
      { get title() { return assetText('assets.updatedAtLabel'); }, key: 'update_date', width: 180 }
    ]
  },
  service: {
    url: '/asset_service/',
    get tabName() { return assetText('tasks.services'); },
    searchFields: [
      { get label() { return assetText('tasks.services'); }, key: 'service_name', operator: '=' },
      { label: 'IP', key: 'service_info.ip', operator: '=' },
      { get label() { return assetText('tasks.port'); }, key: 'service_info.port_id', operator: '=' },
      { get label() { return assetText('tasks.product'); }, key: 'service_info.product', operator: '=' },
      { get label() { return assetText('assets.updatedAtLabel'); }, key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return assetText('tasks.services'); }, dataIndex: 'service_name', key: 'service_name', width: 150, align: 'center' },
      { get title() { return assetText('tasks.ipPort'); }, key: 'ip_port', width: 300 },
      { get title() { return assetText('tasks.product'); }, key: 'product', width: 250 },
      { get title() { return assetText('assets.updatedAtLabel'); }, key: 'update_date', width: 180 }
    ]
  },
  fileleak: {
    url: '/asset_fileleak/',
    get tabName() { return assetText('tasks.fileDisclosure'); },
    searchFields: [
      { label: 'URL', key: 'url', operator: '=' },
      { get label() { return assetText('tasks.title'); }, key: 'title', operator: '=' },
      { get label() { return assetText('tasks.statusCode'); }, key: 'status_code', type: 'httpStatus' },
      { get label() { return assetText('tasks.bodyLength'); }, key: 'content_length', operator: '=' },
      { get label() { return assetText('assets.updatedAtLabel'); }, key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { title: 'URL', key: 'fileleak_url', width: 500 },
      { get title() { return assetText('tasks.title'); }, dataIndex: 'title', key: 'title', width: 250 },
      { get title() { return assetText('tasks.statusCode'); }, dataIndex: 'status_code', key: 'status_code', width: 100, align: 'center' },
      { get title() { return assetText('tasks.bodyLength'); }, dataIndex: 'content_length', key: 'content_length', width: 120, align: 'center' },
      { get title() { return assetText('assets.updatedAtLabel'); }, key: 'update_date', width: 180 }
    ]
  },
  url: {
    url: '/asset_url/',
    exportUrl: '/asset_url/export/',
    get tabName() { return assetText('tasks.urls'); },
    searchFields: [
      { label: 'URL', key: 'url', operator: '=' },
      { get label() { return assetText('tasks.title'); }, key: 'title', operator: '=' },
      { get label() { return assetText('tasks.statusCode'); }, key: 'status_code', type: 'httpStatus' },
      { get label() { return assetText('tasks.bodyLength'); }, key: 'content_length', operator: '=' },
      { get label() { return assetText('tasks.source'); }, key: 'source', operator: '=' },
      { get label() { return assetText('assets.updatedAtLabel'); }, key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { title: 'URL', key: 'url_link', width: 450 },
      { get title() { return assetText('tasks.title'); }, dataIndex: 'title', key: 'title', width: 200 },
      { get title() { return assetText('tasks.statusCode'); }, dataIndex: 'status_code', key: 'status_code', width: 100, align: 'center' },
      { get title() { return assetText('tasks.bodyLength'); }, dataIndex: 'content_length', key: 'content_length', width: 120, align: 'center' },
      { get title() { return assetText('tasks.source'); }, dataIndex: 'source', key: 'source', width: 150 },
      { get title() { return assetText('assets.updatedAtLabel'); }, key: 'update_date', width: 180 }
    ]
  },
  vuln: {
    url: '/asset_vuln/',
    get tabName() { return assetText('tasks.risks'); },
    searchFields: [
      { get label() { return assetText('tasks.vulnerabilityName'); }, key: 'vul_name', operator: '=' },
      { get label() { return assetText('tasks.category'); }, key: 'vul_category', operator: '=' },
      { get label() { return assetText('tasks.applicationName'); }, key: 'app_name', operator: '=' },
      { get label() { return assetText('tasks.target'); }, key: 'target', operator: '=' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return assetText('tasks.vulnerabilityName'); }, dataIndex: 'vul_name', key: 'vul_name', width: 250 },
      { get title() { return assetText('tasks.category'); }, dataIndex: 'vul_category', key: 'vul_category', width: 120 },
      { get title() { return assetText('tasks.applicationName'); }, dataIndex: 'app_name', key: 'app_name', width: 150 },
      { get title() { return assetText('tasks.target'); }, dataIndex: 'target', key: 'target', width: 200 },
      { get title() { return assetText('tasks.credentials'); }, key: 'verify_data', width: 350 },
      { get title() { return assetText('tasks.discoveredAt'); }, dataIndex: 'insert_time', key: 'insert_time', width: 160 }
    ]
  },
  npoc_service: {
    url: '/asset_npoc_service/',
    get tabName() { return assetText('assets.pythonPluginServicesLabel'); },
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
  cip: {
    url: '/asset_cip/',
    exportUrl: '/asset_cip/export/',
    get tabName() { return assetText('tasks.cClassNetworks'); },
    searchFields: [
      { get label() { return assetText('tasks.cClassNetworks'); }, key: 'cidr_ip', operator: '=' },
      { get label() { return assetText('assets.updatedAtLabel'); }, key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return assetText('tasks.cClassNetworks'); }, dataIndex: 'cidr_ip', key: 'cidr_ip', width: 300 },
      { get title() { return assetText('tasks.ipCount'); }, key: 'ip_count_col', width: 150, align: 'center' },
      { get title() { return assetText('tasks.domainCount'); }, key: 'domain_count_col', width: 150, align: 'center' },
      { get title() { return assetText('assets.updatedAtLabel'); }, key: 'update_date', width: 180 }
    ]
  },
  nuclei_result: {
    url: '/asset_nuclei_result/',
    tabName: 'nuclei',
    searchFields: [
      { get label() { return assetText('tasks.templateId'); }, key: 'template_id', operator: '=' },
      { get label() { return assetText('tasks.target'); }, key: 'target', operator: '=' },
      { get label() { return assetText('tasks.vulnerableUrl'); }, key: 'vuln_url', operator: '=' },
      { get label() { return assetText('tasks.vulnerabilityName'); }, key: 'vuln_name', operator: '=' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 60, align: 'center' },
      { get title() { return assetText('tasks.templateId'); }, dataIndex: 'template_id', key: 'template_id', width: 180 },
      { get title() { return assetText('tasks.target'); }, dataIndex: 'target', key: 'target', width: 200 },
      { get title() { return assetText('tasks.vulnerableUrl'); }, key: 'nuclei_vuln_url', width: 300 },
      { get title() { return assetText('tasks.vulnerabilityName'); }, dataIndex: 'vuln_name', key: 'vul_name', width: 200 },
      { get title() { return assetText('tasks.severity'); }, dataIndex: 'vuln_severity', key: 'vul_severity', width: 100, align: 'center' },
      { get title() { return assetText('tasks.savedAt'); }, dataIndex: 'insert_time', key: 'insert_time', width: 160 },
      { get title() { return assetText('tasks.verificationCommand'); }, key: 'verify_command', width: 350 }
    ]
  },
  stat_finger: {
    url: '/asset_stat_finger/',
    get tabName() { return assetText('tasks.fingerprintStatistics'); },
    searchFields: [
      {
        get label() { return assetText('tasks.fingerprints'); },
        key: 'name',
        operator: '模糊匹配',
        hasOperatorSelect: true,
        operators: ['模糊匹配', '精确匹配']
      },
      { get label() { return assetText('assets.updatedAtLabel'); }, key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { get title() { return assetText('tasks.no'); }, key: 'index', width: 80, align: 'center' },
      { get title() { return assetText('tasks.fingerprints'); }, key: 'finger_name', width: 500 },
      { get title() { return assetText('tasks.count'); }, dataIndex: 'cnt', key: 'cnt', width: 200 },
      { get title() { return assetText('assets.updatedAtLabel'); }, key: 'update_date', width: 180 }
    ]
  }
});

const tabCache = createTabStateCache({
  getStorageKey: () => scope_id.value ? `ARL_GROUP_TAB_STATE_${scope_id.value}` : null,
  tabConfig,
  defaultTab: 'site'
});

const columns = ref(tabConfig.site.cols);

const fetchData = async () => {
  const config = tabConfig[effectiveTab.value];
  if (!config) return;

  const currentReqTab = effectiveTab.value;
  loading.value = true;
  try {
    // 🚨 修复 2：获取 computed 响应式对象的最新值
    const params = { page: pagination.current, size: pagination.pageSize, scope_id: scope_id.value };

    Object.assign(params, buildAssetFilterParams(searchForm.value, config.searchFields));
    const res = await request.get(config.url, { params });
    // 竞态防御：若响应到达时 Tab 已切换，丢弃过期响应
    if (effectiveTab.value !== currentReqTab) return;

    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
      asmCounts[effectiveTab.value] = res.total || 0;
      selectedRowKeys.value = [];
      lastFetchedPage = pagination.current;
      lastFetchedSize = pagination.pageSize;
      // 更新当前 Tab 内存数据缓存并持久化轻量搜索状态
      tabCache.updateMemoryCache(effectiveTab.value, dataSource.value, pagination.total, pagination.pageSize);
      tabCache.saveCurrentTab(effectiveTab.value, searchForm.value, pagination.current);
    }
  } catch (error) {
    if (effectiveTab.value === currentReqTab) {
      message.error(assetText('assets.failedToLoadData'));
    }
  } finally {
    if (effectiveTab.value === currentReqTab) {
      loading.value = false;
    }
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

// ================= 批量删除功能 (兼容所有 Tab) =================
const handleBatchDelete = () => {
  Modal.confirm({
    title: assetText('tasks.deleteSelectedRecords'),
    icon: createVNode(ExclamationCircleOutlined),
    content: assetText('assets.permanentlyDeleteTheSelectedAssetsCountFromThis', { count: selectedRowKeys.value.length }),
    okText: assetText('tasks.confirm'),
    okType: 'danger',
    cancelText: assetText('assets.cancel'),
    onOk: async () => {
      try {
        const config = tabConfig[effectiveTab.value];
        if (!config || !config.url) return;

        // 🚨 优先读取专用配置，否则动态拼接删除 API 路径：例如 /asset_domain/ -> /asset_domain/delete/
        const deleteUrl = config.deleteUrl || `${config.url}delete/`;

        // 🚨 严格按照抓包 Payload：键名为 _id
        const res = await request.post(deleteUrl, {
          _id: selectedRowKeys.value
        });

        if (res.code === 200) {
          message.success(assetText('tasks.assetsDeletedCount', { count: selectedRowKeys.value.length }));

          // 如果删光了当前页的数据且不在第一页，自动回退一页
          if (dataSource.value.length === selectedRowKeys.value.length && pagination.current > 1) {
            pagination.current -= 1;
          }

          selectedRowKeys.value = []; // 清空选中状态
          tabCache.invalidateMemoryCache(effectiveTab.value);
          fetchData(); // 删除后自动刷新表格数据
        } else {
          message.error(assetText('tasks.deletionFailed') + res.message);
        }
      } catch (error) {
        message.error(assetText('assets.requestFailedAssetGroupWasNotDeleted'));
      }
    }
  });
};

watch(activeTab, (newVal, oldVal) => {
  const oldEffective = (oldVal === 'service' && serviceEngineType.value === 'npoc') ? 'npoc_service' : oldVal;
  const newEffective = (newVal === 'service' && serviceEngineType.value === 'npoc') ? 'npoc_service' : newVal;

  if (oldEffective && tabConfig[oldEffective] && !isScopeSwitching.value) {
    // 离开旧选项卡前，仅在非切组且有效交互时保存当前搜索表单、操作符和页码
    tabCache.saveCurrentTab(oldEffective, searchForm.value, pagination.current);
  }

  if (tabConfig[newEffective]) {
    columns.value = tabConfig[newEffective].cols;
    selectedRowKeys.value = [];

    // 恢复新选项卡的搜索表单、操作符与页码
    searchForm.value = tabCache.getTabSearchForm(newEffective);
    tabCache.applyTabOperators(newEffective);
    pagination.current = tabCache.getTabPage(newEffective) || 1;

    // 检查内存数据缓存：若已加载过且单页条数匹配则直接秒开渲染，不重复向后端发请求
    const cached = tabCache.getMemoryCache(newEffective, pagination.pageSize);
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

// 监听路由参数 chain_target 变化（支持前进/后退/深链直接打开画像抽屉）
watch(() => route.query.chain_target, (newTarget) => {
  if (newTarget) {
    const cleanTarget = String(newTarget).trim();
    if (chainDrawerTarget.value !== cleanTarget || !chainDrawerVisible.value) {
      chainDrawerTarget.value = cleanTarget;
      chainDrawerVisible.value = true;
    }
  } else {
    if (chainDrawerVisible.value) {
      chainDrawerVisible.value = false;
    }
  }
});

// 🚨 修复 3：监听 scope_id 的变化，无论是初次进入还是组件复用，只要 ID 变了就刷新数据！
watch(scope_id, (newId) => {
  if (newId) {
    fetchScopeMeta();
    isScopeSwitching.value = true;
    dataSource.value = [];
    selectedRowKeys.value = [];

    let restoredTab = tabCache.init();
    if (restoredTab === 'npoc_service') {
      serviceEngineType.value = 'npoc';
      restoredTab = 'service';
    }
    if (restoredTab && tabConfig[restoredTab] && restoredTab !== activeTab.value) {
      activeTab.value = restoredTab;
      nextTick(() => {
        isScopeSwitching.value = false;
      });
    } else {
      if (tabConfig[effectiveTab.value]) {
        columns.value = tabConfig[effectiveTab.value].cols;
        searchForm.value = tabCache.getTabSearchForm(effectiveTab.value);
        tabCache.applyTabOperators(effectiveTab.value);
        pagination.current = tabCache.getTabPage(effectiveTab.value) || 1;
      }
      const cached = tabCache.getMemoryCache(effectiveTab.value, pagination.pageSize);
      if (cached) {
        dataSource.value = cached.dataSource;
        pagination.total = cached.total;
        lastFetchedPage = pagination.current;
        lastFetchedSize = pagination.pageSize;
        isScopeSwitching.value = false;
      } else {
        fetchData().finally(() => {
          isScopeSwitching.value = false;
        });
      }
      nextTick(() => {
        isScopeSwitching.value = false;
      });
    }

    // 若路由携带 chain_target，自动唤起全链路画像抽屉
    if (route.query.chain_target) {
      openChainDrawer(route.query.chain_target);
    }
  }
}, { immediate: true }); // immediate: true 完美替代了 onMounted 的作用


// ================= 导出功能 (站点、域名、WIH 通用) =================
const handleExport = async () => {
  const config = tabConfig[effectiveTab.value];
  if (!config || !config.exportUrl) return;

  try {
    message.loading({ content: assetText('tasks.generatingExportFile'), key: 'export_data' });

    // 🚨 动态映射真实的 tabIndex
    const tabIndexMap = { site: 0, domain: 1, ip: 2, cert: 3, service: 4, fileleak: 5, url: 6, cip: 7, stat_finger: 8, wih: 9, vuln: 10, npoc_service: 11, nuclei_result: 12 };

    // 导出请求参数：设置单页上限并携带动态 tabIndex
    const params = {
      page: 1,
      size: 100000,
      scope_id: scope_id.value,
      targetName: targetName.value,
      tabIndex: tabIndexMap[effectiveTab.value]
    };

    // 🚨 补全缺失的搜索参数：确保用户过滤后导出的数据也是精准的！
    Object.assign(params, buildAssetFilterParams(searchForm.value, config.searchFields));

    const res = await request.get(config.exportUrl, { params, responseType: 'blob' });

    const isCert = effectiveTab.value === 'cert';
    const mimeType = isCert ? 'application/json;charset=utf-8' : 'text/plain;charset=utf-8';
    const ext = isCert ? 'json' : 'txt';

    const blob = new Blob([res], { type: mimeType });
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `ARL_Group_Export_${effectiveTab.value}_${new Date().getTime()}.${ext}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    message.success({ content: assetText('assets.exportCompleted'), key: 'export_data', duration: 2 });
  } catch (error) {
    message.error({ content: assetText('assets.exportFailed'), key: 'export_data', duration: 2 });
  }
};



// ================= IP专属导出占位 =================
// ================= IP专属导出 =================
const handleIPExport = async (type) => {
  let exportUrl = '';
  let typeName = '';

  // 🚨 完美映射抓包里的 3 个真实 API 路径
  if (type === 'port') {
    exportUrl = '/asset_ip/export/';
    typeName = assetText('tasks.ipPort');
  } else if (type === 'domain') {
    exportUrl = '/asset_ip/export_domain/';
    typeName = assetText('tasks.domains');
  } else if (type === 'ip') {
    exportUrl = '/asset_ip/export_ip/';
    typeName = 'IP';
  }

  if (!exportUrl) return;

  try {
    message.loading({ content: assetText('assets.preparingExportFile'), key: 'export_ip_data' });

    // 组装导出请求参数，附带当前搜索过滤条件
    const params = {
      page: 1,
      size: 10000,
      scope_id: scope_id.value,
      targetName: targetName.value,
      tabIndex: 2
    };

    Object.assign(params, buildAssetFilterParams(searchForm.value, tabConfig[effectiveTab.value].searchFields));

    // 发起 Blob 下载请求
    const res = await request.get(exportUrl, { params, responseType: 'blob' });

    // 触发浏览器的原生下载动作
    const blob = new Blob([res], { type: 'text/plain;charset=utf-8' });
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `ARL_Group_Export_${typeName}_${new Date().getTime()}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    message.success({ content: assetText('assets.typeExportCompleted', { type: typeName }), key: 'export_ip_data', duration: 2 });
  } catch (error) {
    message.error({ content: assetText('assets.exportFailedTryAgain'), key: 'export_ip_data', duration: 2 });
  }
};


// ================= 添加站点弹窗 =================
const addSiteVisible = ref(false);
const addSiteLoading = ref(false);
const addSiteFormRef = ref();
const policies = ref([]);

const addSiteForm = reactive({ site: '', policy_id: undefined });
const addSiteRules = {
  site: [{ required: true, get message() { return assetText('assets.enterAWebsite'); } }],
  policy_id: [{ required: true, get message() { return assetText('tasks.selectAPolicy'); } }]
};

const openAddSiteModal = async () => {
  addSiteForm.site = '';
  addSiteForm.policy_id = undefined;
  addSiteVisible.value = true;
  // 获取策略下拉列表
  if(policies.value.length === 0) {
    const res = await request.get('/policy/', { params: { size: 1000 } });
    if(res.code === 200) policies.value = res.items || [];
  }
};

const submitAddSite = async () => {
  await addSiteFormRef.value.validate();
  addSiteLoading.value = true;
  try {
    const res = await request.post('/asset_site/', {
      scope_id: scope_id.value,
      site: addSiteForm.site,
      policy_id: addSiteForm.policy_id
    });

    // 🚨 完美还原抓包：正常成功是 200，如果资产不在范围内是 802
    if (res.code === 200) {
      message.success(assetText('assets.websiteAdded'));
      addSiteVisible.value = false;
      tabCache.invalidateAllMemoryCaches();
      fetchData(); // 刷新表格
    } else if (res.code === 802) {
      message.error(res.message); // 弹出 "任务目标不在资产组中"
    } else {
      message.error(assetText('assets.failedToAddTask') + res.message);
    }
  } catch (e) {
    message.error(assetText('tasks.requestFailed'));
  } finally {
    addSiteLoading.value = false;
  }
};

// ================= 风险巡航 =================
const riskModalVisible = ref(false);
const riskLoading = ref(false);
const riskFormRef = ref();
const currentResultSetId = ref(''); // 保存弹药箱 ID
const currentTargetCount = ref(0); // 保存查出来的目标数量
const selectedRiskTargets = ref([]); // 保存勾选选中的具体目标列表

const riskForm = reactive({ name: '', policy_id: undefined });
const riskRules = {
  name: [{ required: true, get message() { return assetText('tasks.enterATaskName'); } }],
  policy_id: [{ required: true, get message() { return assetText('tasks.selectAPolicy'); } }]
};
// 统计目标数量
const getPocCount = (policy) => {
  return policy.policy?.poc_config?.filter(poc => poc.enable)?.length || 0;
};

// 1. 打开弹窗：智能区分勾选目标 vs 全量筛选结果集
const openRiskModal = async () => {
  try {
    message.loading({ content: assetText('assets.preparingRiskScanTargets'), key: 'risk_task' });

    // 复用之前的 policies 拉取逻辑，没有才去拉
    if (policies.value.length === 0) {
      const polRes = await request.get('/policy/', { params: { size: 1000 } });
      if (polRes.code === 200) policies.value = polRes.items || [];
    }

    // 🎯 智能分支：如果用户在表格中勾选了具体数据行，严格仅针对勾选项下发
    if (hasSelected.value && selectedRowKeys.value.length > 0) {
      const selectedSites = dataSource.value
        .filter(item => selectedRowKeys.value.includes(item._id || item.id))
        .map(item => item.site)
        .filter(Boolean);

      if (selectedSites.length === 0) {
        message.warning({ content: assetText('assets.theSelectedRecordsContainNoValidWebsiteTargets'), key: 'risk_task' });
        return;
      }

      selectedRiskTargets.value = selectedSites;
      currentResultSetId.value = '';
      currentTargetCount.value = selectedSites.length;

      message.success({ content: assetText('assets.selectedAssetsReadyForScanningCount', { count: selectedSites.length }), key: 'risk_task' });
    } else {
      // 🎯 未勾选：根据当前搜索与资产组条件打包全量结果集
      selectedRiskTargets.value = [];
      const params = { scope_id: scope_id.value };
      Object.assign(params, buildAssetFilterParams(searchForm.value, tabConfig[effectiveTab.value].searchFields));

      // 发起结果集保存请求
      const setRes = await request.get('/asset_site/save_result_set/', { params });
      if (setRes.code !== 200) throw new Error(assetText('assets.failedToCreateResultSet'));

      currentResultSetId.value = setRes.data.result_set_id;
      currentTargetCount.value = setRes.data.result_total || 0;

      message.success({ content: assetText('assets.assetsReadyForScanningCount', { count: setRes.data.result_total }), key: 'risk_task' });
    }

    // 初始化弹窗数据
    riskForm.name = '';
    riskForm.policy_id = undefined;
    riskModalVisible.value = true;
  } catch (e) {
    message.error({ content: assetText('assets.failedToPrepareScanningTask'), key: 'risk_task' });
  }
};

// 2. 选择策略时：极客级自动推导任务名称
const handleRiskPolicyChange = (val) => {
  const selected = policies.value.find(p => p._id === val);
  if (selected) {
    // 🚨 调用公共函数获取 PoC 数量
    const pocCount = getPocCount(selected);
    riskForm.name = `风险巡航任务-${selected.name} (PoC : ${pocCount})`;
  }
};

// 3. 提交任务
const submitRiskTask = async () => {
  await riskFormRef.value.validate();
  riskLoading.value = true;
  try {
    const payload = {
      name: riskForm.name,
      task_tag: 'risk_cruising',
      policy_id: riskForm.policy_id
    };

    if (selectedRiskTargets.value.length > 0) {
      payload.target = selectedRiskTargets.value.join('\n');
      payload.result_set_id = '';
    } else {
      payload.target = '';
      payload.result_set_id = currentResultSetId.value;
    }

    const res = await request.post('/task/policy/', payload);

    if (res.code === 200) {
      message.success(assetText('assets.riskScanTaskCreated'));
      riskModalVisible.value = false;
      if (selectedRiskTargets.value.length > 0) {
        selectedRowKeys.value = [];
      }
    } else {
      message.error(assetText('tasks.failedToCreateTaskLabel') + (res.message || assetText('tasks.unknownError')));
    }
  } catch (e) {
    console.warn('请求异常', e);
  } finally {
    riskLoading.value = false;
  }
};

// ================= 添加子域名弹窗 =================
const addDomainVisible = ref(false);
const addDomainLoading = ref(false);
const addDomainFormRef = ref();

const addDomainForm = reactive({ domain: '', policy_id: undefined });
const addDomainRules = {
  domain: [{ required: true, get message() { return assetText('assets.enterASubdomain'); } }],
  policy_id: [{ required: true, get message() { return assetText('tasks.selectAPolicy'); } }]
};

const openAddDomainModal = async () => {
  addDomainForm.domain = '';
  addDomainForm.policy_id = undefined;
  addDomainVisible.value = true;

  // 复用之前写好的拉取策略逻辑，避免重复请求
  if(policies.value.length === 0) {
    const res = await request.get('/policy/', { params: { size: 1000 } });
    if(res.code === 200) policies.value = res.items || [];
  }
};

const submitAddDomain = async () => {
  await addDomainFormRef.value.validate();
  addDomainLoading.value = true;
  try {
    const res = await request.post('/asset_domain/', {
      scope_id: scope_id.value,
      domain: addDomainForm.domain, // 🚨 注意这里 payload 的 key 是 domain
      policy_id: addDomainForm.policy_id
    });

    // 🚨 完美拦截原版状态码：成功是 200，越界是 701
    if (res.code === 200) {
      message.success(assetText('assets.subdomainAdded'));
      addDomainVisible.value = false;
      tabCache.invalidateAllMemoryCaches();
      fetchData(); // 自动刷新当前页面的域名列表
    } else if (res.code === 701) {
      message.error(res.message); // 原汁原味抛出：域名不在给定的资产范围中
    } else {
      message.error(assetText('assets.failedToAddTask') + res.message);
    }
  } catch (e) {
    message.error(assetText('tasks.requestFailed'));
  } finally {
    addDomainLoading.value = false;
  }
};

onDeactivated(() => {
  fingerModalVisible.value = false;
  cipDetailModalVisible.value = false;
  serviceDetailModalVisible.value = false;
  previewVisible.value = false;
  tagVisible.value = false;
  addSiteVisible.value = false;
  riskModalVisible.value = false;
  addDomainVisible.value = false;
  bindModalVisible.value = false;
  chainDrawerVisible.value = false;
  rawDrawerVisible.value = false;
});
</script>

<style scoped>
.wih-api-content { display: flex; flex-direction: column; gap: 4px; overflow-wrap: anywhere; }
.wih-api-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; }

.hero-left-section-wide { flex-wrap: wrap; row-gap: 6px; overflow: visible; }
.filter-field-label.filter-field-label-wide { width: 112px; white-space: normal; overflow: visible; text-overflow: clip; }
.asset-increment-badge :deep(.ant-badge-count) { background-color: #52c41a; font-size: 10px; }
.asset-site-count :deep(.ant-badge-count) { background-color: #1890ff; color: #fff; cursor: pointer; border-radius: 4px; padding: 0 6px; font-size: 12px; }

.operator-op-select-wide { width: 130px !important; min-width: 130px; }

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
/* 🚨 将原本的 gap: 16px 24px 改为更紧凑的 16px 12px */
.scroll-x { width: 100%; max-width: 400px; overflow-x: auto; }
.scroll-x pre { margin: 0; font-family: Consolas, monospace; font-size: 12px; color: var(--arl-text-color); opacity: 0.65; }
:deep(.ant-tabs-card-bar .ant-tabs-tab) { border-radius: 2px 2px 0 0 !important; margin-right: 4px !important; border: 1px solid var(--arl-border-color) !important; background: var(--arl-bg-light) !important; }
:deep(.ant-tabs-card-bar .ant-tabs-tab-active) { background: var(--arl-bg-white) !important;  font-weight: 500; border-bottom-color: transparent !important; }

.site-header { line-height: 1.5; word-break: break-all; }
.site-img { width: 16px; height: 16px; margin-right: 8px; vertical-align: middle; }
.add-tag { color: var(--arl-text-color); cursor: pointer; font-size: 12px; border: 1px dashed var(--arl-border-color); padding: 0 7px; border-radius: 2px; background: var(--arl-bg-light); transition: all 0.3s; }
.add-tag:hover { color: var(--arl-theme-color); border-color: var(--arl-theme-color); }
.mt5 { margin-top: 5px; }

.tag-pending-test {
  background: color-mix(in srgb, var(--arl-theme-color) 15%, transparent) !important;
  color: var(--arl-theme-color) !important;
  border-color: var(--arl-theme-color) !important;
  font-weight: 500;
  transition: all 0.3s;
}
.tag-pending-test :deep(.anticon-close) {
  color: var(--arl-theme-color) !important;
}
.tag-pending-test :deep(.anticon-close:hover) {
  opacity: 0.75;
}

.chain-card {
  border-radius: 6px;
  background: var(--arl-bg-white);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.05);
  border: 1px solid var(--arl-border-color);
}
.chain-card-header {
  display: flex;
  align-items: center;
  font-size: 15px;
  font-weight: 600;
  color: var(--arl-text-color);
}
.chain-icon {
  margin-right: 8px;
  color: var(--arl-theme-color);
  font-size: 16px;
}
.chain-empty-tip {
  color: var(--arl-text-secondary);
  text-align: center;
  padding: 24px 0;
  font-size: 13px;
}
.chain-site-item {
  padding: 16px;
  background: var(--arl-bg-light);
  border-radius: 6px;
  border: 1px solid var(--arl-border-color);
}
.chain-info-grid {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}
.chain-info-row {
  display: flex;
  align-items: baseline;
  line-height: 1.6;
}
.chain-info-label {
  width: 95px;
  color: var(--arl-text-secondary);
  flex-shrink: 0;
}
.chain-info-value {
  flex: 1;
  color: var(--arl-text-color);
  word-break: break-all;
}

/* ================= 一体化 Hero 头部卡片 ================= */
.arl-hero-card {
  background: var(--arl-bg-white);
  border-radius: 8px;
  border: 1px solid var(--arl-border-color);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
  margin-bottom: 8px;
  overflow: hidden;
  transition: border-color 0.3s, box-shadow 0.3s;
}

/* 极简单行整合栏 */
.hero-unified-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 6px 14px;
  min-height: 46px;
  gap: 12px;
  box-sizing: border-box;
}

.hero-enterprise-icon-only {
  display: inline-flex;
  align-items: center;
  color: var(--arl-theme-color);
  font-size: 13px;
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
  transition: all 0.2s;
}
.hero-enterprise-icon-only:hover {
  background: var(--arl-bg-light);
}

/* 左侧区域：返回按钮 + 标题 + 核心标签 + 垂直分割线 + 主体元数据 */
.hero-left-section {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
  flex: 1 1 auto;
}

.hero-back-btn {
  padding: 4px 8px;
  height: 28px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  border-radius: 4px;
  color: var(--arl-text-secondary);
  font-size: 13px;
  font-weight: 500;
  flex-shrink: 0;
  cursor: pointer;
  transition: all 0.2s;
}
.hero-back-btn:hover {
  background: var(--arl-bg-light);
  color: var(--arl-theme-color);
}

.hero-title-wrapper {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex-shrink: 0;
}

.hero-title-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--arl-text-color);
  letter-spacing: -0.2px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 260px;
  line-height: 24px;
}

.hero-scope-tag {
  font-size: 11px;
  font-weight: 500;
  border-radius: 3px;
  padding: 0 6px;
  line-height: 18px;
  margin-right: 0;
  flex-shrink: 0;
}

.hero-v-divider {
  width: 1px;
  height: 14px;
  background-color: var(--arl-border-color);
  margin: 0 4px;
  flex-shrink: 0;
}

.hero-meta-section {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 0 1 auto;
}

.hero-enterprise-label {
  display: inline-flex;
  align-items: center;
  font-size: 12px;
  color: var(--arl-text-color);
  min-width: 0;
  cursor: default;
}

.hero-enterprise-label .meta-icon {
  color: var(--arl-theme-color);
  margin-right: 4px;
  flex-shrink: 0;
}

.hero-enterprise-label .enterprise-text {
  max-width: 200px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  font-weight: 600;
}

.hero-unbound-label {
  display: inline-flex;
  align-items: center;
  color: var(--arl-text-secondary);
  font-size: 12px;
  background: var(--arl-bg-layout);
  padding: 1px 8px;
  border-radius: 4px;
  border: 1px dashed var(--arl-border-color);
  cursor: help;
  white-space: nowrap;
}

.hero-mini-tag {
  font-size: 11px;
  padding: 0 5px;
  border-radius: 3px;
  line-height: 18px;
  margin-right: 0;
  flex-shrink: 0;
}

/* 右侧区域：操作按钮组 */
.hero-right-section {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  flex-shrink: 0;
}

/* 下层：专属独立行 OSINT / ASM 视角切换 Tab 栏 (浅底通栏，靠左对齐，视觉焦点突出) */
.hero-view-switcher {
  background: var(--arl-bg-light);
  border-top: 1px solid var(--arl-border-color);
  padding: 5px 16px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  min-height: 38px;
}

.capsule-switcher {
  display: inline-flex;
  background: var(--arl-bg-white);
  padding: 3px;
  border-radius: 7px;
  border: 1px solid var(--arl-border-color);
  gap: 3px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.03);
}

.capsule-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 14px;
  border-radius: 5px;
  border: none;
  background: transparent;
  color: var(--arl-text-secondary);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
  line-height: 20px;
}
.capsule-btn:hover {
  color: var(--arl-text-color);
  background: rgba(0, 0, 0, 0.03);
}
.capsule-btn.active {
  background: var(--arl-theme-color);
  color: #fff;
  font-weight: 600;
  box-shadow: 0 2px 6px color-mix(in srgb, var(--arl-theme-color) 35%, transparent);
}

.capsule-icon {
  font-size: 14px;
}

.capsule-count {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: 9px;
  font-size: 11px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-weight: 600;
  background: var(--arl-bg-light);
  color: var(--arl-text-secondary);
  border: 1px solid var(--arl-border-color);
  transition: all 0.2s;
}
.capsule-btn.active .capsule-count {
  background: rgba(255, 255, 255, 0.25);
  color: #fff;
  border-color: rgba(255, 255, 255, 0.4);
}

.capsule-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #52c41a;
  margin-left: 2px;
}
.capsule-btn.active .capsule-dot {
  background: #fff;
  box-shadow: 0 0 4px #fff;
}

/* 响应式优雅降级：极端窄屏下标题与操作自适应折行 */
@media screen and (max-width: 1080px) {
  .hero-title-bar {
    flex-wrap: wrap;
    padding: 8px 12px;
    gap: 8px;
    min-height: auto;
  }
  .hero-left-section {
    width: 100%;
    justify-content: flex-start;
  }
  .hero-right-section {
    margin-left: auto;
  }
}

/* ================= 一体化资产画像 Hero 头部卡片常驻吸附 ================= */
.hero-sticky-card {
  position: sticky;
  top: 0px;
  z-index: 12;
  background: var(--arl-bg-white);
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.05);
  margin-bottom: 8px !important;
}

/* ================= ASM 网络暴露面专属控制区 ================= */
.asm-control-box {
  position: sticky;
  z-index: 11;
  background: var(--arl-bg-white);
  border-radius: 8px;
  border: 1px solid var(--arl-border-color);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  margin-bottom: 8px;
  transition: box-shadow 0.2s ease;
}

.asm-tabs-nav {
  padding: 6px 12px 0 12px;
  margin-bottom: 0 !important;
}

.asm-tabs-nav :deep(.ant-tabs-nav) {
  margin-bottom: 0 !important;
}


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


/* 普通资产列表工具栏与平铺检索区 */
.asm-toolbar-container {
  padding: 8px 12px;
  border-top: 1px solid var(--arl-border-color);
  background: var(--arl-bg-white);
}

.toolbar-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.toolbar-left {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.toolbar-title-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--arl-text-color);
}

.toolbar-meta-count {
  font-size: 11px;
  color: var(--arl-text-secondary);
  background: var(--arl-bg-light);
  padding: 1px 6px;
  border-radius: 8px;
  border: 1px solid var(--arl-border-color);
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

/* 直接平铺的紧凑栅格筛选卡片 */
.asm-filter-card {
  margin-top: 6px;
  padding: 8px 12px 6px 12px;
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
}

.filter-grid-form {
  width: 100%;
}

.filter-field-cell {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}

.filter-field-label {
  width: 72px;
  flex-shrink: 0;
  text-align: right;
  font-size: 12px;
  color: var(--arl-text-secondary);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  user-select: none;
}

.filter-field-widget {
  flex: 1;
  min-width: 0;
}

.filter-search-icon {
  color: var(--arl-text-secondary);
  opacity: 0.45;
  cursor: pointer;
  transition: all 0.2s;
  font-size: 11px;
}
.filter-search-icon:hover {
  color: var(--arl-theme-color);
  opacity: 1;
  transform: scale(1.15);
}

/* 操作符组合输入框 (如 等于/不等于) */
.filter-operator-box {
  display: flex;
  align-items: center;
  border: 1px solid var(--arl-border-color);
  border-radius: 4px;
  background: var(--arl-bg-white);
  height: 24px;
  transition: all 0.2s;
  overflow: hidden;
}
.filter-operator-box:hover,
.filter-operator-box:focus-within {
  border-color: var(--arl-theme-color);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--arl-theme-color) 20%, transparent);
}
.operator-text-input {
  flex: 1;
  min-width: 0;
  box-shadow: none !important;
  font-size: 12px;
}
.operator-divider {
  width: 1px;
  height: 14px;
  background: var(--arl-border-color);
  flex-shrink: 0;
}
.operator-op-select {
  width: 70px;
  flex-shrink: 0;
  box-shadow: none !important;
  font-size: 12px;
}
.operator-op-select :deep(.ant-select-selector) {
  height: 22px !important;
  padding: 0 4px !important;
  font-size: 12px !important;
}

/* 底部操作行与状态提示 */
.filter-footer-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 6px;
  padding-top: 4px;
  border-top: 1px dashed color-mix(in srgb, var(--arl-border-color) 80%, transparent);
}

.filter-badge-status {
  display: flex;
  align-items: center;
  gap: 5px;
  font-size: 11px;
  color: var(--arl-text-secondary);
}

.active-indicator-dot {
  width: 5px;
  height: 5px;
  border-radius: 50%;
  background: var(--arl-theme-color);
  animation: filter-dot-pulse 2s infinite;
}

@keyframes filter-dot-pulse {
  0% { opacity: 0.6; transform: scale(0.9); }
  50% { opacity: 1; transform: scale(1.2); }
  100% { opacity: 0.6; transform: scale(0.9); }
}

.filter-idle-text {
  color: var(--arl-text-secondary);
  opacity: 0.7;
}

.filter-action-btns {
  display: flex;
  align-items: center;
  gap: 6px;
}

/* ================= 极简空状态 (Standard Empty State) ================= */
.empty-default-box {
  padding: 40px 0;
}

.osint-unbound-box {
  background: var(--arl-bg-white);
  border-radius: 8px;
  border: 1px solid var(--arl-border-color);
  padding: 60px 0;
  margin-top: 16px;
}

/* ================= 悬浮浮动操作条 (Floating Action Bar) ================= */
.arl-floating-action-bar {
  position: fixed;
  bottom: 28px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 1000;
  background: var(--arl-bg-white);
  border: 1px solid var(--arl-border-color);
  box-shadow: 0 8px 28px rgba(0, 0, 0, 0.16);
  border-radius: 28px;
  padding: 8px 20px 8px 24px;
  display: flex;
  align-items: center;
  gap: 24px;
  backdrop-filter: blur(8px);
}

.floating-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--arl-text-color);
}

.floating-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.floating-slide-enter-active,
.floating-slide-leave-active {
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
}

.floating-slide-enter-from,
.floating-slide-leave-to {
  opacity: 0;
  transform: translate(-50%, 24px);
}

/* ================= 表格内悬停高频操作按钮 ================= */
.cell-copy-btn {
  opacity: 0;
  transition: opacity 0.2s, color 0.2s;
  color: var(--arl-text-secondary);
  cursor: pointer;
  padding: 0 4px;
  font-size: 13px;
}
:hover > .cell-copy-btn,
:hover > span > .cell-copy-btn,
div:hover > .cell-copy-btn {
  opacity: 0.75;
}
.cell-copy-btn:hover {
  opacity: 1 !important;
  color: var(--arl-theme-color) !important;
}

.chain-action-btn {
  opacity: 0;
  transition: opacity 0.2s;
  cursor: pointer;
  margin-left: 6px;
  border-radius: 4px;
  padding: 0 4px;
  font-size: 11px;
}
:hover > .chain-action-btn,
:hover > span > .chain-action-btn,
div:hover > .chain-action-btn {
  opacity: 0.85;
}
.chain-action-btn:hover {
  opacity: 1 !important;
}

/* ================= 辅助工具类 ================= */
.font-mono {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

/* ================= 高级筛选折叠动画 ================= */

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.2s ease-in-out;
}
.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* ================= Headers 样式 (对齐 TaskDetail，全视口无滚动条完美适配) ================= */
.scroll-x {
  background: transparent;
  border: none;
  padding: 6px 8px;
  width: 100%;
  max-width: 360px;
  max-height: 140px;
  overflow-x: auto;
  overflow-y: hidden;
  box-sizing: border-box;
}

.scroll-x pre {
  margin: 0;
  padding: 0;
  background-color: transparent;
  border: none;
  font-family: Consolas, Menlo, Courier, monospace;
  font-size: 11px;
  line-height: 1.45;
  color: #334155;
  opacity: 0.85;
  white-space: pre;
  word-wrap: normal;
}

/* 定制横向滚动条的纤细样式 */
.scroll-x::-webkit-scrollbar {
  height: 4px;
}
.scroll-x::-webkit-scrollbar-track {
  background: transparent;
}
.scroll-x::-webkit-scrollbar-thumb {
  background: rgba(0, 0, 0, 0.15);
  border-radius: 2px;
}
.scroll-x::-webkit-scrollbar-thumb:hover {
  background: rgba(0, 0, 0, 0.3);
}

.modern-clean-table :deep(.ant-table-cell:has(.scroll-x)) {
  max-width: 360px !important;
  width: 360px !important;
}


/* ================= SSL 证书两列紧凑微网格 ================= */
.cert-grid-container {
  padding: 4px 0;
  font-size: 12px;
  line-height: 1.6;
}
.cert-micro-row {
  display: flex;
  align-items: baseline;
  margin-bottom: 3px;
  gap: 4px;
}
.cert-micro-label {
  width: 80px;
  flex-shrink: 0;
  text-align: right;
  color: var(--arl-text-secondary);
  font-weight: 500;
}
.cert-micro-val {
  flex: 1;
  min-width: 0;
  color: var(--arl-text-color);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* ================= 现代化无纵线表格风格 ================= */
.modern-clean-table :deep(.ant-table) {
  background: var(--arl-bg-white);
  border-radius: 6px;
  border: 1px solid var(--arl-border-color);
}
.modern-clean-table :deep(.ant-table-thead > tr > th) {
  background: var(--arl-bg-light) !important;
  color: var(--arl-text-secondary);
  font-weight: 600;
  font-size: 12px;
  border-bottom: 1px solid var(--arl-border-color) !important;
  border-right: none !important;
}
.modern-clean-table :deep(.ant-table-tbody > tr > td) {
  border-bottom: 1px solid var(--arl-border-color) !important;
  border-right: none !important;
  transition: background 0.15s ease;
}
.modern-clean-table :deep(.ant-table-tbody > tr:hover > td) {
  background: color-mix(in srgb, var(--arl-theme-color) 4%, var(--arl-bg-white)) !important;
}


.asset-status-icon { margin-right: 3px; }
.asset-option-heading { font-weight: 600; font-size: 13px; color: var(--arl-text-color); }
.asset-clickable { cursor: pointer; }
.asset-field-hint { color: var(--arl-text-color); opacity: 0.45; margin-top: 2px; }
.asset-summary-caption { color: var(--arl-text-color); opacity: 0.65; font-size: 12px; }
.asset-selection-number { color: var(--arl-theme-color); margin: 0 4px; }
.asset-risk-form { margin-top: 20px; }
.asset-flush-bottom { margin-bottom: 0; }
.asset-muted { color: var(--arl-text-color); opacity: 0.65; }
</style>
