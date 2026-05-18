import glob
import logging
import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException

from database.db_manager import get_current_db_path, switch_database
from simulation.manager import SimulationManager
from simulation.models import SimConfig, SimulationTask
from utils.logging import append_debug


router = APIRouter(prefix="/api/simulation", tags=["simulation"])
manager = SimulationManager()
logger = logging.getLogger(__name__)


def log_debug(message: str) -> None:
    append_debug("API", message)
    logger.debug(message)


def _build_config(config_data: Dict[str, Any]) -> SimConfig:
    return SimConfig(
        num_agents=config_data.get("num_agents", 10),
        num_rounds=config_data.get("num_rounds", 5),
        llm_provider=config_data.get("llm_provider", "vllm"),
        llm_endpoint=config_data.get("llm_endpoint", "http://127.0.0.1:8000/v1"),
        model_name=config_data.get("model_name", "qwen-2"),
        enable_llm=config_data.get("enable_llm", True),
        dataset_path=config_data.get(
            "dataset_path",
            "weibo_test/total_data_with_descriptions_transformers.json",
        ),
        output_db_name=config_data.get("output_db_name"),
        enable_seed_posts=config_data.get("enable_seed_posts", True),
        num_seed_posts=config_data.get("num_seed_posts", 2),
        seed_agent_ids=config_data.get("seed_agent_ids"),
    )


def _task_or_404(task_id: str) -> SimulationTask:
    task = manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


def _db_stats_payload(stats: Dict[str, int]) -> Dict[str, int]:
    return {
        "users": stats.get("user", 0),
        "posts": stats.get("post", 0),
        "comments": stats.get("comment", 0),
        "likes": stats.get("like", 0),
        "follows": stats.get("follow", 0),
    }


def _find_databases() -> list[Dict[str, Any]]:
    patterns = ("weibo_test/*.db", "*.db", "../weibo_test/*.db", "../*.db")
    databases = {}

    for pattern in patterns:
        try:
            for file_path in glob.glob(pattern):
                abs_path = os.path.abspath(file_path)
                if abs_path in databases:
                    continue

                stat = os.stat(abs_path)
                databases[abs_path] = {
                    "path": abs_path,
                    "name": os.path.basename(abs_path),
                    "size_mb": round(stat.st_size / (1024 * 1024), 2),
                    "mtime": stat.st_mtime,
                    "modified": stat.st_mtime,
                }
        except OSError:
            logger.exception("Failed to scan database pattern: %s", pattern)

    return sorted(databases.values(), key=lambda item: item["mtime"], reverse=True)


log_debug("Simulation API module loaded")


@router.post("/start")
async def start_simulation(request: Dict[str, Any]):
    try:
        log_debug(f"Received start_simulation request: {request}")
        config = _build_config(request.get("config", {}))
        log_debug(f"Created SimConfig: {config.to_dict()}")
        task_id = manager.create_task(config)

        return {
            "task_id": task_id,
            "status": "started",
            "message": "模拟任务已启动",
        }
    except RuntimeError as e:
        log_debug(f"RuntimeError in start_simulation: {e}")
        raise HTTPException(status_code=429, detail=str(e))
    except Exception as e:
        log_debug(f"Exception in start_simulation: {e}")
        logger.exception("Failed to start simulation")
        raise HTTPException(status_code=500, detail=f"启动失败: {str(e)}")


@router.get("/list")
async def list_simulations():
    tasks = manager.get_all_tasks()
    return {
        "tasks": [task.to_dict() for task in tasks],
        "total": len(tasks),
    }


@router.get("/{task_id}/status")
async def get_simulation_status(task_id: str):
    return _task_or_404(task_id).to_dict()


@router.get("/{task_id}/logs")
async def get_simulation_logs(task_id: str, max_lines: int = 100):
    task = _task_or_404(task_id)
    logs = manager.get_logs(task_id, max_lines)

    return {
        "task_id": task_id,
        "logs": logs,
        "total_lines": len(task.logs),
    }


@router.delete("/{task_id}/stop")
async def stop_simulation(task_id: str):
    success = manager.stop_task(task_id)

    if not success:
        _task_or_404(task_id)
        raise HTTPException(status_code=400, detail="任务未在运行中，无法停止")

    return {
        "task_id": task_id,
        "status": "stopped",
        "message": "任务已停止",
    }


@router.delete("/{task_id}")
async def delete_simulation(task_id: str):
    success = manager.delete_task(task_id)

    if not success:
        _task_or_404(task_id)
        raise HTTPException(status_code=400, detail="无法删除运行中的任务")

    return {
        "task_id": task_id,
        "status": "deleted",
        "message": "任务已删除",
    }


@router.get("/{task_id}/result")
async def get_simulation_result(task_id: str):
    task = _task_or_404(task_id)

    if task.status.value not in ("completed", "stopped"):
        raise HTTPException(status_code=400, detail="任务尚未完成")

    return {
        "task_id": task_id,
        "db_path": task.db_path,
        "stats": task.stats.to_dict(),
        "config": task.config.to_dict(),
        "completed_at": task.completed_at.isoformat() if task.completed_at else None,
    }


@router.get("/list-databases")
async def list_database_files():
    db_files = _find_databases()
    return {
        "databases": db_files,
        "count": len(db_files),
    }


@router.post("/switch-database")
async def switch_to_database(request: Dict[str, Any]):
    try:
        db_path = request.get("db_path")
        if not db_path:
            raise HTTPException(status_code=400, detail="db_path is required")

        new_db = switch_database(db_path)

        return {
            "success": True,
            "db_path": db_path,
            "stats": _db_stats_payload(new_db.get_table_stats()),
            "message": f"Successfully switched to database: {db_path}",
        }
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Failed to switch database")
        raise HTTPException(status_code=500, detail=f"Failed to switch database: {str(e)}")


@router.get("/current-db")
async def get_current_database():
    try:
        db_path = get_current_db_path()

        if not db_path:
            return {
                "db_path": None,
                "status": "not_initialized",
            }

        from database.db_manager import get_db_manager

        db = get_db_manager()
        return {
            "db_path": db_path,
            "stats": _db_stats_payload(db.get_table_stats()),
            "status": "connected",
        }
    except Exception as e:
        logger.exception("Failed to read current database")
        raise HTTPException(status_code=500, detail=str(e))
