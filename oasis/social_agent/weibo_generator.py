"""微博数据生成与适配工具，负责将标注数据注入 OASIS 平台。"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from oasis.social_agent import AgentGraph, SocialAgent
from oasis.social_platform.channel import Channel
from oasis.social_platform.config import UserInfo
from oasis.social_platform.typing import ActionType

_HTML_TAG = re.compile(r"<[^>]+>")

SECTION_ALIASES = {
    "个人基本信息": ["个人基础信息", "���˻�����Ϣ"],
    "社交影响力": ["社会影响力", "�罻Ӱ����"],
    "用户行为特征": ["�û���Ϊ����"],
    "标签特征": ["标签信息", "��ǩ����", "��ǩ��Ϣ"],
    "关注博主信息": ["��ע������Ϣ"],
    "近期发帖内容分析": ["���ڷ������ݷ���"],
}

FIELD_ALIASES = {
    "用户名": ["�û���"],
    "用户昵称": ["�û��ǳ�"],
    "用户简介": ["�û����"],
    "用户性别": ["�û��Ա�"],
    "微博等级": ["΢���ȼ�"],
    "地区信息": ["������Ϣ"],
    "粉丝数量": ["��˿����"],
    "年龄": ["����"],
}


def _expand_keys(keys: tuple[str, ...], alias_map: dict[str, list[str]]) -> list[str]:
    candidates: list[str] = []
    for key in keys:
        if key not in candidates:
            candidates.append(key)
        for alias in alias_map.get(key, []):
            if alias not in candidates:
                candidates.append(alias)
    return candidates


def _get_section(record: dict[str, Any], *keys: str) -> dict[str, Any]:
    candidates = _expand_keys(keys, SECTION_ALIASES)
    for candidate in candidates:
        value = record.get(candidate)
        if isinstance(value, dict):
            return value
    for actual_key, value in record.items():
        if not isinstance(value, dict):
            continue
        for target in candidates:
            if target in actual_key or actual_key in target:
                return value
    return {}


def _get_field(data: dict[str, Any], *keys: str, default: Any | None = None) -> Any:
    if not isinstance(data, dict):
        return default
    candidates = _expand_keys(keys, FIELD_ALIASES)
    for candidate in candidates:
        value = data.get(candidate)
        if value not in (None, ""):
            return value
    for actual_key, value in data.items():
        if value in (None, ""):
            continue
        for target in candidates:
            if target in actual_key or actual_key in target:
                return value
    return default


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _clean_content(text: str) -> str:
    cleaned = _HTML_TAG.sub("", text)
    return cleaned.replace("&nbsp;", " ").strip()


def _build_user_profile(record: dict[str, Any]) -> dict[str, Any]:
    base_info = _get_section(record, "个人基本信息", "个人基础信息")
    influence = _get_section(record, "社交影响力", "社会影响力")
    behavior = _get_section(record, "用户行为特征")
    tags = _get_section(record, "标签特征", "标签信息")

    summary_parts = []
    level = _get_field(base_info, "微博等级")
    if level:
        summary_parts.append(f"微博等级：{level}")
    fan_count = _get_field(influence, "粉丝数量")
    if fan_count is not None:
        summary_parts.append(f"粉丝数：{fan_count}")
    keywords = behavior.get("keywords_list", {})
    if isinstance(keywords, dict) and keywords:
        hot_topics = "、".join(list(keywords.keys())[:3])
        summary_parts.append(f"常聊话题：{hot_topics}")
    if not summary_parts:
        summary_parts.append("暂无画像")

    other_info = {
        "user_profile": "；".join(summary_parts),
        "gender": _get_field(base_info, "用户性别", default="未知"),
        "age": _get_field(behavior, "年龄", default="未知"),
        "mbti": _get_field(tags, "MBTI", default="未知"),
        "country": _get_field(base_info, "地区信息", default="未知"),
        "raw_record": record,
    }

    profile = {
        "nodes": [],
        "edges": [],
        "other_info": other_info,
    }
    return profile


def get_default_weibo_actions() -> list[ActionType]:
    return [
        ActionType.CREATE_POST,
        ActionType.REPOST,
        ActionType.CREATE_COMMENT,
        ActionType.LIKE_POST,
        ActionType.FOLLOW,
        ActionType.SEARCH_POSTS,
        ActionType.SEARCH_USER,
        ActionType.TREND,
        ActionType.REFRESH,
        ActionType.DO_NOTHING,
    ]


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
        base_info = _get_section(record, "个人基本信息", "个人基础信息")
        username = _safe_str(_get_field(base_info, "用户名"), f"weibo_user_{agent_id}")
        real_name = _safe_str(_get_field(base_info, "用户昵称", default=username))
        bio = _safe_str(_get_field(base_info, "用户简介", default="暂无简介"))
        profile = _build_user_profile(record)

        user_info = UserInfo(
            name=real_name,
            description=bio,
            profile=profile,
            recsys_type="reddit",
        )

        agent = SocialAgent(
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
        base_info = _get_section(record, "个人基本信息", "个人基础信息")
        username = _safe_str(_get_field(base_info, "用户名"), f"weibo_user_{agent.agent_id}")
        real_name = _safe_str(_get_field(base_info, "用户昵称", default=username))
        bio = _safe_str(_get_field(base_info, "用户简介", default="暂无简介"))
        resp = await agent.env.action.sign_up(username, real_name, bio)
        dataset_id = _safe_str(record.get("用户ID") or record.get("�û�ID"), str(agent.agent_id))
        user_id = resp.get("user_id")
        if user_id is None:
            raise RuntimeError(f"代理 {agent.agent_id} 注册失败：{resp}")
        dataset_id_to_user_id[dataset_id] = user_id
        dataset_id_to_agent_id[dataset_id] = agent.agent_id
        agent_user_id_mapping[agent.agent_id] = user_id

    for record, agent in agent_entries:
        follows = _get_section(record, "关注博主信息").get("follows", {})
        if not isinstance(follows, dict):
            continue
        for target_id in follows.keys():
            target_user_id = dataset_id_to_user_id.get(_safe_str(target_id))
            target_agent_id = dataset_id_to_agent_id.get(_safe_str(target_id))
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
            text = _clean_content(_safe_str(raw_text))
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
) -> AgentGraph:
    records = load_weibo_dataset(dataset_path)
    if agent_graph is None:
        agent_graph = AgentGraph()
    if available_actions is None:
        available_actions = get_default_weibo_actions()

    for idx, record in enumerate(records):
        base_info = _get_section(record, "个人基本信息", "个人基础信息")
        username = _safe_str(_get_field(base_info, "用户名"), f"weibo_user_{idx}")
        bio = _safe_str(_get_field(base_info, "用户简介", default="暂无简介"))
        profile = _build_user_profile(record)

        user_info = UserInfo(
            name=username,
            description=bio,
            profile=profile,
            recsys_type="reddit",
        )

        agent = SocialAgent(
            agent_id=idx,
            user_info=user_info,
            agent_graph=agent_graph,
            model=model,
            available_actions=available_actions,
        )
        agent_graph.add_agent(agent)

    return agent_graph
