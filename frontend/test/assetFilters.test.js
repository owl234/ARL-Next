import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { parse, compileScript } from 'vue/compiler-sfc';
import { computed, ref } from 'vue';
import dayjs from 'dayjs';
import { i18n } from '../src/i18n/index.js';
import { buildAssetFilterParams, normalizeHttpStatuses } from '../src/utils/assetFilters.js';
import { serializeSearchForm, deserializeSearchForm } from '../src/utils/useTabStateCache.js';

const statusFields = [{ key: 'status', type: 'httpStatus' }, { key: 'title' }];
const plain = value => JSON.parse(JSON.stringify(value));
const taskText = (...args) => i18n.global.t(...args);

function sourceBindings(file) {
  const source = fs.readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8');
  const { descriptor } = parse(source);
  const { scriptSetupAst } = compileScript(descriptor, { id: file });
  const bindings = {};
  for (const node of scriptSetupAst) {
    if (node.type === 'VariableDeclaration') {
      for (const item of node.declarations) {
        if (item.id.type === 'Identifier' && item.init) bindings[item.id.name] = descriptor.scriptSetup.content.slice(item.init.start, item.init.end);
      }
    }
  }
  return { bindings, descriptor };
}

function pageFixture(name, tab = 'site') {
  const { bindings } = sourceBindings(`views/${name}.vue`);
  const calls = [];
  const notices = [];
  const context = vm.createContext({
    reactive: value => value, computed, buildAssetFilterParams, taskText, assetText: taskText,
    serviceEngineType: ref('nmap'), columns: ref([]), lastFetchedPage: 1, lastFetchedSize: 20,
    activeTab: ref(tab), searchForm: ref(tab === 'site' ? { status: ['403', '200'], title: 'admin' } : { status_code: ['403', '200'], title: 'admin' }),
    pagination: { current: 2, pageSize: 20, total: 2 }, taskId: ref('task-a'), scope_id: ref('scope-a'), targetName: ref('fixture'),
    loading: ref(false), dataSource: ref([]), selectedRowKeys: ref([]), hasSelected: ref(false), asmCounts: {},
    selectionTracker: { rememberRows() {}, syncSelection() {}, getLabels: () => [], clear() {} },
    getAssetRowKey: r => r?._id || r?.id,
    getAssetRecordDisplayLabel: () => '',
    tabCache: { updateMemoryCache() {}, saveCurrentTab() {}, resetTabState() {},
      getTabSearchForm: () => ({}), applyTabOperators() {}, getTabPage: () => 1, getMemoryCache: () => null },
    request: { async get(url, options) {
      calls.push({ url, ...plain(options) });
      if (url === '/policy/') return { code: 200, items: [] };
      if (url.includes('save_result_set')) return { code: 200, data: { result_set_id: 'result-a', result_total: 2 } };
      return { code: 200, items: [{ _id: '1' }], total: 2 };
    } },
    message: Object.fromEntries(['loading', 'success', 'error', 'warning'].map(key => [key, value => notices.push({ key, value })])),
    Blob, console, window: { URL: { createObjectURL: () => 'fixture', revokeObjectURL() {} } },
    document: { createElement: () => ({ click() {} }), body: { appendChild() {}, removeChild() {} } },
    riskForm: {}, policyOptions: ref([]), policies: ref([{}]), currentResultSetId: ref(''), targetCount: ref(2),
    riskVisible: ref(false), selectedRiskTargets: ref([]), currentTargetCount: ref(0), riskModalVisible: ref(false)
  });
  vm.runInContext(`var tabConfig = ${bindings.tabConfig};`, context);
  vm.runInContext(`var resolveAssetEndpoint = ${bindings.resolveAssetEndpoint};`, context);
  vm.runInContext(`var effectiveTab = ${bindings.effectiveTab};`, context);
  vm.runInContext(`var fetchData = ${bindings.fetchData};`, context);
  const invoke = async name => {
    assert.ok(bindings[name], `Missing original function: ${name}`);
    return await vm.runInContext(`(${bindings[name]})()`, context);
  };
  return { context, calls, notices, invoke };
}

test('legacy scalar, comma-delimited route query and cached arrays normalize identically', () => {
  assert.deepEqual(normalizeHttpStatuses(200), ['200']);
  assert.deepEqual(normalizeHttpStatuses('200'), ['200']);
  assert.deepEqual(normalizeHttpStatuses(['200,403', 200]), ['200', '403']);
  assert.deepEqual(buildAssetFilterParams({ status: '403,200' }, statusFields), { status__in: '200,403' });
});

