import asyncio
import logging
import uuid
from typing import Dict, List, Optional
from datetime import datetime

from .models import SimConfig, SimStatus, SimulationTask
from .executor import SimulationExecutor
from utils.logging import append_debug


logger = logging.getLogger(__name__)


def log_debug(msg: str) -> None:
    append_debug("MANAGER", msg)
    logger.debug(msg)


class SimulationManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.tasks: Dict[str, SimulationTask] = {}
        self.executors: Dict[str, SimulationExecutor] = {}
        self.max_concurrent_tasks = 3
        self._initialized = True
    
    def create_task(self, config: SimConfig) -> str:
        log_debug(f"Creating task with config: {config.to_dict()}")
        
        running_count = sum(1 for task in self.tasks.values() 
                          if task.status == SimStatus.RUNNING)
        
        if running_count >= self.max_concurrent_tasks:
            log_debug(f"Max concurrent tasks reached: {running_count}")
            raise RuntimeError(
                f"已达到最大并发任务数限制 ({self.max_concurrent_tasks})。"
                "请等待其他任务完成。"
            )
        
        task_id = str(uuid.uuid4())[:8]
        log_debug(f"Generated task_id: {task_id}")
        
        try:
            task = SimulationTask(task_id, config)
            self.tasks[task_id] = task
            
            log_debug("Initializing SimulationExecutor...")
            executor = SimulationExecutor(task)
            self.executors[task_id] = executor
            log_debug("Executor initialized.")
            
            log_debug("Starting background task...")
            asyncio.create_task(self._run_task(task_id))
            log_debug("Background task scheduled.")
        except Exception as e:
            log_debug(f"Error in create_task: {e}")
            import traceback
            log_debug(traceback.format_exc())
            raise
        
        return task_id
    
    async def _run_task(self, task_id: str):
        log_debug(f"Starting background task execution for {task_id}")
        executor = self.executors.get(task_id)
        if not executor:
            log_debug(f"Executor not found for {task_id}")
            return
        
        try:
            log_debug(f"Calling executor.run() for {task_id}")
            await executor.run()
            log_debug(f"Executor completed for {task_id}")
        except Exception as e:
            log_debug(f"Task {task_id} execution failed: {e}")
            import traceback
            log_debug(traceback.format_exc())
            logger.exception("任务 %s 执行失败", task_id)
    
    def get_task(self, task_id: str) -> Optional[SimulationTask]:
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[SimulationTask]:
        return list(self.tasks.values())
    
    def stop_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        executor = self.executors.get(task_id)
        
        if not task or not executor:
            return False
        
        if task.status != SimStatus.RUNNING:
            return False
        
        executor.stop()
        task.status = SimStatus.STOPPED
        task.completed_at = datetime.now()
        
        return True
    
    def delete_task(self, task_id: str) -> bool:
        task = self.tasks.get(task_id)
        
        if not task:
            return False
        
        if task.status == SimStatus.RUNNING:
            return False
        
        del self.tasks[task_id]
        if task_id in self.executors:
            del self.executors[task_id]
        
        return True
    
    def get_logs(self, task_id: str, max_lines: int = 100) -> List[str]:
        task = self.tasks.get(task_id)
        if not task:
            return []
        
        return task.logs[-max_lines:]
