"""
可视分析 API (Visual Analytics)
================================

面向「分析师主导」的可视分析接口，不再是「一个图表一个端点」，而是：
  - /catalog   告诉前端有哪些可选维度与度量
  - /explore   通用聚合查询：用户选什么维度，就按什么维度 group by
  - /lifecycle 舆情事件生命周期 + 各阶段维度变化      （需求 1）
  - /key-groups 关键群体识别，支持任意条件组合筛选     （需求 2）
  - /key-users  关键用户识别（意见领袖/发起者/活跃者） （需求 3）
  - /user/{id}  个体下钻

所有接口依赖 ETL 产出的 va_* 表；未构建时返回 needs_build 标记。
"""
import os
import json
import sqlite3
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Body

from database.db_manager import get_db_manager
from etl.build_analysis_db import build_analysis_db, has_analysis_tables

router = APIRouter(prefix="/api/va", tags=["visual-analytics"])


# ---------------------------------------------------------------------------
# 维度 / 度量定义  —— 可视分析的「可分析空间」
# 每个维度: id -> (显示名, 类型, SQL表达式, 所属分组)
# 表达式基于以下 JOIN:
#   va_event_fact e
#   LEFT JOIN va_user_dim u ON e.actor_id = u.user_id
#   LEFT JOIN va_post_dim p ON e.post_id  = p.post_id
# ---------------------------------------------------------------------------
DIMENSIONS = {
    "user.community":         ("社群",       "categorical", "e.community_id",   "用户维度"),
    "user.influence_tier":    ("影响力分层", "ordinal",     "u.influence_tier", "用户维度"),
    "user.behavior_label":    ("行为标签",   "categorical", "u.behavior_label", "用户维度"),
    "user.role":              ("关键角色",   "categorical", "u.role",           "用户维度"),
    "user.gender":            ("性别",       "categorical", "u.gender",         "用户维度"),
    "user.region":            ("地区",       "categorical", "u.region",         "用户维度"),
    "user.profession":        ("职业",       "categorical", "u.profession",     "用户维度"),
    "user.account_type":      ("账号类型",   "categorical", "u.account_type",   "用户维度"),
    "user.content_preference":("内容偏好",   "categorical", "u.content_preference", "用户维度"),
    "post.topic":             ("话题",       "categorical", "e.topic",          "内容维度"),
    "post.sentiment_class":   ("情感极性",   "categorical", "e.sentiment_class","内容维度"),
    "post.stance":            ("立场",       "categorical", "p.stance",         "内容维度"),
    "event.action_type":      ("行为类型",   "categorical", "e.action_type",    "行为维度"),
    "event.is_rec_driven":    ("推荐驱动",   "categorical", "e.is_rec_driven",  "行为维度"),
    "time.phase":             ("舆情阶段",   "ordinal",     "e.phase",          "时间维度"),
    "time.hour":              ("时间(小时)", "temporal",    "substr(e.ts,1,13)","时间维度"),
}

MEASURES = {
    "count_events":  ("行为数",       "COUNT(*)"),
    "count_users":   ("独立用户数",   "COUNT(DISTINCT e.actor_id)"),
    "count_posts":   ("涉及内容数",   "COUNT(DISTINCT e.post_id)"),
    "sentiment_avg": ("平均情感分",   "AVG(e.sentiment_score)"),
    "pos_ratio":     ("正面占比",     "AVG(CASE WHEN e.sentiment_class='正面' THEN 1.0 ELSE 0.0 END)"),
    "neg_ratio":     ("负面占比",     "AVG(CASE WHEN e.sentiment_class='负面' THEN 1.0 ELSE 0.0 END)"),
    "rec_ratio":     ("推荐驱动占比", "AVG(CAST(e.is_rec_driven AS REAL))"),
}

# 序数维度的固定排序
ORDINAL_ORDER = {
    "time.phase": ["潜伏期", "爆发期", "扩散期", "衰退期"],
    "user.influence_tier": ["头部", "腰部", "长尾"],
}

BASE_JOIN = (
    "FROM va_event_fact e "
    "LEFT JOIN va_user_dim u ON e.actor_id = u.user_id "
    "LEFT JOIN va_post_dim p ON e.post_id  = p.post_id"
)

