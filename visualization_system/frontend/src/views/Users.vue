<template>
  <div class="users-page">
    <!-- 页面标题 -->
    <div class="page-header gradient-bg">
      <h1 class="page-title">👥 用户浏览</h1>
      <p class="page-subtitle">浏览和搜索所有仿真用户</p>
    </div>

    <!-- 搜索和筛选 -->
    <div class="filters-section card">
      <el-row :gutter="16" justify="center">
        <!-- 搜索框 -->
        <el-col :span="18">
          <el-input
            v-model="searchQuery"
            placeholder="搜索用户名或昵称..."
            size="large"
            clearable
            @clear="handleSearch"
            @keyup.enter="handleSearch"
            class="search-input user-search-input"
          >
            <template #prefix>
              <span class="search-icon">🔍</span>
            </template>
            <template #append>
              <el-button @click="handleSearch" :loading="loading" type="primary">搜索</el-button>
            </template>
          </el-input>
        </el-col>
      </el-row>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading && users.length === 0" class="loading-container">
      <el-skeleton :rows="8" animated />
    </div>

    <!-- 用户列表 -->
    <div v-else class="card users-table-card">
      <el-table
        :data="users"
        style="width: 100%"
        @row-click="handleRowClick"
        class="users-table"
        :row-class-name="getRowClassName"
      >
        <el-table-column prop="user_id" label="ID" width="80" />
        <el-table-column prop="name" label="昵称" min-width="150">
          <template #default="{ row }">
            <div class="user-name-cell">
              <div class="user-avatar">{{ getInitial(row.name) }}</div>
              <span class="user-name">{{ row.name }}</span>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="user_name" label="用户名" min-width="120" />
        <el-table-column prop="bio" label="简介" min-width="200">
          <template #default="{ row }">
            <el-tooltip :content="row.bio || '暂无简介'" placement="top" effect="dark">
              <div class="bio-cell">{{ row.bio || '暂无简介' }}</div>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column prop="num_followers" label="粉丝数" width="100" align="right">
          <template #default="{ row }">
            <span class="stat-badge">{{ row.num_followers?.toLocaleString() || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="num_followings" label="关注数" width="100" align="right">
          <template #default="{ row }">
            <span class="stat-badge">{{ row.num_followings?.toLocaleString() || 0 }}</span>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120" align="center">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click.stop="openUserDetail(row.user_id)">
              查看详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination-container">
        <el-config-provider :locale="zhCn">
          <el-pagination
            v-model:current-page="currentPage"
            v-model:page-size="pageSize"
            :page-sizes="[10, 20, 50, 100]"
            :total="total"
            layout="total, sizes, prev, pager, next, jumper"
            @size-change="handleSizeChange"
            @current-change="handlePageChange"
          />
        </el-config-provider>
      </div>
    </div>

    <!-- 用户详情抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      :title="currentUser?.name || '用户详情'"
      size="60%"
      :close-on-click-modal="false"
    >
      <div v-if="currentUser" class="user-detail">
        <!-- 用户画像 -->
        <div class="user-profile-card card">
          <div class="profile-header">
            <div class="profile-avatar">{{ getInitial(currentUser.name) }}</div>
            <div class="profile-info">
              <h2 class="profile-name">{{ currentUser.name }}</h2>
              <p class="profile-username">@{{ currentUser.user_name }}</p>
              <p class="profile-bio">{{ currentUser.bio || '暂无简介' }}</p>
            </div>
          </div>

          <!-- 统计数据 -->
          <div class="stats-grid">
            <div class="stat-item">
              <div class="stat-icon">📝</div>
              <div class="stat-value">{{ userStats.post_count?.toLocaleString() || 0 }}</div>
              <div class="stat-label">帖子</div>
            </div>
            <div class="stat-item">
              <div class="stat-icon">💬</div>
              <div class="stat-value">{{ userStats.comment_count?.toLocaleString() || 0 }}</div>
              <div class="stat-label">评论</div>
            </div>
            <div class="stat-item">
              <div class="stat-icon">❤️</div>
              <div class="stat-value">{{ userStats.total_likes_received?.toLocaleString() || 0 }}</div>
              <div class="stat-label">获赞</div>
            </div>
            <div class="stat-item">
              <div class="stat-icon">👥</div>
              <div class="stat-value">{{ currentUser.num_followers?.toLocaleString() || 0 }}</div>
              <div class="stat-label">粉丝</div>
            </div>
            <div class="stat-item">
              <div class="stat-icon">👤</div>
              <div class="stat-value">{{ currentUser.num_followings?.toLocaleString() || 0 }}</div>
              <div class="stat-label">关注</div>
            </div>
          </div>
        </div>

        <!-- 标签页 -->
        <el-tabs v-model="activeTab" class="detail-tabs">
          <!-- 发帖历史 -->
          <el-tab-pane label="📝 发帖历史" name="posts">
            <div class="tab-content">
              <!-- 时间线图表 -->
              <div class="card chart-card">
                <h3 class="section-title">发帖时间分布</h3>
                <div ref="postsTimelineChart" class="chart" style="height: 300px"></div>
              </div>

              <!-- 帖子列表 -->
              <div class="card posts-list-card">
                <h3 class="section-title">最近发帖</h3>
                <div v-if="userPosts.length === 0" class="empty-state">
                  <p>该用户暂无发帖</p>
                </div>
                <div v-else class="posts-list">
                  <div v-for="post in userPosts" :key="post.post_id" class="post-item">
                    <div class="post-header">
                      <span class="post-id">#{{ post.post_id }}</span>
                      <span class="post-time">{{ formatDate(post.created_at) }}</span>
                    </div>
                    <p class="post-content">{{ post.content }}</p>
                    <div class="post-stats">
                      <span>❤️ {{ post.num_likes || 0 }}</span>
                      <span>💬 {{ post.num_comments || 0 }}</span>
                      <span>🔁 {{ post.num_shares || 0 }}</span>
                      <span v-if="post.is_repost" class="repost-badge">转发</span>
                    </div>
                  </div>
                </div>

                <!-- 帖子分页 -->
                <div v-if="postTotal > postsPageSize" class="pagination-container">
                  <el-pagination
                    v-model:current-page="postsPage"
                    :page-size="postsPageSize"
                    :total="postTotal"
                    layout="prev, pager, next"
                    @current-change="handlePostsPageChange"
                    small
                  />
                </div>
              </div>
            </div>
          </el-tab-pane>

          <!-- 互动关系 -->
          <el-tab-pane label="🔗 互动关系" name="interactions">
            <div class="tab-content">
              <!-- 互动网络图 -->
              <div class="card chart-card">
                <h3 class="section-title">互动关系网络</h3>
                <div ref="interactionChart" class="chart" style="height: 400px"></div>
              </div>

              <!-- 关注列表 -->
              <el-row :gutter="16">
                <el-col :span="12">
                  <div class="card">
                    <h3 class="section-title">关注列表 ({{ interactions.following?.length || 0 }})</h3>
                    <div class="interaction-list">
                      <div
                        v-for="user in interactions.following?.slice(0, 10)"
                        :key="user.followee_id"
                        class="interaction-item"
                        @click="openUserDetail(user.followee_id)"
                      >
                        <div class="interaction-avatar">{{ getInitial(user.name) }}</div>
                        <span class="interaction-name">{{ user.name }}</span>
                      </div>
                      <div v-if="interactions.following?.length === 0" class="empty-state-small">
                        暂无关注
                      </div>
                    </div>
                  </div>
                </el-col>

                <el-col :span="12">
                  <div class="card">
                    <h3 class="section-title">粉丝列表 ({{ interactions.followers?.length || 0 }})</h3>
                    <div class="interaction-list">
                      <div
                        v-for="user in interactions.followers?.slice(0, 10)"
                        :key="user.follower_id"
                        class="interaction-item"
                        @click="openUserDetail(user.follower_id)"
                      >
                        <div class="interaction-avatar">{{ getInitial(user.name) }}</div>
                        <span class="interaction-name">{{ user.name }}</span>
                      </div>
                      <div v-if="interactions.followers?.length === 0" class="empty-state-small">
                        暂无粉丝
                      </div>
                    </div>
                  </div>
                </el-col>
              </el-row>
            </div>
          </el-tab-pane>
        </el-tabs>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import { userAPI } from '@/api'
import { ElMessage } from 'element-plus'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import * as echarts from 'echarts'

// 用户列表状态
const users = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)
const searchQuery = ref('')
const loading = ref(false)

// 用户详情状态
const drawerVisible = ref(false)
const currentUser = ref(null)
const userStats = ref({})
const userPosts = ref([])
const interactions = ref({})
const activeTab = ref('posts')

// 帖子分页
const postsPage = ref(1)
const postsPageSize = ref(10)
const postTotal = ref(0)

// 图表引用
const postsTimelineChart = ref(null)
const interactionChart = ref(null)

// 获取用户列表
const fetchUsers = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }
    if (searchQuery.value) {
      params.search = searchQuery.value
    }

    const response = await userAPI.getUsers(params)
    users.value = response.users || []
    total.value = response.total || 0
  } catch (error) {
    console.error('Failed to fetch users:', error)
    ElMessage.error('获取用户列表失败')
  } finally {
    loading.value = false
  }
}

