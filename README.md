# MoltBot - 分布式大模型调用框架

## 简介

MoltBot 是一个高性能、分布式的异步大模型调用框架，专为 Agent 开发设计。

## 核心特性

- 🚀 **高性能异步执行** - 基于 asyncio 的并行任务处理
- 🌐 **分布式支持** - Redis 集成，支持多节点部署
- 📊 **智能调度** - 根据模型可用度自动分配任务
- 🔄 **灵活回调** - 支持多种回调机制（Webhooks、WebSocket）
- 🔌 **易于集成** - 简洁的 API 设计

## 安装

```bash
pip install moltbot
```

## 快速开始

```python
from moltbot import MoltBot, Task, Callback

# 初始化框架
app = MoltBot()

# 定义回调
async def on_complete(task):
    print(f"任务完成: {task.result}")

# 注册任务
@app.register(model="gpt-4")
async def my_task():
    return await app.execute(
        Task(
            prompt="分析这段文本...",
            on_complete=on_complete
        )
    )

# 运行
app.run()
```

## 文档

详细文档请参考 [docs/](docs/)

## 许可证

MIT
