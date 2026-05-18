<template>
  <div class="propagation-view">
    <!-- 控制面板 -->
    <div class="card controls-panel">
      <h3 class="panel-title">🌐 传播图谱可视化</h3>
      
      <div class="control-row">
        <!-- 模式切换 -->
        <div class="control-group">
          <label>查看模式:</label>
          <el-radio-group v-model="viewMode" @change="onViewModeChange" size="small">
            <el-radio-button label="single">单个帖子</el-radio-button>
            <el-radio-button label="all">所有帖子</el-radio-button>
          </el-radio-group>
        </div>

        <!-- 帖子选择 (单个帖子模式) -->
        <div v-if="viewMode === 'single'" class="control-group">
          <label>选择帖子:</label>
          <el-select
            v-model="selectedPostId"
            placeholder="请选择帖子"
            filterable
            @change="loadData"
            style="width: 350px"
          >
            <el-option
              v-for="post in recentPosts"
              :key="post.post_id"
              :label="`#${post.post_id}: ${truncate(post.content, 40)}`"
              :value="post.post_id"
            />
          </el-select>
        </div>

        <!-- 刷新按钮 -->
        <el-button type="primary" @click="loadRecentPosts" size="small">
          🔄 刷新
        </el-button>
      </div>

      <!-- 时间轴控制 -->
      <div v-if="hasData" class="timeline-controls">
        <div class="control-row">
          <!-- 播放控制 -->
          <div class="btn-group">
            <el-button :type="isPlaying ? 'info' : 'success'" @click="togglePlay" size="small">
              {{ isPlaying ? '⏸ 暂停' : '▶ 播放' }}
            </el-button>
            <el-button @click="resetTimeline" size="small">↺ 重置</el-button>
          </div>

          <!-- 时间模式 -->
          <div class="control-group">
            <label>时间模式:</label>
            <el-select v-model="timeMode" @change="onTimeModeChange" size="small" style="width: 120px">
              <el-option label="累积模式" value="cumulative" />
              <el-option label="时间切片" value="slice" />
            </el-select>
          </div>

          <!-- 时间窗口 (切片模式) -->
          <div v-if="timeMode === 'slice'" class="control-group">
            <label>窗口大小:</label>
            <el-select v-model="sliceWindow" @change="updateVisualization" size="small" style="width: 100px">
              <el-option label="5分钟" :value="300" />
              <el-option label="15分钟" :value="900" />
              <el-option label="30分钟" :value="1800" />
              <el-option label="1小时" :value="3600" />
              <el-option label="2小时" :value="7200" />
              <el-option label="1天" :value="86400" />
            </el-select>
          </div>

          <!-- 播放速度 -->
          <div class="control-group">
            <label>速度:</label>
            <el-select v-model="animationSpeed" size="small" style="width: 80px">
              <el-option label="0.5x" :value="0.5" />
              <el-option label="1x" :value="1" />
              <el-option label="2x" :value="2" />
              <el-option label="5x" :value="5" />
              <el-option label="10x" :value="10" />
            </el-select>
          </div>

          <!-- 视角控制 -->
          <div class="btn-group">
            <el-button :type="isViewLocked ? 'warning' : 'default'" @click="toggleLockView" size="small">
              {{ isViewLocked ? '🔒 解锁视角' : '🔓 锁定视角' }}
            </el-button>
            <el-button @click="centerGraph" size="small">⊙ 居中</el-button>
          </div>
        </div>

        <!-- 时间轴滑块 -->
        <div class="timeline-slider">
          <div class="time-display">{{ currentTimeStr }}</div>
          <el-slider
            v-model="currentTime"
            :min="timeRange.min"
            :max="timeMode === 'slice' ? timeRange.max - sliceWindow : timeRange.max"
            :step="1"
            @input="onSliderChange"
            style="flex: 1"
          />
        </div>
      </div>
    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="8" animated />
    </div>

    <!-- 可视化容器 -->
    <div v-else-if="hasData" class="visualization-container">
      <!-- 图表 -->
      <div class="card chart-panel">
        <div ref="graphChart" class="graph-chart"></div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <p>请选择查看模式和帖子以查看传播图谱</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { postAPI } from '@/api'

const loading = ref(false)
const viewMode = ref('single')
const selectedPostId = ref(null)
const recentPosts = ref([])
const graphData = ref({ nodes: [], links: [], categories: [], timeRange: {}, colorMap: {} })

