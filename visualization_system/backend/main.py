"""
FastAPI主应用
"""
import sys
from pathlib import Path

# 添加项目根目录到Python路径，以便找到oasis模块
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 使用绝对导入避免相对导入问题
from api import users, posts, analytics, simulation, network
from database.db_manager import get_db_manager

# 创建FastAPI应用
app = FastAPI(
    title="微博仿真可视化系统 API",
    description="Oasis Weibo Simulation Visualization System",
    version="1.0.0"
)

# 配置CORS - 允许前端跨域访问
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 生产环境应该指定具体域名
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# 注册路由

# 注册路由
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(analytics.router)
app.include_router(simulation.router)  # 新增：模拟功能
app.include_router(network.router)  # 新增：网络分析功能


@app.get("/")
async def root():
    """根路径 - API信息"""
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
    """健康检查"""
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
    """应用启动事件"""
    print("=" * 60)
    print("微博仿真可视化系统 API 启动中...")
    
    try:
        db = get_db_manager()
        stats = db.get_table_stats()
        time_range = db.get_time_range()
        
        print(f"数据库连接成功: {db.db_path}")
        print(f"数据统计:")
        print(f"  - 用户数: {stats.get('user', 0)}")
        print(f"  - 帖子数: {stats.get('post', 0)}")
        print(f"  - 评论数: {stats.get('comment', 0)}")
        print(f"  - 点赞数: {stats.get('like', 0)}")
        print(f"数据时间范围: {time_range.get('min_time')} ~ {time_range.get('max_time')}")
        print("=" * 60)
        print("API文档地址: http://localhost:8001/docs")
        print("=" * 60)
    except Exception as e:
        print(f"警告: 数据库连接失败 - {e}")
        print("请确保数据库文件存在并设置正确的路径")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
