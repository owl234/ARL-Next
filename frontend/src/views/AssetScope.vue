<template>
  <div style="background-color: #fff; padding: 24px; min-height: calc(100vh - 64px);">

    <div style="margin-bottom: 24px;">
      <a-button type="primary" style="background-color: #00bcd4; border-color: #00bcd4;" @click="openAddModal">新建资产分组</a-button>
    </div>

    <div class="search-row" style="margin-bottom: 16px;">
      <div class="search-item">
        <span class="label">资产组名称：</span>
        <a-input v-model:value="searchForm.name" placeholder="请输入资产组名称进行搜索" style="width: 220px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
        </a-input>
      </div>
      <div class="search-item">
        <span class="label">资产范围：</span>
        <a-input v-model:value="searchForm.scope" placeholder="请输入资产范围进行搜索" style="width: 220px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
        </a-input>
      </div>
      <div class="search-item">
        <span class="label">资产范围ID：</span>
        <a-input v-model:value="searchForm._id" placeholder="请输入资产范围ID进行搜索" style="width: 220px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
        </a-input>
      </div>
    </div>

    <div style="margin-bottom: 16px; display: flex; gap: 8px;">
      <a-button :disabled="!hasSelected" @click="handleBatchDelete">批量删除</a-button>
      <a-dropdown :disabled="!hasSelected">
        <a-button>
          批量导出 <down-outlined />
        </a-button>
        <template #overlay>
          <a-menu @click="handleBatchExport">
            <a-menu-item key="asset_domain">域名批量导出</a-menu-item>
            <a-menu-item key="asset_ip">IP 批量导出</a-menu-item>
            <a-menu-item key="asset_site">站点批量导出</a-menu-item>
            <a-menu-item key="asset_wih">WIH批量导出</a-menu-item>
          </a-menu>
        </template>
      </a-dropdown>
    </div>

    <a-table
        :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }"
        :loading="loading"
        :dataSource="dataSource"
        :columns="columns"
        :pagination="false"
        size="middle"
        :rowKey="(record) => record._id"
    >
      <template #bodyCell="{ column, record }">

        <template v-if="column.key === 'name'">
          <span>
            {{ record.name }}
          </span>
        </template>

        <template v-else-if="column.key === 'scope_array'">
          <div style="display: flex; flex-wrap: wrap; gap: 4px; align-items: center;">
            <a-tag
                v-for="(item, idx) in (record.scope_array || []).slice(0, 5)"
                :key="idx"
                closable
                style="background: #fafafa; color: #666; border-color: #d9d9d9; margin-right: 0;"
                @close="handleRemoveScope(record, item)"
            >
              {{ item }}
            </a-tag>
            <a-popover v-if="(record.scope_array || []).length > 5" placement="bottomLeft">
              <template #content>
                <div style="max-width: 400px; max-height: 300px; overflow-y: auto; display: flex; flex-wrap: wrap; gap: 4px; padding: 4px;">
                  <a-tag
                      v-for="(item, idx) in record.scope_array.slice(5)"
                      :key="idx"
                      closable
                      style="background: #fafafa; color: #666; border-color: #d9d9d9; margin-right: 0;"
                      @close="handleRemoveScope(record, item)"
                  >
                    {{ item }}
                  </a-tag>
                </div>
              </template>
              <a-tag style="background: #fff; border-style: dashed; cursor: pointer; margin-right: 0;">
                +{{ record.scope_array.length - 5 }} 更多
              </a-tag>
            </a-popover>
          </div>
        </template>

        <template v-else-if="column.key === 'scope_id'">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span
                style="color: #00bcd4; cursor: pointer; user-select: none;"
                @click="copyText(record.scope_array ? record.scope_array.join('\n') : '')"
            >
              复制
            </span>
            <span style="color: #00bcd4; cursor: pointer;" @click="goToDetail(record)">{{ record._id }}</span>
          </div>
        </template>

        <template v-else-if="column.key === 'action'">
          <div style="display: flex; flex-direction: column; gap: 8px; width: max-content;">
            <div style="display: flex; gap: 8px;">
              <a-button size="small" @click="openAddScopeModal(record)">添加资产分组范围</a-button>
              <a-button size="small" @click="openAddMonitorModal(record)">添加监控任务</a-button>
            </div>
            <div style="display: flex; gap: 8px;">
              <a-button size="small" @click="openAddSiteMonitorModal(record)">添加站点监控任务</a-button>
              <a-button size="small" @click="openAddWihMonitorModal(record)">添加WIH监控任务</a-button>
            </div>
          </div>
        </template>

      </template>
    </a-table>

    <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
      <div style="color: rgba(0,0,0,.65);">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
      <a-pagination v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" @showSizeChange="handleTableChange" />
    </div>

    <a-modal
        v-model:open="addModalVisible"
        title="新建资产分组"
        @ok="handleAddSubmit"
        :confirmLoading="addLoading"
        width="520px"
        okText="确 定"
        cancelText="取 消"
        destroyOnClose
    >
      <a-form
          ref="addFormRef"
          :model="addForm"
          :rules="addRules"
          :label-col="{ span: 5 }"
          :wrapper-col="{ span: 18 }"
          style="margin-top: 20px;"
      >
        <a-form-item label="IP类别" name="scope_type">
          <a-select v-model:value="addForm.scope_type" placeholder="请选择类别">
            <a-select-option value="domain">域名</a-select-option>
            <a-select-option value="ip">IP</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="资产组名称" name="name">
          <a-input v-model:value="addForm.name" placeholder="请输入资产组名称" />
        </a-form-item>

        <a-form-item label="资产范围" name="scope">
          <a-textarea
              v-model:value="addForm.scope"
              :rows="4"
              placeholder="请输入资产范围，多个请用逗号或换行分隔"
          />
        </a-form-item>
      </a-form>
    </a-modal>

