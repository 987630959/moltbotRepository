"""
配置管理模块
"""
from pydantic import BaseModel, Field
from typing import Dict, Optional, List
from pathlib import Path
import json
import os

class Config(BaseModel):
    """主配置类"""
    # 应用配置
    app_name: str = "MoltBot"
    debug: bool = False
    log_level: str = "INFO"
    
    # 执行引擎配置
    max_workers: int = 10
    max_concurrent_tasks: int = 100
    task_timeout: int = 300  # 默认超时时间（秒）
    retry_times: int = 3
    
    # Redis 配置（分布式支持）
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: Optional[str] = None
    use_redis: bool = False
    
    # RabbitMQ 配置（消息队列）
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_user: str = "guest"
    rabbitmq_password: str = "guest"
    use_rabbitmq: bool = False
    
    # 模型配置
    default_model: str = "gpt-3.5-turbo"
    model_selection_strategy: str = "availability"  # availability, load, cost, random
    models: Dict[str, Dict] = Field(default_factory=dict)
    
    # 回调配置
    webhook_enabled: bool = False
    webhooks: Dict[str, Dict] = Field(default_factory=dict)
    
    # API 配置
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    enable_api: bool = False

class ConfigManager:
    """配置管理器"""
    
    _instance: Optional['ConfigManager'] = None
    _config: Config
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._load_config()
        return cls._instance
    
    def _load_config(self, config_path: Optional[str] = None):
        """加载配置"""
        if config_path is None:
            config_path = os.environ.get(
                "MOLTBOT_CONFIG",
                str(Path.cwd() / "config.json")
            )
        
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config_data = json.load(f)
            self._config = Config(**config_data)
        else:
            self._config = Config()
    
    def get_config(self) -> Config:
        """获取配置"""
        return self._config
    
    def update_config(self, **kwargs):
        """更新配置"""
        for key, value in kwargs.items():
            if hasattr(self._config, key):
                setattr(self._config, key, value)
    
    def save_config(self, config_path: str = "config.json"):
        """保存配置"""
        with open(config_path, 'w') as f:
            json.dump(self._config.dict(), f, indent=2)

# 全局配置实例
config = ConfigManager()
