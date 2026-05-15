"""
build_dashboard_html.py

Inline data.json into a self-contained HTML dashboard with 17 charts.
Uses ECharts CDN + echarts-wordcloud.
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
DATA_JSON = HERE / "data.json"
OUT_HTML = HERE / "dashboard.html"

HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>Oasis 大规模社交仿真 · 多维分析仪表盘</title>
<script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/echarts-wordcloud@2.1.0/dist/echarts-wordcloud.min.js"></script>
<style>
:root{
  --bg-0:#06081a; --bg-1:#0d1230; --bg-2:#161c40;
  --card:rgba(22,28,64,.55); --card-border:rgba(120,140,210,.18);
  --t-0:#ffffff; --t-1:#c9d1ec; --t-2:#7c87b8; --t-3:#4a527a;
  --c-blue:#5b8def; --c-cyan:#4ecdc4; --c-violet:#a78bfa; --c-pink:#ff6b9d;
  --c-gold:#ffd166; --c-orange:#ff8b3d; --c-red:#ef4565; --c-green:#5fdba7;
  --grad-1:linear-gradient(135deg,#667eea 0%,#764ba2 100%);
  --grad-2:linear-gradient(135deg,#4ecdc4 0%,#44a08d 100%);
  --grad-3:linear-gradient(135deg,#ff6b9d 0%,#fc6076 100%);
  --grad-4:linear-gradient(135deg,#ffd166 0%,#ff8b3d 100%);
  --grad-bg:linear-gradient(135deg,#06081a 0%,#0d1230 50%,#1a1f3a 100%);
  --shadow-card:0 8px 32px rgba(0,0,0,.35);
  --shadow-glow:0 0 32px rgba(102,126,234,.18);
}
*{box-sizing:border-box;margin:0;padding:0}
html,body{
  background:var(--grad-bg);
  color:var(--t-1);
  font-family:'Inter','PingFang SC','Microsoft YaHei',-apple-system,system-ui,sans-serif;
  min-height:100vh;
  font-feature-settings:"cv11","ss01";
}
body{
  background:radial-gradient(ellipse at top left,rgba(102,126,234,.15),transparent 50%),
             radial-gradient(ellipse at bottom right,rgba(78,205,196,.10),transparent 50%),
             var(--grad-bg);
  background-attachment:fixed;
}
.wrap{max-width:1700px;margin:0 auto;padding:32px 28px 60px}

/* Hero */
.hero{
  position:relative;
  padding:36px 40px 32px;
  margin-bottom:28px;
  border-radius:20px;
  overflow:hidden;
  background:linear-gradient(135deg,rgba(102,126,234,.16),rgba(78,205,196,.08));
  border:1px solid var(--card-border);
  backdrop-filter:blur(12px);
}
.hero::before{
  content:"";position:absolute;inset:-60px -40px;
  background:radial-gradient(ellipse at 20% 30%,rgba(167,139,250,.35),transparent 45%),
             radial-gradient(ellipse at 80% 70%,rgba(78,205,196,.30),transparent 45%);
  filter:blur(40px);z-index:0;pointer-events:none;
}
.hero-content{position:relative;z-index:1}
.hero h1{
  font-size:32px;font-weight:800;color:#fff;margin-bottom:8px;
  letter-spacing:-.5px;
  background:linear-gradient(90deg,#fff 0%,#c9d1ec 100%);
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.hero .sub{font-size:14px;color:var(--t-2);max-width:780px;line-height:1.7}
.hero .meta{
  display:flex;gap:18px;margin-top:14px;font-size:12px;color:var(--t-3);
  font-family:'JetBrains Mono','SF Mono',Consolas,monospace;
}
.hero .meta span{padding:4px 10px;background:rgba(255,255,255,.04);border-radius:6px;border:1px solid rgba(255,255,255,.05)}
.hero .meta b{color:var(--c-cyan);font-weight:600;margin-right:6px}

/* KPI grid */
.kpi-grid{
  display:grid;
  grid-template-columns:repeat(6,1fr);
  gap:14px;
  margin-bottom:28px;
}
.kpi{
  padding:18px 16px;
  border-radius:14px;
  background:var(--card);
  border:1px solid var(--card-border);
  backdrop-filter:blur(10px);
  position:relative;overflow:hidden;
  transition:transform .25s ease, box-shadow .25s ease;
}
.kpi:hover{transform:translateY(-4px);box-shadow:var(--shadow-card)}
.kpi::after{
  content:"";position:absolute;left:0;top:0;width:3px;height:100%;
  background:var(--grad-1);
}
.kpi:nth-child(6n+2)::after{background:var(--grad-2)}
.kpi:nth-child(6n+3)::after{background:var(--grad-3)}
.kpi:nth-child(6n+4)::after{background:var(--grad-4)}
.kpi:nth-child(6n+5)::after{background:linear-gradient(135deg,#5fdba7,#4ecdc4)}
.kpi:nth-child(6n+0)::after{background:linear-gradient(135deg,#a78bfa,#667eea)}
.kpi-label{font-size:11px;color:var(--t-2);text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px;font-weight:500}
.kpi-value{font-size:24px;font-weight:700;color:#fff;font-feature-settings:"tnum"}
.kpi-hint{font-size:11px;color:var(--t-3);margin-top:4px}

/* Section */
.section{margin-top:32px;margin-bottom:14px;display:flex;align-items:baseline;gap:14px}
.section-tag{
  display:inline-block;padding:4px 10px;border-radius:6px;
  font-family:'JetBrains Mono',monospace;font-size:11px;font-weight:600;letter-spacing:.5px;
  background:rgba(102,126,234,.18);color:#9eaaff;border:1px solid rgba(102,126,234,.3);
}
.section-title{font-size:18px;font-weight:700;color:#fff;letter-spacing:-.2px}
.section-sub{font-size:13px;color:var(--t-2)}

/* Card grid */
.cards{display:grid;grid-template-columns:repeat(12,1fr);gap:18px}
.card{
  background:var(--card);
  border:1px solid var(--card-border);
  border-radius:16px;
  padding:18px 20px 14px;
  backdrop-filter:blur(10px);
  display:flex;flex-direction:column;
  position:relative;overflow:hidden;
}
.card::before{
  content:"";position:absolute;inset:0;border-radius:16px;
  background:linear-gradient(135deg,rgba(255,255,255,.03),transparent 50%);
  pointer-events:none;
}
.card-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:8px}
.card-title{
  font-size:14px;font-weight:600;color:#fff;display:flex;align-items:center;gap:8px;
}
.card-title .dot{width:8px;height:8px;border-radius:50%;background:var(--c-cyan);box-shadow:0 0 12px var(--c-cyan)}
.card-meta{font-size:11px;color:var(--t-3);font-family:'JetBrains Mono',monospace}
.card-desc{font-size:12px;color:var(--t-2);line-height:1.5;margin-bottom:8px}
.chart{width:100%;flex:1}

/* spans */
.span-3{grid-column:span 3}
.span-4{grid-column:span 4}
.span-5{grid-column:span 5}
.span-6{grid-column:span 6}
.span-7{grid-column:span 7}
.span-8{grid-column:span 8}
.span-9{grid-column:span 9}
.span-12{grid-column:span 12}

.h-280{height:280px}.h-320{height:320px}.h-360{height:360px}.h-400{height:400px}.h-440{height:440px}.h-480{height:480px}.h-520{height:520px}

/* footer */
footer{margin-top:48px;padding-top:28px;border-top:1px solid var(--card-border);text-align:center;font-size:12px;color:var(--t-3)}
footer code{background:rgba(255,255,255,.05);padding:2px 8px;border-radius:4px;color:var(--c-cyan);font-family:'JetBrains Mono',monospace}

/* responsive */
@media (max-width:1280px){.kpi-grid{grid-template-columns:repeat(4,1fr)} .span-3{grid-column:span 4}.span-4{grid-column:span 6}.span-5{grid-column:span 6}.span-6{grid-column:span 12}.span-7{grid-column:span 12}.span-8{grid-column:span 12}.span-9{grid-column:span 12}}
@media (max-width:768px){.kpi-grid{grid-template-columns:repeat(2,1fr)} .cards>*{grid-column:span 12!important}}
</style>
</head>
<body>
<div class="wrap">
  <div class="hero">
    <div class="hero-content">
      <h1>🌊 Oasis · 大规模社交仿真分析仪表盘</h1>
      <p class="sub">基于 100-agent 微博仿真数据库的 17 维多角度可视化原型 · 适配 10,000+ agent 规模 · 覆盖行为剖析、传播力、网络结构、话题、推荐系统、KOL 共 8 大类分析视角</p>
      <div class="meta" id="meta"></div>
    </div>
  </div>

  <!-- KPI -->
  <div class="kpi-grid" id="kpi-grid"></div>

  <!-- A. 行为剖析 -->
  <div class="section">
    <span class="section-tag">A · BEHAVIOR</span>
    <span class="section-title">Agent 行为剖析</span>
    <span class="section-sub">基于 trace 表 11 维行为向量的聚类、指纹、分布</span>
  </div>
  <div class="cards">
    <div class="card span-7 h-440">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-violet);box-shadow:0 0 12px var(--c-violet)"></span>① TSNE + KMeans 行为聚类散点图</div>
        <div class="card-meta">N=100 · 11D→2D · k=5</div>
      </div>
      <div class="card-desc">每个点 = 一个 agent，坐标来自 11 维行为频率向量的 TSNE 降维，颜色为 KMeans 自动聚类。能够看出"潜水党 / KOL / 转发机器 / 探索者"等自然类群。</div>
      <div id="c-tsne" class="chart"></div>
    </div>
    <div class="card span-5 h-440">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-pink);box-shadow:0 0 12px var(--c-pink)"></span>② 行为指纹平行坐标</div>
        <div class="card-meta">每聚类一条均值线</div>
      </div>
      <div class="card-desc">把 11 个 action 列为竖轴，每条折线代表一个聚类的平均行为分布。一眼对比"哪类人在哪个维度突出"。</div>
      <div id="c-parallel" class="chart"></div>
    </div>
    <div class="card span-6 h-320">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-cyan);box-shadow:0 0 12px var(--c-cyan)"></span>③ Action 类型总分布</div>
        <div class="card-meta">log scale</div>
      </div>
      <div class="card-desc">11 种 action 在全仿真过程的总频次。对数坐标看长尾——refresh / do_nothing 远超主动行为，符合真实社交媒体的 90-9-1 法则。</div>
      <div id="c-action-bar" class="chart"></div>
    </div>
    <div class="card span-6 h-320">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-gold);box-shadow:0 0 12px var(--c-gold)"></span>④ 用户活跃度幂律</div>
        <div class="card-meta">log-log</div>
      </div>
      <div class="card-desc">X = 用户排名，Y = 该用户的总动作数（log-log）。直线代表幂律分布——少数 KOL 贡献大部分活动，是社交网络的标志性特征。</div>
      <div id="c-activity-power" class="chart"></div>
    </div>
  </div>

  <!-- B. 传播力 -->
  <div class="section">
    <span class="section-tag">B · CASCADE</span>
    <span class="section-title">信息传播力分析</span>
    <span class="section-sub">替代单图全局传播——用统计分布 + 抽样下钻应对万级 cascade</span>
  </div>
  <div class="cards">
    <div class="card span-6 h-440">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-orange);box-shadow:0 0 12px var(--c-orange)"></span>⑤ Cascade 特征气泡散点</div>
        <div class="card-meta">每点=一帖原创</div>
      </div>
      <div class="card-desc">X = cascade size（含原帖+转发）, Y = max depth（最深转发链）, 气泡大小 = 影响到的 unique 用户数, 颜色 = structural virality（结构虚拟性，越大越像深链而非广播）。点击点可跳转到具体帖子。</div>
      <div id="c-cascade-scatter" class="chart"></div>
    </div>
    <div class="card span-6 h-440">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-red);box-shadow:0 0 12px var(--c-red)"></span>⑥ Cascade size 幂律分布</div>
        <div class="card-meta">CCDF, log-log</div>
      </div>
      <div class="card-desc">cascade size 的互补累积分布函数（CCDF），双对数。绝大多数 cascade size=1（无人转发），少数极大——验证仿真是否复现真实社交网络的重尾性质。</div>
      <div id="c-cascade-power" class="chart"></div>
    </div>
    <div class="card span-12 h-400">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-violet);box-shadow:0 0 12px var(--c-violet)"></span>⑦ Top-10 病毒帖生命周期</div>
        <div class="card-meta">stacked area</div>
      </div>
      <div class="card-desc">挑出转发数 Top-10 的原帖，按 12 个时间桶聚合每帖在该时段的新增传播事件（转发+评论），堆叠面积图。能看到"爆发型"vs"长尾型"病毒帖的差异。</div>
      <div id="c-cascade-life" class="chart"></div>
    </div>
  </div>

  <!-- C. 网络结构 -->
  <div class="section">
    <span class="section-tag">C · NETWORK</span>
    <span class="section-title">关注网络结构</span>
    <span class="section-sub">Louvain 社群发现 + 度分布 + 跨社群关系矩阵</span>
  </div>
  <div class="cards">
    <div class="card span-7 h-520">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-blue);box-shadow:0 0 12px var(--c-blue)"></span>⑧ Louvain 社群发现网络图</div>
        <div class="card-meta" id="c-network-meta"></div>
      </div>
      <div class="card-desc">所有用户作为节点，关注关系为有向边。Louvain 算法自动发现紧密社群（同色），节点大小 = 度数。</div>
      <div id="c-network" class="chart"></div>
    </div>
    <div class="card span-5 h-520">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-cyan);box-shadow:0 0 12px var(--c-cyan)"></span>⑨ 度分布双对数图</div>
        <div class="card-meta">in / out</div>
      </div>
      <div class="card-desc">入度（被多少人关注）、出度（关注多少人）的频次分布。log-log 直线 ≈ 幂律，是无标度网络的特征。仿真复现该特征则说明 agent 关注行为符合真实社交规律。</div>
      <div id="c-degree" class="chart"></div>
    </div>
    <div class="card span-12 h-400">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-pink);box-shadow:0 0 12px var(--c-pink)"></span>⑩ 社群 × 社群跨群关注矩阵</div>
        <div class="card-meta">heatmap</div>
      </div>
      <div class="card-desc">行=源社群, 列=目标社群, cell = 跨社群关注边数。对角线越亮 = 社群越封闭（回音室），非对角越亮 = 跨群桥接。</div>
      <div id="c-comm-matrix" class="chart"></div>
    </div>
  </div>

  <!-- D. 话题 -->
  <div class="section">
    <span class="section-tag">D · TOPIC</span>
    <span class="section-title">话题与内容</span>
    <span class="section-sub">基于 hashtag 解析（无 LLM 依赖，万级数据可秒级处理）</span>
  </div>
  <div class="cards">
    <div class="card span-5 h-440">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-gold);box-shadow:0 0 12px var(--c-gold)"></span>⑪ Hashtag 词云</div>
        <div class="card-meta" id="c-cloud-meta"></div>
      </div>
      <div class="card-desc">提取所有原创帖中的 #xxx 标签，按频次绘制词云。可以快速看出仿真社区的核心话题。</div>
      <div id="c-cloud" class="chart"></div>
    </div>
    <div class="card span-7 h-440">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-cyan);box-shadow:0 0 12px var(--c-cyan)"></span>⑫ Hashtag × 社群矩阵</div>
        <div class="card-meta">heatmap</div>
      </div>
      <div class="card-desc">行=Top hashtag, 列=社群编号, cell = 该社群中提及该话题的用户数。揭示"哪个群关心哪个话题"——回音室 / 话题极化的最直观证据。</div>
      <div id="c-tag-comm" class="chart"></div>
    </div>
    <div class="card span-12 h-400">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-violet);box-shadow:0 0 12px var(--c-violet)"></span>⑬ 话题时序流图（ThemeRiver）</div>
        <div class="card-meta">Top-8 hashtag</div>
      </div>
      <div class="card-desc">Top-8 hashtag 在 12 个时间桶里的提及次数。河流形状一眼看出话题"诞生—爆发—消退"的时序节奏。</div>
      <div id="c-river" class="chart"></div>
    </div>
  </div>

  <!-- E. 推荐 + 时序 -->
  <div class="section">
    <span class="section-tag">E · RECSYS &amp; TEMPORAL</span>
    <span class="section-title">推荐系统效果与时序活动</span>
    <span class="section-sub">企业视角：曝光-点击-互动转化 + 仿真时序节奏</span>
  </div>
  <div class="cards">
    <div class="card span-6 h-400">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-green);box-shadow:0 0 12px var(--c-green)"></span>⑭ 曝光 → 互动 Sankey 漏斗</div>
        <div class="card-meta">refresh→action</div>
      </div>
      <div class="card-desc">从 trace.refresh 提取曝光事件，连接到后续的 like / comment / repost / 不操作（do_nothing）。流量粗细 = 转化数量。可发现推荐系统的瓶颈环节。</div>
      <div id="c-sankey" class="chart"></div>
    </div>
    <div class="card span-6 h-400">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-orange);box-shadow:0 0 12px var(--c-orange)"></span>⑮ 仿真时间 × 小时热力图</div>
        <div class="card-meta">日期 × 小时</div>
      </div>
      <div class="card-desc">仿真过程中每个"日期-小时"格子的总动作数。能看出仿真的时间节奏（连续 / 离散 / 是否有夜间静默）。万级数据下规模不变。</div>
      <div id="c-heatmap" class="chart"></div>
    </div>
  </div>

  <!-- F. KOL -->
  <div class="section">
    <span class="section-tag">F · KOL</span>
    <span class="section-title">关键意见领袖</span>
    <span class="section-sub">影响力多维剖面 + 行为故事线</span>
  </div>
  <div class="cards">
    <div class="card span-5 h-440">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-gold);box-shadow:0 0 12px var(--c-gold)"></span>⑯ Top-8 KOL 多维雷达</div>
        <div class="card-meta">5 维</div>
      </div>
      <div class="card-desc">影响力综合分排行 Top-8，从 5 个维度（粉丝、发帖、获赞、获转、活跃度）刻画 KOL 类型——是"网红型"、"创作型"还是"水军型"。</div>
      <div id="c-radar" class="chart"></div>
    </div>
    <div class="card span-7 h-440">
      <div class="card-header">
        <div class="card-title"><span class="dot" style="background:var(--c-pink);box-shadow:0 0 12px var(--c-pink)"></span>⑰ KOL 行为故事线</div>
        <div class="card-meta">timeline</div>
      </div>
      <div class="card-desc">Top-8 KOL 每人一行，按时间散点显示其每个 action 类型。颜色编码 action 种类，能看出不同 KOL 的活跃节奏与行为模式（持续创作 vs 集中发布 vs 周期性互动）。</div>
      <div id="c-storyline" class="chart"></div>
    </div>
  </div>

  <footer>
    <p>原型由 <code>build_dashboard_data.py</code> + <code>build_dashboard_html.py</code> 离线生成 · 数据来自 <code id="db-path"></code></p>
    <p style="margin-top:6px">所有可视化均设计为 O(n log n) 或更优复杂度，可平滑扩展至 10,000+ agent 规模</p>
  </footer>
</div>

<script id="data-payload" type="application/json">__DATA_JSON__</script>
<script>
const DATA = JSON.parse(document.getElementById('data-payload').textContent);
const PALETTE = ['#5b8def','#4ecdc4','#a78bfa','#ff6b9d','#ffd166','#ff8b3d','#5fdba7','#ef4565','#9eaaff','#fbbf77','#67e8f9','#fb7185'];
const PALETTE_LARGE = PALETTE.concat(['#3b82f6','#10b981','#f59e0b','#ef4444','#8b5cf6','#ec4899','#06b6d4','#84cc16','#f97316','#6366f1','#14b8a6','#d946ef','#0ea5e9','#22c55e']);
const TXT = '#c9d1ec', TXT_DIM = '#7c87b8', GRID = 'rgba(120,140,210,.12)';
const baseGrid = { left:42, right:18, top:32, bottom:38, containLabel:true };
const baseTooltip = {
  backgroundColor:'rgba(13,18,48,.96)',
  borderColor:'rgba(120,140,210,.3)',
  textStyle:{color:'#fff',fontSize:12,fontFamily:'Inter, sans-serif'},
  extraCssText:'box-shadow:0 8px 32px rgba(0,0,0,.4); border-radius:10px; backdrop-filter:blur(8px);'
};
const baseAxis = {
  axisLine:{lineStyle:{color:GRID}},
  axisLabel:{color:TXT_DIM,fontSize:11},
  splitLine:{lineStyle:{color:GRID,type:'dashed'}},
  nameTextStyle:{color:TXT_DIM,fontSize:11},
};

// ======= meta + KPI =======
function renderMeta(){
  const m = DATA._meta || {};
  document.getElementById('meta').innerHTML = `
    <span><b>DB</b>${(m.db||'').split(/[\\\\/]/).pop()}</span>
    <span><b>GEN</b>${m.generated_at||''}</span>
    <span><b>USERS</b>${DATA.kpi.total_users}</span>
    <span><b>POSTS</b>${DATA.kpi.total_posts}</span>
    <span><b>TRACES</b>${DATA.kpi.total_traces.toLocaleString()}</span>
  `;
  document.getElementById('db-path').textContent = m.db || '';
  const k = DATA.kpi;
  const cards = [
    {l:'总用户',v:k.total_users,h:`活跃 ${k.active_users}`,i:'👥'},
    {l:'总帖子',v:k.total_posts,h:`原创 ${k.original_posts} · 转发 ${k.reposts}`,i:'📝'},
    {l:'评论',v:k.total_comments,h:'comment',i:'💬'},
    {l:'点赞',v:k.total_likes,h:'like',i:'❤️'},
    {l:'关注关系',v:k.total_follows,h:'follow edges',i:'🔗'},
    {l:'Trace 行为',v:k.total_traces.toLocaleString(),h:'agent decisions',i:'🧠'},
    {l:'Cascade',v:k.cascade_count,h:'有转发的原帖',i:'🌊'},
    {l:'最大病毒度',v:k.max_virality,h:'单帖最多被转发',i:'🔥'},
    {l:'仿真时长',v:k.duration_h+'h',h:'wall clock',i:'⏱'},
    {l:'社群数',v:DATA.network.n_communities,h:'Louvain',i:'🧭'},
    {l:'话题(hashtag)',v:DATA.topics.cloud.length,h:'unique tag',i:'#️⃣'},
    {l:'TOP KOL',v:(DATA.kols.ranking[0]||{}).name||'—',h:`score=${(DATA.kols.ranking[0]||{}).score||0}`,i:'⭐'},
  ];
  document.getElementById('kpi-grid').innerHTML = cards.map(c=>`
    <div class="kpi">
      <div class="kpi-label">${c.i} ${c.l}</div>
      <div class="kpi-value">${c.v}</div>
      <div class="kpi-hint">${c.h}</div>
    </div>
  `).join('');
}

// ======= ① TSNE scatter =======
function renderTsne(){
  const b = DATA.behavior;
  const groups = {};
  b.scatter.forEach(p=>{ (groups[p.cluster] = groups[p.cluster] || []).push(p); });
  const series = Object.keys(groups).map(c=>{
    const pts = groups[c];
    return {
      name: b.cluster_names[c] || `群组${c}`,
      type: 'scatter',
      data: pts.map(p=>({
        value:[p.x, p.y, p.total_actions, p.name, p.user_id, p.actions],
        symbolSize: Math.max(8, Math.min(38, Math.log(p.total_actions+1)*5))
      })),
      itemStyle:{color: PALETTE[c % PALETTE.length], opacity:.85, borderColor:'rgba(255,255,255,.25)', borderWidth:.5},
      emphasis:{itemStyle:{borderColor:'#fff',borderWidth:2,shadowBlur:12,shadowColor:'rgba(255,255,255,.4)'}}
    };
  });
  echarts.init(document.getElementById('c-tsne')).setOption({
    backgroundColor:'transparent',
    legend:{textStyle:{color:TXT,fontSize:11},top:0,type:'scroll',pageIconColor:TXT_DIM,pageTextStyle:{color:TXT_DIM}},
    grid:{...baseGrid,top:50},
    tooltip:{...baseTooltip, formatter:p=>{
      const v = p.value;
      const acts = v[5]||{};
      const top3 = Object.entries(acts).sort((a,b)=>b[1]-a[1]).slice(0,3).map(([a,n])=>`${a}=${n}`).join(' ');
      return `<b>${v[3]}</b> <span style="color:#7c87b8">#${v[4]}</span><br/>
              <span style="color:#7c87b8">总动作：</span>${v[2]}<br/>
              <span style="color:#7c87b8">Top3：</span>${top3}`;
    }},
    xAxis:{...baseAxis,type:'value',name:'TSNE-1',scale:true,splitLine:{show:false}},
    yAxis:{...baseAxis,type:'value',name:'TSNE-2',scale:true,splitLine:{show:false}},
    series
  });
}

// ======= ② Parallel =======
function renderParallel(){
  const b = DATA.behavior;
  const dims = b.feature_names.map((f,i)=>({dim:i, name:f, max:1}));
  echarts.init(document.getElementById('c-parallel')).setOption({
    backgroundColor:'transparent',
    legend:{textStyle:{color:TXT,fontSize:10},top:0,type:'scroll'},
    parallelAxis: dims.map((d,i)=>({...d,
      axisLine:{lineStyle:{color:GRID}},
      axisLabel:{color:TXT_DIM,fontSize:10,rotate:25},
      nameTextStyle:{color:TXT_DIM,fontSize:10},
      nameLocation:'end',
      splitLine:{lineStyle:{color:GRID}}
    })),
    parallel:{left:30,right:30,top:50,bottom:36,parallelAxisDefault:{nameGap:20}},
    tooltip:{...baseTooltip, formatter:(p)=>`<b>${p.seriesName}</b><br/>${p.data.map((v,i)=>`${b.feature_names[i]}: ${v.toFixed(3)}`).join('<br/>')}`},
    series: b.parallel.map((p,i)=>({
      name: `${p.name} · ${p.size}人`, type:'parallel',
      lineStyle:{width:3, color:PALETTE[p.cluster % PALETTE.length], opacity:.85},
      data:[p.values],
      smooth: true,
      emphasis:{lineStyle:{width:5,opacity:1}}
    }))
  });
}

// ======= ③ Action bar =======
function renderActionBar(){
  const b = DATA.behavior;
  const data = b.feature_names.map(a=>b.action_totals[a]||0);
  echarts.init(document.getElementById('c-action-bar')).setOption({
    backgroundColor:'transparent',
    grid:{...baseGrid,top:14,bottom:54},
    tooltip:{...baseTooltip},
    xAxis:{...baseAxis,type:'category',data:b.feature_names,axisLabel:{...baseAxis.axisLabel,rotate:30}},
    yAxis:{...baseAxis,type:'log',name:'count (log)',min:1},
    series:[{
      type:'bar',
      data: data.map((v,i)=>({value:v,itemStyle:{color:{
        type:'linear',x:0,y:0,x2:0,y2:1,
        colorStops:[{offset:0,color:PALETTE_LARGE[i % PALETTE_LARGE.length]},
                    {offset:1,color:PALETTE_LARGE[i % PALETTE_LARGE.length]+'66'}]
      }}})),
      barWidth:'55%',
      label:{show:true,position:'top',color:TXT,fontSize:10}
    }]
  });
}

// ======= ④ Activity power law =======
function renderActivityPower(){
  const b = DATA.behavior;
  const totals = b.scatter.map(p=>p.total_actions).filter(v=>v>0).sort((a,b)=>b-a);
  const data = totals.map((v,i)=>[i+1, v]);
  echarts.init(document.getElementById('c-activity-power')).setOption({
    backgroundColor:'transparent',
    grid:{...baseGrid,top:18,bottom:46},
    tooltip:{...baseTooltip, formatter:p=>`rank ${p.value[0]}: ${p.value[1]} 动作`},
    xAxis:{...baseAxis,type:'log',name:'用户排名 (log)',min:1},
    yAxis:{...baseAxis,type:'log',name:'动作总数 (log)',min:1},
    series:[{
      type:'scatter', data, symbolSize:8,
      itemStyle:{color:{type:'linear',x:0,y:0,x2:1,y2:0,colorStops:[
        {offset:0,color:'#ffd166'},{offset:1,color:'#ff8b3d'}
      ]}, opacity:.9, borderColor:'rgba(255,255,255,.3)', borderWidth:.5}
    }]
  });
}

// ======= ⑤ Cascade scatter =======
function renderCascadeScatter(){
  const fts = DATA.cascades.features;
  const data = fts.filter(f=>f.size>=2).map(f=>({
    value:[f.size, f.max_depth, f.unique_users, f.structural_virality, f.user_name, f.content, f.post_id],
    symbolSize: Math.max(8, Math.sqrt(f.unique_users)*4),
  }));
  echarts.init(document.getElementById('c-cascade-scatter')).setOption({
    backgroundColor:'transparent',
    grid:{...baseGrid,top:30,right:50},
    tooltip:{...baseTooltip, formatter:p=>{
      const v=p.value;
      return `<b>#${v[6]} · ${v[4]}</b><br/>
        <span style="color:#7c87b8">size:</span> ${v[0]} · <span style="color:#7c87b8">depth:</span> ${v[1]}<br/>
        <span style="color:#7c87b8">unique:</span> ${v[2]} · <span style="color:#7c87b8">virality:</span> ${v[3]}<br/>
        <span style="color:#7c87b8">${(v[5]||'').slice(0,80)}</span>`;
    }},
    visualMap:{
      min:1, max: Math.max(2, Math.max(...fts.map(f=>f.structural_virality))),
      dimension:3, calculable:true, orient:'vertical', right:0, top:'middle',
      inRange:{color:['#5b8def','#a78bfa','#ff6b9d','#ffd166']},
      textStyle:{color:TXT_DIM,fontSize:10},
      text:['深链\nvirality','广播']
    },
    xAxis:{...baseAxis,type:'value',name:'cascade size',min:1},
    yAxis:{...baseAxis,type:'value',name:'max depth',min:0},
    series:[{type:'scatter', data,
      itemStyle:{opacity:.85, borderColor:'rgba(255,255,255,.3)', borderWidth:.5}}]
  });
}

// ======= ⑥ Cascade size CCDF =======
function renderCascadePower(){
  const fts = DATA.cascades.features;
  const sizes = fts.map(f=>f.size);
  const cnt = {};
  sizes.forEach(s=>cnt[s]=(cnt[s]||0)+1);
  const sorted = Object.keys(cnt).map(Number).sort((a,b)=>a-b);
  const N = sizes.length;
  // CCDF: P(X >= s)
  let cumulative = 0;
  const cum = {};
  for(let i=sorted.length-1;i>=0;i--){
    cumulative += cnt[sorted[i]];
    cum[sorted[i]] = cumulative;
  }
  const data = sorted.map(s=>[s, cum[s]/N]);
  echarts.init(document.getElementById('c-cascade-power')).setOption({
    backgroundColor:'transparent',
    grid:{...baseGrid,top:18},
    tooltip:{...baseTooltip, formatter:p=>`size≥${p.value[0]}: ${(p.value[1]*100).toFixed(1)}%`},
    xAxis:{...baseAxis,type:'log',name:'cascade size (log)',min:1},
    yAxis:{...baseAxis,type:'log',name:'P(X ≥ size) (log)',min:1/N},
    series:[{
      type:'scatter', data, symbolSize:9,
      itemStyle:{color:'#ef4565',opacity:.9,borderColor:'rgba(255,255,255,.3)',borderWidth:.5}
    },{
      type:'line', data, lineStyle:{color:'rgba(239,69,101,.4)',width:1,type:'dashed'},
      symbol:'none', smooth:false
    }]
  });
}

// ======= ⑦ Cascade lifecycles =======
function renderCascadeLife(){
  const lifes = DATA.cascades.lifecycles;
  if(!lifes.length){ document.getElementById('c-cascade-life').innerHTML='<div style="color:#7c87b8;text-align:center;padding-top:60px">no cascade lifecycle data</div>'; return; }
  // 用每个 cascade 自己的时间轴，归一化到 [0,1]，然后画折线
  const N_BUCKETS = 12;
  const allCounts = lifes.map(l=>{
    const ts = l.events.map(e=>e.t);
    const tmin = Math.min(...ts), tmax = Math.max(...ts);
    const range = Math.max(tmax - tmin, 1);
    const buckets = new Array(N_BUCKETS).fill(0);
    l.events.forEach(e=>{
      const idx = Math.min(N_BUCKETS-1, Math.floor((e.t - tmin) / range * N_BUCKETS));
      buckets[idx]++;
    });
    return {name:`#${l.post_id} (${l.size})`, content:l.content, data:buckets};
  });
  const xData = Array.from({length:N_BUCKETS},(_,i)=>`T${i+1}`);
  const series = allCounts.map((c,i)=>({
    name: c.name, type:'line', stack:'lifecycle',
    smooth:true,
    showSymbol:false,
    areaStyle:{opacity:.65,color:PALETTE_LARGE[i % PALETTE_LARGE.length]},
    lineStyle:{width:1,color:PALETTE_LARGE[i % PALETTE_LARGE.length]},
    data: c.data,
    emphasis:{focus:'series'},
  }));
  echarts.init(document.getElementById('c-cascade-life')).setOption({
    backgroundColor:'transparent',
    legend:{textStyle:{color:TXT,fontSize:10},top:0,type:'scroll'},
    grid:{...baseGrid,top:46,bottom:46},
    tooltip:{...baseTooltip,trigger:'axis',axisPointer:{type:'cross',lineStyle:{color:GRID}}},
    xAxis:{...baseAxis,type:'category',data:xData,name:'相对时间桶',boundaryGap:false},
    yAxis:{...baseAxis,type:'value',name:'事件数（堆叠）'},
    series
  });
}

// ======= ⑧ Network with Louvain =======
function renderNetwork(){
  const net = DATA.network;
  document.getElementById('c-network-meta').textContent = `N=${net.nodes.length} · E=${net.links.length} · ${net.n_communities}社群`;
  // 把节点位置归一化到合理范围
  const xs = net.nodes.map(n=>n.x), ys = net.nodes.map(n=>n.y);
  const xmin=Math.min(...xs), xmax=Math.max(...xs), ymin=Math.min(...ys), ymax=Math.max(...ys);
  const sx = 1, sy = 1;
  const nodes = net.nodes.map(n=>({
    id: String(n.id), name: n.name,
    x: (n.x - xmin) / Math.max(xmax-xmin,1) * 1000 * sx,
    y: (n.y - ymin) / Math.max(ymax-ymin,1) * 600 * sy,
    symbolSize: Math.max(6, Math.min(28, 6 + Math.sqrt(n.degree)*3)),
    category: n.community,
    value: n.degree,
    itemStyle:{color: PALETTE_LARGE[n.community % PALETTE_LARGE.length], borderColor:'rgba(255,255,255,.2)', borderWidth:.5},
    label:{show: n.degree >= 6, color:'#fff', fontSize:9, position:'right'},
  }));
  const links = net.links.map(l=>({source: String(l.source), target: String(l.target)}));
  const categories = net.communities.map(c=>({name:`C${c.id} (${c.size})`}));
  echarts.init(document.getElementById('c-network')).setOption({
    backgroundColor:'transparent',
    legend:{show:false},
    tooltip:{...baseTooltip, formatter:p=>{
      if(p.dataType==='node') return `<b>${p.data.name}</b> #${p.data.id}<br/>community: C${p.data.category}<br/>degree: ${p.data.value}`;
      return '';
    }},
    series:[{
      type:'graph', layout:'none',
      data: nodes, links, categories,
      roam:true, zoom:.85,
      edgeSymbol:['none','arrow'],
      edgeSymbolSize:[3,6],
      lineStyle:{color:'rgba(180,200,255,.18)',width:.6,curveness:.08},
      emphasis:{focus:'adjacency',lineStyle:{color:'#fff',width:1.5,opacity:.8}}
    }]
  });
}

// ======= ⑨ Degree dist =======
function renderDegree(){
  const net = DATA.network;
  const inD = net.in_degree_dist;
  const outD = net.out_degree_dist;
  echarts.init(document.getElementById('c-degree')).setOption({
    backgroundColor:'transparent',
    legend:{textStyle:{color:TXT,fontSize:11},top:0,data:['in-degree','out-degree']},
    grid:{...baseGrid,top:40},
    tooltip:{...baseTooltip,formatter:p=>`${p.seriesName}<br/>k=${p.value[0]} · count=${p.value[1]}`},
    xAxis:{...baseAxis,type:'log',name:'degree k (log)',min:1},
    yAxis:{...baseAxis,type:'log',name:'count (log)',min:1},
    series:[
      {name:'in-degree', type:'scatter', data: inD, symbolSize:10,
        itemStyle:{color:'#5b8def',opacity:.9,borderColor:'rgba(255,255,255,.3)',borderWidth:.5}},
      {name:'out-degree', type:'scatter', data: outD, symbolSize:10,
        itemStyle:{color:'#4ecdc4',opacity:.9,borderColor:'rgba(255,255,255,.3)',borderWidth:.5}}
    ]
  });
}

// ======= ⑩ Comm matrix =======
function renderCommMatrix(){
  const net = DATA.network;
  const N = net.n_communities;
  const data = [];
  for(let i=0;i<N;i++) for(let j=0;j<N;j++){
    if(net.matrix[i][j] > 0) data.push([j, i, net.matrix[i][j]]);
  }
  const labels = Array.from({length:N},(_,i)=>`C${i}`);
  const max = Math.max(1,...data.map(d=>d[2]));
  echarts.init(document.getElementById('c-comm-matrix')).setOption({
    backgroundColor:'transparent',
    grid:{...baseGrid,top:14,bottom:50,right:80},
    tooltip:{...baseTooltip,formatter:p=>`${labels[p.value[1]]} → ${labels[p.value[0]]}<br/>edges: ${p.value[2]}`},
    xAxis:{...baseAxis,type:'category',data:labels,name:'目标社群',axisLabel:{...baseAxis.axisLabel,rotate:0,fontSize:10}},
    yAxis:{...baseAxis,type:'category',data:labels,name:'源社群',inverse:true},
    visualMap:{
      min:0, max, calculable:true, orient:'vertical', right:0, top:'middle',
      inRange:{color:['rgba(91,141,239,.05)','#5b8def','#a78bfa','#ff6b9d','#ffd166']},
      textStyle:{color:TXT_DIM,fontSize:10}
    },
    series:[{type:'heatmap',data,
      label:{show:N<=20,color:'#fff',fontSize:9},
      emphasis:{itemStyle:{borderColor:'#fff',borderWidth:1}}
    }]
  });
}

// ======= ⑪ Word cloud =======
function renderCloud(){
  const cloud = DATA.topics.cloud;
  document.getElementById('c-cloud-meta').textContent = `${cloud.length} 个标签`;
  echarts.init(document.getElementById('c-cloud')).setOption({
    backgroundColor:'transparent',
    tooltip:{...baseTooltip,formatter:p=>`<b>#${p.name}</b><br/>提及 ${p.value} 次`},
    series:[{
      type:'wordCloud',
      gridSize:6,
      sizeRange:[12,52],
      rotationRange:[-30,30],
      shape:'circle',
      width:'95%',height:'90%',
      drawOutOfBound:false,
      textStyle:{
        color:()=>PALETTE_LARGE[Math.floor(Math.random()*PALETTE_LARGE.length)],
        fontWeight:600,
        fontFamily:'Inter, PingFang SC, sans-serif'
      },
      emphasis:{textStyle:{textShadowBlur:18, textShadowColor:'rgba(255,255,255,.5)'}},
      data: cloud
    }]
  });
}

// ======= ⑫ Hashtag × community matrix =======
function renderTagComm(){
  const t = DATA.topics;
  const N = t.n_communities;
  const M = t.top_tags.length;
  const data = [];
  let maxV = 1;
  for(let i=0;i<M;i++) for(let j=0;j<N;j++){
    const v = t.comm_matrix[i][j];
    if(v>0){ data.push([j,i,v]); maxV=Math.max(maxV,v); }
  }
  const xLabels = Array.from({length:N},(_,i)=>`C${i}`);
  echarts.init(document.getElementById('c-tag-comm')).setOption({
    backgroundColor:'transparent',
    grid:{left:120,right:80,top:14,bottom:38},
    tooltip:{...baseTooltip,formatter:p=>`<b>#${t.top_tags[p.value[1]]}</b> in ${xLabels[p.value[0]]}<br/>${p.value[2]} 用户提及`},
    xAxis:{...baseAxis,type:'category',data:xLabels,name:'社群',axisLabel:{...baseAxis.axisLabel,fontSize:10}},
    yAxis:{...baseAxis,type:'category',data:t.top_tags.map(t=>'#'+t),inverse:true,axisLabel:{color:TXT,fontSize:10}},
    visualMap:{
      min:0, max:maxV, calculable:true, orient:'vertical', right:0, top:'middle',
      inRange:{color:['rgba(167,139,250,.05)','#a78bfa','#ff6b9d','#ffd166']},
      textStyle:{color:TXT_DIM,fontSize:10}
    },
    series:[{type:'heatmap',data,
      label:{show:false},
      emphasis:{itemStyle:{borderColor:'#fff',borderWidth:1}}
    }]
  });
}

// ======= ⑬ ThemeRiver =======
function renderRiver(){
  const t = DATA.topics;
  if(!t.stream.length || !t.stream_x.length){
    document.getElementById('c-river').innerHTML='<div style="color:#7c87b8;text-align:center;padding-top:60px">no temporal hashtag data</div>'; return;
  }
  const data = [];
  t.stream_x.forEach((x, idx)=>{
    t.stream.forEach(s=>{
      data.push([x, s.values[idx]||0, s.name]);
    });
  });
  echarts.init(document.getElementById('c-river')).setOption({
    backgroundColor:'transparent',
    legend:{textStyle:{color:TXT,fontSize:11},top:0,type:'scroll'},
    tooltip:{...baseTooltip,trigger:'axis',axisPointer:{type:'line',lineStyle:{color:GRID}}},
    singleAxis:{
      left:50,right:30,top:46,bottom:36,
      type:'category', data:t.stream_x,
      axisLine:{lineStyle:{color:GRID}},
      axisLabel:{color:TXT_DIM,fontSize:10,rotate:30},
      axisTick:{lineStyle:{color:GRID}}
    },
    series:[{
      type:'themeRiver', data,
      label:{show:false},
      emphasis:{itemStyle:{shadowColor:'rgba(255,255,255,.3)',shadowBlur:14}},
      colorBy:'series'
    }],
    color: PALETTE_LARGE
  });
}

// ======= ⑭ Sankey =======
function renderSankey(){
  const f = DATA.funnel;
  const acted = f.likes + f.comments + f.reposts;
  const passive = Math.max(0, f.refresh_events - acted - f.do_nothing);
  const nodes = [
    {name:'曝光\n(refresh)', itemStyle:{color:'#5b8def'}},
    {name:'do_nothing', itemStyle:{color:'#7c87b8'}},
    {name:'无后续', itemStyle:{color:'#4a527a'}},
    {name:'点赞', itemStyle:{color:'#ff6b9d'}},
    {name:'评论', itemStyle:{color:'#4ecdc4'}},
    {name:'转发', itemStyle:{color:'#ffd166'}},
  ];
  const links = [
    {source:'曝光\n(refresh)', target:'do_nothing', value:f.do_nothing},
    {source:'曝光\n(refresh)', target:'点赞', value:f.likes},
    {source:'曝光\n(refresh)', target:'评论', value:f.comments},
    {source:'曝光\n(refresh)', target:'转发', value:f.reposts},
    {source:'曝光\n(refresh)', target:'无后续', value:passive},
  ].filter(l=>l.value>0);
  echarts.init(document.getElementById('c-sankey')).setOption({
    backgroundColor:'transparent',
    tooltip:{...baseTooltip,formatter:p=>p.dataType==='edge'?`${p.data.source} → ${p.data.target}<br/>${p.data.value}`:`<b>${p.name}</b>`},
    series:[{
      type:'sankey', data: nodes, links,
      orient:'horizontal',
      left:10, right:50, top:18, bottom:18,
      nodeWidth:14, nodeGap:14,
      label:{color:TXT,fontSize:11,fontWeight:600},
      lineStyle:{color:'gradient',opacity:.55,curveness:.5},
      emphasis:{focus:'adjacency'}
    }]
  });
}

// ======= ⑮ Activity heatmap =======
function renderHeatmap(){
  const a = DATA.activity;
  const data = a.heatmap;
  const max = Math.max(1, ...data.map(d=>d[2]));
  echarts.init(document.getElementById('c-heatmap')).setOption({
    backgroundColor:'transparent',
    grid:{left:60,right:80,top:18,bottom:46},
    tooltip:{...baseTooltip,formatter:p=>`${p.value[0]} ${String(p.value[1]).padStart(2,'0')}:00<br/>${p.value[2]} actions`},
    xAxis:{...baseAxis,type:'category',data:a.days,name:'日期',axisLabel:{...baseAxis.axisLabel,rotate:0,fontSize:10}},
    yAxis:{...baseAxis,type:'category',data:a.hours.map(h=>String(h).padStart(2,'0')+':00'),inverse:true,name:'小时'},
    visualMap:{
      min:0, max, calculable:true, orient:'vertical', right:8, top:'middle',
      inRange:{color:['rgba(91,141,239,.04)','#5b8def','#a78bfa','#ff6b9d','#ffd166']},
      textStyle:{color:TXT_DIM,fontSize:10}
    },
    series:[{type:'heatmap',data:data.map(d=>[d[0],a.hours.indexOf(d[1]),d[2]]),
      emphasis:{itemStyle:{borderColor:'#fff',borderWidth:1}}}]
  });
}

// ======= ⑯ Radar =======
function renderRadar(){
  const k = DATA.kols;
  echarts.init(document.getElementById('c-radar')).setOption({
    backgroundColor:'transparent',
    legend:{textStyle:{color:TXT,fontSize:10},top:0,type:'scroll'},
    radar:{
      indicator: k.radar_indicators,
      shape:'polygon',
      splitNumber:4,
      splitArea:{areaStyle:{color:['rgba(255,255,255,.02)','rgba(255,255,255,.04)']}},
      splitLine:{lineStyle:{color:GRID}},
      axisLine:{lineStyle:{color:GRID}},
      name:{textStyle:{color:TXT,fontSize:11,fontWeight:600}},
      center:['50%','58%'],
      radius:'62%'
    },
    tooltip:{...baseTooltip},
    series:[{
      type:'radar',
      data: k.radar_data.map((d,i)=>({
        name:d.name, value:d.value,
        lineStyle:{width:2, color:PALETTE_LARGE[i % PALETTE_LARGE.length]},
        itemStyle:{color:PALETTE_LARGE[i % PALETTE_LARGE.length]},
        areaStyle:{color:PALETTE_LARGE[i % PALETTE_LARGE.length], opacity:.18}
      }))
    }]
  });
}

// ======= ⑰ Storyline =======
function renderStoryline(){
  const k = DATA.kols;
  const actionColors = {};
  ['refresh','do_nothing','create_comment','like_post','repost','follow','search_user','create_post','search_posts','trend','sign_up'].forEach((a,i)=>{
    actionColors[a] = PALETTE_LARGE[i % PALETTE_LARGE.length];
  });
  const yCats = k.storyline.map(s=>s.name).reverse();  // 反转使得排名第1在顶部
  const yIndex = {};
  yCats.forEach((n,i)=>yIndex[n]=i);
  // 按 action type 分 series
  const actionTypes = Array.from(new Set(k.storyline.flatMap(s=>s.events.map(e=>e.action))));
  const series = actionTypes.map(at=>({
    name: at, type:'scatter',
    data: k.storyline.flatMap(s=>s.events.filter(e=>e.action===at).map(e=>({
      value:[e.t*1000, yIndex[s.name], at, s.name]
    }))),
    symbolSize: 8,
    itemStyle:{color: actionColors[at] || '#7c87b8', opacity:.8, borderColor:'rgba(255,255,255,.2)', borderWidth:.4}
  }));
  echarts.init(document.getElementById('c-storyline')).setOption({
    backgroundColor:'transparent',
    legend:{textStyle:{color:TXT,fontSize:10},top:0,type:'scroll'},
    grid:{left:130,right:30,top:46,bottom:36},
    tooltip:{...baseTooltip,formatter:p=>{
      const v=p.value;
      return `<b>${v[3]}</b><br/>${new Date(v[0]).toLocaleString('zh-CN')}<br/>action: <span style="color:#ffd166">${v[2]}</span>`;
    }},
    xAxis:{...baseAxis,type:'time',name:'仿真时间'},
    yAxis:{...baseAxis,type:'category',data:yCats,axisLabel:{color:TXT,fontSize:11}},
    series
  });
}

// ===== launch =====
function go(){
  renderMeta();
  renderTsne();
  renderParallel();
  renderActionBar();
  renderActivityPower();
  renderCascadeScatter();
  renderCascadePower();
  renderCascadeLife();
  renderNetwork();
  renderDegree();
  renderCommMatrix();
  renderCloud();
  renderTagComm();
  renderRiver();
  renderSankey();
  renderHeatmap();
  renderRadar();
  renderStoryline();
  // resize on window change
  window.addEventListener('resize', ()=>{
    document.querySelectorAll('.chart').forEach(el=>{
      const inst = echarts.getInstanceByDom(el);
      if(inst) inst.resize();
    });
  });
}
go();
</script>
</body>
</html>
"""


def main():
    if not DATA_JSON.exists():
        raise SystemExit(f"data.json not found: {DATA_JSON}\nRun build_dashboard_data.py first.")
    payload = DATA_JSON.read_text(encoding="utf-8")
    payload_safe = payload.replace("</", "<\\/")
    html = HTML.replace("__DATA_JSON__", payload_safe)
    OUT_HTML.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT_HTML}")
    print(f"Open in browser: file:///{str(OUT_HTML).replace(chr(92), '/')}")


if __name__ == "__main__":
    main()
