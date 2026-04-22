import sqlite3
import pandas as pd
import textwrap
import math
import json
from datetime import datetime
from pyecharts import options as opts
from pyecharts.charts import Graph
from pyecharts.globals import ThemeType

# ==========================================
# 1. 连数据库取数
# ==========================================
db_path = './weibo_test/weibo_sim_qwen_huawei.db' 
conn = sqlite3.connect(db_path)

# 1.1 查用户表
df_users = pd.read_sql_query("SELECT user_id, name FROM user", conn)
user_map = df_users.set_index('user_id')['name'].to_dict()

# 1.2 查帖子 (Post)
# 新增: created_at, num_likes, num_shares, num_dislikes
query_posts = """
SELECT 
    post_id, 
    original_post_id, 
    user_id, 
    content,
    quote_content, 
    created_at,
    num_likes,
    num_shares,
    num_dislikes,
    'post' as type
FROM post
"""
df_posts = pd.read_sql_query(query_posts, conn)

# 1.3 查评论 (Comment)
query_comments = """
SELECT 
    comment_id, 
    post_id as parent_id, 
    user_id, 
    content,
    created_at,
    num_likes,
    num_dislikes,
    0 as num_shares,  -- 评论没有转发数，补0
    'comment' as type
FROM comment
"""
df_comments = pd.read_sql_query(query_comments, conn)

conn.close()

# ==========================================
# 2. 数据清洗 & 节点逻辑
# ==========================================

# 2.1 区分是 原创(Root) 还是 转发(Repost)
def determine_post_type(val):
    if pd.isna(val) or val == '' or val == 0 or str(val).lower() == 'null':
        return 'root'
    return 'repost'

df_posts['post_type'] = df_posts['original_post_id'].apply(determine_post_type)

# 2.2 决定显示啥内容
def get_display_content(row):
    if row['post_type'] == 'root':
        return row['content']
    else:
        return row['quote_content'] if pd.notnull(row['quote_content']) else "[No Quote Text]"

df_posts['final_content'] = df_posts.apply(get_display_content, axis=1)

# 2.3 拼凑节点数据 DataFrame
df_posts_clean = pd.DataFrame()
df_posts_clean['node_id'] = 'P_' + df_posts['post_id'].astype(str)
df_posts_clean['parent_node_id'] = df_posts.apply(
    lambda x: ('P_' + str(int(x['original_post_id']))) if x['post_type'] == 'repost' else None, 
    axis=1
)
df_posts_clean['user_id'] = df_posts['user_id']
df_posts_clean['content'] = df_posts['final_content']
df_posts_clean['type'] = df_posts['post_type']
for col in ['created_at', 'num_likes', 'num_shares', 'num_dislikes']:
    df_posts_clean[col] = df_posts[col]

# 处理评论数据
df_comments_clean = pd.DataFrame()
df_comments_clean['node_id'] = 'C_' + df_comments['comment_id'].astype(str)
df_comments_clean['parent_node_id'] = 'P_' + df_comments['parent_id'].astype(str)
df_comments_clean['user_id'] = df_comments['user_id']
df_comments_clean['content'] = df_comments['content']
df_comments_clean['type'] = 'comment'
for col in ['created_at', 'num_likes', 'num_shares', 'num_dislikes']:
    df_comments_clean[col] = df_comments[col]

# 合并
df_all = pd.concat([df_posts_clean, df_comments_clean], ignore_index=True)
df_all['user_name'] = df_all['user_id'].map(user_map).fillna('Unknown')
df_all['content'] = df_all['content'].fillna('')
# 填充数值空值为0
df_all[['num_likes', 'num_shares', 'num_dislikes']] = df_all[['num_likes', 'num_shares', 'num_dislikes']].fillna(0)

# ==========================================
# 3. 转成 PyECharts 节点与边
# ==========================================

nodes = []
links = []
valid_node_ids = set(df_all['node_id'])

# 计算结构热度 (被作为父节点的次数)
structure_degree = df_all['parent_node_id'].value_counts().to_dict()

# 高级配色方案 (Material / Modern)
color_map = {
    'root':    "#FFD700", # Gold for Root
    'repost':  "#FF6B6B", # Coral Red for Repost
    'comment': "#4ECDC4"  # Medium Turquoise for Comment
}

