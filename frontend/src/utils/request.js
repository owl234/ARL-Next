import axios from 'axios';
import { message } from 'ant-design-vue';
import { i18n } from '../i18n/index.js';

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

function triggerUnauthorizedRedirect() {
    if (!isRedirecting) {
        isRedirecting = true; // 上锁

        message.warning(i18n.global.t('request.sessionExpired'));

        // 撕毁所有过期门票
        localStorage.removeItem('token');
        localStorage.removeItem('userInfo');

        // 延迟一点点跳转，让用户能看清 warning 提示词
        setTimeout(() => {
            window.location.href = '/login';
            // 注意：跳转后页面会刷新，脚本会重新加载，锁自然就重置了
        }, 1000);
    }
}

// 响应拦截器：统一处理状态码
request.interceptors.response.use(
    (response) => {
        // 若已处于登出跳转中，直接挂起后续并发响应，收敛组件层重复报错弹窗
        if (isRedirecting) {
            return new Promise(() => {});
        }

        const res = response.data; // 剥离最外层，直接拿核心数据

        // 核心逻辑：精准捕获 ARL 的 401 状态
        if (res.code === 401 || res.message === 'not login') {

            // 如果是登录接口返回的 401（账号密码错误），直接放行给页面处理，不拦截踢人
            if (response.config && response.config.url && response.config.url.includes('/user/login')) {
                return res;
            }

            triggerUnauthorizedRedirect();

            // 返回挂起 Promise 阻断后续调用链，实现平滑静默跳转
            return new Promise(() => {});
        }

        if (response.config && response.config.returnFullResponse) {
            return response;
        }

        return res;
    },
    (error) => {
        // 若已处于登出跳转中，直接挂起后续所有并发错误
        if (isRedirecting) {
            return new Promise(() => {});
        }

        // 1. 优先捕获真实 HTTP 401 状态码 (网关/代理层异常或标准 RESTful 鉴权失败)
        // 必须优先于 blob 判断，防止导出文件时 401 绕过全局登出重定向
        if (error.response && error.response.status === 401) {
            if (error.config && error.config.url && error.config.url.includes('/user/login')) {
                return Promise.reject(error);
            }
            triggerUnauthorizedRedirect();
            return new Promise(() => {});
        }

        if (error.response?.status === 429 && error.config?.url?.includes('/user/login')) {
            return Promise.reject(error);
        }

        // 2. blob 类请求（如下载）的错误体由业务组件自行解析并提示精确信息，避免双重弹窗
        if (error.config && error.config.responseType === 'blob') {
            return Promise.reject(error);
        }

        // 3. 处理真正的 HTTP 级别报错 (如 500, 502)
        message.error(i18n.global.t('request.networkError'));
        return Promise.reject(error);
    }
);

export default request;