test('empty and cleared selections omit status condition', () => {
  for (const value of [undefined, null, '', []]) {
    assert.deepEqual(buildAssetFilterParams({ status: value, title: 'admin' }, statusFields), { title: 'admin' });
  }
});

test('invalid selections fail without discarding the filter', () => {
  for (const value of ['600', '99', '200,', '2e2', ['200', 'invalid'], ['200', null]]) {
    assert.throws(() => buildAssetFilterParams({ status: value }, statusFields), /100 到 599/);
  }
});

test('all numeric HTTP codes remain selectable, with duplicates removed', () => {
  const codes = Array.from({ length: 500 }, (_, i) => i + 100);
  assert.equal(buildAssetFilterParams({ status: codes }, statusFields).status__in.split(',').length, 500);
  assert.equal(buildAssetFilterParams({ status: [200, '200', 403] }, statusFields).status__in, '200,403');
});

test('operator and date conditions coexist and fields from another tab are excluded', () => {
  const fields = [...statusFields, { key: 'finger', hasOperatorSelect: true, operator: '精确匹配' },
    { key: 'update_date', type: 'dateRange' }, { key: 'length', hasOperatorSelect: true, operator: '大于' }];
  const params = buildAssetFilterParams({ status: [200, 403], finger: 'nginx', length: 123,
    update_date: [dayjs('2026-10-01'), dayjs('2026-10-12')], unrelated: 'ignore' }, fields);
  assert.deepEqual(params, { status__in: '200,403', finger__eq: 'nginx', length__gt: 123,
    update_date__dgt: '2026-10-01 00:00:00', update_date__dlt: '2026-10-12 00:00:00' });
});

test('tab cache round trip preserves multiselect and date filters', () => {
  const fields = [...statusFields, { key: 'update_date', type: 'dateRange' }];
  const form = { status: ['200', '403'], title: 'admin', update_date: [dayjs('2026-10-01'), dayjs('2026-10-12')] };
  assert.deepEqual(buildAssetFilterParams(deserializeSearchForm(serializeSearchForm(form), fields), fields), buildAssetFilterParams(form, fields));
  assert.deepEqual(buildAssetFilterParams(deserializeSearchForm({ status: 200 }, fields), fields), { status__in: '200' });
});

test('shared control normalizes old values and emits selection update before search', () => {
  const { bindings, descriptor } = sourceBindings('components/HttpStatusFilter.vue');
  const events = [];
  const context = vm.createContext({ normalizeHttpStatuses, computed, taskText, props: { value: 200 }, emit: (...args) => events.push(plain(args)) });
  for (const key of ['selectedCodes', 'descriptionKeys', 'options', 'onChange']) {
    vm.runInContext(`var ${key} = ${bindings[key]};`, context);
  }
  assert.deepEqual(plain(context.selectedCodes.value), ['200']);
  assert.equal(context.options.value.length, 500);
  assert.match(descriptor.template.content, /mode="multiple"/);
  assert.match(descriptor.template.content, /show-search/);
  context.onChange(['403', '200']);
  assert.deepEqual(events, [['update:value', ['403', '200']], ['change', ['403', '200']]]);
  context.onChange(undefined);
  assert.deepEqual(events.slice(-2), [['update:value', []], ['change', []]]);
});

for (const name of ['AssetSearch', 'TaskDetail', 'GroupAssetsDetail']) {
  test(`${name}: original list, export and result-set functions preserve the same status filter and scope`, async () => {
    const fixture = pageFixture(name);
    for (const fn of ['fetchData', 'handleExport', 'openRiskModal']) await fixture.invoke(fn);
    const relevant = fixture.calls.filter(call => call.url !== '/policy/');
    assert.equal(relevant.length, 3, JSON.stringify(fixture.notices));
    for (const call of relevant) {
      assert.equal(call.params.status__in, '200,403');
      assert.equal(call.params.title, 'admin');
      assert.ok(!('status' in call.params));
      if (name === 'TaskDetail') assert.equal(call.params.task_id, 'task-a');
      if (name === 'GroupAssetsDetail') assert.equal(call.params.scope_id, 'scope-a');
    }
    assert.equal(fixture.notices.filter(item => item.key === 'error').length, 0);
  });

  for (const tab of ['url', 'fileleak']) {
    test(`${name}: original ${tab} list sends numeric membership, not an array query parameter`, async () => {
      const fixture = pageFixture(name, tab);
      await fixture.invoke('fetchData');
      assert.equal(fixture.calls.length, 1, JSON.stringify(fixture.notices));
      assert.equal(fixture.calls[0].params.status_code__in, '200,403');
      assert.ok(!('status_code' in fixture.calls[0].params));
      assert.equal(fixture.notices.filter(item => item.key === 'error').length, 0);
    });
  }
}

