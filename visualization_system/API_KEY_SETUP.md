# 🔑 API Key 设置指南

## ✅ 快速设置（3步完成）

### 步骤1：在PowerShell中设置API Key

**如果您有OpenAI API Key**：
```powershell
$env:OPENAI_API_KEY="sk-your-actual-api-key-here"
```

**如果您有DeepSeek API Key**：
```powershell
$env:DEEPSEEK_API_KEY="your-deepseek-api-key-here" 
```

**重要**：把上面的引号里的内容替换成您的真实API key！

### 步骤2：重启后端服务

```powershell
# 停止现有后端（Ctrl+C）
# 然后重新启动
cd E:\Project\oasis_simulation\visualization_system\backend
python start.py
```

**为什么要重启？** 环境变量只有在进程启动时才会被读取。

### 步骤3：在前端配置

打开模拟控制台，设置：

**如果用OpenAI**：
- LLM提供商：`openai`
- LLM端点：保持默认（或填 `https://api.openai.com/v1`）
- 模型名称：`gpt-3.5-turbo`（或 `gpt-4`）
- **启用LLM**：✅ 打开开关

**如果用DeepSeek**：
- LLM提供商：`deepseek`
- LLM端点：`https://api.deepseek.com/v1`
- 模型名称：`deepseek-chat`
- **启用LLM**：✅ 打开开关

然后点击"🚀 启动模拟"！

---

## 📍 详细说明

### API Key在哪里设置？

**只有一个地方**：在PowerShell终端中设置环境变量

```powershell
# 临时设置（关闭终端后失效）
$env:OPENAI_API_KEY="sk-xxxxx"

# 永久设置（推荐）
[System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY', 'sk-xxxxx', 'User')
```

### 前端界面设置什么？

前端界面**不需要输入API Key**（出于安全考虑）。

前端只需要选择：
1. **LLM提供商**：告诉系统用哪个服务（openai/deepseek/vllm）
2. **LLM端点**：API的URL地址
3. **模型名称**：要使用的具体模型
4. **启用LLM开关**：是否使用真实LLM（关闭=Mock模式）

### 如何验证API Key是否生效？

启动模拟后，查看日志：

**成功**：
```
✅ 使用OpenAI API (模型: gpt-3.5-turbo)
🤖 生成Agent图...
```

**失败**：
```
❌ 未设置OPENAI_API_KEY环境变量！
请在PowerShell中运行: $env:OPENAI_API_KEY="sk-your-key"
```

---

## 🔐 安全提示

1. **不要**把API key写在代码里
2. **不要**提交API key到git
3. **只在**环境变量中设置
4. **永久设置时**使用User级别（不要System级别）

---

## ❓ 常见问题

### Q: 我设置了环境变量但还是提示未设置？

A: 需要**重启后端服务**！环境变量只在进程启动时读取。

### Q: 怎么知道我的API key是什么？

A: 
- **OpenAI**: 登录 https://platform.openai.com/api-keys 查看
- **DeepSeek**: 登录 https://platform.deepseek.com 查看

### Q: 可以在前端界面输入API key吗？

A: 出于安全考虑，不建议。API key应该只存在于服务器端（环境变量）。

### Q: 临时设置和永久设置有什么区别？

A:
- **临时**：`$env:VAR="value"` - 关闭终端后失效
- **永久**：`SetEnvironmentVariable(...)` - 一直有效

---

## ✅ 完整流程示例

假设您有OpenAI API Key：`sk-abc123xyz...`

```powershell
# 1. 设置环境变量（永久）
[System.Environment]::SetEnvironmentVariable('OPENAI_API_KEY', 'sk-abc123xyz', 'User')

# 2. 重启PowerShell（重要！让环境变量生效）

# 3. 启动后端
cd E:\Project\oasis_simulation\visualization_system\backend
python start.py

# （在另一个终端）启动前端
cd E:\Project\oasis_simulation\visualization_system\frontend
npm run dev
```

然后在浏览器中：
1. 打开 http://localhost:5173
2. 进入模拟控制台
3. 选择 OpenAI，模型 gpt-3.5-turbo
4. **打开**"启用LLM"开关
5. 点击"启动模拟"

完成！您将看到真实的OpenAI API调用！
