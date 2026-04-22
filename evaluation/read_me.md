# 舆情模拟仿真评估

本文件夹包含一套完整的社交网络仿真评估脚本，用于从五个维度评估模拟数据与真实数据的匹配程度。

---

## 目录结构

```
evaluation/
├── 核心脚本
│   ├── dbtocsv.py                # 数据库导出工具
│   ├── dim1_evaluation.py        # 维度一：事件参与度评估
│   ├── dim2_evaluation.py        # 维度二：评论语义评估
│   ├── dim3_evaluation.py        # 维度三：用户动作预测评估
│   ├── dim4_evaluation.py        # 维度四：角色一致性评估
│   ├── dim5_evaluation.py        # 维度五：传播网络评估
│   ├── dim1_plot.py              # 维度一：声量可视化
│   ├── dim2_plot.py              # 维度二：情感分布可视化
│
├── groundtruth/                  # 真实数据目录
│   └── top100_users_complete_data_post_followers.json
│
└── output/                       # 输出目录
    ├── output1.log ~ output5.log
    └── *.png                    # 可视化图表
```

---

## 快速开始

### 1. 数据库导出（第一步）

首先需要将模拟数据库导出为 CSV 文件：

```bash
python dbtocsv.py
```

这将生成 `user.csv`, `post.csv`, `comment.csv`, `trace.csv` 四个文件。

### 2. 运行各维度评估

每个维度脚本会自动执行预处理+正式评测：

```bash
# 维度一：事件参与度
python dim1_evaluation.py

# 维度二：评论语义评估（需要 BERT 模型）
python dim2_evaluation.py

# 维度三：用户动作预测
python dim3_evaluation.py

# 维度四：角色一致性（需要 OpenAI API）
python dim4_evaluation.py

# 维度五：传播网络结构
python dim5_evaluation.py
```
---

## 各维度详细配置

### 维度一：事件参与度评估

**脚本**: `dim1_evaluation.py`

**评估内容**:
- 用户参与率
- 人均互动次数（评论+转发）
- 内容产出量（发帖数）
- 仿真声量与真实声量对比（Trend MAPE、NRMSE）

**输入文件**:
- `post.csv` - 模拟帖子数据
- `comment.csv` - 模拟评论数据
- `user.csv` - 模拟用户数据
- `trace.csv` - 行为轨迹数据
- `groundtruth/top100_users_complete_data_post_followers.json` - 真实用户数据

**输出**: `output/output1.log`

---

### 维度二：评论语义评估

**脚本**: `dim2_evaluation.py`

**评估内容**:
- 情感分布的 10-bin 直方图 Pearson 相关系数
- 情感分类（正/中/负）的 KL 散度

**方法**: 使用 BERT 多语言情感分析模型 (`nlptown/bert-base-multilingual-uncased-sentiment`)

**依赖**: `transformers`, `torch`, `scipy`

**输入文件**: 与维度一相同

**输出**: 
- `output/output2.log`
- `sim_df_with_score.csv` - 带情感分数的模拟评论
- `real_df_with_score.csv` - 带情感分数的真实评论

---

### 维度三：用户动作预测评估

**脚本**: `dim3_evaluation.py`

**评估内容**:
- 动作数量归一化误差 (Normalized Error)
- 行为向量 Cosine 相似度 & Pearson 相关系数
- 动作是否发生的二分类指标 (Accuracy, Precision, Recall, F1)

**动作类型**: 点赞 (`n_like`)、评论 (`n_comment`)、转发 (`n_repost`)、发帖 (`n_post`)

**输入文件**: 与维度一相同

**输出**: 
- `output/output3.log`
- `agent_action_vector_sim.csv` - 模拟动作向量
- `agent_action_vector_real.csv` - 真实动作向量

---

### 维度四：角色一致性评估

**脚本**: `dim4_evaluation.py`（并行版）

**评估内容**:
- 智能体生成文本与人物设定的语义一致性
- 平均角色一致性评分

**方法**: 使用 LLM 作为评判模型，对每条生成文本打分 (1-5分)

**环境变量配置**:

```bash
# 设置 OpenAI API 配置
export OPENAI_API_KEY="your-api-key"
export OPENAI_BASE_URL="your-base-url"
export OPENAI_MODEL="your-model-name"
```

**并发配置**: 默认 10 个并发线程 (`MAX_WORKERS = 10`)

**输入文件**: 与维度一相同

**输出**: 
- `output/output4.log`
- `agent_personas.json` - 智能体人设
- `role_consistency_all_texts.csv` - 详细评分结果

---

### 维度五：传播网络评估

**脚本**: `dim5_evaluation.py`

**评估内容**:
- 级联规模 (Size) 误差
- 级联深度 (Depth) 误差
- 级联广度 (Breadth) 误差
- 度分布 KS 检验 / 幂律分布检验
- 核心传播节点对比

**方法**: 使用 NetworkX 构建有向传播图

**输入文件**: 
- `post.csv` - 模拟帖子数据（用于构建转发关系）
- `user.csv` - 模拟用户数据
- `groundtruth/top100_users_complete_data_post_followers.json` - 真实用户数据

**输出**: 
- `output/output5.log`
- `agent_follows.csv` - 真实关注关系

---

## 依赖安装

```bash
pip install pandas numpy scipy transformers torch networkx openai scikit-learn matplotlib
```

---

## 可视化

运行独立可视化脚本：

```bash
# 维度一：声量分布可视化
python dim1_plot.py

# 维度二：情感分布可视化（需要先运行dim2_evaluation.py生成带分数的数据）
python dim2_plot.py
```

---

## 注意事项

1. **维度二**: 首次运行会下载 BERT 模型（约 400MB）
2. **维度四**: 需要有效的 API Key，支持环境变量配置
3. **所有输出**: 默认保存到 `output/` 目录