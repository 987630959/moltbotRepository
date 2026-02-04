"""
示例：自定义模型参数
"""
import asyncio
from moltbot import MoltBot, create_app


async def custom_params_example():
    """自定义参数示例"""
    
    bot = create_app()
    
    # 提交带参数的任务
    task_id = await bot.submit(
        prompt="写一个Python函数，实现快速排序",
        
        # 模型参数
        model="gpt-4",
        
        # 任务优先级
        priority=10,
        
        # OpenAI 参数
        parameters={
            "temperature": 0.5,  # 较低的温度，更确定性的输出
            "max_tokens": 2000,
            "system_prompt": "你是一个专业的Python程序员",
            
            # 额外的对话历史
            "history": [
                {"role": "user", "content": "你好，我想学习排序算法"},
                {"role": "assistant", "content": "好的，你想学习哪种排序算法？"}
            ]
        },
        
        # 回调
        on_complete=lambda t: print(f"完成! 结果: {t.result[:50]}...")
    )
    
    result = await bot.wait(task_id)
    print(result.result)
    
    await bot.stop()


if __name__ == "__main__":
    asyncio.run(custom_params_example())
