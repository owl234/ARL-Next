import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
import { parse, compileScript } from 'vue/compiler-sfc';
import { ref, shallowRef, computed, reactive, watch, nextTick } from 'vue';

function loadPolicyDetailBindings() {
  const filePath = new URL('../src/views/PolicyDetail.vue', import.meta.url);
  const content = fs.readFileSync(filePath, 'utf8');
  const { descriptor } = parse(content);
  const { scriptSetupAst } = compileScript(descriptor, { id: 'PolicyDetail.vue' });
  const bindings = {};

  const watchers = [];
  for (const node of scriptSetupAst) {
    if (node.type === 'VariableDeclaration') {
      for (const item of node.declarations) {
        if (item.id.type === 'Identifier' && item.init) {
          bindings[item.id.name] = descriptor.scriptSetup.content.slice(item.init.start, item.init.end);
        }
      }
    } else if (node.type === 'FunctionDeclaration' && node.id) {
      bindings[node.id.name] = descriptor.scriptSetup.content.slice(node.start, node.end);
    } else if (node.type === 'ExpressionStatement' && node.expression?.type === 'CallExpression') {
      if (node.expression.callee?.name === 'watch') {
        watchers.push(descriptor.scriptSetup.content.slice(node.start, node.end));
      }
    }
  }

  const context = vm.createContext({
    pageText: (key, params) => `${key}${params ? JSON.stringify(params) : ''}`,
    computed,
    reactive,
    ref,
    shallowRef,
    watch,
    nextTick,
    console,
    performance,
    message: {
      success() {},
      error() {},
      warning() {},
      info() {},
    },
    route: { query: {} },
    router: { push() {} },
  });

  const read = (name) => {
    assert.ok(bindings[name], `Missing binding ${name}`);
    return vm.runInContext(`globalThis.${name} = (${bindings[name]})`, context);
  };

  const initWatchers = () => {
    watchers.forEach(code => vm.runInContext(code, context));
  };

  return { bindings, context, read, initWatchers };
}

