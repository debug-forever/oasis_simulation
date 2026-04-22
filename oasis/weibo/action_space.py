from __future__ import annotations

from oasis.social_platform.typing import ActionType

WEIBO_ALLOWED_ACTIONS: list[ActionType] = [
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

WEIBO_ALLOWED_ACTION_NAMES: tuple[str, ...] = tuple(
    action.value for action in WEIBO_ALLOWED_ACTIONS
)


def get_default_weibo_actions() -> list[ActionType]:
    return list(WEIBO_ALLOWED_ACTIONS)


def normalize_weibo_actions(
    actions: list[ActionType | str] | None = None,
) -> list[ActionType]:
    if not actions:
        return get_default_weibo_actions()

    allowed_map = {action.value: action for action in WEIBO_ALLOWED_ACTIONS}
    normalized: list[ActionType] = []
    seen: set[str] = set()

    for action in actions:
        action_name = action.value if isinstance(action, ActionType) else str(action)
        if action_name not in allowed_map:
            raise ValueError(f"微博动作白名单不支持动作: {action_name}")
        if action_name in seen:
            continue
        normalized.append(allowed_map[action_name])
        seen.add(action_name)

    return normalized
