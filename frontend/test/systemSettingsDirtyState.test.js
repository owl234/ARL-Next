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

test('SystemSettings: firstDirtyTabKey 与 goToFirstDirty 正确支持外层 Tab 与内层子 Tab 导航', () => {
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

  context.activeKey = ref('api_config');
  context.scanSubTab = ref('performance');

  read('firstDirtyTabKey');
  read('goToFirstDirty');

  // 1. 当 performanceDirty 时
  context.performanceForm.value.celery_heavy_concurrency = 3;
  assert.equal(context.firstDirtyTabKey.value, 'performance');
  context.goToFirstDirty();
  assert.equal(context.activeKey.value, 'performance');
  assert.equal(context.scanSubTab.value, 'performance');

  // 还原
  context.performanceForm.value.celery_heavy_concurrency = 1;

  // 2. 当 securityDirty 时
  context.securityForm.value.blackIpsText = '10.0.0.1';
  assert.equal(context.firstDirtyTabKey.value, 'performance');
  context.goToFirstDirty();
  assert.equal(context.activeKey.value, 'performance');
  assert.equal(context.scanSubTab.value, 'security');

  // 还原
  context.securityForm.value.blackIpsText = '';

  // 3. 当 system_general 有脏字段时
  context.generalForm.value.proxy_url = 'http://127.0.0.1:8080';
  assert.equal(context.firstDirtyTabKey.value, 'performance');
  context.goToFirstDirty();
  assert.equal(context.activeKey.value, 'performance');
  assert.equal(context.scanSubTab.value, 'system_general');

  // 还原
  context.generalForm.value.proxy_url = '';

  // 4. 当 api_config 有脏字段时
  context.generalForm.value.fofa_key = 'test_key';
  assert.equal(context.firstDirtyTabKey.value, 'api_config');
  context.goToFirstDirty();
  assert.equal(context.activeKey.value, 'api_config');
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
