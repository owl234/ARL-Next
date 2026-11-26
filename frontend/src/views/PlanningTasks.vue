<template>
  <div class="arl-page-container" :class="{ 'page-wide-text': taskLocale !== 'zh-CN' }">
    <!-- 1. 吸顶操作栏与三段式英雄头部卡片（对齐 /taskList 设计范式） -->
    <div ref="actionBarRef" class="arl-hero-card">
      <!-- 顶层主栏：标题 + 大类切换胶囊 + 自动刷新与主创建按钮 -->
      <div class="arl-hero-unified-bar">
        <div class="arl-hero-left">
          <div class="arl-hero-title">
            <span class="title-text">{{ taskText('navigation.schedules') }}</span>
          </div>
          <div class="arl-capsule-switcher">
            <button
              type="button"
              class="arl-capsule-item"
              :class="{ 'is-active': activeCategory === 'all' }"
              @click="onCategoryChange('all')"
            >
              <appstore-outlined class="capsule-icon" />
              <span>{{ taskText('tasks.allSchedules') }}</span>
              <span class="arl-capsule-count">
                <span v-if="categoryActiveCounts.all > 0" class="arl-capsule-dot is-pulse"></span>
                {{ categoryCounts.all }}
              </span>
            </button>
            <button
              type="button"
              class="arl-capsule-item"
              :class="{ 'is-active': activeCategory === 'planning' }"
              @click="onCategoryChange('planning')"
            >
              <clock-circle-outlined class="capsule-icon" />
              <span>{{ taskText('tasks.scheduledScans') }}</span>
              <span class="arl-capsule-count">
                <span v-if="categoryActiveCounts.planning > 0" class="arl-capsule-dot is-pulse"></span>
                {{ categoryCounts.planning }}
              </span>
            </button>
            <button
              type="button"
              class="arl-capsule-item"
              :class="{ 'is-active': activeCategory === 'monitor' }"
              @click="onCategoryChange('monitor')"
            >
              <radar-chart-outlined class="capsule-icon" />
              <span>{{ taskText('tasks.continuousAssetMonitoring') }}</span>
              <span class="arl-capsule-count">
                <span v-if="categoryActiveCounts.monitor > 0" class="arl-capsule-dot is-pulse"></span>
                {{ categoryCounts.monitor }}
              </span>
            </button>
          </div>
        </div>

        <div class="arl-hero-right">
          <a-tooltip :title="autoRefreshEnabled ? taskText('tasks.autoRefreshIsOnRefreshSilentlyEvery9') : taskText('tasks.autoRefreshPaused')">
            <div class="auto-refresh-toggle">
              <a-switch
                v-model:checked="autoRefreshEnabled"
                size="small"
                @change="handleAutoRefreshToggle"
              />
              <span class="toggle-label">{{ taskText('tasks.autoRefresh') }}</span>
            </div>
          </a-tooltip>

          <a-button
            size="small"
            class="task-refresh-btn"
            :loading="loading"
            @click="fetchAllSchedules(false)"
          >
            <template #icon><reload-outlined /></template>
            {{ taskText('tasks.refresh') }}
          </a-button>

          <a-divider type="vertical" style="height: 18px; margin: 0 4px;" />

          <a-button type="primary" size="small" class="primary-action-btn" @click="openAddModal">
            <template #icon><plus-outlined /></template>
            {{ taskText('tasks.newScheduleTask') }}
          </a-button>
        </div>
      </div>

      <!-- 中层：调度运行态 4 维概览指标卡 (点击卡片可联动过滤) -->
      <div class="task-metric-cards-row">
        <div
          class="metric-stat-card"
          :class="{ active: !filterForm.status }"
          @click="toggleStatusFilter('')"
          :title="taskText('tasks.showAllTasks')"
        >
          <div class="stat-card-inner">
            <div class="stat-icon-box all">
              <appstore-outlined />
            </div>
            <div class="stat-info">
              <div class="stat-label">{{ taskText('tasks.allTasks') }}</div>
              <div class="stat-value">{{ metricCounts.total }}</div>
            </div>
          </div>
        </div>

        <div
          class="metric-stat-card"
          :class="{ active: filterForm.status === 'active' }"
          @click="toggleStatusFilter('active')"
          :title="taskText('tasks.activeScheduled')"
        >
          <div class="stat-card-inner">
            <div class="stat-icon-box running">
              <sync-outlined :spin="metricCounts.active > 0" />
            </div>
            <div class="stat-info">
              <div class="stat-label">
                <span>{{ taskText('tasks.activeScheduled') }}</span>
                <span v-if="metricCounts.active > 0" class="mini-pulse-beacon"></span>
              </div>
              <div class="stat-value running">{{ metricCounts.active }}</div>
            </div>
          </div>
        </div>

        <div
          class="metric-stat-card"
          :class="{ active: filterForm.status === 'done' }"
          @click="toggleStatusFilter('done')"
          :title="taskText('tasks.showCompletedTasks')"
        >
          <div class="stat-card-inner">
            <div class="stat-icon-box done">
              <check-circle-outlined />
            </div>
            <div class="stat-info">
              <div class="stat-label">{{ taskText('tasks.completed') }}</div>
              <div class="stat-value done">{{ metricCounts.done }}</div>
            </div>
          </div>
        </div>

        <div
          class="metric-stat-card"
          :class="{ active: filterForm.status === 'abnormal' }"
          @click="toggleStatusFilter('abnormal')"
          :title="taskText('tasks.showFailedAndStoppedTasks')"
        >
          <div class="stat-card-inner">
            <div class="stat-icon-box error">
              <close-circle-outlined />
            </div>
            <div class="stat-info">
              <div class="stat-label">{{ taskText('tasks.failedStopped') }}</div>
              <div class="stat-value error">{{ metricCounts.abnormal }}</div>
            </div>
          </div>
        </div>
      </div>

      <!-- 下层：常驻核心检索栏（前缀图标输入框 + 圆点状态下拉） -->
      <div class="task-filter-container">
        <div class="resident-filter-bar">
          <div class="filter-inputs-group">
            <a-input
              v-model:value="filterForm.name"
              :placeholder="taskText('tasks.taskName')"
              style="width: 195px;"
              size="small"
              allowClear
              @pressEnter="onFilterSearch"
            >
              <template #prefix><search-outlined class="input-prefix-icon" /></template>
            </a-input>

            <a-input
              v-model:value="filterForm.target"
              :placeholder="taskText('tasks.target')"
              style="width: 195px;"
              size="small"
              allowClear
              @pressEnter="onFilterSearch"
            >
              <template #prefix><global-outlined class="input-prefix-icon" /></template>
            </a-input>

            <a-input
              v-model:value="filterForm.context"
              :placeholder="taskText('tasks.enterPolicyOrScope')"
              style="width: 195px;"
              size="small"
              allowClear
              @pressEnter="onFilterSearch"
            >
              <template #prefix><cluster-outlined class="input-prefix-icon" /></template>
            </a-input>

            <a-select
              v-model:value="filterForm.sub_type"
              :placeholder="taskText('tasks.scheduleCategoryCol')"
              style="width: 175px;"
              size="small"
              allowClear
              @change="onFilterSearch"
            >
              <template v-if="activeCategory === 'all' || activeCategory === 'planning'">
                <a-select-option value="plan_recurrent">
                  <span class="status-option-item"><span class="status-dot plan"></span> {{ taskText('tasks.capsulePlanRecurrent') }}</span>
                </a-select-option>
                <a-select-option value="plan_future">
                  <span class="status-option-item"><span class="status-dot plan"></span> {{ taskText('tasks.capsulePlanFuture') }}</span>
                </a-select-option>
              </template>
              <template v-if="activeCategory === 'all' || activeCategory === 'monitor'">
                <a-select-option value="monitor_domain">
                  <span class="status-option-item"><span class="status-dot monitor"></span> {{ taskText('tasks.capsuleMonitorDomain') }}</span>
                </a-select-option>
                <a-select-option value="monitor_ip">
                  <span class="status-option-item"><span class="status-dot monitor"></span> {{ taskText('tasks.capsuleMonitorIp') }}</span>
                </a-select-option>
                <a-select-option value="monitor_site">
                  <span class="status-option-item"><span class="status-dot monitor"></span> {{ taskText('tasks.capsuleMonitorSite') }}</span>
                </a-select-option>
                <a-select-option value="monitor_wih">
                  <span class="status-option-item"><span class="status-dot monitor"></span> {{ taskText('tasks.capsuleMonitorWih') }}</span>
                </a-select-option>
              </template>
            </a-select>

            <a-select
              v-model:value="filterForm.status"
              :placeholder="taskText('tasks.status')"
              style="width: 160px;"
              size="small"
              allowClear
              @change="onFilterSearch"
            >
              <a-select-option value="">{{ taskText('tasks.allStatuses') }}</a-select-option>
              <a-select-option value="active">
                <span class="status-option-item"><span class="status-dot running"></span> {{ taskText('tasks.activeScheduled') }}</span>
              </a-select-option>
              <a-select-option value="running">
                <span class="status-option-item"><span class="status-dot running"></span> {{ taskText('tasks.statusRunning') }}</span>
              </a-select-option>
              <a-select-option value="scheduled">
                <span class="status-option-item"><span class="status-dot running"></span> {{ taskText('tasks.statusScheduled') }}</span>
              </a-select-option>
              <a-select-option value="done">
                <span class="status-option-item"><span class="status-dot done"></span> {{ taskText('tasks.statusDone') }}</span>
              </a-select-option>
              <a-select-option value="stop">
                <span class="status-option-item"><span class="status-dot stop"></span> {{ taskText('tasks.statusStop') }}</span>
              </a-select-option>
              <a-select-option value="error">
                <span class="status-option-item"><span class="status-dot error"></span> {{ taskText('tasks.statusError') }}</span>
              </a-select-option>
              <a-select-option value="abnormal">
                <span class="status-option-item"><span class="status-dot error"></span> {{ taskText('tasks.failedStopped') }}</span>
              </a-select-option>
            </a-select>
          </div>

          <div class="filter-actions-group">
            <a-button size="small" @click="onFilterSearch">
              <template #icon><search-outlined /></template>
              {{ taskText('tasks.search') }}
            </a-button>
            <a-button size="small" @click="resetFilterSearch">
              {{ taskText('tasks.reset') }}
            </a-button>
          </div>
        </div>
      </div>
    </div>

    <!-- 2. 动态浮动批量操作条（有勾选行时激活，对齐 /taskList） -->
    <div v-if="hasSelected" class="floating-batch-action-bar">
      <div class="batch-left">
        <span class="selected-count-badge">
          {{ taskText('tasks.selected') }} <b>{{ selectedRowKeys.length }}</b> {{ taskText('tasks.tasks') }}
        </span>
      </div>

      <div class="batch-right">
        <a-button size="small" @click="handleBatchAction('run')">
          <template #icon><send-outlined /></template>
          {{ taskText('tasks.runSelected') }}
        </a-button>
        <a-button size="small" @click="handleBatchAction('recover')">
          <template #icon><play-circle-outlined /></template>
          {{ taskText('tasks.resumeSelected') }}
        </a-button>
        <a-button size="small" @click="handleBatchAction('stop')">
          <template #icon><pause-circle-outlined /></template>
          {{ taskText('tasks.stopSelected') }}
        </a-button>
        <a-button danger size="small" @click="handleBatchAction('delete')">
          <template #icon><delete-outlined /></template>
          {{ taskText('tasks.deleteSelected') }}
        </a-button>
        <a-button size="small" type="link" @click="clearSelection">
          {{ taskText('tasks.clearSelection') }}
        </a-button>
      </div>
    </div>

    <!-- 3. 主数据表格容器 -->
    <div class="arl-table-card">
      <a-table
        :sticky="stickyConfig"
        :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange, preserveSelectedRowKeys: true }"
        :loading="loading"
        :dataSource="pagedRows"
        :columns="unifiedColumns"
        :pagination="false"
        size="small"
        :rowKey="(record) => record.uid"
      >
        <template #emptyText>
          <ArlEmpty :description="taskText('tasks.noData')" />
        </template>

        <template #bodyCell="{ column, record }">
          <!-- 复合语义胶囊标签列 -->
          <template v-if="column.key === 'capsule_type'">
            <div class="arl-capsule-cell">
              <span
                class="arl-schedule-capsule"
                :class="record.source === 'planning' ? 'is-plan' : 'is-monitor'"
              >
                <clock-circle-outlined v-if="record.source === 'planning'" />
                <radar-chart-outlined v-else />
                <span>{{ getCapsuleLabel(record) }}</span>
              </span>
              <span
                v-if="record.source === 'planning' && record.task_tag"
                class="arl-sub-tag-pill"
                :class="record.task_tag === 'risk_cruising' ? 'is-risk' : 'is-discovery'"
              >
                {{ record.task_tag === 'risk_cruising' ? taskText('tasks.riskScanningTask') : taskText('tasks.assetDiscoveryTasks') }}
              </span>
            </div>
          </template>

          <!-- 目标列 -->
          <template v-else-if="column.key === 'target_display'">
            <span class="arl-target-cell" :title="record.targetDisplay">{{ record.targetDisplay || '-' }}</span>
          </template>

          <!-- 统一状态列 -->
          <template v-else-if="column.key === 'status'">
            <a-tag
              :color="
                record.status === 'scheduled' ? 'blue' :
                record.status === 'running' ? 'processing' :
                record.status === 'stop' ? 'warning' :
                record.status === 'error' ? 'error' :
                'success'
              "
            >
              {{ record.status === 'scheduled' ? taskText('tasks.statusScheduled') : formatTaskStatus(record.status) }}
            </a-tag>
          </template>

          <!-- 合并列：关联策略 / 资产组 -->
          <template v-else-if="column.key === 'context_binding'">
            <div v-if="record.source === 'planning'" class="arl-context-cell">
              <span class="arl-context-pill is-policy">{{ taskText('tasks.badgePolicyPrefix') }}</span>
              <span class="arl-context-text" :title="record.policy_name">{{ record.policy_name || '-' }}</span>
            </div>
            <div v-else class="arl-context-cell">
              <span class="arl-context-pill is-scope">{{ taskText('tasks.badgeScopePrefix') }}</span>
              <a
                v-if="record.scope_id"
                class="arl-context-link"
                :title="`${record.scopeNameDisplay} (${record.scope_id})`"
                @click="goToAssetScope(record.scope_id)"
              >
                {{ record.scopeNameDisplay }}
              </a>
              <span v-else>-</span>
            </div>
          </template>

          <!-- 调度规则列 -->
          <template v-else-if="column.key === 'schedule_rule'">
            <div v-if="record.source === 'planning'" class="arl-rule-cell">
              <span class="arl-rule-badge">
                {{ record.schedule_type === 'future_scan' ? taskText('tasks.ruleFixedTimePrefix') : 'Cron' }}
              </span>
              <span class="arl-mono-rule">
                {{ record.schedule_type === 'future_scan' ? record.start_date : record.cron }}
              </span>
            </div>
            <div v-else class="arl-rule-cell">
              <span class="arl-rule-badge">{{ taskText('tasks.ruleIntervalPrefix') }}</span>
              <span>{{ formatInterval(record.interval) }}</span>
            </div>
          </template>

          <!-- 对称操作列 -->
          <template v-else-if="column.key === 'action'">
            <div class="arl-row-actions">
              <a-button
                size="small"
                @click="handleSingleAction('run', record)"
              >
                {{ taskText('tasks.runTaskNow') }}
              </a-button>

              <a-button
                size="small"
                :disabled="record.status === 'stop' || record.status === 'done'"
                @click="handleSingleAction('stop', record)"
              >
                {{ taskText('tasks.stop') }}
              </a-button>

              <a-button
                size="small"
                :disabled="record.status === 'scheduled' || record.status === 'running'"
                @click="handleSingleAction('recover', record)"
              >
                {{ taskText('tasks.resume') }}
              </a-button>

              <a-button
                size="small"
                danger
                @click="handleSingleAction('delete', record)"
              >
                {{ taskText('tasks.delete') }}
              </a-button>
            </div>
          </template>
        </template>
      </a-table>

      <div class="arl-pagination-bar">
        <div class="pagination-info">
          {{ taskText('tasks.paginationSummary', { pages: Math.ceil(filteredRows.length / pagination.pageSize) || 1, total: filteredRows.length }) }}
        </div>
        <a-pagination
          :pageSizeOptions="$pageSizeOptions"
          v-model:current="pagination.current"
          v-model:pageSize="pagination.pageSize"
          :total="filteredRows.length"
          show-size-changer
          size="small"
          @change="handleTablePageChange"
          @showSizeChange="handleTablePageChange"
        />
      </div>
    </div>

    <!-- 统一新建调度任务弹窗（内置胶囊切换：扫描计划任务 / 资产持续监控） -->
    <a-modal
      v-model:open="addModalVisible"
      :title="taskText('tasks.newScheduleTask')"
      @ok="submitAdd"
      :confirmLoading="addLoading"
      width="560px"
      :okText="taskText('tasks.confirm')"
      :cancelText="taskText('tasks.cancel')"
      destroyOnClose
    >
      <div class="arl-modal-capsule-bar">
        <div class="arl-capsule-switcher">
          <button
            type="button"
            class="arl-capsule-item"
            :class="{ 'is-active': addMode === 'planning' }"
            @click="switchAddMode('planning')"
          >
            <clock-circle-outlined />
            <span>{{ taskText('tasks.scheduledScans') }}</span>
          </button>
          <button
            type="button"
            class="arl-capsule-item"
            :class="{ 'is-active': addMode === 'monitor' }"
            @click="switchAddMode('monitor')"
          >
            <radar-chart-outlined />
            <span>{{ taskText('tasks.continuousAssetMonitoring') }}</span>
          </button>
        </div>
      </div>

      <!-- 模式 A：新建扫描计划任务 -->
      <a-form
        v-if="addMode === 'planning'"
        :label-wrap="true"
        ref="addPlanFormRef"
        :model="addForm"
        :rules="addPlanRules"
        :label-col="{ span: taskLocale !== 'zh-CN' ? 7 : 5 }"
        :wrapper-col="{ span: taskLocale !== 'zh-CN' ? 16 : 18 }"
      >
        <a-form-item :label="taskText('tasks.name')" name="name">
          <a-input v-model:value="addForm.name" :placeholder="taskText('tasks.enterAName')" />
        </a-form-item>

        <a-form-item
          :label="taskText('tasks.target')"
          name="target"
          :extra="taskText('tasks.enterDomainsIpsOrCidrRangesSeparatedBy')"
        >
          <a-textarea v-model:value="addForm.target" :rows="3" :placeholder="taskText('tasks.enterTargets')" />
        </a-form-item>

        <a-form-item :label="taskText('tasks.scheduleType')" name="schedule_type">
          <a-select v-model:value="addForm.schedule_type" @change="onScheduleTypeChange">
            <a-select-option value="future_scan">{{ taskText('tasks.oneTimeTask') }}</a-select-option>
            <a-select-option value="recurrent_scan">{{ taskText('tasks.recurringTask') }}</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item :label="taskText('tasks.policy')" name="policy_id">
          <a-select
            v-model:value="addForm.policy_id"
            :placeholder="taskText('tasks.selectAPolicy')"
            show-search
            option-filter-prop="label"
          >
            <a-select-option
              v-for="p in policyList"
              :key="p._id"
              :value="p._id"
              :label="p.name"
            >
              {{ p.name }} (PoC : {{ p.policy?.poc_config?.length || 0 }})
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item
          v-if="addForm.schedule_type === 'future_scan'"
          :label="taskText('tasks.startTime')"
          name="start_date"
        >
          <a-date-picker
            v-model:value="addForm.start_date"
            show-time
            :disabled-date="disablePastDate"
            valueFormat="YYYY-MM-DD HH:mm:ss"
            style="width: 100%"
            :placeholder="taskText('tasks.selectAStartDate')"
          />
        </a-form-item>

        <a-form-item
          v-if="addForm.schedule_type === 'recurrent_scan'"
          label="Cron"
          name="cron"
          :extra="taskText('tasks.standardFiveFieldCronMinuteHourDayMonth')"
        >
          <a-input v-model:value="addForm.cron" :placeholder="taskText('tasks.enterCronEG001')" />
        </a-form-item>

        <a-form-item
          :label="taskText('tasks.taskCategory')"
          name="task_tag"
          :extra="taskText('tasks.assetDiscoveryParsesDomainAndIpTargetsTo')"
        >
          <a-select v-model:value="addForm.task_tag" :placeholder="taskText('tasks.selectATaskCategory')">
            <a-select-option value="task">{{ taskText('tasks.assetDiscoveryTasks') }}</a-select-option>
            <a-select-option value="risk_cruising">{{ taskText('tasks.riskScanningTask') }}</a-select-option>
          </a-select>
        </a-form-item>
      </a-form>

      <!-- 模式 B：新建资产持续监控 -->
      <a-form
        v-else
        :label-wrap="true"
        ref="addMonitorFormRef"
        :model="addMonitorForm"
        :rules="addMonitorRules"
        :label-col="{ span: taskLocale !== 'zh-CN' ? 7 : 5 }"
        :wrapper-col="{ span: taskLocale !== 'zh-CN' ? 16 : 18 }"
      >
        <a-form-item :label="taskText('tasks.assetGroupLabel')" name="scope_id">
          <a-select
            v-model:value="addMonitorForm.scope_id"
            :placeholder="taskText('tasks.selectAnAssetGroup')"
            show-search
            option-filter-prop="label"
            @change="onMonitorScopeChange"
          >
            <a-select-option
              v-for="s in scopeList"
              :key="s._id"
              :value="s._id"
              :label="`${s.name} (${s._id})`"
            >
              {{ s.name }} ({{ (s.scope_array || []).length }})
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item :label="taskText('tasks.monitorDimensionLabel')" name="monitor_type">
          <a-select v-model:value="addMonitorForm.monitor_type" @change="onMonitorDimensionChange">
            <a-select-option value="target">{{ taskText('tasks.monitorDimensionTarget') }}</a-select-option>
            <a-select-option value="site_monitor">{{ taskText('tasks.monitorDimensionSite') }}</a-select-option>
            <a-select-option value="wih_monitor">{{ taskText('tasks.monitorDimensionWih') }}</a-select-option>
          </a-select>
        </a-form-item>

        <template v-if="addMonitorForm.monitor_type === 'target'">
          <a-form-item :label="taskText('tasks.monitorTargetsLabel')" name="domains">
            <a-select
              v-model:value="addMonitorForm.domains"
              mode="multiple"
              :placeholder="taskText('tasks.selectMonitorTargets')"
              :disabled="!addMonitorForm.scope_id"
              :max-tag-count="6"
              allowClear
            >
              <a-select-option v-for="d in currentScopeTargets" :key="d" :value="d">
                {{ d }}
              </a-select-option>
            </a-select>
            <div v-if="currentScopeTargets.length > 0" class="arl-scope-target-quick-bar">
              <a-button type="link" size="small" @click="selectAllMonitorTargets">
                {{ taskText('tasks.selectAllScopeTargets', { count: currentScopeTargets.length }) }}
              </a-button>
              <a-button type="link" size="small" @click="addMonitorForm.domains = []">
                {{ taskText('tasks.clearSelectedTargets') }}
              </a-button>
            </div>
          </a-form-item>

          <a-form-item :label="taskText('tasks.policy')" name="policy_id">
            <a-select
              v-model:value="addMonitorForm.policy_id"
              :placeholder="taskText('tasks.optionalPolicyPlaceholder')"
              allowClear
              show-search
              option-filter-prop="label"
            >
              <a-select-option
                v-for="p in policyList"
                :key="p._id"
                :value="p._id"
                :label="p.name"
              >
                {{ p.name }} (PoC : {{ p.policy?.poc_config?.length || 0 }})
              </a-select-option>
            </a-select>
          </a-form-item>
        </template>

        <a-form-item :label="taskText('tasks.name')" name="name">
          <a-input
            v-model:value="addMonitorForm.name"
            :placeholder="taskText('tasks.optionalMonitorNamePlaceholder')"
          />
        </a-form-item>

        <a-form-item
          :label="taskText('tasks.runIntervalHoursLabel')"
          name="interval_hours"
          :extra="taskText('tasks.runIntervalMin6HoursExtra')"
        >
          <a-input-number
            v-model:value="addMonitorForm.interval_hours"
            :min="6"
            :max="8760"
            style="width: 100%;"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';
