import { ref, reactive, defineComponent, h } from 'vue';
import { Alert } from 'ant-design-vue';
import dayjs from 'dayjs';

/**
 * 全局资产/任务/监控变更版本号（供所有 <keep-alive> 视图感知跨页面数据变更并即时失效回源）
 */
export const assetMutationVersion = ref(0);
export const deletedScopeIdSet = reactive(new Set());

export function notifyAssetMutated(meta = {}) {
  if (Array.isArray(meta?.deletedScopeIds)) {
    meta.deletedScopeIds.forEach((sid) => {
      if (sid) deletedScopeIdSet.add(String(sid));
    });
  }
  assetMutationVersion.value += 1;
}

/**
 * 提取各资产维度记录的人类可读对象名称（用于跨页批量操作确认清单展示）
 */
export function getAssetRecordDisplayLabel(tabKey, record) {
  if (!record || typeof record !== 'object') return String(record || '');
  switch (tabKey) {
    case 'site':
      return record.site || record.url || record.hostname || record._id || '';
    case 'domain':
      return record.domain || record._id || '';
    case 'ip':
      return record.ip || record._id || '';
    case 'cip':
      return record.cidr_ip || record._id || '';
    case 'stat_finger':
      return record.name || record._id || '';
    case 'service':
      if (record.ip && record.port_id != null) {
        return `${record.service_name ? `${record.service_name} · ` : ''}${record.ip}:${record.port_id}`;
      }
      if (record.host && record.port != null) {
        return `${record.scheme || record.service_name ? `${record.scheme || record.service_name} · ` : ''}${record.host}:${record.port}`;
      }
      return record.service_name
        ? `${record.service_name}${Array.isArray(record.service_info) && record.service_info.length ? ` (${record.service_info.length})` : ''}`
        : (record._id || '');
    case 'npoc_service':
      return record.target || (record.host && record.port ? `${record.host}:${record.port}` : (record.host || record._id || ''));
    case 'cert':
      return record.ip ? `${record.ip}${record.port ? `:${record.port}` : ''}` : (record._id || '');
    case 'fileleak':
    case 'url':
      return record.url || record.site || record._id || '';
    case 'vuln':
      return [record.vul_name || record.plugin_name, record.target || record.vuln_url].filter(Boolean).join(' · ') || record._id || '';
    case 'nuclei_result':
      return [record.template_id, record.target || record.vuln_url].filter(Boolean).join(' · ') || record._id || '';
    case 'wih':
      return [record.record_type, record.content].filter(Boolean).join(': ') || record.site || record._id || '';
    default:
      return record.name || record.site || record.domain || record.ip || record.url || record._id || '';
  }
}

/**
 * 跨页多选对象名称映射追踪器（配合 preserveSelectedRowKeys: true，切页后仍完整保留已勾选对象真实名称）
 */
export function createSelectionLabelTracker() {
  const labelMap = new Map();

  const rememberRows = (rows, getKey, getLabel) => {
    if (!Array.isArray(rows)) return;
    for (const row of rows) {
      const k = getKey(row);
      if (k != null && k !== '') {
        labelMap.set(String(k), getLabel(row) || String(k));
      }
    }
  };

  const syncSelection = (selectedKeys, selectedRows, allVisibleRows, getKey, getLabel) => {
    rememberRows(allVisibleRows, getKey, getLabel);
    rememberRows(selectedRows, getKey, getLabel);
    const keepSet = new Set((selectedKeys || []).filter(k => k != null).map(k => String(k)));
    for (const key of Array.from(labelMap.keys())) {
      if (!keepSet.has(key)) {
        labelMap.delete(key);
      }
    }
  };

  const getLabels = (selectedKeys) => {
    return (selectedKeys || [])
      .filter(k => k != null && k !== '')
      .map(k => labelMap.get(String(k)) || String(k));
  };

  const clear = () => {
    labelMap.clear();
  };

  return {
    rememberRows,
    syncSelection,
    getLabels,
    clear,
  };
}

/**
 * 构造带可折叠对象清单（默认前 20 条 + 一键展开全部）和分级警示条的确认弹窗内容 VNode
 */
