import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import test from 'node:test';

import {
  isAsmSupportedProtocol,
  isCustomNucleiResult,
  isHttpUrl,
  buildNucleiConfigFromScope,
  formatNucleiPolicySummary,
  formatRiskPolicyLabel
} from '../src/utils/nucleiHelpers.js';

const FRONTEND_DIR = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');

test('nucleiHelpers: 协议支持判定、来源判定与 URL 安全判定', () => {
  assert.equal(isAsmSupportedProtocol('http'), true);
  assert.equal(isAsmSupportedProtocol('tcp'), true);
  assert.equal(isAsmSupportedProtocol('dns'), true);
  assert.equal(isAsmSupportedProtocol('ssl'), true);
  assert.equal(isAsmSupportedProtocol('headless'), false);
  assert.equal(isAsmSupportedProtocol('code'), false);
  assert.equal(isAsmSupportedProtocol('file'), false);
  assert.equal(isAsmSupportedProtocol('workflows'), false);

  assert.equal(isCustomNucleiResult({ template_source: 'custom' }), true);
  assert.equal(isCustomNucleiResult({ template_source: 'community' }), false);
  assert.equal(isCustomNucleiResult({}), false);

  assert.equal(isHttpUrl('https://example.com/admin'), true);
  assert.equal(isHttpUrl('http://127.0.0.1:8080'), true);
  assert.equal(isHttpUrl('127.0.0.1:6379'), false);
  assert.equal(isHttpUrl('sub.example.com'), false);
});

test('nucleiHelpers: 模板范围映射与策略摘要格式化', () => {
  assert.deepEqual(buildNucleiConfigFromScope('custom_only'), {
    include_community: false,
    custom_template_mode: 'all_enabled',
    exclude_blacklist: true
  });
  assert.deepEqual(buildNucleiConfigFromScope('community_only'), {
    include_community: true,
    custom_template_mode: 'none',
    exclude_blacklist: true
  });
  assert.deepEqual(buildNucleiConfigFromScope('both'), {
    include_community: true,
    custom_template_mode: 'all_enabled',
    exclude_blacklist: true
  });

  const t = (key, params = {}) => `${key}${params.count !== undefined ? ':' + params.count : ''}`;
  assert.equal(formatNucleiPolicySummary({ nuclei_scan: false }, t), 'pages.disabled');
  assert.equal(
    formatNucleiPolicySummary({
      nuclei_scan: true,
      nuclei_config: { include_community: false, custom_template_mode: 'selected', selected_custom_templates: ['a', 'b'] }
    }, t),
    'pages.enabled (pages.nucleiSummaryCustomSelectedOnly:2)'
  );
  assert.equal(
    formatRiskPolicyLabel({
      name: 'FastCustom',
      policy: {
        poc_config: [{ enable: true }],
        site_config: { nuclei_scan: true, nuclei_config: { include_community: false, custom_template_mode: 'all_enabled' } }
      }
    }, t),
    'FastCustom (PoC : 1 · Nuclei : tasks.nucleiScopeCustomOnly)'
  );
});

test('ASM 视图与策略页已接通自建模板配置、风险巡航回流与结果来源标记', () => {
  const policyDetail = fs.readFileSync(path.join(FRONTEND_DIR, 'src/views/PolicyDetail.vue'), 'utf8');
  assert.match(policyDetail, /include_community/);
  assert.match(policyDetail, /selected_custom_templates/);
  assert.match(policyDetail, /selected_tags/);

  const taskList = fs.readFileSync(path.join(FRONTEND_DIR, 'src/views/TaskList.vue'), 'utf8');
  assert.match(taskList, /nuclei_scope/);
  assert.match(taskList, /buildNucleiConfigFromScope/);

  const groupDetail = fs.readFileSync(path.join(FRONTEND_DIR, 'src/views/GroupAssetsDetail.vue'), 'utf8');
  assert.match(groupDetail, /related_scope_id:\s*scope_id\.value/);
  assert.match(groupDetail, /key:\s*'template_source'/);
  assert.match(groupDetail, /isCustomNucleiResult/);

  const taskDetail = fs.readFileSync(path.join(FRONTEND_DIR, 'src/views/TaskDetail.vue'), 'utf8');
  assert.match(taskDetail, /key:\s*'template_source'/);
  assert.match(taskDetail, /isCustomNucleiResult/);

  const assetSearch = fs.readFileSync(path.join(FRONTEND_DIR, 'src/views/AssetSearch.vue'), 'utf8');
  assert.match(assetSearch, /key:\s*'template_source'/);
  assert.match(assetSearch, /isCustomNucleiResult/);

  const chainDrawer = fs.readFileSync(path.join(FRONTEND_DIR, 'src/components/ChainDrawer.vue'), 'utf8');
  assert.match(chainDrawer, /isCustomNucleiResult/);
});
