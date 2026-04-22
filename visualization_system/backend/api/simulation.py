"""
模拟功能API端点
提供启动、监控和管理模拟任务的RESTful API
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, List, Dict, Any

from simulation.manager import SimulationManager
from simulation.models import SimConfig

router = APIRouter(prefix="/api/simulation", tags=["simulation"])

# 全局管理器实例
manager = SimulationManager()

# Debug Logging Setup
import logging
import sys
import os

debug_log_path = os.path.abspath("debug_startup.log")
logging.basicConfig(
    filename=debug_log_path,
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    force=True
)
logger = logging.getLogger("simulation_api")

def log_debug(msg):
    with open(debug_log_path, "a", encoding='utf-8') as f:
        f.write(f"[API] {msg}\n")
    logger.debug(msg)

log_debug("Simulation API module loaded")


@router.post("/start")
async def start_simulation(request: Dict[str, Any]):
    """
    启动新的模拟任务
    
    请求体示例：
    {
        "config": {
            "num_agents": 10,
            "num_rounds": 5,
            "llm_provider": "vllm",
            "llm_endpoint": "http://127.0.0.1:8000/v1",
            "model_name": "qwen-2",
            "enable_llm": true,
            "dataset_path": "weibo_test/total_data_with_descriptions_transformers.json",
            "output_db_name": "my_simulation.db"
        }
    }
    """

    try:
        log_debug(f"Received start_simulation request: {request}")
        
        # 解析配置
        config_data = request.get("config", {})
        log_debug(f"Parsed config data: {config_data}")
        
        config = SimConfig(
            num_agents=config_data.get("num_agents", 10),
            num_rounds=config_data.get("num_rounds", 5),
            llm_provider=config_data.get("llm_provider", "vllm"),
            llm_endpoint=config_data.get("llm_endpoint", "http://127.0.0.1:8000/v1"),
            model_name=config_data.get("model_name", "qwen-2"),
            enable_llm=config_data.get("enable_llm", True),
            dataset_path=config_data.get("dataset_path", "weibo_test/total_data_with_descriptions_transformers.json"),
            output_db_name=config_data.get("output_db_name"),
            enable_seed_posts=config_data.get("enable_seed_posts", True),
            num_seed_posts=config_data.get("num_seed_posts", 2),
            seed_agent_ids=config_data.get("seed_agent_ids")
        )
        
        log_debug(f"Created SimConfig: {config.to_dict()}")
        
        # 创建任务
        log_debug("Calling manager.create_task...")
        task_id = manager.create_task(config)
        log_debug(f"Task created successfully. ID: {task_id}")
        
        return {
            "task_id": task_id,
            "status": "started",
            "message": "模拟任务已启动"
        }
    
    except RuntimeError as e:
        log_debug(f"RuntimeError in start_simulation: {e}")
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        log_debug(f"Exception in start_simulation: {e}")
        import traceback
        log_debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"启动失败: {str(e)}")


@router.get("/list")
async def list_simulations():
    """
    获取所有模拟任务列表
    """
    tasks = manager.get_all_tasks()
    return {
        "tasks": [task.to_dict() for task in tasks],
        "total": len(tasks)
    }


@router.get("/{task_id}/status")
async def get_simulation_status(task_id: str):
    """
    获取指定模拟任务的状态
    """
    task = manager.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return task.to_dict()


@router.get("/{task_id}/logs")
async def get_simulation_logs(
    task_id: str,
    max_lines: int = 100
):
    """
    获取模拟任务的日志
    """
    task = manager.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    logs = manager.get_logs(task_id, max_lines)
    
    return {
        "task_id": task_id,
        "logs": logs,
        "total_lines": len(task.logs)
    }


@router.delete("/{task_id}/stop")
async def stop_simulation(task_id: str):
    """
    停止运行中的模拟任务
    """
    success = manager.stop_task(task_id)
    
    if not success:
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        raise HTTPException(status_code=400, detail="任务未在运行中，无法停止")
    
    return {
        "task_id": task_id,
        "status": "stopped",
        "message": "任务已停止"
    }


@router.delete("/{task_id}")
async def delete_simulation(task_id: str):
    """
    删除模拟任务（仅限已完成或失败的任务）
    """
    success = manager.delete_task(task_id)
    
    if not success:
        task = manager.get_task(task_id)
        if not task:
            raise HTTPException(status_code=404, detail="任务不存在")
        raise HTTPException(status_code=400, detail="无法删除运行中的任务")
    
    return {
        "task_id": task_id,
        "status": "deleted",
        "message": "任务已删除"
    }


@router.get("/{task_id}/result")
async def get_simulation_result(task_id: str):
    """
    获取模拟结果（完成后的数据库路径和统计信息）
    """
    task = manager.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    if task.status.value not in ["completed", "stopped"]:
        raise HTTPException(status_code=400, detail="任务尚未完成")
    
    return {
        "task_id": task_id,
        "db_path": task.db_path,
        "stats": task.stats.to_dict(),
        "config": task.config.to_dict(),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None
    }



@router.get("/list-databases")
async def list_database_files():
    """
    获取所有可用的数据库文件列表
    扫描 weibo_test 目录和项目根目录下的 .db 文件
    """
    import os
    import glob
    from pathlib import Path
    
    db_files = []
    
    # 定义搜索路径
    search_paths = [
        "weibo_test/*.db",
        "*.db",
        "../weibo_test/*.db",
        "../*.db" 
    ]
    
    # 获取当前工作目录，用于计算相对路径
    cwd = os.getcwd()
    
    for pattern in search_paths:
        try:
            # 查找文件
            files = glob.glob(pattern)
            for f in files:
                abs_path = os.path.abspath(f)
                
                # 获取文件信息
                stat = os.stat(abs_path)
                size_mb = round(stat.st_size / (1024 * 1024), 2)
                mtime = stat.st_mtime
                
                # 添加到列表（避免重复）
                file_info = {
                    "path": abs_path,
                    "name": os.path.basename(abs_path),
                    "size_mb": size_mb,
                    "mtime": mtime,
                    "modified": os.path.getmtime(abs_path)
                }
                
                # 检查是否已存在（通过绝对路径去重）
                if not any(item["path"] == abs_path for item in db_files):
                    db_files.append(file_info)
                    
        except Exception as e:
            print(f"Error searching {pattern}: {e}")
            continue
    
    # 按修改时间倒序排列
    db_files.sort(key=lambda x: x["mtime"], reverse=True)
    
    return {
        "databases": db_files,
        "count": len(db_files)
    }


@router.post("/switch-database")
async def switch_to_database(request: Dict[str, Any]):
    """
    切换到指定的数据库
    
    请求体示例：
    {
        "db_path": "weibo_test/weibo_sim_20240204_123456.db"
    }
    """
    from database.db_manager import switch_database, get_db_manager
    
    try:
        db_path = request.get("db_path")
        if not db_path:
            raise HTTPException(status_code=400, detail="db_path is required")
        
        # 切换数据库
        new_db = switch_database(db_path)
        
        # 获取新数据库的统计信息
        stats = new_db.get_table_stats()
        
        return {
            "success": True,
            "db_path": db_path,
            "stats": {
                "users": stats.get("user", 0),
                "posts": stats.get("post", 0),
                "comments": stats.get("comment", 0),
                "likes": stats.get("like", 0),
                "follows": stats.get("follow", 0)
            },
            "message": f"Successfully switched to database: {db_path}"
        }
    
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to switch database: {str(e)}")


@router.get("/current-db")
async def get_current_database():
    """
    获取当前连接的数据库信息
    """
    from database.db_manager import get_current_db_path, get_db_manager
    
    try:
        db_path = get_current_db_path()
        
        if not db_path:
            return {
                "db_path": None,
                "status": "not_initialized"
            }
        
        db = get_db_manager()
        stats = db.get_table_stats()
        
        return {
            "db_path": db_path,
            "stats": {
                "users": stats.get("user", 0),
                "posts": stats.get("post", 0),
                "comments": stats.get("comment", 0),
                "likes": stats.get("like", 0),
                "follows": stats.get("follow", 0)
            },
            "status": "connected"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

