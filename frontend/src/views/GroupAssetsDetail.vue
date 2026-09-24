<template>
  <div style="background-color: var(--arl-bg-layout); padding: 12px 16px; min-height: calc(100vh - 64px);">
    <!-- 1. 一体化资产画像 Hero 头部卡片 (常驻吸附在页面最顶部 top: 0，极简单行整合) -->
    <div ref="heroRef" class="arl-hero-card hero-sticky-card">
      <div class="hero-unified-bar">
        <!-- 左侧：返回 + 标题 + 分组标签 + 类型 + 测绘状态 (去重) -->
        <div class="hero-left-section">
          <a-button type="text" class="hero-back-btn" @click="handleBack" title="返回资产组列表">
            <template #icon><arrow-left-outlined style="font-size: 15px;" /></template>
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
                    <div>关联主体: {{ scopeEnterpriseName || targetName }}</div>
                    <div v-if="taskTarget && taskTarget.startsWith('TYC_')">主体编号: {{ taskTarget }}</div>
                    <div v-if="taskTypeLabel">任务类型: {{ taskTypeLabel }}</div>
                    <div v-if="taskStatusLabel">测绘状态: {{ taskStatusLabel }}</div>
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
              <a-tag v-if="taskStatusLabel" :color="taskStatusColor" class="hero-mini-tag">
                {{ taskStatusLabel }}
              </a-tag>
              <a-badge v-if="scopeHasIncrement" count="有增量" :number-style="{ backgroundColor: '#52c41a', fontSize: '10px' }" />
            </template>
            <template v-else>
              <a-tooltip title="尚未关联企业主体，点击可立即拉取工商与数字资产" placement="bottom">
                <span class="hero-unbound-label" @click="openBindModal" style="cursor: pointer;">
                  <link-outlined style="margin-right: 4px;" />
                  未关联主体
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
              title="切换至企业生态资产视角"
            >
              <bank-outlined class="capsule-icon" />
              <span>企业生态资产 (OSINT)</span>
              <span class="capsule-count" v-if="osintTotalCount > 0">{{ osintTotalCount }}</span>
              <span v-if="scopeHasIncrement" class="capsule-dot"></span>
            </button>
            <button
              class="capsule-btn"
              :class="{ active: currentView === 'asm' }"
              @click="currentView = 'asm'"
              title="切换至网络暴露面视角"
            >
              <global-outlined class="capsule-icon" />
              <span>网络暴露面 (ASM)</span>
              <span class="capsule-count" v-if="asmTotalCount > 0">{{ asmTotalCount }}</span>
            </button>
          </div>
        </div>
      </div>
    </div>

      <!-- 2. 网络暴露面 (ASM) 专属控制与筛选区 (吸附于 Hero 头部正下方) -->
      <div v-show="currentView === 'asm'" ref="asmControlRef" class="asm-control-box" :style="{ top: heroHeight + 'px' }">
        <!-- 维度 Tabs 导航 (带数量徽标与平滑滚动) -->
        <a-tabs v-model:activeKey="activeTab" type="card" size="small" class="arl-detail-tabs asm-tabs-nav">
          <a-tab-pane key="site_chain">
            <template #tab>
              <span class="chain-tab-pill">
                <compass-outlined /> 全链路画像
              </span>
            </template>
          </a-tab-pane>
          <a-tab-pane v-for="t in asmTabList" :key="t.key">
            <template #tab>
              <span class="asm-tab-item">
                <span>{{ t.label }}</span>
                <span class="asm-tab-badge" :class="{ 'has-data': asmCounts[t.key] > 0 }">
                  {{ asmCounts[t.key] || 0 }}
                </span>
              </span>
            </template>
          </a-tab-pane>
        </a-tabs>

        <!-- 全链路画像专属检索与快捷 Chips -->
        <div v-if="activeTab === 'site_chain'" class="chain-search-container">
          <div v-if="scopeDomainList && scopeDomainList.length > 0" class="chain-quick-chips">
            <span class="chips-label"><rocket-outlined /> 快捷透视本组资产：</span>
            <div class="chips-list">
              <a-tag
                v-for="d in scopeDomainList.slice(0, 8)"
                :key="d"
                color="blue"
                class="quick-chip-tag"
                @click="() => { chainSearchDomain = d; handleChainSearch(d); }"
              >
                {{ d }}
              </a-tag>
            </div>
          </div>

          <div class="chain-search-row">
            <span class="chain-search-label">目标域名/IP：</span>
            <a-auto-complete
              v-model:value="chainSearchDomain"
              :options="domainSuggestions"
              style="width: 360px;"
              placeholder="请输入或选择子域名/IP（回车直接搜索）"
              allow-clear
              size="small"
              @select="(val) => handleChainSearch(val)"
              @search="handleDomainSearchInput"
              @pressEnter="() => handleChainSearch()"
            />
            <a-button type="primary" size="small" :loading="chainLoading" @click="() => handleChainSearch()">
              <template #icon><search-outlined /></template>
              查 询
            </a-button>
            <a-button size="small" @click="resetChainSearch">清 除</a-button>
            <a-button v-if="chainData" size="small" @click="downloadChainJson">
              <template #icon><download-outlined /></template>
              导出画像 (JSON)
            </a-button>
            <span v-if="chainData" class="chain-result-stat">
              已命中关联 IP: <b class="font-mono">{{ chainData.resolved_ips?.length || 0 }}</b> 个
            </span>
          </div>
        </div>

        <!-- 普通资产列表检索与操作工具栏 (上下分层：业务操作行 + 直接平铺紧凑检索卡片) -->
        <div v-else class="asm-toolbar-container">
          <div class="toolbar-row">
            <div class="toolbar-left">
              <span class="toolbar-title-text">{{ tabConfig[activeTab]?.tabName || '资产' }}维度</span>
              <span class="toolbar-meta-count">
                共 <b class="font-mono">{{ asmCounts[activeTab] || 0 }}</b> 条记录
              </span>
            </div>

            <div class="toolbar-right">
              <a-button v-if="activeTab === 'site'" type="primary" size="small" @click="openAddSiteModal">
                <template #icon><plus-outlined /></template>
                添加站点
              </a-button>
              <a-button v-if="activeTab === 'domain'" type="primary" size="small" @click="openAddDomainModal">
                <template #icon><plus-outlined /></template>
                添加子域名
              </a-button>
              <a-button v-if="activeTab !== 'ip' && tabConfig[activeTab]?.exportUrl" size="small" @click="handleExport">
                <template #icon><download-outlined /></template>
                导出{{ tabConfig[activeTab].tabName }}
              </a-button>
              <template v-if="activeTab === 'ip'">
                <a-button size="small" @click="handleIPExport('port')">导出端口</a-button>
                <a-button size="small" @click="handleIPExport('domain')">导出域名</a-button>
                <a-button type="primary" ghost size="small" @click="handleIPExport('ip')">
                  <template #icon><download-outlined /></template>
                  导出 IP
                </a-button>
              </template>
              <a-button v-if="activeTab === 'site'" type="dashed" danger size="small" @click="openRiskModal">
                <template #icon><bug-outlined /></template>
                风险巡航
              </a-button>

              <!-- 高级筛选折叠展开切换按钮 -->
              <a-button
                v-if="tabConfig[activeTab]?.searchFields?.length"
                size="small"
                :type="isAdvancedFilterOpen ? 'primary' : 'default'"
                :ghost="isAdvancedFilterOpen"
                @click="isAdvancedFilterOpen = !isAdvancedFilterOpen"
              >
                <template #icon><filter-outlined /></template>
                {{ isAdvancedFilterOpen ? '收起筛选' : '高级筛选' }}
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
            <div v-show="isAdvancedFilterOpen" v-if="tabConfig[activeTab]?.searchFields?.length" class="asm-filter-card">
            <a-form :model="searchForm" class="filter-grid-form">
              <a-row :gutter="[12, 6]">
                <a-col
                  v-for="field in tabConfig[activeTab].searchFields.filter(f => !f.hidden)"
                  :key="field.key"
                  :xs="24" :sm="12" :md="8" :lg="6"
                >
                  <div class="filter-field-cell">
                    <span class="filter-field-label" :title="field.label">{{ field.label }}</span>
                    <div class="filter-field-widget">
                      <!-- 下拉选择 -->
                      <a-select
                        v-if="field.type === 'select'"
                        v-model:value="searchForm[field.key]"
                        :placeholder="`请选择${field.label}`"
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
                        :placeholder="['开始日期', '结束日期']"
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
                          :placeholder="field.placeholder || `请输入${field.label}`"
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
                          class="operator-op-select"
                          @change="onSearch"
                        >
                          <a-select-option v-for="op in field.operators" :key="op" :value="op">{{ op }}</a-select-option>
                        </a-select>
                      </div>

                      <!-- 普通文本输入框 -->
                      <a-input
                        v-else
                        v-model:value="searchForm[field.key]"
                        :placeholder="field.placeholder || `请输入${field.label}`"
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
                    <span>已应用 <b class="font-mono" style="color: var(--arl-theme-color);">{{ activeFilterCount }}</b> 项筛选条件</span>
                  </template>
                  <span v-else class="filter-idle-text">支持回车或点击放大镜图标快速检索</span>
                </div>
                <div class="filter-action-btns">
                  <a-button size="small" @click="resetSearch">
                    <template #icon><redo-outlined /></template>
                    重 置
                  </a-button>
                  <a-button type="primary" size="small" @click="onSearch">
                    <template #icon><search-outlined /></template>
                    查 询
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
      v-if="activeTab !== 'site_chain'"
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
                <a-tooltip title="复制站点">
                  <a-button type="text" size="small" class="cell-copy-btn" @click.stop="handleCopyText(record.site || record.url)">
                    <copy-outlined style="font-size: 11px; opacity: 0.65;" />
                  </a-button>
                </a-tooltip>
              </div>
              <a-button type="link" size="small" class="chain-action-btn" style="padding: 0; height: auto; font-size: 12px; flex-shrink: 0;" @click="openChainDrawer(record.hostname || record.site)">
                <compass-outlined />画像
              </a-button>
            </div>
            <div class="mt5" style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">
              <!-- 1. 置顶渲染「待测试」标签 -->
              <a-tag
                v-if="getTags(record).includes('待测试')"
                class="tag-pending-test"
              >
                待测试
                <a-popconfirm
                  title="确定移除「待测试」标签吗？"
                  ok-text="确认"
                  cancel-text="取消"
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
                入口
                <a-popconfirm
                  title="确定移除「入口」标签吗？"
                  ok-text="确认"
                  cancel-text="取消"
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
                    :title="`确定移除「${t}」标签吗？`"
                    ok-text="确认"
                    cancel-text="取消"
                    @confirm="handleDeleteTag(record, t)"
                  >
                    <span class="ant-tag-close-icon" @click.stop>
                      <close-outlined />
                    </span>
                  </a-popconfirm>
                </a-tag>
              </template>
              <span class="add-tag" @click="openTagModal(record)" style="cursor: pointer;">添加标签</span>
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
                <div style="color: var(--arl-text-color); opacity: 0.45; margin-top: 2px;">...等 {{ record.ips.length }} 个</div>
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
              <a-tooltip title="复制 IP">
                <a-button type="text" size="small" class="cell-copy-btn" @click.stop="handleCopyText(record.ip)">
                  <copy-outlined style="font-size: 11px; opacity: 0.65;" />
                </a-button>
              </a-tooltip>
            </div>
            <a-button type="link" size="small" class="chain-action-btn" style="padding: 0; height: auto; font-size: 12px; flex-shrink: 0;" @click="openChainDrawer(record.ip)">
              <compass-outlined />画像
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
                <a-tooltip title="复制域名">
                  <a-button type="text" size="small" class="cell-copy-btn" @click.stop="handleCopyText(dom)">
                    <copy-outlined style="font-size: 11px; opacity: 0.65;" />
                  </a-button>
                </a-tooltip>
              </div>
            </div>
            <div v-else style="display: flex; align-items: center; gap: 6px;">
              <span style="font-weight: 500;">{{ record.domain }}</span>
              <a-tooltip title="复制域名">
                <a-button type="text" size="small" class="cell-copy-btn" @click.stop="handleCopyText(record.domain)">
                  <copy-outlined style="font-size: 11px; opacity: 0.65;" />
                </a-button>
              </a-tooltip>
            </div>
            <a-button v-if="!Array.isArray(record.domain)" type="link" size="small" class="chain-action-btn" style="padding: 0; height: auto; font-size: 12px; flex-shrink: 0;" @click="openChainDrawer(record.domain)">
              <compass-outlined />画像
            </a-button>
          </div>
        </template>

        <template v-else-if="column.key === 'ip_cdn_tag'">
          <a-tag v-if="record.is_cdn || record.cdn_name" color="blue">
            {{ record.cdn_name || 'CDN节点' }}
          </a-tag>
          <a-tag v-else color="green">
            独立源站
          </a-tag>
        </template>

        <template v-else-if="column.key === 'source'">
          <div style="word-break: break-all; color: var(--arl-text-color); line-height: 1.6;">
            <a :href="record.source" target="_blank" style="color: var(--arl-text-color); text-decoration: none;">
              {{ record.source || '-' }}
            </a>
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
              <a-badge :count="`+${record.sites.length - 1} 站点`" :number-style="{ backgroundColor: '#1890ff', color: '#fff', cursor: 'pointer', borderRadius: '4px', padding: '0 6px', fontSize: '12px' }" />
            </a-popover>
          </div>
        </template>

      
        <template v-else-if="column.key === 'cert_detail'">
          <div v-if="record.cert" class="cert-grid-container">
            <a-row :gutter="[16, 4]">
              <!-- 左列：基础信息 -->
              <a-col :xs="24" :sm="14">
                <div class="cert-micro-row">
                  <span class="cert-micro-label">主题名称：</span>
                  <span class="cert-micro-val font-mono" :title="record.cert.subject_dn">{{ record.cert.subject_dn || '-' }}</span>
                </div>
                <div class="cert-micro-row">
                  <span class="cert-micro-label">签发者：</span>
                  <span class="cert-micro-val" :title="record.cert.issuer_dn">{{ record.cert.issuer_dn || '-' }}</span>
                </div>
                <div class="cert-micro-row">
                  <span class="cert-micro-label">备用名称：</span>
                  <span class="cert-micro-val font-mono" :title="record.cert.extensions?.subjectAltName">{{ record.cert.extensions?.subjectAltName || '-' }}</span>
                </div>
                <div class="cert-micro-row">
                  <span class="cert-micro-label">有效时间：</span>
                  <span class="cert-micro-val">{{ record.cert.validity?.start || '-' }} 至 {{ record.cert.validity?.end || '-' }}</span>
                </div>
              </a-col>

              <!-- 右列：指纹与序列号 -->
              <a-col :xs="24" :sm="10">
                <div class="cert-micro-row">
                  <span class="cert-micro-label">序列号：</span>
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
                查看全部 (共 {{ record.service_info.length }} 项) &gt;&gt;
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
          <a-empty description="暂无资产数据" />
        </div>
      </template>
    </a-table>

    <!-- ================= 站点信息查询（全链路透视画像） ================= -->
    <template v-if="activeTab === 'site_chain'">
      <!-- 1. 初始未搜索：空白引导态 -->
      <div v-if="!chainSearched" style="background: var(--arl-bg-white); border-radius: 8px; padding: 70px 24px; text-align: center; border: 1px dashed var(--arl-border-color); margin-top: 8px;">
        <a-empty description="请输入或选择子域名展开全链路资产画像">
          <template #image>
            <compass-outlined style="font-size: 64px; color: var(--arl-theme-color); opacity: 0.75;" />
          </template>
          <div style="color: var(--arl-text-secondary); margin-top: 12px; font-size: 13px;">
            自上而下顺次透视：站点元数据与截图 ➔ 子域名解析 ➔ 关联IP与归属 ➔ 关联C段网段 ➔ SSL证书 ➔ 开放服务与NPOC ➔ 敏感文件、URL与WIH ➔ 风险漏洞与Nuclei
          </div>
        </a-empty>
      </div>

      <!-- 2. 查询中或已有数据时的展示区 -->
      <a-spin v-else :spinning="chainLoading" tip="正在全息聚合各资产板块数据...">
        <div v-if="chainData" style="display: flex; flex-direction: column; gap: 16px; margin-top: 8px;">

          <!-- 板块 1：站点基础信息与截图 (chainData.site) -->
          <a-card :bordered="false" class="chain-card" :bodyStyle="{ padding: '16px 20px' }">
            <template #title>
              <div class="chain-card-header">
                <global-outlined class="chain-icon" />
                <span class="chain-title">站点基础信息</span>
                <a-badge :count="chainData.site?.length || 0" :number-style="{ backgroundColor: '#1890ff' }" style="margin-left: 8px;" />
              </div>
            </template>

            <div v-if="!chainData.site || chainData.site.length === 0" class="chain-empty-tip">
              暂无关联站点记录
            </div>
            <div v-else style="display: flex; flex-direction: column; gap: 16px;">
              <div v-for="siteItem in chainData.site" :key="siteItem._id || siteItem.site" class="chain-site-item">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 24px; flex-wrap: wrap;">
                  <!-- 站点详情信息 -->
                  <div style="flex: 1; min-width: 320px;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                      <img v-if="siteItem.favicon && siteItem.favicon.data" :src="`data:image/png;base64,${siteItem.favicon.data}`" class="site-img" />
                      <a :href="siteItem.site" target="_blank" style="font-size: 16px; font-weight: 600; color: var(--arl-theme-color); word-break: break-all;">
                        {{ siteItem.site }}
                      </a>
                      <a-tag :color="siteItem.status === 200 ? 'success' : (siteItem.status >= 400 ? 'error' : 'default')">
                        HTTP {{ siteItem.status || '-' }}
                      </a-tag>
                    </div>

                    <div class="chain-info-grid">
                      <div class="chain-info-row">
                        <span class="chain-info-label">网页标题：</span>
                        <span class="chain-info-value" style="font-weight: 500;">{{ siteItem.title || '-' }}</span>
                      </div>
                      <div class="chain-info-row">
                        <span class="chain-info-label">Web Server：</span>
                        <span class="chain-info-value">{{ siteItem.http_server || '-' }}</span>
                      </div>
                      <div class="chain-info-row">
                        <span class="chain-info-label">关联 IP：</span>
                        <span class="chain-info-value" style="font-family: monospace;">{{ siteItem.ip || '-' }}</span>
                      </div>
                      <div class="chain-info-row">
                        <span class="chain-info-label">更新时间：</span>
                        <span class="chain-info-value">{{ siteItem.update_date || siteItem.save_date || '-' }}</span>
                      </div>
                      <div class="chain-info-row">
                        <span class="chain-info-label">指纹识别：</span>
                        <div class="chain-info-value" style="display: flex; flex-wrap: wrap; gap: 4px;">
                          <template v-if="siteItem.finger && siteItem.finger.length > 0">
                            <a-tag v-for="f in siteItem.finger" :key="f.name" color="blue">{{ f.name }}</a-tag>
                          </template>
                          <span v-else>-</span>
                        </div>
                      </div>
                      <div class="chain-info-row">
                        <span class="chain-info-label">业务标签：</span>
                        <div class="chain-info-value" style="display: flex; align-items: center; flex-wrap: wrap; gap: 4px;">
                          <!-- 1. 置顶渲染「待测试」标签 -->
                          <a-tag
                            v-if="getTags(siteItem).includes('待测试')"
                            class="tag-pending-test"
                          >
                            待测试
                            <a-popconfirm
                              title="确定移除「待测试」标签吗？"
                              ok-text="确认"
                              cancel-text="取消"
                              @confirm="handleDeleteTag(siteItem, '待测试')"
                            >
                              <span class="ant-tag-close-icon" @click.stop>
                                <close-outlined />
                              </span>
                            </a-popconfirm>
                          </a-tag>

                          <!-- 2. 渲染「入口」标签 -->
                          <a-tag
                            v-if="getTags(siteItem).includes('入口')"
                            style="background: var(--arl-bg-light); color: var(--arl-text-color); border-color: var(--arl-border-color);"
                          >
                            入口
                            <a-popconfirm
                              title="确定移除「入口」标签吗？"
                              ok-text="确认"
                              cancel-text="取消"
                              @confirm="handleDeleteTag(siteItem, '入口')"
                            >
                              <span class="ant-tag-close-icon" @click.stop>
                                <close-outlined />
                              </span>
                            </a-popconfirm>
                          </a-tag>

                          <!-- 3. 渲染其余业务自定义标签 -->
                          <template v-for="t in getTags(siteItem)" :key="t">
                            <a-tag
                              v-if="t !== '待测试' && t !== '入口'"
                              style="background: var(--arl-bg-light); color: var(--arl-text-color); border-color: var(--arl-border-color);"
                            >
                              {{ t }}
                              <a-popconfirm
                                :title="`确定移除「${t}」标签吗？`"
                                ok-text="确认"
                                cancel-text="取消"
                                @confirm="handleDeleteTag(siteItem, t)"
                              >
                                <span class="ant-tag-close-icon" @click.stop>
                                  <close-outlined />
                                </span>
                              </a-popconfirm>
                            </a-tag>
                          </template>
                          <span class="add-tag" @click="openTagModal(siteItem)" style="cursor: pointer;">添加标签</span>
                        </div>
                      </div>
                      <div v-if="siteItem.headers" class="chain-info-row">
                        <span class="chain-info-label">响应标头：</span>
                        <a-popover placement="bottomLeft" trigger="click">
                          <template #content>
                            <pre style="max-height: 250px; max-width: 500px; overflow: auto; font-size: 11px; margin: 0;">{{ siteItem.headers }}</pre>
                          </template>
                          <a-button type="link" size="small" style="padding: 0; height: auto;">查看 Headers</a-button>
                        </a-popover>
                      </div>
                    </div>
                  </div>

                  <!-- 站点网页截图预览 -->
                  <div style="width: 240px; text-align: center; flex-shrink: 0;">
                    <div v-if="siteItem.screenshot" style="border: 1px solid var(--arl-border-color); border-radius: 4px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.06); cursor: pointer;" @click="handlePreview(`/api${siteItem.screenshot}`)">
                      <img :src="`/api${siteItem.screenshot}`" style="width: 100%; height: 140px; object-fit: cover; object-position: top; display: block;" />
                      <div style="background: var(--arl-bg-light); font-size: 11px; padding: 4px; color: var(--arl-text-secondary);">点击放大截图</div>
                    </div>
                    <div v-else style="width: 100%; height: 140px; border: 1px dashed var(--arl-border-color); border-radius: 4px; display: flex; align-items: center; justify-content: center; color: var(--arl-text-secondary); font-size: 12px; background: var(--arl-bg-light);">
                      暂无网页截图
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </a-card>

          <!-- 板块 2：子域名与解析记录 (chainData.domain_records) -->
          <a-card :bordered="false" class="chain-card" :bodyStyle="{ padding: '16px 20px' }">
            <template #title>
              <div class="chain-card-header">
                <link-outlined class="chain-icon" />
                <span class="chain-title">子域名与解析记录</span>
                <a-badge :count="chainData.domain_records?.length || 0" :number-style="{ backgroundColor: '#52c41a' }" style="margin-left: 8px;" />
              </div>
            </template>
            <a-table
              :dataSource="chainData.domain_records || []"
              :columns="chainDomainCols"
              :pagination="false"
              size="middle"
              :rowKey="(record) => record._id || record.id || record.domain"
              :locale="{ emptyText: '暂无子域名解析记录' }"
            >
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                <template v-else-if="column.key === 'domain'"><span style="font-weight: 500;">{{ record.domain }}</span></template>
                <template v-else-if="column.key === 'record'">
                  <div v-if="Array.isArray(record.record)"><div v-for="(r, i) in record.record" :key="i">{{ r }}</div></div>
                  <span v-else>{{ record.record || '-' }}</span>
                </template>
                <template v-else-if="column.key === 'ips'">
                  <div v-if="Array.isArray(record.ips)"><div v-for="(ip, i) in record.ips" :key="i" style="font-family: monospace;">{{ ip }}</div></div>
                  <span v-else>{{ record.ips || '-' }}</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 板块 3：IP 与网络归属 (chainData.ip) -->
          <a-card :bordered="false" class="chain-card" :bodyStyle="{ padding: '16px 20px' }">
            <template #title>
              <div class="chain-card-header">
                <cloud-server-outlined class="chain-icon" />
                <span class="chain-title">IP 与网络归属</span>
                <a-badge :count="chainData.ip?.length || 0" :number-style="{ backgroundColor: '#722ed1' }" style="margin-left: 8px;" />
              </div>
            </template>
            <a-table
              :dataSource="chainData.ip || []"
              :columns="chainIpCols"
              :pagination="false"
              :scroll="{ x: 'max-content' }"
              size="middle"
              :rowKey="(record) => record._id || record.id || record.ip"
              :locale="{ emptyText: '暂无关联 IP 资产记录' }"
            >
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                <template v-else-if="column.key === 'ip'"><span style="font-weight: 500; font-family: monospace;">{{ record.ip }}</span></template>
                <template v-else-if="column.key === 'port_info'">
                  <span v-if="record.port_info && record.port_info.length">{{ record.port_info.map(p => p.port_id).join(', ') }}</span>
                  <span v-else>-</span>
                </template>
                <template v-else-if="column.key === 'os_info'"><span>{{ record.os_info?.name || '-' }}</span></template>
                <template v-else-if="column.key === 'domain'">
                  <div v-if="Array.isArray(record.domain) && record.domain.length">
                    <div v-for="(dom, i) in record.domain" :key="i" style="font-family: monospace;">{{ dom }}</div>
                  </div>
                  <span v-else-if="record.domain && !Array.isArray(record.domain)" style="font-family: monospace;">{{ record.domain }}</span>
                  <span v-else>-</span>
                </template>
                <template v-else-if="column.key === 'geo_city'"><span>{{ formatGeo(record.geo_city) }}</span></template>
                <template v-else-if="column.key === 'geo_asn'"><span>{{ record.geo_asn?.organization || '-' }}</span></template>
              </template>
            </a-table>
          </a-card>

          <!-- 板块 4：关联 C 段网段 (chainData.cip) -->
          <a-card :bordered="false" class="chain-card" :bodyStyle="{ padding: '16px 20px' }">
            <template #title>
              <div class="chain-card-header">
                <cluster-outlined class="chain-icon" />
                <span class="chain-title">关联 C 段网段</span>
                <a-badge :count="chainData.cip?.length || 0" :number-style="{ backgroundColor: '#eb2f96' }" style="margin-left: 8px;" />
              </div>
            </template>
            <a-table
              :dataSource="chainData.cip || []"
              :columns="chainCipCols"
              :pagination="false"
              size="middle"
              :rowKey="(record) => record._id || record.id || record.cidr_ip"
              :locale="{ emptyText: '暂无关联 C 段资产记录' }"
            >
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                <template v-else-if="column.key === 'cidr_ip'">
                  <a style="cursor: pointer; font-family: monospace; font-size: 14px; font-weight: 600; color: var(--arl-primary-color);" @click="openCidrDetail(record)">
                    {{ record.cidr_ip || '-' }}
                  </a>
                </template>
                <template v-else-if="column.key === 'ip_count'">
                  <a-tag color="purple" style="font-family: monospace;">
                    {{ record.ip_count ?? (record.ip_list ? record.ip_list.length : 0) }} 个 IP
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'domain_count'">
                  <a-tag color="blue" style="font-family: monospace;">
                    {{ record.domain_count ?? (record.domain_list ? record.domain_list.length : 0) }} 个域名
                  </a-tag>
                </template>
                <template v-else-if="column.key === 'update_date'">
                  <span style="font-size: 13px; color: var(--arl-text-secondary);">
                    {{ record.update_date || record.save_date || '-' }}
                  </span>
                </template>
                <template v-else-if="column.key === 'action'">
                  <a-button type="link" size="small" @click="openCidrDetail(record)">
                    查看详情
                  </a-button>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 板块 5：SSL 证书 (chainData.cert) -->
          <a-card :bordered="false" class="chain-card" :bodyStyle="{ padding: '16px 20px' }">
            <template #title>
              <div class="chain-card-header">
                <safety-certificate-outlined class="chain-icon" />
                <span class="chain-title">SSL 证书</span>
                <a-badge :count="chainData.cert?.length || 0" :number-style="{ backgroundColor: '#13c2c2' }" style="margin-left: 8px;" />
              </div>
            </template>
            <a-table
              :dataSource="chainData.cert || []"
              :columns="chainCertCols"
              :pagination="false"
              size="middle"
              :rowKey="(record) => record._id || record.id"
              :locale="{ emptyText: '暂无关联 SSL 证书' }"
            >
              <template #bodyCell="{ column, record, index }">
                <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                <template v-else-if="column.key === 'host'"><span>{{ record.ip || record.host }}{{ record.port ? ':' + record.port : '' }}</span></template>
                <template v-else-if="column.key === 'cert_detail'">
                  <div v-if="record.cert" style="font-size: 12px; line-height: 1.6;">
                    <div><b>主题名称：</b>{{ record.cert.subject_dn || '-' }}</div>
                    <div><b>签发者：</b>{{ record.cert.issuer_dn || '-' }}</div>
                    <div v-if="record.cert.extensions?.subjectAltName"><b>备用名 (SAN)：</b>{{ record.cert.extensions.subjectAltName }}</div>
                    <div><b>有效期限：</b>{{ record.cert.validity?.start || '-' }} 至 {{ record.cert.validity?.end || '-' }}</div>
                  </div>
                  <span v-else>-</span>
                </template>
              </template>
            </a-table>
          </a-card>

          <!-- 板块 6：开放服务与 NPOC (chainData.service & chainData.npoc_service) -->
          <a-card :bordered="false" class="chain-card" :bodyStyle="{ padding: '16px 20px' }">
            <template #title>
              <div class="chain-card-header">
                <api-outlined class="chain-icon" />
                <span class="chain-title">开放服务与 NPOC</span>
                <a-badge :count="(chainData.service?.length || 0) + (chainData.npoc_service?.length || 0)" :number-style="{ backgroundColor: '#fa8c16' }" style="margin-left: 8px;" />
              </div>
            </template>
            <div style="display: flex; flex-direction: column; gap: 16px;">
              <div>
                <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px; color: var(--arl-text-color);">
                  🔌 资产系统服务 ({{ chainData.service?.length || 0 }})
                </div>
                <a-table
                  :dataSource="chainData.service || []"
                  :columns="chainServiceCols"
                  :pagination="false"
                  size="middle"
                  :rowKey="(record) => record._id || record.id"
                  :locale="{ emptyText: '暂无开放服务记录' }"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                    <template v-else-if="column.key === 'service_name'"><a-tag color="cyan">{{ record.service_name }}</a-tag></template>
                    <template v-else-if="column.key === 'ip_port'">
                      <div v-if="record.service_info && record.service_info.length">
                        <div v-for="(info, i) in record.service_info" :key="i" style="font-family: monospace;">
                          {{ info.ip }}:{{ info.port_id }}
                        </div>
                      </div>
                      <span v-else>-</span>
                    </template>
                    <template v-else-if="column.key === 'product'">
                      <div v-if="record.service_info && record.service_info.length">
                        <div v-for="(info, i) in record.service_info" :key="i">
                          {{ info.product || '-' }} {{ info.version ? `(${info.version})` : '' }}
                        </div>
                      </div>
                      <span v-else>-</span>
                    </template>
                  </template>
                </a-table>
              </div>

              <div>
                <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px; color: var(--arl-text-color);">
                  🐍 Python NPOC 探测服务 ({{ chainData.npoc_service?.length || 0 }})
                </div>
                <a-table
                  :dataSource="chainData.npoc_service || []"
                  :columns="chainNpocCols"
                  :pagination="false"
                  size="small"
                  :rowKey="(record) => record._id || record.id"
                  :locale="{ emptyText: '暂无 NPOC 探测服务记录' }"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                    <template v-else-if="column.key === 'scheme'"><a-tag color="purple">{{ record.scheme || '-' }}</a-tag></template>
                    <template v-else-if="column.key === 'target'">
                      <span style="font-family: monospace;">{{ record.target || '-' }}</span>
                    </template>
                  </template>
                </a-table>
              </div>
            </div>
          </a-card>

          <!-- 板块 7：文件泄露、敏感 URL 与 WIH (chainData.fileleak & chainData.url & chainData.wih) -->
          <a-card :bordered="false" class="chain-card" :bodyStyle="{ padding: '16px 20px' }">
            <template #title>
              <div class="chain-card-header">
                <file-search-outlined class="chain-icon" />
                <span class="chain-title">文件泄露、敏感 URL 与 WIH</span>
                <a-badge :count="(chainData.fileleak?.length || 0) + (chainData.url?.length || 0) + (chainData.wih?.length || 0)" :number-style="{ backgroundColor: '#faad14' }" style="margin-left: 8px;" />
              </div>
            </template>

            <div style="display: flex; flex-direction: column; gap: 16px;">
              <!-- 7.1 文件泄露 -->
              <div>
                <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px; color: var(--arl-text-color);">
                  📄 疑似敏感文件泄露 ({{ chainData.fileleak?.length || 0 }})
                </div>
                <a-table
                  :dataSource="chainData.fileleak || []"
                  :columns="chainFileleakCols"
                  :pagination="false"
                  size="small"
                  :rowKey="(record) => record._id || record.id || record.url"
                  :locale="{ emptyText: '暂无文件泄露记录' }"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                    <template v-else-if="column.key === 'url'">
                      <a :href="record.url" target="_blank" style="font-family: monospace; word-break: break-all;">
                        {{ record.url }}
                      </a>
                    </template>
                  </template>
                </a-table>
              </div>

              <!-- 7.2 关联 URL -->
              <div>
                <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px; color: var(--arl-text-color);">
                  🔗 关联探测 URL ({{ chainData.url?.length || 0 }})
                </div>
                <a-table
                  :dataSource="chainData.url || []"
                  :columns="chainUrlCols"
                  :pagination="false"
                  size="small"
                  :rowKey="(record) => record._id || record.id || record.url"
                  :locale="{ emptyText: '暂无关联 URL 记录' }"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                    <template v-else-if="column.key === 'url'">
                      <a :href="record.url" target="_blank" style="font-family: monospace; word-break: break-all;">
                        {{ record.url }}
                      </a>
                    </template>
                  </template>
                </a-table>
              </div>

              <!-- 7.3 WIH 敏感信息 -->
              <div>
                <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px; color: var(--arl-text-color);">
                  🔍 WEB Info Hunter 泄露信息 ({{ chainData.wih?.length || 0 }})
                </div>
                <a-table
                  :dataSource="chainData.wih || []"
                  :columns="chainWihCols"
                  :pagination="false"
                  size="small"
                  :rowKey="(record) => record._id || record.id"
                  :locale="{ emptyText: '暂无 WIH 泄露记录' }"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                    <template v-else-if="column.key === 'content'">
                      <span style="font-family: monospace; word-break: break-all; color: #fa8c16; font-weight: 500;">
                        {{ record.content }}
                      </span>
                    </template>
                    <template v-else-if="column.key === 'site' || column.key === 'source'">
                      <a v-if="record[column.key]" :href="record[column.key]" target="_blank" style="font-family: monospace; word-break: break-all;">
                        {{ record[column.key] }}
                      </a>
                      <span v-else>-</span>
                    </template>
                  </template>
                </a-table>
              </div>
            </div>
          </a-card>

          <!-- 板块 8：风险漏洞与 Nuclei (chainData.vuln & chainData.nuclei_result) -->
          <a-card :bordered="false" class="chain-card" :bodyStyle="{ padding: '16px 20px' }">
            <template #title>
              <div class="chain-card-header">
                <bug-outlined class="chain-icon" />
                <span class="chain-title">风险漏洞与 Nuclei 结果</span>
                <a-badge :count="(chainData.vuln?.length || 0) + (chainData.nuclei_result?.length || 0)" :number-style="{ backgroundColor: '#f5222d' }" style="margin-left: 8px;" />
              </div>
            </template>

            <div style="display: flex; flex-direction: column; gap: 16px;">
              <!-- 7.1 常规漏洞 / PoC 结果 -->
              <div>
                <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px; color: var(--arl-text-color);">
                  🛡️ 应用与服务漏洞 ({{ chainData.vuln?.length || 0 }})
                </div>
                <a-table
                  :dataSource="chainData.vuln || []"
                  :columns="chainVulnCols"
                  :pagination="false"
                  size="small"
                  :rowKey="(record) => record._id || record.id"
                  :locale="{ emptyText: '暂无漏洞风险记录' }"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                    <template v-else-if="column.key === 'target'">
                      <a v-if="record.target && (record.target.startsWith('http://') || record.target.startsWith('https://'))" :href="record.target" target="_blank" style="word-break: break-all;">{{ record.target }}</a>
                      <span v-else style="font-family: monospace; word-break: break-all;">{{ record.target || '-' }}</span>
                    </template>
                    <template v-else-if="column.key === 'verify_data'">
                      <div style="max-height: 80px; overflow-y: auto; color: #f5222d; font-family: monospace; font-size: 12px; word-break: break-all;">
                        {{ record.verify_data || record.proof || '-' }}
                      </div>
                    </template>
                  </template>
                </a-table>
              </div>

              <!-- 7.2 Nuclei 命中结果 -->
              <div>
                <div style="font-weight: 600; font-size: 13px; margin-bottom: 8px; color: var(--arl-text-color);">
                  🎯 Nuclei 扫描发现 ({{ chainData.nuclei_result?.length || 0 }})
                </div>
                <a-table
                  :dataSource="chainData.nuclei_result || []"
                  :columns="chainNucleiCols"
                  :pagination="false"
                  size="small"
                  :rowKey="(record) => record._id || record.id"
                  :locale="{ emptyText: '暂无 Nuclei 扫描发现' }"
                >
                  <template #bodyCell="{ column, record, index }">
                    <template v-if="column.key === 'index'">{{ index + 1 }}</template>
                    <template v-else-if="column.key === 'vuln_severity'">
                      <a-tag :color="getSeverityColor(record.vuln_severity || record.vul_severity)">
                        {{ (record.vuln_severity || record.vul_severity || 'info').toUpperCase() }}
                      </a-tag>
                    </template>
                    <template v-else-if="column.key === 'vuln_url'">
                      <a v-if="(record.vuln_url || record.target) && ((record.vuln_url || record.target).startsWith('http://') || (record.vuln_url || record.target).startsWith('https://'))" :href="record.vuln_url || record.target" target="_blank" style="word-break: break-all;">
                        {{ record.vuln_url || record.target }}
                      </a>
                      <span v-else style="font-family: monospace; word-break: break-all;">{{ record.vuln_url || record.target || '-' }}</span>
                    </template>
                    <template v-else-if="column.key === 'verify_command'">
                      <div style="max-height: 80px; overflow-y: auto; background: var(--arl-bg-light); padding: 4px 8px; border-radius: 4px; font-family: monospace; font-size: 11px; word-break: break-all;">
                        {{ record.verify_command || record.curl_command || '-' }}
                      </div>
                    </template>
                  </template>
                </a-table>
              </div>
            </div>
          </a-card>

        </div>
      </a-spin>
    </template>


    <!-- 指纹统计关联站点弹窗 -->
    <a-modal v-model:open="fingerModalVisible" :title="`指纹关联站点：${currentFingerName}`" :footer="null" width="800px">
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

    <!-- 综合C段详情弹窗 (提取为组件) -->
    <CidrDetailModal v-model:open="cipDetailModalVisible" :record="currentCidrRecord" />

    <!-- 系统服务端点详情弹窗 (提取为组件) -->
    <ServiceDetailModal v-model:open="serviceDetailModalVisible" :record="currentServiceRecord" />

    <!-- 图片预览组件 -->
    <a-modal v-model:open="previewVisible" :footer="null" width="85vw" centered @cancel="previewVisible = false" :bodyStyle="{ padding: '16px' }">
      <img :src="previewImage" style="width: 100%; max-height: 85vh; object-fit: contain; display: block;" />
    </a-modal>

    <!-- 添加标签弹窗 -->
    <a-modal v-model:open="tagVisible" title="添加标签" @ok="submitTag" :confirmLoading="tagSubmitLoading" width="400px" okText="确 定" cancelText="取 消">
      <div style="margin-top: 20px;">
        <a-input v-model:value="newTagValue" placeholder="请输入标签名称" />
      </div>
    </a-modal>


    <div v-if="tabConfig[activeTab] && activeTab !== 'site_chain'" style="display: flex; justify-content: space-between; align-items: center; padding: 0 16px; margin-top: 10px;">
      <div style="color: var(--arl-text-color); opacity: 0.65; font-size: 12px;">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
      <a-pagination size="small" :pageSizeOptions="$pageSizeOptions" v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" @showSizeChange="handleTableChange" />
    </div>

    <!-- 悬浮浮动批处理条 (Floating Action Bar) -->
    <transition name="floating-slide">
      <div v-if="hasSelected" class="arl-floating-action-bar">
        <div class="floating-info">
          <check-circle-filled style="color: var(--arl-theme-color); font-size: 16px;" />
          <span>已选中 <b style="color: var(--arl-theme-color); margin: 0 4px;">{{ selectedRowKeys.length }}</b> 项资产</span>
        </div>
        <div class="floating-actions">
          <a-button danger size="middle" @click="handleBatchDelete">
            <template #icon><delete-outlined /></template>
            批量删除
          </a-button>
          <a-button v-if="activeTab === 'site'" type="primary" size="middle" @click="openRiskModal">
            <template #icon><bug-outlined /></template>
            下发风险巡航 ({{ selectedRowKeys.length }})
          </a-button>
          <a-button size="middle" @click="selectedRowKeys = []">取消选择</a-button>
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
      :hide-header="true"
      :sticky-top-offset="heroHeight"
      @taskLoaded="handleOsintLoaded"
      @synced="handleOsintSynced"
      @openBind="openBindModal"
      @refreshed="(newTid) => { if (newTid) { boundIcpTaskId = newTid; fetchBoundTaskDetail(newTid); } }"
    />
    <div v-else class="osint-unbound-box">
      <a-empty description="尚未关联企业主体" />
    </div>
  </div>

    <a-modal v-model:open="addSiteVisible" title="添加站点" @ok="submitAddSite" :confirmLoading="addSiteLoading" width="520px" okText="确 定" cancelText="取 消" destroyOnClose>
      <a-form ref="addSiteFormRef" :model="addSiteForm" :rules="addSiteRules" :label-col="{ span: 4 }" :wrapper-col="{ span: 19 }" style="margin-top: 20px;">
        <a-form-item label="站点" name="site">
          <a-textarea v-model:value="addSiteForm.site" :rows="4" placeholder="会对站点进行探测，获取标题、headers, finger等信息。示例：https://www.freebuf.com/" />
        </a-form-item>
        <a-form-item label="策略" name="policy_id">
          <a-select v-model:value="addSiteForm.policy_id" placeholder="请选择策略">
            <a-select-option v-for="p in policies" :key="p._id" :value="p._id">{{ p.name }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <a-modal v-model:open="riskModalVisible" title="添加风险巡航任务" @ok="submitRiskTask" :confirmLoading="riskLoading" width="520px" okText="确 定" cancelText="取 消" destroyOnClose>
      <a-form ref="riskFormRef" :model="riskForm" :rules="riskRules" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">

        <a-form-item label="策略名称" name="policy_id">
          <a-select v-model:value="riskForm.policy_id" placeholder="请选择策略" @change="handleRiskPolicyChange">
            <a-select-option v-for="p in policies" :key="p._id" :value="p._id">
              {{ p.name }} (PoC : {{ getPocCount(p) }})
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="任务名称" name="name">
          <a-input v-model:value="riskForm.name" placeholder="请输入任务名称" allowClear />
        </a-form-item>

        <a-form-item label="目标" style="margin-bottom: 0;">
          <span style="color: var(--arl-text-color); opacity: 0.65;">选择目标数 {{ currentTargetCount }}</span>
        </a-form-item>

      </a-form>
    </a-modal>

    <a-modal v-model:open="addDomainVisible" title="添加子域名" @ok="submitAddDomain" :confirmLoading="addDomainLoading" width="520px" okText="确 定" cancelText="取 消" destroyOnClose>
      <a-form ref="addDomainFormRef" :model="addDomainForm" :rules="addDomainRules" :label-col="{ span: 4 }" :wrapper-col="{ span: 19 }" style="margin-top: 20px;">
        <a-form-item label="子域名" name="domain">
          <a-textarea v-model:value="addDomainForm.domain" :rows="4" placeholder="会对子域名自动下发侦察任务，获取子域名关联的ip、站点等信息。示例：live.freebuf.com" />
        </a-form-item>
        <a-form-item label="策略" name="policy_id">
          <a-select v-model:value="addDomainForm.policy_id" placeholder="请选择策略">
            <a-select-option v-for="p in policies" :key="p._id" :value="p._id">{{ p.name }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 绑定企业主体弹窗 -->
    <a-modal
      v-model:open="bindModalVisible"
      :title="boundIcpTaskId ? '重新绑定企业主体' : '绑定企业主体'"
      @ok="handleBindSubmit"
      :confirmLoading="bindLoading"
      width="540px"
      wrapClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
      destroyOnClose
    >
      <a-form :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">
        <a-form-item label="绑定方式">
          <a-radio-group v-model:value="bindMode">
            <a-radio value="existing">选择已有测绘任务</a-radio>
            <a-radio value="new">发起新企业测绘</a-radio>
          </a-radio-group>
        </a-form-item>

        <template v-if="bindMode === 'existing'">
          <a-form-item label="企业测绘" required>
            <a-select
              v-model:value="selectedBindTaskId"
              placeholder="请选择已有的企业测绘任务"
              show-search
              option-filter-prop="label"
              :options="completedIcpTasks.map(t => ({
                value: t._id,
                label: t.task_type === 'tyc'
                  ? `${t.name || t.target} [TYC: ${t.gid || (t.target ? t.target.replace(/^TYC_/, '') : '')}]`
                  : `${t.target || t.name} (ICP)`
              }))"
            />
          </a-form-item>
        </template>

        <template v-else>
          <a-form-item label="测绘类型">
            <a-radio-group v-model:value="newEnterpriseEngine">
              <a-radio value="tyc">天眼查工商测绘</a-radio>
              <a-radio value="icp">工信部ICP备案</a-radio>
            </a-radio-group>
          </a-form-item>

          <a-form-item
            v-if="newEnterpriseEngine === 'tyc'"
            label="公司ID (TYC_id)"
            required
            tooltip="可在天眼查详情页URL中获取，例如 https://www.tianyancha.com/company/25174642 中的 25174642"
          >
            <a-input v-model:value="newEnterpriseTarget" placeholder="请输入天眼查公司 ID（纯数字/字母，例如：25174642）" />
          </a-form-item>

          <a-form-item
            v-else
            label="企业目标"
            required
          >
            <a-input v-model:value="newEnterpriseTarget" placeholder="输入企业全称或主域名（如：腾讯科技 或 qq.com）" />
          </a-form-item>
        </template>
      </a-form>
    </a-modal>

    <!-- 全链路画像滑出抽屉 (快速透视) -->
    <ChainDrawer
      v-model:open="chainDrawerVisible"
      :target="chainDrawerTarget"
      :scope-id="scope_id"
      @openDedicated="handleOpenDedicatedChain"
    />

    <!-- 原始数据 JSON 抽屉 -->
    <RawDataDrawer
      v-model:open="rawDrawerVisible"
      :data="currentRawRecord"
    />


  </div>
