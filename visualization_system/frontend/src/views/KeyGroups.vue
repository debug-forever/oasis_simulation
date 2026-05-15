<template>
  <div class="key-groups-view">
    <VaStatusBar :step="4" @ready="onReady" />

    <template v-if="ready">
      <!-- 条件组合筛选面板 -->
      <div class="card filter-panel">
        <div class="fp-row">
          <span class="fp-label">群体划分维度</span>
          <el-select v-model="groupBy" style="width: 160px" @change="run">
            <el-option v-for="g in groupDims" :key="g.id" :label="g.name" :value="g.id" />
          </el-select>

          <span class="fp-label">聚焦阶段</span>
          <el-select v-model="phase" clearable placeholder="全部阶段" style="width: 140px" @change="run">
            <el-option v-for="p in phaseOrder" :key="p" :label="p" :value="p" />
          </el-select>
          <span v-if="lockedPhase" class="locked-tip">
            （生命周期页锁定了「{{ lockedPhase }}」<el-button link size="small" @click="useLocked">套用</el-button>）
          </span>

          <div class="spacer" />
          <el-button type="primary" @click="run">应用筛选</el-button>
        </div>

        <!-- 动态条件组合 -->
        <div class="fp-conditions">
          <span class="fp-label">条件组合</span>
          <div v-for="(c, i) in conditions" :key="i" class="cond-item">
            <el-select v-model="c.dim" placeholder="选择特征" style="width: 130px" @change="c.values = []">
              <el-option v-for="d in userDims" :key="d.id" :label="d.name" :value="d.id" />
            </el-select>
            <el-select v-model="c.values" multiple collapse-tags collapse-tags-tooltip
              placeholder="选择取值" style="width: 240px" :disabled="!c.dim">
              <el-option v-for="v in dimValues(c.dim)" :key="v" :label="String(v)" :value="v" />
            </el-select>
            <el-button link type="danger" @click="conditions.splice(i, 1)">移除</el-button>
          </div>
          <el-button link type="primary" @click="conditions.push({ dim: '', values: [] })">
            ＋ 添加条件
          </el-button>
        </div>
      </div>

      <!-- 群体识别散点图 + 关键度排名 -->
      <div class="chart-row">
        <div class="card chart-card">
          <h3 class="chart-title">🎯 群体分布</h3>
          <p class="chart-sub">横轴活跃度 · 纵轴影响力 · 气泡大小为人数 · 颜色越暖关键度越高</p>
          <div ref="scatterChart" class="chart" style="height: 380px"></div>
        </div>
        <div class="card chart-card">
          <h3 class="chart-title">
            🏆 群体关键度排名
            <el-tooltip placement="top"
              content="关键度 = 规模 25% + 平均影响力 30% + 活跃度 20% + 事件量 25%">
              <span class="info-dot">?</span>
            </el-tooltip>
          </h3>
          <div ref="rankChart" class="chart" style="height: 380px"></div>
        </div>
      </div>

      <!-- 群体明细表 -->
      <div class="card">
        <h3 class="chart-title">📋 群体明细（按 {{ groupByName }} 划分，共 {{ groups.length }} 个群体）</h3>
        <el-table :data="groups" stripe style="width: 100%" max-height="460"
          @row-click="goUsers">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="group" :label="groupByName" min-width="120" />
          <el-table-column prop="key_score" label="关键度" width="100" sortable>
            <template #default="{ row }">
              <el-tag :type="row.key_score > 0.5 ? 'danger' : row.key_score > 0.25 ? 'warning' : 'info'">
                {{ row.key_score }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="members" label="人数" width="80" sortable />
          <el-table-column prop="avg_influence" label="平均影响力" width="110" sortable />
          <el-table-column prop="event_count" label="事件量" width="90" sortable />
          <el-table-column prop="total_activity" label="总活跃度" width="100" sortable />
          <el-table-column prop="opinion_leaders" label="意见领袖" width="90" sortable />
          <el-table-column prop="initiators" label="发起者" width="80" sortable />
          <el-table-column prop="avg_sentiment" label="平均情感" width="100" sortable />
          <el-table-column label="情感构成" width="140">
            <template #default="{ row }">
              <div class="senti-mini">
                <span class="seg pos" :style="{ flex: row.pos || 0 }" />
                <span class="seg neg" :style="{ flex: row.neg || 0 }" />
                <span class="seg neu" :style="{ flex: Math.max(1, row.event_count - row.pos - row.neg) }" />
              </div>
            </template>
          </el-table-column>
          <el-table-column prop="rec_ratio" label="推荐驱动占比" width="120" sortable />
        </el-table>
        <p class="table-hint">点击任一行可下钻到该群体的关键用户</p>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { vaAPI } from '@/api'
import VaStatusBar from '@/components/VaStatusBar.vue'

const router = useRouter()
const ready = ref(false)
const catalog = ref({ dimensions: [], group_dims: [], phase_order: [] })
const groupBy = ref('user.role')
const phase = ref('')
const conditions = ref([])
const groups = ref([])
const lockedPhase = ref(localStorage.getItem('va_locked_phase') || '')

const scatterChart = ref(null)
const rankChart = ref(null)
let scatterInst, rankInst

const groupDims = computed(() => catalog.value.group_dims || [])
const userDims = computed(() =>
  (catalog.value.dimensions || []).filter(d => d.group === '用户维度'))
const phaseOrder = computed(() => catalog.value.phase_order || [])
const groupByName = computed(() =>
  groupDims.value.find(g => g.id === groupBy.value)?.name || '群体')

const dimValues = (dimId) =>
  (catalog.value.dimensions || []).find(d => d.id === dimId)?.values || []

const onReady = async () => {
  try {
    catalog.value = await vaAPI.getCatalog()
    if (lockedPhase.value) phase.value = lockedPhase.value
    ready.value = true
    await nextTick()
    run()
  } catch (e) {
    console.error(e)
    ElMessage.error('加载维度目录失败')
  }
}

const useLocked = () => { phase.value = lockedPhase.value; run() }

const buildFilters = () =>
  conditions.value.filter(c => c.dim && c.values.length)
    .map(c => ({ dim: c.dim, values: c.values }))

const run = async () => {
  try {
    const res = await vaAPI.getKeyGroups(groupBy.value, buildFilters(), phase.value || null)
    groups.value = res.groups || []
    await nextTick()
    renderScatter()
    renderRank()
  } catch (e) {
    console.error(e)
    ElMessage.error('查询关键群体失败')
  }
}

const renderScatter = () => {
  if (!scatterChart.value) return
  scatterInst = scatterInst || echarts.init(scatterChart.value)
  const maxMembers = Math.max(...groups.value.map(g => g.members), 1)
  const data = groups.value.map(g => ({
    name: String(g.group),
    value: [g.total_activity, g.avg_influence, g.members, g.key_score, g.event_count]
  }))
  scatterInst.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      backgroundColor: 'rgba(26,26,46,0.95)', borderColor: '#667eea', textStyle: { color: '#fff' },
      formatter: p => `<b>${p.data.name}</b><br/>活跃度 ${p.data.value[0]}<br/>` +
        `平均影响力 ${p.data.value[1]}<br/>人数 ${p.data.value[2]}<br/>` +
        `事件量 ${p.data.value[4]}<br/>关键度 ${p.data.value[3]}`
    },
    grid: { left: 60, right: 30, top: 20, bottom: 50 },
    xAxis: { name: '总活跃度', type: 'value', nameTextStyle: { color: '#b8b8d1' },
      axisLabel: { color: '#b8b8d1' }, splitLine: { lineStyle: { color: '#2d2d44', type: 'dashed' } } },
    yAxis: { name: '平均影响力', type: 'value', nameTextStyle: { color: '#b8b8d1' },
      axisLabel: { color: '#b8b8d1' }, splitLine: { lineStyle: { color: '#2d2d44', type: 'dashed' } } },
    visualMap: {
      min: 0, max: Math.max(...groups.value.map(g => g.key_score), 0.1),
      dimension: 3, inRange: { color: ['#5b8ff9', '#f6bd16', '#ff6b6b'] },
      textStyle: { color: '#b8b8d1' }, left: 'right', bottom: 10, calculable: true,
      text: ['关键度高', '低']
    },
    series: [{
      type: 'scatter',
      symbolSize: v => 12 + (v[2] / maxMembers) * 48,
      data,
      label: { show: true, formatter: p => p.data.name, position: 'top',
        color: '#b8b8d1', fontSize: 11 },
      itemStyle: { opacity: 0.85, borderColor: '#fff', borderWidth: 0.5 }
    }]
  })
  scatterInst.off('click')
  scatterInst.on('click', p => goUsers({ group: p.data.name }))
}

