<template>
  <a-layout :style="{ height: '100vh', background: 'transparent' }">
    <a-layout-sider v-model:collapsed="collapsed" collapsible :trigger="null" :width="locale !== 'zh-CN' ? 240 : 170" :style="{ background: hasBgImage ? (isUIHidden ? 'transparent' : 'rgba(11, 17, 32, 0.6)') : '#0b1120', borderRight: isUIHidden ? 'none' : (isDarkMode ? '1px solid #1e293b' : 'none'), transition: 'all 0.5s' }">
      <div class="logo-container" @click="toggleUI" :title="t('layout.toggleInterface')" style="height: 64px; display: flex; align-items: center; justify-content: center; cursor: pointer; z-index: 999; position: relative;" :style="{ background: hasBgImage ? 'transparent' : '#0b1120', borderBottom: isDarkMode ? '1px solid #1e293b' : 'none' }">
        <DeploymentUnitOutlined class="logo-icon" :style="{ color: 'var(--arl-theme-color)', fontSize: '20px' }" />
        <span class="logo-text" v-show="!collapsed" style="color: #f1f5f9; font-size: 16px; margin-left: 8px; font-weight: 500;">ARL-Next</span>
      </div>

      <div ref="sidebarMenuWrapperRef" class="sidebar-menu-wrapper" :style="{ opacity: isUIHidden ? 0 : 1, pointerEvents: isUIHidden ? 'none' : 'auto', transition: 'opacity 0.5s' }">
        <a-menu v-model:selectedKeys="selectedKeys" theme="dark" mode="inline" @click="handleMenuClick">
          <a-menu-item
            v-for="item in menuItems"
            :key="item.key"
            :data-key="item.key"
            :title="collapsed ? t(item.titleKey) : null"
            class="sidebar-sortable-menu-item"
          >
            <template #icon>
              <component :is="item.icon" />
            </template>
            <span
              class="sidebar-menu-title-text"
              @mouseenter="handleMenuTextHover($event, t(item.titleKey))"
            >{{ t(item.titleKey) }}</span>
            <span
              v-if="!collapsed"
              class="sidebar-menu-drag-handle"
              @click.stop
              :title="t('layout.sortMenu')"
            >
              <HolderOutlined />
            </span>
          </a-menu-item>
        </a-menu>
      </div>
    </a-layout-sider>

    <a-layout :style="{ background: 'transparent', opacity: isUIHidden ? 0 : 1, pointerEvents: isUIHidden ? 'none' : 'auto', transition: 'opacity 0.5s', overflow: 'hidden' }">
      <a-layout-header class="arl-header" :style="{ background: isDarkMode ? 'rgba(15, 23, 42, 0.75)' : 'rgba(255, 255, 255, 0.75)', borderBottom: '1px solid ' + (isDarkMode ? '#1e293b' : '#e2e8f0') }">
        <div style="display: flex; align-items: center;">
          <span class="trigger" @click="() => (collapsed = !collapsed)" style="font-size: 18px; cursor: pointer; margin-right: 24px;">
            <menu-unfold-outlined v-if="collapsed" /><menu-fold-outlined v-else />
          </span>
          <span :style="{ fontSize: '16px', fontWeight: 500, color: isDarkMode ? 'rgba(255,255,255,.85)' : 'var(--arl-text-color)' }">{{ currentPageTitle }}</span>
        </div>

        <div class="header-actions">
          <LanguageSwitcher class="header-language-switcher" />
          <SupportAuthorPopover />

          <a-dropdown>
            <span class="header-text-action" style="cursor: pointer; margin-right: 24px; display: flex; align-items: center;">
              <BgColorsOutlined style="font-size: 16px; margin-right: 4px;" />
              {{ t('layout.theme') }}
            </span>
            <template #overlay>
              <a-menu @click="handleThemeChange">
                <a-menu-item key="#00bcd4">
                  <span class="theme-swatch theme-cyan"></span>{{ t('layout.cyan') }}
                </a-menu-item>
                <a-menu-item key="#1890ff">
                  <span class="theme-swatch theme-blue"></span>{{ t('layout.blue') }}
                </a-menu-item>
                <a-menu-item key="#52c41a">
                  <span class="theme-swatch theme-green"></span>{{ t('layout.green') }}
                </a-menu-item>
                <a-menu-item key="#fa541c">
                  <span class="theme-swatch theme-orange"></span>{{ t('layout.orange') }}
                </a-menu-item>
                <a-menu-item key="#eb2f96">
                  <span class="theme-swatch theme-pink"></span>{{ t('layout.pink') }}
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>

          <a-upload :show-upload-list="false" :before-upload="handleUploadBackground" accept="image/*">
            <span class="header-text-action" style="cursor: pointer; margin-right: 24px; display: flex; align-items: center;">
              <PictureOutlined style="font-size: 16px; margin-right: 4px;" />
              {{ t('layout.background') }}
            </span>
          </a-upload>

          <div class="header-switch" :title="t('layout.darkMode')">
            <a-switch checked-children="🌙" un-checked-children="☀️" v-model:checked="isDarkMode" @change="toggleDarkMode" />
          </div>

          <div class="header-switch" :title="isBasicAuthOnline ? (isBasicAuthEnabled ? t('layout.basicAuthEnabled') : t('layout.basicAuthDisabled')) : t('layout.basicAuthOffline')">
            <a-switch :checked="isBasicAuthEnabled" :loading="isBasicAuthLoading" :disabled="!isBasicAuthOnline" @click="handleBasicAuthSwitchClick" checked-children="🔒" un-checked-children="🔓" />
          </div>

          <span class="header-text-action" style="cursor: pointer; margin-right: 24px; display: flex; align-items: center;" @click="handleShowMcpModal">
            <RobotOutlined style="font-size: 16px; margin-right: 4px;" />
            {{ t('layout.mcp') }}
          </span>
          
          <a-dropdown>
            <span class="header-text-action header-user-settings" :title="t('layout.userSettings')">
              <a-avatar style="background-color: #87d068; margin-right: 8px;" size="small"><template #icon><UserOutlined /></template></a-avatar>
              <span>{{ currentUsername }}</span>
              <DownOutlined style="font-size: 10px; margin-left: 6px; opacity: 0.7;" />
            </span>
            <template #overlay>
              <a-menu>
                <a-menu-item key="changePass" @click="showChangePassModal = true">
                  <KeyOutlined class="user-menu-icon" />{{ t('account.changePassword') }}
                </a-menu-item>
                <a-menu-item key="resetMenuOrder" @click="handleResetMenuOrder">
                  <ReloadOutlined class="user-menu-icon" />{{ t('layout.resetMenu') }}
                </a-menu-item>
                <a-menu-divider />
                <a-menu-item key="logout" @click="handleLogout" style="color: #ff4d4f;">
                  <LogoutOutlined class="user-menu-icon" />{{ t('layout.signOut') }}
                </a-menu-item>
              </a-menu>
            </template>
          </a-dropdown>
          
          <span class="header-text-action header-change-password" @click="showChangePassModal = true">{{ t('account.changePassword') }}</span>
          
          <a-tooltip :title="t('layout.signOut')" placement="bottom">
            <span class="header-icon-action header-icon-danger" style="cursor: pointer;" @click="handleLogout">
              <LogoutOutlined style="font-size: 16px;" />
            </span>
          </a-tooltip>
        </div>
      </a-layout-header>

      <a-layout-content class="arl-main-content" style="margin: 16px; display: flex; flex-direction: column; overflow-y: auto; height: 0;">
        <div :style="{ background: hasBgImage ? (isDarkMode ? 'rgba(15, 23, 42, 0.5)' : 'rgba(255, 255, 255, 0.4)') : (isDarkMode ? '#0f172a' : 'transparent'), flex: '1 0 auto', display: 'flex', flexDirection: 'column', borderRadius: '4px' }">
          <router-view v-slot="{ Component }">
            <keep-alive include="Dashboard,TaskList,TaskDetail,AssetScope,GroupAssetsDetail,AssetSearch,PlanningTasks,GithubManage,PocList,Fingerprint,Policy,SystemSettings">
              <component :is="Component" />
            </keep-alive>
          </router-view>
        </div>
        <div :style="{ textAlign: 'center', padding: '16px 0', color: isDarkMode ? 'rgba(255,255,255,.45)' : 'rgba(0,0,0,.45)', fontSize: '12px' }">
          {{ pageText('pages.poweredByArlNext') }}
        </div>
      </a-layout-content>
    </a-layout>
  </a-layout>
  <a-modal
      v-model:visible="showMcpModal"
      :title="pageText('pages.aiAssistantMcpClientConfiguration')"
      @cancel="showMcpModal = false"
      :footer="null"
      width="680px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
  >
    <!-- 模式切换 -->
    <div style="margin-bottom: 16px; display: flex; justify-content: center;">
      <a-radio-group v-model:value="mcpMode" button-style="solid" @change="updateMcpConfigJson">
        <a-radio-button value="sse">{{ pageText('pages.mcpModeRemoteSse') }}</a-radio-button>
        <a-radio-button value="stdio">{{ pageText('pages.mcpModeLocalStdio') }}</a-radio-button>
      </a-radio-group>
    </div>

    <!-- 远程直连模式在 IP / 自签环境下的友好告警 -->
    <div v-if="mcpMode === 'sse' && isIpAccess" style="margin-bottom: 14px;">
      <a-alert
        type="warning"
        show-icon
        :message="pageText('pages.mcpSseIpWarningTitle')"
      >
        <template #description>
          <div style="margin-top: 4px;">
            <div style="line-height: 1.5;">{{ pageText('pages.mcpSseIpWarningDesc') }}</div>
            <div style="margin-top: 8px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap;">
              <a-button size="small" type="primary" ghost @click="switchToStdioMode">
                {{ pageText('pages.mcpSwitchToStdio') }}
              </a-button>
              <a-button size="small" type="link" style="padding: 0;" @click="showCertGuide = !showCertGuide">
                {{ showCertGuide ? pageText('pages.mcpHideCertGuide') : pageText('pages.mcpShowCertGuide') }}
              </a-button>
            </div>
            <div v-if="showCertGuide" :style="{ marginTop: '10px', padding: '10px 12px', background: hasBgImage ? 'rgba(0,0,0,0.2)' : 'var(--arl-bg-light, rgba(0,0,0,0.03))', border: hasBgImage ? '1px solid rgba(255,255,255,0.08)' : '1px solid var(--arl-border-color, rgba(0,0,0,0.06))', borderRadius: '6px', fontSize: '12px', lineHeight: '1.6' }">
              <div style="margin-bottom: 6px;">{{ pageText('pages.mcpCertGuideStep1') }}</div>
              <div>{{ pageText('pages.mcpCertGuideStep2') }}</div>
            </div>
          </div>
        </template>
      </a-alert>
    </div>

    <!-- 模式 1: 远程直连说明 -->
    <div v-if="mcpMode === 'sse'" style="margin-bottom: 10px;">
      <p class="page-section-gap">{{ pageText('pages.mcpSseStepDesc') }}</p>
    </div>

    <!-- 模式 2: 本地脚本导出步骤 -->
    <div v-else style="margin-bottom: 16px;">
      <p class="page-section-gap">{{ pageText('pages.connectAiAssistantsSuchAsCcSwitchClaudeCode') }}</p>
      <div :style="{ background: hasBgImage ? 'rgba(0,0,0,0.15)' : 'var(--arl-bg-light)', border: hasBgImage ? '1px solid rgba(255,255,255,0.1)' : '1px solid var(--arl-border-color)', borderRadius: '6px', padding: '12px 14px', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }">
        <div>
          <div class="page-section-heading">{{ pageText('pages.step1ExportYourClientScript') }}</div>
          <div class="page-muted-note">{{ pageText('pages.theScriptIncludesYourAccountTokenAndServerUrl') }}</div>
        </div>
        <a-button type="primary" :loading="isDownloadingScript" @click="downloadMcpScript">
          {{ pageText('pages.downloadArlMcpPy') }}
        </a-button>
      </div>
      <div style="margin-top: 14px; margin-bottom: 8px; font-size: 13px; font-weight: 500;">
        {{ pageText('pages.step2CopyTheConfigurationIntoYourClient') }} <code>"mcpServers"</code> {{ pageText('pages.node') }}
      </div>
    </div>

    <div style="position: relative;">
      <pre :style="{ background: hasBgImage ? 'rgba(0,0,0,0.2)' : 'var(--arl-bg-light)', padding: '16px', borderRadius: '6px', overflowX: 'auto', fontSize: '13px', border: hasBgImage ? '1px solid rgba(255,255,255,0.1)' : '1px solid var(--arl-border-color)', margin: 0 }"><code :style="{ color: hasBgImage ? 'var(--arl-text-color)' : 'inherit' }">{{ mcpConfigJson }}</code></pre>
      <div style="position: absolute; top: 12px; right: 12px; display: flex; gap: 8px;">
        <a-popconfirm
          :title="pageText('pages.refreshingImmediatelyInvalidatesTheCurrentTokenExportedScriptsAnd')"
          :okText="pageText('pages.confirmRefresh')"
          :cancelText="pageText('tasks.cancel')"
          @confirm="refreshMcpToken"
        >
          <a-button type="default" size="small" :loading="isRefreshingToken">{{ pageText('pages.refreshToken') }}</a-button>
        </a-popconfirm>
        <a-button type="primary" size="small" @click="copyMcpConfig">{{ pageText('pages.copyConfiguration') }}</a-button>
      </div>
    </div>

    <div style="margin-top: 14px; font-size: 12px; color: var(--arl-text-color); opacity: 0.75; line-height: 1.6;">
      <template v-if="mcpMode === 'stdio'">
        💡 <b>{{ pageText('pages.noEnvironmentSetupNeeded') }}</b>{{ pageText('pages.theScriptIncludesAccessCredentialsAndAssumesItIs') }} <code>~/Downloads/arl_mcp.py</code>{{ pageText('pages.ifItIsSavedElsewhereUpdate') }} <code>args</code> {{ pageText('pages.toTheActualAbsolutePathOnWindowsUse') }} <code>python</code> {{ pageText('pages.message') }}<br/>
      </template>
      🔒 <b>{{ pageText('pages.credentialSecurity') }}</b>{{ pageText('pages.theExportedScriptContainsAPrivilegedApiTokenFor') }}
      <div style="margin-top: 12px; display: flex; justify-content: space-between; align-items: center; border-top: 1px solid var(--arl-border-color); padding-top: 10px;">
        <a-button type="link" size="small" @click="goToMcpCenter" style="padding: 0; font-weight: 500;">
          <RobotOutlined style="margin-right: 4px;" />
          {{ pageText('pages.goToMcpCenter') }} →
        </a-button>
        <a href="https://github.com/owl234/ARL-Next/tree/main/mcp-server" target="_blank" rel="noopener noreferrer" style="font-size: 12px; color: var(--ant-primary-color, #1890ff);">
          📖 {{ pageText('pages.mcpDocGuide') }}
        </a>
      </div>
    </div>
  </a-modal>

  <a-modal
      v-model:visible="showChangePassModal"
      :title="t('account.changePassword')"
      @ok="handleChangePass"
      :confirmLoading="isSubmitting"
      @cancel="handleCancelChangePass"
      :okText="t('account.confirmChange')"
      :cancelText="t('common.cancel')"
  >
    <a-form :label-wrap="true" :model="passForm" :rules="passRules" ref="passFormRef" layout="vertical">
      <a-form-item :label="t('account.oldPassword')" name="old_password">
        <a-input-password v-model:value="passForm.old_password" :placeholder="t('account.oldPlaceholder')" />
      </a-form-item>
      <a-form-item :label="t('account.newPassword')" name="new_password">
        <a-input-password v-model:value="passForm.new_password" :placeholder="t('account.newPlaceholder')" />
      </a-form-item>
      <a-form-item :label="t('account.confirmPassword')" name="check_password">
        <a-input-password v-model:value="passForm.check_password" :placeholder="t('account.confirmPlaceholder')" />
      </a-form-item>
    </a-form>
  </a-modal>

  <!-- Basic Auth 配置与开启弹窗 -->
  <a-modal
    v-model:visible="showBasicAuthModal"
    :title="pageText('pages.enableNginxBasicAuthProtection')"
    :okText="pageText('pages.enableAndApply')"
    :cancelText="pageText('tasks.cancel')"
    :confirmLoading="isBasicAuthLoading"
    @ok="handleConfirmEnableBasicAuth"
    @cancel="showBasicAuthModal = false"
    width="520px"
    wrapClassName="arl-theme-modal"
    rootClassName="arl-theme-modal"
  >
    <div style="margin-bottom: 16px; font-size: 13px; line-height: 1.6; color: var(--arl-text-color);">
      <p class="page-form-spacing">{{ pageText('pages.basicAuthAddsAnHttpUsernameAndPasswordPrompt') }}</p>
    </div>

    <a-form :label-wrap="true" :model="basicAuthForm" :rules="basicAuthRules" ref="basicAuthFormRef" layout="vertical">
      <a-form-item :label="pageText('pages.basicAuthUsername')" name="username" :extra="pageText('pages.httpAuthenticationUsernameDefaultsToAdmin')">
        <a-input v-model:value="basicAuthForm.username" :placeholder="pageText('pages.enterAUsername')" />
      </a-form-item>
      <a-form-item :label="pageText('pages.basicAuthPassword')" name="password" :extra="pageText('pages.leaveBlankToKeepTheCurrentPasswordOrUse')">
        <a-input-password v-model:value="basicAuthForm.password" :placeholder="pageText('pages.leaveBlankForTheCurrentDefaultPasswordOrEnter')" />
      </a-form-item>
    </a-form>

    <div style="background: var(--arl-bg-light, rgba(0,0,0,0.03)); padding: 12px; border-radius: 6px; border: 1px solid var(--arl-border-color, rgba(255,255,255,0.08)); font-size: 12px; color: var(--arl-text-color); opacity: 0.85;">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
        <span class="page-theme-emphasis">{{ pageText('pages.quickPreset') }}</span>
        <a-button type="link" size="small" class="page-text-action" @click="resetBasicAuthDefaults">{{ pageText('pages.fillDefaultCredentialsAdminArlNext') }}</a-button>
      </div>
      <div>{{ pageText('pages.credentialsAreStoredPersistentlyInTheHostWorkingDirectory') }} <code>frontend/.htpasswd</code>。</div>
      <div class="page-validation-warning">• <b>{{ pageText('pages.verification') }}</b> {{ pageText('pages.browsersCacheBasicAuthCredentialsToCheckTheAuthentication') }}<b>{{ pageText('pages.aPrivateWindow') }}</b>{{ pageText('pages.messageLabel2') }}</div>
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
      <div class="screensaver-tip">{{ pageText('pages.screensaverResumeHint') }}</div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, watch, computed, onUnmounted, createVNode, nextTick } from 'vue';
