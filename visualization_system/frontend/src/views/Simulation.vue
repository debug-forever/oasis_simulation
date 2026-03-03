<template>
  <div class="simulation-console">
    <!-- 页面标题 -->
    <div class="page-header gradient-bg">
      <h1 class="page-title">🚀 模拟控制台</h1>
      <p class="page-subtitle">配置并启动微博仿真实验</p>
    </div>

    <el-row :gutter="24">
      <!-- 左侧：配置表单 -->
      <el-col :xs="24" :sm="24" :md="10" :lg="10">
        <div class="card config-panel">
          <h2 class="section-title">⚙️ 配置参数</h2>
          
          <el-form :model="config" label-position="top" class="config-form">
            <el-form-item label="Agent数量">
              <el-input-number 
                v-model="config.num_agents" 
                :min="2" 
                controls-position="right"
                style="width: 100%"
              />
              <div class="form-hint">设置参与模拟的agent数量</div>
            </el-form-item>

            <el-form-item label="模拟轮次">
              <el-input-number 
                v-model="config.num_rounds" 
                :min="1" 
                controls-position="right"
                style="width: 100%"
              />
              <div class="form-hint">每轮所有agent执行一次动作</div>
            </el-form-item>

            <el-form-item label="LLM提供商">
              <el-select v-model="config.llm_provider" style="width: 100%">
                <el-option label="vLLM" value="vllm" />
                <el-option label="OpenAI" value="openai" />
                <el-option label="DeepSeek" value="deepseek" />
                <el-option label="Qwen/通义千问" value="qwen" />
              </el-select>
            </el-form-item>

            <el-form-item label="LLM端点">
              <el-input v-model="config.llm_endpoint" placeholder="http://127.0.0.1:8000/v1" />
            </el-form-item>

            <el-form-item label="模型名称">
              <el-input v-model="config.model_name" placeholder="qwen-2" />
            </el-form-item>

            <el-form-item label="启用LLM">
              <el-switch v-model="config.enable_llm" />
              <div class="form-hint">关闭时使用演示模式</div>
            </el-form-item>

            <el-divider content-position="left">📌 初始帖子播种</el-divider>

            <el-form-item label="启用初始帖子">
              <el-switch v-model="config.enable_seed_posts" />
              <div class="form-hint">播种初始内容以启动互动</div>
            </el-form-item>

            <el-form-item label="初始帖子数量" v-if="config.enable_seed_posts">
              <el-input-number 
                v-model="config.num_seed_posts" 
                :min="1" 
                controls-position="right"
                style="width: 100%"
              />
              <div class="form-hint">由前N个agent发布</div>
            </el-form-item>

            <el-form-item label="数据库文件名（可选）">
              <el-input v-model="config.output_db_name" placeholder="自动生成时间戳命名" />
              <div class="form-hint">留空则自动生成</div>
            </el-form-item>

            <el-button 
              type="primary" 
              size="large" 
              :loading="starting"
              :disabled="hasRunningTask"
              @click="startSimulation"
              class="start-button"
            >
              <span v-if="hasRunningTask">⏳ 有任务正在运行</span>
              <span v-else>🚀 启动模拟</span>
            </el-button>
          </el-form>
        </div>
      </el-col>

      <!-- 右侧：任务列表和监控 -->
      <el-col :xs="24" :sm="24" :md="14" :lg="14">
        <!-- 任务列表 -->
        <div class="card tasks-panel">
          <div class="section-header">
            <h2 class="section-title">📋 任务列表</h2>
            <el-button size="small" @click="refreshTasks" :loading="loading">
              刷新
            </el-button>
          </div>

          <div v-if="tasks.length === 0" class="empty-state">
            <p>暂无模拟任务</p>
          </div>

          <div v-else class="task-list">
            <div 
              v-for="task in tasks" 
              :key="task.id" 
              class="task-item"
              :class="{ 'active': selectedTask?.id === task.id }"
              @click="selectTask(task)"
            >
              <div class="task-header">
                <div class="task-id">
                  <span class="status-badge" :class="task.status">
                    {{ getStatusIcon(task.status) }}
                  </span>
                  <span class="task-name">任务 {{ task.id }}</span>
                </div>
                <div class="task-actions">
                  <el-button 
                    v-if="task.status === 'running'" 
                    size="small" 
                    type="danger"
                    @click.stop="stopTask(task.id)"
                  >
                    停止
                  </el-button>
                  <el-button 
                    v-if="task.status === 'completed'" 
                    size="small" 
                    type="success"
                    @click.stop="viewResult(task)"
                  >
                    查看结果
                  </el-button>
                  <el-button 
                    v-if="['completed', 'failed', 'stopped'].includes(task.status)" 
                    size="small" 
                    type="danger"
                    @click.stop="deleteTask(task.id)"
                  >
                    删除
                  </el-button>
                </div>
              </div>

              <div class="task-progress">
                <el-progress 
                  :percentage="task.progress.percentage" 
                  :status="getProgressStatus(task.status)"
                />
                <div class="progress-text">
                  {{ task.progress.current_action || getStatusText(task.status) }}
                </div>
              </div>

              <div class="task-stats">
                <span>👥 {{ task.config.num_agents }}个Agent</span>
                <span>🔄 {{ task.progress.current_round }}/{{ task.config.num_rounds }}轮</span>
                <span>⏱️ {{ formatTime(task.stats.elapsed_time) }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- 详细信息和日志 -->
        <div v-if="selectedTask" class="card details-panel">
          <h2 class="section-title">📊 任务详情</h2>
          
          <el-tabs v-model="activeTab">
            <el-tab-pane label="统计信息" name="stats">
              <div class="stats-grid">
                <div class="stat-item">
                  <div class="stat-label">用户数</div>
                  <div class="stat-value">{{ selectedTask.stats.users_created }}</div>
                </div>
                <div class="stat-item">
                  <div class="stat-label">帖子数</div>
                  <div class="stat-value">{{ selectedTask.stats.posts_created }}</div>
                </div>
                <div class="stat-item">
                  <div class="stat-label">评论数</div>
                  <div class="stat-value">{{ selectedTask.stats.comments_created }}</div>
                </div>
                <div class="stat-item">
                  <div class="stat-label">用时</div>
                  <div class="stat-value">{{ formatTime(selectedTask.stats.elapsed_time) }}</div>
                </div>
              </div>

              <div v-if="selectedTask.db_path" class="db-path">
                <strong>数据库路径:</strong>
                <code>{{ selectedTask.db_path }}</code>
              </div>
            </el-tab-pane>

            <el-tab-pane label="实时日志" name="logs">
              <div class="logs-container">
                <div v-if="logs.length === 0" class="empty-logs">
                  暂无日志
                </div>
                <div v-else class="log-lines">
                  <div v-for="(log, index) in logs" :key="index" class="log-line">
                    {{ log }}
                  </div>
                </div>
              </div>
              <el-button size="small" @click="refreshLogs" :loading="loadingLogs" style="margin-top: 10px">
                刷新日志
              </el-button>
            </el-tab-pane>
          </el-tabs>
        </div>
      </el-col>
    </el-row>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage, ElMessageBox, ElNotification } from 'element-plus'
