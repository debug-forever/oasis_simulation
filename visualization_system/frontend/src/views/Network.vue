<template>
  <div class="network-view">
    <!-- 控制面板 -->
    <div class="card controls-panel">
      <h3 class="panel-title">🔗 互动网络可视化</h3>
      
      <div class="control-row">
        <!-- 可视化类型选择 -->
        <div class="control-group">
          <h3>用户关系网络</h3>
        </div>

        <!-- 刷新按钮 -->
        <el-button type="primary" @click="loadData" size="small" :loading="loading">
          🔄 刷新数据
        </el-button>
      </div>




    </div>

    <!-- 加载状态 -->
    <div v-if="loading" class="loading-state">
      <el-skeleton :rows="8" animated />
    </div>

    <!-- 可视化容器 -->
    <div v-else-if="hasData" class="visualization-container">
      <!-- 图表 - 学习传播图谱的结构 -->
      <div class="chart-panel">
        <div ref="relationshipChart" class="chart"></div>
      </div>

      <!-- 统计信息卡片 - 浮动 -->
      <div class="card stats-card" v-if="stats">
        <h4>📊 网络统计</h4>
        <div class="stats-grid">
          <div class="stat-item" v-if="stats.total_nodes !== undefined">
            <span class="stat-label">节点数</span>
            <span class="stat-value">{{ stats.total_nodes }}</span>
          </div>
          <div class="stat-item" v-if="stats.total_edges !== undefined">
            <span class="stat-label">连接数</span>
            <span class="stat-value">{{ stats.total_edges }}</span>
          </div>
        </div>
      </div>

      <!-- 详情面板 - 浮动 -->
      <div class="card details-panel" v-if="selectedNode">
        <h4>👤 节点详情</h4>
        <div class="detail-content">
          <p><strong>用户名:</strong> {{ selectedNode.display_name }}</p>
          <p v-if="selectedNode.followers !== undefined"><strong>粉丝数:</strong> {{ selectedNode.followers }}</p>
          <p v-if="selectedNode.followings !== undefined"><strong>关注数:</strong> {{ selectedNode.followings }}</p>
          <p v-if="selectedNode.post_count !== undefined"><strong>发帖数:</strong> {{ selectedNode.post_count }}</p>
          <p v-if="selectedNode.total_likes !== undefined"><strong>获赞数:</strong> {{ selectedNode.total_likes }}</p>

        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else class="empty-state">
      <p>{{ emptyMessage }}</p>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import axios from 'axios'

const API_BASE = 'http://localhost:8001'

// ========== 状态管理 ==========
const loading = ref(false)
const graphData = ref(null)
const selectedNode = ref(null)

// 各类型配置参数
const relationshipLimit = ref(100)
const minFollowers = ref(0)

// 图表实例
const relationshipChart = ref(null)
const chartInstance = ref(null)

// ========== 计算属性 ==========
const hasData = computed(() => graphData.value !== null)

const stats = computed(() => {
  if (!graphData.value) return null
  return graphData.value.stats || null
})

const emptyMessage = computed(() => {
  return '暂无数据，请点击刷新数据'
})

// ========== 数据加载 ==========
const loadData = async () => {
  loading.value = true
  selectedNode.value = null
  
  try {
    const response = await axios.get(`${API_BASE}/api/network/relationship-graph`, {
      params: { limit: 2000, min_followers: 0 }
    })
    
    if (response && response.data.success) {
      console.log('Network data loaded:', response.data.data)
      // Force uniform node size
      if (response.data.data.nodes) {
        response.data.data.nodes.forEach(node => {
          node.symbolSize = 25
        })
      }
      graphData.value = response.data.data
      loading.value = false
      await nextTick()
      renderVisualization()
      // 延迟再次resize确保图表正确填充容器
      setTimeout(() => {
        if (chartInstance.value) {
          chartInstance.value.resize()
          console.log('Delayed resize completed')
        }
      }, 100)
    } else {
      console.error('Failed to load network data: API returned success=false')
      loading.value = false
    }
  } catch (error) {
    console.error('Failed to load network data:', error)
    loading.value = false
  }
}

