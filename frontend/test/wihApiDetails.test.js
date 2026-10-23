import assert from 'node:assert/strict';
import fs from 'node:fs';
import test, { afterEach } from 'node:test';
import * as vue from 'vue';
import { renderToString } from 'vue/server-renderer';
import { parse, compileScript, babelParse } from 'vue/compiler-sfc';
import { useI18n } from 'vue-i18n';
import { i18n } from '../src/i18n/index.js';
import { getWihApiDetails, isApiEndpointRecord, PROBE_REASON_KEYS } from '../src/utils/wihApi.js';
import zh from '../src/i18n/wihApi.zh-CN.js';
import en from '../src/i18n/wihApi.en-US.js';
import ru from '../src/i18n/wihApi.ru-RU.js';

const text = (...args) => i18n.global.t(...args);
afterEach(() => { i18n.global.locale.value = 'zh-CN'; });

const sample = overrides => ({
  record_type: 'api_endpoint', content: 'GET https://app.example.test/api/users [path: /api/users]',
  site: 'https://app.example.test/', source: 'https://app.example.test/app.js [script:line 12]',
  api_request: {
    method: 'GET', path: '/api/users', url: 'https://app.example.test/api/users',
    client: 'fetch', line: 12, verified: true,
    probe: {
      state: 'responded', method: 'GET', status_code: 403,
      url: 'https://app.example.test/api/users', last_attempt_url: 'https://app.example.test/api/users',
      checked_at: '2026-10-22T00:00:00+00:00', elapsed_ms: 0, redirects: [],
      headers: { 'content-type': 'application/json' }, body_preview: '{"message":"denied"}',
      body_bytes: 20, body_truncated: false, ...overrides,
    },
  },
});

const file = fs.readFileSync(new URL('../src/components/WihApiDetailsDrawer.vue', import.meta.url), 'utf8');
const { descriptor } = parse(file);
const script = compileScript(descriptor, { id: 'wih-api-details-test', inlineTemplate: true });
const bindings = {};
const modules = {
  vue, 'vue-i18n': { useI18n }, 'ant-design-vue': { message: { success() {}, warning() {} } },
  '../utils/clipboard': { copyText: async () => true },
  '../utils/wihApi': { getWihApiDetails, PROBE_REASON_KEYS },
};
const edits = [];
for (const node of babelParse(script.content, { sourceType: 'module' }).program.body) {
  if (node.type === 'ImportDeclaration') {
    assert.ok(modules[node.source.value], node.source.value);
    for (const specifier of node.specifiers) bindings[specifier.local.name] = modules[node.source.value][specifier.imported.name];
    edits.push([node.start, node.end, '']);
  } else if (node.type === 'ExportDefaultDeclaration') edits.push([node.start, node.declaration.start, 'return ']);
}
let code = script.content;
for (const [start, end, value] of edits.sort((a, b) => b[0] - a[0])) code = code.slice(0, start) + value + code.slice(end);
const Drawer = new Function(...Object.keys(bindings), code)(...Object.values(bindings));

async function render(record, locale = 'zh-CN') {
  i18n.global.locale.value = locale;
  const app = vue.createSSRApp({ render: () => vue.h(Drawer, { open: true, record }) });
  app.use(i18n);
  // 保留实际 SFC 的表达式与 Vue 文本转义，替换依赖浏览器的 Ant 容器。
  for (const name of ['a-drawer', 'a-alert', 'a-descriptions', 'a-descriptions-item', 'a-tag', 'a-button']) {
    app.component(name, vue.defineComponent({ inheritAttrs: false, setup(_, { attrs, slots }) {
      return () => vue.h('section', { 'data-component': name }, [
        ...['title', 'label', 'message'].filter(key => attrs[key] !== undefined).map(key => vue.h('span', String(attrs[key]))),
        slots.default?.(),
      ]);
    } }));
  }
  return renderToString(app);
}

