<template>
  <div style="padding: 24px; background: #fff; min-height: 100%;">
    <h2 style="margin-bottom: 24px;">系统设置</h2>
    
    <a-tabs v-model:activeKey="activeKey">
      <!-- 字典管理 Tab -->
      <a-tab-pane key="dictionary" tab="字典管理">
        <a-spin :spinning="loading">
          <div style="display: flex; gap: 24px; min-height: 500px;">
            <!-- 左侧一键选择菜单 -->
            <div style="width: 280px; flex-shrink: 0;">
              <a-menu 
                v-model:selectedKeys="selectedDictKeys" 
                mode="inline" 
                style="border-right: 1px solid #f0f0f0;"
                @select="handleMenuSelect"
              >
                <a-menu-item-group v-for="(dicts, cat) in groupedDicts" :key="cat" :title="cat">
                  <a-menu-item v-for="dict in dicts" :key="dict.name">
                    <span style="font-size: 14px;">{{ dict.name }}</span>
                    <span style="color: #aaa; font-size: 12px; margin-left: 8px;">{{ (dict.size / 1024).toFixed(1) }} KB</span>
                  </a-menu-item>
                </a-menu-item-group>
              </a-menu>
            </div>

            <!-- 右侧操作区 -->
            <div style="flex: 1; max-width: 800px;" v-if="selectedDict">
              <!-- 搜索功能 -->
              <div style="margin-bottom: 20px;">
                <span style="margin-right: 16px; font-weight: bold;">字典条目搜索:</span>
                <a-input-search
                  v-model:value="searchKeyword"
                  placeholder="精确匹配搜索条目是否存在"
                  style="width: 300px"
                  @search="handleSearch"
                  :loading="searchLoading"
                >
                  <template #enterButton>
                    <a-button type="primary">搜索</a-button>
                  </template>
                </a-input-search>
                <div v-if="searchResult !== null" style="margin-top: 8px;">
                  <div v-if="searchResult.length > 0" style="margin-bottom: 8px; color: #52c41a;">
                    ✅ 找到 {{ searchResult.length }} 条包含该关键词的条目:
                  </div>
                  <div v-else style="margin-bottom: 8px; color: #ff4d4f;">
                    ❌ 未找到包含该关键词的条目
                  </div>
                  
                  <div v-if="searchResult.length > 0" style="max-height: 200px; overflow-y: auto; background: #fafafa; padding: 12px; border: 1px solid #f0f0f0; border-radius: 4px;">
                    <div v-for="(item, idx) in searchResult" :key="idx" style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 4px; padding-bottom: 4px; border-bottom: 1px solid #f5f5f5;">
                      <span style="font-family: monospace; word-break: break-all; font-size: 13px;">{{ item }}</span>
                      <a-button 
                        type="link" 
                        danger 
                        size="small" 
                        @click="handleDeleteSingle(item)" 
                        :loading="deleteLoading"
                      >
                        删除
                      </a-button>
                    </div>
                  </div>
                  <div v-if="searchResult.length === 100" style="color: #faad14; font-size: 12px; margin-top: 4px;">
                    * 仅显示前 100 条匹配项，请细化搜索词。
                  </div>
                </div>
              </div>

              <!-- 预览区 -->
              <div style="margin-bottom: 24px;">
                <div style="margin-bottom: 8px; font-weight: bold;">
                  字典内容预览 (显示前 {{ previewLimit }} 行, 总行数: {{ totalLines }}):
                </div>
                <a-textarea 
                  v-model:value="previewContent" 
                  :rows="12" 
                  readonly 
                  style="background-color: #f5f5f5;"
                />
              </div>

              <!-- 新增与批量删除区 -->
              <div style="margin-bottom: 24px;">
                <div style="margin-bottom: 8px; font-weight: bold;">新增 / 批量删除条目 (每行一个):</div>
                <a-textarea 
                  v-model:value="newEntries" 
                  :rows="6" 
                  placeholder="输入要操作的条目，点击“追加保存”或“批量删除”..." 
                />
                <div style="margin-top: 16px; display: flex; gap: 12px;">
                  <a-button type="primary" @click="handleAppend" :loading="submitLoading" :disabled="!newEntries.trim()">
                    追加保存
                  </a-button>
                  <a-button danger @click="handleDeleteBatch" :loading="deleteLoading" :disabled="!newEntries.trim()">
                    批量删除
                  </a-button>
                </div>
              </div>
            </div>
            
            <div style="flex: 1; display: flex; align-items: center; justify-content: center; color: #999; font-size: 16px;" v-else>
              👈 请在左侧菜单点击选择一个字典文件
            </div>
          </div>
        </a-spin>
      </a-tab-pane>

      <!-- CDN 字典管理 Tab -->
      <a-tab-pane key="cdn" tab="CDN字典管理" force-render>
        <div style="margin-bottom: 16px; display: flex; justify-content: space-between;">
          <div style="display: flex; gap: 8px;">
            <a-button type="primary" @click="openCdnModal()">添加CDN特征</a-button>
            <a-upload
              name="file"
              :show-upload-list="false"
              :customRequest="handleCdnImport"
              accept=".json"
            >
              <a-button>一键导入CDN</a-button>
            </a-upload>
          </div>
          <a-button type="primary" style="background-color: #52c41a; border-color: #52c41a;" @click="saveCdnData" :loading="cdnSaveLoading">保存全量更改到服务器</a-button>
        </div>
        
        <a-table 
          :dataSource="cdnList" 
          :columns="cdnColumns" 
          rowKey="name"
          :pagination="{ pageSize: 20 }"
          size="middle"
          :loading="cdnLoading"
        >
          <template #bodyCell="{ column, record, index }">
            <template v-if="column.key === 'cname_domain'">
              <div style="max-height: 100px; overflow-y: auto;">
                <a-tag v-for="cname in (record.cname_domain || [])" :key="cname" color="blue" style="margin-bottom: 4px;">{{ cname }}</a-tag>
              </div>
            </template>
            <template v-else-if="column.key === 'ip_cidr'">
              <div style="max-height: 100px; overflow-y: auto;">
                <a-tag v-for="ip in (record.ip_cidr || [])" :key="ip" color="green" style="margin-bottom: 4px;">{{ ip }}</a-tag>
              </div>
            </template>
            <template v-else-if="column.key === 'action'">
              <a-button type="link" @click="openCdnModal(record, index)">编辑</a-button>
              <a-popconfirm title="确定要删除该CDN特征吗？此操作需点击右上角保存后才能持久化" @confirm="deleteCdnItem(index)">
                <a-button type="link" danger>删除</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>

        <!-- CDN 编辑弹窗 -->
        <a-modal
          v-model:open="cdnModalVisible"
          :title="isEditingCdn ? '编辑CDN特征' : '添加CDN特征'"
          @ok="submitCdnModal"
          width="700px"
          destroyOnClose
        >
          <a-form :model="currentCdnForm" :label-col="{ span: 4 }" :wrapper-col="{ span: 19 }" style="margin-top: 20px;">
            <a-form-item label="CDN名称" required>
              <a-input v-model:value="currentCdnForm.name" placeholder="例如：阿里云CDN" />
            </a-form-item>
            <a-form-item label="CNAME后缀">
              <a-textarea v-model:value="currentCdnForm.cnameText" :rows="4" placeholder="每行输入一个CNAME后缀，如: kunlunpi.com" />
            </a-form-item>
            <a-form-item label="IP网段(CIDR)">
              <a-textarea v-model:value="currentCdnForm.ipText" :rows="4" placeholder="每行输入一个IP网段，如: 103.21.244.0/22" />
            </a-form-item>
          </a-form>
        </a-modal>
      </a-tab-pane>
    </a-tabs>
  </div>
