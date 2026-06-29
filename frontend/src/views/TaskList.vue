<template>
  <div style="background-color: #fff; padding: 24px; min-height: calc(100vh - 64px);">

    <div style="margin-bottom: 24px;">
      <a-button type="primary" style="background-color: #00bcd4; border-color: #00bcd4; margin-right: 12px;" @click="showModal">添加任务</a-button>
      <a-button type="primary" style="background-color: #00bcd4; border-color: #00bcd4; margin-right: 12px;" @click="openFofaModal">FOFA 任务下发</a-button>
      <a-button type="primary" style="background-color: #00bcd4; border-color: #00bcd4;" @click="goToGlobalView">全局查看</a-button>
    </div>

    <div style="margin-bottom: 16px;">
      <a-form :model="searchForm" layout="inline" style="row-gap: 16px;">

        <a-form-item label="任务名:">
          <a-input v-model:value="searchForm.name" placeholder="请输入任务名进行搜索" style="width: 230px;" allowClear @pressEnter="onSearch">
            <template #suffix><search-outlined @click="onSearch" style="color: rgba(0,0,0,.25); cursor: pointer;"/></template>
          </a-input>
        </a-form-item>

        <a-form-item label="目标:">
          <a-input v-model:value="searchForm.target" placeholder="请输入目标进行搜索" style="width: 230px;" allowClear @pressEnter="onSearch">
            <template #suffix><search-outlined @click="onSearch" style="color: rgba(0,0,0,.25); cursor: pointer;"/></template>
          </a-input>
        </a-form-item>

        <a-form-item label="Task_Id:">
          <a-input v-model:value="searchForm.task_id" placeholder="请输入Task_Id进行搜索" style="width: 230px;" allowClear @pressEnter="onSearch">
            <template #suffix><search-outlined @click="onSearch" style="color: rgba(0,0,0,.25); cursor: pointer;"/></template>
          </a-input>
        </a-form-item>

        <a-form-item label="任务类型:">
          <a-select v-model:value="searchForm.type" placeholder="请选择任务类型进行搜索" style="width: 230px;" allowClear>
            <a-select-option value="task">资产侦查任务</a-select-option>
            <a-select-option value="monitor">资产监控任务</a-select-option>
            <a-select-option value="risk_cruising">风险巡航任务</a-select-option>
            <a-select-option value="site_update">资产站点更新</a-select-option>
            <a-select-option value="wih">WIH 监控任务</a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="状态:">
          <a-input v-model:value="searchForm.status" placeholder="请输入状态进行搜索" style="width: 230px;" allowClear @pressEnter="onSearch">
            <template #suffix><search-outlined @click="onSearch" style="color: rgba(0,0,0,.25); cursor: pointer;"/></template>
          </a-input>
        </a-form-item>

        <a-form-item label="站点数量:">
          <a-input-group compact style="display: flex; width: 230px;">
            <a-input v-model:value="searchForm.site_count" placeholder="请输入数量" style="flex: 1;" @pressEnter="onSearch">
              <template #suffix><search-outlined @click="onSearch" style="color: rgba(0,0,0,.25); cursor: pointer;"/></template>
            </a-input>
            <a-select v-model:value="searchForm.site_operator" style="width: 75px;">
              <a-select-option value="=">等于</a-select-option>
              <a-select-option value=">">大于</a-select-option>
              <a-select-option value="<">小于</a-select-option>
            </a-select>
          </a-input-group>
        </a-form-item>

        <a-form-item label="域名数量:">
          <a-input-group compact style="display: flex; width: 230px;">
            <a-input v-model:value="searchForm.domain_count" placeholder="请输入数量" style="flex: 1;" @pressEnter="onSearch">
              <template #suffix><search-outlined @click="onSearch" style="color: rgba(0,0,0,.25); cursor: pointer;"/></template>
            </a-input>
            <a-select v-model:value="searchForm.domain_operator" style="width: 75px;">
              <a-select-option value="=">等于</a-select-option>
              <a-select-option value=">">大于</a-select-option>
              <a-select-option value="<">小于</a-select-option>
            </a-select>
          </a-input-group>
        </a-form-item>

        <a-form-item label="WIH数量:">
          <a-input-group compact style="display: flex; width: 230px;">
            <a-input v-model:value="searchForm.wih_count" placeholder="请输入数量" style="flex: 1;" @pressEnter="onSearch">
              <template #suffix><search-outlined @click="onSearch" style="color: rgba(0,0,0,.25); cursor: pointer;"/></template>
            </a-input>
            <a-select v-model:value="searchForm.wih_operator" style="width: 75px;">
              <a-select-option value="=">等于</a-select-option>
              <a-select-option value=">">大于</a-select-option>
              <a-select-option value="<">小于</a-select-option>
            </a-select>
          </a-input-group>
        </a-form-item>

      </a-form>
    </div>

    <div style="margin-bottom: 16px;">
      <a-button :disabled="!hasSelected" style="margin-right: 8px;" @click="handleBatchDelete">批量删除</a-button>
      <a-button :disabled="!hasSelected" style="margin-right: 8px;" @click="handleBatchStop">批量停止</a-button>
      <a-dropdown :disabled="!hasSelected">
        <template #overlay>
          <a-menu @click="handleBatchExport">
            <a-menu-item key="cip">C段 批量导出</a-menu-item>
            <a-menu-item key="domain">域名批量导出</a-menu-item>
            <a-menu-item key="ip">IP 批量导出</a-menu-item>
            <a-menu-item key="ip_port">IP 端口批量导出</a-menu-item>
            <a-menu-item key="site">站点批量导出</a-menu-item>
            <a-menu-item key="url">URL批量导出</a-menu-item>
            <a-menu-item key="wih">WIH批量导出</a-menu-item>
          </a-menu>
        </template>
        <a-button>批量导出 <down-outlined /></a-button>
      </a-dropdown>
    </div>

    <a-table
        :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }"
        :dataSource="taskList"
        :columns="columns"
        :loading="loading"
        :pagination="false"
        :scroll="{ x: 'max-content' }"
        :rowKey="(record) => record.task_id || record._id"
        bordered
        style="margin-bottom: 16px;"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'name'">
          <a style="color: #00bcd4; font-weight: 500;" @click="viewTask(record)">{{ record.name }}</a>
        </template>

        <template v-else-if="column.key === 'target'">
          <a-tooltip :title="record.target" placement="topLeft">
            <div style="width: 100%; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">
              {{ record.target }}
            </div>
          </a-tooltip>
        </template>

        <template v-else-if="column.key === 'statistic'">
          <div v-if="record.statistic" style="display: flex; gap: 8px; flex-wrap: wrap;">
            <a-badge v-if="record.statistic.site_cnt !== undefined" :count="record.statistic.site_cnt" :number-style="{ backgroundColor: '#00bcd4' }" title="站点" />
            <a-badge v-if="record.statistic.domain_cnt !== undefined" :count="record.statistic.domain_cnt" :number-style="{ backgroundColor: '#1890ff' }" title="域名" />
            <a-badge v-if="record.statistic.ip_cnt !== undefined" :count="record.statistic.ip_cnt" :number-style="{ backgroundColor: '#52c41a' }" title="IP" />
          </div>
          <span v-else style="color: #999;">-</span>
        </template>

        <template v-else-if="column.key === 'options'">
          <a-tooltip placement="bottom" color="rgba(0, 0, 0, 0.85)">
            <template #title>
              <div v-for="(item, index) in getDetailedOptions(record.options)" :key="index" style="line-height: 2;">
                {{ item }}
              </div>
            </template>
            <div style="max-width: 180px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; cursor: pointer;">
              {{ formatOptions(record.options) }}
            </div>
          </a-tooltip>
        </template>

        <template v-else-if="column.key === 'status'">
          <a-tooltip v-if="record.service && record.service.length > 0" placement="bottom" color="rgba(0, 0, 0, 0.85)">
            <template #title>
              <div v-for="(item, index) in record.service" :key="index" style="line-height: 2; font-size: 13px;">
                {{ item.name }}: {{ item.elapsed }}
              </div>
            </template>
            <div style="display: inline-block; cursor: pointer;">
              <a-tag :color="getStatusColor(record.status)" style="margin-right: 0;">{{ record.status }}</a-tag>
            </div>
          </a-tooltip>

          <a-tag v-else :color="getStatusColor(record.status)">{{ record.status }}</a-tag>
        </template>

        <template v-else-if="column.key === 'task_id'">
          <a style="color: #00bcd4; cursor: pointer;" @click="viewTask(record)">{{ record._id }}</a>
        </template>

        <template v-else-if="column.key === 'action'">
          <a-space size="small">
            <a-button type="link" size="small" style="color: #666; padding: 0 4px;" @click="syncTask(record)">同 步</a-button>
            <a-button type="link" size="small" style="color: #666; padding: 0 4px;" @click="exportTask(record)">导 出</a-button>

            <a-button type="link" size="small" style="color: #666; padding: 0 4px;" @click="stopSingleTask(record)" :disabled="record.status === 'done' || record.status === 'error'">停 止</a-button>

            <a-popconfirm title="确定要彻底删除该任务及底层资产数据吗？" ok-text="删除" cancel-text="取消" @confirm="deleteSingleTask(record)">
              <a-button type="link" size="small" style="color: #666; padding: 0 4px;" :disabled="record.status !== 'done' && record.status !== 'error'">删 除</a-button>
            </a-popconfirm>

            <a-button type="link" size="small" style="color: #666; padding: 0 4px;" @click="restartTask(record)">重 启</a-button>
          </a-space>
        </template>

      </template>
    </a-table>

    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0 16px;">
      <div style="color: rgba(0,0,0,.65);">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
      <a-pagination v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" @showSizeChange="handleTableChange" />
    </div>

  </div>

  <a-modal
      v-model:open="visible"
      title="添加任务"
      @ok="handleOk"
      :confirmLoading="submitLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
      :bodyStyle="{ padding: '24px 32px' }"
  >
    <a-form
        ref="formRef"
        :model="formState"
        :label-col="{ style: { width: '115px' } }"
        :wrapper-col="{ style: { width: 'calc(100% - 115px)' } }"
    >
      <a-form-item label="任务名称" name="name" :rules="[{ required: true, message: '请输入任务名称' }]">
        <a-input v-model:value="formState.name" placeholder="请输入任务名称" />
      </a-form-item>

      <a-form-item label="目标" name="target" :rules="[{ required: true, message: '请输入目标' }]">
        <a-textarea
            v-model:value="formState.target"
            placeholder="请输入目标，支持IP、IP段、域名"
            :rows="2"
            style="resize: none;"
        />
      </a-form-item>

      <a-form-item label="域名爆破类型" name="domain_brute_type" :rules="[{ required: true }]">
        <a-select v-model:value="formState.domain_brute_type">
          <a-select-option value="test">测试</a-select-option>
          <a-select-option value="big">大字典</a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item label="端口扫描类型" name="port_scan_type" :rules="[{ required: true }]">
        <a-select v-model:value="formState.port_scan_type">
          <a-select-option value="test">测试</a-select-option>
          <a-select-option value="top100">TOP100</a-select-option>
          <a-select-option value="top1000">TOP1000</a-select-option>
          <a-select-option value="all">全端口</a-select-option>
        </a-select>
      </a-form-item>

      <a-form-item :wrapper-col="{ offset: 3, span: 21 }" style="margin-top: 16px; margin-bottom: 0;">
        <a-row :gutter="[16, 12]">
          <a-col :span="12" v-for="(item, index) in pluginList" :key="item.key"
                 :style="{ marginBottom: (index === 3 || index === 8) ? '16px' : '0' }">
            <a-checkbox v-model:checked="formState[item.key]">
              <span style="color: #666; font-size: 13px;">{{ item.label }}</span>
            </a-checkbox>
          </a-col>
        </a-row>
      </a-form-item>
    </a-form>
  </a-modal>

  <a-modal
      v-model:open="syncVisible"
      title="同步任务"
      @ok="handleSyncOk"
      :confirmLoading="syncLoading"
      width="520px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
  >
    <a-form :model="syncFormState" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">
      <a-form-item label="资产信息" name="scope_id" :rules="[{ required: true }]">
        <a-select
            v-model:value="syncFormState.scope_id"
            placeholder="请选择资产"
            :options="syncOptions"
            allowClear
        >
          <template #notFoundContent>
            <div style="text-align: center; padding: 20px 0;">
              <img src="https://gw.alipayobjects.com/zos/antfincdn/ZHrcdLPrvN/empty.svg" style="height: 35px; opacity: 0.5;" />
              <p style="color: #999; margin-top: 8px;">暂无数据</p>
            </div>
          </template>
        </a-select>
      </a-form-item>
    </a-form>
  </a-modal>

