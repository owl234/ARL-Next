<template>
  <div class="dashboard-container">
    <!-- Row 1: 顶部数据统计卡片 -->
    <div class="dashboard-section section-stats">
      <a-row :gutter="[14, 14]" class="stat-row">
        <a-col :xs="24" :sm="12" :md="12" :lg="6">
          <a-card class="modern-stat-card clickable-card" :bordered="false" @click="router.push('/asset-search')">
            <a-skeleton :loading="initialLoading" active :paragraph="{ rows: 1 }" :title="false">
              <div class="stat-flex">
                <div class="stat-icon-box primary">
                  <DatabaseOutlined />
                </div>
                <div class="stat-info">
                  <div class="stat-label">总站点数量</div>
                  <div class="stat-value">{{ stats.total_assets }}</div>
                </div>
              </div>
            </a-skeleton>
          </a-card>
        </a-col>

        <a-col :xs="24" :sm="12" :md="12" :lg="6">
          <a-card class="modern-stat-card" :bordered="false">
            <a-skeleton :loading="initialLoading" active :paragraph="{ rows: 1 }" :title="false">
              <div class="stat-flex">
                <div class="stat-icon-box success">
                  <SyncOutlined />
                </div>
                <div class="stat-info" style="width: 100%;">
                  <div class="stat-label">今日动态</div>
                  <div class="stat-split-values">
                    <div class="stat-split-item" @click="router.push('/taskList')">
                      <div class="val">{{ stats.today_tasks }}</div>
                      <div class="sub-label">新增任务</div>
                    </div>
                    <div class="stat-divider"></div>
                    <div class="stat-split-item" @click="router.push('/asset-search')">
                      <div class="val text-primary">{{ stats.today_new_assets }}</div>
                      <div class="sub-label">新增站点</div>
                    </div>
                  </div>
                </div>
              </div>
            </a-skeleton>
          </a-card>
        </a-col>

        <a-col :xs="24" :sm="12" :md="12" :lg="6">
          <a-card class="modern-stat-card" :bordered="false">
            <a-skeleton :loading="initialLoading" active :paragraph="{ rows: 1 }" :title="false">
              <div class="stat-flex">
                <div class="stat-icon-box danger">
                  <AlertOutlined />
                </div>
                <div class="stat-info" style="width: 100%;">
                  <div class="stat-label">漏洞分布</div>
                  <div class="stat-vuln-bar">
                    <a-tooltip title="严重 (Nuclei)">
                      <div class="vuln-item critical" @click="router.push({ path: '/asset-search', query: { tab: 'nuclei_result', vuln_severity: 'critical' } })">{{ stats.vuln?.nuclei_critical || 0 }}</div>
                    </a-tooltip>
                    <a-tooltip title="高危 (Nuclei)">
                      <div class="vuln-item high" @click="router.push({ path: '/asset-search', query: { tab: 'nuclei_result', vuln_severity: 'high' } })">{{ stats.vuln?.nuclei_high || 0 }}</div>
                    </a-tooltip>
                    <a-tooltip title="中危 (Nuclei)">
                      <div class="vuln-item medium" @click="router.push({ path: '/asset-search', query: { tab: 'nuclei_result', vuln_severity: 'medium' } })">{{ stats.vuln?.nuclei_medium || 0 }}</div>
                    </a-tooltip>
                    <a-tooltip title="低危 (Nuclei)">
                      <div class="vuln-item low" @click="router.push({ path: '/asset-search', query: { tab: 'nuclei_result', vuln_severity: 'low' } })">{{ stats.vuln?.nuclei_low || 0 }}</div>
                    </a-tooltip>
                    <a-tooltip title="ARL 内部检测">
                      <div class="vuln-item arl" @click="router.push({ path: '/asset-search', query: { tab: 'vuln' } })">{{ stats.vuln?.arl_total || 0 }}</div>
                    </a-tooltip>
                  </div>
                </div>
              </div>
            </a-skeleton>
          </a-card>
        </a-col>

        <a-col :xs="24" :sm="12" :md="12" :lg="6">
          <a-card class="modern-stat-card clickable-card" :bordered="false" @click="router.push('/GitHubTasks/GitHubTasksList')">
            <a-skeleton :loading="initialLoading" active :paragraph="{ rows: 1 }" :title="false">
              <div class="stat-flex">
                <div class="stat-icon-box dark">
                  <GithubOutlined />
                </div>
                <div class="stat-info" style="width: 100%;">
                  <div class="stat-label">GitHub 监控动态 (今日)</div>
                  <div class="stat-split-values" style="margin-top: 2px;">
                    <div class="stat-split-item" @click.stop="router.push('/GitHubTasks/GitHubTasksList?tab=scheduler')">
                      <div class="val" style="color: #f5222d">{{ sysInfo.github_today?.leaks || 0 }}</div>
                      <div class="sub-label">新增泄露</div>
                    </div>
                    <div class="stat-divider"></div>
                    <a-tooltip placement="bottom">
                      <template #title>
                        <div style="font-size: 12px; line-height: 1.5;">
                          <div style="font-weight: bold; margin-bottom: 4px; color: #faad14;">今日新增明细：</div>
                          <div>● 新增 CVE：{{ sysInfo.github_today_breakdown?.cves || 0 }}</div>
                          <div>● 追踪大佬：{{ sysInfo.github_today_breakdown?.hackers || 0 }}</div>
                          <div>● 其他情报：{{ sysInfo.github_today_breakdown?.general || 0 }}</div>
                          <div style="border-top: 1px dashed rgba(255,255,255,0.4); margin: 6px 0;"></div>
                          <div style="font-weight: bold; margin-bottom: 4px;">全库累计收录：</div>
                          <div>● 累计 CVE：{{ sysInfo.github_totals?.cves || 0 }}</div>
                          <div>● 监控工具：{{ sysInfo.github_totals?.tools || 0 }}</div>
                          <div>● 追踪大佬：{{ sysInfo.github_totals?.hackers || 0 }}</div>
                        </div>
                      </template>
                      <div class="stat-split-item" @click.stop="router.push('/GitHubTasks/GitHubTasksList?tab=cve_history')">
                        <div class="val" style="color: #faad14">{{ sysInfo.github_today?.intel || 0 }}</div>
                        <div class="sub-label">新增情报</div>
                      </div>
                    </a-tooltip>
                  </div>
                </div>
              </div>
            </a-skeleton>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- Row 2: 系统硬件状态区域 -->
    <div class="dashboard-section section-sys">
      <a-row :gutter="[14, 14]" class="stat-row">
        <a-col :xs="24" :sm="12" :md="12" :lg="6">
          <a-card class="modern-stat-card" :bordered="false">
            <a-skeleton :loading="initialLoading" active :paragraph="{ rows: 1 }" :title="false">
              <div class="sys-flex">
                <div class="sys-info">
                  <div class="sys-label">CPU 占用</div>
                  <div class="sys-value" :style="{ color: sysInfo.cpu_percent > 80 ? '#ff4d4f' : 'inherit' }">{{ sysInfo.cpu_percent }}%</div>
                </div>
                <a-progress type="circle" :percent="sysInfo.cpu_percent" :width="46" :strokeWidth="7" :strokeColor="sysInfo.cpu_percent > 80 ? '#ff4d4f' : 'var(--arl-theme-color)'" :showInfo="false" />
              </div>
            </a-skeleton>
          </a-card>
        </a-col>

        <a-col :xs="24" :sm="12" :md="12" :lg="6">
          <a-card class="modern-stat-card" :bordered="false">
            <a-skeleton :loading="initialLoading" active :paragraph="{ rows: 1 }" :title="false">
              <div class="sys-flex">
                <div class="sys-info">
                  <div class="sys-label">内存占用</div>
                  <div class="sys-value" :style="{ color: sysInfo.mem_percent > 80 ? '#ff4d4f' : 'inherit' }">{{ sysInfo.mem_percent }}%</div>
                </div>
                <a-progress type="circle" :percent="sysInfo.mem_percent" :width="46" :strokeWidth="7" :strokeColor="sysInfo.mem_percent > 80 ? '#ff4d4f' : 'var(--arl-theme-color)'" :showInfo="false" />
              </div>
            </a-skeleton>
          </a-card>
        </a-col>

        <a-col :xs="24" :sm="12" :md="12" :lg="6">
          <a-card class="modern-stat-card" :bordered="false">
            <a-skeleton :loading="initialLoading" active :paragraph="{ rows: 1 }" :title="false">
              <div class="sys-flex">
                <div class="sys-info">
                  <div class="sys-label">磁盘占用</div>
                  <div class="sys-value" :style="{ color: sysInfo.disk_percent > 90 ? '#ff4d4f' : 'inherit' }">{{ sysInfo.disk_percent }}%</div>
                </div>
                <a-progress type="circle" :percent="sysInfo.disk_percent" :width="46" :strokeWidth="7" :strokeColor="sysInfo.disk_percent > 90 ? '#ff4d4f' : '#52c41a'" :showInfo="false" />
              </div>
            </a-skeleton>
          </a-card>
        </a-col>

        <a-col :xs="24" :sm="12" :md="12" :lg="6">
          <a-card class="modern-stat-card" :bordered="false">
            <a-skeleton :loading="initialLoading" active :paragraph="{ rows: 1 }" :title="false">
              <div class="sys-flex">
                <div class="sys-info" style="width: 100%;">
                  <div class="sys-label">后台任务 (Celery)</div>
                  <div class="stat-split-values" style="margin-top: 4px;">
                    <div class="stat-split-item" @click="router.push('/taskList')">
                      <div class="val" style="color: #52c41a">{{ sysInfo.tasks?.running || 0 }}</div>
                      <div class="sub-label">运行中</div>
                    </div>
                    <div class="stat-divider"></div>
                    <div class="stat-split-item" @click="router.push('/taskList')">
                      <div class="val" style="color: #fb8c00">{{ sysInfo.tasks?.waiting || 0 }}</div>
                      <div class="sub-label">等待中</div>
                    </div>
                  </div>
                </div>
              </div>
            </a-skeleton>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- Row 3: 主体态势（近7天趋势图 300px 黄金比例 + 最新系统动态 300px） -->
    <div class="dashboard-section section-main">
      <a-row :gutter="[14, 14]" class="main-row">
        <!-- 左侧：近7天站点与风险趋势 -->
        <a-col :xs="24" :lg="16" class="main-col">
          <a-card class="main-card trend-card" :bordered="false">
            <template #title>
              <div class="card-header-title">
                <LineChartOutlined class="card-header-icon" />
                <span>近7天站点与风险趋势</span>
              </div>
            </template>
            <div class="card-body-wrapper">
              <a-skeleton v-if="initialLoading" active :paragraph="{ rows: 6 }" style="padding: 12px;" />
              <div v-show="!initialLoading" ref="chartRef" class="echarts-box"></div>
            </div>
          </a-card>
        </a-col>

        <!-- 右侧：最新系统动态 (Log 展示) -->
        <a-col :xs="24" :lg="8" class="main-col">
          <a-card class="main-card log-card" :bordered="false">
            <template #title>
              <div class="card-header-title">
                <ClockCircleOutlined class="card-header-icon" />
                <span>最新系统动态 (Log)</span>
              </div>
            </template>
            <template #extra>
              <span class="log-badge-total" v-if="logs.length">{{ logs.length }} 条动态</span>
            </template>
            <div class="card-body-wrapper">
              <a-skeleton v-if="initialLoading" active :paragraph="{ rows: 4 }" style="padding: 12px;" />
              <div v-else class="log-scroll-area">
                <a-timeline v-if="logs.length > 0">
                  <a-timeline-item
                    v-for="(log, index) in logs"
                    :key="index"
                    :color="getLogColor(log.level)"
                    class="clickable-log"
                    @click="showLogDetail(log)"
                  >
                    <div class="log-item-header">
                      <span class="log-item-tag" :class="log.level || 'info'">[{{ log.title || (log.level === 'error' ? '异常' : '通知') }}]</span>
                      <span class="log-item-time">{{ log.create_time }}</span>
                    </div>
                    <div class="log-item-msg">{{ log.message }}</div>
                  </a-timeline-item>
                </a-timeline>
                <div v-else class="empty-log-box">
                  <a-empty description="暂无系统动态" :image="simpleImage" />
                </div>
              </div>
            </div>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- Row 4: 业务拓展行 (Web指纹TOP5 + 漏洞严重级别环形图 + 实时任务流) -->
    <div class="dashboard-section section-widgets">
      <a-row :gutter="[14, 14]" class="widget-row">
        <!-- 模块 1: Web 指纹与组件 TOP 5 -->
        <a-col :xs="24" :lg="8" class="widget-col">
          <a-card class="widget-card" :bordered="false">
            <template #title>
              <div class="card-header-title">
                <TagsOutlined class="card-header-icon" />
                <span>Web 指纹与组件 TOP 5</span>
              </div>
            </template>
            <template #extra>
              <span class="widget-extra-link" @click="router.push('/fingerprint')">
                指纹库 <RightOutlined style="font-size: 11px;" />
              </span>
            </template>
            <div class="widget-body-wrapper">
              <a-skeleton v-if="initialLoading" active :paragraph="{ rows: 4 }" />
              <div v-else-if="widgetsData.top_fingerprints && widgetsData.top_fingerprints.length > 0" class="finger-list-container">
                <div 
                  v-for="(item, idx) in widgetsData.top_fingerprints" 
                  :key="idx" 
                  class="finger-rank-item"
                  @click="router.push({ path: '/asset-search', query: { tab: 'site', finger: item.name } })"
                  title="点击查看该指纹站点"
                >
                  <div class="finger-rank-left">
                    <span class="rank-badge" :class="'rank-' + (idx + 1)">{{ idx + 1 }}</span>
                    <span class="finger-name" :title="item.name">{{ item.name }}</span>
                  </div>
                  <div class="finger-rank-bar-wrap">
                    <div class="finger-progress-bar">
                      <div class="finger-progress-fill" :style="{ width: getFingerPercent(item.count) + '%' }"></div>
                    </div>
                  </div>
                  <div class="finger-rank-count">{{ item.count }} 站点</div>
                </div>
              </div>
              <div v-else class="empty-widget-box">
                <a-empty description="暂无指纹聚合数据" :image="simpleImage" />
              </div>
            </div>
          </a-card>
        </a-col>

        <!-- 模块 2: 漏洞严重级别分布环形图 -->
        <a-col :xs="24" :lg="8" class="widget-col">
          <a-card class="widget-card" :bordered="false">
            <template #title>
              <div class="card-header-title">
                <PieChartOutlined class="card-header-icon" />
                <span>漏洞严重级别分布</span>
              </div>
            </template>
            <template #extra>
              <span class="widget-extra-link" @click="router.push({ path: '/asset-search', query: { tab: 'nuclei_result' } })">
                漏洞库 <RightOutlined style="font-size: 11px;" />
              </span>
            </template>
            <div class="widget-body-wrapper">
              <a-skeleton v-if="initialLoading" active :paragraph="{ rows: 4 }" />
              <div v-show="!initialLoading" ref="vulnChartRef" class="echarts-widget-box"></div>
            </div>
          </a-card>
        </a-col>

        <!-- 模块 3: 实时任务流 -->
        <a-col :xs="24" :lg="8" class="widget-col">
          <a-card class="widget-card" :bordered="false">
            <template #title>
              <div class="card-header-title">
                <ThunderboltOutlined class="card-header-icon" />
                <span>实时任务流</span>
              </div>
            </template>
            <template #extra>
              <span class="widget-extra-link" @click="router.push('/taskList')">
                任务大厅 <RightOutlined style="font-size: 11px;" />
              </span>
            </template>
            <div class="widget-body-wrapper">
              <a-skeleton v-if="initialLoading" active :paragraph="{ rows: 4 }" />
              <div v-else-if="widgetsData.active_tasks && widgetsData.active_tasks.length > 0" class="task-stream-container">
                <div 
                  v-for="(task, idx) in widgetsData.active_tasks" 
                  :key="idx" 
                  class="task-stream-item"
                  @click="router.push('/taskList')"
                >
                  <div class="task-item-top">
                    <span class="task-name" :title="task.name">{{ task.name }}</span>
                    <a-tag :color="getTaskTagColor(task.status)" class="task-status-tag">
                      <template #icon>
                        <SyncOutlined v-if="task.status === 'running'" spin />
                        <ClockCircleOutlined v-else-if="task.status === 'waiting'" />
                        <CheckCircleOutlined v-else />
                      </template>
                      {{ getTaskStatusLabel(task.status) }}
                    </a-tag>
                  </div>
                  <div class="task-item-bottom">
                    <span class="task-target" :title="task.target">目标: {{ task.target }}</span>
                    <span class="task-time">{{ task.start_time ? task.start_time.substring(5, 16) : '-' }}</span>
                  </div>
                </div>
              </div>
              <div v-else class="empty-widget-box">
                <a-empty description="暂无活动任务" :image="simpleImage">
                  <a-button type="primary" size="small" @click="router.push('/taskList')">新建侦察任务</a-button>
                </a-empty>
              </div>
            </div>
          </a-card>
        </a-col>
      </a-row>
    </div>

    <!-- 日志详情弹窗 -->
    <a-modal
      v-model:open="isLogModalVisible"
      title="系统动态详情"
      :footer="null"
      width="600px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
    >
      <div v-if="currentLog" class="log-detail-content">
        <p><strong>【级别】</strong> <a-tag :color="getLogColor(currentLog.level)">{{ currentLog.level }}</a-tag></p>
        <p><strong>【时间】</strong> {{ currentLog.create_time }}</p>
        <p><strong>【标题】</strong> {{ currentLog.title || (currentLog.level === 'error' ? '异常' : '通知') }}</p>
        <div style="margin-top: 16px;">
          <strong>【详细信息】</strong>
          <div class="log-message-box">
            {{ currentLog.message }}
          </div>
        </div>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
