# 数据库表名修复 - 补充说明

## 发现的新问题

在测试过程中发现，模拟完成后统计数据时出现错误：

```
⚠️ 读取统计数据失败: no such table: posts
```

## 根本原因

SQL 查询使用了**复数形式**的表名：
- `posts` (错误)
- `comments` (错误)

但 Oasis 数据库使用的是**单数形式**：
- `post` (正确)
- `comment` (正确)

## 修复内容

**文件**: [executor.py](file:///E:/Project/oasis_simulation/visualization_system/backend/simulation/executor.py#L272-L277)

**修改前**:
```python
cursor.execute("SELECT COUNT(*) FROM posts")    # ❌ 错误
cursor.execute("SELECT COUNT(*) FROM comments") # ❌ 错误
```

**修改后**:
```python
cursor.execute("SELECT COUNT(*) FROM post")    # ✅ 正确
cursor.execute("SELECT COUNT(*) FROM comment") # ✅ 正确
```

## Oasis 数据库表结构

根据 schema 文件，Oasis 使用以下表（单数形式）：

| 表名 | 用途 |
|------|------|
| `user` | 用户信息 |
| `post` | 帖子 |
| `comment` | 评论 |
| `like` | 点赞 |
| `dislike` | 踩 |
| `follow` | 关注关系 |
| `mute` | 屏蔽 |
| `trace` | 操作追踪 |

## 验证方法

运行以下命令检查数据库表：

```bash
cd E:\Project\oasis_simulation\visualization_system
python check_db_tables.py "E:\Project\oasis_simulation\weibo_test\sim_20260204_182118.db"
```

应该看到表列表包含：`user`, `post`, `comment` 等。

## 测试确认

修复后，再次运行模拟，后端日志应显示：

```
[18:30:45] 📊 统计数据库中的真实数据...
[18:30:45] ✅ 成功读取统计数据
[18:30:45] ✅ 模拟成功完成！
[18:30:45] 📊 统计: 5个用户, 3个帖子, 0条评论  ← 正确的数据！
```

**不再出现** "no such table" 错误。
