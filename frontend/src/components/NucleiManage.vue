<template>
  <div class="nuclei-manage-container" :class="{ 'page-wide-text': pageLocale !== 'zh-CN' }">
    <!-- 吸顶 Hero 控制卡片：胶囊子视角 + 版本状态 + 对应子视角工具栏 -->
    <div ref="nucleiActionBarRef" class="arl-hero-card">
      <div class="arl-hero-unified-bar">
        <div class="arl-hero-left">
          <div class="arl-capsule-switcher">
            <button
              type="button"
              class="arl-capsule-item"
              :class="{ 'is-active': innerTab === 'community' }"
              @click="innerTab = 'community'"
            >
              <span>{{ pageText('pages.communityTemplatesReadOnlySearch') }}</span>
              <span class="arl-capsule-count">{{ stats.community_total ? stats.community_total.toLocaleString() : pageText('pages.scanning') }}</span>
            </button>
            <button
              type="button"
              class="arl-capsule-item"
              :class="{ 'is-active': innerTab === 'blacklist' }"
              @click="innerTab = 'blacklist'"
            >
              <span>{{ pageText('pages.falsePositiveBlocklist') }}</span>
              <span class="arl-capsule-count">{{ stats.blacklist_total || 0 }}</span>
            </button>
            <button
              type="button"
              class="arl-capsule-item"
              :class="{ 'is-active': innerTab === 'custom' }"
              @click="innerTab = 'custom'"
            >
              <span>{{ pageText('pages.customTemplateWorkspace') }}</span>
              <span class="arl-capsule-count">{{ stats.custom_total }}</span>
            </button>
          </div>
        </div>

        <div class="arl-hero-right nuclei-hero-meta">
          <span class="nuclei-meta-item">
            <span class="page-secondary-label">{{ pageText('pages.enabledCustomTemplates') }}</span>
            <strong class="page-success">{{ stats.custom_enabled }}</strong>
          </span>
          <span class="nuclei-meta-item">
            <span class="page-secondary-label">{{ pageText('pages.communityTemplateVersion') }}</span>
            <a-tag :color="stats.has_template_update ? 'orange' : 'cyan'" class="page-quiet-status-tag">
              {{ formatTemplateVersion(stats.template_version) }}
              <span v-if="stats.has_template_update" class="page-version-note">({{ pageText('pages.templateUpdateAvailable', { version: formatTemplateVersion(stats.template_latest_version) }) }})</span>
            </a-tag>
          </span>
          <span class="nuclei-meta-item">
            <span class="page-secondary-label">{{ pageText('pages.nucleiEngine') }}</span>
            <a-tag :color="stats.nuclei_version !== pageText('tasks.unknown') ? 'green' : 'orange'" class="page-quiet-status-tag">
              {{ formatTemplateVersion(stats.nuclei_version) }}
            </a-tag>
          </span>
        </div>
      </div>

      <!-- 1. 社区模板库工具栏 -->
      <div v-if="innerTab === 'community'" class="arl-toolbar-row nuclei-sub-toolbar">
        <div class="arl-filter-group">
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.keywordCve') }}</span>
            <a-input
              v-model:value="communitySearch.search"
              :placeholder="pageText('pages.searchByCveOrName')"
              class="page-width-240"
              size="small"
              allowClear
              @pressEnter="onSearchCommunity"
            />
          </div>
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.severityLabel2') }}</span>
            <a-select
              v-model:value="communitySearch.severity"
              class="page-width-130"
              size="small"
              allowClear
              :placeholder="pageText('pages.allSeverities')"
              @change="onSearchCommunity"
            >
              <a-select-option value="critical">{{ pageText('pages.critical') }}</a-select-option>
              <a-select-option value="high">{{ pageText('pages.high') }}</a-select-option>
              <a-select-option value="medium">{{ pageText('pages.medium') }}</a-select-option>
              <a-select-option value="low">{{ pageText('pages.low') }}</a-select-option>
              <a-select-option value="info">{{ pageText('pages.info') }}</a-select-option>
            </a-select>
          </div>
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.scanStatus') }}</span>
            <a-select
              v-model:value="communitySearch.blacklist_status"
              class="page-width-140"
              size="small"
              :placeholder="pageText('tasks.allStatuses')"
              @change="onSearchCommunity"
            >
              <a-select-option value="all">{{ pageText('pages.allTemplates') }}</a-select-option>
              <a-select-option value="normal">{{ pageText('pages.includedInScans') }}</a-select-option>
              <a-select-option value="blacklisted">{{ pageText('pages.blockedFalsePositive') }}</a-select-option>
            </a-select>
          </div>
          <a-button size="small" @click="onSearchCommunity">
            <template #icon><search-outlined /></template>
            {{ pageText('tasks.search') }}
          </a-button>
          <a-button size="small" @click="resetSearchCommunity">{{ pageText('tasks.reset') }}</a-button>
        </div>

        <div class="arl-actions-group">
          <a-tag v-if="syncStatus.status === 'syncing'" color="processing" class="page-clickable" @click="openSyncLogModal">
            <template #icon><sync-outlined spin /></template>
            {{ pageText('pages.synchronizingCommunityTemplates') }}
          </a-tag>
          <a-tag v-else-if="syncStatus.status === 'success'" color="success" class="page-clickable" @click="openSyncLogModal">
            <template #icon><check-circle-outlined /></template>
            {{ pageText('pages.synchronizationCompleted') }}{{ syncStatus.diff_count >= 0 ? '+' : '' }}{{ syncStatus.diff_count }}{{ pageText('pages.templates') }}
          </a-tag>
          <a-tag v-else-if="syncStatus.status === 'failed'" color="error" class="page-clickable" @click="openSyncLogModal">
            <template #icon><close-circle-outlined /></template>
            {{ pageText('pages.synchronizationFailedClickForDetails') }}
          </a-tag>

          <a-button type="link" size="small" style="padding: 0 4px;" @click="openSyncLogModal">
            <template #icon><file-text-outlined /></template>
            {{ pageText('pages.viewSynchronizationLogs') }}
          </a-button>

          <a-popconfirm
            :title="pageText('pages.synchronizeTheCommunityTemplateLibraryTheSystemWillUse')"
            :ok-text="pageText('pages.confirmSynchronization')"
            :cancel-text="pageText('tasks.cancel')"
            @confirm="handleSyncCommunity"
          >
            <a-button type="primary" size="small" :loading="syncStatus.status === 'syncing'">
              <template #icon><sync-outlined /></template>
              {{ pageText('pages.syncLatestCommunityVersion') }}
            </a-button>
          </a-popconfirm>

          <a-button size="small" @click="isOfflineModalVisible = true">
            <template #icon><cloud-upload-outlined /></template>
            {{ pageText('pages.offlineUpdatePackage') }}
          </a-button>
        </div>
      </div>

      <!-- 2. 误报黑名单工具栏 -->
      <div v-else-if="innerTab === 'blacklist'" class="arl-toolbar-row nuclei-sub-toolbar">
        <div class="arl-filter-group">
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.keywordLabel3') }}</span>
            <a-input
              v-model:value="blacklistSearch.search"
              :placeholder="pageText('pages.enterAnIdNameOrReasonForBlocking')"
              class="page-width-240"
              size="small"
              allowClear
              @pressEnter="onSearchBlacklist"
            />
          </div>
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.severityLabel2') }}</span>
            <a-select
              v-model:value="blacklistSearch.severity"
              class="page-width-130"
              size="small"
              allowClear
              :placeholder="pageText('pages.allSeverities')"
              @change="onSearchBlacklist"
            >
              <a-select-option value="critical">{{ pageText('pages.critical') }}</a-select-option>
              <a-select-option value="high">{{ pageText('pages.high') }}</a-select-option>
              <a-select-option value="medium">{{ pageText('pages.medium') }}</a-select-option>
              <a-select-option value="low">{{ pageText('pages.low') }}</a-select-option>
              <a-select-option value="info">{{ pageText('pages.info') }}</a-select-option>
            </a-select>
          </div>
          <a-button size="small" @click="onSearchBlacklist">
            <template #icon><search-outlined /></template>
            {{ pageText('tasks.search') }}
          </a-button>
          <a-button size="small" @click="resetSearchBlacklist">{{ pageText('tasks.reset') }}</a-button>
        </div>

        <div class="arl-actions-group">
          <span class="page-secondary-label" style="font-size: 12px;">
            {{ pageText('pages.blockedTemplatesAreExcludedFromAllSubsequentNucleiScans') }}
          </span>
          <a-button type="primary" size="small" @click="openAddBlacklistModal">
            <template #icon><plus-outlined /></template>
            {{ pageText('pages.addAFalsePositive') }}
          </a-button>
          <a-popconfirm
            :title="pageText('pages.removeTheSelectedTemplatesFromTheFalsePositiveBlocklist')"
            :ok-text="pageText('pages.confirmRemoval')"
            :cancel-text="pageText('tasks.cancel')"
            @confirm="handleBatchRemoveBlacklist"
            :disabled="blacklistSelectedRowKeys.length === 0"
          >
            <a-button danger size="small" :disabled="blacklistSelectedRowKeys.length === 0">
              <template #icon><delete-outlined /></template>
              {{ pageText('pages.unblockSelectedTemplates') }}
            </a-button>
          </a-popconfirm>
        </div>
      </div>

      <!-- 3. 自建模板库工具栏 -->
      <div v-else class="arl-toolbar-row nuclei-sub-toolbar">
        <div class="arl-filter-group">
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.templateId') }}</span>
            <a-input
              v-model:value="customSearch.template_id"
              :placeholder="pageText('pages.eGCve2024')"
              class="page-width-150"
              size="small"
              allowClear
              @pressEnter="onSearchCustom"
            />
          </div>
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.vulnerabilityName') }}</span>
            <a-input
              v-model:value="customSearch.name"
              :placeholder="pageText('tasks.enterAName')"
              class="page-width-150"
              size="small"
              allowClear
              @pressEnter="onSearchCustom"
            />
          </div>
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.severityLabel2') }}</span>
            <a-select
              v-model:value="customSearch.severity"
              class="page-width-130"
              size="small"
              allowClear
              :placeholder="pageText('pages.allSeverities')"
              @change="onSearchCustom"
            >
              <a-select-option value="critical">{{ pageText('pages.critical') }}</a-select-option>
              <a-select-option value="high">{{ pageText('pages.high') }}</a-select-option>
              <a-select-option value="medium">{{ pageText('pages.medium') }}</a-select-option>
              <a-select-option value="low">{{ pageText('pages.low') }}</a-select-option>
              <a-select-option value="info">{{ pageText('pages.info') }}</a-select-option>
            </a-select>
          </div>
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.tags') }}</span>
            <a-input
              v-model:value="customSearch.tag"
              :placeholder="pageText('pages.eGRceSpring')"
              class="page-width-130"
              size="small"
              allowClear
              @pressEnter="onSearchCustom"
            />
          </div>
          <a-button size="small" @click="onSearchCustom">
            <template #icon><search-outlined /></template>
            {{ pageText('tasks.search') }}
          </a-button>
          <a-button size="small" @click="resetSearchCustom">{{ pageText('tasks.reset') }}</a-button>
        </div>

        <div class="arl-actions-group">
          <a-button type="primary" size="small" @click="openCreateModal">
            <template #icon><plus-outlined /></template>
            {{ pageText('pages.newTemplate') }}
          </a-button>
          <a-button size="small" @click="isImportModalVisible = true">
            <template #icon><cloud-upload-outlined /></template>
            {{ pageText('pages.importTemplates') }}
          </a-button>
          <a-button size="small" @click="downloadSampleTemplate">
            <template #icon><download-outlined /></template>
            {{ pageText('pages.downloadStandardTemplate') }}
          </a-button>
          <a-button size="small" @click="handleExport">
            <template #icon><cloud-download-outlined /></template>
            {{ pageText('pages.exportSelectedAll') }}
          </a-button>
          <a-button size="small" :disabled="selectedRowKeys.length === 0" @click="handleBatchToggle(true)">
            {{ pageText('pages.enableSelected') }}
          </a-button>
          <a-button size="small" :disabled="selectedRowKeys.length === 0" @click="handleBatchToggle(false)">
            {{ pageText('pages.disableSelected') }}
          </a-button>
          <a-popconfirm
            :title="pageText('pages.permanentlyDeleteTheSelectedCustomTemplatesThisCannotBe')"
            :ok-text="pageText('assets.confirm')"
            :cancel-text="pageText('tasks.cancel')"
            @confirm="handleBatchDelete"
            :disabled="selectedRowKeys.length === 0"
          >
            <a-button danger size="small" :disabled="selectedRowKeys.length === 0" :loading="batchDeleteLoading">
              <template #icon><delete-outlined /></template>
              {{ pageText('tasks.deleteSelected') }}
            </a-button>
          </a-popconfirm>
        </div>
      </div>
    </div>

    <!-- 1. 社区模板表格 -->
    <template v-if="innerTab === 'community'">
      <a-table
        :loading="communityLoading"
        :dataSource="communityList"
        :columns="communityColumns"
        :pagination="false"
        :sticky="stickyConfig"
        size="small"
        :rowKey="(record) => record.file_path || record.template_id"
      >
        <template #bodyCell="{ column, record, index }">
          <template v-if="column.key === 'index'">
            <span>{{ (communityPagination.current - 1) * communityPagination.pageSize + index + 1 }}</span>
          </template>
          <template v-if="column.key === 'template_id'">
            <span class="arl-mono" style="font-weight: 600;">{{ record.template_id }}</span>
          </template>
          <template v-if="column.key === 'severity'">
            <a-tag :color="getSeverityColor(record.severity)" style="font-weight: 500; text-transform: uppercase;">
              {{ record.severity || 'UNKNOWN' }}
            </a-tag>
          </template>
          <template v-if="column.key === 'status'">
            <a-tooltip v-if="record.is_blacklisted" :title="record.blacklist_reason ? pageText('pages.reasonForBlockingReason', { reason: record.blacklist_reason }) : pageText('pages.blockedAsAFalsePositiveExcludedFromScans')">
              <a-tag color="orange" class="page-clickable">{{ pageText('pages.blockedFalsePositiveLabel2') }}</a-tag>
            </a-tooltip>
            <a-tag v-else color="blue">{{ pageText('pages.includedInScans') }}</a-tag>
          </template>
          <template v-if="column.key === 'file_path'">
            <span class="arl-mono" style="font-size: 12px; color: var(--arl-text-secondary);">
              {{ record.file_path }}
            </span>
          </template>
          <template v-if="column.key === 'action'">
            <div style="display: flex; gap: 10px; align-items: center; justify-content: center;">
              <a @click="viewCommunitySource(record)">
                <file-text-outlined /> {{ pageText('pages.viewYaml') }}
              </a>
              <a-popconfirm
                v-if="record.is_blacklisted"
                :title="pageText('pages.unblockThisTemplateAndIncludeItInScansAgain')"
                :ok-text="pageText('pages.unblock')"
                :cancel-text="pageText('tasks.cancel')"
                @confirm="handleRemoveBlacklist(record.template_id)"
              >
                <a class="page-success"><check-outlined /> {{ pageText('pages.unblock') }}</a>
              </a-popconfirm>
              <a v-else style="color: #fa8c16;" @click="openMarkBlacklistModal(record)">
                <stop-outlined /> {{ pageText('pages.markAsFalsePositive') }}
              </a>
            </div>
          </template>
        </template>
        <template #emptyText>
          <ArlEmpty :description="pageText('tasks.noData')" />
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">
          {{ pageText('tasks.paginationSummary', { pages: Math.ceil(communityPagination.total / communityPagination.pageSize) || 1, total: communityPagination.total }) }}
        </div>
        <a-pagination
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="communityPagination.current"
          v-model:pageSize="communityPagination.pageSize"
          :total="communityPagination.total"
          show-size-changer
          size="small"
          @change="handleCommunityPageChange"
          @showSizeChange="handleCommunityPageChange"
        />
      </div>
    </template>

    <!-- 2. 误报黑名单表格 -->
    <template v-else-if="innerTab === 'blacklist'">
      <a-table
        :loading="blacklistLoading"
        :dataSource="blacklistItems"
        :columns="blacklistColumns"
        :pagination="false"
        :sticky="stickyConfig"
        size="small"
        :rowKey="(record) => record.template_id"
        :rowSelection="{ selectedRowKeys: blacklistSelectedRowKeys, onChange: onBlacklistSelectChange, preserveSelectedRowKeys: true }"
      >
        <template #bodyCell="{ column, record, index }">
          <template v-if="column.key === 'index'">
            <span>{{ (blacklistPagination.current - 1) * blacklistPagination.pageSize + index + 1 }}</span>
          </template>
          <template v-if="column.key === 'template_id'">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span class="arl-mono" style="font-weight: 600; color: #fa8c16;">{{ record.template_id }}</span>
              <a-tooltip :title="pageText('pages.copyTemplateId')">
                <copy-outlined style="cursor: pointer; opacity: 0.5; font-size: 12px;" @click="copyText(record.template_id)" />
              </a-tooltip>
            </div>
          </template>
          <template v-if="column.key === 'name'">
            <span style="font-weight: 500;">{{ record.name }}</span>
          </template>
          <template v-if="column.key === 'severity'">
            <a-tag :color="getSeverityColor(record.severity)" style="font-weight: 500; text-transform: uppercase;">
              {{ record.severity || 'UNKNOWN' }}
            </a-tag>
          </template>
          <template v-if="column.key === 'reason'">
            <span style="color: var(--arl-text-color); font-size: 13px;">{{ record.reason || '手工标记误报' }}</span>
          </template>
          <template v-if="column.key === 'created_at'">
            <span style="font-size: 12px; opacity: 0.7;">{{ record.created_at || '-' }}</span>
          </template>
          <template v-if="column.key === 'action'">
            <div style="display: flex; gap: 10px; align-items: center; justify-content: center;">
              <a @click="viewCommunitySource(record)">
                <file-text-outlined /> {{ pageText('pages.viewYaml') }}
              </a>
              <a-popconfirm
                :title="pageText('pages.removeThisTemplateFromTheFalsePositiveBlocklistAnd')"
                :ok-text="pageText('pages.unblock')"
                :cancel-text="pageText('tasks.cancel')"
                @confirm="handleRemoveBlacklist(record.template_id)"
              >
                <a class="page-success"><check-outlined /> {{ pageText('pages.unblock') }}</a>
              </a-popconfirm>
            </div>
          </template>
        </template>
        <template #emptyText>
          <ArlEmpty :description="pageText('pages.noFalsePositiveTemplatesBlockedScansWillUseThe')" />
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">
          {{ pageText('tasks.paginationSummary', { pages: Math.ceil(blacklistPagination.total / blacklistPagination.pageSize) || 1, total: blacklistPagination.total }) }}
        </div>
        <a-pagination
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="blacklistPagination.current"
          v-model:pageSize="blacklistPagination.pageSize"
          :total="blacklistPagination.total"
          show-size-changer
          size="small"
          @change="handleBlacklistPageChange"
          @showSizeChange="handleBlacklistPageChange"
        />
      </div>
    </template>

    <!-- 3. 自建模板表格 -->
    <template v-else>
      <a-table
        :loading="customLoading"
        :dataSource="customList"
        :columns="customColumns"
        :pagination="false"
        :sticky="stickyConfig"
        size="small"
        :rowKey="(record) => record.template_id"
        :rowSelection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange, preserveSelectedRowKeys: true }"
      >
        <template #bodyCell="{ column, record, index }">
          <template v-if="column.key === 'index'">
            <span>{{ (customPagination.current - 1) * customPagination.pageSize + index + 1 }}</span>
          </template>

          <template v-if="column.key === 'template_id'">
            <div style="display: flex; align-items: center; gap: 6px;">
              <span class="arl-mono" style="font-weight: 600; color: var(--arl-text-color);">{{ record.template_id }}</span>
              <a-tooltip :title="pageText('pages.copyTemplateId')">
                <copy-outlined style="cursor: pointer; opacity: 0.5; font-size: 12px;" @click="copyText(record.template_id)" />
              </a-tooltip>
            </div>
          </template>

          <template v-if="column.key === 'name'">
            <a @click="openEditModal(record)" style="font-weight: 500;">{{ record.name }}</a>
            <div v-if="record.description" style="font-size: 12px; color: var(--arl-text-secondary); max-width: 380px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
              {{ record.description }}
            </div>
          </template>

          <template v-if="column.key === 'severity'">
            <a-tag :color="getSeverityColor(record.severity)" style="font-weight: 500; text-transform: uppercase;">
              {{ record.severity || 'UNKNOWN' }}
            </a-tag>
          </template>

          <template v-if="column.key === 'tags'">
            <div style="display: flex; flex-wrap: wrap; gap: 4px; max-width: 220px;">
              <a-tag v-for="tag in (record.tags || []).slice(0, 3)" :key="tag" color="blue" size="small">{{ tag }}</a-tag>
              <span v-if="(record.tags || []).length > 3" style="font-size: 11px; opacity: 0.6;">+{{ (record.tags || []).length - 3 }}</span>
            </div>
          </template>

          <template v-if="column.key === 'enable'">
            <a-switch
              :checked="record.enable"
              :loading="record._toggling"
              :checked-children="pageText('pages.enable')"
              :un-checked-children="pageText('pages.disable')"
              @change="(val) => handleToggleEnable(record, val)"
            />
          </template>

          <template v-if="column.key === 'action'">
            <div style="display: flex; gap: 12px; align-items: center;">
              <a @click="openEditModal(record)">{{ pageText('pages.editSource') }}</a>
              <a @click="openDryRunDirect(record)" style="color: #52c41a;">
                <thunderbolt-outlined /> {{ pageText('pages.debug') }}
              </a>
              <a-popconfirm :title="pageText('pages.deleteThisTemplate')" :ok-text="pageText('tasks.delete')" :cancel-text="pageText('tasks.cancel')" @confirm="handleSingleDelete(record.template_id)">
                <a class="page-danger">{{ pageText('tasks.delete') }}</a>
              </a-popconfirm>
            </div>
          </template>
        </template>

        <template #emptyText>
          <ArlEmpty :description="pageText('pages.noCustomTemplatesSelectNewTemplateOrImportTemplates')" />
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">
          {{ pageText('tasks.paginationSummary', { pages: Math.ceil(customPagination.total / customPagination.pageSize) || 1, total: customPagination.total }) }}
        </div>
        <a-pagination
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="customPagination.current"
          v-model:pageSize="customPagination.pageSize"
          :total="customPagination.total"
          show-size-changer
          size="small"
          @change="handleCustomPageChange"
          @showSizeChange="handleCustomPageChange"
        />
      </div>
    </template>

    <!-- 弹窗 1：新建 / 编辑自建模板弹窗 (带 Dry Run) -->
    <a-modal
      v-model:open="isEditModalVisible"
      :title="isCreateMode ? pageText('pages.newNucleiTemplate') : pageText('pages.editTemplateId', { id: currentEditTemplateId })"
      width="900px"
      :footer="null"
      :destroyOnClose="true"
    >
      <div style="display: flex; flex-direction: column; gap: 12px;">
        <!-- 骨架模板快速填充选择器 (仅新建时显示) -->
        <div v-if="isCreateMode" style="display: flex; align-items: center; justify-content: space-between; background: var(--arl-bg-layout); padding: 8px 12px; border-radius: 4px;">
          <span class="page-label">{{ pageText('pages.starterTemplate') }}</span>
          <a-select v-model:value="selectedSkeleton" style="width: 240px;" @change="handleSkeletonChange">
            <a-select-option value="http_get">{{ pageText('pages.standardHttpGetVulnerabilityCheck') }}</a-select-option>
            <a-select-option value="http_post">{{ pageText('pages.httpPostWithBodyAndHeaders') }}</a-select-option>
            <a-select-option value="file_leak">{{ pageText('pages.sensitiveInformationBackupFileDisclosure') }}</a-select-option>
            <a-select-option value="dns_check">{{ pageText('pages.dnsRecordMatching') }}</a-select-option>
          </a-select>
        </div>

        <!-- CodeMirror 代码编辑区域 -->
        <div style="border: 1px solid var(--arl-border-color); border-radius: 4px; overflow: hidden;">
          <codemirror
            v-model="currentEditorCode"
            :placeholder="pageText('pages.enterAValidNucleiYamlTemplateHere')"
            :style="{ height: '400px', fontSize: '13px' }"
            :autofocus="true"
            :indent-with-tab="true"
            :tab-size="2"
            :extensions="editExtensions"
          />
        </div>

        <!-- 错误提示横条 -->
        <a-alert v-if="saveErrorMsg" :message="saveErrorMsg" type="error" show-icon closable @close="saveErrorMsg = ''" />

        <!-- 在线即时调试 (Dry Run) 面板 -->
        <div class="dryrun-panel">
          <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 8px;">
            <div style="font-weight: 600; display: flex; align-items: center; gap: 6px;">
              <thunderbolt-outlined style="color: #faad14;" />
              <span>{{ pageText('pages.runAgainstOneTargetDryRun') }}</span>
            </div>
            <span class="page-faded-note">{{ pageText('pages.executionIsLimitedTo30Seconds') }}</span>
          </div>

          <div style="display: flex; gap: 8px; margin-bottom: 8px;">
            <a-input v-model:value="dryRunTarget" :placeholder="pageText('pages.testTargetEGHttpsExampleComOr1')" class="page-fill-space" />
            <a-button type="primary" ghost :loading="dryRunLoading" @click="executeDryRun">
              <template #icon><play-circle-outlined /></template>
              {{ pageText('pages.runTest') }}
            </a-button>
          </div>

          <div v-if="dryRunOutput" class="dryrun-console">
            <div style="display: flex; justify-content: space-between; margin-bottom: 4px; color: #8c8c8c; font-size: 11px;">
              <span>{{ pageText('pages.nucleiOutputElapsed') }} {{ dryRunCost }}s)</span>
              <a-tag :color="dryRunMatched ? 'red' : 'default'" size="small">
                {{ dryRunMatched ? pageText('pages.vulnerabilityMatched') : pageText('pages.noMatch') }}
              </a-tag>
            </div>
            <pre class="console-pre">{{ dryRunOutput }}</pre>
          </div>
        </div>

        <!-- 底部保存按钮 -->
        <div style="display: flex; justify-content: flex-end; gap: 12px; margin-top: 8px;">
          <a-button @click="isEditModalVisible = false">{{ pageText('assets.cancel') }}</a-button>
          <a-button type="primary" :loading="saveLoading" @click="saveTemplate">
            {{ pageText('pages.saveTemplate') }}
          </a-button>
        </div>
      </div>
    </a-modal>

    <!-- 弹窗 2：导入模板弹窗 -->
    <a-modal v-model:open="isImportModalVisible" :title="pageText('pages.importNucleiTemplatesInBulk')" :footer="null">
      <a-upload-dragger
        name="file"
        :multiple="true"
        action="/api/nuclei/template/import/"
        :headers="uploadHeaders"
        accept=".yaml,.yml,.zip"
        @change="handleUploadChange"
      >
        <p class="ant-upload-drag-icon"><inbox-outlined /></p>
        <p class="ant-upload-text">{{ pageText('pages.clickOrDragFilesHereToUpload') }}</p>
        <p class="ant-upload-hint">{{ pageText('pages.acceptsYamlYmlFilesOrAZipArchiveContaining') }}</p>
      </a-upload-dragger>
      <div style="margin-top: 12px; display: flex; justify-content: flex-end; align-items: center; font-size: 13px;">
        <span class="page-muted">{{ pageText('pages.needAStandardFormatExample') }}</span>
        <a @click="downloadSampleTemplate" style="margin-left: 6px; font-weight: 500;">
          <download-outlined /> {{ pageText('pages.downloadStandardYamlTemplate') }}
        </a>
      </div>
    </a-modal>

    <!-- 抽屉：查看社区模板源码 -->
    <a-drawer
      v-model:open="isCommunityDrawerVisible"
      :title="pageText('pages.communityTemplateSourceId', { id: selectedCommunityRecord?.template_id || '' })"
      placement="right"
      width="750"
    >
      <div v-if="communitySourceLoading" style="text-align: center; padding: 60px 0;">
        <a-spin :tip="pageText('pages.loadingTemplateSource')" />
      </div>
      <div v-else style="border: 1px solid var(--arl-border-color); border-radius: 4px; overflow: hidden;">
        <codemirror
          v-model="communitySourceCode"
          :disabled="true"
          :style="{ height: 'calc(100vh - 140px)', fontSize: '13px' }"
          :indent-with-tab="true"
          :tab-size="2"
          :extensions="editExtensions"
        />
      </div>
    </a-drawer>

    <!-- 弹窗 3：官方模板同步控制台 -->
    <a-modal
      v-model:open="isSyncLogModalVisible"
      :title="pageText('pages.communityTemplateSynchronizationConsole')"
      width="800px"
      :footer="null"
    >
      <div style="display: flex; flex-direction: column; gap: 12px;">
        <!-- 状态与指标面板 -->
        <div style="background: var(--arl-bg-layout); padding: 12px 16px; border-radius: 6px; border: 1px solid var(--arl-border-color); display: flex; flex-wrap: wrap; gap: 16px; align-items: center;">
          <div>
            <span class="page-secondary-label">{{ pageText('pages.currentStatus') }}</span>
            <a-tag v-if="syncStatus.status === 'syncing'" color="processing"><sync-outlined spin /> {{ pageText('pages.synchronizing') }}</a-tag>
            <a-tag v-else-if="syncStatus.status === 'success'" color="success"><check-circle-outlined /> {{ pageText('pages.synchronizationCompletedLabel2') }}</a-tag>
            <a-tag v-else-if="syncStatus.status === 'failed'" color="error"><close-circle-outlined /> {{ pageText('tasks.syncFailedLabel') }}</a-tag>
            <a-tag v-else>{{ pageText('pages.idle') }}</a-tag>
          </div>
          <div>
            <span class="page-secondary-label">{{ pageText('pages.currentVersion') }}</span>
            <a-tag color="blue">{{ formatTemplateVersion(syncStatus.current_version) }}</a-tag>
          </div>
          <div>
            <span class="page-secondary-label">{{ pageText('pages.latestCommunityVersion') }}</span>
            <a-tag color="purple">{{ formatTemplateVersion(syncStatus.latest_version) }}</a-tag>
          </div>
          <div>
            <span class="page-secondary-label">{{ pageText('pages.newTemplates') }}</span>
            <span style="font-weight: 600; color: var(--arl-theme-color);">{{ syncStatus.diff_count >= 0 ? '+' : '' }}{{ syncStatus.diff_count }}</span>
          </div>
          <div style="margin-left: auto;">
            <a-button size="small" :loading="syncStatusLoading" @click="fetchSyncStatus">
              <template #icon><sync-outlined /></template> {{ pageText('pages.refreshStatus') }}
            </a-button>
          </div>
        </div>

        <!-- 错误警示 (若有) -->
        <a-alert
          v-if="syncStatus.status === 'failed' && syncStatus.error_message"
          type="error"
          show-icon
          :message="pageText('pages.synchronizationFailed') + syncStatus.error_message"
          style="margin-bottom: 4px;"
        />

        <!-- 终端日志窗口 -->
        <div style="position: relative;">
          <div style="position: absolute; right: 12px; top: 10px; z-index: 10;">
            <a-button size="small" type="link" style="color: #aaa;" @click="copyText(syncStatus.log)">
              <template #icon><copy-outlined /></template> {{ pageText('pages.copyLogs') }}
            </a-button>
          </div>
          <pre class="arl-mono-terminal nuclei-sync-terminal">{{ syncStatus.log || pageText('pages.noConsoleLogsSelectSyncLatestCommunityVersionAbove') }}</pre>
        </div>

        <div style="display: flex; justify-content: flex-end; gap: 8px;">
          <a-button @click="isSyncLogModalVisible = false">{{ pageText('pages.close') }}</a-button>
        </div>
      </div>
    </a-modal>

    <!-- 弹窗 4：离线全量模板 ZIP 包导入 -->
    <a-modal v-model:open="isOfflineModalVisible" :title="pageText('pages.importCompleteCommunityTemplateArchiveZip')" :footer="null">
      <a-alert
        type="info"
        show-icon
        :message="pageText('pages.offlineUpdateMode')"
        :description="pageText('pages.uploadTheCompleteCommunityNucleiTemplatesZipArchiveTo')"
        style="margin-bottom: 16px;"
      />
      <a-upload-dragger
        name="file"
        :multiple="false"
        action="/api/nuclei/community/sync_offline/"
        :headers="uploadHeaders"
        accept=".zip"
        @change="handleOfflineUploadChange"
      >
        <p class="ant-upload-drag-icon"><cloud-upload-outlined /></p>
        <p class="ant-upload-text">{{ pageText('pages.clickOrDragNucleiTemplatesZipHere') }}</p>
        <p class="ant-upload-hint">{{ pageText('pages.theSystemWillExtractTheArchiveIntoTheCommunity') }}</p>
      </a-upload-dragger>
    </a-modal>

    <!-- 弹窗 5：标记误报原因录入弹窗 -->
    <a-modal
      v-model:open="isMarkModalVisible"
      :title="pageText('pages.markAsFalsePositiveAndExcludeFromScans')"
      :confirmLoading="markModalLoading"
      @ok="handleConfirmMarkBlacklist"
    >
      <div style="display: flex; flex-direction: column; gap: 14px; padding-top: 8px;">
        <a-alert
          type="warning"
          show-icon
          :message="pageText('pages.blockingBehavior')"
          :description="pageText('pages.addingThisTemplateToTheGlobalFalsePositiveBlocklist')"
        />
        <div>
          <span class="page-secondary-label-alt">{{ pageText('pages.templateId') }}</span>
          <span class="arl-mono" style="font-weight: 600; color: #fa8c16; margin-left: 6px;">{{ markModalForm.template_id }}</span>
        </div>
        <div>
          <span class="page-secondary-label-alt">{{ pageText('pages.vulnerabilityName') }}</span>
          <span style="font-weight: 500; margin-left: 6px;">{{ markModalForm.name }}</span>
        </div>
        <div>
          <div style="margin-bottom: 6px; font-size: 13px; font-weight: 500;">
            {{ pageText('pages.reasonForBlocking') }}
          </div>
          <a-textarea
            v-model:value="markModalForm.reason"
            :placeholder="pageText('pages.eGAFalsePositiveCausedByWildcardRouting')"
            :rows="3"
            allowClear
          />
          <div style="display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px;">
            <span class="page-subtle-label">{{ pageText('pages.quickReasons') }}</span>
            <a-tag class="page-clickable" @click="markModalForm.reason = '内网泛解析与统一404状态码误判'">{{ pageText('pages.wildcardRouting') }}</a-tag>
            <a-tag class="page-clickable" @click="markModalForm.reason = '特定CMS版本指纹匹配过宽'">{{ pageText('pages.broadFingerprintMatch') }}</a-tag>
            <a-tag class="page-clickable" @click="markModalForm.reason = '反向代理网关默认返回特定响应头误报'">{{ pageText('pages.gatewayResponse') }}</a-tag>
            <a-tag class="page-clickable" @click="markModalForm.reason = '业务自定义静态资源文件名称重合'">{{ pageText('pages.matchingFilePath') }}</a-tag>
          </div>
        </div>
      </div>
    </a-modal>

    <!-- 弹窗 6：手动录入误报模板弹窗 -->
    <a-modal
      v-model:open="isAddBlacklistModalVisible"
      :title="pageText('pages.addToFalsePositiveBlocklist')"
      :confirmLoading="addBlacklistLoading"
      @ok="handleConfirmAddBlacklist"
    >
      <div style="display: flex; flex-direction: column; gap: 14px; padding-top: 8px;">
        <a-form :label-wrap="true" layout="vertical">
          <a-form-item :label="pageText('pages.templateIdRequired')" required>
            <a-input v-model:value="addBlacklistForm.template_id" :placeholder="pageText('pages.eGCve202141773OrApacheStatus')" allowClear />
          </a-form-item>
          <a-form-item :label="pageText('pages.vulnerabilityNameOptional')">
            <a-input v-model:value="addBlacklistForm.name" :placeholder="pageText('pages.enterABriefVulnerabilityDescription')" allowClear />
          </a-form-item>
          <a-form-item :label="pageText('pages.severityLabel3')">
            <a-select v-model:value="addBlacklistForm.severity" style="width: 100%;">
              <a-select-option value="critical">{{ pageText('pages.critical') }}</a-select-option>
              <a-select-option value="high">{{ pageText('pages.high') }}</a-select-option>
              <a-select-option value="medium">{{ pageText('pages.medium') }}</a-select-option>
              <a-select-option value="low">{{ pageText('pages.low') }}</a-select-option>
              <a-select-option value="info">{{ pageText('pages.info') }}</a-select-option>
              <a-select-option value="unknown">{{ pageText('pages.unknown') }}</a-select-option>
            </a-select>
          </a-form-item>
          <a-form-item :label="pageText('pages.reasonForBlockingLabel2')">
            <a-textarea v-model:value="addBlacklistForm.reason" :placeholder="pageText('pages.explainWhyThisTemplateShouldBeBlocked')" :rows="3" allowClear />
          </a-form-item>
        </a-form>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';
