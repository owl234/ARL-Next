<template>
  <div style="background-color: var(--arl-bg-layout); padding: 24px; min-height: calc(100vh - 64px);">
    <div ref="actionBarRef" style="position: sticky; top: 0px; z-index: 10; background-color: var(--arl-bg-layout); margin: -24px -24px 16px -24px; padding: 24px 24px 16px 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.05);">

      <div style="margin-bottom: 24px;">
        <a-button type="primary" @click="openAddModal">新建资产分组</a-button>
      </div>

      <div style="margin-bottom: 16px;">
        <a-form :model="searchForm" layout="inline" style="row-gap: 16px;">
          <a-form-item label="资产组名称:">
            <a-input v-model:value="searchForm.name" placeholder="请输入资产组名称" style="width: 220px;" allowClear @pressEnter="onSearch">
              <template #suffix><search-outlined @click="onSearch" style="color: var(--arl-text-color); opacity: 0.25; cursor: pointer;" /></template>
            </a-input>
          </a-form-item>
          <a-form-item label="资产范围:">
            <a-input v-model:value="searchForm.scope" placeholder="请输入资产范围" style="width: 220px;" allowClear @pressEnter="onSearch">
              <template #suffix><search-outlined @click="onSearch" style="color: var(--arl-text-color); opacity: 0.25; cursor: pointer;" /></template>
            </a-input>
          </a-form-item>
          <a-form-item label="资产范围ID:">
            <a-input v-model:value="searchForm._id" placeholder="请输入资产范围ID" style="width: 220px;" allowClear @pressEnter="onSearch">
              <template #suffix><search-outlined @click="onSearch" style="color: var(--arl-text-color); opacity: 0.25; cursor: pointer;" /></template>
            </a-input>
          </a-form-item>
        </a-form>
      </div>

      <div style="margin-bottom: 16px; display: flex; align-items: center; gap: 8px;">
        <a-button @click="resetSearch">清 除</a-button>
        <a-button danger :disabled="!hasSelected" @click="handleBatchDelete">批量删除</a-button>
        <a-dropdown :disabled="!hasSelected">
          <template #overlay>
            <a-menu @click="handleBatchExport">
              <a-menu-item key="asset_domain">域名批量导出</a-menu-item>
              <a-menu-item key="asset_ip">IP 批量导出</a-menu-item>
              <a-menu-item key="asset_site">站点批量导出</a-menu-item>
              <a-menu-item key="asset_wih">WIH批量导出</a-menu-item>
            </a-menu>
          </template>
          <a-button>
            批量导出 <down-outlined />
          </a-button>
        </a-dropdown>
      </div>

    </div>

    <a-table 
      :sticky="stickyConfig"
      :row-selection="{ selectedRowKeys: selectedRowKeys, onChange: onSelectChange }"
      :loading="loading"
      :dataSource="dataSource"
      :columns="columns"
      :pagination="false"
      :scroll="{ x: 'max-content' }"
      bordered
      style="margin-bottom: 16px;"
      size="middle"
      :rowKey="(record) => record._id"
    >
      <template #bodyCell="{ column, record }">

        <template v-if="column.key === 'name'">
          <div style="display: flex; align-items: center; gap: 6px; flex-wrap: wrap;">
            <a style="font-weight: 500;" @click="goToDetail(record)">{{ record.name }}</a>
            <a-tooltip v-if="record.black_scope" placement="top">
              <template #title>黑名单: {{ record.black_scope }}</template>
              <a-tag color="error" style="font-size: 11px; padding: 0 4px; line-height: 18px; height: 18px; margin-right: 0;">黑名单</a-tag>
            </a-tooltip>
          </div>
        </template>

        <template v-else-if="column.key === 'scope_array'">
          <div style="display: flex; flex-wrap: wrap; gap: 4px; align-items: center;">
            <a-tooltip
              v-for="(item, idx) in (record._sorted_scopes || record.scope_array || []).slice(0, 5)"
              :key="idx"
              :title="getDomainTooltip(record, item)"
            >
              <a-tag
                closable
                @close="(e) => { e.preventDefault(); handleRemoveSingleScope(record, item); }"
                :style="getDomainTagStyle(record, item)"
              >
                <span v-if="getDomainStatus(record, item) === 'unprobed'" style="color: #faad14; font-weight: bold; margin-right: 2px;">●</span>
                <span v-else-if="getDomainStatus(record, item) === 'scanning'" style="color: #1890ff; font-weight: bold; margin-right: 2px;">◌</span>
                {{ item }}
              </a-tag>
            </a-tooltip>
            <a-popover v-if="(record.scope_array || []).length > 5" placement="bottomLeft">
              <template #content>
                <div style="max-width: 440px; max-height: 300px; overflow-y: auto; display: flex; flex-wrap: wrap; gap: 4px; padding: 4px;">
                  <a-tooltip
                    v-for="(item, idx) in (record._sorted_scopes || record.scope_array || []).slice(5)"
                    :key="idx"
                    :title="getDomainTooltip(record, item)"
                  >
                    <a-tag
                      closable
                      @close="(e) => { e.preventDefault(); handleRemoveSingleScope(record, item); }"
                      :style="getDomainTagStyle(record, item)"
                    >
                      <span v-if="getDomainStatus(record, item) === 'unprobed'" style="color: #faad14; font-weight: bold; margin-right: 2px;">●</span>
                      <span v-else-if="getDomainStatus(record, item) === 'scanning'" style="color: #1890ff; font-weight: bold; margin-right: 2px;">◌</span>
                      {{ item }}
                    </a-tag>
                  </a-tooltip>
                </div>
              </template>
              <a-tag style="background: var(--arl-bg-white); border-style: dashed; cursor: pointer; margin-right: 0;">
                +{{ record.scope_array.length - 5 }} 更多
              </a-tag>
            </a-popover>
            <a-tag 
              style="background: var(--arl-bg-white); border-style: dashed; cursor: pointer; margin-right: 0; color: var(--arl-theme-color);" 
              @click="openEditGroupModal(record)"
            >
              <plus-outlined /> 添加
            </a-tag>
          </div>
        </template>

        <template v-else-if="column.key === 'domain_stat'">
          <a-tooltip
            v-if="record.domain_stat && record.domain_stat.total > 0"
            placement="top"
          >
            <template #title>
              <div style="line-height: 1.8;">
                <div>总资产范围数: <strong>{{ record.domain_stat.total }}</strong></div>
                <div v-if="record.domain_stat.scanning > 0">探测中数量: <strong style="color: #1890ff;">{{ record.domain_stat.scanning }}</strong></div>
                <div>已探测数量: <strong style="color: #52c41a;">{{ record.domain_stat.probed }}</strong> ({{ Math.round((record.domain_stat.probed / record.domain_stat.total) * 100) }}%)</div>
                <div v-if="record.domain_stat.unprobed > 0">待探测数量: <strong style="color: #faad14;">{{ record.domain_stat.unprobed }}</strong></div>
                <div v-if="record.domain_stat.error > 0">探测异常数量: <strong style="color: #ff4d4f;">{{ record.domain_stat.error }}</strong></div>
              </div>
            </template>
            <div style="display: flex; gap: 6px; align-items: center; cursor: pointer; flex-wrap: wrap;">
              <a-badge
                v-if="record.domain_stat.scanning > 0"
                :count="record.domain_stat.scanning + ' 探测中'"
                :number-style="{ backgroundColor: '#1890ff', color: '#fff' }"
              />
              <a-badge
                v-if="record.domain_stat.probed > 0 || (!record.domain_stat.scanning && !record.domain_stat.unprobed)"
                :count="record.domain_stat.probed + ' 已测'"
                :number-style="{ backgroundColor: '#52c41a', color: '#fff' }"
              />
              <a-badge
                v-if="record.domain_stat.unprobed > 0"
                :count="record.domain_stat.unprobed + ' 待测'"
                :number-style="{ backgroundColor: '#faad14', color: '#fff' }"
              />
              <a-badge
                v-if="record.domain_stat.error > 0"
                :count="record.domain_stat.error + ' 异常'"
                :number-style="{ backgroundColor: '#ff4d4f', color: '#fff' }"
              />
            </div>
          </a-tooltip>
          <span v-else style="color: var(--arl-text-color); opacity: 0.45;">-</span>
        </template>

        <template v-else-if="column.key === 'scope_id'">
          <div style="display: flex; align-items: center; gap: 8px;">
            <a style="font-family: monospace; font-size: 13px;" @click="goToDetail(record)">{{ record._id }}</a>
            <a-tooltip title="复制所有资产范围">
              <copy-outlined
                style="cursor: pointer; color: var(--arl-text-color); opacity: 0.45; font-size: 13px;"
                @click="copyText(record.scope_array ? record.scope_array.join('\n') : '')"
              />
            </a-tooltip>
          </div>
        </template>

        <template v-else-if="column.key === 'action'">
          <a-space size="small">
            <a-button type="link" size="small" style="padding: 0 4px;" @click="openEditGroupModal(record)">编辑</a-button>
            <a-button type="link" size="small" style="padding: 0 4px;" @click="openAddMonitorModal(record)">资产监控</a-button>
            <a-button type="link" size="small" style="padding: 0 4px;" @click="openAddSiteMonitorModal(record)">站点监控</a-button>
            <a-button type="link" size="small" style="padding: 0 4px;" @click="openAddWihMonitorModal(record)">WIH</a-button>
            <a-button type="link" danger size="small" style="padding: 0 4px;" @click="handleSingleDelete(record)">删除</a-button>
          </a-space>
        </template>

      </template>
    </a-table>

    <div style="display: flex; justify-content: space-between; align-items: center; padding: 0 16px;">
      <div style="color: var(--arl-text-color); opacity: 0.65;">共 {{ Math.ceil(pagination.total / pagination.pageSize) || 1 }} 页 / {{ pagination.total }} 条数据</div>
      <a-pagination 
        :pageSizeOptions="$pageSizeOptions" 
        v-model:current="pagination.current" 
        v-model:pageSize="pagination.pageSize" 
        :total="pagination.total" 
        show-size-changer 
        @change="handleTableChange" 
        @showSizeChange="handleTableChange" 
      />
    </div>

    <!-- 新建资产分组弹窗 -->
    <a-modal
      v-model:open="addModalVisible"
      title="新建资产分组"
      @ok="handleAddSubmit"
      :confirmLoading="addLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
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
        <a-form-item label="资产组名称" name="name">
          <a-input v-model:value="addForm.name" placeholder="请输入资产组名称" />
        </a-form-item>

        <a-form-item label="资产范围" name="scope">
          <a-textarea
            v-model:value="addForm.scope"
            :rows="5"
            placeholder="请输入资产范围（支持同时混填 IP、CIDR 与域名，如: 1.1.1.1, baidu.com, 192.168.1.0/24），多个请用逗号或换行分隔"
            style="font-family: monospace; font-size: 13px;"
          />
        </a-form-item>

        <a-form-item label="资产黑名单" name="black_scope">
          <a-textarea
            v-model:value="addForm.black_scope"
            :rows="3"
            placeholder="选填。请输入资产黑名单（在监控与扫描中排除），多个请用逗号或换行分隔"
            style="font-family: monospace; font-size: 13px;"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 编辑资产分组弹窗 -->
    <a-modal
      v-model:open="editGroupModalVisible"
      title="编辑资产分组"
      @ok="handleEditGroupSubmit"
      :confirmLoading="editGroupLoading"
      width="640px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      okText="保 存"
      cancelText="取 消"
      destroyOnClose
    >
      <a-form
        ref="editGroupFormRef"
        :model="editGroupForm"
        :rules="editGroupRules"
        :label-col="{ span: 4 }"
        :wrapper-col="{ span: 19 }"
        style="margin-top: 20px;"
      >
        <a-form-item label="资产组名称" name="name">
          <a-input v-model:value="editGroupForm.name" placeholder="请输入资产组名称" />
        </a-form-item>

        <a-form-item label="资产范围" name="scope">
          <!-- 模式切换与统计栏 -->
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div style="font-size: 13px; color: var(--arl-text-color); opacity: 0.85;">
              <span>共 <strong style="color: var(--arl-theme-color, #1890ff);">{{ editGroupScopeList.length }}</strong> 个有效目标</span>
              <span v-if="editGroupMode === 'visual' && editGroupSearchKeyword.trim()" style="margin-left: 6px;">
                (匹配到 <strong style="color: #52c41a;">{{ filteredScopeList.length }}</strong> 个)
              </span>
            </div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <a-button 
                type="link" 
                size="small" 
                style="padding: 0; height: auto;" 
                @click="toggleEditGroupMode"
              >
                <template v-if="editGroupMode === 'visual'">
                  <file-text-outlined style="margin-right: 4px;" />纯文本批量模式
                </template>
                <template v-else>
                  <tags-outlined style="margin-right: 4px;" />可视化标签模式
                </template>
              </a-button>
            </div>
          </div>

          <!-- 可视化管理模式 -->
          <div v-if="editGroupMode === 'visual'" class="arl-scope-visual-panel">
            <!-- 搜索与批量删除工具栏 -->
            <div style="display: flex; gap: 8px; margin-bottom: 8px;">
              <a-input
                v-model:value="editGroupSearchKeyword"
                placeholder="搜索资产 (支持域名/IP模糊过滤)"
                allowClear
                size="middle"
                style="flex: 1;"
              >
                <template #prefix>
                  <search-outlined style="color: #bfbfbf;" />
                </template>
              </a-input>

              <a-popconfirm
                v-if="editGroupSearchKeyword.trim() && filteredScopeList.length > 0"
                :title="`确定批量移除匹配到的 ${filteredScopeList.length} 个资产范围吗？`"
                ok-text="删除"
                cancel-text="取消"
                ok-type="danger"
                @confirm="removeFilteredScopes"
              >
                <a-button danger size="middle">
                  <delete-outlined /> 删除筛选结果 ({{ filteredScopeList.length }})
                </a-button>
              </a-popconfirm>
            </div>

            <!-- 快捷追加输入 -->
            <div style="display: flex; gap: 8px; margin-bottom: 10px;">
              <a-input
                v-model:value="editGroupNewInput"
                placeholder="追加新资产（支持多行/逗号批量粘贴，回车快速添加）"
                size="middle"
                @pressEnter="addScopesFromInput"
                style="flex: 1;"
              />
              <a-button type="primary" size="middle" @click="addScopesFromInput">
                <plus-outlined /> 添加
              </a-button>
            </div>

            <!-- 资产标签滚动展示区 -->
            <div class="arl-scope-tag-container">
              <template v-if="filteredScopeList.length > 0">
                <a-tag
                  v-for="item in filteredScopeList"
                  :key="item"
                  closable
                  @close.prevent="removeScopeItem(item)"
                  class="arl-scope-edit-item-tag"
                >
                  {{ item }}
                </a-tag>
              </template>
              <div v-else class="arl-scope-empty-hint">
                {{ editGroupSearchKeyword.trim() ? '未找到匹配的资产' : '暂无资产，请在上方输入添加' }}
              </div>
            </div>
          </div>

          <!-- 纯文本批量模式 -->
          <div v-else>
            <a-textarea
              v-model:value="editGroupForm.scope"
              :rows="7"
              placeholder="请输入资产范围（支持同时混填 IP 与域名），多个请用逗号或换行分隔"
              style="font-family: monospace; font-size: 13px;"
            />
            <div style="margin-top: 6px; font-size: 12px; color: var(--arl-text-color); opacity: 0.65; display: flex; justify-content: space-between; align-items: center;">
              <span>当前共 <strong style="color: #1890ff;">{{ parseScopeList(editGroupForm.scope).length }}</strong> 个有效目标</span>
              <a-button type="link" size="small" style="padding: 0; height: auto;" @click="formatEditGroupScopes">格式化规整</a-button>
            </div>
          </div>
        </a-form-item>

        <a-form-item label="资产黑名单" name="black_scope">
          <a-textarea
            v-model:value="editGroupForm.black_scope"
            :rows="2"
            placeholder="选填。请输入资产黑名单，多个请用逗号或换行分隔"
            style="font-family: monospace; font-size: 13px;"
          />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 添加常规监控任务 -->
    <a-modal
      v-model:open="addMonitorVisible"
      @ok="submitAddMonitor"
      :confirmLoading="addMonitorLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
      destroyOnClose
    >
      <template #title>
        添加监控任务
        <a-tooltip title="将对资产组已发现域名与本次新发现域名取并集后执行策略，当前结果仅展示资产组的增量更新（新增及变动数据）。">
          <QuestionCircleOutlined style="font-size: 14px; color: #8c8c8c; cursor: pointer; margin-left: 4px;" />
        </a-tooltip>
      </template>
      <a-form ref="addMonitorFormRef" :model="addMonitorForm" :rules="addMonitorRules" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">

        <a-form-item label="范围" name="domains">
          <div style="margin-bottom: 8px; display: flex; gap: 6px; flex-wrap: wrap;">
            <a-button size="small" @click="selectAllDomains">全选 ({{ (currentRecord?.scope_array || []).length }})</a-button>
            <a-button 
              size="small" 
              type="primary" 
              ghost 
              @click="selectUnprobedDomains"
              :style="{ borderColor: unprobedDomainList.length > 0 ? '#faad14' : '', color: unprobedDomainList.length > 0 ? '#d48806' : '' }"
            >
              仅选未探测域名 ({{ unprobedDomainList.length }})
            </a-button>
            <a-button size="small" @click="selectProbedDomains">仅选已探测 ({{ probedDomainList.length }})</a-button>
            <a-button size="small" @click="clearDomains">清空</a-button>
          </div>
          <a-select mode="multiple" v-model:value="addMonitorForm.domains" placeholder="请选择范围" style="width: 100%;">
            <a-select-option v-for="item in currentRecord?.scope_array || []" :key="item" :value="item">
              <span style="display: flex; justify-content: space-between; align-items: center;">
                <span>{{ item }}</span>
                <span :style="{ 
                  fontSize: '11px', 
                  marginLeft: '8px',
                  color: getDomainStatus(currentRecord, item) === 'unprobed' ? '#faad14' : 
                         getDomainStatus(currentRecord, item) === 'scanning' ? '#1890ff' : 
                         getDomainStatus(currentRecord, item) === 'error' ? '#ff4d4f' : '#52c41a' 
                }">
                  [{{ getDomainStatusLabel(currentRecord, item) }}]
                </span>
              </span>
            </a-select-option>
          </a-select>
        </a-form-item>

        <a-form-item label="任务类型" name="task_type">
          <a-radio-group v-model:value="addMonitorForm.task_type">
            <a-radio value="periodic">周期性监控</a-radio>
            <a-radio value="oneshot">一次性扫描</a-radio>
          </a-radio-group>
        </a-form-item>

        <a-form-item label="运行间隔" name="interval_hours" v-if="addMonitorForm.task_type === 'periodic'">
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

    <!-- 添加站点监控任务 -->
    <a-modal
      v-model:open="addSiteMonitorVisible"
      title="添加站点监控任务"
      @ok="submitAddSiteMonitor"
      :confirmLoading="addSiteMonitorLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
      destroyOnClose
    >
      <a-form ref="addSiteMonitorFormRef" :model="addSiteMonitorForm" :rules="addSiteMonitorRules" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">
        <a-form-item label="运行间隔" name="interval_hours">
          <div style="display: flex; align-items: center; gap: 8px;">
            <a-input-number v-model:value="addSiteMonitorForm.interval_hours" :min="1" style="width: 100%;" />
            <span>小时</span>
          </div>
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- 添加WIH监控任务 -->
    <a-modal
      v-model:open="addWihMonitorVisible"
      title="添加WIH监控任务"
      @ok="submitAddWihMonitor"
      :confirmLoading="addWihMonitorLoading"
      width="560px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
      okText="确 定"
      cancelText="取 消"
      destroyOnClose
    >
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
defineOptions({ name: 'AssetScope' });

