import { createApp } from 'vue'
import 'ant-design-vue/dist/reset.css' // Vue3/Antd4 的样式引入方式
import './style.css'
import App from './App.vue'
import router from './router'
import { i18n, initializeLocale } from './i18n'

initializeLocale()
const app = createApp(App)
app.config.globalProperties.$pageSizeOptions = ['10', '20', '50', '100', '200', '500']
app.use(router)
app.use(i18n)
app.mount('#app')