<!--    新建资产分组-->
    <a-modal
        v-model:open="addScopeVisible"
        title="新建资产分组范围"
        @ok="submitAddScope"
        :confirmLoading="addScopeLoading"
        width="520px"
        okText="确 定"
        cancelText="取 消"
        destroyOnClose
    >
      <a-form
          ref="addScopeFormRef"
          :model="addScopeForm"
          :rules="addScopeRules"
          :label-col="{ span: 6 }"
          :wrapper-col="{ span: 17 }"
          style="margin-top: 20px;"
      >
        <a-form-item label="资产组名称" style="margin-bottom: 8px;">
          <span style="color: rgba(0,0,0,0.85);">{{ currentRecord?.name || '-' }}</span>
        </a-form-item>

        <a-form-item label="资产范围" name="scope">
          <a-textarea
              v-model:value="addScopeForm.scope"
              :rows="4"
              placeholder="请输入资产范围（如：frebuff.com），多个请用逗号或换行分隔"
          />
        </a-form-item>
      </a-form>
    </a-modal>
<!--添加监控任务-->
    <a-modal v-model:open="addMonitorVisible" title="添加监控任务" @ok="submitAddMonitor" :confirmLoading="addMonitorLoading" width="520px" okText="确 定" cancelText="取 消" destroyOnClose>
      <a-form ref="addMonitorFormRef" :model="addMonitorForm" :rules="addMonitorRules" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">

        <a-form-item label="范围" name="domains">
          <div style="display: flex; gap: 8px; align-items: flex-start;">
            <a-select mode="multiple" v-model:value="addMonitorForm.domains" placeholder="请选择范围" style="flex: 1;">
              <a-select-option v-for="item in currentRecord?.scope_array || []" :key="item" :value="item">{{ item }}</a-select-option>
            </a-select>
            <a-button @click="selectAllDomains">全选</a-button>
          </div>
        </a-form-item>

        <a-form-item label="运行间隔" name="interval_hours">
          <div style="display: flex; align-items: center; gap: 8px;">
            <a-input-number v-model:value="addMonitorForm.interval_hours" :min="1" style="width: 100%;" />
            <span>小时</span>
          </div>
        </a-form-item>

        <a-form-item label="策略" name="policy_id">
          <a-select v-model:value="addMonitorForm.policy_id" placeholder="请选择策略">
            <a-select-option v-for="p in policies" :key="p._id" :value="p._id">{{ p.name }}</a-select-option>
          </a-select>
        </a-form-item>

      </a-form>
    </a-modal>

    <a-modal v-model:open="addSiteMonitorVisible" title="添加站点监控任务" @ok="submitAddSiteMonitor" :confirmLoading="addSiteMonitorLoading" width="520px" okText="确 定" cancelText="取 消" destroyOnClose>
      <a-form ref="addSiteMonitorFormRef" :model="addSiteMonitorForm" :rules="addSiteMonitorRules" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">

        <a-form-item label="运行间隔" name="interval_hours">
          <div style="display: flex; align-items: center; gap: 8px;">
            <a-input-number v-model:value="addSiteMonitorForm.interval_hours" :min="1" style="width: 100%;" />
            <span>小时</span>
          </div>
        </a-form-item>

      </a-form>
    </a-modal>
    <a-modal v-model:open="addWihMonitorVisible" title="添加WIH监控任务" @ok="submitAddWihMonitor" :confirmLoading="addWihMonitorLoading" width="520px" okText="确 定" cancelText="取 消" destroyOnClose>
      <a-form ref="addWihMonitorFormRef" :model="addWihMonitorForm" :rules="addWihMonitorRules" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">

        <a-form-item label="运行间隔" name="interval_hours">
          <div style="display: flex; align-items: center; gap: 8px;">
            <a-input-number v-model:value="addWihMonitorForm.interval_hours" :min="1" style="width: 100%;" />
            <span>小时</span>
          </div>
        </a-form-item>

      </a-form>
    </a-modal>

  </div>
