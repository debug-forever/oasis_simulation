# 微博改造工作日志

## 计划（2025-12-05 05:31:20）
1. 在 docs/weibo_migration_log.md 中维护全过程记录，确保任何一步都有描述、时间戳与原因。
2. 依托 weibo_test/total_data_with_descriptions_transformers.json 分析字段语义，制定与现有 Agent/Platform 结构的映射策略。
3. 通过新增微博専属模块完成 Agent 生成、历史发帖/关注关系导入，并屏蔽微博不存在的操作；尽量复用既有 API，仅在必要处新增文件。
4. 结合提供的数据集运行验证/测试，将执行命令、结果与问题逐条写入本日志。

## 进展记录
### 2025-12-05 05:31:20 建立日志并写入计划
- 新建文件 `docs/weibo_migration_log.md`，采用 UTF-8 编码，写入上述计划，满足“所有提示必须中文且有日志”的约束。
- 目的：形成唯一的信息源，后续步骤（数据分析、编码、测试）全部在此文记录，以便追溯。

### 2025-12-05 05:31:39 分析微博标注数据
- 运行 `python tmp_inspect.py` 读取 `weibo_test/total_data_with_descriptions_transformers.json`，输出记录数、字段名，并捕捉示例内容；为避免 PowerShell GBK 编码报错，转义为 `unicode_escape`。
- 识别到的主要字段：`用户ID`、`个人基础信息`（含用户名/性别/简介等）、`社会影响力`、`关注与互动信息`（内嵌 follows 字典）、`内容创作分布`（含“全部帖子合集”文本列表）、`用户行为画像`、`标签信息`。
- 目的：确认微博数据确实提供建档、关注关系、历史发帖等所需信息，便于下一步映射。

### 2025-12-05 05:32:34 形成详细适配方案
- 在日志中写入“适配方案”段落，明确：
  * `个人基础信息` → `UserInfo.user_name/name/description`，原始字段存入 `profile.other_info` 供 LLM 参考。
  * `内容创作分布-全部帖子合集` → 历史微博，限制每代理最多 5 条，通过 `SocialAction.create_post` 导入 sqlite。
  * `关注与互动信息-follows` → 遍历关注关系，仅在目标存在于数据集时调用 `follow` 并更新 `AgentGraph.add_edge`。
  * `标签信息`、`社会影响力`、`用户行为画像` 等统计字段写入 `profile`；不派生额外逻辑，减少对核心平台的修改。
  * 可用动作限定为微博常见操作：发帖/转发/评论/点赞/关注/搜索/刷新/趋势/无动作，避免触发 Reddit 专属的踩、点踩、静音等。
- 目的：把“如何映射/为什么这样做”固定下来，防止后续实现偏离。

### 2025-12-05 05:34:52 开始实现微博生成模块
- 根据“少动原文件”要求，新建 `oasis/social_agent/weibo_generator.py`，集中封装微博逻辑：
  * `_safe_str`、`_clean_content`：统一处理字符串与 HTML，保证导入内容干净。
  * `_build_user_profile`：把基础信息/影响力/画像/标签串联成 profile，兼容现有 `UserInfo` 模板；额外把原始记录保存在 `raw_record`，方便调试。
  * `get_default_weibo_actions`：列出微博允许的动作（CREATE_POST、REPOST、CREATE_COMMENT、LIKE_POST、FOLLOW、SEARCH、TREND、REFRESH、DO_NOTHING），确保 LLM 行为受限。
  * `load_weibo_dataset`：独立的 JSON 读取入口（UTF-8 强制），满足“所有操作集中在新文件”原则。
  * `generate_weibo_agents`：核心流程——(1) 读取数据并按顺序创建 `SocialAgent`；(2) 调用 `sign_up` 获取平台 `user_id` 并建立数据集 ID → user_id/agent_id 映射；(3) 根据 `follows` 建立关注关系；(4) 从“全部帖子合集”中取最多 5 条文本，逐条调用 `create_post`，实现最小化历史同步。