defineOptions({
  name: 'Dashboard'
});

import { ref, computed, onMounted, onUnmounted, onActivated, onDeactivated, nextTick } from 'vue';
import { useRouter } from 'vue-router';
import { 
  DatabaseOutlined, 
  SyncOutlined, 
  AlertOutlined, 
  GithubOutlined,
  LineChartOutlined,
  ClockCircleOutlined,
  TagsOutlined,
  PieChartOutlined,
  ThunderboltOutlined,
  RightOutlined,
  CheckCircleOutlined
} from '@ant-design/icons-vue';
import { Empty } from 'ant-design-vue';
import * as echarts from 'echarts/core';
import { LineChart, BarChart, PieChart } from 'echarts/charts';
import { TitleComponent, TooltipComponent, GridComponent, LegendComponent } from 'echarts/components';
import { CanvasRenderer } from 'echarts/renderers';

echarts.use([
  LineChart,
  BarChart,
  PieChart,
  TitleComponent,
  TooltipComponent,
  GridComponent,
  LegendComponent,
  CanvasRenderer
]);
import request from '@/utils/request';

const simpleImage = Empty.PRESENTED_IMAGE_SIMPLE;
const router = useRouter();

// 首次加载微光骨架屏标记
const initialLoading = ref(true);

const isDarkMode = ref(localStorage.getItem('darkMode') === 'true');

