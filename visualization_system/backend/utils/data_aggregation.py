"""
数据聚合工具模块
提供数据统计、传播树构建等功能
"""
from typing import List, Dict, Any, Optional, Set, Tuple
from datetime import datetime
from collections import defaultdict
import math
import pandas as pd


def parse_timestamp(ts_str: str) -> Optional[int]:
    """
    将数据库时间戳转换为 Unix 时间戳（秒）
    
    Args:
        ts_str: 时间戳字符串
        
    Returns:
        Unix时间戳(秒),如果解析失败返回None
    """
    if not ts_str or pd.isna(ts_str) or ts_str == '':
        return None
    try:
        # 支持多种时间格式
        if '.' in str(ts_str):
            # 带微秒: 2026-01-13 17:04:57.618708
            dt = datetime.strptime(str(ts_str).split('.')[0], '%Y-%m-%d %H:%M:%S')
        else:
            dt = datetime.strptime(str(ts_str), '%Y-%m-%d %H:%M:%S')
        return int(dt.timestamp())
    except Exception as e:
        print(f"Warning: Could not parse timestamp '{ts_str}': {e}")
        return None


def build_propagation_tree(db_manager, root_post_id: int) -> Dict[str, Any]:
    """
    构建帖子的传播树（增强版，递归获取所有转发链）
    
    Args:
        db_manager: 数据库管理器实例
        root_post_id: 根帖子ID
        
    Returns:
        包含节点、边、时间范围和分类的传播树数据
    """
    # 获取根帖子信息
    root_post = db_manager.execute_single("""
        SELECT p.*, u.name as user_name
        FROM post p
        JOIN user u ON p.user_id = u.user_id
        WHERE p.post_id = ?
    """, (root_post_id,))
    
    if not root_post:
        return {
            'nodes': [],
            'links': [],
            'total_shares': 0,
            'max_depth': 0,
            'timeRange': {'min': 0, 'max': 0, 'minStr': '', 'maxStr': ''},
            'categories': []
        }
    
    # 构建节点和边
    nodes = []
    links = []
    processed_posts = set()  # 避免重复处理
    
    # 添加根节点
    root_node_id = f"P_{root_post_id}"
    root_timestamp = parse_timestamp(root_post['created_at'])
    nodes.append({
        'node_id': root_node_id,
        'post_id': root_post['post_id'],
        'user_id': root_post['user_id'],
        'user_name': root_post['user_name'],
        'content': root_post['content'] or '',
        'created_at': root_post['created_at'],
        'timestamp': root_timestamp,
        'num_likes': root_post['num_likes'] or 0,
        'num_shares': root_post['num_shares'] or 0,
        'num_dislikes': root_post['num_dislikes'] or 0,
        'is_root': True,
        'node_type': 'root',
        'category': 0,
        'parent_id': None
    })
    processed_posts.add(root_post_id)
    
    # 递归获取所有转发（包括转发的转发）
    def get_reposts_recursive(parent_post_id: int):
        """递归获取某个帖子的所有转发和转发的转发"""
        reposts = db_manager.execute_query("""
            SELECT p.*, u.name as user_name
            FROM post p
            JOIN user u ON p.user_id = u.user_id
            WHERE p.original_post_id = ?
        """, (parent_post_id,))
        
        for repost in reposts:
            repost_id = repost['post_id']
            
            # 避免重复处理
            if repost_id in processed_posts:
                continue
            processed_posts.add(repost_id)
            
            node_id = f"P_{repost_id}"
            parent_id = f"P_{repost['original_post_id']}"
            timestamp = parse_timestamp(repost['created_at'])
            
            nodes.append({
                'node_id': node_id,
                'post_id': repost_id,
                'user_id': repost['user_id'],
                'user_name': repost['user_name'],
                'content': repost.get('quote_content') or '[转发]',
                'created_at': repost['created_at'],
                'timestamp': timestamp,
                'num_likes': repost['num_likes'] or 0,
                'num_shares': repost['num_shares'] or 0,
                'num_dislikes': repost['num_dislikes'] or 0,
                'is_root': False,
                'node_type': 'repost',
                'category': 1,
                'parent_id': parent_id
            })
            
            links.append({
                'source': parent_id,
                'target': node_id
            })
            
            # 递归获取这个转发的转发
            get_reposts_recursive(repost_id)
    
    # 从根帖子开始递归获取所有转发
    get_reposts_recursive(root_post_id)
    
    # 获取所有相关帖子的评论（包括转发的评论）
    all_post_ids = list(processed_posts)
    if all_post_ids:
        placeholders = ','.join('?' * len(all_post_ids))
        comments = db_manager.execute_query(f"""
            SELECT c.*, u.name as user_name
            FROM comment c
            JOIN user u ON c.user_id = u.user_id
            WHERE c.post_id IN ({placeholders})
        """, tuple(all_post_ids))
        
        for comment in comments:
            node_id = f"C_{comment['comment_id']}"
            parent_id = f"P_{comment['post_id']}"
            timestamp = parse_timestamp(comment['created_at'])
            
            nodes.append({
                'node_id': node_id,
                'comment_id': comment['comment_id'],
                'post_id': comment['post_id'],
                'user_id': comment['user_id'],
                'user_name': comment['user_name'],
                'content': comment['content'] or '',
                'created_at': comment['created_at'],
                'timestamp': timestamp,
                'num_likes': comment.get('num_likes', 0),
                'num_shares': 0,
                'num_dislikes': comment.get('num_dislikes', 0),
                'is_root': False,
                'node_type': 'comment',
                'category': 2,
                'parent_id': parent_id
            })
            
            links.append({
                'source': parent_id,
                'target': node_id
            })
    
    # 为边添加时间戳信息
    node_time_map = {n['node_id']: n['timestamp'] for n in nodes}
    for link in links:
        link['source_time'] = node_time_map.get(link['source'], 0)
        link['target_time'] = node_time_map.get(link['target'], 0)
    
    # 计算时间范围
    valid_timestamps = [n['timestamp'] for n in nodes if n['timestamp'] is not None]
    if valid_timestamps:
        min_time = min(valid_timestamps)
        max_time = max(valid_timestamps)
        min_str = datetime.fromtimestamp(min_time).strftime('%Y-%m-%d %H:%M:%S')
        max_str = datetime.fromtimestamp(max_time).strftime('%Y-%m-%d %H:%M:%S')
    else:
        min_time = max_time = 0
        min_str = max_str = ''
    
    # 计算最大深度
    max_depth = calculate_tree_depth(nodes, links, root_node_id)
    
    # 定义分类
    categories = [
        {'name': '原创帖子', 'itemStyle': {'color': '#FFD700'}},
        {'name': '转发', 'itemStyle': {'color': '#FF6B6B'}},
        {'name': '评论', 'itemStyle': {'color': '#4ECDC4'}}
    ]
    
    return {
        'root_post_id': root_post_id,
        'nodes': nodes,
        'links': links,
        'total_shares': len(processed_posts) - 1 + len([n for n in nodes if n['node_id'].startswith('C_')]),
        'max_depth': max_depth,
        'timeRange': {
            'min': min_time,
            'max': max_time,
            'minStr': min_str,
            'maxStr': max_str
        },
        'categories': categories,
        'colorMap': {
            'root': '#FFD700',
            'repost': '#FF6B6B',
            'comment': '#4ECDC4'
        }
    }



