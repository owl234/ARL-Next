import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { parse, compileScript } from 'vue/compiler-sfc';
import { createAssetScopeLoader, getTaskAssetGroupState, hasSyncSummary } from '../src/utils/taskAssetGroups.js';
import { i18n } from '../src/i18n/index.js';

const state = () => ({ search: '', page: 1, options: [], loading: false, hasMore: true });
const plain = value => JSON.parse(JSON.stringify(value));
const deferred = () => { let resolve; const promise = new Promise(value => { resolve = value; }); return { promise, resolve }; };

function bindings(file) {
  const { descriptor } = parse(fs.readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8'));
  const { scriptSetupAst } = compileScript(descriptor, { id: file });
  const result = {};
  for (const node of scriptSetupAst) {
    if (node.type === 'VariableDeclaration') {
      for (const item of node.declarations) {
        if (item.id.type === 'Identifier' && item.init) result[item.id.name] = descriptor.scriptSetup.content.slice(item.init.start, item.init.end);
      }
    }
  }
  return { result, descriptor };
}

test('remote group loader supports search and successive pages beyond the first fifty', async () => {
  const calls = [];
  const fixture = state();
  const loader = createAssetScopeLoader({ async get(url, options) {
    calls.push({ url, ...options });
    const page = options.params.page;
    return { code: 200, total: 51, items: Array.from({ length: page === 1 ? 50 : 1 }, (_, i) => ({ _id: String(i + (page - 1) * 50), name: `Group ${i}` })) };
  } }, fixture);
  await loader.load(true, 'business');
  assert.equal(fixture.hasMore, true);
  await loader.load();
  assert.equal(fixture.options.length, 51);
  assert.equal(fixture.hasMore, false);
  await loader.load();
  assert.equal(calls.length, 2);
  assert.equal(calls[0].params.name, 'business');
  assert.equal(calls[1].params.page, 2);
  assert.equal(calls[0].params.size, 50);
});

test('stale remote search response cannot replace newer options or loading state', async () => {
  const first = deferred(), second = deferred();
  let count = 0;
  const fixture = state();
  const loader = createAssetScopeLoader({ get: () => ++count === 1 ? first.promise : second.promise }, fixture);
  const old = loader.load(true, 'old');
  const current = loader.load(true, 'new');
  first.resolve({ code: 200, total: 1, items: [{ _id: 'old', name: 'Old group' }] });
  await old;
  assert.equal(fixture.loading, true);
  assert.deepEqual(fixture.options, []);
  second.resolve({ code: 200, total: 1, items: [{ _id: 'new', name: 'New group' }] });
  await current;
  assert.equal(fixture.options[0].value, 'new');
  assert.equal(fixture.loading, false);
});

test('load failure preserves page for retry and reports business errors', async () => {
  let count = 0;
  const errors = [];
  const fixture = state();
  const loader = createAssetScopeLoader({ get: async () => ++count === 1 ? { code: 500, data: { error: 'fixture unavailable' } } : { code: 200, total: 0, items: [] } }, fixture, error => errors.push(error.message));
  await loader.load(true);
  assert.equal(fixture.page, 1);
  assert.equal(fixture.loading, false);
  assert.deepEqual(errors, ['fixture unavailable']);
  await loader.load();
  assert.equal(fixture.page, 2);
  assert.equal(fixture.hasMore, false);
});

test('concurrent scroll events request one page and disposal ignores pending results', async () => {
  const pending = deferred();
  let calls = 0;
  const fixture = state();
  const loader = createAssetScopeLoader({ get: () => { calls++; return pending.promise; } }, fixture);
  const request = loader.load(true);
  await loader.load();
  assert.equal(calls, 1);
  loader.dispose();
  pending.resolve({ code: 200, total: 1, items: [{ _id: 'late', name: 'Late group' }] });
  await request;
  assert.deepEqual(fixture.options, []);
});

test('selected group is pending until synchronization completes', () => {
  const task = { status: 'waiting', options: { related_scope_id: 'group-a' }, related_scope_name: 'A' };
  assert.equal(getTaskAssetGroupState(task).text, '完成后同步');
  assert.equal(getTaskAssetGroupState({ ...task, status: 'stop' }).text, '未同步');
  assert.equal(getTaskAssetGroupState({ ...task, sync_status: 'running' }).text, '同步中');
  assert.equal(getTaskAssetGroupState({ ...task, sync_status: 'waiting' }).text, '等待同步');
  assert.equal(getTaskAssetGroupState({ ...task, synced_scope_id: 'group-a', synced_scope_name: 'New name' }).text, '已同步');
});

test('failed attempt takes priority over an earlier completed sync and exposes reason', () => {
  const task = { options: { related_scope_id: 'group-a' }, synced_scope_id: 'group-a',
    sync_status: 'error', sync_error: 'group no longer exists', related_scope_name: 'A' };
  assert.equal(getTaskAssetGroupState(task).text, '同步失败');
  assert.equal(getTaskAssetGroupState(task).error, 'group no longer exists');
  assert.equal(getTaskAssetGroupState({ options: {} }), null);
  assert.equal(getTaskAssetGroupState({ synced_scope_id: 'group-b', synced_scope_name: 'B' }).label, 'B');
});

function taskPage(response = { code: 200 }) {
  const { result, descriptor } = bindings('views/TaskList.vue');
  const calls = [], messages = [];
  const context = vm.createContext({
    taskText: (...args) => i18n.global.t(...args),
    formRef: { value: { validate: async () => {} } }, formState: { name: 'fixture', target: 'example.com', related_scope_id: 'group-a', service_detection: true, port_scan: true },
    submitLoading: { value: false }, visible: { value: true }, pagination: { current: 2, pageSize: 20 },
    request: { post: async (url, payload) => { calls.push({ url, payload: plain(payload) }); return response; } },
    message: Object.fromEntries(['error', 'success', 'warning'].map(name => [name, value => messages.push({ name, value })])),
    fetchTasks() {}, fetchTaskMetricCounts() {}, syncFormState: { scope_id: undefined },
    currentSyncRecord: { value: null }, syncVisible: { value: false }, syncLoading: { value: false },
    // handleOk 现由「表单校验 + 多任务二次确认」与 doSubmitTask 两部分组成，这里补齐其依赖
    fanoutHint: { value: { taskCount: 1, text: '' } }, Modal: { confirm: () => {} },
    createVNode: () => ({}), ExclamationCircleOutlined: {}
  });
  return { calls, messages, context, descriptor, invoke: name => vm.runInContext(`(${result[name]})()`, context),
    sync: record => vm.runInContext(`(${result.syncTask})(${JSON.stringify(record)})`, context) };
}

test('original task submission sends selected group and preserves scanning options, then clears group after success', async () => {
  const fixture = taskPage();
  await fixture.invoke('doSubmitTask');
  assert.equal(fixture.calls[0].url, '/task/');
  assert.equal(fixture.calls[0].payload.related_scope_id, 'group-a');
  assert.equal(fixture.calls[0].payload.port_scan, true);
  assert.equal(fixture.calls[0].payload.npoc_service_detection, true);
  assert.equal(fixture.context.formState.related_scope_id, undefined);
  assert.equal(fixture.context.submitLoading.value, false);
  assert.equal(fixture.context.visible.value, false);
});

test('original task submission displays out-of-scope detail and keeps selection on failure', async () => {
  const fixture = taskPage({ code: 500, message: 'generic', data: { error: 'outside.org 不在范围中' } });
  await fixture.invoke('doSubmitTask');
  assert.equal(fixture.context.formState.related_scope_id, 'group-a');
  assert.equal(fixture.context.visible.value, true);
  assert.ok(fixture.messages.some(message => message.value.includes('outside.org')));
});

test('cleared group retains unassociated submission', async () => {
  const fixture = taskPage();
  fixture.context.formState.related_scope_id = undefined;
  await fixture.invoke('doSubmitTask');
  assert.ok(!('related_scope_id' in fixture.calls[0].payload));
});

test('manual retry defaults to the associated group and shows server error details', async () => {
  const fixture = taskPage({ code: 500, data: { error: 'group removed' } });
  fixture.sync({ _id: 'task-a', options: { related_scope_id: 'group-a' } });
  assert.equal(fixture.context.syncFormState.scope_id, 'group-a');
  await fixture.invoke('handleSyncOk');
  assert.equal(fixture.calls[0].payload.scope_id, 'group-a');
  assert.ok(fixture.messages.some(message => message.value.includes('group removed')));
});

test('shared selector retains selected label while searching another page and clearing removes it', () => {
  const { result } = bindings('components/AssetScopeSelect.vue');
  const events = [];
  const context = vm.createContext({
    state: { options: [{ value: 'group-a', label: 'A' }] }, selectedOption: { value: null }, emit: (...args) => events.push(plain(args)),
    computed: fn => ({ get value() { return fn(); } })
  });
  vm.runInContext(`var options = ${result.options}; var onChange = ${result.onChange};`, context);
  context.onChange('group-a');
  context.state.options = [{ value: 'group-b', label: 'B' }];
  assert.deepEqual(plain(context.options.value), [{ value: 'group-a', label: 'A' }, { value: 'group-b', label: 'B' }]);
  context.onChange(undefined);
  assert.equal(context.selectedOption.value, null);
  assert.equal(events[0][0], 'update:value');
  assert.equal(events[0][1], 'group-a');
});

test('hasSyncSummary hides stale badges while sync is waiting, running, or failed', () => {
  const withSummary = { sync_summary: { total_new: 2, total_update: 1 } };
  assert.equal(hasSyncSummary(withSummary), true);
  assert.equal(hasSyncSummary({ ...withSummary, sync_status: 'default' }), true);
  assert.equal(hasSyncSummary({ sync_summary: { total_new: 0, total_update: 0 }, sync_status: 'default' }), false);
  for (const sync_status of ['waiting', 'running', 'error']) {
    assert.equal(hasSyncSummary({ ...withSummary, sync_status }), false);
  }
});

test('App.vue sets --arl-text-secondary once without overwriting it later', () => {
  const source = fs.readFileSync(new URL('../src/App.vue', import.meta.url), 'utf8');
  const matches = source.match(/--arl-text-secondary/g) || [];
  assert.equal(matches.length, 1);
  assert.ok(source.includes("root.style.setProperty('--arl-text-secondary', isDark ? 'rgba(255, 255, 255, 0.65)' : '#64748b');"));
});