</template>

<script setup>
import { ref, onMounted, computed } from 'vue';
import { message } from 'ant-design-vue';
import request from '@/utils/request';

const activeKey = ref('dictionary');
const loading = ref(false);
const searchLoading = ref(false);
const submitLoading = ref(false);
const deleteLoading = ref(false);

const dictList = ref([]);
const groupedDicts = computed(() => {
  const groups = {};
  dictList.value.forEach(dict => {
    const cat = dict.category || '其他 (Others)';
    if (!groups[cat]) {
      groups[cat] = [];
    }
    groups[cat].push(dict);
  });
  return groups;
});
const selectedDictKeys = ref([]);
const selectedDict = ref(null);

const previewContent = ref('');
const totalLines = ref(0);
const previewLimit = ref(500);

const searchKeyword = ref('');
const searchResult = ref(null);

const newEntries = ref('');

// 获取字典列表
const fetchDictList = async () => {
  loading.value = true;
  try {
    const res = await request.get('/api/dictionary/list');
    if (res.code === 200) {
      dictList.value = res.data || [];
    } else {
      message.error(res.message || '获取字典列表失败');
    }
  } catch (error) {
    message.error('请求字典列表出错');
    console.error(error);
  } finally {
    loading.value = false;
  }
};

// 获取预览
const fetchPreview = async (name) => {
  if (!name) return;
  loading.value = true;
  try {
    const res = await request.get(`/api/dictionary/preview`, {
      params: { name, limit: previewLimit.value }
    });
    if (res.code === 200) {
      previewContent.value = res.data.lines.join('\n');
      totalLines.value = res.data.total;
    } else {
      message.error(res.message || '获取预览失败');
    }
  } catch (error) {
    message.error('请求预览内容出错');
    console.error(error);
  } finally {
    loading.value = false;
  }
};

