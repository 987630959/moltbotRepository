"""
示例：回调机制
"""
import asyncio
from moltbot import MoltBot, create_app, Task


async def callback_example():
    """回调示例"""
    
    bot = create_app()
    
    # 定义回调函数
    def on_complete_callback(task):
        print(f"✅ 任务完成: {task.id}")
        print(f"结果: {task.result[:100]}...")
    
    async def on_error_callback(task):
        print(f"❌ 任务失败: {task.id}")
        print(f"错误: {task.error}")
    
    # 注册回调
    bot.on_complete(on_complete_callback)
    bot.on_error(on_error_callback)
    
    # 提交任务
    task_id = await bot.submit(
        prompt="写一首关于春天的诗",
        priority=10  # 高优先级
    )
    
    print(f"任务已提交，等待完成...")
    
    # 或者等待所有任务完成
    await bot.wait(task_id)
    
    await bot.stop()


if __name__ == "__main__":
    asyncio.run(callback_example())
