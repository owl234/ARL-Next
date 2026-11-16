import assert from 'node:assert/strict';
import fs from 'node:fs';
import test, { afterEach } from 'node:test';
import vm from 'node:vm';
import { computed, nextTick, reactive, ref } from 'vue';
import { parse, compileScript } from 'vue/compiler-sfc';
import { i18n } from '../src/i18n/index.js';
import {
  formatProxyEgressLabel,
  formatProxyLevelClass,
  formatProxyPulse,
  formatProxyTagColor,
} from '../src/constants/proxyStatus.js';

const pageText = (...args) => i18n.global.t(...args);

afterEach(() => {
  i18n.global.locale.value = 'zh-CN';
});

function loadProxyManagePanelBindings() {
  const filePath = new URL('../src/components/settings/ProxyManagePanel.vue', import.meta.url);
  const raw = fs.readFileSync(filePath, 'utf8');
  const { descriptor } = parse(raw);
  const { scriptSetupAst } = compileScript(descriptor, { id: 'ProxyManagePanel.vue' });
  const bindings = {};
  for (const node of scriptSetupAst) {
    if (node.type !== 'VariableDeclaration') continue;
    for (const item of node.declarations) {
      if (item.id.type === 'Identifier' && item.init) {
        bindings[item.id.name] = descriptor.scriptSetup.content.slice(item.init.start, item.init.end);
      }
    }
  }

  const context = vm.createContext({
    pageText,
    pageLocale: i18n.global.locale,
    computed,
    reactive,
    ref,
    nextTick,
    console,
    formatProxyEgressLabel,
    formatProxyLevelClass,
    formatProxyTagColor,
  });

  const read = (name) => {
    assert.ok(bindings[name], `ProxyManagePanel.vue missing binding ${name}`);
    return vm.runInContext(`globalThis.${name} = (${bindings[name]})`, context);
  };

  return { raw, descriptor, context, read };
}

test('OSINT 出口 5 态术语在三语下保持单一事实源及前后缀契约', () => {
  const cases = [
    ['zh-CN', { state: 'direct_ok' }, '直连', 'OSINT 出口: 直连', 'success', 'is-ok', ''],
    ['zh-CN', { state: 'backup_active', active_node_name: '华南备机' }, '备节点接管 · 华南备机', 'OSINT 出口: 备节点接管 · 华南备机', 'warning', 'is-warning', 'orange'],
    ['zh-CN', { state: 'proxy_active', active_node_name: '上海出口' }, '代理出口 · 上海出口', 'OSINT 出口: 代理出口 · 上海出口', 'processing', 'is-info', ''],
    ['zh-CN', { state: 'degraded_blocked', cooldown_remaining_sec: 120 }, '出口冷却 120s', 'OSINT 出口: 出口冷却 120s', 'error', 'is-danger', 'red'],
    ['zh-CN', { state: 'proxy_unavailable' }, '代理不可用', 'OSINT 出口: 代理不可用', 'error', 'is-danger', 'red'],
    ['en-US', { state: 'backup_active', active_node_name: 'ecs-1' }, 'Backup Active · ecs-1', 'OSINT Egress: Backup Active · ecs-1', 'warning', 'is-warning', 'orange'],
    ['ru-RU', { state: 'proxy_unavailable' }, 'Прокси недоступен', 'Выход OSINT: Прокси недоступен', 'error', 'is-danger', 'red'],
  ];

  for (const [locale, runtime, plainText, prefixedText, color, levelClass, pulse] of cases) {
    i18n.global.locale.value = locale;
    assert.equal(formatProxyEgressLabel(runtime), plainText);
    assert.equal(formatProxyEgressLabel(runtime, { withPrefix: true }), prefixedText);
    assert.equal(formatProxyTagColor(runtime.state), color);
    assert.equal(formatProxyLevelClass(runtime.state), levelClass);
    assert.equal(formatProxyPulse(runtime.state), pulse);
  }

  i18n.global.locale.value = 'zh-CN';
  assert.equal(formatProxyEgressLabel({ state: 'backup_active', active_exit_id: '__direct__' }), '备节点接管');
  assert.equal(
    formatProxyEgressLabel({ state: 'degraded_blocked', cooldown_remaining_sec: 120 }, { cooldownSecOverride: 45 }),
    '出口冷却 45s',
  );
});

