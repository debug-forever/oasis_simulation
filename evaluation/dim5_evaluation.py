#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
维度五：传播网络评估
包含预处理（生成agent_follows.csv）和正式评测
"""

import pandas as pd
import networkx as nx
import numpy as np
from scipy import stats
import json
import sys
import csv
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 设置输出
sys.stdout = open(OUTPUT_DIR / "output5.log", "w", encoding="utf-8")
print("================ 维度五：传播网络评估 ================")


# ============================================================
# 1. 配置
# ============================================================
REAL_DATA_FILE = BASE_DIR / "groundtruth" / "top100_users_complete_data_post_followers.json"
SIM_POST_FILE = BASE_DIR / "post.csv"
SIM_USER_FILE = BASE_DIR / "user.csv"


# ============================================================
# 2. 预处理函数：生成agent_follows.csv
# ============================================================
def preprocess_follows():
    """预处理：提取关注关系"""
    print("正在进行预处理，提取关注关系...")

    rows = []

    with open(REAL_DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            user = json.loads(line)
            source_uid = str(user["用户ID"])
            follows = user.get("关注博主信息", {}).get("follows", {})

            for target_uid in follows.keys():
                rows.append({
                    "user_id": source_uid,
                    "follows_id": target_uid
                })

    follows_path = BASE_DIR / "agent_follows.csv"
    with open(follows_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["user_id", "follows_id"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"关注关系已保存到 agent_follows.csv，共 {len(rows)} 条")

    return follows_path


# ============================================================
# 3. 构建传播图
# ============================================================
def build_cascade_graph_sim(df):
    """根据post表构建模拟传播图"""
    G = nx.DiGraph()

    for _, row in df.iterrows():
        post_id = row["post_id"]
        parent_id = row["original_post_id"]

        G.add_node(post_id)

        if not pd.isna(parent_id):
            G.add_edge(int(parent_id), post_id)

    return G


def build_cascade_graph_real(df):
    """根据follows表构建真实传播图"""
    G = nx.DiGraph()

    for _, row in df.iterrows():
        post_id = row["user_id"]
        parent_id = row["follows_id"]

        G.add_node(post_id)

        if not pd.isna(parent_id):
            G.add_edge(int(parent_id), post_id)

    return G


# ============================================================
# 4. 级联结构指标
# ============================================================
def cascade_size(G):
    """级联规模"""
    return G.number_of_nodes()


def cascade_depth(G):
    """传播深度：root到最远叶子"""
    roots = [n for n in G.nodes if G.in_degree(n) == 0]
    max_depth = 0

    for r in roots:
        lengths = nx.single_source_shortest_path_length(G, r)
        max_depth = max(max_depth, max(lengths.values()))

    return max_depth


def max_breadth(G):
    """最大广度：同一层最大节点数"""
    roots = [n for n in G.nodes if G.in_degree(n) == 0]
    level_count = {}

    for r in roots:
        lengths = nx.single_source_shortest_path_length(G, r)
        for _, level in lengths.items():
            level_count[level] = level_count.get(level, 0) + 1

    return max(level_count.values())


# ============================================================
# 5. 幂律/度分布KS检验
# ============================================================
def ks_degree_test(G_sim, G_real):
    """度分布KS检验"""
    deg_sim = [d for _, d in G_sim.out_degree()]
    deg_real = [d for _, d in G_real.out_degree()]

    return stats.ks_2samp(deg_sim, deg_real).statistic


# ============================================================
# 6. 核心传播节点
# ============================================================
def get_core_spreaders(G, df_post, df_user, top_n=10):
    """找出转发量最高的用户"""
    out_deg_dict = dict(G.out_degree())
    df_post['out_degree'] = df_post['post_id'].map(out_deg_dict).fillna(0)
    user_outdeg = df_post.groupby('user_id')['out_degree'].sum().reset_index()
    user_outdeg = user_outdeg.merge(df_user, on='user_id', how='left')
    user_outdeg = user_outdeg.sort_values(by='out_degree', ascending=False)
    return user_outdeg[['user_id', 'weibo_id', 'out_degree']].head(top_n)


def get_most_followed_users(G, df_user, top_n=10):
    """找出被关注数最高的用户"""
    out_deg_dict = dict(G.out_degree())

    df_deg = pd.DataFrame(
        out_deg_dict.items(),
        columns=["weibo_id", "num_followers"]
    )

    df_deg = df_deg.sort_values(by="num_followers", ascending=False).head(top_n)

    df_result = df_deg.merge(df_user[["user_id", "weibo_id"]], on="weibo_id", how="left")
    df_result["user_id"] = df_result["user_id"].apply(lambda x: int(x) if pd.notna(x) else "N/A")
    df_result = df_result[["user_id", "weibo_id", "num_followers"]]

    return df_result


# ============================================================
# 7. 评测函数
# ============================================================
def evaluate_cascade(sim_csv, real_csv, user_csv):
    """综合评估传播网络"""
    print("\n正在构建传播图...")
    sim_df = pd.read_csv(sim_csv)
    real_df = pd.read_csv(real_csv)
    df_user = pd.read_csv(user_csv)

    G_sim = build_cascade_graph_sim(sim_df)
    G_real = build_cascade_graph_real(real_df)

    # 结构指标
    size_sim, size_real = cascade_size(G_sim), cascade_size(G_real)
    depth_sim, depth_real = cascade_depth(G_sim), cascade_depth(G_real)
    breadth_sim, breadth_real = max_breadth(G_sim), max_breadth(G_real)

    error_scale = abs(size_sim - size_real) / size_real * 100
    error_depth = abs(depth_sim - depth_real)
    error_breadth = abs(breadth_sim - breadth_real) / breadth_real * 100

    # 幂律检验
    ks_stat = ks_degree_test(G_sim, G_real)

    print("\n=== Cascade Metrics Comparison ===")
    print(f"Size - Simulated: {size_sim}, Real: {size_real}, Error: {error_scale:.2f}%")
    print(f"Depth - Simulated: {depth_sim}, Real: {depth_real}, Error: {error_depth}")
    print(f"Breadth - Simulated: {breadth_sim}, Real: {breadth_real}, Error: {error_breadth:.2f}%")
    print(f"KS Statistic: {ks_stat:.4f}")

    # 核心传播节点
    print("\n模拟中被转发数最高的 Top 用户:")
    core_users_sim = get_core_spreaders(G_sim, sim_df, df_user, top_n=10)
    print(core_users_sim)

    print("\n实际中被互动数最高的 Top 用户:")
    top_followed = get_most_followed_users(G_real, df_user, top_n=10)
    print(top_followed)

    results = {
        "Scale Error (%)": error_scale,
        "Depth Error": error_depth,
        "Breadth Error (%)": error_breadth,
        "KS Statistic": ks_stat,
        "Scale Pass": error_scale < 20,
        "Depth Pass": error_depth <= 1,
        "Breadth Pass": error_breadth < 30,
        "PowerLaw Pass": ks_stat < 0.1,
    }

    print("\n=== 达标判定 ===")
    for k, v in results.items():
        print(f"{k}: {v}")

    return results


# ============================================================
# 8. 主函数
# ============================================================
def main():
    # 预处理
    import csv
    preprocess_personas = preprocess_follows.__name__

    # 使用转换后的follows路径
    follows_file = BASE_DIR / "agent_follows.csv"

    # 正式评测
    results = evaluate_cascade(
        sim_csv=SIM_POST_FILE,
        real_csv=follows_file,
        user_csv=SIM_USER_FILE
    )

    print("\n================ 评估完成 ================")

    return results


if __name__ == "__main__":
    main()