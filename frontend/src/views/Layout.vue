<template>
  <a-layout :style="{ height: '100vh', background: 'transparent' }">
    <a-layout-sider v-model:collapsed="collapsed" collapsible :trigger="null" width="170" :style="{ background: hasBgImage ? (isUIHidden ? 'transparent' : 'rgba(11, 17, 32, 0.6)') : '#0b1120', borderRight: isUIHidden ? 'none' : (isDarkMode ? '1px solid #1e293b' : 'none'), transition: 'all 0.5s' }">
      <div class="logo-container" @click="toggleUI" title="点击隐藏/显示界面" style="height: 64px; display: flex; align-items: center; justify-content: center; cursor: pointer; z-index: 999; position: relative;" :style="{ background: hasBgImage ? 'transparent' : '#0b1120', borderBottom: isDarkMode ? '1px solid #1e293b' : 'none' }">
        <DeploymentUnitOutlined class="logo-icon" :style="{ color: 'var(--arl-theme-color)', fontSize: '20px' }" />
        <span class="logo-text" v-show="!collapsed" style="color: #f1f5f9; font-size: 16px; margin-left: 8px; font-weight: 500;">ARL-Next</span>
      </div>

      <a-menu :style="{ opacity: isUIHidden ? 0 : 1, pointerEvents: isUIHidden ? 'none' : 'auto', transition: 'opacity 0.5s' }" v-model:selectedKeys="selectedKeys" theme="dark" mode="inline" @click="handleMenuClick">
        <a-menu-item key="/dashboard"><DashboardOutlined /><span>仪表盘</span></a-menu-item>
        <a-menu-item key="/assetRecon"><SearchOutlined /><span>企业资产查询</span></a-menu-item>
        <a-menu-item key="/group"><AppstoreOutlined /><span>资产分组</span></a-menu-item>
        <a-menu-item key="/taskList"><GlobalOutlined /><span>任务管理</span></a-menu-item>
        <a-menu-item key="/asset-search"><SearchOutlined /><span>资产搜索</span></a-menu-item>
        <a-menu-item key="/assetsMonitor"><DesktopOutlined /><span>资产监控</span></a-menu-item>
        <a-menu-item key="/planningTasks"><ClockCircleOutlined /><span>计划任务</span></a-menu-item>
        <a-menu-item key="/GitHubTasks/GitHubTasksList"><GithubOutlined /><span>GitHub监控</span></a-menu-item>
        <a-menu-item key="/pocList"><BugOutlined /><span>POC管理</span></a-menu-item>
        <a-menu-item key="/fingerprint"><TagsOutlined /><span>指纹管理</span></a-menu-item>
        <a-menu-item key="/policy"><SettingOutlined /><span>策略配置</span></a-menu-item>
        <a-menu-item key="/systemSettings"><SettingOutlined /><span>系统设置</span></a-menu-item>
      </a-menu>
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
          
          <a-avatar style="background-color: #87d068; margin-right: 12px;" size="small"><template #icon><UserOutlined /></template></a-avatar>
          <span style="margin-right: 24px;">{{ currentUsername }}</span>
          
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
            <keep-alive include="Dashboard,AssetRecon,TaskList,AssetScope">
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
      title="🚀 AI 助手 (MCP) 一键接入"
      @cancel="showMcpModal = false"
      :footer="null"
      width="600px"
      wrapClassName="arl-theme-modal"
      rootClassName="arl-theme-modal"
  >
    <div style="margin-bottom: 16px;">
      <p>想要使用 Cursor、Claude Desktop 或其他 AI 工具自动分析平台资产与漏洞？</p>
      <p>请复制以下配置，粘贴到您的 AI 客户端配置文件的 <code>"mcpServers"</code> 节点内部：</p>
    </div>
    <div style="position: relative;">
      <pre :style="{ background: hasBgImage ? 'rgba(0,0,0,0.2)' : 'var(--arl-bg-light)', padding: '16px', borderRadius: '4px', overflowX: 'auto', fontSize: '13px', border: hasBgImage ? '1px solid rgba(255,255,255,0.1)' : 'none' }"><code :style="{ color: hasBgImage ? 'var(--arl-text-color)' : 'inherit' }">{{ mcpConfigJson }}</code></pre>
      <div style="position: absolute; top: 12px; right: 12px; display: flex; gap: 8px;">
        <a-button type="default" size="small" :loading="isRefreshingToken" @click="refreshMcpToken">刷新 Token</a-button>
        <a-button type="primary" size="small" @click="copyMcpConfig">复制配置</a-button>
      </div>
    </div>
    <p style="margin-top: 16px; font-size: 12px; color: var(--arl-text-color); opacity: 0.45;">
      注：该配置包含您的专属 API Token，请妥善保管。底层采用 <code>docker</code> 运行，请确保本地已安装并启动 Docker。
    </p>
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
import { ref, reactive, onMounted, watch, computed, onUnmounted, createVNode } from 'vue';
import { useRoute, useRouter } from 'vue-router';
// 引入 request (根据你的实际路径调整)
import request from '@/utils/request';
// 引入主题提取工具和 IndexedDB
import { extractDominantColor, processImageToBase64, dbHelper } from '@/utils/theme';
// 引入 Ant Design 的消息提示与模态框
import { message, Modal } from 'ant-design-vue';

