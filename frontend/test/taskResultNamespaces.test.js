import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { parse, compileScript } from 'vue/compiler-sfc';
import { buildAssetFilterParams } from '../src/utils/assetFilters.js';
import { i18n } from '../src/i18n/index.js';

const plain = value => JSON.parse(JSON.stringify(value));
const ref = value => ({ value });
const computed = fn => ({ get value() { return fn(); } });

function testInBothLanguages(name, run) {
  for (const locale of ['zh-CN', 'en-US']) {
    test(`${name} (${locale})`, async () => {
      i18n.global.locale.value = locale;
      try {
        await run();
      } finally {
        i18n.global.locale.value = 'zh-CN';
      }
    });
  }
}

function fixture(tab, task = 'task-a') {
  const file = new URL('../src/views/TaskDetail.vue', import.meta.url);
  const { descriptor } = parse(fs.readFileSync(file, 'utf8'));
  const { scriptSetupAst } = compileScript(descriptor, { id: 'TaskDetail' });
  const bindings = {};
  for (const node of scriptSetupAst) {
    if (node.type !== 'VariableDeclaration') continue;
    for (const item of node.declarations) {
      if (item.id.type === 'Identifier' && item.init) {
        bindings[item.id.name] = descriptor.scriptSetup.content.slice(item.init.start, item.init.end);
      }
    }
  }
  const calls = [], confirmations = [], notices = [];
  const context = vm.createContext({
    reactive: value => value, computed, buildAssetFilterParams,
    taskText: (...args) => i18n.global.t(...args),
    activeTab: ref(tab), taskId: ref(task), serviceEngineType: ref('nmap'),
    searchForm: ref(tab === 'url' ? { status_code: ['403', '200'], title: 'admin' } : {}),
    pagination: { current: 2, pageSize: 20, total: 0 }, loading: ref(false),
    dataSource: ref([]), selectedRowKeys: ref(['selected-id']), hasSelected: ref(true),
    selectionTracker: { rememberRows() {}, syncSelection() {}, getLabels: keys => keys, clear() {} },
    buildSelectionConfirmContent: options => options,
    getAssetRecordDisplayLabel: (_tab, row) => row?._id || row?.name || '',
    clearSelection() { context.selectedRowKeys.value = []; },
    assetMutationVersion: ref(0),
    notifyAssetMutated() {},
    lastObservedMutationVersion: 0,
    fetchTaskStats() {},
    lastFetchedPage: 1, lastFetchedSize: 20,
    tabCache: { updateMemoryCache() {}, saveCurrentTab() {}, invalidateMemoryCache() {}, invalidateAllMemoryCaches() {} },
    request: {
      async get(url, options) { calls.push({ method: 'GET', url, ...plain(options) }); return { code: 200, items: [], total: 0 }; },
      async post(url, body) { calls.push({ method: 'POST', url, body: plain(body) }); return { code: 200 }; }
    },
    Modal: { confirm: options => confirmations.push(options) },
    createVNode() {}, ExclamationCircleOutlined: {},
    message: Object.fromEntries(['loading', 'success', 'error', 'warning'].map(key => [key, value => notices.push({ key, value })])),
    Blob, console, window: { URL: { createObjectURL: () => 'fixture', revokeObjectURL() {} } },
    document: { createElement: () => ({ click() {} }), body: { appendChild() {}, removeChild() {} } }
  });
  for (const name of ['tabConfig', 'resolveAssetEndpoint', 'effectiveTab', 'canDeleteAssets', 'canSelectAssets', 'getAssetRowKey', 'fetchData', 'handleExport', 'handleBatchDelete']) {
    vm.runInContext(`var ${name} = ${bindings[name]};`, context);
  }
  return { context, descriptor, calls, confirmations, notices,
    invoke: name => vm.runInContext(`${name}()`, context) };
}

for (const tab of ['url', 'cip', 'stat_finger']) {
  testInBothLanguages(`${tab} task detail fetches task results and retains task scope`, async () => {
    const page = fixture(tab);
    await page.invoke('fetchData');
    assert.equal(page.calls[0].url, `/${tab}/`);
    assert.equal(page.calls[0].params.task_id, 'task-a');
    assert.equal(page.calls[0].params.page, 2);
  });
}

