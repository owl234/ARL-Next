<template>
  <div style="background-color: #fff; padding: 24px; min-height: calc(100vh - 64px);">
    <a-page-header
      :title="`任务名: ${taskName || taskId}`"
      @back="() => router.back()"
      style="padding: 0 0 24px 0;"
    />

    <a-tabs v-model:activeKey="activeTab" type="card" class="arl-detail-tabs" @change="onTabChange">
      <a-tab-pane key="web" :tab="`网站备案 - ${queryCounts.web}`"></a-tab-pane>
      <a-tab-pane key="app" :tab="`APP - ${queryCounts.app}`"></a-tab-pane>
      <a-tab-pane key="mapp" :tab="`小程序 - ${queryCounts.mapp}`"></a-tab-pane>
      <a-tab-pane key="kapp" :tab="`快应用 - ${queryCounts.kapp}`"></a-tab-pane>
      <a-tab-pane key="invest" :tab="`对外投资 - ${queryCounts.invest}`"></a-tab-pane>
      <a-tab-pane key="trademark" :tab="`商标信息 - ${queryCounts.trademark}`"></a-tab-pane>
      <a-tab-pane key="wechat" :tab="`公众号 - ${queryCounts.wechat}`"></a-tab-pane>
      <a-tab-pane key="weibo" :tab="`微博 - ${queryCounts.weibo}`"></a-tab-pane>
      <a-tab-pane key="log" tab="运行日志"></a-tab-pane>
    </a-tabs>

    <div v-show="activeTab !== 'log'">
      <div style="margin-bottom: 16px;">
      <a-form :model="searchForm" layout="inline" style="row-gap: 16px;">
        <template v-for="col in dynamicColumns" :key="col.key">
          <a-form-item v-if="col.key !== 'raw' && col.key !== 'icon' && col.key !== 'examineDate'" :label="col.title + ':'">
            <a-input-group compact v-if="['regCapital', 'percent'].includes(col.dataIndex)">
              <a-select v-model:value="searchFormOp[col.dataIndex]" style="width: 70px" :options="[{value:'eq',label:'='},{value:'gt',label:'>'},{value:'lt',label:'<'}]" />
              <a-input-number v-model:value="searchForm[col.dataIndex]" style="width: 130px" :placeholder="'输入' + col.title" @pressEnter="onSearch" />
            </a-input-group>
            <a-input v-else v-model:value="searchForm[col.dataIndex]" :placeholder="'请输入' + col.title" style="width: 180px;" allowClear @pressEnter="onSearch">
              <template #suffix><search-outlined @click="onSearch" style="color: rgba(0,0,0,.25); cursor: pointer;"/></template>
            </a-input>
          </a-form-item>
        </template>
      </a-form>
    </div>

    <a-table
        :dataSource="assetList"
        :columns="dynamicColumns"
        :loading="loading"
        :pagination="false"
        :scroll="{ x: 'max-content' }"
        :rowKey="(record) => record._id || record.id || Math.random()"
        bordered
        style="margin-bottom: 16px;"
    >
        <template #bodyCell="{ column, record, text }">
          <template v-if="column.key === 'icon'">
            <img v-if="text" :src="text" style="width:32px;height:32px;border-radius:4px;" />
          </template>
          <template v-else-if="column.key === 'brief' || column.key === 'recommend'">
            <div style="max-width: 300px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;" :title="text">
              {{ text || '-' }}
            </div>
          </template>
          <template v-else-if="column.key === 'raw'">
            <a-popover title="原始数据" trigger="click" placement="left">
              <template #content>
                <div style="max-width: 400px; max-height: 400px; overflow: auto;">
                  <pre style="font-size: 12px;">{{ JSON.stringify(record, null, 2) }}</pre>
                </div>
              </template>
              <a-button type="link" size="small">查看JSON</a-button>
            </a-popover>
          </template>
          <template v-else>
            {{ text || '-' }}
          </template>
        </template>
    </a-table>

      <div style="display: flex; justify-content: space-between; align-items: center; padding: 0 16px;">
        <div style="color: rgba(0,0,0,.65);">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
        <a-pagination v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" @showSizeChange="handleTableChange" />
      </div>
    </div>

    <div v-show="activeTab === 'log'">
      <div style="border: 1px solid #e8e8e8; border-radius: 4px; padding: 8px; background-color: #fafafa;">
        <div style="background-color: #001529; color: #e6f7ff; font-family: 'Fira Code', Consolas, 'Courier New', monospace; padding: 16px; border-radius: 4px; height: 60vh; overflow-y: auto; font-size: 13px; line-height: 1.6; box-shadow: inset 0 2px 8px rgba(0,0,0,0.2);">
          <div v-for="(log, idx) in syslogList" :key="idx" style="margin-bottom: 6px; word-break: break-all; border-bottom: 1px dashed rgba(255,255,255,0.1); padding-bottom: 4px;">
            <span style="color: #00bcd4; margin-right: 8px;">[{{ log.create_time }}]</span>
            <span :style="{ color: log.level === 'error' ? '#ff4d4f' : log.level === 'warning' ? '#faad14' : '#52c41a', fontWeight: 'bold', marginRight: '8px' }">[{{ (log.level || 'info').toUpperCase() }}]</span>
            <span style="color: #1890ff; margin-right: 8px;">[{{ log.title }}]</span>
            <span style="color: #e6f7ff;">{{ log.message }}</span>
          </div>
          <div v-if="syslogList.length === 0" style="color: rgba(255,255,255,0.45); font-style: italic;">[System] 暂无日志记录... (等待日志生成或当前为历史遗留任务)</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { SearchOutlined } from '@ant-design/icons-vue';
