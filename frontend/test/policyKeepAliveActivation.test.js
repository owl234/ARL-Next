import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { parse, compileScript } from 'vue/compiler-sfc';
import { ref, reactive, watch } from 'vue';

function loadPolicyComponent() {
  const filePath = new URL('../src/views/Policy.vue', import.meta.url);
  const content = fs.readFileSync(filePath, 'utf8');
  const { descriptor } = parse(content);
  const { scriptSetupAst } = compileScript(descriptor, { id: 'Policy.vue' });
  const bindings = {};

  const lifecycleHooks = {
    onMounted: [],
    onActivated: [],
    onDeactivated: [],
  };

  for (const node of scriptSetupAst) {
    if (node.type === 'VariableDeclaration') {
      for (const item of node.declarations) {
        if (item.id.type === 'Identifier' && item.init) {
          bindings[item.id.name] = descriptor.scriptSetup.content.slice(item.init.start, item.init.end);
        }
      }
    } else if (node.type === 'ExpressionStatement' && node.expression?.type === 'CallExpression') {
      const calleeName = node.expression.callee?.name;
      if (calleeName in lifecycleHooks) {
        lifecycleHooks[calleeName].push(descriptor.scriptSetup.content.slice(node.start, node.end));
      }
    }
  }

  const calls = [];
  let policyItems = [
    { _id: '6a6f02d5e244abf45193751c', name: '旧策略名称', desc: '旧描述', update_date: '2026-11-01 10:00:00', policy: {} }
  ];

  const context = vm.createContext({
    pageText: (key, params) => `${key}${params ? JSON.stringify(params) : ''}`,
    ref,
    reactive,
    watch,
    console,
    pageLocale: 'zh-CN',
    $pageSizeOptions: ['10', '20', '50'],
    useSticky: () => ({ stickyConfig: {} }),
    useGlobalPageSize: (size) => ref(size),
    useRouter: () => ({ push() {} }),
    message: {
      success() {},
      error() {},
      warning() {},
      info() {},
    },
    request: {
      async get(url, config) {
        calls.push({ url, config });
        return {
          code: 200,
          items: policyItems,
          total: policyItems.length,
        };
      },
      async post() {
        return { code: 200 };
      }
    },
    onMounted: (fn) => { context._mountedHandler = fn; },
    onActivated: (fn) => { context._activatedHandler = fn; },
    onDeactivated: (fn) => { context._deactivatedHandler = fn; },
  });

  const read = (name) => {
    assert.ok(bindings[name], `Missing binding ${name}`);
    return vm.runInContext(`globalThis.${name} = (${bindings[name]})`, context);
  };

  // 顺序执行 setup 脚本逻辑
  read('actionBarRef');
  read('loading');
  read('dataSource');
  read('searchForm');
  read('globalPageSize');
  read('pagination');
  read('selectedRowKeys');
  read('columns');
  read('fetchData');
  read('resetSearch');
  read('onSearch');
  read('handleTableChange');
  read('goToDetail');
  read('firstActivation');
  read('dispatchModalVisible');

  // 注册生命周期钩子
  for (const hookCode of lifecycleHooks.onMounted) {
    vm.runInContext(hookCode, context);
  }
  for (const hookCode of lifecycleHooks.onActivated) {
    vm.runInContext(hookCode, context);
  }
  for (const hookCode of lifecycleHooks.onDeactivated) {
    vm.runInContext(hookCode, context);
  }

  return {
    context,
    calls,
    setPolicyItems: (items) => { policyItems = items; },
    mount: async () => {
      if (context._mountedHandler) await context._mountedHandler();
    },
    activate: async () => {
      if (context._activatedHandler) await context._activatedHandler();
    },
    deactivate: async () => {
      if (context._deactivatedHandler) await context._deactivatedHandler();
    },
  };
}

test('Policy.vue: KeepAlive 激活钩子确保从 PolicyDetail 返回时策略名称自动刷新', async () => {
  const env = loadPolicyComponent();

  // 1. 首次挂载时触发 onMounted，拉取初始列表
  await env.mount();
  assert.equal(env.calls.length, 1, 'onMounted 应触发首次数据拉取');
  assert.equal(env.context.dataSource.value[0].name, '旧策略名称');

  // 2. Vue KeepAlive 在首次挂载后会立即触发一次 onActivated
  // 防重保护应保证不重复拉取数据
  await env.activate();
  assert.equal(env.calls.length, 1, '首次 onActivated 防重拦截，不产生重复请求');

  // 3. 用户在列表点击编辑跳转 PolicyDetail：Policy 页面触发 onDeactivated 进入缓存
  await env.deactivate();

  // 4. 模拟用户在 PolicyDetail 修改策略配置并保存成功，后端数据已更新
  env.setPolicyItems([
    { _id: '6a6f02d5e244abf45193751c', name: '已修改的新策略名称', desc: '新描述', update_date: '2026-11-11 12:00:00', policy: {} }
  ]);

  // 5. 保存策略后返回 /policy：KeepAlive 重新激活 Policy.vue 触发 onActivated
  await env.activate();
  assert.equal(env.calls.length, 2, '从 PolicyDetail 返回激活时应触发数据拉取');
  assert.equal(env.context.dataSource.value[0].name, '已修改的新策略名称', '策略名称应自动刷新为最新数据');
});

test('Policy.vue: KeepAlive 激活刷新时保留当前搜索条件与分页参数', async () => {
  const env = loadPolicyComponent();
  await env.mount();
  await env.activate();

  // 用户设置了名称搜索和分页
  env.context.searchForm.value.name = '专项';
  env.context.pagination.current = 2;

  // 切换去 PolicyDetail 编辑并返回
  await env.deactivate();
  await env.activate();

  const lastCall = env.calls[env.calls.length - 1];
  assert.equal(lastCall.config.params.name, '专项', '激活刷新时应携带已有搜索关键词');
  assert.equal(lastCall.config.params.page, 2, '激活刷新时应保持当前分页页码');
});
