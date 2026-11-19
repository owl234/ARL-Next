import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { parse, compileScript } from 'vue/compiler-sfc';
import { ref, computed, reactive, nextTick } from 'vue';

const plain = (val) => JSON.parse(JSON.stringify(val));

function loadSystemSettings() {
  const filePath = new URL('../src/views/SystemSettings.vue', import.meta.url);
  const content = fs.readFileSync(filePath, 'utf8');
  const { descriptor } = parse(content);
  const { scriptSetupAst } = compileScript(descriptor, { id: 'SystemSettings.vue' });
  const bindings = {};
  for (const node of scriptSetupAst) {
    if (node.type === 'VariableDeclaration') {
      for (const item of node.declarations) {
        if (item.id.type === 'Identifier' && item.init) {
          bindings[item.id.name] = descriptor.scriptSetup.content.slice(item.init.start, item.init.end);
        }
      }
    }
  }

  const notices = [];
  const context = vm.createContext({
    pageText: (key, params) => `${key}${params ? JSON.stringify(params) : ''}`,
    computed,
    reactive,
    ref,
    nextTick,
    console,
    pageLocale: 'zh-CN',
    message: {
      success: (msg) => notices.push({ type: 'success', msg }),
      error: (msg) => notices.push({ type: 'error', msg }),
      warning: (msg) => notices.push({ type: 'warning', msg }),
      info: (msg) => notices.push({ type: 'info', msg }),
    },
    route: { query: {} },
    router: { push() {} },
    proxyPanelRef: ref(null),
    cdnPanelRef: ref(null),
  });

  const read = (name) => {
    assert.ok(bindings[name], `Missing binding ${name}`);
    return vm.runInContext(`globalThis.${name} = (${bindings[name]})`, context);
  };

  return { descriptor, bindings, context, notices, read };
}

test('SystemSettings: 性能与安全初始基线完全对齐，未初始化时门禁隔离', () => {
  const { read, context } = loadSystemSettings();

  // 1. 读取基础依赖
  read('isConfigInitialized');
  read('GENERAL_FIELD_GROUPS');
  read('cloneDeep');
  read('generalForm');
  read('generalBaseline');
  read('captureBaseline');
  context.captureBaseline();
  read('changedFields');
  read('pendingByGroup');

  read('securityForm');
  read('securityBaseline');
  read('isSecurityDirty');

  read('performanceForm');
  read('performanceBaseline');
  read('isPerformanceDirty');

  read('isSectionRefDirty');
  read('SECTION_SPECS');
  read('dirtySections');
  read('hasUnsavedChanges');
  read('unsavedCount');

  // 初始状态下：isConfigInitialized 为 false
  assert.equal(context.isConfigInitialized.value, false);

  // performanceForm 与 performanceBaseline 均具备完整 4 个字段且相等
  assert.deepEqual(plain(context.performanceForm.value), {
    celery_heavy_concurrency: 1,
    celery_light_concurrency: 1,
    osint_concurrency: 1,
    github_concurrency: 1,
  });
  assert.deepEqual(plain(context.performanceBaseline.value), {
    celery_heavy_concurrency: 1,
    celery_light_concurrency: 1,
    osint_concurrency: 1,
    github_concurrency: 1,
  });
  assert.equal(context.isPerformanceDirty.value, false);
  assert.equal(context.isSecurityDirty.value, false);

  // 门禁隔离：isConfigInitialized 为 false 时，hasUnsavedChanges 恒为 false，unsavedCount 恒为 0
  assert.equal(context.hasUnsavedChanges.value, false);
  assert.equal(context.unsavedCount.value, 0);

  // 人为引入脏数据（例如用户在异步加载前误触发变更）
  context.performanceForm.value.celery_heavy_concurrency = 5;
  assert.equal(context.isPerformanceDirty.value, true);
  // 此时门禁依然生效，阻断提示与拦截
  assert.equal(context.hasUnsavedChanges.value, false);
  assert.equal(context.unsavedCount.value, 0);

  // 当首轮加载完成
  context.isConfigInitialized.value = true;
  assert.equal(context.hasUnsavedChanges.value, true);
  assert.equal(context.unsavedCount.value, 1);
});

