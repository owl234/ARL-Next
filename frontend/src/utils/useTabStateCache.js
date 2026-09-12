import { ref, reactive } from 'vue';
import dayjs from 'dayjs';

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
  const updateMemoryCache = (tabKey, dataSourceList, total) => {
    if (!tabKey) return;
    memoryDataCache[tabKey] = {
      dataSource: Array.isArray(dataSourceList) ? [...dataSourceList] : [],
      total: total || 0,
      isLoaded: true
    };
  };

  /**
   * 读取指定 Tab 的内存数据缓存
   */
  const getMemoryCache = (tabKey) => {
    if (typeof canUseMemoryCache === 'function' && !canUseMemoryCache()) {
      return null;
    }
    if (!tabKey || !memoryDataCache[tabKey] || !memoryDataCache[tabKey].isLoaded) {
      return null;
    }
    return memoryDataCache[tabKey];
  };

  /**
   * 使指定 Tab 的内存缓存失效（例如删除/添加资产后强制刷新）
   */
  const invalidateMemoryCache = (tabKey) => {
    if (tabKey && memoryDataCache[tabKey]) {
      memoryDataCache[tabKey].isLoaded = false;
    }
  };

  /**
   * 使所有 Tab 的内存缓存失效（例如任务完成或批量操作后全局刷新）
   */
  const invalidateAllMemoryCaches = () => {
    Object.keys(memoryDataCache).forEach(k => {
      if (memoryDataCache[k]) {
        memoryDataCache[k].isLoaded = false;
      }
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
