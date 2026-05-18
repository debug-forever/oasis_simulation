"""SQLite connection and query helpers."""
import logging
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Dict, Any, Optional


logger = logging.getLogger(__name__)
TABLES = ("user", "post", "comment", "like", "dislike", "follow", "mute", "trace")
FALLBACK_DB_PATH = r"E:\Project\oasis_simulation\visualization_system\weibo_sim_vllm_api1.db"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _candidate_paths() -> List[str]:
    weibo_test = _repo_root() / "weibo_test"
    return [
        os.environ.get("OASIS_DB_PATH"),
        FALLBACK_DB_PATH,
        str(weibo_test / "weibo_sim_qwen_huawei.db"),
        str(weibo_test / "weibo_sim_openai.db"),
        str(weibo_test / "weibo_sim_vllm.db"),
        str(weibo_test / "weibo_sim_demo.db"),
        r"E:\Project\oasis_simulation\weibo_test\weibo_sim_demo.db",
        "weibo_test/weibo_sim_demo.db",
        "../weibo_test/weibo_sim_demo.db",
        "../../weibo_test/weibo_sim_demo.db",
        "weibo_test/weibo_sim_openai.db",
        "weibo_test/weibo_sim_vllm.db",
        "../weibo_test/weibo_sim_openai.db",
        "../../weibo_test/weibo_sim_openai.db",
    ]


class DatabaseManager:
    def __init__(self, db_path: str = None):
        if db_path is None:
            for path in _candidate_paths():
                if path and os.path.exists(path):
                    db_path = path
                    break
            
            if db_path is None:
                raise FileNotFoundError(
                    "Database not found. Please set OASIS_DB_PATH environment variable "
                    "or place database in weibo_test/ directory"
                )
        
        self.db_path = db_path
        logger.info("Using database: %s", self.db_path)
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()
    
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            columns = [column[0] for column in cursor.description] if cursor.description else []
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def execute_single(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        results = self.execute_query(query, params)
        return results[0] if results else None
    
    def get_table_stats(self) -> Dict[str, int]:
        stats = {}
        
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for table in TABLES:
                try:
                    cursor.execute(f"SELECT COUNT(*) FROM {table}")
                    stats[table] = cursor.fetchone()[0]
                except sqlite3.OperationalError:
                    stats[table] = 0
        
        return stats
    
    def get_time_range(self) -> Dict[str, Optional[str]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
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


db_manager = None


def get_db_manager() -> DatabaseManager:
    global db_manager
    if db_manager is None:
        db_manager = DatabaseManager()
    return db_manager


def switch_database(new_db_path: str) -> DatabaseManager:
    global db_manager
    
    if not os.path.exists(new_db_path):
        raise FileNotFoundError(f"Database file not found: {new_db_path}")
    
    db_manager = DatabaseManager(db_path=new_db_path)
    logger.info("Database switched to: %s", new_db_path)
    
    return db_manager


def get_current_db_path() -> Optional[str]:
    global db_manager
    if db_manager is None:
        return None
    return db_manager.db_path