import { ref, reactive, onMounted, onBeforeUnmount, computed, watch } from 'vue';
import { message, notification } from 'ant-design-vue';
import {
  PlusOutlined,
  CloudUploadOutlined,
  CloudDownloadOutlined,
  DownloadOutlined,
  DeleteOutlined,
  SearchOutlined,
  InboxOutlined,
  SyncOutlined,
  CopyOutlined,
  ThunderboltOutlined,
  PlayCircleOutlined,
  FileTextOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  StopOutlined,
  CheckOutlined
} from '@ant-design/icons-vue';
import { Codemirror } from 'vue-codemirror';
import { oneDark } from '@codemirror/theme-one-dark';
import request from '../utils/request';
import { downloadAuthenticated } from '../utils/authenticatedFiles';
import { useSticky } from '../utils/useSticky';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';

const { t: pageText, locale: pageLocale } = useI18n({ useScope: 'global' });

const nucleiActionBarRef = ref(null);
const { stickyConfig } = useSticky(nucleiActionBarRef);
const globalPageSize = useGlobalPageSize(10);

const editExtensions = [oneDark];
const uploadHeaders = computed(() => {
  const token = localStorage.getItem('token');
  return token ? { Token: token } : {};
});

// ---------- 页面状态与统计 ----------
const formatTemplateVersion = version => {
  const keys = { '检测中': 'pages.detecting', '未知': 'tasks.unknown', '未安装': 'pages.notInstalled', '未下载': 'pages.notDownloaded' };
  return keys[version] ? pageText(keys[version]) : (version || pageText('tasks.unknown'));
};