const CollapsibleSelectionList = defineComponent({
  name: 'CollapsibleSelectionList',
  props: {
    summary: { type: String, default: '' },
    listHeading: { type: String, default: '' },
    items: { type: Array, default: () => [] },
    previewLimit: { type: Number, default: 20 },
    alertType: { type: String, default: '' },
    alertMessage: { type: String, default: '' },
    alertDescription: { type: String, default: '' },
    expandText: { type: Function, default: (total) => `展开全部 (${total})` },
    collapseText: { type: String, default: '收起清单' },
  },
  setup(props) {
    const expanded = ref(false);
    return () => {
      const allItems = Array.isArray(props.items) ? props.items : [];
      const hasOverflow = allItems.length > props.previewLimit;
      const visibleItems = expanded.value || !hasOverflow ? allItems : allItems.slice(0, props.previewLimit);

      const children = [];
      if (props.alertType && (props.alertMessage || props.alertDescription)) {
        children.push(
          h(Alert, {
            type: props.alertType,
            showIcon: true,
            message: props.alertMessage,
            description: props.alertDescription || undefined,
            style: 'margin-bottom: 12px;',
          })
        );
      }
      if (props.summary) {
        children.push(
          h('div', { style: 'margin-bottom: 10px; color: var(--arl-text-color); line-height: 1.5;' }, props.summary)
        );
      }
      if (allItems.length > 0) {
        children.push(
          h(
            'div',
            {
              style:
                'background: var(--arl-bg-light); border: 1px solid var(--arl-border-color); border-radius: 6px; padding: 8px 10px; font-size: 12px; color: var(--arl-text-color);',
            },
            [
              props.listHeading
                ? h('div', { style: 'font-weight: 500; margin-bottom: 6px; opacity: 0.9;' }, props.listHeading)
                : null,
              h(
                'div',
                {
                  style:
                    'max-height: 180px; overflow-y: auto; line-height: 1.65; word-break: break-all; font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;',
                },
                visibleItems.map((label, idx) => h('div', { key: `${idx}-${label}` }, `${idx + 1}. ${label}`))
              ),
              hasOverflow
                ? h(
                    'div',
                    { style: 'margin-top: 6px; padding-top: 6px; border-top: 1px dashed var(--arl-border-color);' },
                    [
                      h(
                        'a',
                        {
                          href: 'javascript:void(0)',
                          style: 'font-size: 12px;',
                          onClick: (e) => {
                            e.preventDefault();
                            expanded.value = !expanded.value;
                          },
                        },
                        expanded.value ? props.collapseText : props.expandText(allItems.length)
                      ),
                    ]
                  )
                : null,
            ]
          )
        );
      }
      return h('div', { style: 'margin-top: 8px;' }, children);
    };
  },
});

export function buildSelectionConfirmContent(options) {
  return h(CollapsibleSelectionList, options);
}

/**
 * 序列化 searchForm 对象
 * 将 dayjs 日期范围数组安全转换为标准字符串，其余字段纯文本保留
 */
export function serializeSearchForm(form) {
  if (!form || typeof form !== 'object') return {};
  const result = {};
  for (const key of Object.keys(form)) {
    const val = form[key];
    if (val === '' || val === null || val === undefined) continue;
    if (Array.isArray(val)) {
      result[key] = val.map(item => {
        if (dayjs.isDayjs(item)) {
          return item.format('YYYY-MM-DD HH:mm:ss');
        }
        return item;
      });
    } else {
      result[key] = val;
    }
  }
  return result;
}

/**
 * 反序列化 searchForm 对象
 * 将时间字符串还原为 dayjs 实例以供 a-range-picker 正确双向绑定
 */
export function deserializeSearchForm(savedForm, searchFields = []) {
  if (!savedForm || typeof savedForm !== 'object') return {};
  const result = {};
  const fieldMap = {};
  const hasFields = Array.isArray(searchFields) && searchFields.length > 0;
  if (hasFields) {
    searchFields.forEach(f => {
      if (f && f.key) fieldMap[f.key] = f;
    });
  }

  for (const key of Object.keys(savedForm)) {
    const val = savedForm[key];
    if (val === '' || val === null || val === undefined) continue;
    // 🚨 防御幽灵过滤器：若已配置字段契约且该字段不在契约中，主动丢弃历史废弃缓存
    if (hasFields && !fieldMap[key]) continue;

    const field = fieldMap[key];
    if (field && field.type === 'dateRange') {
      if (Array.isArray(val) && val.length === 2) {
        const d0 = dayjs(val[0]);
        const d1 = dayjs(val[1]);
        result[key] = (d0.isValid() && d1.isValid()) ? [d0, d1] : null;
      } else {
        result[key] = null;
      }
    } else {
      result[key] = val;
    }
  }
  return result;
}

/**
 * 提取 searchFields 中的当前操作符配置
 */
export function extractOperators(searchFields = []) {
  const ops = {};
  if (Array.isArray(searchFields)) {
    searchFields.forEach(f => {
      if (f && f.key && f.operator !== undefined) {
        ops[f.key] = f.operator;
      }
    });
  }
  return ops;
}

/**
 * 将保存的操作符回填至 searchFields
 */