const chartRef = ref(null);
let myChart = null;
let lastTrendData = null;
let resizeObserver = null;

const vulnChartRef = ref(null);
let myVulnChart = null;
let vulnResizeObserver = null;

// 日志弹窗相关状态
const isLogModalVisible = ref(false);
const currentLog = ref(null);

const showLogDetail = (log) => {
  currentLog.value = log;
  isLogModalVisible.value = true;
};

// 响应式数据绑定
const stats = ref({
  total_assets: 0,
  today_tasks: 0,
  today_new_assets: 0,
  vuln: { arl_total: 0, nuclei_critical: 0, nuclei_high: 0, nuclei_medium: 0, nuclei_low: 0 },
  github_monitors: 0
});

const sysInfo = ref({
  cpu_percent: 0,
  mem_percent: 0,
  disk_percent: 0,
  tasks: { running: 0, waiting: 0 },
  github_today: { leaks: 0, intel: 0 },
  github_today_breakdown: { cves: 0, hackers: 0, general: 0 },
  github_totals: { cves: 0, tools: 0, hackers: 0 }
});

const widgetsData = ref({
  top_fingerprints: [],
  active_tasks: []
});

const logs = ref([]);

// 动态获取日志颜色
const getLogColor = (level) => {
  const map = {
    'info': 'blue',
    'success': 'green',
    'warning': 'orange',
    'error': 'red'
  };
  return map[level] || 'gray';
};

