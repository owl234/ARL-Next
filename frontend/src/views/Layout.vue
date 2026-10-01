<template>
  <a-layout :style="{ height: '100vh', background: 'transparent' }">
    <a-layout-sider v-model:collapsed="collapsed" collapsible :trigger="null" width="170" :style="{ background: hasBgImage ? (isUIHidden ? 'transparent' : 'rgba(11, 17, 32, 0.6)') : '#0b1120', borderRight: isUIHidden ? 'none' : (isDarkMode ? '1px solid #1e293b' : 'none'), transition: 'all 0.5s' }">
      <div class="logo-container" @click="toggleUI" title="点击隐藏/显示界面" style="height: 64px; display: flex; align-items: center; justify-content: center; cursor: pointer; z-index: 999; position: relative;" :style="{ background: hasBgImage ? 'transparent' : '#0b1120', borderBottom: isDarkMode ? '1px solid #1e293b' : 'none' }">
        <DeploymentUnitOutlined class="logo-icon" :style="{ color: 'var(--arl-theme-color)', fontSize: '20px' }" />
        <span class="logo-text" v-show="!collapsed" style="color: #f1f5f9; font-size: 16px; margin-left: 8px; font-weight: 500;">ARL-Next</span>
      </div>

      <div ref="sidebarMenuWrapperRef" class="sidebar-menu-wrapper" :style="{ opacity: isUIHidden ? 0 : 1, pointerEvents: isUIHidden ? 'none' : 'auto', transition: 'opacity 0.5s' }">
        <a-menu v-model:selectedKeys="selectedKeys" theme="dark" mode="inline" @click="handleMenuClick">
          <a-menu-item
            v-for="item in menuItems"
            :key="item.key"
            :data-key="item.key"
            class="sidebar-sortable-menu-item"
          >
            <template #icon>
              <component :is="item.icon" />
            </template>
            <span class="sidebar-menu-title-text">{{ item.title }}</span>
            <span
              v-if="!collapsed"
              class="sidebar-menu-drag-handle"
              @click.stop
              title="按住拖拽调整顺序"
            >
              <HolderOutlined />
            </span>
          </a-menu-item>
        </a-menu>
      </div>
    </a-layout-sider>

    <a-layout :style="{ background: 'transparent', opacity: isUIHidden ? 0 : 1, pointerEvents: isUIHidden ? 'none' : 'auto', transition: 'opacity 0.5s', overflow: 'hidden' }">
      <a-layout-header :style="{ background: isDarkMode ? 'rgba(15, 23, 42, 0.75)' : 'rgba(255, 255, 255, 0.75)', backdropFilter: 'blur(12px)', WebkitBackdropFilter: 'blur(12px)', padding: '0 24px', display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderBottom: '1px solid ' + (isDarkMode ? '#1e293b' : '#e2e8f0'), zIndex: 10, position: 'relative' }">
        <div style="display: flex; align-items: center;">
          <span class="trigger" @click="() => (collapsed = !collapsed)" style="font-size: 18px; cursor: pointer; margin-right: 24px;">
            <menu-unfold-outlined v-if="collapsed" /><menu-fold-outlined v-else />
          </span>
          <span :style="{ fontSize: '16px', fontWeight: 500, color: isDarkMode ? 'rgba(255,255,255,.85)' : 'var(--arl-text-color)' }">{{ currentPageTitle }}</span>
        </div>

        <div style="display: flex; align-items: center; color: var(--arl-text-color);">
          <SupportAuthorPopover />

          <a-dropdown>
            <span class="header-text-action" style="cursor: pointer; margin-right: 24px; display: flex; align-items: center;">
              <BgColorsOutlined style="font-size: 16px; margin-right: 4px;" />
              主题色
            </span>
            <template #overlay>
              <a-menu @click="handleThemeChange">
                <a-menu-item key="#00bcd4">
                  <span style="display: inline-block; width: 12px; height: 12px; background: #00bcd4; border-radius: 50%; margin-right: 8px;"></span>ARL 青
                </a-menu-item>
                <a-menu-item key="#1890ff">
                  <span style="display: inline-block; width: 12px; height: 12px; background: #1890ff; border-radius: 50%; margin-right: 8px;"></span>AntD 蓝
                </a-menu-item>
                <a-menu-item key="#52c41a">
                  <span style="display: inline-block; width: 12px; height: 12px; background: #52c41a; border-radius: 50%; margin-right: 8px;"></span>极客绿
                </a-menu-item>
                <a-menu-item key="#fa541c">
                  <span style="display: inline-block; width: 12px; height: 12px; background: #fa541c; border-radius: 50%; margin-right: 8px;"></span>火山橙
                </a-menu-item>
                <a-menu-item key="#eb2f96">
                  <span style="display: inline-block; width: 12px; height: 12px; background: #eb2f96; border-radius: 50%; margin-right: 8px;"></span>猛男粉
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>

          <a-upload :show-upload-list="false" :before-upload="handleUploadBackground" accept="image/*">
            <span class="header-text-action" style="cursor: pointer; margin-right: 24px; display: flex; align-items: center;">
              <PictureOutlined style="font-size: 16px; margin-right: 4px;" />
              自定义背景
            </span>
          </a-upload>

          <div style="margin-right: 24px; display: flex; align-items: center;" title="黑客暗色模式">
            <a-switch checked-children="🌙" un-checked-children="☀️" v-model:checked="isDarkMode" @change="toggleDarkMode" />
          </div>

          <div style="margin-right: 24px; display: flex; align-items: center;" :title="isBasicAuthOnline ? (isBasicAuthEnabled ? 'Basic Auth 安全防护已开启 (点击切换)' : 'Basic Auth 安全防护已关闭 (点击切换)') : 'Basic Auth 控制服务未连接'">
            <a-switch :checked="isBasicAuthEnabled" :loading="isBasicAuthLoading" :disabled="!isBasicAuthOnline" @click="handleBasicAuthSwitchClick" checked-children="🔒" un-checked-children="🔓" />
          </div>

          <span class="header-text-action" style="cursor: pointer; margin-right: 24px; display: flex; align-items: center;" @click="handleShowMcpModal">
            <RobotOutlined style="font-size: 16px; margin-right: 4px;" />
            AI 助手接入 (MCP)
          </span>
          
          <a-dropdown>
            <span class="header-text-action" style="cursor: pointer; margin-right: 24px; display: flex; align-items: center;" title="用户设置与操作">
              <a-avatar style="background-color: #87d068; margin-right: 8px;" size="small"><template #icon><UserOutlined /></template></a-avatar>
              <span>{{ currentUsername }}</span>
              <DownOutlined style="font-size: 10px; margin-left: 6px; opacity: 0.7;" />
            </span>
            <template #overlay>
              <a-menu>
                <a-menu-item key="changePass" @click="showChangePassModal = true">
                  <KeyOutlined style="margin-right: 8px;" />修改密码
                </a-menu-item>
                <a-menu-item key="resetMenuOrder" @click="handleResetMenuOrder">
                  <ReloadOutlined style="margin-right: 8px;" />恢复默认菜单顺序
                </a-menu-item>
                <a-menu-divider />
                <a-menu-item key="logout" @click="handleLogout" style="color: #ff4d4f;">
                  <LogoutOutlined style="margin-right: 8px;" />退出登录
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
          
          <span class="header-text-action" style="cursor: pointer; margin-right: 24px;" @click="showChangePassModal = true">修改密码</span>
          
          <a-tooltip title="退出登录" placement="bottom">
            <span class="header-icon-action header-icon-danger" style="cursor: pointer;" @click="handleLogout">
              <LogoutOutlined style="font-size: 16px;" />
            </span>
          </a-tooltip>
        </div>
      </a-layout-header>

      <a-layout-content class="arl-main-content" style="margin: 16px; display: flex; flex-direction: column; overflow-y: auto; height: 0;">
        <div :style="{ background: hasBgImage ? (isDarkMode ? 'rgba(15, 23, 42, 0.5)' : 'rgba(255, 255, 255, 0.4)') : (isDarkMode ? '#0f172a' : 'transparent'), flex: '1 0 auto', display: 'flex', flexDirection: 'column', borderRadius: '4px' }">
          <router-view v-slot="{ Component }">
            <!-- ★ 改动：include 中组件名与路由 name 对齐 -->
            <keep-alive include="Dashboard,TaskList,TaskDetail,AssetScope,GroupAssetsDetail,AssetSearch,AssetMonitor,PlanningTasks,GithubManage,PocList,Fingerprint,Policy,SystemSettings,PlatformDashboard,PlatformList,PlatformSubmitRecords,PlatformScheduleConfig">
              <component :is="Component" />
            </keep-alive>
          </router-view>
        </div>
        <div :style="{ textAlign: 'center', padding: '16px 0', color: isDarkMode ? 'rgba(255,255,255,.45)' : 'rgba(0,0,0,.45)', fontSize: '12px' }">
          Powered by ARL-Next
        </div>
      </a-layout-content>
    </a-layout>
  </a-layout>

  <a-modal
      v-model:visible="showMcpModal"
      title="AI 助手 MCP 客户端配置"
      @cancel="showMcpModal = false"
      :footer="null"
      width="640px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
  >
    <div style="margin-bottom: 16px;">
      <p style="margin-bottom: 10px;">支持接入 CC-Switch、Claude Code、Cursor、Windsurf 或 Antigravity 等 AI 助手：</p>
      <div :style="{ background: hasBgImage ? 'rgba(0,0,0,0.15)' : 'var(--arl-bg-light)', border: hasBgImage ? '1px solid rgba(255,255,255,0.1)' : '1px solid var(--arl-border-color)', borderRadius: '6px', padding: '12px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }">
        <div>
          <div style="font-weight: 600; font-size: 13px; margin-bottom: 2px;">📥 第一步：导出专属客户端脚本</div>
          <div style="font-size: 12px; color: var(--arl-text-color); opacity: 0.75;">已预置当前账号 Token 与服务端地址，零三方依赖，开箱即用。</div>
        </div>
        <a-button type="primary" :loading="isDownloadingScript" @click="downloadMcpScript">
          下载 arl_mcp.py
        </a-button>
      </div>
    </div>

    <div style="margin-bottom: 8px; font-size: 13px; font-weight: 500;">
      📋 第二步：复制配置并粘贴至客户端 <code>"mcpServers"</code> 节点下：
    </div>

    <div style="position: relative;">
      <pre :style="{ background: hasBgImage ? 'rgba(0,0,0,0.2)' : 'var(--arl-bg-light)', padding: '16px', borderRadius: '6px', overflowX: 'auto', fontSize: '13px', border: hasBgImage ? '1px solid rgba(255,255,255,0.1)' : '1px solid var(--arl-border-color)', margin: 0 }"><code :style="{ color: hasBgImage ? 'var(--arl-text-color)' : 'inherit' }">{{ mcpConfigJson }}</code></pre>
      <div style="position: absolute; top: 12px; right: 12px; display: flex; gap: 8px;">
        <a-popconfirm
          title="刷新将立即作废当前 Token，导致已导出的脚本与已接入客户端失效，确认刷新？"
          okText="确认刷新"
          cancelText="取消"
          @confirm="refreshMcpToken"
        >
          <a-button type="default" size="small" :loading="isRefreshingToken">刷新 Token</a-button>
        </a-popconfirm>
        <a-button type="primary" size="small" @click="copyMcpConfig">复制配置</a-button>
      </div>
    </div>

    <div style="margin-top: 14px; font-size: 12px; color: var(--arl-text-color); opacity: 0.75; line-height: 1.6;">
      💡 <b>免环境配置</b>：脚本已内嵌访问凭据，默认假定下载至 <code>~/Downloads/arl_mcp.py</code>。若存放于其他路径，请将 <code>args</code> 调整为实际绝对路径；Windows 环境请使用 <code>python</code> 命令。<br/>
      🔒 <b>凭据安全</b>：导出的脚本包含当前账号的高权限 API Token，请妥善保管勿公开提交；若发生泄露可点击“刷新 Token”一键作废。
    </div>
  </a-modal>

  <a-modal
      v-model:visible="showChangePassModal"
      title="修改密码"
      @ok="handleChangePass"
      :confirmLoading="isSubmitting"
      @cancel="handleCancelChangePass"
      okText="确认修改"
      cancelText="取消"
  >
    <a-form :model="passForm" :rules="passRules" ref="passFormRef" layout="vertical">
      <a-form-item label="旧密码" name="old_password">
        <a-input-password v-model:value="passForm.old_password" placeholder="请输入旧密码" />
      </a-form-item>
      <a-form-item label="新密码" name="new_password">
        <a-input-password v-model:value="passForm.new_password" placeholder="请输入新密码" />
      </a-form-item>
      <a-form-item label="确认新密码" name="check_password">
        <a-input-password v-model:value="passForm.check_password" placeholder="请再次输入新密码" />
      </a-form-item>
    </a-form>
  </a-modal>

  <!-- Basic Auth 配置与开启弹窗 -->
  <a-modal
    v-model:visible="showBasicAuthModal"
    title="🔒 开启 Nginx Basic Auth 前置安全防护"
    okText="确认开启并生效"
    cancelText="取消"
    :confirmLoading="isBasicAuthLoading"
    @ok="handleConfirmEnableBasicAuth"
    @cancel="showBasicAuthModal = false"
    width="520px"
    wrapClassName="arl-theme-modal"
    rootClassName="arl-theme-modal"
  >
    <div style="margin-bottom: 16px; font-size: 13px; line-height: 1.6; color: var(--arl-text-color);">
      <p style="margin-bottom: 8px;">开启 Basic Auth 前置安全网关防护后，访问系统前需输入 HTTP 基础认证账密，可有效抵御公网扫描器被动探测与爆破。</p>
    </div>

    <a-form :model="basicAuthForm" :rules="basicAuthRules" ref="basicAuthFormRef" layout="vertical">
      <a-form-item label="Basic Auth 账号" name="username" extra="基础认证账号，默认为 admin">
        <a-input v-model:value="basicAuthForm.username" placeholder="请输入账号" />
      </a-form-item>
      <a-form-item label="Basic Auth 密码" name="password" extra="留空则保持现有密码或使用系统默认密码 (arl_next)">
        <a-input-password v-model:value="basicAuthForm.password" placeholder="留空使用默认/现有密码，或输入新密码" />
      </a-form-item>
    </a-form>

    <div style="background: var(--arl-bg-light, rgba(0,0,0,0.03)); padding: 12px; border-radius: 6px; border: 1px solid var(--arl-border-color, rgba(255,255,255,0.08)); font-size: 12px; color: var(--arl-text-color); opacity: 0.85;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
        <span style="font-weight: bold; color: var(--arl-theme-color);">💡 快速预设：</span>
        <a-button type="link" size="small" style="padding: 0; height: auto;" @click="resetBasicAuthDefaults">填充默认凭证 (admin / arl_next)</a-button>
      </div>
      <div>• 凭证文件持久化存放于宿主机工作目录下的 <code>frontend/.htpasswd</code>。</div>
      <div style="margin-top: 4px; color: #faad14;">• <b>验证提示：</b> 浏览器会长期缓存基础认证，开启后若需验证防护拦截效果，请使用<b>无痕窗口</b>访问。</div>
    </div>
  </a-modal>

  <!-- 沉浸式背景屏幕保护叠加层 -->
  <div class="screensaver-overlay" :class="{ 'is-active': isUIHidden }">
    <div class="screensaver-content">
      <div class="screensaver-time">{{ currentTime }}</div>
      <div class="screensaver-brand">
        <DeploymentUnitOutlined class="screensaver-icon" />
        <span>ARL-Next OS</span>
      </div>
      <div class="screensaver-tip">Monitoring assets... Click anywhere to resume.</div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, computed, onUnmounted, createVNode, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