const chart = ref(null)
const graphChart = ref(null)
const isPlaying = ref(false)
const animationSpeed = ref(1)
const currentTime = ref(0)
const timeMode = ref('cumulative')
const sliceWindow = ref(3600)
const isViewLocked = ref(false)
const isFirstRender = ref(true)
const animationFrameId = ref(null)
const nodePositions = ref({})

const stats = ref({
  root: 0,
  repost: 0,
  comment: 0,
  total: 0
})

const hasData = computed(() => graphData.value.nodes.length > 0)

const timeRange = computed(() => graphData.value.timeRange || { min: 0, max: 0, minStr: '', maxStr: '' })

const currentTimeStr = computed(() => {
  if (!currentTime.value) return 'Loading...'
  
  const date = new Date(currentTime.value * 1000)
  const timeStr = date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
  
  if (timeMode.value === 'slice') {
    const endDate = new Date((currentTime.value + sliceWindow.value) * 1000)
    const endTimeStr = endDate.toLocaleString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit'
    })
    return `${timeStr} - ${endTimeStr}`
  }
  
  return timeStr
})

const truncate = (text, maxLength) => {
  if (!text) return ''
  return text.length > maxLength ? text.substring(0, maxLength) + '...' : text
}

const loadRecentPosts = async () => {
  try {
    const response = await postAPI.getPosts({ page: 1, page_size: 50, post_type: 'original' })
    recentPosts.value = response.posts || []
    
    if (recentPosts.value.length > 0 && !selectedPostId.value) {
      selectedPostId.value = recentPosts.value[0].post_id
      await loadData()
    }
  } catch (error) {
    console.error('Failed to load posts:', error)
  }
}

const loadData = async () => {
  loading.value = true
  
  if (chart.value) {
    chart.value.dispose()
    chart.value = null
  }
  isFirstRender.value = true
  
  try {
    let data
    
    const timeoutPromise = new Promise((_, reject) => {
      setTimeout(() => reject(new Error('API request timeout after 30s')), 30000)
    })

    if (viewMode.value === 'single') {
      if (!selectedPostId.value) {
        loading.value = false
        return
      }
      data = await Promise.race([
        postAPI.getPropagation(selectedPostId.value),
        timeoutPromise
      ])
    } else {
      data = await Promise.race([
        postAPI.getPropagationAll(),
        timeoutPromise
      ])
    }

    graphData.value = data
    loading.value = false

    await nextTick()
    await nextTick()

    precomputeNodePositions()
    
    if (timeRange.value.min && timeRange.value.max) {
      currentTime.value = timeRange.value.max
      
      if (!isViewLocked.value && graphData.value.nodes.length > 100) {
        isViewLocked.value = true
      }

      updateVisualization()
    } else {
      if (graphData.value.nodes.length > 0) {
        renderGraph(graphData.value.nodes, graphData.value.links)
        updateStats(graphData.value.nodes)
      }
    }
  } catch (error) {
    console.error('Failed to load propagation data:', error)
    loading.value = false
  }
}

const precomputeNodePositions = () => {
  const nodes = graphData.value.nodes
  const links = graphData.value.links
  
  if (!nodes.length) return

  const childrenMap = {}
  links.forEach(link => {
    if (!childrenMap[link.source]) {
      childrenMap[link.source] = []
    }
    childrenMap[link.source].push(link.target)
  })

  const allTargets = new Set(links.map(l => l.target))
  const rootNodes = nodes.filter(n => !allTargets.has(n.node_id))

  const centerX = 0
  const centerY = 0
  
  rootNodes.forEach((node, i) => {
    if (rootNodes.length === 1) {
      nodePositions.value[node.node_id] = { x: centerX, y: centerY }
    } else {
      const angle = (2 * Math.PI * i) / rootNodes.length
      const radius = Math.max(1500, rootNodes.length * 20)
      nodePositions.value[node.node_id] = {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle)
      }
    }
  })
  
  const layoutChildren = (parentId, parentX, parentY, level, siblings = 1, siblingIndex = 0) => {
    const children = childrenMap[parentId] || []
    if (children.length === 0) return
    
    const baseRadius = 700 + level * 700
    const angleSpan = Math.PI * 2
    const startAngle = -angleSpan / 2 + (siblingIndex / Math.max(siblings - 1, 1)) * angleSpan * 0.3
    
    children.forEach((childId, i) => {
      const angle = startAngle + (i / Math.max(children.length - 1, 1)) * angleSpan
      const jitter = (Math.random() - 0.5) * 200
      
      const x = parentX + baseRadius * Math.cos(angle) + jitter
      const y = parentY + baseRadius * Math.sin(angle) + jitter
      
      nodePositions.value[childId] = { x, y }
      layoutChildren(childId, x, y, level + 1, children.length, i)
    })
  }
  
  rootNodes.forEach((rootNode, i) => {
    const rootPos = nodePositions.value[rootNode.node_id]
    layoutChildren(rootNode.node_id, rootPos.x, rootPos.y, 1, rootNodes.length, i)
  })
  
  nodes.forEach((node, i) => {
    if (!nodePositions.value[node.node_id]) {
      const angle = (2 * Math.PI * i) / nodes.length
      const radius = 800
      nodePositions.value[node.node_id] = {
        x: centerX + radius * Math.cos(angle),
        y: centerY + radius * Math.sin(angle)
      }
    }
  })
}

