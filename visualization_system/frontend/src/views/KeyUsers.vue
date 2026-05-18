<template>
  <div class="key-users-view">
    <VaStatusBar :step="5" @ready="onReady" />

    <template v-if="ready">
      <!-- 筛选面板 -->
      <div class="card filter-panel">
        <div class="fp-row">
          <span class="fp-label">关键角色</span>
          <el-select v-model="role" style="width: 140px" @change="run">
            <el-option label="全部" value="all" />
            <el-option v-for="r in roleOptions" :key="r" :label="r" :value="r" />
          </el-select>

          <span class="fp-label">排序依据</span>
          <el-select v-model="sortBy" style="width: 150px" @change="run">
            <el-option v-for="s in sortOptions" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>

          <span class="fp-label">聚焦阶段</span>
          <el-select v-model="phase" clearable placeholder="全部阶段" style="width: 130px" @change="run">
            <el-option v-for="p in phaseOrder" :key="p" :label="p" :value="p" />
          </el-select>

          <span class="fp-label">数量</span>
          <el-input-number v-model="limit" :min="10" :max="200" :step="10" @change="run" />

          <div class="spacer" />
          <el-button type="primary" @click="run">应用筛选</el-button>
        </div>

        <div class="fp-conditions">
          <span class="fp-label">条件组合</span>
          <div v-for="(c, i) in conditions" :key="i" class="cond-item">
            <el-select v-model="c.dim" placeholder="选择特征" style="width: 130px" @change="c.values = []">
              <el-option v-for="d in userDims" :key="d.id" :label="d.name" :value="d.id" />
            </el-select>
            <el-select v-model="c.values" multiple collapse-tags collapse-tags-tooltip
              placeholder="选择取值" style="width: 230px" :disabled="!c.dim">
              <el-option v-for="v in dimValues(c.dim)" :key="v" :label="String(v)" :value="v" />
            </el-select>
            <el-button link type="danger" @click="conditions.splice(i, 1)">移除</el-button>
          </div>
          <el-button link type="primary" @click="conditions.push({ dim: '', values: [] })">
            ＋ 添加条件
          </el-button>
          <span v-if="fromGroup" class="from-group">
            （来自群体分析：{{ fromGroup }}）
          </span>
        </div>
      </div>

      <!-- 角色分布 + 关键用户排名 -->
      <div class="chart-row">
        <div class="card chart-card role-card">
          <h3 class="chart-title">👥 角色构成</h3>
          <div ref="roleChart" class="chart" style="height: 300px"></div>
        </div>
        <div class="card chart-card">
          <h3 class="chart-title">
            🏆 关键用户排名（Top {{ Math.min(20, users.length) }} · 按{{ sortName }}）
          </h3>
          <div ref="rankChart" class="chart" style="height: 300px"></div>
        </div>
      </div>

      <!-- 用户明细表 -->
      <div class="card">
        <h3 class="chart-title">📋 关键用户明细（{{ users.length }} 人）</h3>
        <el-table :data="users" stripe style="width: 100%" max-height="500" @row-click="openUser">
          <el-table-column type="index" label="#" width="50" />
          <el-table-column prop="name" label="用户" min-width="120" />
          <el-table-column prop="role" label="角色" width="110">
            <template #default="{ row }">
              <el-tag :type="roleTagType(row.role)">{{ row.role }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="influence_score" label="影响力" width="90" sortable />
          <el-table-column prop="influence_tier" label="分层" width="80" />
          <el-table-column prop="num_followers" label="粉丝" width="80" sortable />
          <el-table-column prop="pagerank" label="PageRank" width="100" sortable>
            <template #default="{ row }">{{ ((row.pagerank || 0) * 1000).toFixed(2) }}‰</template>
          </el-table-column>
          <el-table-column prop="post_count" label="原创" width="70" sortable />
          <el-table-column prop="repost_count" label="转发" width="70" sortable />
          <el-table-column prop="reposts_received" label="被转发" width="90" sortable />
          <el-table-column prop="likes_received" label="获赞" width="80" sortable />
          <el-table-column prop="activity_level" label="活跃度" width="90" sortable />
          <el-table-column prop="behavior_label" label="行为标签" width="100" />
          <el-table-column prop="community_id" label="社群" width="70" />
        </el-table>
        <p class="table-hint">点击任一行可查看该用户的画像、行为轨迹与发布内容</p>
      </div>
    </template>

    <!-- 个体溯源 -->
    <el-dialog v-model="dialogVisible" :title="`个体溯源 · ${detail?.profile?.name || ''}`"
      width="900px" top="6vh">
      <div v-if="detail" class="drill">
        <div class="drill-profile">
          <div class="dp-item" v-for="f in profileFields" :key="f.k">
            <span class="dp-label">{{ f.label }}</span>
            <span class="dp-value">{{ detail.profile[f.k] }}</span>
          </div>
        </div>
        <div class="drill-charts">
          <div class="dc-box">
            <h4>行为构成</h4>
            <div ref="mixChart" style="height: 240px"></div>
          </div>
          <div class="dc-box">
            <h4>各阶段活跃度</h4>
            <div ref="phaseChart" style="height: 240px"></div>
          </div>
        </div>
        <div class="dc-box">
          <h4>行为轨迹（逐小时）</h4>
          <div ref="trackChart" style="height: 220px"></div>
        </div>

        <!-- 影响力获取路径 -->
        <div class="dc-box" v-if="influencePath">
          <h4>影响力获取路径
            <span class="dc-sub">
              共 {{ influencePath.total }} 次外部反馈
              · 转发 {{ influencePath.totals.reposts }}
              · 评论 {{ influencePath.totals.comments }}
              · 点赞 {{ influencePath.totals.likes }}
            </span>
          </h4>
          <div ref="pathChart" style="height: 240px"></div>
          <div v-if="influencePath.top_sources && influencePath.top_sources.length" class="top-sources">
            <span class="ts-label">主要扩散来源（按转发×3+评论×2+点赞加权）</span>
            <div class="ts-list">
              <div v-for="s in influencePath.top_sources.slice(0, 6)" :key="s.src_user_id"
                class="ts-chip" :class="(s.src_tier||'').toLowerCase()">
                <b>{{ s.src_name || '匿名' }}</b>
                <span class="ts-role">{{ s.src_role || '—' }}</span>
                <span class="ts-stat">🔁{{ s.repost }} 💬{{ s.comment }} ❤️{{ s.like }}</span>
                <span class="ts-meta">影响力 {{ s.src_influence ?? '—' }} · 粉丝 {{ s.src_followers ?? 0 }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="drill-posts">
          <h4>发布内容（最近 {{ detail.posts.length }} 条）</h4>
          <div v-for="p in detail.posts" :key="p.post_id" class="post-item">
            <el-tag size="small" :type="p.is_repost ? 'info' : 'primary'">
              {{ p.is_repost ? '转发' : '原创' }}
            </el-tag>
            <el-tag size="small" :type="sentiTag(p.sentiment_class)">{{ p.sentiment_class }}</el-tag>
            <span class="post-phase">{{ p.phase }}</span>
            <span class="post-content">{{ p.content || '[无文本]' }}</span>
            <span class="post-stat">❤️{{ p.num_likes }} 🔁{{ p.num_shares }} 💬{{ p.comment_count }}
              · 级联{{ p.cascade_size }}/深{{ p.cascade_depth }}</span>
          </div>
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, nextTick, onMounted } from 'vue'
import * as echarts from 'echarts'
import { ElMessage } from 'element-plus'
import { vaAPI } from '@/api'
import VaStatusBar from '@/components/VaStatusBar.vue'

const ready = ref(false)
const catalog = ref({ dimensions: [], phase_order: [] })
const role = ref('all')
const sortBy = ref('influence_score')
const phase = ref('')
const limit = ref(50)
const conditions = ref([])
const users = ref([])
const roleDist = ref([])
const fromGroup = ref('')

const influencePath = ref(null)

const sortOptions = [
  { id: 'influence_score', name: '影响力分数' },
  { id: 'pagerank', name: 'PageRank' },
  { id: 'num_followers', name: '粉丝数' },
  { id: 'reposts_received', name: '被转发数' },
  { id: 'likes_received', name: '获赞数' },
  { id: 'activity_level', name: '活跃度' },
  { id: 'post_count', name: '原创数' }
]
const roleOptions = ['意见领袖', '讨论发起者', '活跃用户', '普通传播者', '边缘用户']
const profileFields = [
  { k: 'role', label: '角色' }, { k: 'influence_tier', label: '影响力分层' },
  { k: 'behavior_label', label: '行为标签' }, { k: 'community_id', label: '所属社群' },
  { k: 'num_followers', label: '粉丝数' }, { k: 'num_followings', label: '关注数' },
  { k: 'influence_score', label: '影响力分' }, { k: 'reposts_received', label: '被转发' },
  { k: 'likes_received', label: '获赞' }, { k: 'activity_level', label: '活跃度' },
  { k: 'gender', label: '性别' }, { k: 'profession', label: '职业' }
]

const roleChart = ref(null)
const rankChart = ref(null)
const mixChart = ref(null)
const phaseChart = ref(null)
const trackChart = ref(null)
const pathChart = ref(null)
let roleInst, rankInst, mixInst, phaseInst, trackInst, pathInst

const dialogVisible = ref(false)
const detail = ref(null)

const userDims = computed(() =>
  (catalog.value.dimensions || []).filter(d => d.group === '用户维度'))
const phaseOrder = computed(() => catalog.value.phase_order || [])
const sortName = computed(() => sortOptions.find(s => s.id === sortBy.value)?.name || '')
const dimValues = (dimId) =>
  (catalog.value.dimensions || []).find(d => d.id === dimId)?.values || []

const roleTagType = (r) => ({
  '意见领袖': 'danger', '讨论发起者': 'warning', '活跃用户': 'success',
  '普通传播者': 'info', '边缘用户': ''
}[r] || '')
const sentiTag = (s) => ({ '正面': 'success', '负面': 'danger', '中性': 'info' }[s] || 'info')

const onReady = async () => {
  try {
    catalog.value = await vaAPI.getCatalog()
    // 接收来自「关键群体识别」页的跳转上下文
    const gf = localStorage.getItem('va_group_filter')
    if (gf) {
      const obj = JSON.parse(gf)
      conditions.value.push({ dim: obj.dim, values: [obj.value] })
      if (obj.phase) phase.value = obj.phase
      fromGroup.value = String(obj.value)
      localStorage.removeItem('va_group_filter')
    } else {
      const lp = localStorage.getItem('va_locked_phase')
      if (lp) phase.value = lp
    }
    ready.value = true
    await nextTick()
    run()
  } catch (e) {
    console.error(e)
    ElMessage.error('加载维度目录失败')
  }
}

const buildFilters = () =>
  conditions.value.filter(c => c.dim && c.values.length)
    .map(c => ({ dim: c.dim, values: c.values }))

const run = async () => {
  try {
    const res = await vaAPI.getKeyUsers({
      role: role.value, sortBy: sortBy.value, phase: phase.value || null,
      limit: limit.value, filters: buildFilters()
    })
    users.value = res.users || []
    roleDist.value = res.role_distribution || []
    await nextTick()
    renderRole()
    renderRank()
  } catch (e) {
    console.error(e)
    ElMessage.error('查询关键用户失败')
  }
}

const renderRole = () => {
  if (!roleChart.value) return
  roleInst = roleInst || echarts.init(roleChart.value)
  const colorMap = {
    '意见领袖': '#ff6b6b', '讨论发起者': '#f6bd16', '活跃用户': '#4ECDC4',
    '普通传播者': '#5b8ff9', '边缘用户': '#71717a'
  }
  roleInst.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item', backgroundColor: 'rgba(26,26,46,0.95)',
      borderColor: '#667eea', textStyle: { color: '#fff' } },
    legend: { bottom: 0, textStyle: { color: '#b8b8d1' } },
    series: [{
      type: 'pie', radius: ['42%', '68%'], center: ['50%', '46%'],
      data: roleDist.value.map(r => ({
        name: r.role, value: r.cnt, itemStyle: { color: colorMap[r.role] || '#888' }
      })),
      label: { color: '#b8b8d1', formatter: '{b}\n{c}' },
      labelLine: { lineStyle: { color: '#2d2d44' } }
    }]
  })
}

