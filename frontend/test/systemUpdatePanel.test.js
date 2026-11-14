import assert from 'node:assert/strict';
import fs from 'node:fs';
import test, { afterEach } from 'node:test';
import vm from 'node:vm';
import { computed, ref } from 'vue';
import { parse, compileScript } from 'vue/compiler-sfc';
import { i18n } from '../src/i18n/index.js';

const pageText = (...args) => i18n.global.t(...args);

afterEach(() => {
  i18n.global.locale.value = 'zh-CN';
});

function loadUpdatePanel(initial = {}) {
  const raw = fs.readFileSync(new URL('../src/components/settings/SystemUpdatePanel.vue', import.meta.url), 'utf8');
  const { descriptor } = parse(raw);
  const { scriptSetupAst } = compileScript(descriptor, { id: 'SystemUpdatePanel.vue' });
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
    pageText,
    pageLocale: i18n.global.locale,
    computed,
    ref,
    console,
    ...initial,
  });
  return {
    descriptor,
    context,
    read(name) {
      assert.ok(bindings[name], `missing binding: ${name}`);
      return vm.runInContext(`globalThis.${name} = (${bindings[name]})`, context);
    },
  };
}

test('SystemUpdatePanel: checkVersion 传递语言与强制刷新参数并丢弃过期竞态响应', async () => {
  i18n.global.locale.value = 'en-US';
  const calls = [];
  let resolveSlow;
  const slowPromise = new Promise((resolve) => { resolveSlow = resolve; });

  const page = loadUpdatePanel({
    localVersion: ref(''),
    remoteVersion: ref(''),
    releaseNotes: ref(''),
    releaseHtmlUrl: ref('https://github.com/owl234/ARL-Next/releases'),
    hasNewVersion: ref(false),
    isOffline: ref(false),
    checkingVersion: ref(false),
    checkVersionSeq: ref(0),
    request: {
      get(url, config) {
        calls.push({ url, params: { ...(config?.params || {}) } });
        if (calls.length === 1) return slowPromise;
        return Promise.resolve({
          code: 200,
          data: {
            local_version: 'v1.4.6',
            remote_version: 'v1.4.6',
            has_new_version: false,
            is_offline: true,
            release_notes: '### 🚀 New Features\n- Latest English notes',
            html_url: 'https://github.com/owl234/ARL-Next/releases/tag/v1.4.6',
          },
        });
      },
    },
  });

  const checkVersion = page.read('checkVersion');
  const firstReq = checkVersion(false);
  // 语言切换发起第二次非强制请求，序号应覆盖第一次慢请求
  i18n.global.locale.value = 'ru-RU';
  await checkVersion(false);

  resolveSlow({
    code: 200,
    data: {
      local_version: 'v1.4.5',
      remote_version: 'v1.4.6',
      has_new_version: true,
      is_offline: false,
      release_notes: 'stale notes should be ignored',
    },
  });
  await firstReq;

  assert.equal(calls[0].url, '/api/system_config/check_update');
  assert.deepEqual(calls[0].params, { lang: 'en-US' });
  assert.deepEqual(calls[1].params, { lang: 'ru-RU' });
  assert.equal(page.context.localVersion.value, 'v1.4.6');
  assert.equal(page.context.isOffline.value, true);
  assert.match(page.context.releaseNotes.value, /Latest English notes/);
  assert.doesNotMatch(page.context.releaseNotes.value, /stale notes/);

  await checkVersion(true);
  assert.deepEqual(calls[2].params, { lang: 'ru-RU', refresh: 1 });
});

test('SystemUpdatePanel: renderedReleaseNotes 支持分割线、链接、代码块并防御 XSS', () => {
  const releaseNotes = ref([
    '### 🚀 新增功能',
    '- **全链路画像**：支持 `https://example.com/in-code` 保留代码块',
    '- 英文日志：[CHANGELOG_en.md](./CHANGELOG_en.md)',
    '- 恶意链接：[bad](javascript:alert(1)) <script>alert(1)</script>',
    '',
    '---',
    '',
    '> 引用提示文本',
    '',
    '1. 有序条目',
    '',
    '**Full Changelog**: https://github.com/owl234/ARL-Next/compare/v1.4.5...v1.4.6',
  ].join('\n'));

  const page = loadUpdatePanel({ releaseNotes });
  const rendered = page.read('renderedReleaseNotes').value;

  assert.match(rendered, /<h4>🚀 新增功能<\/h4>/);
  assert.match(rendered, /<hr\/>/);
  assert.match(rendered, /<blockquote>引用提示文本<\/blockquote>/);
  assert.match(rendered, /<code>https:\/\/example\.com\/in-code<\/code>/);
  assert.doesNotMatch(rendered, /href="https:\/\/example\.com\/in-code"/);
  assert.match(rendered, /href="https:\/\/github\.com\/owl234\/ARL-Next\/blob\/main\/CHANGELOG_en\.md"/);
  assert.match(rendered, /href="https:\/\/github\.com\/owl234\/ARL-Next\/compare\/v1\.4\.5\.\.\.v1\.4\.6"/);
  assert.match(rendered, /<li class="md-ol">有序条目<\/li>/);
  assert.doesNotMatch(rendered, /<script>/);
  assert.doesNotMatch(rendered, /href="javascript:/);
});

test('SystemUpdatePanel: 模板始终展示更新日志行，无空框且含刷新与离线兜底', () => {
  const { descriptor } = loadUpdatePanel();
  const tpl = descriptor.template.content;

  assert.doesNotMatch(tpl, /v-if="hasNewVersion"\s+:label="pageText\('pages\.releaseNotes'\)"/);
  assert.match(tpl, /:label="pageText\('pages\.releaseNotes'\)"/);
  assert.doesNotMatch(tpl, /markdown-release-notes\s+hide-scrollbar/);
  assert.match(tpl, /v-else-if="renderedReleaseNotes"/);
  assert.match(tpl, /class="release-notes-empty"/);
  assert.match(tpl, /pages\.releaseNotesLoadFailedHint/);
  assert.match(tpl, /pages\.noLocalReleaseNotesFound/);
  assert.match(tpl, /pages\.unableToReachGithubCheckNetwork/);
  assert.match(tpl, /pages\.checkForUpdates/);
});