- 在日志中记录“开始”节点，后续每次关键操作（编码、测试、完成）都会追加描述。
### 2025-12-05 05:38:14 微博生成模块编码进展
- 新建 `oasis/social_agent/weibo_generator.py`，集中实现微博所需函数：`_safe_str`、`_clean_content`、`_build_user_profile`、`get_default_weibo_actions`、`load_weibo_dataset`、`generate_weibo_agents`。这些函数负责：
  1) 统一字符串与 HTML 处理，保证写入平台的内容不会夹杂标签或额外空白；
  2) 根据提供的数据字段拼接 `profile.other_info`，并将原始记录保存在 `raw_record` 便于追溯；
  3) 限定微博可用动作列表，屏蔽踩、点踩、静音等 Reddit 特有逻辑；
  4) 按顺序注册代理、建立关注关系、导入历史帖子。整套流程全部通过原有 `SocialAction.sign_up/follow/create_post` 接口完成，实现“多复用原函数”的要求。
- 将 `generate_weibo_agents` 在 `oasis/social_agent/__init__.py` 中曝光：重新写入文件，先引入 `from .weibo_generator import generate_weibo_agents`，再把 `__all__` 扩展为包含 `"generate_weibo_agents"`。这样其他模块可直接 `from oasis.social_agent import generate_weibo_agents`，而无需修改 `agents_generator.py` 主体。
- 当前仍需：为默认平台类型增加微博分支、将该生成函数串入运行入口、并编写/执行测试脚本，上述任务将在后续步骤继续推进。
### 2025-12-05 05:38:49 开始：平台类型与运行入口适配
- 计划修改 `oasis/social_platform/typing.py`，新增 `DefaultPlatformType.WEIBO` 常量（如需要也可扩展 `RecsysType`）。
- 更新 `oasis/environment/env.py`：为新平台分支实例化 `Platform`，沿用 Reddit 推荐逻辑但隐藏 Reddit 加分项；同时在“自定义 Platform”分支识别 `platform.platform_type`，避免后续运行误判。
- 目标：保证环境层能够以 `DefaultPlatformType.WEIBO` 启动，并与 `generate_weibo_agents` 输出的 AgentGraph 协同。
### 2025-12-05 05:40:05 平台类型适配完成
- `oasis/social_platform/typing.py`：在 `DefaultPlatformType` 中新增 `WEIBO = "weibo"`，保持 `RecsysType` 不变（仍复用 `reddit` 逻辑），满足“微博作为独立平台类型”需求。
- `oasis/environment/env.py`：
  1) 在 `DefaultPlatformType` 分支下新增 `WEIBO` 逻辑，实例化 `Platform` 时复用 `recsys_type="reddit"`，关闭 `show_score` 并将对象打上 `platform_type` 标记，保证推荐算法沿用 Reddit 热度。
  2) 扩展错误提示为 “TWITTER/REDDIT/WEIBO”。
  3) 当用户传入自定义 `Platform` 时，优先读取 `platform.platform_type`，若为 WEIBO 则对应设置；否则按原逻辑依据 `recsys_type` 判断 Reddit/Twitter。
- 以上修改确保 `OasisEnv` 可通过 `DefaultPlatformType.WEIBO` 创建微博平台，同时不破坏既有平台路径。
### 2025-12-05 05:43:24 示例脚本与测试
- 新增 `examples/weibo_seed_demo.py`：提供如何以 `DefaultPlatformType.WEIBO` 初始化 Channel/Platform、调用 `generate_weibo_agents`、关闭平台的完整流程，脚本内部会：
  1) 删除/重建 `weibo_test/weibo_demo.db`；
  2) 创建 `Platform`（复用 reddit 推荐参数，关闭 show_score，并打上 `platform_type` 标记）；
  3) 运行 `generate_weibo_agents` 将全部 100 条标注数据写入 sqlite；
  4) 发送 `ActionType.EXIT` 以优雅结束平台任务，终端输出导入数量。
