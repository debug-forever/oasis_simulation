"""
后端服务启动脚本 - 禁用自动重载以保持环境变量
"""
import sys
import os

# 添加backend目录到Python路径
backend_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, backend_dir)

if __name__ == "__main__":
    import uvicorn
    # 使用8001端口避免冲突
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=False)
