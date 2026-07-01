<template>
  <div style="background-color: #fff; padding: 24px; min-height: calc(100vh - 64px);">
    <a-tabs v-model:activeKey="activeTab" type="card">
      
      <!-- ================= Tab 1: 监控策略管理 (原GitHub监控) ================= -->
      <a-tab-pane key="scheduler" tab="监控策略管理">
        <div style="margin-bottom: 20px; display: flex; justify-content: space-between;">
          <a-button type="primary" style="background-color: #00bcd4; border-color: #00bcd4;" @click="openSchedulerAdd">添加策略</a-button>
          <a-button type="dashed" @click="fetchSchedulerData">
            <template #icon><sync-outlined /></template>
            刷新列表
          </a-button>
        </div>

        <!-- 策略搜索栏 -->
        <div class="search-row" style="margin-bottom: 16px; background-color: #f9f9f9; padding: 16px; border-radius: 4px;">
          <div class="search-item">
            <span class="label">策略名称：</span>
            <a-input v-model:value="schedulerSearchForm.name" placeholder="请输入策略名称" style="width: 180px;" allowClear @pressEnter="onSchedulerSearch">
              <template #suffix><search-outlined @click="onSchedulerSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
            </a-input>
          </div>
          <div class="search-item">
            <span class="label">关键字：</span>
            <a-input v-model:value="schedulerSearchForm.keyword" placeholder="请输入关键字" style="width: 180px;" allowClear @pressEnter="onSchedulerSearch">
              <template #suffix><search-outlined @click="onSchedulerSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
            </a-input>
          </div>
          <div class="search-item">
            <span class="label">状态：</span>
            <a-select v-model:value="schedulerSearchForm.status" placeholder="请选择状态" style="width: 180px;" allowClear @change="onSchedulerSearch">
              <a-select-option value="running">running</a-select-option>
              <a-select-option value="stop">stop</a-select-option>
              <a-select-option value="error">error</a-select-option>
            </a-select>
          </div>
        </div>

        <!-- 批量操作 -->
        <div style="margin-bottom: 16px; display: flex; gap: 8px;">
          <a-popconfirm title="确认删除所选策略吗？" @confirm="handleSchedulerBatchDelete">
            <a-button :disabled="!schedulerHasSelected">批量删除</a-button>
          </a-popconfirm>
          <a-popconfirm title="确认停止所选策略吗？" @confirm="handleSchedulerBatchStop">
            <a-button :disabled="!schedulerHasSelected">批量停止</a-button>
          </a-popconfirm>
        </div>

        <!-- 策略表格 -->
        <a-table
            :row-selection="{ selectedRowKeys: schedulerSelectedRowKeys, onChange: onSchedulerSelectChange }"
            :loading="schedulerLoading"
            :dataSource="schedulerData"
            :columns="schedulerColumns"
            :pagination="false"
            size="middle"
            :rowKey="(record) => record._id"
        >
          <template #emptyText>
            <div style="padding: 40px 0;">
              <inbox-outlined style="font-size: 48px; color: #d9d9d9;" />
              <div style="color: #999; margin-top: 8px;">暂无策略数据</div>
            </div>
          </template>

          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'name'">
              <a style="color: #00bcd4; font-weight: 500;" @click="goToSchedulerDetail(record)">{{ record.name }}</a>
            </template>

            <template v-else-if="column.key === 'status'">
              <a-tag :color="record.status === 'running' ? 'blue' : record.status === 'stop' ? 'warning' : 'error'">
                {{ record.status }}
              </a-tag>
            </template>

            <template v-else-if="column.key === 'action'">
              <a-button
                  size="small"
                  style="margin-right: 8px;"
                  :disabled="record.status !== 'running'"
                  @click="handleSchedulerSingleAction('stop', record._id)"
              >停止</a-button>
              
              <a-button
                  size="small"
                  style="margin-right: 8px;"
                  :disabled="record.status !== 'stop' && record.status !== 'error'"
                  @click="handleSchedulerSingleAction('recover', record._id)"
              >恢复</a-button>

              <a-button size="small" style="margin-right: 8px;" @click="openSchedulerEdit(record)">修改</a-button>

              <a-popconfirm title="确认删除该策略？" @confirm="handleSchedulerSingleAction('delete', record._id)">
                <a-button size="small">删除</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>

        <!-- 策略分页 -->
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
          <div style="color: rgba(0,0,0,.65);">共 {{ Math.ceil(schedulerPagination.total / schedulerPagination.pageSize) || 1 }} 页 / {{ schedulerPagination.total }} 条数据</div>
          <a-pagination v-model:current="schedulerPagination.current" v-model:pageSize="schedulerPagination.pageSize" :total="schedulerPagination.total" show-size-changer @change="handleSchedulerTableChange" />
        </div>
      </a-tab-pane>

      <!-- ================= Tab 2: 扫描任务实例 (原GitHub管理) ================= -->
      <a-tab-pane key="task" tab="扫描任务实例">
        <div style="margin-bottom: 20px; display: flex; justify-content: space-between;">
          <a-button type="primary" style="background-color: #00bcd4; border-color: #00bcd4;" @click="openTaskAdd">新建单次任务</a-button>
          <a-button type="dashed" @click="fetchTaskData">
            <template #icon><sync-outlined /></template>
            刷新列表
          </a-button>
        </div>

        <!-- 任务搜索栏 -->
        <div class="search-row" style="margin-bottom: 16px; background-color: #f9f9f9; padding: 16px; border-radius: 4px;">
          <div class="search-item">
            <span class="label">任务名称：</span>
            <a-input v-model:value="taskSearchForm.name" placeholder="请输入任务名称" style="width: 180px;" allowClear @pressEnter="onTaskSearch">
              <template #suffix><search-outlined @click="onTaskSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
            </a-input>
          </div>
          <div class="search-item">
            <span class="label">关键字：</span>
            <a-input v-model:value="taskSearchForm.keyword" placeholder="请输入关键字" style="width: 180px;" allowClear @pressEnter="onTaskSearch">
              <template #suffix><search-outlined @click="onTaskSearch" style="cursor: pointer; color: rgba(0,0,0,0.25);" /></template>
            </a-input>
          </div>
          <div class="search-item">
            <span class="label">状态：</span>
            <a-select v-model:value="taskSearchForm.status" placeholder="请选择状态" style="width: 180px;" allowClear @change="onTaskSearch">
              <a-select-option value="waiting">waiting</a-select-option>
              <a-select-option value="running">running</a-select-option>
              <a-select-option value="done">done</a-select-option>
              <a-select-option value="error">error</a-select-option>
              <a-select-option value="stop">stop</a-select-option>
            </a-select>
          </div>
        </div>

        <!-- 批量操作 -->
        <div style="margin-bottom: 16px; display: flex; gap: 8px;">
          <a-popconfirm title="确认删除所选任务吗？" @confirm="handleTaskBatchDelete">
            <a-button :disabled="!taskHasSelected">批量删除</a-button>
          </a-popconfirm>
          <a-popconfirm title="确认停止所选任务吗？" @confirm="handleTaskBatchStop">
            <a-button :disabled="!taskHasSelected">批量停止</a-button>
          </a-popconfirm>
        </div>

        <!-- 任务表格 -->
        <a-table
            :row-selection="{ selectedRowKeys: taskSelectedRowKeys, onChange: onTaskSelectChange }"
            :loading="taskLoading"
            :dataSource="taskData"
            :columns="taskColumns"
            :pagination="false"
            size="middle"
            :rowKey="(record) => record._id"
        >
          <template #emptyText>
            <div style="padding: 40px 0;">
              <inbox-outlined style="font-size: 48px; color: #d9d9d9;" />
              <div style="color: #999; margin-top: 8px;">暂无扫描任务</div>
            </div>
          </template>

          <template #bodyCell="{ column, record }">
            <template v-if="column.key === 'name'">
              <a style="color: #00bcd4; font-weight: 500;" @click="goToTaskDetail(record)">{{ record.name }}</a>
            </template>

            <template v-else-if="column.key === 'status'">
              <a-tag
                  :color="
                  record.status === 'running' || record.status === 'waiting' ? 'blue' :
                  record.status === 'error' ? 'error' :
                  'success'
                "
              >
                {{ record.status }}
              </a-tag>
            </template>

            <template v-else-if="column.key === 'action'">
              <a-button
                  size="small"
                  style="margin-right: 8px;"
                  :disabled="record.status === 'done' || record.status === 'error'"
                  @click="handleTaskSingleAction('stop', record._id)"
              >停止</a-button>

              <a-popconfirm title="确认删除该任务？" @confirm="handleTaskSingleAction('delete', record._id)">
                <a-button size="small">删除</a-button>
              </a-popconfirm>
            </template>
          </template>
        </a-table>

        <!-- 任务分页 -->
        <div style="display: flex; justify-content: space-between; align-items: center; padding: 16px 0;">
          <div style="color: rgba(0,0,0,.65);">共 {{ Math.ceil(taskPagination.total / taskPagination.pageSize) || 1 }} 页 / {{ taskPagination.total }} 条数据</div>
          <a-pagination v-model:current="taskPagination.current" v-model:pageSize="taskPagination.pageSize" :total="taskPagination.total" show-size-changer @change="handleTaskTableChange" />
        </div>
      </a-tab-pane>
    </a-tabs>

    <!-- ================= 策略弹窗 (新增/修改) ================= -->
    <a-modal
        v-model:open="schedulerModalVisible"
        :title="schedulerIsEdit ? '修改策略' : '添加策略'"
        @ok="submitSchedulerModal"
        :confirmLoading="schedulerSubmitLoading"
        width="520px"
        okText="确定"
        cancelText="取消"
        destroyOnClose
    >
      <a-form :model="schedulerForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">
        <a-form-item label="策略名称" required>
          <a-input v-model:value="schedulerForm.name" placeholder="请输入策略名" />
        </a-form-item>

        <a-form-item label="关键字" required>
          <a-input v-model:value="schedulerForm.keyword" placeholder="请输入关键字" />
        </a-form-item>

        <a-form-item label="cron表达式" required>
          <a-input v-model:value="schedulerForm.cron" placeholder="请输入cron表达式，如 */30 * * * *" />
        </a-form-item>
      </a-form>
    </a-modal>

    <!-- ================= 任务弹窗 (新增) ================= -->
    <a-modal
        v-model:open="taskModalVisible"
        title="新建单次扫描"
        @ok="submitTaskModal"
        :confirmLoading="taskSubmitLoading"
        width="520px"
        okText="确定"
        cancelText="取消"
        destroyOnClose
    >
      <a-form :model="taskForm" :label-col="{ span: 5 }" :wrapper-col="{ span: 18 }" style="margin-top: 20px;">
        <a-form-item label="任务名称" required>
          <a-input v-model:value="taskForm.name" placeholder="请输入任务名称" />
        </a-form-item>

        <a-form-item label="关键字" required>
          <a-input v-model:value="taskForm.keyword" placeholder="请输入关键字" />
        </a-form-item>
      </a-form>
    </a-modal>

  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue';
