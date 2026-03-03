"""
测试前端是否能连接到后端API
"""
import requests

print("=" * 60)
print("测试后端API连接")
print("=" * 60)

try:
    # 测试后端API
    r = requests.get('http://localhost:8000/api/analytics/overview')
    data = r.json()
    print(f"\n✅ 后端API正常")
    print(f"   用户数: {data.get('total_users')}")
    print(f"   帖子数: {data.get('total_posts')}")
    print(f"   评论数: {data.get('total_comments')}")
    print(f"   点赞数: {data.get('total_likes')}")
    
except Exception as e:
    print(f"\n❌ 后端API错误: {e}")

print("\n" + "=" * 60)
print("检查前端是否在运行")
print("=" * 60)

try:
    # 测试前端是否运行
    r = requests.get('http://localhost:5173/', timeout=2)
    print(f"\n✅ 前端正在运行 (状态码: {r.status_code})")
    
except requests.exceptions.ConnectionError:
    print("\n❌ 前端未运行！")
    print("   请在另一个终端运行:")
    print("   cd visualization_system\\frontend")
    print("   npm run dev")
    
except Exception as e:
    print(f"\n⚠️  前端检查错误: {e}")

print("\n" + "=" * 60)