</template>

<script setup>
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
import { formatGeo } from '../utils/formatGeo';
import { message, Modal } from 'ant-design-vue';
import * as echarts from 'echarts';
import dayjs from 'dayjs';
import CidrDetailModal from '../components/CidrDetailModal.vue';
import ServiceDetailModal from '../components/ServiceDetailModal.vue';
import EnterpriseOsintPanel from '../components/EnterpriseOsintPanel.vue';
import ChainDrawer from '../components/ChainDrawer.vue';
import RawDataDrawer from '../components/RawDataDrawer.vue';
import { copyText } from '../utils/clipboard';
import {
  SearchOutlined,
  ExclamationCircleOutlined,
  InfoCircleOutlined,
  GlobalOutlined,
  CloudServerOutlined,
  SafetyCertificateOutlined,
  ApiOutlined,
  FileSearchOutlined,
  BugOutlined,
  CompassOutlined,
  ClusterOutlined,
  LinkOutlined,
  DownloadOutlined,
  CloseOutlined,
  BankOutlined,
  ArrowLeftOutlined,
  FilterOutlined,
  DownOutlined,
  UpOutlined,
  CopyOutlined,
  CheckCircleFilled,
  DeleteOutlined,
  RocketOutlined,
  PlusOutlined,
  RedoOutlined
} from '@ant-design/icons-vue';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import { createTabStateCache } from '../utils/useTabStateCache';

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
    return scopeEnterpriseName.value || t || '企业资产';
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
const scopeHasIncrement = ref(false);
const scopeGroupName = ref('');
const scopeType = ref('');
const scopeDomainList = ref([]);
const boundTaskRecord = ref({});
const taskTarget = ref('');
const taskTypeLabel = ref('');
const taskStatusLabel = ref('');
const taskStatusColor = ref('default');
const osintTotalCount = ref(0);

