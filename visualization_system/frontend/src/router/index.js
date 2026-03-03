import { createRouter, createWebHistory } from 'vue-router'

const routes = [
    {
        path: '/',
        name: 'Simulation',
        component: () => import('@/views/Simulation.vue')
    },
    {
        path: '/dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue')
    },
    {
        path: '/users',
        name: 'Users',
        component: () => import('@/views/Users.vue')
    },
    {
        path: '/posts',
        name: 'Posts',
        component: () => import('@/views/Posts.vue')
    },
    {
        path: '/propagation',
        name: 'Propagation',
        component: () => import('@/views/Propagation.vue')
    },
    {
        path: '/network',
        name: 'Network',
        component: () => import('@/views/Network.vue')
    }
]

const router = createRouter({
    history: createWebHistory(),
    routes
})

export default router
