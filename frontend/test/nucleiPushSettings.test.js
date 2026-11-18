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

  const context = vm.createContext({
    pageText: (key) => key,
    computed,
    reactive,
    ref,
    nextTick,
    console,
    pageLocale: 'zh-CN',
    message: { success() {}, error() {}, warning() {}, info() {} },
    route: { query: {} },
    router: { push() {} },
    proxyPanelRef: ref(null),
    cdnPanelRef: ref(null),
  });

  const read = (name) => {
    assert.ok(bindings[name], `Missing binding ${name}`);
    return vm.runInContext(`globalThis.${name} = (${bindings[name]})`, context);
  };

  return { content, context, read };
}

test('SystemSettings: Nuclei 漏洞推送订阅与严重等级过滤脏状态与重置闭环', () => {
  const { content, context, read } = loadSystemSettings();
  assert.match(content, /value="nuclei_vuln"/);
  assert.match(content, /generalForm\.nuclei_push_severities/);

  read('GENERAL_FIELD_GROUPS');
  read('cloneDeep');
  read('generalForm');
  read('generalBaseline');
  read('captureBaseline');
  context.captureBaseline();
  read('changedFields');
  read('pendingByGroup');
  read('resetGeneralGroup');
  read('nucleiPushSeverityOptions');

  assert.ok(context.GENERAL_FIELD_GROUPS.message_push.includes('nuclei_push_severities'));
  assert.ok(context.generalForm.value.push_options.includes('nuclei_vuln'));
  assert.deepEqual(plain(context.generalForm.value.nuclei_push_severities), ['critical', 'high', 'medium', 'low']);
  assert.deepEqual(
    plain(context.nucleiPushSeverityOptions.map((o) => o.value)),
    ['critical', 'high', 'medium', 'low', 'info'],
  );

  context.generalForm.value.nuclei_push_severities = ['critical', 'high'];
  assert.deepEqual(plain(context.pendingByGroup.value.message_push), {
    nuclei_push_severities: ['critical', 'high'],
  });

  context.resetGeneralGroup('message_push', { silent: true });
  assert.deepEqual(plain(context.generalForm.value.nuclei_push_severities), ['critical', 'high', 'medium', 'low']);
  assert.deepEqual(plain(context.pendingByGroup.value.message_push), {});
});

test('i18n: 中英俄三语语言包均包含 Nuclei 推送配置词条', async () => {
  const [zh, en, ru] = await Promise.all([
    import('../src/i18n/pages.zh-CN.js'),
    import('../src/i18n/pages.en-US.js'),
    import('../src/i18n/pages.ru-RU.js'),
  ]);
  for (const localeObj of [zh.default, en.default, ru.default]) {
    assert.ok(localeObj.nucleiVulnerabilityAlert);
    assert.ok(localeObj.nucleiPushSeverityFilter);
  }
});
