# Weibo Simulation Script (Oasis)

本项目修改自 GitHub 开源仓库 [camel-ai/oasis](https://github.com/camel-ai/oasis)，用于在本地环境中运行基于微博数据的多智能体社会模拟。

## 📋 功能说明

该脚本 (`examples/weibo_simulation_openai.py`) 加载真实的微博用户画像数据，创建多个 AI 智能体。这些智能体能够在虚拟的微博环境中：

  * 发布帖子（根据历史数据或 AI 生成）
  * 浏览时间流
  * 相互点赞、评论和互动
  * 所有行为数据将记录在 SQLite 数据库中

## ⚠️ 注意事项

1.  **数据文件**：确保 `weibo_test/total_data_with_descriptions_transformers.json` 文件存在。
2.  **编码问题**：Windows 用户请务必在运行前切换终端编码（见下文），否则 Emoji 可能导致报错。
3.  **数据库**：每次运行可能会重置或追加数据库，请注意备份 `weibo_test/` 下的 `.db` 文件。

-----

## 🚀 运行方法 1：使用 DeepSeek / OpenAI API

### 🪟 Windows (PowerShell)

在 PowerShell 中直接运行以下命令（请替换 API Key）：

```powershell
# 1. 解决中文/Emoji 乱码问题 (至关重要)
chcp 65001

# 2. 设置环境变量
$env:PYTHONIOENCODING='utf-8'
$env:OPENAI_API_KEY='你的deepseek api key'
$env:WEIBO_MODEL_PROVIDER='deepseek'
$env:WEIBO_MODEL_NAME='deepseek-chat'
$env:WEIBO_COMPATIBLE_API_URL='https://api.deepseek.com/v1'
$env:WEIBO_ENABLE_LLM='1'

# 3. 运行脚本
python examples/weibo_simulation_openai.py
```

### 🐧 Linux / macOS (使用 .sh 脚本)

如果你已将环境变量配置保存为 `.sh` 文件（例如 `run_weibo.sh`）：

1.  赋予执行权限：
    ```bash
    chmod +x run_weibo.sh
    ```
2.  运行脚本：
    ```bash
    ./run_weibo.sh
    ```

*`.sh` 文件内容参考：*

```bash
#!/bin/bash
export PYTHONIOENCODING=utf-8
export OPENAI_API_KEY='你的deepseek api key'
export WEIBO_MODEL_PROVIDER='deepseek'
export WEIBO_MODEL_NAME='deepseek-chat'
export WEIBO_COMPATIBLE_API_URL='https://api.deepseek.com/v1'
export WEIBO_ENABLE_LLM='1'

python examples/weibo_simulation_openai.py
```

-----

## 🚀 运行方法 2：使用 vLLM (本地部署模型)

如果你使用 `examples/weibo_simulation_vllm.py` 版本：

### 1\. 启动 vLLM 服务端

请在另一个独立的终端窗口中运行：

```bash
# 显存允许的情况下，推荐使用 Qwen2.5-7B
python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-7B-Instruct --gpu-memory-utilization 0.85 --served-model-name qwen-2
```

### 2\. 运行仿真客户端

**Windows (PowerShell):**

```powershell
chcp 65001
$env:PYTHONIOENCODING='utf-8'
$env:WEIBO_ENABLE_LLM='1'
# 如果端口不是默认的8000，请设置 WEIBO_VLLM_ENDPOINTS
python examples/weibo_simulation_vllm.py
```

**Linux (.sh):**

```bash
#!/bin/bash
export PYTHONIOENCODING=utf-8
export WEIBO_ENABLE_LLM='1'
python examples/weibo_simulation_vllm.py
```