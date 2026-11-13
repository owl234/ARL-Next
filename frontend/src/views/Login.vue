<template>
  <div class="login-wrapper">
    <a-card class="login-card" :bordered="false">
      <template #extra><LanguageSwitcher /></template>
      <template #title>
        <div class="login-card-header">
          <DeploymentUnitOutlined class="login-brand-icon" />
          <span class="login-brand-title">ARL-Next</span>
        </div>
      </template>

      <a-form
        ref="formRef"
        :model="formState"
        layout="vertical"
        @finish="onFinish"
        @finishFailed="validationFailed = true"
        @submit.prevent
      >
        <a-form-item :label="t('login.username')" name="username" :rules="[{ required: true, message: t('login.usernameRequired') }]">
          <a-input v-model:value="formState.username" placeholder="admin" size="large">
            <template #prefix><UserOutlined style="color: rgba(255, 255, 255, 0.45);" /></template>
          </a-input>
        </a-form-item>

        <a-form-item :label="t('login.password')" name="password" :rules="[{ required: true, message: t('login.passwordRequired') }]">
          <a-input-password v-model:value="formState.password" :placeholder="t('login.passwordPlaceholder')" size="large">
            <template #prefix><LockOutlined style="color: rgba(255, 255, 255, 0.45);" /></template>
          </a-input-password>
        </a-form-item>

        <a-form-item style="margin-top: 32px; margin-bottom: 8px;">
          <a-button type="primary" html-type="submit" block size="large" :loading="loading" class="login-submit-btn">
            {{ t('login.signIn') }}
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup>
import { reactive, ref, watch } from 'vue';
import { useI18n } from 'vue-i18n';
import { useRouter } from 'vue-router';
import request from '../utils/request';
import { message } from 'ant-design-vue';
import { DeploymentUnitOutlined, UserOutlined, LockOutlined } from '@ant-design/icons-vue';
import LanguageSwitcher from '@/components/LanguageSwitcher.vue';

const { t, locale } = useI18n({ useScope: 'global' });
const router = useRouter();
const loading = ref(false);
const formRef = ref();
const validationFailed = ref(false);

// 校验结果由组件缓存，切换语言后重新校验已提交的表单。
watch(locale, () => {
  if (validationFailed.value) formRef.value?.validateFields().catch(() => {});
}, { flush: 'post' });

const formState = reactive({
  username: 'admin',
  password: '',
});

const onFinish = async (values) => {
  loading.value = true;
  try {
    const loginRes = await request.post('/api/user/login', {
      username: values.username,
      password: values.password
    });

    if (loginRes.code === 200) {
      localStorage.setItem('token', loginRes.data.token);
      message.success(t('login.success'));
      router.push('/');
    } else if (loginRes.code === 401) {
      message.error(t('login.invalidCredentials'));
    } else {
      message.error(t('login.failed', { reason: loginRes.message || t('common.unknownError') }));
    }
  } catch (error) {
    console.error('登录请求抛出异常:', error.message);
    if (error.response?.status === 429) {
      message.error(t('login.rateLimited'));
    } else if (error.message !== '未登录或 Token 失效') {
      message.error(t('login.networkError'));
    }
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
.login-card :deep(.ant-form-item-label > label) {
  color: rgba(255, 255, 255, 0.85);
}

.login-wrapper {
  height: 100vh;
  display: flex;
  justify-content: center;
  align-items: center;
  background: radial-gradient(circle at 50% 30%, #1e293b 0%, #0b1120 100%);
}

.login-card {
  width: 380px;
  background: rgba(15, 23, 42, 0.85);
  backdrop-filter: blur(16px);
  -webkit-backdrop-filter: blur(16px);
  border: 1px solid rgba(255, 255, 255, 0.08) !important;
  border-radius: 12px !important;
  box-shadow: 0 20px 45px rgba(0, 0, 0, 0.5) !important;
  padding: 8px 12px;
}

.login-card-header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 8px 0;
}

.login-brand-icon {
  font-size: 24px;
  color: var(--arl-theme-color);
}

.login-brand-title {
  font-size: 20px;
  font-weight: 600;
  color: #f1f5f9;
  letter-spacing: -0.3px;
}

.login-submit-btn {
  border-radius: 6px;
  font-weight: 500;
}
</style>
