<!-- ARL-Next/frontend/src/views/platform/ScheduleConfig.vue -->
<template>
  <div class="schedule-config">
    <div class="toolbar">
      <a-button type="primary" @click="handleCreate">
        <template #icon><PlusOutlined /></template>
        新建调度
      </a-button>
      <a-button @click="loadSchedules">
        <template #icon><ReloadOutlined /></template>
        刷新
      </a-button>
    </div>

    <a-table
      :columns="columns"
      :data-source="schedules"
      :loading="loading.schedules"
      row-key="_id"
      size="small"
    >
      <template #bodyCell="{ column, record }">
        <template v-if="column.key === 'platform'">
          <PlatformTag :platform="record.platform" />
        </template>
        <template v-else-if="column.key === 'profile'">
          <a-tag>{{ profileLabel(record.profile) }}</a-tag>
        </template>
        <template v-else-if="column.key === 'enabled'">
          <a-switch
            :checked="record.enabled"
            @change="(val) => handleToggle(record, val)"
          />
        </template>
        <template v-else-if="column.key === 'action'">
          <a-button
            type="link"
            size="small"
            @click="handleEdit(record)"
          >
            编辑
          </a-button>
          <a-popconfirm
            title="确认删除该调度？"
            @confirm="handleDelete(record)"
          >
            <a-button type="link" size="small" danger>
              删除
            </a-button>
          </a-popconfirm>
        </template>
      </template>
    </a-table>

    <a-modal
      v-model:open="modal.visible"
      :title="modal.form.id ? '编辑调度' : '新建调度'"
      @ok="handleSave"
    >
      <a-form :model="modal.form" layout="vertical">
        <a-form-item label="项目指纹">
          <a-input
            v-model:value="modal.form.project_fingerprint"
            placeholder="输入项目 fingerprint"
            :disabled="!!modal.form.id"
          />
        </a-form-item>
        <a-form-item label="扫描策略">
          <a-radio-group v-model:value="modal.form.profile">
            <a-radio value="quick">快速侦察</a-radio>
            <a-radio value="full">深度扫描</a-radio>
            <a-radio value="incremental">增量复扫</a-radio>
          </a-radio-group>
        </a-form-item>
        <a-form-item label="Cron 表达式">
          <a-input
            v-model:value="modal.form.cron_expression"
            placeholder="例如：0 2 * * *"
          />
          <div class="cron-hint">
            常用示例：
            <a-tag @click="modal.form.cron_expression = '0 2 * * *'">
              每天 2 点
            </a-tag>
            <a-tag @click="modal.form.cron_expression = '0 */6 * * *'">
              每 6 小时
            </a-tag>
            <a-tag @click="modal.form.cron_expression = '0 8 * * 1'">
              每周一 8 点
            </a-tag>
          </div>
        </a-form-item>
        <a-form-item label="启用">
          <a-switch v-model:checked="modal.form.enabled" />
        </a-form-item>
      </a-form>
    </a-modal>
  </div>
</template>

<script setup>
import { reactive, onMounted } from 'vue'
import { message } from 'ant-design-vue'
import {
  PlusOutlined,
  ReloadOutlined,
} from '@ant-design/icons-vue'
import PlatformTag from '@/components/platform/PlatformTag.vue'
import { usePlatformStore } from '@/stores/platform'

const {
  schedules,
  loading,
  loadSchedules,
  saveSchedule,
  switchSchedule,
  deleteSchedule,
} = usePlatformStore()

const columns = [
  { title: '项目指纹', dataIndex: 'project_fingerprint', key: 'project_fingerprint', ellipsis: true },
  { title: '平台', key: 'platform', width: 100 },
  { title: '扫描策略', key: 'profile', width: 120 },
  { title: 'Cron', dataIndex: 'cron_expression', key: 'cron_expression', width: 140 },
  { title: '启用', key: 'enabled', width: 80 },
  { title: '上次执行', dataIndex: 'last_run', key: 'last_run', width: 160 },
  { title: '操作', key: 'action', width: 140 },
]

const modal = reactive({
  visible: false,
  form: {
    id: null,
    project_fingerprint: '',
    profile: 'quick',
    cron_expression: '0 2 * * *',
    enabled: true,
  },
})

onMounted(() => {
  loadSchedules()
})

function profileLabel(p) {
  return { quick: '快速', full: '深度', incremental: '增量' }[p] || p
}

function handleCreate() {
  Object.assign(modal.form, {
    id: null,
    project_fingerprint: '',
    profile: 'quick',
    cron_expression: '0 2 * * *',
    enabled: true,
  })
  modal.visible = true
}

function handleEdit(record) {
  Object.assign(modal.form, record)
  modal.visible = true
}

async function handleSave() {
  if (!modal.form.project_fingerprint) {
    message.warning('请填写项目指纹')
    return
  }
  try {
    await saveSchedule(modal.form)
    message.success('保存成功')
    modal.visible = false
    loadSchedules()
  } catch (e) {
    message.error(e.message)
  }
}

async function handleToggle(record, enabled) {
  try {
    await switchSchedule(record._id, enabled)
    message.success(enabled ? '已启用' : '已禁用')
  } catch (e) {
    message.error(e.message)
  }
}

async function handleDelete(record) {
  try {
    await deleteSchedule(record._id)
    message.success('已删除')
    loadSchedules()
  } catch (e) {
    message.error(e.message)
  }
}
</script>

<style scoped>
.schedule-config { padding: 16px; }
.toolbar {
  display: flex;
  justify-content: space-between;
  margin-bottom: 16px;
}
.cron-hint {
  margin-top: 8px;
  font-size: 12px;
  color: #8c8c8c;
}
.cron-hint .ant-tag {
  cursor: pointer;
  margin-left: 4px;
}
</style>