// 引入 request (根据你的实际路径调整)
import request from '@/utils/request';
// 引入主题提取工具和 IndexedDB
import { extractDominantColor, processImageToBase64, dbHelper } from '@/utils/theme';
// 引入 Ant Design 的消息提示与模态框
import { message, Modal } from 'ant-design-vue';
import SupportAuthorPopover from '@/components/SupportAuthorPopover.vue';
import { copyText } from '@/utils/clipboard';
import Sortable from 'sortablejs';

// 补全所有需要的图标
import {
  DashboardOutlined,
  MenuUnfoldOutlined,
  MenuFoldOutlined,
  UserOutlined,
  LogoutOutlined,
  GlobalOutlined,
  SearchOutlined,
  DesktopOutlined,
  AppstoreOutlined,
  SettingOutlined,
  TagsOutlined,
  BugOutlined,
  ClockCircleOutlined,
  GithubOutlined,
  DeploymentUnitOutlined,
  RobotOutlined,
  BgColorsOutlined,
  PictureOutlined,
  ExclamationCircleOutlined,
  HolderOutlined,
  DownOutlined,
  KeyOutlined,
  ReloadOutlined
} from '@ant-design/icons-vue';

const route = useRoute();
const router = useRouter();
const collapsed = ref(false);
const selectedKeys = ref([route.path]);
const isDarkMode = ref(false);
const currentUsername = ref('admin');
const hasBgImage = ref(false);
const isUIHidden = ref(false);