import { formatTaskStatus } from '../constants/taskStatus';

defineOptions({ name: 'PlanningTasks' });

import { ref, reactive, onMounted, onActivated, onDeactivated, onUnmounted, computed, watch, createVNode } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useSticky } from '../utils/useSticky';
import request from '../utils/request';
import {
  assetMutationVersion,
  notifyAssetMutated,
  createSelectionLabelTracker,
  buildSelectionConfirmContent
} from '../utils/useTabStateCache';
import { message, Modal } from 'ant-design-vue';
import {
  SearchOutlined,
  ExclamationCircleOutlined,
  PlusOutlined,
  DeleteOutlined,
  PauseCircleOutlined,
  PlayCircleOutlined,
  SendOutlined,
  ReloadOutlined,
  ClockCircleOutlined,
  RadarChartOutlined,
  AppstoreOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  GlobalOutlined,
  ClusterOutlined
} from '@ant-design/icons-vue';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import dayjs from 'dayjs';

const { t: taskText, locale: taskLocale } = useI18n({ useScope: 'global' });

const route = useRoute();
const router = useRouter();

const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

// 兼容 /assetsMonitor 重定向 (?tab=monitor) 与 ?tab=planning，无参时默认展示 'all'（全部调度合表）
const resolveCategoryFromQuery = (tabVal) => {
  if (tabVal === 'monitor' || tabVal === 'planning') return tabVal;
  return 'all';
};