import { useRouter } from 'vue-router'
import axios from 'axios'

const API_BASE = 'http://localhost:8001/api/simulation'
const router = useRouter()

// 从localStorage加载配置或使用默认值
const loadConfig = () => {
  const saved = localStorage.getItem('simulation_config')
  if (saved) {
    try {
      return JSON.parse(saved)
    } catch (e) {
      console.error('Failed to parse saved config:', e)
    }
  }
  return {
    num_agents: 10,
    num_rounds: 5,
    llm_provider: 'vllm',
    llm_endpoint: 'http://127.0.0.1:8000/v1',
    model_name: 'qwen-2',
    enable_llm: false,
    enable_seed_posts: true,
    num_seed_posts: 2,
    output_db_name: ''
  }
}

// 配置
const config = ref(loadConfig())

// 监听配置变化，自动保存到localStorage
watch(config, (newConfig) => {
  localStorage.setItem('simulation_config', JSON.stringify(newConfig))
}, { deep: true })

// 任务列表
const tasks = ref([])
const selectedTask = ref(null)
const logs = ref([])
const activeTab = ref('stats')

// 状态
const loading = ref(false)
const starting = ref(false)
const loadingLogs = ref(false)

// 轮询定时器
let pollTimer = null

// 追踪已完成的任务(避免重复通知)
// 从localStorage加载已完成的任务ID
const loadCompletedTaskIds = () => {
  try {
    const saved = localStorage.getItem('completed_task_ids')
    return saved ? new Set(JSON.parse(saved)) : new Set()
  } catch (e) {
    console.error('Failed to load completed task IDs:', e)
    return new Set()
  }
}

