"""
MoltBot - 分布式大模型调用框架
"""
import asyncio
from typing import Optional, Dict, Any, List, Callable, Awaitable
from datetime import datetime

from .models import Task, TaskStatus, ModelInfo
from .config import config
from .scheduler import TaskScheduler
from .model_manager import ModelManager, model_manager
from .callback import CallbackManager
from .engine import ExecutionEngine
from .logger import get_logger

logger = get_logger("framework")


class MoltBot:
    """
    MoltBot 主框架
    提供简洁的 API 用于任务注册和执行
    """
    
    def __init__(self):
        self.scheduler = TaskScheduler(
            max_concurrent=config.get_config().max_concurrent_tasks
        )
        self.model_mgr = model_manager
        self.callback_mgr = CallbackManager()
        self.engine = ExecutionEngine(
            scheduler=self.scheduler,
            model_mgr=self.model_mgr,
            callback_mgr=self.callback_mgr
        )
        
        self._started = False
    
    # ========== 任务管理 ==========
    
    async def submit(
        self,
        prompt: str,
        model: Optional[str] = None,
        priority: int = 5,
        on_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
        **kwargs
    ) -> str:
        """
        提交任务
        
        Args:
            prompt: 任务提示
            model: 指定模型（可选）
            priority: 优先级 (1-20)
            on_complete: 完成回调
            on_error: 错误回调
            **kwargs: 其他参数
            
        Returns:
            任务 ID
        """
        # 创建任务
        task = Task(
            prompt=prompt,
            model=model,
            priority=priority,
            parameters=kwargs,
            max_retries=config.get_config().retry_times,
            timeout=config.get_config().task_timeout
        )
        
        # 注册回调
        if on_complete:
            self.callback_mgr.register_callback(
                "on_complete",
                on_complete,
                is_async=asyncio.iscoroutinefunction(on_complete)
            )
        
        if on_error:
            self.callback_mgr.register_callback(
                "on_error",
                on_error,
                is_async=asyncio.iscoroutinefunction(on_error)
            )
        
        # 执行
        return await self.engine.execute(task)
    
    async def submit_task(self, task: Task) -> str:
        """直接提交任务对象"""
        return await self.engine.execute(task)
    
    async def execute(
        self,
        prompt: str,
        model: Optional[str] = None,
        **kwargs
    ) -> str:
        """提交并等待任务完成"""
        task_id = await self.submit(prompt, model, **kwargs)
        result = await self.wait(task_id)
        return result
    
    def get_result(self, task_id: str) -> Optional[Task]:
        """获取任务结果"""
        return self.engine.get_task_result(task_id)
    
    async def wait(
        self,
        task_id: str,
        timeout: Optional[int] = None
    ) -> Task:
        """等待任务完成"""
        return await self.engine.wait_for_completion(task_id, timeout)
    
    async def cancel(self, task_id: str) -> bool:
        """取消任务"""
        return await self.scheduler.cancel(task_id)
    
    def list_tasks(
        self,
        status: Optional[TaskStatus] = None
    ) -> List[Task]:
        """列出任务"""
        if status:
            return self.scheduler.get_tasks_by_status(status)
        return self.scheduler.get_all_tasks()
    
    # ========== 模型管理 ==========
    
    async def register_model(
        self,
        name: str,
        provider: str = "openai",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        weight: int = 10,
        **kwargs
    ):
        """注册模型"""
        model = ModelInfo(
            name=name,
            provider=provider,
            api_key=api_key,
            base_url=base_url,
            weight=weight,
            **kwargs
        )
        await self.model_mgr.register_model(model)
    
    def list_models(self) -> List[ModelInfo]:
        """列出模型"""
        return self.model_mgr.list_models()
    
    # ========== 回调管理 ==========
    
    def on_complete(self, func: Callable):
        """注册完成回调"""
        self.callback_mgr.register_callback(
            "on_complete",
            func,
            is_async=asyncio.iscoroutinefunction(func)
        )
        return func
    
    def on_error(self, func: Callable):
        """注册错误回调"""
        self.callback_mgr.register_callback(
            "on_error",
            func,
            is_async=asyncio.iscoroutinefunction(func)
        )
        return func
    
    def webhook(
        self,
        event: str,
        url: str,
        headers: Optional[Dict] = None
    ):
        """注册 webhook"""
        self.callback_mgr.register_webhook(event, url, headers)
    
    # ========== 生命周期 ==========
    
    async def start(self):
        """启动框架"""
        if not self._started:
            self._started = True
            await self.model_mgr.start_health_check()
            logger.info("MoltBot 已启动")
    
    async def stop(self):
        """停止框架"""
        if self._started:
            await self.model_mgr.stop_health_check()
            await self.callback_mgr.close()
            self._started = False
            logger.info("MoltBot 已停止")
    
    async def run(self):
        """运行框架（阻塞）"""
        await self.start()
        
        try:
            while True:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            await self.stop()
    
    @property
    def status(self) -> Dict[str, Any]:
        """获取状态"""
        return {
            "started": self._started,
            "running": self.engine.stats,
            "models": len(self.model_mgr.list_models()),
            "tasks": {
                "total": len(self.scheduler.get_all_tasks()),
                "pending": len(self.scheduler.get_tasks_by_status(TaskStatus.PENDING)),
                "running": len(self.scheduler.get_tasks_by_status(TaskStatus.RUNNING)),
                "completed": len(self.scheduler.get_tasks_by_status(TaskStatus.COMPLETED)),
                "failed": len(self.scheduler.get_tasks_by_status(TaskStatus.FAILED))
            }
        }


# 便捷函数
def create_app() -> MoltBot:
    """创建 MolBot 实例"""
    return MoltBot()


# 导出
from .models import TaskPriority
from .api import app

__all__ = [
    "MoltBot",
    "Task",
    "TaskStatus",
    "TaskPriority",
    "ModelInfo",
    "create_app",
    "app"
]
