<template>
  <div class="arl-page-container">
    <a-tabs v-model:activeKey="mainTab" size="large" style="margin-bottom: 12px;">
      <a-tab-pane key="arl" :tab="pageText('pages.arlPluginsPython')">
        <!-- 吸顶 Hero 操作卡片 -->
        <div ref="actionBarRef" class="arl-hero-card">
          <div class="arl-toolbar-row">
            <!-- 左侧：紧凑搜索条件与重置 -->
            <div class="arl-filter-group">
              <div class="arl-filter-item">
                <span class="arl-filter-label">{{ pageText('pages.vulnerabilityName') }}</span>
                <a-input
                  v-model:value="searchForm.vul_name"
                  :placeholder="pageText('pages.enterAVulnerabilityName')"
                  style="width: 160px;"
                  allowClear
                  size="small"
                  @pressEnter="onSearch"
                >
                  <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
                </a-input>
              </div>
              <div class="arl-filter-item">
                <span class="arl-filter-label">{{ pageText('pages.application') }}</span>
                <a-input
                  v-model:value="searchForm.app_name"
                  :placeholder="pageText('pages.enterAnApplication')"
                  style="width: 140px;"
                  allowClear
                  size="small"
                  @pressEnter="onSearch"
                >
                  <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
                </a-input>
              </div>
              <div class="arl-filter-item">
                <span class="arl-filter-label">{{ pageText('pages.category') }}</span>
                <a-input
                  v-model:value="searchForm.category"
                  :placeholder="pageText('pages.enterACategory')"
                  style="width: 130px;"
                  allowClear
                  size="small"
                  @pressEnter="onSearch"
                >
                  <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
                </a-input>
              </div>
              <div class="arl-filter-item">
                <span class="arl-filter-label">{{ pageText('pages.protocol') }}</span>
                <a-input
                  v-model:value="searchForm.scheme"
                  :placeholder="pageText('pages.enterAProtocol')"
                  style="width: 120px;"
                  allowClear
                  size="small"
                  @pressEnter="onSearch"
                >
                  <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
                </a-input>
              </div>

              <a-button size="small" @click="resetSearch">
                <template #icon><undo-outlined /></template>
                {{ pageText('assets.reset') }}
              </a-button>
            </div>

            <!-- 右侧：单一主要操作 + 次要操作组 + 批量动作 -->
            <div class="arl-actions-group">
              <a-button type="primary" size="small" @click="openCreateModal">
                <template #icon><plus-outlined /></template>
                {{ pageText('pages.newPoc') }}
              </a-button>

              <a-button size="small" @click="isImportModalVisible = true">
                <template #icon><upload-outlined /></template>
                {{ pageText('pages.importPocs') }}
              </a-button>

              <a-button size="small" @click="downloadTemplate">
                <template #icon><download-outlined /></template>
                {{ pageText('pages.downloadTemplate') }}
              </a-button>

              <a-tooltip :title="pageText('pages.scanDiskAndSynchronizePocPluginsToTheDatabase')">
                <a-button size="small" :loading="syncLoading" @click="handleSync">
                  <template #icon><sync-outlined /></template>
                  {{ pageText('pages.syncPlugins') }}
                </a-button>
              </a-tooltip>

              <a-popconfirm
                :title="pageText('pages.deleteTheSelectedPocs')"
                :ok-text="pageText('assets.confirm')"
                :cancel-text="pageText('tasks.cancel')"
                @confirm="handleBatchDelete"
                :disabled="selectedRowKeys.length === 0"
              >
                <a-button danger size="small" :disabled="selectedRowKeys.length === 0" :loading="deleteLoading">
                  <template #icon><delete-outlined /></template>
                  {{ pageText('tasks.deleteSelected') }}
                </a-button>
              </a-popconfirm>
            </div>
          </div>
        </div>

        <!-- 表格：统一小尺寸 -->
        <a-table
          :sticky="stickyConfig"
          :loading="loading"
          :dataSource="dataSource"
          :columns="columns"
          :pagination="false"
          size="small"
          :rowKey="(record) => record._id"
          :rowSelection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange, preserveSelectedRowKeys: true }"
        >
          <template #bodyCell="{ column, record, index }">
            <template v-if="column.key === 'index'">
              <span>{{ (pagination.current - 1) * pagination.pageSize + index + 1 }}</span>
            </template>
            <template v-if="column.key === 'vul_name'">
              <a @click="showPocDetail(record)" style="font-weight: 500;">{{ record.vul_name }}</a>
            </template>
            <template v-if="column.key === 'action'">
              <a @click="editPocSource(record)">{{ pageText('pages.editSource') }}</a>
            </template>
          </template>
          <template #emptyText>
            <ArlEmpty :description="pageText('tasks.noData')" />
          </template>
        </a-table>

        <!-- 统一微型分页栏 -->
        <div class="arl-pagination-bar">
          <div class="pagination-info">{{ pageText('tasks.paginationSummary', { pages: Math.ceil(pagination.total / pagination.pageSize) || 1, total: pagination.total }) }}</div>
          <a-pagination
            :pageSizeOptions="$pageSizeOptions"
            v-model:current="pagination.current"
            v-model:pageSize="pagination.pageSize"
            :total="pagination.total"
            show-size-changer
            size="small"
            @change="handleTableChange"
            @showSizeChange="handleTableChange"
          />
        </div>

    <!-- 导入 PoC 弹窗 -->
    <a-modal v-model:open="isImportModalVisible" :title="pageText('pages.importPocFiles')" :footer="null">
      <a-upload-dragger
        name="file"
        :multiple="true"
        action="/api/poc/import/"
        :headers="uploadHeaders"
        accept=".py"
        @change="handleUploadChange"
      >
        <p class="ant-upload-drag-icon"><inbox-outlined /></p>
        <p class="ant-upload-text">{{ pageText('pages.clickOrDragFilesHereToUpload') }}</p>
        <p class="ant-upload-hint">{{ pageText('pages.uploadOneOrMoreFilesOnlyPyScriptsAre') }}</p>
      </a-upload-dragger>
      <div style="margin-top: 12px; display: flex; justify-content: flex-end; align-items: center; font-size: 13px;">
        <span class="page-muted">{{ pageText('pages.needAStandardScriptExample') }}</span>
        <a @click="downloadTemplate" style="margin-left: 6px; font-weight: 500;">
          <download-outlined /> {{ pageText('pages.downloadStandardPocTemplate') }}
        </a>
      </div>
    </a-modal>

    <!-- 详情抽屉 -->
    <a-drawer
        v-model:open="isDetailDrawerVisible"
        :title="pageText('pages.pocDetails')"
        placement="right"
        width="600"
    >
      <a-descriptions bordered :column="1" size="small" v-if="selectedPoc" style="word-break: break-all;">
        <a-descriptions-item v-for="item in formatPoc(selectedPoc)" :key="item.key" :label="item.label">
          <!-- 危险级别：彩色 Tag -->
          <template v-if="item.key === 'severity'">
            <a-tag :color="getSeverityColor(item.value)" style="font-weight: 500;">{{ item.value }}</a-tag>
          </template>

          <!-- 修复建议：高亮提示区块 -->
          <template v-else-if="item.key === 'remediation'">
            <div style="background: var(--arl-theme-soft-bg); border-left: 3px solid var(--arl-theme-color); padding: 8px 12px; border-radius: 4px; color: var(--arl-text-color); white-space: pre-wrap; line-height: 1.6;">
              {{ item.value }}
            </div>
          </template>

          <!-- 描述文本 -->
          <template v-else-if="item.key === 'description' || item.key === 'desc'">
            <div style="white-space: pre-wrap; line-height: 1.6;">{{ item.value }}</div>
          </template>

          <!-- 参考链接：带图标的新窗口跳转链接 -->
          <template v-else-if="item.key === 'references' && Array.isArray(item.value)">
            <div style="display: flex; flex-direction: column; gap: 6px;">
              <a
                v-for="url in item.value"
                :key="url"
                :href="url"
                target="_blank"
                rel="noopener noreferrer"
                style="display: inline-flex; align-items: center; gap: 6px; word-break: break-all; color: var(--arl-theme-color);"
              >
                <link-outlined style="flex-shrink: 0;" />
                <span>{{ url }}</span>
              </a>
            </div>
          </template>

          <!-- 其他数组 -->
          <template v-else-if="Array.isArray(item.value)">
            <a-tag v-for="tag in item.value" :key="tag" color="blue" style="margin-bottom: 4px;">{{ tag }}</a-tag>
          </template>

          <!-- 嵌套对象/JSON -->
          <template v-else-if="typeof item.value === 'object' && item.value !== null">
            <pre style="margin: 0; white-space: pre-wrap; font-size: 12px; background: var(--arl-bg-light); padding: 8px; border-radius: 4px;">{{ JSON.stringify(item.value, null, 2) }}</pre>
          </template>

          <!-- 普通文本/默认 -->
          <template v-else>
            {{ item.value || '-' }}
          </template>
        </a-descriptions-item>
      </a-descriptions>
    </a-drawer>

    <!-- 源码编辑弹窗 -->
    <a-modal v-model:open="isEditModalVisible" :title="pageText('pages.editSourceName', { name: currentEditPluginName })" width="800px" @ok="savePocSource" :confirmLoading="saveLoading" :ok-text="pageText('pages.save')" :cancel-text="pageText('tasks.cancel')">
      <div style="border: 1px solid var(--arl-border-color); border-radius: 4px; overflow: hidden; text-align: left;">
        <codemirror
          v-model="currentEditSourceCode"
          :placeholder="pageText('pages.loadingSource')"
          :style="{ height: '500px', fontSize: '14px' }"
          :autofocus="true"
          :indent-with-tab="true"
          :tab-size="4"
          :extensions="editExtensions"
        />
      </div>
    </a-modal>

    <!-- 新建 PoC 弹窗 -->
    <a-modal v-model:open="isCreateModalVisible" :title="pageText('pages.newPoc')" width="800px" @ok="createPocSource" :confirmLoading="createLoading" :ok-text="pageText('pages.save')" :cancel-text="pageText('tasks.cancel')">
      <div style="margin-bottom: 16px; display: flex; gap: 16px; align-items: center;">
        <a-input v-model:value="createForm.plugin_name" :placeholder="pageText('pages.pluginFilenameEGPocTestVuln')" class="page-fill-space">
          <template #addonAfter>
            <a class="page-clickable-label" @click="generateFilename">{{ pageText('pages.generateName') }}</a>
          </template>
        </a-input>
        <a-select v-model:value="createForm.templateType" style="width: 180px;" @change="handleTemplateChange">
          <a-select-option value="python_default">{{ pageText('pages.generalPythonPoc') }}</a-select-option>
          <a-select-option value="python_brute">{{ pageText('pages.pythonCredentialCheck') }}</a-select-option>
        </a-select>
      </div>
      <div style="border: 1px solid var(--arl-border-color); border-radius: 4px; overflow: hidden; text-align: left;">
        <codemirror
          v-model="createForm.content"
          :placeholder="pageText('pages.writeYourPocCodeHere')"
          :style="{ height: '500px', fontSize: '14px' }"
          :autofocus="true"
          :indent-with-tab="true"
          :tab-size="4"
          :extensions="editExtensions"
          @change="saveDraft"
        />
      </div>
    </a-modal>
      </a-tab-pane>

      <!-- Nuclei 模板中心 -->
      <a-tab-pane key="nuclei" :tab="pageText('pages.nucleiTemplatesYaml')">
        <NucleiManage />
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';
defineOptions({ name: 'PocList' });

