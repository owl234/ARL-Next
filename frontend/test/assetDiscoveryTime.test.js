import assert from 'node:assert/strict';
import fs from 'node:fs';
import test, { afterEach } from 'node:test';
import vm from 'node:vm';
import { computed, reactive, ref } from 'vue';
import { parse, compileScript } from 'vue/compiler-sfc';
import dayjs from 'dayjs';
import { i18n } from '../src/i18n/index.js';
import {
  buildAssetFilterParams,
  buildAssetSortOrder,
  extractTableSortState,
} from '../src/utils/assetFilters.js';
import { createTabStateCache } from '../src/utils/useTabStateCache.js';

const t = (...args) => i18n.global.t(...args);
const plain = v => JSON.parse(JSON.stringify(v));
afterEach(() => { i18n.global.locale.value = 'zh-CN'; });

const ALL_12_DIMENSIONS = [
  'site', 'domain', 'ip', 'cert', 'service', 'fileleak',
  'url', 'cip', 'stat_finger', 'wih', 'vuln', 'nuclei_result',
];

function loadSfcBindings(relPath, initial = {}) {
  const source = fs.readFileSync(new URL(`../src/${relPath}`, import.meta.url), 'utf8');
  const { descriptor } = parse(source);
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
  const context = vm.createContext({
    t, assetText: t, taskText: t, computed, reactive, ref, console, ...initial,
  });
  return {
    source,
    descriptor,
    context,
    read(name) {
      assert.ok(bindings[name], `${relPath}: missing binding ${name}`);
      vm.runInContext(`globalThis.${name} = ${bindings[name]}`, context);
      return context[name];
    },
  };
}

test('三页 12 个维度均配置可排序 save_date 列、正确列位且清除历史 insert_time / savedAt 残留', () => {
  const views = [
    { file: 'views/GroupAssetsDetail.vue', expectTitle: '发现 / 更新时间', hasSaveFilter: true, hasUpdateFilter: true },
    { file: 'views/AssetSearch.vue', expectTitle: null, hasSaveFilter: true, hasUpdateFilter: false },
    { file: 'views/TaskDetail.vue', expectTitle: '发现时间', hasSaveFilter: false, hasUpdateFilter: false },
  ];

  for (const { file, expectTitle, hasSaveFilter, hasUpdateFilter } of views) {
    const view = loadSfcBindings(file);
    const tabConfig = view.read('tabConfig');

    for (const dim of ALL_12_DIMENSIONS) {
      const cfg = tabConfig[dim];
      assert.ok(cfg, `${file}: missing tabConfig.${dim}`);
      const cols = cfg.cols;
      assert.ok(Array.isArray(cols) && cols.length > 0, `${file}.${dim}: empty cols`);

      // 无存量 insert_time 绑定
      assert.equal(cols.some(c => c.key === 'insert_time' || c.dataIndex === 'insert_time'), false, `${file}.${dim}: stale insert_time`);
      // 无旧文案 "保存时间"
      assert.equal(cols.some(c => c.title === '保存时间'), false, `${file}.${dim}: stale 保存时间`);

      const timeIdx = cols.findIndex(c => c.key === 'save_date');
      assert.ok(timeIdx >= 0, `${file}.${dim}: missing save_date column`);
      assert.equal(cols[timeIdx].dataIndex, 'save_date', `${file}.${dim}: dataIndex must be save_date`);
      assert.equal(cols[timeIdx].sorter, true, `${file}.${dim}: save_date must have sorter: true`);

      // 列位校验：site 在指纹与截图之间；nuclei_result 在等级与验证命令之间；其余在末列
      if (dim === 'site') {
        assert.equal(cols[timeIdx + 1]?.key, 'screenshot', `${file}.site: save_date should precede screenshot`);
      } else if (dim === 'nuclei_result') {
        assert.equal(cols[timeIdx + 1]?.key, 'verify_command', `${file}.nuclei_result: save_date should precede verify_command`);
      } else {
        assert.equal(timeIdx, cols.length - 1, `${file}.${dim}: save_date should be the last column`);
      }

      // 标题口径校验
      if (expectTitle) {
        assert.equal(cols[timeIdx].title, expectTitle, `${file}.${dim}: title mismatch`);
      } else {
        const expectedSearchTitle = ['service', 'cip', 'stat_finger'].includes(dim)
          ? '发现 / 最近出现'
          : '发现时间';
        assert.equal(cols[timeIdx].title, expectedSearchTitle, `${file}.${dim}: AssetSearch title mismatch`);
      }

      // 筛选字段契约校验
      const fields = cfg.searchFields || [];
      const hasSave = fields.some(f => f.key === 'save_date' && f.type === 'dateRange');
      const hasUpd = fields.some(f => f.key === 'update_date' && f.type === 'dateRange');
      assert.equal(hasSave, hasSaveFilter, `${file}.${dim}: save_date dateRange filter mismatch`);
      assert.equal(hasUpd, hasUpdateFilter, `${file}.${dim}: update_date dateRange filter mismatch`);
    }
  }
});