test('SystemSettings: applyRecommended 正确映射字段名并触发脏状态响应', () => {
  const { read, context, notices } = loadSystemSettings();

  read('isConfigInitialized');
  read('capacityInfo');
  read('performanceForm');
  read('performanceBaseline');
  read('isPerformanceDirty');
  read('RECOMMENDED_FIELD_MAP');
  read('applyRecommended');

  context.isConfigInitialized.value = true;
  context.capacityInfo.value = {
    heavy_recommended: 4,
    light_recommended: 8,
    osint_recommended: 2,
    github_recommended: 6,
  };

  // 应用 heavy 推荐值
  context.applyRecommended(context.performanceForm, 'heavy');
  assert.equal(context.performanceForm.value.celery_heavy_concurrency, 4);
  assert.equal(context.isPerformanceDirty.value, true);
  assert.equal(notices[0].type, 'success');

  // 应用 light 推荐值
  context.applyRecommended(context.performanceForm, 'light');
  assert.equal(context.performanceForm.value.celery_light_concurrency, 8);

  // 应用 osint 推荐值
  context.applyRecommended(context.performanceForm, 'osint');
  assert.equal(context.performanceForm.value.osint_concurrency, 2);

  // 应用 github 推荐值
  context.applyRecommended(context.performanceForm, 'github');
  assert.equal(context.performanceForm.value.github_concurrency, 6);
});

test('SystemSettings: firstDirtyTabKey 与 goToFirstDirty 正确支持 5 大主域与二级 Tab 导航', async () => {
  const { read, context } = loadSystemSettings();

  read('isConfigInitialized');
  read('GENERAL_FIELD_GROUPS');
  read('cloneDeep');
  read('generalForm');
  read('generalBaseline');
  read('captureBaseline');
  context.captureBaseline();
  read('changedFields');
  read('pendingByGroup');

  read('securityForm');
  read('securityBaseline');
  read('isSecurityDirty');

  read('performanceForm');
  read('performanceBaseline');
  read('isPerformanceDirty');

  context.activeKey = ref('intel');
  context.guardrailSubTab = ref('proxy');
  context.arsenalSubTab = ref('concurrency');
  context.opsSubTab = ref('auth_infra');
  context.visitedDomains = reactive({
    intel: true,
    egress_guardrails: false,
    scanning_arsenal: true,
    notifications: true,
    system_ops: false,
  });
  context.visitedSubTabs = reactive({
    proxy: false,
    cdn: false,
    backup: false,
    update: false,
  });
  read('markVisitedState');
  read('applyDomainAndSubTab');

  read('isSectionRefDirty');
  read('SECTION_SPECS');
  read('dirtySections');
  read('navigateToSection');
  read('firstDirtyTabKey');
  read('goToFirstDirty');

  context.isConfigInitialized.value = true;

  // 1. 当 performanceDirty 时 -> scanning_arsenal / concurrency
  context.performanceForm.value.celery_heavy_concurrency = 3;
  assert.equal(context.firstDirtyTabKey.value, 'scanning_arsenal');
  context.goToFirstDirty();
  assert.equal(context.activeKey.value, 'scanning_arsenal');
  assert.equal(context.arsenalSubTab.value, 'concurrency');

  // 还原
  context.performanceForm.value.celery_heavy_concurrency = 1;

  // 2. 当 securityDirty 时 -> egress_guardrails / security
  context.securityForm.value.blackIpsText = '10.0.0.1';
  assert.equal(context.firstDirtyTabKey.value, 'egress_guardrails');
  context.goToFirstDirty();
  assert.equal(context.activeKey.value, 'egress_guardrails');
  assert.equal(context.guardrailSubTab.value, 'security');

  // 还原
  context.securityForm.value.blackIpsText = '';

  // 3. 当 scan_params (domain_brute_concurrent) 有脏字段时 -> scanning_arsenal / concurrency
  context.generalForm.value.domain_brute_concurrent = 500;
  assert.equal(context.firstDirtyTabKey.value, 'scanning_arsenal');
  context.goToFirstDirty();
  assert.equal(context.activeKey.value, 'scanning_arsenal');
  assert.equal(context.arsenalSubTab.value, 'concurrency');

  // 还原
  context.generalForm.value.domain_brute_concurrent = 300;

  // 4. 当 system_auth (auth/api_key) 有脏字段时 -> system_ops / auth_infra
  context.generalForm.value.auth = true;
  assert.equal(context.firstDirtyTabKey.value, 'system_ops');
  context.goToFirstDirty();
  assert.equal(context.activeKey.value, 'system_ops');
  assert.equal(context.opsSubTab.value, 'auth_infra');

  // 还原
  context.generalForm.value.auth = false;

  // 5. 当 proxy 面板有脏字段时 -> egress_guardrails / proxy
  const focusedAnchors = [];
  context.proxyPanelRef.value = {
    hasUnsavedChanges: () => true,
    focusSection: (anchor) => focusedAnchors.push(anchor),
  };
  assert.equal(context.firstDirtyTabKey.value, 'egress_guardrails');
  context.goToFirstDirty();
  assert.equal(context.activeKey.value, 'egress_guardrails');
  assert.equal(context.guardrailSubTab.value, 'proxy');
  await nextTick();
  assert.deepEqual(focusedAnchors, ['proxy']);
  context.proxyPanelRef.value = null;

  // 6. 当 api_config 有脏字段时 -> intel
  context.generalForm.value.fofa_key = 'test_key';
  assert.equal(context.firstDirtyTabKey.value, 'intel');
  context.goToFirstDirty();
  assert.equal(context.activeKey.value, 'intel');
});