import { ref, reactive, onMounted, onDeactivated, watch } from 'vue';
import { useRoute } from 'vue-router';
import NucleiManage from '../components/NucleiManage.vue';
import { useSticky } from '../utils/useSticky';
const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

const route = useRoute();
const mainTab = ref(route.query.tab === 'nuclei' ? 'nuclei' : 'arl');

watch(() => route.query.tab, (newTab) => {
  if (newTab === 'nuclei' || newTab === 'arl') {
    mainTab.value = newTab;
  }
});

import { Codemirror } from 'vue-codemirror';
import { python } from '@codemirror/lang-python';
import { oneDark } from '@codemirror/theme-one-dark';
import request from '../utils/request';
import { message } from 'ant-design-vue';
import { SearchOutlined, InboxOutlined, LinkOutlined, SyncOutlined, DownloadOutlined, PlusOutlined, UploadOutlined, DeleteOutlined, UndoOutlined } from '@ant-design/icons-vue';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';

const { t: pageText } = useI18n({ useScope: 'global' });

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
  currentEditSourceCode.value = pageText('pages.loading');
  isEditModalVisible.value = true;
  
  try {
    const res = await request.get('/poc/source/', { params: { plugin_name: record.plugin_name } });
    if (res.code === 200) {
      currentEditSourceCode.value = res.data?.content || res.content || '';
    } else {
      message.error(pageText('pages.failedToLoadSource') + (res.message || res.error || pageText('tasks.unknownError')));
      isEditModalVisible.value = false;
    }
  } catch (error) {
    message.error(pageText('tasks.requestFailed'));
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
      message.success(pageText('pages.savedAndSynchronized'));
      isEditModalVisible.value = false;
      onSearch(); // 刷新列表
    } else {
      message.error(pageText('pages.failedToSave') + (res.message || res.error || pageText('tasks.unknownError')));
    }
  } catch (error) {
    message.error(pageText('pages.requestFailedChangesWereNotSaved'));
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
        
        # 富文本详情元数据 (选填)
        self.author = "作者名称"
        self.severity = "High"  # Critical, High, Medium, Low
        self.description = "漏洞产生的原因及详细描述"
        self.remediation = "升级至最新版本，或修复相关配置"
        self.references = ["https://cve.mitre.org/..."]

    def verify(self, target):
        # 1. 构造漏洞验证 URL
        url = target + "/vuln_path"

        # 2. 发送探测请求
        conn = http_req(url)

        # 3. 判断是否触发漏洞
        if conn.status_code == 200 and b"vuln_keyword" in conn.content:
            self.logger.success("发现漏洞 {}".format(target))
            return url
`
  },
  python_brute: {
    ext: '.py',
    content: `from xing.core.BasePlugin import BasePlugin
from xing.utils import http_req
from xing.core import PluginType, SchemeType

class Plugin(BasePlugin):
    def __init__(self):
        super(Plugin, self).__init__()
        self.plugin_type = PluginType.BRUTE
        self.vul_name = "【必填】弱口令"
        self.app_name = "【必填】应用名称"
        self.scheme = [SchemeType.HTTPS, SchemeType.HTTP]

        # 爆破字典（必填）：必须是 xing/dicts/ 下真实存在的文件名，
        # 引擎 load_dict 直接 open()，写错会当场报错。此处以 tomcat 字典为示例，请换成目标服务的字典
        self.username_file = "username_tomcat.txt"
        self.password_file = "password_tomcat.txt"

        self.author = "作者名称"
        self.severity = "High"
        self.description = "服务弱口令漏洞"

    def check_app(self, target):
        # 1. 指纹识别：判断目标是否为本插件针对的应用，返回 True 才会进入爆破循环
        url = target + "/login"
        conn = http_req(url)
        if conn.status_code == 200 and b"login" in conn.content:
            return True
        return False

    def login(self, target, user, passwd):
        # 2. 构造登录验证请求
        url = target + "/login"
        payload = {"username": user, "password": passwd}
        conn = http_req(url, "post", json=payload)

        # 3. 验证凭据是否有效 (成功时返回 True)
        if conn.status_code == 200 and b"login success" in conn.content:
            return True
        return False
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
    message.warning(pageText('pages.pluginNameAndContentCannotBeEmpty'));
    return;
  }
  if (!/^[a-zA-Z0-9][a-zA-Z0-9_]*$/.test(createForm.plugin_name)) {
    message.warning(pageText('pages.useOnlyLettersNumbersAndUnderscoresTheFirstCharacter'));
    return;
  }
  
  createLoading.value = true;
  try {
    const res = await request.post('/poc/create/', {
      plugin_name: createForm.plugin_name,
      content: createForm.content,
      ext: createForm.ext,
      plugin_type: createForm.templateType === 'python_brute' ? 'brute' : 'poc'
    });
    if (res.code === 200) {
      message.success(pageText('pages.createdAndSynchronized'));
      isCreateModalVisible.value = false;
      // 清除草稿
      localStorage.removeItem('poc_draft_name');
      localStorage.removeItem('poc_draft_ext');
      localStorage.removeItem('poc_draft_type');
      localStorage.removeItem('poc_draft_content');
      onSearch(); // 刷新列表
    } else {
      message.error(pageText('pages.failedToCreatePluginPrefix') + (res.message || res.error || pageText('tasks.unknownError')));
    }
  } catch (error) {
    message.error(pageText('pages.requestFailedPluginWasNotCreated'));
  } finally {
    createLoading.value = false;
  }
};