import { ref, reactive, computed, createVNode, watch, onActivated, onDeactivated, onUnmounted } from 'vue';
import { useSticky } from '../utils/useSticky';
const actionBarRef = ref(null);
const { stickyConfig } = useSticky(actionBarRef);

import request from '../utils/request';
import { message, Modal } from 'ant-design-vue';
import { 
  SearchOutlined, 
  DownOutlined, 
  ExclamationCircleOutlined, 
  QuestionCircleOutlined, 
  EditOutlined, 
  PlusOutlined, 
  GlobalOutlined, 
  ScheduleOutlined, 
  FileSearchOutlined, 
  DeleteOutlined,
  CopyOutlined,
  FileTextOutlined,
  TagsOutlined
} from '@ant-design/icons-vue';
import { useRoute, useRouter } from 'vue-router';
import { useGlobalPageSize } from '../utils/useGlobalPageSize';
import { copyText as copyToClipboard } from '../utils/clipboard';

const route = useRoute();
const router = useRouter();
const loading = ref(false);
const dataSource = ref([]);
const searchForm = ref({});
const currentRecord = ref(null);
const globalPageSize = useGlobalPageSize(10);
const pagination = reactive({ current: 1, pageSize: globalPageSize.value, total: 0 });

watch(() => pagination.pageSize, (newSize) => {
  globalPageSize.value = newSize;
});

