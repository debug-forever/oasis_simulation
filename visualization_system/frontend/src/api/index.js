/**
 * API请求封装
 */
import axios from 'axios'

// 创建axios实例
const api = axios.create({
    baseURL: '/api',
    timeout: 10000
})

// 请求拦截器
api.interceptors.request.use(
    config => {
        return config
    },
    error => {
        console.error('Request error:', error)
        return Promise.reject(error)
    }
)

// 响应拦截器
api.interceptors.response.use(
    response => {
        return response.data
    },
    error => {
        console.error('Response error:', error)
        return Promise.reject(error)
    }
)

// ========== 用户相关API ==========

export const userAPI = {
    // 获取用户列表
    getUsers(params) {
        return api.get('/users', { params })
    },

    // 获取用户详情
    getUserDetail(userId) {
        return api.get(`/users/${userId}`)
    },

    // 获取用户帖子
    getUserPosts(userId, params) {
        return api.get(`/users/${userId}/posts`, { params })
    },

    // 获取用户互动
    getUserInteractions(userId) {
        return api.get(`/users/${userId}/interactions`)
    }
}

// ========== 帖子相关API ==========

export const postAPI = {
    // 获取帖子列表
    getPosts(params) {
        return api.get('/posts', { params })
    },

    // 获取帖子详情
    getPostDetail(postId) {
        return api.get(`/posts/${postId}`)
    },

    // 获取帖子评论
    getPostComments(postId) {
        return api.get(`/posts/${postId}/comments`)
    },

    // 获取传播树
    getPropagation(postId) {
        return api.get(`/posts/${postId}/propagation`)
    },

    // 获取所有帖子传播图
    getPropagationAll(params) {
        return api.get('/posts/propagation/all', { params })
    },

    // 获取热门帖子
    getTrending(limit = 10) {
        return api.get('/posts/trending/list', { params: { limit } })
    }
}

// ========== 分析相关API ==========

export const analyticsAPI = {
    // 获取总体统计
    getOverview() {
        return api.get('/analytics/overview')
    },

    // 获取时间线数据
    getTimeline(params) {
        return api.get('/analytics/timeline', { params })
    },

    // 获取用户网络
    getNetwork(limit = 100) {
        return api.get('/analytics/network', { params: { limit } })
    },

    // 获取影响力排行
    getInfluence(limit = 20) {
        return api.get('/analytics/influence', { params: { limit } })
    },

    // 获取活跃度数据
    getActivity(params) {
        return api.get('/analytics/activity', { params })
    }

}


export const simulationAPI = {
    // 获取模拟任务列表
    getTasks() {
        return api.get('/simulation/list')
    },

    // 启动新任务
    startTask(config) {
        return api.post('/simulation/start', { config })
    },

    // 获取任务状态
    getTaskStatus(taskId) {
        return api.get(`/simulation/${taskId}/status`)
    },

    // 获取任务日志
    getTaskLogs(taskId, maxLines = 100) {
        return api.get(`/simulation/${taskId}/logs`, { params: { max_lines: maxLines } })
    },

    // 停止任务
    stopTask(taskId) {
        return api.delete(`/simulation/${taskId}/stop`)
    },

    // 删除任务
    deleteTask(taskId) {
        return api.delete(`/simulation/${taskId}`)
    },

    // 获取任务结果
    getTaskResult(taskId) {
        return api.get(`/simulation/${taskId}/result`)
    },

    // 获取数据库列表
    getDatabaseList() {
        return api.get('/simulation/list-databases')
    },

    // 切换数据库
    switchDatabase(dbPath) {
        return api.post('/simulation/switch-database', { db_path: dbPath })
    },

    // 获取当前数据库
    getCurrentDatabase() {
        return api.get('/simulation/current-db')
    }
}


export default api
