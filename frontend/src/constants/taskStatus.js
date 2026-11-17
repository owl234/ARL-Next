import { i18n } from '../i18n/index.js';

const taskText = (key, params) => i18n.global.t(key, params);

/**
 * 任务状态术语唯一事实源（全项目唯一口径）
 *
 * 基准词表（新增状态须先在此登记再使用）：
 *   running 进行中 / waiting 排队中 / done 已完成 / stop 已停止 / error 异常失败
 *
 * 注意：
 *   - 状态文案字典（TASK_STATUS_LABEL）与插件名/阶段字典（PLUGIN_NAME_MAP）必须分表维护；
 *   - 后端插件名/阶段标识严禁直接当作任务状态展示，须经 formatTaskStatus 标注为「进行中 · <阶段名>」。
 */

/** 任务状态 → 展示文案 */
export const TASK_STATUS_LABEL = {
  get running() { return taskText('tasks.statusRunning'); },
  get waiting() { return taskText('tasks.statusWaiting'); },
  get done() { return taskText('tasks.statusDone'); },
  get stop() { return taskText('tasks.statusStop'); },
  get error() { return taskText('tasks.statusError'); }
};

/** 任务状态 → Ant Design Tag 配色 */
export const TASK_STATUS_COLOR = {
  running: 'processing',
  waiting: 'warning',
  done: 'success',
  stop: 'default',
  error: 'error'
};

/** 插件名/阶段标识 → 展示名称（与状态字典分表，严禁混用） */
export const PLUGIN_NAME_MAP = {
  get domain_brute() { return taskText('tasks.stageDomainBrute'); },
  get dns_query_plugin() { return taskText('tasks.stageDnsQueryPlugin'); },
  get arl_search() { return taskText('tasks.stageArlSearch'); },
  get alt_dns() { return taskText('tasks.stageAltDns'); },
  get recursive_domain_brute() { return taskText('tasks.stageRecursiveDomainBrute'); },
  get port_scan() { return taskText('tasks.stagePortScan'); },
  get ssl_cert() { return taskText('tasks.stageSslCert'); },
  get service_detection() { return taskText('tasks.stageServiceDetection'); },
  get os_detection() { return taskText('tasks.stageOsDetection'); },
  get find_site() { return taskText('tasks.stageFindSite'); },
  get site_identify() { return taskText('tasks.stageSiteIdentify'); },
  get search_engines() { return taskText('tasks.stageSearchEngines'); },
  get site_spider() { return taskText('tasks.stageSiteSpider'); },
  get file_leak() { return taskText('tasks.stageFileLeak'); },
  get find_vhost() { return taskText('tasks.stageFindVhost'); },
  get findvhost() { return taskText('tasks.stageFindvhost'); },
  get npoc_service_detection() { return taskText('tasks.stageNpocServiceDetection'); },
  get poc_run() { return taskText('tasks.stagePocRun'); },
  get nuclei_scan() { return taskText('tasks.stageNucleiScan'); },
  get weak_brute() { return taskText('tasks.stageWeakBrute'); },
  get wih_domain_update() { return taskText('tasks.stageWihDomainUpdate'); },
  get web_info_hunter() { return taskText('tasks.stageWebInfoHunter'); }
};

/** GitHub 扫描阶段字典（独立于任务状态字典） */
export const GITHUB_STAGE_MAP = {
  get search() { return taskText('tasks.stageGithubSearch'); },
  get 'fetch content'() { return taskText('tasks.stageGithubFetchContent'); }
};

/**
 * 是否为已知的任务状态值。
 * @param {string} status 后端返回的状态值
 * @returns {boolean}
 */
export const isKnownTaskStatus = (status) => !!status && status in TASK_STATUS_LABEL;

/**
 * 是否为 GitHub 扫描阶段状态（如 search / fetch content / fetch content-32）。
 * @param {string} status 后端返回的状态值
 * @returns {boolean}
 */
export const isGithubStageStatus = (status) => {
  if (!status) return false;
  return status in GITHUB_STAGE_MAP || String(status).startsWith('fetch content-');
};

/**
 * 是否为阶段状态（后端返回插件/阶段标识，表示任务正在该阶段执行）。
 * @param {string} status 后端返回的状态值
 * @returns {boolean}
 */
export const isStageStatus = (status) => !!status && !isKnownTaskStatus(status);

/**
 * 状态值 → 展示文案。阶段状态显式标注为「进行中 · <阶段名>」，
 * 避免用户把插件名误读为任务状态。
 * @param {string} status 后端返回的状态值
 * @returns {string} 展示文案
 */
export const formatTaskStatus = (status) => {
  if (TASK_STATUS_LABEL[status]) return TASK_STATUS_LABEL[status];
  if (status && GITHUB_STAGE_MAP[status]) {
    return taskText('tasks.statusWithStage', { stage: GITHUB_STAGE_MAP[status] });
  }
  if (status && String(status).startsWith('fetch content-')) {
    const count = String(status).slice('fetch content-'.length).trim();
    const stage = count ? `${GITHUB_STAGE_MAP['fetch content']} (${count})` : GITHUB_STAGE_MAP['fetch content'];
    return taskText('tasks.statusWithStage', { stage });
  }
  const stageName = PLUGIN_NAME_MAP[status] || status;
  return stageName ? taskText('tasks.statusWithStage', { stage: stageName }) : TASK_STATUS_LABEL.running;
};

/**
 * 状态值 → Tag 配色，未知状态回落 default。
 * @param {string} status 后端返回的状态值
 * @returns {string}
 */
export const formatTaskStatusColor = (status) => TASK_STATUS_COLOR[status] || 'default';