// 获取用户详情
const fetchUserDetail = async (userId) => {
  try {
    const detail = await userAPI.getUserDetail(userId)
    currentUser.value = detail
    userStats.value = {
      post_count: detail.post_count,
      comment_count: detail.comment_count,
      total_likes_received: detail.total_likes_received,
      like_count: detail.like_count
    }
  } catch (error) {
    console.error('Failed to fetch user detail:', error)
    ElMessage.error('获取用户详情失败')
  }
}

// 获取用户帖子
const fetchUserPosts = async (userId) => {
  try {
    const response = await userAPI.getUserPosts(userId, {
      page: postsPage.value,
      page_size: postsPageSize.value
    })
    userPosts.value = response.posts || []
    postTotal.value = response.total || 0

    // 渲染时间线图表
    await nextTick()
    renderPostsTimeline()
  } catch (error) {
    console.error('Failed to fetch user posts:', error)
  }
}

// 获取用户互动
const fetchUserInteractions = async (userId) => {
  try {
    const data = await userAPI.getUserInteractions(userId)
    interactions.value = data

    // 渲染互动网络图
    await nextTick()
    renderInteractionNetwork()
  } catch (error) {
    console.error('Failed to fetch user interactions:', error)
  }
}

// 打开用户详情
const openUserDetail = async (userId) => {
  drawerVisible.value = true
  activeTab.value = 'posts'
  postsPage.value = 1

  await fetchUserDetail(userId)
  await fetchUserPosts(userId)
  await fetchUserInteractions(userId)
}

