"""
FastAPI REST API
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from datetime import datetime
import asyncio

from . import MoltBot, Task, TaskStatus, ModelInfo
from .logger import get_logger

logger = get_logger("api")

# 创建 FastAPI 应用
app = FastAPI(
    title="MoltBot API",
    description="分布式大模型调用框架 API",
    version="0.1.0"
)

# 允许 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 全局框架实例
bot: Optional[MoltBot] = None

def get_bot() -> MoltBot:
    """获取框架实例"""
    global bot
    if bot is None:
        bot = MoltBot()
    return bot

# ========== 数据模型 ==========

class TaskSubmit(BaseModel):
    prompt: str
    model: Optional[str] = None
    priority: int = 5
    parameters: Dict[str, Any] = {}
    on_complete_url: Optional[str] = None
    on_error_url: Optional[str] = None

class TaskResponse(BaseModel):
    task_id: str
    status: str
    created_at: datetime

class TaskResult(BaseModel):
    id: str
    status: str
    prompt: str
    result: Optional[str] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    model: Optional[str] = None

class ModelRegister(BaseModel):
    name: str
    provider: str = "openai"
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    weight: int = 10
    max_tokens: int = 4096
    temperature: float = 0.7

class WebhookRegister(BaseModel):
    event: str
    url: str
    headers: Dict[str, str] = {}

# ========== 任务端点 ==========

@app.post("/tasks", response_model=TaskResponse)
async def submit_task(task_data: TaskSubmit, background_tasks: BackgroundTasks):
    """提交任务"""
    bot = get_bot()
    
    # 创建任务
    task = Task(
        prompt=task_data.prompt,
        model=task_data.model,
        priority=task_data.priority,
        parameters=task_data.parameters
    )
    
    # 注册 webhook 回调
    if task_data.on_complete_url:
        bot.callback_mgr.register_webhook(
            "on_complete",
            task_data.on_complete_url
        )
    if task_data.on_error_url:
        bot.callback_mgr.register_webhook(
            "on_error",
            task_data.on_error_url
        )
    
    # 提交任务
    task_id = await bot.submit_task(task)
    
    return TaskResponse(
        task_id=task_id,
        status="pending",
        created_at=datetime.utcnow()
    )

@app.get("/tasks", response_model=List[TaskResult])
async def list_tasks(status: Optional[str] = None):
    """列出任务"""
    bot = get_bot()
    
    status_enum = None
    if status:
        try:
            status_enum = TaskStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail="无效的状态")
    
    tasks = bot.list_tasks(status=status_enum)
    
    return [
        TaskResult(
            id=t.id,
            status=t.status,
            prompt=t.prompt[:100] + "..." if len(t.prompt) > 100 else t.prompt,
            result=t.result,
            error=t.error,
            created_at=t.created_at,
            started_at=t.started_at,
            completed_at=t.completed_at,
            model=t.model
        )
        for t in tasks
    ]

@app.get("/tasks/{task_id}", response_model=TaskResult)
async def get_task(task_id: str):
    """获取任务详情"""
    bot = get_bot()
    
    task = bot.get_result(task_id)
    
    if task is None:
        raise HTTPException(status_code=404, detail="任务不存在")
    
    return TaskResult(
        id=task.id,
        status=task.status,
        prompt=task.prompt,
        result=task.result,
        error=task.error,
        created_at=task.created_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        model=task.model
    )

@app.post("/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """取消任务"""
    bot = get_bot()
    
    success = await bot.cancel(task_id)
    
    if not success:
        raise HTTPException(status_code=400, detail="取消失败")
    
    return {"message": "任务已取消"}

@app.post("/tasks/{task_id}/wait")
async def wait_task(task_id: str, timeout: Optional[int] = 60):
    """等待任务完成"""
    bot = get_bot()
    
    try:
        task = await bot.wait(task_id, timeout)
        
        return TaskResult(
            id=task.id,
            status=task.status,
            prompt=task.prompt,
            result=task.result,
            error=task.error,
            created_at=task.created_at,
            started_at=task.started_at,
            completed_at=task.completed_at,
            model=task.model
        )
    except TimeoutError:
        raise HTTPException(status_code=408, detail="任务超时")

@app.post("/tasks/batch")
async def submit_batch(tasks: List[TaskSubmit], concurrency: int = 5):
    """批量提交任务"""
    bot = get_bot()
    
    task_objects = [
        Task(
            prompt=t.prompt,
            model=t.model,
            priority=t.priority,
            parameters=t.parameters
        )
        for t in tasks
    ]
    
    task_ids = await bot.engine.execute_batch(task_objects, concurrency)
    
    return {"task_ids": task_ids}

# ========== 模型端点 ==========

@app.post("/models")
async def register_model(model: ModelRegister):
    """注册模型"""
    bot = get_bot()
    
    model_info = ModelInfo(
        name=model.name,
        provider=model.provider,
        api_key=model.api_key,
        base_url=model.base_url,
        weight=model.weight,
        max_tokens=model.max_tokens,
        temperature=model.temperature
    )
    
    await bot.model_mgr.register_model(model_info)
    
    return {"message": "模型已注册", "name": model.name}

@app.get("/models", response_model=List[Dict[str, Any]])
async def list_models():
    """列出模型"""
    bot = get_bot()
    
    models = bot.list_models()
    
    return [
        {
            "name": m.name,
            "provider": m.provider,
            "available": m.available,
            "weight": m.weight,
            "avg_response_time": m.avg_response_time,
            "success_rate": m.success_rate
        }
        for m in models
    ]

# ========== Webhook 端点 ==========

@app.post("/webhooks")
async def register_webhook(webhook: WebhookRegister):
    """注册 webhook"""
    bot = get_bot()
    
    bot.callback_mgr.register_webhook(
        webhook.event,
        webhook.url,
        webhook.headers
    )
    
    return {"message": "Webhook 已注册"}

# ========== 状态端点 ==========

@app.get("/status")
async def get_status():
    """获取框架状态"""
    bot = get_bot()
    return bot.status

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "ok"}

# ========== 启动事件 ==========

@app.on_event("startup")
async def startup():
    """启动时初始化"""
    global bot
    bot = MoltBot()
    await bot.start()
    logger.info("MoltBot API 已启动")

@app.on_event("shutdown")
async def shutdown():
    """关闭时清理"""
    global bot
    if bot:
        await bot.stop()
        logger.info("MoltBot API 已关闭")
