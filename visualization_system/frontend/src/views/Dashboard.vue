<template>
  <div class="dashboard">
    <!-- 欢迎横幅 -->
    <div class="welcome-banner gradient-bg">
      <div class="banner-content">
        <h1 class="banner-title">欢迎使用微博仿真可视化系统 👋</h1>
        <p class="banner-subtitle">实时监控和分析社交媒体仿真数据</p>
      </div>
    </div>

    <!-- 数据库选择 -->
    <el-row :gutter="24" class="control-row">
      <el-col :span="24">
        <div class="card control-card">
          <div class="control-header">
            <span class="control-title">📚 数据库管理</span>
            <span class="current-db-badge" v-if="currentDbInfo">
              当前: {{ currentDbInfo.name }} ({{ currentDbInfo.size_mb }}MB)
            </span>
          </div>
          <div class="control-body">
            <div class="db-selector">
              <el-select 
                v-model="selectedDb" 
                placeholder="选择仿真数据库" 
                class="db-select"
                size="large"
              >
                <el-option
                  v-for="db in databaseList"
                  :key="db.path"
                  :label="`${db.name} (${db.size_mb}MB) - ${formatDate(db.mtime)}`"
                  :value="db.path"
                />
              </el-select>
              <el-button 
                type="primary" 
                size="large" 
                @click="handleSwitchDatabase"
                :loading="switchingDb"
                :disabled="!selectedDb || selectedDb === currentDbInfo?.path"
              >
                切换数据库
              </el-button>
              <el-button 
                plain 
                size="large" 
                @click="refreshDbList"
                :loading="loadingDbList"
              >
                🔄 刷新列表
              </el-button>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>


    <!-- 加载状态 -->
    <div v-if="loading" class="loading-container">
      <el-skeleton :rows="6" animated />
    </div>

    <!-- 统计卡片 -->
    <el-row v-else :gutter="24" class="stats-row">
      <el-col :xs="12" :sm="12" :md="6" :lg="6">
        <div class="stat-card fade-in">
          <div class="stat-card-icon">👥</div>
          <div class="stat-card-value">{{ overview.total_users?.toLocaleString() || 0 }}</div>
          <div class="stat-card-label">总用户数</div>
          <div class="stat-card-trend">
            <span class="trend-value">{{ overview.active_users || 0 }}</span>
            <span class="trend-label">活跃用户</span>
          </div>
        </div>
      </el-col>

      <el-col :xs="12" :sm="12" :md="6" :lg="6">
        <div class="stat-card fade-in" style="animation-delay: 0.1s">
          <div class="stat-card-icon">📝</div>
          <div class="stat-card-value">{{ overview.total_posts?.toLocaleString() || 0 }}</div>
          <div class="stat-card-label">总帖子数</div>
          <div class="stat-card-trend">
            <span class=" trend-value">{{ overview.total_reposts || 0 }}</span>
            <span class="trend-label">转发数</span>
          </div>
        </div>
      </el-col>

      <el-col :xs="12" :sm="12" :md="6" :lg="6">
        <div class="stat-card fade-in" style="animation-delay: 0.2s">
          <div class="stat-card-icon">💬</div>
          <div class="stat-card-value">{{ overview.total_comments?.toLocaleString() || 0 }}</div>
          <div class="stat-card-label">总评论数</div>
          <div class="stat-card-trend">
            <span class="trend-value">{{ overview.avg_posts_per_user?.toFixed(1) || 0 }}</span>
            <span class="trend-label">人均发帖</span>
          </div>
        </div>
      </el-col>

      <el-col :xs="12" :sm="12" :md="6" :lg="6">
        <div class="stat-card fade-in" style="animation-delay: 0.3s">
          <div class="stat-card-icon">❤️</div>
          <div class="stat-card-value">{{ overview.total_likes?.toLocaleString() || 0 }}</div>
          <div class="stat-card-label">总点赞数</div>
          <div class="stat-card-trend">
            <span class="trend-value">{{ overview.total_follows || 0 }}</span>
            <span class="trend-label">关注关系</span>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 图表区域 -->
    <el-row :gutter="24" class="charts-row">
      <!-- 时间线图表 -->
      <el-col :xs="24" :sm="24" :md="16" :lg="16">
        <div class="card chart-container">
          <h3 class="chart-title">📊 活动时间线</h3>
          <div ref="timelineChart" class="chart" style="height: 400px"></div>
        </div>
      </el-col>

      <!-- 热门帖子 -->
      <el-col :xs="24" :sm="24" :md="8" :lg="8">
        <div class="card">
          <h3 class="chart-title">🔥 热门帖子</h3>
          <div class="trending-list">
            <div v-for="(post, index) in trendingPosts" :key="post.post_id" class="trending-item">
              <div class="trending-rank" :class="`rank-${index + 1}`">{{ index + 1 }}</div>
              <div class="trending-content">
                <p class="trending-text">{{ truncateText(post.content, 50) }}</p>
                <div class="trending-stats">
                  <span>❤️ {{ post.num_likes }}</span>
                  <span>🔁 {{ post.num_shares }}</span>
                  <span>💬 {{ post.num_comments }}</span>
                </div>
              </div>
            </div>
            <div v-if="trendingPosts.length === 0" class="empty-state">
              <p>暂无热门帖子数据</p>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>

    <!-- 数据概览 -->
    <el-row :gutter="24" class="info-row">
      <el-col :span="24">
        <div class="card">
          <h3 class="chart-title">ℹ️ 数据概览</h3>
          <div class="info-grid">
            <div class="info-item">
              <span class="info-label">数据时间范围</span>
              <span class="info-value">{{ formatTimeRange() }}</span>
            </div>
            <div class="info-item">
              <span class="info-label">总互动数</span>
              <span class="info-value">
                {{ ((overview.total_likes || 0) + (overview.total_comments || 0) + (overview.total_reposts || 0)).toLocaleString() }}
              </span>
            </div>
          </div>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { analyticsAPI, postAPI, simulationAPI } from '@/api'

