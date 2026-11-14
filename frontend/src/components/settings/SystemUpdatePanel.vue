<template>
  <div class="tab-content" style="padding: 20px;">
    <a-card data-setting-anchor="update" :title="pageText('pages.systemUpdateManagement')" :bordered="false" class="page-dialog-content">
      <template #extra>
        <a-button size="small" :loading="checkingVersion" @click="checkVersion(true)">
          <template #icon><ReloadOutlined /></template>
          {{ pageText('pages.checkForUpdates') }}
        </a-button>
      </template>
      <a-descriptions bordered :column="1">
        <a-descriptions-item :label="pageText('pages.currentVersionLabel2')">
          <a-tag color="blue">{{ formatSystemVersion(localVersion) }}</a-tag>
        </a-descriptions-item>
        <a-descriptions-item :label="pageText('pages.latestAvailableVersion')">
          <a-tag :color="hasNewVersion ? 'red' : (isOffline ? 'orange' : 'green')">{{ formatSystemVersion(remoteVersion) }}</a-tag>
          <span v-if="hasNewVersion" style="margin-left: 10px; color: #f5222d; font-weight: bold;">
            {{ pageText('pages.newVersionAvailableAnUpdateIsRecommended') }}
          </span>
          <span v-else-if="isOffline" style="margin-left: 10px; color: #faad14;">
            {{ pageText('pages.unableToReachGithubCheckNetwork') }}
          </span>
          <span v-else-if="remoteVersion" style="margin-left: 10px; color: #52c41a;">
            {{ pageText('pages.alreadyUpToDate') }}
          </span>
        </a-descriptions-item>
        <a-descriptions-item :label="pageText('pages.releaseNotes')">
          <div v-if="checkingVersion && !renderedReleaseNotes" class="release-notes-placeholder">
            {{ pageText('pages.loadingLabel2') }}
          </div>
          <div
            v-else-if="renderedReleaseNotes"
            class="markdown-release-notes"
            v-html="renderedReleaseNotes"
          ></div>
          <div v-else class="release-notes-empty">
            <span>{{ hasNewVersion ? pageText('pages.releaseNotesLoadFailedHint') : pageText('pages.noLocalReleaseNotesFound') }}</span>
            <div class="release-notes-empty-actions">
              <a-button size="small" :loading="checkingVersion" @click="checkVersion(true)">
                <template #icon><ReloadOutlined /></template>
                {{ pageText('pages.retryFetchReleaseNotes') }}
              </a-button>
              <a :href="releaseHtmlUrl" target="_blank" rel="noopener noreferrer">
                {{ pageText('pages.viewOnGithubReleases') }}
              </a>
            </div>
          </div>
        </a-descriptions-item>
      </a-descriptions>

      <div style="margin-top: 20px; text-align: center;">
        <a-popconfirm :title="pageText('pages.thisWillDownloadTheLatestImagesAndRestartSystem')" @confirm="handleStartUpdateClick">
          <a-button type="primary" size="large" danger :loading="updateButtonLoading" :disabled="!hasNewVersion && !forceUpdateMode">
            {{ pageText('pages.updateSystem') }}
          </a-button>
        </a-popconfirm>
        <div style="margin-top: 10px;">
          <a-checkbox v-model:checked="forceUpdateMode">{{ pageText('pages.forceShowUpdateButton') }}</a-checkbox>
        </div>
      </div>

      <!-- 开源仓库入口：纯文本外链，不嵌外部 badge/iframe，保证离线内网环境无破图 -->
      <a-divider style="margin: 20px 0 12px;" />
      <div style="text-align: center; font-size: 12px; color: var(--arl-text-color); opacity: 0.55;">
        <GithubOutlined style="margin-right: 4px;" />
        <span>{{ pageText('pages.sourceRepository') }}</span>
        <a href="https://github.com/owl234/ARL-Next" target="_blank" rel="noopener noreferrer">github.com/owl234/ARL-Next</a>
        <a-divider type="vertical" />
        <a href="https://github.com/owl234/ARL-Next/releases" target="_blank" rel="noopener noreferrer">{{ pageText('pages.releaseHistory') }}</a>
      </div>
    </a-card>

    <!-- 系统更新日志 Modal -->
    <a-modal
      v-model:open="updateModalVisible"
      :closable="updateFinished"
      :maskClosable="false"
      :footer="null"
      width="840px"
    >
      <template #title>
        <div style="display: flex; align-items: center; justify-content: space-between; padding-right: 24px;">
          <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 18px;">🚀</span>
            <span class="page-sidebar-heading">{{ pageText('pages.arlNextOnlineSystemUpdate') }}</span>
          </div>
          <div style="display: flex; align-items: center; gap: 12px;">
            <div v-if="!updateFinished" class="update-heartbeat-badge">
              <span class="heartbeat-dot"></span>
              <span>{{ pageText('pages.runningLabel2') }}</span>
            </div>
            <div style="font-family: monospace; font-size: 13px; font-weight: 600; color: var(--arl-text-color); background: var(--arl-bg-subtle); padding: 2px 8px; border-radius: 4px;">
              {{ pageText('pages.elapsed') }} {{ formattedElapsedTime }}
            </div>
          </div>
        </div>
      </template>

      <!-- 阶段与总进度 -->
      <div style="margin-bottom: 12px; background: var(--arl-bg-light); border: 1px solid var(--arl-border-color); padding: 10px 14px; border-radius: 6px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
          <span style="font-size: 13px; font-weight: 500; color: var(--arl-text-color);">{{ currentStageTitle }}</span>
          <span style="font-size: 13px; font-weight: 600; color: var(--arl-theme-color);">{{ updateProgress }}%</span>
        </div>
        <a-progress :percent="updateProgress" :show-info="false" :status="updateHasError ? 'exception' : (updateFinished ? 'success' : 'active')" stroke-linecap="square" />
      </div>

      <!-- 实时镜像分层动态传输芯片 -->
      <div v-if="Object.keys(activeLayers).length > 0" class="update-layer-box">
        <div class="update-layer-header">
          <span style="font-size: 14px;">⚡</span>
          <span class="page-small-heading">{{ pageText('pages.transferringImageLayers') }}{{ Object.keys(activeLayers).length }} {{ pageText('pages.activeLayers') }}</span>
        </div>
        <div class="update-layer-list">
          <div v-for="(statusText, layerId) in activeLayers" :key="layerId" class="layer-chip">
            <span class="layer-id">{{ String(layerId).slice(0, 12) }}</span>
            <span class="layer-status">{{ statusText }}</span>
          </div>
        </div>
      </div>

      <!-- 终端控制台 -->
      <div style="background-color: #141414; border: 1px solid #333; color: #00ff66; padding: 14px; border-radius: 6px; font-family: 'Consolas', 'Monaco', 'Courier New', monospace; height: 380px; overflow-y: auto; box-shadow: inset 0 2px 8px rgba(0,0,0,0.4);" ref="terminalRef">
        <pre style="margin: 0; white-space: pre-wrap; font-family: inherit; color: inherit; background: transparent; border: none; padding: 0; font-size: 12px; line-height: 1.6;">{{ updateLogs }}</pre>
      </div>

      <div v-if="updateFinished" style="margin-top: 16px; text-align: center;">
        <a-button v-if="!updateHasError" type="primary" size="large" @click="reloadPage" class="page-primary-action">{{ pageText('pages.updateCompletedReloadThePage') }}</a-button>
        <a-button v-else type="default" size="large" @click="updateModalVisible = false" class="page-rounded">{{ pageText('pages.closeWindow') }}</a-button>
      </div>
    </a-modal>
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted, onActivated, onDeactivated, onUnmounted, nextTick } from 'vue';
import { useI18n } from 'vue-i18n';
import { message, Modal } from 'ant-design-vue';
import { GithubOutlined, ReloadOutlined } from '@ant-design/icons-vue';
import request from '@/utils/request';

