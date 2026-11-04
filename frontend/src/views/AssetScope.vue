<template>
  <div style="min-height: calc(100vh - 96px); background-color: var(--arl-bg-layout); position: relative;">
    <!-- 隐形定位锚点 (用于精准定位 fixed 侧边栏左边界) -->
    <div ref="sidebarAnchorRef" style="position: absolute; top: 0; left: 0; width: 0; height: 0; pointer-events: none;"></div>

    <!-- 左侧集团分组固定侧边栏 (Fixed 视口绝对锁定，绝不随页面滚动) -->
    <div
      class="asset-group-sidebar"
      :style="{
        position: 'fixed',
        top: '80px',
        bottom: '16px',
        left: (sidebarLeft || 186) + 'px',
        width: isSidebarCollapsed ? '0px' : '240px',
        overflow: 'hidden',
        opacity: isSidebarCollapsed ? 0 : 1,
        transition: 'width 0.25s, opacity 0.25s, left 0.2s',
        background: 'var(--arl-bg-white)',
        borderRight: isSidebarCollapsed ? 'none' : '1px solid var(--arl-border-color)',
        display: 'flex',
        flexDirection: 'column',
        zIndex: 15,
        boxShadow: isSidebarCollapsed ? 'none' : '2px 0 8px rgba(0,0,0,0.03)'
      }"
    >
      <div class="sidebar-header">
        <div style="display: flex; align-items: center; gap: 6px; min-width: 0;">
          <ApartmentOutlined style="font-size: 16px; color: var(--arl-theme-color); flex-shrink: 0;" />
          <span class="asset-sidebar-heading" style="white-space: nowrap;">{{ assetText('assets.organizationGroupCatalog') }}</span>
          <a-tooltip :title="assetText('assets.organizationGroupCatalogTooltip')" placement="right">
            <question-circle-outlined style="font-size: 13px; color: var(--arl-text-color); opacity: 0.45; cursor: pointer; flex-shrink: 0;" />
          </a-tooltip>
          <span class="sidebar-total-badge">{{ groupList.length }}</span>
        </div>
        <a-tooltip :title="assetText('assets.newOrganizationGroupWithLevel')">
          <a-button type="text" size="small" class="sidebar-add-btn" @click="openAddEnterpriseGroupModal">
            <plus-outlined />
          </a-button>
        </a-tooltip>
      </div>
      <div class="sidebar-search-container">
        <a-input v-model:value="groupSearchKey" :placeholder="assetText('assets.searchOrganizationGroups')" allowClear size="small">
          <template #prefix><search-outlined style="color: var(--arl-text-color); opacity: 0.35;" /></template>
        </a-input>
      </div>
      <div style="flex: 1; min-height: 0; overflow-y: auto; padding: 6px 0;">
        <a-menu
          mode="inline"
          :selectedKeys="['all', 'unassigned'].includes(activeGroupId) ? [activeGroupId] : []"
          @click="handleGroupSwitch"
          class="sidebar-group-menu"
          style="border-right: none;"
        >
          <a-menu-item key="all">
            <template #icon><appstore-outlined /></template>
            {{ assetText('assets.allAssetGroups') }}
          </a-menu-item>
          <a-menu-item key="unassigned">
            <template #icon><inbox-outlined /></template>
            {{ assetText('assets.ungrouped') }}
          </a-menu-item>
        </a-menu>

        <div class="sidebar-group-divider"></div>

        <!-- 无自定义集团时的轻量指引卡片 -->
        <div v-if="groupList.length === 0" style="margin: 12px 10px; padding: 10px; background: var(--arl-bg-light, rgba(0,0,0,0.02)); border: 1px dashed var(--arl-border-color); border-radius: 6px; font-size: 12px; line-height: 1.5; color: var(--arl-text-color); opacity: 0.8;">
          <div style="font-weight: 500; margin-bottom: 4px; display: flex; align-items: center; gap: 4px; color: var(--arl-theme-color);">
            <info-circle-outlined />
            <span>{{ assetText('assets.sidebarCatalogTipTitle') }}</span>
          </div>
          <div>{{ assetText('assets.sidebarCatalogTipDesc') }}</div>
        </div>

        <!-- 可拖拽自定义集团列表容器 -->
        <div ref="draggableGroupListRef" class="sidebar-group-draggable-list">
          <div
            v-for="group in filteredGroupList"
            :key="group._id"
            :data-id="group._id"
            class="group-nav-item"
            :class="{ 'group-nav-item-active': activeGroupId === group._id }"
            @click="handleGroupSwitch(group._id)"
          >
            <div style="display: flex; align-items: center; gap: 4px; flex: 1; min-width: 0;">
              <a-tooltip :title="groupSearchKey ? assetText('assets.sortingIsDisabledWhileFilteringSearchResults') : assetText('assets.dragToReorder')" placement="left" :mouseEnterDelay="0.4">
                <span
                  class="group-drag-handle"
                  :class="{ 'group-drag-handle-disabled': !!groupSearchKey }"
                  @click.stop
                >
                  <holder-outlined />
                </span>
              </a-tooltip>
              <span
                class="group-name-text"
                :title="group.name"
                style="overflow: hidden; text-overflow: ellipsis; white-space: nowrap; flex: 1; min-width: 0;"
              >
                {{ group.name }}
              </span>
            </div>
            <div style="display: flex; align-items: center; gap: 4px; flex-shrink: 0;">
              <span class="sidebar-scope-pill">
                {{ group.scope_count || 0 }}
              </span>
              <a-dropdown :trigger="['click']" :getPopupContainer="getBodyContainer">
                <span class="group-action-icon" @click.stop><more-outlined /></span>
                <template #overlay>
                  <a-menu @click="(e) => handleGroupAction(e, group)">
                    <a-menu-item key="edit">{{ assetText('assets.rename') }}</a-menu-item>
                    <a-menu-item key="delete" class="asset-danger">{{ assetText('tasks.delete') }}</a-menu-item>
                  </a-menu>
                </template>
              </a-dropdown>
            </div>
          </div>
        </div>

        <div v-if="groupSearchKey && filteredGroupList.length === 0" style="padding: 24px 16px; text-align: center; color: var(--arl-text-color); opacity: 0.5; font-size: 12px;">
          <div>{{ assetText('assets.noMatchingOrganizationGroups') }}</div>
          <a-button type="link" size="small" class="asset-clear-search" @click="groupSearchKey = ''">{{ assetText('assets.clearSearch') }}</a-button>
        </div>
      </div>
    </div>

    <!-- 侧边栏折叠把手（展开态：垂直居中悬浮在 Fixed 侧边栏右边缘） -->
    <div
      v-if="!isSidebarCollapsed"
      @click="isSidebarCollapsed = true"
      :style="{
        position: 'fixed',
        top: '50%',
        transform: 'translateY(-50%)',
        left: ((sidebarLeft || 186) + 240) + 'px',
        width: '14px',
        height: '44px',
        background: 'var(--arl-bg-white)',
        border: '1px solid var(--arl-border-color)',
        borderLeft: 'none',
        borderRadius: '0 6px 6px 0',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        cursor: 'pointer',
        zIndex: 16,
        boxShadow: '2px 0 8px rgba(0,0,0,0.06)',
        transition: 'left 0.2s ease, background 0.2s'
      }"
      class="sidebar-collapse-handle"
      :title="assetText('assets.collapseOrganizationGroups')"
    >
      <left-outlined style="font-size: 10px; color: var(--arl-text-color); opacity: 0.65;" />
    </div>

    <!-- 侧边栏展开把手（收起态：细条垂直居中，高度撑满） -->
    <div
      v-if="isSidebarCollapsed"
      @click="isSidebarCollapsed = false"
      :style="{
        position: 'fixed',
        top: '80px',
        bottom: '16px',
        left: (sidebarLeft || 186) + 'px',
        width: '26px',
        background: 'var(--arl-bg-white)',
        borderRight: '1px solid var(--arl-border-color)',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: '8px',
        cursor: 'pointer',
        transition: 'all 0.2s ease',
        zIndex: 15
      }"
      class="sidebar-expand-handle"
      :title="assetText('assets.expandOrganizationGroups')"
    >
      <right-outlined style="font-size: 11px; color: var(--arl-text-color); opacity: 0.65;" />
      <span class="asset-sidebar-handle">{{ assetText('assets.organizationGroups') }}</span>
    </div>

    <!-- 右侧主工作区 (现代化一体卡片容器) -->
    <div
      :style="{
        marginLeft: isSidebarCollapsed ? '34px' : '248px',
        transition: 'margin-left 0.25s ease',
        padding: '16px 20px',
        minWidth: 0,
        position: 'relative'
      }"
    >
      <div class="arl-scope-main-card">
        <!-- 头部吸附操作区 (含标题、全局搜索与批量操作) -->
        <div ref="actionBarRef" class="arl-scope-action-bar">

          <!-- 顶行：标题与快捷操作按钮 -->
          <div class="scope-header-top">
            <div class="scope-title-area">
              <a-breadcrumb v-if="isSidebarCollapsed">
                <a-breadcrumb-item>{{ assetText('assets.organizationGroupCatalog') }}</a-breadcrumb-item>
                <a-breadcrumb-item>
                  <a-dropdown :getPopupContainer="getBodyContainer">
                    <span class="group-switch-trigger">
                      {{ currentGroupName }} <down-outlined style="font-size: 10px;" />
                    </span>
                    <template #overlay>
                      <a-menu :selectedKeys="[activeGroupId]" @click="handleGroupSwitch">
                        <a-menu-item key="all">{{ assetText('assets.allAssetGroups') }}</a-menu-item>
                        <a-menu-item key="unassigned">{{ assetText('assets.ungrouped') }}</a-menu-item>
                        <a-menu-divider />
                        <a-menu-item v-for="g in groupList" :key="g._id">{{ g.name }}</a-menu-item>
                      </a-menu>
                    </template>
                  </a-dropdown>
                </a-breadcrumb-item>
                <a-breadcrumb-item v-if="!['all', 'unassigned'].includes(activeGroupId)">{{ assetText('assets.subordinateAssetGroups') }}</a-breadcrumb-item>
              </a-breadcrumb>
              <div v-else class="scope-title-wrap">
                <template v-if="activeGroupId === 'all'">
                  <span class="scope-title-text">{{ assetText('assets.allAssetGroups') }}</span>
                  <span class="scope-total-tag" v-if="pagination.total !== undefined">{{ assetText('assets.assetGroupCount', { count: pagination.total }) }}</span>
                </template>
                <template v-else-if="activeGroupId === 'unassigned'">
                  <span class="scope-title-text">{{ assetText('assets.ungroupedAssetGroups') }}</span>
                  <span class="scope-total-tag" v-if="pagination.total !== undefined">{{ assetText('assets.assetGroupCount', { count: pagination.total }) }}</span>
                </template>
                <template v-else>
                  <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                    <a-tag color="blue" style="font-size: 12px; margin-right: 0; padding: 2px 8px;">
                      <apartment-outlined style="margin-right: 3px;" />{{ assetText('assets.organizationGroupLevel') }}
                    </a-tag>
                    <span class="scope-title-text">{{ currentGroupName }}</span>
                    <span style="color: var(--arl-text-color); opacity: 0.35; font-size: 14px;">/</span>
                    <span style="font-size: 14px; font-weight: 500; color: var(--arl-text-color); opacity: 0.85;">{{ assetText('assets.subordinateAssetGroups') }}</span>
                    <span class="scope-total-tag" v-if="pagination.total !== undefined">{{ assetText('assets.assetGroupCount', { count: pagination.total }) }}</span>
                  </div>
                </template>
              </div>
            </div>
            <div class="scope-header-actions" style="display: flex; align-items: center; gap: 12px;">
              <!-- 后台正在自动建组中的任务轻量状态标签 -->
              <a-popover v-if="runningReconTasks.length > 0" placement="bottomRight">
                <template #title>
                  <div style="display: flex; justify-content: space-between; align-items: center;">
                    <span class="asset-bold-label">{{ assetText('assets.enterpriseQueueCount', { count: runningReconTasks.length }) }}</span>
                    <a-button type="link" size="small" style="padding: 0; font-size: 11px; height: auto;" @click="clearAllRunningReconTasks">
                      {{ assetText('assets.clearQueue') }}
                    </a-button>
                  </div>
                </template>
                <template #content>
                  <div style="min-width: 280px; max-width: 360px;">
                    <div
                      v-for="t in runningReconTasks"
                      :key="t.taskId"
                      style="padding: 8px 0; border-bottom: 1px solid var(--arl-border-color); display: flex; justify-content: space-between; align-items: center; gap: 10px;"
                    >
                      <div style="flex: 1; min-width: 0;">
                        <div style="font-weight: 500; font-size: 13px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                          {{ t.name || t.target }}
                        </div>
                        <div style="font-size: 11px; color: var(--arl-text-color); opacity: 0.65; margin-top: 2px;">
                          {{ assetText('assets.tianyanchaAndOfficialRecordsDiscoveryAutomaticAssetGroup') }}
                        </div>
                      </div>
                      <div style="display: flex; align-items: center; gap: 6px;">
                        <a-tag color="processing" style="margin: 0; font-size: 11px;">
                          <sync-outlined spin /> {{ assetText('assets.discovering') }}
                        </a-tag>
                        <a-tooltip :title="assetText('assets.stopTrackingAndRemoveFromQueue')">
                          <close-outlined
                            style="cursor: pointer; color: #8c8c8c; font-size: 12px; padding: 2px; transition: color 0.2s;"
                            @click.stop="dismissPendingReconTask(t.taskId)"
                          />
                        </a-tooltip>
                      </div>
                    </div>
                  </div>
                </template>
                <a-tag color="processing" style="cursor: pointer; padding: 4px 10px; border-radius: 14px; font-size: 12px; display: inline-flex; align-items: center; gap: 5px;">
                  <sync-outlined spin /> {{ assetText('assets.runningEnterpriseCount', { count: runningReconTasks.length }) }}
                </a-tag>
              </a-popover>

              <!-- 集团上下文管理操作下拉 (当选中具体集团时呈现) -->
              <a-dropdown v-if="!['all', 'unassigned'].includes(activeGroupId)" :getPopupContainer="getBodyContainer">
                <template #overlay>
                  <a-menu @click="handleCurrentGroupDropdownClick">
                    <a-menu-item key="edit">
                      <EditOutlined /> {{ assetText('assets.rename') }}
                    </a-menu-item>
                    <a-menu-item key="delete" class="asset-danger">
                      <DeleteOutlined /> {{ assetText('tasks.delete') }}
                    </a-menu-item>
                  </a-menu>
                </template>
                <a-button class="header-action-btn">
                  <ApartmentOutlined /> {{ assetText('assets.manageOrganizationGroup') }} <DownOutlined />
                </a-button>
              </a-dropdown>

              <a-button type="primary" @click="openAddModal" class="header-action-btn">
                <PlusOutlined /> {{ assetText('tasks.createAnAssetGroup') }}
              </a-button>
            </div>
          </div>

          <!-- 筛选表单栏 -->
          <div class="scope-filter-toolbar">
            <a-form :label-wrap="true" :model="searchForm" layout="inline" class="scope-filter-form" @submit.prevent>
              <a-form-item :label="assetText('tasks.assetGroupName')">
                <a-input v-model:value="searchForm.name" :placeholder="assetText('assets.searchByName')" class="asset-width-170" allowClear @pressEnter="onSearch" />
              </a-form-item>
              <a-form-item :label="assetText('assets.assetScope')">
                <a-input v-model:value="searchForm.scope" :placeholder="assetText('assets.searchDomainsOrIps')" class="asset-width-175" allowClear @pressEnter="onSearch" />
              </a-form-item>
              <a-form-item :label="assetText('assets.assetScopeIdLabel')">
                <a-input v-model:value="searchForm._id" :placeholder="assetText('assets.searchById')" class="asset-width-170" allowClear @pressEnter="onSearch" />
              </a-form-item>
              <a-form-item class="filter-actions-item">
                <a-space size="small">
                  <a-button type="primary" @click="onSearch">
                    <SearchOutlined /> {{ assetText('tasks.search') }}
                  </a-button>
                  <a-button @click="resetSearch">
                    <ReloadOutlined /> {{ assetText('tasks.reset') }}
                  </a-button>
                </a-space>
              </a-form-item>
            </a-form>
          </div>

          <!-- 批量操作栏与选中信息条 -->
          <div class="scope-batch-toolbar">
            <div class="batch-buttons-group">
              <a-button :disabled="!hasSelected" @click="openBatchMoveModal">
                <FolderOpenOutlined /> {{ assetText('assets.moveSelectedToOrganizationGroup') }}
              </a-button>
              <a-button danger :disabled="!hasSelected" @click="handleBatchDelete">
                <DeleteOutlined /> {{ assetText('tasks.deleteSelected') }}
              </a-button>
              <a-dropdown :disabled="!hasSelected" :getPopupContainer="getBodyContainer">
                <template #overlay>
                  <a-menu @click="handleBatchExport">
                    <a-menu-item key="asset_domain">{{ assetText('tasks.exportSelectedDomains') }}</a-menu-item>
                    <a-menu-item key="asset_ip">{{ assetText('tasks.exportSelectedIps') }}</a-menu-item>
                    <a-menu-item key="asset_site">{{ assetText('tasks.exportSelectedWebsites') }}</a-menu-item>
                    <a-menu-item key="asset_wih">{{ assetText('assets.exportWihRecordsInBatch') }}</a-menu-item>
                  </a-menu>
                </template>
                <a-button>
                  {{ assetText('tasks.exportSelected') }} <DownOutlined />
                </a-button>
              </a-dropdown>
            </div>

            <div v-if="hasSelected" class="selection-indicator">
              <InfoCircleOutlined style="color: var(--arl-theme-color);" />
              <span>{{ assetText('assets.selected') }} <strong>{{ selectedRowKeys.length }}</strong> {{ assetText('assets.items') }}</span>
              <a-button type="link" size="small" @click="selectedRowKeys = []" class="asset-inline-action">{{ assetText('tasks.clearSelection') }}</a-button>
            </div>
          </div>

        </div>

        <a-table
          :sticky="stickyConfig"
          :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange, preserveSelectedRowKeys: true }"
          :loading="loading"
          :dataSource="dataSource"
          :columns="columns"
          :pagination="false"
          :scroll="{ x: 1000 }"
          bordered
          class="arl-scope-table"
          size="middle"
          :rowKey="(record) => record._id"
        >
          <template #bodyCell="{ column, record }">

            <template v-if="column.key === 'name'">
              <div class="group-name-cell">
                <div class="group-name-title-row">
                  <a class="group-name-title" @click="goToDetail(record)">{{ record.name }}</a>
                  <a-badge v-if="record.has_increment" :count="assetText('assets.newAssets')" class="asset-increment-badge" />
                </div>
                <div v-if="record.enterprise_name" class="enterprise-tag-row">
                  <a-tag color="cyan" size="small" class="enterprise-osint-tag" @click.stop="goToOsintDetail(record)">
                    <BankOutlined style="margin-right: 2px;" />{{ record.enterprise_name }}
                  </a-tag>
                </div>
              </div>
            </template>

            <template v-else-if="column.key === 'group_name'">
              <a-tooltip v-if="record.group_name" :title="assetText('assets.filterByThisOrganization')">
                <a-tag color="blue" class="group-cell-tag" style="cursor: pointer;" @click="activeGroupId = record.group_id">
                  <apartment-outlined style="margin-right: 3px;" />{{ record.group_name }}
                </a-tag>
              </a-tooltip>
              <a-tag v-else :bordered="false" style="color: var(--arl-text-color); opacity: 0.5; background: var(--arl-bg-light, rgba(0,0,0,0.03));">
                {{ assetText('assets.ungrouped') }}
              </a-tag>
            </template>

            <template v-else-if="column.key === 'scope_and_stat'">
              <div class="scope-stat-compact-cell">
                <!-- 顶行：前两个核心主域 + 总数胶囊 -->
                <div class="scope-compact-header">
                  <div class="scope-compact-tags">
                    <span
                      v-for="(item, idx) in (record.scope_array || []).slice(0, 2)"
                      :key="idx"
                      class="scope-compact-domain"
                      :title="item"
                    >
                      <span class="domain-status-dot" :class="'status-' + getDomainStatus(record, item)"></span>
                      {{ item }}
                    </span>
                  </div>
                  <a-popover
                    v-if="(record.scope_array || []).length > 0"
                    placement="bottomLeft"
                    :getPopupContainer="getBodyContainer"
                    trigger="hover"
                  >
                    <template #content>
                      <div class="scope-popover-panel">
                        <div class="scope-popover-header">
                          <span class="scope-popover-title">{{ assetText('assets.seedTargetCount', { count: (record.scope_array || []).length }) }}</span>
                          <a-button type="link" size="small" class="scope-popover-copy-btn" @click="copyText((record.scope_array || []).join('\n'))">
                            <copy-outlined /> {{ assetText('assets.copyAll') }}
                          </a-button>
                        </div>
                        <div class="scope-popover-list">
                          <a-tooltip
                            v-for="(item, idx) in (record._sorted_scopes || record.scope_array || [])"
                            :key="idx"
                            placement="right"
                            :getPopupContainer="getBodyContainer"
                          >
                            <template #title>
                              <div style="font-size: 12px; line-height: 1.6; padding: 2px;">
                                <div><b>{{ assetText('assets.target') }}</b> {{ item }}</div>
                                <div><b>{{ assetText('assets.status') }}</b> {{ getDomainStatusLabel(record, item) }}</div>
                                <template v-if="record.domain_status?.[item]?.sync_source === 'icp'">
                                  <div class="asset-source-label"><b>{{ assetText('assets.source') }}</b> {{ assetText('assets.enterpriseAssetQuery') }}</div>
                                  <div v-if="record.domain_status?.[item]?.task_name"><b>{{ assetText('assets.relatedTask') }}</b> {{ record.domain_status[item].task_name }}</div>
                                  <div v-if="record.domain_status?.[item]?.sync_time"><b>{{ assetText('assets.syncedAt') }}</b> {{ record.domain_status[item].sync_time }}</div>
                                  <div v-if="record.domain_status?.[item]?.task_id" style="margin-top: 4px; border-top: 1px dashed rgba(255,255,255,0.3); padding-top: 4px;">
                                    <a style="color: #40a9ff; font-weight: 500;" @click="goToReconDetail(record.domain_status[item].task_id)">
                                      {{ assetText('assets.viewEnterpriseTaskDetails') }}
                                    </a>
                                  </div>
                                </template>
                                <div v-else-if="record.domain_status?.[item]?.sync_time">
                                  <b>{{ assetText('assets.updatedAt') }}</b> {{ record.domain_status[item].sync_time }}
                                </div>
                              </div>
                            </template>
                            <div class="scope-popover-item">
                              <div class="scope-popover-item-main">
                                <span class="domain-status-dot" :class="'status-' + getDomainStatus(record, item)"></span>
                                <span v-if="record.domain_status?.[item]?.sync_source === 'icp'" class="asset-sync-marker" :title="assetText('assets.syncedFromEnterpriseAssets')">⚑</span>
                                <span class="scope-popover-item-text">{{ item }}</span>
                              </div>
                              <span class="scope-popover-item-status" :class="'text-' + getDomainStatus(record, item)">
                                {{ getDomainStatusLabel(record, item) }}
                              </span>
                            </div>
                          </a-tooltip>
                        </div>
                      </div>
                    </template>
                    <span class="scope-compact-count-badge">
                      {{ assetText('assets.targetCount', { count: (record.scope_array || []).length }) }}
                    </span>
                  </a-popover>
                  <span v-else class="asset-no-targets">{{ assetText('assets.noTargets') }}</span>
                </div>

                <!-- 底行：微型健康进度条与覆盖率 -->
                <div v-if="record.domain_stat && record.domain_stat.total > 0" class="scope-compact-progress-row">
                  <a-tooltip placement="top">
                    <template #title>
                      <div style="line-height: 1.8; font-size: 12px;">
                        <div>{{ assetText('assets.seedTargetsLabel') }} <strong>{{ record.domain_stat.total }}</strong></div>
                        <div v-if="record.domain_stat.scanning > 0">{{ assetText('assets.scanning') }} <strong class="asset-info">{{ record.domain_stat.scanning }}</strong></div>
                        <div>{{ assetText('assets.scanned') }} <strong class="asset-success">{{ record.domain_stat.probed }}</strong> ({{ Math.round((record.domain_stat.probed / record.domain_stat.total) * 100) }}%)</div>
                        <div v-if="record.domain_stat.unprobed > 0">{{ assetText('assets.notScanned') }} <strong class="asset-warning">{{ record.domain_stat.unprobed }}</strong></div>
                        <div v-if="record.domain_stat.error > 0">{{ assetText('assets.scanErrors') }} <strong class="asset-danger">{{ record.domain_stat.error }}</strong></div>
                      </div>
                    </template>
                    <div class="scope-mini-progress-bar">
                      <div
                        class="progress-seg probed"
                        :style="{ width: ((record.domain_stat.probed / record.domain_stat.total) * 100) + '%' }"
                      ></div>
                      <div
                        v-if="record.domain_stat.scanning > 0"
                        class="progress-seg scanning"
                        :style="{ width: ((record.domain_stat.scanning / record.domain_stat.total) * 100) + '%' }"
                      ></div>
                      <div
                        v-if="record.domain_stat.error > 0"
                        class="progress-seg error"
                        :style="{ width: ((record.domain_stat.error / record.domain_stat.total) * 100) + '%' }"
                      ></div>
                      <div
                        v-if="record.domain_stat.unprobed > 0"
                        class="progress-seg unprobed"
                        :style="{ width: ((record.domain_stat.unprobed / record.domain_stat.total) * 100) + '%' }"
                      ></div>
                    </div>
                  </a-tooltip>
                  <span class="scope-compact-progress-text">
                    {{ Math.round((record.domain_stat.probed / record.domain_stat.total) * 100) }}{{ assetText('assets.coverage') }}
                  </span>
                </div>
              </div>
            </template>

            <template v-else-if="column.key === 'scope_id'">
              <div style="display: flex; align-items: center; gap: 8px;">
                <a class="scope-id-text" @click="goToDetail(record)">{{ record._id }}</a>
                <a-tooltip :title="assetText('assets.copyAssetGroupId')">
                  <copy-outlined
                    class="copy-id-icon"
                    @click="copyText(record._id)"
                  />
                </a-tooltip>
              </div>
            </template>

            <template v-else-if="column.key === 'action'">
              <div class="table-actions-container">
                <a-button type="link" size="small" class="grid-action-btn btn-theme" @click="goToDetail(record)">
                  <RightCircleOutlined />{{ assetText('assets.open') }}
                </a-button>
                <a-button type="link" size="small" class="grid-action-btn" @click="openEditGroupModal(record)">
                  <EditOutlined />{{ assetText('assets.edit') }}
                </a-button>
                <a-dropdown :getPopupContainer="getBodyContainer">
                  <a-button type="link" size="small" class="grid-action-btn">
                    <ScheduleOutlined />{{ assetText('assets.schedule') }} <DownOutlined class="asset-small-caption" />
                  </a-button>
                  <template #overlay>
                    <a-menu>
                      <a-menu-item key="monitor" @click="openAddMonitorModal(record)">
                        <DashboardOutlined class="asset-info-icon" />{{ assetText('assets.assetMonitoringScan') }}
                      </a-menu-item>
                      <a-menu-item key="site" @click="openAddSiteMonitorModal(record)">
                        <GlobalOutlined class="asset-success-icon" />{{ assetText('assets.websiteAvailabilityMonitoring') }}
                      </a-menu-item>
                      <a-menu-item key="wih" @click="openAddWihMonitorModal(record)">
                        <RadarChartOutlined class="asset-purple-icon" />{{ assetText('assets.wihMonitoring') }}
                      </a-menu-item>
                    </a-menu>
                  </template>
                </a-dropdown>
                <a-button
                  v-if="record.has_increment"
                  type="link"
                  size="small"
                  class="grid-action-btn btn-success"
                  @click="openSyncIncrement(record)"
                  :title="assetText('assets.newAssetsFoundClickToSync')"
                >
                  <SyncOutlined />{{ assetText('assets.newAssets') }}
                </a-button>
                <a-button
                  v-else-if="!record.synced_icp_task_id"
                  type="link"
                  size="small"
                  class="grid-action-btn"
                  style="color: #fa8c16;"
                  @click="openBindEnterprise(record)"
                  :title="assetText('assets.noOrganizationLinkedClickToLinkOne')"
                >
                  <LinkOutlined />{{ assetText('assets.link') }}
                </a-button>
                <a-button type="link" danger size="small" class="grid-action-btn btn-danger" @click="handleSingleDelete(record)">
                  <DeleteOutlined />{{ assetText('tasks.delete') }}
                </a-button>
              </div>
            </template>

          </template>

          <template #emptyText>
            <div v-if="!searchForm.name && !searchForm.scope && !searchForm._id && activeGroupId === 'all'" style="padding: 36px 16px; text-align: center;">
              <div style="font-size: 16px; font-weight: 600; color: var(--arl-text-color); margin-bottom: 8px;">
                {{ assetText('assets.emptyGuideTitle') }}
              </div>
              <div style="font-size: 13px; color: var(--arl-text-color); opacity: 0.65; max-width: 600px; margin: 0 auto 18px; line-height: 1.6;">
                {{ assetText('assets.emptyGuideDesc') }}
              </div>
              <div style="display: inline-flex; align-items: center; gap: 8px; background: var(--arl-bg-light, rgba(0,0,0,0.02)); border: 1px solid var(--arl-border-color); border-radius: 6px; padding: 10px 18px; margin-bottom: 24px; font-size: 12px; color: var(--arl-text-color); opacity: 0.85;">
                <ApartmentOutlined style="color: var(--arl-theme-color);" />
                <span>{{ assetText('assets.architectureHierarchyTip') }}</span>
              </div>
              <div style="display: flex; justify-content: center; gap: 12px;">
                <a-button type="primary" @click="openAddModal">
                  <PlusOutlined /> {{ assetText('assets.createAssetGroupDirectly') }}
                </a-button>
                <a-button @click="openAddEnterpriseGroupModal">
                  <ApartmentOutlined /> {{ assetText('assets.createOrganizationGroupStructure') }}
                </a-button>
              </div>
            </div>
            <a-empty v-else :description="assetText('tasks.noData')" />
          </template>
        </a-table>

        <div class="table-pagination-footer">
          <div class="pagination-summary">{{ assetText('tasks.paginationSummary', { pages: Math.ceil(pagination.total / pagination.pageSize) || 1, total: pagination.total }) }}</div>
          <a-pagination
            :pageSizeOptions="$pageSizeOptions"
            v-model:current="pagination.current"
            v-model:pageSize="pagination.pageSize"
            :total="pagination.total"
            show-size-changer
            @change="handleTableChange"
            @showSizeChange="handleTableChange"
          />
        </div>
      </div>

    <!-- 新建资产组弹窗 -->
    <a-modal
      v-model:open="addModalVisible"
      :title="assetText('tasks.createAnAssetGroup')"
      :width="'720px'"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      :footer="creationMode === 'wizard' ? null : undefined"
      @ok="handleAddSubmit"
      :confirmLoading="addLoading"
      :okText="assetText('tasks.confirm')"
      :cancelText="assetText('assets.cancel')"
      destroyOnClose
    >
      <div class="creation-mode-selector">
        <div
          class="mode-card"
          :class="{ 'mode-card-active': creationMode === 'wizard' }"
          @click="creationMode = 'wizard'"
        >
          <div class="mode-card-header">
            <div class="mode-card-title-wrap">
              <span class="mode-card-title">{{ assetText('assets.discoverEnterpriseAndCreateAssetGroup') }}</span>
            </div>
            <a-tag color="orange" class="mode-card-tag">{{ assetText('assets.recommended') }}</a-tag>
          </div>
          <div class="mode-card-desc">
            {{ assetText('assets.discoverEnterpriseModeDesc') }}
          </div>
        </div>

        <div
          class="mode-card"
          :class="{ 'mode-card-active': creationMode === 'manual' }"
          @click="creationMode = 'manual'"
        >
          <div class="mode-card-header">
            <div class="mode-card-title-wrap">
              <span class="mode-card-title">{{ assetText('assets.enterAssetsManually') }}</span>
            </div>
          </div>
          <div class="mode-card-desc">
            {{ assetText('assets.enterAssetsManuallyModeDesc') }}
          </div>
        </div>
      </div>

      <!-- 手工录入模式 -->
      <a-form :label-wrap="true"
        v-if="creationMode === 'manual'"
        ref="addFormRef"
        :model="addForm"
        :rules="addRules"
        :label-col="{ style: { width: assetLocale !== 'zh-CN' ? '160px' : '110px' } }"
        :wrapper-col="{ style: { width: assetLocale !== 'zh-CN' ? 'calc(100% - 160px)' : 'calc(100% - 110px)' } }"
        style="margin-top: 10px;"
      >
        <a-form-item
          :label="assetText('tasks.parentOrganization')"
          name="group_id"
          :tooltip="assetText('assets.parentOrganizationHelpTooltip')"
        >
          <div style="display: flex; gap: 8px; align-items: center;">
            <a-select v-model:value="addForm.group_id" :placeholder="assetText('tasks.selectAParentOrganizationOptional')" allowClear show-search option-filter-prop="label" style="flex: 1;" :getPopupContainer="(trigger) => trigger.parentNode">
              <a-select-option v-for="g in groupList" :key="g._id" :value="g._id">{{ g.name }}</a-select-option>
            </a-select>
            <a-tooltip :title="assetText('assets.quickCreateOrganizationGroup')">
              <a-button type="dashed" @click="openQuickCreateGroup('manual')">
                <plus-outlined /> {{ assetText('assets.quickNew') }}
              </a-button>
            </a-tooltip>
          </div>
        </a-form-item>

        <a-form-item :label="assetText('tasks.assetGroupName')" name="name">
          <a-input v-model:value="addForm.name" :placeholder="assetText('tasks.enterAnAssetGroupName')" allowClear />
        </a-form-item>

        <a-form-item :label="assetText('assets.assetScope')" name="scope">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <span class="asset-muted-caption">{{ assetText('assets.enterTargetsOrImportFromAnExistingTask') }}</span>
            <a-button type="link" size="small" style="padding: 0; height: auto;" @click="openIcpImportModal('add')">
              <cloud-download-outlined /> {{ assetText('assets.importFromEnterpriseTask') }}
            </a-button>
          </div>
          <a-textarea
            v-model:value="addForm.scope"
            :rows="5"
            :placeholder="assetText('assets.enterIpsCidrRangesOrDomainsSuchAs')"
            style="font-family: monospace; font-size: 13px;"
          />
        </a-form-item>
      </a-form>

      <!-- 企业全景测绘建组模式 -->
      <div v-else-if="creationMode === 'wizard'">
        <!-- Stage 1: 全景测绘建组表单 -->
        <div v-if="wizardStep === 1">
          <a-spin :spinning="wizardLoading" :tip="wizardLoadingTip">
            <a-form :label-wrap="true"
              ref="wizardFormRef"
              :model="wizardForm"
              :label-col="{ style: { width: assetLocale !== 'zh-CN' ? '160px' : '110px' } }"
              :wrapper-col="{ style: { width: assetLocale !== 'zh-CN' ? 'calc(100% - 160px)' : 'calc(100% - 110px)' } }"
              style="margin-top: 8px;"
            >
              <!-- 引擎引导提示 -->
              <a-alert
                type="info"
                show-icon
                style="margin-bottom: 16px; border-radius: 6px; font-size: 12px;"
              >
                <template #message>
                  <span style="color: var(--arl-text-color); line-height: 1.5;">
                    {{ assetText('assets.enterATianyanchaCompanyUrlOrNumericGid') }}
                  </span>
                </template>
              </a-alert>

              <!-- 输入目标: 企业目标 (支持链接与纯数字ID) -->
              <a-form-item
                :label="assetText('tasks.targetOrganization')"
                required
                :validateStatus="wizardTargetError ? 'error' : ''"
                :help="wizardTargetError"
              >
                <a-input
                  v-model:value="wizardForm.target"
                  :placeholder="assetText('assets.pasteATianyanchaUrlSuchAsCompany25174642')"
                  allowClear
                  @change="onTycTargetChange"
                  @pressEnter="startWizardRecon"
                >
                  <template #prefix>
                    <component :is="parsedTycGid ? 'LinkOutlined' : 'BankOutlined'" style="color: #bfbfbf;" />
                  </template>
                </a-input>
                <div v-if="parsedTycGid" style="margin-top: 4px; font-size: 12px; color: var(--ant-primary-color); display: flex; align-items: center; gap: 4px;">
                  <check-circle-outlined /> <span>{{ assetText('tasks.parsedTianyanchaGid') }} <b>{{ parsedTycGid }}</b> {{ assetText('tasks.theGidWillBeVerifiedAndCombinedDiscovery') }}</span>
                </div>
                <div v-else-if="isWizardCompanyName" style="margin-top: 4px; font-size: 12px; color: #722ed1; display: flex; align-items: center; gap: 4px;">
                  <safety-certificate-outlined /> <span>{{ assetText('assets.registeredOrganizationIdentified') }} <b>{{ wizardForm.target.trim() }}</b> {{ assetText('tasks.sourceMiitIcpRecords') }}</span>
                </div>
              </a-form-item>

              <!-- 资产组名称 (选填，留空自动生成) -->
              <a-form-item
                :label="assetText('tasks.assetGroupName')"
                :tooltip="assetText('assets.leaveBlankToUseTheOfficialRegisteredCompany')"
              >
                <a-input
                  v-model:value="wizardForm.name"
                  :placeholder="assetText('assets.optionalDefaultsToTheRegisteredCompanyName')"
                  allowClear
                  @pressEnter="startWizardRecon"
                />
              </a-form-item>

              <!-- 所属集团 (选填) -->
              <a-form-item
                :label="assetText('tasks.parentOrganization')"
                :tooltip="assetText('assets.parentOrganizationHelpTooltip')"
              >
                <div style="display: flex; gap: 8px; align-items: center;">
                  <a-select
                    v-model:value="wizardForm.group_id"
                    :placeholder="assetText('tasks.selectAParentOrganizationOptional')"
                    allowClear
                    show-search
                    option-filter-prop="label"
                    style="flex: 1;"
                    :getPopupContainer="(trigger) => trigger.parentNode"
                  >
                    <a-select-option v-for="g in groupList" :key="g._id" :value="g._id" :label="g.name">{{ g.name }}</a-select-option>
                  </a-select>
                  <a-tooltip :title="assetText('assets.quickCreateOrganizationGroup')">
                    <a-button type="dashed" @click="openQuickCreateGroup('wizard')">
                      <plus-outlined /> {{ assetText('assets.quickNew') }}
                    </a-button>
                  </a-tooltip>
                </div>
              </a-form-item>

              <!-- 自动化托管与探测偏好 -->
              <div style="background: var(--arl-bg-light); border: 1px solid var(--arl-border-color); border-radius: 6px; padding: 12px 14px; margin-bottom: 16px;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
                  <span class="asset-section-caption">{{ assetText('assets.automaticGroupCreationAndDiscoveryPreferences') }}</span>
                </div>
                <div style="margin-bottom: 10px;">
                  <a-checkbox v-model:checked="wizardAutoSync">
                    <b>{{ assetText('assets.createAndManageAnAssetGroupAfterDiscovery') }}</b>
                    <span style="font-size: 12px; color: var(--arl-text-color); opacity: 0.7; margin-left: 6px;">
                      {{ assetText('assets.theServerCreatesTheGroupAfterDiscoveryYou') }}
                    </span>
                  </a-checkbox>
                </div>
                <div>
                  <a-checkbox v-model:checked="wizardAutoScan">
                    <b>{{ assetText('assets.startActiveScanningAfterCreatingTheGroup') }}</b>
                    <span style="font-size: 12px; color: var(--arl-text-color); opacity: 0.7; margin-left: 6px;">
                      {{ assetText('assets.queuePortScanningAndFingerprintDetectionForNewly') }}
                    </span>
                  </a-checkbox>
                </div>

                <div v-if="wizardAutoScan" style="margin-top: 12px; padding-top: 10px; border-top: 1px dashed var(--arl-border-color);">
                  <a-row :gutter="12">
                    <a-col :span="assetLocale !== 'zh-CN' ? 24 : 12">
                      <a-form-item :label="assetText('tasks.scanPolicy')" :label-col="{ style: { width: assetLocale !== 'zh-CN' ? '160px' : '80px' } }" :wrapper-col="{ style: { width: assetLocale !== 'zh-CN' ? 'calc(100% - 160px)' : 'calc(100% - 80px)' } }" :class="assetLocale !== 'zh-CN' ? 'asset-form-spacing' : 'asset-flush-bottom'" required>
                        <a-select
                          v-model:value="wizardPolicyId"
                          :placeholder="assetText('tasks.selectAScanPolicy')"
                          size="small"
                          :options="policyList.map(p => ({ value: p._id, label: p.name }))"
                        />
                      </a-form-item>
                    </a-col>
                    <a-col :span="assetLocale !== 'zh-CN' ? 24 : 12">
                      <a-form-item :label="assetText('tasks.taskTypeLabel')" :label-col="{ style: { width: assetLocale !== 'zh-CN' ? '160px' : '80px' } }" :wrapper-col="{ style: { width: assetLocale !== 'zh-CN' ? 'calc(100% - 160px)' : 'calc(100% - 80px)' } }" class="asset-flush-bottom">
                        <a-radio-group v-model:value="wizardTaskType" size="small">
                          <a-radio-button value="oneshot">{{ assetText('assets.oneTimeScan') }}</a-radio-button>
                          <a-radio-button value="periodic">{{ assetText('assets.recurringMonitoring') }}</a-radio-button>
                        </a-radio-group>
                      </a-form-item>
                    </a-col>
                  </a-row>
                </div>
              </div>

              <!-- 高级测绘参数（常驻平铺展示） -->
              <div style="background: var(--arl-bg-light); border: 1px solid var(--arl-border-color); border-radius: 6px; padding: 12px 14px; margin-bottom: 20px;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 10px;">
                  <span class="asset-section-caption">{{ assetText('tasks.advancedDiscoverySettings') }}</span>
                </div>
                <a-row :gutter="16">
                  <a-col :span="assetLocale !== 'zh-CN' ? 24 : 12">
                    <a-form-item
                      :label="assetText('tasks.investmentDepthLabel')"
                      :label-col="{ style: { width: assetLocale !== 'zh-CN' ? '160px' : '90px' } }"
                      :wrapper-col="{ style: { width: assetLocale !== 'zh-CN' ? 'calc(100% - 160px)' : 'calc(100% - 90px)' } }"
                      style="margin-bottom: 8px;"
                      :tooltip="assetText('tasks.recursiveDepthForSubsidiariesAndInvesteeCompanies1')"
                    >
                      <a-input-number
                        v-model:value="wizardForm.depth"
                        :min="1"
                        :max="20"
                        size="small"
                        style="width: 100%;"
                        :addon-after="assetText('tasks.levels')"
                      />
                    </a-form-item>
                  </a-col>
                  <a-col :span="assetLocale !== 'zh-CN' ? 24 : 12">
                    <a-form-item
                      :label="assetText('tasks.minimumOwnershipLabel')"
                      :label-col="{ style: { width: assetLocale !== 'zh-CN' ? '160px' : '90px' } }"
                      :wrapper-col="{ style: { width: assetLocale !== 'zh-CN' ? 'calc(100% - 160px)' : 'calc(100% - 90px)' } }"
                      style="margin-bottom: 8px;"
                      :tooltip="assetText('tasks.minimumOwnershipShareForInvestments1100')"
                    >
                      <a-input-number
                        v-model:value="wizardForm.invest_ratio"
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
                      <span class="settings-row-title">{{ assetText('tasks.icpCrossCheck') }}</span>
                      <a-tooltip :title="assetText('tasks.crossCheckAgainstOfficialMiitIcpRecordsAnd')">
                        <question-circle-outlined class="settings-row-help" />
                      </a-tooltip>
                    </div>
                    <div class="settings-row-subtitle">
                      {{ assetText('tasks.crossCheckAgainstOfficialMiitIcpRecordsAnd') }}
                    </div>
                  </div>
                  <div class="settings-row-right">
                    <a-switch v-model:checked="wizardForm.enable_icp" size="small" />
                    <span class="settings-row-status">
                      {{ wizardForm.enable_icp ? assetText('tasks.enabledRecommended') : assetText('assets.disabled') }}
                    </span>
                  </div>
                </div>

                <a-alert
                  v-if="wizardForm.depth > 1"
                  type="warning"
                  show-icon
                  style="margin-top: 10px; font-size: 12px; border-radius: 4px;"
                  :message="assetText('tasks.investmentDepthHint', { depth: wizardForm.depth })"
                />
              </div>

              <div style="display: flex; justify-content: flex-end; gap: 8px; margin-top: 20px;">
                <a-button @click="addModalVisible = false">{{ assetText('assets.cancel') }}</a-button>
                <a-button type="primary" :loading="wizardLoading" @click="startWizardRecon">
                  <template #icon><rocket-outlined /></template>
                  {{ wizardAutoSync ? assetText('assets.discoverEnterpriseAndCreateAssetGroupAutomatically') : assetText('assets.startEnterpriseDiscovery') }}
                </a-button>
              </div>
            </a-form>
          </a-spin>
        </div>

        <!-- Stage 2: 域名挑选与创建入库 -->
        <div v-else-if="wizardStep === 2">
          <div style="margin-bottom: 14px;">
            <a-alert
              type="success"
              show-icon
              :message="assetText('assets.enterpriseDiscoveryCompletedWebsiteDomainsFoundCount', { count: wizardDomains.length })"
              :description="assetText('assets.organizationGroupGroupAssetGroupNameName', { group: getGroupName(wizardForm.group_id) || assetText('assets.ungrouped'), name: wizardForm.name.trim() || (wizardForm.target.trim() ? 'TYC_' + wizardForm.target.trim() : assetText('assets.unnamed')) })"
            />
          </div>

          <div style="margin-bottom: 10px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 8px;">
            <div style="display: flex; gap: 6px; align-items: center;">
              <a-input v-model:value="wizardDomainSearch" :placeholder="assetText('tasks.filterDomains')" size="small" class="asset-width-160" allowClear />
              <a-button size="small" @click="selectAllWizardDomains">{{ assetText('tasks.selectAll') }}</a-button>
              <a-button size="small" @click="selectedWizardDomains = []">{{ assetText('tasks.clearThisCategory') }}</a-button>
            </div>
            <span style="font-size: 12px; color: var(--arl-text-color); opacity: 0.7;">
              {{ assetText('assets.selected') }} <b class="asset-theme-text">{{ selectedWizardDomains.length }}</b> / {{ wizardDomains.length }} {{ assetText('assets.items') }}
            </span>
          </div>

          <div style="max-height: 200px; overflow-y: auto; border: 1px solid var(--arl-border-color); border-radius: 6px; padding: 8px; background: var(--arl-bg-light); display: flex; flex-direction: column; gap: 4px; margin-bottom: 16px;">
            <div v-for="d in filteredWizardDomains" :key="d" style="display: flex; align-items: center; justify-content: space-between; padding: 4px 8px; background: var(--arl-bg-white); border-radius: 4px; font-family: monospace; font-size: 12px;">
              <a-checkbox :checked="selectedWizardDomains.includes(d)" @change="e => toggleWizardDomain(d, e.target.checked)">
                {{ d }}
              </a-checkbox>
            </div>
            <div v-if="filteredWizardDomains.length === 0" style="text-align: center; color: #bfbfbf; padding: 16px; font-size: 12px;">
              {{ assetText('assets.noMatchingDomainsFound') }}
            </div>
          </div>

          <a-form layout="vertical" style="background: var(--arl-bg-light); padding: 12px 14px; border-radius: 6px; border: 1px solid var(--arl-border-color); margin-bottom: 20px;">
            <a-form-item :label="assetText('assets.automaticDiscovery')" class="asset-form-spacing">
              <a-checkbox v-model:checked="wizardAutoScan">{{ assetText('assets.runActiveDiscoveryOnTheSelectedDomainsNow') }}</a-checkbox>
            </a-form-item>
            <template v-if="wizardAutoScan">
              <a-row :gutter="16">
                <a-col :span="assetLocale !== 'zh-CN' ? 24 : 12">
                  <a-form-item :label="assetText('tasks.taskTypeLabel')" :class="assetLocale !== 'zh-CN' ? 'asset-form-spacing' : 'asset-flush-bottom'">
                    <a-radio-group v-model:value="wizardTaskType">
                      <a-radio-button value="oneshot">{{ assetText('assets.oneTimeScan') }}</a-radio-button>
                      <a-radio-button value="periodic">{{ assetText('assets.recurringMonitoring') }}</a-radio-button>
                    </a-radio-group>
                  </a-form-item>
                </a-col>
                <a-col :span="assetLocale !== 'zh-CN' ? 24 : 12">
                  <a-form-item :label="assetText('tasks.scanPolicy')" class="asset-flush-bottom" required>
                    <a-select v-model:value="wizardPolicyId" :placeholder="assetText('tasks.selectAScanPolicy')" :options="policyList.map(p => ({ value: p._id, label: p.name }))" />
                  </a-form-item>
                </a-col>
              </a-row>
            </template>
          </a-form>

          <div style="display: flex; justify-content: space-between; align-items: center;">
            <a-button @click="wizardStep = 1">{{ assetText('assets.goBack') }}</a-button>
            <div style="display: flex; gap: 8px;">
              <a-button @click="addModalVisible = false">{{ assetText('assets.cancel') }}</a-button>
              <a-button type="primary" :loading="wizardSubmitting" :disabled="selectedWizardDomains.length === 0" @click="submitWizardSync">
                {{ assetText('assets.createGroupWithCount', { count: selectedWizardDomains.length }) }}
              </a-button>
            </div>
          </div>
        </div>
      </div>
    </a-modal>

    <!-- 编辑资产组弹窗 -->
    <a-modal
      v-model:open="editGroupModalVisible"
      :title="assetText('assets.editAssetGroup')"
      @ok="handleEditGroupSubmit"
      :confirmLoading="editGroupLoading"
      width="640px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      :okText="assetText('assets.save')"
      :cancelText="assetText('assets.cancel')"
      destroyOnClose
    >
      <a-form :label-wrap="true"
        ref="editGroupFormRef"
        :model="editGroupForm"
        :rules="editGroupRules"
        :label-col="{ span: assetLocale !== 'zh-CN' ? 6 : 4 }"
        :wrapper-col="{ span: assetLocale !== 'zh-CN' ? 17 : 19 }"
        style="margin-top: 20px;"
      >
        <a-form-item
          :label="assetText('tasks.parentOrganization')"
          name="group_id"
          :tooltip="assetText('assets.parentOrganizationHelpTooltip')"
        >
          <div style="display: flex; gap: 8px; align-items: center;">
            <a-select v-model:value="editGroupForm.group_id" :placeholder="assetText('tasks.selectAParentOrganizationOptional')" allowClear show-search option-filter-prop="label" style="flex: 1;" :getPopupContainer="(trigger) => trigger.parentNode">
              <a-select-option v-for="g in groupList" :key="g._id" :value="g._id">{{ g.name }}</a-select-option>
            </a-select>
            <a-tooltip :title="assetText('assets.quickCreateOrganizationGroup')">
              <a-button type="dashed" @click="openQuickCreateGroup('edit')">
                <plus-outlined /> {{ assetText('assets.quickNew') }}
              </a-button>
            </a-tooltip>
          </div>
        </a-form-item>

        <a-form-item :label="assetText('tasks.assetGroupName')" name="name">
          <a-input v-model:value="editGroupForm.name" :placeholder="assetText('tasks.enterAnAssetGroupName')" />
        </a-form-item>

        <a-form-item :label="assetText('assets.assetScope')" name="scope">
          <!-- 提前告知剔除范围的级联后果，避免用户仅在点击保存后才被动获知 -->
          <div style="background: rgba(250, 173, 20, 0.12); border: 1px solid rgba(250, 173, 20, 0.3); border-radius: 4px; padding: 6px 10px; margin-bottom: 8px; font-size: 12px; color: #faad14; line-height: 1.5;">
            {{ assetText('assets.removingTargetsAlsoPermanentlyDeletesTheirDiscoveredSubdomains') }}
          </div>
          <!-- 模式切换与统计栏 -->
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="font-size: 13px; color: var(--arl-text-color); opacity: 0.85;">
              <span>{{ assetText('assets.total') }} <strong class="asset-theme-fallback">{{ editGroupScopeList.length }}</strong> {{ assetText('assets.validTargets') }}</span>
              <span v-if="editGroupMode === 'visual' && editGroupSearchKeyword.trim()" style="margin-left: 6px;">
                {{ assetText('assets.matched') }} <strong class="asset-success">{{ filteredScopeList.length }}</strong> {{ assetText('assets.message') }}
              </span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <a-button
                type="link"
                size="small"
                class="asset-text-action"
                @click="openIcpImportModal('edit')"
              >
                <cloud-download-outlined class="asset-inline-icon" />{{ assetText('assets.importEnterpriseAssets') }}
              </a-button>
              <a-button
                type="link"
                size="small"
                class="asset-text-action"
                @click="toggleEditGroupMode"
              >
                <template v-if="editGroupMode === 'visual'">
                  <file-text-outlined class="asset-inline-icon" />{{ assetText('assets.bulkTextMode') }}
                </template>
                <template v-else>
                  <tags-outlined class="asset-inline-icon" />{{ assetText('assets.tagMode') }}
                </template>
              </a-button>
            </div>
          </div>

          <!-- 可视化管理模式 -->
          <div v-if="editGroupMode === 'visual'" class="arl-scope-visual-panel">
            <!-- 搜索与批量删除工具栏 -->
            <div style="display: flex; gap: 8px; margin-bottom: 8px;">
              <a-input
                v-model:value="editGroupSearchKeyword"
                :placeholder="assetText('assets.searchAssetsByDomainOrIp')"
                allowClear
                size="middle"
                style="flex: 1;"
              >
                <template #prefix>
                  <search-outlined style="color: #bfbfbf;" />
                </template>
              </a-input>

              <a-popconfirm
                v-if="editGroupSearchKeyword.trim() && filteredScopeList.length > 0"
                :title="assetText('assets.removeAllMatchingScopeTargetsCount', { count: filteredScopeList.length })"
                :ok-text="assetText('tasks.delete')"
                :cancel-text="assetText('tasks.cancel')"
                ok-type="danger"
                @confirm="removeFilteredScopes"
              >
                <a-button danger size="middle">
                  <delete-outlined /> {{ assetText('assets.deleteFilteredCount', { count: filteredScopeList.length }) }}
                </a-button>
              </a-popconfirm>
            </div>

            <!-- 快捷追加输入 -->
            <div style="display: flex; gap: 8px; margin-bottom: 10px;">
              <a-input
                v-model:value="editGroupNewInput"
                :placeholder="assetText('assets.addAssetsPasteMultipleLinesOrCommaSeparated')"
                size="middle"
                @pressEnter="addScopesFromInput"
                style="flex: 1;"
              />
              <a-button type="primary" size="middle" @click="addScopesFromInput">
                <plus-outlined /> {{ assetText('assets.add') }}
              </a-button>
            </div>

            <!-- 资产标签滚动展示区 -->
            <div class="arl-scope-tag-container">
              <template v-if="filteredScopeList.length > 0">
                <a-tag
                  v-for="item in filteredScopeList"
                  :key="item"
                  closable
                  @close.prevent="removeScopeItem(item)"
                  class="arl-scope-edit-item-tag"
                >
                  {{ item }}
                </a-tag>
              </template>
              <div v-else class="arl-scope-empty-hint">
                {{ editGroupSearchKeyword.trim() ? assetText('assets.noMatchingAssets') : assetText('assets.noAssetsYetAddThemAbove') }}
              </div>
            </div>
          </div>

          <!-- 纯文本批量模式 -->
          <div v-else>
            <a-textarea
              v-model:value="editGroupForm.scope"
              :rows="7"
              :placeholder="assetText('assets.enterIpsOrDomainsSeparatedByCommasOr')"
              style="font-family: monospace; font-size: 13px;"
            />
            <div style="margin-top: 6px; font-size: 12px; color: var(--arl-text-color); opacity: 0.65; display: flex; justify-content: space-between; align-items: center;">
              <span>{{ assetText('assets.totalLabel') }} <strong class="asset-info">{{ parseScopeList(editGroupForm.scope).length }}</strong> {{ assetText('assets.validTargets') }}</span>
              <a-button type="link" size="small" class="asset-text-action" @click="formatEditGroupScopes">{{ assetText('assets.formatAndDeduplicate') }}</a-button>
            </div>
          </div>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 添加常规监控任务 -->
    <a-modal
      v-model:open="addMonitorVisible"
      @ok="submitAddMonitor"
      :confirmLoading="addMonitorLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      :okText="assetText('tasks.confirm')"
      :cancelText="assetText('assets.cancel')"
      destroyOnClose
    >
      <template #title>
        {{ assetText('assets.addMonitoringTask') }}
        <a-tooltip :title="assetText('assets.thePolicyRunsAgainstTheUnionOfExisting')">
          <QuestionCircleOutlined style="font-size: 14px; color: #8c8c8c; cursor: pointer; margin-left: 4px;" />
        </a-tooltip>
      </template>
      <a-form :label-wrap="true" ref="addMonitorFormRef" :model="addMonitorForm" :rules="addMonitorRules" :label-col="{ span: assetLocale !== 'zh-CN' ? 7 : 5 }" :wrapper-col="{ span: assetLocale !== 'zh-CN' ? 16 : 18 }" class="asset-risk-form">

        <a-form-item :label="assetText('assets.scope')" name="domains">
          <div style="margin-bottom: 8px; display: flex; gap: 6px; flex-wrap: wrap;">
            <a-button size="small" @click="selectAllDomains">{{ assetText('assets.selectAllCount', { count: (currentRecord?.scope_array || []).length }) }}</a-button>
            <a-button
              size="small"
              type="primary"
              ghost
              @click="selectUnprobedDomains"
              :style="{ borderColor: unprobedDomainList.length > 0 ? '#faad14' : '', color: unprobedDomainList.length > 0 ? '#d48806' : '' }"
            >
              {{ assetText('assets.selectUnscannedCount', { count: unprobedDomainList.length }) }}
            </a-button>
            <a-button size="small" @click="selectProbedDomains">{{ assetText('assets.selectScannedCount', { count: probedDomainList.length }) }}</a-button>
            <a-button size="small" @click="clearDomains">{{ assetText('assets.clear') }}</a-button>
          </div>
          <a-select mode="multiple" v-model:value="addMonitorForm.domains" :placeholder="assetText('assets.selectTargets')" class="asset-full-width">
            <a-select-option v-for="item in currentRecord?.scope_array || []" :key="item" :value="item">
              <span style="display: flex; justify-content: space-between; align-items: center;">
                <span>{{ item }}</span>
                <span :style="{
                  fontSize: '11px',
                  marginLeft: '8px',
                  color: getDomainStatus(currentRecord, item) === 'unprobed' ? '#faad14' :
                         getDomainStatus(currentRecord, item) === 'scanning' ? '#1890ff' :
                         getDomainStatus(currentRecord, item) === 'error' ? '#ff4d4f' : '#52c41a'
                }">
                  [{{ getDomainStatusLabel(currentRecord, item) }}]
                </span>
              </span>
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item :label="assetText('tasks.taskTypeLabel')" name="task_type">
          <a-radio-group v-model:value="addMonitorForm.task_type">
            <a-radio value="periodic">{{ assetText('assets.recurringMonitoring') }}</a-radio>
            <a-radio value="oneshot">{{ assetText('assets.oneTimeScan') }}</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item :label="assetText('tasks.runInterval')" name="interval_hours" v-if="addMonitorForm.task_type === 'periodic'">
          <div style="display: flex; align-items: center; gap: 8px;">
            <a-input-number v-model:value="addMonitorForm.interval_hours" :min="1" style="width: 100%;" />
            <span>{{ assetText('tasks.hours') }}</span>
          </div>
        </a-form-item>

        <a-form-item :label="assetText('tasks.policy')" name="policy_id">
          <a-select v-model:value="addMonitorForm.policy_id" :placeholder="assetText('tasks.selectAPolicy')">
            <a-select-option v-for="p in policies" :key="p._id" :value="p._id">{{ p.name }}</a-select-option>
          </a-select>
        </a-form-item>

      </a-form>
    </a-modal>

    <!-- 添加站点监控任务 -->
    <a-modal
      v-model:open="addSiteMonitorVisible"
      :title="assetText('assets.addWebsiteMonitoringTask')"
      @ok="submitAddSiteMonitor"
      :confirmLoading="addSiteMonitorLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      :okText="assetText('tasks.confirm')"
      :cancelText="assetText('assets.cancel')"
      destroyOnClose
    >
      <a-form :label-wrap="true" ref="addSiteMonitorFormRef" :model="addSiteMonitorForm" :rules="addSiteMonitorRules" :label-col="{ span: assetLocale !== 'zh-CN' ? 7 : 5 }" :wrapper-col="{ span: assetLocale !== 'zh-CN' ? 16 : 18 }" class="asset-risk-form">
        <a-form-item :label="assetText('tasks.runInterval')" name="interval_hours">
          <div style="display: flex; align-items: center; gap: 8px;">
            <a-input-number v-model:value="addSiteMonitorForm.interval_hours" :min="1" style="width: 100%;" />
            <span>{{ assetText('tasks.hours') }}</span>
          </div>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 添加WIH监控任务 -->
    <a-modal
      v-model:open="addWihMonitorVisible"
      :title="assetText('assets.addWihMonitoringTask')"
      @ok="submitAddWihMonitor"
      :confirmLoading="addWihMonitorLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      :okText="assetText('tasks.confirm')"
      :cancelText="assetText('assets.cancel')"
      destroyOnClose
    >
      <a-form :label-wrap="true" ref="addWihMonitorFormRef" :model="addWihMonitorForm" :rules="addWihMonitorRules" :label-col="{ span: assetLocale !== 'zh-CN' ? 7 : 5 }" :wrapper-col="{ span: assetLocale !== 'zh-CN' ? 16 : 18 }" class="asset-risk-form">
        <a-form-item :label="assetText('tasks.runInterval')" name="interval_hours">
          <div style="display: flex; align-items: center; gap: 8px;">
            <a-input-number v-model:value="addWihMonitorForm.interval_hours" :min="1" style="width: 100%;" />
            <span>{{ assetText('tasks.hours') }}</span>
          </div>
        </a-form-item>

      </a-form>
    </a-modal>


    <!-- 新建/重命名集团弹窗 -->
    <a-modal
      v-model:open="enterpriseGroupModalVisible"
      :title="enterpriseGroupForm.isEdit ? assetText('assets.renameOrganizationGroup') : assetText('assets.newOrganizationGroup')"
      @ok="submitEnterpriseGroup"
      :confirmLoading="enterpriseGroupLoading"
      width="480px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      :okText="assetText('tasks.confirm')"
      :cancelText="assetText('assets.cancel')"
      destroyOnClose
    >
      <a-form :label-wrap="true" :model="enterpriseGroupForm" layout="vertical" class="asset-modal-spacing">
        <a-form-item :label="assetText('assets.organizationGroupName')" required>
          <a-input v-model:value="enterpriseGroupForm.name" :placeholder="assetText('assets.enterAnOrganizationGroupName')" />
        </a-form-item>
        <a-form-item :label="assetText('assets.description')" v-if="!enterpriseGroupForm.isEdit">
          <a-textarea v-model:value="enterpriseGroupForm.description" :placeholder="assetText('assets.enterADescriptionOptional')" :rows="3" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 快捷新建集团轻量弹窗 -->
    <a-modal
      v-model:open="quickGroupModalVisible"
      :title="assetText('assets.quickCreateOrganizationGroup')"
      @ok="handleQuickGroupSubmit"
      :confirmLoading="quickGroupLoading"
      width="420px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      :okText="assetText('tasks.confirm')"
      :cancelText="assetText('assets.cancel')"
      destroyOnClose
    >
      <div style="font-size: 12px; color: var(--arl-text-color); opacity: 0.75; margin-bottom: 14px; line-height: 1.6;">
        {{ assetText('assets.quickCreateOrganizationDesc') }}
      </div>
      <a-form layout="vertical">
        <a-form-item :label="assetText('assets.organizationGroupName')" required>
          <a-input
            v-model:value="quickGroupName"
            :placeholder="assetText('assets.enterAnOrganizationGroupName')"
            @pressEnter="handleQuickGroupSubmit"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 批量移动至集团弹窗 -->
    <a-modal
      v-model:open="batchMoveModalVisible"
      :title="assetText('assets.moveSelectedToOrganizationGroup')"
      @ok="submitBatchMove"
      :confirmLoading="batchMoveLoading"
      width="480px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      :okText="assetText('tasks.confirm')"
      :cancelText="assetText('assets.cancel')"
      destroyOnClose
    >
      <a-form :label-wrap="true" layout="vertical" class="asset-modal-spacing">
        <p>{{ assetText('assets.selected') }} <strong>{{ selectedRowKeys.length }}</strong> {{ assetText('assets.assetGroupsLabel') }}</p>
        <a-form-item :label="assetText('assets.destinationOrganizationGroup')" required>
          <a-select v-model:value="batchMoveTargetGroupId" :placeholder="assetText('assets.selectADestinationOrganizationGroup')" :getPopupContainer="(trigger) => trigger.parentNode">
            <a-select-option value="unassigned">{{ assetText('assets.removeGroupingMoveToUngrouped') }}</a-select-option>
            <a-select-option v-for="g in groupList" :key="g._id" :value="g._id">{{ g.name }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 集团删除与下属资产组处置弹窗 -->
    <a-modal
      v-model:open="deleteGroupModalVisible"
      :title="assetText('assets.deleteOrganizationWithSubScopesTitle')"
      width="540px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      destroyOnClose
    >
      <div v-if="deleteGroupTarget" style="display: flex; flex-direction: column; gap: 16px; padding: 4px 0;">
        <a-alert
          type="info"
          show-icon
          :message="assetText('assets.deleteOrganizationNoticeDataKept')"
        />

        <div style="font-size: 13px; color: var(--arl-text-color); font-weight: 500;">
          {{ assetText('assets.subordinateAssetGroupCountNotice', { count: deleteGroupTarget.scope_count || 0 }) }}
        </div>

        <a-radio-group v-model:value="deleteGroupForm.action" style="display: flex; flex-direction: column; gap: 12px; width: 100%;">
          <div
            style="border: 1px solid var(--arl-border-color); border-radius: 6px; padding: 12px; cursor: pointer; transition: all 0.2s;"
            :style="deleteGroupForm.action === 'dissolve' ? { borderColor: 'var(--arl-theme-color)', background: 'rgba(250, 84, 28, 0.03)' } : {}"
            @click="deleteGroupForm.action = 'dissolve'"
          >
            <a-radio value="dissolve" style="font-weight: 500; align-items: flex-start;">
              <div>
                <span style="font-weight: 600;">{{ assetText('assets.dissolveToUngrouped') }}</span>
                <div style="font-size: 12px; color: var(--arl-text-color); opacity: 0.7; margin-top: 4px; font-weight: normal; line-height: 1.5;">
                  {{ assetText('assets.dissolveToUngroupedDesc') }}
                </div>
              </div>
            </a-radio>
          </div>

          <div
            style="border: 1px solid var(--arl-border-color); border-radius: 6px; padding: 12px; transition: all 0.2s;"
            :style="[
              deleteGroupForm.action === 'transfer' ? { borderColor: 'var(--arl-theme-color)', background: 'rgba(250, 84, 28, 0.03)' } : {},
              availableTransferGroups.length === 0 ? { opacity: 0.6, cursor: 'not-allowed' } : { cursor: 'pointer' }
            ]"
            @click="availableTransferGroups.length > 0 && (deleteGroupForm.action = 'transfer')"
          >
            <a-radio value="transfer" :disabled="availableTransferGroups.length === 0" style="font-weight: 500; align-items: flex-start; width: 100%;">
              <div style="width: 100%;">
                <span style="font-weight: 600;">{{ assetText('assets.transferToOtherOrganization') }}</span>
                <div style="font-size: 12px; color: var(--arl-text-color); opacity: 0.7; margin-top: 4px; font-weight: normal; line-height: 1.5;">
                  {{ availableTransferGroups.length > 0 ? assetText('assets.transferToOtherOrganizationDesc') : assetText('assets.noOtherOrganizationAvailable') }}
                </div>

                <div v-if="deleteGroupForm.action === 'transfer'" style="margin-top: 10px;" @click.stop>
                  <a-select
                    v-model:value="deleteGroupForm.target_group_id"
                    :placeholder="assetText('assets.selectTargetOrganization')"
                    style="width: 100%;"
                    :getPopupContainer="getBodyContainer"
                  >
                    <a-select-option v-for="g in availableTransferGroups" :key="g._id" :value="g._id">
                      {{ g.name }} ({{ assetText('assets.assetGroupCount', { count: g.scope_count || 0 }) }})
                    </a-select-option>
                  </a-select>
                </div>
              </div>
            </a-radio>
          </div>
        </a-radio-group>
      </div>

      <template #footer>
        <a-space>
          <a-button @click="deleteGroupModalVisible = false">{{ assetText('assets.cancel') }}</a-button>
          <a-button
            type="primary"
            danger
            :loading="deleteGroupLoading"
            :disabled="deleteGroupForm.action === 'transfer' && !deleteGroupForm.target_group_id"
            @click="confirmDeleteGroupWithDisposal"
          >
            {{ deleteGroupForm.action === 'transfer' ? assetText('assets.confirmTransferAndDelete') : assetText('assets.confirmDissolveAndDelete') }}
          </a-button>
        </a-space>
      </template>
    </a-modal>
    <a-modal
      v-model:open="icpImportModalVisible"
      :title="assetText('assets.importAssetsFromEnterpriseQuery')"
      :footer="null"
      width="720px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      destroyOnClose
    >
      <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
        <a-input
          v-model:value="icpImportSearchKey"
          :placeholder="assetText('assets.searchTaskNameOrTargetOrganization')"
          allowClear
          style="width: 280px;"
        >
          <template #prefix><search-outlined style="color: #bfbfbf;" /></template>
        </a-input>
        <span style="font-size: 12px; color: var(--arl-text-color); opacity: 0.65;">
          {{ assetText('assets.showsCompletedEnterpriseAssetAndIcpQueryTasks') }}
        </span>
      </div>

      <a-table
        :dataSource="filteredIcpTasks"
        :columns="icpImportColumns"
        :loading="icpImportLoading"
        :pagination="{ pageSize: 5, size: 'small' }"
        size="small"
        :rowKey="r => r._id"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'statistic'">
            <span>{{ assetText('assets.websiteCount', { count: record.statistic?.web_cnt !== undefined ? record.statistic.web_cnt : (record.statistic?.asset_cnt || 0) }) }}</span>
          </template>
          <template v-else-if="column.key === 'action'">
            <a-button
              type="primary"
              size="small"
              :loading="importingTaskId === record._id"
              @click="handleImportFromTask(record)"
            >
              {{ assetText('assets.importAssetsFromThisTask') }}
            </a-button>
          </template>
        </template>
      </a-table>
    </a-modal>

    <!-- 同步增量弹窗 -->
    <SyncToScopeModal
      v-model:open="syncIncrementModalVisible"
      :task="currentIncrementTask"
      @success="handleIncrementSyncSuccess"
    />

    <!-- 列表操作栏：绑定企业主体弹窗 -->
    <a-modal
      v-model:open="bindScopeModalVisible"
      :title="assetText('assets.linkOrganizationToAssetGroup')"
      @ok="submitBindScopeEnterprise"
      :confirmLoading="bindScopeLoading"
      width="540px"
      wrapClassName="arl-theme-modal"
      :okText="assetText('tasks.confirm')"
      :cancelText="assetText('assets.cancel')"
      destroyOnClose
    >
      <a-form :label-wrap="true" :label-col="{ span: assetLocale !== 'zh-CN' ? 7 : 5 }" :wrapper-col="{ span: assetLocale !== 'zh-CN' ? 16 : 18 }" class="asset-risk-form">
        <a-form-item :label="assetText('assets.currentAssetGroup')">
          <span style="font-weight: 500;">{{ currentBindingScope?.name }}</span>
        </a-form-item>
        <a-form-item :label="assetText('tasks.enterpriseOsint')" required>
          <a-select
            v-model:value="selectedBindScopeTaskId"
            :placeholder="assetText('assets.selectACompletedEnterpriseDiscoveryTask')"
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
      </a-form>
    </a-modal>

  </div>
  <!-- Close Root wrapper div added at step 1 -->
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';
defineOptions({ name: 'AssetScope' });

