"""简单验证：seed posts是否被执行"""
import sqlite3
from pathlib import Path

# 找最新db
latest_db = max(
    Path(r"visualization_system\backend\weibo_test").glob("sim_*.db"),
    key=lambda p: p.stat().st_mtime
)

print(f"数据库: {latest_db.name}\n")

conn = sqlite3.connect(latest_db)
cursor = conn.cursor()

# 检查表
tables = [t[0] for t in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print(f"表: {', '.join(tables)}\n")

# 统计动作
if 'history' in tables:
    print("动作统计:")
    for row in cursor.execute("SELECT action_type, COUNT(*) FROM history GROUP BY action_type ORDER BY COUNT(*) DESC"):
        print(f"  {row[0]}: {row[1]}")
    
    print(f"\n总动作: {cursor.execute('SELECT COUNT(*) FROM history').fetchone()[0]}")

# 检查是否有CREATE_POST动作
if 'history' in tables:
    create_post_count = cursor.execute("SELECT COUNT(*) FROM history WHERE action_type='CREATE_POST'").fetchone()[0]
    print(f"\nCREATE_POST动作数: {create_post_count}")
    
    if create_post_count > 0:
        print("\nCREATE_POST详情:")
        for row in cursor.execute("SELECT agent_id, action_content, timestamp FROM history WHERE action_type='CREATE_POST' LIMIT 5"):
            print(f"  Agent {row[0]}: {row[1][:50] if row[1] else '无'}")

conn.close()