test('dateRange 参数全天归一（含单日查询）及排序工具函数行为一致', () => {
  const fields = [{ key: 'save_date', type: 'dateRange' }];
  // 选择同一天，且对象带有非零当前时分秒，仍应归并到 00:00:00 ~ 23:59:59
  const sameDay = buildAssetFilterParams(
    { save_date: [dayjs('2026-11-21 11:35:10'), dayjs('2026-11-21 11:35:10')] },
    fields,
  );
  assert.deepEqual(sameDay, {
    save_date__dgt: '2026-11-21 00:00:00',
    save_date__dlt: '2026-11-21 23:59:59',
  });

  assert.equal(buildAssetSortOrder({ field: 'save_date', order: 'descend' }), '-save_date');
  assert.equal(buildAssetSortOrder({ field: 'save_date', order: 'ascend' }), '+save_date');
  assert.equal(buildAssetSortOrder({ field: 'save_date', order: null }), '');
  assert.deepEqual(extractTableSortState({ columnKey: 'save_date', order: 'descend' }), { field: 'save_date', order: 'descend' });
  assert.deepEqual(extractTableSortState({ columnKey: 'save_date', order: undefined }), { field: '', order: null });
});

test('tabCache 独立保存、恢复与复位各 Tab 的排序状态', () => {
  const tabConfig = {
    site: { searchFields: [{ key: 'save_date', type: 'dateRange' }] },
    domain: { searchFields: [{ key: 'save_date', type: 'dateRange' }] },
  };
  const cache = createTabStateCache({ getStorageKey: () => null, tabConfig, defaultTab: 'site' });
  cache.saveCurrentTab('site', {}, 1, { field: 'save_date', order: 'descend' });
  cache.saveCurrentTab('domain', {}, 2, { field: 'save_date', order: 'ascend' });
  assert.deepEqual(cache.getTabSort('site'), { field: 'save_date', order: 'descend' });
  assert.deepEqual(cache.getTabSort('domain'), { field: 'save_date', order: 'ascend' });

  cache.resetTabState('site');
  assert.deepEqual(cache.getTabSort('site'), { field: '', order: null });
  assert.deepEqual(cache.getTabSort('domain'), { field: 'save_date', order: 'ascend' });
});

test('AssetTimeCell 单双行判定与兜底逻辑符合预期', () => {
  const evalCell = (props) => {
    const comp = loadSfcBindings('components/AssetTimeCell.vue', { props });
    comp.read('normalizeTimeText');
    const primaryTime = comp.read('primaryTime');
    const secondaryTime = comp.read('secondaryTime');
    const showSecondaryLine = comp.read('showSecondaryLine');
    const secondaryShortLabel = comp.read('secondaryShortLabel');
    return {
      primary: primaryTime.value,
      secondary: secondaryTime.value,
      showSecondary: showSecondaryLine.value,
      prefix: secondaryShortLabel.value,
    };
  };

  // 1. 仅发现一次（save_date === update_date）不展开次行
  assert.deepEqual(
    evalCell({ record: { save_date: '2026-11-10 10:00:00', update_date: '2026-11-10 10:00:00' }, showSecondary: true, secondaryMode: 'update' }),
    { primary: '2026-11-10 10:00:00', secondary: '2026-11-10 10:00:00', showSecondary: false, prefix: '更新' },
  );

  // 2. 复扫更新后（update_date !== save_date）展开次行
  assert.deepEqual(
    evalCell({ record: { save_date: '2026-11-01 10:00:00', update_date: '2026-11-20 12:30:00' }, showSecondary: true, secondaryMode: 'update' }),
    { primary: '2026-11-01 10:00:00', secondary: '2026-11-20 12:30:00', showSecondary: true, prefix: '更新' },
  );

  // 3. 资产搜索跨任务聚合维度使用「最近」前缀
  assert.deepEqual(
    evalCell({ record: { save_date: '2026-11-01 10:00:00', update_date: '2026-11-20 12:30:00' }, showSecondary: true, secondaryMode: 'latest' }),
    { primary: '2026-11-01 10:00:00', secondary: '2026-11-20 12:30:00', showSecondary: true, prefix: '最近' },
  );

  // 4. 空记录回退为空串（模板渲染 "-"）
  assert.deepEqual(
    evalCell({ record: {}, showSecondary: true, secondaryMode: 'update' }),
    { primary: '', secondary: '', showSecondary: false, prefix: '更新' },
  );
});

