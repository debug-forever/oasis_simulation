"""
可视分析数据富化层 (ETL)
=========================

把 OASIS 仿真原始库 (user / post / follow / like / comment / trace / rec)
重构成一组面向「可视分析」的维度模型表，全部以 ``va_`` 前缀写回**同一个**库文件，
不破坏原表，原有可视化页面照常工作。

产出表：
    va_meta            构建元信息 + 生命周期阶段边界
    va_event_fact      统一事实表（一行一个行为事件）
    va_user_dim        用户维度（画像 + 社群 + 影响力分层 + 行为标签 + 关键角色）
    va_post_dim        内容维度（话题 + 情感 + 级联指标 + 所属阶段）
    va_community_dim   社群维度（规模 + 主导话题/情感 + 极化指数）

设计原则：所有耗时计算（社群检测、情感打分、级联指标、生命周期分期）在此一次性
离线完成并落库，API 层只做轻量聚合查询，不阻塞页面。
"""
import os
import sys
import json
import math
import sqlite3
from datetime import datetime
from collections import defaultdict, Counter

# 允许以脚本或模块两种方式运行
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
if _THIS_DIR not in sys.path:
    sys.path.insert(0, _THIS_DIR)
from lexicon import score_sentiment, extract_topics  # noqa: E402

try:
    import networkx as nx
except ImportError:  # pragma: no cover
    nx = None


# ---------------------------------------------------------------------------
# 工具函数
# ---------------------------------------------------------------------------
def parse_ts(s):
    """'2026-03-25 15:30:15.732250' -> datetime，失败返回 None"""
    if not s:
        return None
    try:
        s = str(s).split(".")[0]
        return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
    except Exception:
        return None


def _rows(conn, sql, params=()):
    cur = conn.cursor()
    cur.execute(sql, params)
    cols = [c[0] for c in cur.description] if cur.description else []
    return [dict(zip(cols, r)) for r in cur.fetchall()]


def quantile_tier(value, q_top, q_mid):
    if value >= q_top:
        return "头部"
    if value >= q_mid:
        return "腰部"
    return "长尾"