categories = [
    {"name": "Root Post", "itemStyle": {"color": color_map['root']}},
    {"name": "Repost",    "itemStyle": {"color": color_map['repost']}},
    {"name": "Comment",   "itemStyle": {"color": color_map['comment']}}
]

MAX_SYMBOL_SIZE = 50  # 减小最大节点尺寸，避免重叠
MIN_SYMBOL_SIZE = 6

for _, row in df_all.iterrows():
    nid = row['node_id']
    ntype = row['type']
    
    # --- 综合影响力大小 (Influence Size) ---
    # 结合 结构热度(repies) + 内容热度(likes/shares)
    # Log scale to handle long-tail distribution
    s_degree = structure_degree.get(nid, 0)
    interaction_score = row['num_likes'] + (row['num_shares'] * 2) # 转发权重更高
    
    # 基础分 + 互动分(log) + 结构分(linear)，整体缩小
    size_score = 4 + math.log(interaction_score + 1) * 3 + (s_degree * 1.5)
    
    # 如果是 Root，给个适度加成（不要太大）
    if ntype == 'root':
        size_score += 8
        
    symbol_size = min(max(size_score, MIN_SYMBOL_SIZE), MAX_SYMBOL_SIZE)

    # --- 内容换行处理 ---
    raw_content = str(row['content'])
    wrapped_content_list = textwrap.wrap(raw_content, width=40) 
    wrapped_html = "<br/>".join(wrapped_content_list)
    
    # --- Rich Tooltip ---
    # 显示时间、统计数据
    stats_line = (
        f"👍 {int(row['num_likes'])} | "
        f"🔁 {int(row['num_shares'])} | "
        f"👎 {int(row['num_dislikes'])} | "
        f"💬 {s_degree}"
    )
    
    tooltip_fmt = (
        f"<div style='font-family: sans-serif; padding:10px; font-size:12px; line-height:1.5; color:#eee;'>"
        f"<div style='margin-bottom:5px;'>"
        f"<b style='font-size:14px; color:{color_map.get(ntype, '#fff')}'>{row['user_name']}</b> "
        f"<span style='background:#555; padding:2px 4px; border-radius:3px; font-size:10px;'>{ntype.upper()}</span>"
        f"</div>"
        f"<div style='color:#bbb; font-size:11px; margin-bottom:8px;'>{row['created_at']}</div>"
        f"<div style='border-left: 3px solid {color_map.get(ntype, '#fff')}; padding-left:8px; margin-bottom:8px;'>"
        f"{wrapped_html}"
        f"</div>"
        f"<div style='background:#333; padding:5px; border-radius:4px; font-weight:bold; color:#ffcc00;'>"
        f"{stats_line}"
        f"</div>"
        f"</div>"
    )

    # --- 标签显示 ---
    # 阈值控制：只有比较大的节点才显示 Label，避免太乱
    show_label = symbol_size > 25
    short_text = raw_content[:10] + '...' if len(raw_content) > 10 else raw_content
    
    cat_idx = 0 if ntype == 'root' else (1 if ntype == 'repost' else 2)

    nodes.append({
        "name": nid,
        "symbolSize": symbol_size,
        "category": cat_idx,
        "value": int(interaction_score), # Value 这里存互动分，鼠标放上去原生 tooltip 也会显示这个
        "label": {
            "show": show_label,
            "formatter": row['user_name'], # 标签显示人名可能比内容更有意义，或者 short_text
            "color": "#fff",       
            "textBorderColor": "#000",
            "textBorderWidth": 2,
            "fontSize": 10 + (symbol_size / 10), # 字体随节点大小微调
            "position": "right"
        },
        "tooltip": {"formatter": tooltip_fmt}
    })

    if row['parent_node_id'] and row['parent_node_id'] in valid_node_ids:
        links.append({"source": row['parent_node_id'], "target": nid})

# ==========================================
# 4. 处理时间戳并导出动态数据
# ==========================================

def parse_timestamp(ts_str):
    """将数据库时间戳转换为 Unix 时间戳（秒）"""
    if pd.isna(ts_str) or ts_str == '':
        return None
    try:
        # 支持多种时间格式
        if '.' in str(ts_str):
            # 带微秒: 2026-01-13 17:04:57.618708
            dt = datetime.strptime(str(ts_str).split('.')[0], '%Y-%m-%d %H:%M:%S')
        else:
            dt = datetime.strptime(str(ts_str), '%Y-%m-%d %H:%M:%S')
        return int(dt.timestamp())
    except Exception as e:
        print(f"Warning: Could not parse timestamp '{ts_str}': {e}")
        return None