const saveCompletedTaskIds = (ids) => {
  try {
    localStorage.setItem('completed_task_ids', JSON.stringify([...ids]))
  } catch (e) {
    console.error('Failed to save completed task IDs:', e)
  }
}

const completedTaskIds = loadCompletedTaskIds()

// 计算属性
const hasRunningTask = computed(() => {
  return tasks.value.some(t => t.status === 'running')
})

// 启动模拟
const startSimulation = async () => {
  starting.value = true
  try {
    const response = await axios.post(`${API_BASE}/start`, { config: config.value })
    
    ElMessage.success(response.data.message)
    
    // 刷新任务列表
    await refreshTasks()
    
    // 自动选中新任务
    const newTask = tasks.value.find(t => t.id === response.data.task_id)
    if (newTask) {
      selectTask(newTask)
    }
    
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '启动失败')
  } finally {
    starting.value = false
  }
}

// 刷新任务列表
const refreshTasks = async () => {
  loading.value = true
  try {
    const response = await axios.get(`${API_BASE}/list`)
    const newTasks = response.data.tasks
    
    // 检查是否有新完成的任务
    for (const task of newTasks) {
      if (task.status === 'completed' && !completedTaskIds.has(task.id)) {
        completedTaskIds.add(task.id)
        saveCompletedTaskIds(completedTaskIds)  // 持久化到localStorage
        onTaskCompleted(task)
      }
    }
    
    tasks.value = newTasks
  } catch (error) {
    ElMessage.error('获取任务列表失败')
  } finally {
    loading.value = false
  }
}

// 选择任务
const selectTask = (task) => {
  selectedTask.value = task
  refreshLogs()
}

// 刷新日志
const refreshLogs = async () => {
  if (!selectedTask.value) return
  
  loadingLogs.value = true
  try {
    const response = await axios.get(`${API_BASE}/${selectedTask.value.id}/logs`)
    logs.value = response.data.logs
  } catch (error) {
    console.error('获取日志失败', error)
  } finally {
    loadingLogs.value = false
  }
}

// 停止任务
const stopTask = async (taskId) => {
  try {
    await axios.delete(`${API_BASE}/${taskId}/stop`)
    ElMessage.success('任务已停止')
    await refreshTasks()
  } catch (error) {
    ElMessage.error(error.response?.data?.detail || '停止失败')
  }
}

// 删除任务
const deleteTask = async (taskId) => {
  try {
    await ElMessageBox.confirm('确定删除此任务吗？', '确认删除', {
      type: 'warning'
    })
    
    await axios.delete(`${API_BASE}/${taskId}`)
    ElMessage.success('任务已删除')
    
    if (selectedTask.value?.id === taskId) {
      selectedTask.value = null
    }
    
    await refreshTasks()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error(error.response?.data?.detail || '删除失败')
    }
  }
}

// 任务完成处理
const onTaskCompleted = (task) => {
  ElNotification({
    title: '✅ 模拟完成！',
    message: `任务 ${task.id} 已成功完成！\n用户: ${task.stats.users_created}, 帖子: ${task.stats.posts_created}, 评论: ${task.stats.comments_created}`,
    type: 'success',
    duration: 8000,
    onClick: () => {
      viewResult(task)
    }
  })
}

// 查看结果
const viewResult = async (task) => {
  try {
    if (!task.db_path) {
      ElMessage.error('该任务没有关联的数据库文件')
      return
    }
    
    // 首先切换数据库
    ElMessage.info('正在切换数据库...')
    const switchResponse = await axios.post(`${API_BASE}/switch-database`, {
      db_path: task.db_path
    })
    
    if (switchResponse.data.success) {
      ElMessage.success(`已切换到模拟结果数据库，正在跳转...`)
      
      // 延迟跳转，让用户看到消息
      setTimeout(() => {
        router.push('/dashboard')
      }, 800)
    } else {
      ElMessage.error('切换数据库失败')
    }
  } catch (error) {
    ElMessage.error('切换数据库失败: ' + (error.response?.data?.detail || error.message))
  }
}

