import assert from 'node:assert/strict';
import fs from 'node:fs';
import test, { afterEach } from 'node:test';
import vm from 'node:vm';
import { computed, nextTick, reactive, ref, watch } from 'vue';
import { parse, compileScript } from 'vue/compiler-sfc';
import { i18n, setLocale } from '../src/i18n/index.js';
import zh from '../src/i18n/zh-CN.js';
import en from '../src/i18n/en-US.js';
import ru from '../src/i18n/ru-RU.js';
import { formatTaskStatus, formatTaskStatusColor, isGithubStageStatus } from '../src/constants/taskStatus.js';
import {
  applyDorkPreset,
  buildGitCloneCmd,
  extractKeywordTerms,
  extractRepoSlugFromApiUrl,
  GITHUB_DORK_PRESETS,
  parseMultilineList,
  tokenizeCodeSnippet,
} from '../src/utils/githubHelpers.js';

const pageText = (...args) => i18n.global.t(...args);

afterEach(() => {
  setLocale('zh-CN');
});

function loadGithubManageContext(initial = {}) {
  const file = 'views/GithubManage.vue';
  const { descriptor } = parse(fs.readFileSync(new URL(`../src/${file}`, import.meta.url), 'utf8'));
  const { scriptSetupAst } = compileScript(descriptor, { id: file });
  let source = descriptor.scriptSetup.content;
  for (const node of [...scriptSetupAst].reverse()) {
    if (node.type === 'ImportDeclaration') {
      source = source.slice(0, node.start) + source.slice(node.end);
    }
  }
  const notices = [];
  const modalConfirmCalls = [];
  const context = vm.createContext({
    ref,
    reactive,
    computed,
    watch,
    nextTick,
    console,
    createVNode: (tag, props, children) => ({ tag, props, children }),
    defineOptions: () => {},
    useI18n: () => ({ t: pageText }),
    useRouter: () => ({ push() {} }),
    useRoute: () => ({ query: {} }),
    useGlobalPageSize: () => ref(10),
    onMounted: () => {},
    onActivated: () => {},
    onDeactivated: () => {},
    onUnmounted: () => {},
    TASK_STATUS_LABEL: { running: '进行中', waiting: '排队中', done: '已完成', stop: '已停止', error: '异常失败' },
    formatTaskStatus,
    formatTaskStatusColor,
    isGithubStageStatus,
    copyText: async () => {},
    GITHUB_BUILTIN_BUCKETS: [],
    GITHUB_DORK_PRESETS,
    GITHUB_CRON_PRESETS: [],
    REDTEAM_TOOL_PRESETS: [],
    applyDorkPreset,
    parseMultilineList,
    extractRepoSlugFromApiUrl,
    toGithubWebUrl: u => u,
    buildGitCloneCmd,
    ExclamationCircleOutlined: {},
    request: {
      get: async () => ({ code: 200, data: {}, items: [], total: 0 }),
      post: async () => ({ code: 200, data: {} }),
    },
    message: {
      success: msg => notices.push({ type: 'success', msg }),
      warning: msg => notices.push({ type: 'warning', msg }),
      error: msg => notices.push({ type: 'error', msg }),
    },
    Modal: {
      confirm: cfg => modalConfirmCalls.push(cfg),
    },
    ...initial,
  });

  const exposed = vm.runInContext(
    `${source}
    ;({
      mainTab, activeTabDlp, activeTabTi, applyRouteTabQuery,
      formatGithubStatusColor, updateTriageStatus, handleIgnoreRepos,
      handleSchedulerRunNow, toolForm, submitToolModal,
      hackerForm, submitHackerModal, confirmBatchItems,
      goToGithubTokenConfig, goToNucleiSearch,
      findingsData, schedulerData, taskData, findingsSelectedRowKeys
    });`,
    context
  );
  return { exposed, context, notices, modalConfirmCalls, descriptor };
}

test('githubHelpers 准确提取关键字并高亮敏感凭证与内网地址', () => {
  assert.deepEqual(extractKeywordTerms('org:acme "corp.example" password OR secret'), ['corp.example', 'password', 'secret']);

  const snippet = 'const url = "https://10.10.1.5:8080/api";\nconst password = "db_secret_value";\nconst site = "corp.example";';
  const lines = tokenizeCodeSnippet(snippet, '"corp.example"');
  assert.equal(lines.length, 3);
  assert.ok(lines[0].tokens.some(t => t.kind === 'network' && t.text.includes('10.10.1.5:8080')));
  assert.ok(lines[1].tokens.some(t => t.kind === 'secret' && t.text.includes('password')));
  assert.ok(lines[2].tokens.some(t => t.kind === 'keyword' && t.text === 'corp.example'));

  assert.equal(
    applyDorkPreset('acme.com', GITHUB_DORK_PRESETS[0]),
    '"acme.com" (password OR passwd OR secret OR token)'
  );
  assert.deepEqual(parseMultilineList('a/b\nhttps://github.com/c/d, a/b'), ['a/b', 'https://github.com/c/d']);
  assert.equal(extractRepoSlugFromApiUrl('https://api.github.com/repos/chaitin/xray'), 'chaitin/xray');
  assert.equal(buildGitCloneCmd('https://api.github.com/repos/chaitin/xray'), 'git clone https://github.com/chaitin/xray.git');
});

