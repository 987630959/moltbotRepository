"""
示例：基本使用
"""
import asyncio
from moltbot import MoltBot, create_app


async def basic_example():
    """基本使用示例"""
    
    # 创建框架实例
    bot = create_app()
    
    # 注册 OpenAI 模型
    await bot.register_model(
        name="gpt-4",
        provider="openai",
        api_key="your-api-key",
        weight=10
    )
    
    await bot.register_model(
        name="gpt-3.5-turbo",
        provider="openai",
        api_key="your-api-key",
        weight=20  # 更高的权重意味着更高的优先级
    )
    
    # 提交任务
    task_id = await bot.submit(
        prompt="解释一下什么是量子计算？",
        model="gpt-4",  # 可为空，会自动选择
        priority=5
    )
    
    print(f"任务已提交: {task_id}")
    
    # 等待结果
    result = await bot.wait(task_id, timeout=60)
    
    print(f"状态: {result.status}")
    print(f"结果: {result.result}")
    
    await bot.stop()


if __name__ == "__main__":
    asyncio.run(basic_example())
