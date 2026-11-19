import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { ref, reactive, computed, nextTick } from 'vue';
import { parse, compileScript } from 'vue/compiler-sfc';
import {
  parseProxyUri,
  parseBlackIpInterval,
  validateForbiddenDomainLine,
  analyzeSecurityPolicy,
  applySecurityPreset,
  SECURITY_IP_PRESETS,
  SECURITY_DOMAIN_PRESETS,
  testTargetAgainstGuardrails,
  maskConnectionUri,
  generateStrongApiKey,
} from '../src/utils/settingsHelpers.js';

const plain = (v) => JSON.parse(JSON.stringify(v));

function loadSfcBindings(relPath, extra = {}) {
  const raw = fs.readFileSync(new URL(`../src/${relPath}`, import.meta.url), 'utf8');
  const { descriptor } = parse(raw);
  const { scriptSetupAst } = compileScript(descriptor, { id: relPath });
  const bindings = {};
  for (const node of scriptSetupAst) {
    if (node.type !== 'VariableDeclaration') continue;
    for (const item of node.declarations) {
      if (item.id.type === 'Identifier' && item.init) {
        bindings[item.id.name] = descriptor.scriptSetup.content.slice(item.init.start, item.init.end);
      }
    }
  }
  const notices = [];
  const context = vm.createContext({
    pageText: (k, params) => `${k}${params ? JSON.stringify(params) : ''}`,
    computed,
    reactive,
    ref,
    nextTick,
    console,
    pageLocale: ref('zh-CN'),
    message: Object.fromEntries(['success', 'warning', 'error', 'info'].map((t) => [t, (m) => notices.push({ type: t, msg: m })])),
    ...extra,
  });
  const read = (name) => {
    assert.ok(bindings[name], `${relPath}: missing binding ${name}`);
    return vm.runInContext(`globalThis.${name} = (${bindings[name]})`, context);
  };
  return { raw, context, notices, read };
}

test('parseProxyUri 正确解析多种协议、URL 编码账密、默认端口与 IPv6 主机', () => {
  assert.deepEqual(parseProxyUri('socks5h://alice:p%40ss%3A1@192.0.2.10:1088'), {
    ok: true,
    protocol: 'socks5h',
    host: '192.0.2.10',
    port: 1088,
    username: 'alice',
    password: 'p@ss:1',
  });
  assert.deepEqual(parseProxyUri('socks5://127.0.0.1'), {
    ok: true,
    protocol: 'socks5',
    host: '127.0.0.1',
    port: 1080,
    username: '',
    password: '',
  });
  assert.deepEqual(parseProxyUri('https://[2001:db8::1]:8443'), {
    ok: true,
    protocol: 'https',
    host: '2001:db8::1',
    port: 8443,
    username: '',
    password: '',
  });
  assert.equal(parseProxyUri('127.0.0.1:7890').protocol, 'http');
  assert.equal(parseProxyUri('ftp://192.0.2.1:21').ok, false);
  assert.equal(parseProxyUri('').ok, false);
});

test('安全红线规则解析、统计、预设增删与 Dry-Run 命中对齐后端边界语义', () => {
  assert.equal(parseBlackIpInterval('192.168.1.1-254').valid, true);
  assert.equal(parseBlackIpInterval('10.0.0.0/8').valid, true);
  assert.equal(parseBlackIpInterval('999.1.1.1').valid, false);
  assert.equal(parseBlackIpInterval('192.168.1.20-10').valid, false);

  assert.equal(validateForbiddenDomainLine('gov.cn').valid, true);
  assert.equal(validateForbiddenDomainLine('https://gov.cn').valid, false);

  const analysis = analyzeSecurityPolicy('127.0.0.0/8\nbad-ip\n10.0.0.1-10', 'gov.cn\nedu.cn\ninvalid');
  assert.equal(analysis.ipCount, 2);
  assert.equal(analysis.invalidIps.length, 1);
  assert.equal(analysis.invalidIps[0].line, 2);
  assert.equal(analysis.domainCount, 2);
  assert.equal(analysis.invalidDomains.length, 1);

  // 预设添加与移除（保持去重且不误删自定义项）
  const added = applySecurityPreset('198.51.100.5\n127.0.0.0/8', SECURITY_IP_PRESETS.rfc1918, 'add');
  assert.equal(added.split('\n').length, 6);
  const removed = applySecurityPreset(added, SECURITY_IP_PRESETS.rfc1918, 'remove');
  assert.equal(removed, '198.51.100.5');

  const domainsAdded = applySecurityPreset('example.org', SECURITY_DOMAIN_PRESETS.govEdu, 'add');
  assert.ok(domainsAdded.includes('gov.cn'));

  // Dry-Run 精确匹配与严格点边界
  const r1 = testTargetAgainstGuardrails('10.10.2.8', added, domainsAdded);
  assert.equal(r1.status, 'blocked_ip');
  assert.equal(r1.matchedRule, '10.0.0.0/8');

  const r2 = testTargetAgainstGuardrails('https://portal.gov.cn:8443/login', added, domainsAdded);
  assert.equal(r2.status, 'blocked_domain');
  assert.equal(r2.matchedRule, 'gov.cn');

  // mygov.cn 不应被 gov.cn 误杀
  const r3 = testTargetAgainstGuardrails('mygov.cn', added, domainsAdded);
  assert.equal(r3.status, 'allowed');
});

