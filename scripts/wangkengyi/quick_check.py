import sqlite3
from pathlib import Path

latest_db = Path(r"visualization_system\backend\weibo_test\sim_20260203_131708.db")

if not latest_db.exists():
    print(f"文件不存在: {latest_db}")
    exit(1)

conn = sqlite3.connect(latest_db)
cursor = conn.cursor()

print("=== 帖子检查 ===")
try:
    post_count = cursor.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    print(f"帖子总数: {post_count}")
    
    if post_count > 0:
        posts = cursor.execute("SELECT post_id, author_id, content FROM posts LIMIT 5").fetchall()
        for p in posts:
            print(f"  帖子{p[0]}: Agent {p[1]} - {p[2][:50]}")
except Exception as e:
    print(f"查询帖子失败: {e}")

print("\n=== 评论检查 ===")
try:
    comment_count = cursor.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    print(f"评论总数: {comment_count}")
except Exception as e:
    print(f"查询评论失败: {e}")

print("\n=== 动作历史 ===")
try:
    actions = cursor.execute("SELECT action_type, COUNT(*) FROM history GROUP BY action_type").fetchall()
    for action, count in actions:
        print(f"  {action}: {count}")
except Exception as e:
    print(f"查询历史失败: {e}")

conn.close()
