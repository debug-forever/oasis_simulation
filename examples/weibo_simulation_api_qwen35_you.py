"""使用微博标注数据运行 Qwen3.5 API 代理示例，所有输出均为中文。"""
from __future__ import annotations

import asyncio
import ast
import json
import logging
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv
from openai import RateLimitError

import oasis
from camel.models import ModelFactory
from camel.types import ModelPlatformType
from oasis import ActionType, LLMAction, ManualAction
from oasis.social_agent.agent import SocialAgent
from oasis.weibo import (
    WeiboRunner,
    WeiboSocialAgent,
    generate_weibo_agent_graph,
    get_default_weibo_actions,
)

# 先读取环境变量，避免密钥硬编码
load_dotenv()

DATASET_PATH = Path(
    os.getenv(
        "WEIBO_DATASET_PATH",
        "weibo_test/total_data_with_descriptions_transformers.json",
    )
)
DB_PATH = Path(os.getenv("WEIBO_DB_PATH", "weibo_test/weibo_sim_api_qwen35_you.db"))


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


def _get_section(record: dict, *keys: str) -> dict:
    for key in keys:
        value = record.get(key)
        if isinstance(value, dict):
            return value
    return {}


def _pick_post_text(record_idx: int, fallback: str) -> str:
    if not WEIBO_RECORDS:
        return fallback
    record = WEIBO_RECORDS[record_idx % len(WEIBO_RECORDS)]
    posts = _get_section(record, "近期发帖内容分析").get("全部帖子合集", []) or []
    for raw in posts:
        text = str(raw).strip()
        if text:
            return text
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
    if not WEIBO_RECORDS:
        return "默认用户"
    record = WEIBO_RECORDS[record_idx % len(WEIBO_RECORDS)]
    base_info = _get_section(record, "个人基本信息")
    username = str(base_info.get("用户名") or f"微博用户{record_idx}")
    profile = str(base_info.get("用户简介") or "暂无简介")
    tags_line = _summarize_tags(record)
    recent = _pick_post_text(record_idx, "暂无历史内容")
    parts = [f"帐号：{username}", f"简介：{profile}"]
    if tags_line:
        parts.append(f"标签：{tags_line}")
    parts.append(f"最近帖子示例：{recent}")
    return "；".join(parts)


def build_llm_model():
    """构建兼容 OpenAI 的微博实验模型。"""
    model_name = os.getenv("WEIBO_MODEL_NAME", "qwen3.5-397b-a17b")
    api_base_url = os.getenv(
        "WEIBO_API_BASE_URL",
        "https://dashscope.aliyuncs.com/compatible-mode/v1",
    )
    api_key = os.getenv("WEIBO_API_KEY", "").strip()
    max_tokens = int(os.getenv("WEIBO_MAX_TOKENS", "2048"))

    if not api_key:
        raise ValueError("缺少 WEIBO_API_KEY，请在 .env 中配置后再运行。")

    print(f"模型名称：{model_name}")
    print(f"接口地址：{api_base_url}")
    print(f"数据集路径：{DATASET_PATH}")

    is_deepseek = (
        "deepseek" in model_name.lower()
        or "deepseek" in api_base_url.lower()
    )
    model_platform = (
        ModelPlatformType.DEEPSEEK
        if is_deepseek
        else ModelPlatformType.OPENAI_COMPATIBLE_MODEL
    )
    print(f"模型平台：{'DeepSeek' if is_deepseek else 'OpenAI-compatible'}")

    return ModelFactory.create(
        model_platform=model_platform,
        model_type=model_name,
        url=api_base_url,
        api_key=api_key,
        model_config_dict={"max_tokens": max_tokens},
    )


def _prepare_database():
    os.environ["OASIS_DB_PATH"] = str(DB_PATH.resolve())
    if DB_PATH.exists():
        try:
            DB_PATH.unlink()
        except Exception:
            pass
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _log_persona(record_idx: int, label: str):
    try:
        print(f"{label} 数据集信息：{_describe_persona(record_idx)}")
    except Exception:
        pass


