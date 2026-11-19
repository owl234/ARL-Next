import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

import { i18n } from '../src/i18n/index.js';
import { PLUGIN_NAME_MAP, formatTaskStatus } from '../src/constants/taskStatus.js';
import tasksZh from '../src/i18n/tasks.zh-CN.js';
import tasksEn from '../src/i18n/tasks.en-US.js';
import tasksRu from '../src/i18n/tasks.ru-RU.js';
import pagesZh from '../src/i18n/pages.zh-CN.js';
import pagesEn from '../src/i18n/pages.en-US.js';
import pagesRu from '../src/i18n/pages.ru-RU.js';

const FRONTEND_DIR = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');

test('taskStatus: site_capture 与 fetch_site 在三语下均有本地化阶段名', () => {
  const originalLocale = i18n.global.locale.value;
  try {
    i18n.global.locale.value = 'zh-CN';
    assert.equal(PLUGIN_NAME_MAP.site_capture, '站点截图');
    assert.equal(PLUGIN_NAME_MAP.fetch_site, '站点获取');
    assert.equal(formatTaskStatus('site_capture'), '进行中 · 站点截图');
    assert.equal(formatTaskStatus('fetch_site'), '进行中 · 站点获取');

    i18n.global.locale.value = 'en-US';
    assert.equal(PLUGIN_NAME_MAP.site_capture, 'Website screenshot');
    assert.equal(PLUGIN_NAME_MAP.fetch_site, 'Website fetch');
    assert.equal(formatTaskStatus('site_capture'), 'In progress · Website screenshot');

    i18n.global.locale.value = 'ru-RU';
    assert.equal(PLUGIN_NAME_MAP.site_capture, 'Снимок экрана сайта');
    assert.equal(PLUGIN_NAME_MAP.fetch_site, 'Получение сайтов');
    assert.equal(formatTaskStatus('site_capture'), 'Выполняется · Снимок экрана сайта');
  } finally {
    i18n.global.locale.value = originalLocale;
  }
});

test('i18n: 新增截图开关与阶段文案在三语语言包中完整对齐', () => {
  for (const key of ['websiteScreenshot', 'stageFetchSite', 'stageSiteCapture']) {
    assert.ok(tasksZh[key], `tasks.zh-CN missing ${key}`);
    assert.ok(tasksEn[key], `tasks.en-US missing ${key}`);
    assert.ok(tasksRu[key], `tasks.ru-RU missing ${key}`);
  }
  const pageKey = 'captureRenderedPageScreenshotsUsingHeadlessBrowser';
  assert.ok(pagesZh[pageKey], `pages.zh-CN missing ${pageKey}`);
  assert.ok(pagesEn[pageKey], `pages.en-US missing ${pageKey}`);
  assert.ok(pagesRu[pageKey], `pages.ru-RU missing ${pageKey}`);

  // 快捷预设 Tooltip 在三语下均明确说明站点截图的开关差异
  assert.match(tasksZh.enableDomainLookupSubdomainEnumerationPortScanningCdn, /关闭站点截图/);
  assert.match(tasksZh.addServiceDetectionSslCertificatesAndFileDisclosure, /站点截图/);
  assert.match(tasksEn.enableDomainLookupSubdomainEnumerationPortScanningCdn, /website screenshots disabled/i);
  assert.match(tasksEn.addServiceDetectionSslCertificatesAndFileDisclosure, /website screenshots/i);
  assert.match(tasksRu.enableDomainLookupSubdomainEnumerationPortScanningCdn, /снимки экранов сайтов.*отключены/i);
  assert.match(tasksRu.addServiceDetectionSslCertificatesAndFileDisclosure, /снимки экранов сайтов/i);
});

test('TaskList / PolicyDetail / Policy 正确显化 site_capture 开关与默认预设', () => {
  const taskList = fs.readFileSync(path.join(FRONTEND_DIR, 'src/views/TaskList.vue'), 'utf8');
  assert.match(taskList, /key:\s*'site_capture',\s*get label\(\)\s*\{\s*return taskText\('tasks\.websiteScreenshot'\);\s*\}/);
  assert.match(taskList, /site_capture:\s*true/);
  assert.match(taskList, /if \(type === 'fast'\)[\s\S]*?formState\.site_capture = false;/);

  const policyDetail = fs.readFileSync(path.join(FRONTEND_DIR, 'src/views/PolicyDetail.vue'), 'utf8');
  assert.match(policyDetail, /v-model:checked="policyForm\.site_config\.site_capture"/);
  assert.match(policyDetail, /site_config:\s*\{[\s\S]*?site_capture:\s*true/);
  assert.match(policyDetail, /sc\.site_identify && sc\.site_capture/);
  assert.match(policyDetail, /policyForm\.site_config\.site_capture = data\.policy\?\.site_config\?\.site_capture !== false;/);

  const policyList = fs.readFileSync(path.join(FRONTEND_DIR, 'src/views/Policy.vue'), 'utf8');
  assert.match(policyList, /if \(p\.site_config\?\.site_capture !== false\) l\.push\(pageText\('tasks\.websiteScreenshot'\)\);/);
});