const innerTab = ref('community');
const stats = reactive({
  custom_total: 0,
  custom_enabled: 0,
  community_total: 0,
  blacklist_total: 0,
  nuclei_version: '检测中',
  template_version: '检测中',
  template_latest_version: '未知',
  has_template_update: false
});

const fetchStats = async () => {
  try {
    const res = await request.get('/nuclei/stats/');
    if (res.code === 200 && res.data) {
      stats.custom_total = res.data.custom_total || 0;
      stats.custom_enabled = res.data.custom_enabled || 0;
      stats.community_total = res.data.community_total || 0;
      stats.blacklist_total = res.data.blacklist_total || 0;
      stats.nuclei_version = res.data.nuclei_version || '未知';
      stats.template_version = res.data.template_version || '未知';
      stats.template_latest_version = res.data.template_latest_version || '未知';
      stats.has_template_update = Boolean(res.data.has_template_update);
    }
  } catch (e) {
    console.error('Failed to fetch nuclei stats:', e);
  }
};

// ---------- 自建模板工作区 ----------
const customLoading = ref(false);
const customList = ref([]);
const selectedRowKeys = ref([]);
const batchDeleteLoading = ref(false);

const customSearch = reactive({
  template_id: '',
  name: '',
  severity: undefined,
  tag: ''
});

