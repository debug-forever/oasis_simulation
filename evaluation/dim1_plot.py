import matplotlib.pyplot as plt
import pandas as pd
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei']
plt.rcParams['axes.unicode_minus'] = False

# 读取数据
df = pd.read_csv(BASE_DIR / 'trace.csv')
df['created_at'] = pd.to_datetime(df['created_at'])
df = df.sort_values('created_at')

# 按小时统计
df['hour'] = df['created_at'].dt.floor('h')
hourly_counts = df.groupby('hour').size()

# 创建图形
fig, ax = plt.subplots(figsize=(14, 6))

x = range(len(hourly_counts))
y = hourly_counts.values

ax.plot(x, y, marker='o', linewidth=2, markersize=4, color='#2E86AB')
ax.fill_between(x, y, alpha=0.3, color='#2E86AB')

# 设置x轴标签
labels = [str(h)[-8:-3] for h in hourly_counts.index]  # 只显示小时:分钟
ax.set_xticks(x[::5])
ax.set_xticklabels([labels[i] for i in range(0, len(labels), 5)], rotation=45)

ax.set_xlabel('时间 (小时)', fontsize=12)
ax.set_ylabel('声量 (动作数)', fontsize=12)
ax.set_title('维度一：模拟数据 声量分布', fontsize=14, fontweight='bold')
ax.grid(True, alpha=0.3)

# 标注峰值
# max_idx = y.argmax()
# ax.annotate(f'峰值: {y[max_idx]}', xy=(max_idx, y[max_idx]),
#             xytext=(max_idx+2, y[max_idx]+50),
#             arrowprops=dict(arrowstyle='->', color='red'),
#             fontsize=10, color='red')

plt.tight_layout()
plt.savefig(OUTPUT_DIR / 'dim1_声量分布按小时.png', dpi=150, bbox_inches='tight')
plt.show()