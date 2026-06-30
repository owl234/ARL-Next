<template>
  <div class="dashboard-container">
    <!-- 顶部数据统计卡片 -->
    <a-row :gutter="16" class="stat-row">
      <a-col :span="6">
        <a-card class="clickable-card" @click="router.push('/asset-search')">
          <a-statistic title="总资产数量" :value="stats.total_assets" style="margin-right: 50px">
            <template #prefix>
              <DatabaseOutlined style="color: #1890ff" />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="clickable-card" :bodyStyle="{ padding: '16px 20px' }" @click="router.push('/taskList')">
          <div style="font-size: 14px; color: rgba(0, 0, 0, 0.45); margin-bottom: 8px;">
            <SyncOutlined style="color: #52c41a; margin-right: 4px;" /> 今日动态
          </div>
          <div style="display: flex; justify-content: space-around; align-items: flex-end; margin-top: 4px;">
            <div style="text-align: center;">
              <div style="font-size: 20px; color: #333; font-weight: 500;">{{ stats.today_tasks }}</div>
              <div style="font-size: 12px; color: #999;">新增任务</div>
            </div>
            <div style="text-align: center;">
              <div style="font-size: 20px; color: #1890ff; font-weight: 500;">{{ stats.today_new_assets }}</div>
              <div style="font-size: 12px; color: #999;">新增资产</div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="clickable-card" :bodyStyle="{ padding: '16px 20px' }" @click="router.push('/pocList')">
          <div style="font-size: 14px; color: rgba(0, 0, 0, 0.45); margin-bottom: 8px;">
            <AlertOutlined style="color: #f5222d; margin-right: 4px;" /> 发现的漏洞 (PoC)
          </div>
          <div style="display: flex; justify-content: space-between; align-items: flex-end; margin-top: 4px;">
            <div style="text-align: center;">
              <div style="font-size: 20px; color: #820014; font-weight: 500;">{{ stats.vuln.critical }}</div>
              <div style="font-size: 12px; color: #999;">严重</div>
            </div>
            <div style="text-align: center;">
              <div style="font-size: 20px; color: #cf1322; font-weight: 500;">{{ stats.vuln.high }}</div>
              <div style="font-size: 12px; color: #999;">高危</div>
            </div>
            <div style="text-align: center;">
              <div style="font-size: 20px; color: #d46b08; font-weight: 500;">{{ stats.vuln.medium }}</div>
              <div style="font-size: 12px; color: #999;">中危</div>
            </div>
            <div style="text-align: center;">
              <div style="font-size: 20px; color: #096dd9; font-weight: 500;">{{ stats.vuln.low }}</div>
              <div style="font-size: 12px; color: #999;">低危</div>
            </div>
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card class="clickable-card" @click="router.push('/GitHubTasks/GitHubTasksList')">
          <a-statistic title="GitHub监控仓库" :value="stats.github_monitors">
            <template #prefix>
              <GithubOutlined style="color: #333" />
            </template>
          </a-statistic>
        </a-card>
      </a-col>
    </a-row>


    <!-- 系统状态区域 -->
    <a-row :gutter="16" style="margin-top: 16px;">
      <a-col :span="6">
        <a-card title="CPU 占用" style="height: 100%;">
          <div style="text-align: center; padding-top: 16px;">
            <a-progress type="dashboard" :percent="sysInfo.cpu_percent" :status="sysInfo.cpu_percent > 80 ? 'exception' : 'normal'" />
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card title="内存占用" style="height: 100%;">
          <div style="text-align: center; padding-top: 16px;">
            <a-progress type="dashboard" :percent="sysInfo.mem_percent" :strokeColor="sysInfo.mem_percent > 80 ? '#ff4d4f' : '#1890ff'" />
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card title="磁盘占用" style="height: 100%;">
          <div style="text-align: center; padding-top: 16px;">
            <a-progress type="dashboard" :percent="sysInfo.disk_percent" :strokeColor="sysInfo.disk_percent > 90 ? '#ff4d4f' : '#52c41a'" />
          </div>
        </a-card>
      </a-col>
      <a-col :span="6">
        <a-card title="后台任务 (Celery)" style="height: 100%;">
          <div style="display: flex; justify-content: space-around; padding-top: 24px;">
            <div style="text-align: center;">
              <div style="font-size: 24px; color: #52c41a; font-weight: 500;">{{ sysInfo.tasks.running }}</div>
              <div style="font-size: 14px; color: #999;">运行中</div>
            </div>
            <div style="text-align: center;">
              <div style="font-size: 24px; color: #faad14; font-weight: 500;">{{ sysInfo.tasks.waiting }}</div>
              <div style="font-size: 14px; color: #999;">等待中</div>
            </div>
          </div>
        </a-card>
      </a-col>
    </a-row>

    <!-- 主体区域 -->
    <a-row :gutter="16" style="margin-top: 16px;">
      <!-- 左侧：趋势图表区域 -->
      <a-col :span="16">
        <a-card title="近7天资产与风险趋势" style="height: 100%;">
          <div ref="chartRef" style="width: 100%; height: 300px;"></div>
        </a-card>
      </a-col>

      <!-- 右侧：最新动态 (Log 展示) -->
      <a-col :span="8">
        <a-card title="最新系统动态 (Log)" style="height: 100%;">
          <a-timeline>
            <a-timeline-item 
              v-for="(log, index) in logs" 
              :key="index" 
              :color="getLogColor(log.level)"
              class="clickable-log"
              @click="showLogDetail(log)">
              <p>
                <strong>[{{ log.title || (log.level === 'error' ? '异常' : '通知') }}]</strong> 
                {{ log.create_time }}
              </p>
              <p>{{ log.message }}</p>
            </a-timeline-item>
            <a-empty v-if="logs.length === 0" description="暂无系统动态" />
          </a-timeline>
        </a-card>
      </a-col>
    </a-row>

    <!-- 日志详情弹窗 -->
    <a-modal
      v-model:visible="isLogModalVisible"
      title="系统动态详情"
      :footer="null"
      width="600px"
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
import { ref, onMounted, onUnmounted } from 'vue';
import { useRouter } from 'vue-router';
import { 
  DatabaseOutlined, 
  SyncOutlined, 
  AlertOutlined, 
  GithubOutlined 
} from '@ant-design/icons-vue';
import * as echarts from 'echarts';
import request from '@/utils/request';