// 表格行点击
const handleRowClick = (row) => {
  openUserDetail(row.user_id)
}

// 搜索处理
const handleSearch = () => {
  currentPage.value = 1
  fetchUsers()
}

// 分页处理
const handlePageChange = (page) => {
  currentPage.value = page
  fetchUsers()
}

const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
  fetchUsers()
}

// 帖子分页处理
const handlePostsPageChange = (page) => {
  postsPage.value = page
  if (currentUser.value) {
    fetchUserPosts(currentUser.value.user_id)
  }
}

// 渲染发帖时间线图表
const renderPostsTimeline = () => {
  if (!postsTimelineChart.value || userPosts.value.length === 0) return

  const chart = echarts.init(postsTimelineChart.value)

  // 按日期统计帖子数
  const dateCounts = {}
  userPosts.value.forEach(post => {
    const date = new Date(post.created_at).toLocaleDateString('zh-CN')
    dateCounts[date] = (dateCounts[date] || 0) + 1
  })

  const dates = Object.keys(dateCounts).sort()
  const counts = dates.map(date => dateCounts[date])

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(26, 26, 46, 0.9)',
      borderColor: '#667eea',
      textStyle: { color: '#fff' }
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'category',
      data: dates,
      axisLine: { lineStyle: { color: '#2d2d44' } },
      axisLabel: { color: '#b8b8d1', rotate: 30 }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#2d2d44' } },
      splitLine: { lineStyle: { color: '#2d2d44', type: 'dashed' } },
      axisLabel: { color: '#b8b8d1' }
    },
    series: [{
      name: '发帖数',
      type: 'bar',
      data: counts,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#667eea' },
          { offset: 1, color: '#764ba2' }
        ])
      }
    }]
  }

  chart.setOption(option)
  window.addEventListener('resize', () => chart.resize())
}

