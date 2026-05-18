import asyncio
import io
import logging
import os
import sys
import time
from pathlib import Path
from datetime import datetime

from .models import SimulationTask, SimStatus


logger = logging.getLogger(__name__)


class SimulationExecutor:
    def __init__(self, task: SimulationTask):
        self.task = task
        self._stop_flag = False
        
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
        except Exception:
            pass
        
        logging.raiseExceptions = False
    
    def stop(self):
        self._stop_flag = True
    
    def _log(self, message: str):
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_line = f"[{timestamp}] {message}"
        logger.info(log_line)
        self.task.logs.append(log_line)
        
        if len(self.task.logs) > 500:
            self.task.logs = self.task.logs[-500:]
    
    async def run(self):
        start_time = time.time()
        
        try:
            self.task.status = SimStatus.RUNNING
            self.task.started_at = datetime.now()
            self._log("🚀 开始模拟任务...")
            
            self._log(f"配置: {self.task.config.num_agents}个agent, {self.task.config.num_rounds}轮")
            
            # 准备数据库路径
            db_path = self._prepare_database()
            self.task.db_path = str(db_path)
            
            await self._run_simulation()
            
            # 完成
            self.task.status = SimStatus.COMPLETED
            self.task.completed_at = datetime.now()
            self.task.stats.elapsed_time = time.time() - start_time
            
            self._log(f"✅ 模拟完成！数据库: {self.task.db_path}")
            self._log(f"总用时: {self.task.stats.elapsed_time:.2f}秒")
            
            try:
                self._log("🔄 切换数据库连接到新生成的模拟数据库...")
                from database.db_manager import switch_database
                switch_database(str(self.task.db_path))
                self._log("✅ 数据库连接已切换！前端现在可以查看新的模拟结果")
            except Exception as e:
                self._log(f"⚠️ 数据库切换失败（不影响模拟结果）: {e}")
            
            
        except Exception as e:
            self.task.status = SimStatus.FAILED
            self.task.error = str(e)
            self.task.completed_at = datetime.now()
            self._log(f"❌ 模拟失败: {e}")
            import traceback
            self._log(traceback.format_exc())
    
    def _prepare_database(self) -> Path:
        db_path = Path("weibo_test") / self.task.config.output_db_name
        
        db_path.parent.mkdir(parents=True, exist_ok=True)
        
        if db_path.exists():
            try:
                db_path.unlink()
                self._log(f"删除旧数据库: {db_path}")
            except Exception as e:
                self._log(f"⚠️ 无法删除旧数据库: {e}")
        
        os.environ["OASIS_DB_PATH"] = str(db_path.resolve())
        
        return db_path
    
    def _build_llm_model(self):
        from camel.models import ModelFactory
        from camel.types import ModelPlatformType, ModelType
        
        provider = self.task.config.llm_provider.lower()
        model_name = self.task.config.model_name
        
        self._log(f"🔧 构建LLM模型: {provider}")
        
        if provider == "openai":
            self._log(f"✅ 使用OpenAI (模型: {model_name})")
            if model_name and model_name != "gpt-4o-mini":
                return ModelFactory.create(
                    model_platform=ModelPlatformType.OPENAI,
                    model_type=model_name,
                )
            else:
                return ModelFactory.create(
                    model_platform=ModelPlatformType.OPENAI,
                    model_type=ModelType.GPT_4O_MINI,
                )
        
        elif provider in ["deepseek", "qwen"]:
            base_url = self.task.config.llm_endpoint
            self._log(f"✅ 使用{provider.upper()} 兼容API")
            self._log(f"   端点: {base_url}")
            return ModelFactory.create(
                model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
                model_type=model_name,
                url=base_url,
            )
        
        elif provider == "vllm":
            self._log(f"✅ 连接vLLM: {self.task.config.llm_endpoint}")
            return ModelFactory.create(
                model_platform=ModelPlatformType.OPENAI_COMPATIBLE_MODEL,
                model_type=model_name,
                url=self.task.config.llm_endpoint,
            )
        
        else:
            raise ValueError(f"❌ 不支持的LLM提供商: {provider}")
    
    async def _run_simulation(self):
        try:
            self._log("📦 导入Oasis模块...")
            import oasis
            from oasis import ActionType, LLMAction, ManualAction
            from oasis.social_agent.weibo_generator import (
                generate_weibo_agent_graph,
                get_default_weibo_actions
            )
            
            llm_model = None
            if self.task.config.enable_llm:
                llm_model = self._build_llm_model()
            else:
                self._log("⚪ LLM未启用，将跳过LLM动作")
            
            available_actions = get_default_weibo_actions()
            
            self._log(f"🤖 生成{self.task.config.num_agents}个Agent...")
            dataset_path = self.task.config.dataset_path
            if not Path(dataset_path).is_absolute():
                project_root = Path(__file__).parent.parent.parent.parent
                dataset_path = str(project_root / dataset_path)
                self._log(f"📁 数据集路径: {dataset_path}")
            
            agent_graph = await generate_weibo_agent_graph(
                dataset_path=dataset_path,
                model=llm_model,
                available_actions=available_actions,
                num_agents=self.task.config.num_agents,
            )
            
            self._log("🌍 创建Oasis环境...")
            env = oasis.make(
                agent_graph=agent_graph,
                platform=oasis.DefaultPlatformType.WEIBO,
                database_path=str(self.task.db_path),
            )
            
            self._log("🔄 重置环境...")
            await env.reset()
            self.task.stats.users_created = len(list(agent_graph.get_agents()))
            
            self._log(f"🔍 检查: enable_seed_posts={self.task.config.enable_seed_posts}, num_seed_posts={self.task.config.num_seed_posts}")
            if self.task.config.enable_seed_posts:
                await self._seed_initial_posts(env, agent_graph)
            else:
                self._log("⏭️ 跳过初始帖子播种（已禁用）")
            
            self._log(f"▶️ 开始执行{self.task.config.num_rounds}轮模拟...")
            
            for round_idx in range(self.task.config.num_rounds):
                if self._stop_flag:
                    self._log("⏸️ 收到停止信号")
                    break
                
                self._log(f"")
                self._log(f"{'='*50}")
                self._log(f"📍 Round {round_idx + 1}/{self.task.config.num_rounds}")
                self._log(f"{'='*50}")
                
                self.task.progress.update(
                    round_idx + 1,
                    self.task.config.num_rounds,
                    f"执行第{round_idx + 1}轮模拟"
                )
                
                if self.task.config.enable_llm and llm_model:
                    self._log("🤖 所有Agent执行LLM动作...")
                    actions = {agent: LLMAction() for _, agent in agent_graph.get_agents()}
                    await env.step(actions)
                    self._log(f"✅ Round {round_idx + 1} 完成（使用真实LLM）")
                else:
                    if round_idx == 0:
                        self._log("📝 Agent 0 创建欢迎帖子（演示模式）...")
                        actions = {
                            env.agent_graph.get_agent(0): ManualAction(
                                action_type=ActionType.CREATE_POST,
                                action_args={"content": f"这是一个模拟测试帖子 (Round {round_idx + 1})"},
                            )
                        }
                        await env.step(actions)
                    else:
                        self._log("⏭️ 跳过LLM动作（演示模式）")
                
                await asyncio.sleep(0.5)
            
            self._log("")
            self._log("🔚 关闭环境...")
            await env.close()
            
            self._log("📊 统计数据库中的真实数据...")
            import sqlite3
            try:
                conn = sqlite3.connect(str(self.task.db_path))
                cursor = conn.cursor()
                
                cursor.execute("SELECT COUNT(*) FROM post")
                self.task.stats.posts_created = cursor.fetchone()[0]
                
                cursor.execute("SELECT COUNT(*) FROM comment")
                self.task.stats.comments_created = cursor.fetchone()[0]
                
                conn.close()
                self._log(f"✅ 成功读取统计数据")
            except Exception as e:
                self._log(f"⚠️ 读取统计数据失败: {e}")
            
            self._log(f"✅ 模拟成功完成！")
            self._log(f"📊 统计: {self.task.stats.users_created}个用户, "
                     f"{self.task.stats.posts_created}个帖子, "
                     f"{self.task.stats.comments_created}条评论")
            
        except ImportError as e:
            self._log(f"⚠️ 导入Oasis模块失败: {e}")
            self._log("🎭 切换到Mock演示模式...")
            await self._mock_simulation()
        except Exception as e:
            self._log(f"❌ 模拟执行出错: {e}")
            raise
    
    async def _seed_initial_posts(self, env, agent_graph):
        from oasis import ActionType, ManualAction
        
        self._log("")
        self._log("🌱 播种初始帖子...")
        
        num_to_seed = min(self.task.config.num_seed_posts, len(self.task.config.seed_agent_ids))
        
        for i in range(num_to_seed):
            agent_id = self.task.config.seed_agent_ids[i]
            
            try:
                agent = env.agent_graph.get_agent(agent_id)
            except Exception as e:
                self._log(f"  ⚠️ Agent {agent_id} 不存在，跳过")
                continue
            
            content = self._generate_seed_post_content(agent_id, i)
            
            actions = {
                agent: ManualAction(
                    action_type=ActionType.CREATE_POST,
                    action_args={"content": content},
                )
            }
            
            await env.step(actions)
            self._log(f"  ✅ Agent {agent_id} 发布了初始帖子")
            await asyncio.sleep(0.3)
        
        self._log(f"🌱 完成播种：{num_to_seed}个初始帖子")
        self._log("")
    
    def _generate_seed_post_content(self, agent_id: int, index: int) -> str:
        try:
            dataset_path = Path(self.task.config.dataset_path)
            if not dataset_path.is_absolute():
                project_root = Path(__file__).parent.parent.parent.parent
                dataset_path = project_root / dataset_path
            
            if dataset_path.exists():
                import json
                data = json.loads(dataset_path.read_text(encoding='utf-8'))
                if isinstance(data, list) and len(data) > agent_id:
                    record = data[agent_id]
                    posts_section = record.get("近期发帖内容分析", {})
                    all_posts = posts_section.get("全部帖子合集", [])
                    if all_posts and len(all_posts) > 0:
                        content = str(all_posts[0]).strip()
                        if content:
                            return content
        except Exception as e:
            self._log(f"  ⚠️ 读取数据集失败，使用默认模板: {e}")
        
        templates = [
            "大家好，很高兴加入这个社区！期待和大家交流。",
            "刚注册完账号，有没有大佬能介绍一下这里的规则？",
            "第一次发帖有点紧张，请多多关照！",
            "听说这里很有趣，来看看~",
            "新人报到！求关注求互动~",
            "今天天气不错，分享一下心情😊",
            "有人在吗？能聊聊天吗？",
            "刚来不久，希望能认识更多朋友！",
            "这是我的第一条微博，纪念一下📝",
            "大家都在聊什么呢？我也来参与一下~"
        ]
        return templates[index % len(templates)]
    
    async def _mock_simulation(self):
        self._log("🎭 使用Mock演示模式...")
        self.task.stats.users_created = self.task.config.num_agents
        
        for round_idx in range(self.task.config.num_rounds):
            if self._stop_flag:
                break
            
            self._log(f"")
            self._log(f"📍 Mock Round {round_idx + 1}/{self.task.config.num_rounds}")
            
            self.task.progress.update(
                round_idx + 1,
                self.task.config.num_rounds,
                f"Mock执行第{round_idx + 1}轮"
            )
            
            self.task.stats.posts_created += 5
            self.task.stats.comments_created += 10
            await asyncio.sleep(2)
        
        self._log("✅ Mock模拟执行完成")