const router = useRouter();
const chartRef = ref(null);
let myChart = null;

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
  vuln: { critical: 0, high: 0, medium: 0, low: 0 },
  github_monitors: 0
});

const sysInfo = ref({
  cpu_percent: 0,
  mem_percent: 0,
  disk_percent: 0,
  tasks: { running: 0, waiting: 0 }
});

const logs = ref([]);

// 动态获取颜色
const getLogColor = (level) => {
  const map = {
    'info': 'blue',
    'success': 'green',
    'warning': 'orange',
    'error': 'red'
  };
  return map[level] || 'gray';
};

const fetchStats = async () => {
  try {
    const res = await request.get('/api/dashboard/stats');
    if (res.code === 200) {
      stats.value = res.data;
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

const fetchTrendAndRender = async () => {
  try {
    const res = await request.get('/api/dashboard/trend');
    if (res.code === 200 && myChart) {
      const { days, assets, vulns } = res.data;
      
      const option = {
        tooltip: {
          trigger: 'axis',
          axisPointer: { 
            type: 'cross',
            crossStyle: { color: '#999' }
          },
          backgroundColor: 'rgba(255, 255, 255, 0.9)',
          borderColor: '#eee',
          textStyle: { color: '#333' }
        },
        legend: {
          data: ['新增资产', '高危漏洞'],
          top: 0
        },
        grid: {
          left: '3%',
          right: '4%',
          bottom: '3%',
          top: '15%',
          containLabel: true
        },
        xAxis: [
          {
            type: 'category',
            data: days,
            axisPointer: { type: 'shadow' },
            axisLine: { lineStyle: { color: '#d9d9d9' } },
            axisLabel: { color: '#666' }
          }
        ],
        yAxis: [
          {
            type: 'value',
            name: '资产数量',
            nameTextStyle: { color: '#666', padding: [0, 0, 0, 20] },
            axisLabel: { color: '#666' },
            splitLine: { lineStyle: { type: 'dashed', color: '#f0f0f0' } }
          },
          {
            type: 'value',
            name: '漏洞数量',
            nameTextStyle: { color: '#666', padding: [0, 20, 0, 0] },
            axisLabel: { color: '#666' },
            splitLine: { show: false } 
          }
        ],
        series: [
          {
            name: '新增资产',
            type: 'line',
            smooth: true,
            symbolSize: 8,
            data: assets,
            itemStyle: { color: '#1890ff' },
            lineStyle: { width: 3, shadowColor: 'rgba(24,144,255,0.3)', shadowBlur: 10, shadowOffsetY: 5 },
            areaStyle: {
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(24,144,255,0.4)' },
                { offset: 1, color: 'rgba(24,144,255,0.05)' }
              ])
            }
          },
          {
            name: '高危漏洞',
            type: 'bar',
            yAxisIndex: 1,
            barMaxWidth: 20,
            itemStyle: { 
              color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: '#ff4d4f' },
                { offset: 1, color: '#cf1322' }
              ]),
              borderRadius: [4, 4, 0, 0] 
            },
            data: vulns
          }
        ]
      };
      
      myChart.setOption(option);
    }
  } catch (error) {
    console.error('Failed to fetch trend:', error);
  }
};

