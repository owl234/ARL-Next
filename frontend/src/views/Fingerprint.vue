<template>
  <div class="arl-page-container">
    <!-- 吸顶 Hero 操作卡片 -->
    <div ref="actionBarRef" class="arl-hero-card">
      <div class="arl-toolbar-row">
        <!-- 左侧：紧凑搜索条件与重置 -->
        <div class="arl-filter-group">
          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('tasks.nameLabel') }}</span>
            <a-input
              v-model:value="searchForm.name"
              :placeholder="pageText('pages.enterAFingerprintName')"
              style="width: 180px;"
              allowClear
              size="small"
              @pressEnter="onSearch"
            >
              <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: var(--arl-text-color); opacity: 0.35;" /></template>
            </a-input>
          </div>

          <div class="arl-filter-item">
            <span class="arl-filter-label">{{ pageText('pages.rule') }}</span>
            <a-input
              v-model:value="searchForm.rule"
              :placeholder="pageText('pages.enterRuleContent')"
              style="width: 180px;"
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
          <a-button type="primary" size="small" @click="openAddModal">
            <template #icon><plus-outlined /></template>
            {{ pageText('pages.addFingerprint') }}
          </a-button>

          <a-upload
            name="file"
            :show-upload-list="false"
            :customRequest="handleUpload"
            accept=".json,.yaml,.yml"
          >
            <a-button size="small">
              <template #icon><upload-outlined /></template>
              {{ pageText('pages.uploadFingerprints') }}
            </a-button>
          </a-upload>

          <a-button size="small" @click="handleExport">
            <template #icon><download-outlined /></template>
            {{ pageText('pages.export') }}
          </a-button>

          <a-popconfirm
            :title="pageText('pages.deleteTheSelectedFingerprints')"
            :ok-text="pageText('assets.confirm')"
            :cancel-text="pageText('tasks.cancel')"
            @confirm="handleBatchDelete"
            :disabled="!hasSelected || deleteLoading"
          >
            <a-button danger size="small" :disabled="!hasSelected || deleteLoading" :loading="deleteLoading">
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
      :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }"
      :loading="loading"
      :dataSource="dataSource"
      :columns="columns"
      :pagination="false"
      size="small"
      :rowKey="(record) => record._id"
    >
      <template #emptyText>
        <ArlEmpty :description="pageText('tasks.noData')" />
      </template>

      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'action'">
          <a class="page-action-link" @click="openEditModal(record)">{{ pageText('assets.edit') }}</a>
          <span class="page-danger-link" @click="handleDelete(record)">{{ pageText('tasks.delete') }}</span>
        </template>
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


    <a-modal
        v-model:open="addModalVisible"
        :title="pageText('pages.addFingerprint')"
        @ok="submitAdd"
        :confirmLoading="addLoading"
        width="520px"
        :okText="pageText('pages.confirm')"
        :cancelText="pageText('tasks.cancel')"
        destroyOnClose
    >
      <a-form :label-wrap="true" :model="addForm" :label-col="{ span: pageLocale !== 'zh-CN' ? 6 : 4 }" :wrapper-col="{ span: 18 }" class="page-risk-form">
        <a-form-item :label="pageText('tasks.name')" required>
          <a-input v-model:value="addForm.name" :placeholder="pageText('tasks.enterAName')" />
        </a-form-item>

        <a-form-item :label="pageText('pages.ruleLabel2')" required>
          <a-textarea
              v-model:value="addForm.human_rule"
              :rows="4"
              :placeholder="pageText('pages.onlyBodyTitleHeaderAndIconHashAreSupported')"
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { useI18n } from 'vue-i18n';
defineOptions({ name: 'Fingerprint' });

import { ref, reactive, onMounted, onDeactivated, computed, watch } from 'vue';
import { useSticky } from '../utils/useSticky';
const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

import request from '../utils/request';
import { message } from 'ant-design-vue';
import { SearchOutlined, PlusOutlined, UploadOutlined, DownloadOutlined, DeleteOutlined, UndoOutlined } from '@ant-design/icons-vue';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';

const { t: pageText, locale: pageLocale } = useI18n({ useScope: 'global' });

const loading = ref(false);
const dataSource = ref([]);
const searchForm = reactive({ name: '', rule: '' });
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

watch(() => pagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});

watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
});

// 表格多选逻辑
const selectedRowKeys = ref([]);
const deleteLoading = ref(false);
const hasSelected = computed(() => selectedRowKeys.value.length > 0);
const onSelectChange = (keys) => { selectedRowKeys.value = keys; };

// 🚨 修正：原版 UI 没有“操作”列，且规则对应字段为 human_rule
const columns = [
  { get title() { return pageText('tasks.name'); }, dataIndex: 'name', key: 'name', width: 250 },
  { get title() { return pageText('pages.ruleLabel2'); }, dataIndex: 'human_rule', key: 'human_rule', width: 500 },
  { get title() { return pageText('assets.updatedAtLabel'); }, dataIndex: 'update_date', key: 'update_date', width: 200 }
];

// ================= 数据拉取 =================
const fetchData = async () => {
  loading.value = true;
  try {
    const params = {
      page: pagination.current,
      size: pagination.pageSize,
      order: '-update_date,-_id' // 稳定分页排序，避免同秒 update_date 翻页抖动
    };

    if (searchForm.name) params.name = searchForm.name;
    if (searchForm.rule) params.human_rule = searchForm.rule; // 对齐后端 human_rule 规则模糊查询

    const res = await request.get('/fingerprint/', { params });
    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
      selectedRowKeys.value = []; // 拉取新数据后清空选中
    }
  } catch (error) {
    message.error(pageText('pages.failedToLoadFingerprints'));
  } finally {
    loading.value = false;
  }
};

