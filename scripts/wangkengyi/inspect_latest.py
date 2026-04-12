"""检查最新模拟的详细情况"""
import sqlite3
from pathlib import Path
import os

# 找到最新的数据库
weibo_test_dir = Path(r"visualization_system\backend\weibo_test")
db_files = list(weibo_test_dir.glob("sim_*.db"))

if not db_files:
    print("❌ 没有数据库文件")
    exit(1)

latest_db = max(db_files, key=lambda p: p.stat().st_mtime)
print(f"📁 最新数据库: {latest_db.name}")
print(f"⏰ 修改时间: {os.path.getmtime(latest_db)}")
print()

conn = sqlite3.connect(latest_db)
cursor = conn.cursor()

# 检查所有表
tables = [t[0] for t in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print(f"📊 数据库中的表: {tables}")
print()

# 检查history表
if 'history' in tables:
    print("=" * 60)
    print("📜 动作历史统计:")
    actions = cursor.execute("""
        SELECT action_type, COUNT(*) as cnt 
        FROM history 
        GROUP BY action_type 
        ORDER BY cnt DESC
    """).fetchall()
    
    total = 0
    for action, count in actions:
        print(f"  {action}: {count}次")
        total += count
    print(f"\n  总计: {total}次动作")
    print()
    
    # 查看前10条history记录
    print("前10条动作记录:")
    records = cursor.execute("""
        SELECT action_type, agent_id, action_content, timestamp 
        FROM history 
        ORDER BY timestamp 
        LIMIT 10
    """).fetchall()
    for r in records:
        content = r[2][:50] if r[2] else "无内容"
        print(f"  [{r[3]}] Agent {r[1]}: {r[0]} - {content}")

# 检查comments表
if 'comments' in tables:
    print("\n" + "=" * 60)
    print("💬 评论统计:")
    comment_count = cursor.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    print(f"总评论数: {comment_count}")
    
    if comment_count > 0:
        print("\n前5条评论:")
        comments = cursor.execute("""
            SELECT comment_id, post_id, author_id, content 
            FROM comments 
            LIMIT 5
        """).fetchall()
        for c in comments:
            print(f"  评论{c[0]}: Agent {c[2]} -> 帖子{c[1]}")
            print(f"    内容: {c[3][:60]}")

# 检查posts表
if 'posts' in tables:
    print("\n" + "=" * 60)
    print("📝 帖子统计:")
    post_count = cursor.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    print(f"总帖子数: {post_count}")
    
    if post_count > 0:
        print("\n所有帖子:")
        posts = cursor.execute("""
            SELECT post_id, author_id, content, created_at 
            FROM posts 
            ORDER BY created_at
        """).fetchall()
        for p in posts:
            print(f"  帖子{p[0]}: Agent {p[1]} ({p[3]})")
            print(f"    内容: {p[2][:80]}")
else:
    print("\n❌ posts表不存在！")

conn.close()