// 任务状态标签颜色与文案
const getTaskTagColor = (status) => {
  if (status === 'running') return 'processing';
  if (status === 'waiting') return 'warning';
  if (status === 'done') return 'success';
  if (status === 'error') return 'error';
  return 'default';
};

const getTaskStatusLabel = (status) => {
  const map = {
    'running': '执行中',
    'waiting': '等待中',
    'done': '已完成',
    'error': '异常',
    'stop': '已终止'
  };
  return map[status] || status || '未知';
};

// 指纹最大计数占比计算
const maxFingerCount = computed(() => {
  if (!widgetsData.value.top_fingerprints || widgetsData.value.top_fingerprints.length === 0) return 1;
  return Math.max(...widgetsData.value.top_fingerprints.map(x => x.count || 0), 1);
});

const getFingerPercent = (cnt) => {
  if (!cnt) return 0;
  return Math.min(Math.round((cnt / maxFingerCount.value) * 100), 100);
};

const colorToRgba = (color, opacity = 1) => {
  if (!color) return `rgba(24, 144, 255, ${opacity})`;
  const c = color.trim();
  if (c.startsWith('#')) {
    let hex = c.slice(1);
    if (hex.length === 3 || hex.length === 4) {
      hex = hex.slice(0, 3).split('').map(char => char + char).join('');
    } else if (hex.length >= 6) {
      hex = hex.slice(0, 6);
    }
    const r = parseInt(hex.substring(0, 2), 16) || 0;
    const g = parseInt(hex.substring(2, 4), 16) || 0;
    const b = parseInt(hex.substring(4, 6), 16) || 0;
    return `rgba(${r}, ${g}, ${b}, ${opacity})`;
  }
  if (c.startsWith('rgb(')) {
    return c.replace('rgb(', 'rgba(').replace(')', `, ${opacity})`);
  }
  if (c.startsWith('rgba(')) {
    return c.replace(/rgba\(([^,]+),([^,]+),([^,]+),[^)]+\)/, `rgba($1,$2,$3, ${opacity})`);
  }
  return c;
};

const handleDarkModeChange = (e) => {
  isDarkMode.value = typeof e?.detail === 'boolean' ? e.detail : (localStorage.getItem('darkMode') === 'true');
  nextTick(() => {
    renderTrendChart();
    renderVulnChart();
  });
};

const handleThemeChange = (e) => {
  const newColor = typeof e?.detail === 'string' ? e.detail : undefined;
  nextTick(() => {
    renderTrendChart(newColor);
    renderVulnChart();
  });
};

const fetchStats = async () => {
  try {
    const res = await request.get('/api/dashboard/stats');
    if (res.code === 200) {
      stats.value = res.data;
      renderVulnChart();
    }
  } catch (error) {
    console.error('Failed to fetch stats:', error);
  }
};

const fetchSysInfo = async () => {
  try {
    const res = await request.get('/api/dashboard/sysinfo');
    if (res.code === 200) {
      sysInfo.value = res.data;
    }
  } catch (error) {
    console.error('Failed to fetch sysinfo:', error);
  }
};

