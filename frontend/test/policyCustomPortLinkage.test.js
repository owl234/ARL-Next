import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test, { afterEach } from 'node:test';
import vm from 'node:vm';
import { computed, reactive, ref } from 'vue';
import { parse, compileScript } from 'vue/compiler-sfc';

import { i18n } from '../src/i18n/index.js';
import pagesZh from '../src/i18n/pages.zh-CN.js';
import pagesEn from '../src/i18n/pages.en-US.js';
import pagesRu from '../src/i18n/pages.ru-RU.js';
import {
  classifyAssetDictionaries,
  describeDictOption,
  formatPortPolicyLabel,
  hasLegacyInlineCustomPorts,
  normalizeDomainDict,
  normalizePortDict,
  shouldPreviewPortDict,
} from '../src/utils/dictHelpers.js';

const FRONTEND_DIR = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const t = (...args) => i18n.global.t(...args);

afterEach(() => {
  i18n.global.locale.value = 'zh-CN';
});

test('dictHelpers: 字典分类不依赖语言包文案，完整包含 port_custom.txt 并排除 port_alive.txt', () => {
  const rawList = [
    { name: 'port_all.txt', size: 8, category: '🔌 端口扫描策略 (Port Config)' },
    { name: 'port_alive.txt', size: 147, category: '🔌 端口扫描策略 (Port Config)' },
    { name: 'port_team_web.txt', size: 42, category: '🔌 端口扫描策略 (Port Config)' },
    { name: 'port_custom.txt', size: 17, category: '🔌 端口扫描策略 (Port Config)' },
    { name: 'port_top1000.txt', size: 4775, category: '🔌 端口扫描策略 (Port Config)' },
    { name: 'port_top100.txt', size: 1318, category: '🔌 端口扫描策略 (Port Config)' },
    { name: 'domain_2w.txt', size: 204800, category: '🌍 子域名爆破 (Subdomain Bruteforce)' },
    { name: 'altdnsdict.txt', size: 12000, category: '🧠 智能子域爆破 (AltDNS Dict)' },
    { name: 'file_top_2000.txt', size: 32000, category: '📂 目录文件泄露 (File/Dir Leak)' },
  ];

  for (const locale of ['zh-CN', 'en-US', 'ru-RU']) {
    i18n.global.locale.value = locale;
    const classified = classifyAssetDictionaries(rawList);
    assert.deepEqual(
      classified.portDicts.map((item) => item.name),
      ['port_top100.txt', 'port_top1000.txt', 'port_custom.txt', 'port_all.txt', 'port_team_web.txt'],
      `locale=${locale}`
    );
    assert.deepEqual(classified.domainDicts.map((item) => item.name), ['domain_2w.txt']);
    assert.deepEqual(classified.altDnsDicts.map((item) => item.name), ['altdnsdict.txt']);
    assert.deepEqual(classified.fileLeakDicts.map((item) => item.name), ['file_top_2000.txt']);
  }
});

test('dictHelpers: 历史别名归一化、端口预览判定与旧手填端口识别准确', () => {
  assert.equal(normalizePortDict('test'), 'port_top100.txt');
  assert.equal(normalizePortDict('top100'), 'port_top100.txt');
  assert.equal(normalizePortDict('top1000'), 'port_top1000.txt');
  assert.equal(normalizePortDict('all'), 'port_all.txt');
  assert.equal(normalizePortDict('port_all'), 'port_all.txt');
  assert.equal(normalizePortDict('custom'), 'port_custom.txt');
  assert.equal(normalizePortDict('port_custom'), 'port_custom.txt');
  assert.equal(normalizePortDict('port_custom.txt'), 'port_custom.txt');
  assert.equal(normalizePortDict('port_team_web.txt'), 'port_team_web.txt');
  assert.equal(normalizeDomainDict('big'), 'domain_2w.txt');
  assert.equal(normalizeDomainDict('test'), 'domain_top300.txt');

  assert.equal(shouldPreviewPortDict('port_custom.txt'), true);
  assert.equal(shouldPreviewPortDict('port_team_web.txt'), true);
  assert.equal(shouldPreviewPortDict('port_top100.txt'), false);
  assert.equal(shouldPreviewPortDict('port_top1000.txt'), false);
  assert.equal(shouldPreviewPortDict('port_all.txt'), false);
  assert.equal(shouldPreviewPortDict('port_alive.txt'), false);

  assert.equal(hasLegacyInlineCustomPorts({ port_scan_type: 'custom', port_custom: '80,443' }), true);
  assert.equal(hasLegacyInlineCustomPorts({ port_scan_type: 'custom', port_custom: '' }), false);
  assert.equal(hasLegacyInlineCustomPorts({ port_scan_type: 'port_custom.txt', port_custom: '80,443' }), false);
});

