import assert from 'node:assert/strict';
import fs from 'node:fs';
import test, { afterEach } from 'node:test';
import vm from 'node:vm';
import { computed, ref, watch } from 'vue';
import { parse, compileScript, babelParse } from 'vue/compiler-sfc';
import { i18n } from '../src/i18n/index.js';
import allZh from '../src/i18n/zh-CN.js';
import allEn from '../src/i18n/en-US.js';
import allRu from '../src/i18n/ru-RU.js';
import { formatTaskStatus } from '../src/constants/taskStatus.js';
import {
  ALL_EXCEL_SHEETS,
  DEFAULT_EXCEL_SHEETS,
  EXCEL_SHEET_OPTIONS,
  MAX_EXCEL_EXPORT_TASKS,
  MAX_EXCEL_ROWS_PER_SHEET,
  SHEET_I18N_KEY_MAP,
  buildExcelExportPayload,
  extractBlobErrorMessage,
  isActiveTaskStatus,
  parseExportResponseHeaders,
  parseFilenameFromContentDisposition,
} from '../src/utils/taskExcelExport.js';

const taskText = (...args) => i18n.global.t(...args);
const plain = (value) => JSON.parse(JSON.stringify(value));

afterEach(() => {
  i18n.global.locale.value = 'zh-CN';
});

test('taskExcelExport 工具函数：载荷构造、文件名解析、截断响应头与 Blob 错误提取', async () => {
  const payload = buildExcelExportPayload({
    taskIds: ['t2', 't1', 't2', '', null],
    sheets: ['url', 'site', 'overview', 'unknown'],
    deduplicate: false,
  });
  assert.deepEqual(payload, {
    task_id: ['t2', 't1'],
    sheets: ['overview', 'site', 'url'],
    deduplicate: false,
  });

  assert.equal(
    parseFilenameFromContentDisposition(
      "attachment; filename=\"ARL_Export.xlsx\"; filename*=UTF-8''ARL_%E6%89%B9%E9%87%8F%E8%B5%84%E4%BA%A7%E6%8A%A5%E5%91%8A.xlsx"
    ),
    'ARL_批量资产报告.xlsx'
  );
  assert.equal(
    parseFilenameFromContentDisposition('attachment; filename="plain_report.xlsx"'),
    'plain_report.xlsx'
  );
  assert.equal(
    parseFilenameFromContentDisposition('', 'fallback.xlsx'),
    'fallback.xlsx'
  );

  const meta = parseExportResponseHeaders({
    'X-Export-Truncated': '1',
    'X-Export-Truncated-Sheets': 'url, wih',
    'x-export-empty-sheets': 'cert',
    'x-export-included-sheets': 'overview,site,url,wih',
  });
  assert.deepEqual(meta, {
    truncated: true,
    truncatedSheets: ['url', 'wih'],
    emptySheets: ['cert'],
    includedSheets: ['overview', 'site', 'url', 'wih'],
  });

  const fakeError = {
    response: {
      data: {
        async text() {
          return JSON.stringify({ code: 400, message: '单次最多支持导出 100 个任务' });
        },
      },
    },
  };
  assert.equal(await extractBlobErrorMessage(fakeError, '默认报错'), '单次最多支持导出 100 个任务');
  assert.equal(await extractBlobErrorMessage(null, '默认报错'), '默认报错');

  assert.equal(isActiveTaskStatus('running'), true);
  assert.equal(isActiveTaskStatus('waiting'), true);
  assert.equal(isActiveTaskStatus('port_scan'), true);
  assert.equal(isActiveTaskStatus('done'), false);
  assert.equal(isActiveTaskStatus('stop'), false);
  assert.equal(isActiveTaskStatus('error'), false);
});