const asmTabList = [
  { key: 'site', label: '站点' },
  { key: 'domain', label: '子域名' },
  { key: 'ip', label: 'IP' },
  { key: 'cert', label: 'SSL证书' },
  { key: 'service', label: '服务' },
  { key: 'fileleak', label: '文件泄露' },
  { key: 'url', label: 'URL信息' },
  { key: 'cip', label: 'C段' },
  { key: 'stat_finger', label: '指纹统计' },
  { key: 'wih', label: 'WIH' },
  { key: 'vuln', label: '风险' },
  { key: 'npoc_service', label: '服务(python)' },
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
  if (ok) message.success(`已复制: ${text}`);
};

const chainDrawerVisible = ref(false);
const chainDrawerTarget = ref('');

const openChainDrawer = (target) => {
  if (!target) return;
  chainDrawerTarget.value = String(target).trim();
  chainDrawerVisible.value = true;
};

const handleOpenDedicatedChain = (target) => {
  chainDrawerVisible.value = false;
  activeTab.value = 'site_chain';
  chainSearchDomain.value = target;
  handleChainSearch(target);
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
  taskTypeLabel.value = payload.taskTypeLabel || '';
  taskStatusLabel.value = payload.taskStatusLabel || '';
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
      taskTypeLabel.value = task.task_type === 'tyc' ? '天眼查' : 'ICP备案';
      const mapStatus = { waiting: '等待中', running: '运行中', done: '已完成', stop: '已停止', error: '执行失败' };
      taskStatusLabel.value = mapStatus[task.status] || task.status;
      const mapColor = { waiting: 'warning', running: 'processing', done: 'success', stop: 'default', error: 'error' };
      taskStatusColor.value = mapColor[task.status] || 'default';
      const stats = task.statistic || {};
      osintTotalCount.value = (
        (stats.web_cnt || 0) +
        (stats.app_cnt || 0) +
        (stats.mapp_cnt || 0) +
        (stats.wechat_cnt || 0) +
        (stats.weibo_cnt || 0) +
        (stats.kapp_cnt || 0) +
        (stats.trademark_cnt || 0) +
        (stats.invest_cnt || 0)
      );
    }
  } catch (e) {}
};

