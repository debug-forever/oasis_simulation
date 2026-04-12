"""使用微博标注数据运行 Qwen API 代理的华为话题模拟，所有输出均为中文。"""
from __future__ import annotations

import asyncio
import os
import json
import re
import sqlite3
import ast
import sys
import logging
from pathlib import Path

logging.basicConfig(stream=sys.stdout, level=logging.INFO, force=True)

from camel.models import ModelFactory
from camel.types import ModelPlatformType, ModelType

import oasis
from oasis import ActionType, LLMAction, ManualAction
from oasis.social_agent.weibo_generator import (generate_weibo_agent_graph,
                                                get_default_weibo_actions)

DATASET_PATH = Path("weibo_test/top100_users_complete_data_post_followers.json")
DB_PATH = Path("weibo_test/weibo_sim_qwen_huawei.db")
_EMOJI_PATTERN = re.compile(r"[\U00010000-\U0010FFFF]")


def _load_weibo_records() -> list[dict]:
    try:
        content = DATASET_PATH.read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"找不到数据文件: {DATASET_PATH}")
        return []
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        data = [json.loads(line) for line in content.splitlines() if line.strip()]
    if not isinstance(data, list):
        raise ValueError("微博数据集格式应为列表")
    return data


WEIBO_RECORDS = _load_weibo_records()


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
    tags = _get_section(record, "特征标签", "标签特征", "标签信息")
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


def build_llm_model():
    return ModelFactory.create(
        model_platform=ModelPlatformType.QWEN,
        model_type="qwen-plus",
        url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        api_key="sk-e0642a92cc6e45c9bd25634a2009f4d2",
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


def update_follower_id_list():
    env_db_path = os.environ.get("OASIS_DB_PATH")
    conn = sqlite3.connect(env_db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT weibo_id, user_id
        FROM user
        WHERE weibo_id IS NOT NULL
    """)
    weibo_to_user = {weibo_id: user_id for weibo_id, user_id in cursor.fetchall()}

    cursor.execute("""
        SELECT rowid, follower_list
        FROM user
        WHERE follower_list IS NOT NULL
    """)
    rows = cursor.fetchall()

    update_rows = []
    for rowid, follower_list_str in rows:
        try:
            try:
                follower_weibo_ids = json.loads(follower_list_str)
            except json.JSONDecodeError:
                follower_weibo_ids = ast.literal_eval(follower_list_str)

            if not isinstance(follower_weibo_ids, list):
                continue

            follower_user_ids = [
                weibo_to_user[w]
                for w in follower_weibo_ids
                if w in weibo_to_user
            ]

            update_rows.append((
                json.dumps(follower_user_ids, ensure_ascii=False),
                rowid
            ))
        except Exception as e:
            print(f"[WARN] rowid={rowid} 处理失败: {e}")

    cursor.executemany("""
        UPDATE user
        SET follower_id_list = ?
        WHERE rowid = ?
    """, update_rows)

    conn.commit()
    conn.close()
    print(f"更新完成，共处理 {len(update_rows)} 条记录")


async def main():
    if not WEIBO_RECORDS:
        print("数据集为空，程序终止")
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
    update_follower_id_list()

    _log_persona(0, "智能体0")

    # 华为相关话题讨论
    actions_1 = {
        env.agent_graph.get_agent(2): ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": "大家用的手机是华为还是苹果？感觉最近华为势头很猛啊"},
        )
    }
    target_agents = env.agent_graph.get_agents([1, 3, 5, 7, 9])
    actions_2 = {agent: LLMAction() for _, agent in target_agents}
    actions_3 = {
        env.agent_graph.get_agent(6): ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": "华为Mate 80系列要发布了，大家觉得值得入手吗？"},
        )
    }
    actions_4 = {agent: LLMAction() for _, agent in env.agent_graph.get_agents()}
    actions_5 = {
        env.agent_graph.get_agent(10): ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": "华为的鸿蒙系统现在生态怎么样了？有没有完全脱离安卓？"},
        )
    }
    actions_6 = {
        env.agent_graph.get_agent(3): ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": "支持国产芯片，华为麒麟芯片越来越强了"},
        )
    }
    actions_7 = {
        env.agent_graph.get_agent(15): ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": "华为和苹果你们会选哪个？从拍照、系统、生态各方面来说"},
        )
    }

    await env.step(actions_1)
    await env.step(actions_2)
    await env.step(actions_3)
    await env.step(actions_5)
    await env.step(actions_4)
    await env.step(actions_6)
    await env.step(actions_4)
    await env.step(actions_7)
    for time_step in range(40):
        await env.step(actions_4)

    await env.close()
    print(f"华为话题微博模拟实验结束，数据库位置：{DB_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
