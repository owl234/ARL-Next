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
          <a-badge v-if="hasIncrement" count="有增量" :number-style="{ backgroundColor: '#52c41a', fontSize: '10px' }" />
        </div>
        <div style="display: flex; gap: 8px; align-items: center;">
          <a-tooltip title="重新抓取企业最新备案、APP与投资数据，比对发现增量资产">
            <a-button type="primary" size="small" :loading="refreshLoading" @click="handleRefreshTask">
              <template #icon><sync-outlined :spin="refreshLoading" /></template>
              更新主体资产
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
              <code-outlined /> 测绘日志
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
            <span class="toolbar-title-text">{{ currentTabLabel }}维度</span>
            <span class="toolbar-meta-count">
              共 <b class="font-mono">{{ activeTab === 'log' ? syslogList.length : (queryCounts[activeTab] || pagination.total || 0) }}</b> 条记录
            </span>
            <a-tag v-if="hasIncrement && activeTab !== 'log'" color="success" class="osint-mini-tag">
              发现增量
            </a-tag>
          </div>

          <div class="toolbar-right">
            <template v-if="activeTab !== 'log'">
              <a-tooltip title="重新抓取企业最新备案、APP与投资数据，比对发现增量资产">
                <a-button type="primary" size="small" :loading="refreshLoading" @click="handleRefreshTask">
                  <template #icon><sync-outlined :spin="refreshLoading" /></template>
                  更新主体资产
                </a-button>
              </a-tooltip>
              <a-tooltip title="更换当前资产组绑定的企业主体并重新拉取全域资产">
                <a-button size="small" @click="emit('openBind')">
                  <template #icon><link-outlined /></template>
                  重新绑定
                </a-button>
              </a-tooltip>
              <a-button size="small" :loading="exportLoading" @click="handleExport">
                <template #icon><download-outlined /></template>
                导出当前维度
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
                {{ isAdvancedFilterOpen ? '收起筛选' : '高级筛选' }}
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
              <span v-if="taskRecord.status === 'running'" class="log-polling-hint">(3秒轮询中)</span>
              <a-button size="small" :loading="logLoading" @click="() => fetchLogs(true)">
                <template #icon><sync-outlined :spin="logLoading" /></template>
                刷新日志
              </a-button>
            </template>
          </div>
        </div>

        <!-- 直接平铺的紧凑栅格筛选卡片 (可折叠) -->
        <transition name="fade-slide">
          <div v-show="isAdvancedFilterOpen" v-if="activeTab !== 'log' && currentSearchFields.length" class="osint-filter-card">
          <a-form :model="searchForm" class="filter-grid-form">
            <a-row :gutter="[12, 6]">
              <a-col
                v-for="field in currentSearchFields"
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

                    <!-- 组合操作符输入框 (如 投资比例/数额 等于/大于/小于) -->
                    <div
                      v-else-if="field.hasOperatorSelect"
                      class="filter-operator-box"
                    >
                      <a-input
                        v-model:value="searchForm[field.key]"
                        :placeholder="`请输入${field.label}`"
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
                      :placeholder="`请输入${field.label}`"
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
              <a-tooltip title="复制域名" v-if="record.domain || record.ym">
                <a-button type="text" size="small" style="padding: 0 4px; height: 22px;" @click.stop="handleCopyText(record.domain || record.ym)">
                  <copy-outlined style="font-size: 12px; opacity: 0.65;" />
                </a-button>
              </a-tooltip>
            </div>
          </template>

          <!-- 首页网址外链与快捷复制 -->
          <template v-else-if="column.key === 'homeUrl'">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 4px;">
              <a v-if="getAssetHomeUrl(record)" :href="getAssetHomeUrl(record)" target="_blank" rel="noopener noreferrer" style="color: var(--arl-theme-color); word-break: break-all;">
                {{ getAssetHomeUrl(record) }} <export-outlined style="font-size: 11px;" />
              </a>
              <span v-else>-</span>
              <a-tooltip title="复制网址" v-if="getAssetHomeUrl(record)">
                <a-button type="text" size="small" style="padding: 0 4px; height: 22px;" @click.stop="handleCopyText(getAssetHomeUrl(record))">
                  <copy-outlined style="font-size: 12px; opacity: 0.65;" />
                </a-button>
              </a-tooltip>
            </div>
          </template>

          <!-- 微博主页外链 -->
          <template v-else-if="column.key === 'href'">
            <a v-if="record.href" :href="record.href" target="_blank" rel="noopener noreferrer" style="color: var(--arl-theme-color);">
              访问微博 <export-outlined style="font-size: 11px;" />
            </a>
            <span v-else>-</span>
          </template>

          <!-- 公众号二维码浮层预览 -->
          <template v-else-if="column.key === 'qrcode'">
            <a-popover v-if="record.codeImg" placement="right" trigger="hover">
              <template #content>
                <div style="text-align: center; padding: 4px;">
                  <img :src="record.codeImg" style="width: 150px; height: 150px; display: block;" />
                  <span style="font-size: 12px; color: #8c8c8c; margin-top: 4px; display: block;">微信扫码关注</span>
                </div>
              </template>
              <a-tag color="blue" style="cursor: pointer;"><qrcode-outlined /> 查看二维码</a-tag>
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
            {{ record.serviceName || record.name || record.webName || record.title || record.tmName || '-' }}
          </template>

          <!-- 法定代表人 -->
          <template v-else-if="column.key === 'legalPerson'">
            {{ record.legalPerson || record.legalPersonName || '-' }}
          </template>

          <!-- 分类字段 -->
          <template v-else-if="column.key === 'category'">
            {{ record.category || record.classes || record.intCls || record.type || '-' }}
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
            <a-tooltip title="查看原始 JSON 数据" placement="top">
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
          <div class="empty-default-box">
            <a-empty description="暂无生态数据" />
          </div>
        </template>
      </a-table>

      <!-- 分页栏 -->
      <div style="display: flex; justify-content: space-between; align-items: center; padding: 0 12px; margin-top: 10px;">
        <div style="color: var(--arl-text-color); opacity: 0.65; font-size: 12px;">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
        <a-pagination
          :pageSizeOptions="['10', '20', '50', '100']"
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
            <span>已选中 <b style="color: var(--arl-theme-color); margin: 0 4px;">{{ selectedWebRowKeys.length }}</b> 项备案域名</span>
          </div>
          <div class="floating-actions">
            <a-button type="primary" size="middle" @click="openSyncModalWithSelected">
              <template #icon><cloud-sync-outlined /></template>
              同步至资产组 ({{ selectedWebRowKeys.length }})
            </a-button>
            <a-button size="middle" @click="handleBatchCopyDomains">
              <template #icon><copy-outlined /></template>
              复制域名
            </a-button>
            <a-button size="middle" @click="clearWebSelection">取消选择</a-button>
          </div>
        </div>
      </transition>
    </div>

    <!-- 运行日志 Tab -->
    <div v-if="taskId && activeTab === 'log'" style="margin-top: 8px;">
      <div class="log-terminal-card">
        <div class="log-terminal-header">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-weight: 600; font-size: 13px;">任务执行过程日志</span>
            <a-tag :color="taskRecord.status === 'running' ? 'processing' : taskRecord.status === 'done' ? 'success' : taskRecord.status === 'error' ? 'error' : 'default'">
              {{ taskRecord.status === 'running' ? '实时采集监控中...' : taskRecord.status === 'done' ? '测绘已完成' : taskRecord.status === 'error' ? '任务异常终止' : (taskRecord.status || '就绪') }}
            </a-tag>
            <span style="color: var(--arl-text-secondary); font-size: 12px;" v-if="taskRecord.status === 'running'">(每 3 秒自动轮询增量)</span>
          </div>
          <a-button size="small" :loading="logLoading" @click="() => fetchLogs(true)">
            <template #icon><sync-outlined :spin="logLoading" /></template>
            刷新日志
          </a-button>
        </div>
        <div ref="terminalContainer" class="log-terminal-body">
          <div v-for="(log, idx) in syslogList" :key="idx" class="log-terminal-line">
            <span class="log-time">[{{ log.create_time }}]</span>
            <span :class="['log-level', log.level]">[{{ (log.level || 'info').toUpperCase() }}]</span>
            <span class="log-title">[{{ log.title }}]</span>
            <span class="log-msg">{{ log.message }}</span>
          </div>
          <div v-if="syslogList.length === 0" class="log-empty">[System] 暂无日志记录... (历史任务或日志正在生成中)</div>
        </div>
      </div>
    </div>

    <!-- 同步至资产分组弹窗 -->
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
import { ref, reactive, computed, watch, nextTick, onMounted, onUnmounted } from 'vue';
import { message } from 'ant-design-vue';
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
  LinkOutlined,
  FilterOutlined,
  DownOutlined,
  UpOutlined
} from '@ant-design/icons-vue';
import request from '../utils/request';
import { copyText } from '../utils/clipboard';
import SyncToScopeModal from './SyncToScopeModal.vue';
import RawDataDrawer from './RawDataDrawer.vue';

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
  }
});

