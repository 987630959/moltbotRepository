"""
模型管理器
支持多模型注册、负载均衡、可用度检测
"""
import asyncio
from typing import Dict, Optional, List
from datetime import datetime
import random

from .models import ModelInfo, Task
from .config import config
from .logger import get_logger

logger = get_logger("model_manager")

class ModelManager:
    """
    模型管理器
    - 管理多个 LLM 模型
    - 根据策略选择最佳模型
    - 跟踪模型可用性和性能指标
    """
    
    def __init__(self):
        self._models: Dict[str, ModelInfo] = {}
        self._usage_count: Dict[str, int] = {}
        self._lock = asyncio.Lock()
        self._health_check_interval = 60  # 秒
        self._health_check_task: Optional[asyncio.Task] = None
    
    async def register_model(self, model: ModelInfo):
        """注册模型"""
        async with self._lock:
            self._models[model.name] = model
            self._usage_count[model.name] = 0
            logger.info(f"模型已注册: {model.name} ({model.provider})")
    
    async def unregister_model(self, model_name: str):
        """注销模型"""
        async with self._lock:
            if model_name in self._models:
                del self._models[model_name]
                logger.info(f"模型已注销: {model_name}")
    
    async def get_model(self, task: Task) -> Optional[ModelInfo]:
        """
        根据任务选择最佳模型
        
        Args:
            task: 任务对象
            
        Returns:
            选中的模型信息
        """
        # 如果任务指定了模型，尝试使用指定模型
        if task.model and task.model in self._models:
            model = self._models[task.model]
            if model.available:
                return model
            logger.warning(f"指定模型不可用: {task.model}")
        
        # 根据策略选择模型
        strategy = config.get_config().model_selection_strategy
        
        available_models = [
            m for m in self._models.values() 
            if m.available
        ]
        
        if not available_models:
            logger.error("没有可用的模型")
            return None
        
        if strategy == "availability":
            return self._select_by_availability(available_models)
        elif strategy == "load":
            return self._select_by_load(available_models)
        elif strategy == "cost":
            return self._select_by_cost(available_models)
        elif strategy == "random":
            return random.choice(available_models)
        else:
            # 默认使用可用度策略
            return self._select_by_availability(available_models)
    
    def _select_by_availability(self, models: List[ModelInfo]) -> ModelInfo:
        """根据综合可用度选择模型"""
        # 计算综合评分: 权重 * 成功率 - 响应时间惩罚
        scored_models = []
        for model in models:
            score = (
                model.weight * model.success_rate 
                - model.avg_response_time / 10
            )
            scored_models.append((model, score))
        
        # 按评分排序
        scored_models.sort(key=lambda x: x[1], reverse=True)
        
        # 还可以加入随机因素，避免总是选择同一个模型
        top_n = min(3, len(scored_models))
        selected, _ = random.choice(scored_models[:top_n])
        
        logger.debug(f"选择模型 (availability): {selected.name}")
        return selected
    
    def _select_by_load(self, models: List[ModelInfo]) -> ModelInfo:
        """根据负载选择模型（选择使用次数最少的）"""
        min_usage = float('inf')
        selected = None
        
        for model in models:
            usage = self._usage_count.get(model.name, 0)
            if usage < min_usage:
                min_usage = usage
                selected = model
        
        logger.debug(f"选择模型 (load): {selected.name}")
        return selected
    
    def _select_by_cost(self, models: List[ModelInfo]) -> ModelInfo:
        """根据成本选择模型（选择成本最低的）"""
        # 成本相同时，选择权重更高的
        models.sort(key=lambda m: (m.cost_per_token, -m.weight))
        selected = models[0]
        
        logger.debug(f"选择模型 (cost): {selected.name}")
        return selected
    
    async def update_model_stats(
        self,
        model_name: str,
        success: bool,
        response_time: float
    ):
        """更新模型统计信息"""
        async with self._lock:
            if model_name not in self._models:
                return
            
            model = self._models[model_name]
            
            # 更新使用计数
            self._usage_count[model_name] = (
                self._usage_count.get(model_name, 0) + 1
            )
            
            # 更新平均响应时间
            old_avg = model.avg_response_time
            usage = self._usage_count[model_name]
            model.avg_response_time = (
                (old_avg * (usage - 1) + response_time) / usage
            )
            
            # 更新成功率
            if success:
                # 简单移动平均
                model.success_rate = (
                    0.99 * model.success_rate + 0.01
                )
            else:
                model.success_rate = (
                    0.99 * model.success_rate - 0.01
                )
            
            logger.debug(
                f"模型统计更新: {model_name}, "
                f"成功率: {model.success_rate:.2%}, "
                f"响应时间: {model.avg_response_time:.2f}s"
            )
    
    async def set_model_available(self, model_name: str, available: bool):
        """设置模型可用性"""
        async with self._lock:
            if model_name in self._models:
                self._models[model_name].available = available
                status = "可用" if available else "不可用"
                logger.info(f"模型状态变更: {model_name} -> {status}")
    
    def list_models(self) -> List[ModelInfo]:
        """列出所有模型"""
        return list(self._models.values())
    
    def get_model_info(self, model_name: str) -> Optional[ModelInfo]:
        """获取模型信息"""
        return self._models.get(model_name)
    
    async def start_health_check(self, interval: int = 60):
        """启动健康检查"""
        self._health_check_interval = interval
        self._health_check_task = asyncio.create_task(
            self._health_check_loop()
        )
    
    async def stop_health_check(self):
        """停止健康检查"""
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
    
    async def _health_check_loop(self):
        """健康检查循环"""
        while True:
            await asyncio.sleep(self._health_check_interval)
            
            for name, model in self._models.items():
                # 这里可以实现实际的健康检查逻辑
                # 比如发送测试请求
                logger.debug(f"健康检查: {name}, 可用: {model.available}")

# 全局模型管理器实例
model_manager = ModelManager()