const isBasicAuthEnabled = ref(false);
const isBasicAuthOnline = ref(true);
const isBasicAuthLoading = ref(false);

const currentTime = ref('');
let timeInterval = null;

// ---------- 左侧边栏动态菜单与拖拽重排逻辑 ----------
const defaultMenuItems = [
  { key: '/dashboard', title: '仪表盘', icon: DashboardOutlined },
  { key: '/group', title: '资产分组', icon: AppstoreOutlined },
  { key: '/taskList', title: '任务管理', icon: GlobalOutlined },
  { key: '/asset-search', title: '资产搜索', icon: SearchOutlined },
  { key: '/assetsMonitor', title: '资产监控', icon: DesktopOutlined },
  { key: '/planningTasks', title: '计划任务', icon: ClockCircleOutlined },
  { key: '/GitHubTasks/GitHubTasksList', title: 'GitHub监控', icon: GithubOutlined },
  { key: '/pocList', title: 'POC管理', icon: BugOutlined },
  { key: '/fingerprint', title: '指纹管理', icon: TagsOutlined },
  { key: '/policy', title: '策略配置', icon: SettingOutlined },
  // ★ 漏洞平台聚合菜单
  { key: '/platform/dashboard', title: '漏洞平台', icon: DeploymentUnitOutlined },
  { key: '/platform/platforms', title: '平台管理', icon: AppstoreOutlined },
  { key: '/platform/records', title: '提交记录', icon: BugOutlined },
  { key: '/platform/schedules', title: '调度配置', icon: ClockCircleOutlined },
  { key: '/systemSettings', title: '系统设置', icon: SettingOutlined },
];