for (const tab of ['url', 'cip']) {
  testInBothLanguages(`${tab} list, export and confirmed delete use the same task namespace`, async () => {
    const page = fixture(tab);
    await page.invoke('fetchData');
    await page.invoke('handleExport');
    page.context.selectedRowKeys.value = ['selected-id'];
    page.invoke('handleBatchDelete');
    assert.equal(page.calls.length, 2, 'Deletion must wait for confirmation');
    await page.confirmations[0].onOk();
    assert.deepEqual(page.calls.slice(0, 3).map(call => call.url), [`/${tab}/`, `/${tab}/export/`, `/${tab}/delete/`]);
    assert.equal(page.calls[1].params.task_id, 'task-a');
    assert.deepEqual(page.calls[2].body, { _id: ['selected-id'], task_id: 'task-a', source_type: 'task' });
    assert.ok(page.calls.every(call => !call.url.startsWith('/asset_') && !call.url.startsWith('/site/')));
  });
}

testInBothLanguages('URL export preserves the list status and title filters', async () => {
  const page = fixture('url');
  await page.invoke('fetchData');
  await page.invoke('handleExport');
  for (const call of page.calls) {
    assert.equal(call.params.status_code__in, '200,403');
    assert.equal(call.params.title, 'admin');
    assert.equal(call.params.task_id, 'task-a');
  }
});

testInBothLanguages('global URL, C-segment and fingerprint views read asset-group collections without task scope', async () => {
  const expected = { url: '/asset_url/', cip: '/asset_cip/', stat_finger: '/asset_stat_finger/' };
  for (const [tab, endpoint] of Object.entries(expected)) {
    const page = fixture(tab, '');
    await page.invoke('fetchData');
    assert.equal(page.calls[0].url, endpoint);
    assert.ok(!('task_id' in page.calls[0].params));
    assert.equal(page.context.canDeleteAssets.value, false);
    assert.equal(page.context.canSelectAssets.value, false);
    page.invoke('handleBatchDelete');
    assert.equal(page.confirmations.length, 0);
    assert.equal(page.calls.length, 1);
  }
  const exportPage = fixture('url', '');
  await exportPage.invoke('handleExport');
  assert.equal(exportPage.calls[0].url, '/url/export/');
});

testInBothLanguages('task fingerprint statistics have stable keys and support scoped deletion while global view stays read-only', async () => {
  const page = fixture('stat_finger');
  assert.equal(page.context.canDeleteAssets.value, true);
  assert.equal(page.context.canSelectAssets.value, true);
  assert.equal(page.context.getAssetRowKey({ name: 'nginx', cnt: 3 }), 'nginx');
  assert.equal(page.context.getAssetRowKey({ _id: 'real-id', name: 'nginx' }), 'real-id');
  page.invoke('handleBatchDelete');
  assert.equal(page.confirmations.length, 1);
  await page.confirmations[0].onOk();
  assert.equal(page.calls.length, 2);
  assert.equal(page.calls[0].url, '/stat_finger/delete/');
  assert.deepEqual(page.calls[0].body, {
    _id: ['selected-id'],
    name: ['selected-id'],
    task_id: 'task-a',
    source_type: 'task',
  });
  assert.ok(page.descriptor.template.content.includes('v-if="canDeleteAssets"'));
  assert.ok(page.descriptor.template.content.includes(':row-selection="canSelectAssets ?'));

  const globalPage = fixture('stat_finger', '');
  assert.equal(globalPage.context.canDeleteAssets.value, false);
  globalPage.invoke('handleBatchDelete');
  assert.equal(globalPage.confirmations.length, 0);
  assert.equal(globalPage.calls.length, 0);
  assert.ok(globalPage.notices.some(notice => notice.key === 'warning'));
});

testInBothLanguages('switching back to a deletable tab restores selection and deletion capability', () => {
  const page = fixture('stat_finger');
  page.context.activeTab.value = 'url';
  assert.equal(page.context.canDeleteAssets.value, true);
  page.invoke('handleBatchDelete');
  assert.equal(page.confirmations.length, 1);
});

testInBothLanguages('global C-segment aggregation is read-only; task C-segment records remain deletable', () => {
  const page = fixture('cip', '');
  assert.equal(page.context.canDeleteAssets.value, false);
  page.invoke('handleBatchDelete');
  assert.equal(page.confirmations.length, 0);
  assert.equal(page.calls.length, 0);
  page.context.taskId.value = 'task-a';
  assert.equal(page.context.canDeleteAssets.value, true);
});
