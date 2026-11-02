import assert from 'node:assert/strict';
import fs from 'node:fs';
import test, { afterEach } from 'node:test';
import vm from 'node:vm';
import { computed, reactive, ref, watch, nextTick, effectScope } from 'vue';
import { parse, compileScript, babelParse } from 'vue/compiler-sfc';
import { i18n } from '../src/i18n/index.js';
import zh from '../src/i18n/zh-CN.js';
import en from '../src/i18n/en-US.js';
import { SUPPORT_CONFIG } from '../src/config/support.js';
import { processImageToBase64 } from '../src/utils/theme.js';

const plain = value => JSON.parse(JSON.stringify(value));
const pageText = (...args) => i18n.global.t(...args);
const stops = [];
afterEach(() => { stops.splice(0).forEach(stop => stop()); i18n.global.locale.value = 'zh-CN'; });
const files = ['views/Dashboard.vue', 'views/GithubManage.vue', 'views/PocList.vue', 'components/NucleiManage.vue',
  'views/Fingerprint.vue', 'views/Policy.vue', 'views/PolicyDetail.vue', 'views/SystemSettings.vue',
  'components/settings/BackupRestorePanel.vue', 'components/settings/SystemUpdatePanel.vue',
  'views/McpCenter.vue', 'views/Layout.vue', 'components/SupportAuthorPopover.vue'];
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
    sources.set(file, { descriptor, bindings, ast: scriptSetupAst });
  }
  const { descriptor, bindings, ast } = sources.get(file);
  const notices = [];
  const context = vm.createContext({ pageText, computed, reactive, ref, console, pageLocale: i18n.global.locale,
    message: Object.fromEntries(['success', 'warning', 'error', 'info', 'loading'].map(key => [key, (...args) => notices.push({ key, args })])), ...initial });
  return { context, descriptor, ast, notices,
    read(name) {
      assert.ok(bindings[name], `${file}: missing ${name}`);
      return vm.runInContext(`globalThis.${name} = (${bindings[name]})`, context);
    },
    statement(node) { return vm.runInContext(descriptor.scriptSetup.content.slice(node.start, node.end), context); },
  };
}
function resolve(messages, key) { return key.split('.').reduce((value, part) => value?.[part], messages); }

test('备份和恢复切换语言后保持请求参数、强制恢复选项和进度跟踪动作', async () => {
  for (const locale of ['zh-CN', 'en-US']) {
    i18n.global.locale.value = locale;
    const calls = [], tracking = [];
    const page = component('components/settings/BackupRestorePanel.vue', {
      request: { async post(url, payload) { calls.push({ url, payload: plain(payload) }); return { code: 200 }; } },
      createBackupForm: reactive({ includeScreenshots: false, note: ' fixture note ' }),
      backupLoading: ref(false), createBackupModalVisible: ref(true),
      selectedRestoreBackup: ref({ filename: 'arl_backup_fixture.tar.gz' }),
      restoreForceCheck: ref(true), backupRunningTasks: ref(2), restoreModalVisible: ref(true),
      startProgressTracking: (...args) => tracking.push(args),
    });
    await page.read('handleExecuteCreateBackup')();
    await page.read('handleExecuteRestore')();
    assert.deepEqual(calls, [
      { url: '/api/backup/create', payload: { include_screenshots: false, note: 'fixture note' } },
      { url: '/api/backup/restore', payload: { filename: 'arl_backup_fixture.tar.gz', force: true } },
    ]);
    assert.deepEqual(tracking, [['backup'], ['restore', 'arl_backup_fixture.tar.gz']]);
    assert.equal(page.context.backupLoading.value, false);
    assert.equal(page.context.createBackupModalVisible.value, false);
    assert.equal(page.context.restoreModalVisible.value, false);
    assert.match(page.descriptor.template.content, /disabled: restoreConfirmInput !== 'RESTORE'/);
  }
});