const activeCategory = ref(resolveCategoryFromQuery(route.query.tab));

const onCategoryChange = (cat) => {
  if (activeCategory.value !== cat) {
    clearSelection();
  }
  activeCategory.value = cat;
  pagination.current = 1;
  if (cat === 'planning' && filterForm.sub_type && !String(filterForm.sub_type).startsWith('plan_')) {
    filterForm.sub_type = undefined;
  } else if (cat === 'monitor' && filterForm.sub_type && !String(filterForm.sub_type).startsWith('monitor_')) {
    filterForm.sub_type = undefined;
  }
  const nextQuery = { ...route.query };
  if (cat === 'all') {
    delete nextQuery.tab;
  } else {
    nextQuery.tab = cat;
  }
  router.replace({ query: nextQuery });
};

watch(() => route.query.tab, (newTab) => {
  const targetCat = resolveCategoryFromQuery(newTab);
  if (activeCategory.value !== targetCat) {
    clearSelection();
    activeCategory.value = targetCat;
    pagination.current = 1;
  }
});

// ================= 全局分页共享 =================
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value });

watch(() => pagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});
watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
});

// ================= 数据源与归一化 =================
const loading = ref(false);
const rawPlanItems = ref([]);
const rawMonitorItems = ref([]);
const policyList = ref([]);
const scopeList = ref([]);

