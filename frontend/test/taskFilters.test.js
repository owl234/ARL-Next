import assert from 'node:assert/strict';
import test from 'node:test';
import {
  buildTaskQueryParams,
  countActiveAdvancedFilters,
  formatAssetYieldTriggerLabel,
  isAssetYieldFilterActive,
  normalizeAssetYieldDimensions,
} from '../src/utils/taskFilters.js';

test('buildTaskQueryParams 使用双下划线 __gt/__lt 修复数值高级筛选并覆盖全部 6 维', () => {
  const params = buildTaskQueryParams({
    name: 'scan-a',
    status: 'done',
    site_count: '5',
    site_operator: '>',
    domain_count: '10',
    domain_operator: '<',
    ip_count: '3',
    ip_operator: '=',
    wih_count: '2',
    wih_operator: '>',
    vuln_count: '1',
    vuln_operator: '>',
    nuclei_count: '4',
    nuclei_operator: '<',
  }, { page: 2, size: 20 });

  assert.deepEqual(params, {
    page: 2,
    size: 20,
    name: 'scan-a',
    status: 'done',
    'statistic.site_cnt__gt': 5,
    'statistic.domain_cnt__lt': 10,
    'statistic.ip_cnt': 3,
    'statistic.wih_cnt__gt': 2,
    'statistic.vuln_cnt__gt': 1,
    'statistic.nuclei_result_cnt__lt': 4,
  });
  assert.equal('statistic.site_cnt_gt' in params, false);
  assert.equal('statistic.domain_cnt_lt' in params, false);
});

test('buildTaskQueryParams 正确映射有产出、无产出（已结束）与多选维度 OR 参数', () => {
  assert.deepEqual(
    buildTaskQueryParams({ asset_yield: 'has_asset', asset_types: [] }, { page: 1, size: 10 }),
    { page: 1, size: 10, asset_yield: 'has_asset' },
  );

  assert.deepEqual(
    buildTaskQueryParams({ asset_yield: 'no_asset', asset_types: ['site'] }, { page: 1, size: 10 }),
    { page: 1, size: 10, asset_yield: 'no_asset' },
  );

  assert.deepEqual(
    buildTaskQueryParams({ asset_yield: 'has_asset', asset_types: ['ip', 'site', 'invalid'] }, { page: 1, size: 10 }),
    { page: 1, size: 10, asset_types: 'site,ip' },
  );
});

test('countActiveAdvancedFilters 计入全部 6 维数值筛选且不重复计入常驻产出筛选', () => {
  assert.equal(countActiveAdvancedFilters({
    asset_yield: 'has_asset',
    asset_types: ['site', 'ip'],
    task_id: '',
    site_count: '',
    ip_count: '2',
    nuclei_count: '1',
  }), 2);
});

test('formatAssetYieldTriggerLabel 与 isAssetYieldFilterActive 展示准确', () => {
  const dimLabels = { site: '站点', domain: '域名', ip: 'IP', wih: 'WIH', vuln: '风险', nuclei: 'Nuclei' };
  const texts = {
    allTrigger: '资产产出: 全部',
    hasAssetShort: '有产出 (核心6维)',
    noAsset: '无产出（已结束）',
    selectedDims: (labels) => `有产出: ${labels}`,
    selectedDimsMore: (labels, count) => `有产出: ${labels} +${count}`,
  };

  assert.equal(isAssetYieldFilterActive({ asset_yield: '', asset_types: [] }), false);
  assert.equal(formatAssetYieldTriggerLabel({ asset_yield: '', asset_types: [] }, dimLabels, texts), '资产产出: 全部');

  assert.equal(isAssetYieldFilterActive({ asset_yield: 'has_asset', asset_types: [] }), true);
  assert.equal(formatAssetYieldTriggerLabel({ asset_yield: 'has_asset', asset_types: [] }, dimLabels, texts), '有产出 (核心6维)');

  assert.equal(formatAssetYieldTriggerLabel({ asset_yield: 'no_asset', asset_types: [] }, dimLabels, texts), '无产出（已结束）');
  assert.equal(formatAssetYieldTriggerLabel({ asset_yield: 'has_asset', asset_types: ['ip', 'site'] }, dimLabels, texts), '有产出: 站点 / IP');
  assert.equal(formatAssetYieldTriggerLabel({ asset_yield: 'has_asset', asset_types: ['site', 'domain', 'ip', 'vuln'] }, dimLabels, texts), '有产出: 站点 / 域名 +2');
  assert.deepEqual(normalizeAssetYieldDimensions(['nuclei', 'site', 'site', 'bogus']), ['site', 'nuclei']);
});