test('SystemSettings: 统一分区计数、批量保存部分失败回写成功项与全部重置闭环', async () => {
  const { read, context, notices } = loadSystemSettings();

  read('isConfigInitialized');
  read('GENERAL_FIELD_GROUPS');
  read('cloneDeep');
  read('generalForm');
  read('generalBaseline');
  read('captureBaseline');
  context.captureBaseline();
  read('changedFields');
  read('pendingByGroup');
  read('securityForm');
  read('securityBaseline');
  read('isSecurityDirty');
  read('performanceForm');
  read('performanceBaseline');
  read('isPerformanceDirty');
  read('generalSaveLoading');
  read('securitySaveLoading');
  read('performanceSaveLoading');
  read('batchSaving');
  read('saveGeneralGroup');
  read('saveGeneralConfig');
  read('resetGeneralGroup');
  read('saveSecurityPolicy');
  read('resetSecurityForm');
  read('savePerformanceConfig');
  read('resetPerformanceForm');

  context.request = {
    post: async (url, payload) => ({ code: 200, data: payload }),
  };
  context.fetchSecurityPolicy = () => {};
  context.activeKey = ref('intel');
  context.guardrailSubTab = ref('proxy');
  context.arsenalSubTab = ref('concurrency');
  context.opsSubTab = ref('auth_infra');
  context.visitedDomains = reactive({
    intel: true,
    egress_guardrails: false,
    scanning_arsenal: true,
    notifications: true,
    system_ops: false,
  });
  context.visitedSubTabs = reactive({
    proxy: false,
    cdn: false,
    backup: false,
    update: false,
  });
  read('markVisitedState');
  read('applyDomainAndSubTab');

  read('isSectionRefDirty');
  read('SECTION_SPECS');
  read('dirtySections');
  read('hasUnsavedChanges');
  read('unsavedCount');
  read('navigateToSection');
  read('saveAllDirtySections');
  read('resetAllDirtySections');

  context.isConfigInitialized.value = true;

  // 在 api_config 修改 2 个字段，统一按分区计数仍为 1 个分区
  context.generalForm.value.fofa_key = 'new_key';
  context.generalForm.value.fofa_url = 'https://fofa.example';
  assert.equal(context.unsavedCount.value, 1);

  // 同时修改 proxy 与 security（proxy 模拟校验失败返回 false，security 提交成功）
  let proxyDirty = true;
  const focused = [];
  context.proxyPanelRef.value = {
    hasUnsavedChanges: () => proxyDirty,
    saveChanges: async () => false,
    resetChanges: () => { proxyDirty = false; },
    focusSection: (anchor) => focused.push(anchor),
  };
  context.securityForm.value.forbiddenDomainsText = 'gov.cn';

  assert.equal(context.unsavedCount.value, 3);

  // 批量保存：api_config 与 security 提交成功且基线回写；proxy 失败后停留 egress_guardrails/proxy 并定位到 proxy
  const okPartial = await context.saveAllDirtySections();
  assert.equal(okPartial, false);
  assert.equal(context.activeKey.value, 'egress_guardrails');
  assert.equal(context.guardrailSubTab.value, 'proxy');
  await nextTick();
  assert.deepEqual(focused, ['proxy']);
  assert.deepEqual(plain(context.pendingByGroup.value.api_config), {});
  assert.equal(context.isSecurityDirty.value, false);
  assert.equal(context.unsavedCount.value, 1);
  assert.equal(notices.at(-1).type, 'warning');

  // 再次使 api_config 脏，并验证 resetAllDirtySections 全部清零
  context.generalForm.value.github_token = 'ghp_test';
  assert.equal(context.unsavedCount.value, 2);
  context.resetAllDirtySections();
  assert.equal(context.unsavedCount.value, 0);
  assert.equal(context.hasUnsavedChanges.value, false);
  assert.equal(context.generalForm.value.github_token, '');
});