const emit = defineEmits(['synced', 'refreshed', 'taskLoaded', 'update:taskId', 'openBind']);

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
  if (ok) message.success('已复制: ' + text);
};

const activeTab = ref('web');
const loading = ref(false);
const exportLoading = ref(false);
const refreshLoading = ref(false);
const pagination = reactive({ current: 1, pageSize: 10, total: 0 });

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
  trademark: 0,
  invest: 0,
});

const displayName = computed(() => {
  return props.enterpriseName || (taskName.value && !taskName.value.includes('TYC_') ? taskName.value : '') || (taskTarget.value && !taskTarget.value.startsWith('TYC_') ? taskTarget.value : '') || taskName.value || '企业资产画像';
});

const taskTypeLabel = computed(() => {
  if (taskType.value === 'tyc') return '天眼查';
  if (taskType.value === 'icp') return 'ICP备案';
  return '';
});

const taskStatusLabel = computed(() => {
  const map = {
    waiting: '等待中',
    running: '运行中',
    done: '已完成',
    stop: '已停止',
    error: '执行失败'
  };
  return map[taskStatus.value] || taskStatus.value;
});

const taskStatusColor = computed(() => {
  const map = {
    waiting: 'warning',
    running: 'processing',
    done: 'success',
    stop: 'default',
    error: 'error'
  };
  return map[taskStatus.value] || 'default';
});

