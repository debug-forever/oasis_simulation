<template>
  <div class="lifecycle-view">
    <VaStatusBar :step="2" @ready="onReady" />

    <template v-if="ready">
      <!-- 控制栏 -->
      <div class="card control-bar">
        <span class="ctrl-label">拆解维度</span>
        <el-select v-model="breakdown" size="default" style="width: 180px" @change="onChange">
          <el-option v-for="d in breakdownOptions" :key="d.id" :label="d.name" :value="d.id" />
        </el-select>

        <template v-if="mode === 'compare'">
          <span class="ctrl-label">对照基线</span>
          <el-select v-model="phaseA" size="default" style="width: 110px" @change="onChange">
            <el-option v-for="p in phaseList" :key="p" :label="p" :value="p" />
          </el-select>
          <span class="ctrl-arrow">→</span>
          <span class="ctrl-label">对比阶段</span>
          <el-select v-model="phaseB" size="default" style="width: 110px" @change="onChange">
            <el-option v-for="p in phaseList" :key="p" :label="p" :value="p" />
          </el-select>
        </template>

        <div class="spacer" />

        <el-radio-group v-model="mode" size="small" @change="onModeChange">
          <el-radio-button label="single">整体走势</el-radio-button>
          <el-radio-button label="compare">阶段对比</el-radio-button>
        </el-radio-group>

        <span v-if="lockedPhase && mode==='single'" class="locked-tag">
          当前聚焦：<b>{{ lockedPhase }}</b>
          <el-button link size="small" @click="clearLock">取消</el-button>
        </span>
      </div>

      <!-- 四阶段卡片：点击可锁定为「关键阶段」供后续分析 -->
      <div v-if="mode==='single'" class="phase-cards">
        <div
          v-for="ph in phases"
          :key="ph.phase"
          class="phase-card"
          :class="{ locked: ph.phase === lockedPhase }"
          :style="{ borderTopColor: phaseColor[ph.order] }"
          @click="lockPhase(ph.phase)"
        >
          <div class="pc-head">
            <span class="pc-name">{{ ph.phase }}</span>
            <span class="pc-order">阶段 {{ ph.order + 1 }}</span>
          </div>
          <div class="pc-time">{{ fmt(ph.start) }} ~ {{ fmt(ph.end) }}</div>
          <div class="pc-stats">
            <div class="pc-stat"><b>{{ ph.event_count }}</b><span>行为事件</span></div>
            <div class="pc-stat"><b>{{ ph.active_users }}</b><span>活跃用户</span></div>
            <div class="pc-stat"><b>{{ ph.posts }}</b><span>涉及内容</span></div>
          </div>
          <div class="pc-senti">
            <div class="senti-bar">
              <span class="seg pos" :style="{ width: pct(ph.pos, ph) }" />
              <span class="seg neu" :style="{ width: pct(ph.neu, ph) }" />
              <span class="seg neg" :style="{ width: pct(ph.neg, ph) }" />
            </div>
            <span class="senti-avg">均值 {{ ph.avg_sentiment }}</span>
          </div>
          <div class="pc-lock-hint">{{ ph.phase === lockedPhase ? '★ 当前聚焦' : '点击聚焦此阶段' }}</div>
        </div>
      </div>

      <!-- 单阶段模式：主轴 + 堆叠流 + 阶段构成 -->
      <template v-if="mode==='single'">
        <div class="card chart-card">
          <h3 class="chart-title">📈 舆情生命周期主轴 —— 事件量与情感走势</h3>
          <div ref="mainChart" class="chart" style="height: 380px"></div>
        </div>

        <div class="chart-row">
          <div class="card chart-card">
            <h3 class="chart-title">🌊 {{ breakdownName }} 构成随时间演化</h3>
            <div ref="streamChart" class="chart" style="height: 340px"></div>
          </div>
          <div class="card chart-card">
            <h3 class="chart-title">📊 各阶段 {{ breakdownName }} 构成对比</h3>
            <div class="mini-toggle">
              <el-radio-group v-model="snapMode" size="small" @change="renderSnapshot">
                <el-radio-button label="absolute">绝对量</el-radio-button>
                <el-radio-button label="ratio">占比</el-radio-button>
              </el-radio-group>
            </div>
            <div ref="snapChart" class="chart" style="height: 300px"></div>
          </div>
        </div>
      </template>

      <!-- 阶段对比模式：A vs B 总览 + lift 条 + 占比并排 -->
      <template v-else>
        <div class="cmp-summary">
          <div class="cmp-side" :class="{ baseline: true }">
            <div class="cmp-head"><b>{{ cmp.phase_a?.name }}</b><span>基线</span></div>
            <div class="cmp-stats">
              <div><b>{{ cmp.phase_a?.event_count }}</b><span>事件</span></div>
              <div><b>{{ cmp.phase_a?.active_users }}</b><span>活跃用户</span></div>
              <div><b>{{ cmp.phase_a?.avg_sentiment }}</b><span>平均情感</span></div>
              <div><b>{{ pctText(cmp.phase_a?.neg_ratio) }}</b><span>负面占比</span></div>
              <div><b>{{ pctText(cmp.phase_a?.rec_ratio) }}</b><span>推荐驱动</span></div>
            </div>
          </div>
          <div class="cmp-side">
            <div class="cmp-head"><b>{{ cmp.phase_b?.name }}</b><span>对比</span></div>
            <div class="cmp-stats">
              <div><b>{{ cmp.phase_b?.event_count }}</b>
                <span>事件 <em :class="deltaCls(cmp.phase_b?.event_count - cmp.phase_a?.event_count)">
                  {{ deltaText(cmp.phase_b?.event_count - cmp.phase_a?.event_count) }}</em></span>
              </div>
              <div><b>{{ cmp.phase_b?.active_users }}</b>
                <span>活跃用户 <em :class="deltaCls(cmp.phase_b?.active_users - cmp.phase_a?.active_users)">
                  {{ deltaText(cmp.phase_b?.active_users - cmp.phase_a?.active_users) }}</em></span>
              </div>
              <div><b>{{ cmp.phase_b?.avg_sentiment }}</b>
                <span>平均情感 <em :class="deltaCls(cmp.phase_b?.avg_sentiment - cmp.phase_a?.avg_sentiment)">
                  {{ deltaText(cmp.phase_b?.avg_sentiment - cmp.phase_a?.avg_sentiment, 3) }}</em></span>
              </div>
              <div><b>{{ pctText(cmp.phase_b?.neg_ratio) }}</b>
                <span>负面占比 <em :class="deltaCls(cmp.phase_b?.neg_ratio - cmp.phase_a?.neg_ratio)">
                  {{ deltaPct(cmp.phase_b?.neg_ratio - cmp.phase_a?.neg_ratio) }}</em></span>
              </div>
              <div><b>{{ pctText(cmp.phase_b?.rec_ratio) }}</b>
                <span>推荐驱动 <em :class="deltaCls(cmp.phase_b?.rec_ratio - cmp.phase_a?.rec_ratio)">
                  {{ deltaPct(cmp.phase_b?.rec_ratio - cmp.phase_a?.rec_ratio) }}</em></span>
              </div>
            </div>
          </div>
        </div>

        <div class="chart-row">
          <div class="card chart-card">
            <h3 class="chart-title">
              ⚖️ {{ breakdownName }} 占比 lift（B / A）
              <el-tooltip placement="top"
                content="lift>1 表示该桶在对比阶段占比变大；<1 表示变小；=1 几乎无变化。按 |lift-1| 排序，最显著的变化排在前面。">
                <span class="info-dot">?</span>
              </el-tooltip>
            </h3>
            <div ref="liftChart" class="chart" style="height: 380px"></div>
          </div>
          <div class="card chart-card">
            <h3 class="chart-title">📊 {{ breakdownName }} 占比并排</h3>
            <div ref="cmpRatioChart" class="chart" style="height: 380px"></div>
          </div>
        </div>
      </template>

      <div class="next-hint card">
        <span v-if="mode==='single'">点击上方阶段卡片可聚焦该阶段</span>
        <span v-else>正在对比「{{ phaseA }}」与「{{ phaseB }}」，下方分析自动套用对比阶段</span>
        <el-button type="primary" plain size="small" @click="$router.push('/key-groups')">
          进入关键群体识别 →
        </el-button>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, nextTick } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { vaAPI } from '@/api'
