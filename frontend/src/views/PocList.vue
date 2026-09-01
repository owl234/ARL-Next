<template>
  <div style="background-color: var(--arl-bg-layout); padding: 24px; min-height: calc(100vh - 64px);">
    <div ref="actionBarRef" style="position: sticky; top: 0px; z-index: 10; background-color: var(--arl-bg-layout); margin: -24px -24px 16px -24px; padding: 24px 24px 16px 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">


    <div style="display: flex; align-items: center; margin-bottom: 20px; gap: 16px;">
      <a-button type="primary" @click="openCreateModal">新建 PoC</a-button>
      <a-button type="primary" @click="isImportModalVisible = true">导入 PoC</a-button>
      <a-button type="primary" @click="downloadTemplate">下载导入模板</a-button>

      <a-button type="primary" :loading="syncLoading" @click="handleSync">更新</a-button>
    </div>

    <div class="search-row" style="margin-bottom: 16px; ">
      <div class="search-item">
        <span class="label">漏洞名称：</span>
        <a-input v-model:value="searchForm.vul_name" placeholder="请输入漏洞名称进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
        </a-input>
      </div>
      <div class="search-item">
        <span class="label">应用：</span>
        <a-input v-model:value="searchForm.app_name" placeholder="请输入应用进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
        </a-input>
      </div>
      <div class="search-item">
        <span class="label">类别：</span>
        <a-input v-model:value="searchForm.category" placeholder="请输入类别进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
        </a-input>
      </div>
      <div class="search-item">
        <span class="label">协议：</span>
        <a-input v-model:value="searchForm.scheme" placeholder="请输入协议进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.25;" /></template>
        </a-input>
      </div>
    </div>

    <div style="margin-bottom: 16px; display: flex; gap: 16px;">
      <a-button @click="resetSearch">清 除</a-button>
      <a-popconfirm
          title="确认批量删除选中的 PoC 吗？"
          ok-text="确认"
          cancel-text="取消"
          @confirm="handleBatchDelete"
          :disabled="selectedRowKeys.length === 0"
      >
        <a-button type="primary" danger :disabled="selectedRowKeys.length === 0" :loading="deleteLoading">批量删除</a-button>
      </a-popconfirm>
    </div>

    
    </div>
