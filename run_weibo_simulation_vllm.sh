#!/bin/bash

# ==========================================
# 1. 编码设置
# ==========================================
export PYTHONIOENCODING=utf-8

# 如果检测到是在 Windows 的 Git Bash 中运行，尝试切换 chcp
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    chcp.com 65001 > /dev/null 2>&1
fi

# ==========================================
# 2. 环境变量配置
# ==========================================
export WEIBO_ENABLE_LLM=1

# [可选] 配置 vLLM 地址和模型名
# export WEIBO_VLLM_ENDPOINTS="http://127.0.0.1:8000/v1"
# export WEIBO_VLLM_MODEL="qwen-2"

# ==========================================
# 3. 运行程序
# ==========================================
echo -e "\n🚀 Starting Weibo Simulation (vLLM Mode)..."
echo -e "⚠️  Ensure vLLM server is running in another terminal!\n"

# 在另外的终端启动python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen3-4B --gpu-memory-utilization 0.85

python examples/weibo_simulation_vllm.py