const customPagination = reactive({
  current: 1,
  pageSize: globalPageSize.value,
  total: 0
});

const customColumns = [
  { get title() { return pageText('tasks.no'); }, key: 'index', width: 65, align: 'center' },
  { get title() { return pageText('pages.templateIdLabel2'); }, key: 'template_id', width: 220 },
  { get title() { return pageText('tasks.vulnerabilityName'); }, key: 'name', minWidth: 200 },
  { get title() { return pageText('pages.severityLabel3'); }, key: 'severity', width: 110, align: 'center' },
  { get title() { return pageText('pages.tagsLabel2'); }, key: 'tags', width: 180 },
  { get title() { return pageText('assets.updatedAtLabel'); }, dataIndex: 'updated_at', key: 'updated_at', width: 170 },
  { get title() { return pageText('tasks.status'); }, key: 'enable', width: 90, align: 'center' },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 180, align: 'center' }
];

const fetchCustomTemplates = async () => {
  customLoading.value = true;
  try {
    const params = {
      page: customPagination.current,
      size: customPagination.pageSize,
      template_id: customSearch.template_id || undefined,
      name: customSearch.name || undefined,
      severity: customSearch.severity || undefined,
      tag: customSearch.tag || undefined
    };
    const res = await request.get('/nuclei/template/', { params });
    if (res.code === 200 && res.data) {
      customList.value = res.data.items || [];
      customPagination.total = res.data.total || 0;
    }
  } catch (e) {
    message.error(pageText('pages.failedToLoadCustomTemplates'));
  } finally {
    customLoading.value = false;
  }
};