// 渲染互动网络图
const renderInteractionNetwork = () => {
  if (!interactionChart.value) return

  const chart = echarts.init(interactionChart.value)

  // 构建节点和边
  const nodes = [
    {
      id: currentUser.value.user_id,
      name: currentUser.value.name,
      symbolSize: 60,
      itemStyle: { color: '#667eea' },
      label: { show: true }
    }
  ]

  const links = []

  // 添加关注的用户
  interactions.value.following?.slice(0, 20).forEach(user => {
    nodes.push({
      id: user.followee_id,
      name: user.name,
      symbolSize: 30,
      itemStyle: { color: '#4ECDC4' }
    })
    links.push({
      source: currentUser.value.user_id,
      target: user.followee_id,
      label: { show: false, formatter: '关注' }
    })
  })

  // 添加粉丝
  interactions.value.followers?.slice(0, 20).forEach(user => {
    // 避免重复添加（如果互相关注）
    if (!nodes.find(n => n.id === user.follower_id)) {
      nodes.push({
        id: user.follower_id,
        name: user.name,
        symbolSize: 30,
        itemStyle: { color: '#f093fb' }
      })
    }
    links.push({
      source: user.follower_id,
      target: currentUser.value.user_id,
      label: { show: false, formatter: '粉丝' }
    })
  })

  const option = {
    backgroundColor: 'transparent',
    tooltip: {
      formatter: params => {
        if (params.dataType === 'node') {
          return `${params.data.name}<br/>ID: ${params.data.id}`
        }
        return ''
      }
    },
    series: [{
      type: 'graph',
      layout: 'force',
      data: nodes,
      links: links,
      roam: true,
      // 关键配置：允许更大范围的缩放和拖拽
      scaleLimit: {
        min: 0.1,
        max: 20
      },
      center: ['50%', '50%'],
      zoom: 0.8,
      // 允许更大的平移范围
      left: 0,
      right: 0,
      top: 0,
      bottom: 0,
      draggable: true,
      coordinateSystem: null,
      label: {
        show: true,
        position: 'bottom',
        color: '#b8b8d1',
        fontSize: 12
      },
      force: {
        repulsion: 300,
        edgeLength: 120,
        gravity: 0.05,
        friction: 0.6,
        layoutAnimation: true
      },
      lineStyle: {
        color: '#667eea',
        curveness: 0.3,
        opacity: 0.5
      }
    }]
  }

  chart.setOption(option)
  window.addEventListener('resize', () => chart.resize())
}

// 工具函数
const getInitial = (name) => {
  if (!name) return '?'
  return name.charAt(0).toUpperCase()
}

const getRowClassName = ({ rowIndex }) => {
  return rowIndex % 2 === 1 ? 'clickable-row stripe-row' : 'clickable-row'
}

const formatDate = (dateString) => {
  if (!dateString) return ''
  return new Date(dateString).toLocaleString('zh-CN')
}

// 生命周期
onMounted(() => {
  fetchUsers()
})

// 监听抽屉关闭，清理图表
watch(drawerVisible, (newVal) => {
  if (!newVal) {
    currentUser.value = null
    userStats.value = {}
    userPosts.value = []
    interactions.value = {}
  }
})
</script>

<style scoped>
.users-page {
  min-height: 100%;
}

