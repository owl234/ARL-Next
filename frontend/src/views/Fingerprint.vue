<template>
  <div style="background-color: #fff; padding: 24px; min-height: calc(100vh - 64px);">

    <div class="search-row" style="margin-bottom: 20px;">
      <a-button type="primary" style="background-color: #00bcd4; border-color: #00bcd4;" @click="openAddModal">添加指纹</a-button>

      <div class="search-item" style="margin-left: 16px;">
        <span class="label">名称：</span>
        <a-input v-model:value="searchForm.name" placeholder="请输入名称进行搜索" style="width: 220px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
        </a-input>
      </div>

      <div class="search-item">
        <span class="label">规则：</span>
        <a-input v-model:value="searchForm.rule" placeholder="请输入规则进行搜索" style="width: 220px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
        </a-input>
      </div>
    </div>

    <div style="margin-bottom: 16px; display: flex; gap: 8px;">

      <a-popconfirm
          title="确认删除所选数据吗？"
          ok-text="确认"
          cancel-text="取消"
          @confirm="handleBatchDelete"
          :disabled="!hasSelected"
      >
        <a-button :disabled="!hasSelected">批量删除</a-button>
      </a-popconfirm>

      <a-button @click="handleExport" type="primary" style="background-color: #52c41a; border-color: #52c41a;">一键全部导出</a-button>
      <a-upload
          name="file"
          :show-upload-list="false"
          :customRequest="handleUpload"
          accept=".json,.yaml,.yml"
      >
        <a-button>上传指纹</a-button>
      </a-upload>
      <a-button @click="handleSync" type="primary" style="background-color: #faad14; border-color: #faad14;" :loading="syncLoading">同步到webapp.json</a-button>
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
      <template #emptyText>
        <div style="padding: 40px 0;">
          <inbox-outlined style="font-size: 48px; color: #d9d9d9;" />
          <div style="color: #999; margin-top: 8px;">暂无数据</div>
        </div>
      </template>

      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'action'">
          <span style="color: #00bcd4; cursor: pointer; margin-right: 8px;" @click="openEditModal(record)">编辑</span>
          <span style="color: #ff4d4f; cursor: pointer;" @click="handleDelete(record)">删除</span>
        </template>
      </template>
    </a-table>

    <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
      <div style="color: rgba(0,0,0,.65);">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
      <a-pagination v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" />
    </div>


    <a-modal
        v-model:open="addModalVisible"
        title="添加指纹"
        @ok="submitAdd"
        :confirmLoading="addLoading"
        width="520px"
        okText="确定"
        cancelText="取消"
        destroyOnClose
    >
      <a-form :model="addForm" :label-col="{ span: 4 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">
        <a-form-item label="名称" required>
          <a-input v-model:value="addForm.name" placeholder="请输入名称" />
        </a-form-item>

        <a-form-item label="规则" required>
          <a-textarea
              v-model:value="addForm.human_rule"
              :rows="4"
              placeholder='只支持body, title, header, icon_hash 四个字段，仅仅可以使用逻辑或， 如 body="Powered by WordPress"'
          />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed } from 'vue';
import request from '../utils/request';
import { message } from 'ant-design-vue';
import { SearchOutlined, InboxOutlined } from '@ant-design/icons-vue';

const loading = ref(false);
const dataSource = ref([]);
const searchForm = reactive({ name: '', rule: '' });
const pagination = reactive({ current: 1, pageSize: 10, total: 0 });
const syncLoading = ref(false);

// 表格多选逻辑
const selectedRowKeys = ref([]);
const hasSelected = computed(() => selectedRowKeys.value.length > 0);
const onSelectChange = (keys) => { selectedRowKeys.value = keys; };

// 🚨 修正：原版 UI 没有“操作”列，且规则对应字段为 human_rule
const columns = [
  { title: '名称', dataIndex: 'name', key: 'name', width: 250 },
  { title: '规则', dataIndex: 'human_rule', key: 'human_rule', width: 500 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 200 }
];