// ========== 可视化渲染 ==========
const renderVisualization = () => {
    renderRelationshipGraph()
}

// 关系网络图
const renderRelationshipGraph = () => {
  console.log('Rendering Graph:', { 
    hasElement: !!relationshipChart.value, 
    hasData: !!graphData.value,
    nodes: graphData.value?.nodes?.length,
    links: graphData.value?.links?.length 
  })

  if (!relationshipChart.value || !graphData.value) return
  
  if (!chartInstance.value) {
    chartInstance.value = echarts.init(relationshipChart.value)
    
    // 监听缩放事件 - 学习传播图谱
    chartInstance.value.on('graphroam', (params) => {
      if (params.zoom != null) {
        console.log('Graph zoomed:', params.zoom)
      }
    })
  } else {
    chartInstance.value.clear()
  }
  
  const option = {
    backgroundColor: '#1a1a2e',
    title: {
      text: '用户关系网络',
      left: 'center',
      textStyle: { color: '#fff', fontSize: 18 }
    },
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(50, 50, 50, 0.9)',
      borderColor: '#333',
      textStyle: {
        color: '#fff'
      },
      formatter: (params) => {
        if (params.dataType === 'node') {
          const node = params.data
          const name = node.display_name || node.name || 'Unknown'
          return `
            <div style="padding:10px; color:#eee;">
              <b style="font-size:14px;">${name}</b><br/>
              粉丝: ${node.followers || 0}<br/>
              关注: ${node.followings || 0}<br/>
              发帖: ${node.post_count || 0}<br/>
              获赞: ${node.total_likes || 0}
            </div>
          `
        } else if (params.dataType === 'edge') {
            return `
            <div style="padding:10px; color:#eee;">
              ${params.name}<br/>
              关系: 关注
            </div>
          `
        }
      }
    },
    legend: {
      data: graphData.value.categories?.map(c => c.name) || [],
      orient: 'vertical',
      right: 20,
      top: 50,
      textStyle: { color: '#fff' }
    },
    // 关键：添加grid配置扩大可用区域
    grid: {
      left: 0,
      right: 0,
      top: 0,
      bottom: 0,
      containLabel: false
    },
    series: [{
      type: 'graph',
      layout: 'force',
      data: graphData.value.nodes,
      links: graphData.value.links,
      categories: graphData.value.categories,
      // 核心配置：允许无限制的缩放和拖拽
      roam: true,
      scaleLimit: {
        min: 0.01,
        max: 100
      },
      // 调整初始zoom，0.3-0.5是比较好的全局预览值
      zoom: 0.35,
      // 图表占满整个容器
      left: '5%',
      right: '5%',
      top: '10%',
      bottom: '5%',
      draggable: true,
      symbolSize: 25,
      edgeSymbol: ['none', 'arrow'],
      edgeSymbolSize: [6, 15],
      zlevel: 1,
      force: {
        // 增大repulsion让节点分散更开
        repulsion: 1500,
        gravity: 0.08,
        edgeLength: [80, 250],
        friction: 0.6,
        layoutAnimation: true
      },
      label: {
        show: true,
        position: 'top',
        formatter: (params) => params.data.display_name || params.data.name,
        color: '#fff',
        fontSize: 12
      },
      labelLayout: {
        hideOverlap: true
      },
      edgeLabel: {
        show: false
      },
      emphasis: {
        focus: 'adjacency',
        label: { show: true, color: '#fff' }
      },
      lineStyle: {
        color: '#aaa',
        opacity: 0.8,
        curveness: 0.05,
        width: 2
      }
    }]
  }
  
  chartInstance.value.setOption(option, {
    notMerge: true,
    lazyUpdate: false
  })
  
  // 强制resize确保图表占满容器
  chartInstance.value.resize()
  
  // 点击节点事件
  chartInstance.value.on('click', (params) => {
    if (params.dataType === 'node') {
        selectedNode.value = params.data
    }
  })
}

// ========== 生命周期 ==========
onMounted(() => {
  loadData()
  window.addEventListener('resize', handleResize)
})

