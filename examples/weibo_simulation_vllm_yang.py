"""使用微博标注数据运行 OpenAI/DeepSeek/Qwen 代理的示例，所有输出均为中文。"""
from __future__ import annotations

# ================= 🙈 掩耳盗铃区 (放在最前面) =================
import sys
import io
import logging

# 1. 【核心】告诉 logging 模块：不管发生什么错误，别喊，别崩，直接忽略
# logging.raiseExceptions = False

# 2. 【核心】强行把 Python 的嘴巴改成 UTF-8，遇到不会读的字直接替换成问号 '?'
# 这样至少汉字能出来，Emoji 变成问号，不会导致整句消失
# try:
#     sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
#     sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
# except Exception:
#     pass 
# =============================================================

import asyncio
import os
import json
import re
from pathlib import Path

# 强制配置 logging 输出流为我们修改过的 stdout
logging.basicConfig(stream=sys.stdout, level=logging.INFO, force=True)

from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType

import oasis
from oasis import ActionType, LLMAction, ManualAction
from oasis.social_agent.weibo_generator import (generate_weibo_agent_graph,
                                                get_default_weibo_actions)

DATASET_PATH = Path("weibo_test/total_data_with_descriptions_transformers.json")
DB_PATH = Path("weibo_test/weibo_sim_openai.db")
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
    if not text: return ""
    # 不洗数据了，哪怕有Emoji也留着
    return text


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


def build_llm_model():
    return ModelFactory.create(
        model_platform=ModelPlatformType.VLLM,
        model_type="./Qwen3-4B-Instruct-2507",
        # model_config_dict={"max_tokens": 8192},
        # TODO: change to your own vllm server url
        url="http://localhost:8192/v1",
    )


def _prepare_database():
    os.environ["OASIS_DB_PATH"] = str(DB_PATH.resolve())
    if DB_PATH.exists():
        try:
            DB_PATH.unlink()
        except:
            pass
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _log_persona(record_idx: int, label: str):
    try:
        print(f"{label} 数据集信息：{_describe_persona(record_idx)}")
    except:
        pass


async def main():
    if not WEIBO_RECORDS:
        print("❌ 数据集为空，程序终止")
        return

    llm_model = build_llm_model()
    available_actions = get_default_weibo_actions()
    _prepare_database()

    agent_graph = await generate_weibo_agent_graph(
        dataset_path=str(DATASET_PATH),
        model=llm_model,
        available_actions=available_actions,
    )

    env = oasis.make(
        agent_graph=agent_graph,
        platform=oasis.DefaultPlatformType.WEIBO,
        database_path=str(DB_PATH),
    )

    await env.reset()

    _log_persona(0, "智能体0")
    actions_1 = {
        env.agent_graph.get_agent(0): ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": "大家好，很高兴认识你，我是一个刚来的新人。能不能请评论区的各位大佬自我介绍一下？"},
        )
    }
    await env.step(actions_1)

    enable_llm = 1
    if enable_llm:
        target_agents = env.agent_graph.get_agents([1, 3, 5, 7, 9])
        actions_2 = {agent: LLMAction() for _, agent in target_agents}
        await env.step(actions_2)
    else:
        print("未启用 LLM 行动，跳过自动互动回合。设置 WEIBO_ENABLE_LLM=1 可开启。")

    _log_persona(1, "智能体1")
    actions_3 = {
        env.agent_graph.get_agent(1): ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": _compose_post_content(1, "我刚加入社区，期待和大家互动。")},
        )
    }
    await env.step(actions_3)
 
    actions_4 = {agent: LLMAction() for _, agent in env.agent_graph.get_agents()}
    if enable_llm:
        await env.step(actions_4)
    else:
        print("再次跳过 LLM 行动以避免调用实际接口，微博数据仍将写入数据库。")

    await env.close()
    print(f"微博 OpenAI/兼容实验结束，数据库位置：{DB_PATH}")


if __name__ == "__main__":
    asyncio.run(main())