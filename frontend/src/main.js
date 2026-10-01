import { createApp } from 'vue'
import { createPinia } from 'pinia'
import './style.css'
import App from './App.vue'
import 'ant-design-vue/dist/reset.css' // Vue3/Antd4 的样式引入方式
import router from './router'

const pinia = createPinia()
const app = createApp(App)
app.config.globalProperties.$pageSizeOptions = ['10', '20', '50', '100', '200', '500']
app.use(pinia)
app.use(router)
app.mount('#app')
