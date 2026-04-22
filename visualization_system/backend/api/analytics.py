"""
数据分析相关API端点
"""
from fastapi import APIRouter, Query
from typing import Optional
from database.db_manager import get_db_manager
from utils.data_aggregation import (
    build_user_network, calculate_influence_score,
    aggregate_timeline_data, get_trending_posts
)

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview")
async def get_overview_stats():
    """
    获取总体统计数据
    """
    try:
        db = get_db_manager()
        
        # 获取表统计
        stats = db.get_table_stats()
        
        # 获取时间范围
        time_range = db.get_time_range()
        
        # 获取活跃用户数（发过帖的用户）
        active_users = db.execute_single("""
            SELECT COUNT(DISTINCT user_id) as count FROM post
        """)
        
        # 计算平均发帖数
        total_posts = stats.get('post', 0)
        total_users = stats.get('user', 0)
        avg_posts_per_user = round(total_posts / total_users, 2) if total_users > 0 else 0.0
        
        # 统计转发数（original_post_id不为空的帖子）
        reposts = db.execute_single("""
            SELECT COUNT(*) as count FROM post WHERE original_post_id IS NOT NULL
        """)
        
        return {
            "total_users": total_users,
            "total_posts": total_posts,
            "total_comments": stats.get('comment', 0),
            "total_likes": stats.get('like', 0),
            "total_dislikes": stats.get('dislike', 0),
            "total_follows": stats.get('follow', 0),
            "total_reposts": reposts['count'] if reposts else 0,
            "earliest_time": time_range.get('min_time'),
            "latest_time": time_range.get('max_time'),
            "active_users": active_users['count'] if active_users else 0,
            "avg_posts_per_user": avg_posts_per_user
        }
    except Exception as e:
        import traceback
        print(f"Error in get_overview_stats: {str(e)}")
        print(traceback.format_exc())
        return {
            "total_users": 0,
            "total_posts": 0,
            "total_comments": 0,
            "total_likes": 0,
            "total_dislikes": 0,
            "total_follows": 0,
            "total_reposts": 0,
            "earliest_time": None,
            "latest_time": None,
            "active_users": 0,
            "avg_posts_per_user": 0.0,
            "error": str(e)
        }


@router.get("/timeline")
async def get_timeline_data(
    start_time: Optional[str] = Query(None, description="起始时间"),
    end_time: Optional[str] = Query(None, description="结束时间"),
    interval: str = Query("hour", description="时间间隔：hour/day")
):
    """
    获取时间线聚合数据
    用于绘制活动趋势图
    """
    db = get_db_manager()
    
    timeline = aggregate_timeline_data(db, start_time, end_time, interval)
    
    return {
        "data": timeline,
        "time_unit": interval
    }


@router.get("/network")
async def get_user_network(limit: int = Query(100, ge=10, le=500)):
    """
    获取用户关系网络图数据
    """
    db = get_db_manager()
    
    network = build_user_network(db, limit)
    
    return network


@router.get("/influence")
async def get_influence_ranking(limit: int = Query(20, ge=1, le=100)):
    """
    获取影响力排行榜
    """
    db = get_db_manager()
    
    # 查询用户数据并计算影响力
    users = db.execute_query("""
        SELECT 
            u.user_id,
            u.name as user_name,
            u.num_followers as follower_count,
            COUNT(DISTINCT p.post_id) as post_count,
            COALESCE(SUM(p.num_likes), 0) as total_likes,
            COALESCE(SUM(p.num_shares), 0) as total_shares
        FROM user u
        LEFT JOIN post p ON u.user_id = p.user_id
        GROUP BY u.user_id
        ORDER BY u.num_followers DESC
        LIMIT ?
    """, (limit * 2,))  # 获取更多数据用于计算
    
    # 计算影响力分数
    rankings = []
    for user in users:
        score = calculate_influence_score({
            'follower_count': user['follower_count'] or 0,
            'post_count': user['post_count'] or 0,
            'total_likes': user['total_likes'] or 0,
            'total_shares': user['total_shares'] or 0
        })
        
        rankings.append({
            'user_id': user['user_id'],
            'user_name': user['user_name'],
            'score': score,
            'post_count': user['post_count'] or 0,
            'total_likes': user['total_likes'] or 0,
            'total_shares': user['total_shares'] or 0,
            'follower_count': user['follower_count'] or 0
        })
    
    # 按分数排序
    rankings.sort(key=lambda x: x['score'], reverse=True)
    
    return {
        "rankings": rankings[:limit],
        "total": len(rankings)
    }


@router.get("/activity")
async def get_activity_stats(
    start_time: Optional[str] = Query(None),
    end_time: Optional[str] = Query(None)
):
    """
    获取活跃度分析数据
    """
    db = get_db_manager()
    
    # 构建时间过滤
    time_filter = ""
    params = []
    
    if start_time:
        time_filter += " AND created_at >= ?"
        params.append(start_time)
    if end_time:
        time_filter += " AND created_at <= ?"
        params.append(end_time)
    
    # 获取每小时活跃用户数
    hourly_activity = db.execute_query(f"""
        SELECT 
            strftime('%Y-%m-%d %H:00:00', created_at) as hour,
            COUNT(DISTINCT user_id) as active_users,
            COUNT(*) as action_count
        FROM (
            SELECT user_id, created_at FROM post WHERE 1=1 {time_filter}
            UNION ALL
            SELECT user_id, created_at FROM comment WHERE 1=1 {time_filter}
        )
        GROUP BY hour
        ORDER BY hour
    """, tuple(params * 2))
    
    # 获取最活跃用户
    most_active_users = db.execute_query(f"""
        SELECT 
            user_id,
            COUNT(*) as action_count
        FROM (
            SELECT user_id, created_at FROM post WHERE 1=1 {time_filter}
            UNION ALL
            SELECT user_id, created_at FROM comment WHERE 1=1 {time_filter}
        )
        GROUP BY user_id
        ORDER BY action_count DESC
        LIMIT 10
    """, tuple(params * 2))
    
    # 获取用户名
    for user in most_active_users:
        user_info = db.execute_single(
            "SELECT name FROM user WHERE user_id = ?",
            (user['user_id'],)
        )
        user['user_name'] = user_info['name'] if user_info else 'Unknown'
    
    return {
        "hourly_activity": hourly_activity,
        "most_active_users": most_active_users
    }
