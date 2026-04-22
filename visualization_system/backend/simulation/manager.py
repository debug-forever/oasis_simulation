"""
模拟任务管理器
负责创建、管理和监控多个并发的模拟任务
"""
import asyncio
import uuid
from typing import Dict, List, Optional
from datetime import datetime

from .models import SimConfig, SimStatus, SimulationTask
from .executor import SimulationExecutor

# Debug Logging Setup
import logging
import sys
import os

debug_log_path = os.path.abspath("debug_startup.log")

def log_debug(msg):
    try:
        with open(debug_log_path, "a", encoding='utf-8') as f:
            f.write(f"[MANAGER] {msg}\n")
    except:
        pass


class SimulationManager:
    """模拟任务管理器（单例）"""
    
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
        self.max_concurrent_tasks = 3  # 最大并发任务数
        self._initialized = True
    
    def create_task(self, config: SimConfig) -> str:
        """
        创建新的模拟任务
        
        Args:
            config: 模拟配置
            
        Returns:
            task_id: 任务ID
        """
        # 检查并发限制
        log_debug(f"Creating task with config: {config.to_dict()}")
        
        running_count = sum(1 for task in self.tasks.values() 
                          if task.status == SimStatus.RUNNING)
        
        if running_count >= self.max_concurrent_tasks:
            log_debug(f"Max concurrent tasks reached: {running_count}")
            raise RuntimeError(
                f"已达到最大并发任务数限制 ({self.max_concurrent_tasks})。"
                "请等待其他任务完成。"
            )
        
        # 生成唯一ID
        task_id = str(uuid.uuid4())[:8]
        log_debug(f"Generated task_id: {task_id}")
        
        try:
            # 创建任务
            task = SimulationTask(task_id, config)
            self.tasks[task_id] = task
            
            # 创建执行器
            log_debug("Initializing SimulationExecutor...")
            executor = SimulationExecutor(task)
            self.executors[task_id] = executor
            log_debug("Executor initialized.")
            
            # 在后台启动任务
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
        """
        在后台运行模拟任务
        
        Args:
            task_id: 任务ID
        """
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
            print(f"任务 {task_id} 执行失败: {e}")
            # 异常已在executor中处理
    
    def get_task(self, task_id: str) -> Optional[SimulationTask]:
        """
        获取任务信息
        
        Args:
            task_id: 任务ID
            
        Returns:
            任务信息，如果不存在返回None
        """
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> List[SimulationTask]:
        """
        获取所有任务列表
        
        Returns:
            任务列表
        """
        return list(self.tasks.values())
    
    def stop_task(self, task_id: str) -> bool:
        """
        停止运行中的任务
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功停止
        """
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
        """
        删除任务（仅限已完成或失败的任务）
        
        Args:
            task_id: 任务ID
            
        Returns:
            是否成功删除
        """
        task = self.tasks.get(task_id)
        
        if not task:
            return False
        
        # 只能删除非运行中的任务
        if task.status == SimStatus.RUNNING:
            return False
        
        del self.tasks[task_id]
        if task_id in self.executors:
            del self.executors[task_id]
        
        return True
    
    def get_logs(self, task_id: str, max_lines: int = 100) -> List[str]:
        """
        获取任务日志
        
        Args:
            task_id: 任务ID
            max_lines: 最大行数
            
        Returns:
            日志列表
        """
        task = self.tasks.get(task_id)
        if not task:
            return []
        
        return task.logs[-max_lines:]
