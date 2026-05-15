"""
Sentiment / Public-Opinion / Key-Actor demo  preprocessor.

Reads:  weibo_test/weibo_sim_qwen_huawei.db
Writes: ./data/*.json   (one file per visualization)

Each builder corresponds to one chart in index.html.

Theory mapping:
    A1 issue lifecycle           Downs 1972
    A2 agenda comparison         McCombs & Shaw 1972
    A3 sentiment stream          Pang & Lee 2008 (lexicon-based)
    A4 framing spectrum          Entman 1993
    A5 polarization radar        Conover 2011 + Esteban-Ray 1994
    A6 spiral of silence         Noelle-Neumann 1974
    A7 risk dashboard            (industry composite)
    B1 group radars (6 axes)     Munzner Vis A&D
    B2 actor multi-dim panel     Inselberg 1985 + Wang 2014
    B3 role quadrants            Burt 1992 + Gleave 2009
    B4 KOL beeswarm timeline     EventFlow / LifeFlow
    B5 group evolution sankey    Liu 2013 (Storyline)

Run:
    python build_data.py
"""
from __future__ import annotations

import json
import math
import re
import sqlite3
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

import numpy as np
import pandas as pd
import networkx as nx


# ----- community detection (python-louvain -> nx fallback) -------------------

HAS_LOUVAIN_PKG = False
try:
    import community as community_louvain
    if hasattr(community_louvain, "best_partition"):
        HAS_LOUVAIN_PKG = True
except Exception:
    pass


def detect_communities(UG: "nx.Graph") -> Tuple[Dict[int, int], float | None]:
    if HAS_LOUVAIN_PKG:
        part = community_louvain.best_partition(UG, random_state=42)
        return part, community_louvain.modularity(part, UG)
    try:
        from networkx.algorithms.community import louvain_communities, modularity
        comms = louvain_communities(UG, seed=42)
    except Exception:
        from networkx.algorithms.community import greedy_modularity_communities, modularity
        comms = list(greedy_modularity_communities(UG))
    part: Dict[int, int] = {}
    for cid, nodes in enumerate(comms):
        for n in nodes:
            part[n] = cid
    try:
        mod = modularity(UG, comms)
    except Exception:
        mod = None
    return part, mod


HERE = Path(__file__).parent
DATA_DIR = HERE / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = Path(r"C:\Users\WangKengyi\oasis_simulation\weibo_test\weibo_sim_qwen_huawei.db")


# =============================================================================
#  LEXICONS  (manually curated, focused on Huawei vs Apple consumer-tech opinion)
# =============================================================================

# --- sentiment ---------------------------------------------------------------
POS_WORDS = [
    "好","棒","赞","强","优秀","出色","惊艳","震撼","完美","满意","稳","香","牛","厉害",
    "突破","创新","领先","突飞猛进","崛起","骄傲","自豪","支持","点赞","看好","期待","希望",
    "信任","可靠","流畅","丝滑","舒服","好用","推荐","值得","划算","热爱","喜欢","爱了",
    "神器","猛","帅","酷","高端","精致","惊喜","提升","跨越","飞跃","超越","碾压","吊打",
    "王者","先进","稳如老狗","硬核","靠谱","逆袭","回血","真香","强大","佩服","认可"
]
NEG_WORDS = [
    "差","烂","糟","坑","垃圾","辣鸡","失望","不行","退步","落后","溢价","贵","难用","卡顿",
    "发热","掉电","掉链子","翻车","崩溃","抄袭","山寨","吹捧","智商税","跌","黑公关","骂",
    "差评","吐槽","抵制","反对","担忧","焦虑","套娃","挤牙膏","阉割","坑爹","凉了","糊了",
    "过气","虚标","缩水","故障","漏洞","不稳定","丑","看不下去","怀疑","质疑","批评","炒作"
]
NEGATION = ["不","没","非","无","别","勿","未"]
SENT_WIN = 3   # negation lookback window (chars)


def score_sentiment(text: str) -> Tuple[int, int, int]:
    """Returns (pos_hits, neg_hits, label) where label in {-1,0,1}.

    For each lexicon hit we look back SENT_WIN chars for a negation char to flip sign.
    """
    if not text:
        return 0, 0, 0
    pos, neg = 0, 0
    for w in POS_WORDS:
        start = 0
        while True:
            i = text.find(w, start)
            if i < 0:
                break
            window = text[max(0, i - SENT_WIN):i]
            flipped = any(n in window for n in NEGATION)
            if flipped:
                neg += 1
            else:
                pos += 1
            start = i + len(w)
    for w in NEG_WORDS:
        start = 0
        while True:
            i = text.find(w, start)
            if i < 0:
                break
            window = text[max(0, i - SENT_WIN):i]
            flipped = any(n in window for n in NEGATION)
            if flipped:
                pos += 1
            else:
                neg += 1
            start = i + len(w)
    if pos > neg:
        label = 1
    elif neg > pos:
        label = -1
    else:
        label = 0
    return pos, neg, label


# --- framing (Entman 1993) ---------------------------------------------------

FRAMES: Dict[str, List[str]] = {
    "民族叙事":   ["国货","国产","中国","民族","自主","自研","崛起","骄傲","自豪","振兴","制裁","封锁","卡脖子","美国","美方"],
    "技术创新":   ["鸿蒙","HarmonyOS","芯片","5G","6G","麒麟","AI","系统","架构","处理器","影像","镜头","续航","快充","工艺","纳米","研发","算法"],
    "产品质量":   ["做工","质量","稳定","可靠","体验","流畅","卡顿","发热","故障","问题","掉链子","丝滑","稳","质感"],
    "价格价值":   ["价格","便宜","贵","溢价","划算","性价比","优惠","降价","预算","万元","成本","钱"],
    "生态体验":   ["生态","应用","App","软件","兼容","互联","同步","云服务","iCloud","账号","设备","平板","手表","耳机","车机","车","跨端"],
}


def score_frames(text: str) -> Dict[str, int]:
    """Counts of frame keywords in text (one count per occurrence)."""
    out = {f: 0 for f in FRAMES}
    if not text:
        return out
    for frame, kws in FRAMES.items():
        for w in kws:
            if not w:
                continue
            i, c = 0, 0
            while True:
                j = text.find(w, i)
                if j < 0:
                    break
                c += 1
                i = j + len(w)
            out[frame] += c
    return out


def primary_frame(text: str) -> str | None:
    s = score_frames(text)
    if max(s.values()) == 0:
        return None
    return max(s.items(), key=lambda kv: kv[1])[0]


# --- stance (pro-Huawei / pro-Apple / neutral) -------------------------------

HW_BRAND = ["华为","Huawei","HUAWEI","鸿蒙","HarmonyOS","Mate","余承东","麒麟"]
APPLE_BRAND = ["苹果","Apple","iPhone","iOS","库克","iCloud","Mac"]
PROCLAIM_HW = ["支持华为","支持国产","华为牛","华为强","国货之光","点赞华为","华为加油","华为崛起"]
PROCLAIM_AP = ["苹果稳","苹果好","苹果生态","苹果体验","iOS流畅","果粉","信仰","果香","只用苹果"]