def calculate_tree_depth(nodes: List[Dict], links: List[Dict], root_id: str) -> int:
    """计算树的最大深度"""
    # 构建邻接表
    children = defaultdict(list)
    for link in links:
        children[link['source']].append(link['target'])
    
    def dfs(node_id: str, depth: int) -> int:
        if node_id not in children:
            return depth
        return max(dfs(child, depth + 1) for child in children[node_id])
    
    return dfs(root_id, 0)


def build_user_network(db_manager, limit: int = 100) -> Dict[str, Any]:
    """
    构建用户关系网络图
    
    Args:
        db_manager: 数据库管理器实例
        limit: 限制节点数量
        
    Returns:
        包含节点和边的网络图数据
    """
    # 获取活跃用户（按发帖数排序）
    users = db_manager.execute_query("""
        SELECT u.user_id, u.name, u.num_followers, 
               COUNT(p.post_id) as post_count
        FROM user u
        LEFT JOIN post p ON u.user_id = p.user_id
        GROUP BY u.user_id
        ORDER BY post_count DESC
        LIMIT ?
    """, (limit,))
    
    user_ids = [u['user_id'] for u in users]
    
    # 构建节点
    nodes = []
    for user in users:
        nodes.append({
            'id': f"U_{user['user_id']}",
            'name': user['name'],
            'user_id': user['user_id'],
            'value': user['num_followers'] or 0,
            'category': 0
        })
    
    # 获取关注关系
    if user_ids:
        placeholders = ','.join('?' * len(user_ids))
        follows = db_manager.execute_query(f"""
            SELECT follower_id, followee_id
            FROM follow
            WHERE follower_id IN ({placeholders})
              AND followee_id IN ({placeholders})
        """, tuple(user_ids * 2))
        
        # 构建边
        links = []
        for follow in follows:
            links.append({
                'source': f"U_{follow['follower_id']}",
                'target': f"U_{follow['followee_id']}",
                'value': 1
            })
    else:
        links = []
    
    return {
        'nodes': nodes,
        'links': links,
        'categories': [
            {'name': '用户'}
        ]
    }


