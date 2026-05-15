# 微博智能体链路与画像输入说明

## 目的

本文档用于交接微博新链路当前的实现方式，说明本轮画像补强改了什么、微博智能体如何从数据集生成、哪些信息进入了大模型 prompt、哪些信息没有进入，以及 vLLM 全量验证暴露出的质量风险。

数据源固定为 `weibo_test/total_data_with_descriptions_transformers.json`。当前数据集共有 100 条用户记录。

## 本轮改动范围

本轮改动只面向微博新链路，默认不影响原始 OASIS、Twitter、Reddit 链路。

主要文件：

- `oasis/weibo/profile_builder.py`：新增微博画像构造逻辑。
- `oasis/weibo/generator.py`：微博 agent 生成入口改用画像 builder。
- `oasis/weibo/agent.py`：微博 agent 默认使用中文系统提示词。
- `oasis/weibo/__init__.py`：导出微博 builder 和生成函数。
- `examples/weibo_simulation_vllm.py`：vLLM 入口使用微博专属 agent，并支持 `WEIBO_MAX_TOKENS`。
- `examples/weibo_simulation_api_qwen35_you.py`：DeepSeek 配置走 DeepSeek 专属模型类型，规避工具 schema strict 兼容风险。
- `docs/weibo_agent_profile_audit.md`：回答“智能体建模时取了哪些属性”的审计报告。

## 微博链路运行原理

微博链路的核心流程如下：

1. `generate_weibo_agent_graph()` 读取微博 JSON 数据集。
2. 每条用户记录通过 `build_user_identity()` 提取身份信息。
3. 每条用户记录通过 `build_user_profile()` 构造中文画像摘要。
4. `UserInfo` 保存用户名、显示名、简介、微博画像、微博 ID、关注关系 payload 和 `recsys_type="weibo"`。
5. `WeiboSocialAgent` 使用 `build_weibo_system_message()` 生成中文系统提示词。
6. OASIS 环境 `env.reset()` 注册用户，并初始化推荐系统缓存。
7. LLM 回合中，agent 读取当前微博环境描述，再通过工具调用执行 `create_post`、`refresh`、`search_posts`、`repost`、`create_comment` 等微博动作。
8. 执行动作写入 SQLite 数据库的 `trace`、`post` 等表，便于后续审计。

`generate_weibo_agents()` 还支持在平台中种入历史发帖：它会读取 `近期发帖内容分析.全部帖子合集`，默认每个 agent 最多写入 5 条历史帖。当前主要全量 smoke 使用的是 `generate_weibo_agent_graph()`，因此不会把所有历史发帖直接写入平台。

## 已读入的身份与画像信息

当前 builder 只读取微博数据集中真实存在且有有效值的字段。进入 `user_profile` 的字段包括：

- 身份信息：`个人基本信息.用户名`
- 简介信息：`个人基本信息.用户简介`
- 性别信息：`个人基本信息.用户性别`
- 账号等级：`个人基本信息.微博等级`
- 影响力：`社交影响力.粉丝数量`、`社交影响力.粉丝等级`
- 认证与层级：`账号类型与层级.用户认证信息`、`账号类型与层级.用户层级`
- 发帖行为：`用户行为特征.总发帖数`、`用户行为特征.发帖密度`
- 互动行为：`用户行为特征.互动密度`
- 活跃行为：`用户行为特征.活跃天数`、`用户行为特征.活跃时间分布`
- 兴趣关键词：`用户行为特征.keywords_list`
- 内容偏好：`标签特征.内容偏好`
- 情感倾向：`标签特征.情感倾向`
- 社交关注：`关注博主信息.关注数`、`关注博主信息.follows`
- 近期表达：`近期发帖内容分析.全部帖子合集`
- 互动统计：`社交影响力.转评赞统计`

其中 `用户ID` 会读入并赋给 `user_info.weibo_id`，用于注册和映射，不写入画像 prompt。

## 长字段的截断与摘要规则

当前不是把 JSON 中所有长文本和列表原样塞进 prompt，而是做了低风险摘要：

- `近期发帖内容分析.全部帖子合集`：每个用户最多取前 3 条，清理 HTML 标签后进入 `近期发帖样例`。
- `用户行为特征.keywords_list`：最多取前 5 个关键词及频次。
- `标签特征.内容偏好`：解析 JSON 字符串后最多取前 5 个偏好项。
- `关注博主信息.follows`：平台关系 payload 中读取完整关注 ID 和互动次数；prompt 中只放前 5 个关注博主摘要。
- `社交影响力.转评赞统计`：只摘要总转发数、总评论数、总点赞数、总互动数。

这样做的原因是避免 prompt 过长、避免整条原始记录污染上下文，并降低回滚和排查成本。

## 明确删除或不进入 prompt 的信息

当前微博数据中不存在或不适合作为画像入口的字段已经从新链路中删除：

- `年龄`
- `age`
- `MBTI`
- `mbti`
- `followers`
- `用户昵称`
- `个人基础信息`
- `country`
- `raw_record`