const scopeNameMap = computed(() => {
  const map = {};
  for (const s of scopeList.value) {
    if (s && s._id) {
      map[String(s._id)] = s.name || '';
    }
  }
  return map;
});

const getSubTypeKey = (source, item) => {
  if (source === 'planning') {
    return item.schedule_type === 'future_scan' ? 'plan_future' : 'plan_recurrent';
  }
  const st = item.scope_type;
  if (st === 'site_update_monitor') return 'monitor_site';
  if (st === 'wih_update_monitor') return 'monitor_wih';
  if (st === 'ip') return 'monitor_ip';
  return 'monitor_domain';
};

const getCapsuleLabel = (record) => {
  const map = {
    plan_recurrent: taskText('tasks.capsulePlanRecurrent'),
    plan_future: taskText('tasks.capsulePlanFuture'),
    monitor_domain: taskText('tasks.capsuleMonitorDomain'),
    monitor_ip: taskText('tasks.capsuleMonitorIp'),
    monitor_site: taskText('tasks.capsuleMonitorSite'),
    monitor_wih: taskText('tasks.capsuleMonitorWih')
  };
  return map[record.subType] || taskText('tasks.capsuleMonitorDomain');
};

const normalizedRows = computed(() => {
  const planRows = (rawPlanItems.value || []).map((item) => ({
    ...item,
    uid: `planning:${item._id}`,
    source: 'planning',
    subType: getSubTypeKey('planning', item),
    targetDisplay: item.target || '-',
    status: item.status || 'scheduled',
    scopeNameDisplay: '',
    run_number: item.run_number ?? 0,
    last_run_date: item.last_run_date || '-',
    next_run_date: item.next_run_date || '-'
  }));

  const monitorRows = (rawMonitorItems.value || []).map((item) => {
    const sid = String(item.scope_id || '');
    const resolvedScopeName = item.scope_name || scopeNameMap.value[sid] || sid || '-';
    return {
      ...item,
      uid: `monitor:${item._id}`,
      source: 'monitor',
      subType: getSubTypeKey('monitor', item),
      targetDisplay: item.domain || '-',
      status: item.status || 'running',
      scopeNameDisplay: resolvedScopeName,
      run_number: item.run_number ?? 0,
      last_run_date: item.last_run_date || '-',
      next_run_date: item.next_run_date || '-'
    };
  });

  return [...planRows, ...monitorRows];
});

const isRowActive = (row) => row.status === 'running' || row.status === 'scheduled';
const isRowAbnormal = (row) => row.status === 'stop' || row.status === 'error';

const categoryCounts = computed(() => ({
  all: normalizedRows.value.length,
  planning: rawPlanItems.value.length,
  monitor: rawMonitorItems.value.length
}));

const categoryActiveCounts = computed(() => {
  let planActive = 0;
  let monActive = 0;
  for (const r of normalizedRows.value) {
    if (isRowActive(r)) {
      if (r.source === 'planning') planActive++;
      else monActive++;
    }
  }
  return {
    all: planActive + monActive,
    planning: planActive,
    monitor: monActive
  };
});

// 当前大类下的全集（用于驱动中层 4 维状态概览卡片计数，保证卡片计数与点击筛选结果严格一致）
const currentCategoryRows = computed(() => {
  if (activeCategory.value === 'all') return normalizedRows.value;
  return normalizedRows.value.filter((r) => r.source === activeCategory.value);
});

