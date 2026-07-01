import { createRouter, createWebHistory } from 'vue-router'
import Login from '../views/Login.vue'
import Layout from '../views/Layout.vue'
import Task from "../views/TaskList.vue";
import TaskDetail from '../views/TaskDetail.vue' // 新增引入





const routes = [
    {
        path: '/login',
        name: 'Login',
        component: Login,
        beforeEnter: (to, from, next) => {
            if (localStorage.getItem('token')) next('/')
            else next()
        }
    },
    {
        path: '/',
        name: 'Layout',
        component: Layout,
        redirect: '/dashboard',
        beforeEnter: (to, from, next) => {
            const token = localStorage.getItem('token')
            if (token) next()
            else next('/login')
        },
        children: [
            {
                path: 'dashboard',
                name: 'Dashboard',
                component: () => import('../views/Dashboard.vue'),
                meta: { title: '仪表盘' }
            },
            {
                path: 'taskList',
                name: 'TaskList',
                component: Task
            },
            {
                // 新增详情页路由
                path: 'taskList/taskDetail',
                name: 'TaskDetail',
                component: TaskDetail
            },

            {
                path: '/asset-search',
                name: 'AssetSearch',
                component: () => import('../views/AssetSearch.vue'), // 指向你刚才新建的文件
                meta: { title: '资产搜索' } // 可选：如果有面包屑或页面标题依赖 meta，可以加上
            },
            {
                // 🚨 核心修改：将 '/asset-monitor' 改为 '/assetsMonitor'
                path: '/assetsMonitor',
                name: 'AssetMonitor',
                component: () => import('../views/AssetMonitor.vue'),
                meta: { title: '资产监控' }
            },
            {
                // 🚨 核心修改：将 '/asset-scope' 改为 '/group'
                path: '/group',
                name: 'AssetScope',
                component: () => import('../views/AssetScope.vue'),
                meta: { title: '资产分组' }
            },
            {
                path: '/groupAssetsManagement/groupAssetsDetail',
                name: 'GroupAssetsDetail',
                component: () => import('../views/GroupAssetsDetail.vue'),
                meta: { title: '资产分组详情' }
            },
            // 在你的 routes 数组中添加：
// 找到你之前加 /policy 的地方，紧挨着追加这一段：
            {
                path: '/policy',
                name: 'Policy',
                component: () => import('../views/Policy.vue')
            },
// 🚨 新增：策略配置的独立新建/编辑页面
            {
                path: '/policyDetail',
                name: 'PolicyDetail',
                component: () => import('../views/PolicyDetail.vue')
            },
            {
                path: '/fingerprint', // 对应你左侧菜单的路径
                name: 'Fingerprint',
                component: () => import('../views/Fingerprint.vue'),
                meta: { title: '指纹管理' }
            },
            {
                path: '/pocList', // 请确保这和你菜单配置的路径一致
                name: 'PocList',
                component: () => import('../views/PocList.vue'),
                meta: { title: 'PoC信息' }
            },

            {
                path: '/planningTasks', // 请确保这和你菜单配置的路径一致
                name: 'PlanningTasks',
                component: () => import('../views/PlanningTasks.vue'),
                meta: { title: '计划任务' }
            },


            {
                path: '/GitHubTasks/GitHubTasksList',
                name: 'GithubManage',
                component: () => import('../views/GithubManage.vue'),
                meta: { title: 'GitHub管理' }
            },
            {
                path: '/GitHubTasks/GitHubTasksInfo', // 这个路径必须和列表页跳转时写的一模一样
                name: 'GitHubTasksInfo',
                component: () => import('../views/GitHubTasksInfo.vue'), // 这里的组件文件名大小写必须和实际文件一字不差！
                meta: { title: 'GitHub 任务详情' }
            },
            {
                path: '/GitHubMonitor/GitHubMonitorInfo', // 这个路径必须和列表页跳转时写的一模一样
                name: 'GitHubMonitorInfo',
                component: () => import('../views/GitHubMonitorInfo.vue'), // 这里的组件文件名大小写必须和实际文件一字不差！
                meta: { title: 'GitHub 监控详情' }
            },
            {
                path: '/systemSettings',
                name: 'SystemSettings',
                component: () => import('../views/SystemSettings.vue'),
                meta: { title: '系统设置' }
            },
            {
                path: '/icpQuery',
                name: 'ICPQuery',
                component: () => import('../views/ICPQuery.vue'),
                meta: { title: 'ICP 备案查询' }
            },
            {
                path: '/icpQuery/assetDetail',
                name: 'ICPAssetDetail',
                component: () => import('../views/ICPAssetDetail.vue'),
                meta: { title: 'ICP 备案资产详情' }
            }
        ]


    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

export default router