test('TaskList.vue 批量操作条与单行导出均接入 TaskExcelExportModal，且保留原有文本批量导出菜单', () => {
  const raw = fs.readFileSync(new URL('../src/views/TaskList.vue', import.meta.url), 'utf8');
  const taskBarMatch = raw.match(
    /<!-- 资产侦查批量操作 -->([\s\S]*?)<\/div>\s*<\/div>\s*<!-- 3\. 主数据表格容器 -->/
  );
  assert.ok(taskBarMatch, 'Should locate ASM task batch bar');
  const taskBar = taskBarMatch[1];
  assert.match(taskBar, /@click="openBatchExcelExportModal"/);
  assert.match(taskBar, /taskText\('tasks\.exportExcel'\)/);
  assert.match(taskBar, /@click="handleBatchExport"/);
  assert.match(raw, /<TaskExcelExportModal[\s\S]*?v-model:open="excelExportModalVisible"/);
});

test('TaskExcelExportModal.vue 所有翻译键与插值参数在中/英/俄三语完整一致', () => {
  const source = fs.readFileSync(new URL('../src/components/TaskExcelExportModal.vue', import.meta.url), 'utf8');
  const { descriptor } = parse(source);
  const check = (node) => {
    if (!node || typeof node !== 'object') return;
    if (node.type === 'CallExpression' && node.callee.name === 'taskText' && node.arguments[0]?.type === 'StringLiteral') {
      const key = node.arguments[0].value;
      const messages = [allZh, allEn, allRu].map((bundle) => key.split('.').reduce((acc, part) => acc?.[part], bundle));
      for (const msg of messages) {
        assert.equal(typeof msg, 'string', `Missing i18n key: ${key}`);
      }
      const expected = [...new Set([...messages[1].matchAll(/\{(\w+)\}/g)].map(([, name]) => name))].sort();
      const actual = (node.arguments[1]?.properties || []).map((prop) => prop.key.name).sort();
      assert.deepEqual(actual, expected, `Param mismatch for key: ${key}`);
    }
    for (const [k, v] of Object.entries(node)) {
      if (['loc', 'comments', 'leadingComments', 'trailingComments'].includes(k)) continue;
      if (Array.isArray(v)) v.forEach(check);
      else if (v && typeof v === 'object') check(v);
    }
  };
  check(babelParse(descriptor.scriptSetup.content, { sourceType: 'module' }));
  const walkTemplate = (node) => {
    if (node.type === 4 && !node.isStatic) {
      if (node.content.includes('taskText(')) check(babelParse(`(${node.content})`, { sourceType: 'module' }));
      return;
    }
    for (const child of [...(node.children || []), ...(node.props || [])]) walkTemplate(child);
    if (node.exp) walkTemplate(node.exp);
    if (node.type === 5) walkTemplate(node.content);
  };
  walkTemplate(descriptor.template.ast);

  // 同时核验所有维度映射键存在于三语中
  for (const i18nKey of Object.values(SHEET_I18N_KEY_MAP)) {
    for (const bundle of [allZh, allEn, allRu]) {
      const val = i18nKey.split('.').reduce((acc, part) => acc?.[part], bundle);
      assert.equal(typeof val, 'string', `Missing sheet key ${i18nKey}`);
    }
  }
});