import { ref, reactive, computed, createVNode, watch, onActivated, onDeactivated, onUnmounted, onMounted, nextTick } from 'vue';
import Sortable from 'sortablejs';
import { useSticky } from '../utils/useSticky';
const sidebarAnchorRef = ref(null);
const sidebarLeft = ref(186);

const updateSidebarLeft = () => {
  if (sidebarAnchorRef.value) {
    const rect = sidebarAnchorRef.value.getBoundingClientRect();
    if (rect.left > 0) {
      sidebarLeft.value = rect.left;
    }
  }
};

const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

import request from '../utils/request';
import { message, Modal, notification, Button } from 'ant-design-vue';
import { h } from 'vue';
import SyncToScopeModal from '../components/SyncToScopeModal.vue';
import {
  SearchOutlined,
  DownOutlined,
  ExclamationCircleOutlined,
  QuestionCircleOutlined,
  PlusOutlined,
  DeleteOutlined,
  BankOutlined,
  SyncOutlined,
  ReloadOutlined,
  FolderOpenOutlined,
  EditOutlined,
  LinkOutlined,
  DashboardOutlined,
  GlobalOutlined,
  RadarChartOutlined,
  ApartmentOutlined,
  InfoCircleOutlined,
  RightCircleOutlined,
  ScheduleOutlined,
  CloseOutlined,
  CloudDownloadOutlined,
  CheckCircleOutlined,
  SafetyCertificateOutlined,
  RocketOutlined,
  AppstoreOutlined,
  InboxOutlined,
  HolderOutlined,
  MoreOutlined,
  LeftOutlined,
  RightOutlined,
  CopyOutlined,
  FileTextOutlined,
  TagsOutlined
} from '@ant-design/icons-vue';
import { useRoute, useRouter } from 'vue-router';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import { copyText as copyToClipboard } from '../utils/clipboard';

