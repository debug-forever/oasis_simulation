<template>
  <div class="posts-page">
    <!-- 页面标题 -->
    <div class="page-header gradient-bg">
      <h1 class="page-title">📝 内容浏览</h1>
      <p class="page-subtitle">浏览所有帖子和评论，探索社区动态</p>
    </div>

    <!-- 筛选和搜索区域 -->
    <div class="filters-section card">
      <el-row :gutter="16">
        <!-- 搜索框 -->
        <el-col :span="9">
          <el-input
            v-model="searchQuery"
            placeholder="搜索帖子内容..."
            size="large"
            clearable
            @clear="handleSearch"
            @keyup.enter="handleSearch"
            class="search-input"
          >
            <template #prefix>
              <span class="search-icon">🔍</span>
            </template>
            <template #append>
              <el-button @click="handleSearch" :loading="loading" type="primary">搜索</el-button>
            </template>
          </el-input>
        </el-col>

        <!-- 间隔 -->
        <el-col :span="4"></el-col>

        <!-- 类型筛选 -->
        <el-col :span="5">
          <el-select
            v-model="postType"
            placeholder="帖子类型"
            size="large"
            @change="handleSearch"
            style="width: 100%"
          >
            <el-option label="全部帖子" value="all" />
            <el-option label="原创帖子" value="original" />
            <el-option label="转发帖子" value="repost" />
          </el-select>
        </el-col>

        <!-- 排序方式 -->
        <el-col :span="6">
          <el-select
            v-model="sortBy"
            placeholder="排序方式"
            size="large"
            @change="handleSearch"
            style="width: 100%"
          >
            <el-option label="最新发布" value="time_desc" />
            <el-option label="最多点赞" value="likes_desc" />
            <el-option label="最多评论" value="comments_desc" />
          </el-select>
        </el-col>
      </el-row>

      <!-- 时间范围选择 -->
      <el-row :gutter="16" style="margin-top: 16px">
        <el-col :span="12">
          <el-date-picker
            v-model="timeRange"
            type="datetimerange"
            range-separator="至"
            start-placeholder="开始时间"
            end-placeholder="结束时间"
            @change="handleSearch"
            style="width: 100%"
          />
        </el-col>
        <el-col :span="12">
          <div class="stats-info">
            <span class="stats-text">共找到 <strong>{{ total }}</strong> 条帖子</span>
          </div>
        </el-col>
      </el-row>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading && posts.length === 0" class="loading-container">
      <el-skeleton :rows="8" animated />
    </div>

    <!-- 帖子列表 -->
    <div v-else-if="posts.length > 0" class="posts-grid">
      <div
        v-for="post in posts"
        :key="post.post_id"
        class="post-card card fade-in"
        @click="openPostDetail(post.post_id)"
      >
        <!-- 帖子头部 -->
        <div class="post-header">
          <div class="user-info">
            <div class="user-avatar">{{ getInitial(post.user_name) }}</div>
            <div class="user-details">
              <div class="user-name">{{ post.user_name }}</div>
              <div class="post-time">⏰ {{ formatDate(post.created_at) }}</div>
            </div>
          </div>
          <div v-if="post.is_repost" class="repost-badge">🔁 转发</div>
        </div>

        <!-- 帖子内容 -->
        <div class="post-content">
          <p class="content-text">{{ post.content }}</p>
          
          <!-- 转发引用内容 -->
          <div v-if="post.quote_content" class="quote-content">
            <div class="quote-indicator">💬 引用内容</div>
            <p class="quote-text">{{ post.quote_content }}</p>
          </div>
        </div>

        <!-- 帖子互动数据 -->
        <div class="post-stats">
          <span class="stat-item">
            <span class="stat-icon">❤️</span>
            <span class="stat-value">{{ post.num_likes || 0 }}</span>
          </span>
          <span class="stat-item">
            <span class="stat-icon">💬</span>
            <span class="stat-value">{{ post.comment_count || 0 }}</span>
          </span>
          <span class="stat-item">
            <span class="stat-icon">🔁</span>
            <span class="stat-value">{{ post.num_shares || 0 }}</span>
          </span>
          <span class="stat-item dislike">
            <span class="stat-icon">👎</span>
            <span class="stat-value">{{ post.num_dislikes || 0 }}</span>
          </span>
          <el-button type="primary" size="small" class="detail-btn" @click.stop="openPostDetail(post.post_id)">
            查看详情 →
          </el-button>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state card">
      <div class="empty-icon">📭</div>
      <p class="empty-text">暂无帖子数据</p>
      <p class="empty-hint">尝试调整筛选条件或清空搜索</p>
    </div>

    <!-- 分页 -->
    <div v-if="total > 0" class="pagination-container">
      <el-config-provider :locale="zhCn">
        <el-pagination
          v-model:current-page="currentPage"
          v-model:page-size="pageSize"
          :page-sizes="[12, 24, 48, 96]"
          :total="total"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSizeChange"
          @current-change="handlePageChange"
        />
      </el-config-provider>
    </div>

    <!-- 帖子详情抽屉 -->
    <el-drawer
      v-model="drawerVisible"
      :title="`帖子详情 #${currentPost?.post_id || ''}`"
      size="60%"
      :close-on-click-modal="false"
    >
      <div v-if="currentPost" class="post-detail">
        <!-- 帖子完整信息 -->
        <div class="post-detail-card card">
          <div class="detail-header">
            <div class="detail-user-info">
              <div class="detail-avatar">{{ getInitial(currentPost.user_name) }}</div>
              <div class="detail-user-details">
                <div class="detail-user-name">{{ currentPost.user_name }}</div>
                <div class="detail-post-time">📅 {{ formatDate(currentPost.created_at) }}</div>
              </div>
            </div>
            <div v-if="currentPost.is_repost" class="detail-repost-badge">🔁 转发帖</div>
          </div>

          <!-- 完整内容 -->
          <div class="detail-content">
            <p class="detail-content-text">{{ currentPost.content }}</p>
            
            <!-- 转发引用 -->
            <div v-if="currentPost.quote_content" class="detail-quote-content">
              <div class="quote-indicator">💬 引用内容</div>
              <p class="quote-text">{{ currentPost.quote_content }}</p>
            </div>
          </div>

          <!-- 详细互动数据 -->
          <div class="detail-stats-grid">
            <div class="detail-stat-item">
              <div class="detail-stat-icon">❤️</div>
              <div class="detail-stat-value">{{ currentPost.num_likes || 0 }}</div>
              <div class="detail-stat-label">点赞</div>
            </div>
            <div class="detail-stat-item">
              <div class="detail-stat-icon">👎</div>
              <div class="detail-stat-value">{{ currentPost.num_dislikes || 0 }}</div>
              <div class="detail-stat-label">踩</div>
            </div>
            <div class="detail-stat-item">
              <div class="detail-stat-icon">💬</div>
              <div class="detail-stat-value">{{ currentPost.comment_count || 0 }}</div>
              <div class="detail-stat-label">评论</div>
            </div>
            <div class="detail-stat-item">
              <div class="detail-stat-icon">🔁</div>
              <div class="detail-stat-value">{{ currentPost.num_shares || 0 }}</div>
              <div class="detail-stat-label">转发</div>
            </div>
          </div>
        </div>

        <!-- 评论区域 -->
        <div class="comments-section">
          <h3 class="section-title">💬 评论 ({{ comments.length }})</h3>

          <!-- 评论时间分布图 -->
          <div v-if="comments.length > 0" class="card chart-card">
            <h4 class="chart-title">评论时间分布</h4>
            <div ref="commentsTimelineChart" class="chart" style="height: 250px"></div>
          </div>

          <!-- 评论列表 -->
          <div v-if="comments.length > 0" class="comments-list card">
            <div
              v-for="comment in comments"
              :key="comment.comment_id"
              class="comment-item"
            >
              <div class="comment-header">
                <div class="comment-user-info">
                  <div class="comment-avatar">{{ getInitial(comment.user_name) }}</div>
                  <div class="comment-user-details">
                    <span class="comment-user-name">{{ comment.user_name }}</span>
                    <span class="comment-time">{{ formatDate(comment.created_at) }}</span>
                  </div>
                </div>
                <div class="comment-stats">
                  <span class="comment-stat">❤️ {{ comment.num_likes || 0 }}</span>
                  <span class="comment-stat">👎 {{ comment.num_dislikes || 0 }}</span>
                </div>
              </div>
              <div class="comment-content">{{ comment.content }}</div>
            </div>
          </div>

          <!-- 无评论状态 -->
          <div v-else class="empty-comments card">
            <div class="empty-icon">💬</div>
            <p class="empty-text">暂无评论</p>
          </div>
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup>
import { ref, onMounted, watch, nextTick } from 'vue'
import { postAPI } from '@/api'
import { ElMessage } from 'element-plus'
import zhCn from 'element-plus/dist/locale/zh-cn.mjs'
import * as echarts from 'echarts'