const metricCounts = computed(() => {
  let active = 0;
  let done = 0;
  let abnormal = 0;
  for (const r of currentCategoryRows.value) {
    if (isRowActive(r)) active++;
    else if (r.status === 'done') done++;
    else if (isRowAbnormal(r)) abnormal++;
  }
  return {
    total: currentCategoryRows.value.length,
    active,
    done,
    abnormal
  };
});

// ================= 检索过滤与状态卡片联动 =================
const filterForm = reactive({
  name: '',
  target: '',
  context: '',
  sub_type: undefined,
  status: ''
});

const toggleStatusFilter = (targetStatus) => {
  if (targetStatus === '') {
    filterForm.status = '';
  } else {
    filterForm.status = filterForm.status === targetStatus ? '' : targetStatus;
  }
  pagination.current = 1;
};

const matchesStatusFilter = (row, statusFilter) => {
  if (!statusFilter) return true;
  if (statusFilter === 'active') return isRowActive(row);
  if (statusFilter === 'abnormal') return isRowAbnormal(row);
  return row.status === statusFilter;
};

const filteredRows = computed(() => {
  const nameKw = String(filterForm.name || '').trim().toLowerCase();
  const targetKw = String(filterForm.target || '').trim().toLowerCase();
  const contextKw = String(filterForm.context || '').trim().toLowerCase();
  const subTypeFilter = filterForm.sub_type;
  const statusFilter = filterForm.status;

  return currentCategoryRows.value.filter((row) => {
    if (nameKw && !String(row.name || '').toLowerCase().includes(nameKw)) {
      return false;
    }
    if (targetKw && !String(row.targetDisplay || '').toLowerCase().includes(targetKw)) {
      return false;
    }
    if (contextKw) {
      const policyMatch = row.source === 'planning' && String(row.policy_name || '').toLowerCase().includes(contextKw);
      const scopeMatch =
        row.source === 'monitor' &&
        (String(row.scope_id || '').toLowerCase().includes(contextKw) ||
          String(row.scopeNameDisplay || '').toLowerCase().includes(contextKw));
      if (!policyMatch && !scopeMatch) {
        return false;
      }
    }
    if (subTypeFilter && row.subType !== subTypeFilter) {
      return false;
    }
    if (!matchesStatusFilter(row, statusFilter)) {
      return false;
    }
    return true;
  });
});

const pagedRows = computed(() => {
  const start = (pagination.current - 1) * pagination.pageSize;
  return filteredRows.value.slice(start, start + pagination.pageSize);
});

const onFilterSearch = () => {
  pagination.current = 1;
};

const resetFilterSearch = () => {
  Object.assign(filterForm, {
    name: '',
    target: '',
    context: '',
    sub_type: undefined,
    status: ''
  });
  pagination.current = 1;
};

const handleTablePageChange = (page, pageSize) => {
  pagination.current = page;
  pagination.pageSize = pageSize;
};

// ================= 自适应静默自动刷新 =================
const autoRefreshEnabled = ref(true);
let pollTimer = null;

const startSmartPolling = () => {
  stopSmartPolling();
  if (!autoRefreshEnabled.value) return;
  pollTimer = setInterval(() => {
    if (autoRefreshEnabled.value && categoryActiveCounts.value.all > 0 && !loading.value) {
      fetchAllSchedules(true);
    }
  }, 9000);
};

const stopSmartPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer);
    pollTimer = null;
  }
};

const handleAutoRefreshToggle = (checked) => {
  if (checked) {
    message.success(taskText('tasks.autoRefreshEnabledRefreshSilentlyWhileTasksAre'));
    startSmartPolling();
  } else {
    message.info(taskText('tasks.autoRefreshPaused'));
    stopSmartPolling();
  }
};

// ================= 跨页/跨类型选择追踪 =================
const selectedRowKeys = ref([]);
const selectionTracker = createSelectionLabelTracker();
const hasSelected = computed(() => selectedRowKeys.value.length > 0);
let lastObservedMutationVersion = assetMutationVersion.value;

const getRowKey = (row) => row?.uid;
const getRowLabel = (row) => {
  if (!row) return '';
  const capsule = getCapsuleLabel(row);
  const name = row.name || row._id || '';
  const target = row.targetDisplay && row.targetDisplay !== name ? ` (${row.targetDisplay})` : '';
  return `[${capsule}] ${name}${target}`;
};

const onSelectChange = (keys, selectedRows) => {
  selectedRowKeys.value = keys;
  selectionTracker.syncSelection(keys, selectedRows, normalizedRows.value, getRowKey, getRowLabel);
};

const clearSelection = () => {
  selectedRowKeys.value = [];
  selectionTracker.clear();
};

// ================= 统一表格列定义 =================
const unifiedColumns = [
  { get title() { return taskText('tasks.taskName'); }, dataIndex: 'name', key: 'name', width: 180 },
  { get title() { return taskText('tasks.scheduleCategoryCol'); }, key: 'capsule_type', width: 210 },
  { get title() { return taskText('tasks.target'); }, key: 'target_display', width: 170 },
  { get title() { return taskText('tasks.status'); }, dataIndex: 'status', key: 'status', width: 105 },
  { get title() { return taskText('tasks.contextBindingCol'); }, key: 'context_binding', width: 180 },
  { get title() { return taskText('tasks.scheduleRuleCol'); }, key: 'schedule_rule', width: 165 },
  { get title() { return taskText('tasks.lastRun'); }, dataIndex: 'last_run_date', key: 'last_run_date', width: 165 },
  { get title() { return taskText('tasks.nextRun'); }, dataIndex: 'next_run_date', key: 'next_run_date', width: 165 },
  { get title() { return taskText('tasks.runCount'); }, dataIndex: 'run_number', key: 'run_number', width: 95, align: 'center' },
  { get title() { return taskText('tasks.actions'); }, key: 'action', width: 250 }
];

const goToAssetScope = (id) => {
  if (!id) return;
  router.push({
    path: '/group',
    query: { scope_id: id }
  });
};

const formatInterval = (seconds) => {
  if (!seconds) return '-';
  if (seconds >= 3600 && seconds % 3600 === 0) return taskText('tasks.countHours', { count: seconds / 3600 });
  if (seconds >= 60 && seconds % 60 === 0) return taskText('tasks.countMinutes', { count: seconds / 60 });
  return taskText('tasks.countSeconds', { count: seconds });
};

// ================= 数据加载 =================
const fetchAllSchedules = async (silent = false) => {
  if (!silent) loading.value = true;
  try {
    const [planRes, monitorRes] = await Promise.all([
      request.get('/task_schedule/', { params: { page: 1, size: 1000 } }),
      request.get('/scheduler/', { params: { page: 1, size: 1000 } })
    ]);

    if (planRes.code === 200) {
      rawPlanItems.value = planRes.items || [];
    }
    if (monitorRes.code === 200) {
      rawMonitorItems.value = monitorRes.items || [];
    }

    selectionTracker.rememberRows(normalizedRows.value, getRowKey, getRowLabel);

    const validKeySet = new Set(normalizedRows.value.map((r) => r.uid));
    if (selectedRowKeys.value.some((k) => !validKeySet.has(k))) {
      selectedRowKeys.value = selectedRowKeys.value.filter((k) => validKeySet.has(k));
    }

    const maxPage = Math.max(1, Math.ceil(filteredRows.value.length / (pagination.pageSize || 10)));
    if (pagination.current > maxPage) {
      pagination.current = maxPage;
    }
  } catch (error) {
    if (!silent) {
      message.error(taskText('tasks.failedToLoadScheduledTasks'));
    }
  } finally {
    if (!silent) loading.value = false;
  }
};

const fetchPolicyList = async () => {
  try {
    const res = await request.get('/policy/', { params: { size: 1000, order: '-update_date' } });
    if (res.code === 200) policyList.value = res.items || [];
  } catch (e) {
    // 忽略策略列表预加载异常
  }
};

