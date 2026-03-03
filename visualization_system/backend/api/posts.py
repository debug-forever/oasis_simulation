"""
帖子相关API端点
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from database.db_manager import get_db_manager
from utils.data_aggregation import build_propagation_tree, get_trending_posts

router = APIRouter(prefix="/api/posts", tags=["posts"])


@router.get("")
async def get_posts(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    post_type: Optional[str] = Query(None, description="帖子类型：original/repost/all"),
    start_time: Optional[str] = Query(None, description="起始时间"),
    end_time: Optional[str] = Query(None, description="结束时间"),
    user_id: Optional[int] = Query(None, description="用户ID筛选")
):
    """
    获取帖子列表
    支持分页、类型筛选、时间范围筛选
    """
    db = get_db_manager()
    
    offset = (page - 1) * page_size
    
    # 构建WHERE条件
    where_conditions = []
    params = []
    
    if post_type == "original":
        where_conditions.append("p.original_post_id IS NULL")
    elif post_type == "repost":
        where_conditions.append("p.original_post_id IS NOT NULL")
    
    if start_time:
        where_conditions.append("p.created_at >= ?")
        params.append(start_time)
    
    if end_time:
        where_conditions.append("p.created_at <= ?")
        params.append(end_time)
    
    if user_id:
        where_conditions.append("p.user_id = ?")
        params.append(user_id)
    
    where_clause = ""
    if where_conditions:
        where_clause = "WHERE " + " AND ".join(where_conditions)
    
    # 获取总数
    count_query = f"SELECT COUNT(*) as total FROM post p {where_clause}"
    total_result = db.execute_single(count_query, tuple(params))
    total = total_result['total'] if total_result else 0
    
    # 获取帖子列表  
    query = f"""
        SELECT 
            p.post_id, p.user_id, p.content, p.created_at,
            p.num_likes, p.num_dislikes, p.num_shares,
            p.original_post_id, p.quote_content,
            u.name as user_name
        FROM post p
        JOIN user u ON p.user_id = u.user_id
        {where_clause}
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?
    """
    params.extend([page_size, offset])
    
    posts = db.execute_query(query, tuple(params))
    
    # 添加is_repost标志
    for post in posts:
        post['is_repost'] = post['original_post_id'] is not None
    
    return {
        "total": total,
        "posts": posts,
        "page": page,
        "page_size": page_size
    }


@router.get("/{post_id}")
async def get_post_detail(post_id: int):
    """
    获取帖子详细信息，包含评论
    """
    db = get_db_manager()
    
    # 获取帖子信息
    post = db.execute_single("""
        SELECT 
            p.post_id, p.user_id, p.content, p.created_at,
            p.num_likes, p.num_dislikes, p.num_shares,
            p.original_post_id, p.quote_content,
            u.name as user_name
        FROM post p
        JOIN user u ON p.user_id = u.user_id
        WHERE p.post_id = ?
    """, (post_id,))
    
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # 获取评论
    comments = db.execute_query("""
        SELECT 
            c.comment_id, c.post_id, c.user_id, c.content, c.created_at,
            c.num_likes, c.num_dislikes,
            u.name as user_name
        FROM comment c
        JOIN user u ON c.user_id = u.user_id
        WHERE c.post_id = ?
        ORDER BY c.created_at ASC
    """, (post_id,))
    
    post_detail = dict(post)
    post_detail['is_repost'] = post['original_post_id'] is not None
    post_detail['comments'] = comments
    post_detail['comment_count'] = len(comments)
    
    return post_detail


@router.get("/{post_id}/comments")
async def get_post_comments(post_id: int):
    """
    获取帖子的所有评论
    """
    db = get_db_manager()
    
    # 检查Post是否存在
    post = db.execute_single("SELECT post_id FROM post WHERE post_id = ?", (post_id,))
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    comments = db.execute_query("""
        SELECT 
            c.comment_id, c.post_id, c.user_id, c.content, c.created_at,
            c.num_likes, c.num_dislikes,
            u.name as user_name
        FROM comment c
        JOIN user u ON c.user_id = u.user_id
        WHERE c.post_id = ?
        ORDER BY c.created_at ASC
    """, (post_id,))
    
    return {
        "post_id": post_id,
        "total": len(comments),
        "comments": comments
    }


@router.get("/{post_id}/propagation")
async def get_post_propagation(post_id: int):
    """
    获取帖子的传播树数据
    用于可视化转发和评论的传播路径
    """
    db = get_db_manager()
    
    # 检查帖子是否存在
    post = db.execute_single("SELECT post_id, original_post_id FROM post WHERE post_id = ?", (post_id,))
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    
    # 如果是转发帖，获取原始帖子ID
    root_post_id = post['original_post_id'] if post['original_post_id'] else post_id
    
    # 构建传播树
    tree = build_propagation_tree(db, root_post_id)
    
    return tree


@router.get("/trending/list")
async def get_trending_posts_list(limit: int = Query(10, ge=1, le=50)):
    """
    获取热门帖子列表
    """
    db = get_db_manager()
    trending = get_trending_posts(db, limit)
    
    return {
        "posts": trending,
        "total": len(trending)
    }


@router.get("/propagation/all")
async def get_all_posts_propagation(
    start_time: Optional[str] = Query(None, description="起始时间"),
    end_time: Optional[str] = Query(None, description="结束时间"),
    limit: Optional[int] = Query(None, ge=1, le=100, description="帖子数量限制")
):
    """
    获取所有帖子的传播图谱
    用于可视化整个社交网络的传播路径
    """
    import time
    from utils.data_aggregation import build_all_posts_propagation
    
    db = get_db_manager()
    
    print(f"\n=== Starting build_all_posts_propagation ===")
    print(f"Parameters: start_time={start_time}, end_time={end_time}, limit={limit}")
    start = time.time()
    
    graph_data = build_all_posts_propagation(db, start_time, end_time, limit)
    
    elapsed = time.time() - start
    print(f"=== Completed in {elapsed:.2f}s ===")
    print(f"Nodes: {len(graph_data.get('nodes', []))}, Links: {len(graph_data.get('links', []))}")
    
    return graph_data

