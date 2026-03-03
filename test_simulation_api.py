"""
测试模拟API
"""
import requests
import json
import time

BASE_URL = "http://localhost:8001/api/simulation"

def test_start_simulation():
    """测试启动模拟"""
    print("=" * 60)
    print("测试1: 启动模拟")
    print("=" * 60)
    
    payload = {
        "config": {
            "num_agents": 5,
            "num_rounds": 3,
            "llm_provider": "vllm",
            "enable_llm": False,  # 先用mock模式测试
            "output_db_name": "test_sim.db"
        }
    }
    
    try:
        response = requests.post(f"{BASE_URL}/start", json=payload)
        result = response.json()
        print(f"✅ 响应: {json.dumps(result, indent=2, ensure_ascii=False)}")
        return result.get("task_id")
    except Exception as e:
        print(f"❌ 错误: {e}")
        return None

def test_get_status(task_id):
    """测试获取状态"""
    print("\n" + "=" * 60)
    print(f"测试2: 获取任务状态 (ID: {task_id})")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/{task_id}/status")
        result = response.json()
        print(f"✅ 状态: {result['status']}")
        print(f"   进度: {result['progress']['percentage']}%")
        print(f"   当前动作: {result['progress']['current_action']}")
        return result
    except Exception as e:
        print(f"❌ 错误: {e}")
        return None

def test_get_logs(task_id):
    """测试获取日志"""
    print("\n" + "=" * 60)
    print(f"测试3: 获取日志 (ID: {task_id})")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/{task_id}/logs?max_lines=20")
        result = response.json()
        print(f"✅ 最近{len(result['logs'])}条日志:")  
        for log in result['logs'][-10:]:
            print(f"   {log}")
    except Exception as e:
        print(f"❌ 错误: {e}")

def test_list_tasks():
    """测试获取任务列表"""
    print("\n" + "=" * 60)
    print("测试4: 获取所有任务")
    print("=" * 60)
    
    try:
        response = requests.get(f"{BASE_URL}/list")
        result = response.json()
        print(f"✅ 共有 {result['total']} 个任务:")
        for task in result['tasks']:
            print(f"   - {task['id']}: {task['status']} ({task['progress']['percentage']}%)")
    except Exception as e:
        print(f"❌ 错误: {e}")

def main():
    print("\n🧪 模拟API测试脚本\n")
    
    # 测试启动
    task_id = test_start_simulation()
    
    if not task_id:
        print("\n❌ 无法启动模拟，测试终止")
        return
    
    # 等待并监控进度
    print("\n⏳ 监控进度...")
    for i in range(10):
        time.sleep(2)
        status = test_get_status(task_id)
        
        if status and status['status'] in ['completed', 'failed', 'stopped']:
            print(f"\n{'✅' if status['status'] == 'completed' else '❌'} 任务{status['status']}")
            break
    
    # 获取日志
    test_get_logs(task_id)
    
    # 列出所有任务
    test_list_tasks()
    
    print("\n" + "=" * 60)
    print("✅ 测试完成！")
    print("=" * 60)

if __name__ == "__main__":
    main()
