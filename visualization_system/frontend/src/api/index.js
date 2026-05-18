import axios from 'axios'

const api = axios.create({
    baseURL: '/api',
    timeout: 10000
})

api.interceptors.request.use(
    config => config,
    error => {
        console.error('Request error:', error)
        return Promise.reject(error)
    }
)

api.interceptors.response.use(
    response => response.data,
    error => {
        console.error('Response error:', error)
        return Promise.reject(error)
    }
)

const withFilters = (params, filters) => {
    if (filters?.length) {
        params.filters = JSON.stringify(filters)
    }
    return params
}

export const userAPI = {
    getUsers(params) {
        return api.get('/users', { params })
    },

    getUserDetail(userId) {
        return api.get(`/users/${userId}`)
    },

    getUserPosts(userId, params) {
        return api.get(`/users/${userId}/posts`, { params })
    },

    getUserInteractions(userId) {
        return api.get(`/users/${userId}/interactions`)
    }
}

export const postAPI = {
    getPosts(params) {
        return api.get('/posts', { params })
    },

    getPostDetail(postId) {
        return api.get(`/posts/${postId}`)
    },

    getPostComments(postId) {
        return api.get(`/posts/${postId}/comments`)
    },

    getPropagation(postId) {
        return api.get(`/posts/${postId}/propagation`)
    },

    getPropagationAll(params) {
        return api.get('/posts/propagation/all', { params })
    },

    getTrending(limit = 10) {
        return api.get('/posts/trending/list', { params: { limit } })
    }
}

export const analyticsAPI = {
    getOverview() {
        return api.get('/analytics/overview')
    },

    getTimeline(params) {
        return api.get('/analytics/timeline', { params })
    },

    getNetwork(limit = 100) {
        return api.get('/analytics/network', { params: { limit } })
    },

    getInfluence(limit = 20) {
        return api.get('/analytics/influence', { params: { limit } })
    },

    getActivity(params) {
        return api.get('/analytics/activity', { params })
    }
}

export const networkAPI = {
    getRelationshipGraph(params) {
        return api.get('/network/relationship-graph', { params })
    }
}

export const simulationAPI = {
    getTasks() {
        return api.get('/simulation/list')
    },

    startTask(config) {
        return api.post('/simulation/start', { config })
    },

    getTaskStatus(taskId) {
        return api.get(`/simulation/${taskId}/status`)
    },

    getTaskLogs(taskId, maxLines = 100) {
        return api.get(`/simulation/${taskId}/logs`, { params: { max_lines: maxLines } })
    },

    stopTask(taskId) {
        return api.delete(`/simulation/${taskId}/stop`)
    },

    deleteTask(taskId) {
        return api.delete(`/simulation/${taskId}`)
    },

    getTaskResult(taskId) {
        return api.get(`/simulation/${taskId}/result`)
    },

    getDatabaseList() {
        return api.get('/simulation/list-databases')
    },

    switchDatabase(dbPath) {
        return api.post('/simulation/switch-database', { db_path: dbPath })
    },

    getCurrentDatabase() {
        return api.get('/simulation/current-db')
    }
}

export const vaAPI = {
    getStatus() {
        return api.get('/va/status')
    },

    build(profileJson = null) {
        return api.post('/va/build', { profile_json: profileJson }, { timeout: 600000 })
    },

    getCatalog() {
        return api.get('/va/catalog')
    },

    explore(spec) {
        return api.post('/va/explore', spec)
    },

    getLifecycle(breakdown = 'event.action_type', filters = null) {
        return api.get('/va/lifecycle', { params: withFilters({ breakdown }, filters) })
    },

    compareLifecycle(phaseA, phaseB, breakdown = 'event.action_type', filters = null) {
        const params = withFilters({ phase_a: phaseA, phase_b: phaseB, breakdown }, filters)
        return api.get('/va/lifecycle/compare', { params })
    },

    getKeyGroups(groupBy = 'user.profession', filters = null, phase = null) {
        const params = withFilters({ group_by: groupBy }, filters)
        if (phase) params.phase = phase
        return api.get('/va/key-groups', { params })
    },

    getKeyUsers(opts = {}) {
        const params = withFilters({
            role: opts.role || 'all',
            sort_by: opts.sortBy || 'influence_score',
            limit: opts.limit || 50
        }, opts.filters)
        if (opts.phase) params.phase = opts.phase
        return api.get('/va/key-users', { params })
    },

    getUserDetail(userId) {
        return api.get(`/va/user/${userId}`)
    },

    getInfluencePath(userId) {
        return api.get(`/va/user/${userId}/influence-path`)
    }
}

export default api
