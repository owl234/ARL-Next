import assert from 'node:assert/strict';
import fs from 'node:fs';
import test, { afterEach } from 'node:test';
import vm from 'node:vm';
import { computed, reactive, ref } from 'vue';
import { parse, compileScript, babelParse } from 'vue/compiler-sfc';
import { i18n } from '../src/i18n/index.js';
import zh from '../src/i18n/zh-CN.js';
import en from '../src/i18n/en-US.js';
import { buildAssetFilterParams, formatAssetFilterOperator } from '../src/utils/assetFilters.js';
import { buildEnterpriseOsintColumns } from '../src/utils/enterpriseOsint.js';
import { formatTaskStatus } from '../src/constants/taskStatus.js';

const assetText = (...args) => i18n.global.t(...args);
const plain = value => JSON.parse(JSON.stringify(value));
afterEach(() => { i18n.global.locale.value = 'zh-CN'; });
const sources = new Map();
function component(file, initial = {}) {
  if (!sources.has(file)) {
    const { descriptor } = parse(fs.readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8'));
    const { scriptSetupAst } = compileScript(descriptor, { id: file });
    const bindings = {};
    for (const node of scriptSetupAst) {
      if (node.type !== 'VariableDeclaration') continue;
      for (const item of node.declarations) {
        if (item.id.type === 'Identifier' && item.init) bindings[item.id.name] = descriptor.scriptSetup.content.slice(item.init.start, item.init.end);
      }
    }
    sources.set(file, { bindings, descriptor });
  }
  const { bindings, descriptor } = sources.get(file);
  const context = vm.createContext({ assetText, computed, reactive, ref, console, ...initial });
  return {
    context, descriptor,
    read(name) {
      assert.ok(bindings[name], `${file}: ${name}`);
      vm.runInContext(`globalThis.${name} = ${bindings[name]}`, context);
      return context[name];
    },
  };
}

test('资产语言包可完整渲染，保留全部插值数据，英文文案没有遗漏中文', () => {
  for (const [locale, messages] of [['zh-CN', zh.assets], ['en-US', en.assets]]) {
    i18n.global.locale.value = locale;
    for (const [key, message] of Object.entries(messages)) {
      const params = Object.fromEntries([...message.matchAll(/\{(\w+)\}/g)].map(([, name]) => [name, `fixture_${name}`]));
      const text = assetText(`assets.${key}`, params);
      assert.notEqual(text, `assets.${key}`, key);
      for (const value of Object.values(params)) assert.ok(text.includes(value), `${locale}: ${key}`);
      if (locale === 'en-US') assert.doesNotMatch(text, /\p{Script=Han}/u, key);
    }
  }
});

test('资产页面和抽屉引用的消息与具名参数在中英文语言包中均存在', () => {
  for (const file of ['views/AssetScope.vue', 'views/GroupAssetsDetail.vue', 'views/AssetSearch.vue',
    'components/EnterpriseOsintPanel.vue', 'components/ChainDrawer.vue', 'components/RawDataDrawer.vue']) {
    const { descriptor } = component(file);
    const check = node => {
      if (!node || typeof node !== 'object') return;
      if (node.type === 'CallExpression' && node.callee.name === 'assetText' && node.arguments[0].type === 'StringLiteral') {
        const key = node.arguments[0].value;
        for (const messages of [zh, en]) assert.equal(typeof key.split('.').reduce((value, part) => value?.[part], messages), 'string', `${file}: ${key}`);
        const message = key.split('.').reduce((value, part) => value[part], en);
        const expected = [...new Set([...message.matchAll(/\{(\w+)\}/g)].map(([, name]) => name))].sort();
        const actual = (node.arguments[1]?.properties || []).map(property => property.key.name).sort();
        assert.deepEqual(actual, expected, `${file}: ${key}`);
      }
      for (const [key, value] of Object.entries(node)) {
        if (['loc', 'comments', 'leadingComments', 'trailingComments'].includes(key)) continue;
        if (Array.isArray(value)) value.forEach(check);
        else if (value && typeof value === 'object') check(value);
      }
    };
    check(babelParse(descriptor.scriptSetup.content, { sourceType: 'module' }));
    const template = node => {
      if (node.type === 4 && !node.isStatic) {
        if (node.content.includes('assetText(')) check(babelParse(`(${node.content})`, { sourceType: 'module' }));
        return;
      }
      for (const child of [...(node.children || []), ...(node.props || [])]) template(child);
      if (node.exp) template(node.exp);
      if (node.type === 5) template(node.content);
    };
    template(descriptor.template.ast);
  }
});

test('已创建的资产列和分类选项随语言变化，数据字段和分类标识保持一致', () => {
  const cases = [
    ['views/AssetScope.vue', 'columns'], ['views/AssetScope.vue', 'icpImportColumns'],
    ['views/AssetSearch.vue', 'assetTabList'], ['views/GroupAssetsDetail.vue', 'asmTabList'],
    ['components/ChainDrawer.vue', 'domainCols'], ['components/EnterpriseOsintPanel.vue', 'osintTabList'],
  ];
  for (const [file, name] of cases) {
    i18n.global.locale.value = 'zh-CN';
    const value = component(file, { activeGroupId: ref('all') }).read(name);
    const rows = computed(() => Array.isArray(value) ? value : value.value);
    const labels = computed(() => rows.value.map(row => row.title || row.label));
    const chinese = labels.value;
    const fields = plain(rows.value.map(({ key, dataIndex }) => ({ key, dataIndex })));
    i18n.global.locale.value = 'en-US';
    assert.notDeepEqual(labels.value, chinese, file);
    assert.deepEqual(plain(rows.value.map(({ key, dataIndex }) => ({ key, dataIndex }))), fields);
    i18n.global.locale.value = 'zh-CN';
    assert.deepEqual(labels.value, chinese, file);
  }
  const dynamicColumns = component('components/EnterpriseOsintPanel.vue', {
    buildEnterpriseOsintColumns,
    activeTab: ref('invest'),
    assetList: ref([]),
  }).read('dynamicColumns');
  const titles = computed(() => dynamicColumns.value.map(column => column.title));
  const chinese = titles.value;
  i18n.global.locale.value = 'en-US';
  assert.notDeepEqual(titles.value, chinese);
});

test('资产搜索与组内筛选切换语言后保留运算符值和查询条件', () => {
  for (const file of ['views/AssetSearch.vue', 'views/GroupAssetsDetail.vue']) {
    const config = component(file).read('tabConfig');
    const field = config.stat_finger.searchFields.find(field => field.key === 'name');
    field.operator = '精确匹配';
    i18n.global.locale.value = 'zh-CN';
    const chinese = plain(buildAssetFilterParams({ name: '用户指纹' }, config.stat_finger.searchFields));
    i18n.global.locale.value = 'en-US';
    assert.equal(formatAssetFilterOperator(field.operator), 'Exact match');
    assert.equal(field.operator, '精确匹配');
    assert.deepEqual(plain(buildAssetFilterParams({ name: '用户指纹' }, config.stat_finger.searchFields)), chinese);
    assert.deepEqual(chinese, { name__eq: '用户指纹' });
    assert.ok(config.site.searchFields.some(field => field.type === 'httpStatus'));
  }
});

test('企业状态与发现进度无需重新请求即可切换语言，用户名称和路由数据保持原样', () => {
  const fixture = component('views/GroupAssetsDetail.vue', {
    boundTaskRecord: ref({ task_type: 'tyc', status: 'done' }), boundIcpTaskId: ref('task-a'), formatTaskStatus,
    route: { query: { scope_id: 'scope-a', targetName: '用户资产组' } }, scopeEnterpriseName: ref(''),
  });
  const type = fixture.read('taskTypeLabel'), status = fixture.read('taskStatusLabel'), name = fixture.read('targetName');
  assert.equal(status.value, '已完成');
  const chineseType = type.value;
  const progress = component('views/AssetScope.vue').read('wizardLoadingTip');
  const chineseProgress = progress.value;
  i18n.global.locale.value = 'en-US';
  assert.equal(status.value, 'Completed');
  assert.notEqual(type.value, chineseType);
  assert.notEqual(progress.value, chineseProgress);
  assert.equal(name.value, '用户资产组');
  assert.deepEqual(fixture.context.route.query, { scope_id: 'scope-a', targetName: '用户资产组' });
});

test('中英文全库搜索与组内搜索的原加载和导出函数保持相同筛选及资产范围', async () => {
  for (const file of ['views/AssetSearch.vue', 'views/GroupAssetsDetail.vue']) {
    const results = [];
    for (const locale of ['zh-CN', 'en-US']) {
      i18n.global.locale.value = locale;
      const calls = [];
      const fixture = component(file, {
        buildAssetFilterParams, serviceEngineType: ref('nmap'), activeTab: ref('site'), scope_id: ref('scope-a'), targetName: ref('用户资产组'),
        searchForm: ref({ status: ['403', '200'], title: '用户网站' }), columns: ref([]), asmCounts: {},
        lastFetchedPage: 1, lastFetchedSize: 20, pagination: { current: 2, pageSize: 20, total: 0 },
        loading: ref(false), dataSource: ref([]), selectedRowKeys: ref([]),
        selectionTracker: { rememberRows() {}, syncSelection() {}, getLabels: () => [], clear() {} },
        getAssetRowKey: r => r?._id || r?.id,
        getAssetRecordDisplayLabel: () => '',
        tabCache: { updateMemoryCache() {}, saveCurrentTab() {} },
        request: { async get(url, options) { calls.push({ url, ...plain(options) }); return { code: 200, items: [], total: 0 }; } },
        message: { loading() {}, success() {}, error(error) { assert.fail(error); } },
        Blob, window: { URL: { createObjectURL: () => 'blob:fixture', revokeObjectURL() {} } },
        document: { createElement: () => ({ click() {}, remove() {} }), body: { appendChild() {}, removeChild() {} } },
      });
      fixture.read('tabConfig');
      fixture.read('effectiveTab');
      await fixture.read('fetchData')();
      await fixture.read('handleExport')();
      assert.equal(calls.length, 2);
      for (const call of calls) {
        assert.equal(call.params.status__in, '200,403');
        assert.equal(call.params.title, '用户网站');
        if (file.includes('GroupAssetsDetail')) assert.equal(call.params.scope_id, 'scope-a');
        else assert.equal('scope_id' in call.params, false);
      }
      results.push(calls);
    }
    assert.deepEqual(results[1], results[0], file);
  }
});

test('中英文创建资产组和两种监控任务时发送相同的目标、策略和运行间隔', async () => {
  const result = [];
  for (const locale of ['zh-CN', 'en-US']) {
    i18n.global.locale.value = locale;
    const calls = [];
    const fixture = component('views/AssetScope.vue', {
      request: { async post(url, payload) { calls.push({ url, payload: plain(payload) }); return { code: 200, data: [{}] }; } },
      message: { success() {}, error(error) { assert.fail(error); } },
      addFormRef: ref({ validate: async () => {} }), addForm: { group_id: 'company-a', name: '用户资产组', scope: 'example.test\n192.0.2.0/24' },
      addLoading: ref(false), addModalVisible: ref(true), pagination: { current: 2 }, fetchData() {},
      currentRecord: ref({ _id: 'scope-a' }), addMonitorFormRef: ref({ validate: async () => {} }), addMonitorLoading: ref(false), addMonitorVisible: ref(true),
      addMonitorForm: { domains: ['example.test', '192.0.2.0/24'], interval_hours: 12, policy_id: 'policy-a', task_type: 'periodic' },
    });
    await fixture.read('handleAddSubmit')();
    const monitor = fixture.read('submitAddMonitor');
    await monitor();
    fixture.context.addMonitorForm.task_type = 'oneshot';
    await monitor();
    result.push(calls);
  }
  assert.deepEqual(result[1], result[0]);
  assert.deepEqual(result[0], [
    { url: '/asset_scope/', payload: { group_id: 'company-a', name: '用户资产组', scope: 'example.test\n192.0.2.0/24' } },
    { url: '/scheduler/add/', payload: { scope_id: 'scope-a', domain: 'example.test,192.0.2.0/24', interval: 43200, policy_id: 'policy-a', name: '' } },
    { url: '/scheduler/one_time_scan/', payload: { scope_id: 'scope-a', domain: 'example.test,192.0.2.0/24', policy_id: 'policy-a', name: '' } },
  ]);
});

test('中英文移除资产范围均等待确认，保留警告、被移除目标和相同更新参数', async () => {
  const results = [];
  for (const locale of ['zh-CN', 'en-US']) {
    i18n.global.locale.value = locale;
    const calls = [], confirmations = [];
    const fixture = component('views/AssetScope.vue', {
      editGroupMode: ref('visual'), editGroupScopeList: ref(['example.test']), editGroupForm: { _id: 'scope-a', group_id: 'company-a', name: '用户资产组', scope: '' },
      editGroupFormRef: ref({ validate: async () => {} }), editGroupLoading: ref(false), editGroupModalVisible: ref(true),
      currentRecord: ref({ scope_array: ['example.test', 'removed.test'] }), fetchData() {},
      notifyAssetMutated() {}, assetMutationVersion: ref(0), lastObservedMutationVersion: 0,
      Modal: { confirm: value => confirmations.push(value) }, ExclamationCircleOutlined: {},
      createVNode: (tag, props, children) => ({ tag, props, children }),
      message: { success() {}, error(error) { assert.fail(error); } },
      request: { async post(url, payload) { calls.push({ url, payload: plain(payload) }); return { code: 200 }; } },
    });
    fixture.read('parseScopeList');
    fixture.read('submitEditGroupUpdate');
    await fixture.read('handleEditGroupSubmit')();
    assert.equal(calls.length, 0);
    assert.equal(confirmations.length, 1);
    assert.equal(confirmations[0].okType, 'danger');
    const content = JSON.stringify(confirmations[0].content);
    assert.match(content, /removed\.test/);
    assert.match(content, /用户资产组/);
    assert.match(content, locale === 'en-US' ? /permanently deletes/ : /不可逆/);
    confirmations[0].onOk();
    await new Promise(resolve => setImmediate(resolve));
    results.push(calls);
  }
  assert.deepEqual(results[1], results[0]);
  assert.deepEqual(results[0], [{ url: '/asset_scope/update/', payload: { _id: 'scope-a', group_id: 'company-a', name: '用户资产组', scope: 'example.test' } }]);
});

test('内置标签仅翻译显示文本，中英文下移除入口标签都发送原始值', async () => {
  const results = [];
  for (const locale of ['zh-CN', 'en-US']) {
    i18n.global.locale.value = locale;
    const format = component('views/AssetSearch.vue').read('formatAssetTag');
    const tags = ['入口', { name: '待测试' }, { tag_name: '用户标签' }];
    assert.deepEqual(tags.map(format), locale === 'en-US' ? ['Entry point', 'To test', '用户标签'] : ['入口', '待测试', '用户标签']);
    assert.deepEqual(tags, ['入口', { name: '待测试' }, { tag_name: '用户标签' }]);
    const calls = [];
    const fixture = component('views/GroupAssetsDetail.vue', {
      request: { async post(url, payload) { calls.push({ url, payload: plain(payload) }); return { code: 200 }; } },
      message: { success() {}, error(error) { assert.fail(error); } },
      syncTagState() {}, tabCache: { invalidateMemoryCache() {} }, activeTab: ref('site'),
    });
    await fixture.read('handleDeleteTag')({ _id: 'site-a', tag: ['入口', '用户标签'] }, '入口');
    results.push(calls);
  }
  assert.deepEqual(results[1], results[0]);
  assert.deepEqual(results[0], [{ url: '/asset_site/delete_tag/', payload: { _id: 'site-a', tag: '入口' } }]);
});

test('切换语言不改变原始 JSON 预览、复制内容或资产画像导出的数据', async () => {
  const data = { name: '用户资产', status: '存续', url: 'https://example.test:8443', tag: ['入口'], nested: { value: '{原值}' } };
  const results = [];
  for (const locale of ['zh-CN', 'en-US']) {
    i18n.global.locale.value = locale;
    const copied = [], blobs = [], links = [];
    const raw = component('components/RawDataDrawer.vue', { props: { data }, copyText: async text => { copied.push(text); return true; }, message: { success() {} } });
    raw.read('formattedJson');
    await raw.read('handleCopy')();
    const chain = component('components/ChainDrawer.vue', {
      props: { target: 'example.test' }, chainData: ref(data), Blob,
      URL: { createObjectURL(blob) { blobs.push(blob); return 'blob:fixture'; }, revokeObjectURL() {} },
      document: { createElement() { const link = { click() {}, remove() {} }; links.push(link); return link; }, body: { appendChild() {} } },
      dayjs: () => ({ format: () => '20261019_000000' }), message: { success() {}, warning(error) { assert.fail(error); }, error(error) { assert.fail(error); } },
    });
    chain.read('downloadChainJson')();
    results.push({ copied, json: await blobs[0].text(), filename: links[0].download });
  }
  assert.deepEqual(results[1], results[0]);
  assert.deepEqual(JSON.parse(results[0].copied[0]), data);
  assert.deepEqual(JSON.parse(results[0].json), data);
  assert.equal(results[0].filename, 'arl_chain_example.test_20261019_000000.json');
});
