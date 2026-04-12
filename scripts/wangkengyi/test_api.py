"""测试API是否返回数据"""
import requests
import json

print("测试连接后端API...")

try:
    # 测试health端点
    r = requests.get("http://localhost:8000/health", timeout=5)
    print(f"\n1. Health Check: {r.status_code}")
    print(json.dumps(r.json(), indent=2, ensure_ascii=False))
    
    # 测试overview端点
    r = requests.get("http://localhost:8000/api/analytics/overview", timeout=5)
    print(f"\n2. Overview Stats: {r.status_code}")
    data = r.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    if data.get('total_users', 0) > 0:
        print("\n✅ 成功！后端返回了数据！")
        print(f"   用户数: {data['total_users']}")
        print(f"   帖子数: {data['total_posts']}")
        print(f"   评论数: {data['total_comments']}")
    else:
        print("\n❌ 后端返回数据全为0")
        if 'error' in data:
            print(f"   错误: {data['error']}")
        print("\n请按照以下步骤操作:")
        print("1. 停止后端服务 (Ctrl+C)")
        print("2. 重新运行: python start.py")
        print("3. 查看终端输出是否显示: Using database: ...weibo_sim_demo.db")
        
except requests.exceptions.ConnectionError:
    print("\n❌ 无法连接到后端服务！")
    print("   请确保后端服务正在运行: python start.py")
except Exception as e:
    print(f"\n❌ 错误: {e}")