import { useRoute, useRouter } from 'vue-router';
import { useI18n } from 'vue-i18n';
// 引入 request (根据你的实际路径调整)
import request from '@/utils/request';
// 引入主题提取工具和 IndexedDB
import { extractDominantColor, processImageToBase64, dbHelper } from '@/utils/theme';
// 引入 Ant Design 的消息提示与模态框
import { message, Modal } from 'ant-design-vue';
import SupportAuthorPopover from '@/components/SupportAuthorPopover.vue';
import { copyText } from '@/utils/clipboard';
import { createStdioServerConfig } from '@/utils/mcpCredentials';
import Sortable from 'sortablejs';
import LanguageSwitcher from '@/components/LanguageSwitcher.vue';

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
  ControlOutlined,
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
const { t, locale } = useI18n({ useScope: 'global' });
const pageText = t;
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
  { key: '/dashboard', titleKey: 'navigation.dashboard', icon: DashboardOutlined },
  { key: '/group', titleKey: 'navigation.assetGroups', icon: AppstoreOutlined },
  { key: '/taskList', titleKey: 'navigation.tasks', icon: GlobalOutlined },
  { key: '/asset-search', titleKey: 'navigation.assetSearch', icon: SearchOutlined },
  { key: '/planningTasks', titleKey: 'navigation.schedules', icon: ClockCircleOutlined },
  { key: '/GitHubTasks/GitHubTasksList', titleKey: 'navigation.github', icon: GithubOutlined },
  { key: '/pocList', titleKey: 'navigation.pocs', icon: BugOutlined },
  { key: '/fingerprint', titleKey: 'navigation.fingerprints', icon: TagsOutlined },
  { key: '/policy', titleKey: 'navigation.policies', icon: ControlOutlined },
  { key: '/mcpCenter', titleKey: 'navigation.mcpCenter', icon: RobotOutlined },
  { key: '/systemSettings', titleKey: 'navigation.settings', icon: SettingOutlined },
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