<!--fofa任务下发弹窗-->
  <a-modal
      v-model:open="fofaVisible"
      title="FOFA 任务下发"
      @ok="submitFofaTask"
      :confirmLoading="fofaSubmitLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
      :bodyStyle="{ padding: '24px 32px' }"
  >
    <a-form
        ref="fofaFormRef"
        :model="fofaForm"
        :label-col="{ style: { width: '90px' } }"
        :wrapper-col="{ style: { width: 'calc(100% - 90px)' } }"
    >
      <a-form-item label="任务名称" name="name" :rules="[{ required: true, message: '请输入任务名称' }]">
        <a-input v-model:value="fofaForm.name" placeholder="请输入任务名称" />
      </a-form-item>

      <a-form-item label="查询语句" name="query" :rules="[{ required: true, message: '请输入查询语句' }]">
        <div style="display: flex; gap: 12px; align-items: flex-start;">
          <a-input v-model:value="fofaForm.query" placeholder="请输入 FOFA 查询语句" style="flex: 1;" />
          <a-button type="primary" @click="testFofaQuery" :loading="fofaTestLoading">测 试</a-button>
        </div>
        <div style="margin-top: 8px; color: rgba(0,0,0,0.85); margin-left: 4px;">
          结果数：{{ fofaResultCount }}
        </div>
      </a-form-item>

      <a-form-item label="关联策略" name="policy_id">
        <a-select
            v-model:value="fofaForm.policy_id"
            placeholder="请选择关联策略 (可选)"
            :options="policyOptions"
            allowClear
        />
      </a-form-item>
    </a-form>
  </a-modal>