# 为所有节点添加时间戳
for node in nodes:
    node_id = node['name']
    # 从 df_all 中找到对应的时间
    node_row = df_all[df_all['node_id'] == node_id].iloc[0]
    timestamp = parse_timestamp(node_row['created_at'])
    node['timestamp'] = timestamp
    node['created_at_str'] = str(node_row['created_at'])

# 计算时间范围（过滤掉None值）
valid_timestamps = [n['timestamp'] for n in nodes if n['timestamp'] is not None]
if valid_timestamps:
    min_time = min(valid_timestamps)
    max_time = max(valid_timestamps)
else:
    min_time = max_time = 0

# 为边添加时间戳（边在源节点和目标节点都存在时才显示）
for link in links:
    source_node = next((n for n in nodes if n['name'] == link['source']), None)
    target_node = next((n for n in nodes if n['name'] == link['target']), None)
    if source_node and target_node:
        link['source_time'] = source_node.get('timestamp', 0)
        link['target_time'] = target_node.get('timestamp', 0)

# 准备动态可视化数据
dynamic_data = {
    'nodes': nodes,
    'links': links,
    'categories': categories,
    'timeRange': {
        'min': min_time,
        'max': max_time,
        'minStr': datetime.fromtimestamp(min_time).strftime('%Y-%m-%d %H:%M:%S') if min_time else '',
        'maxStr': datetime.fromtimestamp(max_time).strftime('%Y-%m-%d %H:%M:%S') if max_time else ''
    },
    'colorMap': color_map
}

