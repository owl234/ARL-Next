<template>
  <div style="background-color: #fff; padding: 24px; min-height: calc(100vh - 64px);">
    <div style="margin-bottom: 24px; display: flex; gap: 8px;">
      <a-button type="primary" style="background-color: #00bcd4; border-color: #00bcd4;" @click="goToDetail">新建策略</a-button>
      <a-popconfirm
          title="确认批量删除选中的数据吗？"
          ok-text="确认"
          cancel-text="取消"
          @confirm="handleBatchDelete"
          :disabled="selectedRowKeys.length === 0"
      >
        <a-button danger :disabled="selectedRowKeys.length === 0">批量删除</a-button>
      </a-popconfirm>
    </div>

    <div class="search-row" style="margin-bottom: 16px;">
      <div class="search-item">
        <span class="label">策略名称：</span>
        <a-input v-model:value="searchForm.name" placeholder="请输入策略名称进行搜索" style="width: 220px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
        </a-input>
      </div>
    </div>

    <a-table :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: keys => selectedRowKeys = keys }" :loading="loading" :dataSource="dataSource" :columns="columns" :pagination="false" size="middle" :rowKey="(record) => record._id">
      <template #bodyCell="{ column, record, index }">
        <template v-if="column.key === 'index'"><span>{{ (pagination.current - 1) * pagination.pageSize + index + 1 }}</span></template>

        <template v-else-if="column.key === 'action'">
          <div style="display: flex; gap: 8px;">
            <a-button size="small" @click="openDispatchModal(record)">任务下发</a-button>
            <a-button size="small" @click="router.push({ path: '/policyDetail', query: { _id: record._id } })">编辑</a-button>
            <a-popconfirm
                title="确认删除所选数据吗？"
                ok-text="确认"
                cancel-text="取消"
                @confirm="handleDelete(record)"
            >
              <a-button size="small" danger>删除</a-button>
            </a-popconfirm>
          </div>
        </template>
      </template>

      <template #expandedRowRender="{ record }">
        <div class="policy-expanded-box">
          <div class="policy-section">
            <div class="policy-title">域名和IP配置</div>
            <div class="policy-row"><span class="policy-label">域名爆破类型</span><span class="policy-val">{{ getDictName(record.policy?.domain_config?.domain_brute_type) }}</span></div>
            <div class="policy-row"><span class="policy-label">端口扫描类型</span><span class="policy-val">{{ getDictName(record.policy?.ip_config?.port_scan_type) }}</span></div>
            <div class="policy-row"><span class="policy-label">配置信息</span><span class="policy-val">{{ getDomainIpConfigText(record.policy) }}</span></div>
          </div>
          <div class="policy-divider"></div>
          <div class="policy-section">
            <div class="policy-title">站点和风险配置</div>
            <div class="policy-row"><span class="policy-label">配置信息</span><span class="policy-val">{{ getSiteRiskConfigText(record.policy) }}</span></div>
          </div>
          <div class="policy-divider"></div>
          <div class="policy-section">
            <div class="policy-title">PoC配置</div>
            <div class="policy-row"><span class="policy-label">配置信息</span><span class="policy-val">{{ getPocConfigText(record.policy) }}</span></div>
          </div>
          <div class="policy-divider"></div>
          <div class="policy-section">
            <div class="policy-title">弱口令爆破配置</div>
            <div class="policy-row"><span class="policy-label">配置信息</span><span class="policy-val">{{ getBruteConfigText(record.policy) }}</span></div>
          </div>
        </div>
      </template>
    </a-table>

    <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
      <div style="color: rgba(0,0,0,.65);">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
      <a-pagination v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" />
    </div>
  </div>

  <a-modal
      v-model:open="dispatchModalVisible"
      title="任务下发"
      @ok="submitDispatch"
      :confirmLoading="dispatchLoading"
      width="520px"
      okText="确 定"
      cancelText="取 消"
      destroyOnClose
  >
    <a-form :model="dispatchForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">
      <a-form-item label="任务类型" required>
        <a-select v-model:value="dispatchForm.task_tag" @change="onTaskTagChange">
          <a-select-option value="task">资产侦查任务</a-select-option>
          <a-select-option value="risk_cruising">风险巡航任务</a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item label="任务名称" required>
        <a-input v-model:value="dispatchForm.name" placeholder="请输入任务名称" />
      </a-form-item>

      <a-form-item label="目标" required>
        <a-textarea v-model:value="dispatchForm.target" :rows="4" placeholder="请输入目标IP或域名，多个请换行" />
      </a-form-item>
    </a-form>
  </a-modal>