watch(globalPageSize, (newSize) => {
  pagination.pageSize = newSize;
});

const selectedRowKeys = ref([]);
const hasSelected = computed(() => selectedRowKeys.value.length > 0);
const onSelectChange = (keys) => { selectedRowKeys.value = keys; };

// 表格列定义
const columns = [
  { title: '资产组名称', key: 'name', width: 200, sorter: true },
  { title: '资产范围', key: 'scope_array', minWidth: 280 },
  { title: '探测覆盖度', key: 'domain_stat', width: 160 },
  { title: '资产范围ID', key: 'scope_id', width: 220 },
  { title: '操作', key: 'action', width: 290 }
];

// 获取主域名探测状态与展示样式
const getDomainStatus = (record, domain) => {
  if (!record || !domain) return 'unprobed';
  return record.domain_status?.[domain]?.status || 'unprobed';
};

const getDomainStatusLabel = (record, domain) => {
  const st = getDomainStatus(record, domain);
  if (st === 'probed') return '已探测';
  if (st === 'scanning') return '探测中';
  if (st === 'error') return '探测异常';
  return '未探测';
};

const getDomainTagStyle = (record, domain) => {
  const st = getDomainStatus(record, domain);
  if (st === 'unprobed') {
    return {
      background: '#fffbe6',
      borderColor: '#ffe58f',
      color: '#d48806',
      marginRight: '0'
    };
  }
  if (st === 'scanning') {
    return {
      background: '#e6f7ff',
      borderColor: '#91d5ff',
      color: '#1890ff',
      marginRight: '0'
    };
  }
  if (st === 'error') {
    return {
      background: '#fff1f0',
      borderColor: '#ffa39e',
      color: '#cf1322',
      marginRight: '0'
    };
  }
  return {
    background: 'var(--arl-bg-light)',
    color: 'var(--arl-text-color)',
    borderColor: 'var(--arl-border-color)',
    marginRight: '0'
  };
};