const { t: pageText, locale: pageLocale } = useI18n({ useScope: 'global' });

const reloadPage = () => {
  window.location.reload();
};

const formatSystemVersion = (version) => {
  if (!version) return pageText('pages.loadingLabel2');
  return version === '未知版本' ? pageText('pages.unknownVersion') : version;
};

const localVersion = ref('');
const remoteVersion = ref('');
const releaseNotes = ref('');
const releaseHtmlUrl = ref('https://github.com/owl234/ARL-Next/releases');
const hasNewVersion = ref(false);
const isOffline = ref(false);
const checkingVersion = ref(false);
const checkVersionSeq = ref(0);
const forceUpdateMode = ref(false);

const updateModalVisible = ref(false);
const updateLogs = ref('');
const updateProgress = ref(0);
const updatePollInterval = ref(null);
const logByteOffset = ref(0);
const updateFinished = ref(false);
const terminalRef = ref(null);
const updateButtonLoading = ref(false);
const updateHasError = ref(false);
const updateOfflineNotices = ref('');

const updateElapsedSeconds = ref(0);
const updateTimer = ref(null);
const activeLayers = ref({});
const currentStageKey = ref('pages.preparingTheUpdateEnvironment');
const currentStageTitle = computed(() => pageText(currentStageKey.value));

