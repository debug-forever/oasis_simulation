"""
数据库管理模块
负责SQLite数据库连接和查询操作
"""
import sqlite3
import os
from typing import List, Dict, Any, Optional
from contextlib import contextmanager


class DatabaseManager:
    """数据库管理器"""
    
    def __init__(self, db_path: str = None):
        """
        初始化数据库管理器
        
        Args:
            db_path: 数据库文件路径，如果为None则从环境变量或默认路径获取
        """
        if db_path is None:
            # ========================================
            # 📍 数据库路径配置（在这里修改数据库路径）
            # ========================================
            # 将您的数据库文件路径写在下面这一行：
            DEFAULT_DB_PATH = r"E:\Project\oasis_simulation\visualization_system\weibo_sim_vllm_api1.db"
            # ========================================
            
            # 尝试多个可能的数据库位置
            possible_paths = [
                # 最高优先级：上面设置的默认路径
                DEFAULT_DB_PATH,
                # 其次：环境变量
                os.environ.get("OASIS_DB_PATH"),
                # 最后：其他常见位置（用于回退）
                r"E:\Project\oasis_simulation\weibo_test\weibo_sim_demo.db",
                "weibo_test/weibo_sim_demo.db",
                "../weibo_test/weibo_sim_demo.db",
                "../../weibo_test/weibo_sim_demo.db",
                "weibo_test/weibo_sim_openai.db",
                "weibo_test/weibo_sim_vllm.db",
                "../weibo_test/weibo_sim_openai.db",
                "../../weibo_test/weibo_sim_openai.db",
            ]
            
            for path in possible_paths:
                if path and os.path.exists(path):
                    db_path = path
                    break
            
            if db_path is None:
                raise FileNotFoundError(
                    "Database not found. Please set OASIS_DB_PATH environment variable "
                    "or place database in weibo_test/ directory"
                )
        
        self.db_path = db_path
        print(f"Using database: {self.db_path}")
    
    @contextmanager
    def get_connection(self):
        """
        获取数据库连接的上下文管理器
        
        Yields:
            sqlite3.Connection: 数据库连接对象
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # 使查询结果可以像字典一样访问
        try:
            yield conn
        finally:
            conn.close()
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        执行查询并返回结果
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            查询结果列表
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            columns = [column[0] for column in cursor.description] if cursor.description else []
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def execute_single(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """
        执行查询并返回单条结果
        
        Args:
            query: SQL查询语句
            params: 查询参数
            
        Returns:
            单条查询结果，如果没有结果则返回None
        """
        results = self.execute_query(query, params)
        return results[0] if results else None
    
    def get_table_stats(self) -> Dict[str, int]:
        """
        获取所有表的记录数统计
        
        Returns:
            表名到记录数的映射
        """
        tables = ['user', 'post', 'comment', 'like', 'dislike', 'follow', 'mute', 'trace']
        stats = {}
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for table in tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[table] = cursor.fetchone()[0]
                except sqlite3.OperationalError:
                    stats[table] = 0
        
        return stats
    
    def get_time_range(self) -> Dict[str, Optional[str]]:
        """
        获取数据的时间范围
        
        Returns:
            包含最早和最晚时间的字典
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # 从post表获取时间范围
            cursor.execute("""
                SELECT 
                    MIN(created_at) as min_time,
                    MAX(created_at) as max_time
                FROM post
            """)
            result = cursor.fetchone()
            
            return {
                'min_time': result[0] if result else None,
                'max_time': result[1] if result else None
            }


# 全局数据库实例
db_manager = None


def get_db_manager() -> DatabaseManager:
    """
    获取数据库管理器实例（单例模式）
    
    Returns:
        DatabaseManager实例
    """
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager


def switch_database(new_db_path: str) -> DatabaseManager:
    """
    切换到新的数据库
    
    Args:
        new_db_path: 新数据库文件的路径
        
    Returns:
        新的DatabaseManager实例
        
    Raises:
        FileNotFoundError: 如果新数据库文件不存在
    """
    global db_manager
    
    # 验证新数据库文件存在
    if not os.path.exists(new_db_path):
        raise FileNotFoundError(f"Database file not found: {new_db_path}")
    
    # 创建新的数据库管理器实例
    db_manager = DatabaseManager(db_path=new_db_path)
    print(f"✅ Database switched to: {new_db_path}")
    
    return db_manager


def get_current_db_path() -> Optional[str]:
    """
    获取当前连接的数据库路径
    
    Returns:
        当前数据库路径，如果未初始化则返回None
    """
    global db_manager
    if db_manager is None:
        return None
    return db_manager.db_path