const onSearchCustom = () => {
  customPagination.current = 1;
  fetchCustomTemplates();
};

const resetSearchCustom = () => {
  customSearch.template_id = '';
  customSearch.name = '';
  customSearch.severity = undefined;
  customSearch.tag = '';
  onSearchCustom();
};

const onSelectChange = (keys) => {
  selectedRowKeys.value = keys;
};

// 单个启停切换
const handleToggleEnable = async (record, val) => {
  record._toggling = true;
  try {
    const res = await request.post('/nuclei/template/toggle/', {
      template_id: record.template_id,
      enable: val
    });
    if (res.code === 200) {
      record.enable = val;
      message.success(pageText('pages.templateActionCompletedAction', { action: val ? pageText('pages.enable') : pageText('pages.disable') }));
      fetchStats();
    } else {
      message.error(res.message || res.error || pageText('pages.failedToChangeTemplateStatus'));
    }
  } catch (e) {
    message.error(pageText('tasks.requestFailed'));
  } finally {
    record._toggling = false;
  }
};

// 批量启停切换
const handleBatchToggle = async (enableVal) => {
  if (selectedRowKeys.value.length === 0) return;
  try {
    const res = await request.post('/nuclei/template/batch_toggle/', {
      template_ids: selectedRowKeys.value,
      enable: enableVal
    });
    if (res.code === 200) {
      message.success(pageText('pages.actionCountTemplatesUpdated', { action: enableVal ? pageText('pages.enable') : pageText('pages.disable'), count: res.data?.modified_count || selectedRowKeys.value.length }));
      fetchCustomTemplates();
      fetchStats();
    }
  } catch (e) {
    message.error(pageText('pages.bulkOperationFailed'));
  }
};

