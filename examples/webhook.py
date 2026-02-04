"""
示例：Webhook 回调
"""
import asyncio
from moltbot import MoltBot, create_app


async def webhook_example():
    """Webhook 示例"""
    
    bot = create_app()
    
    # 注册 webhook
    bot.webhook(
        event="on_complete",
        url="https://your-server.com/webhook/moltbot",
        headers={"Authorization": "Bearer your-token"}
    )
    
    bot.webhook(
        event="on_error",
        url="https://your-server.com/webhook/error"
    )
    
    # 提交任务
    task_id = await bot.submit(
        prompt="分析这段代码的性能问题...",
        parameters={
            "code": "def foo(): pass"
        }
    )
    
    print(f"任务已提交: {task_id}")
    print("结果将通过 webhook 发送到你的服务器")
    
    await bot.stop()


if __name__ == "__main__":
    asyncio.run(webhook_example())
