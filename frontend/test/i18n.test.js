import assert from 'node:assert/strict';
import fs from 'node:fs';
import test, { afterEach } from 'node:test';
import vm from 'node:vm';
import { computed, reactive, ref } from 'vue';
import { parse, compileScript } from 'vue/compiler-sfc';
import { DEFAULT_LOCALE, LOCALE_STORAGE_KEY, i18n, initializeLocale, setLocale } from '../src/i18n/index.js';
import zhCN from '../src/i18n/zh-CN.js';
import enUS from '../src/i18n/en-US.js';

const originalStorage = Object.getOwnPropertyDescriptor(globalThis, 'localStorage');
const originalDocument = Object.getOwnPropertyDescriptor(globalThis, 'document');
const plain = value => JSON.parse(JSON.stringify(value));
const t = (...args) => i18n.global.t(...args);

function storage(values = {}) {
  const data = new Map(Object.entries(values));
  return {
    data,
    getItem: key => data.get(key) ?? null,
    setItem: (key, value) => data.set(key, String(value)),
    removeItem: key => data.delete(key),
  };
}

function browserPreferences(values) {
  const store = storage(values);
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: store });
  Object.defineProperty(globalThis, 'document', { configurable: true, value: { documentElement: { lang: '' } } });
  return store;
}

afterEach(() => {
  i18n.global.locale.value = DEFAULT_LOCALE;
  for (const [key, descriptor] of [['localStorage', originalStorage], ['document', originalDocument]]) {
    if (descriptor) Object.defineProperty(globalThis, key, descriptor);
    else delete globalThis[key];
  }
});

