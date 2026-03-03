"""
用户相关API端点
"""
from fastapi import APIRouter, HTTPException, Query
from typing import Optional
from database.db_manager import get_db_manager

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("")
async def get_users(
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页数量"),
    search: Optional[str] = Query(None, description="搜索用户名")
):
    """
    获取用户列表
    支持分页和搜索
    """
    db = get_db_manager()
    
    offset = (page - 1) * page_size
    
    # 构建查询条件
    where_clause = ""
    params = []
    
    if search:
        where_clause = "WHERE name LIKE ? OR user_name LIKE ?"
        search_param = f"%{search}%"
        params = [search_param, search_param]
    
    # 获取总数
    count_query = f"SELECT COUNT(*) as total FROM user {where_clause}"
    total_result = db.execute_single(count_query, tuple(params))
    total = total_result['total'] if total_result else 0
    
    # 获取用户列表
    query = f"""
        SELECT user_id, name, user_name, bio, created_at, 
               num_followings, num_followers
        FROM user
        {where_clause}
        ORDER BY user_id
        LIMIT ? OFFSET ?
    """
    params.extend([page_size, offset])
    
    users = db.execute_query(query, tuple(params))
    
    return {
        "total": total,
        "users": users,
        "page": page,
        "page_size": page_size
    }


@router.get("/{user_id}")
async def get_user_detail(user_id: int):
    """
    获取用户详细信息
    """
    db = get_db_manager()
    
    # 获取用户基本信息
    user = db.execute_single("""
        SELECT user_id, name, user_name, bio, created_at,
               num_followings, num_followers, weibo_id,
               follower_list, follower_num_list
        FROM user
        WHERE user_id = ?
    """, (user_id,))
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 获取发帖数
    post_count = db.execute_single("""
        SELECT COUNT(*) as count FROM post WHERE user_id = ?
    """, (user_id,))
    
    # 获取评论数
    comment_count = db.execute_single("""
        SELECT COUNT(*) as count FROM comment WHERE user_id = ?
    """, (user_id,))
    
    # 获取点赞数
    like_count = db.execute_single("""
        SELECT COUNT(*) as count FROM 'like' WHERE user_id = ?
    """, (user_id,))
    
    # 获取获得的点赞数
    total_likes = db.execute_single("""
        SELECT SUM(num_likes) as total FROM post WHERE user_id = ?
    """, (user_id,))
    
    user_detail = dict(user)
    user_detail['post_count'] = post_count['count'] if post_count else 0
    user_detail['comment_count'] = comment_count['count'] if comment_count else 0
    user_detail['like_count'] = like_count['count'] if like_count else 0
    user_detail['total_likes_received'] = total_likes['total'] if total_likes and total_likes['total'] else 0
    
    return user_detail


@router.get("/{user_id}/posts")
async def get_user_posts(
    user_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100)
):
    """
    获取用户的帖子列表
    """
    db = get_db_manager()
    
    offset = (page - 1) * page_size
    
    # 获取总数
    total = db.execute_single("""
        SELECT COUNT(*) as total FROM post WHERE user_id = ?
    """, (user_id,))
    
    # 获取帖子
    posts = db.execute_query("""
        SELECT 
            p.post_id, p.user_id, p.content, p.created_at,
            p.num_likes, p.num_dislikes, p.num_shares,
            p.original_post_id, p.quote_content,
            u.name as user_name
        FROM post p
        JOIN user u ON p.user_id = u.user_id
        WHERE p.user_id = ?
        ORDER BY p.created_at DESC
        LIMIT ? OFFSET ?
    """, (user_id, page_size, offset))
    
    # 添加is_repost标志
    for post in posts:
        post['is_repost'] = post['original_post_id'] is not None
    
    return {
        "total": total['total'] if total else 0,
        "posts": posts,
        "page": page,
        "page_size": page_size
    }


@router.get("/{user_id}/interactions")
async def get_user_interactions(user_id: int):
    """
    获取用户互动统计
    """
    db = get_db_manager()
    
    # 用户是否存在
    user = db.execute_single("SELECT user_id FROM user WHERE user_id = ?", (user_id,))
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # 获取关注的用户
    following = db.execute_query("""
        SELECT f.followee_id, u.name
        FROM follow f
        JOIN user u ON f.followee_id = u.user_id
        WHERE f.follower_id = ?
    """, (user_id,))
    
    # 获取粉丝
    followers = db.execute_query("""
        SELECT f.follower_id, u.name
        FROM follow f
        JOIN user u ON f.follower_id = u.user_id
        WHERE f.followee_id = ?
    """, (user_id,))
    
    # 获取点赞过的帖子
    liked_posts = db.execute_query("""
        SELECT l.post_id, l.created_at
        FROM 'like' l
        WHERE l.user_id = ?
        ORDER BY l.created_at DESC
        LIMIT 50
    """, (user_id,))
    
    # 获取评论过的帖子
    commented_posts = db.execute_query("""
        SELECT DISTINCT c.post_id, COUNT(*) as comment_count
        FROM comment c
        WHERE c.user_id = ?
        GROUP BY c.post_id
        ORDER BY comment_count DESC
        LIMIT 50
    """, (user_id,))
    
    return {
        "user_id": user_id,
        "following": following,
        "followers": followers,
        "liked_posts": liked_posts,
        "commented_posts": commented_posts,
        "stats": {
            "following_count": len(following),
            "follower_count": len(followers),
            "liked_count": len(liked_posts),
            "commented_posts_count": len(commented_posts)
        }
    }
