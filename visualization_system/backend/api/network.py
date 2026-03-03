"""
网络分析相关API端点
提供用户关系网络、互动矩阵、社群分析等功能
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from database.db_manager import get_db_manager
from utils.data_aggregation import (
    build_relationship_network
)

router = APIRouter(prefix="/api/network", tags=["network"])


@router.get("/relationship-graph")
async def get_relationship_graph(
    limit: int = Query(100, ge=10, le=5000, description="节点数量限制"),
    min_followers: int = Query(0, ge=0, description="最小粉丝数筛选")
):
    """
    获取用户关系网络图数据
    
    返回用户节点和关注关系边，用于绘制关系网络图
    """
    try:
        db = get_db_manager()
        network_data = build_relationship_network(db, limit, min_followers)
        
        return {
            "success": True,
            "data": network_data,
            "total_nodes": len(network_data.get('nodes', [])),
            "total_edges": len(network_data.get('links', []))
        }
    except Exception as e:
        import traceback
        print(f"Error in get_relationship_graph: {str(e)}")
        print(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))



