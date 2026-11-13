<template>
  <div class="tab-content" style="padding: 20px;">
    <!-- 顶层操作看板 -->
    <a-card data-setting-anchor="backup" :title="pageText('pages.backupTitle')" :bordered="false" style="max-width: 1050px; margin-bottom: 20px;">
      <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap; gap: 16px;">
        <div style="max-width: 620px;">
          <div style="font-size: 14px; font-weight: 500; margin-bottom: 6px; color: var(--arl-text-color);">{{ pageText('pages.backupSnapshot') }}</div>
          <div style="font-size: 13px; color: var(--arl-text-color); opacity: 0.65; line-height: 1.6;">{{ pageText('pages.backupDescription') }}</div>
        </div>

        <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
          <a-button type="primary" @click="openCreateBackupModal" :loading="backupLoading">
            <template #icon><CloudUploadOutlined /></template>{{ pageText('pages.backupCreate') }}</a-button>

          <a-button @click="openUploadBackupModal">
            <template #icon><UploadOutlined /></template>{{ pageText('pages.backupUpload') }}</a-button>

          <a-button @click="fetchBackupList" :loading="backupListLoading">
            <template #icon><ReloadOutlined /></template>{{ pageText('pages.backupRefresh') }}</a-button>
        </div>
      </div>

      <a-alert
        v-if="backupRunningTasks > 0"
        type="warning"
        show-icon
        style="margin-top: 16px; border-radius: 6px;"
        :message="pageText('pages.backupRunningWarning', { count: backupRunningTasks })"
      />
    </a-card>

    <!-- 现存备份归档表格 -->
    <a-card :title="pageText('pages.backupArchives')" :bordered="false" style="max-width: 1050px;">
      <a-table
        :dataSource="backupList"
        :columns="backupColumns"
        rowKey="filename"
        :loading="backupListLoading"
        size="small"
        :pagination="{
          pageSize: globalPageSize,
          showSizeChanger: true,
          pageSizeOptions: $pageSizeOptions,
          size: 'small',
          onChange: handleBackupPageChange,
          onShowSizeChange: handleBackupPageChange,
          showTotal: total => pageText('pages.backupArchiveCount', { count: total })
        }"
      >
        <template #bodyCell="{ column, record }">
          <template v-if="column.key === 'filename'">
            <div style="font-family: monospace; font-weight: 600; color: var(--arl-text-color);">
              {{ record.filename }}
            </div>
            <div v-if="record.note" style="font-size: 12px; color: var(--arl-text-color); opacity: 0.6; margin-top: 2px;">
              📝 {{ record.note }}
            </div>
          </template>

          <template v-else-if="column.key === 'size'">
            <a-tag color="blue">{{ formatBytes(record.size) }}</a-tag>
          </template>

          <template v-else-if="column.key === 'include_screenshots'">
            <a-tag :color="record.include_screenshots ? 'cyan' : 'orange'">
              {{ record.include_screenshots ? pageText('pages.backupFull') : pageText('pages.backupCompact') }}
            </a-tag>
          </template>

          <template v-else-if="column.key === 'summary'">
            <div v-if="record.summary && record.summary.task_assets !== undefined" style="font-size: 12px; line-height: 1.5;">
              <div>{{ pageText('pages.backupTaskAssets') }}: <b>{{ record.summary.task_assets }}</b> | {{ pageText('pages.backupScopeAssets') }}: <b>{{ record.summary.scope_assets || 0 }}</b></div>
              <div style="opacity: 0.65;">{{ pageText('pages.backupHistoryTasks') }}: {{ record.summary.total_tasks || 0 }} | {{ pageText('pages.backupUsers') }}: {{ record.summary.total_users || 0 }}</div>
            </div>
            <span v-else style="opacity: 0.4;">-</span>
          </template>

          <template v-else-if="column.key === 'created_at'">
            <span style="font-size: 12px; white-space: nowrap;">{{ formatDateTime(record.created_at) }}</span>
          </template>

          <template v-else-if="column.key === 'action'">
            <a-space>
              <a-button type="link" size="small" @click="handleDownloadBackup(record.filename)">
                <template #icon><DownloadOutlined /></template>{{ pageText('pages.backupDownload') }}</a-button>

              <a-button type="link" danger size="small" @click="openRestoreModal(record)">
                <template #icon><CloudDownloadOutlined /></template>{{ pageText('pages.backupRestore') }}</a-button>

              <a-popconfirm
                :title="pageText('pages.backupDeleteConfirm')"
                :ok-text="pageText('pages.backupConfirmDelete')"
                :cancel-text="pageText('pages.backupCancel')"
                ok-type="danger"
                @confirm="handleDeleteBackup(record.filename)"
              >
                <a-button type="link" danger size="small" style="opacity: 0.7;">
                  <template #icon><DeleteOutlined /></template>{{ pageText('pages.backupDelete') }}</a-button>
              </a-popconfirm>
            </a-space>
          </template>
        </template>
      </a-table>
    </a-card>

    <!-- 1. 创建备份 Modal -->
    <a-modal
      v-model:open="createBackupModalVisible"
      :title="pageText('pages.backupCreateTitle')"
      :okText="pageText('pages.backupCreateConfirm')"
      :cancelText="pageText('pages.backupCancel')"
      :confirmLoading="backupLoading"
      @ok="handleExecuteCreateBackup"
      width="560px"
    >
      <div style="padding: 10px 0;">
        <a-alert
          type="info"
          show-icon
          style="margin-bottom: 16px; border-radius: 6px;"
          :message="pageText('pages.backupCollections')"
        />

        <a-form layout="vertical" :label-wrap="true">
          <a-form-item :label="pageText('pages.backupContents')">
            <div style="background: var(--arl-bg-light); border: 1px solid var(--arl-border-color); padding: 12px 16px; border-radius: 6px;">
              <a-checkbox v-model:checked="createBackupForm.includeScreenshots">
                <span style="font-weight: 500;">{{ pageText('pages.backupScreenshots') }}</span>
              </a-checkbox>
              <div style="font-size: 12px; color: var(--arl-text-color); opacity: 0.6; margin-top: 6px; margin-left: 24px;">{{ pageText('pages.backupScreenshotsHint') }}</div>
            </div>
          </a-form-item>

          <a-form-item :label="pageText('pages.backupNote')">
            <a-input v-model:value="createBackupForm.note" :placeholder="pageText('pages.backupNotePlaceholder')" :maxLength="80" showCount />
          </a-form-item>
        </a-form>
      </div>
    </a-modal>

    <!-- 2. 上传备份 Modal -->
    <a-modal
      v-model:open="uploadBackupModalVisible"
      :title="pageText('pages.backupUploadTitle')"
      :footer="null"
      width="580px"
    >
      <div style="padding: 10px 0;">
        <a-alert
          type="info"
          show-icon
          style="margin-bottom: 16px; border-radius: 6px;"
          :message="pageText('pages.backupUploadHint')"
        />

        <a-upload-dragger
          name="file"
          :multiple="false"
          :showUploadList="true"
          accept=".tar.gz,.gz"
          :customRequest="handleCustomUploadBackup"
        >
          <p class="ant-upload-drag-icon">
            <InboxOutlined style="font-size: 48px; color: var(--arl-theme-color);" />
          </p>
          <p class="ant-upload-text" style="font-size: 15px; font-weight: 500;">{{ pageText('pages.backupUploadDrop') }}</p>
          <p class="ant-upload-hint" style="font-size: 12px; color: var(--arl-text-color); opacity: 0.6;">{{ pageText('pages.backupUploadFormat') }}</p>
        </a-upload-dragger>
      </div>
    </a-modal>

    <!-- 3. 恢复确认 Modal -->
    <a-modal
      v-model:open="restoreModalVisible"
      :title="pageText('pages.backupRestoreTitle')"
      :okText="pageText('pages.backupRestoreConfirm')"
      :cancelText="pageText('pages.backupCancel')"
      okType="danger"
      :okButtonProps="{ disabled: restoreConfirmInput !== 'RESTORE' }"
      @ok="handleExecuteRestore"
      width="620px"
    >
      <div style="padding: 10px 0;" v-if="selectedRestoreBackup">
        <a-alert
          type="error"
          show-icon
          style="margin-bottom: 16px; border-radius: 6px;"
          :message="pageText('pages.backupDropWarning')"
          :description="pageText('pages.backupDropDescription')"
        />

        <a-descriptions bordered size="small" :column="2" style="margin-bottom: 16px;">
          <a-descriptions-item :label="pageText('pages.backupRestoreArchive')" :span="2">
            <span style="font-family: monospace; font-weight: 600;">{{ selectedRestoreBackup.filename }}</span>
          </a-descriptions-item>
          <a-descriptions-item :label="pageText('pages.backupArchiveSize')">
            {{ formatBytes(selectedRestoreBackup.size) }}
          </a-descriptions-item>
          <a-descriptions-item :label="pageText('pages.backupIncludesScreenshots')">
            {{ selectedRestoreBackup.include_screenshots ? pageText('pages.backupYes') : pageText('pages.backupNo') }}
          </a-descriptions-item>
          <a-descriptions-item :label="pageText('pages.backupCreatedAt')" :span="2">
            {{ formatDateTime(selectedRestoreBackup.created_at) }}
          </a-descriptions-item>
        </a-descriptions>

        <div v-if="backupRunningTasks > 0" style="margin-bottom: 16px; background: rgba(250, 173, 20, 0.08); border: 1px dashed #faad14; padding: 10px 14px; border-radius: 6px;">
          <a-checkbox v-model:checked="restoreForceCheck">
            <span style="color: #d46b08; font-weight: 600;">{{ pageText('pages.backupForceRestore', { count: backupRunningTasks }) }}</span>
          </a-checkbox>
        </div>

        <div style="background: var(--arl-bg-light); border: 1px solid var(--arl-border-color); padding: 12px 14px; border-radius: 6px;">
          <div style="font-size: 13px; font-weight: 500; margin-bottom: 6px;">
            <i18n-t keypath="pages.backupRestoreVerification" tag="span"><template #word><span style="color: #ff4d4f; font-weight: bold; font-family: monospace;">RESTORE</span></template></i18n-t>
          </div>
          <a-input
            v-model:value="restoreConfirmInput"
            :placeholder="pageText('pages.backupEnterRestore')"
            style="font-family: monospace; font-size: 14px;"
          />
        </div>
      </div>
    </a-modal>

    <!-- 4. 备份 / 恢复实时进度流 Modal -->
    <a-modal
      v-model:open="backupProgressModalVisible"
      :closable="progressFinished"
      :maskClosable="false"
      :footer="null"
      width="780px"
    >
      <template #title>
        <div style="display: flex; align-items: center; justify-content: space-between; padding-right: 24px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 18px;">{{ progressAction === 'backup' ? '📦' : '🔄' }}</span>
            <span style="font-weight: 600; font-size: 15px; color: var(--arl-text-color);">
              {{ progressAction === 'backup' ? pageText('pages.backupProgressTitle') : pageText('pages.backupRestoreProgressTitle') }}
            </span>
          </div>
          <div style="display: flex; align-items: center; gap: 12px;">
            <div v-if="!progressFinished" class="update-heartbeat-badge">
              <span class="heartbeat-dot"></span>
              <span>{{ pageText('pages.backupInProgress') }}</span>
            </div>
            <div style="font-family: monospace; font-size: 13px; font-weight: 600; color: var(--arl-text-color); background: var(--arl-bg-subtle); padding: 2px 8px; border-radius: 4px;">
              {{ pageText('pages.backupElapsed', { seconds: progressElapsed }) }}
            </div>
          </div>
        </div>
      </template>

      <!-- 阶段与总进度 -->
      <div style="margin-bottom: 12px; background: var(--arl-bg-light); border: 1px solid var(--arl-border-color); padding: 10px 14px; border-radius: 6px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <a-spin v-if="!progressFinished" size="small" />
            <span style="font-size: 13px; font-weight: 500; color: var(--arl-text-color);">
              {{ progressStage }}
              <span v-if="!progressFinished" style="font-size: 12px; opacity: 0.65; margin-left: 4px;">
                {{ pageText('pages.backupWriting', { seconds: progressElapsed }) }}
              </span>
            </span>
          </div>
          <span style="font-size: 13px; font-weight: 600; color: var(--arl-theme-color);">{{ progressPercent }}%</span>
        </div>
        <a-progress
          :percent="progressPercent"
          :show-info="false"
          :status="progressHasError ? 'exception' : (progressFinished ? 'success' : 'active')"
          stroke-linecap="square"
        />
      </div>

      <!-- 终端控制台 -->
      <div class="arl-mono-terminal" style="height: 320px; overflow-y: auto; box-shadow: inset 0 2px 8px rgba(0,0,0,0.4);" ref="backupTerminalRef">
        <pre style="margin: 0; white-space: pre-wrap; font-family: inherit; color: inherit; background: transparent; border: none; padding: 0; font-size: 12px; line-height: 1.6;">{{ progressLogs.join('\n') }}</pre>
      </div>

      <div v-if="progressFinished" style="margin-top: 16px; text-align: center;">
        <template v-if="!progressHasError">
          <div v-if="progressAction === 'restore'" style="display: flex; justify-content: center; gap: 12px;">
            <a-button type="primary" size="large" @click="reloadPage" style="border-radius: 6px; padding: 0 32px; font-weight: 600;">{{ pageText('pages.backupReload') }}</a-button>
          </div>
          <div v-else style="display: flex; justify-content: center; gap: 12px;">
            <a-button v-if="progressArchiveName" type="primary" size="large" @click="handleDownloadBackup(progressArchiveName)" style="border-radius: 6px;">
              <template #icon><DownloadOutlined /></template>{{ pageText('pages.backupDownloadNow') }}</a-button>
            <a-button size="large" @click="backupProgressModalVisible = false" style="border-radius: 6px;">{{ pageText('pages.backupFinish') }}</a-button>
          </div>
        </template>
        <template v-else>
          <a-button type="default" size="large" @click="backupProgressModalVisible = false" style="border-radius: 6px;">{{ pageText('pages.closeWindow') }}</a-button>
        </template>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';
