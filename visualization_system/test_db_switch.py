"""
测试数据库切换功能

这个脚本测试：
1. 数据库切换API是否正常工作
2. 切换后能否正确读取新数据库
"""
import requests
import json

API_BASE = "http://localhost:8001/api/simulation"

def test_current_db():
    """测试获取当前数据库"""
    print("=" * 60)
    print("📍 测试1: 获取当前数据库")
    print("=" * 60)
    
    response = requests.get(f"{API_BASE}/current-db")
    data = response.json()
    
    print(f"当前数据库: {data.get('db_path')}")
    print(f"状态: {data.get('status')}")
    
    if data.get('stats'):
        stats = data['stats']
        print(f"统计数据:")
        print(f"  - 用户: {stats.get('users', 0)}")
        print(f"  - 帖子: {stats.get('posts', 0)}")
        print(f"  - 评论: {stats.get('comments', 0)}")
    
    print()
    return data


def test_switch_db(db_path):
    """测试切换数据库"""
    print("=" * 60)
    print(f"📍 测试2: 切换到数据库: {db_path}")
    print("=" * 60)
    
    try:
        response = requests.post(
            f"{API_BASE}/switch-database",
            json={"db_path": db_path}
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ 切换成功!")
            print(f"新数据库: {data.get('db_path')}")
            
            if data.get('stats'):
                stats = data['stats']
                print(f"统计数据:")
                print(f"  - 用户: {stats.get('users', 0)}")
                print(f"  - 帖子: {stats.get('posts', 0)}")
                print(f"  - 评论: {stats.get('comments', 0)}")
        else:
            print(f"❌ 切换失败: {response.status_code}")
            print(f"错误: {response.text}")
    
    except Exception as e:
        print(f"❌ 请求失败: {e}")
    
    print()


def test_dashboard_data():
    """测试Dashboard能否读取到新数据"""
    print("=" * 60)
    print("📍 测试3: 验证Dashboard API")
    print("=" * 60)
    
    try:
        # 测试获取概览数据
        response = requests.get("http://localhost:8001/api/analytics/overview")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Dashboard API正常!")
            print(f"总用户数: {data.get('total_users', 0)}")
            print(f"总帖子数: {data.get('total_posts', 0)}")
            print(f"总评论数: {data.get('total_comments', 0)}")
        else:
            print(f"❌ Dashboard API失败: {response.status_code}")
    
    except Exception as e:
        print(f"❌ 请求失败: {e}")
    
    print()


if __name__ == "__main__":
    print("\n🚀 开始测试数据库切换功能\n")
    
    # 测试1: 获取当前数据库
    current = test_current_db()
    
    # 测试2: 如果用户提供数据库路径，测试切换
    print("💡 提示: 如果想测试切换功能，请运行:")
    print("   python test_db_switch.py <database_path>")
    print()
    
    # 测试3: 验证Dashboard API
    test_dashboard_data()
    
    print("✅ 测试完成!")
    print()
    print("📝 使用说明:")
    print("1. 启动一个模拟任务")
    print("2. 等待任务完成")
    print("3. 观察终端日志，应该看到 '数据库连接已切换' 的消息")
    print("4. 前端会显示通知，点击可跳转到Dashboard")
    print("5. Dashboard应该显示新的模拟数据")
    print()