test('dictHelpers: 三语端口字典选项与策略摘要展示一致且兼容存量手填端口', () => {
  i18n.global.locale.value = 'zh-CN';
  assert.equal(describeDictOption({ name: 'port_custom.txt', size: 17 }, t), '自定义端口');
  assert.equal(describeDictOption({ name: 'port_team.txt', size: 512 }, t), 'port_team.txt (512 B)');
  assert.equal(formatPortPolicyLabel('port_custom.txt', '', t), '自定义端口');
  assert.equal(formatPortPolicyLabel('custom', '', t), '自定义端口');
  assert.equal(formatPortPolicyLabel('custom', '80,443,8080', t), '自定义端口 (80,443,8080)');
  assert.equal(formatPortPolicyLabel('port_all.txt', '', t), '全端口 (1-65535)');
  assert.equal(formatPortPolicyLabel('test', '', t), 'Top 100 常用端口');

  i18n.global.locale.value = 'en-US';
  assert.equal(formatPortPolicyLabel('port_custom.txt', '', t), 'Custom ports');
  assert.equal(formatPortPolicyLabel('custom', '80,443', t), 'Custom ports (80,443)');
  assert.equal(formatPortPolicyLabel('port_all.txt', '', t), 'All ports (1–65535)');

  i18n.global.locale.value = 'ru-RU';
  assert.equal(formatPortPolicyLabel('port_custom.txt', '', t), 'Произвольные порты');
  assert.equal(formatPortPolicyLabel('custom', '80,443', t), 'Пользовательские порты (80,443)');
});

test('TaskList.getDetailedOptions: 端口字典文件名展示可读标签而非生硬大写文件名', () => {
  const source = fs.readFileSync(path.join(FRONTEND_DIR, 'src/views/TaskList.vue'), 'utf8');
  const { descriptor } = parse(source);
  const { scriptSetupAst } = compileScript(descriptor, { id: 'TaskList.vue' });
  let binding = '';
  for (const node of scriptSetupAst) {
    if (node.type !== 'VariableDeclaration') continue;
    for (const item of node.declarations) {
      if (item.id.type === 'Identifier' && item.id.name === 'getDetailedOptions' && item.init) {
        binding = descriptor.scriptSetup.content.slice(item.init.start, item.init.end);
      }
    }
  }
  assert.ok(binding, 'getDetailedOptions binding not found');
  const ctx = vm.createContext({ taskText: t, pluginList: [], computed, reactive, ref });
  const getDetailedOptions = vm.runInContext(`(${binding})`, ctx);

  i18n.global.locale.value = 'zh-CN';
  assert.deepEqual(
    JSON.parse(JSON.stringify(getDetailedOptions({ port_scan: true, port_scan_type: 'port_custom.txt' }))),
    ['端口扫描策略: 自定义端口']
  );
  assert.deepEqual(
    JSON.parse(JSON.stringify(getDetailedOptions({ port_scan: true, port_scan_type: 'custom', port_custom: '80,8443' }))),
    ['端口扫描策略: 自定义端口 (80,8443)']
  );
  assert.deepEqual(
    JSON.parse(JSON.stringify(getDetailedOptions({ port_scan: true, port_scan_type: 'port_all.txt' }))),
    ['端口扫描策略: 全端口 (1-65535)']
  );
});

test('PolicyDetail / SystemSettings 结构与三语 i18n 键完整对齐且已清理孤立键', () => {
  const policyDetail = fs.readFileSync(path.join(FRONTEND_DIR, 'src/views/PolicyDetail.vue'), 'utf8');
  assert.doesNotMatch(policyDetail, /item\.name !== 'port_custom\.txt'/);
  assert.doesNotMatch(policyDetail, /value="custom">\{\{\s*pageText\('tasks\.customPorts'\)\s*\}\}/);
  assert.doesNotMatch(policyDetail, /v-model:value="policyForm\.ip_config\.port_custom"/);
  assert.match(policyDetail, /port-dict-preview-box/);
  assert.match(policyDetail, /openSystemPortDictSettings/);
  assert.match(policyDetail, /path:\s*'\/systemSettings'/);
  assert.match(policyDetail, /legacyCustomPortMigrationNotice/);

  const systemSettings = fs.readFileSync(path.join(FRONTEND_DIR, 'src/views/SystemSettings.vue'), 'utf8');
  assert.match(systemSettings, /pendingDeepLinkDict/);
  assert.match(systemSettings, /selectDictByName/);
  assert.match(systemSettings, /route\.query\.dict/);

  const newKeys = [
    'portDictLinkedHint',
    'portDictPreviewEntriesCount',
    'portDictPreviewLoading',
    'portDictPreviewLoadFailed',
    'portDictPreviewEmptyFallback',
    'managePortDictInSystemSettings',
    'legacyCustomPortMigrationNotice',
    'portDictMoreEntriesSuffix',
  ];
  for (const key of newKeys) {
    assert.ok(pagesZh[key], `pages.zh-CN missing ${key}`);
    assert.ok(pagesEn[key], `pages.en-US missing ${key}`);
    assert.ok(pagesRu[key], `pages.ru-RU missing ${key}`);
  }

  const removedKeys = [
    'customPortRange',
    'eG8044380008080',
    'enterAPortRangeForTheCustomPortPolicy',
    'subdomainDiscovery',
    'smart',
    'subdomainMutationDiscovery',
    'directoryAndFileDisclosure',
    'directoryAndFileDisclosures',
  ];
  for (const key of removedKeys) {
    assert.equal(pagesZh[key], undefined, `orphan key still in zh-CN: ${key}`);
    assert.equal(pagesEn[key], undefined, `orphan key still in en-US: ${key}`);
    assert.equal(pagesRu[key], undefined, `orphan key still in ru-RU: ${key}`);
  }
});
