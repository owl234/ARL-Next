<template>
  <a-modal
    :open="open"
    :title="taskText('tasks.excelExportModalTitle')"
    width="620px"
    wrapClassName="arl-theme-modal"
    rootClassName="arl-theme-modal"
    :confirmLoading="exporting"
    :okText="taskText('tasks.excelExportConfirmBtn')"
    :cancelText="taskText('tasks.cancel')"
    :okButtonProps="{ disabled: isConfirmDisabled }"
    :maskClosable="!exporting"
    :closable="!exporting"
    @ok="handleConfirmExport"
    @cancel="handleCancel"
  >
    <div class="excel-export-modal-body">
      <!-- 1. 超出任务数上限拦截提示 -->
      <a-alert
        v-if="isOverTaskLimit"
        type="error"
        show-icon
        style="margin-bottom: 12px;"
        :message="taskText('tasks.excelExportTooManyTasks', { max: MAX_EXCEL_EXPORT_TASKS, count: tasks.length })"
      />

      <!-- 2. 进行中/排队中任务快照提示 -->
      <a-alert
        v-if="activeTaskCount > 0"
        type="warning"
        show-icon
        style="margin-bottom: 12px;"
        :message="taskText('tasks.excelExportActiveTasksNotice', { count: activeTaskCount })"
      />

      <!-- 3. 待导出任务复核清单（支持跨页勾选复核与折叠展开） -->
      <div class="export-section-box">
        <div class="export-summary-line">
          {{ taskText('tasks.excelExportSelectedSummary', { count: tasks.length }) }}
        </div>
        <div class="export-task-list-box">
          <div class="export-list-heading">{{ taskText('tasks.excelExportTaskListHeading') }}</div>
          <div class="export-task-items">
            <div v-for="(item, idx) in visibleTasks" :key="item.id || idx" class="export-task-item">
              <span class="export-task-idx">{{ idx + 1 }}.</span>
              <span class="export-task-label">{{ item.label }}</span>
              <a-tag
                v-if="item.status && isActiveTaskStatus(item.status)"
                color="processing"
                class="export-task-status-tag"
              >
                {{ formatTaskStatus(item.status) }}
              </a-tag>
            </div>
          </div>
          <div v-if="hasOverflowTasks" class="export-list-toggle">
            <a href="javascript:void(0)" @click.prevent="tasksExpanded = !tasksExpanded">
              {{ tasksExpanded ? taskText('assets.collapseList') : taskText('assets.expandAllCount', { count: tasks.length }) }}
            </a>
          </div>
          <div v-if="crossPageCount > 0" class="export-cross-page-note">
            {{ taskText('tasks.includesCountSelectionsRetainedFromOtherPages', { count: crossPageCount }) }}
          </div>
        </div>
      </div>

      <!-- 4. 工作表维度选择区 -->
      <div class="export-section-box">
        <div class="export-section-header">
          <span class="export-section-title">{{ taskText('tasks.excelExportSheetsLabel') }}</span>
          <div class="export-quick-actions">
            <a-button type="link" size="small" @click="selectAllSheets">{{ taskText('tasks.excelExportSelectAll') }}</a-button>
            <a-button type="link" size="small" @click="resetDefaultSheets">{{ taskText('tasks.excelExportResetDefault') }}</a-button>
            <a-button type="link" size="small" @click="clearSheets">{{ taskText('tasks.excelExportClearSheets') }}</a-button>
          </div>
        </div>

        <a-checkbox-group v-model:value="selectedSheets" style="width: 100%;">
          <div class="sheet-group-label">{{ taskText('tasks.excelExportCoreGroupTitle') }}</div>
          <a-row :gutter="[8, 8]" style="margin-bottom: 12px;">
            <a-col :xs="12" :sm="8" v-for="item in defaultSheetOptions" :key="item.key">
              <a-checkbox :value="item.key">{{ taskText(item.i18nKey) }}</a-checkbox>
            </a-col>
          </a-row>

          <div class="sheet-group-label">{{ taskText('tasks.excelExportExtendedGroupTitle') }}</div>
          <a-row :gutter="[8, 8]">
            <a-col :xs="12" :sm="8" v-for="item in extendedSheetOptions" :key="item.key">
              <a-checkbox :value="item.key">{{ taskText(item.i18nKey) }}</a-checkbox>
            </a-col>
          </a-row>
        </a-checkbox-group>

        <div class="export-hint-caption">
          {{ taskText('tasks.excelExportEmptyAndCapHint', { maxRows: MAX_EXCEL_ROWS_PER_SHEET }) }}
        </div>
      </div>

      <!-- 5. 跨任务资产去重开关 -->
      <div class="export-dedup-box">
        <a-checkbox v-model:checked="deduplicate">
          <span class="dedup-label">{{ taskText('tasks.excelExportDeduplicateLabel') }}</span>
        </a-checkbox>
        <div class="dedup-hint">{{ taskText('tasks.excelExportDeduplicateHint') }}</div>
      </div>
    </div>
  </a-modal>
