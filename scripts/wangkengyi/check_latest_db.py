import sqlite3
from pathlib import Path
import os

# 找到最新的数据库文件
weibo_test_dir = Path(r"visualization_system\backend\weibo_test")
db_files = list(weibo_test_dir.glob("*.db"))

if not db_files:
    print("❌ 没有找到数据库文件")
    exit(1)

# 按修改时间排序，取最新的
latest_db = max(db_files, key=lambda p: p.stat().st_mtime)
print(f"📁 检查最新数据库: {latest_db}")
print(f"📅 修改时间: {os.path.getmtime(latest_db)}")
print()

conn = sqlite3.connect(latest_db)
cursor = conn.cursor()

# 检查表
print("=" * 60)
print("📋 数据库表:")
tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print([t[0] for t in tables])
print()

# 检查用户数
if ('users',) in tables:
    user_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    print(f"👥 用户总数: {user_count}")
    print()

# 检查帖子
if ('posts',) in tables:
    post_count = cursor.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    print(f"📝 帖子总数: {post_count}")
    if post_count > 0:
        print("\n所有帖子:")
        posts = cursor.execute("SELECT post_id, author_id, content, created_at FROM posts ORDER BY created_at").fetchall()
        for p in posts:
            print(f"  [{p[0]}] Agent {p[1]}: {p[2][:80]}...")
            print(f"       时间: {p[3]}")
    print()

# 检查评论
if ('comments',) in tables:
    comment_count = cursor.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    print(f"💬 评论总数: {comment_count}")
    if comment_count > 0:
        print("\n所有评论:")
        comments = cursor.execute("SELECT comment_id, post_id, author_id, content FROM comments LIMIT 10").fetchall()
        for c in comments:
            print(f"  [{c[0]}] Agent {c[2]} 评论帖子 {c[1]}: {c[3][:60]}...")
    print()

# 检查历史动作
if ('history',) in tables:
    print("📊 动作历史统计:")
    actions = cursor.execute("""
        SELECT action_type, COUNT(*) as cnt 
        FROM history 
        GROUP BY action_type 
        ORDER BY cnt DESC
    """).fetchall()
    for action, count in actions:
        print(f"  - {action}: {count}次")
    print()
    
    total_actions = cursor.execute("SELECT COUNT(*) FROM history").fetchone()[0]
    print(f"总动作数: {total_actions}")

conn.close()