import { useRouter, useRoute } from 'vue-router';
import request from '../utils/request';
import { message } from 'ant-design-vue';
import { SearchOutlined, InboxOutlined, SyncOutlined } from '@ant-design/icons-vue';

const router = useRouter();
const route = useRoute();
const activeTab = ref('scheduler');

// 💡 优先识别 URL 中传过来的参数（例如 dashboard 跳转过来默认指向对应 Tab）
onMounted(() => {
  if (route.query.tab === 'task') {
    activeTab.value = 'task';
  }
  fetchSchedulerData();
  fetchTaskData();
});

// 监听 Tab 切换，按需重新拉取
watch(activeTab, (newTab) => {
  if (newTab === 'scheduler') {
    fetchSchedulerData();
  } else {
    fetchTaskData();
  }
});


// ==========================================
// ⚙️ 模块 A: 监控策略管理 (github_scheduler)
// ==========================================
const schedulerLoading = ref(false);
const schedulerData = ref([]);
const schedulerSearchForm = reactive({ name: '', keyword: '', status: undefined });
const schedulerPagination = reactive({ current: 1, pageSize: 10, total: 0 });

const schedulerSelectedRowKeys = ref([]);
const schedulerHasSelected = computed(() => schedulerSelectedRowKeys.value.length > 0);
const onSchedulerSelectChange = (keys) => { schedulerSelectedRowKeys.value = keys; };