<a-table :sticky="stickyConfig"
        :loading="loading"
        :dataSource="dataSource"
        :columns="columns"
        :pagination="false"
        size="middle"
        :rowKey="(record) => record._id"
        :rowSelection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }"
    >
      <template #bodyCell="{ column, record, index }">
        <template v-if="column.key === 'index'">
          <span>{{ (pagination.current - 1) * pagination.pageSize + index + 1 }}</span>
        </template>
        <template v-if="column.key === 'vul_name'">
          <a @click="showPocDetail(record)" style="font-weight: 500;">{{ record.vul_name }}</a>
        </template>
        <template v-if="column.key === 'action'">
          <a @click="editPocSource(record)">编辑源码</a>
        </template>
      </template>
      <template #emptyText>
        <div style="padding: 40px 0;">
          <inbox-outlined style="font-size: 48px; color: var(--arl-border-color);" />
          <div style="color: var(--arl-text-color); opacity: 0.45; margin-top: 8px;">暂无数据</div>
        </div>
      </template>
    </a-table>

    <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
      <div style="color: var(--arl-text-color); opacity: 0.65;">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
      <a-pagination :pageSizeOptions="$pageSizeOptions" v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" />
    </div>

    <!-- 导入 PoC 弹窗 -->
    <a-modal v-model:open="isImportModalVisible" title="导入 PoC 文件" :footer="null">
      <a-upload-dragger
        name="file"
        :multiple="true"
        action="/api/poc/import/"
        :headers="uploadHeaders"
        accept=".yml, .yaml, .py"
        @change="handleUploadChange"
      >
        <p class="ant-upload-drag-icon"><inbox-outlined /></p>
        <p class="ant-upload-text">点击或将文件拖拽到这里上传</p>
        <p class="ant-upload-hint">支持单文件或多文件批量上传，仅支持 .yml, .yaml, .py 格式</p>
      </a-upload-dragger>
    </a-modal>

    <!-- 详情抽屉 -->
    <a-drawer
        v-model:open="isDetailDrawerVisible"
        title="PoC 详情"
        placement="right"
        width="600"
    >
      <a-descriptions bordered :column="1" size="small" v-if="selectedPoc" style="word-break: break-all;">
        <a-descriptions-item v-for="(value, key) in formatPoc(selectedPoc)" :key="key" :label="formatKey(key)">
          <template v-if="Array.isArray(value)">
            <a-tag v-for="item in value" :key="item" color="blue" style="margin-bottom: 4px;">{{ item }}</a-tag>
          </template>
          <template v-else-if="typeof value === 'object' && value !== null">
            <pre style="margin: 0; white-space: pre-wrap; font-size: 12px; background: var(--arl-bg-light); padding: 8px; border-radius: 4px;">{{ JSON.stringify(value, null, 2) }}</pre>
          </template>
          <template v-else>
            {{ value || '-' }}
          </template>
        </a-descriptions-item>
      </a-descriptions>
    </a-drawer>

    <!-- 源码编辑弹窗 -->
    <a-modal v-model:open="isEditModalVisible" :title="`编辑源码 - ${currentEditPluginName}`" width="800px" @ok="savePocSource" :confirmLoading="saveLoading" ok-text="保存" cancel-text="取消">
      <div style="border: 1px solid var(--arl-border-color); border-radius: 4px; overflow: hidden; text-align: left;">
        <codemirror
          v-model="currentEditSourceCode"
          placeholder="正在加载源码..."
          :style="{ height: '500px', fontSize: '14px' }"
          :autofocus="true"
          :indent-with-tab="true"
          :tab-size="4"
          :extensions="editExtensions"
        />
      </div>
    </a-modal>

    <!-- 新建 PoC 弹窗 -->
    <a-modal v-model:open="isCreateModalVisible" title="新建 PoC" width="800px" @ok="createPocSource" :confirmLoading="createLoading" ok-text="保存" cancel-text="取消">
      <div style="margin-bottom: 16px; display: flex; gap: 16px; align-items: center;">
        <a-input v-model:value="createForm.plugin_name" placeholder="插件文件名 (如: poc_test_vuln)" style="flex: 1;">
          <template #addonAfter>
            <a style="cursor: pointer; " @click="generateFilename">生成名称</a>
          </template>
        </a-input>
        <a-select v-model:value="createForm.templateType" style="width: 180px;" @change="handleTemplateChange">
          <a-select-option value="python_default">通用 Python PoC</a-select-option>
          <a-select-option value="python_brute">Python 弱口令</a-select-option>
        </a-select>
      </div>
      <div style="border: 1px solid var(--arl-border-color); border-radius: 4px; overflow: hidden; text-align: left;">
        <codemirror
          v-model="createForm.content"
          placeholder="在这里编写您的 PoC 代码..."
          :style="{ height: '500px', fontSize: '14px' }"
          :autofocus="true"
          :indent-with-tab="true"
          :tab-size="4"
          :extensions="editExtensions"
          @change="saveDraft"
        />
      </div>
    </a-modal>

  </div>
</template>

<script setup>

import { ref, reactive, onMounted, watch } from 'vue';
import { useSticky } from '../utils/useSticky';
const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

import { Codemirror } from 'vue-codemirror';
import { python } from '@codemirror/lang-python';
import { oneDark } from '@codemirror/theme-one-dark';
import request from '../utils/request';
import { message } from 'ant-design-vue';
import { SearchOutlined, InboxOutlined } from '@ant-design/icons-vue';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';

const editExtensions = [python(), oneDark];