const fetchScopeList = async () => {
  try {
    const res = await request.get('/asset_scope/', { params: { size: 1000 } });
    if (res.code === 200) scopeList.value = res.items || [];
  } catch (e) {
    // 忽略资产组预加载异常
  }
};

// ================= 单行与批量操作分发 =================
const isRowEligibleForAction = (action, row) => {
  if (!row) return false;
  if (action === 'run' || action === 'delete') return true;
  if (action === 'stop') {
    return row.status === 'running' || row.status === 'scheduled';
  }
  if (action === 'recover') {
    if (row.source === 'monitor') return row.status === 'stop';
    return row.status === 'stop' || row.status === 'done';
  }
  return true;
};

const executeDispatchedActions = async (actionType, targetUids) => {
  const planIds = [];
  const monitorIds = [];
  const planUids = [];
  const monitorUids = [];

  for (const uid of targetUids) {
    if (String(uid).startsWith('planning:')) {
      planIds.push(String(uid).slice('planning:'.length));
      planUids.push(uid);
    } else if (String(uid).startsWith('monitor:')) {
      monitorIds.push(String(uid).slice('monitor:'.length));
      monitorUids.push(uid);
    }
  }

  const dispatches = [];

  if (planIds.length > 0) {
    const planActionUrlMap = {
      run: '/task_schedule/run/',
      stop: '/task_schedule/stop/',
      recover: '/task_schedule/recover/',
      delete: '/task_schedule/delete/'
    };
    const url = planActionUrlMap[actionType];
    if (url) {
      dispatches.push({
        source: 'planning',
        uids: planUids,
        promise: request.post(url, { _id: planIds })
      });
    }
  }

  if (monitorIds.length > 0) {
    const monitorActionUrlMap = {
      run: monitorIds.length === 1 ? '/scheduler/run/' : '/scheduler/run/batch',
      stop: monitorIds.length === 1 ? '/scheduler/stop/' : '/scheduler/stop/batch',
      recover: monitorIds.length === 1 ? '/scheduler/recover/' : '/scheduler/recover/batch',
      delete: '/scheduler/delete/'
    };
    const url = monitorActionUrlMap[actionType];
    if (url) {
      const payload =
        actionType === 'delete' || monitorIds.length > 1
          ? { scheduler_id: monitorIds }
          : { scheduler_id: monitorIds[0] };
      dispatches.push({
        source: 'monitor',
        uids: monitorUids,
        promise: request.post(url, payload)
      });
    }
  }

  if (dispatches.length === 0) return false;

  const settled = await Promise.allSettled(dispatches.map((d) => d.promise));
  const errorMessages = [];
  const succeededUids = [];
  let monitorSucceeded = false;

  settled.forEach((entry, idx) => {
    const meta = dispatches[idx];
    if (entry.status === 'fulfilled' && entry.value?.code === 200) {
      succeededUids.push(...meta.uids);
      if (meta.source === 'monitor') {
        monitorSucceeded = true;
      }
    } else if (entry.status === 'fulfilled') {
      errorMessages.push(entry.value?.message || taskText('tasks.operationFailedLabel'));
    } else {
      errorMessages.push(taskText('tasks.requestFailed'));
    }
  });

  if (errorMessages.length > 0) {
    message.error([...new Set(errorMessages)].join('；'));
  } else {
    message.success(taskText('tasks.operationCompleted'));
  }

  if (monitorSucceeded) {
    notifyAssetMutated();
    lastObservedMutationVersion = assetMutationVersion.value;
  }

  if (actionType === 'delete' && succeededUids.length > 0) {
    const deletedSet = new Set(succeededUids);
    selectedRowKeys.value = selectedRowKeys.value.filter((k) => !deletedSet.has(k));
    if (selectedRowKeys.value.length === 0) {
      selectionTracker.clear();
    }
  }

  if (succeededUids.length > 0) {
    await fetchAllSchedules();
  }
  return errorMessages.length === 0;
};

const handleSingleAction = (actionType, record) => {
  const isMonitor = record.source === 'monitor';
  const uid = record.uid;

  if (actionType === 'recover') {
    executeDispatchedActions('recover', [uid]);
    return;
  }

  const isDelete = actionType === 'delete';
  const isStop = actionType === 'stop';

  let title = '';
  let content = '';

  if (isMonitor) {
    title = isDelete
      ? taskText('tasks.deleteMonitoringTask')
      : isStop
        ? taskText('tasks.pauseMonitoringTaskTitle')
        : taskText('tasks.runMonitoringTask');
    content = isDelete
      ? taskText('tasks.deleteMonitoringTaskStopsRunningDesc', { name: record.name })
      : isStop
        ? taskText('tasks.pauseMonitoringTaskConfirmDesc', { name: record.name })
        : taskText('tasks.runMonitoringTaskNameNowItWillBe', { name: record.name });
  } else {
    title = isDelete
      ? taskText('tasks.deleteSelectedScheduledTasksCount', { count: 1 })
      : isStop
        ? taskText('tasks.stopTheSelectedScheduledTasks')
        : taskText('tasks.runScheduledTaskNowTitle');
    content = isDelete
      ? taskText('tasks.theseScheduledTasksAndTheirSchedulingConfigurationWill', { names: `· ${record.name}`, more: '' })
      : isStop
        ? `${record.name}`
        : taskText('tasks.runScheduledTaskNowConfirmDesc', { name: record.name });
  }

  Modal.confirm({
    title,
    icon: createVNode(
      ExclamationCircleOutlined,
      isDelete ? { style: 'color: #ff4d4f;' } : isStop ? { style: 'color: #faad14;' } : undefined
    ),
    content,
    okText: isDelete ? taskText('tasks.confirmDeletion') : taskText('tasks.confirm'),
    okButtonProps: isDelete || isStop ? { danger: true } : undefined,
    cancelText: taskText('tasks.cancel'),
    onOk: () => executeDispatchedActions(actionType, [uid])
  });
};

const handleBatchAction = (action) => {
  const actionMetaMap = {
    delete:  { title: taskText('tasks.deleteSelected'), text: taskText('tasks.delete'), type: 'danger' },
    stop:    { title: taskText('tasks.stopSelected'), text: taskText('tasks.stop'), type: 'danger' },
    recover: { title: taskText('tasks.resumeSelected'), text: taskText('tasks.resume'), type: 'primary' },
    run:     { title: taskText('tasks.runSelected'), text: taskText('tasks.run'), type: 'primary' }
  };

  const current = actionMetaMap[action];
  if (!current) return;

  const selectedUids = selectedRowKeys.value.filter((k) => k != null && k !== '');
  if (!selectedUids.length) return;

  const rowMap = new Map(normalizedRows.value.map((r) => [r.uid, r]));
  const eligibleUids = selectedUids.filter((uid) => {
    const row = rowMap.get(uid);
    return row ? isRowEligibleForAction(action, row) : (action === 'run' || action === 'delete');
  });
  const skippedCount = selectedUids.length - eligibleUids.length;

  if (!eligibleUids.length) {
    message.warning(taskText('tasks.noEligibleSchedulesForAction', { count: selectedUids.length, action: current.text }));
    return;
  }

  const selectedLabels = selectionTracker.getLabels(eligibleUids);
  const includesMonitor = eligibleUids.some((k) => String(k).startsWith('monitor:'));
  const isDestructive = action === 'delete' || action === 'stop';
  const baseSummary = taskText('tasks.applyActionToTheSelectedTasksCount', { count: eligibleUids.length, action: current.text });
  const summaryText = skippedCount > 0
    ? `${baseSummary}${taskText('tasks.batchActionSkippedNotice', { skipped: skippedCount })}`
    : baseSummary;

  Modal.confirm({
    title: taskText('tasks.confirmAction', { action: current.title }),
    icon: createVNode(ExclamationCircleOutlined),
    width: 560,
    content: buildSelectionConfirmContent({
      alertType: isDestructive && includesMonitor ? 'warning' : '',
      alertMessage: isDestructive && includesMonitor ? current.title : '',
      alertDescription: isDestructive && includesMonitor ? taskText('tasks.monitorBatchStopDeleteWarning') : '',
      summary: summaryText,
      listHeading: taskText('tasks.selectedSchedulesListHeading'),
      items: selectedLabels,
      expandText: (total) => taskText('assets.expandAllCount', { count: total }),
      collapseText: taskText('assets.collapseList')
    }),
    okText: taskText('tasks.confirm'),
    okType: current.type,
    cancelText: taskText('tasks.cancel'),
    onOk: async () => {
      await executeDispatchedActions(action, eligibleUids);
    }
  });
};