import { message } from 'ant-design-vue';
import {
  CloudUploadOutlined, CloudDownloadOutlined, DownloadOutlined,
  UploadOutlined, DeleteOutlined, ReloadOutlined, InboxOutlined
} from '@ant-design/icons-vue';
import request from '@/utils/request';
import { useGlobalPageSize } from '@/utils/useGlobalPageSize';

const { t: pageText } = useI18n({ useScope: 'global' });

const globalPageSize = useGlobalPageSize(10);
const handleBackupPageChange = (_page, pageSize) => {
  if (pageSize && pageSize !== globalPageSize.value) {
    globalPageSize.value = pageSize;
  }
};

const reloadPage = () => {
  window.location.reload();
};

const backupList = ref([]);
const backupListLoading = ref(false);
const backupRunningTasks = ref(0);
const backupLoading = ref(false);

const createBackupModalVisible = ref(false);
const createBackupForm = reactive({
  includeScreenshots: true,
  note: ''
});

const uploadBackupModalVisible = ref(false);

const restoreModalVisible = ref(false);
const selectedRestoreBackup = ref(null);
const restoreConfirmInput = ref('');
const restoreForceCheck = ref(false);

const backupProgressModalVisible = ref(false);
const progressAction = ref('backup');
const progressPercent = ref(0);
const progressStage = ref('');
const progressElapsed = ref(0);
const progressLogs = ref([]);
const progressFinished = ref(false);
const progressHasError = ref(false);
const progressArchiveName = ref('');
const backupTerminalRef = ref(null);
let progressPollTimer = null;
let progressElapsedTimer = null;