const showPocDetail = (record) => {
  selectedPoc.value = record;
  isDetailDrawerVisible.value = true;
};

const getSeverityColor = (sev) => {
  if (!sev) return 'default';
  const s = String(sev).toLowerCase();
  if (s === 'critical') return '#cf1322';
  if (s === 'high') return '#ff4d4f';
  if (s === 'medium') return '#fa8c16';
  if (s === 'low') return '#1890ff';
  return 'blue';
};

const formatKey = (key) => {
  const map = {
    vul_name: pageText('tasks.vulnerabilityName'),
    plugin_name: pageText('pages.pluginName'),
    app_name: pageText('pages.applicationLabel2'),
    severity: pageText('pages.severity'),
    category: pageText('tasks.category'),
    scheme: pageText('tasks.protocol'),
    plugin_type: pageText('pages.pluginType'),
    author: pageText('pages.author'),
    update_date: pageText('assets.updatedAtLabel'),
    desc: pageText('assets.description'),
    description: pageText('assets.description'),
    remediation: pageText('pages.remediation'),
    references: pageText('pages.references')
  };
  return map[key] || key;
};

const formatPoc = (poc) => {
  if (!poc) return [];
  const { _id, index, ...rest } = poc; // 过滤内部无用字段

  const order = [
    'vul_name',
    'plugin_name',
    'app_name',
    'severity',
    'category',
    'scheme',
    'plugin_type',
    'author',
    'update_date',
    'description',
    'desc',
    'remediation',
    'references'
  ];

  // 选填富文本字段：若为空或未定义则智能隐藏，避免大量空白或短横线占用空间
  const optionalFields = ['severity', 'author', 'description', 'desc', 'remediation', 'references'];

  const allKeys = Array.from(new Set([...order, ...Object.keys(rest)]));
  const result = [];

  for (const key of allKeys) {
    if (!(key in rest)) continue;
    const value = rest[key];

    if (optionalFields.includes(key)) {
      if (value === null || value === undefined) continue;
      if (typeof value === 'string' && value.trim() === '') continue;
      if (Array.isArray(value) && value.length === 0) continue;
    }

    result.push({
      key,
      label: formatKey(key),
      value
    });
  }

  return result;
};

