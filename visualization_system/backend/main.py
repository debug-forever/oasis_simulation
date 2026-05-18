"""FastAPI application entrypoint."""
import logging
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import users, posts, analytics, simulation, network, va
from database.db_manager import get_db_manager

logging.basicConfig(level=logging.INFO, format="%(levelname)s:%(name)s:%(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="微博仿真可视化系统 API",
    description="Oasis Weibo Simulation Visualization System",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


for router in (
    users.router,
    posts.router,
    analytics.router,
    simulation.router,
    network.router,
    va.router,
):
    app.include_router(router)


@app.get("/")
async def root():
    return {
        "name": "微博仿真可视化系统 API",
        "version": "1.0.0",
        "description": "提供用户、帖子、评论、传播分析等数据的RESTful API",
        "docs": "/docs",
        "endpoints": {
            "users": "/api/users",
            "posts": "/api/posts",
            "analytics": "/api/analytics"
        }
    }


@app.get("/health")
async def health_check():
    try:
        db = get_db_manager()
        stats = db.get_table_stats()
        return {
            "status": "healthy",
            "database": "connected",
            "tables": stats
        }
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.on_event("startup")
async def startup_event():
    logger.info("微博仿真可视化系统 API 启动中...")
    
    try:
        db = get_db_manager()
        stats = db.get_table_stats()
        time_range = db.get_time_range()

        logger.info("数据库连接成功: %s", db.db_path)
        logger.info(
            "数据统计: users=%s posts=%s comments=%s likes=%s",
            stats.get("user", 0),
            stats.get("post", 0),
            stats.get("comment", 0),
            stats.get("like", 0),
        )
        logger.info(
            "数据时间范围: %s ~ %s",
            time_range.get("min_time"),
            time_range.get("max_time"),
        )
        logger.info("API文档地址: http://localhost:8001/docs")
    except Exception as e:
        logger.warning("数据库连接失败: %s", e)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8001)