const fetchAsmCounts = async () => {
  if (!scope_id.value) return;
  const keys = Object.keys(tabConfig).filter(k => k !== 'site_chain');
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
const newEnterpriseEngine = ref('tyc');

const fetchScopeMeta = async () => {
  if (!scope_id.value) return;
  try {
    const res = await request.get('/asset_scope/', { params: { _id: scope_id.value } });
    if (res && res.code === 200 && res.items && res.items.length > 0) {
      const item = res.items[0];
      boundIcpTaskId.value = item.synced_icp_task_id || '';
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
      message.success(boundIcpTaskId.value ? '重新绑定企业主体成功' : '绑定企业主体成功');
      bindModalVisible.value = false;
      fetchScopeMeta();
      currentView.value = 'osint';
    } else {
      message.error(res.message || '绑定失败');
    }
  } catch (err) {
    message.error('网络请求失败');
  } finally {
    bindLoading.value = false;
  }
};

const executeBindNew = async () => {
  const targetVal = newEnterpriseTarget.value.trim();
  if (!targetVal) {
    message.warning(newEnterpriseEngine.value === 'tyc' ? '请输入天眼查公司 ID (TYC_id)' : '请输入企业全称或主域名');
    return;
  }
  if (newEnterpriseEngine.value === 'tyc' && !/^[a-zA-Z0-9]+$/.test(targetVal)) {
    message.warning('天眼查公司 ID 格式不正确，请输入纯数字/字母 ID（例如：25174642）');
    return;
  }
  bindLoading.value = true;
  try {
    let createRes;
    if (newEnterpriseEngine.value === 'tyc') {
      createRes = await request.post('/icp/tyc_task', {
        name: `${targetName.value}企业测绘`,
        gid: targetVal,
        depth: 1,
        invest_ratio: 50,
        enable_icp: true,
        query_type: ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo']
      });
    } else {
      createRes = await request.post('/icp/task', {
        name: `${targetName.value}ICP查询`,
        target: targetVal,
        query_type: ['web', 'app', 'mapp']
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
      message.success('已成功发起企业测绘并绑定');
      bindModalVisible.value = false;
      fetchScopeMeta();
      currentView.value = 'osint';
    } else {
      message.error(createRes.message || '创建测绘任务失败');
    }
  } catch (err) {
    message.error('网络请求失败');
  } finally {
    bindLoading.value = false;
  }
};

const handleBindSubmit = async () => {
  if (bindMode.value === 'existing') {
    if (!selectedBindTaskId.value) {
      message.warning('请选择要绑定的测绘任务');
      return;
    }
    // 若已绑定主体且用户选择了不同的测绘任务，弹出二次确认
    if (boundIcpTaskId.value && selectedBindTaskId.value !== boundIcpTaskId.value) {
      Modal.confirm({
        title: '确认更换企业主体？',
        content: '检测到您正在更换绑定的企业主体，此操作将同步切换本资产组关联的企业工商与全域数字资产画像。',
        okText: '确认更换',
        cancelText: '取消',
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
        title: '确认发起并更换企业主体？',
        content: '当前资产组已关联企业主体，发起新测绘后将自动切换为新主体画像，是否继续？',
        okText: '确认发起',
        cancelText: '取消',
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
const loading = ref(false);
const dataSource = ref([]);

// ================= 全链路子域名画像检索逻辑 =================
const chainSearchDomain = ref('');
const chainLoading = ref(false);
const chainSearched = ref(false);
const chainData = ref(null);
const domainSuggestions = ref([]);

const chainDomainCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: '子域名', dataIndex: 'domain', key: 'domain', width: 220 },
  { title: '解析类型', dataIndex: 'type', key: 'type', width: 100, align: 'center' },
  { title: '记录值', key: 'record', width: 250 },
  { title: '关联IP', key: 'ips', width: 250 },
  { title: '来源', dataIndex: 'source', key: 'source', width: 150 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
];

const chainIpCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: 'IP', dataIndex: 'ip', key: 'ip', width: 160 },
  { title: '操作系统', key: 'os_info', width: 140 },
  { title: '开放端口', key: 'port_info', width: 220 },
  { title: '关联域名', key: 'domain', width: 250 },
  { title: 'Geo 归属', key: 'geo_city', width: 180 },
  { title: 'AS 归属', key: 'geo_asn', width: 260 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
];

const chainCipCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: 'C段网段', dataIndex: 'cidr_ip', key: 'cidr_ip', width: 220 },
  { title: '关联 IP 数量', key: 'ip_count', width: 140, align: 'center' },
  { title: '关联域名数量', key: 'domain_count', width: 140, align: 'center' },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 },
  { title: '操作', key: 'action', width: 120, align: 'center' }
];

const chainCertCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: 'HOST', key: 'host', width: 180 },
  { title: '证书详情', key: 'cert_detail' },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
];

const chainServiceCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: '服务', dataIndex: 'service_name', key: 'service_name', width: 120, align: 'center' },
  { title: 'IP:端口', key: 'ip_port', width: 220 },
  { title: 'Product / 版本', key: 'product', width: 300 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
];

const chainFileleakCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: 'URL', key: 'url' },
  { title: '标题', dataIndex: 'title', key: 'title', width: 200 },
  { title: '状态码', key: 'status_code', width: 90, align: 'center' },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
];

const chainUrlCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: 'URL', key: 'url' },
  { title: '标题', dataIndex: 'title', key: 'title', width: 200 },
  { title: '状态码', key: 'status_code', width: 90, align: 'center' },
  { title: '来源', dataIndex: 'source', key: 'source', width: 140 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
];

const chainVulnCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: '漏洞名称', dataIndex: 'vul_name', key: 'vul_name', width: 220 },
  { title: '类别', dataIndex: 'vul_category', key: 'vul_category', width: 120 },
  { title: '目标', key: 'target', width: 220 },
  { title: '凭证', key: 'verify_data' },
  { title: '发现时间', dataIndex: 'insert_time', key: 'insert_time', width: 160 }
];

const chainNucleiCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: '危害等级', key: 'vuln_severity', width: 100, align: 'center' },
  { title: '模版ID', dataIndex: 'template_id', key: 'template_id', width: 180 },
  { title: '漏洞名称', dataIndex: 'vuln_name', key: 'vul_name', width: 200 },
  { title: '漏洞 URL', key: 'vuln_url', width: 260 },
  { title: '验证命令', key: 'verify_command' },
  { title: '保存时间', dataIndex: 'insert_time', key: 'insert_time', width: 160 }
];

const chainNpocCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: '协议', dataIndex: 'scheme', key: 'scheme', width: 120, align: 'center' },
  { title: '主机', dataIndex: 'host', key: 'host', width: 180 },
  { title: '端口', dataIndex: 'port', key: 'port', width: 90, align: 'center' },
  { title: '目标', dataIndex: 'target', key: 'target', width: 220 },
  { title: '保存时间', dataIndex: 'insert_time', key: 'insert_time', width: 180 }
];