const resetSearch = () => {
  Object.assign(searchForm, { name: '', rule: '' });
  pagination.current = 1;
  onSearch();
};

const onSearch = () => { pagination.current = 1; fetchData(); };
const handleTableChange = (page, pageSize) => { pagination.current = page; pagination.pageSize = pageSize; fetchData(); };

// ================= 占位函数 =================
// ================= 添加指纹逻辑 =================
const addModalVisible = ref(false);
const addLoading = ref(false);
const addForm = reactive({ name: '', human_rule: '' });

// 打开弹窗并清空表单
const openAddModal = () => {
  addForm.name = '';
  addForm.human_rule = '';
  addModalVisible.value = true;
};

// 提交发包
const submitAdd = async () => {
  if (!addForm.name || !addForm.human_rule) {
    return message.warning(pageText('pages.enterBothANameAndARule'));
  }

  addLoading.value = true;
  try {
    const payload = {
      name: addForm.name,
      human_rule: addForm.human_rule
    };

    // 发起 POST 请求
    const res = await request.post('/fingerprint/', payload);

    if (res.code === 200) {
      message.success(pageText('pages.fingerprintAdded'));
      addModalVisible.value = false;
      // 添加成功后自动刷新列表并重置页码
      pagination.current = 1;
      fetchData();
    } else {
      message.error(pageText('assets.failedToAddTask') + res.message);
    }
  } catch (error) {
    message.error(pageText('pages.requestFailedFingerprintWasNotAdded'));
  } finally {
    addLoading.value = false;
  }
};
// ================= 批量删除逻辑 =================
const handleBatchDelete = async () => {
  if (selectedRowKeys.value.length === 0 || deleteLoading.value) return;

  deleteLoading.value = true;
  try {
    // 🚨 核心对齐：指纹管理的删除参数名叫 _id，且必须是数组
    const payload = {
      _id: selectedRowKeys.value
    };

    const res = await request.post('/fingerprint/delete/', payload);

    if (res.code === 200) {
      message.success(pageText('pages.fingerprintsDeleted'));

      // 体验优化：如果当前页的数据被全部删光了，且当前不是第一页，则自动退回上一页
      if (dataSource.value.length === selectedRowKeys.value.length && pagination.current > 1) {
        pagination.current -= 1;
      }

      // 清空选中项并刷新列表
      selectedRowKeys.value = [];
      await fetchData();
    } else {
      message.error(pageText('tasks.deletionFailed') + res.message);
    }
  } catch (error) {
    message.error(pageText('pages.requestFailedSelectedRecordsWereNotDeleted'));
  } finally {
    deleteLoading.value = false;
  }
};
// ================= 指纹导出逻辑 =================
const handleExport = async () => {
  try {
    // 🚨 根据抓包 Payload 为空，大概率是 GET 请求 (如果后端严格要求 POST，将其改为 request.post 即可)
    const res = await request.get('/fingerprint/export/');

    // 智能处理：如果后端返回的是 YAML/JSON 字符串，直接用；如果是对象，则转为美化后的 JSON 字符串
    const content = typeof res === 'string' ? res : JSON.stringify(res, null, 2);

    // 构造 Blob 文件对象
    const blob = new Blob([content], { type: 'application/json;charset=utf-8' });
    const url = window.URL.createObjectURL(blob);

    // 创建隐形 <a> 标签触发下载
    const link = document.createElement('a');
    link.style.display = 'none';
    link.href = url;
    // 🚨 文件名设定。如果你发现导出的内容确实是 YAML，可以把后缀改为 fingerprint.yaml
    link.download = 'fingerprint.json';

    document.body.appendChild(link);
    link.click();

    // 拔除无用节点，释放内存
    document.body.removeChild(link);
    window.URL.revokeObjectURL(url);

    message.success(pageText('pages.fingerprintsExported'));
  } catch (error) {
    message.error(pageText('pages.exportRequestFailed'));
  }
};
// ================= 上传指纹逻辑 =================
const handleUpload = async (options) => {
  const { file, onSuccess, onError } = options;

  // 组装 multipart/form-data 格式数据
  const formData = new FormData();
  formData.append('file', file);

  const hide = message.loading(pageText('pages.uploadingAndParsingFingerprints'), 0);
  try {
    // Axios 会自动识别 FormData 并设置正确的带 Boundary 的 Content-Type
    const res = await request.post('/fingerprint/upload/', formData);

    if (res.code === 200) {
      const { success_cnt, repeat_cnt, error_cnt } = res.data || {};
      message.success(pageText('pages.uploadCompletedAddedAddedDuplicatesDuplicatesFailedFailed', { added: success_cnt || 0, duplicates: repeat_cnt || 0, failed: error_cnt || 0 }));

      onSuccess(res, file);

      // 上传成功后，重置回第一页并拉取最新数据
      pagination.current = 1;
      fetchData();
    } else {
      message.error(pageText('pages.uploadFailed') + res.message);
      onError(new Error(res.message));
    }
  } catch (error) {
    message.error(pageText('pages.requestFailedUploadDidNotComplete'));
    onError(error);
  } finally {
    hide(); // 关闭 loading 提示
  }
};
const openEditModal = (record) => {};
const handleDelete = (record) => {};

onMounted(() => {
  fetchData();
});

onDeactivated(() => {
  addModalVisible.value = false;
});
</script>
<style scoped>
.page-action-link { cursor: pointer; margin-right: 8px; }
.page-danger-link { color: #ff4d4f; cursor: pointer; }

.page-risk-form { margin-top: 20px; }
</style>