const { t: assetText, locale: assetLocale } = useI18n({ useScope: 'global' });

const getBodyContainer = () => document.body;

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const dataSource = ref([]);
const searchForm = ref({ group_id: undefined });
const currentRecord = ref(null);
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

// 表格列定义
const columns = computed(() => {
  const baseColumns = [
    { title: assetText('tasks.assetGroupName'), key: 'name', width: 220, sorter: true },
    { title: assetText('assets.seedTargetsAndCoverage'), key: 'scope_and_stat', minWidth: 260 },
    { title: assetText('assets.assetScopeIdLabel'), key: 'scope_id', width: 150 },
    { title: assetText('tasks.actions'), key: 'action', width: 250, fixed: 'right' }
  ];
  if (activeGroupId.value === 'all') {
    baseColumns.splice(1, 0, { title: assetText('tasks.parentOrganization'), key: 'group_name', width: 120 });
  }
  return baseColumns;
});

// 获取主域名探测状态与展示样式
const getDomainStatus = (record, domain) => {
  if (!record || !domain) return 'unprobed';
  return record.domain_status?.[domain]?.status || 'unprobed';
};

const getDomainStatusLabel = (record, domain) => {
  const st = getDomainStatus(record, domain);
  if (st === 'probed') return assetText('assets.scannedLabel');
  if (st === 'scanning') return assetText('assets.scanningLabel');
  if (st === 'error') return assetText('assets.scanError');
  return assetText('assets.notScannedLabel');
};

