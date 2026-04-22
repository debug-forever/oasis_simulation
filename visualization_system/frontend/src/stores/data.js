/**
 * Pinia状态管理
 */
import { defineStore } from 'pinia'
import { analyticsAPI } from '@/api'

export const useDataStore = defineStore('data', {
    state: () => ({
        overview: null,
        loading: false,
        error: null
    }),

    actions: {
        async fetchOverview() {
            this.loading = true
            this.error = null
            try {
                this.overview = await analyticsAPI.getOverview()
            } catch (error) {
                this.error = error.message
                console.error('Failed to fetch overview:', error)
            } finally {
                this.loading = false
            }
        }
    }
})