// 帖子列表状态
const posts = ref([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(12)
const loading = ref(false)

// 筛选条件
const searchQuery = ref('')
const postType = ref('all')
const sortBy = ref('time_desc')
const timeRange = ref(null)

// 详情状态
const drawerVisible = ref(false)
const currentPost = ref(null)
const comments = ref([])

// 图表引用
const commentsTimelineChart = ref(null)

// 获取帖子列表
const fetchPosts = async () => {
  loading.value = true
  try {
    const params = {
      page: currentPage.value,
      page_size: pageSize.value
    }

    // 添加筛选条件
    if (postType.value && postType.value !== 'all') {
      params.post_type = postType.value
    }

    if (timeRange.value && timeRange.value.length === 2) {
      params.start_time = timeRange.value[0].toISOString()
      params.end_time = timeRange.value[1].toISOString()
    }

    const response = await postAPI.getPosts(params)
    
    // 获取每个帖子的评论数
    let postsWithComments = response.posts || []
    
    // 客户端排序（如果需要）
    if (sortBy.value === 'likes_desc') {
      postsWithComments.sort((a, b) => (b.num_likes || 0) - (a.num_likes || 0))
    }

    // 客户端搜索过滤
    if (searchQuery.value) {
      const query = searchQuery.value.toLowerCase()
      postsWithComments = postsWithComments.filter(post => 
        post.content?.toLowerCase().includes(query) ||
        post.quote_content?.toLowerCase().includes(query)
      )
    }

    posts.value = postsWithComments
    total.value = response.total || 0
  } catch (error) {
    console.error('Failed to fetch posts:', error)
    ElMessage.error('获取帖子列表失败')
  } finally {
    loading.value = false
  }
}

// 获取帖子详情
const fetchPostDetail = async (postId) => {
  try {
    const detail = await postAPI.getPostDetail(postId)
    currentPost.value = detail
    comments.value = detail.comments || []

    // 渲染评论时间线图表
    await nextTick()
    renderCommentsTimeline()
  } catch (error) {
    console.error('Failed to fetch post detail:', error)
    ElMessage.error('获取帖子详情失败')
  }
}

// 打开帖子详情
const openPostDetail = async (postId) => {
  drawerVisible.value = true
  await fetchPostDetail(postId)
}

// 搜索处理
const handleSearch = () => {
  currentPage.value = 1
  fetchPosts()
}

// 分页处理
const handlePageChange = (page) => {
  currentPage.value = page
  fetchPosts()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

const handleSizeChange = (size) => {
  pageSize.value = size
  currentPage.value = 1
  fetchPosts()
}

// 渲染评论时间线图表
const renderCommentsTimeline = () => {
  if (!commentsTimelineChart.value || comments.value.length === 0) return

  const chart = echarts.init(commentsTimelineChart.value)

  // 按时间统计评论数
  const timeCounts = {}
  comments.value.forEach(comment => {
    const date = new Date(comment.created_at).toLocaleString('zh-CN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    })
    timeCounts[date] = (timeCounts[date] || 0) + 1
  })

  const times = Object.keys(timeCounts)
  const counts = times.map(time => timeCounts[time])

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
      data: times,
      axisLine: { lineStyle: { color: '#2d2d44' } },
      axisLabel: { color: '#b8b8d1', rotate: 30, fontSize: 10 }
    },
    yAxis: {
      type: 'value',
      axisLine: { lineStyle: { color: '#2d2d44' } },
      splitLine: { lineStyle: { color: '#2d2d44', type: 'dashed' } },
      axisLabel: { color: '#b8b8d1' }
    },
    series: [{
      name: '评论数',
      type: 'bar',
      data: counts,
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: '#667eea' },
          { offset: 1, color: '#764ba2' }
        ]),
        borderRadius: [4, 4, 0, 0]
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

const formatDate = (dateString) => {
  if (!dateString) return ''
  const date = new Date(dateString)
  const now = new Date()
  const diff = now - date
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  return date.toLocaleString('zh-CN')
}

// 生命周期
onMounted(() => {
  fetchPosts()
})

// 监听抽屉关闭
watch(drawerVisible, (newVal) => {
  if (!newVal) {
    currentPost.value = null
    comments.value = []
  }
})
</script>

<style scoped>
.posts-page {
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

.filters-section :deep(.el-select .el-input__wrapper) {
  background-color: var(--bg-tertiary) !important;
}

.filters-section :deep(.el-button--primary) {
  background: var(--primary-gradient) !important;
  border: none !important;
  box-shadow: none !important;
  margin-left: -1px !important;
  height: 40px !important;
  padding: 0 20px !important;
}

.filters-section :deep(.el-date-editor) {
  background-color: var(--bg-tertiary) !important;
}

.filters-section :deep(.el-date-editor .el-input__wrapper) {
  background-color: var(--bg-tertiary) !important;
  box-shadow: none !important;
  border: 1px solid var(--border-color) !important;
}

.filters-section :deep(.el-date-editor .el-input__wrapper:hover) {
  border-color: var(--primary-color) !important;
  box-shadow: none !important;
}

.filters-section :deep(.el-range-separator) {
  color: var(--text-secondary) !important;
}

.filters-section :deep(.el-range-input) {
  background-color: transparent !important;
  color: var(--text-primary) !important;
}

.search-icon {
  font-size: 18px;
}

.stats-info {
  display: flex;
  align-items: center;
  height: 100%;
  padding-left: var(--spacing-md);
}

.stats-text {
  color: var(--text-secondary);
  font-size: 14px;
}

.stats-text strong {
  color: var(--primary-color);
  font-size: 16px;
  font-weight: 700;
}

/* 帖子网格 */
.posts-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
  gap: var(--spacing-lg);
  margin-bottom: var(--spacing-xl);
}

/* 帖子卡片 */
.post-card {
  cursor: pointer;
  transition: all 0.3s ease;
  padding: var(--spacing-lg);
  display: flex;
  flex-direction: column;
  gap: var(--spacing-md);
}

.post-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-glow);
  border-color: var(--primary-color);
}

.post-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
}