const updateVisualization = () => {
  if (!hasData.value) {
    return
  }

  let visibleNodes, visibleLinks
  
  if (timeMode.value === 'cumulative') {
    visibleNodes = graphData.value.nodes.filter(node => {
      if (!node.timestamp || node.timestamp === 0) {
        return true
      }
      return node.timestamp <= currentTime.value
    })
    visibleLinks = graphData.value.links.filter(link => {
      const sourceVisible = visibleNodes.find(n => n.node_id === link.source)
      const targetVisible = visibleNodes.find(n => n.node_id === link.target)
      return sourceVisible && targetVisible
    })
  } else {
    const windowStart = currentTime.value
    const windowEnd = currentTime.value + sliceWindow.value
    
    visibleNodes = graphData.value.nodes.filter(node => {
      if (!node.timestamp || node.timestamp === 0) {
        return true
      }
      return node.timestamp >= windowStart && node.timestamp <= windowEnd
    })
    
    const visibleNodeIds = new Set(visibleNodes.map(n => n.node_id))
    visibleLinks = graphData.value.links.filter(link =>
      visibleNodeIds.has(link.source) && visibleNodeIds.has(link.target)
    )
  }

  if (visibleNodes.length === 0) {
    visibleNodes = graphData.value.nodes
    visibleLinks = graphData.value.links
  }
  
  updateStats(visibleNodes)
  renderGraph(visibleNodes, visibleLinks)
}

const renderGraph = (nodes, links) => {
  if (!graphChart.value) {
    console.error('Graph chart ref not available, retrying after nextTick...')
    nextTick(() => {
      if (graphChart.value) {
        renderGraph(nodes, links)
      }
    })
    return
  }
  
  if (!chart.value) {
    chart.value = echarts.init(graphChart.value)
  }

  buildAndRenderGraph(nodes, links)
}