def calculate_influence_score(user_data: Dict[str, Any]) -> float:
    """
    计算用户影响力分数
    
    综合考虑：
    - 粉丝数
    - 发帖数
    - 获赞数
    - 转发数
    """
    followers = user_data.get('follower_count', 0)
    posts = user_data.get('post_count', 0)
    likes = user_data.get('total_likes', 0)
    shares = user_data.get('total_shares', 0)
    
    # 权重配置
    score = (
        math.log(followers + 1) * 3.0 +
        math.log(posts + 1) * 2.0 +
        math.log(likes + 1) * 1.5 +
        math.log(shares + 1) * 2.5
    )
    
    return round(score, 2)


def aggregate_timeline_data(
    db_manager,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    interval: str = 'hour'
) -> List[Dict[str, Any]]:
    """
    聚合时间线数据
    
    Args:
        db_manager: 数据库管理器
        start_time: 起始时间
        end_time: 结束时间
        interval: 时间间隔（hour/day）
        
    Returns:
        时间线数据点列表
    """
    # 根据interval选择时间格式
    if interval == 'hour':
        time_format = '%Y-%m-%d %H:00:00'
    elif interval == 'day':
        time_format = '%Y-%m-%d'
    else:
        time_format = '%Y-%m-%d %H:00:00'
    
    # 构建查询条件
    time_filter = ""
    params = []
    
    if start_time:
        time_filter += " AND created_at >= ?"
        params.append(start_time)
    if end_time:
        time_filter += " AND created_at <= ?"
        params.append(end_time)
    
    # 获取帖子数据
    posts = db_manager.execute_query(f"""
        SELECT 
            strftime('{time_format}', created_at) as time_slot,
            COUNT(*) as post_count,
            SUM(num_likes) as like_count,
            SUM(num_shares) as share_count
        FROM post
        WHERE 1=1 {time_filter}
        GROUP BY time_slot
        ORDER BY time_slot
    """, tuple(params))
    
    # 获取评论数据
    comments = db_manager.execute_query(f"""
        SELECT 
            strftime('{time_format}', created_at) as time_slot,
            COUNT(*) as comment_count
        FROM comment
        WHERE 1=1 {time_filter}
        GROUP BY time_slot
        ORDER BY time_slot
    """, tuple(params))
    
    # 合并数据
    timeline_dict = {}
    
    for post in posts:
        time_slot = post['time_slot']
        timeline_dict[time_slot] = {
            'timestamp': time_slot,
            'post_count': post['post_count'] or 0,
            'like_count': post['like_count'] or 0,
            'share_count': post['share_count'] or 0,
            'comment_count': 0
        }
    
    for comment in comments:
        time_slot = comment['time_slot']
        if time_slot in timeline_dict:
            timeline_dict[time_slot]['comment_count'] = comment['comment_count'] or 0
        else:
            timeline_dict[time_slot] = {
                'timestamp': time_slot,
                'post_count': 0,
                'like_count': 0,
                'share_count': 0,
                'comment_count': comment['comment_count'] or 0
            }
    
    # 返回排序后的列表
    return sorted(timeline_dict.values(), key=lambda x: x['timestamp'])


