"""
build_dashboard_data.py

Read weibo_sim_qwen_huawei.db and produce a single self-contained HTML dashboard
demonstrating 17 new visualizations targeting 10k-scale social simulation data.

Run:  python build_dashboard_data.py
Output: ./dashboard.html  (open in browser)
"""

from __future__ import annotations
import sqlite3, json, re, math, os, sys
from collections import defaultdict, Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import networkx as nx
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
try:
    import networkx.algorithms.community as nx_comm
except ImportError:
    nx_comm = None

DB = r"C:\Users\WangKengyi\oasis_simulation\weibo_test\weibo_sim_qwen_huawei.db"
OUT_HTML = Path(__file__).parent / "dashboard.html"
HTML_TEMPLATE = Path(__file__).parent / "dashboard_template.html"

ACTION_TYPES = [
    "refresh", "do_nothing", "create_comment", "like_post", "repost",
    "follow", "search_user", "create_post", "search_posts", "trend",
]


# ---------- helpers ----------
def parse_ts(s: str | None) -> int | None:
    if not s:
        return None
    s = str(s)
    try:
        if "." in s:
            s = s.split(".")[0]
        return int(datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timestamp())
    except Exception:
        return None


def safe_log(x: float) -> float:
    return math.log(max(x, 1e-9))


# ---------- A. KPI ----------
def compute_kpi(conn):
    cur = conn.cursor()
    def cnt(q, p=()):
        cur.execute(q, p)
        return cur.fetchone()[0]
    total_users = cnt("SELECT COUNT(*) FROM user")
    total_posts = cnt("SELECT COUNT(*) FROM post")
    original = cnt("SELECT COUNT(*) FROM post WHERE original_post_id IS NULL")
    repost = cnt("SELECT COUNT(*) FROM post WHERE original_post_id IS NOT NULL")
    total_comments = cnt("SELECT COUNT(*) FROM comment")
    total_likes = cnt("SELECT COUNT(*) FROM `like`")
    total_follows = cnt("SELECT COUNT(*) FROM follow")
    total_traces = cnt("SELECT COUNT(*) FROM trace")
    active_users = cnt("SELECT COUNT(DISTINCT user_id) FROM post")
    cur.execute("SELECT MIN(created_at), MAX(created_at) FROM post")
    a, b = cur.fetchone()
    duration_h = 0
    if a and b:
        ta, tb = parse_ts(a), parse_ts(b)
        duration_h = round(((tb or 0) - (ta or 0)) / 3600, 1)
    cur.execute("""
        SELECT COUNT(*) FROM post p WHERE original_post_id IS NULL
        AND EXISTS (SELECT 1 FROM post c WHERE c.original_post_id = p.post_id)
    """)
    cascade_count = cur.fetchone()[0]
    cur.execute("""
        SELECT MAX(repost_count) FROM (
          SELECT COUNT(c.post_id) AS repost_count
          FROM post p LEFT JOIN post c ON c.original_post_id = p.post_id
          WHERE p.original_post_id IS NULL GROUP BY p.post_id
        )
    """)
    max_virality = cur.fetchone()[0] or 0
    return dict(
        total_users=total_users, active_users=active_users,
        total_posts=total_posts, original_posts=original, reposts=repost,
        total_comments=total_comments, total_likes=total_likes,
        total_follows=total_follows, total_traces=total_traces,
        duration_h=duration_h, cascade_count=cascade_count,
        max_virality=max_virality,
    )


# ---------- B. Behavior clustering ----------
def compute_behavior_features(conn):
    cur = conn.cursor()
    cur.execute("SELECT user_id, action, COUNT(*) FROM trace GROUP BY user_id, action")
    counts = defaultdict(lambda: dict.fromkeys(ACTION_TYPES, 0))
    for uid, action, n in cur.fetchall():
        if action in ACTION_TYPES:
            counts[uid][action] = n
    cur.execute("SELECT user_id, name FROM user")
    user_name = {r[0]: r[1] for r in cur.fetchall()}
    rows = []
    for uid in sorted(counts.keys()):
        row = {"user_id": uid, "name": user_name.get(uid, str(uid))}
        for a in ACTION_TYPES:
            row[a] = counts[uid][a]
        rows.append(row)
    df = pd.DataFrame(rows)
    return df