import VaStatusBar from '@/components/VaStatusBar.vue'

const ready = ref(false)
const breakdown = ref('event.action_type')
const breakdownOptions = [
  { id: 'event.action_type', name: '行为类型' },
  { id: 'post.sentiment_class', name: '情感极性' },
  { id: 'user.role', name: '关键角色' },
  { id: 'user.influence_tier', name: '影响力分层' },
  { id: 'user.behavior_label', name: '行为标签' },
  { id: 'post.topic', name: '话题' },
  { id: 'event.is_rec_driven', name: '推荐驱动' }
]
const breakdownName = computed(() =>
  breakdownOptions.find(o => o.id === breakdown.value)?.name || '维度')

const phaseColor = ['#5b8ff9', '#f6bd16', '#ff6b6b', '#9270ca']
const phases = ref([])
const timeline = ref([])
const timelineBreakdown = ref([])
const snapshots = ref([])
const snapMode = ref('absolute')
const lockedPhase = ref(localStorage.getItem('va_locked_phase') || '')

const mode = ref('single')        // single | compare
const phaseA = ref('潜伏期')
const phaseB = ref('爆发期')
const cmp = ref({})
const phaseList = computed(() => phases.value.map(p => p.phase))

const mainChart = ref(null)
const streamChart = ref(null)
const snapChart = ref(null)
const liftChart = ref(null)
const cmpRatioChart = ref(null)
let mainInst, streamInst, snapInst, liftInst, cmpRatioInst