</template>

<script setup>
import { ref, onMounted, reactive, computed, createVNode,watch } from 'vue';
import request from '../utils/request';
import { message, Modal } from 'ant-design-vue';
import { SearchOutlined, DownOutlined, ExclamationCircleOutlined } from '@ant-design/icons-vue';
import { useRoute, useRouter } from 'vue-router';


const route = useRoute();
const router = useRouter();
const loading = ref(false);
const dataSource = ref([]);
const searchForm = ref({});
const pagination = reactive({ current: 1, pageSize: 10, total: 0 });

const selectedRowKeys = ref([]);
const hasSelected = computed(() => selectedRowKeys.value.length > 0);
const onSelectChange = (keys) => { selectedRowKeys.value = keys; };


// 🚨 核心还原：没有序号列，名称带排序箭头(sorter)
const columns = [
  { title: '资产组名称', key: 'name', width: 200, sorter: true },
  { title: '资产范围', key: 'scope_array', width: 350 },
  { title: '资产范围ID', key: 'scope_id', width: 280 },
  { title: '操作', key: 'action', width: 300 }
];

// 复制功能
const copyText = async (text) => {
  try {
    await navigator.clipboard.writeText(text);
    message.success('复制成功');
  } catch (err) {
    message.error('复制失败，请手动选取复制');
  }
};

// 拉取表格数据
const fetchData = async () => {
  loading.value = true;
  try {
    const params = { page: pagination.current, size: pagination.pageSize };
    for (const key in searchForm.value) {
      if (searchForm.value[key]) params[key] = searchForm.value[key];
    }
    const res = await request.get('/asset_scope/', { params });
    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
      selectedRowKeys.value = [];
    }
  } catch (error) {
    message.error('加载资产分组失败');
  } finally {
    loading.value = false;
  }
};

const onSearch = () => { pagination.current = 1; fetchData(); };
const handleTableChange = (page, pageSize) => { pagination.current = page; pagination.pageSize = pageSize; fetchData(); };