const getDomainTooltip = (record, domain) => {
  const meta = record?.domain_status?.[domain] || {};
  const statusLabel = getDomainStatusLabel(record, domain);
  const time = meta.last_probe_time || meta.sync_time || '-';
  return `域名: ${domain} | 状态: ${statusLabel} | 更新: ${time}`;
};

// 解析文本中的目标数组（去重去空小写）
const parseScopeList = (text) => {
  if (!text) return [];
  const rawList = text.split(/[\n,]+/);
  const seen = new Set();
  const result = [];
  for (let item of rawList) {
    item = item.trim().toLowerCase();
    if (item && !seen.has(item)) {
      seen.add(item);
      result.push(item);
    }
  }
  return result;
};

// 复制功能 (复用 utils/clipboard，兼容非 HTTPS 环境)
const copyText = async (text) => {
  const ok = await copyToClipboard(text);
  if (ok) {
    message.success('复制成功');
  } else {
    message.error('复制失败，请手动选取复制');
  }
};

// 域名标签优先级预排序（探测中 > 待测 > 异常 > 已测），预处理挂载到 _sorted_scopes 杜绝模板渲染卡顿
const processScopeItems = (items) => {
  const statusWeight = { scanning: 0, unprobed: 1, error: 2, probed: 3 };
  return (items || []).map(record => {
    const arr = record?.scope_array || [];
    let sorted = arr;
    if (arr.length > 5) {
      sorted = [...arr].sort((a, b) => {
        const weightA = statusWeight[getDomainStatus(record, a)] ?? 4;
        const weightB = statusWeight[getDomainStatus(record, b)] ?? 4;
        return weightA - weightB;
      });
    }
    return {
      ...record,
      _sorted_scopes: sorted
    };
  });
};