const renderRank = () => {
  if (!rankChart.value) return
  rankInst = rankInst || echarts.init(rankChart.value)
  const top = users.value.slice(0, 20).reverse()
  const valKey = sortBy.value
  rankInst.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(26,26,46,0.95)', borderColor: '#667eea', textStyle: { color: '#fff' } },
    grid: { left: 110, right: 40, top: 10, bottom: 24 },
    xAxis: { type: 'value', axisLabel: { color: '#b8b8d1' },
      splitLine: { lineStyle: { color: '#2d2d44', type: 'dashed' } } },
    yAxis: { type: 'category', data: top.map(u => u.name),
      axisLabel: { color: '#b8b8d1' }, axisLine: { lineStyle: { color: '#2d2d44' } } },
    series: [{
      type: 'bar', data: top.map(u => u[valKey]),
      itemStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 1, 0, [
          { offset: 0, color: '#667eea' }, { offset: 1, color: '#f093fb' }]),
        borderRadius: [0, 4, 4, 0]
      },
      label: { show: true, position: 'right', color: '#b8b8d1' }
    }]
  })
}

const openUser = async (row) => {
  try {
    influencePath.value = null
    detail.value = await vaAPI.getUserDetail(row.user_id)
    dialogVisible.value = true
    await nextTick()
    renderDrill()
    // 异步加载影响力路径（不阻塞主对话框）
    try {
      influencePath.value = await vaAPI.getInfluencePath(row.user_id)
      await nextTick()
      renderPath()
    } catch (err) {
      console.warn('influence-path load failed', err)
    }
  } catch (e) {
    console.error(e)
    ElMessage.error('加载用户详情失败')
  }
}

