import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import vm from 'node:vm';
import { applyTaskStatistics, createTaskListClient } from '../src/utils/taskStatistics.js';
import { buildTaskQueryParams } from '../src/utils/taskFilters.js';
import { i18n } from '../src/i18n/index.js';

const counts = { total: 9, active: 3, done: 4, abnormal: 2 };
const tick = () => new Promise(resolve => setImmediate(resolve));

test('valid statistics update all metrics; failed or incomplete statistics keep old values', () => {
  const metrics = { total: 1, running: 1, done: 0, abnormal: 0 };
  assert.equal(applyTaskStatistics(metrics, counts), true);
  assert.deepEqual(metrics, { total: 9, running: 3, done: 4, abnormal: 2 });
  for (const invalid of [undefined, {}, { ...counts, active: -1 }, { ...counts, total: '9' }]) {
    assert.equal(applyTaskStatistics(metrics, invalid), false);
    assert.equal(metrics.total, 9);
  }
});

test('identical concurrent requests share one RPC, then later refreshes run again', async () => {
  const calls = [];
  let release;
  const client = createTaskListClient({ get: (endpoint, options) => {
    calls.push({ endpoint, ...options });
    return new Promise(resolve => { release = resolve; });
  } });
  const first = client.get('/task/', { page: 1, size: 10 });
  const second = client.get('/task/', { size: 10, page: 1 });
  assert.equal(first, second);
  await tick();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].params.include_statistics, 1);
  release({ code: 200 });
  await first;
  const next = client.get('/task/', { page: 1, size: 10 });
  await tick();
  assert.equal(calls.length, 2);
  release({ code: 200 });
  await next;
});

test('failed requests release the in-flight entry so retry is possible', async () => {
  let calls = 0;
  const client = createTaskListClient({ get: async () => {
    if (++calls === 1) throw new Error('fixture');
    return { code: 200 };
  } });
  await assert.rejects(client.get('/task/', { page: 1 }), /fixture/);
  assert.equal((await client.get('/task/', { page: 1 })).code, 200);
  assert.equal(calls, 2);
});

test('ordinary pagination can omit statistics; distinct tabs and pages remain separate', async () => {
  const calls = [];
  const client = createTaskListClient({ get: async (endpoint, options) => {
    calls.push({ endpoint, ...options });
    return { code: 200 };
  } });
  await Promise.all([client.get('/task/', { page: 2 }, false), client.get('/task/', { page: 1 }),
    client.get('/icp/task', { page: 1 })]);
  assert.equal(calls.length, 3);
  assert.equal('include_statistics' in calls[0].params, false);
});

// 执行组件的原加载函数及生命周期回调；网络、Vue refs 和定时器使用替身。
const source = readFileSync(new URL('../src/views/TaskList.vue', import.meta.url), 'utf8');
function functionSource(name) {
  const start = source.indexOf(`const ${name} = `);
  const tail = source.slice(start);
  const end = tail.indexOf('\n};');
  // fetchTasks 内含缩进的辅助函数，顶层结束标记仍是第一个无缩进的 };。
  return tail.slice(0, end + 3);
}
function hookSource(name) {
  const start = source.indexOf(`${name}(`);
  return source.slice(start, source.indexOf('\n});', start) + 4);
}
function component(get) {
  const request = { get };
  const sandbox = {
    taskText: (...args) => i18n.global.t(...args),
    request, taskListClient: createTaskListClient(request), applyTaskStatistics, buildTaskQueryParams,
    taskRequestVersion: 0, enterpriseRequestVersion: 0, taskStatisticsReady: false, enterpriseStatisticsReady: false,
    assetMutationVersion: { value: 0 }, lastObservedMutationVersion: 0, clearSelection() {},
    taskMetricCounts: {}, enterpriseMetricCounts: {}, enterpriseRunningCount: { value: 0 },
    activeMainTab: { value: 'enterprise' }, reconSearchForm: {}, searchForm: {},
    taskList: { value: [] }, enterpriseTaskList: { value: [] }, enterpriseTaskCache: new Map(),
    pagination: { current: 1, pageSize: 10 }, enterprisePagination: { current: 1, pageSize: 10 },
    loading: { value: false }, enterpriseLoading: { value: false }, lastRefreshTime: { value: null },
    route: { query: {} }, router: { replace() {} }, formState: {},
    domainDicts: { value: [] }, altDnsDicts: { value: [] }, fileLeakDicts: { value: [] }, portDicts: { value: [] },
    autoRefreshEnabled: { value: true }, pollingTimer: null,
    setInterval(callback, delay) { sandbox.poll = callback; sandbox.pollDelay = delay; return 1; },
    clearInterval() { sandbox.timerCleared = true; }, console: { error() {} },
    onMounted(callback) { sandbox.mounted = callback; },
    onActivated(callback) { sandbox.activated = callback; }
  };
  vm.createContext(sandbox);
  vm.runInContext([functionSource('fetchTasks'), functionSource('fetchEnterpriseTasks'),
    functionSource('stopSmartPolling'), functionSource('startSmartPolling'),
    'let firstActivation = true;', hookSource('onMounted'), hookSource('onActivated'),
    'this.fetchTasks = fetchTasks; this.fetchEnterpriseTasks = fetchEnterpriseTasks; this.startPolling = startSmartPolling;'].join('\n'), sandbox);
  return sandbox;
}