const getMenuStorageKey = () => `arl_sidebar_menu_order_${currentUsername.value || 'default'}`;

const loadOrderedMenuItems = () => {
  try {
    const raw = localStorage.getItem(getMenuStorageKey());
    if (!raw) return [...defaultMenuItems];
    const savedKeys = JSON.parse(raw);
    if (!Array.isArray(savedKeys)) return [...defaultMenuItems];

    const ordered = [];
    const itemMap = new Map(defaultMenuItems.map(item => [item.key, item]));

    savedKeys.forEach(k => {
      if (itemMap.has(k)) {
        ordered.push(itemMap.get(k));
        itemMap.delete(k);
      }
    });
    // 兼容升级：若未来系统新增菜单项，自动增量安全追加在末尾
    defaultMenuItems.forEach(item => {
      if (itemMap.has(item.key)) {
        ordered.push(item);
      }
    });
    return ordered;
  } catch (e) {
    console.error('Failed to load sidebar menu order:', e);
    return [...defaultMenuItems];
  }
};

const menuItems = ref(loadOrderedMenuItems());

const saveMenuOrder = () => {
  try {
    const keys = menuItems.value.map(item => item.key);
    localStorage.setItem(getMenuStorageKey(), JSON.stringify(keys));
  } catch (e) {
    console.error('Failed to save sidebar menu order:', e);
  }
};

const handleResetMenuOrder = () => {
  Modal.confirm({
    title: '恢复默认菜单顺序',
    icon: createVNode(ExclamationCircleOutlined),
    content: '确认要恢复左侧边栏为出厂默认的菜单排列顺序吗？',
    okText: '确认恢复',
    cancelText: '取消',
    onOk: () => {
      localStorage.removeItem(getMenuStorageKey());
      menuItems.value = [...defaultMenuItems];
      message.success('已恢复出厂默认菜单排序');
      nextTick(() => {
        initSidebarSortable();
      });
    }
  });
};

const sidebarMenuWrapperRef = ref(null);
let sidebarSortableInstance = null;

const initSidebarSortable = () => {
  if (!sidebarMenuWrapperRef.value) return;
  const menuEl = sidebarMenuWrapperRef.value.querySelector('.ant-menu') || sidebarMenuWrapperRef.value;
  if (!menuEl) return;

  if (sidebarSortableInstance) {
    sidebarSortableInstance.destroy();
    sidebarSortableInstance = null;
  }

  sidebarSortableInstance = new Sortable(menuEl, {
    animation: 150,
    draggable: '.ant-menu-item',
    handle: '.sidebar-menu-drag-handle',
    ghostClass: 'sidebar-menu-ghost',
    chosenClass: 'sidebar-menu-chosen',
    dragClass: 'sidebar-menu-active',
    filter: '.ant-menu-item-disabled',
    preventOnFilter: false,
    disabled: !!collapsed.value,
    onEnd: (evt) => {
      const { oldIndex, newIndex, item, from } = evt;
      if (oldIndex === newIndex || oldIndex == null || newIndex == null) return;

      // 核心加固：撤销 Sortable 的物理 DOM 变更，使真实 DOM 树与 Vue 虚拟 DOM 现有状态对齐
      if (from && item && item.parentNode === from) {
        from.removeChild(item);
        if (oldIndex >= from.children.length) {
          from.appendChild(item);
        } else {
          from.insertBefore(item, from.children[oldIndex]);
        }
      }

      // 由 Vue 3 响应式系统独占安全接管真实的 DOM 树重排与 Diff
      const movedItem = menuItems.value.splice(oldIndex, 1)[0];
      menuItems.value.splice(newIndex, 0, movedItem);

      saveMenuOrder();
    }
  });
};