</template>

<script setup>
import { ref, reactive, onMounted, computed, createVNode } from 'vue';
import { Modal, message, Checkbox } from 'ant-design-vue';
import { useRouter } from 'vue-router'; // 新增：引入路由钩子
// 引入 Antd 的图标（搜索放大镜、下拉箭头）
import { SearchOutlined, DownOutlined, ExclamationCircleOutlined } from '@ant-design/icons-vue';
import request from '../utils/request';

// --- 表格与数据逻辑 ---
const router = useRouter();
const taskList = ref([]);
const loading = ref(false);
const pagination = reactive({ current: 1, pageSize: 10, total: 0, showSizeChanger: true });

// 1:1 还原原版精确的宽带分配，并为任务名和目标开启排序
const columns = [
  { title: '任务名', dataIndex: 'name', key: 'name', width: 180, sorter: true, ellipsis: true },
  { title: '目标', dataIndex: 'target', key: 'target', width: 220, sorter: true, ellipsis: true },
  { title: '统计', dataIndex: 'statistic', key: 'statistic', width: 100 },
  { title: '配置项', dataIndex: 'options', key: 'options', width: 160, ellipsis: true },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '开始时间', dataIndex: 'start_time', key: 'start_time', width: 160 },
  { title: '结束时间', dataIndex: 'end_time', key: 'end_time', width: 160 },
  { title: 'Task_Id', dataIndex: '_id', key: 'task_id', width: 220 },
  { title: '操作', key: 'action', fixed: 'right', width: 280 },
];