const getDomainTagStyle = (record, domain) => {
  return {
    background: 'var(--arl-bg-light, #f8fafc)',
    color: 'var(--arl-text-color, #334155)',
    borderColor: 'var(--arl-border-color, #e2e8f0)',
    marginRight: '0'
  };
};

const getDomainTooltip = (record, domain) => {
  const meta = record?.domain_status?.[domain] || {};
  const statusLabel = getDomainStatusLabel(record, domain);
  const time = meta.last_probe_time || meta.sync_time || '-';
  return assetText('assets.domainDomainStatusStatusUpdatedTime', { domain: domain, status: statusLabel, time: time });
};

// 解析文本中的目标数组（去重去空小写）
const parseScopeList = (text) => {
  if (!text) return [];
  const rawList = text.split(/[\n,]+/);
  const seen = new Set();
  const result = [];
  for (let item of rawList) {
    item = item.trim().toLowerCase();
    if (item && !seen.has(item)) {
      seen.add(item);
      result.push(item);
    }
  }
  return result;
};

// 复制功能 (复用 utils/clipboard，兼容非 HTTPS 环境)
const copyText = async (text) => {
  const ok = await copyToClipboard(text);
  if (ok) {
    message.success(assetText('assets.copied'));
  } else {
    message.error(assetText('tasks.copyFailedPleaseSelectAndCopyManually'));
  }
};

// 域名标签优先级预排序（探测中 > 待测 > 异常 > 已测），预处理挂载到 _sorted_scopes 杜绝模板渲染卡顿
const processScopeItems = (items) => {
  const statusWeight = { scanning: 0, unprobed: 1, error: 2, probed: 3 };
  return (items || []).map(record => {
    const arr = record?.scope_array || [];
    let sorted = arr;
    if (arr.length > 5) {
      sorted = [...arr].sort((a, b) => {
        const weightA = statusWeight[getDomainStatus(record, a)] ?? 4;
        const weightB = statusWeight[getDomainStatus(record, b)] ?? 4;
        return weightA - weightB;
      });
    }
    return {
      ...record,
      _sorted_scopes: sorted
    };
  });
};


// 轮询调度管理：如果有正在扫描中的资产组，则每 5 秒静默轮询一次
let pollTimer = null;
const stopPoll = () => {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
};

const checkAndSchedulePoll = () => {
  stopPoll();
  const hasScanning = (dataSource.value || []).some(item => (item?.domain_stat?.scanning || 0) > 0);
  if (hasScanning) {
    pollTimer = setTimeout(() => {
      fetchData(true);
    }, 5000);
  }
};

// 拉取表格数据（增加防重与竞态保护）
let isFetching = false;
let currentFetchContextId = null;

const fetchData = async (silent = false) => {
  if (isFetching) return;
  isFetching = true;
  if (!silent) {
    loading.value = true;
  }

  const fetchContextId = activeGroupId.value;
  currentFetchContextId = fetchContextId;

  try {
    const params = { page: pagination.current, size: pagination.pageSize };
    for (const key in searchForm.value) {
      if (searchForm.value[key]) params[key] = searchForm.value[key];
    }
    const res = await request.get('/asset_scope/', { params });

    // 竞态防御：如果上下文 ID 已变更，说明已经切换了集团，直接丢弃本次请求结果
    if (currentFetchContextId !== fetchContextId) return;

    if (res.code === 200) {
      dataSource.value = processScopeItems(res.items || []);
      pagination.total = res.total || 0;
      if (!silent) {
        selectedRowKeys.value = [];
      }
      checkAndSchedulePoll();
    }
  } catch (error) {
    if (currentFetchContextId === fetchContextId) {
      message.error(assetText('assets.failedToLoadAssetGroups'));
    }
  } finally {
    if (currentFetchContextId === fetchContextId) {
      isFetching = false;
      if (!silent) {
        loading.value = false;
      }
    } else {
      isFetching = false;
    }
  }
};

const onSearch = () => { pagination.current = 1; fetchData(); };
const resetSearch = () => {
  searchForm.value = {};
  onSearch();
};
const handleTableChange = (page, pageSize) => { pagination.current = page; pagination.pageSize = pageSize; fetchData(); };