const buildAndRenderGraph = (nodes, links) => {
  const nodeDegreeMap = {}
  links.forEach(link => {
    nodeDegreeMap[link.source] = (nodeDegreeMap[link.source] || 0) + 1
    nodeDegreeMap[link.target] = (nodeDegreeMap[link.target] || 0) + 1
  })

  const positionedNodes = nodes.map(node => {
    const pos = nodePositions.value[node.node_id]
    
    const structDegree = nodeDegreeMap[node.node_id] || 0
    const interactionScore = node.num_likes + (node.num_shares * 2)
    let symbolSize = 8 + Math.log(interactionScore + 1) * 2 + (structDegree * 1.5)
    
    symbolSize = Math.min(Math.max(symbolSize, 8), 25)
    
    const colorMap = graphData.value.colorMap || {}
    let color = colorMap[node.node_type] || '#FF0000'
    
    if (node.node_type === 'root') color = '#FFD700'
    else if (node.node_type === 'repost') color = '#FF6B6B'
    else if (node.node_type === 'comment') color = '#4ECDC4'
    
    const nodeConfig = {
      name: node.node_id,
      symbolSize: symbolSize,
      category: node.category,
      value: interactionScore,
      id: node.node_id,
      x: pos && isViewLocked.value ? pos.x : undefined,
      y: pos && isViewLocked.value ? pos.y : undefined,
      fixed: isViewLocked.value,
      rawNode: node,
      structDegree: structDegree,
      itemStyle: {
        color: color,
        borderColor: '#fff',
        borderWidth: 1
      },
      label: {
        show: symbolSize > 30,
        formatter: node.user_name,
        color: '#fff',
        fontSize: 10,
        position: 'right'
      }
    }
    
    return nodeConfig
  })
  
  const option = {
    backgroundColor: '#1a1a2e',
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(30, 30, 30, 0.95)',
      borderColor: '#555',
      borderWidth: 1,
      padding: 0,
      formatter: (params) => {
        if (params.dataType !== 'node') return
        const data = params.data
        const node = data.rawNode
        if (!node) return
        
        const color = data.itemStyle.color
        const structDegree = data.structDegree
        
        return `
          <div style="padding:10px; font-family: sans-serif; font-size:12px; line-height:1.5; color:#eee;">
            <div style="margin-bottom:5px;">
              <b style="font-size:14px; color:${color}">${node.user_name}</b>
              <span style="background:#555; padding:2px 4px; border-radius:3px; font-size:10px; margin-left:8px;">${(node.node_type || '').toUpperCase()}</span>
            </div>
            <div style="color:#bbb; font-size:11px; margin-bottom:8px;">${node.created_at}</div>
            <div style="border-left: 3px solid ${color}; padding-left:8px; margin-bottom:8px;">
              ${truncate(node.content, 100)}
            </div>
            <div style="background:#333; padding:5px; border-radius:4px; font-weight:bold; color:#ffcc00;">
              👍 ${node.num_likes} | 🔁 ${node.num_shares} | 👎 ${node.num_dislikes} | 💬 ${structDegree}
            </div>
          </div>
        `
      }
    },
    legend: {
      data: graphData.value.categories.map(c => c.name),
      orient: 'horizontal',
      right: '3%',
      top: '3%',
      textStyle: {
        color: '#fff',
        fontSize: 12,
        fontWeight: 'normal'
      },
      itemGap: 15,
      itemWidth: 20,
      itemHeight: 20
    },
    animationDuration: isFirstRender.value ? 1000 : 300,
    animationDurationUpdate: 300,
    animationEasingUpdate: 'cubicOut',
    series: [{
      type: 'graph',
      layout: isViewLocked.value ? 'none' : 'force',
      data: positionedNodes,
      links: links,
      categories: graphData.value.categories,
      roam: true,
      draggable: true,
      scaleLimit: {
        min: 0.05,
        max: 30
      },
      center: ['50%', '50%'],
      zoom: 0.8,
      left: 0,
      right: 0,
      top: 0,
      bottom: 0,
      coordinateSystem: null,
      symbol: 'circle',
      symbolSize: 30,
      showSymbol: true,
      zlevel: 1,
      force: {
        repulsion: 2500,
        gravity: 0.3,
        edgeLength: [15, 50],
        friction: 0.9,
        layoutAnimation: true
      },
      lineStyle: {
        color: '#888',
        curveness: 0.15,
        opacity: 0.4,
        width: 1.5
      },
      emphasis: {
        focus: 'adjacency',
        scale: 1.2,
        lineStyle: {
          width: 3,
          opacity: 0.8
        },
        itemStyle: {
          borderWidth: 3
        }
      }
    }]
  }
  
  if (!chart.value) {
    return
  }
  
  chart.value.setOption(option, {
    notMerge: false,
    lazyUpdate: false
  })
  
  chart.value.resize()
  
  if (isFirstRender.value) {
    setTimeout(() => {
      if (chart.value) {
        chart.value.dispatchAction({ type: 'restore' })
      }
    }, 500)
  }
  
  isFirstRender.value = false
}

const updateStats = (visibleNodes) => {
  const counts = {
    root: 0,
    repost: 0,
    comment: 0
  }
  
  visibleNodes.forEach(node => {
    const nodeId = node.node_id
    if (nodeId.startsWith('P_')) {
      if (node.category === 0) counts.root++
      else if (node.category === 1) counts.repost++
    } else if (nodeId.startsWith('C_')) {
      counts.comment++
    }
  })
  
  stats.value = {
    root: counts.root,
    repost: counts.repost,
    comment: counts.comment,
    total: visibleNodes.length
  }
}

