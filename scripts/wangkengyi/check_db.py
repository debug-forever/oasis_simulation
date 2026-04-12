import sqlite3
from pathlib import Path

db_path = r"visualization_system\backend\weibo_test\sim_20260203_121042.db"

if not Path(db_path).exists():
    print(f"❌ 数据库文件不存在: {db_path}")
    exit(1)

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 检查表
print("=" * 60)
print("📋 数据库中的表:")
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print([t[0] for t in tables])
print()

# 如果有posts表，检查帖子数量
if ('posts',) in tables:
    post_count = cursor.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    print(f"📝 帖子总数: {post_count}")
    if post_count > 0:
        print("\n前5个帖子:")
        posts = cursor.execute("SELECT post_id, author_id, content FROM posts LIMIT 5").fetchall()
        for p in posts:
            print(f"  - ID={p[0]}, 作者={p[1]}, 内容={p[2][:50]}...")
    print()

# 如果有comments表，检查评论数量  
if ('comments',) in tables:
    comment_count = cursor.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    print(f"💬 评论总数: {comment_count}")
    if comment_count > 0:
        print("\n前5条评论:")
        comments = cursor.execute("SELECT comment_id, post_id, author_id, content FROM comments LIMIT 5").fetchall()
        for c in comments:
            print(f"  - ID={c[0]}, 帖子={c[1]}, 作者={c[2]}, 内容={c[3][:50]}...")
    print()

# 如果有users表，检查用户数量
if ('users',) in tables:
    user_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    print(f"👥 用户总数: {user_count}")
    if user_count > 0:
        print("\n前5个用户:")
        users = cursor.execute("SELECT user_id, name FROM users LIMIT 5").fetchall()
        for u in users:
            print(f"  - ID={u[0]}, 昵称={u[1]}")
    print()

# 如果有history表，查看动作类型分布
if ('history',) in tables:
    print("📊 动作历史统计:")
    actions = cursor.execute("SELECT action_type, COUNT(*) as cnt FROM history GROUP BY action_type ORDER BY cnt DESC").fetchall()
    for action, count in actions:
        print(f"  - {action}: {count}次")
    print()
    
    total_actions = cursor.execute("SELECT COUNT(*) FROM history").fetchone()[0]
    print(f"总动作数: {total_actions}")

conn.close()