// 补全所有需要的图标
import { DashboardOutlined, MenuUnfoldOutlined, MenuFoldOutlined, UserOutlined, LogoutOutlined, GlobalOutlined, SearchOutlined, DesktopOutlined, AppstoreOutlined, SettingOutlined, TagsOutlined, BugOutlined, ClockCircleOutlined, GithubOutlined, EyeOutlined, DeploymentUnitOutlined, RobotOutlined, BgColorsOutlined, PictureOutlined, UploadOutlined, DeleteOutlined, SafetyCertificateOutlined, ExclamationCircleOutlined } from '@ant-design/icons-vue';

const route = useRoute();
const router = useRouter();
const collapsed = ref(false);
const selectedKeys = ref([route.path]);
const isDarkMode = ref(false);
const currentUsername = ref('admin');
const hasBgImage = ref(false);
const isUIHidden = ref(false);

const isBasicAuthEnabled = ref(true);
const isBasicAuthOnline = ref(true);
const isBasicAuthLoading = ref(false);

const currentTime = ref('');
let timeInterval = null;

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
  // 由于读取和提取可能较慢，可以给个 Loading 提示
  const hide = message.loading('正在提取主题色并设置高清背景...', 0);
  try {
    const base64 = await processImageToBase64(file);
    const color = await extractDominantColor(base64);
    
    localStorage.setItem('themeColor', color);
    await dbHelper.set('bgImage', base64);
    
    window.dispatchEvent(new CustomEvent('theme-changed', { detail: color }));
    window.dispatchEvent(new CustomEvent('bg-image-changed', { detail: base64 }));
    
    hide();
    message.success('自定义高清主题背景设置成功！');
  } catch (e) {
    hide();
    message.error('提取颜色或设置失败：' + e.message);
  }
  return false; // 拦截默认上传行为
};

const handleBgImageEvent = (e) => {
  hasBgImage.value = !!e.detail;
};

onMounted(() => {
  const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
  if (userInfo.username) currentUsername.value = userInfo.username;
  
  if (route.path.includes('/GitHubTasks/')) {
    selectedKeys.value = ['/GitHubTasks/GitHubTasksList'];
  }
  
  const savedDarkMode = localStorage.getItem('darkMode');
  if (savedDarkMode === 'true') {
    isDarkMode.value = true;
  }
  
  dbHelper.get('bgImage').then((bgImage) => {
    if (bgImage) {
      hasBgImage.value = true;
    }
  });
  
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
});

const handleMenuClick = (e) => router.push(e.key);

const handleLogout = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('userInfo');
  router.push('/login');
};

