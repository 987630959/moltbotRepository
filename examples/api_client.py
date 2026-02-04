"""
示例：使用 API 服务器
"""
# 保存为 examples/api_client.py

import httpx
import asyncio

API_BASE = "http://localhost:8000"


async def api_example():
    """API 客户端示例"""
    
    async with httpx.AsyncClient() as client:
        # 1. 注册模型
        await client.post(f"{API_BASE}/models", json={
            "name": "gpt-4",
            "provider": "openai",
            "api_key": "your-api-key",
            "weight": 10
        })
        
        # 2. 提交任务
        response = await client.post(f"{API_BASE}/tasks", json={
            "prompt": "解释一下 RESTful API",
            "priority": 5,
            "parameters": {
                "temperature": 0.7
            },
            "on_complete_url": "https://your-server.com/webhook"
        })
        
        task_id = response.json()["task_id"]
        print(f"任务已提交: {task_id}")
        
        # 3. 等待完成
        result = await client.post(
            f"{API_BASE}/tasks/{task_id}/wait",
            params={"timeout": 60}
        )
        
        task_data = result.json()
        print(f"状态: {task_data['status']}")
        print(f"结果: {task_data['result'][:100]}...")
        
        # 4. 批量提交
        tasks = [
            {"prompt": f"任务 {i}"}
            for i in range(5)
        ]
        
        batch_response = await client.post(
            f"{API_BASE}/tasks/batch",
            json=tasks,
            params={"concurrency": 3}
        )
        
        print(f"批量任务 IDs: {batch_response.json()['task_ids']}")


if __name__ == "__main__":
    asyncio.run(api_example())