// ================= 新建资产分组逻辑 =================
const addModalVisible = ref(false);
const addLoading = ref(false);
const addFormRef = ref();

// 表单数据绑定
const addForm = reactive({
  scope_type: 'domain', // 默认选中"域名"
  name: '',
  scope: ''
});

// 必填项校验规则
const addRules = {
  scope_type: [{ required: true, message: '请选择IP类别', trigger: 'change' }],
  name: [{ required: true, message: '请输入资产组名称', trigger: 'blur' }],
  scope: [{ required: true, message: '请输入资产范围', trigger: 'blur' }]
};

// 打开弹窗并重置表单
const openAddModal = () => {
  addForm.scope_type = 'domain';
  addForm.name = '';
  addForm.scope = '';
  addModalVisible.value = true;
};

// 提交表单
const handleAddSubmit = async () => {
  try {
    // 触发前端必填项校验
    await addFormRef.value.validate();

    addLoading.value = true;
    // 发送 POST 请求到抓包指定的接口
    const res = await request.post('/asset_scope/', addForm);

    if (res.code === 200) {
      message.success('新建资产分组成功！');
      addModalVisible.value = false;
      pagination.current = 1; // 自动重置到第一页
      fetchData(); // 刷新表格数据
    } else {
      message.error('新建失败: ' + res.message);
    }
  } catch (error) {
    // 表单校验未通过或网络报错，控制台提示即可
    console.warn('提交中断或校验失败', error);
  } finally {
    addLoading.value = false;
  }
};



// ================= 批量删除逻辑 =================
const handleBatchDelete = () => {
  Modal.confirm({
    title: '批量删除确认',
    icon: createVNode(ExclamationCircleOutlined),
    content: `确定要删除选中的 ${selectedRowKeys.value.length} 个资产分组吗？删除后不可恢复。`,
    okText: '确 定',
    okType: 'danger',
    cancelText: '取 消',
    onOk: async () => {
      try {
        // 🚨 核心对齐：按照抓包要求，Payload 的 key 必须是 scope_id
        const res = await request.post('/asset_scope/delete/', {
          scope_id: selectedRowKeys.value
        });

        if (res.code === 200) {
          message.success('批量删除成功！');
          selectedRowKeys.value = []; // 清空选中状态

          // 如果删光了当前页的数据，自动退回到上一页
          if (dataSource.value.length === selectedRowKeys.value.length && pagination.current > 1) {
            pagination.current -= 1;
          }
          fetchData(); // 重新拉取表格数据
        } else {
          message.error('删除失败: ' + res.message);
        }
      } catch (error) {
        message.error('请求异常，删除失败');
      }
    }
  });
};

// ================= 批量导出逻辑 =================
const handleBatchExport = async ({ key }) => {
  // 根据点击的菜单项，拼凑完整的 API 路径
  const url = `/batch_export/${key}/`;

  // 用于提升用户体验的提示映射字典
  const nameMap = {
    'asset_domain': '域名',
    'asset_ip': 'IP',
    'asset_site': '站点',
    'asset_wih': 'WIH'
  };
  const exportName = nameMap[key];

  try {
    message.loading({ content: `正在生成 ${exportName} 导出文件...`, key: 'export_data' });

    // 🚨 核心逻辑：发起 POST 请求，并指明响应类型为 blob，防止前端 Axios 将纯文本强转 JSON 导致报错
    const res = await request.post(url, { scope_id: selectedRowKeys.value }, { responseType: 'blob' });

    // 将后端返回的纯文本 Blob 转换为前端可下载的文件
    const blob = new Blob([res], { type: 'text/plain;charset=utf-8' });
    const downloadUrl = window.URL.createObjectURL(blob);

    // 模拟点击 a 标签触发浏览器下载
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `ARL_Export_${exportName}_${new Date().getTime()}.txt`; // 自动带上时间戳防止重名
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    message.success({ content: `${exportName} 导出成功！`, key: 'export_data', duration: 2 });
  } catch (error) {
    message.error({ content: `${exportName} 导出失败`, key: 'export_data', duration: 2 });
  }
};