const isSidebarCollapsed = ref(false);
const activeGroupId = ref('all');
const groupSearchKey = ref('');
const groupList = ref([]);
const filteredGroupList = computed(() => {
  if (!groupSearchKey.value) return groupList.value;
  return groupList.value.filter(g => g.name.toLowerCase().includes(groupSearchKey.value.toLowerCase()));
});

const currentGroupName = computed(() => {
  if (activeGroupId.value === 'all') return assetText('assets.allAssetGroups');
  if (activeGroupId.value === 'unassigned') return assetText('assets.ungrouped');
  const g = groupList.value.find(x => x._id === activeGroupId.value);
  return g ? g.name : assetText('assets.unknownOrganizationGroup');
});

// Sortable 拖拽排序逻辑
const draggableGroupListRef = ref(null);
let sortableInstance = null;
let originalListSnapshot = null;
let saveOrderTimer = null;

const initSortable = () => {
  if (!draggableGroupListRef.value) return;
  if (sortableInstance) {
    sortableInstance.destroy();
    sortableInstance = null;
  }
  sortableInstance = new Sortable(draggableGroupListRef.value, {
    animation: 150,
    handle: '.group-drag-handle',
    ghostClass: 'group-drag-ghost',
    chosenClass: 'group-drag-chosen',
    dragClass: 'group-drag-active',
    filter: '.group-action-icon, .ant-dropdown-trigger, .group-drag-handle-disabled',
    preventOnFilter: false,
    disabled: !!groupSearchKey.value,
    onEnd: (evt) => {
      const { oldIndex, newIndex, item, from } = evt;
      if (oldIndex === newIndex || oldIndex == null || newIndex == null) return;

      // 记录首轮拖动前的原始快照（用于故障原子回滚）
      if (!originalListSnapshot) {
        originalListSnapshot = [...groupList.value];
      }

      // 核心加固：撤销 Sortable 的物理 DOM 变更，使真实 DOM 树与 Vue 虚拟 DOM 现有状态对齐，杜绝高亮激活项重复插入
      if (from && item && item.parentNode === from) {
        from.removeChild(item);
        if (oldIndex >= from.children.length) {
          from.appendChild(item);
        } else {
          from.insertBefore(item, from.children[oldIndex]);
        }
      }

      // 乐观重排前端响应式数据
      const movedItem = groupList.value.splice(oldIndex, 1)[0];
      groupList.value.splice(newIndex, 0, movedItem);

      // 防抖触发持久化保存
      triggerSaveOrder();
    }
  });
};

const triggerSaveOrder = () => {
  if (saveOrderTimer) clearTimeout(saveOrderTimer);
  saveOrderTimer = setTimeout(async () => {
    const rollbackSnapshot = originalListSnapshot;
    originalListSnapshot = null;
    try {
      const orderIds = groupList.value.map(g => g._id);
      const res = await request.post('/asset_group/reorder/', { order_ids: orderIds });
      if (res.code === 200) {
        groupList.value.forEach((g, idx) => {
          g.sort_order = idx;
        });
      } else {
        message.error(res.message || assetText('assets.failedToSaveTheOrderThePreviousOrder'));
        if (rollbackSnapshot) {
          groupList.value = rollbackSnapshot;
        }
      }
    } catch (err) {
      message.error(assetText('assets.networkRequestFailedThePreviousOrderWasRestored'));
      if (rollbackSnapshot) {
        groupList.value = rollbackSnapshot;
      }
    }
  }, 400);
};

watch(groupSearchKey, (newVal) => {
  if (sortableInstance) {
    sortableInstance.option('disabled', !!newVal);
  }
});

// fetch groups
const fetchGroups = async () => {
  try {
    const res = await request.get('/asset_group/', { params: { size: 1000 } });
    if (res.code === 200) {
      groupList.value = res.items || [];
      nextTick(() => {
        initSortable();
      });
    }
  } catch (err) {}
};

// handle group switch with confirmation guard
const handleGroupSwitch = (info) => {
  const newKey = (info && typeof info === 'object' && info.key) ? info.key : info;
  if (newKey === activeGroupId.value) return;

  if (selectedRowKeys.value.length > 0) {
    Modal.confirm({
      title: assetText('assets.switchOrganizationGroup'),
      content: assetText('assets.youHaveSelectedCountAssetGroupsSwitchingViews', { count: selectedRowKeys.value.length }),
      onOk: () => {
        selectedRowKeys.value = [];
        activeGroupId.value = newKey;
      }
    });
  } else {
    activeGroupId.value = newKey;
  }
};

watch(activeGroupId, (newVal) => {
  selectedRowKeys.value = [];
  searchForm.value.group_id = newVal === 'all' ? undefined : newVal;
  pagination.current = 1;
  fetchData();
});

// 集团上下文与删除处置状态
const currentGroupObj = computed(() => {
  return groupList.value.find(x => x._id === activeGroupId.value);
});

const deleteGroupModalVisible = ref(false);
const deleteGroupLoading = ref(false);
const deleteGroupTarget = ref(null);
const deleteGroupForm = reactive({
  action: 'dissolve',
  target_group_id: undefined
});

const availableTransferGroups = computed(() => {
  if (!deleteGroupTarget.value) return [];
  return groupList.value.filter(g => g._id !== deleteGroupTarget.value._id);
});

const handleCurrentGroupDropdownClick = (e) => {
  const group = currentGroupObj.value;
  if (!group) return;
  if (e.key === 'edit') {
    enterpriseGroupForm.isEdit = true;
    enterpriseGroupForm._id = group._id;
    enterpriseGroupForm.name = group.name;
    enterpriseGroupModalVisible.value = true;
  } else if (e.key === 'delete') {
    triggerDeleteGroup(group);
  }
};

const triggerDeleteGroup = (group) => {
  if (!group) return;
  if ((group.scope_count || 0) === 0) {
    Modal.confirm({
      title: assetText('assets.deleteOrganizationGroup'),
      content: assetText('assets.permanentlyDeleteEmptyOrganizationGroupNameThisCannot', { name: group.name }),
      okType: 'danger',
      okText: assetText('tasks.confirm'),
      cancelText: assetText('assets.cancel'),
      onOk: async () => {
        try {
          const res = await request.post('/asset_group/delete/', { _id: group._id, action: 'dissolve' });
          if (res.code === 200) {
            message.success(assetText('assets.organizationGroupDeleted'));
            if (activeGroupId.value === group._id) {
              activeGroupId.value = 'all'; // Fallback focus
            }
            await fetchGroups();
          } else {
            message.error(res.message || assetText('tasks.deletionFailedLabel'));
          }
        } catch (err) {
          message.error(assetText('tasks.requestFailed'));
        }
      }
    });
  } else {
    deleteGroupTarget.value = group;
    deleteGroupForm.action = 'dissolve';
    deleteGroupForm.target_group_id = undefined;
    deleteGroupModalVisible.value = true;
  }
};

const confirmDeleteGroupWithDisposal = async () => {
  if (!deleteGroupTarget.value) return;
  const targetId = deleteGroupTarget.value._id;
  const isCurrentActive = activeGroupId.value === targetId;
  const action = deleteGroupForm.action;
  const targetGroupId = deleteGroupForm.target_group_id;

  if (action === 'transfer' && !targetGroupId) {
    message.warning(assetText('assets.selectTargetOrganization'));
    return;
  }

  deleteGroupLoading.value = true;
  try {
    const payload = {
      _id: targetId,
      action: action
    };
    if (action === 'transfer') {
      payload.target_group_id = targetGroupId;
    }
    const res = await request.post('/asset_group/delete/', payload);
    if (res.code === 200) {
      message.success(assetText('assets.organizationGroupDeleted'));
      deleteGroupModalVisible.value = false;

      // 智能上下文流转
      if (isCurrentActive) {
        if (action === 'transfer') {
          activeGroupId.value = targetGroupId;
        } else {
          activeGroupId.value = 'unassigned';
        }
      } else {
        if (['all', 'unassigned', targetGroupId].includes(activeGroupId.value)) {
          fetchData();
        }
      }
      await fetchGroups();
    } else {
      message.error(res.message || assetText('tasks.deletionFailedLabel'));
    }
  } catch (err) {
    message.error(assetText('tasks.requestFailed'));
  } finally {
    deleteGroupLoading.value = false;
  }
};

// Group Actions
const handleGroupAction = (e, group) => {
  if (e.key === 'edit') {
    enterpriseGroupForm.isEdit = true;
    enterpriseGroupForm._id = group._id;
    enterpriseGroupForm.name = group.name;
    enterpriseGroupModalVisible.value = true;
  } else if (e.key === 'delete') {
    triggerDeleteGroup(group);
  }
};

// 快捷新建集团轻量弹窗状态与方法
const quickGroupModalVisible = ref(false);
const quickGroupLoading = ref(false);
const quickGroupName = ref('');
const quickGroupTargetContext = ref('wizard'); // 'wizard' | 'manual' | 'edit'

const openQuickCreateGroup = (context) => {
  quickGroupTargetContext.value = context;
  quickGroupName.value = '';
  quickGroupModalVisible.value = true;
};

const handleQuickGroupSubmit = async () => {
  const name = quickGroupName.value.trim();
  if (!name) {
    message.warning(assetText('assets.enterAnOrganizationGroupName'));
    return;
  }
  quickGroupLoading.value = true;
  try {
    const res = await request.post('/asset_group/', { name });
    if (res.code === 200) {
      const newId = res.data?._id;
      message.success(assetText('assets.organizationGroupCreated'));
      quickGroupModalVisible.value = false;
      await fetchGroups();
      if (newId) {
        if (quickGroupTargetContext.value === 'wizard') {
          wizardForm.group_id = newId;
        } else if (quickGroupTargetContext.value === 'manual') {
          addForm.group_id = newId;
        } else if (quickGroupTargetContext.value === 'edit') {
          editGroupForm.group_id = newId;
        }
      }
    } else {
      message.error(res.message || assetText('tasks.operationFailedLabel'));
    }
  } catch (err) {
    message.error(assetText('tasks.requestFailed'));
  } finally {
    quickGroupLoading.value = false;
  }
};

// Enterprise Group Modal
const enterpriseGroupModalVisible = ref(false);
const enterpriseGroupLoading = ref(false);
const enterpriseGroupForm = reactive({ isEdit: false, _id: '', name: '', description: '' });

const openAddEnterpriseGroupModal = () => {
  enterpriseGroupForm.isEdit = false;
  enterpriseGroupForm._id = '';
  enterpriseGroupForm.name = '';
  enterpriseGroupForm.description = '';
  enterpriseGroupModalVisible.value = true;
};

const submitEnterpriseGroup = async () => {
  if (!enterpriseGroupForm.name) {
    message.warning(assetText('assets.enterAnOrganizationGroupName'));
    return;
  }
  enterpriseGroupLoading.value = true;
  try {
    let res;
    if (enterpriseGroupForm.isEdit) {
      res = await request.post('/asset_group/edit/', { _id: enterpriseGroupForm._id, name: enterpriseGroupForm.name });
    } else {
      res = await request.post('/asset_group/', { name: enterpriseGroupForm.name, description: enterpriseGroupForm.description });
    }
    if (res.code === 200) {
      message.success(enterpriseGroupForm.isEdit ? assetText('assets.renamed') : assetText('assets.organizationGroupCreated'));
      enterpriseGroupModalVisible.value = false;
      fetchGroups();
    } else {
      message.error(res.message || assetText('tasks.operationFailedLabel'));
    }
  } catch(err) {
    message.error(assetText('tasks.requestFailed'));
  } finally {
    enterpriseGroupLoading.value = false;
  }
};

// Batch Move Modal
const batchMoveModalVisible = ref(false);
const batchMoveLoading = ref(false);
const batchMoveTargetGroupId = ref(undefined);

const openBatchMoveModal = () => {
  batchMoveTargetGroupId.value = undefined;
  batchMoveModalVisible.value = true;
};

const submitBatchMove = async () => {
  if (!batchMoveTargetGroupId.value) {
    message.warning(assetText('assets.selectADestinationOrganizationGroup'));
    return;
  }
  batchMoveLoading.value = true;
  try {
    const res = await request.post('/asset_scope/batch_move_group/', {
      scope_ids: selectedRowKeys.value,
      group_id: batchMoveTargetGroupId.value === 'unassigned' ? '' : batchMoveTargetGroupId.value
    });
    if (res.code === 200) {
      message.success(assetText('assets.selectedGroupsMoved'));
      batchMoveModalVisible.value = false;
      selectedRowKeys.value = [];
      fetchData();
      fetchGroups();
    } else {
      message.error(res.message || assetText('assets.failedToMoveAssetGroups'));
    }
  } catch(err) {
    message.error(assetText('tasks.requestFailed'));
  } finally {
    batchMoveLoading.value = false;
  }
};

// initialize
let siderObserver = null;

onMounted(() => {
  if (route.path === '/group') {
    fetchGroups();
  }
  updateSidebarLeft();
  window.addEventListener('resize', updateSidebarLeft);
  const siderEl = document.querySelector('.ant-layout-sider');
  if (siderEl) {
    const handleSiderChange = () => {
      updateSidebarLeft();
      setTimeout(updateSidebarLeft, 250);
      setTimeout(updateSidebarLeft, 550);
    };
    siderObserver = new MutationObserver(handleSiderChange);
    siderObserver.observe(siderEl, { attributes: true, attributeFilter: ['style', 'class'] });
    siderEl.addEventListener('transitionend', updateSidebarLeft);
  }
  loadPendingReconTasks();
  if (pendingReconTasks.value.some(t => t.status === 'running')) {
    pollRunningReconTasks();
    startReconPoller();
  }
});

onActivated(() => {
  if (route.path === '/group') {
    fetchGroups();
    fetchData(true);
  }
  updateSidebarLeft();
  loadPendingReconTasks();
  if (pendingReconTasks.value.some(t => t.status === 'running')) {
    pollRunningReconTasks();
    startReconPoller();
  }
});

// Update the initial addForm and editGroupForm state definitions

// ================= 新建资产组逻辑 =================
const addModalVisible = ref(false);
const addLoading = ref(false);
const addFormRef = ref();

const addForm = reactive({
  group_id: undefined,
  name: '',
  scope: ''
});

const addRules = {
  name: [{ required: true, get message() { return assetText('tasks.enterAnAssetGroupName'); }, trigger: 'blur' }],
  scope: [{ required: true, get message() { return assetText('assets.enterAssetScopeTargets'); }, trigger: 'blur' }]
};

// 新建资产组模式与向导状态
const creationMode = ref('wizard'); // 'wizard' | 'manual'
const wizardStep = ref(1);
const wizardLoading = ref(false);
const wizardLoadingTip = computed(() => assetText('assets.startingEnterpriseDiscovery'));
const wizardTaskId = ref('');
const wizardDomains = ref([]);
const selectedWizardDomains = ref([]);
const wizardDomainSearch = ref('');
const wizardAutoSync = ref(true); // 测绘完成后是否由后端自动纳管建组
const wizardAutoScan = ref(false);
const wizardTaskType = ref('oneshot');
const wizardPolicyId = ref('');
const wizardSubmitting = ref(false);
const policyList = ref([]);
const wizardEngine = ref('tyc'); // 'tyc' | 'icp'
const wizardTargetError = ref('');

const wizardForm = reactive({
  group_id: undefined,
  target: '',
  name: '',
  depth: 1,
  invest_ratio: 50,
  enable_icp: true
});

const parseTycInput = (input) => {
  if (!input) return { gid: '', isUrl: false, isName: false, raw: '' };
  const str = input.trim();
  const urlMatch = str.match(/(?:tianyancha\.com\/company\/|^company\/)([a-zA-Z0-9]+)/i);
  if (urlMatch && urlMatch[1]) {
    return { gid: urlMatch[1], isUrl: true, isName: false, raw: str };
  }
  // 仅纯数字串视为 GID（天眼查 GID 为数字）；其余字母数字混排（如 "alibaba"）
  // 按企业名称处理，交由后端检索匹配，避免误把普通输入当成 GID。
  if (/^\d+$/.test(str)) {
    return { gid: str, isUrl: false, isName: false, raw: str };
  }
  if (str.length >= 2) {
    return { gid: '', isUrl: false, isName: true, raw: str };
  }
  return { gid: '', isUrl: false, isName: false, raw: str };
};

const parsedTycGid = computed(() => {
  if (!wizardForm.target) return '';
  const parsed = parseTycInput(wizardForm.target);
  return parsed.gid;
});

const isWizardCompanyName = computed(() => {
  if (!wizardForm.target) return false;
  const parsed = parseTycInput(wizardForm.target);
  return parsed.isName;
});

const onTycTargetChange = () => {
  wizardTargetError.value = '';
};

const getGroupName = (gid) => {
  const g = groupList.value.find(item => item._id === gid);
  return g ? g.name : '';
};

const filteredWizardDomains = computed(() => {
  if (!wizardDomainSearch.value.trim()) return wizardDomains.value;
  return wizardDomains.value.filter(d => d.includes(wizardDomainSearch.value.trim().toLowerCase()));
});

const toggleWizardDomain = (d, checked) => {
  if (checked) {
    if (!selectedWizardDomains.value.includes(d)) selectedWizardDomains.value.push(d);
  } else {
    selectedWizardDomains.value = selectedWizardDomains.value.filter(item => item !== d);
  }
};

const selectAllWizardDomains = () => {
  selectedWizardDomains.value = wizardDomains.value.slice();
};

// ================= 企业测绘后台异步追踪与免等建组 =================
const PENDING_RECON_KEY = 'arl_pending_wizard_recon_tasks';
const pendingReconTasks = ref([]);
const activeResumeTaskId = ref('');

const loadPendingReconTasks = () => {
  try {
    const raw = localStorage.getItem(PENDING_RECON_KEY);
    if (raw) {
      const parsed = JSON.parse(raw);
      if (Array.isArray(parsed)) {
        const now = Date.now();
        // 仅保留仍在运行且未超 7 天兜底时限的追踪项（护航跨天超长测绘任务，真实终态由 pollRunningReconTasks 实时向后端核验收敛）；
        // 凡被过滤的残留项立即回写 localStorage，规避因未持久化回写导致每次切页重复读取的问题。
        const valid = parsed.filter(
          t => t && t.status === 'running' && (now - (t.startTime || 0)) < 7 * 86400000
        );
        pendingReconTasks.value = valid;
        if (valid.length !== parsed.length) {
          savePendingReconTasks();
        }
      } else {
        pendingReconTasks.value = [];
        localStorage.removeItem(PENDING_RECON_KEY);
      }
    }
  } catch (e) {
    console.error('Failed to load pending recon tasks', e);
  }
};

const savePendingReconTasks = () => {
  try {
    localStorage.setItem(PENDING_RECON_KEY, JSON.stringify(pendingReconTasks.value));
  } catch (e) {
    console.error('Failed to save pending recon tasks', e);
  }
};

const addPendingReconTask = (task) => {
  const existingIdx = pendingReconTasks.value.findIndex(t => t.taskId === task.taskId);
  if (existingIdx >= 0) {
    pendingReconTasks.value[existingIdx] = task;
  } else {
    pendingReconTasks.value.unshift(task);
  }
  savePendingReconTasks();
};

const dismissPendingReconTask = (taskId) => {
  pendingReconTasks.value = pendingReconTasks.value.filter(t => t.taskId !== taskId);
  savePendingReconTasks();
  notification.close(`recon_done_${taskId}`);
};

const clearAllRunningReconTasks = () => {
  pendingReconTasks.value = [];
  savePendingReconTasks();
  stopReconPoller();
  message.success(assetText('assets.enterpriseDiscoveryGroupQueueCleared'));
};

const runningReconTasks = computed(() => {
  return pendingReconTasks.value.filter(t => t.status === 'running');
});

let reconPollerTimer = null;
let isPollingRecon = false;

const startReconPoller = () => {
  if (reconPollerTimer) return;
  reconPollerTimer = setInterval(pollRunningReconTasks, 4000);
};

const stopReconPoller = () => {
  if (reconPollerTimer) {
    clearInterval(reconPollerTimer);
    reconPollerTimer = null;
  }
};

