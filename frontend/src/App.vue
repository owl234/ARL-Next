<template>
  <a-config-provider :theme="currentTheme">
    <div :style="{ 
      '--arl-theme-color': currentPrimaryColor,
      color: isDarkMode ? 'rgba(255, 255, 255, 0.85)' : 'rgba(0, 0, 0, 0.85)' 
    }" style="width: 100%; height: 100%; transition: all 0.3s; min-height: 100vh;">
      <div :class="{ 'glass-overlay': currentBgImage }" style="width: 100%; height: 100%; min-height: 100vh;">
        <router-view></router-view>
      </div>
    </div>
  </a-config-provider>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watchEffect } from 'vue';
import { theme } from 'ant-design-vue';
import { dbHelper } from '@/utils/theme';

// 默认恢复为 火山橙，如果是之前保存的颜色则使用保存的
const currentPrimaryColor = ref('#fa541c'); 
const isDarkMode = ref(false);
const currentBgImage = ref('');


const updateGlobalCssVariables = () => {
  const root = document.documentElement;
  const isDark = isDarkMode.value;
  const hasBg = !!currentBgImage.value;
  
  root.style.setProperty('--arl-theme-color', currentPrimaryColor.value);
  root.style.setProperty('--arl-bg-light', isDark ? (hasBg ? 'rgba(17, 17, 17, 0.3)' : '#111111') : (hasBg ? 'rgba(241, 245, 249, 0.3)' : 'rgba(241, 245, 249, 0.8)'));
  root.style.setProperty('--arl-bg-white', isDark ? (hasBg ? 'rgba(17, 17, 17, 0.3)' : '#111111') : (hasBg ? 'rgba(255, 255, 255, 0.3)' : 'rgba(255, 255, 255, 0.8)'));
  root.style.setProperty('--arl-bg-layout', isDark ? (hasBg ? 'rgba(0, 0, 0, 0.3)' : '#000000') : (hasBg ? 'rgba(241, 245, 249, 0.3)' : '#f1f5f9'));
  root.style.setProperty('--arl-border-color', isDark ? (hasBg ? 'rgba(51, 51, 51, 0.4)' : '#333333') : (hasBg ? 'rgba(226, 232, 240, 0.4)' : 'rgba(226, 232, 240, 0.8)'));
  root.style.setProperty('--arl-text-color', isDark ? 'rgba(255, 255, 255, 0.85)' : 'rgba(0, 0, 0, 0.85)');
  
  if (isDark) {
    document.body.classList.add('dark-mode');
  } else {
    document.body.classList.remove('dark-mode');
  }
};

watchEffect(() => {
  updateGlobalCssVariables();
});

const handleThemeChange = (e) => {
  currentPrimaryColor.value = e.detail;
};

const handleDarkModeChange = (e) => {
  isDarkMode.value = e.detail;
  document.body.style.backgroundColor = e.detail ? '#000000' : '#f1f5f9';
  document.documentElement.style.backgroundColor = e.detail ? '#000000' : '#f1f5f9';
};

const handleBgImageChange = (e) => {
  currentBgImage.value = e.detail;
  if (e.detail) {
    document.body.style.backgroundImage = `url(${e.detail})`;
    document.body.style.backgroundSize = 'cover';
    document.body.style.backgroundPosition = 'center';
    document.body.style.backgroundAttachment = 'fixed';
    document.body.classList.add('has-bg-image');
    document.documentElement.classList.add('has-bg-image');
  } else {
    document.body.style.backgroundImage = 'none';
    document.body.classList.remove('has-bg-image');
    document.documentElement.classList.remove('has-bg-image');
  }
};

