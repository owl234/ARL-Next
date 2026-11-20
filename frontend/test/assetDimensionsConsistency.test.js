import assert from 'node:assert/strict';
import fs from 'node:fs';
import test, { afterEach } from 'node:test';
import vm from 'node:vm';
import { computed, reactive, ref } from 'vue';
import { parse, compileScript } from 'vue/compiler-sfc';
import { i18n } from '../src/i18n/index.js';

const assetText = (...args) => i18n.global.t(...args);
const plain = value => JSON.parse(JSON.stringify(value));
afterEach(() => { i18n.global.locale.value = 'zh-CN'; });

const EXPECTED_DIMENSIONS = [
  'site',
  'domain',
  'ip',
  'cert',
  'service',
  'fileleak',
  'url',
  'cip',
  'stat_finger',
  'wih',
  'vuln',
  'nuclei_result',
];

const EXPECTED_CHAIN_SECTION_IDS = [
  'chain-sec-site',
  'chain-sec-domain',
  'chain-sec-ip',
  'chain-sec-cert',
  'chain-sec-service',
  'chain-sec-fileleak',
  'chain-sec-url',
  'chain-sec-cip',
  'chain-sec-stat-finger',
  'chain-sec-wih',
  'chain-sec-vuln',
  'chain-sec-nuclei',
];

function loadComponent(file, initial = {}) {
  const source = fs.readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8');
  const { descriptor } = parse(source);
  const { scriptSetupAst } = compileScript(descriptor, { id: file });
  const bindings = {};
  for (const node of scriptSetupAst) {
    if (node.type !== 'VariableDeclaration') continue;
    for (const item of node.declarations) {
      if (item.id.type === 'Identifier' && item.init) {
        bindings[item.id.name] = descriptor.scriptSetup.content.slice(item.init.start, item.init.end);
      }
    }
  }
  const context = vm.createContext({ assetText, computed, reactive, ref, console, ...initial });
  return {
    source,
    descriptor,
    context,
    read(name) {
      assert.ok(bindings[name], `${file}: missing binding ${name}`);
      vm.runInContext(`globalThis.${name} = ${bindings[name]}`, context);
      return context[name];
    },
  };
}

test('资产搜索、资产组详情、任务详情与全链路画像抽屉统一为 12 个资产维度且均含 nuclei', () => {
  const assetSearch = loadComponent('views/AssetSearch.vue');
  const assetTabKeys = plain(assetSearch.read('assetTabList').map(tab => tab.key));
  assert.deepEqual(assetTabKeys, EXPECTED_DIMENSIONS);

  const groupDetail = loadComponent('views/GroupAssetsDetail.vue');
  const asmTabKeys = plain(groupDetail.read('asmTabList').map(tab => tab.key));
  assert.deepEqual(asmTabKeys, EXPECTED_DIMENSIONS);

  const taskDetailSource = fs.readFileSync(new URL('../src/views/TaskDetail.vue', import.meta.url), 'utf8');
  const taskTabKeys = [...taskDetailSource.matchAll(/<a-tab-pane[^>]*key="([^"]+)"/g)]
    .map(([, key]) => key)
    .filter(key => key !== 'syslog');
  assert.deepEqual(taskTabKeys, EXPECTED_DIMENSIONS);

  const iconStubs = Object.fromEntries([
    'GlobalOutlined', 'LinkOutlined', 'CloudServerOutlined', 'SafetyCertificateOutlined',
    'ApiOutlined', 'FileSearchOutlined', 'DeploymentUnitOutlined', 'ClusterOutlined',
    'TagOutlined', 'RadarChartOutlined', 'BugOutlined', 'FireOutlined',
  ].map(name => [name, name]));
  const chainData = ref({});
  const chain = loadComponent('components/ChainDrawer.vue', { chainData, ...iconStubs });
  chain.read('statFingerList');
  chain.read('unifiedServiceList');
  chain.read('nmapServiceCount');
  chain.read('npocServiceCount');
  chain.read('mergedServiceCount');
  const chips = chain.read('metricChips').value;
  assert.equal(chips.length, 12);
  assert.deepEqual(plain(chips.map(chip => chip.id)), EXPECTED_CHAIN_SECTION_IDS);
});