const loading = ref(true)
const overview = ref({})
const timelineData = ref([])
const trendingPosts = ref([])
const timelineChart = ref(null)

// 数据库相关状态
const databaseList = ref([])
const selectedDb = ref('')
const currentDbInfo = ref(null)
const switchingDb = ref(false)
const loadingDbList = ref(false)

const fetchData = async () => {
  loading.value = true
  try {
    // 获取总体统计
    overview.value = await analyticsAPI.getOverview()
    
    // 获取时间线数据
    timelineData.value = await analyticsAPI.getTimeline({ interval: 'hour' })
    
    // 获取热门帖子
    const trending = await postAPI.getTrending(5)
    trendingPosts.value = trending.posts || []
    
    // 渲染图表
    renderTimelineChart()
    
    // 获取当前数据库信息
    await fetchCurrentDb()
  } catch (error) {
    console.error('Failed to fetch dashboard data:', error)
  } finally {
    loading.value = false
  }
}

const renderTimelineChart = () => {
  if (!timelineChart.value) return
  
  const chart = echarts.init(timelineChart.value)
  
  const timestamps = timelineData.value.data?.map(d => d.timestamp) || []
  const posts = timelineData.value.data?.map(d => d.post_count) || []
  const comments = timelineData.value.data?.map(d => d.comment_count) || []
  const likes = timelineData.value.data?.map(d => d.like_count) || []
  
  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(26, 26, 46, 0.9)',
      borderColor: '#667eea',
      textStyle: { color: '#fff' }
    },
    legend: {
      data: ['帖子', '评论', '点赞'],
      textStyle: { color: '#b8b8d1' },
      top: 10
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: timestamps,
      axisLine: { lineStyle: { color: '#2d2d44' } },
      axisLabel: { color: '#b8b8d1', rotate: 45 }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#2d2d44' } },
      splitLine: { lineStyle: { color: '#2d2d44', type: 'dashed' } },
      axisLabel: { color: '#b8b8d1' }
    },
    series: [
      {
        name: '帖子',
        type: 'line',
        data: posts,
        smooth: true,
        lineStyle: { width: 3, color: '#667eea' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(102, 126, 234, 0.3)' },
            { offset: 1, color: 'rgba(102, 126, 234, 0)' }
          ])
        }
      },
      {
        name: '评论',
        type: 'line',
        data: comments,
        smooth: true,
        lineStyle: { width: 3, color: '#4ECDC4' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(78, 205, 196, 0.3)' },
            { offset: 1, color: 'rgba(78, 205, 196, 0)' }
          ])
        }
      },
      {
        name: '点赞',
        type: 'line',
        data: likes,
        smooth: true,
        lineStyle: { width: 3, color: '#f093fb' },
        areaStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color: 'rgba(240, 147, 251, 0.3)' },
            { offset: 1, color: 'rgba(240, 147, 251, 0)' }
          ])
        }
      }
    ]
  }
  
  chart.setOption(option)
  
  // 响应式
  window.addEventListener('resize', () => chart.resize())
}

const truncateText = (text, maxLength) => {
  if (!text) return ''
  return text.length > maxLength ? text.substring(0, maxLength) + '...' : text
}

const formatTimeRange = () => {
  if (!overview.value.earliest_time || !overview.value.latest_time) {
    return '暂无数据'
  }
  const start = new Date(overview.value.earliest_time).toLocaleDateString('zh-CN')
  const end = new Date(overview.value.latest_time).toLocaleDateString('zh-CN')
  return `${start} ~ ${end}`
}

const formatDate = (timestamp) => {
  return new Date(timestamp * 1000).toLocaleString('zh-CN')
}