const fmt = (s) => (s || '').slice(5, 16)
const pct = (v, ph) => {
  const tot = (ph.pos || 0) + (ph.neu || 0) + (ph.neg || 0)
  return tot ? ((v / tot) * 100).toFixed(1) + '%' : '0%'
}
const bucketLabel = (b) => (b === null || b === undefined || b === '') ? '其他/无情感'
  : (b === 1 || b === '1') ? '推荐驱动' : (b === 0 || b === '0') ? '自然到达' : String(b)

const onReady = () => { ready.value = true; nextTick(fetchData) }

const onChange = () => {
  if (mode.value === 'single') fetchData()
  else fetchCompare()
}
const onModeChange = async () => {
  // 切换到对比模式时若两阶段相同，默认取相邻两阶段
  if (mode.value === 'compare' && phaseA.value === phaseB.value) {
    const list = phaseList.value
    if (list.length >= 2) { phaseA.value = list[0]; phaseB.value = list[1] }
  }
  await nextTick()
  onChange()
}
const pctText = (v) => v == null ? '-' : (v * 100).toFixed(1) + '%'
const deltaText = (v, n=0) => v == null || isNaN(v) ? '' :
  ((v > 0 ? '+' : '') + (n ? v.toFixed(n) : v.toString()))
const deltaPct = (v) => v == null || isNaN(v) ? '' :
  ((v > 0 ? '+' : '') + (v * 100).toFixed(1) + 'pp')
const deltaCls = (v) => v == null ? '' : (v > 0 ? 'up' : v < 0 ? 'down' : '')

const lockPhase = (p) => {
  lockedPhase.value = p
  localStorage.setItem('va_locked_phase', p)
  ElMessage.success(`已聚焦「${p}」，群体与用户分析将自动沿用`)
}
const clearLock = () => {
  lockedPhase.value = ''
  localStorage.removeItem('va_locked_phase')
}

