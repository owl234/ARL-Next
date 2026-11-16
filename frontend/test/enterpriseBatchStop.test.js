import assert from 'node:assert/strict';
import fs from 'node:fs';
import test, { afterEach } from 'node:test';
import vm from 'node:vm';
import { ref } from 'vue';
import { parse, compileScript } from 'vue/compiler-sfc';
import { i18n } from '../src/i18n/index.js';

const taskText = (...args) => i18n.global.t(...args);
const plain = (value) => JSON.parse(JSON.stringify(value));

afterEach(() => {
  i18n.global.locale.value = 'zh-CN';
});

function loadEnterpriseBatchStopContext(initial = {}) {
  const raw = fs.readFileSync(new URL('../src/views/TaskList.vue', import.meta.url), 'utf8');
  const { descriptor } = parse(raw);
  const { scriptSetupAst } = compileScript(descriptor, { id: 'TaskList.vue' });
  const content = descriptor.scriptSetup.content;
  const declarations = new Map();

  for (const node of scriptSetupAst) {
    if (node.type !== 'VariableDeclaration') continue;
    for (const decl of node.declarations) {
      if (decl.id.type === 'Identifier' && decl.init) {
        declarations.set(decl.id.name, {
          kind: node.kind,
          initCode: content.slice(decl.init.start, decl.init.end),
        });
      }
    }
  }

  const context = vm.createContext({
    ref,
    taskText,
    createVNode: (type, props, children) => ({ type, props, children }),
    ExclamationCircleOutlined: 'ExclamationCircleOutlined',
    ...initial,
  });

  for (const name of [
    'enterpriseBatchStopping',
    'handleBatchStopEnterprise',
    'executeBatchStopEnterprise',
  ]) {
    const entry = declarations.get(name);
    assert.ok(entry, `Missing binding in TaskList.vue: ${name}`);
    vm.runInContext(
      `${entry.kind === 'let' ? 'let' : 'const'} ${name} = (${entry.initCode}); globalThis.${name} = ${name};`,
      context
    );
  }

  return { raw, context };
}

function collectVNodeText(node) {
  if (node == null) return '';
  if (typeof node === 'string' || typeof node === 'number') return String(node);
  if (Array.isArray(node)) return node.map(collectVNodeText).join('\n');
  if (typeof node === 'object') return collectVNodeText(node.children);
  return '';
}

test('TaskList.vue 企业测绘浮动批量操作条包含批量停止按钮与防重加载绑定', () => {
  const raw = fs.readFileSync(new URL('../src/views/TaskList.vue', import.meta.url), 'utf8');
  const enterpriseBarMatch = raw.match(
    /<template v-if="activeMainTab === 'enterprise'">([\s\S]*?)<\/template>\s*<!-- 资产侦查批量操作 -->/
  );
  assert.ok(enterpriseBarMatch, 'Should find enterprise batch action bar template');
  const enterpriseBar = enterpriseBarMatch[1];
  assert.match(enterpriseBar, /@click="handleBatchStopEnterprise"/);
  assert.match(enterpriseBar, /:loading="enterpriseBatchStopping"/);
  assert.match(enterpriseBar, /:disabled="enterpriseBatchStopping"/);
  assert.match(enterpriseBar, /taskText\('tasks\.stopSelected'\)/);
});

test('全选终态任务时拦截弹出确认框且不发送停止请求', async () => {
  const warnings = [];
  const confirms = [];
  const posts = [];

  const { context } = loadEnterpriseBatchStopContext({
    enterpriseSelectedRowKeys: ref(['t-done', 't-stop']),
    enterpriseTaskList: ref([
      { _id: 't-done', name: '已完成企业', status: 'done' },
      { _id: 't-stop', name: '已停止企业', status: 'stop' },
    ]),
    enterpriseTaskCache: new Map([
      ['t-done', { _id: 't-done', name: '已完成企业', status: 'done' }],
      ['t-stop', { _id: 't-stop', name: '已停止企业', status: 'stop' }],
    ]),
    enterprisePagination: { current: 1, pageSize: 10 },
    fetchEnterpriseTasks: async () => {},
    request: {
      post: async (url, payload) => {
        posts.push({ url, payload });
        return { code: 200, data: {} };
      },
    },
    Modal: { confirm: (opts) => confirms.push(opts) },
    message: {
      warning: (msg) => warnings.push(msg),
      loading: () => {},
      success: () => {},
      error: () => {},
      info: () => {},
    },
  });

  context.handleBatchStopEnterprise();
  assert.equal(warnings.length, 1);
  assert.equal(warnings[0], '所选任务均已结束，无需停止');
  assert.equal(confirms.length, 0);
  assert.equal(posts.length, 0);
});

