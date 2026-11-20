import assert from 'node:assert/strict';
import fs from 'node:fs';
import test, { afterEach } from 'node:test';
import vm from 'node:vm';
import { computed, nextTick, reactive, ref, watch } from 'vue';
import { parse, compileScript } from 'vue/compiler-sfc';
import { formatTaskStatus, formatTaskStatusColor } from '../src/constants/taskStatus.js';
import { i18n } from '../src/i18n/index.js';

const assetText = (...args) => i18n.global.t(...args);

afterEach(() => {
  i18n.global.locale.value = 'zh-CN';
});

function createFakeTimers() {
  let nextId = 1;
  const active = new Map();
  return {
    active,
    setInterval(fn, ms) {
      const id = nextId++;
      active.set(id, { fn, ms });
      return id;
    },
    clearInterval(id) {
      active.delete(id);
    },
    clearAll() {
      active.clear();
    }
  };
}

function collectBindings(relativePath) {
  const raw = fs.readFileSync(new URL(relativePath, import.meta.url), 'utf8');
  const { descriptor } = parse(raw);
  const { scriptSetupAst } = compileScript(descriptor, { id: relativePath });
  const content = descriptor.scriptSetup.content;
  const declarations = new Map();
  const lifecycles = new Map();
  const watchExpressions = [];

  for (const node of scriptSetupAst) {
    if (node.type === 'VariableDeclaration') {
      for (const decl of node.declarations) {
        if (decl.id.type === 'Identifier' && decl.init) {
          declarations.set(decl.id.name, {
            kind: node.kind,
            initCode: content.slice(decl.init.start, decl.init.end)
          });
        }
      }
    } else if (
      node.type === 'ExpressionStatement' &&
      node.expression.type === 'CallExpression' &&
      node.expression.callee.type === 'Identifier'
    ) {
      const callee = node.expression.callee.name;
      const exprCode = content.slice(node.expression.start, node.expression.end);
      if (['onActivated', 'onDeactivated', 'onUnmounted'].includes(callee)) {
        lifecycles.set(callee, exprCode);
      } else if (callee === 'watch') {
        watchExpressions.push(exprCode);
      }
    }
  }

  return { raw, descriptor, declarations, lifecycles, watchExpressions };
}

function loadBindingsIntoContext(parsed, names, context) {
  for (const name of names) {
    const entry = parsed.declarations.get(name);
    assert.ok(entry, `Missing script binding: ${name}`);
    vm.runInContext(`${entry.kind === 'let' ? 'let' : 'const'} ${name} = (${entry.initCode}); globalThis.${name} = ${name};`, context);
  }
}

test('SFC 模板与 KeepAlive 隔离契约：scope_id 键控、日志路由切换、停止按钮与列表态标记就位', () => {
  const detailRaw = fs.readFileSync(new URL('../src/views/GroupAssetsDetail.vue', import.meta.url), 'utf8');
  const panelRaw = fs.readFileSync(new URL('../src/components/EnterpriseOsintPanel.vue', import.meta.url), 'utf8');
  const scopeRaw = fs.readFileSync(new URL('../src/views/AssetScope.vue', import.meta.url), 'utf8');

  assert.match(detailRaw, /<EnterpriseOsintPanel[\s\S]*:key="scope_id"/);
  assert.match(detailRaw, /<EnterpriseOsintPanel[\s\S]*:updating-status="scopeUpdatingStatus"/);
  assert.match(detailRaw, /<EnterpriseOsintPanel[\s\S]*:last-update-error="scopeUpdateError"/);
  assert.match(detailRaw, /<EnterpriseOsintPanel[\s\S]*:active="isPageActive"/);
  assert.match(detailRaw, /@updatingStarted="handleUpdatingStarted"/);
  assert.match(detailRaw, /@updatingStopped="handleUpdatingStopped"/);
  assert.match(detailRaw, /@updateFailed="handleUpdateFailed"/);
  assert.match(detailRaw, /@dismissUpdateError="handleDismissUpdateError"/);

  assert.match(panelRaw, /formatTaskStatus\(effectiveLogStatus\)/);
  assert.match(panelRaw, /v-if="stopTargetTaskId"[\s\S]*@confirm="handleStopUpdate"/);
  assert.match(panelRaw, /v-if="props\.lastUpdateError && !isUpdating"[\s\S]*@close="emit\('dismissUpdateError'\)"/);

  assert.match(scopeRaw, /v-if="record\.updating_icp_task_id"/);
  assert.match(scopeRaw, /updatingQueuedInQueue/);
  assert.match(scopeRaw, /updatingInProgressLabel/);
});