const fetchData = async () => {
  try {
    const res = await vaAPI.getLifecycle(breakdown.value)
    phases.value = res.phases || []
    timeline.value = res.timeline || []
    timelineBreakdown.value = res.timeline_breakdown || []
    snapshots.value = res.snapshots || []
    // 若对比模式从未初始化，把 A/B 设为前两阶段
    if (phaseList.value.length >= 2 && (!phaseList.value.includes(phaseA.value)
      || !phaseList.value.includes(phaseB.value))) {
      phaseA.value = phaseList.value[0]
      phaseB.value = phaseList.value[1]
    }
    await nextTick()
    renderMain()
    renderStream()
    renderSnapshot()
  } catch (e) {
    console.error(e)
    ElMessage.error('加载生命周期数据失败')
  }
}

const fetchCompare = async () => {
  if (!phaseA.value || !phaseB.value) return
  // 阶段元数据可能还没加载，先确保 phases 有数据
  if (!phases.value.length) {
    try {
      const r0 = await vaAPI.getLifecycle(breakdown.value)
      phases.value = r0.phases || []
      if (phaseList.value.length >= 2) {
        phaseA.value = phaseList.value[0]; phaseB.value = phaseList.value[1]
      }
    } catch (e) { /* ignore */ }
  }
  if (phaseA.value === phaseB.value) {
    ElMessage.warning('请选择两个不同的阶段进行对比')
    return
  }
  try {
    cmp.value = await vaAPI.compareLifecycle(phaseA.value, phaseB.value, breakdown.value)
    await nextTick()
    renderLift()
    renderCmpRatio()
  } catch (e) {
    console.error(e)
    ElMessage.error('加载阶段对比数据失败')
  }
}

const renderMain = () => {
  if (!mainChart.value) return
  mainInst = mainInst || echarts.init(mainChart.value)
  const hours = timeline.value.map(d => d.hour)
  const counts = timeline.value.map(d => d.event_count)
  const senti = timeline.value.map(d => d.avg_sentiment == null ? null : +d.avg_sentiment.toFixed(3))
  // 阶段背景带
  const markAreas = phases.value.map(ph => [
    { xAxis: (ph.start || '').slice(0, 13), itemStyle: { color: phaseColor[ph.order] + '22' },
      label: { show: true, formatter: ph.phase, color: '#b8b8d1', position: 'insideTop' } },
    { xAxis: (ph.end || '').slice(0, 13) }
  ])
  mainInst.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(26,26,46,0.95)', borderColor: '#667eea',
      textStyle: { color: '#fff' } },
    legend: { data: ['行为事件量', '平均情感分'], textStyle: { color: '#b8b8d1' }, top: 4 },
    grid: { left: 50, right: 55, top: 44, bottom: 60 },
    xAxis: { type: 'category', data: hours, axisLabel: { color: '#b8b8d1', rotate: 45 },
      axisLine: { lineStyle: { color: '#2d2d44' } } },
    yAxis: [
      { type: 'value', name: '事件量', axisLabel: { color: '#b8b8d1' },
        splitLine: { lineStyle: { color: '#2d2d44', type: 'dashed' } } },
      { type: 'value', name: '情感分', min: -1, max: 1, axisLabel: { color: '#b8b8d1' },
        splitLine: { show: false } }
    ],
    dataZoom: [{ type: 'slider', height: 18, bottom: 8, textStyle: { color: '#b8b8d1' } }],
    series: [
      { name: '行为事件量', type: 'line', smooth: true, data: counts, symbol: 'none',
        lineStyle: { width: 2.5, color: '#667eea' },
        areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: 'rgba(102,126,234,0.35)' }, { offset: 1, color: 'rgba(102,126,234,0)' }]) },
        markArea: { silent: true, data: markAreas } },
      { name: '平均情感分', type: 'line', smooth: true, yAxisIndex: 1, data: senti, symbol: 'none',
        connectNulls: true, lineStyle: { width: 2, color: '#f6bd16' } }
    ]
  })
}