const getSortedScopeArray = (record) => {
  return record?._sorted_scopes || record?.scope_array || [];
};

// 轮询调度管理：如果有正在扫描中的资产组，则每 5 秒静默轮询一次
let pollTimer = null;
const stopPoll = () => {
  if (pollTimer) {
    clearTimeout(pollTimer);
    pollTimer = null;
  }
};

const checkAndSchedulePoll = () => {
  stopPoll();
  const hasScanning = (dataSource.value || []).some(item => (item?.domain_stat?.scanning || 0) > 0);
  if (hasScanning) {
    pollTimer = setTimeout(() => {
      fetchData(true);
    }, 5000);
  }
};

// 拉取表格数据（增加防重与竞态保护）
let isFetching = false;
const fetchData = async (silent = false) => {
  if (isFetching) return;
  isFetching = true;
  if (!silent) {
    loading.value = true;
  }
  try {
    const params = { page: pagination.current, size: pagination.pageSize };
    for (const key in searchForm.value) {
      if (searchForm.value[key]) params[key] = searchForm.value[key];
    }
    const res = await request.get('/asset_scope/', { params });
    if (res.code === 200) {
      dataSource.value = processScopeItems(res.items || []);
      pagination.total = res.total || 0;
      selectedRowKeys.value = [];
      checkAndSchedulePoll();
    }
  } catch (error) {
    message.error('加载资产分组失败');
  } finally {
    isFetching = false;
    if (!silent) {
      loading.value = false;
    }
  }
};

const onSearch = () => { pagination.current = 1; fetchData(); };
const resetSearch = () => {
  searchForm.value = {};
  onSearch();
};
const handleTableChange = (page, pageSize) => { pagination.current = page; pagination.pageSize = pageSize; fetchData(); };

// ================= 新建资产分组逻辑 =================
const addModalVisible = ref(false);
const addLoading = ref(false);
const addFormRef = ref();

const addForm = reactive({
  name: '',
  scope: '',
  black_scope: ''
});

const addRules = {
  name: [{ required: true, message: '请输入资产组名称', trigger: 'blur' }],
  scope: [{ required: true, message: '请输入资产范围', trigger: 'blur' }]
};

const openAddModal = () => {
  addForm.name = '';
  addForm.scope = '';
  addForm.black_scope = '';
  addModalVisible.value = true;
};

const handleAddSubmit = async () => {
  try {
    await addFormRef.value.validate();
    addLoading.value = true;
    const res = await request.post('/asset_scope/', addForm);

    if (res.code === 200) {
      message.success('新建资产分组成功！');
      addModalVisible.value = false;
      pagination.current = 1;
      fetchData();
    } else {
      message.error('新建失败: ' + (res.message || '未知错误'));
    }
  } catch (error) {
    console.warn('提交中断或校验失败', error);
  } finally {
    addLoading.value = false;
  }
};

// ================= 编辑资产分组逻辑 =================
const editGroupModalVisible = ref(false);
const editGroupLoading = ref(false);
const editGroupFormRef = ref();
const editGroupMode = ref('visual'); // 'visual' | 'text'
const editGroupScopeList = ref([]);
const editGroupSearchKeyword = ref('');
const editGroupNewInput = ref('');

const editGroupForm = reactive({
  _id: '',
  name: '',
  scope: '',
  black_scope: ''
});

const editGroupRules = {
  name: [{ required: true, message: '请输入资产组名称', trigger: 'blur' }],
  scope: [
    {
      validator: async () => {
        const list = editGroupMode.value === 'visual' 
          ? editGroupScopeList.value 
          : parseScopeList(editGroupForm.scope);
        if (!list || list.length === 0) {
          return Promise.reject(new Error('请输入或保留至少一个资产范围'));
        }
        return Promise.resolve();
      },
      trigger: 'change'
    }
  ]
};