def get_trending_posts(db_manager, limit: int = 10) -> List[Dict[str, Any]]:
    """
    获取热门帖子
    
    计算热度分数 = likes * 2 + shares * 3 + comments * 1.5
    """
    posts = db_manager.execute_query("""
        SELECT 
            p.post_id,
            p.user_id,
            u.name as user_name,
            p.content,
            p.created_at,
            p.num_likes,
            p.num_shares,
            COUNT(DISTINCT c.comment_id) as num_comments,
            (p.num_likes * 2 + p.num_shares * 3 + COUNT(DISTINCT c.comment_id) * 1.5) as engagement_score
        FROM post p
        JOIN user u ON p.user_id = u.user_id
        LEFT JOIN comment c ON p.post_id = c.post_id
        WHERE p.original_post_id IS NULL  -- 只统计原创帖子
        GROUP BY p.post_id
        ORDER BY engagement_score DESC
        LIMIT ?
    """, (limit,))
    
    return [dict(post) for post in posts]


def build_all_posts_propagation(
    db_manager,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    limit: Optional[int] = None
) -> Dict[str, Any]:
    """
    构建所有帖子的传播图谱
    
    Args:
        db_manager: 数据库管理器实例
        start_time: 可选的起始时间过滤
        end_time: 可选的结束时间过滤
        limit: 可选的帖子数量限制
        
    Returns:
        包含所有帖子传播关系的图谱数据
    """
    # 构建时间过滤条件
    time_filter = ""
    params = []
    
    if start_time:
        time_filter += " AND p.created_at >= ?"
        params.append(start_time)
    if end_time:
        time_filter += " AND p.created_at <= ?"
        params.append(end_time)
    
    # 获取所有原创帖子
    limit_clause = f" LIMIT {limit}" if limit else ""
    root_posts_query = f"""
        SELECT p.*, u.name as user_name
        FROM post p
        JOIN user u ON p.user_id = u.user_id
        WHERE p.original_post_id IS NULL {time_filter}
        ORDER BY p.created_at DESC{limit_clause}
    """
    root_posts = db_manager.execute_query(root_posts_query, tuple(params))
    
    if not root_posts:
        return {
            'nodes': [],
            'links': [],
            'total_shares': 0,
            'max_depth': 0,
            'timeRange': {'min': 0, 'max': 0, 'minStr': '', 'maxStr': ''},
            'categories': []
        }
    
    root_post_ids = [p['post_id'] for p in root_posts]
    
    # 递归获取所有转发（包括转发的转发）
    all_post_ids = set(root_post_ids)
    processed_posts = set(root_post_ids)
    
    def get_reposts_recursive(parent_post_ids):
        """递归获取帖子的所有转发"""
        if not parent_post_ids:
            return []
        
        placeholders = ','.join('?' * len(parent_post_ids))
        reposts = db_manager.execute_query(f"""
            SELECT p.*, u.name as user_name
            FROM post p
            JOIN user u ON p.user_id = u.user_id
            WHERE p.original_post_id IN ({placeholders})
        """, tuple(parent_post_ids))
        
        if not reposts:
            return []
        
        # 收集这一层的转发ID
        current_layer_ids = []
        for repost in reposts:
            repost_id = repost['post_id']
            if repost_id not in processed_posts:
                processed_posts.add(repost_id)
                all_post_ids.add(repost_id)
                current_layer_ids.append(repost_id)
        
        # 递归获取下一层转发
        next_layer = get_reposts_recursive(current_layer_ids)
        return reposts + next_layer
    
    # 获取所有层级的转发
    reposts = get_reposts_recursive(root_post_ids)
    
    # 获取所有相关的评论（包括原创帖和所有转发的评论）
    all_post_ids_list = list(all_post_ids)
    if all_post_ids_list:
        placeholders = ','.join('?' * len(all_post_ids_list))
        comments = db_manager.execute_query(f"""
            SELECT c.*, u.name as user_name
            FROM comment c
            JOIN user u ON c.user_id = u.user_id
            WHERE c.post_id IN ({placeholders})
        """, tuple(all_post_ids_list))
    else:
        comments = []

    
    # 构建节点和边
    nodes = []
    links = []
    
    # 添加所有原创帖子节点
    for root_post in root_posts:
        node_id = f"P_{root_post['post_id']}"
        timestamp = parse_timestamp(root_post['created_at'])
        
        nodes.append({
            'node_id': node_id,
            'post_id': root_post['post_id'],
            'user_id': root_post['user_id'],
            'user_name': root_post['user_name'],
            'content': root_post['content'] or '',
            'created_at': root_post['created_at'],
            'timestamp': timestamp,
            'num_likes': root_post['num_likes'] or 0,
            'num_shares': root_post['num_shares'] or 0,
            'num_dislikes': root_post['num_dislikes'] or 0,
            'is_root': True,
            'node_type': 'root',
            'category': 0,
            'parent_id': None
        })
    
    # 添加转发节点
    for repost in reposts:
        node_id = f"P_{repost['post_id']}"
        parent_id = f"P_{repost['original_post_id']}"
        timestamp = parse_timestamp(repost['created_at'])
        
        nodes.append({
            'node_id': node_id,
            'post_id': repost['post_id'],
            'user_id': repost['user_id'],
            'user_name': repost['user_name'],
            'content': repost.get('quote_content') or '[转发]',
            'created_at': repost['created_at'],
            'timestamp': timestamp,
            'num_likes': repost['num_likes'] or 0,
            'num_shares': repost['num_shares'] or 0,
            'num_dislikes': repost['num_dislikes'] or 0,
            'is_root': False,
            'node_type': 'repost',
            'category': 1,
            'parent_id': parent_id
        })
        
        links.append({
            'source': parent_id,
            'target': node_id
        })
    
    # 添加评论节点
    for comment in comments:
        node_id = f"C_{comment['comment_id']}"
        parent_id = f"P_{comment['post_id']}"
        timestamp = parse_timestamp(comment['created_at'])
        
        nodes.append({
            'node_id': node_id,
            'comment_id': comment['comment_id'],
            'post_id': comment['post_id'],
            'user_id': comment['user_id'],
            'user_name': comment['user_name'],
            'content': comment['content'] or '',
            'created_at': comment['created_at'],
            'timestamp': timestamp,
            'num_likes': comment.get('num_likes', 0),
            'num_shares': 0,
            'num_dislikes': comment.get('num_dislikes', 0),
            'is_root': False,
            'node_type': 'comment',
            'category': 2,
            'parent_id': parent_id
        })
        
        links.append({
            'source': parent_id,
            'target': node_id
        })
    
    # 为边添加时间戳信息
    node_time_map = {n['node_id']: n['timestamp'] for n in nodes}
    for link in links:
        link['source_time'] = node_time_map.get(link['source'], 0)
        link['target_time'] = node_time_map.get(link['target'], 0)
    
    # 计算时间范围
    valid_timestamps = [n['timestamp'] for n in nodes if n['timestamp'] is not None]
    if valid_timestamps:
        min_time = min(valid_timestamps)
        max_time = max(valid_timestamps)
        min_str = datetime.fromtimestamp(min_time).strftime('%Y-%m-%d %H:%M:%S')
        max_str = datetime.fromtimestamp(max_time).strftime('%Y-%m-%d %H:%M:%S')
    else:
        min_time = max_time = 0
        min_str = max_str = ''
    
    # 计算最大深度（针对每个根帖子）
    max_depth = 0
    for root_post in root_posts:
        root_node_id = f"P_{root_post['post_id']}"
        depth = calculate_tree_depth(nodes, links, root_node_id)
        max_depth = max(max_depth, depth)
    
    # 定义分类
    categories = [
        {'name': '原创帖子', 'itemStyle': {'color': '#FFD700'}},
        {'name': '转发', 'itemStyle': {'color': '#FF6B6B'}},
        {'name': '评论', 'itemStyle': {'color': '#4ECDC4'}}
    ]
    
    return {
        'nodes': nodes,
        'links': links,
        'total_shares': len(reposts) + len(comments),
        'total_roots': len(root_posts),
        'max_depth': max_depth,
        'timeRange': {
            'min': min_time,
            'max': max_time,
            'minStr': min_str,
            'maxStr': max_str
        },
        'categories': categories,
        'colorMap': {
            'root': '#FFD700',
            'repost': '#FF6B6B',
            'comment': '#4ECDC4'
        }
    }