.user-info {
  display: flex;
  gap: var(--spacing-sm);
  flex: 1;
}

.user-avatar {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 16px;
  flex-shrink: 0;
}

.user-details {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.user-name {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 14px;
}

.post-time {
  font-size: 12px;
  color: var(--text-muted);
}

.repost-badge {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: white;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

/* 帖子内容 */
.post-content {
  flex: 1;
}

.content-text {
  color: var(--text-primary);
  line-height: 1.6;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 4;
  line-clamp: 4;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.quote-content {
  margin-top: var(--spacing-sm);
  padding: var(--spacing-sm);
  background: var(--bg-tertiary);
  border-left: 3px solid var(--primary-color);
  border-radius: var(--radius-sm);
}

.quote-indicator {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.quote-text {
  color: var(--text-secondary);
  font-size: 13px;
  margin: 0;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

/* 帖子统计 */
.post-stats {
  display: flex;
  gap: var(--spacing-md);
  align-items: center;
  padding-top: var(--spacing-sm);
  border-top: 1px solid var(--border-color);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 13px;
  color: var(--text-secondary);
}

.stat-item.dislike {
  color: var(--text-muted);
}

.stat-icon {
  font-size: 16px;
}

.stat-value {
  font-weight: 600;
}

.detail-btn {
  margin-left: auto;
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: var(--spacing-xl) * 2;
}

.empty-icon {
  font-size: 64px;
  margin-bottom: var(--spacing-md);
}

.empty-text {
  font-size: 18px;
  color: var(--text-secondary);
  margin: 0 0 var(--spacing-sm) 0;
}

.empty-hint {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0;
}

/* 分页 */
.pagination-container {
  display: flex;
  justify-content: center;
  margin-top: var(--spacing-lg);
  padding: var(--spacing-lg) 0;
}

/* 详情页 */
.post-detail {
  padding: var(--spacing-md);
}

.post-detail-card {
  margin-bottom: var(--spacing-lg);
}

.detail-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: var(--spacing-lg);
}

.detail-user-info {
  display: flex;
  gap: var(--spacing-md);
}

.detail-avatar {
  width: 60px;
  height: 60px;
  border-radius: 50%;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 700;
  font-size: 24px;
}

.detail-user-details {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-xs);
}

.detail-user-name {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.detail-post-time {
  font-size: 14px;
  color: var(--text-muted);
}

.detail-repost-badge {
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  color: white;
  padding: 6px 16px;
  border-radius: 16px;
  font-size: 14px;
  font-weight: 600;
}

.detail-content {
  margin-bottom: var(--spacing-lg);
}

.detail-content-text {
  color: var(--text-primary);
  line-height: 1.8;
  font-size: 15px;
  margin: 0;
  white-space: pre-wrap;
}

.detail-quote-content {
  margin-top: var(--spacing-md);
  padding: var(--spacing-md);
  background: var(--bg-tertiary);
  border-left: 4px solid var(--primary-color);
  border-radius: var(--radius-sm);
}

/* 详细统计 */
.detail-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-md);
}

.detail-stat-item {
  text-align: center;
  padding: var(--spacing-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  transition: transform 0.3s ease;
}

.detail-stat-item:hover {
  transform: translateY(-2px);
}

.detail-stat-icon {
  font-size: 28px;
  margin-bottom: var(--spacing-xs);
}

.detail-stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--primary-color);
  margin-bottom: var(--spacing-xs);
}

.detail-stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  text-transform: uppercase;
}