// 搜索过滤后的资产列表
const filteredScopeList = computed(() => {
  const keyword = editGroupSearchKeyword.value.trim().toLowerCase();
  if (!keyword) {
    return editGroupScopeList.value;
  }
  return editGroupScopeList.value.filter(item => item.toLowerCase().includes(keyword));
});

// 打开编辑分组弹窗
const openEditGroupModal = (record) => {
  currentRecord.value = record;
  editGroupForm._id = record._id;
  editGroupForm.name = record.name || '';
  editGroupScopeList.value = [...(record.scope_array || [])];
  editGroupForm.scope = editGroupScopeList.value.join('\n');
  editGroupForm.black_scope = record.black_scope || '';
  editGroupMode.value = 'visual';
  editGroupSearchKeyword.value = '';
  editGroupNewInput.value = '';
  editGroupModalVisible.value = true;
};

// 模式切换
const toggleEditGroupMode = () => {
  if (editGroupMode.value === 'visual') {
    // 切换到纯文本模式
    editGroupForm.scope = editGroupScopeList.value.join('\n');
    editGroupMode.value = 'text';
  } else {
    // 切换到可视化模式
    editGroupScopeList.value = parseScopeList(editGroupForm.scope);
    editGroupForm.scope = editGroupScopeList.value.join('\n');
    editGroupMode.value = 'visual';
    editGroupSearchKeyword.value = '';
  }
};

// 单项移除资产
const removeScopeItem = (item) => {
  editGroupScopeList.value = editGroupScopeList.value.filter(x => x !== item);
  editGroupForm.scope = editGroupScopeList.value.join('\n');
};

// 批量删除搜索筛选结果
const removeFilteredScopes = () => {
  const toRemove = new Set(filteredScopeList.value);
  editGroupScopeList.value = editGroupScopeList.value.filter(x => !toRemove.has(x));
  editGroupForm.scope = editGroupScopeList.value.join('\n');
  message.success(`已批量移除 ${toRemove.size} 个匹配资产`);
  editGroupSearchKeyword.value = '';
};

// 快捷追加资产
const addScopesFromInput = () => {
  if (!editGroupNewInput.value.trim()) return;
  const newItems = parseScopeList(editGroupNewInput.value);
  if (newItems.length === 0) return;
  const existingSet = new Set(editGroupScopeList.value);
  let addedCount = 0;
  for (const item of newItems) {
    if (!existingSet.has(item)) {
      existingSet.add(item);
      editGroupScopeList.value.push(item);
      addedCount++;
    }
  }
  editGroupForm.scope = editGroupScopeList.value.join('\n');
  editGroupNewInput.value = '';
  if (addedCount > 0) {
    message.success(`成功追加 ${addedCount} 个新资产！`);
  } else {
    message.info('所填资产已全部存在，未重复添加');
  }
};

// 格式化文本模式下的资产
const formatEditGroupScopes = () => {
  const list = parseScopeList(editGroupForm.scope);
  editGroupScopeList.value = list;
  editGroupForm.scope = list.join('\n');
  message.success('已自动去重并按行规整！');
};

// 提交编辑保存
const handleEditGroupSubmit = async () => {
  try {
    if (editGroupMode.value === 'visual') {
      editGroupForm.scope = editGroupScopeList.value.join('\n');
    } else {
      editGroupScopeList.value = parseScopeList(editGroupForm.scope);
      editGroupForm.scope = editGroupScopeList.value.join('\n');
    }

    await editGroupFormRef.value.validate();
    const newScopeList = parseScopeList(editGroupForm.scope);
    if (newScopeList.length === 0) {
      message.error('资产组必须保留至少一个资产范围，禁止清空！');
      return;
    }

    const originalScopes = currentRecord.value?.scope_array || [];
    const newSet = new Set(newScopeList);
    const removed = originalScopes.filter(x => !newSet.has(x));

    if (removed.length > 0) {
      Modal.confirm({
        title: '⚠️ 资产范围剔除与级联清理确认',
        icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
        content: createVNode('div', null, [
          createVNode('p', { style: 'color: #ff4d4f; margin-bottom: 8px;' }, `检测到您从资产组【${editGroupForm.name}】中移除了以下 ${removed.length} 个资产范围：`),
          createVNode('div', { style: 'max-height: 100px; overflow-y: auto; background: #fff1f0; padding: 6px 8px; border-radius: 4px; margin-bottom: 10px; font-family: monospace; font-size: 12px; color: #cf1322;' }, removed.join(', ')),
          createVNode('p', { style: 'font-size: 12px; color: #8c8c8c; margin-bottom: 0;' }, '警告：移除上述主干目标后，系统将自动物理级联清理该组下所有归属于这些目标的已发现子域名、IP、站点和 WIH 沉淀资产，此操作不可逆！是否确认更新？')
        ]),
        okText: '确认更新并清理',
        okType: 'danger',
        cancelText: '取 消',
        onOk: () => {
          submitEditGroupUpdate(newScopeList);
        }
      });
    } else {
      submitEditGroupUpdate(newScopeList);
    }
  } catch (error) {
    console.warn('编辑校验失败', error);
  }
};

const submitEditGroupUpdate = async (scopeList) => {
  try {
    editGroupLoading.value = true;
    const res = await request.post('/asset_scope/update/', {
      _id: editGroupForm._id,
      name: editGroupForm.name,
      scope: scopeList.join(','),
      black_scope: editGroupForm.black_scope
    });

    if (res.code === 200) {
      message.success('资产分组更新成功！');
      editGroupModalVisible.value = false;
      fetchData();
    } else {
      message.error('更新失败: ' + (res.message || '未知错误'));
    }
  } catch (error) {
    message.error('请求异常，更新失败');
  } finally {
    editGroupLoading.value = false;
  }
};

