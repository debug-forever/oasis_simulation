import sqlite3
from pathlib import Path

latest = max(Path("visualization_system/backend/weibo_test").glob("sim_*.db"), key=lambda p: p.stat().st_mtime)
conn = sqlite3.connect(latest)
cur = conn.cursor()

# 只看动作统计
print("=== 动作类型统计 ===")
for row in cur.execute("SELECT action_type, COUNT(*) as c FROM history GROUP BY action_type ORDER BY c DESC LIMIT 10"):
    print(f"{row[0]}: {row[1]}")

print(f"\nCREATE_POST次数: {cur.execute('SELECT COUNT(*) FROM history WHERE action_type=\"CREATE_POST\"').fetchone()[0]}")

# 看看是否有comments表
try:
    cnt = cur.execute("SELECT COUNT(*) FROM comments").fetchone()[0]
    print(f"comments表记录数: {cnt}")
except:
    print("comments表不存在")

# 看看是否有posts表
try:
    cnt = cur.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
    print(f"posts表记录数: {cnt}")
except:
    print("posts表不存在")

conn.close()