test('ProxyManagePanel 移除顶部全局态势条并将 OSINT 状态按需内嵌至 OSINT 策略卡', () => {
  const { raw, context, read } = loadProxyManagePanelBindings();

  assert.doesNotMatch(raw, /class="proxy-runtime-card"/);
  assert.match(raw, /data-setting-anchor="osint"[\s\S]*showOsintHeaderStatus[\s\S]*showOsintCooldownAlert[\s\S]*handleResetCooldown/);

  for (const file of [
    '../src/views/Dashboard.vue',
    '../src/components/TycTaskModal.vue',
    '../src/components/EnterpriseOsintPanel.vue',
  ]) {
    const content = fs.readFileSync(new URL(file, import.meta.url), 'utf8');
    assert.match(content, /constants\/proxyStatus/);
  }

  read('runtime');
  read('cooldownTickOffset');
  read('blockedExitsList');
  read('displayCooldownSec');
  read('showOsintHeaderStatus');
  read('showOsintCooldownAlert');
  read('osintCooldownBoxClass');
  read('osintStatusTagColor');
  read('osintStatusTagText');

  // 1. direct_only / failover 健康直连且无冷却：卡头标签与告警块均隐藏
  Object.assign(context.runtime, {
    mode: 'failover',
    state: 'direct_ok',
    active_exit_id: '__direct__',
    active_node_name: '',
    cooldown_remaining_sec: 0,
    blocked_exits: [],
  });
  assert.equal(context.showOsintHeaderStatus.value, false);
  assert.equal(context.showOsintCooldownAlert.value, false);

  // 2. proxy_active 且无冷却：仅展示卡头标签，不渲染冷却告警块
  Object.assign(context.runtime, {
    mode: 'fixed_proxy',
    state: 'proxy_active',
    active_exit_id: 'node-1',
    active_node_name: '上海代理',
    cooldown_remaining_sec: 0,
    blocked_exits: [],
  });
  assert.equal(context.showOsintHeaderStatus.value, true);
  assert.equal(context.showOsintCooldownAlert.value, false);
  assert.equal(context.osintStatusTagColor.value, 'processing');
  assert.equal(context.osintStatusTagText.value, '代理出口 · 上海代理');

  // 3. backup_active 且主出口冷却中：卡头标签 + 冷却明细与重置冷却块同步展示，并随倒计时递减
  Object.assign(context.runtime, {
    mode: 'failover',
    state: 'backup_active',
    active_exit_id: 'node-2',
    active_node_name: '华南备机',
    cooldown_remaining_sec: 180,
    blocked_exits: [
      { exit_id: '__direct__', label: '主服务器直连', reason: '创宇盾 403', ip: '192.0.2.10', remaining_sec: 180 },
    ],
  });
  context.cooldownTickOffset.value = 15;
  assert.equal(context.showOsintHeaderStatus.value, true);
  assert.equal(context.showOsintCooldownAlert.value, true);
  assert.equal(context.osintCooldownBoxClass.value, 'is-warning');
  assert.equal(context.osintStatusTagText.value, '备节点接管 · 华南备机');
  assert.equal(context.displayCooldownSec.value, 165);
  assert.equal(context.blockedExitsList.value[0].remaining_sec, 165);

  // 4. degraded_blocked：使用 danger 样式与实时倒计时文案
  Object.assign(context.runtime, {
    mode: 'direct_only',
    state: 'degraded_blocked',
    active_exit_id: '__direct__',
    active_node_name: '',
    cooldown_remaining_sec: 90,
    blocked_exits: [
      { exit_id: '__direct__', label: '主服务器直连', reason: '419 bannedLocation', ip: '', remaining_sec: 90 },
    ],
  });
  context.cooldownTickOffset.value = 10;
  assert.equal(context.showOsintHeaderStatus.value, true);
  assert.equal(context.showOsintCooldownAlert.value, true);
  assert.equal(context.osintCooldownBoxClass.value, 'is-danger');
  assert.equal(context.osintStatusTagColor.value, 'error');
  assert.equal(context.osintStatusTagText.value, '出口冷却 80s');

  // 5. proxy_unavailable 且无冷却条目：仅展示卡头异常标签，不渲染空冷却块
  Object.assign(context.runtime, {
    mode: 'fixed_proxy',
    state: 'proxy_unavailable',
    active_exit_id: '__direct__',
    active_node_name: '',
    cooldown_remaining_sec: 0,
    blocked_exits: [],
  });
  context.cooldownTickOffset.value = 0;
  assert.equal(context.showOsintHeaderStatus.value, true);
  assert.equal(context.showOsintCooldownAlert.value, false);
  assert.equal(context.osintStatusTagColor.value, 'error');
  assert.equal(context.osintStatusTagText.value, '代理不可用');
});