export function applyOperators(searchFields = [], ops = {}) {
  if (Array.isArray(searchFields) && ops) {
    searchFields.forEach(f => {
      if (f && f.key && ops[f.key] !== undefined) {
        f.operator = ops[f.key];
      }
    });
  }
}

/**
 * 安全加载 SessionStorage
 */
export function loadSessionTabState(storageKey) {
  if (!storageKey || typeof window === 'undefined' || !window.sessionStorage) return null;
  try {
    const raw = sessionStorage.getItem(storageKey);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) {
    console.warn(`[TabStateCache] Failed to load session state for key: ${storageKey}`, e);
    return null;
  }
}

/**
 * 安全写入 SessionStorage
 */
export function saveSessionTabState(storageKey, state) {
  if (!storageKey || typeof window === 'undefined' || !window.sessionStorage) return;
  try {
    sessionStorage.setItem(storageKey, JSON.stringify(state));
  } catch (e) {
    console.warn(`[TabStateCache] Failed to save session state for key: ${storageKey}`, e);
  }
}

/**
 * 创建多 Tab 独立状态与分层缓存控制器
 */
export function createTabStateCache({
  getStorageKey,
  tabConfig,
  defaultTab = 'site',
  canUseMemoryCache
}) {
  let currentKey = '';
  // 内存数据缓存：记录已加载的表格数据，避免重复请求
  const memoryDataCache = {};
  // 轻量状态缓存（搜索表单、操作符、页码）
  const tabStateMap = reactive({});
  // 记录每个 Tab 的初始默认操作符，用于点击“清除”时复位
  const defaultOperators = {};

  // 预采集初始默认操作符
  if (tabConfig) {
    for (const tabKey of Object.keys(tabConfig)) {
      if (tabConfig[tabKey]?.searchFields) {
        defaultOperators[tabKey] = extractOperators(tabConfig[tabKey].searchFields);
      }
    }
  }

  /**
   * 同步探测初始激活 Tab，供组件 setup 阶段 ref 初始化使用，避免首屏跳变
   */
  const getInitialTab = (preferredTab) => {
    if (preferredTab && tabConfig && tabConfig[preferredTab]) {
      return preferredTab;
    }
    const key = typeof getStorageKey === 'function' ? getStorageKey() : getStorageKey;
    if (key) {
      const saved = loadSessionTabState(key);
      if (saved && saved.activeTab && tabConfig && tabConfig[saved.activeTab]) {
        return saved.activeTab;
      }
    }
    return defaultTab;
  };

  /**
   * 初始化或在实体 ID 变化时调用
   * @returns {string} 恢复的 activeTab 标识
   */
  const init = () => {
    const key = typeof getStorageKey === 'function' ? getStorageKey() : getStorageKey;
    if (key !== currentKey) {
      // 切换了实体分组或任务，清空旧内存缓存
      Object.keys(memoryDataCache).forEach(k => delete memoryDataCache[k]);
      Object.keys(tabStateMap).forEach(k => delete tabStateMap[k]);
      currentKey = key || '';
    }

    if (!currentKey) return defaultTab;

    const saved = loadSessionTabState(currentKey);
    if (saved && saved.tabs) {
      for (const tabKey of Object.keys(saved.tabs)) {
        tabStateMap[tabKey] = {
          searchForm: saved.tabs[tabKey].searchForm || {},
          operators: saved.tabs[tabKey].operators || {},
          page: saved.tabs[tabKey].page || 1
        };
      }
      if (saved.activeTab && tabConfig[saved.activeTab]) {
        return saved.activeTab;
      }
    }
    return defaultTab;
  };

  /**
   * 保存特定 Tab 的轻量搜索与分页状态
   */
  const saveCurrentTab = (tabKey, currentSearchForm, page) => {
    if (!tabKey) return;
    if (!tabStateMap[tabKey]) {
      tabStateMap[tabKey] = { searchForm: {}, operators: {}, page: 1 };
    }
    tabStateMap[tabKey].searchForm = serializeSearchForm(currentSearchForm);
    if (tabConfig[tabKey]?.searchFields) {
      tabStateMap[tabKey].operators = extractOperators(tabConfig[tabKey].searchFields);
    }
    if (typeof page === 'number' && page > 0) {
      tabStateMap[tabKey].page = page;
    }

    // 立即持久化轻量状态至 SessionStorage
    syncToSessionStorage(tabKey);
  };

  /**
   * 同步轻量状态树到 SessionStorage
   */
  const syncToSessionStorage = (activeTabKey) => {
    const key = typeof getStorageKey === 'function' ? getStorageKey() : getStorageKey;
    if (!key) return;

    const tabsData = {};
    for (const tabKey of Object.keys(tabStateMap)) {
      tabsData[tabKey] = {
        searchForm: tabStateMap[tabKey].searchForm || {},
        operators: tabStateMap[tabKey].operators || {},
        page: tabStateMap[tabKey].page || 1
      };
    }

    saveSessionTabState(key, {
      activeTab: activeTabKey || defaultTab,
      tabs: tabsData
    });
  };

  /**
   * 获取指定 Tab 的反序列化搜索表单对象
   */
  const getTabSearchForm = (tabKey) => {
    const rawForm = tabStateMap[tabKey]?.searchForm || {};
    const searchFields = tabConfig[tabKey]?.searchFields || [];
    return deserializeSearchForm(rawForm, searchFields);
  };

  /**
   * 应用指定 Tab 保存的操作符
   */
  const applyTabOperators = (tabKey) => {
    const ops = tabStateMap[tabKey]?.operators;
    if (ops && tabConfig[tabKey]?.searchFields) {
      applyOperators(tabConfig[tabKey].searchFields, ops);
    }
  };

  /**
   * 获取指定 Tab 记忆的当前页码
   */
  const getTabPage = (tabKey) => {
    return tabStateMap[tabKey]?.page || 1;
  };

  /**
   * 更新内存数据缓存
   */
  const updateMemoryCache = (tabKey, dataSourceList, total, pageSize) => {
    if (!tabKey) return;
    memoryDataCache[tabKey] = {
      dataSource: Array.isArray(dataSourceList) ? [...dataSourceList] : [],
      total: total || 0,
      pageSize: typeof pageSize === 'number' && pageSize > 0 ? pageSize : undefined,
      isLoaded: true
    };
  };

  /**
   * 读取指定 Tab 的内存数据缓存
   * @param {string} tabKey
   * @param {number} [expectedPageSize] 期望的单页容量大小，用于多 Tab 切换及分页修改校验
   */
  const getMemoryCache = (tabKey, expectedPageSize) => {
    if (typeof canUseMemoryCache === 'function' && !canUseMemoryCache()) {
      return null;
    }
    if (!tabKey || !memoryDataCache[tabKey] || !memoryDataCache[tabKey].isLoaded) {
      return null;
    }
    const cached = memoryDataCache[tabKey];
    if (typeof expectedPageSize === 'number' && expectedPageSize > 0) {
      // 1. 若显式记录了 pageSize 且与当前期望不符，说明是不同分页粒度的历史切片，必须穿透重拉
      if (cached.pageSize && cached.pageSize !== expectedPageSize) {
        return null;
      }
      // 2. 若缓存条数小于当前期望条数，且总条数大于已缓存行数（说明存在未加载的完整页数据），必须穿透重拉
      if (cached.dataSource.length < expectedPageSize && cached.total > cached.dataSource.length) {
        return null;
      }
    }
    return cached;
  };

  /**
   * 使指定 Tab 的内存缓存失效（例如删除/添加资产后强制刷新）
   */
  const invalidateMemoryCache = (tabKey) => {
    if (tabKey && memoryDataCache[tabKey]) {
      memoryDataCache[tabKey].isLoaded = false;
      delete memoryDataCache[tabKey];
    }
  };

  /**
   * 使所有 Tab 的内存缓存失效（例如任务完成或每页容量改变后全局刷新）
   */
  const invalidateAllMemoryCaches = () => {
    Object.keys(memoryDataCache).forEach(k => {
      if (memoryDataCache[k]) {
        memoryDataCache[k].isLoaded = false;
      }
      delete memoryDataCache[k];
    });
  };

  /**
   * 重置指定 Tab 的状态（点击“清除”时调用）
   */
  const resetTabState = (tabKey) => {
    if (!tabKey) return;
    if (!tabStateMap[tabKey]) {
      tabStateMap[tabKey] = { searchForm: {}, operators: {}, page: 1 };
    }
    tabStateMap[tabKey].searchForm = {};
    tabStateMap[tabKey].page = 1;

    // 复位操作符为初始默认值
    if (defaultOperators[tabKey] && tabConfig[tabKey]?.searchFields) {
      applyOperators(tabConfig[tabKey].searchFields, defaultOperators[tabKey]);
      tabStateMap[tabKey].operators = { ...defaultOperators[tabKey] };
    }

    // 内存数据设为未加载
    invalidateMemoryCache(tabKey);

    // 同步到 SessionStorage
    syncToSessionStorage(tabKey);
  };

  return {
    getInitialTab,
    init,
    saveCurrentTab,
    getTabSearchForm,
    applyTabOperators,
    getTabPage,
    updateMemoryCache,
    getMemoryCache,
    invalidateMemoryCache,
    invalidateAllMemoryCaches,
    resetTabState,
    syncToSessionStorage
  };
}