function bindings(file) {
  const { descriptor } = parse(fs.readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8'));
  const { scriptSetupAst } = compileScript(descriptor, { id: file });
  const result = {};
  for (const node of scriptSetupAst) {
    if (node.type !== 'VariableDeclaration') continue;
    for (const item of node.declarations) {
      if (item.id.type === 'Identifier' && item.init) {
        result[item.id.name] = descriptor.scriptSetup.content.slice(item.init.start, item.init.end);
      }
    }
  }
  return result;
}

test('默认中文，已保存的英文偏好可在重新初始化后恢复', () => {
  const store = browserPreferences();
  initializeLocale();
  assert.equal(t('login.signIn'), '登录');
  assert.equal(document.documentElement.lang, 'zh-CN');
  setLocale('en-US');
  assert.equal(store.getItem(LOCALE_STORAGE_KEY), 'en-US');
  assert.equal(document.documentElement.lang, 'en-US');
  i18n.global.locale.value = 'zh-CN';
  initializeLocale();
  assert.equal(t('login.signIn'), 'Sign in');
});

test('语言切换不修改 Token、用户资料和菜单排序', () => {
  const saved = { token: 'fixture-token', userInfo: '{"username":"fixture"}',
    arl_sidebar_menu_order_fixture: '["/policy","/dashboard"]' };
  const store = browserPreferences(saved);
  setLocale('en-US');
  setLocale('zh-CN');
  for (const [key, value] of Object.entries(saved)) assert.equal(store.getItem(key), value);
  assert.equal(store.data.size, 4);
});

test('无效语言偏好回退中文，非法切换不改变当前语言', () => {
  browserPreferences({ [LOCALE_STORAGE_KEY]: '__proto__' });
  initializeLocale();
  assert.equal(i18n.global.locale.value, 'zh-CN');
  setLocale('en-US');
  for (const locale of ['fr', '', null, {}, 'constructor']) assert.equal(setLocale(locale), false);
  assert.equal(i18n.global.locale.value, 'en-US');
});

test('浏览器拒绝访问存储时仍可初始化并切换语言', () => {
  browserPreferences();
  Object.defineProperty(globalThis, 'localStorage', {
    configurable: true,
    get() { throw new Error('storage unavailable'); },
  });
  assert.doesNotThrow(initializeLocale);
  assert.equal(i18n.global.locale.value, 'zh-CN');
  assert.equal(setLocale('en-US'), true);
  assert.equal(document.documentElement.lang, 'en-US');
});

test('浏览器拒绝写入存储时当前页面的语言切换仍然生效', () => {
  const store = browserPreferences({ [LOCALE_STORAGE_KEY]: 'en-US' });
  store.setItem = () => { throw new Error('read-only storage'); };
  initializeLocale();
  assert.equal(t('login.signIn'), 'Sign in');
  setLocale('zh-CN');
  assert.equal(t('login.signIn'), '登录');
});

test('中英文语言包的键和插值参数一致', () => {
  const flatten = (object, prefix = '') => Object.entries(object).flatMap(([key, value]) => {
    const path = prefix ? `${prefix}.${key}` : key;
    return typeof value === 'string' ? [[path, value]] : flatten(value, path);
  });
  const chinese = Object.fromEntries(flatten(zhCN));
  const english = Object.fromEntries(flatten(enUS));
  assert.deepEqual(Object.keys(chinese).sort(), Object.keys(english).sort());
  for (const key of Object.keys(chinese)) {
    assert.ok(english[key].trim(), key);
    assert.deepEqual(chinese[key].match(/\{\w+\}/g)?.sort(), english[key].match(/\{\w+\}/g)?.sort(), key);
  }
});

test('已迁移组件引用的翻译键均存在于中英文语言包', () => {
  for (const file of ['views/Login.vue', 'views/Layout.vue', 'components/LanguageSwitcher.vue', 'utils/request.js']) {
    const source = fs.readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8');
    const keys = [...source.matchAll(/\bt\('([^']+)'/g)].map(match => match[1]);
    keys.push(...[...source.matchAll(/'(navigation\.[a-zA-Z]+)'/g)].map(match => match[1]));
    for (const key of keys) {
      for (const messages of [zhCN, enUS]) {
        assert.equal(typeof key.split('.').reduce((value, part) => value?.[part], messages), 'string', `${file}: ${key}`);
      }
    }
  }
});

test('英文翻译缺失时使用中文回退，后端原始提示作为参数保留', () => {
  const messages = plain(enUS);
  delete messages.login.signIn;
  i18n.global.setLocaleMessage('en-US', messages);
  try {
    setLocale('en-US');
    assert.equal(t('login.signIn'), '登录');
    assert.equal(t('login.failed', { reason: '服务原始提示 {value}' }), 'Sign-in failed: 服务原始提示 {value}');
  } finally {
    i18n.global.setLocaleMessage('en-US', enUS);
  }
});

function navigation() {
  const source = bindings('views/Layout.vue');
  const store = browserPreferences({ arl_sidebar_menu_order_fixture: '["/policy","/dashboard"]' });
  const route = reactive({ path: '/taskList' });
  const context = { localStorage: store, currentUsername: ref('fixture'), route, computed, t, console };
  for (const [, name] of source.defaultMenuItems.matchAll(/icon:\s*(\w+)/g)) context[name] = name;
  const sandbox = vm.createContext(context);
  for (const name of ['defaultMenuItems', 'getMenuStorageKey', 'loadOrderedMenuItems', 'currentPageTitle']) {
    vm.runInContext(`globalThis.${name} = ${source[name]}`, sandbox);
  }
  return { ...sandbox, route, store };
}

test('菜单按保存的路由顺序排列，切换语言后只更新标签', () => {
  const nav = navigation();
  const items = nav.loadOrderedMenuItems();
  const labels = computed(() => items.map(item => t(item.titleKey)));
  assert.deepEqual(plain(items.slice(0, 2).map(item => item.key)), ['/policy', '/dashboard']);
  assert.deepEqual(plain(labels.value.slice(0, 2)), ['策略配置', '仪表盘']);
  setLocale('en-US');
  assert.deepEqual(plain(labels.value.slice(0, 2)), ['Policies', 'Dashboard']);
  assert.equal(items.length, 11);
  assert.equal(nav.store.getItem('arl_sidebar_menu_order_fixture'), '["/policy","/dashboard"]');
});

test('导航标题响应语言与路由变化，详情页标题也正确切换', () => {
  const nav = navigation();
  assert.equal(nav.currentPageTitle.value, '任务管理');
  setLocale('en-US');
  assert.equal(nav.currentPageTitle.value, 'Tasks');
  for (const [path, title] of [
    ['/taskList/taskDetail', 'Task details'],
    ['/groupAssetsManagement/groupAssetsDetail', 'Asset group details'],
    ['/policyDetail', 'Policy details'], ['/systemSettings', 'System settings'],
  ]) {
    nav.route.path = path;
    assert.equal(nav.currentPageTitle.value, title);
  }
  setLocale('zh-CN');
  assert.equal(nav.currentPageTitle.value, '系统设置');
});

function login(response, throws = false) {
  const calls = [], messages = [], routes = [];
  const store = browserPreferences();
  const context = vm.createContext({
    t, loading: ref(false), localStorage: store, console,
    request: { post: async (url, payload) => { calls.push({ url, payload: plain(payload) });
      if (throws) throw new Error('fixture unavailable');
      return response;
    } },
    message: { success: value => messages.push(value), error: value => messages.push(value) },
    router: { push: value => routes.push(value) },
  });
  const onFinish = vm.runInContext(bindings('views/Login.vue').onFinish, context);
  return { onFinish, calls, messages, routes, store, loading: context.loading };
}

test('英文登录成功时保留原请求参数、Token 保存与路由跳转', async () => {
  const page = login({ code: 200, data: { token: 'fixture-token' } });
  setLocale('en-US');
  await page.onFinish({ username: 'fixture', password: 'fixture-password' });
  assert.deepEqual(page.calls, [{ url: '/api/user/login', payload: { username: 'fixture', password: 'fixture-password' } }]);
  assert.equal(page.store.getItem('token'), 'fixture-token');
  assert.deepEqual(page.routes, ['/']);
  assert.deepEqual(page.messages, ['Signed in successfully']);
  assert.equal(page.loading.value, false);
});

test('账号密码错误使用当前语言，后端其他错误不丢失原因', async () => {
  const page = login({ code: 401 });
  await page.onFinish({ username: 'fixture', password: 'wrong' });
  assert.equal(page.messages[0], '登录失败：账号或密码错误');
  setLocale('en-US');
  await page.onFinish({ username: 'fixture', password: 'wrong' });
  assert.equal(page.messages[1], 'Sign-in failed: incorrect username or password');
  const other = login({ code: 500, message: 'fixture reason' });
  await other.onFinish({ username: 'fixture', password: 'wrong' });
  assert.equal(other.messages[0], 'Sign-in failed: fixture reason');
});

test('登录请求异常使用英文提示并恢复按钮状态', async () => {
  const page = login(null, true);
  setLocale('en-US');
  await page.onFinish({ username: 'fixture', password: 'fixture-password' });
  assert.deepEqual(page.messages, ['Request failed. Check the console or service status.']);
  assert.equal(page.loading.value, false);
  assert.deepEqual(page.routes, []);
});

function requestClient() {
  const source = fs.readFileSync(new URL('../src/utils/request.js', import.meta.url), 'utf8');
  const hooks = {}, messages = [], redirects = [];
  const store = browserPreferences({ token: 'fixture-token', userInfo: '{}' });
  const client = { interceptors: {
    request: { use: (ok, fail) => { hooks.request = { ok, fail }; } },
    response: { use: (ok, fail) => { hooks.response = { ok, fail }; } },
  } };
  vm.runInNewContext(source.replace(/^import .*;$/gm, '').replace('export default request;', ''), {
    axios: { create: () => client }, i18n, localStorage: store, Promise,
    message: { warning: value => messages.push(value), error: value => messages.push(value) },
    setTimeout: callback => redirects.push(callback), window: { location: { href: '' } },
  });
  return { hooks, messages, redirects, store };
}

test('公共请求仍保留 API 前缀和 Token，请求内容不受语言影响', () => {
  const api = requestClient();
  setLocale('en-US');
  const config = api.hooks.request.ok({ url: '/task/', headers: {}, data: { name: '原始任务名' } });
  assert.equal(config.url, '/api/task/');
  assert.equal(config.headers.Token, 'fixture-token');
  assert.equal(config.data.name, '原始任务名');
});

test('登录 401 交给页面处理，其他 401 只提示和清理登录态一次并保留语言', () => {
  const api = requestClient();
  setLocale('en-US');
  const loginResponse = { data: { code: 401 }, config: { url: '/api/user/login' } };
  assert.equal(api.hooks.response.ok(loginResponse), loginResponse.data);
  assert.equal(api.store.getItem('token'), 'fixture-token');
  api.hooks.response.ok({ data: { code: 401 }, config: { url: '/api/task/' } });
  api.hooks.response.ok({ data: { code: 401 }, config: { url: '/api/task/' } });
  assert.deepEqual(api.messages, ['Your session has expired or is invalid. Please sign in again.']);
  assert.equal(api.redirects.length, 1);
  assert.equal(api.store.getItem('token'), null);
  assert.equal(api.store.getItem(LOCALE_STORAGE_KEY), 'en-US');
});

test('公共网络提示随语言切换，下载错误仍由业务页面处理', async () => {
  const api = requestClient();
  const error = { config: {}, response: { status: 500 } };
  setLocale('en-US');
  await assert.rejects(api.hooks.response.fail(error), value => value === error);
  assert.equal(api.messages[0], 'Request failed. Please check the backend service.');
  setLocale('zh-CN');
  await assert.rejects(api.hooks.response.fail(error), value => value === error);
  assert.equal(api.messages[1], '网络请求异常，请检查后端服务！');
  const blobError = { config: { responseType: 'blob' }, response: { status: 500 } };
  await assert.rejects(api.hooks.response.fail(blobError), value => value === blobError);
  assert.equal(api.messages.length, 2);
});