const fetchWidgetsData = async () => {
  try {
    const res = await request.get('/api/dashboard/widgets');
    if (res.code === 200) {
      widgetsData.value = res.data || { top_fingerprints: [], active_tasks: [] };
    }
  } catch (error) {
    console.error('Failed to fetch widgets data:', error);
  }
};

const fetchLogs = async () => {
  try {
    const res = await request.get('/api/dashboard/logs');
    if (res.code === 200) {
      logs.value = res.data.logs;
    }
  } catch (error) {
    console.error('Failed to fetch logs:', error);
  }
};

const renderTrendChart = (customColor) => {
  if (!chartRef.value) return;
  if (!myChart) {
    myChart = echarts.getInstanceByDom(chartRef.value) || echarts.init(chartRef.value);
  }
  if (!myChart || !lastTrendData) return;

  const days = lastTrendData.days || [];
  const assets = lastTrendData.assets || [];
  const vulns = lastTrendData.vulns || [];
  const leaks = lastTrendData.leaks || [];
  const cves = lastTrendData.cves || [];

  const themeColor = customColor || getComputedStyle(document.documentElement).getPropertyValue('--arl-theme-color').trim() || '#1890ff';
  const isDark = isDarkMode.value;

  const option = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { 
        type: 'line',
        lineStyle: { color: isDark ? 'rgba(255,255,255,0.15)' : 'rgba(0,0,0,0.12)', width: 1 }
      },
      backgroundColor: isDark ? 'rgba(17, 17, 17, 0.85)' : 'rgba(255, 255, 255, 0.9)',
      borderColor: isDark ? '#333333' : '#e2e8f0',
      textStyle: { color: isDark ? 'rgba(255, 255, 255, 0.85)' : '#333333', fontSize: 12 },
      extraCssText: 'backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px); border-radius: 8px; box-shadow: 0 6px 24px rgba(0,0,0,0.18);',
      padding: [10, 14]
    },
    legend: {
      data: ['新增站点', '漏洞', '代码泄露', 'CVE'],
      top: 0,
      textStyle: { color: isDark ? 'rgba(255, 255, 255, 0.75)' : '#555', fontWeight: 500, fontSize: 12 },
      itemGap: 16,
      itemWidth: 14,
      itemHeight: 10
    },
    grid: {
      left: 12,
      right: 12,
      bottom: 8,
      top: 36,
      containLabel: true
    },
    xAxis: [
      {
        type: 'category',
        data: days,
        axisLine: { show: false },
        axisTick: { show: false },
        axisLabel: { 
          color: isDark ? 'rgba(255, 255, 255, 0.45)' : '#888', 
          margin: 10,
          fontSize: 11
        }
      }
    ],
    yAxis: [
      {
        type: 'value',
        name: '站点数量',
        nameTextStyle: { color: isDark ? 'rgba(255, 255, 255, 0.45)' : '#888', padding: [0, 0, 0, 16], fontSize: 11 },
        axisLabel: { color: isDark ? 'rgba(255, 255, 255, 0.45)' : '#888', fontSize: 11 },
        minInterval: 1,
        splitLine: { 
          show: true,
          lineStyle: { color: isDark ? 'rgba(255, 255, 255, 0.05)' : 'rgba(0, 0, 0, 0.04)', type: 'dashed' }
        },
        axisLine: { show: false },
        axisTick: { show: false }
      },
      {
        type: 'value',
        name: '风险/事件数量',
        nameTextStyle: { color: isDark ? 'rgba(255, 255, 255, 0.45)' : '#888', padding: [0, 16, 0, 0], fontSize: 11 },
        axisLabel: { color: isDark ? 'rgba(255, 255, 255, 0.45)' : '#888', fontSize: 11 },
        minInterval: 1,
        splitLine: { show: false },
        axisLine: { show: false },
        axisTick: { show: false }
      }
    ],
    series: [
      {
        name: '新增站点',
        type: 'line',
        smooth: true,
        symbol: 'none',
        data: assets,
        itemStyle: { color: themeColor },
        lineStyle: { width: 2.5, color: themeColor },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: colorToRgba(themeColor, 0.25) },
            { offset: 1, color: colorToRgba(themeColor, 0.0) }
          ])
        }
      },
      {
        name: '漏洞',
        type: 'bar',
        yAxisIndex: 1,
        barMaxWidth: 10,
        itemStyle: { 
          color: isDark ? '#ff7875' : '#ff4d4f',
          borderRadius: [3, 3, 0, 0] 
        },
        data: vulns
      },
      {
        name: '代码泄露',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'none',
        data: leaks,
        itemStyle: { color: '#fa8c16' },
        lineStyle: { width: 2, type: 'dashed' }
      },
      {
        name: 'CVE',
        type: 'line',
        yAxisIndex: 1,
        smooth: true,
        symbol: 'none',
        data: cves,
        itemStyle: { color: isDark ? '#b37feb' : '#722ed1' },
        lineStyle: { width: 2 }
      }
    ]
  };
  
  myChart.setOption(option, true);
};

