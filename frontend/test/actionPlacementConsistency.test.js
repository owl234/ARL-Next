import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { ref, reactive, computed, watch } from 'vue';
import { parse, compileScript } from 'vue/compiler-sfc';
import zh from '../src/i18n/zh-CN.js';
import en from '../src/i18n/en-US.js';
import ru from '../src/i18n/ru-RU.js';

function loadAst(relPath) {
  const src = fs.readFileSync(new URL(`../src/${relPath}`, import.meta.url), 'utf8');
  return parse(src).descriptor.template.ast;
}

function getStaticClass(node) {
  const clsProp = (node.props || []).find(p => p.type === 6 && p.name === 'class');
  return clsProp?.value?.content ? clsProp.value.content.split(/\s+/) : [];
}

function getAttr(node, name) {
  const prop = (node.props || []).find(p => p.type === 6 && p.name === name);
  return prop?.value?.content ?? null;
}

function findElements(node, predicate, out = []) {
  if (!node) return out;
  if (node.type === 1 && predicate(node)) out.push(node);
  for (const child of node.children || []) {
    findElements(child, predicate, out);
  }
  if (node.type === 9) {
    for (const branch of node.branches || []) {
      findElements(branch, predicate, out);
    }
  }
  return out;
}

function isPrimaryButton(node) {
  if (node.type !== 1 || node.tag !== 'a-button' || getAttr(node, 'type') !== 'primary') return false;
  const hasGhost = (node.props || []).some(p => p.name === 'ghost');
  return !hasGhost;
}

function getDirectiveName(node) {
  for (const p of node.props || []) {
    if (p.type === 7 && ['if', 'else-if', 'else'].includes(p.name)) return p.name;
  }
  return null;
}

function collectBranches(children, prefix = []) {
  // Recursively expand v-if / v-else-if / v-else sibling chains into concrete visible button sequences
  const sequences = [[]];
  for (let i = 0; i < (children || []).length; ) {
    const ch = children[i];
    if (ch.type !== 1) { i++; continue; }
    const dir = getDirectiveName(ch);
    if (dir === 'if') {
      const chain = [ch];
      let j = i + 1;
      while (j < children.length) {
        const next = children[j];
        if (next.type === 2 || next.type === 3) { j++; continue; }
        if (next.type === 1 && ['else-if', 'else'].includes(getDirectiveName(next))) {
          chain.push(next);
          j++;
          continue;
        }
        break;
      }
      const nextSequences = [];
      for (const base of sequences) {
        for (const branchNode of chain) {
          const branchBtnPaths = branchNode.tag === 'a-button'
            ? [[branchNode]]
            : collectBranches(branchNode.children || []);
          for (const bp of branchBtnPaths) nextSequences.push([...base, ...bp]);
        }
      }
      sequences.splice(0, sequences.length, ...nextSequences);
      i = j;
      continue;
    }
    const subPaths = ch.tag === 'a-button' ? [[ch]] : collectBranches(ch.children || []);
    const nextSequences = [];
    for (const base of sequences) {
      for (const sp of subPaths) nextSequences.push([...base, ...sp]);
    }
    sequences.splice(0, sequences.length, ...nextSequences);
    i++;
  }
  return sequences;
}

function assertPrimaryIsLastInContainer(container, label) {
  const sequences = collectBranches(container.children || []);
  for (const btns of sequences) {
    const primaryIndices = btns.map((b, idx) => (isPrimaryButton(b) ? idx : -1)).filter(idx => idx !== -1);
    if (primaryIndices.length === 0) continue;
    assert.equal(primaryIndices.length, 1, `${label}: expected at most 1 primary button per visible state, got ${primaryIndices.length}`);
    assert.equal(
      primaryIndices[0],
      btns.length - 1,
      `${label}: primary button must be the last (far-right) <a-button> in its action bar, got index ${primaryIndices[0]} of ${btns.length}`
    );
  }
}

test('多页签页面统一使用顶栏胶囊切换，且主创建按钮固定在顶栏最右侧无下方重复入口', () => {
  const multiTabPages = [
    'views/TaskList.vue',
    'views/GithubManage.vue',
    'views/PlanningTasks.vue',
    'views/PocList.vue',
    'components/NucleiManage.vue',
  ];

  for (const relPath of multiTabPages) {
    const ast = loadAst(relPath);
    const heroBars = findElements(ast, n => getStaticClass(n).includes('arl-hero-unified-bar'));
    assert.equal(heroBars.length, 1, `${relPath}: expected single .arl-hero-unified-bar`);

    const heroRights = findElements(heroBars[0], n => getStaticClass(n).includes('arl-hero-right'));
    assert.equal(heroRights.length, 1, `${relPath}: expected single .arl-hero-right`);
    assertPrimaryIsLastInContainer(heroRights[0], `${relPath} (.arl-hero-right)`);

    const toolbars = findElements(ast, n => getStaticClass(n).includes('arl-toolbar-row'));
    for (const tb of toolbars) {
      const primaryInToolbar = findElements(tb, isPrimaryButton);
      assert.equal(
        primaryInToolbar.length,
        0,
        `${relPath}: .arl-toolbar-row should only hold filters/batch utilities, found ${primaryInToolbar.length} primary button(s)`
      );
    }
  }
});