const buildStacked = (records, keyField, valField, catField) => {
  // 把 [{cat, key, val}] 透视成 ECharts 堆叠 series
  const cats = [...new Set(records.map(r => r[catField]))].sort()
  const keys = [...new Set(records.map(r => bucketLabel(r[keyField])))]
  const idx = {}
  cats.forEach((c, i) => { idx[c] = i })
  const series = keys.map(k => ({
    name: k, type: 'bar', stack: 'total',
    emphasis: { focus: 'series' },
    data: new Array(cats.length).fill(0)
  }))
  const sByName = {}
  series.forEach(s => { sByName[s.name] = s })
  records.forEach(r => {
    const k = bucketLabel(r[keyField])
    sByName[k].data[idx[r[catField]]] += r[valField]
  })
  return { cats, series }
}

const renderStream = () => {
  if (!streamChart.value) return
  streamInst = streamInst || echarts.init(streamChart.value)
  const { cats, series } = buildStacked(timelineBreakdown.value, 'bucket', 'cnt', 'hour')
  series.forEach(s => { s.type = 'line'; s.stack = 'total'; s.areaStyle = {}; s.smooth = true; s.symbol = 'none' })
  streamInst.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(26,26,46,0.95)', borderColor: '#667eea',
      textStyle: { color: '#fff' } },
    legend: { type: 'scroll', textStyle: { color: '#b8b8d1' }, top: 0 },
    grid: { left: 50, right: 20, top: 36, bottom: 56 },
    xAxis: { type: 'category', data: cats, axisLabel: { color: '#b8b8d1', rotate: 45 },
      axisLine: { lineStyle: { color: '#2d2d44' } } },
    yAxis: { type: 'value', axisLabel: { color: '#b8b8d1' },
      splitLine: { lineStyle: { color: '#2d2d44', type: 'dashed' } } },
    dataZoom: [{ type: 'slider', height: 16, bottom: 6, textStyle: { color: '#b8b8d1' } }],
    series
  })
}

const renderSnapshot = () => {
  if (!snapChart.value) return
  snapInst = snapInst || echarts.init(snapChart.value)
  const order = ['潜伏期', '爆发期', '扩散期', '衰退期']
  const recs = snapshots.value.slice().sort(
    (a, b) => order.indexOf(a.phase) - order.indexOf(b.phase))
  let { cats, series } = buildStacked(recs, 'bucket', 'cnt', 'phase')
  cats = order.filter(c => cats.includes(c))
  // 重新按 order 对齐
  const idx = {}; cats.forEach((c, i) => { idx[c] = i })
  series.forEach(s => { s.data = new Array(cats.length).fill(0) })
  const sByName = {}; series.forEach(s => { sByName[s.name] = s })
  recs.forEach(r => {
    if (idx[r.phase] === undefined) return
    sByName[bucketLabel(r.bucket)].data[idx[r.phase]] += r.cnt
  })
  if (snapMode.value === 'ratio') {
    const totals = new Array(cats.length).fill(0)
    series.forEach(s => s.data.forEach((v, i) => { totals[i] += v }))
    series.forEach(s => { s.data = s.data.map((v, i) => totals[i] ? +(v / totals[i] * 100).toFixed(2) : 0) })
  }
  snapInst.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(26,26,46,0.95)', borderColor: '#667eea', textStyle: { color: '#fff' },
      valueFormatter: v => snapMode.value === 'ratio' ? v + '%' : v },
    legend: { type: 'scroll', textStyle: { color: '#b8b8d1' }, top: 0 },
    grid: { left: 50, right: 20, top: 36, bottom: 30 },
    xAxis: { type: 'category', data: cats, axisLabel: { color: '#b8b8d1' },
      axisLine: { lineStyle: { color: '#2d2d44' } } },
    yAxis: { type: 'value', axisLabel: { color: '#b8b8d1',
      formatter: snapMode.value === 'ratio' ? '{value}%' : '{value}' },
      splitLine: { lineStyle: { color: '#2d2d44', type: 'dashed' } } },
    series
  })
}