const syncModalVisible = ref(false);
const selectedWebRowKeys = ref([]);
const selectedWebDomains = ref([]);

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
  if (ok) message.success(`已复制 ${selectedWebDomains.value.length} 个域名至剪贴板`);
};

const openSyncModalWithSelected = () => {
  syncModalVisible.value = true;
};

const handleSyncSuccess = (res) => {
  fetchTaskStatistic();
  emit('synced', res);
};

const handleRefreshTask = async () => {
  if (!props.taskId) return;
  refreshLoading.value = true;
  try {
    const res = await request.get(`/icp/restart/${props.taskId}`);
    if (res.code === 200) {
      message.success('已触发主体资产更新任务');
      const newTaskId = res.data?.task_id;
      if (newTaskId) {
        emit('update:taskId', newTaskId);
      }
      fetchTaskDetail();
      emit('refreshed', newTaskId);
    } else {
      message.error(res.message || '触发失败');
    }
  } catch (err) {
    message.error('网络请求失败');
  } finally {
    refreshLoading.value = false;
  }
};

/* ================= 维度列表与精选筛选项配置 (osintTabConfig) ================= */
const osintTabList = [
  { key: 'web', label: '网站备案' },
  { key: 'app', label: '移动 APP' },
  { key: 'mapp', label: '微信小程序' },
  { key: 'wechat', label: '微信公众号' },
  { key: 'weibo', label: '企业微博' },
  { key: 'kapp', label: '快应用' },
  { key: 'trademark', label: '商标信息' },
  { key: 'invest', label: '对外投资' }
];