const chainWihCols = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: '类型', dataIndex: 'record_type', key: 'record_type', width: 120 },
  { title: '敏感内容', dataIndex: 'content', key: 'content' },
  { title: '来源 JS', dataIndex: 'source', key: 'source', width: 350 },
  { title: '来源站点', dataIndex: 'site', key: 'site', width: 220 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
];

const syncChainQuery = (target) => {
  const currentQuery = { ...route.query };
  if (target) {
    currentQuery.chain_target = target;
  } else {
    delete currentQuery.chain_target;
  }
  router.replace({ query: currentQuery });
};

const downloadChainJson = () => {
  if (!chainData.value) {
    message.warning('当前无画像数据可导出');
    return;
  }
  try {
    const jsonStr = JSON.stringify(chainData.value, null, 2);
    const blob = new Blob([jsonStr], { type: 'application/json;charset=utf-8' });
    const blobUrl = URL.createObjectURL(blob);
    const downloadAnchor = document.createElement('a');
    const targetLabel = chainSearchDomain.value || 'target';
    const filename = `arl_chain_${targetLabel}_${dayjs().format('YYYYMMDD_HHmmss')}.json`;
    downloadAnchor.href = blobUrl;
    downloadAnchor.download = filename;
    document.body.appendChild(downloadAnchor);
    downloadAnchor.click();
    downloadAnchor.remove();
    URL.revokeObjectURL(blobUrl);
    message.success(`已成功导出画像数据: ${filename}`);
  } catch (err) {
    message.error('导出画像数据失败');
  }
};

const jumpToChain = (target) => {
  if (!target) return;
  let dom = String(target).trim();
  if (dom.includes('://')) {
    try {
      dom = new URL(dom).hostname;
    } catch (e) {
      dom = dom.split('://')[1].split('/')[0];
    }
  } else if (dom.includes('/')) {
    dom = dom.split('/')[0];
  }
  if (dom.includes(':') && !dom.startsWith('[')) {
    dom = dom.split(':')[0];
  }
  dom = dom.replace(/^\[|\]$/g, '').trim().toLowerCase();
  chainSearchDomain.value = dom;
  activeTab.value = 'site_chain';
  nextTick(() => {
    handleChainSearch();
  });
};

const getSeverityColor = (sev) => {
  const s = String(sev || '').toLowerCase();
  if (s === 'critical') return '#f5222d';
  if (s === 'high') return '#fa541c';
  if (s === 'medium') return '#fa8c16';
  if (s === 'low') return '#faad14';
  return '#1890ff';
};

const fetchDomainSuggestions = async (keyword = '') => {
  if (!scope_id.value) return;
  try {
    const params = {
      scope_id: scope_id.value,
      page: 1,
      size: 30
    };
    if (keyword && typeof keyword === 'string' && keyword.trim()) {
      params.domain = keyword.trim();
    }
    const res = await request.get('/asset_domain/', { params });
    if (res && res.items) {
      const domains = Array.from(new Set(res.items.map(item => item.domain).filter(Boolean)));
      domainSuggestions.value = domains.map(d => ({ value: d, label: d }));
    }
  } catch (err) {
    console.error('获取子域名建议失败', err);
  }
};

let domainSuggestTimer = null;
const handleDomainSearchInput = (value) => {
  if (domainSuggestTimer) clearTimeout(domainSuggestTimer);
  domainSuggestTimer = setTimeout(() => {
    fetchDomainSuggestions(value);
  }, 300);
};

onUnmounted(() => {
  if (domainSuggestTimer) {
    clearTimeout(domainSuggestTimer);
    domainSuggestTimer = null;
  }
});

const handleChainSearch = async (val) => {
  if (typeof val === 'string' && val.trim()) {
    chainSearchDomain.value = val.trim();
  }
  const queryDomain = (chainSearchDomain.value || '').trim();
  if (!queryDomain) {
    message.warning('请输入或选择子域名/IP进行查询');
    return;
  }
  if (!scope_id.value) {
    message.warning('资产组 ID 不存在');
    return;
  }

  syncChainQuery(queryDomain);

  chainLoading.value = true;
  chainSearched.value = true;
  try {
    const res = await request.get('/asset_site/subdomain_chain/', {
      params: {
        scope_id: scope_id.value,
        domain: queryDomain
      }
    });

    if (res.code === 200) {
      chainData.value = res.data || {};
      const d = chainData.value;
      const totalFound = (
        (d.site?.length || 0) +
        (d.domain_records?.length || 0) +
        (d.ip?.length || 0) +
        (d.cip?.length || 0) +
        (d.cert?.length || 0) +
        (d.service?.length || 0) +
        (d.npoc_service?.length || 0) +
        (d.fileleak?.length || 0) +
        (d.url?.length || 0) +
        (d.wih?.length || 0) +
        (d.vuln?.length || 0) +
        (d.nuclei_result?.length || 0)
      );
      if (totalFound === 0) {
        message.info('未检索到该子域名/IP的关联资产记录');
      }
    } else {
      message.error(res.message || '查询失败');
    }
  } catch (err) {
    message.error('请求全链路资产画像异常');
  } finally {
    chainLoading.value = false;
  }
};

const resetChainSearch = () => {
  chainSearchDomain.value = '';
  chainSearched.value = false;
  chainData.value = null;
  syncChainQuery('');
  fetchDomainSuggestions();
};

const previewVisible = ref(false);
const previewImage = ref('');
const handlePreview = (url) => { previewImage.value = url; previewVisible.value = true; };
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
  // 1. 同步全链路画像 chainData.site 中的对应项
  if (chainData.value && Array.isArray(chainData.value.site)) {
    const chainSite = chainData.value.site.find(s => (s._id || s.id) === targetId);
    if (chainSite) {
      chainSite.tag = [...newTags];
    }
  }
  // 2. 同步常规列表 dataSource 中的对应项
  if (Array.isArray(dataSource.value)) {
    const tableSite = dataSource.value.find(s => (s._id || s.id) === targetId);
    if (tableSite) {
      tableSite.tag = [...newTags];
    }
  }
};

const submitTag = async () => {
  if (!newTagValue.value.trim()) {
    message.warning('标签内容不能为空');
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
      message.success('添加标签成功');
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
      if (activeTab.value !== 'site_chain') {
        fetchData(); // 重新加载数据
      }
    } else {
      message.error(res.message || '添加标签失败');
    }
  } catch (error) {
    message.error('请求异常');
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
      message.success(`已移除标签「${tag}」`);
      const currentTags = Array.isArray(record.tag) ? record.tag : (record.tag ? [record.tag] : []);
      record.tag = currentTags.filter(t => t !== tag);
      syncTagState(targetId, record.tag);
      tabCache.invalidateMemoryCache(activeTab.value);
      tabCache.invalidateMemoryCache('site');
    } else {
      message.error(res.message || '删除标签失败');
    }
  } catch (error) {
    message.error('请求异常');
  }
};

// 指纹统计弹窗状态与方法
const fingerModalVisible = ref(false);
const currentFingerName = ref('');
const fingerModalData = ref([]);
const fingerModalLoading = ref(false);

