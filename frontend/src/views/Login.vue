<template>
  <div style="height: 100vh; display: flex; justify-content: center; align-items: center; background-color: #141414;">
    <a-card title="ARL-Next" style="width: 400px; box-shadow: 0 4px 12px rgba(0,0,0,0.5); border-radius: 8px;">
      <a-form
          :model="formState"
          layout="vertical"
          @finish="onFinish"
          @submit.prevent
      >
        <a-form-item label="账号" name="username" :rules="[{ required: true, message: '请输入账号!' }]">
          <a-input v-model:value="formState.username" placeholder="admin" size="large" />
        </a-form-item>

        <a-form-item label="密码" name="password" :rules="[{ required: true, message: '请输入密码!' }]">
          <a-input-password v-model:value="formState.password" placeholder="arlpass" size="large" />
        </a-form-item>

        <a-form-item style="margin-top: 30px;">
          <a-button type="primary" html-type="submit" block size="large" :loading="loading">
            登录
          </a-button>
        </a-form-item>
      </a-form>
    </a-card>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue';
import { useRouter } from 'vue-router';
import request from '../utils/request';

const router = useRouter();
const loading = ref(false);

const formState = reactive({
  username: 'admin',
  password: 'arlpass',
});

const onFinish = async (values) => {
  loading.value = true;
  try {
    // 铁证1：精准调用 user.py 中的 /login 路由
    const loginRes = await request.post('/api/user/login', {
      username: values.username,
      password: values.password
    });

    // 铁证2：build_data() 函数默认成功的 code 就是 200
    if (loginRes.code === 200) {
      // 拿到后端下发的 Token 并存储
      localStorage.setItem('token', loginRes.data.token);

      // 铁证3：不需要额外请求用户信息，直接跳转到主页 (Task页)
      router.push('/');
    } else {
      alert('登录失败：' + (loginRes.message || '未知错误'));
    }
  } catch (error) {
    console.error('登录请求抛出异常:', error.message);
    // 只有当真正的网络断开时，才弹这个原生的 alert
    if (error.message !== '未登录或 Token 失效') {
      alert('真正的网络请求失败，请检查控制台。');
    }
  } finally {
    loading.value = false;
  }
};
</script>

<style scoped>
/* 稍微美化一下暗色主题的卡片文字 */
:deep(.ant-card-head-title) {
  text-align: center;
  font-size: 18px;
  font-weight: bold;
}
</style>