test('新旧接口记录均可查看，其他 WIH 类型不显示详情入口', () => {
  assert.equal(isApiEndpointRecord(sample()), true);
  assert.equal(isApiEndpointRecord({ recordType: 'api_endpoint', content: '/legacy' }), true);
  for (const record of [null, [], {}, { record_type: 'domain', api_request: {} }]) assert.equal(isApiEndpointRecord(record), false);
  const details = getWihApiDetails({ record_type: 'api_endpoint', content: '/legacy', source: 'old.js' });
  assert.equal(details.legacy, true);
  assert.equal(details.state, 'not_collected');
  assert.equal(details.method, '');
  assert.equal(details.content, '/legacy');
  assert.equal(details.source, 'old.js');
});

test('被拒绝、未找到和服务器错误均保留 HTTP 观测，不按 verified 标志推断漏洞', () => {
  for (const status_code of [200, 401, 403, 404, 500]) {
    const record = sample({ status_code });
    record.api_request.verified = false;
    const details = getWihApiDetails(record);
    assert.equal(details.state, 'responded');
    assert.equal(details.statusCode, status_code);
    assert.equal(details.elapsedMs, 0);
  }
  const passive = sample();
  delete passive.api_request.probe;
  assert.equal(getWihApiDetails(passive).state, 'not_collected');
});

test('请求失败与跳过状态保持独立，失败目标不能冒充响应地址', () => {
  for (const [state, code] of [['error', 'timeout'], ['skipped', 'outside_origin']]) {
    const record = sample();
    record.api_request.probe = { state, error: state === 'error' ? code : '', reason: state === 'skipped' ? code : '', url: record.api_request.url };
    const details = getWihApiDetails(record);
    assert.equal(details.state, state);
    assert.equal(details.responseUrl, '');
    assert.equal(details.statusCode, null);
    assert.equal(details.checkedAt, '');
  }
});

test('后续跳转失败同时保留上一跳响应与最近尝试地址', () => {
  const details = getWihApiDetails(sample({
    status_code: 302, last_attempt_url: 'https://app.example.test/final', error: 'timeout',
    redirects: [{ status_code: 302, url: 'https://app.example.test/api/users' }],
  }));
  assert.equal(details.state, 'responded');
  assert.equal(details.responseUrl, 'https://app.example.test/api/users');
  assert.equal(details.lastAttemptUrl, 'https://app.example.test/final');
  assert.equal(details.error, 'timeout');
  assert.equal(details.redirects[0].statusCode, 302);
});

test('区分正文为空、未采集、按类型跳过及截断或读取失败', () => {
  assert.equal(getWihApiDetails(sample({ body_preview: '', body_bytes: 0 })).bodyCollected, true);
  for (const body_skipped of ['head', 'non_text']) {
    const details = getWihApiDetails(sample({ body_skipped, body_preview: '', body_bytes: 0 }));
    assert.equal(details.bodyCollected, false);
    assert.equal(details.bodySkipped, body_skipped);
  }
  const record = sample({ body_truncated: true, body_error: 'timeout' });
  assert.equal(getWihApiDetails(record).bodyTruncated, true);
  assert.equal(getWihApiDetails(record).bodyError, 'timeout');
  delete record.api_request.probe.body_preview;
  assert.equal(getWihApiDetails(record).bodyCollected, false);
});

test('缺失和异常元数据不抛错，不使用占位对象或非法状态码伪造证据', () => {
  for (const record of [undefined, null, [], { api_request: [] }, { api_request: { probe: [] } }]) assert.doesNotThrow(() => getWihApiDetails(record));
  const details = getWihApiDetails({ api_request: { method: {}, line: -1, probe: {
    state: '__proto__', status_code: 999, elapsed_ms: NaN, body_preview: {}, body_truncated: 'false',
    headers: { good: 'value', zero: 0, invalid: {} }, redirects: [null, 'invalid', { status_code: 0, url: {} }],
  } } });
  assert.equal(details.state, 'unknown');
  assert.equal(details.statusCode, null);
  assert.equal(details.elapsedMs, null);
  assert.equal(details.line, null);
  assert.equal(details.method, '');
  assert.equal(details.headers, 'good: value\nzero: 0');
  assert.deepEqual(details.redirects, [{ statusCode: null, url: '' }]);
  assert.equal(details.bodyCollected, false);
  assert.equal(details.bodyTruncated, false);
});