# 可作为「群体划分」的用户维度（关键群体识别用）
GROUP_DIMS = {
    "user.community":         ("社群",       "community_id"),
    "user.influence_tier":    ("影响力分层", "influence_tier"),
    "user.behavior_label":    ("行为标签",   "behavior_label"),
    "user.role":              ("关键角色",   "role"),
    "user.gender":            ("性别",       "gender"),
    "user.region":            ("地区",       "region"),
    "user.profession":        ("职业",       "profession"),
    "user.account_type":      ("账号类型",   "account_type"),
    "user.content_preference":("内容偏好",   "content_preference"),
}


# ---------------------------------------------------------------------------
# 公共工具
# ---------------------------------------------------------------------------
def _db_path():
    return get_db_manager().db_path


def _conn():
    c = sqlite3.connect(_db_path())
    c.row_factory = sqlite3.Row
    return c


def _require_built():
    if not has_analysis_tables(_db_path()):
        raise HTTPException(status_code=409,
                            detail="分析表未构建，请先调用 POST /api/va/build")


def _q(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    cols = [c[0] for c in cur.description] if cur.description else []
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def _build_where(filters, extra_clauses=None):
    """
    把 filters [{dim, values}] 编译成 WHERE 子句片段 + 参数。
    只接受白名单内的维度，值用占位符参数化，杜绝注入。
    extra_clauses: 额外的原始条件（不含参数），例如 'e.ts IS NOT NULL'。
    """
    clauses, params = [], []
    for f in filters or []:
        dim = f.get("dim")
        values = f.get("values") or []
        if dim not in DIMENSIONS or not values:
            continue
        expr = DIMENSIONS[dim][2]
        placeholders = ",".join("?" * len(values))
        clauses.append(f"{expr} IN ({placeholders})")
        params.extend(values)
    for c in (extra_clauses or []):
        clauses.append(c)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return where, params


def _sort_values(dim_id, values):
    """对序数维度按预定义顺序排序，其余按出现顺序/字典序。"""
    if dim_id in ORDINAL_ORDER:
        order = ORDINAL_ORDER[dim_id]
        return sorted(values, key=lambda v: order.index(v) if v in order else 999)
    return values


# ---------------------------------------------------------------------------
# 1. 状态 / 构建
# ---------------------------------------------------------------------------
@router.get("/status")
async def va_status():
    """返回当前数据库的分析层构建状态。"""
    path = _db_path()
    built = has_analysis_tables(path)
    info = {"db_path": path, "db_name": os.path.basename(path), "built": built}
    if built:
        try:
            conn = _conn()
            meta = {r["key"]: r["value"] for r in _q(conn, "SELECT key,value FROM va_meta")}
            conn.close()
            info["built_at"] = meta.get("built_at")
            info["counts"] = json.loads(meta.get("counts", "{}"))
            info["phases"] = json.loads(meta.get("phases", "[]"))
        except Exception as e:
            info["meta_error"] = str(e)
    return info


@router.post("/build")
async def va_build(profile_json: Optional[str] = Body(None, embed=True)):
    """对当前数据库构建/重建 va_* 分析表。"""
    path = _db_path()
    # 自动寻找同目录或 weibo_test 下的画像 JSON（可选增强）
    pj = profile_json
    if not pj:
        guess = os.path.join(os.path.dirname(path),
                             "top100_users_complete_data_post_followers.json")
        if os.path.exists(guess):
            pj = guess
    try:
        result = build_analysis_db(path, pj, verbose=True)
        return {"success": True, "result": result}
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"构建失败: {e}")


# ---------------------------------------------------------------------------
# 2. 维度目录
# ---------------------------------------------------------------------------
@router.get("/catalog")
async def va_catalog():
    """返回可分析空间：所有维度（含取值域）与度量。"""
    _require_built()
    conn = _conn()
    dims = []
    for did, (name, dtype, expr, group) in DIMENSIONS.items():
        values = []
        if dtype in ("categorical", "ordinal"):
            try:
                rows = _q(conn, f"SELECT DISTINCT {expr} AS v {BASE_JOIN} "
                                f"WHERE {expr} IS NOT NULL ORDER BY v")
                values = _sort_values(did, [r["v"] for r in rows])
            except Exception:
                values = []
        dims.append({"id": did, "name": name, "type": dtype,
                     "group": group, "values": values})
    conn.close()
    measures = [{"id": mid, "name": m[0]} for mid, m in MEASURES.items()]
    groups = [{"id": gid, "name": g[0]} for gid, g in GROUP_DIMS.items()]
    return {"dimensions": dims, "measures": measures, "group_dims": groups,
            "phase_order": ORDINAL_ORDER["time.phase"]}