- 运行脚本时发现 `UserInfo.to_reddit_system_message` 中遗留的调试 `print(self.profile['other_info'])` 造成 GBK 编码报错，现已删除该行以避免中文/emoji 内容退出。
- 由于 `SocialAgent` 初始化依赖 `OPENAI_API_KEY` 环境变量，测试阶段临时设为 `'test'` 以通过校验（脚本本身不调用 LLM，不会实际访问 OpenAI）。
- 执行 `$env:OPENAI_API_KEY='test'; python examples/weibo_seed_demo.py`，终端输出 `已将 100 个微博代理写入 weibo_test\weibo_demo.db`，验证导入流程与微博专属逻辑可用。
### 2025-12-05 05:50:55 新微博实验计划
- 目标：基于 `examples/twitter_simulation_openai.py` 与 `examples/twitter_simulation_vllm.py` 复制出微博版本示例，涵盖 OpenAI 与 vLLM/DeepSeek/Qwen 场景，保持所有交互中文。
- 要求：新脚本需调用 `DefaultPlatformType.WEIBO`、使用 `generate_weibo_agents` 或微博数据，并在提示词/打印信息中统一中文；文档需同步更新，记录逻辑与使用方式。
- 输出：完成后追加中文使用说明，含 API 配置、运行命令、两类模型后端差异。
### 2025-12-05 05:50:55 新微博实验计划
- 目标：基于 `examples/twitter_simulation_openai.py` 与 `examples/twitter_simulation_vllm.py` 复制出微博版本示例，涵盖 OpenAI 与 vLLM/DeepSeek/Qwen 场景，保持所有交互中文。
- 要求：新脚本需调用 `DefaultPlatformType.WEIBO`、使用 `weibo_test` 标注数据，并在提示词/打印信息中统一中文；文档需同步更新，记录逻辑与使用方式。
- 输出：完成后追加中文使用说明，含 API 配置、运行命令、两类模型后端差异。
### 2025-12-05 05:54:23 微博实验代码实现
- `oasis/social_agent/weibo_generator.py`：新增 `generate_weibo_agent_graph`，与 `generate_twitter_agent_graph` 类似，仅根据微博 JSON 构建 `AgentGraph`，供环境在 `reset` 阶段统一注册帐号，避免重复写库。
- `examples/weibo_simulation_openai.py`：
  * 整体逻辑沿用 Twitter OpenAI 实验，但切换到 `DefaultPlatformType.WEIBO` 与 `generate_weibo_agent_graph`。
  * `build_llm_model` 支持 `WEIBO_MODEL_PROVIDER=openai|deepseek|qwen`，当取值为 `deepseek/qwen` 时自动切到 `ModelPlatformType.OPENAI_COMPATIBLE` 并允许自定义 `WEIBO_COMPATIBLE_API_URL`。
  * 所有手工动作、提示与日志均改为中文。通过 `WEIBO_ENABLE_LLM` 控制是否真的触发 `LLMAction`，方便在无 API 的情况下做干跑测试。
- `examples/weibo_simulation_vllm.py`：
  * 提供 vLLM/Qwen 私有部署示例，读取 `WEIBO_VLLM_ENDPOINTS`（逗号分隔多个 URL）和 `WEIBO_VLLM_MODEL`，利用 `ModelManager` 轮询多台推理服务。
  * 同样通过 `WEIBO_ENABLE_LLM` 控制是否真正调用模型，默认仅执行人工动作，便于在未部署 vLLM 时跑通流程。
