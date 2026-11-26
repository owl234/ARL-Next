import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { computed, reactive, ref, watch } from 'vue';
import { compileScript, parse } from 'vue/compiler-sfc';
import { i18n } from '../src/i18n/index.js';
import { buildAssetFilterParams } from '../src/utils/assetFilters.js';

const plain = value => JSON.parse(JSON.stringify(value));
const t = (...args) => i18n.global.t(...args);

function loadBindings(relPath, extra = {}) {
  const src = fs.readFileSync(new URL(`../src/${relPath}`, import.meta.url), 'utf8');
  const { descriptor } = parse(src);
  const { scriptSetupAst } = compileScript(descriptor, { id: relPath });
  const bindings = {};
  for (const node of scriptSetupAst) {
    if (node.type === 'VariableDeclaration') {
      for (const item of node.declarations) {
        if (item.id.type === 'Identifier' && item.init) {
          bindings[item.id.name] = descriptor.scriptSetup.content.slice(item.init.start, item.init.end);
        }
      }
    }
  }
  const ctx = vm.createContext({
    ref, reactive, computed, watch, console,
    taskText: t, assetText: t,
    buildAssetFilterParams,
    ...extra,
  });
  return {
    src,
    descriptor,
    ctx,
    read(name) {
      assert.ok(bindings[name], `${relPath}: missing binding ${name}`);
      vm.runInContext(`var ${name} = ${bindings[name]};`, ctx);
      return ctx[name];
    },
  };
}

test('P0-1: AssetSearch、TaskDetail、GroupAssetsDetail 勾选站点风险巡航改走 POST JSON 并严格 Fail-Closed', async () => {
  const cases = [
    {
      file: 'views/AssetSearch.vue',
      endpoint: '/site/save_result_set/',
      expectedBody: { _id: ['oid1', 'oid2'] },
      modalRefKey: 'riskVisible',
    },
    {
      file: 'views/TaskDetail.vue',
      endpoint: '/site/save_result_set/',
      expectedBody: { _id: ['oid1', 'oid2'], task_id: 'task-42' },
      modalRefKey: 'riskVisible',
    },
    {
      file: 'views/GroupAssetsDetail.vue',
      endpoint: '/asset_site/save_result_set/',
      expectedBody: { _id: ['oid1', 'oid2'], scope_id: 'scope-42' },
      modalRefKey: 'riskModalVisible',
    },
  ];

  for (const item of cases) {
    const calls = [];
    const notices = [];
    let postResponse = { code: 200, data: { result_set_id: 'rs-ok', result_total: 2 } };
    const modalVisible = ref(false);
    const selectedRowKeys = ref(['oid1', 'oid2']);

    const page = loadBindings(item.file, {
      activeTab: ref('site'),
      effectiveTab: ref('site'),
      taskId: ref('task-42'),
      scope_id: ref('scope-42'),
      targetName: ref('demo'),
      searchForm: ref({}),
      pagination: { current: 1, pageSize: 20, total: 999 },
      selectedRowKeys,
      hasSelected: computed(() => selectedRowKeys.value.length > 0),
      dataSource: ref([{ _id: 'oid1', site: 'https://a.example.test' }]),
      riskForm: reactive({ name: '', policy_id: undefined }),
      policyOptions: ref([]),
      policies: ref([{ _id: 'p1', name: 'P1' }]),
      currentResultSetId: ref(''),
      targetCount: ref(0),
      currentTargetCount: ref(0),
      selectedRiskTargets: ref([]),
      [item.modalRefKey]: modalVisible,
      formatRiskPolicyLabel: p => p.name,
      message: Object.fromEntries(['loading', 'success', 'error', 'warning'].map(k => [k, v => notices.push({ k, v })])),
      request: {
        async get(url, opts) {
          calls.push({ method: 'GET', url, opts: plain(opts || {}) });
          if (url === '/policy/') return { code: 200, items: [{ _id: 'p1', name: 'P1' }] };
          return { code: 200, data: { result_set_id: 'rs-get', result_total: 999 } };
        },
        async post(url, body) {
          calls.push({ method: 'POST', url, body: plain(body) });
          return postResponse;
        },
      },
    });
    page.read('tabConfig');
    const openRiskModal = page.read('openRiskModal');

    // 1. 勾选模式发送 POST JSON 载荷，绝不降级 GET
    await openRiskModal();
    const postCalls = calls.filter(c => c.method === 'POST');
    assert.equal(postCalls.length, 1, `${item.file}: must use POST when rows are selected`);
    assert.equal(postCalls[0].url, item.endpoint);
    assert.deepEqual(postCalls[0].body, item.expectedBody);
    assert.equal(modalVisible.value, true);
    assert.equal(page.ctx.currentResultSetId.value, 'rs-ok');

    // 2. 后端返回非 200 时阻断打开弹窗并报错
    modalVisible.value = false;
    page.ctx.currentResultSetId.value = '';
    postResponse = { code: 400, message: 'invalid ids' };
    await openRiskModal();
    assert.equal(modalVisible.value, false, `${item.file}: must NOT open risk modal on non-200`);
    assert.ok(notices.some(n => n.k === 'error'));

    // 3. 超过 500 条勾选时直接前端拦截，不发 POST 请求
    const callsBeforeLimit = calls.length;
    selectedRowKeys.value = Array.from({ length: 501 }, (_, i) => `oid-${i}`);
    await openRiskModal();
    assert.equal(calls.length, callsBeforeLimit, `${item.file}: must block >500 selection before HTTP`);
    assert.ok(notices.some(n => n.k === 'warning'));
  }
});