const handleRemoveScope = (record, item) => { message.info(`准备从 ${record.name} 中移除范围: ${item}`); };
const handleAction = (type, record) => { message.info(`准备开发：${type} (目标ID: ${record._id})`); };


// ================= 添加资产分组范围 =================
const addScopeVisible = ref(false);
const addScopeLoading = ref(false);
const addScopeFormRef = ref();
const currentRecord = ref(null); // 记录当前点击的是哪一行

const addScopeForm = reactive({ scope: '' });
const addScopeRules = {
  scope: [{ required: true, message: '请输入资产范围', trigger: 'blur' }]
};

// 1. 打开弹窗
const openAddScopeModal = (record) => {
  currentRecord.value = record; // 把当前行数据存下来，用于展示名字和提取 ID
  addScopeForm.scope = '';
  addScopeVisible.value = true;
};

// 2. 提交请求
const submitAddScope = async () => {
  try {
    await addScopeFormRef.value.validate();
    addScopeLoading.value = true;

    // 🚨 完美对齐抓包 Payload
    const res = await request.post('/asset_scope/add/', {
      scope_id: currentRecord.value._id,
      scope: addScopeForm.scope
    });

    if (res.code === 200) {
      message.success('添加资产分组范围成功！');
      addScopeVisible.value = false;
      fetchData(); // 🚨 对齐抓包的最后一步：重新拉取数据刷新表格
    } else {
      message.error('添加失败: ' + res.message);
    }
  } catch (error) {
    console.warn('校验失败或请求异常', error);
  } finally {
    addScopeLoading.value = false;
  }
};

// 🚨 丝滑跳转：留在当前页面，享受 Vue Router 的极速切换
const goToDetail = (record) => {
  router.push({
    path: '/groupAssetsManagement/groupAssetsDetail',
    query: {
      scope_id: record._id,
      targetName: record._id // 严格遵循抓包发现的逻辑：大标题显示 ID
    }
  });
};



// ================= 添加监控任务 =================
const addMonitorVisible = ref(false);
const addMonitorLoading = ref(false);
const addMonitorFormRef = ref();
const policies = ref([]); // 存放策略列表

// 🚨 初始表单：默认 24 小时，范围使用数组存储
const addMonitorForm = reactive({ domains: [], interval_hours: 24, policy_id: undefined });
const addMonitorRules = {
  domains: [{ type: 'array', required: true, message: '请选择范围', trigger: 'change' }],
  interval_hours: [{ required: true, message: '请输入运行间隔', trigger: 'blur' }],
  policy_id: [{ required: true, message: '请选择策略', trigger: 'change' }]
};

// 1. 打开弹窗并预加载策略
const openAddMonitorModal = async (record) => {
  currentRecord.value = record;
  addMonitorForm.domains = [];
  addMonitorForm.interval_hours = 24; // 恢复默认值 24
  addMonitorForm.policy_id = undefined;
  addMonitorVisible.value = true;

  // 避免重复请求，没数据才去拉取策略
  if (policies.value.length === 0) {
    const res = await request.get('/policy/', { params: { size: 1000 } });
    if (res.code === 200) policies.value = res.items || [];
  }
};

// 2. 实现神级的“全选”按钮功能
const selectAllDomains = () => {
  if (currentRecord.value && currentRecord.value.scope_array) {
    addMonitorForm.domains = [...currentRecord.value.scope_array];
  }
};