test('GitHub 扫描阶段状态遵循三语统一状态口径且保持 port_scan 原颜色契约', () => {
  assert.equal(isGithubStageStatus('search'), true);
  assert.equal(isGithubStageStatus('fetch content-32'), true);
  assert.equal(formatTaskStatus('search'), '进行中 · GitHub 检索');
  assert.equal(formatTaskStatus('fetch content-32'), '进行中 · 拉取匹配内容 (32)');

  setLocale('en-US');
  assert.equal(formatTaskStatus('search'), 'In progress · GitHub search');
  assert.equal(formatTaskStatus('fetch content-32'), 'In progress · Fetching content (32)');

  setLocale('ru-RU');
  assert.equal(formatTaskStatus('search'), 'Выполняется · Поиск GitHub');
  assert.equal(formatTaskStatus('fetch content-32'), 'Выполняется · Загрузка содержимого (32)');
  assert.equal(formatTaskStatusColor('port_scan'), 'default');
});

test('GithubManage 默认落在代码泄露总览并支持深链定位、阶段色标与新增动作', async () => {
  const postCalls = [];
  const pushCalls = [];
  const { exposed, modalConfirmCalls } = loadGithubManageContext({
    useRouter: () => ({ push: target => pushCalls.push(JSON.parse(JSON.stringify(target))) }),
    request: {
      get: async () => ({ code: 200, data: { items: [], total: 0 }, items: [], total: 0 }),
      post: async (url, payload) => {
        postCalls.push({ url, payload: JSON.parse(JSON.stringify(payload)) });
        return { code: 200, data: { msg: 'ok' } };
      },
    },
  });

  assert.equal(exposed.mainTab.value, 'dlp');
  assert.equal(exposed.activeTabDlp.value, 'findings');

  exposed.applyRouteTabQuery('cve_history');
  assert.equal(exposed.mainTab.value, 'ti');
  assert.equal(exposed.activeTabTi.value, 'cve_history');

  exposed.applyRouteTabQuery('scheduler');
  assert.equal(exposed.mainTab.value, 'dlp');
  assert.equal(exposed.activeTabDlp.value, 'scheduler');

  assert.equal(exposed.formatGithubStatusColor('search'), 'processing');
  assert.equal(exposed.formatGithubStatusColor('fetch content-12'), 'processing');
  assert.equal(exposed.formatGithubStatusColor('stop'), 'default');
  assert.equal(exposed.formatGithubStatusColor('error'), 'error');

  await exposed.updateTriageStatus(['h1', 'h1'], 'confirmed', 'verified');
  await exposed.handleIgnoreRepos('add', ['owner/noisy']);
  await exposed.handleSchedulerRunNow(['sched-1']);

  exposed.toolForm.repo_url = 'projectdiscovery/nuclei\nchaitin/xray';
  await exposed.submitToolModal();

  exposed.hackerForm.github_id = 'knownsec\nprojectdiscovery';
  await exposed.submitHackerModal();

  assert.deepEqual(
    postCalls.map(c => c.url),
    [
      '/github_result/triage/',
      '/github_result/ignored_repos/',
      '/github_scheduler/run/',
      '/github_threat/tools_target',
      '/github_threat/hackers_target',
    ]
  );
  assert.deepEqual(postCalls[0].payload, { hash_md5s: ['h1'], triage_status: 'confirmed', note: 'verified' });
  assert.deepEqual(postCalls[3].payload, { repo_urls: ['projectdiscovery/nuclei', 'chaitin/xray'] });
  assert.deepEqual(postCalls[4].payload, { github_ids: ['knownsec', 'projectdiscovery'] });

  exposed.confirmBatchItems({ actionLabel: '删除', items: ['repo-a', 'repo-b'], danger: true, onOk: () => {} });
  assert.equal(modalConfirmCalls.length, 1);
  assert.match(JSON.stringify(modalConfirmCalls[0].content), /repo-a/);
  assert.match(JSON.stringify(modalConfirmCalls[0].content), /repo-b/);

  exposed.goToGithubTokenConfig();
  exposed.goToNucleiSearch('CVE-2026-0001');
  assert.deepEqual(pushCalls, [
    { path: '/systemSettings', query: { tab: 'api_config', focus: 'github_token' } },
    { path: '/pocList', query: { tab: 'nuclei', search: 'CVE-2026-0001' } },
  ]);
});

test('GithubCodeReader 引用的所有 pages.* 键值在三语语言包中均存在且模板无裸中文', () => {
  const content = fs.readFileSync(new URL('../src/components/github/GithubCodeReader.vue', import.meta.url), 'utf8');
  const { descriptor } = parse(content);
  const templateStr = descriptor.template.content;
  assert.doesNotMatch(templateStr, /\p{Script=Han}/u);
  const matches = [...content.matchAll(/pageText\(['"]([^'"]+)['"]\)/g)].map(m => m[1]);
  for (const key of matches) {
    const segs = key.split('.');
    for (const bundle of [zh, en, ru]) {
      const val = segs.reduce((acc, k) => acc?.[k], bundle);
      assert.equal(typeof val, 'string', `Missing key ${key}`);
    }
  }
});