test('单表页 Policy 与 Fingerprint 将主新建按钮锚定在操作组最右端', () => {
  for (const relPath of ['views/Policy.vue', 'views/Fingerprint.vue']) {
    const ast = loadAst(relPath);
    const actionGroups = findElements(ast, n => getStaticClass(n).includes('arl-actions-group'));
    assert.equal(actionGroups.length, 1, `${relPath}: expected single .arl-actions-group`);
    const buttons = findElements(actionGroups[0], n => n.tag === 'a-button');
    assert.ok(buttons.length >= 2, `${relPath}: expected primary + batch/secondary buttons`);
    assert.equal(
      isPrimaryButton(buttons[buttons.length - 1]),
      true,
      `${relPath}: far-right button in .arl-actions-group must be type="primary"`
    );
  }
});

test('创建动词术语在三语语言包中完整同步且中文统一为「新建」口径', () => {
  assert.equal(zh.tasks.addScheduledTask, '新建计划任务');
  assert.equal(zh.pages.addPolicy, '新建监控策略');
  assert.equal(zh.pages.addFingerprint, '新建指纹');

  for (const bundle of [zh, en, ru]) {
    assert.ok(bundle.navigation.schedules);
    assert.ok(bundle.navigation.pocs);
    assert.ok(bundle.tasks.addScheduledTask);
    assert.ok(bundle.pages.addPolicy);
    assert.ok(bundle.pages.addFingerprint);
  }
});

test('PlanningTasks 与 PocList 胶囊切换可联动更新视图状态与路由 query', () => {
  const replaced = [];
  const loadView = (relPath, exposeList, extra = {}) => {
    const src = fs.readFileSync(new URL(`../src/${relPath}`, import.meta.url), 'utf8');
    const { descriptor } = parse(src);
    const { scriptSetupAst } = compileScript(descriptor, { id: relPath });
    let body = descriptor.scriptSetup.content;
    for (const node of [...scriptSetupAst].reverse()) {
      if (node.type === 'ImportDeclaration') body = body.slice(0, node.start) + body.slice(node.end);
    }
    const ctx = vm.createContext({
      ref, reactive, computed, watch, console,
      localStorage: { getItem: () => '' },
      createVNode: () => ({}),
      defineOptions: () => {},
      useI18n: () => ({ t: k => k, locale: ref('zh-CN') }),
      useRoute: () => ({ query: {} }),
      useRouter: () => ({ replace: arg => replaced.push(JSON.parse(JSON.stringify(arg))), push: () => {} }),
      useSticky: () => ({ stickyConfig: computed(() => false) }),
      useGlobalPageSize: () => ref(10),
      onMounted: () => {},
      onDeactivated: () => {},
      request: { get: async () => ({ code: 200, items: [], total: 0 }), post: async () => ({ code: 200 }) },
      message: { success() {}, error() {}, warning() {} },
      Modal: { confirm() {} },
      NucleiManage: {},
      Codemirror: {},
      python: () => ({}),
      oneDark: {},
      dayjs: () => ({}),
      formatTaskStatus: s => s,
      ExclamationCircleOutlined: {}, SearchOutlined: {}, InboxOutlined: {}, LinkOutlined: {},
      SyncOutlined: {}, DownloadOutlined: {}, PlusOutlined: {}, UploadOutlined: {},
      DeleteOutlined: {}, UndoOutlined: {}, PauseCircleOutlined: {}, PlayCircleOutlined: {},
      SendOutlined: {}, ReloadOutlined: {}, ClockCircleOutlined: {}, RadarChartOutlined: {},
      ...extra,
    });
    return vm.runInContext(`${body}\n;({ ${exposeList.join(', ')} });`, ctx);
  };

  const plan = loadView('views/PlanningTasks.vue', ['activeTab', 'onTabChange', 'refreshActiveTab'], {
    fetchMonitorData: () => {},
    fetchPlanData: () => {},
  });
  assert.equal(plan.activeTab.value, 'planning');
  plan.onTabChange('monitor');
  assert.equal(plan.activeTab.value, 'monitor');
  assert.deepEqual(replaced.at(-1), { query: { tab: 'monitor' } });

  const poc = loadView('views/PocList.vue', ['mainTab', 'hasVisitedNuclei', 'switchMainTab']);
  assert.equal(poc.mainTab.value, 'arl');
  assert.equal(poc.hasVisitedNuclei.value, false);
  poc.switchMainTab('nuclei');
  assert.equal(poc.mainTab.value, 'nuclei');
  assert.equal(poc.hasVisitedNuclei.value, true);
  assert.deepEqual(replaced.at(-1), { query: { tab: 'nuclei' } });
});
