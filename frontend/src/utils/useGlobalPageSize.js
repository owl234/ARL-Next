import { ref, watch } from 'vue';

const getInitialPageSize = (defaultSize = 10) => {
  try {
    const storedSize = localStorage.getItem('global_pageSize');
    if (storedSize) {
      const parsed = parseInt(storedSize, 10);
      if (!isNaN(parsed) && parsed > 0) {
        return parsed;
      }
    }
  } catch (e) {
    console.error('Failed to read global_pageSize from localStorage:', e);
  }
  return defaultSize;
};

// 单例响应式状态，全站各组件共享同一引用
const globalPageSize = ref(getInitialPageSize(10));

// 监听变动并安全同步到 localStorage
watch(globalPageSize, (newSize) => {
  try {
    if (newSize && !isNaN(newSize) && newSize > 0) {
      localStorage.setItem('global_pageSize', String(newSize));
    }
  } catch (e) {
    console.error('Failed to save global_pageSize to localStorage:', e);
  }
});

export function useGlobalPageSize() {
  return globalPageSize;
}