const schedulerColumns = [
  { title: '策略名称', dataIndex: 'name', key: 'name', width: 150 },
  { title: '关键字', dataIndex: 'keyword', key: 'keyword', width: 150 },
  { title: 'cron表达式', dataIndex: 'cron', key: 'cron', width: 150 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '运行次数', dataIndex: 'run_number', key: 'run_number', width: 100 },
  { title: '上次运行时间', dataIndex: 'last_run_date', key: 'last_run_date', width: 180 },
  { title: '下次运行时间', dataIndex: 'next_run_date', key: 'next_run_date', width: 180 },
  { title: '操作', key: 'action', width: 280 }
];

const fetchSchedulerData = async () => {
  schedulerLoading.value = true;
  try {
    const params = { page: schedulerPagination.current, size: schedulerPagination.pageSize };
    if (schedulerSearchForm.name) params.name = schedulerSearchForm.name;
    if (schedulerSearchForm.keyword) params.keyword = schedulerSearchForm.keyword;
    if (schedulerSearchForm.status) params.status = schedulerSearchForm.status;

    const res = await request.get('/github_scheduler/', { params });
    if (res.code === 200) {
      schedulerData.value = res.items || [];
      schedulerPagination.total = res.total || 0;
      schedulerSelectedRowKeys.value = [];
    }
  } catch (error) {
    message.error('加载监控策略失败');
  } finally {
    schedulerLoading.value = false;
  }
};