/* 页面标题 */
.page-header {
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl);
  margin-bottom: var(--spacing-xl);
  text-align: center;
  box-shadow: var(--shadow-glow);
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: white;
  margin: 0 0 var(--spacing-sm) 0;
}

.page-subtitle {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.9);
  margin: 0;
}

/* 筛选区域 */
.filters-section {
  margin-bottom: var(--spacing-xl);
  padding: var(--spacing-lg);
}

/* 修复el-row重叠问题 */
.filters-section :deep(.el-row) {
  display: flex;
  flex-wrap: wrap;
  margin-left: -8px !important;
  margin-right: -8px !important;
}

.filters-section :deep(.el-col) {
  padding-left: 8px !important;
  padding-right: 8px !important;
  margin-bottom: 0 !important;
}

/* Element Plus组件深色主题样式 */
.filters-section :deep(.el-input__wrapper) {
  background-color: var(--bg-tertiary) !important;
  box-shadow: none !important;
  border: 1px solid var(--border-color) !important;
}

.filters-section :deep(.el-input__wrapper:hover),
.filters-section :deep(.el-input__wrapper.is-focus) {
  border-color: var(--primary-color) !important;
  box-shadow: none !important;
}

.filters-section :deep(.el-input__inner) {
  color: var(--text-primary) !important;
  background-color: transparent !important;
}

/* 移除输入框内所有白色元素 */
.filters-section :deep(.el-input__prefix),
.filters-section :deep(.el-input__suffix),
.filters-section :deep(.el-input__prefix-inner),
.filters-section :deep(.el-input__suffix-inner) {
  background-color: transparent !important;
}

/* 移除append按钮的白框 */
.filters-section :deep(.el-input-group__append) {
  background-color: transparent !important;
  border: none !important;
  box-shadow: none !important;
  padding: 0 !important;
}

.filters-section :deep(.el-button--primary) {
  background: var(--primary-gradient) !important;
  border: none !important;
  box-shadow: none !important;
  margin-left: -1px !important;
  height: 40px !important;
  padding: 0 20px !important;
}

/* 用户搜索框额外高度 */
.user-search-input :deep(.el-input__wrapper) {
  min-height: 48px !important;
}

.user-search-input :deep(.el-input__inner) {
  height: 48px !important;
  line-height: 48px !important;
  font-size: 15px !important;
}

.user-search-input :deep(.el-input-group__append) {
  padding: 0 !important;
}

.user-search-input :deep(.el-button--primary) {
  height: 48px !important;
  padding: 0 24px !important;
  font-size: 15px !important;
}

.search-icon {
  font-size: 18px;
}

/* 用户表格 */
.users-table-card {
  padding: var(--spacing-lg);
}

/* 表格行样式 - 深色主题 */
.users-table :deep(.el-table__row) {
  background-color: var(--bg-secondary) !important;
  color: var(--text-primary) !important;
}

.users-table :deep(.el-table__row.stripe-row) {
  background-color: var(--bg-tertiary) !important;
}

.users-table :deep(.clickable-row) {
  cursor: pointer;
  transition: background-color 0.2s;
}

.users-table :deep(.clickable-row:hover) {
  background-color: var(--bg-tertiary) !important;
}

.user-name-cell {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.user-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 14px;
}

.user-name {
  font-weight: 500;
  color: var(--text-primary);
}

.stat-badge {
  color: var(--primary-color);
  font-weight: 600;
}

/* 简介单元格 */
.bio-cell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  cursor: help;
}

/* 分页 */
.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: var(--spacing-lg);
  padding-top: var(--spacing-lg);
  border-top: 1px solid var(--border-color);
}

/* 用户详情 */
.user-detail {
  padding: var(--spacing-md);
}

.user-profile-card {
  padding: var(--spacing-xl);
  margin-bottom: var(--spacing-lg);
}

.profile-header {
  display: flex;
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
}

.profile-avatar {
  width: 80px;
  height: 80px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 700;
  font-size: 32px;
  flex-shrink: 0;
}

.profile-info {
  flex: 1;
}

.profile-name {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-xs) 0;
}