const renderRank = () => {
  if (!rankChart.value) return
  rankInst = rankInst || echarts.init(rankChart.value)
  const sorted = groups.value.slice().sort((a, b) => a.key_score - b.key_score).slice(-15)
  rankInst.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(26,26,46,0.95)', borderColor: '#667eea', textStyle: { color: '#fff' } },
    grid: { left: 110, right: 30, top: 10, bottom: 30 },
    xAxis: { type: 'value', axisLabel: { color: '#b8b8d1' },
      splitLine: { lineStyle: { color: '#2d2d44', type: 'dashed' } } },
    yAxis: { type: 'category', data: sorted.map(g => String(g.group)),
      axisLabel: { color: '#b8b8d1' }, axisLine: { lineStyle: { color: '#2d2d44' } } },
    series: [{
      type: 'bar', data: sorted.map(g => g.key_score),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#5b8ff9' }, { offset: 1, color: '#ff6b6b' }]),
        borderRadius: [0, 4, 4, 0]
      },
      label: { show: true, position: 'right', color: '#b8b8d1' }
    }]
  })
}

const goUsers = (row) => {
  // 携带群体维度与取值跳转到关键用户识别
  localStorage.setItem('va_group_filter', JSON.stringify({
    dim: groupBy.value, value: row.group, phase: phase.value || ''
  }))
  router.push('/key-users')
}