test('ChainDrawer 全链路画像抽屉统一复用发现/更新时间并保留归并时间', () => {
  const sampleData = {
    site: [
      { site: 'https://a.example.test', finger: [{ name: 'Nginx' }], save_date: '2026-11-01 10:00:00', update_date: '2026-11-10 10:00:00' },
      { site: 'https://b.example.test', finger: [{ name: 'Nginx' }], save_date: '2026-11-05 10:00:00', update_date: '2026-11-20 10:00:00' },
    ],
    service: [
      { ip: '192.0.2.10', port_id: 6379, service_name: 'unknown', sources: ['nmap'], save_date: '2026-11-02 08:00:00', update_date: '2026-11-12 08:00:00' },
    ],
    npoc_service: [
      { scheme: 'redis', host: '192.0.2.10', port: '6379', save_date: '2026-11-01 08:00:00', update_date: '2026-11-18 08:00:00' },
    ],
  };

  const chain = loadSfcBindings('components/ChainDrawer.vue', { chainData: ref(sampleData) });
  for (const colName of ['domainCols', 'ipCols', 'cipCols', 'serviceCols', 'fileleakCols', 'urlCols', 'fingerCols', 'wihCols']) {
    const cols = chain.read(colName);
    const timeCol = cols.find(c => c.key === 'save_date');
    assert.ok(timeCol, `ChainDrawer.${colName}: missing save_date column`);
    assert.equal(timeCol.title, '发现 / 更新时间');
  }

  const statFingers = plain(chain.read('statFingerList').value);
  assert.equal(statFingers[0].save_date, '2026-11-01 10:00:00');
  assert.equal(statFingers[0].update_date, '2026-11-20 10:00:00');

  const services = plain(chain.read('unifiedServiceList').value);
  assert.equal(services[0].save_date, '2026-11-01 08:00:00');
  assert.equal(services[0].update_date, '2026-11-18 08:00:00');
});

test('三页排序状态透传为后端 order 参数并在重置时清空', async () => {
  for (const name of ['AssetSearch', 'TaskDetail', 'GroupAssetsDetail']) {
    const view = loadSfcBindings(`views/${name}.vue`, {
      reactive: v => v,
      buildAssetFilterParams,
      buildAssetSortOrder,
      extractTableSortState,
      activeTab: ref('site'),
      searchForm: ref({}),
      columns: ref([]),
      sortState: reactive({ field: '', order: null }),
      lastFetchedPage: 1,
      lastFetchedSize: 20,
      pagination: { current: 2, pageSize: 20, total: 2 },
      taskId: ref('task-a'),
      scope_id: ref('scope-a'),
      loading: ref(false),
      dataSource: ref([]),
      asmCounts: {},
      selectionTracker: { rememberRows() {}, syncSelection() {}, getLabels: () => [], clear() {} },
      getAssetRowKey: r => r?._id || r?.id,
      getAssetRecordDisplayLabel: () => '',
      tabCache: {
        updateMemoryCache() {},
        saveCurrentTab() {},
        resetTabState() {},
        invalidateMemoryCache() {},
      },
      message: { error(err) { assert.fail(err); } },
      request: {
        calls: [],
        async get(url, opts) {
          this.calls.push({ url, params: plain(opts.params) });
          return { code: 200, items: [], total: 0 };
        },
      },
    });
    view.read('tabConfig');
    if (name === 'TaskDetail') view.read('resolveAssetEndpoint');
    view.read('effectiveTab');
    view.read('fetchData');
    const handleTableSortChange = view.read('handleTableSortChange');
    const resetSearch = view.read('resetSearch');

    await handleTableSortChange({}, {}, { columnKey: 'save_date', order: 'descend' });
    assert.equal(view.context.request.calls[0].params.order, '-save_date');
    assert.equal(view.context.request.calls[0].params.page, 1);

    await handleTableSortChange({}, {}, { columnKey: 'save_date', order: 'ascend' });
    assert.equal(view.context.request.calls[1].params.order, '+save_date');

    await resetSearch();
    assert.equal('order' in view.context.request.calls[2].params, false);
  }
});