// ================= 统一新建调度任务弹窗 =================
const addModalVisible = ref(false);
const addLoading = ref(false);
const addMode = ref('planning');
const addPlanFormRef = ref();
const addMonitorFormRef = ref();

const addForm = reactive({
  name: '',
  target: '',
  schedule_type: 'future_scan',
  policy_id: undefined,
  task_tag: undefined,
  start_date: '',
  cron: ''
});

const addMonitorForm = reactive({
  scope_id: undefined,
  monitor_type: 'target',
  domains: [],
  policy_id: undefined,
  name: '',
  interval_hours: 24
});

const currentScopeObj = computed(() =>
  scopeList.value.find((s) => s._id === addMonitorForm.scope_id) || null
);

const currentScopeTargets = computed(() =>
  currentScopeObj.value?.scope_array || []
);

const onMonitorScopeChange = () => {
  if (currentScopeTargets.value.length > 0) {
    addMonitorForm.domains = [...currentScopeTargets.value];
  } else {
    addMonitorForm.domains = [];
  }
};

const onMonitorDimensionChange = () => {
  addMonitorFormRef.value?.clearValidate(['domains']);
};

const selectAllMonitorTargets = () => {
  addMonitorForm.domains = [...currentScopeTargets.value];
};

// 5 段 Cron 最小校验
const CRON_SEGMENT_RE = /^(\*|\d+|\*\/\d+|\d+-\d+|\d+(,\d+)*)$/;

const isValidCron = (value) => {
  const segments = String(value || '').trim().split(/\s+/);
  if (segments.length !== 5) return false;
  return segments.every((seg) => {
    if (!CRON_SEGMENT_RE.test(seg)) return false;
    if (/^\d+$/.test(seg)) {
      const num = Number(seg);
      return num <= 59;
    }
    return true;
  });
};

const disablePastDate = (current) => current && current < dayjs().startOf('day');

const addPlanRules = {
  name: [{ required: true, get message() { return taskText('tasks.enterAName'); } }],
  target: [{ required: true, get message() { return taskText('tasks.enterTargets'); } }],
  schedule_type: [{ required: true, get message() { return taskText('tasks.selectAScheduleType'); } }],
  policy_id: [{ required: true, get message() { return taskText('tasks.selectAPolicy'); } }],
  task_tag: [{ required: true, get message() { return taskText('tasks.selectATaskCategory'); } }],
  start_date: [{ required: true, get message() { return taskText('tasks.selectAStartTime'); } }],
  cron: [
    { required: true, get message() { return taskText('tasks.enterACronExpression'); } },
    {
      validator: (_rule, value) => {
        if (!value || isValidCron(value)) return Promise.resolve();
        return Promise.reject(taskText('tasks.invalidCronUseFiveFieldsEG0'));
      }
    }
  ]
};

const addMonitorRules = {
  scope_id: [{ required: true, get message() { return taskText('tasks.selectAnAssetGroup'); } }],
  monitor_type: [{ required: true, get message() { return taskText('tasks.selectAScheduleType'); } }],
  domains: [
    {
      required: true,
      type: 'array',
      min: 1,
      get message() { return taskText('tasks.selectMonitorTargets'); }
    }
  ],
  interval_hours: [{ required: true, get message() { return taskText('tasks.runIntervalMin6HoursExtra'); } }]
};

const switchAddMode = (mode) => {
  addMode.value = mode;
};

const openAddModal = () => {
  addMode.value = activeCategory.value === 'monitor' ? 'monitor' : 'planning';
  Object.assign(addForm, {
    name: '',
    target: '',
    schedule_type: 'future_scan',
    policy_id: undefined,
    task_tag: undefined,
    start_date: '',
    cron: ''
  });
  Object.assign(addMonitorForm, {
    scope_id: undefined,
    monitor_type: 'target',
    domains: [],
    policy_id: undefined,
    name: '',
    interval_hours: 24
  });
  if (scopeList.value.length === 0) {
    fetchScopeList();
  }
  addModalVisible.value = true;
};

const onScheduleTypeChange = () => {
  const hadValue = !!addForm.start_date || !!addForm.cron;
  addForm.start_date = '';
  addForm.cron = '';
  addPlanFormRef.value?.clearValidate(['start_date', 'cron']);
  if (hadValue) {
    message.info(taskText('tasks.scheduleTypeChangedPleaseEnterTheScheduleAgain'));
  }
};

const submitAdd = async () => {
  if (addMode.value === 'planning') {
    try {
      await addPlanFormRef.value.validate();
    } catch (error) {
      return;
    }

    const payload = {
      name: addForm.name,
      target: addForm.target,
      schedule_type: addForm.schedule_type,
      policy_id: addForm.policy_id,
      task_tag: addForm.task_tag
    };

    if (addForm.schedule_type === 'future_scan') {
      payload.start_date = addForm.start_date;
    } else {
      payload.cron = addForm.cron;
    }

    addLoading.value = true;
    try {
      const res = await request.post('/task_schedule/', payload);
      if (res.code === 200) {
        message.success(taskText('tasks.scheduledTaskCreated'));
        addModalVisible.value = false;
        await fetchAllSchedules();
      } else {
        message.error(res.message || taskText('tasks.failedToCreateTask'));
      }
    } catch (error) {
      message.error(taskText('tasks.requestFailedTaskWasNotCreated'));
    } finally {
      addLoading.value = false;
    }
  } else {
    try {
      await addMonitorFormRef.value.validate();
    } catch (error) {
      return;
    }

    const intervalSeconds = Number(addMonitorForm.interval_hours || 24) * 3600;
    let apiUrl = '/scheduler/add/';
    const payload = {
      scope_id: addMonitorForm.scope_id,
      interval: intervalSeconds,
      name: String(addMonitorForm.name || '').trim()
    };

    if (addMonitorForm.monitor_type === 'target') {
      apiUrl = '/scheduler/add/';
      payload.domain = (addMonitorForm.domains || []).join(',');
      if (addMonitorForm.policy_id) {
        payload.policy_id = addMonitorForm.policy_id;
      }
    } else if (addMonitorForm.monitor_type === 'site_monitor') {
      apiUrl = '/scheduler/add/site_monitor/';
    } else if (addMonitorForm.monitor_type === 'wih_monitor') {
      apiUrl = '/scheduler/add/wih_monitor/';
    }

    addLoading.value = true;
    try {
      const res = await request.post(apiUrl, payload);
      if (res.code === 200) {
        message.success(taskText('tasks.operationCompleted'));
        addModalVisible.value = false;
        notifyAssetMutated();
        lastObservedMutationVersion = assetMutationVersion.value;
        await fetchAllSchedules();
      } else {
        message.error(res.message || taskText('tasks.failedToCreateTask'));
      }
    } catch (error) {
      message.error(taskText('tasks.requestFailedTaskWasNotCreated'));
    } finally {
      addLoading.value = false;
    }
  }
};

// ================= 生命周期 =================
onMounted(() => {
  fetchAllSchedules();
  fetchPolicyList();
  fetchScopeList();
  startSmartPolling();
});

