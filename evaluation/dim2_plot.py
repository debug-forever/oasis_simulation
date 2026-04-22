import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

# 读取带情感分数的数据
sim_df = pd.read_csv(BASE_DIR / "sim_df_with_score.csv")
real_df = pd.read_csv(BASE_DIR / "real_df_with_score.csv")

# 10-bin 分布数据
N_bins = 10
bins = np.linspace(0, 1, N_bins+1)

def get_bin_dist(scores):
    bin_idx = pd.cut(scores, bins=bins, labels=False, include_lowest=True)
    counts = bin_idx.value_counts().sort_index()
    counts = counts.reindex(range(N_bins), fill_value=0)
    return counts / counts.sum()

sim_bin_dist = get_bin_dist(sim_df['comment_score'])
real_bin_dist = get_bin_dist(real_df['comment_score'])

# 3类分布 - 修复字符串比较问题
def categorize(scores):
    result = []
    for s in scores:
        if s <= 0.33:
            result.append('neg')
        elif s < 0.66:
            result.append('neu')
        else:
            result.append('pos')
    return np.array(result)

def category_dist(cat_array):
    total = len(cat_array)
    return {
        'neg': np.sum(cat_array=='neg') / total,
        'neu': np.sum(cat_array=='neu') / total,
        'pos': np.sum(cat_array=='pos') / total
    }

sim_cat = category_dist(categorize(sim_df['comment_score'].values))
real_cat = category_dist(categorize(real_df['comment_score'].values))

# 创建可视化
fig, axes = plt.subplots(1, 2, figsize=(14, 5))

# 左图：10-bin分布对比
ax1 = axes[0]
x = np.arange(1, N_bins+1)
width = 0.35
ax1.bar(x - width/2, real_bin_dist.values, width, label='真实值', color='#2E86AB', alpha=0.8)
ax1.bar(x + width/2, sim_bin_dist.values, width, label='模拟值', color='#E94F37', alpha=0.8)
ax1.set_xlabel('情感分数区间', fontsize=11)
ax1.set_ylabel('占比', fontsize=11)
ax1.set_title('情感分数10区间分布对比', fontsize=12, fontweight='bold')
ax1.set_xticks(x)
ax1.set_xticklabels([f'{i/10:.1f}-{(i+1)/10:.1f}' for i in range(N_bins)], rotation=45, fontsize=9)
ax1.legend()

# 右图：3类分布对比
ax2 = axes[1]
categories = ['负面 (neg)', '中性 (neu)', '正面 (pos)']
real_vals = [real_cat['neg'], real_cat['neu'], real_cat['pos']]
sim_vals = [sim_cat['neg'], sim_cat['neu'], sim_cat['pos']]

x2 = np.arange(len(categories))
ax2.bar(x2 - width/2, real_vals, width, label='真实值', color='#2E86AB', alpha=0.8)
ax2.bar(x2 + width/2, sim_vals, width, label='模拟值', color='#E94F37', alpha=0.8)
ax2.set_xlabel('情感类别', fontsize=11)
ax2.set_ylabel('占比', fontsize=11)
ax2.set_title('负面/中性/正面 分布对比', fontsize=12, fontweight='bold')
ax2.set_xticks(x2)
ax2.set_xticklabels(categories)
ax2.legend()

# 添加数值标签
for i, (r, s) in enumerate(zip(real_vals, sim_vals)):
    ax2.text(i - width/2, r + 0.02, f'{r:.1%}', ha='center', fontsize=10)
    ax2.text(i + width/2, s + 0.02, f'{s:.1%}', ha='center', fontsize=10)

plt.suptitle('维度二：情感分布对比', fontsize=14, fontweight='bold')
plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'dim2_情感分布对比.png', dpi=150, bbox_inches='tight')
plt.show()

print("\n=== 维度二 指标总结 ===")
print(f"Pearson Correlation (10-bin): -0.2787")
print(f"KL Divergence (3-class): 0.0000")
print("\n3类分布:")
print(f"真实: 负面={real_cat['neg']:.1%}, 中性={real_cat['neu']:.1%}, 正面={real_cat['pos']:.1%}")
print(f"模拟: 负面={sim_cat['neg']:.1%}, 中性={sim_cat['neu']:.1%}, 正面={sim_cat['pos']:.1%}")