const currentTheme = computed(() => {
  const isDark = isDarkMode.value;
  const hasBg = !!currentBgImage.value;
  
  return {
    algorithm: isDark ? theme.darkAlgorithm : theme.defaultAlgorithm,
    token: { 
      colorBgBase: isDark ? (hasBg ? 'rgba(17, 17, 17, 0.7)' : '#111111') : (hasBg ? 'rgba(255, 255, 255, 0.7)' : '#ffffff'),
      colorBgLayout: isDark ? (hasBg ? 'rgba(0, 0, 0, 0.4)' : '#000000') : (hasBg ? 'rgba(241, 245, 249, 0.4)' : '#f1f5f9'),
      colorPrimary: currentPrimaryColor.value, 
      colorLink: currentPrimaryColor.value, 
      colorLinkHover: currentPrimaryColor.value, 
      colorLinkActive: currentPrimaryColor.value, 
      colorInfo: currentPrimaryColor.value,
      colorSuccess: '#4caf50',
      colorWarning: '#ffb300',
      colorError: '#e53935',
      colorBgContainer: isDark ? (hasBg ? 'rgba(17, 17, 17, 0.3)' : '#111111') : (hasBg ? 'rgba(255, 255, 255, 0.4)' : '#ffffff'),
      colorBgElevated: isDark ? (hasBg ? 'rgba(17, 17, 17, 0.4)' : '#111111') : (hasBg ? 'rgba(255, 255, 255, 0.5)' : '#ffffff'),
      colorBorder: isDark ? (hasBg ? 'rgba(51, 51, 51, 0.4)' : '#333333') : (hasBg ? 'rgba(217, 217, 217, 0.4)' : 'rgba(217, 217, 217, 0.8)'),
      colorBorderSecondary: isDark ? 'rgba(34, 34, 34, 0.8)' : 'rgba(240, 240, 240, 0.8)',
      colorTextBase: isDark ? 'rgba(255, 255, 255, 0.85)' : 'rgba(0, 0, 0, 0.85)',
      borderRadius: 8 
    }
  };
});

onMounted(() => {
  const savedColor = localStorage.getItem('themeColor');
  if (savedColor) {
    currentPrimaryColor.value = savedColor;
  } else {
    localStorage.setItem('themeColor', '#fa541c');
  }

  const savedDarkMode = localStorage.getItem('darkMode');
  if (savedDarkMode === 'true') {
    isDarkMode.value = true;
  }
  
  dbHelper.get('bgImage').then((savedBgImage) => {
    if (savedBgImage) {
      currentBgImage.value = savedBgImage;
      requestAnimationFrame(() => {
        document.body.style.backgroundImage = `url(${savedBgImage})`;
        document.body.style.backgroundSize = 'cover';
        document.body.style.backgroundPosition = 'center';
        document.body.style.backgroundAttachment = 'fixed';
        document.body.classList.add('has-bg-image');
        document.documentElement.classList.add('has-bg-image');
      });
    } else {
      document.body.style.backgroundColor = isDarkMode.value ? '#000000' : '#f1f5f9';
      document.documentElement.style.backgroundColor = isDarkMode.value ? '#000000' : '#f1f5f9';
    }
  });
  
  window.addEventListener('theme-changed', handleThemeChange);
  window.addEventListener('dark-mode-changed', handleDarkModeChange);
  window.addEventListener('bg-image-changed', handleBgImageChange);
});

onUnmounted(() => {
  window.removeEventListener('theme-changed', handleThemeChange);
  window.removeEventListener('dark-mode-changed', handleDarkModeChange);
  window.removeEventListener('bg-image-changed', handleBgImageChange);
});
</script>

<style>
/* 清除浏览器默认的内外边距 */
html, body {
  margin: 0;
  padding: 0;
  width: 100%;
  min-height: 100vh;
  /* 将背景底色统一刷成动态变量，避免边缘有白边或刷新闪烁 */
  background-color: var(--arl-bg-layout, #f1f5f9);
}

html.has-bg-image, body.has-bg-image {
  background-color: transparent !important;
}

/* 让 Vue 的挂载根节点也 100% 撑满 */
#app {
  width: 100%;
  min-height: 100vh;
  max-width: none !important; /* 强行覆盖可能遗留的 max-width */
  padding: 0 !important;      /* 强行覆盖可能遗留的 padding */
}

/* 全局修复：让没有 href 的 <a> 伪链接也能继承并跟随主题色动态变化 */
a:not([href]) {
  color: v-bind('currentPrimaryColor');
  cursor: pointer;
  transition: color 0.3s, opacity 0.3s;
}
a:not([href]):hover {
  color: v-bind('currentPrimaryColor');
  opacity: 0.8;
}