存在但当前不进入 prompt 的字段：

- `地区信息`：当前 100 条均为 `未知`。
- `职业`：当前 100 条均为 `未知`。
- `教育背景`：当前 100 条均为 `未知`。
- `账号类型`：数字编码，数据集中没有编码说明。
- `认证类型`：数字编码，数据集中没有编码说明。
- `权重系数`：更像算法权重，不适合作为用户人设。

如果后续需要使用数字编码字段，应先补充编码含义说明，再通过中文可解释文本进入画像，而不是直接把数字写进 prompt。

## 模型运行优先级

微博模型运行遵循“优先 vLLM，失败后再用 API 兜底”的原则：

1. 优先检查 `WEIBO_VLLM_ENDPOINTS`、`WEIBO_VLLM_MODEL` 和可访问的 `/v1/models`。
2. vLLM 可用时，先做单 agent tool-call smoke，再做小规模 agent 回合，最后做全量一轮。
3. vLLM 不可用时，再读取 `.env` 中的 DeepSeek 或 Qwen API 配置。
4. DeepSeek 需要走 CAMEL 的 `ModelPlatformType.DEEPSEEK`，避免普通 OpenAI-compatible 后端保留工具 schema 的 `strict` 字段导致兼容问题。
5. Qwen/DashScope 可走 OpenAI-compatible 接口，但也必须先做单 agent smoke。

API key 只从环境变量或 `.env` 读取，不写入代码、文档、日志或提交历史。

## 当前验证结果

已完成的关键验证：

- 画像构造：100 条数据均可构造中文画像。
- 删除字段检查：新微博链路不再读取 `年龄`、`MBTI`、`followers`、`用户昵称`、`个人基础信息` 等不存在入口。
- DeepSeek smoke：单 agent 工具调用通过。
- DeepSeek 小流量一轮：3 个 LLM agent 工具调用通过。
- vLLM 远端 `10.12.208.150:9020` 单 agent smoke：通过。
- vLLM 远端 `10.12.208.150:9020` 3 agent 一轮：通过。
- vLLM 远端 `10.12.208.150:9020` 100 agent 全量一轮：通过。

最新全量一轮测试配置：

- vLLM 地址：`http://10.12.208.150:9020/v1`
- 模型：`/mnt/disk3/Models/LIYOU_HF_HOME/hub/models--Qwen--Qwen3-4B/snapshots/1cfa9a7208912126459214e8b04321603b3df60c`
- `max_tokens=4096`
- `temperature=0.2`
- 并发：`10`
- 数据库：`/tmp/oasis_weibo_vllm_full_round_latest.db`

最新全量一轮结果：

- 注册用户：`sign_up:100`
- LLM 回合动作：`create_post:98`、`create_comment:1`、`do_nothing:1`
- 扣除 1 条手动种子微博后，LLM 产生 97 条原创发帖。
- 97 条 LLM 原创中，不同文本 80 条，精确重复 17 条。
- 未发现 error trace。

## 当前主要风险

链路能跑通，但生成质量存在明显复读风险。原因不是没有读画像，而是数据集中高频关键词高度集中：

- 100 个用户里有 98 个用户的 `keywords_list` 包含 `#祖国山河一寸不能丢#`。
- 最新全量一轮非种子帖子中，`祖国山河` 出现 88 条，`边防` 出现 65 条，`致敬` 出现 73 条。
- 重复最多的文本“致敬边防军人！致敬英雄！🇨🇳 #祖国山河一寸不能丢#”出现 6 次。

因此，当前问题不是“智能体没有输入有效画像”，而是“有效画像中某些关键词过于同质，导致模型生成主题塌缩”。

## 后续建议

建议下一轮优先做生成质量控制，而不是盲目把全部历史微博塞进 prompt：

1. 对 `近期发帖样例` 做去重和多样性采样，不固定取前 3 条。
2. 对 `keywords_list` 做主题去重，避免单一高频标签垄断 prompt。
3. 在微博系统提示词中增加约束：不要照抄历史样例原句，不要所有用户围绕同一标签发帖。
4. 对全量历史微博做主题摘要或聚类摘要，而不是原文全量注入。
5. 保留 `max_tokens=4096` 的 vLLM 默认值；如果继续出现上下文截断，再压缩画像或提高服务端上下文配置。

## 回滚方式

如需回滚本轮微博画像补强：

1. 删除 `oasis/weibo/profile_builder.py`。
2. 恢复 `oasis/weibo/generator.py` 中原始画像构造和关注关系读取逻辑。
3. 恢复 `oasis/weibo/agent.py` 中默认 `UserInfo.to_system_message()` 调用。
4. 恢复 `examples/weibo_simulation_vllm.py` 和 `examples/weibo_simulation_api_qwen35_you.py` 的模型构造逻辑。
5. 删除或标注废弃 `docs/weibo_agent_profile_audit.md` 和本文档。