test('P1: GroupAssetsDetail 总资产不重复计入 npoc_service、筛选不污染徽标、WIH source 列隔离防冲突', async () => {
  const asmCounts = reactive({
    site: 5, domain: 4, ip: 3, cert: 2, service: 10, npoc_service: 6,
    fileleak: 1, url: 2, cip: 1, stat_finger: 3, wih: 2, vuln: 1, nuclei_result: 1,
  });
  const page = loadBindings('views/GroupAssetsDetail.vue', {
    asmCounts,
    activeTab: ref('site'),
    scope_id: ref('scope-1'),
    searchForm: ref({ title: 'admin' }),
    pagination: reactive({ current: 1, pageSize: 20, total: 0 }),
    loading: ref(false),
    dataSource: ref([]),
    lastFetchedPage: 1,
    lastFetchedSize: 20,
    selectionTracker: { rememberRows() {}, syncSelection() {}, getLabels: () => [], clear() {} },
    getAssetRowKey: r => r?._id,
    getAssetRecordDisplayLabel: () => '',
    tabCache: { updateMemoryCache() {}, saveCurrentTab() {} },
    message: { error(err) { assert.fail(err); } },
    request: {
      async get() { return { code: 200, items: [{ _id: 's1' }], total: 1 }; },
    },
  });
  page.read('asmTabList');
  page.read('getAsmTabCount');
  const asmTotalCount = page.read('asmTotalCount');
  // 12 维之和 = 5+4+3+2+10+1+2+1+3+2+1+1 = 35（不含 npoc_service=6）
  assert.equal(asmTotalCount.value, 35);

  page.read('tabConfig');
  page.read('effectiveTab');
  const fetchData = page.read('fetchData');
  // 带筛选条件拉取 total=1 时，不得覆盖未筛选总量徽标 asmCounts.site=5
  await fetchData();
  assert.equal(page.ctx.pagination.total, 1);
  assert.equal(asmCounts.site, 5);

  // 清空筛选后拉取 total=1，正确同步回 asmCounts.site
  page.ctx.searchForm.value = {};
  await fetchData();
  assert.equal(asmCounts.site, 1);

  // WIH source 列使用独立 key 'wih_source'，避免污染 domain.source 渲染；且外链校验 isHttpUrl + noopener
  const wihCols = page.ctx.tabConfig.wih.cols;
  assert.ok(wihCols.some(c => c.key === 'wih_source'));
  assert.ok(!wihCols.some(c => c.key === 'source'));
  assert.match(page.descriptor.template.content, /column\.key === 'wih_source'/);
  assert.match(page.descriptor.template.content, /isHttpUrl\(record\.source\)/);
  assert.match(page.descriptor.template.content, /rel="noopener noreferrer"/);
});

