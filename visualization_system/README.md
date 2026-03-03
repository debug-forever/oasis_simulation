# 微博仿真可视化系统

基于 Oasis 框架的社交媒体仿真数据可视化系统，提供美观、交互式的数据展示和分析功能。

## 系统特性

### ✨ 核心功能

- **📊 仪表板**：总体统计数据一览、活动时间线图表、热门帖子排行
- **👥 用户浏览**：用户列表、用户画像、发帖历史、互动关系
- **📝 帖子浏览**：帖子时间线、详情查看、评论树展示
- **🌐 传播可视化**：交互式转发传播树、时间轴动画
- **🔗 互动网络**：用户关系网络图、互动热力分析
- **📈 数据分析**：影响力排行、活跃度统计、趋势分析

### 🎨 设计特色

- ⚡ **现代化UI**：暗色主题、渐变色彩、流畅动画
- 📱 **响应式设计**：适配各种屏幕尺寸
- 🚀 **高性能**：前后端分离、异步加载、图表按需渲染
- 🎯 **用户友好**：直观的交互、清晰的信息层次

## 技术栈

### 后端
- **FastAPI**：高性能异步Web框架
- **SQLite**：数据库（复用Oasis仿真数据）
- **Pydantic**：数据验证和序列化

### 前端
- **Vue 3**：渐进式JavaScript框架
- **Vite**：下一代前端构建工具
- **Element Plus**：Vue 3 UI组件库
- **ECharts**：强大的图表可视化库
- **Pinia**：Vue 3状态管理
- **Vue Router**：官方路由管理器

## 快速开始

### 前置要求

- Python 3.8+
- Node.js 16+
- Weibo仿真数据库文件（由Oasis生成）

### 1. 后端启动

```powershell
# 进入后端目录
cd visualization_system/backend

# 安装Python依赖
pip install -r requirements.txt

# 设置数据库路径（可选，如果数据库不在默认位置）
$env:OASIS_DB_PATH="E:\Project\oasis_simulation\weibo_test\weibo_sim_openai.db"

# 启动后端服务
python main.py
```

后端启动后访问 http://localhost:8000/docs 查看API文档

### 2. 前端启动

```powershell
# 进入前端目录（新开一个终端）
cd visualization_system/frontend

# 安装依赖（首次运行）
npm install

# 启动开发服务器
npm run dev
```

前端启动后访问 http://localhost:5173

## 项目结构

```
visualization_system/
├──  backend/                 # 后端FastAPI应用
│   ├── api/                 # API路由模块
│   │   ├── users.py         # 用户相关API
│   │   ├── posts.py         # 帖子相关API
│   │   └── analytics.py     # 数据分析API
│   ├── database/            # 数据库管理
│   │   └── db_manager.py    # SQLite连接管理器
│   ├── models/              # 数据模型
│   │   └── schemas.py       # Pydantic模型定义
│   ├── utils/               # 工具函数
│   │   └── data_aggregation.py  # 数据聚合工具
│   ├── main.py              # FastAPI应用入口
│   └── requirements.txt     # Python依赖
│
└── frontend/                # 前端Vue应用
    ├── src/
    │   ├── api/             # API请求封装
    │   │   └── index.js
    │   ├── views/           # 页面视图组件
    │   │   ├── Dashboard.vue      # 仪表板
    │   │   ├── Users.vue          # 用户浏览
    │   │   ├── Posts.vue          # 帖子浏览
    │   │ ├── Propagation.vue     # 传播可视化
    │   │   ├── Network.vue        # 互动网络
    │   │   └── Analytics.vue      # 数据分析
    │   ├── router/          # 路由配置
    │   │   └── index.js
    │   ├── stores/          # 状态管理
    │   │   └── data.js
    │   ├── App.vue          # 根组件
    │   ├── main.js          # 应用入口
    │   └── style.css        # 全局样式
    ├── package.json
    └── vite.config.js       # Vite配置
```

## API端点

### 用户相关
- `GET /api/users` - 获取用户列表
- `GET /api/users/{user_id}` - 获取用户详情
- `GET /api/users/{user_id}/posts` - 获取用户帖子
- `GET /api/users/{user_id}/interactions` - 获取用户互动

### 帖子相关
- `GET /api/posts` - 获取帖子列表
- `GET /api/posts/{post_id}` - 获取帖子详情
- `GET /api/posts/{post_id}/comments` - 获取帖子评论
- `GET /api/posts/{post_id}/propagation` - 获取传播树
- `GET /api/posts/trending/list` - 获取热门帖子

### 数据分析
- `GET /api/analytics/overview` - 总体统计
- `GET /api/analytics/timeline` - 时间线数据
- `GET /api/analytics/network` - 用户网络
- `GET /api/analytics/influence` - 影响力排行
- `GET /api/analytics/activity` - 活跃度分析

## 数据库配置

系统会自动在以下位置查找数据库文件：
1. 环境变量 `OASIS_DB_PATH`
2. `weibo_test/weibo_sim_openai.db`
3. `weibo_test/weibo_sim_vllm.db`

如果数据库在其他位置，请设置环境变量：
```powershell
$env:OASIS_DB_PATH="你的数据库路径.db"
```

## 开发说明

### 添加新的API端点

1. 在 `backend/api/` 下创建新的路由文件
2. 在 `backend/main.py` 中注册路由
3. 在 `frontend/src/api/index.js` 中添加前端API调用

### 添加新的视图页面

1. 在 `frontend/src/views/` 下创建Vue组件
2. 在 `frontend/src/router/index.js` 中添加路由
3. 在 `App.vue` 的侧边栏菜单中添加入口

### 自定义主题

修改 `frontend/src/style.css` 中的CSS变量：
```css
:root {
  --primary-color: #667eea;  /* 主色调 */
  --bg-color: #0f0f23;       /* 背景色 */
  /* ... 更多变量 */
}
```

## 生产部署

### 后端部署

```bash
# 使用gunicorn进行生产部署
pip install gunicorn
gunicorn main:app -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

### 前端部署

```bash
# 构建生产版本
npm run build

# dist目录内容部署到Web服务器（Nginx/Apache）
```

## 故障排查

### 后端无法启动
- 检查数据库路径是否正确
- 确认Python依赖已安装
- 查看 `OASIS_DB_PATH` 环境变量

### 前端无法连接后端
- 确认后端在 http://localhost:8000 运行
- 检查 `vite.config.js` 中的代理配置
- 查看浏览器控制台的网络请求

### 图表不显示
- 确认数据已成功加载
- 检查浏览器控制台是否有JavaScript错误
- 确认ECharts库已正确安装

## 贡献

欢迎提交Issue和Pull Request！

## 许可证

本项目基于 Apache License 2.0 开源。

## 致谢

- [Oasis](https://github.com/camel-ai/oasis) - 多智能体社交媒体仿真框架
- [FastAPI](https://fastapi.tiangolo.com/) - 现代化Python Web框架
- [Vue.js](https://vuejs.org/) - 渐进式JavaScript框架
- [ECharts](https://echarts.apache.org/) - 数据可视化图表库
- [Element Plus](https://element-plus.org/) - Vue 3 UI组件库
