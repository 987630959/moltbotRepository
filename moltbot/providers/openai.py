"""
OpenAI 集成模块
"""
import asyncio
from typing import Optional, Dict, Any
from datetime import datetime

import httpx
from tenacity import (
    retry, 
    stop_after_attempt, 
    wait_exponential,
    retry_if_exception_type
)

from .models import ModelInfo
from .logger import get_logger

logger = get_logger("openai")

class OpenAIClient:
    """
    OpenAI API 客户端
    - 异步请求
    - 自动重试
    - 错误处理
    """
    
    def __init__(self, model: ModelInfo):
        self.model = model
        self.base_url = (
            model.base_url or 
            "https://api.openai.com/v1"
        )
        self.api_key = model.api_key
        self.max_tokens = model.max_tokens
        self.temperature = model.temperature
        
        self._client: Optional[httpx.AsyncClient] = None
    
    async def get_client(self) -> httpx.AsyncClient:
        """获取 HTTP 客户端"""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                }
            )
        return self._client
    
    async def close(self):
        """关闭客户端"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.RequestError, httpx.TimeoutException))
    )
    async def chat_completion(
        self,
        messages: list,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        发送聊天完成请求
        
        Args:
            messages: 消息列表
            temperature: 温度参数
            max_tokens: 最大 token 数
            **kwargs: 其他参数
            
        Returns:
            生成的文本
        """
        client = await self.get_client()
        
        payload = {
            "model": self.model.name,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
            **kwargs
        }
        
        start_time = datetime.utcnow()
        
        try:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            
            response_time = (datetime.utcnow() - start_time).total_seconds()
            logger.debug(
                f"OpenAI 请求成功: {self.model.name}, "
                f"响应时间: {response_time:.2f}s"
            )
            
            return content
            
        except httpx.HTTPStatusError as e:
            logger.error(f"OpenAI API 错误: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"OpenAI 请求失败: {e}")
            raise
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def embeddings(self, input_text: str) -> list:
        """获取文本嵌入"""
        client = await self.get_client()
        
        payload = {
            "model": "text-embedding-3-small",
            "input": input_text
        }
        
        response = await client.post(
            f"{self.base_url}/embeddings",
            json=payload
        )
        response.raise_for_status()
        
        data = response.json()
        return data["data"][0]["embedding"]


class LLMProvider:
    """
    LLM 提供商抽象
    支持多种 LLM 提供商（OpenAI, Anthropic, Local 等）
    """
    
    _providers: Dict[str, type] = {}
    
    @classmethod
    def register(cls, name: str, provider_class):
        """注册提供商"""
        cls._providers[name] = provider_class
        logger.info(f"LLM 提供商已注册: {name}")
    
    @classmethod
    def create(cls, model: ModelInfo) -> OpenAIClient:
        """创建提供商实例"""
        provider_class = cls._providers.get(model.provider)
        
        if provider_class is None:
            # 默认使用 OpenAI
            provider_class = OpenAIClient
        
        return provider_class(model)
    
    @classmethod
    def list_providers(cls) -> list:
        """列出所有已注册的提供商"""
        return list(cls._providers.keys())


# 注册默认提供商
LLMProvider.register("openai", OpenAIClient)
LLMProvider.register("openai-azure", OpenAIClient)