# ========== 网络分析函数 ==========

def build_relationship_network(db_manager, limit: int = 100, min_followers: int = 0) -> Dict[str, Any]:
    """
    构建用户关系网络图
    
    Args:
        db_manager: 数据库管理器实例
        limit: 节点数量限制
        min_followers: 最小粉丝数筛选
        
    Returns:
        包含节点和边的关系网络数据
    """
    # 获取活跃用户（按粉丝数和发帖数排序）
    users = db_manager.execute_query("""
        SELECT 
            u.user_id, 
            u.name, 
            u.user_name,
            u.num_followers, 
            u.num_followings,
            COUNT(DISTINCT p.post_id) as post_count,
            COALESCE(SUM(p.num_likes), 0) as total_likes
        FROM user u
        LEFT JOIN post p ON u.user_id = p.user_id
        WHERE u.num_followers >= ?
        GROUP BY u.user_id
        ORDER BY u.num_followers DESC, post_count DESC
        LIMIT ?
    """, (min_followers, limit))
    
    if not users:
        return {
            'nodes': [],
            'links': [],
            'categories': [],
            'stats': {}
        }
    
    user_ids = [u['user_id'] for u in users]
    user_id_set = set(user_ids)
    
    # 构建节点
    nodes = []
    max_followers = max(u['num_followers'] or 0 for u in users)
    min_follower_count = min(u['num_followers'] or 0 for u in users)
    
    for user in users:
        # 计算节点大小（基于粉丝数）
        follower_count = user['num_followers'] or 0
        if max_followers > min_follower_count:
            normalized_size = 20 + (follower_count - min_follower_count) / (max_followers - min_follower_count) * 60
        else:
            normalized_size = 40
        
        nodes.append({
            'id': f"U_{user['user_id']}",
            'name': f"U_{user['user_id']}",  # Ensure name matches link source/target
            'display_name': user['name'],     # Store display name for UI
            'user_id': user['user_id'],
            'user_name': user['user_name'],
            'value': follower_count,
            'symbolSize': normalized_size,
            'category': 0,
            'followers': follower_count,
            'followings': user['num_followings'] or 0,
            'post_count': user['post_count'] or 0,
            'total_likes': user['total_likes'] or 0
        })
    
    # 获取关注关系（只包含在用户列表中的关系）
    if user_ids:
        placeholders = ','.join('?' * len(user_ids))
        follows = db_manager.execute_query(f"""
            SELECT follower_id, followee_id
            FROM follow
            WHERE follower_id IN ({placeholders})
              AND followee_id IN ({placeholders})
        """, tuple(user_ids * 2))
        
        # 构建边
        links = []
        for follow in follows:
            if follow['follower_id'] in user_id_set and follow['followee_id'] in user_id_set:
                links.append({
                    'source': f"U_{follow['follower_id']}",
                    'target': f"U_{follow['followee_id']}",
                    'value': 1
                })
    else:
        links = []
    
    # 计算网络统计
    stats = {
        'total_nodes': len(nodes),
        'total_edges': len(links),
        'avg_degree': len(links) * 2 / len(nodes) if len(nodes) > 0 else 0,
        'density': len(links) / (len(nodes) * (len(nodes) - 1)) if len(nodes) > 1 else 0
    }
    
    return {
        'nodes': nodes,
        'links': links,
        'categories': [
            {'name': '用户', 'itemStyle': {'color': '#5470c6'}}
        ],
        'stats': stats
    }












