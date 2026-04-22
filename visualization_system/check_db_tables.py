import sqlite3
import sys

db_path = sys.argv[1] if len(sys.argv) > 1 else "weibo_test/sim_20260204_182118.db"

try:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 获取所有表名
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    
    print("=" * 60)
    print(f"数据库: {db_path}")
    print("=" * 60)
    print(f"表列表: {tables}")
    print()
    
    # 对每个表统计行数
    for table in tables:
        try:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  {table}: {count} 行")
        except Exception as e:
            print(f"  {table}: 错误 - {e}")
    
    conn.close()
    
except Exception as e:
    print(f"错误: {e}")