test('mount plus first KeepAlive activation loads one list with statistics; return loads once more', async () => {
  const calls = [];
  const ctx = component(async (endpoint, options) => {
    calls.push({ endpoint, options });
    return endpoint === '/dictionary/list' ? { code: 200, data: [] }
      : { code: 200, items: [], total: 9, statistics: counts };
  });
  const mounted = ctx.mounted();
  ctx.activated();
  await mounted;
  await tick();
  assert.equal(calls.filter(call => call.endpoint === '/icp/task').length, 1);
  assert.equal(ctx.enterpriseMetricCounts.running, 3);
  ctx.activated();
  await tick();
  assert.equal(calls.filter(call => call.endpoint === '/icp/task').length, 2);
});

test('manual refresh overlapping silent polling shares one request and clears loading', async () => {
  let release, calls = 0;
  const ctx = component(() => {
    calls++;
    return new Promise(resolve => { release = resolve; });
  });
  const manual = ctx.fetchTasks(1, 10);
  const poll = ctx.fetchTasks(1, 10, true);
  await tick();
  assert.equal(calls, 1);
  release({ code: 200, items: [], total: 9, statistics: counts });
  await Promise.all([manual, poll]);
  assert.equal(ctx.loading.value, false);
  assert.equal(ctx.taskMetricCounts.running, 3);
});

test('a late old page response cannot overwrite the newer page or statistics', async () => {
  const pending = new Map();
  const ctx = component((endpoint, { params }) => new Promise(resolve => { pending.set(params.page, resolve); }));
  const first = ctx.fetchTasks(1, 10);
  const second = ctx.fetchTasks(2, 10);
  await tick();
  pending.get(2)({ code: 200, items: [], total: 20, statistics: { ...counts, total: 20 } });
  await second;
  pending.get(1)({ code: 200, items: [], total: 10, statistics: { ...counts, total: 10 } });
  await first;
  assert.equal(ctx.pagination.current, 2);
  assert.equal(ctx.pagination.total, 20);
  assert.equal(ctx.taskMetricCounts.total, 20);
});

test('component retains metrics on statistics failure while accepting the new list', async () => {
  const ctx = component(async () => ({ code: 200, items: [], total: 2, statistics_error: true }));
  Object.assign(ctx.taskMetricCounts, { total: 9, running: 3, done: 4, abnormal: 2 });
  await ctx.fetchTasks(1, 10);
  assert.equal(ctx.taskMetricCounts.running, 3);
  assert.equal(ctx.pagination.total, 2);
  assert.equal(ctx.taskStatisticsReady, false);
});

test('polling retries missing initial statistics, then avoids requests once a successful result is idle', async () => {
  let calls = 0;
  const ctx = component(async () => {
    calls++;
    return { code: 200, items: [], total: 9, statistics: { ...counts, active: 0 } };
  });
  ctx.startPolling();
  await ctx.poll();
  assert.equal(calls, 1);
  assert.equal(ctx.enterpriseStatisticsReady, true);
  await ctx.poll();
  assert.equal(calls, 1);
});

test('active polling obtains the list and all metrics through one RPC', async () => {
  const calls = [];
  const ctx = component(async (endpoint, options) => {
    calls.push({ endpoint, options });
    return { code: 200, items: [], total: 9, statistics: counts };
  });
  ctx.enterpriseStatisticsReady = true;
  ctx.enterpriseMetricCounts.running = 3;
  ctx.startPolling();
  await ctx.poll();
  assert.equal(calls.length, 1);
  assert.equal(calls[0].options.params.include_statistics, 1);
});

test('component pagination skips aggregation and preserves existing global metrics', async () => {
  let params;
  const ctx = component(async (endpoint, options) => {
    params = options.params;
    return { code: 200, items: [], total: 2 };
  });
  Object.assign(ctx.taskMetricCounts, { total: 9, running: 3, done: 4, abnormal: 2 });
  await ctx.fetchTasks(2, 10, false, false);
  assert.equal('include_statistics' in params, false);
  assert.equal(ctx.pagination.current, 2);
  assert.equal(ctx.taskMetricCounts.total, 9);
});