// 单个删除
const handleSingleDelete = async (templateId) => {
  try {
    const res = await request.post('/nuclei/template/delete/', { template_ids: [templateId] });
    if (res.code === 200) {
      message.success(pageText('pages.templateDeleted'));
      selectedRowKeys.value = selectedRowKeys.value.filter(k => k !== templateId);
      fetchCustomTemplates();
      fetchStats();
    }
  } catch (e) {
    message.error(pageText('pages.deletionRequestFailed'));
  }
};

// 批量删除
const handleBatchDelete = async () => {
  if (selectedRowKeys.value.length === 0) return;
  batchDeleteLoading.value = true;
  try {
    const res = await request.post('/nuclei/template/delete/', { template_ids: selectedRowKeys.value });
    if (res.code === 200) {
      message.success(pageText('pages.templatesDeletedCount', { count: res.data?.delete_cnt || 0 }));
      selectedRowKeys.value = [];
      fetchCustomTemplates();
      fetchStats();
    }
  } catch (e) {
    message.error(pageText('pages.templateDeletionFailed'));
  } finally {
    batchDeleteLoading.value = false;
  }
};

// 导出
const handleExport = async () => {
  let url = '/api/nuclei/template/export/';
  if (selectedRowKeys.value.length > 0) {
    url += `?template_ids=${selectedRowKeys.value.join(',')}`;
  }
  try {
    await downloadAuthenticated(url, 'nuclei_templates.zip');
  } catch (error) {
    message.error(error.message);
  }
};

// ---------- 骨架模板预设 ----------
const skeletonTemplates = {
  http_get: `id: custom-poc-demo

info:
  name: Custom Demo Vulnerability (GET)
  author: security-team
  severity: high
  description: 探测目标是否存在特定敏感路径与漏洞关键字
  tags: custom,demo,rce

http:
  - method: GET
    path:
      - "{{BaseURL}}/actuator/env"
      - "{{BaseURL}}/env"
    matchers-condition: and
    matchers:
      - type: word
        words:
          - "spring.cloud"
          - "server.port"
        condition: or
      - type: status
        status:
          - 200
`,
  http_post: `id: custom-poc-post-payload

info:
  name: Custom POST Exploit Check
  author: security-team
  severity: critical
  description: 带有自定义 Header 与 Payload 的 POST 请求验证
  tags: custom,rce

http:
  - method: POST
    path:
      - "{{BaseURL}}/api/check"
    headers:
      Content-Type: application/json
      X-Forwarded-For: 127.0.0.1
    body: |
      {"action": "test", "command": "id"}
    matchers-condition: and
    matchers:
      - type: word
        words:
          - "uid="
          - "gid="
      - type: status
        status:
          - 200
`,
  file_leak: `id: custom-sensitive-file-leak

info:
  name: Sensitive Backup File Leak
  author: security-team
  severity: medium
  description: 检测 Web 站点是否存在常见数据库与备份配置泄露
  tags: leak,config

http:
  - method: GET
    path:
      - "{{BaseURL}}/.git/config"
      - "{{BaseURL}}/.env"
      - "{{BaseURL}}/config.inc.php.bak"
    matchers-condition: or
    matchers:
      - type: word
        words:
          - "[core]"
          - "DB_PASSWORD"
      - type: status
        status:
          - 200
`,
  dns_check: `id: custom-dns-cname-takeover

info:
  name: DNS CNAME Takeover Check
  author: security-team
  severity: high
  description: 针对域名的 CNAME 悬挂指向实施探测
  tags: dns,takeover

dns:
  - name: "{{FQDN}}"
    type: CNAME
    matchers:
      - type: word
        words:
          - "trafficmanager.net"
          - "herokuapp.com"
`
};

// ---------- 新建 / 编辑弹窗逻辑 ----------
const isEditModalVisible = ref(false);
const isCreateMode = ref(false);
const currentEditTemplateId = ref('');
const currentEditorCode = ref('');
const selectedSkeleton = ref('http_get');
const saveLoading = ref(false);
const saveErrorMsg = ref('');

const openCreateModal = () => {
  isCreateMode.value = true;
  currentEditTemplateId.value = '';
  selectedSkeleton.value = 'http_get';
  currentEditorCode.value = skeletonTemplates.http_get;
  saveErrorMsg.value = '';
  dryRunOutput.value = '';
  isEditModalVisible.value = true;
};

const openEditModal = async (record) => {
  isCreateMode.value = false;
  currentEditTemplateId.value = record.template_id;
  saveErrorMsg.value = '';
  dryRunOutput.value = '';
  isEditModalVisible.value = true;

  try {
    const res = await request.get('/nuclei/template/detail/', { params: { template_id: record.template_id } });
    if (res.code === 200 && res.data) {
      currentEditorCode.value = res.data.content || '';
    } else {
      message.error(pageText('pages.failedToLoadTemplateSource') + (res.message || pageText('tasks.unknownError')));
    }
  } catch (e) {
    message.error(pageText('pages.failedToLoadTemplateData'));
  }
};

const handleSkeletonChange = (val) => {
  if (skeletonTemplates[val]) {
    currentEditorCode.value = skeletonTemplates[val];
  }
};

const saveTemplate = async () => {
  saveErrorMsg.value = '';
  if (!currentEditorCode.value.trim()) {
    saveErrorMsg.value = pageText('pages.templateContentCannotBeEmpty');
    return;
  }
  saveLoading.value = true;
  try {
    const endpoint = isCreateMode.value ? '/nuclei/template/create/' : '/nuclei/template/update/';
    const payload = isCreateMode.value
      ? { content: currentEditorCode.value, enable: true }
      : { template_id: currentEditTemplateId.value, content: currentEditorCode.value };

    const res = await request.post(endpoint, payload);
    if (res.code === 200) {
      message.success(isCreateMode.value ? pageText('pages.templateCreated') : pageText('pages.templateUpdated'));
      isEditModalVisible.value = false;
      fetchCustomTemplates();
      fetchStats();
    } else {
      saveErrorMsg.value = res.message || res.error || pageText('pages.failedToSaveLabel2');
    }
  } catch (e) {
    saveErrorMsg.value = pageText('pages.requestFailedChangesWereNotSavedLabel2');
  } finally {
    saveLoading.value = false;
  }
};

// ---------- Dry Run 即时调试 ----------
const dryRunTarget = ref('');
const dryRunLoading = ref(false);
const dryRunOutput = ref('');
const dryRunMatched = ref(false);
const dryRunCost = ref(0);

const openDryRunDirect = (record) => {
  openEditModal(record);
};

const executeDryRun = async () => {
  if (!dryRunTarget.value.trim()) {
    message.warning(pageText('pages.enterATargetUrlToTest'));
    return;
  }
  dryRunLoading.value = true;
  dryRunOutput.value = pageText('pages.startingTheNucleiTestPleaseWait');
  try {
    const res = await request.post('/nuclei/template/test/', {
      content: currentEditorCode.value,
      target: dryRunTarget.value.trim()
    });
    if (res.code === 200 && res.data) {
      dryRunOutput.value = res.data.output || pageText('pages.noStandardOutput');
      dryRunMatched.value = !!res.data.matched;
      dryRunCost.value = res.data.cost_seconds || 0;
      if (dryRunMatched.value) {
        message.success(pageText('pages.vulnerabilityMatchingConditionsMet'));
      } else {
        message.info(pageText('pages.testCompletedNoVulnerabilityRuleMatched'));
      }
    } else {
      dryRunOutput.value = pageText('pages.executionFailed') + (res.message || res.error || pageText('tasks.unknownError'));
      dryRunMatched.value = false;
    }
  } catch (e) {
    dryRunOutput.value = pageText('pages.requestFailedLabel2') + e.message;
  } finally {
    dryRunLoading.value = false;
  }
};

