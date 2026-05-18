"""Visual analytics endpoints backed by the va_* analysis tables."""
import logging
import os
import json
import sqlite3
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query, Body

from database.db_manager import get_db_manager
from etl.build_analysis_db import build_analysis_db, has_analysis_tables

router = APIRouter(prefix="/api/va", tags=["visual-analytics"])
logger = logging.getLogger(__name__)


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

ORDINAL_ORDER = {
    "time.phase": ["潜伏期", "爆发期", "扩散期", "衰退期"],
    "user.influence_tier": ["头部", "腰部", "长尾"],
}

BASE_JOIN = (
    "FROM va_event_fact e "
    "LEFT JOIN va_user_dim u ON e.actor_id = u.user_id "
    "LEFT JOIN va_post_dim p ON e.post_id  = p.post_id"
)

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

USER_COLUMNS = {
    "user.community": "community_id",
    "user.influence_tier": "influence_tier",
    "user.behavior_label": "behavior_label",
    "user.role": "role",
    "user.gender": "gender",
    "user.region": "region",
    "user.profession": "profession",
    "user.account_type": "account_type",
    "user.content_preference": "content_preference",
}


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
    if dim_id in ORDINAL_ORDER:
        order = ORDINAL_ORDER[dim_id]
        return sorted(values, key=lambda v: order.index(v) if v in order else 999)
    return values


def _parse_filters(filters):
    return json.loads(filters) if filters else []


def _build_user_where(filters, table_alias=""):
    prefix = f"{table_alias}." if table_alias else ""
    clauses, params = [], []
    for item in filters or []:
        dim = item.get("dim")
        values = item.get("values") or []
        if dim in USER_COLUMNS and values:
            placeholders = ",".join("?" * len(values))
            clauses.append(f"{prefix}{USER_COLUMNS[dim]} IN ({placeholders})")
            params.extend(values)
    return (" WHERE " + " AND ".join(clauses)) if clauses else "", params


def _round(value, digits=4):
    return round(value, digits) if value is not None else None


def _safe_lift(num, den):
    if not den:
        return None
    return round(num / den, 3)


@router.get("/status")
async def va_status():
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
    path = _db_path()
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
        logger.exception("Failed to build visual analytics tables")
        raise HTTPException(status_code=500, detail=f"构建失败: {e}")


@router.get("/catalog")
async def va_catalog():
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


@router.post("/explore")
async def va_explore(spec: dict = Body(...)):
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


@router.get("/lifecycle")
async def va_lifecycle(
    breakdown: str = Query("event.action_type", description="阶段内拆解维度"),
    filters: Optional[str] = Query(None, description="JSON 编码的 filters 数组"),
):
    _require_built()
    if breakdown not in DIMENSIONS:
        breakdown = "event.action_type"
    bexpr = DIMENSIONS[breakdown][2]
    flt = _parse_filters(filters)
    where, params = _build_where(flt)
    where_ts, params_ts = _build_where(flt, ["e.ts IS NOT NULL"])

    conn = _conn()
    try:
        meta = {r["key"]: r["value"] for r in _q(conn, "SELECT key,value FROM va_meta")}
        phases_meta = json.loads(meta.get("phases", "[]"))

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

        timeline_breakdown = _q(conn, f"""
            SELECT substr(e.ts,1,13) AS hour, {bexpr} AS bucket, COUNT(*) AS cnt
            {BASE_JOIN}{where_ts}
            GROUP BY hour, bucket ORDER BY hour
        """, tuple(params_ts))

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