# ---------------------------------------------------------------------------
# 3. 通用聚合查询
# ---------------------------------------------------------------------------
@router.post("/explore")
async def va_explore(spec: dict = Body(...)):
    """
    通用维度聚合。请求体 spec:
      {
        "rows":   ["维度id", ...],   # 1~2 个，用于 group by 的「行」
        "col":    "维度id" | null,   # 可选，用于交叉的「列」
        "measure":"度量id",
        "filters":[{"dim":"维度id","values":[...]}],
        "limit":  int
      }
    返回 tidy 记录列表，前端据维度类型自动选图。
    """
    _require_built()
    rows = [d for d in (spec.get("rows") or []) if d in DIMENSIONS][:2]
    col = spec.get("col") if spec.get("col") in DIMENSIONS else None
    measure = spec.get("measure") if spec.get("measure") in MEASURES else "count_events"
    limit = min(int(spec.get("limit", 500)), 2000)
    if not rows and not col:
        raise HTTPException(400, "至少选择一个行维度或列维度")

    select_dims = []
    group_exprs = []
    for d in rows:
        select_dims.append((d, DIMENSIONS[d][2]))
        group_exprs.append(DIMENSIONS[d][2])
    if col:
        select_dims.append((col, DIMENSIONS[col][2]))
        group_exprs.append(DIMENSIONS[col][2])

    select_sql = ", ".join(f"{expr} AS \"{d}\"" for d, expr in select_dims)
    measure_sql = f"{MEASURES[measure][1]} AS value"
    where, params = _build_where(spec.get("filters"))
    sql = (f"SELECT {select_sql}, {measure_sql} {BASE_JOIN}{where} "
           f"GROUP BY {', '.join(group_exprs)} "
           f"ORDER BY value DESC LIMIT {limit}")

    conn = _conn()
    try:
        data = _q(conn, sql, tuple(params))
    finally:
        conn.close()

    return {
        "rows": rows, "col": col,
        "measure": {"id": measure, "name": MEASURES[measure][0]},
        "dimensions": {d: {"name": DIMENSIONS[d][0], "type": DIMENSIONS[d][1]}
                       for d, _ in select_dims},
        "data": data,
        "chart_hint": _chart_hint(rows, col),
    }


def _chart_hint(rows, col):
    """根据所选维度类型给前端一个出图建议。"""
    types = [DIMENSIONS[d][1] for d in rows] + ([DIMENSIONS[col][1]] if col else [])
    if "temporal" in types and col:
        return "stacked_area"
    if "temporal" in types:
        return "line"
    if len(rows) == 1 and col:
        return "heatmap"
    if len(rows) == 2:
        return "heatmap"
    return "bar"