- 两个脚本都指定 `DATASET_PATH=weibo_test/total_data_with_descriptions_transformers.json`，确保实验与最初数据集保持一致。
### 2025-12-05 05:56:21 测试记录
- `$env:OPENAI_API_KEY='test'; WEIBO_ENABLE_LLM=0; python examples/weibo_simulation_openai.py`：脚本在禁用 LLM 情况下完成两次手动发帖，平台顺利生成 `weibo_sim_openai.db`。终端提示“未启用 LLM 行动”，验证跳过逻辑正常，执行完毕后删除测试数据库。
- `WEIBO_ENABLE_LLM=0; python examples/weibo_simulation_vllm.py`：在缺少真实 vLLM 服务的情况下，通过轮询两个假地址完成流程，控制台出现 `max_tokens` 的兼容性 warning（vLLM 端点未返回配置所致），但脚本继续运行并生成 `weibo_sim_vllm.db`，随后清理测试数据库。提醒实际部署时自行配置端点与模型参数。
### 2025-12-05 05:56:36 新实验使用说明（OpenAI/DeepSeek/Qwen + vLLM）
1. **共通逻辑**：两个脚本都会读取 `weibo_test/total_data_with_descriptions_transformers.json`，借助 `generate_weibo_agent_graph` 生成 100 位代理并交由 `DefaultPlatformType.WEIBO` 平台统一注册。所有提示、打印、示例内容均为中文，动作集合限定为微博常见行为（发帖、评论、搜索等）。
2. **数据库配置**：脚本启动前会自动删除旧库并设置 `OASIS_DB_PATH`。如需保留结果可修改 `DB_PATH`，或在运行结束后备份 `weibo_test/weibo_sim_*.db`。
3. **OpenAI/DeepSeek/Qwen 脚本**（`examples/weibo_simulation_openai.py`）
   - `WEIBO_MODEL_PROVIDER`：`openai`（默认）、`deepseek` 或 `qwen`。
   - `WEIBO_MODEL_NAME`：自定义模型名，例如 `deepseek-chat`、`qwen-plus`。
   - `WEIBO_COMPATIBLE_API_URL`：当 provider=deepseek/qwen 时指定兼容模式基地址（默认分别为 `https://api.deepseek.com/v1`、`https://dashscope.aliyuncs.com/compatible-mode/v1`）。
   - `OPENAI_API_KEY` 或兼容 API Key 必须设置；若仅做流程验证，可使用假值并保持 `WEIBO_ENABLE_LLM=0`，脚本会跳过 `LLMAction` 回合。
4. **vLLM / 私有 Qwen 服务脚本**（`examples/weibo_simulation_vllm.py`）
   - `WEIBO_VLLM_ENDPOINTS`：逗号分隔的多个推理端点，例如 `http://10.0.0.1:8080/v1,http://10.0.0.2:8080/v1`。
   - `WEIBO_VLLM_MODEL`：部署在 vLLM 的模型代号，默认 `qwen-2`。
   - 可与 DeepSeek/Qwen 的 OpenAI 兼容 API 并存（一个脚本用兼容 API，另一个脚本用 vLLM），都通过 `WEIBO_ENABLE_LLM=1` 控制是否真实发起 LLM 调用。
5. **运行示例**：
   - OpenAI/DeepSeek/Qwen：`$env:OPENAI_API_KEY='<your_key>'; $env:WEIBO_MODEL_PROVIDER='deepseek'; $env:WEIBO_ENABLE_LLM='1'; python examples/weibo_simulation_openai.py`
   - vLLM/Qwen：`$env:WEIBO_VLLM_ENDPOINTS='http://server1:8000/v1,http://server2:8000/v1'; $env:WEIBO_VLLM_MODEL='qwen-2.5'; $env:WEIBO_ENABLE_LLM='1'; python examples/weibo_simulation_vllm.py`
6. **测试模式**：若尚未配置可用模型，只需保持 `WEIBO_ENABLE_LLM=0` 即可执行手动动作验证数据库写入；完成后请删除生成的 `.db`，避免污染仓库。
### 2025-12-05 05:59:29 修复脚本平台常量
- 运行 DeepSeek 模式时报 `ModelPlatformType` 缺少 `OPENAI_COMPATIBLE`，确认 camel 仅提供 `OPENAI_COMPATIBLE_MODEL` 常量。
- 更新 `examples/weibo_simulation_openai.py` 的 `build_llm_model`，当 provider=deepseek/qwen 时改用 `ModelPlatformType.OPENAI_COMPATIBLE_MODEL`，继续沿用可配置 base_url 逻辑，确保脚本可创建兼容模型实例。
### 2025-12-05 06:07:49 编码与示例数据修复
- `oasis/social_agent/agent_environment.py`：`json.dumps` 统一加 `ensure_ascii=False`，包含动态现有帖子、群聊列表、消息等内容，避免环境提示再显示 `\uXXXX`，满足中文呈现需求。
- `examples/weibo_simulation_openai.py`、`examples/weibo_simulation_vllm.py`：
  1) 引入 JSON 读取逻辑 `_load_weibo_records`+`_pick_post_text`，所有手动发帖文本直接采样自 `weibo_test/total_data_with_descriptions_transformers.json`，不再生造句子。
  2) 更新提示语，明确在禁用 LLM 时仍会把数据集中提取的中文内容写入数据库。