// 左侧菜单选择字典
const handleMenuSelect = ({ key }) => {
  selectedDict.value = key;
  searchKeyword.value = '';
  searchResult.value = null;
  newEntries.value = '';
  fetchPreview(key);
};

// 搜索功能
const handleSearch = async () => {
  if (!searchKeyword.value.trim()) {
    message.warning('请输入搜索关键词');
    return;
  }
  searchLoading.value = true;
  try {
    const res = await request.get('/api/dictionary/search', {
      params: { name: selectedDict.value, keyword: searchKeyword.value }
    });
    if (res.code === 200) {
      searchResult.value = res.data.matches;
      if (res.data.matches.length > 0) {
        message.success(`找到 ${res.data.matches.length} 条匹配项！`);
      } else {
        message.info('未找到包含该关键词的条目。');
      }
    } else {
      message.error(res.message || '搜索失败');
    }
  } catch (error) {
    message.error('请求搜索出错');
    console.error(error);
  } finally {
    searchLoading.value = false;
  }
};

// 追加条目
const handleAppend = async () => {
  if (!newEntries.value.trim()) return;
  
  submitLoading.value = true;
  try {
    const res = await request.post('/api/dictionary/append', {
      name: selectedDict.value,
      content: newEntries.value
    });
    
    if (res.code === 200) {
      message.success(`保存成功！共提交 ${res.data.total_submitted} 项，实际追加新条目 ${res.data.added} 项。`);
      newEntries.value = ''; // 清空输入框
      // 刷新预览和大小
      fetchDictList();
      fetchPreview(selectedDict.value);
    } else {
      message.error(res.message || '保存失败');
    }
  } catch (error) {
    message.error('请求保存出错');
    console.error(error);
  } finally {
    submitLoading.value = false;
  }
};

// 批量删除
const handleDeleteBatch = async () => {
  if (!newEntries.value.trim()) return;
  await deleteEntries(newEntries.value);
};

// 单条删除
const handleDeleteSingle = async (item) => {
  if (!item) return;
  await deleteEntries(item);
  // 删除成功后，从搜索结果列表中移除该条目
  if (searchResult.value) {
    searchResult.value = searchResult.value.filter(x => x !== item);
  }
};

// 公共删除逻辑
const deleteEntries = async (content) => {
  deleteLoading.value = true;
  try {
    const res = await request.post('/api/dictionary/delete_entries', {
      name: selectedDict.value,
      content: content
    });
    
    if (res.code === 200) {
      message.success(`删除成功！尝试删除 ${res.data.total_submitted} 项，实际成功删除 ${res.data.deleted} 项。`);
      newEntries.value = '';
      // 刷新预览和大小
      fetchDictList();
      fetchPreview(selectedDict.value);
    } else {
      message.error(res.message || '删除失败');
    }
  } catch (error) {
    message.error('请求删除出错');
    console.error(error);
  } finally {
    deleteLoading.value = false;
  }
};

// ======================= CDN 管理逻辑 =======================
const cdnList = ref([]);
const cdnLoading = ref(false);
const cdnSaveLoading = ref(false);