# ---------------------------------------------------------------------------
# 4. 舆情生命周期  （需求 1）
# ---------------------------------------------------------------------------
@router.get("/lifecycle")
async def va_lifecycle(
    breakdown: str = Query("event.action_type", description="阶段内拆解维度"),
    filters: Optional[str] = Query(None, description="JSON 编码的 filters 数组"),
):
    """
    舆情事件生命周期：
      - phases:    四个阶段（潜伏/爆发/扩散/衰退）的边界与汇总指标
      - timeline:  逐小时的事件量与情感曲线（含 breakdown 维度堆叠）
      - snapshots: 每个阶段按 breakdown 维度的构成 + 关键指标，便于「看各阶段维度变化」
    """
    _require_built()
    if breakdown not in DIMENSIONS:
        breakdown = "event.action_type"
    bexpr = DIMENSIONS[breakdown][2]
    flt = json.loads(filters) if filters else []
    where, params = _build_where(flt)
    where_ts, params_ts = _build_where(flt, ["e.ts IS NOT NULL"])

    conn = _conn()
    try:
        meta = {r["key"]: r["value"] for r in _q(conn, "SELECT key,value FROM va_meta")}
        phases_meta = json.loads(meta.get("phases", "[]"))

        # 每阶段汇总
        phase_rows = _q(conn, f"""
            SELECT e.phase AS phase,
                   COUNT(*) AS event_count,
                   COUNT(DISTINCT e.actor_id) AS active_users,
                   COUNT(DISTINCT e.post_id) AS posts,
                   AVG(e.sentiment_score) AS avg_sentiment,
                   SUM(CASE WHEN e.sentiment_class='正面' THEN 1 ELSE 0 END) AS pos,
                   SUM(CASE WHEN e.sentiment_class='中性' THEN 1 ELSE 0 END) AS neu,
                   SUM(CASE WHEN e.sentiment_class='负面' THEN 1 ELSE 0 END) AS neg
            {BASE_JOIN}{where}
            GROUP BY e.phase
        """, tuple(params))
        phase_map = {r["phase"]: r for r in phase_rows}
        phases = []
        for pm in phases_meta:
            ph = pm["phase"]
            agg = phase_map.get(ph, {})
            phases.append({**pm, **{
                "event_count": agg.get("event_count", 0),
                "active_users": agg.get("active_users", 0),
                "posts": agg.get("posts", 0),
                "avg_sentiment": round(agg.get("avg_sentiment") or 0, 4),
                "pos": agg.get("pos", 0), "neu": agg.get("neu", 0),
                "neg": agg.get("neg", 0),
            }})

        # 逐小时时间线（总量 + 情感）
        timeline = _q(conn, f"""
            SELECT substr(e.ts,1,13) AS hour, e.phase AS phase,
                   COUNT(*) AS event_count,
                   AVG(e.sentiment_score) AS avg_sentiment,
                   SUM(CASE WHEN e.sentiment_class='正面' THEN 1 ELSE 0 END) AS pos,
                   SUM(CASE WHEN e.sentiment_class='中性' THEN 1 ELSE 0 END) AS neu,
                   SUM(CASE WHEN e.sentiment_class='负面' THEN 1 ELSE 0 END) AS neg
            {BASE_JOIN}{where_ts}
            GROUP BY hour ORDER BY hour
        """, tuple(params_ts))

        # 逐小时 × breakdown（用于堆叠流图）
        timeline_breakdown = _q(conn, f"""
            SELECT substr(e.ts,1,13) AS hour, {bexpr} AS bucket, COUNT(*) AS cnt
            {BASE_JOIN}{where_ts}
            GROUP BY hour, bucket ORDER BY hour
        """, tuple(params_ts))

        # 每阶段 × breakdown 构成（用于「各阶段维度变化」对比）
        snap = _q(conn, f"""
            SELECT e.phase AS phase, {bexpr} AS bucket, COUNT(*) AS cnt,
                   COUNT(DISTINCT e.actor_id) AS users,
                   AVG(e.sentiment_score) AS avg_sentiment
            {BASE_JOIN}{where}
            GROUP BY e.phase, bucket
        """, tuple(params))
    finally:
        conn.close()

    return {
        "breakdown": {"id": breakdown, "name": DIMENSIONS[breakdown][0]},
        "phases": phases,
        "timeline": timeline,
        "timeline_breakdown": timeline_breakdown,
        "snapshots": snap,
        "phase_order": ORDINAL_ORDER["time.phase"],
    }