const osintTabConfig = reactive({
  web: {
    label: '网站备案',
    searchFields: [
      { label: '域名', key: 'domain' },
      { label: '网站名称', key: 'serviceName' },
      { label: '主办单位', key: 'unitName' },
      { label: '备案号', key: 'serviceLicence' },
      { label: '单位性质', key: 'companyType' }
    ]
  },
  app: {
    label: '移动 APP',
    searchFields: [
      { label: 'APP名称', key: 'name' },
      { label: '主办单位', key: 'unitName' },
      { label: '备案号', key: 'serviceLicence' },
      { label: '分类', key: 'category' }
    ]
  },
  mapp: {
    label: '微信小程序',
    searchFields: [
      { label: '小程序名', key: 'name' },
      { label: '主办单位', key: 'unitName' },
      { label: '备案号', key: 'serviceLicence' },
      { label: '分类', key: 'category' }
    ]
  },
  wechat: {
    label: '微信公众号',
    searchFields: [
      { label: '公众号名', key: 'name' },
      { label: '微信号', key: 'wechatId' },
      { label: '认证主体', key: 'unitName' }
    ]
  },
  weibo: {
    label: '企业微博',
    searchFields: [
      { label: '微博昵称', key: 'name' },
      { label: '认证简介', key: 'brief' }
    ]
  },
  kapp: {
    label: '快应用',
    searchFields: [
      { label: '快应用名', key: 'name' },
      { label: '主办单位', key: 'unitName' },
      { label: '备案号', key: 'serviceLicence' }
    ]
  },
  trademark: {
    label: '商标信息',
    searchFields: [
      { label: '商标名称', key: 'name' },
      { label: '注册号', key: 'regNo' },
      { label: '国际分类', key: 'category' },
      { label: '状态', key: 'status' }
    ]
  },
  invest: {
    label: '对外投资',
    searchFields: [
      { label: '企业名称', key: 'name' },
      { label: '法定代表人', key: 'legalPerson' },
      { label: '企业状态', key: 'status' },
      { label: '投资比例', key: 'percent', hasOperatorSelect: true, operator: 'eq', operators: ['eq', 'gt', 'lt'] },
      { label: '投资数额', key: 'amount', hasOperatorSelect: true, operator: 'eq', operators: ['eq', 'gt', 'lt'] }
    ]
  }
});

const currentSearchFields = computed(() => {
  return osintTabConfig[activeTab.value]?.searchFields || [];
});