test('真实详情模板将 HTML、脚本、响应头和来源转义为文本', async () => {
  const payload = '<script>alert("fixture")</script><img src="https://outside.example.test/pixel" onerror="fixture()">';
  const record = sample({ body_preview: payload, headers: { 'x-fixture': payload } });
  record.source = payload;
  const html = await render(record, 'en-US');
  assert.match(html, /&lt;script&gt;/);
  assert.match(html, /&lt;img src=/);
  assert.doesNotMatch(html, /<script\b|<img\b|<iframe\b|href="https:\/\/outside/);
  assert.match(html, /HTTP response received/);
  assert.match(html, /403/);
  assert.match(html, /does not establish endpoint validity/);
});

test('真实模板兼容旧记录，未知原因保留原值，各语言可立即更新', async () => {
  const legacy = { record_type: 'api_endpoint', content: 'GET /legacy', source: 'old.js' };
  assert.match(await render(legacy, 'en-US'), /no structured API metadata/);
  assert.match(await render(legacy, 'ru-RU'), /нет структурированных сведений/);
  const record = sample({ state: 'skipped', reason: 'future_reason' });
  assert.match(await render(record, 'en-US'), /Unrecognized reason: future_reason/);
  assert.match(await render(record, 'zh-CN'), /未识别的原因：future_reason/);
});

test('截断和跳转停止均有可见提示，HEAD 正文不会显示为空响应', async () => {
  const html = await render(sample({ body_truncated: true, body_error: 'timeout', redirect_stop: 'outside_origin' }), 'en-US');
  assert.match(html, /body preview is incomplete/);
  assert.match(html, /Body reading did not complete/);
  assert.match(html, /Redirect stop reason/);
  const head = await render(sample({ body_skipped: 'head', body_preview: '' }), 'en-US');
  assert.match(head, /HEAD responses have no captured body/);
  assert.doesNotMatch(head, /Response body is empty/);
});

test('所有状态和原因均有三语文案，插值一致且所有消息可渲染', () => {
  assert.deepEqual(Object.keys(zh), Object.keys(en));
  assert.deepEqual(Object.keys(zh), Object.keys(ru));
  for (const [locale, messages] of [['zh-CN', zh], ['en-US', en], ['ru-RU', ru]]) {
    i18n.global.locale.value = locale;
    for (const [key, value] of Object.entries(messages)) {
      const params = Object.fromEntries([...value.matchAll(/\{(\w+)\}/g)].map(([, name]) => [name, `fixture_${name}`]));
      assert.deepEqual(value.match(/\{\w+\}/g)?.sort(), zh[key].match(/\{\w+\}/g)?.sort(), key);
      const rendered = text(`wihApi.${key}`, params);
      assert.notEqual(rendered, `wihApi.${key}`);
      for (const value of Object.values(params)) assert.ok(rendered.includes(value));
      if (locale !== 'zh-CN') assert.doesNotMatch(rendered, /\p{Script=Han}/u);
    }
    for (const key of Object.values(PROBE_REASON_KEYS)) assert.equal(typeof messages[key], 'string');
  }
});

test('三个 WIH 页面均复用抽屉，详情不引入网络或 HTML 渲染入口', () => {
  for (const view of ['TaskDetail', 'AssetSearch', 'GroupAssetsDetail']) {
    const source = fs.readFileSync(new URL(`../src/views/${view}.vue`, import.meta.url), 'utf8');
    const { descriptor } = parse(source);
    compileScript(descriptor, { id: view });
    assert.match(descriptor.template.content, /v-if="isApiEndpointRecord\(record\)"/);
    assert.match(descriptor.template.content, /@click="showWihApiDetails\(record\)"/);
    assert.match(descriptor.template.content, /<WihApiDetailsDrawer v-model:open="wihApiDetailsOpen"/);
    assert.match(descriptor.template.content, /:context-key="route.fullPath \+ ':' \+ activeTab"/);
  }
  assert.doesNotMatch(file, /v-html|<iframe\b|<img\b|\bfetch\(|request\.(?:get|post)|axios/);
});
