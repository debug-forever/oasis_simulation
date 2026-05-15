# 舆情可视化 + 关键人物/群体识别 — 海选 Demo

独立 demo（不影响现有 `visualization_system` 前端），用新闻学/传播学指标 + 视觉分析特征暴露范式
做了 12 张候选图。

## 目录

```
sentiment_demo/
├── build_data.py     # 一次性预处理；DB → data/*.json
├── data/             # 13 个 JSON（含一个 overview）
├── index.html        # 单页 gallery
└── README.md
```

## 运行

```powershell
cd visualization_system\prototypes\sentiment_demo

# 1. 预处理（首次约 5-10s）
python build_data.py

# 2. 起本地 http server
python -m http.server 8081

# 3. 浏览器
#   http://localhost:8081/
```

切换 DB 改 `build_data.py` 顶部 `DB_PATH`。

## 12 张候选图

### A · 舆情视图（嵌入新闻学/传播学指标）

| # | 名称 | 对应理论 / 论文 |
|---|---|---|
| **A1** | 议题生命周期总览 | Issue-Attention Cycle (Downs 1972) |
| **A2** | 议程对照 媒体 vs 公众 | Agenda Setting (McCombs & Shaw 1972) |
| **A3** | 情感时序流 | Sentiment lexicon (Pang & Lee 2008) |
| **A4** | 框架光谱演化 + 框架×社区矩阵 | Framing (Entman 1993) |
| **A5** | 群体极化雷达 + ER 指数 | Conover 2011 + Esteban-Ray 1994 |
| **A6** | 沉默的螺旋曲线 | Noelle-Neumann 1974 |
| **A7** | 舆情风险仪表盘 (红/橙/黄/蓝) | 行业实务综合 |

### B · 关键人物 / 关键群体识别

| # | 名称 | 方法 / 论文 |
|---|---|---|
| **B1** | 群体雷达图谱（6 种群体定义） | Munzner Vis A&D + Bertin small-multiples |
| **B2** | 关键人物多维仪表 (PCP + SPLOM) | Inselberg 1985 + Wang TVCG 2014 |
| **B3** | 角色四象限 | Burt 1992 (structural holes) + Gleave HICSS 2009 |
| **B4** | KOL 蜂群时间轴 | Wongsuphasawat LifeFlow 2011 |
| **B5** | 群体演化 Sankey | Liu TVCG 2013 (StoryFlow) |

## 关键设计选择

- **群体的 6 种定义**（B1）：因为本数据集没有显式人口学标签，我们提供 6 种可用的群体生成方式：
  - G1 网络社区 (Louvain on follow graph)
  - G2 行为画像簇 (KMeans on action shares)
  - G3 角色（bio 关键词规则：官媒/科技博主/商家/生活/普通）
  - G4 影响力分层（粉丝数 quantile 50/90）
  - G5 立场簇（pro-Huawei / pro-Apple / 中立 / 未表态）
  - G6 时段画像（小时分布 modal）
  并排呈现可选择最有解释力的切群方式。

- **情感分析**：纯规则 + 中文情感词典（消费科技场景定向）+ 否定语境窗口（3 字符回溯）。
  优点：零模型依赖，秒级出结果，可解释；缺点：对反讽/隐喻不敏感。

- **立场分类**：每篇内容里 brand-mention 周围 ±10 字窗口的情感分数差，配合显式宣示词。

- **风险综合分**：5 维加权（声量增速 / 负面占比 / 跨群扩散 / KOL 涉入 / 立场极化）→ 0-100，
  对照红橙黄蓝四级。权重写死在 `build_risk()` 中，可按业务需求调。

## 当前数据集上的关键发现

- **议题生命周期**：明显的 burst 出现在第 25 小时左右（约一天后），衰退期占整体时长的 28%。
- **议程相关性**：媒体与公众议程 Spearman ρ ≈ 0.97，议程一致性极高（华为相关议题的强主导）。
- **情感构成**：正向 522 / 中立 571 / 负向 5。在该模拟设定下，舆情几乎一边倒正面。
- **极化指数**：ER index 仅 0.011 — **几乎没有极化**，所有社区均偏亲华为。
- **沉默的螺旋**：少数派（亲苹果）只有 1 个用户，从仿真开始就处于"已沉默"状态。
- **角色构成**：100 个用户中 Broker 48 / Amplifier 45 / Influencer 4 / Resonator 3 — Influencer 稀少，
  舆情主要靠 Amplifier 转发推动。
- **风险等级**：当前综合分 ~31，处于黄色"关注"边缘，主要由 KOL 涉入度（0.79）拉高。

## 推广到 10K 用户时的注意点

- 几乎所有视图都是聚合/降维结果，10K 数据下渲染压力可控。
- B2（PCP）建议初始仅显示 top-1% KOL + 5% 抽样，brushing 后扩展。
- B4（KOL 蜂群）取 followers top-100；事件多时按时间 zoom。
- B5（Sankey）节点数 = 窗口×类别，远小于用户数，不受规模影响。
- 预处理脚本可改为增量 / 缓存版本：分量级 metric 写回单独 cache 表，前端只读聚合。

## 局限 / 后续可升级方向

- **情感词典** 是手工小词典；上规模后建议替换为中文 BERT/RoBERTa fine-tune 模型（uer/roberta-finetuned-jd-binary-chinese）。
- **frame keyword set** 是消费科技领域硬编码；不同事件主题需要重新设计 frame。
- **立场分类** 只支持 pro_hw / pro_ap 两极；多议题事件需要扩展为 multi-stance 模型。
- **群体时间演化 (B5)** 当前以 5 个等长窗口切分；可以接入更细 trace 窗口或滑动窗口。