const fetchDbList = async () => {
  loadingDbList.value = true
  try {
    const res = await simulationAPI.getDatabaseList()
    databaseList.value = res.databases || []
  } catch (error) {
    console.error('Failed to fetch DB list:', error)
    ElMessage.error('获取数据库列表失败')
  } finally {
    loadingDbList.value = false
  }
}

const fetchCurrentDb = async () => {
  try {
    const res = await simulationAPI.getCurrentDatabase()
    if (res.db_path) {
      // 从列表中找到对应的信息，或者创建一个简单的对象
      const found = databaseList.value.find(db => db.path === res.db_path)
      if (found) {
        currentDbInfo.value = found
        selectedDb.value = found.path
      } else {
        // 如果列表还没加载或者不在列表中
        const name = res.db_path.split(/[\\/]/).pop()
        currentDbInfo.value = {
          name: name,
          path: res.db_path,
          size_mb: 'Unknown'
        }
        selectedDb.value = res.db_path
      }
    }
  } catch (error) {
    console.error('Failed to fetch current DB:', error)
  }
}

const handleSwitchDatabase = async () => {
  if (!selectedDb.value) return
  
  switchingDb.value = true
  try {
    await simulationAPI.switchDatabase(selectedDb.value)
    ElMessage.success('数据库切换成功')
    
    // 重新获取数据
    await fetchData()
    await fetchCurrentDb()
  } catch (error) {
    console.error('Failed to switch database:', error)
    ElMessage.error('数据库切换失败: ' + error.message)
  } finally {
    switchingDb.value = false
  }
}

const refreshDbList = async () => {
  await fetchDbList()
  await fetchCurrentDb()
}

onMounted(async () => {
  await fetchDbList()
  await fetchData()
})
</script>

<style scoped>
.dashboard {
  min-height: 100%;
}

/* 欢迎横幅 */
.welcome-banner {
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl);
  margin-bottom: var(--spacing-xl);
  text-align: center;
  box-shadow: var(--shadow-glow);
}

.banner-title {
  font-size: 28px;
  font-weight: 700;
  color: white;
  margin: 0 0 var(--spacing-sm) 0;
}

.banner-subtitle {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.9);
  color: rgba(255, 255, 255, 0.9);
  margin: 0;
}

/* 控制栏 */
.control-row {
  margin-bottom: var(--spacing-xl);
}

.control-card {
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.control-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.control-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.current-db-badge {
  font-size: 12px;
  color: var(--primary-color);
  background: rgba(102, 126, 234, 0.1);
  padding: 4px 12px;
  border-radius: 12px;
  font-weight: 500;
}

.db-selector {
  display: flex;
  gap: var(--spacing-md);
  align-items: center;
}

.db-select {
  flex: 1;
  max-width: 500px;
}

/* 统计卡片行 */
.stats-row {
  margin-bottom: var(--spacing-xl);
}

.stat-card-trend {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--border-color);
}

.trend-value {
  font-size: 18px;
  font-weight: 600;
  color: var(--primary-color);
}

.trend-label {
  font-size: 12px;
  color: var(--text-muted);
}

/* 图表区域 */
.charts-row {
  margin-bottom: var(--spacing-xl);
}

.chart-container {
  height: 100%;
}

.chart-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: var(--spacing-lg);
  padding-bottom: var(--spacing-sm);
  border-bottom: 2px solid var(--border-color);
}

.chart {
  width: 100%;
}

/* 热门帖子列表 */
.trending-list {
  max-height: 400px;
  overflow-y: auto;
}

.trending-item {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-md);
  padding: var(--spacing-md);
  margin-bottom: var(--spacing-sm);
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  transition: all 0.3s ease;
}

.trending-item:hover {
  background: var(--bg-color);
  transform: translateX(-4px);
}

.trending-rank {
  min-width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  font-weight: 700;
  font-size: 14px;
  background: var(--bg-secondary);
  color: var(--text-secondary);
}

.rank-1 {
  background: linear-gradient(135deg, #FFD700 0%, #FFA500 100%);
  color: white;
}

.rank-2 {
  background: linear-gradient(135deg, #C0C0C0 0%, #808080 100%);
  color: white;
}

.rank-3 {
  background: linear-gradient(135deg, #CD7F32 0%, #8B4513 100%);
  color: white;
}

.trending-content {
  flex: 1;
}

.trending-text {
  font-size: 14px;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-sm) 0;
  line-height: 1.5;
}

.trending-stats {
  display: flex;
  gap: var(--spacing-md);
  font-size: 12px;
  color: var(--text-secondary);
}

.trending-stats span {
  display: flex;
  align-items: center;
  gap: var(--spacing-xs);
}

/* 信息网格 */
.info-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: var(--spacing-lg);
}

.info-item {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.info-label {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.info-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.empty-state {
  text-align: center;
  padding: var(--spacing-xl);
  color: var(--text-muted);
}

.loading-container {
  padding: var(--spacing-xl);
}
</style>
