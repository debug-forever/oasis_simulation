#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
维度二：评论语义评估
包含预处理（生成sim_comments.csv和real_comments.csv）和正式评测
"""

import pandas as pd
import numpy as np
import json
import sys
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F
from scipy.stats import pearsonr
from scipy.special import rel_entr
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 设置输出
sys.stdout = open(OUTPUT_DIR / "output2.log", "w", encoding="utf-8")
print("================ 维度二：评论语义评估 ================")


# ============================================================
# 1. 配置
# ============================================================
REAL_DATA_FILE = BASE_DIR / "groundtruth" / "top100_users_complete_data_post_followers.json"  # 真实 JSON 文件
SIM_POST_FILE = BASE_DIR / "post.csv"
SIM_COMMENT_FILE = BASE_DIR / "comment.csv"


# ============================================================
# 2. 预处理函数：生成sim_comments.csv和real_comments.csv
# ============================================================
def preprocess_comments():
    """预处理：提取评论文本生成评测所需的CSV"""
    print("正在进行预处理...")

    # 读取模拟结果
    df_post = pd.read_csv(SIM_POST_FILE, encoding="utf-8")
    df_comment = pd.read_csv(SIM_COMMENT_FILE, encoding="utf-8")

    # 提取content列并重命名
    df_content1 = df_post[["content"]].rename(columns={"content": "comment_text"})
    df_content2 = df_comment[["content"]].rename(columns={"content": "comment_text"})

    # 合并
    df_all = pd.concat([df_content1, df_content2], ignore_index=True)
    df_all = df_all.dropna(subset=["comment_text"])

    # 保存模拟评论
    sim_comments_path = BASE_DIR / "sim_comments.csv"
    df_all.to_csv(sim_comments_path, index=False, encoding="utf-8-sig")
    print(f"模拟评论已保存到 sim_comments.csv，共 {len(df_all)} 条")

    # 提取真实评论
    all_posts = []
    with open(REAL_DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
                recent_posts = data.get("近期发帖内容分析", {}).get("全部帖子合集", [])
                constructed_posts = data.get("近期发帖内容分析", {}).get("构建帖子合集", [])

                combined = recent_posts + constructed_posts

                for post in combined:
                    all_posts.append({"comment_text": post})

            except Exception as e:
                print(f"解析错误: {e}")

    df_posts = pd.DataFrame(all_posts)
    df_posts = df_posts.dropna(subset=["comment_text"])
    real_comments_path = BASE_DIR / "real_comments.csv"
    df_posts.to_csv(real_comments_path, index=False, encoding="utf-8-sig")
    print(f"真实评论已保存到 real_comments.csv，共 {len(df_posts)} 条")

    return sim_comments_path, real_comments_path


# ============================================================
# 3. 情感分析函数
# ============================================================
def init_sentiment_model():
    """初始化BERT情感分析模型"""
    tokenizer = AutoTokenizer.from_pretrained("nlptown/bert-base-multilingual-uncased-sentiment")
    model = AutoModelForSequenceClassification.from_pretrained("nlptown/bert-base-multilingual-uncased-sentiment")
    return tokenizer, model


def get_sentiment_score(text, tokenizer, model):
    """获取文本的情感得分 (0-1)"""
    inputs = tokenizer(text, return_tensors="pt", truncation=True, padding=True)
    outputs = model(**inputs)
    probs = F.softmax(outputs.logits, dim=-1).detach().numpy()[0]
    score = (sum([i*p for i,p in enumerate(probs, start=1)]) - 1) / 4
    return score


# ============================================================
# 4. 评测函数
# ============================================================
def evaluate_sentiment_distribution(sim_csv, real_csv, tokenizer, model):
    """评估情感分布相似性"""
    sim_df = pd.read_csv(sim_csv)
    real_df = pd.read_csv(real_csv)

    # 处理空值
    sim_df['comment_text'] = sim_df['comment_text'].fillna('')
    real_df['comment_text'] = real_df['comment_text'].fillna('')

    # 计算情感分
    print("正在计算情感分数（这可能需要一些时间）...")
    sim_df['comment_score'] = sim_df['comment_text'].apply(lambda x: get_sentiment_score(x, tokenizer, model))
    real_df['comment_score'] = real_df['comment_text'].apply(lambda x: get_sentiment_score(x, tokenizer, model))

    # 保存带分数的数据
    sim_df.to_csv(BASE_DIR / "sim_df_with_score.csv", index=False, encoding="utf-8-sig")
    real_df.to_csv(BASE_DIR / "real_df_with_score.csv", index=False, encoding="utf-8-sig")

    # 10-bin分布
    N_bins = 10
    bins = np.linspace(0, 1, N_bins+1)

    def get_bin_dist(scores):
        bin_idx = pd.cut(scores, bins=bins, labels=False, include_lowest=True)
        counts = bin_idx.value_counts().sort_index()
        counts = counts.reindex(range(N_bins), fill_value=0)
        return counts / counts.sum()

    sim_bin_dist = get_bin_dist(sim_df['comment_score'])
    real_bin_dist = get_bin_dist(real_df['comment_score'])

    # Pearson correlation (10-bin)
    pearson_corr, _ = pearsonr(real_bin_dist.values, sim_bin_dist.values)
    print(f"\nPearson Correlation (10-bin distribution): {pearson_corr:.4f}")

    # KL散度 (3-class: neg/neu/pos)
    def categorize(scores):
        cats = np.empty_like(scores, dtype=str)
        cats[scores < 0.4] = 'neg'
        cats[(scores >= 0.4) & (scores <= 0.6)] = 'neu'
        cats[scores > 0.6] = 'pos'
        return cats

    def category_dist(cat_array):
        total = len(cat_array)
        return {
            'neg': np.sum(cat_array=='neg') / total,
            'neu': np.sum(cat_array=='neu') / total,
            'pos': np.sum(cat_array=='pos') / total
        }

    sim_cat_dist = category_dist(categorize(sim_df['comment_score'].values))
    real_cat_dist = category_dist(categorize(real_df['comment_score'].values))

    sim_vec = np.array([sim_cat_dist['pos'], sim_cat_dist['neu'], sim_cat_dist['neg']])
    real_vec = np.array([real_cat_dist['pos'], real_cat_dist['neu'], real_cat_dist['neg']])

    epsilon = 1e-10
    sim_vec = np.clip(sim_vec, epsilon, 1)
    real_vec = np.clip(real_vec, epsilon, 1)

    kl_div = np.sum(rel_entr(real_vec, sim_vec))
    print(f"KL Divergence (3-class distribution): {kl_div:.4f}")

    # 输出10-bin分布表格
    bin_table = pd.DataFrame({
        'Bin': range(1, N_bins+1),
        'Real': real_bin_dist.values,
        'Simulated': sim_bin_dist.values,
        'Absolute Error': np.abs(real_bin_dist.values - sim_bin_dist.values)
    })
    print("\n10-bin distribution comparison:")
    print(bin_table)

    return {
        "pearson_corr": pearson_corr,
        "kl_divergence": kl_div,
        "bin_table": bin_table
    }


# ============================================================
# 5. 主函数
# ============================================================
def main():
    # 预处理：生成评测所需的CSV文件
    preprocess_comments()

    # 初始化模型
    print("\n正在加载BERT情感分析模型...")
    tokenizer, model = init_sentiment_model()

    # 正式评测
    results = evaluate_sentiment_distribution(
        BASE_DIR / "sim_comments.csv",
        BASE_DIR / "real_comments.csv",
        tokenizer,
        model
    )

    print("\n================ 评估完成 ================")
    print(f"最终结果: Pearson相关系数={results['pearson_corr']:.4f}, KL散度={results['kl_divergence']:.4f}")

    return results


if __name__ == "__main__":
    main()