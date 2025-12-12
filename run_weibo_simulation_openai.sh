#!/usr/bin/env bash
set -euo pipefail

# 如需直接在脚本中配置密钥，请将下方占位符替换为真实值；
# 也可在运行前通过 `export OPENAI_API_KEY=...` 传入。
if [[ -z "${OPENAI_API_KEY:-}" ]]; then
  echo "请先设置 OPENAI_API_KEY 环境变量 (DeepSeek/Qwen 兼容密钥)。"
  exit 1
fi

export WEIBO_MODEL_PROVIDER="${WEIBO_MODEL_PROVIDER:-deepseek}"
export WEIBO_MODEL_NAME="${WEIBO_MODEL_NAME:-deepseek-chat}"
export WEIBO_COMPATIBLE_API_URL="${WEIBO_COMPATIBLE_API_URL:-https://api.deepseek.com/v1}"
export WEIBO_ENABLE_LLM="${WEIBO_ENABLE_LLM:-1}"

python examples/weibo_simulation_openai.py