const renderPath = () => {
  if (!pathChart.value || !influencePath.value) return
  pathInst = pathInst || echarts.init(pathChart.value)
  const p = influencePath.value.path || []
  // 把时间序列转成 [ts, cumulative_reposts] 三条曲线 + 来源用户散点
  const repostPts = p.map(r => [r.ts, r.cum_reposts])
  const commentPts = p.map(r => [r.ts, r.cum_comments])
  const likePts = p.map(r => [r.ts, r.cum_likes])
  // 在 repost 事件上做散点，按来源影响力着色
  const repostEvents = p.filter(r => r.action_type === 'repost').map(r => ({
    value: [r.ts, r.cum_reposts],
    name: r.src_name || '匿名',
    src_influence: r.src_influence ?? 0,
    src_role: r.src_role ?? '—',
    src_tier: r.src_tier ?? '—',
  }))
  pathInst.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      trigger: 'axis', axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(26,26,46,0.95)', borderColor: '#667eea', textStyle: { color: '#fff' },
      formatter: params => {
        if (!params.length) return ''
        const t = params[0].axisValueLabel
        const lines = [`<b>${t}</b>`]
        params.forEach(p => {
          if (p.seriesType === 'scatter' && p.data) {
            lines.push(`🔁 来自 <b>${p.data.name}</b>（${p.data.src_role}/${p.data.src_tier}）`
              + ` 影响力 ${p.data.src_influence}`)
          } else {
            lines.push(`${p.marker} ${p.seriesName}: ${p.value[1] ?? p.value}`)
          }
        })
        return lines.join('<br/>')
      }
    },
    legend: { top: 0, textStyle: { color: '#b8b8d1' } },
    grid: { left: 50, right: 20, top: 32, bottom: 40 },
    xAxis: { type: 'time', axisLabel: { color: '#b8b8d1' },
      splitLine: { lineStyle: { color: '#2d2d44', type: 'dashed' } } },
    yAxis: { type: 'value', name: '累计', nameTextStyle: { color: '#b8b8d1' },
      axisLabel: { color: '#b8b8d1' },
      splitLine: { lineStyle: { color: '#2d2d44', type: 'dashed' } } },
    series: [
      { name: '累计被转发', type: 'line', smooth: true, symbol: 'none', data: repostPts,
        lineStyle: { color: '#ff6b6b', width: 2.5 },
        areaStyle: { color: 'rgba(255,107,107,0.15)' } },
      { name: '累计评论', type: 'line', smooth: true, symbol: 'none', data: commentPts,
        lineStyle: { color: '#f6bd16', width: 1.8 } },
      { name: '累计点赞', type: 'line', smooth: true, symbol: 'none', data: likePts,
        lineStyle: { color: '#4ECDC4', width: 1.5 } },
      { name: '转发来源', type: 'scatter', data: repostEvents,
        symbolSize: v => 6 + Math.min(18, Math.sqrt((repostEvents.find(e=>e.value[0]===v[0]&&e.value[1]===v[1])||{}).src_influence || 0) * 0.7),
        itemStyle: { color: '#ff6b6b', opacity: 0.7, borderColor: '#fff', borderWidth: 0.5 }
      }
    ]
  })
}

