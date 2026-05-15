"""微博数据生成与适配工具，负责将标注数据注入 OASIS 平台。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from oasis.social_agent.agent import SocialAgent
from oasis.social_agent.agent_graph import AgentGraph
from oasis.social_platform.channel import Channel
from oasis.social_platform.config import UserInfo
from oasis.social_platform.typing import ActionType
from oasis.weibo.action_space import get_default_weibo_actions as _get_default_weibo_actions
from oasis.weibo.profile_builder import (
    build_follow_payload,
    build_user_identity,
    build_user_profile,
    clean_weibo_text,
)


def _get_section(record: dict[str, Any], key: str) -> dict[str, Any]:
    value = record.get(key)
    return value if isinstance(value, dict) else {}


def get_default_weibo_actions() -> list[ActionType]:
    return _get_default_weibo_actions()


def load_weibo_dataset(dataset_path: str) -> list[dict[str, Any]]:
    path = Path(dataset_path)
    if not path.exists():
        raise FileNotFoundError(f"未找到数据文件：{dataset_path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("微博数据格式错误，应为列表")
    return [record for record in data if isinstance(record, dict)]


async def generate_weibo_agents(
    dataset_path: str,
    channel: Channel,
    agent_graph: AgentGraph | None = None,
    model=None,
    available_actions: list[ActionType] | None = None,
    max_posts_per_agent: int = 5,
    agent_cls: type[SocialAgent] = SocialAgent,
) -> tuple[AgentGraph, dict[int, int]]:
    records = load_weibo_dataset(dataset_path)
    if agent_graph is None:
        agent_graph = AgentGraph()

    if available_actions is None:
        available_actions = get_default_weibo_actions()

    base_agent_id = agent_graph.get_num_nodes()
    agent_entries: list[tuple[dict[str, Any], SocialAgent]] = []
    dataset_id_to_user_id: dict[str, int] = {}
    dataset_id_to_agent_id: dict[str, int] = {}
    agent_user_id_mapping: dict[int, int] = {}

    for offset, record in enumerate(records):
        agent_id = base_agent_id + offset
        identity = build_user_identity(record, f"weibo_user_{agent_id}")
        profile = build_user_profile(record)

        user_info = UserInfo(
            user_name=identity.user_name,
            name=identity.name,
            description=identity.description,
            profile=profile,
            recsys_type="weibo",
        )
        user_info.weibo_id = identity.weibo_id
        follower_list, follower_num_list = build_follow_payload(record)
        if follower_list:
            print(
                f"生成微博用户 {agent_id}，关注列表：{follower_list}，"
                f"互动数列表：{follower_num_list}"
            )
            user_info.follower_list = follower_list
            user_info.follower_num_list = follower_num_list

        agent = agent_cls(
            agent_id=agent_id,
            user_info=user_info,
            channel=channel,
            model=model,
            agent_graph=agent_graph,
            available_actions=available_actions,
        )
        agent_graph.add_agent(agent)
        agent_entries.append((record, agent))

    for record, agent in agent_entries:
        identity = build_user_identity(record, f"weibo_user_{agent.agent_id}")
        resp = await agent.env.action.sign_up(
            identity.user_name,
            identity.name,
            identity.description,
            agent.user_info.follower_list,
            agent.user_info.follower_num_list,
            identity.weibo_id,
        )
        dataset_id = clean_weibo_text(record.get("用户ID")) or str(agent.agent_id)
        user_id = resp.get("user_id")
        if user_id is None:
            raise RuntimeError(f"智能体 {agent.agent_id} 注册失败：{resp}")
        dataset_id_to_user_id[dataset_id] = user_id
        dataset_id_to_agent_id[dataset_id] = agent.agent_id
        agent_user_id_mapping[agent.agent_id] = user_id

    for record, agent in agent_entries:
        follows = _get_section(record, "关注博主信息").get("follows", {})
        if not isinstance(follows, dict):
            continue
        for target_id in follows.keys():
            target_key = clean_weibo_text(target_id)
            target_user_id = dataset_id_to_user_id.get(target_key)
            target_agent_id = dataset_id_to_agent_id.get(target_key)
            if target_user_id is None or target_agent_id is None:
                continue
            await agent.env.action.follow(target_user_id)
            agent_graph.add_edge(agent.agent_id, target_agent_id)

    for record, agent in agent_entries:
        posts = _get_section(record, "近期发帖内容分析").get("全部帖子合集", [])
        if not isinstance(posts, list):
            continue
        created = 0
        for raw_text in posts:
            text = clean_weibo_text(raw_text)
            if not text:
                continue
            await agent.env.action.create_post(text)
            created += 1
            if created >= max_posts_per_agent:
                break

    return agent_graph, agent_user_id_mapping


async def generate_weibo_agent_graph(
    dataset_path: str,
    agent_graph: AgentGraph | None = None,
    model=None,
    available_actions: list[ActionType] | None = None,
    agent_cls: type[SocialAgent] = SocialAgent,
) -> AgentGraph:
    records = load_weibo_dataset(dataset_path)
    if agent_graph is None:
        agent_graph = AgentGraph()
    if available_actions is None:
        available_actions = get_default_weibo_actions()

    for idx, record in enumerate(records):
        identity = build_user_identity(record, f"weibo_user_{idx}")
        profile = build_user_profile(record)

        user_info = UserInfo(
            user_name=identity.user_name,
            name=identity.name,
            description=identity.description,
            profile=profile,
            recsys_type="weibo",
        )
        user_info.weibo_id = identity.weibo_id
        follower_list, follower_num_list = build_follow_payload(record)
        if follower_list:
            user_info.follower_list = follower_list
            user_info.follower_num_list = follower_num_list

        agent = agent_cls(
            agent_id=idx,
            user_info=user_info,
            agent_graph=agent_graph,
            model=model,
            available_actions=available_actions,
        )
        agent_graph.add_agent(agent)

    return agent_graph