# ---------------------------------------------------------------------------
# 生命周期分期
# ---------------------------------------------------------------------------
def compute_phases(event_dts):
    """
    根据事件量随时间的曲线，把整个舆情过程切成 潜伏期 / 爆发期 / 扩散期 / 衰退期。

    Args:
        event_dts: 所有事件的 datetime 列表

    Returns:
        phases:  [{'phase','start','end','order'}]  （start/end 为字符串时间）
        assign:  函数 dt -> phase 名称
    """
    PHASE_NAMES = ["潜伏期", "爆发期", "扩散期", "衰退期"]
    dts = sorted([d for d in event_dts if d is not None])
    if len(dts) < 8:
        # 数据太少，按事件数四等分
        n = len(dts)
        if n == 0:
            return [], lambda d: "潜伏期"
        bounds = [dts[0]] + [dts[min(n - 1, (n * k) // 4)] for k in range(1, 4)] + [dts[-1]]
    else:
        # 按小时分桶统计事件量
        buckets = defaultdict(int)
        for d in dts:
            buckets[d.replace(minute=0, second=0, microsecond=0)] += 1
        hours = sorted(buckets)
        counts = [buckets[h] for h in hours]
        # 3 点移动平均平滑
        sm = []
        for i in range(len(counts)):
            lo, hi = max(0, i - 1), min(len(counts), i + 2)
            sm.append(sum(counts[lo:hi]) / (hi - lo))
        peak_i = sm.index(max(sm))
        peak_v = sm[peak_i]
        low_thr = 0.25 * peak_v
        # 潜伏期结束：首次达到 low_thr
        latent_end = 0
        for i in range(len(sm)):
            if sm[i] >= low_thr:
                latent_end = i
                break
        # 爆发期结束 = 峰值
        outbreak_end = max(peak_i, latent_end + 1)
        # 扩散期结束：峰值之后首次跌破 50% 峰值
        diffusion_end = len(sm) - 1
        for i in range(outbreak_end, len(sm)):
            if sm[i] < 0.5 * peak_v:
                diffusion_end = i
                break
        idxs = sorted(set([0, latent_end, outbreak_end, diffusion_end, len(hours) - 1]))
        # 保证恰好 5 个边界点（4 个阶段）
        while len(idxs) < 5:
            idxs.append(len(hours) - 1)
        idxs = idxs[:5]
        bounds = [hours[i] for i in idxs]

    phases = []
    for k in range(4):
        phases.append({
            "phase": PHASE_NAMES[k],
            "order": k,
            "start": bounds[k].strftime("%Y-%m-%d %H:%M:%S"),
            "end": bounds[k + 1].strftime("%Y-%m-%d %H:%M:%S"),
        })

    bound_dt = bounds

    def assign(dt):
        if dt is None:
            return "潜伏期"
        for k in range(4):
            if dt <= bound_dt[k + 1]:
                return PHASE_NAMES[k]
        return "衰退期"

    return phases, assign


# ---------------------------------------------------------------------------
# 级联指标
# ---------------------------------------------------------------------------
def compute_cascades(posts):
    """
    posts: [{post_id, original_post_id, ...}]
    返回 {post_id: {cascade_size, cascade_depth, structural_virality, root_post_id}}
    """
    children = defaultdict(list)
    parent = {}
    for p in posts:
        op = p["original_post_id"]
        if op is not None:
            children[op].append(p["post_id"])
            parent[p["post_id"]] = op

    # 找根
    def find_root(pid):
        seen = set()
        while pid in parent and pid not in seen:
            seen.add(pid)
            pid = parent[pid]
        return pid

    result = {}
    roots = [p["post_id"] for p in posts if p["original_post_id"] is None]
    for root in roots:
        # BFS 收集整棵树 + 深度
        tree_nodes = []
        depth_of = {root: 0}
        queue = [root]
        while queue:
            cur = queue.pop(0)
            tree_nodes.append(cur)
            for ch in children.get(cur, []):
                depth_of[ch] = depth_of[cur] + 1
                queue.append(ch)
        size = len(tree_nodes)
        max_depth = max(depth_of.values()) if depth_of else 0
        # 结构病毒性：树上所有节点对的平均距离（Wiener 指数 / n(n-1)）
        sv = 0.0
        if size > 1 and nx is not None:
            g = nx.Graph()
            for n_ in tree_nodes:
                g.add_node(n_)
            for n_ in tree_nodes:
                for ch in children.get(n_, []):
                    if ch in depth_of:
                        g.add_edge(n_, ch)
            try:
                total, pairs = 0, 0
                for _, dist in nx.all_pairs_shortest_path_length(g):
                    for d in dist.values():
                        total += d
                        pairs += 1
                sv = round(total / max(1, pairs - size), 4) if pairs > size else 0.0
            except Exception:
                sv = float(max_depth)
        for n_ in tree_nodes:
            result[n_] = {
                "root_post_id": root,
                "cascade_size": size,
                "cascade_depth": max_depth,
                "structural_virality": sv,
            }
    # 兜底（孤立帖）
    for p in posts:
        result.setdefault(p["post_id"], {
            "root_post_id": find_root(p["post_id"]),
            "cascade_size": 1,
            "cascade_depth": 0,
            "structural_virality": 0.0,
        })
    return result


# ---------------------------------------------------------------------------
# 用户画像 JSON（可选，尽力匹配）
# ---------------------------------------------------------------------------
def load_profiles(json_path):
    """读取用户画像 NDJSON，返回 {用户名: {gender,region,profession,...}}"""
    if not json_path or not os.path.exists(json_path):
        return {}
    profiles = {}
    try:
        with open(json_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue
                basic = obj.get("个人基本信息", {}) or {}
                name = basic.get("用户名")
                tags = obj.get("特征标签", {}) or {}
                pref = tags.get("内容偏好")
                if isinstance(pref, dict):
                    pref = "/".join(list(pref.keys())[:3])
                elif isinstance(pref, list):
                    pref = "/".join([str(x) for x in pref[:3]])
                if name:
                    profiles[str(name)] = {
                        "gender": basic.get("用户性别") or "未知",
                        "region": basic.get("地区信息") or "未知",
                        "profession": basic.get("职业") or "未知",
                        "education": basic.get("教育背景") or "未知",
                        "weibo_level": basic.get("微博等级") or "未知",
                        "account_type": (obj.get("账号类型与层级", {}) or {}).get("账号类型") or "未知",
                        "content_preference": pref or "未知",
                    }
    except Exception as e:
        print(f"[ETL] 用户画像 JSON 解析失败（忽略）: {e}")
    return profiles


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------
def build_analysis_db(db_path, profile_json_path=None, verbose=True):
    """对指定 SQLite 库构建 va_* 分析表。"""
    def log(*a):
        if not verbose:
            return
        msg = "[ETL] " + " ".join(str(x) for x in a)
        try:
            print(msg)
        except UnicodeEncodeError:
            # Windows GBK 控制台兜底
            sys.stdout.buffer.write(msg.encode("utf-8", "replace") + b"\n")

    if not os.path.exists(db_path):
        raise FileNotFoundError(db_path)

    conn = sqlite3.connect(db_path)
    log(f"打开数据库: {db_path}")

    # ---- 1. 读取原始数据 ------------------------------------------------
    users = _rows(conn, "SELECT user_id, agent_id, user_name, name, bio, "
                        "num_followings, num_followers, weibo_id FROM user")
    posts = _rows(conn, "SELECT post_id, user_id, original_post_id, content, "
                        "quote_content, created_at, num_likes, num_dislikes, "
                        "num_shares, num_reports FROM post")
    follows = _rows(conn, "SELECT follower_id, followee_id, created_at FROM follow")
    likes = _rows(conn, "SELECT user_id, post_id, created_at FROM 'like'")
    comments = _rows(conn, "SELECT comment_id, post_id, user_id, content, "
                          "created_at, num_likes, num_dislikes FROM comment")
    traces = _rows(conn, "SELECT user_id, created_at, action FROM trace")
    recs = _rows(conn, "SELECT user_id, post_id FROM rec")
    log(f"原始数据: users={len(users)} posts={len(posts)} follows={len(follows)} "
        f"likes={len(likes)} comments={len(comments)} traces={len(traces)} recs={len(recs)}")

    post_by_id = {p["post_id"]: p for p in posts}
    rec_set = {(r["user_id"], r["post_id"]) for r in recs}

    # ---- 2. 社群检测（关注图） -----------------------------------------
    community_of = {u["user_id"]: 0 for u in users}
    indeg = defaultdict(int)
    outdeg = defaultdict(int)
    pagerank = {u["user_id"]: 0.0 for u in users}
    if nx is not None and follows:
        DG = nx.DiGraph()
        DG.add_nodes_from([u["user_id"] for u in users])
        for f in follows:
            DG.add_edge(f["follower_id"], f["followee_id"])
            outdeg[f["follower_id"]] += 1
            indeg[f["followee_id"]] += 1
        try:
            pagerank = nx.pagerank(DG, alpha=0.85)
        except Exception as e:
            log(f"pagerank 失败: {e}")
        UG = DG.to_undirected()
        comps = None
        if UG.number_of_edges() > 0:
            try:
                comps = nx.community.louvain_communities(UG, seed=42)
            except Exception as e:
                log(f"Louvain 不可用，尝试贪心模块度: {e}")
                try:
                    comps = list(nx.community.greedy_modularity_communities(UG))
                except Exception as e2:
                    log(f"贪心模块度失败，退回连通分量: {e2}")
                    comps = list(nx.connected_components(UG))
        else:
            comps = list(nx.connected_components(UG))
        for i, comp in enumerate(comps):
            for n_ in comp:
                community_of[n_] = i
    n_comm = len(set(community_of.values()))
    log(f"社群检测完成: {n_comm} 个社群")

    # ---- 3. 帖子情感 / 话题 / 级联 -------------------------------------
    cascades = compute_cascades(posts)
    post_meta = {}  # post_id -> dict
    for p in posts:
        text = p["content"] or p["quote_content"] or ""
        senti, slabel = score_sentiment(text)
        topic, hashtags = extract_topics(text)
        # 转发帖若无内容，继承原帖话题
        if topic == "其他" and p["original_post_id"] is not None:
            root = cascades.get(p["post_id"], {}).get("root_post_id")
            rp = post_by_id.get(root)
            if rp:
                topic, _ = extract_topics(rp["content"] or "")
        c = cascades.get(p["post_id"], {})
        post_meta[p["post_id"]] = {
            "sentiment_score": senti,
            "sentiment_class": slabel,
            "topic": topic,
            "hashtags": json.dumps(hashtags, ensure_ascii=False),
            "is_repost": 1 if p["original_post_id"] is not None else 0,
            "root_post_id": c.get("root_post_id", p["post_id"]),
            "cascade_size": c.get("cascade_size", 1),
            "cascade_depth": c.get("cascade_depth", 0),
            "structural_virality": c.get("structural_virality", 0.0),
        }

    # ---- 4. 组装事实表 event_fact --------------------------------------
    events = []  # 每项: dict
    all_dts = []

    def add_event(dt, actor, action, post_id=None, target=None):
        topic = senti = slabel = None
        if post_id is not None and post_id in post_meta:
            pm = post_meta[post_id]
            topic, senti, slabel = pm["topic"], pm["sentiment_score"], pm["sentiment_class"]
        is_rec = 1 if (post_id is not None and (actor, post_id) in rec_set) else 0
        events.append({
            "ts": dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None,
            "_dt": dt,
            "actor_id": actor,
            "action_type": action,
            "post_id": post_id,
            "target_user_id": target,
            "topic": topic,
            "sentiment_score": senti,
            "sentiment_class": slabel,
            "community_id": community_of.get(actor, 0),
            "is_rec_driven": is_rec,
        })
        if dt:
            all_dts.append(dt)

    for p in posts:
        dt = parse_ts(p["created_at"])
        if p["original_post_id"] is None:
            add_event(dt, p["user_id"], "create_post", p["post_id"])
        else:
            root = post_meta[p["post_id"]]["root_post_id"]
            target = post_by_id.get(p["original_post_id"], {}).get("user_id")
            add_event(dt, p["user_id"], "repost", p["post_id"], target)
    for c in comments:
        add_event(parse_ts(c["created_at"]), c["user_id"], "create_comment", c["post_id"],
                  post_by_id.get(c["post_id"], {}).get("user_id"))
    for l in likes:
        add_event(parse_ts(l["created_at"]), l["user_id"], "like_post", l["post_id"],
                  post_by_id.get(l["post_id"], {}).get("user_id"))
    for f in follows:
        add_event(parse_ts(f["created_at"]), f["follower_id"], "follow", None, f["followee_id"])
    SOFT = {"refresh", "do_nothing", "search_user", "search_posts", "trend", "sign_up"}
    for t in traces:
        if t["action"] in SOFT:
            add_event(parse_ts(t["created_at"]), t["user_id"], t["action"])
    log(f"事实表事件数: {len(events)}")

    # ---- 5. 生命周期分期 ------------------------------------------------
    phases, assign_phase = compute_phases(all_dts)
    for e in events:
        e["phase"] = assign_phase(e["_dt"])
    # 给帖子也打阶段
    post_phase = {}
    for p in posts:
        post_phase[p["post_id"]] = assign_phase(parse_ts(p["created_at"]))
    log(f"生命周期阶段: {[ph['phase'] for ph in phases]}")

    # ---- 6. 用户维度聚合 ------------------------------------------------
    # 按用户聚合各类计数
    u_post = Counter(); u_repost = Counter(); u_comment = Counter()
    u_like_given = Counter(); u_activity = Counter()
    u_action_mix = defaultdict(Counter)
    likes_received = Counter(); reposts_received = Counter()
    first_dt = {}; last_dt = {}
    for e in events:
        a = e["actor_id"]
        u_action_mix[a][e["action_type"]] += 1
        u_activity[a] += 1
        if e["_dt"]:
            if a not in first_dt or e["_dt"] < first_dt[a]:
                first_dt[a] = e["_dt"]
            if a not in last_dt or e["_dt"] > last_dt[a]:
                last_dt[a] = e["_dt"]
        if e["action_type"] == "create_post":
            u_post[a] += 1
        elif e["action_type"] == "repost":
            u_repost[a] += 1
            if e["target_user_id"] is not None:
                reposts_received[e["target_user_id"]] += 1
        elif e["action_type"] == "create_comment":
            u_comment[a] += 1
        elif e["action_type"] == "like_post":
            u_like_given[a] += 1
            if e["target_user_id"] is not None:
                likes_received[e["target_user_id"]] += 1
    # 也把帖子自带的 num_likes/num_shares 计入「收到」
    for p in posts:
        likes_received[p["user_id"]] += (p["num_likes"] or 0)
        reposts_received[p["user_id"]] += (p["num_shares"] or 0)

    # 影响力分数
    infl = {}
    for u in users:
        uid = u["user_id"]
        infl[uid] = round(
            math.log((u["num_followers"] or 0) + 1) * 3.0 +
            math.log(reposts_received[uid] + 1) * 2.5 +
            math.log(likes_received[uid] + 1) * 1.5 +
            math.log(u_post[uid] + 1) * 2.0 +
            pagerank.get(uid, 0.0) * 50.0, 3)
    sorted_infl = sorted(infl.values(), reverse=True)
    n_u = max(1, len(sorted_infl))
    q_top = sorted_infl[int(n_u * 0.10)] if n_u > 10 else sorted_infl[0]
    q_mid = sorted_infl[int(n_u * 0.40)] if n_u > 4 else sorted_infl[-1]

    # 活跃度阈值（top 15%）
    sorted_act = sorted(u_activity.values(), reverse=True) or [0]
    act_thr = sorted_act[int(len(sorted_act) * 0.15)] if len(sorted_act) > 6 else sorted_act[0]

    # 讨论发起者：发过 cascade_size>=3 原创帖的人
    initiators = set()
    for p in posts:
        if p["original_post_id"] is None and post_meta[p["post_id"]]["cascade_size"] >= 3:
            initiators.add(p["user_id"])

    def behavior_label(uid):
        mix = u_action_mix[uid]
        total = sum(mix.values())
        if total == 0:
            return "未参与"
        soft = mix["refresh"] + mix["do_nothing"] + mix["search_user"] + mix["search_posts"] + mix["trend"]
        produce = mix["create_post"] + mix["repost"]
        interact = mix["create_comment"] + mix["like_post"] + mix["follow"]
        if mix["do_nothing"] / total > 0.6:
            return "沉默用户"
        if soft / total > 0.7:
            return "潜水观望"
        if produce >= interact and produce > 0:
            return "内容生产者"
        if interact > 0:
            return "活跃互动者"
        return "普通参与者"

    profiles = load_profiles(profile_json_path)
    if profiles:
        log(f"载入用户画像: {len(profiles)} 条")

    user_dim = []
    for u in users:
        uid = u["user_id"]
        tier = quantile_tier(infl[uid], q_top, q_mid)
        is_leader = tier == "头部" and (reposts_received[uid] + likes_received[uid]) > 0
        is_initiator = uid in initiators
        is_active = u_activity[uid] >= act_thr and act_thr > 0
        if is_leader:
            role = "意见领袖"
        elif is_initiator:
            role = "讨论发起者"
        elif is_active:
            role = "活跃用户"
        elif u_repost[uid] > 0:
            role = "普通传播者"
        else:
            role = "边缘用户"
        prof = profiles.get(str(u["name"] or ""), {})
        user_dim.append({
            "user_id": uid,
            "name": u["name"] or f"用户{uid}",
            "bio": u["bio"] or "",
            "num_followers": u["num_followers"] or 0,
            "num_followings": u["num_followings"] or 0,
            "in_degree": indeg.get(uid, 0),
            "out_degree": outdeg.get(uid, 0),
            "pagerank": round(pagerank.get(uid, 0.0), 6),
            "post_count": u_post[uid],
            "repost_count": u_repost[uid],
            "comment_count": u_comment[uid],
            "like_given": u_like_given[uid],
            "likes_received": likes_received[uid],
            "reposts_received": reposts_received[uid],
            "activity_level": u_activity[uid],
            "community_id": community_of.get(uid, 0),
            "influence_score": infl[uid],
            "influence_tier": tier,
            "behavior_label": behavior_label(uid),
            "role": role,
            "is_opinion_leader": int(is_leader),
            "is_initiator": int(is_initiator),
            "is_active": int(is_active),
            "first_active": first_dt[uid].strftime("%Y-%m-%d %H:%M:%S") if uid in first_dt else None,
            "last_active": last_dt[uid].strftime("%Y-%m-%d %H:%M:%S") if uid in last_dt else None,
            "gender": prof.get("gender", "未知"),
            "region": prof.get("region", "未知"),
            "profession": prof.get("profession", "未知"),
            "education": prof.get("education", "未知"),
            "account_type": prof.get("account_type", "未知"),
            "content_preference": prof.get("content_preference", "未知"),
        })

    # ---- 7. 社群维度 ----------------------------------------------------
    comm_users = defaultdict(list)
    for ud in user_dim:
        comm_users[ud["community_id"]].append(ud)
    comm_events = defaultdict(list)
    for e in events:
        comm_events[e["community_id"]].append(e)
    community_dim = []
    for cid, members in comm_users.items():
        evs = comm_events.get(cid, [])
        senti_vals = [e["sentiment_score"] for e in evs if e["sentiment_score"] is not None]
        topic_counter = Counter(e["topic"] for e in evs if e["topic"])
        scls = Counter(e["sentiment_class"] for e in evs if e["sentiment_class"])
        pos, neu, neg = scls["正面"], scls["中性"], scls["负面"]
        tot_s = max(1, pos + neu + neg)
        # 极化指数：正负占比的乘积越大越「两极对立」，再放大
        polar = round(4.0 * (pos / tot_s) * (neg / tot_s), 4)
        top_user = max(members, key=lambda m: m["influence_score"]) if members else None
        community_dim.append({
            "community_id": cid,
            "size": len(members),
            "post_count": sum(m["post_count"] for m in members),
            "event_count": len(evs),
            "avg_sentiment": round(sum(senti_vals) / len(senti_vals), 4) if senti_vals else 0.0,
            "pos_count": pos, "neu_count": neu, "neg_count": neg,
            "polarization_index": polar,
            "dominant_topic": topic_counter.most_common(1)[0][0] if topic_counter else "其他",
            "top_user_id": top_user["user_id"] if top_user else None,
            "top_user_name": top_user["name"] if top_user else None,
        })
    community_dim.sort(key=lambda c: c["size"], reverse=True)

    # ---- 8. 帖子维度 ----------------------------------------------------
    comment_cnt = Counter(c["post_id"] for c in comments)
    post_dim = []
    for p in posts:
        pm = post_meta[p["post_id"]]
        post_dim.append({
            "post_id": p["post_id"],
            "user_id": p["user_id"],
            "is_repost": pm["is_repost"],
            "root_post_id": pm["root_post_id"],
            "content": (p["content"] or p["quote_content"] or "")[:500],
            "created_at": p["created_at"],
            "phase": post_phase.get(p["post_id"], "潜伏期"),
            "num_likes": p["num_likes"] or 0,
            "num_shares": p["num_shares"] or 0,
            "num_dislikes": p["num_dislikes"] or 0,
            "comment_count": comment_cnt.get(p["post_id"], 0),
            "topic": pm["topic"],
            "hashtags": pm["hashtags"],
            "sentiment_score": pm["sentiment_score"],
            "sentiment_class": pm["sentiment_class"],
            "stance": "未标注",  # 立场信息：预留字段，后续标注后写回
            "cascade_size": pm["cascade_size"],
            "cascade_depth": pm["cascade_depth"],
            "structural_virality": pm["structural_virality"],
            "community_id": community_of.get(p["user_id"], 0),
        })

    # ---- 9. 落库 --------------------------------------------------------
    _write_tables(conn, events, user_dim, post_dim, community_dim, phases,
                  {"users": len(users), "posts": len(posts), "events": len(events),
                   "communities": n_comm})
    conn.commit()
    conn.close()
    log("构建完成")
    return {
        "users": len(user_dim), "posts": len(post_dim), "events": len(events),
        "communities": len(community_dim), "phases": phases,
    }


def _write_tables(conn, events, user_dim, post_dim, community_dim, phases, counts):
    cur = conn.cursor()
    for t in ["va_event_fact", "va_user_dim", "va_post_dim", "va_community_dim", "va_meta"]:
        cur.execute(f"DROP TABLE IF EXISTS {t}")

    cur.execute("""
        CREATE TABLE va_event_fact (
            event_id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT, phase TEXT, actor_id INTEGER, action_type TEXT,
            post_id INTEGER, target_user_id INTEGER, topic TEXT,
            sentiment_score REAL, sentiment_class TEXT,
            community_id INTEGER, is_rec_driven INTEGER
        )""")
    cur.executemany("""
        INSERT INTO va_event_fact
        (ts,phase,actor_id,action_type,post_id,target_user_id,topic,
         sentiment_score,sentiment_class,community_id,is_rec_driven)
        VALUES (:ts,:phase,:actor_id,:action_type,:post_id,:target_user_id,:topic,
                :sentiment_score,:sentiment_class,:community_id,:is_rec_driven)
    """, events)

    cur.execute("""
        CREATE TABLE va_user_dim (
            user_id INTEGER PRIMARY KEY, name TEXT, bio TEXT,
            num_followers INTEGER, num_followings INTEGER,
            in_degree INTEGER, out_degree INTEGER, pagerank REAL,
            post_count INTEGER, repost_count INTEGER, comment_count INTEGER,
            like_given INTEGER, likes_received INTEGER, reposts_received INTEGER,
            activity_level INTEGER, community_id INTEGER,
            influence_score REAL, influence_tier TEXT, behavior_label TEXT, role TEXT,
            is_opinion_leader INTEGER, is_initiator INTEGER, is_active INTEGER,
            first_active TEXT, last_active TEXT,
            gender TEXT, region TEXT, profession TEXT, education TEXT,
            account_type TEXT, content_preference TEXT
        )""")
    cur.executemany("""
        INSERT INTO va_user_dim VALUES
        (:user_id,:name,:bio,:num_followers,:num_followings,:in_degree,:out_degree,
         :pagerank,:post_count,:repost_count,:comment_count,:like_given,:likes_received,
         :reposts_received,:activity_level,:community_id,:influence_score,:influence_tier,
         :behavior_label,:role,:is_opinion_leader,:is_initiator,:is_active,
         :first_active,:last_active,:gender,:region,:profession,:education,
         :account_type,:content_preference)
    """, user_dim)

    cur.execute("""
        CREATE TABLE va_post_dim (
            post_id INTEGER PRIMARY KEY, user_id INTEGER, is_repost INTEGER,
            root_post_id INTEGER, content TEXT, created_at TEXT, phase TEXT,
            num_likes INTEGER, num_shares INTEGER, num_dislikes INTEGER,
            comment_count INTEGER, topic TEXT, hashtags TEXT,
            sentiment_score REAL, sentiment_class TEXT, stance TEXT,
            cascade_size INTEGER, cascade_depth INTEGER, structural_virality REAL,
            community_id INTEGER
        )""")
    cur.executemany("""
        INSERT INTO va_post_dim VALUES
        (:post_id,:user_id,:is_repost,:root_post_id,:content,:created_at,:phase,
         :num_likes,:num_shares,:num_dislikes,:comment_count,:topic,:hashtags,
         :sentiment_score,:sentiment_class,:stance,:cascade_size,:cascade_depth,
         :structural_virality,:community_id)
    """, post_dim)

    cur.execute("""
        CREATE TABLE va_community_dim (
            community_id INTEGER PRIMARY KEY, size INTEGER, post_count INTEGER,
            event_count INTEGER, avg_sentiment REAL,
            pos_count INTEGER, neu_count INTEGER, neg_count INTEGER,
            polarization_index REAL, dominant_topic TEXT,
            top_user_id INTEGER, top_user_name TEXT
        )""")
    cur.executemany("""
        INSERT INTO va_community_dim VALUES
        (:community_id,:size,:post_count,:event_count,:avg_sentiment,
         :pos_count,:neu_count,:neg_count,:polarization_index,:dominant_topic,
         :top_user_id,:top_user_name)
    """, community_dim)

    cur.execute("CREATE TABLE va_meta (key TEXT PRIMARY KEY, value TEXT)")
    meta = {
        "built_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "phases": json.dumps(phases, ensure_ascii=False),
        "counts": json.dumps(counts, ensure_ascii=False),
    }
    cur.executemany("INSERT INTO va_meta VALUES (?,?)", list(meta.items()))

    # 索引
    for col in ["actor_id", "action_type", "phase", "community_id", "topic",
                "sentiment_class", "post_id"]:
        cur.execute(f"CREATE INDEX idx_ef_{col} ON va_event_fact({col})")
    cur.execute("CREATE INDEX idx_ud_comm ON va_user_dim(community_id)")
    cur.execute("CREATE INDEX idx_ud_role ON va_user_dim(role)")
    cur.execute("CREATE INDEX idx_pd_topic ON va_post_dim(topic)")
    cur.execute("CREATE INDEX idx_pd_phase ON va_post_dim(phase)")


def has_analysis_tables(db_path):
    """检查指定库是否已构建 va_* 表。"""
    if not os.path.exists(db_path):
        return False
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'va_%'")
        names = {r[0] for r in cur.fetchall()}
        conn.close()
        return {"va_event_fact", "va_user_dim", "va_post_dim",
                "va_community_dim", "va_meta"}.issubset(names)
    except Exception:
        return False


if __name__ == "__main__":
    # 直接运行：默认对 weibo_test 下的样例库构建
    default_db = os.path.join(_THIS_DIR, "..", "..", "..", "weibo_test",
                              "weibo_sim_qwen_huawei.db")
    default_json = os.path.join(_THIS_DIR, "..", "..", "..", "weibo_test",
                                "top100_users_complete_data_post_followers.json")
    db = sys.argv[1] if len(sys.argv) > 1 else os.path.abspath(default_db)
    pj = sys.argv[2] if len(sys.argv) > 2 else os.path.abspath(default_json)
    print(build_analysis_db(db, pj))