// 智能防截断 Tooltip：仅当菜单项文字发生溢出截断时动态设置原生 title
const handleMenuTextHover = (e, text) => {
  const el = e?.currentTarget;
  if (el) {
    el.title = el.scrollWidth > el.clientWidth ? text : '';
  }
};

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
    title: t('layout.resetMenu'),
    icon: createVNode(ExclamationCircleOutlined),
    content: t('layout.resetMenuConfirm'),
    okText: t('layout.resetMenuOk'),
    cancelText: t('common.cancel'),
    onOk: () => {
      localStorage.removeItem(getMenuStorageKey());
      menuItems.value = [...defaultMenuItems];
      message.success(t('layout.resetMenuSuccess'));
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

      // 核心加固：撤销 Sortable 的物理 DOM 变更，使真实 DOM 树与 Vue 虚拟 DOM 现有状态对齐，杜绝高亮项重复插入
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
  message.success(pageText('pages.themeColorChanged'));
};

const handleUploadBackground = async (file) => {
  if (file.size > 25 * 1024 * 1024) {
    message.warning(pageText('pages.imageMustBeNoLargerThan25Mb'));
    return false;
  }
  // 由于读取和提取可能较慢，可以给个 Loading 提示
  const hide = message.loading(pageText('pages.extractingTheThemeColorAndSettingTheBackground'), 0);
  try {
    const base64 = await processImageToBase64(file);
    const color = await extractDominantColor(base64);
    
    localStorage.setItem('themeColor', color);
    await dbHelper.set('bgImage', base64);
    
    window.dispatchEvent(new CustomEvent('theme-changed', { detail: color }));
    window.dispatchEvent(new CustomEvent('bg-image-changed', { detail: base64 }));
    
    message.success(pageText('pages.customBackgroundApplied'));
  } catch (e) {
    message.error(pageText('pages.failedToExtractColorOrApplySettings') + (e.message || pageText('tasks.unknownError')));
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

  fetchBasicAuthStatus();

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
  return path;
};

// 记录各业务模块最后访问的完整路由（含 query 参数与详情页路径）
const moduleLastPathMap = reactive({
  '/group': '/group',
  // 显式落地「企业测绘任务」页签，与页面内胶囊切换器的首项保持一致
  '/taskList': '/taskList?tab=enterprise',
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
  if (route.path.includes('taskDetail')) return t('navigation.taskDetail');
  if (route.path.includes('groupAssetsDetail')) return t('navigation.assetGroupDetail');
  if (route.path.includes('policyDetail')) return t('navigation.policyDetail');
  const titleMap = {
    '/dashboard': 'navigation.dashboard',
    '/group': 'navigation.assetGroups',
    '/taskList': 'navigation.tasks',
    '/asset-search': 'navigation.assetSearch',
    '/assetsMonitor': 'navigation.schedules',
    '/planningTasks': 'navigation.schedules',
    '/GitHubTasks/GitHubTasksList': 'navigation.github',
    '/policy': 'navigation.policies',
    '/pocList': 'navigation.pocs',
    '/fingerprint': 'navigation.fingerprints',
    '/mcpCenter': 'navigation.mcpCenter',
    '/systemSettings': 'navigation.settings',
  };
  return titleMap[route.path] ? t(titleMap[route.path]) : 'ARL-Next';
});
/* ---------- 新增：修改密码逻辑 ---------- */
const showChangePassModal = ref(false);
const isSubmitting = ref(false);
const passFormRef = ref();

// 表单数据绑定
const passForm = reactive({
  old_password: '',
  new_password: '',
  check_password: ''
});

// 自定义校验：确认密码必须和新密码一致
const validateCheckPassword = async (_rule, value) => {
  if (value === '') {
    return Promise.reject(t('account.confirmRequired'));
  } else if (value !== passForm.new_password) {
    return Promise.reject(t('account.mismatch'));
  } else {
    return Promise.resolve();
  }
};

// 表单校验规则
const passRules = computed(() => ({
  old_password: [{ required: true, message: t('account.oldRequired'), trigger: 'blur' }],
  new_password: [{ required: true, message: t('account.newRequired'), trigger: 'blur' },
    { min: 12, max: 1024, message: t('account.passwordLength'), trigger: 'blur' }],
  check_password: [{ required: true, validator: validateCheckPassword, trigger: 'blur' }]
}));

// 提交修改密码
const handleChangePass = async () => {
  try {
    // 1. 触发前端表单验证
    await passFormRef.value.validate();
    isSubmitting.value = true;

    // 2. 发送请求给后端（注意检查这里的 URL 是否需要加 /api 前缀，取决于你的 request.js baseURL 配置）
    const res = await request.post('/user/change_pass', passForm);

    // 3. 处理后端返回结果
    if (res.code === 200) {
      message.success(t('account.changed'));
      showChangePassModal.value = false;
      passFormRef.value.resetFields();
      handleLogout(); // 密码修改成功后调用已有的退出逻辑
    } else {
      // 捕获后端的 301, 302, 303 等错误
      message.error(res.message || t('account.failed'));
    }
  } catch (error) {
    console.error('表单校验失败或网络错误:', error);
  } finally {
    isSubmitting.value = false;
  }
};

// 取消弹窗时重置表单
const handleCancelChangePass = () => {
  passFormRef.value?.resetFields();
};

/* ---------- 新增：MCP 接入逻辑 ---------- */
const showMcpModal = ref(false);
const mcpMode = ref('sse');
const isIpAccess = ref(false);
const showCertGuide = ref(false);
const mcpConfigJson = ref('');
const isDownloadingScript = ref(false);

const switchToStdioMode = () => {
  mcpMode.value = 'stdio';
  updateMcpConfigJson();
};

const updateMcpConfigJson = () => {
  const token = localStorage.getItem('token') || '';
  const host = window.location.origin;

  if (mcpMode.value === 'sse') {
    const sseConfig = {
      "arl-next": {
        "url": `${host}/mcp/sse`,
        "headers": {
          "Authorization": `Bearer ${token}`
        }
      }
    };
    const jsonStr = JSON.stringify(sseConfig, null, 2);
    mcpConfigJson.value = jsonStr.substring(2, jsonStr.length - 2).trim();
  } else {
    const stdioConfig = {
      "arl-next": createStdioServerConfig()
    };
    const jsonStr = JSON.stringify(stdioConfig, null, 2);
    mcpConfigJson.value = jsonStr.substring(2, jsonStr.length - 2).trim();
  }
};

const goToMcpCenter = () => {
  showMcpModal.value = false;
  router.push('/mcpCenter');
};

const handleShowMcpModal = () => {
  const hostname = window.location.hostname;
  const isIp = /^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$/.test(hostname) || hostname === 'localhost' || hostname === '127.0.0.1';
  isIpAccess.value = isIp;
  mcpMode.value = isIp ? 'stdio' : 'sse';
  showCertGuide.value = false;
  updateMcpConfigJson();
  showMcpModal.value = true;
};

const copyMcpConfig = async () => {
  const ok = await copyText(mcpConfigJson.value);
  if (ok) {
    message.success(pageText('pages.mcpConfigurationCopiedToClipboard'));
  } else {
    message.error(pageText('pages.copyFailedSelectAndCopyTheTextManually'));
  }
};

const downloadMcpScript = async () => {
  try {
    isDownloadingScript.value = true;
    const token = localStorage.getItem('token') || '';
    let scriptText = '';

    const host = window.location.origin;

    // 优先从后端动态注入导出接口获取
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

    // 降级保护：若后端接口未就绪，直接拉取静态模版并在前端完成凭据注入
    if (!scriptText || scriptText.startsWith('{"code":')) {
      const staticRes = await fetch('/mcp/server.py');
      if (!staticRes.ok) {
        throw new Error(pageText('pages.failedToLoadClientScriptTemplate'));
      }
      let content = await staticRes.text();
      const host = window.location.origin;
      if (token) {
        content = content.replace('DEFAULT_TOKEN = ""', () => `DEFAULT_TOKEN = ${JSON.stringify(token)}`);
      }
      if (host) {
        content = content.replace('DEFAULT_HOST = ""', () => `DEFAULT_HOST = ${JSON.stringify(host)}`);
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
    message.success(pageText('pages.arlMcpPyExportedDownloadStarted'));
  } catch (error) {
    console.error('下载 MCP 客户端脚本失败:', error);
    message.error(pageText('pages.failedToDownloadScriptCheckTheNetworkConnection'));
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
      message.success(pageText('pages.tokenInvalidatedAndRefreshedDownloadANewClientScript'));
      updateMcpConfigJson(); // 重新生成配置展示
    } else {
      message.error(res.message || pageText('pages.failedToRefreshToken'));
    }
  } catch (error) {
    message.error(pageText('pages.failedToRefreshTokenCheckTheNetworkConnection'));
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
  username: [{ required: true, get message() { return pageText('pages.enterABasicAuthUsername'); }, trigger: 'blur' }]
};

const resetBasicAuthDefaults = () => {
  basicAuthForm.username = 'admin';
  basicAuthForm.password = 'arl_next';
};

const fetchBasicAuthStatus = async () => {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 6000);
  try {
    const ticket = await request.post('/api/system_config/request_update_token', { purpose: 'status' });
    if (ticket.code !== 200 || !ticket.data?.token) throw new Error('Missing updater status token');
    const res = await fetch('/update_stream/auth_status', {
      signal: controller.signal, headers: { 'X-Update-Token': ticket.data.token },
    });
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
    // 开发模式或未启动 updater 服务时优雅容错
    isBasicAuthOnline.value = false;
  } finally {
    clearTimeout(timeoutId);
  }
};

const handleBasicAuthSwitchClick = () => {
  if (isBasicAuthLoading.value || !isBasicAuthOnline.value) return;
  
  if (!isBasicAuthEnabled.value) {
    // 当前为关闭状态，点击打开自定义配置弹窗
    showBasicAuthModal.value = true;
  } else {
    // 当前为开启状态，点击弹出高危关闭警示
    Modal.confirm({
      title: pageText('pages.disableNginxBasicAuthProtection'),
      icon: createVNode(ExclamationCircleOutlined, { style: 'color: #ff4d4f;' }),
      width: 480,
      content: createVNode('div', { style: 'margin-top: 12px; line-height: 1.6;' }, [
        createVNode('p', { style: 'margin-bottom: 8px; color: #ff4d4f;' }, pageText('pages.disablingBasicAuthExposesTheWebGatewayDirectlyTo')),
        createVNode('p', { style: 'margin-bottom: 0;' }, pageText('pages.disableBasicAuthProtection'))
      ]),
      okText: pageText('pages.disableProtection'),
      okButtonProps: { danger: true },
      cancelText: pageText('tasks.cancel'),
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
  const timeoutId = setTimeout(() => controller.abort(), 12000); // 12s 熔断保护

  try {
    // 1. 获取一次性 Token
    const tokenRes = await request.post('/system_config/request_update_token');
    if (tokenRes.code === 200 && tokenRes.data && tokenRes.data.token) {
      const token = tokenRes.data.token;
      
      // 2. 调用 POST 接口传递 Token 及账号密码参数
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
              content: pageText('pages.basicAuthEnabledUsernameUsernameUseAPrivateWindow', { username: username || 'admin' }),
              duration: 6
            });
          } else {
            message.success(pageText('pages.basicAuthProtectionDisabled'));
          }
        } else {
          message.error(pageText('pages.failedToChangeSetting') + (data.message || pageText('tasks.unknownError')));
        }
      } else {
        message.error(pageText('pages.gatewayConfigurationRequestFailedCheckTheUpdateServiceStatus'));
      }
    } else {
      message.error(tokenRes.message || pageText('pages.failedToObtainAuthorizationToken'));
    }
  } catch (error) {
    if (error.name === 'AbortError') {
      message.error(pageText('pages.requestTimedOutCheckThatTheUpdaterServiceIs'));
    } else {
      console.error(error);
      message.error(pageText('pages.operationFailedCheckTheNetworkConnectionOrConsoleLogs'));
    }
  } finally {
    clearTimeout(timeoutId);
    isBasicAuthLoading.value = false;
  }
};
</script>