const renderVulnChart = () => {
  if (!vulnChartRef.value) return;
  if (!myVulnChart) {
    myVulnChart = echarts.getInstanceByDom(vulnChartRef.value) || echarts.init(vulnChartRef.value);
  }
  if (!myVulnChart) return;

  const v = stats.value.vuln || {};
  const dataList = [
    { value: v.nuclei_critical || 0, name: '严重', itemStyle: { color: '#e53935' }, tabKey: 'critical' },
    { value: v.nuclei_high || 0, name: '高危', itemStyle: { color: '#f4511e' }, tabKey: 'high' },
    { value: v.nuclei_medium || 0, name: '中危', itemStyle: { color: '#fb8c00' }, tabKey: 'medium' },
    { value: v.nuclei_low || 0, name: '低危', itemStyle: { color: '#1e88e5' }, tabKey: 'low' },
    { value: v.arl_total || 0, name: 'ARL内置', itemStyle: { color: '#8e24aa' }, tabKey: 'arl' }
  ];

  const totalVulns = dataList.reduce((acc, cur) => acc + cur.value, 0);
  const isDark = isDarkMode.value;

  const option = {
    tooltip: {
      trigger: 'item',
      backgroundColor: isDark ? 'rgba(17, 17, 17, 0.85)' : 'rgba(255, 255, 255, 0.9)',
      borderColor: isDark ? '#333333' : '#e2e8f0',
      textStyle: { color: isDark ? 'rgba(255, 255, 255, 0.85)' : '#333333', fontSize: 12 },
      formatter: '{b}: {c} 个 ({d}%)'
    },
    legend: {
      orient: 'vertical',
      right: '6%',
      top: 'center',
      itemWidth: 10,
      itemHeight: 10,
      itemGap: 8,
      textStyle: {
        color: isDark ? 'rgba(255, 255, 255, 0.75)' : '#555',
        fontSize: 11
      },
      formatter: (name) => {
        const item = dataList.find(d => d.name === name);
        return `${name}  ${item ? item.value : 0}`;
      }
    },
    series: [
      {
        name: '漏洞严重级别',
        type: 'pie',
        radius: ['52%', '75%'],
        center: ['38%', '50%'],
        avoidLabelOverlap: false,
        itemStyle: {
          borderRadius: 4,
          borderColor: isDark ? '#141414' : '#fff',
          borderWidth: 2
        },
        label: {
          show: true,
          position: 'center',
          formatter: () => `{total|${totalVulns}}\n{label|全库漏洞}`,
          rich: {
            total: {
              fontSize: 19,
              fontWeight: 600,
              color: isDark ? 'rgba(255,255,255,0.9)' : '#262626',
              lineHeight: 23
            },
            label: {
              fontSize: 11,
              color: isDark ? 'rgba(255,255,255,0.45)' : '#8c8c8c'
            }
          }
        },
        labelLine: { show: false },
        data: dataList
      }
    ]
  };

  myVulnChart.setOption(option, true);

  // 绑定扇区点击跳转
  myVulnChart.off('click');
  myVulnChart.on('click', (params) => {
    const item = dataList.find(d => d.name === params.name);
    if (!item) return;
    if (item.tabKey === 'arl') {
      router.push({ path: '/asset-search', query: { tab: 'vuln' } });
    } else {
      router.push({ path: '/asset-search', query: { tab: 'nuclei_result', vuln_severity: item.tabKey } });
    }
  });
};

const fetchTrendAndRender = async () => {
  try {
    const res = await request.get('/api/dashboard/trend');
    if (res.code === 200) {
      lastTrendData = res.data;
      await nextTick();
      renderTrendChart();
    }
  } catch (error) {
    console.error('Failed to fetch trend:', error);
  }
};

const initResizeObserver = () => {
  if (typeof ResizeObserver !== 'undefined' && chartRef.value) {
    if (resizeObserver) resizeObserver.disconnect();
    resizeObserver = new ResizeObserver(() => {
      if (myChart && chartRef.value && chartRef.value.clientWidth > 0 && chartRef.value.clientHeight > 0) {
        myChart.resize();
      }
    });
    resizeObserver.observe(chartRef.value);
  }

  if (typeof ResizeObserver !== 'undefined' && vulnChartRef.value) {
    if (vulnResizeObserver) vulnResizeObserver.disconnect();
    vulnResizeObserver = new ResizeObserver(() => {
      if (myVulnChart && vulnChartRef.value && vulnChartRef.value.clientWidth > 0 && vulnChartRef.value.clientHeight > 0) {
        myVulnChart.resize();
      }
    });
    vulnResizeObserver.observe(vulnChartRef.value);
  }
};

const fetchAllData = async (isInitial = false) => {
  if (isInitial) {
    initialLoading.value = true;
  }
  try {
    await Promise.allSettled([
      fetchStats(),
      fetchLogs(),
      fetchTrendAndRender(),
      fetchSysInfo(),
      fetchWidgetsData()
    ]);
  } finally {
    if (isInitial) {
      initialLoading.value = false;
      await nextTick();
      if (chartRef.value) {
        if (!myChart) myChart = echarts.getInstanceByDom(chartRef.value) || echarts.init(chartRef.value);
        if (lastTrendData) renderTrendChart();
      }
      if (vulnChartRef.value) {
        if (!myVulnChart) myVulnChart = echarts.getInstanceByDom(vulnChartRef.value) || echarts.init(vulnChartRef.value);
        renderVulnChart();
      }
      initResizeObserver();
      if (myChart && chartRef.value?.clientWidth > 0) myChart.resize();
      if (myVulnChart && vulnChartRef.value?.clientWidth > 0) myVulnChart.resize();
    }
  }
};

let sysInfoTimer = null;
let isFirstMounted = true;
const isPageActive = ref(false);

const startPolling = () => {
  stopPolling();
  sysInfoTimer = setInterval(() => {
    if (isPageActive.value && document.visibilityState === 'visible') {
      fetchSysInfo();
      fetchWidgetsData();
    }
  }, 5000);
};

const stopPolling = () => {
  if (sysInfoTimer) {
    clearInterval(sysInfoTimer);
    sysInfoTimer = null;
  }
};

const handleVisibilityChange = () => {
  if (isPageActive.value && document.visibilityState === 'visible') {
    fetchSysInfo();
    fetchWidgetsData();
    startPolling();
  } else {
    stopPolling();
  }
};

const handleResize = () => {
  if (myChart && chartRef.value?.clientWidth > 0) myChart.resize();
  if (myVulnChart && vulnChartRef.value?.clientWidth > 0) myVulnChart.resize();
};

onMounted(async () => {
  window.addEventListener('theme-changed', handleThemeChange);
  window.addEventListener('dark-mode-changed', handleDarkModeChange);
  window.addEventListener('resize', handleResize);
  document.addEventListener('visibilitychange', handleVisibilityChange);

  isPageActive.value = true;
  await fetchAllData(true);
  startPolling();
  isFirstMounted = false;
});