watch(collapsed, (newVal) => {
  if (sidebarSortableInstance) {
    sidebarSortableInstance.option('disabled', !!newVal);
  }
  if (!newVal) {
    nextTick(() => {
      initSidebarSortable();
    });
  }
});

const updateTime = () => {
  const now = new Date();
  const hours = now.getHours().toString().padStart(2, '0');
  const mins = now.getMinutes().toString().padStart(2, '0');
  currentTime.value = `${hours}:${mins}`;
};

const toggleUI = (e) => {
  if (!hasBgImage.value) return;
  e.stopPropagation();
  isUIHidden.value = !isUIHidden.value;
  if (isUIHidden.value) {
    document.body.classList.add('ui-hidden');
  } else {
    document.body.classList.remove('ui-hidden');
  }
};

const restoreUI = () => {
  if (isUIHidden.value) {
    isUIHidden.value = false;
    document.body.classList.remove('ui-hidden');
  }
};

const toggleDarkMode = (checked) => {
  isDarkMode.value = checked;
  localStorage.setItem('darkMode', checked ? 'true' : 'false');
  window.dispatchEvent(new CustomEvent('dark-mode-changed', { detail: checked }));
};

const handleThemeChange = async (e) => {
  const color = e.key;
  localStorage.setItem('themeColor', color);
  await dbHelper.remove('bgImage'); // 恢复纯色主题时移除背景图片
  hasBgImage.value = false;
  window.dispatchEvent(new CustomEvent('theme-changed', { detail: color }));
  window.dispatchEvent(new CustomEvent('bg-image-changed', { detail: '' }));
  message.success('主题色已切换');
};

const handleUploadBackground = async (file) => {
  if (file.size > 25 * 1024 * 1024) {
    message.warning('图片大小不能超过 25MB，请重新选择');
    return false;
  }
  const hide = message.loading('正在提取主题色并设置高清背景...', 0);
  try {
    const base64 = await processImageToBase64(file);
    const color = await extractDominantColor(base64);

    localStorage.setItem('themeColor', color);
    await dbHelper.set('bgImage', base64);

    window.dispatchEvent(new CustomEvent('theme-changed', { detail: color }));
    window.dispatchEvent(new CustomEvent('bg-image-changed', { detail: base64 }));

    message.success('自定义高清主题背景设置成功！');
  } catch (e) {
    message.error('提取颜色或设置失败：' + (e.message || '未知错误'));
  } finally {
    hide();
  }
  return false; // 拦截默认上传行为
};

const handleBgImageEvent = (e) => {
  hasBgImage.value = !!e.detail;
};

onMounted(() => {
  const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
  if (userInfo.username) {
    currentUsername.value = userInfo.username;
    menuItems.value = loadOrderedMenuItems();
  }
  nextTick(() => {
    initSidebarSortable();
  });

  if (route.path.includes('/GitHubTasks/')) {
    selectedKeys.value = ['/GitHubTasks/GitHubTasksList'];
  }

  const savedDarkMode = localStorage.getItem('darkMode');
  if (savedDarkMode === 'true') {
    isDarkMode.value = true;
  }

  const urlParams = new URLSearchParams(window.location.search);
  const hashParams = new URLSearchParams(window.location.hash.includes('?') ? window.location.hash.split('?')[1] : '');
  const shouldResetBg = urlParams.get('reset_bg') === '1' || hashParams.get('reset_bg') === '1';

  if (shouldResetBg) {
    hasBgImage.value = false;
  } else {
    dbHelper.get('bgImage').then((bgImage) => {
      if (bgImage) {
        hasBgImage.value = true;
      }
    }).catch(() => {});
  }

  window.addEventListener('bg-image-changed', handleBgImageEvent);
  document.addEventListener('click', restoreUI);

  // fetchBasicAuthStatus();

  updateTime();
  timeInterval = setInterval(updateTime, 1000);
});

onUnmounted(() => {
  window.removeEventListener('bg-image-changed', handleBgImageEvent);
  document.removeEventListener('click', restoreUI);
  if (timeInterval) clearInterval(timeInterval);
  if (sidebarSortableInstance) {
    sidebarSortableInstance.destroy();
    sidebarSortableInstance = null;
  }
});

// 帮助函数：将任意子路径或详情页映射至左侧菜单项的 key
const getMenuKeyForPath = (path) => {
  if (!path) return '/dashboard';
  if (path.startsWith('/taskList')) return '/taskList';
  if (path.startsWith('/group') || path.startsWith('/groupAssetsManagement')) return '/group';
  if (path.startsWith('/policy')) return '/policy';
  if (path.startsWith('/GitHub')) return '/GitHubTasks/GitHubTasksList';
  // ★ 漏洞平台路径映射
  if (path.startsWith('/platform/projects')) return '/platform/dashboard';
  if (path.startsWith('/platform/')) return path;
  return path;
};

// 记录各业务模块最后访问的完整路由（含 query 参数与详情页路径）
const moduleLastPathMap = reactive({
  '/group': '/group',
  '/taskList': '/taskList',
  '/policy': '/policy',
  '/GitHubTasks/GitHubTasksList': '/GitHubTasks/GitHubTasksList'
});