test('TaskExcelExportModal 交互流：正常导出、截断告警与后端 JSON 报错解析', async () => {
  const source = fs.readFileSync(new URL('../src/components/TaskExcelExportModal.vue', import.meta.url), 'utf8');
  const { descriptor } = parse(source);
  const { scriptSetupAst } = compileScript(descriptor, { id: 'TaskExcelExportModal.vue' });
  let body = descriptor.scriptSetup.content;
  for (const node of [...scriptSetupAst].reverse()) {
    if (node.type === 'ImportDeclaration') {
      body = body.slice(0, node.start) + body.slice(node.end);
    }
  }

  const emitted = [];
  const downloads = [];
  const msgCalls = { loading: [], success: [], warning: [], error: [] };
  const posts = [];
  let postBehavior = async (url, payload, config) => {
    posts.push({ url, payload, config });
    return {
      data: new Blob(['fake-xlsx'], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' }),
      headers: {
        'content-type': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        'content-disposition': "attachment; filename=\"ARL_Export.xlsx\"; filename*=UTF-8''ARL_%E6%89%B9%E9%87%8F.xlsx",
        'x-export-truncated': '1',
        'x-export-truncated-sheets': 'url,wih',
      },
    };
  };

  const props = {
    open: true,
    tasks: [
      { id: '650000000000000000000001', label: '任务A (a.example)', status: 'done' },
      { id: '650000000000000000000002', label: '任务B (b.example)', status: 'port_scan' },
    ],
    crossPageCount: 1,
  };

  const ctx = vm.createContext({
    ref, computed, watch, Blob,
    defineProps: () => props,
    defineEmits: () => (event, val) => emitted.push({ event, val }),
    useI18n: () => ({ t: taskText }),
    formatTaskStatus,
    ALL_EXCEL_SHEETS,
    DEFAULT_EXCEL_SHEETS,
    EXCEL_SHEET_OPTIONS,
    MAX_EXCEL_EXPORT_TASKS,
    MAX_EXCEL_ROWS_PER_SHEET,
    SHEET_I18N_KEY_MAP,
    buildExcelExportPayload,
    extractBlobErrorMessage,
    isActiveTaskStatus,
    parseExportResponseHeaders,
    parseFilenameFromContentDisposition,
    request: { post: (...args) => postBehavior(...args) },
    message: {
      loading: (arg) => msgCalls.loading.push(arg),
      success: (arg) => msgCalls.success.push(arg),
      warning: (arg) => msgCalls.warning.push(arg),
      error: (arg) => msgCalls.error.push(arg),
    },
    window: {
      URL: {
        createObjectURL: () => 'blob:mock-url',
        revokeObjectURL: () => {},
      },
    },
    document: {
      createElement: () => ({
        href: '',
        download: '',
        click() {
          downloads.push({ href: this.href, download: this.download });
        },
      }),
      body: {
        appendChild() {},
        removeChild() {},
      },
    },
  });

  const api = vm.runInContext(
    `${body}\n;({ selectedSheets, deduplicate, activeTaskCount, handleConfirmExport, selectAllSheets, clearSheets, resetDefaultSheets });`,
    ctx
  );

  assert.equal(api.activeTaskCount.value, 1);
  assert.deepEqual(plain(api.selectedSheets.value), DEFAULT_EXCEL_SHEETS);
  assert.equal(api.deduplicate.value, true);

  await api.handleConfirmExport();
  assert.equal(posts.length, 1);
  assert.equal(posts[0].url, '/export/batch/');
  assert.equal(posts[0].config.returnFullResponse, true);
  assert.equal(posts[0].config.responseType, 'blob');
  assert.deepEqual(plain(posts[0].payload), {
    task_id: ['650000000000000000000001', '650000000000000000000002'],
    sheets: DEFAULT_EXCEL_SHEETS,
    deduplicate: true,
  });
  assert.deepEqual(downloads, [{ href: 'blob:mock-url', download: 'ARL_批量.xlsx' }]);
  assert.equal(msgCalls.warning.length, 1);
  assert.match(msgCalls.warning[0].content, /50000/);
  assert.match(msgCalls.warning[0].content, /URL/);
  assert.match(msgCalls.warning[0].content, /WIH/);
  assert.ok(emitted.some((e) => e.event === 'update:open' && e.val === false));

  // 模拟后端返回 400 JSON Blob
  postBehavior = async () => {
    const err = new Error('Bad Request');
    err.response = {
      data: {
        async text() {
          return JSON.stringify({ code: 400, message: '包含无效的任务 ID' });
        },
      },
    };
    throw err;
  };
  await api.handleConfirmExport();
  assert.equal(msgCalls.error.length, 1);
  assert.match(msgCalls.error[0].content, /包含无效的任务 ID/);
});
