import sqlite3
import json

db_path = r"E:\Project\oasis_simulation\visualization_system\weibo_sim_vllm_api1.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 统计action类型
print("=== Action Types in Trace Table ===")
cursor.execute("SELECT action, COUNT(*) as count FROM trace GROUP BY action ORDER BY count DESC")
actions = cursor.fetchall()
for action, count in actions:
    print(f"{action}: {count}")

print("\n=== Sample Records for Each Action Type ===")
for action, _ in actions[:5]:  # 只查看前5种action类型的样本
    print(f"\n--- Action: {action} ---")
    cursor.execute("SELECT user_id, created_at, info FROM trace WHERE action = ? LIMIT 2", (action,))
    samples = cursor.fetchall()
    for sample in samples:
        user_id, created_at, info = sample
        print(f"User: {user_id}, Time: {created_at}")
        if info:
            try:
                parsed = json.loads(info)
                print(f"Info: {json.dumps(parsed, indent=2, ensure_ascii=False)}")
            except:
                print(f"Info (raw): {info[:200]}")
        print()

# 检查post表和comment表的数据
print("\n=== Post and Comment Statistics ===")
cursor.execute("SELECT COUNT(*) FROM post")
post_count = cursor.fetchone()[0]
print(f"Total posts: {post_count}")

cursor.execute("SELECT COUNT(*) FROM comment")
comment_count = cursor.fetchone()[0]
print(f"Total comments: {comment_count}")

# 检查是否有原创帖子（非转发）
cursor.execute("SELECT COUNT(*) FROM post WHERE original_post_id IS NULL")
original_posts = cursor.fetchone()[0]
print(f"Original posts: {original_posts}")

cursor.execute("SELECT COUNT(*) FROM post WHERE original_post_id IS NOT NULL")
repost_count = cursor.fetchone()[0]
print(f"Reposts: {repost_count}")

# 查看几个用户的发帖情况
print("\n=== Top 5 Active Users (by post count) ===")
cursor.execute("""
    SELECT user_id, COUNT(*) as post_count 
    FROM post 
    GROUP BY user_id 
    ORDER BY post_count DESC 
    LIMIT 5
""")
top_users = cursor.fetchall()
for user_id, post_count in top_users:
    print(f"User {user_id}: {post_count} posts")

conn.close()