test('P1: PlanningTasks 胶囊切换清空勾选、批量操作按状态预过滤、失败不误清空且不误发变异事件', async () => {
  const replaced = [];
  const posts = [];
  const modals = [];
  const notices = [];
  let mutatedCount = 0;

  const src = fs.readFileSync(new URL('../src/views/PlanningTasks.vue', import.meta.url), 'utf8');
  const { descriptor } = parse(src);
  const { scriptSetupAst } = compileScript(descriptor, { id: 'PlanningTasks.vue' });
  let body = descriptor.scriptSetup.content;
  for (const node of [...scriptSetupAst].reverse()) {
    if (node.type === 'ImportDeclaration') body = body.slice(0, node.start) + body.slice(node.end);
  }

  let activatedCb = null;
  let policyFetchCount = 0;
  let monitorPostFail = false;

  const ctx = vm.createContext({
    ref, reactive, computed, watch, console,
    setInterval: () => 1,
    clearInterval: () => {},
    localStorage: { getItem: () => '' },
    createVNode: () => ({}),
    defineOptions: () => {},
    useI18n: () => ({ t, locale: ref('zh-CN') }),
    useRoute: () => ({ query: {} }),
    useRouter: () => ({ replace: arg => replaced.push(plain(arg)), push: () => {} }),
    useSticky: () => ({ stickyConfig: computed(() => false) }),
    useGlobalPageSize: () => ref(10),
    onMounted: () => {},
    onActivated: fn => { activatedCb = fn; },
    onDeactivated: () => {},
    onUnmounted: () => {},
    createSelectionLabelTracker: () => ({
      rememberRows() {},
      syncSelection() {},
      getLabels: keys => keys.map(k => `label:${k}`),
      clear() {},
    }),
    buildSelectionConfirmContent: opts => opts,
    assetMutationVersion: ref(0),
    notifyAssetMutated: () => { mutatedCount += 1; },
    request: {
      async get(url) {
        if (url === '/policy/') { policyFetchCount += 1; return { code: 200, items: [] }; }
        if (url === '/task_schedule/') {
          return {
            code: 200,
            items: [{ _id: 'p2', name: 'plan-stopped', status: 'stop', schedule_type: 'recurrent_scan' }],
            total: 1,
          };
        }
        if (url === '/scheduler/') {
          return {
            code: 200,
            items: [{ _id: 'm1', name: 'mon-stopped', status: 'stop', scope_id: 's1', domain: 'a.example.test' }],
            total: 1,
          };
        }
        return { code: 200, items: [], total: 0 };
      },
      async post(url, payload) {
        posts.push({ url, payload: plain(payload) });
        if (monitorPostFail && url.startsWith('/scheduler/')) {
          return { code: 400, message: 'monitor stop failed' };
        }
        return { code: 200 };
      },
    },
    message: Object.fromEntries(['success', 'error', 'warning', 'info'].map(k => [k, v => notices.push({ k, v })])),
    Modal: { confirm: opts => modals.push(opts) },
    dayjs: () => ({}),
    formatTaskStatus: s => s,
    ExclamationCircleOutlined: {}, SearchOutlined: {}, DeleteOutlined: {}, UndoOutlined: {},
    PauseCircleOutlined: {}, PlayCircleOutlined: {}, SendOutlined: {}, ReloadOutlined: {},
    ClockCircleOutlined: {}, RadarChartOutlined: {}, PlusOutlined: {},
    AppstoreOutlined: {}, CheckCircleOutlined: {}, CloseCircleOutlined: {},
    GlobalOutlined: {}, ClusterOutlined: {},
  });

  const exposed = vm.runInContext(
    `${body}\n;({ rawPlanItems, rawMonitorItems, selectedRowKeys, onCategoryChange, handleBatchAction, executeDispatchedActions, activeCategory });`,
    ctx
  );

  // 1. 装载 2 条计划任务（1 scheduled, 1 stop）与 1 条监控任务（stop）
  exposed.rawPlanItems.value = [
    { _id: 'p1', name: 'plan-active', status: 'scheduled', schedule_type: 'recurrent_scan' },
    { _id: 'p2', name: 'plan-stopped', status: 'stop', schedule_type: 'recurrent_scan' },
  ];
  exposed.rawMonitorItems.value = [
    { _id: 'm1', name: 'mon-stopped', status: 'stop', scope_id: 's1', domain: 'a.example.test' },
  ];

  // 2. 批量停止：仅 1 条 scheduled 符合，2 条 stop 被跳过并在摘要中提示
  exposed.selectedRowKeys.value = ['planning:p1', 'planning:p2', 'monitor:m1'];
  exposed.handleBatchAction('stop');
  assert.equal(modals.length, 1);
  assert.deepEqual(modals[0].content.items, ['label:planning:p1']);
  assert.match(modals[0].content.summary, /跳过 2 项/);

  // 3. 全部不符合（仅选 stop 去执行 stop）：警告并阻断，不弹确认框
  exposed.selectedRowKeys.value = ['planning:p2', 'monitor:m1'];
  exposed.handleBatchAction('stop');
  assert.equal(modals.length, 1);
  assert.ok(notices.some(n => n.k === 'warning'));

  // 4. 混合删除时监控分支失败：保留失败项勾选、不触发 notifyAssetMutated、提示错误
  monitorPostFail = true;
  exposed.selectedRowKeys.value = ['planning:p1', 'monitor:m1'];
  const ok = await exposed.executeDispatchedActions('delete', ['planning:p1', 'monitor:m1']);
  assert.equal(ok, false);
  assert.equal(mutatedCount, 0);
  assert.deepEqual(plain(exposed.selectedRowKeys.value), ['monitor:m1']);
  assert.ok(notices.some(n => n.k === 'error' && String(n.v).includes('monitor stop failed')));

  // 5. 切换顶层胶囊自动清空已勾选行
  exposed.onCategoryChange('planning');
  assert.equal(exposed.selectedRowKeys.value.length, 0);

  // 6. KeepAlive 再次激活（返回页面）同步刷新策略列表
  assert.ok(typeof activatedCb === 'function');
  policyFetchCount = 0;
  activatedCb(); // 首次激活由 onMounted 负责，跳过重复拉取
  activatedCb(); // 再次激活返回页面，触发 fetchPolicyList
  assert.equal(policyFetchCount, 1);

  // 7. 模板行按钮统一使用 tasks.stop（非 tasks.pause）
  assert.doesNotMatch(descriptor.template.content, /tasks\.pause\b/);
});