const cdnColumns = [
  { title: '名称', dataIndex: 'name', key: 'name', width: '20%' },
  { title: 'CNAME域名', dataIndex: 'cname_domain', key: 'cname_domain', width: '35%' },
  { title: 'IP网段', dataIndex: 'ip_cidr', key: 'ip_cidr', width: '30%' },
  { title: '操作', key: 'action', width: '15%' }
];

const cdnModalVisible = ref(false);
const isEditingCdn = ref(false);
const currentEditIndex = ref(-1);
const currentCdnForm = ref({ name: '', cnameText: '', ipText: '' });

// 拉取 CDN 列表
const fetchCdnList = async () => {
  cdnLoading.value = true;
  try {
    const res = await request.get('/api/cdn_dict/list');
    if (res.code === 200) {
      cdnList.value = res.data || [];
    } else {
      message.error(res.message || '获取CDN列表失败');
    }
  } catch (error) {
    message.error('请求CDN列表出错');
    console.error(error);
  } finally {
    cdnLoading.value = false;
  }
};

// 打开新增/编辑弹窗
const openCdnModal = (record = null, index = -1) => {
  if (record) {
    isEditingCdn.value = true;
    currentEditIndex.value = index;
    currentCdnForm.value = {
      name: record.name || '',
      cnameText: (record.cname_domain || []).join('\n'),
      ipText: (record.ip_cidr || []).join('\n')
    };
  } else {
    isEditingCdn.value = false;
    currentEditIndex.value = -1;
    currentCdnForm.value = { name: '', cnameText: '', ipText: '' };
  }
  cdnModalVisible.value = true;
};

// 提交本地编辑
const submitCdnModal = () => {
  if (!currentCdnForm.value.name.trim()) {
    message.warning('请输入CDN名称');
    return;
  }
  
  const cname_domain = currentCdnForm.value.cnameText.split('\n').map(s => s.trim()).filter(s => s);
  const ip_cidr = currentCdnForm.value.ipText.split('\n').map(s => s.trim()).filter(s => s);
  
  const newItem = {
    name: currentCdnForm.value.name.trim(),
    cname_domain,
    ip_cidr
  };
  
  if (isEditingCdn.value && currentEditIndex.value > -1) {
    cdnList.value.splice(currentEditIndex.value, 1, newItem);
  } else {
    cdnList.value.push(newItem);
  }
  
  cdnModalVisible.value = false;
  message.info('本地修改成功，请记得点击【保存全量更改到服务器】');
};

// 删除单条 CDN 记录
const deleteCdnItem = (index) => {
  cdnList.value.splice(index, 1);
  message.info('本地删除成功，请记得点击【保存全量更改到服务器】');
};

// 保存全量数据到服务器
const saveCdnData = async () => {
  cdnSaveLoading.value = true;
  try {
    const res = await request.post('/api/cdn_dict/save', {
      data: cdnList.value
    });
    if (res.code === 200) {
      message.success('全量保存成功！');
      fetchCdnList(); // 重新拉取确认
    } else {
      message.error(res.message || '保存失败');
    }
  } catch (error) {
    message.error('请求保存出错');
    console.error(error);
  } finally {
    cdnSaveLoading.value = false;
  }
};

// CDN 一键导入
const handleCdnImport = (options) => {
  const { file, onSuccess, onError } = options;
  const reader = new FileReader();
  reader.onload = (e) => {
    try {
      const importedData = JSON.parse(e.target.result);
      if (Array.isArray(importedData)) {
        cdnList.value = [...cdnList.value, ...importedData];
        message.success(`成功导入 ${importedData.length} 条数据，请确认后点击【保存全量更改到服务器】`);
        onSuccess(null, file);
      } else {
        message.error('文件格式错误，应为 JSON 数组');
        onError(new Error('Format error'));
      }
    } catch (err) {
      message.error('解析 JSON 失败');
      onError(err);
    }
  };
  reader.onerror = (err) => {
    message.error('读取文件失败');
    onError(err);
  };
  reader.readAsText(file);
};

onMounted(() => {
  fetchDictList();
  fetchCdnList();
});
</script>

<style scoped>
/* 可以在此处添加自定义样式 */
</style>
