<template>
  <a-layout style="min-height: 100vh">
    <a-layout-sider v-model:collapsed="collapsed" collapsible :trigger="null" width="170" style="background: #001529;">
      <div class="logo-container" style="height: 64px; display: flex; align-items: center; justify-content: center; background: #002140;">
        <DeploymentUnitOutlined class="logo-icon" :style="{ color: '#00bcd4', fontSize: '20px' }" />
        <span class="logo-text" v-show="!collapsed" style="color: #fff; font-size: 16px; margin-left: 8px; font-weight: bold;">资产灯塔系统</span>
      </div>

      <a-menu v-model:selectedKeys="selectedKeys" theme="dark" mode="inline" @click="handleMenuClick">
        <a-menu-item key="/taskList"><GlobalOutlined /><span>任务管理</span></a-menu-item>
        <a-menu-item key="/asset-search"><SearchOutlined /><span>资产搜索</span></a-menu-item>
        <a-menu-item key="/assetsMonitor"><DesktopOutlined /><span>资产监控</span></a-menu-item>
        <a-menu-item key="/group"><AppstoreOutlined /><span>资产分组</span></a-menu-item>
        <a-menu-item key="/policy"><SettingOutlined /><span>策略配置</span></a-menu-item>
        <a-menu-item key="/fingerprint"><TagsOutlined /><span>指纹管理</span></a-menu-item>
        <a-menu-item key="/pocList"><BugOutlined /><span>PoC信息</span></a-menu-item>
        <a-menu-item key="/planningTasks"><ClockCircleOutlined /><span>计划任务</span></a-menu-item>
        <a-menu-item key="/GitHubTasks/GitHubTasksList"><GithubOutlined /><span>GitHub管理</span></a-menu-item>
        <a-menu-item key="/GitHubMonitor/GitHubMonitorList"><EyeOutlined /><span>GitHub监控</span></a-menu-item>
      </a-menu>
    </a-layout-sider>

    <a-layout>
      <a-layout-header style="background: #fff; padding: 0 24px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 1px 4px rgba(0,21,41,.08); z-index: 10;">
        <div style="display: flex; align-items: center;">
          <span class="trigger" @click="() => (collapsed = !collapsed)" style="font-size: 18px; cursor: pointer; margin-right: 24px;">
            <menu-unfold-outlined v-if="collapsed" /><menu-fold-outlined v-else />
          </span>
          <span style="font-size: 16px; font-weight: 500; color: rgba(0,0,0,.85);">任务管理</span>
        </div>

        <div style="display: flex; align-items: center; color: #555;">
          <a-avatar style="background-color: #87d068; margin-right: 12px;" size="small"><template #icon><UserOutlined /></template></a-avatar>
          <span style="margin-right: 24px;">{{ currentUsername }}</span>
          <LogoutOutlined style="font-size: 16px; cursor: pointer; margin-right: 24px; color: #555;" @click="handleLogout" />
<!--          <span style="cursor: pointer; color: #555;">修改密码</span>-->
          <span style="cursor: pointer; color: #555;" @click="showChangePassModal = true">修改密码</span>
        </div>
      </a-layout-header>

      <a-layout-content style="margin: 16px; display: flex; flex-direction: column;">
        <div style="background: #fff; flex: 1;">
          <router-view></router-view>
        </div>
        <div style="text-align: center; padding: 16px 0; color: rgba(0,0,0,.45); font-size: 12px;">
          Powered by TCC(Tophant Competence Center) ARL 2.6.2
        </div>
      </a-layout-content>
    </a-layout>
  </a-layout>
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
</template>

<script setup>
import { ref,reactive, onMounted, watch, computed } from 'vue';
import { useRoute, useRouter } from 'vue-router';
// 引入 request (根据你的实际路径调整)
import request from '@/utils/request';
// 引入 Ant Design 的消息提示
import { message } from 'ant-design-vue';

// 补全所有需要的图标
import { MenuUnfoldOutlined, MenuFoldOutlined, UserOutlined, LogoutOutlined, GlobalOutlined, SearchOutlined, DesktopOutlined, AppstoreOutlined, SettingOutlined, TagsOutlined, BugOutlined, ClockCircleOutlined, GithubOutlined, EyeOutlined, DeploymentUnitOutlined } from '@ant-design/icons-vue';

const route = useRoute();
const router = useRouter();
const collapsed = ref(false);
const selectedKeys = ref([route.path]);
const currentUsername = ref('admin');

onMounted(() => {
  const userInfo = JSON.parse(localStorage.getItem('userInfo') || '{}');
  if (userInfo.username) currentUsername.value = userInfo.username;
});

const handleMenuClick = (e) => router.push(e.key);

const handleLogout = () => {
  localStorage.removeItem('token');
  localStorage.removeItem('userInfo');
  router.push('/login');
};

// 监听路由变化，保持左侧菜单高亮的一致性
watch(() => route.path, (newPath) => {
  // 如果当前在详情页，依然让“任务管理”菜单亮起
  if (newPath.startsWith('/taskList')) {
    selectedKeys.value = ['/taskList'];
  } else {
    selectedKeys.value = [newPath];
  }
}, { immediate: true });

// 动态计算页面标题
const currentPageTitle = computed(() => {
  if (route.path.includes('taskDetail')) return '任务详情'; // 详情页标题
  const titleMap = {
    '/taskList': '任务管理',
    '/search': '资产搜索',
    // ... 其他映射
  };
  return titleMap[route.path] || '资产灯塔系统';
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
</script>