/* 毛玻璃遮罩层 */
.glass-overlay {
  backdrop-filter: blur(8px);
  background-color: v-bind('isDarkMode ? "rgba(0, 0, 0, 0.4)" : "rgba(255, 255, 255, 0.3)"');
  transition: all 0.3s;
}

body.ui-hidden .glass-overlay {
  background-color: transparent !important;
  backdrop-filter: none !important;
}

/* 隐藏 UI 时禁止滚动，防止出现下方白底空白 */
body.ui-hidden {
  overflow: hidden !important;
}
body.ui-hidden #app {
  height: 100vh !important;
  overflow: hidden !important;
}

/* 强制让 Ant Design 布局组件背景透明，避免遮挡 body 背景 */
body.has-bg-image .ant-layout,
body.has-bg-image .ant-layout-content,
body.has-bg-image .ant-layout-sider,
body.has-bg-image .ant-menu,
body.has-bg-image .ant-menu-sub {
  background: transparent !important;
  background-color: transparent !important;
}

/* 始终覆盖 Ant Design 的暗色菜单默认深蓝背景，以继承我们自定义的 Slate 黑/蓝系背景 */
.ant-menu-dark,
.ant-menu.ant-menu-dark,
.ant-menu-dark .ant-menu-sub {
  background: transparent !important;
  background-color: transparent !important;
}

body.has-bg-image .ant-card,
body.has-bg-image .ant-table-wrapper,
body.has-bg-image .ant-table,
body.has-bg-image .ant-table-thead > tr > th,
body.has-bg-image .ant-table-tbody > tr > td,
body.has-bg-image .ant-tabs-nav,
body.has-bg-image .ant-modal-content,
body.has-bg-image .ant-drawer-content {
  background: var(--arl-bg-white) !important;
  backdrop-filter: blur(8px);
}

body.has-bg-image .ant-modal-header,
body.has-bg-image .ant-modal-footer,
body.has-bg-image .ant-drawer-header,
body.has-bg-image .ant-drawer-footer {
  background: transparent !important;
  background-color: transparent !important;
  border-color: var(--arl-border-color) !important;
}

/* ========================================================
   暗黑模式优化 (纯暗黑 & 沉浸式通用)
   ======================================================== */
body.dark-mode .ant-card {
  border: 1px solid var(--arl-border-color) !important;
  box-shadow: none !important;
}

body.dark-mode .ant-card-head {
  border-bottom: 1px solid var(--arl-border-color) !important;
}

body.dark-mode .ant-table-thead > tr > th {
  background: #111111 !important;
  border-bottom: 1px solid var(--arl-border-color) !important;
  color: rgba(255, 255, 255, 0.85) !important;
}

body.dark-mode .ant-table-tbody > tr > td {
  border-bottom: 1px solid var(--arl-border-color) !important;
}

body.dark-mode .ant-table-tbody > tr:hover > td {
  background: #1a1a1a !important;
}

/* 分页组件在暗黑模式下的边框和背景优化 */
body.dark-mode .ant-pagination-item {
  background: transparent !important;
  border-color: var(--arl-border-color) !important;
}
body.dark-mode .ant-pagination-item-active {
  background: var(--arl-theme-color) !important;
  border-color: var(--arl-theme-color) !important;
}
body.dark-mode .ant-pagination-item-active a {
  color: #fff !important;
}
body.dark-mode .ant-pagination-prev .ant-pagination-item-link,
body.dark-mode .ant-pagination-next .ant-pagination-item-link {
  background: transparent !important;
  border-color: var(--arl-border-color) !important;
  color: rgba(255, 255, 255, 0.65) !important;
}

body.has-bg-image .ant-modal-title,
body.has-bg-image .ant-drawer-title,
body.has-bg-image .ant-modal-close {
  color: var(--arl-text-color) !important;
  background: transparent !important;
}

/* 滚动条暗黑模式/沉浸模式美化 */
::-webkit-scrollbar {
  width: 8px;
  height: 8px;
}
::-webkit-scrollbar-track {
  background: transparent;
}
::-webkit-scrollbar-thumb {
  background: var(--arl-border-color);
  border-radius: 4px;
}
::-webkit-scrollbar-thumb:hover {
  background: var(--arl-theme-color);
}


</style>