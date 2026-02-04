"""
分布式协调模块
Redis 集成：队列、状态存储、分布式锁
"""
import asyncio
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
import hashlib
import redis.asyncio as redis
from redis.asyncio.lock import Lock

from .config import config
from .logger import get_logger

logger = get_logger("distributed")

class DistributedManager:
    """
    分布式管理器
    - Redis 连接管理
    - 分布式任务队列
    - 任务状态同步
    - 分布式锁
    """
    
    def __init__(self):
        self._client: Optional[redis.Redis] = None
        self._pubsub: Optional[redis.client.PubSub] = None
        self._config = config.get_config()
        self._lock = asyncio.Lock()
        self._initialized = False
        self._listeners: Dict[str, asyncio.Queue] = {}
    
    async def connect(self):
        """连接 Redis"""
        async with self._lock:
            if self._initialized:
                return
            
            if not self._config.use_redis:
                logger.info("Redis 未启用，使用本地模式")
                return
            
            try:
                self._client = redis.Redis(
                    host=self._config.redis_host,
                    port=self._config.redis_port,
                    db=self._config.redis_db,
                    password=self._config.redis_password,
                    decode_responses=True
                )
                
                # 测试连接
                await self._client.ping()
                self._initialized = True
                logger.info(
                    f"Redis 已连接: "
                    f"{self._config.redis_host}:{self._config.redis_port}"
                )
            except Exception as e:
                logger.error(f"Redis 连接失败: {e}")
                raise
    
    async def disconnect(self):
        """断开 Redis"""
        if self._client:
            await self._client.aclose()
            self._initialized = False
            logger.info("Redis 已断开")
    
    async def is_connected(self) -> bool:
        """检查是否已连接"""
        return self._initialized and self._client is not None
    
    # ========== 任务队列 ==========
    
    async def push_task(self, task_id: str, task_data: Dict[str, Any], priority: int = 5):
        """
        推送任务到队列
        
        Args:
            task_id: 任务 ID
            task_data: 任务数据
            priority: 优先级
        """
        if not await self.is_connected():
            return
        
        queue_key = f"moltbot:queue:priority:{priority}"
        
        await self._client.rpush(queue_key, json.dumps({
            "task_id": task_id,
            "data": task_data,
            "created_at": datetime.utcnow().isoformat()
        }))
        
        logger.debug(f"任务已入队: {task_id}, 优先级: {priority}")
    
    async def pop_task(self, timeout: int = 1) -> Optional[Dict]:
        """
        从队列弹出任务
        
        Returns:
            任务数据或 None
        """
        if not await self.is_connected():
            return None
        
        # 按优先级从高到低检查
        for priority in [10, 5, 1]:
            queue_key = f"moltbot:queue:priority:{priority}"
            task = await self._client.lpop(queue_key)
            
            if task:
                return json.loads(task)
        
        # 等待新任务
        await asyncio.sleep(timeout)
        return None
    
    async def get_queue_size(self, priority: int = 5) -> int:
        """获取队列大小"""
        if not await self.is_connected():
            return 0
        
        queue_key = f"moltbot:queue:priority:{priority}"
        return await self._client.llen(queue_key)
    
    # ========== 任务状态 ==========
    
    async def set_task_status(
        self,
        task_id: str,
        status: str,
        data: Optional[Dict] = None
    ):
        """设置任务状态"""
        if not await self.is_connected():
            return
        
        key = f"moltbot:task:{task_id}"
        
        task_data = {
            "status": status,
            "updated_at": datetime.utcnow().isoformat(),
            **(data or {})
        }
        
        await self._client.hset(key, mapping={
            k: json.dumps(v) if isinstance(v, (dict, list)) else v
            for k, v in task_data.items()
        })
        
        # 设置过期时间 24 小时
        await self._client.expire(key, 86400)
        
        # 发布状态变更
        await self._publish(f"moltbot:events:task:{task_id}", task_data)
    
    async def get_task_status(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        if not await self.is_connected():
            return None
        
        key = f"moltbot:task:{task_id}"
        data = await self._client.hgetall(key)
        
        if not data:
            return None
        
        return {
            k: json.loads(v) if v.startswith("{") or v.startswith("[") else v
            for k, v in data.items()
        }
    
    # ========== 分布式锁 ==========
    
    async def acquire_lock(
        self,
        lock_name: str,
        timeout: int = 30,
        retry_interval: float = 0.1
    ) -> Optional[Lock]:
        """获取锁"""
        if not await self.is_connected():
            return None
        
        lock_key = f"moltbot:lock:{lock_name}"
        
        lock = self._client.lock(
            lock_key,
            timeout=timeout,
            blocking_timeout=None
        )
        
        acquired = await lock.acquire()
        
        if acquired:
            logger.debug(f"获取锁成功: {lock_name}")
            return lock
        
        return None
    
    async def release_lock(self, lock: Lock):
        """释放锁"""
        if lock:
            await lock.release()
            logger.debug("锁已释放")
    
    # ========== 发布/订阅 ==========
    
    async def _publish(self, channel: str, message: Dict):
        """发布消息"""
        if not await self.is_connected():
            return
        
        await self._client.publish(
            channel,
            json.dumps(message)
        )
    
    async def subscribe(self, channel: str) -> asyncio.Queue:
        """
        订阅频道
        
        Returns:
            消息队列
        """
        if not self._pubsub:
            self._pubsub = self._client.pubsub()
        
        queue = asyncio.Queue()
        self._listeners[channel] = queue
        
        await self._pubsub.subscribe(channel)
        
        # 在后台监听
        asyncio.create_task(self._listen_pubsub())
        
        return queue
    
    async def _listen_pubsub(self):
        """监听 PubSub 消息"""
        if not self._pubsub:
            return
        
        try:
            while True:
                message = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0
                )
                
                if message and message["type"] == "message":
                    channel = message["channel"]
                    
                    if channel in self._listeners:
                        try:
                            data = json.loads(message["data"])
                            await self._listeners[channel].put(data)
                        except Exception as e:
                            logger.error(f"PubSub 消息解析失败: {e}")
        except Exception as e:
            logger.error(f"PubSub 监听错误: {e}")
    
    # ========== 模型负载均衡 ==========
    
    async def increment_model_usage(self, model_name: str):
        """增加模型使用计数"""
        if not await self.is_connected():
            return
        
        key = f"moltbot:model:{model_name}:usage"
        await self._client.incr(key)
        
        # 设置过期时间 1 小时
        await self._client.expire(key, 3600)
    
    async def get_model_usage(self, model_name: str) -> int:
        """获取模型使用计数"""
        if not await self.is_connected():
            return 0
        
        key = f"moltbot:model:{model_name}:usage"
        count = await self._client.get(key)
        return int(count) if count else 0
    
    async def set_model_available(self, model_name: str, available: bool):
        """设置模型可用性"""
        if not await self.is_connected():
            return
        
        key = f"moltbot:model:{model_name}:available"
        await self._client.set(key, "1" if available else "0", ex=300)
    
    async def is_model_available(self, model_name: str) -> bool:
        """检查模型是否可用"""
        if not await self.is_connected():
            return True
        
        key = f"moltbot:model:{model_name}:available"
        value = await self._client.get(key)
        
        # 如果没有设置，默认可用
        if value is None:
            return True
        
        return value == "1"

# 全局实例
distributed = DistributedManager()