// ================= 数据拉取 =================
const fetchData = async () => {
  loading.value = true;
  try {
    const params = {
      page: pagination.current,
      size: pagination.pageSize,
      order_name: 'update_date' // 默认排序
    };

    if (searchForm.name) params.name = searchForm.name;
    if (searchForm.rule) params.rule = searchForm.rule; // 新增：根据规则搜索

    const res = await request.get('/fingerprint/', { params });
    if (res.code === 200) {
      dataSource.value = res.items || [];
      pagination.total = res.total || 0;
      selectedRowKeys.value = []; // 拉取新数据后清空选中
    }
  } catch (error) {
    message.error('加载指纹数据失败');
  } finally {
    loading.value = false;
  }
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
    return message.warning('请填写完整的名称和规则！');
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
      message.success('添加指纹成功！');
      addModalVisible.value = false;
      // 添加成功后自动刷新列表并重置页码
      pagination.current = 1;
      fetchData();
    } else {
      message.error('添加失败: ' + res.message);
    }
  } catch (error) {
    message.error('请求异常，添加失败');
  } finally {
    addLoading.value = false;
  }
};
// ================= 批量删除逻辑 =================
const handleBatchDelete = async () => {
  if (selectedRowKeys.value.length === 0) return;

  try {
    // 🚨 核心对齐：指纹管理的删除参数名叫 _id，且必须是数组
    const payload = {
      _id: selectedRowKeys.value
    };

    const res = await request.post('/fingerprint/delete/', payload);

    if (res.code === 200) {
      message.success('批量删除成功！');

      // 体验优化：如果当前页的数据被全部删光了，且当前不是第一页，则自动退回上一页
      if (dataSource.value.length === selectedRowKeys.value.length && pagination.current > 1) {
        pagination.current -= 1;
      }

      // 清空选中项并刷新列表
      selectedRowKeys.value = [];
      fetchData();
    } else {
      message.error('删除失败: ' + res.message);
    }
  } catch (error) {
    message.error('请求异常，批量删除失败');
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

    message.success('指纹导出成功！');
  } catch (error) {
    message.error('导出请求异常');
  }
};
// ================= 同步指纹逻辑 =================
const handleSync = async () => {
  syncLoading.value = true;
  try {
    const res = await request.post('/fingerprint/sync/');
    if (res.code === 200) {
      message.success(res.data?.msg || '同步成功！');
    } else {
      message.error('同步失败: ' + res.message);
    }
  } catch (error) {
    message.error('请求异常，同步失败');
  } finally {
    syncLoading.value = false;
  }
};
// ================= 上传指纹逻辑 =================
const handleUpload = async (options) => {
  const { file, onSuccess, onError } = options;

  // 组装 multipart/form-data 格式数据
  const formData = new FormData();
  formData.append('file', file);

  const hide = message.loading('正在上传并解析指纹数据...', 0);
  try {
    // Axios 会自动识别 FormData 并设置正确的带 Boundary 的 Content-Type
    const res = await request.post('/fingerprint/upload/', formData);

    if (res.code === 200) {
      const { success_cnt, repeat_cnt, error_cnt } = res.data || {};
      message.success(`上传完毕！新增: ${success_cnt || 0}，重复: ${repeat_cnt || 0}，失败: ${error_cnt || 0}`);

      onSuccess(res, file);

      // 上传成功后，重置回第一页并拉取最新数据
      pagination.current = 1;
      fetchData();
    } else {
      message.error('上传失败: ' + res.message);
      onError(new Error(res.message));
    }
  } catch (error) {
    message.error('请求异常，上传失败');
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
</script>

<style scoped>
.search-row { display: flex; flex-wrap: wrap; gap: 16px 12px; align-items: center; }
.search-item { display: flex; align-items: center; }
.search-item .label { color: rgba(0,0,0,0.85); margin-right: 8px; min-width: 40px; text-align: right; white-space: nowrap; }
</style>