const formattedElapsedTime = computed(() => {
  const mins = Math.floor(updateElapsedSeconds.value / 60);
  const secs = updateElapsedSeconds.value % 60;
  return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
});

const renderedReleaseNotes = computed(() => {
  const source = (releaseNotes.value || '').replace(/\u0000/g, '').trim();
  if (!source) return '';

  const tokens = [];
  const stash = (fragment) => {
    const idx = tokens.length;
    tokens.push(fragment);
    return `\u0000TOKEN_${idx}\u0000`;
  };

  let html = source
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');

  html = html.replace(/`([^`\n]+)`/g, (_, code) => stash(`<code>${code}</code>`));

  html = html.replace(/\[([^\]]+)\]\(((?:https?:\/\/|\.?\/)[^)\s]+)\)/g, (_, label, rawHref) => {
    const resolved = rawHref.startsWith('http')
      ? rawHref
      : `https://github.com/owl234/ARL-Next/blob/main/${rawHref.replace(/^\.\//, '')}`;
    return stash(`<a href="${resolved}" target="_blank" rel="noopener noreferrer">${label}</a>`);
  });

  html = html.replace(/https?:\/\/[^\s<>"')\]]+?(?=[.,;:!?]?(?:\s|$))/g, (url) =>
    stash(`<a href="${url}" target="_blank" rel="noopener noreferrer">${url}</a>`)
  );

  html = html.replace(/^\s*(?:-{3,}|\*{3,}|_{3,})\s*$/gm, '<hr/>');
  html = html.replace(/^### (.*$)/gim, '<h4>$1</h4>');
  html = html.replace(/^## (.*$)/gim, '<h3>$1</h3>');
  html = html.replace(/^# (.*$)/gim, '<h2>$1</h2>');
  html = html.replace(/^&gt;\s?(.*$)/gim, '<blockquote>$1</blockquote>');

  html = html.replace(/\*\*([^*\n]+)\*\*/g, '<strong>$1</strong>');

  html = html.replace(/^\s*[-*]\s+(.*$)/gim, '<li class="md-ul">$1</li>');
  html = html.replace(/^\s*\d+\.\s+(.*$)/gim, '<li class="md-ol">$1</li>');

  html = html.replace(/\r?\n\r?\n/g, '<div class="md-gap"></div>');
  html = html.replace(/\r?\n/g, '<br/>');
  html = html
    .replace(/(<\/h[234]>|<hr\/>|<\/blockquote>)\s*<br\/>/g, '$1')
    .replace(/<br\/>\s*(<h[234]>|<hr\/>|<blockquote>|<li\b)/g, '$1')
    .replace(/<\/li>\s*<br\/>/g, '</li>');

  return html.replace(/\u0000TOKEN_(\d+)\u0000/g, (_, idx) => tokens[Number(idx)] ?? '');
});

const checkVersion = async (force = false) => {
  if (force && checkingVersion.value) return;
  const seq = ++checkVersionSeq.value;
  checkingVersion.value = true;
  try {
    const params = { lang: pageLocale.value || 'zh-CN' };
    if (force) params.refresh = 1;
    const res = await request.get('/api/system_config/check_update', { params });
    if (seq !== checkVersionSeq.value) return;
    if (res.code === 200 && res.data) {
      localVersion.value = res.data.local_version || '未知版本';
      remoteVersion.value = res.data.remote_version || localVersion.value;
      hasNewVersion.value = Boolean(res.data.has_new_version);
      isOffline.value = Boolean(res.data.is_offline);
      releaseNotes.value = res.data.release_notes || '';
      releaseHtmlUrl.value = res.data.html_url || 'https://github.com/owl234/ARL-Next/releases';
    }
  } catch (e) {
    if (seq !== checkVersionSeq.value) return;
    console.error('检查版本更新失败', e);
    try {
      const localRes = await request.get('/api/system_config/local_version');
      if (seq === checkVersionSeq.value && localRes.code === 200) {
        localVersion.value = localRes.data.version;
      }
    } catch (_) {}
  } finally {
    if (seq === checkVersionSeq.value) {
      checkingVersion.value = false;
    }
  }
};

const handleStartUpdateClick = async () => {
  try {
    const res = await request.get('/api/system_config/running_task_count');
    const runningCount = res.code === 200 && res.data ? (res.data.running_count || 0) : 0;
    if (runningCount > 0) {
      Modal.confirm({
        title: pageText('pages.scanningTasksAreRunning'),
        content: pageText('pages.thereAreCountRunningScanningTasksUpdatingTheSystem', { count: runningCount }),
        okText: pageText('pages.interruptTasksAndUpdate'),
        okType: 'danger',
        cancelText: pageText('pages.cancelAndWaitForTasksToFinish'),
        onOk: () => {
          startUpdate();
        }
      });
      return;
    }
  } catch (e) {
    console.warn('获取运行中任务数量失败，跳过前置阻断', e);
  }
  startUpdate();
};

const stopUpdateTimers = () => {
  if (updatePollInterval.value) {
    clearInterval(updatePollInterval.value);
    updatePollInterval.value = null;
  }
  if (updateTimer.value) {
    clearInterval(updateTimer.value);
    updateTimer.value = null;
  }
  activeLayers.value = {};
};

const finishUpdate = (stageKey, { progress = null, hasError = false } = {}) => {
  stopUpdateTimers();
  currentStageKey.value = stageKey;
  if (progress !== null) updateProgress.value = progress;
  updateFinished.value = true;
  updateHasError.value = hasError;
  updateOfflineNotices.value = '';
};

const scrollToBottom = () => {
  nextTick(() => {
    if (terminalRef.value) {
      terminalRef.value.scrollTop = terminalRef.value.scrollHeight;
    }
  });
};

const startUpdate = async () => {
  if (updateButtonLoading.value) return;
  updateButtonLoading.value = true;
  try {
    const res = await request.post('/api/system_config/request_update_token');
    if (res.code !== 200) {
      message.error(res.message || pageText('pages.failedToObtainUpdateToken'));
      updateButtonLoading.value = false;
      return;
    }
    const token = res.data.token;

    updateModalVisible.value = true;
    updateHasError.value = false;
    updateOfflineNotices.value = '';
    updateLogs.value = pageText('pages.startingTheUpdateService');
    updateProgress.value = 10;
    updateFinished.value = false;
    updateButtonLoading.value = false;
    logByteOffset.value = 0;
    activeLayers.value = {};
    updateElapsedSeconds.value = 0;
    currentStageKey.value = 'pages.preparingTheUpdateEnvironment';

    stopUpdateTimers();
    updateTimer.value = setInterval(() => {
      updateElapsedSeconds.value++;
    }, 1000);

    const triggerUrl = '/update_stream/trigger';
    let logToken = '';
    try {
      const triggerRes = await fetch(triggerUrl, { method: 'POST', headers: { 'X-Update-Token': token } });
      if (!triggerRes.ok) {
        updateLogs.value += pageText('pages.errorUpdateRequestFailedTheServiceReturnedAnUnexpected');
        finishUpdate('pages.failedToStartUpdate', { hasError: true });
        return;
      }
      const triggerData = await triggerRes.json();
      logToken = triggerData.log_token;
      if (!logToken) throw new Error('Missing updater log token');
    } catch (e) {
      updateLogs.value += pageText('pages.errorCannotConnectToTheUpdateServiceCheckThe');
      finishUpdate('pages.cannotConnectToUpdateService', { hasError: true });
      return;
    }

    if (updatePollInterval.value) {
      clearInterval(updatePollInterval.value);
    }

    updatePollInterval.value = setInterval(async () => {
      try {
        const pollUrl = `/update_stream/log?offset=${logByteOffset.value}`;
        const logRes = await fetch(pollUrl, { headers: { 'X-Update-Read-Token': logToken } });
        if (!logRes.ok) {
          if (logRes.status === 403) {
            finishUpdate('pages.failedToObtainUpdateToken', { hasError: true });
            return;
          }
          if (logRes.status === 401) {
            finishUpdate('pages.systemUpdatedBasicAuthProtectionIsActive', { progress: 100 });
            updateLogs.value += pageText('pages.doneSystemUpdatedBasicAuthProtectionIsActiveRefresh');
            scrollToBottom();
            message.success(pageText('pages.systemUpdatedRefreshThePage'), 8);
            return;
          }
          if (updateOfflineNotices.value !== 'network') {
            updateOfflineNotices.value = 'network';
            updateLogs.value += pageText('pages.gatewayRestartingOrServiceTemporarilyUnavailableWaitingForThe');
            scrollToBottom();
          }
          return;
        }

        const contentType = logRes.headers.get("content-type") || "";
        if (contentType.includes("application/json")) {
          const data = await logRes.json();
          logByteOffset.value = data.offset !== undefined ? data.offset : logByteOffset.value;
          if (data.chunk) {
            updateLogs.value += data.chunk;
            scrollToBottom();
          }

          if (data.progress && typeof data.progress === 'object') {
            activeLayers.value = data.progress;
          } else {
            activeLayers.value = {};
          }

          if (!updateFinished.value) {
            if (updateLogs.value.includes('正在拉取核心镜像')) {
              currentStageKey.value = 'pages.stage13PullingTheCoreImageToExtract';
              updateProgress.value = Math.max(updateProgress.value, 20);
            }
            if (updateLogs.value.includes('核心镜像拉取完成') || updateLogs.value.includes('基础架构同步完毕')) {
              currentStageKey.value = 'pages.stage13InfrastructureExtractedPreparingServiceDeployment';
              updateProgress.value = Math.max(updateProgress.value, 35);
            }
            if (updateLogs.value.includes('正在为当前运行版本创建稳定备份快照')) {
              currentStageKey.value = 'pages.stage23CreatingAStableSnapshotOfThe';
              updateProgress.value = Math.max(updateProgress.value, 45);
            }
            if (updateLogs.value.includes('正在从阿里云镜像库极速拉取最新构建')) {
              currentStageKey.value = 'pages.stage23PullingTheLatestImagesFromThe';
              updateProgress.value = Math.max(updateProgress.value, 60);
            }
            if (updateLogs.value.includes('所有微服务镜像拉取完成') || updateLogs.value.includes('正在启动生产多服务容器组')) {
              currentStageKey.value = 'pages.stage33StartingServiceContainersAndCheckingTheir';
              updateProgress.value = Math.max(updateProgress.value, 80);
            }
            if (updateLogs.value.includes('后端服务已完全就绪')) {
              currentStageKey.value = 'pages.stage33BackendServicesAndDatabaseAreReady';
              updateProgress.value = Math.max(updateProgress.value, 95);
            }
          }

          if (data.done) {
            finishUpdate('pages.systemUpdateAndDeploymentCompleted', { progress: 100 });
            message.success(pageText('pages.systemUpdatedSelectReloadBelowToRefreshThePage'), 5);
          } else if (data.error) {
            finishUpdate('pages.systemUpdateFailed', { hasError: true });
            message.error(pageText('pages.systemUpdateFailedCheckTheLogs'), 8);
          }
        } else {
          const logText = await logRes.text();
          updateLogs.value = logText;
          scrollToBottom();
          if (logText.includes('[DONE]')) {
            finishUpdate('pages.systemUpdated', { progress: 100 });
            message.success(pageText('pages.systemUpdated'), 5);
          } else if (logText.includes('[ERROR]')) {
            finishUpdate('pages.systemUpdateFailed', { hasError: true });
            message.error(pageText('pages.systemUpdateFailedLabel2'), 8);
          }
        }
      } catch (err) {
        if (updateOfflineNotices.value !== 'container') {
          updateOfflineNotices.value = 'container';
          updateLogs.value += pageText('pages.networkDisconnectedWaitingForContainersToRecover');
          scrollToBottom();
        }
      }
    }, 1200);

  } catch (e) {
    message.error(pageText('pages.failedToStartUpdateLabel2'));
    console.error(e);
    updateButtonLoading.value = false;
    stopUpdateTimers();
  }
};

const closeModals = () => {
  updateModalVisible.value = false;
  stopUpdateTimers();
};

// 面板可能延迟挂载于已激活的 KeepAlive 页面 Tab 内，用失活标记区分首次激活与切页重返。
let hasDeactivated = false;
onMounted(() => {
  checkVersion();
});

onDeactivated(() => {
  hasDeactivated = true;
});

onActivated(() => {
  if (!hasDeactivated) return;
  hasDeactivated = false;
  checkVersion();
});

watch(pageLocale, () => {
  checkVersion();
});

onUnmounted(() => {
  stopUpdateTimers();
});

defineExpose({
  checkVersion,
  stopUpdateTimers,
  closeModals
});
</script>

<style scoped>
.page-dialog-content { max-width: 800px; }
.page-dialog-content :deep(.ant-descriptions-item-label) { width: 150px; min-width: 130px; }
.page-sidebar-heading { font-weight: 600; font-size: 15px; color: var(--arl-text-color); }
.page-small-heading { font-weight: 600; font-size: 12px; }
.page-primary-action { border-radius: 6px; padding: 0 32px; font-weight: 600; }
.page-rounded { border-radius: 6px; }

.markdown-release-notes {
  max-height: 380px;
  overflow-y: auto;
  line-height: 1.6;
  font-size: 13px;
  background: var(--arl-bg-subtle);
  padding: 12px 16px;
  border-radius: 6px;
  border: 1px solid var(--arl-border-color);
  word-break: break-word;
}

.markdown-release-notes :deep(h2) {
  margin: 14px 0 8px 0;
  font-weight: 700;
  font-size: 15px;
  color: var(--arl-text-color);
}

.markdown-release-notes :deep(h3) {
  margin: 12px 0 8px 0;
  font-weight: 700;
  font-size: 14px;
  color: var(--arl-text-color);
}

.markdown-release-notes :deep(h4) {
  margin: 10px 0 6px 0;
  font-weight: 600;
  font-size: 13px;
  color: var(--arl-text-color);
}

.markdown-release-notes :deep(h2:first-child),
.markdown-release-notes :deep(h3:first-child),
.markdown-release-notes :deep(h4:first-child) {
  margin-top: 0;
}

.markdown-release-notes :deep(strong) {
  font-weight: 600;
}

.markdown-release-notes :deep(code) {
  background: var(--arl-bg-hover);
  padding: 2px 6px;
  border-radius: 4px;
  font-family: var(--arl-font-mono, monospace);
  font-size: 12px;
}

.markdown-release-notes :deep(a) {
  color: var(--arl-theme-color);
  text-decoration: underline;
}

.markdown-release-notes :deep(hr) {
  border: none;
  border-top: 1px solid var(--arl-border-color);
  margin: 12px 0;
}

.markdown-release-notes :deep(blockquote) {
  margin: 8px 0;
  padding: 4px 10px;
  border-left: 3px solid var(--arl-border-color);
  color: var(--arl-text-secondary);
}

.markdown-release-notes :deep(li.md-ul) {
  margin-left: 18px;
  line-height: 1.8;
  list-style-type: disc;
}

.markdown-release-notes :deep(li.md-ol) {
  margin-left: 18px;
  line-height: 1.8;
  list-style-type: decimal;
}

.markdown-release-notes :deep(.md-gap) {
  height: 6px;
}

.release-notes-placeholder,
.release-notes-empty {
  padding: 12px 16px;
  border-radius: 6px;
  background: var(--arl-bg-subtle);
  border: 1px dashed var(--arl-border-color);
  color: var(--arl-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}

.release-notes-empty-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 8px;
  flex-wrap: wrap;
}

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

.update-layer-box {
  margin-bottom: 12px;
  background: var(--arl-theme-soft-bg);
  border: 1px dashed var(--arl-theme-soft-border);
  border-radius: 6px;
  padding: 8px 12px;
}

.update-layer-header {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--arl-theme-color);
  margin-bottom: 6px;
}

.update-layer-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  max-height: 80px;
  overflow-y: auto;
}

.layer-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  background: var(--arl-bg-white);
  border: 1px solid var(--arl-border-color);
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-family: monospace;
}

.layer-id {
  font-weight: 600;
  color: var(--arl-theme-color);
}

.layer-status {
  color: var(--arl-text-color);
  opacity: 0.85;
}
</style>