.profile-username {
  font-size: 14px;
  color: var(--text-secondary);
  margin: 0 0 var(--spacing-sm) 0;
}

.profile-bio {
  font-size: 14px;
  color: var(--text-muted);
  line-height: 1.6;
  margin: 0;
}

/* 统计网格 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(100px, 1fr));
  gap: var(--spacing-lg);
}

.stat-item {
  text-align: center;
  padding: var(--spacing-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  transition: transform 0.3s ease;
}

.stat-item:hover {
  transform: translateY(-4px);
}

.stat-icon {
  font-size: 24px;
  margin-bottom: var(--spacing-xs);
}

.stat-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--primary-color);
  margin-bottom: var(--spacing-xs);
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
}

/* 标签页 */
.detail-tabs {
  margin-top: var(--spacing-lg);
}

.tab-content {
  padding-top: var(--spacing-md);
}

/* 区块标题 */
.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-lg) 0;
  padding-bottom: var(--spacing-sm);
  border-bottom: 2px solid var(--border-color);
}

/* 图表卡片 */
.chart-card {
  padding: var(--spacing-lg);
  margin-bottom: var(--spacing-lg);
}

.chart {
  width: 100%;
}

/* 帖子列表 */
.posts-list-card {
  padding: var(--spacing-lg);
  margin-top: var(--spacing-lg);
}

.posts-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.post-item {
  padding: var(--spacing-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  border-left: 3px solid var(--primary-color);
  transition: all 0.3s ease;
}

.post-item:hover {
  background: var(--bg-color);
  transform: translateX(4px);
}

.post-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-sm);
}

.post-id {
  font-size: 12px;
  color: var(--primary-color);
  font-weight: 600;
}

.post-time {
  font-size: 12px;
  color: var(--text-muted);
}

.post-content {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.6;
  margin: 0 0 var(--spacing-sm) 0;
}

.post-stats {
  display: flex;
  gap: var(--spacing-md);
  font-size: 12px;
  color: var(--text-secondary);
}

.repost-badge {
  background: linear-gradient(135deg, #4ECDC4 0%, #44A08D 100%);
  color: white;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 600;
}

/* 互动列表 */
.interaction-list {
  max-height: 300px;
  overflow-y: auto;
}

.interaction-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
  padding: var(--spacing-sm);
  margin-bottom: var(--spacing-xs);
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.3s ease;
}

.interaction-item:hover {
  background: var(--bg-color);
  transform: translateX(4px);
}

.interaction-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 12px;
  flex-shrink: 0;
}

.interaction-name {
  font-size: 14px;
  color: var(--text-primary);
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: var(--spacing-xl);
  color: var(--text-muted);
}

.empty-state-small {
  text-align: center;
  padding: var(--spacing-md);
  color: var(--text-muted);
  font-size: 12px;
}

/* 加载容器 */
.loading-container {
  padding: var(--spacing-xl);
}

/* ========================================
   Element Plus 深色主题全局覆盖
   ======================================== */

/* 表格header - 修复白色背景 */
.users-table :deep(.el-table__header-wrapper) {
  background-color: var(--bg-secondary) !important;
}

.users-table :deep(th.el-table__cell) {
  background-color: var(--bg-secondary) !important;
  color: var(--text-primary) !important;
  border-bottom: 2px solid var(--border-color) !important;
  font-weight: 600;
}

.users-table :deep(td.el-table__cell) {
  color: var(--text-primary) !important;
  border-bottom: 1px solid var(--border-color) !important;
}

/* 搜索框 - 修复白色边框 */
.search-card :deep(.el-input__wrapper) {
  background-color: var(--bg-tertiary) !important;
  border-color: var(--border-color) !important;
  box-shadow: none !important;
}

.search-card :deep(.el-input__wrapper:hover) {
  border-color: var(--primary-color) !important;
}

.search-card :deep(.el-input__inner) {
  color: var(--text-primary) !important;
}

.search-card :deep(.el-input-group__append),
.search-card :deep(.el-input-group__prepend) {
  background-color: var(--bg-secondary) !important;
  border-color: var(--border-color) !important;
  color: var(--text-primary) !important;
}