const renderLift = () => {
  if (!liftChart.value) return
  liftInst = liftInst || echarts.init(liftChart.value)
  const list = (cmp.value.comparison || []).slice(0, 14).reverse()
  const labels = list.map(c => bucketLabel(c.bucket))
  const lifts = list.map(c => c.lift == null ? 0 : c.lift - 1)
  liftInst.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(26,26,46,0.95)', borderColor: '#667eea', textStyle: { color: '#fff' },
      formatter: p => {
        const r = list[p[0].dataIndex]
        return `<b>${bucketLabel(r.bucket)}</b><br/>`
          + `${cmp.value.phase_a?.name} 占比 ${(r.ratio_a*100).toFixed(2)}%<br/>`
          + `${cmp.value.phase_b?.name} 占比 ${(r.ratio_b*100).toFixed(2)}%<br/>`
          + `lift ${r.lift ?? '—'}（${r.lift==null?'-':r.lift>1?'↑':'↓'}）`
      }
    },
    grid: { left: 130, right: 40, top: 10, bottom: 30 },
    xAxis: { type: 'value', name: 'lift − 1', nameTextStyle: { color: '#b8b8d1' },
      axisLabel: { color: '#b8b8d1', formatter: v => (v >= 0 ? '+' : '') + v.toFixed(2) },
      splitLine: { lineStyle: { color: '#2d2d44', type: 'dashed' } } },
    yAxis: { type: 'category', data: labels, axisLabel: { color: '#b8b8d1' },
      axisLine: { lineStyle: { color: '#2d2d44' } } },
    series: [{
      type: 'bar', data: lifts.map(v => ({
        value: v,
        itemStyle: { color: v > 0 ? '#ff6b6b' : v < 0 ? '#5b8ff9' : '#71717a',
          borderRadius: [0, 4, 4, 0] }
      })),
      label: { show: true, color: '#b8b8d1', position: 'insideRight',
        formatter: p => p.value === 0 ? '' : (p.value > 0 ? '+' : '') + p.value.toFixed(2) }
    }]
  })
}

const renderCmpRatio = () => {
  if (!cmpRatioChart.value) return
  cmpRatioInst = cmpRatioInst || echarts.init(cmpRatioChart.value)
  const list = (cmp.value.comparison || []).slice(0, 14)
  const labels = list.map(c => bucketLabel(c.bucket))
  cmpRatioInst.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(26,26,46,0.95)', borderColor: '#667eea', textStyle: { color: '#fff' },
      valueFormatter: v => (v * 100).toFixed(2) + '%' },
    legend: { top: 0, textStyle: { color: '#b8b8d1' } },
    grid: { left: 50, right: 20, top: 36, bottom: 60 },
    xAxis: { type: 'category', data: labels, axisLabel: { color: '#b8b8d1', rotate: 30 },
      axisLine: { lineStyle: { color: '#2d2d44' } } },
    yAxis: { type: 'value', axisLabel: { color: '#b8b8d1', formatter: '{value}' },
      splitLine: { lineStyle: { color: '#2d2d44', type: 'dashed' } } },
    series: [
      { name: cmp.value.phase_a?.name, type: 'bar',
        data: list.map(c => c.ratio_a), itemStyle: { color: '#5b8ff9' } },
      { name: cmp.value.phase_b?.name, type: 'bar',
        data: list.map(c => c.ratio_b), itemStyle: { color: '#ff6b6b' } }
    ]
  })
}

onMounted(() => {
  window.addEventListener('resize', () => {
    mainInst && mainInst.resize()
    streamInst && streamInst.resize()
    snapInst && snapInst.resize()
    liftInst && liftInst.resize()
    cmpRatioInst && cmpRatioInst.resize()
  })
})
</script>

<style scoped>
.control-bar { display: flex; align-items: center; gap: var(--spacing-md);
  padding: var(--spacing-md) var(--spacing-lg); margin-bottom: var(--spacing-md); }