const onSchedulerSearch = () => { schedulerPagination.current = 1; fetchSchedulerData(); };
const handleSchedulerTableChange = (page, pageSize) => {
  schedulerPagination.current = page;
  schedulerPagination.pageSize = pageSize;
  fetchSchedulerData();
};

const goToSchedulerDetail = (record) => {
  router.push({ path: '/GitHubMonitor/GitHubMonitorInfo', query: { _id: record._id } });
};

const performSchedulerAction = async (actionType, idArray) => {
  try {
    const url = `/github_scheduler/${actionType}/`;
    const res = await request.post(url, { _id: idArray });
    if (res.code === 200) {
      message.success('操作成功！');
      fetchSchedulerData();
    } else {
      message.error(res.message || '操作失败');
    }
  } catch (e) {
    message.error('请求异常');
  }
};

const handleSchedulerSingleAction = (type, id) => performSchedulerAction(type, [id]);
const handleSchedulerBatchDelete = () => performSchedulerAction('delete', schedulerSelectedRowKeys.value);
const handleSchedulerBatchStop = () => performSchedulerAction('stop', schedulerSelectedRowKeys.value);

// 策略弹窗逻辑
const schedulerModalVisible = ref(false);
const schedulerSubmitLoading = ref(false);
const schedulerIsEdit = ref(false);
const schedulerEditId = ref('');
const schedulerForm = reactive({ name: '', keyword: '', cron: '' });

const openSchedulerAdd = () => {
  schedulerIsEdit.value = false;
  schedulerEditId.value = '';
  Object.assign(schedulerForm, { name: '', keyword: '', cron: '' });
  schedulerModalVisible.value = true;
};

const openSchedulerEdit = (record) => {
  schedulerIsEdit.value = true;
  schedulerEditId.value = record._id;
  Object.assign(schedulerForm, { name: record.name, keyword: record.keyword, cron: record.cron });
  schedulerModalVisible.value = true;
};

const submitSchedulerModal = async () => {
  if (!schedulerForm.name || !schedulerForm.keyword || !schedulerForm.cron) {
    return message.warning('请填写所有必填项！');
  }
  schedulerSubmitLoading.value = true;
  try {
    let res;
    if (schedulerIsEdit.value) {
      const payload = { _id: schedulerEditId.value, ...schedulerForm };
      res = await request.post('/github_scheduler/update/', payload);
    } else {
      res = await request.post('/github_scheduler/', schedulerForm);
    }
    if (res.code === 200) {
      message.success(`${schedulerIsEdit.value ? '修改' : '添加'}策略成功！`);
      schedulerModalVisible.value = false;
      onSchedulerSearch();
    } else {
      message.error(res.message || '操作失败');
    }
  } catch (error) {
    message.error('请求异常');
  } finally {
    schedulerSubmitLoading.value = false;
  }
};