// 在路由变化时，动态记录各模块最后访问的 fullPath
watch(() => route.fullPath, (newFullPath) => {
  const currentPath = route.path;
  const menuKey = getMenuKeyForPath(currentPath);
  if (menuKey && moduleLastPathMap[menuKey] !== undefined) {
    moduleLastPathMap[menuKey] = newFullPath;
  }
}, { immediate: true });

const handleMenuClick = (e) => {
  const targetMenuKey = e.key;
  const currentMenuKey = getMenuKeyForPath(route.path);

  // 如果用户当前已经在该模块的二级/详情页中，再次点击该模块的左侧菜单，视为希望返回一级大盘列表
  if (currentMenuKey === targetMenuKey) {
    if (route.path !== targetMenuKey) {
      moduleLastPathMap[targetMenuKey] = targetMenuKey;
      router.push(targetMenuKey);
    }
    return;
  }

  // 从其他模块切回该模块：若之前访问过详情页或子路径，直接恢复到上次停留的完整路由
  const savedPath = moduleLastPathMap[targetMenuKey];
  if (savedPath && savedPath !== targetMenuKey) {
    router.push(savedPath);
  } else {
    router.push(targetMenuKey);
  }
};

const handleLogout = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('userInfo');
  router.push('/login');
};

// 记录各路由对应的滚动容器偏移量
const scrollPositions = new Map();
let prevPath = '';

// 监听路由变化，保持左侧菜单高亮的一致性并记忆还原滚动条位置
watch(() => route.path, (newPath) => {
  const mainContent = document.querySelector('.arl-main-content');
  if (mainContent && prevPath) {
    scrollPositions.set(prevPath, mainContent.scrollTop);
  }
  prevPath = newPath;

  nextTick(() => {
    requestAnimationFrame(() => {
      const el = document.querySelector('.arl-main-content');
      if (el) {
        const savedScroll = scrollPositions.get(newPath);
        if (savedScroll !== undefined) {
          el.scrollTop = savedScroll;
        } else {
          el.scrollTop = 0;
        }
      }
    });
  });

  // 映射对应的菜单高亮
  const activeMenuKey = getMenuKeyForPath(newPath);
  selectedKeys.value = [activeMenuKey];
}, { immediate: true });

// 动态计算页面标题
const currentPageTitle = computed(() => {
  if (route.path.includes('taskDetail')) return '任务详情';
  if (route.path.includes('groupAssetsDetail')) return '资产分组详情';
  if (route.path.includes('GitHubTasksInfo')) return 'GitHub 任务详情';
  if (route.path.includes('GitHubMonitorInfo')) return 'GitHub 监控详情';
  if (route.path.includes('policyDetail')) return '策略配置详情';
  // ★ 漏洞平台项目详情页标题
  if (route.path.startsWith('/platform/projects/')) return '项目详情';

  const titleMap = {
    '/dashboard': '仪表盘',
    '/group': '资产分组',
    '/taskList': '任务管理',
    '/asset-search': '资产搜索',
    '/assetsMonitor': '资产监控',
    '/planningTasks': '计划任务',
    '/GitHubTasks/GitHubTasksList': 'GitHub监控',
    '/policy': '策略配置',
    '/pocList': 'POC管理',
    '/fingerprint': '指纹管理',
    // ★ 漏洞平台标题映射
    '/platform/dashboard': '项目看板',
    '/platform/platforms': '平台管理',
    '/platform/records': '提交记录',
    '/platform/schedules': '调度配置',
    '/systemSettings': '系统设置',
  };
  return titleMap[route.path] || 'ARL-Next';
});

/* ---------- 修改密码逻辑 ---------- */
const showChangePassModal = ref(false);
const isSubmitting = ref(false);
const passFormRef = ref();

const passForm = reactive({
  old_password: '',
  new_password: '',
  check_password: ''
});

const validateCheckPassword = async (_rule, value) => {
  if (value === '') {
    return Promise.reject('请再次输入确认密码');
  } else if (value !== passForm.new_password) {
    return Promise.reject('两次输入的新密码不一致!');
  } else {
    return Promise.resolve();
  }
};

const passRules = {
  old_password: [{ required: true, message: '旧密码不能为空', trigger: 'blur' }],
  new_password: [{ required: true, message: '新密码不能为空', trigger: 'blur' }],
  check_password: [{ required: true, validator: validateCheckPassword, trigger: 'blur' }]
};

const handleChangePass = async () => {
  try {
    await passFormRef.value.validate();
    isSubmitting.value = true;

    const res = await request.post('/user/change_pass', passForm);

    if (res.code === 200) {
      message.success('密码修改成功，请重新登录');
      showChangePassModal.value = false;
      passFormRef.value.resetFields();
      handleLogout();
    } else {
      message.error(res.message || '修改失败');
    }
  } catch (error) {
    console.error('表单校验失败或网络错误:', error);
  } finally {
    isSubmitting.value = false;
  }
};

const handleCancelChangePass = () => {
  passFormRef.value?.resetFields();
};

/* ---------- MCP 接入逻辑 ---------- */
const showMcpModal = ref(false);
const mcpConfigJson = ref('');
const isDownloadingScript = ref(false);

const handleShowMcpModal = () => {
  const config = {
    "arl-next": {
      "command": "python3",
      "args": [
        "~/Downloads/arl_mcp.py"
      ]
    }
  };
  const jsonStr = JSON.stringify(config, null, 2);
  mcpConfigJson.value = jsonStr.substring(2, jsonStr.length - 2).trim();
  showMcpModal.value = true;
};

const copyMcpConfig = async () => {
  const ok = await copyText(mcpConfigJson.value);
  if (ok) {
    message.success('MCP 配置已复制到剪贴板！');
  } else {
    message.error('复制失败，请手动选择复制');
  }
};