onMounted(() => {
  window.addEventListener('resize', () => {
    scatterInst && scatterInst.resize()
    rankInst && rankInst.resize()
  })
})
</script>

<style scoped>
.filter-panel { padding: var(--spacing-md) var(--spacing-lg); margin-bottom: var(--spacing-md); }
.fp-row { display: flex; align-items: center; gap: var(--spacing-sm); flex-wrap: wrap;
  margin-bottom: var(--spacing-sm); }
.fp-label { font-size: 13px; font-weight: 600; color: var(--text-primary); margin-left: var(--spacing-sm); }
.fp-label:first-child { margin-left: 0; }
.locked-tip { font-size: 12px; color: #f6bd16; }
.spacer { flex: 1; }
.fp-conditions { display: flex; align-items: center; gap: var(--spacing-sm); flex-wrap: wrap;
  padding-top: var(--spacing-sm); border-top: 1px dashed var(--border-color); }
.cond-item { display: flex; align-items: center; gap: 6px;
  background: var(--bg-tertiary); padding: 4px 8px; border-radius: var(--radius-sm); }

.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--spacing-md);
  margin-bottom: var(--spacing-md); }
.chart-card { position: relative; }
.chart-title { font-size: 15px; font-weight: 600; color: var(--text-primary);
  margin-bottom: 4px; display: flex; align-items: center; gap: 6px; }
.chart-sub { font-size: 12px; color: var(--text-muted); margin: 0 0 var(--spacing-sm); }
.info-dot { display: inline-flex; align-items: center; justify-content: center;
  width: 15px; height: 15px; border-radius: 50%; font-size: 11px;
  background: var(--bg-tertiary); color: var(--text-muted); cursor: help; }
.chart { width: 100%; }
.senti-mini { display: flex; height: 10px; border-radius: 5px; overflow: hidden;
  background: var(--bg-tertiary); }
.senti-mini .seg.pos { background: #4ECDC4; }
.senti-mini .seg.neg { background: #ff6b6b; }
.senti-mini .seg.neu { background: #3a3a52; }
.table-hint { font-size: 12px; color: var(--text-muted); margin-top: var(--spacing-sm); }
@media (max-width: 1100px) { .chart-row { grid-template-columns: 1fr; } }
</style>