const onSliderChange = () => {
  updateVisualization()
}

const togglePlay = () => {
  isPlaying.value = !isPlaying.value
  
  if (isPlaying.value) {
    if (!isViewLocked.value) {
      toggleLockView()
    }
    startAnimation()
  } else {
    stopAnimation()
  }
}

const startAnimation = () => {
  const step = () => {
    if (!isPlaying.value) return
    
    const timeStep = animationSpeed.value * 30
    currentTime.value += timeStep
    
    const maxTime = timeMode.value === 'slice'
      ? timeRange.value.max - sliceWindow.value
      : timeRange.value.max
    
    if (currentTime.value >= maxTime) {
      currentTime.value = maxTime
      isPlaying.value = false
      return
    }
    
    updateVisualization()
    animationFrameId.value = setTimeout(step, 100)
  }
  
  step()
}

const stopAnimation = () => {
  if (animationFrameId.value) {
    clearTimeout(animationFrameId.value)
    animationFrameId.value = null
  }
}

const resetTimeline = () => {
  stopAnimation()
  isPlaying.value = false
  isFirstRender.value = true
  currentTime.value = timeRange.value.min
  updateVisualization()
}

const toggleLockView = () => {
  isViewLocked.value = !isViewLocked.value
  updateVisualization()
}

const centerGraph = () => {
  if (chart.value) {
    chart.value.dispatchAction({
      type: 'restore'
    })
  }
}

const onViewModeChange = () => {
  graphData.value = { nodes: [], links: [], categories: [], timeRange: {}, colorMap: {} }
  if (viewMode.value === 'all') {
    loadData()
  } else {
    loadRecentPosts()
  }
}

const onTimeModeChange = () => {
  updateVisualization()
}

const handleResize = () => {
  if (chart.value) {
    chart.value.resize()
  }
}

onMounted(() => {
  loadRecentPosts()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  stopAnimation()
  if (chart.value) {
    chart.value.dispose()
  }
  window.removeEventListener('resize', handleResize)
})
</script>

<style scoped>
.propagation-view {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-lg);
  height: calc(100vh - 140px);
}

.controls-panel {
  flex-shrink: 0;
}

.panel-title {
  font-size: 16px;
  font-weight: 600;
  margin-bottom: var(--spacing-md);
  color: var(--text-primary);
}

.control-row {
  display: flex;
  gap: var(--spacing-md);
  align-items: center;
  flex-wrap: wrap;
  margin-bottom: var(--spacing-sm);
}

.control-row:last-child {
  margin-bottom: 0;
}

.control-group {
  display: flex;
  gap: var(--spacing-xs);
  align-items: center;
}

.control-group label {
  color: var(--text-secondary);
  font-size: 13px;
  white-space: nowrap;
}

.btn-group {
  display: flex;
  gap: var(--spacing-xs);
}

.timeline-controls {
  margin-top: var(--spacing-md);
  padding-top: var(--spacing-md);
  border-top: 1px solid var(--border-color);
}

.timeline-slider {
  display: flex;
  gap: var(--spacing-md);
  align-items: center;
  margin-top: var(--spacing-md);
}

.time-display {
  min-width: 200px;
  padding: 8px 12px;
  background: rgba(255, 215, 0, 0.1);
  border: 1px solid rgba(255, 215, 0, 0.3);
  border-radius: 6px;
  text-align: center;
  font-family: 'Courier New', monospace;
  font-size: 12px;
  color: #FFD700;
  font-weight: bold;
}

.stats-panel {
  display: flex;
  gap: var(--spacing-xl);
  margin-bottom: var(--spacing-md);
}

.stat-item {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-xs);
}

.stat-label {
  font-size: 11px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 1px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
}

.stat-item.roots .stat-value { color: #FFD700; }
.stat-item.reposts .stat-value { color: #FF6B6B; }
.stat-item.comments .stat-value { color: #4ECDC4; }
.stat-item.total .stat-value { color: #fff; }

.visualization-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
}

.chart-panel {
  flex: 1;
  min-height: 0;
}

.graph-chart {
  width: 100%;
  height: 800px;
  min-height: 800px;
  position: relative;
  z-index: 1;
  overflow: visible !important;
}

.empty-state,
.loading-state {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  font-size: 16px;
}
</style>
