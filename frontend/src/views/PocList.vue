<template>
  <div style="background-color: #fff; padding: 24px; min-height: calc(100vh - 64px);">

    <div style="display: flex; align-items: center; margin-bottom: 20px; gap: 16px;">
      <a-button type="primary" style="background-color: #00bcd4; border-color: #00bcd4;" :loading="syncLoading" @click="handleSync">更新</a-button>
      <a-button type="primary" style="background-color: #00bcd4; border-color: #00bcd4;" @click="isImportModalVisible = true">导入 PoC</a-button>
      <a-button type="primary" style="background-color: #00bcd4; border-color: #00bcd4;" @click="downloadTemplate">下载模板</a-button>

      <a-popconfirm
          title="确认清空所有 PoC 数据吗？"
          ok-text="确认"
          cancel-text="取消"
          @confirm="handleClear"
      >
        <a-button type="primary" style="background-color: #00bcd4; border-color: #00bcd4;" :loading="clearLoading">清空</a-button>
      </a-popconfirm>
    </div>

    <div class="search-row" style="margin-bottom: 20px; background-color: #f9f9f9; padding: 16px; border-radius: 4px;">
      <div class="search-item">
        <span class="label">漏洞名称：</span>
        <a-input v-model:value="searchForm.vul_name" placeholder="请输入漏洞名称进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
        </a-input>
      </div>
      <div class="search-item">
        <span class="label">应用：</span>
        <a-input v-model:value="searchForm.app_name" placeholder="请输入应用进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
        </a-input>
      </div>
      <div class="search-item">
        <span class="label">类别：</span>
        <a-input v-model:value="searchForm.category" placeholder="请输入类别进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
        </a-input>
      </div>
      <div class="search-item">
        <span class="label">协议：</span>
        <a-input v-model:value="searchForm.scheme" placeholder="请输入协议进行搜索" style="width: 200px;" allowClear @pressEnter="onSearch">
          <template #suffix><search-outlined @click="onSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
        </a-input>
      </div>
    </div>

    <a-table
        :loading="loading"
        :dataSource="dataSource"
        :columns="columns"
        :pagination="false"
        size="middle"
        :rowKey="(record) => record._id"
    >
      <template #bodyCell="{ column, index }">
        <template v-if="column.key === 'index'">
          <span>{{ (pagination.current - 1) * pagination.pageSize + index + 1 }}</span>
        </template>
      </template>
      <template #emptyText>
        <div style="padding: 40px 0;">
          <inbox-outlined style="font-size: 48px; color: #d9d9d9;" />
          <div style="color: #999; margin-top: 8px;">暂无数据</div>
        </div>
      </template>
    </a-table>

    <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
      <div style="color: rgba(0,0,0,.65);">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
      <a-pagination v-model:current="pagination.current" v-model:pageSize="pagination.pageSize" :total="pagination.total" show-size-changer @change="handleTableChange" />
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

  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue';
import request from '../utils/request';
import { message } from 'ant-design-vue';
import { SearchOutlined, InboxOutlined } from '@ant-design/icons-vue';

const loading = ref(false);
const syncLoading = ref(false);
const clearLoading = ref(false);
const dataSource = ref([]);

const isImportModalVisible = ref(false);
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
const pagination = reactive({ current: 1, pageSize: 10, total: 0 });

const columns = [
  { title: '序号', key: 'index', width: 80, align: 'center' },
  { title: '漏洞名称', dataIndex: 'vul_name', key: 'vul_name', width: 300 },
  { title: '应用', dataIndex: 'app_name', key: 'app_name', width: 200 },
  { title: '类别', dataIndex: 'category', key: 'category', width: 150 },
  { title: '协议', dataIndex: 'scheme', key: 'scheme', width: 150 },
  { title: '更新时间', dataIndex: 'update_date', key: 'update_date', width: 200 }
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

// ================= 清空逻辑 =================
const handleClear = async () => {
  clearLoading.value = true;
  try {
    const res = await request.get('/poc/delete/'); // 根据抓包，清空也是一个无 payload 的 POST 请求
    if (res.code === 200) {
      message.success(`清空成功！共删除 ${res.data?.delete_cnt || 0} 个插件`);
      onSearch(); // 刷新列表
    } else {
      message.error('清空失败: ' + res.message);
    }
  } catch (error) {
    message.error('请求异常，清空失败');
  } finally {
    clearLoading.value = false;
  }
};

onMounted(() => { fetchData(); });
</script>

<style scoped>
.search-row { display: flex; flex-wrap: wrap; gap: 16px 12px; align-items: center; }
.search-item { display: flex; align-items: center; }
.search-item .label { color: rgba(0,0,0,0.85); margin-right: 8px; min-width: 60px; text-align: right; white-space: nowrap; }
</style>