// 升级版：智能识别 ARL 的各种动态运行状态
const getStatusColor = (status) => {
  if (status === 'done') return 'success';     // 成功：绿色
  if (status === 'error') return 'error';      // 失败：红色
  if (status === 'waiting') return 'default';  // 等待：灰色

  // ARL 会把当前执行的插件名作为状态，比如 domain_brute, port_scan
  // 只要不是上面三种，统统认为是“正在运行”，显示为蓝色处理中状态
  return 'processing';
};

// 解析 JSON 中的 options 对象，转换为中文逗号分隔字符串
const formatOptions = (options) => {
  if (!options) return '-';
  const activeOptions = [];
  for (const key in options) {
    if (options[key] === true) {
      // 在新的 pluginList 中寻找中文标签
      const plugin = pluginList.find(item => item.key === key);
      if (plugin) {
        activeOptions.push(plugin.label);
      }
    }
  }
  return activeOptions.length > 0 ? activeOptions.join(', ') : '-';
};
// 🚨 新增：专门给黑色 Tooltip 气泡用的高级解析函数 (支持换行和提取子类型)
const getDetailedOptions = (options) => {
  if (!options) return ['-'];
  const detailed = [];

  // 1. 提取普通的布尔值插件 (为 true 的项)
  for (const key in options) {
    if (options[key] === true) {
      const plugin = pluginList.find(item => item.key === key);
      if (plugin) detailed.push(plugin.label);
    }
  }

  // 2. 提取并翻译特殊的具体配置项 (如字典类型、端口范围)
  if (options.domain_brute_type) {
    const typeMap = { test: '测试', big: '大字典' };
    detailed.push(`域名爆破类型: ${typeMap[options.domain_brute_type] || options.domain_brute_type}`);
  }
  if (options.port_scan_type) {
    const typeMap = { test: '测试', top100: 'TOP100', top1000: 'TOP1000', all: '全端口' };
    // 忽略 null 值
    if(options.port_scan_type !== 'null' && options.port_scan_type !== null) {
      detailed.push(`端口扫描类型: ${typeMap[options.port_scan_type] || options.port_scan_type.toUpperCase()}`);
    }
  }

  return detailed.length > 0 ? detailed : ['-'];
};

// --- 搜索表单逻辑 ---
const searchForm = reactive({
  name: '', target: '', task_id: '', type: undefined,
  status: '', site_count: '', site_operator: '=',
  domain_count: '', domain_operator: '=', wih_count: '', wih_operator: '='
});

// --- 表格多选逻辑 ---
const selectedRowKeys = ref([]);
const hasSelected = computed(() => selectedRowKeys.value.length > 0);
const onSelectChange = (keys) => {
  selectedRowKeys.value = keys;
};



// 💥 完美复刻 ARL 任务删除：支持动态勾选是否删除底层数据
const handleBatchDelete = () => {
  if (!hasSelected.value) {
    message.warning('请先勾选需要删除的任务');
    return;
  }

  // 1. 数据消杀，确保拿到的是纯净的 ID 数组
  const validKeys = selectedRowKeys.value.filter(key => key != null);

  if (validKeys.length === 0) {
    message.error('获取任务ID失败，请检查表格 rowKey 设置！');
    return;
  }

  // 2. 定义局部变量接管复选框的状态（默认打勾，对齐 ARL 原版逻辑）
  let isDeleteData = true;

  Modal.confirm({
    title: '删除确认',
    icon: createVNode(ExclamationCircleOutlined),
    // 3. 利用 createVNode 动态渲染一段包含 Checkbox 的提示内容
    content: createVNode('div', { style: 'margin-top: 8px;' }, [
      createVNode('div', { style: 'margin-bottom: 16px; color: rgba(0,0,0,0.85);' }, `确认要删除选中的 ${validKeys.length} 项任务吗？`),
      createVNode(Checkbox, {
        defaultChecked: isDeleteData,
        onChange: (e) => { isDeleteData = e.target.checked; } // 监听勾选状态变化
      }, () => '同时删除该任务关联的所有资产数据 (不可恢复)')
    ]),
    okText: '确 定',
    cancelText: '取 消',
    okButtonProps: { danger: true }, // 删除按钮标红，符合安全操作规范
    onOk: async () => {
      try {
        // 4. 完全对齐你抓包的 Payload 结构
        const res = await request.post('/task/delete/', {
          del_task_data: isDeleteData, // 读取用户的勾选状态
          task_id: validKeys           // 发送被勾选的任务 ID 数组
        });

        if (res.code === 200) {
          message.success(`成功删除 ${validKeys.length} 项任务！`);
          selectedRowKeys.value = []; // 清空表格勾选状态
          fetchTasks(1, pagination.pageSize); // 刷新表格并回到第一页
        } else {
          message.error('删除失败: ' + (res.message || '未知错误'));
        }
      } catch (error) {
        console.error('批量删除任务异常:', error);
        message.error('网络异常，请查看控制台');
      }
    }
  });
};