test('ChainDrawer 将 Nmap 与 Python 插件服务按端点去重融合为单一服务表，且保留导出 JSON 原样结构', async () => {
  const iconStubs = Object.fromEntries([
    'GlobalOutlined', 'LinkOutlined', 'CloudServerOutlined', 'SafetyCertificateOutlined',
    'ApiOutlined', 'FileSearchOutlined', 'DeploymentUnitOutlined', 'ClusterOutlined',
    'TagOutlined', 'RadarChartOutlined', 'BugOutlined', 'FireOutlined',
  ].map(name => [name, name]));

  const sampleData = {
    site: [{ site: 'https://app.example.test', finger: [{ name: 'Nginx' }, { name: 'Vue' }] }],
    domain_records: [{ domain: 'app.example.test', ips: ['192.0.2.10'] }],
    ip: [],
    cert: [],
    service: [
      { ip: '192.0.2.10', port_id: 80, service_name: 'http', product: 'Nginx', version: '1.24', sources: ['nmap'] },
      { ip: '192.0.2.10', port_id: 6379, service_name: 'unknown', product: 'Redis', version: '7.0', sources: ['nmap'] },
    ],
    npoc_service: [
      { _id: 'n1', scheme: 'redis', host: '192.0.2.10', port: '6379', target: 'redis://192.0.2.10:6379' },
      { _id: 'n2', scheme: 'ssh', host: '192.0.2.10', port: '22', target: 'ssh://192.0.2.10:22' },
    ],
    fileleak: [],
    url: [],
    cip: [],
    wih: [],
    vuln: [],
    nuclei_result: [{ template_id: 'cve-test', vuln_name: 'Test CVE', vuln_severity: 'high' }],
  };

  const chainData = ref(sampleData);
  const blobs = [];
  const links = [];
  const chain = loadComponent('components/ChainDrawer.vue', {
    props: { target: 'app.example.test' },
    chainData,
    Blob,
    URL: { createObjectURL(blob) { blobs.push(blob); return 'blob:test'; }, revokeObjectURL() {} },
    document: { createElement() { const link = { click() {}, remove() {} }; links.push(link); return link; }, body: { appendChild() {} } },
    dayjs: () => ({ format: () => '20261119_120000' }),
    message: { success() {}, warning(err) { assert.fail(err); }, error(err) { assert.fail(err); } },
    ...iconStubs,
  });

  chain.read('statFingerList');
  const unifiedList = chain.read('unifiedServiceList');
  chain.read('nmapServiceCount');
  chain.read('npocServiceCount');
  const mergedCount = chain.read('mergedServiceCount');
  const metricChips = chain.read('metricChips');
  const hitCategoryCount = chain.read('hitCategoryCount');
  const emptyCategoryCount = chain.read('emptyCategoryCount');
  const totalRecords = chain.read('totalRecords');

  // 192.0.2.10:6379 被 Nmap 与 Python 插件同时命中，自动按 (ip, port) 去重归并为 1 条并校准为 redis
  assert.equal(mergedCount.value, 3);
  const redisEp = unifiedList.value.find(item => String(item.port_id) === '6379');
  assert.equal(redisEp.service_name, 'redis');
  assert.equal(redisEp.product, 'Redis');
  assert.deepEqual(plain(redisEp.sources), ['nmap', 'npoc']);

  assert.equal(metricChips.value.length, 12);
  assert.equal(metricChips.value.find(c => c.id === 'chain-sec-service').count, 3);
  assert.equal(metricChips.value.find(c => c.id === 'chain-sec-nuclei').count, 1);
  // 命中维度：site(1)、domain(1)、service(3)、stat_finger(2)、nuclei(1) 共 5 维，其余 7 维为空
  assert.equal(hitCategoryCount.value, 5);
  assert.equal(emptyCategoryCount.value, 7);
  assert.equal(totalRecords.value, 1 + 1 + 3 + 2 + 1);

  // 仅命中 Python 插件服务时，仍计为命中「服务」这 1 个维度
  chainData.value = { service: [], npoc_service: [{ _id: 'n1', scheme: 'redis', target: '192.0.2.10:6379' }] };
  assert.equal(mergedCount.value, 1);
  assert.equal(hitCategoryCount.value, 1);
  assert.equal(emptyCategoryCount.value, 11);
  assert.equal(totalRecords.value, 1);

  // 导出 JSON 保持后端原始结构，service 与 npoc_service 双键均完整保留
  chainData.value = sampleData;
  chain.read('downloadChainJson')();
  const exported = JSON.parse(await blobs[0].text());
  assert.deepEqual(exported.service, sampleData.service);
  assert.deepEqual(exported.npoc_service, sampleData.npoc_service);

  // 模板不再存在独立 chain-sec-npoc 卡片，也不再拆分为双引擎子区块
  assert.doesNotMatch(chain.source, /id="chain-sec-npoc"/);
  assert.match(chain.source, /id="chain-sec-service"/);
  assert.match(chain.source, /unifiedServiceList/);
});

test('AssetSearch、GroupAssetsDetail 与 TaskDetail 服务页签统一为融合单表且移除二级引擎切换栏', () => {
  const assetSearch = loadComponent('views/AssetSearch.vue', { route: { query: {} } });
  const overviewCounts = assetSearch.read('overviewCounts');
  const getOverviewTabCount = assetSearch.read('getOverviewTabCount');

  // 初始未拉取完成时返回 undefined
  assert.equal(getOverviewTabCount('service'), undefined);
  assert.equal(getOverviewTabCount('nuclei_result'), undefined);

  // 正常返回时 service 页签直接展示后端已融合去重的 service 计数
  overviewCounts.value = { site: 10, service: 12, npoc_service: 5, nuclei_result: 3 };
  assert.equal(getOverviewTabCount('service'), 12);
  assert.equal(getOverviewTabCount('site'), 10);
  assert.equal(getOverviewTabCount('nuclei_result'), 3);

  // 兼容旧数据：若 service 为 0 而 npoc_service 非 0，回退展示 npoc_service
  overviewCounts.value = { service: 0, npoc_service: 4 };
  assert.equal(getOverviewTabCount('service'), 4);

  // 任一服务计数失败返回 null 时，整体服务徽标降级为 null（UI 展示 "-"）
  overviewCounts.value = { service: 12, npoc_service: null };
  assert.equal(getOverviewTabCount('service'), null);
  overviewCounts.value = { service: null, npoc_service: 5 };
  assert.equal(getOverviewTabCount('service'), null);

  // 三个主视图均已移除 serviceEngineType 二级切换单选栏
  const groupDetailSource = fs.readFileSync(new URL('../src/views/GroupAssetsDetail.vue', import.meta.url), 'utf8');
  const taskDetailSource = fs.readFileSync(new URL('../src/views/TaskDetail.vue', import.meta.url), 'utf8');
  assert.doesNotMatch(assetSearch.source, /serviceEngineType/);
  assert.doesNotMatch(groupDetailSource, /serviceEngineType/);
  assert.doesNotMatch(taskDetailSource, /serviceEngineType/);
});
