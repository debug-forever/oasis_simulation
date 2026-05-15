from __future__ import annotations

import asyncio
import logging
from typing import Union

from oasis.environment.env_action import LLMAction, ManualAction
from oasis.social_agent.agent import SocialAgent
from oasis.social_agent.agent_graph import AgentGraph
from oasis.social_platform.channel import Channel
from oasis.social_platform.platform import Platform
from oasis.social_platform.typing import ActionType, DefaultPlatformType

runner_log = logging.getLogger("oasis.weibo_runner")


class WeiboRunner:
    def __init__(
        self,
        agent_graph: AgentGraph,
        database_path: str | None = None,
        platform: Platform | None = None,
        semaphore: int = 128,
    ) -> None:
        self.agent_graph = agent_graph
        self.llm_semaphore = asyncio.Semaphore(semaphore)
        self.platform_task = None

        if platform is not None:
            self.platform = platform
            self.channel = platform.channel
            return

        if database_path is None:
            raise ValueError("微博专用运行器需要提供 database_path 或 platform。")

        self.channel = Channel()
        self.platform = Platform(
            db_path=database_path,
            channel=self.channel,
            recsys_type="weibo",
            allow_self_rating=False,
            show_score=False,
            max_rec_post_len=10,
            refresh_rec_post_count=5,
        )
        setattr(self.platform, "platform_type", DefaultPlatformType.WEIBO)

    async def reset(self) -> None:
        self.platform_task = asyncio.create_task(self.platform.running())

        for _, agent in self.agent_graph.get_agents():
            agent.channel = self.channel
            agent.env.action.channel = self.channel

        sign_up_tasks = []
        for _, agent in self.agent_graph.get_agents():
            user_name = (
                agent.user_info.user_name
                or agent.user_info.name
                or f"weibo_user_{agent.social_agent_id}"
            )
            sign_up_tasks.append(
                agent.env.action.sign_up(
                    user_name=user_name,
                    name=agent.user_info.name or user_name,
                    bio=agent.user_info.description or "",
                    follower_list=agent.user_info.follower_list,
                    follower_num_list=agent.user_info.follower_num_list,
                    weibo_id=agent.user_info.weibo_id,
                )
            )

        results = await asyncio.gather(*sign_up_tasks)
        for _, result in zip(self.agent_graph.get_agents(), results):
            if not result.get("success"):
                raise RuntimeError(f"微博专用运行器注册代理失败：{result}")

    async def _perform_llm_action(self, agent: SocialAgent):
        async with self.llm_semaphore:
            return await agent.perform_action_by_llm()

    async def step(
        self,
        actions: dict[
            SocialAgent,
            Union[ManualAction, LLMAction, list[Union[ManualAction, LLMAction]]],
        ],
    ) -> None:
        await self.platform.update_rec_table()
        tasks = []

        for agent, action in actions.items():
            action_list = action if isinstance(action, list) else [action]
            for single_action in action_list:
                if isinstance(single_action, ManualAction):
                    tasks.append(
                        agent.perform_action_by_data(
                            single_action.action_type,
                            **single_action.action_args,
                        )
                    )
                elif isinstance(single_action, LLMAction):
                    tasks.append(self._perform_llm_action(agent))

        await asyncio.gather(*tasks)

    async def close(self) -> None:
        await self.channel.write_to_receive_queue((None, None, ActionType.EXIT))
        if self.platform_task is not None:
            await self.platform_task
        runner_log.info(
            "微博专用运行器已结束，数据库路径：%s",
            self.platform.db_path,
        )