/* 评论区域 */
.comments-section {
  margin-top: var(--spacing-xl);
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-lg) 0;
  padding-bottom: var(--spacing-sm);
  border-bottom: 2px solid var(--border-color);
}

.chart-card {
  margin-bottom: var(--spacing-lg);
}

.chart-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-secondary);
  margin: 0 0 var(--spacing-md) 0;
}

.comments-list {
  padding: var(--spacing-md);
}

.comment-item {
  padding: var(--spacing-md);
  border-bottom: 1px solid var(--border-color);
}

.comment-item:last-child {
  border-bottom: none;
}

.comment-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-sm);
}

.comment-user-info {
  display: flex;
  gap: var(--spacing-sm);
  align-items: center;
}

.comment-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: 600;
  font-size: 14px;
}

.comment-user-details {
  display: flex;
  gap: var(--spacing-sm);
  align-items: center;
}

.comment-user-name {
  font-weight: 600;
  color: var(--text-primary);
  font-size: 14px;
}

.comment-time {
  font-size: 12px;
  color: var(--text-muted);
}

.comment-stats {
  display: flex;
  gap: var(--spacing-sm);
}

.comment-stat {
  font-size: 12px;
  color: var(--text-muted);
}

.comment-content {
  color: var(--text-secondary);
  line-height: 1.6;
  font-size: 14px;
  padding-left: 40px;
}