# ---------------------------------------------------------------------------
# 5. 关键群体识别  （需求 2）
# ---------------------------------------------------------------------------
@router.get("/key-groups")
async def va_key_groups(
    group_by: str = Query("user.profession", description="群体划分维度"),
    filters: Optional[str] = Query(None, description="JSON 编码的 filters 数组（条件组合筛选）"),
    phase: Optional[str] = Query(None, description="限定舆情阶段"),
):
    """
    按所选用户维度切出群体，并对每个群体计算规模/活跃/影响力/情感等指标，
    给出「关键度」排名。filters 支持任意用户维度的条件组合（职业+性别+行为+...）。
    """
    _require_built()
    if group_by not in GROUP_DIMS:
        group_by = "user.profession"
    gcol = GROUP_DIMS[group_by][1]

    # 用户维度筛选：把 filters 中属于用户维度的条件作用到 va_user_dim
    flt = json.loads(filters) if filters else []
    u_clauses, u_params = [], []
    USER_COL = {  # dim id -> va_user_dim 列名
        "user.community": "community_id", "user.influence_tier": "influence_tier",
        "user.behavior_label": "behavior_label", "user.role": "role",
        "user.gender": "gender", "user.region": "region",
        "user.profession": "profession", "user.account_type": "account_type",
        "user.content_preference": "content_preference",
    }
    for f in flt:
        d, vals = f.get("dim"), f.get("values") or []
        if d in USER_COL and vals:
            ph = ",".join("?" * len(vals))
            u_clauses.append(f"{USER_COL[d]} IN ({ph})")
            u_params.extend(vals)
    u_where = (" WHERE " + " AND ".join(u_clauses)) if u_clauses else ""

    conn = _conn()
    try:
        # 群体的成员侧指标（来自 va_user_dim）
        member_rows = _q(conn, f"""
            SELECT {gcol} AS grp,
                   COUNT(*) AS members,
                   AVG(influence_score) AS avg_influence,
                   MAX(influence_score) AS max_influence,
                   SUM(activity_level) AS total_activity,
                   SUM(post_count) AS posts,
                   SUM(repost_count) AS reposts,
                   SUM(comment_count) AS comments,
                   SUM(likes_received) AS likes_received,
                   SUM(reposts_received) AS reposts_received,
                   SUM(is_opinion_leader) AS leaders,
                   SUM(is_initiator) AS initiators
            FROM va_user_dim{u_where}
            GROUP BY {gcol}
        """, tuple(u_params))

        # 群体的行为侧指标（来自事实表，可按阶段过滤）
        ev_where = ""
        ev_params = []
        if phase:
            ev_where = " WHERE e.phase = ?"
            ev_params.append(phase)
        event_rows = _q(conn, f"""
            SELECT u.{gcol} AS grp,
                   COUNT(*) AS event_count,
                   AVG(e.sentiment_score) AS avg_sentiment,
                   SUM(CASE WHEN e.sentiment_class='负面' THEN 1 ELSE 0 END) AS neg,
                   SUM(CASE WHEN e.sentiment_class='正面' THEN 1 ELSE 0 END) AS pos,
                   AVG(CAST(e.is_rec_driven AS REAL)) AS rec_ratio
            FROM va_event_fact e JOIN va_user_dim u ON e.actor_id = u.user_id
            {ev_where}
            GROUP BY u.{gcol}
        """, tuple(ev_params))
        ev_map = {r["grp"]: r for r in event_rows}
    finally:
        conn.close()

    # 合并 + 计算关键度
    groups = []
    max_members = max([r["members"] for r in member_rows], default=1) or 1
    max_act = max([r["total_activity"] or 0 for r in member_rows], default=1) or 1
    max_infl = max([r["avg_influence"] or 0 for r in member_rows], default=1) or 1
    max_event = max([(ev_map.get(r["grp"], {}).get("event_count") or 0)
                     for r in member_rows], default=1) or 1
    for r in member_rows:
        ev = ev_map.get(r["grp"], {})
        # 关键度 = 规模 × 影响力 × 活跃度 × 事件量 的归一化加权
        key_score = round(
            0.25 * (r["members"] / max_members) +
            0.30 * ((r["avg_influence"] or 0) / max_infl) +
            0.20 * ((r["total_activity"] or 0) / max_act) +
            0.25 * ((ev.get("event_count") or 0) / max_event), 4)
        groups.append({
            "group": r["grp"],
            "members": r["members"],
            "avg_influence": round(r["avg_influence"] or 0, 3),
            "max_influence": round(r["max_influence"] or 0, 3),
            "total_activity": r["total_activity"] or 0,
            "posts": r["posts"] or 0,
            "reposts": r["reposts"] or 0,
            "comments": r["comments"] or 0,
            "likes_received": r["likes_received"] or 0,
            "reposts_received": r["reposts_received"] or 0,
            "opinion_leaders": r["leaders"] or 0,
            "initiators": r["initiators"] or 0,
            "event_count": ev.get("event_count") or 0,
            "avg_sentiment": round(ev.get("avg_sentiment") or 0, 4),
            "pos": ev.get("pos") or 0, "neg": ev.get("neg") or 0,
            "rec_ratio": round(ev.get("rec_ratio") or 0, 4),
            "key_score": key_score,
        })
    groups.sort(key=lambda g: g["key_score"], reverse=True)
    return {
        "group_by": {"id": group_by, "name": GROUP_DIMS[group_by][0]},
        "phase": phase,
        "groups": groups,
        "total_groups": len(groups),
    }


# ---------------------------------------------------------------------------
# 6. 关键用户识别  （需求 3）
# ---------------------------------------------------------------------------
KEY_USER_SORTS = {
    "influence_score": "influence_score",
    "pagerank": "pagerank",
    "num_followers": "num_followers",
    "reposts_received": "reposts_received",
    "likes_received": "likes_received",
    "activity_level": "activity_level",
    "post_count": "post_count",
}