const loading = ref(false);
const syncLoading = ref(false);
const deleteLoading = ref(false);

const dataSource = ref([]);
const selectedRowKeys = ref([]);
const selectedPluginNames = ref([]);

const onSelectChange = (keys, rows) => {
  selectedRowKeys.value = keys;
  selectedPluginNames.value = rows.map(r => r.plugin_name);
};

const isImportModalVisible = ref(false);
const isDetailDrawerVisible = ref(false);
const selectedPoc = ref(null);

const isEditModalVisible = ref(false);
const currentEditPluginName = ref('');
const currentEditSourceCode = ref('');
const saveLoading = ref(false);

const editPocSource = async (record) => {
  currentEditPluginName.value = record.plugin_name;
  currentEditSourceCode.value = '加载中...';
  isEditModalVisible.value = true;
  
  try {
    const res = await request.get('/poc/source/', { params: { plugin_name: record.plugin_name } });
    if (res.code === 200) {
      currentEditSourceCode.value = res.data?.content || res.content || '';
    } else {
      message.error('获取源码失败: ' + (res.message || res.error || '未知错误'));
      isEditModalVisible.value = false;
    }
  } catch (error) {
    message.error('请求异常');
    isEditModalVisible.value = false;
  }
};

const savePocSource = async () => {
  saveLoading.value = true;
  try {
    const res = await request.post('/poc/source/', {
      plugin_name: currentEditPluginName.value,
      content: currentEditSourceCode.value
    });
    if (res.code === 200) {
      message.success('保存成功，已同步');
      isEditModalVisible.value = false;
      onSearch(); // 刷新列表
    } else {
      message.error('保存失败: ' + (res.message || res.error || '未知错误'));
    }
  } catch (error) {
    message.error('请求异常，保存失败');
  } finally {
    saveLoading.value = false;
  }
};

// ================= 新建 PoC 逻辑 =================
const isCreateModalVisible = ref(false);
const createLoading = ref(false);
const createForm = reactive({
  plugin_name: '',
  ext: '.py',
  templateType: 'python_default',
  content: ''
});

const templates = {
  python_default: {
    ext: '.py',
    content: `from xing.core.BasePlugin import BasePlugin
from xing.utils import http_req
from xing.core import PluginType, SchemeType

class Plugin(BasePlugin):
    def __init__(self):
        super(Plugin, self).__init__()
        self.plugin_type = PluginType.POC
        self.vul_name = "【必填】此处填写漏洞名称"
        self.app_name = "【必填】应用名称"
        self.scheme = [SchemeType.HTTPS, SchemeType.HTTP]
        
        self.author = "作者"
        self.severity = "High"
        self.description = "描述"

    def verify(self, target):
        url = target + "/vuln_path"
        conn = http_req(url)
        if conn.status_code == 200 and b"vuln_keyword" in conn.content:
            self.logger.success("发现漏洞 {}".format(target))
            return url
`
  },
  python_brute: {
    ext: '.py',
    content: `from xing.core.BasePlugin import BasePlugin
from xing.core import PluginType, SchemeType

class Plugin(BasePlugin):
    def __init__(self):
        super(Plugin, self).__init__()
        self.plugin_type = PluginType.POC
        self.vul_name = "【必填】弱口令"
        self.app_name = "【必填】应用"
        self.scheme = [SchemeType.HTTPS, SchemeType.HTTP]

    def verify(self, target):
        # 实现爆破逻辑
        pass
`
  }
};

const handleTemplateChange = () => {
  const tpl = templates[createForm.templateType];
  if (tpl) {
    createForm.ext = tpl.ext;
    createForm.content = tpl.content;
    saveDraft();
  }
};

const generateFilename = () => {
  const ts = new Date().getTime();
  createForm.plugin_name = `poc_${ts}`;
};

const saveDraft = () => {
  localStorage.setItem('poc_draft_name', createForm.plugin_name);
  localStorage.setItem('poc_draft_ext', createForm.ext);
  localStorage.setItem('poc_draft_type', createForm.templateType);
  localStorage.setItem('poc_draft_content', createForm.content);
};