.empty-comments {
  text-align: center;
  padding: var(--spacing-xl);
}

/* 加载容器 */
.loading-container {
  padding: var(--spacing-xl);
}

/* Drawer抽屉深色主题 */
:deep(.el-drawer) {
  background-color: var(--bg-color) !important;
  border: none !important;
}

:deep(.el-drawer__header) {
  color: var(--text-primary) !important;
  border-bottom: 1px solid var(--border-color) !important;
  background-color: var(--bg-color) !important;
  margin-bottom: 0 !important;
}

:deep(.el-drawer__body) {
  background-color: var(--bg-color) !important;
}

:deep(.el-drawer__title) {
  color: var(--text-primary) !important;
}

:deep(.el-drawer__close-btn) {
  color: var(--text-secondary) !important;
}

:deep(.el-drawer__close-btn:hover) {
  color: var(--text-primary) !important;
}

/* 下拉菜单深色主题 */
:deep(.el-select-dropdown) {
  background-color: var(--bg-secondary) !important;
  border: 1px solid var(--border-color) !important;
}

:deep(.el-select-dropdown__item) {
  color: var(--text-primary) !important;
}

:deep(.el-select-dropdown__item:hover) {
  background-color: var(--bg-tertiary) !important;
}

:deep(.el-select-dropdown__item.selected) {
  color: var(--primary-color) !important;
}

/* 日期选择器下拉深色主题 */
:deep(.el-picker-panel) {
  background-color: var(--bg-secondary) !important;
  border: 1px solid var(--border-color) !important;
  box-shadow: var(--shadow-lg) !important;
}

:deep(.el-picker-panel__body) {
  padding: 12px !important;
}

:deep(.el-date-range-picker__content) {
  padding: 12px !important;
  margin: 0 !important;
}

:deep(.el-date-picker__header) {
  color: var(--text-primary) !important;
  margin: 8px 0 !important;
  padding: 0 12px !important;
}

:deep(.el-date-picker__header-label) {
  color: var(--text-primary) !important;
}

:deep(.el-picker-panel__icon-btn) {
  color: var(--text-secondary) !important;
}