// 监听路由变化，保持左侧菜单高亮的一致性
watch(() => route.path, (newPath) => {
  // 切换页面时，将滚动容器恢复到顶部
  const mainContent = document.querySelector('.arl-main-content');
  if (mainContent) {
    mainContent.scrollTop = 0;
  }

  // 如果当前在详情页，依然让相应的菜单亮起
  if (newPath.startsWith('/taskList')) {
    selectedKeys.value = ['/taskList'];
  } else if (newPath.startsWith('/assetRecon')) {
    selectedKeys.value = ['/assetRecon'];
  } else if (newPath.startsWith('/group')) {
    selectedKeys.value = ['/group'];
  } else {
    selectedKeys.value = [newPath];
  }
}, { immediate: true });

// 动态计算页面标题
const currentPageTitle = computed(() => {
  if (route.path.includes('taskDetail')) return '任务详情'; // 详情页标题
  if (route.path.includes('assetRecon/assetDetail')) return '企业信息资产详情'; // ICP详情页
  const titleMap = {
    '/dashboard': '仪表盘',
    '/assetRecon': '企业资产查询',
    '/group': '资产分组',
    '/taskList': '任务管理',
    '/asset-search': '资产搜索',
    '/assetsMonitor': '资产监控',
    '/planningTasks': '计划任务',
    '/GitHubTasks/GitHubTasksList': 'GitHub监控',
    '/policy': '策略配置',
    '/pocList': 'POC管理',
    '/fingerprint': '指纹管理',
    '/systemSettings': '系统设置',
  };
  return titleMap[route.path] || 'ARL-Next';
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
    return Promise.reject('请再次输入确认密码');
  } else if (value !== passForm.new_password) {
    return Promise.reject('两次输入的新密码不一致!');
  } else {
    return Promise.resolve();
  }
};

// 表单校验规则
const passRules = {
  old_password: [{ required: true, message: '旧密码不能为空', trigger: 'blur' }],
  new_password: [{ required: true, message: '新密码不能为空', trigger: 'blur' }],
  check_password: [{ required: true, validator: validateCheckPassword, trigger: 'blur' }]
};

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
      message.success('密码修改成功，请重新登录');
      showChangePassModal.value = false;
      passFormRef.value.resetFields();
      handleLogout(); // 密码修改成功后调用已有的退出逻辑
    } else {
      // 捕获后端的 301, 302, 303 等错误
      message.error(res.message || '修改失败');
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
const mcpConfigJson = ref('');

const handleShowMcpModal = () => {
  const token = localStorage.getItem('token') || 'YOUR_API_TOKEN';
  const host = window.location.origin;
  const config = {
    "ARL-Next": {
      "command": "docker",
      "args": [
        "run",
        "-i",
        "--rm",
        "-e",
        "ARL_HOST",
        "-e",
        "ARL_TOKEN",
        "arl-next-mcp:latest"
      ],
      "env": {
        "ARL_HOST": host,
        "ARL_TOKEN": token
      }
    }
  };
  // 去除最外层的 {} 使其更容易直接粘贴到已有的 mcpServers 对象内部
  const jsonStr = JSON.stringify(config, null, 2);
  mcpConfigJson.value = jsonStr.substring(2, jsonStr.length - 2).trim();
  showMcpModal.value = true;
};

const copyMcpConfig = () => {
  if (navigator.clipboard) {
    navigator.clipboard.writeText(mcpConfigJson.value).then(() => {
      message.success('MCP 配置已复制到剪贴板！');
    }).catch(() => {
      message.error('复制失败，请手动选择复制');
    });
  } else {
    message.error('当前环境不支持一键复制，请手动选择复制');
  }
};

const isRefreshingToken = ref(false);
const refreshMcpToken = async () => {
  try {
    isRefreshingToken.value = true;
    const res = await request.post('/user/refresh_token');
    if (res.code === 200 && res.data && res.data.token) {
      localStorage.setItem('token', res.data.token);
      message.success('Token 已作废并刷新成功，配置已自动更新！');
      handleShowMcpModal(); // 重新生成配置展示
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
</style>