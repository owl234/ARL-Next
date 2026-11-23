export const TASK_ASSET_YIELD_DIMENSION_KEYS = Object.freeze([
  'site',
  'domain',
  'ip',
  'wih',
  'vuln',
  'nuclei',
]);

export const TASK_NUMERIC_FILTER_SPECS = Object.freeze([
  { countKey: 'site_count', operatorKey: 'site_operator', paramBase: 'statistic.site_cnt' },
  { countKey: 'domain_count', operatorKey: 'domain_operator', paramBase: 'statistic.domain_cnt' },
  { countKey: 'ip_count', operatorKey: 'ip_operator', paramBase: 'statistic.ip_cnt' },
  { countKey: 'wih_count', operatorKey: 'wih_operator', paramBase: 'statistic.wih_cnt' },
  { countKey: 'vuln_count', operatorKey: 'vuln_operator', paramBase: 'statistic.vuln_cnt' },
  { countKey: 'nuclei_count', operatorKey: 'nuclei_operator', paramBase: 'statistic.nuclei_result_cnt' },
]);

const VALID_DIMENSION_SET = new Set(TASK_ASSET_YIELD_DIMENSION_KEYS);

export function normalizeAssetYieldDimensions(dimensions) {
  if (!Array.isArray(dimensions)) return [];
  const selected = new Set(
    dimensions
      .map((item) => String(item || '').trim().toLowerCase())
      .filter((item) => VALID_DIMENSION_SET.has(item))
  );
  return TASK_ASSET_YIELD_DIMENSION_KEYS.filter((key) => selected.has(key));
}

function hasInputValue(value) {
  return value !== '' && value !== null && value !== undefined && String(value).trim() !== '';
}

export function buildTaskQueryParams(searchForm = {}, { page = 1, size = 10 } = {}) {
  const queryParams = { page, size };

  if (searchForm.name) queryParams.name = searchForm.name;
  if (searchForm.target) queryParams.target = searchForm.target;
  if (searchForm.status) queryParams.status = searchForm.status;
  if (searchForm.task_id) queryParams._id = searchForm.task_id;
  if (searchForm.type) queryParams.task_tag = searchForm.type;
  if (searchForm.sync_status) queryParams.sync_status = searchForm.sync_status;

  const yieldMode = String(searchForm.asset_yield || '').trim().toLowerCase();
  const selectedDims = normalizeAssetYieldDimensions(searchForm.asset_types);

  if (yieldMode === 'no_asset') {
    queryParams.asset_yield = 'no_asset';
  } else if (selectedDims.length > 0) {
    queryParams.asset_types = selectedDims.join(',');
  } else if (yieldMode === 'has_asset') {
    queryParams.asset_yield = 'has_asset';
  }

  for (const spec of TASK_NUMERIC_FILTER_SPECS) {
    const rawCount = searchForm[spec.countKey];
    if (!hasInputValue(rawCount)) continue;
    const parsed = Number.parseInt(String(rawCount).trim(), 10);
    if (!Number.isInteger(parsed)) continue;
    const operator = searchForm[spec.operatorKey] || '=';
    if (operator === '=') queryParams[spec.paramBase] = parsed;
    else if (operator === '>') queryParams[`${spec.paramBase}__gt`] = parsed;
    else if (operator === '<') queryParams[`${spec.paramBase}__lt`] = parsed;
  }

  return queryParams;
}

export function countActiveAdvancedFilters(searchForm = {}) {
  let count = 0;
  if (searchForm.task_id) count++;
  if (searchForm.type) count++;
  if (searchForm.sync_status) count++;
  for (const spec of TASK_NUMERIC_FILTER_SPECS) {
    if (hasInputValue(searchForm[spec.countKey])) count++;
  }
  return count;
}

export function isAssetYieldFilterActive(searchForm = {}) {
  const yieldMode = String(searchForm.asset_yield || '').trim().toLowerCase();
  return yieldMode === 'has_asset' || yieldMode === 'no_asset' || normalizeAssetYieldDimensions(searchForm.asset_types).length > 0;
}

export function formatAssetYieldTriggerLabel(searchForm = {}, dimensionLabels = {}, texts = {}) {
  const yieldMode = String(searchForm.asset_yield || '').trim().toLowerCase();
  if (yieldMode === 'no_asset') {
    return texts.noAsset || 'No assets (finished)';
  }
  const selectedDims = normalizeAssetYieldDimensions(searchForm.asset_types);
  if (selectedDims.length > 0) {
    const labels = selectedDims.map((key) => dimensionLabels[key] || key);
    if (labels.length <= 2) {
      return typeof texts.selectedDims === 'function'
        ? texts.selectedDims(labels.join(' / '))
        : labels.join(' / ');
    }
    return typeof texts.selectedDimsMore === 'function'
      ? texts.selectedDimsMore(labels.slice(0, 2).join(' / '), labels.length - 2)
      : `${labels.slice(0, 2).join(' / ')} +${labels.length - 2}`;
  }
  if (yieldMode === 'has_asset') {
    return texts.hasAssetShort || 'With assets (core 6)';
  }
  return texts.allTrigger || 'Asset output: All';
}