for (const name of ['AssetSearch', 'TaskDetail', 'GroupAssetsDetail']) {
  test(`${name}: selection searches from page one, pagination retains status, and reset clears it`, async () => {
    const fixture = pageFixture(name);
    await fixture.invoke('onSearch');
    assert.equal(fixture.context.pagination.current, 1);
    assert.equal(fixture.calls[0].params.status__in, '200,403');
    fixture.context.pagination.current = 3;
    await fixture.invoke('fetchData');
    assert.equal(fixture.calls[1].params.page, 3);
    assert.equal(fixture.calls[1].params.status__in, '200,403');
    await fixture.invoke('resetSearch');
    assert.equal(fixture.context.pagination.current, 1);
    assert.ok(!('status__in' in fixture.calls[2].params));
    assert.equal(fixture.notices.filter(item => item.key === 'error').length, 0);
  });
}

for (const name of ['AssetSearch', 'TaskDetail', 'GroupAssetsDetail']) {
  test(`${name}: invalid status selection stops the original list function before an HTTP request`, async () => {
    const fixture = pageFixture(name);
    fixture.context.searchForm.value.status = ['200', 'invalid'];
    await fixture.invoke('fetchData');
    assert.equal(fixture.calls.length, 0);
    assert.equal(fixture.notices.filter(item => item.key === 'error').length, 1);
  });
}

for (const name of ['AssetSearch', 'TaskDetail', 'GroupAssetsDetail']) {
  test(`${name}: unified service tab supports endpoint filters, source filter and service export`, async () => {
    const fixture = pageFixture(name, 'service');
    fixture.context.searchForm.value = {
      service_name: 'redis',
      ip: '192.0.2.1',
      port_id: '6379',
      product: 'Redis',
      version: '7.0',
      sources: 'npoc',
      unrelated: 'ignored'
    };
    fixture.context.pagination.current = 2;
    await fixture.invoke('fetchData');
    assert.equal(fixture.calls[0].url, fixture.context.tabConfig.service.url);
    assert.equal(fixture.calls[0].params.service_name, 'redis');
    assert.equal(fixture.calls[0].params.ip, '192.0.2.1');
    assert.equal(fixture.calls[0].params.port_id, '6379');
    assert.equal(fixture.calls[0].params.product, 'Redis');
    assert.equal(fixture.calls[0].params.version, '7.0');
    assert.equal(fixture.calls[0].params.sources, 'npoc');
    assert.equal(fixture.calls[0].params.page, 2);
    assert.ok(!('unrelated' in fixture.calls[0].params));

    await fixture.invoke('handleExport');
    assert.equal(fixture.calls[1].url, fixture.context.tabConfig.service.exportUrl);
    assert.equal(fixture.calls[1].params.service_name, 'redis');
    assert.equal(fixture.calls[1].params.sources, 'npoc');
    assert.equal(fixture.notices.filter(item => item.key === 'error').length, 0);
  });

  test(`${name}: a response from a previous tab cannot replace the current tab data`, async () => {
    const fixture = pageFixture(name, 'service');
    let finishOld;
    fixture.context.request.get = url => url === fixture.context.tabConfig.service.url
      ? new Promise(resolve => { finishOld = resolve; })
      : Promise.resolve({ code: 200, total: 1, items: [{ id: 'current-tab' }] });
    const oldRequest = fixture.invoke('fetchData');
    fixture.context.activeTab.value = 'domain';
    await fixture.invoke('fetchData');
    finishOld({ code: 200, total: 9, items: [{ id: 'old-tab' }] });
    await oldRequest;
    assert.deepEqual(plain(fixture.context.dataSource.value), [{ id: 'current-tab' }]);
    assert.equal(fixture.context.pagination.total, 1);
  });
}
