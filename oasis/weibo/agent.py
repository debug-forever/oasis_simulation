from __future__ import annotations

import inspect
from typing import TYPE_CHECKING, Any, Callable, List, Optional, Union

from camel.agents import ChatAgent
from camel.messages import BaseMessage
from camel.models import BaseModelBackend, ModelManager
from camel.prompts import TextPrompt
from camel.toolkits import FunctionTool
from camel.types import OpenAIBackendRole

from oasis.social_agent.agent import SocialAgent, agent_log
from oasis.social_agent.agent_environment import SocialEnvironment
from oasis.social_agent.agent_graph import AgentGraph
from oasis.social_platform import Channel
from oasis.social_platform.config import UserInfo
from oasis.social_platform.typing import ActionType
from oasis.weibo.action_client import WeiboActionClient
from oasis.weibo.action_space import normalize_weibo_actions
from oasis.weibo.profile_builder import build_weibo_system_message

if TYPE_CHECKING:
    from oasis.social_agent.agent_graph import AgentGraph


class WeiboSocialAgent(SocialAgent):
    def __init__(
        self,
        agent_id: int,
        user_info: UserInfo,
        user_info_template: TextPrompt | None = None,
        channel: Channel | None = None,
        model: Optional[
            Union[BaseModelBackend, List[BaseModelBackend], ModelManager]
        ] = None,
        agent_graph: AgentGraph = None,
        available_actions: list[ActionType] | None = None,
        tools: Optional[List[Union[FunctionTool, Callable]]] = None,
        max_iteration: int = 1,
        interview_record: bool = False,
    ):
        self.social_agent_id = agent_id
        self.user_info = user_info
        self.channel = channel or Channel()
        self.env = SocialEnvironment(WeiboActionClient(agent_id, self.channel))
        self.available_actions = normalize_weibo_actions(available_actions)

        if user_info_template is None:
            system_message_content = build_weibo_system_message(self.user_info)
        else:
            system_message_content = self.user_info.to_custom_system_message(
                user_info_template
            )

        system_message = BaseMessage.make_assistant_message(
            role_name="system",
            content=system_message_content,
        )

        self.action_tools = self.env.action.get_openai_function_list(
            self.available_actions
        )
        all_tools = (tools or []) + self.action_tools

        ChatAgent.__init__(
            self,
            system_message=system_message,
            model=model,
            scheduling_strategy="random_model",
            tools=all_tools,
        )
        self.max_iteration = max_iteration
        self.interview_record = interview_record
        self.agent_graph = agent_graph
        self.test_prompt = (
            "\n"
            "你是一名微博用户。现在有一位作家正在考虑是否投入大量时间去写一本新小说。"
            "如果成功，这本书可能大幅提升她的职业发展；如果失败，她会付出大量时间和精力却没有明显回报。\n"
            "\n"
            "你认为她应该怎么做？"
        )

    async def perform_action_by_llm(self):
        env_prompt = await self.env.to_text_prompt()
        user_msg = BaseMessage.make_user_message(
            role_name="User",
            content=(
                "请在观察微博平台环境后执行合适的社交动作。"
                "不要把行为局限在单一动作上，例如只点赞。"
                f"以下是你当前可见的微博环境：{env_prompt}"
            ),
        )
        try:
            agent_log.info(
                f"微博智能体 {self.social_agent_id} 正在观察环境：{env_prompt}"
            )
            response = await self.astep(user_msg)
            for tool_call in response.info["tool_calls"]:
                action_name = tool_call.tool_name
                args = tool_call.args
                agent_log.info(
                    f"微博智能体 {self.social_agent_id} 执行动作：{action_name}，参数：{args}"
                )
                return response
        except Exception as e:
            agent_log.error(f"微博智能体 {self.social_agent_id} 执行动作失败：{e}")
            return e

    async def perform_test(self):
        _ = BaseMessage.make_user_message(role_name="User", content="你是一名微博用户。")
        openai_messages, num_tokens = self.memory.get_context()
        openai_messages = ([{
            "role": self.system_message.role_name,
            "content": self.system_message.content.split("# RESPONSE FORMAT")[0],
        }] + openai_messages + [{
            "role": "user",
            "content": self.test_prompt,
        }])

        agent_log.info(f"微博智能体 {self.social_agent_id} 测试提示：{openai_messages}")
        response = await self._aget_model_response(
            openai_messages=openai_messages,
            num_tokens=num_tokens,
        )
        content = response.output_messages[0].content
        agent_log.info(f"微博智能体 {self.social_agent_id} 测试回复：{content}")
        return {
            "user_id": self.social_agent_id,
            "prompt": openai_messages,
            "content": content,
        }

    async def perform_interview(self, interview_prompt: str):
        user_msg = BaseMessage.make_user_message(
            role_name="User",
            content="你是一名微博用户。",
        )

        if self.interview_record:
            self.update_memory(message=user_msg, role=OpenAIBackendRole.SYSTEM)

        openai_messages, num_tokens = self.memory.get_context()
        openai_messages = ([{
            "role": self.system_message.role_name,
            "content": self.system_message.content.split("# RESPONSE FORMAT")[0],
        }] + openai_messages + [{
            "role": "user",
            "content": interview_prompt,
        }])

        agent_log.info(f"微博智能体 {self.social_agent_id} 访谈提示：{openai_messages}")
        response = await self._aget_model_response(
            openai_messages=openai_messages,
            num_tokens=num_tokens,
        )
        content = response.output_messages[0].content
        agent_log.info(f"微博智能体 {self.social_agent_id} 访谈回复：{content}")
        return {
            "user_id": self.social_agent_id,
            "prompt": openai_messages,
            "content": content,
        }

    async def perform_action_by_hci(self) -> Any:
        print("请选择一个要执行的微博动作：")
        function_list = list(self.action_tools)
        for i, tool in enumerate(function_list):
            agent_log.info(
                f"微博智能体 {self.social_agent_id} 可选动作：{i} {tool.func.__name__}"
            )

        selection = int(input("请输入动作编号："))
        if not 0 <= selection < len(function_list):
            agent_log.error(f"微博智能体 {self.social_agent_id} 输入的动作编号无效。")
            return None

        func = function_list[selection].func
        params = inspect.signature(func).parameters
        args: list[str] = []
        for param in params.values():
            args.append(input(f"请输入参数 {param.name} 的值："))

        return await func(*args)

    async def perform_action_by_data(self, func_name, *args, **kwargs) -> Any:
        func_name = func_name.value if isinstance(func_name, ActionType) else func_name
        function_list = list(self.action_tools)
        for tool in function_list:
            if tool.func.__name__ == func_name:
                result = await tool.func(*args, **kwargs)
                agent_log.info(f"微博智能体 {self.social_agent_id} 执行结果：{result}")
                return result
        raise ValueError(f"微博动作白名单中不存在函数: {func_name}")