def stance_score(text: str) -> Tuple[float, float, str]:
    """Returns (score_hw, score_apple, stance) where stance ∈ {pro_hw, pro_ap, neutral, none}.

    For each brand-mention occurrence, look ±10 chars and tally pos/neg sentiment words → contributes to that brand's score.
    Adds bonus from explicit proclaim phrases.
    """
    if not text:
        return 0.0, 0.0, "none"
    hw, ap = 0.0, 0.0
    # brand-window sentiment
    for brand_words, target in [(HW_BRAND, "hw"), (APPLE_BRAND, "ap")]:
        for w in brand_words:
            i = 0
            while True:
                j = text.find(w, i)
                if j < 0:
                    break
                lo, hi = max(0, j - 10), min(len(text), j + len(w) + 10)
                window = text[lo:hi]
                p, n, _ = score_sentiment(window)
                contrib = p - n
                if target == "hw":
                    hw += contrib
                else:
                    ap += contrib
                i = j + len(w)
    for w in PROCLAIM_HW:
        if w in text:
            hw += 2
    for w in PROCLAIM_AP:
        if w in text:
            ap += 2
    # decide
    if hw == 0 and ap == 0:
        # text touched neither brand strongly OR neutral mention
        if any(b in text for b in HW_BRAND) and not any(b in text for b in APPLE_BRAND):
            return 0.0, 0.0, "neutral_hw"
        if any(b in text for b in APPLE_BRAND) and not any(b in text for b in HW_BRAND):
            return 0.0, 0.0, "neutral_ap"
        return 0.0, 0.0, "none"
    if hw > 0 and hw > ap:
        return hw, ap, "pro_hw"
    if ap > 0 and ap > hw:
        return hw, ap, "pro_ap"
    if hw == ap and hw > 0:
        return hw, ap, "neutral"
    if hw > 0 and ap > 0:
        return hw, ap, "neutral"
    return hw, ap, "none"


# --- bio role taxonomy --------------------------------------------------------

BIO_ROLE_RULES = [
    ("官媒/媒体", ["财经","日报","新闻","电视","广播","央视","公众号","记者","编辑","主编","卫视","报"]),
    ("科技博主",  ["科技","数码","手机玩家","测评","搞机","极客","数码博主","互联网","开发","程序员","工程师","技术","评测"]),
    ("商家/合作",  ["合作","商务","微信","客服","推广","商家","代理","卖","店铺","厂商","渠道","V "]),
    ("生活/兴趣",  ["生活","美食","旅行","摄影","游戏","音乐","影视","动漫","养生","宠物","健身","旅游","时尚"]),
]


def classify_bio(bio: str) -> str:
    if not bio:
        return "普通用户"
    for role, kws in BIO_ROLE_RULES:
        for w in kws:
            if w in bio:
                return role
    return "普通用户"


# --- topical agenda keywords (for A2) ----------------------------------------

AGENDA_TOPICS = [
    "华为","苹果","鸿蒙","芯片","Mate","iPhone","5G","生态","影像",
    "续航","价格","国产","创新","系统","制裁","充电","发布会","预算"
]


def agenda_count(text: str) -> Counter:
    c: Counter = Counter()
    if not text:
        return c
    for w in AGENDA_TOPICS:
        i, total = 0, 0
        while True:
            j = text.find(w, i)
            if j < 0:
                break
            total += 1
            i = j + len(w)
        if total:
            c[w] = total
    return c


# =============================================================================
#  IO HELPERS
# =============================================================================

def parse_ts(s: Any) -> int | None:
    if not s:
        return None
    try:
        s = str(s).split(".")[0]
        return int(datetime.strptime(s, "%Y-%m-%d %H:%M:%S").timestamp())
    except Exception:
        return None


def write_json(name: str, payload: Any) -> None:
    p = DATA_DIR / name
    p.write_text(json.dumps(payload, ensure_ascii=False, default=float), encoding="utf-8")
    print(f"  -> {p.relative_to(HERE)}  ({p.stat().st_size/1024:.1f} KB)")


def open_db() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH))
    con.text_factory = lambda b: b.decode("utf-8", errors="replace")
    con.row_factory = sqlite3.Row
    return con


def load_tables() -> Dict[str, pd.DataFrame]:
    con = open_db()
    out = {}
    for t in ["user","post","follow","like","comment","trace","rec"]:
        out[t] = pd.read_sql(f"SELECT * FROM {t}", con)
    con.close()
    for t in ["post","follow","like","comment","trace"]:
        df = out[t]
        if "created_at" in df.columns:
            df["ts"] = df["created_at"].apply(parse_ts)
    return out