def update_follower_id_list():
    env_db_path = os.environ.get("OASIS_DB_PATH")
    conn = sqlite3.connect(env_db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT weibo_id, user_id
        FROM user
        WHERE weibo_id IS NOT NULL
        """
    )
    weibo_to_user = {weibo_id: user_id for weibo_id, user_id in cursor.fetchall()}

    cursor.execute(
        """
        SELECT rowid, follower_list
        FROM user
        WHERE follower_list IS NOT NULL
        """
    )
    rows = cursor.fetchall()

    update_rows = []

    for rowid, follower_list_str in rows:
        try:
            if not isinstance(follower_list_str, str):
                continue
            follower_list_str = follower_list_str.strip()
            if not follower_list_str:
                continue
            try:
                follower_weibo_ids = json.loads(follower_list_str)
            except json.JSONDecodeError:
                follower_weibo_ids = ast.literal_eval(follower_list_str)

            if not isinstance(follower_weibo_ids, list):
                continue

            follower_user_ids = [
                weibo_to_user[w] for w in follower_weibo_ids if w in weibo_to_user
            ]

            update_rows.append((json.dumps(follower_user_ids, ensure_ascii=False), rowid))

        except Exception as exc:
            print(f"[WARN] rowid={rowid} 处理失败: {exc}")

    cursor.executemany(
        """
        UPDATE user
        SET follower_id_list = ?
        WHERE rowid = ?
        """,
        update_rows,
    )

    conn.commit()
    conn.close()

    print(f"更新完成，共处理 {len(update_rows)} 条记录")


def _use_legacy_oasis_env() -> bool:
    return os.getenv("WEIBO_USE_LEGACY_OASIS_ENV", "0").strip() == "1"


def _build_weibo_env(agent_graph, use_legacy_oasis_env: bool):
    if use_legacy_oasis_env:
        print("运行链路：旧版 OasisEnv（可回滚路径）")
        return oasis.make(
            agent_graph=agent_graph,
            platform=oasis.DefaultPlatformType.WEIBO,
            database_path=str(DB_PATH),
        )

    print("运行链路：微博专用运行器（半脱钩路径）")
    return WeiboRunner(
        agent_graph=agent_graph,
        database_path=str(DB_PATH),
    )


def _build_llm_actions(env, max_agents: int):
    all_agents = [agent for _, agent in env.agent_graph.get_agents()]
    if max_agents <= 0:
        selected = all_agents
    else:
        selected = all_agents[:max_agents]
    return {agent: LLMAction() for agent in selected}


async def _step_with_retry(
    env, actions: dict, max_retries: int, retry_wait_seconds: float
):
    for attempt in range(max_retries + 1):
        try:
            await env.step(actions)
            return
        except RateLimitError as exc:
            if attempt >= max_retries:
                raise
            wait_seconds = retry_wait_seconds * (2**attempt)
            print(
                f"[WARN] 触发限流，将在 {wait_seconds:.1f}s 后重试 "
                f"({attempt + 1}/{max_retries})，错误：{exc}"
            )
            await asyncio.sleep(wait_seconds)


def _get_trace_count(db_path: Path) -> int:
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM trace")
        result = cur.fetchone()
        conn.close()
        return int(result[0]) if result else 0
    except Exception:
        return 0


def _get_trace_action_stats(db_path: Path, offset: int) -> list[tuple[str, int]]:
    try:
        conn = sqlite3.connect(str(db_path))
        cur = conn.cursor()
        cur.execute(
            """
            SELECT action, COUNT(*)
            FROM trace
            WHERE rowid > ?
            GROUP BY action
            ORDER BY COUNT(*) DESC
            """,
            (offset,),
        )
        rows = cur.fetchall()
        conn.close()
        return [(str(action), int(count)) for action, count in rows]
    except Exception:
        return []


async def _run_step(
    env,
    name: str,
    actions: dict,
    db_path: Path,
    max_retries: int,
    retry_wait_seconds: float,
    verbose: bool,
):
    before = _get_trace_count(db_path)
    await _step_with_retry(env, actions, max_retries, retry_wait_seconds)
    after = _get_trace_count(db_path)
    if verbose:
        stats = _get_trace_action_stats(db_path, before)
        stats_text = "、".join([f"{k}:{v}" for k, v in stats]) if stats else "无可见动作"
        print(f"[回合] {name} | 新增trace={after - before} | 明细={stats_text}")


async def main():
    logging.basicConfig(level=logging.INFO)

    if not WEIBO_RECORDS:
        print("❌ 数据集为空，程序终止")
        return

    llm_model = build_llm_model()
    available_actions = get_default_weibo_actions()
    use_legacy_oasis_env = _use_legacy_oasis_env()
    agent_cls = SocialAgent if use_legacy_oasis_env else WeiboSocialAgent
    _prepare_database()

    agent_graph = await generate_weibo_agent_graph(
        dataset_path=str(DATASET_PATH),
        model=llm_model,
        available_actions=available_actions,
        agent_cls=agent_cls,
    )

    env = _build_weibo_env(agent_graph, use_legacy_oasis_env)

    await env.reset()
    update_follower_id_list()

    _log_persona(0, "智能体0")
    llm_agent_limit = int(os.getenv("WEIBO_LLM_AGENT_LIMIT", "0"))
    llm_rounds = int(os.getenv("WEIBO_LLM_ROUNDS", "17"))
    llm_retry = int(os.getenv("WEIBO_LLM_RETRY", "4"))
    llm_retry_wait = float(os.getenv("WEIBO_LLM_RETRY_WAIT_SECONDS", "2"))
    llm_step_interval = float(os.getenv("WEIBO_LLM_STEP_INTERVAL_SECONDS", "0.8"))
    verbose = os.getenv("WEIBO_VERBOSE", "1").strip() == "1"

    if verbose:
        agent_count = len([agent for _, agent in env.agent_graph.get_agents()])
        active_llm_agents = agent_count if llm_agent_limit <= 0 else llm_agent_limit
        print(
            "运行参数："
            f"总agent={agent_count}，LLM参与agent={active_llm_agents}，"
            f"LLM轮数={llm_rounds}，重试={llm_retry}，间隔={llm_step_interval}s"
        )

    actions_1 = {
        env.agent_graph.get_agent(6): ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": "泰国和柬埔寨打起来了，大家怎么看？"},
        )
    }
    target_agents = env.agent_graph.get_agents([1, 3, 5, 7, 9])
    actions_2 = {agent: LLMAction() for _, agent in target_agents}
    actions_3 = {
        env.agent_graph.get_agent(74): ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": "支持泰国打击柬埔寨电诈园区"},
        )
    }
    actions_4 = _build_llm_actions(env, llm_agent_limit)
    actions_5 = {
        env.agent_graph.get_agent(2): ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": "大家用的手机上华为还是苹果？"},
        )
    }
    actions_6 = {
        env.agent_graph.get_agent(3): ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": "泰国和柬埔寨说怎么打起来的？"},
        )
    }
    actions_7 = {
        env.agent_graph.get_agent(3): ManualAction(
            action_type=ActionType.CREATE_POST,
            action_args={"content": "这次冲突会不会影响到中国？"},
        )
    }

    await _run_step(
        env, "手动发帖1", actions_1, DB_PATH, llm_retry, llm_retry_wait, verbose
    )
    await _run_step(
        env, "定向LLM回合", actions_2, DB_PATH, llm_retry, llm_retry_wait, verbose
    )
    await _run_step(
        env, "手动发帖2", actions_3, DB_PATH, llm_retry, llm_retry_wait, verbose
    )
    await _run_step(
        env, "手动发帖3", actions_5, DB_PATH, llm_retry, llm_retry_wait, verbose
    )
    await _run_step(
        env, "全体LLM回合A", actions_4, DB_PATH, llm_retry, llm_retry_wait, verbose
    )
    await asyncio.sleep(llm_step_interval)
    await _run_step(
        env, "手动发帖4", actions_6, DB_PATH, llm_retry, llm_retry_wait, verbose
    )
    await _run_step(
        env, "全体LLM回合B", actions_4, DB_PATH, llm_retry, llm_retry_wait, verbose
    )
    await asyncio.sleep(llm_step_interval)
    await _run_step(
        env, "手动发帖5", actions_7, DB_PATH, llm_retry, llm_retry_wait, verbose
    )
    for _ in range(llm_rounds):
        await _run_step(
            env,
            "循环LLM回合",
            actions_4,
            DB_PATH,
            llm_retry,
            llm_retry_wait,
            verbose,
        )
        await asyncio.sleep(llm_step_interval)

    await env.close()
    print(f"微博 API 实验结束，数据库位置：{DB_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
