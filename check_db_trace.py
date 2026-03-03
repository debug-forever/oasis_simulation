import sqlite3
import json

db_path = r"E:\Project\oasis_simulation\visualization_system\weibo_sim_vllm_api1.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 查看trace表的结构
print("=== Trace Table Schema ===")
cursor.execute("PRAGMA table_info(trace)")
columns = cursor.fetchall()
for col in columns:
    print(f"{col[1]} ({col[2]})")

column_names = [col[1] for col in columns]
print(f"\nColumn names: {column_names}")

# 查看trace表的总记录数
cursor.execute("SELECT COUNT(*) FROM trace")
total_count = cursor.fetchone()[0]
print(f"\n=== Total trace records: {total_count} ===")

# 查看前10条trace记录
print("\n=== First 10 trace records ===")
cursor.execute("SELECT * FROM trace LIMIT 10")
rows = cursor.fetchall()
for i, row in enumerate(rows):
    print(f"\nRecord {i+1}:")
    for col_idx, col_name in enumerate(column_names):
        value = row[col_idx]
        # 如果是info字段，尝试解析JSON
        if col_name == 'info' and value:
            try:
                parsed = json.loads(value)
                print(f"  {col_name}: {json.dumps(parsed, indent=4, ensure_ascii=False)}")
            except:
                print(f"  {col_name}: {value}")
        else:
            print(f"  {col_name}: {value}")

# 统计各表的数据量
print("\n=== Table Statistics ===")
tables = ['user', 'post', 'comment', 'like', 'dislike', 'follow']
for table in tables:
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"{table}: {count}")
    except Exception as e:
        print(f"{table}: Error - {e}")

# 查看post表的前5条数据
print("\n=== First 5 posts ===")
cursor.execute("SELECT post_id, user_id, content, created_at FROM post LIMIT 5")
posts = cursor.fetchall()
for post in posts:
    print(f"Post ID: {post[0]}, User: {post[1]}, Created: {post[3]}")
    print(f"  Content: {post[2][:100] if post[2] else 'None'}...")

conn.close()
