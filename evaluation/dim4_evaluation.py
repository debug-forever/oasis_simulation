"""
维度四：角色一致性评估（并行版）
包含预处理（生成agent_personas.json）和正式评测
"""

import os
import time
import json
import pandas as pd
import random
import sys
import concurrent.futures
from openai import OpenAI
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 设置输出
sys.stdout = open(OUTPUT_DIR / "output4.log", "w", encoding="utf-8")
print("================ 维度四：角色一致性评估（并行版） ================")


# ============================================================
# 1. 配置
# ============================================================
REAL_DATA_FILE = BASE_DIR / "groundtruth" / "top100_users_complete_data_post_followers.json"  # 真实数据 JSON 文件
SIM_POST_FILE = BASE_DIR / "post.csv"
SIM_COMMENT_FILE = BASE_DIR / "comment.csv"

# OpenAI API 配置（从环境变量获取）
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL")
MODEL_NAME = os.environ.get("OPENAI_MODEL")

# 检查API Key是否配置
if not OPENAI_API_KEY:
    print("错误: 请设置环境变量 OPENAI_API_KEY")
    print("示例: export OPENAI_API_KEY='your-api-key'")
    sys.exit(1)

# 并发配置
MAX_WORKERS = 10  # 并发线程数


# ============================================================
# 2. 预处理函数：生成agent_personas.json
# ============================================================
MAX_REAL_POSTS = 3


def extract_persona(user, agent_id):
    """从真实用户数据提取人设"""
    source_uid = str(user["用户ID"])

    # 基本信息
    basic_info = user["个人基本信息"]
    basic_profile = {
        "username": basic_info.get("用户名", ""),
        "gender": basic_info.get("用户性别", "未知"),
        "bio": basic_info.get("用户简介", ""),
        "region": basic_info.get("地区信息", "未知")
    }

    # 内容偏好
    topic_pref = user["标签特征"].get("内容偏好", {})

    # 关键词
    keywords = user["用户行为特征"].get("keywords_list", {})

    # 真实文本 grounding
    real_posts = []
    post_analysis = user.get("近期发帖内容分析", {})
    real_posts += post_analysis.get("全部帖子合集", [])
    real_posts += post_analysis.get("构建帖子合集", [])

    # 清洗
    real_posts = [p.strip() for p in real_posts if isinstance(p, str) and p.strip()]

    # 随机抽样
    sampled_posts = random.sample(real_posts, min(len(real_posts), MAX_REAL_POSTS))

    persona = {
        "agent_id": agent_id,
        "source_user_id": source_uid,
        "persona": {
            "basic_profile": basic_profile,
            "user_level": user["账号类型与层级"].get("用户层级", "未知"),
            "content_profile": {
                "topic_preference": topic_pref,
                "keywords": keywords
            },
            "linguistic_grounding": {
                "real_posts": sampled_posts
            }
        }
    }

    return persona


def preprocess_personas():
    """预处理：生成智能体人设JSON"""
    print("正在进行预处理，提取智能体人设...")

    raw_users = []
    with open(REAL_DATA_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw_users.append(json.loads(line))

    agent_personas = {}
    for idx, user in enumerate(raw_users):
        persona = extract_persona(user, agent_id=idx)
        agent_personas[str(idx)] = persona

    persona_path = BASE_DIR / "agent_personas.json"
    with open(persona_path, "w", encoding="utf-8") as f:
        json.dump(agent_personas, f, ensure_ascii=False, indent=2)

    print(f"智能体人设已保存到 agent_personas.json，共 {len(agent_personas)} 个智能体")

    return persona_path


# ============================================================
# 3. 评测函数（并行版）
# ============================================================

# OpenAI Client
client = OpenAI(
    api_key=OPENAI_API_KEY,
    base_url=OPENAI_BASE_URL
)

# Prompt 模板
SYSTEM_PROMPT = (
    "You are an expert evaluator in social simulation and human behavior modeling. "
    "Your task is to evaluate whether a generated social media text is consistent "
    "with the given agent persona.\n\n"
    "You must provide an integer score from 1 to 5.\n"
    "Do not provide explanations."
)

USER_PROMPT_TEMPLATE = """
Agent Persona:
{persona}

Generated Text:
{text}

Question:
How consistent is the generated text with the agent persona?

Scoring Guidelines:
1 = Completely inconsistent with the persona
2 = Mostly inconsistent
3 = Partially consistent
4 = Mostly consistent
5 = Highly consistent and believable

Answer with a single integer between 1 and 5.
"""


def judge(persona: str, text: str):
    """使用LLM评判文本与角色的一致性"""
    try:
        resp = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT_TEMPLATE.format(
                    persona=persona, text=text
                )}
            ],
            temperature=0.0,
            max_tokens=5
        )

        score = int(resp.choices[0].message.content.strip())
        if 1 <= score <= 5:
            return score
    except Exception as e:
        print(f"Judge error: {e}")

    return None