test('备份进度恢复保留已有进度，忽略空闲状态和更低百分比', async () => {
  const timers = [], replies = [
    { status: 'idle', percent: 0 }, { status: 'backing_up', percent: 20 },
    { status: 'success', percent: 100, action: 'backup' },
  ];
  let stopped = 0, refreshed = 0;
  const page = component('components/settings/BackupRestorePanel.vue', {
    request: { async get(url) { assert.equal(url, '/api/backup/status'); return { code: 200, data: replies.shift() }; } },
    progressAction: ref('backup'), progressPercent: ref(42), progressStage: ref('fixture backend stage'),
    progressElapsed: ref(17), progressLogs: ref(['fixture backend log']), progressFinished: ref(false),
    progressHasError: ref(false), progressArchiveName: ref('arl_backup_fixture.tar.gz'),
    backupProgressModalVisible: ref(false), progressPollTimer: null, progressElapsedTimer: null,
    setInterval: (callback) => { timers.push(callback); return timers.length; },
    stopProgressTracking: () => { stopped += 1; }, scrollBackupTerminal() {},
    fetchBackupList: () => { refreshed += 1; },
  });
  page.read('startProgressTracking')('backup', 'arl_backup_fixture.tar.gz', true);
  assert.equal(page.context.progressPercent.value, 42);
  assert.equal(page.context.progressElapsed.value, 17);
  assert.deepEqual(plain(page.context.progressLogs.value), ['fixture backend log']);
  await timers[1]();
  assert.equal(page.context.progressPercent.value, 42);
  await timers[1]();
  assert.equal(page.context.progressPercent.value, 42);
  await timers[1]();
  assert.equal(page.context.progressPercent.value, 100);
  assert.equal(page.context.progressFinished.value, true);
  assert.equal(page.context.progressHasError.value, false);
  assert.equal(stopped, 2);
  assert.equal(refreshed, 1);
});

// Execute the original methods with isolated requests; no live backend is contacted.
test('第四阶段语言包可完整渲染，英文无遗漏中文，全部具名参数保留', () => {
  assert.deepEqual(Object.keys(zh.pages), Object.keys(en.pages));
  for (const [locale, messages] of [['zh-CN', zh.pages], ['en-US', en.pages]]) {
    i18n.global.locale.value = locale;
    for (const [key, message] of Object.entries(messages)) {
      const params = Object.fromEntries([...message.matchAll(/\{(\w+)\}/g)].map(([, name]) => [name, `fixture_${name}`]));
      const text = pageText(`pages.${key}`, params);
      assert.notEqual(text, `pages.${key}`, `${locale}: ${key}`);
      for (const value of Object.values(params)) assert.ok(text.includes(value), `${locale}: ${key}`);
      if (locale === 'en-US') assert.doesNotMatch(text, /\p{Script=Han}/u, key);
    }
  }
});