const formatBytes = (bytes) => {
  if (!bytes || bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return (bytes / Math.pow(k, i)).toFixed(2) + ' ' + sizes[i];
};

const formatDateTime = (iso) => {
  if (!iso) return '-';
  return iso.slice(0, 19).replace('T', ' ');
};

const backupColumns = [
  { get title() { return pageText('pages.backupArchiveName'); }, dataIndex: 'filename', key: 'filename', width: 280 },
  { get title() { return pageText('pages.backupSize'); }, dataIndex: 'size', key: 'size', width: 110 },
  { get title() { return pageText('pages.backupScreenshotColumn'); }, dataIndex: 'include_screenshots', key: 'include_screenshots', width: 130 },
  { get title() { return pageText('pages.backupSummary'); }, key: 'summary' },
  { get title() { return pageText('pages.backupCreatedAt'); }, dataIndex: 'created_at', key: 'created_at', width: 160 },
  { get title() { return pageText('pages.backupActions'); }, key: 'action', width: 200, align: 'center' }
];

const fetchBackupList = async () => {
  backupListLoading.value = true;
  try {
    const res = await request.get('/api/backup/list');
    if (res.code === 200 && res.data) {
      backupList.value = res.data.items || [];
      backupRunningTasks.value = res.data.running_tasks || 0;
    } else {
      message.error(res.message || pageText('pages.backupListFailed'));
    }
  } catch (e) {
    message.error(pageText('pages.backupListNetworkError'));
  } finally {
    backupListLoading.value = false;
  }
};

const openCreateBackupModal = () => {
  createBackupForm.includeScreenshots = true;
  createBackupForm.note = '';
  createBackupModalVisible.value = true;
};

const handleExecuteCreateBackup = async () => {
  backupLoading.value = true;
  try {
    const res = await request.post('/api/backup/create', {
      include_screenshots: createBackupForm.includeScreenshots,
      note: createBackupForm.note.trim()
    });
    if (res.code === 200) {
      createBackupModalVisible.value = false;
      startProgressTracking('backup');
    } else {
      message.error(res.message || pageText('pages.backupStartFailed'));
    }
  } catch (e) {
    message.error(e.response?.data?.message || pageText('pages.backupStartError'));
  } finally {
    backupLoading.value = false;
  }
};

const openUploadBackupModal = () => {
  uploadBackupModalVisible.value = true;
};

const handleCustomUploadBackup = async ({ file, onSuccess, onError, onProgress }) => {
  const formData = new FormData();
  formData.append('file', file);
  try {
    const res = await request.post('/api/backup/upload', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
      onUploadProgress: (progressEvent) => {
        if (progressEvent.total) {
          const percent = Math.round((progressEvent.loaded * 100) / progressEvent.total);
          onProgress({ percent });
        }
      }
    });
    if (res.code === 200) {
      message.success(pageText('pages.backupUploadSuccess'));
      onSuccess(res.data, file);
      uploadBackupModalVisible.value = false;
      fetchBackupList();
    } else {
      message.error(res.message || pageText('pages.backupUploadFailed'));
      onError(new Error(res.message));
    }
  } catch (err) {
    const errText = err.response?.data?.message || pageText('pages.backupUploadError');
    message.error(errText);
    onError(err);
  }
};