onActivated(() => {
  isPageActive.value = true;
  isDarkMode.value = localStorage.getItem('darkMode') === 'true';
  if (!isFirstMounted) {
    fetchAllData(false);
    startPolling();
  }
  nextTick(() => {
    if (chartRef.value) {
      if (!myChart) myChart = echarts.getInstanceByDom(chartRef.value) || echarts.init(chartRef.value);
      if (lastTrendData) renderTrendChart();
    }
    if (vulnChartRef.value) {
      if (!myVulnChart) myVulnChart = echarts.getInstanceByDom(vulnChartRef.value) || echarts.init(vulnChartRef.value);
      renderVulnChart();
    }
    initResizeObserver();
    if (myChart && chartRef.value?.clientWidth > 0) myChart.resize();
    if (myVulnChart && vulnChartRef.value?.clientWidth > 0) myVulnChart.resize();
  });
});

onDeactivated(() => {
  isPageActive.value = false;
  stopPolling();
  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (vulnResizeObserver) {
    vulnResizeObserver.disconnect();
    vulnResizeObserver = null;
  }
});

onUnmounted(() => {
  isPageActive.value = false;
  stopPolling();
  window.removeEventListener('theme-changed', handleThemeChange);
  window.removeEventListener('dark-mode-changed', handleDarkModeChange);
  window.removeEventListener('resize', handleResize);
  document.removeEventListener('visibilitychange', handleVisibilityChange);

  if (resizeObserver) {
    resizeObserver.disconnect();
    resizeObserver = null;
  }
  if (vulnResizeObserver) {
    vulnResizeObserver.disconnect();
    vulnResizeObserver = null;
  }

  if (myChart) {
    myChart.dispose();
    myChart = null;
  }
  if (myVulnChart) {
    myVulnChart.dispose();
    myVulnChart = null;
  }
});
</script>

<style scoped>
.dashboard-container {
  display: flex;
  flex-direction: column;
  box-sizing: border-box;
  padding: 16px;
  background: var(--arl-bg-layout);
  gap: 14px;
  min-height: 100%;
}

.dashboard-section {
  width: 100%;
}

.section-stats,
.section-sys {
  flex-shrink: 0;
}

.section-main {
  width: 100%;
}

.section-widgets {
  width: 100%;
}

.stat-row,
.main-row,
.widget-row {
  margin-left: -7px !important;
  margin-right: -7px !important;
  margin-top: 0 !important;
  margin-bottom: 0 !important;
  align-items: stretch;
}

.main-col,
.widget-col {
  display: flex;
  flex-direction: column;
}

/* ========================================================
   现代数据卡片 (Modern Stat Cards)
   ======================================================== */
.modern-stat-card {
  height: 100%;
  border-radius: 10px;
  transition: all 0.3s ease;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}
.modern-stat-card:hover {
  transform: translateY(-3px);
  box-shadow: 0 8px 20px rgba(0, 0, 0, 0.08);
}
.modern-stat-card :deep(.ant-card-body) {
  padding: 12px 14px;
  display: flex;
  align-items: center;
  height: 100%;
  box-sizing: border-box;
}

.clickable-card {
  cursor: pointer;
}

.stat-flex, .sys-flex {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 12px;
}
.sys-flex {
  justify-content: space-between;
}

.stat-icon-box {
  width: 44px;
  height: 44px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 20px;
  flex-shrink: 0;
}
.stat-icon-box.primary {
  background: rgba(24, 144, 255, 0.12);
  color: var(--arl-theme-color);
}
.stat-icon-box.success {
  background: rgba(82, 196, 26, 0.12);
  color: #52c41a;
}
.stat-icon-box.danger {
  background: rgba(245, 34, 45, 0.12);
  color: #f5222d;
}
.stat-icon-box.dark {
  background: var(--arl-border-color);
  color: var(--arl-text-color);
}

.stat-info, .sys-info {
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-width: 0;
}
.stat-label, .sys-label {
  font-size: 13px;
  color: var(--arl-text-color);
  opacity: 0.65;
  margin-bottom: 2px;
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.stat-value, .sys-value {
  font-size: 24px;
  font-weight: 600;
  color: var(--arl-text-color);
  line-height: 1.1;
}

/* 分割数值区域 (Split Values) */
.stat-split-values {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
}
.stat-split-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  cursor: pointer;
  padding: 2px 6px;
  border-radius: 4px;
  transition: background 0.2s;
  flex: 1;
}
.stat-split-item:hover {
  background: var(--arl-bg-light);
}
.stat-split-item .val {
  font-size: 16px;
  font-weight: 600;
  color: var(--arl-text-color);
  line-height: 1.2;
}
.stat-split-item .val.text-primary {
  color: var(--arl-theme-color);
}
.stat-split-item .sub-label {
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.45;
  white-space: nowrap;
}
.stat-divider {
  width: 1px;
  height: 20px;
  background: var(--arl-border-color);
  margin: 0 4px;
  flex-shrink: 0;
}

