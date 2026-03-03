"""
模拟功能的数据模型
"""
from typing import Optional, Dict, Any
from datetime import datetime
from enum import Enum


class SimStatus(str, Enum):
    """模拟任务状态"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    STOPPED = "stopped"


class SimConfig:
    """模拟配置"""
    def __init__(
        self,
        num_agents: int = 10,
        num_rounds: int = 5,
        llm_provider: str = "vllm",
        llm_endpoint: str = "http://127.0.0.1:8000/v1",
        model_name: str = "qwen-2",
        enable_llm: bool = True,
        dataset_path: str = "weibo_test/total_data_with_descriptions_transformers.json",
        output_db_name: Optional[str] = None,
        enable_seed_posts: bool = True,
        num_seed_posts: int = 2,
        seed_agent_ids: Optional[list[int]] = None
    ):
        self.num_agents = num_agents
        self.num_rounds = num_rounds
        self.llm_provider = llm_provider
        self.llm_endpoint = llm_endpoint
        self.model_name = model_name
        self.enable_llm = enable_llm
        self.dataset_path = dataset_path
        self.output_db_name = output_db_name or self._generate_db_name()
        self.enable_seed_posts = enable_seed_posts
        self.num_seed_posts = num_seed_posts
        self.seed_agent_ids = seed_agent_ids if seed_agent_ids is not None else list(range(num_seed_posts))
    
    def _generate_db_name(self) -> str:
        """生成默认数据库名称"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        return f"sim_{timestamp}.db"
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "num_agents": self.num_agents,
            "num_rounds": self.num_rounds,
            "llm_provider": self.llm_provider,
            "llm_endpoint": self.llm_endpoint,
            "model_name": self.model_name,
            "enable_llm": self.enable_llm,
            "dataset_path": self.dataset_path,
            "output_db_name": self.output_db_name,
            "enable_seed_posts": self.enable_seed_posts,
            "num_seed_posts": self.num_seed_posts,
            "seed_agent_ids": self.seed_agent_ids
        }


class SimProgress:
    """模拟进度信息"""
    def __init__(self):
        self.current_round = 0
        self.total_rounds = 0
        self.percentage = 0.0
        self.current_action = ""
    
    def update(self, current_round: int, total_rounds: int, action: str = ""):
        """更新进度"""
        self.current_round = current_round
        self.total_rounds = total_rounds
        self.percentage = (current_round / total_rounds * 100) if total_rounds > 0 else 0
        self.current_action = action
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "current_round": self.current_round,
            "total_rounds": self.total_rounds,
            "percentage": round(self.percentage, 2),
            "current_action": self.current_action
        }


class SimStats:
    """模拟统计信息"""
    def __init__(self):
        self.users_created = 0
        self.posts_created = 0
        self.comments_created = 0
        self.elapsed_time = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "users_created": self.users_created,
            "posts_created": self.posts_created,
            "comments_created": self.comments_created,
            "elapsed_time": round(self.elapsed_time, 2)
        }


class SimulationTask:
    """模拟任务信息"""
    def __init__(self, task_id: str, config: SimConfig):
        self.task_id = task_id
        self.config = config
        self.status = SimStatus.PENDING
        self.progress = SimProgress()
        self.stats = SimStats()
        self.db_path: Optional[str] = None
        self.created_at = datetime.now()
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None
        self.logs: list[str] = []
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "id": self.task_id,
            "status": self.status.value,
            "progress": self.progress.to_dict(),
            "stats": self.stats.to_dict(),
            "db_path": self.db_path,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
            "config": self.config.to_dict()
        }
