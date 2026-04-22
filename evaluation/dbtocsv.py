import sqlite3
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "db" / "weibo_sim_qwen_huawei.db"

conn = sqlite3.connect(str(DB_PATH))
t_names = ["comment", "post", "user", "trace"]

for t in t_names:
    if t == "user":
        df = pd.read_sql_query(f"SELECT user_id, weibo_id FROM {t}", conn)
    else:
        df = pd.read_sql_query(f"SELECT * FROM {t}", conn)

    # 导出 CSV，UTF-8 带 BOM（适合 Windows Excel）
    df.to_csv(BASE_DIR / f"{t}.csv", index=False, encoding="utf-8-sig")

conn.close()