/* 漏洞分布条 (Vuln Bar) */
.stat-vuln-bar {
  display: flex;
  align-items: center;
  gap: 3px;
  margin-top: 2px;
}
.vuln-item {
  flex: 1;
  text-align: center;
  padding: 2px 3px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  cursor: pointer;
  transition: all 0.2s;
  line-height: 1.3;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.vuln-item:hover {
  transform: translateY(-1px);
  filter: brightness(1.1);
}
.vuln-item.critical { background: #e53935; }
.vuln-item.high { background: #f4511e; }
.vuln-item.medium { background: #fb8c00; }
.vuln-item.low { background: #1e88e5; }
.vuln-item.arl { background: #8e24aa; }

/* ========================================================
   主体卡片与联动布局 (Main Cards: Chart & Log)
   ======================================================== */
.main-card {
  height: 300px;
  display: flex;
  flex-direction: column;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.main-card :deep(.ant-card-head),
.widget-card :deep(.ant-card-head) {
  min-height: 42px;
  padding: 0 16px;
  border-bottom: 1px solid var(--arl-border-color);
  font-size: 14px;
  font-weight: 500;
  display: flex;
  align-items: center;
  flex-shrink: 0;
}

.main-card :deep(.ant-card-head-wrapper),
.widget-card :deep(.ant-card-head-wrapper) {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.main-card :deep(.ant-card-body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 10px 14px;
  overflow: hidden;
}

.card-header-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--arl-text-color);
}

.card-header-icon {
  color: var(--arl-theme-color);
  font-size: 16px;
}

.card-body-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  width: 100%;
  position: relative;
}

.echarts-box {
  width: 100%;
  height: 100%;
  min-height: 230px;
}

/* ========================================================
   系统日志展示 (Responsive System Logs)
   ======================================================== */
.log-badge-total {
  font-size: 12px;
  color: var(--arl-text-color);
  opacity: 0.5;
  font-weight: normal;
}

.log-scroll-area {
  flex: 1;
  min-height: 0;
  height: 100%;
  overflow-y: auto;
  overflow-x: hidden;
  padding-right: 4px;
}

/* 自定义纤细优雅半透明滚动条 */
.log-scroll-area::-webkit-scrollbar,
.task-stream-container::-webkit-scrollbar {
  width: 5px;
}
.log-scroll-area::-webkit-scrollbar-track,
.task-stream-container::-webkit-scrollbar-track {
  background: transparent;
}
.log-scroll-area::-webkit-scrollbar-thumb,
.task-stream-container::-webkit-scrollbar-thumb {
  background: var(--arl-border-color);
  border-radius: 4px;
  transition: background-color 0.2s;
}
.log-scroll-area::-webkit-scrollbar-thumb:hover,
.task-stream-container::-webkit-scrollbar-thumb:hover {
  background: var(--arl-theme-color);
}

.clickable-log {
  cursor: pointer;
  padding: 4px 6px;
  border-radius: 6px;
  transition: all 0.2s ease;
  margin-bottom: 0;
}
.clickable-log:hover {
  background-color: var(--arl-bg-light);
  transform: translateX(2px);
}
.clickable-log :deep(.ant-timeline-item-content) {
  margin-left: 20px;
  margin-bottom: 8px;
}

.log-item-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 2px;
}

.log-item-tag {
  font-size: 12px;
  font-weight: 600;
}
.log-item-tag.error { color: #f5222d; }
.log-item-tag.warning { color: #fa8c16; }
.log-item-tag.success { color: #52c41a; }
.log-item-tag.info { color: #1890ff; }

.log-item-time {
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.45;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace;
}

.log-item-msg {
  font-size: 12px;
  color: var(--arl-text-color);
  opacity: 0.8;
  line-height: 1.4;
  word-break: break-all;
}

.empty-log-box {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180px;
}

/* ========================================================
   Row 4: 拓展卡片样式 (Widgets: Fingerprint, Vuln Pie, Tasks)
   ======================================================== */
.widget-card {
  height: 245px;
  display: flex;
  flex-direction: column;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.widget-card :deep(.ant-card-body) {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  padding: 10px 14px;
  overflow: hidden;
}

.widget-extra-link {
  font-size: 12px;
  color: var(--arl-theme-color);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 2px;
  transition: opacity 0.2s;
}
.widget-extra-link:hover {
  opacity: 0.8;
  text-decoration: underline;
}

.widget-body-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  height: 100%;
  width: 100%;
  position: relative;
}

.echarts-widget-box {
  width: 100%;
  height: 100%;
  min-height: 175px;
}

.empty-widget-box {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 指纹列表 */
.finger-list-container {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding-top: 2px;
}

.finger-rank-item {
  display: flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  padding: 3px 6px;
  border-radius: 6px;
  transition: all 0.2s;
}
.finger-rank-item:hover {
  background-color: var(--arl-bg-light);
  transform: translateX(2px);
}

.finger-rank-left {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 0 1 auto;
  max-width: 130px;
  min-width: 85px;
  flex-shrink: 0;
}

.rank-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 50%;
  font-size: 11px;
  font-weight: 600;
  color: #fff;
  background: #bfbfbf;
  flex-shrink: 0;
}
.rank-badge.rank-1 { background: #ff4d4f; }
.rank-badge.rank-2 { background: #fa8c16; }
.rank-badge.rank-3 { background: #faad14; }

.finger-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--arl-text-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.finger-rank-bar-wrap {
  flex: 1;
  min-width: 0;
}

.finger-progress-bar {
  height: 6px;
  background: var(--arl-border-color);
  border-radius: 3px;
  overflow: hidden;
}

.finger-progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--arl-theme-color) 0%, rgba(24, 144, 255, 0.4) 100%);
  border-radius: 3px;
  transition: width 0.4s ease;
}

.finger-rank-count {
  font-size: 12px;
  color: var(--arl-text-color);
  opacity: 0.7;
  width: 58px;
  text-align: right;
  flex-shrink: 0;
  font-weight: 500;
}

/* 实时任务流 */
.task-stream-container {
  flex: 1;
  min-height: 0;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-stream-item {
  padding: 6px 8px;
  border-radius: 6px;
  background: var(--arl-bg-light);
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}
.task-stream-item:hover {
  border-color: var(--arl-theme-color);
  transform: translateY(-1px);
}

.task-item-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  margin-bottom: 2px;
}

.task-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--arl-text-color);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}

.task-status-tag {
  margin-right: 0;
  font-size: 11px;
  padding: 0 4px;
}

.task-item-bottom {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 11px;
  color: var(--arl-text-color);
  opacity: 0.55;
}

.task-target {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.task-time {
  flex-shrink: 0;
  margin-left: 8px;
}

.log-message-box {
  margin-top: 8px;
  padding: 12px;
  background-color: var(--arl-bg-light);
  border-radius: 6px;
  font-family: monospace;
  white-space: pre-wrap;
  word-wrap: break-word;
  color: var(--arl-text-color);
  border: 1px solid var(--arl-border-color);
}

@media (max-width: 991px) {
  .main-row,
  .widget-row {
    flex-direction: column;
    gap: 14px;
  }
  .main-col,
  .widget-col {
    width: 100%;
  }
  .main-card,
  .widget-card {
    height: auto;
    min-height: 245px;
  }
}
</style>
