"""微博 vLLM/私有 Qwen-API 适配示例，所有提示均为中文。"""
from __future__ import annotations

# ================= 🔧 底层输出流矫正 (必须保留) =================
import sys

class SafeWriter:
    """
    Windows 控制台救星：拦截所有输出，遇到 GBK 不支持的 Emoji 自动替换为 '?'
    """
    def __init__(self, original_stream):
        self.original_stream = original_stream
        self.encoding = getattr(original_stream, 'encoding', 'gbk') or 'gbk'

    def write(self, data):
        if not data: return
        try:
            self.original_stream.write(data)
        except (UnicodeError, UnicodeEncodeError):
            try:
                # 强行替换无法显示的字符，保留汉字
                safe_data = data.encode(self.encoding, 'replace').decode(self.encoding)
                self.original_stream.write(safe_data)
            except Exception:
                pass

    def flush(self):
        try:
            self.original_stream.flush()
        except:
            pass
    
    def isatty(self):
        return getattr(self.original_stream, 'isatty', lambda: False)()

# 🔥 立即替换系统标准输出
sys.stdout = SafeWriter(sys.stdout)
sys.stderr = SafeWriter(sys.stderr)
# ===============================================================

import asyncio
import os
import json
import re
import logging
from pathlib import Path

# 强制配置 logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stdout, 
    force=True
)

from camel.models import ModelFactory, ModelManager
from camel.types import ModelPlatformType, ModelType

import oasis
from oasis import ActionType, LLMAction, ManualAction
from oasis.social_agent.weibo_generator import (generate_weibo_agent_graph,
                                                get_default_weibo_actions)

DATASET_PATH = Path("weibo_test/total_data_with_descriptions_transformers.json")
DB_PATH = Path("weibo_test/weibo_sim_vllm.db")
_EMOJI_PATTERN = re.compile(r"[\U00010000-\U0010FFFF]")


def _load_weibo_records() -> list[dict]:
    try:
        content = DATASET_PATH.read_text(encoding="utf-8")
        data = json.loads(content)
    except FileNotFoundError:
        print(f"❌ 找不到数据文件: {DATASET_PATH}")
        return []
    if not isinstance(data, list):
        raise ValueError("微博数据集格式应为列表")
    return data

WEIBO_RECORDS = _load_weibo_records()

def _strip_emoji(text: str) -> str:
    # 保留 Emoji，显示交给 SafeWriter
    if not text: return ""
    cleaned = text.replace("\ufe0f", "").replace("\u200d", "")
    return cleaned

def _get_section(record: dict, *keys: str) -> dict:
    for key in keys:
        value = record.get(key)
        if isinstance(value, dict): return value
    return {}

def _pick_post_text(record_idx: int, fallback: str) -> str:
    if not WEIBO_RECORDS: return fallback
    record = WEIBO_RECORDS[record_idx % len(WEIBO_RECORDS)]
    posts = _get_section(record, "近期发帖内容分析").get("全部帖子合集", []) or []
    for raw in posts:
        text = str(raw).strip() 
        if text: return text
    return fallback

def _summarize_tags(record: dict) -> str:
    tags = _get_section(record, "标签特征", "标签信息")
    tag_items = []
    if isinstance(tags, dict):
        for key, value in tags.items():
            if isinstance(value, str) and value.strip():
                tag_items.append(f"{key}:{value.strip()}")
            elif value not in (None, "", []):
                tag_items.append(f"{key}:{value}")
    return "、".join(tag_items[:3])

def _describe_persona(record_idx: int) -> str:
    if not WEIBO_RECORDS: return "默认用户"
    record = WEIBO_RECORDS[record_idx % len(WEIBO_RECORDS)]
    base_info = _get_section(record, "个人基本信息", "个人基础信息")
    username = str(base_info.get("用户名") or f"微博用户{record_idx}")
    profile = str(base_info.get("用户简介") or "暂无简介")
    tags_line = _summarize_tags(record)
    recent = _pick_post_text(record_idx, "暂无历史内容")
    parts = [f"帐号：{username}", f"简介：{profile}"]
    if tags_line: parts.append(f"标签：{tags_line}")
    parts.append(f"最近帖子示例：{recent}")
    return "；".join(parts)

def _compose_post_content(record_idx: int, fallback: str) -> str:
    raw_text = _pick_post_text(record_idx, fallback)
    return raw_text if raw_text else fallback