def compute_behavior_clusters(df: pd.DataFrame, k: int = 5):
    X_counts = df[ACTION_TYPES].values.astype(float)
    totals = X_counts.sum(axis=1, keepdims=True)
    totals[totals == 0] = 1
    X_norm = X_counts / totals
    X_scaled = StandardScaler().fit_transform(X_norm)
    n = len(df)
    if n < k:
        labels = np.zeros(n, dtype=int)
    else:
        labels = KMeans(n_clusters=k, n_init=10, random_state=42).fit_predict(X_scaled)
    if n >= 4:
        perplexity = max(2, min(30, (n - 1) // 3))
        coords = TSNE(
            n_components=2, perplexity=perplexity, random_state=42,
            init="pca", learning_rate="auto",
        ).fit_transform(X_scaled)
    else:
        coords = np.zeros((n, 2))
    cluster_names = label_clusters(X_norm, labels, k)
    scatter = []
    for i, row in df.iterrows():
        scatter.append({
            "x": float(coords[i, 0]), "y": float(coords[i, 1]),
            "cluster": int(labels[i]), "user_id": int(row["user_id"]),
            "name": row["name"], "total_actions": int(X_counts[i].sum()),
            "actions": {a: int(row[a]) for a in ACTION_TYPES},
        })
    parallel = []
    for c in range(k):
        if (labels == c).sum() == 0:
            continue
        mean = X_norm[labels == c].mean(axis=0)
        parallel.append({
            "cluster": c, "name": cluster_names[c],
            "size": int((labels == c).sum()),
            "values": [round(float(v), 4) for v in mean],
        })
    action_totals = {a: int(X_counts[:, i].sum()) for i, a in enumerate(ACTION_TYPES)}
    return {
        "scatter": scatter, "parallel": parallel,
        "action_totals": action_totals,
        "cluster_names": cluster_names, "k": k,
        "feature_names": ACTION_TYPES,
    }


def label_clusters(X_norm: np.ndarray, labels: np.ndarray, k: int) -> dict[int, str]:
    cluster_names: dict[int, str] = {}
    for c in range(k):
        mask = labels == c
        if not mask.any():
            cluster_names[c] = f"群组{c}"
            continue
        mean = X_norm[mask].mean(axis=0)
        feat = {a: mean[i] for i, a in enumerate(ACTION_TYPES)}
        creators = feat["create_post"] + feat["create_comment"]
        passive = feat["refresh"] + feat["do_nothing"]
        social = feat["follow"] + feat["like_post"]
        searchers = feat["search_posts"] + feat["search_user"]
        spreader = feat["repost"]
        scores = {
            "内容创作者": creators, "潜水/被动": passive,
            "社交活跃者": social, "信息探索者": searchers,
            "传播放大者": spreader,
        }
        cluster_names[c] = max(scores, key=scores.get) + f" (#{c})"
    return cluster_names


# ---------- C. Cascade analysis ----------
def compute_cascades(conn):
    cur = conn.cursor()
    cur.execute("""
        SELECT p.post_id, p.user_id, p.content, p.created_at,
               p.num_likes, p.num_shares, p.num_dislikes, u.name
        FROM post p JOIN user u ON p.user_id = u.user_id
        WHERE p.original_post_id IS NULL
    """)
    roots = cur.fetchall()
    cur.execute("SELECT post_id, original_post_id, created_at FROM post WHERE original_post_id IS NOT NULL")
    repost_edges = cur.fetchall()
    children = defaultdict(list)
    for rid, oid, t in repost_edges:
        children[oid].append((rid, parse_ts(t)))
    cur.execute("SELECT post_id, COUNT(*) FROM comment GROUP BY post_id")
    comment_count_map = dict(cur.fetchall())

    cascade_features = []
    cascade_lifecycles = []
    for root_post_id, uid, content, created, likes, shares, dislikes, uname in roots:
        ts = parse_ts(created)
        descendants = []
        stack = [(root_post_id, 0)]
        max_depth = 0
        edges = []
        while stack:
            pid, d = stack.pop()
            for c, ct in children.get(pid, []):
                descendants.append((c, ct, d + 1))
                edges.append((pid, c))
                stack.append((c, d + 1))
                max_depth = max(max_depth, d + 1)
        size = len(descendants) + 1
        unique_users = set()
        cur.execute("SELECT user_id FROM post WHERE post_id = ?", (root_post_id,))
        r = cur.fetchone()
        if r: unique_users.add(r[0])
        if descendants:
            ids = [d[0] for d in descendants]
            placeholders = ",".join("?" * len(ids))
            cur.execute(f"SELECT user_id FROM post WHERE post_id IN ({placeholders})", ids)
            for (u,) in cur.fetchall():
                unique_users.add(u)
        sv = structural_virality(edges, root_post_id) if edges else 1.0
        all_ts = [ts] + [d[1] for d in descendants if d[1] is not None]
        all_ts = [t for t in all_ts if t]
        duration = (max(all_ts) - min(all_ts)) if len(all_ts) >= 2 else 0
        cascade_features.append({
            "post_id": root_post_id, "user_id": uid, "user_name": uname,
            "content": (content or "")[:120], "size": size,
            "max_depth": max_depth, "unique_users": len(unique_users),
            "duration_min": round(duration / 60, 1),
            "structural_virality": round(sv, 3),
            "num_likes": likes or 0, "num_shares": shares or 0,
            "num_dislikes": dislikes or 0,
            "num_comments": comment_count_map.get(root_post_id, 0),
            "created_at": created,
        })
        if size >= 2 and ts:
            timeline = [(ts, "root")] + [(d[1], "repost") for d in descendants if d[1]]
            timeline.sort()
            cascade_lifecycles.append({
                "post_id": root_post_id, "user_name": uname,
                "content": (content or "")[:60], "size": size,
                "events": [{"t": t, "type": typ} for t, typ in timeline],
            })
    cascade_features.sort(key=lambda x: x["size"], reverse=True)
    cascade_lifecycles.sort(key=lambda x: x["size"], reverse=True)
    return {
        "features": cascade_features,
        "lifecycles": cascade_lifecycles[:10],
    }


def structural_virality(edges: list[tuple[int, int]], root: int) -> float:
    G = nx.DiGraph()
    G.add_node(root)
    G.add_edges_from(edges)
    UG = G.to_undirected()
    n = UG.number_of_nodes()
    if n < 2:
        return 1.0
    try:
        sp = dict(nx.all_pairs_shortest_path_length(UG))
        total = 0; cnt = 0
        nodes = list(UG.nodes())
        for i, u in enumerate(nodes):
            for v in nodes[i + 1:]:
                d = sp.get(u, {}).get(v)
                if d is not None:
                    total += d; cnt += 1
        return total / cnt if cnt else 1.0
    except Exception:
        return 1.0


# ---------- D. Network structure (Louvain) ----------
def compute_network(conn):
    cur = conn.cursor()
    cur.execute("SELECT follower_id, followee_id FROM follow")
    edges = cur.fetchall()
    cur.execute("SELECT user_id, name, num_followers, num_followings FROM user")
    users = cur.fetchall()
    G_dir = nx.DiGraph()
    for uid, name, nf, ng in users:
        G_dir.add_node(uid, name=name, num_followers=nf or 0, num_followings=ng or 0)
    for fr, to in edges:
        G_dir.add_edge(fr, to)
    G_und = G_dir.to_undirected()
    if G_und.number_of_edges() > 0 and nx_comm is not None:
        comms = nx_comm.louvain_communities(G_und, seed=42)
        partition = {}
        for cid, members in enumerate(comms):
            for n in members:
                partition[n] = cid
        for n in G_und.nodes():
            partition.setdefault(n, len(comms))
    else:
        partition = {n: 0 for n in G_und.nodes()}
    pos = nx.spring_layout(G_und, k=1.5 / math.sqrt(max(G_und.number_of_nodes(), 1)),
                          iterations=80, seed=42)
    nodes_out = []
    for uid in G_und.nodes():
        nf = G_dir.nodes[uid].get("num_followers", 0)
        x, y = pos[uid]
        nodes_out.append({
            "id": uid, "name": G_dir.nodes[uid].get("name", str(uid)),
            "x": float(x) * 1000, "y": float(y) * 1000,
            "community": partition.get(uid, 0),
            "followers": int(nf), "degree": int(G_und.degree(uid)),
            "in_degree": int(G_dir.in_degree(uid)),
            "out_degree": int(G_dir.out_degree(uid)),
        })
    links_out = [{"source": fr, "target": to} for fr, to in edges]
    in_deg = Counter([d for _, d in G_dir.in_degree()])
    out_deg = Counter([d for _, d in G_dir.out_degree()])
    in_dist = sorted([(k, v) for k, v in in_deg.items() if k > 0])
    out_dist = sorted([(k, v) for k, v in out_deg.items() if k > 0])
    comms = sorted(set(partition.values()))
    n_comms = len(comms)
    matrix = [[0] * n_comms for _ in range(n_comms)]
    for fr, to in edges:
        ci, cj = partition.get(fr), partition.get(to)
        if ci is not None and cj is not None:
            matrix[ci][cj] += 1
    comm_sizes = Counter(partition.values())
    return {
        "nodes": nodes_out, "links": links_out,
        "communities": [{"id": c, "size": comm_sizes[c]} for c in comms],
        "in_degree_dist": in_dist, "out_degree_dist": out_dist,
        "matrix": matrix, "n_communities": n_comms,
        "partition": partition,
    }


# ---------- E. Topics ----------
def compute_topics(conn, partition: dict, top_k: int = 30):
    cur = conn.cursor()
    cur.execute("SELECT post_id, user_id, content, created_at FROM post WHERE content IS NOT NULL")
    rows = cur.fetchall()
    tag_re = re.compile(r"#([一-龥A-Za-z0-9_]+)")
    tag_count = Counter()
    tag_user = defaultdict(set)
    tag_time = defaultdict(list)
    for pid, uid, content, ts in rows:
        ts_int = parse_ts(ts)
        for t in tag_re.findall(content):
            tag_count[t] += 1
            tag_user[t].add(uid)
            if ts_int: tag_time[t].append(ts_int)
    top_tags = [t for t, _ in tag_count.most_common(top_k)]
    cloud = [{"name": t, "value": tag_count[t]} for t in top_tags]
    n_comms = max(partition.values()) + 1 if partition else 1
    matrix = [[0] * n_comms for _ in top_tags]
    for i, t in enumerate(top_tags):
        for u in tag_user[t]:
            c = partition.get(u)
            if c is not None and c < n_comms:
                matrix[i][c] += 1
    river_top = top_tags[:8]
    if river_top:
        all_ts = [t for tag in river_top for t in tag_time[tag]]
        if all_ts:
            t_min, t_max = min(all_ts), max(all_ts)
            n_buckets = 12
            step = max(1, (t_max - t_min) // n_buckets)
            buckets = [t_min + i * step for i in range(n_buckets + 1)]
            stream = []
            for tag in river_top:
                series = []
                ts_list = sorted(tag_time[tag])
                idx = 0
                for b in buckets:
                    cnt = 0
                    while idx < len(ts_list) and ts_list[idx] < b + step:
                        cnt += 1; idx += 1
                    series.append(cnt)
                stream.append({"name": tag, "values": series})
            stream_x = [datetime.fromtimestamp(b).strftime("%m-%d %H:%M") for b in buckets]
        else:
            stream, stream_x = [], []
    else:
        stream, stream_x = [], []
    return {
        "cloud": cloud, "top_tags": top_tags,
        "comm_matrix": matrix, "n_communities": n_comms,
        "stream": stream, "stream_x": stream_x,
    }


# ---------- F. Recommendation funnel ----------
def compute_funnel(conn):
    cur = conn.cursor()
    cur.execute("SELECT info FROM trace WHERE action='refresh'")
    impressions = 0
    impressed_pairs: set[tuple[int, int]] = set()
    for (info,) in cur.fetchall():
        try:
            d = json.loads(info)
            posts = d.get("posts", [])
            for p in posts:
                pid = p.get("post_id"); uid = p.get("user_id")
                if pid is not None:
                    impressions += 1
            cur2 = conn.cursor()
        except Exception:
            continue
    cur.execute("SELECT user_id, created_at FROM trace WHERE action='refresh'")
    refresh_events = cur.fetchall()
    cur.execute("""
        SELECT t.user_id, t.action, t.info FROM trace t
        WHERE action IN ('like_post','create_comment','repost')
    """)
    likes = comments = reposts = 0
    for uid, act, info in cur.fetchall():
        if act == "like_post": likes += 1
        elif act == "create_comment": comments += 1
        elif act == "repost": reposts += 1
    cur.execute("SELECT COUNT(*) FROM trace WHERE action='do_nothing'")
    do_nothing = cur.fetchone()[0]
    return {
        "impressions": impressions, "do_nothing": do_nothing,
        "likes": likes, "comments": comments, "reposts": reposts,
        "refresh_events": len(refresh_events),
    }


# ---------- G. Activity heatmap ----------
def compute_activity(conn):
    cur = conn.cursor()
    cur.execute("SELECT created_at, action FROM trace WHERE created_at IS NOT NULL")
    rows = cur.fetchall()
    by_day_hour = defaultdict(int)
    by_action_time = defaultdict(lambda: defaultdict(int))
    for created, action in rows:
        ts = parse_ts(created)
        if not ts: continue
        dt = datetime.fromtimestamp(ts)
        day = dt.strftime("%m-%d")
        hour = dt.hour
        by_day_hour[(day, hour)] += 1
        slot = dt.strftime("%m-%d %H:00")
        by_action_time[action][slot] += 1
    days = sorted({d for d, _ in by_day_hour.keys()})
    hours = list(range(24))
    heatmap = []
    for d in days:
        for h in hours:
            heatmap.append([d, h, by_day_hour[(d, h)]])
    all_slots = sorted({slot for d in by_action_time.values() for slot in d.keys()})
    series = []
    for action in ACTION_TYPES:
        d = by_action_time.get(action, {})
        series.append({"name": action, "values": [d.get(slot, 0) for slot in all_slots]})
    return {
        "heatmap": heatmap, "days": days, "hours": hours,
        "stack_x": all_slots, "stack_series": series,
    }


# ---------- H. KOL ----------
def compute_kols(conn, top_n: int = 8):
    cur = conn.cursor()
    cur.execute("""
        SELECT u.user_id, u.name, u.num_followers,
               COUNT(DISTINCT p.post_id) AS posts,
               COALESCE(SUM(p.num_likes), 0) AS likes_recv,
               COALESCE(SUM(p.num_shares), 0) AS shares_recv
        FROM user u LEFT JOIN post p ON u.user_id = p.user_id
        GROUP BY u.user_id
    """)
    rows = cur.fetchall()
    cur.execute("SELECT user_id, action, COUNT(*) FROM trace GROUP BY user_id, action")
    user_actions = defaultdict(lambda: dict.fromkeys(ACTION_TYPES, 0))
    for uid, action, n in cur.fetchall():
        if action in ACTION_TYPES:
            user_actions[uid][action] = n
    enriched = []
    for uid, name, nf, posts, likes, shares in rows:
        score = (
            math.log((nf or 0) + 1) * 3.0
            + math.log(posts + 1) * 2.0
            + math.log(likes + 1) * 1.5
            + math.log(shares + 1) * 2.5
        )
        enriched.append({
            "user_id": uid, "name": name,
            "followers": nf or 0, "posts": posts,
            "likes_recv": likes, "shares_recv": shares,
            "score": round(score, 2),
            "actions": user_actions[uid],
        })
    enriched.sort(key=lambda x: x["score"], reverse=True)
    top = enriched[:top_n]
    radar_indicators = ["粉丝", "发帖", "获赞", "获转", "活跃度"]
    radar_max = [
        max((u["followers"] for u in enriched), default=1) or 1,
        max((u["posts"] for u in enriched), default=1) or 1,
        max((u["likes_recv"] for u in enriched), default=1) or 1,
        max((u["shares_recv"] for u in enriched), default=1) or 1,
        max((sum(u["actions"].values()) for u in enriched), default=1) or 1,
    ]
    radar_data = []
    for u in top:
        radar_data.append({
            "name": u["name"],
            "value": [
                u["followers"], u["posts"], u["likes_recv"],
                u["shares_recv"], sum(u["actions"].values()),
            ],
        })
    storyline = []
    for u in top:
        cur.execute("""
            SELECT created_at, action FROM trace
            WHERE user_id = ? ORDER BY created_at
        """, (u["user_id"],))
        events = []
        for created, action in cur.fetchall():
            ts = parse_ts(created)
            if ts:
                events.append({"t": ts, "action": action})
        storyline.append({
            "user_id": u["user_id"], "name": u["name"],
            "events": events,
        })
    return {
        "ranking": top,
        "radar_indicators": [
            {"name": n, "max": int(m * 1.1) + 1}
            for n, m in zip(radar_indicators, radar_max)
        ],
        "radar_data": radar_data,
        "storyline": storyline,
    }


# ---------- main ----------
def main():
    if not os.path.exists(DB):
        print(f"DB not found: {DB}", file=sys.stderr); sys.exit(1)
    print(f"Reading {DB}")
    conn = sqlite3.connect(DB)
    print("[A] KPI")
    kpi = compute_kpi(conn)
    print("[B] behavior features")
    df = compute_behavior_features(conn)
    behavior = compute_behavior_clusters(df, k=5)
    print(f"    {len(behavior['scatter'])} users, {behavior['k']} clusters")
    print("[C] cascades")
    cascades = compute_cascades(conn)
    print(f"    {len(cascades['features'])} cascades, top size = {cascades['features'][0]['size'] if cascades['features'] else 0}")
    print("[D] network + Louvain")
    network = compute_network(conn)
    print(f"    {network['n_communities']} communities")
    print("[E] topics")
    topics = compute_topics(conn, network["partition"])
    print(f"    {len(topics['cloud'])} hashtags")
    print("[F] funnel")
    funnel = compute_funnel(conn)
    print("[G] activity")
    activity = compute_activity(conn)
    print("[H] KOL")
    kols = compute_kols(conn)
    conn.close()
    network.pop("partition", None)
    payload = {
        "kpi": kpi, "behavior": behavior, "cascades": cascades,
        "network": network, "topics": topics, "funnel": funnel,
        "activity": activity, "kols": kols,
        "_meta": {
            "db": DB,
            "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    }
    payload_path = Path(__file__).parent / "data.json"
    payload_path.write_text(
        json.dumps(payload, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    print(f"\nWrote {payload_path} ({payload_path.stat().st_size / 1024:.1f} KB)")
    print("Run: python build_dashboard_html.py")


if __name__ == "__main__":
    main()
