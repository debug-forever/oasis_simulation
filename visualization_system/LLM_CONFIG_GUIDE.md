# 模拟功能 - LLM配置指南

## 🎯 快速测试（无需LLM）

**现在就可以使用！**

1. 启动后端和前端
2. 打开模拟控制台
3. **关闭"启用LLM"开关**
4. 点击"启动模拟"

系统会使用**Mock演示模式**，模拟执行过程并生成示例数据。

---

## 🔧 真实LLM配置

如果您想使用真实的LLM进行模拟，需要配置以下内容：

### 方案1：OpenAI API（推荐，最简单）

#### 1. 获取API Key
- 访问 https://platform.openai.com/api-keys
  - 创建新的API key

#### 2. 设置环境变量

**Windows PowerShell**：
```powershell
$env:OPENAI_API_KEY="sk-your-api-key-here"
```

**永久设置**（推荐）：
```powershell
[System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY', 'sk-your-api-key-here', 'User')
```

#### 3. 前端配置

在模拟控制台中设置：
- **LLM提供商**: 选择 `openai`
- **LLM端点**: 保持默认（OpenAI官方）或使用兼容端点
- **模型名称**: `gpt-3.5-turbo` 或 `gpt-4`
- **启用LLM**: 打开开关 ✅

#### 4. 启动模拟

点击"启动模拟"即可使用真实的OpenAI模型！

---

### 方案2：DeepSeek API

#### 1. 获取API Key
- 访问 https://platform.deepseek.com/
- 创建API key

#### 2. 设置环境变量

```powershell
$env:DEEPSEEK_API_KEY="your-deepseek-api-key"
```

#### 3. 前端配置

- **LLM提供商**: `deepseek`
- **LLM端点**: `https://api.deepseek.com/v1`
- **模型名称**: `deepseek-chat`
- **启用LLM**: ✅

---

### 方案3：本地vLLM服务器

#### 1. 安装vLLM

```bash
pip install vllm
```

#### 2. 下载模型

例如Qwen模型：
```bash
# 使用huggingface-cli下载
huggingface-cli download Qwen/Qwen2.5-7B-Instruct
```

#### 3. 启动vLLM服务器

```bash
python -m vllm.entrypoints.openai.api_server \
    --model Qwen/Qwen2.5-7B-Instruct \
    --host 0.0.0.0 \
    --port 8000
```

#### 4. 前端配置

- **LLM提供商**: `vllm`
- **LLM端点**: `http://127.0.0.1:8000/v1`
- **模型名称**: `qwen-2`（或您的模型名称）
- **启用LLM**: ✅

---

## 📝 修改Executor支持真实LLM

当前executor有mock模式，要支持真实LLM需要完善代码。

### 需要修改的文件

**`backend/simulation/executor.py`**

在 `_run_simulation` 方法中（约第100行），需要添加：

```python
# 根据config构建模型管理器
def _build_model_manager(self):
    """根据配置构建模型管理器"""
    from camel.models import ModelFactory
    from camel.types import ModelPlatformType
    
    provider = self.task.config.llm_provider
    
    if provider == "openai":
        import os
        api_key = os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("未设置OPENAI_API_KEY环境变量")
        
        model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,
            model_type="gpt-3.5-turbo",  # 或从config读取
            api_key=api_key
        )
    
    elif provider == "deepseek":
        import os
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise ValueError("未设置DEEPSEEK_API_KEY环境变量")
        
        model = ModelFactory.create(
            model_platform=ModelPlatformType.OPENAI,  # DeepSeek兼容OpenAI API
            model_type="deepseek-chat",
            api_key=api_key,
            url="https://api.deepseek.com/v1"
        )
    
    elif provider == "vllm":
        model = ModelFactory.create(
            model_platform=ModelPlatformType.VLLM,
            model_type=self.task.config.model_name,
            url=self.task.config.llm_endpoint,
        )
    
    else:
        raise ValueError(f"不支持的LLM提供商: {provider}")
    
    from camel.models import ModelManager
    return ModelManager(models=[model])
```

然后在 `_run_simulation` 中调用：

```python
# 构建模型管理器
model_manager = None
if self.task.config.enable_llm:
    self._log(f"🔌 连接LLM: {self.task.config.llm_provider}")
    model_manager = self._build_model_manager()  # ← 调用上面的方法
```

---

## ⚡ 快速开始建议

### 新手推荐流程

**阶段1：测试界面**（现在就可以）
1. 关闭LLM开关
2. 使用Mock模式测试界面
3. 熟悉操作流程

**阶段2：使用真实LLM**
1. 获取OpenAI API key（最简单）
2. 设置环境变量
3. 修改executor.py添加API key支持
4. 打开LLM开关测试

**阶段3：本地部署**
1. 安装vLLM
2. 下载本地模型
3. 启动vLLM服务器
4. 配置使用本地端点

---

## 🔑 API Key安全

**重要提示**：

1. **不要把API key写死在代码里**
2. **使用环境变量**
3. **不要提交到git**

### 推荐做法

创建环境变量文件（不提交到git）：

**`.env`文件**：
```bash
OPENAI_API_KEY=sk-your-key-here
DEEPSEEK_API_KEY=your-deepseek-key
```

在代码中加载：
```python
from dotenv import load_dotenv
load_dotenv()
```

---

## ❓ 常见问题

### Q: 现在点击启动会发生什么？

A: 使用Mock模式，模拟5轮执行，每轮2秒，生成假数据。可以看到完整的UI流程。

### Q: 必须要LLM才能运行吗？

A: 不需要！Mock模式可以用于：
- 测试界面
- 演示系统
- 开发调试

### Q: OpenAI API收费吗？

A: 是的，按使用量计费。建议先用Mock模式测试，确认无误再用真实API。

### Q: 能用其他模型吗？

A: 可以！只要支持OpenAI兼容API的模型都可以，例如：
- 通义千问（Qwen）
- 文心一言（需要兼容层）
- ChatGLM
- 本地Ollama

### Q: 如何知道是否在使用真实LLM？

A: 查看日志：
- Mock模式：`🎭 使用模拟模式...`
- 真实模式：`🔌 连接LLM: openai` + 实际LLM响应日志

---

## 📊 总结

| 模式 | 需要配置 | 适用场景 |
|------|---------|----------|
| **Mock演示** | 无 | 测试界面、演示、开发 |
| **OpenAI** | API key | 快速使用真实LLM |
| **DeepSeek** | API key | 国内访问更快 |
| **本地vLLM** | 安装+模型 | 私有部署、大规模使用 |

**推荐顺序**：Mock测试 → OpenAI验证 → vLLM部署

现在您可以直接使用Mock模式测试系统！