</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import { useRouter } from 'vue-router'; // 引入路由
import request from '../utils/request';
import { message } from 'ant-design-vue';
import { SearchOutlined } from '@ant-design/icons-vue';

const router = useRouter(); // 实例化路由
const loading = ref(false);
const dataSource = ref([]);
const searchForm = ref({});
const pagination = reactive({ current: 1, pageSize: 10, total: 0 });
const selectedRowKeys = ref([]);

const columns = [
  { title: '序号', key: 'index', width: 80, align: 'center' },
  { title: '名称', dataIndex: 'name', key: 'name', width: 250 },
  { title: '描述', dataIndex: 'desc', key: 'desc', width: 300 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 200 },
  { title: '操作', key: 'action', width: 250 }
];

const fetchData = async () => {
  loading.value = true;
  try {
    const params = { page: pagination.current, size: pagination.pageSize, order: '-update_date' };
    if (searchForm.value.name) params.name = searchForm.value.name;
    const res = await request.get('/policy/', { params });
    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
    }
  } catch (error) { message.error('加载策略数据失败'); } finally { loading.value = false; }
};

const onSearch = () => { pagination.current = 1; fetchData(); };
const handleTableChange = (page, pageSize) => { pagination.current = page; pagination.pageSize = pageSize; fetchData(); };

// 🚨 核心跳转函数
const goToDetail = () => {
  router.push('/policyDetail'); // 跳往独立的配置页面
};

// ======================== 展开行字典翻译 ========================
const getDictName = (val) => ({ 'big':'大字典', 'test':'测试字典', 'top100':'TOP100', 'top1000':'TOP1000', 'all':'全部端口' }[val] || val || '-');
const getDomainIpConfigText = (p) => {
  if (!p) return '-'; const l = [];
  if (p.domain_config?.domain_brute) l.push('域名爆破');
  if (p.domain_config?.alt_dns) l.push('DNS字典智能生成');
  if (p.domain_config?.arl_search) l.push('ARL历史查询');
  if (p.domain_config?.dns_query_plugin) l.push('域名查询插件');
  if (p.ip_config?.port_scan) l.push('端口扫描');
  if (p.ip_config?.service_detection) l.push('服务识别');
  if (p.ip_config?.os_detection) l.push('操作系统识别');
  if (p.ip_config?.ssl_cert) l.push('SSL证书获取');
  if (p.ip_config?.skip_scan_cdn_ip) l.push('跳过CDN');
  if (p.npoc_service_detection) l.push('服务(python)识别');
  return l.join('、') || '-';
};
const getSiteRiskConfigText = (p) => {
  if (!p) return '-'; const l = [];
  if (p.site_config?.site_identify) l.push('站点识别');
  if (p.site_config?.search_engines) l.push('搜索引擎调用');
  if (p.site_config?.site_spider) l.push('站点爬虫');
  if (p.site_config?.site_capture) l.push('站点截图');
  if (p.file_leak) l.push('文件泄露');
  if (p.site_config?.nuclei_scan) l.push('nuclei 调用');
  if (p.site_config?.web_info_hunter) l.push('WIH 调用');
  return l.join('、') || '-';
};
const getPocConfigText = (p) => p?.poc_config?.filter(x => x.enable).map(x => x.vul_name).join('、') || '-';
const getBruteConfigText = (p) => p?.brute_config?.filter(x => x.enable).map(x => x.vul_name).join('、') || '-';

onMounted(() => fetchData());

// ================= 任务下发逻辑 =================
const dispatchModalVisible = ref(false);
const dispatchLoading = ref(false);
const currentPolicy = ref(null);

const dispatchForm = reactive({
  task_tag: 'task',
  name: '',
  target: ''
});

