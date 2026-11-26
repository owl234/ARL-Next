/**
 * 资产侦查任务 Excel 导出配置、请求构造与响应解析纯工具函数。
 */

export const MAX_EXCEL_EXPORT_TASKS = 100;
export const MAX_EXCEL_ROWS_PER_SHEET = 50000;

export const EXCEL_SHEET_OPTIONS = [
  { key: 'overview', i18nKey: 'tasks.excelSheetOverview', group: 'default', defaultSelected: true },
  { key: 'site', i18nKey: 'tasks.excelSheetSite', group: 'default', defaultSelected: true },
  { key: 'domain', i18nKey: 'tasks.excelSheetDomain', group: 'default', defaultSelected: true },
  { key: 'ip', i18nKey: 'tasks.excelSheetIp', group: 'default', defaultSelected: true },
  { key: 'service', i18nKey: 'tasks.excelSheetService', group: 'default', defaultSelected: true },
  { key: 'vuln', i18nKey: 'tasks.excelSheetVuln', group: 'default', defaultSelected: true },
  { key: 'nuclei_result', i18nKey: 'tasks.excelSheetNuclei', group: 'default', defaultSelected: true },
  { key: 'statist', i18nKey: 'tasks.excelSheetStatist', group: 'default', defaultSelected: true },
  { key: 'wih', i18nKey: 'tasks.excelSheetWih', group: 'extended', defaultSelected: false },
  { key: 'fileleak', i18nKey: 'tasks.excelSheetFileleak', group: 'extended', defaultSelected: false },
  { key: 'cert', i18nKey: 'tasks.excelSheetCert', group: 'extended', defaultSelected: false },
  { key: 'url', i18nKey: 'tasks.excelSheetUrl', group: 'extended', defaultSelected: false },
  { key: 'cip', i18nKey: 'tasks.excelSheetCip', group: 'extended', defaultSelected: false },
];

export const DEFAULT_EXCEL_SHEETS = EXCEL_SHEET_OPTIONS
  .filter((item) => item.defaultSelected)
  .map((item) => item.key);

export const ALL_EXCEL_SHEETS = EXCEL_SHEET_OPTIONS.map((item) => item.key);

export const SHEET_I18N_KEY_MAP = Object.fromEntries(
  EXCEL_SHEET_OPTIONS.map((item) => [item.key, item.i18nKey])
);

const TERMINAL_TASK_STATUSES = new Set(['done', 'stop', 'error']);

export function isActiveTaskStatus(status) {
  if (!status) return false;
  return !TERMINAL_TASK_STATUSES.has(String(status).trim());
}

export function buildExcelExportPayload({ taskIds, sheets, deduplicate = true }) {
  const uniqueTaskIds = [];
  const seenIds = new Set();
  for (const rawId of Array.isArray(taskIds) ? taskIds : []) {
    const id = rawId == null ? '' : String(rawId).trim();
    if (id && !seenIds.has(id)) {
      seenIds.add(id);
      uniqueTaskIds.push(id);
    }
  }

  const sheetSet = new Set(Array.isArray(sheets) ? sheets.map((s) => String(s).trim()) : []);
  const orderedSheets = ALL_EXCEL_SHEETS.filter((key) => sheetSet.has(key));

  return {
    task_id: uniqueTaskIds,
    sheets: orderedSheets,
    deduplicate: Boolean(deduplicate),
  };
}

function getHeaderCaseInsensitive(headers, targetName) {
  if (!headers || typeof headers !== 'object') return '';
  if (typeof headers.get === 'function') {
    const val = headers.get(targetName);
    if (val != null) return String(val);
  }
  const lowerTarget = targetName.toLowerCase();
  for (const [k, v] of Object.entries(headers)) {
    if (String(k).toLowerCase() === lowerTarget && v != null) {
      return String(v);
    }
  }
  return '';
}

export function parseFilenameFromContentDisposition(headerValue, fallbackName = 'ARL_Export.xlsx') {
  const raw = String(headerValue || '').trim();
  if (!raw) return fallbackName;

  const utf8Match = raw.match(/filename\*\s*=\s*UTF-8''([^;]+)/i);
  if (utf8Match && utf8Match[1]) {
    try {
      const decoded = decodeURIComponent(utf8Match[1].trim().replace(/^"|"$/g, ''));
      if (decoded) return decoded;
    } catch {
      // 回退至普通 filename
    }
  }

  const plainMatch = raw.match(/filename\s*=\s*"([^"]+)"|filename\s*=\s*([^;]+)/i);
  const candidate = (plainMatch && (plainMatch[1] || plainMatch[2])) ? String(plainMatch[1] || plainMatch[2]).trim() : '';
  if (candidate) {
    try {
      return decodeURIComponent(candidate);
    } catch {
      return candidate;
    }
  }
  return fallbackName;
}

function splitCsvHeader(value) {
  return String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

export function parseExportResponseHeaders(headers) {
  const truncatedFlag = getHeaderCaseInsensitive(headers, 'x-export-truncated').trim();
  const truncatedSheets = splitCsvHeader(getHeaderCaseInsensitive(headers, 'x-export-truncated-sheets'));
  const emptySheets = splitCsvHeader(getHeaderCaseInsensitive(headers, 'x-export-empty-sheets'));
  const includedSheets = splitCsvHeader(getHeaderCaseInsensitive(headers, 'x-export-included-sheets'));
  return {
    truncated: truncatedFlag === '1' || truncatedSheets.length > 0,
    truncatedSheets,
    emptySheets,
    includedSheets,
  };
}

export async function extractBlobErrorMessage(source, fallbackMsg = '') {
  const rawBlob = source?.response?.data ?? source;
  if (!rawBlob) return fallbackMsg;

  if (typeof rawBlob === 'object' && typeof rawBlob.text === 'function') {
    try {
      const text = await rawBlob.text();
      if (text) {
        const parsed = JSON.parse(text);
        return parsed?.data?.error || parsed?.message || fallbackMsg;
      }
    } catch {
      return fallbackMsg;
    }
  }

  if (typeof rawBlob === 'string') {
    try {
      const parsed = JSON.parse(rawBlob);
      return parsed?.data?.error || parsed?.message || fallbackMsg;
    } catch {
      return rawBlob || fallbackMsg;
    }
  }

  if (typeof rawBlob === 'object') {
    return rawBlob?.data?.error || rawBlob?.message || fallbackMsg;
  }

  return fallbackMsg;
}