def time_bin(ts: int, bin_seconds: int) -> int:
    return (ts // bin_seconds) * bin_seconds


# =============================================================================
#  ENRICHMENT — annotate posts/comments/users with sentiment / frame / stance / role
# =============================================================================

def enrich(tables: Dict[str, pd.DataFrame]) -> Dict[str, pd.DataFrame]:
    posts = tables["post"].copy()
    comments = tables["comment"].copy()
    users = tables["user"].copy()

    # post text = content + quote_content if present
    def merged_text(row):
        a = row.get("content") or ""
        b = row.get("quote_content") or ""
        return f"{a} {b}".strip()

    posts["text"] = posts.apply(merged_text, axis=1)
    posts["sent_pos"], posts["sent_neg"], posts["sent_label"] = zip(
        *posts["text"].apply(score_sentiment)
    )
    posts["frame"] = posts["text"].apply(primary_frame)
    sc = posts["text"].apply(stance_score)
    posts["stance_hw"]  = sc.apply(lambda t: t[0])
    posts["stance_ap"]  = sc.apply(lambda t: t[1])
    posts["stance"]     = sc.apply(lambda t: t[2])

    comments["sent_pos"], comments["sent_neg"], comments["sent_label"] = zip(
        *comments["content"].fillna("").apply(score_sentiment)
    )
    comments["frame"] = comments["content"].fillna("").apply(primary_frame)
    sc = comments["content"].fillna("").apply(stance_score)
    comments["stance_hw"] = sc.apply(lambda t: t[0])
    comments["stance_ap"] = sc.apply(lambda t: t[1])
    comments["stance"]    = sc.apply(lambda t: t[2])

    users["bio_role"] = users["bio"].fillna("").apply(classify_bio)

    tables["post"] = posts
    tables["comment"] = comments
    tables["user"] = users
    return tables


# =============================================================================
#  GRAPH + COMMUNITY  (shared by many builders)
# =============================================================================

def build_graph(follow_df: pd.DataFrame) -> Tuple[nx.DiGraph, nx.Graph, Dict[int,int]]:
    G = nx.DiGraph()
    for _, r in follow_df.iterrows():
        G.add_edge(int(r["follower_id"]), int(r["followee_id"]))
    UG = G.to_undirected()
    if UG.number_of_nodes() == 0:
        return G, UG, {}
    part, _mod = detect_communities(UG)
    return G, UG, part


# =============================================================================
#  A1  ISSUE LIFECYCLE  (Downs 1972)
# =============================================================================

def build_lifecycle(tables) -> None:
    posts, comments, likes = tables["post"], tables["comment"], tables["like"]
    # follow is dominated by sign-up rush → exclude from lifecycle volume
    bin_s = 60 * 60  # 1h
    rows = []
    for df, kind in [(posts, "post"), (comments, "comment"), (likes, "like")]:
        if "ts" not in df.columns:
            continue
        for ts in df["ts"].dropna().astype(int):
            rows.append((time_bin(int(ts), bin_s), kind))
    if not rows:
        write_json("lifecycle.json", {"times": [], "series": {}, "phases": []})
        return
    df = pd.DataFrame(rows, columns=["bin","kind"])
    pivot = df.groupby(["bin","kind"]).size().unstack(fill_value=0).sort_index()
    pivot = pivot.reindex(range(int(pivot.index.min()), int(pivot.index.max())+bin_s, bin_s), fill_value=0)
    times = [datetime.utcfromtimestamp(int(t)).strftime("%m-%d %H:%M") for t in pivot.index]
    total = pivot.sum(axis=1).values
    # 4 phase classifier
    peak_idx = int(np.argmax(total))
    peak = total[peak_idx] if peak_idx < len(total) else 0
    phases = []
    if peak > 0:
        # latent: from start until volume first crosses 20% of peak
        burst_start = 0
        for i, v in enumerate(total):
            if v >= 0.2 * peak:
                burst_start = i
                break
        # sustain start = peak; decay start = first index after peak where v < 0.5*peak
        decay_start = len(total) - 1
        for i in range(peak_idx, len(total)):
            if total[i] < 0.5 * peak:
                decay_start = i
                break
        phases = [
            {"name":"潜伏期 latent",   "start": 0,            "end": max(0, burst_start-1)},
            {"name":"爆发期 burst",    "start": burst_start,  "end": peak_idx},
            {"name":"持续期 sustain",  "start": peak_idx,     "end": max(peak_idx, decay_start-1)},
            {"name":"衰退期 decay",    "start": decay_start,  "end": len(total)-1},
        ]
        # normalize phase ordering / boundaries
        prev = -1
        for ph in phases:
            ph["start"] = max(ph["start"], prev + 1)
            ph["end"] = max(ph["start"], ph["end"])
            prev = ph["end"]
    out = {
        "times": times,
        "series": {col: pivot[col].astype(int).tolist() for col in pivot.columns},
        "total": total.astype(int).tolist(),
        "peak_idx": peak_idx,
        "phases": phases,
    }
    write_json("lifecycle.json", out)


# =============================================================================
#  A2  AGENDA COMPARISON  (McCombs & Shaw 1972)
# =============================================================================

def build_agenda(tables) -> None:
    users, posts, comments = tables["user"], tables["post"], tables["comment"]
    if users.empty:
        write_json("agenda.json", {"topics": [], "media": [], "public": [], "spearman": None})
        return
    follower_q80 = users["num_followers"].quantile(0.80) if not users.empty else 0
    kol_ids = set(users[users["num_followers"] >= max(follower_q80, 1)]["user_id"].astype(int).tolist())

    media_count: Counter = Counter()
    public_count: Counter = Counter()
    # use both posts & comments
    for _, r in posts.iterrows():
        text = r.get("text") or ""
        c = agenda_count(text)
        if int(r["user_id"]) in kol_ids:
            media_count.update(c)
        else:
            public_count.update(c)
    for _, r in comments.iterrows():
        text = r.get("content") or ""
        c = agenda_count(text)
        if int(r["user_id"]) in kol_ids:
            media_count.update(c)
        else:
            public_count.update(c)

    topics = AGENDA_TOPICS
    media = [media_count.get(t, 0) for t in topics]
    public = [public_count.get(t, 0) for t in topics]
    # rank correlation (Spearman)
    def ranks(arr):
        order = np.argsort(-np.array(arr))
        rk = np.zeros(len(arr))
        for r, i in enumerate(order):
            rk[i] = r + 1
        return rk
    if sum(media) > 0 and sum(public) > 0:
        rm = ranks(media)
        rp = ranks(public)
        n = len(media)
        d2 = np.sum((rm - rp) ** 2)
        spearman = 1 - 6 * d2 / (n * (n*n - 1))
    else:
        spearman = None
    write_json("agenda.json", {
        "topics": topics,
        "media": media,
        "public": public,
        "kol_count": len(kol_ids),
        "public_count": int(users.shape[0] - len(kol_ids)),
        "spearman": float(spearman) if spearman is not None else None,
        "kol_threshold_followers": int(follower_q80),
    })


# =============================================================================
#  A3  SENTIMENT STREAM  (Pang & Lee 2008)
# =============================================================================

def build_sentiment_stream(tables) -> None:
    posts, comments = tables["post"], tables["comment"]
    bin_s = 60 * 60
    rows = []
    for df in [posts, comments]:
        if "ts" not in df.columns:
            continue
        for _, r in df.iterrows():
            ts = r.get("ts")
            lab = r.get("sent_label", 0)
            if ts is None or pd.isna(ts):
                continue
            rows.append((time_bin(int(ts), bin_s), int(lab)))
    if not rows:
        write_json("sentiment_stream.json", {"times": [], "pos": [], "neu": [], "neg": []})
        return
    df = pd.DataFrame(rows, columns=["bin","lab"])
    pivot = df.groupby(["bin","lab"]).size().unstack(fill_value=0).sort_index()
    for c in [-1, 0, 1]:
        if c not in pivot.columns:
            pivot[c] = 0
    pivot = pivot.reindex(range(int(pivot.index.min()), int(pivot.index.max())+bin_s, bin_s), fill_value=0)
    out = {
        "times": [datetime.utcfromtimestamp(int(t)).strftime("%m-%d %H:%M") for t in pivot.index],
        "pos":   pivot[1].astype(int).tolist(),
        "neu":   pivot[0].astype(int).tolist(),
        "neg":   pivot[-1].astype(int).tolist(),
    }
    # also load A1 phases for shading overlay
    p = DATA_DIR / "lifecycle.json"
    if p.exists():
        try:
            out["phases"] = json.loads(p.read_text(encoding="utf-8")).get("phases", [])
        except Exception:
            pass
    write_json("sentiment_stream.json", out)


# =============================================================================
#  A4  FRAMING SPECTRUM  (Entman 1993)
# =============================================================================

def build_frames(tables) -> None:
    posts, comments = tables["post"], tables["comment"]
    bin_s = 60 * 60
    rows = []
    for df, txtcol in [(posts, "text"), (comments, "content")]:
        for _, r in df.iterrows():
            ts = r.get("ts")
            if ts is None or pd.isna(ts):
                continue
            text = r.get(txtcol) or ""
            sc = score_frames(text)
            for f, c in sc.items():
                if c > 0:
                    rows.append((time_bin(int(ts), bin_s), f, c))
    if not rows:
        write_json("frames.json", {"times": [], "frames": {}, "matrix": []})
        return
    df = pd.DataFrame(rows, columns=["bin","frame","count"])
    pivot = df.pivot_table(index="bin", columns="frame", values="count", aggfunc="sum", fill_value=0).sort_index()
    pivot = pivot.reindex(range(int(pivot.index.min()), int(pivot.index.max())+bin_s, bin_s), fill_value=0)
    for f in FRAMES:
        if f not in pivot.columns:
            pivot[f] = 0
    times = [datetime.utcfromtimestamp(int(t)).strftime("%m-%d %H:%M") for t in pivot.index]
    series = {f: pivot[f].astype(int).tolist() for f in FRAMES}
    # frame x community matrix
    follow = tables["follow"]; users = tables["user"]
    _, _, part = build_graph(follow)
    user_to_comm = part
    comm_ids = sorted(set(part.values())) if part else []
    matrix = []  # rows=community, cols=frames
    for cid in comm_ids:
        row = {"community": int(cid), "size": int(sum(1 for v in part.values() if v == cid))}
        counts = {f: 0 for f in FRAMES}
        for _, r in posts.iterrows():
            uid = int(r["user_id"])
            if user_to_comm.get(uid) != cid:
                continue
            sc = score_frames(r.get("text") or "")
            for f, c in sc.items():
                counts[f] += int(c)
        row["frames"] = counts
        matrix.append(row)
    write_json("frames.json", {
        "times": times,
        "series": series,
        "frames_order": list(FRAMES.keys()),
        "matrix": matrix,
    })


# =============================================================================
#  A5  POLARIZATION RADAR  (Conover 2011 + Esteban-Ray 1994)
# =============================================================================

def build_polarization(tables) -> None:
    users, posts, follows = tables["user"], tables["post"], tables["follow"]
    _, _, part = build_graph(follows)
    if not part:
        write_json("polarization.json", {"communities": [], "er_index": None})
        return
    # only communities with >=3 members
    cids = sorted({c for c in part.values()})
    sizes = Counter(part.values())
    cids = [c for c in cids if sizes[c] >= 3]

    # per-user stance label
    posts_by_user = posts.groupby("user_id")
    user_stance = {}
    for uid, df in posts_by_user:
        labs = []
        for _, r in df.iterrows():
            s = r.get("stance")
            if s == "pro_hw":
                labs.append(1)
            elif s == "pro_ap":
                labs.append(-1)
            elif s in ("neutral","neutral_hw","neutral_ap"):
                labs.append(0)
        if labs:
            user_stance[int(uid)] = float(np.mean(labs))
    # users without posts → 0
    # frames per user
    user_frames: Dict[int, Counter] = defaultdict(Counter)
    for _, r in posts.iterrows():
        sc = score_frames(r.get("text") or "")
        for f, c in sc.items():
            if c:
                user_frames[int(r["user_id"])][f] += c
    # sentiment per user
    user_sent: Dict[int, float] = {}
    for uid, df in posts_by_user:
        labs = df["sent_label"].astype(int).tolist()
        if labs:
            user_sent[int(uid)] = float(np.mean(labs))

    communities = []
    comm_means = []
    comm_share = []
    total_mass = 0
    for cid in cids:
        members = [u for u, c in part.items() if c == cid]
        n = len(members)
        if n == 0:
            continue
        stances = [user_stance.get(u, 0.0) for u in members]
        sentiments = [user_sent.get(u, 0.0) for u in members]
        frame_counter = Counter()
        for u in members:
            frame_counter.update(user_frames.get(u, Counter()))
        frame_total = sum(frame_counter.values()) or 1
        frame_share = {f: frame_counter.get(f, 0) / frame_total for f in FRAMES}
        # 8-dim radar: stance_pro_hw, stance_pro_ap, sentiment_pos, sentiment_neg, frame×5
        pro_hw = float(np.mean([1 if s > 0.1 else 0 for s in stances]))
        pro_ap = float(np.mean([1 if s < -0.1 else 0 for s in stances]))
        sent_p = float(np.mean([1 if s > 0 else 0 for s in sentiments]))
        sent_n = float(np.mean([1 if s < 0 else 0 for s in sentiments]))
        radar = {
            "倾向华为": pro_hw,
            "倾向苹果": pro_ap,
            "情感正向": sent_p,
            "情感负向": sent_n,
            **frame_share,
        }
        mean_stance = float(np.mean(stances))
        communities.append({
            "id": int(cid),
            "size": int(n),
            "mean_stance": mean_stance,
            "radar": radar,
        })
        comm_means.append(mean_stance)
        comm_share.append(n)
        total_mass += n

    # Esteban-Ray polarization on stance distribution at community level
    # P(α) = K * sum_i sum_j p_i^(1+α) * p_j * |y_i - y_j|
    er_index = 0.0
    if total_mass > 0:
        ps = np.array(comm_share, dtype=float) / total_mass
        ys = np.array(comm_means, dtype=float)
        alpha = 1.6
        K = 1.0
        n = len(ps)
        for i in range(n):
            for j in range(n):
                er_index += K * (ps[i] ** (1+alpha)) * ps[j] * abs(ys[i] - ys[j])

    # Conover-style: variance of mean stances weighted by community size
    if total_mass > 0:
        ps = np.array(comm_share, dtype=float) / total_mass
        ys = np.array(comm_means, dtype=float)
        global_mean = float((ps * ys).sum())
        weighted_var = float((ps * (ys - global_mean) ** 2).sum())
    else:
        weighted_var = 0.0

    write_json("polarization.json", {
        "communities": communities,
        "er_index": float(er_index),
        "between_var": float(weighted_var),
        "alpha": 1.6,
        "frames_order": list(FRAMES.keys()),
    })


# =============================================================================
#  A6  SPIRAL OF SILENCE  (Noelle-Neumann 1974)
# =============================================================================

def build_spiral(tables) -> None:
    posts, comments = tables["post"], tables["comment"]
    bin_s = 60 * 60
    # determine majority/minority stance from total post+comment volume
    stance_counter: Counter = Counter()
    for df, col in [(posts, "stance"), (comments, "stance")]:
        for s in df[col].fillna("none").tolist():
            if s in ("pro_hw","pro_ap"):
                stance_counter[s] += 1
    if not stance_counter:
        write_json("spiral.json", {"times": [], "majority":[], "minority":[], "silencing":[], "majority_label":"", "minority_label":""})
        return
    if stance_counter["pro_hw"] >= stance_counter["pro_ap"]:
        majority, minority = "pro_hw", "pro_ap"
    else:
        majority, minority = "pro_ap", "pro_hw"
    LABEL = {"pro_hw":"亲华为","pro_ap":"亲苹果"}

    # per user → stance group based on majority of their posts/comments
    user_stance_majority: Dict[int, str] = {}
    for uid, grp in pd.concat([
        posts[["user_id","stance"]],
        comments[["user_id","stance"]]
    ]).groupby("user_id"):
        c = Counter(grp["stance"].fillna("none").tolist())
        if c[majority] > c[minority] and c[majority] > 0:
            user_stance_majority[int(uid)] = "majority"
        elif c[minority] > c[majority] and c[minority] > 0:
            user_stance_majority[int(uid)] = "minority"
    # per bin volume from majority/minority users
    rows = []
    for df in [posts, comments]:
        for _, r in df.iterrows():
            ts = r.get("ts")
            if ts is None or pd.isna(ts):
                continue
            uid = int(r["user_id"])
            grp = user_stance_majority.get(uid)
            if grp is None:
                continue
            rows.append((time_bin(int(ts), bin_s), grp))
    if not rows:
        write_json("spiral.json", {"times":[], "majority":[], "minority":[], "silencing":[],
                                   "majority_label":LABEL[majority], "minority_label":LABEL[minority]})
        return
    df = pd.DataFrame(rows, columns=["bin","grp"])
    pivot = df.groupby(["bin","grp"]).size().unstack(fill_value=0).sort_index()
    pivot = pivot.reindex(range(int(pivot.index.min()), int(pivot.index.max())+bin_s, bin_s), fill_value=0)
    for c in ["majority","minority"]:
        if c not in pivot.columns:
            pivot[c] = 0

    maj = pivot["majority"].astype(int).tolist()
    minr = pivot["minority"].astype(int).tolist()

    # silencing index = 1 - (cur minority post rate / baseline rate)
    # baseline = mean(minority) over first 4 bins or first 25% of bins, whichever is larger
    n = len(minr)
    base_n = max(4, n // 4)
    base = np.mean(minr[:base_n]) if base_n > 0 else 0
    silencing = []
    for v in minr:
        if base <= 0:
            silencing.append(0.0)
        else:
            silencing.append(max(0.0, 1.0 - v / base))

    write_json("spiral.json", {
        "times": [datetime.utcfromtimestamp(int(t)).strftime("%m-%d %H:%M") for t in pivot.index],
        "majority": maj,
        "minority": minr,
        "silencing": silencing,
        "majority_label": LABEL[majority],
        "minority_label": LABEL[minority],
        "n_majority_users": int(sum(1 for v in user_stance_majority.values() if v == "majority")),
        "n_minority_users": int(sum(1 for v in user_stance_majority.values() if v == "minority")),
    })


# =============================================================================
#  A7  RISK DASHBOARD
# =============================================================================

def build_risk(tables) -> None:
    posts, comments = tables["post"], tables["comment"]
    users = tables["user"]
    follows = tables["follow"]
    _, _, part = build_graph(follows)

    bin_s = 60 * 60
    # five components per bin
    rows = []
    pc = pd.concat([
        posts[["user_id","ts","sent_label","stance"]],
        comments[["user_id","ts","sent_label","stance"]],
    ])
    pc = pc.dropna(subset=["ts"])
    pc["bin"] = pc["ts"].astype(int).apply(lambda t: time_bin(t, bin_s))
    follower_q80 = users["num_followers"].quantile(0.80) if not users.empty else 0
    kol_ids = set(users[users["num_followers"] >= max(follower_q80, 1)]["user_id"].astype(int).tolist())

    bins = sorted(pc["bin"].unique())
    if not bins:
        write_json("risk.json", {"score": 0, "level": "blue", "components": {}, "history": []})
        return
    full_bins = list(range(int(bins[0]), int(bins[-1])+bin_s, bin_s))

    history = []
    prev_total = 0
    for b in full_bins:
        sub = pc[pc["bin"] == b]
        total = len(sub)
        # 1. velocity = (total - prev_total) / max(prev_total,1)
        velocity = (total - prev_total) / max(prev_total, 1)
        prev_total = total
        # 2. negative rate
        neg_rate = float((sub["sent_label"] == -1).mean()) if total > 0 else 0
        # 3. cross-community spread = unique communities in this bin / total communities
        if part:
            uids = sub["user_id"].astype(int).unique()
            comms = {part.get(u) for u in uids if part.get(u) is not None}
            cross = len(comms) / max(len(set(part.values())), 1)
        else:
            cross = 0
        # 4. KOL involvement
        if total > 0:
            kol_share = float(sub["user_id"].astype(int).isin(kol_ids).mean())
        else:
            kol_share = 0
        # 5. polarization in bin = abs(pro_hw rate - pro_ap rate)
        if total > 0:
            phw = (sub["stance"] == "pro_hw").mean()
            pap = (sub["stance"] == "pro_ap").mean()
            pol = abs(phw - pap)
        else:
            pol = 0
        history.append({
            "time": datetime.utcfromtimestamp(b).strftime("%m-%d %H:%M"),
            "velocity": float(max(0, min(1, velocity / 2))),  # clip to [0,1]
            "neg_rate": float(neg_rate),
            "cross":    float(cross),
            "kol":      float(kol_share),
            "pol":      float(pol),
            "total":    int(total),
        })

    # aggregate score: weighted recent (last 25% of bins)
    take = max(1, len(history) // 4)
    recent = history[-take:]
    def avg(k):
        return float(np.mean([h[k] for h in recent])) if recent else 0
    weights = {"velocity":0.25, "neg_rate":0.25, "cross":0.20, "kol":0.15, "pol":0.15}
    components = {}
    score = 0
    for k, w in weights.items():
        v = avg(k)
        score += w * v
        components[k] = {
            "value": v,
            "weight": w,
            "history": [h[k] for h in history],
        }
    score = round(score * 100, 1)
    if score >= 70:
        level = "red"
    elif score >= 50:
        level = "orange"
    elif score >= 30:
        level = "yellow"
    else:
        level = "blue"

    write_json("risk.json", {
        "score": score,
        "level": level,
        "components": components,
        "labels": {
            "velocity":"声量增速",
            "neg_rate":"负面占比",
            "cross":"跨群扩散",
            "kol":"KOL 涉入",
            "pol":"立场极化",
        },
        "history": history,
    })


# =============================================================================
#  B1  GROUP RADARS  (6 grouping axes)
# =============================================================================

def build_group_radars(tables) -> None:
    users, posts, comments, follows, likes, trace = (
        tables["user"], tables["post"], tables["comment"],
        tables["follow"], tables["like"], tables["trace"]
    )
    DG, UG, part = build_graph(follows)

    # per-user features
    feat: Dict[int, Dict[str, float]] = defaultdict(lambda: dict(
        volume=0, engage_recv=0, influence=0, cross_comm=0,
        sentiment=0, originality=0, responsiveness=0, depth=0
    ))

    posts_by_user = posts.groupby("user_id")
    comments_by_user = comments.groupby("user_id")

    for _, r in users.iterrows():
        uid = int(r["user_id"])
        feat[uid]["influence"] = int(r.get("num_followers") or 0)

    for uid, grp in posts_by_user:
        uid = int(uid)
        feat[uid]["volume"] += len(grp)
        feat[uid]["engage_recv"] += int(grp["num_likes"].fillna(0).sum() + grp["num_shares"].fillna(0).sum())
        feat[uid]["sentiment"] += float(grp["sent_label"].astype(int).sum())
        feat[uid]["originality"] += int(grp["original_post_id"].isna().sum())

    for uid, grp in comments_by_user:
        uid = int(uid)
        feat[uid]["volume"] += len(grp)
        feat[uid]["sentiment"] += float(grp["sent_label"].astype(int).sum())

    # cross-community ties
    for u, c in part.items():
        if u not in DG:
            continue
        nb = list(DG.successors(u)) + list(DG.predecessors(u))
        if not nb:
            continue
        out_comm = sum(1 for n in nb if part.get(n) is not None and part.get(n) != c)
        feat[int(u)]["cross_comm"] = out_comm / max(len(nb), 1)

    # depth = max cascade depth user is part of
    # build cascade trees from posts
    children = defaultdict(list)
    for _, r in posts.iterrows():
        op = r.get("original_post_id")
        if pd.notna(op):
            children[int(op)].append(int(r["post_id"]))
    post_user = dict(zip(posts["post_id"].astype(int), posts["user_id"].astype(int)))
    def depth(pid):
        ch = children.get(pid, [])
        if not ch:
            return 0
        return 1 + max((depth(c) for c in ch), default=0)
    for _, r in posts.iterrows():
        if pd.isna(r.get("original_post_id")):
            d = depth(int(r["post_id"]))
            feat[int(r["user_id"])]["depth"] = max(feat[int(r["user_id"])]["depth"], d)

    # responsiveness = mean inverse gap between sign_up and first action (in seconds)
    # simpler: inverse of (mean trace inter-event gap) per user
    if "ts" in trace.columns:
        for uid, grp in trace.dropna(subset=["ts"]).groupby("user_id"):
            ts = sorted(grp["ts"].astype(int).tolist())
            if len(ts) > 1:
                gaps = np.diff(ts)
                resp = 1.0 / (np.mean(gaps) + 1)  # smaller gap → larger responsiveness
                feat[int(uid)]["responsiveness"] = float(resp)

    user_feat = {int(r["user_id"]): feat[int(r["user_id"])] for _, r in users.iterrows()}

    # 6 grouping schemes
    groupings = []

    # G1 network community (Louvain)
    g1 = defaultdict(list)
    for u in user_feat:
        cid = part.get(u, -1)
        g1[cid].append(u)
    groupings.append(("G1 网络社区 (Louvain)", "follow 图 Louvain 社区", g1))

    # G2 behavior cluster (KMeans on action share)
    from sklearn.cluster import KMeans
    if not trace.empty:
        act_pivot = trace.groupby(["user_id","action"]).size().unstack(fill_value=0)
        if act_pivot.shape[1] > 1 and act_pivot.shape[0] >= 4:
            X = act_pivot.div(act_pivot.sum(axis=1).replace(0,1), axis=0).values
            k = min(5, max(2, X.shape[0] // 5))
            km = KMeans(n_clusters=k, random_state=42, n_init=10).fit(X)
            g2 = defaultdict(list)
            for uid, lab in zip(act_pivot.index, km.labels_):
                if int(uid) in user_feat:
                    g2[int(lab)].append(int(uid))
            groupings.append(("G2 行为画像簇", "trace 动作分布 KMeans", g2))

    # G3 bio role
    g3 = defaultdict(list)
    bio_role = dict(zip(users["user_id"].astype(int), users["bio_role"]))
    for u in user_feat:
        g3[bio_role.get(u, "普通用户")].append(u)
    groupings.append(("G3 角色 (bio)", "bio 文本规则", g3))

    # G4 influence tier
    g4 = defaultdict(list)
    fol = users[["user_id","num_followers"]].copy()
    fol["num_followers"] = fol["num_followers"].fillna(0).astype(int)
    if not fol.empty:
        q = fol["num_followers"].quantile([0.5, 0.9])
        med = q.iloc[0]
        p90 = q.iloc[1]
        for _, r in fol.iterrows():
            f = int(r["num_followers"])
            uid = int(r["user_id"])
            if uid not in user_feat:
                continue
            if f >= max(p90, 1):
                g4["头部 KOL"].append(uid)
            elif f >= max(med, 1):
                g4["腰部"].append(uid)
            else:
                g4["长尾"].append(uid)
    groupings.append(("G4 影响力分层", "粉丝数 quantile 50/90", g4))

    # G5 stance cluster
    g5 = defaultdict(list)
    for uid in user_feat:
        labs = []
        sub = posts[posts["user_id"] == uid]
        for s in sub["stance"].fillna("none").tolist():
            if s == "pro_hw": labs.append(1)
            elif s == "pro_ap": labs.append(-1)
            elif s in ("neutral","neutral_hw","neutral_ap"): labs.append(0)
        if not labs:
            g5["未表态"].append(uid)
            continue
        m = np.mean(labs)
        if m > 0.2: g5["亲华为"].append(uid)
        elif m < -0.2: g5["亲苹果"].append(uid)
        else: g5["中立/混合"].append(uid)
    groupings.append(("G5 立场簇", "post 内容 brand×sentiment", g5))

    # G6 hour pattern: morning/day/evening/night
    g6 = defaultdict(list)
    if "ts" in trace.columns:
        for uid, grp in trace.dropna(subset=["ts"]).groupby("user_id"):
            uid = int(uid)
            if uid not in user_feat:
                continue
            hours = pd.to_datetime(grp["ts"], unit="s").dt.hour.values
            if len(hours) == 0:
                g6["不活跃"].append(uid); continue
            cnt = Counter()
            for h in hours:
                if 6 <= h < 12: cnt["上午"] += 1
                elif 12 <= h < 18: cnt["下午"] += 1
                elif 18 <= h < 24: cnt["晚上"] += 1
                else: cnt["深夜"] += 1
            top = cnt.most_common(1)[0][0]
            g6[top].append(uid)
    groupings.append(("G6 时段画像", "trace 小时分布 modal", g6))

    # build radar payload — normalize each dim across all users in this grouping system
    AXES = ["volume","engage_recv","influence","cross_comm","sentiment","originality","responsiveness","depth"]
    AXIS_LABEL = {
        "volume":"声量",
        "engage_recv":"获赞转发",
        "influence":"粉丝数",
        "cross_comm":"跨群度",
        "sentiment":"情感倾向",
        "originality":"原创率",
        "responsiveness":"响应速度",
        "depth":"传播深度",
    }
    out_groupings = []
    for (name, definition, mapping) in groupings:
        # group means
        groups = []
        # gather all values per axis for normalization
        all_vals = {a: [] for a in AXES}
        for gid, uids in mapping.items():
            for u in uids:
                f = user_feat.get(u, {})
                for a in AXES:
                    all_vals[a].append(float(f.get(a, 0) or 0))
        norm = {}
        for a in AXES:
            arr = np.array(all_vals[a]) if all_vals[a] else np.array([0.0])
            mx = float(np.max(arr)) if arr.size else 1.0
            mn = float(np.min(arr)) if arr.size else 0.0
            norm[a] = (mn, mx)
        for gid, uids in mapping.items():
            if not uids:
                continue
            vec = []
            for a in AXES:
                arr = [float(user_feat.get(u, {}).get(a, 0) or 0) for u in uids]
                m = np.mean(arr) if arr else 0
                lo, hi = norm[a]
                if hi - lo > 1e-9:
                    val = (m - lo) / (hi - lo)
                else:
                    val = 0
                vec.append({"axis": AXIS_LABEL[a], "value": float(val), "raw": float(m)})
            groups.append({
                "id": str(gid),
                "size": len(uids),
                "axes": vec,
            })
        out_groupings.append({
            "name": name,
            "definition": definition,
            "axis_labels": [AXIS_LABEL[a] for a in AXES],
            "groups": groups,
        })

    write_json("group_radars.json", {"groupings": out_groupings})


# =============================================================================
#  B2  ACTOR MULTI-DIM PANEL  (Inselberg 1985 + Wang 2014)
# =============================================================================

def build_actor_dims(tables) -> None:
    users, posts, comments, follows = tables["user"], tables["post"], tables["comment"], tables["follow"]
    DG, UG, part = build_graph(follows)
    # 8 dims
    dims = []
    for _, u in users.iterrows():
        uid = int(u["user_id"])
        sub_p = posts[posts["user_id"] == uid]
        sub_c = comments[comments["user_id"] == uid]
        n_post = len(sub_p)
        n_orig = int(sub_p["original_post_id"].isna().sum())
        n_comm = len(sub_c)
        n_likes_recv = int(sub_p["num_likes"].fillna(0).sum())
        n_shares = int(sub_p["num_shares"].fillna(0).sum())
        followers = int(u.get("num_followers") or 0)
        # betweenness (small graph, OK to compute exactly)
        # for speed, compute once outside; we'll compute here
        # we'll fall back to k-core if needed
        sentiment = 0.0
        if n_post + n_comm > 0:
            sentiment = float((sub_p["sent_label"].sum() + sub_c["sent_label"].sum()) /
                              (n_post + n_comm))
        cross = 0.0
        if uid in DG and DG.degree(uid) > 0:
            nb = list(DG.successors(uid)) + list(DG.predecessors(uid))
            same = sum(1 for n in nb if part.get(n) == part.get(uid))
            cross = 1 - same / len(nb)
        originality = (n_orig / n_post) if n_post > 0 else 0
        dims.append({
            "id": uid,
            "name": u.get("name") or "",
            "role": u.get("bio_role") or "普通用户",
            "comm": int(part.get(uid, -1)),
            "posts": n_post,
            "comments": n_comm,
            "orig": n_orig,
            "likes_recv": n_likes_recv,
            "shares": n_shares,
            "followers": followers,
            "sentiment": sentiment,
            "cross_comm": float(cross),
            "originality": float(originality),
        })

    # global betweenness on undirected graph (small)
    if UG.number_of_nodes() > 0:
        bc = nx.betweenness_centrality(UG)
    else:
        bc = {}
    for d in dims:
        d["betweenness"] = float(bc.get(d["id"], 0))

    # axis order
    axes = ["posts","comments","orig","likes_recv","shares","followers",
            "sentiment","cross_comm","originality","betweenness"]
    axis_labels = {
        "posts":"发帖", "comments":"评论", "orig":"原创",
        "likes_recv":"获赞", "shares":"被转", "followers":"粉丝",
        "sentiment":"情感", "cross_comm":"跨群度",
        "originality":"原创率", "betweenness":"中介度",
    }
    write_json("actor_dims.json", {
        "axes": axes,
        "axis_labels": [axis_labels[a] for a in axes],
        "users": dims,
    })


# =============================================================================
#  B3  ROLE QUADRANTS (Influencer/Broker/Amplifier/Resonator)
# =============================================================================

def build_roles(tables) -> None:
    users, posts, comments, follows = tables["user"], tables["post"], tables["comment"], tables["follow"]
    DG, UG, part = build_graph(follows)

    out = []
    counts = Counter()
    for _, u in users.iterrows():
        uid = int(u["user_id"])
        sub_p = posts[posts["user_id"] == uid]
        sub_c = comments[comments["user_id"] == uid]
        followers = int(u.get("num_followers") or 0)
        n_orig = int(sub_p["original_post_id"].isna().sum())
        n_repost_out = int(sub_p["original_post_id"].notna().sum())
        n_comm = len(sub_c)
        likes_recv = int(sub_p["num_likes"].fillna(0).sum())
        shares = int(sub_p["num_shares"].fillna(0).sum())
        # cross-community share
        cross = 0.0
        if uid in DG and DG.degree(uid) > 0:
            nb = list(DG.successors(uid)) + list(DG.predecessors(uid))
            same = sum(1 for n in nb if part.get(n) == part.get(uid))
            cross = 1 - same / len(nb)
        # role scores
        # normalize scales loosely; the demo dataset is small
        score_inf = followers * 0.7 + n_orig * 1.5 + likes_recv * 0.4
        score_brk = cross * 50 + UG.degree(uid) * 0.5 if uid in UG else 0
        score_amp = n_repost_out * 2.0 + (shares * 0.5)
        score_res = n_comm * 1.0 + likes_recv * 0.2

        scores = {"Influencer": score_inf, "Broker": score_brk,
                  "Amplifier": score_amp, "Resonator": score_res}
        # if all near zero → "Lurker"
        max_s = max(scores.values()) if scores else 0
        if max_s < 1e-3:
            role = "Lurker"
        else:
            role = max(scores.items(), key=lambda kv: kv[1])[0]
        counts[role] += 1

        out.append({
            "id": uid,
            "name": u.get("name") or "",
            "role": role,
            "scores": {k: float(v) for k, v in scores.items()},
            "x": float(cross),                 # cross-community share
            "y": float(math.log1p(followers)), # log followers (reach proxy)
            "size": float(math.log1p(n_orig + n_repost_out + n_comm)),
        })

    write_json("actor_roles.json", {
        "users": out,
        "counts": dict(counts),
        "axis_x": "跨社区连接占比",
        "axis_y": "log(粉丝数+1)",
        "size_meta": "log(总动作+1)",
    })


# =============================================================================
#  B4  KOL BEESWARM TIMELINE (EventFlow / LifeFlow style)
# =============================================================================

def build_kol_timeline(tables) -> None:
    users, posts = tables["user"], tables["post"]
    if users.empty:
        write_json("kol_timeline.json", {"kols": [], "events": []})
        return
    top = users.sort_values("num_followers", ascending=False).head(12)
    kol_ids = list(top["user_id"].astype(int))
    kol_meta = []
    for lane, (_, u) in enumerate(top.iterrows()):
        kol_meta.append({
            "id": int(u["user_id"]),
            "name": u.get("name") or "",
            "role": u.get("bio_role") or "普通用户",
            "lane": lane,
            "followers": int(u.get("num_followers") or 0),
        })
    events = []
    for _, r in posts.iterrows():
        uid = int(r["user_id"])
        if uid not in kol_ids:
            continue
        ts = r.get("ts")
        if ts is None or pd.isna(ts):
            continue
        reach = int((r.get("num_likes") or 0) + (r.get("num_shares") or 0))
        events.append({
            "uid": uid,
            "ts": int(ts),
            "time": datetime.utcfromtimestamp(int(ts)).strftime("%m-%d %H:%M"),
            "reach": reach,
            "sentiment": int(r.get("sent_label") or 0),
            "stance": r.get("stance") or "none",
            "frame": r.get("frame") or "",
            "is_orig": bool(pd.isna(r.get("original_post_id"))),
            "text": (r.get("text") or "")[:80],
            "lane": next(k["lane"] for k in kol_meta if k["id"] == uid),
        })
    events.sort(key=lambda e: e["ts"])
    write_json("kol_timeline.json", {
        "kols": kol_meta,
        "events": events,
    })


# =============================================================================
#  B5  GROUP EVOLUTION SANKEY (stance group over time windows)
# =============================================================================

def build_group_evolution(tables) -> None:
    posts, comments = tables["post"], tables["comment"]
    pc = pd.concat([
        posts[["user_id","ts","stance"]],
        comments[["user_id","ts","stance"]],
    ]).dropna(subset=["ts"])
    if pc.empty:
        write_json("group_evolution.json", {"windows": [], "links": []})
        return
    pc["ts"] = pc["ts"].astype(int)
    t_min, t_max = int(pc["ts"].min()), int(pc["ts"].max())
    n_win = 5
    span = max(1, (t_max - t_min) // n_win)
    edges = [t_min + i * span for i in range(n_win + 1)]
    edges[-1] = t_max + 1

    def label(group):
        c = Counter(group["stance"].fillna("none").tolist())
        if c["pro_hw"] > c["pro_ap"] and c["pro_hw"] > 0:
            return "亲华为"
        if c["pro_ap"] > c["pro_hw"] and c["pro_ap"] > 0:
            return "亲苹果"
        if c["pro_hw"] == c["pro_ap"] == 0 and c["none"] > 0:
            return "未表态"
        return "中立"

    user_window_label: Dict[int, List[str]] = defaultdict(lambda: [None] * n_win)
    win_labels = []
    for w in range(n_win):
        sub = pc[(pc["ts"] >= edges[w]) & (pc["ts"] < edges[w+1])]
        win_labels.append({
            "label": f"窗口{w+1}",
            "start": datetime.utcfromtimestamp(edges[w]).strftime("%m-%d %H:%M"),
            "end":   datetime.utcfromtimestamp(edges[w+1]-1).strftime("%m-%d %H:%M"),
        })
        for uid, g in sub.groupby("user_id"):
            user_window_label[int(uid)][w] = label(g)

    # nodes: window_idx + label
    cats = ["亲华为","亲苹果","中立","未表态","离场"]
    nodes = []
    node_id_map = {}
    for w in range(n_win):
        for cat in cats:
            nid = f"W{w}_{cat}"
            node_id_map[(w, cat)] = nid
            nodes.append({"name": nid, "win": w, "cat": cat,
                          "label": win_labels[w]["label"]})

    # links
    links = []
    link_counter: Counter = Counter()
    for uid, lst in user_window_label.items():
        for w in range(n_win - 1):
            cur = lst[w] or "离场"
            nxt = lst[w+1] or "离场"
            link_counter[((w, cur), (w+1, nxt))] += 1
    for (a, b), v in link_counter.items():
        links.append({
            "source": node_id_map[a],
            "target": node_id_map[b],
            "value": int(v),
        })

    write_json("group_evolution.json", {
        "windows": win_labels,
        "categories": cats,
        "nodes": nodes,
        "links": links,
    })


# =============================================================================
#  OVERVIEW META — for header KPIs
# =============================================================================

def build_overview(tables) -> None:
    posts, comments, users, follows, likes, trace = (
        tables["post"], tables["comment"], tables["user"],
        tables["follow"], tables["like"], tables["trace"]
    )
    n_orig = int(posts["original_post_id"].isna().sum()) if not posts.empty else 0
    n_repost = int(posts["original_post_id"].notna().sum()) if not posts.empty else 0
    write_json("overview.json", {
        "users": int(len(users)),
        "posts_original": n_orig,
        "posts_repost": n_repost,
        "comments": int(len(comments)),
        "likes": int(len(likes)),
        "follows": int(len(follows)),
        "traces": int(len(trace)),
        "time_range": [
            datetime.utcfromtimestamp(int(trace["ts"].dropna().min())).strftime("%Y-%m-%d %H:%M") if "ts" in trace.columns and trace["ts"].notna().any() else "",
            datetime.utcfromtimestamp(int(trace["ts"].dropna().max())).strftime("%Y-%m-%d %H:%M") if "ts" in trace.columns and trace["ts"].notna().any() else "",
        ],
    })


# =============================================================================
#  MAIN
# =============================================================================

def main():
    print(f"DB:  {DB_PATH}")
    print(f"Out: {DATA_DIR}\n")
    tables = load_tables()
    print("loaded:", {k: len(v) for k, v in tables.items()})
    tables = enrich(tables)
    print("enriched (sentiment/frame/stance/role)\n")

    builders = [
        ("overview", build_overview),
        ("A1 lifecycle", build_lifecycle),
        ("A2 agenda", build_agenda),
        ("A3 sentiment_stream", build_sentiment_stream),  # depends on A1 phases
        ("A4 frames", build_frames),
        ("A5 polarization", build_polarization),
        ("A6 spiral", build_spiral),
        ("A7 risk", build_risk),
        ("B1 group_radars", build_group_radars),
        ("B2 actor_dims", build_actor_dims),
        ("B3 actor_roles", build_roles),
        ("B4 kol_timeline", build_kol_timeline),
        ("B5 group_evolution", build_group_evolution),
    ]
    for name, fn in builders:
        print(f"[{name}]")
        fn(tables)
    print("\nALL DONE")


if __name__ == "__main__":
    main()
