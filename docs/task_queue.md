# 伏羲 v1.44 任务队列使用指南

## 概述

伏羲 v1.44 引入了基于 Redis Stream 的异步任务队列，用于处理文件上传和评测任务，避免阻塞 API 响应。

## 架构

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  文件上传   │    │  评测任务   │    │  其他任务   │
│  API        │    │  API        │    │  API        │
└──────┬──────┘    └──────┬──────┘    └──────┬──────┘
       │                  │                  │
       └──────────────────┼──────────────────┘
                          │
                          ▼
                ┌─────────────────┐
                │  Redis Stream   │
                │  任务队列       │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │  任务消费者     │
                │  (Worker)       │
                └────────┬────────┘
                         │
                         ▼
                ┌─────────────────┐
                │  任务处理器     │
                │  - 文件处理     │
                │  - 评测执行     │
                │  - 知识库更新   │
                └─────────────────┘
```

## 功能特性

1. **异步处理**：文件上传和评测任务立即返回，后台处理
2. **任务状态追踪**：支持 pending/processing/completed/failed 状态
3. **消费者组**：支持多个 Worker 并行处理任务
4. **故障恢复**：支持任务重试和死信队列
5. **监控接口**：提供任务状态查询 API

## 配置

### 环境变量

在 `.env` 文件中添加以下配置：

```bash
# Redis 任务队列配置
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_STREAM_NAME=fuxi:tasks
REDIS_GROUP_NAME=fuxi:workers
```

### 依赖

确保安装了 Redis 和 Python redis 库：

```bash
# 安装 Redis（如果尚未安装）
# Windows: 使用 Chocolatey 或下载 Windows 版本
# Linux: sudo apt-get install redis-server

# Python 依赖已包含在 requirements.txt 中
pip install redis>=5.0.0
```

## API 接口

### 1. 文件上传（异步）

**POST /api/upload**

上传文件后立即返回任务 ID，文件在后台处理。

**请求：**
```bash
curl -X POST "http://localhost:8080/api/upload" \
  -F "file=@/path/to/file.pdf"
```

**响应：**
```json
{
  "status": "ok",
  "file_name": "file.pdf",
  "task_id": "task:20260709214100123456",
  "message": "文件已接收，正在后台处理"
}
```

### 2. 查询任务状态

**GET /api/tasks/{task_id}**

查询任务的处理状态。

**请求：**
```bash
curl "http://localhost:8080/api/tasks/task:20260709214100123456"
```

**响应：**
```json
{
  "task_id": "task:20260709214100123456",
  "task_type": "file_process",
  "status": "completed",
  "created_at": "2026-07-09T21:41:00.123456",
  "updated_at": "2026-07-09T21:41:05.654321",
  "result": {
    "file_name": "file.pdf",
    "chunks": 15,
    "duration_ms": 5231,
    "status": "completed"
  },
  "error": null
}
```

### 3. 创建评测任务（异步）

**POST /api/evaluation**

提交评测任务到队列，立即返回任务 ID。

**请求：**
```bash
curl -X POST "http://localhost:8080/api/evaluation" \
  -H "Content-Type: application/json" \
  -d '{}'
```

**响应：**
```json
{
  "ok": true,
  "task_id": "task:20260709214200123456",
  "status": "processing",
  "message": "评测任务已提交，正在后台执行"
}
```

## 任务状态

| 状态 | 说明 |
|------|------|
| `pending` | 任务已创建，等待处理 |
| `processing` | 任务正在处理中 |
| `completed` | 任务处理完成 |
| `failed` | 任务处理失败 |

## 监控和调试

### 查看 Redis Stream 信息

```bash
# 查看 Stream 信息
redis-cli XINFO STREAM fuxi:tasks

# 查看消费者组信息
redis-cli XINFO GROUPS fuxi:tasks

# 查看待处理消息
redis-cli XPENDING fuxi:tasks fuxi:workers

# 查看具体消息
redis-cli XRANGE fuxi:tasks - +
```

### 查看任务状态

```bash
# 查看所有任务状态
redis-cli KEYS "task:status:*"

# 查看特定任务状态
redis-cli HGETALL "task:status:task:20260709214100123456"
```

## 故障排除

### 1. Redis 连接失败

**症状**：启动时日志显示 "Redis 连接失败"

**解决方案**：
1. 检查 Redis 服务是否运行：`redis-cli ping`
2. 检查配置是否正确：`REDIS_HOST`、`REDIS_PORT`、`REDIS_PASSWORD`
3. 检查防火墙设置

### 2. 任务卡在 pending 状态

**症状**：任务状态一直是 pending

**解决方案**：
1. 检查任务消费者是否运行：查看启动日志
2. 检查 Redis Stream 中是否有消息：`redis-cli XLEN fuxi:tasks`
3. 检查消费者组状态：`redis-cli XINFO GROUPS fuxi:tasks`

### 3. 任务处理失败

**症状**：任务状态为 failed

**解决方案**：
1. 查看任务错误信息：`GET /api/tasks/{task_id}`
2. 查看服务器日志中的错误详情
3. 检查相关服务是否正常（如 Embedder 服务）

## 开发指南

### 添加新的任务类型

1. 在 `src/infra/task_queue.py` 中添加任务类型常量：
```python
TASK_NEW_TYPE = "new_type"
```

2. 在 `src/infra/task_handlers.py` 中添加处理器函数：
```python
async def handle_new_type(payload: Dict[str, Any]) -> Dict[str, Any]:
    # 处理逻辑
    return {"status": "completed"}
```

3. 在 `src/server.py` 的 startup 函数中注册处理器：
```python
task_queue.register_handler(TASK_NEW_TYPE, handle_new_type)
```

### 测试任务队列

运行测试脚本：
```bash
python test_task_queue.py
```

运行验证脚本：
```bash
python verify_async_upload.py
```

## 性能优化

### 1. 消费者并发

可以通过启动多个消费者实例来提高处理能力。每个消费者实例会自动加入同一个消费者组。

### 2. 消息批处理

任务队列支持批量读取消息，通过 `count` 参数控制每批读取的数量。

### 3. 消息确认

使用 `XACK` 命令确认消息已处理，避免重复处理。

## 安全考虑

1. **Redis 访问控制**：生产环境应设置 Redis 密码
2. **网络隔离**：Redis 服务应仅在内网可访问
3. **任务验证**：处理器应验证任务参数的合法性
4. **日志记录**：所有任务操作应记录日志，便于审计

## 扩展性

### 分布式部署

任务队列支持分布式部署：
- 多个 API 服务器可以发布任务到同一个 Redis Stream
- 多个 Worker 服务器可以消费同一个消费者组
- 通过增加 Worker 数量来水平扩展处理能力

### 监控集成

可以集成 Prometheus 监控：
- 任务发布速率
- 任务处理延迟
- 任务成功率
- 消费者积压数量

## 版本历史

- **v1.44**：引入 Redis Stream 任务队列
  - 文件上传异步处理
  - 评测任务异步处理
  - 任务状态追踪
  - 消费者组支持