const openRestoreModal = (record) => {
  selectedRestoreBackup.value = record;
  restoreConfirmInput.value = '';
  restoreForceCheck.value = false;
  restoreModalVisible.value = true;
};

const handleExecuteRestore = async () => {
  if (!selectedRestoreBackup.value) return;
  try {
    const res = await request.post('/api/backup/restore', {
      filename: selectedRestoreBackup.value.filename,
      force: restoreForceCheck.value || backupRunningTasks.value === 0
    });
    if (res.code === 200) {
      restoreModalVisible.value = false;
      startProgressTracking('restore', selectedRestoreBackup.value.filename);
    } else {
      message.error(res.message || pageText('pages.backupRestoreFailed'));
    }
  } catch (e) {
    message.error(e.response?.data?.message || pageText('pages.backupRestoreError'));
  }
};

const handleDownloadBackup = async (filename) => {
  try {
    const res = await request.post('/api/backup/download_ticket', { filename });
    if (res.code !== 200 || !res.data?.ticket) throw new Error(res.message);
    const a = document.createElement('a');
    a.href = `/api/backup/download/${encodeURIComponent(filename)}?ticket=${encodeURIComponent(res.data.ticket)}`;
    a.download = filename;
    a.rel = 'noreferrer';
    document.body.appendChild(a);
    a.click();
    a.remove();
  } catch (error) {
    message.error(error.message);
  }
};