- 重新运行两个脚本（均设 `WEIBO_ENABLE_LLM=0`）验证：日志中所有中文内容均以原样展示，数据库写入与此前一致，运行后删除生成的 `.db` 以保持环境整洁。
### 2025-12-05 06:10:15 记录：修复日志编码
- 运行微博 OpenAI 脚本时，无论代理动作还是 LLM 回复都可能出现 emoji（如 🌿），导致 `social.agent` 日志的 `FileHandler` 使用系统默认 GBK 编码写入失败。
- 为彻底消除 UnicodeEncodeError，将 `oasis/social_agent/agent.py` 内的 `FileHandler` 显式设置 `encoding="utf-8"`，确保所有中文与 emoji 都能顺利写入日志文件。
### 2025-12-05 06:12:10 复测日志
- 已以 `OPENAI_API_KEY=test`、`WEIBO_ENABLE_LLM=0` 重跑 `examples/weibo_simulation_openai.py`，脚本完成全部手动动作，日志中 emoji（如 🌿）亦成功写入，无再出现 GBK 编码错误；测试结束后删除 `weibo_sim_openai.db`。
### 2025-12-05 06:20:05 需求更新
- 用户要求：所有模拟中的初始互动要基于微博数据集本身（如历史帖子、标签、用户简介），避免与数据无关的内容。
- 计划：调整脚本使手工动作与 `total_data_with_descriptions_transformers.json` 中的字段紧密关联，必要时引用用户简介/标签作为讨论主题，并在日志记录执行过程。
### 2025-12-05 06:25:26 数据驱动内容更新
- `examples/weibo_simulation_openai.py` 与 `examples/weibo_simulation_vllm.py`：新增 `_summarize_tags` / `_compose_post_content`，由微博 JSON 中的“个人基础信息”“标签信息”“内容创作分布”拼装人工发帖内容，使每条手动互动都直接引用真实用户简介、标签与原帖；辅助提示也声明内容来自数据集。
- 统一修正 `parts.join` 语句的换行编码，避免因行分割触发语法错误。
- 回归测试：
  * `$env:OPENAI_API_KEY='test'; WEIBO_ENABLE_LLM=0; python examples/weibo_simulation_openai.py`
  * `$env:WEIBO_ENABLE_LLM=0; python examples/weibo_simulation_vllm.py`
  两个脚本均只执行人工动作，日志显示内容均源自数据集字段，运行生成的数据库随后删除以保持工作区整洁。
### 2025-12-05 06:33:04 日志编码修复
- 针对新的提示词产生的 emoji（😊 等）依然会在控制台日志触发 GBK 报错。虽然文件输出已设为 UTF-8，但 `StreamHandler` 默认绑定到 GBK 控制台。
- 在 `oasis/social_agent/agent.py` 中新增 `sys.stdout/sys.stderr.reconfigure(encoding="utf-8", errors="replace")`，确保所有日志流都以 UTF-8 写入并对偶发字符做容错。
### 2025-12-08 15:50:06 新增运行脚本
- 在项目根目录添加 `run_weibo_simulation.sh`：包含 `#!/usr/bin/env bash`、`set -euo pipefail` 以及 DeepSeek 兼容接口所需环境变量。脚本要求调用者预先设置 `OPENAI_API_KEY`（或在外部 export），其他变量默认值与此前示例一致，最后执行 `python examples/weibo_simulation_openai.py`。
- 目的：将常用的微博 OpenAI/DeepSeek 模拟命令固化为一键脚本，便于替换密钥后直接运行。
### 2025-12-12 23:38:23 调整微博示例的发帖内容与提示
- `examples/weibo_simulation_openai.py`：
  * 新增 `_describe_persona`，在每次手工发帖前打印当前账号的“用户名/简介/标签/近期帖子”，保证操作者能看到个人信息；同时 `_compose_post_content` 仅返回微博文本本身，不再把自我介绍混入帖子内容。
  * `_summarize_tags`、`_pick_post_text` 调整为读取 `近期发帖内容分析/全部帖子合集` 和 `标签特征` 字段，默认文案为纯中文；新增 `_log_persona` 输出提示语。
  * 主流程在两处手工动作前调用 `_log_persona`，并将 fallback 文案改为中文说明，终端日志清晰展示账号信息。