import request from '../utils/request';

const route = useRoute();
const router = useRouter();
const query = route.query || {};

const taskId = query.task_id;
const taskName = query.name;

const activeTab = ref('web');
const queryCounts = reactive({
  web: Number(query.web_cnt) || 0,
  app: Number(query.app_cnt) || 0,
  mapp: Number(query.mapp_cnt) || 0,
  kapp: Number(query.kapp_cnt) || 0,
  invest: Number(query.invest_cnt) || 0,
  trademark: Number(query.trademark_cnt) || 0,
  wechat: Number(query.wechat_cnt) || 0,
  weibo: Number(query.weibo_cnt) || 0,
});

const assetList = ref([]);
const loading = ref(false);
const pagination = reactive({ current: 1, pageSize: 10, total: 0 });

const syslogList = ref([]);
let syslogTimer = null;

import { computed } from 'vue';

const webColumns = [
  { title: '主办单位名称', dataIndex: 'companyName', key: 'companyName', width: 220 },
  { title: '单位性质', dataIndex: 'companyType', key: 'companyType', width: 120 },
  { title: '主备案号', dataIndex: 'liscense', key: 'liscense', width: 180 },
  { title: '域名', dataIndex: 'ym', key: 'ym', width: 200 },
  { title: '网站名称', dataIndex: 'webName', key: 'webName', width: 200 },
  { title: '审核日期', dataIndex: 'examineDate', key: 'examineDate', width: 120 },
  { title: '详情', key: 'raw', width: 80 }
];


const mappColumns = [
  { title: '小程序名称', dataIndex: 'serviceName', key: 'serviceName', width: 200 },
  { title: '备案号', dataIndex: 'serviceFilingNumber', key: 'serviceFilingNumber', width: 200 },
  { title: '审核日期', dataIndex: 'examineDate', key: 'examineDate', width: 120 },
  { title: '详情', key: 'raw', width: 80 }
];

const appColumns = [
  { title: '图标', dataIndex: 'icon', key: 'icon', width: 60 },
  { title: 'APP名称', dataIndex: 'name', key: 'name', width: 150 },
  { title: '分类', dataIndex: 'classes', key: 'classes', width: 100 },
  { title: '应用类型', dataIndex: 'type', key: 'type', width: 100 },
  { title: '简介', dataIndex: 'brief', key: 'brief', width: 300, ellipsis: true },
  { title: '详情', key: 'raw', width: 80 }
];

const investColumns = [
  { title: '投资公司名称', dataIndex: 'name', key: 'name', width: 220 },
  { title: '法定代表人', dataIndex: 'legalPersonName', key: 'legalPersonName', width: 120 },
  { title: '注册资本', dataIndex: 'regCapital', key: 'regCapital', width: 120 },
  { title: '投资比例', dataIndex: 'percent', key: 'percent', width: 100 },
  { title: '详情', key: 'raw', width: 80 }
];

const trademarkColumns = [
  { title: '商标名称', dataIndex: 'tmName', key: 'tmName', width: 180 },
  { title: '注册号', dataIndex: 'regNo', key: 'regNo', width: 150 },
  { title: '分类', dataIndex: 'intCls', key: 'intCls', width: 80 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 120 },
  { title: '详情', key: 'raw', width: 80 }
];

const wechatColumns = [
  { title: '头像', dataIndex: 'titleImgURL', key: 'icon', width: 60 },
  { title: '公众号名称', dataIndex: 'title', key: 'title', width: 200 },
  { title: '微信号', dataIndex: 'publicNum', key: 'publicNum', width: 150 },
  { title: '简介', dataIndex: 'recommend', key: 'recommend', width: 300, ellipsis: true },
  { title: '详情', key: 'raw', width: 80 }
];