test('剩余页面引用的消息和具名参数在两种语言中均存在', () => {
  const check = node => {
    if (!node || typeof node !== 'object') return;
    if (node.type === 'CallExpression' && node.callee.name === 'pageText' && node.arguments[0]?.type === 'StringLiteral') {
      const key = node.arguments[0].value;
      for (const messages of [zh, en]) assert.equal(typeof resolve(messages, key), 'string', key);
      const expected = [...new Set([...resolve(en, key).matchAll(/\{(\w+)\}/g)].map(([, name]) => name))].sort();
      const actual = (node.arguments[1]?.properties || []).map(property => property.key.name).sort();
      assert.deepEqual(actual, expected, key);
    }
    if (node.type === 'StringLiteral' && node.value.startsWith('pages.')) {
      for (const messages of [zh, en]) assert.equal(typeof resolve(messages, node.value), 'string', node.value);
    }
    for (const [key, value] of Object.entries(node)) {
      if (['loc', 'comments', 'leadingComments', 'trailingComments'].includes(key)) continue;
      if (Array.isArray(value)) value.forEach(check);
      else if (value && typeof value === 'object') check(value);
    }
  };
  for (const file of files) {
    const { descriptor } = component(file);
    check(babelParse(descriptor.scriptSetup.content, { sourceType: 'module' }));
    const template = node => {
      if (node.type === 4 && !node.isStatic) {
        if (node.content.includes('pageText(')) {
          try { check(babelParse(`(${node.content})`, { sourceType: 'module' })); }
          catch (error) { throw new Error(`${file}: ${node.content}`, { cause: error }); }
        }
        return;
      }
      if (node.type === 2) assert.doesNotMatch(node.content, /\p{Script=Han}/u, file);
      if (node.type === 6 && node.value) assert.doesNotMatch(node.value.content, /\p{Script=Han}/u, `${file}: ${node.name}`);
      for (const child of [...(node.children || []), ...(node.props || [])]) template(child);
      if (node.exp) template(node.exp);
      if (node.type === 5) template(node.content);
    };
    template(descriptor.template.ast);
  }
  for (const file of ['config/support.js', 'utils/theme.js']) check(babelParse(fs.readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8'), { sourceType: 'module' }));
});

test('已创建的管理表格、选项和设置索引切换语言后更新标题，字段标识不变', () => {
  const cases = [
    ['views/GithubManage.vue', 'schedulerColumns'], ['views/GithubManage.vue', 'resultColumns'],
    ['views/PocList.vue', 'columns'], ['components/NucleiManage.vue', 'customColumns'],
    ['components/NucleiManage.vue', 'communityColumns'], ['components/NucleiManage.vue', 'blacklistColumns'],
    ['views/Fingerprint.vue', 'columns'], ['views/Policy.vue', 'columns'],
    ['components/settings/BackupRestorePanel.vue', 'backupColumns'],
    ['views/McpCenter.vue', 'keyColumns'], ['views/McpCenter.vue', 'logColumns'], ['views/McpCenter.vue', 'toolSwitchConfigs'],
    ['views/PolicyDetail.vue', 'nucleiSeverityOptions'], ['views/SystemSettings.vue', 'SETTINGS_INDEX'],
  ];
  for (const [file, name] of cases) {
    i18n.global.locale.value = 'zh-CN';
    const rows = component(file).read(name);
    const list = () => rows.value || rows;
    const labels = computed(() => list().map(row => row.title || row.label || row.desc));
    const chinese = labels.value;
    const identity = () => plain(list().map(({ key, dataIndex, value, tab, anchor, keywords }) => ({ key, dataIndex, value, tab, anchor, keywords })));
    const original = identity();
    i18n.global.locale.value = 'en-US';
    assert.notDeepEqual(labels.value, chinese, file);
    assert.deepEqual(identity(), original, file);
    i18n.global.locale.value = 'zh-CN';
    assert.deepEqual(labels.value, chinese, file);
  }
});

test('字典分类切换语言后保持分组键、文件名、内置标识和当前选择', () => {
  const page = component('views/SystemSettings.vue', {
    dictList: ref([{ name: 'domain_2w.txt', is_builtin: true }, { name: 'port_top100.txt', is_builtin: true }]),
    bruteDictList: ref([{ name: 'username_ssh.txt' }, { name: 'password_ssh.txt' }, { name: 'common_password.txt' }]),
    unifiedSelectedType: ref('asset'), unifiedSelectedName: ref('domain_2w.txt'),
  });
  for (const name of ['ASSET_DICT_META', 'assetMenuGroups', 'bruteSvcGroups', 'formatDictionaryGroup', 'treeData', 'unifiedSelectedDesc', 'selectedCategoryKeys']) page.read(name);
  const tree = page.context.treeData, description = page.context.unifiedSelectedDesc;
  const identity = () => plain(tree.value.map(group => ({ key: group.key, children: group.children.map(({ key, subTitle, is_builtin }) => ({ key, subTitle, is_builtin })) })));
  const original = identity(), title = tree.value[0].title, chinese = description.value;
  i18n.global.locale.value = 'en-US';
  assert.notEqual(tree.value[0].title, title);
  assert.notEqual(description.value, chinese);
  assert.deepEqual(identity(), original);
  assert.deepEqual(plain(page.context.selectedCategoryKeys.value), ['group_asset_🌍 子域名爆破']);
  assert.equal(tree.value.at(-1).children.find(row => row.subTitle === 'common_password.txt').mainTitle, 'common_password.txt');
  assert.equal(page.context.unifiedSelectedName.value, 'domain_2w.txt');
});

test('设置搜索保留中文别名并支持英文显示文案，不改变定位锚点', () => {
  const page = component('views/SystemSettings.vue', { settingsKeyword: ref('并发') });
  page.read('SETTINGS_INDEX');
  const results = page.read('settingsSearchResults');
  const anchors = results.value.map(row => row.anchor);
  assert.ok(anchors.length > 0);
  i18n.global.locale.value = 'en-US';
  assert.deepEqual(results.value.map(row => row.anchor), anchors);
  page.context.settingsKeyword.value = 'concurrency';
  assert.ok(results.value.some(row => anchors.includes(row.anchor)));
  assert.ok(results.value.every(row => !/\p{Script=Han}/u.test(row.label)));
});

test('中英文下保存系统设置只提交当前分组的改动，配置字段与内容保持一致', async () => {
  const results = [];
  for (const locale of ['zh-CN', 'en-US']) {
    i18n.global.locale.value = locale;
    const calls = [];
    const page = component('views/SystemSettings.vue', {
      generalForm: ref({ fofa_max_page: 3, query_plugin_config: { custom: '用户配置' }, proxy_url: 'http://127.0.0.1:8888' }),
      generalBaseline: ref({ fofa_max_page: 1, query_plugin_config: { custom: '用户配置' }, proxy_url: '' }),
      request: { async post(url, data) { calls.push({ url, data: plain(data) }); return { code: 200 }; } },
    });
    for (const name of ['GENERAL_FIELD_GROUPS', 'cloneDeep', 'changedFields', 'pendingByGroup']) page.read(name);
    assert.equal(await page.read('saveGeneralGroup')('api_config', ref(false)), true);
    assert.equal(page.context.generalBaseline.value.proxy_url, '');
    assert.equal(page.context.changedFields.value.proxy_url, 'http://127.0.0.1:8888');
    assert.equal(page.context.generalForm.value.query_plugin_config.custom, '用户配置');
    assert.ok(!page.notices.some(row => row.key === 'error'));
    results.push(calls);
  }
  assert.deepEqual(results[1], results[0]);
  assert.deepEqual(results[0], [{ url: '/api/system_config/general', data: { fofa_max_page: 3 } }]);
});

test('中英文提交的扫描策略保留端口、字典、插件和 Nuclei 参数', async () => {
  const results = [];
  for (const locale of ['zh-CN', 'en-US']) {
    i18n.global.locale.value = locale;
    const calls = [];
    const page = component('views/PolicyDetail.vue', {
      isEdit: false, submitLoading: ref(false), hasPocLoaded: ref(true),
      pocList: ref([{ plugin_name: 'poc_original', vul_name: '用户漏洞名称', enable: true }]),
      bruteList: ref([{ plugin_name: 'brute_original', vul_name: '用户检查', enable: true }]),
      router: { push() {} }, request: { async post(url, data) { calls.push({ url, data: plain(data) }); return { code: 200 }; } },
    });
    page.read('initPolicyForm');
    const form = page.read('policyForm');
    form.name = ' 用户策略 '; form.desc = '保留描述';
    Object.assign(form.domain_config, { domain_brute: true, domain_brute_type: 'domain_2w.txt', alt_dns: true, alt_dns_dict: 'altdns_default.txt' });
    Object.assign(form.ip_config, { port_scan: true, port_scan_type: 'custom', port_custom: '80,443,8443', service_detection: true });
    form.site_config.nuclei_scan = true;
    form.file_leak = true; form.file_leak_dict = 'file_top_200.txt';
    await page.read('submitPolicy')();
    assert.equal(calls.length, 1, JSON.stringify(page.notices));
    assert.ok(!page.notices.some(row => row.key === 'error'));
    results.push(calls);
  }
  assert.deepEqual(results[1], results[0]);
  const data = results[0][0].data;
  assert.equal(data.name, '用户策略');
  assert.equal(data.policy.ip_config.port_custom, '80,443,8443');
  assert.equal(data.policy.domain_config.domain_brute_type, 'domain_2w.txt');
  assert.deepEqual(data.policy.site_config.nuclei_config, { severity: ['critical', 'high', 'medium', 'low'], custom_template_mode: 'all_enabled', exclude_blacklist: true });
  assert.equal(data.policy.poc_config[0].vul_name, '用户漏洞名称');
});

test('策略校验在两种语言下均阻止缺少字典或端口的扫描配置', async () => {
  for (const locale of ['zh-CN', 'en-US']) {
    i18n.global.locale.value = locale;
    const calls = [];
    const page = component('views/PolicyDetail.vue', { isEdit: false, request: { post: (...args) => calls.push(args) } });
    page.read('initPolicyForm');
    const form = page.read('policyForm'); form.name = '用户策略'; form.domain_config.domain_brute = true;
    const submit = page.read('submitPolicy');
    await submit();
    assert.equal(calls.length, 0);
    form.domain_config.domain_brute_type = 'domain_2w.txt';
    form.ip_config.port_scan = true; form.ip_config.port_scan_type = 'custom';
    await submit();
    assert.equal(calls.length, 0);
    assert.equal(page.notices.filter(row => row.key === 'warning').length, 2);
    if (locale === 'en-US') assert.doesNotMatch(JSON.stringify(page.notices), /\p{Script=Han}/u);
  }
});

test('GitHub 监控与一次性任务在中英文下使用相同请求、关键字和 Cron', async () => {
  const results = [];
  for (const locale of ['zh-CN', 'en-US']) {
    i18n.global.locale.value = locale;
    const calls = [];
    const page = component('views/GithubManage.vue', {
      schedulerForm: { name: '用户监控', keyword: 'org:example 原始关键字', cron: '*/30 * * * *' },
      schedulerIsEdit: ref(false), schedulerSubmitLoading: ref(false), schedulerModalVisible: ref(true), onSchedulerSearch() {},
      taskForm: { name: '用户任务', keyword: 'repo:example/project config' }, taskSubmitLoading: ref(false), taskModalVisible: ref(true), onTaskSearch() {},
      request: { async post(url, data) { calls.push({ url, data: plain(data) }); return { code: 200 }; } },
    });
    await page.read('submitSchedulerModal')();
    await page.read('submitTaskModal')();
    assert.equal(calls.length, 2, JSON.stringify(page.notices));
    results.push(calls);
  }
  assert.deepEqual(results[1], results[0]);
  assert.equal(results[0][0].data.cron, '*/30 * * * *');
  assert.equal(results[0][0].data.keyword, 'org:example 原始关键字');
});

test('GitHub 结果抽屉标题即时切换语言，记录名称和 ID 不变', () => {
  const page = component('views/GithubManage.vue', { resultCurrentRecord: ref({ _id: 'record-a', name: '用户任务' }), resultDrawerType: ref('task') });
  const title = page.read('resultDrawerTitle');
  const chinese = title.value;
  i18n.global.locale.value = 'en-US';
  assert.notEqual(title.value, chinese);
  assert.match(title.value, /用户任务/);
  page.context.resultDrawerType.value = 'scheduler';
  assert.match(title.value, /Recurring/);
  assert.deepEqual(plain(page.context.resultCurrentRecord.value), { _id: 'record-a', name: '用户任务' });
});

test('Nuclei 模板提交与误报屏蔽保留原始 YAML、标识及原因', async () => {
  const results = [];
  for (const locale of ['zh-CN', 'en-US']) {
    i18n.global.locale.value = locale;
    const calls = [];
    const page = component('components/NucleiManage.vue', {
      saveErrorMsg: ref(''), currentEditorCode: ref('id: fixture\n# 用户规则\ninfo:\n  name: 用户模板\n'),
      saveLoading: ref(false), isCreateMode: ref(false), currentEditTemplateId: ref('fixture'), isEditModalVisible: ref(true),
      markModalForm: { template_id: 'fixture', name: '用户模板', severity: 'high', tags: ['custom'], reason: '' },
      markModalLoading: ref(false), isMarkModalVisible: ref(true), fetchCustomTemplates() {}, fetchStats() {}, fetchBlacklist() {}, fetchCommunityTemplates() {},
      request: { async post(url, data) { calls.push({ url, data: plain(data) }); return { code: 200 }; } },
    });
    await page.read('saveTemplate')();
    await page.read('handleConfirmMarkBlacklist')();
    assert.equal(calls.length, 2, JSON.stringify(page.notices));
    results.push(calls);
  }
  assert.deepEqual(results[1], results[0]);
  assert.equal(results[0][0].data.content, 'id: fixture\n# 用户规则\ninfo:\n  name: 用户模板\n');
  assert.equal(results[0][1].data.reason, '手工标记误报');
  assert.equal(results[0][1].data.severity, 'high');
});

test('语言切换不翻译内置 PoC 和 YAML 示例源码', () => {
  const snapshots = [];
  for (const locale of ['zh-CN', 'en-US']) {
    i18n.global.locale.value = locale;
    const templates = component('views/PocList.vue').read('templates');
    snapshots.push({ python: Object.fromEntries(Object.entries(templates).map(([key, value]) => [key, value.content])),
      yaml: plain(component('components/NucleiManage.vue').read('skeletonTemplates')) });
  }
  assert.deepEqual(snapshots[1], snapshots[0]);
  assert.ok(Object.values(snapshots[0].python).some(source => source.includes('class Plugin(BasePlugin)')));
  assert.match(snapshots[0].yaml.http_get, /\{\{BaseURL\}\}/);
  assert.match(snapshots[0].yaml.dns_check, /\{\{FQDN\}\}/);
});

test('语言切换重新绘制图表标签，保留图表数据、比例与严重级别标识', async () => {
  const trends = [], pies = [];
  const page = component('views/Dashboard.vue', {
    chartRef: ref({}), vulnChartRef: ref({}), myChart: { setOption: value => trends.push(value), resize() {} }, myVulnChart: { setOption: value => pies.push(value), off() {}, on() {}, resize() {} },
    lastTrendData: { days: ['2026-10-20'], assets: [5], vulns: [2], leaks: [1], cves: [3] },
    stats: ref({ vuln: { nuclei_critical: 2, nuclei_high: 1, nuclei_medium: 0, nuclei_low: 0, arl_total: 1 } }),
    isDarkMode: ref(false), trendFilter: ref('all'), vulnEngineMode: ref('all'),
    document: { documentElement: {} }, getComputedStyle: () => ({ getPropertyValue: () => '#1890ff' }),
    echarts: { graphic: { LinearGradient: class { constructor(...args) { this.args = args; } } } },
    watch: (...args) => { const stop = watch(...args); stops.push(stop); return stop; },
  });
  page.read('colorToRgba');
  page.read('renderTrendChart')(); page.read('renderVulnChart')();
  const identity = () => ({ trends: plain(trends.at(-1).series.map(({ data, type, yAxisIndex }) => ({ data, type, yAxisIndex }))),
    pie: plain(pies.at(-1).series[0].data.map(({ value, tabKey }) => ({ value, tabKey }))) });
  const original = identity();
  const listener = page.ast.find(node => node.type === 'ExpressionStatement' && node.expression.callee?.name === 'watch' && node.expression.arguments[0]?.name === 'pageLocale');
  assert.ok(listener); page.statement(listener);
  i18n.global.locale.value = 'en-US'; await nextTick();
  assert.equal(trends.length, 2); assert.equal(pies.length, 2);
  assert.deepEqual(identity(), original);
  assert.doesNotMatch(trends.at(-1).legend.data.join(' '), /\p{Script=Han}/u);
  assert.doesNotMatch(pies.at(-1).series[0].data.map(row => row.name).join(' '), /\p{Script=Han}/u);
  const text = pies.at(-1).tooltip.formatter({ name: 'Critical', value: 2, percent: 50 });
  assert.match(text, /Critical/); assert.match(text, /2/); assert.match(text, /50%/);
});

test('字典条目删除在两种语言下均等待确认并保留原始文件名及条目', async () => {
  const results = [];
  for (const locale of ['zh-CN', 'en-US']) {
    i18n.global.locale.value = locale;
    const calls = [], confirmations = [];
    const page = component('views/SystemSettings.vue', {
      selectedDict: ref('用户字典.txt'), dictApiBase: ref('/api/dictionary'), deleteLoading: ref(false), searchResult: ref(['原始条目', '保留条目']),
      fetchDictList() {}, fetchBruteDictList() {}, fetchPreview() {}, createVNode() {}, ExclamationCircleOutlined: {},
      Modal: { confirm: value => confirmations.push(value) },
      request: { async post(url, data) { calls.push({ url, data: plain(data) }); return { code: 200, data: { total_submitted: 1, deleted: 1 } }; } },
    });
    page.read('deleteEntries');
    page.read('handleDeleteSingle')('原始条目');
    assert.equal(calls.length, 0); assert.equal(confirmations.length, 1);
    assert.equal(confirmations[0].okButtonProps.danger, true);
    await confirmations[0].onOk();
    assert.deepEqual(plain(page.context.searchResult.value), ['保留条目']);
    results.push(calls);
  }
  assert.deepEqual(results[1], results[0]);
  assert.deepEqual(results[0], [{ url: '/api/dictionary/delete_entries', data: { name: '用户字典.txt', content: '原始条目' } }]);
});

test('更新日志保留原始阶段识别和字节偏移，语言切换不重复追加离线提示', async () => {
  const timers = new Map(), requests = []; let sequence = 0;
  const responses = [
    { ok: true, json: async () => ({ log_token: 'fixture-log-token' }) }, { ok: false, status: 502 }, { ok: false, status: 502 },
    { ok: true, headers: { get: () => 'application/json' }, json: async () => ({ chunk: '正在拉取核心镜像\n', offset: 77 }) },
    { ok: true, headers: { get: () => 'application/json' }, json: async () => ({ chunk: '后端服务已完全就绪\n', offset: 140, done: true }) },
  ];
  const page = component('components/settings/SystemUpdatePanel.vue', {
    ...Object.fromEntries(['updateModalVisible', 'updateButtonLoading', 'updateHasError', 'updateFinished'].map(name => [name, ref(false)])),
    updateLogs: ref(''), updateProgress: ref(0), updateOfflineNotices: ref(''), logByteOffset: ref(0), activeLayers: ref({}),
    updateElapsedSeconds: ref(0), updateTimer: ref(null), updatePollInterval: ref(null), scrollToBottom() {},
    setInterval(fn, ms) { const id = ++sequence; timers.set(id, { fn, ms }); return id; }, clearInterval(id) { timers.delete(id); },
    request: { async post(url) { requests.push(url); return { code: 200, data: { token: 'fixture-update-token' } }; } },
    async fetch(url) { requests.push(url); assert.ok(responses.length); return responses.shift(); },
  });
  for (const name of ['currentStageKey', 'currentStageTitle', 'stopUpdateTimers', 'finishUpdate']) page.read(name);
  await page.read('startUpdate')();
  const poll = [...timers.values()].find(timer => timer.ms === 1200).fn;
  await poll(); const firstOfflineLog = page.context.updateLogs.value;
  i18n.global.locale.value = 'en-US';
  await poll(); assert.equal(page.context.updateLogs.value, firstOfflineLog);
  await poll();
  assert.match(page.context.currentStageTitle.value, /Stage 1\/3/);
  assert.match(page.context.updateLogs.value, /正在拉取核心镜像/);
  assert.equal(page.context.logByteOffset.value, 77);
  await poll();
  assert.equal(page.context.updateFinished.value, true);
  assert.equal(page.context.updateHasError.value, false);
  assert.equal(page.context.updateProgress.value, 100);
  assert.equal(timers.size, 0);
  assert.match(requests.at(-1), /offset=77$/);
  assert.equal(requests[1], '/update_stream/trigger');
  assert.doesNotMatch(page.context.currentStageTitle.value, /\p{Script=Han}/u);
});

test('版本占位文案切换语言，真实版本和支持信息的身份字段保持原样', () => {
  const format = component('components/NucleiManage.vue').read('formatTemplateVersion');
  assert.equal(format('未安装'), '未安装');
  const systemVersion = component('components/settings/SystemUpdatePanel.vue').read('formatSystemVersion');
  assert.equal(systemVersion('未知版本'), '未知版本');
  const author = { name: SUPPORT_CONFIG.official.name, wechatId: SUPPORT_CONFIG.wechat.wechatId, tab: SUPPORT_CONFIG.defaultTab };
  const chinese = SUPPORT_CONFIG.entry.text;
  i18n.global.locale.value = 'en-US';
  assert.equal(format('未安装'), 'Not installed');
  assert.equal(format('v3.11.0'), 'v3.11.0');
  assert.equal(systemVersion('未知版本'), 'Unknown version');
  assert.equal(systemVersion('v1.4.2'), 'v1.4.2');
  assert.equal(systemVersion(''), 'Loading...');
  assert.notEqual(SUPPORT_CONFIG.entry.text, chinese);
  assert.deepEqual({ name: SUPPORT_CONFIG.official.name, wechatId: SUPPORT_CONFIG.wechat.wechatId, tab: SUPPORT_CONFIG.defaultTab }, author);
});

test('背景图片校验错误随当前语言显示', async () => {
  await assert.rejects(processImageToBase64(null), /有效的图片/);
  i18n.global.locale.value = 'en-US';
  await assert.rejects(processImageToBase64(null), /valid image/);
});


test('GitHub 页面完整初始化后，五个分页控件继续共享每页条数，切换语言不发起请求', async () => {
  const { descriptor, ast } = component('views/GithubManage.vue');
  let source = descriptor.scriptSetup.content;
  for (const node of [...ast].reverse()) {
    if (node.type === 'ImportDeclaration') source = source.slice(0, node.start) + source.slice(node.end);
  }
  const size = ref(10), calls = [], mounted = [];
  const scope = effectScope();
  stops.push(() => scope.stop());
  const context = vm.createContext({ ref, reactive, computed, watch, nextTick, console,
    defineOptions: () => {}, useI18n: () => ({ t: pageText }),
    useRouter: () => ({ push() {} }), useRoute: () => ({ query: {} }),
    useGlobalPageSize: () => size, onMounted: fn => mounted.push(fn),
    onDeactivated: () => {}, onUnmounted: () => {},
    request: { get: async path => { calls.push(path); return { code: 200, data: [], items: [], total: 0 }; } },
    message: { success() {}, error() {}, warning() {} }, Modal: {},
  });
  const state = scope.run(() => vm.runInContext(`${source}
    ;({ schedulerPagination, taskPagination, toolsPagination, hackersPagination, cvePagination, schedulerColumns });`, context));
  assert.equal(mounted.length, 1);
  const pages = Object.entries(state).filter(([name]) => name.endsWith('Pagination')).map(([, value]) => value);
  assert.equal(pages.length, 5);
  for (const page of pages) {
    page.pageSize += 10;
    await nextTick();
    assert.ok(pages.every(value => value.pageSize === size.value));
  }
  const title = state.schedulerColumns[0].title;
  i18n.global.locale.value = 'en-US';
  await nextTick();
  assert.notEqual(state.schedulerColumns[0].title, title);
  assert.deepEqual(calls, []);
});

test('所有前端组件的固定模板文字和属性均无遗漏中文', () => {
  const untranslated = [];
  const files = fs.readdirSync(new URL('../src/', import.meta.url), { recursive: true }).filter(file => file.endsWith('.vue'));
  for (const file of files) {
    const { descriptor } = parse(fs.readFileSync(new URL(`../src/${file.replaceAll('\\', '/')}`, import.meta.url), 'utf8'));
    const visit = node => {
      const text = node.type === 2 ? node.content : node.type === 6 ? node.value?.content : '';
      if (/\p{Script=Han}/u.test(text || '')) untranslated.push(`${file}:${node.loc.start.line} ${text.trim()}`);
      for (const child of [...(node.children || []), ...(node.props || [])]) visit(child);
    };
    if (descriptor.template) visit(descriptor.template.ast);
  }
  assert.deepEqual(untranslated, []);
});

test('补齐的筛选和表头切换语言时保持字段、运算符、选项值和接口路径', () => {
  const identity = value => JSON.parse(JSON.stringify(value, (key, item) => ['title', 'label', 'exportName', 'tabName', 'placeholder'].includes(key) ? undefined : item));
  for (const file of ['views/TaskDetail.vue', 'views/AssetSearch.vue', 'views/GroupAssetsDetail.vue']) {
    i18n.global.locale.value = 'zh-CN';
    const config = component(file, { taskText: pageText, assetText: pageText }).read('tabConfig');
    const before = identity(config);
    const fields = config.site.searchFields.filter(field => ['http_server', 'favicon.hash'].includes(field.key));
    assert.equal(fields.length, 2);
    const chinese = fields.map(field => field.label);
    assert.ok(chinese.every(label => /\p{Script=Han}/u.test(label)));
    i18n.global.locale.value = 'en-US';
    assert.deepEqual(plain(fields.map(field => field.label)), ['Web server', 'Favicon hash']);
    assert.deepEqual(identity(config), before);
    if (file.endsWith('TaskDetail.vue')) {
      assert.equal(config.site.cols.find(column => column.key === 'headers').title, 'Headers');
      assert.equal(config.service.cols.find(column => column.key === 'product').title, 'Product');
    }
  }
});

test('指纹分类显示随语言变化，分类标识和查看全部的真实数量保持一致', () => {
  const page = component('views/Dashboard.vue');
  const category = page.read('getFingerCategory');
  page.read('fingerCategoryKeys');
  const label = page.read('formatFingerCategory');
  const names = ['cloudflare', 'nginx', 'Vue', 'spring', 'tomcat', '用户自定义指纹'];
  const classes = names.map(name => category(name).toLowerCase());
  assert.deepEqual(classes, ['cdn', 'server', 'front', 'frame', 'app', 'web']);
  assert.equal(label(category('nginx')), '服务器');
  assert.equal(pageText('tasks.viewAllTotal', { count: 4 }), '查看全部（共 4 项） >>');
  i18n.global.locale.value = 'en-US';
  assert.equal(label(category('nginx')), 'Server');
  assert.equal(label(category('Vue')), 'Frontend');
  assert.equal(pageText('tasks.viewAllTotal', { count: 4 }), 'View all (total: 4) >>');
  assert.deepEqual(names.map(name => category(name).toLowerCase()), classes);
});