</template>

<script setup>
import { ref, computed, watch } from 'vue';
import { message } from 'ant-design-vue';
import { useI18n } from 'vue-i18n';
import request from '../utils/request';
import { formatTaskStatus } from '../constants/taskStatus';
import {
  ALL_EXCEL_SHEETS,
  DEFAULT_EXCEL_SHEETS,
  EXCEL_SHEET_OPTIONS,
  MAX_EXCEL_EXPORT_TASKS,
  MAX_EXCEL_ROWS_PER_SHEET,
  SHEET_I18N_KEY_MAP,
  buildExcelExportPayload,
  extractBlobErrorMessage,
  isActiveTaskStatus,
  parseExportResponseHeaders,
  parseFilenameFromContentDisposition,
} from '../utils/taskExcelExport';

const props = defineProps({
  open: { type: Boolean, default: false },
  tasks: { type: Array, default: () => [] },
  crossPageCount: { type: Number, default: 0 },
});

const emit = defineEmits(['update:open', 'exported']);

const { t: taskText } = useI18n({ useScope: 'global' });

const PREVIEW_LIMIT = 10;
const exporting = ref(false);
const tasksExpanded = ref(false);
const selectedSheets = ref([...DEFAULT_EXCEL_SHEETS]);
const deduplicate = ref(true);

const defaultSheetOptions = EXCEL_SHEET_OPTIONS.filter((item) => item.group === 'default');
const extendedSheetOptions = EXCEL_SHEET_OPTIONS.filter((item) => item.group === 'extended');

const isOverTaskLimit = computed(() => props.tasks.length > MAX_EXCEL_EXPORT_TASKS);
const activeTaskCount = computed(() => props.tasks.filter((item) => isActiveTaskStatus(item?.status)).length);
const hasOverflowTasks = computed(() => props.tasks.length > PREVIEW_LIMIT);
const visibleTasks = computed(() => (
  tasksExpanded.value || !hasOverflowTasks.value
    ? props.tasks
    : props.tasks.slice(0, PREVIEW_LIMIT)
));
const isConfirmDisabled = computed(() => (
  exporting.value
  || props.tasks.length === 0
  || isOverTaskLimit.value
  || selectedSheets.value.length === 0
));

watch(() => props.open, (isOpen) => {
  if (isOpen) {
    tasksExpanded.value = false;
  }
});

const selectAllSheets = () => {
  selectedSheets.value = [...ALL_EXCEL_SHEETS];
};

const resetDefaultSheets = () => {
  selectedSheets.value = [...DEFAULT_EXCEL_SHEETS];
};

const clearSheets = () => {
  selectedSheets.value = [];
};

const handleCancel = () => {
  if (exporting.value) return;
  emit('update:open', false);
};