const fingerModalColumns = [
  { title: '序号', key: 'index', width: 60, align: 'center' },
  { title: '站点 URL', key: 'site', width: 300 },
  { title: '标题', key: 'title', dataIndex: 'title', width: 200 },
  { title: '状态码', key: 'status', dataIndex: 'status', width: 100 }
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
    message.error('获取关联站点失败');
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
    tabName: '站点',
    searchFields: [
      { label: '站点', key: 'site', operator: '=' },
      { label: '标题', key: 'title', operator: '=' },
      { label: 'Web Server', key: 'http_server', operator: '=' },
      { label: '状态码', key: 'status', operator: '=' },
      // 🚨 补充丢失的 4 个字段
      { label: '标头', key: 'headers', operator: '=' },
      { label: '指纹', key: 'finger', operator: '=' },
      { label: 'favicon hash', key: 'favicon.hash', operator: '=' },
      { label: '标签', key: 'tag', operator: '=' },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 50, align: 'center' },
      { title: '站点', dataIndex: 'site', key: 'site', width: 260 },
      { title: '状态码', dataIndex: 'status', key: 'status', width: 75, align: 'center' },
      { title: '标题', dataIndex: 'title', key: 'title', width: 200 },
      { title: 'headers', key: 'headers', width: 360 },
      { title: '指纹', key: 'finger', width: 200 },
      { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 160, align: 'center' },
      { title: '截图', key: 'screenshot', width: 250 }
    ]
  },
  domain: {
    url: '/asset_domain/',
    exportUrl: '/asset_domain/export/',
    tabName: '域名',
    // 🚨 修复：严格对齐截图中的 6 个搜索框顺序和文案
    searchFields: [
      { label: '域名', key: 'domain', operator: '=' },
      { label: '记录值', key: 'record', operator: '=' },
      { label: '类型', key: 'type', operator: '=' }, // 调整到第 3 位
      { label: 'IP', key: 'ips', operator: '=' },    // 调整到第 4 位
      { label: '来源', key: 'source', operator: '=' },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      // ... cols 保持不变，上一轮猜得完全正确 ...
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '域名', dataIndex: 'domain', key: 'domain', width: 220 },
      { title: '解析类型', dataIndex: 'type', key: 'type', width: 100 },
      { title: '记录值', key: 'record', width: 280 },
      { title: '关联IP', key: 'ips', width: 280 },
      { title: '来源', dataIndex: 'source', key: 'source', width: 150 },
      { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
    ]
  },
  ip: {
    url: '/asset_ip/',
    tabName: 'IP',
    // 🚨 修复：完美对齐截图的 7 个搜索字段，首个为下拉框
    searchFields: [
      { label: 'IP类别', key: 'ip_type', type: 'select', options: [{label: 'PUBLIC', value: 'PUBLIC'}, {label: 'PRIVATE', value: 'PRIVATE'}] },
      { label: 'IP', key: 'ip', operator: '=' },
      { label: '端口', key: 'port_info.port_id', operator: '=' },
      { label: '操作系统', key: 'os_info.name', operator: '=' }, // ARL 默认 OS 字段名
      { label: '域名', key: 'domain', operator: '=' },
      { label: 'CDN', key: 'cdn_name', operator: '=', placeholder: '输入厂商或独立源站' },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: 'IP', dataIndex: 'ip', key: 'ip', width: 160 },
      { title: '操作系统', key: 'os_info', width: 150 },
      { title: '开放端口', key: 'port_info', width: 200 },
      { title: '关联域名', key: 'domain', width: 250 },
      { title: 'CDN状态', key: 'ip_cdn_tag', width: 150 },
      { title: 'Geo', key: 'geo_city', width: 180 },
      { title: 'AS', key: 'geo_asn', width: 280 },
      { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
    ]
  },
  wih: {
    url: '/asset_wih/',
    exportUrl: '/asset_wih/export/', // 🚨 激活“导出WIH”按钮
    tabName: 'WIH',
    // 🚨 完美对齐截图的 4 个搜索框，记录类型带下拉选择
    searchFields: [
      {
        label: '记录类型',
        key: 'record_type',
        operator: '等于',
        hasOperatorSelect: true,
        operators: ['等于', '不等于']
      },
      { label: '内容', key: 'content', operator: '=' },
      { label: '来源 JS', key: 'source', operator: '=' },
      { label: '来源站点', key: 'site', operator: '=' }
    ],
    // 🚨 完美对齐抓包数据的列，特别是 source 键名
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '记录类型', dataIndex: 'record_type', key: 'record_type', width: 120 },
      { title: '内容', dataIndex: 'content', key: 'content', width: 250 },
      { title: '来源 JS', dataIndex: 'source', key: 'source', width: 450 }, // 绑定 source
      { title: '来源站点', dataIndex: 'site', key: 'wih_site', width: 250 },
      { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 180 }
    ]
  },
  cert: {
    url: '/asset_cert/',
    exportUrl: '/asset_cert/export/',
    tabName: 'SSL证书',
    searchFields: [
      { label: 'IP字段', key: 'ip', operator: '=' },
      { label: '签发者名称', key: 'cert.issuer_dn', operator: '=' },
      { label: '主题名称', key: 'cert.subject_dn', operator: '=' },
      { label: 'SHA-1', key: 'cert.fingerprint.sha1', operator: '=' },
      { label: '使用者备用名称', key: 'cert.extensions.subjectAltName', operator: '=' },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: 'HOST', key: 'host', width: 180 },
      { title: 'CERT', key: 'cert_detail', width: 900 },
      { title: '更新时间', key: 'update_date', width: 180 }
    ]
  },
  service: {
    url: '/asset_service/',
    tabName: '服务',
    searchFields: [
      { label: '服务', key: 'service_name', operator: '=' },
      { label: 'IP', key: 'service_info.ip', operator: '=' },
      { label: '端口', key: 'service_info.port_id', operator: '=' },
      { label: '产品', key: 'service_info.product', operator: '=' },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '服务', dataIndex: 'service_name', key: 'service_name', width: 150, align: 'center' },
      { title: 'IP端口', key: 'ip_port', width: 300 },
      { title: 'Product', key: 'product', width: 250 },
      { title: '更新时间', key: 'update_date', width: 180 }
    ]
  },
  fileleak: {
    url: '/asset_fileleak/',
    tabName: '文件泄露',
    searchFields: [
      { label: 'URL', key: 'url', operator: '=' },
      { label: '标题', key: 'title', operator: '=' },
      { label: '状态码', key: 'status_code', operator: '=' },
      { label: 'body 长度', key: 'content_length', operator: '=' },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: 'URL', key: 'fileleak_url', width: 500 },
      { title: '标题', dataIndex: 'title', key: 'title', width: 250 },
      { title: '状态码', dataIndex: 'status_code', key: 'status_code', width: 100, align: 'center' },
      { title: 'body 长度', dataIndex: 'content_length', key: 'content_length', width: 120, align: 'center' },
      { title: '更新时间', key: 'update_date', width: 180 }
    ]
  },
  url: {
    url: '/asset_url/',
    exportUrl: '/asset_url/export/',
    tabName: 'URL信息',
    searchFields: [
      { label: 'URL', key: 'url', operator: '=' },
      { label: '标题', key: 'title', operator: '=' },
      { label: '状态码', key: 'status_code', operator: '=' },
      { label: 'body 长度', key: 'content_length', operator: '=' },
      { label: '来源', key: 'source', operator: '=' },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: 'URL', key: 'url_link', width: 450 },
      { title: '标题', dataIndex: 'title', key: 'title', width: 200 },
      { title: '状态码', dataIndex: 'status_code', key: 'status_code', width: 100, align: 'center' },
      { title: 'body 长度', dataIndex: 'content_length', key: 'content_length', width: 120, align: 'center' },
      { title: '来源', dataIndex: 'source', key: 'source', width: 150 },
      { title: '更新时间', key: 'update_date', width: 180 }
    ]
  },
  vuln: {
    url: '/asset_vuln/',
    tabName: '风险',
    searchFields: [
      { label: '漏洞名称', key: 'vul_name', operator: '=' },
      { label: '类别', key: 'vul_category', operator: '=' },
      { label: '应用名', key: 'app_name', operator: '=' },
      { label: '目标', key: 'target', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '漏洞名称', dataIndex: 'vul_name', key: 'vul_name', width: 250 },
      { title: '类别', dataIndex: 'vul_category', key: 'vul_category', width: 120 },
      { title: '应用名', dataIndex: 'app_name', key: 'app_name', width: 150 },
      { title: '目标', dataIndex: 'target', key: 'target', width: 200 },
      { title: '凭证', key: 'verify_data', width: 350 },
      { title: '发现时间', dataIndex: 'insert_time', key: 'insert_time', width: 160 }
    ]
  },
  npoc_service: {
    url: '/asset_npoc_service/',
    tabName: '服务(python)',
    searchFields: [
      { label: '协议', key: 'scheme', operator: '=' },
      { label: '主机', key: 'host', operator: '=' },
      { label: '端口', key: 'port', operator: '=' },
      { label: '目标', key: 'target', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '协议', dataIndex: 'scheme', key: 'scheme', width: 150 },
      { title: '主机', dataIndex: 'host', key: 'host', width: 200 },
      { title: '端口', dataIndex: 'port', key: 'port', width: 100, align: 'center' },
      { title: '目标', dataIndex: 'target', key: 'target', width: 250 },
      { title: '保存时间', dataIndex: 'insert_time', key: 'insert_time', width: 180 }
    ]
  },
  cip: {
    url: '/asset_cip/',
    exportUrl: '/asset_cip/export/',
    tabName: 'C段',
    searchFields: [
      { label: 'C段', key: 'cidr_ip', operator: '=' },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: 'C段', dataIndex: 'cidr_ip', key: 'cidr_ip', width: 300 },
      { title: 'IP数', key: 'ip_count_col', width: 150, align: 'center' },
      { title: '域名数', key: 'domain_count_col', width: 150, align: 'center' },
      { title: '更新时间', key: 'update_date', width: 180 }
    ]
  },
  nuclei_result: {
    url: '/asset_nuclei_result/',
    tabName: 'nuclei',
    searchFields: [
      { label: '模版ID', key: 'template_id', operator: '=' },
      { label: '目标', key: 'target', operator: '=' },
      { label: '漏洞URL', key: 'vuln_url', operator: '=' },
      { label: '漏洞名称', key: 'vuln_name', operator: '=' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 60, align: 'center' },
      { title: '模版ID', dataIndex: 'template_id', key: 'template_id', width: 180 },
      { title: '目标', dataIndex: 'target', key: 'target', width: 200 },
      { title: '漏洞URL', key: 'nuclei_vuln_url', width: 300 },
      { title: '漏洞名称', dataIndex: 'vuln_name', key: 'vul_name', width: 200 },
      { title: '漏洞等级', dataIndex: 'vuln_severity', key: 'vul_severity', width: 100, align: 'center' },
      { title: '保存时间', dataIndex: 'insert_time', key: 'insert_time', width: 160 },
      { title: '验证命令', key: 'verify_command', width: 350 }
    ]
  },
  stat_finger: {
    url: '/asset_stat_finger/',
    tabName: '指纹统计',
    searchFields: [
      { 
        label: 'finger', 
        key: 'name', 
        operator: '模糊匹配',
        hasOperatorSelect: true,
        operators: ['模糊匹配', '精确匹配']
      },
      { label: '更新时间', key: 'update_date', type: 'dateRange' }
    ],
    cols: [
      { title: '序号', key: 'index', width: 80, align: 'center' },
      { title: 'finger', key: 'finger_name', width: 500 },
      { title: '数量', dataIndex: 'cnt', key: 'cnt', width: 200 },
      { title: '更新时间', key: 'update_date', width: 180 }
    ]
  },
  site_chain: {
    tabName: '全链路画像'
  }
});

const tabCache = createTabStateCache({
  getStorageKey: () => scope_id.value ? `ARL_GROUP_TAB_STATE_${scope_id.value}` : null,
  tabConfig,
  defaultTab: 'site'
});

const columns = ref(tabConfig.site.cols);

const fetchData = async () => {
  if (activeTab.value === 'site_chain') return;
  const config = tabConfig[activeTab.value];
  if (!config) return;

  const currentReqTab = activeTab.value;
  loading.value = true;
  try {
    // 🚨 修复 2：获取 computed 响应式对象的最新值
    const params = { page: pagination.current, size: pagination.pageSize, scope_id: scope_id.value };

    for (const key in searchForm.value) {
      if (searchForm.value[key] !== '' && searchForm.value[key] != null) {
        const fieldConfig = config.searchFields?.find(f => f.key === key);
        // 🚨 防御幽灵过滤：若该字段不在当前 Tab 的契约中，直接丢弃
        if (config.searchFields && !fieldConfig) continue;

        // 如果是时间范围数组，则特殊处理给后端
        if (key === 'update_date' && Array.isArray(searchForm.value[key])) {
          // 🚨 核心对齐：精准替换为 ARL 专属的 __dgt 和 __dlt 参数名，并格式化为全时分秒
          params.update_date__dgt = searchForm.value[key][0].format('YYYY-MM-DD HH:mm:ss');
          params.update_date__dlt = searchForm.value[key][1].format('YYYY-MM-DD HH:mm:ss');
        } else {
          let paramKey = key;
          if (fieldConfig && fieldConfig.hasOperatorSelect) {
            if (fieldConfig.operator === '大于') paramKey += '__gt';
            else if (fieldConfig.operator === '小于') paramKey += '__lt';
            else if (fieldConfig.operator === '不等于') paramKey += '__neq';
            else if (fieldConfig.operator === '不包含') paramKey += '__not';
            else if (fieldConfig.operator === '精确匹配') paramKey += '__eq';
          }
          params[paramKey] = searchForm.value[key];
        }
      }
    }
    const res = await request.get(config.url, { params });
    // 竞态防御：若响应到达时 Tab 已切换，丢弃过期响应
    if (activeTab.value !== currentReqTab) return;

    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
      asmCounts[activeTab.value] = res.total || 0;
      selectedRowKeys.value = [];
      // 更新当前 Tab 内存数据缓存并持久化轻量搜索状态
      tabCache.updateMemoryCache(activeTab.value, dataSource.value, pagination.total);
      tabCache.saveCurrentTab(activeTab.value, searchForm.value, pagination.current);
    }
  } catch (error) {
    if (activeTab.value === currentReqTab) {
      message.error('加载数据失败');
    }
  } finally {
    if (activeTab.value === currentReqTab) {
      loading.value = false;
    }
  }
};

const onSearch = () => {
  pagination.current = 1;
  tabCache.saveCurrentTab(activeTab.value, searchForm.value, 1);
  fetchData();
};
const resetSearch = () => {
  searchForm.value = {};
  tabCache.resetTabState(activeTab.value);
  pagination.current = 1;
  fetchData();
};
const handleTableChange = (page, pageSize) => {
  pagination.current = page;
  pagination.pageSize = pageSize;
  tabCache.saveCurrentTab(activeTab.value, searchForm.value, page);
  fetchData();
};

// ================= 批量删除功能 (兼容所有 Tab) =================
const handleBatchDelete = () => {
  Modal.confirm({
    title: '批量删除确认',
    icon: createVNode(ExclamationCircleOutlined),
    content: `确定要从当前分组中删除选中的 ${selectedRowKeys.value.length} 条资产吗？删除后不可恢复。`,
    okText: '确 定',
    okType: 'danger',
    cancelText: '取 消',
    onOk: async () => {
      try {
        const config = tabConfig[activeTab.value];
        if (!config || !config.url) return;

        // 🚨 优先读取专用配置，否则动态拼接删除 API 路径：例如 /asset_domain/ -> /asset_domain/delete/
        const deleteUrl = config.deleteUrl || `${config.url}delete/`;

        // 🚨 严格按照抓包 Payload：键名为 _id
        const res = await request.post(deleteUrl, {
          _id: selectedRowKeys.value
        });

        if (res.code === 200) {
          message.success('批量删除成功！');

          // 如果删光了当前页的数据且不在第一页，自动回退一页
          if (dataSource.value.length === selectedRowKeys.value.length && pagination.current > 1) {
            pagination.current -= 1;
          }

          selectedRowKeys.value = []; // 清空选中状态
          tabCache.invalidateMemoryCache(activeTab.value);
          fetchData(); // 🚨 完美对齐抓包里的第二个请求：自动刷新表格数据
        } else {
          message.error('删除失败: ' + res.message);
        }
      } catch (error) {
        message.error('请求异常，删除失败');
      }
    }
  });
};

