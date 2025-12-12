import sqlite3
import pandas as pd
import os

def export_entire_db_to_excel(db_path, output_excel_name):
    """
    自动读取 SQLite 数据库中的所有表，并导出到一个 Excel 文件中。
    每个表占用一个 Sheet。
    """
    # 1. 检查数据库是否存在
    if not os.path.exists(db_path):
        print(f"❌ 错误：找不到数据库文件 {db_path}")
        return

    print(f"🔄 正在连接数据库: {db_path} ...")
    conn = sqlite3.connect(db_path)
    
    try:
        # 2. 获取数据库中所有表的名称
        # sqlite_master 是 SQLite 的系统表，记录了所有表的信息
        query_tables = "SELECT name FROM sqlite_master WHERE type='table';"
        tables = pd.read_sql(query_tables, conn)
        table_list = tables['name'].tolist()
        
        print(f"📋 发现 {len(table_list)} 个表: {table_list}")
        
        # 3. 创建 Excel 写入器
        print(f"💾 正在写入 Excel 文件: {output_excel_name} ...")
        with pd.ExcelWriter(output_excel_name, engine='openpyxl') as writer:
            for table_name in table_list:
                try:
                    # 读取该表的所有数据
                    df = pd.read_sql(f"SELECT * FROM {table_name}", conn, parse_dates=['created_at', 'time'])
                    
                    # 检查数据是否为空
                    row_count = len(df)
                    status = f"✅ {row_count} 行" if row_count > 0 else "⚠️ 空表"
                    
                    # Excel Sheet 名称最长不能超过 31 个字符
                    sheet_name = table_name[:31]
                    
                    # 写入 Sheet
                    df.to_excel(writer, sheet_name=sheet_name, index=False)
                    print(f"   - 导出表 [{table_name}]: {status}")
                    
                except Exception as e:
                    print(f"   - ❌ 导出表 [{table_name}] 失败: {e}")

        print(f"\n🎉 导出完成！所有数据已保存至：{output_excel_name}")
        
    except Exception as e:
        print(f"❌ 发生未知错误: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    # 配置你的路径
    DB_FILE = "weibo_test/weibo_sim_openai.db"
    OUTPUT_FILE = "weibo_sim_data_all.xlsx"
    
    export_entire_db_to_excel(DB_FILE, OUTPUT_FILE)