test('SystemSettings: 刷新失败时仅在未初始化阶段兜底对齐，已初始化时不破坏用户已编辑内容', async () => {
  const { read, context } = loadSystemSettings();

  read('cloneDeep');
  read('isConfigInitialized');
  read('performanceForm');
  read('performanceBaseline');
  read('runtimePerformance');
  read('performanceLoading');

  // 模拟请求失败的 request
  let shouldFail = true;
  context.request = {
    get: async () => {
      if (shouldFail) throw new Error('Network error');
      return {
        code: 200,
        data: {
          celery_heavy_concurrency: 2,
          celery_light_concurrency: 2,
          osint_concurrency: 2,
          github_concurrency: 2,
        },
      };
    },
  };

  read('fetchPerformanceConfig');

  // 场景 1：首屏挂载阶段（isConfigInitialized = false）接口异常，执行兜底对齐
  context.isConfigInitialized.value = false;
  await context.fetchPerformanceConfig();
  assert.deepEqual(plain(context.performanceBaseline.value), plain(context.performanceForm.value));

  // 场景 2：初始化完成后（isConfigInitialized = true），用户修改了并发数为 9
  context.isConfigInitialized.value = true;
  context.performanceBaseline.value = { celery_heavy_concurrency: 2, celery_light_concurrency: 2, osint_concurrency: 2, github_concurrency: 2 };
  context.performanceForm.value = { celery_heavy_concurrency: 9, celery_light_concurrency: 2, osint_concurrency: 2, github_concurrency: 2 };

  // 用户点击“刷新状态”，但网络断开失败
  shouldFail = true;
  await context.fetchPerformanceConfig();

  // baseline 绝不能被覆盖为用户未保存的 9，必须保留原有基线 2！
  assert.equal(context.performanceBaseline.value.celery_heavy_concurrency, 2);
  assert.equal(context.performanceForm.value.celery_heavy_concurrency, 9);
});