// 💥 完美复刻 ARL 任务停止：批量强制终止选中的任务
const handleBatchStop = () => {
  if (!hasSelected.value) {
    message.warning('请先勾选需要停止的任务');
    return;
  }

  // 1. 数据消杀，确保拿到的是纯净的 ID 数组
  const validKeys = selectedRowKeys.value.filter(key => key != null);

  if (validKeys.length === 0) {
    message.error('获取任务ID失败，请检查表格 rowKey 设置！');
    return;
  }

  // 2. 原版风格的确认弹窗（不需要内部复选框了）
  Modal.confirm({
    title: '停止确认',
    icon: createVNode(ExclamationCircleOutlined),
    content: `确认要强制停止选中的 ${validKeys.length} 项任务吗？`,
    okText: '确 定',
    cancelText: '取 消',
    // 停止按钮不需要像删除那样标红，保持默认的蓝色即可
    onOk: async () => {
      try {
        // 3. 1:1 对齐你抓包的极简 Payload 结构
        const res = await request.post('/task/batch_stop/', {
          task_id: validKeys
        });

        if (res.code === 200) {
          message.success(`成功下发停止指令给 ${validKeys.length} 项任务！`);
          selectedRowKeys.value = []; // 清空表格勾选状态
          fetchTasks(pagination.current, pagination.pageSize); // 刷新当前页表格以获取最新状态
        } else {
          message.error('停止失败: ' + (res.message || '未知错误'));
        }
      } catch (error) {
        console.error('批量停止任务异常:', error);
        message.error('网络异常，请查看控制台');
      }
    }
  });
};

// 💥 完美复刻 ARL 任务批量导出：支持纯文本文件流自动下载
const handleBatchExport = async ({ key }) => {
  if (!hasSelected.value) {
    message.warning('请先勾选需要导出的任务');
    return;
  }

  const validKeys = selectedRowKeys.value.filter(k => k != null);
  if (validKeys.length === 0) {
    message.error('获取任务ID失败，请检查表格 rowKey 设置！');
    return;
  }

  try {
    // 弹出一个加载提示，防止用户在下载大文件时疯狂点击
    message.loading({ content: '正在生成导出文件...', key: 'exporting' });

    // 发起 POST 请求。
    // 🚨 核心设定：加上 responseType: 'blob'，强制让 Axios 把返回的纯文本/文件流当作 Blob 对象处理，
    // 避免你们项目中的 request 拦截器试图把它当作 JSON (res.code === 200) 来解析从而引发报错。
    const res = await request.post(`/batch_export/${key}/`, {
      task_id: validKeys
    }, {
      responseType: 'blob'
    });

    // 创建虚拟文件对象 (Blob)
    const blob = new Blob([res], { type: 'text/plain;charset=utf-8' });
    const downloadUrl = window.URL.createObjectURL(blob);

    // 创建一个隐藏的 <a> 标签并模拟点击下载
    const link = document.createElement('a');
    link.href = downloadUrl;
    // 动态生成文件名，例如：batch_export_cip.txt
    link.download = `batch_export_${key}.txt`;
    document.body.appendChild(link);
    link.click();

    // 下载完毕后清理 DOM 和内存中的临时 URL
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    // 更新加载提示为成功状态
    message.success({ content: '导出成功！', key: 'exporting', duration: 2 });

  } catch (error) {
    console.error('批量导出异常:', error);
    message.error({ content: '导出失败，请查看控制台', key: 'exporting', duration: 2 });
  }
};

// 点击同步弹窗“确定”按钮
const handleSyncOk = async () => {
  if (!syncFormState.scope_id) {
    message.warning('请选择资产信息');
    return;
  }

  syncLoading.value = true;
  try {
    // 1:1 对齐抓包：POST /api/task/sync/
    // Payload 结构：{"scope_id": "...", "task_id": "..."}
    const res = await request.post('/task/sync/', {
      scope_id: syncFormState.scope_id,
      task_id: currentSyncRecord.value._id || currentSyncRecord.value.task_id
    });

    if (res.code === 200) {
      message.success('同步任务下发成功 🚀');
      syncVisible.value = false;
      // 刷新列表以显示最新状态
      fetchTasks(pagination.current, pagination.pageSize);
    } else {
      message.error('同步失败: ' + (res.message || '未知错误'));
    }
  } catch (error) {
    console.error('同步请求异常:', error);
    message.error('网络异常，请稍后再试');
  } finally {
    syncLoading.value = false;
  }
};

// --- 数据获取 ---
// --- 数据获取与搜索逻辑 ---
// --- 数据获取与搜索逻辑 ---
const fetchTasks = async (page = 1, size = 10) => {
  loading.value = true;
  try {
    // 1. 基础分页参数
    const queryParams = { page, size };

    // 2. 映射基础文本框 (精准排空)
    if (searchForm.name) queryParams.name = searchForm.name;
    if (searchForm.target) queryParams.target = searchForm.target;
    if (searchForm.status) queryParams.status = searchForm.status;

    // 3. 🚨 修正 Task_Id: 映射为 _id
    if (searchForm.task_id) queryParams._id = searchForm.task_id;

    // 4. 🚨 修正 任务类型: 映射为 task_tag
    if (searchForm.type) queryParams.task_tag = searchForm.type;

    // 5. 🚨 修正 数量统计: 封装为后端认识的 statistic.xxx 格式
    const appendCountParam = (count, operator, baseKey) => {
      if (count !== '' && count !== null && count !== undefined) {
        if (operator === '=') {
          queryParams[baseKey] = count;
        } else if (operator === '>') {
          queryParams[`${baseKey}_gt`] = count; // ARL 的大于语法
        } else if (operator === '<') {
          queryParams[`${baseKey}_lt`] = count; // ARL 的小于语法
        }
      }
    };

    // 依次将前端绑定的双变量转换为后端认识的单 key
    appendCountParam(searchForm.site_count, searchForm.site_operator, 'statistic.site_cnt');
    appendCountParam(searchForm.domain_count, searchForm.domain_operator, 'statistic.domain_cnt');
    appendCountParam(searchForm.wih_count, searchForm.wih_operator, 'statistic.wih_cnt');

    // 发送最终拼装好的绝赞参数
    const res = await request.get('/task/', { params: queryParams });

    if (res.code === 200) {
      taskList.value = res.items || [];
      pagination.total = res.total || 0;
      pagination.current = page;
      pagination.pageSize = size;
    } else {
      console.error('获取列表失败:', res);
    }
  } catch (error) {
    console.error('API 请求失败:', error);
  } finally {
    loading.value = false;
  }
};