// 3. 提交请求（含时间转换与状态码拦截）
const submitAddMonitor = async () => {
  try {
    await addMonitorFormRef.value.validate();
    addMonitorLoading.value = true;

    // 🚨 完美组装抓包 Payload
    const payload = {
      scope_id: currentRecord.value._id,
      domain: addMonitorForm.domains.join(','),     // 前端数组 -> 逗号字符串
      interval: addMonitorForm.interval_hours * 3600, // UI 的小时 -> 接口的秒
      policy_id: addMonitorForm.policy_id,
      name: ''
    };

    const res = await request.post('/scheduler/add/', payload);

    if (res.code === 200) {
      message.success('添加监控任务成功！');
      addMonitorVisible.value = false;
      // 监控任务创建后通常不需要刷新当前列表，去任务监控页看即可
    } else if (res.code === 699) {
      message.error(res.message); // 🚨 原汁原味抛出：域名已存在监控任务
    } else {
      message.error('添加失败: ' + res.message);
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
  interval_hours: [{ required: true, message: '请输入运行间隔', trigger: 'blur' }]
};

// 1. 打开极简弹窗
const openAddSiteMonitorModal = (record) => {
  currentRecord.value = record;
  addSiteMonitorForm.interval_hours = 24; // 默认 24 小时
  addSiteMonitorVisible.value = true;
};

// 2. 提交任务（含状态码拦截）
const submitAddSiteMonitor = async () => {
  try {
    await addSiteMonitorFormRef.value.validate();
    addSiteMonitorLoading.value = true;

    // 🚨 完美组装专属 Payload
    const payload = {
      scope_id: currentRecord.value._id,
      interval: addSiteMonitorForm.interval_hours * 3600 // 依然需要 小时 -> 秒 转换
    };

    const res = await request.post('/scheduler/add/site_monitor/', payload);

    if (res.code === 200) {
      message.success('添加站点监控任务成功！');
      addSiteMonitorVisible.value = false;
    } else if (res.code === 1607) {
      message.error(res.message); // 🚨 原汁原味抛出 1607 专属错误：资产站点更新任务已存在
    } else {
      message.error('添加失败: ' + res.message);
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
  interval_hours: [{ required: true, message: '请输入运行间隔', trigger: 'blur' }]
};

// 1. 打开极简弹窗
const openAddWihMonitorModal = (record) => {
  currentRecord.value = record;
  addWihMonitorForm.interval_hours = 24; // 默认 24 小时
  addWihMonitorVisible.value = true;
};

// 2. 提交任务（含状态码拦截）
const submitAddWihMonitor = async () => {
  try {
    await addWihMonitorFormRef.value.validate();
    addWihMonitorLoading.value = true;

    // 🚨 完美组装专属 Payload
    const payload = {
      scope_id: currentRecord.value._id,
      interval: addWihMonitorForm.interval_hours * 3600 // 依然需要 小时 -> 秒 转换
    };

    const res = await request.post('/scheduler/add/wih_monitor/', payload);

    if (res.code === 200) {
      message.success('添加WIH监控任务成功！');
      addWihMonitorVisible.value = false;
    } else if (res.code === 1607) {
      message.error(res.message); // 🚨 原汁原味抛出 1607 专属错误
    } else {
      message.error('添加失败: ' + res.message);
    }
  } catch (error) {
    console.warn('校验失败或请求异常', error);
  } finally {
    addWihMonitorLoading.value = false;
  }
};

// 🚨 核心联动与统一加载引擎：一个 watch 接管所有情况，拒绝重复请求！
watch(() => route.query.scope_id, (newScopeId) => {
  // 1. 如果 URL 里有 ID (联动跳过来的)，自动填入搜索框
  //    如果 URL 里没 ID (正常点左侧菜单进来的)，自动清空搜索框
  searchForm.value._id = newScopeId || undefined;

  // 2. 统一在这里重置页码并触发唯一一次数据拉取
  pagination.current = 1;
  fetchData();
}, { immediate: true });
// immediate: true 完美替代了 onMounted 的作用，它会在组件加载时自动执行一次





</script>

<style scoped>
.search-row { display: flex; flex-wrap: wrap; gap: 16px 24px; align-items: center; }
.search-item { display: flex; align-items: center; }
.search-item .label { color: rgba(0,0,0,0.85); margin-right: 4px; white-space: nowrap; }
</style>