// 工具函数
const getStatusIcon = (status) => {
  const icons = {
    pending: '⏳',
    running: '▶️',
    completed: '✅',
    failed: '❌',
    stopped: '⏸️'
  }
  return icons[status] || '❓'
}

const getStatusText = (status) => {
  const texts = {
    pending: '等待中',
    running: '运行中',
    completed: '已完成',
    failed: '失败',
    stopped: '已停止'
  }
  return texts[status] || '未知'
}

const getProgressStatus = (status) => {
  if (status === 'completed') return 'success'
  if (status === 'failed') return 'exception'
  if (status === 'running') return ''
  return 'warning'
}

const formatTime = (seconds) => {
  if (!seconds) return '0s'
  if (seconds < 60) return `${seconds.toFixed(1)}s`
  const minutes = Math.floor(seconds / 60)
  const secs = Math.floor(seconds % 60)
  return `${minutes}m ${secs}s`
}

// 自动刷新
const startPolling = () => {
  pollTimer = setInterval(async () => {
    if (hasRunningTask.value) {
      await refreshTasks()
      
      // 如果选中的任务正在运行，刷新日志
      if (selectedTask.value && selectedTask.value.status === 'running') {
        await refreshLogs()
      }
    }
  }, 2000) // 每2秒刷新一次
}

const stopPolling = () => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// 生命周期
onMounted(() => {
  refreshTasks()
  startPolling()
})

onUnmounted(() => {
  stopPolling()
})
</script>

<style scoped>
.simulation-console {
  min-height: 100%;
}

.page-header {
  border-radius: var(--radius-lg);
  padding: var(--spacing-xl);
  margin-bottom: var(--spacing-xl);
  text-align: center;
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

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 var(--spacing-lg) 0;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-lg);
}

/* 配置面板 */
.config-panel {
  margin-bottom: var(--spacing-xl);
}

.config-form {
  margin-top: var(--spacing-md);
}

.form-hint {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 4px;
}

.start-button {
  width: 100%;
  margin-top: var(--spacing-md);
  height: 48px;
  font-size: 16px;
  font-weight: 600;
}

/* 任务列表 */
.tasks-panel {
  margin-bottom: var(--spacing-xl);
}

.task-list {
  max-height: 500px;
  overflow-y: auto;
}

.task-item {
  padding: var(--spacing-md);
  margin-bottom: var(--spacing-sm);
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  border: 2px solid transparent;
  cursor: pointer;
  transition: all 0.3s ease;
}

.task-item:hover {
  border-color: var(--primary-color);
  transform: translateY(-2px);
}

.task-item.active {
  border-color: var(--primary-color);
  background: var(--bg-secondary);
}

.task-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--spacing-sm);
}

.task-id {
  display: flex;
  align-items: center;
  gap: var(--spacing-sm);
}

.status-badge {
  font-size: 16px;
}

.task-name {
  font-weight: 600;
  color: var(--text-primary);
}

.task-actions {
  display: flex;
  gap: var(--spacing-xs);
}

.task-progress {
  margin: var(--spacing-sm) 0;
}

.progress-text {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.task-stats {
  display: flex;
  gap: var(--spacing-md);
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: var(--spacing-sm);
}

/* 详情面板 */
.details-panel {
  margin-bottom: var(--spacing-xl);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--spacing-md);
  margin-bottom: var(--spacing-md);
}

.stat-item {
  padding: var(--spacing-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  text-align: center;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--primary-color);
}

.db-path {
  padding: var(--spacing-md);
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  font-size: 12px;
}

.db-path code {
  display: block;
  margin-top: 4px;
  padding: 4px 8px;
  background: var(--bg-color);
  border-radius: 4px;
  color: var(--primary-color);
  word-break: break-all;
}

/* 日志 */
.logs-container {
  max-height: 300px;
  overflow-y: auto;
  background: var(--bg-tertiary);
  border-radius: var(--radius-sm);
  padding: var(--spacing-sm);
}

.log-lines {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  line-height: 1.6;
}

.log-line {
  color: var(--text-primary);
  white-space: pre-wrap;
  word-break: break-all;
  padding: 2px 0;
}

.empty-state,
.empty-logs {
  text-align: center;
  padding: var(--spacing-xl);
  color: var(--text-muted);
}
</style>