const pollRunningReconTasks = async () => {
  if (isPollingRecon) return;
  const runningTasks = pendingReconTasks.value.filter(t => t.status === 'running');
  if (runningTasks.length === 0) {
    stopReconPoller();
    return;
  }

  isPollingRecon = true;
  try {
    for (const task of runningTasks) {
      try {
        const checkRes = await request.get('/icp/task', { params: { _id: task.taskId } });
        if (checkRes.code === 200 && checkRes.items) {
          if (checkRes.items.length === 0) {
            // 数据库中该任务已不存在（已被删除），立即收敛移除追踪，不再轮询
            dismissPendingReconTask(task.taskId);
            continue;
          }

          const taskObj = checkRes.items[0];
          // 关键：只要任务不是 running 也不是 waiting，一律从运行追踪队列收敛
          if (taskObj.status !== 'running' && taskObj.status !== 'waiting') {
            if (taskObj.status === 'stop') {
              dismissPendingReconTask(task.taskId);
              notification.warning({
                key: `recon_stop_${task.taskId}`,
                message: assetText('assets.enterpriseDiscoveryStoppedManuallyName', { name: task.name || task.target }),
                description: assetText('assets.theTaskWasStoppedNoAssetGroupWill'),
                duration: 6
              });
              continue;
            }

            if (taskObj.status === 'error') {
              dismissPendingReconTask(task.taskId);
              notification.error({
                key: `recon_err_${task.taskId}`,
                message: assetText('assets.enterpriseDiscoveryFailedName', { name: task.name || task.target }),
                description: taskObj.error_msg || assetText('assets.theDiscoveryTaskFailedCheckItsExecutionLogs')
              });
              continue;
            }

            if (taskObj.status === 'done') {
              // 若开启了自动建组 (autoSync 默认开启)，统一由后端消费建组并回写结果，前端仅读取结果展示
              if (task.autoSync) {
                if (taskObj.auto_group && !taskObj.auto_group_result && !taskObj.synced_scope_id) {
                  // 后端正在执行自动建组中，等待下一轮轮询结果
                  continue;
                }
                const targetName = taskObj.synced_scope_name || task.groupName || taskObj.company_name || (task.name ? task.name.replace(/(?:企业全景测绘|企业测绘|全景测绘)$/, '') : ('TYC_' + task.target));
                dismissPendingReconTask(task.taskId);

                if (taskObj.auto_group_result === 'no_domain') {
                  notification.warning({
                    key: `recon_done_${task.taskId}`,
                    message: assetText('assets.noWebsiteDomainsFoundByEnterpriseDiscoveryName', { name: task.name || task.target }),
                    description: assetText('assets.companyRelationshipsAndIcpRecordsWereQueriedBut'),
                    duration: 6
                  });
                } else if (taskObj.auto_group_result === 'error' && !taskObj.synced_scope_id) {
                  notification.error({
                    key: `recon_done_${task.taskId}`,
                    message: assetText('assets.automaticGroupCreationFailedName', { name: targetName }),
                    description: taskObj.auto_group_msg || assetText('assets.assetImportFailed')
                  });
                } else {
                  const domainCount = taskObj.auto_group_domain_count ?? (taskObj.statistic?.web_cnt || 0);
                  notification.success({
                    key: `recon_done_${task.taskId}`,
                    message: assetText('assets.enterpriseAssetGroupCreatedAutomatically'),
                    description: assetText('assets.assetGroupCreatedForNameWithCountWebsite', {
                      name: targetName,
                      count: domainCount,
                      details: task.autoScan ? assetText('assets.activeDiscoveryTasksHaveAlsoBeenQueued') : ''
                    }),
                    duration: 8
                  });
                  fetchData();
                }
              } else {
                // 用户显式取消了自动成组，拉取域名列表并弹出手动挑选引导，同时从 localStorage 移除避免残留
                const assetRes = await request.get('/icp/asset', { params: { task_id: task.taskId, query_type: 'web', size: 5000 } });
                const domainSet = new Set();
                if (assetRes.code === 200 && assetRes.items) {
                  assetRes.items.forEach(item => {
                    const d = item.domain || item.ym;
                    if (d && typeof d === 'string') domainSet.add(d.trim().toLowerCase());
                  });
                }
                const domainList = Array.from(domainSet);
                const completedTask = { ...task, status: 'done', domains: domainList };
                dismissPendingReconTask(task.taskId);

                notification.success({
                  key: `recon_done_${task.taskId}`,
                  message: assetText('assets.enterpriseDiscoveryCompletedName', { name: task.name || task.target }),
                  description: assetText('assets.websiteDomainsFoundCountSelectDomainsToSave', { count: domainList.length }),
                  btn: () => h(
                    Button,
                    {
                      type: 'primary',
                      size: 'small',
                      onClick: () => {
                        notification.close(`recon_done_${task.taskId}`);
                        resumeWizardFromCompletedTask(completedTask);
                      }
                    },
                    { default: () => assetText('assets.selectDomainsAndCreateGroup') }
                  ),
                  duration: 0
                });
              }
              continue;
            }

            // 兜底任何其他非运行状态
            dismissPendingReconTask(task.taskId);
          }
        }
      } catch (err) {
        console.error(`Error polling recon task ${task.taskId}`, err);
      }
    }
  } finally {
    isPollingRecon = false;
  }
};

const resumeWizardFromCompletedTask = async (task) => {
  creationMode.value = 'wizard';
  wizardStep.value = 2;
  wizardTaskId.value = task.taskId;
  wizardForm.group_id = task.group_id;
  wizardForm.target = task.target;
  wizardForm.name = task.name.startsWith('TYC_') ? '' : task.name.replace(/(?:企业测绘|全景测绘)$/, '');
  wizardDomains.value = task.domains || [];
  selectedWizardDomains.value = (task.domains || []).slice();
  wizardDomainSearch.value = '';
  wizardAutoScan.value = false;
  activeResumeTaskId.value = task.taskId;

  if (policyList.value.length === 0) {
    try {
      const pRes = await request.get('/policy/', { params: { size: 100 } });
      if (pRes.code === 200 && pRes.items?.length > 0) {
        policyList.value = pRes.items;
        wizardPolicyId.value = pRes.items[0]._id;
      }
    } catch (e) {
      console.error(e);
    }
  }

  addModalVisible.value = true;
};

// 自动纳管建组意图随任务一并下发，由后端调度器消费。
// 这样建组不再依赖当前浏览器页面存活，关闭页面也会正常完成。
const buildAutoGroupIntent = () => ({
  auto_group: wizardAutoSync.value,
  auto_group_scan: wizardAutoScan.value,
  auto_group_task_type: wizardTaskType.value || 'oneshot',
  auto_group_policy_id: wizardPolicyId.value || '',
  auto_group_interval_hours: 24,
  group_id: wizardForm.group_id || ''
});

const startWizardRecon = async () => {
  wizardTargetError.value = '';
  const rawTarget = (wizardForm.target || '').trim();
  const customName = (wizardForm.name || '').trim();

  if (!rawTarget) {
    wizardTargetError.value = assetText('assets.enterATianyanchaCompanyUrlGidOrFull');
    return;
  }

  const parsed = parseTycInput(rawTarget);
  if (!parsed.gid && !parsed.isName) {
    wizardTargetError.value = assetText('assets.noValidTargetRecognizedEnterACompanyUrl');
    return;
  }

  // 校验自动扫描策略
  if (wizardAutoScan.value && !wizardPolicyId.value) {
    message.warning(assetText('assets.automaticDiscoveryIsEnabledSelectAScanPolicy'));
    return;
  }

  wizardLoading.value = true;
  try {
    let taskId = '';
    let taskName = '';
    let isTycUpgraded = false;

    if (parsed.gid) {
      taskName = customName ? (customName + '全景测绘') : ('TYC_' + parsed.gid);
      const payload = {
        name: taskName,
        gid: parsed.gid,
        depth: wizardForm.depth || 1,
        invest_ratio: wizardForm.invest_ratio || 50,
        enable_icp: wizardForm.enable_icp !== false,
        query_type: ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo'],
        ...buildAutoGroupIntent()
      };
      if (customName) {
        payload.company_name = customName;
      }
      const taskRes = await request.post('/icp/tyc_task', payload);
      if (!taskRes || taskRes.code !== 200) {
        const errMsg = taskRes?.message || assetText('assets.failedToStartEnterpriseDiscovery');
        wizardLoading.value = false;
        if (errMsg.includes('bannedLocation') || errMsg.includes('地域围栏拦截')) {
          Modal.confirm({
            title: assetText('tasks.tianyanchaLocationRestrictedTitle'),
            content: assetText('tasks.tianyanchaLocationRestrictedContent'),
            okText: assetText('tasks.configureSystemProxy'),
            cancelText: assetText('tasks.stayOnThisPage'),
            onOk() {
              addModalVisible.value = false;
              router.push({ path: '/systemSettings', query: { tab: 'system_general', focus: 'proxy' } });
            }
          });
          return;
        }
        message.error(errMsg);
        return;
      }
      taskId = taskRes.data?.task_id || taskRes.data?._id || taskRes.task_id;
    } else {
      taskName = customName || rawTarget;
      const payload = {
        name: taskName,
        target: rawTarget,
        depth: wizardForm.depth || 1,
        invest_ratio: wizardForm.invest_ratio || 50,
        enable_icp: wizardForm.enable_icp !== false,
        query_type: ['invest', 'web', 'app', 'mapp', 'wechat', 'weibo'],
        ...buildAutoGroupIntent()
      };
      const taskRes = await request.post('/icp/task', payload);
      if (!taskRes || taskRes.code !== 200) {
        message.error(taskRes?.message || assetText('assets.failedToStartEnterpriseDiscovery'));
        wizardLoading.value = false;
        return;
      }
      taskId = taskRes.data?.task_id || taskRes.data?._id || taskRes.task_id;
      isTycUpgraded = !!taskRes.data?.matched_tyc;
    }

    wizardTaskId.value = taskId;

    // 立即关闭弹窗，改为后台异步追踪建组状态
    addModalVisible.value = false;
    wizardLoading.value = false;

    // 注册到后台追踪队列
    addPendingReconTask({
      taskId: taskId,
      engine: (parsed.gid || isTycUpgraded) ? 'tyc' : 'icp',
      name: taskName,
      target: parsed.gid || rawTarget,
      groupName: customName,
      group_id: wizardForm.group_id || '',
      autoSync: wizardAutoSync.value,
      autoScan: wizardAutoScan.value,
      taskType: wizardTaskType.value,
      policyId: wizardPolicyId.value,
      status: 'running',
      startTime: Date.now()
    });

    // 启动非阻塞轮询器
    startReconPoller();

    // 弹出通知
    notification.info({
      key: `recon_start_${taskId}`,
      message: assetText('assets.enterpriseDiscoveryAndGroupCreationQueued'),
      description: wizardAutoSync.value
        ? assetText('assets.enterpriseDiscoveryQueuedForTargetTheServerWill', { target: taskName })
        : assetText('assets.enterpriseDiscoveryQueuedForTargetYouWillBe', { target: taskName }),
      duration: 4.5
    });

  } catch (err) {
    message.error(assetText('assets.networkRequestFailed'));
    wizardLoading.value = false;
  }
};

const submitWizardSync = async () => {
  if (selectedWizardDomains.value.length === 0) {
    message.warning(assetText('assets.selectAtLeastOneDomainToSave'));
    return;
  }
  wizardSubmitting.value = true;
  try {
    const payload = {
      mode: 'new',
      target_name: wizardForm.name.trim() || ('TYC_' + wizardForm.target.trim()),
      group_id: wizardForm.group_id || '',
      selected_domains: selectedWizardDomains.value,
      auto_scan: wizardAutoScan.value,
      task_type: wizardTaskType.value,
      policy_id: wizardPolicyId.value
    };
    const res = await request.post(`/icp/sync/${wizardTaskId.value}`, payload);
    if (res.code === 200) {
      message.success(assetText('assets.assetGroupCreatedAndAssetsImported'));
      addModalVisible.value = false;
      if (activeResumeTaskId.value) {
        dismissPendingReconTask(activeResumeTaskId.value);
        activeResumeTaskId.value = '';
      } else if (wizardTaskId.value) {
        dismissPendingReconTask(wizardTaskId.value);
      }
      fetchData();
    } else {
      message.error(res.message || assetText('assets.failedToSaveAssets'));
    }
  } catch (err) {
    message.error(assetText('assets.networkRequestFailed'));
  } finally {
    wizardSubmitting.value = false;
  }
};

// 增量同步弹窗
const syncIncrementModalVisible = ref(false);
const currentIncrementTask = ref(null);

const openSyncIncrement = async (record) => {
  if (!record.synced_icp_task_id) return;
  try {
    const res = await request.get('/icp/task', { params: { _id: record.synced_icp_task_id } });
    if (res.code === 200 && res.items && res.items.length > 0) {
      currentIncrementTask.value = res.items[0];
      syncIncrementModalVisible.value = true;
    } else {
      message.error(assetText('assets.noRelatedEnterpriseDiscoveryTaskFound'));
    }
  } catch (err) {
    message.error(assetText('assets.failedToLoadTask'));
  }
};

const handleIncrementSyncSuccess = () => {
  fetchData();
};


// 资产组绑定已有企业主体
const bindScopeModalVisible = ref(false);
const bindScopeLoading = ref(false);
const currentBindingScope = ref(null);
const selectedBindScopeTaskId = ref(undefined);
const completedIcpTasks = ref([]);

const openBindEnterprise = async (record) => {
  currentBindingScope.value = record;
  selectedBindScopeTaskId.value = undefined;
  bindScopeModalVisible.value = true;
  try {
    const res = await request.get('/icp/task', { params: { size: 100 } });
    if (res.code === 200) {
      completedIcpTasks.value = res.items || [];
    }
  } catch (err) {
    console.error(err);
  }
};

const submitBindScopeEnterprise = async () => {
  if (!selectedBindScopeTaskId.value) {
    message.warning(assetText('assets.selectAnEnterpriseDiscoveryTaskToLink'));
    return;
  }
  bindScopeLoading.value = true;
  try {
    const res = await request.post('/asset_scope/bind_enterprise/', {
      scope_id: currentBindingScope.value._id,
      task_id: selectedBindScopeTaskId.value
    });
    if (res && res.code === 200) {
      message.success(assetText('assets.organizationLinked'));
      bindScopeModalVisible.value = false;
      fetchData();
    } else {
      message.error(res.message || assetText('assets.failedToLinkOrganization'));
    }
  } catch (err) {
    message.error(assetText('assets.networkRequestFailed'));
  } finally {
    bindScopeLoading.value = false;
  }
};

const goToOsintDetail = (record) => {
  router.push({
    path: '/groupAssetsManagement/groupAssetsDetail',
    query: { scope_id: record._id, targetName: record.name, view: 'osint' }
  });
};

const openAddModal = async () => {
  creationMode.value = 'wizard';
  wizardStep.value = 1;
  wizardEngine.value = 'tyc';
  wizardAutoSync.value = true;
  wizardAutoScan.value = false;
  wizardTaskType.value = 'oneshot';
  wizardTargetError.value = '';

  const defaultGroupId = (activeGroupId.value === 'all' || activeGroupId.value === 'unassigned') ? undefined : activeGroupId.value;
  wizardForm.group_id = defaultGroupId;
  wizardForm.target = '';
  wizardForm.name = '';
  wizardForm.depth = 1;
  wizardForm.invest_ratio = 50;
  wizardForm.enable_icp = true;
  wizardDomains.value = [];
  selectedWizardDomains.value = [];
  wizardDomainSearch.value = '';

  addForm.group_id = defaultGroupId;
  addForm.name = '';
  addForm.scope = '';

  // 预拉取扫描策略列表供自动探测选择
  if (policyList.value.length === 0) {
    try {
      const pRes = await request.get('/policy/', { params: { size: 100 } });
      if (pRes.code === 200 && pRes.items?.length > 0) {
        policyList.value = pRes.items;
        if (!wizardPolicyId.value) {
          wizardPolicyId.value = pRes.items[0]._id;
        }
      }
    } catch (e) {
      console.error('预拉取策略列表失败', e);
    }
  }

  addModalVisible.value = true;
};

const handleAddSubmit = async () => {
  try {
    await addFormRef.value.validate();
    addLoading.value = true;
    const res = await request.post('/asset_scope/', addForm);

    if (res.code === 200) {
      message.success(assetText('assets.assetGroupCreated'));
      addModalVisible.value = false;
      pagination.current = 1;
      fetchData();
    } else {
      message.error(assetText('assets.failedToCreateAssetGroup') + (res.message || assetText('tasks.unknownError')));
    }
  } catch (error) {
    console.warn('提交中断或校验失败', error);
  } finally {
    addLoading.value = false;
  }
};

// ================= 编辑资产组逻辑 =================
const editGroupModalVisible = ref(false);
const editGroupLoading = ref(false);
const editGroupFormRef = ref();
const editGroupMode = ref('visual'); // 'visual' | 'text'
const editGroupScopeList = ref([]);
const editGroupSearchKeyword = ref('');
const editGroupNewInput = ref('');

const editGroupForm = reactive({
  _id: '',
  group_id: undefined,
  name: '',
  scope: ''
});

const editGroupRules = {
  name: [{ required: true, get message() { return assetText('tasks.enterAnAssetGroupName'); }, trigger: 'blur' }],
  scope: [
    {
      validator: async () => {
        const list = editGroupMode.value === 'visual'
          ? editGroupScopeList.value
          : parseScopeList(editGroupForm.scope);
        if (!list || list.length === 0) {
          return Promise.reject(new Error(assetText('assets.enterOrRetainAtLeastOneScopeTarget')));
        }
        return Promise.resolve();
      },
      trigger: 'change'
    }
  ]
};

// 搜索过滤后的资产列表
const filteredScopeList = computed(() => {
  const keyword = editGroupSearchKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return editGroupScopeList.value;
  }
  return editGroupScopeList.value.filter(item => item.toLowerCase().includes(keyword));
});

// 打开编辑分组弹窗
const openEditGroupModal = (record) => {
  currentRecord.value = record;
  editGroupForm._id = record._id;
  editGroupForm.group_id = record.group_id || undefined;
  editGroupForm.name = record.name || '';
  editGroupScopeList.value = [...(record.scope_array || [])];
  editGroupForm.scope = editGroupScopeList.value.join('\n');
  editGroupMode.value = 'visual';
  editGroupSearchKeyword.value = '';
  editGroupNewInput.value = '';
  editGroupModalVisible.value = true;
};

// 模式切换
const toggleEditGroupMode = () => {
  if (editGroupMode.value === 'visual') {
    // 切换到纯文本模式
    editGroupForm.scope = editGroupScopeList.value.join('\n');
    editGroupMode.value = 'text';
  } else {
    // 切换到可视化模式
    editGroupScopeList.value = parseScopeList(editGroupForm.scope);
    editGroupForm.scope = editGroupScopeList.value.join('\n');
    editGroupMode.value = 'visual';
    editGroupSearchKeyword.value = '';
  }
};

// 单项移除资产
const removeScopeItem = (item) => {
  editGroupScopeList.value = editGroupScopeList.value.filter(x => x !== item);
  editGroupForm.scope = editGroupScopeList.value.join('\n');
};

// 批量删除搜索筛选结果
const removeFilteredScopes = () => {
  const toRemove = new Set(filteredScopeList.value);
  editGroupScopeList.value = editGroupScopeList.value.filter(x => !toRemove.has(x));
  editGroupForm.scope = editGroupScopeList.value.join('\n');
  message.success(assetText('assets.matchingAssetsRemovedCount', { count: toRemove.size }));
  editGroupSearchKeyword.value = '';
};

// 快捷追加资产
const addScopesFromInput = () => {
  if (!editGroupNewInput.value.trim()) return;
  const newItems = parseScopeList(editGroupNewInput.value);
  if (newItems.length === 0) return;
  const existingSet = new Set(editGroupScopeList.value);
  let addedCount = 0;
  for (const item of newItems) {
    if (!existingSet.has(item)) {
      existingSet.add(item);
      editGroupScopeList.value.push(item);
      addedCount++;
    }
  }
  editGroupForm.scope = editGroupScopeList.value.join('\n');
  editGroupNewInput.value = '';
  if (addedCount > 0) {
    message.success(assetText('assets.newAssetsAddedCount', { count: addedCount }));
  } else {
    message.info(assetText('assets.allEnteredAssetsAlreadyExistNoDuplicatesWere'));
  }
};