@router.get("/lifecycle/compare")
async def va_lifecycle_compare(
    phase_a: str = Query(..., description="参照阶段（基线）"),
    phase_b: str = Query(..., description="对比阶段"),
    breakdown: str = Query("event.action_type", description="拆解维度"),
    filters: Optional[str] = Query(None, description="JSON 条件组合"),
):
    _require_built()
    if breakdown not in DIMENSIONS:
        breakdown = "event.action_type"
    bexpr = DIMENSIONS[breakdown][2]
    base_filters = _parse_filters(filters)

    def fetch_phase(phase):
        f2 = list(base_filters) + [{"dim": "time.phase", "values": [phase]}]
        where, params = _build_where(f2)
        conn = _conn()
        try:
            agg = _q(conn, f"""
                SELECT COUNT(*) AS event_count,
                       COUNT(DISTINCT e.actor_id) AS active_users,
                       COUNT(DISTINCT e.post_id) AS posts,
                       AVG(e.sentiment_score) AS avg_sentiment,
                       SUM(CASE WHEN e.sentiment_class='正面' THEN 1 ELSE 0 END) AS pos,
                       SUM(CASE WHEN e.sentiment_class='中性' THEN 1 ELSE 0 END) AS neu,
                       SUM(CASE WHEN e.sentiment_class='负面' THEN 1 ELSE 0 END) AS neg,
                       AVG(CAST(e.is_rec_driven AS REAL)) AS rec_ratio
                {BASE_JOIN}{where}
            """, tuple(params))[0]
            brk = _q(conn, f"""
                SELECT {bexpr} AS bucket, COUNT(*) AS cnt,
                       COUNT(DISTINCT e.actor_id) AS users,
                       AVG(e.sentiment_score) AS avg_sentiment
                {BASE_JOIN}{where}
                GROUP BY bucket
            """, tuple(params))
        finally:
            conn.close()
        return agg, brk

    agg_a, brk_a = fetch_phase(phase_a)
    agg_b, brk_b = fetch_phase(phase_b)
    total_a = agg_a["event_count"] or 1
    total_b = agg_b["event_count"] or 1

    def _norm_agg(a, total):
        return {
            "event_count": a["event_count"] or 0,
            "active_users": a["active_users"] or 0,
            "posts": a["posts"] or 0,
            "avg_sentiment": _round(a["avg_sentiment"] or 0),
            "pos": a["pos"] or 0, "neu": a["neu"] or 0, "neg": a["neg"] or 0,
            "pos_ratio": _round((a["pos"] or 0) / total),
            "neg_ratio": _round((a["neg"] or 0) / total),
            "rec_ratio": _round(a["rec_ratio"] or 0),
        }

    ma = {r["bucket"]: r for r in brk_a}
    mb = {r["bucket"]: r for r in brk_b}
    buckets = sorted(set(list(ma.keys()) + list(mb.keys())), key=lambda x: str(x))
    comparison = []
    for b in buckets:
        ca = (ma.get(b) or {}).get("cnt") or 0
        cb = (mb.get(b) or {}).get("cnt") or 0
        ra = ca / total_a
        rb = cb / total_b
        lift = (rb / ra) if ra > 0 else None
        comparison.append({
            "bucket": b,
            "count_a": ca, "count_b": cb,
            "ratio_a": _round(ra), "ratio_b": _round(rb),
            "lift": _round(lift, 3),
            "delta_count": cb - ca,
            "delta_ratio": _round(rb - ra),
        })
    comparison.sort(key=lambda x: abs((x["lift"] or 1) - 1), reverse=True)

    return {
        "phase_a": {"name": phase_a, **_norm_agg(agg_a, total_a)},
        "phase_b": {"name": phase_b, **_norm_agg(agg_b, total_b)},
        "breakdown": {"id": breakdown, "name": DIMENSIONS[breakdown][0]},
        "comparison": comparison,
        "phase_order": ORDINAL_ORDER["time.phase"],
    }


@router.get("/key-groups")
async def va_key_groups(
    group_by: str = Query("user.profession", description="群体划分维度"),
    filters: Optional[str] = Query(None, description="JSON 编码的 filters 数组（条件组合筛选）"),
    phase: Optional[str] = Query(None, description="限定舆情阶段"),
):
    _require_built()
    if group_by not in GROUP_DIMS:
        group_by = "user.profession"
    gcol = GROUP_DIMS[group_by][1]

    flt = _parse_filters(filters)
    u_where, u_params = _build_user_where(flt)

    conn = _conn()
    try:
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

    total_members = sum(g["members"] for g in groups) or 1
    total_events = sum(g["event_count"] for g in groups) or 1
    total_pos = sum(g["pos"] for g in groups) or 0
    total_neg = sum(g["neg"] for g in groups) or 0
    total_recw = sum((g["rec_ratio"] or 0) * (g["event_count"] or 0) for g in groups)
    total_sentw = sum((g["avg_sentiment"] or 0) * (g["event_count"] or 0) for g in groups)
    total_inflw = sum((g["avg_influence"] or 0) * (g["members"] or 0) for g in groups)

    base_events_per_member = total_events / total_members
    base_pos_ratio         = (total_pos / total_events) if total_events else 0
    base_neg_ratio         = (total_neg / total_events) if total_events else 0
    base_rec_ratio         = (total_recw / total_events) if total_events else 0
    base_sentiment         = (total_sentw / total_events) if total_events else 0
    base_influence         = (total_inflw / total_members) if total_members else 0

    for g in groups:
        epm = (g["event_count"] / g["members"]) if g["members"] else 0
        pr  = (g["pos"] / g["event_count"]) if g["event_count"] else 0
        nr  = (g["neg"] / g["event_count"]) if g["event_count"] else 0
        g["events_per_member"]    = round(epm, 3)
        g["pos_ratio"]            = round(pr, 4)
        g["neg_ratio"]            = round(nr, 4)
        g["lift_events_per_member"] = _safe_lift(epm, base_events_per_member)
        g["lift_pos_ratio"]         = _safe_lift(pr,  base_pos_ratio)
        g["lift_neg_ratio"]         = _safe_lift(nr,  base_neg_ratio)
        g["lift_rec_ratio"]         = _safe_lift(g["rec_ratio"], base_rec_ratio)
        g["lift_influence"]         = _safe_lift(g["avg_influence"], base_influence)
        g["sentiment_delta"]        = round((g["avg_sentiment"] or 0) - base_sentiment, 4)

    baseline = {
        "events_per_member": round(base_events_per_member, 3),
        "pos_ratio":         round(base_pos_ratio, 4),
        "neg_ratio":         round(base_neg_ratio, 4),
        "rec_ratio":         round(base_rec_ratio, 4),
        "avg_influence":     round(base_influence, 3),
        "avg_sentiment":     round(base_sentiment, 4),
        "total_members":     total_members,
        "total_events":      total_events,
        "total_groups":      len(groups),
    }

    return {
        "group_by": {"id": group_by, "name": GROUP_DIMS[group_by][0]},
        "phase": phase,
        "groups": groups,
        "total_groups": len(groups),
        "baseline": baseline,
    }


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
    _require_built()
    sort_col = KEY_USER_SORTS.get(sort_by, "influence_score")

    clauses, params = [], []
    if role and role != "all":
        clauses.append("u.role = ?")
        params.append(role)

    filter_where, filter_params = _build_user_where(_parse_filters(filters), table_alias="u")
    if filter_where:
        clauses.append(filter_where.removeprefix(" WHERE "))
        params.extend(filter_params)

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