const renderDrill = () => {
  const d = detail.value
  if (!d) return
  // 行为构成
  mixInst = echarts.init(mixChart.value)
  mixInst.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    series: [{
      type: 'pie', radius: ['35%', '65%'],
      data: d.action_mix.map(a => ({ name: a.action_type, value: a.cnt })),
      label: { color: '#b8b8d1' }, labelLine: { lineStyle: { color: '#2d2d44' } }
    }]
  })
  // 阶段活跃度
  phaseInst = echarts.init(phaseChart.value)
  const order = ['潜伏期', '爆发期', '扩散期', '衰退期']
  const pa = order.map(p => {
    const found = d.phase_activity.find(x => x.phase === p)
    return found ? found.cnt : 0
  })
  phaseInst.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    grid: { left: 50, right: 20, top: 20, bottom: 30 },
    xAxis: { type: 'category', data: order, axisLabel: { color: '#b8b8d1' } },
    yAxis: { type: 'value', axisLabel: { color: '#b8b8d1' },
      splitLine: { lineStyle: { color: '#2d2d44', type: 'dashed' } } },
    series: [{ type: 'bar', data: pa, itemStyle: { color: '#4ECDC4', borderRadius: [4, 4, 0, 0] } }]
  })
  // 行为轨迹
  trackInst = echarts.init(trackChart.value)
  const hours = [...new Set(d.timeline.map(t => t.hour))].sort()
  const actions = [...new Set(d.timeline.map(t => t.action_type))]
  const hidx = {}; hours.forEach((h, i) => { hidx[h] = i })
  const series = actions.map(a => ({
    name: a, type: 'bar', stack: 'x', data: new Array(hours.length).fill(0)
  }))
  const sByName = {}; series.forEach(s => { sByName[s.name] = s })
  d.timeline.forEach(t => { sByName[t.action_type].data[hidx[t.hour]] += t.cnt })
  trackInst.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { type: 'scroll', textStyle: { color: '#b8b8d1' }, top: 0 },
    grid: { left: 45, right: 20, top: 30, bottom: 50 },
    xAxis: { type: 'category', data: hours, axisLabel: { color: '#b8b8d1', rotate: 45 } },
    yAxis: { type: 'value', axisLabel: { color: '#b8b8d1' },
      splitLine: { lineStyle: { color: '#2d2d44', type: 'dashed' } } },
    series
  })
}