const uploadHeaders = {
  Token: localStorage.getItem('token') || ''
};

const handleUploadChange = (info) => {
  const status = info.file.status;
  if (status === 'done') {
    const res = info.file.response;
    if (res && res.code === 200) {
      if (res.data?.fail_count > 0) {
        const detail = res.data.fail_details?.[0];
        const reason = detail?.reason || pageText('pages.validationFailed');
        message.warning(pageText('pages.nameFailedImportValidationReason', { name: info.file.name, reason: reason }), 6);
      } else {
        message.success(pageText('pages.nameImportedAndSynchronized', { name: info.file.name }));
      }
      onSearch();
    } else {
      message.error(pageText('pages.failedToImportNameReason', { name: info.file.name, reason: res?.error || res?.message || pageText('tasks.unknownError') }));
    }
  } else if (status === 'error') {
    message.error(pageText('pages.networkErrorUploadingName', { name: info.file.name }));
  }
};

const downloadTemplate = () => {
  const templateStr = templates.python_default.content;
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
  { get title() { return pageText('tasks.no'); }, key: 'index', width: 80, align: 'center' },
  { get title() { return pageText('tasks.vulnerabilityName'); }, dataIndex: 'vul_name', key: 'vul_name', width: 300 },
  { get title() { return pageText('pages.applicationLabel2'); }, dataIndex: 'app_name', key: 'app_name', width: 200 },
  { get title() { return pageText('tasks.category'); }, dataIndex: 'category', key: 'category', width: 150 },
  { get title() { return pageText('tasks.protocol'); }, dataIndex: 'scheme', key: 'scheme', width: 150 },
  { get title() { return pageText('assets.updatedAtLabel'); }, dataIndex: 'update_date', key: 'update_date', width: 200 },
  { get title() { return pageText('tasks.actions'); }, key: 'action', width: 100, align: 'center' }
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
    message.error(pageText('pages.failedToLoadPocs'));
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

// ================= 同步插件逻辑 =================
const handleSync = async () => {
  syncLoading.value = true;
  try {
    const res = await request.get('/poc/sync/');
    if (res.code === 200) {
      message.success(pageText('pages.synchronizationCompletedPluginsLoadedCount', { count: res.data?.plugin_cnt || 0 }));
      onSearch(); // 刷新列表
    } else {
      message.error(pageText('tasks.syncFailed') + res.message);
    }
  } catch (error) {
    message.error(pageText('pages.requestFailedSynchronizationDidNotComplete'));
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
      message.success(pageText('pages.pluginsDeletedCount', { count: res.data?.delete_cnt || 0 }));
      selectedRowKeys.value = [];
      selectedPluginNames.value = [];
      onSearch();
    } else {
      message.error(pageText('tasks.deletionFailed') + res.message);
    }
  } catch (error) {
    message.error(pageText('assets.requestFailedAssetGroupWasNotDeleted'));
  } finally {
    deleteLoading.value = false;
  }
};
onMounted(() => { fetchData(); });

onDeactivated(() => {
  isImportModalVisible.value = false;
  isDetailDrawerVisible.value = false;
  isEditModalVisible.value = false;
  isCreateModalVisible.value = false;
});
</script>
<style scoped>
.page-muted { color: var(--arl-text-color); opacity: 0.65; }
.page-fill-space { flex: 1; }
.page-clickable-label { cursor: pointer;  }
</style>
