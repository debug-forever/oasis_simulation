# 完整依赖安装脚本

## 一次性解决所有依赖

```powershell
# 1. 安装PyTorch（必需）
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118

# 2. 安装所有其他依赖
pip install pandas igraph sentence-transformers pillow unstructured neo4j requests-oauthlib slack-sdk

# 3. 验证
python -c "import torch; import oasis; import camel; print('✅ 所有依赖已安装')"
```

## 安装后重启后端

```powershell
$env:QWEN_API_KEY="your-key"
cd E:\Project\oasis_simulation\visualization_system\backend
python start.py
```

正在安装中...