:deep(.el-picker-panel__icon-btn:hover) {
  color: var(--primary-color) !important;
}

:deep(.el-picker-panel__content) {
  color: var(--text-primary) !important;
  margin: 0 !important;
}

:deep(.el-date-table) {
  margin: 0 !important;
}

:deep(.el-date-table th) {
  color: var(--text-secondary) !important;
  padding: 4px !important;
  border: none !important;
}

:deep(.el-date-table td) {
  color: var(--text-primary) !important;
  padding: 4px !important;
}

:deep(.el-date-table td .el-date-table-cell) {
  padding: 3px 0 !important;
  height: 32px !important;
}

:deep(.el-date-table td.available:hover) {
  color: var(--primary-color) !important;
}

:deep(.el-date-table td.current:not(.disabled)) {
  color: var(--primary-color) !important;
}

:deep(.el-date-table td.today .el-date-table-cell__text) {
  color: var(--primary-color) !important;
  font-weight: 700 !important;
}

:deep(.el-date-table td.in-range .el-date-table-cell) {
  background-color: rgba(102, 126, 234, 0.1) !important;
}

:deep(.el-date-table td.start-date .el-date-table-cell),
:deep(.el-date-table td.end-date .el-date-table-cell) {
  background-color: var(--primary-color) !important;
  color: white !important;
}

/* 时间选择器面板 */
:deep(.el-date-range-picker__time-header) {
  padding: 8px 12px !important;
  border-top: 1px solid var(--border-color) !important;
  margin-top: 12px !important;
}

:deep(.el-time-panel) {
  background-color: var(--bg-secondary) !important;
  border: 1px solid var(--border-color) !important;
  box-shadow: var(--shadow-lg) !important;
}

:deep(.el-time-panel__content) {
  background-color: var(--bg-secondary) !important;
}

:deep(.el-time-spinner__item) {
  color: var(--text-primary) !important;
}

:deep(.el-time-spinner__item:hover) {
  background-color: var(--bg-tertiary) !important;
}

:deep(.el-time-spinner__item.is-active) {
  color: var(--primary-color) !important;
  font-weight: 700 !important;
}

/* 日期范围选择器的时间输入框 */
:deep(.el-date-range-picker__time-picker-wrap) {
  padding: 8px 12px !important;
}

:deep(.el-date-range-picker__time-picker-wrap .el-input) {
  width: 100% !important;
}

:deep(.el-date-range-picker__time-picker-wrap .el-input__wrapper) {
  background-color: var(--bg-tertiary) !important;
  box-shadow: none !important;
  border: 1px solid var(--border-color) !important;
  padding: 4px 8px !important;
}

:deep(.el-date-range-picker__time-picker-wrap .el-input__inner) {
  color: var(--text-primary) !important;
  background-color: transparent !important;
  text-align: center !important;
}

/* 分页器深色主题 */
:deep(.el-pagination) {
  color: var(--text-primary) !important;
}

:deep(.el-pagination button) {
  background-color: var(--bg-secondary) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--border-color) !important;
}

:deep(.el-pagination button:hover) {
  color: var(--primary-color) !important;
}

:deep(.el-pagination .el-pager li) {
  background-color: var(--bg-secondary) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--border-color) !important;
}

:deep(.el-pagination .el-pager li:hover) {
  color: var(--primary-color) !important;
}

:deep(.el-pagination .el-pager li.is-active) {
  background: var(--primary-gradient) !important;
  color: white !important;
  border-color: transparent !important;
}

:deep(.el-pagination .el-pagination__editor) {
  background-color: var(--bg-secondary) !important;
  color: var(--text-primary) !important;
  border: 1px solid var(--border-color) !important;
}

:deep(.el-pagination .el-pagination__editor .el-input__inner) {
  background-color: var(--bg-secondary) !important;
  color: var(--text-primary) !important;
}

/* Skeleton骨架屏深色主题 */
:deep(.el-skeleton) {
  background-color: transparent !important;
}

:deep(.el-skeleton__item) {
  background-color: var(--bg-tertiary) !important;
}

/* 响应式 */
@media (max-width: 768px) {
  .posts-grid {
    grid-template-columns: 1fr;
  }

  .detail-stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .filters-section :deep(.el-row) {
    flex-direction: column;
  }

  .filters-section :deep(.el-col) {
    max-width: 100%;
    margin-bottom: var(--spacing-sm);
  }
}
</style>
