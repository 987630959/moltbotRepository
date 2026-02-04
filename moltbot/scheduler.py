"""
异步任务调度器
"""
import asyncio
from typing import Dict, Optional, List, Callable, Awaitable
from datetime import datetime
from collections import deque
import uuid

from .models import Task, TaskStatus, TaskPriority
from .config import config
from .logger import get_logger

logger = get_logger("scheduler")

class TaskScheduler:
    """
    异步任务调度器
    支持优先级队列、任务状态追踪、并发控制
    """
    
    def __init__(self, max_concurrent: int = 100):
        self.max_concurrent = max_concurrent
        self._running_count = 0
        self._tasks: Dict[str, Task] = {}
        self._queues: Dict[TaskPriority, deque] = {
            priority: deque() for priority in TaskPriority
        }
        self._callbacks: Dict[str, List[Callable]] = {
            "on_submit": [],
            "on_start": [],
            "on_complete": [],
            "on_error": [],
            "on_cancel": []
        }
        self._lock = asyncio.Lock()
    
    async def submit(self, task: Task) -> str:
        """
        提交任务
        
        Args:
            task: 任务对象
            
        Returns:
            任务 ID
        """
        async with self._lock:
            # 设置任务状态
            task.status = TaskStatus.PENDING
            task.created_at = datetime.utcnow()
            
            # 保存任务
            self._tasks[task.id] = task
            
            # 添加到对应优先级队列
            self._queues[task.priority].append(task.id)
            
            logger.info(f"任务已提交: {task.id}, 优先级: {task.priority}")
        
        # 触发回调
        await self._trigger_callbacks("on_submit", task)
        
        # 尝试调度执行
        asyncio.create_task(self._schedule())
        
        return task.id
    
    async def _schedule(self):
        """调度任务执行"""
        if self._running_count >= self.max_concurrent:
            return
        
        # 按优先级从高到低查找可用任务
        for priority in reversed(list(TaskPriority)):
            queue = self._queues[priority]
            
            while queue and self._running_count < self.max_concurrent:
                task_id = queue.popleft()
                
                if task_id not in self._tasks:
                    continue
                    
                task = self._tasks[task_id]
                
                if task.status != TaskStatus.PENDING:
                    continue
                
                # 执行任务
                self._running_count += 1
                asyncio.create_task(self._execute(task))
    
    async def _execute(self, task: Task):
        """执行任务"""
        try:
            task.status = TaskStatus.RUNNING
            task.started_at = datetime.utcnow()
            
            logger.info(f"任务开始执行: {task.id}")
            
            # 触发开始回调
            await self._trigger_callbacks("on_start", task)
            
            # 等待任务完成（由执行引擎调用）
            result = await self._wait_for_completion(task)
            
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()
            task.result = result
            
            logger.info(f"任务完成: {task.id}")
            
            # 触发完成回调
            await self._trigger_callbacks("on_complete", task)
            
        except Exception as e:
            task.status = TaskStatus.FAILED
            task.error = str(e)
            task.completed_at = datetime.utcnow()
            
            logger.error(f"任务执行失败: {task.id}, 错误: {e}")
            
            # 触发错误回调
            await self._trigger_callbacks("on_error", task)
            
        finally:
            async with self._lock:
                self._running_count -= 1
            
            # 继续调度
            asyncio.create_task(self._schedule())
    
    async def _wait_for_completion(self, task: Task) -> str:
        """等待任务完成（由外部设置结果）"""
        while task.status == TaskStatus.RUNNING:
            await asyncio.sleep(0.1)
        return task.result
    
    async def cancel(self, task_id: str) -> bool:
        """取消任务"""
        async with self._lock:
            if task_id not in self._tasks:
                return False
            
            task = self._tasks[task_id]
            
            if task.status not in [TaskStatus.PENDING, TaskStatus.RUNNING]:
                return False
            
            task.status = TaskStatus.CANCELLED
            task.completed_at = datetime.utcnow()
            
            logger.info(f"任务已取消: {task_id}")
            
            await self._trigger_callbacks("on_cancel", task)
            
            return True
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """获取任务信息"""
        return self._tasks.get(task_id)
    
    def get_all_tasks(self) -> List[Task]:
        """获取所有任务"""
        return list(self._tasks.values())
    
    def get_tasks_by_status(self, status: TaskStatus) -> List[Task]:
        """按状态获取任务"""
        return [t for t in self._tasks.values() if t.status == status]
    
    def on(self, event: str, callback: Callable):
        """注册事件回调"""
        if event in self._callbacks:
            self._callbacks[event].append(callback)
    
    async def _trigger_callbacks(self, event: str, task: Task):
        """触发事件回调"""
        if event in self._callbacks:
            for callback in self._callbacks[event]:
                try:
                    if asyncio.iscoroutinefunction(callback):
                        await callback(task)
                    else:
                        callback(task)
                except Exception as e:
                    logger.error(f"回调执行失败: {event}, 错误: {e}")
    
    @property
    def running_count(self) -> int:
        """当前运行任务数"""
        return self._running_count
    
    @property
    def pending_count(self) -> int:
        """当前等待任务数"""
        return sum(len(q) for q in self._queues.values())