onMounted(() => {
  window.addEventListener('resize', () => {
    roleInst && roleInst.resize()
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
.spacer { flex: 1; }
.fp-conditions { display: flex; align-items: center; gap: var(--spacing-sm); flex-wrap: wrap;
  padding-top: var(--spacing-sm); border-top: 1px dashed var(--border-color); }
.cond-item { display: flex; align-items: center; gap: 6px;
  background: var(--bg-tertiary); padding: 4px 8px; border-radius: var(--radius-sm); }
.from-group { font-size: 12px; color: #f6bd16; }

.chart-row { display: grid; grid-template-columns: 360px 1fr; gap: var(--spacing-md);
  margin-bottom: var(--spacing-md); }
.chart-title { font-size: 15px; font-weight: 600; color: var(--text-primary);
  margin-bottom: var(--spacing-sm); }
.chart { width: 100%; }
.table-hint { font-size: 12px; color: var(--text-muted); margin-top: var(--spacing-sm); }

.dc-sub { font-size: 11px; color: var(--text-muted); font-weight: normal; margin-left: 8px; }
.top-sources { margin-top: var(--spacing-sm); padding-top: var(--spacing-sm);
  border-top: 1px dashed var(--border-color); }
.ts-label { font-size: 11px; color: var(--text-muted); }
.ts-list { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; margin-top: 8px; }
.ts-chip { background: var(--bg-tertiary); padding: 6px 10px; border-radius: var(--radius-sm);
  display: flex; flex-direction: column; gap: 2px; border-left: 3px solid #71717a; }
.ts-chip.头部 { border-left-color: #ff6b6b; }
.ts-chip.腰部 { border-left-color: #f6bd16; }
.ts-chip.长尾 { border-left-color: #5b8ff9; }
.ts-chip b { font-size: 13px; color: var(--text-primary); }
.ts-role { font-size: 11px; color: var(--text-secondary); }
.ts-stat { font-size: 11px; color: var(--text-primary); }
.ts-meta { font-size: 10px; color: var(--text-muted); }

.drill-profile { display: grid; grid-template-columns: repeat(4, 1fr); gap: var(--spacing-sm);
  margin-bottom: var(--spacing-md); }
.dp-item { background: var(--bg-tertiary); padding: 8px 12px; border-radius: var(--radius-sm); }
.dp-label { display: block; font-size: 11px; color: var(--text-muted); }
.dp-value { font-size: 14px; font-weight: 600; color: var(--text-primary); }
.drill-charts { display: grid; grid-template-columns: 1fr 1fr; gap: var(--spacing-md); }
.dc-box { margin-bottom: var(--spacing-md); }
.dc-box h4 { font-size: 13px; color: var(--text-secondary); margin: 0 0 var(--spacing-sm); }
.drill-posts h4 { font-size: 13px; color: var(--text-secondary); margin: 0 0 var(--spacing-sm); }
.post-item { display: flex; align-items: center; gap: 8px; padding: 6px 8px;
  border-bottom: 1px solid var(--border-color); font-size: 12px; }
.post-phase { color: var(--text-muted); }
.post-content { flex: 1; color: var(--text-primary); overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap; }
.post-stat { color: var(--text-muted); white-space: nowrap; }
@media (max-width: 1100px) {
  .chart-row { grid-template-columns: 1fr; }
  .drill-charts { grid-template-columns: 1fr; }
}
</style>