.ctrl-label { font-size: 13px; font-weight: 600; color: var(--text-secondary); }
.spacer { flex: 1; }
.locked-tag { font-size: 13px; color: #f6bd16; }

.phase-cards { display: grid; grid-template-columns: repeat(4, 1fr);
  gap: var(--spacing-md); margin-bottom: var(--spacing-md); }
.phase-card { background: var(--bg-secondary); border: 1px solid var(--border-color);
  border-top: 3px solid #5b8ff9; border-radius: var(--radius-md);
  padding: var(--spacing-md); cursor: pointer; transition: all .25s; }
.phase-card:hover { transform: translateY(-3px); box-shadow: var(--shadow-lg); }
.phase-card.locked { box-shadow: var(--shadow-glow); border-color: #f6bd16; }
.pc-head { display: flex; justify-content: space-between; align-items: baseline; }
.pc-name { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.pc-order { font-size: 11px; color: var(--text-muted); }
.pc-time { font-size: 11px; color: var(--text-secondary); margin: 4px 0 10px; }
.pc-stats { display: flex; justify-content: space-between; margin-bottom: 10px; }
.pc-stat { display: flex; flex-direction: column; align-items: center; }
.pc-stat b { font-size: 18px; color: var(--primary-color); }
.pc-stat span { font-size: 11px; color: var(--text-muted); }
.senti-bar { display: flex; height: 8px; border-radius: 4px; overflow: hidden;
  background: var(--bg-tertiary); margin-bottom: 4px; }
.seg.pos { background: #4ECDC4; } .seg.neu { background: #71717a; } .seg.neg { background: #ff6b6b; }
.senti-avg { font-size: 11px; color: var(--text-secondary); }
.pc-lock-hint { font-size: 11px; color: var(--text-muted); margin-top: 8px; text-align: center; }
.phase-card.locked .pc-lock-hint { color: #f6bd16; }

.chart-card { margin-bottom: var(--spacing-md); position: relative; }
.chart-title { font-size: 15px; font-weight: 600; color: var(--text-primary);
  margin-bottom: var(--spacing-md); padding-bottom: var(--spacing-sm);
  border-bottom: 2px solid var(--border-color); }
.chart-row { display: grid; grid-template-columns: 1fr 1fr; gap: var(--spacing-md); }
.chart { width: 100%; }
.mini-toggle { position: absolute; right: var(--spacing-lg); top: var(--spacing-md); }
.next-hint { padding: var(--spacing-md) var(--spacing-lg); font-size: 13px;
  color: var(--text-secondary); display: flex; align-items: center;
  justify-content: space-between; gap: var(--spacing-md); }
.ctrl-arrow { color: var(--text-muted); font-size: 16px; }

.cmp-summary { display: grid; grid-template-columns: 1fr 1fr; gap: var(--spacing-md);
  margin-bottom: var(--spacing-md); }
.cmp-side { background: var(--bg-secondary); border: 1px solid var(--border-color);
  border-radius: var(--radius-md); padding: var(--spacing-md) var(--spacing-lg); }
.cmp-side.baseline { border-left: 3px solid #5b8ff9; }
.cmp-side:not(.baseline) { border-left: 3px solid #ff6b6b; }
.cmp-head { display: flex; justify-content: space-between; align-items: baseline;
  margin-bottom: var(--spacing-sm); }
.cmp-head b { font-size: 17px; color: var(--text-primary); }
.cmp-head span { font-size: 11px; color: var(--text-muted); }
.cmp-stats { display: grid; grid-template-columns: repeat(5, 1fr); gap: var(--spacing-sm); }
.cmp-stats > div { display: flex; flex-direction: column; align-items: center;
  background: var(--bg-tertiary); border-radius: var(--radius-sm); padding: 6px 4px; }
.cmp-stats b { font-size: 16px; color: var(--primary-color); }
.cmp-stats span { font-size: 11px; color: var(--text-muted); margin-top: 2px;
  display: flex; align-items: center; gap: 4px; }
.cmp-stats em { font-style: normal; font-size: 10px; padding: 1px 5px; border-radius: 8px;
  background: var(--bg-secondary); }
.cmp-stats em.up { color: #ff6b6b; background: rgba(255,107,107,.15); }
.cmp-stats em.down { color: #4ECDC4; background: rgba(78,205,196,.15); }
@media (max-width: 1100px) {
  .phase-cards { grid-template-columns: repeat(2, 1fr); }
  .chart-row { grid-template-columns: 1fr; }
}
</style>
