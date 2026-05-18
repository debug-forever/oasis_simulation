import { createRouter, createWebHistory } from 'vue-router'

export const routes = [
    {
        path: '/',
        name: 'Simulation',
        title: '控制台',
        icon: '🚀',
        component: () => import('@/views/Simulation.vue')
    },
    {
        path: '/dashboard',
        name: 'Dashboard',
        title: '系统概览',
        icon: '🏠',
        component: () => import('@/views/Dashboard.vue')
    },
    {
        path: '/users',
        name: 'Users',
        title: '用户列表',
        icon: '👥',
        component: () => import('@/views/Users.vue')
    },
    {
        path: '/posts',
        name: 'Posts',
        title: '内容列表',
        icon: '📝',
        component: () => import('@/views/Posts.vue')
    },
    {
        path: '/propagation',
        name: 'Propagation',
        title: '传播图谱',
        icon: '🌐',
        component: () => import('@/views/Propagation.vue')
    },
    {
        path: '/network',
        name: 'Network',
        title: '关系网络',
        icon: '🔗',
        component: () => import('@/views/Network.vue')
    },
    {
        path: '/lifecycle',
        name: 'Lifecycle',
        title: '舆情生命周期',
        icon: '📈',
        group: '可视分析',
        component: () => import('@/views/Lifecycle.vue')
    },
    {
        path: '/key-groups',
        name: 'KeyGroups',
        title: '关键群体识别',
        icon: '🎯',
        group: '可视分析',
        component: () => import('@/views/KeyGroups.vue')
    },
    {
        path: '/key-users',
        name: 'KeyUsers',
        title: '关键用户识别',
        icon: '⭐',
        group: '可视分析',
        component: () => import('@/views/KeyUsers.vue')
    }
]

export const navSections = [
    {
        items: routes.filter(route => !route.group)
    },
    {
        label: '可视分析',
        items: routes.filter(route => route.group === '可视分析')
    }
]

export const pageTitles = Object.fromEntries(routes.map(route => [route.path, route.title]))

const router = createRouter({
    history: createWebHistory(),
    routes
})

export default router