const handleDeleteBackup = async (filename) => {
  try {
    const res = await request.delete(`/api/backup/delete/${encodeURIComponent(filename)}`);
    if (res.code === 200) {
      message.success(pageText('pages.backupDeleted'));
      fetchBackupList();
    } else {
      message.error(res.message || pageText('pages.backupDeleteFailed'));
    }
  } catch (e) {
    message.error(pageText('pages.backupDeleteError'));
  }
};

const scrollBackupTerminal = () => {
  nextTick(() => {
    if (backupTerminalRef.value) {
      backupTerminalRef.value.scrollTop = backupTerminalRef.value.scrollHeight;
    }
  });
};

const stopProgressTracking = () => {
  if (progressPollTimer) {
    clearInterval(progressPollTimer);
    progressPollTimer = null;
  }
  if (progressElapsedTimer) {
    clearInterval(progressElapsedTimer);
    progressElapsedTimer = null;
  }
};

const checkAndResumeBackupProgress = async () => {
  try {
    const res = await request.get('/api/backup/status');
    if (res.code === 200 && res.data) {
      const d = res.data;
      if (['backing_up', 'restoring'].includes(d.status)) {
        if (typeof d.percent === 'number') progressPercent.value = d.percent;
        if (d.stage) progressStage.value = d.stage;
        if (Array.isArray(d.logs)) progressLogs.value = d.logs;
        if (d.archive_name) progressArchiveName.value = d.archive_name;
        if (d.elapsed) progressElapsed.value = d.elapsed;
        startProgressTracking(d.action, d.archive_name, true);
      }
    }
  } catch (e) {
    // 页面初始化静默容错
  }
};