watch(activeTab, (newVal, oldVal) => {
  if (oldVal && tabConfig[oldVal] && !isScopeSwitching.value) {
    // 离开旧选项卡前，仅在非切组且有效交互时保存当前搜索表单、操作符和页码
    tabCache.saveCurrentTab(oldVal, searchForm.value, pagination.current);
  }

  if (newVal === 'site_chain') {
    fetchDomainSuggestions();
    if (route.query.chain_target && !chainSearchDomain.value) {
      chainSearchDomain.value = String(route.query.chain_target);
      nextTick(() => {
        handleChainSearch();
      });
    }
    return;
  }

  if (tabConfig[newVal]) {
    columns.value = tabConfig[newVal].cols;
    selectedRowKeys.value = [];

    // 恢复新选项卡的搜索表单、操作符与页码
    searchForm.value = tabCache.getTabSearchForm(newVal);
    tabCache.applyTabOperators(newVal);
    pagination.current = tabCache.getTabPage(newVal);

    // 检查内存数据缓存：若已加载过则直接秒开渲染，不重复向后端发请求
    const cached = tabCache.getMemoryCache(newVal);
    if (cached) {
      dataSource.value = cached.dataSource;
      pagination.total = cached.total;
    } else {
      fetchData();
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
    resetChainSearch();

    // 若路由携带 chain_target，直接深链穿透至全链路画像并触发拉取
    if (route.query.chain_target) {
      activeTab.value = 'site_chain';
      chainSearchDomain.value = String(route.query.chain_target);
      nextTick(() => {
        isScopeSwitching.value = false;
        fetchDomainSuggestions();
        handleChainSearch();
      });
      return;
    }

    const restoredTab = tabCache.init();
    if (restoredTab && tabConfig[restoredTab] && restoredTab !== activeTab.value) {
      activeTab.value = restoredTab;
      nextTick(() => {
        isScopeSwitching.value = false;
        if (activeTab.value === 'site_chain') {
          fetchDomainSuggestions();
        }
      });
    } else {
      if (activeTab.value === 'site_chain') {
        fetchDomainSuggestions();
        nextTick(() => {
          isScopeSwitching.value = false;
        });
      } else {
        if (tabConfig[activeTab.value]) {
          columns.value = tabConfig[activeTab.value].cols;
          searchForm.value = tabCache.getTabSearchForm(activeTab.value);
          tabCache.applyTabOperators(activeTab.value);
          pagination.current = tabCache.getTabPage(activeTab.value);
        }
        const cached = tabCache.getMemoryCache(activeTab.value);
        if (cached) {
          dataSource.value = cached.dataSource;
          pagination.total = cached.total;
        } else {
          fetchData();
        }
        nextTick(() => {
          isScopeSwitching.value = false;
        });
      }
    }
  }
}, { immediate: true }); // immediate: true 完美替代了 onMounted 的作用


// ================= 导出功能 (站点、域名、WIH 通用) =================
const handleExport = async () => {
  const config = tabConfig[activeTab.value];
  if (!config || !config.exportUrl) return;

  try {
    message.loading({ content: `正在生成导出文件...`, key: 'export_data' });

    // 🚨 动态映射真实的 tabIndex
    const tabIndexMap = { site: 0, domain: 1, ip: 2, cert: 3, service: 4, fileleak: 5, url: 6, cip: 7, stat_finger: 8, wih: 9, vuln: 10, npoc_service: 11, nuclei_result: 12 };

    // 🚨 完美对齐 WIH 抓包：size 扩大到十万级 100000，并带上动态的 tabIndex
    const params = {
      page: 1,
      size: 100000,
      scope_id: scope_id.value,
      targetName: targetName.value,
      tabIndex: tabIndexMap[activeTab.value]
    };

    // 🚨 补全缺失的搜索参数：确保用户过滤后导出的数据也是精准的！
    for (const key in searchForm.value) {
      if (searchForm.value[key] !== '' && searchForm.value[key] != null) {
        const fieldConfig = config.searchFields?.find(f => f.key === key);
        // 🚨 防御幽灵过滤：若该字段不在当前 Tab 的契约中，直接丢弃
        if (config.searchFields && !fieldConfig) continue;

        if (key === 'update_date' && Array.isArray(searchForm.value[key])) {
          params.update_date__dgt = searchForm.value[key][0].format('YYYY-MM-DD HH:mm:ss');
          params.update_date__dlt = searchForm.value[key][1].format('YYYY-MM-DD HH:mm:ss');
        } else {
          let paramKey = key;
          if (fieldConfig && fieldConfig.hasOperatorSelect) {
            if (fieldConfig.operator === '大于') paramKey += '__gt';
            else if (fieldConfig.operator === '小于') paramKey += '__lt';
            else if (fieldConfig.operator === '不等于') paramKey += '__neq';
            else if (fieldConfig.operator === '不包含') paramKey += '__not';
            else if (fieldConfig.operator === '精确匹配') paramKey += '__eq';
          }
          params[paramKey] = searchForm.value[key];
        }
      }
    }

    const res = await request.get(config.exportUrl, { params, responseType: 'blob' });

    const isCert = activeTab.value === 'cert';
    const mimeType = isCert ? 'application/json;charset=utf-8' : 'text/plain;charset=utf-8';
    const ext = isCert ? 'json' : 'txt';

    const blob = new Blob([res], { type: mimeType });
    const downloadUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `ARL_Group_Export_${activeTab.value}_${new Date().getTime()}.${ext}`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    message.success({ content: `导出成功！`, key: 'export_data', duration: 2 });
  } catch (error) {
    message.error({ content: `导出异常`, key: 'export_data', duration: 2 });
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
    typeName = 'IP端口';
  } else if (type === 'domain') {
    exportUrl = '/asset_ip/export_domain/';
    typeName = '域名';
  } else if (type === 'ip') {
    exportUrl = '/asset_ip/export_ip/';
    typeName = 'IP';
  }

  if (!exportUrl) return;

  try {
    message.loading({ content: `正在打包生成文件...`, key: 'export_ip_data' });

    // 🚨 完美对齐 Payload，并自动带上当前所有的搜索过滤条件
    const params = {
      page: 1,
      size: 10000,
      scope_id: scope_id.value,
      targetName: targetName.value,
      tabIndex: 2
    };

    for (const key in searchForm.value) {
      if (searchForm.value[key] !== '' && searchForm.value[key] != null) {
        if (key === 'update_date' && Array.isArray(searchForm.value[key])) {
          params.update_date__dgt = searchForm.value[key][0].format('YYYY-MM-DD HH:mm:ss');
          params.update_date__dlt = searchForm.value[key][1].format('YYYY-MM-DD HH:mm:ss');
        } else {
          params[key] = searchForm.value[key];
        }
      }
    }

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

    message.success({ content: `导出 ${typeName} 成功！`, key: 'export_ip_data', duration: 2 });
  } catch (error) {
    message.error({ content: `导出异常，请重试`, key: 'export_ip_data', duration: 2 });
  }
};


// ================= 添加站点弹窗 =================
const addSiteVisible = ref(false);
const addSiteLoading = ref(false);
const addSiteFormRef = ref();
const policies = ref([]);

const addSiteForm = reactive({ site: '', policy_id: undefined });
const addSiteRules = {
  site: [{ required: true, message: '请输入站点' }],
  policy_id: [{ required: true, message: '请选择策略' }]
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
      message.success('添加站点成功！');
      addSiteVisible.value = false;
      tabCache.invalidateAllMemoryCaches();
      fetchData(); // 刷新表格
    } else if (res.code === 802) {
      message.error(res.message); // 弹出 "任务目标不在资产组中"
    } else {
      message.error('添加失败: ' + res.message);
    }
  } catch (e) {
    message.error('请求异常');
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
  name: [{ required: true, message: '请输入任务名称' }],
  policy_id: [{ required: true, message: '请选择策略' }]
};
// 统计目标数量
const getPocCount = (policy) => {
  return policy.policy?.poc_config?.filter(poc => poc.enable)?.length || 0;
};

// 1. 打开弹窗：智能区分勾选目标 vs 全量筛选结果集
const openRiskModal = async () => {
  try {
    message.loading({ content: '正在准备巡航目标...', key: 'risk_task' });

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
        message.warning({ content: '选中的记录中未包含有效的站点目标', key: 'risk_task' });
        return;
      }

      selectedRiskTargets.value = selectedSites;
      currentResultSetId.value = '';
      currentTargetCount.value = selectedSites.length;

      message.success({ content: `成功锁定选中的 ${selectedSites.length} 条资产准备下发`, key: 'risk_task' });
    } else {
      // 🎯 未勾选：根据当前搜索与资产组条件打包全量结果集
      selectedRiskTargets.value = [];
      const params = { scope_id: scope_id.value };
      for (const key in searchForm.value) {
        if (searchForm.value[key] !== '' && searchForm.value[key] != null) {
          if (key === 'update_date' && Array.isArray(searchForm.value[key])) {
            params.update_date__dgt = searchForm.value[key][0].format('YYYY-MM-DD HH:mm:ss');
            params.update_date__dlt = searchForm.value[key][1].format('YYYY-MM-DD HH:mm:ss');
          } else {
            params[key] = searchForm.value[key];
          }
        }
      }

      // 发起结果集保存请求
      const setRes = await request.get('/asset_site/save_result_set/', { params });
      if (setRes.code !== 200) throw new Error('生成结果集失败');

      currentResultSetId.value = setRes.data.result_set_id;
      currentTargetCount.value = setRes.data.result_total || 0;

      message.success({ content: `成功锁定 ${setRes.data.result_total} 条资产准备下发`, key: 'risk_task' });
    }

    // 初始化弹窗数据
    riskForm.name = '';
    riskForm.policy_id = undefined;
    riskModalVisible.value = true;
  } catch (e) {
    message.error({ content: '准备下发任务失败', key: 'risk_task' });
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
      message.success('风险巡航任务下发成功！');
      riskModalVisible.value = false;
      if (selectedRiskTargets.value.length > 0) {
        selectedRowKeys.value = [];
      }
    } else {
      message.error('下发失败: ' + (res.message || '未知错误'));
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
  domain: [{ required: true, message: '请输入子域名' }],
  policy_id: [{ required: true, message: '请选择策略' }]
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
      message.success('添加子域名成功！');
      addDomainVisible.value = false;
      tabCache.invalidateAllMemoryCaches();
      fetchData(); // 自动刷新当前页面的域名列表
    } else if (res.code === 701) {
      message.error(res.message); // 原汁原味抛出：域名不在给定的资产范围中
    } else {
      message.error('添加失败: ' + res.message);
    }
  } catch (e) {
    message.error('请求异常');
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
  padding: 2px 6px;
  height: 28px;
  width: 28px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 4px;
  color: var(--arl-text-secondary);
  flex-shrink: 0;
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

.chain-tab-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #722ed1;
  font-weight: 600;
  font-size: 12px;
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

/* 全链路画像专属检索栏 */
.chain-search-container {
  padding: 8px 12px;
  border-top: 1px solid var(--arl-border-color);
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--arl-bg-light);
}

.chain-quick-chips {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  font-size: 12px;
}

.chips-label {
  color: var(--arl-text-secondary);
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
  font-size: 12px;
}

.chips-list {
  display: flex;
  align-items: center;
  gap: 4px;
  flex-wrap: wrap;
}

.quick-chip-tag {
  cursor: pointer;
  border-radius: 3px;
  font-size: 11px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  transition: all 0.2s;
  user-select: none;
}
.quick-chip-tag:hover {
  opacity: 0.85;
  transform: translateY(-1px);
}

.chain-search-row {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.chain-search-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--arl-text-color);
}

.chain-result-stat {
  font-size: 12px;
  color: var(--arl-text-secondary);
  margin-left: 6px;
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

</style>