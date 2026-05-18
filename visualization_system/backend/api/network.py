import logging

from fastapi import APIRouter, HTTPException, Query
from database.db_manager import get_db_manager
from utils.data_aggregation import (
    build_relationship_network
)

router = APIRouter(prefix="/api/network", tags=["network"])
logger = logging.getLogger(__name__)


@router.get("/relationship-graph")
async def get_relationship_graph(
    limit: int = Query(100, ge=10, le=5000, description="节点数量限制"),
    min_followers: int = Query(0, ge=0, description="最小粉丝数筛选")
):
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
        logger.exception("Failed to build relationship graph")
        raise HTTPException(status_code=500, detail=str(e))