const openCreateModal = () => {
  // 恢复草稿或应用默认模板
  const draftContent = localStorage.getItem('poc_draft_content');
  if (draftContent) {
    createForm.plugin_name = localStorage.getItem('poc_draft_name') || '';
    createForm.ext = localStorage.getItem('poc_draft_ext') || '.py';
    createForm.templateType = localStorage.getItem('poc_draft_type') || 'python_default';
    createForm.content = draftContent;
  } else {
    createForm.plugin_name = '';
    createForm.templateType = 'python_default';
    handleTemplateChange();
  }
  isCreateModalVisible.value = true;
};

const createPocSource = async () => {
  if (!createForm.plugin_name || !createForm.content) {
    message.warning('插件名称和内容不能为空');
    return;
  }
  if (!/^[a-zA-Z0-9_]+$/.test(createForm.plugin_name)) {
    message.warning('插件名称只能包含字母、数字和下划线');
    return;
  }
  
  createLoading.value = true;
  try {
    const res = await request.post('/poc/create/', {
      plugin_name: createForm.plugin_name,
      content: createForm.content,
      ext: createForm.ext
    });
    if (res.code === 200) {
      message.success('新建成功，已同步');
      isCreateModalVisible.value = false;
      // 清除草稿
      localStorage.removeItem('poc_draft_name');
      localStorage.removeItem('poc_draft_ext');
      localStorage.removeItem('poc_draft_type');
      localStorage.removeItem('poc_draft_content');
      onSearch(); // 刷新列表
    } else {
      message.error('新建失败: ' + (res.message || res.error || '未知错误'));
    }
  } catch (error) {
    message.error('请求异常，新建失败');
  } finally {
    createLoading.value = false;
  }
};

const showPocDetail = (record) => {
  selectedPoc.value = record;
  isDetailDrawerVisible.value = true;
};

const formatPoc = (poc) => {
  if (!poc) return {};
  const { _id, index, ...rest } = poc; // ignore internal fields
  return rest;
};

const formatKey = (key) => {
  const map = {
    vul_name: '漏洞名称',
    app_name: '应用',
    category: '类别',
    scheme: '协议',
    update_date: '更新时间',
    plugin_type: '插件类型',
    author: '作者',
    desc: '描述',
    description: '描述',
    references: '参考链接',
    severity: '危险级别'
  };
  return map[key] || key;
};

const uploadHeaders = {
  Token: localStorage.getItem('token') || ''
};

const handleUploadChange = (info) => {
  const status = info.file.status;
  if (status === 'done') {
    const res = info.file.response;
    if (res.code === 200) {
      if (res.data.fail_count > 0) {
         message.warning(`${info.file.name} 导入存在失败：${res.data.fail_details[0].reason}`);
      } else {
         message.success(`${info.file.name} 导入并同步成功`);
      }
      onSearch();
    } else {
      message.error(`${info.file.name} 导入失败: ${res.message}`);
    }
  } else if (status === 'error') {
    message.error(`${info.file.name} 上传异常`);
  }
};

const downloadTemplate = () => {
  const templateStr = `from xing.core.BasePlugin import BasePlugin
from xing.utils import http_req
from xing.core import PluginType, SchemeType

class Plugin(BasePlugin):
    def __init__(self):
        super(Plugin, self).__init__()
        self.plugin_type = PluginType.POC
        self.vul_name = "【必填】此处填写漏洞名称"
        self.app_name = "【必填】应用名称"
        self.scheme = [SchemeType.HTTPS, SchemeType.HTTP]
        
        # 富文本详情元数据 (选填)
        self.author = "作者名称"
        self.severity = "High" # High, Medium, Low, Critical
        self.description = "漏洞产生的原因及详细描述"
        self.remediation = "升级至 xxx 版本，或修改 xxx 配置"
        self.references = ["https://cve.mitre.org/..."]


    def verify(self, target):
        # 1. 构造漏洞验证 URL
        url = target + "/vuln_path"
        
        # 2. 发送请求
        conn = http_req(url)
        content = conn.content
        
        # 3. 判断是否触发漏洞
        if conn.status_code == 200 and b"vuln_keyword" in content:
            self.logger.success("发现漏洞 {}".format(self.target))
            return url
`;
  const blob = new Blob([templateStr], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'poc_template.py';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
};

const searchForm = reactive({ vul_name: '', app_name: '', category: '', scheme: '' });
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

watch(() => pagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});

watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
});

const columns = [
  { title: '序号', key: 'index', width: 80, align: 'center' },
  { title: '漏洞名称', dataIndex: 'vul_name', key: 'vul_name', width: 300 },
  { title: '应用', dataIndex: 'app_name', key: 'app_name', width: 200 },
  { title: '类别', dataIndex: 'category', key: 'category', width: 150 },
  { title: '协议', dataIndex: 'scheme', key: 'scheme', width: 150 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 200 },
  { title: '操作', key: 'action', width: 100, align: 'center' }
];

// ================= 数据拉取 =================
const fetchData = async () => {
  loading.value = true;
  try {
    const params = {
      page: pagination.current,
      size: pagination.pageSize,
      ts: Date.now() // 🚨 完美还原抓包中的时间戳细节
    };

    // 动态拼接搜索条件
    if (searchForm.vul_name) params.vul_name = searchForm.vul_name;
    if (searchForm.app_name) params.app_name = searchForm.app_name;
    if (searchForm.category) params.category = searchForm.category;
    if (searchForm.scheme) params.scheme = searchForm.scheme;

    const res = await request.get('/poc/', { params });
    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
    }
  } catch (error) {
    message.error('加载 PoC 数据失败');
  } finally {
    loading.value = false;
  }
};

const onSearch = () => { pagination.current = 1; fetchData(); };
const resetSearch = () => {
  searchForm.vul_name = '';
  searchForm.app_name = '';
  searchForm.category = '';
  searchForm.scheme = '';
  onSearch();
};
const handleTableChange = (page, pageSize) => { pagination.current = page; pagination.pageSize = pageSize; fetchData(); };

// ================= 同步更新逻辑 =================
const handleSync = async () => {
  syncLoading.value = true;
  try {
    const res = await request.get('/poc/sync/'); // 根据抓包，同步是一个无 payload 的 POST 请求
    if (res.code === 200) {
      message.success(`更新成功！共拉取 ${res.data?.plugin_cnt || 0} 个插件`);
      onSearch(); // 刷新列表
    } else {
      message.error('更新失败: ' + res.message);
    }
  } catch (error) {
    message.error('请求异常，更新失败');
  } finally {
    syncLoading.value = false;
  }
};

// ================= 批量删除逻辑 =================
const handleBatchDelete = async () => {
  if (selectedPluginNames.value.length === 0) return;
  deleteLoading.value = true;
  try {
    const res = await request.post('/poc/delete/', { plugin_names: selectedPluginNames.value });
    if (res.code === 200) {
      message.success(`批量删除成功，共删除 ${res.data?.delete_cnt || 0} 个插件`);
      selectedRowKeys.value = [];
      selectedPluginNames.value = [];
      onSearch();
    } else {
      message.error('删除失败: ' + res.message);
    }
  } catch (error) {
    message.error('请求异常，删除失败');
  } finally {
    deleteLoading.value = false;
  }
};
onMounted(() => { fetchData(); });
</script>

<style scoped>
.search-row { display: flex; flex-wrap: wrap; gap: 16px 12px; align-items: center; }
.search-item { display: flex; align-items: center; }
.search-item .label { color: var(--arl-text-color); margin-right: 8px; min-width: 60px; text-align: right; white-space: nowrap; }
</style>