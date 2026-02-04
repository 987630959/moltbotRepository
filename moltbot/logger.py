"""
日志模块
"""
import logging
import sys
from typing import Optional

def setup_logging(
    level: str = "INFO",
    format: Optional[str] = None
):
    """配置日志"""
    if format is None:
        format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    logging.basicConfig(
        level=getattr(logging, level.upper()),
        format=format,
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )

def get_logger(name: str) -> logging.Logger:
    """获取 logger"""
    return logging.getLogger(f"moltbot.{name}")