# 生成内嵌数据的动态HTML文件
dynamic_html_template = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>讨论传播时间线 - Discussion Propagation Timeline</title>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.4.3/dist/echarts.min.js"></script>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0a0a0a 0%, #1a1a2e 100%);
            color: #eee;
            overflow: hidden;
        }

        .container {
            width: 100vw;
            height: 100vh;
            display: flex;
            flex-direction: column;
        }

        /* Header */
        .header {
            background: rgba(20, 20, 30, 0.95);
            padding: 15px 30px;
            border-bottom: 2px solid #333;
            backdrop-filter: blur(10px);
        }

        .header h1 {
            font-size: 24px;
            font-weight: bold;
            color: #FFD700;
            margin-bottom: 3px;
            text-shadow: 0 0 10px rgba(255, 215, 0, 0.3);
        }

        .header p {
            font-size: 12px;
            color: #aaa;
        }

        /* Control Panel */
        .control-panel {
            background: rgba(30, 30, 40, 0.95);
            padding: 15px 30px;
            border-bottom: 1px solid #444;
            backdrop-filter: blur(10px);
        }

        .controls {
            display: flex;
            align-items: center;
            gap: 15px;
            flex-wrap: wrap;
        }

        .controls-row {
            display: flex;
            align-items: center;
            gap: 15px;
            flex-wrap: wrap;
            width: 100%;
            margin-bottom: 10px;
        }

        .controls-row:last-child {
            margin-bottom: 0;
        }

        .btn-group {
            display: flex;
            gap: 8px;
        }

        button {
            padding: 8px 16px;
            border: none;
            border-radius: 6px;
            font-size: 13px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            box-shadow: 0 4px 15px rgba(102, 126, 234, 0.3);
        }

        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 6px 20px rgba(102, 126, 234, 0.5);
        }

        button:active {
            transform: translateY(0);
        }

        button.play {
            background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%);
        }

        button.pause {
            background: linear-gradient(135deg, #4facfe 0%, #00f2fe 100%);
        }

        button.active {
            background: linear-gradient(135deg, #11998e 0%, #38ef7d 100%);
        }

        button:disabled {
            opacity: 0.5;
            cursor: not-allowed;
        }

        .speed-control, .mode-control {
            display: flex;
            align-items: center;
            gap: 8px;
        }

        .speed-control label, .mode-control label {
            font-size: 13px;
            color: #ccc;
        }

        .speed-control select, .mode-control select {
            padding: 6px 10px;
            border-radius: 6px;
            border: 1px solid #555;
            background: rgba(40, 40, 50, 0.9);
            color: #fff;
            font-size: 13px;
            cursor: pointer;
            transition: all 0.3s ease;
        }

        .speed-control select:hover, .mode-control select:hover {
            border-color: #777;
        }

        /* Timeline */
        .timeline-container {
            flex: 1;
            display: flex;
            align-items: center;
            gap: 12px;
        }

        .time-display {
            min-width: 180px;
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

        .slider-container {
            flex: 1;
            position: relative;
        }

        input[type="range"] {
            width: 100%;
            height: 8px;
            border-radius: 4px;
            background: rgba(255, 255, 255, 0.1);
            outline: none;
            -webkit-appearance: none;
        }

        input[type="range"]::-webkit-slider-thumb {
            -webkit-appearance: none;
            appearance: none;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: linear-gradient(135deg, #FFD700, #FFA500);
            cursor: pointer;
            box-shadow: 0 0 10px rgba(255, 215, 0, 0.5);
            transition: all 0.3s ease;
        }

        input[type="range"]::-webkit-slider-thumb:hover {
            transform: scale(1.2);
            box-shadow: 0 0 15px rgba(255, 215, 0, 0.8);
        }

        input[type="range"]::-moz-range-thumb {
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: linear-gradient(135deg, #FFD700, #FFA500);
            cursor: pointer;
            border: none;
            box-shadow: 0 0 10px rgba(255, 215, 0, 0.5);
        }

        /* Time Slice Controls - 简化版 */
        .window-control {
            display: none;
            align-items: center;
            gap: 8px;
        }

        .window-control.active {
            display: flex;
        }

        .window-control label {
            font-size: 13px;
            color: #ccc;
        }

        .window-control select {
            padding: 6px 10px;
            border-radius: 6px;
            border: 1px solid #555;
            background: rgba(40, 40, 50, 0.9);
            color: #fff;
            font-size: 13px;
            cursor: pointer;
        }

        /* Stats Panel */
        .stats-panel {
            display: flex;
            gap: 20px;
            padding: 12px 30px;
            background: rgba(30, 30, 40, 0.9);
            border-top: 1px solid #444;
        }

        .stat-item {
            display: flex;
            flex-direction: column;
            gap: 3px;
        }

        .stat-item .label {
            font-size: 11px;
            color: #999;
            text-transform: uppercase;
            letter-spacing: 1px;
        }

        .stat-item .value {
            font-size: 20px;
            font-weight: bold;
            color: #FFD700;
        }

        .stat-item.roots .value { color: #FFD700; }
        .stat-item.reposts .value { color: #FF6B6B; }
        .stat-item.comments .value { color: #4ECDC4; }
        .stat-item.total .value { color: #fff; }

        /* Graph Container */
        #graph-container {
            flex: 1;
            width: 100%;
            background: rgba(10, 10, 15, 0.5);
        }

        /* Progress Indicator */
        .progress-bar {
            position: absolute;
            bottom: 0;
            left: 0;
            height: 4px;
            background: linear-gradient(90deg, #FFD700, #FF6B6B, #4ECDC4);
            border-radius: 2px;
            transition: width 0.3s ease;
        }

        /* Dual Range Slider for Time Slice */
        .dual-range-container {
            position: relative;
            flex: 1;
            height: 30px;
            min-width: 200px;
        }

        .dual-range-container input[type="range"] {
            position: absolute;
            width: 100%;
            height: 8px;
            top: 50%;
            transform: translateY(-50%);
            pointer-events: none;
            background: transparent;
        }

        .dual-range-container input[type="range"]::-webkit-slider-thumb {
            pointer-events: auto;
        }

        .dual-range-container input[type="range"]::-moz-range-thumb {
            pointer-events: auto;
        }

        .range-track {
            position: absolute;
            width: 100%;
            height: 8px;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
        }

        .range-highlight {
            position: absolute;
            height: 8px;
            top: 50%;
            transform: translateY(-50%);
            background: linear-gradient(90deg, #4ECDC4, #11998e);
            border-radius: 4px;
        }
    </style>
</head>
<body>
    <div class="container">
        <!-- Header -->
        <div class="header">
            <h1>📊 讨论传播时间线可视化</h1>
            <p>Discussion Propagation Timeline - Interactive Visualization</p>
        </div>

        <!-- Control Panel -->
        <div class="control-panel">
            <div class="controls-row">
                <div class="btn-group">
                    <button id="playBtn" class="play" onclick="togglePlay()">▶ 播放</button>
                    <button id="resetBtn" onclick="resetTimeline()">↺ 重置</button>
                </div>

                <div class="mode-control">
                    <label>模式:</label>
                    <select id="modeSelect" onchange="toggleMode()">
                        <option value="cumulative">累积模式</option>
                        <option value="slice">时间切片</option>
                    </select>
                </div>

                <div class="window-control" id="windowControl">
                    <label>窗口:</label>
                    <select id="windowSelect" onchange="onWindowChange()">
                        <option value="300">5 分钟</option>
                        <option value="900">15 分钟</option>
                        <option value="1800">30 分钟</option>
                        <option value="3600" selected>1 小时</option>
                        <option value="7200">2 小时</option>
                        <option value="14400">4 小时</option>
                        <option value="43200">12 小时</option>
                        <option value="86400">1 天</option>
                    </select>
                </div>

                <div class="speed-control">
                    <label>速度:</label>
                    <select id="speedSelect" onchange="updateSpeed()">
                        <option value="0.5">0.5x</option>
                        <option value="1" selected>1x</option>
                        <option value="2">2x</option>
                        <option value="5">5x</option>
                        <option value="10">10x</option>
                    </select>
                </div>

                <div class="btn-group">
                    <button id="lockViewBtn" onclick="toggleLockView()">🔓 锁定视角</button>
                    <button id="centerBtn" onclick="centerGraph()">⊙ 居中</button>
                </div>
            </div>

            <div class="controls-row">
                <div class="timeline-container">
                    <div class="time-display" id="timeDisplay">
                        Loading...
                    </div>
                    <div class="slider-container">
                        <input type="range" id="timeSlider" min="0" max="100" value="0" oninput="onSliderChange()">
                        <div class="progress-bar" id="progressBar"></div>
                    </div>
                </div>
            </div>
        </div>



        <!-- Graph -->
        <div id="graph-container"></div>

        <!-- Stats Panel -->
        <div class="stats-panel">
            <div class="stat-item roots">
                <div class="label">Root Posts</div>
                <div class="value" id="rootCount">0</div>
            </div>
            <div class="stat-item reposts">
                <div class="label">Reposts</div>
                <div class="value" id="repostCount">0</div>
            </div>
            <div class="stat-item comments">
                <div class="label">Comments</div>
                <div class="value" id="commentCount">0</div>
            </div>
            <div class="stat-item total">
                <div class="label">Total Visible</div>
                <div class="value" id="totalCount">0</div>
            </div>
        </div>
    </div>

    <script>
        // 内嵌数据
        const graphData = EMBEDDED_DATA_PLACEHOLDER;

        // Global variables
        let chart = null;
        let isPlaying = false;
        let animationSpeed = 1;
        let currentTime = 0;
        let animationFrameId = null;
        let viewMode = 'cumulative'; // 'cumulative' or 'slice'
        let sliceWindow = 3600; // 1 hour in seconds
        let sliceStart = 0;
        let sliceEnd = 0;
        let isViewLocked = false;
        let savedZoom = null;
        let savedCenter = null;
        let nodePositions = {}; // 存储节点位置
        let isFirstRender = true;

        // Initialize on page load
        function initializeVisualization() {
            const { timeRange } = graphData;
            
            // Setup slider
            const slider = document.getElementById('timeSlider');
            slider.min = timeRange.min;
            slider.max = timeRange.max;
            slider.value = timeRange.min;
            currentTime = timeRange.min;
            sliceStart = timeRange.min;
            sliceEnd = timeRange.max;

            // Initialize chart
            chart = echarts.init(document.getElementById('graph-container'));
            
            // 监听图表的缩放和平移事件，保存视角状态
            chart.on('graphroam', function(params) {
                if (params.zoom) {
                    savedZoom = params.zoom;
                }
            });

            // 预计算所有节点的初始位置（基于力导向布局的稳定状态）
            precomputeNodePositions();
            
            // Update visualization
            updateVisualization(currentTime);
        }

        function precomputeNodePositions() {
            // 使用同心圆布局预计算节点位置
            // Root 在中心，按时间顺序向外扩散
            const sortedNodes = [...graphData.nodes].sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
            const centerX = 0;
            const centerY = 0;
            
            // 找到所有 root 节点
            const rootNodes = sortedNodes.filter(n => n.category === 0);
            const otherNodes = sortedNodes.filter(n => n.category !== 0);
            
            // Root 节点放在中心区域，大幅增大间距
            rootNodes.forEach((node, i) => {
                const angle = (2 * Math.PI * i) / Math.max(rootNodes.length, 1);
                const radius = rootNodes.length > 1 ? 400 : 0;  // 大幅增大root节点间距
                nodePositions[node.name] = {
                    x: centerX + radius * Math.cos(angle),
                    y: centerY + radius * Math.sin(angle)
                };
            });
            
            // 其他节点按时间分层向外扩展
            const timeSpan = graphData.timeRange.max - graphData.timeRange.min;
            otherNodes.forEach((node, i) => {
                const parentNode = graphData.links.find(l => l.target === node.name);
                let baseX = centerX;
                let baseY = centerY;
                
                if (parentNode && nodePositions[parentNode.source]) {
                    baseX = nodePositions[parentNode.source].x;
                    baseY = nodePositions[parentNode.source].y;
                }
                
                // 基于时间计算半径层级，大幅增大扩散范围
                const timeFactor = timeSpan > 0 ? ((node.timestamp || 0) - graphData.timeRange.min) / timeSpan : 0;
                const layerRadius = 350 + timeFactor * 1200;  // 大幅增大扩散半径
                
                // 随机角度但带有一定聚集性
                const angle = (Math.PI * 2 * i / otherNodes.length) + (Math.random() - 0.5) * 0.3;
                const jitter = (Math.random() - 0.5) * 180;  // 增大随机扰动
                
                nodePositions[node.name] = {
                    x: baseX + layerRadius * Math.cos(angle) + jitter,
                    y: baseY + layerRadius * Math.sin(angle) + jitter
                };
            });
        }

        function updateVisualization(timestamp) {
            if (!graphData) return;

            currentTime = timestamp;
            
            // Filter nodes and links based on current time and mode
            let visibleNodes, visibleLinks;
            
            if (viewMode === 'cumulative') {
                // 累积模式：显示从开始到当前时间的所有节点
                visibleNodes = graphData.nodes.filter(node => 
                    node.timestamp && node.timestamp <= timestamp
                );
                visibleLinks = graphData.links.filter(link => 
                    link.source_time && link.target_time &&
                    link.source_time <= timestamp && 
                    link.target_time <= timestamp
                );
            } else {
                // 时间切片模式：只显示时间窗口内的节点
                const windowStart = timestamp;
                const windowEnd = timestamp + sliceWindow;
                
                visibleNodes = graphData.nodes.filter(node => 
                    node.timestamp && node.timestamp >= windowStart && node.timestamp <= windowEnd
                );
                
                const visibleNodeIds = new Set(visibleNodes.map(n => n.name));
                visibleLinks = graphData.links.filter(link => 
                    visibleNodeIds.has(link.source) && visibleNodeIds.has(link.target)
                );
            }

            // Update stats
            updateStats(visibleNodes);

            // Update time display
            const timeStr = new Date(timestamp * 1000).toLocaleString('zh-CN', {
                year: 'numeric',
                month: '2-digit',
                day: '2-digit',
                hour: '2-digit',
                minute: '2-digit',
                second: '2-digit'
            });
            
            if (viewMode === 'slice') {
                const endTimeStr = new Date((timestamp + sliceWindow) * 1000).toLocaleString('zh-CN', {
                    hour: '2-digit',
                    minute: '2-digit'
                });
                document.getElementById('timeDisplay').textContent = `${timeStr} - ${endTimeStr}`;
            } else {
                document.getElementById('timeDisplay').textContent = timeStr;
            }

            // Update progress bar
            const progress = ((timestamp - graphData.timeRange.min) / (graphData.timeRange.max - graphData.timeRange.min)) * 100;
            document.getElementById('progressBar').style.width = progress + '%';

            // Update slider
            document.getElementById('timeSlider').value = timestamp;

            // Render graph
            renderGraph(visibleNodes, visibleLinks);
        }

        function renderGraph(nodes, links) {
            // 为节点添加固定位置，避免布局跳动
            const positionedNodes = nodes.map(node => {
                const pos = nodePositions[node.name];
                if (pos && isViewLocked) {
                    return {
                        ...node,
                        x: pos.x,
                        y: pos.y,
                        fixed: true
                    };
                }
                return {
                    ...node,
                    x: pos ? pos.x : undefined,
                    y: pos ? pos.y : undefined,
                    fixed: false
                };
            });

            const option = {
                backgroundColor: 'transparent',
                tooltip: {
                    trigger: 'item',
                    backgroundColor: 'rgba(30, 30, 30, 0.95)',
                    borderColor: '#555',
                    borderWidth: 1,
                    padding: 0,
                    textStyle: {
                        color: '#eee'
                    }
                },
                legend: {
                    data: graphData.categories.map(c => c.name),
                    orient: 'vertical',
                    left: '2%',
                    top: '10%',
                    textStyle: {
                        color: '#eee',
                        fontSize: 14
                    },
                    itemGap: 20
                },
                animationDuration: isFirstRender ? 1000 : 300,
                animationDurationUpdate: 300,
                animationEasingUpdate: 'cubicOut',
                series: [{
                    type: 'graph',
                    layout: isViewLocked ? 'none' : 'force',
                    data: positionedNodes,
                    links: links,
                    categories: graphData.categories,
                    roam: true,
                    focusNodeAdjacency: true,
                    draggable: true,
                    symbol: 'circle',
                    force: {
                        repulsion: 3500,
                        gravity: 0.01,
                        edgeLength: [200, 600],
                        friction: 0.9,
                        layoutAnimation: !isViewLocked
                    },
                    lineStyle: {
                        color: 'source',
                        curveness: 0.15,
                        opacity: 0.5,
                        width: 1.5
                    },
                    emphasis: {
                        focus: 'adjacency',
                        lineStyle: {
                            width: 3,
                            opacity: 0.8
                        }
                    },
                    label: {
                        show: false
                    },
                    // 控制缩放范围，防止自动缩放太远
                    zoom: savedZoom || 1,
                    center: savedCenter || null
                }]
            };

            // 使用 notMerge: false 来保持视图状态
            chart.setOption(option, {
                notMerge: false,
                lazyUpdate: true
            });
            
            isFirstRender = false;
        }

        function updateStats(visibleNodes) {
            const counts = {
                root: 0,
                repost: 0,
                comment: 0
            };

            visibleNodes.forEach(node => {
                const nodeId = node.name;
                if (nodeId.startsWith('P_')) {
                    if (node.category === 0) counts.root++;
                    else if (node.category === 1) counts.repost++;
                } else if (nodeId.startsWith('C_')) {
                    counts.comment++;
                }
            });

            document.getElementById('rootCount').textContent = counts.root;
            document.getElementById('repostCount').textContent = counts.repost;
            document.getElementById('commentCount').textContent = counts.comment;
            document.getElementById('totalCount').textContent = visibleNodes.length;
        }

        function onSliderChange() {
            const slider = document.getElementById('timeSlider');
            updateVisualization(parseInt(slider.value));
        }

        function togglePlay() {
            isPlaying = !isPlaying;
            const btn = document.getElementById('playBtn');
            
            if (isPlaying) {
                btn.textContent = '⏸ 暂停';
                btn.className = 'pause';
                // 播放时自动锁定视角
                if (!isViewLocked) {
                    toggleLockView();
                }
                startAnimation();
            } else {
                btn.textContent = '▶ 播放';
                btn.className = 'play';
                stopAnimation();
            }
        }

        function startAnimation() {
            const step = () => {
                if (!isPlaying) return;

                const timeStep = animationSpeed * 30; // 减慢步进
                currentTime += timeStep;

                const maxTime = viewMode === 'slice' ? 
                    graphData.timeRange.max - sliceWindow : 
                    graphData.timeRange.max;

                if (currentTime >= maxTime) {
                    currentTime = maxTime;
                    togglePlay();
                }

                updateVisualization(currentTime);
                animationFrameId = setTimeout(step, 100);
            };

            step();
        }

        function stopAnimation() {
            if (animationFrameId) {
                clearTimeout(animationFrameId);
                animationFrameId = null;
            }
        }

        function resetTimeline() {
            stopAnimation();
            isPlaying = false;
            isFirstRender = true;
            document.getElementById('playBtn').textContent = '▶ 播放';
            document.getElementById('playBtn').className = 'play';
            
            currentTime = graphData.timeRange.min;
            savedZoom = null;
            savedCenter = null;
            updateVisualization(currentTime);
        }

        function updateSpeed() {
            const select = document.getElementById('speedSelect');
            animationSpeed = parseFloat(select.value);
        }

        function toggleMode() {
            const select = document.getElementById('modeSelect');
            viewMode = select.value;
            
            const windowControl = document.getElementById('windowControl');
            if (viewMode === 'slice') {
                windowControl.classList.add('active');
            } else {
                windowControl.classList.remove('active');
            }
            
            updateVisualization(currentTime);
        }

        function toggleLockView() {
            isViewLocked = !isViewLocked;
            const btn = document.getElementById('lockViewBtn');
            
            if (isViewLocked) {
                btn.textContent = '🔒 解锁视角';
                btn.classList.add('active');
                // 保存当前节点位置
                saveCurrentPositions();
            } else {
                btn.textContent = '🔓 锁定视角';
                btn.classList.remove('active');
            }
            
            updateVisualization(currentTime);
        }

        function saveCurrentPositions() {
            // 从图表中获取当前节点位置
            const option = chart.getOption();
            if (option && option.series && option.series[0] && option.series[0].data) {
                option.series[0].data.forEach(node => {
                    if (node.x !== undefined && node.y !== undefined) {
                        nodePositions[node.name] = { x: node.x, y: node.y };
                    }
                });
            }
        }

        function centerGraph() {
            if (chart) {
                chart.dispatchAction({
                    type: 'restore'
                });
                savedZoom = null;
                savedCenter = null;
            }
        }

        function onWindowChange() {
            const select = document.getElementById('windowSelect');
            sliceWindow = parseInt(select.value);
            updateVisualization(currentTime);
        }

        // Window resize handler
        window.addEventListener('resize', () => {
            if (chart) {
                chart.resize();
            }
        });

        // Initialize on page load
        initializeVisualization();
    </script>
</body>
</html>
'''

# 将数据嵌入HTML
dynamic_html = dynamic_html_template.replace(
    'EMBEDDED_DATA_PLACEHOLDER',
    json.dumps(dynamic_data, ensure_ascii=False)
)

# 保存动态HTML文件
dynamic_html_file = 'transfer_tree_vis/tree_dynamic.html'
with open(dynamic_html_file, 'w', encoding='utf-8') as f:
    f.write(dynamic_html)
print(f"Dynamic visualization generated: {dynamic_html_file}")

# ==========================================
# 5. 渲染静态图表
# ==========================================

c = (
    Graph(init_opts=opts.InitOpts(
        width="100%", 
        height="95vh", 
        page_title="Discussion Impact Graph",
        theme=ThemeType.DARK
    ))
    .add(
        series_name="",
        nodes=nodes,
        links=links,
        categories=categories,
        layout="force",
        symbol="circle",
        # 力引导布局参数微调 - 让图更舒展
        gravity=0.08,
        repulsion=1500, # 增大排斥力，避免挤在一起
        edge_length=[50, 200], # 边长范围
        friction=0.6,
        is_roam=True,
        is_focusnode=True, # 点击节点高亮相邻
        is_draggable=True,
        linestyle_opts=opts.LineStyleOpts(
            color="source", 
            curve=0.1, 
            opacity=0.4, 
            width=1.5
        ),
        label_opts=opts.LabelOpts(is_show=False) # 默认全局关，用节点单独配置覆盖
    )
    .set_global_opts(
        title_opts=opts.TitleOpts(
            title="Discussion Info-Tree", 
            subtitle="Size = Content Impact (Likes/Shares) + Structural Impact (Replies)",
            pos_left="center",
            pos_top="20px",
            title_textstyle_opts=opts.TextStyleOpts(color="#fff", font_size=28, font_weight="bold"),
            subtitle_textstyle_opts=opts.TextStyleOpts(color="#ccc", font_size=14)
        ),
        legend_opts=opts.LegendOpts(
            orient="vertical", 
            pos_left="2%", 
            pos_top="10%",
            item_gap=20,
            textstyle_opts=opts.TextStyleOpts(color="#eee", font_size=14),
            border_color="#444",
            border_width=1,
            padding=15
        ),
        toolbox_opts=opts.ToolboxOpts(
            is_show=True,
            pos_right="2%",    
            feature={
                "saveAsImage": {"title": "Save PNG", "pixel_ratio": 2}, 
                "restore": {"title": "Reset"},     
            }
        ),
        tooltip_opts=opts.TooltipOpts(
            trigger="item", 
            # enterable=True, # Removed due to TypeError in current pyecharts version
            background_color="rgba(30,30,30,0.95)", 
            border_color="#555",
            border_width=1,
            padding=0 # 把 padding 交给内部 div 控制
        ), 
    )
)

output_file = "transfer_tree_vis/tree.html"
c.render(output_file)
print(f"Visualization generated: {output_file}")