const currentTabLabel = computed(() => {
  if (activeTab.value === 'log') return '测绘日志';
  return osintTabConfig[activeTab.value]?.label || '资产';
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
    { title: '序号', key: 'index', width: 55, align: 'center' },
    { title: '域名', dataIndex: 'domain', key: 'domain', width: 170 },
    { title: '网站名称', dataIndex: 'serviceName', key: 'serviceName', width: 160, ellipsis: true },
    { title: '主办单位', dataIndex: 'unitName', key: 'unitName', ellipsis: true },
    { title: '单位性质', dataIndex: 'companyType', key: 'companyType', width: 90, align: 'center' },
    { title: '备案号', dataIndex: 'serviceLicence', key: 'serviceLicence', width: 170 },
    { title: '首页网址', dataIndex: 'homeUrl', key: 'homeUrl', width: 170, ellipsis: true },
    { title: '更新时间', dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 120, align: 'center' },
    { title: '原始', key: 'raw', width: 55, align: 'center' }
  ],
  app: [
    { title: '序号', key: 'index', width: 55, align: 'center' },
    { title: '图标', dataIndex: 'icon', key: 'icon', width: 65, align: 'center' },
    { title: 'APP名称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '分类', dataIndex: 'category', key: 'category', width: 100 },
    { title: '备案号', dataIndex: 'serviceLicence', key: 'serviceLicence', width: 160 },
    { title: '主办单位', dataIndex: 'unitName', key: 'unitName', ellipsis: true },
    { title: '简介', dataIndex: 'brief', key: 'brief', ellipsis: true },
    { title: '版本', dataIndex: 'version', key: 'version', width: 90, align: 'center' },
    { title: '更新时间', dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 120, align: 'center' },
    { title: '原始', key: 'raw', width: 55, align: 'center' }
  ],
  mapp: [
    { title: '序号', key: 'index', width: 55, align: 'center' },
    { title: '图标', dataIndex: 'icon', key: 'icon', width: 65, align: 'center' },
    { title: '小程序名称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '备案号', dataIndex: 'serviceLicence', key: 'serviceLicence', width: 170 },
    { title: '主办单位', dataIndex: 'unitName', key: 'unitName', ellipsis: true },
    { title: '分类', dataIndex: 'category', key: 'category', width: 100 },
    { title: '描述', dataIndex: 'brief', key: 'brief', ellipsis: true },
    { title: '更新时间', dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 120, align: 'center' },
    { title: '原始', key: 'raw', width: 55, align: 'center' }
  ],
  wechat: [
    { title: '序号', key: 'index', width: 55, align: 'center' },
    { title: '头像', dataIndex: 'icon', key: 'icon', width: 65, align: 'center' },
    { title: '公众号名称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '微信号', dataIndex: 'wechatId', key: 'wechatId', width: 140 },
    { title: '二维码', key: 'qrcode', width: 80, align: 'center' },
    { title: '功能介绍', dataIndex: 'brief', key: 'brief', ellipsis: true },
    { title: '认证主体', dataIndex: 'unitName', key: 'unitName', ellipsis: true },
    { title: '原始', key: 'raw', width: 55, align: 'center' }
  ],
  weibo: [
    { title: '序号', key: 'index', width: 55, align: 'center' },
    { title: '头像', dataIndex: 'icon', key: 'icon', width: 65, align: 'center' },
    { title: '微博昵称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '认证信息/简介', dataIndex: 'brief', key: 'brief', ellipsis: true },
    { title: '微博主页', key: 'href', width: 160 },
    { title: '粉丝数', dataIndex: 'fans', key: 'fans', width: 100, align: 'center' },
    { title: '原始', key: 'raw', width: 55, align: 'center' }
  ],
  kapp: [
    { title: '序号', key: 'index', width: 55, align: 'center' },
    { title: '图标', dataIndex: 'icon', key: 'icon', width: 65, align: 'center' },
    { title: '快应用名称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '备案号', dataIndex: 'serviceLicence', key: 'serviceLicence', width: 170 },
    { title: '主办单位', dataIndex: 'unitName', key: 'unitName', ellipsis: true },
    { title: '分类', dataIndex: 'category', key: 'category', width: 100 },
    { title: '更新时间', dataIndex: 'updateRecordTime', key: 'updateRecordTime', width: 120, align: 'center' },
    { title: '原始', key: 'raw', width: 55, align: 'center' }
  ],
  trademark: [
    { title: '序号', key: 'index', width: 55, align: 'center' },
    { title: '商标图', dataIndex: 'icon', key: 'icon', width: 65, align: 'center' },
    { title: '商标名称', dataIndex: 'name', key: 'name', width: 160 },
    { title: '注册号', dataIndex: 'regNo', key: 'regNo', width: 140 },
    { title: '国际分类', dataIndex: 'category', key: 'category', width: 110 },
    { title: '状态', dataIndex: 'status', key: 'status', width: 100, align: 'center' },
    { title: '申请日期', dataIndex: 'appDate', key: 'appDate', width: 120, align: 'center' },
    { title: '原始', key: 'raw', width: 55, align: 'center' }
  ],
  invest: [
    { title: '序号', key: 'index', width: 55, align: 'center' },
    { title: '被投资企业', dataIndex: 'name', key: 'name', ellipsis: true },
    { title: '法定代表人', dataIndex: 'legalPerson', key: 'legalPerson', width: 110 },
    { title: '投资比例', dataIndex: 'percent', key: 'percent', width: 100, align: 'center' },
    { title: '投资数额', dataIndex: 'amount', key: 'amount', width: 140 },
    { title: '企业状态', dataIndex: 'status', key: 'status', width: 100, align: 'center' },
    { title: '地区', key: 'region', width: 130 },
    { title: '成立日期', key: 'estiblishTime', width: 120, align: 'center' },
    { title: '原始', key: 'raw', width: 55, align: 'center' }
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
  return record.icon || record.titleImgURL || record.codeImg || record.ico || record.productLogo || record.tmPic || '';
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
      queryCounts.trademark = stats.trademark_cnt || 0;
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
  fetchAssets(page, pageSize);
};

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
    message.success('导出成功');
  } catch (err) {
    message.error('导出失败');
  } finally {
    exportLoading.value = false;
  }
};

watch(() => props.taskId, (newVal) => {
  if (newVal) {
    fetchTaskDetail();
    if (activeTab.value === 'log') {
      fetchLogs(true);
      startLogPolling();
    } else {
      stopLogPolling();
      fetchAssets(pagination.current, pagination.pageSize);
    }
  }
}, { immediate: true });

defineExpose({
  handleRefreshTask,
  refreshLoading,
  queryCounts,
  taskRecord,
  fetchTaskDetail
});
</script>

<style scoped>
/* ================= OSINT 吸顶控制区 (与 ASM 完全对齐) ================= */
.osint-sticky-control-box {
  position: sticky;
  z-index: 11;
  background: var(--arl-bg-white);
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

/* ================= 标准空状态 ================= */
.empty-default-box {
  padding: 40px 0;
}

/* ================= 悬浮浮动批处理条 (Floating Action Bar) ================= */
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
  transform: translate(-50%, 20px);
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
  background-color: #001529;
  color: #e6f7ff;
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
  color: #40a9ff;
  margin-right: 8px;
}

.log-msg {
  color: #e6f7ff;
}

.log-empty {
  color: rgba(255, 255, 255, 0.45);
  font-style: italic;
}
</style>
