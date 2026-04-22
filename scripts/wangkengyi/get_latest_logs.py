"""获取模拟任务的最新日志"""
import sys
sys.path.insert(0, 'visualization_system/backend')

from simulation.manager import SimulationManager

manager = SimulationManager()
tasks = manager.get_all_tasks()

if not tasks:
    print("没有任务")
else:
    # 找最新任务
    latest_task = max(tasks, key=lambda t: t.created_at)
    print(f"任务ID: {latest_task.task_id}")
    print(f"状态: {latest_task.status.value}")
    print(f"配置: enable_seed_posts={latest_task.config.enable_seed_posts}, num_seed_posts={latest_task.config.num_seed_posts}")
    print(f"\n{'='*60}")
    print("日志内容:")
    print('='*60)
    for log in latest_task.logs[-50:]:  # 最后50行
        print(log)