const startProgressTracking = (action, archiveName = '', isResume = false) => {
  stopProgressTracking();
  progressAction.value = action || 'backup';
  if (!isResume) {
    progressPercent.value = 5;
    progressStage.value = action === 'backup' ? pageText('pages.backupPreparing') : pageText('pages.backupRestorePreparing');
    progressElapsed.value = 0;
    progressLogs.value = [pageText('pages.backupConnecting')];
  }
  progressFinished.value = false;
  progressHasError.value = false;
  if (archiveName) progressArchiveName.value = archiveName;
  backupProgressModalVisible.value = true;

  const initElapsed = progressElapsed.value || 0;
  const startTime = Date.now() - initElapsed * 1000;
  let microStepTick = 0;

  progressElapsedTimer = setInterval(() => {
    progressElapsed.value = Math.floor((Date.now() - startTime) / 1000);
    microStepTick += 1;
    if (microStepTick % 3 === 0 && !progressFinished.value) {
      if (progressPercent.value >= 20 && progressPercent.value < 54) {
        progressPercent.value = Math.min(54, progressPercent.value + 1);
      } else if (progressPercent.value >= 58 && progressPercent.value < 74) {
        progressPercent.value = Math.min(74, progressPercent.value + 1);
      } else if (progressPercent.value >= 85 && progressPercent.value < 96) {
        progressPercent.value = Math.min(96, progressPercent.value + 1);
      }
    }
  }, 1000);

  progressPollTimer = setInterval(async () => {
    try {
      const res = await request.get('/api/backup/status');
      if (res.code === 200 && res.data) {
        const d = res.data;
        if (d.status === 'idle' && !progressFinished.value) {
          return;
        }

        if (d.stage) progressStage.value = d.stage;
        if (typeof d.percent === 'number' && d.percent > progressPercent.value) {
          progressPercent.value = d.percent;
        }
        if (Array.isArray(d.logs) && d.logs.length > 0) {
          progressLogs.value = d.logs;
        }
        if (d.archive_name) progressArchiveName.value = d.archive_name;
        if (typeof d.elapsed === 'number' && d.elapsed > progressElapsed.value) {
          progressElapsed.value = d.elapsed;
        }
        scrollBackupTerminal();

        if (d.status === 'success') {
          progressFinished.value = true;
          progressHasError.value = false;
          progressPercent.value = 100;
          progressStage.value = (d.action || action) === 'backup' ? pageText('pages.backupCompleted') : pageText('pages.backupRestoreCompleted');
          stopProgressTracking();
          fetchBackupList();
        } else if (d.status === 'error') {
          progressFinished.value = true;
          progressHasError.value = true;
          progressStage.value = pageText('pages.backupExecutionFailed', { error: d.error || pageText('pages.backupUnknownError') });
          stopProgressTracking();
          fetchBackupList();
        }
      }
    } catch (err) {
      // 容错重试
    }
  }, 1000);
};

const closeModals = () => {
  backupProgressModalVisible.value = false;
  createBackupModalVisible.value = false;
  uploadBackupModalVisible.value = false;
  restoreModalVisible.value = false;
  stopProgressTracking();
};

onMounted(() => {
  fetchBackupList();
  checkAndResumeBackupProgress();
});

onUnmounted(() => {
  stopProgressTracking();
});

defineExpose({
  fetchBackupList,
  checkAndResumeBackupProgress,
  stopProgressTracking,
  closeModals
});
</script>

<style scoped>
.update-heartbeat-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: rgba(82, 196, 26, 0.12);
  color: #52c41a;
  border: 1px solid rgba(82, 196, 26, 0.3);
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 500;
}

.heartbeat-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background-color: #52c41a;
  animation: pulse-dot 1.5s infinite ease-in-out;
}

@keyframes pulse-dot {
  0% { transform: scale(0.8); opacity: 0.5; }
  50% { transform: scale(1.3); opacity: 1; }
  100% { transform: scale(0.8); opacity: 0.5; }
}
</style>