const handleConfirmExport = async () => {
  if (exporting.value) return;
  if (props.tasks.length === 0) {
    message.warning(taskText('tasks.selectTasksToExportFirst'));
    return;
  }
  if (isOverTaskLimit.value) {
    message.error(taskText('tasks.excelExportTooManyTasks', { max: MAX_EXCEL_EXPORT_TASKS, count: props.tasks.length }));
    return;
  }
  if (selectedSheets.value.length === 0) {
    message.warning(taskText('tasks.excelExportSelectAtLeastOneSheet'));
    return;
  }

  const payload = buildExcelExportPayload({
    taskIds: props.tasks.map((item) => item.id),
    sheets: selectedSheets.value,
    deduplicate: deduplicate.value,
  });

  exporting.value = true;
  const loadingKey = 'batch_excel_export';
  message.loading({ content: taskText('tasks.generatingExcelExport'), key: loadingKey, duration: 0 });

  try {
    const response = await request.post('/export/batch/', payload, {
      responseType: 'blob',
      returnFullResponse: true,
      timeout: 300000,
    });

    const headers = response?.headers || {};
    const rawBlob = response?.data instanceof Blob
      ? response.data
      : new Blob([response?.data || response], {
          type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        });

    const contentType = String(headers['content-type'] || rawBlob.type || '').toLowerCase();
    if (contentType.includes('application/json')) {
      const errMsg = await extractBlobErrorMessage(rawBlob, taskText('tasks.unknownError'));
      message.error({
        content: taskText('tasks.excelExportFailedWithReason', { reason: errMsg }),
        key: loadingKey,
        duration: 4,
      });
      return;
    }

    const fallbackName = props.tasks.length === 1
      ? `ARL_Task_${props.tasks[0].id}_Export.xlsx`
      : `ARL_Batch_Export_${props.tasks.length}_Tasks.xlsx`;
    const filename = parseFilenameFromContentDisposition(headers['content-disposition'], fallbackName);

    const downloadUrl = window.URL.createObjectURL(rawBlob);
    const link = document.createElement('a');
    link.href = downloadUrl;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(downloadUrl);

    const meta = parseExportResponseHeaders(headers);
    if (meta.truncated && meta.truncatedSheets.length > 0) {
      const localizedSheets = meta.truncatedSheets
        .map((key) => (SHEET_I18N_KEY_MAP[key] ? taskText(SHEET_I18N_KEY_MAP[key]) : key))
        .join('、');
      message.warning({
        content: taskText('tasks.excelExportTruncatedWarning', {
          maxRows: MAX_EXCEL_ROWS_PER_SHEET,
          sheets: localizedSheets,
        }),
        key: loadingKey,
        duration: 6,
      });
    } else {
      message.success({
        content: taskText('tasks.excelExportCompleted'),
        key: loadingKey,
        duration: 2,
      });
    }

    emit('exported', { payload, meta, filename });
    emit('update:open', false);
  } catch (error) {
    const reason = await extractBlobErrorMessage(error, taskText('tasks.exportFailedCheckTheConsole'));
    message.error({
      content: taskText('tasks.excelExportFailedWithReason', { reason }),
      key: loadingKey,
      duration: 4,
    });
  } finally {
    exporting.value = false;
  }
};
</script>

<style scoped>
.excel-export-modal-body {
  padding-top: 4px;
}

.export-section-box {
  margin-bottom: 14px;
}

.export-summary-line {
  font-size: 13px;
  color: var(--arl-text-color);
  margin-bottom: 8px;
}

.export-task-list-box {
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
  padding: 8px 10px;
  font-size: 12px;
}

.export-list-heading {
  font-weight: 500;
  margin-bottom: 6px;
  color: var(--arl-text-color);
  opacity: 0.9;
}

.export-task-items {
  max-height: 150px;
  overflow-y: auto;
  line-height: 1.65;
}

.export-task-item {
  display: flex;
  align-items: center;
  gap: 6px;
  word-break: break-all;
}

.export-task-idx {
  color: var(--arl-text-secondary);
  flex-shrink: 0;
}

.export-task-label {
  color: var(--arl-text-color);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.export-task-status-tag {
  margin: 0;
  font-size: 11px;
  line-height: 16px;
  padding: 0 5px;
  flex-shrink: 0;
}

.export-list-toggle {
  margin-top: 6px;
  padding-top: 6px;
  border-top: 1px dashed var(--arl-border-color);
}

.export-cross-page-note {
  margin-top: 6px;
  color: #d48806;
}

.export-section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.export-section-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--arl-text-color);
}

.export-quick-actions {
  display: inline-flex;
  align-items: center;
  gap: 2px;
}

.sheet-group-label {
  font-size: 12px;
  color: var(--arl-text-secondary);
  margin-bottom: 6px;
}

.export-hint-caption {
  margin-top: 10px;
  font-size: 12px;
  color: var(--arl-text-secondary);
  line-height: 1.5;
}

.export-dedup-box {
  padding: 10px 12px;
  background: var(--arl-bg-light);
  border: 1px solid var(--arl-border-color);
  border-radius: 6px;
}

.dedup-label {
  font-weight: 500;
  color: var(--arl-text-color);
}

.dedup-hint {
  margin-top: 4px;
  padding-left: 24px;
  font-size: 12px;
  color: var(--arl-text-secondary);
  line-height: 1.5;
}
</style>
