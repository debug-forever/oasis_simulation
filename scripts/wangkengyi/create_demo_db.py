"""
创建测试数据库用于演示可视化系统
"""
import sqlite3
from datetime import datetime, timedelta

# 创建数据库
db_path = "weibo_test/weibo_sim_demo.db"
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 创建用户表
cursor.execute("""
CREATE TABLE IF NOT EXISTS user (
    user_id INTEGER PRIMARY KEY,
    agent_id TEXT,
    user_name TEXT,
    name TEXT,
    bio TEXT,
    created_at TEXT,
    num_followings INTEGER DEFAULT 0,
    num_followers INTEGER DEFAULT 0,
    follower_list TEXT,
    follower_id_list TEXT,
    follower_num_list TEXT,
    weibo_id TEXT
)
""")

# 创建帖子表
cursor.execute("""
CREATE TABLE IF NOT EXISTS post (
    post_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    original_post_id INTEGER,
    content TEXT,
    quote_content TEXT,
    created_at TEXT,
    num_likes INTEGER DEFAULT 0,
    num_dislikes INTEGER DEFAULT 0,
    num_shares INTEGER DEFAULT 0,
    num_reports INTEGER DEFAULT 0,
    FOREIGN KEY (user_id) REFERENCES user(user_id),
    FOREIGN KEY (original_post_id) REFERENCES post(post_id)
)
""")

# 创建评论表
cursor.execute("""
CREATE TABLE IF NOT EXISTS comment (
    comment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER,
    user_id INTEGER,
    content TEXT,
    created_at TEXT,
    num_likes INTEGER DEFAULT 0,
    num_dislikes INTEGER DEFAULT 0,
    FOREIGN KEY (post_id) REFERENCES post(post_id),
    FOREIGN KEY (user_id) REFERENCES user(user_id)
)
""")

# 创建其他表
for table in ['like', 'dislike', 'follow', 'mute', 'trace']:
    cursor.execute(f"""
    CREATE TABLE IF NOT EXISTS "{table}" (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        created_at TEXT
    )
    """)

# 插入测试用户数据
users = [
    (1, "agent_1", "tech_enthusiast", "张三", "热爱科技的普通人", 0, 0),
    (2, "agent_2", "ai_researcher", "李四", "人工智能研究员", 0, 0),
    (3, "agent_3", "daily_life", "王五", "分享生活点滴", 0, 0),
    (4, "agent_4", "news_curator", "赵六", "新闻爱好者", 0, 0),
    (5, "agent_5", "food_lover", "刘七", "美食探索家", 0, 0),
]

base_time = datetime.now() - timedelta(days=7)

for i, (uid, aid, uname, name, bio, following, followers) in enumerate(users):
    created = (base_time + timedelta(hours=i)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO user (user_id, agent_id, user_name, name, bio, created_at, num_followings, num_followers)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (uid, aid, uname, name, bio, created, following, followers))

# 插入测试帖子数据
posts = [
    (1, None, "今天天气真好，适合出去走走！☀️", 15, 2, 3),
    (1, None, "刚看了一部很棒的科幻电影，推荐给大家", 28, 1, 8),
    (2, None, "最新的大语言模型技术真是太神奇了！#AI #机器学习", 45, 0, 12),
    (2, 3, "确实！AI的发展速度令人惊叹", 20, 0, 5),
    (3, None, "今天做了一道新菜，味道不错😋", 30, 1, 6),
    (4, None, "【重要新闻】某某领域取得重大突破", 58, 2, 15),
    (5, None, "分享一家超赞的餐厅，地址在...", 25, 0, 7),
    (1, 2, "转发！这个技术确实值得关注", 18, 1, 4),
    (3, 6, "这个新闻太重要了！", 12, 0, 3),
    (4, None, "今日热点汇总 #新闻", 40, 1, 10),
]

for i, (user_id, orig_id, content, likes, dislikes, shares) in enumerate(posts):
    created = (base_time + timedelta(hours=i+1, minutes=i*15)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO post (user_id, original_post_id, content, created_at, num_likes, num_dislikes, num_shares)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (user_id, orig_id, content, created, likes, dislikes, shares))

# 插入测试评论数据
comments = [
    (1, 2, "我也超喜欢科幻电影！", 8, 0),
    (2, 1, "确实是好天气！", 5, 0),
    (3, 3, "能分享一下具体是哪个模型吗？", 12, 0),
    (4, 5, "看起来好好吃！", 6, 0),
    (5, 6, "感谢分享这个重要信息", 10, 0),
    (1, 3, "期待更多AI相关的内容", 7, 0),
    (2, 7, "收藏了，有机会去试试", 4, 0),
    (3, 10, "热点追得很及时👍", 5, 0),
]

for post_id, user_id, content, likes, dislikes in comments:
    created = (base_time + timedelta(hours=post_id+2, minutes=30)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO comment (post_id, user_id, content, created_at, num_likes, num_dislikes)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (post_id, user_id, content, created, likes, dislikes))

# 插入一些点赞和关注数据
for i in range(1, 50):
    user_id = (i % 5) + 1
    created = (base_time + timedelta(hours=i, minutes=i*5)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('INSERT INTO "like" (user_id, created_at) VALUES (?, ?)', (user_id, created))

for i in range(1, 15):
    user_id = (i % 5) + 1
    created = (base_time + timedelta(hours=i*2)).strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('INSERT INTO follow (user_id, created_at) VALUES (?, ?)', (user_id, created))

# 提交并关闭
conn.commit()
conn.close()

print(f"✅ 测试数据库创建成功: {db_path}")
print(f"📊 包含:")
print(f"   - 5个用户")
print(f"   - 10个帖子（包括原创和转发）")
print(f"   - 8条评论")
print(f"   - 约50个点赞")
print(f"   - 约15个关注关系")
print(f"\n现在可以设置环境变量:")
print(f'$env:OASIS_DB_PATH="{db_path}"')