@router.get("/user/{user_id}")
async def va_user_detail(user_id: int):
    _require_built()
    conn = _conn()
    try:
        profile = _q(conn, "SELECT * FROM va_user_dim WHERE user_id = ?", (user_id,))
        if not profile:
            raise HTTPException(404, "用户不存在")
        profile = profile[0]
        timeline = _q(conn, """
            SELECT substr(ts,1,13) AS hour, action_type, phase, COUNT(*) AS cnt
            FROM va_event_fact WHERE actor_id = ? AND ts IS NOT NULL
            GROUP BY hour, action_type ORDER BY hour
        """, (user_id,))
        action_mix = _q(conn, """
            SELECT action_type, COUNT(*) AS cnt FROM va_event_fact
            WHERE actor_id = ? GROUP BY action_type ORDER BY cnt DESC
        """, (user_id,))
        phase_activity = _q(conn, """
            SELECT phase, COUNT(*) AS cnt FROM va_event_fact
            WHERE actor_id = ? GROUP BY phase
        """, (user_id,))
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


@router.get("/user/{user_id}/influence-path")
async def va_user_influence_path(user_id: int):
    _require_built()
    conn = _conn()
    try:
        prof = _q(conn, "SELECT user_id, name FROM va_user_dim WHERE user_id=?", (user_id,))
        if not prof:
            raise HTTPException(404, "用户不存在")
        rows = _q(conn, """
            SELECT e.ts, e.actor_id AS src_user_id, e.action_type, e.post_id,
                   e.phase, su.name AS src_name, su.role AS src_role,
                   su.influence_score AS src_influence,
                   su.num_followers   AS src_followers,
                   su.influence_tier  AS src_tier
            FROM va_event_fact e
            JOIN va_post_dim p ON e.post_id = p.post_id
            LEFT JOIN va_user_dim su ON e.actor_id = su.user_id
            WHERE p.user_id = ?
              AND e.actor_id != ?
              AND e.ts IS NOT NULL
              AND e.action_type IN ('repost','comment','like','转发','评论','点赞')
            ORDER BY e.ts ASC
        """, (user_id, user_id))
    finally:
        conn.close()

    ZH2EN = {"转发": "repost", "评论": "comment", "点赞": "like"}
    cum_r = cum_c = cum_l = 0
    path = []
    src_agg = {}
    for r in rows:
        a = ZH2EN.get(r["action_type"], r["action_type"])
        if   a == "repost":  cum_r += 1
        elif a == "comment": cum_c += 1
        elif a == "like":    cum_l += 1
        path.append({
            "ts": r["ts"], "action_type": a, "phase": r["phase"],
            "post_id": r["post_id"],
            "src_user_id": r["src_user_id"], "src_name": r["src_name"],
            "src_role": r["src_role"], "src_influence": r["src_influence"],
            "src_followers": r["src_followers"], "src_tier": r["src_tier"],
            "cum_reposts": cum_r, "cum_comments": cum_c, "cum_likes": cum_l,
        })
        sk = r["src_user_id"]
        if sk not in src_agg:
            src_agg[sk] = {
                "src_user_id": sk, "src_name": r["src_name"], "src_role": r["src_role"],
                "src_influence": r["src_influence"], "src_followers": r["src_followers"],
                "src_tier": r["src_tier"],
                "repost": 0, "comment": 0, "like": 0, "total": 0,
            }
        if a in ("repost", "comment", "like"):
            src_agg[sk][a] += 1
        src_agg[sk]["total"] += 1

    top_sources = sorted(src_agg.values(), key=lambda x: x["repost"] * 3 + x["comment"] * 2 + x["like"],
                         reverse=True)[:20]

    return {
        "user_id": user_id, "name": prof[0]["name"],
        "path": path, "total": len(path),
        "totals": {"reposts": cum_r, "comments": cum_c, "likes": cum_l},
        "top_sources": top_sources,
    }