test('混选含跨页活跃与终态任务时：弹窗列出清单与副作用说明，确认后调用 /icp/batch_stop/', async () => {
  const confirms = [];
  const posts = [];
  const successes = [];
  const fetchCalls = [];
  const cache = new Map([
    ['t-run-visible', { _id: 't-run-visible', name: '当前页企业A', status: 'running' }],
    ['t-wait-other', { _id: 't-wait-other', name: '跨页企业B', status: 'waiting' }],
    ['t-done', { _id: 't-done', name: '已完成企业C', status: 'done' }],
  ]);
  const selectedKeys = ref(['t-run-visible', 't-wait-other', 't-done']);

  const { context } = loadEnterpriseBatchStopContext({
    enterpriseSelectedRowKeys: selectedKeys,
    enterpriseTaskList: ref([
      { _id: 't-run-visible', name: '当前页企业A', status: 'running' },
      { _id: 't-done', name: '已完成企业C', status: 'done' },
    ]),
    enterpriseTaskCache: cache,
    enterprisePagination: { current: 2, pageSize: 20 },
    fetchEnterpriseTasks: async (page, size) => fetchCalls.push({ page, size }),
    request: {
      post: async (url, payload) => {
        posts.push({ url, payload });
        return {
          code: 200,
          data: {
            total: 3,
            stopped_count: 2,
            skipped_count: 1,
            failed_count: 0,
            stopped_ids: ['t-run-visible', 't-wait-other'],
            skipped_ids: ['t-done'],
            failed_ids: [],
          },
        };
      },
    },
    Modal: { confirm: (opts) => confirms.push(opts) },
    message: {
      warning: () => {},
      loading: () => {},
      success: (opts) => successes.push(opts),
      error: () => {},
      info: () => {},
    },
  });

  context.handleBatchStopEnterprise();
  assert.equal(confirms.length, 1);
  const modalText = collectVNodeText(confirms[0].content);
  assert.match(modalText, /当前页企业A/);
  assert.match(modalText, /跨页企业B/);
  assert.doesNotMatch(modalText, /已完成企业C/);
  assert.match(modalText, /自动跳过/);
  assert.match(modalText, /不会自动建组或纳管资产/);
  assert.match(modalText, /来自其他页/);

  await confirms[0].onOk();
  assert.deepEqual(plain(posts), [
    { url: '/icp/batch_stop/', payload: { task_ids: ['t-run-visible', 't-wait-other', 't-done'] } },
  ]);
  assert.deepEqual(plain(selectedKeys.value), []);
  assert.equal(cache.get('t-run-visible').status, 'stop');
  assert.equal(cache.get('t-wait-other').status, 'stop');
  assert.equal(successes.length, 1);
  assert.deepEqual(plain(fetchCalls), [{ page: 2, size: 20 }]);
  assert.equal(context.enterpriseBatchStopping.value, false);
});

test('部分停止失败时：提示警告并仅保留 failed_ids 选中状态便于重试', async () => {
  const warnings = [];
  const selectedKeys = ref(['t-ok', 't-fail', 't-done']);
  const cache = new Map([
    ['t-ok', { _id: 't-ok', name: '成功停止任务', status: 'running' }],
    ['t-fail', { _id: 't-fail', name: '失败任务', status: 'running' }],
    ['t-done', { _id: 't-done', name: '已完成任务', status: 'done' }],
  ]);

  const { context } = loadEnterpriseBatchStopContext({
    enterpriseSelectedRowKeys: selectedKeys,
    enterpriseTaskList: ref([...cache.values()]),
    enterpriseTaskCache: cache,
    enterprisePagination: { current: 1, pageSize: 10 },
    fetchEnterpriseTasks: async () => {},
    request: {
      post: async () => ({
        code: 200,
        data: {
          total: 3,
          stopped_count: 1,
          skipped_count: 1,
          failed_count: 1,
          stopped_ids: ['t-ok'],
          skipped_ids: ['t-done'],
          failed_ids: ['t-fail'],
        },
      }),
    },
    Modal: { confirm: () => {} },
    message: {
      warning: (opts) => warnings.push(opts),
      loading: () => {},
      success: () => {},
      error: () => {},
      info: () => {},
    },
  });

  await context.executeBatchStopEnterprise(['t-ok', 't-fail', 't-done']);
  assert.equal(warnings.length, 1);
  assert.match(warnings[0].content, /已停止 1 项，跳过 1 项，失败 1 项/);
  assert.deepEqual(plain(selectedKeys.value), ['t-fail']);
  assert.equal(context.enterpriseBatchStopping.value, false);
});