test('基础设施连接串脱敏与随机 Key 生成', () => {
  assert.equal(
    maskConnectionUri('mongodb://admin:SecretPass123@127.0.0.1:27018/?authSource=admin'),
    'mongodb://admin:******@127.0.0.1:27018/?authSource=admin',
  );
  assert.equal(maskConnectionUri('amqp://127.0.0.1:5672/'), 'amqp://127.0.0.1:5672/');

  const key = generateStrongApiKey(32);
  assert.equal(key.length, 32);
  assert.match(key, /^[A-Za-z0-9]+$/);
});

test('SystemSettings: 情报凭据检测在存在未保存改动时自动先保存再校验，保存失败则阻断检测', async () => {
  const { read, context, notices } = loadSfcBindings('views/SystemSettings.vue');
  read('GENERAL_FIELD_GROUPS');
  read('cloneDeep');
  read('generalForm');
  read('generalBaseline');
  read('captureBaseline');
  context.captureBaseline();
  read('changedFields');
  read('pendingByGroup');
  read('generalSaveLoading');
  read('saveGeneralGroup');
  read('saveGeneralConfig');
  read('intelChecks');
  read('ensureIntelSavedBeforeCheck');
  read('verifyFofaConnection');

  const calls = [];
  let failSave = false;
  context.request = {
    async post(url, data) {
      calls.push({ url, data: plain(data) });
      if (url === '/api/system_config/general' && failSave) {
        return { code: 400, message: 'save failed' };
      }
      if (url === '/task_fofa/test') {
        return { code: 200, data: { size: 42 } };
      }
      return { code: 200 };
    },
  };

  // 修改 fofa_key 后直接点测试：应先 POST /api/system_config/general，再 POST /task_fofa/test
  context.generalForm.value.fofa_key = 'new_fofa_key';
  await context.verifyFofaConnection();
  assert.deepEqual(calls.map((c) => c.url), ['/api/system_config/general', '/task_fofa/test']);
  assert.equal(context.intelChecks.fofa.status, 'ok');
  assert.deepEqual(plain(context.pendingByGroup.value.api_config), {});
  assert.match(notices.at(-1).msg, /autoSavedAndChecked/);

  // 若自动保存失败，不应继续发测试请求
  calls.length = 0;
  failSave = true;
  context.generalForm.value.fofa_key = 'bad_save_key';
  await context.verifyFofaConnection();
  assert.deepEqual(calls.map((c) => c.url), ['/api/system_config/general']);
});