def extract_agent_texts(post_csv, comment_csv):
    """提取所有智能体生成的文本"""
    samples = []

    # Post 表
    posts = pd.read_csv(post_csv)
    for _, row in posts.iterrows():
        user_id = row["user_id"]

        # 原创帖 content
        if pd.notna(row.get("content")) and str(row["content"]).strip() != "":
            samples.append({
                "agent_id": str(user_id),
                "text": row["content"],
                "source": "post_content",
                "ref_id": row["post_id"]
            })

        # 转发 quote_content
        if pd.notna(row.get("quote_content")) and str(row["quote_content"]).strip() != "":
            samples.append({
                "agent_id": str(user_id),
                "text": row["quote_content"],
                "source": "post_quote",
                "ref_id": row["post_id"]
            })

    # Comment 表
    comments = pd.read_csv(comment_csv)
    for _, row in comments.iterrows():
        if pd.notna(row.get("content")) and str(row["content"]).strip() != "":
            samples.append({
                "agent_id": str(row["user_id"]),
                "text": row["content"],
                "source": "comment",
                "ref_id": row["comment_id"]
            })

    return pd.DataFrame(samples)


def process_sample(args):
    """处理单条样本的函数，用于并行执行"""
    row, personas = args
    agent_id = row["agent_id"]
    persona = personas.get(agent_id)

    if persona is None:
        return None

    # 将persona转为字符串
    persona_str = json.dumps(persona, ensure_ascii=False)
    score = judge(persona_str, row["text"])

    if score is not None:
        return {
            "agent_id": agent_id,
            "source": row["source"],
            "ref_id": row["ref_id"],
            "score": score,
            "text": row["text"]
        }
    return None


def evaluate_role_consistency_parallel(post_csv, comment_csv, persona_json):
    """并行评估角色一致性"""
    print("\n正在加载智能体人设...")
    personas = json.load(open(persona_json, "r", encoding="utf-8"))

    print("正在提取智能体生成的文本...")
    samples = extract_agent_texts(post_csv, comment_csv)
    print(f"共提取 {len(samples)} 条文本")
    print(f"使用 {MAX_WORKERS} 并行 workers")

    results = []
    samples_list = samples.to_dict('records')

    # 并行执行
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        futures = {executor.submit(process_sample, (row, personas)): row for row in samples_list}

        completed = 0
        for future in concurrent.futures.as_completed(futures):
            result = future.result()
            if result:
                results.append(result)
            completed += 1
            if completed % 50 == 0:
                print(f"Progress: {completed}/{len(samples_list)}")

    df_scores = pd.DataFrame(results)

    if len(df_scores) > 0:
        avg_score = df_scores["score"].mean()

        summary = {
            "Average Role Consistency Score": avg_score,
            "Pass (>3.5)": avg_score > 3.5,
            "Num Text Samples": len(df_scores),
            "Num Agents": df_scores["agent_id"].nunique()
        }

        print("\n=== 评估结果 ===")
        for k, v in summary.items():
            print(f"{k}: {v}")

        # 保存详细结果
        df_scores.to_csv(BASE_DIR / "role_consistency_all_texts.csv", index=False)
        print("\n详细结果已保存到 role_consistency_all_texts.csv")

        return summary
    else:
        print("未能获取任何有效评分")
        return None


# ============================================================
# 4. 主函数
# ============================================================
def main():
    start_time = time.time()

    # 预处理
    preprocess_personas()

    # 正式评测
    results = evaluate_role_consistency_parallel(
        post_csv=SIM_POST_FILE,
        comment_csv=SIM_COMMENT_FILE,
        persona_json=BASE_DIR / "agent_personas.json"
    )

    elapsed = time.time() - start_time
    print(f"\n总耗时: {elapsed:.2f} 秒")
    print("\n================ 评估完成 ================")

    return results


if __name__ == "__main__":
    main()