// ================= 表格 Tag 快捷单个移除范围 =================
const handleRemoveSingleScope = (record, scopeItem) => {
  if ((record.scope_array || []).length <= 1) {
    message.error('资产组必须保留至少一个资产范围，禁止清空！如需彻底销毁该分组，请直接删除资产组。');
    return;
  }

  Modal.confirm({
    title: '⚠️ 资产范围剔除与级联清理确认',
    icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
    content: createVNode('div', null, [
      createVNode('p', { style: 'color: #ff4d4f; margin-bottom: 8px;' }, `检测到您正准备从资产组【${record.name}】中移除资产范围：`),
      createVNode('div', { style: 'background: #fff1f0; padding: 6px 8px; border-radius: 4px; margin-bottom: 10px; font-family: monospace; font-size: 13px; font-weight: bold; color: #cf1322;' }, scopeItem),
      createVNode('p', { style: 'font-size: 12px; color: #8c8c8c; margin-bottom: 0;' }, '警告：移除该主干目标后，系统将自动物理级联清理该组下所有归属于该目标的已发现子域名、IP、站点和 WIH 沉淀资产，此操作不可逆！是否确认移除？')
    ]),
    okText: '确认移除并清理',
    okType: 'danger',
    cancelText: '取 消',
    onOk: async () => {
      try {
        const res = await request.get('/asset_scope/delete/', {
          params: {
            scope_id: record._id,
            scope: scopeItem
          }
        });
        if (res.code === 200) {
          message.success(`已成功移除资产范围：${scopeItem}`);
          fetchData(true);
        } else {
          message.error('移除失败: ' + (res.message || res.data?.error || '未知错误'));
        }
      } catch (e) {
        message.error('请求异常，移除失败');
      }
    }
  });
};

// ================= 单行删除资产分组 =================
const handleSingleDelete = (record) => {
  Modal.confirm({
    title: '⚠️ 资产分组彻底销毁确认',
    icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
    content: createVNode('div', null, [
      createVNode('p', { style: 'color: #ff4d4f; margin-bottom: 8px;' }, `确定要彻底删除资产分组【${record.name}】吗？`),
      createVNode('p', { style: 'font-size: 12px; color: #8c8c8c; margin-bottom: 0;' }, '警告：该操作将同时物理级联清理该组关联的所有已发现子域名、IP、站点、WIH 以及所有定时监控任务，此操作不可逆！')
    ]),
    okText: '彻底删除',
    okType: 'danger',
    cancelText: '取 消',
    onOk: async () => {
      try {
        const res = await request.post('/asset_scope/delete/', {
          scope_id: [record._id]
        });

        if (res.code === 200) {
          message.success('资产分组删除成功！');
          if (dataSource.value.length === 1 && pagination.current > 1) {
            pagination.current -= 1;
          }
          fetchData();
        } else {
          message.error('删除失败: ' + res.message);
        }
      } catch (error) {
        message.error('请求异常，删除失败');
      }
    }
  });
};

