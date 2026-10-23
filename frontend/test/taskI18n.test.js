import assert from 'node:assert/strict';
import fs from 'node:fs';
import test, { afterEach } from 'node:test';
import vm from 'node:vm';
import { computed, reactive, ref } from 'vue';
import { parse, compileScript, babelParse } from 'vue/compiler-sfc';
import { i18n } from '../src/i18n/index.js';
import zh from '../src/i18n/tasks.zh-CN.js';
import en from '../src/i18n/tasks.en-US.js';
import allZh from '../src/i18n/zh-CN.js';
import allEn from '../src/i18n/en-US.js';
import { TASK_STATUS_LABEL, PLUGIN_NAME_MAP, formatTaskStatus, formatTaskStatusColor } from '../src/constants/taskStatus.js';
import { buildAssetFilterParams, formatAssetFilterOperator } from '../src/utils/assetFilters.js';
import { describeTaskFanout } from '../src/utils/targetParse.js';
import { getTaskAssetGroupState } from '../src/utils/taskAssetGroups.js';

const taskText = (...args) => i18n.global.t(...args);
const plain = value => JSON.parse(JSON.stringify(value));
afterEach(() => { i18n.global.locale.value = 'zh-CN'; });

function component(file, initial = {}) {
  const { descriptor } = parse(fs.readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8'));
  const { scriptSetupAst } = compileScript(descriptor, { id: file });
  const bindings = {};
  for (const node of scriptSetupAst) {
    if (node.type !== 'VariableDeclaration') continue;
    for (const item of node.declarations) {
      if (item.id.type === 'Identifier' && item.init) bindings[item.id.name] = descriptor.scriptSetup.content.slice(item.init.start, item.init.end);
    }
  }
  const context = vm.createContext({ taskText, computed, reactive, ref, ...initial });
  return {
    context,
    read(name) {
      assert.ok(bindings[name], `${file}: ${name}`);
      vm.runInContext(`globalThis.${name} = ${bindings[name]}`, context);
      return context[name];
    },
  };
}

test('任务语言包均能渲染，所有参数保留原值，英文没有遗漏的中文文案', () => {
  for (const [locale, messages] of [['zh-CN', zh], ['en-US', en]]) {
    i18n.global.locale.value = locale;
    for (const [key, message] of Object.entries(messages)) {
      const params = Object.fromEntries([...message.matchAll(/\{(\w+)\}/g)].map(([, name]) => [name, `fixture_${name}`]));
      const text = taskText(`tasks.${key}`, params);
      assert.notEqual(text, `tasks.${key}`, key);
      for (const value of Object.values(params)) assert.ok(text.includes(value), `${locale}: ${key}`);
      if (locale === 'en-US') assert.doesNotMatch(text, /\p{Script=Han}/u, key);
    }
  }
});

test('任务组件的翻译引用及插值参数与语言包一致', () => {
  const files = ['views/TaskList.vue', 'views/TaskDetail.vue', 'views/PlanningTasks.vue',
    'components/EnterpriseTaskDetailPanel.vue', 'components/TycTaskModal.vue', 'components/SyncToScopeModal.vue',
    'components/ServiceDetailModal.vue', 'components/CidrDetailModal.vue', 'components/AssetScopeSelect.vue', 'components/HttpStatusFilter.vue'];
  for (const file of files) {
    const source = fs.readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8');
    // 分别解析模板表达式与脚本，检查调用时提供的具名参数。
    const { descriptor } = parse(source);
    const check = node => {
      if (!node || typeof node !== 'object') return;
      if (node.type === 'CallExpression' && node.callee.name === 'taskText' && node.arguments[0].type === 'StringLiteral') {
        const key = node.arguments[0].value;
        const messages = [allZh, allEn].map(bundle => key.split('.').reduce((value, part) => value?.[part], bundle));
        for (const message of messages) assert.equal(typeof message, 'string', `${file}: ${key}`);
        const expected = [...new Set([...messages[1].matchAll(/\{(\w+)\}/g)].map(([, name]) => name))].sort();
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
        if (node.content.includes('taskText(')) check(babelParse(`(${node.content})`, { sourceType: 'module' }));
        return;
      }
      for (const child of [...(node.children || []), ...(node.props || [])]) template(child);
      if (node.exp) template(node.exp);
      if (node.type === 5) template(node.content);
    };
    template(descriptor.template.ast);
  }
});

test('已创建的任务表格、计划表格和企业结果列名随语言切换更新', () => {
  const cases = [
    ['views/TaskList.vue', 'enterpriseColumns'], ['views/TaskList.vue', 'columns'],
    ['views/PlanningTasks.vue', 'columns'], ['views/PlanningTasks.vue', 'monitorColumns'],
    ['components/EnterpriseTaskDetailPanel.vue', 'webColumns'], ['components/ServiceDetailModal.vue', 'columns'],
    ['components/EnterpriseTaskDetailPanel.vue', 'kappColumns'],
  ];
  for (const [file, name] of cases) {
    i18n.global.locale.value = 'zh-CN';
    const columns = component(file).read(name);
    const titles = computed(() => columns.map(column => column.title));
    const chinese = titles.value;
    const fields = columns.map(({ key, dataIndex }) => ({ key, dataIndex }));
    i18n.global.locale.value = 'en-US';
    assert.notDeepEqual(titles.value, chinese, file);
    assert.deepEqual(columns.map(({ key, dataIndex }) => ({ key, dataIndex })), fields);
    i18n.global.locale.value = 'zh-CN';
    assert.deepEqual(titles.value, chinese, file);
  }
});

test('切换语言只改变状态及阶段名称，状态标识、颜色和同步目标不变', () => {
  const status = computed(() => formatTaskStatus('port_scan'));
  const task = { status: 'done', sync_status: 'error', sync_scope_id: 'group-a', sync_scope_name: '用户资产组', sync_error: '后端原始错误' };
  const sync = computed(() => getTaskAssetGroupState(task));
  assert.equal(status.value, '进行中 · 端口扫描');
  assert.equal(sync.value.text, '同步失败');
  i18n.global.locale.value = 'en-US';
  assert.equal(status.value, 'In progress · Port scan');
  assert.equal(TASK_STATUS_LABEL.done, 'Completed');
  assert.equal(PLUGIN_NAME_MAP.port_scan, 'Port scan');
  assert.equal(formatTaskStatusColor('done'), 'success');
  assert.equal(formatTaskStatusColor('port_scan'), 'default');
  assert.deepEqual(sync.value, { id: 'group-a', label: '用户资产组', color: 'error', text: 'Sync failed', error: '后端原始错误' });
});

test('任务筛选字段保留历史运算符，语言切换不改变请求参数', () => {
  const config = component('views/TaskDetail.vue').read('tabConfig');
  const fields = config.stat_finger.searchFields;
  const finger = fields.find(field => field.key === 'name');
  assert.ok(finger);
  finger.operator = '精确匹配';
  const form = { name: '用户指纹' };
  const chinese = plain(buildAssetFilterParams(form, fields));
  i18n.global.locale.value = 'en-US';
  assert.equal(formatAssetFilterOperator(finger.operator), 'Exact match');
  assert.equal(finger.operator, '精确匹配');
  assert.deepEqual(plain(buildAssetFilterParams(form, fields)), chinese);
  assert.deepEqual(chinese, { name__eq: '用户指纹' });
});

test('混合 IP 和域名的任务拆分保持一致，仅预告文字改变', () => {
  const hint = computed(() => describeTaskFanout('192.0.2.1, 192.0.2.0/24, example.test, example.test, other.test'));
  assert.equal(hint.value.taskCount, 3);
  assert.equal(hint.value.total, 4);
  const chinese = hint.value.text;
  i18n.global.locale.value = 'en-US';
  assert.equal(hint.value.taskCount, 3);
  assert.equal(hint.value.total, 4);
  assert.notEqual(hint.value.text, chinese);
  assert.match(hint.value.text, /combined into one task/);
  assert.match(hint.value.text, /Tasks to create: 3/);
});

test('HTTP 状态码选项和表单校验提示响应语言变化，选项值和错误范围不变', () => {
  const fixture = component('components/HttpStatusFilter.vue');
  fixture.read('descriptionKeys');
  const options = fixture.read('options');
  assert.equal(options.value[100].label, '200 成功');
  const values = options.value.map(option => option.value);
  const rules = component('components/TycTaskModal.vue').read('rules');
  const chinese = rules.rawTarget[0].message;
  i18n.global.locale.value = 'en-US';
  assert.equal(options.value[100].label, '200 OK');
  assert.deepEqual(options.value.map(option => option.value), values);
  assert.notEqual(rules.rawTarget[0].message, chinese);
  assert.throws(() => buildAssetFilterParams({ status: '600' }, [{ key: 'status', type: 'httpStatus' }]), /100 to 599/);
});

test('中英文提交使用相同的扫描配置、计划类型、时间和用户输入', async () => {
  const scanForm = { name: '用户任务', target: 'example.test\n192.0.2.0/24', related_scope_id: 'group-a',
    port_scan: true, service_detection: true, nuclei_scan: false, skip_scan_cdn_ip: true,
    domain_brute_type: 'domain_top300.txt', port_scan_type: 'port_top100.txt' };
  const scheduleForm = { name: '用户计划', target: 'example.test', schedule_type: 'cycle_scan',
    cron: '0 0 * * *', policy_id: 'policy-a', task_tag: 'domain' };
  const results = [];
  for (const locale of ['zh-CN', 'en-US']) {
    i18n.global.locale.value = locale;
    const calls = [];
    const initial = {
      request: { async post(url, payload) { calls.push({ url, payload: plain(payload) }); return { code: 200 }; } },
      message: { success() {}, error(error) { assert.fail(error); } },
    };
    const scan = component('views/TaskList.vue', { ...initial, formState: { ...scanForm }, submitLoading: ref(false),
      visible: ref(true), pagination: { pageSize: 20 }, fetchTasks() {} });
    await scan.read('doSubmitTask')();
    const plan = component('views/PlanningTasks.vue', { ...initial, addForm: { ...scheduleForm },
      addFormRef: ref({ validate: async () => {} }), addLoading: ref(false), addModalVisible: ref(true), onPlanSearch() {} });
    await plan.read('submitAdd')();
    results.push(calls);
  }
  assert.deepEqual(results[1], results[0]);
  assert.deepEqual(results[0], [
    { url: '/task/', payload: { ...scanForm, npoc_service_detection: true } },
    { url: '/task_schedule/', payload: scheduleForm },
  ]);
});