/* 抽屉 - 修复白色边框 */
:deep(.el-drawer) {
  background-color: var(--bg-secondary) !important;
  border-left: 1px solid var(--border-color) !important;
  box-shadow: -4px 0 16px rgba(0, 0, 0, 0.3) !important;
}

:deep(.el-drawer__header) {
  color: var(--text-primary) !important;
  border-bottom: 2px solid var(--border-color) !important;
}

:deep(.el-drawer__title) {
  color: var(--text-primary) !important;
}

:deep(.el-drawer__body) {
  background-color: var(--bg-secondary) !important;
}

/* 标签页 */
:deep(.el-tabs__item) {
  color: var(--text-secondary) !important;
}

:deep(.el-tabs__item.is-active) {
  color: var(--primary-color) !important;
}

/* 分页器 */
:deep(.el-pagination button) {
  background-color: var(--bg-tertiary) !important;
  color: var(--text-secondary) !important;
}

:deep(.el-pager li) {
  background-color: var(--bg-tertiary) !important;
  color: var(--text-secondary) !important;
}

:deep(.el-pager li.is-active) {
  background-color: var(--primary-color) !important;
  color: white !important;
}

/* 搜索框完整样式重写 */
.search-section :deep(.el-input) {
  border-radius: 12px;
}

.search-section :deep(.el-input__wrapper) {
  background-color: var(--bg-tertiary) !important;
  border: none !important;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3) !important;
  border-radius: 12px !important;
  transition: all 0.3s ease;
  padding: 1px !important;
}

.search-section :deep(.el-input__wrapper:hover) {
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.4) !important;
  transform: translateY(-1px);
}

.search-section :deep(.el-input__wrapper.is-focus) {
  box-shadow: 0 4px 16px rgba(102, 126, 234, 0.4) !important;
}

.search-section :deep(.el-input__inner) {
  font-size: 15px;
  padding-left: 12px;
  background: transparent !important;
  border: none !important;
}

/* 修复前缀图标 - 防止闪烁 */
.search-section :deep(.el-input__prefix) {
  margin-left: 8px;
  transition: none !important;
}

.search-section :deep(.el-input__prefix-inner) {
  display: inline-flex !important;
  align-items: center !important;
  transition: none !important;
}

.search-icon {
  font-size: 18px;
  display: inline-block;
  line-height: 1;
  transition: none !important;
}

/* 后缀按钮区域 */
.search-section :deep(.el-input-group__append) {
  background: transparent !important;
  border: none !important;
  padding: 0;
  margin-left: 0;
  box-shadow: none !important;
}

.search-section :deep(.el-input-group__append .el-button) {
  border-radius: 0 12px 12px 0 !important;
  height: 100%;
  margin: 0;
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
}

.search-section :deep(.el-input-group__append .el-button:hover),
.search-section :deep(.el-input-group__append .el-button:focus),
.search-section :deep(.el-input-group__append .el-button:active) {
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
}

/* 额外的强制覆盖 - Element Plus 按钮 */
.search-section :deep(.el-input-group__append),
.search-section :deep(.el-input-group__append *) {
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
}

.search-section :deep(.el-button.el-button--primary) {
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
}

.search-section :deep(.el-button.el-button--primary:hover),
.search-section :deep(.el-button.el-button--primary:focus),
.search-section :deep(.el-button.el-button--primary:active),
.search-section :deep(.el-button.el-button--primary.is-active) {
  border: none !important;
  box-shadow: none !important;
  outline: none !important;
}

.search-section :deep(.el-input-group__append .el-button::before),
.search-section :deep(.el-input-group__append .el-button::after) {
  display: none !important;
  border: none !important;
}

/* 清除按钮样式 */
.search-section :deep(.el-input__suffix) {
  transition: none !important;
}

.search-section :deep(.el-input__suffix-inner) {
  transition: none !important;
}

.search-section :deep(.el-icon) {
  transition: none !important;
  font-size: 14px !important;
}
</style>
