import assert from 'node:assert/strict';
import fs from 'node:fs';
import test, { afterEach } from 'node:test';
import * as Vue from 'vue';
import { createSSRApp, h } from 'vue';
import { renderToString } from 'vue/server-renderer';
import { parse, compileTemplate } from 'vue/compiler-sfc';
import { i18n } from '../src/i18n/index.js';

const taskListSource = fs.readFileSync(new URL('../src/views/TaskList.vue', import.meta.url), 'utf8');
const { descriptor } = parse(taskListSource);

afterEach(() => {
  i18n.global.locale.value = 'zh-CN';
});

function extractTaskStatisticBlock() {
  const templateContent = descriptor.template.content;
  const taskTabStart = templateContent.indexOf(':dataSource="taskList"');
  assert.notEqual(taskTabStart, -1, '未找到 taskList 表格区块');

  const statMarker = '<template v-else-if="column.key === \'statistic\'">';
  const statStart = templateContent.indexOf(statMarker, taskTabStart);
  assert.notEqual(statStart, -1, '未找到 task 页签的 statistic 列模板');

  const innerStart = statStart + statMarker.length;
  const optionsMarker = '<template v-else-if="column.key === \'options\'">';
  const optionsStart = templateContent.indexOf(optionsMarker, innerStart);
  assert.notEqual(optionsStart, -1, '未找到紧随 statistic 列后的 options 模板');

  const innerEnd = templateContent.lastIndexOf('</template>', optionsStart);
  assert.ok(innerEnd > innerStart, 'statistic 列结束标签位置异常');
  return templateContent.slice(innerStart, innerEnd).trim();
}

function compileStatisticRenderer() {
  const block = extractTaskStatisticBlock();
  const compiled = compileTemplate({
    source: `<div>${block}</div>`,
    filename: 'TaskList.vue',
    id: 'task-list-statistic-test',
    compilerOptions: {
      mode: 'function',
    },
  });
  assert.deepEqual(compiled.errors, [], `模板编译失败: ${compiled.errors.join('; ')}`);
  const factory = new Function('Vue', `${compiled.code}\nreturn render;`);
  return factory(Vue);
}

const renderStatistic = compileStatisticRenderer();

async function renderCell(record) {
  const app = createSSRApp({
    render() {
      return renderStatistic({
        record,
        taskText: (...args) => i18n.global.t(...args),
      }, {});
    },
  });
  app.component('ATooltip', {
    props: { title: String },
    render() {
      return h('span', { class: 'tooltip-stub', 'data-title': this.title }, this.$slots.default?.());
    },
  });
  return renderToString(app);
}

test('TaskList 资产统计列：仅命中 Nuclei 时展示火山橙 Nuclei 胶囊与多语言 Tooltip', async () => {
  const record = {
    statistic: {
      site_cnt: 3,
      domain_cnt: 2,
      ip_cnt: 1,
      wih_cnt: 0,
      vuln_cnt: 0,
      nuclei_result_cnt: 4,
    },
  };

  for (const [locale, expectedTooltip] of [
    ['zh-CN', 'Nuclei 漏洞: 4'],
    ['en-US', 'Nuclei vulnerabilities: 4'],
    ['ru-RU', 'Уязвимостей Nuclei: 4'],
  ]) {
    i18n.global.locale.value = locale;
    const html = await renderCell(record);
    assert.match(html, /class="stat-capsule nuclei"/);
    assert.match(html, /<span class="stat-lbl">Nuclei<\/span><span class="stat-num">4<\/span>/);
    assert.ok(html.includes(`data-title="${expectedTooltip}"`), `${locale}: missing tooltip ${expectedTooltip}`);
    assert.doesNotMatch(html, /class="stat-capsule vuln"/);
    assert.doesNotMatch(html, /class="stat-capsule wih"/);
  }
});

test('TaskList 资产统计列：同时存在内置风险与 Nuclei 检出时独立并列展示', async () => {
  const html = await renderCell({
    statistic: {
      site_cnt: 10,
      domain_cnt: 5,
      ip_cnt: 4,
      wih_cnt: 2,
      vuln_cnt: 3,
      nuclei_result_cnt: 7,
    },
  });

  assert.match(html, /class="stat-capsule vuln"><span class="stat-lbl">风险<\/span><span class="stat-num">3<\/span>/);
  assert.match(html, /class="stat-capsule nuclei"><span class="stat-lbl">Nuclei<\/span><span class="stat-num">7<\/span>/);
  assert.ok(html.indexOf('class="stat-capsule vuln"') < html.indexOf('class="stat-capsule nuclei"'));
});

test('TaskList 资产统计列：nuclei_result_cnt 为 0 或缺失时隐藏 Nuclei 胶囊，无 statistic 时回退占位符', async () => {
  for (const statistic of [
    { site_cnt: 1, domain_cnt: 1, ip_cnt: 1, nuclei_result_cnt: 0 },
    { site_cnt: 1, domain_cnt: 1, ip_cnt: 1 },
  ]) {
    const html = await renderCell({ statistic });
    assert.doesNotMatch(html, /class="stat-capsule nuclei"/);
  }

  const emptyHtml = await renderCell({});
  assert.doesNotMatch(emptyHtml, /task-stats-capsules/);
  assert.match(emptyHtml, />-<\/span>/);
});

test('TaskList 样式表包含 Nuclei 胶囊火山橙配色定义', () => {
  const styles = descriptor.styles.map((s) => s.content).join('\n');
  assert.match(styles, /\.stat-capsule\.nuclei\s*\{[^}]*background:\s*rgba\(250,\s*84,\s*28,\s*0\.14\);[^}]*color:\s*#d4380d;/);
});
