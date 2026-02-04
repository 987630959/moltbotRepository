from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Callable, Awaitable
from enum import Enum
from datetime import datetime
import uuid

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class TaskPriority(int, Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20

class Task(BaseModel):
    """任务模型"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    prompt: str
    model: Optional[str] = None
    priority: TaskPriority = TaskPriority.NORMAL
    parameters: Dict[str, Any] = Field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[str] = None
    error: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout: int = 300  # 秒
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        use_enum_values = True

class ModelInfo(BaseModel):
    """模型信息"""
    name: str
    provider: str  # openai, anthropic, local, etc.
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 4096
    temperature: float = 0.7
    available: bool = True
    weight: int = 10  # 用于负载均衡，权重越高越优先
    avg_response_time: float = 0.0  # 平均响应时间
    success_rate: float = 1.0  # 成功率
    cost_per_token: float = 0.0  # 每 token 成本

class CallbackType(str, Enum):
    ON_COMPLETE = "on_complete"
    ON_ERROR = "on_error"
    ON_PROGRESS = "on_progress"
    ON_START = "on_start"

class WebhookConfig(BaseModel):
    """Webhook 配置"""
    url: str
    headers: Dict[str, str] = Field(default_factory=dict)
    retry_times: int = 3
    timeout: int = 10
