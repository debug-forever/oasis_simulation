#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
维度一：事件参与度评估
包含预处理和正式评测
"""

import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 设置输出到日志文件
sys.stdout = open(OUTPUT_DIR / "output1.log", "w", encoding="utf-8")
print("================ 维度一：事件参与度评估 ================")

# ============================================================
# 1. 数据路径配置
# ============================================================
REAL_DATA_FILE = BASE_DIR / "groundtruth" / "top100_users_complete_data_post_followers.json"  # 真实原始 JSON 文件
SIM_POST_FILE = BASE_DIR / "post.csv"
SIM_COMMENT_FILE = BASE_DIR / "comment.csv"
SIM_USER_FILE = BASE_DIR / "user.csv"
TRACE_FILE = BASE_DIR / "trace.csv"


# ============================================================
# 2. 真实数据评估函数
# ============================================================
def load_jsonl(path):
    """加载 JSON Lines 格式文件"""
    users = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            users.append(json.loads(line))
    return users


def eval_real_event_metrics(json_path):
    """评估真实事件指标"""
    users = load_jsonl(json_path)

    total_users = len(users)
    event_users = total_users

    total_comments = 0
    total_reposts = 0
    total_posts = 0

    for u in users:
        stats = u.get("社交影响力", {}).get("转评赞统计", {})
        total_comments += stats.get("总评论数", 0)
        total_reposts += stats.get("总转发数", 0)

        post_block = u.get("近期发帖内容分析", {})
        total_posts += len(post_block.get("全部帖子合集", []))
        total_posts += len(post_block.get("构建帖子合集", []))

    return {
        "real_total_users": total_users,
        "real_event_users": event_users,
        "real_participation_rate": 1.0,
        "real_avg_interactions": (
            (total_comments + total_reposts) / event_users
            if event_users > 0 else 0
        ),
        "real_total_posts": total_posts
    }


# ============================================================
# 3. 模拟数据评估函数
# ============================================================
def eval_sim_event_metrics(post_csv, comment_csv, user_csv):
    """评估模拟事件指标"""
    df_post = pd.read_csv(post_csv)
    df_comment = pd.read_csv(comment_csv)
    df_user = pd.read_csv(user_csv)

    total_users = df_user['user_id'].nunique()

    repost_df = df_post[df_post['original_post_id'].notna()]

    event_users = set(df_post['user_id']) | set(df_comment['user_id'])
    event_users.discard(None)

    num_event_users = len(event_users)

    total_comments = len(df_comment)
    total_reposts = len(repost_df)
    total_posts = len(df_post)

    return {
        "sim_total_users": total_users,
        "sim_event_users": num_event_users,
        "sim_participation_rate": (
            num_event_users / total_users if total_users > 0 else 0
        ),
        "sim_avg_interactions": (
            (total_comments + total_reposts) / num_event_users
            if num_event_users > 0 else 0
        ),
        "sim_total_posts": total_posts
    }


# ============================================================
# 4. 指标对比
# ============================================================
def compare_event_metrics(real_metrics, sim_metrics):
    """对比真实和模拟指标"""
    rows = []
    for k in real_metrics:
        sim_k = k.replace("real_", "sim_")
        rows.append({
            "metric": k.replace("real_", ""),
            "real": round(real_metrics[k], 4),
            "sim": round(sim_metrics.get(sim_k, 0), 4),
            "gap(sim-real)": round(
                sim_metrics.get(sim_k, 0) - real_metrics[k], 4
            )
        })
    return pd.DataFrame(rows)


# ============================================================
# 5. 声量评估
# ============================================================
def calculate_volume_metrics(trace_csv, real_json_file):
    """
    计算声量指标：Trend MAPE、NRMSE
    """
    df = pd.read_csv(trace_csv)

    # 读取真实声量数据
    total_interactions = 0

    # 打开 JSON 文件，逐行读取
    with open(real_json_file, "r", encoding="utf-8") as f_in:
        for line in f_in:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                interaction = data["社交影响力"]["转评赞统计"]["总互动数"]
                total_interactions += interaction
            except (json.JSONDecodeError, KeyError) as e:
                print(f"数据解析错误: {e}")

    R = np.array([total_interactions])
    N = len(R)

    # 计算模拟声量
    excluded_actions = ['refresh', 'sign_up']

    if 'time_slice' in df.columns:
        S = df[~df['action'].isin(excluded_actions)].groupby('time_slice').size().reindex(range(N), fill_value=0).values
    else:
        other_actions_total = df[~df['action'].isin(excluded_actions)].shape[0]
        S = np.full(N, other_actions_total / N)

    # 计算指标
    epsilon = 1

    # Trend MAPE
    trend_mape = np.mean(np.abs((S - R) / (R + epsilon))) * 100

    # NRMSE
    if N == 1:
        nrmse = np.sqrt(np.mean((S - R)**2))
    else:
        nrmse = np.sqrt(np.mean((S - R)**2)) / (np.max(R) - np.min(R) + 1e-6)

    # 输出结果
    result_df = pd.DataFrame({
        'Time Slice': range(1, N+1),
        'Simulated': S,
        'Real': R,
        'Absolute Error': np.abs(S - R)
    })

    print("\n各时间片仿真与真实声量对比：")
    print(result_df)

    print("\n总体指标：")
    print(f"Trend MAPE: {trend_mape:.2f}%")
    print(f"NRMSE: {nrmse:.4f}")

    return {
        "trend_mape": trend_mape,
        "nrmse": nrmse,
        "real_volume": total_interactions,
        "sim_volume": S[0] if len(S) > 0 else 0
    }


# ============================================================
# 6. 主函数
# ============================================================
def main():
    # 评估真实数据
    real_metrics = eval_real_event_metrics(REAL_DATA_FILE)

    # 评估模拟数据
    sim_metrics = eval_sim_event_metrics(
        SIM_POST_FILE, SIM_COMMENT_FILE, SIM_USER_FILE
    )

    # 输出事件参与度指标对比
    df_compare = compare_event_metrics(real_metrics, sim_metrics)
    print("\n事件参与度指标对比：")
    print(df_compare)
    print("\n")

    # 计算声量指标
    volume_metrics = calculate_volume_metrics(TRACE_FILE, REAL_DATA_FILE)

    print("\n================ 评估完成 ================")

    return {
        "event_metrics": df_compare,
        "volume_metrics": volume_metrics
    }


if __name__ == "__main__":
    main()