const weiboColumns = [
  { title: '微博名称', dataIndex: 'name', key: 'name', width: 200 },
  { title: '微博链接', dataIndex: 'href', key: 'href', width: 250 },
  { title: '详情', key: 'raw', width: 80 }
];

const baseIcpColumns = [
  { title: '主办单位名称', dataIndex: 'unitName', key: 'unitName', width: 220 },
  { title: '单位性质', dataIndex: 'natureName', key: 'natureName', width: 120 },
  { title: '主备案号', dataIndex: 'mainLicence', key: 'mainLicence', width: 180 },
  { title: '域名', dataIndex: 'domain', key: 'domain', width: 200 },
  { title: '网站名称', dataIndex: 'serviceName', key: 'serviceName', width: 200 },
  { title: '详情', key: 'raw', width: 80 }
];

const genericColumns = [
  { title: '名称', dataIndex: 'filterName', key: 'filterName', width: 200 },
  { title: '详情', key: 'raw', width: 80 }
];

const dynamicColumns = computed(() => {
  const isTyc = query.task_type === 'tyc';
  if (activeTab.value === 'invest') return investColumns;
  if (activeTab.value === 'trademark') return trademarkColumns;
  if (activeTab.value === 'wechat') return wechatColumns;
  if (activeTab.value === 'weibo') return weiboColumns;

  if (isTyc) {
    if (activeTab.value === 'web') return webColumns;
    if (activeTab.value === 'mapp') return mappColumns;
    if (activeTab.value === 'app') return appColumns;
  } else {
    if (['web', 'app', 'mapp', 'kapp'].includes(activeTab.value)) return baseIcpColumns;
  }

  return genericColumns;
});

const searchForm = reactive({});
const searchFormOp = reactive({});

const hasActiveSearch = () => {
  return Object.values(searchForm).some((val) => val !== undefined && val !== null && val !== '');
};

const fetchAssets = async (page = 1, size = 10) => {
  loading.value = true;
  try {
    const queryParams = { page, size, task_id: taskId, query_type: activeTab.value };
    for (const [key, val] of Object.entries(searchForm)) {
      if (val !== undefined && val !== null && val !== '') {
        if (['regCapital', 'percent'].includes(key)) {
          const op = searchFormOp[key] || 'eq';
          const fieldName = key + '_num';
          if (op === 'gt') queryParams[`${fieldName}__ngt`] = val;
          else if (op === 'lt') queryParams[`${fieldName}__nlt`] = val;
          else queryParams[fieldName] = val;
        } else {
          queryParams[key] = val;
        }
      }
    }

    const res = await request.get('/icp/asset', { params: queryParams });
    if (res.code === 200) {
      assetList.value = res.items || [];
      pagination.total = res.total || 0;
      pagination.current = page;
      pagination.pageSize = size;
      if (!hasActiveSearch() && Object.prototype.hasOwnProperty.call(queryCounts, activeTab.value)) {
        queryCounts[activeTab.value] = pagination.total;
      }
    } else {
      console.error('获取资产列表失败:', res);
    }
  } catch (error) {
    console.error('API 请求失败:', error);
  } finally {
    loading.value = false;
  }
};

const onSearch = () => fetchAssets(1, pagination.pageSize);
const handleTableChange = (page, pageSize) => fetchAssets(page, pageSize);

const fetchSyslog = async () => {
  try {
    const res = await request.get('/syslog/', { params: { task_id: taskId, size: 500, order: 'create_time' } });
    if (res.code === 200) {
      syslogList.value = res.items || [];
    }
  } catch (error) {
    console.error('获取日志失败:', error);
  }
};

const stopSyslogTimer = () => {
  if (syslogTimer) {
    clearInterval(syslogTimer);
    syslogTimer = null;
  }
};

const onTabChange = (key) => {
  for (const k of Object.keys(searchForm)) {
    delete searchForm[k];
  }
  for (const k of Object.keys(searchFormOp)) {
    delete searchFormOp[k];
  }

  if (key === 'invest') {
    searchFormOp['regCapital'] = 'eq';
    searchFormOp['percent'] = 'eq';
  }

  if (key === 'log') {
    fetchSyslog();
    if (!syslogTimer) {
      syslogTimer = setInterval(fetchSyslog, 5000);
    }
  } else {
    stopSyslogTimer();
    assetList.value = [];
    fetchAssets(1, 10);
  }
};

onMounted(() => {
  if (taskId) {
    fetchAssets(pagination.current, pagination.pageSize);
  }
});

onUnmounted(() => {
  if (syslogTimer) {
    clearInterval(syslogTimer);
  }
});
</script>