// 打开弹窗并初始化数据
const openDispatchModal = (record) => {
  currentPolicy.value = record;
  dispatchForm.task_tag = 'task';
  dispatchForm.target = '';
  // 智能联动：默认任务名称为“资产侦查任务-策略名”
  dispatchForm.name = `资产侦查任务-${record.name}`;
  dispatchModalVisible.value = true;
};

// 监听下拉框切换，动态改变任务名称前缀
const onTaskTagChange = (val) => {
  const prefix = val === 'task' ? '资产侦查任务' : '风险巡航任务';
  dispatchForm.name = `${prefix}-${currentPolicy.value?.name}`;
};

// 提交发包
const submitDispatch = async () => {
  if (!dispatchForm.name || !dispatchForm.target) {
    return message.warning('请填写完整的任务名称和目标！');
  }

  dispatchLoading.value = true;
  try {
    const payload = {
      policy_id: currentPolicy.value._id,
      name: dispatchForm.name,
      task_tag: dispatchForm.task_tag,
      target: dispatchForm.target
    };

    const res = await request.post('/task/policy/', payload);

    if (res.code === 200) {
      message.success('任务下发成功！');
      dispatchModalVisible.value = false;
      // 成功后一般不需要刷新策略列表，用户会自己去任务监控页面看
    } else if (res.code === 500) {
      // 🚨 原汁原味拦截 500 报错（如：不在关联的资产组范围内）
      message.error(res.message || res.data?.error || '系统异常');
    } else {
      message.error('下发失败: ' + res.message);
    }
  } catch (error) {
    message.error('请求异常，任务下发失败');
  } finally {
    dispatchLoading.value = false;
  }
};

// ================= 单个删除策略逻辑 =================
const handleDelete = async (record) => {
  try {
    // 🚨 核心对齐：抓包显示哪怕删除一个，Payload 也必须是包含 ID 的数组
    const payload = {
      policy_id: [record._id]
    };

    const res = await request.post('/policy/delete/', payload);

    if (res.code === 200) {
      message.success('删除策略成功！');

      // 体验优化：如果当前页只有一条数据，删除后自动退回上一页
      if (dataSource.value.length === 1 && pagination.current > 1) {
        pagination.current -= 1;
      }

      // 重新拉取列表数据
      fetchData();
    } else {
      message.error('删除失败: ' + res.message);
    }
  } catch (error) {
    message.error('请求异常，删除失败');
  }
};

// ================= 批量删除策略逻辑 =================
const handleBatchDelete = async () => {
  if (selectedRowKeys.value.length === 0) {
    return message.warning('请先选择要删除的策略！');
  }
  try {
    const payload = {
      policy_id: selectedRowKeys.value
    };

    const res = await request.post('/policy/delete/', payload);

    if (res.code === 200) {
      message.success('批量删除策略成功！');
      
      // 体验优化：如果当前页数据全被删除了，退回上一页
      if (dataSource.value.length === selectedRowKeys.value.length && pagination.current > 1) {
        pagination.current -= 1;
      }
      
      selectedRowKeys.value = []; // 清空选中
      fetchData(); // 重新拉取列表数据
    } else {
      message.error('批量删除失败: ' + res.message);
    }
  } catch (error) {
    message.error('请求异常，批量删除失败');
  }
};

</script>

<style scoped>
.search-row { display: flex; flex-wrap: wrap; gap: 16px 12px; align-items: center; }
.search-item { display: flex; align-items: center; }
.search-item .label { color: rgba(0,0,0,0.85); margin-right: 8px; min-width: 60px; text-align: right; white-space: nowrap; }
.policy-expanded-box { margin: 8px 16px 16px 16px; background: #fff; border: 1px solid #e8e8e8; border-radius: 2px; }
.policy-section { padding: 16px 24px; }
.policy-title { font-weight: bold; color: #333; margin-bottom: 16px; }
.policy-row { display: flex; margin-bottom: 12px; line-height: 1.5; }
.policy-row:last-child { margin-bottom: 0; }
.policy-label { color: #666; width: 130px; flex-shrink: 0; }
.policy-val { color: #333; word-break: break-word; }
.policy-divider { height: 1px; background: #e8e8e8; margin: 0; }
</style>