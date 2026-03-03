# ❌ 问题诊断报告

## 发现的问题

### 1. 前端缺少Qwen选项 ✅ 已修复
**问题**：下拉菜单只有 vLLM/OpenAI/DeepSeek，没有Qwen
**修复**：添加了 `<el-option label="Qwen/通义千问" value="qwen" />`

### 2. 后端未启动 ❌ 需要手动启动
**问题**：测试显示后端完全没运行
**证据**：`requests.get('http://localhost:8001/api/simulation/list')` 连接失败

### 3. API Base路径错误 ✅ 已修复  
**问题**：前端使用相对路径 `/api/simulation`，可能导致请求发到错误端口
**修复**：改为绝对路径 `http://localhost:8001/api/simulation`

---

## 🔧 立即修复步骤

### 步骤1：启动后端

```powershell
# 打开新的PowerShell终端
cd E:\Project\oasis_simulation\visualization_system\backend

# 设置API Key（根据您使用的provider）
$env:QWEN_API_KEY="sk-your-qwen-key"

# 启动后端
python start.py
```

**期望输出**：
```
INFO:     Uvicorn running on http://0.0.0.0:8001 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### 步骤2：重新加载前端

```powershell
# 在另一个终端
cd E:\Project\oasis_simulation\visualization_system\frontend  

# 如果已经在运行，按 Ctrl+C 停止
# 然后重新启动
npm run dev
```

### 步骤3：验证连接

打开浏览器开发者工具（F12），进入模拟控制台页面，查看Network标签：
- 应该能看到对 `http://localhost:8001/api/simulation/list` 的请求
- 状态码应该是200

---

## 📝 Qwen配置示例

现在前端已经有Qwen选项了，配置如下：

| 字段 | 值 |
|------|-----|
| **LLM提供商** | `Qwen/通义千问` |
| **LLM端点** | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| **模型名称** | `qwen-plus` 或 `qwen-turbo` |
| **启用LLM** | ✅ |

---

## 🔍 如何验证修复成功

### 1. 后端连接测试

```powershell
# 在PowerShell中测试
Invoke-RestMethod -Uri "http://localhost:8001/api/simulation/list"
```

**成功输出**：
```json
{
  "tasks": [],
  "total": 0
}
```

### 2. 前端测试

1. 打开 http://localhost:5173
2. 进入"模拟控制台"
3. 检查LLM提供商下拉菜单是否有**4个选项**：
   - vLLM
   - OpenAI
   - DeepSeek
   - Qwen/通义千问 ⭐ 新增

4. 选择Qwen，填写配置
5. 点击"启动模拟"

### 3. 查看日志

启动后应该在日志标签看到：
```
🔧 构建LLM模型: qwen
✅ 使用QWEN 兼容API
   端点: https://dashscope.aliyuncs.com/compatible-mode/v1
```

### 4. 检查数据库文件

模拟运行后，检查目录：
```powershell
ls E:\Project\oasis_simulation\weibo_test\
```

应该看到新生成的 `.db` 文件，例如：
```
sim_20260203_110530.db
```

---

## 🚨 如果还是不行

### 检查清单

- [ ] 后端是否真的在运行？（看到Uvicorn日志）
- [ ] 端口8001是否被占用？
- [ ] 环境变量是否已设置？（`echo $env:QWEN_API_KEY`）
- [ ] 浏览器开发者工具有无错误？
- [ ] 前端是否已重新加载？（Ctrl+F5强制刷新）

### 端口冲突排查

```powershell
# 检查8001端口
netstat -ano | findstr :8001
```

如果端口被占用，修改后端端口：
```powershell
# backend/start.py 中修改
uvicorn main:app --host 0.0.0.0 --port 9001
```

然后前端也要改成 `http://localhost:9001/api/simulation`

---

## ✅ 修复总结

1. ✅ 添加了Qwen下拉选项
2. ✅ 修复了API请求路径
3. ❌ 后端需要**您手动启动**
4. ✅ 后端代码已支持Qwen

**现在请启动后端，然后再试一次！**