// ================= 批量删除逻辑 =================
const handleBatchDelete = () => {
  Modal.confirm({
    title: '⚠️ 批量删除资产分组确认',
    icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
    content: `确定要彻底删除选中的 ${selectedRowKeys.value.length} 个资产分组吗？删除后将同时物理级联清理所有关联的子资产与监控任务，不可恢复。`,
    okText: '彻底删除',
    okType: 'danger',
    cancelText: '取 消',
    onOk: async () => {
      try {
        const res = await request.post('/asset_scope/delete/', {
          scope_id: selectedRowKeys.value
        });

        if (res.code === 200) {
          message.success('批量删除成功！');
          selectedRowKeys.value = [];
          if (dataSource.value.length === selectedRowKeys.value.length && pagination.current > 1) {
            pagination.current -= 1;
          }
          fetchData();
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
  const url = `/batch_export/${key}/`;
  const nameMap = {
    'asset_domain': '域名',
    'asset_ip': 'IP',
    'asset_site': '站点',
    'asset_wih': 'WIH'
  };
  const exportName = nameMap[key];

  try {
    message.loading({ content: `正在生成 ${exportName} 导出文件...`, key: 'export_data' });

    const res = await request.post(url, { scope_id: selectedRowKeys.value }, { responseType: 'blob' });
    const blob = new Blob([res], { type: 'text/plain;charset=utf-8' });
    const downloadUrl = window.URL.createObjectURL(blob);

    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = `ARL_Export_${exportName}_${new Date().getTime()}.txt`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    message.success({ content: `${exportName} 导出成功！`, key: 'export_data', duration: 2 });
  } catch (error) {
    message.error({ content: `${exportName} 导出失败`, key: 'export_data', duration: 2 });
  }
};

// 丝滑跳转至详情页
const goToDetail = (record) => {
  router.push({
    path: '/groupAssetsManagement/groupAssetsDetail',
    query: {
      scope_id: record._id,
      targetName: record._id
    }
  });
};

// ================= 添加监控任务 =================
const addMonitorVisible = ref(false);
const addMonitorLoading = ref(false);
const addMonitorFormRef = ref();
const policies = ref([]);

const addMonitorForm = reactive({ domains: [], interval_hours: 24, policy_id: undefined, task_type: 'periodic' });
const addMonitorRules = {
  domains: [{ type: 'array', required: true, message: '请选择范围', trigger: 'change' }],
  interval_hours: [{ required: true, message: '请输入运行间隔', trigger: 'blur' }],
  policy_id: [{ required: true, message: '请选择策略', trigger: 'change' }],
  task_type: [{ required: true, message: '请选择任务类型', trigger: 'change' }]
};

const openAddMonitorModal = async (record) => {
  currentRecord.value = record;
  addMonitorForm.domains = [];
  addMonitorForm.interval_hours = 24;
  addMonitorForm.policy_id = undefined;
  addMonitorForm.task_type = 'periodic';
  addMonitorVisible.value = true;

  if (policies.value.length === 0) {
    const res = await request.get('/policy/', { params: { size: 1000 } });
    if (res.code === 200) policies.value = res.items || [];
  }
};

const unprobedDomainList = computed(() => {
  const scopes = currentRecord.value?.scope_array || [];
  return scopes.filter(d => getDomainStatus(currentRecord.value, d) === 'unprobed');
});

const probedDomainList = computed(() => {
  const scopes = currentRecord.value?.scope_array || [];
  return scopes.filter(d => getDomainStatus(currentRecord.value, d) === 'probed');
});

const selectAllDomains = () => {
  if (currentRecord.value && currentRecord.value.scope_array) {
    addMonitorForm.domains = [...currentRecord.value.scope_array];
  }
};

const selectUnprobedDomains = () => {
  if (currentRecord.value && currentRecord.value.scope_array) {
    addMonitorForm.domains = unprobedDomainList.value.length > 0 ? [...unprobedDomainList.value] : [...currentRecord.value.scope_array];
  }
};

const selectProbedDomains = () => {
  if (currentRecord.value && currentRecord.value.scope_array) {
    addMonitorForm.domains = [...probedDomainList.value];
  }
};

const clearDomains = () => {
  addMonitorForm.domains = [];
};

const submitAddMonitor = async () => {
  try {
    await addMonitorFormRef.value.validate();
    addMonitorLoading.value = true;

    const payload = {
      scope_id: currentRecord.value._id,
      domain: addMonitorForm.domains.join(','),
      interval: addMonitorForm.interval_hours * 3600,
      policy_id: addMonitorForm.policy_id,
      name: ''
    };
    
    if (addMonitorForm.task_type === 'oneshot') {
      delete payload.interval;
    }

    const apiUrl = addMonitorForm.task_type === 'oneshot' ? '/scheduler/one_time_scan/' : '/scheduler/add/';
    const res = await request.post(apiUrl, payload);

    if (res.code === 200) {
      const successCount = (res.data || res.items || []).length;
      const countMsg = successCount > 0 ? `，共成功下发 ${successCount} 个任务！` : '！';
      
      message.success(addMonitorForm.task_type === 'oneshot' ? `一次性监控任务下发成功${countMsg}` : `添加监控任务成功${countMsg}`);
      addMonitorVisible.value = false;
    } else if (res.code === 699) {
      message.error(res.message);
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

const openAddSiteMonitorModal = (record) => {
  currentRecord.value = record;
  addSiteMonitorForm.interval_hours = 24;
  addSiteMonitorVisible.value = true;
};

const submitAddSiteMonitor = async () => {
  try {
    await addSiteMonitorFormRef.value.validate();
    addSiteMonitorLoading.value = true;

    const payload = {
      scope_id: currentRecord.value._id,
      interval: addSiteMonitorForm.interval_hours * 3600
    };

    const res = await request.post('/scheduler/add/site_monitor/', payload);

    if (res.code === 200) {
      message.success('添加站点监控任务成功！');
      addSiteMonitorVisible.value = false;
    } else if (res.code === 1607) {
      message.error(res.message);
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

const openAddWihMonitorModal = (record) => {
  currentRecord.value = record;
  addWihMonitorForm.interval_hours = 24;
  addWihMonitorVisible.value = true;
};

const submitAddWihMonitor = async () => {
  try {
    await addWihMonitorFormRef.value.validate();
    addWihMonitorLoading.value = true;

    const payload = {
      scope_id: currentRecord.value._id,
      interval: addWihMonitorForm.interval_hours * 3600
    };

    const res = await request.post('/scheduler/add/wih_monitor/', payload);

    if (res.code === 200) {
      message.success('添加WIH监控任务成功！');
      addWihMonitorVisible.value = false;
    } else if (res.code === 1607) {
      message.error(res.message);
    } else {
      message.error('添加失败: ' + res.message);
    }
  } catch (error) {
    console.warn('校验失败或请求异常', error);
  } finally {
    addWihMonitorLoading.value = false;
  }
};

// 监听路由参数联动
watch(() => route.query.scope_id, (newScopeId) => {
  searchForm.value._id = newScopeId || undefined;
  pagination.current = 1;
  fetchData();
}, { immediate: true });

onActivated(() => {
  if (route.path === '/group') {
    fetchData(true);
  }
});

onDeactivated(() => {
  stopPoll();
});

onUnmounted(() => {
  stopPoll();
});

</script>

<style scoped>
.arl-scope-visual-panel {
  border: 1px solid var(--arl-border-color, #e2e8f0);
  border-radius: 8px;
  padding: 12px;
  background: var(--arl-bg-light, rgba(0, 0, 0, 0.02));
}

.arl-scope-tag-container {
  max-height: 220px;
  min-height: 110px;
  overflow-y: auto;
  padding: 8px;
  border: 1px dashed var(--arl-border-color, #d9d9d9);
  border-radius: 6px;
  background: var(--arl-bg-white, #ffffff);
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  align-content: flex-start;
}

.arl-scope-edit-item-tag {
  margin: 0 !important;
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  transition: all 0.2s;
  background: var(--arl-bg-light, #f1f5f9);
  border-color: var(--arl-border-color, #d9d9d9);
  color: var(--arl-text-color, rgba(0, 0, 0, 0.85));
}

.arl-scope-edit-item-tag:hover {
  border-color: #ff4d4f !important;
  background: #fff1f0 !important;
  color: #cf1322 !important;
}

.arl-scope-empty-hint {
  width: 100%;
  text-align: center;
  color: var(--arl-text-color, #8c8c8c);
  opacity: 0.55;
  padding: 36px 0;
  font-size: 13px;
}
</style>