import assert from 'node:assert/strict';
import fs from 'node:fs';
import test, { afterEach } from 'node:test';
import vm from 'node:vm';
import { reactive, ref, watch, nextTick } from 'vue';
import { parse, compileScript } from 'vue/compiler-sfc';
import { i18n } from '../src/i18n/index.js';

const { descriptor } = parse(fs.readFileSync(new URL('../src/components/NucleiManage.vue', import.meta.url), 'utf8'));
const { scriptSetupAst } = compileScript(descriptor, { id: 'components/NucleiManage.vue' });
const bindings = {};
for (const node of scriptSetupAst) {
  if (node.type !== 'VariableDeclaration') continue;
  for (const item of node.declarations) {
    if (item.id.type === 'Identifier' && item.init) {
      bindings[item.id.name] = descriptor.scriptSetup.content.slice(item.init.start, item.init.end);
    }
  }
}

const pageText = (...args) => i18n.global.t(...args);
const plain = (value) => JSON.parse(JSON.stringify(value));
const stops = [];

afterEach(() => {
  stops.splice(0).forEach((stop) => stop());
  i18n.global.locale.value = 'zh-CN';
});

function createContext(overrides = {}) {
  const notices = [];
  const modalConfirms = [];
  const context = vm.createContext({
    pageText,
    reactive,
    ref,
    nextTick,
    console,
    watch: (...args) => {
      const stop = watch(...args);
      stops.push(stop);
      return stop;
    },
    Modal: {
      confirm: (cfg) => modalConfirms.push(cfg),
    },
    message: Object.fromEntries(
      ['success', 'warning', 'error', 'info', 'loading'].map((key) => [
        key,
        (...args) => notices.push({ key, args }),
      ]),
    ),
    skeletonTemplates: vm.runInNewContext(`(${bindings.skeletonTemplates})`),
    isEditModalVisible: ref(false),
    isCreateMode: ref(false),
    currentEditTemplateId: ref(''),
    currentEditorCode: ref(''),
    selectedSkeleton: ref('http_get'),
    createEnable: ref(true),
    saveLoading: ref(false),
    saveErrorMsg: ref(''),
    detailLoading: ref(false),
    detailLoadFailed: ref(false),
    focusDryRunOnOpen: ref(false),
    dryRunPanelRef: ref(null),
    dryRunTargetInputRef: ref(null),
    lastAppliedSkeletonCode: '',
    activeModalSeq: 0,
    activeDryRunSeq: 0,
    dryRunTarget: ref(''),
    dryRunLoading: ref(false),
    dryRunOutput: ref(''),
    dryRunMatched: ref(false),
    dryRunFindings: ref([]),
    dryRunError: ref(''),
    dryRunCost: ref(0),
    fetchCustomTemplates() {},
    fetchStats() {},
    request: { async get() { return { code: 200, data: {} }; }, async post() { return { code: 200, data: {} }; } },
    ...overrides,
  });

  const read = (name) => vm.runInContext(`globalThis.${name} = (${bindings[name]})`, context);
  read('resetDryRunState');
  read('applySkeleton');
  return { context, read, notices, modalConfirms };
}

test('file_leak 预设骨架采用 and 组合条件，避免 HTTP 200 全量误报', () => {
  const { context } = createContext();
  const yaml = context.skeletonTemplates.file_leak;
  assert.match(yaml, /matchers-condition:\s*and/);
  assert.match(yaml, /condition:\s*or/);
  assert.match(yaml, /-\s*200/);
});

test('新建模板支持初始启用开关，且切换预设骨架在已有编辑时弹出覆盖确认', () => {
  const posts = [];
  const { context, read, modalConfirms } = createContext({
    request: {
      async post(url, data) {
        posts.push({ url, data: plain(data) });
        return { code: 200 };
      },
    },
  });

  const openCreateModal = read('openCreateModal');
  const handleSkeletonChange = read('handleSkeletonChange');
  const saveTemplate = read('saveTemplate');

  openCreateModal();
  assert.equal(context.isCreateMode.value, true);
  assert.equal(context.createEnable.value, true);
  assert.equal(context.currentEditorCode.value, context.skeletonTemplates.http_get);

  // 未修改时直接切换不弹窗
  handleSkeletonChange('http_post');
  assert.equal(modalConfirms.length, 0);
  assert.equal(context.selectedSkeleton.value, 'http_post');
  assert.equal(context.currentEditorCode.value, context.skeletonTemplates.http_post);

  // 修改内容后切换触发二次确认；未确认前保留当前内容
  context.currentEditorCode.value += '\n# custom edit\n';
  handleSkeletonChange('dns_check');
  assert.equal(modalConfirms.length, 1);
  assert.equal(context.selectedSkeleton.value, 'http_post');

  // 确认覆盖
  modalConfirms[0].onOk();
  assert.equal(context.selectedSkeleton.value, 'dns_check');
  assert.equal(context.currentEditorCode.value, context.skeletonTemplates.dns_check);

  // 关闭初始启用并保存
  context.createEnable.value = false;
  return saveTemplate().then(() => {
    assert.equal(posts.length, 1);
    assert.equal(posts[0].url, '/nuclei/template/create/');
    assert.equal(posts[0].data.enable, false);
  });
});

