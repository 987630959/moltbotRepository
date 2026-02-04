"""
执行引擎
异步执行 LLM 调用
"""
import asyncio
from typing import Optional, Dict, Any, List
from datetime import datetime

from .models import Task, TaskStatus
from .scheduler import TaskScheduler
from .model_manager import ModelManager, model_manager
from .callback import CallbackManager
from .providers import LLMProvider
from .config import config
from .logger import get_logger

logger = get_logger("engine")

class ExecutionEngine:
    """
    执行引擎
    - 协调任务调度和模型调用
    - 管理执行上下文
    - 跟踪执行指标
    """
    
    def __init__(
        self,
        scheduler: Optional[TaskScheduler] = None,
        model_mgr: Optional[ModelManager] = None,
        callback_mgr: Optional[CallbackManager] = None
    ):
        self.scheduler = scheduler or TaskScheduler(
            max_concurrent=config.get_config().max_concurrent_tasks
        )
        self.model_mgr = model_mgr or model_manager
        self.callback_mgr = callback_mgr or CallbackManager()
        
        self._running_tasks: Dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()
    
    async def execute(self, task: Task) -> str:
        """
        执行任务
        
        Args:
            task: 任务对象
            
        Returns:
            任务 ID
        """
        # 选择模型
        model = await self.model_mgr.get_model(task)
        
        if model is None:
            raise ValueError("没有可用的模型")
        
        task.model = model.name
        
        logger.info(f"开始执行任务: {task.id}, 使用模型: {model.name}")
        
        # 提交到调度器
        task_id = await self.scheduler.submit(task)
        
        # 在后台执行实际调用
        exec_task = asyncio.create_task(
            self._run_llm_call(task, model)
        )
        
        async with self._lock:
            self._running_tasks[task_id] = exec_task
        
        return task_id
    
    async def _run_llm_call(self, task: Task, model):
        """
        运行 LLM 调用
        """
        try:
            # 获取 LLM 提供商
            llm_provider = LLMProvider.create(model)
            
            # 构建消息
            messages = self._build_messages(task)
            
            # 执行调用
            start_time = datetime.utcnow()
            
            result = await llm_provider.chat_completion(
                messages=messages,
                temperature=task.parameters.get("temperature"),
                max_tokens=task.parameters.get("max_tokens"),
                **task.parameters
            )
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            
            # 更新模型统计
            await self.model_mgr.update_model_stats(
                model.name,
                success=True,
                response_time=response_time
            )
            
            # 设置结果
            task.result = result
            task.status = TaskStatus.COMPLETED
            
            # 触发回调
            await self.callback_mgr.trigger_callbacks("on_complete", task)
            
            logger.info(
                f"任务执行成功: {task.id}, "
                f"模型: {model.name}, "
                f"耗时: {response_time:.2f}s"
            )
            
        except Exception as e:
            task.error = str(e)
            task.status = TaskStatus.FAILED
            
            # 更新模型统计
            await self.model_mgr.update_model_stats(
                model.name,
                success=False,
                response_time=0
            )
            
            # 触发错误回调
            await self.callback_mgr.trigger_callbacks("on_error", task)
            
            logger.error(f"任务执行失败: {task.id}, 错误: {e}")
            
            # 如果需要重试
            if task.retry_count < task.max_retries:
                task.retry_count += 1
                logger.info(f"任务准备重试: {task.id}, "
                          f"重试次数: {task.retry_count}/{task.max_retries}")
                await asyncio.sleep(2 ** task.retry_count)  # 指数退避
                await self._run_llm_call(task, model)
    
    def _build_messages(self, task: Task) -> list:
        """构建消息列表"""
        # 默认系统提示
        system_prompt = task.parameters.get(
            "system_prompt",
            "You are a helpful AI assistant."
        )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task.prompt}
        ]
        
        # 如果有对话历史
        if "history" in task.parameters:
            messages = task.parameters["history"] + messages
        
        return messages
    
    async def execute_batch(
        self,
        tasks: List[Task],
        concurrency: int = 5
    ) -> List[str]:
        """
        批量执行任务
        
        Args:
            tasks: 任务列表
            concurrency: 并发数
            
        Returns:
            任务 ID 列表
        """
        semaphore = asyncio.Semaphore(concurrency)
        
        async def run_with_semaphore(task):
            async with semaphore:
                return await self.execute(task)
        
        results = await asyncio.gather(*[
            run_with_semaphore(task) for task in tasks
        ])
        
        return results
    
    def get_task_result(self, task_id: str) -> Optional[Task]:
        """获取任务结果"""
        return self.scheduler.get_task(task_id)
    
    async def wait_for_completion(
        self,
        task_id: str,
        timeout: Optional[int] = None
    ) -> Task:
        """等待任务完成"""
        task = self.scheduler.get_task(task_id)
        
        if task is None:
            raise ValueError(f"任务不存在: {task_id}")
        
        while task.status not in [
            TaskStatus.COMPLETED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED
        ]:
            await asyncio.sleep(0.1)
            
            # 检查超时
            if timeout:
                timeout -= 0.1
                if timeout <= 0:
                    raise TimeoutError(f"任务超时: {task_id}")
            
            task = self.scheduler.get_task(task_id)
        
        return task
    
    @property
    def stats(self) -> Dict[str, Any]:
        """获取执行统计"""
        return {
            "running": self.scheduler.running_count,
            "pending": self.scheduler.pending_count,
            "total_tasks": len(self.scheduler.get_all_tasks())
        }