let sysInfoTimer = null;

onMounted(() => {
  if (chartRef.value) {
    myChart = echarts.init(chartRef.value);
    
    const handleResize = () => {
      myChart.resize();
    };
    window.addEventListener('resize', handleResize);
    myChart.__resizeHandler = handleResize;
  }
  
  // 并发请求所有数据
  Promise.all([
    fetchStats(),
    fetchLogs(),
    fetchTrendAndRender(),
    fetchSysInfo()
  ]);
  
  // 每 5 秒自动刷新一次系统状态
  sysInfoTimer = setInterval(() => {
    fetchSysInfo();
  }, 5000);
});

onUnmounted(() => {
  if (sysInfoTimer) clearInterval(sysInfoTimer);
  
  if (myChart) {
    if (myChart.__resizeHandler) {
      window.removeEventListener('resize', myChart.__resizeHandler);
    }
    myChart.dispose();
  }
});
</script>

<style scoped>
.dashboard-container {
  padding: 16px;
  background: #f0f2f5;
  min-height: calc(100vh - 64px - 48px);
}
.stat-row .ant-card {
  border-radius: 8px;
  box-shadow: 0 1px 2px -2px rgba(0,0,0,.16), 0 3px 6px 0 rgba(0,0,0,.12), 0 5px 12px 4px rgba(0,0,0,.09);
  transition: all 0.3s ease;
}
.stat-row .clickable-card {
  cursor: pointer;
}
.stat-row .clickable-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 4px 8px -2px rgba(0,0,0,.16), 0 8px 16px 0 rgba(0,0,0,.12), 0 12px 24px 4px rgba(0,0,0,.09);
}
.clickable-log {
  cursor: pointer;
  padding: 8px;
  border-radius: 4px;
  transition: background-color 0.3s;
}
.clickable-log:hover {
  background-color: rgba(0, 0, 0, 0.02);
}
.log-message-box {
  margin-top: 8px;
  padding: 12px;
  background-color: #f5f5f5;
  border-radius: 4px;
  font-family: monospace;
  white-space: pre-wrap;
  word-wrap: break-word;
  color: #333;
}
</style>