test('ProxyManagePanel 移除顶栏测活下拉并升级为行内复合探针、目标标签及三语优先映射', async () => {
  const { raw, context, read } = loadProxyManagePanelBindings();

  assert.doesNotMatch(raw, /batchProbePreset/);
  assert.match(raw, /<a-dropdown-button[\s\S]*handleProbeExistingNode\(record,\s*key\)/);
  assert.match(raw, /record\.last_probe\.preset[\s\S]*probePresetShortLabel\(record\.last_probe\.preset\)/);

  read('capabilities');
  read('PROBE_PRESET_I18N_MAP');
  read('probePresetShortLabel');
  read('probePresetOptions');
  read('probingNodeId');

  // 即使后端返回了硬编码中文 capabilities.presets，切英/俄语仍优先使用前端三语词条
  context.capabilities.presets = [
    { key: 'egress_ip', label: '后端硬编码中文1' },
    { key: 'miit', label: '后端硬编码中文2' },
    { key: 'tianyancha', label: '后端硬编码中文3' },
    { key: 'github', label: '后端硬编码中文4' },
    { key: 'custom_probe', label: 'Custom Probe' },
  ];

  i18n.global.locale.value = 'en-US';
  assert.deepEqual(
    context.probePresetOptions.value.map((o) => o.label),
    [
      'Egress Connectivity & Public IP',
      'MIIT ICP Connectivity',
      'Tianyancha Connectivity',
      'GitHub API Connectivity',
      'Custom Probe',
    ],
  );
  assert.equal(context.probePresetShortLabel('miit'), 'MIIT ICP');
  assert.equal(context.probePresetShortLabel('tianyancha'), 'Tianyancha');

  i18n.global.locale.value = 'ru-RU';
  assert.equal(context.probePresetShortLabel('egress_ip'), 'Внешний IP');
  assert.equal(context.probePresetOptions.value[1].label, 'Доступность MIIT ICP');

  i18n.global.locale.value = 'zh-CN';
  assert.equal(context.probePresetShortLabel('miit'), '工信部');
  assert.equal(context.probePresetShortLabel('tianyancha'), '天眼查');

  // 验证行内复合按钮默认传 egress_ip，下拉选择传指定 preset
  const probeCalls = [];
  context.request = {
    async post(url, payload) {
      probeCalls.push({ url, payload });
      return { code: 200, data: { result: { ok: true, latency_ms: 42, egress_ip: '192.0.2.99' } } };
    },
  };
  context.applyServerPayload = () => {};
  context.message = { success() {}, warning() {}, error() {} };
  read('handleProbeExistingNode');

  const node = { id: 'n-1', name: 'Node-1' };
  await context.handleProbeExistingNode(node);
  await context.handleProbeExistingNode(node, 'tianyancha');
  assert.deepEqual(JSON.parse(JSON.stringify(probeCalls)), [
    { url: '/api/system_config/proxy/probe', payload: { node_id: 'n-1', preset: 'egress_ip', save_result: true } },
    { url: '/api/system_config/proxy/probe', payload: { node_id: 'n-1', preset: 'tianyancha', save_result: true } },
  ]);
});

test('ProxyManagePanel 使用共享 SettingsActionBar 并由 SystemSettings 统一接管悬浮条', () => {
  const panelRaw = fs.readFileSync(new URL('../src/components/settings/ProxyManagePanel.vue', import.meta.url), 'utf8');
  const sysRaw = fs.readFileSync(new URL('../src/views/SystemSettings.vue', import.meta.url), 'utf8');
  const cdnRaw = fs.readFileSync(new URL('../src/components/settings/CdnRulePanel.vue', import.meta.url), 'utf8');
  const styleRaw = fs.readFileSync(new URL('../src/style.css', import.meta.url), 'utf8');

  assert.match(panelRaw, /<SettingsActionBar[\s\S]*anchor="proxy_save"/);
  assert.doesNotMatch(panelRaw, /arl-floating-action-bar/);
  assert.match(cdnRaw, /<SettingsActionBar[\s\S]*anchor="cdn_save"/);
  assert.doesNotMatch(cdnRaw, /breathing-btn/);
  assert.match(sysRaw, /<div v-if="activeSectionDirty" class="arl-floating-action-bar">[\s\S]*saveAllDirtySections/);
  assert.match(styleRaw, /\.arl-anchor-flash\b/);
  assert.match(styleRaw, /\.arl-dirty-btn\b/);
});