# ================= vLLM 配置部分 =================
def build_vllm_manager() -> ModelManager:
    """
    创建 vLLM 模型管理器。
    支持多个端点负载均衡 (Round Robin)。
    """
    # 默认尝试连接本地 8000 端口
    endpoints = os.getenv("WEIBO_VLLM_ENDPOINTS", "http://127.0.0.1:8000/v1")
    model_name = os.getenv("WEIBO_VLLM_MODEL", "qwen-2") # 你的模型名称，如 Qwen/Qwen2.5-7B-Instruct
    
    urls = [url.strip() for url in endpoints.split(",") if url.strip()]
    
    print(f"🔌 正在连接 vLLM 端点: {urls}, 模型: {model_name}")
    
    models = [
        ModelFactory.create(
            model_platform=ModelPlatformType.VLLM,
            model_type=model_name,
            url=url,
        ) for url in urls
    ]
    
    if not models:
        raise ValueError("未提供有效的 vLLM 端点。")
        
    return ModelManager(models=models, scheduling_strategy='round_robin')
# ================================================

def _prepare_database():
    os.environ["OASIS_DB_PATH"] = str(DB_PATH.resolve())
    if DB_PATH.exists():
        try:
            DB_PATH.unlink()
        except:
            print("⚠️ 无法删除旧数据库，将尝试直接写入。")
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

def _log_persona(record_idx: int, label: str):
    print(f"{label} 数据集信息：{_describe_persona(record_idx)}")

async def main():
    if not WEIBO_RECORDS:
        print("❌ 数据集为空，程序终止")
        return

    # 1. 构建 vLLM 管理器
    try:
        shared_model_manager = build_vllm_manager()
    except Exception as e:
        print(f"❌ vLLM 初始化失败: {e}")
        print("请确保你已经在另一个终端启动了 vLLM 服务器，例如：")
        print("python -m vllm.entrypoints.openai.api_server --model Qwen/Qwen2.5-7B-Instruct")
        return

    available_actions = get_default_weibo_actions()
    _prepare_database()

    # 2. 生成图（注意这里传入的是 model manager）
    agent_graph = await generate_weibo_agent_graph(
        dataset_path=str(DATASET_PATH),
        model=shared_model_manager, 
        available_actions=available_actions,
    )

    env = oasis.make(
        agent_graph=agent_graph,
        platform=oasis.DefaultPlatformType.WEIBO,
        database_path=str(DB_PATH),
    )

    # 确保能看到日志
    logging.getLogger("oasis").setLevel(logging.INFO)
    logging.getLogger("social_agent").setLevel(logging.INFO)

    await env.reset()

    _log_persona(0, "代理0")
    # 第一回合：手动发帖 (自我介绍)
    # 我这里改回了“自我介绍”的文案，方便你对比之前的成功结果
    actions_1 = {
        env.agent_graph.get_agent(0): ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": "大家好，很高兴认识你，我是一个刚来的新人。能不能请评论区的各位大佬自我介绍一下？"},
        )
    }
    await env.step(actions_1)

    enable_llm = os.getenv("WEIBO_ENABLE_LLM", "0") == "1"
    
    if enable_llm:
        print("🤖 正在调用 vLLM 进行回复...")
        # 选取部分 Agent 回复
        selected_agents = env.agent_graph.get_agents([2, 4, 6, 8, 10])
        llm_actions = {agent: LLMAction() for _, agent in selected_agents}
        await env.step(llm_actions)
    else:
        print("⚠️ 未启用 LLM 行动。请设置环境变量 WEIBO_ENABLE_LLM=1 并启动 vLLM 服务。")

    _log_persona(2, "代理2")
    # 第二回合：手动发帖 (使用历史数据)
    manual_post = {
        env.agent_graph.get_agent(2): ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": _compose_post_content(2, "默认发帖内容")},
        )
    }
    await env.step(manual_post)

    # 第三回合：全员自由互动
    all_llm_actions = {agent: LLMAction() for _, agent in env.agent_graph.get_agents()}
    if enable_llm:
        print("🤖 正在进行全员互动 (vLLM)...")
        await env.step(all_llm_actions)
    else:
        print("跳过第二轮 LLM 行动。")

    await env.close()
    print(f"✅ 微博 vLLM/Qwen 实验完成，数据库存于：{DB_PATH}")


if __name__ == "__main__":
    asyncio.run(main())