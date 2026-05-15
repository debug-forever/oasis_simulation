<template>
  <div class="va-status-bar">
    <!-- 分析流程指引 -->
    <div class="workflow card">
      <div class="workflow-head">
        <span class="workflow-title">🧭 分析路径</span>
        <span class="workflow-hint">从舆情整体走势，逐层下探到关键群体与关键个体</span>
      </div>
      <div class="workflow-steps">
        <div
          v-for="s in steps"
          :key="s.idx"
          class="wf-step"
          :class="{ active: s.idx === step, done: s.idx < step }"
        >
          <div class="wf-dot">{{ s.idx < step ? '✓' : s.idx }}</div>
          <div class="wf-body">
            <div class="wf-name">{{ s.name }}</div>
            <div class="wf-desc">{{ s.desc }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 构建状态 -->
    <div class="card build-card">
      <template v-if="loading">
        <el-skeleton :rows="1" animated />
      </template>
      <template v-else-if="status && status.built">
        <div class="built-info">
          <span class="ok-badge">✅ 数据已就绪</span>
          <span class="meta">{{ status.db_name }}</span>
          <span class="meta">用户 {{ status.counts?.users }} · 内容 {{ status.counts?.posts }}
            · 事件 {{ status.counts?.events }} · 社群 {{ status.counts?.communities }}</span>
          <span class="meta">处理于 {{ status.built_at }}</span>
          <el-button size="small" plain :loading="building" @click="doBuild">重新处理</el-button>
        </div>
      </template>
      <template v-else>
        <div class="need-build">
          <div class="nb-text">
            <span class="nb-title">⚙️ 当前仿真库尚未预处理</span>
            <span class="nb-desc">
              首次分析前需对仿真库做一次预处理（识别社群、情感、话题、传播链路、
              活跃阶段等），完成后即可开始分析。每个仿真库只需处理一次。
            </span>
          </div>
          <el-button type="primary" size="large" :loading="building" @click="doBuild">
            开始预处理
          </el-button>
        </div>
      </template>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { vaAPI } from '@/api'

const props = defineProps({
  step: { type: Number, default: 1 }
})
const emit = defineEmits(['ready'])

const steps = [
  { idx: 1, name: '准备数据', desc: '预处理当前仿真库' },
  { idx: 2, name: '看整体走势', desc: '舆情各阶段演化' },
  { idx: 3, name: '选定阶段', desc: '聚焦某一阶段' },
  { idx: 4, name: '找关键群体', desc: '按特征切分人群' },
  { idx: 5, name: '找关键用户', desc: '定位核心人物' },
  { idx: 6, name: '查个体', desc: '追溯单人轨迹' }
]

const loading = ref(true)
const building = ref(false)
const status = ref(null)

const fetchStatus = async () => {
  loading.value = true
  try {
    status.value = await vaAPI.getStatus()
    if (status.value.built) emit('ready', status.value)
  } catch (e) {
    console.error('va status failed', e)
    ElMessage.error('获取分析状态失败，请确认后端已启动')
  } finally {
    loading.value = false
  }
}

const doBuild = async () => {
  building.value = true
  try {
    ElMessage.info('正在预处理数据，大规模仿真库可能需要数十秒…')
    await vaAPI.build()
    ElMessage.success('数据预处理完成')
    await fetchStatus()
  } catch (e) {
    console.error('va build failed', e)
    ElMessage.error('预处理失败：' + (e.response?.data?.detail || e.message))
  } finally {
    building.value = false
  }
}

defineExpose({ refresh: fetchStatus })
onMounted(fetchStatus)
</script>

<style scoped>
.va-status-bar { margin-bottom: var(--spacing-lg); }

.workflow { padding: var(--spacing-md) var(--spacing-lg); margin-bottom: var(--spacing-md); }
.workflow-head { display: flex; align-items: baseline; gap: var(--spacing-md); margin-bottom: var(--spacing-md); }
.workflow-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.workflow-hint { font-size: 12px; color: var(--text-muted); }

.workflow-steps { display: flex; gap: var(--spacing-sm); flex-wrap: wrap; }
.wf-step {
  display: flex; align-items: center; gap: var(--spacing-sm);
  padding: var(--spacing-sm) var(--spacing-md);
  background: var(--bg-tertiary); border-radius: var(--radius-sm);
  border: 1px solid var(--border-color); flex: 1; min-width: 150px;
}
.wf-step.active { border-color: var(--primary-color); box-shadow: var(--shadow-glow); }
.wf-step.done { opacity: 0.7; }
.wf-dot {
  width: 24px; height: 24px; border-radius: 50%;
  display: flex; align-items: center; justify-content: center;
  font-size: 12px; font-weight: 700; flex-shrink: 0;
  background: var(--bg-secondary); color: var(--text-secondary);
}
.wf-step.active .wf-dot { background: var(--primary-gradient); color: #fff; }
.wf-step.done .wf-dot { background: #4ECDC4; color: #fff; }
.wf-name { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.wf-desc { font-size: 11px; color: var(--text-muted); }

.build-card { padding: var(--spacing-md) var(--spacing-lg); }
.built-info { display: flex; align-items: center; gap: var(--spacing-lg); flex-wrap: wrap; }
.ok-badge { font-weight: 600; color: #4ECDC4; }
.meta { font-size: 12px; color: var(--text-secondary); }

.need-build { display: flex; align-items: center; justify-content: space-between; gap: var(--spacing-lg); }
.nb-text { display: flex; flex-direction: column; gap: var(--spacing-xs); }
.nb-title { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.nb-desc { font-size: 12px; color: var(--text-secondary); max-width: 720px; line-height: 1.6; }
</style>