// ==========================================
// 👷 模块 B: 扫描任务实例 (github_task)
// ==========================================
const taskLoading = ref(false);
const taskData = ref([]);
const taskSearchForm = reactive({ name: '', keyword: '', status: undefined });
const taskPagination = reactive({ current: 1, pageSize: 10, total: 0 });

const taskSelectedRowKeys = ref([]);
const taskHasSelected = computed(() => taskSelectedRowKeys.value.length > 0);
const onTaskSelectChange = (keys) => { taskSelectedRowKeys.value = keys; };

const taskColumns = [
  { title: '任务名', dataIndex: 'name', key: 'name', width: 150 },
  { title: '关键字', dataIndex: 'keyword', key: 'keyword', width: 150 },
  { title: '结果数目', dataIndex: 'result_count', key: 'result_count', width: 100 },
  { title: '状态', dataIndex: 'status', key: 'status', width: 100 },
  { title: '开始时间', dataIndex: 'start_time', key: 'start_time', width: 180 },
  { title: '结束时间', dataIndex: 'end_time', key: 'end_time', width: 180 },
  { title: '任务id', dataIndex: '_id', key: '_id', width: 200 },
  { title: '操作', key: 'action', width: 150 }
];

const fetchTaskData = async () => {
  taskLoading.value = true;
  try {
    const params = { page: taskPagination.current, size: taskPagination.pageSize };
    if (taskSearchForm.name) params.name = taskSearchForm.name;
    if (taskSearchForm.keyword) params.keyword = taskSearchForm.keyword;
    if (taskSearchForm.status) params.status = taskSearchForm.status;

    const res = await request.get('/github_task/', { params });
    if (res.code === 200) {
      taskData.value = res.items || [];
      taskPagination.total = res.total || 0;
      taskSelectedRowKeys.value = [];
    }
  } catch (error) {
    message.error('加载扫描任务失败');
  } finally {
    taskLoading.value = false;
  }
};

const onTaskSearch = () => { taskPagination.current = 1; fetchTaskData(); };
const handleTaskTableChange = (page, pageSize) => {
  taskPagination.current = page;
  taskPagination.pageSize = pageSize;
  fetchTaskData();
};

const goToTaskDetail = (record) => {
  router.push({ path: '/GitHubTasks/GitHubTasksInfo', query: { _id: record._id } });
};

const performTaskAction = async (actionType, idArray) => {
  try {
    const url = `/github_task/${actionType}/`;
    const res = await request.post(url, { _id: idArray });
    if (res.code === 200) {
      message.success('操作成功！');
      fetchTaskData();
    } else {
      message.error(res.message || '操作失败');
    }
  } catch (e) {
    message.error('请求异常');
  }
};

const handleTaskSingleAction = (type, id) => performTaskAction(type, [id]);
const handleTaskBatchDelete = () => performTaskAction('delete', taskSelectedRowKeys.value);
const handleTaskBatchStop = () => performTaskAction('stop', taskSelectedRowKeys.value);

// 新增任务弹窗
const taskModalVisible = ref(false);
const taskSubmitLoading = ref(false);
const taskForm = reactive({ name: '', keyword: '' });

const openTaskAdd = () => {
  taskForm.name = '';
  taskForm.keyword = '';
  taskModalVisible.value = true;
};

const submitTaskModal = async () => {
  if (!taskForm.name || !taskForm.keyword) {
    return message.warning('请填写任务名称和关键字！');
  }
  taskSubmitLoading.value = true;
  try {
    const res = await request.post('/github_task/', taskForm);
    if (res.code === 200) {
      message.success('新建单次扫描任务成功！');
      taskModalVisible.value = false;
      onTaskSearch();
    } else {
      message.error('下发失败: ' + res.message);
    }
  } catch (error) {
    message.error('请求异常');
  } finally {
    taskSubmitLoading.value = false;
  }
};
</script>

<style scoped>
.search-row { display: flex; flex-wrap: wrap; gap: 16px 12px; align-items: center; }
.search-item { display: flex; align-items: center; }
.search-item .label { color: rgba(0,0,0,0.85); margin-right: 8px; min-width: 70px; text-align: right; white-space: nowrap; }
</style>
