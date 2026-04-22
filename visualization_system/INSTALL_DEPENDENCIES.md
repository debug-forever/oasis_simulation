# 🚨 依赖问题解决方案

## 问题根源

您的项目是缺少依赖的**Poetry项目**，需要安装：
- `camel-ai` (核心依赖)
- 其他依赖包

## ✅ 立即解决

### 方案1：直接安装camel-ai（推荐）

```powershell
pip install camel-ai
```

等待安装完成（可能需要几分钟）。

### 方案2：安装Poetry并使用它

```powershell
# 安装poetry
pip install poetry

# 在项目目录安装所有依赖
cd E:\Project\oasis_simulation
poetry install
```

### 方案3：使用conda  

```powershell
conda install -c conda-forge camel-ai
```

---

## 验证安装

```powershell
python -c "import camel; print('✅ CAMEL已安装'); import oasis; print('✅ OASIS可用')"
```

成功后应该看到两个✅。

---

## 安装后重启后端

```powershell
# 设置API key
$env:QWEN_API_KEY="your-key"

# 重启后端
cd E:\Project\oasis_simulation\visualization_system\backend
python start.py
```

现在启动模拟应该显示：
```
📦 导入Oasis模块...
🔧 构建LLM模型: qwen
✅ 使用QWEN 兼容API
```

**不再是Mock！**

---

## 需要安装的主要包

根据pyproject.toml，需要：
- camel-ai (v0.2.70)
- pandas
- igraph
- sentence-transformers
- 等等...

直接`pip install camel-ai`会自动安装大部分依赖。

---

正在为您安装 camel-ai...
