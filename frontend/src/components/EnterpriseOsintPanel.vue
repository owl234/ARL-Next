<template>
  <div class="enterprise-osint-panel">
    <!-- 顶部摘要与操作栏 (仅当有任务且未隐藏 Header 时渲染) -->
    <div v-if="taskId && !hideHeader" style="margin-bottom: 12px;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
          <span style="font-weight: 600; font-size: 15px; color: var(--arl-text-color);">{{ displayName }}</span>
          <a-tag v-if="taskTarget && taskTarget.startsWith('TYC_')" color="cyan">{{ taskTarget }}</a-tag>
          <a-tag v-if="taskTypeLabel" color="blue">{{ taskTypeLabel }}</a-tag>
          <a-tag v-if="taskStatusLabel" :color="taskStatusColor">{{ taskStatusLabel }}</a-tag>
          <a-badge v-if="hasIncrement" :count="assetText('tasks.newAssets')" class="asset-increment-badge" />
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
          <a-tooltip :title="isUpdating ? assetText('assets.organizationAssetsAreBeingUpdatedInTheBackground') : assetText('assets.fetchTheLatestIcpRecordsAppsAndInvestment')">
            <a-button type="primary" size="small" :loading="refreshLoading || isUpdating" :disabled="isUpdating" @click="handleRefreshTask">
              <template #icon><sync-outlined :spin="refreshLoading || isUpdating" /></template>
              {{ isUpdating ? assetText('assets.updatingOrganization') : assetText('assets.updateOrganizationAssets') }}
            </a-button>
          </a-tooltip>
        </div>
      </div>
    </div>

    <!-- 维度 Tabs 导航与控制检索区 (吸附在 Hero 顶栏正下方，与 ASM 保持同等视觉与吸顶标准) -->
    <div
      v-if="taskId"
      ref="osintControlRef"
      class="osint-sticky-control-box"
      :style="{ top: (props.stickyTopOffset || 0) + 'px' }"
    >
      <!-- 测绘更新中顶部平滑提示条 -->
      <div v-if="isUpdating" class="osint-updating-banner">
        <div class="updating-banner-content">
          <sync-outlined :spin="true" class="updating-spin-icon" />
          <span class="updating-banner-text">
            <b>{{ assetText('assets.updatingOrganizationAssetDiscovery') }}</b>{{ assetText('assets.retrievingTheLatestCompanyRecordsIcpRecordsAnd') }}<span v-if="updateElapsed > 0">{{ assetText('assets.elapsed') }} {{ updateElapsed }} {{ assetText('assets.seconds') }}</span>{{ assetText('assets.theExistingSnapshotRemainsAvailableTheViewWill') }}
          </span>
        </div>
        <a-tag color="processing" class="updating-banner-tag">{{ assetText('assets.comparingNewAssets') }}</a-tag>
      </div>

      <!-- 维度 Tabs 导航 (微徽标胶囊风格) -->
      <a-tabs v-model:activeKey="activeTab" type="card" size="small" class="arl-detail-tabs osint-tabs-nav" @change="onTabChange">
        <a-tab-pane v-for="t in osintTabList" :key="t.key">
          <template #tab>
            <span class="osint-tab-item">
              <span>{{ t.label }}</span>
              <span class="osint-tab-badge" :class="{ 'has-data': (queryCounts[t.key] || 0) > 0 }">
                {{ queryCounts[t.key] || 0 }}
              </span>
            </span>
          </template>
        </a-tab-pane>
        <a-tab-pane key="log">
          <template #tab>
            <span class="log-tab-pill">
              <code-outlined /> {{ assetText('assets.discoveryLogs') }}
              <span v-if="taskRecord.status === 'running'" class="log-pulse-dot"></span>
            </span>
          </template>
        </a-tab-pane>
      </a-tabs>

      <!-- 统一工具栏与直接平铺检索区 -->
      <div class="osint-toolbar-container">
        <!-- 业务操作行 -->
        <div class="toolbar-row">
          <div class="toolbar-left">
            <span class="toolbar-title-text">{{ assetText('assets.categoryHeading', { category: currentTabLabel }) }}</span>
            <span class="toolbar-meta-count">
              {{ assetText('assets.recordCount', { count: activeTab === 'log' ? syslogList.length : (queryCounts[activeTab] || pagination.total || 0) }) }}
            </span>
            <a-tag v-if="hasIncrement && activeTab !== 'log'" color="success" class="osint-mini-tag">
              {{ assetText('assets.newAssetsFound') }}
            </a-tag>
          </div>

          <div class="toolbar-right">
            <template v-if="activeTab !== 'log'">
              <!-- 扩充本组按钮 (仅在 Web 备案维度且存在未纳管域名时呈现) -->
              <a-popconfirm
                v-if="props.scopeId && activeTab === 'web' && untrackedWebDomains.length > 0"
                :title="assetText('assets.addAllDiscoveredUnmanagedDomainsCountToThis', { count: untrackedWebDomains.length })"
                :ok-text="assetText('assets.addDomains')"
                :cancel-text="assetText('tasks.cancel')"
                @confirm="handleOneClickExpandScope"
              >
                <a-button type="primary" size="small" :loading="expandingScopeLoading" style="background: #52c41a; border-color: #52c41a;">
                  <template #icon><plus-circle-outlined /></template>
                  {{ assetText('assets.addNewDomainCount', { count: untrackedWebDomains.length }) }}
                </a-button>
              </a-popconfirm>

              <a-tooltip :title="isUpdating ? assetText('assets.organizationAssetsAreBeingUpdatedInTheBackground') : assetText('assets.fetchTheLatestIcpRecordsAppsAndInvestment')">
                <a-button type="primary" size="small" :loading="refreshLoading || isUpdating" :disabled="isUpdating" @click="handleRefreshTask">
                  <template #icon><sync-outlined :spin="refreshLoading || isUpdating" /></template>
                  {{ isUpdating ? assetText('assets.updatingOrganization') : assetText('assets.updateOrganizationAssets') }}
                </a-button>
              </a-tooltip>
              <a-tooltip :title="assetText('assets.changeTheOrganizationLinkedToThisGroupAnd')">
                <a-button size="small" @click="emit('openBind')">
                  <template #icon><link-outlined /></template>
                  {{ assetText('assets.changeOrganization') }}
                </a-button>
              </a-tooltip>
              <a-button size="small" :loading="exportLoading" @click="handleExport">
                <template #icon><download-outlined /></template>
                {{ assetText('assets.exportCurrentCategory') }}
              </a-button>

              <!-- 高级筛选折叠展开切换按钮 -->
              <a-button
                v-if="currentSearchFields.length"
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
            </template>
            <template v-else>
              <a-tag :color="taskStatusColor">{{ taskStatusLabel }}</a-tag>
              <span v-if="taskRecord.status === 'running'" class="log-polling-hint">{{ assetText('assets.pollingEvery3Seconds') }}</span>
              <a-button size="small" :loading="logLoading" @click="() => fetchLogs(true)">
                <template #icon><sync-outlined :spin="logLoading" /></template>
                {{ assetText('assets.refreshLogs') }}
              </a-button>
            </template>
          </div>
        </div>

        <!-- 直接平铺的紧凑栅格筛选卡片 (可折叠) -->
        <transition name="fade-slide">
          <div v-show="isAdvancedFilterOpen" v-if="activeTab !== 'log' && currentSearchFields.length" class="osint-filter-card">
          <a-form :label-wrap="true" :model="searchForm" class="filter-grid-form">
            <a-row :gutter="[12, 6]">
              <a-col
                v-for="field in currentSearchFields"
                :key="field.key"
                :xs="24" :sm="12" :md="assetLocale !== 'zh-CN' ? 12 : 8" :lg="assetLocale !== 'zh-CN' ? 8 : 6"
              >
                <div class="filter-field-cell">
                  <span class="filter-field-label" :class="{ 'filter-field-label-wide': assetLocale !== 'zh-CN' }" :title="field.label">{{ field.label }}</span>
                  <div class="filter-field-widget">
                    <!-- 下拉选择 -->
                    <a-select
                      v-if="field.type === 'select'"
                      v-model:value="searchForm[field.key]"
                      :placeholder="assetText('tasks.selectField', { field: field.label })"
                      style="width: 100%;"
                      size="small"
                      allowClear
                      @change="onSearch"
                    >
                      <a-select-option v-for="opt in field.options" :key="opt.value" :value="opt.value">{{ opt.label }}</a-select-option>
                    </a-select>

                    <!-- 组合操作符输入框 (如 投资比例/数额 等于/大于/小于) -->
                    <div
                      v-else-if="field.hasOperatorSelect"
                      class="filter-operator-box"
                    >
                      <a-input
                        v-model:value="searchForm[field.key]"
                        :placeholder="assetText('tasks.enterField', { field: field.label })"
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
                        <a-select-option v-for="op in field.operators" :key="op" :value="op">{{ op === 'eq' ? '=' : op === 'gt' ? '>' : '<' }}</a-select-option>
                      </a-select>
                    </div>

                    <!-- 普通文本输入框 -->
                    <a-input
                      v-else
                      v-model:value="searchForm[field.key]"
                      :placeholder="assetText('tasks.enterField', { field: field.label })"
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

    <!-- 资产数据表格区 -->
    <div v-if="taskId && activeTab !== 'log'">
      <a-table
        :sticky="osintStickyConfig"
        :dataSource="assetList"
        :columns="dynamicColumns"
        :loading="loading"
        :pagination="false"
        :row-selection="activeTab === 'web' ? { selectedRowKeys: selectedWebRowKeys, onChange: onWebSelectChange } : null"
        :scroll="{ x: 'max-content' }"
        :rowKey="(record) => record._id || record.id || record.domain || record.ym || record.name || Math.random()"
        size="small"
        class="modern-clean-table"
        style="margin-bottom: 8px;"
      >
        <template #bodyCell="{ column, record, text, index }">
          <template v-if="column.key === 'index'">
            {{ (pagination.current - 1) * pagination.pageSize + index + 1 }}
          </template>

          <!-- 图标/头像渲染 -->
          <template v-else-if="column.key === 'icon'">
            <a-avatar v-if="getAssetIcon(record)" :src="getAssetIcon(record)" shape="square" :size="32" style="background: #fafafa; border: 1px solid var(--arl-border-color);" />
            <span v-else style="color: #bfbfbf;">-</span>
          </template>

          <!-- 域名可点击外链与快捷复制 -->
          <template v-else-if="column.key === 'domain'">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 4px;">
              <a v-if="record.domain || record.ym" :href="(record.domain || record.ym).startsWith('http') ? (record.domain || record.ym) : ('http://' + (record.domain || record.ym))" target="_blank" rel="noopener noreferrer" style="color: var(--arl-theme-color); word-break: break-all;">
                {{ record.domain || record.ym }} <export-outlined style="font-size: 11px;" />
              </a>
              <span v-else>-</span>
              <a-tooltip :title="assetText('assets.copyDomain')" v-if="record.domain || record.ym">
                <a-button type="text" size="small" style="padding: 0 4px; height: 22px;" @click.stop="handleCopyText(record.domain || record.ym)">
                  <copy-outlined style="font-size: 12px; opacity: 0.65;" />
                </a-button>
              </a-tooltip>
            </div>
          </template>

          <!-- 纳管状态 -->
          <template v-else-if="column.key === 'managedStatus'">
            <a-tag v-if="!props.scopeId" color="default" class="asset-small-label">{{ assetText('assets.noGroupLinked') }}</a-tag>
            <a-tag v-else-if="isDomainManaged(record)" color="success" style="font-size: 11px;">
              <check-circle-outlined /> {{ assetText('tasks.managed') }}
            </a-tag>
            <a-tag v-else color="orange" style="font-size: 11px;">
              <plus-circle-outlined /> {{ assetText('assets.unmanaged') }}
            </a-tag>
          </template>

          <!-- 首页网址外链与快捷复制 -->
          <template v-else-if="column.key === 'homeUrl'">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 4px;">
              <a v-if="getAssetHomeUrl(record)" :href="getAssetHomeUrl(record)" target="_blank" rel="noopener noreferrer" style="color: var(--arl-theme-color); word-break: break-all;">
                {{ getAssetHomeUrl(record) }} <export-outlined style="font-size: 11px;" />
              </a>
              <span v-else>-</span>
              <a-tooltip :title="assetText('assets.copyUrl')" v-if="getAssetHomeUrl(record)">
                <a-button type="text" size="small" style="padding: 0 4px; height: 22px;" @click.stop="handleCopyText(getAssetHomeUrl(record))">
                  <copy-outlined style="font-size: 12px; opacity: 0.65;" />
                </a-button>
              </a-tooltip>
            </div>
          </template>

          <!-- 微博主页外链 -->
          <template v-else-if="column.key === 'href'">
            <a v-if="record.href" :href="record.href" target="_blank" rel="noopener noreferrer" style="color: var(--arl-theme-color);">
              {{ assetText('assets.openWeibo') }} <export-outlined class="asset-small-label" />
            </a>
            <span v-else>-</span>
          </template>

          <!-- 公众号二维码浮层预览 -->
          <template v-else-if="column.key === 'qrcode'">
            <a-popover v-if="record.codeImg" placement="right" trigger="hover">
              <template #content>
                <div style="text-align: center; padding: 4px;">
                  <img :src="record.codeImg" style="width: 150px; height: 150px; display: block;" />
                  <span class="asset-action-hint">{{ assetText('assets.scanWithWechatToFollow') }}</span>
                </div>
              </template>
              <a-tag color="blue" class="asset-clickable"><qrcode-outlined /> {{ assetText('assets.viewQrCode') }}</a-tag>
            </a-popover>
            <span v-else style="color: #bfbfbf;">-</span>
          </template>

          <!-- 企业状态 Tag 渲染 -->
          <template v-else-if="column.key === 'status'">
            <a-tag v-if="['存续', '在业', '正常'].includes(record.status || record.regStatus)" color="success">
              {{ record.status || record.regStatus }}
            </a-tag>
            <a-tag v-else-if="['注销', '吊销', '撤销', '迁出'].includes(record.status || record.regStatus)" color="error">
              {{ record.status || record.regStatus }}
            </a-tag>
            <a-tag v-else-if="record.status || record.regStatus">
              {{ record.status || record.regStatus }}
            </a-tag>
            <span v-else style="color: #bfbfbf;">-</span>
          </template>

          <!-- 地区展示 -->
          <template v-else-if="column.key === 'region'">
            {{ record.region || [record.province, record.city].filter(Boolean).join(' ') || '-' }}
          </template>

          <!-- 成立时间 -->
          <template v-else-if="column.key === 'estiblishTime'">
            {{ formatDate(record.estiblishTime) }}
          </template>

          <!-- 单位性质 -->
          <template v-else-if="column.key === 'companyType'">
            {{ record.companyType || record.natureName || '-' }}
          </template>

          <!-- 服务备案号/服务许可 -->
          <template v-else-if="column.key === 'serviceLicence'">
            {{ record.serviceLicence || record.liscense || record.serviceFilingNumber || record.mainLicence || '-' }}
          </template>

          <!-- 主办单位 -->
          <template v-else-if="column.key === 'unitName'">
            {{ record.unitName || record.companyName || record.miniProgramIcpRecordDetail?.icpFilingSubjectInformation?.organizingName || '-' }}
          </template>

          <!-- 名称字段多字段兼顾 -->
          <template v-else-if="column.key === 'serviceName' || column.key === 'name'">
            {{ record.serviceName || record.name || record.webName || record.title || '-' }}
          </template>

          <!-- 法定代表人 -->
          <template v-else-if="column.key === 'legalPerson'">
            {{ record.legalPerson || record.legalPersonName || '-' }}
          </template>

          <!-- 分类字段 -->
          <template v-else-if="column.key === 'category'">
            {{ record.category || record.classes || record.type || '-' }}
          </template>

          <!-- 微信号 -->
          <template v-else-if="column.key === 'wechatId'">
            {{ record.wechatId || record.publicNum || '-' }}
          </template>

          <!-- 更新/审核时间 -->
          <template v-else-if="column.key === 'updateRecordTime'">
            {{ record.updateRecordTime || record.examineDate || '-' }}
          </template>

          <!-- 简介/描述 -->
          <template v-else-if="column.key === 'brief' || column.key === 'recommend'">
            <div style="max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="record.brief || record.recommend || record.info || text">
              {{ record.brief || record.recommend || record.info || text || '-' }}
            </div>
          </template>

          <!-- 原始 JSON 抽屉 -->
          <template v-else-if="column.key === 'raw'">
            <a-tooltip :title="assetText('assets.viewRawJsonData')" placement="top">
              <a-button type="text" size="small" class="json-icon-btn" @click="openRawDrawer(record)">
                <code-outlined />
              </a-button>
            </a-tooltip>
          </template>

          <template v-else>
            {{ text || '-' }}
          </template>
        </template>

        <!-- 标准表格空状态 -->
        <template #emptyText>
          <ArlEmpty :description="assetText('assets.noEnterpriseAssetData')" />
        </template>
      </a-table>

      <!-- 分页栏 -->
      <div class="arl-pagination-bar">
        <div class="pagination-info">{{ assetText('tasks.paginationSummary', { pages: Math.ceil(pagination.total / pagination.pageSize) || 1, total: pagination.total }) }}</div>
        <a-pagination
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="pagination.current"
          v-model:pageSize="pagination.pageSize"
          :total="pagination.total"
          size="small"
          show-size-changer
          @change="handlePaginationChange"
          @showSizeChange="handlePaginationChange"
        />
      </div>

      <!-- 悬浮浮动批处理条 (仅在 Web 备案维度且选中行时平滑弹出) -->
      <transition name="floating-slide">
        <div v-if="activeTab === 'web' && selectedWebRowKeys.length > 0" class="arl-floating-action-bar">
          <div class="floating-info">
            <check-circle-filled style="color: var(--arl-theme-color); font-size: 16px;" />
            <span>{{ assetText('tasks.selected') }} <b class="asset-selection-number">{{ selectedWebRowKeys.length }}</b> {{ assetText('assets.registeredDomains') }}</span>
          </div>
          <div class="floating-actions">
            <!-- 若在资产组内，优先提供直达扩充当前组，免弹窗！ -->
            <a-button v-if="props.scopeId" type="primary" size="small" :loading="expandingScopeLoading" @click="handleExpandSelectedToScope">
              <template #icon><plus-circle-outlined /></template>
              {{ assetText('assets.addDomainCount', { count: selectedWebRowKeys.length }) }}
            </a-button>
            <a-button size="small" @click="openSyncModalWithSelected">
              <template #icon><cloud-sync-outlined /></template>
              {{ props.scopeId ? assetText('assets.syncToAnotherAssetGroup') : assetText('assets.syncToAssetGroupCount', { count: selectedWebRowKeys.length }) }}
            </a-button>
            <a-button size="small" @click="handleBatchCopyDomains">
              <template #icon><copy-outlined /></template>
              {{ assetText('assets.copyDomain') }}
            </a-button>
            <a-button size="small" @click="clearWebSelection">{{ assetText('tasks.clearSelection') }}</a-button>
          </div>
        </div>
      </transition>
    </div>

    <!-- 运行日志 Tab -->
    <div v-if="taskId && activeTab === 'log'" style="margin-top: 8px;">
      <div class="log-terminal-card">
        <div class="log-terminal-header">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span class="asset-toolbar-heading">{{ assetText('assets.taskExecutionLogs') }}</span>
            <a-tag :color="formatTaskStatusColor(taskRecord.status)">
              {{ formatTaskStatus(taskRecord.status) }}
            </a-tag>
            <span class="asset-secondary-caption" v-if="taskRecord.status === 'running'">{{ assetText('assets.automaticallyPollingForNewLogsEvery3Seconds') }}</span>
          </div>
          <a-button size="small" :loading="logLoading" @click="() => fetchLogs(true)">
            <template #icon><sync-outlined :spin="logLoading" /></template>
            {{ assetText('assets.refreshLogs') }}
          </a-button>
        </div>
        <div ref="terminalContainer" class="log-terminal-body">
          <div v-for="(log, idx) in syslogList" :key="idx" class="log-terminal-line">
            <span class="log-time">[{{ log.create_time }}]</span>
            <span :class="['log-level', log.level]">[{{ (log.level || 'info').toUpperCase() }}]</span>
            <span class="log-title">[{{ log.title }}]</span>
            <span class="log-msg">{{ log.message }}</span>
          </div>
          <div v-if="syslogList.length === 0" class="log-empty">{{ assetText('tasks.systemNoLogsYetTheTaskHasNot') }}</div>
        </div>
      </div>
    </div>

    <!-- 同步至资产组弹窗 -->
    <SyncToScopeModal
      v-model:open="syncModalVisible"
      :task="taskRecord"
      :preSelectedDomains="selectedWebDomains"
      @success="handleSyncSuccess"
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
import { ref, reactive, computed, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { message, notification } from 'ant-design-vue';
import {
  SearchOutlined,
  DownloadOutlined,
  CloudSyncOutlined,
  SyncOutlined,
  ExportOutlined,
  QrcodeOutlined,
  CopyOutlined,
  RedoOutlined,
  CodeOutlined,
  CheckCircleFilled,
  CheckCircleOutlined,
  PlusCircleOutlined,
  LinkOutlined,
  FilterOutlined,
  DownOutlined,
  UpOutlined
} from '@ant-design/icons-vue';
import request from '../utils/request';
import { copyText } from '../utils/clipboard';
import { formatTaskStatus, formatTaskStatusColor } from '../constants/taskStatus';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import SyncToScopeModal from './SyncToScopeModal.vue';
import RawDataDrawer from './RawDataDrawer.vue';

const { t: assetText, locale: assetLocale } = useI18n({ useScope: 'global' });

const props = defineProps({
  taskId: {
    type: String,
    default: ''
  },
  scopeId: {
    type: String,
    default: ''
  },
  enterpriseName: {
    type: String,
    default: ''
  },
  hideHeader: {
    type: Boolean,
    default: false
  },
  stickyTopOffset: {
    type: Number,
    default: 120
  },
  updatingTaskId: {
    type: String,
    default: ''
  }
});

const emit = defineEmits(['synced', 'refreshed', 'taskLoaded', 'update:taskId', 'openBind']);

const activeUpdatingTaskId = ref('');
const isUpdating = ref(false);
const updateElapsed = ref(0);
let updateTimer = null;
let elapsedTimer = null;

const stopUpdatePolling = () => {
  if (updateTimer) {
    clearInterval(updateTimer);
    updateTimer = null;
  }
  if (elapsedTimer) {
    clearInterval(elapsedTimer);
    elapsedTimer = null;
  }
};

const startUpdatePolling = (targetUpdatingId) => {
  if (!targetUpdatingId) return;
  stopUpdatePolling();
  isUpdating.value = true;
  activeUpdatingTaskId.value = targetUpdatingId;
  updateElapsed.value = 0;
  elapsedTimer = setInterval(() => {
    updateElapsed.value += 1;
  }, 1000);

  updateTimer = setInterval(async () => {
    try {
      const res = await request.get('/icp/task', { params: { _id: targetUpdatingId } });
      if (res && res.code === 200 && res.items && res.items.length > 0) {
        const task = res.items[0];
        if (task.status === 'done') {
          stopUpdatePolling();
          isUpdating.value = false;
          activeUpdatingTaskId.value = '';
          notification.success({
            message: assetText('assets.organizationAssetsUpdated'),
            description: assetText('assets.theEnterpriseAssetProfileIsUpToDate', { count: task.statistic?.asset_cnt || 0 }),
            duration: 4
          });
          emit('update:taskId', targetUpdatingId);
          emit('refreshed', targetUpdatingId);
          fetchTaskDetail();
          fetchAssets(1, pagination.pageSize);
        } else if (task.status === 'error' || task.status === 'stop') {
          stopUpdatePolling();
          isUpdating.value = false;
          activeUpdatingTaskId.value = '';
          notification.error({
            message: assetText('assets.organizationAssetUpdateDidNotComplete'),
            description: task.error_msg || assetText('assets.backgroundDiscoveryFailedExistingAssetsHaveBeenPreserved'),
            duration: 5
          });
          fetchTaskDetail();
        }
      }
    } catch (e) {
      console.warn('轮询更新任务状态失败', e);
    }
  }, 3000);
};

watch(() => props.updatingTaskId, (newVal) => {
  if (newVal && !isUpdating.value) {
    startUpdatePolling(newVal);
  }
}, { immediate: true });

watch(isUpdating, () => {
  nextTick(() => {
    updateOsintHeight();
  });
});

const osintControlRef = ref(null);
const isAdvancedFilterOpen = ref(true);
const osintControlHeight = ref(120);
const scrollContainer = ref(null);
let osintResizeObserver = null;

const updateOsintHeight = () => {
  if (osintControlRef.value && typeof osintControlRef.value.getBoundingClientRect === 'function') {
    const rect = osintControlRef.value.getBoundingClientRect();
    if (rect.height > 0) {
      osintControlHeight.value = Math.round(rect.height);
    }
  }
};

const totalOsintOffsetHeader = computed(() => {
  return (props.stickyTopOffset || 0) + osintControlHeight.value;
});

const osintStickyConfig = computed(() => {
  if (!scrollContainer.value) return false;
  return {
    offsetHeader: totalOsintOffsetHeader.value,
    offsetScroll: 0,
    getContainer: () => scrollContainer.value
  };
});

onMounted(() => {
  scrollContainer.value = document.querySelector('.ant-layout-content');
  osintResizeObserver = new ResizeObserver(updateOsintHeight);
  if (osintControlRef.value) {
    osintResizeObserver.observe(osintControlRef.value);
  }
  updateOsintHeight();
});

onUnmounted(() => {
  stopLogPolling();
  stopUpdatePolling();
  if (osintResizeObserver) osintResizeObserver.disconnect();
});

const rawDrawerVisible = ref(false);
const currentRawRecord = ref({});

const openRawDrawer = (record) => {
  currentRawRecord.value = record;
  rawDrawerVisible.value = true;
};

const handleCopyText = async (text) => {
  const ok = await copyText(text);
  if (ok) message.success(assetText('assets.copiedLabel') + text);
};

const activeTab = ref('web');
const loading = ref(false);
const exportLoading = ref(false);
const refreshLoading = ref(false);
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

const taskRecord = ref({});
const taskName = ref('');
const taskTarget = ref('');
const taskType = ref('icp');
const taskStatus = ref('');
const hasIncrement = ref(false);

const queryCounts = reactive({
  web: 0,
  app: 0,
  mapp: 0,
  wechat: 0,
  weibo: 0,
  kapp: 0,
  invest: 0,
});

const displayName = computed(() => {
  return props.enterpriseName || (taskName.value && !taskName.value.includes('TYC_') ? taskName.value : '') || (taskTarget.value && !taskTarget.value.startsWith('TYC_') ? taskTarget.value : '') || taskName.value || assetText('assets.enterpriseAssetProfile');
});

const taskTypeLabel = computed(() => {
  if (taskType.value === 'tyc') return assetText('tasks.combinedSources');
  if (taskType.value === 'icp') return assetText('tasks.officialIcpRecordsLabel');
  return assetText('tasks.enterpriseOsint');
});

const taskStatusLabel = computed(() => {
  return formatTaskStatus(taskStatus.value);
});

const taskStatusColor = computed(() => {
  return formatTaskStatusColor(taskStatus.value);
});

const syncModalVisible = ref(false);
const selectedWebRowKeys = ref([]);
const selectedWebDomains = ref([]);

// 资产组当前已纳管域名集合 & 任务 Web 域名（后端单次返回上限 5000 条）
const managedDomainSet = ref(new Set());
const allTaskWebDomains = ref([]);
const expandingScopeLoading = ref(false);

const fetchManagedDomains = async () => {
  if (!props.scopeId) {
    managedDomainSet.value = new Set();
    return;
  }
  try {
    const res = await request.get('/asset_scope/', { params: { _id: props.scopeId } });
    if (res.code === 200 && res.items && res.items.length > 0) {
      const scopeItem = res.items[0];
      const domains = scopeItem.domain_array || (scopeItem.scope ? scopeItem.scope.split(',').map(s => s.trim().toLowerCase()).filter(Boolean) : []);
      managedDomainSet.value = new Set(domains.map(d => String(d).trim().toLowerCase()));
    }
  } catch (e) {
    console.error('获取资产组已纳管域名失败', e);
  }
};

const fetchAllTaskWebDomains = async () => {
  if (!props.taskId) {
    allTaskWebDomains.value = [];
    return;
  }
  try {
    const res = await request.get('/icp/asset', { params: { task_id: props.taskId, query_type: 'web', size: 5000 } });
    if (res.code === 200 && res.items) {
      const set = new Set();
      res.items.forEach(item => {
        const d = (item.domain || item.ym || '').trim().toLowerCase();
        if (d) set.add(d);
      });
      allTaskWebDomains.value = Array.from(set);
    }
  } catch (e) {
    console.error('获取任务域名列表失败', e);
  }
};

const untrackedWebDomains = computed(() => {
  if (!props.scopeId || allTaskWebDomains.value.length === 0) return [];
  return allTaskWebDomains.value.filter(d => !managedDomainSet.value.has(d.toLowerCase()));
});

const isDomainManaged = (record) => {
  if (!props.scopeId) return false;
  const d = (record.domain || record.ym || '').trim().toLowerCase();
  return managedDomainSet.value.has(d);
};

const onWebSelectChange = (keys, rows) => {
  selectedWebRowKeys.value = keys;
  const domains = [];
  rows.forEach(r => {
    const d = r.domain || r.ym;
    if (d && typeof d === 'string') domains.push(d.trim());
  });
  selectedWebDomains.value = domains;
};

const clearWebSelection = () => {
  selectedWebRowKeys.value = [];
  selectedWebDomains.value = [];
};

const handleBatchCopyDomains = async () => {
  if (!selectedWebDomains.value.length) return;
  const text = selectedWebDomains.value.join('\n');
  const ok = await copyText(text);
  if (ok) message.success(assetText('assets.domainsCopiedToClipboardCount', { count: selectedWebDomains.value.length }));
};

const openSyncModalWithSelected = () => {
  syncModalVisible.value = true;
};

const handleSyncSuccess = async (res) => {
  fetchTaskStatistic();
  await fetchManagedDomains();
  await fetchAllTaskWebDomains();
  emit('synced', res);
};

const handleOneClickExpandScope = async () => {
  if (!props.scopeId || !props.taskId) return;
  if (untrackedWebDomains.value.length === 0) {
    message.info(assetText('assets.allRegisteredDomainsForThisOrganizationAreAlready'));
    return;
  }
  expandingScopeLoading.value = true;
  try {
    const payload = {
      mode: 'existing',
      scope_id: props.scopeId,
      selected_domains: untrackedWebDomains.value,
      auto_scan: false
    };
    const res = await request.post(`/icp/sync/${props.taskId}`, payload);
    if (res && res.code === 200) {
      // 以后端实际入库数为准；缺失该字段时如实说明，不将提交数当作成功数展示
      const inserted = res.data?.insert_count;
      if (Number.isInteger(inserted)) {
        message.success(assetText('assets.newDomainsAddedToThisAssetGroupCount', { count: inserted }));
      } else {
        message.success(assetText('assets.domainAdditionsRequestedCountRefreshTheListTo', { count: untrackedWebDomains.value.length }));
      }
      await fetchManagedDomains();
      await fetchAllTaskWebDomains();
      emit('synced', res);
    } else {
      message.error(res?.message || assetText('assets.failedToAddDomainsToAssetGroup'));
    }
  } catch (err) {
    console.error('扩充资产组失败', err);
    message.error(assetText('assets.networkRequestFailed'));
  } finally {
    expandingScopeLoading.value = false;
  }
};

const handleExpandSelectedToScope = async () => {
  if (!props.scopeId || !props.taskId) return;
  if (selectedWebDomains.value.length === 0) {
    message.warning(assetText('assets.selectAtLeastOneDomain'));
    return;
  }
  expandingScopeLoading.value = true;
  try {
    const payload = {
      mode: 'existing',
      scope_id: props.scopeId,
      selected_domains: selectedWebDomains.value,
      auto_scan: false
    };
    const res = await request.post(`/icp/sync/${props.taskId}`, payload);
    if (res && res.code === 200) {
      message.success(assetText('assets.selectedDomainsAddedToThisAssetGroup'));
      clearWebSelection();
      await fetchManagedDomains();
      await fetchAllTaskWebDomains();
      emit('synced', res);
    } else {
      message.error(res?.message || assetText('assets.failedToAddDomainsToAssetGroup'));
    }
  } catch (err) {
    console.error('扩充资产组失败', err);
    message.error(assetText('assets.networkRequestFailed'));
  } finally {
    expandingScopeLoading.value = false;
  }
};

const handleRefreshTask = async () => {
  if (!props.taskId || isUpdating.value) return;
  refreshLoading.value = true;
  try {
    const res = await request.get(`/icp/restart/${props.taskId}`);
    if (res.code === 200) {
      message.success(assetText('assets.organizationAssetUpdateStartedDiscoveryAndComparisonAre'));
      const newTaskId = res.data?.task_id || res.data?.updating_task_id;
      if (newTaskId) {
        startUpdatePolling(newTaskId);
      }
    } else {
      message.error(res.message || assetText('assets.failedToStartUpdate'));
    }
  } catch (err) {
    message.error(assetText('assets.networkRequestFailed'));
  } finally {
    refreshLoading.value = false;
  }
};

/* ================= 维度列表与精选筛选项配置 (osintTabConfig) ================= */
const osintTabList = [
  { key: 'web', get label() { return assetText('tasks.websiteIcpRecords'); } },
  { key: 'app', get label() { return assetText('assets.mobileApps'); } },
  { key: 'mapp', get label() { return assetText('tasks.wechatMiniPrograms'); } },
  { key: 'wechat', get label() { return assetText('tasks.wechatOfficialAccounts'); } },
  { key: 'weibo', get label() { return assetText('tasks.corporateWeiboAccounts'); } },
  { key: 'kapp', get label() { return assetText('tasks.quickApps'); } },
  { key: 'invest', get label() { return assetText('tasks.investments'); } }
];

const osintTabConfig = reactive({
  web: {
    get label() { return assetText('tasks.websiteIcpRecords'); },
    searchFields: [
      { get label() { return assetText('tasks.domains'); }, key: 'domain' },
      { get label() { return assetText('tasks.websiteName'); }, key: 'serviceName' },
      { get label() { return assetText('assets.organization'); }, key: 'unitName' },
      { get label() { return assetText('tasks.icpNumber'); }, key: 'serviceLicence' },
      { get label() { return assetText('tasks.organizationType'); }, key: 'companyType' }
    ]
  },
  app: {
    get label() { return assetText('assets.mobileApps'); },
    searchFields: [
      { get label() { return assetText('tasks.appName'); }, key: 'name' },
      { get label() { return assetText('assets.organization'); }, key: 'unitName' },
      { get label() { return assetText('tasks.icpNumber'); }, key: 'serviceLicence' },
      { get label() { return assetText('assets.category'); }, key: 'category' }
    ]
  },
  mapp: {
    get label() { return assetText('tasks.wechatMiniPrograms'); },
    searchFields: [
      { get label() { return assetText('assets.miniProgramName'); }, key: 'name' },
      { get label() { return assetText('assets.organization'); }, key: 'unitName' },
      { get label() { return assetText('tasks.icpNumber'); }, key: 'serviceLicence' },
      { get label() { return assetText('assets.category'); }, key: 'category' }
    ]
  },
  wechat: {
    get label() { return assetText('tasks.wechatOfficialAccounts'); },
    searchFields: [
      { get label() { return assetText('assets.officialAccountName'); }, key: 'name' },
      { get label() { return assetText('tasks.wechatId'); }, key: 'wechatId' },
      { get label() { return assetText('assets.verifiedOrganization'); }, key: 'unitName' }
    ]
  },
  weibo: {
    get label() { return assetText('tasks.corporateWeiboAccounts'); },
    searchFields: [
      { get label() { return assetText('assets.weiboName'); }, key: 'name' },
      { get label() { return assetText('assets.verifiedProfile'); }, key: 'brief' }
    ]
  },
  kapp: {
    get label() { return assetText('tasks.quickApps'); },
    searchFields: [
      { get label() { return assetText('assets.quickAppName'); }, key: 'name' },
      { get label() { return assetText('assets.organization'); }, key: 'unitName' },
      { get label() { return assetText('tasks.icpNumber'); }, key: 'serviceLicence' }
    ]
  },
  invest: {
    get label() { return assetText('tasks.investments'); },
    searchFields: [
      { get label() { return assetText('assets.companyName'); }, key: 'name' },
      { get label() { return assetText('tasks.legalRepresentative'); }, key: 'legalPerson' },
      { get label() { return assetText('assets.companyStatus'); }, key: 'status' },
      { get label() { return assetText('tasks.ownershipShare'); }, key: 'percent', hasOperatorSelect: true, operator: 'eq', operators: ['eq', 'gt', 'lt'] },
      { get label() { return assetText('assets.investmentAmount'); }, key: 'amount', hasOperatorSelect: true, operator: 'eq', operators: ['eq', 'gt', 'lt'] }
    ]
  }
});

const currentSearchFields = computed(() => {
  return osintTabConfig[activeTab.value]?.searchFields || [];
});

const currentTabLabel = computed(() => {
  if (activeTab.value === 'log') return assetText('assets.discoveryLogs');
  return osintTabConfig[activeTab.value]?.label || assetText('tasks.assets');
});

const searchForm = reactive({});

const activeFilterCount = computed(() => {
  let count = 0;
  for (const k in searchForm) {
    if (searchForm[k] !== undefined && searchForm[k] !== null && searchForm[k] !== '') {
      if (Array.isArray(searchForm[k]) && searchForm[k].length === 0) continue;
      count++;
    }
  }
  return count;
});

const columnConfigs = {
  web: [
    { get title() { return assetText('tasks.no'); }, key: 'index', width: 55, align: 'center' },
    { get title() { return assetText('tasks.domains'); }, dataIndex: 'domain', key: 'domain', width: 170 },
    { get title() { return assetText('assets.managementStatus'); }, key: 'managedStatus', width: 95, align: 'center' },
    { get title() { return assetText('tasks.websiteName'); }, dataIndex: 'serviceName', key: 'serviceName', width: 160, ellipsis: true },
    { get title() { return assetText('assets.organization'); }, dataIndex: 'unitName', key: 'unitName', ellipsis: true },
    { get title() { return assetText('tasks.organizationType'); }, dataIndex: 'companyType', key: 'companyType', width: 90, align: 'center' },
    { get title() { return assetText('tasks.icpNumber'); }, dataIndex: 'serviceLicence', key: 'serviceLicence', width: 170 },
    { get title() { return assetText('assets.homeUrl'); }, dataIndex: 'homeUrl', key: 'homeUrl', width: 170, ellipsis: true },
    { get title() { return assetText('assets.updatedAtLabel'); }, dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 120, align: 'center' },
    { get title() { return assetText('assets.rawData'); }, key: 'raw', width: 55, align: 'center' }
  ],
  app: [
    { get title() { return assetText('tasks.no'); }, key: 'index', width: 55, align: 'center' },
    { get title() { return assetText('tasks.icon'); }, dataIndex: 'icon', key: 'icon', width: 65, align: 'center' },
    { get title() { return assetText('tasks.appName'); }, dataIndex: 'name', key: 'name', width: 160 },
    { get title() { return assetText('assets.category'); }, dataIndex: 'category', key: 'category', width: 100 },
    { get title() { return assetText('tasks.icpNumber'); }, dataIndex: 'serviceLicence', key: 'serviceLicence', width: 160 },
    { get title() { return assetText('assets.organization'); }, dataIndex: 'unitName', key: 'unitName', ellipsis: true },
    { get title() { return assetText('tasks.description'); }, dataIndex: 'brief', key: 'brief', ellipsis: true },
    { get title() { return assetText('assets.version'); }, dataIndex: 'version', key: 'version', width: 90, align: 'center' },
    { get title() { return assetText('assets.updatedAtLabel'); }, dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 120, align: 'center' },
    { get title() { return assetText('assets.rawData'); }, key: 'raw', width: 55, align: 'center' }
  ],
  mapp: [
    { get title() { return assetText('tasks.no'); }, key: 'index', width: 55, align: 'center' },
    { get title() { return assetText('tasks.icon'); }, dataIndex: 'icon', key: 'icon', width: 65, align: 'center' },
    { get title() { return assetText('tasks.miniProgramName'); }, dataIndex: 'name', key: 'name', width: 160 },
    { get title() { return assetText('tasks.icpNumber'); }, dataIndex: 'serviceLicence', key: 'serviceLicence', width: 170 },
    { get title() { return assetText('assets.organization'); }, dataIndex: 'unitName', key: 'unitName', ellipsis: true },
    { get title() { return assetText('assets.category'); }, dataIndex: 'category', key: 'category', width: 100 },
    { get title() { return assetText('assets.description'); }, dataIndex: 'brief', key: 'brief', ellipsis: true },
    { get title() { return assetText('assets.updatedAtLabel'); }, dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 120, align: 'center' },
    { get title() { return assetText('assets.rawData'); }, key: 'raw', width: 55, align: 'center' }
  ],
  wechat: [
    { get title() { return assetText('tasks.no'); }, key: 'index', width: 55, align: 'center' },
    { get title() { return assetText('tasks.avatar'); }, dataIndex: 'icon', key: 'icon', width: 65, align: 'center' },
    { get title() { return assetText('tasks.officialAccountName'); }, dataIndex: 'name', key: 'name', width: 160 },
    { get title() { return assetText('tasks.wechatId'); }, dataIndex: 'wechatId', key: 'wechatId', width: 140 },
    { get title() { return assetText('assets.qrCode'); }, key: 'qrcode', width: 80, align: 'center' },
    { get title() { return assetText('assets.features'); }, dataIndex: 'brief', key: 'brief', ellipsis: true },
    { get title() { return assetText('assets.verifiedOrganization'); }, dataIndex: 'unitName', key: 'unitName', ellipsis: true },
    { get title() { return assetText('assets.rawData'); }, key: 'raw', width: 55, align: 'center' }
  ],
  weibo: [
    { get title() { return assetText('tasks.no'); }, key: 'index', width: 55, align: 'center' },
    { get title() { return assetText('tasks.avatar'); }, dataIndex: 'icon', key: 'icon', width: 65, align: 'center' },
    { get title() { return assetText('assets.weiboName'); }, dataIndex: 'name', key: 'name', width: 160 },
    { get title() { return assetText('assets.verificationDescription'); }, dataIndex: 'brief', key: 'brief', ellipsis: true },
    { get title() { return assetText('assets.weiboProfile'); }, key: 'href', width: 160 },
    { get title() { return assetText('assets.followers'); }, dataIndex: 'fans', key: 'fans', width: 100, align: 'center' },
    { get title() { return assetText('assets.rawData'); }, key: 'raw', width: 55, align: 'center' }
  ],
  kapp: [
    { get title() { return assetText('tasks.no'); }, key: 'index', width: 55, align: 'center' },
    { get title() { return assetText('tasks.icon'); }, dataIndex: 'icon', key: 'icon', width: 65, align: 'center' },
    { get title() { return assetText('assets.quickAppName'); }, dataIndex: 'name', key: 'name', width: 160 },
    { get title() { return assetText('tasks.icpNumber'); }, dataIndex: 'serviceLicence', key: 'serviceLicence', width: 170 },
    { get title() { return assetText('assets.organization'); }, dataIndex: 'unitName', key: 'unitName', ellipsis: true },
    { get title() { return assetText('assets.category'); }, dataIndex: 'category', key: 'category', width: 100 },
    { get title() { return assetText('assets.updatedAtLabel'); }, dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 120, align: 'center' },
    { get title() { return assetText('assets.rawData'); }, key: 'raw', width: 55, align: 'center' }
  ],
  invest: [
    { get title() { return assetText('tasks.no'); }, key: 'index', width: 55, align: 'center' },
    { get title() { return assetText('assets.investeeCompany'); }, dataIndex: 'name', key: 'name', ellipsis: true },
    { get title() { return assetText('tasks.legalRepresentative'); }, dataIndex: 'legalPerson', key: 'legalPerson', width: 110 },
    { get title() { return assetText('tasks.ownershipShare'); }, dataIndex: 'percent', key: 'percent', width: 100, align: 'center' },
    { get title() { return assetText('assets.investmentAmount'); }, dataIndex: 'amount', key: 'amount', width: 140 },
    { get title() { return assetText('assets.companyStatus'); }, dataIndex: 'status', key: 'status', width: 100, align: 'center' },
    { get title() { return assetText('assets.region'); }, key: 'region', width: 130 },
    { get title() { return assetText('assets.establishedOn'); }, key: 'estiblishTime', width: 120, align: 'center' },
    { get title() { return assetText('assets.rawData'); }, key: 'raw', width: 55, align: 'center' }
  ]
};

const dynamicColumns = computed(() => {
  return columnConfigs[activeTab.value] || columnConfigs.web;
});

const assetList = ref([]);
const syslogList = ref([]);
const terminalContainer = ref(null);
const logLoading = ref(false);
let logTimer = null;

const getAssetIcon = (record) => {
  return record.icon || record.titleImgURL || record.codeImg || record.ico || record.productLogo || '';
};

const getAssetHomeUrl = (record) => {
  if (record.homeUrl) return record.homeUrl;
  if (record.webSite) {
    if (Array.isArray(record.webSite) && record.webSite.length > 0) return record.webSite[0];
    if (typeof record.webSite === 'string') return record.webSite;
  }
  return '';
};

const formatDate = (val) => {
  if (!val) return '-';
  if (typeof val === 'number') {
    const d = new Date(val);
    if (!isNaN(d.getTime())) {
      return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
    }
  }
  return String(val);
};

const fetchTaskDetail = async () => {
  if (!props.taskId) return;
  try {
    const res = await request.get(`/icp/task`, { params: { _id: props.taskId } });
    if (res.code === 200 && res.items && res.items.length > 0) {
      const task = res.items[0];
      taskRecord.value = task;
      taskName.value = task.name || '';
      taskTarget.value = task.target || '';
      taskType.value = task.task_type || 'icp';
      taskStatus.value = task.status || '';
      hasIncrement.value = !!task.has_increment;
      const stats = task.statistic || {};
      queryCounts.web = stats.web_cnt || 0;
      queryCounts.app = stats.app_cnt || 0;
      queryCounts.mapp = stats.mapp_cnt || 0;
      queryCounts.wechat = stats.wechat_cnt || 0;
      queryCounts.weibo = stats.weibo_cnt || 0;
      queryCounts.kapp = stats.kapp_cnt || 0;
      queryCounts.invest = stats.invest_cnt || 0;

      if (task.status === 'done' || task.status === 'error') {
        stopLogPolling();
      }

      emit('taskLoaded', {
        task,
        taskName: taskName.value,
        taskTarget: taskTarget.value,
        taskType: taskType.value,
        taskTypeLabel: taskTypeLabel.value,
        taskStatus: taskStatus.value,
        taskStatusLabel: taskStatusLabel.value,
        taskStatusColor: taskStatusColor.value,
        hasIncrement: hasIncrement.value,
        queryCounts: { ...queryCounts },
        totalCount: Object.values(queryCounts).reduce((a, b) => a + (Number(b) || 0), 0)
      });
    }
  } catch (err) {
    console.error('获取任务详情失败', err);
  }
};

const fetchTaskStatistic = async () => {
  fetchTaskDetail();
};

const fetchAssets = async (page = 1, size = 10) => {
  if (!props.taskId || activeTab.value === 'log') return;
  loading.value = true;
  try {
    const params = {
      task_id: props.taskId,
      query_type: activeTab.value,
      page,
      size
    };
    const fields = currentSearchFields.value;
    for (const f of fields) {
      const val = searchForm[f.key];
      if (val !== undefined && val !== null && val !== '') {
        const trimmed = typeof val === 'string' ? val.trim() : val;
        if (f.hasOperatorSelect) {
          const numKey = `${f.key}_num`;
          const op = f.operator || 'eq';
          const numVal = parseFloat(trimmed);
          if (!isNaN(numVal)) {
            if (op === 'gt' || op === '>') {
              params[`${numKey}__ngt`] = numVal;
            } else if (op === 'lt' || op === '<') {
              params[`${numKey}__nlt`] = numVal;
            } else {
              params[numKey] = numVal;
            }
          } else {
            params[f.key] = trimmed;
          }
        } else {
          params[f.key] = trimmed;
        }
      }
    }
    const res = await request.get('/icp/asset', { params });
    if (res.code === 200) {
      assetList.value = res.items || [];
      pagination.total = res.total || 0;
      pagination.current = page;
      pagination.pageSize = size;
    }
  } catch (err) {
    console.error('获取资产列表失败', err);
  } finally {
    loading.value = false;
  }
};

const fetchLogs = async (isManual = false) => {
  if (!props.taskId) return;
  if (isManual) logLoading.value = true;
  try {
    let items = [];
    try {
      const res = await request.get(`/icp/task/log/${props.taskId}`);
      if (res && res.code === 200 && Array.isArray(res.items)) {
        items = res.items;
      }
    } catch (e) {
      console.warn('Fallback to /syslog for task logs', e);
      const res = await request.get('/syslog/', {
        params: { task_id: props.taskId, size: 500, order: 'create_time' }
      });
      if (res && res.code === 200 && Array.isArray(res.items)) {
        items = res.items;
      }
    }

    items.sort((a, b) => (a.create_time || '').localeCompare(b.create_time || ''));
    syslogList.value = items;

    await nextTick();
    if (terminalContainer.value) {
      terminalContainer.value.scrollTop = terminalContainer.value.scrollHeight;
    }
  } catch (err) {
    console.error('获取日志失败', err);
  } finally {
    if (isManual) logLoading.value = false;
  }
};

const startLogPolling = () => {
  stopLogPolling();
  if (activeTab.value === 'log' && (taskRecord.value.status === 'running' || taskRecord.value.status === 'waiting')) {
    logTimer = setInterval(() => {
      fetchLogs(false);
      fetchTaskDetail();
    }, 3000);
  }
};

const stopLogPolling = () => {
  if (logTimer) {
    clearInterval(logTimer);
    logTimer = null;
  }
};

const onTabChange = (key) => {
  pagination.current = 1;
  selectedWebRowKeys.value = [];
  selectedWebDomains.value = [];
  for (const k in searchForm) {
    searchForm[k] = undefined;
  }
  nextTick(() => { updateOsintHeight(); });
  if (key === 'log') {
    fetchLogs(true);
    startLogPolling();
  } else {
    stopLogPolling();
    fetchAssets(1, pagination.pageSize);
  }
};

const onSearch = () => fetchAssets(1, pagination.pageSize);

const resetSearch = () => {
  for (const k in searchForm) {
    searchForm[k] = undefined;
  }
  const fields = currentSearchFields.value;
  fields.forEach(f => {
    if (f.hasOperatorSelect && f.operators && f.operators.length > 0) {
      f.operator = f.operators[0];
    }
  });
  onSearch();
};

const handlePaginationChange = (page, pageSize) => {
  if (pageSize && pageSize !== pagination.pageSize) {
    pagination.pageSize = pageSize;
  }
  if (pagination.pageSize !== globalPageSize.value) {
    globalPageSize.value = pagination.pageSize;
  }
  fetchAssets(page, pageSize);
};

watch(globalPageSize, (newSize) => {
  if (pagination.pageSize !== newSize) {
    pagination.pageSize = newSize;
    if (props.taskId && activeTab.value !== 'log') {
      fetchAssets(1, newSize);
    }
  }
});

const handleExport = async () => {
  if (!props.taskId) return;
  exportLoading.value = true;
  try {
    const res = await request.get(`/icp/export/${props.taskId}`, {
      params: { query_type: activeTab.value },
      responseType: 'blob'
    });
    const blob = new Blob([res.data || res]);
    const url = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `${displayName.value || taskTarget.value || 'osint'}_${activeTab.value}.xlsx`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    message.success(assetText('tasks.exportCompleted'));
  } catch (err) {
    message.error(assetText('tasks.exportFailed'));
  } finally {
    exportLoading.value = false;
  }
};

watch(() => props.taskId, (newVal) => {
  if (newVal) {
    fetchTaskDetail();
    fetchAllTaskWebDomains();
    if (props.scopeId) fetchManagedDomains();
    if (activeTab.value === 'log') {
      fetchLogs(true);
      startLogPolling();
    } else {
      stopLogPolling();
      fetchAssets(pagination.current, pagination.pageSize);
    }
  }
}, { immediate: true });

watch(() => props.scopeId, (newVal) => {
  if (newVal) {
    fetchManagedDomains();
  }
}, { immediate: true });

defineExpose({
  handleRefreshTask,
  refreshLoading,
  isUpdating,
  activeUpdatingTaskId,
  queryCounts,
  taskRecord,
  fetchTaskDetail
});
</script>

<style scoped>
.filter-field-label.filter-field-label-wide { width: 112px; white-space: normal; overflow: visible; text-overflow: clip; }
.asset-increment-badge :deep(.ant-badge-count) { background-color: #52c41a; font-size: 10px; }

/* ================= 测绘更新中顶部平滑提示条 ================= */
.osint-updating-banner {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 16px;
  background: var(--arl-theme-soft-bg);
  border-bottom: 1px solid var(--arl-theme-soft-border);
  border-top-left-radius: 8px;
  border-top-right-radius: 8px;
  font-size: 13px;
  color: var(--arl-theme-color);
}

.updating-banner-content {
  display: flex;
  align-items: center;
  gap: 8px;
}

.updating-spin-icon {
  font-size: 14px;
}

.updating-banner-text {
  color: var(--arl-text-color, #1f2225);
}

.updating-banner-tag {
  margin: 0;
}

/* ================= OSINT 吸顶控制区 (与 ASM 完全对齐) ================= */
.osint-sticky-control-box {
  position: sticky;
  z-index: 11;
  background: var(--arl-bg-sticky);
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border-radius: 8px;
  border: 1px solid var(--arl-border-color);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.06);
  margin-bottom: 8px;
  transition: box-shadow 0.2s ease;
}

.osint-tabs-nav {
  padding: 6px 12px 0 12px;
  margin-bottom: 0 !important;
}

.osint-tabs-nav :deep(.ant-tabs-nav) {
  margin-bottom: 0 !important;
}

.osint-tab-item {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  font-size: 12px;
}

.osint-tab-badge {
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

.osint-tab-badge.has-data {
  background: color-mix(in srgb, var(--arl-theme-color) 12%, transparent);
  color: var(--arl-theme-color);
  font-weight: 600;
}

.log-tab-pill {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  color: #13c2c2;
  font-weight: 600;
  font-size: 12px;
}

.log-pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #52c41a;
  animation: filter-dot-pulse 1.5s infinite;
}

/* 工具栏与平铺检索区 */
.osint-toolbar-container {
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

.osint-mini-tag {
  font-size: 10px;
  line-height: 16px;
  padding: 0 4px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}


.json-icon-btn {
  color: var(--arl-theme-color);
  padding: 0 4px;
  height: 24px;
  line-height: 24px;
  border-radius: 4px;
  transition: all 0.2s;
}
.json-icon-btn:hover {
  background: color-mix(in srgb, var(--arl-theme-color) 12%, transparent);
}

.fade-slide-enter-active,
.fade-slide-leave-active {
  transition: all 0.2s ease-in-out;
}
.fade-slide-enter-from,
.fade-slide-leave-to {
  opacity: 0;
  transform: translateY(-6px);
}

/* 现代化无纵线表格风格 */
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

.log-polling-hint {
  color: var(--arl-text-secondary);
  font-size: 12px;
}

/* 直接平铺的紧凑栅格筛选卡片 */
.osint-filter-card {
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

/* 操作符组合输入框 (如 等于/大于/小于) */
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
  width: 65px;
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

/* ================= 测绘日志卡片与终端 ================= */
.log-terminal-card {
  border: 1px solid var(--arl-border-color);
  border-radius: 8px;
  background: var(--arl-bg-white);
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.log-terminal-header {
  padding: 10px 16px;
  background: var(--arl-bg-light);
  border-bottom: 1px solid var(--arl-border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.log-terminal-body {
  background-color: var(--arl-terminal-bg);
  color: var(--arl-terminal-text);
  font-family: 'Fira Code', Consolas, Monaco, monospace;
  padding: 14px;
  height: 480px;
  overflow-y: auto;
  font-size: 12px;
  line-height: 1.6;
}

.log-terminal-line {
  margin-bottom: 4px;
  word-break: break-all;
  border-bottom: 1px dashed rgba(255, 255, 255, 0.08);
  padding-bottom: 2px;
}

.log-time {
  opacity: 0.65;
  margin-right: 8px;
}

.log-level {
  font-weight: 600;
  margin-right: 8px;
}
.log-level.error { color: #ff4d4f; }
.log-level.warning { color: #faad14; }
.log-level.info { color: #52c41a; }

.log-title {
  color: var(--arl-primary-light);
  margin-right: 8px;
}

.log-msg {
  color: var(--arl-terminal-text);
}

.log-empty {
  color: rgba(255, 255, 255, 0.45);
  font-style: italic;
}

.asset-small-label { font-size: 11px; }
.asset-action-hint { font-size: 12px; color: #8c8c8c; margin-top: 4px; display: block; }
.asset-clickable { cursor: pointer; }
.asset-selection-number { color: var(--arl-theme-color); margin: 0 4px; }
.asset-toolbar-heading { font-weight: 600; font-size: 13px; }
.asset-secondary-caption { color: var(--arl-text-secondary); font-size: 12px; }
</style>
