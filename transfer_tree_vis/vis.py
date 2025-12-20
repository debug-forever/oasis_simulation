import sqlite3
import pandas as pd
import textwrap
import math
from pyecharts import options as opts
from pyecharts.charts import Graph
from pyecharts.globals import ThemeType

# ==========================================
# 1. 连数据库取数
# ==========================================
db_path = 'reddit_simulation.db' 
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

MAX_SYMBOL_SIZE = 100
MIN_SYMBOL_SIZE = 8

for _, row in df_all.iterrows():
    nid = row['node_id']
    ntype = row['type']
    
    # --- 综合影响力大小 (Influence Size) ---
    # 结合 结构热度(repies) + 内容热度(likes/shares)
    # Log scale to handle long-tail distribution
    s_degree = structure_degree.get(nid, 0)
    interaction_score = row['num_likes'] + (row['num_shares'] * 2) # 转发权重更高
    
    # 基础分 + 互动分(log) + 结构分(linear)
    size_score = 5 + math.log(interaction_score + 1) * 5 + (s_degree * 2)
    
    # 如果是 Root，给个保底加成
    if ntype == 'root':
        size_score += 15
        
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
# 4. 渲染图表
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

output_file = "Weibo_tree.html"
c.render(output_file)
print(f"Visualization generated: {output_file}")