<style scoped>
.arl-header {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  min-height: 64px;
  height: auto;
  line-height: normal;
  padding: 12px 24px;
  position: relative;
  z-index: 10;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
}

.header-actions {
  display: flex;
  flex-wrap: wrap;
  justify-content: flex-end;
  align-items: center;
  gap: 12px;
  min-width: 0;
  white-space: nowrap;
  color: var(--arl-text-color);
}

.theme-swatch {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  margin-right: 8px;
}
.theme-cyan { background: #00bcd4; }
.theme-blue { background: #1890ff; }
.theme-green { background: #52c41a; }
.theme-orange { background: #fa541c; }
.theme-pink { background: #eb2f96; }

.header-language-switcher {
  margin-right: 16px;
}

.header-switch,
.header-user-settings {
  margin-right: 24px;
  display: flex;
  align-items: center;
}

.header-user-settings,
.header-change-password {
  cursor: pointer;
}

.header-change-password {
  margin-right: 24px;
}

.user-menu-icon {
  margin-right: 8px;
}

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

.page-section-gap { margin-bottom: 10px; }
.page-section-heading { font-weight: 600; font-size: 13px; margin-bottom: 2px; }
.page-muted-note { font-size: 12px; color: var(--arl-text-color); opacity: 0.75; }
.page-form-spacing { margin-bottom: 8px; }
.page-theme-emphasis { font-weight: bold; color: var(--arl-theme-color); }
.page-text-action { padding: 0; height: auto; }
.page-validation-warning { margin-top: 4px; color: #faad14; }
</style>