const downloadMcpScript = async () => {
  try {
    isDownloadingScript.value = true;
    const token = localStorage.getItem('token') || '';
    let scriptText = '';

    const host = window.location.origin;

    try {
      const res = await fetch(`/api/mcp/export_server?host=${encodeURIComponent(host)}`, {
        method: 'GET',
        headers: {
          'Token': token
        }
      });
      if (res.ok) {
        scriptText = await res.text();
      }
    } catch (e) {
      console.warn('后端导出接口调用失败，尝试静态降级生成:', e);
    }

    if (!scriptText || scriptText.startsWith('{"code":')) {
      const staticRes = await fetch('/mcp/server.py');
      if (!staticRes.ok) {
        throw new Error('获取客户端模板失败');
      }
      let content = await staticRes.text();
      const host = window.location.origin;
      if (token) {
        content = content.replace('DEFAULT_TOKEN = ""', `DEFAULT_TOKEN = "${token}"`);
      }
      if (host) {
        content = content.replace('DEFAULT_HOST = ""', `DEFAULT_HOST = "${host}"`);
      }
      scriptText = content;
    }

    const blob = new Blob([scriptText], { type: 'text/x-python;charset=utf-8' });
    const blobUrl = window.URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = blobUrl;
    link.download = 'arl_mcp.py';
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    window.URL.revokeObjectURL(blobUrl);
    message.success('arl_mcp.py 已成功导出并开始下载！');
  } catch (error) {
    console.error('下载 MCP 客户端脚本失败:', error);
    message.error('下载脚本失败，请检查网络');
  } finally {
    isDownloadingScript.value = false;
  }
};

const isRefreshingToken = ref(false);
const refreshMcpToken = async () => {
  try {
    isRefreshingToken.value = true;
    const res = await request.post('/user/refresh_token');
    if (res.code === 200 && res.data && res.data.token) {
      localStorage.setItem('token', res.data.token);
      message.success('Token 已作废并刷新成功！请重新下载客户端脚本。');
      handleShowMcpModal();
    } else {
      message.error(res.message || '刷新 Token 失败');
    }
  } catch (error) {
    message.error('刷新 Token 失败，请检查网络');
  } finally {
    isRefreshingToken.value = false;
  }
};

/* ---------- Basic Auth 管理逻辑 ---------- */
const showBasicAuthModal = ref(false);
const basicAuthFormRef = ref();
const basicAuthForm = reactive({
  username: 'admin',
  password: 'arl_next'
});

const basicAuthRules = {
  username: [{ required: true, message: '请输入 Basic Auth 账号', trigger: 'blur' }]
};

const resetBasicAuthDefaults = () => {
  basicAuthForm.username = 'admin';
  basicAuthForm.password = 'arl_next';
};

const fetchBasicAuthStatus = async () => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 6000);
  try {
    const res = await fetch('/update_stream/auth_status', { signal: controller.signal });
    if (res.ok) {
      const data = await res.json();
      if (data.status === 'ok') {
        isBasicAuthEnabled.value = data.enabled;
        isBasicAuthOnline.value = true;
        return;
      }
    }
    isBasicAuthOnline.value = false;
  } catch (error) {
    isBasicAuthOnline.value = false;
  } finally {
    clearTimeout(timeoutId);
  }
};

const handleBasicAuthSwitchClick = () => {
  if (isBasicAuthLoading.value || !isBasicAuthOnline.value) return;

  if (!isBasicAuthEnabled.value) {
    showBasicAuthModal.value = true;
  } else {
    Modal.confirm({
      title: '关闭 Nginx Basic Auth 前置安全防护',
      icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
      width: 480,
      content: createVNode('div', { style: 'margin-top: 12px; line-height: 1.6;' }, [
        createVNode('p', { style: 'margin-bottom: 8px; color: #ff4d4f;' }, '关闭后，Web 前端网关将直接对网络环境暴露（仅保留系统应用层登录鉴权）。'),
        createVNode('p', { style: 'margin-bottom: 0;' }, '确定要关闭 Basic Auth 防护吗？')
      ]),
      okText: '确认关闭',
      okButtonProps: { danger: true },
      cancelText: '取消',
      onOk: () => executeToggleBasicAuth(false)
    });
  }
};

const handleConfirmEnableBasicAuth = async () => {
  try {
    await basicAuthFormRef.value?.validate();
    await executeToggleBasicAuth(true, basicAuthForm.username, basicAuthForm.password);
    showBasicAuthModal.value = false;
  } catch (e) {
    console.error('Basic Auth 表单校验失败:', e);
  }
};

const executeToggleBasicAuth = async (checked, username = null, password = null) => {
  if (isBasicAuthLoading.value) return;
  isBasicAuthLoading.value = true;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 12000);

  try {
    const tokenRes = await request.post('/system_config/request_update_token');
    if (tokenRes.code === 200 && tokenRes.data && tokenRes.data.token) {
      const token = tokenRes.data.token;

      const payload = {
        token,
        enable: checked,
        username: username || undefined,
        password: password || undefined
      };

      const toggleRes = await fetch('/update_stream/toggle_auth', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-Update-Token': token
        },
        body: JSON.stringify(payload),
        signal: controller.signal
      });

      if (toggleRes.ok) {
        const data = await toggleRes.json();
        if (data.status === 'ok') {
          isBasicAuthEnabled.value = checked;
          if (checked) {
            message.success({
              content: `Basic Auth 防护已开启！(账号: ${username || 'admin'}，建议使用无痕窗口验证拦截效果)`,
              duration: 6
            });
          } else {
            message.success('Basic Auth 前置防护已成功关闭！');
          }
        } else {
          message.error('切换失败: ' + (data.message || '未知错误'));
        }
      } else {
        message.error('调用底层切换接口失败，请检查更新服务状态');
      }
    } else {
      message.error(tokenRes.message || '获取授权 Token 失败');
    }
  } catch (error) {
    if (error.name === 'AbortError') {
      message.error('请求超时，请检查 updater 更新服务是否正常运行');
    } else {
      console.error(error);
      message.error('操作失败，请检查网络或控制台日志');
    }
  } finally {
    clearTimeout(timeoutId);
    isBasicAuthLoading.value = false;
  }
};
</script>