// 格式化文本模式下的资产
const formatEditGroupScopes = () => {
  const list = parseScopeList(editGroupForm.scope);
  editGroupScopeList.value = list;
  editGroupForm.scope = list.join('\n');
  message.success(assetText('assets.duplicatesRemovedAndTargetsFormattedOnePerLine'));
};

// 提交编辑保存
const handleEditGroupSubmit = async () => {
  try {
    if (editGroupMode.value === 'visual') {
      editGroupForm.scope = editGroupScopeList.value.join('\n');
    } else {
      editGroupScopeList.value = parseScopeList(editGroupForm.scope);
      editGroupForm.scope = editGroupScopeList.value.join('\n');
    }

    await editGroupFormRef.value.validate();
    const newScopeList = parseScopeList(editGroupForm.scope);
    if (newScopeList.length === 0) {
      message.error(assetText('assets.keepAtLeastOneTargetInTheAsset'));
      return;
    }

    const originalScopes = currentRecord.value?.scope_array || [];
    const newSet = new Set(newScopeList);
    const removed = originalScopes.filter(x => !newSet.has(x));

    if (removed.length > 0) {
      Modal.confirm({
        title: assetText('assets.removeScopeTargetsAndDeleteRelatedAssets'),
        icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
        content: createVNode('div', null, [
          createVNode('p', { style: 'color: #ff4d4f; margin-bottom: 8px;' }, assetText('assets.youHaveRemovedTheseTargetsFromAssetGroup', { name: editGroupForm.name, count: removed.length })),
          createVNode('div', { style: 'max-height: 100px; overflow-y: auto; background: rgba(255, 77, 79, 0.12); border: 1px solid rgba(255, 77, 79, 0.25); padding: 6px 8px; border-radius: 4px; margin-bottom: 10px; font-family: monospace; font-size: 12px; color: #ff4d4f;' }, removed.join(', ')),
          createVNode('p', { style: 'font-size: 12px; color: #8c8c8c; margin-bottom: 0;' }, assetText('assets.warningRemovingTheseSeedTargetsPermanentlyDeletesAll'))
        ]),
        okText: assetText('assets.updateAndDeleteRelatedAssets'),
        okType: 'danger',
        cancelText: assetText('assets.cancel'),
        onOk: () => {
          submitEditGroupUpdate(newScopeList);
        }
      });
    } else {
      submitEditGroupUpdate(newScopeList);
    }
  } catch (error) {
    console.warn('编辑校验失败', error);
  }
};

const submitEditGroupUpdate = async (scopeList) => {
  try {
    editGroupLoading.value = true;
    const res = await request.post('/asset_scope/update/', {
      _id: editGroupForm._id,
      group_id: editGroupForm.group_id || '',
      name: editGroupForm.name,
      scope: scopeList.join(',')
    });

    if (res.code === 200) {
      message.success(assetText('assets.assetGroupUpdated'));
      editGroupModalVisible.value = false;
      fetchData();
    } else {
      message.error(assetText('assets.updateFailed') + (res.message || assetText('tasks.unknownError')));
    }
  } catch (error) {
    message.error(assetText('assets.requestFailedAssetGroupWasNotUpdated'));
  } finally {
    editGroupLoading.value = false;
  }
};

// ================= 表格 Tag 快捷单个移除范围 =================
const handleRemoveSingleScope = (record, scopeItem) => {
  if ((record.scope_array || []).length <= 1) {
    message.error(assetText('assets.keepAtLeastOneTargetInTheAssetScope'));
    return;
  }

  Modal.confirm({
    title: assetText('assets.removeScopeTargetsAndDeleteRelatedAssets'),
    icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
    content: createVNode('div', null, [
      createVNode('p', { style: 'color: #ff4d4f; margin-bottom: 8px;' }, assetText('assets.youAreAboutToRemoveThisScopeTarget', { name: record.name })),
      createVNode('div', { style: 'background: rgba(255, 77, 79, 0.12); border: 1px solid rgba(255, 77, 79, 0.25); padding: 6px 8px; border-radius: 4px; margin-bottom: 10px; font-family: monospace; font-size: 13px; font-weight: bold; color: #ff4d4f;' }, scopeItem),
      createVNode('p', { style: 'font-size: 12px; color: #8c8c8c; margin-bottom: 0;' }, assetText('assets.warningRemovingThisSeedTargetPermanentlyDeletesIts'))
    ]),
    okText: assetText('assets.removeTargetAndRelatedAssets'),
    okType: 'danger',
    cancelText: assetText('assets.cancel'),
    onOk: async () => {
      try {
        const res = await request.get('/asset_scope/delete/', {
          params: {
            scope_id: record._id,
            scope: scopeItem
          }
        });
        if (res.code === 200) {
          message.success(assetText('assets.scopeTargetRemovedTarget', { target: scopeItem }));
          fetchData(true);
        } else {
          message.error(assetText('assets.removalFailed') + (res.message || res.data?.error || assetText('tasks.unknownError')));
        }
      } catch (e) {
        message.error(assetText('assets.requestFailedScopeTargetWasNotRemoved'));
      }
    }
  });
};

// ================= 单行删除资产组 =================
const handleSingleDelete = (record) => {
  Modal.confirm({
    title: assetText('assets.permanentlyDeleteAssetGroup'),
    icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
    content: createVNode('div', null, [
      createVNode('p', { style: 'color: #ff4d4f; margin-bottom: 8px;' }, assetText('assets.permanentlyDeleteAssetGroupName', { name: record.name })),
      createVNode('p', { style: 'font-size: 12px; color: #8c8c8c; margin-bottom: 0;' }, assetText('assets.warningAllDiscoveredSubdomainsIpsWebsitesWihAssets'))
    ]),
    okText: assetText('assets.deletePermanently'),
    okType: 'danger',
    cancelText: assetText('assets.cancel'),
    onOk: async () => {
      try {
        const res = await request.post('/asset_scope/delete/', {
          scope_id: [record._id]
        });

        if (res.code === 200) {
          message.success(assetText('assets.assetGroupDeleted'));
          if (dataSource.value.length === 1 && pagination.current > 1) {
            pagination.current -= 1;
          }
          fetchData();
        } else {
          message.error(assetText('tasks.deletionFailed') + res.message);
        }
      } catch (error) {
        message.error(assetText('assets.requestFailedAssetGroupWasNotDeleted'));
      }
    }
  });
};

// ================= 批量删除逻辑 =================
const handleBatchDelete = () => {
  Modal.confirm({
    title: assetText('assets.deleteSelectedAssetGroups'),
    icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
    content: assetText('assets.permanentlyDeleteSelectedAssetGroupsCountAndAll', { count: selectedRowKeys.value.length }),
    okText: assetText('assets.deletePermanently'),
    okType: 'danger',
    cancelText: assetText('assets.cancel'),
    onOk: async () => {
      try {
        const res = await request.post('/asset_scope/delete/', {
          scope_id: selectedRowKeys.value
        });

        if (res.code === 200) {
          message.success(assetText('assets.selectedAssetGroupsDeleted'));
          selectedRowKeys.value = [];
          if (dataSource.value.length === selectedRowKeys.value.length && pagination.current > 1) {
            pagination.current -= 1;
          }
          fetchData();
        } else {
          message.error(assetText('tasks.deletionFailed') + res.message);
        }
      } catch (error) {
        message.error(assetText('assets.requestFailedAssetGroupWasNotDeleted'));
      }
    }
  });
};

