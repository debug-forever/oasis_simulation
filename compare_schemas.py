"""
快速测试：验证posts表是在哪一步创建的
"""
import sqlite3
from pathlib import Path

# 检查示例数据库
example_db = Path("weibo_test/weibo_sim_openai.db")
if example_db.exists():
    print("检查示例数据库:", example_db)
    conn = sqlite3.connect(example_db)
    cursor = conn.cursor()
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print("表:", [t[0] for t in tables])
    
    if ('posts',) in tables:
        count = cursor.execute("SELECT COUNT(*) FROM posts").fetchone()[0]
        print(f"posts表存在，记录数: {count}")
    conn.close()
else:
    print("示例数据库不存在")

print()

# 检查最新模拟数据库
sim_db = Path("visualization_system/backend/weibo_test/sim_20260203_131708.db")
if sim_db.exists():
    print("检查模拟数据库:", sim_db)
    conn = sqlite3.connect(sim_db)
    cursor = conn.cursor()
    tables = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print("表:", [t[0] for t in tables])
    
    # 检查是否有users表
    if ('users',) in tables:
        user_count = cursor.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        print(f"users表存在，用户数: {user_count}")
    
    conn.close()