onUnmounted(() => {
  if (chartInstance.value) chartInstance.value.dispose()
  window.removeEventListener('resize', handleResize)
})

const handleResize = () => {
  if (chartInstance.value) chartInstance.value.resize()
}
</script>

<style scoped>

.network-view {
  padding: 0;
  background: #1a1a2e;
  height: calc(100vh - 84px);
  width: 100%;
  display: flex;
  flex-direction: column;
  /* 允许子元素超出边界以支持更大的拖拽 */
  overflow: visible;
  position: relative;
  border-radius: 12px;
}

/* Top Toolbar (Controls) */
.controls-panel {
  position: relative;
  width: 100%;
  padding: 10px 20px;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  display: flex;
  justify-content: space-between;
  align-items: center;
  z-index: 20;
  border-radius: 12px 12px 0 0;
}

.panel-title {
  font-size: 18px;
  margin: 0;
  background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  font-weight: bold;
}

.control-row {
  display: flex;
  align-items: center;
  gap: 15px;
  margin: 0;
}

/* Main Visualization Area - 学习传播图谱的布局 */
.visualization-container {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-height: 0;
  position: relative;
}

.chart-panel {
  flex: 1;
  min-height: 0;
  position: relative;
  border-radius: 0 0 12px 12px;
  background: radial-gradient(circle at center, #1a1a2e 0%, #0f0c29 100%);
}

.chart {
  width: 100%;
  /* 关键：使用固定高度，与传播图谱一致 */
  height: 800px;
  min-height: 800px;
  position: relative;
  z-index: 1;
  overflow: visible !important;
}

/* Floating Overlays (Stats & Details) */
.card {
  background: rgba(20, 20, 35, 0.7);
  backdrop-filter: blur(12px);
  border-radius: 16px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}

.controls-panel.card {
  box-shadow: none;
  background: rgba(20, 20, 35, 0.9);
}

.stats-card {
  position: absolute;
  top: 20px;
  right: 20px;
  width: auto;
  min-width: 200px;
  z-index: 10;
}

.details-panel {
  position: absolute;
  bottom: 20px;
  right: 20px;
  width: 300px;
  max-height: 40vh;
  overflow-y: auto;
  z-index: 10;
}

/* Rest of styles... */
.stats-card h4 {
  margin-bottom: 15px;
  font-size: 18px;
}

.stats-grid {
  display: flex;
  justify-content: space-around;
  gap: 15px;
}

.stat-item {
  background: rgba(255, 255, 255, 0.03);
  padding: 10px 15px;
  border-radius: 8px;
  text-align: center;
  border: 1px solid rgba(255, 255, 255, 0.03);
  flex: 1;
}

.stat-label {
  display: block;
  font-size: 11px;
  color: #aaa;
  margin-bottom: 4px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: bold;
  color: #fff;
  text-shadow: 0 0 10px rgba(102, 126, 234, 0.5);
}

.details-panel h4 {
  margin-bottom: 15px;
  font-size: 16px;
  color: #ddd;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  padding-bottom: 10px;
}

.detail-content p {
  margin: 12px 0;
  font-size: 14px;
  line-height: 1.5;
  display: flex;
  justify-content: space-between;
}

.detail-content strong {
  color: #aaa;
  font-weight: normal;
}

.loading-state, .empty-state {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  z-index: 5;
  text-align: center;
  color: #aaa;
  pointer-events: none;
}

/* Dark theme element overrides */
:deep(.el-button--primary) {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border: none;
  box-shadow: 0 4px 15px rgba(118, 75, 162, 0.4);
}

:deep(.el-button--primary:hover) {
  opacity: 0.9;
  transform: scale(1.05);
}

::-webkit-scrollbar {
  width: 6px;
}

::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.1);
}

::-webkit-scrollbar-thumb {
  background: rgba(255, 255, 255, 0.1);
  border-radius: 3px;
}

::-webkit-scrollbar-thumb:hover {
  background: rgba(255, 255, 255, 0.2);
}
</style>
