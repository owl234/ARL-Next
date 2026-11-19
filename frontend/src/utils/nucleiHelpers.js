/**
 * Nuclei 自建模板与 ASM 扫描策略共用辅助函数（唯一事实源）。
 */

export const ASM_UNSUPPORTED_NUCLEI_PROTOCOLS = new Set([
  'code',
  'headless',
  'file',
  'workflows'
]);

export function isAsmSupportedProtocol(protocol) {
  const normalized = String(protocol || 'http').trim().toLowerCase();
  return !ASM_UNSUPPORTED_NUCLEI_PROTOCOLS.has(normalized);
}

export function isCustomNucleiResult(record) {
  if (!record || typeof record !== 'object') return false;
  return String(record.template_source || '').trim().toLowerCase() === 'custom';
}

export function isHttpUrl(value) {
  if (typeof value !== 'string') return false;
  return /^https?:\/\//i.test(value.trim());
}

export function buildNucleiConfigFromScope(scope) {
  if (scope === 'custom_only') {
    return {
      include_community: false,
      custom_template_mode: 'all_enabled',
      exclude_blacklist: true
    };
  }
  if (scope === 'community_only') {
    return {
      include_community: true,
      custom_template_mode: 'none',
      exclude_blacklist: true
    };
  }
  return {
    include_community: true,
    custom_template_mode: 'all_enabled',
    exclude_blacklist: true
  };
}

export function formatNucleiPolicySummary(siteConfig, t) {
  if (!siteConfig?.nuclei_scan) {
    return t('pages.disabled');
  }
  const cfg = siteConfig.nuclei_config || {};
  const includeCommunity = cfg.include_community !== false;
  const mode = cfg.custom_template_mode || 'all_enabled';
  const selectedCount = Array.isArray(cfg.selected_custom_templates) ? cfg.selected_custom_templates.length : 0;
  const tagCount = Array.isArray(cfg.selected_tags) ? cfg.selected_tags.length : 0;

  let detail = '';
  if (includeCommunity) {
    if (mode === 'none') {
      detail = t('pages.nucleiSummaryCommunityOnly');
    } else if (mode === 'selected') {
      detail = t('pages.nucleiSummaryCommunityPlusSelected', { count: selectedCount });
    } else if (mode === 'tags') {
      detail = t('pages.nucleiSummaryCommunityPlusTags', { count: tagCount });
    } else {
      detail = t('pages.nucleiSummaryCommunityPlusAllCustom');
    }
  } else {
    if (mode === 'selected') {
      detail = t('pages.nucleiSummaryCustomSelectedOnly', { count: selectedCount });
    } else if (mode === 'tags') {
      detail = t('pages.nucleiSummaryCustomTagsOnly', { count: tagCount });
    } else {
      detail = t('pages.nucleiSummaryCustomAllOnly');
    }
  }
  return `${t('pages.enabled')} (${detail})`;
}

export function formatRiskPolicyLabel(policy, t) {
  const pocCount = policy?.policy?.poc_config?.filter(p => p.enable)?.length || 0;
  const siteCfg = policy?.policy?.site_config;
  if (!siteCfg?.nuclei_scan) {
    return `${policy.name} (PoC : ${pocCount})`;
  }
  const cfg = siteCfg.nuclei_config || {};
  const includeCommunity = cfg.include_community !== false;
  const mode = cfg.custom_template_mode || 'all_enabled';
  let nucleiTag = '';
  if (!includeCommunity) {
    nucleiTag = t('tasks.nucleiScopeCustomOnly');
  } else if (mode === 'none') {
    nucleiTag = t('tasks.nucleiScopeCommunityOnly');
  } else {
    nucleiTag = t('tasks.nucleiScopeBoth');
  }
  return `${policy.name} (PoC : ${pocCount} · Nuclei : ${nucleiTag})`;
}