@router.get("/key-users")
async def va_key_users(
    role: str = Query("all", description="意见领袖/讨论发起者/活跃用户/普通传播者/all"),
    sort_by: str = Query("influence_score"),
    filters: Optional[str] = Query(None, description="JSON 编码的用户维度条件组合"),
    phase: Optional[str] = Query(None, description="限定该用户在某阶段有活动"),
    limit: int = Query(50, ge=1, le=500),
):
    """
    关键用户识别：按角色 + 用户维度条件组合筛选并排序。
    角色由 ETL 预先判定（意见领袖 / 讨论发起者 / 活跃用户 / 普通传播者 / 边缘用户）。
    """
    _require_built()
    sort_col = KEY_USER_SORTS.get(sort_by, "influence_score")

    clauses, params = [], []
    if role and role != "all":
        clauses.append("u.role = ?")
        params.append(role)
    flt = json.loads(filters) if filters else []
    USER_COL = {
        "user.community": "community_id", "user.influence_tier": "influence_tier",
        "user.behavior_label": "behavior_label", "user.role": "role",
        "user.gender": "gender", "user.region": "region",
        "user.profession": "profession", "user.account_type": "account_type",
        "user.content_preference": "content_preference",
    }
    for f in flt:
        d, vals = f.get("dim"), f.get("values") or []
        if d in USER_COL and vals:
            ph = ",".join("?" * len(vals))
            clauses.append(f"u.{USER_COL[d]} IN ({ph})")
            params.extend(vals)
    phase_join = ""
    if phase:
        phase_join = ("JOIN (SELECT DISTINCT actor_id FROM va_event_fact "
                      "WHERE phase = ?) ap ON ap.actor_id = u.user_id")
        params = [phase] + params
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""

    conn = _conn()
    try:
        users = _q(conn, f"""
            SELECT u.user_id, u.name, u.role, u.influence_score, u.influence_tier,
                   u.behavior_label, u.community_id, u.pagerank,
                   u.num_followers, u.num_followings, u.in_degree, u.out_degree,
                   u.post_count, u.repost_count, u.comment_count,
                   u.like_given, u.likes_received, u.reposts_received,
                   u.activity_level, u.is_opinion_leader, u.is_initiator, u.is_active,
                   u.gender, u.region, u.profession, u.account_type,
                   u.first_active, u.last_active
            FROM va_user_dim u {phase_join}{where}
            ORDER BY u.{sort_col} DESC
            LIMIT {limit}
        """, tuple(params))
        # 角色分布（不受 limit 影响，但受筛选影响）
        role_dist = _q(conn, f"""
            SELECT u.role AS role, COUNT(*) AS cnt
            FROM va_user_dim u {phase_join}{where}
            GROUP BY u.role
        """, tuple(params))
    finally:
        conn.close()

    return {
        "role": role, "sort_by": sort_col, "phase": phase,
        "users": users, "role_distribution": role_dist,
        "total": len(users),
    }


# ---------------------------------------------------------------------------
# 7. 个体下钻
# ---------------------------------------------------------------------------
@router.get("/user/{user_id}")
async def va_user_detail(user_id: int):
    """单个用户的画像 + 行为轨迹 + 内容，用于关键用户/群体的溯源下钻。"""
    _require_built()
    conn = _conn()
    try:
        profile = _q(conn, "SELECT * FROM va_user_dim WHERE user_id = ?", (user_id,))
        if not profile:
            raise HTTPException(404, "用户不存在")
        profile = profile[0]
        # 行为轨迹（逐小时 × 行为类型）
        timeline = _q(conn, """
            SELECT substr(ts,1,13) AS hour, action_type, phase, COUNT(*) AS cnt
            FROM va_event_fact WHERE actor_id = ? AND ts IS NOT NULL
            GROUP BY hour, action_type ORDER BY hour
        """, (user_id,))
        # 行为构成
        action_mix = _q(conn, """
            SELECT action_type, COUNT(*) AS cnt FROM va_event_fact
            WHERE actor_id = ? GROUP BY action_type ORDER BY cnt DESC
        """, (user_id,))
        # 阶段活跃度
        phase_activity = _q(conn, """
            SELECT phase, COUNT(*) AS cnt FROM va_event_fact
            WHERE actor_id = ? GROUP BY phase
        """, (user_id,))
        # 发布的内容
        posts = _q(conn, """
            SELECT post_id, is_repost, content, created_at, phase, topic,
                   sentiment_class, sentiment_score, num_likes, num_shares,
                   comment_count, cascade_size, cascade_depth
            FROM va_post_dim WHERE user_id = ?
            ORDER BY created_at DESC LIMIT 50
        """, (user_id,))
    finally:
        conn.close()
    return {
        "profile": profile, "timeline": timeline, "action_mix": action_mix,
        "phase_activity": phase_activity, "posts": posts,
    }