test('EnterpriseOsintPanel: KeepAlive 失活/切换清空轮询定时器并对齐测绘日志与停止目标', async () => {
  const parsed = collectBindings('../src/components/EnterpriseOsintPanel.vue');
  const timers = createFakeTimers();
  const requests = [];
  const emitted = [];
  const toastMsgs = { success: [], info: [], error: [] };
  const notifMsgs = { success: [], error: [] };

  const props = reactive({
    taskId: 'bound_a',
    scopeId: 'scope_a',
    enterpriseName: 'Enterprise A',
    hideHeader: true,
    stickyTopOffset: 64,
    updatingTaskId: 'upd_a',
    updatingStatus: 'waiting',
    updatingStartTime: '2026-11-16 08:00:00',
    lastUpdateError: '',
    active: true
  });

  const emit = (name, payload) => emitted.push({ name, payload });

  const context = vm.createContext({
    props,
    emit,
    ref,
    reactive,
    computed,
    watch,
    nextTick,
    assetText,
    formatTaskStatus,
    formatTaskStatusColor,
    console,
    Date,
    Math,
    Number,
    String,
    Array,
    Object,
    Set,
    isNaN,
    parseFloat,
    setInterval: timers.setInterval,
    clearInterval: timers.clearInterval,
    message: {
      success: (m) => toastMsgs.success.push(m),
      info: (m) => toastMsgs.info.push(m),
      error: (m) => toastMsgs.error.push(m)
    },
    notification: {
      success: (n) => notifMsgs.success.push(n),
      error: (n) => notifMsgs.error.push(n)
    },
    request: {
      get: async (url, cfg = {}) => {
        requests.push({ method: 'GET', url, params: cfg.params || {} });
        if (url === '/api/system_config/proxy') return { code: 200, data: {} };
        if (url === '/asset_scope/') return { code: 200, items: [{ scope_id: props.scopeId, domain_array: ['a.example.com'] }] };
        if (url.startsWith('/icp/task/log/')) {
          return { code: 200, items: [{ create_time: '2026-11-16 08:00:01', level: 'info', title: 'icp', message: `log-for-${url.split('/').pop()}` }] };
        }
        if (url === '/icp/task') {
          const id = cfg.params?._id;
          if (id === 'upd_a') {
            return { code: 200, items: [{ _id: 'upd_a', status: props.updatingStatus || 'waiting', start_time: '2026-11-16 08:00:00' }] };
          }
          return { code: 200, items: [{ _id: id, name: 'Org', target: 'Org', task_type: 'tyc', status: 'done', statistic: { web_cnt: 3 } }] };
        }
        if (url === '/icp/asset') return { code: 200, items: [], total: 0 };
        if (url.startsWith('/icp/stop/')) return { code: 200, data: { confirmed: true } };
        if (url.startsWith('/icp/restart/')) return { code: 200, data: { task_id: 'upd_new_1' } };
        return { code: 200, items: [] };
      }
    }
  });

  vm.runInContext(`
    const registeredLifecycles = {};
    globalThis.registeredLifecycles = registeredLifecycles;
    const onActivated = (fn) => { registeredLifecycles.onActivated = fn; };
    const onDeactivated = (fn) => { registeredLifecycles.onDeactivated = fn; };
    const onUnmounted = (fn) => { registeredLifecycles.onUnmounted = fn; };
    const osintResizeObserver = null;
    const osintControlRef = ref(null);
    const updateOsintHeight = () => {};
    const fetchOsintProxyStatus = () => {};
    const currentSearchFields = computed(() => []);
    const searchForm = reactive({});
    const pagination = reactive({ current: 1, pageSize: 10, total: 0 });
    const loading = ref(false);
    const refreshLoading = ref(false);
    const syslogList = ref([]);
    globalThis.syslogList = syslogList;
    const assetList = ref([]);
    const terminalContainer = ref(null);
    const logLoading = ref(false);
    const activeTab = ref('log');
    const taskRecord = ref({});
    const taskName = ref('');
    const taskTarget = ref('');
    const taskType = ref('icp');
    const taskStatus = ref('');
    const hasIncrement = ref(false);
    const managedDomainSet = ref(new Set());
    const allTaskWebDomains = ref([]);
    const selectedWebRowKeys = ref([]);
    const selectedWebDomains = ref([]);
    const queryCounts = reactive({ web: 0, app: 0, mapp: 0, wechat: 0, weibo: 0, kapp: 0, invest: 0 });
    let logTimer = null;
    const taskTypeLabel = computed(() => taskType.value);
    const taskStatusLabel = computed(() => formatTaskStatus(taskStatus.value));
    const taskStatusColor = computed(() => formatTaskStatusColor(taskStatus.value));
  `, context);

  loadBindingsIntoContext(parsed, [
    'activeUpdatingTaskId',
    'isUpdating',
    'updatingStatusState',
    'updateElapsed',
    'stopLoading',
    'isPanelActive',
    'updateTimer',
    'elapsedTimer',
    'boundTaskTimer',
    'updateStartTimestampMs',
    'parseStartTimeMs',
    'computeElapsedSeconds',
    'stopUpdatePolling',
    'stopBoundTaskPolling',
    'isBoundTaskActive',
    'isAnyDiscoveryActive',
    'updateActionTooltip',
    'updateActionLabel',
    'stopTargetTaskId',
    'effectiveLogTaskId',
    'effectiveLogStatus',
    'isLogTaskActive',
    'latestTaskDetailSeq',
    'latestAssetsSeq',
    'latestLogsSeq',
    'fetchTaskDetail',
    'fetchAllTaskWebDomains',
    'fetchManagedDomains',
    'fetchAssets',
    'fetchLogs',
    'startLogPolling',
    'stopLogPolling',
    'startBoundTaskPolling',
    'startUpdatePolling',
    'stopAllPollers',
    'syncActivePollers',
    'handleRefreshTask',
    'handleStopUpdate'
  ], context);

  // 注册 Panel 内 4 个核心 props 监听器与 KeepAlive 生命周期
  const relevantWatches = parsed.watchExpressions.filter((w) =>
    /^watch\(\s*\(\)\s*=>\s*(?:\[\s*props\.updatingTaskId|props\.(?:taskId|scopeId|active)\b)/.test(w)
  );
  assert.equal(relevantWatches.length, 4, 'Should capture all 4 core EnterpriseOsintPanel watchers');
  for (const wExpr of relevantWatches) {
    vm.runInContext(wExpr, context);
  }
  for (const name of ['onActivated', 'onDeactivated', 'onUnmounted']) {
    const code = parsed.lifecycles.get(name);
    assert.ok(code, `Missing ${name}`);
    vm.runInContext(code, context);
  }

  await nextTick();
  await new Promise((r) => setTimeout(r, 20));

  assert.equal(context.isUpdating.value, true);
  assert.equal(context.activeUpdatingTaskId.value, 'upd_a');
  assert.equal(context.updatingStatusState.value, 'waiting');
  assert.equal(context.effectiveLogTaskId.value, 'upd_a');
  assert.equal(context.effectiveLogStatus.value, 'waiting');
  assert.equal(context.stopTargetTaskId.value, 'upd_a');
  assert.equal(context.syslogList.value[0]?.message, 'log-for-upd_a');
  assert.ok(timers.active.size >= 2, 'Active panel should hold update/elapsed/log pollers');

  // 1) KeepAlive 失活：立即销毁全部定时器，禁止后台泄露轮询
  context.registeredLifecycles.onDeactivated();
  await nextTick();
  assert.equal(timers.active.size, 0, 'Deactivation must clear every polling interval immediately');

  // 2) 切往无更新中的分组 B：props.updatingTaskId 变为空且 taskId 切换，更新态与日志立即切回分组 B
  props.updatingTaskId = '';
  props.updatingStatus = '';
  props.scopeId = 'scope_b';
  props.taskId = 'bound_b';
  await nextTick();
  await new Promise((r) => setTimeout(r, 20));

  assert.equal(context.isUpdating.value, false);
  assert.equal(context.activeUpdatingTaskId.value, '');
  assert.equal(context.updatingStatusState.value, '');
  assert.equal(context.effectiveLogTaskId.value, 'bound_b');
  assert.equal(context.syslogList.value[0]?.message, 'log-for-bound_b');

  // 3) 切回正在更新的分组 A 并重新激活：恢复对 upd_a 的追踪与停止能力
  props.scopeId = 'scope_a';
  props.taskId = 'bound_a';
  props.updatingTaskId = 'upd_a';
  props.updatingStatus = 'running';
  context.registeredLifecycles.onActivated();
  await nextTick();
  await new Promise((r) => setTimeout(r, 20));

  assert.equal(context.isUpdating.value, true);
  assert.equal(context.stopTargetTaskId.value, 'upd_a');
  assert.ok(timers.active.size >= 2);

  // 4) 点击停止更新：调用 /icp/stop/upd_a，保留快照 bound_a，清空 updating 态与定时器
  await context.handleStopUpdate();
  assert.ok(requests.some((r) => r.url === '/icp/stop/upd_a'));
  assert.equal(context.isUpdating.value, false);
  assert.equal(context.activeUpdatingTaskId.value, '');
  assert.ok(emitted.some((e) => e.name === 'updatingStopped' && e.payload === 'upd_a'));
  assert.equal(props.taskId, 'bound_a');

  timers.clearAll();
});

test('EnterpriseOsintPanel: 初次绑定任务运行中禁用更新按钮并在完成后自动刷新资产', async () => {
  const parsed = collectBindings('../src/components/EnterpriseOsintPanel.vue');
  const timers = createFakeTimers();
  let boundStatus = 'running';
  let assetFetchCount = 0;
  const notifMsgs = { success: [], error: [] };

  const props = reactive({
    taskId: 'init_running_task',
    scopeId: 'scope_init',
    enterpriseName: 'New Corp',
    updatingTaskId: '',
    updatingStatus: '',
    updatingStartTime: '',
    lastUpdateError: '',
    active: true
  });

  const context = vm.createContext({
    props,
    emit: () => {},
    ref,
    reactive,
    computed,
    watch,
    nextTick,
    assetText,
    formatTaskStatus,
    formatTaskStatusColor,
    console,
    Date,
    Math,
    Number,
    String,
    Array,
    Object,
    Set,
    isNaN,
    parseFloat,
    setInterval: timers.setInterval,
    clearInterval: timers.clearInterval,
    message: { success: () => {}, info: () => {}, error: () => {} },
    notification: {
      success: (n) => notifMsgs.success.push(n),
      error: (n) => notifMsgs.error.push(n)
    },
    request: {
      get: async (url) => {
        if (url === '/icp/task') {
          return {
            code: 200,
            items: [{ _id: 'init_running_task', name: 'New Corp', target: 'New Corp', task_type: 'tyc', status: boundStatus, statistic: { web_cnt: 8 } }]
          };
        }
        if (url === '/icp/asset') {
          assetFetchCount += 1;
          return { code: 200, items: [{ domain: 'new.example.com' }], total: 1 };
        }
        if (url === '/asset_scope/') {
          return { code: 200, items: [{ domain_array: [] }] };
        }
        return { code: 200, items: [] };
      }
    }
  });

  vm.runInContext(`
    const fetchOsintProxyStatus = () => {};
    const currentSearchFields = computed(() => []);
    const searchForm = reactive({});
    const pagination = reactive({ current: 1, pageSize: 10, total: 0 });
    const loading = ref(false);
    const refreshLoading = ref(false);
    const syslogList = ref([]);
    globalThis.syslogList = syslogList;
    const assetList = ref([]);
    const terminalContainer = ref(null);
    const logLoading = ref(false);
    const activeTab = ref('web');
    const taskRecord = ref({});
    const taskName = ref('');
    const taskTarget = ref('');
    const taskType = ref('icp');
    const taskStatus = ref('');
    const hasIncrement = ref(false);
    const managedDomainSet = ref(new Set());
    const allTaskWebDomains = ref([]);
    const queryCounts = reactive({ web: 0, app: 0, mapp: 0, wechat: 0, weibo: 0, kapp: 0, invest: 0 });
    let logTimer = null;
    const taskTypeLabel = computed(() => taskType.value);
    const taskStatusLabel = computed(() => formatTaskStatus(taskStatus.value));
    const taskStatusColor = computed(() => formatTaskStatusColor(taskStatus.value));
  `, context);

  loadBindingsIntoContext(parsed, [
    'activeUpdatingTaskId',
    'isUpdating',
    'updatingStatusState',
    'updateElapsed',
    'stopLoading',
    'isPanelActive',
    'updateTimer',
    'elapsedTimer',
    'boundTaskTimer',
    'updateStartTimestampMs',
    'parseStartTimeMs',
    'computeElapsedSeconds',
    'stopUpdatePolling',
    'stopBoundTaskPolling',
    'isBoundTaskActive',
    'isAnyDiscoveryActive',
    'updateActionTooltip',
    'updateActionLabel',
    'stopTargetTaskId',
    'effectiveLogTaskId',
    'effectiveLogStatus',
    'isLogTaskActive',
    'latestTaskDetailSeq',
    'latestAssetsSeq',
    'latestLogsSeq',
    'fetchTaskDetail',
    'fetchAllTaskWebDomains',
    'fetchManagedDomains',
    'fetchAssets',
    'fetchLogs',
    'startLogPolling',
    'stopLogPolling',
    'startBoundTaskPolling',
    'startUpdatePolling',
    'stopAllPollers',
    'syncActivePollers'
  ], context);

  await context.fetchTaskDetail();
  assert.equal(context.isBoundTaskActive.value, true);
  assert.equal(context.isAnyDiscoveryActive.value, true);
  assert.equal(context.stopTargetTaskId.value, 'init_running_task');
  assert.equal(timers.active.size, 1, 'Bound active task must start boundTaskTimer');

  // 后端完成初次测绘
  boundStatus = 'done';
  await context.fetchTaskDetail();
  assert.equal(context.isBoundTaskActive.value, false);
  assert.equal(context.isAnyDiscoveryActive.value, false);
  assert.equal(context.stopTargetTaskId.value, '');
  assert.equal(timers.active.size, 0, 'Completion must clear boundTaskTimer');
  assert.equal(notifMsgs.success.length, 1);
  assert.ok(assetFetchCount >= 1);
});

test('GroupAssetsDetail: 切换分组时同步清零 OSINT 更新态并丢弃迟到响应，失败提示支持持久化与关闭清理', async () => {
  const parsed = collectBindings('../src/views/GroupAssetsDetail.vue');
  const route = reactive({ query: { scope_id: 'scope_a', view: 'osint' } });
  const clearedErrors = [];
  let resolveSlowScopeA;

  const context = vm.createContext({
    route,
    ref,
    reactive,
    computed,
    watch,
    nextTick,
    queueMicrotask,
    assetText,
    formatTaskStatus,
    formatTaskStatusColor,
    console,
    Object,
    Promise,
    String,
    Number,
    Boolean,
    request: {
      get: (url, cfg = {}) => {
        if (url === '/asset_scope/') {
          const sid = cfg.params?._id;
          if (sid === 'scope_a' && !resolveSlowScopeA) {
            return Promise.resolve({
              code: 200,
              items: [{
                _id: 'scope_a',
                name: '分组A',
                enterprise_name: '企业A',
                synced_icp_task_id: 'task_a',
                updating_icp_task_id: 'upd_a',
                updating_status: 'waiting',
                updating_start_time: '2026-11-16 08:00:00',
                update_error_msg: ''
              }]
            });
          }
          if (sid === 'scope_a') {
            return new Promise((resolve) => { resolveSlowScopeA = resolve; });
          }
          if (sid === 'scope_b') {
            return Promise.resolve({
              code: 200,
              items: [{
                _id: 'scope_b',
                name: '分组B',
                enterprise_name: '企业B',
                synced_icp_task_id: 'task_b',
                updating_icp_task_id: '',
                updating_status: '',
                updating_start_time: '',
                update_error_msg: '天眼查配额不足'
              }]
            });
          }
        }
        if (url === '/icp/task') {
          const tid = cfg.params?._id;
          return Promise.resolve({ code: 200, items: [{ _id: tid, target: tid, task_type: 'tyc', status: 'done', statistic: { web_cnt: 2 } }] });
        }
        return Promise.resolve({ code: 200, items: [], total: 0 });
      },
      post: async (url, data) => {
        if (url === '/asset_scope/clear_update_error/') {
          clearedErrors.push(data.scope_id);
        }
        return { code: 200 };
      }
    }
  });

  vm.runInContext(`
    const registeredLifecycles = {};
    globalThis.registeredLifecycles = registeredLifecycles;
    const onActivated = (fn) => { registeredLifecycles.onActivated = fn; };
    const onDeactivated = (fn) => { registeredLifecycles.onDeactivated = fn; };
    const scope_id = computed(() => route.query.scope_id || '');
    const scopeEnterpriseName = ref('');
    const taskStatusColor = ref('default');
    const osintTotalCount = ref(0);
    const asmCounts = reactive({ site: 0, domain: 0, ip: 0 });
    const tabConfig = {};
    const isScopeSwitching = ref(false);
    const dataSource = ref([]);
    const selectedRowKeys = ref([]);
    const pagination = reactive({ current: 1, pageSize: 10, total: 0 });
    const activeTab = ref('site');
    const effectiveTab = ref('site');
    const columns = ref([]);
    const searchForm = ref({});
    const serviceEngineType = ref('nmap');
    const tabCache = { init: () => 'site', getTabSearchForm: () => ({}), applyTabOperators: () => {}, getTabPage: () => 1, getMemoryCache: () => ({ dataSource: [], total: 0 }) };
    const fetchData = () => Promise.resolve();
    const fingerModalVisible = ref(false);
    const cipDetailModalVisible = ref(false);
    const previewVisible = ref(false);
    const tagVisible = ref(false);
    const addSiteVisible = ref(false);
    const riskModalVisible = ref(false);
    const addDomainVisible = ref(false);
    const bindModalVisible = ref(false);
    const chainDrawerVisible = ref(false);
    const rawDrawerVisible = ref(false);
    const openChainDrawer = () => {};
    let lastFetchedPage = 1;
    let lastFetchedSize = 10;
  `, context);

  loadBindingsIntoContext(parsed, [
    'osintPanelRef',
    'boundIcpTaskId',
    'scopeUpdatingTaskId',
    'scopeUpdatingStatus',
    'scopeUpdatingStartTime',
    'scopeUpdateError',
    'isPageActive',
    'hasDeactivated',
    'lastObservedScopeId',
    'justSyncedOnActivated',
    'latestScopeMetaSeq',
    'scopeHasIncrement',
    'scopeGroupName',
    'scopeType',
    'scopeDomainList',
    'boundTaskRecord',
    'taskTarget',
    'fetchBoundTaskDetail',
    'fetchAsmCounts',
    'resetOsintAndScopeMeta',
    'handleUpdatingStarted',
    'handleUpdatingStopped',
    'handleUpdateFailed',
    'handleOsintRefreshed',
    'handleDismissUpdateError',
    'fetchScopeMeta'
  ], context);

  const scopeWatchExpr = parsed.watchExpressions.find((w) => w.startsWith('watch(scope_id,'));
  assert.ok(scopeWatchExpr, 'Missing watch(scope_id, ...)');
  vm.runInContext(scopeWatchExpr, context);
  vm.runInContext(parsed.lifecycles.get('onActivated'), context);
  vm.runInContext(parsed.lifecycles.get('onDeactivated'), context);

  await new Promise((r) => setTimeout(r, 20));
  assert.equal(context.boundIcpTaskId.value, 'task_a');
  assert.equal(context.scopeUpdatingTaskId.value, 'upd_a');
  assert.equal(context.scopeUpdatingStatus.value, 'waiting');

  // 触发一个缓慢的 scope_a 请求，然后用户退回列表并立即点进 scope_b
  resolveSlowScopeA = null;
  const slowAReq = (() => {
    resolveSlowScopeA = undefined; // force slow branch below
  });
  void slowAReq;
  // 先发起 scope_a 的后台刷新模拟（第二次调用走 slow promise）
  resolveSlowScopeA = () => {};
  const inflightA = context.fetchScopeMeta();
  context.registeredLifecycles.onDeactivated();
  assert.equal(context.isPageActive.value, false);

  route.query.scope_id = 'scope_b';
  // 在 await 之前同步断言：切换一瞬即刻清零分组 A 的更新状态，防止闪现
  await nextTick();
  assert.equal(context.scopeUpdatingTaskId.value, '');
  assert.equal(context.boundIcpTaskId.value, '');

  context.registeredLifecycles.onActivated();
  assert.equal(context.isPageActive.value, true);

  // 让迟到的 scope_a 响应落地，必须被序列号与当前 scope_id 双重防线丢弃
  resolveSlowScopeA({
    code: 200,
    items: [{
      _id: 'scope_a',
      name: '分组A',
      enterprise_name: '企业A',
      synced_icp_task_id: 'task_a',
      updating_icp_task_id: 'upd_a',
      updating_status: 'running'
    }]
  });
  await inflightA;
  await new Promise((r) => setTimeout(r, 20));

  assert.equal(context.boundIcpTaskId.value, 'task_b');
  assert.equal(context.scopeUpdatingTaskId.value, '');
  assert.equal(context.scopeUpdateError.value, '天眼查配额不足');

  // 关闭错误摘要提示
  await context.handleDismissUpdateError();
  assert.equal(context.scopeUpdateError.value, '');
  assert.deepEqual(clearedErrors, ['scope_b']);
});
