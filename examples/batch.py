"""
示例：批量任务处理
"""
import asyncio
from moltbot import MoltBot, create_app, Task


async def batch_example():
    """批量处理示例"""
    
    bot = create_app()
    
    # 创建多个任务
    tasks = [
        Task(
            prompt=f"翻译第{i+1}段文本到英文",
            priority=5
        )
        for i in range(10)
    ]
    
    # 批量执行（并发控制）
    task_ids = await bot.engine.execute_batch(
        tasks,
        concurrency=5  # 最多同时5个任务
    )
    
    print(f"已提交 {len(task_ids)} 个任务")
    
    # 等待所有任务完成
    for task_id in task_ids:
        result = await bot.wait(task_id, timeout=120)
        print(f"任务 {task_id}: {result.status}")
    
    await bot.stop()


if __name__ == "__main__":
    asyncio.run(batch_example())