// ---------- 导入弹窗 ----------
const isImportModalVisible = ref(false);
const handleUploadChange = (info) => {
  const status = info.file.status;
  if (status === 'done') {
    const res = info.file.response;
    if (res && res.code === 200) {
      message.success(pageText('pages.importCompletedSuccessSucceededFailedFailed', { success: res.data.success_count || 0, failed: res.data.fail_count || 0 }));
      isImportModalVisible.value = false;
      fetchCustomTemplates();
      fetchStats();
    } else {
      message.error(res?.message || res?.error || pageText('pages.importFailed'));
    }
  } else if (status === 'error') {
    message.error(pageText('pages.networkErrorUploadingFile'));
  }
};

// 下载标准 YAML 模板
const downloadSampleTemplate = () => {
  const blob = new Blob([skeletonTemplates.http_get], { type: 'text/yaml;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'nuclei_sample_template.yaml';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

// ---------- 社区模板库只读检索 ----------
const communityLoading = ref(false);
const communityList = ref([]);
const communitySearch = reactive({
  search: '',
  severity: undefined,
  blacklist_status: 'all'
});
const communityPagination = reactive({
  current: 1,
  pageSize: globalPageSize.value,
  total: 0
});

const communityColumns = [
  { get title() { return pageText('tasks.no'); }, key: 'index', width: 65, align: 'center' },
  { get title() { return pageText('pages.templateIdLabel2'); }, key: 'template_id', width: 220 },
  { get title() { return pageText('tasks.vulnerabilityName'); }, dataIndex: 'name', key: 'name', minWidth: 220 },
  { get title() { return pageText('pages.severityLabel3'); }, key: 'severity', width: 110, align: 'center' },
  { get title() { return pageText('tasks.status'); }, key: 'status', width: 120, align: 'center' },
  { get title() { return pageText('pages.relativeFilePath'); }, key: 'file_path', minWidth: 260 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 200, align: 'center' }
];

const fetchCommunityTemplates = async () => {
  communityLoading.value = true;
  try {
    const params = {
      page: communityPagination.current,
      size: communityPagination.pageSize,
      search: communitySearch.search || undefined,
      severity: communitySearch.severity || undefined,
      blacklist_status: communitySearch.blacklist_status !== 'all' ? communitySearch.blacklist_status : undefined
    };
    const res = await request.get('/nuclei/community/', { params });
    if (res.code === 200 && res.data) {
      communityList.value = res.data.items || [];
      communityPagination.total = res.data.total || 0;
    }
  } catch (e) {
    message.error(pageText('pages.failedToLoadCommunityTemplates'));
  } finally {
    communityLoading.value = false;
  }
};

const onSearchCommunity = () => {
  communityPagination.current = 1;
  fetchCommunityTemplates();
};

const resetSearchCommunity = () => {
  communitySearch.search = '';
  communitySearch.severity = undefined;
  communitySearch.blacklist_status = 'all';
  onSearchCommunity();
};

// ---------- 误报黑名单治理管理 (Blacklist) ----------
const blacklistLoading = ref(false);
const blacklistItems = ref([]);
const blacklistSelectedRowKeys = ref([]);
const blacklistSearch = reactive({
  search: '',
  severity: undefined
});
const blacklistPagination = reactive({
  current: 1,
  pageSize: globalPageSize.value,
  total: 0
});

const blacklistColumns = [
  { get title() { return pageText('tasks.no'); }, key: 'index', width: 65, align: 'center' },
  { get title() { return pageText('pages.templateIdLabel2'); }, key: 'template_id', width: 220 },
  { get title() { return pageText('tasks.vulnerabilityName'); }, key: 'name', minWidth: 200 },
  { get title() { return pageText('pages.severityLabel3'); }, key: 'severity', width: 110, align: 'center' },
  { get title() { return pageText('pages.reasonForBlockingLabel2'); }, key: 'reason', minWidth: 260 },
  { get title() { return pageText('pages.blockedAt'); }, key: 'created_at', width: 170, align: 'center' },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 170, align: 'center' }
];

const fetchBlacklist = async () => {
  blacklistLoading.value = true;
  try {
    const params = {
      page: blacklistPagination.current,
      size: blacklistPagination.pageSize,
      search: blacklistSearch.search || undefined,
      severity: blacklistSearch.severity || undefined
    };
    const res = await request.get('/nuclei/blacklist/', { params });
    if (res.code === 200 && res.data) {
      blacklistItems.value = res.data.items || [];
      blacklistPagination.total = res.data.total || 0;
    }
  } catch (e) {
    message.error(pageText('pages.failedToLoadFalsePositiveBlocklist'));
  } finally {
    blacklistLoading.value = false;
  }
};

const onSearchBlacklist = () => {
  blacklistPagination.current = 1;
  fetchBlacklist();
};

const resetSearchBlacklist = () => {
  blacklistSearch.search = '';
  blacklistSearch.severity = undefined;
  onSearchBlacklist();
};

const onBlacklistSelectChange = (keys) => {
  blacklistSelectedRowKeys.value = keys;
};

// 标记误报弹窗
const isMarkModalVisible = ref(false);
const markModalLoading = ref(false);
const markModalForm = reactive({
  template_id: '',
  name: '',
  severity: '',
  tags: [],
  reason: ''
});

const openMarkBlacklistModal = (record) => {
  markModalForm.template_id = record.template_id;
  markModalForm.name = record.name || record.template_id;
  markModalForm.severity = record.severity || 'unknown';
  markModalForm.tags = record.tags || [];
  markModalForm.reason = '内网泛解析与统一404状态码误判';
  isMarkModalVisible.value = true;
};

const handleConfirmMarkBlacklist = async () => {
  if (!markModalForm.template_id) return;
  markModalLoading.value = true;
  try {
    const res = await request.post('/nuclei/blacklist/', {
      template_id: markModalForm.template_id,
      name: markModalForm.name,
      severity: markModalForm.severity,
      tags: markModalForm.tags,
      reason: markModalForm.reason || '手工标记误报'
    });
    if (res.code === 200) {
      message.success(pageText('pages.templateIdAddedToTheFalsePositiveBlocklist', { id: markModalForm.template_id }));
      isMarkModalVisible.value = false;
      fetchCommunityTemplates();
      fetchBlacklist();
      fetchStats();
    } else {
      message.error(res.message || pageText('pages.failedToMarkTemplate'));
    }
  } catch (e) {
    message.error(pageText('pages.requestFailedLabel3'));
  } finally {
    markModalLoading.value = false;
  }
};

// 手动录入误报弹窗
const isAddBlacklistModalVisible = ref(false);
const addBlacklistLoading = ref(false);
const addBlacklistForm = reactive({
  template_id: '',
  name: '',
  severity: 'unknown',
  reason: ''
});

const openAddBlacklistModal = () => {
  addBlacklistForm.template_id = '';
  addBlacklistForm.name = '';
  addBlacklistForm.severity = 'unknown';
  addBlacklistForm.reason = '';
  isAddBlacklistModalVisible.value = true;
};

const handleConfirmAddBlacklist = async () => {
  if (!addBlacklistForm.template_id.trim()) {
    message.warning(pageText('pages.enterATemplateId'));
    return;
  }
  addBlacklistLoading.value = true;
  try {
    const res = await request.post('/nuclei/blacklist/', {
      template_id: addBlacklistForm.template_id.trim(),
      name: addBlacklistForm.name.trim() || addBlacklistForm.template_id.trim(),
      severity: addBlacklistForm.severity,
      reason: addBlacklistForm.reason.trim() || '手动录入误报'
    });
    if (res.code === 200) {
      message.success(pageText('pages.templateIdAddedToTheBlocklist', { id: addBlacklistForm.template_id }));
      isAddBlacklistModalVisible.value = false;
      fetchBlacklist();
      fetchCommunityTemplates();
      fetchStats();
    } else {
      message.error(res.message || pageText('pages.failedToAdd'));
    }
  } catch (e) {
    message.error(pageText('tasks.networkRequestFailed'));
  } finally {
    addBlacklistLoading.value = false;
  }
};

// 单个解除屏蔽
const handleRemoveBlacklist = async (templateId) => {
  try {
    const res = await request.delete(`/nuclei/blacklist/${templateId}/`);
    if (res.code === 200) {
      message.success(pageText('pages.templateIdIncludedInScansAgain', { id: templateId }));
      fetchBlacklist();
      fetchCommunityTemplates();
      fetchStats();
      blacklistSelectedRowKeys.value = blacklistSelectedRowKeys.value.filter(k => k !== templateId);
    } else {
      message.error(res.message || pageText('pages.failedToUnblockTemplate'));
    }
  } catch (e) {
    message.error(pageText('pages.requestFailed'));
  }
};

// 批量解除屏蔽
const handleBatchRemoveBlacklist = async () => {
  if (blacklistSelectedRowKeys.value.length === 0) return;
  try {
    const res = await request.post('/nuclei/blacklist/delete/', { template_ids: blacklistSelectedRowKeys.value });
    if (res.code === 200) {
      message.success(pageText('pages.templatesUnblockedCount', { count: res.data?.deleted_count || 0 }));
      blacklistSelectedRowKeys.value = [];
      fetchBlacklist();
      fetchCommunityTemplates();
      fetchStats();
    } else {
      message.error(res.message || pageText('pages.bulkOperationFailed'));
    }
  } catch (e) {
    message.error(pageText('tasks.networkRequestFailed'));
  }
};

// ---------- 官方社区模板同步控制中心 ----------
const isSyncLogModalVisible = ref(false);
const isOfflineModalVisible = ref(false);
const syncStatusLoading = ref(false);
let syncTimer = null;

const syncStatus = reactive({
  status: 'idle',
  sync_mode: 'online',
  start_time: '',
  end_time: '',
  current_version: '未知',
  latest_version: '未知',
  has_update: false,
  before_total: 0,
  after_total: 0,
  diff_count: 0,
  log: '',
  error_message: ''
});

const openSyncLogModal = () => {
  fetchSyncStatus();
  isSyncLogModalVisible.value = true;
};

const fetchSyncStatus = async () => {
  syncStatusLoading.value = true;
  try {
    const res = await request.get('/nuclei/community/sync_status/');
    if (res.code === 200 && res.data) {
      Object.assign(syncStatus, res.data);
      if (syncStatus.status === 'syncing' && !syncTimer) {
        startSyncPolling();
      }
    }
  } catch (e) {
    console.error('获取同步状态失败:', e);
  } finally {
    syncStatusLoading.value = false;
  }
};

const stopSyncPolling = () => {
  if (syncTimer) {
    clearInterval(syncTimer);
    syncTimer = null;
  }
};

const startSyncPolling = () => {
  stopSyncPolling();
  syncTimer = setInterval(async () => {
    try {
      const res = await request.get('/nuclei/community/sync_status/');
      if (res.code === 200 && res.data) {
        Object.assign(syncStatus, res.data);
        if (syncStatus.status !== 'syncing') {
          stopSyncPolling();
          if (syncStatus.status === 'success') {
            notification.success({
              message: pageText('pages.communityTemplatesSynchronized'),
              description: pageText('pages.updatedToVersionVersionNewTemplatesSignCount', { version: syncStatus.current_version, sign: syncStatus.diff_count >= 0 ? '+' : '', count: syncStatus.diff_count }),
              duration: 5
            });
            fetchStats();
            fetchCommunityTemplates();
          } else if (syncStatus.status === 'failed') {
            notification.error({
              message: pageText('pages.communityTemplateSynchronizationFailed'),
              description: syncStatus.error_message || pageText('pages.synchronizationFailedOpenViewSynchronizationLogsToInvestigate'),
              duration: 7
            });
          }
        }
      }
    } catch (e) {
      console.error('轮询同步状态异常:', e);
    }
  }, 2500);
};

const handleSyncCommunity = async () => {
  try {
    const res = await request.post('/nuclei/community/sync/');
    if (res.code === 200) {
      message.loading(pageText('pages.communityTemplateSynchronizationQueuedDownloadingInTheBackground'), 2.5);
      syncStatus.status = 'syncing';
      startSyncPolling();
    } else {
      message.warning(res.message || pageText('pages.unableToStartSynchronization'));
    }
  } catch (e) {
    message.error(pageText('pages.failedToRequestSynchronization'));
  }
};

const handleOfflineUploadChange = (info) => {
  const status = info.file.status;
  if (status === 'done') {
    const res = info.file.response;
    if (res && res.code === 200) {
      message.success(res.data?.message || pageText('pages.offlineTemplateArchiveUploadedBackgroundExtractionStarted'));
      isOfflineModalVisible.value = false;
      syncStatus.status = 'syncing';
      startSyncPolling();
    } else {
      message.error(res?.message || pageText('pages.failedToParseOfflineArchive'));
    }
  } else if (status === 'error') {
    message.error(pageText('pages.failedToUploadOfflineArchive'));
  }
};

// 社区源码抽屉
const isCommunityDrawerVisible = ref(false);
const selectedCommunityRecord = ref(null);
const communitySourceCode = ref('');
const communitySourceLoading = ref(false);

const viewCommunitySource = async (record) => {
  selectedCommunityRecord.value = record;
  communitySourceCode.value = pageText('pages.readingCommunityTemplateYamlSource');
  communitySourceLoading.value = true;
  isCommunityDrawerVisible.value = true;
  try {
    const res = await request.get('/nuclei/community/source/', {
      params: { file_path: record.file_path, template_id: record.template_id }
    });
    if (res.code === 200 && res.data) {
      communitySourceCode.value = res.data.content || '';
    } else {
      communitySourceCode.value = pageText('pages.failedToRead') + (res.message || pageText('pages.fileNotFound'));
    }
  } catch (e) {
    communitySourceCode.value = pageText('pages.requestFailedLabel4');
  } finally {
    communitySourceLoading.value = false;
  }
};

// 辅助方法
const getSeverityColor = (sev) => {
  const s = String(sev || '').toLowerCase();
  if (s === 'critical') return 'red';
  if (s === 'high') return 'volcano';
  if (s === 'medium') return 'orange';
  if (s === 'low') return 'blue';
  if (s === 'info') return 'green';
  return 'default';
};

const copyText = (txt) => {
  navigator.clipboard.writeText(txt);
  message.success(pageText('pages.copiedToClipboard'));
};

const makePageChangeHandler = (paginationState, fetcher) => (page, pageSize) => {
  paginationState.current = page;
  if (pageSize && pageSize !== paginationState.pageSize) {
    paginationState.pageSize = pageSize;
  }
  if (paginationState.pageSize !== globalPageSize.value) {
    globalPageSize.value = paginationState.pageSize;
  }
  fetcher();
};

const handleCommunityPageChange = makePageChangeHandler(communityPagination, fetchCommunityTemplates);
const handleBlacklistPageChange = makePageChangeHandler(blacklistPagination, fetchBlacklist);
const handleCustomPageChange = makePageChangeHandler(customPagination, fetchCustomTemplates);

watch(globalPageSize, (newSize) => {
  communityPagination.pageSize = newSize;
  blacklistPagination.pageSize = newSize;
  customPagination.pageSize = newSize;
});

watch(innerTab, (newTab) => {
  if (newTab === 'blacklist') {
    fetchBlacklist();
  } else if (newTab === 'community') {
    fetchCommunityTemplates();
  } else if (newTab === 'custom') {
    fetchCustomTemplates();
  }
});

onMounted(() => {
  fetchStats();
  fetchCustomTemplates();
  fetchCommunityTemplates();
  fetchBlacklist();
  fetchSyncStatus();
});

onBeforeUnmount(() => {
  stopSyncPolling();
});
</script>

<style scoped>
.nuclei-sync-terminal {
  max-height: 380px;
}

.nuclei-manage-container {
  display: flex;
  flex-direction: column;
}

.nuclei-hero-meta {
  flex-wrap: wrap;
  gap: 12px;
}

.nuclei-meta-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
}

.nuclei-sub-toolbar {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid var(--arl-border-color);
}

.dryrun-panel {
  background: var(--arl-bg-subtle);
  border: 1px dashed var(--arl-border-color);
  padding: 12px;
  border-radius: 6px;
}

.dryrun-console {
  background: var(--arl-terminal-bg);
  border: 1px solid var(--arl-terminal-border);
  border-radius: 4px;
  padding: 10px;
  margin-top: 8px;
}

.console-pre {
  color: var(--arl-terminal-text);
  font-family: var(--arl-font-mono);
  font-size: 12px;
  line-height: 1.5;
  margin: 0;
  max-height: 200px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

.page-version-note { margin-left: 4px; font-size: 11px; }
.page-quiet-status-tag { margin: 0; font-weight: 500; }
.page-width-240 { width: 240px; }
.page-width-130 { width: 130px; }
.page-width-140 { width: 140px; }
.page-clickable { cursor: pointer; }
.page-success { color: #52c41a; }
.page-width-150 { width: 150px; }
.page-danger { color: #ff4d4f; }
.page-label { font-size: 13px; font-weight: 500; }
.page-faded-note { font-size: 12px; opacity: 0.5; }
.page-fill-space { flex: 1; }
.page-muted { color: var(--arl-text-color); opacity: 0.65; }
.page-secondary-label { color: var(--arl-text-color); opacity: 0.65; font-size: 13px; }
.page-secondary-label-alt { font-size: 13px; color: var(--arl-text-color); opacity: 0.65; }
.page-subtle-label { font-size: 12px; opacity: 0.6; }

.page-wide-text .nuclei-hero-meta { row-gap: 8px; }
</style>
