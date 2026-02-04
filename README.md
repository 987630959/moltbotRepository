# MoltBot - 分布式大模型调用框架

## 核心架构

```
┌─────────────────────────────────────────────────────────────┐
│                      MoltBot Framework                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │   任务队列   │  │  模型管理器  │  │     回调系统        │  │
│  │ Task Queue  │  │Model Manager│  │  Callback System   │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────│  │
│         │                 │                     │          │
│  ┌──────▼──────────────────▼──────────────────▼──────────┐│
│  │              执行引擎 (Execution Engine)              ││
│  │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐     ││
│  │  │ Worker1 │ │ Worker2 │ │ Worker3 │ │ WorkerN │     ││
│  │  └─────────┘ └─────────┘ └─────────┘ └─────────┘     ││
│  └───────────────────────────────────────────────────────┘│
│                          │                                │
│  ┌───────────────────────▼─────────────────────────────┐ │
│  │              分布式协调 (Redis/RabbitMQ)             │ │
│  └───────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

## 特性

- 🚀 **高性能异步执行** - 基于 asyncio 的并行任务处理
- 🌐 **分布式支持** - Redis 集成，支持多节点部署
- 📊 **智能调度** - 根据模型可用度自动分配任务
- 🔄 **灵活回调** - 支持多种回调机制（Webhooks、WebSocket）
- 🔌 **易于集成** - 简洁的 API 设计

## 安装

### 从源码安装

```bash
git clone https://github.com/987630959/moltbotRepository.git
cd moltbot
pip install -e .
```

### 使用 Poetry

```bash
poetry install
```

## 快速开始

### 1. 基本使用

```python
from moltbot import MoltBot, create_app

app = create_app()

# 注册模型
await app.register_model(
    name="gpt-4",
    provider="openai",
    api_key="your-api-key"
)

# 提交任务
task_id = await app.submit(
    prompt="解释什么是量子计算？",
    model="gpt-4"
)

# 等待结果
result = await app.wait(task_id)
print(result.result)

await app.stop()
```

### 2. 使用回调

```python
app = create_app()

@app.on_complete
async def on_complete(task):
    print(f"任务完成: {task.result}")

await app.submit(prompt="写一首诗")
```

### 3. API 服务器

```bash
moltbot --api --api-port 8000
```

然后通过 REST API 交互：

```bash
# 提交任务
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"prompt": "你好世界", "priority": 5}'

# 获取结果
curl http://localhost:8000/tasks/{task_id}
```

## 高级功能

### 模型选择策略

```python
# 根据可用度选择（默认）
await app.register_model(name="gpt-4", weight=10)

# 根据负载选择（使用次数最少）
app.model_mgr.select_strategy = "load"

# 根据成本选择
app.model_mgr.select_strategy = "cost"
```

### 批量任务处理

```python
tasks = [Task(prompt=f"任务 {i}") for i in range(10)]
task_ids = await app.engine.execute_batch(tasks, concurrency=5)
```

### Webhook 回调

```python
app.webhook(
    event="on_complete",
    url="https://your-server.com/webhook",
    headers={"Authorization": "Bearer token"}
)
```

## 架构设计

### 核心组件

1. **TaskScheduler** - 任务调度器
   - 优先级队列
   - 并发控制
   - 任务状态追踪

2. **ModelManager** - 模型管理器
   - 多模型注册
   - 负载均衡
   - 性能统计

3. **ExecutionEngine** - 执行引擎
   - 异步任务执行
   - 重试机制
   - 错误处理

4. **CallbackManager** - 回调管理器
   - 同步/异步回调
   - Webhook 支持

5. **DistributedManager** - 分布式协调
   - Redis 集成
   - 分布式锁
   - 状态同步

## 配置

### 配置文件 (config.json)

```json
{
  "app_name": "MoltBot",
  "debug": false,
  "log_level": "INFO",
  "max_workers": 10,
  "max_concurrent_tasks": 100,
  "task_timeout": 300,
  "retry_times": 3,
  "redis_host": "localhost",
  "redis_port": 6379,
  "use_redis": false,
  "default_model": "gpt-3.5-turbo",
  "model_selection_strategy": "availability"
}
```

### 环境变量

```bash
export MOLTBOT_CONFIG=/path/to/config.json
export MOLTBOT_REDIS_HOST=localhost
export MOLTBOT_API_KEY=your-api-key
```

## API 参考

### REST API

| 方法 | 端点 | 描述 |
|------|------|------|
| POST | /tasks | 提交任务 |
| GET | /tasks | 列出任务 |
| GET | /tasks/{id} | 获取任务详情 |
| POST | /tasks/{id}/cancel | 取消任务 |
| POST | /tasks/{id}/wait | 等待任务完成 |
| POST | /tasks/batch | 批量提交 |
| POST | /models | 注册模型 |
| GET | /models | 列出模型 |
| POST | /webhooks | 注册 webhook |
| GET | /status | 获取状态 |
| GET | /health | 健康检查 |

### Python API

```python
# 创建应用
app = create_app()

# 任务管理
task_id = await app.submit(prompt, model, priority)
result = app.get_result(task_id)
await app.cancel(task_id)

# 模型管理
await app.register_model(name, provider, api_key)
models = app.list_models()

# 回调
app.on_complete(callback)
app.on_error(callback)
app.webhook(event, url)
```

## 示例

查看 [examples/](examples/) 目录获取完整示例：

- `basic.py` - 基本使用
- `callbacks.py` - 回调机制
- `webhook.py` - Webhook 回调
- `batch.py` - 批量处理
- `custom_params.py` - 自定义参数
- `api_client.py` - API 客户端

## 许可证

MIT License