test('PolicyDetail: 海量 PoC 分页、解耦 Set 与微秒级全选响应测试', () => {
  const { read, context, initWatchers } = loadPolicyDetailBindings();

  // 读取所有目标依赖
  read('pocList');
  read('bruteList');
  read('selectedPocNames');
  read('selectedBruteNames');
  read('pocSearch');
  read('bruteSearch');
  read('pocPagination');
  read('brutePagination');
  read('filteredPocList');
  read('filteredBruteList');
  read('paginatedPocList');
  read('paginatedBruteList');
  read('selectedPocCount');
  read('selectedBruteCount');
  read('pocSelectedFilteredCount');
  read('isAllPocSelected');
  read('isPocIndeterminate');
  read('bruteSelectedFilteredCount');
  read('isAllBruteSelected');
  read('isBruteIndeterminate');
  read('togglePocItem');
  read('toggleBruteItem');
  read('toggleAllPoc');
  read('toggleAllBrute');

  // 初始化响应式监听器（search 与 pageSize 同步联动）
  initWatchers();

  // 1. 模拟装配 10,000 个 PoC 数据
  const totalCount = 10000;
  const mockPocs = [];
  for (let i = 0; i < totalCount; i++) {
    mockPocs.push(Object.freeze({
      plugin_name: `poc_plugin_${i}`,
      vul_name: i === 42 ? 'Apache Struts2 S2-045 RCE' : `Vulnerability ${i}`
    }));
  }
  context.pocList.value = Object.freeze(mockPocs);

  // 初始状态验证
  assert.equal(context.pocList.value.length, totalCount);
  assert.equal(context.filteredPocList.value.length, totalCount);
  assert.equal(context.selectedPocCount.value, 0);
  assert.equal(context.isAllPocSelected.value, false);
  assert.equal(context.isPocIndeterminate.value, false);

  // 验证分页分片渲染：只展示第 1 页的 60 个节点，避免挂载上万 DOM 节点
  assert.equal(context.pocPagination.pageSize, 60);
  assert.equal(context.paginatedPocList.value.length, 60);
  assert.equal(context.paginatedPocList.value[0].plugin_name, 'poc_plugin_0');
  assert.equal(context.paginatedPocList.value[59].plugin_name, 'poc_plugin_59');

  // 切换第 2 页
  context.pocPagination.current = 2;
  assert.equal(context.paginatedPocList.value.length, 60);
  assert.equal(context.paginatedPocList.value[0].plugin_name, 'poc_plugin_60');
  context.pocPagination.current = 1;

  // 2. 单选触发与状态更新
  context.togglePocItem('poc_plugin_0', true);
  assert.equal(context.selectedPocCount.value, 1);
  assert.equal(context.selectedPocNames.value.has('poc_plugin_0'), true);
  assert.equal(context.isPocIndeterminate.value, true);
  assert.equal(context.isAllPocSelected.value, false);

  context.togglePocItem('poc_plugin_0', false);
  assert.equal(context.selectedPocCount.value, 0);
  assert.equal(context.isPocIndeterminate.value, false);

  // 3. 性能测试：海量 PoC (10,000项) 全选耗时断言（必须低于 25ms，杜绝页面假死）
  const t0 = performance.now();
  context.toggleAllPoc({ target: { checked: true } });
  const selectAllDuration = performance.now() - t0;

  assert.equal(context.selectedPocCount.value, totalCount);
  assert.equal(context.isAllPocSelected.value, true);
  assert.equal(context.isPocIndeterminate.value, false);
  assert.ok(selectAllDuration < 25, `全选 10,000 项耗时 ${selectAllDuration.toFixed(2)}ms，应低于 25ms`);

  // 反选全清耗时断言
  const t1 = performance.now();
  context.toggleAllPoc({ target: { checked: false } });
  const deselectAllDuration = performance.now() - t1;

  assert.equal(context.selectedPocCount.value, 0);
  assert.equal(context.isAllPocSelected.value, false);
  assert.equal(context.isPocIndeterminate.value, false);
  assert.ok(deselectAllDuration < 25, `反选 10,000 项耗时 ${deselectAllDuration.toFixed(2)}ms，应低于 25ms`);

  // 4. 搜索联动与局部全选
  context.pocSearch.value = 'Struts2';
  assert.equal(context.filteredPocList.value.length, 1);
  assert.equal(context.filteredPocList.value[0].vul_name, 'Apache Struts2 S2-045 RCE');
  assert.equal(context.paginatedPocList.value.length, 1);

  // 局部全选（仅勾选筛选结果）
  context.toggleAllPoc({ target: { checked: true } });
  assert.equal(context.selectedPocCount.value, 1);
  assert.equal(context.selectedPocNames.value.has('poc_plugin_42'), true);
  assert.equal(context.isAllPocSelected.value, true);

  // 清空搜索框后，10,000 个中仅有 1 个被勾选，处于半选状态
  context.pocSearch.value = '';
  assert.equal(context.filteredPocList.value.length, totalCount);
  assert.equal(context.selectedPocCount.value, 1);
  assert.equal(context.isPocIndeterminate.value, true);
  assert.equal(context.isAllPocSelected.value, false);

  // 5. 分页越界防呆与 pageSize 联动测试
  context.pocPagination.current = 999999;
  // 越界时，计算属性自动收敛至最后一页 (10000 条数据按 60 分页，最后一页为 40 条)，绝不返回空切片
  assert.equal(context.paginatedPocList.value.length, 40);
  assert.equal(context.paginatedPocList.value[39].plugin_name, 'poc_plugin_9999');

  // 修改 pageSize 自动归位回第 1 页
  context.pocPagination.pageSize = 100;
  assert.equal(context.pocPagination.current, 1);
  assert.equal(context.paginatedPocList.value.length, 100);

  // 6. 幽灵/废弃插件隔离测试：当已选集合中包含已被删除的插件时，不干扰真实计数与全选判断
  context.selectedPocNames.value.add('deleted_orphan_plugin_xyz');
  // 真实计数应仍然为 1，绝不虚标为 2
  assert.equal(context.selectedPocCount.value, 1);
  assert.equal(context.pocSelectedFilteredCount.value, 1);

  // 7. 直接传入 boolean 值切换全选的容错支持
  context.toggleAllPoc(false);
  assert.equal(context.selectedPocCount.value, 0);
  assert.equal(context.isAllPocSelected.value, false);
});
