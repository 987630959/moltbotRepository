"""
回调管理器
支持同步/异步回调、Webhook
"""
import asyncio
import json
from typing import Dict, List, Callable, Awaitable, Optional
from datetime import datetime
from enum import Enum

import httpx

from .models import Task, CallbackType, WebhookConfig
from .logger import get_logger

logger = get_logger("callback")

class Callback:
    """
    回调封装
    """
    
    def __init__(
        self,
        func: Callable,
        is_async: bool = False,
        retry_times: int = 3,
        timeout: int = 10
    ):
        self.func = func
        self.is_async = is_async
        self.retry_times = retry_times
        self.timeout = timeout
    
    async def execute(self, task: Task, *args, **kwargs):
        """执行回调"""
        try:
            if self.is_async:
                result = await asyncio.wait_for(
                    self.func(task, *args, **kwargs),
                    timeout=self.timeout
                )
            else:
                result = await asyncio.to_thread(
                    self.func, task, *args, **kwargs
                )
            return result
        except Exception as e:
            logger.error(f"回调执行失败: {e}")
            raise

class CallbackManager:
    """
    回调管理器
    - 管理任务回调
    - 处理 webhook
    - 支持重试机制
    """
    
    def __init__(self):
        self._callbacks: Dict[str, List[Callback]] = {
            "on_complete": [],
            "on_error": [],
            "on_progress": [],
            "on_start": []
        }
        self._webhooks: Dict[str, WebhookConfig] = {}
        self._http_client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0)
            )
        return self._http_client
    
    async def close(self):
        """关闭客户端"""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
    
    def register_callback(
        self,
        event: str,
        func: Callable,
        is_async: bool = False
    ):
        """注册回调函数"""
        if event not in self._callbacks:
            self._callbacks[event] = []
        
        callback = Callback(func, is_async=is_async)
        self._callbacks[event].append(callback)
        logger.info(f"回调已注册: {event}")
    
    async def trigger_callbacks(self, event: str, task: Task):
        """触发回调"""
        if event not in self._callbacks:
            return
        
        for callback in self._callbacks[event]:
            try:
                await callback.execute(task)
            except Exception as e:
                logger.error(f"回调执行失败 ({event}): {e}")
    
    def register_webhook(
        self,
        event: str,
        url: str,
        headers: Optional[Dict] = None,
        retry_times: int = 3
    ):
        """注册 webhook"""
        webhook_id = f"{event}:{url}"
        self._webhooks[webhook_id] = WebhookConfig(
            url=url,
            headers=headers or {},
            retry_times=retry_times
        )
        logger.info(f"Webhook 已注册: {webhook_id}")
    
    async def send_webhook(
        self,
        event: str,
        task: Task,
        payload: Optional[Dict] = None
    ):
        """发送 webhook"""
        # 查找匹配的 webhooks
        matching = [
            (k, v) for k, v in self._webhooks.items()
            if k.startswith(event + ":")
        ]
        
        if not matching:
            return
        
        webhook_data = {
            "event": event,
            "task_id": task.id,
            "status": task.status,
            "result": task.result,
            "error": task.error,
            "timestamp": datetime.utcnow().isoformat(),
            **(payload or {})
        }
        
        client = await self._get_client()
        
        for webhook_id, config in matching:
            for attempt in range(config.retry_times):
                try:
                    response = await client.post(
                        config.url,
                        json=webhook_data,
                        headers=config.headers,
                        timeout=config.timeout
                    )
                    response.raise_for_status()
                    logger.info(f"Webhook 发送成功: {webhook_id}")
                    break
                except Exception as e:
                    logger.error(
                        f"Webhook 发送失败 ({webhook_id}): "
                        f"{e}, 重试 {attempt + 1}/{config.retry_times}"
                    )
    
    def list_callbacks(self, event: str) -> List[str]:
        """列出某类事件的回调"""
        return [str(i) for i in self._callbacks.get(event, [])]
