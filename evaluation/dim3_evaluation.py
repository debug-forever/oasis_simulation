#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
维度三：用户动作预测评估
包含预处理（生成agent_action_vector_sim.csv和agent_action_vector_real.csv）和正式评测
"""

import pandas as pd
import numpy as np
import json
import sys
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from scipy.spatial.distance import cosine
from scipy.stats import pearsonr
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 设置输出
sys.stdout = open(OUTPUT_DIR / "output3.log", "w", encoding="utf-8")
print("================ 维度三：用户动作预测评估 ================")


# ============================================================
# 1. 配置
# ============================================================
REAL_DATA_FILE = BASE_DIR / "groundtruth" / "top100_users_complete_data_post_followers.json"
TRACE_FILE = BASE_DIR / "trace.csv"


# ============================================================
# 2. 预处理函数
# ============================================================
def preprocess_action_vectors():
    """预处理：生成动作向量"""
    print("正在进行预处理...")

    df = pd.read_csv(TRACE_FILE)

    # 定义动作分类
    like_actions = ['like', 'like_post', 'like_comment']
    comment_actions = ['create_comment']
    repost_actions = ['quote_post', 'repost']
    post_actions = ['create_post']

    def categorize_action(act):
        if act in like_actions:
            return 'n_like'
        elif act in comment_actions:
            return 'n_comment'
        elif act in repost_actions:
            return 'n_repost'
        elif act in post_actions:
            return 'n_post'
        else:
            return None

    df['category'] = df['action'].apply(categorize_action)

    # 按agent_id和category分组计数
    action_counts = df.groupby(['user_id', 'category']).size().unstack(fill_value=0).reset_index()

    # 补齐所有列
    for col in ['n_like', 'n_comment', 'n_repost', 'n_post']:
        if col not in action_counts.columns:
            action_counts[col] = 0

    action_counts = action_counts.rename(columns={'user_id': 'agent_id'})
    action_counts = action_counts[['agent_id', 'n_like', 'n_comment', 'n_repost', 'n_post']]

    print(f"模拟动作向量已生成，共 {len(action_counts)} 个智能体")

    # 保存模拟动作向量
    sim_vector_path = BASE_DIR / "agent_action_vector_sim.csv"
    action_counts.to_csv(sim_vector_path, index=False)
    print("模拟动作向量已保存到 agent_action_vector_sim.csv")

    # 生成真实动作向量
    rows = []
    with open(REAL_DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)

                agent_id = data.get("用户ID")

                stats = data.get("社交影响力", {}).get("转评赞统计", {})
                n_like = stats.get("总点赞数", 0)
                n_comment = stats.get("总评论数", 0)
                n_repost = stats.get("总转发数", 0)

                posts_info = data.get("近期发帖内容分析", {})
                n_post = len(posts_info.get("全部帖子合集", [])) + len(posts_info.get("构建帖子合集", []))

                rows.append({
                    "agent_id": agent_id,
                    "n_like": n_like,
                    "n_comment": n_comment,
                    "n_repost": n_repost,
                    "n_post": n_post
                })

            except Exception as e:
                print(f"解析错误: {e}")

    df_stats = pd.DataFrame(rows)
    real_vector_path = BASE_DIR / "agent_action_vector_real.csv"
    df_stats.to_csv(real_vector_path, index=False, encoding="utf-8-sig")
    print(f"真实动作向量已保存到 agent_action_vector_real.csv，共 {len(df_stats)} 条")

    return sim_vector_path, real_vector_path


# ============================================================
# 3. 评测函数
# ============================================================
def evaluate_action_prediction(sim_csv, real_csv):
    """评估用户动作预测准确性"""
    sim_df = pd.read_csv(sim_csv)
    real_df = pd.read_csv(real_csv)

    actions = ['n_like', 'n_comment', 'n_repost', 'n_post']

    # 1. 动作数量相似性 - Normalized Error
    print("\n=== 动作数量归一化误差 ===")
    normalized_errors = {}
    for action in actions:
        ne = np.abs(sim_df[action].values - real_df[action].values) / (real_df[action].values + 1)
        normalized_errors[action] = ne
        print(f"{action} 平均归一化误差: {ne.mean():.4f}")

    overall_ne = np.mean([normalized_errors[a] for a in actions])
    print(f"\n整体智能体数量一致性指标 (Normalized Error): {overall_ne:.4f}")

    # 2. Cosine similarity & Pearson correlation
    print("\n=== 行为向量相似度 ===")
    cos_sims = []
    pearson_corrs = []

    for i in range(len(sim_df)):
        sim_vec = sim_df.loc[i, actions].values
        real_vec = real_df.loc[i, actions].values

        cos_sim = 1 - cosine(sim_vec, real_vec)
        cos_sims.append(cos_sim)

        if np.std(sim_vec) == 0 or np.std(real_vec) == 0:
            corr = 0
        else:
            corr, _ = pearsonr(sim_vec, real_vec)
        pearson_corrs.append(corr)

    print(f"平均 Cosine 相似度: {np.mean(cos_sims):.4f}")
    print(f"平均 Pearson 相关系数: {np.mean(pearson_corrs):.4f}")

    # 3. Accuracy, Precision, Recall, F1 (二值化)
    print("\n=== 动作发生二分类指标 ===")
    sim_bin = (sim_df[actions] > 0).astype(int)
    real_bin = (real_df[actions] > 0).astype(int)

    metrics = {}
    for action in actions:
        acc = accuracy_score(real_bin[action], sim_bin[action])
        prec = precision_score(real_bin[action], sim_bin[action], zero_division=0)
        rec = recall_score(real_bin[action], sim_bin[action], zero_division=0)
        f1 = f1_score(real_bin[action], sim_bin[action], zero_division=0)

        metrics[action] = {'Accuracy': acc, 'Precision': prec, 'Recall': rec, 'F1': f1}
        print(f"动作 {action}: Accuracy={acc:.4f}, Precision={prec:.4f}, Recall={rec:.4f}, F1={f1:.4f}")

    overall_acc = np.mean([metrics[a]['Accuracy'] for a in actions])
    overall_f1 = np.mean([metrics[a]['F1'] for a in actions])
    print(f"\n总体 Accuracy: {overall_acc:.4f}, 总体 F1-score: {overall_f1:.4f}")

    # 达标判定
    print("\n=== 达标判定 ===")
    print("Accuracy > 50%:", overall_acc > 0.5)
    print("F1-score > 0.3:", overall_f1 > 0.3)

    return {
        "normalized_error": overall_ne,
        "cosine_similarity": np.mean(cos_sims),
        "pearson_correlation": np.mean(pearson_corrs),
        "overall_accuracy": overall_acc,
        "overall_f1": overall_f1
    }


# ============================================================
# 4. 主函数
# ============================================================
def main():
    # 预处理
    preprocess_action_vectors()

    # 正式评测
    results = evaluate_action_prediction(
        BASE_DIR / "agent_action_vector_sim.csv",
        BASE_DIR / "agent_action_vector_real.csv"
    )

    print("\n================ 评估完成 ================")

    return results


if __name__ == "__main__":
    main()