<style scoped>
.header-icon-action {
  color: var(--arl-text-color);
  transition: color 0.3s;
}
.header-icon-action:hover {
  color: var(--arl-theme-color);
}
.header-text-action {
  color: var(--arl-text-color);
  transition: color 0.3s;
}
.header-text-action:hover {
  color: var(--arl-theme-color);
}
.header-icon-danger {
  color: var(--arl-text-color);
  transition: color 0.3s;
}
.header-icon-danger:hover {
  color: #ff4d4f;
}

/* 屏幕保护叠加层 */
.screensaver-overlay {
  position: fixed;
  top: 0; left: 0; right: 0; bottom: 0;
  pointer-events: none;
  z-index: 99;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.8s ease-in-out;
}
.screensaver-overlay.is-active {
  opacity: 1;
}
.screensaver-content {
  text-align: center;
  color: rgba(255, 255, 255, 0.9);
  text-shadow: 0 2px 10px rgba(0,0,0,0.5);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
}
.screensaver-time {
  font-size: 72px;
  font-weight: 200;
  letter-spacing: 4px;
  margin-bottom: 8px;
}
.screensaver-brand {
  font-size: 24px;
  font-weight: 500;
  letter-spacing: 8px;
  text-transform: uppercase;
  margin-bottom: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
}
.screensaver-icon {
  font-size: 28px;
  color: var(--arl-theme-color);
  animation: pulse-ring 2s infinite;
}
.screensaver-tip {
  font-size: 14px;
  opacity: 0.6;
  letter-spacing: 2px;
}
@keyframes pulse-ring {
  0% { transform: scale(1); opacity: 0.8; }
  50% { transform: scale(1.1); opacity: 1; text-shadow: 0 0 15px var(--arl-theme-color); }
  100% { transform: scale(1); opacity: 0.8; }
}

/* 支持作者 Popover 弹窗深度美化与暗黑模式自适应 */
.support-author-popover-overlay .ant-popover-inner {
  padding: 0 !important;
  border-radius: 12px !important;
  overflow: hidden !important;
  box-shadow: 0 10px 32px rgba(0, 0, 0, 0.22) !important;
}
body.dark-mode .support-author-popover-overlay .ant-popover-inner {
  background: rgba(15, 23, 42, 0.96) !important;
  border: 1px solid #1e293b !important;
  backdrop-filter: blur(16px) !important;
}

/* 侧边栏菜单拖拽重排与自适应动效 */
.sidebar-menu-wrapper {
  overflow-y: auto;
  overflow-x: hidden;
  max-height: calc(100vh - 64px);
}

.sidebar-menu-wrapper::-webkit-scrollbar {
  width: 3px;
}

.sidebar-menu-wrapper::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.15);
  border-radius: 2px;
}

.sidebar-menu-wrapper::-webkit-scrollbar-track {
  background: transparent;
}

.sidebar-sortable-menu-item {
  position: relative !important;
  user-select: none !important;
  transition: background-color 0.2s ease, border-color 0.2s ease, transform 0.15s ease !important;
}

.sidebar-sortable-menu-item :deep(.ant-menu-title-content) {
  display: flex !important;
  align-items: center !important;
  justify-content: space-between !important;
  width: 100% !important;
  padding-right: 2px !important;
}

.sidebar-menu-title-text {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 微动抓手图标 */
.sidebar-menu-drag-handle {
  cursor: grab;
  color: rgba(255, 255, 255, 0.35);
  opacity: 0;
  transition: opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1), color 0.2s ease, background-color 0.2s ease;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 22px;
  font-size: 13px;
  border-radius: 4px;
  flex-shrink: 0;
  margin-left: 4px;
  user-select: none;
}

.sidebar-sortable-menu-item:hover .sidebar-menu-drag-handle {
  opacity: 0.8;
  color: var(--arl-theme-color);
}

.sidebar-menu-drag-handle:hover {
  opacity: 1 !important;
  color: var(--arl-theme-color) !important;
  background: rgba(255, 255, 255, 0.12);
}

.sidebar-menu-drag-handle:active {
  cursor: grabbing;
}

/* Sortable 正在被拖动的元素浮动预览状态 (Drag Class) */
.sidebar-menu-active {
  opacity: 0.96 !important;
  background: #1e293b !important;
  box-shadow: 0 10px 24px rgba(0, 0, 0, 0.35), 0 0 0 1px var(--arl-theme-color) !important;
  border-radius: 6px !important;
  transform: scale(1.02);
  z-index: 1000 !important;
  cursor: grabbing !important;
}

/* 目标位置的幽灵占位符状态 (Ghost Class) */
.sidebar-menu-ghost {
  opacity: 0.45 !important;
  background: rgba(255, 255, 255, 0.05) !important;
  border: 1px dashed var(--arl-theme-color) !important;
  border-radius: 6px !important;
  box-shadow: inset 0 0 8px rgba(0, 0, 0, 0.2) !important;
}

/* 选中但未开始移动状态 (Chosen Class) */
.sidebar-menu-chosen {
  cursor: grabbing !important;
}
</style>