// ================= 批量导出逻辑 =================
const handleBatchExport = async ({ key }) => {
  const url = `/batch_export/${key}/`;
  const nameMap = {
    'asset_domain': assetText('tasks.domains'),
    'asset_ip': 'IP',
    'asset_site': assetText('tasks.websites'),
    'asset_wih': 'WIH'
  };
  const exportName = nameMap[key];

  try {
    message.loading({ content: assetText('assets.generatingTypeExport', { type: exportName }), key: 'export_data' });

    const res = await request.post(url, { scope_id: selectedRowKeys.value, group_id: searchForm.value.group_id }, { responseType: 'blob' });
    const blob = new Blob([res], { type: 'text/plain;charset=utf-8' });
    const downloadUrl = window.URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `ARL_Export_${exportName}_${new Date().getTime()}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    message.success({ content: assetText('assets.typeExportCompleted', { type: exportName }), key: 'export_data', duration: 2 });
  } catch (error) {
    message.error({ content: assetText('assets.typeExportFailed', { type: exportName }), key: 'export_data', duration: 2 });
  }
};

// 丝滑跳转至详情页
const goToDetail = (record) => {
  router.push({
    path: '/groupAssetsManagement/groupAssetsDetail',
    query: {
      scope_id: record._id,
      targetName: record._id
    }
  });
};

// ================= 添加监控任务 =================
const addMonitorVisible = ref(false);
const addMonitorLoading = ref(false);
const addMonitorFormRef = ref();
const policies = ref([]);

const addMonitorForm = reactive({ domains: [], interval_hours: 24, policy_id: undefined, task_type: 'periodic' });
const addMonitorRules = {
  domains: [{ type: 'array', required: true, get message() { return assetText('assets.selectTargets'); }, trigger: 'change' }],
  interval_hours: [{ required: true, get message() { return assetText('assets.enterARunInterval'); }, trigger: 'blur' }],
  policy_id: [{ required: true, get message() { return assetText('tasks.selectAPolicy'); }, trigger: 'change' }],
  task_type: [{ required: true, get message() { return assetText('assets.selectATaskType'); }, trigger: 'change' }]
};

const openAddMonitorModal = async (record) => {
  currentRecord.value = record;
  addMonitorForm.domains = [];
  addMonitorForm.interval_hours = 24;
  addMonitorForm.policy_id = undefined;
  addMonitorForm.task_type = 'periodic';
  addMonitorVisible.value = true;

  if (policies.value.length === 0) {
    const res = await request.get('/policy/', { params: { size: 1000 } });
    if (res.code === 200) policies.value = res.items || [];
  }
};

const unprobedDomainList = computed(() => {
  const scopes = currentRecord.value?.scope_array || [];
  return scopes.filter(d => getDomainStatus(currentRecord.value, d) === 'unprobed');
});

const probedDomainList = computed(() => {
  const scopes = currentRecord.value?.scope_array || [];
  return scopes.filter(d => getDomainStatus(currentRecord.value, d) === 'probed');
});

const selectAllDomains = () => {
  if (currentRecord.value && currentRecord.value.scope_array) {
    addMonitorForm.domains = [...currentRecord.value.scope_array];
  }
};

const selectUnprobedDomains = () => {
  if (currentRecord.value && currentRecord.value.scope_array) {
    addMonitorForm.domains = unprobedDomainList.value.length > 0 ? [...unprobedDomainList.value] : [...currentRecord.value.scope_array];
  }
};

const selectProbedDomains = () => {
  if (currentRecord.value && currentRecord.value.scope_array) {
    addMonitorForm.domains = [...probedDomainList.value];
  }
};

const clearDomains = () => {
  addMonitorForm.domains = [];
};

const submitAddMonitor = async () => {
  try {
    await addMonitorFormRef.value.validate();
    addMonitorLoading.value = true;

    const payload = {
      scope_id: currentRecord.value._id,
      domain: addMonitorForm.domains.join(','),
      interval: addMonitorForm.interval_hours * 3600,
      policy_id: addMonitorForm.policy_id,
      name: ''
    };

    if (addMonitorForm.task_type === 'oneshot') {
      delete payload.interval;
    }

    const apiUrl = addMonitorForm.task_type === 'oneshot' ? '/scheduler/one_time_scan/' : '/scheduler/add/';
    const res = await request.post(apiUrl, payload);

    if (res.code === 200) {
      const successCount = (res.data || res.items || []).length;
      const countMsg = successCount > 0 ? assetText('assets.tasksQueuedCount', { count: successCount }) : '！';

      message.success(addMonitorForm.task_type === 'oneshot' ? assetText('assets.oneTimeMonitoringTasksQueuedDetails', { details: countMsg }) : assetText('assets.monitoringTasksAddedDetails', { details: countMsg }));
      addMonitorVisible.value = false;
    } else if (res.code === 699) {
      message.error(res.message);
    } else {
      message.error(assetText('assets.failedToAddTask') + res.message);
    }
  } catch (error) {
    console.warn('校验失败或请求异常', error);
  } finally {
    addMonitorLoading.value = false;
  }
};

// ================= 添加站点监控任务 =================
const addSiteMonitorVisible = ref(false);
const addSiteMonitorLoading = ref(false);
const addSiteMonitorFormRef = ref();

const addSiteMonitorForm = reactive({ interval_hours: 24 });
const addSiteMonitorRules = {
  interval_hours: [{ required: true, get message() { return assetText('assets.enterARunInterval'); }, trigger: 'blur' }]
};

const openAddSiteMonitorModal = (record) => {
  currentRecord.value = record;
  addSiteMonitorForm.interval_hours = 24;
  addSiteMonitorVisible.value = true;
};

const submitAddSiteMonitor = async () => {
  try {
    await addSiteMonitorFormRef.value.validate();
    addSiteMonitorLoading.value = true;

    const payload = {
      scope_id: currentRecord.value._id,
      interval: addSiteMonitorForm.interval_hours * 3600
    };

    const res = await request.post('/scheduler/add/site_monitor/', payload);

    if (res.code === 200) {
      message.success(assetText('assets.websiteMonitoringTaskAdded'));
      addSiteMonitorVisible.value = false;
    } else if (res.code === 1607) {
      message.error(res.message);
    } else {
      message.error(assetText('assets.failedToAddTask') + res.message);
    }
  } catch (error) {
    console.warn('校验失败或请求异常', error);
  } finally {
    addSiteMonitorLoading.value = false;
  }
};

// ================= 添加WIH监控任务 =================
const addWihMonitorVisible = ref(false);
const addWihMonitorLoading = ref(false);
const addWihMonitorFormRef = ref();

const addWihMonitorForm = reactive({ interval_hours: 24 });
const addWihMonitorRules = {
  interval_hours: [{ required: true, get message() { return assetText('assets.enterARunInterval'); }, trigger: 'blur' }]
};

const openAddWihMonitorModal = (record) => {
  currentRecord.value = record;
  addWihMonitorForm.interval_hours = 24;
  addWihMonitorVisible.value = true;
};

const submitAddWihMonitor = async () => {
  try {
    await addWihMonitorFormRef.value.validate();
    addWihMonitorLoading.value = true;

    const payload = {
      scope_id: currentRecord.value._id,
      interval: addWihMonitorForm.interval_hours * 3600
    };

    const res = await request.post('/scheduler/add/wih_monitor/', payload);

    if (res.code === 200) {
      message.success(assetText('assets.wihMonitoringTaskAdded'));
      addWihMonitorVisible.value = false;
    } else if (res.code === 1607) {
      message.error(res.message);
    } else {
      message.error(assetText('assets.failedToAddTask') + res.message);
    }
  } catch (error) {
    console.warn('校验失败或请求异常', error);
  } finally {
    addWihMonitorLoading.value = false;
  }
};

// 监听路由参数联动
watch(
  () => ({ path: route.path, scopeId: route.query.scope_id }),
  (curr, prev) => {
    // 核心加固：仅在当前路由精确处于 /group 页面时响应外部 query 联动，杜绝子页面或详情页穿透
    if (curr.path !== '/group') return;

    // 如果是从二级详情页或其他页面返回 /group，严禁重置或覆盖已有一级页面状态
    if (prev && prev.path !== '/group') return;

    // 响应外部传入或 /group 内部的有效 scope_id 联动
    if (curr.scopeId && curr.scopeId !== searchForm.value._id) {
      activeGroupId.value = 'all';
      searchForm.value._id = curr.scopeId;
      pagination.current = 1;
      fetchData();
    } else if (!curr.scopeId && prev && prev.scopeId && searchForm.value._id === prev.scopeId) {
      // 仅当之前是在 /group 页面且显式携带了 scopeId，现被主动清空时才重置
      searchForm.value._id = undefined;
      pagination.current = 1;
      fetchData();
    }
  },
  { immediate: true }
);

const goToReconDetail = (taskId, taskType = 'icp') => {
  if (taskId) {
    router.push({
      path: '/taskList/taskDetail',
      query: { task_id: taskId, task_type: taskType }
    });
  }
};

// ================= 从企业资产任务导入逻辑 =================
const icpImportModalVisible = ref(false);
const icpImportLoading = ref(false);
const importingTaskId = ref('');
const icpImportSearchKey = ref('');
const icpTaskList = ref([]);
const icpImportTarget = ref('add'); // 'add' | 'edit'

const icpImportColumns = [
  { get title() { return assetText('assets.taskName'); }, dataIndex: 'name', key: 'name', ellipsis: true },
  { get title() { return assetText('tasks.queryTarget'); }, dataIndex: 'target', key: 'target', ellipsis: true },
  { get title() { return assetText('assets.websiteAssets'); }, key: 'statistic', width: 120 },
  { get title() { return assetText('assets.completionTime'); }, dataIndex: 'end_time', key: 'end_time', width: 160 },
  { get title() { return assetText('tasks.actions'); }, key: 'action', width: 130, align: 'center' }
];

const filteredIcpTasks = computed(() => {
  if (!icpImportSearchKey.value.trim()) return icpTaskList.value;
  const kw = icpImportSearchKey.value.trim().toLowerCase();
  return icpTaskList.value.filter(t =>
    (t.name && t.name.toLowerCase().includes(kw)) ||
    (t.target && t.target.toLowerCase().includes(kw))
  );
});

const openIcpImportModal = async (target = 'add') => {
  icpImportTarget.value = target;
  icpImportModalVisible.value = true;
  icpImportSearchKey.value = '';
  icpImportLoading.value = true;
  try {
    const res = await request.get('/icp/task', { params: { size: 50, status: 'done' } });
    if (res.code === 200) {
      icpTaskList.value = res.items || [];
    }
  } catch (err) {
    console.error('获取企业资产任务列表失败', err);
  } finally {
    icpImportLoading.value = false;
  }
};

const handleImportFromTask = async (task) => {
  importingTaskId.value = task._id;
  try {
    const res = await request.get('/icp/asset', { params: { task_id: task._id, query_type: 'web', size: 10000 } });
    const items = res.items || res.data?.items || [];
    const domainSet = new Set();
    items.forEach(item => {
      const d = item.domain || item.ym;
      if (d && typeof d === 'string') domainSet.add(d.trim().toLowerCase());
    });
    const domainList = Array.from(domainSet);

    if (domainList.length === 0) {
      message.warning(assetText('assets.noWebsiteAssetsAreAvailableToImportFrom'));
      return;
    }

    if (icpImportTarget.value === 'add') {
      if (!addForm.name.trim()) {
        addForm.name = task.name || task.target || '';
      }
      const existing = parseScopeList(addForm.scope);
      const merged = Array.from(new Set([...existing, ...domainList]));
      addForm.scope = merged.join('\n');
    } else {
      if (editGroupMode.value === 'visual') {
        const merged = Array.from(new Set([...editGroupScopeList.value, ...domainList]));
        editGroupScopeList.value = merged;
      } else {
        const existing = parseScopeList(editGroupForm.scope);
        const merged = Array.from(new Set([...existing, ...domainList]));
        editGroupForm.scope = merged.join('\n');
      }
    }

    message.success(assetText('assets.importedAssetsFromTaskNameCountDomains', { name: task.name || task.target, count: domainList.length }));
    icpImportModalVisible.value = false;
  } catch (err) {
    console.error('导入资产失败', err);
    message.error(assetText('assets.importFailedTryAgainLater'));
  } finally {
    importingTaskId.value = '';
  }
};



onDeactivated(() => {
  stopPoll();
  stopReconPoller();
  // 离开页面时安全收起弹窗，避免浮层遮挡其他视图
  addModalVisible.value = false;
  editGroupModalVisible.value = false;
  enterpriseGroupModalVisible.value = false;
  batchMoveModalVisible.value = false;
  icpImportModalVisible.value = false;
  syncIncrementModalVisible.value = false;
  bindScopeModalVisible.value = false;
  addMonitorVisible.value = false;
  addSiteMonitorVisible.value = false;
  addWihMonitorVisible.value = false;
});

onUnmounted(() => {
  window.removeEventListener('resize', updateSidebarLeft);
  const siderEl = document.querySelector('.ant-layout-sider');
  if (siderEl) {
    siderEl.removeEventListener('transitionend', updateSidebarLeft);
  }
  if (siderObserver) siderObserver.disconnect();
  if (sortableInstance) {
    sortableInstance.destroy();
    sortableInstance = null;
  }
  if (saveOrderTimer) {
    clearTimeout(saveOrderTimer);
  }
  stopPoll();
  stopReconPoller();
});

</script>

<style scoped>
.asset-increment-badge :deep(.ant-badge-count) { background-color: #52c41a; font-size: 10px; }

/* 投资层级成本提示：层级越高，天眼查付费额度消耗越大 */
.depth-cost-hint {
  margin-top: 4px;
  font-size: 12px;
  line-height: 1.5;
  color: var(--arl-warning-color, #faad14);
}

.arl-scope-visual-panel {
  border: 1px solid var(--arl-border-color, #e2e8f0);
  border-radius: 8px;
  padding: 12px;
  background: var(--arl-bg-light, rgba(0, 0, 0, 0.02));
}

.arl-scope-tag-container {
  max-height: 220px;
  min-height: 110px;
  overflow-y: auto;
  padding: 8px;
  border: 1px dashed var(--arl-border-color, #d9d9d9);
  border-radius: 6px;
  background: var(--arl-bg-white, #ffffff);
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-content: flex-start;
}

.arl-scope-edit-item-tag {
  margin: 0 !important;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s;
  background: var(--arl-bg-light, #f1f5f9);
  border-color: var(--arl-border-color, #d9d9d9);
  color: var(--arl-text-color, rgba(0, 0, 0, 0.85));
}

.arl-scope-edit-item-tag:hover {
  border-color: #ff4d4f !important;
  background: rgba(255, 77, 79, 0.12) !important;
  color: #ff4d4f !important;
}

.arl-scope-empty-hint {
  width: 100%;
  text-align: center;
  color: var(--arl-text-color, #8c8c8c);
  opacity: 0.55;
  padding: 36px 0;
  font-size: 13px;
}

.sidebar-collapse-handle {
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
}
.sidebar-collapse-handle:hover {
  background: var(--arl-bg-light, #f1f5f9) !important;
}
.sidebar-collapse-handle:hover :deep(.anticon) {
  color: var(--arl-theme-color) !important;
}

.sidebar-expand-handle {
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  user-select: none;
}
.sidebar-expand-handle:hover {
  background: var(--arl-bg-light, #f1f5f9) !important;
}
.sidebar-expand-handle:hover :deep(.anticon) {
  color: var(--arl-theme-color) !important;
}

/* 一体化卡片容器 */
.arl-scope-main-card {
  background: var(--arl-bg-white, #ffffff);
  border: 1px solid var(--arl-border-color, #e2e8f0);
  border-radius: 10px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
  padding: 20px 24px;
  position: relative;
  min-height: calc(100vh - 128px);
}

/* 顶部吸附操作区 */
.arl-scope-action-bar {
  position: sticky;
  top: 0px;
  z-index: 10;
  background-color: var(--arl-bg-white, #ffffff);
  margin: -20px -24px 16px -24px;
  padding: 20px 24px 14px 24px;
  border-top-left-radius: 10px;
  border-top-right-radius: 10px;
  border-bottom: 1px solid var(--arl-border-color, #e2e8f0);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.02);
}

/* 顶部标题与操作 */
.scope-header-top {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}
.scope-title-wrap {
  display: flex;
  align-items: center;
  gap: 10px;
}
.scope-title-text {
  font-size: 18px;
  font-weight: 600;
  color: var(--arl-text-color);
  letter-spacing: -0.2px;
}
.scope-total-tag {
  font-size: 12px;
  color: var(--arl-text-color);
  opacity: 0.55;
  background: var(--arl-bg-light, #f1f5f9);
  padding: 2px 8px;
  border-radius: 10px;
}
.group-switch-trigger {
  cursor: pointer;
  color: var(--arl-theme-color);
  font-weight: 500;
}
.scope-header-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.header-action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

/* 筛选表单栏 */
.scope-filter-toolbar {
  margin-bottom: 14px;
}
.scope-filter-form {
  row-gap: 12px;
  align-items: center;
}
.filter-actions-item {
  margin-right: 0 !important;
}

/* 批量操作与选中反馈 */
.scope-batch-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
}
.batch-buttons-group {
  display: flex;
  align-items: center;
  gap: 8px;
}
.selection-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  padding: 4px 12px;
  background: rgba(250, 84, 28, 0.08);
  border: 1px solid rgba(250, 84, 28, 0.2);
  border-radius: 6px;
}

/* 表格主体美化 */
.arl-scope-table {
  margin-bottom: 16px;
}
:deep(.arl-scope-table .ant-table-thead > tr > th) {
  font-weight: 600;
  background: var(--arl-bg-light, #f8fafc) !important;
  color: var(--arl-text-color);
  font-size: 13px;
}
:deep(.arl-scope-table .ant-table-tbody > tr > td) {
  padding: 10px 12px !important;
}

/* 资产组名称单元格 */
.group-name-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  align-items: flex-start;
}
.group-name-title-row {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}
.group-name-title {
  font-weight: 600;
  color: var(--arl-text-color);
  transition: color 0.2s;
  font-size: 13px;
}
.group-name-title:hover {
  color: var(--arl-theme-color);
}
.enterprise-tag-row {
  display: flex;
  align-items: center;
}
.enterprise-osint-tag {
  font-size: 11px !important;
  line-height: 18px !important;
  cursor: pointer;
  margin-right: 0 !important;
  border-radius: 4px;
}
.group-cell-tag {
  cursor: pointer;
  border-radius: 4px;
  font-size: 12px;
  margin-right: 0;
}

/* 种子目标与覆盖度复合单元格 */
.scope-stat-compact-cell {
  display: flex;
  flex-direction: column;
  gap: 5px;
  min-width: 0;
}
.scope-compact-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 6px;
}
.scope-compact-tags {
  display: flex;
  align-items: center;
  gap: 5px;
  overflow: hidden;
  flex: 1;
  min-width: 0;
}
.scope-compact-domain {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  background: var(--arl-bg-light, #f8fafc);
  border: 1px solid var(--arl-border-color, #e2e8f0);
  border-radius: 4px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 11px;
  color: var(--arl-text-color, #334155);
  max-width: 110px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.scope-compact-count-badge {
  font-size: 11px;
  color: var(--arl-theme-color, #1890ff);
  background: rgba(24, 144, 255, 0.08);
  border: 1px solid rgba(24, 144, 255, 0.2);
  border-radius: 10px;
  padding: 1px 7px;
  cursor: pointer;
  white-space: nowrap;
  font-weight: 500;
  transition: all 0.2s ease;
}
.scope-compact-count-badge:hover {
  background: var(--arl-theme-color, #1890ff);
  color: #fff;
}
.scope-compact-progress-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.scope-mini-progress-bar {
  flex: 1;
  height: 5px;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 3px;
  overflow: hidden;
  display: flex;
  cursor: pointer;
}
.progress-seg {
  height: 100%;
  transition: width 0.3s ease;
}
.progress-seg.probed {
  background: #52c41a;
}
.progress-seg.scanning {
  background: #1890ff;
  animation: progress-pulse 1.5s infinite;
}
.progress-seg.error {
  background: #ff4d4f;
}
.progress-seg.unprobed {
  background: #d9d9d9;
}
@keyframes progress-pulse {
  0% { opacity: 0.6; }
  50% { opacity: 1; }
  100% { opacity: 0.6; }
}
.scope-compact-progress-text {
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.65;
  white-space: nowrap;
  font-family: ui-monospace, monospace;
}

/* 种子目标悬浮 Popover 面板 */
.scope-popover-panel {
  max-width: 380px;
  min-width: 260px;
  max-height: 280px;
  display: flex;
  flex-direction: column;
}
.scope-popover-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding-bottom: 6px;
  border-bottom: 1px solid var(--arl-border-color, #f0f0f0);
  margin-bottom: 6px;
}
.scope-popover-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--arl-text-color);
}
.scope-popover-copy-btn {
  padding: 0 !important;
  font-size: 11px !important;
  height: auto !important;
}
.scope-popover-list {
  overflow-y: auto;
  max-height: 220px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.scope-popover-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 3px 6px;
  border-radius: 4px;
  background: var(--arl-bg-light, #fafafa);
  font-size: 12px;
  cursor: pointer;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}
.scope-popover-item:hover {
  background: rgba(24, 144, 255, 0.08);
}
.scope-popover-item-main {
  display: flex;
  align-items: center;
  gap: 6px;
  min-width: 0;
  flex: 1;
}
.scope-popover-item-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.scope-popover-item-status {
  font-size: 11px;
  margin-left: 8px;
  white-space: nowrap;
}
.scope-popover-item-status.text-probed { color: #52c41a; }
.scope-popover-item-status.text-scanning { color: #1890ff; }
.scope-popover-item-status.text-unprobed { color: #faad14; }
.scope-popover-item-status.text-error { color: #ff4d4f; }

.domain-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
  margin-right: 5px;
  flex-shrink: 0;
}
.domain-status-dot.status-probed {
  background-color: #52c41a;
  box-shadow: 0 0 0 1.5px rgba(82, 196, 26, 0.25);
}
.domain-status-dot.status-scanning {
  background-color: #1890ff;
  box-shadow: 0 0 0 1.5px rgba(24, 144, 255, 0.25);
  animation: pulse-dot 1.5s infinite ease-in-out;
}
.domain-status-dot.status-unprobed {
  background-color: #faad14;
  box-shadow: 0 0 0 1.5px rgba(250, 173, 20, 0.25);
}
.domain-status-dot.status-error {
  background-color: #ff4d4f;
  box-shadow: 0 0 0 1.5px rgba(255, 77, 79, 0.25);
}
@keyframes pulse-dot {
  0% { transform: scale(0.9); opacity: 0.7; }
  50% { transform: scale(1.2); opacity: 1; }
  100% { transform: scale(0.9); opacity: 0.7; }
}

/* ID 样式 */
.scope-id-text {
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 12px;
  color: var(--arl-text-color);
  opacity: 0.85;
}
.scope-id-text:hover {
  color: var(--arl-theme-color);
}
.copy-id-icon {
  cursor: pointer;
  color: var(--arl-text-color);
  opacity: 0.4;
  font-size: 12px;
  transition: opacity 0.2s;
}
.copy-id-icon:hover {
  opacity: 1;
  color: var(--arl-theme-color);
}

/* 操作列平铺紧凑按钮 */
.table-actions-container {
  display: flex;
  align-items: center;
  flex-wrap: nowrap;
  gap: 2px;
}
:deep(.arl-scope-table .ant-table-cell:last-child) {
  padding-left: 6px !important;
  padding-right: 6px !important;
}
.grid-action-btn {
  padding: 0 4px !important;
  height: 24px !important;
  line-height: 24px !important;
  font-size: 12px !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 2px !important;
  white-space: nowrap !important;
  color: var(--arl-text-color);
  opacity: 0.85;
  transition: all 0.2s ease;
}
.grid-action-btn:hover {
  opacity: 1;
  color: var(--arl-theme-color);
}
.grid-action-btn.btn-theme {
  color: var(--arl-theme-color) !important;
  opacity: 1;
}
.grid-action-btn.btn-success {
  color: #52c41a !important;
  font-weight: 500;
  opacity: 1;
}
.grid-action-btn.btn-danger {
  color: #ff4d4f !important;
  opacity: 0.85;
}
.grid-action-btn.btn-danger:hover {
  opacity: 1;
}

/* 分页条 */
.table-pagination-footer {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 4px 0 4px;
}
.pagination-summary {
  color: var(--arl-text-color);
  opacity: 0.65;
  font-size: 13px;
}

/* 左侧集团侧边栏样式 */
.sidebar-header {
  padding: 14px 16px;
  border-bottom: 1px solid var(--arl-border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}
.sidebar-total-badge {
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.55;
  background: var(--arl-bg-light);
  padding: 1px 7px;
  border-radius: 10px;
}
.sidebar-add-btn {
  color: var(--arl-text-color);
  opacity: 0.65;
  transition: all 0.2s;
}
.sidebar-add-btn:hover {
  opacity: 1;
  color: var(--arl-theme-color);
  background: var(--arl-bg-light);
}
.sidebar-search-container {
  padding: 10px 12px;
  flex-shrink: 0;
  border-bottom: 1px solid var(--arl-border-color);
}
.sidebar-scope-pill {
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.6;
  background: var(--arl-bg-light, #f1f5f9);
  padding: 0 6px;
  border-radius: 10px;
  line-height: 18px;
  font-weight: 500;
  transition: all 0.2s;
}
.sidebar-group-menu :deep(.ant-menu-item) {
  margin: 2px 8px !important;
  width: calc(100% - 16px) !important;
  border-radius: 6px !important;
  height: 36px !important;
  line-height: 36px !important;
  transition: all 0.2s ease !important;
}
.sidebar-group-menu :deep(.ant-menu-item-selected) {
  background-color: rgba(250, 84, 28, 0.08) !important;
  color: var(--arl-theme-color) !important;
  font-weight: 600 !important;
}
.sidebar-group-menu :deep(.ant-menu-item-selected) .sidebar-scope-pill {
  background-color: var(--arl-bg-white) !important;
  color: var(--arl-theme-color) !important;
  opacity: 0.9;
}
.group-action-icon {
  cursor: pointer;
  padding: 2px 4px;
  border-radius: 4px;
  opacity: 0.45;
  transition: opacity 0.2s;
}
.group-action-icon:hover {
  opacity: 1;
  color: var(--arl-theme-color);
}

.sidebar-group-divider {
  margin: 6px 12px;
  height: 1px;
  background: var(--arl-border-color);
  opacity: 0.6;
}

.sidebar-group-draggable-list {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 0;
}

.group-nav-item {
  margin: 2px 8px;
  padding: 0 10px 0 6px;
  border-radius: 6px;
  height: 36px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  font-size: 14px;
  color: var(--arl-text-color);
  transition: background-color 0.2s ease, color 0.2s ease, border-color 0.2s ease;
  user-select: none;
  position: relative;
  background: transparent;
  border: 1px solid transparent;
}

.group-nav-item:hover {
  background-color: rgba(0, 0, 0, 0.04);
}

.group-nav-item-active {
  background-color: rgba(250, 84, 28, 0.08) !important;
  color: var(--arl-theme-color) !important;
  font-weight: 600 !important;
}

.group-nav-item-active .sidebar-scope-pill {
  background-color: var(--arl-bg-white) !important;
  color: var(--arl-theme-color) !important;
  opacity: 0.9;
}

/* 拖拽微动抓手 */
.group-drag-handle {
  cursor: grab;
  color: var(--arl-text-color);
  opacity: 0.35;
  transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 24px;
  font-size: 13px;
  border-radius: 4px;
  flex-shrink: 0;
  user-select: none;
}

.group-nav-item:hover .group-drag-handle {
  opacity: 0.85;
  color: var(--arl-theme-color);
}

.group-drag-handle:hover {
  opacity: 1 !important;
  background: rgba(250, 84, 28, 0.1);
}

.group-drag-handle:active {
  cursor: grabbing;
}

.group-drag-handle-disabled {
  cursor: not-allowed !important;
  opacity: 0.15 !important;
}

.group-drag-handle-disabled:hover {
  background: transparent !important;
  color: var(--arl-text-color) !important;
}

/* Sortable 正在被拖动的元素浮动预览状态 (Drag Class) */
.group-drag-active {
  opacity: 0.96 !important;
  background: var(--arl-bg-white) !important;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.12), 0 2px 6px rgba(250, 84, 28, 0.12) !important;
  border: 1px solid var(--arl-theme-color) !important;
  border-radius: 6px !important;
  transform: scale(1.02);
  z-index: 1000 !important;
  cursor: grabbing !important;
}

/* 目标位置的幽灵占位符状态 (Ghost Class) */
.group-drag-ghost {
  opacity: 0.55 !important;
  background: rgba(250, 84, 28, 0.06) !important;
  border: 1px dashed var(--arl-theme-color) !important;
  border-radius: 6px !important;
  box-shadow: inset 0 0 8px rgba(250, 84, 28, 0.08) !important;
}

/* 选中但未开始移动状态 (Chosen Class) */
.group-drag-chosen {
  cursor: grabbing !important;
}

.asset-sidebar-heading { font-weight: 600; font-size: 15px; color: var(--arl-text-color); }
.asset-danger { color: #ff4d4f; }
.asset-clear-search { font-size: 11px; padding: 0; margin-top: 4px; }
.asset-sidebar-handle { writing-mode: vertical-lr; font-size: 11px; letter-spacing: 2px; color: var(--arl-text-color); opacity: 0.65; }
.asset-bold-label { font-weight: 600; }
.asset-width-170 { width: 170px; }
.asset-width-175 { width: 175px; }
.asset-inline-action { padding: 0 4px; }
.asset-source-label { color: #69c0ff; }
.asset-sync-marker { color: var(--arl-theme-color); margin-right: 3px; font-size: 11px; }
.asset-no-targets { color: var(--arl-text-color); opacity: 0.45; font-size: 12px; }
.asset-info { color: #1890ff; }
.asset-success { color: #52c41a; }
.asset-warning { color: #faad14; }
.asset-small-caption { font-size: 10px; }
.asset-info-icon { color: #1890ff; margin-right: 6px; }
.asset-success-icon { color: #52c41a; margin-right: 6px; }
.asset-purple-icon { color: #722ed1; margin-right: 6px; }
.asset-muted-caption { font-size: 12px; color: var(--arl-text-color); opacity: 0.65; }
.asset-section-caption { font-weight: 500; font-size: 13px; }
.asset-flush-bottom { margin-bottom: 0; }
.asset-width-160 { width: 160px; }
.asset-theme-text { color: var(--arl-theme-color); }
.asset-form-spacing { margin-bottom: 8px; }
.asset-theme-fallback { color: var(--arl-theme-color, #1890ff); }
.asset-inline-icon { margin-right: 4px; }
.asset-text-action { padding: 0; height: auto; }
.asset-risk-form { margin-top: 20px; }
.asset-full-width { width: 100%; }
.asset-modal-spacing { margin-top: 16px; }

/* 新建资产组特征卡片选择器 */
.creation-mode-selector {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 20px;
}

.mode-card {
  position: relative;
  background: var(--arl-bg-light, #fafafa);
  border: 1.5px solid var(--arl-border-color, #d9d9d9);
  border-radius: 8px;
  padding: 12px 14px;
  cursor: pointer;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
  display: flex;
  flex-direction: column;
  justify-content: flex-start;
  user-select: none;
}

.mode-card:hover {
  border-color: var(--arl-theme-color, #1890ff);
  background: var(--arl-bg-white, #ffffff);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.06);
  transform: translateY(-1px);
}

.mode-card-active {
  border-color: var(--arl-theme-color, #1890ff) !important;
  background: var(--arl-bg-white, #ffffff) !important;
  box-shadow: 0 0 0 2px rgba(24, 144, 255, 0.12), 0 3px 10px rgba(0, 0, 0, 0.08) !important;
}

.mode-card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 6px;
}

.mode-card-title-wrap {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex: 1;
  min-width: 0;
}

.mode-card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--arl-text-color, #262626);
  line-height: 1.4;
  word-break: break-word;
}

.mode-card-tag {
  font-size: 11px;
  line-height: 18px;
  padding: 0 6px;
  border-radius: 10px;
  font-weight: 500;
  margin-right: 0;
  flex-shrink: 0;
}

.mode-card-desc {
  font-size: 12px;
  line-height: 1.5;
  color: var(--arl-text-color, #595959);
  opacity: 0.72;
  margin-top: 2px;
}

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