- `examples/weibo_simulation_openai copy.py`：与 OpenAI 脚本保持一致，便于下游复用。
- `examples/weibo_simulation_vllm.py`：同步引入 `_describe_persona`、`_compose_post_content` 的变更，在 vLLM/私有 Qwen 脚本中也能看到账号信息且帖子只包含主题文本。
- 验证：
  * `$env:OPENAI_API_KEY='test'; WEIBO_ENABLE_LLM=0; python examples/weibo_simulation_openai.py`
  * `$env:WEIBO_ENABLE_LLM=0; python examples/weibo_simulation_vllm.py`
 运行均成功，手工发帖打印出“代理X 数据集信息”且数据库写入后已删除测试文件。
### 2025-12-12 23:44:46 日志编码彻底修复
- 发现 `social.agent` 日志仍向根 logger 传播，默认 `StreamHandler` 使用 GBK，导致包含 🇨🇳/emoji 的信息触发 UnicodeEncodeError。
- 在 `oasis/social_agent/agent.py` 中为 `agent_log` 设置 `propagate = False`，使其只写入 UTF-8 文件，不再传给根日志处理器。
- 重新运行 `$env:OPENAI_API_KEY='test'; WEIBO_ENABLE_LLM=0; python examples/weibo_simulation_openai.py`，确认控制台无编码报错；测试完删除 `weibo_sim_openai.db`。
### 2025-12-12 23:49:05 Emoji 过滤与交互修正
- `examples/weibo_simulation_openai.py`、`examples/weibo_simulation_openai copy.py`、`examples/weibo_simulation_vllm.py`：统一引入 `_EMOJI_PATTERN`、`_strip_emoji`，在 `_pick_post_text`、`_compose_post_content`、`_describe_persona` 中去除 emoji/变体，确保交互内容和终端日志不会再触发 GBK 编码错误。
- `_log_persona` 继续打印“智能体 X 数据集信息”，但文本已剔除 emoji；手动发帖内容也仅包含纯文本微博正文。
- 运行 `OPENAI_API_KEY='test'; WEIBO_ENABLE_LLM=0; python examples/weibo_simulation_openai.py` 以及 `WEIBO_ENABLE_LLM=0; python examples/weibo_simulation_vllm.py` 验证无报错。之后删除生成的数据库文件。
### 2025-12-13 00:09:55 LLM 日志编码修复与验证
- `oasis/social_agent/agent.py`：
  * 引入 `_LOG_SANITIZE_PATTERN` 和 `_sanitize_log_text`，为所有 LLM 相关的日志（观察环境、执行动作、函数结果等）自动剔除 emoji/特殊字符；
  * 在模块初始化阶段统一设置 stdout/stderr 为 UTF-8，并强制 root logger 使用 UTF-8 的 `StreamHandler`，防止默认 GBK 控制台继续产生编码错误；
  * 清理旧的重复 reconfigure 代码，确保日志只写入 UTF-8。
- `examples/weibo_simulation_openai.py` / `weibo_simulation_openai copy.py` / `weibo_simulation_vllm.py`：保留之前的 `_strip_emoji` 逻辑，发帖内容仍只保留纯文本；本次变更重点在 agent 层日志。
- 测试：`OPENAI_API_KEY='sk-7d5764a82e654f70b18502e352981fe0'; WEIBO_MODEL_PROVIDER=deepseek; WEIBO_ENABLE_LLM=1; python examples/weibo_simulation_openai.py`，运行过程中 LLM 返回多条含 emoji/国旗的评论，控制台与文件日志均未报错，验证通过。测试完成后删除 `weibo_sim_openai.db`。
