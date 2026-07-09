import axios from 'axios';
import { message } from 'ant-design-vue';

// 创建 axios 实例
const request = axios.create({
   // baseURL: '/api', // 根据你的代理配置调整
    timeout: 60000,
});
// 2. 🚀 请求拦截器：自动加 /api 前缀 & 携带 Token
request.interceptors.request.use(
    (config) => {
        // 【终极修复逻辑】：不管是哪个页面发出的请求
        // 只要路径里没有 /api，我们就强行给它拼上！
        // 这样就完美兼容了 '/task' 和 'task' 等各种写法，绝对不会再丢前缀！
        if (config.url && !config.url.startsWith('/api') && !config.url.startsWith('http')) {
            config.url = '/api' + (config.url.startsWith('/') ? config.url : '/' + config.url);
        }

        const token = localStorage.getItem('token');
        if (token) {
            config.headers['Token'] = token;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// 全局防抖锁：防止并发 401 触发多次提示和跳转
let isRedirecting = false;

// 响应拦截器：统一处理状态码
request.interceptors.response.use(
    (response) => {
        const res = response.data; // 剥离最外层，直接拿核心数据

        // 核心逻辑：精准捕获 ARL 的 401 状态
        if (res.code === 401 || res.message === 'not login') {

            // 如果锁没开启，说明是第一个报错的请求
            if (!isRedirecting) {
                isRedirecting = true; // 上锁

                message.warning('身份已过期或失效，请重新登录！');

                // 撕毁所有过期门票
                localStorage.removeItem('token');
                localStorage.removeItem('userInfo');

                // 延迟一点点跳转，让用户能看清 warning 提示词
                setTimeout(() => {
                    window.location.href = '/login';
                    // 注意：跳转后页面会刷新，脚本会重新加载，锁自然就重置了
                }, 1000);
            }

            // 拦截掉这个请求，不要让它抛到业务组件里去报错
            return Promise.reject(new Error('未登录或 Token 失效'));
        }

        return res;
    },
    (error) => {
        // 处理真正的 HTTP 级别报错 (如 500, 502)
        message.error('网络请求异常，请检查后端服务！');
        return Promise.reject(error);
    }
);

export default request;