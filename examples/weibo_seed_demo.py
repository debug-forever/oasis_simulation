"""使用微博标注数据初始化平台的示例脚本。"""
from __future__ import annotations

import asyncio
from pathlib import Path

from oasis.social_agent.agent_graph import AgentGraph
from oasis.social_agent.weibo_generator import (generate_weibo_agents,
                                               get_default_weibo_actions)
from oasis.social_platform.channel import Channel
from oasis.social_platform.platform import Platform
from oasis.social_platform.typing import ActionType, DefaultPlatformType


def _prepare_database(db_path: Path) -> None:
    if db_path.exists():
        db_path.unlink()
    db_path.parent.mkdir(parents=True, exist_ok=True)


async def main() -> None:
    dataset_path = Path("weibo_test/total_data_with_descriptions_transformers.json")
    db_path = Path("weibo_test/weibo_demo.db")
    _prepare_database(db_path)

    channel = Channel()
    platform = Platform(
        db_path=str(db_path),
        channel=channel,
        recsys_type="reddit",
        allow_self_rating=False,
        show_score=False,
        max_rec_post_len=100,
        refresh_rec_post_count=5,
    )
    setattr(platform, "platform_type", DefaultPlatformType.WEIBO)

    platform_task = asyncio.create_task(platform.running())

    agent_graph = AgentGraph()
    await generate_weibo_agents(
        dataset_path=str(dataset_path),
        channel=channel,
        agent_graph=agent_graph,
        available_actions=get_default_weibo_actions(),
    )

    await channel.write_to_receive_queue((None, None, ActionType.EXIT))
    await platform_task

    print(f"已将 {agent_graph.get_num_nodes()} 个微博代理写入 {db_path}")


if __name__ == "__main__":
    asyncio.run(main())