// 触发搜索的捷径方法（强制回到第一页）
const onSearch = () => {
  fetchTasks(1, pagination.pageSize);
};

const handleTableChange = (page, pageSize) => fetchTasks(page, pageSize);
onMounted(() => fetchTasks(pagination.current, pagination.pageSize));

// --- 弹窗逻辑 (保持原样) ---
const visible = ref(false);
const submitLoading = ref(false);
const formRef = ref();

// 完全对齐原版截图的插件名称和左/右两列的顺序
// === 1. 纯净的插件字典（严格按照截图双列排序） ===
const pluginList = [
  { key: 'domain_brute', label: '域名爆破' },
  { key: 'alt_dns', label: 'DNS字典智能生成' },
  { key: 'dns_query_plugin', label: '域名查询插件' },
  { key: 'arl_search', label: 'ARL 历史查询' },
  { key: 'port_scan', label: '端口扫描' },
  { key: 'service_detection', label: '服务识别' },
  { key: 'os_detection', label: '操作系统识别' },
  { key: 'ssl_cert', label: 'SSL 证书获取' },
  { key: 'skip_scan_cdn_ip', label: '跳过CDN' },
  { key: 'site_identify', label: '站点识别' },
  { key: 'search_engines', label: '搜索引擎调用' },
  { key: 'site_spider', label: '站点爬虫' },
  { key: 'site_capture', label: '站点截图' },
  { key: 'file_leak', label: '文件泄露' },
  { key: 'findvhost', label: 'Host 碰撞' },
  { key: 'nuclei_scan', label: 'nuclei 调用' },
  { key: 'web_info_hunter', label: 'WIH 调用' }
];

// === 2. 匹配截图的默认勾选状态 ===
const defaultPlugins = {
  domain_brute: true, alt_dns: true, dns_query_plugin: true, arl_search: true,
  port_scan: true, service_detection: false, os_detection: false, ssl_cert: false,
  skip_scan_cdn_ip: true, site_identify: false, search_engines: false, site_spider: false,
  site_capture: false, file_leak: false, findvhost: false, nuclei_scan: false, web_info_hunter: false
};

// === 3. 表单状态初始化（不再依赖任何废弃变量） ===
const formState = reactive({
  name: "",
  target: "",
  domain_brute_type: "big",
  port_scan_type: "TOP100",
  ...defaultPlugins
});

const showModal = () => { visible.value = true; };

// 跳转到详情页，并把全部统计数据塞进 URL
// --- 操作列逻辑 ---
const viewTask = (record) => {
  // 1. 防御性检查：确保传入的确实是一行数据对象
  if (!record || !record._id) {
    console.error('viewTask 接收到的参数有误:', record);
    return;
  }

  // 2. 拼装基础查询参数
  const query = {
    task_id: record._id,
    targetName: record.target
  };

  // 3. 把统计数据里的数量也全部解构进去 (适配 ARL 原版的 url 传参形式)
  if (record.statistic) {
    Object.assign(query, record.statistic);
  }

  // 4. 执行跳转！
  console.log('准备跳转到详情页，携带参数:', query);
  router.push({ path: '/taskList/taskDetail', query });
};




// === 同步任务专属状态 ===
const syncVisible = ref(false);
const syncLoading = ref(false);
const syncOptions = ref([]); // 下拉框资产列表
const currentSyncRecord = ref(null);
const syncFormState = reactive({
  scope_id: undefined
});





// ==========================================
// 💥 任务管理：单行操作 5 大核心功能 1:1 复刻
// ==========================================

// 1. 同步 (Sync)
// 点击表格“同步”按钮的操作
const syncTask = async (record) => {
  currentSyncRecord.value = record;
  syncFormState.scope_id = undefined;
  syncOptions.value = [];
  syncVisible.value = true;

  try {
    // 1:1 对齐抓包：GET /api/task/sync_scope/?target=...
    const res = await request.get('/task/sync_scope/', {
      params: { target: record.target }
    });

    if (res.code === 200) {
      // 对齐抓包 Response：提取 _id 和 name
      syncOptions.value = (res.items || []).map(item => ({
        value: item._id,
        label: item.name
      }));
    }
  } catch (error) {
    console.error('获取资产选项失败:', error);
  }
};

