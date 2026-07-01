# -*- coding: utf-8 -*-
"""
脚手架日志模块

提供完整的日志配置和管理功能，包括：
- structlog结构化日志
- Rich美化输出
- 文件日志滚动
"""

from .logger import get_logger, setup_logger, LoggerMixin

__all__ = [
    "get_logger", 
    "setup_logger", 
    "LoggerMixin"
]