test('编辑与快捷调试隔离加载态、旧响应竞态并聚焦 Dry Run 输入框', async () => {
  let resolveA;
  let resolveB;
  let focused = 0;
  let scrolled = 0;
  const { context, read } = createContext({
    dryRunPanelRef: ref({ scrollIntoView() { scrolled += 1; } }),
    dryRunTargetInputRef: ref({ focus() { focused += 1; } }),
    request: {
      get(url, { params }) {
        return new Promise((resolve) => {
          if (params.template_id === 'tpl-a') resolveA = resolve;
          else resolveB = resolve;
        });
      },
    },
  });

  const openEditModal = read('openEditModal');
  const openDryRunDirect = read('openDryRunDirect');

  context.currentEditorCode.value = 'stale-code-from-previous-modal';
  const pA = openEditModal({ template_id: 'tpl-a' });
  // 打开后应立即清空残留源码并置为加载中
  assert.equal(context.currentEditorCode.value, '');
  assert.equal(context.detailLoading.value, true);

  // 快速切换至 tpl-b 快捷调试
  const pB = openDryRunDirect({ template_id: 'tpl-b' });
  assert.equal(context.focusDryRunOnOpen.value, true);

  // 先返回 B，再延迟返回 A：A 必须被丢弃
  resolveB({ code: 200, data: { content: 'id: tpl-b\n' } });
  await pB;
  assert.equal(context.currentEditorCode.value, 'id: tpl-b\n');
  assert.equal(context.detailLoading.value, false);
  assert.equal(scrolled, 1);
  assert.equal(focused, 1);

  resolveA({ code: 200, data: { content: 'id: tpl-a\n' } });
  await pA;
  assert.equal(context.currentEditorCode.value, 'id: tpl-b\n');
});

test('Dry Run 校验空模板、正确回显命中摘要及非 200 错误日志', async () => {
  const replies = [
    {
      code: 200,
      data: {
        matched: true,
        matched_count: 1,
        findings: [{ template_id: 'demo', severity: 'high', matched_at: 'http://127.0.0.1:8080/hit', extracted_results: ['v1'] }],
        output: '[demo] [http] [high] http://127.0.0.1:8080/hit',
        cost_seconds: 0.42,
      },
    },
    {
      code: 999,
      message: 'Nuclei 执行失败: no templates provided',
      data: {
        output: '[FTL] Could not run nuclei: no templates provided',
        cost_seconds: 0.15,
      },
    },
  ];

  const { context, read, notices } = createContext({
    isEditModalVisible: ref(true),
    request: {
      async post() {
        return replies.shift();
      },
    },
  });

  const executeDryRun = read('executeDryRun');

  // 空模板拦截
  context.currentEditorCode.value = '   ';
  context.dryRunTarget.value = 'http://127.0.0.1:8080';
  await executeDryRun();
  assert.equal(notices.at(-1).key, 'warning');

  // 正常命中
  context.currentEditorCode.value = 'id: demo\n';
  await executeDryRun();
  assert.equal(context.dryRunMatched.value, true);
  assert.equal(context.dryRunFindings.value.length, 1);
  assert.equal(context.dryRunError.value, '');
  assert.equal(context.dryRunCost.value, 0.42);

  // 非 200 报错同时保留错误提示与控制台原始诊断输出
  await executeDryRun();
  assert.equal(context.dryRunMatched.value, false);
  assert.equal(context.dryRunFindings.value.length, 0);
  assert.match(context.dryRunError.value, /Nuclei 执行失败/);
  assert.match(context.dryRunOutput.value, /Could not run nuclei/);
  assert.equal(context.dryRunCost.value, 0.15);
});
