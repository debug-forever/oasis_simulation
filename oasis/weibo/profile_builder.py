"""微博画像构造工具，只读取当前微博数据集中真实有效的字段。"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

_HTML_TAG = re.compile(r"<[^>]+>")
_EMPTY_TEXT_VALUES = {"", "未知", "unknown", "none", "null", "暂无", "无"}


@dataclass(frozen=True)
class WeiboIdentity:
    user_name: str
    name: str
    description: str
    weibo_id: str


def clean_weibo_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = _HTML_TAG.sub("", text)
    text = text.replace("&nbsp;", " ")
    return " ".join(text.split()).strip()


def _is_valid_value(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip().lower() not in _EMPTY_TEXT_VALUES
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def _section(record: dict[str, Any], key: str) -> dict[str, Any]:
    value = record.get(key)
    return value if isinstance(value, dict) else {}


def _value(data: dict[str, Any], key: str) -> Any:
    value = data.get(key)
    return value if _is_valid_value(value) else None


def _add_field(fields: dict[str, Any], label: str, value: Any) -> None:
    if _is_valid_value(value):
        fields[label] = value


def _parse_json_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str) or not value.strip():
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _summarize_mapping(mapping: dict[str, Any], limit: int = 5) -> str:
    if not mapping:
        return ""
    items = []
    for key, value in list(mapping.items())[:limit]:
        if _is_valid_value(value):
            items.append(f"{key}({value})")
        else:
            items.append(str(key))
    return "、".join(items)


def _summarize_stats(stats: Any) -> str:
    if not isinstance(stats, dict):
        return ""
    ordered_keys = ["总转发数", "总评论数", "总点赞数", "总互动数"]
    parts = [
        f"{key}:{stats[key]}"
        for key in ordered_keys
        if _is_valid_value(stats.get(key))
    ]
    return "、".join(parts)


def _recent_posts(record: dict[str, Any], limit: int = 3) -> list[str]:
    posts = _section(record, "近期发帖内容分析").get("全部帖子合集", [])
    if not isinstance(posts, list):
        return []
    result: list[str] = []
    for raw_text in posts:
        text = clean_weibo_text(raw_text)
        if not text:
            continue
        result.append(text[:180])
        if len(result) >= limit:
            break
    return result


def _summarize_follows(record: dict[str, Any], limit: int = 5) -> str:
    follows = _section(record, "关注博主信息").get("follows", {})
    if not isinstance(follows, dict):
        return ""

    items = []
    for follow_id, info in list(follows.items())[:limit]:
        if isinstance(info, dict):
            username = clean_weibo_text(info.get("username")) or str(follow_id)
            reply_count = info.get("reply_count")
            if _is_valid_value(reply_count):
                items.append(f"{username}(互动{reply_count})")
            else:
                items.append(username)
        else:
            items.append(str(follow_id))
    return "、".join(items)


def build_follow_payload(record: dict[str, Any]) -> tuple[str, str]:
    follows = _section(record, "关注博主信息").get("follows", {})
    if not isinstance(follows, dict) or not follows:
        return "", ""

    follow_ids: list[str] = []
    reply_counts: list[int] = []
    for follow_id, info in follows.items():
        follow_ids.append(str(follow_id))
        if isinstance(info, dict):
            reply_count = info.get("reply_count", 0)
        else:
            reply_count = 0
        try:
            reply_counts.append(int(reply_count))
        except (TypeError, ValueError):
            reply_counts.append(0)

    return (
        json.dumps(follow_ids, ensure_ascii=False),
        json.dumps(reply_counts, ensure_ascii=False),
    )


def build_user_identity(record: dict[str, Any], fallback_user_name: str) -> WeiboIdentity:
    base_info = _section(record, "个人基本信息")
    user_name = clean_weibo_text(base_info.get("用户名")) or fallback_user_name
    description = clean_weibo_text(base_info.get("用户简介"))
    weibo_id = clean_weibo_text(record.get("用户ID"))
    return WeiboIdentity(
        user_name=user_name,
        name=user_name,
        description=description,
        weibo_id=weibo_id,
    )


def build_user_profile(record: dict[str, Any]) -> dict[str, Any]:
    base_info = _section(record, "个人基本信息")
    account_info = _section(record, "账号类型与层级")
    influence = _section(record, "社交影响力")
    follow_info = _section(record, "关注博主信息")
    behavior = _section(record, "用户行为特征")
    tags = _section(record, "标签特征")

    fields: dict[str, Any] = {}
    _add_field(fields, "用户名", _value(base_info, "用户名"))
    _add_field(fields, "用户简介", clean_weibo_text(base_info.get("用户简介")))
    _add_field(fields, "用户性别", _value(base_info, "用户性别"))
    _add_field(fields, "微博等级", _value(base_info, "微博等级"))
    _add_field(fields, "粉丝数量", _value(influence, "粉丝数量"))
    _add_field(fields, "粉丝等级", _value(influence, "粉丝等级"))
    _add_field(fields, "用户认证信息", _value(account_info, "用户认证信息"))
    _add_field(fields, "用户层级", _value(account_info, "用户层级"))
    _add_field(fields, "总发帖数", _value(behavior, "总发帖数"))
    _add_field(fields, "互动密度", _value(behavior, "互动密度"))
    _add_field(fields, "发帖密度", _value(behavior, "发帖密度"))
    _add_field(fields, "活跃天数", _value(behavior, "活跃天数"))
    _add_field(fields, "活跃时间分布", _value(behavior, "活跃时间分布"))
    _add_field(fields, "关注数", _value(follow_info, "关注数"))
    _add_field(fields, "情感倾向", _value(tags, "情感倾向"))

    keywords = behavior.get("keywords_list")
    if isinstance(keywords, dict):
        _add_field(fields, "关键词及频次", _summarize_mapping(keywords, limit=5))

    content_preference = _parse_json_mapping(tags.get("内容偏好"))
    _add_field(fields, "内容偏好", _summarize_mapping(content_preference, limit=5))
    _add_field(fields, "转评赞统计", _summarize_stats(influence.get("转评赞统计")))
    _add_field(fields, "关注博主摘要", _summarize_follows(record, limit=5))

    recent_posts = _recent_posts(record, limit=3)
    if recent_posts:
        fields["近期发帖样例"] = recent_posts

    profile_lines: list[str] = []
    for label, value in fields.items():
        if isinstance(value, list):
            profile_lines.append(
                f"{label}：" + "；".join(f"{idx + 1}. {item}" for idx, item in enumerate(value))
            )
        else:
            profile_lines.append(f"{label}：{value}")

    return {
        "nodes": [],
        "edges": [],
        "other_info": {
            "user_profile": "；".join(profile_lines) if profile_lines else "暂无有效画像",
            "gender": fields.get("用户性别", ""),
            "weibo_profile_fields": fields,
        },
    }


def build_weibo_system_message(user_info: Any) -> str:
    lines: list[str] = []
    name = getattr(user_info, "name", None)
    user_name = getattr(user_info, "user_name", None)
    if name and name != user_name:
        lines.append(f"你的显示名称是：{name}。")
    if user_name:
        lines.append(f"你的微博账号是：{user_name}。")
    if getattr(user_info, "description", None):
        lines.append(f"你的个人简介是：{user_info.description}。")

    profile = getattr(user_info, "profile", None) or {}
    other_info = profile.get("other_info", {}) if isinstance(profile, dict) else {}
    user_profile = other_info.get("user_profile")
    if user_profile:
        lines.append(f"你的画像摘要：{user_profile}。")

    description = "\n".join(lines)
    return f"""
# 目标
你是一名微博用户。我会向你展示微博平台中的帖子、推荐内容和环境信息。请结合你的人设、兴趣偏好和当前语境，选择最合适的动作。

# 自我描述
你的行为必须与自己的画像、历史偏好和平台情境保持一致。
{description}

# 行动要求
- 只选择符合微博场景的动作。
- 优先依据自己的兴趣、活跃习惯、关注对象和近期发帖内容做判断。
- 如果当前没有特别想做的事，可以刷新、搜索，或者选择不做任何事。

# 回复方式
必须通过工具调用执行动作，不要输出额外解释。
"""
