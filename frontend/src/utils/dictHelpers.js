export const BUILTIN_PORT_DICT_ORDER = [
  'port_top100.txt',
  'port_top1000.txt',
  'port_custom.txt',
  'port_all.txt',
];

const STATIC_BUILTIN_PORT_DICTS = new Set([
  'port_top100.txt',
  'port_top1000.txt',
  'port_all.txt',
  'port_alive.txt',
]);

export function isDomainDict(item) {
  const name = String(item?.name || '');
  return name.startsWith('domain_');
}

export function isAltDnsDict(item) {
  const name = String(item?.name || '');
  return name === 'altdnsdict.txt' || name.startsWith('altdns_');
}

export function isFileLeakDict(item) {
  const name = String(item?.name || '');
  return name.startsWith('file_');
}

export function isPortScanDict(item) {
  const name = String(item?.name || '');
  return name.startsWith('port_') && name !== 'port_alive.txt';
}

export function sortPortScanDicts(list) {
  return [...list].sort((a, b) => {
    const idxA = BUILTIN_PORT_DICT_ORDER.indexOf(a?.name);
    const idxB = BUILTIN_PORT_DICT_ORDER.indexOf(b?.name);
    if (idxA !== -1 && idxB !== -1) return idxA - idxB;
    if (idxA !== -1) return -1;
    if (idxB !== -1) return 1;
    return String(a?.name || '').localeCompare(String(b?.name || ''));
  });
}

export function classifyAssetDictionaries(list) {
  const items = Array.isArray(list) ? list : [];
  return {
    domainDicts: items.filter(isDomainDict),
    altDnsDicts: items.filter(isAltDnsDict),
    fileLeakDicts: items.filter(isFileLeakDict),
    portDicts: sortPortScanDicts(items.filter(isPortScanDict)),
  };
}

export function normalizeDomainDict(val) {
  if (!val) return val;
  const key = String(val).trim();
  const map = {
    big: 'domain_2w.txt',
    test: 'domain_top300.txt',
    domain_2w: 'domain_2w.txt',
    domain_top300: 'domain_top300.txt',
  };
  return map[key] || key;
}

export function normalizePortDict(val) {
  if (!val) return val;
  const key = String(val).trim();
  const map = {
    test: 'port_top100.txt',
    top100: 'port_top100.txt',
    port_top100: 'port_top100.txt',
    top1000: 'port_top1000.txt',
    port_top1000: 'port_top1000.txt',
    all: 'port_all.txt',
    port_all: 'port_all.txt',
    custom: 'port_custom.txt',
    port_custom: 'port_custom.txt',
    bughunter: 'port_bughunter.txt',
    port_bughunter: 'port_bughunter.txt',
  };
  return map[key] || key;
}

export function formatDictSize(bytes) {
  if (!Number.isFinite(bytes) || bytes <= 0) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

export function describeDictOption(item, t) {
  if (!item) return '';
  const labelMap = {
    'domain_2w.txt': 'tasks.largeWordlistAbout20000Entries',
    'domain_top300.txt': 'tasks.smallWordlistAbout300Entries',
    'altdnsdict.txt': 'tasks.generatedWordlist',
    'port_top100.txt': 'tasks.top100Ports',
    'port_top1000.txt': 'tasks.top1000Ports',
    'port_all.txt': 'tasks.allPorts165535',
    'port_custom.txt': 'tasks.customPorts',
    'file_top_200.txt': 'tasks.smallWordlistAbout200Entries',
    'file_top_2000.txt': 'tasks.largeWordlistAbout2000Entries',
  };
  const key = labelMap[item.name];
  if (key && typeof t === 'function') return t(key);
  const size = formatDictSize(item.size);
  return size ? `${item.name} (${size})` : item.name;
}

export function formatPortPolicyLabel(portScanType, portCustom, t) {
  const rawType = String(portScanType || '').trim();
  if (!rawType) return '-';

  const inlinePorts = String(portCustom || '').trim();
  if (rawType === 'custom' && inlinePorts) {
    return typeof t === 'function'
      ? t('pages.customPortsPorts', { ports: inlinePorts })
      : `${rawType} (${inlinePorts})`;
  }

  const normalized = normalizePortDict(rawType);
  const labelKeyMap = {
    'port_top100.txt': 'tasks.top100Ports',
    'port_top1000.txt': 'tasks.top1000Ports',
    'port_all.txt': 'tasks.allPorts165535',
    'port_custom.txt': 'tasks.customPorts',
    'port_bughunter.txt': 'pages.bughunterPorts',
  };
  const labelKey = labelKeyMap[normalized];
  if (labelKey && typeof t === 'function') {
    return t(labelKey);
  }
  return rawType;
}

export function shouldPreviewPortDict(dictName) {
  const name = String(dictName || '').trim();
  return name.startsWith('port_') && !STATIC_BUILTIN_PORT_DICTS.has(name);
}

export function hasLegacyInlineCustomPorts(ipConfig) {
  return String(ipConfig?.port_scan_type || '').trim() === 'custom'
    && String(ipConfig?.port_custom || '').trim().length > 0;
}