// 2. 导出 Excel (Export)
const exportTask = async (record) => {
  try {
    message.loading({ content: '正在生成 Excel 导出文件...', key: 'exporting_excel' });

    // 对齐 Payload: /api/export/{task_id}
    // 🚨 必须加 responseType: 'blob'，否则 Axios 拿到 Excel 的二进制乱码会报错崩溃
    const res = await request.get(`/export/${record._id || record.task_id}`, {
      responseType: 'blob'
    });

    // 将二进制流组装为 .xlsx Excel 文件
    const blob = new Blob([res], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
    const downloadUrl = window.URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `ARL_Task_${record.name}_Export.xlsx`; // 动态拼装更优雅的文件名
    document.body.appendChild(link);
    link.click();

    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    message.success({ content: 'Excel 导出成功！', key: 'exporting_excel', duration: 2 });
  } catch (error) {
    console.error('导出 Excel 异常:', error);
    message.error({ content: '导出异常，请查看控制台', key: 'exporting_excel', duration: 2 });
  }
};

// 3. 停止单行任务 (Stop)
const stopSingleTask = async (record) => {
  try {
    // 对齐 Payload: /api/task/stop/{task_id} (无 body)
    const res = await request.get(`/task/stop/${record._id || record.task_id}`);
    if (res.code === 200) {
      message.success('已发送停止指令 🛑');
      fetchTasks(pagination.current, pagination.pageSize); // 刷新表格状态
    } else {
      message.error('停止失败: ' + (res.message || '未知错误'));
    }
  } catch (error) {
    message.error('网络异常，停止失败');
  }
};

// 4. 删除单行任务 (Delete)
const deleteSingleTask = async (record) => {
  try {
    // 对齐 Payload: 与批量删除接口一致，必须传数组，且硬编码 del_task_data: true
    const res = await request.post('/task/delete/', {
      task_id: [record._id || record.task_id],
      del_task_data: true
    });

    if (res.code === 200) {
      message.success('任务及资产数据已彻底销毁 💥');
      fetchTasks(pagination.current, pagination.pageSize);
    } else {
      message.error('删除失败: ' + (res.message || '未知错误'));
    }
  } catch (error) {
    message.error('网络异常，删除失败');
  }
};

// 5. 重启任务 (Restart)
const restartTask = async (record) => {
  try {
    // 对齐 Payload: 传数组
    const res = await request.post('/task/restart/', {
      task_id: [record._id || record.task_id]
    });

    if (res.code === 200) {
      message.success('任务已重启，正在执行... 🚀');
      fetchTasks(pagination.current, pagination.pageSize); // 刷新表格看到状态变为 processing
    } else {
      message.error('重启失败: ' + (res.message || '未知错误'));
    }
  } catch (error) {
    message.error('网络异常，重启失败');
  }
};



const handleOk = async () => {
  try {
    await formRef.value.validate();
    submitLoading.value = true;
    const res = await request.post('/task/', formState);
    if (res.code === 200) {
      message.success('任务下发成功！');
      visible.value = false;
      fetchTasks(1, pagination.pageSize);
    } else {
      message.error('下发失败: ' + (res.message || '未知错误'));
    }
  } catch (error) {
    if (!error.errorFields) message.error('网络异常');
  } finally {
    submitLoading.value = false;
  }
};



// ==========================================
// 💥 FOFA 任务下发：获取策略、测试语句、提交表单
// ==========================================
const fofaVisible = ref(false);
const fofaSubmitLoading = ref(false);
const fofaTestLoading = ref(false);
const fofaResultCount = ref(0);
const policyOptions = ref([]); // 存放下拉框策略数据
const fofaFormRef = ref();

const fofaForm = reactive({
  name: '',
  query: '',
  policy_id: undefined
});

// 1. 打开弹窗，并拉取策略列表 (对齐 GET /api/policy/)
const openFofaModal = async () => {
  // 重置状态
  fofaForm.name = '';
  fofaForm.query = '';
  fofaForm.policy_id = undefined;
  fofaResultCount.value = 0;
  if (fofaFormRef.value) fofaFormRef.value.clearValidate();

  fofaVisible.value = true;

  try {
    // 强制分页拉取最多 1000 条策略，保证下拉框数据完整
    const res = await request.get('/policy/', { params: { page: 1, size: 1000 } });
    if (res.code === 200) {
      policyOptions.value = (res.items || []).map(item => ({
        value: item._id,
        label: item.name
      }));
    }
  } catch (error) {
    console.error('拉取关联策略失败:', error);
  }
};

// 2. 点击“测试”按钮 (对齐 POST /api/task_fofa/test)
const testFofaQuery = async () => {
  if (!fofaForm.query) {
    message.warning('请先输入查询语句再进行测试');
    return;
  }

  fofaTestLoading.value = true;
  try {
    const res = await request.post('/task_fofa/test', { query: fofaForm.query });

    // 如果 FOFA 配置正常并返回了数据 (兼容 size 或 total 字段)
    if (res.code === 200) {
      fofaResultCount.value = res.data?.size || res.data?.total || 0;
      message.success('测试连接成功');
    } else {
      // 完美拦截你抓到的 1202 错误 (Fofa key is not set)
      fofaResultCount.value = 0;
      message.error(res.message || '测试失败');
    }
  } catch (error) {
    fofaResultCount.value = 0;
    message.error('测试请求异常，请查看控制台');
  } finally {
    fofaTestLoading.value = false;
  }
};

// 3. 点击“确定”下发任务 (对齐 POST /api/task_fofa/submit)
const submitFofaTask = async () => {
  try {
    await fofaFormRef.value.validate(); // 触发必填校验

    fofaSubmitLoading.value = true;
    const res = await request.post('/task_fofa/submit', {
      name: fofaForm.name,
      query: fofaForm.query,
      policy_id: fofaForm.policy_id
    });

    if (res.code === 200) {
      message.success('FOFA 任务下发成功！');
      fofaVisible.value = false;
      fetchTasks(1, pagination.pageSize); // 回到第一页并刷新列表
    } else {
      // 完美拦截你抓到的 1201 错误 (please set fofa key in config-docker.yaml)
      message.error(res.message || '任务下发失败');
    }
  } catch (error) {
    if (!error.errorFields) { // 排除表单校验报错
      message.error('网络请求异常');
    }
  } finally {
    fofaSubmitLoading.value = false;
  }
};

// 💥 全局查看：跳转到详情页，但不带 task_id 参数
const goToGlobalView = () => {
  router.push({
    path: '/taskList/taskDetail',
    query: {
      targetName: '全局', // 让详情页的标题显示为“全局相关资产”
      // 注意：这里故意不传 task_id
    }
  });
};


</script>

<style scoped>
/* ==========================================
   1. 表单标签文字微调 (贴近原版颜色和大小)
========================================== */
:deep(.ant-form-item-label > label) {
  font-size: 14px;
  color: #333;
}

/* ==========================================
   2. ARL 专属主题色覆盖 (黑客青 #00bcd4)
   只作用于带有 arl-theme-modal 类的弹窗
========================================== */

/* 核心补丁 A：高度还原原版 Checkbox 样式 (2px 微圆角 + 黑客青) */
:deep(.arl-theme-modal .ant-checkbox-inner) {
  border-radius: 2px !important;
}
:deep(.arl-theme-modal .ant-checkbox-checked .ant-checkbox-inner) {
  background-color: #00bcd4 !important;
  border-color: #00bcd4 !important;
}

/* 覆盖复选框悬浮时的边框色 */
:deep(.arl-theme-modal .ant-checkbox-wrapper:hover .ant-checkbox-inner),
:deep(.arl-theme-modal .ant-checkbox:hover .ant-checkbox-inner),
:deep(.arl-theme-modal .ant-checkbox-input:focus + .ant-checkbox-inner) {
  border-color: #00bcd4 !important;
}

/* 覆盖输入框 (Input / Textarea) 聚焦时的光晕和边框 */
:deep(.arl-theme-modal .ant-input:focus),
:deep(.arl-theme-modal .ant-input-focused),
:deep(.arl-theme-modal .ant-input:hover) {
  border-color: #00bcd4 !important;
  box-shadow: 0 0 0 2px rgba(0, 188, 212, 0.2) !important;
}

/* 覆盖下拉选择框 (Select) 聚焦和悬浮时的颜色 */
:deep(.arl-theme-modal .ant-select:not(.ant-select-disabled):hover .ant-select-selector),
:deep(.arl-theme-modal .ant-select-focused:not(.ant-select-disabled).ant-select:not(.ant-select-customize-input) .ant-select-selector) {
  border-color: #00bcd4 !important;
  box-shadow: 0 0 0 2px rgba(0, 188, 212, 0.2) !important;
}

/* 核心补丁 B：还原弹窗底部“下发”主按钮的青色 */
:deep(.arl-theme-modal .ant-btn-primary) {
  background-color: #00bcd4 !important;
  border-color: #00bcd4 !important;
}
:deep(.arl-theme-modal .ant-btn-primary:hover),
:deep(.arl-theme-modal .ant-btn-primary:focus) {
  background-color: #00acc1 !important; /* 悬浮时稍微加深一点 */
  border-color: #00acc1 !important;
}
</style>


<style>
/* ==========================================
   ARL 专属主题色覆盖 (黑客青 #00bcd4)
   利用 .arl-theme-modal 限定范围，绝对不污染其他组件
========================================== */

/* 1. 将复选框 (Checkbox) 打勾后的背景色和边框染成青色 */
.arl-theme-modal .ant-checkbox-checked .ant-checkbox-inner {
  background-color: #00bcd4 !important;
  border-color: #00bcd4 !important;
}

/* 2. 修复复选框鼠标悬浮时的蓝色边框 */
.arl-theme-modal .ant-checkbox-wrapper:hover .ant-checkbox-inner,
.arl-theme-modal .ant-checkbox:hover .ant-checkbox-inner,
.arl-theme-modal .ant-checkbox-input:focus + .ant-checkbox-inner {
  border-color: #00bcd4 !important;
}

/* 3. 将输入框 (Input / Textarea) 聚焦时的蓝色边框和光晕改成青色 */
.arl-theme-modal .ant-input:focus,
.arl-theme-modal .ant-input-focused,
.arl-theme-modal .ant-input:hover {
  border-color: #00bcd4 !important;
  box-shadow: 0 0 0 2px rgba(0, 188, 212, 0.2) !important;
}

/* 4. 将下拉选择框 (Select) 聚焦和悬浮时的蓝色改成青色 */
.arl-theme-modal .ant-select:not(.ant-select-disabled):hover .ant-select-selector,
.arl-theme-modal .ant-select-focused:not(.ant-select-disabled).ant-select:not(.ant-select-customize-input) .ant-select-selector {
  border-color: #00bcd4 !important;
  box-shadow: 0 0 0 2px rgba(0, 188, 212, 0.2) !important;
}

/* 5. 核心：把“确定”按钮的默认蓝色强制覆盖为青色 */
.arl-theme-modal .ant-btn-primary {
  background-color: #00bcd4 !important;
  border-color: #00bcd4 !important;
}

/* 按钮悬浮时颜色微微加深，提升交互手感 */
.arl-theme-modal .ant-btn-primary:hover,
.arl-theme-modal .ant-btn-primary:focus {
  background-color: #00acc1 !important;
  border-color: #00acc1 !important;
}
</style>