let firstActivation = true;
onActivated(() => {
  const mutated = assetMutationVersion.value !== lastObservedMutationVersion;
  if (mutated) {
    lastObservedMutationVersion = assetMutationVersion.value;
    clearSelection();
  }
  if (firstActivation) {
    firstActivation = false;
    if (!mutated) {
      startSmartPolling();
      return;
    }
  }
  fetchAllSchedules(!mutated);
  fetchPolicyList();
  fetchScopeList();
  startSmartPolling();
});

onDeactivated(() => {
  stopSmartPolling();
  addModalVisible.value = false;
});

onUnmounted(() => {
  stopSmartPolling();
});
</script>

<style scoped>
/* ==========================================================================
   顶层与三段式状态指标卡（对齐 TaskList.vue 视觉规范）
   ========================================================================== */
.arl-hero-title .title-text {
  font-size: 15px;
  font-weight: 600;
  color: var(--arl-text-color);
  letter-spacing: -0.2px;
}

.capsule-icon {
  font-size: 13px;
}

.auto-refresh-toggle {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--arl-text-secondary);
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
}

.task-refresh-btn {
  font-size: 12px;
}

.primary-action-btn {
  box-shadow: 0 2px 4px color-mix(in srgb, var(--arl-theme-color) 20%, transparent);
}

.task-metric-cards-row {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 10px;
  padding: 10px 0;
  border-bottom: 1px solid var(--arl-border-color);
}

.metric-stat-card {
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
  padding: 8px 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
  height: 100%;
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
}

.metric-stat-card:hover {
  background: var(--arl-bg-white);
  border-color: var(--arl-theme-color);
  box-shadow: 0 2px 6px rgba(0, 0, 0, 0.05);
  transform: translateY(-1px);
}

.metric-stat-card.active {
  background: var(--arl-bg-white);
  border-color: var(--arl-theme-color);
  box-shadow: 0 0 0 2px color-mix(in srgb, var(--arl-theme-color) 15%, transparent);
}

.stat-card-inner {
  display: flex;
  align-items: center;
  gap: 10px;
}

.stat-icon-box {
  width: 32px;
  height: 32px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  flex-shrink: 0;
}

.stat-icon-box.all {
  background: var(--arl-theme-soft-bg);
  color: var(--arl-theme-color);
}

.stat-icon-box.running {
  background: rgba(82, 196, 26, 0.12);
  color: #52c41a;
}

.stat-icon-box.done {
  background: rgba(0, 188, 212, 0.12);
  color: #00bcd4;
}

.stat-icon-box.error {
  background: rgba(255, 77, 79, 0.1);
  color: #ff4d4f;
}

.stat-info {
  min-width: 0;
  flex: 1;
}

.stat-label {
  font-size: 12px;
  color: var(--arl-text-secondary);
  line-height: 1.2;
  display: flex;
  align-items: center;
  gap: 4px;
}

.mini-pulse-beacon {
  width: 5px;
  height: 5px;
  background: #52c41a;
  border-radius: 50%;
  animation: pulseBeacon 1.6s infinite ease-in-out;
}

@keyframes pulseBeacon {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.45; transform: scale(0.8); }
}

.stat-value {
  font-size: 17px;
  font-weight: 600;
  color: var(--arl-text-color);
  line-height: 1.3;
  margin-top: 2px;
}

.stat-value.running { color: #52c41a; }
.stat-value.done { color: var(--arl-theme-color); }
.stat-value.error { color: #ff4d4f; }

/* ==========================================================================
   下层：常驻核心检索栏
   ========================================================================== */
.task-filter-container {
  padding-top: 10px;
}

.resident-filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 10px;
}

.filter-inputs-group {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.filter-actions-group {
  display: flex;
  align-items: center;
  gap: 8px;
}

.input-prefix-icon {
  color: var(--arl-text-secondary);
  opacity: 0.6;
}

.status-option-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}

.status-dot.running { background: #1890ff; }
.status-dot.done { background: #52c41a; }
.status-dot.stop { background: #faad14; }
.status-dot.error { background: #ff4d4f; }
.status-dot.plan { background: #4f46e5; }
.status-dot.monitor { background: #0d9488; }

/* ==========================================================================
   浮动批量操作激活条与表格卡片
   ========================================================================== */
.floating-batch-action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 16px;
  background: var(--arl-theme-soft-bg);
  border: 1px solid var(--arl-theme-soft-border);
  border-radius: 6px;
  margin-bottom: 12px;
  animation: batchFadeIn 0.25s ease;
}

@keyframes batchFadeIn {
  from { opacity: 0; transform: translateY(-3px); }
  to { opacity: 1; transform: translateY(0); }
}

.selected-count-badge {
  font-size: 13px;
  color: var(--arl-theme-color);
}

.batch-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.arl-table-card {
  background: var(--arl-bg-white);
  border: 1px solid var(--arl-border-color);
  border-radius: 8px;
  padding: 12px 16px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.03);
}

/* ==========================================================================
   行内胶囊标签与上下文样式
   ========================================================================== */
.arl-capsule-cell {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 6px;
}

.arl-schedule-capsule {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.5;
  white-space: nowrap;
  border: 1px solid transparent;
}

.arl-schedule-capsule.is-plan {
  background: color-mix(in srgb, #4f46e5 12%, transparent);
  color: #4f46e5;
  border-color: color-mix(in srgb, #4f46e5 28%, transparent);
}

.arl-schedule-capsule.is-monitor {
  background: color-mix(in srgb, #0d9488 12%, transparent);
  color: #0d9488;
  border-color: color-mix(in srgb, #0d9488 28%, transparent);
}

.arl-sub-tag-pill {
  display: inline-flex;
  align-items: center;
  padding: 1px 7px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 500;
  background: var(--arl-bg-hover);
  color: var(--arl-text-secondary);
  border: 1px solid var(--arl-border-color);
  white-space: nowrap;
}

.arl-sub-tag-pill.is-risk {
  color: #d97706;
  border-color: color-mix(in srgb, #d97706 30%, transparent);
  background: color-mix(in srgb, #d97706 10%, transparent);
}

.arl-target-cell {
  display: inline-block;
  max-width: 160px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  vertical-align: bottom;
}

.arl-context-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  max-width: 170px;
}

.arl-context-pill {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  flex-shrink: 0;
}

.arl-context-pill.is-policy {
  background: color-mix(in srgb, #6366f1 12%, transparent);
  color: #6366f1;
}

.arl-context-pill.is-scope {
  background: color-mix(in srgb, #0891b2 12%, transparent);
  color: #0891b2;
}

.arl-context-text,
.arl-context-link {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.arl-context-link {
  cursor: pointer;
}

.arl-rule-cell {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.arl-rule-badge {
  display: inline-flex;
  align-items: center;
  padding: 1px 6px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
  background: var(--arl-bg-hover);
  color: var(--arl-text-secondary);
  border: 1px solid var(--arl-border-color);
  flex-shrink: 0;
}

.arl-mono-rule {
  font-family: var(--arl-font-mono);
  font-size: 12px;
}

.arl-row-actions {
  display: flex;
  gap: 6px;
}

.arl-modal-capsule-bar {
  display: flex;
  justify-content: center;
  margin: 14px 0 20px;
}

.arl-scope-target-quick-bar {
  display: flex;
  gap: 8px;
  margin-top: 4px;
}

.page-wide-text .stat-label {
  line-height: 1.3;
  flex-wrap: wrap;
  overflow-wrap: anywhere;
}

@media (max-width: 1440px) {
  .page-wide-text .task-metric-cards-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 1366px) {
  .task-metric-cards-row {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 640px) {
  .task-metric-cards-row,
  .page-wide-text .task-metric-cards-row {
    grid-template-columns: 1fr;
  }
}
</style>
