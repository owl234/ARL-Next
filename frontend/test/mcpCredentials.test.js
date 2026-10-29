import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import os from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import { computed, reactive, ref } from 'vue';
import { parse, compileScript } from 'vue/compiler-sfc';
import { isCompleteMcpKey, resolveMcpCredential, createStdioServerConfig } from '../src/utils/mcpCredentials.js';

const key = `arl_mcp_${'a'.repeat(32)}`;
const { descriptor } = parse(fs.readFileSync(new URL('../src/views/McpCenter.vue', import.meta.url), 'utf8'));
const { scriptSetupAst } = compileScript(descriptor, { id: 'McpCenter' });
const bindings = {};
for (const node of scriptSetupAst) {
  if (node.type !== 'VariableDeclaration') continue;
  for (const item of node.declarations) {
    if (item.id.type === 'Identifier' && item.init) {
      bindings[item.id.name] = descriptor.scriptSetup.content.slice(item.init.start, item.init.end);
    }
  }
}

function setup() {
  const requests = [];
  const notices = [];
  const context = vm.createContext({
    computed, resolveMcpCredential, createStdioServerConfig,
    selectedKeyId: ref('fixture'), keySecrets: reactive({}), mcpMode: ref('sse'),
    activeKeyOptions: ref([{ id: 'fixture', key_prefix: key.slice(0, 12) + '...' }]),
    localStorage: { getItem: () => 'fixture-session', setItem: () => assert.fail('Do not persist keys') },
    window: { location: { protocol: 'https:', host: 'example.test' } },
    message: { warning: value => notices.push(value), error: () => {}, success: () => {} },
    pageText: value => value, copyText: async value => requests.push({ copied: value }),
    isDownloadingScript: ref(false),
    fetch: async (url, options) => { requests.push({ url, options }); return { ok: false }; },
    newKeyForm: reactive({ name: 'fixture' }), isCreatingKey: ref(false),
    createKeyModalVisible: ref(true), createdKeyPlaintext: ref(''), keySuccessModalVisible: ref(false),
    request: { post: async () => ({ data: { code: 200, data: { id: 'fixture', raw_key: key } } }) },
    fetchKeys: async () => {},
  });
  for (const name of ['currentTokenValue', 'configSnippet', 'handleCopySnippet', 'handleDownloadScript', 'handleCreateKeySubmit']) {
    vm.runInContext(`globalThis.${name} = ${bindings[name]}`, context);
  }
  return { context, requests, notices };
}

test('masked keys and absent plaintext never become authentication credentials', () => {
  assert.equal(isCompleteMcpKey(key), true);
  assert.equal(isCompleteMcpKey(key.slice(0, 12) + '...'), false);
  assert.equal(resolveMcpCredential('fixture', 'session', {}), '');
  assert.equal(resolveMcpCredential('fixture', 'session', { fixture: key }), key);
  assert.equal(resolveMcpCredential('current_session', 'session', {}), 'session');
});

test('newly created plaintext is used by the generated SSE configuration', async () => {
  const { context } = setup();
  await context.handleCreateKeySubmit();
  assert.equal(context.currentTokenValue.value, key);
  const config = JSON.parse(context.configSnippet.value);
  assert.equal(config.mcpServers['arl-next'].headers.Authorization, `Bearer ${key}`);
});

test('existing keys require plaintext before copy or download', async () => {
  const { context, requests, notices } = setup();
  await context.handleCopySnippet();
  await context.handleDownloadScript();
  assert.equal(requests.length, 0);
  assert.equal(notices.length, 2);
  context.keySecrets.fixture = key;
  await context.handleCopySnippet();
  assert.equal(JSON.parse(requests[0].copied).mcpServers['arl-next'].headers.Authorization, `Bearer ${key}`);
});

test('script export sends the full dedicated key in the POST body only', async () => {
  const { context, requests } = setup();
  context.keySecrets.fixture = key;
  await context.handleDownloadScript();
  const { url, options } = requests[0];
  assert.equal(url, '/api/mcp/export_server');
  assert.equal(options.method, 'POST');
  assert.equal(options.headers.Token, 'fixture-session');
  assert.equal(JSON.parse(options.body).raw_key, key);
  assert.equal(url.includes(key), false);
});

test('session script export preserves account credential behavior', async () => {
  const { context, requests } = setup();
  context.selectedKeyId.value = 'current_session';
  await context.handleDownloadScript();
  assert.equal(Object.hasOwn(JSON.parse(requests[0].options.body), 'raw_key'), false);
  assert.equal(requests[0].options.headers.Token, 'fixture-session');
});


test('Stdio starts without shell expansion, including a home path with spaces', () => {
  const directory = fs.mkdtempSync(path.join(os.homedir(), '.arl-stdio-test-'));
  try {
    const script = path.join(directory, 'fixture script.py');
    fs.writeFileSync(script, "print('stdio-fixture-ready')\n");
    const config = createStdioServerConfig(`~/${path.basename(directory)}/fixture script.py`);
    const result = spawnSync(config.command, config.args, { encoding: 'utf8', timeout: 5000 });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(result.stdout.trim(), 'stdio-fixture-ready');
  } finally {
    fs.rmSync(directory, { recursive: true });
  }
});
