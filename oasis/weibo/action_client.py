from __future__ import annotations

from camel.toolkits import FunctionTool

from oasis.social_agent.agent_action import SocialAction
from oasis.weibo.action_space import normalize_weibo_actions
from oasis.social_platform.typing import ActionType


class WeiboActionClient(SocialAction):
    def get_openai_function_list(
        self,
        available_actions: list[ActionType | str] | None = None,
    ) -> list[FunctionTool]:
        allowed_names = {
            action.value for action in normalize_weibo_actions(available_actions)
        }
        return [
            tool
            for tool in super().get_openai_function_list()
            if tool.func.__name__ in allowed_names
        ]