test('SystemSettings: 历史深链参数 (?tab=&focus=) 全部精确映射至新 5 主域与二级 Tab', () => {
  const { read, context } = loadSfcBindings('views/SystemSettings.vue');
  context.activeKey = ref('intel');
  context.guardrailSubTab = ref('proxy');
  context.arsenalSubTab = ref('concurrency');
  context.opsSubTab = ref('auth_infra');
  context.visitedDomains = reactive({
    intel: true, egress_guardrails: false, scanning_arsenal: true, notifications: true, system_ops: false,
  });
  context.visitedSubTabs = reactive({ proxy: false, cdn: false, backup: false, update: false });
  context.proxyPanelRef = ref({ focusSection() {} });
  context.cdnPanelRef = ref({ focusSection() {} });
  context.scrollAndFlashAnchor = () => {};
  context.settingsKeyword = ref('');
  context.highlightedAnchor = ref('');
  read('markVisitedState');
  read('applyDomainAndSubTab');
  read('SETTINGS_INDEX');
  read('jumpToSetting');
  read('LEGACY_TAB_MAP');
  read('applyRouteDeepLink');

  context.applyRouteDeepLink({ tab: 'api_config', focus: 'github_token' });
  assert.equal(context.activeKey.value, 'intel');

  context.applyRouteDeepLink({ tab: 'proxy', focus: 'osint' });
  assert.equal(context.activeKey.value, 'egress_guardrails');
  assert.equal(context.guardrailSubTab.value, 'proxy');

  context.applyRouteDeepLink({ tab: 'security' });
  assert.equal(context.activeKey.value, 'egress_guardrails');
  assert.equal(context.guardrailSubTab.value, 'security');

  context.applyRouteDeepLink({ tab: 'system_general', focus: 'brute_concurrent' });
  assert.equal(context.activeKey.value, 'scanning_arsenal');
  assert.equal(context.arsenalSubTab.value, 'concurrency');

  context.applyRouteDeepLink({ tab: 'system_general', focus: 'auth' });
  assert.equal(context.activeKey.value, 'system_ops');
  assert.equal(context.opsSubTab.value, 'auth_infra');

  context.applyRouteDeepLink({ tab: 'cdn' });
  assert.equal(context.activeKey.value, 'scanning_arsenal');
  assert.equal(context.arsenalSubTab.value, 'cdn');

  context.applyRouteDeepLink({ tab: 'message_push' });
  assert.equal(context.activeKey.value, 'notifications');

  context.applyRouteDeepLink({ tab: 'system_backup' });
  assert.equal(context.activeKey.value, 'system_ops');
  assert.equal(context.opsSubTab.value, 'backup');
});

test('CdnRulePanel: 新增/删除确认后即时落盘，请求失败时不篡改本地清单', async () => {
  const { read, context } = loadSfcBindings('components/settings/CdnRulePanel.vue');
  read('cdnList');
  read('cdnSaveLoading');
  read('cdnDrawerVisible');
  read('isEditingCdn');
  read('currentCdnForm');
  read('currentEditIndex');
  read('selectedCdnName');
  read('selectedCdn');
  read('ensureDefaultSelection');
  read('persistCdnList');
  read('submitCdnDrawer');
  read('deleteSelectedCdn');

  let failSave = false;
  const savedPayloads = [];
  context.request = {
    async post(url, body) {
      savedPayloads.push({ url, body: plain(body) });
      if (failSave) return { code: 400, message: 'invalid cidr' };
      return { code: 200 };
    },
  };

  // 新增即时保存成功
  context.currentCdnForm.name = 'Cloudflare';
  context.currentCdnForm.cnameText = 'cloudflare.net';
  context.currentCdnForm.ipText = '1.1.1.0/24';
  context.cdnDrawerVisible.value = true;
  await context.submitCdnDrawer();

  assert.equal(savedPayloads.length, 1);
  assert.equal(savedPayloads[0].url, '/api/cdn_dict/save');
  assert.equal(context.cdnList.value.length, 1);
  assert.equal(context.selectedCdnName.value, 'Cloudflare');
  assert.equal(context.cdnDrawerVisible.value, false);

  // 删除失败时不破坏当前列表
  failSave = true;
  await context.deleteSelectedCdn();
  assert.equal(context.cdnList.value.length, 1);
});

test('SystemSettings: 删除 brute 类型字典后仍正确刷新 fetchBruteDictList', async () => {
  const { read, context } = loadSfcBindings('views/SystemSettings.vue');
  context.loading = ref(false);
  context.unifiedSelectedKeys = ref(['brute_sub']);
  context.unifiedSelectedName = ref('sub_small.txt');
  context.unifiedSelectedType = ref('brute');
  context.selectedDict = ref('sub_small.txt');
  context.previewContent = ref('www\nmail');
  context.totalLines = ref(2);
  read('dictApiBase');

  const calls = [];
  context.request = {
    async post(url, body) {
      calls.push({ url, body: plain(body) });
      return { code: 200 };
    },
  };
  let refreshedBrute = 0;
  let refreshedAsset = 0;
  context.fetchBruteDictList = async () => {
    refreshedBrute += 1;
  };
  context.fetchDictList = async () => {
    refreshedAsset += 1;
  };
  read('executeDeleteDict');

  await context.executeDeleteDict('sub_small.txt');

  assert.deepEqual(calls, [{ url: '/api/brute_dict/delete_file', body: { name: 'sub_small.txt' } }]);
  assert.equal(refreshedBrute, 1);
  assert.equal(refreshedAsset, 0);
  assert.equal(context.unifiedSelectedType.value, '');
  assert.equal(context.selectedDict.value, '');
});
